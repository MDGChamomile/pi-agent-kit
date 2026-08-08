# Pi Agent Kit

The skills and extensions I use and experiment with personally for the [Pi coding agent](https://github.com/earendil-works/pi). This is a public, source-first collection: read the resources, take what is useful, and adapt it to your own workflow.

It is not published as an npm package or maintained as an install-everything Pi package. Skills and extensions remain ordinary files so they are easy to inspect, link, copy, and change.

## Live

Resources currently used and maintained.

### Skills

| Skill | Purpose | Invoke |
| --- | --- | --- |
| [`deep-plan`](live/skills/deep-plan/SKILL.md) | Turn a vague repository change into an aligned execution record | `/skill:deep-plan` |
| [`nomore-harness`](live/skills/nomore-harness/SKILL.md) | Assess whether a proposed Pi Skill or Extension should be added as-is | `/skill:nomore-harness` |

### Extensions

| Extension | Purpose |
| --- | --- |
| [`git-history`](live/extensions/git-history/index.ts) | Add `/snapshot` to review and commit changes in the Pi agent directory |

`/snapshot` shows the Git status and asks for confirmation before staging and committing changes in the configured Pi agent directory. Use it only when that directory is intentionally a Git repository.

## Retired

Resources kept for reference but no longer actively used or maintained.

| Resource | Purpose |
| --- | --- |
| [`meta-prompt`](retired/skills/meta-prompt/SKILL.md) | Write or improve a compact, ready-to-use prompt |

## Agent instructions

[`AGENTS.md`](AGENTS.md) contains the global operating preferences used in my Pi environment.

Unlike the lengthy AGENTS.md and CLAUDE.md files commonly used in tools like Codex or Claude Code, this file contains only the minimal, essential instructions designed to maximize the performance and autonomy of modern AI models without imposing unnecessary constraints. Although originally spanning over 100 lines, this streamlined set of instructions is more than sufficient for optimal behavior—feel free to test it out.

## Use with Pi

> [!WARNING]
> Skills can instruct an agent to take actions, and extensions run with your user permissions. Review any resource before enabling it.

Clone the repository, then link only the live resources you want. These commands target macOS and Linux.

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
cd pi-agent-kit

mkdir -p ~/.pi/agent/skills ~/.pi/agent/extensions
ln -s "$PWD/live/skills/deep-plan" ~/.pi/agent/skills/deep-plan
ln -s "$PWD/live/extensions/git-history" ~/.pi/agent/extensions/git-history
```

Run `/reload` in Pi after changing links. Repository edits are reflected through the links immediately.

## Contributing

This is an opinionated personal collection, but issues and suggestions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
