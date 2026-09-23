# pi-compaction-model development and verification

This document records development checks and historical smoke-test details. For installation, configuration, runtime behavior, and user-facing limitations, see the [extension guide](README.md).

## Offline checks

From this directory, with Bun 1.3.14:

```bash
bun install --frozen-lockfile
bun run check
```

The `live-validation` CI workflow runs these commands with Bun 1.3.14. A fresh frozen-lockfile installation against the inherited Pi 0.80.7 dependency passed typechecking and all 13 tests.

The inherited lockfile pins the original development environment. To check a newer Pi version, typecheck and run the tests against that version in an isolated development copy; do not treat the inherited dependency range as verification of every later release.

`test/config.test.ts` tests configuration parsing and merging. `test/index.test.ts` mocks the compaction API and checks file-list restoration in dedicated-model and fallback paths. The test script runs the files in separate processes so module mocks cannot leak between them. These tests make no model requests and do not use real credentials.

## Kit verification

Pi 0.85.1 typechecking passed with TypeScript 7.0.2. All 13 tests passed with Bun 1.3.14 against an existing Pi 0.85.1 installation, and Pi's extension loader registered exactly one compaction handler without errors. These checks used temporary copies and existing dependencies, not a fresh lockfile installation.

A separate Pi 0.85.1 SDK smoke test with synthetic messages and `openai-codex/gpt-5.6-luna` (`medium`) passed two dedicated-model compactions followed by native fallback after a deliberately failed model lookup. All three retained cumulative read/modified file lists in both summary text and details, and the active model stayed unchanged. The temporary test harness forced SSE, disabled retries, imposed a 60-second cancellation signal per request, and made exactly three model requests. This does not test every provider or failure mode. This Pi version's Codex transport does not forward `maxTokens` as a server-side output cap, so it cannot guarantee that cap.

An additional source smoke on 2026-09-15 used Pi 0.85.1 and Node.js 22.22.3 with `openai-codex/gpt-6-astra` / `medium` as the active model, retaining Luna/medium for dedicated compaction. Two Luna compactions and a deliberately failed model lookup followed by native Astra compaction all passed. Each preserved cumulative file lists in both summary sections and details; the active model and thinking stayed Astra/medium. Wire model/thinking and response identity were verified for all three requests.

The temporary SDK harness used synthetic in-memory messages and isolated settings, forced SSE, disabled retries, imposed a 60-second signal per request, and enforced a three-request transport limit. The original smoke above remains a separate record. Source-only results and source/harness hashes are in [`verification/2026-09-15-astra-medium.json`](verification/2026-09-15-astra-medium.json). This manual, non-split-turn smoke does not establish summary quality, performance, automatic threshold/overflow behavior, or recovery from actual provider errors or cancellation.

## Single-retry regression verification

The fixed single-retry policy passed `bun run check` with Bun 1.3.14 and TypeScript 7.0.2 against both the frozen Pi 0.80.7 dependency and Pi 0.85.1 in an isolated copy (29 tests each). `test/index.test.ts` covers transient recovery for all three reasons, exhaustion, unchanged request arguments, deterministic/unknown failures, lookup/authentication failures, and cancellation before/during requests and backoff. `test/retry.test.ts` verifies cancellation with the real backoff timer; it runs in a separate process to avoid timer/module mock leakage. No live provider requests were made.

The retry wrapper intentionally does not inherit Pi settings or pass a native retry policy. Pi 0.80.7 lacks the compaction retry arguments; the wrapper bounds complete compaction attempts uniformly across these versions. It is not a generic retry framework and does not bound provider-internal HTTP attempts. Review the wrapper when changing the minimum supported Pi version.

## Live verification boundary

Offline tests and typechecking do not establish real-provider compatibility. Before switching an active installation, verify loading in Pi and test compaction separately with an authorized model call. Compaction sends session content to the configured provider and can incur usage charges; returning control to Pi may lead to another request with the active model. The extension does not change the active conversation model or write its own settings.
