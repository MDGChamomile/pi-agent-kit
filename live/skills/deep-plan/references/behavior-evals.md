# Deep Plan Behavior Scenarios

Use these lightweight scenarios when changing `SKILL.md` or its execution-record contract. Exercise them through Pi; the expected invariants matter more than exact wording. Run artifact-writing scenarios in a disposable explicit destination and inspect the resulting tree, content, and links. Do not reuse a destination between scenarios unless testing a collision.

## Workflow scenarios

| Scenario | Expected invariants | Failure example |
| --- | --- | --- |
| Request is already execution-ready | Resolves evidence without inventing Fog, confirms Same Page, creates one record directory, and does not implement | Adds preference questions that cannot change the plan |
| A critical gate is reached without `ask_user` | Reports the missing dependency and unresolved gate, writes no record unless Same Page was already explicitly confirmed, and stops | Writes `Alignment: Confirmed` for an unresolved plan |
| Independent low-risk questions are ready | Presents them together in one numbered normal response | Serializes every low-risk question through `ask_user` |
| The user corrects one confirmed decision | Reopens only branches whose basis changed | Reopens unrelated settled branches |
| Work expands beyond one-session readiness | Records a split or handoff gate instead of silently absorbing the expansion | Produces one nominally ready record for an unbounded scope |

## Artifact scenarios

| Scenario | Expected invariants | Failure example |
| --- | --- | --- |
| One coherent execution thread | Creates `YYYYMMDD-subject/PLAN.md` only; PLAN contains complete steps and proofs | Creates ceremonial specs or tickets because several files are touched |
| Several cohesive work packages | Creates a PLAN plus a judgment-based number of specs; PLAN links each spec and owns global scope, order, and completion | Uses a fixed spec count or one spec per feature/directory |
| A small spec needs no further split | Keeps its work in `SPEC.md` and creates no `tickets/` artifacts | Creates a ticket that only restates the spec |
| A spec has independently actionable tasks | Creates only useful tickets with parent/PLAN links, prerequisites, actions, proofs, and stop conditions | Splits every implementation bullet into a ticket |
| Work crosses spec boundaries | Gives the work one owning spec, records dependency/consumer edges in PLAN, and links rather than duplicates | Copies the same task or decision into multiple specs |
| Child detail conflicts with PLAN | Treats PLAN as authoritative and fails integrity review until the child is corrected before writing | Lets a ticket silently widen scope or weaken a gate |
| The preferred record directory already exists | Preserves every existing artifact and reports the collision without implementation | Overwrites, merges into, repairs, or renames the existing record |
| A write or integrity check fails before PLAN publication | Reports all possibly created paths and an incomplete record; `PLAN.pending.md` may remain, but PLAN is absent | Publishes PLAN before validation, claims success, deletes partial output, or fills it by overwriting |
| Atomic PLAN publication fails | Reports the incomplete directory and leaves pending artifacts untouched; PLAN remains absent | Treats the pending file as complete, retries by overwriting, or publishes under another name |
| No destination is supplied | Uses the external Pi agent state directory, canonical-path-derived project key, and dated subject directory | Writes generated records into the skill checkout or project tree |
| Historical flat records exist | Leaves them valid and untouched; creates new records in directory form | Migrates or rewrites old Markdown records automatically |

For every completed artifact scenario, also verify:

- `PLAN.md` records `Alignment: Confirmed`, readiness, and `Execution: Unauthorized`;
- no implementation follows record creation;
- the date came from `date +%Y%m%d`;
- all IDs are unique in scope, relative links resolve under final names, dependency targets exist, and unexplained cycles are absent before PLAN publication;
- every PLAN completion condition maps to direct proof or linked spec acceptance evidence before the pending PLAN is atomically published;
- shared decisions are not needlessly duplicated and no child contradicts PLAN;
- an explicit destination still overrides the external-state default.
