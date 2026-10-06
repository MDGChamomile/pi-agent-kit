# Contributing

This repository is an opinionated collection of skills and extensions maintained for the author's own Pi workflow. Issues, examples, and focused suggestions are welcome; inclusion in the collection is not guaranteed.

For a proposed change:

1. Explain the recurring problem and the observable improvement.
2. Keep each skill or extension small, self-contained, and inspectable.
3. Document invocation, side effects, platform assumptions, and any required setup.
4. Keep credentials, private data, absolute machine paths, and generated dependencies out of the repository.
5. Run the checks appropriate to the changed resource below; distinguish offline results from live Pi/provider verification.
6. Prefer adapting a resource in your own fork when the desired behavior is personal or highly specific.

The [harness-minimalism principles](https://github.com/MDGChamomile/MDGChamomile/blob/main/PRINCIPLE.md) are maintained in the MDGChamomile repository. This repository's [PRINCIPLE.md](PRINCIPLE.md) is a pointer, not a separate copy; propose changes to the principles at the canonical source.

## Pull requests

Create your contribution branch from the latest `updates` branch, and select
`updates` as the base branch when opening a pull request. GitHub may suggest
`main` because it is the repository's default branch; please change the base
to `updates` before submitting.

### External contributions

Fork the repository and clone your fork. In a fresh clone, where `origin` points
to your fork and `upstream` has not yet been added:

```bash
git remote add upstream https://github.com/MDGChamomile/pi-agent-kit.git
git fetch upstream updates
git switch -c my-change upstream/updates
# Make your change and run the relevant checks below.
git push -u origin my-change
```

Open a PR from your fork's `my-change` branch to this repository's `updates`,
not your fork's `updates` or this repository's default `main`. Use the
[PR template](.github/pull_request_template.md) to explain the Summary,
Verification, and Risk. If you accidentally target `main`, change the base to
`updates` and review the resulting diff and checks again.

External contributors do not need to merge `main`, synchronize release history,
or perform releases; those are maintainer responsibilities.

### Branch protection and review

Both `main` and `updates` require PRs. Do not push directly to them, rewrite
their history, or bypass protection. The current merge method is a merge commit;
the [live GitHub rules](https://github.com/MDGChamomile/pi-agent-kit/rules) are
authoritative if configuration changes.

The required checks for `updates` are currently `skills` and
`pi-compaction-model`, defined in the
[validation workflow](.github/workflows/live-validation.yml). Before merging,
maintainers verify the latest PR head, applicable required checks, and review
conversations. Findings must be fixed and verified or declined with a reason
before their threads are resolved; unresolved issues must not be closed merely
to unblock merging.

Eligible PRs targeting `updates` receive automatic Pullfrog reviews, including
external contributions. PR content is shared with that external review service;
do not include credentials or private data. Pullfrog reviews only: it does not
modify code, approve PRs, or merge them. A successful review-run check means the
run completed, not that the PR was approved. Maintainers assess findings and
perform any changes and merges. See the [review policy](.github/PULLFROG.md).

### Maintainer development and release history

Keep unmerged work on a task branch, not on local `updates`. The normal flow is:

```text
latest origin/updates -> local task branch -> remote task branch
-> PR into updates -> merge -> fetch and fast-forward local updates
```

The final fast-forward makes local `updates` match `origin/updates` without
creating another merge commit. GitHub merges do not update local branches
automatically.

Maintainers open `updates` -> `main` PRs only for explicitly authorized releases.
A release merge can leave a main-only merge commit even when no files differ;
this is an expected history difference, not missing development code. Identical
`main` and `updates` SHAs are not a development requirement.

With explicit authorization, maintainers can include that release history in
the next task branch and its existing PR instead of creating a separate history
PR. First verify that the main-only commits are completed `updates` -> `main`
release merges in this repository and that `main` has the same file tree as the
common ancestor. Merge the verified main SHA into the task branch normally and
confirm its file tree is unchanged by that merge. Unexpected changes, conflicts,
or unverified history require separate review and authorization; matching trees
or commit messages alone do not establish provenance. Consider a separate
history-sync PR only when immediate synchronization is requested or combining it
with an authorized task is not appropriate.

## Verification entry points

Use the smallest relevant set of checks. For prose-only changes, review examples, relative links, and consistency with the source; do not make model calls just to validate wording. Run the skill metadata check for `SKILL.md` changes. For behavior changes, add a regression test and run the affected resource's offline suite. Pi Subagent and Pi Jev changes belong in their independent repositories; use the verification instructions there.

The commands below match the relevant `live-validation` entry points. Python checks need Python 3.10+. JavaScript checks use Node.js 22.22+ unless noted. Install development dependencies only when needed; those installation commands may access package registries.

| Changed area | Working directory | Setup | Offline verification |
| --- | --- | --- | --- |
| Skill frontmatter or maintained Markdown relative links | Repository root | None | `python3 -B .github/scripts/validate_skills.py` |
| Skill validator or its CI step | Repository root | None | `python3 -B -m unittest discover -s .github/scripts -p 'test_*.py' -v`, then the metadata check above |
| Session search / recall | `live/skills/session-search` | None | `python3 -B -m unittest discover -s tests -v` |
| Deep-plan records-root and publication helpers | Repository root | None | `set -- live/skills/deep-plan/scripts/*.test.mjs; test -f "$1" && node --test "$@"` |
| Compaction model extension | `live/extensions/pi-compaction-model` | Bun 1.3.14; `bun install --frozen-lockfile` | `bun run check` |

For moved resources, contribute and verify in [Pi Subagent](https://github.com/MDGChamomile/pi-subagent/blob/main/CONTRIBUTING.md) or [Pi Jev](https://github.com/MDGChamomile/pi-jev/blob/main/CONTRIBUTING.md). Their runtime sources, companion skills, test dependencies, and release workflows are no longer maintained in this kit.

The frontmatter check verifies opening/closing delimiters and non-empty required fields inside them. The same command checks relative Markdown links in every `SKILL.md` and in the maintained root documents (`README.md`, `AGENTS.md`, `MIGRATION.md`, `CONTRIBUTING.md`, and `PRINCIPLE.md`); it is not a complete YAML schema validator or a general Markdown linter.

See the [compaction guide](live/extensions/pi-compaction-model/README.md#development) for its pinned test environment. For deep-plan workflow changes, select relevant scenarios from its [behavior evaluations](live/skills/deep-plan/references/behavior-evals.md). Report any checks you could not run.

Live model/web smoke tests and evaluations are opt-in, can disclose supplied content, and consume provider usage. Obtain applicable authorization before running them; neither a documentation change nor an offline test pass establishes real-provider compatibility. Do not install repository changes into an active Pi environment merely to validate a contribution.

Substantial additions or behavior changes should start with an issue. By contributing, you agree that your contribution is licensed under the repository's MIT License.
