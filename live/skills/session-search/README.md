# Session Search

`session-search` is an [Agent Skill](https://agentskills.io/) for factual analysis across multiple local [Pi](https://github.com/earendil-works/pi) session files. Its helper script can count matching entries, identify repeated tool errors, and distinguish direct skill invocations from reads of a skill's `SKILL.md`.

Use Pi's built-in `/resume` command instead when you only need to find, open, or continue one session.

## Safety model

- Reads session JSONL files without changing them or building an index.
- Searches only sessions whose recorded working directory exactly matches the current directory by default.
- Excludes the active session by default when `PI_SESSION_FILE` is set.
- Returns bounded evidence snippets and applies best-effort masking before truncation.
- Uses only the Python standard library and makes no network requests.

Session data is inherently sensitive. Masking cannot recognize every credential or personal detail, and output includes local file paths and session identifiers. Review output before sharing it, prefer `--summary-only` when snippets are unnecessary, and never send raw session data to an external service.

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
# Count matching events in sessions for the current project without snippets
python3 scripts/session_search.py --query timeout --summary-only

# Find tool errors from the last seven days
python3 scripts/session_search.py --days 7 --error --tool bash

# Compare direct invocations with SKILL.md reads across all projects
python3 scripts/session_search.py --all-projects --skill deep-plan
```

Repeated `--query` values use AND logic. Repeated `--role`, `--tool`, and `--skill` values are alternatives within each filter.

The command emits one JSON object containing:

- `scope`: the selected project and time range
- `summary`: scan and match counts grouped by role, tool, and skill
- `results`: bounded representative evidence, newest first
- `warnings`: unreadable or malformed input encountered during the scan

A direct skill invocation and a read of that skill's `SKILL.md` are reported separately. Reading instructions alone is not evidence that the skill was used.

## Known limitations

- Searches are case-insensitive literal matches, not regular expressions or semantic search.
- Counts describe recorded events and entries, not inferred tasks or outcomes.
- The latest branch marker is inferred from the parent chain of the last recorded entry.
- Every invocation scans the selected JSONL files; there is no persistent index.
- Secret masking is deliberately best-effort and is not a data-loss-prevention guarantee.

## Tests

From this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

## License

MIT, as provided by the repository-level `LICENSE` file.
