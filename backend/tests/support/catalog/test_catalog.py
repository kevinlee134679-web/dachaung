import copy
import json
import sqlite3
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from pydantic import TypeAdapter, ValidationError

import fixtures as existing
from medplatform.core.config import ROOT
from medplatform.core.documents import stamp
from medplatform.core.errors import AppError
from medplatform.support.catalog.service import (
    FIXTURE_FILE,
    ResourceFixture,
    register_catalog,
    seed_catalog,
)

PA = existing.PA
CATALOG = "/support-resources"
PHARMACY = "resource-pharmacist-demo"
COMMUNITY = "resource-community-demo"
INACTIVE = "resource-community-inactive-demo"


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
            "?channel=rewards",
            "?channel=support&channel=rewards",
            "?cursor=",
            "?limit=2&limit=3",
            "?patient_id=forged",
        ):
            self.assertEqual(
                self.request(CATALOG + query, expected=422)["code"], "VALIDATION_ERROR"
            )
        self.request(f"{CATALOG}/{PHARMACY}?version=resource-demo-v1", expected=422)
        first = self.request(CATALOG + "?limit=2")
        self.assertEqual(len(first["items"]), 2)
        follow = CATALOG + "?limit=4&cursor=" + first["next_cursor"]
        second = self.request(follow)
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(
            len({r["resource_id"] for r in first["items"] + second["items"]}), 5
        )
        self.assertEqual(
            self.request(follow, client=self.s.b, expected=422)["code"],
            "INVALID_CURSOR",
        )

    def test_current_revision_preserves_prior_versions(self):
        self.install()
        first = self.request(f"{CATALOG}/{PHARMACY}")
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
        with self.s.db.connection(readonly=True) as conn:
            rows = conn.execute(
                "SELECT * FROM c_support_resource_versions WHERE resource_id=?",
                (PHARMACY,),
            ).fetchall()
            self.assertEqual(
                {r["resource_version"] for r in rows},
                {"resource-demo-v1", "resource-demo-v2", "resource-demo-v3"},
            )
            old = next(
                r for r in rows if r["resource_version"] == first["resource_version"]
            )
            self.assertEqual(json.loads(old["resource_json"]), first)
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
        fixture["resource"]["access_mode"] = "reward_only"
        with self.assertRaises(ValidationError):
            ResourceFixture.model_validate(fixture)

    def test_family_scope_revocation_and_other_identities(self):
        self.install()
        admin = self.s.login("demo-admin")
        self.request(CATALOG, client=admin, expected=403)
        _, grant = self.s.bind(["support:read"])
        self.request(
            "/auth/current-patient",
            client=self.s.f,
            method="PUT",
            body={"patient_id": PA},
        )
        self.assertTrue(self.request(CATALOG, client=self.s.f)["items"])
        cursor = self.request(CATALOG + "?limit=1", client=self.s.f)["next_cursor"]
        self.request(
            f"/grants/{grant['grant_id']}/revoke",
            method="POST",
            body={
                "expected_revision": grant["meta"]["revision"],
                "reason": "虚构撤权验收",
            },
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
        self.request(CATALOG, client=self.s.f, expected=403)
