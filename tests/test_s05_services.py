import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import patch

import test_s02 as existing
import test_s05_drafts as drafts
from medplatform.documents import stamp
from medplatform.web import create_app

PA, PB = existing.PA, existing.PB
SERVICES = f"/patients/{PA}/services"
PROVIDER = "provider-pharmacist-demo"
TOKEN = "isolated-test-fixture-token-no-external-access"
RECEIPTS = "/api/v1/integrations/service-receipts"


class FormalServiceTests(unittest.TestCase):
    def setUp(self):
        self.d = drafts.DraftConsentTests()
        self.d.setUp()
        self.addCleanup(self.d.doCleanups)
        self.s = self.d.s
        self.admin = self.s.login("demo-admin")
        self.execution = self.s.app.state.s03_execution
        self.adapter = self.execution.service_dispatch

    @staticmethod
    def body(draft, consent):
        return dict(service_draft_id=draft["service_draft_id"], draft_revision=draft["draft_revision"],
                    confirmation_ref_id=consent["confirmation_ref_id"],
                    sharing_scope_ref_id=consent["sharing_scope"]["sharing_scope_ref_id"])

    def prepare(self, **kwargs):
        draft = self.d.create(**kwargs)
        return draft, self.d.confirm(draft)

    def create(self, body=None, *, client=None, expected=201, key=None):
        return self.d.call("POST", SERVICES, body if body is not None else self.body(*self.prepare()),
                           client, expected, key)

    @staticmethod
    def path(doc):
        return "/services/" + doc["service_id"]

    @staticmethod
    def task(doc):
        return "/tasks/" + doc["dispatch_task_id"]

    def counts(self):
        with self.s.db.connection(readonly=True) as conn:
            return tuple(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                         for table in ("c_services", "c_service_history", "a_tasks", "a_executions",
                                       "c_service_dispatches", "c_service_provider_receipts"))

    def run_task(self, doc, *, revision=None, key=None, expected=200, client=None):
        path = self.task(doc)
        if revision is None:
            revision = self.d.call("GET", path, client=self.admin)["meta"]["revision"]
        return self.d.call("POST", path + "/run", {"expected_revision": revision}, client or self.admin, expected, key)

    def transition(self, doc, status, *, client=None, expected=200):
        return self.d.call("POST", "/demo" + self.path(doc) + "/transitions",
                           dict(expected_revision=doc["meta"]["revision"], target_status=status, reason="模拟测试记录"),
                           client or self.admin, expected)

    def cancel(self, doc, *, expected=200, key=None):
        return self.d.call("POST", self.path(doc) + "/cancel",
                           dict(expected_revision=doc["meta"]["revision"], reason="本人停止模拟"),
                           expected=expected, key=key)

    def receipt_client(self, subject=PROVIDER):
        settings = self.s.settings.model_copy(update={"DEMO_SERVICE_RECEIPT_SUBJECT": subject,
                                                     "DEMO_SERVICE_RECEIPT_TOKEN": type(self.s.settings.DEMO_SERVICE_RECEIPT_TOKEN)(TOKEN)})
        app = create_app(settings, clock=self.s.clock)
        return self.s.login("demo-admin", app)

    def receipt(self, client, body, *, enabled=True, expected=200, key=None):
        response = client.post(RECEIPTS, json=body, headers={
            "Idempotency-Key": key or existing.key(), **({"Authorization": "Bearer " + TOKEN} if enabled else {}),
        })
        self.assertEqual(response.status_code, expected, response.text)
        envelope = response.json()
        self.assertEqual(set(envelope), {"request_id", "status", "data", "error"})
        return envelope["data"] if expected < 400 else envelope["error"]

    def receipt_body(self, doc, status, **fields):
        return dict(dict(provider_event_id=existing.key(), service_id=doc["service_id"], status=status,
                         expected_revision=doc["meta"]["revision"], occurred_at=stamp(self.s.clock()),
                         result_summary=None, failure_reason=None, response_text=None), **fields)

    def test_requires_exact_link_reused_only_after_explicit_confirmation(self):
        draft, original = self.prepare(text="第一份草稿")
        second = self.d.create(text="第二份草稿")
        self.assertNotEqual(draft["service_draft_id"], second["service_draft_id"])
        self.assertEqual(self.create(self.body(second, original), expected=409)["code"], "SERVICE_CONFIRMATION_REQUIRED")
        self.assertEqual(self.counts(), (0, 0, 0, 0, 0, 0))
        reuse = self.d.confirm(second, hint=original["confirmation_ref_id"], expected=200)
        self.assertEqual(reuse, original)
        self.assertEqual(self.create(self.body(second, reuse))["request_text"], "第二份草稿")
        with self.s.db.connection(readonly=True) as conn:
            links = conn.execute("SELECT service_draft_id,draft_revision FROM c_draft_confirmations").fetchall()
            self.assertEqual({tuple(row) for row in links},
                             {(draft["service_draft_id"], 1), (second["service_draft_id"], 1)})

    def test_revoked_expired_edited_and_guarded_grant_block_new_services(self):
        with self.subTest("edited"):
            draft, consent = self.prepare()
            current = self.d.read(draft)
            revised = self.d.call("PUT", self.d.draft_path(draft), {
                "expected_revision": current["meta"]["revision"], "content": dict(drafts.RESOURCE, request_text="新修订"),
            })
            for version in (draft, revised):
                self.assertEqual(self.create(self.body(version, consent), expected=409)["code"], "SERVICE_CONFIRMATION_REQUIRED")
        with self.subTest("revoked"):
            self.d.revoke(consent)
            self.assertEqual(self.create(self.body(draft, consent), expected=409)["code"], "SERVICE_CONFIRMATION_REQUIRED")
        with self.subTest("grant"):
            binding, grant = self.s.bind(drafts.FAMILY_SCOPES)
            precise = {grant["grant_id"]: grant["grant_version"]}
            with patch.object(self.d.service.sharing, "terms", return_value=precise):
                grant_draft, grant_consent = self.prepare()
                self.d.revise_grant(binding, grant["meta"]["revision"], ["support:read"])
                self.assertEqual(self.create(self.body(grant_draft, grant_consent), expected=409)["code"],
                                 "SERVICE_CONFIRMATION_REQUIRED")
        with self.subTest("expires at boundary"):
            draft, consent = self.prepare()
            self.s.time[0] += timedelta(hours=24)
            self.assertEqual(self.create(self.body(draft, consent), client=self.s.login("demo-patient-a"),
                                         expected=409)["code"], "SERVICE_CONFIRMATION_REQUIRED")
        self.assertEqual(self.counts(), (0, 0, 0, 0, 0, 0))

    def test_unique_formal_service_database_and_query_after_lost_response(self):
        draft, consent = self.prepare()
        self.s.time[0] += timedelta(hours=24, microseconds=-1)
        patient = self.s.login("demo-patient-a")
        body, key = self.body(draft, consent), existing.key()
        created = self.create(body, client=patient, key=key)
        self.assertEqual((created["status"], created["meta"]["revision"]), ("submitted", 1))
        self.assertEqual(self.create(body, client=patient, key=key), created)
        self.assertEqual(self.create(body, client=patient), created)
        draft_view = self.d.read(draft, patient)
        self.assertEqual((draft_view["status"], draft_view["service_id"]), ("submitted", created["service_id"]))
        self.assertEqual(self.d.call("GET", SERVICES + "?status=submitted", client=patient)["items"], [created])
        self.assertEqual(self.d.call("GET", self.path(created), client=patient), created)
        self.assertEqual(self.d.call("GET", SERVICES + "?status=completed", client=patient)["items"], [])
        task = self.d.call("GET", self.task(created), client=patient)
        self.assertEqual((task["status"], task["payload"]), ("pending", {
            "service_id": created["service_id"], "service_revision": 1,
            "confirmation_ref_id": body["confirmation_ref_id"], "sharing_scope_ref_id": body["sharing_scope_ref_id"],
        }))
        self.assertEqual(task["valid_until"], consent["valid_until"])
        with self.assertRaisesRegex(sqlite3.IntegrityError, "c_services.patient_id"):
            with self.s.db.transaction() as conn:
                conn.execute("""INSERT INTO c_services SELECT 'other-service',patient_id,service_draft_id,draft_revision,
                             confirmation_ref_id,sharing_scope_ref_id,'other-task',submitted_at FROM c_services""")
        self.assertEqual(self.counts(), (1, 1, 1, 0, 0, 0))

    def test_permission_minimal_fields_and_revocation(self):
        draft, consent = self.prepare(text="患者私密问题")
        body = self.body(draft, consent)
        binding, grant = self.s.bind(["services:read"])
        self.assertEqual(self.create(body, client=self.s.f, expected=403)["code"], "PATIENT_CONFIRMATION_REQUIRED")
        value = self.create(body)
        self.d.call("GET", self.path(value), client=self.s.b, expected=404)
        family = self.d.call("GET", self.path(value), client=self.s.f)
        self.assertEqual(family["service_id"], value["service_id"])
        self.assertNotIn("患者私密问题", json.dumps(family, ensure_ascii=False))
        self.d.call("GET", self.task(value), client=self.s.f, expected=403)
        self.d.call("POST", self.path(value) + "/cancel", {"expected_revision": 1, "reason": "禁止代理"},
                    self.s.f, 403)
        self.transition(value, "failed", client=self.s.a, expected=403)
        self.d.revise_grant(binding, grant["meta"]["revision"], ["tasks:read"])
        self.d.call("GET", self.path(value), client=self.s.f, expected=403)
        self.d.call("GET", self.task(value), client=self.s.f, expected=403)
        self.assertEqual(self.d.call("GET", f"/patients/{PA}/tasks", client=self.s.f)["items"], [])

    def test_concurrent_direct_and_b_share_one_service_and_keep_case(self):
        draft, consent = self.prepare()
        body = self.body(draft, consent)
        session = self.d.call("POST", "/sessions", dict(patient_id=PA, case_id="case-low-mood", entry_source="user"),
                              expected=201)
        referral = dict(patient_id=PA, session_id=session["session_id"], resource_id=draft["resource_id"],
                        service_draft_revision=body["draft_revision"],
                        **{k: v for k, v in body.items() if k != "draft_revision"})
        first, second = self.d.concurrent((self.s.a, SERVICES, body, existing.key()),
                                          (self.s.login("demo-patient-a"), "/referrals", referral, existing.key()))
        self.assertEqual([first.status_code, second.status_code], [201, 201], [first.text, second.text])
        service, proxy = (response.json()["data"] for response in (first, second))
        self.assertEqual(proxy["service_id"], service["service_id"])
        self.assertEqual(self.d.call("POST", "/referrals", referral, expected=201), proxy)
        self.assertEqual(self.counts(), (1, 1, 1, 0, 0, 0))
        self.cancel(service)
        self.assertEqual(self.d.call("GET", "/referrals/" + proxy["referral_id"])["service_status"], "cancelled")
        err = self.d.call("POST", "/cases/case-low-mood/reset", {"case_template_version": "s04-cases-v1", "confirmed": True},
                          self.admin, 409)
        self.assertEqual(err["code"], "CASE_HAS_LINKED_RESOURCES")

    def test_atomic_rollback_after_service_and_task_written(self):
        draft, consent = self.prepare()
        body, key = self.body(draft, consent), existing.key()
        original = self.execution.create_in_transaction

        def failed(*args, **kwargs):
            original(*args, **kwargs)
            raise sqlite3.OperationalError("injected rollback")

        with patch.object(self.execution, "create_in_transaction", failed):
            self.assertEqual(self.create(body, expected=503, key=key)["code"], "DEPENDENCY_NOT_READY")
        self.assertEqual(self.counts(), (0, 0, 0, 0, 0, 0))
        self.assertEqual(self.d.read(draft)["status"], "preparing")
        self.create(body, key=key)
        self.assertEqual(self.counts(), (1, 1, 1, 0, 0, 0))

    def test_status_legal_terminal_and_dispatch_is_independent(self):
        service = self.create()
        self.transition(service, "completed", expected=409)
        self.transition(service, "in_progress", expected=409)
        self.run_task(service, client=self.s.a, expected=403)
        run_key = existing.key()
        execution = self.run_task(service, revision=1, key=run_key)
        self.assertEqual((execution["execution_status"], execution["delivery_status"], execution["channel"]),
                         ("completed", "submitted", "mock"))
        self.assertEqual(self.run_task(service, revision=1, key=run_key), execution)
        self.run_task(service, expected=409)
        self.assertEqual(self.d.call("GET", self.path(service))["status"], "submitted")
        started = self.transition(service, "in_progress")
        self.transition(service, "failed", expected=409)
        done = self.transition(started, "completed")
        self.assertEqual((done["status"], done["meta"]["revision"]), ("completed", 3))
        self.cancel(done, expected=409)
        self.transition(done, "in_progress", expected=409)
        with self.s.db.connection(readonly=True) as conn:
            self.assertEqual([r[0] for r in conn.execute("SELECT status FROM c_service_history ORDER BY revision")],
                             ["submitted", "in_progress", "completed"])
            notices = conn.execute("SELECT * FROM change_notices WHERE kind='c_service_changed'").fetchall()
            self.assertEqual(len(notices), 3)
        self.assertEqual(self.counts(), (1, 3, 1, 1, 1, 0))

    def test_closed_failure_and_cancelled_tasks_never_dispatch(self):
        first = self.create()
        self.assertEqual(self.transition(first, "failed")["status"], "failed")
        self.run_task(first, expected=409)
        draft = self.d.create()
        consent = self.d.confirm(draft, expected=200)
        second = self.create(self.body(draft, consent))
        key = existing.key()
        cancelled = self.cancel(second, key=key)
        self.assertEqual(self.cancel(second, key=key), cancelled)
        self.assertEqual(cancelled["status"], "cancelled")
        self.run_task(second, expected=409)
        self.assertEqual(self.counts(), (2, 4, 2, 0, 0, 0))

    def test_provider_identity_event_dedupe_late_and_unknown(self):
        service = self.create()
        body = self.receipt_body(service, "in_progress", response_text="虚构接收，未调用机构")
        self.receipt(self.admin, body, expected=503)
        provider = self.receipt_client()
        self.receipt(provider, body, enabled=False, expected=401)
        self.receipt(self.receipt_client("other-mock-provider"), body, expected=404)
        self.assertFalse(self.receipt(provider, dict(body, provider_event_id=existing.key()))["applied"])
        with patch.object(self.adapter, "adapter", return_value={"outcome_unknown": True}) as adapter:
            outcome = self.run_task(service)
            self.assertEqual(outcome["execution_status"], "outcome_unknown")
            self.run_task(service, expected=409)
            adapter.assert_called_once()
        self.s.time[0] += timedelta(seconds=2)
        body["occurred_at"] = stamp(self.s.clock())
        ack = self.receipt(provider, body)
        self.assertTrue(ack["applied"])
        self.assertEqual(self.receipt(provider, body), ack)
        self.assertEqual(self.receipt(provider, dict(body, response_text="different"), expected=409)["code"],
                         "SERVICE_RECEIPT_CONFLICT")
        started = self.d.call("GET", self.path(service))
        self.assertEqual((started["status"], started["provider_response"]["origin"]), ("in_progress", "mock_example"))
        self.assertEqual(self.d.call("GET", "/executions/" + outcome["execution_id"])["execution_status"], "outcome_unknown")
        completion = self.receipt_body(started, "completed", result_summary="模拟记录完成")
        self.assertTrue(self.receipt(provider, completion)["applied"])
        self.assertFalse(self.receipt(provider, self.receipt_body(started, "cancelled"))["applied"])
        self.assertEqual(self.d.call("GET", self.path(service))["status"], "completed")
        self.assertEqual(self.counts(), (1, 3, 1, 1, 1, 4))

    def test_retry_known_definite_failure_keeps_same_task(self):
        service = self.create()
        failure = {"error_code": "SIMULATED_UNAVAILABLE", "error_message": "测试前已知未派发", "retryable": True}
        with patch.object(self.adapter, "adapter", side_effect=[failure, {"delivery_status": "submitted"}]) as adapter:
            result = self.run_task(service)
            self.assertEqual(result["execution_status"], "failed")
            self.run_task(service, expected=409)
            self.s.time[0] += timedelta(seconds=60)
            result = self.run_task(service)
            self.assertEqual((result["attempt"], result["task_id"], result["delivery_status"]),
                             (2, service["dispatch_task_id"], "submitted"))
            self.assertEqual(adapter.call_count, 2)
        self.assertEqual(self.counts(), (1, 1, 1, 2, 1, 0))

    def test_revocation_during_dispatch_no_lock_or_late_application(self):
        draft, consent = self.prepare()
        service = self.create(self.body(draft, consent))
        entered, release = Event(), Event()

        def delayed(task, execution):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("timed out")
            return {"delivery_status": "submitted"}

        with patch.object(self.adapter, "adapter", side_effect=delayed) as adapter, ThreadPoolExecutor(2) as pool:
            worker = pool.submit(self.run_task, service)
            try:
                self.assertTrue(entered.wait(5))
                self.run_task(service, expected=409)
                self.d.revoke(consent)
            finally:
                release.set()
            self.assertEqual(worker.result(timeout=10)["execution_status"], "cancelled")
            adapter.assert_called_once()
        provider = self.receipt_client()
        self.assertFalse(self.receipt(provider, self.receipt_body(service, "in_progress"))["applied"])
        self.assertEqual(self.create(self.body(draft, consent), expected=409)["code"], "SERVICE_CONFIRMATION_REQUIRED")
        self.assertEqual(self.counts(), (1, 1, 1, 1, 0, 1))
