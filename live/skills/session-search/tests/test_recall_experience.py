"""Check retrieval boundaries, not whether a model interprets them correctly."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from experience_fixtures import CASES, write_cases
from support import cli_args, session_recall


class RecallExperienceTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root = base / "sessions"
        self.project = base / "project"
        self.project.mkdir()
        write_cases(self.root, self.project)

    def args(self, mode, terms):
        return cli_args(mode, self.root, self.project, terms=terms)

    def recall(self, terms):
        found = session_recall.find_output(self.args("find", terms), self.NOW)
        self.assertEqual(found["summary"]["matched_sessions"], 1)
        self.assertEqual(found["results"], [])
        metadata = json.dumps(found, ensure_ascii=False)
        for private in (str(self.root), str(self.project), *CASES, *terms):
            self.assertNotIn(private, metadata)
        return session_recall.recall_output(self.args("recall", terms), self.NOW)

    def evidence(self, output):
        return "\n".join(item["evidence"] for window in output["results"]
                         for item in window["messages"])

    def test_revised_hypothesis_and_recorded_outcome_are_both_retrievable(self):
        output = self.recall(CASES["revised-hypothesis"]["terms"])
        evidence = self.evidence(output)
        self.assertIn("Initial hypothesis", evidence)
        self.assertIn("Rejected that hypothesis", evidence)
        self.assertIn("middleware order was the cause", evidence)
        self.assertIn("according to the smoke check report", evidence)

    def test_claimed_verification_does_not_expose_actual_tool_result(self):
        output = self.recall(CASES["claimed-verification"]["terms"])
        self.assertIn("all tests passed", self.evidence(output))
        self.assertNotIn("SYNTHETIC_TEST_OUTPUT", json.dumps(output))
        self.assertEqual({item["role"] for window in output["results"]
                          for item in window["messages"]}, {"user", "assistant"})
        self.assertIsNone(output["next_continuation"])

    def test_cause_term_research_can_find_an_outcome_outside_symptom_window(self):
        case = CASES["distant-outcome"]
        initial = self.recall(case["terms"])
        self.assertIn("route wiring", self.evidence(initial))
        self.assertNotIn("reported successful", self.evidence(initial))
        self.assertGreater(initial["results"][-1]["messages_omitted_after"], 0)
        self.assertIsNone(initial["next_continuation"])
        followup = self.recall(case["followup_terms"])
        self.assertIn("reported successful", self.evidence(followup))
        self.assertEqual(initial["scope"], followup["scope"])

    def test_final_page_can_hide_outcome_inside_a_shortened_message(self):
        case = CASES["truncated-outcome"]
        initial = self.recall(case["terms"])
        for term in case["followup_terms"]:
            self.assertNotIn(term, self.evidence(initial))
        assistant = next(item for window in initial["results"]
                         for item in window["messages"] if item["role"] == "assistant")
        self.assertTrue(assistant["text_truncated"])
        self.assertLessEqual(len(assistant["evidence"]), session_recall.MAX_MESSAGE_CHARS)
        self.assertFalse(initial["summary"]["evidence_truncated"])
        self.assertIsNone(initial["next_continuation"])
        # A separately supplied cause term can retrieve the ending; it is NOT
        # discoverable from the first excerpt and must not be invented by an agent.
        followup = self.recall(case["followup_terms"])
        self.assertIn("Confirmed queue binding issue", self.evidence(followup))
        self.assertIn("reported a passing smoke check", self.evidence(followup))


if __name__ == "__main__":
    unittest.main()
