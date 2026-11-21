import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import APIRouter
from fastapi.testclient import TestClient
from medplatform.core.config import ROOT, ConfigurationError, Settings, load_settings
from medplatform.core.database import Database
from medplatform.core.errors import AppError, SchemaError
from medplatform.core.migrations import DIRECTORY, catalog, migrate, status
from medplatform.identity.auth import Account, DemoAuthority
from medplatform.web.app import create_app
from medplatform.web.registry import ModuleRegistry

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


def slot(conn, slot_id="slot-a", patient="pa"):
    conn.execute(
        "INSERT INTO dose_slots VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            slot_id,
            patient,
            "demo",
            "plan-demo-" + patient,
            1,
            "entry-" + slot_id,
            "med-demo",
            "2026-11-16T00:00:00+00:00",
            "active",
            "fixture-v1",
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
            DIALOGUE_PIPELINE="single_pass",
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

    def test_two_evidences_one_slot_and_cross_patient_fk(self):
        migrate(self.db, initialize=True, target=1)
        with self.db.transaction() as c:
            slot(c)
            slot(c, "slot-b", "pb")
            event(c, "self")
            event(c, "box", source="box", subject="device-a")
            event(c, "unlinked")
        migrate(self.db)
        with self.db.transaction() as c:
            for eid in ("self", "box"):
                c.execute(
                    "INSERT INTO evidence_slot_links VALUES (?,1,'pa','demo','slot-a')",
                    (eid,),
                )
        with self.db.connection(readonly=True) as c:
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM evidence_slot_links WHERE dose_slot_id='slot-a'"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                c.execute(
                    "SELECT count(*) FROM dose_slots WHERE patient_id='pa'"
                ).fetchone()[0],
                1,
            )
        with (
            self.assertRaisesRegex(sqlite3.IntegrityError, "FOREIGN KEY"),
            self.db.transaction() as c,
        ):
            c.execute(
                "INSERT INTO evidence_slot_links VALUES ('unlinked',1,'pb','demo','slot-b')"
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

    def test_null_zero_and_revisions_survive_upgrade(self):
        migrate(self.db, initialize=True, target=1)
        with self.db.transaction() as c:
            event(
                c,
                "missing",
                kind="measurement",
                payload={"value": None, "missing_reason": "not_collected"},
            )
            event(
                c,
                "zero",
                kind="measurement",
                payload={"value": 0, "missing_reason": None},
            )
        migrate(self.db)
        with self.db.connection(readonly=True) as c:
            values = {
                r["event_id"]: json.loads(r["payload_json"])["value"]
                for r in c.execute("SELECT * FROM event_revisions")
            }
            self.assertIsNone(values["missing"])
            self.assertEqual(values["zero"], 0)

    def test_null_cannot_bypass_medication_evidence_constraints(self):
        migrate(self.db, initialize=True)
        with self.db.transaction() as c:
            event(c, "e1")
        with self.assertRaises(sqlite3.IntegrityError), self.db.transaction() as c:
            c.execute("UPDATE source_events SET evidence_type=NULL WHERE event_id='e1'")


class WebTests(Sandbox):
    def client(self, auth=None):
        app = create_app(self.settings(), auth)
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
        for url in ("/api/v1/statistics", "/api/v1/unknown", "/docs", "/openapi.json"):
            r = client.get(url)
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.headers["content-type"], "application/json")
        self.assertEqual(client.get("/api/v1/health?patient_id=pb").status_code, 422)

    def test_schema_table_damage_is_not_ready(self):
        migrate(self.db, initialize=True)
        with self.db.transaction() as c:
            c.execute("ALTER TABLE evidence_slot_links RENAME TO damaged_links")
        self.assertEqual(self.client().get("/api/v1/health").status_code, 503)

    def test_admin_configuration_is_authenticated_and_redacted(self):
        migrate(self.db, initialize=True)
        auth = DemoAuthority([Account("admin", admin=True), Account("user", "pa")])
        settings = self.settings().model_copy(
            update={
                "LLM_BASE_URL": "https://private.invalid/secret",
                "LLM_MODEL": "mock-test",
            }
        )
        app = create_app(settings, auth)
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            self.assertEqual(
                client.get(
                    "/api/v1/config/status", headers={"X-Account-ID": "admin"}
                ).status_code,
                401,
            )
            client.cookies.set("session", auth.issue("user")[0])
            self.assertEqual(client.get("/api/v1/config/status").status_code, 403)
            client.cookies.set("session", auth.issue("admin")[0])
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
        auth = DemoAuthority([Account("aa", "pa")])
        client = self.client(auth)
        router = APIRouter()

        @router.post("/api/v1/test-write", operation_id="test_write")
        def test_write():
            return {"result": "guard reached; test only"}

        self.app.state.registry.include_router(self.app, router)
        token, csrf = auth.issue("aa")
        self.assertEqual(client.post("/api/v1/test-write").status_code, 401)
        client.cookies.set("session", token)
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
        self.assertIn(r.json()["request_id"], " ".join(logs.output))
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
            with patch.dict(
                os.environ, {**env, "LLM_API_KEY": "PRIVATE_TEST_SECRET"}, clear=True
            ):
                with self.assertRaises(ConfigurationError) as e:
                    load_settings()
                self.assertNotIn("PRIVATE_TEST_SECRET", str(e.exception))

    def test_duplicate_route_and_operation_registration(self):
        app = create_app(self.settings())
        router = APIRouter()

        @router.get("/api/v1/health", operation_id="different_name")
        def duplicate():
            return {}

        with self.assertRaises(ValueError):
            app.state.registry.include_router(app, router)
        registry = ModuleRegistry()
        registry.register_operation("safe", lambda: None)
        with self.assertRaises(ValueError):
            registry.register_operation("safe", lambda: None)
        with self.assertRaises(ValueError):
            registry.register_operation("unsafe", "arbitrary-command")

    def test_session_expiration_and_revocation(self):
        now = [datetime(2026, 11, 16, tzinfo=UTC)]
        auth = DemoAuthority([Account("aa", "pa")], clock=lambda: now[0])
        token, _csrf = auth.issue("aa")
        principal = auth.resolve(token)
        now[0] += timedelta(hours=8)
        with self.assertRaises(AppError):
            auth.resolve(token)
        now[0] -= timedelta(hours=1)
        auth.revoke_session(principal)
        with self.assertRaises(AppError):
            auth.resolve(token)


if __name__ == "__main__":
    unittest.main()
