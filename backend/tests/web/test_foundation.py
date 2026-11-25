import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import APIRouter
from fastapi.testclient import TestClient

from fixtures import BASE, key
from medplatform.core.config import ROOT, ConfigurationError, Settings, load_settings
from medplatform.core.database import Database
from medplatform.core.errors import SchemaError
from medplatform.core.migrations import DIRECTORY, catalog, migrate, status
from medplatform.identity.service import seed_demo
from medplatform.web.app import create_app

LATEST = len(catalog())


def event(
    conn,
    event_id,
    patient="pa",
    *,
    kind="medication",
    source="manual",
    subject="aa",
    source_id=None,
    payload=None,
):
    conn.execute(
        """INSERT INTO source_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event_id,
            patient,
            "demo",
            kind,
            source,
            subject,
            source_id or event_id,
            ("self_report" if source == "manual" else "box_opening")
            if kind == "medication"
            else None,
            "2026-11-16T00:00:00+00:00",
            "2026-11-16T00:01:00+00:00",
            subject if source == "manual" else None,
            subject if source != "manual" else None,
            json.dumps(
                payload if payload is not None else {"reported_status": "taken"}
            ),
            1,
        ),
    )


class Sandbox(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "test-output"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        assert self.path.resolve().parent == parent.resolve()
        self.db = Database(self.path / "demo.sqlite3")

    def settings(self):
        return Settings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_PATH=self.db.path,
            AUTH_MODE="demo",
            LLM_MODE="mock",
        )


class MigrationTests(Sandbox):
    def test_explicit_initialization_upgrade_preserves_data(self):
        migrate(self.db, initialize=True, target=1)
        with self.db.transaction() as c:
            event(c, "e1")
            event(c, "e2", patient="pb", subject="ab", source_id="e1")
        self.assertEqual(migrate(self.db), LATEST)
        self.assertEqual(status(self.db), LATEST)
        with self.db.connection(readonly=True) as c:
            self.assertEqual(
                c.execute("SELECT count(*) FROM source_events").fetchone()[0], 2
            )
            self.assertEqual(
                c.execute("SELECT count(*) FROM event_revisions").fetchone()[0], 2
            )
        self.assertEqual(migrate(self.db, initialize=True), LATEST)
        with self.assertRaises(SchemaError):
            migrate(self.db, target=1)

    def test_unmanaged_database_is_not_overwritten(self):
        with self.db.connection(create=True) as c:
            c.execute("CREATE TABLE untouched(value TEXT)")
            c.execute("INSERT INTO untouched VALUES ('keep')")
        with self.assertRaises(SchemaError):
            migrate(self.db, initialize=True)
        with self.db.connection(readonly=True) as c:
            self.assertEqual(
                c.execute("SELECT value FROM untouched").fetchone()[0], "keep"
            )
            self.assertIsNone(
                c.execute(
                    "SELECT name FROM sqlite_master WHERE name='schema_migrations'"
                ).fetchone()
            )

    def test_tampered_applied_migration_is_refused(self):
        migrate(self.db, initialize=True)
        copied = self.path / "migrations"
        shutil.copytree(DIRECTORY, copied)
        with (copied / "0001_foundation.sql").open("ab") as f:
            f.write(b"\n-- changed history\n")
        with self.assertRaises(SchemaError):
            status(self.db, copied)
        with self.assertRaises(SchemaError):
            migrate(self.db, directory=copied)

    def test_failed_migration_rolls_back_ddl_data_and_version(self):
        migrate(self.db, initialize=True)
        with self.db.transaction() as c:
            event(c, "keep")
        copied = self.path / "migrations"
        shutil.copytree(DIRECTORY, copied)
        (copied / f"{LATEST + 1:04d}_failure.sql").write_text(
            "CREATE TABLE rollback_probe(value TEXT);\nINSERT INTO rollback_probe VALUES ('x');\nINVALID SQL;\n",
            encoding="utf-8",
        )
        with self.assertRaises(sqlite3.Error):
            migrate(self.db, directory=copied)
        with self.db.connection(readonly=True) as c:
            self.assertIsNone(
                c.execute(
                    "SELECT name FROM sqlite_master WHERE name='rollback_probe'"
                ).fetchone()
            )
            self.assertEqual(
                c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0],
                LATEST,
            )
            self.assertEqual(
                c.execute("SELECT event_id FROM source_events").fetchone()[0], "keep"
            )

    def test_source_dedup_and_transaction_rollback(self):
        migrate(self.db, initialize=True)
        with self.db.transaction() as c:
            event(c, "original", source_id="stable")
        with self.assertRaises(sqlite3.IntegrityError), self.db.transaction() as c:
            c.execute(
                "INSERT INTO operation_audit VALUES ('rollback',NULL,NULL,'test','pending','now','demo')"
            )
            event(c, "duplicate", source_id="stable")
        with self.db.connection(readonly=True) as c:
            self.assertEqual(
                c.execute("SELECT count(*) FROM operation_audit").fetchone()[0], 0
            )
            self.assertEqual(
                c.execute("SELECT count(*) FROM source_events").fetchone()[0], 1
            )

    def test_revision_chain_keeps_original_and_requires_reason(self):
        migrate(self.db, initialize=True, target=1)
        with self.db.transaction() as c:
            event(c, "history")
        migrate(self.db)
        with self.db.transaction() as c:
            c.execute("""INSERT INTO event_revisions VALUES
                ('history',2,'correction','later','{"reported_status":"unknown"}',
                 'fixture correction',1,'aa','later',1)""")
        with self.assertRaises(sqlite3.IntegrityError), self.db.transaction() as c:
            c.execute("""INSERT INTO event_revisions VALUES
                    ('history',3,'withdrawal','later','{}',NULL,2,'aa','later',1)""")
        with self.db.connection(readonly=True) as c:
            rows = c.execute(
                "SELECT * FROM event_revisions ORDER BY revision"
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                json.loads(rows[0]["payload_json"])["reported_status"], "taken"
            )
            self.assertEqual(rows[1]["replaces_revision"], 1)

    def test_null_cannot_bypass_medication_evidence_constraints(self):
        migrate(self.db, initialize=True)
        with self.db.transaction() as c:
            event(c, "e1")
        with self.assertRaises(sqlite3.IntegrityError), self.db.transaction() as c:
            c.execute("UPDATE source_events SET evidence_type=NULL WHERE event_id='e1'")


class WebTests(Sandbox):
    def client(self):
        app = create_app(self.settings())
        self.app = app
        client = TestClient(
            app, base_url="http://127.0.0.1:8000", raise_server_exceptions=False
        )
        self.addCleanup(client.close)
        return client

    def test_no_import_startup_or_health_initialization(self):
        client = self.client()
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.db.path.exists())
        self.assertEqual(
            set(response.json()), {"request_id", "status", "data", "error"}
        )
        self.assertIsNone(response.json()["data"])
        migrate(self.db, initialize=True, target=1)
        self.assertEqual(client.get("/api/v1/health").status_code, 503)
        with self.db.connection(readonly=True) as c:
            self.assertEqual(
                c.execute("SELECT max(version) FROM schema_migrations").fetchone()[0], 1
            )

    def test_ready_health_and_no_business_routes(self):
        migrate(self.db, initialize=True)
        client = self.client()
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["readiness"], "ready")
        self.assertEqual(
            response.headers["X-Request-ID"], response.json()["request_id"]
        )
        for url in ("/api/v1/unknown", "/docs", "/openapi.json"):
            r = client.get(url)
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers["content-type"], "application/json")
        self.assertEqual(client.get("/api/v1/health?patient_id=pb").status_code, 422)

    def test_schema_table_damage_is_not_ready(self):
        migrate(self.db, initialize=True)
        with self.db.transaction() as c:
            c.execute("ALTER TABLE event_revisions RENAME TO damaged_revisions")
        self.assertEqual(self.client().get("/api/v1/health").status_code, 503)

    def test_admin_configuration_is_authenticated_and_redacted(self):
        migrate(self.db, initialize=True)
        seed_demo(self.db)
        settings = self.settings().model_copy(
            update={
                "LLM_BASE_URL": "https://private.invalid/secret",
                "LLM_MODEL": "mock-test",
            }
        )
        app = create_app(settings)
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            self.assertEqual(
                client.get(
                    "/api/v1/config/status", headers={"X-Account-ID": "admin"}
                ).status_code,
                401,
            )
            response = client.post(
                "/api/v1/auth/demo-session",
                json={"demo_account_id": "demo-patient-a"},
                headers={"Origin": BASE, "Idempotency-Key": key()},
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(client.get("/api/v1/config/status").status_code, 403)
            response = client.post(
                "/api/v1/auth/demo-session",
                json={"demo_account_id": "demo-admin"},
                headers={"Origin": BASE, "Idempotency-Key": key()},
            )
            self.assertEqual(response.status_code, 201)
            r = client.get("/api/v1/config/status")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["data"]["model_connectivity"], "unverified")
            self.assertNotIn("private.invalid", r.text)
            self.assertNotIn(str(self.db.path), r.text)
        self.assertTrue(
            next(
                c for c in r.json()["data"]["capabilities"] if c["code"] == "demo_login"
            )["available"]
        )

    def test_csrf_origin_and_idempotency_header_guard(self):
        migrate(self.db, initialize=True)
        seed_demo(self.db)
        client = self.client()
        router = APIRouter()

        @router.post("/api/v1/test-write", operation_id="test_write")
        def test_write():
            return {"result": "guard reached; test only"}

        self.app.state.registry.include_router(self.app, router)
        self.assertEqual(client.post("/api/v1/test-write").status_code, 401)
        response = client.post(
            "/api/v1/auth/demo-session",
            json={"demo_account_id": "demo-patient-a"},
            headers={"Origin": BASE, "Idempotency-Key": key()},
        )
        self.assertEqual(response.status_code, 201)
        csrf = response.json()["data"]["csrf_token"]
        self.assertEqual(client.post("/api/v1/test-write").status_code, 403)
        headers = {
            "X-CSRF-Token": csrf,
            "Origin": "http://evil.invalid",
            "Idempotency-Key": "test-operation-0001",
        }
        self.assertEqual(
            client.post("/api/v1/test-write", headers=headers).status_code, 403
        )
        headers["Origin"] = "http://127.0.0.1:8000"
        self.assertEqual(
            client.post("/api/v1/test-write", headers=headers).status_code, 200
        )
        headers.pop("Idempotency-Key")
        self.assertEqual(
            client.post("/api/v1/test-write", headers=headers).status_code, 422
        )

    def test_errors_and_logs_do_not_echo_secrets(self):
        client = self.client()
        router = APIRouter()

        @router.get("/api/v1/test-failure", operation_id="test_failure")
        def fail():
            raise RuntimeError("PRIVATE_TEST_SECRET")

        self.app.state.registry.include_router(self.app, router)
        with self.assertLogs("medplatform.requests", level="INFO") as logs:
            r = client.get(
                "/api/v1/test-failure?value=PRIVATE_TEST_SECRET",
                headers={"X-Request-ID": "PRIVATE_TEST_SECRET"},
            )
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("PRIVATE_TEST_SECRET", r.text + " ".join(logs.output))
        self.assertEqual(
            client.get("/", headers={"Host": "evil.invalid"}).status_code, 403
        )

    def test_page_and_local_assets(self):
        static = self.path / "static"
        with patch("medplatform.web.app.STATIC", static):
            client = self.client()
            r = client.get("/")
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()["error"]["code"], "FRONTEND_NOT_BUILT")
            (static / "assets").mkdir(parents=True)
            (static / "index.html").write_text(
                '<script type="module" src="/static/assets/app.js"></script>'
            )
            (static / "assets" / "app.js").write_text("export {}")
            r = client.get("/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(client.get("/static/assets/app.js").status_code, 200)
        self.assertNotIn("unsafe-inline", r.headers["content-security-policy"])


class ConfigurationAndRegistryTests(Sandbox):
    def test_explicit_real_external_production_fail_closed(self):
        for values in (
            {"LLM_MODE": "real"},
            {"AUTH_MODE": "external"},
            {"APP_ENV": "production"},
            {"PORT": 0},
        ):
            env = {key: str(value) for key, value in values.items()}
            with (
                patch.dict(Settings.model_config, {"env_file": None}),
                patch.dict(
                    os.environ,
                    {**env, "LLM_API_KEY": "PRIVATE_TEST_SECRET"},
                    clear=True,
                ),
            ):
                with self.assertRaises(ConfigurationError) as e:
                    load_settings()
                self.assertNotIn("PRIVATE_TEST_SECRET", str(e.exception))

    def test_duplicate_route_registration(self):
        app = create_app(self.settings())
        router = APIRouter()

        @router.get("/api/v1/health", operation_id="different_name")
        def duplicate():
            return {}

        with self.assertRaises(ValueError):
            app.state.registry.include_router(app, router)


if __name__ == "__main__":
    unittest.main()
