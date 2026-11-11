"""CLI integration and mastery-rule tests. FSRS roundtrip runs if installed."""
import contextlib
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tutor_state as t


class TutorStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "study.json"
        self.run_cli("init", "--topic", "Concurrency", "--skill", "locks", "--skill", "race")

    def run_cli(self, *command):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            t.main(["--state", str(self.path), *command])
        return json.loads(out.getvalue())

    def test_initial_state_status_and_export(self):
        state = t.load(self.path)
        self.assertEqual(state["version"], 1)
        status = self.run_cli("status")
        self.assertEqual(status["topic"], "Concurrency")
        self.assertEqual(status["cards_total"], 0)
        self.assertEqual(status["skills"]["locks"]["level"], 0)
        self.assertTrue(status["skills"]["locks"]["provisional"])
        self.assertEqual(self.run_cli("export"), state)
        if sys.platform != "win32":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_init_does_not_overwrite(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrit"):
            self.run_cli("init", "--topic", "Replacement", "--skill", "new")
        self.assertEqual(before, self.path.read_bytes())

    def test_mastery_gates(self):
        self.run_cli("level", "--skill", "locks", "--value", "2", "--reason", "diagnostic only")
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.run_cli("level", "--skill", "locks", "--value", "3", "--reason", "too soon")
        self.run_cli("evidence", "--skill", "locks", "--check", "a", "--kind", "guided", "--result", "pass", "--note", "corrected with scaffold")
        self.run_cli("evidence", "--skill", "locks", "--check", "b", "--kind", "guided", "--result", "pass", "--note", "another case")
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.run_cli("level", "--skill", "locks", "--value", "3", "--reason", "only guided attempts")
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.run_cli("level", "--skill", "locks", "--value", "4", "--reason", "not independent")
        self.run_cli("evidence", "--skill", "locks", "--check", "c", "--kind", "independent", "--result", "pass", "--note", "new test case")
        self.run_cli("level", "--skill", "locks", "--value", "3", "--reason", "distinct checks including unaided retrieval")
        self.run_cli("evidence", "--skill", "locks", "--check", "d", "--kind", "delayed", "--result", "pass", "--note", "next day transfer")
        self.run_cli("level", "--skill", "locks", "--value", "4", "--reason", "independent transfer and delayed retrieval")
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.run_cli("level", "--skill", "locks", "--value", "5", "--reason", "not yet")
        self.run_cli("evidence", "--skill", "locks", "--check", "e", "--kind", "edge", "--result", "pass", "--note", "boundary analysis")
        self.run_cli("evidence", "--skill", "locks", "--check", "f", "--kind", "teach", "--result", "pass", "--note", "teaches limitation")
        result = self.run_cli("level", "--skill", "locks", "--value", "5", "--reason", "verified edge and teach back")
        self.assertEqual(result["skills"]["locks"]["level"], 5)
        self.assertFalse(result["skills"]["locks"]["provisional"])

    def test_duplicate_evidence_and_negative_checks(self):
        self.run_cli("evidence", "--skill", "race", "--check", "case1", "--kind", "independent", "--result", "fail", "--note", "wrong")
        with self.assertRaisesRegex(ValueError, "unique"):
            self.run_cli("evidence", "--skill", "race", "--check", "case1", "--kind", "independent", "--result", "pass", "--note", "retcon")
        self.run_cli("evidence", "--skill", "race", "--check", "case2", "--kind", "guided", "--result", "pass", "--note", "hinted success")
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            self.run_cli("level", "--skill", "race", "--value", "3", "--reason", "one success")

    def test_rejects_corrupted_state(self):
        self.path.write_text('{"version": 200, "topic": "X", "skills": {}, "cards": {}}')
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.run_cli("status")

    def test_missing_fsrs_leaves_state_unchanged(self):
        before = self.path.read_bytes()
        script = Path(t.__file__).resolve()
        result = subprocess.run(
            [sys.executable, "-S", str(script), "--state", str(self.path),
             "add-card", "--id", "card1", "--skill", "race", "--cue", "Explain a race"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("FSRS is unavailable", result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        result = subprocess.run(
            [sys.executable, "-S", str(script), "--state", str(self.path), "status"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["cards_total"], 0)

    @unittest.skipUnless(importlib.util.find_spec("fsrs"), "Py-FSRS is not installed locally")
    def test_fsrs_review_roundtrip(self):
        self.run_cli("add-card", "--id", "card1", "--skill", "race", "--cue", "Explain a race")
        status = self.run_cli("status")
        self.assertEqual(status["due"][0]["id"], "card1")
        before_review = datetime.now(timezone.utc)
        self.run_cli("review", "--id", "card1", "--rating", "good")
        data = t.load(self.path)
        self.assertEqual(len(data["reviews"]), 1)
        self.assertEqual(data["reviews"][0]["rating"], "good")
        from fsrs import Card
        self.assertIsInstance(Card.from_json(data["cards"]["card1"]["fsrs"]).due, datetime)
        card = Card.from_json(data["cards"]["card1"]["fsrs"])
        self.assertGreater(card.due, before_review)
        self.assertIsNotNone(card.stability)
        self.assertEqual(self.run_cli("status")["due"], [])
        self.assertEqual(data["skills"]["race"]["level"], 0)
        self.assertEqual(self.run_cli("export"), data)


if __name__ == "__main__":
    unittest.main()
