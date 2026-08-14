# Session Search

`session-search` is an [Agent Skill](https://agentskills.io/) for factual analysis across multiple local [Pi](https://github.com/earendil-works/pi) session files. Its helper script can count matching entries, identify repeated tool errors, and distinguish direct skill invocations from reads of a skill's `SKILL.md`.

Use Pi's built-in `/resume` command instead when you only need to find, open, or continue one session.

## Safety model

- Reads session JSONL files without changing them or building an index.
- Searches only sessions whose recorded working directory exactly matches the current directory by default.
- Excludes the active session by default when `PI_SESSION_FILE` is set.
- Returns a path-free aggregate summary by default.
- Returns bounded, best-effort-masked evidence only with `--include-evidence`.
- Uses only the Python standard library and makes no network requests.

Session data is inherently sensitive. In an agent workflow, local tool output becomes context for the active model and may therefore reach a remote model provider. A cross-session request authorizes the default aggregate only. Use `--include-evidence` only after the user explicitly approves sending masked snippets, local paths, session identifiers, and warning paths to that provider. Masking cannot recognize every credential or personal detail.

## Requirements

- Pi session files under `~/.pi/agent/sessions`
- Python 3.10 or later

The parser follows Pi's JSONL session structure. Future Pi schema changes may require updates.

## Installation

Copy this directory into one of Pi's skill locations, for example:

```bash
mkdir -p ~/.pi/agent/skills
cp -R live/skills/session-search ~/.pi/agent/skills/
```

Restart Pi after installing it. Pi will expose the skill as `/skill:session-search` when skill commands are enabled.

## Script usage

The agent normally runs the helper script for you. You can also invoke it directly:

```bash
python3 ~/.pi/agent/skills/session-search/scripts/session_search.py --help
```

Examples:

```bash
# Count matching events in sessions for the current project (safe default)
python3 scripts/session_search.py --query timeout

# Explicitly request the same path-free summary mode
python3 scripts/session_search.py --query timeout --summary-only

# Include representative evidence after explicit disclosure approval
python3 scripts/session_search.py --days 7 --error --tool bash --include-evidence

# Compare direct invocations with SKILL.md reads across all projects
python3 scripts/session_search.py --all-projects --skill deep-plan
```

Repeated `--query` values use AND logic. Repeated `--role`, `--tool`, and `--skill` values are alternatives within each filter.

The command emits one JSON object containing:

- `scope`: path-free project selection and time range by default; the exact cwd only with `--include-evidence`
- `summary`: scan and match counts grouped by role, tool, and skill
- `results`: empty by default; bounded representative evidence, newest first, with `--include-evidence`
- `warnings`: deduplicated counts by kind by default; up to 100 file-path details with `--include-evidence`

`--summary-only` remains as an explicit alias for the safe default. `--include-evidence` is mutually exclusive with it. A direct skill invocation is counted only for a user message matching Pi's complete skill envelope; it is reported separately from a read of that skill's `SKILL.md`. Reading instructions, quoting the XML, or mentioning a skill is not evidence that the skill was invoked.

## Known limitations

- Searches are case-insensitive literal matches, not regular expressions or semantic search.
- Counts describe recorded events and entries, not inferred tasks or outcomes.
- The latest branch marker is inferred from the parent chain of the last recorded entry.
- Every invocation scans the selected JSONL files twice—once for branch metadata and once for events; there is no persistent index. Memory remains bounded by compact per-session branch metadata, aggregate counters, warning caps, and the requested result limit.
- Secret masking is deliberately best-effort and is not a data-loss-prevention guarantee.

## Tests

From this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

## License

MIT, as provided by the repository-level `LICENSE` file.
