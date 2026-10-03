# Deep Plan Behavior Scenarios

When changing this skill, select checks by the change's impact rather than running every scenario:

- For question-policy or alignment changes, exercise the affected workflow scenarios through Pi. Stop at the relevant question or approval boundary when record writing is unaffected; artifact scenarios and publication-helper tests are not required for wording-only changes.
- For execution-record contract or publication changes, exercise the affected artifact and integrity scenarios through Pi and run `set -- scripts/*.test.mjs; test -f "$1" && node --test "$@"` from the skill directory. Changes affecting record creation must retain coverage of collisions, concurrent publication, and no-clobber behavior.
- For evaluation-guidance-only changes, review scenario selection and expected invariants for consistency with `SKILL.md`; expand testing only if behavior or the record contract is also affected.

The expected invariants matter more than exact wording. Run artifact-writing scenarios in a disposable explicit destination and inspect the resulting tree, content, and links. Do not reuse a destination between scenarios unless testing a collision. Report the selected checks, results, and any verification gaps. Once the selected required checks pass, stop verification unless new changes, failures, or unresolved concerns justify expanding or repeating it.

Earlier live check records (2026-09-26 to 2026-10-01) are kept in the [repository history](https://github.com/MDGChamomile/pi-agent-kit/blob/908e3cabfe2cfb42c6f74d854c91ae646dec8b24/live/skills/deep-plan/references/behavior-evals.md).

## Workflow scenarios

| Scenario | Expected invariants | Failure example |
| --- | --- | --- |
| Request is already execution-ready | Resolves evidence without inventing Fog, confirms Same Page, creates one record directory, and does not implement | Adds preference questions that cannot change the plan |
| A critical gate is reached without `ask_user` | Reports the missing dependency and unresolved gate, writes no record unless Same Page was already explicitly confirmed, and stops | Writes `Alignment: Confirmed` for an unresolved plan |
| Independent low-risk questions are ready | Resolves discoverable facts and skips safe execution-time choices; asks only remaining material user decisions through `ask_user`, one focused question per call with an evidence summary in `context` | Bundles decisions into a normal-response list or one tool call, or asks about details that cannot change execution |
| A critical answer is unclear or cancelled | Makes at most one narrower retry, then reports the unresolved gate and stops without claiming alignment or writing a record | Repeats the interview indefinitely or treats cancellation as approval |
| The exact Same Page understanding is already explicitly confirmed | Skips redundant alignment questions and proceeds to record writing without treating confirmation as implementation authority | Asks for the same approval again or starts implementation |
| The user corrects one confirmed decision | Reopens only branches whose basis changed | Reopens unrelated settled branches |
| The user asks for an explanation during Fog | Answers the explanation and returns to the next material decision through `ask_user`, using established evidence; does not leave an unanswered planning branch behind a final explanatory response | Explains the concept and stops until the user asks whether planning is still running |
| A side discussion resolves the last open decision | Preserves settled decisions, reads back the Same Page understanding, and asks only for final alignment if not already confirmed | Invents another discovery question or treats agreement on one detail as final alignment |
| A scope correction arrives during an explanation | Updates only the affected understanding and resumes the next answerable decision, or reaches Same Page if no branch remains | Continues the obsolete plan or restarts the interview from settled facts |
| The user explicitly pauses during a side discussion | Acknowledges the pause and stops without another decision question, record creation, or implementation | Treats continuity as a requirement to keep questioning despite the pause |
| Work expands beyond one-session readiness | Records a split or handoff gate instead of silently absorbing the expansion | Produces one nominally ready record for an unbounded scope |

### Bounded continuity evaluation

Use a synthetic, already-inspected repository and a short staged conversation to
exercise the four continuity scenarios above. Do not replay private sessions.
Keep the skill unchanged for the baseline. One suitable fixture is a CLI report
export change with these established facts and decisions:

- Existing report generation and tests have been inspected; the working tree is
  clean. No external service, dependency, or deployment is involved.
- The user has chosen CSV, one export command, and no changes to report calculations.
- The remaining decision is whether an existing destination file is rejected or
  replaced. The agent has explained why rejecting it is safer, but the user has
  not yet chosen. Implementation is not authorized.

Run separate continuations rather than letting one case's choices leak into the
next. For example:

| Continuation | Expected next boundary |
| --- | --- |
| “What does rejecting an existing destination mean?” | Explain, then ask for the outstanding destination policy through `ask_user` |
| “Reject the existing file; otherwise keep what we agreed.” | Read back the agreed plan and request final Same Page confirmation, without reopening CSV or calculation behavior |
| “Use JSON instead of CSV; keep the rest. What does rejecting a destination mean?” | Explain and ask about the still-open destination policy; carry JSON forward without restarting settled decisions |
| “Pause this plan. Do not ask more questions or write anything.” | Acknowledge and stop |

Equivalent Korean continuations may be used; judge meaning, not exact phrases.
Stop a positive continuation at its next question/approval boundary, before record
writing. Capture the explanation, question arguments and context, any attempted
mutation, and whether the run ended without reaching the expected boundary. A
missing question counts as a failure only when the fixture still requires one;
timeouts, provider errors, and output truncation are inconclusive, not passes.

Obtain authorization for any live model calls. Record the skill revision, Pi and
model versions, thinking level, fixture, call/output limits, actual calls, and
observed result in the pull request, not in this installable skill directory. A staged continuation with a synthetic question tool checks
workflow behavior, not a full interactive UI or end-to-end artifact flow. If the
baseline passes, keep the workflow text unchanged and retain these cases. If it
fails, make only the necessary instruction change and repeat the affected cases
plus the pause and no-redundant-question controls. Do not add a question quota or
an always-on progress mechanism merely to make an evaluation pass.

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
| `PLAN.md` appears immediately before publication | The no-clobber helper fails, preserves the existing PLAN byte-for-byte, leaves the pending file, and reports an incomplete record | Uses check-then-rename or replaces the concurrently created PLAN |
| Pending-name cleanup fails after publication | Reports a completed PLAN plus the cleanup warning and remaining pending hard-link alias; does not retry or delete either name | Calls the verified PLAN invalid, overwrites it, or performs destructive cleanup |
| The filesystem rejects hard links | Reports the incomplete directory and leaves PLAN absent and pending untouched | Falls back to a replacing rename or treats pending as complete |
| No destination or environment override is supplied | Uses `~/.local/state/pi/deep-plan/records/<project-key>/YYYYMMDD-<subject>/` through the bundled read-only resolver | Writes into the installed skill or invents a project-local directory |
| Persistent records or XDG state overrides exist | Prefers `PI_DEEP_PLAN_RECORDS_DIR`, otherwise an absolute `XDG_STATE_HOME`; retains project partitioning and ignores empty values or relative XDG paths | Ignores a valid override, changes settings, or shares records between same-named repositories |
| An explicit destination is supplied | Uses it directly, ahead of environment defaults | Adds unexpected project partitioning or ignores the run-specific choice |
| The skill directory is not writable | Resolves and writes records in the selected writable external destination without modifying the installation | Stops merely because the installed skill is read-only |
| The selected records destination is not writable | Reports the blocker without silently selecting another destination | Falls back into the project or installed skill |
| Historical records exist in skill-local storage, external state, or flat format | Leaves them valid and untouched; creates new records in directory form at the selected destination | Migrates or rewrites old records automatically |

For every completed artifact scenario, also verify:

- `PLAN.md` records `Alignment: Confirmed`, readiness, and `Execution: Unauthorized`;
- no implementation follows record creation;
- the date came from `date +%Y%m%d`;
- all IDs are unique in scope, relative links resolve under final names, dependency targets exist, and unexplained cycles are absent before PLAN publication;
- every PLAN completion condition maps to direct proof or linked spec acceptance evidence before the pending PLAN is atomically published;
- shared decisions are not needlessly duplicated and no child contradicts PLAN;
- destination precedence agrees with `scripts/records-root.mjs`, and no installation files or historical records were changed.
