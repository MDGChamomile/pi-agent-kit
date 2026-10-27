"""Tool-event refactoring preserves payloads and serialization boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_nested_calls import nested_entry
from support import header, message, session_search, write_session


class ToolEventTests(unittest.TestCase):
    def test_direct_and_nested_event_shapes_keep_metadata_and_skill_identity(self):
        session = {"session_id": "session", "file": "session.jsonl"}
        for read_skill in (None, "alpha"):
            name = "read" if read_skill else "bash"
            arguments = {"path": "/skills/alpha/SKILL.md"} if read_skill else {"command": "echo marker"}
            arguments_text = '{"path": "/skills/alpha/SKILL.md"}' if read_skill else '{"command": "echo marker"}'
            for status in ("ok", "error"):
                for on_leaf in (None, False, True):
                    with self.subTest(skill=read_skill, status=status, on_leaf=on_leaf):
                        call = {"type": "toolCall", "id": "tool", "name": name, "arguments": arguments}
                        direct = message("call", None, "2026-09-29T00:00:00Z", "assistant", [call])
                        result = message("result", "call", "2026-09-29T00:00:00Z", "toolResult", "result text",
                                         toolCallId="tool", toolName=name, isError=status == "error")
                        nested = nested_entry([{**call, "status": status, "error": "result text"}])
                        direct_events = session_search.events_for_entry(direct, session, on_leaf)
                        result_events = session_search.events_for_entry(
                            result, session, on_leaf, {"tool": read_skill} if read_skill else {},
                        )
                        nested_events = session_search.events_for_entry(nested, session, on_leaf)
                        call_kind = "skill_file_read" if read_skill else "tool_call"
                        result_kind = "tool_error" if status == "error" else "tool_result"
                        cases = [
                            (direct_events[0], "call", "assistant", call_kind, arguments_text, False),
                            (result_events[0], "result", "toolResult", result_kind, "result text", status == "error"),
                            (nested_events[1], "result", "toolResult", call_kind, arguments_text, False),
                            (nested_events[2], "result", "toolResult", result_kind, "result text", status == "error"),
                        ]
                        for event, entry_id, role, kind, text, is_error in cases:
                            self.assertEqual(event, {
                                **session, "timestamp": "2026-09-29T00:00:00Z", "entry_id": entry_id,
                                "role": role, "on_latest_leaf": on_leaf,
                                "event": kind, "tool_name": name, "is_error": is_error,
                                "skill_names": [read_skill] if read_skill else [], "direct_skills": [],
                                "skill_file_read": read_skill,
                                "searchable": name + "\n" + text + ("\nalpha" if read_skill else ""),
                                "evidence_raw": text,
                            })

    def test_argument_shapes_keep_direct_and_nested_serialization_differences(self):
        cases = [
            ({}, "{}", ""),  # Missing arguments differ from an explicitly recorded object.
            ({"arguments": {}}, "{}", "{}"),
            ({"arguments": {"z": 1, "a": "한글"}}, '{"a": "한글", "z": 1}', '{"a": "한글", "z": 1}'),
            ({"arguments": None}, "null", ""),
            ({"arguments": ["raw"]}, '["raw"]', ""),
            ({"arguments": "raw"}, '"raw"', ""),
        ]
        for fields, direct_text, nested_text in cases:
            with self.subTest(fields=fields):
                call = {"type": "toolCall", "id": "inner", "name": "bash", "status": "unfinished", **fields}
                direct = message("call", None, "2026-09-29T00:00:00Z", "assistant", [call])
                for entry, index, expected in [(direct, 0, direct_text), (nested_entry([call]), 1, nested_text)]:
                    event = session_search.events_for_entry(entry, {}, True)[index]
                    self.assertEqual(event["evidence_raw"], expected)
                    self.assertEqual(event["searchable"], "bash" + ("\n" + expected if expected else ""))

    def test_argument_omission_skips_serialization_but_keeps_skill_identity(self):
        call = {"type": "toolCall", "id": "inner", "name": "read",
                "arguments": {"path": "/skills/alpha/SKILL.md"}, "status": "unfinished"}
        direct = message("call", None, "2026-09-29T00:00:00Z", "assistant", [call])
        with patch.object(session_search.json, "dumps", side_effect=AssertionError("serialized")):
            for entry, index in [(direct, 0), (nested_entry([call]), 1)]:
                event = session_search.events_for_entry(entry, {}, True, include_arguments=False)[index]
                self.assertEqual(event["evidence_raw"], "")
                self.assertEqual(event["searchable"], "read\nalpha")
                self.assertEqual(event["skill_file_read"], "alpha")

    def test_quoted_argument_values_are_masked_without_changing_search_matches(self):
        commands = (
            'echo password="SYNTHETIC FIRST SECOND"',
            "echo passwd='SYNTHETIC FIRST SECOND'",
            r'echo secret="SYNTHETIC\" SECOND"',
            'echo token="SYNTHETIC\nSECOND"',
            'echo {"password": "SYNTHETIC FIRST SECOND"}',
            'Cookie: session=SYNTHETIC_A; sid=SYNTHETIC_B\nVisible: marker',
        )
        for command in commands:
            for nested in (False, True):
                with self.subTest(command=command, nested=nested), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    call = {"type": "toolCall", "id": "inner", "name": "bash", "status": "unfinished",
                            "arguments": {"options": [{"command": command}], "token": "SYNTHETIC_FIELD"}}
                    entry = (nested_entry([call]) if nested else
                             message("call", None, "2026-09-29T00:00:00Z", "assistant", [call]))
                    path = root / "session.jsonl"
                    write_session(path, header("session", root), [entry])
                    before = path.read_bytes()
                    flags = ["--sessions-root", temp, "--cwd", temp, "--tool", "bash", "--query", "SYNTHETIC"]
                    for evidence in (False, True):
                        args = session_search.build_parser().parse_args(flags + (["--include-evidence"] if evidence else []))
                        result = session_search.aggregate(args)
                        self.assertEqual(result["summary"]["matched_events"], 1)
                        self.assertNotIn("SYNTHETIC", json.dumps(result))
                        if evidence:
                            self.assertIn("[REDACTED]", result["results"][0]["evidence"])
                        else:
                            self.assertEqual(result["results"], [])
                    self.assertEqual(path.read_bytes(), before)

    def test_cli_masks_quoted_direct_and_nested_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            call = {"type": "toolCall", "id": "inner", "name": "bash", "status": "unfinished",
                    "arguments": {"command": 'echo password="SYNTHETIC FIRST SECOND"'}}
            write_session(root / "session.jsonl", header("session", root), [
                message("call", None, "2026-09-29T00:00:00Z", "assistant", [call]),
                nested_entry([call]),
            ])
            for evidence in (False, True):
                completed = subprocess.run(
                    [sys.executable, "-B", session_search.__file__, "--sessions-root", temp, "--cwd", temp,
                     "--tool", "bash", "--query", "SYNTHETIC", *(["--include-evidence"] if evidence else [])],
                    capture_output=True, text=True, env={**os.environ, "PI_SESSION_FILE": ""},
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result = json.loads(completed.stdout)
                self.assertEqual(result["summary"]["tool_calls"], {"bash": 2})
                self.assertNotIn("SYNTHETIC", completed.stdout)
                self.assertEqual(len(result["results"]), 2 if evidence else 0)

    def test_nested_argument_query_is_searchable_and_evidence_is_opt_in_and_masked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outer = message("call", None, "2026-09-29T00:00:00Z", "assistant", [
                {"type": "toolCall", "id": "outer", "name": "codemode", "arguments": {}},
            ])
            nested = nested_entry([{"id": "inner", "name": "bash", "status": "ok",
                                    "arguments": {"command": "nested-marker", "token": "SYNTHETIC_SECRET"}}])
            write_session(root / "session.jsonl", header("session", root), [outer, nested])
            flags = ["--sessions-root", temp, "--cwd", temp, "--query", "nested-marker", "--tool", "bash"]
            for evidence in (False, True):
                with self.subTest(evidence=evidence):
                    args = session_search.build_parser().parse_args(flags + (["--include-evidence"] if evidence else []))
                    result = session_search.aggregate(args)
                    self.assertEqual(result["summary"]["matched_events"], 1)
                    self.assertEqual(result["summary"]["tool_calls"], {"bash": 1})
                    self.assertNotIn("SYNTHETIC_SECRET", json.dumps(result))
                    if evidence:
                        self.assertEqual(len(result["results"]), 1)
                        self.assertIn("nested-marker", result["results"][0]["evidence"])
                        self.assertIn("[REDACTED]", result["results"][0]["evidence"])
                    else:
                        self.assertEqual(result["results"], [])
