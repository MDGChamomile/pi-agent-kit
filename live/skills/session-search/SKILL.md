---
name: session-search
description: Aggregate factual evidence across multiple local Pi sessions, including counts, repeated errors, and tool or skill usage. Use for cross-session analysis; do not use to find, open, or resume a single session.
license: MIT
compatibility: Requires Pi session JSONL files and Python 3.10 or later.
---

# Session Search

Use this skill only when a request needs factual aggregation across multiple Pi sessions. For finding, opening, or resuming one session—or ordinary past-conversation search—use Pi's `/resume` instead.

## Workflow

1. Resolve paths relative to this `SKILL.md`, then run `python3 <skill-directory>/scripts/session_search.py --help` to read the current CLI contract.
2. Translate the user's stated scope and filters into CLI options. With no explicit scope, retain the script's current-working-directory default. Prefer `--summary-only` unless representative evidence is necessary.
3. Run the script locally. It reads session JSONL files without modifying them or creating an index.
4. Interpret the returned JSON as evidence, not as an automatic judgment. Keep direct skill invocations separate from reads of a skill's `SKILL.md`; a file read alone does not establish use.
5. Report only what is needed to answer the request.

## Privacy

Session data can contain credentials, personal information, private source code, and local paths. The script applies best-effort masking to evidence snippets, but no pattern-based masking can guarantee removal of every sensitive value.

- Do not send session contents or script output to external tools or services.
- Do not quote raw evidence beyond what the user needs.
- Preserve masked values exactly; never attempt to reconstruct them.
- Treat file paths, session identifiers, and warnings as potentially sensitive too.
