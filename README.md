# Pi Agent Kit

[![live-validation](https://github.com/MDGChamomile/pi-agent-kit/actions/workflows/live-validation.yml/badge.svg?branch=main)](https://github.com/MDGChamomile/pi-agent-kit/actions/workflows/live-validation.yml)
[![Latest release](https://img.shields.io/github/v/release/MDGChamomile/pi-agent-kit)](https://github.com/MDGChamomile/pi-agent-kit/releases/latest)
[![License](https://img.shields.io/github/license/MDGChamomile/pi-agent-kit)](LICENSE)

> Inspectable, copy-friendly skills and extensions for the [Pi coding agent](https://github.com/earendil-works/pi).

Pi Agent Kit is the public, source-first collection of resources I currently use or have tested in my own workflow. It is for people who prefer to adopt one small, understandable component at a time instead of installing a complete agent framework.

- **Skills** provide focused workflows that Pi loads on demand.
- **Extensions** add tools or enforce runtime boundaries.
- **Live** resources are currently used and maintained.
- **Retired** resources remain available as references.

The collection follows a set of [harness-minimalism principles](PRINCIPLE.md): read the source, take what is useful, and adapt it to your own workflow. It is not maintained as an install-everything Pi package. The `pi-subagent` skill and extension are also distributed together as the focused [`@mdgchamomile/pi-subagent`](https://www.npmjs.com/package/@mdgchamomile/pi-subagent) package.

## Start here

| If you want to… | Start with | Adopt it by… |
| --- | --- | --- |
| Isolate noisy investigation from the main context | [`pi-subagent`](live/extensions/pi-subagent/README.md) | Installing the paired skill and extension from npm |
| Turn a vague repository change into an executable plan | [`deep-plan`](live/skills/deep-plan/SKILL.md) | Copying the standalone skill from source |
| Analyze patterns across local Pi sessions | [`session-search`](live/skills/session-search/README.md) | Copying the standalone skill from source |

### Install Pi Subagent

Pi Subagent requires Linux, including Ubuntu on WSL; native Windows is not officially supported or tested. See the [extension guide](live/extensions/pi-subagent/README.md#requirements-and-installation) for its complete requirements and security model.

```bash
pi install npm:@mdgchamomile/pi-subagent
```

### Copy a standalone resource

Clone the repository, review the resource, and copy or link only the directory you want into the applicable Pi location. For example:

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
mkdir -p ~/.pi/agent/skills
cp -R pi-agent-kit/live/skills/deep-plan ~/.pi/agent/skills/
```

Restart Pi, or use `/reload` for an auto-discovered resource.

> [!CAUTION]
> Skills can instruct the model to take actions, and extensions run with the user's system permissions. Review each resource before adopting it.

## Retired

Resources kept for reference but no longer actively used or maintained:

| Resource | Purpose |
| --- | --- |
| [`whitebox`](retired/extensions/whitebox/README.md) | Run project commands and Pi file tools inside an offline Linux Bubblewrap boundary |
| [`git-history`](retired/extensions/git-history/index.ts) | Add `/snapshot` to review and commit changes in the Pi agent directory |
| [`meta-prompt`](retired/skills/meta-prompt/SKILL.md) | Write or improve a compact, ready-to-use prompt |
| [`nomore-harness`](retired/skills/nomore-harness/SKILL.md) | Review proposed additions to a Pi environment before adoption |

## Contributing

This is an opinionated personal collection, but issues and suggestions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
