# -*- coding: utf-8 -*-
import json
import random
from datetime import datetime, timedelta

from db import clear_telemetry_raw, init_db, save_telemetry


def seed_database() -> None:
    print("Подключаемся к PostgreSQL через DATABASE_URL...")
    init_db()
    clear_telemetry_raw()

    now = datetime.now()
    print("Генерируем данные за 7 дней (168 часов)...")

    for i in range(168, -1, -1):
        record_time = now - timedelta(hours=i)

        temp = round(random.uniform(22.0, 25.0), 1)
        hum = round(random.uniform(60.0, 75.0), 1)
        water_temp = round(random.uniform(18.0, 21.0), 1)

        if 48 <= i <= 72:
            temp = round(random.uniform(29.0, 33.0), 1)
            hum = round(random.uniform(40.0, 45.0), 1)

        if 12 <= i <= 24:
            water_temp = round(random.uniform(14.0, 16.0), 1)

        climate_payload = json.dumps({"air_temp": temp, "humidity": hum})
        water_payload = json.dumps({"water_temp": water_temp})

        save_telemetry("farm/tray_1/sensors/climate", climate_payload, record_time)
        save_telemetry("farm/tray_1/sensors/water", water_payload, record_time)

    print("Готово: telemetry_raw заполнена тестовыми данными.")


if __name__ == "__main__":
    seed_database()
