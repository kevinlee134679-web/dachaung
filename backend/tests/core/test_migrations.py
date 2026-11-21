import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dialogue import test_star as prior
from medplatform.core.config import ROOT
from medplatform.core.database import Database
from medplatform.core.migrations import migrate, status


class StageMigrationTests(unittest.TestCase):
    def test_star_checkpoint_upgrade_and_injected_ddl_failure_preserve_prior_rows(self):
        fixture = prior.StarTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.base.send(fixture.base.create())
        with tempfile.TemporaryDirectory(dir=ROOT / "test-output") as directory:
            folder = Path(directory)
            db = Database(folder / "schema15.sqlite3")
            migrate(db, initialize=True, target=15)
            tables = [
                "b_sessions",
                "b_messages",
                "b_generations",
                "b_generation_runs",
                "b_star_checkpoints",
            ]
            before = {}
            with (
                fixture.h.db.connection(readonly=True) as source,
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
            last = faulty / "0016_support_rule_versions.sql"
            with last.open("a") as stream:
                stream.write("\nCREATE TABL deliberate_failure(x);\n")
            original = hashlib.sha256(db.path.read_bytes()).hexdigest()
            with self.assertRaises(sqlite3.Error):
                migrate(db, directory=faulty)
            self.assertEqual(hashlib.sha256(db.path.read_bytes()).hexdigest(), original)
            migrate(db)
            self.assertEqual(status(db), 16)
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
