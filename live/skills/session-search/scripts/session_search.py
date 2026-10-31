#!/usr/bin/env python3
"""Read-only aggregation of evidence across Pi session JSONL files."""

from __future__ import annotations

import argparse
import heapq
import json
import posixpath
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import session_common

DEFAULT_LIMIT = 20
MAX_BATCH_FILTERS = 8
MAX_BATCH_FILTER_CHARS = 4096
SKILL_ENVELOPE_RE = re.compile(
    r'\A<skill name="([^"\r\n]+)" location="([^"\r\n]+)">\r?\n'
    r'References are relative to [^\r\n]+\.\r?\n\r?\n'
    r'.*\r?\n</skill>(?:\r?\n\r?\n.*)?\Z',
    re.DOTALL,
)
SKILL_FILE_RE = re.compile(r"(?:^|[/\\])([^/\\]+)[/\\]SKILL\.md$", re.IGNORECASE)


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
    match = SKILL_ENVELOPE_RE.fullmatch(session_common.text_content(message.get("content")))
    if match:
        return {**names_by_path, recorded_skill_path(match.group(2), cwd): match.group(1)}
    return names_by_path


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


def _tool_event(
    base: dict[str, Any], kind: str, tool_name: str, text: str, read_skill: str | None,
    *, is_error: bool = False,
) -> dict[str, Any]:
    """Build shared tool fields; callers retain call/result interpretation."""
    return {
        **base,
        "event": kind,
        "tool_name": tool_name,
        "is_error": is_error,
        "skill_names": [read_skill] if read_skill else [],
        "direct_skills": [],
        "skill_file_read": read_skill,
        "searchable": "\n".join(filter(None, [tool_name, text, read_skill])),
        "evidence_raw": text,
    }


def _call_event(
    base: dict[str, Any], tool_name: str, arguments: Any, read_skill: str | None, *, include_arguments: bool,
) -> dict[str, Any]:
    arguments_text = (
        json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str) if include_arguments else ""
    )
    return _tool_event(base, "skill_file_read" if read_skill else "tool_call", tool_name, arguments_text, read_skill)


def events_for_entry(
    entry: dict[str, Any],
    session: dict[str, str],
    on_leaf: bool | None,
    skill_reads_by_call_id: dict[str, str | None] | None = None,
    names_by_path: dict[str, str] | None = None,
    cwd: str = "",
    *,
    include_arguments: bool = True,
) -> list[dict[str, Any]]:
    """Serialize tool-call arguments only when a query or evidence can use them."""
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
    text = session_common.text_content(message.get("content"))
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
            read_skill = skill_read_name(tool_name, arguments, names_by_path, cwd)
            events.append(_call_event(base, tool_name, arguments, read_skill, include_arguments=include_arguments))
    if role == "toolResult":
        tool_name = str(message.get("toolName", "unknown"))
        tool_call_id = message.get("toolCallId")
        read_skill = (
            skill_reads_by_call_id.get(tool_call_id)
            if isinstance(tool_call_id, str) and skill_reads_by_call_id is not None
            else None
        )
        events.append(_tool_event(
            base, "tool_error" if message.get("isError") else "tool_result",
            tool_name, text, read_skill, is_error=bool(message.get("isError", False)),
        ))
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
            events.append(_call_event(
                base, name, arguments, read_skill, include_arguments=include_arguments and isinstance(arguments, dict),
            ))
            if status != "unfinished":
                error = call.get("error")
                error_text = error if isinstance(error, str) else ""
                events.append(_tool_event(
                    base, "tool_error" if status == "error" else "tool_result",
                    name, error_text, read_skill, is_error=status == "error",
                ))
    return events


def record_skill_read_calls(
    entry: dict[str, Any], skill_reads_by_call_id: dict[str, str | None],
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
        if isinstance(call_id, str):
            # A non-skill call must shadow an older skill call with the same ID.
            skill_reads_by_call_id[call_id] = read_skill


def skill_read_calls_for_result(
    entry: dict[str, Any], calls_by_id: dict[str, dict[str, str | None]],
    parent_by_id: dict[str, Any],
) -> dict[str, str | None]:
    message = entry.get("message")
    if not isinstance(message, dict) or message.get("role") != "toolResult":
        return {}
    call_id = message.get("toolCallId")
    if not isinstance(call_id, str):
        return {}
    candidates = calls_by_id.get(call_id)
    if not candidates:
        return {}
    parent = entry.get("parentId")
    seen: set[str] = set()
    while isinstance(parent, str) and parent not in seen:
        seen.add(parent)
        if parent in candidates:
            return {call_id: candidates[parent]}
        parent = parent_by_id.get(parent)
    return {}


class LinearSkillState:
    """Version 1 entries form one history, so later records shadow earlier ones."""

    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.names_by_path: dict[str, str] = {}
        self.skill_reads_by_call_id: dict[str, str | None] = {}

    def advance(self, entry: dict[str, Any]) -> None:
        self.names_by_path = record_skill_identity(entry, self.names_by_path, self.cwd)
        record_skill_read_calls(entry, self.skill_reads_by_call_id, self.names_by_path, self.cwd)

    def leaf_path(self) -> set[str]:
        return set()


class BranchSkillState:
    """Version 2+ entries form a tree, so each entry sees only records on its parent chain."""

    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.names_by_path: dict[str, str] = {}
        self.skill_reads_by_call_id: dict[str, str | None] = {}
        self.parent_by_id: dict[str, Any] = {}
        self.leaf_id: str | None = None
        self.identities_by_entry: dict[str, dict[str, str]] = {}
        self.calls_by_id: dict[str, dict[str, str | None]] = {}

    def advance(self, entry: dict[str, Any]) -> None:
        entry_id = entry.get("id")
        parent_id = entry.get("parentId")
        if isinstance(entry_id, str):
            self.parent_by_id[entry_id] = parent_id
            self.leaf_id = entry_id
        names_by_path = self.identities_by_entry.get(parent_id, {}) if isinstance(parent_id, str) else {}
        self.names_by_path = record_skill_identity(entry, names_by_path, self.cwd)
        if isinstance(entry_id, str):
            self.identities_by_entry[entry_id] = self.names_by_path
        entry_calls: dict[str, str | None] = {}
        record_skill_read_calls(entry, entry_calls, self.names_by_path, self.cwd)
        if isinstance(entry_id, str):
            for call_id, skill in entry_calls.items():
                self.calls_by_id.setdefault(call_id, {})[entry_id] = skill
        self.skill_reads_by_call_id = skill_read_calls_for_result(entry, self.calls_by_id, self.parent_by_id)

    def leaf_path(self) -> set[str]:
        return set(session_common.ancestor_ids(self.leaf_id, self.parent_by_id))


def result_view(event: dict[str, Any], queries: Iterable[str] = ()) -> dict[str, Any]:
    result = {
        key: event.get(key)
        for key in ("session_id", "file", "timestamp", "entry_id", "role", "event", "tool_name", "is_error", "on_latest_leaf")
    }
    if event.get("direct_skills"):
        result["direct_skills"] = event["direct_skills"]
    if event.get("skill_file_read"):
        result["skill_file_read"] = event["skill_file_read"]
    evidence = event.get("evidence_raw", "")
    if event.get("event") in ("tool_call", "skill_file_read"):
        # Call evidence is JSON. Mask each decoded string before escaping it
        # again, including strings inside nested arguments. Keep search raw.
        evidence = re.sub(
            r'"(?:\\.|[^"\\])*"',
            lambda match: json.dumps(session_common.mask_secrets(json.loads(match[0])), ensure_ascii=False),
            evidence,
        )
    result["evidence"] = session_common.mask_and_shorten(evidence, queries=queries)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = session_common.SessionArgumentParser(description="Aggregate local evidence across multiple Pi sessions; use /resume for a single session.")
    parser.add_argument("-q", "--query", action="append", default=[], help="case-insensitive literal filter; repeat to require every value (AND)")
    session_common.add_time_arguments(parser)
    session_common.add_storage_scope_arguments(parser)
    parser.add_argument("--role", action="append", default=[], help="message role filter; repeat for alternatives")
    parser.add_argument("--tool", action="append", default=[], help="tool-name filter; repeat for alternatives")
    parser.add_argument("--error", action="store_true", help="include only error events")
    parser.add_argument("--skill", action="append", default=[], help="direct-invocation or skill-file-read name; repeat for alternatives")
    parser.add_argument("--batch-filter", action="append", default=[], metavar="JSON",
                        help="independent summary-only filter object; repeat up to 8 times; "
                             "keys: query, role, tool, skill (string arrays), error (boolean)")
    session_common.add_exclusion_argument(parser)
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
        help="explicitly select the path-free summary output (the default)",
    )
    return parser


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


def _aggregate_output(
    args: argparse.Namespace, time_range: session_common.TimeRange, target_cwd: str,
    scan: dict[str, int], aggregations: list[EventAggregation], warnings: session_common.WarningCollector,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "evidence_included": args.include_evidence,
        "scope": {
            "cwd": target_cwd if args.include_evidence and not args.all_projects else None,
            "all_projects": args.all_projects,
            "days": args.days,
            **time_range.view(),
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


def aggregate(args: argparse.Namespace, now: datetime | None = None) -> dict[str, Any]:
    time_range = session_common.time_range_for_args(args, now)
    if args.limit < 0:
        raise ValueError("--limit must be non-negative")
    filters = aggregate_filters(args)
    exclusions = session_common.normalized_exclusions(args.exclude_session_file)
    paths = session_common.discover_session_files([args.sessions_root, *args.additional_sessions_root])
    target_cwd = session_common.normalized_path(args.cwd)
    file_exclusions = session_common.SessionFileExclusions(exclusions, args.include_current)

    warnings = session_common.WarningCollector()
    result_limit = args.limit if args.include_evidence else 0
    aggregations = [EventAggregation(item, result_limit, args.include_evidence) for item in filters]
    include_arguments = args.include_evidence or any(item.queries for item in filters)
    files_discovered = 0
    selected_files = 0
    scanned_entries = 0
    eligible_entries = 0
    attempted_files = 0
    readable_headers = 0

    def read_entries(
        path: Path, header: dict[str, Any], version: int, entries: Iterator[dict[str, Any]],
    ) -> None:
        # Shared counters preserve progress even when a file fails partway through.
        nonlocal selected_files, scanned_entries, eligible_entries
        selected_files += 1
        session = {"session_id": str(header.get("id", "")), "file": str(path)}
        for aggregation in aggregations:
            aggregation.start_session()
        header_cwd = header.get("cwd")
        recorded_cwd = header_cwd if isinstance(header_cwd, str) else ""
        state = BranchSkillState(recorded_cwd) if version >= 2 else LinearSkillState(recorded_cwd)

        for entry in entries:
            scanned_entries += 1
            message = entry.get("message")
            nested = message.get("nestedCalls") if isinstance(message, dict) else None
            if isinstance(nested, dict) and nested.get("complete") is not True:
                warnings.add(path, "incomplete_nested_calls")
            if version >= 2 and not isinstance(entry.get("id"), str):
                warnings.add(path, "invalid_entry_id")
            state.advance(entry)

            timestamp = session_common.parse_timestamp(entry.get("timestamp"))
            if not time_range.contains(timestamp):
                continue
            eligible_entries += 1
            events = events_for_entry(
                entry, session, None, state.skill_reads_by_call_id, state.names_by_path, recorded_cwd,
                include_arguments=include_arguments,
            )
            for aggregation in aggregations:
                aggregation.consume(events, timestamp)

        if result_limit:
            leaf_path = state.leaf_path()
            for aggregation in aggregations:
                aggregation.mark_branch(path, version, leaf_path)

    scope_cwd = None if args.all_projects else target_cwd
    for path in paths:
        files_discovered += 1
        if file_exclusions.excludes(session_common.normalized_path(path)):
            continue
        attempted_files += 1
        file_scan = session_common.scan_session(path, scope_cwd, warnings, read_entries)
        if file_scan.header_valid:
            readable_headers += 1
        if file_scan.version is not None and not file_scan.complete:
            # Keep already counted evidence, but never claim a complete branch scan.
            for aggregation in aggregations:
                aggregation.mark_branch(path, 1, None)

    if attempted_files and not readable_headers:
        raise RuntimeError("all candidate session files were unreadable or invalid")

    scan = {
        "files_discovered": files_discovered,
        "files_selected": selected_files,
        **file_exclusions.summary(),
        "entries_scanned": scanned_entries,
        "entries_eligible": eligible_entries,
    }
    return _aggregate_output(args, time_range, target_cwd, scan, aggregations, warnings)


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        output = aggregate(args)
    except (session_common.InvalidArgumentError, ValueError):
        return session_common.emit_error("INVALID_ARGUMENT", "Arguments are invalid.")
    except (OSError, RuntimeError):
        return session_common.emit_error("SESSION_STORAGE_UNAVAILABLE", "Session storage could not be read.")
    session_common.emit_json(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
