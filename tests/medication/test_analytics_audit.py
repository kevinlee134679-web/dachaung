"""Independent A6/A5 boundary audit against the registered HTTP routes."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import fixtures as support

from medplatform.core.documents import stamp


class AnalyticsAuditTests(unittest.TestCase):
    def setUp(self):
        self.case = support.IdentityFixture()
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.window = {
            "window_start": "2026-11-16T00:00:00+08:00",
            "window_end": "2026-11-18T00:00:00+08:00",
            "data_environment": "demo",
        }

    def plan(self, times=None, **changes):
        draft = self.case.pending(
            self.case.draft(
                schedule={"kind": "daily", "times": times or ["20:00"], "weekdays": []}
            )
        )
        return self.case.confirm(draft, **changes)

    def move(self, moment):
        self.case.time[0] = (
            datetime.fromisoformat(moment) if isinstance(moment, str) else moment
        )
        self.case.a = self.case.login("demo-patient-a")
        self.case.f = self.case.login("demo-family")

    def slots(self):
        with self.case.db.connection(readonly=True) as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM dose_slots WHERE patient_id=? AND scheduled_at<=? ORDER BY scheduled_at",
                    (support.PA, stamp(self.case.clock())),
                )
            ]

    def report(self, slot, status="taken", client=None):
        return self.case.call(
            client or self.case.a,
            "POST",
            f"/patients/{support.PA}/medication-events",
            {
                "source_event_id": support.key(),
                "occurred_at": slot["scheduled_at"],
                "reported_status": status,
                "dose_slot_id": slot["dose_slot_id"],
                "medication_id": slot["medication_id"],
                "plan_ref": {
                    "plan_id": slot["plan_id"],
                    "plan_version": slot["plan_version"],
                },
            },
            expected=201,
        )

    def refresh(self, as_of=None, client=None, operation=None, expected=200):
        return self.case.call(
            client or self.case.a,
            "POST",
            f"/patients/{support.PA}/summary-refresh",
            {**self.window, "as_of": as_of or stamp(self.case.clock())},
            operation=operation,
            expected=expected,
        )

    def read(self, resource, as_of=None, client=None, expected=200):
        params = {**self.window, "as_of": as_of or stamp(self.case.clock())}
        return self.case.call(
            client or self.case.a,
            "GET",
            f"/patients/{support.PA}/{resource}",
            params=params,
            expected=expected,
        )

    def test_daily_one_of_one_and_zero_of_three_aggregate_to_one_of_four(self):
        self.plan(["08:00", "12:00", "20:00"])
        self.move("2026-11-17T13:00:00+00:00")
        due = self.slots()
        self.assertEqual(len(due), 4)
        self.report(due[0])
        summary = self.refresh()
        trend = self.read("medication-trends")
        self.assertEqual(
            [
                (day["patient_confirmed_count"], day["planned_dose_count"])
                for day in trend["items"]
            ],
            [(1, 1), (0, 3)],
        )
        self.assertEqual(
            [day["patient_confirmation_ratio"] for day in trend["items"]], [1.0, 0.0]
        )
        self.assertEqual(trend["aggregate"]["patient_confirmation_ratio"], 0.25)
        self.assertEqual(summary["record_overview"]["patient_confirmation_ratio"], 0.25)
        self.assertEqual(
            trend["aggregate"]["statistics_id"],
            summary["record_overview"]["statistics_id"],
        )

    def test_later_plan_publication_does_not_reassign_historical_denominator(self):
        original = self.plan()
        self.move("2026-11-17T13:00:00+00:00")
        old_cutoff = stamp(self.case.clock())
        old = self.refresh(old_cutoff)["record_overview"]
        self.assertEqual(old["planned_dose_count"], 2)
        self.assertEqual(
            old["plan_refs"], [{"plan_id": original["plan_id"], "plan_version": 1}]
        )
        self.move(self.case.clock() + timedelta(minutes=1))
        self.plan(
            ["21:00"],
            existing_plan_id=original["plan_id"],
            expected_plan_version=1,
            effective_from=stamp(self.case.clock() + timedelta(hours=1)),
        )
        rebuilt = self.refresh(old_cutoff)["record_overview"]
        self.assertEqual(rebuilt["planned_dose_count"], old["planned_dose_count"])
        self.assertEqual(rebuilt["plan_refs"], old["plan_refs"])
        self.assertEqual(rebuilt["as_of"], old_cutoff)
        with self.case.db.connection(readonly=True) as conn:
            saved = conn.execute(
                "SELECT result_json FROM s03_results WHERE result_id=?",
                (old["statistics_id"],),
            ).fetchone()[0]
        self.assertIn(old["statistics_id"], saved)

    def test_family_opposite_final_report_is_an_unresolved_conflict(self):
        self.plan()
        self.move("2026-11-16T13:00:00+00:00")
        self.case.bind(["records:report"])
        slot = self.slots()[0]
        self.report(slot, "taken")
        family = self.report(slot, "not_taken", self.case.f)
        self.assertEqual(family["evidence_type"], "family_report")
        stats = self.refresh()["record_overview"]
        self.assertEqual(stats["patient_confirmed_count"], 0)
        self.assertEqual(stats["reported_not_taken_count"], 0)
        self.assertEqual(stats["unknown_count"], 1)
        self.assertEqual(stats["issues"][0]["code"], "conflicting_reports")

    def test_explicit_review_unlink_stops_old_payload_from_counting_as_taken(self):
        self.plan()
        self.move("2026-11-16T13:00:00+00:00")
        event = self.report(self.slots()[0])
        old_cutoff = stamp(self.case.clock())
        old = self.refresh(old_cutoff)["record_overview"]
        self.assertEqual(old["patient_confirmed_count"], 1)
        self.move(self.case.clock() + timedelta(minutes=1))
        admin = self.case.login("demo-admin")
        self.case.call(
            admin,
            "POST",
            "/dose-matches/review",
            {
                "event_id": event["event_id"],
                "expected_revision": 1,
                "dose_slot_id": None,
                "reason": "演示复核明确解除原关联",
            },
        )
        current = self.refresh()["record_overview"]
        self.assertEqual(current["patient_confirmed_count"], 0)
        self.assertEqual(current["unknown_count"], 1)
        historical = self.read("medication-statistics", old_cutoff)
        self.assertEqual(historical["patient_confirmed_count"], 1)
        self.assertEqual(historical["statistics_id"], old["statistics_id"])

    def test_quality_processed_after_cutoff_does_not_backfill_historical_result(self):
        self.plan()
        self.move("2026-11-16T13:00:00+00:00")
        with patch.object(self.case.app.state.records, "_process", return_value=None):
            event = self.report(self.slots()[0])
        self.assertEqual(event["quality"]["status"], "pending_validation")
        old_cutoff = stamp(self.case.clock())
        old = self.refresh(old_cutoff)["record_overview"]
        self.assertEqual(old["patient_confirmed_count"], 0)
        self.move(self.case.clock() + timedelta(minutes=1))
        admin = self.case.login("demo-admin")
        self.case.call(
            admin,
            "POST",
            f"/events/{event['event_id']}/reprocess",
            {"expected_revision": 1},
        )
        rebuilt = self.refresh(old_cutoff)["record_overview"]
        self.assertEqual(rebuilt["patient_confirmed_count"], 0)
        self.assertEqual(rebuilt["unknown_count"], 1)
        now = self.refresh()["record_overview"]
        self.assertEqual(now["patient_confirmed_count"], 1)
        with self.case.db.connection(readonly=True) as conn:
            original = conn.execute(
                "SELECT result_json FROM s03_results WHERE result_id=?",
                (old["statistics_id"],),
            ).fetchone()[0]
        self.assertIn('"patient_confirmed_count":0', original)

    def test_revoked_source_scopes_cannot_replay_old_summary_or_read_old_body(self):
        self.plan()
        self.move("2026-11-16T13:00:00+00:00")
        self.report(self.slots()[0])
        self.case.call(
            self.case.a,
            "POST",
            f"/patients/{support.PA}/measurements",
            {
                "source_event_id": support.key(),
                "occurred_at": stamp(self.case.clock()),
                "payload": {
                    "metric_code": "sleep_duration",
                    "value": 7,
                    "unit": "h",
                    "method_code": None,
                    "missing_reason": None,
                },
            },
            expected=201,
        )
        binding, _ = self.case.bind(
            ["summary:read", "statistics:read", "measurements:read"]
        )
        cutoff = stamp(self.case.clock())
        operation = support.key()
        shared = self.refresh(cutoff, self.case.f, operation)
        self.assertEqual(shared["record_overview"]["patient_confirmed_count"], 1)
        self.assertTrue(
            any(item["latest_value"] == 7 for item in shared["measurement_overview"])
        )
        self.case.call(
            self.case.a,
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": 1,
                "scopes": ["summary:read"],
                "valid_until": None,
                "confirmed": True,
            },
        )
        refused = self.refresh(cutoff, self.case.f, operation, expected=403)
        self.assertEqual(refused["code"], "SOURCE_ACCESS_CHANGED")
        self.read("summary", cutoff, self.case.f, expected=409)
        limited = self.refresh(cutoff, self.case.f)
        self.assertIsNone(limited["record_overview"])
        self.assertEqual(limited["measurement_overview"], [])
        self.assertTrue(
            any(item["code"] == "restricted" for item in limited["missing_items"])
        )
