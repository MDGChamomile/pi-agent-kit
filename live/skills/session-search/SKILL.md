---
name: session-search
description: Aggregate factual evidence across multiple local Pi sessions, including counts, repeated errors, and tool or skill usage. Use for cross-session analysis; do not use to find, open, or resume a single session.
license: MIT
compatibility: Requires Pi session JSONL files and Python 3.10 or later.
---

# Session Search

Use this skill only when a request needs factual aggregation across multiple Pi sessions. For finding, opening, or resuming one session—or ordinary past-conversation search—use Pi's `/resume` instead.

## Workflow

1. Resolve paths relative to this `SKILL.md`, then run `python3 <skill-directory>/scripts/session_search.py --help`. Treat that output as the single source of truth for current options, defaults, repetition rules, and mutually exclusive flags; never invent plausible aliases.
2. Translate only the user's stated scope and filters into options shown by `--help`. With no explicit scope, retain the script's current-working-directory default and path-free aggregate output.
3. Run the script locally. It reads session JSONL files without modifying them or creating an index.
4. Interpret the returned JSON as evidence, not as an automatic judgment. Direct invocation means a user-role message matching Pi's complete skill envelope; keep it separate from reads of a skill's `SKILL.md`, mentions, and quoted XML.
5. Report only what is needed to answer the request. Use the bounded evidence mode shown by `--help` only after the user explicitly approves sending masked snippets, local paths, and session identifiers to the active model provider.

## Privacy

Session data can contain credentials, personal information, private source code, and local paths. Tool results become context for the active model, so an agent-run search can send returned data to that model provider. The user's cross-session analysis request authorizes only the default path-free aggregate unless they explicitly approve evidence disclosure.

- Keep the default summary mode unless the user explicitly approves `--include-evidence` after being told that masked snippets, local paths, session identifiers, and warning paths will reach the active model provider. When approval is still being requested, ask only for consent: do not run or emit a prepared evidence command, keep command arguments empty, and treat the report scope as none until approval arrives.
- Best-effort masking is not a data-loss-prevention guarantee. Do not quote raw evidence beyond what the user approved and needs.
- Preserve masked values exactly; never attempt to reconstruct them.
- Do not send session contents or script output to any additional external tool or service.
