import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import fixtures as existing
from medplatform.core.documents import stamp
from medplatform.support.rewards.catalog import (
    RESOURCE,
    RESOURCE_VERSION,
    REWARD_VERSION,
    RewardFixture,
    install_rewards,
    seed_rewards,
)
from pydantic import SecretStr

from support.points import test_points as points

PA, PB, ACCOUNT = points.PA, points.PB, points.ACCOUNT
PATH = f"/patients/{PA}/redemptions"
RECEIPT = "/api/v1/integrations/fulfillment-receipts"
TOKEN = "local-test-receipt-fixture-" + "x" * 32


class RewardTests(unittest.TestCase):
    def setUp(self):
        self.p = points.PointsTests()
        self.p.setUp()
        self.addCleanup(self.p.doCleanups)
        self.s = self.p.s
        self.rewards = self.s.app.state.rewards
        self.rewards.fulfillment.settings.DEMO_FULFILLMENT_RECEIPT_SUBJECT = (
            "demo-rewards"
        )
        self.rewards.fulfillment.settings.DEMO_FULFILLMENT_RECEIPT_TOKEN = SecretStr(
            TOKEN
        )
        self.p.init()
        self.assertEqual(seed_rewards(self.s.db, self.s.clock), 5)

    def call(self, *args, **kwargs):
        return self.p.call(*args, **kwargs)

    def funds(self, indices=range(29)):
        self.p.move("2026-11-16T00:00:00+00:00")
        self.s.confirm(effective_from=stamp(self.s.clock()))
        self.p.move("2026-12-15T08:00:00+00:00")
        self.s.f = self.s.login("demo-family")
        with self.s.db.connection(readonly=True) as conn:
            self.p.a.slots = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM dose_slots ORDER BY scheduled_at"
                )
            ]
        for i in indices:
            self.p.a.report(i * 2, "not_taken")
        return self.p.reconcile(
            body=self.p.body(window_end="2026-12-16T00:00:00+08:00")
        )["account"]

    def order_body(self, name="reminder", revision=None, **extra):
        if revision is None:
            revision = self.call("GET", ACCOUNT)["meta"]["revision"]
        return {
            "reward_id": f"reward-{name}-demo",
            "reward_version": REWARD_VERSION,
            "expected_account_revision": revision,
            "confirmed": True,
        } | extra

    def redeem(self, body=None, **kwargs):
        return self.call(
            "POST", PATH, body or self.order_body(), **({"expected": 201} | kwargs)
        )

    def detail(self, order, fulfillment=False, **kwargs):
        path = "/redemptions/" + order["redemption_id"]
        return self.call(
            "GET", path + ("/fulfillment" if fulfillment else ""), **kwargs
        )

    def delivery_body(self, order, target="failed", **extra):
        return {
            "provider_event_id": existing.key(),
            "fulfillment_id": order["fulfillment_id"],
            "status": target,
            "occurred_at": stamp(self.s.clock()),
            "result_ref": None,
            "failure_reason": "虚构独立模拟交付结果"
            if target in {"failed", "cancelled", "outcome_unknown"}
            else None,
        } | extra

    def receipt(self, body, key=None, expected=200, token=TOKEN, client=None):
        response = (client or self.p.admin).post(
            RECEIPT,
            json=body,
            headers={
                "Authorization": "Bearer " + token,
                "Idempotency-Key": key or existing.key(),
            },
        )
        self.assertEqual(response.status_code, expected, response.text)
        self.assertEqual(
            set(response.json()), {"request_id", "status", "data", "error"}
        )
        return response.json()["data" if expected < 400 else "error"]

    def run_task(self, task_id, **kwargs):
        task = self.call("GET", f"/tasks/{task_id}", client=self.p.admin)
        return self.call(
            "POST",
            f"/tasks/{task_id}/run",
            {"expected_revision": task["meta"]["revision"]},
            client=self.p.admin,
            **kwargs,
        )

    def parallel(self, *actions):
        gate = Barrier(len(actions))

        def invoke(function):
            gate.wait(timeout=10)
            return function()

        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            return [
                f.result(timeout=30)
                for f in [pool.submit(invoke, action) for action in actions]
            ]

    def raw_redeem(self, client, body):
        result = client.post(
            "/api/v1" + PATH,
            json=body,
            headers={
                "Origin": existing.BASE,
                "X-CSRF-Token": client.csrf,
                "Idempotency-Key": existing.key(),
            },
        )
        return result.status_code, result.json()

    def test_directory_exact_costs_seed_conflict_and_stale_version(self):
        self.assertEqual(seed_rewards(self.s.db, self.s.clock), 0)
        self.call("PUT", "/auth/current-patient", {"patient_id": PA})
        catalog = self.call("GET", "/rewards")
        self.assertEqual(
            {item["reward_id"]: item["points_cost"] for item in catalog["items"]},
            {
                f"reward-{n}-demo": c
                for n, c in zip(
                    ("reminder", "card", "routine", "companion", "toolkit"),
                    (30, 40, 50, 60, 80),
                )
            },
        )
        self.assertTrue(
            all(
                item["is_simulated"] and not item["is_essential"]
                for item in catalog["items"]
            )
        )
        self.assertEqual(
            [
                item["resource_id"]
                for item in self.call("GET", "/support-resources?channel=rewards")[
                    "items"
                ]
            ],
            [RESOURCE],
        )
        self.assertNotIn(
            RESOURCE,
            {
                item["resource_id"]
                for item in self.call("GET", "/support-resources")["items"]
            },
        )
        old = self.call("GET", "/rewards/reward-card-demo")
        change = dict(old, reward_version="reward-demo-v2", availability="unavailable")
        with self.s.db.transaction() as conn:
            fixture = RewardFixture.model_validate(
                {
                    "reward": change,
                    "previous_version": REWARD_VERSION,
                    "template_text": "虚构",
                }
            )
            self.assertEqual(install_rewards(conn, [fixture], stamp(self.s.clock())), 1)
            with self.assertRaisesRegex(Exception, "REWARD_VERSION_CONFLICT"):
                install_rewards(
                    conn,
                    [fixture.model_copy(update={"template_text": "同版本异内容"})],
                    stamp(self.s.clock()),
                )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM c_reward_versions WHERE reward_id=?",
                    (old["reward_id"],),
                ).fetchone()[0],
                2,
            )
        self.assertEqual(
            self.call("GET", "/rewards/reward-card-demo")["availability"], "unavailable"
        )
        self.assertEqual(
            self.redeem(self.order_body("card"), expected=409)["code"],
            "REWARD_VERSION_CONFLICT",
        )

    def test_exact_cost_idempotent_history_feedback_and_completed_never_refunds(self):
        initial = self.funds(range(0, 29, 2))
        self.assertEqual(initial["balance"], 30)
        body, key = self.order_body(), existing.key()
        order = self.redeem(body, key=key)
        self.assertEqual(self.redeem(body, key=key), order)
        self.assertEqual(self.redeem(body), order)
        self.assertEqual(
            self.redeem(
                body | {"reward_id": "reward-card-demo"}, key=key, expected=409
            )["code"],
            "IDEMPOTENCY_CONFLICT",
        )
        self.assertEqual(self.redeem(expected=409)["code"], "INSUFFICIENT_POINTS")
        task = self.detail(order, True)["task_id"]
        self.assertEqual(self.detail(order, True)["status"], "pending")
        self.assertEqual(self.run_task(task)["execution_status"], "completed")
        self.run_task(task, expected=409)
        final = self.detail(order, True)
        self.assertEqual(
            (final["status"], final["artifact"]["media_type"]),
            ("completed", "text/plain"),
        )
        self.assertEqual(final["artifact"]["source_refs"][0]["version"], REWARD_VERSION)
        self.assertFalse(self.receipt(self.delivery_body(order))["applied"])
        self.receipt(
            self.delivery_body(order, "completed", result_ref="wrong-original-result"),
            expected=409,
        )
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], 0)
        fresh = self.s.login("demo-patient-a")
        self.assertEqual(self.detail(order, client=fresh)["points_status"], "debited")
        feedback = {
            "client_feedback_id": existing.key(),
            "participation": "provided",
            "experience": "虚构体验",
        }
        route = "/redemptions/" + order["redemption_id"] + "/feedback"
        self.assertEqual(
            self.call("POST", route, feedback, expected=201),
            self.call("POST", route, feedback, expected=201),
        )
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], 0)

    def test_unknown_late_and_explicit_no_delivery_refund_exactly_once(self):
        self.funds()
        order = self.redeem()
        initial = self.call("GET", ACCOUNT)["balance"]
        task = self.detail(order, True)["task_id"]
        with patch.object(
            self.rewards.fulfillment, "attempt", side_effect=TimeoutError
        ):
            execution = self.run_task(task)
        self.assertEqual(execution["execution_status"], "outcome_unknown")
        self.assertEqual(self.detail(order, True)["status"], "outcome_unknown")
        self.assertEqual(self.detail(order)["points_status"], "debited")
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], initial)
        self.run_task(task, expected=409)
        replay = self.delivery_body(
            order,
            "failed",
            occurred_at=stamp(self.s.clock() - timedelta(microseconds=1)),
        )
        self.assertFalse(self.receipt(replay)["applied"])
        body, key = self.delivery_body(order), existing.key()
        result = self.receipt(body, key)
        self.assertTrue(result["applied"])
        self.assertEqual(self.receipt(body, key), result)
        self.assertEqual(self.receipt(body), result)
        self.receipt(body | {"failure_reason": "同一来源异内容"}, key, expected=409)
        self.receipt(body | {"failure_reason": "同一来源异内容"}, expected=409)
        self.assertFalse(
            self.receipt(
                self.delivery_body(order, "completed", result_ref="late-result")
            )["applied"]
        )
        current = self.detail(order)
        self.assertEqual(
            (current["status"], current["points_status"]), ("failed", "refunded")
        )
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], initial + 30)
        with self.s.db.transaction() as conn:
            rows = conn.execute(
                "SELECT entry_kind,delta,reverses_ledger_id FROM c_points_ledger WHERE redemption_id=? ORDER BY rowid",
                (order["redemption_id"],),
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in rows],
                [
                    ("redemption_debit", -30, None),
                    ("redemption_refund", 30, order["debit_ledger_id"]),
                ],
            )
            for command in (
                "UPDATE c_points_ledger SET delta=0",
                "DELETE FROM c_points_ledger",
                "DELETE FROM c_redemption_history",
            ):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    conn.execute(command)
            with self.assertRaisesRegex(sqlite3.IntegrityError, "UNIQUE"):
                conn.execute(
                    """INSERT OR REPLACE INTO c_points_ledger
                    SELECT ledger_id,points_account_id,patient_id,operation_id,entry_kind,delta,
                           (SELECT SUM(v.delta) FROM c_points_ledger v WHERE v.patient_id=d.patient_id)+delta,
                           business_key,rule_code,period_start,rules_version,created_at,redemption_id,reverses_ledger_id
                    FROM c_points_ledger d WHERE ledger_id=?""",
                    (order["debit_ledger_id"],),
                )

    def test_debit_and_refund_fault_rollback_and_original_request_retry(self):
        initial = self.funds()["balance"]
        body, key = self.order_body(), existing.key()
        with patch.object(
            self.s.app.state.execution,
            "create_in_transaction",
            side_effect=sqlite3.OperationalError,
        ):
            self.redeem(body, key=key, expected=503)
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], initial)
        self.assertEqual(self.call("GET", PATH)["items"], [])
        order = self.redeem(body, key=key)
        failure, key = self.delivery_body(order), existing.key()
        with patch.object(self.rewards, "ledger", side_effect=sqlite3.OperationalError):
            self.receipt(failure, key, expected=503)
        self.assertEqual(self.detail(order, True)["status"], "pending")
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], initial - 30)
        self.assertTrue(self.receipt(failure, key)["applied"])
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], initial)

    def test_expected_revision_race_and_balance_competition(self):
        self.funds(range(0, 29, 2))
        other_tab = self.s.login("demo-patient-a")
        body = self.order_body()
        same = self.parallel(
            lambda: self.raw_redeem(self.s.a, body),
            lambda: self.raw_redeem(other_tab, body),
        )
        self.assertEqual([r[0] for r in same], [201, 201])
        self.assertEqual(
            same[0][1]["data"]["redemption_id"], same[1][1]["data"]["redemption_id"]
        )
        self.assertEqual(len(self.call("GET", PATH)["items"]), 1)
        failure = self.delivery_body(same[0][1]["data"])
        self.receipt(failure)
        one, two = self.order_body(), self.order_body("card")
        results = self.parallel(
            lambda: self.raw_redeem(self.s.a, one),
            lambda: self.raw_redeem(other_tab, two),
        )
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], 0)

    def test_refund_and_new_order_concurrent_keeps_single_balance(self):
        initial = self.funds()["balance"]
        order = self.redeem()
        body = self.order_body("card")
        outcome, result = self.parallel(
            lambda: self.receipt(self.delivery_body(order)),
            lambda: self.raw_redeem(self.s.a, body),
        )
        self.assertTrue(outcome["applied"])
        self.assertIn(result[0], {201, 409})
        self.assertEqual(
            self.call("GET", ACCOUNT)["balance"],
            initial - (40 if result[0] == 201 else 0),
        )

    def test_c25_and_redemption_concurrent_share_authoritative_account(self):
        initial = self.funds()["balance"]
        self.call(
            "POST",
            f"/patients/{PA}/management-reviews",
            self.p.review_body(week_start="2026-12-14"),
            expected=201,
        )
        body = self.order_body()
        award, result = self.parallel(
            lambda: self.p.reconcile(
                body=self.p.body(
                    window_start="2026-12-14T00:00:00+08:00",
                    window_end="2026-12-16T00:00:00+08:00",
                )
            ),
            lambda: self.raw_redeem(self.s.a, body),
        )
        self.assertEqual([r["delta"] for r in award["new_entries"]], [3])
        self.assertIn(result[0], {201, 409})
        self.assertEqual(
            self.call("GET", ACCOUNT)["balance"],
            initial + 3 - (30 if result[0] == 201 else 0),
        )

    def test_family_projection_cursor_revocation_and_provider_independence(self):
        self.funds()
        first = self.redeem()
        self.redeem(self.order_body("card"))
        owner = self.call("GET", PATH + "?limit=1")
        self.detail(first, client=self.s.login("demo-patient-b"), expected=404)
        self.detail(first, client=self.p.admin, expected=404)
        self.receipt(self.delivery_body(first), token="invalid", expected=401)
        self.receipt(
            self.delivery_body(first, fulfillment_id="different-id"), expected=404
        )
        self.run_task(self.detail(first, True)["task_id"])
        binding, grant = self.s.bind(["services:read"])
        self.detail(first, client=self.s.f, expected=403)
        grant = self.call(
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": grant["meta"]["revision"],
                "confirmed": True,
                "scopes": ["points:read"],
                "valid_until": None,
            },
        )
        self.redeem(client=self.s.f, expected=403)
        family = self.call("GET", PATH + "?limit=1", client=self.s.f)
        self.assertIsNone(self.detail(first, True, client=self.s.f)["artifact"])
        self.call(
            "GET",
            PATH + "?cursor=" + owner["next_cursor"],
            client=self.s.f,
            expected=422,
        )
        self.call(
            "POST",
            f"/grants/{grant['grant_id']}/revoke",
            {"expected_revision": grant["meta"]["revision"], "reason": "虚构撤权"},
        )
        self.call(
            "GET",
            PATH + "?cursor=" + family["next_cursor"],
            client=self.s.f,
            expected=403,
        )

    def test_personnel_uses_one_c_service_and_only_original_dispatch_completes(self):
        self.funds()
        draft = self.call(
            "POST",
            f"/patients/{PA}/service-drafts",
            {
                "resource_id": RESOURCE,
                "resource_version": RESOURCE_VERSION,
                "request_text": "仅用于虚构陪伴验收",
            },
            expected=201,
        )
        consent = self.call(
            "POST",
            f"/patients/{PA}/service-confirmations",
            {
                "service_draft_id": draft["service_draft_id"],
                "draft_revision": draft["draft_revision"],
                "shared_categories": ["support_question"],
                "confirmed": True,
            },
            expected=201,
        )
        refs = {
            "service_draft_id": draft["service_draft_id"],
            "draft_revision": draft["draft_revision"],
            "confirmation_ref_id": consent["confirmation_ref_id"],
            "sharing_scope_ref_id": consent["sharing_scope"]["sharing_scope_ref_id"],
        }
        self.call("POST", f"/patients/{PA}/services", refs, expected=409)
        self.redeem(self.order_body("companion"), expected=409)
        order = self.redeem(self.order_body("companion", **refs))
        service = self.call("GET", "/services/" + order["service_id"])
        self.assertEqual(service["redemption_id"], order["redemption_id"])
        self.run_task(self.detail(order, True)["task_id"])
        self.assertEqual(self.detail(order, True)["status"], "in_progress")
        self.assertEqual(
            self.call("GET", "/services/" + service["service_id"])["status"],
            "submitted",
        )
        self.run_task(service["dispatch_task_id"])
        for revision, target in [(1, "in_progress"), (2, "completed")]:
            self.call(
                "POST",
                f"/demo/services/{service['service_id']}/transitions",
                {
                    "expected_revision": revision,
                    "target_status": target,
                    "reason": "模拟正式服务确认",
                },
                client=self.p.admin,
            )
        self.assertEqual(self.detail(order, True)["status"], "completed")
        with self.s.db.connection(readonly=True) as conn:
            for table, count in {
                "c_services": 1,
                "c_service_dispatches": 1,
                "c_redemptions": 1,
            }.items():
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], count
                )
