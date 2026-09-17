from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "session_recall.py"
SPEC = importlib.util.spec_from_file_location("session_recall", SCRIPT)
assert SPEC and SPEC.loader
session_recall = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = session_recall
SPEC.loader.exec_module(session_recall)


def header(session_id: str, cwd: Path, version: int = 3) -> dict:
    return {
        "type": "session",
        "version": version,
        "id": session_id,
        "timestamp": "2026-08-01T00:00:00Z",
        "cwd": str(cwd),
    }


def message(entry_id: str, parent_id: str | None, timestamp: str, role: str, content, **extra) -> dict:
    return {
        "type": "message",
        "id": entry_id,
        "parentId": parent_id,
        "timestamp": timestamp,
        "message": {"role": role, "content": content, **extra},
    }


def entry(entry_type: str, entry_id: str, parent_id: str | None, **extra) -> dict:
    return {
        "type": entry_type,
        "id": entry_id,
        "parentId": parent_id,
        "timestamp": "2026-08-10T00:00:00Z",
        **extra,
    }


def write_session(path: Path, head: dict, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(head) + "\n")
        for item in entries:
            handle.write(json.dumps(item) + "\n")


class SessionRecallTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def args(self, mode: str, root: Path, cwd: Path, *extra: str):
        required = ["--term", "인증 오류"]
        if mode == "recall":
            required += ["--include-evidence"]
        return session_recall.build_parser().parse_args([
            mode, "--sessions-root", str(root), "--cwd", str(cwd), *required, *extra
        ])

    def test_find_is_path_free_and_project_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            other = base / "other"
            project.mkdir()
            other.mkdir()
            write_session(root / "match.jsonl", header("private-session-id", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "인증 오류를 조사해 주세요"),
            ])
            write_session(root / "other.jsonl", header("other-id", other), [
                message("o1", None, "2026-08-10T00:00:00Z", "user", "인증 오류가 있습니다"),
            ])
            result = session_recall.find_output(self.args("find", root, project), self.NOW)
        self.assertEqual(result["summary"]["matched_sessions"], 1)
        self.assertEqual(result["candidates"][0]["rank"], 1)
        serialized = json.dumps(result, ensure_ascii=False)
        for private in (str(base), "private-session-id", "other-id", "인증 오류"):
            self.assertNotIn(private, serialized)
        self.assertEqual(result["results"], [])

    def test_find_uses_active_branch_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            write_session(root / "branch.jsonl", header("branch", project), [
                message("root", None, "2026-08-09T00:00:00Z", "user", "시작"),
                message("old", "root", "2026-08-10T00:00:00Z", "assistant", "인증 오류 old branch"),
                message("new", "root", "2026-08-11T00:00:00Z", "assistant", "다른 해결 경로"),
            ])
            result = session_recall.find_output(self.args("find", root, project), self.NOW)
        self.assertEqual(result["summary"]["matched_sessions"], 0)

    def test_compaction_does_not_hide_active_ancestor_or_duplicate_retained_tail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            original = message("u1", None, "2026-08-10T00:00:00Z", "user", "인증 오류 원문")
            compact = entry(
                "compaction", "c1", "u1", summary="인증 오류 요약",
                retainedTail=[original["message"]], tokensBefore=100,
            )
            write_session(root / "compact.jsonl", header("compact", project), [
                original,
                compact,
                message("a1", "c1", "2026-08-10T00:00:01Z", "assistant", "수정 완료"),
            ])
            result = session_recall.find_output(self.args("find", root, project), self.NOW)
        self.assertEqual(result["candidates"][0]["matching_messages"], 1)

    def test_recall_excludes_tool_results_thinking_and_unrelated_bookends(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            write_session(root / "recall.jsonl", header("private-id", project), [
                message("m0", None, "2026-08-10T00:00:00Z", "user", "UNRELATED_FIRST_PRIVATE"),
                message("m1", "m0", "2026-08-10T00:00:01Z", "assistant", "관련 전 단계"),
                message("m2", "m1", "2026-08-10T00:00:02Z", "assistant", [
                    {"type": "thinking", "thinking": "THINKING_PRIVATE 인증 오류"},
                    {"type": "text", "text": "인증 오류의 원인은 캐시였습니다 token=SECRET_VALUE"},
                    {"type": "toolCall", "id": "call", "name": "bash", "arguments": {"password": "TOOL_PRIVATE"}},
                ]),
                message("m3", "m2", "2026-08-10T00:00:03Z", "toolResult", "TOOL_RESULT_PRIVATE 인증 오류", toolName="bash", isError=True),
                message("m4", "m3", "2026-08-10T00:00:04Z", "assistant", "캐시 키를 수정했습니다"),
                message("m5", "m4", "2026-08-10T00:00:05Z", "user", "UNRELATED_LAST_PRIVATE"),
            ])
            result = session_recall.recall_output(self.args("recall", root, project), self.NOW)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertIn("인증 오류의 원인은 캐시였습니다 token=[REDACTED]", serialized)
        for excluded in (
            "UNRELATED_FIRST_PRIVATE", "UNRELATED_LAST_PRIVATE", "THINKING_PRIVATE",
            "TOOL_PRIVATE", "TOOL_RESULT_PRIVATE", "SECRET_VALUE", "private-id", str(root),
        ):
            self.assertNotIn(excluded, serialized)
        self.assertLessEqual(result["summary"]["messages_returned"], 5)

    def test_overlapping_hits_do_not_duplicate_messages_or_make_negative_gaps(self):
        ranges, truncated = session_recall.window_ranges(8, [1, 3, 4, 6])
        self.assertFalse(truncated)
        self.assertTrue(all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:])))
        messages = [
            session_recall.RecallMessage(str(index), None, "user", "needle")
            for index in range(8)
        ]
        windows, _summary = session_recall.recall_windows(messages, ("needle",))
        self.assertTrue(all(window["messages_omitted_before"] >= 0 for window in windows))

    def test_omitted_after_stops_at_the_next_returned_window(self):
        messages = [
            session_recall.RecallMessage(str(index), None, "user", (
                "needle" if index in {2, 8} else "filler"
            ))
            for index in range(12)
        ]
        windows, _summary = session_recall.recall_windows(messages, ("needle",))
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0]["messages_omitted_after"], 3)
        self.assertEqual(windows[1]["messages_omitted_after"], 2)

    def test_recall_windows_are_bounded_and_show_omissions(self):
        messages = [
            session_recall.RecallMessage(str(index), f"2026-08-10T00:00:{index:02d}Z", "user", (
                f"needle {index} " + "x" * 500 if index in {2, 8, 14, 20} else f"filler {index}"
            ))
            for index in range(24)
        ]
        windows, summary = session_recall.recall_windows(messages, ("needle",))
        self.assertEqual(len(windows), session_recall.MAX_WINDOWS)
        self.assertTrue(summary["evidence_truncated"])
        self.assertTrue(any(window["messages_omitted_before"] for window in windows[1:]))
        self.assertLessEqual(summary["evidence_chars"], session_recall.MAX_TOTAL_EVIDENCE_CHARS)
        self.assertTrue(all(
            len(item["evidence"]) <= session_recall.MAX_MESSAGE_CHARS
            for window in windows for item in window["messages"]
        ))

    def test_recall_rejects_candidate_changed_during_second_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            path = root / "changing.jsonl"
            write_session(path, header("changing", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "인증 오류"),
            ])
            args = self.args("recall", root, project)
            original = session_recall.read_active_messages
            calls = 0

            def changing_read(*arguments, **keywords):
                nonlocal calls
                calls += 1
                loaded = original(*arguments, **keywords)
                if calls == 2 and loaded is not None:
                    return ([session_recall.RecallMessage(
                        "m2", "2026-08-10T00:00:00Z", "user", "인증 오류 changed"
                    )], loaded[1])
                return loaded

            with patch.object(session_recall, "read_active_messages", side_effect=changing_read):
                with self.assertRaises(session_recall.CandidateNotFoundError):
                    session_recall.recall_output(args, self.NOW)

    def test_invalid_branch_is_skipped_with_path_free_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            write_session(root / "broken.jsonl", header("private-id", project), [
                message("m1", "missing", "2026-08-10T00:00:00Z", "user", "인증 오류"),
            ])
            result = session_recall.find_output(self.args("find", root, project), self.NOW)
        self.assertEqual(result["summary"]["matched_sessions"], 0)
        self.assertEqual(result["warnings"]["by_kind"], {"invalid_branch_structure": 1})
        self.assertNotIn(str(root), json.dumps(result))

    def test_terms_are_or_ranked_and_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            write_session(root / "one.jsonl", header("one", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "한글 검색"),
            ])
            write_session(root / "two.jsonl", header("two", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "한글 검색과 캐시 문제"),
            ])
            args = session_recall.build_parser().parse_args([
                "find", "--sessions-root", str(root), "--cwd", str(project),
                "--term", "한글", "--term", "캐시",
            ])
            result = session_recall.find_output(args, self.NOW)
        self.assertEqual([item["matched_terms"] for item in result["candidates"]], [2, 1])
        for values in ([], ["한"], ["x" * 101], [str(i) * 2 for i in range(9)]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                session_recall.normalize_terms(values)

    def test_literal_terms_preserve_internal_whitespace_in_find_and_recall(self):
        self.assertEqual(session_recall.normalize_terms(['  Foo  BAR  ', 'foo  bar', 'foo bar']),
                         ('foo  bar', 'foo bar'))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for whitespace in ('  ', '\t', '\n'):
                with self.subTest(whitespace=whitespace):
                    text = f'인증{whitespace}오류'
                    write_session(root / 'literal.jsonl', header('literal', root), [
                        message('m1', None, '2026-08-10T00:00:00Z', 'user', text),
                    ])
                    args = self.args('find', root, root)
                    args.term = [text]
                    result = session_recall.find_output(args, self.NOW)
                    self.assertEqual(result['summary']['matched_sessions'], 1)
                    args = self.args('recall', root, root)
                    args.term = [text]
                    result = session_recall.recall_output(args, self.NOW)
                    self.assertEqual(result['summary']['matching_messages'], 1)
                    self.assertTrue(result['results'][0]['messages'][0]['matches_term'])
                    args = self.args('find', root, root)
                    self.assertEqual(session_recall.find_output(args, self.NOW)['candidates'], [])
                    write_session(root / 'literal.jsonl', header('literal', root), [
                        message('m1', None, '2026-08-10T00:00:00Z', 'user', '인증 오류'),
                    ])
                    args.term = [text]
                    self.assertEqual(session_recall.find_output(args, self.NOW)['candidates'], [])

    def test_invalid_message_roles_preserve_branch_links_and_do_not_abort_cli(self):
        stamp = '2026-08-10T00:00:00Z'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for version in (1, 2, 3):
                for role in ([], {}, None, 42):
                    with self.subTest(version=version, role=role):
                        malformed = message('bad', 'u', stamp, role, 'BAD_ROLE_CONTENT')
                        self.assertIsNone(session_recall.recall_text(malformed))
                        retained = session_recall.retain_recall_entry(malformed)
                        self.assertEqual(retained['id'], 'bad')
                        self.assertEqual(retained['parentId'], 'u')
                        write_session(root / 'roles.jsonl', header('roles', root, version), [
                            message('u', None, stamp, 'user', '인증 오류 before'),
                            malformed,
                            message('a', 'bad', stamp, 'assistant', '인증 오류 after'),
                        ])
                        stdout = io.StringIO()
                        with redirect_stdout(stdout):
                            code = session_recall.main([
                                'recall', '--sessions-root', str(root), '--cwd', str(root),
                                '--term', '인증 오류', '--include-evidence',
                            ])
                        self.assertEqual(code, 0)
                        result = json.loads(stdout.getvalue())
                        self.assertEqual(result['summary']['matching_messages'], 2)
                        self.assertEqual(result['warnings']['count'], 0)
                        self.assertNotIn('BAD_ROLE_CONTENT', stdout.getvalue())

    def test_recall_evidence_masks_quoted_password_and_all_cookies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_session(root / 'secrets.jsonl', header('synthetic', root), [
                message('m1', None, '2026-08-10T00:00:00Z', 'user',
                        '인증 오류 password="FAKE FIRST SECOND"\nCookie: session=FAKE_A; sid=FAKE_B'),
            ])
            result = session_recall.recall_output(self.args('recall', root, root), self.NOW)
        self.assertEqual(result['results'][0]['messages'][0]['evidence'],
                         '인증 오류 password=[REDACTED] Cookie: [REDACTED]')

    def test_default_scope_does_not_report_foreign_project_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            foreign = base / "foreign"
            project.mkdir()
            foreign.mkdir()
            write_session(root / "local.jsonl", header("local", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "인증 오류"),
            ])
            future = header("future", foreign)
            future["version"] = 99
            write_session(root / "future.jsonl", future, [])
            (root / "broken.jsonl").write_text("not-json\n", encoding="utf-8")
            result = session_recall.find_output(self.args("find", root, project), self.NOW)
        self.assertEqual(result["summary"]["files_selected"], 1)
        self.assertNotIn("files_discovered", result["summary"])
        self.assertEqual(result["warnings"], {"count": 0, "by_kind": {}})

    def test_selected_project_decode_failure_has_path_free_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "corrupt.jsonl"
            write_session(path, header("private-id", root), [
                message("u", None, "2026-08-10T00:00:00Z", "user", "인증 오류"),
                # Put the invalid byte beyond the header's decoding buffer.
                message("t", "u", "2026-08-10T00:00:01Z", "toolResult", "x" * 20000),
            ])
            with path.open("ab") as handle:
                handle.write(b"\xff\n")
            for all_projects in (False, True):
                with self.subTest(all_projects=all_projects):
                    args = self.args("find", root, root)
                    args.all_projects = all_projects
                    result = session_recall.find_output(args, self.NOW)
                    self.assertEqual(result["summary"]["matched_sessions"], 0)
                    self.assertEqual(result["warnings"], {
                        "count": 1, "by_kind": {"unreadable_file": 1},
                    })
                    self.assertNotIn(str(root), json.dumps(result))

    def test_near_header_decode_failure_warns_only_for_selected_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'corrupt.jsonl'
            for scope in ('selected', 'foreign', 'unknown'):
                for all_projects in (False, True):
                    with self.subTest(scope=scope, all_projects=all_projects):
                        head = header('synthetic', root if scope == 'selected' else root / 'foreign')
                        prefix = (json.dumps(head) + '\n').encode('utf-8') if scope != 'unknown' else b'\xff\n'
                        path.write_bytes(prefix + b'\xff\n')
                        args = self.args('find', root, root)
                        args.all_projects = all_projects
                        result = session_recall.find_output(args, self.NOW)
                        expected = {'unreadable_file': 1} if all_projects or scope == 'selected' else {}
                        self.assertEqual(result['warnings']['by_kind'], expected)
                        self.assertNotIn(str(root), json.dumps(result))

    def test_read_failures_warn_only_after_scope_is_known(self):
        class FailingBody(io.BytesIO):
            def __next__(self):
                raise OSError("synthetic read failure")

        class FailingHeader(FailingBody):
            def readline(self, *args, **kwargs):
                raise UnicodeError("synthetic header failure")

        path = Path("/synthetic/session.jsonl")
        cwd = session_recall.session_search.normalized_path("/synthetic/project")
        for all_projects in (False, True):
            for scope in ("selected", "foreign", "unknown", "open_failure"):
                with self.subTest(all_projects=all_projects, scope=scope):
                    warnings = session_recall.session_search.WarningCollector()
                    head = header("private-id", Path(cwd if scope == "selected" else "/foreign"))
                    stream_type = FailingHeader if scope == "unknown" else FailingBody
                    stream = stream_type((json.dumps(head) + "\n").encode("utf-8"))
                    options = ({"side_effect": OSError("synthetic open failure")}
                               if scope == "open_failure" else {"return_value": stream})
                    with patch.object(Path, "open", **options):
                        session_recall.read_active_messages(path, cwd, all_projects, warnings)
                    expected = {"unreadable_file": 1} if all_projects or scope == "selected" else {}
                    self.assertEqual(warnings.output(False)["by_kind"], expected)

    def test_retained_entries_discard_unused_payloads_without_truncating_text(self):
        text = "x" * 20000 + "인증 오류"
        original = message("u", None, "2026-08-10T00:00:00Z", "user", [
            {"type": "image", "data": "IMAGE_PAYLOAD"},
            {"type": "thinking", "thinking": "THINKING_PAYLOAD"},
            {"type": "text", "text": text},
            {"type": "text", "text": "second block"},
            {"type": "toolCall", "arguments": {"value": "CALL_PAYLOAD"}},
        ], usage={"unused": "USAGE_PAYLOAD"})
        tool = message("t", "u", "2026-08-10T00:00:01Z", "toolResult", "TOOL_PAYLOAD")
        compact = entry("compaction", "c", "t", summary="SUMMARY_PAYLOAD", retainedTail=[original])
        retained = [session_recall.retain_recall_entry(item) for item in (original, tool, compact)]
        self.assertEqual(retained[0]["message"], {"role": "user", "content": text + "\nsecond block"})
        self.assertEqual(retained[1]["message"], {"role": "toolResult"})
        self.assertEqual(retained[2], {
            key: compact[key] for key in ("type", "id", "parentId", "timestamp")
        })
        self.assertNotIn("PAYLOAD", json.dumps(retained))
        self.assertEqual(session_recall.active_entries(retained, 3), retained)
        self.assertEqual(session_recall.recall_text(retained[0]), session_recall.recall_text(original))
        self.assertIsInstance(original["message"]["content"], list)

    def test_reader_retains_branch_nodes_and_full_text_across_versions(self):
        stamp = "2026-08-10T00:00:00Z"
        records = [
            message("u", None, stamp, "user", "x" * 20000 + "인증 오류"),
            message("old", "u", stamp, "assistant", "old branch"),
            message("t", "u", stamp, "toolResult", "unused tool payload"),
            entry("compaction", "c", "t", summary="unused summary"),
            message("a", "c", stamp, "assistant", "answer"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "branch.jsonl"
            for version in (1, 2, 3):
                with self.subTest(version=version):
                    write_session(path, header("branch", root, version), records)
                    warnings = session_recall.session_search.WarningCollector()
                    validate = session_recall.active_entries
                    with patch.object(session_recall, "active_entries", wraps=validate) as observed:
                        loaded = session_recall.read_active_messages(path, str(root), False, warnings)
                    retained = observed.call_args.args[0]
                    self.assertEqual(len(retained), len(records))
                    self.assertNotIn("unused", json.dumps(retained))
                    chosen = records[:2] + records[-1:] if version == 1 else [records[0], records[-1]]
                    expected = [session_recall.recall_text(item) for item in chosen]
                    self.assertEqual(loaded, (expected, len(records)))
                    self.assertEqual(warnings.count, 0)
                    candidate, _ = session_recall.candidate_for_messages(path, loaded[0], ("인증 오류",), None)
                    self.assertIsNotNone(candidate)

    def test_reader_preserves_invalid_branch_checks(self):
        cases = {
            "duplicate": [entry("custom", "a", None), entry("custom", "a", None)],
            "cycle": [entry("custom", "a", "b"), entry("custom", "b", "a")],
            "missing_parent": [entry("custom", "a", "missing")],
            "invalid_parent": [entry("custom", "a", 42)],
            "missing_id": [{"type": "custom", "parentId": None}],
            "invalid_id": [entry("custom", 42, None)],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "invalid.jsonl"
            for version in (1, 2, 3):
                for name, records in cases.items():
                    with self.subTest(version=version, case=name):
                        write_session(path, header("invalid", root, version), records)
                        warnings = session_recall.session_search.WarningCollector()
                        loaded = session_recall.read_active_messages(path, str(root), False, warnings)
                        if version == 1:
                            self.assertEqual(loaded, ([], len(records)))
                            self.assertEqual(warnings.count, 0)
                        else:
                            self.assertIsNone(loaded)
                            self.assertEqual(warnings.output(False)["by_kind"], {"invalid_branch_structure": 1})

    def test_extreme_timestamp_is_ignored_without_overflow(self):
        self.assertIsNone(session_recall.session_search.parse_timestamp("0001-01-01T00:00:00+14:00"))

    def test_untrusted_timestamp_is_not_returned_as_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            private_timestamp = "timestamp=PRIVATE_VALUE" + "x" * 1000
            write_session(root / "timestamp.jsonl", header("timestamp", project), [
                message("m1", None, private_timestamp, "user", "인증 오류"),
            ])
            result = session_recall.recall_output(self.args("recall", root, project), self.NOW)
        self.assertIsNone(result["results"][0]["messages"][0]["timestamp"])
        self.assertNotIn("PRIVATE_VALUE", json.dumps(result))

    def test_file_symlink_outside_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            root.mkdir()
            project = base / "project"
            project.mkdir()
            outside = base / "outside.jsonl"
            write_session(outside, header("outside", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "인증 오류"),
            ])
            (root / "alias.jsonl").symlink_to(outside)
            result = session_recall.find_output(self.args("find", root, project), self.NOW)
        self.assertEqual(result["summary"]["matched_sessions"], 0)
        self.assertEqual(result["warnings"]["by_kind"], {"file_outside_session_root": 1})

    def test_recall_days_uses_same_candidate_calculation_on_second_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sessions"
            project = Path(temp) / "project"
            project.mkdir()
            write_session(root / "days.jsonl", header("days", project), [
                message("old", None, "2026-08-01T00:00:00Z", "user", "인증 오류 old"),
                message("new", "old", "2026-08-14T00:00:00Z", "assistant", "인증 오류 recent"),
            ])
            result = session_recall.recall_output(self.args(
                "recall", root, project, "--days", "2"
            ), self.NOW)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertIn("인증 오류 recent", serialized)
        self.assertNotIn("인증 오류 old", serialized)

    def test_recall_requires_explicit_evidence_flag(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = session_recall.main(["recall", "--term", "인증 오류"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "INVALID_ARGUMENT")

    def test_candidate_rank_and_missing_candidate_are_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = self.args("recall", root, root, "--candidate-rank", "2")
            stdout = io.StringIO()
            with patch.object(session_recall, "build_parser") as parser, redirect_stdout(stdout):
                parser.return_value.parse_args.return_value = args
                code = session_recall.main([])
        self.assertEqual(code, 2)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["error"]["code"], "CANDIDATE_NOT_FOUND")
        self.assertNotIn(str(root), stdout.getvalue())

    def test_cli_help_and_json_output(self):
        help_result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], check=True, capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertIn("{find,recall}", help_result.stdout)
        self.assertEqual(help_result.stderr, "")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "find", "--sessions-root", str(root),
                 "--cwd", str(root), "--term", "인증 오류"],
                check=True, capture_output=True, text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertEqual(len(completed.stdout.strip().splitlines()), 1)
        self.assertEqual(json.loads(completed.stdout)["mode"], "find")


if __name__ == "__main__":
    unittest.main()
