# Pi Agent Kit

The skills and extensions I use or have experimented with personally for the [Pi coding agent](https://github.com/earendil-works/pi). This is a public, source-first collection curated according to a set of [harness-minimalism principles](PRINCIPLE.md): read the resources, take what is useful, and adapt it to your own workflow.

It is not published as an npm package or maintained as an install-everything Pi package. Skills and extensions remain ordinary files so they are easy to inspect, link, copy, and change.

## Live

Resources currently used and maintained.

### Skills

| Skill | Purpose | Invoke |
| --- | --- | --- |
| [`deep-plan`](live/skills/deep-plan/SKILL.md) | Turn a vague repository change into an aligned execution record | `/skill:deep-plan` |
| [`pi-subagent`](live/skills/pi-subagent/SKILL.md) | Delegate noisy local-file or public-web investigation and return only a bounded report | Model-selected or `/skill:pi-subagent` |
| [`session-search`](live/skills/session-search/README.md) | Aggregate counts, errors, and tool or skill usage across local Pi sessions | `/skill:session-search` |

### Extensions

| Extension | Purpose | Platform |
| --- | --- | --- |
| [`pi-subagent`](live/extensions/pi-subagent/README.md) | Run bounded, isolated, read-only local or public-web investigations outside the parent context | Portable (tested on Linux) |
| [`whitebox`](live/extensions/whitebox/README.md) | Run project commands and Pi file tools inside a strict offline Bubblewrap boundary | Linux |

## Retired

Resources kept for reference but no longer actively used or maintained.

| Resource | Purpose |
| --- | --- |
| [`git-history`](retired/extensions/git-history/index.ts) | Add `/snapshot` to review and commit changes in the Pi agent directory |
| [`meta-prompt`](retired/skills/meta-prompt/SKILL.md) | Write or improve a compact, ready-to-use prompt |
| [`nomore-harness`](retired/skills/nomore-harness/SKILL.md) | Review proposed additions to a Pi environment before adoption |

## Contributing

This is an opinionated personal collection, but issues and suggestions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
