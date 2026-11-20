import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from medplatform.medication.runner import Runner
from support.services import test_services as prior


class IntegratedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.c = prior.FormalServiceTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        self.h = self.c.s
        self.runner = Runner(self.h.app)

    def cycle(self):
        with self.runner.exclusive():
            return self.runner.cycle()

    def test_b_c_unique_service_runner_dispatch_and_current_status(self):
        draft, consent = self.c.prepare()
        session = self.h.call(
            self.h.a,
            "POST",
            "/sessions",
            {
                "patient_id": prior.PA,
                "case_id": None,
                "entry_source": "user",
                "invitation_id": None,
            },
            expected=201,
        )
        body = {
            "patient_id": prior.PA,
            "session_id": session["session_id"],
            "source_suggestion_id": None,
            "resource_id": draft["resource_id"],
            "service_draft_id": draft["service_draft_id"],
            "service_draft_revision": draft["draft_revision"],
            "confirmation_ref_id": consent["confirmation_ref_id"],
            "sharing_scope_ref_id": consent["sharing_scope"]["sharing_scope_ref_id"],
        }
        referral = self.h.call(self.h.a, "POST", "/referrals", body, expected=201)
        direct = self.c.create(self.c.body(draft, consent))
        self.assertEqual(referral["service_id"], direct["service_id"])
        self.assertEqual(self.cycle()["completed"], 1)
        self.assertEqual(self.cycle()["executions"], 0)
        progress = self.c.transition(direct, "in_progress")
        done = self.c.transition(progress, "completed")
        current = self.h.call(self.h.a, "GET", "/referrals/" + referral["referral_id"])
        self.assertEqual(current["service_status"], done["status"])
        with self.h.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM c_services").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM c_service_dispatches").fetchone()[0],
                1,
            )

    def test_revoked_sharing_stops_pending_dispatch_without_deleting_service(self):
        draft, consent = self.c.prepare()
        self.c.create(self.c.body(draft, consent))
        self.c.d.revoke(consent)
        self.cycle()
        with self.h.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM c_service_dispatches").fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM c_services").fetchone()[0], 1
            )

    def test_unknown_provider_attempt_is_not_resubmitted_by_later_cycles(self):
        self.c.create()
        self.c.adapter.attempt = lambda *_: {"outcome_unknown": True}
        self.assertEqual(self.cycle()["failed"], 1)
        self.assertEqual(self.cycle()["executions"], 0)
        with self.h.db.connection(readonly=True) as conn:
            rows = [
                json.loads(r[0])
                for r in conn.execute("SELECT document_json FROM a_executions")
            ]
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM c_service_dispatches").fetchone()[0],
                0,
            )
        self.assertEqual(rows[0]["execution_status"], "outcome_unknown")
        self.assertFalse(rows[0]["retryable"])

    def test_external_inflight_crash_is_preserved_unknown_not_safe_local_retry(self):
        service = self.c.create()
        with (
            patch.object(
                self.c.execution,
                "_complete",
                side_effect=SystemExit("controlled crash"),
            ),
            self.assertRaises(SystemExit),
        ):
            self.c.execution.run_once(
                None,
                service["dispatch_task_id"],
                1,
                "controlled-c-provider-original",
            )
        self.h.time[0] += timedelta(seconds=91)
        self.assertEqual(self.cycle()["executions"], 0)
        self.assertEqual(self.cycle()["executions"], 0)
        with self.h.db.connection(readonly=True) as conn:
            row = json.loads(
                conn.execute("SELECT document_json FROM a_executions").fetchone()[0]
            )
        self.assertEqual(row["execution_status"], "outcome_unknown")
        self.assertFalse(row["retryable"])
