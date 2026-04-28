# -*- coding: utf-8 -*-
import json
import os
import re
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
CROPS_DATA_DIR = BASE_DIR / "crops_data"
AGROTECH_NORM_KEYS = (
    "air_temp",
    "humidity",
    "water_temp",
    "ph",
    "ec",
    "light_hours",
    "light_intensity",
)
BASE_CATALOG_ITEMS = (
    ("metric", "air_temp", "Температура воздуха", "C"),
    ("metric", "humidity", "Влажность воздуха", "%"),
    ("metric", "water_temp", "Температура воды", "C"),
    ("metric", "ph", "pH", None),
    ("metric", "ec", "EC", "mS/cm"),
    ("metric", "light_hours", "Длительность освещения", "h"),
    ("metric", "light_intensity", "Интенсивность освещения", None),
    ("device_type", "pump", "Насос", None),
    ("device_type", "light", "Свет", None),
    ("device_type", "fan", "Вентиляция", None),
    ("device_type", "sensor", "Датчик", None),
    ("event_type", "manual_on", "Ручное включение", None),
    ("event_type", "manual_off", "Ручное выключение", None),
    ("event_type", "manual_toggle", "Ручное переключение", None),
    ("event_type", "status_update", "Обновление статуса", None),
    ("sensor_type", "climate", "Климат", None),
    ("sensor_type", "water", "Вода", None),
    ("sensor_type", "mixed", "Смешанные данные", None),
    ("severity", "info", "Информация", None),
    ("severity", "warning", "Предупреждение", None),
    ("severity", "critical", "Критично", None),
    ("anomaly_type", "air_overheat", "Перегрев воздуха", None),
    ("anomaly_type", "air_overcooling", "Переохлаждение воздуха", None),
    ("anomaly_type", "low_humidity", "Низкая влажность", None),
    ("anomaly_type", "high_humidity", "Высокая влажность", None),
    ("anomaly_type", "rapid_air_temp_rise", "Быстрый рост температуры воздуха", None),
    ("anomaly_type", "low_ph", "pH ниже нормы", None),
    ("anomaly_type", "high_ph", "pH выше нормы", None),
    ("anomaly_type", "ph_low", "pH ниже нормы", None),
    ("anomaly_type", "ph_high", "pH выше нормы", None),
    ("anomaly_type", "low_ec", "EC ниже нормы", None),
    ("anomaly_type", "high_ec", "EC выше нормы", None),
    ("anomaly_type", "ec_low", "EC ниже нормы", None),
    ("anomaly_type", "ec_high", "EC выше нормы", None),
    ("anomaly_type", "water_overheat", "Перегрев воды", None),
    ("anomaly_type", "water_overcooling", "Переохлаждение воды", None),
    ("anomaly_type", "stale_sensor_data", "Данные датчиков устарели", None),
    ("anomaly_type", "stale_climate_data", "Данные климатических датчиков устарели", None),
    ("anomaly_type", "stale_water_data", "Данные водных датчиков устарели", None),
    ("anomaly_type", "predicted_ph_low", "Прогноз снижения pH ниже нормы", None),
    ("anomaly_type", "predicted_ph_high", "Прогноз роста pH выше нормы", None),
    ("anomaly_type", "predicted_ec_low", "Прогноз снижения EC ниже нормы", None),
    ("anomaly_type", "predicted_ec_high", "Прогноз роста EC выше нормы", None),
    ("anomaly_type", "predicted_water_temp_low", "Прогноз снижения температуры воды ниже нормы", None),
    ("anomaly_type", "predicted_water_temp_high", "Прогноз роста температуры воды выше нормы", None),
    ("anomaly_type", "predicted_air_temp_low", "Прогноз снижения температуры воздуха ниже нормы", None),
    ("anomaly_type", "predicted_air_temp_high", "Прогноз роста температуры воздуха выше нормы", None),
    ("anomaly_type", "predicted_humidity_low", "Прогноз снижения влажности ниже нормы", None),
    ("anomaly_type", "predicted_humidity_high", "Прогноз роста влажности выше нормы", None),
)
BASE_CATALOG_ITEM_BY_CODE = {item[1]: item for item in BASE_CATALOG_ITEMS}
NON_CROP_CARD_FILES = {"crops_index.md", "project_recommendations.md"}
DEFAULT_TRAY_ID = "tray_1"


class CropNotFoundError(ValueError):
    pass


class ActiveCardRevisionNotFoundError(ValueError):
    pass


class ActiveGrowingCycleExistsError(ValueError):
    pass


class NoActiveGrowingCycleError(ValueError):
    pass


class GrowingCycleNotFoundError(ValueError):
    pass


class GrowingCycleNotFinishedError(ValueError):
    pass


class InvalidCycleResultError(ValueError):
    pass


class AdvisorReportNotFoundError(ValueError):
    pass


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


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = %s
        """,
        (table_name,),
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


TRAY_FK_CONSTRAINTS = (
    ("anomaly_events", "fk_anomaly_events_tray_id_trays", "tray_id", "trays", "id"),
)


def normalize_device_id(device_id: Any) -> str | None:
    if device_id is None:
        return None
    normalized = str(device_id).strip()
    return normalized or None


def ensure_trays_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trays (
            id TEXT PRIMARY KEY,
            name TEXT,
            location TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def ensure_tray(cursor, tray_id: Any = DEFAULT_TRAY_ID) -> str:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID
    cursor.execute(
        """
        INSERT INTO trays (id)
        VALUES (%s)
        ON CONFLICT (id) DO NOTHING
        """,
        (normalized_tray_id,),
    )
    return normalized_tray_id


def looks_like_tray_id(device_id: str | None) -> bool:
    return bool(device_id and re.fullmatch(r"tray[_-][A-Za-z0-9_-]+", device_id))


def infer_device_type_code(device_id: str | None) -> str | None:
    normalized_device_id = normalize_device_id(device_id)
    if normalized_device_id is None:
        return None

    lowered = normalized_device_id.lower()
    if "pump" in lowered:
        return "pump"
    if "light" in lowered:
        return "light"
    if "fan" in lowered:
        return "fan"
    if "sensor" in lowered:
        return "sensor"
    return None


def _ensure_device(cursor, device_id: Any) -> str | None:
    normalized_device_id = normalize_device_id(device_id)
    if normalized_device_id is None:
        return None

    ensure_trays_schema(cursor)
    default_tray_id = ensure_tray(cursor, DEFAULT_TRAY_ID)
    tray_id = ensure_tray(cursor, normalized_device_id) if looks_like_tray_id(normalized_device_id) else default_tray_id
    device_type_code = infer_device_type_code(normalized_device_id)
    device_type_id = None
    if device_type_code is not None and column_exists(cursor, "devices", "device_type_id"):
        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[device_type_code]
        device_type = get_or_create_catalog_item(cursor, "device_type", device_type_code, name_ru, unit)
        device_type_id = device_type["id"]

    cursor.execute(
        """
        INSERT INTO devices (id, last_seen, tray_id, device_type_id)
        VALUES (%s, now(), %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            last_seen = EXCLUDED.last_seen,
            tray_id = COALESCE(devices.tray_id, EXCLUDED.tray_id),
            device_type_id = COALESCE(EXCLUDED.device_type_id, devices.device_type_id)
        """,
        (normalized_device_id, tray_id, device_type_id),
    )
    return normalized_device_id


def ensure_device(device_id: Any) -> str | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _ensure_device(cursor, device_id)


def backfill_trays_from_existing_refs(cursor) -> None:
    ensure_trays_schema(cursor)
    ensure_tray(cursor, DEFAULT_TRAY_ID)

    for table_name in ("anomaly_events", "devices"):
        if not table_exists(cursor, table_name) or not column_exists(cursor, table_name, "tray_id"):
            continue
        cursor.execute(
            sql.SQL(
                """
                UPDATE {}
                SET tray_id = NULL
                WHERE tray_id IS NOT NULL
                  AND btrim(tray_id) = ''
                """
            ).format(sql.Identifier(table_name))
        )

    for table_name in ("anomaly_events", "growing_cycles", "devices"):
        if not table_exists(cursor, table_name) or not column_exists(cursor, table_name, "tray_id"):
            continue
        cursor.execute(
            sql.SQL(
                """
                INSERT INTO trays (id)
                SELECT DISTINCT btrim(tray_id)
                FROM {}
                WHERE tray_id IS NOT NULL
                  AND btrim(tray_id) <> ''
                ON CONFLICT (id) DO NOTHING
                """
            ).format(sql.Identifier(table_name))
        )


def backfill_devices_for_existing_tray_ids(cursor) -> None:
    # Compatibility hook: tray_id is now normalized through trays.id, not devices.id.
    # Existing legacy FKs to devices.id are left untouched and can be removed by a dedicated migration.
    backfill_trays_from_existing_refs(cursor)


def constraint_exists(cursor, table_name: str, constraint_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND constraint_name = %s
        """,
        (table_name, constraint_name),
    )
    return cursor.fetchone() is not None


def foreign_key_exists(
    cursor,
    table_name: str,
    column_name: str,
    referenced_table: str,
    referenced_column: str,
) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class child_table ON child_table.oid = c.conrelid
        JOIN pg_namespace child_namespace ON child_namespace.oid = child_table.relnamespace
        JOIN pg_class parent_table ON parent_table.oid = c.confrelid
        JOIN pg_attribute child_column
          ON child_column.attrelid = c.conrelid
         AND child_column.attnum = ANY(c.conkey)
        JOIN pg_attribute parent_column
          ON parent_column.attrelid = c.confrelid
         AND parent_column.attnum = ANY(c.confkey)
        WHERE c.contype = 'f'
          AND child_namespace.nspname = current_schema()
          AND child_table.relname = %s
          AND child_column.attname = %s
          AND parent_table.relname = %s
          AND parent_column.attname = %s
        LIMIT 1
        """,
        (table_name, column_name, referenced_table, referenced_column),
    )
    return cursor.fetchone() is not None


def add_foreign_key_if_missing(
    cursor,
    table_name: str,
    constraint_name: str,
    column_name: str,
    referenced_table: str,
    referenced_column: str,
) -> None:
    if constraint_exists(cursor, table_name, constraint_name) or foreign_key_exists(
        cursor,
        table_name,
        column_name,
        referenced_table,
        referenced_column,
    ):
        return

    cursor.execute(
        sql.SQL(
            """
            ALTER TABLE {}
            ADD CONSTRAINT {}
            FOREIGN KEY ({})
            REFERENCES {}({})
            """
        ).format(
            sql.Identifier(table_name),
            sql.Identifier(constraint_name),
            sql.Identifier(column_name),
            sql.Identifier(referenced_table),
            sql.Identifier(referenced_column),
        )
    )


def ensure_device_foreign_keys(cursor) -> None:
    backfill_trays_from_existing_refs(cursor)
    for fk_config in TRAY_FK_CONSTRAINTS:
        table_name, _, column_name, _, _ = fk_config
        if not table_exists(cursor, table_name) or not column_exists(cursor, table_name, column_name):
            continue
        add_foreign_key_if_missing(cursor, *fk_config)


def extract_markdown_section(content: str, heading: str) -> str | None:
    match = re.search(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        content,
    )
    if not match:
        return None
    return match.group("body").strip()


def extract_first_nonempty_line(content: str, heading: str) -> str | None:
    section = extract_markdown_section(content, heading)
    if not section:
        return None
    for line in section.splitlines():
        value = line.strip()
        if value:
            return value
    return None


def extract_crop_slug(content: str, fallback_slug: str) -> str:
    match = re.search(r"(?im)^#\s*CULTURE:\s*([a-z0-9_-]+)\s*$", content)
    return match.group(1).strip().lower() if match else fallback_slug


def extract_card_title(content: str, fallback_slug: str) -> str:
    name_ru = extract_first_nonempty_line(content, "Название")
    if name_ru:
        return name_ru

    match = re.search(r"(?m)^#\s+(.+?)\s*$", content)
    if match:
        return match.group(1).strip()

    return fallback_slug.replace("_", " ").title()


def parse_norm_value(raw_value: str) -> Any:
    value = raw_value.strip()
    numeric_range_match = re.fullmatch(
        r"(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)",
        value,
    )
    if numeric_range_match:
        low, high = numeric_range_match.groups()
        return {"min": float(low), "max": float(high)}

    numeric_match = re.fullmatch(r"-?\d+(?:\.\d+)?", value)
    if numeric_match:
        return float(value)

    object_match = re.fullmatch(r'([a-zA-Z_][\w-]*)\s*:\s*"?(.*?)"?', value)
    if object_match:
        key, nested_value = object_match.groups()
        return {key: nested_value}

    return value.strip('"')


def parse_agrotech_params(content: str) -> dict[str, Any]:
    norms_block = extract_markdown_section(content, "Нормы")
    if not norms_block:
        return {}

    params: dict[str, Any] = {}
    for key in AGROTECH_NORM_KEYS:
        match = re.search(rf"(?im)^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", norms_block)
        if match:
            params[key] = parse_norm_value(match.group(1))
    return params


def ensure_agrotech_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS crops (
            id BIGSERIAL PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name_ru TEXT,
            crop_type TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agrotech_cards (
            id BIGSERIAL PRIMARY KEY,
            crop_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agrotech_card_revisions (
            id BIGSERIAL PRIMARY KEY,
            card_id BIGINT NOT NULL,
            version_major INTEGER NOT NULL,
            version_minor INTEGER NOT NULL,
            parent_revision_id BIGINT,
            content TEXT NOT NULL,
            source TEXT,
            change_reason TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT false
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agrotech_audit_log (
            id BIGSERIAL PRIMARY KEY,
            card_id BIGINT NOT NULL,
            revision_id BIGINT,
            action TEXT NOT NULL,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agrotech_card_sections (
            id BIGSERIAL PRIMARY KEY,
            revision_id BIGINT NOT NULL,
            section_title TEXT NOT NULL,
            section_order INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(revision_id, section_order)
        )
        """
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_agrotech_cards_crop_id ON agrotech_cards(crop_id)"
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agrotech_card_revisions_version
        ON agrotech_card_revisions(card_id, version_major, version_minor)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agrotech_card_revisions_active
        ON agrotech_card_revisions(card_id)
        WHERE is_active
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agrotech_audit_log_card_id ON agrotech_audit_log(card_id, created_at DESC)"
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agrotech_card_sections_revision_order
        ON agrotech_card_sections(revision_id, section_order)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agrotech_card_sections_revision_title
        ON agrotech_card_sections(revision_id, section_title)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_cards",
        "fk_agrotech_cards_crop_id_crops",
        "crop_id",
        "crops",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_card_revisions",
        "fk_agrotech_card_revisions_card_id_cards",
        "card_id",
        "agrotech_cards",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_card_revisions",
        "fk_agrotech_card_revisions_parent_revision_id",
        "parent_revision_id",
        "agrotech_card_revisions",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_audit_log",
        "fk_agrotech_audit_log_card_id_cards",
        "card_id",
        "agrotech_cards",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_audit_log",
        "fk_agrotech_audit_log_revision_id_revisions",
        "revision_id",
        "agrotech_card_revisions",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_card_sections",
        "fk_agrotech_card_sections_revision_id_revisions",
        "revision_id",
        "agrotech_card_revisions",
        "id",
    )


def ensure_agrotech_norms_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_items (
            id BIGSERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            code TEXT NOT NULL,
            name_ru TEXT,
            unit TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(category, code)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agrotech_revision_norms (
            id BIGSERIAL PRIMARY KEY,
            revision_id BIGINT NOT NULL,
            metric_id BIGINT NOT NULL,
            min_value DOUBLE PRECISION,
            max_value DOUBLE PRECISION,
            target_value DOUBLE PRECISION,
            raw_value TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(revision_id, metric_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_catalog_items_category_code
        ON catalog_items(category, code)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agrotech_revision_norms_revision_metric
        ON agrotech_revision_norms(revision_id, metric_id)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_revision_norms",
        "fk_agrotech_revision_norms_revision_id_revisions",
        "revision_id",
        "agrotech_card_revisions",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "agrotech_revision_norms",
        "fk_agrotech_revision_norms_metric_id_catalog_items",
        "metric_id",
        "catalog_items",
        "id",
    )


def get_or_create_catalog_item(
    cursor,
    category: str,
    code: str,
    name_ru: str | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO catalog_items (category, code, name_ru, unit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (category, code) DO UPDATE SET
            name_ru = COALESCE(EXCLUDED.name_ru, catalog_items.name_ru),
            unit = EXCLUDED.unit
        RETURNING id, category, code, name_ru, unit, created_at
        """,
        (category, code, name_ru, unit),
    )
    return cursor.fetchone()


def get_catalog_item_id(cursor, category: str, code: str) -> int | None:
    if code is None:
        return None
    cursor.execute(
        """
        SELECT id
        FROM catalog_items
        WHERE category = %s
          AND code = %s
        """,
        (category, code),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def resolve_catalog_item_id(cursor, category: str, code: str | None) -> int | None:
    normalized_code = normalize_device_id(code)
    if normalized_code is None:
        return None
    return get_catalog_item_id(cursor, category, normalized_code)


def ensure_base_catalog_items(cursor) -> None:
    for category, code, name_ru, unit in BASE_CATALOG_ITEMS:
        get_or_create_catalog_item(cursor, category, code, name_ru, unit)


def json_object_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def norm_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def norm_raw_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def save_revision_norms(cursor, revision_id: int, norms_payload: Any) -> None:
    params = json_object_to_dict(norms_payload)
    if not revision_id or not params:
        return

    for metric_code in AGROTECH_NORM_KEYS:
        if metric_code not in params or params[metric_code] is None:
            continue

        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[metric_code]
        metric = get_or_create_catalog_item(cursor, "metric", metric_code, name_ru, unit)
        value = params[metric_code]
        min_value = None
        max_value = None
        target_value = None
        raw_value = None

        if isinstance(value, dict) and ("min" in value or "max" in value):
            min_value = norm_float(value.get("min"))
            max_value = norm_float(value.get("max"))
            if min_value is None and max_value is None:
                raw_value = norm_raw_value(value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            target_value = float(value)
        else:
            raw_value = norm_raw_value(value)

        cursor.execute(
            """
            INSERT INTO agrotech_revision_norms (
                revision_id, metric_id, min_value, max_value, target_value, raw_value
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (revision_id, metric_id) DO UPDATE SET
                min_value = EXCLUDED.min_value,
                max_value = EXCLUDED.max_value,
                target_value = EXCLUDED.target_value,
                raw_value = EXCLUDED.raw_value
            """,
            (
                revision_id,
                metric["id"],
                min_value,
                max_value,
                target_value,
                raw_value,
            ),
        )


def migrate_revision_norms_from_legacy_params_json(cursor) -> None:
    ensure_base_catalog_items(cursor)
    if not column_exists(cursor, "agrotech_card_revisions", "params_json"):
        return
    cursor.execute(
        """
        SELECT id, params_json
        FROM agrotech_card_revisions
        """
    )
    for row in cursor.fetchall():
        save_revision_norms(cursor, row["id"], row["params_json"])


def drop_agrotech_legacy_columns(cursor) -> None:
    migrate_revision_norms_from_legacy_params_json(cursor)
    for column_name in ("params_json", "version_label"):
        cursor.execute(
            sql.SQL("ALTER TABLE agrotech_card_revisions DROP COLUMN IF EXISTS {}").format(
                sql.Identifier(column_name)
            )
        )
    for column_name in ("old_params_json", "new_params_json"):
        cursor.execute(
            sql.SQL("ALTER TABLE agrotech_audit_log DROP COLUMN IF EXISTS {}").format(
                sql.Identifier(column_name)
            )
        )


def get_revision_norms(cursor, revision_id: int | None) -> dict[str, Any]:
    if revision_id is None:
        return {}

    cursor.execute(
        """
        SELECT
            catalog_items.code,
            agrotech_revision_norms.min_value,
            agrotech_revision_norms.max_value,
            agrotech_revision_norms.target_value,
            agrotech_revision_norms.raw_value
        FROM agrotech_revision_norms
        JOIN catalog_items ON catalog_items.id = agrotech_revision_norms.metric_id
        WHERE agrotech_revision_norms.revision_id = %s
          AND catalog_items.category = 'metric'
        ORDER BY catalog_items.code
        """,
        (revision_id,),
    )

    norms: dict[str, Any] = {}
    for row in cursor.fetchall():
        if row["min_value"] is not None or row["max_value"] is not None:
            value = {}
            if row["min_value"] is not None:
                value["min"] = row["min_value"]
            if row["max_value"] is not None:
                value["max"] = row["max_value"]
            norms[row["code"]] = value
        elif row["target_value"] is not None:
            norms[row["code"]] = row["target_value"]
        elif row["raw_value"] is not None:
            try:
                norms[row["code"]] = json.loads(row["raw_value"])
            except json.JSONDecodeError:
                norms[row["code"]] = row["raw_value"]

    return norms


def make_version_label(version_major: Any, version_minor: Any) -> str:
    return f"v{version_major}.{version_minor}"


def with_version_label(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    result["version_label"] = make_version_label(result["version_major"], result["version_minor"])
    return result


def parse_markdown_sections(content: str) -> list[dict[str, Any]]:
    source_content = str(content or "").strip()
    if not source_content:
        return [
            {
                "section_title": "Основное описание",
                "section_order": 1,
                "content": "",
            }
        ]

    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", source_content))
    if not matches:
        return [
            {
                "section_title": "Основное описание",
                "section_order": 1,
                "content": source_content,
            }
        ]

    sections: list[dict[str, Any]] = []
    for index, match in enumerate(matches, start=1):
        section_start = match.end()
        section_end = matches[index].start() if index < len(matches) else len(source_content)
        section_title = match.group(1).strip() or "Раздел"
        section_content = source_content[section_start:section_end].strip()
        sections.append(
            {
                "section_title": section_title,
                "section_order": index,
                "content": section_content,
            }
        )

    return sections


def save_card_sections(cursor, revision_id: int, content: str) -> None:
    if not revision_id:
        return

    for section in parse_markdown_sections(content):
        cursor.execute(
            """
            INSERT INTO agrotech_card_sections (
                revision_id, section_title, section_order, content
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (revision_id, section_order) DO UPDATE SET
                section_title = EXCLUDED.section_title,
                content = EXCLUDED.content
            """,
            (
                revision_id,
                section["section_title"],
                section["section_order"],
                section["content"],
            ),
        )


def backfill_card_sections(cursor) -> None:
    cursor.execute(
        """
        SELECT id, content
        FROM agrotech_card_revisions
        ORDER BY id ASC
        """
    )
    for row in cursor.fetchall():
        save_card_sections(cursor, row["id"], row["content"])


def ensure_device_relationship_columns(cursor) -> None:
    ensure_trays_schema(cursor)
    ensure_tray(cursor, DEFAULT_TRAY_ID)
    ensure_base_catalog_items(cursor)

    cursor.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS tray_id TEXT")
    cursor.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS device_type_id BIGINT")

    cursor.execute("SELECT id, tray_id, device_type_id FROM devices")
    for row in cursor.fetchall():
        if row["tray_id"] is None:
            tray_id = ensure_tray(cursor, row["id"]) if looks_like_tray_id(row["id"]) else DEFAULT_TRAY_ID
            cursor.execute(
                """
                UPDATE devices
                SET tray_id = %s
                WHERE id = %s
                """,
                (tray_id, row["id"]),
            )

        if row["device_type_id"] is not None:
            continue
        device_type_code = infer_device_type_code(row["id"])
        if device_type_code is None:
            continue
        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[device_type_code]
        device_type = get_or_create_catalog_item(cursor, "device_type", device_type_code, name_ru, unit)
        cursor.execute(
            """
            UPDATE devices
            SET device_type_id = %s
            WHERE id = %s
            """,
            (device_type["id"], row["id"]),
        )

    cursor.execute(
        """
        INSERT INTO trays (id)
        SELECT DISTINCT tray_id
        FROM devices
        WHERE tray_id IS NOT NULL
          AND btrim(tray_id) <> ''
        ON CONFLICT (id) DO NOTHING
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "devices",
        "fk_devices_tray_id_trays",
        "tray_id",
        "trays",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "devices",
        "fk_devices_device_type_id_catalog_items",
        "device_type_id",
        "catalog_items",
        "id",
    )


def ensure_device_events_schema(cursor) -> None:
    ensure_trays_schema(cursor)
    ensure_tray(cursor, DEFAULT_TRAY_ID)
    ensure_base_catalog_items(cursor)
    ensure_device_relationship_columns(cursor)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS device_events (
            id BIGSERIAL PRIMARY KEY,
            device_id TEXT NOT NULL,
            tray_id TEXT NOT NULL,
            event_type_id BIGINT,
            command TEXT NOT NULL,
            value TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            payload JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_device_events_device_created_at
        ON device_events(device_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_device_events_tray_created_at
        ON device_events(tray_id, created_at DESC)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "device_events",
        "fk_device_events_device_id_devices",
        "device_id",
        "devices",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "device_events",
        "fk_device_events_tray_id_trays",
        "tray_id",
        "trays",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "device_events",
        "fk_device_events_event_type_id_catalog_items",
        "event_type_id",
        "catalog_items",
        "id",
    )


def infer_device_event_type_code(command: Any = None, value: Any = None, source: str = "manual") -> str:
    command_text = str(command or "").strip().lower()
    value_text = str(value or "").strip().lower()
    source_text = str(source or "").strip().lower()
    combined = f"{command_text} {value_text}".strip()

    if command_text == "status_update" or source_text == "status":
        return "status_update"
    if combined in {"on", "manual_on"} or command_text.endswith("_on") or value_text == "on":
        return "manual_on"
    if combined in {"off", "manual_off"} or command_text.endswith("_off") or value_text == "off":
        return "manual_off"
    return "manual_toggle"


def _save_device_event(
    cursor,
    *,
    device_id: Any,
    tray_id: Any = DEFAULT_TRAY_ID,
    command: Any = None,
    value: Any = None,
    source: str = "manual",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized_device_id = normalize_device_id(device_id)
    if normalized_device_id is None:
        return None

    normalized_tray_id = ensure_tray(cursor, tray_id)
    _ensure_device(cursor, normalized_device_id)
    cursor.execute(
        """
        UPDATE devices
        SET tray_id = %s
        WHERE id = %s
          AND (tray_id IS NULL OR tray_id = %s)
        """,
        (normalized_tray_id, normalized_device_id, DEFAULT_TRAY_ID),
    )
    event_type_code = infer_device_event_type_code(command, value, source)
    event_type_id = get_catalog_item_id(cursor, "event_type", event_type_code)
    if event_type_id is None:
        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[event_type_code]
        event_type = get_or_create_catalog_item(cursor, "event_type", event_type_code, name_ru, unit)
        event_type_id = event_type["id"]
    command_text = str(command if command is not None else value if value is not None else "toggle")
    value_text = str(value) if value is not None else None

    cursor.execute(
        """
        INSERT INTO device_events (
            device_id, tray_id, event_type_id, command, value, source, payload, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        RETURNING id, device_id, tray_id, event_type_id, command, value, source, payload, created_at
        """,
        (
            normalized_device_id,
            normalized_tray_id,
            event_type_id,
            command_text,
            value_text,
            source,
            Jsonb(payload) if payload is not None else None,
        ),
    )
    return cursor.fetchone()


def get_device_current_status(cursor, device_id: Any) -> str | None:
    normalized_device_id = normalize_device_id(device_id)
    if normalized_device_id is None:
        return None
    cursor.execute(
        """
        SELECT value, command, source
        FROM device_events
        WHERE device_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (normalized_device_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return row["value"] or row["command"] or row["source"]


def save_device_event(
    device_id: Any,
    tray_id: Any = DEFAULT_TRAY_ID,
    command: Any = None,
    value: Any = None,
    source: str = "manual",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _save_device_event(
                cursor,
                device_id=device_id,
                tray_id=tray_id,
                command=command,
                value=value,
                source=source,
                payload=payload,
            )


def _get_or_create_crop(
    cursor,
    *,
    slug: str,
    name_ru: str | None = None,
    crop_type: str | None = None,
) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO crops (slug, name_ru, crop_type)
        VALUES (%s, %s, %s)
        ON CONFLICT (slug) DO NOTHING
        RETURNING id, slug, name_ru, crop_type, created_at
        """,
        (slug, name_ru, crop_type),
    )
    row = cursor.fetchone()
    if row:
        return row

    cursor.execute(
        """
        SELECT id, slug, name_ru, crop_type, created_at
        FROM crops
        WHERE slug = %s
        """,
        (slug,),
    )
    return cursor.fetchone()


def get_or_create_crop(
    *,
    slug: str,
    name_ru: str | None = None,
    crop_type: str | None = None,
) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _get_or_create_crop(
                cursor,
                slug=slug,
                name_ru=name_ru,
                crop_type=crop_type,
            )


def _get_or_create_agrotech_card(cursor, *, crop_id: int, title: str) -> dict[str, Any]:
    cursor.execute(
        """
        INSERT INTO agrotech_cards (crop_id, title, status)
        VALUES (%s, %s, 'active')
        ON CONFLICT (crop_id) DO NOTHING
        RETURNING id, crop_id, title, status, created_at
        """,
        (crop_id, title),
    )
    row = cursor.fetchone()
    if row:
        return row

    cursor.execute(
        """
        SELECT id, crop_id, title, status, created_at
        FROM agrotech_cards
        WHERE crop_id = %s
        """,
        (crop_id,),
    )
    return cursor.fetchone()


def _create_card_revision(
    cursor,
    *,
    card_id: int,
    version_major: int,
    version_minor: int,
    norms_payload: dict[str, Any] | None,
    content: str,
    source: str | None = None,
    change_reason: str | None = None,
    created_by: str | None = None,
    parent_revision_id: int | None = None,
    is_active: bool = True,
) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, card_id, version_major, version_minor,
               parent_revision_id, content, source,
               change_reason, created_by, created_at, is_active
        FROM agrotech_card_revisions
        WHERE card_id = %s
          AND version_major = %s
          AND version_minor = %s
        """,
        (card_id, version_major, version_minor),
    )
    existing_revision = cursor.fetchone()
    if existing_revision:
        save_revision_norms(cursor, existing_revision["id"], norms_payload or {})
        save_card_sections(cursor, existing_revision["id"], content)
        return with_version_label(existing_revision)

    if is_active:
        cursor.execute(
            """
            UPDATE agrotech_card_revisions
            SET is_active = false
            WHERE card_id = %s
              AND is_active
            """,
            (card_id,),
        )

    cursor.execute(
        """
        INSERT INTO agrotech_card_revisions (
            card_id, version_major, version_minor,
            parent_revision_id, content, source,
            change_reason, created_by, is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, card_id, version_major, version_minor,
                  parent_revision_id, content, source,
                  change_reason, created_by, created_at, is_active
        """,
        (
            card_id,
            version_major,
            version_minor,
            parent_revision_id,
            content,
            source,
            change_reason,
            created_by,
            is_active,
        ),
    )
    revision = with_version_label(cursor.fetchone())
    save_revision_norms(cursor, revision["id"], norms_payload or {})
    save_card_sections(cursor, revision["id"], content)
    cursor.execute(
        """
        INSERT INTO agrotech_audit_log (
            card_id, revision_id, action, reason, created_at
        )
        VALUES (%s, %s, %s, %s, now())
        """,
        (
            card_id,
            revision["id"],
            "create_revision",
            change_reason,
        ),
    )
    return revision


def _card_has_active_revision(cursor, card_id: int) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM agrotech_card_revisions
        WHERE card_id = %s
          AND is_active
        LIMIT 1
        """,
        (card_id,),
    )
    return cursor.fetchone() is not None


def _card_revision_exists(
    cursor,
    *,
    card_id: int,
    version_major: int,
    version_minor: int,
) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM agrotech_card_revisions
        WHERE card_id = %s
          AND version_major = %s
          AND version_minor = %s
        LIMIT 1
        """,
        (card_id, version_major, version_minor),
    )
    return cursor.fetchone() is not None


def create_card_revision(
    *,
    card_id: int,
    version_major: int,
    version_minor: int,
    content: str,
    norms_payload: dict[str, Any] | None = None,
    source: str | None = None,
    change_reason: str | None = None,
    created_by: str | None = None,
    parent_revision_id: int | None = None,
    is_active: bool = True,
    params_json: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    resolved_norms_payload = norms_payload if norms_payload is not None else params_json
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _create_card_revision(
                cursor,
                card_id=card_id,
                version_major=version_major,
                version_minor=version_minor,
                norms_payload=resolved_norms_payload,
                content=content,
                source=source,
                change_reason=change_reason,
                created_by=created_by,
                parent_revision_id=parent_revision_id,
                is_active=is_active,
            )


def _import_crop_cards_from_md(cursor) -> int:
    if not CROPS_DATA_DIR.exists():
        return 0

    imported_count = 0
    for path in sorted(CROPS_DATA_DIR.glob("*.md")):
        if path.name in NON_CROP_CARD_FILES:
            continue

        content = path.read_text(encoding="utf-8")
        slug = extract_crop_slug(content, path.stem)
        title = extract_card_title(content, slug)
        crop_type = extract_first_nonempty_line(content, "Тип культуры")
        norms_payload = parse_agrotech_params(content)

        crop = _get_or_create_crop(
            cursor,
            slug=slug,
            name_ru=title,
            crop_type=crop_type,
        )
        card = _get_or_create_agrotech_card(cursor, crop_id=crop["id"], title=title)
        if _card_revision_exists(
            cursor,
            card_id=card["id"],
            version_major=1,
            version_minor=0,
        ):
            continue

        revision = _create_card_revision(
            cursor,
            card_id=card["id"],
            version_major=1,
            version_minor=0,
            norms_payload=norms_payload,
            content=content,
            source=f"crops_data/{path.name}",
            change_reason="Initial import from Markdown",
            created_by="init_db",
            is_active=not _card_has_active_revision(cursor, card["id"]),
        )
        if revision and revision.get("version_major") == 1 and revision.get("version_minor") == 0:
            imported_count += 1

    return imported_count


def import_crop_cards_from_md() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _import_crop_cards_from_md(cursor)


def _get_active_card_revision(cursor, crop_slug: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT
            crops.id AS crop_id,
            crops.slug,
            crops.name_ru,
            crops.crop_type,
            agrotech_cards.id AS card_id,
            agrotech_cards.title,
            agrotech_cards.status,
            agrotech_card_revisions.id AS revision_id,
            agrotech_card_revisions.version_major,
            agrotech_card_revisions.version_minor,
            agrotech_card_revisions.parent_revision_id,
            agrotech_card_revisions.content,
            agrotech_card_revisions.source,
            agrotech_card_revisions.change_reason,
            agrotech_card_revisions.created_by,
            agrotech_card_revisions.created_at,
            agrotech_card_revisions.is_active
        FROM crops
        JOIN agrotech_cards ON agrotech_cards.crop_id = crops.id
        JOIN agrotech_card_revisions
          ON agrotech_card_revisions.card_id = agrotech_cards.id
        WHERE crops.slug = %s
          AND agrotech_card_revisions.is_active
        LIMIT 1
        """,
        (crop_slug,),
    )
    return with_version_label(cursor.fetchone())


def get_active_card_revision(crop_slug: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _get_active_card_revision(cursor, crop_slug)


def normalize_crop_lookup(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("ё", "е")
    return " ".join(normalized.replace("_", " ").replace("-", " ").split())


def get_crop_agrotech_card_from_db(crop_name_or_slug: Any) -> dict[str, Any] | None:
    lookup = str(crop_name_or_slug or "").strip()
    if not lookup:
        return None

    normalized_lookup = normalize_crop_lookup(lookup)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    crops.id AS crop_id,
                    crops.slug AS crop_slug,
                    crops.name_ru AS crop_name_ru,
                    crops.crop_type,
                    agrotech_cards.id AS card_id,
                    agrotech_card_revisions.id AS revision_id,
                    agrotech_card_revisions.version_major,
                    agrotech_card_revisions.version_minor
                FROM crops
                JOIN agrotech_cards ON agrotech_cards.crop_id = crops.id
                JOIN agrotech_card_revisions
                  ON agrotech_card_revisions.card_id = agrotech_cards.id
                 AND agrotech_card_revisions.is_active
                WHERE lower(crops.slug) = lower(%s)
                   OR lower(crops.name_ru) = lower(%s)
                   OR replace(replace(lower(crops.slug), '_', ' '), '-', ' ') = %s
                   OR replace(replace(lower(COALESCE(crops.name_ru, '')), '_', ' '), '-', ' ') = %s
                ORDER BY crops.slug
                LIMIT 1
                """,
                (lookup, lookup, normalized_lookup, normalized_lookup),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            norms = get_revision_norms(cursor, row["revision_id"])

            cursor.execute(
                """
                SELECT section_title, content
                FROM agrotech_card_sections
                WHERE revision_id = %s
                ORDER BY section_order ASC
                """,
                (row["revision_id"],),
            )
            sections = cursor.fetchall()

    version_label = make_version_label(row["version_major"], row["version_minor"])
    return {
        "crop_slug": row["crop_slug"],
        "crop_name_ru": row["crop_name_ru"],
        "crop_type": row["crop_type"],
        "card_id": row["card_id"],
        "revision_id": row["revision_id"],
        "version_major": row["version_major"],
        "version_minor": row["version_minor"],
        "version_label": version_label,
        "norms": norms,
        "sections": [
            {
                "section_title": section["section_title"],
                "content": section["content"],
            }
            for section in sections
        ],
    }


def ensure_growing_cycles_schema(cursor) -> None:
    ensure_trays_schema(cursor)
    ensure_tray(cursor, DEFAULT_TRAY_ID)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS growing_cycles (
            id BIGSERIAL PRIMARY KEY,
            tray_id TEXT NOT NULL,
            crop_id BIGINT NOT NULL,
            card_revision_id BIGINT NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    if not constraint_exists(cursor, "growing_cycles", "chk_growing_cycles_status"):
        cursor.execute(
            """
            ALTER TABLE growing_cycles
            ADD CONSTRAINT chk_growing_cycles_status
            CHECK (status IN ('active', 'finished', 'cancelled'))
            """
        )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_growing_cycles_active_tray_id
        ON growing_cycles(tray_id)
        WHERE status = 'active'
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_growing_cycles_tray_status
        ON growing_cycles(tray_id, status, started_at DESC)
        """
    )
    backfill_trays_from_existing_refs(cursor)
    add_foreign_key_if_missing(
        cursor,
        "growing_cycles",
        "fk_growing_cycles_tray_id_trays",
        "tray_id",
        "trays",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "growing_cycles",
        "fk_growing_cycles_crop_id_crops",
        "crop_id",
        "crops",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "growing_cycles",
        "fk_growing_cycles_card_revision_id_revisions",
        "card_revision_id",
        "agrotech_card_revisions",
        "id",
    )


def get_active_cycle_id_for_tray(cursor, tray_id: Any) -> int | None:
    normalized_tray_id = normalize_device_id(tray_id)
    if normalized_tray_id is None:
        return None

    cursor.execute(
        """
        SELECT id
        FROM growing_cycles
        WHERE tray_id = %s
          AND status = 'active'
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (normalized_tray_id,),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def get_current_cycle_id_for_tray(tray_id: str = DEFAULT_TRAY_ID) -> int | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return get_active_cycle_id_for_tray(cursor, tray_id)


def ensure_anomaly_event_refs_schema(cursor) -> None:
    ensure_base_catalog_items(cursor)
    cursor.execute("ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS sensor_type_id BIGINT")
    cursor.execute("ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS event_type_id BIGINT")
    cursor.execute("ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS metric_id BIGINT")
    cursor.execute("ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS severity_id BIGINT")
    cursor.execute("ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS cycle_id BIGINT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_events_tray_created_at
        ON anomaly_events(tray_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_events_event_type_created_at
        ON anomaly_events(event_type_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_events_metric_created_at
        ON anomaly_events(metric_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_events_severity_created_at
        ON anomaly_events(severity_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_anomaly_events_cycle_created_at
        ON anomaly_events(cycle_id, created_at DESC)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "anomaly_events",
        "fk_anomaly_events_sensor_type_id_catalog_items",
        "sensor_type_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "anomaly_events",
        "fk_anomaly_events_event_type_id_catalog_items",
        "event_type_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "anomaly_events",
        "fk_anomaly_events_metric_id_catalog_items",
        "metric_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "anomaly_events",
        "fk_anomaly_events_severity_id_catalog_items",
        "severity_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "anomaly_events",
        "fk_anomaly_events_cycle_id_growing_cycles",
        "cycle_id",
        "growing_cycles",
        "id",
    )


def backfill_anomaly_event_refs(cursor) -> int:
    ensure_anomaly_event_refs_schema(cursor)
    legacy_columns = ("sensor_type", "event_type", "metric_name", "severity")
    if not all(column_exists(cursor, "anomaly_events", column_name) for column_name in legacy_columns):
        return 0
    cursor.execute(
        """
        SELECT
            id, tray_id, sensor_type, event_type,
            metric_name, severity, cycle_id
        FROM anomaly_events
        WHERE sensor_type_id IS NULL
           OR event_type_id IS NULL
           OR metric_id IS NULL
           OR severity_id IS NULL
           OR cycle_id IS NULL
        ORDER BY id ASC
        """
    )
    rows = cursor.fetchall()
    for row in rows:
        cycle_id = row["cycle_id"]
        if cycle_id is None:
            cycle_id = get_active_cycle_id_for_tray(cursor, row["tray_id"])
        cursor.execute(
            """
            UPDATE anomaly_events
            SET sensor_type_id = COALESCE(sensor_type_id, %s),
                event_type_id = COALESCE(event_type_id, %s),
                metric_id = COALESCE(metric_id, %s),
                severity_id = COALESCE(severity_id, %s),
                cycle_id = COALESCE(cycle_id, %s)
            WHERE id = %s
            """,
            (
                resolve_catalog_item_id(cursor, "sensor_type", row["sensor_type"]),
                resolve_catalog_item_id(cursor, "anomaly_type", row["event_type"]),
                resolve_catalog_item_id(cursor, "metric", row["metric_name"]),
                resolve_catalog_item_id(cursor, "severity", row["severity"]),
                cycle_id,
                row["id"],
            ),
        )
    return len(rows)


def drop_anomaly_legacy_columns(cursor) -> None:
    backfill_anomaly_event_refs(cursor)
    for column_name in ("sensor_type", "event_type", "metric_name", "severity"):
        cursor.execute(
            sql.SQL("ALTER TABLE anomaly_events DROP COLUMN IF EXISTS {}").format(
                sql.Identifier(column_name)
            )
        )


def ensure_cycle_results_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cycle_results (
            id BIGSERIAL PRIMARY KEY,
            cycle_id BIGINT NOT NULL UNIQUE,
            harvest_weight_grams DOUBLE PRECISION,
            quality_score INTEGER,
            operator_comment TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "cycle_results",
        "fk_cycle_results_cycle_id_growing_cycles",
        "cycle_id",
        "growing_cycles",
        "id",
    )


def row_to_cycle_result(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "cycle_id": row["cycle_id"],
        "harvest_weight_grams": row["harvest_weight_grams"],
        "quality_score": row["quality_score"],
        "operator_comment": row["operator_comment"],
        "created_at": format_timestamp(row["created_at"]),
        "updated_at": format_timestamp(row["updated_at"]),
    }


def _get_cycle_result(cursor, cycle_id: int) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT
            id, cycle_id, harvest_weight_grams, quality_score,
            operator_comment, created_at, updated_at
        FROM cycle_results
        WHERE cycle_id = %s
        """,
        (cycle_id,),
    )
    return cursor.fetchone()


def get_cycle_result(cycle_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return row_to_cycle_result(_get_cycle_result(cursor, cycle_id))


def save_cycle_result(
    cycle_id: int,
    harvest_weight_grams: float | None = None,
    quality_score: int | None = None,
    operator_comment: str | None = None,
) -> dict[str, Any]:
    if quality_score is not None and not 1 <= quality_score <= 5:
        raise InvalidCycleResultError("quality_score must be in range 1..5")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_cycle_results_schema(cursor)
            cursor.execute(
                """
                SELECT id, status
                FROM growing_cycles
                WHERE id = %s
                """,
                (cycle_id,),
            )
            cycle = cursor.fetchone()
            if cycle is None:
                raise GrowingCycleNotFoundError(f"Growing cycle '{cycle_id}' not found")
            if cycle["status"] != "finished":
                raise GrowingCycleNotFinishedError(
                    f"Growing cycle '{cycle_id}' is not finished"
                )

            cursor.execute(
                """
                INSERT INTO cycle_results (
                    cycle_id, harvest_weight_grams, quality_score,
                    operator_comment, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, now(), now())
                ON CONFLICT (cycle_id) DO UPDATE SET
                    harvest_weight_grams = EXCLUDED.harvest_weight_grams,
                    quality_score = EXCLUDED.quality_score,
                    operator_comment = EXCLUDED.operator_comment,
                    updated_at = now()
                RETURNING id, cycle_id, harvest_weight_grams, quality_score,
                          operator_comment, created_at, updated_at
                """,
                (cycle_id, harvest_weight_grams, quality_score, operator_comment),
            )
            return row_to_cycle_result(cursor.fetchone())


def get_cycle_with_result(cycle_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cycle = row_to_growing_cycle(_select_growing_cycle_by_id(cursor, cycle_id))
            if cycle is None:
                raise GrowingCycleNotFoundError(f"Growing cycle '{cycle_id}' not found")
            cycle["result"] = row_to_cycle_result(_get_cycle_result(cursor, cycle_id))
            return cycle


def ensure_advisor_reports_schema(cursor) -> None:
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
    cursor.execute("ALTER TABLE advisor_reports ADD COLUMN IF NOT EXISTS cycle_id BIGINT")
    cursor.execute("ALTER TABLE advisor_reports ADD COLUMN IF NOT EXISTS card_revision_id BIGINT")
    cursor.execute("ALTER TABLE advisor_reports ADD COLUMN IF NOT EXISTS summary TEXT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_advisor_reports_cycle_created_at
        ON advisor_reports(cycle_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_advisor_reports_card_revision_created_at
        ON advisor_reports(card_revision_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS advisor_report_findings (
            id BIGSERIAL PRIMARY KEY,
            report_id BIGINT NOT NULL,
            metric_id BIGINT,
            severity_id BIGINT,
            finding_type TEXT,
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS advisor_report_recommendations (
            id BIGSERIAL PRIMARY KEY,
            report_id BIGINT NOT NULL,
            metric_id BIGINT,
            recommendation_text TEXT NOT NULL,
            proposed_min_value DOUBLE PRECISION,
            proposed_max_value DOUBLE PRECISION,
            proposed_target_value DOUBLE PRECISION,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    for table_name, index_name, column_name in (
        ("advisor_report_findings", "idx_advisor_report_findings_report_id", "report_id"),
        ("advisor_report_findings", "idx_advisor_report_findings_metric_id", "metric_id"),
        ("advisor_report_recommendations", "idx_advisor_report_recommendations_report_id", "report_id"),
        ("advisor_report_recommendations", "idx_advisor_report_recommendations_metric_id", "metric_id"),
        ("advisor_report_recommendations", "idx_advisor_report_recommendations_status", "status"),
    ):
        cursor.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {}({})").format(
                sql.Identifier(index_name),
                sql.Identifier(table_name),
                sql.Identifier(column_name),
            )
        )
    add_foreign_key_if_missing(
        cursor,
        "advisor_reports",
        "fk_advisor_reports_cycle_id_growing_cycles",
        "cycle_id",
        "growing_cycles",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "advisor_reports",
        "fk_advisor_reports_card_revision_id_revisions",
        "card_revision_id",
        "agrotech_card_revisions",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "advisor_report_findings",
        "fk_advisor_report_findings_report_id_reports",
        "report_id",
        "advisor_reports",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "advisor_report_findings",
        "fk_advisor_report_findings_metric_id_catalog_items",
        "metric_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "advisor_report_findings",
        "fk_advisor_report_findings_severity_id_catalog_items",
        "severity_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "advisor_report_recommendations",
        "fk_advisor_report_recommendations_report_id_reports",
        "report_id",
        "advisor_reports",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "advisor_report_recommendations",
        "fk_advisor_report_recommendations_metric_id_catalog_items",
        "metric_id",
        "catalog_items",
        "id",
    )


def ensure_ai_logs_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_logs (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            thought TEXT
        )
        """
    )
    cursor.execute("ALTER TABLE ai_logs ADD COLUMN IF NOT EXISTS cycle_id BIGINT")
    cursor.execute("ALTER TABLE ai_logs ADD COLUMN IF NOT EXISTS source TEXT")
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_logs_cycle_timestamp
        ON ai_logs(cycle_id, timestamp DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_logs_source_timestamp
        ON ai_logs(source, timestamp DESC)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "ai_logs",
        "fk_ai_logs_cycle_id_growing_cycles",
        "cycle_id",
        "growing_cycles",
        "id",
    )


def ensure_ai_log_commands_schema(cursor) -> None:
    ensure_device_relationship_columns(cursor)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_log_commands (
            id BIGSERIAL PRIMARY KEY,
            ai_log_id BIGINT NOT NULL,
            device_id TEXT,
            command TEXT,
            value TEXT,
            payload JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_log_commands_ai_log_id
        ON ai_log_commands(ai_log_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_log_commands_device_created_at
        ON ai_log_commands(device_id, created_at DESC)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "ai_log_commands",
        "fk_ai_log_commands_ai_log_id_ai_logs",
        "ai_log_id",
        "ai_logs",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "ai_log_commands",
        "fk_ai_log_commands_device_id_devices",
        "device_id",
        "devices",
        "id",
    )


def normalize_ai_log_command_items(commands: Any) -> list[Any]:
    if isinstance(commands, list):
        return commands
    if isinstance(commands, dict):
        return [commands]
    if commands is None:
        return []
    return [{"payload": commands}]


def save_ai_log_commands(cursor, ai_log_id: int, commands: Any) -> None:
    for item in normalize_ai_log_command_items(commands):
        payload = item if isinstance(item, dict) else {"payload": item}
        device_id = normalize_device_id(
            payload.get("device_id")
            or payload.get("device")
            or payload.get("type")
            or payload.get("target")
        )
        if device_id is not None:
            _ensure_device(cursor, device_id)
        command = payload.get("command") or payload.get("action")
        value = payload.get("value") or payload.get("state")
        cursor.execute(
            """
            INSERT INTO ai_log_commands (
                ai_log_id, device_id, command, value, payload, created_at
            )
            VALUES (%s, %s, %s, %s, %s, now())
            """,
            (
                ai_log_id,
                device_id,
                str(command) if command is not None else None,
                str(value) if value is not None else None,
                Jsonb(payload),
            ),
        )


def migrate_ai_log_commands_from_legacy(cursor) -> None:
    if not column_exists(cursor, "ai_logs", "commands_json"):
        return
    ensure_jsonb_column(cursor, "ai_logs", "commands_json")
    cursor.execute(
        """
        SELECT id, commands_json
        FROM ai_logs
        WHERE commands_json IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM ai_log_commands
              WHERE ai_log_commands.ai_log_id = ai_logs.id
          )
        ORDER BY id ASC
        """
    )
    for row in cursor.fetchall():
        save_ai_log_commands(cursor, row["id"], row["commands_json"])
    cursor.execute("ALTER TABLE ai_logs DROP COLUMN IF EXISTS commands_json")


def drop_strict_3nf_legacy_objects(cursor) -> None:
    cursor.execute("ALTER TABLE devices DROP COLUMN IF EXISTS status")
    cursor.execute("DROP TABLE IF EXISTS telemetry_raw")
    cursor.execute("DROP TABLE IF EXISTS telemetry_hourly")


def get_strict_3nf_runtime_checks() -> dict[str, Any]:
    return {
        "status": "strict_3nf_model",
        "runtime_uses_telemetry_raw": False,
        "runtime_uses_telemetry_hourly": False,
        "uses_params_json_as_runtime_source": False,
        "uses_commands_json_as_runtime_source": False,
        "uses_devices_status_as_runtime_source": False,
        "agrotech_norm_source": "agrotech_revision_norms",
        "telemetry_source": "telemetry_readings + telemetry_values",
        "hourly_source": "telemetry_hourly_values",
        "ai_commands_source": "ai_log_commands",
        "device_status_source": "device_events",
        "anomaly_catalog_source": "catalog_items",
    }


def get_database_model_summary() -> dict[str, Any]:
    return {
        "status": "strict_3nf_model",
        "note": (
            "Backend использует только нормализованные таблицы. "
            "API-ответы собираются из 3НФ-модели без runtime-обращений к старым таблицам и полям."
        ),
        "catalogs": ["catalog_items"],
        "agrotech": [
            "crops",
            "agrotech_cards",
            "agrotech_card_revisions",
            "agrotech_card_sections",
            "agrotech_revision_norms",
            "agrotech_audit_log",
        ],
        "farm_structure": ["trays", "devices", "device_events"],
        "growing": ["growing_cycles", "cycle_results"],
        "telemetry": ["telemetry_readings", "telemetry_values", "telemetry_hourly_values"],
        "alerts": ["anomaly_events"],
        "ai": [
            "ai_logs",
            "ai_log_commands",
            "advisor_reports",
            "advisor_report_findings",
            "advisor_report_recommendations",
        ],
        "runtime_checks": get_strict_3nf_runtime_checks(),
    }


def row_to_advisor_report(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "cycle_id": row["cycle_id"],
        "card_revision_id": row["card_revision_id"],
        "title": row["title"],
        "summary": row["summary"],
        "content": row["content"],
        "payload": row["payload"],
        "created_at": format_timestamp(row["created_at"]),
    }


def row_to_advisor_report_finding(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "report_id": row["report_id"],
        "metric_id": row["metric_id"],
        "severity_id": row["severity_id"],
        "finding_type": row["finding_type"],
        "message": row["message"],
        "created_at": format_timestamp(row["created_at"]),
    }


def row_to_advisor_report_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "report_id": row["report_id"],
        "metric_id": row["metric_id"],
        "recommendation_text": row["recommendation_text"],
        "proposed_min_value": row["proposed_min_value"],
        "proposed_max_value": row["proposed_max_value"],
        "proposed_target_value": row["proposed_target_value"],
        "status": row["status"],
        "created_at": format_timestamp(row["created_at"]),
    }


def create_advisor_report(
    cycle_id: int | None = None,
    card_revision_id: int | None = None,
    title: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    payload: Any = None,
) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_advisor_reports_schema(cursor)
            cursor.execute(
                """
                INSERT INTO advisor_reports (
                    cycle_id, card_revision_id, title, summary,
                    content, payload, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, now())
                RETURNING id, cycle_id, card_revision_id, title,
                          summary, content, payload, created_at
                """,
                (
                    cycle_id,
                    card_revision_id,
                    title,
                    summary,
                    content,
                    Jsonb(payload) if payload is not None else None,
                ),
            )
            return row_to_advisor_report(cursor.fetchone())


def add_advisor_report_finding(
    report_id: int,
    message: str,
    metric_code: str | None = None,
    severity_code: str | None = None,
    finding_type: str | None = None,
) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_advisor_reports_schema(cursor)
            cursor.execute(
                """
                INSERT INTO advisor_report_findings (
                    report_id, metric_id, severity_id, finding_type, message, created_at
                )
                VALUES (%s, %s, %s, %s, %s, now())
                RETURNING id, report_id, metric_id, severity_id,
                          finding_type, message, created_at
                """,
                (
                    report_id,
                    resolve_catalog_item_id(cursor, "metric", metric_code),
                    resolve_catalog_item_id(cursor, "severity", severity_code),
                    finding_type,
                    message,
                ),
            )
            return row_to_advisor_report_finding(cursor.fetchone())


def add_advisor_report_recommendation(
    report_id: int,
    recommendation_text: str,
    metric_code: str | None = None,
    proposed_min_value: float | None = None,
    proposed_max_value: float | None = None,
    proposed_target_value: float | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_advisor_reports_schema(cursor)
            cursor.execute(
                """
                INSERT INTO advisor_report_recommendations (
                    report_id, metric_id, recommendation_text,
                    proposed_min_value, proposed_max_value,
                    proposed_target_value, status, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                RETURNING id, report_id, metric_id, recommendation_text,
                          proposed_min_value, proposed_max_value,
                          proposed_target_value, status, created_at
                """,
                (
                    report_id,
                    resolve_catalog_item_id(cursor, "metric", metric_code),
                    recommendation_text,
                    proposed_min_value,
                    proposed_max_value,
                    proposed_target_value,
                    status,
                ),
            )
            return row_to_advisor_report_recommendation(cursor.fetchone())


def get_advisor_report(report_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cycle_id, card_revision_id, title,
                       summary, content, payload, created_at
                FROM advisor_reports
                WHERE id = %s
                """,
                (report_id,),
            )
            report = row_to_advisor_report(cursor.fetchone())
            if report is None:
                return None

            cursor.execute(
                """
                SELECT id, report_id, metric_id, severity_id,
                       finding_type, message, created_at
                FROM advisor_report_findings
                WHERE report_id = %s
                ORDER BY id ASC
                """,
                (report_id,),
            )
            findings = [row_to_advisor_report_finding(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT id, report_id, metric_id, recommendation_text,
                       proposed_min_value, proposed_max_value,
                       proposed_target_value, status, created_at
                FROM advisor_report_recommendations
                WHERE report_id = %s
                ORDER BY id ASC
                """,
                (report_id,),
            )
            recommendations = [
                row_to_advisor_report_recommendation(row)
                for row in cursor.fetchall()
            ]

    return {
        "report": report,
        "findings": findings,
        "recommendations": recommendations,
    }


def get_cycle_advisor_reports(cycle_id: int) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cycle_id, card_revision_id, title,
                       summary, content, payload, created_at
                FROM advisor_reports
                WHERE cycle_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (cycle_id,),
            )
            return [row_to_advisor_report(row) for row in cursor.fetchall()]


def calculate_cycle_day_number(
    started_at: datetime | None,
    finished_at: datetime | None,
    status: str | None,
) -> int | None:
    if started_at is None:
        return None

    if status == "finished" and finished_at is not None:
        end_at = finished_at
    else:
        end_at = datetime.now(started_at.tzinfo)

    return max((end_at.date() - started_at.date()).days + 1, 1)


def row_to_growing_cycle(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return {
        "id": row["id"],
        "tray_id": row["tray_id"],
        "status": row["status"],
        "crop_slug": row["crop_slug"],
        "crop_name_ru": row["crop_name_ru"],
        "card_revision_id": row["card_revision_id"],
        "version_label": row.get("version_label") or make_version_label(row["version_major"], row["version_minor"]),
        "started_at": format_timestamp(row["started_at"]),
        "finished_at": format_timestamp(row["finished_at"]) if row["finished_at"] is not None else None,
        "day_number": calculate_cycle_day_number(
            row["started_at"],
            row["finished_at"],
            row["status"],
        ),
    }


def _select_growing_cycle_by_id(cursor, cycle_id: int) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT
            growing_cycles.id,
            growing_cycles.tray_id,
            growing_cycles.status,
            growing_cycles.card_revision_id,
            growing_cycles.started_at,
            growing_cycles.finished_at,
            crops.slug AS crop_slug,
            crops.name_ru AS crop_name_ru,
            agrotech_card_revisions.version_major,
            agrotech_card_revisions.version_minor
        FROM growing_cycles
        JOIN crops ON crops.id = growing_cycles.crop_id
        JOIN agrotech_card_revisions
          ON agrotech_card_revisions.id = growing_cycles.card_revision_id
        WHERE growing_cycles.id = %s
        """,
        (cycle_id,),
    )
    return with_version_label(cursor.fetchone())


def _get_current_growing_cycle(cursor, tray_id: str = DEFAULT_TRAY_ID) -> dict[str, Any] | None:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID
    cursor.execute(
        """
        SELECT
            growing_cycles.id,
            growing_cycles.tray_id,
            growing_cycles.status,
            growing_cycles.card_revision_id,
            growing_cycles.started_at,
            growing_cycles.finished_at,
            crops.slug AS crop_slug,
            crops.name_ru AS crop_name_ru,
            agrotech_card_revisions.version_major,
            agrotech_card_revisions.version_minor
        FROM growing_cycles
        JOIN crops ON crops.id = growing_cycles.crop_id
        JOIN agrotech_card_revisions
          ON agrotech_card_revisions.id = growing_cycles.card_revision_id
        WHERE growing_cycles.tray_id = %s
          AND growing_cycles.status = 'active'
        ORDER BY growing_cycles.started_at DESC, growing_cycles.id DESC
        LIMIT 1
        """,
        (normalized_tray_id,),
    )
    return with_version_label(cursor.fetchone())


def get_available_crops() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    crops.id,
                    crops.slug,
                    crops.name_ru,
                    crops.crop_type,
                    agrotech_cards.id AS card_id,
                    agrotech_card_revisions.id AS active_revision_id,
                    agrotech_card_revisions.version_major,
                    agrotech_card_revisions.version_minor
                FROM crops
                JOIN agrotech_cards ON agrotech_cards.crop_id = crops.id
                JOIN agrotech_card_revisions
                  ON agrotech_card_revisions.card_id = agrotech_cards.id
                 AND agrotech_card_revisions.is_active
                ORDER BY crops.slug
                """
            )
            return [with_version_label(row) for row in cursor.fetchall()]


def get_current_growing_cycle(tray_id: str = DEFAULT_TRAY_ID) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return row_to_growing_cycle(_get_current_growing_cycle(cursor, tray_id))


def get_active_cycle_ai_context(tray_id: str = DEFAULT_TRAY_ID) -> dict[str, Any] | None:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    growing_cycles.id AS cycle_id,
                    growing_cycles.tray_id,
                    growing_cycles.status,
                    growing_cycles.started_at,
                    crops.slug AS crop_slug,
                    crops.name_ru AS crop_name_ru,
                    crops.crop_type,
                    agrotech_cards.id AS card_id,
                    agrotech_card_revisions.id AS revision_id,
                    agrotech_card_revisions.version_major,
                    agrotech_card_revisions.version_minor,
                    agrotech_card_revisions.content
                FROM growing_cycles
                JOIN crops ON crops.id = growing_cycles.crop_id
                LEFT JOIN agrotech_card_revisions
                  ON agrotech_card_revisions.id = growing_cycles.card_revision_id
                LEFT JOIN agrotech_cards
                  ON agrotech_cards.id = agrotech_card_revisions.card_id
                WHERE growing_cycles.tray_id = %s
                  AND growing_cycles.status = 'active'
                ORDER BY growing_cycles.started_at DESC, growing_cycles.id DESC
                LIMIT 1
                """,
                (normalized_tray_id,),
            )
            row = cursor.fetchone()
            norms = {}
            if row is not None:
                row = with_version_label(row)
                norms = get_revision_norms(cursor, row["revision_id"])

    if row is None:
        return None

    return {
        "cycle_id": row["cycle_id"],
        "tray_id": row["tray_id"],
        "status": row["status"],
        "started_at": format_timestamp(row["started_at"]),
        "day_number": calculate_cycle_day_number(row["started_at"], None, row["status"]) or 1,
        "crop_slug": row["crop_slug"],
        "crop_name_ru": row["crop_name_ru"],
        "crop_type": row["crop_type"],
        "card_id": row["card_id"],
        "revision_id": row["revision_id"],
        "version_label": row["version_label"],
        "norms": norms,
        "content": row["content"],
    }


def get_active_cycle_norm_ranges(tray_id: str = DEFAULT_TRAY_ID) -> dict[str, tuple[float, float]]:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    growing_cycles.card_revision_id
                FROM growing_cycles
                LEFT JOIN agrotech_card_revisions
                  ON agrotech_card_revisions.id = growing_cycles.card_revision_id
                WHERE growing_cycles.tray_id = %s
                  AND growing_cycles.status = 'active'
                ORDER BY growing_cycles.started_at DESC, growing_cycles.id DESC
                LIMIT 1
                """,
                (normalized_tray_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return {}

            norms = get_revision_norms(cursor, row["card_revision_id"])

    ranges: dict[str, tuple[float, float]] = {}
    for metric_code in ("air_temp", "humidity", "water_temp", "ph", "ec"):
        value = norms.get(metric_code)
        if not isinstance(value, dict):
            continue
        low = norm_float(value.get("min"))
        high = norm_float(value.get("max"))
        if low is None or high is None:
            continue
        ranges[metric_code] = (low, high)

    return ranges


def start_growing_cycle(
    crop_slug: str,
    tray_id: str = DEFAULT_TRAY_ID,
    notes: str | None = None,
) -> dict[str, Any]:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID
    normalized_crop_slug = str(crop_slug or "").strip()
    if not normalized_crop_slug:
        raise CropNotFoundError("crop_slug is required")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_tray(cursor, normalized_tray_id)

            cursor.execute(
                """
                SELECT id
                FROM crops
                WHERE slug = %s
                """,
                (normalized_crop_slug,),
            )
            crop = cursor.fetchone()
            if crop is None:
                raise CropNotFoundError(f"Crop '{normalized_crop_slug}' not found")

            active_revision = _get_active_card_revision(cursor, normalized_crop_slug)
            if active_revision is None:
                raise ActiveCardRevisionNotFoundError(
                    f"Active agrotech card revision for crop '{normalized_crop_slug}' not found"
                )

            if _get_current_growing_cycle(cursor, normalized_tray_id) is not None:
                raise ActiveGrowingCycleExistsError(
                    f"Tray '{normalized_tray_id}' already has an active growing cycle"
                )

            try:
                cursor.execute(
                    """
                    INSERT INTO growing_cycles (
                        tray_id, crop_id, card_revision_id, status,
                        started_at, notes, created_at
                    )
                    VALUES (%s, %s, %s, 'active', now(), %s, now())
                    RETURNING id
                    """,
                    (
                        normalized_tray_id,
                        active_revision["crop_id"],
                        active_revision["revision_id"],
                        notes,
                    ),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise ActiveGrowingCycleExistsError(
                    f"Tray '{normalized_tray_id}' already has an active growing cycle"
                ) from exc

            created = cursor.fetchone()
            cycle = _select_growing_cycle_by_id(cursor, created["id"])
            return row_to_growing_cycle(cycle)


def finish_growing_cycle(
    tray_id: str = DEFAULT_TRAY_ID,
    notes: str | None = None,
) -> dict[str, Any]:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID

    with get_connection() as connection:
        with connection.cursor() as cursor:
            active_cycle = _get_current_growing_cycle(cursor, normalized_tray_id)
            if active_cycle is None:
                raise NoActiveGrowingCycleError(
                    f"Tray '{normalized_tray_id}' has no active growing cycle"
                )

            cursor.execute(
                """
                UPDATE growing_cycles
                SET status = 'finished',
                    finished_at = now(),
                    notes = COALESCE(%s, notes)
                WHERE id = %s
                RETURNING id
                """,
                (notes, active_cycle["id"]),
            )
            updated = cursor.fetchone()
            cycle = _select_growing_cycle_by_id(cursor, updated["id"])
            return row_to_growing_cycle(cycle)


def init_db() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    last_seen TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ")
            cursor.execute("UPDATE devices SET last_seen = now() WHERE last_seen IS NULL")
            cursor.execute("ALTER TABLE devices ALTER COLUMN last_seen SET DEFAULT now()")
            cursor.execute("ALTER TABLE devices ALTER COLUMN last_seen SET NOT NULL")
            ensure_trays_schema(cursor)
            ensure_tray(cursor, DEFAULT_TRAY_ID)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS anomaly_events (
                    id BIGSERIAL PRIMARY KEY,
                    tray_id TEXT,
                    value DOUBLE PRECISION,
                    message TEXT,
                    payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute(
                "ALTER TABLE anomaly_events ADD COLUMN IF NOT EXISTS value DOUBLE PRECISION"
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_anomaly_events_recent
                ON anomaly_events(tray_id, created_at DESC)
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
            ensure_device_foreign_keys(cursor)
            ensure_agrotech_schema(cursor)
            ensure_agrotech_norms_schema(cursor)
            ensure_base_catalog_items(cursor)
            ensure_device_relationship_columns(cursor)
            ensure_device_events_schema(cursor)
            ensure_telemetry_normalized_schema(cursor)
            ensure_telemetry_hourly_values_schema(cursor)
            _import_crop_cards_from_md(cursor)
            migrate_revision_norms_from_legacy_params_json(cursor)
            backfill_card_sections(cursor)
            drop_agrotech_legacy_columns(cursor)
            ensure_growing_cycles_schema(cursor)
            ensure_anomaly_event_refs_schema(cursor)
            backfill_anomaly_event_refs(cursor)
            drop_anomaly_legacy_columns(cursor)
            ensure_cycle_results_schema(cursor)
            ensure_advisor_reports_schema(cursor)
            ensure_ai_logs_schema(cursor)
            ensure_ai_log_commands_schema(cursor)
            migrate_ai_log_commands_from_legacy(cursor)
            drop_strict_3nf_legacy_objects(cursor)


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
            normalized_device_id = normalize_device_id(device_id)
            if looks_like_tray_id(normalized_device_id):
                ensure_tray(cursor, normalized_device_id)
                return

            _ensure_device(cursor, normalized_device_id)
            tray_id = DEFAULT_TRAY_ID
            _save_device_event(
                cursor,
                device_id=normalized_device_id,
                tray_id=tray_id,
                command="status_update",
                value="online",
                source="status",
                payload={"status": "online"},
            )


def get_recent_device_events(
    tray_id: str = DEFAULT_TRAY_ID,
    hours: int = 24,
    limit: int = 50,
) -> list[dict[str, Any]]:
    normalized_tray_id = normalize_device_id(tray_id) or DEFAULT_TRAY_ID
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    device_events.id,
                    device_events.device_id,
                    device_events.tray_id,
                    catalog_items.code AS event_type,
                    device_events.command,
                    device_events.value,
                    device_events.source,
                    device_events.created_at
                FROM device_events
                LEFT JOIN catalog_items ON catalog_items.id = device_events.event_type_id
                WHERE device_events.tray_id = %s
                  AND device_events.created_at >= now() - (%s * interval '1 hour')
                ORDER BY device_events.created_at DESC, device_events.id DESC
                LIMIT %s
                """,
                (normalized_tray_id, hours, limit),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "device_id": row["device_id"],
            "tray_id": row["tray_id"],
            "event_type": row["event_type"],
            "command": row["command"],
            "value": row["value"],
            "source": row["source"],
            "created_at": format_timestamp(row["created_at"]),
        }
        for row in rows
    ]


def ensure_telemetry_normalized_schema(cursor) -> None:
    ensure_trays_schema(cursor)
    ensure_tray(cursor, DEFAULT_TRAY_ID)
    ensure_base_catalog_items(cursor)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_readings (
            id BIGSERIAL PRIMARY KEY,
            tray_id TEXT NOT NULL,
            sensor_type_id BIGINT,
            topic TEXT NOT NULL,
            raw_payload JSONB NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_values (
            id BIGSERIAL PRIMARY KEY,
            reading_id BIGINT NOT NULL,
            metric_id BIGINT NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(reading_id, metric_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_readings_tray_recorded_at
        ON telemetry_readings(tray_id, recorded_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_readings_topic_recorded_at
        ON telemetry_readings(topic, recorded_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_values_reading_metric
        ON telemetry_values(reading_id, metric_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_values_metric_id
        ON telemetry_values(metric_id)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_readings",
        "fk_telemetry_readings_tray_id_trays",
        "tray_id",
        "trays",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_readings",
        "fk_telemetry_readings_sensor_type_id_catalog_items",
        "sensor_type_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_values",
        "fk_telemetry_values_reading_id_readings",
        "reading_id",
        "telemetry_readings",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_values",
        "fk_telemetry_values_metric_id_catalog_items",
        "metric_id",
        "catalog_items",
        "id",
    )


def infer_sensor_type_code(topic: str | None, payload: Any) -> str:
    topic_text = str(topic or "").strip().lower()
    parsed_payload = json_object_to_dict(payload)

    if topic_text.endswith("/climate"):
        return "climate"
    if topic_text.endswith("/water"):
        return "water"
    if any(key in parsed_payload for key in ("water_temp", "ph", "pH", "ec", "EC")):
        return "water"
    if any(key in parsed_payload for key in ("air_temp", "humidity")):
        return "climate"
    return "mixed"


def save_telemetry_normalized(
    cursor,
    topic: str,
    payload: Any,
    tray_id: Any = None,
    recorded_at: datetime | None = None,
) -> dict[str, Any] | None:
    parsed_payload = json_object_to_dict(payload)
    normalized_tray_id = normalize_device_id(tray_id)
    if normalized_tray_id is None:
        topic_tray_id, _ = parse_topic(topic)
        normalized_tray_id = normalize_device_id(topic_tray_id)
    normalized_tray_id = ensure_tray(cursor, normalized_tray_id or DEFAULT_TRAY_ID)

    sensor_type_code = infer_sensor_type_code(topic, parsed_payload)
    sensor_type_id = get_catalog_item_id(cursor, "sensor_type", sensor_type_code)
    if sensor_type_id is None:
        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[sensor_type_code]
        sensor_type = get_or_create_catalog_item(cursor, "sensor_type", sensor_type_code, name_ru, unit)
        sensor_type_id = sensor_type["id"]

    timestamp_sql = "%s" if recorded_at is not None else "now()"
    params: list[Any] = [
        normalized_tray_id,
        sensor_type_id,
        topic,
        Jsonb(payload),
    ]
    if recorded_at is not None:
        params.append(recorded_at)

    cursor.execute(
        f"""
        INSERT INTO telemetry_readings (
            tray_id, sensor_type_id, topic, raw_payload, recorded_at
        )
        VALUES (%s, %s, %s, %s, {timestamp_sql})
        RETURNING id, tray_id, sensor_type_id, topic, raw_payload, recorded_at, created_at
        """,
        params,
    )
    reading = cursor.fetchone()

    metric_values = {
        "air_temp": number_or_none(parsed_payload.get("air_temp")),
        "humidity": number_or_none(parsed_payload.get("humidity")),
        "water_temp": number_or_none(parsed_payload.get("water_temp")),
        "ph": number_or_none(parsed_payload.get("ph", parsed_payload.get("pH"))),
        "ec": number_or_none(parsed_payload.get("ec", parsed_payload.get("EC"))),
    }
    for metric_code, metric_value in metric_values.items():
        if metric_value is None:
            continue
        metric_id = get_catalog_item_id(cursor, "metric", metric_code)
        if metric_id is None:
            _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[metric_code]
            metric = get_or_create_catalog_item(cursor, "metric", metric_code, name_ru, unit)
            metric_id = metric["id"]
        cursor.execute(
            """
            INSERT INTO telemetry_values (reading_id, metric_id, value)
            VALUES (%s, %s, %s)
            ON CONFLICT (reading_id, metric_id) DO UPDATE SET
                value = EXCLUDED.value
            """,
            (reading["id"], metric_id, metric_value),
        )

    return reading


def ensure_telemetry_hourly_values_schema(cursor) -> None:
    ensure_trays_schema(cursor)
    ensure_tray(cursor, DEFAULT_TRAY_ID)
    ensure_base_catalog_items(cursor)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_hourly_values (
            id BIGSERIAL PRIMARY KEY,
            tray_id TEXT NOT NULL,
            sensor_type_id BIGINT,
            metric_id BIGINT NOT NULL,
            hour_start TIMESTAMPTZ NOT NULL,
            avg_value DOUBLE PRECISION,
            min_value DOUBLE PRECISION,
            max_value DOUBLE PRECISION,
            count_value INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(tray_id, sensor_type_id, metric_id, hour_start)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_values_tray_hour
        ON telemetry_hourly_values(tray_id, hour_start DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_values_metric_hour
        ON telemetry_hourly_values(metric_id, hour_start DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_values_sensor_hour
        ON telemetry_hourly_values(sensor_type_id, hour_start DESC)
        """
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_hourly_values",
        "fk_telemetry_hourly_values_tray_id_trays",
        "tray_id",
        "trays",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_hourly_values",
        "fk_telemetry_hourly_values_sensor_type_id_catalog_items",
        "sensor_type_id",
        "catalog_items",
        "id",
    )
    add_foreign_key_if_missing(
        cursor,
        "telemetry_hourly_values",
        "fk_telemetry_hourly_values_metric_id_catalog_items",
        "metric_id",
        "catalog_items",
        "id",
    )


def save_hourly_value(
    cursor,
    tray_id: Any,
    sensor_type_code: str | None,
    metric_code: str,
    hour_start: datetime,
    avg_value: Any,
    min_value: Any,
    max_value: Any,
    count_value: Any,
) -> None:
    normalized_tray_id = ensure_tray(cursor, tray_id or DEFAULT_TRAY_ID)
    normalized_sensor_type_code = normalize_device_id(sensor_type_code) or "mixed"
    if normalized_sensor_type_code not in {"climate", "water", "mixed"}:
        normalized_sensor_type_code = "mixed"
    sensor_type_id = get_catalog_item_id(cursor, "sensor_type", normalized_sensor_type_code)
    if sensor_type_id is None:
        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE.get(
            normalized_sensor_type_code,
            ("sensor_type", normalized_sensor_type_code, normalized_sensor_type_code, None),
        )
        sensor_type = get_or_create_catalog_item(
            cursor,
            "sensor_type",
            normalized_sensor_type_code,
            name_ru,
            unit,
        )
        sensor_type_id = sensor_type["id"]

    metric_id = get_catalog_item_id(cursor, "metric", metric_code)
    if metric_id is None:
        _, _, name_ru, unit = BASE_CATALOG_ITEM_BY_CODE[metric_code]
        metric = get_or_create_catalog_item(cursor, "metric", metric_code, name_ru, unit)
        metric_id = metric["id"]

    cursor.execute(
        """
        INSERT INTO telemetry_hourly_values (
            tray_id, sensor_type_id, metric_id, hour_start,
            avg_value, min_value, max_value, count_value, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, 0), now())
        ON CONFLICT (tray_id, sensor_type_id, metric_id, hour_start) DO UPDATE SET
            avg_value = EXCLUDED.avg_value,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            count_value = EXCLUDED.count_value,
            updated_at = now()
        """,
        (
            normalized_tray_id,
            sensor_type_id,
            metric_id,
            hour_start,
            avg_value,
            min_value,
            max_value,
            count_value,
        ),
    )


def save_hourly_values_from_row(cursor, row: dict[str, Any]) -> None:
    for metric_code in ("air_temp", "humidity", "water_temp", "ph", "ec"):
        save_hourly_value(
            cursor,
            row["tray_id"],
            row.get("sensor_type") or "mixed",
            metric_code,
            row["hour_start"],
            row.get(f"{metric_code}_avg"),
            row.get(f"{metric_code}_min"),
            row.get(f"{metric_code}_max"),
            row.get(f"{metric_code}_count") or 0,
        )


def save_telemetry(topic: str, payload: str, recorded_at: datetime | None = None) -> None:
    parsed_value = parse_json_value(payload)
    tray_id, _ = parse_topic(topic)
    tray_id = normalize_device_id(tray_id)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_tray(cursor, tray_id or DEFAULT_TRAY_ID)
            save_telemetry_normalized(
                cursor,
                topic,
                parsed_value,
                tray_id=tray_id,
                recorded_at=recorded_at,
            )


def save_ai_log(
    thought: str,
    commands: Any,
    cycle_id: int | None = None,
    tray_id: str = DEFAULT_TRAY_ID,
    source: str | None = None,
) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_ai_logs_schema(cursor)
            ensure_ai_log_commands_schema(cursor)
            resolved_cycle_id = cycle_id
            if resolved_cycle_id is None:
                resolved_cycle_id = get_active_cycle_id_for_tray(cursor, tray_id)
            cursor.execute(
                """
                INSERT INTO ai_logs (timestamp, thought, cycle_id, source)
                VALUES (now(), %s, %s, %s)
                RETURNING id
                """,
                (thought, resolved_cycle_id, source),
            )
            row = cursor.fetchone()
            save_ai_log_commands(cursor, row["id"], commands)


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


def build_payload_from_telemetry_values(cursor, reading_id: int) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT catalog_items.code, telemetry_values.value
        FROM telemetry_values
        JOIN catalog_items ON catalog_items.id = telemetry_values.metric_id
        WHERE telemetry_values.reading_id = %s
          AND catalog_items.category = 'metric'
        ORDER BY catalog_items.code
        """,
        (reading_id,),
    )
    return {row["code"]: row["value"] for row in cursor.fetchall()}


def row_to_normalized_telemetry_record(
    row: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload_string = json_value_to_api_string(payload)
    return {
        "id": row["id"],
        "topic": row["topic"],
        "payload": payload_string,
        "timestamp": format_timestamp(row["recorded_at"]),
        "parsed_payload": payload,
    }


def get_recent_telemetry(limit: int = 15) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, topic, recorded_at
                FROM telemetry_readings
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                row_to_normalized_telemetry_record(
                    row,
                    build_payload_from_telemetry_values(cursor, row["id"]),
                )
                for row in reversed(rows)
            ]


def get_last_climate_records(limit: int = 3) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT telemetry_readings.id, telemetry_readings.topic, telemetry_readings.recorded_at
                FROM telemetry_readings
                LEFT JOIN catalog_items
                  ON catalog_items.id = telemetry_readings.sensor_type_id
                 AND catalog_items.category = 'sensor_type'
                WHERE catalog_items.code = 'climate'
                   OR telemetry_readings.topic = %s
                   OR telemetry_readings.topic LIKE %s
                ORDER BY telemetry_readings.id DESC
                LIMIT %s
                """,
                (CLIMATE_TOPIC, "%/climate", limit),
            )
            rows = cursor.fetchall()
            records: list[dict[str, Any]] = []
            for row in reversed(rows):
                record = row_to_normalized_telemetry_record(
                    row,
                    build_payload_from_telemetry_values(cursor, row["id"]),
                )
                record["recorded_at"] = row["recorded_at"]
                if isinstance(record.get("parsed_payload"), dict):
                    records.append(record)
            return records


def get_last_water_records(limit: int = 3) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT telemetry_readings.id, telemetry_readings.topic, telemetry_readings.recorded_at
                FROM telemetry_readings
                LEFT JOIN catalog_items
                  ON catalog_items.id = telemetry_readings.sensor_type_id
                 AND catalog_items.category = 'sensor_type'
                WHERE catalog_items.code = 'water'
                   OR telemetry_readings.topic = %s
                   OR telemetry_readings.topic LIKE %s
                ORDER BY telemetry_readings.id DESC
                LIMIT %s
                """,
                (WATER_TOPIC, "%/water", limit),
            )
            rows = cursor.fetchall()
            records: list[dict[str, Any]] = []
            for row in reversed(rows):
                record = row_to_normalized_telemetry_record(
                    row,
                    build_payload_from_telemetry_values(cursor, row["id"]),
                )
                record["recorded_at"] = row["recorded_at"]
                if isinstance(record.get("parsed_payload"), dict):
                    records.append(record)
            return records


def get_recent_ai_logs(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, timestamp, thought, cycle_id, source
                FROM ai_logs
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            log_ids = [row["id"] for row in rows]
            commands_by_log_id: dict[int, list[dict[str, Any]]] = {log_id: [] for log_id in log_ids}
            if log_ids:
                cursor.execute(
                    """
                    SELECT ai_log_id, device_id, command, value, payload
                    FROM ai_log_commands
                    WHERE ai_log_id = ANY(%s)
                    ORDER BY id ASC
                    """,
                    (log_ids,),
                )
                for command_row in cursor.fetchall():
                    payload = command_row["payload"] if isinstance(command_row["payload"], dict) else {}
                    item = dict(payload)
                    if command_row["device_id"] is not None:
                        item.setdefault("device_id", command_row["device_id"])
                    if command_row["command"] is not None:
                        item.setdefault("command", command_row["command"])
                    if command_row["value"] is not None:
                        item.setdefault("value", command_row["value"])
                    commands_by_log_id.setdefault(command_row["ai_log_id"], []).append(item)

    return [
        {
            "id": row["id"],
            "timestamp": format_timestamp(row["timestamp"]),
            "thought": row["thought"],
            "commands_json": json_value_to_api_string(commands_by_log_id.get(row["id"], [])),
            "commands": commands_by_log_id.get(row["id"], []),
            "cycle_id": row["cycle_id"],
            "source": row["source"],
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
            metric_map = {
                "temperature": "air_temp",
                "humidity": "humidity",
                "water_temp": "water_temp",
                "ph": "ph",
                "ec": "ec",
            }
            for result_key, metric_code in metric_map.items():
                cursor.execute(
                    """
                    SELECT telemetry_values.value
                    FROM telemetry_values
                    JOIN telemetry_readings ON telemetry_readings.id = telemetry_values.reading_id
                    JOIN catalog_items ON catalog_items.id = telemetry_values.metric_id
                    WHERE catalog_items.category = 'metric'
                      AND catalog_items.code = %s
                    ORDER BY telemetry_readings.recorded_at DESC, telemetry_readings.id DESC
                    LIMIT 1
                    """,
                    (metric_code,),
                )
                row = cursor.fetchone()
                if row:
                    result[result_key] = row["value"]

    return result


def build_hourly_summary_rows_from_values(hours: int = 24) -> list[dict[str, Any]]:
    metric_codes = ("air_temp", "humidity", "water_temp", "ph", "ec")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    telemetry_hourly_values.tray_id,
                    COALESCE(sensor_types.code, 'mixed') AS sensor_type,
                    telemetry_hourly_values.hour_start,
                    metrics.code AS metric_code,
                    telemetry_hourly_values.avg_value,
                    telemetry_hourly_values.min_value,
                    telemetry_hourly_values.max_value,
                    telemetry_hourly_values.count_value
                FROM telemetry_hourly_values
                JOIN catalog_items AS metrics
                  ON metrics.id = telemetry_hourly_values.metric_id
                 AND metrics.category = 'metric'
                LEFT JOIN catalog_items AS sensor_types
                  ON sensor_types.id = telemetry_hourly_values.sensor_type_id
                 AND sensor_types.category = 'sensor_type'
                WHERE telemetry_hourly_values.hour_start >= now() - (%s * interval '1 hour')
                  AND metrics.code = ANY(%s)
                ORDER BY telemetry_hourly_values.hour_start ASC,
                         telemetry_hourly_values.tray_id ASC,
                         sensor_type ASC,
                         metrics.code ASC
                """,
                (hours, list(metric_codes)),
            )
            rows = cursor.fetchall()

    summaries: dict[tuple[Any, str, Any], dict[str, Any]] = {}
    for row in rows:
        key = (row["hour_start"], row["tray_id"], row["sensor_type"])
        summary = summaries.setdefault(
            key,
            {
                "tray_id": row["tray_id"],
                "sensor_type": row["sensor_type"],
                "hour_start": row["hour_start"],
            },
        )
        metric_code = row["metric_code"]
        summary[f"{metric_code}_avg"] = row["avg_value"]
        summary[f"{metric_code}_min"] = row["min_value"]
        summary[f"{metric_code}_max"] = row["max_value"]
        summary[f"{metric_code}_count"] = row["count_value"]

    result: list[dict[str, Any]] = []
    for summary in summaries.values():
        for metric_code in metric_codes:
            summary.setdefault(f"{metric_code}_avg", None)
            summary.setdefault(f"{metric_code}_min", None)
            summary.setdefault(f"{metric_code}_max", None)
            summary.setdefault(f"{metric_code}_count", 0)
        result.append(summary)
    return result


def get_hourly_history(metric_name: str, hours: int = 24) -> list[dict[str, Any]]:
    metric_config = {
        "temperature": "air_temp",
        "humidity": "humidity",
        "water_temp": "water_temp",
        "ph": "ph",
        "ec": "ec",
    }
    if metric_name not in metric_config:
        raise ValueError(f"Unknown metric: {metric_name}")

    metric_code = metric_config[metric_name]
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    telemetry_hourly_values.hour_start,
                    ROUND(telemetry_hourly_values.avg_value::numeric, 2) AS avg_value
                FROM telemetry_hourly_values
                JOIN catalog_items
                  ON catalog_items.id = telemetry_hourly_values.metric_id
                 AND catalog_items.category = 'metric'
                WHERE telemetry_hourly_values.hour_start >= now() - (%s * interval '1 hour')
                  AND catalog_items.code = %s
                  AND telemetry_hourly_values.avg_value IS NOT NULL
                ORDER BY telemetry_hourly_values.hour_start ASC
                """,
                (hours, metric_code),
            )
            rows = cursor.fetchall()

    return [
        {
            "hour": format_timestamp(row["hour_start"])[:13] + ":00",
            "avg_value": float(row["avg_value"]) if row["avg_value"] is not None else None,
        }
        for row in rows
    ]


def get_new_hourly_value_rows_from_normalized(cursor) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT 1
        FROM telemetry_readings
        JOIN telemetry_values ON telemetry_values.reading_id = telemetry_readings.id
        LIMIT 1
        """
    )
    if cursor.fetchone() is None:
        return []

    cursor.execute(
        """
        SELECT
            telemetry_readings.tray_id,
            COALESCE(sensor_types.code, 'mixed') AS sensor_type,
            date_trunc('hour', telemetry_readings.recorded_at) AS hour_start,
            metrics.code AS metric_code,
            AVG(telemetry_values.value) AS avg_value,
            MIN(telemetry_values.value) AS min_value,
            MAX(telemetry_values.value) AS max_value,
            COUNT(telemetry_values.value)::integer AS count_value
        FROM telemetry_readings
        JOIN telemetry_values ON telemetry_values.reading_id = telemetry_readings.id
        JOIN catalog_items AS metrics
          ON metrics.id = telemetry_values.metric_id
         AND metrics.category = 'metric'
        LEFT JOIN catalog_items AS sensor_types
          ON sensor_types.id = telemetry_readings.sensor_type_id
         AND sensor_types.category = 'sensor_type'
        WHERE telemetry_readings.recorded_at < date_trunc('hour', now())
          AND metrics.code = ANY(%s)
          AND NOT EXISTS (
              SELECT 1
              FROM telemetry_hourly_values
              JOIN catalog_items AS existing_metrics
                ON existing_metrics.id = telemetry_hourly_values.metric_id
               AND existing_metrics.category = 'metric'
              LEFT JOIN catalog_items AS existing_sensor_types
                ON existing_sensor_types.id = telemetry_hourly_values.sensor_type_id
               AND existing_sensor_types.category = 'sensor_type'
              WHERE telemetry_hourly_values.tray_id = telemetry_readings.tray_id
                AND COALESCE(existing_sensor_types.code, 'mixed') = COALESCE(sensor_types.code, 'mixed')
                AND existing_metrics.code = metrics.code
                AND telemetry_hourly_values.hour_start = date_trunc('hour', telemetry_readings.recorded_at)
          )
        GROUP BY
            telemetry_readings.tray_id,
            COALESCE(sensor_types.code, 'mixed'),
            date_trunc('hour', telemetry_readings.recorded_at),
            metrics.code
        ORDER BY hour_start ASC, telemetry_readings.tray_id ASC, sensor_type ASC, metrics.code ASC
        """,
        (["air_temp", "humidity", "water_temp", "ph", "ec"],),
    )
    return cursor.fetchall()


def aggregate_completed_hours() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            rows = get_new_hourly_value_rows_from_normalized(cursor)

            for row in rows:
                save_hourly_value(
                    cursor,
                    row["tray_id"],
                    row["sensor_type"],
                    row["metric_code"],
                    row["hour_start"],
                    row["avg_value"],
                    row["min_value"],
                    row["max_value"],
                    row["count_value"],
                )

            return len(rows)


def delete_old_raw_data(retention_hours: int = 24) -> int:
    # Kept only for backward-compatible scheduler/API calls; strict 3NF runtime does not use raw telemetry.
    return 0


def save_anomaly_event(
    *,
    tray_id: str | None,
    metric_name: str | None,
    severity: str,
    value: float | None,
    message: str,
    event_type: str,
    sensor_type: str | None = None,
    payload: dict[str, Any] | None = None,
    cooldown_minutes: int = 5,
) -> bool:
    normalized_tray_id = normalize_device_id(tray_id) or "unknown"
    with get_connection() as connection:
        with connection.cursor() as cursor:
            ensure_tray(cursor, normalized_tray_id)
            sensor_type_id = resolve_catalog_item_id(cursor, "sensor_type", sensor_type)
            event_type_id = resolve_catalog_item_id(cursor, "anomaly_type", event_type)
            metric_id = resolve_catalog_item_id(cursor, "metric", metric_name)
            severity_id = resolve_catalog_item_id(cursor, "severity", severity)
            cycle_id = get_active_cycle_id_for_tray(cursor, normalized_tray_id)
            cursor.execute(
                """
                WITH recent_duplicate AS (
                    SELECT 1
                    FROM anomaly_events
                    WHERE tray_id = %s
                      AND event_type_id IS NOT DISTINCT FROM %s
                      AND metric_id IS NOT DISTINCT FROM %s
                      AND created_at >= now() - (%s * interval '1 minute')
                    LIMIT 1
                )
                INSERT INTO anomaly_events (
                    tray_id, value, message, payload,
                    sensor_type_id, event_type_id, metric_id, severity_id, cycle_id,
                    created_at
                )
                SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, now()
                WHERE NOT EXISTS (SELECT 1 FROM recent_duplicate)
                RETURNING id
                """,
                (
                    normalized_tray_id,
                    event_type_id,
                    metric_id,
                    cooldown_minutes,
                    normalized_tray_id,
                    value,
                    message,
                    Jsonb(payload or {}),
                    sensor_type_id,
                    event_type_id,
                    metric_id,
                    severity_id,
                    cycle_id,
                ),
            )
            return cursor.fetchone() is not None


def get_recent_anomaly_events(hours: int = 24) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    anomaly_events.id,
                    anomaly_events.tray_id,
                    sensor_types.code AS sensor_type,
                    event_types.code AS event_type,
                    metrics.code AS metric_name,
                    severities.code AS severity,
                    anomaly_events.value,
                    anomaly_events.message,
                    anomaly_events.payload,
                    anomaly_events.created_at
                FROM anomaly_events
                LEFT JOIN catalog_items AS sensor_types
                  ON sensor_types.id = anomaly_events.sensor_type_id
                 AND sensor_types.category = 'sensor_type'
                LEFT JOIN catalog_items AS event_types
                  ON event_types.id = anomaly_events.event_type_id
                 AND event_types.category = 'anomaly_type'
                LEFT JOIN catalog_items AS metrics
                  ON metrics.id = anomaly_events.metric_id
                 AND metrics.category = 'metric'
                LEFT JOIN catalog_items AS severities
                  ON severities.id = anomaly_events.severity_id
                 AND severities.category = 'severity'
                WHERE anomaly_events.created_at >= now() - (%s * interval '1 hour')
                ORDER BY anomaly_events.created_at DESC, anomaly_events.id DESC
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


def get_recent_system_feed_events(limit: int = 15) -> list[dict[str, Any]]:
    normalized_limit = max(1, min(int(limit), 100))
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM (
                    SELECT
                        'anomaly' AS feed_type,
                        anomaly_events.id,
                        NULL::TEXT AS device_id,
                        event_types.code AS event_type,
                        NULL::TEXT AS command,
                        COALESCE(severities.code, 'warning') AS severity,
                        anomaly_events.message,
                        anomaly_events.created_at
                    FROM anomaly_events
                    LEFT JOIN catalog_items AS event_types
                      ON event_types.id = anomaly_events.event_type_id
                     AND event_types.category = 'anomaly_type'
                    LEFT JOIN catalog_items AS severities
                      ON severities.id = anomaly_events.severity_id
                     AND severities.category = 'severity'

                    UNION ALL

                    SELECT
                        'device' AS feed_type,
                        device_events.id,
                        device_events.device_id,
                        event_types.code AS event_type,
                        device_events.command,
                        'info' AS severity,
                        NULL::TEXT AS message,
                        device_events.created_at
                    FROM device_events
                    LEFT JOIN catalog_items AS event_types
                      ON event_types.id = device_events.event_type_id
                     AND event_types.category = 'event_type'
                ) AS feed
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (normalized_limit,),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "feed_type": row["feed_type"],
            "device_id": row["device_id"],
            "event_type": row["event_type"],
            "command": row["command"],
            "severity": row["severity"],
            "message": row["message"],
            "created_at": format_timestamp(row["created_at"]),
        }
        for row in rows
    ]


def get_recent_hourly_summary(hours: int = 24) -> list[dict[str, Any]]:
    normalized_rows = build_hourly_summary_rows_from_values(hours)
    return [
        {
            **row,
            "hour_start": format_timestamp(row["hour_start"]),
        }
        for row in normalized_rows
    ]


def clear_telemetry_raw() -> None:
    # Kept only for backward-compatible seed scripts; strict 3NF runtime does not use raw telemetry.
    return None
