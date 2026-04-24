# -*- coding: utf-8 -*-
import asyncio
import json
import os
import sqlite3
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel
from tools import TOOLS_SCHEMA, get_current_metrics, get_history, get_crop_rules

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

DB_PATH = BASE_DIR / "farm.db"
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
KNOWN_SENSOR_TOPICS = {
    "farm/tray_1/sensors/climate",
    "farm/tray_1/sensors/water",
}
KNOWN_DEVICE_TYPES = {"pump", "light", "fan"}
AI_COOLDOWN_SECONDS = 5
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
    "5. Ограничения языка: Отвечай ИСКЛЮЧИТЕЛЬНО на русском языке. КАТЕГОРИЧЕСКИ запрещено использовать английские слова. "
    "Запрещено использовать любые странные символы, программный код, теги или markdown-разметку. Пиши чистым, обычным текстом."
)


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def init_db() -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                status TEXT,
                last_seen DATETIME
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                payload TEXT,
                timestamp DATETIME
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON telemetry(timestamp);")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                thought TEXT,
                commands_json TEXT
            )
            """
        )
        connection.commit()

    crops_data_dir = BASE_DIR / "crops_data"
    crops_data_dir.mkdir(exist_ok=True)
    tomatoes_file = crops_data_dir / "tomatoes.md"
    if not tomatoes_file.exists():
        tomatoes_file.write_text(
            """# Томаты (Черри) - АгроТехКарта
- Оптимальная температура: 22-26°C
- Оптимальная влажность: 60-75%
- Оптимальная температура воды: 18-22°C
- Требуемый pH: 5.5-6.5
- Требуемый EC: 2.0-2.5
Внимание: при падении температуры ниже 18°C рост замедляется.
""",
            encoding="utf-8",
        )

def current_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_json_payload(payload: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        return parsed

    return None


def update_device_status(device_id: str) -> None:
    last_seen = current_timestamp()
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO devices (id, status, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                last_seen = excluded.last_seen
            """,
            (device_id, "online", last_seen),
        )
        connection.commit()


def save_telemetry(topic: str, payload: str) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO telemetry (topic, payload, timestamp)
            VALUES (?, ?, ?)
            """,
            (topic, payload, current_timestamp()),
        )
        connection.commit()


def save_ai_log(thought: str, commands: list[dict[str, Any]]) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO ai_logs (timestamp, thought, commands_json)
            VALUES (?, ?, ?)
            """,
            (current_timestamp(), thought, json.dumps(commands, ensure_ascii=False)),
        )
        connection.commit()


def get_recent_telemetry(limit: int = 15) -> list[dict[str, Any]]:
    with get_db_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, topic, payload, timestamp
            FROM telemetry
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    records: list[dict[str, Any]] = []
    for row in reversed(rows):
        record = dict(row)
        record["parsed_payload"] = parse_json_payload(str(record["payload"]))
        records.append(record)
    return records


def get_last_climate_records(limit: int = 3) -> list[dict[str, Any]]:
    with get_db_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, topic, payload, timestamp
            FROM telemetry
            WHERE topic = 'farm/tray_1/sensors/climate'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    records: list[dict[str, Any]] = []
    for row in reversed(rows):
        record = dict(row)
        parsed_payload = parse_json_payload(str(record["payload"]))
        if isinstance(parsed_payload, dict):
            record["parsed_payload"] = parsed_payload
            records.append(record)
    return records


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


def get_recent_ai_logs(limit: int = 50) -> list[dict[str, Any]]:
    with get_db_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, timestamp, thought, commands_json
            FROM ai_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


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


async def ask_ai(system_prompt: str, user_prompt: str, message_history: list = None) -> str:
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
                    result = get_current_metrics()
                elif func_name == "get_history":
                    result = get_history(args.get("metric_name"), args.get("hours", 24))
                elif func_name == "get_crop_rules":
                    result = get_crop_rules(args.get("crop_name"))
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


def build_decision_ai_request(records: list[dict[str, Any]]) -> tuple[str, str]:
    telemetry_russian = format_telemetry_records_russian(records)
    system_prompt = (
        "Ты — Нейрогном, эксперт сити-фермы. Отвечай только валидным JSON без markdown. "
        "Используй только русский текст в поле thought и только допустимые device_type: fan, pump, light."
    )
    user_prompt = (
        "Проанализируй данные датчиков и верни только валидный JSON без markdown.\n"
        "Полный набор правил принятия решений:\n"
        "- Если air_temp > 28 C, включи fan командой ON.\n"
        "- Если air_temp < 18 C, включи light командой ON для обогрева и обязательно выключи fan командой OFF.\n"
        "- Если humidity < 50 %, включи pump командой TIMER на 5 секунд.\n"
        "- Если water_temp < 18 C, включи light командой ON.\n"
        "- Если water_temp > 26 C, выключи light командой OFF.\n"
        "- Если температура воздуха 18-28 C и влажность выше 50%, это считается нормой. В этом случае верни команды на выключение всех активных устройств, например fan OFF и light OFF.\n"
        "- Если температура воздуха быстро растет более чем на 2 C за 3 последних замера, учти это как тревожный признак.\n"
        "- Если действий не требуется, верни пустой массив commands.\n"
        "Формат ответа:\n"
        "{"
        "\"thought\":\"Краткое объяснение\","
        "\"commands\":[{\"device_type\":\"fan\",\"state\":\"ON\"},{\"device_type\":\"pump\",\"state\":\"TIMER\",\"duration\":5},{\"device_type\":\"light\",\"state\":\"OFF\"}]"
        "}\n"
        "Данные датчиков:\n"
        f"{telemetry_russian}"
    )
    return system_prompt, user_prompt


def get_latest_data_snapshot() -> dict[str, Any]:
    latest_snapshot: dict[str, Any] = {
        "Температура": None,
        "Влажность": None,
        "Темп. воды": None,
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

    return latest_snapshot


def format_latest_data_for_prompt() -> str:
    latest_data = get_latest_data_snapshot()

    air_temp = latest_data.get("Температура")
    humidity = latest_data.get("Влажность")
    water_temp = latest_data.get("Темп. воды")

    return (
        f"Текущие показатели: Температура воздуха {format_sensor_value(air_temp, ' C')}, "
        f"Влажность {format_sensor_value(humidity, '%')}, "
        f"Температура воды {format_sensor_value(water_temp, ' C')}"
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


def normalize_commands(raw_commands: Any) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    logs: list[str] = []

    if not isinstance(raw_commands, list):
        return normalized, ["Поле commands в ответе модели имеет неверный формат."]

    for raw_command in raw_commands:
        if not isinstance(raw_command, dict):
            logs.append(f"Пропущена некорректная команда: {raw_command!r}")
            continue

        device_type = str(raw_command.get("device_type", "")).strip()
        state = str(raw_command.get("state", "")).strip().upper()

        if device_type not in KNOWN_DEVICE_TYPES:
            logs.append(f"Пропущена команда с неизвестным устройством: {raw_command!r}")
            continue

        if state not in {"ON", "OFF", "TIMER"}:
            logs.append(f"Пропущена команда с неверным состоянием: {raw_command!r}")
            continue

        command: dict[str, Any] = {
            "device_type": device_type,
            "state": state,
        }

        duration = raw_command.get("duration")
        if state == "TIMER":
            if not isinstance(duration, (int, float)) or duration <= 0:
                logs.append(f"Пропущена TIMER-команда без корректной duration: {raw_command!r}")
                continue
            command["duration"] = float(duration)

        normalized.append(command)

    return normalized, logs


def publish_ai_command(command: dict[str, Any]) -> str:
    device_type = str(command["device_type"])
    state = str(command["state"])
    topic = f"farm/tray_1/cmd/{device_type}"

    if state == "TIMER":
        duration = command["duration"]
        payload = f"TIMER {duration:g}"
        action = f"Опубликована команда: {device_type} -> TIMER {duration:g}"
    else:
        payload = state
        action = f"Опубликована команда: {device_type} -> {state}"

    app.state.mqtt_client.publish(topic, payload)
    return f"{action} в топик {topic}"


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


def print_watchdog_ai_logs(result: dict[str, Any]) -> None:
    logs = result.get("logs", [])
    if isinstance(logs, list) and logs:
        for log in logs:
            print(f"[WATCHDOG] {log}")
    else:
        print("[WATCHDOG] AI вызван, но журнал действий пуст.")


async def internal_watchdog() -> None:
    last_ai_call_ts = 0.0
    in_alert_mode = False
    loop = asyncio.get_running_loop()
    print("[WATCHDOG] Запущен внутри FastAPI. Проверка аномалий каждые 5 сек.")

    while True:
        try:
            records = await asyncio.to_thread(get_last_climate_records, 3)
            anomalies = detect_anomalies(records)

            if anomalies:
                in_alert_mode = True
                print("[WATCHDOG] Обнаружены аномалии:")
                for anomaly in anomalies:
                    print(f"[WATCHDOG] - {anomaly}")

                now = loop.time()
                cooldown_left = AI_COOLDOWN_SECONDS - (now - last_ai_call_ts)
                if cooldown_left > 0:
                    print(f"[WATCHDOG] AI не вызывается: cooldown ещё {int(cooldown_left)} сек.")
                else:
                    print("[WATCHDOG] Вызываю ai_decide() напрямую ...")
                    result = await ai_decide()
                    last_ai_call_ts = loop.time()
                    print_watchdog_ai_logs(result)
            elif in_alert_mode:
                now = loop.time()
                cooldown_left = AI_COOLDOWN_SECONDS - (now - last_ai_call_ts)
                if cooldown_left > 0:
                    print(f"[WATCHDOG] Норма восстановлена, ожидаю cooldown ещё {int(cooldown_left)} сек.")
                else:
                    print("[WATCHDOG] Ситуация нормализовалась. Запрашиваю деактивацию устройств ...")
                    result = await ai_decide()
                    last_ai_call_ts = loop.time()
                    print_watchdog_ai_logs(result)
                    in_alert_mode = False
            else:
                print("[WATCHDOG] Аномалий не обнаружено.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[WATCHDOG] Ошибка: {exc}")

        await asyncio.sleep(5)


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

    try:
        yield
    finally:
        watchdog_task.cancel()
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


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "db": "initialized"}


@app.get("/api/telemetry")
def get_telemetry() -> dict[str, Any]:
    snapshot = get_latest_data_snapshot()
    air_temp = snapshot.get("air_temp")
    humidity = snapshot.get("humidity")
    water_temp = snapshot.get("water_temp")

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
    return {
        "status": "sent",
        "target_id": request.target_id,
        "device_type": request.device_type,
        "state": request.state,
        "payload": payload,
    }


@app.post("/api/ai/decide")
async def ai_decide() -> dict[str, Any]:
    logs: list[str] = []
    telemetry_records = await asyncio.to_thread(get_recent_telemetry, 15)

    if not telemetry_records:
        return {"logs": ["В базе нет записей телеметрии."], "thought": "", "commands": []}

    try:
        system_prompt, user_prompt = build_decision_ai_request(telemetry_records)
        raw_decision = await ask_ai(system_prompt, user_prompt)
        decision = json.loads(raw_decision)
    except Exception as exc:
        return {
            "logs": [f"Не удалось получить корректное решение от AI: {exc}"],
            "thought": "",
            "commands": [],
        }

    if not isinstance(decision, dict):
        return {
            "logs": ["Модель вернула ответ не в формате JSON-объекта."],
            "thought": "",
            "commands": [],
        }

    thought = str(decision.get("thought", "")).strip()
    normalized_commands, normalization_logs = normalize_commands(decision.get("commands", []))
    logs.extend(normalization_logs)

    if thought:
        logs.insert(0, f"Мысль Нейроагронома: {thought}")
    else:
        thought = "Модель не дала пояснения."
        logs.insert(0, f"Мысль Нейроагронома: {thought}")

    await asyncio.to_thread(save_ai_log, thought, normalized_commands)

    if not normalized_commands:
        logs.append("Действия не требуются.")
        return {"logs": logs, "thought": thought, "commands": normalized_commands}

    for command in normalized_commands:
        logs.append(publish_ai_command(command))

    return {"logs": logs, "thought": thought, "commands": normalized_commands}


@app.get("/api/logs")
def get_logs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return get_recent_ai_logs(limit)


@app.post("/api/chat")
@app.post("/api/ai/chat")
async def chat_with_ai(request: ChatRequest) -> dict[str, str]:
    user_prompt = request.messages[-1]["content"]
    history = request.messages[:-1]

    try:
        reply = await ask_ai(CHAT_SYSTEM_PROMPT, user_prompt, history)
    except Exception as exc:
        return {"reply": f"Не удалось получить ответ от AI: {exc}"}

    if not reply:
        reply = "Недостаточно данных для ответа."

    return {"reply": reply}
