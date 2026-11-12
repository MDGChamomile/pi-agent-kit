from __future__ import annotations

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

from support import (
    SEARCH_SCRIPT as SCRIPT, cli_args, fixture_tree, header, message, session_common, session_search, skill_envelope,
    write_session,
)


class SessionSearchTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def args(self, root: Path, cwd: Path, *extra: str):
        return cli_args("aggregate", root, cwd, *extra)

    def test_symlink_aliases_count_once_but_copies_stay_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            source = root / "nested" / "source.jsonl"
            write_session(source, header("same-id", base), [
                message("one", None, "2026-08-14T00:00:00Z", "user", "match"),
            ])
            (root / "copy.jsonl").write_bytes(source.read_bytes())
            (root / "alias.jsonl").symlink_to(source)
            result = session_search.aggregate(self.args(root, base))
            self.assertEqual(result["summary"]["files_discovered"], 2)
            self.assertEqual(result["summary"]["matched_sessions"], 2)

    def test_file_symlink_outside_the_root_is_skipped_before_opening(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            root.mkdir()
            other = base / "sessions-other"  # A string-prefix match must not grant access.
            source = other / "source.jsonl"
            write_session(source, header("outside", base), [
                message("one", None, "2026-08-14T00:00:00Z", "user", "match"),
            ])
            (root / "alias.jsonl").symlink_to(source)
            with patch.object(session_common, "open_session_file") as open_file:
                excluded = session_search.aggregate(self.args(root, base))
                open_file.assert_not_called()
            self.assertEqual(excluded["summary"]["files_discovered"], 0)
            self.assertEqual(excluded["summary"]["matched_sessions"], 0)

    def test_missing_or_non_directory_root_fails_without_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            non_directory = base / "not-directory"
            non_directory.write_text("test", encoding="utf-8")
            for root in (base / "missing-private", non_directory):
                with self.subTest(root=root):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        code = session_search.main(["--sessions-root", str(root)])
                    self.assertEqual(code, 2)
                    self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "SESSION_STORAGE_UNAVAILABLE")
                    self.assertNotIn(str(base), stdout.getvalue())

    def test_directory_traversal_failure_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def failing_walk(_path, *, onerror):
                onerror(PermissionError("private directory"))
                yield from ()

            with patch.object(session_common.os, "walk", side_effect=failing_walk):
                with self.assertRaises(PermissionError):
                    session_search.aggregate(self.args(root, root))

    def test_default_cwd_current_exclusion_and_literal_filter(self):
        with fixture_tree() as (root, project_a, _, primary, _, current):
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(self.args(root, project_a, "--query", "failure"), now=self.NOW)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["evidence_included"])
        self.assertEqual(result["summary"]["files_selected"], 1)
        self.assertEqual(result["summary"]["current_session_files_excluded"], 1)
        self.assertEqual(result["summary"]["matched_sessions"], 1)
        self.assertEqual(result["summary"]["matched_entries"], 2)
        self.assertEqual(result["results"], [])
        self.assertTrue(result["summary"]["evidence_omitted"])
        self.assertFalse(result["summary"]["evidence_truncated"])
        self.assertFalse(result["summary"]["truncated"])
        serialized = json.dumps(result)
        self.assertNotIn(str(project_a), serialized)
        self.assertNotIn(str(primary), serialized)
        self.assertNotIn("session-a", serialized)
        self.assertNotIn("Repeated FAILURE", serialized)
        self.assertNotIn("current only marker", serialized)
        self.assertNotIn("another project", serialized)
        self.assertNotIn("items", result["warnings"])

    def test_all_projects_and_current_inclusion(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            parser = session_search.build_parser()
            args = parser.parse_args([
                "--sessions-root", str(root), "--all-projects", "--include-current", "--query", "project"
            ])
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(args, now=self.NOW)
        self.assertEqual(result["summary"]["files_selected"], 3)
        self.assertEqual(result["summary"]["matched_sessions"], 1)
        self.assertIsNone(result["scope"]["cwd"])

    def test_period_is_based_on_entry_timestamp(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(self.args(
                    root, project_a, "--include-evidence", "--days", "2", "--query", "failure"
                ), now=self.NOW)
        self.assertEqual(result["summary"]["matched_entries"], 1)
        self.assertEqual(result["results"][0]["entry_id"], "b3")

    def test_tool_error_filter_and_latest_branch_marker(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(self.args(
                    root, project_a, "--include-evidence", "--error", "--tool", "BASH"
                ), now=self.NOW)
        self.assertEqual(result["summary"]["tool_errors"], {"bash": 1})
        self.assertEqual(result["summary"]["matched_events"], 1)
        self.assertTrue(result["results"][0]["on_latest_leaf"])
        self.assertEqual(result["results"][0]["event"], "tool_error")

    def test_tool_error_sessions_count_files_once_per_filtered_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, tools in enumerate((("BASH", "bash", "read"), ("bash",))):
                # Identical header IDs deliberately remain separate session files.
                write_session(root / f"errors-{index}.jsonl", header("same-id", root), [
                    message(
                        f"e{i}", None, "2026-08-14T00:00:00Z", "toolResult",
                        "failure" if i != 1 else "retry", toolName=tool, isError=True,
                    )
                    for i, tool in enumerate(tools)
                ])
            cases = (
                ((), {"bash": 3, "read": 1}, {"bash": 2, "read": 1}),
                (("--error", "--tool", "BASH", "--tool", "read"),
                 {"bash": 3, "read": 1}, {"bash": 2, "read": 1}),
                (("--query", "retry"), {"bash": 1}, {"bash": 1}),
                (("--tool", "read", "--role", "toolResult"), {"read": 1}, {"read": 1}),
                (("--role", "assistant"), {}, {}),
                (("--days", "0"), {}, {}),
                (("--query", "absent"), {}, {}),
            )
            for flags, errors, sessions in cases:
                with self.subTest(flags=flags):
                    result = session_search.aggregate(self.args(root, root, *flags), now=self.NOW)
                    self.assertEqual(result["summary"]["tool_errors"], errors)
                    self.assertEqual(result["summary"]["tool_error_sessions"], sessions)
                    self.assertEqual(result["results"], [])
                    self.assertNotIn(str(root), json.dumps(result))
                    self.assertNotIn("same-id", json.dumps(result))

    def test_empty_assistant_errors_are_recorded(self):
        session = {"session_id": "synthetic-session", "file": "/tmp/synthetic-session.jsonl"}
        for content in ([], "", [{"type": "thinking", "thinking": "internal reasoning"}]):
            for metadata in ({"stopReason": "error"}, {"isError": True}):
                with self.subTest(content=content, metadata=metadata):
                    entry = message("e1", None, "2026-08-10T00:00:00Z", "assistant", content, **metadata)
                    events = session_search.events_for_entry(entry, session, True)
                    self.assertEqual(len(events), 1)
                    self.assertEqual(events[0]["event"], "message")
                    self.assertTrue(events[0]["is_error"])
                    self.assertEqual(events[0]["searchable"], "")
                    self.assertEqual(events[0]["evidence_raw"], "")

    def test_assistant_error_messages_are_searchable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = [
                message(
                    "e1", None, "2026-08-10T00:00:00Z", "assistant", [],
                    stopReason="error", errorMessage="Provider rate limit exceeded",
                ),
                message(
                    "e2", "e1", "2026-08-10T00:00:01Z", "assistant",
                    [{"type": "text", "text": "Partial answer"}],
                    stopReason="error", errorMessage="Provider rate limit exceeded",
                ),
            ]
            write_session(root / "errors.jsonl", header("synthetic-errors", root), entries)
            for filters in (
                ("--error",),
                ("--error", "--query", "RATE LIMIT"),
                ("--query", "rate limit", "--role", "ASSISTANT"),
            ):
                with self.subTest(filters=filters):
                    result = session_search.aggregate(self.args(root, root, *filters), now=self.NOW)
                    self.assertEqual(result["summary"]["matched_sessions"], 1)
                    self.assertEqual(result["summary"]["matched_entries"], 2)
                    self.assertEqual(result["summary"]["matched_events"], 2)
                    self.assertEqual(result["summary"]["roles"], {"assistant": 2})
                    self.assertEqual(result["summary"]["tool_errors"], {})
                    self.assertEqual(result["results"], [])

    def test_assistant_error_evidence_is_masked_and_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "errors.jsonl"
            write_session(path, header("synthetic-private-session", root), [
                message(
                    "e1", None, "2026-08-10T00:00:00Z", "assistant",
                    [{"type": "text", "text": "Partial answer"}],
                    stopReason="error", errorMessage="Provider failed token=SYNTHETIC_ERROR_SECRET",
                ),
            ])
            filters = ("--error", "--query", "SYNTHETIC_ERROR_SECRET")
            summary = session_search.aggregate(self.args(root, root, *filters), now=self.NOW)
            evidence = session_search.aggregate(self.args(
                root, root, *filters, "--include-evidence"
            ), now=self.NOW)
        self.assertEqual(summary["summary"]["matched_entries"], 1)
        self.assertFalse(summary["evidence_included"])
        self.assertTrue(summary["summary"]["evidence_omitted"])
        self.assertEqual(summary["results"], [])
        serialized = json.dumps(summary)
        for private_value in (
            str(root), str(path), "synthetic-private-session", "Partial answer", "Provider failed",
            "SYNTHETIC_ERROR_SECRET",
        ):
            self.assertNotIn(private_value, serialized)
        self.assertTrue(evidence["evidence_included"])
        self.assertEqual(evidence["summary"]["matched_entries"], 1)
        self.assertEqual(evidence["results"][0]["evidence"], "Partial answer Provider failed token=[REDACTED]")
        self.assertNotIn("SYNTHETIC_ERROR_SECRET", json.dumps(evidence))

    def test_assistant_error_message_alone_does_not_mark_an_error(self):
        session = {"session_id": "synthetic-session", "file": "/tmp/synthetic-session.jsonl"}
        filters = session_search.EventFilters.from_args(session_search.build_parser().parse_args(["--error"]))
        for stop_reason in ("stop", "aborted"):
            with self.subTest(stop_reason=stop_reason):
                entry = message(
                    "e1", None, "2026-08-10T00:00:00Z", "assistant", "Partial answer",
                    stopReason=stop_reason, errorMessage="Synthetic diagnostic",
                )
                events = session_search.events_for_entry(entry, session, True)
                self.assertEqual(len(events), 1)
                self.assertFalse(events[0]["is_error"])
                self.assertFalse(session_search.event_matches(events[0], filters))

    def test_non_string_assistant_error_messages_are_ignored(self):
        session = {"session_id": "synthetic-session", "file": "/tmp/synthetic-session.jsonl"}
        for error_message in (None, False, 42, {}, []):
            with self.subTest(error_message=error_message):
                entry = message(
                    "e1", None, "2026-08-10T00:00:00Z", "assistant", "Partial answer",
                    stopReason="error", errorMessage=error_message,
                )
                events = session_search.events_for_entry(entry, session, True)
                self.assertEqual(len(events), 1)
                self.assertTrue(events[0]["is_error"])
                self.assertEqual(events[0]["searchable"], "Partial answer")
                self.assertEqual(events[0]["evidence_raw"], "Partial answer")

    def test_direct_skill_and_file_read_are_separate(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(self.args(
                    root, project_a, "--include-evidence", "--skill", "alpha"
                ), now=self.NOW)
        self.assertEqual(result["summary"]["direct_skill_calls"], {"alpha": 1})
        self.assertEqual(result["summary"]["skill_file_reads"], {"alpha": 1})
        self.assertEqual(result["summary"]["skill_file_read_attempts"], {"alpha": 1})
        self.assertEqual(result["summary"]["skill_file_read_successes"], {"alpha": 1})
        self.assertEqual(result["summary"]["skill_file_read_errors"], {})
        events = {item["event"]: item for item in result["results"]}
        self.assertFalse(events["skill_file_read"]["on_latest_leaf"])
        self.assertIn("direct_skills", events["message"])

    def test_direct_skill_detection_requires_user_role_and_full_pi_envelope(self):
        envelope = skill_envelope("alpha", "/tmp/skills/alpha/SKILL.md", "Instructions") + "\n\nuser arguments"
        session = {"session_id": "session", "file": "/tmp/session.jsonl"}
        generic_user = message("u1", None, "2026-08-10T00:00:00Z", "user", 'Discuss <skill name="alpha">')
        assistant_example = message("a1", None, "2026-08-10T00:00:00Z", "assistant", envelope)
        direct_user = message("u2", None, "2026-08-10T00:00:00Z", "user", envelope)

        self.assertEqual(session_search.events_for_entry(generic_user, session, True)[0]["direct_skills"], [])
        self.assertEqual(session_search.events_for_entry(assistant_example, session, True)[0]["direct_skills"], [])
        self.assertEqual(session_search.events_for_entry(direct_user, session, True)[0]["direct_skills"], ["alpha"])

    def test_masking_happens_before_output(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(self.args(
                    root, project_a, "--include-evidence", "--skill", "alpha"
                ), now=self.NOW)
        serialized = json.dumps(result)
        self.assertTrue(result["evidence_included"])
        self.assertEqual(result["scope"]["cwd"], str(project_a.resolve()))
        self.assertIn("session-a", serialized)
        self.assertNotIn("TOPSECRET123456", serialized)
        self.assertNotIn("KEY_SHOULD_HIDE_123", serialized)
        self.assertIn("REDACTED", serialized)

    def test_aggregate_evidence_masks_quoted_password_and_all_cookies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = 'password="FAKE FIRST SECOND"\nCookie: session=FAKE_A; sid=FAKE_B'
            write_session(root / 'secrets.jsonl', header('synthetic', root), [
                message('e1', None, '2026-08-14T00:00:00Z', 'user', raw),
            ])
            result = session_search.aggregate(self.args(root, root, '--include-evidence'), now=self.NOW)
        self.assertEqual(result['results'][0]['evidence'],
                         'password=[REDACTED] Cookie: [REDACTED]')

    def test_query_centered_evidence_is_opt_in_and_keeps_and_filtering(self):
        raw = "prefix " * 100 + "한글 NEEDLE context " + "middle " * 100 + "distant"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_session(root / "long.jsonl", header("synthetic-long", root), [
                message("e1", None, "2026-08-14T00:00:00Z", "user", raw),
            ])
            flags = ("--query", "distant", "--query", "한글 needle")
            with patch.object(session_common, "mask_and_shorten", wraps=session_common.mask_and_shorten) as shorten:
                summary = session_search.aggregate(self.args(root, root, *flags), now=self.NOW)
                shorten.assert_not_called()
            result = session_search.aggregate(self.args(
                root, root, *flags, "--include-evidence"
            ), now=self.NOW)
            no_match = session_search.aggregate(self.args(
                root, root, *flags, "--query", "absent", "--include-evidence"
            ), now=self.NOW)
        self.assertEqual(summary["results"], [])
        self.assertEqual(summary["summary"]["matched_events"], 1)
        evidence = result["results"][0]["evidence"]
        self.assertIn("한글 NEEDLE context", evidence)
        self.assertNotIn("distant", evidence)
        self.assertTrue(evidence.startswith("…"))
        self.assertTrue(evidence.endswith("…"))
        self.assertLessEqual(len(evidence), session_common.MAX_EVIDENCE_CHARS)
        self.assertEqual(no_match["results"], [])

    def test_tool_arguments_are_serialized_only_for_queries_or_evidence(self):
        with fixture_tree() as (root, project_a, _, _, _, _):
            with patch.object(session_search.json, "dumps", side_effect=AssertionError("serialized")):
                counts = session_search.aggregate(self.args(root, project_a, "--tool", "bash"), now=self.NOW)
            queried = session_search.aggregate(
                self.args(root, project_a, "--query", "KEY_SHOULD_HIDE_123"), now=self.NOW,
            )
            batch = session_search.aggregate(self.args(
                root, project_a, "--batch-filter", '{"tool": ["bash"]}',
                "--batch-filter", '{"query": ["KEY_SHOULD_HIDE_123"]}',
            ), now=self.NOW)
        self.assertEqual(counts["summary"]["tool_calls"], {"bash": 1})
        self.assertEqual(queried["summary"]["matched_events"], 1)
        self.assertEqual([item["summary"]["matched_events"] for item in batch["batches"]],
                         [counts["summary"]["matched_events"], 1])

    def test_limit_summary_only_no_match_and_warning(self):
        with fixture_tree() as (root, project_a, _, primary, _, current):
            before = primary.stat().st_mtime_ns
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                limited = session_search.aggregate(self.args(
                    root, project_a, "--include-evidence", "--limit", "1"
                ), now=self.NOW)
                summary_only = session_search.aggregate(self.args(root, project_a, "--summary-only"), now=self.NOW)
                no_match = session_search.aggregate(self.args(root, project_a, "--query", "never-present"), now=self.NOW)
            after = primary.stat().st_mtime_ns
        self.assertEqual(limited["summary"]["results_returned"], 1)
        self.assertTrue(limited["summary"]["truncated"])
        self.assertTrue(limited["summary"]["evidence_truncated"])
        self.assertFalse(limited["summary"]["evidence_omitted"])
        self.assertEqual(summary_only["results"], [])
        self.assertFalse(summary_only["evidence_included"])
        self.assertTrue(summary_only["summary"]["evidence_omitted"])
        self.assertFalse(summary_only["summary"]["evidence_truncated"])
        self.assertFalse(summary_only["summary"]["truncated"])
        self.assertEqual(no_match["summary"]["matched_entries"], 0)
        self.assertGreaterEqual(limited["warnings"]["count"], 1)
        self.assertIn("items", limited["warnings"])
        self.assertEqual(before, after)

    def test_bounded_results_keep_only_newest_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            project.mkdir()
            entries = [
                message(
                    f"e{index}",
                    f"e{index - 1}" if index else None,
                    f"2026-08-{index + 1:02d}T00:00:00Z",
                    "user",
                    f"match {index}",
                )
                for index in range(10)
            ]
            write_session(root / "bounded.jsonl", header("bounded", project), entries)
            result = session_search.aggregate(self.args(
                root, project, "--include-evidence", "--query", "match", "--limit", "3"
            ), now=self.NOW)
        self.assertEqual(result["summary"]["matched_events"], 10)
        self.assertEqual(result["summary"]["results_returned"], 3)
        self.assertEqual([item["entry_id"] for item in result["results"]], ["e9", "e8", "e7"])

    def test_near_header_utf8_failure_keeps_in_scope_partial_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "damaged.jsonl"
            write_session(path, header("damaged", root), [
                message("u", None, "2026-08-10T00:00:00Z", "user", "needle"),
            ])
            with path.open("ab") as handle:
                handle.write(b"\xff\n")
            result = session_search.aggregate(self.args(root, root, "--include-evidence"), now=self.NOW)
        self.assertEqual(result["summary"]["files_selected"], 1)
        self.assertEqual(result["summary"]["matched_events"], 1)
        self.assertEqual(result["warnings"]["by_kind"], {"unreadable_file": 1})
        self.assertIsNone(result["results"][0]["on_latest_leaf"])

    def test_unselected_corrupt_body_is_not_decoded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "foreign.jsonl"
            path.write_bytes((json.dumps(header("foreign", root / "foreign")) + "\n").encode() + b"\xff\n")
            result = session_search.aggregate(self.args(root, root), now=self.NOW)
        self.assertEqual(result["summary"]["files_selected"], 0)
        self.assertEqual(result["warnings"]["count"], 0)

    def test_late_utf8_failure_preserves_consistent_partial_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            damaged = root / "a-damaged.jsonl"
            write_session(damaged, header("damaged", root), [
                message("a", None, "2026-08-10T00:00:00Z", "toolResult", "needle",
                        toolName="read", isError=True),
                message("b", "a", "2026-08-10T00:00:01Z", "toolResult", "needle",
                        toolName="read", isError=True),
                # Place the decode error far beyond the header and the matching entries.
                *[{"type": "custom", "id": f"p{i}", "parentId": "b", "padding": "x" * 300}
                  for i in range(100)],
            ])
            with damaged.open("ab") as handle:
                handle.write(b"\xff\n")
            write_session(root / "b-good.jsonl", header("good", root), [
                message("c", None, "2026-08-10T00:00:02Z", "user", "needle"),
            ])
            for flags in [(), ("--include-evidence",), ("--include-evidence", "--limit", "0")]:
                with self.subTest(flags=flags):
                    result = session_search.aggregate(self.args(root, root, "--query", "needle", *flags), now=self.NOW)
                    summary = result["summary"]
                    self.assertEqual(summary["matched_sessions"], 2)
                    self.assertEqual(summary["matched_entries"], 3)
                    self.assertEqual(summary["matched_events"], 3)
                    self.assertEqual(summary["tool_errors"], {"read": 2})
                    self.assertEqual(summary["tool_error_sessions"], {"read": 1})
                    self.assertEqual(result["warnings"]["by_kind"], {"unreadable_file": 1})
                    if flags == ("--include-evidence",):
                        events = {event["entry_id"]: event for event in result["results"]}
                        self.assertIsNone(events["a"]["on_latest_leaf"])
                        self.assertIsNone(events["b"]["on_latest_leaf"])
                        self.assertTrue(events["c"]["on_latest_leaf"])
                    else:
                        self.assertEqual(result["results"], [])
                    if not flags:
                        self.assertNotIn(str(root), json.dumps(result))

    def test_late_oserror_keeps_matches_but_not_branch_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "session.jsonl"
            write_session(path, header("session", root), [
                message("a", None, "2026-08-10T00:00:00Z", "user", "needle"),
            ])
            content = path.read_bytes()

            class FailingReader(io.BytesIO):
                def __next__(self):
                    line = self.readline()
                    if not line:
                        raise OSError("synthetic read failure")
                    return line

            with patch.object(session_common, "open_session_file", return_value=FailingReader(content)):
                result = session_search.aggregate(self.args(root, root, "--include-evidence"), now=self.NOW)
            self.assertEqual(result["summary"]["matched_sessions"], 1)
            self.assertEqual(result["summary"]["matched_events"], 1)
            self.assertIsNone(result["results"][0]["on_latest_leaf"])
            self.assertEqual(result["warnings"]["by_kind"], {"unreadable_file": 1})

    def test_file_boundaries_reset_skill_calls_identities_and_branches(self):
        for version in (1, 2, 3):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                location = "/custom/folder/SKILL.md"
                timestamp = "2026-08-10T00:00:00Z"
                head = {**header("reused-session-id", root), "version": version}
                call = [{"type": "toolCall", "id": "shared-call", "name": "read",
                         "arguments": {"path": location}}]
                write_session(root / "a-first.jsonl", head, [
                    message("shared", None, timestamp, "user", "first root"),
                    message("alias", "shared", timestamp, "user", skill_envelope("declared", location)),
                    message("call", "alias", timestamp, "assistant", call),
                ])
                second = root / "b-second.jsonl"
                write_session(second, head, [
                    message("shared", None, timestamp, "user", "second root"),
                    message("orphan", "shared", timestamp, "toolResult", "body",
                            toolName="read", toolCallId="shared-call", isError=False),
                    message("call", "alias", timestamp, "assistant", call),
                    {"type": "custom", "id": "end", "parentId": "alias"},
                ])
                result = session_search.aggregate(self.args(root, root, "--include-evidence"), now=self.NOW)
                self.assertEqual(result["summary"]["matched_sessions"], 2)
                self.assertEqual(result["summary"]["skill_file_read_attempts"], {"declared": 1, "folder": 1})
                self.assertEqual(result["summary"]["skill_file_read_successes"], {})
                events = {event["entry_id"]: event for event in result["results"] if event["file"] == str(second)}
                self.assertEqual(set(events), {"shared", "orphan", "call"})
                self.assertNotIn("skill_file_read", events["orphan"])
                self.assertEqual(events["call"]["skill_file_read"], "folder")
                for event in events.values():
                    self.assertIs(event["on_latest_leaf"], version == 1)

    def test_unknown_scope_io_failure_does_not_inherit_previous_file_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_session(root / "a-selected.jsonl", header("selected", root), [
                message("entry", None, "2026-08-10T00:00:00Z", "user", "needle"),
            ])
            failing = root / "b-unknown.jsonl"
            write_session(failing, header("unknown", root), [])
            original_open = session_common.open_session_file

            class FailingHeader(io.BytesIO):
                def readline(self, *args, **kwargs):
                    raise OSError("synthetic header failure")

            for failure in ("open", "header"):
                for all_projects in (False, True):
                    with self.subTest(failure=failure, all_projects=all_projects):
                        def open_file(path, *args, **kwargs):
                            if path == failing:
                                if failure == "open":
                                    raise OSError("synthetic open failure")
                                return FailingHeader()
                            return original_open(path, *args, **kwargs)

                        scope = ["--all-projects"] if all_projects else ["--cwd", str(root)]
                        args = session_search.build_parser().parse_args([
                            "--sessions-root", str(root), "--include-evidence", *scope,
                        ])
                        with patch.object(session_common, "open_session_file", new=open_file):
                            result = session_search.aggregate(args, now=self.NOW)
                        self.assertEqual(result["summary"]["files_discovered"], 2)
                        self.assertEqual(result["summary"]["files_selected"], 1)
                        self.assertEqual(result["summary"]["matched_events"], 1)
                        self.assertTrue(result["results"][0]["on_latest_leaf"])
                        self.assertEqual(result["warnings"]["by_kind"], {"unreadable_file": 1} if all_projects else {})
                        self.assertEqual(result["warnings"]["items"],
                                         [{"path": str(failing), "kind": "unreadable_file"}] if all_projects else [])

    def test_invalid_entry_ids_do_not_abort_aggregate(self):
        for version in (1, 2, 3):
            for bad_id in ([], {}, None, 42, True):
                with self.subTest(version=version, bad_id=bad_id), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    head = {**header("session", root), "version": version}
                    malformed = message("bad", None, "2026-08-10T00:00:00Z", "user", "needle")
                    malformed["id"] = bad_id
                    write_session(root / "session.jsonl", head, [
                        malformed,
                        message("good", None, "2026-08-10T00:00:01Z", "user", "needle"),
                    ])
                    for flags in [(), ("--include-evidence",)]:
                        result = session_search.aggregate(self.args(root, root, *flags), now=self.NOW)
                        self.assertEqual(result["summary"]["matched_sessions"], 1)
                        self.assertEqual(result["summary"]["matched_events"], 2)
                        self.assertEqual(result["warnings"]["by_kind"],
                                         {"invalid_entry_id": 1} if version >= 2 else {})
                        if flags:
                            self.assertTrue(result["results"][0]["on_latest_leaf"])
                            self.assertEqual(result["results"][1]["entry_id"], bad_id)
                            self.assertIs(result["results"][1]["on_latest_leaf"], True if version == 1 else None)

    def test_unselected_session_body_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            selected_project = base / "selected"
            other_project = base / "other"
            selected_project.mkdir()
            other_project.mkdir()
            write_session(root / "selected.jsonl", header("selected", selected_project), [])
            write_session(root / "foreign.jsonl", header("foreign", other_project), [], malformed=True)
            result = session_search.aggregate(self.args(root, selected_project), now=self.NOW)
        self.assertEqual(result["summary"]["files_selected"], 1)
        self.assertNotIn("invalid_json_line", result["warnings"]["by_kind"])

    def test_skill_file_read_outcomes_are_correlated(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            project.mkdir()
            entries = [
                message("a1", None, "2026-08-10T00:00:00Z", "assistant", [{
                    "type": "toolCall",
                    "id": "failed-read",
                    "name": "read",
                    "arguments": {"path": "/tmp/skills/Alpha/SKILL.md"},
                }], stopReason="toolUse"),
                message(
                    "a2",
                    "a1",
                    "2026-08-10T00:00:01Z",
                    "toolResult",
                    [{"type": "text", "text": "permission denied"}],
                    toolCallId="failed-read",
                    toolName="read",
                    isError=True,
                ),
            ]
            write_session(root / "failed-read.jsonl", header("failed-read", project), entries)
            result = session_search.aggregate(self.args(
                root, project, "--include-evidence", "--skill", "ALPHA"
            ), now=self.NOW)
        self.assertEqual(result["summary"]["skill_file_read_attempts"], {"alpha": 1})
        self.assertEqual(result["summary"]["skill_file_read_successes"], {})
        self.assertEqual(result["summary"]["skill_file_read_errors"], {"alpha": 1})
        self.assertEqual(result["summary"]["tool_error_sessions"], {"read": 1})
        self.assertEqual({item["event"] for item in result["results"]}, {"skill_file_read", "tool_error"})

    def test_session_versions_are_explicit_and_future_versions_are_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            project.mkdir()
            legacy_header = header("legacy", project)
            legacy_header.pop("version")
            write_session(
                root / "legacy.jsonl",
                legacy_header,
                [message("legacy-1", None, "2026-08-10T00:00:00Z", "user", "legacy match")],
            )
            future_header = header("future", project)
            future_header["version"] = 99
            write_session(
                root / "future.jsonl",
                future_header,
                [message("future-1", None, "2026-08-10T00:00:00Z", "user", "future match")],
            )
            result = session_search.aggregate(self.args(
                root, project, "--include-evidence", "--query", "match"
            ), now=self.NOW)
        self.assertEqual(result["summary"]["files_selected"], 1)
        self.assertEqual(result["summary"]["matched_events"], 1)
        self.assertTrue(result["results"][0]["on_latest_leaf"])
        self.assertEqual(result["warnings"]["by_kind"], {
            "missing_session_version": 1,
            "unsupported_session_version": 1,
        })

    def test_default_scope_does_not_report_foreign_or_unknown_project_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            foreign = base / "foreign"
            project.mkdir()
            foreign.mkdir()
            write_session(root / "local.jsonl", header("local", project), [
                message("m1", None, "2026-08-10T00:00:00Z", "user", "local match"),
            ])
            future = header("future", foreign)
            future["version"] = 99
            write_session(root / "foreign-future.jsonl", future, [])
            legacy = header("legacy", foreign)
            legacy.pop("version")
            write_session(root / "foreign-legacy.jsonl", legacy, [])
            (root / "broken.jsonl").write_text("not-json\n", encoding="utf-8")
            (root / "undecodable.jsonl").write_bytes(b"\xff\n")
            scoped = session_search.aggregate(self.args(root, project, "--include-evidence"), now=self.NOW)
            all_projects = session_search.aggregate(session_search.build_parser().parse_args([
                "--sessions-root", str(root), "--all-projects", "--include-evidence",
            ]), now=self.NOW)
        self.assertEqual(scoped["summary"]["files_selected"], 1)
        self.assertEqual(scoped["warnings"]["count"], 0)
        self.assertEqual(scoped["warnings"]["items"], [])
        self.assertEqual(all_projects["warnings"]["by_kind"], {
            "invalid_header": 1,
            "missing_session_version": 1,
            "unreadable_file": 1,
            "unsupported_session_version": 1,
        })

    def test_warning_details_are_deduplicated_and_capped(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            project.mkdir()
            write_session(root / "valid.jsonl", header("valid", project), [])
            for index in range(session_common.MAX_WARNING_ITEMS + 5):
                path = root / f"broken-{index}.jsonl"
                path.write_text("invalid\n", encoding="utf-8")
            repeated = root / "repeated.jsonl"
            repeated.write_text("invalid\ninvalid\n", encoding="utf-8")
            parser = session_search.build_parser()
            result = session_search.aggregate(parser.parse_args([
                "--sessions-root", str(root), "--all-projects", "--include-evidence"
            ]), now=self.NOW)
        self.assertEqual(result["warnings"]["count"], session_common.MAX_WARNING_ITEMS + 6)
        self.assertEqual(len(result["warnings"]["items"]), session_common.MAX_WARNING_ITEMS)
        self.assertTrue(result["warnings"]["truncated"])
        self.assertEqual(result["warnings"]["by_kind"], {
            "invalid_header": session_common.MAX_WARNING_ITEMS + 6
        })

    def test_empty_session_root_returns_zero_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = session_search.aggregate(self.args(root, root), now=self.NOW)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["files_discovered"], 0)
        self.assertEqual(result["summary"]["tool_error_sessions"], {})
        self.assertEqual(result["summary"]["matched_events"], 0)
        self.assertEqual(result["results"], [])

    def test_evidence_and_summary_only_flags_are_mutually_exclusive(self):
        parser = session_search.build_parser()
        with self.assertRaises(session_common.InvalidArgumentError):
            parser.parse_args(["--include-evidence", "--summary-only"])

    def test_negative_days_and_limit_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "--days"):
                session_search.aggregate(self.args(root, root, "--days", "-1"), now=self.NOW)
            with self.assertRaisesRegex(ValueError, "--limit"):
                session_search.aggregate(self.args(root, root, "--limit", "-1"), now=self.NOW)

    def test_non_finite_days_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for value in ("nan", "inf", "-inf", "-infinity", "-nan"):
                with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, "^--days must be a finite non-negative number$"
                ):
                    session_search.aggregate(self.args(root, root, f"--days={value}"), now=self.NOW)

    def assert_invalid_cli_argument(self, missing_root: Path, arguments: list[str]):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--sessions-root",
                str(missing_root),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(len(completed.stdout.strip().splitlines()), 1)
        self.assertEqual(json.loads(completed.stdout), {
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "Arguments are invalid.",
            },
            "results": [],
            "status": "error",
        })

    def test_non_finite_days_cli_emits_one_json_error(self):
        with tempfile.TemporaryDirectory() as temp:
            missing_root = Path(temp) / "missing-sessions"
            for value in ("nan", "inf", "-inf", "-infinity", "-nan"):
                for options in (["--days", value], [f"--days={value}"]):
                    with self.subTest(options=options):
                        self.assert_invalid_cli_argument(missing_root, options)

    def test_parse_and_range_errors_emit_one_json_error(self):
        with tempfile.TemporaryDirectory() as temp:
            missing_root = Path(temp) / "missing-sessions"
            cases = (
                ["--days", "abc"],
                ["--limit", "abc"],
                ["--unknown-option"],
                ["--days", "1000000000"],
            )
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    self.assert_invalid_cli_argument(missing_root, arguments)

    def test_help_retains_argparse_text_output(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        self.assertIn("usage:", completed.stdout)
        self.assertIn("--sessions-root PATH", completed.stdout)

    def test_total_parse_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "broken.jsonl").write_text("not-json\n", encoding="utf-8")
            args = self.args(root, root)
            with self.assertRaisesRegex(RuntimeError, "all candidate"):
                session_search.aggregate(args, now=self.NOW)

    def test_cli_errors_do_not_expose_exception_paths(self):
        stdout = io.StringIO()
        with patch.object(
            session_search,
            "aggregate",
            side_effect=OSError("could not open /home/private-user/sessions/private.jsonl"),
        ), redirect_stdout(stdout):
            code = session_search.main([])
        result = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "SESSION_STORAGE_UNAVAILABLE")
        self.assertNotIn("/home/private-user", stdout.getvalue())

    def test_cli_emits_one_json_object(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            env = {**os.environ, "PI_SESSION_FILE": str(current), "PYTHONDONTWRITEBYTECODE": "1"}
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--sessions-root", str(root), "--cwd", str(project_a), "--query", "never-present"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        result = json.loads(completed.stdout)
        self.assertEqual(result["summary"]["matched_entries"], 0)
        self.assertEqual(len(completed.stdout.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
