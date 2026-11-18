import json
import threading
import unittest
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlencode

import test_s02 as existing
from medplatform.documents import encode, stamp
from medplatform.s04_model import MockModel, OpenAICompatible, validate_completion
from medplatform.s04_state import CASE_VERSION
from medplatform.web import create_app

CASE_A = "case-low-mood"
CASE_B = "case-anxiety"
PA, PB = existing.PA, existing.PB


class S04Tests(unittest.TestCase):
    def setUp(self):
        self.s = existing.S02Tests()
        self.s.setUp()
        self.addCleanup(self.s.doCleanups)
        self.admin = self.s.login("demo-admin")
        self.b = self.s.app.state.s04

    def api(self, method, path, body=None, *, client=None, expected=200, operation=None):
        return self.s.call(client or self.s.a, method, path, body, expected=expected, operation=operation)

    def create(self, case=CASE_A, client=None, patient=PA, invitation=None):
        return self.api("POST", "/sessions", dict(
            patient_id=patient, case_id=case, invitation_id=invitation,
            entry_source="accepted_invitation" if invitation else "user",
        ), client=client, expected=201)

    @staticmethod
    def path(session, suffix=""):
        return f"/sessions/{session['session_id']}" + suffix

    def send(self, session, content="  心情低落，只想倾诉。  ", *, expected=201, number=None, operation=None, turn=0):
        return self.api("POST", self.path(session, "/messages"), {
            "client_message_id": number or existing.key(), "content": content, "expected_turn_count": turn,
        }, expected=expected, operation=operation)

    def trigger(self, scenario, *, session=None, run=None, at=None, case=CASE_A, client=None, expected=201):
        return self.api("POST", "/demo/triggers", dict(
            case_id=case, session_id=session and session["session_id"], scenario=scenario,
            scenario_run_id=run or existing.key(), occurred_at=at or stamp(self.s.clock()),
        ), client=client or self.admin, expected=expected)

    def test_registered_cards_and_guarded_mock_config(self):
        registry = self.s.app.state.registry
        self.assertEqual({f"B{n:02d}" for n in range(1, 40)}, {name for name in registry.names if name.startswith("B")})
        # The five S05 batches authorize precisely these additional routes.
        c_routes = {
            ("GET", "/api/v1/patients/{}/support-recommendations"),
            ("GET", "/api/v1/support-resources"),
            ("GET", "/api/v1/support-resources/{}"),
            ("POST", "/api/v1/patients/{}/service-drafts"),
            ("GET", "/api/v1/service-drafts/{}"),
            ("PUT", "/api/v1/service-drafts/{}"),
            ("POST", "/api/v1/patients/{}/service-confirmations"),
            ("GET", "/api/v1/service-confirmations/{}"),
            ("POST", "/api/v1/service-confirmations/{}/revoke"),
            ("POST", "/api/v1/patients/{}/services"),
            ("GET", "/api/v1/patients/{}/services"),
            ("GET", "/api/v1/services/{}"),
            ("POST", "/api/v1/services/{}/cancel"),
            ("POST", "/api/v1/integrations/service-receipts"),
            ("POST", "/api/v1/demo/services/{}/transitions"),
            ("POST", "/api/v1/services/{}/feedback"),
            ("GET", "/api/v1/services/{}/feedback"),
            ("GET", "/api/v1/patients/{}/support-feedback"),
            ("GET", "/api/v1/peer-groups"),
            ("GET", "/api/v1/peer-groups/{}"),
            ("POST", "/api/v1/peer-groups/{}/memberships"),
            ("POST", "/api/v1/memberships/{}/leave"),
            ("GET", "/api/v1/peer-groups/{}/posts"),
            ("POST", "/api/v1/peer-groups/{}/posts"),
            ("POST", "/api/v1/peer-posts/{}/moderation"),
            ("GET", "/api/v1/peer-memberships/me"),
            ("GET", "/api/v1/patients/{}/points"),
            ("GET", "/api/v1/points/rules"),
            ("GET", "/api/v1/patients/{}/points-ledger"),
            ("POST", "/api/v1/internal/points/reconcile"),
            ("POST", "/api/v1/patients/{}/management-reviews"),
            ("GET", "/api/v1/patients/{}/management-reviews"),
            ("GET", "/api/v1/rewards"),
            ("GET", "/api/v1/rewards/{}"),
            ("POST", "/api/v1/patients/{}/redemptions"),
            ("GET", "/api/v1/patients/{}/redemptions"),
            ("GET", "/api/v1/redemptions/{}"),
            ("POST", "/api/v1/integrations/fulfillment-receipts"),
            ("GET", "/api/v1/redemptions/{}/fulfillment"),
            ("POST", "/api/v1/redemptions/{}/feedback"),
        }
        self.assertEqual(registry.routes & c_routes, c_routes)
        self.assertEqual(len(registry.routes - c_routes), 114)
        self.api("GET", "/cases", expected=403)
        cases = self.api("GET", "/cases", client=self.admin)["items"]
        self.assertEqual({d["focus"] for d in cases}, {"low_mood", "anxiety_concerns", "treatment_fatigue"})
        self.assertTrue(all(d["opening_draft"] for d in cases))
        status = self.api("GET", "/config/status", client=self.admin)
        version = next(r["version"] for r in status["version_refs"] if r["kind"] == "model_config")
        probe = {"profile_id": "mock-single-pass", "expected_config_version": version, "allow_external_call": False}
        op = existing.key()
        checked = self.api("POST", "/config/check-model", probe, client=self.admin, operation=op)
        self.assertEqual(checked, self.api("POST", "/config/check-model", probe, client=self.admin, operation=op))
        self.assertEqual(checked["network_attempt_count"], 0)
        self.assertIsNone(checked["usage"]["total_tokens"])
        self.api("PUT", "/config/model-profile", {
            "profile_id": "unregistered-real", "expected_config_version": version, "confirmed": True,
        }, client=self.admin, expected=422)
        selected = self.api("PUT", "/config/model-profile", {
            "profile_id": "mock-single-pass", "expected_config_version": version, "confirmed": True,
        }, client=self.admin)
        self.assertNotEqual(selected["model_config_version"], version)
        self.api("POST", "/config/check-model", probe, client=self.admin, expected=409)

    def test_exact_source_dedupe_case_isolation_and_readonly_strategy(self):
        created = self.create()
        self.assertEqual(created["ui_mode"], "normal")
        key, number = existing.key(), existing.key()
        result = self.send(created, number=number, operation=key)
        self.assertEqual(self.send(created, number=number, operation=key), result)
        self.assertEqual(self.send(created, number=number), result)
        self.assertEqual(result["user_message"]["content"], "  心情低落，只想倾诉。  ")
        self.assertEqual(result["generation"]["budget"]["used_network_attempts"], 0)
        self.assertEqual(result["business_output"]["difficulty_cues"][0]["evidence"], "心情低落")
        self.assertEqual(result["generation"]["actual_pipeline"], "single_pass")
        self.assertIsNone(result["intervention_id"])
        self.send(created, "不同正文", number=number, expected=409)
        self.api("GET", self.path(created, "/messages"), client=self.s.b, expected=404)
        self.api("POST", "/sessions", {"patient_id": PA, "case_id": CASE_B}, expected=404)
        before = self.s.db.path.read_bytes()
        view = self.api("GET", self.path(created, "/strategy"))
        self.assertEqual(view["intensity_mapping"]["availability"], "not_configured")
        self.assertIsNone(view["intensity_mapping"]["support_intensity"])
        self.assertEqual(len(view["intensity_mapping"]), 8)
        self.assertEqual(len(self.api("GET", self.path(created, "/messages"))["items"]), 2)
        self.assertEqual(self.s.db.path.read_bytes(), before)

    def test_stale_turn_recovers_without_saving_or_generating_rejected_message(self):
        session = self.create()
        messages = self.path(session, "/messages")
        rejected_id, new_id, operation = existing.key(), existing.key(), existing.key()
        adapter = self.b.dialogue.adapter
        with patch.object(adapter, "complete", wraps=adapter.complete) as complete:
            self.send(session)
            error = self.send(session, number=rejected_id, operation=operation, turn=0, expected=409)
            self.assertEqual(error["code"], "SESSION_REVISION_CONFLICT")
            lookup = self.api("GET", messages + "?client_message_id=" + rejected_id, expected=404)
            self.assertEqual(lookup["code"], "RESOURCE_NOT_FOUND")
            self.assertEqual(complete.call_count, 1)
            current = self.api("GET", self.path(session))
            self.assertEqual(current["turn_count"], 1)
            new_operation = existing.key()
            saved = self.send(current, number=new_id, operation=new_operation, turn=current["turn_count"])
            self.assertEqual(self.send(current, number=new_id, operation=new_operation, turn=1), saved)
            self.assertEqual(self.send(current, number=new_id, turn=1), saved)
            self.assertEqual(complete.call_count, 2)
        self.assertEqual(self.api("GET", self.path(session))["turn_count"], 2)
        stored = self.api("GET", messages)["items"]
        self.assertEqual(len(stored), 4)
        self.assertEqual([m["client_message_id"] for m in stored if m["client_message_id"] == new_id], [new_id])
        self.assertNotIn(rejected_id, [m["client_message_id"] for m in stored])

    def test_failed_message_restores_and_retries_original_generation(self):
        s = self.create()
        self.trigger("empty_response", session=s)
        number = existing.key()
        self.send(s, number=number, expected=502)
        original = self.api("GET", self.path(s, "/messages?client_message_id=" + number))["items"][0]
        self.assertEqual(original["generation_status"], "failed")
        retry_path = f"/messages/{original['message_id']}/generation-retries"
        body = {"generation_id": original["generation_id"], "expected_turn_count": 1}
        op = existing.key()
        result = self.api("POST", retry_path, body, operation=op)
        self.assertEqual(result, self.api("POST", retry_path, body, operation=op))
        self.assertEqual(result["user_message"]["message_id"], original["message_id"])
        self.assertEqual(result["generation"]["generation_id"], original["generation_id"])
        self.assertEqual([r["status"] for r in result["generation"]["calls"]], ["failed", "succeeded"])
        restarted = create_app(self.s.settings, clock=self.s.clock)
        fresh = self.s.login("demo-patient-a", app=restarted)
        saved = self.api("GET", self.path(s, "/messages"), client=fresh)["items"]
        self.assertEqual(len(saved), 2)

    def test_retry_keeps_audit_snapshot_without_reusing_superseded_plan(self):
        plan = self.s.confirm(effective_from=stamp(self.s.clock()))
        session = self.create()
        self.trigger("empty_response", session=session)
        number = existing.key()
        self.send(session, number=number, expected=502)
        message = self.api("GET", self.path(session, "/messages?client_message_id=" + number))["items"][0]
        self.s.confirm(existing_plan_id=plan["plan_id"], expected_plan_version=1,
                       effective_from=stamp(self.s.clock() + timedelta(seconds=2)))
        self.s.time[0] += timedelta(seconds=3)
        with patch.object(self.b.dialogue.adapter, "complete", wraps=self.b.dialogue.adapter.complete) as attempted:
            result = self.api("POST", f"/messages/{message['message_id']}/generation-retries",
                              {"generation_id": message["generation_id"], "expected_turn_count": 1})
        self.assertEqual(result["generation"]["input_snapshot"]["plan_refs"],
                         [{"plan_id": plan["plan_id"], "plan_version": 1}])
        self.assertFalse(any("当前正式计划引用" in part["content"] for part in attempted.call_args.args[0]))

    def test_live_summary_rechecks_source_correction_without_rewriting_history(self):
        when = stamp(self.s.clock())
        event = self.api("POST", f"/patients/{PA}/medication-events", {
            "source_event_id": existing.key(), "occurred_at": when, "reported_status": "unknown"
        }, expected=201)
        window = dict(window_start=stamp(self.s.clock() - timedelta(days=1)),
                      window_end=stamp(self.s.clock() + timedelta(days=1)), data_environment="demo")
        summary = self.api("POST", f"/patients/{PA}/summary-refresh", window)
        analytics = self.s.app.state.s03_analytics
        principal = analytics.auth.resolve(self.s.a.cookies.get("session"))
        with self.s.db.connection(readonly=True) as conn:
            self.assertTrue(analytics.summary_feedback_current(conn, principal, PA, summary))
        self.s.time[0] += timedelta(seconds=1)
        self.api("POST", f"/events/{event['event_id']}/withdrawals",
                 {"expected_revision": 1, "reason": "虚构来源撤回"})
        with self.s.db.connection(readonly=True) as conn:
            self.assertFalse(analytics.summary_feedback_current(conn, principal, PA, summary))
        self.assertEqual(self.api("GET", f"/patients/{PA}/summary?" + urlencode(dict(window, as_of=when))), summary)

    def test_unknown_result_never_retries(self):
        session = self.create()
        self.trigger("llm_timeout", session=session)
        number = existing.key()
        self.send(session, number=number, expected=502)
        failed = self.api("GET", self.path(session, "/messages?client_message_id=" + number))["items"][0]
        self.assertEqual(failed["generation_status"], "outcome_unknown")
        error = self.api("POST", "/messages/" + failed["message_id"] + "/generation-retries", {
            "generation_id": failed["generation_id"], "expected_turn_count": 1,
        }, expected=409)
        self.assertEqual(error["code"], "GENERATION_NOT_RETRYABLE")

    def test_close_can_write_while_adapter_runs_and_late_result_stays_audit(self):
        session = self.create()
        started, release = threading.Event(), threading.Event()
        completed = []
        adapter = self.b.dialogue.adapter

        def blocking(messages, **options):
            started.set()
            if not release.wait(10):
                raise RuntimeError("test adapter did not resume")
            return MockModel().complete(messages, **options)

        number = existing.key()
        other_client = self.s.login("demo-patient-a")
        with patch.object(adapter, "complete", side_effect=blocking):
            def send():
                response = self.s.a.post("/api/v1" + self.path(session, "/messages"), json={
                    "client_message_id": number, "expected_turn_count": 0, "content": "只想倾诉",
                }, headers={"Origin": existing.BASE, "X-CSRF-Token": self.s.a.csrf,
                            "Idempotency-Key": existing.key()})
                completed.append(response)
            thread = threading.Thread(target=send, daemon=True)
            thread.start()
            try:
                self.assertTrue(started.wait(8))
                latest = self.api("GET", self.path(session), client=other_client)
                self.api("POST", self.path(session, "/close"), {"expected_revision": latest["meta"]["revision"]},
                         client=other_client)
            finally:
                release.set()
                thread.join(10)
        self.assertEqual(completed[0].status_code, 409)
        saved = self.api("GET", self.path(session, "/messages"))["items"]
        self.assertEqual([(m["role"], m["generation_status"]) for m in saved], [("user", "cancelled")])

    def test_family_revocation_and_descriptive_feedback(self):
        session = self.create()
        _, grant = self.s.bind(["dialogue:read", "summary:read"])
        self.api("GET", self.path(session, "/messages"), client=self.s.f)
        self.api("POST", self.path(session, "/messages"), {
            "client_message_id": existing.key(), "content": "代发不会成功", "expected_turn_count": 0,
        }, client=self.s.f, expected=403)
        self.api("GET", self.path(session, "/assessments"), client=self.s.f, expected=403)
        self.api("POST", f"/grants/{grant['grant_id']}/revoke", {
            "expected_revision": grant["meta"]["revision"], "reason": "test",
        })
        self.api("GET", self.path(session, "/messages"), client=self.s.f, expected=403)
        sample = {"client_report_id": existing.key(), "items": [{"dimension": "burden", "description": "隔离自评"}]}
        report = self.api("POST", self.path(session, "/self-reports"), sample, expected=201)
        self.assertIsNone(report["score"])
        self.assertIsNone(report["scoring_method_version"])
        self.assertTrue(report["score_missing_reason"])
        query = urlencode(dict(window_start=stamp(self.s.clock() - timedelta(days=1)),
                              window_end=stamp(self.s.clock() + timedelta(days=1)), data_environment="demo"))
        response = self.api("GET", f"/patients/{PA}/feedback-overview?" + query)["sources"]
        self.assertEqual([s["availability"] for s in response], ["available", "not_collected"])
        self.assertNotIn("隔离自评", json.dumps(response, ensure_ascii=False))
        self.assertEqual(response[0]["records"][0]["record_id"], report["assessment_id"])
        export_query = urlencode(dict(window_start=stamp(self.s.clock() - timedelta(days=1)),
                                     window_end=stamp(self.s.clock() + timedelta(days=1)), patient_id=PA))
        self.assertEqual(self.api("GET", "/interventions/export?" + export_query)["items"], [])

    def test_a41_rechecks_feedback_and_b_source_scopes_without_exposing_content(self):
        session = self.create()
        query = urlencode(dict(window_start=stamp(self.s.clock() - timedelta(days=1)),
                               window_end=stamp(self.s.clock() + timedelta(days=1)), data_environment="demo"))
        path = f"/patients/{PA}/feedback-overview?" + query

        def source(client=None):
            return next(s for s in self.api("GET", path, client=client)["sources"] if s["source_module"] == "B")

        binding, grant = self.s.bind(["feedback:read"])

        def change_scopes(*scopes):
            nonlocal grant
            grant = self.api("PUT", f"/family-bindings/{binding['binding_id']}/grant", {
                "expected_revision": grant["meta"]["revision"], "scopes": list(scopes),
                "valid_until": None, "confirmed": True,
            })

        restricted = source(self.s.f)
        self.assertEqual((restricted["availability"], restricted["records"]), ("restricted", []))
        self.assertTrue(restricted["reason"])
        empty = source()
        self.assertEqual((empty["availability"], empty["records"]), ("not_collected", []))
        secret = "仅用于隔离权限测试的自评正文"
        report = self.api("POST", self.path(session, "/self-reports"), {
            "client_report_id": existing.key(), "items": [{"dimension": "burden", "description": secret}],
        }, expected=201)
        owner_view = source()
        self.assertEqual(owner_view["availability"], "available")
        self.assertEqual([ref["record_id"] for ref in owner_view["records"]], [report["assessment_id"]])
        self.assertNotIn(secret, json.dumps(owner_view, ensure_ascii=False))
        self.assertEqual(source(self.s.f), restricted)
        change_scopes("feedback:read", "interventions:read")
        self.assertEqual(source(self.s.f), restricted)
        change_scopes("feedback:read", "assessment:read")
        self.assertEqual(source(self.s.f), owner_view)
        change_scopes("feedback:read", "assessment:read", "interventions:read")
        self.assertEqual(source(self.s.f), owner_view)
        feedback = f"/patients/{PA}/intervention-feedback?" + query.replace("&data_environment=demo", "")
        self.assertEqual(self.api("GET", feedback, client=self.s.f, expected=403)["code"],
                         "PATIENT_CONFIRMATION_REQUIRED")
        change_scopes("feedback:read")
        self.assertEqual(source(self.s.f), restricted)
        self.api("POST", f"/grants/{grant['grant_id']}/revoke", {
            "expected_revision": grant["meta"]["revision"], "reason": "withdraw test grant",
        })
        denied = self.api("GET", path, client=self.s.f, expected=403)
        self.assertEqual(denied["code"], "SCOPE_REQUIRED")
        for unrelated in (self.s.b, self.admin):
            self.assertEqual(self.api("GET", path, client=unrelated, expected=404)["code"], "RESOURCE_NOT_FOUND")

    def test_s04_summary_signature_still_tracks_b_source_changes(self):
        session = self.create()
        window = dict(window_start=stamp(self.s.clock() - timedelta(days=1)),
                      window_end=stamp(self.s.clock() + timedelta(days=1)), data_environment="demo")
        summary = self.api("POST", f"/patients/{PA}/summary-refresh", window)
        query = urlencode(dict(window, as_of=stamp(self.s.clock())))
        path = f"/patients/{PA}/summary?" + query
        self.assertEqual(self.api("GET", path), summary)
        self.api("POST", self.path(session, "/self-reports"), {
            "client_report_id": existing.key(), "items": [{"dimension": "burden", "description": "虚构正文"}],
        }, expected=201)
        before = self.s.db.path.read_bytes()
        stale = self.api("GET", path)
        self.assertEqual(stale["data_status"], "stale")
        self.assertEqual(stale["summary_id"], summary["summary_id"])
        self.assertEqual(stale["feedback_overview"], summary["feedback_overview"])
        self.assertEqual(self.s.db.path.read_bytes(), before)

    def test_expiry_projection_and_registered_a_task(self):
        session = self.create()
        path = self.path(session, "/ui-mode")
        simple = self.api("PUT", path, {"ui_mode": "simplified", "expected_revision": 1, "confirmed": True})
        self.assertEqual(simple["minimum_until"], simple["changed_at"])
        self.s.time[0] += timedelta(hours=2)
        before = self.s.db.path.read_bytes()
        projected = self.api("GET", path + "?include_history=true")
        self.assertEqual((projected["current"]["ui_mode"], projected["effective_ui_mode"]), ("simplified", "normal"))
        self.assertEqual(len(projected["changes"]), 1)
        self.assertEqual(self.s.db.path.read_bytes(), before)
        task = self.api("GET", f"/patients/{PA}/tasks")["items"][0]
        self.assertEqual(task["owner_module"], "B")
        outcome = self.api("POST", f"/tasks/{task['task_id']}/run", {"expected_revision": task["meta"]["revision"]},
                           client=self.admin)
        self.assertEqual(outcome["delivery_status"], "not_applicable")
        restored = self.api("GET", path + "?include_history=true")
        self.assertEqual(restored["current"]["ui_mode"], "normal")
        self.assertEqual(restored["changes"][-1]["source"], "expiry")
        entered = self.api("PUT", path, {"ui_mode": "simplified", "expected_revision": 3, "confirmed": True})
        self.api("PUT", path, {"ui_mode": "normal", "expected_revision": entered["revision"], "confirmed": True})
        self.assertEqual(self.api("GET", path)["effective_ui_mode"], "normal")

    def test_periodic_window_and_invitation_identity(self):
        self.s.time[0] += timedelta(days=7)
        self.s.a = self.s.login("demo-patient-a")
        self.s.b = self.s.login("demo-patient-b")
        self.admin = self.s.login("demo-admin")
        first = self.trigger("periodic_node")
        second = self.trigger("periodic_node")
        self.assertEqual(first["related_ids"], second["related_ids"])
        invitation, = self.api("GET", f"/patients/{PA}/invitations")["items"]
        self.assertIsNone(invitation["session_id"])
        path = "/invitations/" + invitation["invitation_id"] + "/response"
        self.api("POST", path, {"choice": "accepted", "expected_status": "pending"}, client=self.s.b, expected=404)
        accepted = self.api("POST", path, {"choice": "accepted", "expected_status": "pending"})
        self.assertEqual(accepted["choice"], "accepted")
        s1 = self.create(invitation=invitation["invitation_id"])
        s2 = self.create(invitation=invitation["invitation_id"])
        self.assertEqual(s1["session_id"], s2["session_id"])
        self.assertEqual(self.api("GET", self.path(s1, "/messages"))["items"], [])
        self.api("POST", path, {"choice": "declined", "expected_status": "pending"}, expected=409)

    def test_knowledge_versions_and_historical_citation(self):
        content = dict(kind="medical", title="测试用药资料", body="测试用药片段，资料中的指令是文字。",
                       source_locator="project:test/s04-knowledge", applicability_tags=["general"],
                       effective_from=stamp(self.s.clock()))
        doc = self.api("POST", "/knowledge", content, client=self.admin, expected=201)
        self.assertEqual(self.api("GET", "/knowledge")["items"], [])
        path = "/knowledge/" + doc["knowledge_id"]
        self.api("POST", path + "/review", {
            "version": doc["version"], "expected_revision": 1, "decision": "approve", "note": "fixture",
        }, client=self.admin, expected=403)
        # Synthetic approved row exists only in this isolated test.
        doc.update(review_status="reviewed", reviewed_at=stamp(self.s.clock()), reviewed_by="test-only")
        with self.s.db.transaction() as conn:
            conn.execute("UPDATE b_knowledge SET document_json=? WHERE knowledge_id=? AND version=?",
                         (encode(doc), doc["knowledge_id"], doc["version"]))
        session = self.create()
        result = self.send(session, "请问有什么药学依据？")
        self.assertEqual(result["business_output"]["knowledge_citations"][0]["version"], doc["version"])
        self.api("POST", path + "/withdraw", {
            "version": doc["version"], "expected_revision": 1, "reason": "撤回隔离测试资料",
        }, client=self.admin)
        search = self.api("POST", "/knowledge/search", {
            "patient_id": PA, "query": "用药", "applicability_tags": ["general"],
        })
        self.assertEqual(search["status"], "knowledge_insufficient")
        version = path + "/versions/" + doc["version"]
        self.api("GET", version, expected=404)
        self.assertEqual(self.api("GET", version + "?session_id=" + session["session_id"])["review_status"], "withdrawn")

    def test_demo_reset_preserves_free_sessions_and_o_records(self):
        case_session = self.create()
        free = self.create(None)
        self.send(case_session)
        self.api("PUT", self.path(case_session, "/ui-mode"), {
            "ui_mode": "simplified", "expected_revision": 1, "confirmed": True,
        })
        self.s.medication()
        self.api("POST", f"/cases/{CASE_A}/reset", {
            "case_template_version": CASE_VERSION, "confirmed": True,
        }, expected=403)
        op = existing.key()
        reset = lambda: self.api("POST", f"/cases/{CASE_A}/reset", {
            "case_template_version": CASE_VERSION, "confirmed": True,
        }, client=self.admin, operation=op)
        result = reset()
        self.assertEqual(result["affected_session_ids"], [case_session["session_id"]])
        self.assertEqual(len(result["cancelled_task_ids"]), 1)
        later = self.create()
        self.assertEqual(reset(), result)
        self.api("GET", self.path(later))
        self.api("GET", self.path(free))
        self.api("GET", self.path(case_session), expected=404)
        self.assertEqual(len(self.api("GET", f"/patients/{PA}/medications")["items"]), 1)

    def test_demo_reset_cancels_only_target_unbound_invitations_and_keeps_responses(self):
        self.s.time[0] += timedelta(days=7)
        self.s.a = self.s.login("demo-patient-a")
        self.s.b = self.s.login("demo-patient-b")
        self.admin = self.s.login("demo-admin")
        case_session = self.create()
        free = self.create(None)

        def invite(**options):
            return self.trigger("state_event", **options)["related_ids"][0]

        def respond(identifier, choice="accepted", session=None, expected=200):
            return self.api("POST", f"/invitations/{identifier}/response", {
                "choice": choice, "expected_status": "pending", "session_id": session and session["session_id"],
            }, expected=expected)

        def visible(patient=PA, client=None):
            return {d["invitation_id"]: d for d in self.api("GET", f"/patients/{patient}/invitations", client=client)["items"]}

        pending, accepted, declined = invite(), invite(), invite()
        bound, resolved, outside = invite(session=case_session), invite(), invite()
        other_case = invite(case=CASE_B)
        periodic, = self.trigger("periodic_node")["related_ids"]
        with self.s.db.transaction() as conn:
            unlinked = self.b.state.invitation(conn, PA, None, "state_event", existing.key(), stamp(self.s.clock()))
        accepted_response = respond(accepted)
        respond(declined, "declined")
        respond(resolved, session=case_session)
        respond(outside, session=free)
        first = visible()
        self.assertEqual((first[pending]["status"], first[pending]["session_id"]), ("pending", None))
        self.assertEqual((first[periodic]["status"], first[periodic]["session_id"]), ("pending", None))
        self.assertEqual((first[accepted]["status"], first[accepted]["resolved_session_id"]), ("accepted", None))
        self.assertEqual(first[bound]["session_id"], case_session["session_id"])
        self.assertEqual(first[resolved]["resolved_session_id"], case_session["session_id"])
        other_before = visible(PB, self.s.b)
        self.assertEqual(other_before[other_case]["status"], "pending")

        self.api("POST", f"/cases/{CASE_A}/reset", {"case_template_version": CASE_VERSION, "confirmed": True},
                 client=self.admin)
        after = visible()
        self.assertNotIn(bound, after)
        for identifier in (pending, accepted, resolved, periodic):
            self.assertEqual((after[identifier]["status"], after[identifier]["resolved_session_id"]),
                             ("cancelled", None))
        for identifier in (declined, outside, unlinked["invitation_id"]):
            self.assertEqual(after[identifier], first[identifier])
        self.assertEqual(visible(PB, self.s.b), other_before)
        self.assertEqual(self.trigger("periodic_node")["related_ids"], [periodic])
        self.assertEqual(visible(), after)
        self.assertEqual(respond(pending, expected=409)["code"], "INVITATION_RESPONSE_CONFLICT")
        self.assertEqual(respond(accepted), accepted_response)
        self.assertEqual(self.api("POST", "/sessions", {
            "patient_id": PA, "case_id": CASE_A, "entry_source": "accepted_invitation", "invitation_id": accepted,
        }, expected=409)["code"], "INVITATION_NOT_ACCEPTED")

    def test_missing_c_draft_and_external_identity_cannot_fabricate_success(self):
        session = self.create()
        error = self.api("POST", "/referrals", {
            "patient_id": PA, "session_id": session["session_id"], "resource_id": "resource",
            "service_draft_id": "draft", "service_draft_revision": 1,
            "confirmation_ref_id": "confirm", "sharing_scope_ref_id": "scope",
        }, expected=404)
        self.assertEqual(error["code"], "RESOURCE_NOT_FOUND")
        error = self.api("POST", "/integrations/state-events", {
            "source_event_id": "untrusted", "patient_id": PA, "event_type": "consent_revoked",
            "summary_ref": None, "occurred_at": stamp(self.s.clock()), "rule_version": "test",
        }, client=self.admin, expected=403)
        self.assertEqual(error["code"], "MODULE_IDENTITY_REQUIRED")


class OfflineModelTests(unittest.TestCase):
    def test_compatible_transport_does_not_force_optional_parameters(self):
        sent = []

        def transport(payload, timeout):
            sent.append((payload, timeout))
            return 200, {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}

        adapter = OpenAICompatible(transport, "unit-placeholder", provider_label="offline-test")
        result = adapter.complete([], timeout=7, output_limit=1024)
        self.assertEqual(result.content, "{}")
        self.assertIsNone(result.usage["total_tokens"])
        self.assertEqual(sent[0][0], dict(model="unit-placeholder", messages=[], n=1, stream=False))

    def test_invalid_core_and_forged_auxiliary(self):
        self.assertEqual(validate_completion("{", {}, lambda _: False), (None, False))
        raw = json.dumps(dict(assistant_reply="原文", support_focus="listening", communication_strategy=["reflection"],
                              suggested_action=None, knowledge_citations=[], change_readiness=None,
                              difficulty_cues=[dict(category="low_mood", label="test", evidence="some",
                                                    source_message_id="unrelated")]))
        clean, degraded = validate_completion(raw, {"actual": "some text"}, lambda _: False)
        self.assertTrue(degraded)
        self.assertEqual(clean["difficulty_cues"], [])
