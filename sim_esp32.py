import json
import random
import time

import paho.mqtt.client as mqtt


BROKER_HOST = "31.56.208.196"
BROKER_PORT = 1883
DEVICE_ID = "tray_1"
COMMANDS_TOPIC = "farm/tray_1/cmd/#"
CLIMATE_TOPIC = "farm/tray_1/sensors/climate"
WATER_TOPIC = "farm/tray_1/sensors/water"
SOIL_TOPIC = "farm/tray_1/sensors/soil"


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(COMMANDS_TOPIC)
    else:
        print(f"[СИМУЛЯТОР] Ошибка подключения: {reason_code}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    print(f"[СИМУЛЯТОР] Получена команда {msg.topic}: {payload}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_start()

while True:
    climate_payload = json.dumps(
        {
            "air_temp": round(random.uniform(20.0, 25.0), 1),
            "humidity": round(random.uniform(45.0, 65.0), 1),
            "lux": random.randint(3000, 5000),
        }
    )
    water_payload = json.dumps(
        {
            "water_temp": round(random.uniform(20.0, 22.0), 1),
            "distance_cm": random.randint(40, 50),
        }
    )
    soil_payload = json.dumps(
        {
            "moisture_percent": random.randint(55, 65),
        }
    )

    client.publish(CLIMATE_TOPIC, climate_payload, retain=True)
    client.publish(WATER_TOPIC, water_payload, retain=True)
    client.publish(SOIL_TOPIC, soil_payload, retain=True)

    print(f"[СИМУЛЯТОР] Отправлены данные: {climate_payload}")
    print(f"[СИМУЛЯТОР] Отправлены данные: {water_payload}")
    print(f"[СИМУЛЯТОР] Отправлены данные: {soil_payload}")
    time.sleep(5)
