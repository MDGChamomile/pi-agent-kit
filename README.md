# Pi Agent Kit

The skills and extensions I use or have experimented with personally for the [Pi coding agent](https://github.com/earendil-works/pi). This is a public, source-first collection: read the resources, take what is useful, and adapt it to your own workflow.

It is not published as an npm package or maintained as an install-everything Pi package. Skills and extensions remain ordinary files so they are easy to inspect, link, copy, and change.

## Live

Resources currently used and maintained.

### Skills

| Skill | Purpose | Invoke |
| --- | --- | --- |
| [`deep-plan`](live/skills/deep-plan/SKILL.md) | Turn a vague repository change into an aligned execution record | `/skill:deep-plan` |
| [`session-search`](live/skills/session-search/README.md) | Aggregate counts, errors, and tool or skill usage across local Pi sessions | `/skill:session-search` |

### Extensions

| Extension | Purpose | Platform |
| --- | --- | --- |
| [`whitebox`](live/extensions/whitebox/README.md) | Run project commands and Pi file tools inside a strict offline Bubblewrap boundary | Linux |

## Retired

Resources kept for reference but no longer actively used or maintained.

| Resource | Purpose |
| --- | --- |
| [`git-history`](retired/extensions/git-history/index.ts) | Add `/snapshot` to review and commit changes in the Pi agent directory |
| [`meta-prompt`](retired/skills/meta-prompt/SKILL.md) | Write or improve a compact, ready-to-use prompt |
| [`nomore-harness`](retired/skills/nomore-harness/SKILL.md) | Review proposed additions to a Pi environment before adoption |

`git-history` was retired because its stage-all flow could commit changes beyond the intended review boundary.

## Agent instructions

[`AGENTS.md`](AGENTS.md) contains the global operating preferences used in my Pi environment.

Unlike the lengthy AGENTS.md and CLAUDE.md files commonly used in tools like Codex or Claude Code, this file contains only the minimal, essential instructions designed to maximize the performance and autonomy of modern AI models without imposing unnecessary constraints. Although originally spanning over 100 lines, this streamlined set of instructions is more than sufficient for optimal behavior—feel free to test it out.

## Contributing

This is an opinionated personal collection, but issues and suggestions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
