"""Explicit file exclusions are path-based, pre-read, and continuation-bound."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from test_session_recall import header, message, session_recall, write_session

session_search = session_recall.session_search


class FileExclusionTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / "sessions"
        self.project = self.base / "project"
        self.project.mkdir()
        self.path = self.root / "original.jsonl"
        self.entries = [message(str(i), str(i - 1) if i else None,
                                "2026-08-10T00:00:00Z", "user", f"needle {i}") for i in range(40)]
        write_session(self.path, header("same-id", self.project), self.entries)
        environment = patch.dict(os.environ, {"PI_SESSION_FILE": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def argv(self, mode, *extra):
        scope = ["--sessions-root", str(self.root), "--cwd", str(self.project)]
        if mode == "aggregate":
            return [*scope, *extra]
        return [mode, *scope, "--term", "needle",
                *(["--include-evidence"] if mode == "recall" else []), *extra]

    def output(self, mode, *extra):
        module = session_search if mode == "aggregate" else session_recall
        args = module.build_parser().parse_args(self.argv(mode, *extra))
        function = {"aggregate": session_search.aggregate, "find": session_recall.find_output,
                    "recall": session_recall.recall_output}[mode]
        return function(args, self.NOW)

    def exclusions(self, *paths):
        return [item for path in paths for item in ("--exclude-session-file", str(path))]

    def assert_counts(self, result, requested, explicit, unmatched, current=0):
        summary = result["summary"]
        self.assertEqual(summary["session_file_exclusions_requested"], requested)
        self.assertEqual(summary["explicit_session_files_excluded"], explicit)
        self.assertEqual(summary["session_file_exclusions_unmatched"], unmatched)
        self.assertEqual(summary["current_session_files_excluded"], current)

    def test_excluded_invalid_and_unreadable_files_are_never_opened(self):
        invalid = self.root / "invalid.jsonl"
        unreadable = self.root / "unreadable.jsonl"
        invalid.write_text("not-json", encoding="utf-8")
        unreadable.write_bytes(b"\xff")
        original_open = Path.open

        def guarded(path, *args, **kwargs):
            self.assertNotIn(path, (invalid, unreadable), "excluded file was opened")
            return original_open(path, *args, **kwargs)

        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode), patch.object(Path, "open", guarded):
                result = self.output(mode, *self.exclusions(invalid, unreadable))
            self.assert_counts(result, 2, 2, 0)
            self.assertEqual(result["summary"]["files_selected"], 1)
            self.assertEqual(result["warnings"]["count"], 0)
            serialized = json.dumps(result)
            self.assertNotIn(str(self.base), serialized)
            self.assertNotIn("invalid.jsonl", serialized)

    def test_relative_duplicate_and_symlink_aliases_use_process_cwd(self):
        alias = self.base / "alias.jsonl"
        alias.symlink_to(self.path)
        old_cwd = Path.cwd()
        try:
            os.chdir(self.base)
            for mode in ("aggregate", "find"):
                result = self.output(mode, *self.exclusions("sessions/original.jsonl", self.path, alias))
                self.assert_counts(result, 1, 1, 0)
                self.assertEqual(result["summary"]["files_selected"], 0)
        finally:
            os.chdir(old_cwd)

    def test_same_id_copies_and_hardlinks_remain_separate(self):
        copy = self.root / "copy.jsonl"
        copy.write_bytes(self.path.read_bytes())
        hardlink = self.root / "hardlink.jsonl"
        os.link(self.path, hardlink)
        alias = self.root / "alias.jsonl"
        alias.symlink_to(self.path)
        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode):
                result = self.output(mode, *self.exclusions(alias, self.path))
                self.assert_counts(result, 1, 1, 0)
                self.assertEqual(result["summary"]["matched_sessions"], 2)
                if mode == "aggregate":
                    self.assertEqual(result["summary"]["files_discovered"], 3)

    def test_current_exclusion_precedence_and_overlap_is_not_unmatched(self):
        other = self.root / "other.jsonl"
        write_session(other, header("other", self.project), self.entries)
        with patch.dict(os.environ, {"PI_SESSION_FILE": str(self.path)}):
            for include in (False, True):
                for explicit in (False, True):
                    options = (["--include-current"] if include else []) + (self.exclusions(self.path) if explicit else [])
                    for mode in ("aggregate", "find", "recall"):
                        with self.subTest(mode=mode, include=include, explicit=explicit):
                            result = self.output(mode, *options)
                            self.assert_counts(result, int(explicit), int(explicit and include), 0, int(not include))
                            self.assertEqual(result["summary"]["files_selected"], 2 if include and not explicit else 1)

    def test_missing_directory_glob_and_outside_paths_do_not_expand_roots(self):
        outside = self.base / "outside.jsonl"
        write_session(outside, header("outside", self.project), self.entries)
        missing = self.root / "missing.jsonl"
        for mode in ("aggregate", "find", "recall"):
            result = self.output(mode, *self.exclusions(outside, missing, self.root, self.root / "*.jsonl"))
            self.assert_counts(result, 4, 0, 4)
            self.assertEqual(result["summary"]["files_selected"], 1)
        result = self.output("find", "--additional-sessions-root", str(self.base), *self.exclusions(outside))
        self.assert_counts(result, 1, 1, 0)
        self.assertEqual(result["summary"]["files_selected"], 1)

    def test_foreign_project_exclusion_counts_are_pre_header_file_counts(self):
        foreign = self.root / "foreign.jsonl"
        write_session(foreign, header("foreign", self.base), self.entries)
        for mode in ("aggregate", "find", "recall"):
            result = self.output(mode, *self.exclusions(foreign))
            self.assert_counts(result, 1, 1, 0)
            self.assertEqual(result["summary"]["files_selected"], 1)
            if mode != "aggregate":
                self.assertNotIn("files_discovered", result["summary"])

    def test_all_excluded_is_empty_for_search_but_candidate_not_found_for_recall(self):
        for mode in ("aggregate", "find"):
            result = self.output(mode, *self.exclusions(self.path))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["summary"]["matched_sessions"], 0)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = session_recall.main(self.argv("recall", *self.exclusions(self.path)))
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "CANDIDATE_NOT_FOUND")

    def test_batch_shares_exclusions_and_matches_single(self):
        other = self.root / "other.jsonl"
        write_session(other, header("other", self.project), self.entries)
        options = [*self.exclusions(other), "--since", "2026-08-10T00:00:00Z", "--until", "2026-08-11T00:00:00Z"]
        single = self.output("aggregate", *options)
        original_open = Path.open
        opened = []

        def counted(path, *args, **kwargs):
            opened.append(path)
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", counted):
            batch = self.output("aggregate", *options, "--batch-filter", "{}", "--batch-filter", '{"role":["user"]}')
        self.assertEqual(opened, [self.path])
        self.assertTrue(all(item["summary"] == single["summary"] for item in batch["batches"]))
        self.assert_counts(batch, 1, 1, 0)

    def test_invalid_exclusions_fail_before_discovery_without_echo(self):
        for value in ("", "private-secret\x00.jsonl"):
            for mode in ("aggregate", "find", "recall"):
                stdout = io.StringIO()
                main = session_search.main if mode == "aggregate" else session_recall.main
                with patch.object(session_search, "discover_session_files") as discover, redirect_stdout(stdout):
                    code = main(self.argv(mode, *self.exclusions(value)))
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_ARGUMENT")
                self.assertNotIn("private-secret", stdout.getvalue())
                discover.assert_not_called()

    def test_normalization_failures_are_arguments_not_storage_errors(self):
        for failure in (ValueError, OSError, RuntimeError):
            for mode in ("aggregate", "find", "recall"):
                stdout = io.StringIO()
                main = session_search.main if mode == "aggregate" else session_recall.main
                with patch.object(session_search, "normalized_path", side_effect=failure("private-secret")), \
                     patch.object(session_search, "discover_session_files") as discover, redirect_stdout(stdout):
                    code = main(self.argv(mode, *self.exclusions("private-secret.jsonl")))
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_ARGUMENT")
                self.assertNotIn("private-secret", stdout.getvalue())
                discover.assert_not_called()

    def test_continuation_equivalent_exclusions_and_changes_before_scan(self):
        other = self.root / "other.jsonl"
        write_session(other, header("other", self.project), self.entries)
        alias = self.base / "alias.jsonl"
        alias.symlink_to(other)
        missing = self.root / "missing.jsonl"
        options = self.exclusions(other, missing)
        first = self.output("recall", *options)
        token = first["next_continuation"]
        with patch.object(session_search, "normalized_exclusions", wraps=session_search.normalized_exclusions) as normalize:
            second = self.output("recall", *self.exclusions(missing, alias, other), "--continuation", token)
        normalize.assert_called_once()
        self.assert_counts(second, 2, 1, 1)
        self.assertIn("needle 15", json.dumps(second))
        for changed in ([], self.exclusions(other), self.exclusions(other, missing, self.path),
                        self.exclusions(other, self.root / "different-missing.jsonl")):
            with self.subTest(changed=changed), patch.object(session_recall, "scan_candidates") as scan:
                with self.assertRaises(ValueError):
                    self.output("recall", *changed, "--continuation", token)
                scan.assert_not_called()
        # Scope follows the requested normalized set, not whether a file exists.
        write_session(missing, header("newly-created", self.project), self.entries)
        second = self.output("recall", *options, "--continuation", token)
        self.assert_counts(second, 2, 2, 0)

    def test_tilde_expansion_uses_existing_normalized_path_contract(self):
        with patch.dict(os.environ, {"HOME": str(self.base)}):
            self.assertEqual(session_search.normalized_exclusions(["~/sessions/original.jsonl"]),
                             frozenset({str(self.path.resolve())}))


if __name__ == "__main__":
    unittest.main()
