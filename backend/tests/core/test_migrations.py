import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dialogue import test_dialogue as prior
from medplatform.core.config import ROOT
from medplatform.core.database import Database
from medplatform.core.migrations import catalog, migrate, status


class StageMigrationTests(unittest.TestCase):
    def test_analytics_cleanup_cancels_only_nonterminal_refresh_tasks(self):
        (ROOT / "test-output").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "test-output") as directory:
            db = Database(Path(directory) / "schema19.sqlite3")
            migrate(db, initialize=True, target=19)
            with db.transaction() as conn:
                for identifier, kind, task_status in (
                    ("pending", "refresh_statistics", "pending"),
                    ("running", "refresh_summary", "running"),
                    ("finished", "refresh_summary", "succeeded"),
                    ("other", "deliver_reminder", "pending"),
                ):
                    document = {
                        "task_id": identifier,
                        "kind": kind,
                        "status": task_status,
                        "cancellation_requested": False,
                        "next_attempt_at": "2026-01-01T00:00:00+00:00",
                        "failure_reason": None,
                        "meta": {
                            "revision": 1,
                            "updated_at": "2025-01-01T00:00:00+00:00",
                        },
                    }
                    raw = json.dumps(document)
                    conn.execute(
                        "INSERT INTO a_tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            identifier,
                            "patient",
                            "demo",
                            "O" if kind == "deliver_reminder" else "A",
                            identifier,
                            None,
                            raw,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO a_task_history VALUES (?, ?, ?)",
                        (identifier, 1, raw),
                    )
            migrate(db)
            self.assertEqual(status(db), len(catalog()))
            with db.connection(readonly=True) as conn:
                tasks = {
                    row[0]: json.loads(row[1])
                    for row in conn.execute(
                        "SELECT task_id, document_json FROM a_tasks"
                    )
                }
                for identifier in ("pending", "running"):
                    task = tasks[identifier]
                    self.assertEqual(task["status"], "cancelled")
                    self.assertTrue(task["cancellation_requested"])
                    self.assertIsNone(task["next_attempt_at"])
                    self.assertTrue(task["failure_reason"])
                    self.assertEqual(task["meta"]["revision"], 2)
                    history = conn.execute(
                        "SELECT document_json FROM a_task_history WHERE task_id=? AND revision=2",
                        (identifier,),
                    ).fetchone()
                    self.assertEqual(json.loads(history[0]), task)
                self.assertEqual(tasks["finished"]["status"], "succeeded")
                self.assertEqual(tasks["other"]["status"], "pending")
                self.assertEqual(tasks["finished"]["meta"]["revision"], 1)
                self.assertEqual(tasks["other"]["meta"]["revision"], 1)
                tables = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                self.assertTrue(
                    {
                        "s03_invalidations",
                        "s03_results",
                        "s03_computation_snapshots",
                        "change_notices",
                    }.isdisjoint(tables)
                )
                self.assertEqual(
                    conn.execute("PRAGMA foreign_key_check").fetchall(), []
                )

    def test_upgrade_and_injected_ddl_failure_preserve_prior_rows(self):
        fixture = prior.DialogueTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.send(fixture.create())
        with tempfile.TemporaryDirectory(dir=ROOT / "test-output") as directory:
            folder = Path(directory)
            db = Database(folder / "schema16.sqlite3")
            migrate(db, initialize=True, target=16)
            tables = [
                "b_sessions",
                "b_messages",
                "b_generations",
                "b_generation_runs",
            ]
            before = {}
            with (
                fixture.s.db.connection(readonly=True) as source,
                db.transaction() as target,
            ):
                for table in tables:
                    rows = [
                        tuple(row)
                        for row in source.execute(
                            "SELECT * FROM " + table + " ORDER BY rowid"
                        )
                    ]
                    before[table] = rows
                    for row in rows:
                        target.execute(
                            "INSERT INTO "
                            + table
                            + " VALUES ("
                            + ",".join("?" for _ in row)
                            + ")",
                            row,
                        )
            faulty = folder / "faulty-migrations"
            shutil.copytree(ROOT / "migrations", faulty)
            last = max(faulty.glob("*.sql"))
            with last.open("a") as stream:
                stream.write("\nCREATE TABL deliberate_failure(x);\n")
            original = hashlib.sha256(db.path.read_bytes()).hexdigest()
            with self.assertRaises(sqlite3.Error):
                migrate(db, directory=faulty)
            self.assertEqual(hashlib.sha256(db.path.read_bytes()).hexdigest(), original)
            migrate(db)
            self.assertEqual(status(db), len(catalog()))
            with db.connection(readonly=True) as connection:
                for table, rows in before.items():
                    self.assertEqual(
                        [
                            tuple(row)
                            for row in connection.execute(
                                "SELECT * FROM " + table + " ORDER BY rowid"
                            )
                        ],
                        rows,
                    )
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(), []
                )
