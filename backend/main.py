# -*- coding: utf-8 -*-
import asyncio
import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Literal

import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel
from db import (
    aggregate_completed_hours,
    delete_old_raw_data,
    get_last_climate_records,
    get_recent_anomaly_events,
    get_recent_ai_logs,
    get_recent_hourly_summary,
    get_recent_telemetry,
    init_db,
    save_ai_log,
    save_anomaly_event,
    save_telemetry,
    update_device_status,
)
from tools import TOOLS_SCHEMA, get_current_metrics, get_history, get_crop_rules, get_recent_anomalies

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
BROKER_USERNAME = os.getenv("BROKER_USERNAME", "").strip()
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD", "")
SENSORS_TOPIC = "farm/+/sensors/#"
DEVICE_STATUS_TOPIC = "farm/+/status/#"
POLZA_API_KEY = os.getenv("POLZA_API_KEY")
client = AsyncOpenAI(
    api_key=POLZA_API_KEY,
    base_url="https://polza.ai/api/v1"
)

AI_MODEL = os.getenv("AI_MODEL", "gpt-5-nano")
POLZA_BASE_URL = os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1/chat/completions")
KNOWN_SENSOR_TOPICS = {
    "farm/tray_1/sensors/climate",
    "farm/tray_1/sensors/water",
}
KNOWN_DEVICE_TYPES = {"pump", "light", "fan", "humidifier"}
DEFAULT_DAY_SCENARIO_DURATION_MS = 15_000
DEFAULT_DAY_SCENARIO_START_DELAY_MS = 1_200
DEVICE_STATUS_BY_TARGET: dict[str, dict[str, Any]] = {}
DEVICE_STATUS_LOCK = threading.Lock()
HOURLY_AGGREGATION_INTERVAL_SECONDS = 300
RAW_RETENTION_HOURS = 24
ANOMALY_EVENT_COOLDOWN_MINUTES = 5
ADVISOR_HISTORY_HOURS = 24
CHAT_SYSTEM_PROMPT = (
    "Ты — Нейрогном, дружелюбный, умный и лаконичный помощник сити-фермы. "
    "В каждом запросе тебе невидимо передаются текущие показатели датчиков (Температура воздуха, Влажность, Температура воды).\n\n"
    "ТВОИ ПРАВИЛА:\n"
    "1. Режим молчания о цифрах: НИКОГДА не перечисляй и не упоминай текущие показатели датчиков, "
    "если пользователь прямо не спросил ('как показатели?', 'всё ли в норме?'). Для обычных бесед используй эти данные только в уме.\n"
    "2. Светская беседа: Если с тобой просто здороваются или общаются на отвлеченные темы — "
    "отвечай по-человечески, тепло и без занудства.\n"
    "3. Тревога: Если ты видишь в скрытых данных, что параметры вышли за рамки "
    "(например, температура воздуха выше 28 градусов или влажность ниже 50%) — мягко предупреди об опасности и дай совет.\n"
    "4. Агро-энциклопедия: Если спрашивают, как выращивать конкретную культуру, выдай базовые "
    "требования. Если текущие показатели фермы подходят под эти требования — можешь порадоваться этому.\n"
    "5. Ограничения языка: Отвечай на русском языке. Обозначения pH и EC разрешены. "
    "Английские slug-названия культур можно использовать, если пользователь сам их написал или если это нужно для точности. "
    "Запрещено использовать программный код, теги или markdown-разметку. Пиши чистым, обычным текстом."
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
    # Корнеплодный редис и полноценный горох не подменяем микрозеленью.
    "microgreen_radish": (
        "microgreen_radish",
        "microgreen radish",
        "микрозелень редиса",
        "редисная микрозелень",
    ),
    "microgreen_pea": (
        "microgreen_pea",
        "microgreen pea",
        "микрозелень гороха",
        "гороховая микрозелень",
        "гороховые побеги",
        "побеги гороха",
    ),
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


def is_root_radish_question(message: str) -> bool:
    normalized_message = message.lower().replace("ё", "е")
    asks_about_radish = re.search(r"(?<![\w])редис[а-я]*(?![\w])", normalized_message, re.IGNORECASE)
    asks_about_microgreen = re.search(
        r"микрозелень\s+редиса|редисная\s+микрозелень",
        normalized_message,
        re.IGNORECASE,
    )
    return bool(asks_about_radish and not asks_about_microgreen)


def is_regular_pea_question(message: str) -> bool:
    normalized_message = message.lower().replace("ё", "е")
    asks_about_pea = re.search(r"(?<![\w])горох[а-я]*(?![\w])", normalized_message, re.IGNORECASE)
    asks_about_microgreen_or_shoots = re.search(
        r"микрозелень\s+гороха|гороховая\s+микрозелень|гороховые\s+побеги|побеги\s+гороха|побег",
        normalized_message,
        re.IGNORECASE,
    )
    return bool(asks_about_pea and not asks_about_microgreen_or_shoots)


def build_unsupported_crop_context(message: str) -> str:
    notes: list[str] = []

    if is_root_radish_question(message):
        notes.append(
            "Корнеплодный редис не является базовой культурой маленькой сити-фермы "
            "в текущей crops_data. Не выдавай его нормы как нормы microgreen_radish. "
            "Объясни пользователю, что вместо корнеплодного редиса в этой установке "
            "поддерживается микрозелень редиса."
        )
    if is_regular_pea_question(message):
        notes.append(
            "Полноценный горох не является базовой культурой маленькой сити-фермы "
            "в текущей crops_data. Не выдавай его нормы как нормы microgreen_pea. "
            "Объясни пользователю, что в этой установке можно выращивать микрозелень "
            "или побеги гороха."
        )

    if not notes:
        return ""

    return "Ограничение базы культур:\n" + "\n".join(f"- {note}" for note in notes)


def build_crop_rules_context(crops: list[str]) -> str:
    sections: list[str] = []

    for crop in crops[:3]:
        rules = get_crop_rules(crop)
        if isinstance(rules, str) and rules.strip():
            sections.append(f"Культура: {crop}\n{rules.strip()}")

    if not sections:
        return ""

    return (
        "База знаний культур из crops_data. Используй этот блок как главный источник "
        "по нормам pH, EC, температуре, циклам, алертам и рекомендациям.\n\n"
        + "\n\n---\n\n".join(sections)
    )


def ensure_crop_files() -> None:
    crops_data_dir = BASE_DIR / "crops_data"
    crops_data_dir.mkdir(exist_ok=True)

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


def build_anomaly_events(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []

    latest_record = records[-1]
    latest_payload = latest_record.get("parsed_payload", {})
    if not isinstance(latest_payload, dict):
        latest_payload = {}

    events: list[dict[str, Any]] = []
    tray_id = get_record_tray_id(latest_record)
    air_temp = latest_payload.get("air_temp")
    humidity = latest_payload.get("humidity")

    if isinstance(air_temp, (int, float)) and air_temp > 28:
        events.append(
            {
                "tray_id": tray_id,
                "sensor_type": "climate",
                "event_type": "air_overheat",
                "metric_name": "air_temp",
                "severity": "warning",
                "value": float(air_temp),
                "message": f"Перегрев воздуха: air_temp={air_temp}",
                "payload": latest_payload,
            }
        )

    if isinstance(air_temp, (int, float)) and air_temp < 18:
        events.append(
            {
                "tray_id": tray_id,
                "sensor_type": "climate",
                "event_type": "air_overcooling",
                "metric_name": "air_temp",
                "severity": "warning",
                "value": float(air_temp),
                "message": f"Переохлаждение воздуха: air_temp={air_temp}",
                "payload": latest_payload,
            }
        )

    if isinstance(humidity, (int, float)) and humidity < 50:
        events.append(
            {
                "tray_id": tray_id,
                "sensor_type": "climate",
                "event_type": "low_humidity",
                "metric_name": "humidity",
                "severity": "warning",
                "value": float(humidity),
                "message": f"Низкая влажность: humidity={humidity}",
                "payload": latest_payload,
            }
        )

    if len(records) >= 3:
        first_payload = records[0].get("parsed_payload", {})
        last_payload = records[-1].get("parsed_payload", {})
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
                                "latest_payload": latest_payload,
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


def parse_crop_ranges(crop_rules: Any) -> dict[str, tuple[float, float]]:
    if not isinstance(crop_rules, str):
        return {}

    norms_match = re.search(
        r"(?ims)^##\s+Нормы\s*$\s*(.*?)(?=^##\s+|\Z)",
        crop_rules,
    )
    if not norms_match:
        return {}

    norms_block = norms_match.group(1)
    metric_names = ["air_temp", "humidity", "water_temp", "ph", "ec"]
    parsed: dict[str, tuple[float, float]] = {}

    for metric_name in metric_names:
        match = re.search(
            rf"(?im)^\s*{re.escape(metric_name)}\s*:\s*(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)\b",
            norms_block,
        )
        if not match:
            continue
        low, high = match.groups()
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
    crop_rules = get_crop_rules(crop)
    crop_ranges = parse_crop_ranges(crop_rules)

    risks: list[str] = []
    recommendations: list[str] = []
    trend_notes = build_hourly_trend_notes(hourly_rows)

    if not telemetry_records:
        return {
            "summary": "Данных телеметрии пока недостаточно для агрономической оценки.",
            "risks": ["Нет свежих показаний из telemetry_raw."],
            "recommendations": ["Запустите симулятор или проверьте поступление MQTT-данных."],
            "data": {
                "crop": crop,
                "current": current,
                "history_hours": ADVISOR_HISTORY_HOURS,
                "hourly_points": len(hourly_rows),
                "anomaly_events": len(anomaly_events),
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
            "crop_rules_loaded": isinstance(crop_rules, str),
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


async def ask_ai(
    system_prompt: str,
    user_prompt: str,
    message_history: list = None,
    analysis_steps: list[str] | None = None,
) -> str:
    # Собираем контекст сообщений
    messages = [{"role": "system", "content": system_prompt}]
    if message_history:
        messages.extend(message_history)
    messages.append({"role": "user", "content": user_prompt})

    model_name = os.getenv("AI_MODEL", "gpt-5.4-mini")

    # Цикл агента (максимум 5 шагов, чтобы избежать бесконечного зацикливания)
    for _ in range(5):
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=0.2
            )

            message = response.choices[0].message
            messages.append(message) # Добавляем ответ модели в историю

            # Если ИИ не вызывает функции, значит это финальный текстовый ответ
            if not message.tool_calls:
                return message.content

            # Если ИИ хочет вызвать функции, выполняем их
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if func_name == "get_current_metrics":
                    add_analysis_step(analysis_steps, "Получаю текущие показатели фермы")
                    result = get_current_metrics()
                elif func_name == "get_history":
                    add_analysis_step(analysis_steps, "Получаю почасовую историю показателей")
                    result = get_history(args.get("metric_name"), args.get("hours", 24))
                elif func_name == "get_crop_rules":
                    add_analysis_step(analysis_steps, "Проверяю правила выбранной культуры")
                    result = get_crop_rules(args.get("crop_name"))
                elif func_name == "get_recent_anomalies":
                    add_analysis_step(analysis_steps, "Проверяю последние события anomaly_events")
                    result = get_recent_anomalies(args.get("hours", 24))
                else:
                    result = {"error": f"Неизвестная функция {func_name}"}

                # Добавляем результат функции в историю сообщений
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": json.dumps(result, ensure_ascii=False)
                })

        except Exception as e:
            return f"Ошибка при обращении к ИИ: {str(e)}"

    return "Я слишком долго думал над этим вопросом и запутался. Пожалуйста, переформулируйте."


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


def format_latest_data_for_prompt() -> str:
    latest_data = get_latest_data_snapshot()

    air_temp = latest_data.get("Температура")
    humidity = latest_data.get("Влажность")
    water_temp = latest_data.get("Темп. воды")
    ph = latest_data.get("pH")
    ec = latest_data.get("EC")
    ph_text = format_sensor_value(ph, "") if ph is not None else "данных по pH пока нет"
    ec_text = format_sensor_value(ec, "") if ec is not None else "данных по EC пока нет"

    return (
        f"Текущие показатели: Температура воздуха {format_sensor_value(air_temp, ' C')}, "
        f"Влажность {format_sensor_value(humidity, '%')}, "
        f"Температура воды {format_sensor_value(water_temp, ' C')}, "
        f"pH {ph_text}, EC {ec_text}"
    )


def build_chat_prompt(message: str, history: list[dict[str, str]] | None = None) -> str:
    translated_data_string = format_latest_data_for_prompt()
    prompt_parts = [f"Данные датчиков: {translated_data_string}"]

    if history:
        history_lines: list[str] = []
        for item in history:
            role = item.get("role", "").strip().lower()
            text = item.get("text", "").strip()
            if not text:
                continue
            speaker = "Пользователь" if role == "user" else "Нейрогном"
            history_lines.append(f"{speaker}: {text}")
        if history_lines:
            prompt_parts.append("История диалога:\n" + "\n".join(history_lines))

    prompt_parts.append(f"Пользователь: {message.strip()}\nНейрогном:")
    return "\n\n".join(prompt_parts)


def normalize_device_status(raw_status: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_status = raw_status or {}
    day_start_at_ms = raw_status.get("day_start_at_ms", raw_status.get("day_started_at_ms"))
    day_duration_ms = raw_status.get("day_duration_ms", DEFAULT_DAY_SCENARIO_DURATION_MS)
    day_scenario_running = bool(raw_status.get("day_scenario_running", False))
    day_scenario_pending = bool(raw_status.get("day_scenario_pending", False))
    light = bool(raw_status.get("light", False))

    if (
        (day_scenario_running or day_scenario_pending)
        and isinstance(day_start_at_ms, (int, float))
        and day_start_at_ms > 0
        and isinstance(day_duration_ms, (int, float))
    ):
        if int(time.time() * 1000) >= int(day_start_at_ms) + int(day_duration_ms):
            day_scenario_running = False
            day_scenario_pending = False
            light = False

    return {
        "pump": bool(raw_status.get("pump", False)),
        "fan": bool(raw_status.get("fan", False)),
        "light": light,
        "humidifier": bool(raw_status.get("humidifier", False)),
        "day_scenario_running": day_scenario_running,
        "day_scenario_pending": day_scenario_pending,
        "day_stage": raw_status.get("day_stage"),
        "day_start_at_ms": day_start_at_ms,
        "day_duration_ms": day_duration_ms,
        "availability": raw_status.get("availability", "unknown"),
        "updated_at_ms": raw_status.get("updated_at_ms"),
    }


def get_device_status_snapshot(target_id: str) -> dict[str, Any]:
    with DEVICE_STATUS_LOCK:
        status = normalize_device_status(DEVICE_STATUS_BY_TARGET.get(target_id))

    status["target_id"] = target_id
    status["server_now_ms"] = int(time.time() * 1000)
    return status


def merge_device_status(target_id: str, status_patch: dict[str, Any]) -> None:
    with DEVICE_STATUS_LOCK:
        current = DEVICE_STATUS_BY_TARGET.get(target_id, {})
        current.update(status_patch)
        current["updated_at_ms"] = int(time.time() * 1000)
        DEVICE_STATUS_BY_TARGET[target_id] = current


def parse_mqtt_json_payload(payload: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def handle_device_status_message(topic: str, payload: str) -> None:
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "farm" or parts[2] != "status":
        return

    target_id = parts[1]
    status_type = parts[3]

    if status_type == "availability":
        merge_device_status(target_id, {"availability": payload.strip()})
        return

    if status_type != "devices":
        return

    parsed_payload = parse_mqtt_json_payload(payload)
    if parsed_payload is None:
        return

    normalized_payload = normalize_device_status(parsed_payload)
    if "availability" not in parsed_payload:
        normalized_payload.pop("availability", None)
    merge_device_status(target_id, normalized_payload)


def on_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code == 0:
        client.subscribe(SENSORS_TOPIC)
        client.subscribe(DEVICE_STATUS_TOPIC)
    else:
        print(f"[БЭКЕНД] Ошибка подключения к MQTT: {reason_code}")


def on_message(client, userdata, msg) -> None:
    payload = msg.payload.decode("utf-8")
    parts = msg.topic.split("/")

    if "sensors" in msg.topic and msg.topic in KNOWN_SENSOR_TOPICS:
        save_telemetry(msg.topic, payload)

    if len(parts) >= 4 and parts[2] == "status":
        handle_device_status_message(msg.topic, payload)

    if len(parts) >= 3:
        device_id = parts[1]
        update_device_status(device_id)
        print(f"[БЭКЕНД] Данные от {device_id}: {payload}")


async def internal_watchdog() -> None:
    in_alert_mode = False
    print("[WATCHDOG] Запущен внутри FastAPI. Проверка аномалий каждые 5 сек.")

    while True:
        try:
            records = await asyncio.to_thread(get_last_climate_records, 3)
            anomalies = detect_anomalies(records)
            anomaly_events = build_anomaly_events(records)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_crop_files()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="backend_service")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    if BROKER_USERNAME:
        mqtt_client.username_pw_set(BROKER_USERNAME, BROKER_PASSWORD or None)
    mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
    mqtt_client.loop_start()

    app.state.mqtt_client = mqtt_client
    watchdog_task = asyncio.create_task(internal_watchdog())
    aggregation_task = asyncio.create_task(hourly_aggregation_worker())

    try:
        yield
    finally:
        aggregation_task.cancel()
        watchdog_task.cancel()
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
    device_type: Literal["pump", "light", "fan", "humidifier"]
    state: Literal["ON", "OFF", "TIMER"]
    duration: float | None = None


class LightDayScenarioRequest(BaseModel):
    target_id: str = "tray_1"
    duration_ms: int = DEFAULT_DAY_SCENARIO_DURATION_MS
    start_delay_ms: int = DEFAULT_DAY_SCENARIO_START_DELAY_MS


class ChatRequest(BaseModel):
    messages: list


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "db": "initialized"}


@app.get("/api/telemetry")
def get_telemetry() -> dict[str, Any]:
    snapshot = get_latest_data_snapshot()
    air_temp = snapshot.get("Температура")
    humidity = snapshot.get("Влажность")
    water_temp = snapshot.get("Темп. воды")

    if air_temp is None or humidity is None or water_temp is None:
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

    return {
        "air_temp": air_temp,
        "humidity": humidity,
        "water_temp": water_temp,
    }


@app.post("/api/device/control")
def control_device(request: DeviceControlRequest) -> dict[str, str]:
    topic = f"farm/{request.target_id}/cmd/{request.device_type}"
    payload = request.state

    if request.state == "TIMER" and request.duration is not None:
        payload = f"TIMER {request.duration:g}"

    app.state.mqtt_client.publish(topic, payload)
    if request.state in {"ON", "OFF"}:
        merge_device_status(
            request.target_id,
            {
                request.device_type: request.state == "ON",
                **(
                    {
                        "day_scenario_running": False,
                        "day_scenario_pending": False,
                        "day_start_at_ms": None,
                    }
                    if request.device_type == "light" and request.state == "OFF"
                    else {}
                ),
            },
        )
    return {
        "status": "sent",
        "target_id": request.target_id,
        "device_type": request.device_type,
        "state": request.state,
        "payload": payload,
    }


@app.get("/api/device/status")
def get_device_status(target_id: str = Query(default="tray_1")) -> dict[str, Any]:
    return get_device_status_snapshot(target_id)


@app.post("/api/light/day")
def start_light_day_scenario(request: LightDayScenarioRequest) -> dict[str, Any]:
    duration_ms = max(1_000, min(int(request.duration_ms), 24 * 60 * 60 * 1000))
    start_delay_ms = max(0, min(int(request.start_delay_ms), 60_000))
    server_now_ms = int(time.time() * 1000)
    start_at_ms = server_now_ms + start_delay_ms
    topic = f"farm/{request.target_id}/cmd/light"
    payload_data = {
        "command": "DAY_SCENARIO",
        "start_at_ms": start_at_ms,
        "start_in_ms": start_delay_ms,
        "duration_ms": duration_ms,
        "stage_count": 10,
    }
    payload = json.dumps(payload_data, ensure_ascii=False, separators=(",", ":"))

    app.state.mqtt_client.publish(topic, payload)
    merge_device_status(
        request.target_id,
        {
            "light": True,
            "day_scenario_running": True,
            "day_scenario_pending": True,
            "day_stage": 0,
            "day_start_at_ms": start_at_ms,
            "day_duration_ms": duration_ms,
        },
    )

    return {
        "status": "sent",
        "target_id": request.target_id,
        "topic": topic,
        "payload": payload_data,
        "server_now_ms": server_now_ms,
        "start_at_ms": start_at_ms,
        "start_delay_ms": start_delay_ms,
        "duration_ms": duration_ms,
    }


@app.post("/api/ai/decide")
async def ai_decide() -> dict[str, Any]:
    advisor_report = await asyncio.to_thread(build_advisor_response, "lettuce")
    thought = str(advisor_report.get("summary", "")).strip()
    recommendations = advisor_report.get("recommendations", [])
    risks = advisor_report.get("risks", [])

    logs: list[str] = []
    if thought:
        logs.append(f"Советник: {thought}")
    if isinstance(risks, list):
        for risk in risks:
            logs.append(f"Риск: {risk}")
    if isinstance(recommendations, list):
        for recommendation in recommendations:
            logs.append(f"Рекомендация: {recommendation}")
    logs.append("Автоуправление отключено: AI не отправляет MQTT-команды.")

    await asyncio.to_thread(save_ai_log, thought, [])
    return {"logs": logs, "thought": thought, "commands": []}


@app.get("/api/advisor")
def get_advisor(crop: str = Query(default="lettuce")) -> dict[str, Any]:
    return build_advisor_response(crop)


@app.get("/api/logs")
def get_logs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return get_recent_ai_logs(limit)


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
    enriched_prompt = build_chat_prompt(user_prompt, history)
    analysis_steps.append("Добавляю актуальные показатели фермы в контекст")
    detected_crops = detect_crops_in_message(user_prompt)
    crop_rules_context = build_crop_rules_context(detected_crops)
    unsupported_crop_context = build_unsupported_crop_context(user_prompt)
    if detected_crops:
        analysis_steps.append("Нашёл упоминания культур в запросе")
    if crop_rules_context:
        analysis_steps.append("Загружаю базу знаний культур из crops_data")
        enriched_prompt = f"{crop_rules_context}\n\n{enriched_prompt}"
    if unsupported_crop_context:
        analysis_steps.append("Проверяю ограничения по неподходящим культурам")
        enriched_prompt = f"{unsupported_crop_context}\n\n{enriched_prompt}"

    try:
        reply = await ask_ai(CHAT_SYSTEM_PROMPT, enriched_prompt, None, analysis_steps)
    except Exception as exc:
        analysis_steps.append("Формирую итоговый ответ")
        return {
            "reply": f"Не удалось получить ответ от AI: {exc}",
            "analysis_steps": analysis_steps,
            "status_text": "Нейрогном не смог сформировать ответ",
        }

    if not reply:
        reply = "Недостаточно данных для ответа."

    analysis_steps.append("Формирую итоговый ответ")
    await asyncio.to_thread(
        save_ai_log,
        reply,
        {
            "type": "chat",
            "analysis_steps": analysis_steps,
        },
    )
    return {
        "reply": reply,
        "analysis_steps": analysis_steps,
        "status_text": "Нейрогном сформировал ответ",
    }
