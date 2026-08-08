---
name: deep-plan
description: Grill a vague repository idea until user and agent reach the same page, then record the result as an execution plan.
disable-model-invocation: true
license: MIT
compatibility: Requires Pi with the ask_user tool provided by pi-ask-user.
---

# Deep Plan

Move from **Fog → Same Page → Execution Record**.

Use this workflow for one repository change that can be brought to execution readiness in one session. During Fog and Same Page, work read-only. The only allowed mutation is the final Markdown record and its selected directory. The record is an execution guide, not authorization; implementation requires a separate explicit user request.

## Requirement

Critical decision gates require the `ask_user` tool from [pi-ask-user](https://github.com/edlsh/pi-ask-user). Install it with `pi install npm:pi-ask-user` before using this skill. If the tool is unavailable, report the missing dependency and stop before the first critical gate rather than weakening the decision protocol.

## 1. Inspect and map the Fog

1. Read applicable repository instructions, relevant code, tests, documentation, configuration, logs, Git state, and prior decision artifacts.
2. Keep three things distinct:
   - **Evidence** — facts established by the repository or another authoritative source;
   - **Decisions** — meanings and preferences confirmed by the user;
   - **Fog** — unresolved in-scope branches whose answers could change the work.
3. Model the Fog as a living decision tree, including dependencies between unresolved branches.

Inspect far enough to distinguish Evidence from Decisions and identify the first unresolved branches whose prerequisites are already settled. Investigate later facts as their branches become answerable. Resolve discoverable facts yourself and reserve questions for user intent, preference-dependent trade-offs, authority, and meanings the repository cannot establish.

## 2. Resolve the Fog

Continue without a preset question or round limit until Same Page is reached or the user ends the session. After every answer or new piece of evidence, recompute which unresolved branches can now be resolved.

### Critical gates

Use `ask_user`, following its decision-gate protocol, for load-bearing or authority-changing decisions that are ready to resolve. Keep them one at a time and grounded in evidence.

### Answerable questions

Once critical prerequisites are settled, present the currently answerable, mutually independent lower-stakes questions as a numbered list in a normal response. Add a recommended answer where it helps. The user may answer naturally by number or in prose.

A question whose answer depends on another open question belongs to a later round. Promote a newly exposed critical decision to `ask_user`; investigate a newly exposed fact yourself.

A question earns its turn only when plausible answers could change behavior, scope, interfaces, risk, execution order, or completion evidence. Be **relentless on live Fog and silent on settled ground**: close resolved branches, reopen only branches invalidated by new information, and never manufacture questions to prolong the session.

A branch is resolved only when it is:

- confirmed by the user;
- established by evidence;
- accepted by the user as an explicit assumption with an invalidation condition;
- assigned to a concrete prototype, investigation, external decision, or execution-time verification gate; or
- explicitly placed out of scope.

When discussion cannot settle a branch, identify the evidence or mechanism that can. Record that dependency instead of asking the user to guess. If the work no longer fits one session, surface the scope problem and record the required split or multi-session handoff rather than absorbing it into this workflow.

If the user says to stop, stop asking immediately. Preserve unresolved branches and their execution impact; blocking Fog prevents the record from being marked ready.

## 3. Reach the Same Page

When Same Page appears reached, silently scan once for overlooked branches. Ask only if that scan finds live Fog.

Then read back only the understanding execution depends on:

- intended outcome and observable completion condition;
- representative normal, boundary, and failure behavior where material;
- confirmed decisions and accepted assumptions;
- scope, non-goals, and do-not-touch boundaries;
- deferred prototypes, investigations, external decisions, and verification gates.

State this limit explicitly:

> Same Page means every known in-scope branch has been resolved or explicitly gated. It is not proof that no unknown unknown exists.

If this exact understanding has not already been confirmed, use `ask_user` for one final alignment question. A correction reopens only the affected branches. Same Page confirmation unlocks record writing.

## 4. Write the Execution Record

After Same Page is confirmed—or after the user ends grilling—read `references/execution-record.md` and write one Markdown record.

Apply the reference's readback, report the path, alignment state, readiness, and execution status, then stop without implementing.
