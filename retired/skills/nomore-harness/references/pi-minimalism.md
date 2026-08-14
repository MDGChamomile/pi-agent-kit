# Pi Minimalism

Use this rubric to decide whether any proposed repository, package, tool, Skill, Extension, or integration has earned a place in the user's Pi environment.

Pi minimalism is a small, predictable core plus explicit user-space extension—not feature deprivation. A candidate should not be rejected merely because Pi keeps it out of core; it should be rejected when the need is unproven or the mechanism is duplicative, hidden, or larger than the outcome requires. Understand the problem fully before simplifying, and seek the smallest **complete** mechanism. Never trade away correctness, security, privacy, data integrity, concurrency protection, accessibility, or explicit requirements for a smaller artifact.

Set the adoption goal, non-discoverable context, hard boundaries, and success criteria. Treat this rubric as decision criteria, not a required investigation sequence. Leave the investigation and implementation path to the model unless the path is itself part of the requirement.

## 1. Earn its existence

- Name the demonstrated need and the result that would prove it has been met.
- Ground the need in at least one of: a recurring observed failure and its root cause; an explicit requirement or non-discoverable domain constraint; or a credible risk whose single-failure cost justifies preventive control.
- Reject speculative future needs: YAGNI applies when none of those grounds is supported by proportionate evidence.
- Compare against adding nothing. Modern models already perform many general coding and reasoning procedures without another harness element.
- Separate additive, non-discoverable intent or domain knowledge from generic advice and facts the model can inspect itself.

**Pass when:** the candidate closes a material gap or enforces a required boundary, the success condition is observable, and the need is supported by observed failure, an explicit requirement, or proportionate risk evidence.

## 2. Use the smallest sufficient mechanism

Apply the **hourglass** test: useful harnesses enrich the input with intent and hard boundaries, leave exploration and execution choices thin, then enforce truth and consequential actions with deterministic checks or explicit authority gates. Procedural steering earns a place only when the path is itself a requirement, it addresses a demonstrated failure, or it protects against a credible high-cost risk. Otherwise state the goal, context, boundaries, and success criteria, then leave the route open to the model.

After understanding the task and environment, stop at the first mechanism that fully preserves the required outcome:

1. existing Pi behavior or no addition;
2. a visible standard artifact or existing mechanism—repository instruction, file, CLI, test, schema, dependency, or installed resource;
3. direct use of the candidate's ordinary interface without a Pi-specific wrapper;
4. a small Skill for on-demand procedure or knowledge;
5. an Extension only for runtime tools, events, UI, state, or integration that static instructions cannot provide.

Prefer boring, composable mechanisms, but retain essential complexity when a simpler option would weaken the contract. Pi deliberately moves optional policy into user space, so a focused, inspectable extension can be more Pi-native than forcing the feature into core.

For a **Skill**:

- Confirm it creates a repeatable behavior beyond the model default rather than restating generic advice.
- Deliberately trade model invocation's persistent context and trigger uncertainty against user invocation's cognitive cost; check false positives and false negatives when material.
- Keep one source of truth, disclose branch-only reference on demand, and apply the deletion test to instructions whose behavioral effect is unknown.

For a **repository or package**, inspect the adoption-relevant resources and install-time actions needed to establish material capability, authority, side effects, and maintenance burden; expand to every included resource when high authority or hidden behavior makes the whole bundle decision-relevant. One useful subdirectory does not justify the whole bundle. For a **tool or integration**, prefer its stable ordinary interface unless Pi-specific behavior adds demonstrated value. For an **Extension**, enumerate everything it registers, injects, mutates, or intercepts and confirm each runtime capability is necessary.

**Pass when:** no smaller mechanism delivers the same complete result and every remaining component changes a needed outcome or protects a required boundary.

## 3. Preserve user sovereignty

A candidate should keep the user's environment:

- **Visible** — active instructions, context, tools, state, automation, and side effects can be inspected.
- **Stable** — contracts and behavior are predictable enough to reproduce and debug.
- **Malleable** — the user can activate, modify, replace, and remove the mechanism.
- **Auditable** — inputs, actions, failures, and consequential decisions leave traceable evidence.

Trace filesystem, shell, network, credentials, provider requests, session mutation, and external writes from source rather than documentation claims. Human intent, architecture, critical review, and irreversible approvals remain human-owned. A confirmation dialog is not an isolation boundary; any security claim must rest on a control proportionate to the threat model.

Keep context, dependencies, maintenance, human review volume, and any recipient attention cost proportionate to demonstrated benefit. Check lifecycle, partial failure, concurrency, cleanup, and rollback wherever the candidate holds runtime authority.

Classify risk by observed authority:

- **Ordinary** — narrow behavior with no persistent runtime authority or external effect.
- **Side effects require caution** — automatic context or session changes, configuration writes, or bounded shell, filesystem, network, or external access.
- **High authority-boundary risk** — behavior that can grant, deny, redirect, or bypass execution authority, trust, credentials, provider requests, or destructive/remote-write approval.

**Pass when:** behavior and cost fit within a meaningful human review budget, authority is proportionate, and the user retains understanding and control.

## 4. Prove value proportionately and keep an exit

Use the lightest evidence that can establish the claimed value and boundary:

- For a static, low-authority artifact, inspect its unique information and use a deletion test when its behavioral effect is uncertain.
- For a behavioral claim, use a proportionate comparison or single-variable ablation.
- For runtime or high-authority mechanisms, verify lifecycle, failure behavior, observability, and rollback through the real Pi entry point.
- For preventive controls, verify that the mechanism enforces the stated invariant; do not require a prior incident merely to justify a credible high-cost boundary.
- Observe the outcomes material to the claim: success, regressions, tool use, context cost, latency, human intervention, and boundary adherence.
- Check provenance, license, compatibility, dependencies, install behavior, ownership, and maintenance burden.
- Record why the candidate exists, where it applies, supporting evidence, and the condition for expansion, re-evaluation, or removal.
- Require a bounded disable and removal path with no unexplained persistent state.

**Pass when:** proportionate evidence supports the claimed benefit or required boundary strongly enough for its cost and risk, failures are observable, and the candidate can be removed safely.

## Decision rule

- Recommend adoption only when all four gates pass for the candidate as-is.
- Defer only when no gate is known to fail but a specific decision-critical fact cannot be established after proportionate investigation because of a concrete external blocker. Name the bounded check, trial, user decision, or target-environment evidence that would settle it.
- Do not recommend adoption when any gate fails, a smaller mechanism is sufficient, authority is disproportionate, substantive changes are required, or the claimed need or value has not earned supporting evidence. A conclusive failure ends investigation of other gates unless they could change the authority-risk classification or smallest sufficient alternative.

A general lack of evidence for a claimed benefit is a failed gate, not a reason to defer. The absence of a prior incident does not invalidate an explicit requirement or a credible high-cost risk; support those with proportionate requirement, threat, or invariant evidence instead. Deferral is reserved for a specific blocked verification with a concrete resolution path. Both deferral and non-recommendation mean no adoption now; do not issue conditional recommendations. A materially changed candidate is a new candidate for a later review.

Minimalism means choosing no more—and no less—than the demonstrated need requires. Generation speed or smaller size never substitutes for human understanding, responsibility, and review.

## Design lenses

Current local Pi documentation is the authority for platform behavior. These sources inform the rubric's design principles without proving compatibility, safety, or value:

- Mario Zechner, [What I learned building an opinionated and minimal coding agent](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)
- Dietrich Gebert, [Ponytail](https://github.com/dietrichgebert/ponytail)
- Martin Fowler, [YAGNI](https://martinfowler.com/bliki/Yagni.html)
- KISS: prefer the simplest design that fully satisfies the known requirements
