# -*- coding: utf-8 -*-
"""Create a dev/demo cycle with an applied AgroTechCard learning result.

Run from the project root:
    python backend/dev_seed_learning_result.py [crop_slug]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from db import (  # noqa: E402
    apply_agrotech_revision_proposal,
    build_cycle_analysis_report,
    finish_growing_cycle_with_result,
    get_active_card_revision,
    get_available_crops,
    get_cycle_source_revision_context,
    init_db,
    save_agrotech_revision_proposal,
    save_anomaly_event,
    save_cycle_ai_analysis,
    save_cycle_analysis_report,
    save_ph_dosing_event,
    save_telemetry,
    start_growing_cycle,
)


AI_CONCLUSION = (
    "В ходе цикла pH периодически опускался ниже целевой зоны, контроллер "
    "компенсировал отклонения с помощью микродоз pH Up. EC большую часть времени "
    "был ниже рекомендуемого диапазона. Оператор не отметил критичных проблем, "
    "урожай признан пригодным. Цикл подходит для уточнения параметров в АгроТехКарте."
)

PH_REASON = "Стабильнее удерживался около середины диапазона"
EC_REASON = "Частые занижения без критичного влияния на результат"
CONTROL_REASON = "На 1–2 дне чаще наблюдались отклонения"


class DemoSeedError(RuntimeError):
    pass


def choose_crop_slug(requested_slug: str | None, crops: list[dict[str, Any]]) -> str:
    if not crops:
        raise DemoSeedError("No crops found. Run the regular project seed first.")

    available_slugs = [str(crop.get("slug") or "").strip() for crop in crops if crop.get("slug")]
    if requested_slug:
        if requested_slug in available_slugs:
            return requested_slug
        raise DemoSeedError(
            "Crop slug not found: "
            f"{requested_slug}\nAvailable crops: {', '.join(available_slugs)}"
        )

    return "mint" if "mint" in available_slugs else available_slugs[0]


def number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def norm_range(norms: dict[str, Any], key: str, fallback_low: float, fallback_high: float) -> tuple[float, float]:
    value = norms.get(key) if isinstance(norms, dict) else None
    if isinstance(value, dict):
        low = number(value.get("min"))
        high = number(value.get("max"))
        if low is not None and high is not None:
            return low, high
    return fallback_low, fallback_high


def range_text(value: tuple[float, float]) -> str:
    return f"{value[0]:g}–{value[1]:g}"


def adjusted_range(
    source: tuple[float, float],
    preferred: tuple[float, float],
    *,
    fallback_delta: float,
) -> tuple[float, float]:
    if source != preferred:
        return preferred
    low, high = source
    return round(low + fallback_delta, 2), round(high - fallback_delta, 2)


def make_demo_payload() -> dict[str, Any]:
    return {
        "harvest_status": "suitable",
        "harvest_mass_grams": 180,
        "completion_reason": "planned",
        "problem_severity": "minor",
        "problem_phase": "early",
        "plant_appearance": {"healthy": True, "demo": True},
        "cycle_problems": {
            "demo": True,
            "solution": {
                "ph_out_of_range": True,
                "ec_out_of_range": True,
                "weak_growth": False,
            },
        },
        "manual_actions": {"ph_adjustment": True, "nutrient_adjustment": False},
        "followed_ai_advice": "yes",
        "ai_advice_helpfulness": "yes",
        "operator_comment": (
            "DEV DEMO: урожай пригоден, pH/EC отклонения учтены для обучения "
            "АгроТехКарты."
        ),
    }


def save_demo_telemetry(tray_id: str) -> None:
    water_samples = [
        {"ph": 6.1, "ec": 1.4, "water_temp": 20.2},
        {"ph": 6.4, "ec": 1.7, "water_temp": 20.4},
        {"ph": 6.8, "ec": 2.0, "water_temp": 20.5},
    ]
    climate_samples = [
        {"air_temp": 21.0, "humidity": 54},
        {"air_temp": 22.3, "humidity": 61},
        {"air_temp": 24.1, "humidity": 68},
    ]

    for water, climate in zip(water_samples, climate_samples):
        save_telemetry(
            f"farm/{tray_id}/sensors/water",
            json.dumps(water, ensure_ascii=False),
        )
        save_telemetry(
            f"farm/{tray_id}/sensors/climate",
            json.dumps(climate, ensure_ascii=False),
        )
        time.sleep(0.02)


def save_demo_ph_dosing(tray_id: str, cycle_id: int) -> None:
    for index in range(3):
        save_ph_dosing_event(
            tray_id=tray_id,
            cycle_id=cycle_id,
            status="executed",
            action="dose",
            pump_id="ph_up",
            reason="ph_below_target",
            current_ph=6.1 + index * 0.05,
            target_ph=6.5,
            tolerance=0.1,
            target_min=6.3,
            target_max=6.7,
            duration_ms=500,
            mqtt_topic=f"farm/{tray_id}/actuators/ph",
            mqtt_payload={"demo": True, "pump_id": "ph_up", "duration_ms": 500},
        )
        time.sleep(0.02)


def save_demo_alerts(tray_id: str, cycle_id: int) -> None:
    for value in (6.1, 6.2):
        save_anomaly_event(
            tray_id=tray_id,
            metric_name="ph",
            severity="warning",
            value=value,
            message="DEV DEMO: pH ниже целевой зоны",
            event_type="ph_low",
            sensor_type="water",
            payload={"demo": True, "cycle_id": cycle_id},
            cooldown_minutes=0,
        )

    for value in (1.4, 1.5, 1.45):
        save_anomaly_event(
            tray_id=tray_id,
            metric_name="ec",
            severity="warning",
            value=value,
            message="DEV DEMO: EC ниже рекомендуемого диапазона",
            event_type="ec_low",
            sensor_type="water",
            payload={"demo": True, "cycle_id": cycle_id},
            cooldown_minutes=0,
        )


def build_proposal_payload(source_revision: dict[str, Any]) -> dict[str, Any]:
    norms = source_revision.get("norms") if isinstance(source_revision.get("norms"), dict) else {}
    source_ph = norm_range(norms, "ph", 6.2, 6.8)
    source_ec = norm_range(norms, "ec", 1.6, 2.2)
    target_ph = adjusted_range(source_ph, (6.3, 6.7), fallback_delta=0.05)
    target_ec = adjusted_range(source_ec, (1.5, 2.1), fallback_delta=0.1)

    source_content = str(source_revision.get("content") or "").strip()
    proposed_content = (
        source_content
        + "\n\n## DEV DEMO: рекомендации контроля\n"
        + "- Усилить контроль в начале цикла: pH и EC проверять чаще на 1–2 дне; "
        + "корректировки выполнять малыми шагами с повторным измерением.\n"
    ).strip()

    return {
        "proposed_norms": {
            "ph": {"min": target_ph[0], "max": target_ph[1]},
            "ec": {"min": target_ec[0], "max": target_ec[1]},
        },
        "proposed_content": proposed_content,
        "proposed_changes": [
            {
                "parameter": "pH",
                "metric": "ph",
                "section": "solution",
                "change_type": "adjust_norm",
                "old_value": range_text(source_ph),
                "new_value": range_text(target_ph),
                "reason": PH_REASON,
                "priority": "high",
            },
            {
                "parameter": "EC",
                "metric": "ec",
                "section": "solution",
                "change_type": "adjust_norm",
                "old_value": range_text(source_ec),
                "new_value": range_text(target_ec),
                "reason": EC_REASON,
                "priority": "high",
            },
            {
                "parameter": "Рекомендация контроля",
                "section": "recommendations_control",
                "change_type": "clarify_instruction",
                "old_value": "Периодический ручной контроль",
                "new_value": "Усилить контроль в начале цикла",
                "reason": CONTROL_REASON,
                "priority": "medium",
            },
        ],
    }


def fetch_learning_result_preview(cycle_id: int) -> dict[str, Any] | None:
    url = f"http://127.0.0.1:8000/api/cycles/{cycle_id}/learning-result"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Endpoint preview unavailable: {exc}")
        return None


def create_demo_learning_result(crop_slug: str) -> dict[str, Any]:
    active_revision = get_active_card_revision(crop_slug)
    if active_revision is None:
        raise DemoSeedError(f"Active AgroTechCard revision for crop '{crop_slug}' was not found.")

    tray_id = f"demo_learning_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    cycle = start_growing_cycle(
        crop_slug,
        tray_id=tray_id,
        notes="DEV DEMO learning-result seed. Safe to ignore.",
    )
    cycle_id = int(cycle["id"])

    save_demo_telemetry(tray_id)
    save_demo_ph_dosing(tray_id, cycle_id)
    save_demo_alerts(tray_id, cycle_id)

    finish_growing_cycle_with_result(
        tray_id=tray_id,
        result_payload=make_demo_payload(),
        notes="DEV DEMO learning-result seed finished.",
    )

    built_report = build_cycle_analysis_report(cycle_id)
    report = save_cycle_analysis_report(
        cycle_id,
        built_report["report_payload"],
        built_report.get("summary_text"),
    )
    analysis = save_cycle_ai_analysis(
        cycle_id=cycle_id,
        analysis_report_id=int(report["id"]),
        summary=AI_CONCLUSION,
        main_findings=[
            {
                "metric": "ph",
                "finding": "pH периодически опускался ниже целевой зоны.",
                "demo": True,
            },
            {
                "metric": "ec",
                "finding": "EC большую часть времени был ниже рекомендуемого диапазона.",
                "demo": True,
            },
        ],
        recommendation_review=[],
        potential_improvements=[
            {
                "parameter": "pH",
                "proposal": "Сузить диапазон pH до более стабильной зоны.",
                "demo": True,
            },
            {
                "parameter": "EC",
                "proposal": "Скорректировать EC по фактической динамике цикла.",
                "demo": True,
            },
        ],
        should_propose_new_revision=True,
        revision_reason="DEV DEMO: цикл подходит для уточнения норм pH, EC и контроля.",
        confidence="high",
        status="completed",
        model_name="dev_seed",
        prompt_version="dev_seed_learning_result_v1",
        raw_response={"source": "dev_seed_learning_result", "demo": True},
    )

    source_revision = get_cycle_source_revision_context(cycle_id)
    if source_revision is None:
        raise DemoSeedError(f"Could not resolve source AgroTechCard revision for cycle {cycle_id}.")

    proposal_payload = build_proposal_payload(source_revision)
    proposal = save_agrotech_revision_proposal(
        cycle_id=cycle_id,
        analysis_id=int(analysis["id"]),
        card_id=int(source_revision["card_id"]),
        crop_id=int(source_revision["crop_id"]),
        source_revision_id=int(source_revision["source_revision_id"]),
        proposed_version_major=int(source_revision["version_major"] or 1),
        proposed_version_minor=int(source_revision["version_minor"] or 0) + 1,
        proposed_content=proposal_payload["proposed_content"],
        proposed_norms=proposal_payload["proposed_norms"],
        proposed_changes=proposal_payload["proposed_changes"],
        ai_reasoning="DEV DEMO: сформирована проверочная новая версия АгроТехКарты.",
        status="generated",
        auto_apply_eligible=True,
        safety_notes=["DEV DEMO data; created by backend/dev_seed_learning_result.py"],
        raw_response={"source": "dev_seed_learning_result", "demo": True},
    )

    apply_result = apply_agrotech_revision_proposal(int(proposal["id"]), force=True)
    applied_proposal = apply_result.get("proposal") or proposal
    created_revision = apply_result.get("created_revision") or apply_result.get("existing_revision")

    preview = fetch_learning_result_preview(cycle_id)
    if preview is None:
        preview = {
            "has_changes": bool(applied_proposal.get("applied_revision_id")),
            "can_open_details": bool(applied_proposal.get("applied_revision_id")),
            "changes": proposal_payload["proposed_changes"],
        }

    return {
        "crop_slug": crop_slug,
        "crop_name_ru": active_revision.get("crop_name_ru"),
        "cycle_id": cycle_id,
        "proposal_id": int(applied_proposal["id"]),
        "applied_revision_id": applied_proposal.get("applied_revision_id"),
        "created_revision": created_revision,
        "preview": preview,
    }


def main() -> int:
    requested_slug = sys.argv[1].strip() if len(sys.argv) > 1 else None
    try:
        init_db()
        crops = get_available_crops()
        crop_slug = choose_crop_slug(requested_slug, crops)
        result = create_demo_learning_result(crop_slug)
    except Exception as exc:
        print("Failed to create demo learning result.")
        print(str(exc))
        return 1

    preview = result["preview"] or {}
    changes = preview.get("changes") if isinstance(preview.get("changes"), list) else []
    print("Demo learning result created.")
    print(f"crop: {result['crop_slug']}")
    print(f"cycle_id: {result['cycle_id']}")
    print(f"proposal_id: {result['proposal_id']}")
    print("learning-result endpoint:")
    print(f"http://127.0.0.1:8000/api/cycles/{result['cycle_id']}/learning-result")
    print(f"has_changes: {bool(preview.get('has_changes'))}")
    print(f"can_open_details: {bool(preview.get('can_open_details'))}")
    print(f"changes_count: {len(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
