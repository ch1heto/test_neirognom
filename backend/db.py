# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

CLIMATE_TOPIC = "farm/tray_1/sensors/climate"
WATER_TOPIC = "farm/tray_1/sensors/water"


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "Не задана переменная окружения DATABASE_URL. "
            "Создайте базу PostgreSQL neirognom и добавьте DATABASE_URL в .env, например: "
            "postgresql://postgres:password@localhost:5432/neirognom"
        )
    return database_url


def get_connection():
    return psycopg.connect(get_database_url(), row_factory=dict_row)


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def get_column_data_type(cursor, table_name: str, column_name: str) -> str | None:
    cursor.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    return str(row["data_type"]) if row else None


def ensure_jsonb_column(cursor, table_name: str, column_name: str) -> None:
    if get_column_data_type(cursor, table_name, column_name) == "jsonb":
        return

    cursor.execute(
        """
        CREATE OR REPLACE FUNCTION pg_temp.safe_jsonb(value text)
        RETURNS jsonb
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN value::jsonb;
        EXCEPTION WHEN others THEN
            RETURN to_jsonb(value);
        END;
        $$;
        """
    )
    cursor.execute(
        sql.SQL("ALTER TABLE {} ALTER COLUMN {} TYPE JSONB USING pg_temp.safe_jsonb({}::text)").format(
            sql.Identifier(table_name),
            sql.Identifier(column_name),
            sql.Identifier(column_name),
        )
    )


def init_db() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    status TEXT,
                    last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_raw (
                    id BIGSERIAL PRIMARY KEY,
                    topic TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    tray_id TEXT,
                    sensor_type TEXT,
                    air_temp DOUBLE PRECISION,
                    humidity DOUBLE PRECISION,
                    water_temp DOUBLE PRECISION,
                    ph DOUBLE PRECISION,
                    ec DOUBLE PRECISION,
                    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                "ALTER TABLE telemetry_raw ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMPTZ"
            )
            if column_exists(cursor, "telemetry_raw", "created_at"):
                cursor.execute(
                    "UPDATE telemetry_raw SET recorded_at = created_at WHERE recorded_at IS NULL"
                )
            cursor.execute(
                "UPDATE telemetry_raw SET recorded_at = now() WHERE recorded_at IS NULL"
            )
            cursor.execute(
                "ALTER TABLE telemetry_raw ALTER COLUMN recorded_at SET DEFAULT now()"
            )
            cursor.execute(
                "ALTER TABLE telemetry_raw ALTER COLUMN recorded_at SET NOT NULL"
            )
            ensure_jsonb_column(cursor, "telemetry_raw", "payload")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_telemetry_raw_recorded_at ON telemetry_raw(recorded_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_telemetry_raw_topic_id ON telemetry_raw(topic, id DESC)"
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry_hourly (
                    id BIGSERIAL PRIMARY KEY,
                    tray_id TEXT,
                    sensor_type TEXT,
                    hour_start TIMESTAMPTZ NOT NULL,
                    air_temp DOUBLE PRECISION,
                    humidity DOUBLE PRECISION,
                    water_temp DOUBLE PRECISION,
                    ph DOUBLE PRECISION,
                    ec DOUBLE PRECISION,
                    air_temp_avg DOUBLE PRECISION,
                    air_temp_min DOUBLE PRECISION,
                    air_temp_max DOUBLE PRECISION,
                    air_temp_count INTEGER NOT NULL DEFAULT 0,
                    humidity_avg DOUBLE PRECISION,
                    humidity_min DOUBLE PRECISION,
                    humidity_max DOUBLE PRECISION,
                    humidity_count INTEGER NOT NULL DEFAULT 0,
                    water_temp_avg DOUBLE PRECISION,
                    water_temp_min DOUBLE PRECISION,
                    water_temp_max DOUBLE PRECISION,
                    water_temp_count INTEGER NOT NULL DEFAULT 0,
                    ph_avg DOUBLE PRECISION,
                    ph_min DOUBLE PRECISION,
                    ph_max DOUBLE PRECISION,
                    ph_count INTEGER NOT NULL DEFAULT 0,
                    ec_avg DOUBLE PRECISION,
                    ec_min DOUBLE PRECISION,
                    ec_max DOUBLE PRECISION,
                    ec_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            for metric_name in ("air_temp", "humidity", "water_temp", "ph", "ec"):
                cursor.execute(
                    f"ALTER TABLE telemetry_hourly ADD COLUMN IF NOT EXISTS {metric_name}_avg DOUBLE PRECISION"
                )
                cursor.execute(
                    f"ALTER TABLE telemetry_hourly ADD COLUMN IF NOT EXISTS {metric_name}_min DOUBLE PRECISION"
                )
                cursor.execute(
                    f"ALTER TABLE telemetry_hourly ADD COLUMN IF NOT EXISTS {metric_name}_max DOUBLE PRECISION"
                )
                cursor.execute(
                    f"ALTER TABLE telemetry_hourly ADD COLUMN IF NOT EXISTS {metric_name}_count INTEGER NOT NULL DEFAULT 0"
                )
            cursor.execute(
                "ALTER TABLE telemetry_hourly ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            )
            cursor.execute(
                "UPDATE telemetry_hourly SET sensor_type = 'mixed' WHERE sensor_type IS NULL"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_hour_start ON telemetry_hourly(hour_start)"
            )
            cursor.execute(
                """
                DROP INDEX IF EXISTS idx_telemetry_hourly_tray_hour
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_telemetry_hourly_tray_sensor_hour
                ON telemetry_hourly(tray_id, sensor_type, hour_start)
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS anomaly_events (
                    id BIGSERIAL PRIMARY KEY,
                    tray_id TEXT,
                    sensor_type TEXT,
                    event_type TEXT,
                    metric_name TEXT,
                    severity TEXT,
                    value DOUBLE PRECISION,
                    message TEXT,
                    payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                "ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS metric_name TEXT"
            )
            cursor.execute(
                "ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS value DOUBLE PRECISION"
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anomaly_events_recent
                ON anomaly_events(tray_id, event_type, metric_name, created_at DESC)
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS advisor_reports (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_logs (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                    thought TEXT,
                    commands_json JSONB
                )
                """
            )
            ensure_jsonb_column(cursor, "ai_logs", "commands_json")


def parse_json_value(payload: Any) -> Any:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return payload


def parse_json_payload(payload: Any) -> dict[str, Any] | None:
    parsed = parse_json_value(payload)
    return parsed if isinstance(parsed, dict) else None


def json_value_to_api_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def parse_topic(topic: str) -> tuple[str | None, str | None]:
    parts = topic.split("/")
    tray_id = parts[1] if len(parts) > 1 else None
    sensor_type = None
    if "sensors" in parts:
        sensor_index = parts.index("sensors")
        if len(parts) > sensor_index + 1:
            sensor_type = parts[sensor_index + 1]
    return tray_id, sensor_type


def number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def format_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value) if value is not None else ""


def update_device_status(device_id: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO devices (id, status, last_seen)
                VALUES (%s, %s, now())
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_seen = EXCLUDED.last_seen
                """,
                (device_id, "online"),
            )


def save_telemetry(topic: str, payload: str, recorded_at: datetime | None = None) -> None:
    parsed_value = parse_json_value(payload)
    parsed_payload = parsed_value if isinstance(parsed_value, dict) else {}
    tray_id, sensor_type = parse_topic(topic)
    timestamp_sql = "%s" if recorded_at is not None else "now()"
    params: list[Any] = [
        topic,
        Jsonb(parsed_value),
        tray_id,
        sensor_type,
        number_or_none(parsed_payload.get("air_temp")),
        number_or_none(parsed_payload.get("humidity")),
        number_or_none(parsed_payload.get("water_temp")),
        number_or_none(parsed_payload.get("ph", parsed_payload.get("pH"))),
        number_or_none(parsed_payload.get("ec", parsed_payload.get("EC"))),
    ]
    if recorded_at is not None:
        params.append(recorded_at)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO telemetry_raw (
                    topic, payload, tray_id, sensor_type,
                    air_temp, humidity, water_temp, ph, ec, recorded_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, {timestamp_sql})
                """,
                params,
            )


def save_ai_log(thought: str, commands: Any) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_logs (timestamp, thought, commands_json)
                VALUES (now(), %s, %s)
                """,
                (thought, Jsonb(commands)),
            )


def row_to_telemetry_record(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    payload_string = json_value_to_api_string(payload)
    record = {
        "id": row["id"],
        "topic": row["topic"],
        "payload": payload_string,
        "timestamp": format_timestamp(row["recorded_at"]),
    }
    record["parsed_payload"] = parse_json_payload(payload)
    return record


def get_recent_telemetry(limit: int = 15) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, topic, payload, recorded_at
                FROM telemetry_raw
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

    return [row_to_telemetry_record(row) for row in reversed(rows)]


def get_last_climate_records(limit: int = 3) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, topic, payload, recorded_at
                FROM telemetry_raw
                WHERE topic = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (CLIMATE_TOPIC, limit),
            )
            rows = cursor.fetchall()

    records: list[dict[str, Any]] = []
    for row in reversed(rows):
        record = row_to_telemetry_record(row)
        if isinstance(record.get("parsed_payload"), dict):
            records.append(record)
    return records


def get_recent_ai_logs(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, timestamp, thought, commands_json
                FROM ai_logs
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "timestamp": format_timestamp(row["timestamp"]),
            "thought": row["thought"],
            "commands_json": json_value_to_api_string(row["commands_json"]),
        }
        for row in rows
    ]


def get_current_metrics() -> dict[str, Any]:
    result: dict[str, Any] = {
        "temperature": None,
        "humidity": None,
        "water_temp": None,
        "ph": None,
        "ec": None,
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT air_temp, humidity
                FROM telemetry_raw
                WHERE topic = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (CLIMATE_TOPIC,),
            )
            climate_row = cursor.fetchone()
            if climate_row:
                result["temperature"] = climate_row["air_temp"]
                result["humidity"] = climate_row["humidity"]

            cursor.execute(
                """
                SELECT water_temp
                FROM telemetry_raw
                WHERE topic = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (WATER_TOPIC,),
            )
            water_row = cursor.fetchone()
            if water_row:
                result["water_temp"] = water_row["water_temp"]

            cursor.execute(
                """
                SELECT ph
                FROM telemetry_raw
                WHERE ph IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """
            )
            ph_row = cursor.fetchone()
            if ph_row:
                result["ph"] = ph_row["ph"]

            cursor.execute(
                """
                SELECT ec
                FROM telemetry_raw
                WHERE ec IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """
            )
            ec_row = cursor.fetchone()
            if ec_row:
                result["ec"] = ec_row["ec"]

    return result


def get_hourly_history(metric_name: str, hours: int = 24) -> list[dict[str, Any]]:
    metric_config = {
        "temperature": "air_temp_avg",
        "humidity": "humidity_avg",
        "water_temp": "water_temp_avg",
        "ph": "ph_avg",
        "ec": "ec_avg",
    }
    if metric_name not in metric_config:
        raise ValueError(f"Unknown metric: {metric_name}")

    column_name = metric_config[metric_name]
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT hour_start, ROUND({column_name}::numeric, 2) AS avg_value
                FROM telemetry_hourly
                WHERE hour_start >= now() - (%s * interval '1 hour')
                  AND {column_name} IS NOT NULL
                ORDER BY hour_start ASC
                """,
                (hours,),
            )
            rows = cursor.fetchall()

    return [
        {
            "hour": format_timestamp(row["hour_start"])[:13] + ":00",
            "avg_value": float(row["avg_value"]) if row["avg_value"] is not None else None,
        }
        for row in rows
    ]


def aggregate_completed_hours() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH completed_hours AS (
                    SELECT
                        COALESCE(tray_id, 'unknown') AS tray_id,
                        COALESCE(sensor_type, 'unknown') AS sensor_type,
                        date_trunc('hour', recorded_at) AS hour_start,
                        AVG(air_temp) AS air_temp_avg,
                        MIN(air_temp) AS air_temp_min,
                        MAX(air_temp) AS air_temp_max,
                        COUNT(air_temp)::integer AS air_temp_count,
                        AVG(humidity) AS humidity_avg,
                        MIN(humidity) AS humidity_min,
                        MAX(humidity) AS humidity_max,
                        COUNT(humidity)::integer AS humidity_count,
                        AVG(water_temp) AS water_temp_avg,
                        MIN(water_temp) AS water_temp_min,
                        MAX(water_temp) AS water_temp_max,
                        COUNT(water_temp)::integer AS water_temp_count,
                        AVG(ph) AS ph_avg,
                        MIN(ph) AS ph_min,
                        MAX(ph) AS ph_max,
                        COUNT(ph)::integer AS ph_count,
                        AVG(ec) AS ec_avg,
                        MIN(ec) AS ec_min,
                        MAX(ec) AS ec_max,
                        COUNT(ec)::integer AS ec_count
                    FROM telemetry_raw
                    WHERE recorded_at < date_trunc('hour', now())
                    GROUP BY
                        COALESCE(tray_id, 'unknown'),
                        COALESCE(sensor_type, 'unknown'),
                        date_trunc('hour', recorded_at)
                ),
                missing_hours AS (
                    SELECT completed_hours.*
                    FROM completed_hours
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM telemetry_hourly
                        WHERE telemetry_hourly.tray_id = completed_hours.tray_id
                          AND telemetry_hourly.sensor_type = completed_hours.sensor_type
                          AND telemetry_hourly.hour_start = completed_hours.hour_start
                    )
                )
                INSERT INTO telemetry_hourly (
                    tray_id, sensor_type, hour_start,
                    air_temp, humidity, water_temp, ph, ec,
                    air_temp_avg, air_temp_min, air_temp_max, air_temp_count,
                    humidity_avg, humidity_min, humidity_max, humidity_count,
                    water_temp_avg, water_temp_min, water_temp_max, water_temp_count,
                    ph_avg, ph_min, ph_max, ph_count,
                    ec_avg, ec_min, ec_max, ec_count,
                    updated_at
                )
                SELECT
                    tray_id, sensor_type, hour_start,
                    air_temp_avg, humidity_avg, water_temp_avg, ph_avg, ec_avg,
                    air_temp_avg, air_temp_min, air_temp_max, air_temp_count,
                    humidity_avg, humidity_min, humidity_max, humidity_count,
                    water_temp_avg, water_temp_min, water_temp_max, water_temp_count,
                    ph_avg, ph_min, ph_max, ph_count,
                    ec_avg, ec_min, ec_max, ec_count,
                    now()
                FROM missing_hours
                ON CONFLICT (tray_id, sensor_type, hour_start) DO UPDATE SET
                    air_temp = EXCLUDED.air_temp,
                    humidity = EXCLUDED.humidity,
                    water_temp = EXCLUDED.water_temp,
                    ph = EXCLUDED.ph,
                    ec = EXCLUDED.ec,
                    air_temp_avg = EXCLUDED.air_temp_avg,
                    air_temp_min = EXCLUDED.air_temp_min,
                    air_temp_max = EXCLUDED.air_temp_max,
                    air_temp_count = EXCLUDED.air_temp_count,
                    humidity_avg = EXCLUDED.humidity_avg,
                    humidity_min = EXCLUDED.humidity_min,
                    humidity_max = EXCLUDED.humidity_max,
                    humidity_count = EXCLUDED.humidity_count,
                    water_temp_avg = EXCLUDED.water_temp_avg,
                    water_temp_min = EXCLUDED.water_temp_min,
                    water_temp_max = EXCLUDED.water_temp_max,
                    water_temp_count = EXCLUDED.water_temp_count,
                    ph_avg = EXCLUDED.ph_avg,
                    ph_min = EXCLUDED.ph_min,
                    ph_max = EXCLUDED.ph_max,
                    ph_count = EXCLUDED.ph_count,
                    ec_avg = EXCLUDED.ec_avg,
                    ec_min = EXCLUDED.ec_min,
                    ec_max = EXCLUDED.ec_max,
                    ec_count = EXCLUDED.ec_count,
                    updated_at = now()
                RETURNING id
                """
            )
            return len(cursor.fetchall())


def delete_old_raw_data(retention_hours: int = 24) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM telemetry_raw
                WHERE recorded_at < now() - (%s * interval '1 hour')
                  AND EXISTS (
                      SELECT 1
                      FROM telemetry_hourly
                      WHERE telemetry_hourly.tray_id = COALESCE(telemetry_raw.tray_id, 'unknown')
                        AND telemetry_hourly.sensor_type = COALESCE(telemetry_raw.sensor_type, 'unknown')
                        AND telemetry_hourly.hour_start = date_trunc('hour', telemetry_raw.recorded_at)
                  )
                RETURNING id
                """,
                (retention_hours,),
            )
            return len(cursor.fetchall())


def save_anomaly_event(
    *,
    tray_id: str | None,
    metric_name: str,
    severity: str,
    value: float | None,
    message: str,
    event_type: str,
    sensor_type: str | None = None,
    payload: dict[str, Any] | None = None,
    cooldown_minutes: int = 5,
) -> bool:
    normalized_tray_id = tray_id or "unknown"
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH recent_duplicate AS (
                    SELECT 1
                    FROM anomaly_events
                    WHERE tray_id = %s
                      AND event_type = %s
                      AND metric_name = %s
                      AND created_at >= now() - (%s * interval '1 minute')
                    LIMIT 1
                )
                INSERT INTO anomaly_events (
                    tray_id, sensor_type, event_type, metric_name,
                    severity, value, message, payload, created_at
                )
                SELECT %s, %s, %s, %s, %s, %s, %s, %s, now()
                WHERE NOT EXISTS (SELECT 1 FROM recent_duplicate)
                RETURNING id
                """,
                (
                    normalized_tray_id,
                    event_type,
                    metric_name,
                    cooldown_minutes,
                    normalized_tray_id,
                    sensor_type,
                    event_type,
                    metric_name,
                    severity,
                    value,
                    message,
                    Jsonb(payload or {}),
                ),
            )
            return cursor.fetchone() is not None


def get_recent_anomaly_events(hours: int = 24) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id, tray_id, sensor_type, event_type, metric_name,
                    severity, value, message, payload, created_at
                FROM anomaly_events
                WHERE created_at >= now() - (%s * interval '1 hour')
                ORDER BY created_at DESC, id DESC
                """,
                (hours,),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "tray_id": row["tray_id"],
            "sensor_type": row["sensor_type"],
            "event_type": row["event_type"],
            "metric_name": row["metric_name"],
            "severity": row["severity"],
            "value": row["value"],
            "message": row["message"],
            "payload": row["payload"],
            "created_at": format_timestamp(row["created_at"]),
        }
        for row in rows
    ]


def get_recent_hourly_summary(hours: int = 24) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    tray_id, sensor_type, hour_start,
                    air_temp_avg, air_temp_min, air_temp_max, air_temp_count,
                    humidity_avg, humidity_min, humidity_max, humidity_count,
                    water_temp_avg, water_temp_min, water_temp_max, water_temp_count,
                    ph_avg, ph_min, ph_max, ph_count,
                    ec_avg, ec_min, ec_max, ec_count
                FROM telemetry_hourly
                WHERE hour_start >= now() - (%s * interval '1 hour')
                ORDER BY hour_start ASC
                """,
                (hours,),
            )
            rows = cursor.fetchall()

    return [
        {
            **row,
            "hour_start": format_timestamp(row["hour_start"]),
        }
        for row in rows
    ]


def clear_telemetry_raw() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM telemetry_raw")
