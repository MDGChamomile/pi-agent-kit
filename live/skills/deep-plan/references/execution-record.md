# Deep Plan Execution Record

Read this reference only after the grilling loop reaches Same Page. Create one execution-record directory whose `PLAN.md` is the final source of truth; do not reproduce the full interview.

## Destination and record directory

Resolve the date with `date +%Y%m%d`; never invent it. Name the record directory:

```text
YYYYMMDD-<subject>/
```

Use a concise kebab-case `<subject>` derived from the work, or the user's supplied subject. Choose the parent records directory in this order:

1. the directory explicitly named by the user for this run, used directly;
2. otherwise `~/.local/state/pi/deep-plan/records/<project>/`, where `<project>` is the name of the repository root directory (or of the current working directory outside a repository).

Create the parent records directory when needed, only after Same Page confirmation. Do not infer another project-local plan directory or ask a destination question while this default is available. The installed skill is read, never used as the output location. If the selected records directory cannot be created or written, report the blocker rather than silently choosing another destination. Existing records, wherever they are stored and whatever their shape, remain valid historical artifacts; do not migrate or rewrite them.

Never overwrite, merge into, or repair an existing record. Create the record directory without `-p` so that an existing directory fails. If the target already exists or a required parent is not a directory, stop and report it.

## PLAN.md required content

A record contains one `PLAN.md`. Keep the plan proportional to the change and its failure cost. Preserve only execution-changing decisions and evidence; do not narrate the interview, restate repository documentation, or add detail merely to fill a section. Required sections may be brief.

### Status and Plan Basis

Record separately:

- `Alignment: Confirmed`;
- `Readiness: Ready` or `Blocked` with the blocking Fog;
- `Execution: Unauthorized`;
- repository root, branch and HEAD when available, working-tree state, inspected-at timestamp, applicable instruction files, material evidence, and known gaps.

### Shared Understanding

Preserve the confirmed Same Page readback. Add only:

- the basis for confirmed decisions;
- accepted assumptions with invalidation conditions;
- deferred choices, each with the default the user saw at Same Page;
- unresolved branches and explicit prototype, investigation, external-decision, or verification gates.

Keep change-specific understanding in this record. Treat existing glossaries, `CONTEXT.md` files, and ADRs as evidence; list durable terminology or decisions as promotion candidates rather than modifying those files in this workflow.

### Execution Strategy

Order the smallest coherent execution steps. Each step must state:

- **Outcome** — the completed result of the step;
- **Touch** — likely files, components, or systems involved;
- **Action** — the change to make;
- **Proof** — the check that demonstrates completion;
- **Stop if** — drift, missing evidence, failed prerequisites, or approval boundaries that require reassessment.

Group steps under headings when the change has several work packages; keep them in the same file.

### Final Verification

Specify the checks that establish the whole outcome, including relevant tests, static checks, integration readback, and checks that may remain unavailable. Add rollback or compensation only when material. Every completion condition must map to at least one proof.

### Gates and Drift

Require the executor to re-read current instructions and compare live state with the Plan Basis. Material or semantic drift is a stop condition. Identify external, destructive, publishing, deployment, migration, credential, or permission-changing actions that require separate approval.

Keep the record executor-neutral. Add executor-specific deltas (tools, sandbox, permissions, verification, or report-back requirements) only when they materially change the contract; do not ask the user to choose an executor merely to fill a field.

## Writing

Before writing, check that the plan maps every completion condition to proof and lists every deferred choice. Then create the record directory and write `PLAN.md` once. If a write fails, stop, report every path that may have been created and that the record is incomplete, and leave it untouched for explicit user-directed recovery. Do not retry by overwriting, deleting, or writing under a different record name.

## Completion condition

The completed record has a `PLAN.md` that preserves every confirmed decision, accepted assumption, deferred choice, unresolved blocking branch, completion condition, proof, gate, and stop condition. The record excludes secrets, credentials, private records, and sensitive repository content.
