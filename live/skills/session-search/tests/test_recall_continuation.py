from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from test_session_recall import header, message, session_recall, write_session


class RecallContinuationTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "sessions"
        self.project = Path(temporary.name) / "project"
        self.project.mkdir()
        self.path = self.root / "original.jsonl"
        self.entries = [
            message(str(i), str(i - 1) if i else None,
                    f"2026-08-10T00:{i:02d}:00Z", "user",
                    f'인증 오류 match-{i} password="synthetic-{i}" ' + "x" * 500
                    if i % 6 == 2 else f"context-{i}")
            for i in range(48)
        ]
        write_session(self.path, header("original", self.project), self.entries)

    def args(self, token=None, *extra):
        selection = ["--continuation", token] if token is not None else []
        return session_recall.build_parser().parse_args([
            "recall", "--sessions-root", str(self.root), "--cwd", str(self.project),
            "--term", "인증 오류", "--include-evidence", *selection, *extra,
        ])

    def recall(self, token=None, *extra, now=None):
        return session_recall.recall_output(self.args(token, *extra), now or self.NOW)

    def token(self):
        return self.recall()["next_continuation"]

    def assert_safe_page(self, output):
        summary = output["summary"]
        self.assertLessEqual(summary["windows_returned"], session_recall.MAX_WINDOWS)
        self.assertLessEqual(summary["evidence_chars"], session_recall.MAX_TOTAL_EVIDENCE_CHARS)
        for window in output["results"]:
            self.assertLessEqual(len(window["messages"]), session_recall.MAX_MESSAGES_PER_WINDOW)
            for item in window["messages"]:
                self.assertLessEqual(len(item["evidence"]), session_recall.MAX_MESSAGE_CHARS)
                self.assertNotIn("synthetic-", item["evidence"])
        serialized = json.dumps(output, ensure_ascii=False)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(str(self.project), serialized)
        self.assertNotIn("original.jsonl", serialized)

    def test_reads_all_matching_windows_once_in_bounded_masked_pages(self):
        output = self.recall()
        matches = []
        page_sizes = []
        while True:
            self.assert_safe_page(output)
            page_sizes.append(output["summary"]["windows_returned"])
            matches.extend(item["evidence"].split(" password")[0]
                           for window in output["results"] for item in window["messages"]
                           if item["matches_term"])
            token = output["next_continuation"]
            if token is None:
                break
            self.assertLess(len(page_sizes), 4)
            self.assertNotIn(str(self.path).encode(), base64.urlsafe_b64decode(token))
            output = self.recall(token)
        self.assertEqual(page_sizes, [3, 3, 2])
        self.assertEqual(matches, [f"인증 오류 match-{i}" for i in range(2, 48, 6)])

    def test_continuation_keeps_candidate_when_another_session_takes_first_rank(self):
        token = self.token()
        write_session(self.root / "newer.jsonl", header("newer", self.project), [
            message(str(i), str(i - 1) if i else None, "2026-08-14T00:00:00Z", "user", "인증 오류 new")
            for i in range(9)
        ])
        output = self.recall(token)
        self.assertEqual(output["summary"]["selected_candidate_rank"], 2)
        self.assertIn("match-20", json.dumps(output, ensure_ascii=False))
        self.assertNotIn("인증 오류 new", json.dumps(output, ensure_ascii=False))
        # Initial ranked recall still uses the current ranking, not a snapshot.
        self.assertIn("인증 오류 new", json.dumps(self.recall(), ensure_ascii=False))

    def test_changed_missing_or_moved_candidate_fails_without_switching(self):
        for change in ("append", "rewrite", "remove", "move"):
            with self.subTest(change=change):
                write_session(self.path, header("original", self.project), self.entries)
                token = self.token()
                if change == "append":
                    with self.path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(message("48", "47", "2026-08-11T00:00:00Z", "user", "new")) + "\n")
                elif change == "rewrite":
                    changed = [dict(item) for item in self.entries]
                    changed[1] = message("1", "0", "2026-08-10T00:01:00Z", "user", "changed non-match")
                    write_session(self.path, header("original", self.project), changed)
                elif change == "remove":
                    self.path.unlink()
                else:
                    self.path.rename(self.root / "moved.jsonl")
                with self.assertRaises(session_recall.CandidateNotFoundError):
                    self.recall(token)
                moved = self.root / "moved.jsonl"
                if moved.exists():
                    moved.unlink()

    def test_copied_identical_conversation_is_not_a_replacement(self):
        token = self.token()
        write_session(self.root / "copy.jsonl", header("original", self.project), self.entries)
        self.path.unlink()
        with self.assertRaises(session_recall.CandidateNotFoundError):
            self.recall(token)

    def test_scope_changes_are_rejected_before_scanning(self):
        token = self.token()
        for change in ({"term": ["different"]}, {"days": 7.0}, {"all_projects": True},
                       {"include_current": True}, {"cwd": str(self.root)},
                       {"sessions_root": self.project}, {"additional_sessions_root": [self.project]}):
            with self.subTest(change=change):
                args = self.args(token)
                for key, value in change.items():
                    setattr(args, key, value)
                with patch.object(session_recall, "scan_candidates") as scan:
                    with self.assertRaises(ValueError):
                        session_recall.recall_output(args, self.NOW)
                    scan.assert_not_called()
        with patch.dict(os.environ, {"PI_SESSION_FILE": str(self.path)}):
            with self.assertRaises(ValueError):
                self.recall(token)

    def test_equivalent_scope_and_terms_are_accepted(self):
        first = self.recall(None, "--term", "context", "--additional-sessions-root", str(self.project))
        args = self.args(first["next_continuation"], "--term", "context")
        args.term.reverse()
        args.additional_sessions_root = [self.project, self.root]
        # Root ordering/aliases and term ordering do not change effective scope.
        args.sessions_root = self.project
        output = session_recall.recall_output(args, self.NOW)
        self.assertGreater(output["summary"]["messages_returned"], 0)

    def test_days_cutoff_is_fixed_for_all_pages(self):
        first = self.recall(None, "--days", "6")
        output = self.recall(first["next_continuation"], "--days", "6", now=self.NOW + timedelta(days=30))
        self.assertIn("match-20", json.dumps(output, ensure_ascii=False))

    def test_invalid_tokens_fail_before_storage_and_do_not_echo_input(self):
        valid = json.loads(base64.urlsafe_b64decode(self.token()))
        malformed = ["", "not-a-token", "x" * 513, "private-path-秘密"]
        for value in (None, {}, [True, *valid[1:]], [2, *valid[1:]],
                      [1, "invalid", *valid[2:]], [*valid[:2], "bad", *valid[3:]],
                      [*valid[:4], True], [*valid[:4], -1], [*valid[:4], 1],
                      [*valid[:4], 2**32]):
            malformed.append(base64.urlsafe_b64encode(json.dumps(value).encode()).decode())
        for token in malformed:
            with self.subTest(token=token):
                output = io.StringIO()
                with patch.object(session_recall, "scan_candidates") as scan, redirect_stdout(output):
                    code = session_recall.main([
                        "recall", "--term", "needle", "--continuation", token,
                        "--sessions-root", "/synthetic/missing", "--include-evidence",
                    ])
                    scan.assert_not_called()
                result = json.loads(output.getvalue())
                self.assertEqual(code, 2)
                self.assertEqual(result["error"]["code"], "INVALID_ARGUMENT")
                self.assertNotIn("private-path", output.getvalue())
                self.assertEqual(result["results"], [])

    def test_cursor_beyond_last_window_fails_safely(self):
        cursor = json.loads(base64.urlsafe_b64decode(self.token()))
        cursor[-1] = 300
        token = base64.urlsafe_b64encode(json.dumps(cursor).encode()).decode()
        with self.assertRaises(session_recall.CandidateNotFoundError):
            self.recall(token)

    def test_each_page_still_requires_evidence_consent_and_cannot_select_a_rank(self):
        token = self.token()
        for options in (["--continuation", token],
                        ["--continuation", token, "--candidate-rank", "2", "--include-evidence"]):
            with self.subTest(options=options), self.assertRaises(session_recall.session_search.InvalidArgumentError):
                session_recall.build_parser().parse_args(["recall", "--term", "needle", *options])

    def test_continuation_works_across_processes_without_writing_state(self):
        command = [sys.executable, "-B", str(session_recall.__file__), "recall",
                   "--sessions-root", str(self.root), "--cwd", str(self.project),
                   "--term", "인증 오류", "--include-evidence"]
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        first = json.loads(subprocess.check_output(command, text=True))
        second = json.loads(subprocess.check_output(
            [*command, "--continuation", first["next_continuation"]], text=True))
        self.assertIn("match-20", json.dumps(second, ensure_ascii=False))
        self.assert_safe_page(second)
        after = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_paging_supports_legacy_and_branch_sessions_with_dense_matches(self):
        for version in (1, 2, 3):
            with self.subTest(version=version):
                entries = [message(str(i), str(i - 1) if i else None,
                                   "2026-08-10T00:00:00Z", "user", f"인증 오류 dense-{i}")
                           for i in range(40)]
                write_session(self.path, header("original", self.project, version), entries)
                output = self.recall(now=self.NOW.replace(tzinfo=None))
                seen = []
                while True:
                    self.assert_safe_page(output)
                    seen.extend(item["evidence"] for window in output["results"]
                                for item in window["messages"])
                    if output["next_continuation"] is None:
                        break
                    output = self.recall(output["next_continuation"])
                self.assertEqual(seen, [f"인증 오류 dense-{i}" for i in range(40)])

    def test_single_page_and_find_have_no_continuation(self):
        write_session(self.path, header("original", self.project), self.entries[:3])
        self.assertIsNone(self.recall()["next_continuation"])
        args = session_recall.build_parser().parse_args([
            "find", "--sessions-root", str(self.root), "--cwd", str(self.project), "--term", "인증 오류",
        ])
        self.assertNotIn("next_continuation", session_recall.find_output(args, self.NOW))

    def test_continuation_checks_second_read_changes(self):
        token = self.token()
        original = session_recall.read_active_messages
        calls = 0

        def changing_read(*arguments, **keywords):
            nonlocal calls
            calls += 1
            loaded = original(*arguments, **keywords)
            if calls == 2:
                return [session_recall.RecallMessage("changed", None, "user", "인증 오류")], 1
            return loaded

        with patch.object(session_recall, "read_active_messages", side_effect=changing_read):
            with self.assertRaises(session_recall.CandidateNotFoundError):
                self.recall(token)
