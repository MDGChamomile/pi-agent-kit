# Contributing

This repository is an opinionated collection of skills and extensions maintained for the author's own Pi workflow. Issues, examples, and focused suggestions are welcome; inclusion in the collection is not guaranteed.

For a proposed change:

1. Explain the recurring problem and the observable improvement.
2. Keep each skill or extension small, self-contained, and inspectable.
3. Document invocation, side effects, platform assumptions, and any required setup.
4. Keep credentials, private data, absolute machine paths, and generated dependencies out of the repository.
5. Run the checks appropriate to the changed resource below; distinguish offline results from live Pi/provider verification.
6. Prefer adapting a resource in your own fork when the desired behavior is personal or highly specific.

## Verification entry points

Use the smallest relevant set of checks. For prose-only changes, review examples, relative links, and consistency with the source; do not make model calls just to validate wording. Run the skill metadata check for `SKILL.md` changes. For behavior changes, add a regression test and run the affected resource's offline suite. Changes to the paired pi-subagent runtime or package require all three checks in its maintenance guide.

The commands below match the relevant `live-validation` entry points. Python checks need Python 3.10+. JavaScript checks use Node.js 22.22+ unless noted. Install development dependencies only when needed; those installation commands may access package registries.

| Changed area | Working directory | Setup | Offline verification |
| --- | --- | --- | --- |
| Skill frontmatter or relative links | Repository root | None | `python3 -B .github/scripts/validate_skills.py` |
| Skill validator or its CI step | Repository root | None | `python3 -B -m unittest discover -s .github/scripts -p 'test_*.py' -v`, then the metadata check above |
| Session search / recall | `live/skills/session-search` | None | `python3 -B -m unittest discover -s tests -v` |
| simplykst calculator | `live/skills/simplykst` | None | `python3 -B -m unittest discover -s tests -v` |
| Deep-plan publication helper | Repository root | None | `node --test live/skills/deep-plan/scripts/publish-plan.test.mjs` |
| Pi Subagent | `live/extensions/pi-subagent` | `npm ci --include=dev --ignore-scripts`; Python 3 and `rg` must be available | `npm run typecheck`, `npm test`, `npm run package:check` |
| Compaction model extension | `live/extensions/pi-compaction-model` | Bun 1.3.14; `bun install --frozen-lockfile` | `bun run check` |
| Jev reranking extension | Repository root | Node 22.22+; locked Pi/TypeScript dependencies from `live/extensions/pi-subagent` for the load check | See the [Jev guide](live/extensions/pi-jev-tools/README.md#offline-verification) for mocked-HTTP tests and offline Pi loading/typecheck |
| Jev routing extension | Repository root | Node 22.22+; locked Pi/TypeScript dependencies from `live/extensions/pi-subagent` for the load check | See the [router guide](live/extensions/pi-jev-router/README.md#offline-verification) for mocked-HTTP tests and offline Pi loading/typecheck |
| Shared Jev skill | Repository root | None | `python3 -B .github/scripts/validate_skills.py`; review both extension-guide links and selection guidance |

The Jev CI job reuses the subagent development lockfile for Pi/TypeScript. Its transport tests use mocked HTTP responses and synthetic keys, not a real credential or provider call.

The frontmatter check verifies opening/closing delimiters and non-empty required fields inside them, plus relative Markdown links in `SKILL.md`; it is not a complete YAML schema validator. README and reference-document links still need review.

See the [Pi Subagent maintenance guide](packaging/pi-subagent/DEVELOPMENT.md) for package assembly and offline discovery checks, and the [compaction guide](live/extensions/pi-compaction-model/README.md#development) for its pinned test environment. For deep-plan workflow changes, select relevant scenarios from its [behavior evaluations](live/skills/deep-plan/references/behavior-evals.md). Report any checks you could not run.

Live model/web smoke tests and evaluations are opt-in, can disclose supplied content, and consume provider usage. Obtain applicable authorization before running them; neither a documentation change nor an offline test pass establishes real-provider compatibility. Do not install repository changes into an active Pi environment merely to validate a contribution.

Substantial additions or behavior changes should start with an issue. By contributing, you agree that your contribution is licensed under the repository's MIT License.
