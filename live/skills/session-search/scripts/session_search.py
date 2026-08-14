#!/usr/bin/env python3
"""Read-only aggregation of evidence across Pi session JSONL files."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_LIMIT = 20
DEFAULT_SESSIONS_ROOT = Path.home() / ".pi" / "agent" / "sessions"
MAX_EVIDENCE_CHARS = 300
SKILL_TAG_RE = re.compile(r'<skill\s+name=["\']([^"\']+)["\']', re.IGNORECASE)
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
    return [match.group(1) for match in SKILL_TAG_RE.finditer(text)]


def skill_read_name(tool_name: str, arguments: Any) -> str | None:
    if tool_name.lower() != "read" or not isinstance(arguments, dict):
        return None
    path = arguments.get("path")
    if not isinstance(path, str):
        return None
    match = SKILL_FILE_RE.search(path)
    return match.group(1) if match else None


def latest_leaf_path(entries: list[dict[str, Any]]) -> set[str]:
    by_id = {entry["id"]: entry for entry in entries if isinstance(entry.get("id"), str)}
    if not by_id:
        return set()
    leaf_id = next((entry.get("id") for entry in reversed(entries) if isinstance(entry.get("id"), str)), None)
    result: set[str] = set()
    while isinstance(leaf_id, str) and leaf_id in by_id and leaf_id not in result:
        result.add(leaf_id)
        leaf_id = by_id[leaf_id].get("parentId")
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
    skills = direct_skills(text)
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


def warning(path: Path, kind: str) -> dict[str, str]:
    return {"path": str(path), "kind": kind}


def read_session(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            try:
                header = json.loads(first)
            except (json.JSONDecodeError, TypeError):
                return None, [], [warning(path, "invalid_header")]
            if not isinstance(header, dict) or header.get("type") != "session":
                return None, [], [warning(path, "invalid_header")]
            for line in handle:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    warnings.append(warning(path, "invalid_json_line"))
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
                else:
                    warnings.append(warning(path, "invalid_entry"))
    except (OSError, UnicodeError):
        return None, [], [warning(path, "unreadable_file")]
    return header, entries, warnings


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate local evidence across multiple Pi sessions; use /resume for a single session.")
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
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"maximum evidence results (default: {DEFAULT_LIMIT})")
    parser.add_argument("--summary-only", action="store_true", help="omit representative evidence results")
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
        if args.days < 0:
            raise ValueError("--days must be non-negative")
        current_time = now or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        cutoff = current_time.astimezone(timezone.utc) - timedelta(days=args.days)
    if args.limit < 0:
        raise ValueError("--limit must be non-negative")

    files = sorted(root.rglob("*.jsonl"))
    warnings: list[dict[str, str]] = []
    matched_events: list[dict[str, Any]] = []
    matched_entry_keys: set[tuple[str, Any]] = set()
    matched_sessions: set[str] = set()
    roles: Counter[str] = Counter()
    tool_calls: Counter[str] = Counter()
    tool_errors: Counter[str] = Counter()
    direct_calls: Counter[str] = Counter()
    skill_reads: Counter[str] = Counter()
    selected_files = 0
    scanned_entries = 0
    eligible_entries = 0
    excluded_current = 0
    attempted_files = 0
    readable_headers = 0

    for path in files:
        if not args.include_current and current and normalized_path(path) == current:
            excluded_current += 1
            continue
        attempted_files += 1
        header, entries, file_warnings = read_session(path)
        warnings.extend(file_warnings)
        if header is None:
            continue
        readable_headers += 1
        header_cwd = header.get("cwd")
        if not args.all_projects and (not isinstance(header_cwd, str) or normalized_path(header_cwd) != target_cwd):
            continue
        selected_files += 1
        scanned_entries += len(entries)
        leaf_path = latest_leaf_path(entries)
        session_id = str(header.get("id", ""))
        session = {"session_id": session_id, "file": str(path)}
        for entry in entries:
            timestamp = parse_timestamp(entry.get("timestamp"))
            if cutoff is not None and (timestamp is None or timestamp < cutoff):
                continue
            eligible_entries += 1
            for event in events_for_entry(entry, session, entry.get("id") in leaf_path):
                if not event_matches(event, args):
                    continue
                matched_events.append(event)
                entry_key = (str(path), entry.get("id"))
                if entry_key not in matched_entry_keys:
                    roles[event["role"]] += 1
                matched_entry_keys.add(entry_key)
                matched_sessions.add(str(path))
                if event["event"] in {"tool_call", "skill_file_read"} and event.get("tool_name"):
                    tool_calls[event["tool_name"]] += 1
                if event.get("is_error") and event.get("tool_name"):
                    tool_errors[event["tool_name"]] += 1
                direct_calls.update(event.get("direct_skills", []))
                if event.get("skill_file_read"):
                    skill_reads[event["skill_file_read"]] += 1

    if attempted_files and not readable_headers:
        raise RuntimeError("all candidate session files were unreadable or invalid")

    matched_events.sort(key=lambda item: parse_timestamp(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    result_limit = 0 if args.summary_only else args.limit
    result_events = matched_events[:result_limit]
    summary = {
        "files_discovered": len(files),
        "files_selected": selected_files,
        "current_session_files_excluded": excluded_current,
        "entries_scanned": scanned_entries,
        "entries_eligible": eligible_entries,
        "matched_sessions": len(matched_sessions),
        "matched_entries": len(matched_entry_keys),
        "matched_events": len(matched_events),
        "results_returned": len(result_events),
        "result_limit": result_limit,
        "truncated": len(matched_events) > len(result_events),
        "roles": dict(sorted(roles.items())),
        "tool_calls": dict(sorted(tool_calls.items())),
        "tool_errors": dict(sorted(tool_errors.items())),
        "direct_skill_calls": dict(sorted(direct_calls.items())),
        "skill_file_reads": dict(sorted(skill_reads.items())),
    }
    return {
        "status": "ok",
        "scope": {
            "cwd": None if args.all_projects else target_cwd,
            "all_projects": args.all_projects,
            "days": args.days,
            "include_current": args.include_current,
        },
        "summary": summary,
        "results": [result_view(event) for event in result_events],
        "warnings": {"count": len(warnings), "items": warnings},
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
