import copy
import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import fixtures as existing
from medplatform.core.config import ROOT
from medplatform.core.documents import get, save, stamp, uid
from medplatform.core.errors import AppError
from medplatform.support.catalog.service import (
    FIXTURE_FILE,
    ResourceFixture,
    register_catalog,
    seed_catalog,
)
from pydantic import TypeAdapter, ValidationError

PA, PB = existing.PA, existing.PB
CATALOG = "/support-resources"
RECOMMEND = f"/patients/{PA}/support-recommendations"
PHARMACY = "resource-pharmacist-demo"
COMMUNITY = "resource-community-demo"
TARGETED = "resource-community-access-demo"
INACTIVE = "resource-community-inactive-demo"
EMOTIONAL = {"resource-companionship-demo", "resource-encouragement-demo"}


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.s = existing.IdentityFixture()
        self.s.setUp()
        self.addCleanup(self.s.doCleanups)
        self.fixtures = TypeAdapter(list[ResourceFixture]).validate_json(
            (ROOT / FIXTURE_FILE).read_bytes()
        )

    def install(self, *fixtures):
        return register_catalog(self.s.db, fixtures or self.fixtures, self.s.clock)

    def request(self, path, *, client=None, expected=200, method="GET", body=None):
        return self.s.call(client or self.s.a, method, path, body, expected=expected)

    def recommend(self, need=None, **kwargs):
        return self.request(
            RECOMMEND + (f"?need={need}" if need is not None else ""), **kwargs
        )

    def fixture(self, resource_id, version=None):
        return next(
            f
            for f in reversed(self.fixtures)
            if f.resource.resource_id == resource_id
            and (version is None or f.resource.resource_version == version)
        )

    def revision(self, resource_id, previous, version, **changes):
        data = self.fixture(resource_id).model_dump()
        data["previous_version"] = previous
        data["resource"].update(resource_version=version, **changes)
        return ResourceFixture.model_validate(data)

    def o_profile(self, answers=None):
        result = self.s.submitted(answers)
        return self.request(
            f"/patients/{PA}/profiles",
            method="POST",
            expected=201,
            body={"response_id": result["response_id"]},
        )

    def o_fixture_profile(self, **fields):
        # These isolated storage fixtures exercise already-labelled O inputs.
        # The application has no path to fabricate these classifications.
        profile = copy.deepcopy(self.o_profile())
        profile.update(profile_id=uid(), **fields)
        with self.s.db.transaction() as conn:
            save(conn, "Profile", profile["profile_id"], PA, profile)
        return profile

    @staticmethod
    def codes(result):
        return {item["code"] for item in result["missing_items"]}

    @staticmethod
    def candidate_ids(result):
        return {
            a["resource_id"]
            for a in [result["primary_action"], *result["secondary_actions"]]
            if a
        }

    def test_public_shapes(self):
        self.assertEqual(seed_catalog(self.s.db), 7)
        self.assertEqual(seed_catalog(self.s.db), 0)
        result = self.request(CATALOG)
        self.assertEqual(set(result), {"items", "next_cursor"})
        self.assertEqual(len(result["items"]), 5)
        data = self.request(f"{CATALOG}/{PHARMACY}")
        self.assertEqual(
            set(data),
            {
                "resource_id",
                "resource_version",
                "service_kind",
                "name",
                "description",
                "provider",
                "availability",
                "access_mode",
                "is_essential",
                "required_shared_categories",
                "optional_shared_categories",
                "peer_group_id",
                "is_simulated",
            },
        )
        self.assertEqual(
            set(data["provider"]),
            {
                "provider_id",
                "provider_type",
                "display_name",
                "qualification_status",
                "is_simulated",
            },
        )
        self.assertEqual(data["resource_version"], "resource-demo-v2")
        self.assertEqual(data["provider"]["qualification_status"], "not_verified")
        self.assertEqual(data["access_mode"], "support_free")
        self.assertTrue(
            data["is_simulated"]
            and data["is_essential"]
            and data["provider"]["is_simulated"]
        )
        self.assertNotIn(INACTIVE, {r["resource_id"] for r in result["items"]})
        self.assertEqual(
            self.request(f"{CATALOG}/{INACTIVE}", expected=404)["code"],
            "RESOURCE_NOT_FOUND",
        )
        self.assertEqual(
            self.request(CATALOG + "?channel=rewards"),
            {"items": [], "next_cursor": None},
        )
        self.assertEqual(
            self.request(CATALOG, method="POST", body={}, expected=405)["code"],
            "METHOD_NOT_ALLOWED",
        )
        self.assertEqual(
            self.request(f"/patients/{PA}/services"), {"items": [], "next_cursor": None}
        )

    def test_explicit_installation_and_unavailable_dependency(self):
        admin = self.s.login("demo-admin")
        caps = self.request("/config/status", client=admin)["capabilities"]
        self.assertFalse(
            next(c["available"] for c in caps if c["code"] == "support_catalog")
        )
        original = self.s.db.path.read_bytes()
        self.assertEqual(
            self.request(CATALOG, expected=503)["code"], "SUPPORT_RESOURCE_UNAVAILABLE"
        )
        self.assertEqual(
            self.recommend("professional", expected=503)["code"],
            "SUPPORT_CONTEXT_UNAVAILABLE",
        )
        self.assertEqual(self.recommend("none")["need_status"], "none")
        self.assertEqual(self.s.db.path.read_bytes(), original)
        self.install()
        caps = self.request("/config/status", client=admin)["capabilities"]
        self.assertTrue(
            next(c["available"] for c in caps if c["code"] == "support_catalog")
        )

    def test_database_read_failure_uses_global_dependency_error(self):
        self.install()
        with patch(
            "medplatform.support.catalog.service.catalog_registered",
            side_effect=sqlite3.OperationalError("injected storage fault"),
        ):
            self.assertEqual(
                self.request(CATALOG, expected=503)["code"], "DEPENDENCY_NOT_READY"
            )

    def test_query_validation_and_cursor_scope(self):
        self.install()
        for query in (
            "?limit=0",
            "?limit=101",
            "?channel=other",
            "?channel=support&channel=rewards",
            "?cursor=",
            "?limit=2&limit=3",
            "?patient_id=forged",
        ):
            self.assertEqual(
                self.request(CATALOG + query, expected=422)["code"], "VALIDATION_ERROR"
            )
        for query in (
            "?need=",
            "?need=diagnosis",
            "?need=practical&need=none",
            "?profile_id=forged",
        ):
            self.assertEqual(
                self.request(RECOMMEND + query, expected=422)["code"],
                "VALIDATION_ERROR",
            )
        self.request(f"{CATALOG}/{PHARMACY}?version=resource-demo-v1", expected=422)
        first = self.request(CATALOG + "?limit=2")
        self.assertEqual(len(first["items"]), 2)
        cursor = first["next_cursor"]
        follow = CATALOG + "?limit=4&cursor=" + cursor
        second = self.request(follow)
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(
            len({r["resource_id"] for r in first["items"] + second["items"]}), 5
        )
        self.assertEqual(
            self.request(follow, client=self.s.b, expected=422)["code"],
            "INVALID_CURSOR",
        )
        self.assertEqual(
            self.request(follow + "&channel=rewards", expected=422)["code"],
            "INVALID_CURSOR",
        )

    def test_current_revision_changes_without_rewriting_prior_match(self):
        self.install()
        first = self.recommend("professional")
        self.assertEqual(
            set(first),
            {
                "patient_id",
                "profile_id",
                "primary_profile_type",
                "additional_profile_types",
                "need_status",
                "main_need",
                "primary_action",
                "secondary_actions",
                "source_refs",
                "missing_items",
                "generated_at",
                "is_simulated",
            },
        )
        self.assertEqual(
            set(first["primary_action"]),
            {
                "resource_id",
                "provider_type",
                "action_type",
                "reason",
                "title",
                "page_entry",
                "requires_confirmation",
            },
        )
        (old_ref,) = first["source_refs"]
        self.assertEqual(
            set(old_ref),
            {"module", "record_kind", "record_id", "version", "recorded_at"},
        )
        self.assertEqual(old_ref["version"], "resource-demo-v2")
        successor = self.revision(
            PHARMACY,
            "resource-demo-v2",
            "resource-demo-v3",
            name="咨询目录更新（模拟）",
        )
        self.assertEqual(self.install(successor), 1)
        self.assertEqual(self.install(successor), 0)
        self.assertEqual(self.install(), 0)
        current = self.request(f"{CATALOG}/{PHARMACY}")
        self.assertEqual(current["resource_version"], "resource-demo-v3")
        self.assertEqual(current["name"], "咨询目录更新（模拟）")
        self.assertEqual(
            self.recommend("professional")["source_refs"][0]["version"],
            current["resource_version"],
        )
        with self.s.db.connection(readonly=True) as conn:
            rows = conn.execute(
                "SELECT * FROM c_support_resource_versions WHERE resource_id=?",
                (PHARMACY,),
            ).fetchall()
            self.assertEqual(
                {r["resource_version"] for r in rows},
                {"resource-demo-v1", "resource-demo-v2", "resource-demo-v3"},
            )
            old = next(r for r in rows if r["resource_version"] == old_ref["version"])
            self.assertEqual(
                json.loads(old["resource_json"])["name"],
                first["primary_action"]["title"],
            )
            self.assertEqual(old["recorded_at"], old_ref["recorded_at"])
        with self.assertRaises(sqlite3.IntegrityError), self.s.db.transaction() as conn:
            conn.execute(
                "UPDATE c_support_resource_versions SET recorded_at=recorded_at"
            )
        conflicting = self.revision(
            PHARMACY, "resource-demo-v2", "resource-demo-v3", name="不同内容（模拟）"
        )
        with self.assertRaises(AppError) as conflict:
            self.install(conflicting)
        self.assertEqual(conflict.exception.code, "RESOURCE_VERSION_CONFLICT")
        self.assertIn("不同内容", conflict.exception.message)

    def test_seed_rollback_and_retry(self):
        self.install()
        valid = self.revision(PHARMACY, "resource-demo-v2", "resource-demo-v3")
        invalid = self.revision(COMMUNITY, "unknown-version", "resource-demo-v2")
        before = self.s.db.path.read_bytes()
        with self.assertRaises(AppError) as raised:
            self.install(valid, invalid)
        self.assertEqual(raised.exception.code, "RESOURCE_VERSION_CONFLICT")
        self.assertEqual(self.s.db.path.read_bytes(), before)
        corrected = self.revision(COMMUNITY, "resource-demo-v1", "resource-demo-v2")
        self.assertEqual(self.install(valid, corrected), 2)

    def test_concurrent_registration_replays_and_rejects_a_sibling_version(self):
        self.install()
        one = self.revision(PHARMACY, "resource-demo-v2", "branch-a")
        two = self.revision(PHARMACY, "resource-demo-v2", "branch-b")

        def concurrent(first, second):
            gate = threading.Barrier(2)

            def run(fixture):
                gate.wait(timeout=10)
                try:
                    return self.install(fixture)
                except AppError as error:
                    return error.code

            with ThreadPoolExecutor(max_workers=2) as pool:
                tasks = [pool.submit(run, f) for f in (first, second)]
                return [t.result(timeout=15) for t in tasks]

        self.assertCountEqual(concurrent(one, two), [1, "RESOURCE_VERSION_CONFLICT"])
        current = self.request(f"{CATALOG}/{PHARMACY}")["resource_version"]
        final = self.revision(PHARMACY, current, "after-race")
        self.assertCountEqual(concurrent(final, final), [1, 0])
        with self.s.db.connection(readonly=True) as conn:
            count = conn.execute(
                "SELECT count(*) FROM c_support_resource_versions WHERE resource_id=?",
                (PHARMACY,),
            ).fetchone()[0]
        self.assertEqual(count, 4)

    def test_non_mock_and_unapproved_fixture_inputs_rejected(self):
        fixture = self.fixture(PHARMACY).model_dump()
        for provider_patch in (
            {"is_simulated": False},
            {"qualification_status": "verified"},
            {"provider_type": "family"},
        ):
            bad = copy.deepcopy(fixture)
            bad["resource"]["provider"].update(provider_patch)
            with self.assertRaises(ValidationError):
                ResourceFixture.model_validate(bad)
        fixture["profile_types"] = ["B1"]
        with self.assertRaises(ValidationError):
            ResourceFixture.model_validate(fixture)

    def test_profile_reference_changes_through_real_o_revisions(self):
        self.install()
        no_profile = self.recommend("professional")
        self.assertIsNone(no_profile["profile_id"])
        self.assertEqual(self.codes(no_profile), {"profile_not_available"})
        self.assertEqual(self.candidate_ids(no_profile), {PHARMACY})
        first = self.o_profile()
        before = self.recommend("professional")
        self.assertIn("profile_type_unknown", self.codes(before))
        self.assertIsNone(before["primary_profile_type"])
        answers = existing.unknown_answers()
        answers["Q2"] = {
            "state": "answered",
            "value": {"selected": ["stockout"], "top_ranked": [], "other_text": None},
        }
        second = self.o_profile(answers)
        after = self.recommend("professional")
        self.assertNotEqual(first["profile_id"], second["profile_id"])
        self.assertEqual(before["profile_id"], first["profile_id"])
        self.assertEqual(after["profile_id"], second["profile_id"])
        o_ref = next(r for r in after["source_refs"] if r["module"] == "O")
        self.assertEqual(
            (o_ref["record_id"], o_ref["version"], o_ref["recorded_at"]),
            (
                second["profile_id"],
                str(second["meta"]["revision"]),
                second["meta"]["updated_at"],
            ),
        )
        self.assertIsNone(second["cas"]["value"])
        self.assertNotIn("药品未补充", json.dumps(after, ensure_ascii=False))
        self.assertEqual(self.candidate_ids(after), {PHARMACY})
        with self.s.db.connection(readonly=True) as conn:
            self.assertEqual(get(conn, "Profile", first["profile_id"]), first)

    def test_unknown_profile_type_does_not_satisfy_a_condition(self):
        self.install(self.fixture(TARGETED))
        self.o_profile()
        unknown = self.recommend("practical")
        self.assertEqual(
            self.codes(unknown),
            {"profile_type_unknown", "profile_condition_unresolved"},
        )
        self.assertEqual(unknown["need_status"], "insufficient")
        self.assertEqual(self.candidate_ids(unknown), set())

    def test_known_matching_and_nonmatching_profile_types(self):
        self.install(self.fixture(TARGETED))
        self.o_fixture_profile(primary_type="C1", additional_types=[])
        none = self.recommend("practical")
        self.assertEqual(none["need_status"], "needed")
        self.assertEqual(
            self.codes(none), {"profile_condition_not_met", "no_matching_resource"}
        )
        self.assertFalse(none["primary_action"])
        found = self.o_fixture_profile(primary_type="C1", additional_types=["B2"])
        result = self.recommend("practical")
        self.assertEqual(result["profile_id"], found["profile_id"])
        self.assertEqual(result["additional_profile_types"], ["B2"])
        self.assertEqual(self.candidate_ids(result), {TARGETED})
        self.assertIn("适用条件", result["primary_action"]["reason"])
        self.assertEqual(result["missing_items"], [])

    def test_availability_unknown_and_unavailable_are_distinct(self):
        self.install(self.fixture(TARGETED))
        self.o_fixture_profile(primary_type="B2", additional_types=[])
        pending = self.revision(
            TARGETED, "resource-demo-v1", "pending", availability="unknown"
        )
        self.install(pending)
        unknown = self.recommend("practical")
        self.assertEqual(unknown["need_status"], "insufficient")
        self.assertEqual(self.codes(unknown), {"resource_availability_unknown"})
        self.assertEqual(self.request(CATALOG)["items"], [])
        closed = self.revision(
            TARGETED, "pending", "closed", availability="unavailable"
        )
        self.install(closed)
        known = self.recommend("practical")
        self.assertEqual(
            self.codes(known), {"resource_unavailable", "no_matching_resource"}
        )
        self.assertEqual(known["need_status"], "needed")
        self.assertEqual(self.candidate_ids(known), set())

    def test_only_explicit_need_and_no_priority_between_equal_candidates(self):
        self.install()
        self.o_profile()
        before = self.s.db.path.read_bytes()
        unknown, declined = self.recommend(), self.recommend("none")
        self.assertEqual(
            (unknown["need_status"], unknown["main_need"]),
            ("insufficient", "unknown"),
        )
        self.assertIn("support_need_unknown", self.codes(unknown))
        self.assertEqual(declined["need_status"], "none")
        self.assertEqual(declined["source_refs"], [])
        self.assertEqual(
            self.candidate_ids(declined) | self.candidate_ids(unknown), set()
        )
        match = self.recommend("emotional")
        self.assertIsNone(match["primary_action"])
        self.assertEqual(self.candidate_ids(match), EMOTIONAL)
        self.assertTrue(
            all(
                a["action_type"] == "companionship" and a["requires_confirmation"]
                for a in match["secondary_actions"]
            )
        )
        self.request(CATALOG)
        self.request(f"{CATALOG}/{PHARMACY}")
        self.assertEqual(self.s.db.path.read_bytes(), before)
        third = self.fixture("resource-companionship-demo").model_dump()
        third["resource"]["resource_id"] = "resource-other-companionship-demo"
        self.install(ResourceFixture.model_validate(third))
        overflow = self.recommend("emotional")
        self.assertEqual(self.candidate_ids(overflow), set())
        self.assertIn("candidate_details_available", self.codes(overflow))
        ids = [
            ref["record_id"] for ref in overflow["source_refs"] if ref["module"] == "C"
        ]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(
            ids,
            [
                ref["record_id"]
                for ref in self.recommend("emotional")["source_refs"]
                if ref["module"] == "C"
            ],
        )
        self.assertEqual(
            {r["record_id"] for r in overflow["source_refs"] if r["module"] == "C"},
            EMOTIONAL | {"resource-other-companionship-demo"},
        )

    def test_family_precise_scope_revocation_and_other_identities(self):
        self.install()
        profile = self.o_fixture_profile(primary_type="B2", additional_types=[])
        admin = self.s.login("demo-admin")
        self.request(CATALOG, client=admin, expected=403)
        self.recommend("practical", client=admin, expected=404)
        self.recommend("practical", client=self.s.b, expected=404)
        self.recommend("practical", client=self.s.f, expected=404)
        binding, grant = self.s.bind(["profile:read", "support:read"])
        self.request(
            "/auth/current-patient",
            client=self.s.f,
            method="PUT",
            body={"patient_id": PA},
        )
        self.assertTrue(self.request(CATALOG, client=self.s.f)["items"])
        original = self.recommend("practical", client=self.s.f)
        self.assertEqual(original["profile_id"], profile["profile_id"])
        self.assertEqual(self.candidate_ids(original), {COMMUNITY, TARGETED})
        cursor = self.request(CATALOG + "?limit=1", client=self.s.f)["next_cursor"]
        path = f"/family-bindings/{binding['binding_id']}/grant"
        reduced = self.request(
            path,
            method="PUT",
            body={
                "expected_revision": grant["meta"]["revision"],
                "scopes": ["support:read"],
                "valid_until": None,
                "confirmed": True,
            },
        )
        with patch.object(
            self.s.app.state.catalog.o,
            "read",
            side_effect=AssertionError("restricted profile was read"),
        ):
            restricted = self.recommend("practical", client=self.s.f)
        self.assertIsNone(restricted["profile_id"])
        self.assertIsNone(restricted["primary_profile_type"])
        self.assertIn("profile_restricted", self.codes(restricted))
        self.assertEqual(self.candidate_ids(restricted), {COMMUNITY})
        self.assertNotIn(profile["profile_id"], json.dumps(restricted))
        self.assertEqual({r["module"] for r in restricted["source_refs"]}, {"C"})
        self.request(
            f"/grants/{reduced['grant_id']}/revoke",
            method="POST",
            body={
                "expected_revision": reduced["meta"]["revision"],
                "reason": "虚构撤权验收",
            },
        )
        self.assertEqual(
            self.recommend("practical", client=self.s.f, expected=403)["code"],
            "SCOPE_REQUIRED",
        )
        self.assertEqual(
            self.request(CATALOG + "?cursor=" + cursor, client=self.s.f, expected=403)[
                "code"
            ],
            "SCOPE_REQUIRED",
        )
        self.request(f"{CATALOG}/{PHARMACY}", client=self.s.f, expected=403)

    def test_expired_grant_and_cursor_bound_to_selected_patient(self):
        self.install()
        binding, grant = self.s.bind(["support:read"])
        self.request(
            f"/family-bindings/{binding['binding_id']}/grant",
            method="PUT",
            body={
                "expected_revision": grant["meta"]["revision"],
                "scopes": ["support:read"],
                "valid_until": stamp(self.s.clock() + timedelta(minutes=1)),
                "confirmed": True,
            },
        )
        first = self.request(CATALOG + "?limit=1", client=self.s.f)["next_cursor"]
        self.request(
            "/auth/current-patient",
            client=self.s.f,
            method="PUT",
            body={"patient_id": PA},
        )
        self.assertEqual(
            self.request(CATALOG + "?cursor=" + first, client=self.s.f, expected=422)[
                "code"
            ],
            "INVALID_CURSOR",
        )
        self.s.time[0] += timedelta(minutes=2)
        self.recommend("practical", client=self.s.f, expected=403)
        self.request(CATALOG, client=self.s.f, expected=403)
