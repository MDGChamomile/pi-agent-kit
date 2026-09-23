# Full defensive source review

Full describes requested breadth, not a guarantee of exhaustive coverage. Keep the process proportional to the target; do not impose fixed waves, profiles, or minimum child counts.

## Establish scope

Identify the authorized target, relevant revision and dirty state, exclusions, and requested output. Use repository-relative identifiers in retained output, not host paths or remote URLs containing credentials. Prior results are context: check relevant current source and conditions before carrying any conclusion forward.

A full review alone does not authorize file creation. If the user requested files and specified their location, write there without overwriting existing work. Otherwise provide results in the conversation; ask only if a file location is necessary. Only the parent writes authorized artifacts; children return text and evidence locations, not files.

## Map and investigate

Briefly map principals, resources, inputs, trust boundaries, and intended controls. Make a small coverage ledger from actual boundaries, not a universal attack checklist. Each unit has `id`, `boundary`, `paths`, `question`, `status`, `evidenceRefs`, `findingIds`, and `limitations`.

Use statuses `not_started`, `reviewed`, `partial`, and `excluded`. Reviewed means the recorded question was examined, not that the resource is vulnerability-free. Preserve excluded and unfinished units visibly.

Delegate focused source-control investigations only when context isolation is useful and the installed pi-subagent contract allows them. The parent performs simple lookups and final validation. Respect the total three-call limit; narrow scope or disclose gaps rather than adding extra waves. Do not delegate exploit development or attack execution.

## Reconcile and report

Merge duplicate root causes and examine existing defenses and counterevidence. Parent-check the decisive current file/symbol references and assumptions; use the finding contract in [evidence-and-reporting.md](evidence-and-reporting.md). No execution or fresh child is mandatory to establish a clear source-level fact; uncertainty remains explicit.

Report scope/revision, principal and boundary map, coverage ledger, findings, defensive recommendations, and limitations. Distinguish completed source inspection from unperformed execution validation. Finish with either a bounded completed review or `incomplete` plus the exact unfinished units and reasons. Never imply total coverage.

For explicitly requested files, a report plus separate ledger/findings documents is sufficient. Markdown is the initial format. No JSON schema or validator is supplied or required; do not claim machine validation. Before delivery, manually check unique IDs, finding references, allowed statuses, evidence locations, and consistency between findings and summary. Optional structured output must preserve the same semantics without claiming a formal schema contract.
