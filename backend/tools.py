import os
from typing import Any

from db import get_current_metrics as db_get_current_metrics
from db import get_hourly_history
from db import get_recent_anomaly_events

CROPS_DIR = "crops_data"
CLIMATE_TOPIC = "farm/tray_1/sensors/climate"
WATER_TOPIC = "farm/tray_1/sensors/water"


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
    # Защита от выхода из директории
    safe_name = "".join(c for c in crop_name if c.isalnum() or c in (" ", "-", "_")).strip()
    file_path = os.path.join(CROPS_DIR, f"{safe_name}.md")

    if not os.path.exists(file_path):
        return {"error": f"Правила для культуры '{crop_name}' не найдены. Доступные: {os.listdir(CROPS_DIR) if os.path.exists(CROPS_DIR) else 'папка пуста'}"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
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
            "name": "get_crop_rules",
            "description": "Получает справочную информацию (АгроТехКарту) с идеальными показателями для конкретной культуры.",
            "parameters": {
                "type": "object",
                "properties": {
                    "crop_name": {
                        "type": "string",
                        "description": "Название культуры на английском (например: tomatoes, basil)."
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
