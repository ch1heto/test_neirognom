import json
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "backend" / "farm.db"
AI_DECIDE_URL = "http://127.0.0.1:8000/api/ai/decide"
POLL_INTERVAL_SECONDS = 10
AI_COOLDOWN_SECONDS = 60


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


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
        try:
            parsed_payload = json.loads(str(record["payload"]))
        except json.JSONDecodeError:
            parsed_payload = {}
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

    if isinstance(air_temp, (int, float)) and air_temp > 32:
        anomalies.append(f"Критический перегрев: air_temp={air_temp}")

    if isinstance(air_temp, (int, float)) and air_temp < 18:
        anomalies.append("Критическое переохлаждение: air_temp=" + str(air_temp))

    if isinstance(humidity, (int, float)) and humidity < 30:
        anomalies.append(f"Критическая засуха: humidity={humidity}")

    if len(records) >= 3:
        first_payload = records[0].get("parsed_payload", {})
        last_payload = records[-1].get("parsed_payload", {})
        if isinstance(first_payload, dict) and isinstance(last_payload, dict):
            first_temp = first_payload.get("air_temp")
            last_temp = last_payload.get("air_temp")
            if isinstance(first_temp, (int, float)) and isinstance(last_temp, (int, float)):
                if last_temp - first_temp > 3:
                    anomalies.append(
                        "Быстрый рост температуры воздуха: "
                        f"{first_temp} -> {last_temp} за последние 3 замера"
                    )
                if first_temp - last_temp > 3:
                    anomalies.append(
                        "Быстрое падение температуры: " + str(first_temp) + " -> " + str(last_temp)
                    )

    return anomalies


def call_ai_decide() -> dict[str, Any]:
    request = urllib.request.Request(
        AI_DECIDE_URL,
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=40) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    last_ai_call_ts = 0.0
    print("[WATCHDOG] Запущен. Проверка аномалий каждые 10 секунд.")

    while True:
        try:
            records = get_last_climate_records(3)
            anomalies = detect_anomalies(records)

            if anomalies:
                print("[WATCHDOG] Обнаружены аномалии:")
                for anomaly in anomalies:
                    print(f"[WATCHDOG] - {anomaly}")

                now = time.time()
                cooldown_left = AI_COOLDOWN_SECONDS - (now - last_ai_call_ts)
                if cooldown_left > 0:
                    print(
                        "[WATCHDOG] AI не вызывается: активен cooldown "
                        f"ещё {int(cooldown_left)} сек."
                    )
                else:
                    print("[WATCHDOG] Вызываю /api/ai/decide ...")
                    result = call_ai_decide()
                    last_ai_call_ts = now
                    logs = result.get("logs", [])
                    if isinstance(logs, list) and logs:
                        for log in logs:
                            print(f"[WATCHDOG] {log}")
                    else:
                        print("[WATCHDOG] AI вызван, но журнал действий пуст.")
            else:
                print("[WATCHDOG] Аномалий не обнаружено.")
        except Exception as exc:
            print(f"[WATCHDOG] Ошибка: {exc}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
