import json
import tempfile
import unittest
from pathlib import Path

from medplatform.__main__ import seed
from medplatform.core.database import Database
from medplatform.core.migrations import migrate
from medplatform.demo.story import PATIENT


class StoryTests(unittest.TestCase):
    def test_story_and_repeated_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "story.sqlite3")
            migrate(db, initialize=True)
            snapshots = []
            for _ in range(2):
                seed(db)
                with db.connection(readonly=True) as conn:
                    documents = [
                        json.loads(row[1])
                        for row in conn.execute(
                            "SELECT resource_type, document_json FROM s02_documents WHERE patient_id=? AND resource_type='Profile'",
                            (PATIENT,),
                        )
                    ]
                    counts = dict(
                        conn.execute(
                            "SELECT resource_type, count(*) FROM s02_documents WHERE patient_id=? AND resource_type IN ('Medication', 'PlanVersion') GROUP BY resource_type",
                            (PATIENT,),
                        )
                    )
                    reasons = [
                        json.loads(row[0]).get("missed_reason")
                        for row in conn.execute(
                            "SELECT original_payload_json FROM source_events WHERE patient_id=?",
                            (PATIENT,),
                        )
                    ]
                    sessions = conn.execute(
                        "SELECT count(*) FROM b_sessions WHERE patient_id=?", (PATIENT,)
                    ).fetchone()[0]
                    messages = conn.execute(
                        "SELECT count(*) FROM b_messages WHERE patient_id=? AND source_message_id IS NOT NULL",
                        (PATIENT,),
                    ).fetchone()[0]
                self.assertEqual(counts, {"Medication": 3, "PlanVersion": 1})
                self.assertCountEqual(
                    [reason for reason in reasons if reason],
                    ["forgot", "not_with_me", "unwell_or_side_effects"],
                )
                self.assertEqual(len(documents), 1)
                cards = documents[0]["cards"]
                self.assertEqual(len(cards), 6)
                self.assertEqual(
                    next(card for card in cards if card["question_id"] == "Q2")[
                        "level"
                    ],
                    "neutral",
                )
                self.assertEqual((sessions, messages), (2, 5))
                snapshots.append((counts, reasons, cards, sessions, messages))
            self.assertEqual(snapshots[0], snapshots[1])
