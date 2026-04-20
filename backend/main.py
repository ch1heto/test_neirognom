import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
import urllib.request

import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "farm.db"
BROKER_HOST = "31.56.208.196"
BROKER_PORT = 1883
SENSORS_TOPIC = "farm/+/sensors/#"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"


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
        connection.commit()


def update_device_status(device_id: str) -> None:
    last_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO telemetry (topic, payload, timestamp)
            VALUES (?, ?, ?)
            """,
            (topic, payload, timestamp),
        )
        connection.commit()


def get_recent_telemetry(limit: int = 15) -> list[dict[str, object]]:
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

    return [dict(row) for row in reversed(rows)]


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


def build_neuroagronom_prompt(records: list[dict[str, object]]) -> str:
    telemetry_json = json.dumps(records, ensure_ascii=False, indent=2)
    return (
        "You are Neuroagronom controlling a city farm.\n"
        "Analyze the telemetry and decide which devices must be turned on.\n"
        "Rules:\n"
        "1. If air_temp > 25, turn ON fan.\n"
        "2. If moisture < 60, turn ON pump.\n"
        "Return only JSON with these keys:\n"
        '- "thought": string\n'
        '- "commands": array of objects with "device_type" and "state"\n'
        'Example: {"thought": "Short reason", "commands": [{"device_type": "fan", "state": "ON"}]}\n'
        "If no action is needed, return an empty commands array.\n"
        "Telemetry records:\n"
        f"{telemetry_json}"
    )


def on_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code == 0:
        client.subscribe(SENSORS_TOPIC)
    else:
        print(f"[БЭКЕНД] Ошибка подключения к MQTT: {reason_code}")


def on_message(client, userdata, msg) -> None:
    payload = msg.payload.decode("utf-8")
    parts = msg.topic.split("/")

    if "sensors" in msg.topic:
        save_telemetry(msg.topic, payload)

    if len(parts) >= 3:
        device_id = parts[1]
        update_device_status(device_id)
        print(f"[БЭКЕНД] Данные от {device_id}: {payload}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="backend_service")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
    mqtt_client.loop_start()

    app.state.mqtt_client = mqtt_client

    try:
        yield
    finally:
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
    device_type: str
    state: Literal["ON", "OFF", "TIMER"]
    duration: float | None = None


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "db": "initialized"}


@app.post("/api/device/control")
def control_device(request: DeviceControlRequest) -> dict[str, str]:
    topic = f"farm/{request.target_id}/cmd/{request.device_type}"
    payload = request.state

    if request.state == "TIMER" and request.duration is not None:
        payload = f"TIMER {request.duration}"

    app.state.mqtt_client.publish(topic, payload)
    return {
        "status": "sent",
        "target_id": request.target_id,
        "device_type": request.device_type,
        "state": request.state,
        "payload": payload,
    }


@app.post("/api/ai/decide")
def ai_decide() -> dict[str, list[str]]:
    logs: list[str] = []
    records = get_recent_telemetry(15)

    if not records:
        return {"logs": ["No telemetry records found in the database."]}

    prompt = build_neuroagronom_prompt(records)
    request_payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    try:
        request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=40) as response:
            response_body = response.read().decode("utf-8")

        ollama_response = json.loads(response_body)
        raw_ai_text = ollama_response.get("response", "")
        cleaned_ai_text = strip_markdown_backticks(raw_ai_text)
        decision = json.loads(cleaned_ai_text)
    except Exception as exc:
        return {"logs": [f"Failed to get a valid AI decision from Ollama: {exc}"]}

    if not isinstance(decision, dict):
        return {"logs": ["AI response was not a JSON object."]}

    thought = str(decision.get("thought", "")).strip()
    commands = decision.get("commands", [])

    if thought:
        logs.append(f"AI thought: {thought}")
    else:
        logs.append("AI thought: no explanation provided.")

    if not isinstance(commands, list):
        return {"logs": logs + ["AI response contained invalid commands data."]}

    if not commands:
        logs.append("AI action: no commands generated.")
        return {"logs": logs}

    for command in commands:
        if not isinstance(command, dict):
            logs.append(f"Skipped invalid command payload: {command!r}")
            continue

        device_type = str(command.get("device_type", "")).strip()
        state = str(command.get("state", "")).strip()

        if not device_type or not state:
            logs.append(f"Skipped incomplete command: {command!r}")
            continue

        topic = f"farm/tray_1/cmd/{device_type}"
        app.state.mqtt_client.publish(topic, state)
        logs.append(f"Published command: {device_type} -> {state} on topic {topic}")

    return {"logs": logs}
