# Deep Plan Execution Record

Read this reference only after the grilling loop reaches Same Page. Write one source of truth; do not reproduce the full interview.

## Destination and filename

Resolve the date with `date +%Y%m%d`; never invent it. Name the record:

```text
YYYYMMDD-<subject>.md
```

Use a concise kebab-case `<subject>` derived from the work, or the user's supplied subject. Choose the destination directory in this order:

1. the directory explicitly named by the user;
2. an existing repository convention for plans or decision artifacts;
3. otherwise ask one focused destination question.

Never overwrite an existing record. If the target exists or conflicts with a non-directory, stop and report it.

## Required content

Use these sections, combining subsections when that improves clarity.

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
- unresolved branches and explicit prototype, investigation, external-decision, or verification gates.

Keep change-specific understanding in this record. Treat existing glossaries, `CONTEXT.md` files, and ADRs as evidence; list durable terminology or decisions as promotion candidates rather than modifying those files in this workflow.

### Execution Steps

Order the smallest coherent steps. Each step must state:

- **Outcome** — the completed result of the step;
- **Touch** — likely files, components, or systems involved;
- **Action** — the change to make;
- **Proof** — the check that demonstrates completion;
- **Stop if** — drift, missing evidence, failed prerequisites, or approval boundaries that require reassessment.

Map every completion condition to at least one step and proof without creating a separate mapping table unless complexity makes one necessary.

### Final Verification

Specify the checks that establish the whole outcome, including relevant tests, static checks, readback, and checks that may remain unavailable. Add rollback or compensation only when material.

### Gates and Drift

Require the executor to re-read current instructions and compare live state with the Plan Basis. Material or semantic drift is a stop condition. Identify external, destructive, publishing, deployment, migration, credential, or permission-changing actions that require separate approval.

Keep the record executor-neutral. If the executor's tools, sandbox, permissions, context, verification, or report-back requirements materially change the contract, read `execution-handoff.md` and add only those deltas.

## Completion condition

The completed record preserves every confirmed decision, accepted assumption, unresolved blocking branch, completion condition, step proof, gate, and stop condition. It excludes secrets, credentials, private records, and sensitive repository content.
