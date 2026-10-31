"""Shared scan mechanics must not absorb aggregate/recall policy decisions."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from support import cli_args, session_common, session_recall, session_search


class SharedScanTests(unittest.TestCase):
    def test_entries_skip_malformed_lines_without_changing_valid_payloads(self):
        entries = [{"id": "first", "message": {"content": "한글"}}, {}]
        lines = [json.dumps(entries[0]), "not-json", "[]", "null", "", json.dumps(entries[1])]
        warnings = session_common.WarningCollector()
        stream = io.BytesIO(("\n".join(lines) + "\n").encode("utf-8"))
        self.assertEqual(list(session_common.read_session_entries(stream, Path("session.jsonl"), warnings)), entries)
        self.assertEqual(warnings.output(False), {
            "count": 2, "by_kind": {"invalid_entry": 1, "invalid_json_line": 1},
        })

    def test_body_failures_propagate_after_preceding_entries(self):
        class FailingBody(io.BytesIO):
            def __next__(self):
                line = self.readline()
                if not line:
                    raise OSError("synthetic read failure")
                return line

        for stream, error in [(io.BytesIO(b'{}\n\xff\n'), UnicodeError),
                              (FailingBody(b'{}\n'), OSError)]:
            with self.subTest(error=error):
                warnings = session_common.WarningCollector()
                entries = session_common.read_session_entries(stream, Path("session.jsonl"), warnings)
                self.assertEqual(next(entries), {})
                with self.assertRaises(error):
                    next(entries)
                # The caller decides whether this file's failure is disclosed.
                self.assertEqual(warnings.count, 0)

    def test_exclusions_use_supplied_identity_and_current_overlap_precedence(self):
        with tempfile.TemporaryDirectory() as temp:
            current = session_common.normalized_path(Path(temp) / "current.jsonl")
            missing = session_common.normalized_path(Path(temp) / "missing.jsonl")
            explicit = session_common.normalized_path(Path(temp) / "explicit.jsonl")
            with patch.dict(os.environ, {"PI_SESSION_FILE": current}):
                for include_current in (False, True):
                    with self.subTest(include_current=include_current):
                        tracker = session_common.SessionFileExclusions(
                            frozenset((current, explicit, missing)), include_current,
                        )
                        # File identities have already been chosen by the caller.
                        with patch.object(session_common, "normalized_path", side_effect=AssertionError("resolved again")), \
                                patch.object(Path, "open", side_effect=AssertionError("opened")):
                            self.assertTrue(tracker.excludes(current))
                            self.assertTrue(tracker.excludes(explicit))
                            self.assertFalse(tracker.excludes(str(Path(temp) / "kept.jsonl")))
                        self.assertEqual(tracker.summary(), {
                            "current_session_files_excluded": int(not include_current),
                            "session_file_exclusions_requested": 3,
                            "explicit_session_files_excluded": 1 + int(include_current),
                            "session_file_exclusions_unmatched": 1,
                        })

    def test_both_pipelines_share_json_warnings_but_keep_partial_read_policy(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"PI_SESSION_FILE": ""}):
            root = Path(temp)
            path = root / "session.jsonl"
            header = {"type": "session", "version": 3, "id": "session", "cwd": str(root)}
            entry = {"type": "message", "id": "entry", "parentId": None,
                     "timestamp": "2026-08-10T00:00:00Z",
                     "message": {"role": "user", "content": "needle"}}
            body = (json.dumps(header) + "\nnot-json\n[]\n" + json.dumps(entry) + "\n").encode()
            search_args = cli_args("aggregate", root, root)
            recall_args = cli_args("find", root, root)
            path.write_bytes(body)
            for result in (session_search.aggregate(search_args), session_recall.find_output(recall_args)):
                self.assertEqual(result["summary"]["entries_scanned"], 1)
                self.assertEqual(result["summary"]["matched_sessions"], 1)
                self.assertEqual(result["warnings"]["by_kind"], {"invalid_entry": 1, "invalid_json_line": 1})

            path.write_bytes(body + b"\xff\n")
            partial = session_search.aggregate(search_args)
            self.assertEqual(partial["summary"]["matched_events"], 1)
            self.assertEqual(partial["warnings"]["by_kind"]["unreadable_file"], 1)
            with self.assertRaises(session_recall.RecallReadError):
                session_recall.find_output(recall_args)
