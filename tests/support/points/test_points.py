import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlencode

import fixtures as existing
from medication import test_analytics as analytics

from medplatform.core.documents import stamp
from medplatform.support.points.service import RULES_VERSION, seed_points
from support.peer import test_peer as peer

PA, PB = existing.PA, existing.PB
ACCOUNT = f"/patients/{PA}/points"
LEDGER = f"/patients/{PA}/points-ledger"
REVIEW = f"/patients/{PA}/management-reviews"
RECONCILE = "/internal/points/reconcile"


class PointsTests(unittest.TestCase):
    def setUp(self):
        self.a = analytics.AnalyticsTests()
        self.a.setUp()
        self.addCleanup(self.a.doCleanups)
        self.s = self.a.s
        self.points = self.s.app.state.points
        self.admin = self.s.login("demo-admin")

    def call(self, method, path, body=None, *, client=None, expected=200, key=None):
        return self.s.call(
            client or self.s.a, method, path, body, expected=expected, operation=key
        )

    def body(self, **changes):
        return {
            "patient_id": PA,
            "window_start": "2026-11-16T00:00:00+08:00",
            "window_end": "2026-11-30T00:00:00+08:00",
            "rules_version": RULES_VERSION,
        } | changes

    def reconcile(self, *, body=None, client=None, key=None, expected=200):
        return self.call(
            "POST",
            RECONCILE,
            body or self.body(),
            client=client or self.admin,
            key=key,
            expected=expected,
        )

    def page(self, path=LEDGER, *, client=None, expected=200, **filters):
        body = self.body()
        search = {k: body[k] for k in ("window_start", "window_end")} | filters
        return self.call(
            "GET", path + "?" + urlencode(search), client=client, expected=expected
        )

    def review_body(self, **changes):
        return {
            "client_review_id": existing.key(),
            "week_start": "2026-11-16",
            "reflection": "虚构回顾正文",
            "confirmed_completed": True,
        } | changes

    def init(self):
        return seed_points(self.s.db, self.s.clock)

    def move(self, instant):
        self.s.time[0] = datetime.fromisoformat(instant)
        self.s.a = self.s.login("demo-patient-a")
        self.admin = self.s.login("demo-admin")

    def prepare_manual(self):
        plan = self.a.prepare()
        self.admin = self.s.login("demo-admin")
        self.init()
        return plan

    @staticmethod
    def issues(result):
        return {issue["code"] for issue in result["source_issues"]}

    def test_rules_signed_in_account_not_created_by_reads(self):
        rules = self.call("GET", "/points/rules")
        self.assertEqual(rules["rules_version"], RULES_VERSION)
        self.assertEqual(
            {r["rule_code"]: r["points"] for r in rules["rules"]},
            {
                "daily_record": 2,
                "five_day_block": 5,
                "weekly_review": 3,
                "peer_participation": 2,
            },
        )
        self.assertEqual(
            (rules["week_start_day"], rules["timezone_source"], rules["is_simulated"]),
            (1, "patient", True),
        )
        self.call("PUT", "/auth/current-patient", {"patient_id": PA})
        self.assertEqual(
            self.call("GET", "/rewards", expected=503)["code"],
            "REWARD_CATALOG_UNAVAILABLE",
        )
        self.assertEqual(
            self.call("GET", "/points/rules?rules_version=unknown", expected=404)[
                "code"
            ],
            "POINTS_RULES_NOT_ENABLED",
        )
        before = self.s.db.path.read_bytes()
        self.assertEqual(
            self.call("GET", ACCOUNT, expected=503)["code"], "POINTS_ACCOUNT_NOT_READY"
        )
        self.page(expected=503)
        self.assertEqual(self.s.db.path.read_bytes(), before)
        self.assertEqual((self.init(), self.init()), (3, 0))
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], 0)
        self.assertEqual(self.page(), {"items": [], "next_cursor": None})

    def test_no_sources_protected_actor_delta_and_invalid_configuration(self):
        self.init()
        self.assertEqual(
            self.reconcile(client=self.s.a, expected=403)["code"], "ADMIN_REQUIRED"
        )
        self.assertEqual(
            self.reconcile(body=self.body(delta=800), expected=422)["code"],
            "VALIDATION_ERROR",
        )
        self.assertEqual(
            self.reconcile(body=self.body(rules_version="other"), expected=409)["code"],
            "POINTS_RECONCILE_CONFLICT",
        )
        result = self.reconcile()
        self.assertEqual(
            (
                result["account"]["balance"],
                result["new_entries"],
                result["skipped_keys"],
            ),
            (0, [], []),
        )
        self.assertEqual(
            self.issues(result),
            {"manual_not_collected", "review_not_collected", "peer_not_configured"},
        )

    def test_daily_outcomes_five_day_block_and_device_do_not_change_stats(self):
        self.prepare_manual()
        outcomes = ("taken", "not_taken", "postponed", "unknown", "not_taken")
        events = [
            self.a.report(day * 2, outcome) for day, outcome in enumerate(outcomes)
        ]
        self.a.report(1, "taken")  # second valid time on the first natural day
        self.a.boxes([10])
        before = self.a.refresh()
        result = self.reconcile()
        awarded = result["new_entries"]
        self.assertEqual(
            [(r["rule_code"], r["delta"]) for r in awarded],
            [("daily_record", 2)] * 5 + [("five_day_block", 5)],
        )
        self.assertEqual(
            [s["record_id"] for s in awarded[-1]["source_refs"]],
            [e["event_id"] for e in events],
        )
        self.assertEqual(
            [a["local_date"] for a in result["new_allocations"]],
            [f"2026-11-{day:02d}" for day in range(16, 21)],
        )
        self.assertEqual([e["balance_after"] for e in awarded], [2, 4, 6, 8, 10, 15])
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], 15)
        self.assertEqual(
            self.a.get_result("summary", as_of=before["record_overview"]["as_of"]),
            before,
        )
        self.a.counts(before["record_overview"], [2, 2, 1, 1, 8])
        replay = self.reconcile()
        self.assertEqual(replay["new_entries"], [])
        self.assertEqual(
            set(replay["skipped_keys"]), {r["business_key"] for r in awarded}
        )

    def test_five_day_gaps_adjacent_blocks_replay_and_half_open_window(self):
        self.move("2026-11-16T00:00:00+00:00")
        self.s.confirm(effective_from=stamp(self.s.clock()))
        self.move("2026-11-29T12:00:00+00:00")
        self.init()
        with self.s.db.connection(readonly=True) as conn:
            self.a.slots = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM dose_slots ORDER BY scheduled_at"
                )
            ]
        # 16–19 then a gap, with two full consecutive blocks from Nov 21.
        for day in (0, 1, 2, 3, *range(5, 15)):
            if day < 14:
                self.a.report(day * 2, "unknown")
        self.move("2026-11-30T12:00:00+00:00")
        self.a.report(28, "not_taken")
        with self.s.db.connection(readonly=True) as conn:
            slots = [
                dict(r)
                for r in conn.execute("SELECT * FROM dose_slots ORDER BY scheduled_at")
            ]
        first = slots[10]["scheduled_at"]
        self.assertEqual(
            self.reconcile(body=self.body(window_end=first))["account"]["balance"], 8
        )
        result = self.reconcile(
            body=self.body(window_start=first, window_end=stamp(self.s.clock()))
        )
        self.assertEqual(
            [
                entry["business_key"].rsplit(":", 1)[1]
                for entry in result["new_entries"]
                if entry["rule_code"] == "five_day_block"
            ],
            ["2026-11-21", "2026-11-26"],
        )
        self.assertEqual(len(result["new_allocations"]), 10)
        self.assertEqual(len({a["local_date"] for a in result["new_allocations"]}), 10)
        self.assertEqual(result["account"]["balance"], 38)

    def test_unmatched_reports_and_family_authorization_revocation_before_and_after_award(
        self,
    ):
        self.prepare_manual()
        binding, grant = self.s.bind(["records:report"])
        self.a.report(0, "not_taken", self.s.f)
        self.call(
            "POST",
            f"/patients/{PA}/medication-events",
            {
                "source_event_id": existing.key(),
                "occurred_at": stamp(self.s.clock()),
                "reported_status": "unknown",
            },
            expected=201,
        )
        self.call(
            "POST",
            f"/grants/{grant['grant_id']}/revoke",
            {
                "expected_revision": grant["meta"]["revision"],
                "reason": "虚构核奖前撤权",
            },
        )
        result = self.reconcile()
        self.assertEqual(result["new_entries"], [])
        self.assertIn("manual_actor_restricted", self.issues(result))
        self.assertIn("manual_unmatched", self.issues(result))
        grant = self.call(
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": 2,
                "scopes": ["records:report"],
                "confirmed": True,
                "valid_until": None,
            },
        )
        self.a.report(2, "unknown", self.s.f)
        awarded = self.reconcile()
        self.assertEqual(awarded["account"]["balance"], 4)
        self.call(
            "POST",
            f"/grants/{grant['grant_id']}/revoke",
            {
                "expected_revision": grant["meta"]["revision"],
                "reason": "虚构核奖后撤权",
            },
        )
        after = self.reconcile()
        self.assertEqual((after["new_entries"], after["account"]["balance"]), ([], 4))
        self.assertIn("source_changed", self.issues(after))

    def test_source_withdrawal_retains_original_award_and_revision_audit(self):
        self.prepare_manual()
        event = self.a.report(0, "unknown")
        initial = self.reconcile()
        self.s.time[0] += timedelta(microseconds=1)
        self.call(
            "POST",
            f"/events/{event['event_id']}/withdrawals",
            {"expected_revision": 1, "reason": "虚构来源撤回并保留历史"},
        )
        rerun = self.reconcile()
        self.assertEqual(rerun["account"]["balance"], 2)
        self.assertEqual(rerun["new_entries"], [])
        self.assertTrue({"manual_withdrawn", "source_changed"} <= self.issues(rerun))
        self.assertEqual(self.page()["items"], initial["new_entries"])
        with self.s.db.connection(readonly=True) as conn:
            changes = json.loads(
                conn.execute(
                    "SELECT source_changes_json FROM c_points_reconciliations ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
        self.assertEqual(
            changes,
            [
                {
                    "ledger_id": initial["new_entries"][0]["ledger_id"],
                    "source_order": 1,
                    "awarded_revision": 1,
                    "current_revision": 2,
                    "reason": "manual_withdrawn",
                }
            ],
        )

    def test_week_review_local_boundary_false_claim_separate_source_and_independent_receipt(
        self,
    ):
        self.init()
        self.move("2026-11-22T15:59:59.999999+00:00")
        first, key = self.review_body(), existing.key()
        for unconfirmed in (False, 1, "true"):
            self.call(
                "POST",
                REVIEW,
                first | {"confirmed_completed": unconfirmed},
                expected=422,
            )
        self.call("POST", REVIEW, first | {"week_start": "2026-11-23"}, expected=409)
        saved = self.call("POST", REVIEW, first, expected=201, key=key)
        self.assertEqual(self.call("POST", REVIEW, first, expected=201, key=key), saved)
        self.assertEqual(self.call("POST", REVIEW, first, expected=201), saved)
        self.assertEqual(self.call("GET", ACCOUNT)["balance"], 0)
        self.move("2026-11-22T16:00:00+00:00")
        self.call("POST", REVIEW, self.review_body(), expected=409)
        second = self.call(
            "POST", REVIEW, self.review_body(week_start="2026-11-23"), expected=201
        )
        self.s.time[0] += timedelta(microseconds=1)
        self.call(
            "POST", REVIEW, self.review_body(week_start="2026-11-23"), expected=409
        )
        before = self.reconcile(body=self.body(window_end="2026-11-22T16:00:00Z"))
        at = self.reconcile(body=self.body(window_start="2026-11-22T16:00:00Z"))
        self.assertEqual(
            [
                (r["delta"], r["source_refs"][0]["record_id"])
                for r in before["new_entries"]
            ],
            [(3, saved["review_id"])],
        )
        self.assertEqual(
            [(r["delta"], r["source_refs"][0]["record_id"]) for r in at["new_entries"]],
            [(3, second["review_id"])],
        )
        self.assertEqual(at["account"]["balance"], 6)

    def test_same_key_concurrent_distinct_keys_result_recovery_and_immutability(self):
        self.init()
        self.call("POST", REVIEW, self.review_body(), expected=201)
        admin_2 = self.s.login("demo-admin")
        first_key, second_key = existing.key(), existing.key()
        start = Barrier(2)

        def attempt(client, key):
            start.wait(timeout=8)
            return self.reconcile(client=client, key=key)

        with ThreadPoolExecutor(max_workers=2) as executor:
            requests = [
                executor.submit(attempt, client, key)
                for client, key in ((self.admin, first_key), (admin_2, second_key))
            ]
            results = [result.result(timeout=20) for result in requests]
        self.assertEqual(sorted(len(r["new_entries"]) for r in results), [0, 1])
        self.assertEqual(self.reconcile(key=first_key), results[0])
        self.assertEqual(self.reconcile(key=second_key), results[1])
        self.assertEqual(
            self.reconcile(
                key=first_key,
                body=self.body(window_end="2026-11-29T00:00:00+08:00"),
                expected=409,
            )["code"],
            "IDEMPOTENCY_CONFLICT",
        )
        fresh = self.s.login("demo-patient-a")
        self.assertEqual(self.call("GET", ACCOUNT, client=fresh)["balance"], 3)
        with self.s.db.transaction() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*),SUM(delta) FROM c_points_ledger"
                ).fetchone()[:],
                (1, 3),
            )
            for sql in (
                "UPDATE c_points_ledger SET delta=7",
                "DELETE FROM c_points_ledger",
                "DELETE FROM c_points_award_sources",
                "UPDATE c_management_reviews SET reflection='changed'",
                "DELETE FROM c_points_reconciliations",
            ):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    conn.execute(sql)
            with self.assertRaisesRegex(sqlite3.IntegrityError, "UNIQUE"):
                conn.execute("""INSERT INTO c_points_ledger
                                (ledger_id,points_account_id,patient_id,operation_id,entry_kind,delta,balance_after,
                                 business_key,rule_code,period_start,rules_version,created_at)
                                SELECT 'duplicate',points_account_id,patient_id,
                                operation_id,entry_kind,delta,6,business_key,rule_code,period_start,rules_version,created_at
                                FROM c_points_ledger""")

    def test_write_failure_rollback_after_first_insertion_and_same_key_retry(self):
        self.prepare_manual()
        self.a.report(0)
        self.a.report(2)
        award = self.points.award
        count = 0

        def fail_later(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise sqlite3.DatabaseError("synthetic write interrupted")
            return award(*args)

        key = existing.key()
        with patch.object(self.points, "award", side_effect=fail_later):
            self.reconcile(key=key, expected=503)
        self.assertEqual(
            (self.call("GET", ACCOUNT)["balance"], self.page()["items"]), (0, [])
        )
        with self.s.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM c_points_reconciliations"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM c_points_award_sources").fetchone()[
                    0
                ],
                0,
            )
        self.assertEqual(self.reconcile(key=key)["account"]["balance"], 4)

    def test_grant_minimal_source_projection_and_cursor_revocation_or_isolation(self):
        self.prepare_manual()
        self.a.report(0)
        self.a.report(2)
        self.reconcile()
        first = self.page(limit=1)
        cursor = first["next_cursor"]
        self.assertEqual(len(self.page(limit=1, cursor=cursor)["items"]), 1)
        self.page(
            limit=1, cursor=cursor, window_end="2026-11-29T00:00:00+08:00", expected=422
        )
        self.call("GET", ACCOUNT, client=self.s.b, expected=404)
        self.assertEqual(
            self.call("GET", f"/patients/{PB}/points", client=self.s.b)["balance"], 0
        )
        binding, grant = self.s.bind(["services:read", "feedback:read"])
        self.call("GET", ACCOUNT, client=self.s.f, expected=403)
        self.call("POST", REVIEW, self.review_body(), client=self.s.f, expected=403)
        grant = self.call(
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": 1,
                "scopes": ["points:read"],
                "confirmed": True,
                "valid_until": None,
            },
        )
        family = self.page(limit=1, client=self.s.f)
        self.assertEqual(
            (
                self.call("GET", ACCOUNT, client=self.s.f)["balance"],
                family["items"][0]["source_refs"],
            ),
            (4, []),
        )
        self.page(limit=1, cursor=cursor, client=self.s.f, expected=422)
        self.page(path=REVIEW, client=self.s.f, expected=403)
        self.call(
            "POST",
            f"/grants/{grant['grant_id']}/revoke",
            {
                "expected_revision": grant["meta"]["revision"],
                "reason": "虚构撤销积分读取",
            },
        )
        self.page(limit=1, client=self.s.f, cursor=family["next_cursor"], expected=403)


class PeerPointsTests(unittest.TestCase):
    def setUp(self):
        self.p = peer.PeerTests()
        self.p.setUp()
        self.addCleanup(self.p.doCleanups)
        self.s = self.p.s
        seed_points(self.s.db, self.s.clock)
        self.window = {
            "patient_id": PA,
            "window_start": "2026-11-16T00:00:00+08:00",
            "window_end": "2026-11-23T00:00:00+08:00",
            "rules_version": RULES_VERSION,
        }

    def reconcile(self):
        return self.p.d.call("POST", RECONCILE, self.window, self.p.f.admin)

    def test_only_current_visible_actual_participation_and_no_post_id_after_share_revocation(
        self,
    ):
        draft, consent = self.p.prepare()
        member = self.p.join(self.p.f.body(draft, consent))
        self.p.activate(member, complete=True)
        post = self.p.post()
        pending = self.reconcile()
        self.assertEqual(pending["account"]["balance"], 0)
        self.assertIn("peer_pending", PointsTests.issues(pending))
        visible = self.p.review(post)
        self.p.review(self.p.post())
        award = self.reconcile()
        self.assertEqual(
            [(x["rule_code"], x["delta"]) for x in award["new_entries"]],
            [("peer_participation", 2)],
        )
        self.assertEqual(len(award["new_entries"][0]["source_refs"]), 1)
        repeated = self.reconcile()
        self.assertEqual(repeated["new_entries"], [])
        self.assertEqual(len(repeated["skipped_keys"]), 1)
        self.p.review(visible, "hidden")
        self.p.d.revoke(consent)
        revoked = self.reconcile()
        self.assertEqual(
            (revoked["new_entries"], revoked["account"]["balance"]), ([], 2)
        )
        search = {k: self.window[k] for k in ("window_start", "window_end")}
        history = self.p.d.call("GET", LEDGER + "?" + urlencode(search))
        self.assertEqual(history["items"][0]["source_refs"], [])
        self.assertEqual(
            self.p.d.call("GET", f"/patients/{PB}/points", client=self.s.b)["balance"],
            0,
        )
