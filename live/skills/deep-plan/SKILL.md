---
name: deep-plan
description: Grill a vague repository idea until user and agent reach the same page, then record the result as an execution plan.
disable-model-invocation: true
license: MIT
compatibility: Requires Pi with an ask_user tool compatible with pi-ask-user.
---

# Deep Plan

Move from **Fog → Same Page → Execution Record**.

Use this workflow for one cohesive repository change that can be brought to execution readiness in one session. Scale the interview to the live Fog, not to a minimum question count: an already concrete request may need no discovery questions before the Same Page readback. During Fog and Same Page, work read-only. During record writing, mutation is limited to creating needed parent directories under the selected records root, the final execution-record directory, and its Markdown files; do not modify or overwrite existing files or make any other repository changes. Unless the user explicitly selects another destination for that run, store records under the external state directory defined in `references/execution-record.md`. The record is an execution guide, not authorization; implementation requires a separate explicit user request.

## Requirement

Critical decision gates require a compatible `ask_user` tool. [pi-ask-user](https://github.com/edlsh/pi-ask-user) is the reference implementation and can be installed with `pi install npm:pi-ask-user`, but you may use a customized question extension instead if it exposes the same tool interface and supports the critical-gate behavior below. If the tool is unavailable at a critical gate, identify the blocker and unresolved gate in the final response, then stop. Unless Same Page was already explicitly confirmed, do not create an execution record.

## 1. Inspect and map the Fog

1. Read applicable repository instructions, relevant code, tests, documentation, configuration, logs, Git state, and prior decision artifacts.
2. Keep three things distinct:
   - **Evidence** — facts established by the repository or another authoritative source;
   - **Decisions** — meanings and preferences confirmed by the user;
   - **Fog** — unresolved in-scope branches whose answers could change the work.
3. Model the Fog as a living decision tree, including dependencies between unresolved branches.

Inspect far enough to distinguish Evidence from Decisions and identify the first unresolved branches whose prerequisites are already settled. Investigate later facts as their branches become answerable. Resolve discoverable facts yourself and reserve questions for user intent, preference-dependent trade-offs, authority, and meanings the repository cannot establish.

Before opening the interview, check workflow fit. If the request has expanded into multiple independently executable changes or can no longer reach execution readiness in one session, ask at most one scope gate needed to choose a coherent slice, then split or hand off the rest. Do not absorb scope growth by continuing to question across every workstream.

## 2. Resolve the Fog

Use no question quota in either direction. Continue only while a known unresolved branch can materially change execution; if inspection finds none, skip directly to Same Page. After every answer or new piece of evidence, recompute which unresolved branches can now be resolved, and re-check whether the work still fits this workflow.

### Critical gates

For load-bearing or authority-changing decisions that are ready to resolve, use `ask_user` with evidence gathered before asking. Ask one focused decision at a time. After an unclear or cancelled answer, make at most one narrower retry; if the gate remains unresolved, report the blocker and stop. A decision continues only this planning workflow and never authorizes implementation. Follow higher-priority system, developer, and user instructions, including tool-use requirements; this skill does not override them.

### Answerable questions

Once critical prerequisites are settled, use `ask_user` for each currently answerable question that still requires user input. Ask one focused question per call, include a short evidence summary in `context`, and recommend an answer where it helps. Do not bundle independent decisions into one tool call or a numbered list in a normal response.

Resolve prerequisite branches first, then ask the dependent questions they make answerable. Apply the critical-gate rules to a newly exposed critical decision; investigate a newly exposed fact yourself.

Each question closes a live branch whose answer could change behavior, scope, interfaces, risk, execution order, or completion evidence. Question count is not progress. Be complete on live Fog and silent on settled ground: do not ask the user to reconfirm repository evidence, their explicit decisions, or low-impact details that can safely remain execution-time choices. Keep resolved branches closed until new evidence invalidates their basis.

A branch is resolved only when it is:

- confirmed by the user;
- established by evidence;
- accepted by the user as an explicit assumption with an invalidation condition;
- assigned to a concrete prototype, investigation, external decision, or execution-time verification gate; or
- explicitly placed out of scope.

When discussion cannot settle a branch, identify the evidence or mechanism that can. Record that dependency instead of asking the user to guess. If the work no longer fits one session, surface the scope problem and record the required split or multi-session handoff rather than absorbing it into this workflow.

## 3. Reach the Same Page

Same Page is reached when every known in-scope branch is resolved, explicitly gated, or placed out of scope.

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

After Same Page is confirmed, read `references/execution-record.md` and write one execution-record directory. Always create its authoritative `PLAN.md`; add specs and tickets only when the reference's qualitative decomposition rules call for them.

Apply the reference's completion and integrity conditions, report the record-directory path, artifact shape, alignment state, readiness, and execution status, then stop without implementing.

When maintaining this skill itself, select and exercise only the affected scenarios through Pi as described in `references/behavior-evals.md`. Once the selected required checks pass, stop verification unless new changes, failures, or unresolved concerns justify expanding or repeating it.
