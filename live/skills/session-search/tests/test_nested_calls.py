from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_session_search import header, message, session_search, write_session


def nested_entry(calls, complete=True):
    return message(
        "result", "call", "2026-09-29T00:00:00Z", "toolResult", [],
        toolCallId="outer", toolName="codemode", isError=False,
        nestedCalls={"calls": calls, "complete": complete},
    )


class NestedCallTests(unittest.TestCase):
    def test_nested_skill_attempt_and_error_without_parent_error(self):
        call = {"id": "inner", "name": "read", "arguments": {"path": "/skills/alpha/SKILL.md"},
                "status": "error", "error": "permission denied"}
        events = session_search.events_for_entry(nested_entry([call]), {}, True)
        self.assertEqual([(e["event"], e["tool_name"], e["is_error"]) for e in events], [
            ("tool_result", "codemode", False),
            ("skill_file_read", "read", False),
            ("tool_error", "read", True),
        ])
        self.assertEqual(events[-1]["skill_file_read"], "alpha")
        self.assertIn("permission denied", events[-1]["searchable"])

    def test_success_uses_recorded_skill_identity_and_cwd(self):
        call = {"id": "inner", "name": "read", "arguments": {"path": "custom/SKILL.md"}, "status": "ok"}
        events = session_search.events_for_entry(
            nested_entry([call]), {}, True, names_by_path={"/project/custom/SKILL.md": "declared"}, cwd="/project",
        )
        self.assertEqual([e["skill_file_read"] for e in events[1:]], ["declared", "declared"])
        self.assertEqual(events[-1]["event"], "tool_result")

    def test_unfinished_omitted_arguments_and_duplicate_ids(self):
        call = {"id": "inner", "name": "read", "argumentsBytes": 100000, "status": "unfinished"}
        events = session_search.events_for_entry(nested_entry([call, call, None, {"status": "bad"}], False), {}, True)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1]["event"], "tool_call")
        self.assertIsNone(events[-1]["skill_file_read"])
        self.assertFalse(events[-1]["is_error"])

    def test_aggregate_counts_direct_and_nested_calls_once_and_warns(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = [message("call", None, "2026-09-29T00:00:00Z", "assistant", [
                {"type": "toolCall", "id": "outer", "name": "codemode", "arguments": {}},
            ]), nested_entry([
                {"id": "read", "name": "read", "arguments": {"path": "/skills/alpha/SKILL.md"}, "status": "ok"},
                {"id": "bash", "name": "bash", "arguments": {"command": "false"}, "status": "error", "error": "token=PRIVATE_SECRET"},
                {"id": "pending", "name": "write", "status": "unfinished"},
            ], False)]
            write_session(root / "test.jsonl", header("private-session", root), entries)
            args = session_search.build_parser().parse_args(["--sessions-root", temp, "--cwd", temp])
            result = session_search.aggregate(args)
            summary = result["summary"]
            self.assertEqual(summary["tool_calls"], {"bash": 1, "codemode": 1, "read": 1, "write": 1})
            self.assertEqual(summary["tool_errors"], {"bash": 1})
            self.assertEqual(summary["tool_error_sessions"], {"bash": 1})
            self.assertEqual(summary["skill_file_read_attempts"], {"alpha": 1})
            self.assertEqual(summary["skill_file_read_successes"], {"alpha": 1})
            self.assertIn("incomplete_nested_calls", json.dumps(result["warnings"]))
            self.assertEqual(result["results"], [])
            self.assertNotIn("PRIVATE_SECRET", json.dumps(result))

    def test_nested_error_evidence_is_masked(self):
        entry = nested_entry([{"id": "inner", "name": "bash", "status": "error", "error": "token=PRIVATE_SECRET"}])
        events = session_search.events_for_entry(entry, {"file": "synthetic", "session_id": "synthetic"}, True)
        evidence = session_search.result_view(events[-1], [])
        self.assertNotIn("PRIVATE_SECRET", json.dumps(evidence))


if __name__ == "__main__":
    unittest.main()
