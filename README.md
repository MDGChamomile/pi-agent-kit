# Pi Agent Kit

[![validation](https://github.com/MDGChamomile/pi-agent-kit/actions/workflows/live-validation.yml/badge.svg?branch=main)](https://github.com/MDGChamomile/pi-agent-kit/actions/workflows/live-validation.yml)
[![Latest release](https://img.shields.io/github/v/release/MDGChamomile/pi-agent-kit)](https://github.com/MDGChamomile/pi-agent-kit/releases/latest)
[![License](https://img.shields.io/github/license/MDGChamomile/pi-agent-kit)](LICENSE)

> Inspectable, copy-friendly skills and extensions for the [Pi coding agent](https://github.com/earendil-works/pi).

Pi Agent Kit is the public, source-first collection of resources I currently use or have tested in my own workflow. It is for people who prefer to adopt one small, understandable component at a time instead of installing a complete agent framework.

- **Skills** provide focused workflows that Pi loads on demand.
- **Extensions** add tools or enforce runtime boundaries.
- **Live** resources are currently used and maintained.
- **Retired** resources are kept in the repository history as references.

The collection follows the [harness-minimalism principles](https://github.com/MDGChamomile/MDGChamomile/blob/main/PRINCIPLE.md) maintained in the MDGChamomile repository. The local [PRINCIPLE.md](PRINCIPLE.md) points to that single source of truth. Read the source, take what is useful, and adapt it to your own workflow; this is not an install-everything Pi package.

## Start here

| If you want to… | Start with | Adopt it by… |
| --- | --- | --- |
| Use a dedicated model for native compaction | [`pi-compaction-model`](live/extensions/pi-compaction-model/README.md) | Copying the standalone extension from source |
| Turn a vague repository change into an executable plan | [`deep-plan`](live/skills/deep-plan/README.md) | Copying the skill from source and providing a compatible `ask_user` tool |
| Analyze patterns across local Pi sessions | [`session-search`](live/skills/session-search/README.md) | Copying the standalone skill from source |

### Copy an individual resource

Clone the repository, review the resource and its requirements, and copy or link only the directory you want into the applicable Pi location. Keep the bundled `LICENSE` and any `NOTICE.md` with the resource when copying or redistributing it.

For `deep-plan`, a compatible `ask_user` tool is required at decision gates; copying the skill does not install that tool. If you do not already have a compatible extension, the reference implementation can be installed with `pi install npm:pi-ask-user`. See the skill's [requirements](live/skills/deep-plan/SKILL.md#requirement) before adopting it.

Copy the skill:

```bash
git clone https://github.com/MDGChamomile/pi-agent-kit.git
mkdir -p ~/.pi/agent/skills
cp -R pi-agent-kit/live/skills/deep-plan ~/.pi/agent/skills/
```

Restart Pi, or use `/reload` for an auto-discovered resource. With skill commands enabled, invoke `deep-plan` explicitly:

```text
/skill:deep-plan
```

This skill sets `disable-model-invocation: true`, so Pi does not advertise it to the model for automatic selection.

> [!CAUTION]
> Skills can instruct the model to take actions, and extensions run with the user's system permissions. Review each resource before adopting it.

## Retired

Resources no longer actively used or maintained. They are not kept in the current tree; the links point to their last version in the repository history:

| Resource | Purpose |
| --- | --- |
| [`whitebox`](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/retired/extensions/whitebox/README.md) | Run project commands and Pi file tools inside an offline Linux Bubblewrap boundary |
| [`git-history`](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/retired/extensions/git-history/index.ts) | Add `/snapshot` to review and commit changes in the Pi agent directory |
| [`meta-prompt`](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/retired/skills/meta-prompt/SKILL.md) | Write or improve a compact, ready-to-use prompt |
| [`nomore-harness`](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/retired/skills/nomore-harness/SKILL.md) | Review proposed additions to a Pi environment before adoption |
| [`security-audit`](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/retired/skills/security-audit/README.md) | Review source defensively with explicit scope and evidence |
| [`simplykst`](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/retired/skills/simplykst/README.md) | Analyze Korean stocks with separate Trading and Investing ratings |

## Contributing

This is an opinionated personal collection, but issues and suggestions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
