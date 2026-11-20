"""Real loopback HTTP, explicit CLI migration, and graceful server shutdown."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

import uvicorn

from medplatform.core.config import ROOT, Settings
from medplatform.core.database import Database
from medplatform.core.migrations import catalog, migrate
from medplatform.web.app import create_app

CLI_TIMEOUT = 60  # Fresh interpreters register all routes, including on emulated Linux.


class HttpLifecycleTests(unittest.TestCase):
    def test_loopback_cli_and_graceful_shutdown(self):
        parent = ROOT / "test-output"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as td:
            db = Path(td) / "demo.sqlite3"
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env = {
                **os.environ,
                "DATABASE_PATH": str(db),
                "PORT": str(port),
                "APP_ENV": "test",
                "AUTH_MODE": "demo",
                "LLM_MODE": "mock",
                "PYTHONUTF8": "1",
            }

            def cli(*args):
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", "-m", "medplatform", *args],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    timeout=CLI_TIMEOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout.splitlines()[-1])

            # A separate interpreter import/factory must not create the database.
            imported = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-c",
                    "from medplatform.web.app import create_app; create_app()",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                timeout=CLI_TIMEOUT,
                check=False,
            )
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertFalse(db.exists())
            settings = Settings(
                _env_file=None, DATABASE_PATH=db, PORT=port, APP_ENV="test"
            )
            static = Path(td) / "static"
            static.mkdir()
            (static / "index.html").write_text(
                '<script type="module" src="/static/assets/app.js"></script>'
            )
            self.enterContext(patch("medplatform.web.app.STATIC", static))
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(settings),
                    host="127.0.0.1",
                    port=port,
                    access_log=False,
                    log_level="critical",
                )
            )
            worker = threading.Thread(target=server.run, daemon=True)
            worker.start()
            opener = build_opener(ProxyHandler({}))
            base = f"http://127.0.0.1:{port}"
            try:
                deadline = time.monotonic() + 10
                while not server.started and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(server.started)
                with self.assertRaises(HTTPError) as unavailable:
                    opener.open(base + "/api/v1/health", timeout=3)
                self.assertEqual(unavailable.exception.code, 503)
                unavailable.exception.close()
                self.assertFalse(db.exists())
                self.assertEqual(migrate(Database(db), initialize=True, target=1), 1)
                with self.assertRaises(HTTPError) as old:
                    opener.open(base + "/api/v1/health", timeout=3)
                self.assertEqual(old.exception.code, 503)
                old.exception.close()
                self.assertEqual(
                    cli("migrate", "--stopped", "--output", str(Path(td) / "backups"))[
                        "schema_version"
                    ],
                    f"{len(catalog()):04d}",
                )
                self.assertEqual(
                    cli("status")["schema_version"], f"{len(catalog()):04d}"
                )
                with opener.open(base + "/api/v1/health", timeout=3) as response:
                    data = json.load(response)
                    self.assertEqual(response.status, 200)
                    self.assertEqual(data["data"]["readiness"], "ready")
                    self.assertEqual(
                        data["request_id"], response.headers["X-Request-ID"]
                    )
                with opener.open(base + "/", timeout=3) as response:
                    self.assertIn(b"/static/assets/app.js", response.read())
            finally:
                server.should_exit = True
                worker.join(10)
            self.assertFalse(worker.is_alive(), "server did not shut down gracefully")
            renamed = db.with_name("closed.sqlite3")
            db.rename(
                renamed
            )  # No retained connection/Windows file lock after shutdown.
            self.assertTrue(renamed.exists())
