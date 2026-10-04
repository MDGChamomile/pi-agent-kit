"""Absolute time bounds share one UTC range across search and recall."""
from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from test_session_recall import header, message, session_recall, write_session

session_search = session_recall.session_search


class TimeRangeTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)
    START = "2026-08-10T00:00:00Z"
    END = "2026-08-11T00:00:00Z"

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "record.jsonl"
        self.environment = patch.dict(os.environ, {"PI_SESSION_FILE": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def args(self, mode, *extra):
        common = ["--sessions-root", str(self.root), "--cwd", str(self.root)]
        if mode == "aggregate":
            return session_search.build_parser().parse_args([*common, *extra])
        return session_recall.build_parser().parse_args([
            mode, *common, "--term", "needle",
            *(["--include-evidence"] if mode == "recall" else []), *extra,
        ])

    def output(self, mode, *extra, now=None):
        args = self.args(mode, *extra)
        function = {"aggregate": session_search.aggregate, "find": session_recall.find_output,
                    "recall": session_recall.recall_output}[mode]
        return function(args, now or self.NOW)

    def write(self, timestamps):
        write_session(self.path, header("synthetic", self.root), [
            message(str(i), str(i - 1) if i else None, timestamp, "user", f"needle {i}")
            for i, timestamp in enumerate(timestamps)
        ])

    def test_bounds_offsets_fractional_seconds_and_one_sided_ranges(self):
        self.write(["2026-08-09T23:59:59.999999Z", self.START,
                    "2026-08-10T09:00:00.000001+09:00", self.END, None, "invalid"])
        for options, expected in [
            (["--since", self.START, "--until", self.END], 2),
            (["--since", "2026-08-10T09:00:00+09:00", "--until", self.END], 2),
            (["--since", "2026-08-10T00:00:00.000001Z", "--until", self.END], 1),
            (["--until", self.END], 3), (["--since", self.START], 3), ([], 6),
        ]:
            for mode in ("aggregate", "find", "recall"):
                with self.subTest(mode=mode, options=options):
                    result = self.output(mode, *options)
                    actual = (result["summary"]["entries_eligible"] if mode == "aggregate" else
                              result["candidates"][0]["matching_messages"] if mode == "find" else
                              result["summary"]["matching_messages"])
                    self.assertEqual(actual, expected)
        result = self.output("recall", "--since", self.START, "--until", self.END)
        self.assertEqual([item["evidence"] for window in result["results"] for item in window["messages"]],
                         ["needle 1", "needle 2"])
        self.assertEqual(result["scope"]["since"], self.START)
        self.assertEqual(result["scope"]["until"], self.END)

    def test_invalid_input_fails_before_discovery_without_echo(self):
        invalid = ["", "private-secret", "2026-08-10", "2026-08-10T00:00:00",
                   "2026-08-10 00:00:00Z", "2026-08-10T00:00:00.1234567Z",
                   "2026-02-30T00:00:00Z", "2026-08-10T24:00:00Z",
                   "2026-08-10T00:00:00+00:60", "0001-01-01T00:00:00+01:00"]
        cases = [[flag, value] for flag in ("--since", "--until") for value in invalid]
        cases += [["--since", self.END, "--until", self.START],
                  ["--since", self.START, "--until", self.START],
                  ["--days", "0", "--since", self.START], ["--days", "1", "--until", self.END]]
        for mode in ("aggregate", "find", "recall"):
            for options in cases:
                with self.subTest(mode=mode, options=options):
                    argv = ([] if mode == "aggregate" else [mode, "--term", "needle"])
                    if mode == "recall":
                        argv.append("--include-evidence")
                    stdout = io.StringIO()
                    main = session_search.main if mode == "aggregate" else session_recall.main
                    with patch.object(session_search, "discover_session_files") as discover, redirect_stdout(stdout):
                        self.assertEqual(main([*argv, *options]), 2)
                    discover.assert_not_called()
                    result = json.loads(stdout.getvalue())
                    self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
                    self.assertNotIn("private-secret", stdout.getvalue())

    def test_days_keeps_future_records_and_reports_actual_lower_bound(self):
        self.write(["2026-08-13T00:00:00Z", "2026-08-14T00:00:00Z",
                    "2027-01-01T00:00:00Z", None, "invalid"])
        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode):
                result = self.output(mode, "--days", "1")
                self.assertEqual(result["scope"]["since"], "2026-08-14T00:00:00Z")
                self.assertIsNone(result["scope"]["until"])
                count = (result["summary"]["entries_eligible"] if mode == "aggregate" else
                         result["candidates"][0]["matching_messages"] if mode == "find" else
                         result["summary"]["matching_messages"])
                self.assertEqual(count, 2)

    def test_batch_matches_single_and_reads_body_once(self):
        self.write([self.START, self.END])
        options = ["--since", self.START, "--until", self.END]
        single = self.output("aggregate", *options)
        original_open = Path.open
        opened = []

        def counted(path, *args, **kwargs):
            if path == self.path:
                opened.append(path)
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", counted):
            batch = self.output("aggregate", *options, "--batch-filter", "{}", "--batch-filter", '{"role":["user"]}')
        self.assertEqual(len(opened), 1)
        self.assertEqual(batch["scope"], single["scope"])
        self.assertTrue(all(item["summary"] == single["summary"] for item in batch["batches"]))

    def test_prior_identity_and_call_survive_time_filter(self):
        write_session(self.path, header("synthetic", self.root), [
            message("1", None, "2026-08-01T00:00:00Z", "user",
                    '<skill name="declared" location="/custom/folder/SKILL.md">\n'
                    'References are relative to /custom/folder.\n\nbody\n</skill>'),
            message("2", "1", "2026-08-02T00:00:00Z", "assistant", [
                {"type": "toolCall", "id": "call", "name": "read",
                 "arguments": {"path": "/custom/folder/SKILL.md"}},
            ]),
            message("3", "2", self.START, "toolResult", "body",
                    toolName="read", toolCallId="call", isError=False),
        ])
        result = self.output("aggregate", "--since", self.START, "--until", self.END, "--skill", "declared")
        self.assertEqual(result["summary"]["skill_file_read_successes"], {"declared": 1})
        self.assertEqual(result["summary"]["skill_file_read_attempts"], {})

    def paged(self):
        self.write([f"2026-08-10T00:{i:02d}:00Z" for i in range(40)])

    def test_range_computed_once_and_reused_for_candidate_reread(self):
        self.paged()
        with patch.object(session_search, "time_range_for_args", wraps=session_search.time_range_for_args) as bounds:
            result = self.output("recall", "--since", self.START, "--until", self.END)
        bounds.assert_called_once()
        self.assertEqual(result["summary"]["matching_messages"], 40)

    def test_continuation_equivalent_offsets_and_fixed_time(self):
        self.paged()
        first = self.output("recall", "--since", self.START, "--until", self.END)
        second = self.output("recall", "--since", "2026-08-10T09:00:00+09:00", "--until", self.END,
                             "--continuation", first["next_continuation"], now=self.NOW + timedelta(days=30))
        self.assertEqual(second["scope"], first["scope"])
        self.assertIn("needle 15", json.dumps(second))
        for options in (["--since", "2026-08-10T00:01:00Z", "--until", self.END],
                        ["--since", self.START], ["--until", self.END], []):
            with self.subTest(options=options), patch.object(session_recall, "scan_candidates") as scan:
                with self.assertRaises(ValueError):
                    self.output("recall", *options, "--continuation", first["next_continuation"])
                scan.assert_not_called()

    def test_legacy_digest_and_days_reference_remain_compatible(self):
        self.paged()
        for options, days in (([], None), (["--days", "6"], 6.0)):
            first = self.output("recall", *options)
            token = first["next_continuation"]
            cursor = json.loads(base64.urlsafe_b64decode(token))
            old_scope = session_recall.continuation_digest({
                "roots": [str(self.root.resolve())], "cwd": str(self.root.resolve()), "all_projects": False,
                "include_current": False, "excluded_current": None, "days": days, "terms": ["needle"],
                "reference_time": self.NOW.isoformat(),
            })
            self.assertEqual(cursor[2], old_scope)
            second = self.output("recall", *options, "--continuation", token, now=self.NOW + timedelta(days=30))
            self.assertEqual(first["scope"], second["scope"])

    def test_out_of_range_change_still_invalidates_candidate(self):
        self.paged()
        options = ["--since", self.START, "--until", self.END]
        token = self.output("recall", *options)["next_continuation"]
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message("40", "39", self.END, "user", "not eligible")) + "\n")
        with self.assertRaises(session_recall.CandidateNotFoundError):
            self.output("recall", *options, "--continuation", token)


if __name__ == "__main__":
    unittest.main()
