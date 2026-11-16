"""Run S03 native frontend logic cases with Node's built-in test runner."""
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "Node is required for frontend logic checks")
class S03FrontendRegressions(unittest.TestCase):
    def test_records_snapshots_and_explicit_execution(self):
        result = subprocess.run(
            [shutil.which("node"), "--test", "--test-reporter=tap",
             str(ROOT / "tests/test_s03_ui_async.cjs")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("# fail 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
