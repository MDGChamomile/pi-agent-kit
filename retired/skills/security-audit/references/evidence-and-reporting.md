# Evidence and reporting

Report supported, actionable control weaknesses rather than checklist deviations. Describe the lower-trust principal, resource, expected control, observed source behavior, and consequence. Do not supply exploit payloads, attack chains, or operational reproduction instructions.

Every candidate has an ID, title, status, boundary, repository-relative file/symbol references, and rationale. Deduplicate by root cause and affected control.

- **confirmed**: parent-verified current evidence establishes a real control failure. Include principal/resource, preconditions, impact, severity with reasoning, narrow defensive fix, non-exploit regression assertions, and which evidence the parent checked. Source analysis can suffice; distinguish it from execution evidence.
- **needs_validation**: a specific source-grounded question remains unresolved. Name the missing deployment fact, defense, or source evidence and the safe next owner check. No severity; do not inflate a hypothesis into a confirmed defect.
- **rejected**: include the counterevidence, existing control, scope reason, or duplicate ID. Missing best practices without a demonstrated security consequence belong in advice, not confirmed findings.

Severity applies only to confirmed findings and cannot exceed supported impact. Explain reachability, preconditions, affected principals, and blast radius; avoid ratings based merely on a pattern name. Never assume absent deployment controls are disabled or that undocumented controls exist.

A regression recommendation states the invariant to enforce, such as denying an unauthorized synthetic principal or preserving isolation between dummy resources. It is not an exploit recipe. Recommend the smallest effective source fix at the trusted decision point; do not implement it without authorization.

Before delivery, check all confirmed findings directly in current source, verify ledger references and IDs, ensure unresolved findings have no severity, and reconcile summary counts. Child results, old reports, and static checks alone do not prove complete coverage. State no confirmed material findings when that is the evidence-supported result.
