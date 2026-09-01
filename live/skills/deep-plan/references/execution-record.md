# Deep Plan Execution Record

Read this reference only after the grilling loop reaches Same Page. Create one execution-record directory whose `PLAN.md` is the final source of truth; do not reproduce the full interview.

## Destination and record directory

Resolve the date with `date +%Y%m%d`; never invent it. Name the record directory:

```text
YYYYMMDD-<subject>/
```

Use a concise kebab-case `<subject>` derived from the work, or the user's supplied subject. Choose the parent records directory in this order:

1. the directory explicitly named by the user for this run;
2. otherwise `<agent-dir>/records/deep-plan/<project-key>/`, where `<agent-dir>` is the non-empty `PI_CODING_AGENT_DIR` value when set and the expanded `~/.pi/agent` path otherwise.

Build `<project-key>` from the canonical repository root, or the canonical current working directory when no repository root is available:

```text
<sanitized-basename>-<first-6-lowercase-hex-of-SHA-256(canonical-path)>
```

Keep ASCII letters, digits, dots, underscores, and hyphens in the basename; replace other runs with `-`, trim separators, and use `project` if nothing remains. The path hash prevents same-named repositories in different locations from sharing records. `PI_CODING_AGENT_DIR` is Pi's supported agent-directory override; do not use a similarly named unofficial variable.

Create the parent records directory when needed. Do not infer a repository-local plan directory or ask a destination question while this default is available. Existing flat `YYYYMMDD-<subject>.md` records remain valid historical artifacts; do not migrate them automatically.

Never overwrite, merge into, or repair an existing record directory or artifact. Before writing, determine and validate the complete path set in memory. If the target record path already exists, any required parent is a non-directory, or two planned artifacts collide, stop and report it.

## Adaptive shape

Every record contains `PLAN.md`. Use the smallest shape that remains clear and executable:

```text
YYYYMMDD-subject/
└── PLAN.md
```

Keep a PLAN-only record when the change has one coherent execution thread and its steps, proofs, and stop conditions remain easy to navigate in one file. Do not create hierarchy merely because several files or features are touched.

Add specs when the change has multiple cohesive work packages with materially distinct boundaries, interfaces, completion evidence, dependencies, risk, or execution order, or when keeping their details in `PLAN.md` would obscure the whole-plan contract. A spec is an execution-coherent slice, not necessarily one feature. Choose the number from the work's natural cohesion; never target a fixed count or mechanically create one spec per feature, component, or directory.

Within a spec, add tickets only when its implementation contains independently actionable units that benefit from separate prerequisites, touch points, proofs, stop conditions, or sequencing. A small spec may have no tickets. Do not create wrapper tickets that merely repeat `SPEC.md`.

The hierarchical shape is:

```text
YYYYMMDD-subject/
├── PLAN.md
└── specs/
    └── SPEC-001-short-name/
        ├── SPEC.md
        └── tickets/
            └── TICKET-001-short-name.md
```

Use zero-padded, sequential IDs in planned execution order. Spec IDs are unique within the record; ticket IDs are unique within their parent spec. Keep IDs and paths stable after writing. Use relative Markdown links for every child artifact.

## Authority and information boundaries

`PLAN.md` owns the whole-change scope, shared decisions and assumptions, global completion conditions, cross-spec dependencies and order, approval gates, and final verification. It is authoritative if any child artifact conflicts with it.

`SPEC.md` owns the detailed contract and acceptance evidence for one cohesive slice. A ticket owns the concrete implementation task needed to satisfy its parent spec. Child artifacts may elaborate but must not redefine PLAN decisions, widen scope, or weaken gates. Prefer links over duplicated prose:

- put a shared fact or decision in `PLAN.md` once and reference it from specs;
- put slice-specific interfaces and acceptance criteria in `SPEC.md` once and reference them from tickets;
- put task-level touch/action/proof detail in a ticket only when tickets are useful.

Assign each cross-spec task to one owning spec. Record its consumers and dependency edges in `PLAN.md` and link to the owner instead of duplicating the task. A child completion rolls up through its parent spec to an explicit PLAN completion condition.

## PLAN.md required content

Keep the plan proportional to the change and its failure cost. Preserve only execution-changing decisions and evidence; do not narrate the interview, restate repository documentation, or add detail merely to fill a section. Required sections may be brief.

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

### Record Map and Execution Strategy

For a PLAN-only record, order the smallest coherent execution steps. Each step must state:

- **Outcome** — the completed result of the step;
- **Touch** — likely files, components, or systems involved;
- **Action** — the change to make;
- **Proof** — the check that demonstrates completion;
- **Stop if** — drift, missing evidence, failed prerequisites, or approval boundaries that require reassessment.

For a hierarchical record, list and link every spec, summarize its outcome, identify dependencies and execution order, and map whole-plan completion conditions to spec acceptance evidence. Keep detailed implementation steps in specs or tickets instead of repeating them in `PLAN.md`. Include ticket links in the PLAN map only when needed to explain a cross-spec edge or whole-plan gate.

### Final Verification

Specify the checks that establish the whole outcome, including relevant tests, static checks, integration readback, and checks that may remain unavailable. Add rollback or compensation only when material. Every completion condition must map to at least one proof, directly for PLAN-only records or through linked spec acceptance evidence.

### Gates and Drift

Require the executor to re-read current instructions and compare live state with the Plan Basis. Material or semantic drift is a stop condition. Identify external, destructive, publishing, deployment, migration, credential, or permission-changing actions that require separate approval.

Keep the record executor-neutral. If the executor's tools, sandbox, permissions, context, verification, or report-back requirements materially change the contract, read `execution-handoff.md` and add only those deltas.

## SPEC.md required content

Each spec must contain:

- **Identity and links** — spec ID, descriptive title, relative link to `PLAN.md`, and links to its tickets, if any;
- **Outcome and boundaries** — the slice's observable result, in-scope work, non-goals, and the PLAN completion conditions it serves;
- **Dependencies and interfaces** — predecessor specs or external gates, consumers, contracts, and cross-spec edges without duplicating their owner's work;
- **Implementation contract** — slice-specific decisions, likely touch points, required behavior, and ordered work; when tickets exist, summarize and order them rather than repeating their actions;
- **Acceptance and proof** — checks that establish the spec outcome and how they roll up to PLAN verification;
- **Stop conditions** — drift, failed prerequisites, interface conflicts, or approval boundaries that require reassessment.

## TICKET-*.md required content

Each ticket must contain:

- **Identity and links** — ticket ID, descriptive title, relative links to its parent `SPEC.md` and authoritative `PLAN.md`;
- **Outcome** — one independently actionable completed result and the parent acceptance criterion it advances;
- **Prerequisites and dependencies** — required tickets, specs, evidence, or gates;
- **Touch and action** — likely files/components and concrete implementation work, without widening the parent boundary;
- **Proof** — focused checks and the evidence to report to the parent spec;
- **Stop conditions** — drift, missing prerequisites, ownership conflicts, failed proof, or approval boundaries.

## Write integrity

Treat successful atomic publication of `PLAN.md` as the record's completion marker. Validate the intended IDs, relative paths, links, dependency graph, and PLAN roll-ups before creating files. The newly created record directory exclusively reserves the selected target; if it cannot be created because the path appeared concurrently, stop without writing into it.

For a hierarchical record, write tickets first and then their `SPEC.md` files. Render the authoritative plan last to `PLAN.pending.md`; for a simple record, write only `PLAN.pending.md`. Before publication, verify the complete intended tree while treating that pending file as the future `PLAN.md`: every intended file exists, every relative link resolves under its final name, every ID is unique in its scope, all dependency targets exist, no dependency cycle is left unexplained, and the plan maps every whole-plan completion condition to proof.

Only after all checks pass, publish with the bundled no-clobber helper, resolving `<skill-dir>` as the directory that contains this skill's `SKILL.md`:

```bash
node <skill-dir>/scripts/publish-plan.mjs <record-dir>/PLAN.pending.md <record-dir>/PLAN.md
```

The helper atomically creates `PLAN.md` as a hard link to the verified pending file. Hard-link creation fails if `PLAN.md` appeared concurrently, so it never replaces an existing destination. Because both names are in the same directory, they are on the same filesystem. If that filesystem does not support hard links, publication fails safely with `PLAN.md` absent. Do not substitute a check-then-rename sequence, plain `rename`, or `mv`, because those forms may replace a destination created after the check.

Successful hard-link creation is the publication point and marks the record complete. The helper then removes `PLAN.pending.md`. If only that cleanup fails, `PLAN.md` still points to the complete pre-verified file; report the helper's cleanup warning and the remaining pending alias, but do not retry, delete, or call the completed PLAN invalid.

If any write, integrity check, or helper publication step fails before `PLAN.md` is created, stop immediately, report every path that may have been created and that the record is incomplete, and leave it untouched for explicit user-directed recovery. `PLAN.pending.md` may remain, but the absence of `PLAN.md` unambiguously means the directory is not a completed execution record. Do not silently retry by overwriting, publishing under a different record name, deleting, or filling a partial record.

## Completion condition

The completed record has an atomically published, pre-verified `PLAN.md` and preserves every confirmed decision, accepted assumption, unresolved blocking branch, completion condition, proof, dependency, gate, and stop condition at the appropriate level. Every child artifact is linked into the PLAN hierarchy and is consistent with its ancestors. The record excludes secrets, credentials, private records, and sensitive repository content.
