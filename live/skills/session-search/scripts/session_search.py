#!/usr/bin/env python3
"""Read-only aggregation of evidence across Pi session JSONL files."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import posixpath
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable

DEFAULT_LIMIT = 20
MAX_EVIDENCE_CHARS = 300
MAX_WARNING_ITEMS = 100
MAX_BATCH_FILTERS = 8
MAX_BATCH_FILTER_CHARS = 4096
SKILL_ENVELOPE_RE = re.compile(
    r'\A<skill name="([^"\r\n]+)" location="([^"\r\n]+)">\r?\n'
    r'References are relative to [^\r\n]+\.\r?\n\r?\n'
    r'.*\r?\n</skill>(?:\r?\n\r?\n.*)?\Z',
    re.DOTALL,
)
SKILL_FILE_RE = re.compile(r"(?:^|[/\\])([^/\\]+)[/\\]SKILL\.md$", re.IGNORECASE)

# Mask before truncation so a secret crossing the truncation boundary cannot leak.
MASK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----", re.I | re.S), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I), r"\1 [REDACTED]"),
    (re.compile(r"(?i)(https?://)([^\s/@:]+):([^\s/@]+)@"), r"\1[REDACTED]@"),
    # Header values can contain several cookies and folded continuation lines.
    (re.compile(r"(?im)(?<![\w-])((?:set-cookie|cookie)[ \t]*:[ \t]*)[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*"), r"\1[REDACTED]"),
    # Quoted values may contain whitespace, separators, and escaped quotes.
    # An unterminated quoted value is masked through the end of the input.
    (re.compile(
        r'''(["']?(?:api[_-]?key|access[_-]?token|auth(?:orization)?|(?:set-)?cookie|password|passwd|secret|token)["']?\s*[:=]\s*)'''
        r'''(?:"(?:\\.|[^"\\])*(?:"|\\?$)|'(?:\\.|[^'\\])*(?:'|\\?$)|[^"'\s,;}]+)''',
        re.I | re.S,
    ), r"\1[REDACTED]"),
    (re.compile(r"(?i)([?&](?:api[_-]?key|access[_-]?token|auth|password|secret|token)=)[^&#\s]+"), r"\1[REDACTED]"),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
)


def pi_environment_path(value: str) -> Path:
    """Expand only Pi's own-home tilde forms, never another user's home."""
    if value == "~":
        return Path.home()
    if value.startswith("~/") or (os.name == "nt" and value.startswith("~\\")):
        return Path.home() / value[2:]
    # Prevent later generic expanduser calls from expanding a literal ~user.
    return Path(value).absolute()


def default_sessions_root() -> Path:
    """Resolve Pi's storage overrides when building a CLI, not at import time."""
    if value := os.environ.get("PI_CODING_AGENT_SESSION_DIR"):
        return pi_environment_path(value)
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR")
    return (pi_environment_path(agent_dir) if agent_dir else Path.home() / ".pi" / "agent") / "sessions"


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def normalized_path(value: str | Path) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def mask_and_shorten(
    value: str, limit: int = MAX_EVIDENCE_CHARS, queries: Iterable[str] = (),
) -> str:
    return mask_and_shorten_with_metadata(value, limit, queries)[0]


def mask_and_shorten_with_metadata(
    value: str, limit: int = MAX_EVIDENCE_CHARS, queries: Iterable[str] = (),
) -> tuple[str, bool]:
    """Return masked evidence and whether normalized masked text was shortened."""
    masked = value
    for pattern, replacement in MASK_PATTERNS:
        masked = pattern.sub(replacement, masked)
    masked = re.sub(r"\s+", " ", masked).strip()
    if limit <= 0:
        return "", bool(masked)
    if len(masked) <= limit:
        return masked, False

    folded = masked.casefold()
    positions = []
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip().casefold()
        if query:
            position = folded.find(query)
            if position >= 0:
                positions.append(position)
    if positions and limit >= 3:
        # casefold can expand characters (e.g. ß -> ss); translate the offset
        # back to masked text without ever consulting the unmasked source.
        target = min(positions)
        folded_offset = 0
        for index, char in enumerate(masked):
            folded_offset += len(char.casefold())
            if folded_offset > target:
                break
        budget = limit - 2  # Reserve both possible omission markers.
        start = min(max(0, index - budget // 2), len(masked) - budget)
        end = start + budget
        return ("…" if start else "") + masked[start:end] + ("…" if end < len(masked) else ""), True
    return masked[: limit - 1] + "…", True


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


def recorded_skill_path(path: str, cwd: str = "") -> str:
    """Normalize recorded spellings without accessing today's filesystem."""
    path = path.replace("\\", "/")
    if not posixpath.isabs(path) and not re.match(r"^[A-Za-z]:/", path):
        path = posixpath.join(cwd.replace("\\", "/"), path)
    return posixpath.normpath(path)


def skill_read_name(
    tool_name: str, arguments: Any, names_by_path: dict[str, str] | None = None, cwd: str = "",
) -> str | None:
    if tool_name.lower() != "read" or not isinstance(arguments, dict):
        return None
    path = arguments.get("path")
    if not isinstance(path, str):
        return None
    path = recorded_skill_path(path, cwd)
    if names_by_path and path in names_by_path:
        return names_by_path[path]
    match = SKILL_FILE_RE.search(path)
    return match.group(1) if match else None


def record_skill_identity(
    entry: dict[str, Any], names_by_path: dict[str, str], cwd: str,
) -> dict[str, str]:
    """Copy only on an identity change so sibling branches keep their own state."""
    message = entry.get("message")
    if entry.get("type") != "message" or not isinstance(message, dict) or message.get("role") != "user":
        return names_by_path
    match = SKILL_ENVELOPE_RE.fullmatch(text_content(message.get("content")))
    if match:
        return {**names_by_path, recorded_skill_path(match.group(2), cwd): match.group(1)}
    return names_by_path


def latest_leaf_path(parent_by_id: dict[str, Any], leaf_id: str | None) -> set[str]:
    result: set[str] = set()
    while isinstance(leaf_id, str) and leaf_id in parent_by_id and leaf_id not in result:
        result.add(leaf_id)
        leaf_id = parent_by_id[leaf_id]
    return result


@dataclass(frozen=True)
class EventFilters:
    queries: tuple[str, ...]
    roles: frozenset[str]
    tools: frozenset[str]
    skills: frozenset[str]
    errors_only: bool

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "EventFilters":
        return cls(
            queries=tuple(value.casefold() for value in args.query),
            roles=frozenset(value.casefold() for value in args.role),
            tools=frozenset(value.casefold() for value in args.tool),
            skills=frozenset(value.casefold() for value in args.skill),
            errors_only=args.error,
        )


def event_matches(event: dict[str, Any], filters: EventFilters) -> bool:
    if filters.queries:
        searchable = event["searchable"].casefold()
        if not all(query in searchable for query in filters.queries):
            return False
    if filters.roles and event["role"].casefold() not in filters.roles:
        return False
    if filters.tools and (not event.get("tool_name") or event["tool_name"].casefold() not in filters.tools):
        return False
    if filters.errors_only and not event.get("is_error", False):
        return False
    if filters.skills and not any(name.casefold() in filters.skills for name in event.get("skill_names", [])):
        return False
    return True


def events_for_entry(
    entry: dict[str, Any],
    session: dict[str, str],
    on_leaf: bool | None,
    skill_reads_by_call_id: dict[str, str] | None = None,
    names_by_path: dict[str, str] | None = None,
    cwd: str = "",
) -> list[dict[str, Any]]:
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
    # Provider failures may have no text content; their details live in errorMessage.
    error_message = message.get("errorMessage")
    if role == "assistant" and isinstance(error_message, str):
        text = "\n".join(filter(None, [text, error_message]))
    skills = direct_skills(text) if role == "user" else []
    is_error = bool(message.get("isError", False) or message.get("stopReason") == "error")
    if (text or is_error) and role != "toolResult":
        events.append({
            **base,
            "event": "message",
            "tool_name": None,
            "is_error": is_error,
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
            read_skill = skill_read_name(tool_name, arguments, names_by_path, cwd)
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
        tool_call_id = message.get("toolCallId")
        read_skill = (
            skill_reads_by_call_id.get(tool_call_id)
            if isinstance(tool_call_id, str) and skill_reads_by_call_id is not None
            else None
        )
        events.append({
            **base,
            "event": "tool_error" if message.get("isError") else "tool_result",
            "tool_name": tool_name,
            "is_error": bool(message.get("isError", False)),
            "skill_names": [read_skill] if read_skill else [],
            "direct_skills": [],
            "skill_file_read": read_skill,
            "searchable": "\n".join(filter(None, [tool_name, text, read_skill])),
            "evidence_raw": text,
        })
        nested = message.get("nestedCalls")
        calls = nested.get("calls") if isinstance(nested, dict) else None
        seen: set[str] = set()
        for call in calls if isinstance(calls, list) else []:
            if not isinstance(call, dict):
                continue
            call_id, name, status = call.get("id"), call.get("name"), call.get("status")
            if (not isinstance(call_id, str) or not isinstance(name, str) or not name
                    or status not in ("ok", "error", "unfinished") or call_id in seen):
                continue
            seen.add(call_id)
            arguments = call.get("arguments")
            read_skill = skill_read_name(name, arguments, names_by_path, cwd)
            arguments_text = json.dumps(arguments, ensure_ascii=False, sort_keys=True) if isinstance(arguments, dict) else ""
            nested_base = {
                **base,
                "tool_name": name,
                "skill_names": [read_skill] if read_skill else [],
                "direct_skills": [],
                "skill_file_read": read_skill,
            }
            events.append({
                **nested_base,
                "event": "skill_file_read" if read_skill else "tool_call",
                "is_error": False,
                "searchable": "\n".join(filter(None, [name, arguments_text, read_skill])),
                "evidence_raw": arguments_text,
            })
            if status != "unfinished":
                error = call.get("error")
                error_text = error if isinstance(error, str) else ""
                events.append({
                    **nested_base,
                    "event": "tool_error" if status == "error" else "tool_result",
                    "is_error": status == "error",
                    "searchable": "\n".join(filter(None, [name, error_text, read_skill])),
                    "evidence_raw": error_text,
                })
    return events


class WarningCollector:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._items: list[dict[str, str]] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, path: Path, kind: str) -> None:
        path_text = str(path)
        key = (path_text, kind)
        if key in self._seen:
            return
        self._seen.add(key)
        self._counts[kind] += 1
        if len(self._items) < MAX_WARNING_ITEMS:
            self._items.append({"path": path_text, "kind": kind})

    @property
    def count(self) -> int:
        return len(self._seen)

    def output(self, include_items: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "count": self.count,
            "by_kind": dict(sorted(self._counts.items())),
        }
        if include_items:
            result["items"] = list(self._items)
            result["truncated"] = self.count > len(self._items)
        return result


def read_session_header(handle: BinaryIO) -> dict[str, Any] | None:
    """Decode only the header; callers retain their own scope and warning policy."""
    try:
        header = json.loads(handle.readline().decode("utf-8"))
    except (json.JSONDecodeError, TypeError):
        return None
    return header if isinstance(header, dict) and header.get("type") == "session" else None


def session_version(header: dict[str, Any], path: Path, warnings: WarningCollector) -> int | None:
    value = header.get("version")
    if value is None:
        warnings.add(path, "missing_session_version")
        return 1
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        warnings.add(path, "invalid_session_version")
        return None
    if value > 3:
        warnings.add(path, "unsupported_session_version")
        return None
    return value


def record_skill_read_calls(
    entry: dict[str, Any], skill_reads_by_call_id: dict[str, str],
    names_by_path: dict[str, str] | None = None, cwd: str = "",
) -> None:
    if entry.get("type") != "message" or not isinstance(entry.get("message"), dict):
        return
    message = entry["message"]
    if message.get("role") != "assistant" or not isinstance(message.get("content"), list):
        return
    for block in message["content"]:
        if not isinstance(block, dict) or block.get("type") != "toolCall":
            continue
        call_id = block.get("id")
        read_skill = skill_read_name(str(block.get("name", "unknown")), block.get("arguments", {}), names_by_path, cwd)
        if isinstance(call_id, str) and read_skill:
            skill_reads_by_call_id[call_id] = read_skill


def result_view(event: dict[str, Any], queries: Iterable[str] = ()) -> dict[str, Any]:
    result = {
        key: event.get(key)
        for key in ("session_id", "file", "timestamp", "entry_id", "role", "event", "tool_name", "is_error", "on_latest_leaf")
    }
    if event.get("direct_skills"):
        result["direct_skills"] = event["direct_skills"]
    if event.get("skill_file_read"):
        result["skill_file_read"] = event["skill_file_read"]
    result["evidence"] = mask_and_shorten(event.get("evidence_raw", ""), queries=queries)
    return result


class InvalidArgumentError(Exception):
    pass


class SessionArgumentParser(argparse.ArgumentParser):
    def _parse_optional(self, arg_string: str):
        # argparse recognizes ordinary negative numbers as values but treats
        # -inf/-nan as options. Let the explicit finite-value check handle them.
        if arg_string.lower() in {"-inf", "-infinity", "-nan"}:
            return None
        return super()._parse_optional(arg_string)

    def error(self, message: str) -> None:
        raise InvalidArgumentError(message)


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
    parser.add_argument("--batch-filter", action="append", default=[], metavar="JSON",
                        help="independent summary-only filter object; repeat up to 8 times; "
                             "keys: query, role, tool, skill (string arrays), error (boolean)")
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
    parser.add_argument(
        "--additional-sessions-root", type=Path, action="append", default=[], metavar="PATH",
        help="also search this directory recursively; repeat for multiple directories; "
             "additive to the selected sessions root; all directories must be readable",
    )
    parser.add_argument(
        "--sessions-root", type=Path, default=default_sessions_root(), metavar="PATH",
        help="replace the primary sessions directory; default precedence: PI_CODING_AGENT_SESSION_DIR, "
             "PI_CODING_AGENT_DIR/sessions, ~/.pi/agent/sessions",
    )
    return parser


def discover_session_files(
    roots: Iterable[Path], on_outside: Callable[[Path], None] | None = None,
) -> list[Path]:
    """Fail visibly on traversal errors; keep only files under an allowed root."""
    paths: dict[str, Path] = {}
    allowed_roots: dict[str, Path] = {}
    for value in roots:
        root = value.expanduser()
        key = normalized_path(root)
        if not root.is_dir():
            raise RuntimeError("session root is unavailable")
        allowed_roots.setdefault(key, root)

    def traversal_error(error: OSError) -> None:
        raise error

    for root in allowed_roots.values():
        # Unlike Path.rglob, walk's onerror makes inaccessible subtrees visible.
        # Do not follow nested directory symlinks, matching the previous scan.
        for directory, _dirs, files in os.walk(root, onerror=traversal_error):
            for name in files:
                if name.endswith(".jsonl"):
                    path = Path(directory) / name
                    resolved = Path(normalized_path(path))
                    if not any(resolved.is_relative_to(allowed) for allowed in allowed_roots):
                        if on_outside is not None:
                            on_outside(path)
                        continue
                    paths.setdefault(str(resolved), path)
    return sorted(paths.values())


def cutoff_for_days(
    days: float | None, now: datetime | None = None
) -> datetime | None:
    if days is None:
        return None
    if not math.isfinite(days) or days < 0:
        raise ValueError("--days must be a finite non-negative number")
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    try:
        return current_time.astimezone(timezone.utc) - timedelta(days=days)
    except OverflowError as error:
        raise ValueError("--days exceeds the supported date range") from error


def aggregate_filters(args: argparse.Namespace) -> list[EventFilters]:
    """Validate a bounded batch before touching session storage; never echo input."""
    raw_filters = args.batch_filter
    if not raw_filters:
        return [EventFilters.from_args(args)]
    if len(raw_filters) > MAX_BATCH_FILTERS:
        raise ValueError("too many batch filters")
    if args.include_evidence or args.query or args.role or args.tool or args.skill or args.error:
        raise ValueError("batch filters cannot mix with evidence or individual filters")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate filter key")
            result[key] = value
        return result

    filters: list[EventFilters] = []
    for raw in raw_filters:
        if len(raw) > MAX_BATCH_FILTER_CHARS:
            raise ValueError("batch filter is too long")
        try:
            value = json.loads(raw, object_pairs_hook=unique_object)
        except RecursionError as error:
            raise ValueError("filter nesting is too deep") from error
        if not isinstance(value, dict) or value.keys() - {"query", "role", "tool", "skill", "error"}:
            raise ValueError("invalid filter object")
        if not isinstance(value.get("error", False), bool):
            raise ValueError("invalid error filter")
        for key in ("query", "role", "tool", "skill"):
            items = value.get(key, [])
            if not isinstance(items, list) or len(items) > 32 or any(
                not isinstance(item, str) or len(item) > 256 for item in items
            ):
                raise ValueError("invalid filter values")
        filters.append(EventFilters.from_args(argparse.Namespace(
            **{key: value.get(key, []) for key in ("query", "role", "tool", "skill")},
            error=value.get("error", False),
        )))
    return filters


class EventAggregation:
    """Per-filter counters and optional evidence; parsing is shared by all filters."""

    def __init__(self, filters: EventFilters, result_limit: int, include_evidence: bool) -> None:
        self.filters = filters
        self.result_limit = result_limit
        self.include_evidence = include_evidence
        self.result_heap: list[tuple[datetime, int, dict[str, Any]]] = []
        self.result_sequence = 0
        self.matched_sessions = 0
        self.matched_entries = 0
        self.matched_events = 0
        self.counters: dict[str, Counter[str]] = {
            key: Counter() for key in (
                "roles", "tool_calls", "tool_errors", "tool_error_sessions", "direct_skill_calls",
                "skill_file_read_attempts", "skill_file_read_successes", "skill_file_read_errors",
            )
        }
        self.start_session()

    def start_session(self) -> None:
        self.session_matched = False
        self.session_error_tools: set[str] = set()

    def consume(self, events: list[dict[str, Any]], timestamp: datetime | None) -> None:
        entry_matched = False
        for event in events:
            if not event_matches(event, self.filters):
                continue
            self.matched_events += 1
            if not entry_matched:
                entry_matched = True
                self.matched_entries += 1
                if not self.session_matched:
                    self.session_matched = True
                    self.matched_sessions += 1
                self.counters["roles"][event["role"].casefold()] += 1
            tool_name = event.get("tool_name")
            if event["event"] in {"tool_call", "skill_file_read"} and tool_name:
                self.counters["tool_calls"][tool_name.casefold()] += 1
            if event.get("is_error") and tool_name:
                tool_key = tool_name.casefold()
                self.counters["tool_errors"][tool_key] += 1
                if tool_key not in self.session_error_tools:
                    self.session_error_tools.add(tool_key)
                    self.counters["tool_error_sessions"][tool_key] += 1
            self.counters["direct_skill_calls"].update(
                name.casefold() for name in event.get("direct_skills", [])
            )
            read_skill = event.get("skill_file_read")
            if read_skill:
                counter = {
                    "skill_file_read": "skill_file_read_attempts",
                    "tool_error": "skill_file_read_errors",
                    "tool_result": "skill_file_read_successes",
                }.get(event["event"])
                if counter:
                    self.counters[counter][read_skill.casefold()] += 1
            if self.result_limit:
                self.result_sequence += 1
                result_key = timestamp or datetime.min.replace(tzinfo=timezone.utc)
                item = (result_key, self.result_sequence, event)
                if len(self.result_heap) < self.result_limit:
                    heapq.heappush(self.result_heap, item)
                elif item[:2] > self.result_heap[0][:2]:
                    heapq.heapreplace(self.result_heap, item)

    def mark_branch(self, path: Path, version: int, leaf_path: set[str] | None) -> None:
        for _timestamp, _sequence, event in self.result_heap:
            if event["file"] == str(path):
                event_id = event.get("entry_id")
                event["on_latest_leaf"] = (
                    None if leaf_path is None else
                    True if version == 1 else
                    event_id in leaf_path if isinstance(event_id, str) else None
                )

    def results(self) -> list[dict[str, Any]]:
        return [
            result_view(item[2], self.filters.queries)
            for item in sorted(self.result_heap, key=lambda item: item[:2], reverse=True)
        ]

    def summary(self, scan: dict[str, int]) -> dict[str, Any]:
        evidence_truncated = self.include_evidence and self.matched_events > len(self.result_heap)
        return {
            **scan,
            "matched_sessions": self.matched_sessions,
            "matched_entries": self.matched_entries,
            "matched_events": self.matched_events,
            "results_returned": len(self.result_heap),
            "result_limit": self.result_limit,
            "evidence_omitted": not self.include_evidence and self.matched_events > 0,
            "evidence_truncated": evidence_truncated,
            "truncated": evidence_truncated,
            **{key: dict(sorted(value.items())) for key, value in self.counters.items()},
            "skill_file_reads": dict(sorted(self.counters["skill_file_read_attempts"].items())),
        }


def aggregate(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    cutoff = cutoff_for_days(args.days, now)
    if args.limit < 0:
        raise ValueError("--limit must be non-negative")
    filters = aggregate_filters(args)
    paths = discover_session_files([args.sessions_root, *args.additional_sessions_root])
    target_cwd = normalized_path(args.cwd)
    current = normalized_path(os.environ["PI_SESSION_FILE"]) if os.environ.get("PI_SESSION_FILE") else None

    warnings = WarningCollector()
    result_limit = args.limit if args.include_evidence else 0
    aggregations = [EventAggregation(item, result_limit, args.include_evidence) for item in filters]
    files_discovered = 0
    selected_files = 0
    scanned_entries = 0
    eligible_entries = 0
    excluded_current = 0
    attempted_files = 0
    readable_headers = 0

    for path in paths:
        files_discovered += 1
        if not args.include_current and current and normalized_path(path) == current:
            excluded_current += 1
            continue
        attempted_files += 1
        try:
            with path.open("rb") as handle:
                header = read_session_header(handle)
                if header is None:
                    warnings.add(path, "invalid_header")
                    continue
                readable_headers += 1
                version = session_version(header, path, warnings)
                if version is None:
                    continue
                header_cwd = header.get("cwd")
                if not args.all_projects and (
                    not isinstance(header_cwd, str) or normalized_path(header_cwd) != target_cwd
                ):
                    continue

                selected_files += 1
                session = {"session_id": str(header.get("id", "")), "file": str(path)}
                for aggregation in aggregations:
                    aggregation.start_session()
                parent_by_id: dict[str, Any] = {}
                leaf_id: str | None = None
                skill_reads_by_call_id: dict[str, str] = {}
                names_by_path: dict[str, str] = {}
                identities_by_entry: dict[str, dict[str, str]] = {}
                recorded_cwd = header_cwd if isinstance(header_cwd, str) else ""

                for line in handle:
                    try:
                        entry = json.loads(line.decode("utf-8"))
                    except (json.JSONDecodeError, TypeError):
                        warnings.add(path, "invalid_json_line")
                        continue
                    if not isinstance(entry, dict):
                        warnings.add(path, "invalid_entry")
                        continue
                    scanned_entries += 1
                    message = entry.get("message")
                    nested = message.get("nestedCalls") if isinstance(message, dict) else None
                    if isinstance(nested, dict) and nested.get("complete") is not True:
                        warnings.add(path, "incomplete_nested_calls")
                    entry_id = entry.get("id")
                    if version >= 2 and not isinstance(entry_id, str):
                        warnings.add(path, "invalid_entry_id")
                    if result_limit and version >= 2 and isinstance(entry_id, str):
                        parent_by_id[entry_id] = entry.get("parentId")
                        leaf_id = entry_id
                    if version >= 2:
                        parent_id = entry.get("parentId")
                        names_by_path = identities_by_entry.get(parent_id, {}) if isinstance(parent_id, str) else {}
                    names_by_path = record_skill_identity(entry, names_by_path, recorded_cwd)
                    if version >= 2 and isinstance(entry_id, str):
                        identities_by_entry[entry_id] = names_by_path
                    record_skill_read_calls(entry, skill_reads_by_call_id, names_by_path, recorded_cwd)

                    timestamp = parse_timestamp(entry.get("timestamp"))
                    if cutoff is not None and (timestamp is None or timestamp < cutoff):
                        continue
                    eligible_entries += 1
                    # Parse each entry into events once, then evaluate independent filters.
                    events = events_for_entry(entry, session, None, skill_reads_by_call_id, names_by_path, recorded_cwd)
                    for aggregation in aggregations:
                        aggregation.consume(events, timestamp)

                if result_limit:
                    leaf_path = latest_leaf_path(parent_by_id, leaf_id) if version >= 2 else set()
                    for aggregation in aggregations:
                        aggregation.mark_branch(path, version, leaf_path)
        except (OSError, UnicodeError):
            warnings.add(path, "unreadable_file")
            # Keep already counted evidence, but never claim a complete branch scan.
            for aggregation in aggregations:
                aggregation.mark_branch(path, 1, None)

    if attempted_files and not readable_headers:
        raise RuntimeError("all candidate session files were unreadable or invalid")

    scan = {
        "files_discovered": files_discovered,
        "files_selected": selected_files,
        "current_session_files_excluded": excluded_current,
        "entries_scanned": scanned_entries,
        "entries_eligible": eligible_entries,
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
        **({
            "mode": "batch",
            "summary": {**scan, "filters_returned": len(aggregations)},
            "batches": [
                {"filter_index": index, "summary": aggregation.summary(scan)}
                for index, aggregation in enumerate(aggregations, 1)
            ],
        } if args.batch_filter else {"summary": aggregations[0].summary(scan)}),
        "results": aggregations[0].results(),
        "warnings": warnings.output(args.include_evidence),
    }


def emit_error(code: str, message: str) -> int:
    output = {
        "status": "error",
        "error": {"code": code, "message": message},
        "results": [],
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 2


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        output = aggregate(args)
    except (InvalidArgumentError, ValueError):
        return emit_error("INVALID_ARGUMENT", "Arguments are invalid.")
    except (OSError, RuntimeError):
        return emit_error("SESSION_STORAGE_UNAVAILABLE", "Session storage could not be read.")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
