---
name: session-search
description: Analyze patterns across local Pi sessions or recall how a topic was handled in a prior session. Use for cross-session counts, repeated errors, tool or skill usage, and questions such as "How did we solve X before?" Do not use to open or resume a session.
license: MIT
compatibility: Requires Pi session JSONL files and Python 3.10 or later.
---

# Session Search

Use this skill for factual aggregation across multiple Pi sessions and for bounded recall of relevant text from a prior session. Use Pi's `/resume` instead when the user wants to find interactively, open, or continue a session.

## Choose the workflow

- For counts, repeated errors, or tool and skill usage, use `scripts/session_search.py` and the aggregate workflow below.
- For questions about what was discussed, decided, or done in a prior session, use `scripts/session_recall.py` and the find-then-recall workflow below.

Resolve paths relative to this `SKILL.md`. Run the selected script with `--help` on its first use in the current session, and run subcommand help when using recall. Reuse that output unless the script changed, options are unclear, or the earlier output is no longer available. Treat help output as the source of truth; never invent aliases.

## Aggregate workflow

1. Translate only the user's stated scope and filters into options shown by `session_search.py --help`. With no explicit scope, retain the current-working-directory default and path-free summary output. Add directories only when the user or local instructions specify them.
2. Run the script locally. For several independent summary counts over the same scope, prefer up to eight `--batch-filter` JSON objects in one invocation rather than rescanning for each condition. Use only the keys and limits documented in the help and [batch guide](README.md#batch-summaries); batch mode is summary-only and cannot include evidence or individual filter flags. The script reads session JSONL files without modifying them or creating an index.
3. Interpret the JSON as evidence, not as an automatic judgment. Keep direct skill invocations separate from reads of a skill's `SKILL.md`, mentions, and quoted XML.
4. Use `--include-evidence` only after the evidence consent described below.

## Find-then-recall workflow

1. Translate the natural-language topic into two to eight meaningful literal terms. Prefer distinctive words or short phrases, including Unicode and Korean terms; do not pass the whole question as one exact phrase.
2. Run `session_recall.py find` first. Repeated terms are alternatives used to rank matching sessions. Keep the default current-project scope unless the user explicitly requests another scope.
3. Treat the returned candidate ranks and match counts only as a local relevance ordering. Do not infer an outcome from them.
4. Before running `session_recall.py recall`, obtain the evidence consent described below. Recall the minimum candidate ranks needed to answer the question.
5. Explain omitted context when material. Recall searches only the active branch, includes bounded user and assistant text around matches, and excludes thinking, tool calls, tool results, and unrelated first or last messages.

## Privacy and consent

Session data can contain credentials, personal information, private source code, and local paths. Tool results become context for the active model and may therefore reach its provider. A cross-session or recall request authorizes only path-free aggregate or candidate metadata unless the user explicitly approves evidence disclosure.

- Before any `--include-evidence` invocation, tell the user that masked conversation snippets and associated timestamps will reach the active model provider. For aggregate evidence, also disclose that local paths, session identifiers, and warning paths will be included. Ask only for consent; do not run or emit a prepared evidence command while approval is pending.
- Best-effort masking is not a data-loss-prevention guarantee. Quote only the approved evidence needed for the answer.
- Preserve masked values exactly and never attempt to reconstruct them.
- Do not send session contents or script output to any additional external tool or service.
