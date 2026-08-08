# Extension Candidate Inspection

Extensions execute with the user's permissions. Inspect the implementation, not only its README or package description, and apply every relevant check below.

## Mechanism and registration

- Confirm that runtime behavior, a custom tool, event interception, persistent state, provider integration, or UI actually requires an Extension rather than a Skill or existing CLI.
- Enumerate registered tools, commands, shortcuts, flags, hooks, providers, message or entry renderers, and overridden built-ins.
- Compare declared behavior with source-observed behavior and identify undeclared automation.

## Authority and data flow

- Trace shell, filesystem, network, credential, environment, and external-system access.
- Inspect tool-call blocking or mutation, tool-result mutation, prompt or context injection, provider-request rewriting, and trust or authorization decisions.
- Identify persistent configuration, session entries, hidden state, logs, and any data sent outside the authorized environment.
- Check output truncation, context pollution, error disclosure, and whether automation reduces user visibility or control.

## Lifecycle and reliability

- Check behavior across installation, startup, session replacement, reload, shutdown, cancellation, partial failure, and recovery where applicable.
- Inspect concurrency and data-integrity handling for shared state or file mutation.
- Review dependencies, install scripts, compatibility assumptions, and supply-chain exposure from source and package metadata.
- Confirm a bounded disable, rollback, and removal path, including cleanup of persistent state.
