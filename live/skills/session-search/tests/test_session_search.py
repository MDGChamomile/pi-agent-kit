from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "session_search.py"
SPEC = importlib.util.spec_from_file_location("session_search", SCRIPT)
assert SPEC and SPEC.loader
session_search = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_search)


def header(session_id: str, cwd: Path) -> dict:
    return {
        "type": "session",
        "version": 3,
        "id": session_id,
        "timestamp": "2026-08-01T00:00:00Z",
        "cwd": str(cwd),
    }


def message(entry_id: str, parent_id: str | None, timestamp: str, role: str, content, **extra) -> dict:
    payload = {"role": role, "content": content, "timestamp": 0, **extra}
    return {
        "type": "message",
        "id": entry_id,
        "parentId": parent_id,
        "timestamp": timestamp,
        "message": payload,
    }


def write_session(path: Path, head: dict, entries: list[dict], malformed: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(head) + "\n")
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
        if malformed:
            handle.write("{not-json\n")


@contextmanager
def fixture_tree():
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        root = base / "sessions"
        project_a = base / "project-a"
        project_b = base / "project-b"
        project_a.mkdir()
        project_b.mkdir()

        primary = root / "a" / "primary.jsonl"
        write_session(
            primary,
            header("session-a", project_a),
            [
                message(
                    "a1",
                    None,
                    "2026-08-10T00:00:00Z",
                    "user",
                    '<skill name="alpha" location="/tmp/skills/alpha/SKILL.md">\n'
                    'References are relative to /tmp/skills/alpha.\n\n'
                    'Investigate failures token=TOPSECRET123456\n</skill>',
                ),
                message(
                    "a2",
                    "a1",
                    "2026-08-11T00:00:00Z",
                    "assistant",
                    [
                        {"type": "text", "text": "Taking the old branch"},
                        {
                            "type": "toolCall",
                            "id": "tc-read",
                            "name": "read",
                            "arguments": {"path": "/tmp/skills/alpha/SKILL.md", "api_key": "KEY_SHOULD_HIDE_123"},
                        },
                    ],
                    stopReason="toolUse",
                ),
                message(
                    "a3",
                    "a2",
                    "2026-08-12T00:00:00Z",
                    "toolResult",
                    [{"type": "text", "text": "old result"}],
                    toolCallId="tc-read",
                    toolName="read",
                    isError=False,
                ),
                message("b2", "a1", "2026-08-13T00:00:00Z", "assistant", [
                    {"type": "toolCall", "id": "tc-bash", "name": "bash", "arguments": {"command": "false"}}
                ], stopReason="toolUse"),
                message(
                    "b3",
                    "b2",
                    "2026-08-14T00:00:00Z",
                    "toolResult",
                    [{"type": "text", "text": "Repeated FAILURE password=hunter2"}],
                    toolCallId="tc-bash",
                    toolName="bash",
                    isError=True,
                ),
            ],
            malformed=True,
        )
        other = root / "b" / "other.jsonl"
        write_session(
            other,
            header("session-b", project_b),
            [message("c1", None, "2026-08-14T12:00:00Z", "user", "failure in another project")],
        )
        current = root / "a" / "current.jsonl"
        write_session(
            current,
            header("session-current", project_a),
            [message("d1", None, "2026-08-14T13:00:00Z", "user", "current only marker")],
        )
        yield root, project_a, project_b, primary, other, current


class SessionSearchTests(unittest.TestCase):
    NOW = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def args(self, root: Path, cwd: Path, *extra: str):
        return session_search.build_parser().parse_args([
            "--sessions-root", str(root), "--cwd", str(cwd), *extra
        ])

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

    def test_direct_skill_and_file_read_are_separate(self):
        with fixture_tree() as (root, project_a, _, _, _, current):
            with patch.dict(os.environ, {"PI_SESSION_FILE": str(current)}):
                result = session_search.aggregate(self.args(
                    root, project_a, "--include-evidence", "--skill", "alpha"
                ), now=self.NOW)
        self.assertEqual(result["summary"]["direct_skill_calls"], {"alpha": 1})
        self.assertEqual(result["summary"]["skill_file_reads"], {"alpha": 1})
        events = {item["event"]: item for item in result["results"]}
        self.assertFalse(events["skill_file_read"]["on_latest_leaf"])
        self.assertIn("direct_skills", events["message"])

    def test_direct_skill_detection_requires_user_role_and_full_pi_envelope(self):
        envelope = (
            '<skill name="alpha" location="/tmp/skills/alpha/SKILL.md">\n'
            'References are relative to /tmp/skills/alpha.\n\n'
            'Instructions\n</skill>\n\nuser arguments'
        )
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

    def test_private_key_url_credentials_and_boundary_secret_are_masked(self):
        raw = (
            "https://alice:correct-horse@example.test/path "
            "-----BEGIN TEST PRIVATE KEY-----private-material-----END TEST PRIVATE KEY----- "
            + "x" * 280
            + " token=BOUNDARY_SECRET_VALUE"
        )
        masked = session_search.mask_and_shorten(raw)
        self.assertNotIn("alice", masked)
        self.assertNotIn("correct-horse", masked)
        self.assertNotIn("private-material", masked)
        self.assertNotIn("BOUNDARY_SECRET_VALUE", masked)
        self.assertLessEqual(len(masked), session_search.MAX_EVIDENCE_CHARS)

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
        self.assertEqual(summary_only["results"], [])
        self.assertFalse(summary_only["evidence_included"])
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

    def test_warning_details_are_deduplicated_and_capped(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "sessions"
            project = base / "project"
            project.mkdir()
            write_session(root / "valid.jsonl", header("valid", project), [])
            for index in range(session_search.MAX_WARNING_ITEMS + 5):
                path = root / f"broken-{index}.jsonl"
                path.write_text("invalid\n", encoding="utf-8")
            repeated = root / "repeated.jsonl"
            repeated.write_text("invalid\ninvalid\n", encoding="utf-8")
            parser = session_search.build_parser()
            result = session_search.aggregate(parser.parse_args([
                "--sessions-root", str(root), "--all-projects", "--include-evidence"
            ]), now=self.NOW)
        self.assertEqual(result["warnings"]["count"], session_search.MAX_WARNING_ITEMS + 6)
        self.assertEqual(len(result["warnings"]["items"]), session_search.MAX_WARNING_ITEMS)
        self.assertTrue(result["warnings"]["truncated"])
        self.assertEqual(result["warnings"]["by_kind"], {
            "invalid_header": session_search.MAX_WARNING_ITEMS + 6
        })

    def test_empty_session_root_returns_zero_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = session_search.aggregate(self.args(root, root), now=self.NOW)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["files_discovered"], 0)
        self.assertEqual(result["summary"]["matched_events"], 0)
        self.assertEqual(result["results"], [])

    def test_naive_timestamp_is_treated_as_utc(self):
        parsed = session_search.parse_timestamp("2026-08-15T00:00:00")
        self.assertEqual(parsed, self.NOW)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_evidence_and_summary_only_flags_are_mutually_exclusive(self):
        parser = session_search.build_parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--include-evidence", "--summary-only"])

    def test_negative_days_and_limit_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "--days"):
                session_search.aggregate(self.args(root, root, "--days", "-1"), now=self.NOW)
            with self.assertRaisesRegex(ValueError, "--limit"):
                session_search.aggregate(self.args(root, root, "--limit", "-1"), now=self.NOW)

    def test_total_parse_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "broken.jsonl").write_text("not-json\n", encoding="utf-8")
            args = self.args(root, root)
            with self.assertRaisesRegex(RuntimeError, "all candidate"):
                session_search.aggregate(args, now=self.NOW)

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
