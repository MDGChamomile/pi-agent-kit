---
title: Redesigning Agent Harnesses After Claude 5 and GPT-5.6
subtitle: "From Execution Control to Planning and Verification Boundaries: Synthesis of Four Key Sources and Recent Research"
date: 2026-08-02
type: research-report
status: complete
language: en
tags:
  - AI
  - agents
  - harness-engineering
  - context-engineering
  - Claude-5
  - GPT-5.6
  - AGENTS.md
  - multi-agent
  - RAG
source:
  - https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models
  - https://arxiv.org/abs/2602.11988
  - User-provided active developer statements
  - https://youtu.be/rdaQSG8KG-g?si=uOzQBGWXEzwGAASo
related:
  - "[[2026-07-26_Bun_Zig-to-Rust_AI_Agent_Verification_Loop]]"
  - "[[2026-07-03_OpenAI_Codex-maxxing_for_long-running_work]]"
  - "[[2026-07-18_matt-pocock-skills-v1.1-analysis]]"
---

# Redesigning Agent Harnesses After Claude 5 and GPT-5.6

> [!abstract] Core Conclusion
> Following Fable 5, Opus 5, and GPT-5.6, **the importance of agent harnesses has not vanished; rather, where a harness adds value has shifted.** Detailed rules, rigid prompt chaining, and redundant self-review meant to micromanage model behavior must be pruned. Conversely, non-discoverable intentions, decision criteria, tool interfaces, authorization boundaries, deterministic verifications, observability, and evaluation frameworks remain essential—and grow even more critical as model autonomy increases. The optimal structure is an **"hourglass harness"**: rich in intent at the input, thin in execution during the middle, and rigid at output and external action boundaries.

---

## 1. Research Question and Scope

This report answers the following question:

> Even after major advancements in instruction following, long-horizon reasoning, tool usage, and self-verification in frontier models, why are agent harnesses still necessary, and what should be deleted or retained?

The foundation of this analysis rests on four primary sources:

1. Anthropic, **"The new rules of context engineering for Claude 5 generation models"**
2. Gloaguen et al., **"Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?"**
3. Short statement from an active software developer provided by the user
4. Full transcript of a ~27-minute video by YouTuber Maker Evan provided by the user

This analysis incorporates official documentation from Anthropic and OpenAI (as of August 2, 2026) alongside research on `AGENTS.md`, harness design, multi-agent systems, self-review, long-context windows, and RAG.

> [!warning] Evidence Independence
> These four sources do not represent four independent pieces of evidence. Sources 3 and 4 reflect experiences from the same active developer presented at different lengths. Source 1 is vendor guidance, Source 2 is an independent benchmark study, and Sources 3 and 4 represent field experience and personal experimentation. Agreement across these sources should not be interpreted as four independent scientific replications.

---

## 2. Executive Summary

| Item | 2026 Baseline Judgment | Rationale |
|---|---|---|
| Long System Prompts | Prune | High repetition, instruction collision, and context cost; restricts frontier model reasoning space |
| Generic `AGENTS.md` / `CLAUDE.md` | Prune or Delete | Repository overviews and standard practices are discoverable in code; uncertain benchmark performance gain |
| Non-standard Rules & Hidden Gotchas | Retain | Cannot be inferred from code alone; high cost when misapplied |
| Prompt Chaining & Fixed Steps | Disable by Default | Obstructs native model planning and dynamic path adjustments |
| Tests, Schemas, & Static Analysis | Retain | Deterministic external oracles independent of model judgment |
| Approvals for External Calls / Deletion / Deployments | Enforce Strongly | Matter of authority, liability, and irreversibility, not model intelligence |
| Vague Self-Review Loops | Disable by Default | Increases costs, causes over-editing, suffers from single-context confirmation bias |
| Fresh-Context Review | Retain Conditionally for High-Risk Tasks | Improves error detection when isolated from execution context |
| Multi-Agent Systems | Exclude as Default | High coordination overhead and token duplication negate benefits unless tasks are highly parallel |
| RAG & Automatic Memory Injection | Conditional | Full context is better for small data; search is necessary for massive/dynamic codebases |
| Skills & Reference Docs | Load On-Demand | Progressive disclosure avoids permanent context window costs |
| Observability, Evals, & A/B Testing | Strengthen | Rapidly evolving models and harnesses make intuition-based validation unreliable |

The key distinction is that **making a harness thin is fundamentally different from eliminating the harness entirely.**

---

## 3. What Actually Changed in Frontier Models

### 3.1 Behavioral Control Moved In-Model

Anthropic noted that over 80% of the Claude Code system prompt was removed when updating for the Claude 5 model generation.[^1] Previously, models frequently misjudged comments, documentation, tool usage, and verification methods, requiring repeated explicit prohibitions and examples. Updated guidance shifts this approach:

- Long rule lists → Concise decision principles encouraging alignment with surrounding code
- Tool usage examples → Expressive, well-typed tool interfaces
- Pre-loading all documentation → Progressive disclosure via Skills, tools, and reference files loaded on demand
- Duplicate instructions in multiple locations → Single, concise tool descriptions
- Manual memory instructions → Automatic memory or explicit external records

OpenAI's official guidance for GPT-5.6 follows the exact same direction. GPT-5.6 infers user intent and required depth more accurately, making step-by-step procedural prescribing unnecessary. OpenAI reported that internal coding-agent evaluations using thinner system prompts improved scores by ~10–15%, while reducing total tokens by 41–66% and costs by 33–67%. OpenAI emphasizes treating these figures as directional internal metrics requiring domain-specific evaluation.[^2]

### 3.2 Model Capabilities Differ Across Families

User-provided video material summarizes model characteristics as follows:

- Opus 5: Superior long-horizon task maintenance and self-reflection
- Fable 5: Stronger grasp of style/tone and long-document processing
- GPT-5.6: Enhanced tool selection judgment and intent comprehension

Official documentation broadly supports these observations, albeit with nuanced qualifications:

- Opus 5 features enhanced long-horizon agentic capabilities, deep reasoning, code review, and self-verification. Anthropic cautions that legacy instructions explicitly commanding "always verify at the end" can cause over-verification behavior.[^3]
- Fable 5 offers a 1M token context window, extended autonomous execution, strong instruction following, and parallel delegation capabilities. For long-running tasks, documentation recommends progress auditing based on actual tool outputs, explicit boundaries, and independent verifiers when necessary.[^4]
- GPT-5.6 offers Programmatic Tool Calling for tool-heavy bounded workflows, and selective multi-agent patterns for complex tasks that decompose cleanly. Guidance advises matching routing structures to task topology rather than discarding tool rules and multi-agent setups entirely.[^2]

Consequently, asserting that "all execution harnesses are obsolete" is overly broad. A precise framing is:

> Modern frontier models rapidly replace **external scaffolding that imitates reasoning**, but they do not replace **operational substrates** handling tools, permissions, verification, and recovery.

---

## 4. Synthesis of Key Sources

### 4.1 Anthropic: Interfaces Over Verbose Instructions

Anthropic's advice focuses on **maximizing the signal-to-noise ratio of always-loaded context** rather than emptying prompts entirely.[^1]

`CLAUDE.md` files should retain:

- A brief statement of repository purpose
- Non-discoverable gotchas absent from code or file structures
- Non-standard team or product decision criteria
- Links to Skills or verification documentation loaded on demand

Conversely, `CLAUDE.md` files should omit:

- Repository overviews restating directory trees
- Standard coding conventions known to pretrained models
- Rules duplicating tool descriptions
- Absolute commands that do not apply universally
- Large procedural manuals saved for hypothetical future tasks

### 4.2 AGENTS.md Research: High Instruction Follow-Through, Unchanged Task Success

Gloaguen et al. evaluated four model combinations across SWE-bench Lite (300 tasks) and CTXBench (138 real-world issues from 12 Python repositories).[^5]

Key findings:

- LLM-generated context files decreased average success rates by 0.5 percentage points on SWE-bench and 2.0 percentage points on CTXBench, showing no statistically significant benefit.
- LLM-generated files increased average costs by ~20% and 23%, respectively.
- Developer-written context files improved success by an average of 2.4 percentage points over the no-context baseline, but the gain was statistically insignificant (`p=0.21`).
- Developer-written files performed significantly better than LLM-generated files (`p=0.038`).
- Context files increased exploration, tool invocations, and test execution. Failures occurred not because agents ignored instructions, but because **following additional instructions failed to translate into correct solutions.**
- When existing documentation was removed—making the context file the sole source of repository docs—LLM-generated files improved average success by 2.7 percentage points.

These findings indicate:

> Context value stems not from length, but from **providing additive information absent from existing code and docs**. Redundant information adds token cost, while unique, non-discoverable information acts as an asset.

### 4.3 Developer Insight: Outdated Weakness Maps Become Obstacles

A central metaphor from practitioner statements is that a harness represents a **map of model weaknesses** drawn at a specific point in time:

- Model forgets instructions → Force rigid sequential steps
- Model guesses assumptions → Force repetitive confirmation loops
- Model fails to plan → Force prompt chaining
- Model loses long context → Force chunk retrieval and re-injection
- Model struggles with multi-role tasks → Force multi-agent org charts

When model capabilities evolve but legacy weakness maps remain, frontier models follow outdated rules "too well," abandoning superior execution paths. This aligns with AGENTS.md research showing that adding context files caused agents to explore, test, and reason more, without significantly raising task completion rates.

### 4.4 Key Video Insight: Separating Execution Harnesses from Planning Harnesses

The video source divides harnesses into two functional components:

| Category | Core Question | Examples |
|---|---|---|
| Execution Harness | How to implement | Step enforcement, role separation, output formats, review loops |
| Planning Harness | What to build & why | Problem definition, decision criteria, constraints, decision records |

This distinction is crucial. As models advance, much of "how to implement" can be delegated directly to the model. However, no model can infer project-specific intent independently:

- Which customer problem takes priority
- Trade-off preferences between speed and perfection
- Hard boundaries and unacceptable risks
- Why alternative architectural options were rejected in the past
- Who holds authority to approve external actions

However, this binary division must be extended: within execution harnesses, **rules that interfere with behavior** must be distinguished from **deterministic safety gates that validate outcomes**. An agent choosing when to run tests is fundamentally different from a CI gate blocking merges when tests fail.

---

## 5. Counterexamples and Boundary Conditions

### 5.1 Context File Efficacy is Conditional

Subsequent research presents mixed conclusions:

- A study analyzing 124 PRs across 10 repositories reported that presence of `AGENTS.md` reduced median execution time by 28.64% and output tokens by 16.58% while maintaining task completion behaviors. This study focused on operational efficiency rather than gold-test correctness.[^6]
- A July 2026 study controlled across 288 runs (Claude Code and Codex, 17 tasks, 3 repositories) found that context file strategies did not significantly alter accuracy. Failures stemmed from implementation wiring flaws rather than repository knowledge deficits.[^7]
- Conversely, a probe-and-refine study using Qwen3.5-35B iteratively tuned repository guidance based on real execution failures, raising task resolution from 25.5% (unguided) to 33.0%. Gains came from improving coverage (reaching relevant files) rather than patch precision.[^8]

In summary, context files offer high expected value under specific conditions:

```text
Information is difficult to discover in code/docs
× Missing this information causes task failure
× Model cannot self-recover without the information
× Value verified against real failure logs
> Cost of tokens, attention dilution, conflicts, and maintenance
```

Value depends not on whether an `AGENTS.md` exists, but **what specific information it contains to prevent specific failures.**

### 5.2 Prose Decreases, but Structural Constraints Remain Essential

Agentic Harness Engineering (AHE) research raised Terminal-Bench 2 pass@1 scores from 69.7% to 77.0%. When transferring fixed harnesses to SWE-bench Verified, the system used 12% fewer tokens than the baseline. Ablation studies showed that tools, middleware, and long-term memory contributed significantly more to performance gains than system prompt prose.[^9]

This provides a vital counter-argument:

> Rather than becoming obsolete, **harnesses depend less on natural language prose and more on interfaces, state management, tool design, and observability.**

A "thin prompt" must not be confused with a "fragile execution environment."

### 5.3 Multi-Agent Systems are Parallelism Multipliers, Not Defaults

Anthropic's multi-agent research system demonstrated a 90.2% performance gain over a single Opus 4 agent in broad research tasks. However, token usage increased ~15-fold over standard chat. Anthropic explicitly noted that multi-agent architectures may be unsuitable for coding tasks that feature tight inter-file dependencies and require shared context.[^10]

A separate study controlling for compute budgets found that single agents equaled or surpassed multi-agent setups on multi-hop reasoning tasks. Reported multi-agent gains frequently stemmed from increased compute and context window expansion rather than architectural decomposition.[^11]

Multi-agent architectures should be reserved for scenarios where:

- Tasks decompose into genuinely independent sub-paths
- Wall-clock time reduction is high value
- Exploration breadth exceeds single-context window limits
- Clear artifact contracts exist to merge results
- High task value justifies multiplied token costs

When multiple agents sequentially pass code back and forth or require identical full context, single-agent setups remain superior.

### 5.4 Self-Review Depends on Oracles and Context Independence

Opus 5 performs extensive native self-verification, making legacy "always review your work" instructions prone to triggering over-verification loops.[^3] Official Fable 5 documentation notes that for long or high-risk tasks, a fresh-context verifier outperforms self-critique within the same context.[^4]

Cross-Context Review research evaluating 360 review runs across 150 injected errors showed that fresh-session reviews achieved an F1 score of 28.6%, compared to 24.6% for single-session reviews, 21.7% for dual-session reviews in the same context, and 23.8% for subagents receiving the original execution context.[^12]

Review mechanisms should be prioritized as follows:

1. Deterministic oracles (test suites, type checkers, schema validators, build commands)
2. Tool results and artifact readbacks
3. Fresh-context independent reviews (for high-stakes tasks)
4. Vague same-session "review if this is correct" prompts (last resort)

### 5.5 Long Context Windows Do Not Eliminate Targeted Retrieval

Loading large documents into context does not guarantee uniform attention across all tokens. Research shows information retrieval accuracy varies based on token positioning within long context windows ("lost in the middle").[^13]

Subsequent comparative studies indicate:

- Given sufficient compute, long context windows outperform chunk-based RAG on average
- Summarization-based retrieval performs comparably to full long-context loading
- Chunk-based retrieval risks losing inter-document relationships
- RAG offers lower costs and scales better for massive, dynamic document collections
- Hybrid routing based on query complexity and document size represents optimal practice[^14][^15]

Practical retrieval principles:

```text
Small, static core docs
→ Include full text or structured references directly

Massive or frequently updated codebases/docs
→ Targeted search, filtering, and summarization

Legal, policy, or schema documents with inter-clause dependencies
→ Retrieve adjacent clauses, parent definitions, and exceptions together, validating against source text
```

---

## 6. Core Framework: The Hourglass Harness Architecture

An effective modern harness features an "hourglass" topology: thick at the input boundary, thin during execution, and rigid at the output/action boundary.

```text
┌──────────────────────────────────────────────┐
│ Input Boundary: What & Why                  │
│ Problem / Criteria / Constraints / Done When  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Thin Execution  │
              │ Model Planning  │
              │ Minimal Rules   │
              └────────┬────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Output & Action Boundary: Truth & Safety     │
│ Tests / Schemas / Permissions / Approvals    │
└──────────────────────────────────────────────┘

Side Channel: On-Demand Skills, References, & Search
```

### 6.1 Thick Input Boundary

Define problem context thoroughly before execution begins:

```markdown
## Problem
Who experiences the issue, under what conditions, and what value is lost?

## Outcome
What observable state changes when this issue is resolved?

## Decision Principles
When A and B conflict, prioritize A. Rationale: ...

## Hard Constraints
Non-negotiable boundaries regarding data, security, compatibility, and cost.

## Done When
Checkable conditions defining task completion.

## Evidence
Required proof (test runs, source text, logs, diffs, readbacks).

## Out of Scope
Explicit non-goals.

## Approval Boundary
Actions requiring explicit human confirmation (deployments, deletions, external API calls).
```

This expands planning harness concepts into an actionable task contract.

### 6.2 Thin Execution Loop

Allow the model native autonomy during execution:

- Exploration order
- Task decomposition
- Tool selection
- Dynamic path adjustments
- Test execution sequence
- Verbosity and output structure

Avoid prescribing rigid procedural steps unless a specific recurring failure mode has been observed and verified.

### 6.3 Rigid Output and Action Boundary

Enforce deterministic safety and verification controls regardless of model capabilities:

- Unit test suites and type checkers
- Data schema and integrity validation
- Authentication and authorization checks
- Approvals for external, destructive, or financial actions
- Retry, timeout, and idempotency handling
- Session logging and execution tracing
- Checkpointing and state resume mechanics
- Actual file state readbacks

These controls exist to manage **failure costs, legal liability, non-determinism, and external system flaws**, rather than to patch model intelligence deficits.

---

## 7. Pruning and Retention Criteria

### 7.1 Priority Deletion Targets

1. Rules duplicated across system prompts, Skills, and tool descriptions
2. Repository directory trees discoverable via basic file inspection
3. Generic advice ("write clean code", "add thorough tests")
4. Fixed prompt chains forcing rigid step-by-step execution
5. Default multi-agent org charts applied to routine tasks
6. Unstructured self-review loops lacking clear evaluation rubrics
7. Rules patching legacy model mistakes that modern models no longer make
8. Automatic memory injection based purely on semantic similarity
9. Arbitrary chunking of small documents better handled in full context
10. Natural language hooks attempting to fake deterministic system behavior

### 7.2 Retain as Core Infrastructure

1. Non-discoverable team or product decision criteria
2. Non-standard build, test, and operational gotchas
3. Security, privacy, and data integrity boundaries
4. Human approval requirements for external or destructive actions
5. Verifiable acceptance criteria
6. Deterministic checks (tests, linters, schemas, static analysis)
7. Precise, well-typed tool interfaces
8. Observability, token cost tracking, and execution tracing
9. Checkpoints, session state, and artifact management for long tasks
10. Decision records containing dates, trade-offs, and rejected options

### 7.3 Conditional Retention Matrix

| Harness Element | Retain When | Delete When |
|---|---|---|
| Test Hooks | Failures must block merges or deployments | Model runs tests natively with no extra gate required |
| Verifier Agents | High-stakes tasks with clear specs & independent context value | Simple tasks; reviews in same context; vague rubrics |
| Multi-Agent | Tasks feature independent parallel sub-paths & high value | Tightly coupled tasks, shared state, routine edits |
| RAG | Codebase/doc set exceeds context window or changes dynamically | Core docs fit cleanly within single context window |
| Memory | Human-auditable, structured, and explicitly scoped | Automatic similarity injection without provenance |
| Skills | Captures recurring, specialized domain workflows | Generic knowledge or one-off procedural steps |
| Long Context Files | Measurably reduces task failure rates in evals | Consists of overviews, duplicates, or stale rules |

---

## 8. Recommended `AGENTS.md` / `CLAUDE.md` Structure

Root context files should act as **concise routers and gotcha lists** rather than comprehensive encyclopedias:

```markdown
# Repository Purpose
2-3 sentences explaining what this repository builds and achieves.

## Non-Discoverable Gotchas
- Non-standard conventions invisible from file inspection alone.
- Rules where violations cause immediate operational failures.

## Hard Boundaries
- Boundaries regarding external actions, data mutation, security, and compatibility.

## Verification Entry Point
- Primary commands or documentation links for validating changes.

## On-Demand References
- Links to Skills, ADRs, or runbooks loaded only when relevant tasks activate.
```

Anti-patterns to avoid:

- Full directory trees
- Exhaustive command lists available in `package.json` or `--help`
- Full copies of style guides
- Vendor-specific prompt examples
- Historical rules patching obsolete model bugs
- Duplicate information conflicting with official docs

A 2026 empirical study analyzing configuration smells across 100 open-source repositories found `Lint Leakage` in 62%, `Context Bloat` in 42%, and `Skill Leakage` in 35% of `AGENTS.md` files, with bloat and conflicting instructions frequently co-occurring.[^16]

---

## 9. Harness Maintenance Framework: Rules as Hypotheses

Treat every rule in a harness or context file as an **active, testable hypothesis**:

```yaml
id: H-017
reason: "Running full test suite from monorepo root causes 40min timeouts"
applies_when: "Modifying packages/payments/**"
intervention: "Load payment verification Skill on demand"
evidence: "eval/tasks/payment-07, payment-11"
introduced: 2026-08-02
owner: team-payments
review_after: 2026-10-01
remove_when: "Default model selects correct targeted test paths in 10 consecutive runs"
```

Every harness rule should have answers to four questions:

1. What specific real-world failure prompted this rule?
2. Which tasks and model generations does it apply to?
3. What measurable improvement (success rate, cost, risk reduction) does it produce?
4. Under what condition should this rule be re-evaluated or deleted?

Rules whose origins and justifications cannot be identified represent **behavioral technical debt**.

---

## 10. Evaluation Framework: From Intuition to Systematic Evals

Evaluating harness changes requires moving beyond single "bare model" tests to systematic evaluation suites.

### 10.1 Representative Evaluation Benchmark

- 10–20 representative real-world repository tasks
- Diverse difficulty levels (easy, medium, hard)
- Coverage across bug fixes, refactoring, docs, and operations
- Historical pass and fail task examples included

### 10.2 Single-Variable Ablation Testing

Evaluate one harness modification at a time:

```text
Baseline: Current full harness
A: Pruned context files
B: Removed prompt chains
C: Disabled same-context verifier
D: Disabled automatic memory injection
E: Minimal harness (bare model + task contract)
```

Modifying multiple parameters simultaneously masks which change drove performance differences.

### 10.3 Evaluation Metrics

| Metric | Question Answered |
|---|---|
| Task Success | Did the output pass deterministic completion criteria? |
| Regression Rate | Did the change break existing working functionality? |
| Human Interventions | How many manual interventions were required? |
| Token / Dollar Cost | What were input, output, and subagent execution costs? |
| Wall-Clock Latency | How long did end-to-end task completion take? |
| Tool Efficiency | Were there redundant searches, edits, or test invocations? |
| Scope Fidelity | Did the agent make unprompted changes outside task scope? |
| Boundary Adherence | Did the agent respect safety and authorization gates? |
| Debuggability | Can execution failures be diagnosed via traces? |

### 10.4 Decision Rules

```text
Statistically significant success gain
→ Retain rule

Identical success + Reduced cost/latency
→ Adopt simpler variant

Identical success + Increased cost
→ Prune rule

Minor success gain + Massive cost/risk increase
→ Limit to high-stakes opt-in workflows
```

---

## 11. Practical Implementation Recommendations

### 11.1 Individual Developer Workflow

```text
1. Define problem, intent, trade-off criteria, and done conditions on one page
2. Start with a minimal global system prompt
3. Allow the model to explore repository code and docs natively
4. Load targeted Skills and reference docs progressively on demand
5. Validate outputs via test suites, diffs, and artifact readbacks
6. Require manual confirmation for external calls, deployments, and deletions
7. Add specific harness rules only when recurring execution failures occur
```

### 11.2 Team and Production Architecture

```text
Intent / Spec / ADR
        ↓
Lean agent prompt
        ↓
Clear tool interfaces + least privilege
        ↓
Deterministic tests / schema / policy gates
        ↓
Observability + cost + trace
        ↓
Human approval for irreversible actions
```

### 11.3 Four-Week Harness Refactoring Plan

#### Week 1: Measurement & Inventory

- Audit existing system prompts, rules, hooks, Skills, memory, and subagents
- Establish baseline metrics (success rate, token cost, latency) on 10 benchmark tasks
- Identify hidden framework prompts and auto-generated tool descriptions

#### Week 2: Pruning Context Prose

- Delete duplicate rules across system prompts and tool descriptions
- Remove generic coding advice and directory overviews
- Refactor root `AGENTS.md` / `CLAUDE.md` into router pointers and gotcha lists
- Move task-specific documentation into on-demand Skills or reference files

#### Week 3: Thinning Execution Loops

- Remove fixed prompt chains forcing rigid step sequences
- Disable default multi-agent setups for single-agent tasks
- Remove unstructured, same-context self-review loops
- Convert automatic memory injection into opt-in, human-auditable logs

#### Week 4: Strengthening Boundaries & Gates

- Verify test, schema, permission, and approval gates
- Implement end-to-end token cost tracking and execution tracing
- Assign ownership, justification, and review dates to all remaining rules
- Re-run benchmark evaluations to measure before-and-after improvements

---

## 12. Avoiding Over-Generalization

### 12.1 Vendor Documentation is Directional, Not Independent Proof

Vendor guidance from Anthropic and OpenAI reflects internal model evaluations. Metrics like OpenAI's reported 10–15% benchmark gain on thinner prompts represent internal directional samples rather than independent academic replications across all enterprise codebases.

### 12.2 Research Findings Have Scope Boundaries

Empirical studies on `AGENTS.md` focused primarily on Python repositories and issue resolution benchmarks. Results should not be generalized blindly to proprietary monorepos, rare languages, security-critical systems, or specialized domain tools without local eval validation.

### 12.3 Practitioner Anecdotes serve as Hypotheses

Practitioner metrics ("7 minutes vs 2.5 hours", "6x cost increase") illustrate failure mechanisms effectively. However, absent public task suites and eval rubrics, they should be treated as **strong hypotheses driving local evaluation** rather than universal laws.

### 12.4 Models Do Not Own Risk or Liability

No matter how advanced models become, they do not hold responsibility for:

- Organizational trade-off preferences
- Legal and regulatory compliance
- Security and financial authorization
- Cost of data corruption
- External infrastructure failures
- Systemic liability when errors occur

Governance harnesses and deterministic safety kernels must remain in human control.

---

## 13. Conclusion

The evolution marked by Fable 5, Opus 5, and GPT-5.6 is not the end of agent harnesses. Rather, the shift can be summarized as follows:

### What shrinks

- Natural language rules attempting to patch model intelligence limits
- Pre-loading all codebase documentation into context
- Fixed execution sequences and prompt chains
- Redundant examples and instructional prose
- Default multi-agent org charts and vague self-review loops

### What remains and grows in importance

- Non-discoverable intent, business goals, and decision criteria
- Non-standard gotchas that prevent real execution failures
- High-expressivity, well-typed tool interfaces
- Deterministic test, schema, permission, and approval gates
- Progressive disclosure loading context only when required
- Observability, cost tracking, A/B evaluation, and removable design
- Decision records and human-owned risk boundaries

The central thesis of modern harness engineering is:

> **Shift the agent harness from the steering wheel of execution to the contract and safety belt of the task.**

A well-designed modern harness does not think for the model. It defines what the model must accomplish, grants autonomy during execution, and independently validates whether outputs and external actions meet safety and correctness standards.

---

## 14. References

### Primary Sources

- Anthropic, [The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models), 2026-07-24.

- Thibaud Gloaguen et al., [Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?](https://arxiv.org/abs/2602.11988), arXiv:2602.11988v2, 2026-06-23.

- Short statement from an active developer, provided by the user.
> Harnesses need to become much lighter.
>
> I think I emphasized hooks a great deal. But hooks have now become almost unnecessary. If hooks are necessary, that means there are many tasks that must be forced, and much less of that is needed now.
>
> Second, for AGENTS.md or CLAUDE.md—I wrote something similar in my course—“write almost nothing.” If you have written a great deal, empty it out. Do not write it. In other words, do not provide a large system prompt. I found that this steers model behavior far too much. So it is best to keep the system prompt extremely light and keep hooks to the absolute minimum.
>
> For example, recently I have mostly used only a hook that runs test code, or perhaps two hooks including one that injects system memory. But Claude and the Codex CLI now handle system memory so well that I recently removed that hook. Models have also been trained so well to run tests that they usually execute them automatically. I may remove that hook soon as well. The whole setup becomes extremely light.
>
> The point I most want to emphasize is context. From the perspective of context management, putting the right context in has become more important than anything else. We rarely need system prompts now, and hooks have become extremely light, so in the end the only remaining input is context. If you place the appropriate context for the development or task at hand and provide only a lightweight system prompt explaining it, the model seems to perform the work well.

- User-provided full developer video transcript: https://youtu.be/rdaQSG8KG-g?si=uLyjTV0TUD7UJn-E

### Vendor Primary Documentation

- OpenAI, [Using GPT-5.6](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6), accessed 2026-08-02.
- Anthropic, [What’s new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5), accessed 2026-08-02.
- Anthropic, [Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5), accessed 2026-08-02.
- Anthropic, [Introducing Claude Fable 5 and Claude Mythos 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5), accessed 2026-08-02.

### `AGENTS.md` and Harness Research

- Jai Lal Lulla et al., [On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents](https://arxiv.org/abs/2601.20404), arXiv:2601.20404v2, 2026.
- Prakhar Khatri, [Do Context Files Help Coding Agents? A Two-Agent Ablation Study on Real Repositories](https://arxiv.org/abs/2607.27250), arXiv:2607.27250v1, 2026.
- Asa Shepard and Jeannie Albrecht, [Probe-and-Refine Tuning of Repository Guidance for Coding Agents](https://arxiv.org/abs/2606.20512), arXiv:2606.20512v2, 2026.
- Jiahang Lin et al., [Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses](https://arxiv.org/abs/2604.25850), arXiv:2604.25850v4, 2026.
- Hélio Victor Flexa Dos Santos et al., [Configuration Smells in AGENTS.md Files: Common Mistakes in Configuring Coding Agents](https://arxiv.org/abs/2606.15828), arXiv:2606.15828v5, 2026.

### Multi-Agent, Review, and Retrieval Research

- Anthropic, [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system), 2025.
- Dat Tran et al., [Single-Agent vs. Multi-Agent Systems under Matched Test-Time Compute](https://arxiv.org/abs/2604.02460), arXiv:2604.02460v2, 2026.
- Tae-Eun Song et al., [Cross-Context Review](https://arxiv.org/abs/2603.12123), arXiv:2603.12123v1, 2026.
- Nelson F. Liu et al., [Lost in the Middle: How Language Models Use Long Contexts](https://aclanthology.org/2024.tacl-1.9/), TACL 2024.
- Xinze Li et al., [Long Context vs. RAG for LLMs: An Evaluation and Revisits](https://arxiv.org/abs/2501.01880), arXiv:2501.01880, 2025.
- Zhuowan Li et al., [Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach](https://aclanthology.org/2024.emnlp-industry.66/), EMNLP Industry 2024.

> All web sources accessed: 2026-08-02.
