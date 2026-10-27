"""Stored JSON edge cases must not become argument errors or break UTF-8 output."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from support import RECALL_SCRIPT, SEARCH_SCRIPT, header, message, session_recall, session_search, write_session

STAMP = "2026-08-14T00:00:00Z"
# The C JSON decoder can accept depths above Python's recursion limit.
DEEP_JSON_VALUE = "[" * 10000 + "]" * 10000


def json_depth_is_limited():
    try:
        json.loads('{"value":' + DEEP_JSON_VALUE + '}')
    except RecursionError:
        return True
    return False


class JsonBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "sessions"
        self.project = self.base / "project"
        self.project.mkdir()
        self.path = self.root / "record.jsonl"

    def write(self, entries):
        write_session(self.path, header("synthetic", self.project), entries)

    def run_cli(self, mode, *extra):
        command = [sys.executable, str(SEARCH_SCRIPT)] if mode == "aggregate" else [
            sys.executable, str(RECALL_SCRIPT), mode, "--term", "needle",
        ]
        command += ["--sessions-root", str(self.root)]
        if "--all-projects" not in extra:
            command += ["--cwd", str(self.project)]
        if mode != "find":
            command += ["--include-evidence"]
        command += list(extra)
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env={
            **os.environ, "PYTHONIOENCODING": "utf-8:strict", "PYTHONINTMAXSTRDIGITS": "640",
            "PI_SESSION_FILE": str(self.base / "synthetic-current.jsonl"),
        })
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(completed.stderr, "")
        return json.loads(completed.stdout), completed.stdout

    def test_aggregate_and_recall_emit_surrogate_text_without_losing_unicode(self):
        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode):
                self.write([message("0", None, STAMP, "user", 'needle 한글 😀 \ud800 password="SYNTHETIC"')])
                output, raw = self.run_cli(mode)
                self.assertEqual(output["status"], "ok")
                self.assertEqual(output["summary"]["matched_sessions"], 1)
                self.assertNotIn("SYNTHETIC", raw)
                if mode == "find":
                    self.assertEqual(output["results"], [])
                    self.assertNotIn("한글", raw)
                else:
                    self.assertIn("한글 😀", raw)
                    self.assertIn("\\ud800", raw)
                    self.assertIn("\ud800", json.dumps(output, ensure_ascii=False))

    def test_aggregate_tool_argument_surrogates_remain_masked_and_serializable(self):
        self.write([message("0", None, STAMP, "assistant", [
            {"type": "toolCall", "id": "call", "name": "bash",
             "arguments": {"command": 'echo needle \udfff password="SYNTHETIC"'}},
        ])])
        output, raw = self.run_cli("aggregate")
        self.assertEqual(output["summary"]["matched_events"], 1)
        self.assertNotIn("SYNTHETIC", raw)
        self.assertIn("\\udfff", raw)

    def test_recall_continuation_round_trips_surrogate_messages(self):
        self.write([
            message(str(i), str(i - 1) if i else None, STAMP, "user",
                    f"needle match-{i} \ud800" if i % 6 == 2 else f"context-{i}")
            for i in range(24)
        ])
        first, _ = self.run_cli("recall")
        self.assertIsNotNone(first["next_continuation"])
        second, _ = self.run_cli("recall", "--continuation", first["next_continuation"])
        self.assertIsNone(second["next_continuation"])
        matches = [item["evidence"] for page in (first, second)
                   for window in page["results"] for item in window["messages"] if item["matches_term"]]
        self.assertEqual(matches, [f"needle match-{i} \ud800" for i in (2, 8, 14, 20)])

    def test_json_emission_round_trips_surrogates_and_literal_escapes(self):
        value = {"unicode": "한글 😀", "edge": "\ud800 middle \udfff", "literal": "\\ud800"}
        with redirect_stdout(io.StringIO()) as output:
            session_search.emit_json(value)
        self.assertEqual(json.loads(output.getvalue()), value)
        output.getvalue().encode("utf-8", "strict")
        self.assertIn("한글 😀", output.getvalue())

    def test_fingerprints_distinguish_surrogates_from_replacement_and_literal_text(self):
        texts = ("\ud800", "\ud801", "\udfff", "\ufffd", "\\ud800")
        fingerprints = {
            session_recall.message_fingerprint([session_recall.RecallMessage("0", STAMP, "user", text)])
            for text in texts
        }
        self.assertEqual(len(fingerprints), len(texts))
        self.assertEqual(len({session_recall.continuation_digest(text) for text in texts}), len(texts))

    def test_existing_unicode_fingerprints_and_continuation_digests_are_unchanged(self):
        text = "한글 😀"
        encoded = json.dumps(["0", STAMP, "user", text], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        expected = hashlib.sha256(len(encoded).to_bytes(8, "big") + encoded).hexdigest()
        self.assertEqual(session_recall.message_fingerprint([
            session_recall.RecallMessage("0", STAMP, "user", text),
        ]), expected)
        expected = hashlib.sha256(json.dumps(text, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(session_recall.continuation_digest(text), expected)

    def assert_body_value_is_isolated(self, value, *, rejected=True):
        self.write([message("0", None, STAMP, "user", "needle valid")])
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write('{"type":"custom","id":"oversized","parentId":"0","value":' + value + '}\n')
        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode):
                output, _ = self.run_cli(mode)
                self.assertEqual(output["status"], "ok")
                self.assertEqual(output["summary"]["matched_sessions"], 1)
                self.assertEqual(output["warnings"]["by_kind"], {"invalid_json_line": 1} if rejected else {})

    def assert_header_value_is_isolated(self, value, *, rejected=True):
        self.write([message("0", None, STAMP, "user", "needle valid")])
        broken = json.dumps(header("broken", self.project))[:-1] + ',"value":' + value + '}\n'
        (self.root / "broken.jsonl").write_text(broken, encoding="utf-8")
        for mode in ("aggregate", "find", "recall"):
            for all_projects in (False, True):
                with self.subTest(mode=mode, all_projects=all_projects):
                    output, _ = self.run_cli(mode, *(["--all-projects"] if all_projects else []))
                    self.assertEqual(output["status"], "ok")
                    self.assertEqual(output["summary"]["matched_sessions"], 1)
                    self.assertEqual(output["warnings"]["by_kind"],
                                     {"invalid_header": 1} if all_projects and rejected else {})

    @unittest.skipUnless(hasattr(sys, "get_int_max_str_digits"), "Python has no integer-conversion limit")
    def test_oversized_body_integer_is_a_row_warning_in_every_mode(self):
        self.assert_body_value_is_isolated("9" * 5000)

    @unittest.skipUnless(hasattr(sys, "get_int_max_str_digits"), "Python has no integer-conversion limit")
    def test_oversized_header_integer_is_skipped_without_disclosing_unknown_scope(self):
        self.assert_header_value_is_isolated("9" * 5000)

    def test_deeply_nested_body_follows_decoder_limits(self):
        self.assert_body_value_is_isolated(DEEP_JSON_VALUE, rejected=json_depth_is_limited())

    def test_deeply_nested_header_follows_decoder_limits(self):
        self.assert_header_value_is_isolated(DEEP_JSON_VALUE, rejected=json_depth_is_limited())

    def test_accepted_nested_values_are_not_reported_as_invalid(self):
        self.assert_body_value_is_isolated("[[0]]", rejected=False)
        self.assert_header_value_is_isolated("[[0]]", rejected=False)

    def test_parser_limits_are_local_but_utf8_decode_errors_propagate(self):
        for error_type in (ValueError, RecursionError):
            with self.subTest(error_type=error_type):
                warnings = session_search.WarningCollector()
                with patch.object(session_search.json, "loads", side_effect=error_type("synthetic parse limit")):
                    self.assertIsNone(session_search.read_session_header(io.BytesIO(b"{}\n")))
                    self.assertEqual(list(session_search.read_session_entries(io.BytesIO(b"{}\n"), self.path, warnings)), [])
                self.assertEqual(warnings.output(False)["by_kind"], {"invalid_json_line": 1})
        with self.assertRaises(UnicodeDecodeError):
            session_search.read_session_header(io.BytesIO(b"\xff\n"))
        with self.assertRaises(UnicodeDecodeError):
            list(session_search.read_session_entries(io.BytesIO(b"\xff\n"), self.path, warnings))
