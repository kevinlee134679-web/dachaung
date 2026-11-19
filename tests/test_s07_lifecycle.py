import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from medplatform import lifecycle
from medplatform.database import Database
from medplatform.migrations import migrate, status


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = Database(self.root / 'demo.sqlite3')

    def invoke(self, command, *args):
        with patch.object(sys, 'argv', ['lifecycle', command, '--database', str(self.db.path), *args]):
            return lifecycle.main()

    def test_repeat_initialization_cannot_reset_or_change_existing_data(self):
        migrate(self.db, initialize=True)
        before = self.db.path.read_bytes()
        self.assertEqual(self.invoke('init-demo'), 2)
        self.assertEqual(before, self.db.path.read_bytes())

    def test_migration_requires_stopped_writers_before_any_write(self):
        migrate(self.db, initialize=True, target=14)
        before = self.db.path.read_bytes()
        self.assertEqual(self.invoke('migrate'), 2)
        self.assertEqual(before, self.db.path.read_bytes())

    def test_backup_upgrade_preserves_legacy_row_files_and_manifest(self):
        migrate(self.db, initialize=True, target=14)
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO o_accounts VALUES ('fixture-account','虚构保留对象',NULL,0,NULL)")
        files = self.root / 'files-demo'
        files.mkdir()
        (files / 'fixture.blob').write_bytes(b'fictional retained upload')
        # Use an empty isolated key root; never include the developer's private key in a test artifact.
        key_patch = patch('medplatform.linux_protection.KEY_ROOT', self.root / 'isolated-keys') if sys.platform == 'linux' else patch.object(lifecycle, '__version__', lifecycle.__version__)
        with key_patch:
            self.assertEqual(self.invoke('migrate', '--stopped', '--output', str(self.root / 'backups')), 0)
        self.assertEqual(status(self.db), 16)
        target = next((self.root / 'backups').iterdir())
        manifest = json.loads((target / 'manifest.json').read_text())
        self.assertEqual(manifest['schema_version'], '0014')
        for name, digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), digest)
        with closing(sqlite3.connect(target / 'database.sqlite3')) as conn:
            self.assertEqual(conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0], 14)
            self.assertEqual(conn.execute('SELECT display_name FROM o_accounts').fetchone()[0], '虚构保留对象')
        with self.db.connection(readonly=True) as conn:
            self.assertEqual(conn.execute('SELECT display_name FROM o_accounts').fetchone()[0], '虚构保留对象')
        self.assertEqual((target / 'files-demo/fixture.blob').read_bytes(), b'fictional retained upload')
        if os.name != 'nt':
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual((target / 'database.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_backup_closes_destination_on_success_and_integrity_error(self):
        migrate(self.db, initialize=True, target=14)
        connect = sqlite3.connect
        for fail in (False, True):
            with self.subTest(integrity_error=fail):
                opened = []

                class TrackedConnection(sqlite3.Connection):
                    closed = False

                    def execute(self, sql, *args):
                        if fail and sql == 'PRAGMA integrity_check':
                            raise sqlite3.DatabaseError('controlled integrity error')
                        return super().execute(sql, *args)

                    def close(self):
                        self.closed = True
                        return super().close()

                def tracked_connect(*args, **kwargs):
                    conn = connect(*args, **(kwargs | {'factory': TrackedConnection}))
                    opened.append(conn)
                    return conn

                with patch.object(lifecycle.sqlite3, 'connect', side_effect=tracked_connect):
                    if fail:
                        with self.assertRaisesRegex(sqlite3.DatabaseError, 'controlled integrity error'):
                            lifecycle.backup(self.db, directory=self.root / 'close-checks')
                    else:
                        lifecycle.backup(self.db, directory=self.root / 'close-checks')
                self.assertGreaterEqual(len(opened), 2)
                self.assertTrue(all(conn.closed for conn in opened))

    def test_backup_rejects_substituted_upload_link_before_migration(self):
        if os.name == 'nt':
            self.skipTest('Unprivileged symbolic-link creation not guaranteed on Windows')
        migrate(self.db, initialize=True, target=14)
        (self.root / 'files-demo').symlink_to(self.root, target_is_directory=True)
        before = self.db.path.read_bytes()
        self.assertEqual(self.invoke('migrate', '--stopped', '--output', str(self.root / 'backups')), 2)
        self.assertEqual(before, self.db.path.read_bytes())

    def test_inventory_matches_actual_registry_and_new_tables(self):
        import re
        from medplatform.config import Settings
        from medplatform.inventory import export
        from medplatform.web import create_app
        output = self.root / 'inventory'
        result = export(output)
        settings = Settings(_env_file=None, DATABASE_PATH=self.db.path)
        app = create_app(settings)
        routes = json.loads((output / 'interface-manifest.json').read_text())['routes']
        self.assertEqual({(r['method'], re.sub(r'\{[^}]+\}', '{}', r['path'])) for r in routes}, app.state.registry.routes)
        self.assertEqual(result['registered_routes'], 154)
        tables = json.loads((output / 'storage-schema.json').read_text())['tables']
        self.assertIn('b_star_checkpoints', [t['name'] for t in tables])
        self.assertIn('b_rule_selection_history', [t['name'] for t in tables])
