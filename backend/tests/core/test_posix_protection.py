"""Linux protection and failure boundaries; Windows continues native DPAPI."""

import base64
import os
import secrets
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from medplatform.core.errors import AppError
from medplatform.core.protection import protect, unprotect


@unittest.skipUnless(os.name == "posix", "POSIX filesystem protection backend")
class LinuxProtectionTests(unittest.TestCase):
    def setUp(self):
        from medplatform.core import posix_protection as linux_protection

        self.backend = linux_protection
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "keys"
        self.patch = patch.object(linux_protection, "KEY_ROOT", self.directory)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.key = self.directory / f"uid-{os.getuid()}" / linux_protection.KEY_FILE
        self.payload = b"fictional sensitive receipt: preserve across processes"

    def unavailable(self, action):
        with self.assertRaises(AppError) as caught:
            action()
        self.assertEqual(caught.exception.status, 503)
        self.assertEqual(caught.exception.code, "SENSITIVE_RECEIPT_UNAVAILABLE")
        self.assertNotIn(str(self.directory), caught.exception.message)

    def test_ciphertext_is_randomized_and_bound_to_context(self):
        first = protect(self.payload, "session:one")
        second = protect(self.payload, "session:one")
        self.assertNotEqual(first, second)
        self.assertNotIn(self.payload, first)
        self.assertEqual(unprotect(first, "session:one"), self.payload)
        self.unavailable(lambda: unprotect(first, "receipt:one"))

    def test_modified_truncated_and_foreign_ciphertexts_are_rejected(self):
        good = protect(self.payload, "receipt:one")
        for bad in (good[:-1], good[:-1] + bytes([good[-1] ^ 1]), b"legacy-dpapi", b""):
            with self.subTest(size=len(bad)):
                self.unavailable(lambda: unprotect(bad, "receipt:one"))  # noqa: B023
        self.assertEqual(unprotect(good, "receipt:one"), self.payload)

    def test_reads_without_original_key_do_not_initialize_storage(self):
        candidate = self.backend.PREFIX + bytes(12 + 16)
        self.unavailable(lambda: unprotect(candidate, "session:one"))
        self.assertFalse(self.directory.exists())

    def test_missing_key_is_not_replaced_by_reads_or_writes(self):
        good = protect(self.payload, "session:one")
        self.key.unlink()
        self.unavailable(lambda: unprotect(good, "session:one"))
        self.unavailable(lambda: protect(b"new login", "session:two"))
        self.assertFalse(self.key.exists())

    def test_changed_key_does_not_unlock_existing_ciphertext(self):
        good = protect(self.payload, "session:one")
        self.key.write_bytes(secrets.token_bytes(32))
        self.unavailable(lambda: unprotect(good, "session:one"))

    def test_key_and_directory_permissions_are_restricted(self):
        good = protect(self.payload, "session:one")
        self.assertEqual(self.key.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.key.chmod(0o644)
        self.unavailable(lambda: unprotect(good, "session:one"))
        self.unavailable(lambda: protect(self.payload, "session:two"))
        self.key.chmod(0o600)
        self.directory.chmod(0o755)
        self.unavailable(lambda: unprotect(good, "session:one"))

    def test_writable_parent_or_different_owner_is_rejected(self):
        good = protect(self.payload, "session:one")
        parent = self.directory.parent
        parent.chmod(0o777)
        try:
            self.unavailable(lambda: unprotect(good, "session:one"))
        finally:
            parent.chmod(0o700)
        owner = os.getuid()
        with patch.object(self.backend.os, "getuid", return_value=owner + 1):
            self.unavailable(lambda: unprotect(good, "session:one"))

    def test_symlink_and_hardlink_keys_are_rejected(self):
        good = protect(self.payload, "session:one")
        original = self.key.with_name("original-key")
        self.key.rename(original)
        self.key.symlink_to(original)
        self.unavailable(lambda: unprotect(good, "session:one"))
        self.key.unlink()
        os.link(original, self.key)
        self.unavailable(lambda: unprotect(good, "session:one"))

    def test_symlink_directory_is_rejected(self):
        good = protect(self.payload, "session:one")
        original = self.directory.with_name("original-directory")
        self.directory.rename(original)
        self.directory.symlink_to(original, target_is_directory=True)
        self.unavailable(lambda: unprotect(good, "session:one"))

    def test_malformed_keys_are_not_replaced(self):
        good = protect(self.payload, "session:one")
        for size in (0, 31, 33):
            self.key.write_bytes(bytes(size))
            with self.subTest(size=size):
                self.unavailable(lambda: unprotect(good, "session:one"))
                self.unavailable(lambda: protect(self.payload, "session:two"))
                self.assertEqual(self.key.stat().st_size, size)

    def test_parallel_process_initialization_and_restart_use_same_key(self):
        code = """import base64, sys
from pathlib import Path
from medplatform.core import posix_protection as linux_protection
from medplatform.core.protection import protect, unprotect
linux_protection.KEY_ROOT = Path(sys.argv[1])
if len(sys.argv) == 2:
    print(base64.b64encode(protect(b'fictional process payload', 'process-test')).decode())
else:
    assert unprotect(base64.b64decode(sys.argv[2]), 'process-test') == b'fictional process payload'
"""

        def run(_):
            return subprocess.check_output(
                [sys.executable, "-B", "-c", code, str(self.directory)], text=True
            ).strip()

        with ThreadPoolExecutor(max_workers=4) as workers:
            encrypted = list(workers.map(run, range(8)))
        self.assertEqual(len(set(encrypted)), 8)
        for value in encrypted:
            self.assertEqual(
                unprotect(base64.b64decode(value), "process-test"),
                b"fictional process payload",
            )
        subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.directory), encrypted[0]],
            check=True,
        )

    def test_unavailable_key_rolls_back_login_without_exposing_paths(self):
        from fastapi.testclient import TestClient

        from medplatform.core.config import Settings
        from medplatform.core.database import Database
        from medplatform.core.migrations import migrate
        from medplatform.identity.service import seed_demo
        from medplatform.web.app import create_app

        db = Database(Path(self.temp.name) / "demo.sqlite3")
        migrate(db, initialize=True)
        seed_demo(db)
        protect(self.payload, "session:one")
        self.key.unlink()
        with TestClient(
            create_app(Settings(_env_file=None, APP_ENV="test", DATABASE_PATH=db.path)),
            base_url="http://127.0.0.1:8000",
        ) as client:
            response = client.post(
                "/api/v1/auth/demo-session",
                json={"demo_account_id": "demo-patient-a"},
                headers={
                    "Origin": "http://127.0.0.1:8000",
                    "Idempotency-Key": str(uuid.uuid4()),
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"], "SENSITIVE_RECEIPT_UNAVAILABLE"
        )
        self.assertNotIn(str(self.directory), response.text)
        with db.connection(readonly=True) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM o_sessions").fetchone()[0], 0
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM idempotency_receipts"
                ).fetchone()[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()
