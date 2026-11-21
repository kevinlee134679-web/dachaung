import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import fixtures as existing
from medplatform.core.documents import stamp
from medplatform.identity.sharing import seed_support_recipients
from medplatform.support.catalog.service import seed_catalog

PA, PB = existing.PA, existing.PB
CREATE = f"/patients/{PA}/service-drafts"
CONFIRM = f"/patients/{PA}/service-confirmations"
RESOURCE = {
    "resource_id": "resource-pharmacist-demo",
    "resource_version": "resource-demo-v2",
}
NEEDED = ["support_question"]
OPTIONAL = ["medication_plan", *NEEDED]
FAMILY_SCOPES = ["services:prepare", "support:read"]


class DraftConsentTests(unittest.TestCase):
    def setUp(self):
        self.s = existing.IdentityFixture()
        self.s.setUp()
        self.addCleanup(self.s.doCleanups)
        seed_catalog(self.s.db)
        self.assertEqual(seed_support_recipients(self.s.db), 5)
        self.service = self.s.app.state.drafts

    def call(self, method, path, body=None, client=None, expected=200, key=None):
        return self.s.call(
            client or self.s.a, method, path, body, expected=expected, operation=key
        )

    def create(self, client=None, text="虚构服务需求", key=None):
        return self.call(
            "POST", CREATE, dict(RESOURCE, request_text=text), client, 201, key
        )

    def read(self, draft, client=None, expected=200):
        return self.call(
            "GET", self.draft_path(draft), client=client, expected=expected
        )

    @staticmethod
    def draft_path(draft):
        return "/service-drafts/" + draft["service_draft_id"]

    @staticmethod
    def confirm_body(draft, categories=NEEDED, hint=None):
        return {
            "service_draft_id": draft["service_draft_id"],
            "draft_revision": draft["draft_revision"],
            "shared_categories": categories,
            "confirmed": True,
            "existing_confirmation_ref_id": hint,
        }

    def confirm(
        self,
        draft,
        categories=NEEDED,
        *,
        hint=None,
        client=None,
        expected=201,
        key=None,
    ):
        return self.call(
            "POST",
            CONFIRM,
            self.confirm_body(draft, categories, hint),
            client,
            expected,
            key,
        )

    @staticmethod
    def consent_path(value):
        return "/service-confirmations/" + value["confirmation_ref_id"]

    def revoke(self, value, client=None, expected=200, key=None):
        return self.call(
            "POST",
            self.consent_path(value) + "/revoke",
            {
                "expected_revision": value["meta"]["revision"],
                "reason": "撤销虚构演示授权",
            },
            client,
            expected,
            key,
        )

    def counts(self):
        with self.s.db.connection(readonly=True) as conn:
            return tuple(
                conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in (
                    "o_sharing_scopes",
                    "o_sharing_scope_history",
                    "c_service_confirmations",
                    "c_draft_confirmations",
                    "c_confirmation_revocations",
                    "idempotency_receipts",
                )
            )

    def revise_grant(self, binding, revision, scopes=FAMILY_SCOPES, valid_until=None):
        return self.call(
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": revision,
                "scopes": scopes,
                "valid_until": valid_until,
                "confirmed": True,
            },
        )

    def concurrent(self, first, second):
        barrier = Barrier(2)

        def send(call):
            client, path, body, key = call
            barrier.wait(timeout=10)
            return client.post(
                existing.BASE + "/api/v1" + path,
                json=body,
                headers={
                    "Origin": existing.BASE,
                    "X-CSRF-Token": client.csrf,
                    "Idempotency-Key": key,
                },
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(send, job) for job in (first, second)]
            return [future.result(timeout=20) for future in results]

    def test_draft_shape_replay_and_immutable_history(self):
        key = existing.key()
        draft = self.create(key=key)
        self.assertEqual(self.create(key=key), draft)
        self.assertEqual(
            set(draft),
            {
                "service_draft_id",
                "patient_id",
                "draft_revision",
                "resource_id",
                "resource_version",
                "request_text",
                "peer_group_id",
                "source_suggestion_id",
                "status",
                "confirmation_ref_id",
                "sharing_scope_ref_id",
                "service_id",
                "meta",
            },
        )
        self.assertEqual(
            (draft["status"], draft["draft_revision"], draft["meta"]["revision"]),
            ("preparing", 1, 1),
        )
        self.assertTrue(
            all(
                draft[k] is None
                for k in (
                    "peer_group_id",
                    "source_suggestion_id",
                    "service_id",
                    "confirmation_ref_id",
                    "sharing_scope_ref_id",
                )
            )
        )
        conflict = self.call(
            "POST", CREATE, dict(RESOURCE, request_text="不同"), expected=409, key=key
        )
        self.assertEqual(conflict["code"], "IDEMPOTENCY_CONFLICT")
        edit = {
            "expected_revision": 1,
            "content": dict(RESOURCE, request_text="修改后的虚构问题"),
        }
        edit_key = existing.key()
        updated = self.call("PUT", self.draft_path(draft), edit, key=edit_key)
        self.assertEqual(
            self.call("PUT", self.draft_path(draft), edit, key=edit_key), updated
        )
        self.assertEqual(
            self.call("PUT", self.draft_path(draft), edit, expected=409)["code"],
            "SERVICE_DRAFT_REVISION_CONFLICT",
        )
        self.confirm(draft, expected=409)
        self.assertEqual(self.read(draft)["draft_revision"], 2)
        with self.s.db.connection(readonly=True) as conn:
            data = conn.execute(
                "SELECT draft_revision, request_text FROM c_service_draft_revisions ORDER BY draft_revision"
            )
            self.assertEqual(
                [tuple(row) for row in data],
                [(1, "虚构服务需求"), (2, "修改后的虚构问题")],
            )
        with self.assertRaises(sqlite3.IntegrityError), self.s.db.transaction() as conn:
            conn.execute("UPDATE c_service_draft_revisions SET request_text='changed'")

    def test_family_prepare_and_read_require_effective_source_access(self):
        binding, grant = self.s.bind(["services:prepare"])
        self.call("POST", CREATE, dict(RESOURCE, request_text="虚构"), self.s.f, 403)
        grant = self.revise_grant(binding, grant["meta"]["revision"])
        draft = self.create(self.s.f)
        self.assertEqual(self.read(draft, self.s.f), draft)
        edit = {
            "expected_revision": 1,
            "content": dict(RESOURCE, request_text="家属代录修订"),
        }
        updated = self.call("PUT", self.draft_path(draft), edit, self.s.f)
        self.assertEqual(updated["request_text"], "家属代录修订")
        self.confirm(updated, client=self.s.f, expected=403)
        self.confirm(updated)
        self.assertIsNone(self.read(draft, self.s.f)["confirmation_ref_id"])
        path = f"/grants/{grant['grant_id']}/revoke"
        self.call(
            "POST",
            path,
            {"expected_revision": grant["meta"]["revision"], "reason": "撤销协助"},
        )
        self.read(draft, self.s.f, 403)
        self.assertEqual(self.read(draft)["request_text"], "家属代录修订")

    def test_historic_resource_read_and_stale_or_forged_source_denied(self):
        self.call(
            "POST",
            CREATE,
            dict(
                RESOURCE,
                request_text="历史不可新建",
                resource_version="resource-demo-v1",
            ),
            expected=422,
        )
        for k in ("source_suggestion_id", "peer_group_id", "patient_id"):
            self.call(
                "POST",
                CREATE,
                dict(RESOURCE, request_text="伪造引用", **{k: "forged"}),
                expected=422,
            )
        draft = self.create()
        with self.s.db.transaction() as conn:
            conn.execute(
                "UPDATE c_support_resources SET current_version='resource-demo-v1' WHERE resource_id=?",
                (RESOURCE["resource_id"],),
            )
        self.assertEqual(self.read(draft)["resource_version"], "resource-demo-v2")
        self.confirm(draft, expected=409)

    def test_recipient_and_sharing_categories_fail_closed(self):
        draft = self.create()
        for categories, expected in [
            ([], 409),
            (["medication_plan"], 409),
            (["support_question", "profile_summary"], 409),
            (["external_blob"], 422),
        ]:
            self.confirm(draft, categories, expected=expected)
        self.call(
            "POST",
            CONFIRM,
            dict(self.confirm_body(draft), confirmed=False),
            expected=422,
        )
        with self.s.db.transaction() as conn:
            conn.execute(
                "DELETE FROM o_demo_support_recipients WHERE resource_id=?",
                (RESOURCE["resource_id"],),
            )
        error = self.confirm(draft, expected=409)
        self.assertEqual(error["code"], "SHARING_CONFIRMATION_REQUIRED")
        self.assertIn("O 接收主体", error["message"])
        self.assertEqual(self.counts()[:5], (0, 0, 0, 0, 0))
        self.assertEqual(seed_support_recipients(self.s.db), 1)
        consent = self.confirm(draft)
        self.assertEqual(consent["sharing_scope"]["related_grant_ids"], [])
        self.assertEqual(
            consent["sharing_scope"]["recipient_id"], consent["provider_id"]
        )
        self.assertEqual(len(consent["sharing_scope"]), 12)

    def test_cannot_create_another_patients_consent_or_read_confirmation(self):
        draft = self.create()
        self.read(draft, self.s.b, 404)
        self.confirm(draft, client=self.s.b, expected=404)
        self.call(
            "POST",
            f"/patients/{PB}/service-confirmations",
            self.confirm_body(draft),
            self.s.b,
            404,
        )
        consent = self.confirm(draft)
        self.call("GET", self.consent_path(consent), client=self.s.b, expected=404)
        self.call(
            "GET",
            self.consent_path(consent),
            client=self.s.login("demo-admin"),
            expected=404,
        )
        self.s.bind([*FAMILY_SCOPES, "services:apply", "services:read"])
        self.call("GET", self.consent_path(consent), client=self.s.f, expected=403)
        self.revoke(consent, client=self.s.f, expected=403)

    def test_explicit_new_revision_and_range_requires_revocation(self):
        draft = self.create()
        value = self.confirm(draft, OPTIONAL)
        linked = self.read(draft)
        self.assertEqual((linked["draft_revision"], linked["meta"]["revision"]), (1, 2))
        self.assertEqual(
            self.confirm(draft, list(reversed(OPTIONAL)), expected=200), value
        )
        self.confirm(draft, NEEDED, expected=409)
        amended = self.call(
            "PUT",
            self.draft_path(draft),
            {
                "expected_revision": linked["meta"]["revision"],
                "content": dict(RESOURCE, request_text="本人需要核对此修订"),
            },
        )
        self.assertIsNone(amended["confirmation_ref_id"])
        self.confirm(draft, OPTIONAL, expected=409)
        self.confirm(amended, NEEDED, expected=409)
        self.assertEqual(self.confirm(amended, OPTIONAL, expected=200), value)
        self.revoke(value)
        changed = self.confirm(amended, NEEDED)
        self.assertNotEqual(
            value["confirmation_ref_id"], changed["confirmation_ref_id"]
        )
        self.assertEqual(changed["origin_draft_revision"], 2)

    def test_24_hour_utc_boundary_and_no_sliding(self):
        draft = self.create()
        original = self.s.clock()
        consent = self.confirm(draft)
        self.assertEqual(consent["confirmed_at"], stamp(original))
        self.assertEqual(consent["valid_until"], stamp(original + timedelta(hours=24)))
        self.assertEqual(
            consent["sharing_scope"]["valid_until"], consent["valid_until"]
        )
        for micros, active in [(-1, True), (0, False), (1, False)]:
            self.s.time[0] = original + timedelta(hours=24, microseconds=micros)
            client = self.s.login("demo-patient-a")
            view = self.call("GET", self.consent_path(consent), client=client)
            self.assertEqual(view["status"], "active" if active else "expired")
            if active:
                self.assertEqual(
                    self.confirm(
                        draft,
                        hint=consent["confirmation_ref_id"],
                        client=client,
                        expected=200,
                    ),
                    consent,
                )
            else:
                self.confirm(
                    draft,
                    hint=consent["confirmation_ref_id"],
                    client=client,
                    expected=409,
                )
        renewed = self.confirm(draft, client=client)
        self.assertNotEqual(
            renewed["confirmation_ref_id"], consent["confirmation_ref_id"]
        )

    def test_revoke_invalidates_all_linked_drafts_and_old_replay_without_revoking_grant(
        self,
    ):
        _, grant = self.s.bind(FAMILY_SCOPES)
        draft, other = self.create(self.s.f), self.create()
        key = existing.key()
        consent = self.confirm(draft, key=key)
        self.assertEqual(self.confirm(other, expected=200), consent)
        revoke_key = existing.key()
        cancelled = self.revoke(consent, key=revoke_key)
        self.assertEqual(self.revoke(consent, key=revoke_key), cancelled)
        self.assertEqual(cancelled["status"], "revoked")
        self.assertEqual(cancelled["sharing_scope"]["scope_version"], 2)
        self.assertEqual(self.confirm(draft, key=key)["status"], "revoked")
        self.assertEqual(self.call("GET", self.consent_path(consent)), cancelled)
        for doc in (draft, other):
            current = self.read(doc)
            self.assertIsNone(current["confirmation_ref_id"])
            self.assertEqual(current["status"], "preparing")
        self.revoke(consent, expected=409)
        self.assertEqual(self.counts()[:5], (1, 2, 1, 2, 1))
        self.assertEqual(
            self.read(draft, self.s.f)["service_draft_id"], draft["service_draft_id"]
        )
        self.assertEqual(grant["scopes"], FAMILY_SCOPES)

    def test_concurrent_c04_keys_and_c34_double_draft_reuse(self):
        second = self.s.login("demo-patient-a")
        payload = dict(RESOURCE, request_text="可独立保存的虚构草稿")
        made = self.concurrent(
            (self.s.a, CREATE, payload, existing.key()),
            (second, CREATE, payload, existing.key()),
        )
        self.assertEqual([r.status_code for r in made], [201, 201])
        one, two = [r.json()["data"] for r in made]
        self.assertNotEqual(one["service_draft_id"], two["service_draft_id"])
        made = self.concurrent(
            (self.s.a, CONFIRM, self.confirm_body(one), existing.key()),
            (second, CONFIRM, self.confirm_body(two), existing.key()),
        )
        self.assertCountEqual([r.status_code for r in made], [200, 201])
        self.assertEqual(made[0].json()["data"], made[1].json()["data"])
        self.assertEqual(self.counts()[:5], (1, 1, 1, 2, 0))

    def test_concurrent_different_ranges_and_revoke_vs_explicit_reuse(self):
        second = self.s.login("demo-patient-a")
        draft = self.create()
        outcomes = self.concurrent(
            (self.s.a, CONFIRM, self.confirm_body(draft), existing.key()),
            (second, CONFIRM, self.confirm_body(draft, OPTIONAL), existing.key()),
        )
        self.assertCountEqual([r.status_code for r in outcomes], [201, 409])
        win = next(r.json()["data"] for r in outcomes if r.status_code == 201)
        categories = win["sharing_scope"]["data_categories"]
        revoke = {"expected_revision": 1, "reason": "并发撤销"}
        outcomes = self.concurrent(
            (self.s.a, self.consent_path(win) + "/revoke", revoke, existing.key()),
            (
                second,
                CONFIRM,
                self.confirm_body(draft, categories, win["confirmation_ref_id"]),
                existing.key(),
            ),
        )
        self.assertEqual(outcomes[0].status_code, 200)
        self.assertIn(outcomes[1].status_code, (200, 409))
        self.assertEqual(self.call("GET", self.consent_path(win))["status"], "revoked")
        self.assertEqual(self.counts()[:5], (1, 2, 1, 1, 1))

    def test_grant_version_revalidation_for_an_explicit_dependency(self):
        binding, grant = self.s.bind(FAMILY_SCOPES)
        draft = self.create()
        resolve = self.service.sharing.terms

        def with_version(version):
            # Exercise the O dependency contract with a real O test Grant.
            # Demo recipient registrations in production of this batch have no household dependency.
            def terms(*args):
                resolve(*args)
                return {grant["grant_id"]: version}

            return patch.object(self.service.sharing, "terms", side_effect=terms)

        with with_version(1):
            consent = self.confirm(draft)
        shrunk = self.revise_grant(binding, 1, ["patient:read"])
        recovered = self.revise_grant(binding, shrunk["meta"]["revision"])
        self.assertEqual(recovered["grant_id"], grant["grant_id"])
        self.assertEqual(
            self.call("GET", self.consent_path(consent))["status"], "revoked"
        )
        with with_version(3):
            self.confirm(draft, hint=consent["confirmation_ref_id"], expected=409)
            new = self.confirm(draft)
        self.call(
            "POST",
            f"/grants/{grant['grant_id']}/revoke",
            {"expected_revision": 3, "reason": "撤回关联授权"},
        )
        self.assertEqual(self.call("GET", self.consent_path(new))["status"], "revoked")
        with with_version(3):
            self.confirm(draft, expected=409)

    def test_grant_deadline_precedes_consent_and_family_access_expires(self):
        binding, grant = self.s.bind(FAMILY_SCOPES)
        expiry = self.s.clock() + timedelta(minutes=2)
        grant = self.revise_grant(
            binding, grant["meta"]["revision"], valid_until=stamp(expiry)
        )
        draft = self.create(self.s.f)
        with patch.object(
            self.service.sharing,
            "terms",
            return_value={grant["grant_id"]: grant["grant_version"]},
        ):
            consent = self.confirm(draft)
            self.s.time[0] = expiry
            self.assertEqual(
                self.call("GET", self.consent_path(consent))["status"], "expired"
            )
            self.confirm(draft, expected=409)
        self.read(draft, self.s.f, 403)

    def test_fault_after_o_gives_no_half_state_and_same_key_recovers(self):
        draft = self.create()
        before = self.counts()
        key = existing.key()
        issue = self.service.sharing.issue

        def lost_issue(*args):
            issue(*args)
            raise RuntimeError("fault after saving O scope")

        with patch.object(self.service.sharing, "issue", side_effect=lost_issue):
            self.confirm(draft, expected=500, key=key)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.read(draft), draft)
        consent = self.confirm(draft, key=key)
        revoke = self.service.sharing.revoke
        before = self.counts()
        key = existing.key()

        def lost_revoke(*args):
            revoke(*args)
            raise RuntimeError("fault after O revocation")

        with patch.object(self.service.sharing, "revoke", side_effect=lost_revoke):
            self.revoke(consent, expected=500, key=key)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.call("GET", self.consent_path(consent)), consent)
        self.assertEqual(self.revoke(consent, key=key)["status"], "revoked")
        with self.s.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM a_tasks").fetchone()[0], 0
            )
            self.assertEqual(
                conn.execute("SELECT count(*) FROM change_notices").fetchone()[0], 0
            )
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
