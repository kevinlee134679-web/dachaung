import sqlite3
import unittest
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

import fixtures as existing
from medplatform.core.documents import stamp
from support.services import test_services as services

PA = existing.PA
P = f"/patients/{PA}"
DIMENSIONS = ("support_needs", "support_acceptance", "intervention_effectiveness")


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f = services.FormalServiceTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.s, self.d = self.f.s, self.f.d
        self.c = self.s.app.state.feedback
        self.range = {
            "window_start": stamp(self.s.clock() - timedelta(days=1)),
            "window_end": stamp(self.s.clock() + timedelta(days=1)),
        }

    def service(self, terminal="completed"):
        draft = self.d.create()
        latest = self.d.read(draft)
        consent = self.d.confirm(draft, expected=200 if self.c_exists() else 201)
        result = self.f.create(self.f.body(latest, consent))
        if terminal == "submitted":
            return result
        if terminal == "failed":
            return self.f.transition(result, "failed")
        if terminal == "cancelled":
            return self.f.cancel(result)
        self.f.run_task(result)
        result = self.f.transition(result, "in_progress")
        return (
            self.f.transition(result, "completed")
            if terminal == "completed"
            else result
        )

    def c_exists(self):
        with self.s.db.connection(readonly=True) as conn:
            return bool(
                conn.execute("SELECT 1 FROM c_service_confirmations").fetchone()
            )

    @staticmethod
    def body(revision=0, **substitutions):
        result = {
            "client_feedback_id": existing.key(),
            "expected_feedback_revision": revision,
            "participation": "provided",
            "support_needs": "仍希望核对虚构安排",
            "support_acceptance": None,
            "intervention_effectiveness": None,
            "willing_to_continue": None,
            "missing_reason": None,
        }
        return result | substitutions

    def history(self, service, *, client=None, expected=200, suffix=""):
        return self.d.call(
            "GET", self.path(service) + suffix, client=client, expected=expected
        )

    def submit(self, service, body=None, *, client=None, expected=201, key=None):
        return self.d.call(
            "POST", self.path(service), body or self.body(), client, expected, key
        )

    @staticmethod
    def path(service):
        return "/services/" + service["service_id"] + "/feedback"

    def projection(self, *, window=None, client=None, expected=200):
        return self.d.call(
            "GET",
            P + "/support-feedback?" + urlencode(window or self.range),
            client=client,
            expected=expected,
        )

    def aggregate(self, *, client=None, expected=200):
        path = (
            P
            + "/feedback-overview?"
            + urlencode(dict(self.range, data_environment="demo"))
        )
        result = self.d.call("GET", path, client=client, expected=expected)
        return result["sources"][1] if expected < 400 else result

    def test_terminal_eligibility_state_and_unchanged_service_fact(self):
        submitted = self.service("submitted")
        self.assertEqual(
            self.submit(submitted, expected=409)["code"], "FEEDBACK_REVISION_CONFLICT"
        )
        pending = self.projection()["records"][0]
        self.assertEqual(pending["service_status"], "submitted")
        self.assertTrue(all(pending[name] is None for name in DIMENSIONS))
        in_progress = self.service("in_progress")
        self.assertEqual(
            self.submit(in_progress, expected=409)["code"], "FEEDBACK_REVISION_CONFLICT"
        )
        for terminal in ("completed", "cancelled", "failed"):
            with self.subTest(terminal=terminal):
                service = self.service(terminal)
                self.assertEqual(
                    self.history(service), {"items": [], "next_cursor": None}
                )
                value = self.submit(
                    service,
                    self.body(
                        participation="declined",
                        support_needs=None,
                        missing_reason="这次选择不参与",
                    ),
                )
                self.assertEqual(value["participation"], "declined")
                self.assertEqual(value["missing_reason"], "这次选择不参与")
                self.assertEqual(self.d.call("GET", self.f.path(service)), service)
        self.assertTrue(
            all(
                ref[name] is None
                for ref in self.projection()["records"]
                for name in DIMENSIONS
            )
        )

    def test_exact_input_and_feedback_history_paging(self):
        service = self.service()
        for change in (
            {"support_needs": None},
            {"support_needs": "  "},
            {"intervention_effectiveness": 1},
            {"support_acceptance": "x" * 2001},
            {"expected_feedback_revision": -1},
            {"participation": "unknown"},
            {"willing_to_continue": "true"},
            {"participation": "unable", "support_needs": None},
            {
                "participation": "declined",
                "missing_reason": "原因",
                "support_needs": "不应伴随描述",
            },
            {"recorded_at": stamp(self.s.clock())},
        ):
            self.assertEqual(
                self.submit(service, self.body(**change), expected=422)["code"],
                "VALIDATION_ERROR",
                change,
            )
        incomplete = self.body(
            missing_reason="其余两维不适用", willing_to_continue=False
        )
        first = self.submit(service, incomplete)
        self.assertEqual(
            set(first),
            {
                "feedback_id",
                "patient_id",
                "service_id",
                "feedback_revision",
                "supersedes_feedback_id",
                "participation",
                *DIMENSIONS,
                "willing_to_continue",
                "missing_reason",
                "recorded_at",
                "meta",
            },
        )
        self.assertIs(first["willing_to_continue"], False)
        self.s.time[0] += timedelta(seconds=1)
        second = self.submit(
            service,
            self.body(
                1,
                participation="unable",
                support_needs=None,
                missing_reason="目前不清楚",
            ),
        )
        self.assertEqual(
            (second["feedback_revision"], second["supersedes_feedback_id"]),
            (2, first["feedback_id"]),
        )
        page = self.history(service, suffix="?limit=1")
        self.assertEqual(page["items"], [first])
        suffix = "?" + urlencode({"limit": 1, "cursor": page["next_cursor"]})
        self.assertEqual(
            self.history(service, suffix=suffix),
            {"items": [second], "next_cursor": None},
        )
        self.assertEqual(
            self.history(service, suffix="?cursor=fake", expected=422)["code"],
            "INVALID_CURSOR",
        )
        older = self.projection(
            window=dict(self.range, window_end=second["recorded_at"])
        )
        self.assertEqual(older["records"][0]["support_needs"], first["support_needs"])
        self.assertIsNone(self.projection()["records"][0]["support_needs"])
        with self.assertRaises(sqlite3.IntegrityError), self.s.db.transaction() as conn:
            conn.execute("UPDATE c_service_feedback SET client_feedback_id='changed'")

    def test_idempotency_races_and_atomic_rollback(self):
        service = self.service()
        key, body = existing.key(), self.body()
        original = self.c.save

        def failure(*args):
            original(*args)
            raise sqlite3.OperationalError("injected write failure")

        with patch.object(self.c, "save", failure):
            self.submit(service, body, key=key, expected=503)
        with self.s.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM c_service_feedback").fetchone()[0], 0
            )
        first = self.submit(service, body, key=key)
        self.assertEqual(self.submit(service, body, key=key), first)
        self.assertEqual(self.submit(service, body), first)
        altered = dict(body, support_needs="不同")
        self.assertEqual(
            self.submit(service, altered, key=key, expected=409)["code"],
            "IDEMPOTENCY_CONFLICT",
        )
        self.assertEqual(
            self.submit(service, altered, expected=409)["code"], "IDEMPOTENCY_CONFLICT"
        )
        second_client = self.s.login("demo-patient-a")
        path = self.path(service)
        response = self.d.concurrent(
            (self.s.a, path, self.body(1), existing.key()),
            (second_client, path, self.body(1), existing.key()),
        )
        self.assertEqual(sorted(r.status_code for r in response), [201, 409])
        self.assertEqual(
            next(r.json()["error"]["code"] for r in response if r.status_code == 409),
            "FEEDBACK_REVISION_CONFLICT",
        )
        self.assertEqual(
            [r["feedback_revision"] for r in self.history(service)["items"]], [1, 2]
        )

    def test_patients_family_admin_and_grant_revocation(self):
        service = self.service()
        feedback = self.submit(service)
        binding, grant = self.s.bind(["feedback:read"])
        self.assertEqual(self.aggregate(client=self.s.f)["availability"], "restricted")
        self.history(service, client=self.s.f, expected=403)
        grant = self.d.revise_grant(
            binding, grant["meta"]["revision"], ["feedback:read", "services:read"]
        )
        self.submit(service, client=self.s.f, expected=403)
        self.submit(service, client=self.f.admin, expected=404)
        self.history(service, client=self.s.b, expected=404)
        self.projection(client=self.s.b, expected=404)
        self.projection(client=self.s.f, expected=403)
        redacted = self.history(service, client=self.s.f)["items"][0]
        self.assertEqual(redacted["feedback_id"], feedback["feedback_id"])
        summary = self.aggregate(client=self.s.f)
        self.assertEqual(summary["availability"], "available")
        self.assertEqual(summary["records"][0]["service_status"], "completed")
        for name in DIMENSIONS:
            self.assertIsNone(redacted[name])
            self.assertIsNone(summary["records"][0][name])
        self.d.revise_grant(binding, grant["meta"]["revision"], ["feedback:read"])
        self.history(service, client=self.s.f, expected=403)
        self.assertEqual(self.aggregate(client=self.s.f)["availability"], "restricted")
        self.assertEqual(
            self.aggregate()["records"][0]["support_needs"], feedback["support_needs"]
        )

    def test_source_pagination_availability_window_and_readonly(self):
        self.assertEqual(self.projection()["availability"], "not_collected")
        for _ in range(2):
            self.submit(self.service())
            self.s.time[0] += timedelta(seconds=1)
        start = self.s.db.path.read_bytes()
        prefix = "/api/v1" + P + "/support-feedback?"
        response = self.s.a.get(prefix + urlencode(dict(self.range, limit=1)))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            set(response.json()["data"]),
            {"source_module", "availability", "records", "reason"},
        )
        self.assertEqual(len(response.json()["data"]["records"]), 1)
        cursor_path = response.headers["Link"].split(">")[0][1:]
        self.assertEqual(urlsplit(cursor_path).path, prefix[:-1])
        next_page = self.s.a.get(cursor_path)
        self.assertEqual(next_page.status_code, 200, next_page.text)
        self.assertNotEqual(
            response.json()["data"]["records"][0]["record_id"],
            next_page.json()["data"]["records"][0]["record_id"],
        )
        self.assertNotIn("Link", next_page.headers)
        foreign = self.s.b.get(cursor_path.replace(PA, existing.PB))
        self.assertEqual(
            (foreign.status_code, foreign.json()["error"]["code"]),
            (422, "INVALID_CURSOR"),
        )
        amended = self.s.a.get(
            cursor_path.replace("limit=1", "limit=2") + "&data_environment=demo"
        )
        self.assertEqual(amended.status_code, 422)
        self.assertEqual(self.s.db.path.read_bytes(), start)
        for window in [
            dict(self.range, window_end=self.range["window_start"]),
            dict(self.range, window_start="naive"),
        ]:
            self.projection(window=window, expected=422)
        with patch.object(
            self.c,
            "source_rows",
            side_effect=sqlite3.OperationalError("source failure"),
        ):
            self.assertEqual(
                self.projection(expected=503)["code"], "SUPPORT_FEEDBACK_UNAVAILABLE"
            )
            self.assertEqual(self.aggregate()["availability"], "unavailable")

    def test_summary_reads_historical_and_current_feedback(self):
        service = self.service()
        first = self.submit(service)
        window = dict(self.range, data_environment="demo", as_of=stamp(self.s.clock()))
        path = P + "/summary?"
        self.s.time[0] += timedelta(seconds=1)
        second = self.submit(service, self.body(1, support_needs="下一次先讨论安排"))
        past = self.d.call("GET", path + urlencode(window))
        current = self.d.call(
            "GET", path + urlencode(dict(window, as_of=stamp(self.s.clock())))
        )
        self.assertEqual(
            past["feedback_overview"]["sources"][1]["records"][0]["support_needs"],
            first["support_needs"],
        )
        self.assertEqual(
            current["feedback_overview"]["sources"][1]["records"][0]["support_needs"],
            second["support_needs"],
        )
