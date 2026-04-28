import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
BROKER_USERNAME = os.getenv("BROKER_USERNAME", "").strip()
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD", "")
DEVICE_ID = "tray_1"
COMMANDS_TOPIC = "farm/tray_1/cmd/#"
CONTROL_TOPIC = "farm/sim/control"
CLIMATE_TOPIC = "farm/tray_1/sensors/climate"
WATER_TOPIC = "farm/tray_1/sensors/water"
DEVICE_STATUS_TOPIC = "farm/tray_1/status/devices"
AVAILABILITY_TOPIC = "farm/tray_1/status/availability"
current_mode = "NORMAL"
device_states = {
    "pump": False,
    "light": False,
    "fan": False,
    "humidifier": False,
}
day_scenario = {
    "running": False,
    "start_at_ms": None,
    "duration_ms": 15_000,
}


def now_ms() -> int:
    return int(time.time() * 1000)


def publish_device_status() -> None:
    start_at_ms = day_scenario["start_at_ms"]
    duration_ms = int(day_scenario["duration_ms"])
    running = bool(day_scenario["running"])
    stage = 9

    if running and isinstance(start_at_ms, int):
        elapsed = now_ms() - start_at_ms
        if elapsed >= duration_ms:
            running = False
            day_scenario["running"] = False
            device_states["light"] = False
        elif elapsed >= 0:
            stage = min(9, int((elapsed / duration_ms) * 9))
        else:
            stage = 0

    payload = json.dumps(
        {
            **device_states,
            "day_scenario_running": running,
            "day_scenario_pending": running and isinstance(start_at_ms, int) and now_ms() < start_at_ms,
            "day_stage": stage,
            "day_start_at_ms": start_at_ms,
            "day_duration_ms": duration_ms,
            "uptime_ms": int(time.monotonic() * 1000),
        }
    )
    client.publish(DEVICE_STATUS_TOPIC, payload, retain=True)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(COMMANDS_TOPIC)
        client.subscribe(CONTROL_TOPIC)
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        publish_device_status()
    else:
        print(f"[СИМУЛЯТОР] Ошибка подключения: {reason_code}")


def on_message(client, userdata, msg):
    global current_mode

    payload = msg.payload.decode("utf-8")

    if msg.topic == CONTROL_TOPIC:
        next_mode = payload.strip().upper()
        if next_mode in {"HEAT", "COLD", "NORMAL"}:
            current_mode = next_mode
            print(f"[СИМУЛЯТОР] Переключение режима: {current_mode}")
        else:
            print(f"[СИМУЛЯТОР] Неизвестный режим: {payload}")
        return

    parts = msg.topic.split("/")
    device_type = parts[-1] if parts else ""

    try:
        parsed_payload = json.loads(payload)
    except json.JSONDecodeError:
        parsed_payload = None

    if device_type == "light" and isinstance(parsed_payload, dict):
        command = str(parsed_payload.get("command", "")).upper()
        if command in {"DAY", "DAY_SCENARIO"}:
            day_scenario["running"] = True
            day_scenario["start_at_ms"] = int(parsed_payload.get("start_at_ms") or now_ms())
            day_scenario["duration_ms"] = int(parsed_payload.get("duration_ms") or 15_000)
            device_states["light"] = True
            publish_device_status()
            print(f"[СИМУЛЯТОР] Запущен световой день: {payload}")
            return

    normalized_payload = payload.strip().upper()
    if device_type in device_states:
        if normalized_payload == "ON":
            device_states[device_type] = True
            if device_type == "light":
                day_scenario["running"] = False
        elif normalized_payload == "OFF":
            device_states[device_type] = False
            if device_type == "light":
                day_scenario["running"] = False
        elif normalized_payload.startswith("TIMER "):
            device_states[device_type] = True
        elif device_type == "light" and normalized_payload in {"DAY", "DAY_SCENARIO"}:
            day_scenario["running"] = True
            day_scenario["start_at_ms"] = now_ms()
            day_scenario["duration_ms"] = 15_000
            device_states["light"] = True
        publish_device_status()

    print(f"[СИМУЛЯТОР] Получена команда {msg.topic}: {payload}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
client.on_connect = on_connect
client.on_message = on_message
if BROKER_USERNAME:
    client.username_pw_set(BROKER_USERNAME, BROKER_PASSWORD or None)

client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_start()

while True:
    if current_mode == "HEAT":
        air_temp = 35.5
        humidity = 30.0
        water_temp = round(random.uniform(20.0, 20.8), 1)
    elif current_mode == "COLD":
        air_temp = 12.0
        humidity = round(random.uniform(48.0, 52.0), 1)
        water_temp = round(random.uniform(19.0, 20.0), 1)
    else:
        air_temp = round(random.uniform(22.0, 24.0), 1)
        humidity = round(random.uniform(52.0, 60.0), 1)
        water_temp = round(random.uniform(19.6, 20.4), 1)

    climate_payload = json.dumps(
        {
            "air_temp": air_temp,
            "humidity": humidity,
        }
    )
    water_payload = json.dumps(
        {
            "water_temp": water_temp,
        }
    )

    client.publish(CLIMATE_TOPIC, climate_payload, retain=True)
    client.publish(WATER_TOPIC, water_payload, retain=True)
    publish_device_status()

    print(f"[СИМУЛЯТОР] Отправлены climate: {climate_payload}")
    print(f"[СИМУЛЯТОР] Отправлены water: {water_payload}")
    time.sleep(1)
