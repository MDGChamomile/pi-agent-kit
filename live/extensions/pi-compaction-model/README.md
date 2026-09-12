# pi-compaction-model

A minimal extension for [Pi Coding Agent](https://github.com/earendil-works/pi) that lets native compaction use a dedicated model and thinking level.

It does not introduce a new summarization pipeline. It calls Pi's exported `compact()` implementation with the configured model, preserving Pi's native:

- prompts and structured summary format
- cut-point and recent-message retention behavior
- iterative previous-summary updates
- split-turn summaries
- file-operation tracking
- output-token budgeting
- `/compact` focus instructions

If the configured model is unavailable or fails, the extension returns control to Pi, which compacts with the active conversation model.

## Origin and maintenance

This is an independently maintained derivative of [JMHSV/pi-compaction-model](https://github.com/JMHSV/pi-compaction-model), not an official upstream successor. Original copyright and MIT terms are preserved in [LICENSE](LICENSE).

Imported from revision `283f0de4fe56d4cc35931e1255e0d3888761426b`, including [upstream PR #1](https://github.com/JMHSV/pi-compaction-model/pull/1): restore cumulative file-operation lists before falling back to Pi's active model. This concerns file lists in compaction summaries, not loss of files on disk.

Kit-specific changes: source-install documentation and private package metadata; aligning the lockfile's peer range with the inherited manifest; and omitting deleted (`null`) authentication headers before calling `compact()`, matching Pi 0.85.1's native bridge, with a regression test. The original compaction routing, file-list restoration, tests, and `compactionModel` configuration are retained. This directory is not separately published to npm; `npm:pi-compaction-model` installs the upstream package, not this derivative.

## Install from source

Requires Pi with the APIs used by this extension (upstream declares `>=0.80.7`). See [Development](#development) for verification; the declared minimum is not a tested compatibility matrix. Runtime dependencies are supplied by Pi; Bun is needed only for development. The commands below assume a POSIX shell.

Review this directory, then copy it from a checkout:

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
mkdir -p ~/.pi/agent/extensions
cp -R pi-agent-kit/live/extensions/pi-compaction-model ~/.pi/agent/extensions/
```

Copy only into a destination that does not already exist; do not overwrite another installation. Keep `package.json`, `src/`, and `LICENSE` together: the `pi.extensions` manifest points to `src/index.ts`. No build or dependency installation is required for runtime use.

If upstream is already installed, remove its Pi package registration with `pi remove npm:pi-compaction-model` as part of the transition before loading this copy. Also check for any other copies registered through settings or symlinks. Do not load both versions: both handle the same compaction hook.

Restart Pi after installation, or use `/reload`.

## Configure

Add `compactionModel` to `~/.pi/agent/settings.json`:

```json
{
  "compactionModel": {
    "model": "openai-codex/gpt-5.6-terra",
    "thinkingLevel": "medium"
  }
}
```

`model` must be a model known to Pi in `provider/model` form.

Supported thinking levels are:

```text
off, minimal, low, medium, high, xhigh, max
```

Omit `thinkingLevel` to use the provider default.

### Select which compactions to route

By default the configured model handles all native compaction reasons:

- `manual` — `/compact`
- `threshold` — automatic context-threshold compaction
- `overflow` — overflow recovery before retry

Use `reasons` to handle only a subset:

```json
{
  "compactionModel": {
    "model": "google/gemini-2.5-flash",
    "thinkingLevel": "low",
    "reasons": ["threshold", "overflow"]
  }
}
```

An empty `reasons` array disables routing without removing the configuration. You can also use `"enabled": false`, or set `"compactionModel": false` in trusted project settings.

### Project overrides

A trusted project's `.pi/settings.json` can override individual global fields:

```json
{
  "compactionModel": {
    "model": "anthropic/claude-sonnet-4-5"
  }
}
```

Project fields are shallow-merged over the global `compactionModel` object. Untrusted project settings are ignored.

## Coexisting with other compaction extensions

Multiple extensions can handle `session_before_compact`, and the last extension that returns a compaction result wins. Avoid configuring two extensions for the same reason.

For example, to use Smart Compact manually and this extension only for automatic native compaction:

```json
{
  "smartCompact": {
    "autoTrigger": false
  },
  "compactionModel": {
    "model": "openai-codex/gpt-5.6-terra",
    "thinkingLevel": "medium",
    "reasons": ["threshold", "overflow"]
  }
}
```

The resulting routing is:

| Event | Handler |
|---|---|
| `/smart-compact` | Smart Compact |
| `/compact` | Pi native compaction with the active model |
| Automatic threshold | Pi native compaction algorithm with the configured model |
| Overflow recovery | Pi native compaction algorithm with the configured model |
| Configured-model failure | Pi native fallback with the active model |

## Failure behavior

The extension logs a warning and falls back to Pi's active model when:

- the configuration is invalid
- the model cannot be found
- authentication cannot be resolved
- the compaction request fails or is cancelled

Pi currently resolves authentication for the active conversation model before firing the compaction extension hook. Consequently, the active model must also have valid authentication even when a dedicated compaction model is configured.

## Development

From this directory, with Bun 1.3.14:

```bash
bun install --frozen-lockfile
bun run check
```

The inherited lockfile pins the original development environment. To check a newer Pi version, typecheck and run the tests against that version in an isolated development copy; do not treat the inherited dependency range as verification of every later release.

Kit verification: Pi 0.85.1 typecheck passed with TypeScript 7.0.2; all 13 tests passed with Bun 1.3.14 against an existing Pi 0.85.1 installation; Pi's extension loader registered exactly one compaction handler without errors. These checks used temporary copies and existing dependencies, not a fresh lockfile installation.

A separate Pi 0.85.1 SDK smoke test with synthetic messages and `openai-codex/gpt-5.6-luna` (`medium`) passed two dedicated-model compactions followed by native fallback after a deliberately failed model lookup. All three retained cumulative read/modified file lists in both summary text and details, and the active model stayed unchanged. The temporary test harness forced SSE, disabled retries, and imposed a 60-second cancellation signal per request; it made exactly three model requests. This does not test every provider or failure mode. This Pi version's Codex transport does not forward `maxTokens` as a server-side output cap, so it cannot guarantee that cap.

`test/config.test.ts` tests configuration parsing and merging. `test/index.test.ts` mocks the compaction API and checks file-list restoration in dedicated-model and fallback paths. The test script runs the files in separate processes so module mocks cannot leak between them. These tests make no model requests and do not use real credentials.

Offline tests and typechecking do not establish real-provider compatibility. Before switching an active installation, verify loading in Pi and test compaction separately with an authorized model call. Compaction sends session content to the configured provider and can incur usage charges; fallback may make another request with the active model. The extension does not change the active conversation model or write its own settings.

## License

[MIT](LICENSE), Copyright (c) 2026 JMHSV.
