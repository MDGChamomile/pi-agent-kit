# Pi Agent Kit

The skills and extensions I use and experiment with personally for the [Pi coding agent](https://github.com/earendil-works/pi). This is a public, source-first collection: read the resources, take what is useful, and adapt it to your own workflow.

It is not published as an npm package or maintained as an install-everything Pi package. Skills and extensions remain ordinary files so they are easy to inspect, link, copy, and change.

## Contents

### Skills

| Skill | Purpose | Invoke |
| --- | --- | --- |
| [`deep-plan`](skills/deep-plan/SKILL.md) | Turn a vague repository change into an aligned execution record | `/skill:deep-plan` |
| [`meta-prompt`](skills/meta-prompt/SKILL.md) | Write or improve a compact, ready-to-use prompt | `/skill:meta-prompt` |
| [`nomore-harness`](skills/nomore-harness/SKILL.md) | Assess whether a proposed Pi Skill or Extension should be added as-is | `/skill:nomore-harness` |

### Extensions

| Extension | Purpose |
| --- | --- |
| [`git-history`](extensions/git-history/index.ts) | Add `/snapshot` to review and commit changes in the Pi agent directory |

`/snapshot` shows the Git status and asks for confirmation before staging and committing changes in the configured Pi agent directory. Use it only when that directory is intentionally a Git repository.

## Use with Pi

> [!WARNING]
> Skills can instruct an agent to take actions, and extensions run with your user permissions. Review any resource before enabling it.

Clone the repository somewhere stable:

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
cd pi-agent-kit
```

Then link only the resources you want into Pi's global discovery directories. The commands below target macOS and Linux.

### Link a skill

```bash
mkdir -p ~/.pi/agent/skills
ln -s "$PWD/skills/meta-prompt" ~/.pi/agent/skills/meta-prompt
```

### Link an extension

```bash
mkdir -p ~/.pi/agent/extensions
ln -s "$PWD/extensions/git-history" ~/.pi/agent/extensions/git-history
```

Run `/reload` in Pi after adding, removing, or changing a link. Edits made in this repository are reflected through the links immediately.

To unlink a resource without deleting its source:

```bash
rm ~/.pi/agent/skills/meta-prompt
rm ~/.pi/agent/extensions/git-history
```

You can also copy a resource instead of linking it when you want an independent version. Copied resources do not receive later repository changes automatically.

## Updating

Pull changes when you choose:

```bash
cd /path/to/pi-agent-kit
git pull --ff-only
```

Review the diff before reloading Pi, especially for extensions.

## Layout

```text
extensions/   Pi TypeScript extensions
skills/       Agent Skills-compatible skill directories
```

Resources under `skills/` and `extensions/` are the source of truth. Supporting references, scripts, and assets stay beside the resource that uses them.

## Contributing

This is an opinionated personal collection, but issues and suggestions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
