---
title: Building Pi in a World of Slop — Mario Zechner Talk Analysis
subtitle: Context Sovereignty, Self-Extending Harnesses, the Clanker Issue in OSS, and Why Humans Must Remain the Bottleneck
date: 2026-08-02
type: research-report
status: complete
language: en
tags:
  - AI
  - coding-agents
  - pi
  - Mario-Zechner
  - harness-engineering
  - context-engineering
  - open-source
  - software-quality
  - human-in-the-loop
source_url:
  - https://youtu.be/RjfbvDXpFls?si=iRawrssNUSNmC8o7
  - https://youtu.be/Dli5slNaJu0?si=bIdP0ya3TVqQAxz7
related:
  - "[[2026-08-02_Claude5_GPT5.6_Agent_Harness_Redesign]]"
  - "[[2026-07-26_Bun_Zig-to-Rust_AI_Agent_Verification_Loop]]"
  - "[[Why_AI_Generated_Apps_Break_in_Production]]"
---

# Building Pi in a World of Slop

> Cross-Analysis of Mario Zechner's talks: **Building pi in a World of Slop** and **I Hated Every Coding Agent, So I Built My Own**

> [!abstract] Single-Sentence Thesis
> The core subject of these talks is not the Pi product itself, but rather **how to restore ownership of tools, context, and architectural decisions to human developers in an era of infinite AI code generation, re-establishing human comprehension and review as the intentional bottleneck of software quality.**

---

## 1. Executive Summary

Mario Zechner presents his journey through what he calls a **"three-act tragedy"**:

1. **Act 1 — Building Pi:** Rejecting tools like Claude Code and OpenCode for invisibly manipulating context and workflows, he built Pi: a minimal core combined with extreme extensibility.
2. **Act 2 — Open Source in the Agent Era:** As Pi became the agentic core of OpenClaw, open-source maintainers were flooded with auto-generated issues and PRs, shifting code review costs entirely onto humans.
3. **Act 3 — Slowing Down:** Unlocking infinite AI code generation causes minor errors and accidental complexity to accumulate faster than human review capacity. The solution is not more agents, but scope boundaries, modularity, evaluation functions, code volume caps, and human authorship/review of critical systems.

On the surface, two core messages seem in tension:

- Act 1: Agents must be free and malleable enough to build their own tools.
- Act 3: Agents should not be trusted with critical design and code.

However, the underlying philosophy is entirely consistent:

> **Pi's self-extensibility is designed not to hand product decisions over to agents, but to empower users to reclaim ownership of their development environment.**

Zechner does not call for "unconstrained autonomous agents." He argues for **high tool adaptability while retaining human agency over intent, architecture, and quality standards.**

---

## 2. Source Material and Methodology

This report synthesizes the following sources:

- Primary Talk: [Building pi in a World of Slop](https://youtu.be/RjfbvDXpFls) (and full timestamped transcript)
- Complementary Talk: [I Hated Every Coding Agent, So I Built My Own](https://youtu.be/Dli5slNaJu0) (and full timestamped transcript)
- Two distinct published full English transcripts of the primary talk
- Timestamped slide notes and community summaries
- Mario Zechner's official essays:
  - [What I learned building an opinionated and minimal coding agent](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)
  - [Thoughts on slowing the fuck down](https://mariozechner.at/posts/2026-03-25-thoughts-on-slowing-the-fuck-down/)
- [Official Pi Documentation](https://pi.dev/docs/latest) and [Official Repository](https://github.com/earendil-works/pi-mono)
- Current `CONTRIBUTING.md` and contributor gating workflows in the Pi repository

> [!note] Video Accessibility
> Both YouTube source videos were age-restricted in the analysis environment. Video content was verified across user-provided transcripts, published transcripts, and timestamped slide notes. Proper nouns and terminology were reconciled against Zechner's official blog posts and the Pi repository.

---

## 3. Structural Argument

```text
Harnesses invisibly manipulate prompt context
        ↓
Developers lose control over model working conditions
        ↓
Need a minimal core + full observability + user extensibility
        ↓
Pi: A small, malleable, self-extending harness
        ↓
Yet if extensibility & generation speed replace human judgment
        ↓
OSS review costs and codebase errors explode exponentially
        ↓
Solution: Humans must reclaim scope, evaluation, review, & intent
```

In this argument, **context sovereignty** and **human agency** represent two expressions of the same principle:

- Context Sovereignty: Users know exactly what enters the model context and which tools are active.
- Human Agency: Users decide what to build and which architectural trade-offs to accept.

Act 1 reclaims control over developer tooling; Act 3 reclaims control over software product architecture.

---

# Act 1 — Building Pi

## 4. Why Leave Existing Agents? Context Ownership Over Feature Creep

Zechner speaks highly of the Claude Code team, noting that around April 2025, Claude Code was the first tool that made AI agents feel genuinely viable. Initially simple and predictable, it fit his workflow well.

His criticism was not feature growth per se, but four core issues:

### 4.1 Tool Instability

Rapid releases led to unexpected bugs and behavioral changes. He compares developer tools to a hammer on a construction site:

> If your hammer breaks every day, you get angry. Developer tools breaking every day should evoke the same reaction.

A developer tool is an operational foundation supporting user habits, custom prompts, automation, and review workflows. When that foundation shifts daily, workflows lose reproducibility.

### 4.2 Invisible Context Mutations

The central quote of the talk appears at [1:56](https://www.youtube.com/watch?v=RjfbvDXpFls&t=116s):

> **"My context wasn't my context."**

When tools modify system prompts, alter tool schemas, or insert hidden system reminders mid-conversation without user visibility, identical user prompts run under completely different working conditions.

This creates several issues:

- **Loss of Reproducibility:** Workflows that succeeded yesterday fail today under identical prompts.
- **Inability to Trace Root Causes:** Distinguishing model failure from hidden harness prompt injection becomes impossible.
- **Attention Pollution:** Irrelevant or semi-relevant information dilutes attention across long contexts.
- **Contract Drift:** Unannounced tool modifications alter the behavioral reasoning space expected by the model.

Zechner defines context engineering not as "injecting as much helpful data as possible," but:

> **Maintaining a state where you know exactly what entered context, why it entered, and how to modify it.**

### 4.3 Lack of Observability

Developers need to inspect what the agent read, skipped, or executed. Without observability, post-failure debugging degrades into guessing root causes from final outputs alone.

Observability enables:

- Isolating model failures from harness bugs
- Identifying missing context
- Analyzing token costs, latency, and tool invocation patterns
- Iteratively refining repeatable workflows
- Determining when human intervention is required

### 4.4 Model Lock-In and Limited Extensibility

While Claude Code naturally focuses on Anthropic models, Zechner sought an environment decoupled from single providers. Furthermore, rather than shallow lifecycle hooks, he required a deep extension API with access to events, tools, session trees, custom UI, and compaction policies.

---

## 5. Critique of Automated Context Manipulations

Automated optimizations intended to save tokens frequently degrade performance:

### 5.1 Tool Output Pruning and Prompt Cache Destruction

In the complementary talk [11:42](https://www.youtube.com/watch?v=Dli5slNaJu0&t=702s), Zechner criticizes automated pruning strategies (such as stripping tool outputs prior to the last 40k tokens). Pruning tool outputs removes historical evidence observed by the model—akin to "lobotomizing" the agent mid-task.

Additionally, altering prefix content invalidates provider **prompt caches**, producing two simultaneous negative effects:

1. The model loses task memory and observed evidence.
2. Uncached prompt prefixes increase latency and API costs.

Tool outputs are not disposable logs; they represent:

- Observed system and file state
- Evidence backing subsequent reasoning
- Command failure and recovery history
- Exploration history preventing duplicate tool calls

Indiscriminate pruning sacrifices **semantic continuity** for token savings. Effective compaction must allow users to define what to retain versus discard based on specific workflows.

### 5.2 Real-Time Linter Errors During Edits

Zechner criticizes appending Language Server Protocol (LSP) diagnostics to tool outputs immediately after every edit. Code is naturally incomplete mid-edit; injecting temporary syntax errors forces models into reactive local patching loops rather than completing intended structural changes.

```text
Flawed Loop:
Edit line → Inject temporary error → Apply local patch → New error → Local patch

Preferred Loop:
Complete structural edit → Run diagnostics at milestone → Resolve errors holistically
```

LSP diagnostics themselves are not harmful; **validation timing must align with natural synchronization points** [14:01](https://www.youtube.com/watch?v=Dli5slNaJu0&t=841s). Diagnostics should run when the agent completes a logical change batch, rather than injecting intermediate failure state after every tool call.

### 5.3 Over-Engineered Session Storage & CORS Misconfigurations

Storing individual messages as separate JSON files complicates session inspection. Furthermore, overly permissive CORS settings in local agent servers expose developer machines to cross-origin requests from arbitrary browser tabs.

These examples reflect a single principle:

> Automated convenience features that increase hidden state, processes, and permissions introduce disproportionate operational costs.

---

## 6. Lessons from Terminus 2: Minimal Harnesses Are Not Weak

At [4:47](https://www.youtube.com/watch?v=RjfbvDXpFls&t=287s), Zechner references **Terminus 2** from Terminal-Bench.

Terminus 2 provides a model with essentially two primitives:

1. Send keystrokes to a `tmux` session
2. Read `tmux` terminal output

It lacks specialized file tools, subagents, or complex planning modules. Yet in December 2025, it equaled or outperformed complex native harnesses across multiple model families.

The complementary talk [17:45](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1065s) adds context: while Terminus is an excellent benchmark interface, its raw terminal interface is unsuitable for human developer experience. **Minimal model interfaces** and **observable, human-friendly collaboration UIs** represent separate design requirements.

Key takeaways from Terminus 2:

- Current agent harness designs are far from final.
- Feature count does not correlate with task performance.
- Models possess strong pretrained priors for shell interaction and coding workflows.
- Heavy harness scaffolding meant to "help" models frequently obstructs reasoning.
- Iterative experimentation requires a minimal, modifiable core.

> [!warning] Benchmark Interpretation
> Terminal-Bench results demonstrate that minimal harnesses can be highly competitive; they do not prove that minimal harnesses are superior across all enterprise workflows. Benchmark scores vary by model, inference settings, and task design, and do not measure long-term maintainability.

---

## 7. Pi's Architecture: Minimal Core, Maximum Extensibility

Pi avoids feature-deprived minimalism:

> **Build a small, predictable core, and allow users to extend functionality as needed.**

### 7.1 Four Core Packages

Pi is structured into four decoupled layers:

| Package | Role |
|---|---|
| `pi-ai` | Unified model provider abstraction with cross-provider context handoff |
| `pi-agent-core` | Core agent loop handling tool validation and event streaming |
| `pi-tui` | Lightweight terminal UI framework built on differential rendering |
| `pi-coding-agent` | Interactive CLI, headless SDK, built-in tools, and extension binding |

This architecture decouples model APIs, the agent loop, UI rendering, and user features into independent layers.

### 7.2 Minimal System Prompt

At [6:21](https://www.youtube.com/watch?v=RjfbvDXpFls&t=381s), Zechner shows Pi's minimal system prompt.

Core assumptions:

- Modern models have learned coding agent behaviors during post-training.
- Explaining "you are an AI coding assistant" at length is redundant.
- The harness needs only to supply tool definitions and explicit project context.

While Pi's system prompt has expanded slightly to support features like Skills, its core philosophy remains: **a short base prompt supplemented by documentation loaded on demand.**

### 7.3 Four Basic Tools

At [6:57](https://www.youtube.com/watch?v=RjfbvDXpFls&t=417s), Pi provides four primitive tools:

- `read`
- `write`
- `edit`
- `bash`

Models understand these primitive tools natively. Rather than building dedicated tools for `git`, `test`, `search`, background processes, or subagents into the core, models combine `bash` and basic file operations.

Benefits of primitive tool sets:

- Stable tool semantics across releases
- Reduced decision space branching for the model
- Compact tool schemas saving prompt context
- Higher-level workflows composable via files, CLI scripts, or extensions
- Clear root-cause tracing when executions fail

### 7.4 Self-Extension via Documentation and Examples

Pi's "self-modification" is not an agent rewriting core source code invisibly:

```text
Pi reads its extension documentation
        ↓
Generates a TypeScript extension for the requested workflow
        ↓
Hot-reloads the extension in the live session
        ↓
Developer inspects behavior and provides feedback
```

This represents an **agent-assisted self-extension loop** combining API documentation, executable code examples, file editing, and runtime hot-reloading.

Key advantages:

- Extension code is explicit and visible on disk
- Full diffing and version control supported
- Humans specify requirements and inspect outputs
- Workflows are customized without forking core repositories

### 7.5 TypeScript Extension API

A Pi extension can be as simple as a single TypeScript file. Extensions can:

- Register custom tools or override built-in tools
- Register slash commands and keyboard shortcuts
- Subscribe to lifecycle events (`session_start`, `tool_call`, `before_agent_start`, `context`)
- Intercept and block tool execution via permission gates
- Store custom session state and define custom TUI renderers
- Register custom compaction algorithms and model providers
- Modify TUI layouts (widgets, footers, overlays)
- Implement plan modes, subagent runners, MCP connectors, or sandboxes in user space

Pi distributes extensions via standard package managers (`npm`, `git`) rather than isolated proprietary marketplaces.

### 7.6 Game Development Iteration Speed

Hot-reloading (`/reload`) is a core design requirement. Drawing from game development, Zechner emphasizes that **minimizing iteration latency accelerates feedback between design and reality**:

```text
Describe workflow → Generate extension → Reload → Test in session → Refine
```

Building Pi extensions inside Pi creates a tight collaborative feedback loop between human and agent.

---

## 8. What Extension Examples Prove

Zechner demonstrates various extension capabilities:

- Intercurring side-queries via commands like `/btw`
- Multi-agent chatrooms with custom rendering
- Terminal games (NES, Doom)
- Subagent runners and MCP adapters
- **Pi Annotate:** An overlay allowing developers to annotate web UI elements directly into agent context
- **File Switcher:** An overlay for inspecting changed files without switching IDE windows
- SSH remote execution wrappers for `read`, `edit`, and `bash`

These examples prove that:

1. UI and agent behavior can be modified deeply without altering core code.
2. Developers with differing workflow preferences can implement custom rules without forking core tools.
3. Agents can read API docs and write functional extensions.
4. Minimal core design **shifts feature ownership from core codebase to user space**.

The complementary talk highlights Pi's **tree-structured session history**. Rather than forcing linear chat histories, tree sessions allow branching into exploration paths, summarizing findings, and returning to the main branch carrying only summary artifacts. This isolates exploration context without resorting to black-box subagents. Combined with token cost tracking, HTML export, JSON session formats, and headless JSON streaming, Pi prioritizes end-to-end observability.

Pi achieving 6th place on Terminal-Bench prior to implementing compaction serves as supporting evidence that minimal harness design remains benchmark-competitive.

Zechner emphasizes:

> **The goal is reclaiming control over your tools and workflows. Build your own if necessary.**

---

## 9. The "YOLO" Security Philosophy: Honest Risk Models vs Permission Fatigue

Pi defaults to running with user permissions without prompting confirmation popups for routine tool calls ("YOLO mode"). Zechner rejects confirmation dialogs as effective security mechanisms.

His rationale:

- If an agent reads files, writes code, executes shell commands, and accesses networks, its attack surface is broad by default.
- Repetitive confirmation popups induce habituation fatigue, causing users to approve prompts blindly.
- Security requirements vary widely; standard popups offer a false sense of safety.
- Users requiring isolation should use containers, VMs, tool allowlists, or custom permission-gate extensions.
- Confirmation fatigue causes developers to disable popups entirely or hold Enter repeatedly [20:27](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1227s).
- Containerization provides genuine isolation boundaries rather than interactive security theater.

> [!danger] Critical Evaluation
> Extensibility is not a substitute for default security boundaries. Providing the ability to build security gates differs from offering safe defaults. While YOLO execution suits experienced developers in sandboxed environments, it transfers significant security responsibility onto end users in enterprise or multi-tenant settings.

Practical framing of Pi's security philosophy:

```text
Do not rely on confirmation popups as primary security
≠ Omit all security boundaries

Implement genuine isolation matched to your threat model:
Containers / VMs / Least-privilege accounts / Network policies /
Secret isolation / Path protections / External write approvals / Audit logs
```

Official Pi documentation explicitly recommends container or sandbox execution for high-risk environments.

---

# Act 2 — Open Source in the Agent Era

## 10. Post-OpenClaw: The Asymmetry Between Code Generation and Review Costs

At [10:46](https://www.youtube.com/watch?v=RjfbvDXpFls&t=646s), Zechner addresses the impact of AI on open source. As Peter Steinberger adopted Pi as the agentic engine for OpenClaw, the Pi repository was flooded with automated issues and PRs generated by unmonitored OpenClaw instances.

This highlights a fundamental economic shift in open source:

```text
Cost for AI agents to generate issues & PRs: ~0
Cost for human maintainers to review & verify: Constant or Increasing
```

The core issue is **cost externalization**:

- Contributors generate long PRs in seconds.
- Maintainers spend hours reproducing and verifying submissions.
- Plausible-sounding hallucinated bug reports consume more review time than obvious spam.
- Automated instances do not read rejection comments or engage in meaningful follow-up.
- As project popularity grows, low-cost automated submissions overwhelm maintainer capacity.

The phrase "clankers are destroying OSS" critiques the **decoupling of generation costs from review costs**.

---

## 11. Human Voice Gates: Proof of Attention

Zechner implemented maintainer gates to manage automated submission floods:

1. Automatically close PRs from new accounts.
2. Instruct contributors to submit concise, single-screen issues in their own words.
3. Add responsive contributors to an account allowlist (`lgtmi` / `lgtm`).
4. Allow subsequent PRs from allowlisted accounts.

Automated bots rarely read rejection comments or respond meaningfully; human contributors read guidelines and clarify intent. This gate acts as **proof of human attention** rather than a simple CAPTCHA.

Current Pi repository policy formalizes this workflow:

- Issues and PRs from new contributors are closed automatically.
- Maintainers review closed issues daily.
- Submissions must be concise, specific, and reproducible on one screen.
- `lgtmi` grants issue submission access; `lgtm` grants PR submission access.
- AI tools may assist in grouping duplicates, but final review and submission remain human responsibilities.

This mechanism is not meant to detect AI text usage:

> **It verifies that a human tested the change, understood the problem, and remains available for follow-up maintenance.**

### 11.1 Additional Maintainer Strategies

- Deprioritizing submissions linked to automated agent run logs
- Clustering submission embeddings in 3D vector space to identify automated issue campaigns
- Temporarily closing issue trackers ("OSS vacations")
- Implementing peer-vouching networks (e.g., Mitchell Hashimoto's `vouch` model)

Key maintainer lesson:

> **Maintainer sustainability takes precedence over open repository access.**

---

## 12. Implications for Open Source Software

### 12.1 Unit of Contribution Shifts from Code Volume to Maintenance Responsibility

In the AI era, code generation is trivial. Real open-source contributions consist of:

- Reproducing real-world failure cases
- Aligning changes with project architecture
- Minimizing change scope
- Verifying cross-subsystem impacts
- Responding to maintainer feedback
- Assuming long-term maintenance responsibility

### 12.2 Automated Systems Require Receiver Attention Budgets

Agentic tools sending issues, PRs, emails, or messages must account for the recipient's review budget:

```text
Total Cost of Automated Submissions
= Generation Cost
+ Recipient Review Cost
+ Verification Cost
+ False-Positive Cost
+ Follow-Up Communication Cost
```

This applies equally to enterprise PRs, ticket systems, security reports, and automated internal tooling.

### 12.3 "Human Voice" Represents a Responsibility Signal

Generating human-like prose is trivial for frontier LLMs. "Human voice" serves not as a stylistic check, but as a **signal of human ownership, testing, and responsibility**.

---

# Act 3 — Slowing Down

## 13. Pushing Back Against "100% Agent-Built" Narratives

At [12:02](https://www.youtube.com/watch?v=RjfbvDXpFls&t=722s), Zechner critiques marketing narratives celebrating fully automated code generation:

> "Our product was 100% built by AI agents."  
> "Right, that's why it's terrible. Congratulations."

This critiques treating **code generation speed as a proxy for software quality**. High-volume code generation says nothing about:

- User utility
- Operational stability
- Architectural consistency
- Maintainability during outages
- Future refactoring costs
- Test suite validity

Zechner describes this trend as "an addiction to generating the maximum volume of code in the minimum amount of time."

---

## 14. Error Accumulation: Zero Learning, No Bottleneck, Delayed Pain

Zechner refers to minor code flaws and code smells as **booboos**:

- Unused helper methods
- Unclear type definitions
- Duplicate logic introduced by missing existing utilities
- Unnecessary abstractions
- Excessive defensive backward-compatibility code
- Cargo-cult defensive programming patterns

Individual flaws are rarely fatal; the problem lies in their **accumulation velocity**.

### 14.1 Humans vs Agent Fleets

| Attribute | Human Developers | Agent Fleets |
|---|---|---|
| Generation Speed | Slow (Natural speed limit) | Infinite (Removes generation bottleneck) |
| Learning from Errors | Learns via feedback & pain | Sessions are statless; errors repeat |
| Pain Response | Experiences friction; refactors | Experiences no pain; continues generating |
| System Comprehension | Builds mental models over time | Evaluates local context per turn |
| Cost of Complexity | Experienced early during writing | Deferred onto future maintainers |

Human writing speed acts as a natural safety limit on error accumulation. When codebases grow complex, developers experience friction and refactor.

Agent fleets remove both control mechanisms:

```text
Minor Error Rate × Massive Code Volume × Zero Cross-Session Learning × Delayed Discovery
= Exponential Accumulation of Technical Debt
```

This is the **compounding error model** ("compounding booboos").

---

## 15. Merchants of Learned Complexity

LLMs are trained on vast internet codebases containing anti-patterns, cargo-cult abstractions, and legacy workarounds. When task specifications contain ambiguities, models fill gaps with their trained averages.

At [14:19](https://www.youtube.com/watch?v=RjfbvDXpFls&t=859s), Zechner states:

> **"You know what we call a sufficiently detailed spec? It's a program."**

This highlights the limits of natural language specifications:

- Imprecise specs allow model priors to dictate architectural decisions.
- Specs detailed enough to eliminate all ambiguity require as much effort as writing code directly.
- Verbose natural language specs introduce internal contradictions and oversights.
- Delegating spec-writing to agents reproduces trained complexity one step earlier in the pipeline.

Specifications should focus on defining core human boundaries:

- What to build and why
- Explicit non-goals
- Invariant architectural constraints
- Trade-off priorities
- Decision authority boundaries

### 15.1 Locally Correct, Globally Flawed

Agents operate within limited context windows, leading to local optimizations that degrade global architecture:

```text
Fails to locate existing utility → Implements duplicate helper
Fails to see global convention → Adds local exception logic
Unaware of original design rationale → Adds compatibility wrapper
Fails to trace root cause → Applies local patch
```

While local patches pass unit tests, they accumulate global complexity. Zechner summarizes this as **"patches locally and fucks up globally."**

---

## 16. Why Long Context Windows and Agentic Search Do Not Solve Architecture

Relying on 1M+ token context windows is a **temporary workaround** rather than a structural solution.

Context size alone does not resolve retrieval challenges:

1. Agents must identify which files to read.
2. Codebase expansion degrades search recall.
3. Missed existing implementations lead to duplicate code.
4. Missed caller dependencies introduce regressions.
5. Models do not attend to all tokens in long contexts uniformly.

Tooling like `ripgrep`, LSP servers, and vector databases cannot guarantee 100% recall across large repositories. When retrieval is incomplete, models generate plausible outputs based on partial evidence.

The most effective context engineering is architectural:

> **Decompose software into clean module boundaries so that entire task contexts fit within a single, focused prompt window.**

---

## 17. The Ouroboros Problem of Review Agents

Addressing agent errors by adding "reviewer agents" creates a feedback loop Zechner calls the **Ouroboros problem**:

- Writer and reviewer agents share identical training data and biases.
- Both rely on the same incomplete codebase context.
- Generated test suites may reflect the same underlying false assumptions.
- Reviewer-suggested fixes introduce new accidental complexity.
- Iterative review-repair loops lack an independent ground-truth oracle.

```text
Agent generates code
  → Agent generates tests
    → Agent reviews code
      → Agent applies fixes
        → Cycle repeats within the same incomplete worldview
```

Review agents have utility, but **without independent oracles and execution feedback, adding reviewer agents does not create system reliability.**

Effective verification hierarchy:

1. Real-world user reproduction cases
2. Human-defined invariant constraints
3. Deterministic test suites, type systems, and static analysis
4. Actual artifact readbacks and manual execution
5. Fresh-context independent verifiers
6. Same-context agent code reviews (lowest priority)

---

## 18. Operational Impairment from "Not Reading Code"

Zechner criticizes the attitude of "never reading generated code."

When production outages occur, this creates severe operational failure modes:

- Users experience production outages.
- Developers lack accurate mental models of the system.
- Agents fail to retrieve full codebase context for complex bugs.
- Tests generated by agents reflect original false assumptions.
- Developers apply surface-level AI patches, worsening system complexity.

Writing and reading code manually builds essential mental models:

- Location and boundaries of core domain concepts
- Original trade-off decisions and design rationales
- Subsystem coupling and failure propagation paths
- Initial diagnostic steps during production incidents

Without mental models, developers degrade from system architects into prompt relayers.

---

## 19. Characteristics of Effective Agent Tasks

At [16:12](https://www.youtube.com/watch?v=RjfbvDXpFls&t=972s), Zechner outlines criteria for suitable agent tasks:

### 19.1 Closed Task Scope

Scope tasks so agents can retrieve all necessary context:

```text
Well-Bounded Scope:
- Contained within a single module
- Explicit inputs and outputs
- Small set of relevant files
- Fully enumerable callers and side effects

Poorly-Bounded Scope:
- Requires understanding full system architecture
- Involves implicit cross-service contracts
- Success criteria limited to "looks good"
- Un-documented historical design rationales
```

### 19.2 Modular Architecture

Modularity serves as a **context boundary for AI agents**, mitigating low recall in agentic search by co-locating relevant context.

### 19.3 Measurable Evaluation Functions

Objective evaluation functions enable automated optimization loops (e.g., auto-research):

- Execution time / Latency
- Memory footprint
- Loss metrics
- Test suite pass rates
- Reproduction case resolution
- Schema compliance

Evaluation functions do not protect unmeasured quality attributes. Optimizing purely for speed can sacrifice readability and maintainability. Evaluation metrics must serve as oracles, not complete proxies for product judgment.

### 19.4 Disposable or Non-Core Workflows

Tasks well-suited for AI execution:

- One-off internal utilities
- Repetitive boilerplate
- Exploring alternative prototype implementations
- Drafting reproduction cases for user bug reports
- Interactive rubber-ducking
- Disposable spike code

### 19.5 Humans as Final Evaluators

Post-generation execution flow:

```text
Generate → Human Evaluation → Select Reasonable Components → Human Finalization
```

Developers must avoid default-accepting generated output.

---

## 20. Task Allocation Framework by System Criticality

| Task Type | Agent Role | Human Role |
|---|---|---|
| Disposable / Non-Core | Autonomous generation & spikes | Rapid sanity check |
| Bounded Boilerplate | Draft implementation & unit tests | Review diffs & execution results |
| Objective Eval Metrics | Iterative optimization loops | Monitor metric side-effects |
| Bug Reproduction | Draft minimal reproduction scripts | Validate reproduction accuracy |
| Core Features | Exploratory pairing & draft options | Review all code lines & boundaries |
| Architecture / APIs | Summarize options & trade-offs | Direct design & code execution |
| Security / Financial | Bounded draft assistance | Full ownership of design, code, & tests |
| System-Wide Refactoring | Do not generate directly | Decompose & modularize system first |

Zechner's core rules:

- Disposable code can tolerate "vibe slop."
- Core production code requires **reading every line.**
- System architecture and core API boundaries should be written directly by human developers.
- Agents should serve as pair programmers, not primary decision-makers.

---

## 21. Capping Code Generation Volume

At [17:20](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1040s), Zechner presents a core operational rule:

> **Generate only as much code as you can meaningfully review.**

Operational rule:

```text
Max Generation Volume ≤ Human Capacity for Meaningful Code Review
```

When generation volume exceeds human review capacity, three failure modes occur:

1. Review queues expand indefinitely.
2. Review depth degrades.
3. Code is merged without review.

Adding reviewer agents does not eliminate shared biases or context omissions. Human review capacity must be preserved as an **intentional quality control bottleneck**.

---

## 22. Core Takeaways from the Final Slide

1. Think carefully about what to build and why.
2. Do not build features simply because AI agents make generation easy.
3. Reclaim the ability to say "no" to unnecessary features.
4. Reduce feature bloat and refine core capabilities.
5. Focus on user utility rather than token consumption.
6. Limit code generation to human review capacity.
7. Read critical code lines and own core architectural decisions.
8. View the friction of writing code as an essential learning mechanism.

> **"All of this requires discipline and agency. All of this still requires humans."**

"Slop" refers not merely to poor AI-generated code, but to **any output optimized purely for generation speed without intent, comprehension, review, or responsibility.**

---

# Cross-Analysis with the Complementary Talk

## Shared Core Arguments

The talk **I Hated Every Coding Agent, So I Built My Own** expands on Acts 1 and 2 of the primary presentation across ~27 minutes, repeating core arguments in sequence:

1. Claude Code evolved from a simple tool into an unobservable "spaceship."
2. Hidden context injections and frequent unannounced tool changes destabilize workflows.
3. OpenCode's tool output pruning, mid-edit LSP diagnostics, and server security issues impaired developer trust.
4. Terminus proved that minimal tool sets can achieve competitive benchmark performance.
5. Pi combines a minimal core with an extension API to allow user-driven harness customization.
6. Automated PR floods post-OpenClaw required human verification gates in open-source maintainer workflows.

This consistency confirms these arguments reflect an established, long-term design philosophy.

## Additional Technical Insights from the Complementary Talk

### 1. Historical Evolution of Coding Agents

At [2:18](https://www.youtube.com/watch?v=Dli5slNaJu0&t=138s), Zechner outlines the agent lineage:

```text
ChatGPT copy-paste
→ GitHub Copilot tab completion
→ Aider / AutoGPT
→ Claude Code ad-hoc repository search
```

Claude Code's breakthrough was using post-trained models with file tools and shell access to perform ad-hoc repository exploration rather than relying on pre-built repository indexes. Zechner's critique targets the feature creep and loss of context transparency that followed that initial breakthrough.

### 2. "Spaceships" and Dark Matter

At [4:52](https://www.youtube.com/watch?v=Dli5slNaJu0&t=292s), Zechner describes complex software as "spaceships" where users understand 10% of features, use 5%, and remain unaware of the rest (**dark matter**). The primary risk occurs when unobserved features manipulate prompt context and application state in the background.

### 3. Externalizing Features via Standards

Pi externalizes features to existing tools and formats rather than building proprietary core abstractions [21:17](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1277s):

| Feature | Pi Alternative |
|---|---|
| MCP | CLI + Skill, or MCP extension |
| Subagents | Independent Pi processes running in `tmux` |
| Plan Mode | Version-controlled `PLAN.md` files |
| Background Jobs | `tmux` sessions |
| Todo Management | Standard `TODO.md` files |
| Generic Popups | Scoped permission-gate extensions or container isolation |

This design replaces hidden harness state with **observable, standard artifacts and standard shell tools**. Markdown files persist across sessions, support git diffs, and remain human-readable. `tmux` exposes process outputs directly.

### 4. Custom Compaction as an Active Research Area

At [23:11](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1391s), Zechner notes that context compaction across all current agent harnesses remains suboptimal. Pi's extensibility serves as a research platform for experimenting with custom context retention policies.

### 5. Session Trees Prevent Context Loss During Exploration

At [24:59](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1499s), Pi's **tree-structured session history** allows developers to branch off exploration tasks, summarize findings, and return to main execution branches carrying only summary artifacts. This decouples exploration from execution without black-box subagents.

### 6. The Absence of Act 3 Distinguishes the Roles of the Two Talks

The complementary talk ends with Pi's technical origins, architecture, extensibility, and OSS gate. **World of Slop**, by contrast, adds a third act asking how such powerful and fast tools should be used with restraint.

```text
Complementary talk: What kind of harness did he build?
World of Slop: How should we live in the agent era, including with that harness?
```

Reading the talks together makes it clearer that Pi's minimalism is not merely a performance optimization. It is a sociotechnical design intended to **increase experimentation speed without surrendering human control and understanding.**

---

# Synthesis & Strategic Conclusions

## 23. The Central Tension: Self-Extending Agents vs Human Control

Reading the presentation purely as a tool overview introduces a seeming paradox:

- Pi enables agents to generate custom TypeScript extensions.
- Zechner insists humans must write critical code and retain decision authority.

This resolves by distinguishing **what gets automated** from **who owns intent**:

| Layer | Desirable Autonomy Level |
|---|---|
| Tool assembly, UI customization, boilerplate | High — Agents build extensions requested by humans |
| Exploration & execution paths | High — Within bounded task scopes |
| Product purpose & feature priorities | Retained by Humans |
| Architecture, APIs, & invariants | Retained by Humans |
| Critical code reviews & approvals | Retained by Humans |
| System liability & external actions | Retained by Humans |

Pi prioritizes **user sovereignty** over unconstrained agent autonomy.

---

## 24. Minimalism as Policy Decentralization

Pi does not prohibit plan modes, subagents, MCP, or permission gates. It shifts policy enforcement from core code into user space:

```text
Monolithic Agent Harness
Core = Features + Policy + UX + Security Assumptions + Context Strategy

Pi Architecture
Core = Stable Primitives
User Space = Features + Policy + UX + Security + Context Strategy
```

Trade-offs of policy decentralization:

- Core updates rarely break custom user workflows.
- Accommodates diverse security and enterprise requirements without forks.
- Reduces experimentation costs.
- Context window contains only actively used features.
- Agents assist in writing custom extensions.
- Requires users to manage security and extension quality.
- Potential for extension conflicts or unvetted code execution.

Pi is built as an **extensible substrate for developers who want direct control over their tooling and security models.**

---

## 25. The Four Pillars of Context Sovereignty

Effective context management requires four key properties:

### 25.1 Visibility
Full transparency into active system prompts, tool definitions, injected reminders, Skills, compaction history, and subagent contexts.

### 25.2 Stability
Consistent tool schemas and system prompt semantics across releases, ensuring reproducible workflows.

### 25.3 Malleability
User control over compaction algorithms, permission gates, tool definitions, and project-specific extensions.

### 25.4 Auditability
Complete traceability into what context the agent read, which tool calls failed, and how conclusions were formed.

---

## 26. Modularity as the Ultimate Agent Harness

Codebase architecture remains the most powerful harness component. Well-designed modules provide:

- Reduced retrieval search spaces
- Co-located domain concepts
- Explicit input and output boundaries
- Independent testability
- Enumerable side-effect scopes
- Objective evaluation functions

> [!important] Core Insight
> A codebase architecture that eliminates the need for 1M token contexts is superior to relying on 1M token context windows.

---

## 27. Preserving Friction as a Learning Mechanism

Eliminating all writing friction accelerates short-term code generation while halting long-term developer comprehension. Manual writing and reading build essential mental models:

- Identifying boundary contradictions
- Feeling API usability during writing
- Recognizing premature abstractions
- Uncovering hidden edge cases
- Anticipating production outage paths

Developer friction should be preserved selectively:

```text
Routine, Known Boilerplate → Accelerate with AI agents
Novel Concepts & Core Boundaries → Accept friction to build mental models
```

---

## 28. Strengths of the Talk

### 28.1 Product Philosophy Is Connected to Operational Experience

Pi's minimalism is not an abstract aesthetic. It comes from experience with changes to Claude Code, OpenCode's context handling, and real overload in OSS issue trackers.

### 28.2 It Accurately Identifies the Asymmetry Between Generation and Review

The central bottleneck in the AI era is not writing code, but judgment, verification, and responsibility. Those costs do not disappear as model performance improves.

### 28.3 It Frames Context as a Control Problem, Not Merely a Token Problem

One of the talk's strengths is that it unifies visible information, stable tools, user-defined compaction, and session observability as a single problem.

### 28.4 It Warns Against the Self-Referential Solution of “More Agents”

Continuing to cover the writer agent's problems with reviewer agents, memory agents, and search agents can increase complexity and cost without creating an independent source of truth.

### 28.5 It Provides Concrete Working Criteria After the Critique

Its criteria—scope, modularity, evaluation functions, non-core work, reproduction cases, rubber-ducking, and human finalization—can be applied immediately.

---

## 29. Limitations and Counterarguments

### 29.1 Strong Rhetoric Exceeds the Empirical Scope

Claims such as “90% of internet code is garbage,” “long context is a hack,” and “review agents do not work” are rhetorical devices emphasizing mechanisms. They should not be read as precise universal statistics.

### 29.2 Pi's Benchmarks Do Not Directly Prove Maintainability Claims

A sixth-place Terminal-Bench result shows that tool minimalism did not significantly impair task performance. It does not validate long-term codebase quality, incident rates, human comprehension, or security.

### 29.3 The Security Philosophy Is Biased Toward Expert Users

The critique that popups are security theater is valid, but making YOLO behavior the default is not appropriate for every user. Real organizations require least privilege, auditing, approval, and isolation.

### 29.4 Humans Also Fail to Understand Entire Systems

Human teams working on large software systems also make local decisions, omit documentation, lose organizational memory, and create enterprise complexity. The difference is not that humans are inherently superior, but that they participate in control loops involving learning, responsibility, pain, and production speed.

### 29.5 Well-Designed Independent Reviewers Can Add Value

Review performance can improve when a reviewer is separated from the authoring context and combines a clear rubric, deterministic tests, a different model family, and actual execution results. Zechner's real target is not reviewers themselves, but **infinite review systems that circulate the same incomplete assumptions.**

### 29.6 User Customizability Can Also Produce Complexity

If misused, Pi's extensibility can reproduce the same harness bloat it criticizes, only in user space. Continually adding extensions, skills, hooks, providers, and custom compaction can eventually create “my own Claude Code.”

Pi users therefore need the same restraint:

> Do not add features before observing a real failure that requires them, and keep every added extension removable.

---

## 30. Ten Propositions to Take Away from the Talk

1. **I must be able to see and change my own context.**
2. More harness features do not necessarily make models work better.
3. The purpose of a minimal core is not deprivation, but experimental freedom and stability.
4. Pi's self-modification is an observable loop in which an agent writes documented extensions.
5. Users have different security requirements, but extensibility itself is not security.
6. The low cost of AI generation can externalize review costs onto OSS maintainers.
7. Agents accumulate small errors without learning, faster than humans can review them.
8. A small module whose entire context fits into one task can be more powerful than a long context window.
9. Reviewer agents are supporting tools, not ground truth.
10. The final bottleneck in important systems must remain human understanding, taste, and responsibility.

---

## 31. Final Assessment

This is not an ordinary “AI coding tool comparison.” Pi's feature set is only the first case in the larger argument. What Zechner consistently defends is **agency**.

- In the critique of Claude Code, users must own their context.
- In Pi's design, users must be able to reshape the harness around their own workflows.
- In OSS governance, maintainers must control their own time and issue trackers.
- In the code-quality debate, humans must own product purpose and architectural judgment.
- In execution practice, generated volume must remain below human review capacity.

Summarizing the talk as “use Pi” therefore misses its point. A more accurate summary is:

> **Do not let tools control your workflow, and do not let agent speed outrun your judgment.**

Pi is a technical implementation of this philosophy.

```text
small core
+ visible context
+ deep extension API
+ fast iteration
= user control over tools
```

But this freedom does not automatically produce good software.

```text
bounded scope
+ modular architecture
+ external evaluation
+ exhaustive human review
+ direct ownership of important decisions
= discipline that keeps slop from becoming a product
```

Ultimately, Zechner is not asking us to return to the pre-AI era. **Use agents fully for repetition and exploration, but do not automate the human role of deciding what to build, which structures to accept, and what to trust.**

> [!quote] Final Message
> Slowing down does not mean using less AI.  
> It means **designing AI's speed back inside the boundaries of human understanding and responsibility.**

---

## 32. Timestamp Index

| Time | Topic |
|---:|---|
| [0:14](https://www.youtube.com/watch?v=RjfbvDXpFls&t=14s) | Introduction to the three-act tragedy |
| [0:29](https://www.youtube.com/watch?v=RjfbvDXpFls&t=29s) | Act 1 — Building Pi; first experiences with Claude Code |
| [1:56](https://www.youtube.com/watch?v=RjfbvDXpFls&t=116s) | “My context wasn't my context” |
| [2:34](https://www.youtube.com/watch?v=RjfbvDXpFls&t=154s) | Problems with observability, model choice, and extensibility |
| [3:36](https://www.youtube.com/watch?v=RjfbvDXpFls&t=216s) | Critique of OpenCode pruning, LSP, sessions, and CORS |
| [4:47](https://www.youtube.com/watch?v=RjfbvDXpFls&t=287s) | Terminal-Bench and Terminus 2 |
| [5:35](https://www.youtube.com/watch?v=RjfbvDXpFls&t=335s) | The answer: a malleable, self-modifying agent |
| [5:59](https://www.youtube.com/watch?v=RjfbvDXpFls&t=359s) | Pi's four packages |
| [6:21](https://www.youtube.com/watch?v=RjfbvDXpFls&t=381s) | Minimal system prompt |
| [6:37](https://www.youtube.com/watch?v=RjfbvDXpFls&t=397s) | Self-extension through documentation and examples |
| [6:57](https://www.youtube.com/watch?v=RjfbvDXpFls&t=417s) | The four tools: read, write, edit, and bash |
| [7:26](https://www.youtube.com/watch?v=RjfbvDXpFls&t=446s) | YOLO default and security philosophy |
| [8:02](https://www.youtube.com/watch?v=RjfbvDXpFls&t=482s) | TypeScript extension API |
| [9:06](https://www.youtube.com/watch?v=RjfbvDXpFls&t=546s) | Hot reload and extension examples |
| [10:25](https://www.youtube.com/watch?v=RjfbvDXpFls&t=625s) | Pi's sixth-place Terminal-Bench result and reclaiming control |
| [10:46](https://www.youtube.com/watch?v=RjfbvDXpFls&t=646s) | Act 2 — OSS in the age of clankers |
| [11:14](https://www.youtube.com/watch?v=RjfbvDXpFls&t=674s) | Automatic closure for new contributors and the human-voice filter |
| [11:40](https://www.youtube.com/watch?v=RjfbvDXpFls&t=700s) | Classification, embeddings, and OSS vacations |
| [12:02](https://www.youtube.com/watch?v=RjfbvDXpFls&t=722s) | Act 3 — Slow down |
| [12:56](https://www.youtube.com/watch?v=RjfbvDXpFls&t=776s) | The compounding-booboos model |
| [13:23](https://www.youtube.com/watch?v=RjfbvDXpFls&t=803s) | Review agents and Ouroboros |
| [13:31](https://www.youtube.com/watch?v=RjfbvDXpFls&t=811s) | Merchants of learned complexity |
| [14:19](https://www.youtube.com/watch?v=RjfbvDXpFls&t=859s) | “A sufficiently detailed spec is a program” |
| [14:41](https://www.youtube.com/watch?v=RjfbvDXpFls&t=881s) | Human learning, bottlenecks, and pain |
| [15:16](https://www.youtube.com/watch?v=RjfbvDXpFls&t=916s) | Why AGENTS.md and memory do not replace persistent learning |
| [15:24](https://www.youtube.com/watch?v=RjfbvDXpFls&t=924s) | Operational incompetence when people stop reading code |
| [15:44](https://www.youtube.com/watch?v=RjfbvDXpFls&t=944s) | Limits of long context and agentic search |
| [16:12](https://www.youtube.com/watch?v=RjfbvDXpFls&t=972s) | Good agent work: scope, modularity, and evaluation |
| [16:33](https://www.youtube.com/watch?v=RjfbvDXpFls&t=993s) | Non-core work, repetition, reproduction, and rubber-ducking |
| [16:58](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1018s) | Final advice: slow down and say “no” |
| [17:20](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1040s) | Generate only as much as can be reviewed |
| [17:26](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1046s) | Freedom for non-core code, exhaustive review for core code |
| [17:41](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1061s) | Write important things yourself and retain decision authority |
| [17:51](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1071s) | Friction produces system understanding and learning |
| [18:03](https://www.youtube.com/watch?v=RjfbvDXpFls&t=1083s) | Discipline, agency, and humans |

### Complementary Talk Timestamps

| Time | Additional or Expanded Topic |
|---:|---|
| [2:18](https://www.youtube.com/watch?v=Dli5slNaJu0&t=138s) | ChatGPT → Copilot → Aider → Claude Code lineage |
| [4:52](https://www.youtube.com/watch?v=Dli5slNaJu0&t=292s) | Claude Code's spaceship transformation and dark matter |
| [7:43](https://www.youtube.com/watch?v=Dli5slNaJu0&t=463s) | Volatility from hidden context injection |
| [9:40](https://www.youtube.com/watch?v=Dli5slNaJu0&t=580s) | Comparison of Codex, Amp, Factory Droid, and OpenCode |
| [11:42](https://www.youtube.com/watch?v=Dli5slNaJu0&t=702s) | Tool-result pruning and prompt-cache problems |
| [12:52](https://www.youtube.com/watch?v=Dli5slNaJu0&t=772s) | Problems with LSP feedback during edits |
| [14:13](https://www.youtube.com/watch?v=Dli5slNaJu0&t=853s) | Per-message JSON and server-security examples |
| [16:07](https://www.youtube.com/watch?v=Dli5slNaJu0&t=967s) | Terminal-Bench and the structure of Terminus |
| [18:15](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1095s) | Two theses: unfinished harnesses and malleability |
| [19:11](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1151s) | Pi's four packages |
| [20:02](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1202s) | Minimal system prompt |
| [20:27](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1227s) | YOLO, approval fatigue, and containerization |
| [21:17](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1277s) | Four tools and alternatives to features not built in |
| [22:18](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1338s) | Custom tools, UI, Skills, packages, and hot reload |
| [23:11](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1391s) | Custom compaction, providers, tool overrides, and SSH |
| [23:57](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1437s) | `/btw`, messenger, games, annotate, and file switcher |
| [24:59](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1499s) | Tree-structured sessions and observability features |
| [25:34](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1534s) | Pi's Terminal-Bench result |
| [25:54](https://www.youtube.com/watch?v=Dli5slNaJu0&t=1554s) | OSSification and human verification |

---

## 33. Sources

### Talks and Transcripts

- Mario Zechner, [Building pi in a World of Slop](https://www.youtube.com/watch?v=RjfbvDXpFls), AI Engineer, 2026-04-16.
- Mario Zechner, [I Hated Every Coding Agent, So I Built My Own — Mario Zechner (Pi)](https://www.youtube.com/watch?v=Dli5slNaJu0). Reviewed together with the complete user-provided timestamped transcript.
- [Full YouTLDR transcript](https://you-tldr.com/transcript/RjfbvDXpFls).
- [Full UseTranscribe transcript](https://www.usetranscribe.io/yt/RjfbvDXpFls/building-pi-coding-agent).
- [TalksIntel timestamped summary](https://talksintel.ai/ai-ml/conferences/aie-eu-2026/building-pi-in-a-world-of-slop-mario-zechner/).
- [Frontier Models talk description](https://frontiermodels.cc/video/building-pi-in-a-world-of-slop-mario-zechner/).

### Mario Zechner Primary Sources

- Mario Zechner, [What I learned building an opinionated and minimal coding agent](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/), 2025-11-30.
- Mario Zechner, [Thoughts on slowing the fuck down](https://mariozechner.at/posts/2026-03-25-thoughts-on-slowing-the-fuck-down/), 2026-03-25.

### Official Pi Sources

- [Official Pi site](https://pi.dev/).
- [Official Pi documentation](https://pi.dev/docs/latest).
- [Official Pi GitHub repository](https://github.com/earendil-works/pi-mono).
- [Pi Extensions documentation](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/docs/extensions.md).
- [Pi Skills documentation](https://github.com/earendil-works/pi-mono/blob/main/packages/coding-agent/docs/skills.md).
- [Pi CONTRIBUTING.md](https://github.com/earendil-works/pi-mono/blob/main/CONTRIBUTING.md).

> Web sources last verified: 2026-08-02.
