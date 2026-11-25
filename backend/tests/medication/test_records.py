"""Isolated real SQLite regressions for A10-A27, never the running library."""

import copy
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import fixtures as support
from medplatform.core.database import Database
from medplatform.core.documents import stamp
from medplatform.core.errors import AppError
from medplatform.core.migrations import migrate
from medplatform.medication.records import (
    ROUTES,
    Records,
    effective_events,
    event_view,
    match_view,
    query_input,
)


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.case = support.IdentityFixture()
        self.addCleanup(self.case.doCleanups)
        self.case.setUp()
        self.service = Records(
            self.case.db,
            self.case.app.state.identity.auth,
            self.case.app.state.identity.receipts,
            self.case.clock,
        )
        self.admin = self.case.login("demo-admin")
        self.plan = self.case.confirm()
        self.case.time[0] += timedelta(hours=3)
        with self.case.db.connection(readonly=True) as conn:
            self.slots = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM dose_slots ORDER BY scheduled_at"
                )
            ]
        self.slot = self.slots[0]
        self.schemas = {action: schema for _, _, _, action, schema in ROUTES}

    def call(self, action, body=None, params=None, q=None, client=None, key=None):
        client = client or self.case.a
        body = body or {}
        schema = self.schemas[action]
        if schema:
            body = schema.model_validate(body).model_dump()
        principal = self.service.auth.resolve(client.cookies.get("session"))
        return self.service.handle(
            action, principal, params or {}, q or {}, body, key or support.key()
        ).data

    def medication(
        self, client=None, source=None, slot=True, status="taken", text=None
    ):
        body = {
            "source_event_id": source or support.key(),
            "occurred_at": stamp(self.case.clock()),
            "reported_status": status,
            "raw_text": text,
        }
        if slot:
            body.update(
                dose_slot_id=self.slot["dose_slot_id"],
                medication_id=self.slot["medication_id"],
                plan_ref={
                    "plan_id": self.slot["plan_id"],
                    "plan_version": self.slot["plan_version"],
                },
            )
        return self.call(
            "records_medication_create", body, {"p": support.PA}, client=client
        )

    def test_original_source_is_single_and_same_source_content_conflicts(self):
        source = support.key()
        one = self.medication(source=source, text="  本人原话  ")
        two = self.medication(source=source, text="  本人原话  ")
        self.assertEqual(one["event_id"], two["event_id"])
        self.assertEqual(one["payload"]["raw_text"], "  本人原话  ")
        with self.assertRaises(AppError) as caught:
            self.medication(source=source, status="not_taken")
        self.assertEqual(caught.exception.code, "SOURCE_EVENT_CONFLICT")
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM source_events").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM event_revisions").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM s03_quality_history").fetchone()[0],
                1,
            )
        self.assertEqual(one["quality"]["status"], "valid")
        self.assertEqual(one["evidence_type"], "self_report")
        self.assertEqual(one["link_status"], "matched")

    def test_family_report_stays_family_and_revoked_rights_block_replay(self):
        binding, _ = self.case.bind(
            ["records:report", "records:read", "records:correct"]
        )
        body = {
            "source_event_id": support.key(),
            "occurred_at": stamp(self.case.clock()),
            "reported_status": "taken",
        }
        operation = support.key()
        first = self.call(
            "records_medication_create",
            body,
            {"p": support.PA},
            client=self.case.f,
            key=operation,
        )
        self.assertEqual(first["evidence_type"], "family_report")
        self.case.call(
            self.case.a,
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": 1,
                "scopes": ["records:read"],
                "valid_until": None,
                "confirmed": True,
            },
        )
        with self.assertRaises(AppError) as caught:
            self.call(
                "records_medication_create",
                body,
                {"p": support.PA},
                client=self.case.f,
                key=operation,
            )
        self.assertEqual(caught.exception.status, 403)
        with self.assertRaises(AppError):
            self.call(
                "records_correction",
                {
                    "expected_revision": 1,
                    "reason": "核对",
                    "occurred_at": first["occurred_at"],
                    "payload": first["payload"],
                },
                {"id": first["event_id"]},
                client=self.case.a,
            )

    def test_corrections_and_withdrawal_preserve_original_and_historical_cutoff(self):
        original = self.medication()
        cutoff = stamp(self.case.clock())
        self.case.time[0] += timedelta(minutes=1)
        payload = copy.deepcopy(original["payload"])
        payload["reported_status"] = "not_taken"
        corrected = self.call(
            "records_correction",
            {
                "expected_revision": 1,
                "reason": "本人更正",
                "occurred_at": stamp(self.case.clock()),
                "payload": payload,
            },
            {"id": original["event_id"]},
        )
        self.assertEqual(corrected["meta"]["revision"], 2)
        with self.case.db.connection(readonly=True) as conn:
            historical = event_view(conn, original["event_id"], cutoff)
            self.assertEqual(historical["payload"]["reported_status"], "taken")
            self.assertEqual(historical["meta"]["revision"], 1)
            self.assertEqual(
                json.loads(
                    conn.execute(
                        "SELECT original_payload_json FROM source_events"
                    ).fetchone()[0]
                )["reported_status"],
                "taken",
            )
        self.case.time[0] += timedelta(minutes=1)
        withdrawn = self.call(
            "records_withdrawal",
            {"expected_revision": 2, "reason": "撤销错误报告"},
            {"id": original["event_id"]},
        )
        self.assertEqual(withdrawn["state"], "withdrawn")
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                effective_events(conn, support.PA, "demo", stamp(self.case.clock())), []
            )
            self.assertEqual(len(effective_events(conn, support.PA, "demo", cutoff)), 1)
        with self.assertRaises(AppError) as caught:
            self.call(
                "records_correction",
                {
                    "expected_revision": 3,
                    "reason": "不能恢复",
                    "occurred_at": cutoff,
                    "payload": payload,
                },
                {"id": original["event_id"]},
            )
        self.assertEqual(caught.exception.code, "EVENT_ALREADY_WITHDRAWN")

    def test_no_automatic_near_time_matching_and_review_history_respects_as_of(self):
        event = self.medication(slot=False)
        cutoff = stamp(self.case.clock())
        self.assertEqual(event["link_status"], "unmatched")
        self.case.time[0] += timedelta(minutes=1)
        review = self.call(
            "records_match_review",
            {
                "event_id": event["event_id"],
                "expected_revision": 1,
                "dose_slot_id": self.slot["dose_slot_id"],
                "reason": "受控虚构案例的明确关联，不是临床审核",
            },
            client=self.admin,
        )
        self.assertEqual(review["link_status"], "matched")
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                match_view(conn, event["event_id"], 1, cutoff)["link_status"],
                "unmatched",
            )
            self.assertEqual(
                match_view(conn, event["event_id"], 1)["dose_slot_id"],
                self.slot["dose_slot_id"],
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM event_revisions").fetchone()[0], 1
            )
        self.case.time[0] += timedelta(minutes=1)
        cleared = self.call(
            "records_match_review",
            {
                "event_id": event["event_id"],
                "expected_revision": 1,
                "dose_slot_id": None,
                "reason": "明确解除",
            },
            client=self.admin,
        )
        self.assertIsNone(cleared["dose_slot_id"])
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM s03_match_history").fetchone()[0], 3
            )

    def test_review_and_reprocess_require_controlled_identity(self):
        event = self.medication()
        for action, body in [
            ("records_reprocess", {"expected_revision": 1}),
            (
                "records_match_review",
                {
                    "event_id": event["event_id"],
                    "expected_revision": 1,
                    "dose_slot_id": None,
                    "reason": "普通患者不得内部复核",
                },
            ),
        ]:
            with self.assertRaises(AppError) as caught:
                self.call(
                    action,
                    body,
                    {"id": event["event_id"]} if action == "records_reprocess" else {},
                )
            self.assertEqual(caught.exception.code, "ADMIN_REQUIRED")

    def test_simulator_reuses_common_source_and_binding_revocation_blocks_old_key(self):
        binding = self.call(
            "records_device_bind",
            {"device_id": "demo-box-a", "confirmed": True},
            {"p": support.PA},
        )
        body = {
            "patient_id": support.PA,
            "device_id": "demo-box-a",
            "scenario": "normal_box",
            "scenario_run_id": support.key(),
            "occurred_at": stamp(self.case.clock() - timedelta(days=2)),
        }
        operation = support.key()
        first = self.call("records_demo_device", body, client=self.admin, key=operation)
        body["scenario"] = "duplicate"
        duplicate = self.call("records_demo_device", body, client=self.admin)
        self.assertEqual(first["event_id"], duplicate["event_id"])
        self.assertEqual(first["evidence_type"], "box_opening")
        self.assertLess(first["occurred_at"], first["received_at"])
        self.assertEqual(first["link_status"], "unmatched")
        self.call(
            "records_device_revoke",
            {"expected_revision": 1, "reason": "本人解绑"},
            {"id": binding["binding_id"]},
        )
        body["scenario"] = "normal_box"
        with self.assertRaises(AppError):
            self.call("records_demo_device", body, client=self.admin, key=operation)

    def test_cross_patient_slot_device_and_event_are_rejected(self):
        event = self.medication()
        with self.assertRaises(AppError) as caught:
            self.call(
                "records_medication",
                params={"id": event["event_id"]},
                client=self.case.b,
            )
        self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(AppError):
            self.call(
                "records_medication_create",
                {
                    "source_event_id": support.key(),
                    "occurred_at": stamp(self.case.clock()),
                    "reported_status": "taken",
                    "dose_slot_id": self.slot["dose_slot_id"],
                },
                {"p": support.PB},
                client=self.case.b,
            )
        self.call(
            "records_device_bind",
            {"device_id": "demo-box-b", "confirmed": True},
            {"p": support.PB},
            client=self.case.b,
        )
        with self.assertRaises(AppError):
            self.call(
                "records_demo_device",
                {
                    "patient_id": support.PA,
                    "device_id": "demo-box-b",
                    "scenario": "normal_box",
                    "scenario_run_id": support.key(),
                    "occurred_at": stamp(self.case.clock()),
                },
                client=self.admin,
            )

    def test_real_device_adapter_is_closed_without_simulation_fallback(self):
        with self.assertRaises(AppError) as caught:
            self.call(
                "records_device_event",
                {
                    "device_id": "demo-box-a",
                    "source_event_id": support.key(),
                    "occurred_at": stamp(self.case.clock()),
                    "event_kind": "medication",
                    "payload": {
                        "reported_status": None,
                        "observation": "box_opened",
                        "medication_id": None,
                        "dose_slot_id": None,
                        "plan_ref": None,
                        "raw_text": None,
                    },
                },
            )
        self.assertEqual(caught.exception.status, 503)
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM source_events").fetchone()[0], 0
            )

    def test_queries_are_strict_and_reads_do_not_write(self):
        event = self.medication()
        q = query_input(
            "records_medications",
            [
                ("window_start", stamp(self.case.clock() - timedelta(hours=2))),
                ("window_end", stamp(self.case.clock() + timedelta(hours=1))),
                ("data_environment", "demo"),
                ("as_of", stamp(self.case.clock())),
            ],
        )
        with self.case.db.connection(readonly=True) as conn:
            before = conn.execute("SELECT count(*) FROM s03_match_history").fetchone()[
                0
            ]
        result = self.call("records_medications", params={"p": support.PA}, q=q)
        self.assertEqual(result["items"][0]["event_id"], event["event_id"])
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM s03_match_history").fetchone()[0],
                before,
            )
        for pairs in [[("limit", "1"), ("limit", "2")], [("unknown", "field")]]:
            with self.assertRaises(AppError):
                query_input("records_medications", pairs)

    def test_correcting_source_cannot_change_identity(self):
        event = self.medication()
        payload = copy.deepcopy(event["payload"])
        payload.update(reported_status=None, observation="box_opened")
        with self.assertRaises(AppError):
            self.call(
                "records_correction",
                {
                    "expected_revision": 1,
                    "reason": "不得改来源",
                    "occurred_at": event["occurred_at"],
                    "payload": payload,
                },
                {"id": event["event_id"]},
            )

    def test_concurrent_source_replay_has_one_original_fact(self):
        source = support.key()
        with ThreadPoolExecutor(max_workers=2) as pool:
            events = list(pool.map(lambda _: self.medication(source=source), range(2)))
        self.assertEqual(events[0]["event_id"], events[1]["event_id"])
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM source_events").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM event_revisions").fetchone()[0], 1
            )

    def test_implicit_cutoff_is_preserved_by_opaque_pagination(self):
        self.medication()
        self.medication()
        raw = {
            "window_start": stamp(self.case.clock() - timedelta(hours=1)),
            "window_end": stamp(self.case.clock() + timedelta(hours=1)),
            "data_environment": "demo",
            "limit": "1",
        }
        first = self.call(
            "records_medications",
            params={"p": support.PA},
            q=query_input("records_medications", list(raw.items())),
        )
        self.assertIsNotNone(first["next_cursor"])
        self.case.time[0] += timedelta(minutes=1)
        late = self.medication()
        raw["cursor"] = first["next_cursor"]
        second = self.call(
            "records_medications",
            params={"p": support.PA},
            q=query_input("records_medications", list(raw.items())),
        )
        self.assertEqual(len(second["items"]), 1)
        self.assertNotEqual(
            second["items"][0]["event_id"], first["items"][0]["event_id"]
        )
        self.assertNotEqual(second["items"][0]["event_id"], late["event_id"])
        self.assertIsNone(second["next_cursor"])
        with self.assertRaises(AppError):
            self.call(
                "records_medications",
                params={"p": support.PB},
                q=query_input("records_medications", list(raw.items())),
                client=self.case.b,
            )

    def test_processing_after_cutoff_does_not_backfill_old_quality(self):
        event = self.medication()
        cutoff = stamp(self.case.clock())
        # A supported old row may have been saved before A4 was implemented.
        with self.case.db.transaction() as conn:
            conn.execute(
                "DELETE FROM s03_quality_history WHERE event_id=?", (event["event_id"],)
            )
            conn.execute(
                "DELETE FROM s03_match_history WHERE event_id=?", (event["event_id"],)
            )
        self.case.time[0] += timedelta(minutes=1)
        self.call(
            "records_reprocess",
            {"expected_revision": 1},
            {"id": event["event_id"]},
            client=self.admin,
        )
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                event_view(conn, event["event_id"], cutoff)["quality"]["status"],
                "pending_validation",
            )
            self.assertIsNone(match_view(conn, event["event_id"], 1, cutoff))
            self.assertEqual(
                event_view(conn, event["event_id"])["quality"]["status"], "valid"
            )

    def test_existing_schema_three_upgrade_preserves_raw_event_and_revision(self):
        database = Database(self.case.path / "upgrade.sqlite3")
        migrate(database, initialize=True, target=3)
        with self.case.db.connection(readonly=True) as conn:
            event = self.medication()
            raw = tuple(
                conn.execute(
                    "SELECT * FROM source_events WHERE event_id=?", (event["event_id"],)
                ).fetchone()
            )
            revision = tuple(
                conn.execute(
                    "SELECT * FROM event_revisions WHERE event_id=?",
                    (event["event_id"],),
                ).fetchone()
            )
        with database.transaction() as conn:
            conn.execute(
                "INSERT INTO source_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", raw
            )
            conn.execute(
                "INSERT INTO event_revisions VALUES (?,?,?,?,?,?,?,?,?,?)", revision
            )
        migrate(database)
        with database.connection(readonly=True) as conn:
            self.assertEqual(
                tuple(conn.execute("SELECT * FROM source_events").fetchone()), raw
            )
            self.assertEqual(
                tuple(conn.execute("SELECT * FROM event_revisions").fetchone()),
                revision,
            )
            self.assertEqual(
                event_view(conn, event["event_id"])["quality"]["status"],
                "pending_validation",
            )

    def test_real_http_routes_enforce_schema_and_current_authorization(self):
        data = self.case.call(
            self.case.a,
            "POST",
            f"/patients/{support.PA}/medication-events",
            {
                "source_event_id": support.key(),
                "occurred_at": stamp(self.case.clock()),
                "reported_status": "unknown",
            },
            expected=201,
        )
        detail = self.case.call(
            self.case.a, "GET", f"/medication-events/{data['event_id']}"
        )
        self.assertEqual(detail, data)
        self.case.call(
            self.case.a,
            "POST",
            f"/patients/{support.PA}/medication-events",
            {
                "source_event_id": support.key(),
                "occurred_at": stamp(self.case.clock()),
                "reported_status": "taken",
                "evidence_type": "self_report",
            },
            expected=422,
        )
        self.case.call(
            self.case.b, "GET", f"/medication-events/{data['event_id']}", expected=404
        )

    def test_reprocess_program_failure_is_saved_redacted_and_replayable_then_recoverable(
        self,
    ):
        event = self.medication()
        identifier = event["event_id"]
        admin = self.case.login("demo-admin")
        operation = support.key()
        self.case.time[0] += timedelta(minutes=1)
        # HTTP service and this direct service share exactly the same database.
        service = self.case.app.state.records
        with patch.object(
            service,
            "_assess_quality",
            side_effect=RuntimeError("private payload must not escape"),
        ) as compute:
            error = self.case.call(
                admin,
                "POST",
                f"/events/{identifier}/reprocess",
                {"expected_revision": 1},
                operation=operation,
                expected=503,
            )
            replay = self.case.call(
                admin,
                "POST",
                f"/events/{identifier}/reprocess",
                {"expected_revision": 1},
                operation=operation,
                expected=503,
            )
            self.assertEqual(compute.call_count, 1)
        self.assertEqual(error, replay)
        self.assertEqual(error["code"], "QUALITY_PROCESSING_FAILED")
        failed = self.case.call(self.case.a, "GET", f"/events/{identifier}/quality")
        self.assertEqual(failed["status"], "processing_failed")
        self.assertNotIn("private payload", json.dumps(failed))
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM event_revisions").fetchone()[0], 1
            )
            self.assertEqual(
                json.loads(
                    conn.execute(
                        "SELECT original_payload_json FROM source_events"
                    ).fetchone()[0]
                ),
                event["payload"],
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM s03_match_history").fetchone()[0], 1
            )
        self.case.time[0] += timedelta(minutes=1)
        recovered = self.case.call(
            admin, "POST", f"/events/{identifier}/reprocess", {"expected_revision": 1}
        )
        self.assertEqual(recovered["status"], "valid")
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM s03_quality_history").fetchone()[0],
                3,
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM event_revisions").fetchone()[0], 1
            )

    def test_ingest_pure_quality_or_matching_failure_preserves_accepted_original(self):
        for function in ("_assess_quality", "_make_match"):
            with self.subTest(function=function):
                with patch.object(
                    self.service,
                    function,
                    side_effect=RuntimeError("isolated computation failure"),
                ):
                    event = self.medication()
                self.assertEqual(event["quality"]["status"], "processing_failed")
                self.assertEqual(event["link_status"], "review_required")
                self.assertEqual(event["payload"]["reported_status"], "taken")
                recovered = self.call(
                    "records_reprocess",
                    {"expected_revision": 1},
                    {"id": event["event_id"]},
                    client=self.admin,
                )
                self.assertEqual(recovered["status"], "valid")
                with self.case.db.connection(readonly=True) as conn:
                    self.assertEqual(
                        match_view(conn, event["event_id"], 1)["link_status"], "matched"
                    )

    def test_storage_failures_are_503_rollbacks_without_saved_processing_failure(self):
        event = self.medication()
        identifier = event["event_id"]
        service = self.case.app.state.records
        for failure in (
            OSError("isolated storage failure"),
            __import__("sqlite3").OperationalError("isolated SQL failure"),
        ):
            with self.subTest(failure=type(failure).__name__):
                with self.case.db.connection(readonly=True) as conn:
                    before = [
                        conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                        for table in (
                            "s03_quality_history",
                            "s03_match_history",
                            "idempotency_receipts",
                        )
                    ]
                with patch.object(service, "_assess_quality", side_effect=failure):
                    self.case.call(
                        self.admin,
                        "POST",
                        f"/events/{identifier}/reprocess",
                        {"expected_revision": 1},
                        expected=503,
                    )
                with self.case.db.connection(readonly=True) as conn:
                    after = [
                        conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                        for table in (
                            "s03_quality_history",
                            "s03_match_history",
                            "idempotency_receipts",
                        )
                    ]
                self.assertEqual(before, after)
                self.assertEqual(
                    self.call("records_quality", params={"id": identifier})["status"],
                    "valid",
                )

    def test_same_input_rule_reprocess_does_not_duplicate_derived_facts(self):
        event = self.medication()
        identifier = event["event_id"]
        with self.case.db.connection(readonly=True) as conn:
            before = [
                conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                for table in (
                    "event_revisions",
                    "s03_quality_history",
                    "s03_match_history",
                )
            ]
        for _ in range(2):
            self.case.time[0] += timedelta(minutes=1)
            self.call(
                "records_reprocess",
                {"expected_revision": 1},
                {"id": identifier},
                client=self.admin,
            )
        with self.case.db.connection(readonly=True) as conn:
            after = [
                conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                for table in (
                    "event_revisions",
                    "s03_quality_history",
                    "s03_match_history",
                )
            ]
        self.assertEqual(before, after)
