#!/usr/bin/env python3
"""Read-only aggregation of evidence across Pi session JSONL files."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

DEFAULT_LIMIT = 20
DEFAULT_SESSIONS_ROOT = Path.home() / ".pi" / "agent" / "sessions"
MAX_EVIDENCE_CHARS = 300
MAX_WARNING_ITEMS = 100
SKILL_ENVELOPE_RE = re.compile(
    r'\A<skill name="([^"\r\n]+)" location="[^"\r\n]+">\r?\n'
    r'References are relative to [^\r\n]+\.\r?\n\r?\n'
    r'.*\r?\n</skill>(?:\r?\n\r?\n.*)?\Z',
    re.DOTALL,
)
SKILL_FILE_RE = re.compile(r"(?:^|[/\\])skills[/\\]([^/\\]+)[/\\]SKILL\.md$", re.IGNORECASE)

# Mask before truncation so a secret crossing the truncation boundary cannot leak.
MASK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----", re.I | re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I), r"\1 [REDACTED]"),
    (re.compile(r"(?i)(https?://)([^\s/@:]+):([^\s/@]+)@"), r"\1[REDACTED]@"),
    (re.compile(r'(?i)(["\']?(?:api[_-]?key|access[_-]?token|auth(?:orization)?|cookie|password|passwd|secret|token)["\']?\s*[:=]\s*)["\']?([^"\'\s,;}]+)'), r"\1[REDACTED]"),
    (re.compile(r"(?i)([?&](?:api[_-]?key|access[_-]?token|auth|password|secret|token)=)[^&#\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalized_path(value: str | Path) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def mask_and_shorten(value: str, limit: int = MAX_EVIDENCE_CHARS) -> str:
    masked = value
    for pattern, replacement in MASK_PATTERNS:
        masked = pattern.sub(replacement, masked)
    masked = re.sub(r"\s+", " ", masked).strip()
    if len(masked) > limit:
        return masked[: max(0, limit - 1)] + "…"
    return masked


def text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )


def direct_skills(text: str) -> list[str]:
    match = SKILL_ENVELOPE_RE.fullmatch(text)
    return [match.group(1)] if match else []


def skill_read_name(tool_name: str, arguments: Any) -> str | None:
    if tool_name.lower() != "read" or not isinstance(arguments, dict):
        return None
    path = arguments.get("path")
    if not isinstance(path, str):
        return None
    match = SKILL_FILE_RE.search(path)
    return match.group(1) if match else None


def latest_leaf_path(parent_by_id: dict[str, Any], leaf_id: str | None) -> set[str]:
    result: set[str] = set()
    while isinstance(leaf_id, str) and leaf_id in parent_by_id and leaf_id not in result:
        result.add(leaf_id)
        leaf_id = parent_by_id[leaf_id]
    return result


def event_matches(event: dict[str, Any], args: argparse.Namespace) -> bool:
    searchable = event["searchable"].casefold()
    if args.query and not all(query.casefold() in searchable for query in args.query):
        return False
    if args.role and event["role"].casefold() not in {value.casefold() for value in args.role}:
        return False
    if args.tool and (not event.get("tool_name") or event["tool_name"].casefold() not in {value.casefold() for value in args.tool}):
        return False
    if args.error and not event.get("is_error", False):
        return False
    if args.skill and not any(name.casefold() in {value.casefold() for value in args.skill} for name in event.get("skill_names", [])):
        return False
    return True


def events_for_entry(entry: dict[str, Any], session: dict[str, str], on_leaf: bool) -> list[dict[str, Any]]:
    if entry.get("type") != "message" or not isinstance(entry.get("message"), dict):
        return []
    message = entry["message"]
    role = str(message.get("role", "unknown"))
    base = {
        **session,
        "timestamp": entry.get("timestamp"),
        "entry_id": entry.get("id"),
        "role": role,
        "on_latest_leaf": on_leaf,
    }
    events: list[dict[str, Any]] = []
    text = text_content(message.get("content"))
    skills = direct_skills(text) if role == "user" else []
    if (text or skills) and role != "toolResult":
        events.append({
            **base,
            "event": "message",
            "tool_name": None,
            "is_error": bool(message.get("isError", False) or message.get("stopReason") == "error"),
            "skill_names": skills,
            "direct_skills": skills,
            "skill_file_read": None,
            "searchable": "\n".join([text, *skills]),
            "evidence_raw": text,
        })
    content = message.get("content")
    if role == "assistant" and isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "toolCall":
                continue
            tool_name = str(block.get("name", "unknown"))
            arguments = block.get("arguments", {})
            arguments_text = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
            read_skill = skill_read_name(tool_name, arguments)
            events.append({
                **base,
                "event": "skill_file_read" if read_skill else "tool_call",
                "tool_name": tool_name,
                "is_error": False,
                "skill_names": [read_skill] if read_skill else [],
                "direct_skills": [],
                "skill_file_read": read_skill,
                "searchable": "\n".join(filter(None, [tool_name, arguments_text, read_skill])),
                "evidence_raw": arguments_text,
            })
    if role == "toolResult":
        tool_name = str(message.get("toolName", "unknown"))
        events.append({
            **base,
            "event": "tool_error" if message.get("isError") else "tool_result",
            "tool_name": tool_name,
            "is_error": bool(message.get("isError", False)),
            "skill_names": [],
            "direct_skills": [],
            "skill_file_read": None,
            "searchable": "\n".join([tool_name, text]),
            "evidence_raw": text,
        })
    return events


class WarningCollector:
    def __init__(self) -> None:
        self._count = 0
        self._counts: Counter[str] = Counter()
        self._items: list[dict[str, str]] = []
        self._current_path: str | None = None
        self._current_kinds: set[str] = set()

    def begin_file(self, path: Path) -> None:
        self._current_path = str(path)
        self._current_kinds.clear()

    def add(self, path: Path, kind: str) -> None:
        path_text = str(path)
        if path_text != self._current_path:
            self.begin_file(path)
        if kind in self._current_kinds:
            return
        self._current_kinds.add(kind)
        self._count += 1
        self._counts[kind] += 1
        if len(self._items) < MAX_WARNING_ITEMS:
            self._items.append({"path": path_text, "kind": kind})

    @property
    def count(self) -> int:
        return self._count

    def output(self, include_items: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "count": self.count,
            "by_kind": dict(sorted(self._counts.items())),
        }
        if include_items:
            result["items"] = list(self._items)
            result["truncated"] = self.count > len(self._items)
        return result


def read_session_metadata(
    path: Path,
    warnings: WarningCollector,
) -> tuple[dict[str, Any] | None, int, set[str]]:
    entry_count = 0
    parent_by_id: dict[str, Any] = {}
    leaf_id: str | None = None
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            try:
                header = json.loads(first)
            except (json.JSONDecodeError, TypeError):
                warnings.add(path, "invalid_header")
                return None, 0, set()
            if not isinstance(header, dict) or header.get("type") != "session":
                warnings.add(path, "invalid_header")
                return None, 0, set()
            for line in handle:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    warnings.add(path, "invalid_json_line")
                    continue
                if not isinstance(entry, dict):
                    warnings.add(path, "invalid_entry")
                    continue
                entry_count += 1
                entry_id = entry.get("id")
                if isinstance(entry_id, str):
                    parent_by_id[entry_id] = entry.get("parentId")
                    leaf_id = entry_id
    except (OSError, UnicodeError):
        warnings.add(path, "unreadable_file")
        return None, 0, set()
    return header, entry_count, latest_leaf_path(parent_by_id, leaf_id)


def iter_session_entries(path: Path, warnings: WarningCollector) -> Iterator[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            handle.readline()
            for line in handle:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    warnings.add(path, "invalid_json_line")
                    continue
                if isinstance(entry, dict):
                    yield entry
                else:
                    warnings.add(path, "invalid_entry")
    except (OSError, UnicodeError):
        warnings.add(path, "unreadable_file")


def result_view(event: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: event.get(key)
        for key in ("session_id", "file", "timestamp", "entry_id", "role", "event", "tool_name", "is_error", "on_latest_leaf")
    }
    if event.get("direct_skills"):
        result["direct_skills"] = event["direct_skills"]
    if event.get("skill_file_read"):
        result["skill_file_read"] = event["skill_file_read"]
    result["evidence"] = mask_and_shorten(event.get("evidence_raw", ""))
    return result


class SessionArgumentParser(argparse.ArgumentParser):
    def _parse_optional(self, arg_string: str):
        # argparse recognizes ordinary negative numbers as values but treats
        # -inf/-nan as options. Let the explicit finite-value check handle them.
        if arg_string.lower() in {"-inf", "-infinity", "-nan"}:
            return None
        return super()._parse_optional(arg_string)


def build_parser() -> argparse.ArgumentParser:
    parser = SessionArgumentParser(description="Aggregate local evidence across multiple Pi sessions; use /resume for a single session.")
    parser.add_argument("-q", "--query", action="append", default=[], help="case-insensitive literal filter; repeat to require every value (AND)")
    parser.add_argument("--days", type=float, help="include entries from the last N days, based on entry timestamps")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--all-projects", action="store_true", help="search sessions from every project")
    scope.add_argument("--cwd", default=os.getcwd(), help="project cwd to match exactly (default: current cwd)")
    parser.add_argument("--role", action="append", default=[], help="message role filter; repeat for alternatives")
    parser.add_argument("--tool", action="append", default=[], help="tool-name filter; repeat for alternatives")
    parser.add_argument("--error", action="store_true", help="include only error events")
    parser.add_argument("--skill", action="append", default=[], help="direct-invocation or skill-file-read name; repeat for alternatives")
    parser.add_argument("--include-current", action="store_true", help="include PI_SESSION_FILE (excluded by default)")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"maximum evidence results with --include-evidence (default: {DEFAULT_LIMIT})")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument(
        "--include-evidence",
        action="store_true",
        help="include masked snippets, session identifiers, and local paths; requires explicit user consent in agent workflows",
    )
    evidence.add_argument(
        "--summary-only",
        action="store_true",
        help="explicitly select the path-free summary output (the default; retained for compatibility)",
    )
    parser.add_argument("--sessions-root", type=Path, default=DEFAULT_SESSIONS_ROOT, help=argparse.SUPPRESS)
    return parser


def aggregate(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    root = args.sessions_root.expanduser()
    if not root.is_dir():
        raise RuntimeError("session root is unavailable")
    target_cwd = normalized_path(args.cwd)
    current = normalized_path(os.environ["PI_SESSION_FILE"]) if os.environ.get("PI_SESSION_FILE") else None
    cutoff = None
    if args.days is not None:
        if not math.isfinite(args.days) or args.days < 0:
            raise ValueError("--days must be a finite non-negative number")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        cutoff = current_time.astimezone(timezone.utc) - timedelta(days=args.days)
    if args.limit < 0:
        raise ValueError("--limit must be non-negative")

    warnings = WarningCollector()
    result_limit = args.limit if args.include_evidence else 0
    result_heap: list[tuple[datetime, int, dict[str, Any]]] = []
    result_sequence = 0
    roles: Counter[str] = Counter()
    tool_calls: Counter[str] = Counter()
    tool_errors: Counter[str] = Counter()
    direct_calls: Counter[str] = Counter()
    skill_reads: Counter[str] = Counter()
    files_discovered = 0
    selected_files = 0
    scanned_entries = 0
    eligible_entries = 0
    matched_sessions = 0
    matched_entries = 0
    matched_events = 0
    excluded_current = 0
    attempted_files = 0
    readable_headers = 0

    for path in root.rglob("*.jsonl"):
        files_discovered += 1
        if not args.include_current and current and normalized_path(path) == current:
            excluded_current += 1
            continue
        attempted_files += 1
        warnings.begin_file(path)
        header, entry_count, leaf_path = read_session_metadata(path, warnings)
        if header is None:
            continue
        readable_headers += 1
        header_cwd = header.get("cwd")
        if not args.all_projects and (not isinstance(header_cwd, str) or normalized_path(header_cwd) != target_cwd):
            continue
        selected_files += 1
        scanned_entries += entry_count
        session = {"session_id": str(header.get("id", "")), "file": str(path)}
        session_matched = False
        for entry in iter_session_entries(path, warnings):
            timestamp = parse_timestamp(entry.get("timestamp"))
            if cutoff is not None and (timestamp is None or timestamp < cutoff):
                continue
            eligible_entries += 1
            entry_matched = False
            for event in events_for_entry(entry, session, entry.get("id") in leaf_path):
                if not event_matches(event, args):
                    continue
                matched_events += 1
                if not entry_matched:
                    entry_matched = True
                    session_matched = True
                    matched_entries += 1
                    roles[event["role"]] += 1
                if event["event"] in {"tool_call", "skill_file_read"} and event.get("tool_name"):
                    tool_calls[event["tool_name"]] += 1
                if event.get("is_error") and event.get("tool_name"):
                    tool_errors[event["tool_name"]] += 1
                direct_calls.update(event.get("direct_skills", []))
                if event.get("skill_file_read"):
                    skill_reads[event["skill_file_read"]] += 1

                result_sequence += 1
                result_key = parse_timestamp(event.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)
                heap_key = (result_key, result_sequence)
                if result_limit and (
                    len(result_heap) < result_limit or heap_key > result_heap[0][:2]
                ):
                    item = (result_key, result_sequence, result_view(event))
                    if len(result_heap) < result_limit:
                        heapq.heappush(result_heap, item)
                    else:
                        heapq.heapreplace(result_heap, item)
        if session_matched:
            matched_sessions += 1

    if attempted_files and not readable_headers:
        raise RuntimeError("all candidate session files were unreadable or invalid")

    result_events = [
        item[2]
        for item in sorted(result_heap, key=lambda item: (item[0], item[1]), reverse=True)
    ]
    summary = {
        "files_discovered": files_discovered,
        "files_selected": selected_files,
        "current_session_files_excluded": excluded_current,
        "entries_scanned": scanned_entries,
        "entries_eligible": eligible_entries,
        "matched_sessions": matched_sessions,
        "matched_entries": matched_entries,
        "matched_events": matched_events,
        "results_returned": len(result_events),
        "result_limit": result_limit,
        "truncated": matched_events > len(result_events),
        "roles": dict(sorted(roles.items())),
        "tool_calls": dict(sorted(tool_calls.items())),
        "tool_errors": dict(sorted(tool_errors.items())),
        "direct_skill_calls": dict(sorted(direct_calls.items())),
        "skill_file_reads": dict(sorted(skill_reads.items())),
    }
    return {
        "status": "ok",
        "evidence_included": args.include_evidence,
        "scope": {
            "cwd": target_cwd if args.include_evidence and not args.all_projects else None,
            "all_projects": args.all_projects,
            "days": args.days,
            "include_current": args.include_current,
        },
        "summary": summary,
        "results": result_events,
        "warnings": warnings.output(args.include_evidence),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = aggregate(args)
    except (OSError, RuntimeError, ValueError) as exc:
        output = {"status": "error", "error": mask_and_shorten(str(exc)), "results": []}
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
