from pathlib import Path
from typing import Any

from db import get_current_metrics as db_get_current_metrics
from db import get_crop_agrotech_card_from_db
from db import get_hourly_history
from db import get_recent_anomaly_events

BASE_DIR = Path(__file__).resolve().parent
CROPS_DIR = BASE_DIR / "crops_data"
CLIMATE_TOPIC = "farm/tray_1/sensors/climate"
WATER_TOPIC = "farm/tray_1/sensors/water"
CROP_NAME_ALIASES: dict[str, str] = {
    "basil": "basil",
    "базилик": "basil",
    "arugula": "arugula",
    "руккола": "arugula",
    "рукола": "arugula",
    "lettuce": "lettuce",
    "латук": "lettuce",
    "салат латук": "lettuce",
    "листовой салат": "lettuce",
    "салат": "lettuce",
    "spinach": "spinach",
    "шпинат": "spinach",
    "cilantro": "cilantro",
    "кинза": "cilantro",
    "кориандр": "cilantro",
    "parsley": "parsley",
    "петрушка": "parsley",
    "mint": "mint",
    "мята": "mint",
    "dill": "dill",
    "укроп": "dill",
    "pak_choi": "pak_choi",
    "pak choi": "pak_choi",
    "pak-choi": "pak_choi",
    "пак-чой": "pak_choi",
    "пак чой": "pak_choi",
    "chard": "chard",
    "мангольд": "chard",
    "microgreen_radish": "microgreen_radish",
    "microgreen radish": "microgreen_radish",
    "микрозелень редиса": "microgreen_radish",
    "редисная микрозелень": "microgreen_radish",
    "microgreen_pea": "microgreen_pea",
    "microgreen pea": "microgreen_pea",
    "микрозелень гороха": "microgreen_pea",
    "гороховая микрозелень": "microgreen_pea",
    "гороховые побеги": "microgreen_pea",
    "побеги гороха": "microgreen_pea",
}


def normalize_crop_name(crop_name) -> str:
    normalized = str(crop_name or "").strip().lower().replace("ё", "е")
    normalized = normalized.replace("_", " ")
    normalized = " ".join(normalized.replace("-", " ").split())

    for alias, slug in CROP_NAME_ALIASES.items():
        normalized_alias = alias.lower().replace("ё", "е").replace("_", " ")
        normalized_alias = " ".join(normalized_alias.replace("-", " ").split())
        if normalized == normalized_alias:
            return slug

    return "".join(c for c in str(crop_name or "") if c.isalnum() or c in (" ", "-", "_")).strip()


def get_current_metrics() -> dict[str, Any]:
    """Возвращает последние показания датчиков."""
    try:
        return db_get_current_metrics()
    except Exception as e:
        return {"error": str(e)}


def get_history(metric_name, hours=24) -> dict[str, str] | list[dict[str, Any]]:
    """Возвращает усредненную историю за указанное количество часов."""
    if metric_name not in {"temperature", "humidity", "water_temp", "ph", "ec"}:
        return {"error": f"Неизвестная метрика: {metric_name}"}

    try:
        hours = int(hours)
        return get_hourly_history(metric_name, hours)
    except Exception as e:
        return {"error": str(e)}


def get_crop_rules(crop_name):
    """Читает правила выращивания культуры из Markdown файла."""
    safe_name = normalize_crop_name(crop_name)
    file_path = CROPS_DIR / f"{safe_name}.md"

    if not file_path.exists():
        available = [path.name for path in CROPS_DIR.iterdir()] if CROPS_DIR.exists() else "папка пуста"
        return {"error": f"Правила для культуры '{crop_name}' не найдены. Доступные: {available}"}

    try:
        with file_path.open("r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return {"error": str(e)}


def get_crop_agrotech_card(crop_name):
    """Возвращает активную АгроТехКарту культуры из PostgreSQL."""
    safe_name = normalize_crop_name(crop_name)
    try:
        card = get_crop_agrotech_card_from_db(safe_name)
        if card is None:
            card = get_crop_agrotech_card_from_db(crop_name)
        if card is None:
            return {"error": f"АгроТехКарта для культуры '{crop_name}' не найдена в БД"}
        return card
    except Exception as e:
        return {"error": str(e)}


def get_recent_anomalies(hours=24) -> dict[str, str] | list[dict[str, Any]]:
    """Возвращает последние события аномалий за указанный период."""
    try:
        return get_recent_anomaly_events(int(hours))
    except Exception as e:
        return {"error": str(e)}


# Схема инструментов для OpenAI API
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_current_metrics",
            "description": "Получает самые свежие, текущие показания датчиков фермы (температура, влажность, температура воды, pH, EC). Вызывай, когда спрашивают 'как дела сейчас'."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_history",
            "description": "Получает историю (тренды) конкретного датчика за указанное количество часов. Данные возвращаются усредненными по часам.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "enum": ["temperature", "humidity", "water_temp", "ph", "ec"],
                        "description": "Название метрики для анализа."
                    },
                    "hours": {
                        "type": "integer",
                        "description": "За сколько последних часов выгрузить историю. По умолчанию 24."
                    }
                },
                "required": ["metric_name", "hours"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_crop_agrotech_card",
            "description": "Получает активную АгроТехКарту культуры из PostgreSQL: нормы, версию карты и разделы описания.",
            "parameters": {
                "type": "object",
                "properties": {
                    "crop_name": {
                        "type": "string",
                        "description": "Название культуры или slug, например: базилик, салат, basil."
                    }
                },
                "required": ["crop_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_anomalies",
            "description": "Получает последние события аномалий фермы за указанный период. Вызывай, когда нужно проверить перегрев, низкую влажность или другие недавние проблемы.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "За сколько последних часов выгрузить события. По умолчанию 24."
                    }
                },
                "required": ["hours"]
            }
        }
    }
]
