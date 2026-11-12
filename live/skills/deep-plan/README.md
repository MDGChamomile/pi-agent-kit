# Deep Plan

An explicitly invoked [Pi](https://github.com/earendil-works/pi) skill for turning a vague repository change into an executable plan: **Fog → Same Page → Execution Record**. The agent inspects available evidence, asks about decisions that remain unresolved, and writes a plan only after alignment. Planning does not authorize implementation.

## In action

A real Pi run on **Parcel Dashboard**, a synthetic shipping dashboard: clarify CSV export scope, resolve the missing UI boundary, confirm the shared understanding, then create `PLAN.md` without implementing the feature.

![Deep-plan asking about CSV export scope, confirming the plan-only boundary, and creating an execution record](https://raw.githubusercontent.com/MDGChamomile/pi-agent-kit/4d061492b34caa5ead7fc7b32d144b0b1052e9f5/docs/assets/deep-plan-demo.gif)

The GIF replays actual terminal output with typing and waits accelerated; model responses and tool results are not scripted. The fixture is not a Git repository, so its Git-status check fails visibly; the agent records that limitation and completes the plan. This is a workflow demonstration, not a measure of planning quality or latency.

## Requirements and installation

- Pi with skill commands enabled.
- A compatible `ask_user` tool for decision gates. [pi-ask-user](https://github.com/edlsh/pi-ask-user) is the reference implementation; copying this skill does not install it.
- A writable records destination; the skill installation itself may be read-only.

The demo GIF is hosted in the repository's `docs/assets/`, outside this installable directory. The README uses an online image URL so it also works when copied on its own; viewing the demo requires network access.

From the repository root, copy the directory into Pi's skill location:

```bash
mkdir -p ~/.pi/agent/skills
cp -R live/skills/deep-plan ~/.pi/agent/skills/
```

Restart Pi or use `/reload`, then invoke it explicitly from the target project:

```text
/skill:deep-plan Help me define a CSV export change before implementation.
```

Read [`SKILL.md`](SKILL.md) for the workflow and critical-gate behavior. The skill is not automatically selected by the model.

## Output and boundaries

Inspection and alignment are read-only. Low-impact details the agent leaves to execution time are listed at the final confirmation with their defaults, so you can settle any of them first. Once alignment is confirmed, the skill creates a new record directory containing one `PLAN.md`. The default destination is `~/.local/state/pi/deep-plan/records/<project>/`, where `<project>` is the repository directory name; name a destination in your request to use that directory directly for one run. Existing records are never overwritten or migrated; records stored elsewhere remain where they are.

The completed record separates confirmed alignment, readiness, and execution authorization. Missing evidence can leave execution blocked; implementation always requires a separate explicit request. See the [execution-record contract](references/execution-record.md) for details and [behavior evaluations](references/behavior-evals.md) for maintenance checks.

## Maintenance

For changes to this skill, use the impact-based [behavior scenarios](references/behavior-evals.md) and the repository contribution guide. The skill has no offline tests; its behavior is established only by live model runs.

## License

[MIT](LICENSE). Keep the bundled license notice when copying or redistributing this skill.
