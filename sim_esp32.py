import json
import random
import time
import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
DEVICE_ID = "tray_1"
COMMANDS_TOPIC = "farm/tray_1/cmd/#"
CONTROL_TOPIC = "farm/sim/control"
CLIMATE_TOPIC = "farm/tray_1/sensors/climate"
WATER_TOPIC = "farm/tray_1/sensors/water"
current_mode = "NORMAL"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(COMMANDS_TOPIC)
        client.subscribe(CONTROL_TOPIC)
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

    print(f"[СИМУЛЯТОР] Получена команда {msg.topic}: {payload}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
client.on_connect = on_connect
client.on_message = on_message

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

    print(f"[СИМУЛЯТОР] Отправлены climate: {climate_payload}")
    print(f"[СИМУЛЯТОР] Отправлены water: {water_payload}")
    time.sleep(1)
