# -*- coding: utf-8 -*-
import asyncio
import json
import os
import re
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel
from db import (
    ActiveCardRevisionNotFoundError,
    ActiveCardRevisionConflictError,
    ActiveGrowingCycleExistsError,
    AgrotechRevisionProposalApplyError,
    AgrotechRevisionProposalNotFoundError,
    CropNotFoundError,
    GrowingCycleNotFinishedError,
    GrowingCycleNotFoundError,
    InvalidCycleResultError,
    NoActiveGrowingCycleError,
    aggregate_completed_hours,
    apply_agrotech_revision_proposal,
    apply_cycle_agrotech_revision_proposal,
    build_cycle_analysis_report,
    delete_old_raw_data,
    finish_growing_cycle,
    finish_growing_cycle_with_result,
    get_active_cycle_ai_context,
    get_active_cycle_norm_ranges,
    get_advisor_report,
    get_available_crops,
    get_cycle_advisor_reports,
    get_current_growing_cycle,
    get_cycle_result,
    get_crop_agrotech_card_from_db,
    get_crop_learning_history,
    get_database_model_summary,
    get_agrotech_revision_proposal,
    get_cycle_agrotech_revision_proposal,
    get_hourly_history,
    get_last_climate_records,
    get_last_water_records,
    get_recent_anomaly_events,
    get_recent_device_events,
    get_recent_ai_logs,
    get_recent_ai_recommendations,
    get_recent_hourly_summary,
    get_recent_system_feed_events,
    get_recent_telemetry,
    get_recommendation_effects,
    get_cycle_ai_recommendations,
    get_cycle_analysis_report,
    get_cycle_ai_analysis,
    get_cycle_with_result,
    get_cycle_source_revision_context,
    init_db,
    list_agrotech_revision_proposals,
    get_metric_snapshot_after,
    get_pending_recommendations_for_effect_evaluation,
    save_ai_log,
    save_ai_recommendation,
    save_cycle_analysis_report,
    save_cycle_ai_analysis,
    save_agrotech_revision_proposal,
    save_anomaly_event,
    save_cycle_result,
    save_device_event,
    save_recommendation_effect,
    save_telemetry,
    start_growing_cycle,
    update_device_status,
)
from tools import get_current_metrics

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
SENSORS_TOPIC = "farm/+/sensors/#"
POLZA_API_KEY = os.getenv("POLZA_API_KEY")
client = AsyncOpenAI(
    api_key=POLZA_API_KEY,
    base_url="https://polza.ai/api/v1"
)

AI_MODEL = os.getenv("AI_MODEL", "gpt-5-nano")
POLZA_BASE_URL = os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1/chat/completions")


def parse_int_list_env(name: str, default: list[int]) -> list[int]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    values: list[int] = []
    for part in raw_value.split(","):
        try:
            value = int(part.strip())
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return sorted(set(values)) or default


KNOWN_SENSOR_TOPICS = {
    "farm/tray_1/sensors/climate",
    "farm/tray_1/sensors/water",
}
KNOWN_DEVICE_TYPES = {"pump", "light", "fan"}
HOURLY_AGGREGATION_INTERVAL_SECONDS = 300
RAW_RETENTION_HOURS = 24
ANOMALY_EVENT_COOLDOWN_MINUTES = 5
SENSOR_STALE_SECONDS = 60
PREDICTIVE_WATCHDOG_INTERVAL_SECONDS = 600
PREDICTIVE_HISTORY_HOURS = 8
PREDICTIVE_HORIZON_HOURS = 4
PREDICTIVE_EVENT_COOLDOWN_MINUTES = 60
PREDICTIVE_MIN_POINTS = 3
RECOMMENDATION_EFFECT_WINDOWS_MINUTES = parse_int_list_env(
    "RECOMMENDATION_EFFECT_WINDOWS_MINUTES",
    [30, 60, 120],
)
RECOMMENDATION_EFFECT_INTERVAL_SECONDS = int(os.getenv("RECOMMENDATION_EFFECT_INTERVAL_SECONDS", "300"))
RECOMMENDATION_EFFECT_INTERPRETATION_NOTE = (
    "Изменение метрики наблюдалось после рекомендации, но причинно-следственная связь не доказана."
)
WATCHDOG_DEFAULT_TRAY_ID = "tray_1"
WATCHDOG_DEFAULT_NORM_RANGES = {
    "air_temp": (18.0, 28.0),
    "humidity": (50.0, 75.0),
    "water_temp": (18.0, 24.0),
    "ph": (5.5, 6.8),
    "ec": (0.8, 2.2),
}
WATCHDOG_METRIC_CONFIG = {
    "air_temp": {
        "sensor_type": "climate",
        "low_event_type": "air_overcooling",
        "high_event_type": "air_overheat",
    },
    "humidity": {
        "sensor_type": "climate",
        "low_event_type": "low_humidity",
        "high_event_type": "high_humidity",
    },
    "water_temp": {
        "sensor_type": "water",
        "low_event_type": "water_overcooling",
        "high_event_type": "water_overheat",
    },
    "ph": {
        "sensor_type": "water",
        "low_event_type": "ph_low",
        "high_event_type": "ph_high",
    },
    "ec": {
        "sensor_type": "water",
        "low_event_type": "ec_low",
        "high_event_type": "ec_high",
    },
}
PREDICTIVE_METRIC_CONFIG = {
    "air_temp": {
        "sensor_type": "climate",
        "slope_threshold": 0.5,
        "low_event_type": "predicted_air_temp_low",
        "high_event_type": "predicted_air_temp_high",
    },
    "humidity": {
        "sensor_type": "climate",
        "slope_threshold": 2.0,
        "low_event_type": "predicted_humidity_low",
        "high_event_type": "predicted_humidity_high",
    },
    "water_temp": {
        "sensor_type": "water",
        "slope_threshold": 0.3,
        "low_event_type": "predicted_water_temp_low",
        "high_event_type": "predicted_water_temp_high",
    },
    "ph": {
        "sensor_type": "water",
        "slope_threshold": 0.05,
        "low_event_type": "predicted_ph_low",
        "high_event_type": "predicted_ph_high",
    },
    "ec": {
        "sensor_type": "water",
        "slope_threshold": 0.05,
        "low_event_type": "predicted_ec_low",
        "high_event_type": "predicted_ec_high",
    },
}
SYSTEM_FEED_ANOMALY_TEXTS = {
    "ph_low": "pH ниже нормы",
    "low_ph": "pH ниже нормы",
    "ph_high": "pH выше нормы",
    "high_ph": "pH выше нормы",
    "ec_low": "EC ниже нормы",
    "low_ec": "EC ниже нормы",
    "ec_high": "EC выше нормы",
    "high_ec": "EC выше нормы",
    "water_overheat": "Температура воды выше нормы",
    "water_overcooling": "Температура воды ниже нормы",
    "air_overheat": "Температура воздуха выше нормы",
    "air_overcooling": "Температура воздуха ниже нормы",
    "low_humidity": "Влажность ниже нормы",
    "high_humidity": "Влажность выше нормы",
    "stale_climate_data": "Данные климатических датчиков давно не обновлялись",
    "stale_water_data": "Данные водных датчиков давно не обновлялись",
    "rapid_air_temp_rise": "Быстрый рост температуры воздуха",
    "predicted_ph_low": "pH снижается и может выйти ниже нормы",
    "predicted_ph_high": "pH растёт и может выйти выше нормы",
    "predicted_ec_low": "EC снижается и может выйти ниже нормы",
    "predicted_ec_high": "EC растёт и может выйти выше нормы",
    "predicted_water_temp_low": "Температура воды снижается и может выйти ниже нормы",
    "predicted_water_temp_high": "Температура воды растёт и может выйти выше нормы",
    "predicted_air_temp_low": "Температура воздуха снижается и может выйти ниже нормы",
    "predicted_air_temp_high": "Температура воздуха растёт и может выйти выше нормы",
    "predicted_humidity_low": "Влажность снижается и может выйти ниже нормы",
    "predicted_humidity_high": "Влажность растёт и может выйти выше нормы",
}
SYSTEM_FEED_DEVICE_TEXTS = {
    ("pump", "manual_on"): "Насос включён",
    ("pump", "manual_off"): "Насос выключен",
    ("light", "manual_on"): "Освещение включено",
    ("light", "manual_off"): "Освещение выключено",
    ("fan", "manual_on"): "Вентиляция включена",
    ("fan", "manual_off"): "Вентиляция выключена",
}
ADVISOR_HISTORY_HOURS = 24
AI_CONTEXT_NORM_KEYS = (
    "air_temp",
    "humidity",
    "water_temp",
    "ph",
    "ec",
    "light_hours",
    "light_intensity",
)
CHAT_SYSTEM_PROMPT = (
    "Ты — Нейрогном, дружелюбный, умный и лаконичный помощник сити-фермы. "
    "В каждом запросе тебе невидимо передаются текущие показатели датчиков и, если он есть, активный цикл выращивания.\n\n"
    "ТВОИ ПРАВИЛА:\n"
    "1. Режим молчания о цифрах: НИКОГДА не перечисляй и не упоминай текущие показатели датчиков, "
    "если пользователь прямо не спросил ('как показатели?', 'всё ли в норме?'). Для обычных бесед используй эти данные только в уме.\n"
    "2. Если backend передал активный цикл, всегда оценивай ферму относительно активной культуры, версии АгроТехКарты и дня цикла. "
    "Не выбирай культуру по догадке из сообщения пользователя, если активный цикл есть. "
    "Если пользователь спрашивает, какая версия АгроТехКарты используется, ответь только active version_label из активного цикла и не уходи в общую оценку фермы.\n"
    "3. Если пользователь спрашивает 'Всё ли нормально на ферме?', оценивай текущие датчики относительно норм активной АгроТехКарты. "
    "Используй нормы из активного цикла как приоритетные.\n"
    "4. Если активного цикла нет, честно скажи, что цикл не запущен, и предложи запустить цикл или уточнить культуру. "
    "Не подставляй lettuce, basil или любую другую культуру по умолчанию.\n"
    "5. Не утверждай, что pH или EC в норме, если по ним нет данных датчиков или в активной АгроТехКарте нет соответствующих норм.\n"
    "6. Светская беседа: Если с тобой просто здороваются или общаются на отвлеченные темы — "
    "отвечай по-человечески, тепло и без занудства.\n"
    "7. Тревога: Если ты видишь в скрытых данных, что параметры вышли за рамки, мягко предупреди об опасности и дай совет.\n"
    "8. Ограничения языка: Отвечай на русском языке. Обозначения pH и EC разрешены. "
    "Если backend передал crop_name_ru, используй только русское название культуры. "
    "crop_slug используй только внутренне; не пиши пользователю arugula, lettuce, basil и другие slug, если есть русское имя. "
    "Запрещено использовать программный код, теги или markdown-разметку. Пиши чистым, обычным текстом.\n"
    "9. Если backend передал расширенный контекст фермы, используй его как факты. "
    "Не придумывай историю устройств, если её нет в device_events. "
    "Не говори, что полив в норме, если нет истории насоса и нет достаточных данных влажности. "
    "Для pH/EC не советуй добавлять щёлочь, кислоту или менять раствор без текущего значения pH/EC.\n"
    "10. Если backend передал блок 'Контекст свежести датчиков', используй его как факт. "
    "Если water-датчики устарели, не утверждай уверенно, что pH, EC или температура воды сейчас в норме, "
    "и не советуй корректировать pH/EC без повторного свежего замера. "
    "Если climate-датчики устарели, не утверждай уверенно, что температура воздуха или влажность сейчас в норме. "
    "При stale-данных сначала советуй проверить датчик, MQTT/ESP32/симулятор и повторить измерение. "
    "Не пугай пользователя, если stale-событие старое и новые данные уже пришли. "
    "Если пользователь просто здоровается или спрашивает не про ферму, не пересказывай stale-контекст.\n"
    "11. Если пользователь задаёт follow-up вопрос с местоимениями вроде 'он', 'она', 'сколько раз', "
    "'когда последний раз', используй расширенный контекст фермы, который backend добавил на основе недавней темы диалога. "
    "Не говори, что точных данных нет, если в расширенном контексте есть counts/history из device_events.\n"
    "12. Если backend передал блок 'Прошлый опыт культуры', используй его как дополнительный источник фактов только для активной культуры. "
    "Не смешивай опыт разных культур. Не утверждай, что новая версия АгроТехКарты эффективнее, если завершённых циклов на ней ещё нет или данных недостаточно. "
    "Не делай жёсткие причинно-следственные выводы: формулируй осторожно, через 'раньше наблюдалось', 'в прошлых циклах было видно'. "
    "При советах по pH, EC, поливу и температуре учитывай прошлые проблемы и внесённые улучшения, но текущие датчики и активная АгроТехКарта важнее прошлого опыта. "
    "Не рассказывай пользователю proposal_id, revision_id, source_revision_id и внутреннюю историю версий, если он прямо не спрашивает. "
    "Если пользователь просто здоровается или спрашивает не про ферму, не пересказывай прошлый опыт.\n"
    "13. Если backend передал recommendation effects или прошлый опыт рекомендаций, не делай жёстких причинно-следственных выводов. "
    "Говори 'раньше после такой рекомендации наблюдалось...' или 'по прошлым данным эффект был неочевиден', а не 'совет помог' или 'совет улучшил показатель'. "
    "Если действие оператора не подтверждено, прямо учитывай, что нельзя подтвердить выполнение совета.\n"
    "14. Если вопрос требует фактов из БД фермы, вызывай доступные инструменты. "
    "Не придумывай количество включений устройств, pH, EC, аномалии, активную культуру или историю метрик. "
    "Если пользователь задаёт follow-up вопрос, используй историю диалога и вызывай подходящий инструмент. "
    "Если пользователь спрашивает про несколько устройств, запроси данные по каждому устройству. "
    "Если инструмент вернул has_events=false, честно скажи, что событий за период нет. "
    "Для советов про pH/EC сначала получи текущие pH/EC и нормы культуры. "
    "Не советуй добавлять щёлочь, кислоту или менять раствор без текущего значения pH. "
    "Для вопросов про конкретную культуру вызывай get_crop_card_tool. "
    "Для вопросов про текущее состояние фермы используй текущие метрики, активный цикл и, при необходимости, аномалии.\n"
    "15. Не используй повреждённый символ �. Если нужно переформулировать слово, напиши его обычными русскими буквами.\n"
    "16. Для конкретной культуры сначала используй get_crop_card_tool. "
    "Если tool вернул suitability_status='db_supported', отвечай по АгроТехКарте. "
    "Если suitability_status='compatible_not_in_db', можно дать только общую справку и обязательно сказать, что точной АгроТехКарты в БД нет. "
    "Если suitability_status='advanced_or_unsuitable', не рассказывай подробную агротехнику для этой установки; объясни, что культура может требовать другой гидропонной системы, большего объёма, опоры, опыления или другого формата выращивания. "
    "Если suitability_status='unknown', не придумывай пригодность культуры и предложи выбрать из supported_crops. "
    "Для текущей установки приоритетные культуры: зелень, травы, микрозелень и компактные листовые культуры. "
    "Не представляй плодоносящие крупные культуры как подходящие для маленьких стаканчиков, если они не поддерживаются БД."
)

CROP_ALIASES: dict[str, tuple[str, ...]] = {
    "basil": ("basil", "базилик"),
    "arugula": ("arugula", "руккола", "рукола"),
    "lettuce": ("lettuce", "латук", "салат латук", "листовой салат", "салат"),
    "spinach": ("spinach", "шпинат"),
    "cilantro": ("cilantro", "кинза", "кориандр"),
    "parsley": ("parsley", "петрушка"),
    "mint": ("mint", "мята"),
    "dill": ("dill", "укроп"),
    "pak_choi": ("pak_choi", "pak choi", "pak-choi", "пак-чой", "пак чой"),
    "chard": ("chard", "мангольд"),
}


CITY_FARM_COMPATIBLE_CROP_ALIASES: dict[str, tuple[str, ...]] = {
    "basil": ("базилик", "basil"),
    "arugula": ("руккола", "рукола", "arugula"),
    "lettuce": ("салат", "латук", "lettuce"),
    "spinach": ("шпинат", "spinach"),
    "cilantro": ("кинза", "cilantro", "coriander"),
    "dill": ("укроп", "dill"),
    "mint": ("мята", "mint"),
    "parsley": ("петрушка", "parsley"),
    "pak_choi": ("пак-чой", "пак чой", "pak choi", "bok choy"),
    "chard": ("мангольд", "chard", "swiss chard"),
    "microgreens": ("микрозелень", "microgreens"),
}


CITY_FARM_ADVANCED_OR_UNSUITABLE_CROP_ALIASES: dict[str, tuple[str, ...]] = {
    "cucumber": ("огурец", "огурцы", "cucumber", "cucumbers"),
    "tomato": ("томат", "томаты", "помидор", "помидоры", "tomato", "tomatoes"),
    "pepper": ("перец", "перцы", "pepper", "peppers"),
    "eggplant": ("баклажан", "баклажаны", "eggplant"),
    "melon": ("дыня", "дыни", "арбуз", "арбузы", "melon", "watermelon"),
    "carrot": ("морковь", "carrot"),
    "potato": ("картофель", "potato"),
    "beet": ("свекла", "свёкла", "beet"),
    "radish": ("редис", "редиска", "radish"),
    "pea": ("горох", "pea"),
}


def detect_crops_in_message(message: str) -> list[str]:
    normalized_message = message.lower().replace("ё", "е")
    detected: list[str] = []

    for slug, aliases in CROP_ALIASES.items():
        for alias in aliases:
            normalized_alias = alias.lower().replace("ё", "е")
            pattern = rf"(?<![\w]){re.escape(normalized_alias)}(?![\w])"
            if re.search(pattern, normalized_message, re.IGNORECASE):
                detected.append(slug)
                break

    return detected


def normalize_dialog_text(text: Any) -> str:
    normalized = str(text or "").strip().lower().replace("ё", "е")
    normalized = normalized.replace("_", " ").replace("-", " ")
    return " ".join(normalized.split())


def get_crop_lookup_aliases() -> dict[str, set[str]]:
    aliases_by_slug: dict[str, set[str]] = {}

    for slug, aliases in CROP_ALIASES.items():
        aliases_by_slug.setdefault(slug, set()).update(
            normalize_dialog_text(alias)
            for alias in aliases
            if normalize_dialog_text(alias)
        )

    try:
        available_crops = get_available_crops()
    except Exception:
        available_crops = []

    for crop in available_crops:
        slug = str(crop.get("slug") or crop.get("crop_slug") or "").strip()
        if not slug:
            continue
        crop_aliases = aliases_by_slug.setdefault(slug, set())
        for value in (slug, crop.get("name_ru"), crop.get("crop_name_ru")):
            normalized_value = normalize_dialog_text(value)
            if normalized_value:
                crop_aliases.add(normalized_value)

    return aliases_by_slug


def find_crop_alias_match(text: str, alias: str) -> re.Match[str] | None:
    if not alias:
        return None
    if re.search(r"[а-я]", alias, re.IGNORECASE) and " " not in alias and len(alias) >= 5:
        stem = alias[:-1] if alias[-1] in "аяьй" else alias
        pattern = rf"(?<![\w]){re.escape(stem)}[а-я]*(?![\w])"
    else:
        pattern = rf"(?<![\w]){re.escape(alias)}(?![\w])"
    return next(re.finditer(pattern, text, re.IGNORECASE), None)


def find_city_farm_crop_alias(
    text: str,
    aliases_by_crop: dict[str, tuple[str, ...]],
) -> str | None:
    normalized_text = normalize_dialog_text(text)
    if not normalized_text:
        return None

    latest_crop: str | None = None
    latest_position = -1
    for crop, aliases in aliases_by_crop.items():
        for alias in aliases:
            match = find_crop_alias_match(normalized_text, normalize_dialog_text(alias))
            if match and match.start() >= latest_position:
                latest_crop = crop
                latest_position = match.start()

    return latest_crop


def get_supported_city_farm_crops() -> list[str]:
    supported = set(CITY_FARM_COMPATIBLE_CROP_ALIASES.keys())
    try:
        for crop in get_available_crops():
            slug = str(crop.get("slug") or crop.get("crop_slug") or "").strip()
            name = str(crop.get("name_ru") or crop.get("crop_name_ru") or "").strip()
            if name:
                supported.add(name)
            elif slug:
                supported.add(slug)
    except Exception:
        pass
    return sorted(supported)


def classify_crop_suitability_for_city_farm(crop_name_or_slug: str) -> dict[str, Any]:
    requested_crop = str(crop_name_or_slug or "").strip()
    normalized_crop = normalize_dialog_text(requested_crop)
    supported_crops = get_supported_city_farm_crops()

    card = get_crop_agrotech_card_from_db(requested_crop)
    if card is None:
        detected_crop = extract_explicit_crop_from_text(requested_crop)
        card = get_crop_agrotech_card_from_db(detected_crop) if detected_crop else None

    if card is not None:
        return {
            "normalized_crop": card.get("crop_slug") or normalized_crop,
            "status": "db_supported",
            "reason": "Культура найдена в БД АгроТехКарт.",
            "supported_crops": supported_crops,
            "card": card,
        }

    compatible_crop = find_city_farm_crop_alias(normalized_crop, CITY_FARM_COMPATIBLE_CROP_ALIASES)
    if compatible_crop:
        return {
            "normalized_crop": compatible_crop,
            "status": "compatible_not_in_db",
            "reason": "Культура подходит для компактной гидропонной сити-фермы, но её точной АгроТехКарты пока нет в БД.",
            "supported_crops": supported_crops,
        }

    unsuitable_crop = find_city_farm_crop_alias(normalized_crop, CITY_FARM_ADVANCED_OR_UNSUITABLE_CROP_ALIASES)
    if unsuitable_crop:
        return {
            "normalized_crop": unsuitable_crop,
            "status": "advanced_or_unsuitable",
            "reason": "Культура требует другой системы выращивания или не подходит для текущей маленькой установки со стаканчиками.",
            "supported_crops": supported_crops,
        }

    return {
        "normalized_crop": normalized_crop,
        "status": "unknown",
        "reason": "Культура не найдена в БД и не классифицирована как подходящая для текущей компактной сити-фермы.",
        "supported_crops": supported_crops,
    }


def extract_explicit_crop_from_text(text: Any, aliases_by_slug: dict[str, set[str]] | None = None) -> str | None:
    normalized_text = normalize_dialog_text(text)
    if not normalized_text:
        return None

    aliases_by_slug = aliases_by_slug or get_crop_lookup_aliases()
    latest_slug: str | None = None
    latest_position = -1
    for slug, aliases in aliases_by_slug.items():
        for alias in aliases:
            match = find_crop_alias_match(normalized_text, alias)
            if match and match.start() >= latest_position:
                latest_slug = slug
                latest_position = match.start()

    return latest_slug


def extract_last_explicit_crop_from_messages(messages: list | None, current_message: str | None = None, limit: int = 6) -> str | None:
    latest_slug: str | None = None
    aliases_by_slug = get_crop_lookup_aliases()
    if isinstance(messages, list):
        for item in messages[-limit:]:
            if not isinstance(item, dict):
                continue
            slug = extract_explicit_crop_from_text(item.get("content") or item.get("text") or "", aliases_by_slug)
            if slug:
                latest_slug = slug

    if current_message is not None:
        slug = extract_explicit_crop_from_text(current_message, aliases_by_slug)
        if slug:
            latest_slug = slug

    return latest_slug


def is_crop_follow_up_message(message: str) -> bool:
    text = normalize_dialog_text(message)
    if not text:
        return False

    crop_phrases = (
        "эта культура", "этой культуре", "это растение", "растение", "культура",
        "для нее", "для него", "у нее", "у него", "ей нужен", "ему нужен",
        "ей нужна", "ему нужна", "ей нужно", "ему нужно",
        "а это нормально", "это нормально растет", "это нормально растёт",
    )
    if any(phrase in text for phrase in crop_phrases):
        return True

    has_reference = bool(re.search(r"(?<![\w])(она|оно|он|ей|ему|ее|его|нее|него)(?![\w])", text))
    crop_question_markers = (
        "норм", "растет", "растёт", "рост", "ph", "ec", "нужен", "нужна",
        "нужно", "высокий", "низкий", "питание", "раствор",
    )
    device_markers = ("насос", "лампа", "свет", "вентилятор", "включался", "выключался", "срабатывал")
    if re.search(r"(?<![\w])а\s+(она|оно)(?![\w])", text) and not any(marker in text for marker in device_markers):
        return True
    if has_reference and any(marker in text for marker in crop_question_markers):
        return not any(marker in text for marker in device_markers)

    return False


def is_root_radish_question(message: str) -> bool:
    normalized_message = message.lower().replace("ё", "е")
    asks_about_radish = re.search(r"(?<![\w])редис[а-я]*(?![\w])", normalized_message, re.IGNORECASE)
    return bool(asks_about_radish)


def is_regular_pea_question(message: str) -> bool:
    normalized_message = message.lower().replace("ё", "е")
    asks_about_pea = re.search(r"(?<![\w])горох[а-я]*(?![\w])", normalized_message, re.IGNORECASE)
    return bool(asks_about_pea)


def build_unsupported_crop_context(message: str) -> str:
    notes: list[str] = []

    if is_root_radish_question(message):
        notes.append(
            "Редис и микрозелень редиса удалены из дипломной базы культур. "
            "Не выдавай нормы редиса как нормы другой культуры и не предлагай замену на его микрозелень."
        )
    if is_regular_pea_question(message):
        notes.append(
            "Горох, микрозелень гороха и побеги гороха удалены из дипломной базы культур. "
            "Не выдавай нормы гороха как нормы другой культуры и не предлагай замену на его микрозелень."
        )

    if not notes:
        return ""

    return "Ограничение базы культур:\n" + "\n".join(f"- {note}" for note in notes)


def build_crop_rules_context(crops: list[str]) -> str:
    sections: list[str] = []

    for crop in crops[:3]:
        card = get_crop_agrotech_card_from_db(crop)
        if not card:
            continue

        crop_title = card.get("crop_name_ru") or card.get("crop_slug") or crop
        norms = card.get("norms") if isinstance(card.get("norms"), dict) else {}
        card_sections = card.get("sections") if isinstance(card.get("sections"), list) else []
        section_text = "\n\n".join(
            f"{section.get('section_title')}\n{section.get('content')}"
            for section in card_sections
            if section.get("content")
        )
        sections.append(
            "\n".join(
                part
                for part in (
                    f"Культура: {crop_title}",
                    f"Версия АгроТехКарты: {card.get('version_label')}",
                    f"Нормы из БД: {json.dumps(norms, ensure_ascii=False)}" if norms else "Нормы в БД не найдены.",
                    section_text,
                )
                if part
            )
        )

    if not sections:
        return ""

    return (
        "База знаний культур из PostgreSQL. Используй этот блок как главный источник "
        "по нормам pH, EC, температуре, циклам, алертам и рекомендациям.\n\n"
        + "\n\n---\n\n".join(sections)
    )


def detect_anomalies(records: list[dict[str, Any]]) -> list[str]:
    anomalies: list[str] = []

    if not records:
        return anomalies

    latest_payload = records[-1].get("parsed_payload", {})
    if not isinstance(latest_payload, dict):
        latest_payload = {}

    air_temp = latest_payload.get("air_temp")
    humidity = latest_payload.get("humidity")

    if isinstance(air_temp, (int, float)) and air_temp > 28:
        anomalies.append(f"Перегрев воздуха: air_temp={air_temp}")

    if isinstance(air_temp, (int, float)) and air_temp < 18:
        anomalies.append(f"Переохлаждение воздуха: air_temp={air_temp}")

    if isinstance(humidity, (int, float)) and humidity < 50:
        anomalies.append(f"Низкая влажность: humidity={humidity}")

    if len(records) >= 3:
        first_payload = records[0].get("parsed_payload", {})
        last_payload = records[-1].get("parsed_payload", {})
        if isinstance(first_payload, dict) and isinstance(last_payload, dict):
            first_temp = first_payload.get("air_temp")
            last_temp = last_payload.get("air_temp")
            if isinstance(first_temp, (int, float)) and isinstance(last_temp, (int, float)):
                if last_temp - first_temp > 2:
                    anomalies.append(
                        "Быстрый рост температуры воздуха: "
                        f"{first_temp} -> {last_temp} за последние 3 замера"
                    )

    return anomalies


def get_record_tray_id(record: dict[str, Any]) -> str:
    tray_id = record.get("tray_id")
    if isinstance(tray_id, str) and tray_id:
        return tray_id

    topic = str(record.get("topic", ""))
    parts = topic.split("/")
    if len(parts) > 1 and parts[1]:
        return parts[1]

    return "unknown"


def record_sort_value(record: dict[str, Any]) -> Any:
    recorded_at = record.get("recorded_at")
    if isinstance(recorded_at, datetime):
        return (0, recorded_at)
    return (1, record.get("id") or 0, str(record.get("timestamp") or ""))


def sorted_watchdog_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=record_sort_value)


def watchdog_tray_id(*record_groups: list[dict[str, Any]]) -> str:
    for records in record_groups:
        for record in reversed(records):
            tray_id = get_record_tray_id(record)
            if tray_id != "unknown":
                return tray_id
    return WATCHDOG_DEFAULT_TRAY_ID


def build_watchdog_norm_ranges(active_ranges: dict[str, tuple[float, float]] | None) -> dict[str, tuple[float, float]]:
    ranges = dict(WATCHDOG_DEFAULT_NORM_RANGES)
    if active_ranges:
        ranges.update(active_ranges)
    return ranges


def sensor_record_age_seconds(record: dict[str, Any] | None) -> float | None:
    if not record:
        return None

    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, datetime):
        return None

    now = datetime.now(recorded_at.tzinfo) if recorded_at.tzinfo else datetime.now()
    return max(0.0, (now - recorded_at).total_seconds())


def append_stale_sensor_event(
    events: list[dict[str, Any]],
    *,
    records: list[dict[str, Any]],
    tray_id: str,
    sensor_type: str,
    event_type: str,
) -> None:
    latest_record = records[-1] if records else None
    age_seconds = sensor_record_age_seconds(latest_record)
    if latest_record is not None and (age_seconds is None or age_seconds <= SENSOR_STALE_SECONDS):
        return

    recorded_at = latest_record.get("recorded_at") if latest_record else None
    events.append(
        {
            "tray_id": tray_id,
            "sensor_type": sensor_type,
            "event_type": event_type,
            "metric_name": None,
            "severity": "warning",
            "value": None,
            "message": f"Устаревшие данные датчика {sensor_type}",
            "payload": {
                "age_seconds": age_seconds,
                "stale_after_seconds": SENSOR_STALE_SECONDS,
                "last_recorded_at": recorded_at.isoformat() if isinstance(recorded_at, datetime) else None,
            },
        }
    )


def build_metric_anomaly_event(
    *,
    tray_id: str,
    metric_name: str,
    value: float,
    limit: float,
    direction: Literal["low", "high"],
    event_type: str,
    sensor_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    relation = "<" if direction == "low" else ">"
    return {
        "tray_id": tray_id,
        "sensor_type": sensor_type,
        "event_type": event_type,
        "metric_name": metric_name,
        "severity": "warning",
        "value": float(value),
        "message": f"{metric_name} вне нормы: {value} {relation} {limit}",
        "payload": payload,
    }


def build_anomaly_events(
    climate_records: list[dict[str, Any]],
    water_records: list[dict[str, Any]] | None = None,
    norm_ranges: dict[str, tuple[float, float]] | None = None,
) -> list[dict[str, Any]]:
    water_records = water_records or []
    climate_records = sorted_watchdog_records(climate_records)
    water_records = sorted_watchdog_records(water_records)
    all_records = sorted_watchdog_records([*climate_records, *water_records])
    ranges = build_watchdog_norm_ranges(norm_ranges)
    events: list[dict[str, Any]] = []
    tray_id = watchdog_tray_id(climate_records, water_records)

    append_stale_sensor_event(
        events,
        records=climate_records,
        tray_id=tray_id,
        sensor_type="climate",
        event_type="stale_climate_data",
    )
    append_stale_sensor_event(
        events,
        records=water_records,
        tray_id=tray_id,
        sensor_type="water",
        event_type="stale_water_data",
    )

    if all_records:
        snapshot = latest_metric_snapshot(all_records)
        payload = {
            "latest_values": {
                metric_name: snapshot.get(metric_name)
                for metric_name in WATCHDOG_METRIC_CONFIG
            },
            "norm_ranges": {
                metric_name: {"min": metric_range[0], "max": metric_range[1]}
                for metric_name, metric_range in ranges.items()
            },
        }

        for metric_name, config in WATCHDOG_METRIC_CONFIG.items():
            value = snapshot.get(metric_name)
            if not isinstance(value, (int, float)):
                continue

            low, high = ranges[metric_name]
            if value < low:
                events.append(
                    build_metric_anomaly_event(
                        tray_id=tray_id,
                        metric_name=metric_name,
                        value=float(value),
                        limit=low,
                        direction="low",
                        event_type=str(config["low_event_type"]),
                        sensor_type=str(config["sensor_type"]),
                        payload=payload,
                    )
                )
            elif value > high:
                events.append(
                    build_metric_anomaly_event(
                        tray_id=tray_id,
                        metric_name=metric_name,
                        value=float(value),
                        limit=high,
                        direction="high",
                        event_type=str(config["high_event_type"]),
                        sensor_type=str(config["sensor_type"]),
                        payload=payload,
                    )
                )

    if len(climate_records) >= 3:
        first_payload = climate_records[0].get("parsed_payload", {})
        last_payload = climate_records[-1].get("parsed_payload", {})
        if isinstance(first_payload, dict) and isinstance(last_payload, dict):
            first_temp = first_payload.get("air_temp")
            last_temp = last_payload.get("air_temp")
            if isinstance(first_temp, (int, float)) and isinstance(last_temp, (int, float)):
                if last_temp - first_temp > 2:
                    events.append(
                        {
                            "tray_id": tray_id,
                            "sensor_type": "climate",
                            "event_type": "rapid_air_temp_rise",
                            "metric_name": "air_temp",
                            "severity": "warning",
                            "value": float(last_temp),
                            "message": (
                                "Быстрый рост температуры воздуха: "
                                f"{first_temp} -> {last_temp} за последние 3 замера"
                            ),
                            "payload": {
                                "first_air_temp": first_temp,
                                "last_air_temp": last_temp,
                                "latest_payload": last_payload,
                            },
                        }
                    )

    return events


async def save_watchdog_anomaly_events(events: list[dict[str, Any]]) -> None:
    for event in events:
        saved = await asyncio.to_thread(
            save_anomaly_event,
            tray_id=event["tray_id"],
            sensor_type=event["sensor_type"],
            event_type=event["event_type"],
            metric_name=event["metric_name"],
            severity=event["severity"],
            value=event["value"],
            message=event["message"],
            payload=event["payload"],
            cooldown_minutes=ANOMALY_EVENT_COOLDOWN_MINUTES,
        )
        if saved:
            print(f"[WATCHDOG] Anomaly event saved: {event['event_type']} {event['metric_name']}")


def system_feed_time(created_at: Any) -> str:
    timestamp = str(created_at or "")
    if len(timestamp) >= 16:
        return timestamp[11:16]
    return timestamp


def system_feed_device_key(device_id: Any) -> str | None:
    device_text = str(device_id or "").lower()
    for device_key in ("pump", "light", "fan"):
        if device_key in device_text:
            return device_key
    return None


def format_system_feed_item(row: dict[str, Any]) -> dict[str, Any]:
    feed_type = str(row.get("feed_type") or "system")
    event_type = str(row.get("event_type") or row.get("command") or "")
    created_at = row.get("created_at") or ""

    if feed_type == "anomaly":
        text = SYSTEM_FEED_ANOMALY_TEXTS.get(event_type) or str(row.get("message") or "Системный алерт")
    elif feed_type == "device":
        device_key = system_feed_device_key(row.get("device_id"))
        text = SYSTEM_FEED_DEVICE_TEXTS.get((device_key, event_type), "Событие устройства")
    else:
        text = "Системное событие"

    return {
        "id": f"{feed_type}-{row.get('id')}",
        "type": feed_type,
        "severity": row.get("severity") or ("warning" if feed_type == "anomaly" else "info"),
        "text": text,
        "time": system_feed_time(created_at),
        "created_at": created_at,
    }


def numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def collect_hourly_metric_values(
    hourly_rows: list[dict[str, Any]],
    metric_name: str,
) -> list[tuple[datetime | None, float]]:
    value_key = f"{metric_name}_avg"
    count_key = f"{metric_name}_count"
    values: list[tuple[datetime | None, float]] = []

    for row in hourly_rows:
        value = numeric_value(row.get(value_key))
        if value is None:
            continue
        count_value = row.get(count_key)
        if isinstance(count_value, int) and count_value <= 0:
            continue
        values.append((parse_event_timestamp(row.get("hour_start")), value))

    return sorted(values, key=lambda item: item[0] or datetime.min)


def calculate_slope_per_hour(values: list[tuple[datetime | None, float]]) -> float | None:
    if len(values) < PREDICTIVE_MIN_POINTS:
        return None

    first_time, first_value = values[0]
    last_time, last_value = values[-1]
    hours_span = float(len(values) - 1)
    if first_time is not None and last_time is not None:
        measured_hours = (last_time - first_time).total_seconds() / 3600
        if measured_hours > 0:
            hours_span = measured_hours

    if hours_span <= 0:
        return None
    return (last_value - first_value) / hours_span


def is_stable_trend(recent_values: list[float], direction: Literal["low", "high"], threshold: float) -> bool:
    if len(recent_values) < PREDICTIVE_MIN_POINTS:
        return False

    sign = 1 if direction == "high" else -1
    noise_floor = threshold / 2
    meaningful_deltas = [
        sign * (current_value - previous_value)
        for previous_value, current_value in zip(recent_values, recent_values[1:])
        if abs(current_value - previous_value) >= noise_floor
    ]
    if len(meaningful_deltas) < 2:
        return False

    positive_steps = [delta for delta in meaningful_deltas if delta > 0]
    negative_steps = [delta for delta in meaningful_deltas if delta < 0]
    positive_total = sum(positive_steps)
    negative_total = abs(sum(negative_steps))

    return (
        len(positive_steps) >= max(2, len(meaningful_deltas) - 1)
        and positive_total > negative_total * 2
    )


def build_predictive_anomaly_events(
    hourly_rows: list[dict[str, Any]],
    norm_ranges: dict[str, tuple[float, float]],
    tray_id: str = WATCHDOG_DEFAULT_TRAY_ID,
) -> list[dict[str, Any]]:
    if not norm_ranges:
        return []

    events: list[dict[str, Any]] = []
    for metric_name, config in PREDICTIVE_METRIC_CONFIG.items():
        metric_range = norm_ranges.get(metric_name)
        if metric_range is None:
            continue

        min_norm, max_norm = metric_range
        values_with_time = collect_hourly_metric_values(hourly_rows, metric_name)
        if len(values_with_time) < PREDICTIVE_MIN_POINTS:
            continue

        recent_values = [value for _, value in values_with_time]
        current_value = recent_values[-1]
        if current_value < min_norm or current_value > max_norm:
            continue

        slope_per_hour = calculate_slope_per_hour(values_with_time)
        threshold = float(config["slope_threshold"])
        if slope_per_hour is None or abs(slope_per_hour) < threshold:
            continue

        direction: Literal["low", "high"] = "high" if slope_per_hour > 0 else "low"
        if not is_stable_trend(recent_values, direction, threshold):
            continue

        if direction == "high":
            predicted_boundary = max_norm
            predicted_hours = (max_norm - current_value) / slope_per_hour
            event_type = str(config["high_event_type"])
        else:
            predicted_boundary = min_norm
            predicted_hours = (current_value - min_norm) / abs(slope_per_hour)
            event_type = str(config["low_event_type"])

        if predicted_hours <= 0 or predicted_hours > PREDICTIVE_HORIZON_HOURS:
            continue

        message = SYSTEM_FEED_ANOMALY_TEXTS[event_type]
        events.append(
            {
                "tray_id": tray_id,
                "sensor_type": str(config["sensor_type"]),
                "event_type": event_type,
                "metric_name": metric_name,
                "severity": "warning",
                "value": current_value,
                "message": message,
                "payload": {
                    "metric_name": metric_name,
                    "current_value": current_value,
                    "min_norm": min_norm,
                    "max_norm": max_norm,
                    "slope_per_hour": slope_per_hour,
                    "predicted_boundary": predicted_boundary,
                    "predicted_hours_to_boundary": predicted_hours,
                    "recent_values": recent_values,
                    "source": "predictive_trend",
                },
            }
        )

    return events


async def save_predictive_anomaly_events(events: list[dict[str, Any]]) -> None:
    for event in events:
        saved = await asyncio.to_thread(
            save_anomaly_event,
            tray_id=event["tray_id"],
            sensor_type=event["sensor_type"],
            event_type=event["event_type"],
            metric_name=event["metric_name"],
            severity=event["severity"],
            value=event["value"],
            message=event["message"],
            payload=event["payload"],
            cooldown_minutes=PREDICTIVE_EVENT_COOLDOWN_MINUTES,
        )
        if saved:
            print(f"[PREDICTIVE] Anomaly event saved: {event['event_type']} {event['metric_name']}")


def norm_ranges_from_db(norms: Any) -> dict[str, tuple[float, float]]:
    if not isinstance(norms, dict):
        return {}

    parsed: dict[str, tuple[float, float]] = {}
    for metric_name in ("air_temp", "humidity", "water_temp", "ph", "ec"):
        value = norms.get(metric_name)
        if not isinstance(value, dict):
            continue
        low = value.get("min")
        high = value.get("max")
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            continue
        parsed[metric_name] = (float(low), float(high))
    return parsed


def latest_metric_snapshot(records: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "tray_id": None,
        "air_temp": None,
        "humidity": None,
        "water_temp": None,
        "ph": None,
        "ec": None,
    }

    for record in reversed(records):
        if snapshot["tray_id"] is None:
            snapshot["tray_id"] = get_record_tray_id(record)

        payload = record.get("parsed_payload")
        if not isinstance(payload, dict):
            continue

        payload_values = {
            "air_temp": payload.get("air_temp"),
            "humidity": payload.get("humidity"),
            "water_temp": payload.get("water_temp"),
            "ph": payload.get("ph", payload.get("pH")),
            "ec": payload.get("ec", payload.get("EC")),
        }
        for metric_name, value in payload_values.items():
            if snapshot[metric_name] is None and isinstance(value, (int, float)):
                snapshot[metric_name] = value

    if snapshot["tray_id"] is None:
        snapshot["tray_id"] = "unknown"

    return snapshot


def describe_trend(values: list[float], metric_title: str, threshold: float) -> str | None:
    if len(values) < 2:
        return None

    delta = values[-1] - values[0]
    if abs(delta) < threshold:
        return f"{metric_title} по почасовой истории в целом стабильна."

    direction = "растёт" if delta > 0 else "снижается"
    return f"{metric_title} по почасовой истории {direction}: изменение {delta:+.1f} за период."


def build_hourly_trend_notes(hourly_rows: list[dict[str, Any]]) -> list[str]:
    metric_config = [
        ("air_temp_avg", "Температура воздуха", 0.7),
        ("humidity_avg", "Влажность", 3.0),
        ("water_temp_avg", "Температура воды", 0.7),
        ("ph_avg", "pH", 0.2),
        ("ec_avg", "EC", 0.2),
    ]
    notes: list[str] = []

    for column_name, title, threshold in metric_config:
        values = [
            float(row[column_name])
            for row in hourly_rows
            if isinstance(row.get(column_name), (int, float))
        ]
        note = describe_trend(values, title, threshold)
        if note:
            notes.append(note)

    return notes


def build_advisor_response(crop: str) -> dict[str, Any]:
    telemetry_records = get_recent_telemetry(30)
    current = latest_metric_snapshot(telemetry_records)
    hourly_rows = get_recent_hourly_summary(ADVISOR_HISTORY_HOURS)
    anomaly_events = get_recent_anomaly_events(ADVISOR_HISTORY_HOURS)
    crop_card = None
    crop_ranges = get_active_cycle_norm_ranges("tray_1")
    crop_ranges_source = "database_active_cycle" if crop_ranges else "database_crop_card"
    if not crop_ranges:
        crop_card = get_crop_agrotech_card_from_db(crop)
        crop_ranges = norm_ranges_from_db(crop_card.get("norms") if crop_card else None)
    if not crop_ranges:
        crop_ranges_source = "database_missing"

    risks: list[str] = []
    recommendations: list[str] = []
    trend_notes = build_hourly_trend_notes(hourly_rows)
    if not crop_ranges:
        risks.append(f"Нормы для культуры '{crop}' не найдены в БД.")

    if not telemetry_records:
        return {
            "summary": "Данных телеметрии пока недостаточно для агрономической оценки.",
            "risks": ["Нет свежих показаний телеметрии."],
            "recommendations": ["Запустите симулятор или проверьте поступление MQTT-данных."],
            "data": {
                "crop": crop,
                "current": current,
                "history_hours": ADVISOR_HISTORY_HOURS,
                "hourly_points": len(hourly_rows),
                "anomaly_events": len(anomaly_events),
                "crop_ranges_source": crop_ranges_source,
            },
        }

    metric_titles = {
        "air_temp": "температура воздуха",
        "humidity": "влажность",
        "water_temp": "температура воды",
        "ph": "pH",
        "ec": "EC",
    }

    for metric_name, title in metric_titles.items():
        value = current.get(metric_name)
        metric_range = crop_ranges.get(metric_name)
        if value is None:
            if metric_name == "ph":
                risks.append("Данных по pH пока нет.")
            elif metric_name == "ec":
                risks.append("Данных по EC пока нет.")
            continue
        if metric_range is None:
            continue

        low, high = metric_range
        if value < low:
            risks.append(f"{title.capitalize()} ниже ориентира культуры: {value} при норме {low:g}-{high:g}.")
        elif value > high:
            risks.append(f"{title.capitalize()} выше ориентира культуры: {value} при норме {low:g}-{high:g}.")

    if anomaly_events:
        grouped_events: dict[str, int] = {}
        for event in anomaly_events:
            event_type = str(event.get("event_type", "unknown"))
            grouped_events[event_type] = grouped_events.get(event_type, 0) + 1
        event_text = ", ".join(f"{event_type}: {count}" for event_type, count in grouped_events.items())
        risks.append(f"За последние 24 часа зафиксированы события аномалий: {event_text}.")

    if len(hourly_rows) < 2:
        recommendations.append("Почасовой истории пока мало, поэтому оценка трендов ограничена.")
    else:
        recommendations.extend(trend_notes)

    if current.get("air_temp") is not None and current["air_temp"] > 28:
        recommendations.append("Проверьте вентиляцию и не увеличивайте интенсивность освещения до стабилизации температуры.")
    if current.get("humidity") is not None and current["humidity"] < 50:
        recommendations.append("Проверьте влажность субстрата и режим увлажнения, но не включайте оборудование без ручной проверки.")
    if current.get("ph") is None and current.get("ec") is None:
        recommendations.append("Данных по pH и EC пока нет, поэтому рекомендации по питательному раствору ограничены.")
    elif current.get("ph") is None:
        recommendations.append("Данных по pH пока нет, поэтому рекомендации по кислотности раствора ограничены.")
    elif current.get("ec") is None:
        recommendations.append("Данных по EC пока нет, поэтому рекомендации по концентрации раствора ограничены.")

    if not risks:
        risks.append("Существенных рисков по доступным данным не обнаружено.")
    if not recommendations:
        recommendations.append("Продолжайте наблюдение и дождитесь накопления почасовой истории для более точных выводов.")

    if risks == ["Существенных рисков по доступным данным не обнаружено."] and not anomaly_events:
        summary = "Состояние фермы стабильное по доступным текущим показателям."
    else:
        summary = "Есть факторы, требующие внимания агронома."

    if anomaly_events:
        summary += f" За последние 24 часа найдено событий аномалий: {len(anomaly_events)}."
    if len(hourly_rows) < 2:
        summary += " Почасовой истории пока недостаточно для уверенного анализа трендов."

    return {
        "summary": summary,
        "risks": risks,
        "recommendations": recommendations,
        "data": {
            "crop": crop,
            "current": current,
            "history_hours": ADVISOR_HISTORY_HOURS,
            "hourly_points": len(hourly_rows),
            "anomaly_events": len(anomaly_events),
            "crop_rules_loaded": bool(crop_ranges),
            "crop_ranges_source": crop_ranges_source,
        },
    }


def strip_markdown_backticks(raw_text: str) -> str:
    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned[3:].lstrip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip(" \n\r\t:")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

    cleaned = cleaned.strip("`").strip()

    if cleaned.lower().startswith("json"):
        candidate = cleaned[4:].lstrip(" \n\r\t:")
        if candidate.startswith("{") or candidate.startswith("["):
            cleaned = candidate

    return cleaned.replace("```", "").strip()


def format_sensor_value(value: Any, suffix: str) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1f}{suffix}"
    return "нет данных"


def format_sensor_payload_russian(payload: dict[str, Any]) -> str:
    parts: list[str] = []

    if "air_temp" in payload:
        parts.append(f"Температура воздуха {format_sensor_value(payload.get('air_temp'), ' C')}")
    if "humidity" in payload:
        parts.append(f"Влажность {format_sensor_value(payload.get('humidity'), '%')}")
    if "water_temp" in payload:
        parts.append(f"Температура воды {format_sensor_value(payload.get('water_temp'), ' C')}")

    return ", ".join(parts) if parts else "Нет данных с датчиков"


def format_telemetry_records_russian(records: list[dict[str, Any]]) -> str:
    formatted: list[str] = []

    for record in records:
        payload = record.get("parsed_payload")
        if not isinstance(payload, dict):
            continue

        timestamp = str(record.get("timestamp", ""))
        formatted_payload = format_sensor_payload_russian(payload)
        if timestamp:
            formatted.append(f"{timestamp}: {formatted_payload}")
        else:
            formatted.append(formatted_payload)

    return "\n".join(formatted) if formatted else "Нет данных с датчиков"


def add_analysis_step(analysis_steps: list[str] | None, step: str) -> None:
    if analysis_steps is not None and step not in analysis_steps:
        analysis_steps.append(step)


def sanitize_ai_reply(text: str) -> str:
    if not text:
        return ""

    cleaned = str(text)
    if "\uFFFD" in cleaned:
        cleaned = cleaned.replace("\uFFFD", "")
        print("[AI_SANITIZE] Removed replacement characters from AI reply")

    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip()


FARM_AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_metrics_tool",
            "description": "Получить текущие показатели фермы: температура воздуха, влажность, температура воды, pH, EC.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_cycle_tool",
            "description": "Получить активный цикл выращивания для tray_id: культура, день цикла, версия АгроТехКарты, нормы.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tray_id": {
                        "type": "string",
                        "description": "Лоток фермы. По умолчанию tray_1.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_events_tool",
            "description": (
                "Получить историю событий устройств за период. Используй, когда пользователь спрашивает, "
                "включалось ли устройство, сколько раз, когда последний раз, как часто срабатывало."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tray_id": {
                        "type": "string",
                        "description": "Лоток фермы. По умолчанию tray_1.",
                    },
                    "device_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["pump", "fan", "light"]},
                        "description": "Типы устройств: pump, fan, light.",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Период в часах. По умолчанию 24.",
                    },
                },
                "required": ["device_types"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_anomalies_tool",
            "description": "Получить недавние аномалии фермы. Используй для вопросов про проблемы, отклонения, перегрев, влажность, pH, EC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Период в часах. По умолчанию 24.",
                    },
                    "event_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Необязательный фильтр по типам событий.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crop_card_tool",
            "description": "Получить АгроТехКарту культуры по названию или slug и проверить пригодность культуры для текущей компактной сити-фермы. Используй, когда пользователь спрашивает про конкретную культуру или продолжает говорить о ней.",
            "parameters": {
                "type": "object",
                "properties": {
                    "crop_name_or_slug": {
                        "type": "string",
                        "description": "Название культуры или slug.",
                    },
                },
                "required": ["crop_name_or_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_history_tool",
            "description": "Получить историю метрики за период. Используй, когда пользователь спрашивает про динамику, тренд или последние часы.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "enum": ["temperature", "humidity", "water_temp", "ph", "ec"],
                        "description": "Метрика: temperature, humidity, water_temp, ph, ec.",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Период в часах. По умолчанию 24.",
                    },
                },
                "required": ["metric_name"],
            },
        },
    },
]


def normalize_tool_hours(value: Any, default: int = 24) -> int:
    try:
        hours = int(value)
    except (TypeError, ValueError):
        hours = default
    return max(1, min(hours, 168))


def event_minutes_ago(value: Any) -> int | None:
    event_time = parse_event_timestamp(value)
    if event_time is None:
        return None
    now = datetime.now(event_time.tzinfo) if event_time.tzinfo else datetime.now()
    return max(0, int((now - event_time).total_seconds() // 60))


def summarize_device_events(events: list[dict[str, Any]], device_type: str) -> dict[str, Any]:
    filtered = [
        event for event in events
        if device_type in str(event.get("device_id") or "").lower()
    ]
    last_on = next((event for event in filtered if event.get("command") == "manual_on"), None)
    return {
        "has_events": bool(filtered),
        "events_count": len(filtered),
        "manual_on_count": sum(1 for event in filtered if event.get("command") == "manual_on"),
        "manual_off_count": sum(1 for event in filtered if event.get("command") == "manual_off"),
        "last_on_at": last_on.get("created_at") if last_on else None,
        "last_on_minutes_ago": event_minutes_ago(last_on.get("created_at")) if last_on else None,
        "events": filtered,
    }


def execute_farm_ai_tool(name: str, arguments: dict) -> dict[str, Any]:
    try:
        args = arguments if isinstance(arguments, dict) else {}
        if name == "get_current_metrics_tool":
            freshness = get_sensor_freshness_status_for_ai()
            metrics_payload = metrics_for_ai_with_freshness(get_current_metrics(), freshness)
            return {
                "ok": True,
                "metrics": metrics_payload["current"],
                "stale_last_known": metrics_payload["stale_last_known"],
                "sensor_freshness": freshness,
                "freshness_warning": metrics_payload["freshness_warning"],
            }

        if name == "get_active_cycle_tool":
            tray_id = str(args.get("tray_id") or "tray_1")
            return {"ok": True, "tray_id": tray_id, "active_cycle": get_active_cycle_ai_context(tray_id)}

        if name == "get_device_events_tool":
            tray_id = str(args.get("tray_id") or "tray_1")
            hours = normalize_tool_hours(args.get("hours"), 24)
            requested_devices = args.get("device_types")
            if not isinstance(requested_devices, list):
                requested_devices = []
            device_types = [
                str(device_type).lower()
                for device_type in requested_devices
                if str(device_type).lower() in KNOWN_DEVICE_TYPES
            ]
            if not device_types:
                return {"ok": False, "error": "device_types must include at least one of: pump, fan, light"}
            events = get_recent_device_events(tray_id=tray_id, hours=hours, limit=200)
            return {
                "ok": True,
                "tray_id": tray_id,
                "hours": hours,
                "devices": {
                    device_type: summarize_device_events(events, device_type)
                    for device_type in device_types
                },
            }

        if name == "get_recent_anomalies_tool":
            hours = normalize_tool_hours(args.get("hours"), 24)
            event_types = args.get("event_types")
            events = get_recent_anomaly_events(hours)
            if isinstance(event_types, list) and event_types:
                allowed = {str(event_type) for event_type in event_types}
                events = [event for event in events if str(event.get("event_type")) in allowed]
            return {"ok": True, "hours": hours, "event_types": event_types, "events": events}

        if name == "get_crop_card_tool":
            crop_name_or_slug = str(args.get("crop_name_or_slug") or "").strip()
            if not crop_name_or_slug:
                return {"ok": False, "error": "crop_name_or_slug is required"}
            suitability = classify_crop_suitability_for_city_farm(crop_name_or_slug)
            status = suitability["status"]
            if status == "db_supported":
                return {
                    "ok": True,
                    "supported": True,
                    "suitability_status": status,
                    "card": suitability.get("card"),
                }
            if status == "compatible_not_in_db":
                return {
                    "ok": True,
                    "supported": False,
                    "suitability_status": status,
                    "requested_crop": crop_name_or_slug,
                    "normalized_crop": suitability.get("normalized_crop"),
                    "policy": "Культура подходит для компактной гидропонной сити-фермы, но её точной АгроТехКарты пока нет в БД. Можно дать только общую справку без точных норм проекта.",
                    "supported_crops": suitability.get("supported_crops", []),
                }
            if status == "advanced_or_unsuitable":
                return {
                    "ok": False,
                    "supported": False,
                    "suitability_status": status,
                    "requested_crop": crop_name_or_slug,
                    "normalized_crop": suitability.get("normalized_crop"),
                    "policy": "Эта культура не является подходящей для текущей маленькой сити-фермы со стаканчиками. Не давай подробную агротехнику как для поддерживаемой культуры. Коротко объясни ограничение и предложи подходящие культуры.",
                    "supported_crops": suitability.get("supported_crops", []),
                }
            return {
                "ok": False,
                "supported": False,
                "suitability_status": "unknown",
                "requested_crop": crop_name_or_slug,
                "normalized_crop": suitability.get("normalized_crop"),
                "policy": "Культура не найдена в БД и не классифицирована как подходящая для текущей компактной сити-фермы. Не давай подробные нормы. Предложи выбрать поддерживаемые культуры.",
                "supported_crops": suitability.get("supported_crops", []),
            }

        if name == "get_metric_history_tool":
            metric_name = str(args.get("metric_name") or "").strip().lower()
            hours = normalize_tool_hours(args.get("hours"), 24)
            if metric_name not in {"temperature", "humidity", "water_temp", "ph", "ec"}:
                return {"ok": False, "error": f"unknown metric_name: {metric_name}"}
            return {"ok": True, "metric_name": metric_name, "hours": hours, "history": get_hourly_history(metric_name, hours)}

        return {"ok": False, "error": f"unknown tool: {name}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def serialize_tool_call(tool_call: Any) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments or "{}",
        },
    }


FARM_TOOL_ANALYSIS_STEPS = {
    "get_current_metrics_tool": "Получаю текущие показатели фермы через tool",
    "get_active_cycle_tool": "Получаю активный цикл выращивания через tool",
    "get_device_events_tool": "Получаю историю device_events через tool",
    "get_recent_anomalies_tool": "Получаю недавние anomaly_events через tool",
    "get_crop_card_tool": "Получаю АгроТехКарту культуры через tool",
    "get_metric_history_tool": "Получаю историю метрики через tool",
}


async def ask_ai(
    system_prompt: str,
    user_prompt: str,
    message_history: list = None,
    analysis_steps: list[str] | None = None,
) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    if message_history:
        messages.extend(message_history)
    messages.append({"role": "user", "content": user_prompt})

    model_name = os.getenv("AI_MODEL", "gpt-5.4-mini")

    try:
        for _ in range(2):
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=FARM_AI_TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )

            message = response.choices[0].message
            tool_calls = message.tool_calls or []
            assistant_message = {
                "role": "assistant",
                "content": message.content or "",
            }
            if tool_calls:
                assistant_message["tool_calls"] = [serialize_tool_call(tool_call) for tool_call in tool_calls]
            messages.append(assistant_message)

            if not tool_calls:
                return sanitize_ai_reply(message.content or "")

            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = parse_tool_arguments(tool_call.function.arguments)
                print(f"[AI_TOOL] {tool_name} args={json.dumps(tool_args, ensure_ascii=False)}")
                add_analysis_step(analysis_steps, FARM_TOOL_ANALYSIS_STEPS.get(tool_name, f"Выполняю tool {tool_name}"))
                result = execute_farm_ai_tool(tool_name, tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        final_response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2,
        )
        return sanitize_ai_reply(final_response.choices[0].message.content or "")
    except Exception as e:
        return f"Ошибка при обращении к ИИ: {str(e)}"


def get_latest_data_snapshot() -> dict[str, Any]:
    latest_snapshot: dict[str, Any] = {
        "Температура": None,
        "Влажность": None,
        "Темп. воды": None,
        "pH": None,
        "EC": None,
    }

    for record in reversed(get_recent_telemetry(10)):
        payload = record.get("parsed_payload")
        if not isinstance(payload, dict):
            continue

        topic = str(record.get("topic", ""))
        if topic.endswith("/climate"):
            if latest_snapshot["Температура"] is None:
                latest_snapshot["Температура"] = payload.get("air_temp")
            if latest_snapshot["Влажность"] is None:
                latest_snapshot["Влажность"] = payload.get("humidity")
        elif topic.endswith("/water"):
            if latest_snapshot["Темп. воды"] is None:
                latest_snapshot["Темп. воды"] = payload.get("water_temp")

        if latest_snapshot["pH"] is None:
            latest_snapshot["pH"] = payload.get("ph", payload.get("pH"))
        if latest_snapshot["EC"] is None:
            latest_snapshot["EC"] = payload.get("ec", payload.get("EC"))

    return latest_snapshot


def is_sensor_type_fresh(
    sensor_freshness: dict[str, dict[str, Any]] | None,
    sensor_type: str,
) -> bool:
    if not isinstance(sensor_freshness, dict):
        return True
    status = sensor_freshness.get(sensor_type)
    if not isinstance(status, dict):
        return True
    return bool(status.get("is_fresh"))


def format_current_or_stale_value(value: Any, unit: str, is_fresh: bool) -> str:
    if is_fresh:
        return format_sensor_value(value, unit)
    if value is None:
        return "нет свежего подтверждённого значения"
    return f"нет свежего подтверждённого значения, последнее устаревшее значение: {format_sensor_value(value, unit)}"


def format_latest_data_for_prompt(sensor_freshness: dict[str, dict[str, Any]] | None = None) -> str:
    latest_data = get_latest_data_snapshot()
    water_is_fresh = is_sensor_type_fresh(sensor_freshness, "water")
    climate_is_fresh = is_sensor_type_fresh(sensor_freshness, "climate")

    air_temp = latest_data.get("Температура")
    humidity = latest_data.get("Влажность")
    water_temp = latest_data.get("Темп. воды")
    ph = latest_data.get("pH")
    ec = latest_data.get("EC")
    air_temp_text = format_current_or_stale_value(air_temp, " C", climate_is_fresh)
    humidity_text = format_current_or_stale_value(humidity, "%", climate_is_fresh)
    water_temp_text = format_current_or_stale_value(water_temp, " C", water_is_fresh)
    ph_text = format_current_or_stale_value(ph, "", water_is_fresh)
    ec_text = format_current_or_stale_value(ec, "", water_is_fresh)

    return (
        f"Текущие показатели: Температура воздуха {air_temp_text}, "
        f"Влажность {humidity_text}, "
        f"Температура воды {water_temp_text}, "
        f"pH {ph_text}, EC {ec_text}"
    )


def format_ai_norm_value(value: Any) -> str:
    if isinstance(value, dict):
        if "min" in value and "max" in value:
            return f"{value['min']}–{value['max']}"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def format_active_cycle_for_prompt(tray_id: str = "tray_1") -> str:
    active_cycle = get_active_cycle_ai_context(tray_id)
    if active_cycle is None:
        return (
            "Активный цикл: не запущен. "
            "Не делай выводы под конкретную культуру, если пользователь её явно не назвал."
        )

    if active_cycle.get("revision_id") is None:
        return (
            "Активный цикл найден, но ревизия АгроТехКарты отсутствует. "
            f"Лоток: {active_cycle.get('tray_id')}. "
            "Не оценивай нормы выращивания без данных ревизии."
        )

    crop_name = active_cycle.get("crop_name_ru") or active_cycle.get("crop_slug") or "без названия"
    lines = [
        "Активный цикл:",
        f"культура: {crop_name}",
        (
            "версия АгроТехКарты: "
            f"{active_cycle.get('version_label') or 'не указана'}, revision_id={active_cycle.get('revision_id')}"
        ),
        f"день цикла: {active_cycle.get('day_number') or 1}",
        f"лоток: {active_cycle.get('tray_id')}",
    ]

    norms = active_cycle.get("norms")
    if isinstance(norms, dict) and norms:
        norm_lines = [
            f"{key}: {format_ai_norm_value(norms[key])}"
            for key in AI_CONTEXT_NORM_KEYS
            if key in norms and norms[key] is not None
        ]
        if norm_lines:
            lines.append("нормы выращивания: " + "; ".join(norm_lines))
        else:
            lines.append("нормы выращивания: в БД нет поддерживаемых норм")
    else:
        lines.append("нормы выращивания: в БД не найдены")

    lines.append("Правило: Используй эти нормы как приоритетные при оценке состояния фермы.")
    return "\n".join(lines)


def build_crop_learning_context_for_ai(crop_slug: str) -> str:
    try:
        history = get_crop_learning_history(crop_slug)
    except Exception:
        return "Прошлый опыт культуры: прошлого опыта пока недостаточно."

    crop = history.get("crop") if isinstance(history, dict) else {}
    versions = history.get("versions") if isinstance(history, dict) else []
    if not isinstance(crop, dict) or not isinstance(versions, list) or not versions:
        return "Прошлый опыт культуры: прошлого опыта пока недостаточно."

    active_revision_id = history.get("active_revision_id")
    active_version = next(
        (version for version in versions if version.get("revision_id") == active_revision_id),
        None,
    )
    if active_version is None:
        active_version = next((version for version in versions if version.get("is_active")), None)

    active_label = active_version.get("version_label") if isinstance(active_version, dict) else None
    crop_name = crop.get("name_ru") or crop.get("slug") or crop_slug
    lines = [
        "Прошлый опыт культуры:",
        f"- культура: {crop_name} ({crop.get('slug') or crop_slug});",
        f"- активная версия АгроТехКарты: {active_label or 'не указана'};",
        "- используй этот блок только для этой культуры; текущие датчики и активная АгроТехКарта важнее прошлого опыта;",
    ]

    recent_versions = versions[-3:]
    for version in recent_versions:
        version_label = version.get("version_label") or "версия без номера"
        effectiveness = version.get("effectiveness") if isinstance(version.get("effectiveness"), dict) else {}
        finished_cycles = int(effectiveness.get("finished_cycles") or 0)
        has_enough_data = bool(effectiveness.get("has_enough_data"))
        created_from = version.get("created_from") if isinstance(version.get("created_from"), dict) else None
        if created_from:
            source_cycle_id = created_from.get("source_cycle_id")
            source_revision_id = created_from.get("source_revision_id")
            source_version = next(
                (
                    item.get("version_label")
                    for item in versions
                    if item.get("revision_id") == source_revision_id
                ),
                None,
            )
            reason = created_from.get("ai_reasoning_short") or version.get("change_reason_short")
            source_part = f" на {source_version}" if source_version else ""
            lines.append(
                f"- {version_label} создана после цикла #{source_cycle_id}{source_part}: "
                f"{reason or 'причина не указана'}"
            )
        else:
            lines.append(f"- {version_label}: завершённых циклов на версии: {finished_cycles}.")

        if not has_enough_data:
            summary = effectiveness.get("summary") or "данных мало для оценки эффективности."
            lines.append(f"- {version_label}: {summary}")

    finished_cycle_notes: list[str] = []
    for version in reversed(versions):
        version_label = version.get("version_label") or "версия без номера"
        cycles = version.get("cycles_on_this_revision")
        if not isinstance(cycles, list):
            continue
        for cycle in reversed(cycles):
            if cycle.get("status") != "finished":
                continue
            findings = cycle.get("main_findings_short")
            if isinstance(findings, list):
                for finding in findings[:3]:
                    if not isinstance(finding, dict):
                        continue
                    problem = str(finding.get("problem") or "").strip()
                    area = str(finding.get("area") or "general").strip()
                    if problem:
                        finished_cycle_notes.append(
                            f"{version_label}, цикл #{cycle.get('cycle_id')}: {area}: {problem}"
                        )
            elif cycle.get("ai_analysis_summary"):
                finished_cycle_notes.append(
                    f"{version_label}, цикл #{cycle.get('cycle_id')}: {cycle.get('ai_analysis_summary')}"
                )
            if len(finished_cycle_notes) >= 5:
                break
        if len(finished_cycle_notes) >= 5:
            break

    if finished_cycle_notes:
        lines.append("- главные проблемы прошлых завершённых циклов:")
        lines.extend(f"  - {note}" for note in finished_cycle_notes[:5])
    else:
        lines.append("- прошлых завершённых циклов с выводами пока недостаточно.")

    latest_created_from = None
    if isinstance(active_version, dict):
        latest_created_from = active_version.get("created_from")
    if not isinstance(latest_created_from, dict):
        latest_created_from = next(
            (
                version.get("created_from")
                for version in reversed(versions)
                if isinstance(version.get("created_from"), dict)
            ),
            None,
        )

    top_changes = latest_created_from.get("top_changes") if isinstance(latest_created_from, dict) else []
    if isinstance(top_changes, list) and top_changes:
        lines.append("- изменения, внесённые в последнюю карту:")
        for change in top_changes[:4]:
            if not isinstance(change, dict):
                continue
            section = change.get("section") or "раздел"
            reason = change.get("reason") or "причина не указана"
            new_value = change.get("new_value")
            if new_value:
                lines.append(f"  - {section}: {new_value} ({reason})")
            else:
                lines.append(f"  - {section}: {reason}")

    try:
        active_card = get_crop_agrotech_card_from_db(crop_slug)
    except Exception:
        active_card = None
    card_sections = active_card.get("sections") if isinstance(active_card, dict) else []
    card_solution_lines: list[str] = []
    if isinstance(card_sections, list):
        for section in card_sections:
            if not isinstance(section, dict):
                continue
            title = str(section.get("section_title") or "")
            content = str(section.get("content") or "")
            if title not in {
                "Рекомендации по уходу",
                "Правила алертов",
                "Как должен отвечать AI-советник",
                "Выбранные диапазоны и обоснование",
            }:
                continue
            for raw_line in content.splitlines():
                line = raw_line.strip().lstrip("-").strip()
                if not line:
                    continue
                lowered = line.lower()
                if not any(keyword in lowered for keyword in ("ph", "ec", "раствор", "измер", "перемеш")):
                    continue
                short_line = line[:220].rstrip()
                if short_line and short_line not in card_solution_lines:
                    card_solution_lines.append(short_line)
                if len(card_solution_lines) >= 4:
                    break
            if len(card_solution_lines) >= 4:
                break
    if card_solution_lines:
        lines.append("- инструкции активной карты по прошлым pH/EC-проблемам:")
        lines.extend(f"  - {line}" for line in card_solution_lines)

    if isinstance(active_version, dict):
        effectiveness = active_version.get("effectiveness") if isinstance(active_version.get("effectiveness"), dict) else {}
        if not effectiveness.get("has_enough_data"):
            lines.append(
                f"- На {active_label or 'активной версии'} пока недостаточно завершённых циклов; "
                "нельзя утверждать, что она эффективнее предыдущих версий."
            )

    lines.append(
        "- Не пересказывай пользователю историю версий и номера внутренних сущностей, "
        "если он прямо не спрашивает."
    )
    return "\n".join(lines)


def sensor_record_age_seconds(recorded_at: Any) -> int | None:
    if not isinstance(recorded_at, datetime):
        return None
    now = datetime.now(recorded_at.tzinfo) if recorded_at.tzinfo else datetime.now()
    return max(0, int((now - recorded_at).total_seconds()))


def latest_sensor_record_status(
    records: list[dict[str, Any]],
    affected_metrics: list[str],
) -> dict[str, Any]:
    latest_record = records[-1] if records else None
    recorded_at = latest_record.get("recorded_at") if isinstance(latest_record, dict) else None
    age_seconds = sensor_record_age_seconds(recorded_at)
    payload = latest_record.get("parsed_payload") if isinstance(latest_record, dict) else None
    return {
        "is_fresh": age_seconds is not None and age_seconds <= SENSOR_STALE_SECONDS,
        "age_seconds": age_seconds,
        "last_recorded_at": recorded_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(recorded_at, datetime) else None,
        "affected_metrics": affected_metrics,
        "last_values": payload if isinstance(payload, dict) else {},
    }


def metrics_for_ai_with_freshness(
    metrics: dict[str, Any],
    freshness: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    current_metrics = dict(metrics) if isinstance(metrics, dict) else {}
    stale_last_known: dict[str, Any] = {}
    warnings: list[str] = []

    water = freshness.get("water", {})
    if isinstance(water, dict) and not water.get("is_fresh"):
        last_values = water.get("last_values") if isinstance(water.get("last_values"), dict) else {}
        for metric_name in ("ph", "ec", "water_temp"):
            stale_last_known[metric_name] = last_values.get(metric_name, current_metrics.get(metric_name))
            current_metrics[metric_name] = None
        warnings.append("water metrics are stale; do not treat ph/ec/water_temp as current")

    climate = freshness.get("climate", {})
    if isinstance(climate, dict) and not climate.get("is_fresh"):
        last_values = climate.get("last_values") if isinstance(climate.get("last_values"), dict) else {}
        for metric_name in ("temperature", "humidity"):
            payload_key = "air_temp" if metric_name == "temperature" else metric_name
            stale_last_known[metric_name] = last_values.get(payload_key, current_metrics.get(metric_name))
            current_metrics[metric_name] = None
        warnings.append("climate metrics are stale; do not treat air_temp/humidity as current")

    return {
        "current": current_metrics,
        "stale_last_known": stale_last_known,
        "freshness_warning": "; ".join(warnings) if warnings else "",
    }


def get_sensor_freshness_status_for_ai() -> dict[str, dict[str, Any]]:
    water_records = get_last_water_records(1)
    climate_records = get_last_climate_records(1)
    return {
        "water": latest_sensor_record_status(
            water_records,
            ["ph", "ec", "water_temp"],
        ),
        "climate": latest_sensor_record_status(
            climate_records,
            ["air_temp", "humidity"],
        ),
    }


def build_stale_sensor_context_for_ai(
    hours: int = 24,
    question_topics: set[str] | None = None,
) -> str:
    freshness = get_sensor_freshness_status_for_ai()
    if question_topics is not None and not question_topics:
        return ""

    stale_events = [
        event
        for event in get_recent_anomaly_events(hours)
        if event.get("event_type") in {"stale_water_data", "stale_climate_data", "stale_sensor_data"}
    ]
    stale_event_types = {str(event.get("event_type")) for event in stale_events}
    lines: list[str] = []

    water = freshness["water"]
    if not water["is_fresh"]:
        if "stale_water_data" in stale_event_types or "stale_sensor_data" in stale_event_types:
            lines.append("- Недавно зафиксировано stale_water_data: данные водных датчиков могли устареть.")
        elif water["last_recorded_at"] is None:
            lines.append("- Нет свежих записей водных датчиков: pH, EC и температура воды неизвестны.")
        else:
            lines.append(
                f"- Последние данные водных датчиков старше {SENSOR_STALE_SECONDS} секунд "
                f"(возраст около {water['age_seconds']} секунд)."
            )
        lines.append("- Для pH, EC и температуры воды сначала попроси перепроверить актуальность показаний.")
        lines.append("- Не давай уверенных рекомендаций по корректировке раствора, пока pH/EC не подтверждены свежим измерением.")

    climate = freshness["climate"]
    if not climate["is_fresh"]:
        if "stale_climate_data" in stale_event_types or "stale_sensor_data" in stale_event_types:
            lines.append("- Недавно зафиксировано stale_climate_data: данные климатических датчиков могли устареть.")
        elif climate["last_recorded_at"] is None:
            lines.append("- Нет свежих записей климатических датчиков: температура воздуха и влажность неизвестны.")
        else:
            lines.append(
                f"- Последние данные климатических датчиков старше {SENSOR_STALE_SECONDS} секунд "
                f"(возраст около {climate['age_seconds']} секунд)."
            )
        lines.append("- Для температуры воздуха и влажности сначала попроси перепроверить актуальность показаний.")

    if not lines:
        return ""

    topic_lines: list[str] = []
    if question_topics is None or "solution" in question_topics:
        if not water["is_fresh"]:
            topic_lines.append(
                "- Вопрос связан с pH/EC/раствором, а water.is_fresh=false: "
                "в ответе сначала скажи, что данные pH/EC могли устареть и нужен свежий замер. "
                "Не начинай с оценки 'pH сейчас в норме'."
            )
    if question_topics is None or "temperature" in question_topics or "watering" in question_topics or "general" in question_topics:
        if not climate["is_fresh"]:
            topic_lines.append(
                "- Вопрос связан с температурой/влажностью, а climate.is_fresh=false: "
                "сначала скажи, что данные климата могли устареть и их нужно подтвердить."
            )

    return "\n".join([
        "Контекст свежести датчиков:",
        *lines,
        *topic_lines,
        "- Если water stale и вопрос про pH/EC, запрещено начинать ответ с оценки текущего pH/EC; первая смысловая фраза должна быть о том, что water-показания устарели или не подтверждены.",
        "- Если climate stale и вопрос про температуру воздуха/влажность, запрещено начинать ответ с оценки текущей температуры/влажности; сначала скажи, что climate-показания нужно подтвердить.",
        "- Если вопрос пользователя касается затронутых метрик, начни ответ с того, что показания нужно подтвердить свежим замером.",
        "- Не пиши, что pH, EC, температура воды, температура воздуха или влажность 'сейчас' в норме/падают/растут, если соответствующий sensor type stale.",
        "- При stale-данных сначала советуй проверить датчик, MQTT/ESP32/симулятор и повторить измерение.",
        "- Если новые данные уже пришли и соответствующий sensor type свежий, не считай старые stale-события актуальной проблемой.",
    ])


def detect_farm_question_topics(message: str) -> set[str]:
    text = str(message or "").lower().replace("ё", "е")
    topic_keywords = {
        "watering": (
            "полив", "поливом", "насос", "насосы", "орошение", "вода для полива",
            "увлажнение", "влажность", "субстрат",
        ),
        "temperature": (
            "температура", "жарко", "холодно", "перегрев", "охлаждение", "воздух",
        ),
        "solution": (
            "ph", "pH", "ec", "раствор", "питательный раствор", "кислотность",
            "щелочь", "щелоч", "кислота", "концентрация", "соли",
        ),
        "light": (
            "свет", "освещение", "лампа", "фитолампа",
        ),
        "general": (
            "все ли нормально", "всё ли нормально", "состояние фермы", "как ферма", "что с фермой",
        ),
    }
    return {
        topic
        for topic, keywords in topic_keywords.items()
        if any(keyword.lower().replace("ё", "е") in text for keyword in keywords)
    }


FARM_FOLLOW_UP_MARKERS = (
    "он", "она", "оно", "они", "его", "ее", "сколько", "сколько раз",
    "когда", "давно", "последний раз", "как часто", "включался",
    "выключался", "срабатывал", "добавлять", "нужно ли", "нормально ли",
    "а сейчас", "а почему", "давай", "проверь",
)


def get_recent_dialog_text(messages, current_message, limit=6) -> str:
    parts: list[str] = []
    if isinstance(messages, list):
        for item in messages[-limit:]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("content") or item.get("text") or "").strip()
            if text:
                parts.append(text)

    current_text = str(current_message or "").strip()
    if current_text:
        parts.append(current_text)

    return " ".join(parts)


def is_farm_follow_up_message(message: str) -> bool:
    text = str(message or "").lower().replace("ё", "е")
    return any(marker in text for marker in FARM_FOLLOW_UP_MARKERS)


def detect_farm_question_topics_from_dialog(current_message: str, messages: list | None = None) -> set[str]:
    current_topics = detect_farm_question_topics(current_message)
    if current_topics:
        return current_topics

    recent_dialog_text = get_recent_dialog_text(messages, current_message)
    recent_topics = detect_farm_question_topics(recent_dialog_text)
    if recent_topics and is_farm_follow_up_message(current_message):
        return recent_topics

    return recent_topics


def format_norm_for_fact(norms: dict[str, Any], metric_name: str) -> str:
    value = norms.get(metric_name) if isinstance(norms, dict) else None
    if isinstance(value, dict) and "min" in value and "max" in value:
        return f"{value['min']}–{value['max']}"
    if value is not None:
        return format_ai_norm_value(value)
    return "нет нормы в активной АгроТехКарте"


def parse_event_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for candidate in (text, text.replace(" ", "T"), text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


RECOMMENDATION_SOURCES = {"chat", "advisor", "predictive", "system"}
RECOMMENDATION_CATEGORIES = {
    "solution",
    "watering",
    "light",
    "climate",
    "ventilation",
    "sensor",
    "general",
}
RECOMMENDATION_METRICS = {"ph", "ec", "humidity", "air_temp", "water_temp"}
RECOMMENDATION_ACTION_KEYWORDS = (
    "проверь",
    "проверить",
    "скоррект",
    "отрегули",
    "перемеш",
    "повтори",
    "повторите",
    "замер",
    "измер",
    "подним",
    "поднять",
    "внос",
    "корректор",
    "долить",
    "добав",
    "замен",
    "сниз",
    "повыс",
    "включ",
    "выключ",
    "очист",
    "насос",
    "помп",
    "свет",
    "ламп",
    "вентиля",
    "датчик",
    "полив",
    "раствор",
    "check",
    "adjust",
    "refill",
    "replace",
    "ventilation",
    "sensor",
    "pump",
)
RECOMMENDATION_SKIP_KEYWORDS = (
    "привет",
    "здравств",
    "все нормально",
    "всё нормально",
    "существенных рисков",
    "продолжайте наблюдение",
    "данных пока нет",
    "данных по",
    "истории пока мало",
    "оценка трендов ограничена",
    "нет данных",
    "по почасовой истории",
    "hello",
)
RECOMMENDATION_DOMAIN_KEYWORDS = (
    "ph",
    "ec",
    "насос",
    "помп",
    "свет",
    "ламп",
    "вентиля",
    "датчик",
    "температур",
    "влаж",
    "полив",
    "раствор",
    "корректор",
    "pump",
    "light",
    "ventilation",
    "sensor",
)
METRIC_EFFECT_THRESHOLDS = {
    "ph": 0.05,
    "ec": 0.03,
    "humidity": 1.0,
    "air_temp": 0.2,
    "water_temp": 0.2,
}


def is_actionable_recommendation_text(text: Any) -> bool:
    normalized = str(text or "").strip().lower()
    if len(normalized) < 8:
        return False
    has_action = any(keyword in normalized for keyword in RECOMMENDATION_ACTION_KEYWORDS)
    has_domain = any(keyword in normalized for keyword in RECOMMENDATION_DOMAIN_KEYWORDS)
    if has_action and has_domain:
        return True

    skip_hit = any(keyword in normalized for keyword in RECOMMENDATION_SKIP_KEYWORDS)
    if skip_hit and not has_action:
        return False

    return has_action and len(normalized) >= 20


def derive_recommendation_metric(text: str, metric_name: Any = None) -> str | None:
    normalized_metric = str(metric_name or "").strip().lower()
    if normalized_metric == "temperature":
        normalized_metric = "air_temp"
    if normalized_metric in RECOMMENDATION_METRICS:
        return normalized_metric

    normalized_text = text.lower()
    if "ph" in normalized_text or "pH" in text:
        return "ph"
    if "ec" in normalized_text:
        return "ec"
    if "влаж" in normalized_text or "humidity" in normalized_text:
        return "humidity"
    if "вод" in normalized_text and "температур" in normalized_text:
        return "water_temp"
    if "воздух" in normalized_text and "температур" in normalized_text:
        return "air_temp"
    if "temperature" in normalized_text:
        return "air_temp"
    return None


def derive_recommendation_category(text: str, category: Any = None) -> str:
    normalized_category = str(category or "").strip().lower()
    if normalized_category in RECOMMENDATION_CATEGORIES:
        return normalized_category

    normalized_text = text.lower()
    if any(marker in normalized_text for marker in ("ph", "ec", "раствор", "питател")):
        return "solution"
    if any(marker in normalized_text for marker in ("полив", "насос", "помп", "долить", "water", "pump")):
        return "watering"
    if any(marker in normalized_text for marker in ("свет", "ламп", "освещ", "light")):
        return "light"
    if any(marker in normalized_text for marker in ("вентиля", "fan", "ventilation")):
        return "ventilation"
    if any(marker in normalized_text for marker in ("температур", "влаж", "climate", "humidity")):
        return "climate"
    if any(marker in normalized_text for marker in ("датчик", "sensor")):
        return "sensor"
    return "general"


def normalize_recommendation_candidate(item: Any, source: str) -> dict[str, Any] | None:
    if isinstance(item, str):
        text = item.strip()
        raw: dict[str, Any] = {}
    elif isinstance(item, dict):
        raw = item
        text = str(
            raw.get("recommendation_text")
            or raw.get("text")
            or raw.get("recommendation")
            or ""
        ).strip()
    else:
        return None

    if not is_actionable_recommendation_text(text):
        print(f"[RECOMMENDATIONS] Dropped by actionable filter: {text[:160]}")
        return None

    normalized_source = source if source in RECOMMENDATION_SOURCES else "system"
    return {
        "source": normalized_source,
        "category": derive_recommendation_category(text, raw.get("category")),
        "metric_name": derive_recommendation_metric(text, raw.get("metric_name")),
        "recommendation_text": text,
        "reason": str(raw.get("reason") or "").strip() or None,
    }


def build_fallback_recommendation_from_reply(reply: str, source: str = "chat") -> dict[str, Any] | None:
    text = str(reply or "").strip()
    if not is_actionable_recommendation_text(text):
        print(f"[RECOMMENDATIONS] Fallback skipped by actionable filter: {text[:160]}")
        return None

    return {
        "source": source,
        "category": derive_recommendation_category(text),
        "metric_name": derive_recommendation_metric(text),
        "recommendation_text": text,
        "reason": "Fallback extraction: reply contains farm domain terms and actionable instructions.",
    }


def parse_recommendation_extraction_json(raw_text: str) -> list[Any]:
    cleaned = strip_markdown_backticks(raw_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}|\[.*\]", cleaned, flags=re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        recommendations = parsed.get("recommendations")
        return recommendations if isinstance(recommendations, list) else []
    return []


CYCLE_AI_ANALYSIS_PROMPT_VERSION = "cycle_ai_analysis_v1"
CYCLE_AI_ANALYSIS_AREAS = {"solution", "light", "watering", "climate", "sensor", "general"}
CYCLE_AI_ANALYSIS_CONFIDENCE = {"low", "medium", "high"}
CYCLE_AI_ANALYSIS_USEFULNESS = {
    "useful",
    "partially_useful",
    "not_useful",
    "harmful",
    "inconclusive",
}
CYCLE_AI_ANALYSIS_METRICS = {"ph", "ec", "humidity", "air_temp", "water_temp", None}


def parse_cycle_ai_analysis_json(raw_text: str) -> dict[str, Any]:
    cleaned = strip_markdown_backticks(raw_text)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("AI analysis response must be a JSON object")
    return parsed


def normalize_cycle_ai_analysis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    main_findings: list[dict[str, Any]] = []
    for item in payload.get("main_findings") or []:
        if not isinstance(item, dict):
            continue
        area = str(item.get("area") or "general").strip().lower()
        confidence = str(item.get("confidence") or "low").strip().lower()
        evidence = item.get("evidence")
        main_findings.append(
            {
                "area": area if area in CYCLE_AI_ANALYSIS_AREAS else "general",
                "problem": str(item.get("problem") or "данных недостаточно").strip(),
                "evidence": evidence if isinstance(evidence, list) else [],
                "confidence": confidence if confidence in CYCLE_AI_ANALYSIS_CONFIDENCE else "low",
            }
        )

    recommendation_review: list[dict[str, Any]] = []
    for item in payload.get("recommendation_review") or []:
        if not isinstance(item, dict):
            continue
        raw_metric = item.get("metric_name")
        metric_name = str(raw_metric).strip().lower() if raw_metric is not None else None
        usefulness = str(item.get("usefulness") or "inconclusive").strip().lower()
        operator_action_confirmed = item.get("operator_action_confirmed")
        if operator_action_confirmed not in {True, False, None}:
            operator_action_confirmed = None
        evidence_level = str(item.get("evidence_level") or "observed_only").strip().lower()
        if evidence_level not in {"observed_only", "operator_reported_followed", "insufficient"}:
            evidence_level = "observed_only"
        recommendation_review.append(
            {
                "metric_name": metric_name if metric_name in CYCLE_AI_ANALYSIS_METRICS else None,
                "recommendation_summary": str(item.get("recommendation_summary") or "").strip(),
                "observed_effect": str(item.get("observed_effect") or "данных недостаточно").strip(),
                "usefulness": usefulness if usefulness in CYCLE_AI_ANALYSIS_USEFULNESS else "inconclusive",
                "comment": str(item.get("comment") or "").strip(),
                "causality": "not_proven",
                "operator_action_confirmed": operator_action_confirmed,
                "evidence_level": evidence_level,
                "interpretation_note": RECOMMENDATION_EFFECT_INTERPRETATION_NOTE,
            }
        )

    potential_improvements: list[dict[str, Any]] = []
    for item in payload.get("potential_improvements") or []:
        if not isinstance(item, dict):
            continue
        priority = str(item.get("priority") or "low").strip().lower()
        potential_improvements.append(
            {
                "target_section": str(item.get("target_section") or "general").strip(),
                "suggested_change": str(item.get("suggested_change") or "").strip(),
                "reason": str(item.get("reason") or "данных недостаточно").strip(),
                "priority": priority if priority in CYCLE_AI_ANALYSIS_CONFIDENCE else "low",
            }
        )

    confidence = str(payload.get("confidence") or "low").strip().lower()
    return {
        "summary": str(payload.get("summary") or "данных недостаточно").strip(),
        "main_findings": main_findings,
        "recommendation_review": recommendation_review,
        "potential_improvements": potential_improvements,
        "should_propose_new_revision": bool(payload.get("should_propose_new_revision", False)),
        "revision_reason": str(payload.get("revision_reason") or "").strip() or None,
        "confidence": confidence if confidence in CYCLE_AI_ANALYSIS_CONFIDENCE else "low",
    }


def build_cycle_ai_analysis_prompt(report_payload: dict[str, Any]) -> str:
    return (
        "Ты Нейрогном. Проанализируй завершённый цикл выращивания только по JSON-досье report_payload ниже.\n"
        "Запрещено использовать внешние данные, сырую БД, догадки и текущие показания фермы.\n"
        "Это НЕ создание новой АгроТехКарты: не пиши готовую карту, не меняй ревизии, не создавай proposal.\n"
        "Нужно только определить проблемы, полезность сохранённых рекомендаций и потенциальные улучшения.\n"
        "Если данных недостаточно, прямо пиши 'данных недостаточно'.\n"
        "Не утверждай жёсткую причинно-следственную связь. Пиши 'после рекомендации наблюдалось...', а не 'рекомендация вызвала...'.\n"
        "Для recommendation_review: не утверждай, что рекомендация вызвала изменение метрики. "
        "Если есть совпадение по времени, называй это временной связью, а не доказанной причиной. "
        "Если нет подтверждения действий оператора, пиши 'нельзя подтвердить, что совет был выполнен'. "
        "Даже если usefulness='useful' или 'partially_useful', не формулируй 'точно сработала'. "
        "Если в recommendation_effects указано causality='not_proven' или causality_not_proven=true, сохрани эту осторожность. "
        "Не делай выводы только по одному замеру; при недостатке свежих данных ставь usefulness='inconclusive'.\n"
        "Верни валидный JSON без markdown и без текста вокруг.\n\n"
        "Строгая схема ответа:\n"
        "{\n"
        '  "summary": "...",\n'
        '  "main_findings": [{"area": "solution/light/watering/climate/sensor/general", "problem": "...", "evidence": ["..."], "confidence": "low/medium/high"}],\n'
        '  "recommendation_review": [{"metric_name": "ph/ec/humidity/air_temp/water_temp/null", "recommendation_summary": "...", "observed_effect": "После рекомендации наблюдалось..., но причинность не доказана", "usefulness": "useful/partially_useful/not_useful/harmful/inconclusive", "comment": "Нельзя подтвердить, что совет был выполнен, если нет данных оператора", "causality": "not_proven", "operator_action_confirmed": true/false/null, "evidence_level": "observed_only/operator_reported_followed/insufficient"}],\n'
        '  "potential_improvements": [{"target_section": "...", "suggested_change": "...", "reason": "...", "priority": "low/medium/high"}],\n'
        '  "should_propose_new_revision": false,\n'
        '  "revision_reason": "...",\n'
        '  "confidence": "low/medium/high"\n'
        "}\n\n"
        "report_payload:\n"
        f"{json.dumps(report_payload, ensure_ascii=False, default=str)}"
    )


async def run_cycle_ai_analysis(cycle_id: int) -> dict[str, Any]:
    cycle = await asyncio.to_thread(get_cycle_with_result, cycle_id)
    if cycle.get("status") != "finished" or not cycle.get("finished_at"):
        raise GrowingCycleNotFinishedError(
            f"Growing cycle '{cycle_id}' is not finished; AI analysis can be run only for completed cycles"
        )

    report = await asyncio.to_thread(get_cycle_analysis_report, cycle_id)
    if report is None:
        built_report = await asyncio.to_thread(build_cycle_analysis_report, cycle_id)
        report = await asyncio.to_thread(
            save_cycle_analysis_report,
            cycle_id,
            built_report["report_payload"],
            built_report["summary_text"],
        )
    if report is None:
        raise RuntimeError(f"Analysis report for cycle '{cycle_id}' could not be built")

    report_payload = report.get("report_payload") or {}
    report_id = int(report["id"])
    model_name = os.getenv("AI_MODEL", "gpt-5.4-mini")
    prompt = build_cycle_ai_analysis_prompt(report_payload)

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Return valid JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        raw_text = response.choices[0].message.content or ""
        parsed = parse_cycle_ai_analysis_json(raw_text)
        normalized = normalize_cycle_ai_analysis_payload(parsed)
        return await asyncio.to_thread(
            save_cycle_ai_analysis,
            cycle_id=cycle_id,
            analysis_report_id=report_id,
            summary=normalized["summary"],
            main_findings=normalized["main_findings"],
            recommendation_review=normalized["recommendation_review"],
            potential_improvements=normalized["potential_improvements"],
            should_propose_new_revision=normalized["should_propose_new_revision"],
            revision_reason=normalized["revision_reason"],
            confidence=normalized["confidence"],
            status="completed",
            model_name=model_name,
            prompt_version=CYCLE_AI_ANALYSIS_PROMPT_VERSION,
            raw_response=parsed,
        )
    except json.JSONDecodeError as exc:
        failed = await asyncio.to_thread(
            save_cycle_ai_analysis,
            cycle_id=cycle_id,
            analysis_report_id=report_id,
            summary="AI analysis failed: model returned invalid JSON.",
            status="failed",
            model_name=model_name,
            prompt_version=CYCLE_AI_ANALYSIS_PROMPT_VERSION,
            raw_response={"error": str(exc), "raw_response": raw_text if "raw_text" in locals() else ""},
        )
        raise HTTPException(status_code=502, detail={"error": "AI model returned invalid JSON", "analysis": failed}) from exc
    except Exception as exc:
        failed = await asyncio.to_thread(
            save_cycle_ai_analysis,
            cycle_id=cycle_id,
            analysis_report_id=report_id,
            summary=f"AI analysis failed: {exc}",
            status="failed",
            model_name=model_name,
            prompt_version=CYCLE_AI_ANALYSIS_PROMPT_VERSION,
            raw_response={"error": str(exc)},
        )
        raise HTTPException(status_code=502, detail={"error": str(exc), "analysis": failed}) from exc


AGROTECH_PROPOSAL_PROMPT_VERSION = "agrotech_revision_proposal_v1"
AGROTECH_PROPOSAL_PRIORITIES = {"low", "medium", "high"}


def parse_agrotech_revision_proposal_json(raw_text: str) -> dict[str, Any]:
    cleaned = strip_markdown_backticks(raw_text)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Agrotech proposal response must be a JSON object")
    return parsed


def normalize_proposal_changes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    changes: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        priority = str(item.get("priority") or "low").strip().lower()
        changes.append(
            {
                "section": str(item.get("section") or "general").strip(),
                "change_type": str(item.get("change_type") or "clarify_instruction").strip(),
                "old_value": str(item.get("old_value") or "").strip(),
                "new_value": str(item.get("new_value") or "").strip(),
                "reason": str(item.get("reason") or "данных недостаточно").strip(),
                "priority": priority if priority in AGROTECH_PROPOSAL_PRIORITIES else "low",
            }
        )
    return changes


def normalize_proposed_norms(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def norm_bound_delta_too_large(metric_name: str, old_value: Any, new_value: Any) -> bool:
    if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)):
        return False
    delta = abs(float(new_value) - float(old_value))
    if metric_name == "ph":
        return delta > 0.3
    if metric_name == "ec":
        return delta > 0.4
    if metric_name in {"air_temp", "water_temp"}:
        return delta > 3.0
    if metric_name == "humidity":
        return delta > 15.0
    if old_value != 0:
        return delta / abs(float(old_value)) > 0.25
    return delta > 1.0


def find_agrotech_norm_safety_notes(
    source_norms: dict[str, Any],
    proposed_norms: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    for metric_name, proposed_value in proposed_norms.items():
        source_value = source_norms.get(metric_name)
        if not isinstance(source_value, dict) or not isinstance(proposed_value, dict):
            continue
        for bound in ("min", "max", "target"):
            if bound not in proposed_value or bound not in source_value:
                continue
            if norm_bound_delta_too_large(metric_name, source_value.get(bound), proposed_value.get(bound)):
                notes.append(
                    f"norm_change: {metric_name}.{bound} changes from {source_value.get(bound)} to {proposed_value.get(bound)}; auto-apply disabled."
                )
    return notes


def normalize_agrotech_proposal_payload(
    payload: dict[str, Any],
    *,
    source_content: str,
    source_norms: dict[str, Any],
) -> dict[str, Any]:
    proposed_content = str(payload.get("proposed_content") or "").strip()
    proposed_norms = normalize_proposed_norms(payload.get("proposed_norms"))
    proposed_changes = normalize_proposal_changes(payload.get("proposed_changes"))
    safety_notes = [
        str(item).strip()
        for item in (payload.get("safety_notes") if isinstance(payload.get("safety_notes"), list) else [])
        if str(item).strip()
    ]

    auto_apply_eligible = bool(payload.get("auto_apply_eligible", False))
    if not proposed_content:
        proposed_content = source_content
        safety_notes.append("empty_content: model returned empty proposed_content; source content preserved.")
        auto_apply_eligible = False
    if not proposed_changes:
        safety_notes.append("no_changes: model returned no structured proposed_changes.")
        auto_apply_eligible = False

    norm_notes = find_agrotech_norm_safety_notes(source_norms, proposed_norms)
    if norm_notes:
        safety_notes.extend(norm_notes)
        auto_apply_eligible = False

    has_medium_or_high = any(change.get("priority") in {"medium", "high"} for change in proposed_changes)
    if not has_medium_or_high:
        safety_notes.append("low_priority_only: no medium/high priority changes; auto-apply disabled.")
        auto_apply_eligible = False

    return {
        "proposed_content": proposed_content,
        "proposed_norms": proposed_norms,
        "proposed_changes": proposed_changes,
        "ai_reasoning": str(payload.get("ai_reasoning") or "").strip() or None,
        "auto_apply_eligible": auto_apply_eligible,
        "safety_notes": safety_notes,
    }


def build_agrotech_revision_proposal_prompt(
    *,
    source_revision: dict[str, Any],
    analysis: dict[str, Any],
    report: dict[str, Any],
) -> str:
    source_payload = {
        "cycle_id": source_revision["cycle_id"],
        "crop_slug": source_revision["crop_slug"],
        "crop_name_ru": source_revision["crop_name_ru"],
        "source_revision_id": source_revision["source_revision_id"],
        "source_version": source_revision["source_version_label"],
        "source_content": source_revision["content"],
        "source_norms": source_revision.get("norms") or {},
    }
    analysis_payload = {
        "summary": analysis.get("summary"),
        "main_findings": analysis.get("main_findings"),
        "recommendation_review": analysis.get("recommendation_review"),
        "potential_improvements": analysis.get("potential_improvements"),
        "should_propose_new_revision": analysis.get("should_propose_new_revision"),
        "revision_reason": analysis.get("revision_reason"),
        "confidence": analysis.get("confidence"),
    }
    return (
        "Ты Нейрогном. Подготовь черновик улучшения АгроТехКарты по завершённому циклу.\n"
        "Это только proposal: НЕ создавай новую ревизию в БД, НЕ меняй active revision, НЕ пиши оператору кнопки принятия.\n"
        "Используй только source_revision, cycle_analysis_report.report_payload и cycle_ai_analysis ниже.\n"
        "Не придумывай факты, которых нет в отчёте или AI-анализе.\n"
        "Если используешь recommendation_review или recommendation_effects, не пиши, что совет вызвал улучшение. "
        "Формулируй осторожно: 'после рекомендации наблюдалось...', 'эффект нельзя подтвердить', 'причинность не доказана'.\n"
        "Не переписывай карту радикально. Улучшай в первую очередь инструкции, порядок действий и уточнения.\n"
        "Числовые нормы pH/EC/температуры/влажности меняй только при очень сильном обосновании в анализе.\n"
        "Если данных недостаточно, proposed_content должен быть близок к исходному, auto_apply_eligible=false.\n"
        "Верни только валидный JSON без markdown.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "proposed_content": "...полный текст улучшенной АгроТехКарты...",\n'
        '  "proposed_norms": {},\n'
        '  "proposed_changes": [{"section": "solution", "change_type": "clarify_instruction", "old_value": "...", "new_value": "...", "reason": "...", "priority": "low/medium/high"}],\n'
        '  "ai_reasoning": "...",\n'
        '  "auto_apply_eligible": false,\n'
        '  "safety_notes": ["..."]\n'
        "}\n\n"
        f"source_revision:\n{json.dumps(source_payload, ensure_ascii=False, default=str)}\n\n"
        f"cycle_ai_analysis:\n{json.dumps(analysis_payload, ensure_ascii=False, default=str)}\n\n"
        f"cycle_analysis_report_payload:\n{json.dumps(report.get('report_payload') or {}, ensure_ascii=False, default=str)}"
    )


async def run_agrotech_revision_proposal(cycle_id: int, force: bool = False) -> dict[str, Any]:
    analysis = await asyncio.to_thread(get_cycle_ai_analysis, cycle_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail={"error": f"AI analysis for cycle '{cycle_id}' not found"})

    report = await asyncio.to_thread(get_cycle_analysis_report, cycle_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"error": f"Analysis report for cycle '{cycle_id}' not found"})

    source_revision = await asyncio.to_thread(get_cycle_source_revision_context, cycle_id)
    if source_revision is None:
        raise HTTPException(status_code=404, detail={"error": f"Source revision for cycle '{cycle_id}' not found"})

    proposed_major = int(source_revision["version_major"])
    proposed_minor = int(source_revision["version_minor"]) + 1

    if not force and not bool(analysis.get("should_propose_new_revision")):
        return await asyncio.to_thread(
            save_agrotech_revision_proposal,
            cycle_id=cycle_id,
            analysis_id=analysis["id"],
            card_id=source_revision["card_id"],
            crop_id=source_revision["crop_id"],
            source_revision_id=source_revision["source_revision_id"],
            proposed_version_major=proposed_major,
            proposed_version_minor=proposed_minor,
            proposed_content=None,
            proposed_norms={},
            proposed_changes=[],
            ai_reasoning=analysis.get("revision_reason") or "AI analysis did not recommend preparing a new revision proposal.",
            status="auto_deferred",
            auto_apply_eligible=False,
            safety_notes=["deferred: should_propose_new_revision=false and force=false."],
            raw_response={"source": "backend_defer", "analysis": analysis},
        )

    model_name = os.getenv("AI_MODEL", "gpt-5.4-mini")
    prompt = build_agrotech_revision_proposal_prompt(
        source_revision=source_revision,
        analysis=analysis,
        report=report,
    )
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Return valid JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        raw_text = response.choices[0].message.content or ""
        parsed = parse_agrotech_revision_proposal_json(raw_text)
        normalized = normalize_agrotech_proposal_payload(
            parsed,
            source_content=str(source_revision.get("content") or ""),
            source_norms=source_revision.get("norms") or {},
        )
        if not normalized["proposed_content"].strip():
            raise ValueError("proposed_content is empty")

        return await asyncio.to_thread(
            save_agrotech_revision_proposal,
            cycle_id=cycle_id,
            analysis_id=analysis["id"],
            card_id=source_revision["card_id"],
            crop_id=source_revision["crop_id"],
            source_revision_id=source_revision["source_revision_id"],
            proposed_version_major=proposed_major,
            proposed_version_minor=proposed_minor,
            proposed_content=normalized["proposed_content"],
            proposed_norms=normalized["proposed_norms"],
            proposed_changes=normalized["proposed_changes"],
            ai_reasoning=normalized["ai_reasoning"],
            status="generated",
            auto_apply_eligible=normalized["auto_apply_eligible"],
            safety_notes=normalized["safety_notes"],
            raw_response={
                "model_name": model_name,
                "prompt_version": AGROTECH_PROPOSAL_PROMPT_VERSION,
                "response": parsed,
            },
        )
    except json.JSONDecodeError as exc:
        failed = await asyncio.to_thread(
            save_agrotech_revision_proposal,
            cycle_id=cycle_id,
            analysis_id=analysis["id"],
            card_id=source_revision["card_id"],
            crop_id=source_revision["crop_id"],
            source_revision_id=source_revision["source_revision_id"],
            proposed_version_major=proposed_major,
            proposed_version_minor=proposed_minor,
            status="failed",
            auto_apply_eligible=False,
            safety_notes=["failed: model returned invalid JSON."],
            raw_response={"error": str(exc), "raw_response": raw_text if "raw_text" in locals() else ""},
        )
        raise HTTPException(status_code=502, detail={"error": "AI model returned invalid JSON", "proposal": failed}) from exc
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        failed = await asyncio.to_thread(
            save_agrotech_revision_proposal,
            cycle_id=cycle_id,
            analysis_id=analysis["id"],
            card_id=source_revision["card_id"],
            crop_id=source_revision["crop_id"],
            source_revision_id=source_revision["source_revision_id"],
            proposed_version_major=proposed_major,
            proposed_version_minor=proposed_minor,
            status="failed",
            auto_apply_eligible=False,
            safety_notes=[f"failed: {exc}"],
            raw_response={"error": str(exc)},
        )
        raise HTTPException(status_code=502, detail={"error": str(exc), "proposal": failed}) from exc


def learning_step(status: str, item: dict[str, Any] | None = None, error: str | None = None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "id": item.get("id") if isinstance(item, dict) else None,
        "error": error,
    }
    payload.update(extra)
    return payload


def auto_apply_step(status: str, result: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    created_revision = result.get("created_revision") if isinstance(result, dict) else None
    existing_revision = result.get("existing_revision") if isinstance(result, dict) else None
    proposal = result.get("proposal") if isinstance(result, dict) else None
    revision = created_revision if isinstance(created_revision, dict) else existing_revision
    return {
        "status": status,
        "revision_id": revision.get("id") if isinstance(revision, dict) else (
            proposal.get("applied_revision_id") if isinstance(proposal, dict) else None
        ),
        "proposal_id": proposal.get("id") if isinstance(proposal, dict) else None,
        "reason": result.get("reason") if isinstance(result, dict) else None,
        "error": error,
    }


def finalize_learning_pipeline_status(steps: dict[str, dict[str, Any]]) -> str:
    if steps["analysis_report"]["status"] == "failed":
        return "failed"
    if steps["ai_analysis"]["status"] == "failed":
        return "partial"
    if steps["revision_proposal"]["status"] == "failed":
        return "partial"
    if steps["auto_apply"]["status"] in {"failed", "deferred"}:
        return "partial"
    return "completed"


async def run_cycle_learning_pipeline(
    cycle_id: int,
    auto_apply: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    steps: dict[str, dict[str, Any]] = {
        "analysis_report": learning_step("pending"),
        "ai_analysis": learning_step("pending"),
        "revision_proposal": learning_step("pending"),
        "auto_apply": auto_apply_step("pending"),
    }

    try:
        cycle = await asyncio.to_thread(get_cycle_with_result, cycle_id)
        if cycle.get("status") != "finished" or not cycle.get("finished_at"):
            reason = f"Growing cycle '{cycle_id}' is not finished; learning pipeline skipped."
            print(f"[LEARNING PIPELINE] cycle {cycle_id}: failed - {reason}")
            for step_name in steps:
                steps[step_name]["status"] = "skipped"
                steps[step_name]["error"] = reason
            return {"cycle_id": cycle_id, "status": "failed", "steps": steps}
    except Exception as exc:
        reason = str(exc)
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: failed - {reason}")
        for step_name in steps:
            steps[step_name]["status"] = "skipped"
            steps[step_name]["error"] = reason
        return {"cycle_id": cycle_id, "status": "failed", "steps": steps}

    try:
        report = await asyncio.to_thread(get_cycle_analysis_report, cycle_id)
        if report is None:
            built_report = await asyncio.to_thread(build_cycle_analysis_report, cycle_id)
            report = await asyncio.to_thread(
                save_cycle_analysis_report,
                cycle_id,
                built_report["report_payload"],
                built_report["summary_text"],
            )
            steps["analysis_report"] = learning_step("completed", report)
        else:
            steps["analysis_report"] = learning_step("existing", report)
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: analysis_report completed")
    except Exception as exc:
        steps["analysis_report"] = learning_step("failed", error=str(exc))
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: analysis_report failed - {exc}")
        return {"cycle_id": cycle_id, "status": "failed", "steps": steps}

    try:
        analysis = await asyncio.to_thread(get_cycle_ai_analysis, cycle_id)
        if analysis is not None and analysis.get("status") == "completed":
            steps["ai_analysis"] = learning_step("existing", analysis)
        else:
            analysis = await run_cycle_ai_analysis(cycle_id)
            steps["ai_analysis"] = learning_step("completed", analysis)
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: ai_analysis completed")
    except Exception as exc:
        steps["ai_analysis"] = learning_step("failed", error=str(exc))
        steps["revision_proposal"] = learning_step("skipped", error="ai_analysis failed")
        steps["auto_apply"] = auto_apply_step("skipped", error="ai_analysis failed")
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: ai_analysis failed - {exc}")
        return {"cycle_id": cycle_id, "status": "partial", "steps": steps}

    try:
        proposal = await asyncio.to_thread(get_cycle_agrotech_revision_proposal, cycle_id)
        if proposal is not None:
            steps["revision_proposal"] = learning_step("existing", proposal)
        else:
            proposal = await run_agrotech_revision_proposal(cycle_id, force=force)
            steps["revision_proposal"] = learning_step("completed", proposal)
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: revision_proposal completed")
    except Exception as exc:
        steps["revision_proposal"] = learning_step("failed", error=str(exc))
        steps["auto_apply"] = auto_apply_step("skipped", error="revision_proposal failed")
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: revision_proposal failed - {exc}")
        return {"cycle_id": cycle_id, "status": "partial", "steps": steps}

    if not auto_apply:
        steps["auto_apply"] = auto_apply_step("skipped", error=None)
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply skipped")
        return {"cycle_id": cycle_id, "status": finalize_learning_pipeline_status(steps), "steps": steps}

    try:
        apply_result = await asyncio.to_thread(
            apply_cycle_agrotech_revision_proposal,
            cycle_id,
            force,
        )
        apply_status = str(apply_result.get("status") or "")
        if apply_status in {"auto_applied", "already_applied"}:
            steps["auto_apply"] = auto_apply_step("applied", apply_result)
            print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply applied")
        elif apply_status == "auto_deferred":
            steps["auto_apply"] = auto_apply_step("deferred", apply_result)
            print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply deferred")
        else:
            steps["auto_apply"] = auto_apply_step("failed", apply_result, error=apply_status or "unknown apply status")
            print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply failed")
    except AgrotechRevisionProposalApplyError as exc:
        steps["auto_apply"] = auto_apply_step("deferred", error=str(exc))
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply deferred - {exc}")
    except AgrotechRevisionProposalNotFoundError as exc:
        steps["auto_apply"] = auto_apply_step("failed", error=str(exc))
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply failed - {exc}")
    except Exception as exc:
        steps["auto_apply"] = auto_apply_step("failed", error=str(exc))
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: auto_apply failed - {exc}")

    return {
        "cycle_id": cycle_id,
        "status": finalize_learning_pipeline_status(steps),
        "steps": steps,
    }


async def run_cycle_learning_pipeline_background(cycle_id: int) -> None:
    try:
        await run_cycle_learning_pipeline(cycle_id, auto_apply=True, force=False)
    except Exception as exc:
        print(f"[LEARNING PIPELINE] cycle {cycle_id}: background failed - {exc}")


async def extract_recommendations_from_reply(
    reply: str,
    user_message: str,
    context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not reply or not is_actionable_recommendation_text(reply):
        print(f"[RECOMMENDATIONS] Reply skipped before extraction: {str(reply or '')[:160]}")
        return []

    extraction_prompt = (
        "Extract only actionable farm recommendations from the assistant reply. "
        "Return strict JSON only: {\"recommendations\": [...]}. "
        "Each item must have category, metric_name, recommendation_text, reason. "
        "Allowed category values: solution, watering, light, climate, ventilation, sensor, general. "
        "Allowed metric_name values: ph, ec, humidity, air_temp, water_temp, null. "
        "Save only concrete actions such as adjust pH/EC, check pump, add water, check light, "
        "ventilation, sensor, temperature. Do not include greetings, normal-status messages, "
        "or generic observation-only statements. If there are no actionable recommendations, "
        "return {\"recommendations\": []}.\n\n"
        f"User message: {user_message}\n\n"
        f"Active cycle context: {json.dumps(context or {}, ensure_ascii=False, default=str)}\n\n"
        f"Assistant reply: {reply}"
    )

    try:
        response = await client.chat.completions.create(
            model=os.getenv("AI_MODEL", "gpt-5.4-mini"),
            messages=[
                {"role": "system", "content": "You return strict JSON only."},
                {"role": "user", "content": extraction_prompt},
            ],
            temperature=0,
        )
    except Exception as exc:
        print(f"[RECOMMENDATIONS] Extraction failed: {exc}")
        fallback = build_fallback_recommendation_from_reply(reply, "chat")
        recommendations = [fallback] if fallback else []
        print(f"[RECOMMENDATIONS] Extractor found 0 recommendations; fallback={len(recommendations)}")
        return recommendations

    raw_content = response.choices[0].message.content or ""
    items = parse_recommendation_extraction_json(raw_content)
    recommendations: list[dict[str, Any]] = []
    for item in items:
        normalized = normalize_recommendation_candidate(item, "chat")
        if normalized:
            recommendations.append(normalized)
    print(f"[RECOMMENDATIONS] Extractor found {len(recommendations)} recommendations")
    if not recommendations:
        fallback = build_fallback_recommendation_from_reply(reply, "chat")
        if fallback:
            recommendations.append(fallback)
            print("[RECOMMENDATIONS] Fallback recommendation created")
    return recommendations


def current_sensor_snapshot_for_recommendation() -> dict[str, Any]:
    records = get_recent_telemetry(30)
    snapshot = latest_metric_snapshot(records)
    raw_metrics = {
        "tray_id": snapshot.get("tray_id"),
        "air_temp": snapshot.get("air_temp"),
        "humidity": snapshot.get("humidity"),
        "water_temp": snapshot.get("water_temp"),
        "ph": snapshot.get("ph"),
        "ec": snapshot.get("ec"),
    }
    freshness = get_sensor_freshness_status_for_ai()
    metrics_payload = metrics_for_ai_with_freshness(
        {
            "temperature": raw_metrics["air_temp"],
            "humidity": raw_metrics["humidity"],
            "water_temp": raw_metrics["water_temp"],
            "ph": raw_metrics["ph"],
            "ec": raw_metrics["ec"],
        },
        freshness,
    )
    current_metrics = metrics_payload["current"]
    return {
        "tray_id": raw_metrics["tray_id"],
        "air_temp": current_metrics.get("temperature"),
        "humidity": current_metrics.get("humidity"),
        "water_temp": current_metrics.get("water_temp"),
        "ph": current_metrics.get("ph"),
        "ec": current_metrics.get("ec"),
        "sensor_freshness": freshness,
        "stale_last_known": metrics_payload["stale_last_known"],
        "freshness_warning": metrics_payload["freshness_warning"],
    }


async def persist_ai_recommendations(
    recommendations: list[dict[str, Any]],
    *,
    active_cycle: dict[str, Any] | None,
    source: str,
) -> list[dict[str, Any]]:
    if not recommendations or not active_cycle:
        print(
            "[RECOMMENDATIONS] Save skipped: "
            f"recommendations={len(recommendations) if recommendations else 0}, "
            f"active_cycle={bool(active_cycle)}"
        )
        return []

    cycle_id = active_cycle.get("cycle_id")
    tray_id = str(active_cycle.get("tray_id") or WATCHDOG_DEFAULT_TRAY_ID)
    if not isinstance(cycle_id, int):
        print(f"[RECOMMENDATIONS] Save skipped: invalid cycle_id={cycle_id}")
        return []

    try:
        sensor_snapshot = await asyncio.to_thread(current_sensor_snapshot_for_recommendation)
        norm_snapshot = active_cycle.get("norms") if isinstance(active_cycle.get("norms"), dict) else {}
        saved: list[dict[str, Any]] = []
        for recommendation in recommendations:
            normalized = normalize_recommendation_candidate(recommendation, source)
            if not normalized:
                continue
            saved_item = await asyncio.to_thread(
                save_ai_recommendation,
                cycle_id=cycle_id,
                tray_id=tray_id,
                source=source,
                category=normalized["category"],
                metric_name=normalized["metric_name"],
                recommendation_text=normalized["recommendation_text"],
                reason=normalized.get("reason"),
                sensor_snapshot=sensor_snapshot,
                norm_snapshot=norm_snapshot,
            )
            if saved_item:
                saved.append(saved_item)
        print(f"[RECOMMENDATIONS] Saved {len(saved)} of {len(recommendations)} recommendations")
        return saved
    except Exception as exc:
        print(f"[RECOMMENDATIONS] Save failed: {exc}")
        return []


def norm_range_for_metric(norm_snapshot: dict[str, Any], metric_name: str) -> tuple[float, float] | None:
    value = norm_snapshot.get(metric_name) if isinstance(norm_snapshot, dict) else None
    if not isinstance(value, dict):
        return None
    low = value.get("min")
    high = value.get("max")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return float(low), float(high)
    return None


def distance_outside_norm(value: float, metric_range: tuple[float, float]) -> float:
    low, high = metric_range
    if value < low:
        return low - value
    if value > high:
        return value - high
    return 0.0


def classify_metric_effect(
    metric_name: str,
    before_value: Any,
    after_value: Any,
    norm_snapshot: dict[str, Any],
) -> tuple[str, float | None, float]:
    if not isinstance(before_value, (int, float)) or not isinstance(after_value, (int, float)):
        return "inconclusive", None, 0.2

    before_float = float(before_value)
    after_float = float(after_value)
    delta = after_float - before_float
    threshold = METRIC_EFFECT_THRESHOLDS.get(metric_name, 0.1)
    metric_range = norm_range_for_metric(norm_snapshot, metric_name)
    if metric_range is None:
        if abs(delta) <= threshold:
            return "unchanged", delta, 0.45
        return "inconclusive", delta, 0.35

    before_distance = distance_outside_norm(before_float, metric_range)
    after_distance = distance_outside_norm(after_float, metric_range)
    if after_distance + threshold < before_distance:
        return "improved", delta, 0.7
    if after_distance > before_distance + threshold:
        return "worsened", delta, 0.65
    return "unchanged", delta, 0.6


def combine_metric_effect_status(statuses: list[str]) -> str:
    meaningful = [status for status in statuses if status != "inconclusive"]
    if not meaningful:
        return "inconclusive"
    if "improved" in meaningful and "worsened" not in meaningful:
        return "improved"
    if "worsened" in meaningful and "improved" not in meaningful:
        return "worsened"
    if all(status == "unchanged" for status in meaningful):
        return "unchanged"
    return "inconclusive"


def infer_operator_action_confirmation(cycle_result: dict[str, Any] | None) -> tuple[bool | None, str]:
    if not isinstance(cycle_result, dict):
        return None, "observed_only"
    followed_ai_advice = str(cycle_result.get("followed_ai_advice") or "unknown").strip().lower()
    if followed_ai_advice in {"yes", "partial"}:
        return True, "operator_reported_followed"
    if followed_ai_advice in {"no", "no_advice"}:
        return False, "observed_only"
    return None, "observed_only"


def build_recommendation_effect_interpretation_payload(
    *,
    effect_status: str,
    operator_action_confirmed: bool | None,
    evidence_level: str,
    metric_statuses: dict[str, str],
    missing_metrics: list[str],
) -> dict[str, Any]:
    if effect_status == "inconclusive" or missing_metrics:
        normalized_evidence_level = "insufficient"
    elif evidence_level == "operator_reported_followed":
        normalized_evidence_level = "operator_reported_followed"
    else:
        normalized_evidence_level = "observed_only"

    return {
        "interpretation_note": RECOMMENDATION_EFFECT_INTERPRETATION_NOTE,
        "causality": "not_proven",
        "causality_not_proven": True,
        "operator_action_confirmed": operator_action_confirmed,
        "operator_action_unknown": operator_action_confirmed is None,
        "evidence_level": normalized_evidence_level,
        "observed_after_recommendation": effect_status != "inconclusive",
        "temporal_association": effect_status != "inconclusive",
        "metric_statuses": metric_statuses,
        "missing_or_stale_metrics": missing_metrics,
    }


def build_effect_summary(
    recommendation: dict[str, Any],
    metrics: list[str],
    before_snapshot: dict[str, Any],
    after_snapshot: dict[str, Any],
    delta_snapshot: dict[str, Any],
    status: str,
) -> str:
    parts: list[str] = []
    for metric_name in metrics:
        before_value = before_snapshot.get(metric_name)
        after_value = after_snapshot.get(metric_name)
        delta_value = delta_snapshot.get(metric_name)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if isinstance(delta_value, (int, float)):
                parts.append(f"{metric_name}: {before_value:g} -> {after_value:g} ({delta_value:+.2f})")
            else:
                parts.append(f"{metric_name}: {before_value:g} -> {after_value:g}")

    window = recommendation.get("window_minutes")
    if not parts:
        return (
            f"After {window} minutes there was not enough fresh telemetry to compare metric changes "
            "after the recommendation. Causality is not proven."
        )

    status_text = {
        "improved": "moved closer to the active norm",
        "unchanged": "changed insignificantly",
        "worsened": "moved farther from the active norm",
        "inconclusive": "does not allow a confident conclusion",
    }.get(status, "does not allow a confident conclusion")
    return (
        f"After {window} minutes, observed metric values changed: {', '.join(parts)}. "
        f"The observation {status_text}. This is a temporal association only; causality is not proven."
    )


async def evaluate_recommendation_effect(recommendation: dict[str, Any]) -> dict[str, Any] | None:
    created_at = parse_event_timestamp(recommendation.get("created_at"))
    window_minutes = int(recommendation.get("window_minutes") or 0)
    if created_at is None or window_minutes <= 0:
        return None

    target_time = created_at + timedelta(minutes=window_minutes)
    metric_name = recommendation.get("metric_name")
    metrics = [metric_name] if metric_name in RECOMMENDATION_METRICS else list(RECOMMENDATION_METRICS)
    before_snapshot = recommendation.get("sensor_snapshot") or {}
    norm_snapshot = recommendation.get("norm_snapshot") or {}
    after_snapshot = await asyncio.to_thread(
        get_metric_snapshot_after,
        tray_id=str(recommendation.get("tray_id") or WATCHDOG_DEFAULT_TRAY_ID),
        after_timestamp=target_time,
        metric_names=metrics,
    )

    delta_snapshot: dict[str, Any] = {}
    metric_statuses: dict[str, str] = {}
    missing_metrics: list[str] = []
    statuses: list[str] = []
    confidences: list[float] = []
    observed_at = after_snapshot.get("observed_at") if isinstance(after_snapshot.get("observed_at"), dict) else {}
    for metric in metrics:
        before_value = before_snapshot.get(metric)
        after_value = after_snapshot.get(metric)
        if not isinstance(before_value, (int, float)) or not isinstance(after_value, (int, float)) or metric not in observed_at:
            status, delta, confidence = "inconclusive", None, 0.2
            missing_metrics.append(metric)
        else:
            status, delta, confidence = classify_metric_effect(
                metric,
                before_value,
                after_value,
                norm_snapshot,
            )
        statuses.append(status)
        confidences.append(confidence)
        metric_statuses[metric] = status
        delta_snapshot[metric] = delta

    effect_status = combine_metric_effect_status(statuses)
    confidence = min(0.95, max(0.0, sum(confidences) / len(confidences))) if confidences else 0.0
    if effect_status == "inconclusive":
        confidence = min(confidence, 0.4)
    effect_summary = build_effect_summary(
        recommendation,
        metrics,
        before_snapshot,
        after_snapshot,
        delta_snapshot,
        effect_status,
    )
    cycle_result = await asyncio.to_thread(get_cycle_result, int(recommendation["cycle_id"]))
    operator_action_confirmed, evidence_level = infer_operator_action_confirmation(cycle_result)
    delta_snapshot.update(
        build_recommendation_effect_interpretation_payload(
            effect_status=effect_status,
            operator_action_confirmed=operator_action_confirmed,
            evidence_level=evidence_level,
            metric_statuses=metric_statuses,
            missing_metrics=missing_metrics,
        )
    )

    return await asyncio.to_thread(
        save_recommendation_effect,
        recommendation_id=int(recommendation["id"]),
        cycle_id=int(recommendation["cycle_id"]),
        tray_id=str(recommendation.get("tray_id") or WATCHDOG_DEFAULT_TRAY_ID),
        window_minutes=window_minutes,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        delta_snapshot=delta_snapshot,
        effect_status=effect_status,
        effect_summary=effect_summary,
        confidence=confidence,
    )


def format_event_age(value: Any) -> str:
    event_time = parse_event_timestamp(value)
    if event_time is None:
        return "время неизвестно"
    now = datetime.now(event_time.tzinfo) if event_time.tzinfo else datetime.now()
    minutes = max(0, int((now - event_time).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} минут назад"
    hours = minutes // 60
    rest_minutes = minutes % 60
    return f"{hours} ч {rest_minutes} мин назад"


def build_device_events_fact_lines(
    events: list[dict[str, Any]],
    device_keyword: str,
    title: str,
) -> list[str]:
    filtered = [
        event for event in events
        if device_keyword in str(event.get("device_id") or "").lower()
    ]
    manual_on_count = sum(1 for event in filtered if event.get("command") == "manual_on")
    manual_off_count = sum(1 for event in filtered if event.get("command") == "manual_off")
    last_on = next((event for event in filtered if event.get("command") == "manual_on"), None)
    lines = [
        f"- событий {title} за 24 часа: {len(filtered)}",
        f"- включений {title} за 24 часа: {manual_on_count}",
        f"- выключений {title} за 24 часа: {manual_off_count}",
    ]
    if last_on:
        lines.append(
            f"- последнее включение {title}: {last_on.get('created_at')} ({format_event_age(last_on.get('created_at'))})"
        )
    else:
        lines.append(f"- в device_events нет включений {title} за последние 24 часа")
    return lines


def build_farm_facts_context_for_prompt(
    message: str,
    tray_id: str = "tray_1",
    messages: list | None = None,
    sensor_freshness: dict[str, dict[str, Any]] | None = None,
) -> str:
    topics = detect_farm_question_topics_from_dialog(message, messages)
    if not topics:
        return ""

    latest_data = get_latest_data_snapshot()
    water_is_fresh = is_sensor_type_fresh(sensor_freshness, "water")
    climate_is_fresh = is_sensor_type_fresh(sensor_freshness, "climate")
    active_cycle = get_active_cycle_ai_context(tray_id)
    norms = active_cycle.get("norms") if isinstance(active_cycle, dict) and isinstance(active_cycle.get("norms"), dict) else {}
    anomaly_events = get_recent_anomaly_events(24)
    needs_device_events = bool(topics & {"watering", "light", "temperature", "general"})
    device_events = get_recent_device_events(tray_id=tray_id, hours=24, limit=100) if needs_device_events else []

    lines = [
        "Расширенный контекст фермы:",
        "- темы вопроса: " + ", ".join(sorted(topics)),
        (
            "- текущие показатели: "
            f"air_temp={format_current_or_stale_value(latest_data.get('Температура'), ' C', climate_is_fresh)}; "
            f"humidity={format_current_or_stale_value(latest_data.get('Влажность'), '%', climate_is_fresh)}; "
            f"water_temp={format_current_or_stale_value(latest_data.get('Темп. воды'), ' C', water_is_fresh)}; "
            f"ph={format_current_or_stale_value(latest_data.get('pH'), '', water_is_fresh)}; "
            f"ec={format_current_or_stale_value(latest_data.get('EC'), '', water_is_fresh)}"
        ),
    ]

    if active_cycle:
        lines.extend([
            (
                "- активный цикл: "
                f"культура={active_cycle.get('crop_name_ru') or active_cycle.get('crop_slug')}; "
                f"день={active_cycle.get('day_number') or 1}; "
                f"версия={active_cycle.get('version_label') or 'не указана'}"
            ),
            (
                "- нормы активного цикла: "
                f"air_temp={format_norm_for_fact(norms, 'air_temp')}; "
                f"humidity={format_norm_for_fact(norms, 'humidity')}; "
                f"water_temp={format_norm_for_fact(norms, 'water_temp')}; "
                f"ph={format_norm_for_fact(norms, 'ph')}; "
                f"ec={format_norm_for_fact(norms, 'ec')}"
            ),
        ])
    else:
        lines.append("- активный цикл: не запущен")

    if "watering" in topics:
        low_humidity_events = [
            event for event in anomaly_events
            if event.get("event_type") == "low_humidity"
        ]
        lines.append("Контекст полива:")
        lines.extend(build_device_events_fact_lines(device_events, "pump", "насоса"))
        lines.extend([
            f"- текущая влажность: {format_current_or_stale_value(latest_data.get('Влажность'), '%', climate_is_fresh)}",
            f"- норма влажности активной культуры: {format_norm_for_fact(norms, 'humidity')}",
            f"- аномалии low_humidity за 24 часа: {'есть' if low_humidity_events else 'нет'}",
        ])

    if "general" in topics and not (topics & {"watering", "temperature", "light"}):
        pump_events = [event for event in device_events if "pump" in str(event.get("device_id") or "").lower()]
        fan_events = [event for event in device_events if "fan" in str(event.get("device_id") or "").lower()]
        light_events = [event for event in device_events if "light" in str(event.get("device_id") or "").lower()]
        lines.extend([
            "Контекст устройств:",
            f"- событий насоса за 24 часа: {len(pump_events)}",
            f"- событий вентиляции за 24 часа: {len(fan_events)}",
            f"- событий освещения за 24 часа: {len(light_events)}",
        ])

    if "solution" in topics:
        solution_anomalies = [
            event for event in anomaly_events
            if event.get("event_type") in {"low_ph", "high_ph", "low_ec", "high_ec"}
        ]
        lines.extend([
            "Контекст питательного раствора:",
            f"- текущий pH: {format_current_or_stale_value(latest_data.get('pH'), '', water_is_fresh)}",
            f"- текущий EC: {format_current_or_stale_value(latest_data.get('EC'), '', water_is_fresh)}",
            f"- норма pH активной культуры: {format_norm_for_fact(norms, 'ph')}",
            f"- норма EC активной культуры: {format_norm_for_fact(norms, 'ec')}",
            f"- аномалии low_ph/high_ph/low_ec/high_ec за 24 часа: {'есть' if solution_anomalies else 'нет'}",
        ])

    if "temperature" in topics:
        temp_anomalies = [
            event for event in anomaly_events
            if event.get("event_type") in {"air_overheat", "air_overcooling", "rapid_air_temp_rise"}
        ]
        lines.extend([
            "Контекст температуры:",
            f"- текущая температура воздуха: {format_current_or_stale_value(latest_data.get('Температура'), ' C', climate_is_fresh)}",
            f"- текущая температура воды: {format_current_or_stale_value(latest_data.get('Темп. воды'), ' C', water_is_fresh)}",
            f"- норма температуры воздуха: {format_norm_for_fact(norms, 'air_temp')}",
            f"- норма температуры воды: {format_norm_for_fact(norms, 'water_temp')}",
        ])
        lines.extend(build_device_events_fact_lines(device_events, "fan", "вентиляции"))
        lines.append(
            f"- аномалии air_overheat/air_overcooling/rapid_air_temp_rise за 24 часа: {'есть' if temp_anomalies else 'нет'}"
        )

    if "light" in topics:
        lines.append("Контекст освещения:")
        lines.extend(build_device_events_fact_lines(device_events, "light", "света"))

    return "\n".join(lines)


def resolve_crop_context_target(message: str, messages: list | None = None, tray_id: str = "tray_1") -> tuple[str | None, str | None]:
    current_crop = extract_last_explicit_crop_from_messages(None, message)
    if current_crop:
        return current_crop, "explicit_crop_from_history"

    if not is_crop_follow_up_message(message):
        return None, None

    history_crop = extract_last_explicit_crop_from_messages(messages)
    if history_crop:
        return history_crop, "explicit_crop_from_history"

    active_cycle = get_active_cycle_ai_context(tray_id)
    if isinstance(active_cycle, dict) and active_cycle.get("crop_slug"):
        return str(active_cycle["crop_slug"]), "active_cycle_fallback"

    return None, None


def build_crop_context_for_prompt(message: str, messages: list | None = None, tray_id: str = "tray_1") -> str:
    crop_slug, source = resolve_crop_context_target(message, messages, tray_id)
    if not crop_slug or not source:
        return ""

    card = get_crop_agrotech_card_from_db(crop_slug)
    if not card:
        return ""

    norms = card.get("norms") if isinstance(card.get("norms"), dict) else {}
    sections = card.get("sections") if isinstance(card.get("sections"), list) else []
    source_rule = (
        "Пользователь, вероятно, продолжает говорить об этой культуре."
        if source == "explicit_crop_from_history"
        else "Если пользователь не уточнил иную культуру, ориентируйся на активную культуру."
    )

    return "\n".join([
        "Контекст культуры из АгроТехКарты:",
        f"- source: {source}",
        f"- rule: {source_rule}",
        f"- crop_slug: {card.get('crop_slug')}",
        f"- crop_name_ru: {card.get('crop_name_ru')}",
        f"- crop_type: {card.get('crop_type')}",
        f"- version_label: {card.get('version_label')}",
        f"- norms: {json.dumps(norms, ensure_ascii=False)}",
        f"- sections: {json.dumps(sections, ensure_ascii=False)}",
    ])


def build_chat_prompt(
    message: str,
    history: list[dict[str, str]] | None = None,
    learning_context: str | None = None,
    stale_sensor_context: str | None = None,
) -> str:
    sensor_freshness_for_prompt: dict[str, dict[str, Any]] = {}
    try:
        sensor_freshness_for_prompt = get_sensor_freshness_status_for_ai()
    except Exception as exc:
        print(f"[AI_STALE_CONTEXT] freshness status unavailable for prompt: {exc}")
    translated_data_string = format_latest_data_for_prompt(sensor_freshness_for_prompt)

    stale_metric_notes: list[str] = []
    water_status = sensor_freshness_for_prompt.get("water") if isinstance(sensor_freshness_for_prompt, dict) else None
    if isinstance(water_status, dict) and not water_status.get("is_fresh"):
        stale_metric_notes.append("pH/EC/температура воды не подтверждены свежими water-данными")
    climate_status = sensor_freshness_for_prompt.get("climate") if isinstance(sensor_freshness_for_prompt, dict) else None
    if isinstance(climate_status, dict) and not climate_status.get("is_fresh"):
        stale_metric_notes.append("температура воздуха/влажность не подтверждены свежими climate-данными")
    if stale_metric_notes:
        translated_data_string += "; stale: " + "; ".join(stale_metric_notes)

    farm_facts_context = build_farm_facts_context_for_prompt(
        message,
        "tray_1",
        messages=history,
        sensor_freshness=sensor_freshness_for_prompt,
    )
    crop_context = build_crop_context_for_prompt(message, messages=history, tray_id="tray_1")
    if stale_sensor_context:
        translated_data_string += (
            ". Внимание: часть показаний может быть устаревшей; смотри блок "
            "'Контекст свежести датчиков' и не оценивай stale-метрики как текущие"
        )
    prompt_parts = []
    if stale_sensor_context:
        prompt_parts.append(stale_sensor_context)
    prompt_parts.extend([
        f"Данные датчиков: {translated_data_string}",
        format_active_cycle_for_prompt("tray_1"),
        (
            "Политика культур текущей фермы:\n"
            "- точные рекомендации даются по культурам из БД АгроТехКарт;\n"
            "- общие справки допустимы только по культурам, подходящим для компактной гидропоники;\n"
            "- крупные плодоносящие, корнеплодные и требующие опоры культуры не считать подходящими для этой установки без отдельной АгроТехКарты."
        ),
    ])
    if farm_facts_context:
        prompt_parts.append(farm_facts_context)
    if crop_context:
        prompt_parts.append(crop_context)
    if learning_context:
        prompt_parts.append(learning_context)

    if history:
        history_lines: list[str] = []
        for item in history:
            role = item.get("role", "").strip().lower()
            text = str(item.get("text") or item.get("content") or "").strip()
            if not text:
                continue
            speaker = "Пользователь" if role == "user" else "Нейрогном"
            history_lines.append(f"{speaker}: {text}")
        if history_lines:
            prompt_parts.append("История диалога:\n" + "\n".join(history_lines))

    prompt_parts.append(f"Пользователь: {message.strip()}\nНейрогном:")
    return "\n\n".join(prompt_parts)


def on_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code == 0:
        client.subscribe(SENSORS_TOPIC)
    else:
        print(f"[БЭКЕНД] Ошибка подключения к MQTT: {reason_code}")


def on_message(client, userdata, msg) -> None:
    payload = msg.payload.decode("utf-8")
    parts = msg.topic.split("/")

    if "sensors" in msg.topic and msg.topic in KNOWN_SENSOR_TOPICS:
        save_telemetry(msg.topic, payload)

    if len(parts) >= 3:
        device_id = parts[1]
        update_device_status(device_id)
        print(f"[БЭКЕНД] Данные от {device_id}: {payload}")


async def internal_watchdog() -> None:
    in_alert_mode = False
    print("[WATCHDOG] Запущен внутри FastAPI. Проверка аномалий каждые 5 сек.")

    while True:
        try:
            climate_records = await asyncio.to_thread(get_last_climate_records, 3)
            water_records = await asyncio.to_thread(get_last_water_records, 3)
            tray_id = watchdog_tray_id(climate_records, water_records)
            active_norm_ranges = await asyncio.to_thread(get_active_cycle_norm_ranges, tray_id)
            anomaly_events = build_anomaly_events(climate_records, water_records, active_norm_ranges)
            anomalies = [event["message"] for event in anomaly_events]

            if anomalies:
                in_alert_mode = True
                print("[WATCHDOG] Обнаружены аномалии:")
                for anomaly in anomalies:
                    print(f"[WATCHDOG] - {anomaly}")
                await save_watchdog_anomaly_events(anomaly_events)
                print("[WATCHDOG] Автоуправление отключено: AI не вызывается и MQTT-команды не отправляются.")
            elif in_alert_mode:
                print("[WATCHDOG] Ситуация нормализовалась. Устройства не переключаются автоматически.")
                in_alert_mode = False
            else:
                print("[WATCHDOG] Аномалий не обнаружено.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[WATCHDOG] Ошибка: {exc}")

        await asyncio.sleep(5)


async def hourly_aggregation_worker() -> None:
    print("[AGGREGATION] Запущена почасовая агрегация")

    while True:
        try:
            aggregated_count = await asyncio.to_thread(aggregate_completed_hours)
            deleted_count = await asyncio.to_thread(delete_old_raw_data, RAW_RETENTION_HOURS)
            print(
                "[AGGREGATION] "
                f"Почасовая агрегация выполнена: новых часов {aggregated_count}; "
                f"удалено старых raw-записей {deleted_count}."
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[AGGREGATION] Ошибка почасовой агрегации: {exc}")

        await asyncio.sleep(HOURLY_AGGREGATION_INTERVAL_SECONDS)


async def predictive_watchdog_worker() -> None:
    print("[PREDICTIVE] Запущен предиктивный анализ трендов")

    while True:
        try:
            norm_ranges = await asyncio.to_thread(
                get_active_cycle_norm_ranges,
                WATCHDOG_DEFAULT_TRAY_ID,
            )
            if norm_ranges:
                hourly_rows = await asyncio.to_thread(
                    get_recent_hourly_summary,
                    PREDICTIVE_HISTORY_HOURS,
                )
                events = build_predictive_anomaly_events(
                    hourly_rows,
                    norm_ranges,
                    WATCHDOG_DEFAULT_TRAY_ID,
                )
                if events:
                    await save_predictive_anomaly_events(events)
                    print(f"[PREDICTIVE] Найдены предиктивные алерты: {len(events)}")
                else:
                    print("[PREDICTIVE] Рисковых трендов не обнаружено.")
            else:
                print("[PREDICTIVE] Активный цикл или нормы не найдены, прогноз пропущен.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[PREDICTIVE] Ошибка предиктивного анализа: {exc}")

        await asyncio.sleep(PREDICTIVE_WATCHDOG_INTERVAL_SECONDS)


async def recommendation_effect_worker() -> None:
    print("[RECOMMENDATIONS] Effect worker started")

    while True:
        try:
            pending = await asyncio.to_thread(
                get_pending_recommendations_for_effect_evaluation,
                RECOMMENDATION_EFFECT_WINDOWS_MINUTES,
                100,
            )
            saved_count = 0
            for recommendation in pending:
                saved = await evaluate_recommendation_effect(recommendation)
                if saved:
                    saved_count += 1
            if saved_count:
                print(f"[RECOMMENDATIONS] Saved recommendation effects: {saved_count}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[RECOMMENDATIONS] Effect worker error: {exc}")

        await asyncio.sleep(RECOMMENDATION_EFFECT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="backend_service")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
    mqtt_client.loop_start()

    app.state.mqtt_client = mqtt_client
    watchdog_task = asyncio.create_task(internal_watchdog())
    aggregation_task = asyncio.create_task(hourly_aggregation_worker())
    predictive_task = asyncio.create_task(predictive_watchdog_worker())
    recommendation_effect_task = asyncio.create_task(recommendation_effect_worker())

    try:
        yield
    finally:
        recommendation_effect_task.cancel()
        predictive_task.cancel()
        aggregation_task.cancel()
        watchdog_task.cancel()
        with suppress(asyncio.CancelledError):
            await recommendation_effect_task
        with suppress(asyncio.CancelledError):
            await predictive_task
        with suppress(asyncio.CancelledError):
            await aggregation_task
        with suppress(asyncio.CancelledError):
            await watchdog_task
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DeviceControlRequest(BaseModel):
    target_id: str
    device_type: Literal["pump", "light", "fan"]
    state: Literal["ON", "OFF", "TIMER"]
    duration: float | None = None


class ChatRequest(BaseModel):
    messages: list


class StartGrowingCycleRequest(BaseModel):
    crop_slug: str
    tray_id: str = "tray_1"
    notes: str | None = None


class EndGrowingCycleRequest(BaseModel):
    tray_id: str = "tray_1"
    notes: str | None = None


class CycleResultPayload(BaseModel):
    harvest_status: Literal["suitable", "partial", "weak_suitable", "failed", "stopped_early"]
    harvest_mass_grams: float | None = None
    completion_reason: Literal["planned", "harvest_ready", "plant_problems", "test_cycle", "other"]
    problem_severity: Literal["none", "minor", "noticeable", "bad", "unknown"] = "unknown"
    problem_phase: Literal["early", "middle", "end", "whole_cycle", "unknown"] = "unknown"
    plant_appearance: dict[str, bool]
    cycle_problems: dict[str, Any]
    manual_actions: dict[str, bool]
    followed_ai_advice: Literal["yes", "partial", "no", "no_advice", "unknown"] = "unknown"
    ai_advice_helpfulness: Literal["yes", "partial", "no", "worse", "unknown"] = "unknown"
    operator_comment: str | None = None


class CycleResultRequest(CycleResultPayload):
    pass


class FinishCycleRequest(CycleResultPayload):
    tray_id: str = "tray_1"
    notes: str | None = None


class FinishCycleResponse(BaseModel):
    cycle: dict[str, Any]
    result: dict[str, Any]


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "db": "initialized"}


@app.get("/api/debug/db-model")
def get_debug_database_model() -> dict[str, Any]:
    return get_database_model_summary()


@app.get("/api/telemetry")
def get_telemetry() -> dict[str, Any]:
    snapshot = get_latest_data_snapshot()
    air_temp = snapshot.get("Температура")
    humidity = snapshot.get("Влажность")
    water_temp = snapshot.get("Темп. воды")
    ph = snapshot.get("pH")
    ec = snapshot.get("EC")

    if air_temp is None or humidity is None or water_temp is None or ph is None or ec is None:
        for record in reversed(get_recent_telemetry(10)):
            payload = record.get("parsed_payload")
            if not isinstance(payload, dict):
                continue

            topic = str(record.get("topic", ""))
            if topic.endswith("/climate"):
                if air_temp is None:
                    air_temp = payload.get("air_temp")
                if humidity is None:
                    humidity = payload.get("humidity")
            elif topic.endswith("/water") and water_temp is None:
                water_temp = payload.get("water_temp")
            if ph is None:
                ph = payload.get("ph", payload.get("pH"))
            if ec is None:
                ec = payload.get("ec", payload.get("EC"))

    return {
        "air_temp": air_temp,
        "humidity": humidity,
        "water_temp": water_temp,
        "ph": ph,
        "ec": ec,
    }


@app.post("/api/device/control")
def control_device(request: DeviceControlRequest) -> dict[str, str]:
    tray_id = request.target_id.strip() or "tray_1"
    device_type = request.device_type.strip().lower()
    state = request.state.strip().upper()
    topic = f"farm/{tray_id}/cmd/{device_type}"
    payload = state

    if state == "TIMER" and request.duration is not None:
        payload = f"TIMER {request.duration:g}"

    app.state.mqtt_client.publish(topic, payload)

    if state == "ON":
        event_command = "manual_on"
        event_value = "on"
    elif state == "OFF":
        event_command = "manual_off"
        event_value = "off"
    else:
        event_command = "manual_toggle"
        event_value = state.lower()

    device_id = f"{tray_id}_{device_type}"
    try:
        save_device_event(
            device_id=device_id,
            tray_id=tray_id,
            command=event_command,
            value=event_value,
            source="manual",
            payload={
                "target_id": request.target_id,
                "tray_id": tray_id,
                "device_type": device_type,
                "state": state,
            },
        )
    except Exception as exc:
        print(f"[DEVICE_EVENTS] Не удалось сохранить событие {device_id}: {exc}")

    return {
        "status": "sent",
        "target_id": tray_id,
        "device_type": device_type,
        "state": state,
        "payload": payload,
    }


@app.post("/api/ai/decide")
async def ai_decide() -> dict[str, Any]:
    active_cycle = await asyncio.to_thread(get_active_cycle_ai_context, "tray_1")
    if not active_cycle:
        thought = "Активный цикл не запущен, агрономическая оценка по конкретной культуре невозможна"
        logs = [
            f"Советник: {thought}",
            "Автоуправление отключено: AI не отправляет MQTT-команды.",
        ]
        await asyncio.to_thread(save_ai_log, thought, [], source="advisor")
        return {"logs": logs, "thought": thought, "commands": []}

    advisor_report = await asyncio.to_thread(build_advisor_response, active_cycle["crop_slug"])
    thought = str(advisor_report.get("summary", "")).strip()
    recommendations = advisor_report.get("recommendations", [])
    risks = advisor_report.get("risks", [])

    logs: list[str] = []
    logs.append(
        "Активный цикл: "
        f"{active_cycle.get('crop_name_ru') or active_cycle.get('crop_slug')} "
        f"({active_cycle.get('crop_slug')}), день {active_cycle.get('day_number')}"
    )
    if thought:
        logs.append(f"Советник: {thought}")
    if isinstance(risks, list):
        for risk in risks:
            logs.append(f"Риск: {risk}")
    if isinstance(recommendations, list):
        for recommendation in recommendations:
            logs.append(f"Рекомендация: {recommendation}")
    logs.append("Автоуправление отключено: AI не отправляет MQTT-команды.")

    await asyncio.to_thread(save_ai_log, thought, [], source="advisor")
    if isinstance(recommendations, list):
        advisor_recommendations = [
            {
                "recommendation_text": str(recommendation),
                "reason": thought,
            }
            for recommendation in recommendations
        ]
        await persist_ai_recommendations(
            advisor_recommendations,
            active_cycle=active_cycle,
            source="advisor",
        )
    return {"logs": logs, "thought": thought, "commands": []}


@app.get("/api/advisor")
def get_advisor(crop: str = Query(default="lettuce")) -> dict[str, Any]:
    return build_advisor_response(crop)


@app.get("/api/advisor/reports/{report_id}")
def api_get_advisor_report(report_id: int) -> dict[str, Any]:
    report = get_advisor_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"error": f"Advisor report '{report_id}' not found"})
    return report


@app.get("/api/crops")
def api_get_crops() -> list[dict[str, Any]]:
    try:
        return get_available_crops()
    except ActiveCardRevisionConflictError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc


@app.get("/api/crops/{crop_slug}/learning-history")
def api_get_crop_learning_history(crop_slug: str) -> dict[str, Any]:
    try:
        return get_crop_learning_history(crop_slug)
    except CropNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc


@app.get("/api/cycles/current")
def api_get_current_growing_cycle(
    tray_id: str = Query(default="tray_1"),
) -> dict[str, Any] | None:
    return get_current_growing_cycle(tray_id)


@app.post("/api/cycles/start")
def api_start_growing_cycle(request: StartGrowingCycleRequest) -> dict[str, Any]:
    try:
        return start_growing_cycle(
            request.crop_slug,
            tray_id=request.tray_id,
            notes=request.notes,
        )
    except CropNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except ActiveCardRevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except ActiveCardRevisionConflictError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    except ActiveGrowingCycleExistsError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc


@app.post("/api/cycles/end", response_model=FinishCycleResponse)
def api_finish_growing_cycle(
    request: FinishCycleRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    try:
        result_payload = request.dict(
            exclude={"tray_id", "notes"},
        )
        finished = finish_growing_cycle_with_result(
            tray_id=request.tray_id,
            result_payload=result_payload,
            notes=request.notes,
        )
        cycle_id = finished.get("cycle", {}).get("id")
        if isinstance(cycle_id, int):
            background_tasks.add_task(run_cycle_learning_pipeline_background, cycle_id)
            print(f"[LEARNING PIPELINE] cycle {cycle_id}: scheduled after cycle finish")
        return finished
    except NoActiveGrowingCycleError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except InvalidCycleResultError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.get("/api/cycles/{cycle_id}/advisor-reports")
def api_get_cycle_advisor_reports(cycle_id: int) -> list[dict[str, Any]]:
    return get_cycle_advisor_reports(cycle_id)


@app.get("/api/recommendations/recent")
def api_get_recent_ai_recommendations(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return get_recent_ai_recommendations(limit)


@app.get("/api/cycles/{cycle_id}/recommendations")
def api_get_cycle_ai_recommendations(cycle_id: int) -> list[dict[str, Any]]:
    return get_cycle_ai_recommendations(cycle_id)


@app.get("/api/cycles/{cycle_id}/recommendation-effects")
def api_get_cycle_recommendation_effects(cycle_id: int) -> list[dict[str, Any]]:
    return get_recommendation_effects(cycle_id)


@app.post("/api/cycles/{cycle_id}/analysis-report")
def api_build_cycle_analysis_report(cycle_id: int) -> dict[str, Any]:
    try:
        report = build_cycle_analysis_report(cycle_id)
        return save_cycle_analysis_report(
            cycle_id,
            report["report_payload"],
            report["summary_text"],
        )
    except GrowingCycleNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except GrowingCycleNotFinishedError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc


@app.get("/api/cycles/{cycle_id}/analysis-report")
def api_get_cycle_analysis_report(cycle_id: int) -> dict[str, Any]:
    report = get_cycle_analysis_report(cycle_id)
    if report is None:
        raise HTTPException(status_code=404, detail={"error": f"Analysis report for cycle '{cycle_id}' not found"})
    return report


@app.post("/api/cycles/{cycle_id}/ai-analysis")
async def api_run_cycle_ai_analysis(cycle_id: int) -> dict[str, Any]:
    try:
        return await run_cycle_ai_analysis(cycle_id)
    except GrowingCycleNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except GrowingCycleNotFinishedError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc


@app.get("/api/cycles/{cycle_id}/ai-analysis")
def api_get_cycle_ai_analysis(cycle_id: int) -> dict[str, Any]:
    analysis = get_cycle_ai_analysis(cycle_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail={"error": f"AI analysis for cycle '{cycle_id}' not found"})
    return analysis


@app.post("/api/cycles/{cycle_id}/agrotech-revision-proposal")
async def api_run_agrotech_revision_proposal(
    cycle_id: int,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    return await run_agrotech_revision_proposal(cycle_id, force=force)


@app.post("/api/cycles/{cycle_id}/learning-pipeline")
async def api_run_cycle_learning_pipeline(
    cycle_id: int,
    auto_apply: bool = Query(default=True),
    force: bool = Query(default=False),
) -> dict[str, Any]:
    return await run_cycle_learning_pipeline(cycle_id, auto_apply=auto_apply, force=force)


@app.get("/api/cycles/{cycle_id}/agrotech-revision-proposal")
def api_get_cycle_agrotech_revision_proposal(cycle_id: int) -> dict[str, Any]:
    proposal = get_cycle_agrotech_revision_proposal(cycle_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail={"error": f"Agrotech revision proposal for cycle '{cycle_id}' not found"})
    return proposal


@app.get("/api/agrotech-revision-proposals/{proposal_id}")
def api_get_agrotech_revision_proposal(proposal_id: int) -> dict[str, Any]:
    proposal = get_agrotech_revision_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail={"error": f"Agrotech revision proposal '{proposal_id}' not found"})
    return proposal


@app.post("/api/agrotech-revision-proposals/{proposal_id}/auto-apply")
def api_auto_apply_agrotech_revision_proposal(
    proposal_id: int,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        return apply_agrotech_revision_proposal(proposal_id, force=force)
    except AgrotechRevisionProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except AgrotechRevisionProposalApplyError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc


@app.post("/api/cycles/{cycle_id}/apply-agrotech-revision-proposal")
def api_apply_cycle_agrotech_revision_proposal(
    cycle_id: int,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        return apply_cycle_agrotech_revision_proposal(cycle_id, force=force)
    except AgrotechRevisionProposalNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except AgrotechRevisionProposalApplyError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc


@app.get("/api/cycles/{cycle_id}/result")
def api_get_cycle_result(cycle_id: int) -> dict[str, Any] | None:
    try:
        return get_cycle_result(cycle_id)
    except GrowingCycleNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc


@app.post("/api/cycles/{cycle_id}/result")
def api_save_cycle_result(cycle_id: int, request: CycleResultRequest) -> dict[str, Any]:
    try:
        return save_cycle_result(
            cycle_id,
            harvest_status=request.harvest_status,
            harvest_mass_grams=request.harvest_mass_grams,
            completion_reason=request.completion_reason,
            problem_severity=request.problem_severity,
            problem_phase=request.problem_phase,
            plant_appearance=request.plant_appearance,
            cycle_problems=request.cycle_problems,
            manual_actions=request.manual_actions,
            followed_ai_advice=request.followed_ai_advice,
            ai_advice_helpfulness=request.ai_advice_helpfulness,
            operator_comment=request.operator_comment,
        )
    except GrowingCycleNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
    except GrowingCycleNotFinishedError as exc:
        raise HTTPException(status_code=409, detail={"error": str(exc)}) from exc
    except InvalidCycleResultError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.get("/api/logs")
def get_logs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return get_recent_ai_logs(limit)


@app.get("/api/system-feed")
def get_system_feed(limit: int = Query(default=15, ge=1, le=100)) -> list[dict[str, Any]]:
    events = get_recent_system_feed_events(limit)
    return [format_system_feed_item(event) for event in events]


@app.post("/api/chat")
@app.post("/api/ai/chat")
async def chat_with_ai(request: ChatRequest) -> dict[str, Any]:
    user_prompt = request.messages[-1]["content"]
    history = request.messages[:-1]
    analysis_steps = [
        "Получен запрос пользователя",
        "Анализирую смысл сообщения",
        "Определяю, какие данные нужны для ответа",
    ]
    analysis_steps.append("Добавляю актуальные показатели фермы в контекст")
    active_cycle = await asyncio.to_thread(get_active_cycle_ai_context, "tray_1")
    analysis_steps.append("Проверяю свежесть данных датчиков")
    question_topics = detect_farm_question_topics_from_dialog(user_prompt, history)
    stale_sensor_context = await asyncio.to_thread(
        build_stale_sensor_context_for_ai,
        24,
        question_topics,
    )
    learning_context = ""
    if active_cycle:
        analysis_steps.append("Добавляю активный цикл выращивания в контекст ИИ")
        crop_slug = str(active_cycle.get("crop_slug") or "").strip()
        if crop_slug:
            learning_context = await asyncio.to_thread(build_crop_learning_context_for_ai, crop_slug)
            if learning_context:
                analysis_steps.append("Добавляю прошлый опыт культуры в контекст ИИ")
    else:
        detected_crops = detect_crops_in_message(user_prompt)
        crop_rules_context = build_crop_rules_context(detected_crops)
        unsupported_crop_context = build_unsupported_crop_context(user_prompt)
        if detected_crops:
            analysis_steps.append("Нашёл упоминания культур в запросе")
        if crop_rules_context:
            analysis_steps.append("Загружаю АгроТехКарты культур из БД")
        if unsupported_crop_context:
            analysis_steps.append("Проверяю ограничения по неподходящим культурам")

    enriched_prompt = build_chat_prompt(
        user_prompt,
        history,
        learning_context=learning_context,
        stale_sensor_context=stale_sensor_context,
    )
    if not active_cycle:
        if crop_rules_context:
            enriched_prompt = f"{crop_rules_context}\n\n{enriched_prompt}"
        if unsupported_crop_context:
            enriched_prompt = f"{unsupported_crop_context}\n\n{enriched_prompt}"

    try:
        reply = await ask_ai(CHAT_SYSTEM_PROMPT, enriched_prompt, history, analysis_steps)
    except Exception as exc:
        analysis_steps.append("Формирую итоговый ответ")
        return {
            "reply": f"Не удалось получить ответ от AI: {exc}",
            "analysis_steps": analysis_steps,
            "status_text": "Нейрогном не смог сформировать ответ",
        }

    if not reply:
        reply = "Недостаточно данных для ответа."
    reply = sanitize_ai_reply(reply)

    analysis_steps.append("Формирую итоговый ответ")
    await asyncio.to_thread(
        save_ai_log,
        reply,
        {
            "type": "chat",
            "analysis_steps": analysis_steps,
        },
        source="chat",
    )
    if active_cycle:
        extracted_recommendations = await extract_recommendations_from_reply(
            reply,
            user_prompt,
            active_cycle,
        )
        await persist_ai_recommendations(
            extracted_recommendations,
            active_cycle=active_cycle,
            source="chat",
        )
    return {
        "reply": reply,
        "analysis_steps": analysis_steps,
        "status_text": "Нейрогном сформировал ответ",
    }
