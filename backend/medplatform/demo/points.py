"""Explicit isolated positive-points fixture, prepared through ordinary business APIs.

The controlled clock is confined to preparation. Serving the resulting DB uses
the normal real clock. No direct balance or ledger writes and no existing reset.
"""

import argparse
import json
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from ..core.config import ROOT, Settings
from ..core.database import Database
from ..core.documents import stamp, uid
from ..core.migrations import migrate
from ..identity.service import seed_demo
from ..support.points.service import seed_points
from ..support.rewards.catalog import seed_rewards
from ..web.app import create_app
from .client import ScenarioClients

PATIENT = "demo-patient-a-self"
ZONE = ZoneInfo("Asia/Shanghai")


def generate(path):
    path = Path(path).resolve()
    if (
        not path.is_relative_to((ROOT / "test-output").resolve())
        or path.exists()
        or path.with_suffix(".scenario.json").exists()
    ):
        raise ValueError(
            "Use a new isolated test-output path; existing data are never reset"
        )
    current = datetime.now(UTC)
    first = current.astimezone(ZONE).date() - timedelta(days=29)
    clock = [datetime.combine(first, time(), ZONE).astimezone(UTC)]
    db = Database(path)
    migrate(db, initialize=True)
    seed_demo(db, lambda: clock[0])
    seed_points(db, lambda: clock[0])
    seed_rewards(db, lambda: clock[0])
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_PATH=path),
        clock=lambda: clock[0],
    )
    with ScenarioClients(
        app, "Fixture login failed", "Fixture API rejected: "
    ) as clients:
        login, call = clients.login, clients.call
        patient = login("demo-patient-a")
        med = call(
            patient,
            "POST",
            f"/patients/{PATIENT}/medications",
            {"name": "积分流程虚构资料（不用于服药）"},
        )
        entry = {
            "draft_entry_id": uid(),
            "medication_id": med["medication_id"],
            "dose_value": "1",
            "dose_unit": "虚构单位",
            "start_date": str(first),
            "end_date": None,
            "schedule": {"kind": "daily", "times": ["08:00"], "weekdays": []},
            "meal_requirement": None,
            "medical_notes": "仅准备虚构流程来源，不是医嘱",
            "strict_timing": False,
            "min_interval_minutes": None,
            "source_file_ids": [],
        }
        draft = call(
            patient,
            "POST",
            f"/patients/{PATIENT}/drafts",
            {"entries": [entry], "source_file_ids": []},
        )
        draft = call(
            patient,
            "POST",
            f"/drafts/{draft['draft_id']}/submit",
            {
                "expected_revision": draft["meta"]["revision"],
                "content_revision": draft["content_revision"],
            },
        )
        call(
            patient,
            "POST",
            f"/patients/{PATIENT}/plan-confirmations",
            {
                "draft_id": draft["draft_id"],
                "draft_revision": draft["content_revision"],
                "existing_plan_id": None,
                "expected_plan_version": None,
                "effective_from": stamp(clock[0]),
                "confirmed": True,
            },
        )
        clock[0] = current
        patient, admin = login("demo-patient-a"), login("demo-admin")
        left = stamp(datetime.combine(first, time(), ZONE))
        right = stamp(datetime.combine(current.astimezone(ZONE).date(), time(), ZONE))
        query = urlencode({"window_start": left, "window_end": right, "limit": 100})
        slots = call(patient, "GET", f"/patients/{PATIENT}/dose-slots?" + query)[
            "items"
        ]
        if len(slots) != 29:
            raise RuntimeError("Fixture needs exactly 29 previous fictional plan days")
        for index, slot in enumerate(slots):
            call(
                patient,
                "POST",
                f"/patients/{PATIENT}/medication-events",
                {
                    "source_event_id": f"s07-points-v1-{index}",
                    "occurred_at": slot["scheduled_at"],
                    "reported_status": "not_taken",
                    "dose_slot_id": slot["dose_slot_id"],
                    "medication_id": slot["medication_id"],
                    "plan_ref": {
                        "plan_id": slot["plan_id"],
                        "plan_version": slot["plan_version"],
                    },
                },
            )
        result = call(
            admin,
            "POST",
            "/internal/points/reconcile",
            {
                "patient_id": PATIENT,
                "window_start": left,
                "window_end": right,
                "rules_version": "points-demo-v1",
            },
        )
        again = call(
            admin,
            "POST",
            "/internal/points/reconcile",
            {
                "patient_id": PATIENT,
                "window_start": left,
                "window_end": right,
                "rules_version": "points-demo-v1",
            },
        )
        if result["account"]["balance"] != 83 or again["new_entries"]:
            raise RuntimeError(
                "Fixture positive-source evaluation or deduplication differs"
            )
        manifest = {
            "scenario": "s07-points-v1",
            "is_simulated": True,
            "clock_mode": "controlled preparation; real clock when serving",
            "source": "29 actual fictional not_taken reports through business API; no direct ledger inserts",
            "window_start": left,
            "window_end": right,
            "balance": 83,
            "new_entries": len(result["new_entries"]),
            "duplicate_new_entries": 0,
        }
        path.with_suffix(".scenario.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args.database), ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError) as error:
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else "Fixture preparation failed; use a new isolated test-output path without resetting existing data."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
