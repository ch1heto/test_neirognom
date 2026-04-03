import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "farm.db"
BROKER_HOST = "31.56.208.196"
BROKER_PORT = 1883
SENSORS_TOPIC = "farm/+/sensors/#"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                status TEXT,
                last_seen DATETIME
            )
            """
        )
        connection.commit()


def update_device_status(device_id: str) -> None:
    last_seen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as connection:
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


def on_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code == 0:
        client.subscribe(SENSORS_TOPIC)
    else:
        print(f"[БЭКЕНД] Ошибка подключения к MQTT: {reason_code}")


def on_message(client, userdata, msg) -> None:
    payload = msg.payload.decode("utf-8")
    parts = msg.topic.split("/")

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
