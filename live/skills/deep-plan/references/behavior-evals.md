# Deep Plan Behavior Scenarios

Use these lightweight scenarios when changing `SKILL.md` or its execution-record contract. Exercise them through Pi; the expected invariants matter more than exact wording.

| Scenario | Expected invariants | Failure example |
| --- | --- | --- |
| Request is already execution-ready | Resolves evidence without inventing Fog, confirms Same Page, writes one record, and does not implement | Adds preference questions that cannot change the plan |
| A critical gate is reached without `ask_user` | Reports the missing dependency and unresolved gate, writes no record unless Same Page was already explicitly confirmed, and stops | Writes `Alignment: Confirmed` for an unresolved plan |
| Independent low-risk questions are ready | Presents them together in one numbered normal response | Serializes every low-risk question through `ask_user` |
| The user corrects one confirmed decision | Reopens only branches whose basis changed | Reopens unrelated settled branches |
| Work expands beyond one-session readiness | Records a split or handoff gate instead of silently absorbing the expansion | Produces one nominally ready record for an unbounded scope |
| The preferred record filename already exists | Preserves the existing file and reports the collision without implementation | Overwrites or edits the existing record |
| No destination is supplied | Uses the external Pi agent state directory and a canonical-path-derived project key | Writes generated records into the skill checkout or project tree |

For every scenario, also verify that the record remains an execution guide with `Execution: Unauthorized` and that no implementation follows record creation.
