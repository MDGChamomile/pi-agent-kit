# Security Audit

A manually invoked, defensive source-review skill. It is not an autonomous penetration-testing system and does not generate exploits or probe deployed services.

## Invoke

Review and copy this directory into your chosen Pi skills location, then reload Pi. Adoption is a user action; this repository does not install or activate it.

```text
/skill:security-audit guidance <question or target>
/skill:security-audit full <target and scope>
```

`disable-model-invocation: true` hides it from automatic model selection. Guidance creates no artifacts. Full adds boundary mapping, a coverage ledger, findings, and parent verification; it writes files only when file output and the destination are authorized.

## Requirements and limits

Both modes can run parent-only with source-reading tools. Full mode may use a compatible [pi-subagent skill and extension](../pi-subagent/README.md) when focused delegation is useful and permitted. Follow the installed skill's result-format contract rather than assuming one package version. When delegating, use one child by default, at most three total per parent run, and keep local and web investigations separate. Partial results remain visible as gaps. Without delegation, retain the requested mode and report actual coverage limitations. No tool is installed automatically.

Target-controlled execution requires independently verified OS isolation described in `SKILL.md`; otherwise use source inspection and disclose the execution-validation gap. The skill and child tool do not supply a sandbox. No npm dependencies, schema validators, or executable helpers are bundled. Initial artifacts are Markdown; structural consistency is manually checked separately from factual source verification.

## Maintenance

Use Pi's `loadSkillsFromDir` and `formatSkillsForPrompt` to check discovery, diagnostics, and exclusion from automatic prompting. Review these scenarios without launching an audit: guidance creates no files; parent-only full retains its boundary map and coverage ledger; partial children retain gaps under the installed result contract; denied or unclear provider permission prevents delegation; private evidence does not enter web tasks; incomplete host isolation prevents target execution; unconfirmed findings have no severity; full without an output request creates no files. Loader checks verify metadata, not model compliance with instructions.

See [full review](references/full-audit.md), [evidence contract](references/evidence-and-reporting.md), [upstream notice](NOTICE.md), and [repository principles](../../../PRINCIPLE.md).
