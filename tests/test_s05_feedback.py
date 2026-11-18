import json
import sqlite3
import unittest
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlencode, urlsplit

import test_s02 as existing
import test_s05_services as services
from medplatform.documents import encode, fingerprint, stamp
from medplatform.s03_analytics import METRICS

PA = existing.PA
P = f"/patients/{PA}"
DIMENSIONS = ("support_needs", "support_acceptance", "intervention_effectiveness")


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.f = services.FormalServiceTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.s, self.d = self.f.s, self.f.d
        self.c = self.s.app.state.s05_feedback
        self.a = self.s.app.state.s03_analytics
        self.range = dict(window_start=stamp(self.s.clock() - timedelta(days=1)),
                          window_end=stamp(self.s.clock() + timedelta(days=1)))

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
        return self.f.transition(result, "completed") if terminal == "completed" else result

    def c_exists(self):
        with self.s.db.connection(readonly=True) as conn:
            return bool(conn.execute("SELECT 1 FROM c_service_confirmations").fetchone())

    @staticmethod
    def body(revision=0, **substitutions):
        result = dict(client_feedback_id=existing.key(), expected_feedback_revision=revision,
                      participation="provided", support_needs="仍希望核对虚构安排",
                      support_acceptance=None, intervention_effectiveness=None, willing_to_continue=None,
                      missing_reason=None)
        return result | substitutions

    def history(self, service, *, client=None, expected=200, suffix=""):
        return self.d.call("GET", self.path(service) + suffix, client=client, expected=expected)

    def submit(self, service, body=None, *, client=None, expected=201, key=None):
        return self.d.call("POST", self.path(service), body or self.body(), client, expected, key)

    @staticmethod
    def path(service):
        return "/services/" + service["service_id"] + "/feedback"

    def projection(self, *, window=None, client=None, expected=200):
        return self.d.call("GET", P + "/support-feedback?" + urlencode(window or self.range),
                           client=client, expected=expected)

    def aggregate(self, *, client=None, expected=200):
        path = P + "/feedback-overview?" + urlencode(dict(self.range, data_environment="demo"))
        result = self.d.call("GET", path, client=client, expected=expected)
        return result["sources"][1] if expected < 400 else result

    def test_terminal_eligibility_state_and_unchanged_service_fact(self):
        submitted = self.service("submitted")
        self.assertEqual(self.submit(submitted, expected=409)["code"], "FEEDBACK_REVISION_CONFLICT")
        pending = self.projection()["records"][0]
        self.assertEqual(pending["service_status"], "submitted")
        self.assertTrue(all(pending[name] is None for name in DIMENSIONS))
        in_progress = self.service("in_progress")
        self.assertEqual(self.submit(in_progress, expected=409)["code"], "FEEDBACK_REVISION_CONFLICT")
        for terminal in ("completed", "cancelled", "failed"):
            with self.subTest(terminal=terminal):
                service = self.service(terminal)
                self.assertEqual(self.history(service), {"items": [], "next_cursor": None})
                value = self.submit(service, self.body(participation="declined", support_needs=None,
                                                      missing_reason="这次选择不参与"))
                self.assertEqual(value["participation"], "declined")
                self.assertEqual(value["missing_reason"], "这次选择不参与")
                self.assertEqual(self.d.call("GET", self.f.path(service)), service)
        self.assertTrue(all(ref[name] is None for ref in self.projection()["records"] for name in DIMENSIONS))

    def test_exact_input_and_feedback_history_paging(self):
        service = self.service()
        for change in (
            {"support_needs": None}, {"support_needs": "  "}, {"intervention_effectiveness": 1},
            {"support_acceptance": "x" * 2001}, {"expected_feedback_revision": -1},
            {"participation": "unknown"}, {"willing_to_continue": "true"},
            {"participation": "unable", "support_needs": None},
            {"participation": "declined", "missing_reason": "原因", "support_needs": "不应伴随描述"},
            {"recorded_at": stamp(self.s.clock())},
        ):
            self.assertEqual(self.submit(service, self.body(**change), expected=422)["code"], "VALIDATION_ERROR", change)
        incomplete = self.body(missing_reason="其余两维不适用", willing_to_continue=False)
        first = self.submit(service, incomplete)
        self.assertEqual(set(first), {"feedback_id", "patient_id", "service_id", "feedback_revision",
                                     "supersedes_feedback_id", "participation", *DIMENSIONS,
                                     "willing_to_continue", "missing_reason", "recorded_at", "meta"})
        self.assertIs(first["willing_to_continue"], False)
        self.s.time[0] += timedelta(seconds=1)
        second = self.submit(service, self.body(1, participation="unable", support_needs=None, missing_reason="目前不清楚"))
        self.assertEqual((second["feedback_revision"], second["supersedes_feedback_id"]), (2, first["feedback_id"]))
        page = self.history(service, suffix="?limit=1")
        self.assertEqual(page["items"], [first])
        suffix = "?" + urlencode(dict(limit=1, cursor=page["next_cursor"]))
        self.assertEqual(self.history(service, suffix=suffix), {"items": [second], "next_cursor": None})
        self.assertEqual(self.history(service, suffix="?cursor=fake", expected=422)["code"], "INVALID_CURSOR")
        older = self.projection(window=dict(self.range, window_end=second["recorded_at"]))
        self.assertEqual(older["records"][0]["support_needs"], first["support_needs"])
        self.assertIsNone(self.projection()["records"][0]["support_needs"])
        with self.assertRaises(sqlite3.IntegrityError):
            with self.s.db.transaction() as conn:
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
            self.assertEqual(conn.execute("SELECT count(*) FROM c_service_feedback").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM change_notices WHERE kind='c_feedback_changed'").fetchone()[0], 0)
        first = self.submit(service, body, key=key)
        self.assertEqual(self.submit(service, body, key=key), first)
        self.assertEqual(self.submit(service, body), first)
        altered = dict(body, support_needs="不同")
        self.assertEqual(self.submit(service, altered, key=key, expected=409)["code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.submit(service, altered, expected=409)["code"], "IDEMPOTENCY_CONFLICT")
        second_client = self.s.login("demo-patient-a")
        path = self.path(service)
        response = self.d.concurrent((self.s.a, path, self.body(1), existing.key()),
                                     (second_client, path, self.body(1), existing.key()))
        self.assertEqual(sorted(r.status_code for r in response), [201, 409])
        self.assertEqual(next(r.json()["error"]["code"] for r in response if r.status_code == 409),
                         "FEEDBACK_REVISION_CONFLICT")
        self.assertEqual([r["feedback_revision"] for r in self.history(service)["items"]], [1, 2])
        with self.s.db.connection(readonly=True) as conn:
            refs = [json.loads(row[0]) for row in conn.execute(
                "SELECT source_ref FROM change_notices WHERE kind='c_feedback_changed' ORDER BY rowid")]
        self.assertEqual(refs, [{"resource_type": "ServiceFeedback", "resource_id": doc["feedback_id"],
                                 "resource_revision": doc["feedback_revision"]} for doc in self.history(service)["items"]])

    def test_patients_family_admin_and_grant_revocation(self):
        service = self.service()
        feedback = self.submit(service)
        binding, grant = self.s.bind(["feedback:read"])
        self.assertEqual(self.aggregate(client=self.s.f)["availability"], "restricted")
        self.history(service, client=self.s.f, expected=403)
        grant = self.d.revise_grant(binding, grant["meta"]["revision"], ["feedback:read", "services:read"])
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
        self.assertEqual(self.aggregate()["records"][0]["support_needs"], feedback["support_needs"])

    def test_source_pagination_availability_window_and_readonly(self):
        self.assertEqual(self.projection()["availability"], "not_collected")
        for _ in range(2):
            self.submit(self.service())
            self.s.time[0] += timedelta(seconds=1)
        start = self.s.db.path.read_bytes()
        prefix = "/api/v1" + P + "/support-feedback?"
        response = self.s.a.get(prefix + urlencode(dict(self.range, limit=1)))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()["data"]), {"source_module", "availability", "records", "reason"})
        self.assertEqual(len(response.json()["data"]["records"]), 1)
        cursor_path = response.headers["Link"].split(">")[0][1:]
        self.assertEqual(urlsplit(cursor_path).path, prefix[:-1])
        next_page = self.s.a.get(cursor_path)
        self.assertEqual(next_page.status_code, 200, next_page.text)
        self.assertNotEqual(response.json()["data"]["records"][0]["record_id"],
                            next_page.json()["data"]["records"][0]["record_id"])
        self.assertNotIn("Link", next_page.headers)
        foreign = self.s.b.get(cursor_path.replace(PA, existing.PB))
        self.assertEqual((foreign.status_code, foreign.json()["error"]["code"]), (422, "INVALID_CURSOR"))
        amended = self.s.a.get(cursor_path.replace("limit=1", "limit=2") + "&data_environment=demo")
        self.assertEqual(amended.status_code, 422)
        self.assertEqual(self.s.db.path.read_bytes(), start)
        for window in [dict(self.range, window_end=self.range["window_start"]), dict(self.range, window_start="naive")]:
            self.projection(window=window, expected=422)
        with patch.object(self.c, "source_rows", side_effect=sqlite3.OperationalError("source failure")):
            self.assertEqual(self.projection(expected=503)["code"], "SUPPORT_FEEDBACK_UNAVAILABLE")
            self.assertEqual(self.aggregate()["availability"], "unavailable")
        with patch.object(self.a, "service_feedback", None):
            self.assertEqual(self.aggregate()["availability"], "not_integrated")

    def test_a_snapshot_preserves_exact_revision_and_b_rechecks_current_feedback(self):
        service = self.service()
        first = self.submit(service)
        session = self.d.call("POST", "/sessions", {"patient_id": PA}, expected=201)
        self.d.call("POST", f"/sessions/{session['session_id']}/self-reports", {
            "client_report_id": existing.key(), "items": [{"dimension": "burden", "description": "虚构自评"}],
        }, expected=201)
        for metric, unit in METRICS.items():
            self.d.call("POST", P + "/measurements", {"source_event_id": existing.key(),
                "occurred_at": stamp(self.s.clock()), "payload": {"metric_code": metric, "unit": unit,
                    "value": 1, "method_code": "manual_entry", "missing_reason": None}}, expected=201)
        path = P + "/summary"
        window = dict(self.range, data_environment="demo", as_of=stamp(self.s.clock()))
        first_summary = self.d.call("POST", path + "-refresh", window)
        self.assertEqual(first_summary["data_status"], "fresh", first_summary["missing_items"])
        self.s.time[0] += timedelta(seconds=1)
        second = self.submit(service, self.body(1, support_needs="下一次先讨论安排"))
        past = self.d.call("GET", path + "?" + urlencode(window))
        self.assertEqual(past, first_summary)
        response = self.d.call("POST", f"/sessions/{session['session_id']}/messages", {
            "client_message_id": existing.key(), "expected_turn_count": 0, "content": "普通测试对话",
        }, expected=201)
        b_ref = response["generation"]["input_snapshot"]["summary_ref"]
        self.assertEqual((b_ref["summary_id"], b_ref["data_status"]), (first_summary["summary_id"], "stale"))
        new_summary = self.d.call("POST", path + "-refresh", dict(window, as_of=stamp(self.s.clock())))
        source = new_summary["feedback_overview"]["sources"][1]
        self.assertEqual(source["records"][0]["support_needs"], second["support_needs"])
        with self.s.db.connection(readonly=True) as conn:
            for snapshot, revision in ((first_summary, first), (new_summary, second)):
                row = conn.execute("""SELECT s.source_refs FROM s03_results r JOIN s03_computation_snapshots s USING(snapshot_id)
                                     WHERE r.result_id=?""", (snapshot["summary_id"],)).fetchone()
                feedback_refs = [r for r in json.loads(row[0]) if r["resource_type"] == "ServiceFeedback"]
                self.assertEqual(feedback_refs, [{"resource_type": "ServiceFeedback", "resource_id": revision["feedback_id"],
                                                   "resource_revision": revision["feedback_revision"]}])

    def test_s03_and_b_only_summary_signatures_remain_readable(self):
        service = self.service()
        window = dict(self.range, data_environment="demo", as_of=stamp(self.s.clock()))
        path = P + "/summary"
        for b_connected in (False, True):
            with self.subTest(b_connected=b_connected):
                summary = self.d.call("POST", path + "-refresh", window)
                summary["schema_version"] = "A-v0.4-summary-v1"
                summary["feedback_overview"]["sources"][1] = dict(
                    source_module="C", availability="not_integrated", records=[], reason="C业务尚未接入",
                )
                with self.s.db.transaction() as conn:
                    saved = self.a.signature(conn, PA, window)
                    if b_connected:
                        saved = fingerprint([saved, summary["feedback_overview"]["sources"][0]])
                    else:
                        summary["feedback_overview"]["sources"][0] = dict(
                            source_module="B", availability="not_integrated", records=[], reason="B业务尚未接入",
                        )
                    conn.execute("UPDATE s03_results SET result_json=?,input_signature=? WHERE result_id=?",
                                 (encode(summary), saved, summary["summary_id"]))
                if not b_connected:
                    self.submit(service)
                actual = self.d.call("GET", path + "?" + urlencode(window))
                self.assertEqual(actual, summary)
                self.assertNotEqual(actual["data_status"], "stale")
