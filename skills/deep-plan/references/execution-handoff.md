# Executor-Specific Deltas

Read this reference only when executor choice materially changes the execution contract. The Execution Record remains the sole plan format, and neither the record nor a handoff authorizes implementation.

Add only relevant differences in:

- available tools, sandbox, context, and runtime constraints;
- executor-specific permissions or external-effect approval gates;
- terminology or artifact mappings required by another interface;
- preflight, verification, rollback, and report-back requirements.

Keep the record executor-neutral when no material difference exists. Do not ask the user to choose an executor merely to fill a field.
