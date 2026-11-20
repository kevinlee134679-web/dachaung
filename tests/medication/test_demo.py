import tempfile
import unittest
from pathlib import Path

from medplatform.core.config import ROOT
from medplatform.demo.medication import generate


class MedicationDemoTests(unittest.TestCase):
    def test_isolated_fixture_replays_late_source_without_duplicate(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "test-output") as directory:
            path = Path(directory) / "scenario.sqlite3"
            before = generate(path)
            self.assertEqual(
                (before["patient_confirmed_count"], before["planned_dose_count"]),
                (10, 14),
            )
            self.assertEqual(before["delivery_status"], "submitted")
            raw = path.read_bytes()
            with self.assertRaises(ValueError):
                generate(path)
            self.assertEqual(raw, path.read_bytes())
            after = generate(path, add_late_report=True)
            replay = generate(path, add_late_report=True)
            self.assertEqual(after["patient_confirmation_ratio"], 11 / 14)
            self.assertEqual(replay["patient_confirmed_count"], 11)
            self.assertNotEqual(before["statistics_id"], after["statistics_id"])

    def test_fixture_refuses_a_normal_runtime_location(self):
        with self.assertRaises(ValueError):
            generate(ROOT / "var" / "do-not-create.sqlite3")
        self.assertFalse((ROOT / "var" / "do-not-create.sqlite3").exists())
