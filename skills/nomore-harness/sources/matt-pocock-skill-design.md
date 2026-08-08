---
title: "Summary of 'Building Great Agent Skills by Matt Pocock'"
date: 2026-07-12
type: research-note
tags:
  - AI
  - agents
  - skills
  - context-engineering
source:
  - "https://youtu.be/UNzCG3lw6O0"
related:
  - "[[2026-07-03_OpenAI_Codex-maxxing_for_long-running_work]]"
  - "[[2026-07-01_From_Prompts_to_Loop_Engineering]]"
---

# Summary of "Building Great Agent Skills" by Matt Pocock

## 1. Purpose of the Document

This document organizes and synthesizes Matt Pocock's presentation "Building Great Agent Skills" based on the original talk transcript. While preserving the speaker's original expressions and evaluation criteria as closely as possible, it transforms the content into a practical checklist for designing and auditing agent skills.

---

## 2. Problem Definition: Skill Hell

The speaker introduces **skill hell** as the next stage developers encounter after `tutorial hell` and `framework hell`.

Skill hell is not simply having too many skills. While there are countless skills available to download, modify, and combine for free, there is a lack of a common standard to determine the following:

- It is difficult to distinguish good skills from bad skills.
- It is difficult to understand how multiple skills operate together.
- When a skill fails to produce promised results, it is difficult to identify the root cause.
- There is no established method for converting an organization's operating procedures into skills that agents can reliably execute.

This problem occurs at both individual and organizational levels. The core missing piece is a **shared rubric** that allows one to inspect a skill and state: "This part works well, this part is bad, and this part needs improvement."

To address this, the speaker presents a skill checklist structured around four key axes:

> **Trigger → Structure → Steering → Pruning**

---

## 3. Trigger: How Skills Are Invoked

Every skill must first be deliberately designated as either user-invoked or model-invoked.

### 3.1 Model-invoked skill

The skill description enters the agent's context. When the model judges that a skill is needed based on its description, it reads `SKILL.md`.

In this setup, the description acts as a **context pointer** referencing the full skill.

- Advantage: Users do not need to memorize or explicitly specify the skill name.
- Cost: The description is included in every request, continuously consuming tokens and attention.
- Risk: Even if a skill is perfectly relevant, the model may fail to follow the context pointer.
- Operational burden: Evaluations (evals) are required to verify whether the skill fires at the correct moments.

As the number of model-invoked skills grows, the **context load** borne by the agent increases. For example, with 100 model-invoked skills, 100 descriptions reside permanently in the agent's context window.

### 3.2 User-invoked skill

The skill resides on the file system but remains invisible within the active agent context. The user explicitly triggers it via its skill name, a slash command, or a direct instruction.

- Advantage: Carries zero persistent context load, and invocation remains entirely predictable.
- Advantage: Eliminates the failure class where the model hesitates or fails to call a skill automatically.
- Cost: The user must remember which skills exist and when to use them.
- Outcome: Impose greater **cognitive load** on the human user.

The speaker personally prefers user-invoked skills to eliminate the unpredictability of automatic model invocation and maintain personal control. However, the takeaway is not to make every single skill user-invoked.

> Both model-invoked and user-invoked patterns carry distinct costs. For each skill, compare context load, cognitive load, and unpredictability to make a conscious design choice.

### 3.3 Trigger Checklist Questions

- Is this skill user-invoked, model-invoked, or both?
- Is this choice an intentional design decision rather than an unconsidered harness default?
- If model-invoked, is the permanent description cost justified?
- Are you actively running evals to measure missed invocations (false negatives) and over-invocations (false positives)?
- If user-invoked, is the cognitive load imposed on the user reasonable and manageable?

---

## 4. Structure: Steps and Reference

The speaker divides most skills into two primary structural building blocks:

| Component | Meaning |
|---|---|
| **Steps** | Sequential, step-by-step procedures that the skill follows |
| **Reference** | Supporting information such as definitions, templates, and examples that assist step execution |

Skills consisting entirely of reference material or simple steps-only workflows are also valid. What matters is distinguishing between the two so procedural workflows and domain knowledge do not become entangled.

### 4.1 The `two PRD` Example

The speaker's `two PRD` skill generates a PRD based on the current context.

Steps:

1. Locate relevant context in the repository.
2. Confirm test seams with the user. This step functions as a human-in-the-loop checkpoint to prevent strange testing architecture decisions.
3. Write the PRD.

Reference:

- Explanation and definition of test seams
- PRD Markdown template

When creating a skill from scratch, first establish the necessary steps, then identify the reference material required to execute each step.

### 4.2 Keep Main `SKILL.md` Files as Small as Possible

The third tip from the presentation is explicit:

> “We want to make the main `skill.md` file as small as possible.”

The benefits of a compact main file include:

- Easier ongoing maintenance.
- Simpler end-to-end reading and auditing.
- Less space for stale, contradictory, or redundant instructions to hide.
- Fewer tokens consumed per invocation.

A small skill file is not merely a stylistic preference; it is a strategic measure to reduce maintenance overhead and token context costs simultaneously.

### 4.3 Move Branching Reference Behind Context Pointers

Separating reference material into external files should be done purposefully rather than indiscriminately.

- If a reference is used in every single execution, keep it inside the main `SKILL.md`.
- If a reference is needed only for specific execution paths, move it to an external reference file.

Because `two PRD` requires the PRD template and test seam definitions during every run, it represents a single execution branch. Having both references in the main file is entirely justified.

In contrast, a `domain modeling` skill might contain multiple branching paths:

- Update the `context.md` glossary
- Write an ADR (Architecture Decision Record)
- Perform neither action

Because the glossary template and ADR template are not required for every run, they are placed into separate Markdown files. The main `SKILL.md` contains only a context pointer instructing the agent to read the corresponding file when that specific branch is selected.

> **Hide branching reference material behind context pointers.**

### 4.4 Structure Checklist Questions

- Are sequential steps and reference materials clearly separated?
- Does the skill follow a single execution path, or does it branch into multiple paths?
- Is the main file limited strictly to reference material required for all executions?
- Is branch-specific material hidden behind context pointers?
- Can `SKILL.md` be reduced further while fully preserving behavior and accuracy?

---

## 5. Steering: How to Direct Actual Agent Behavior

Steering addresses the problem where an instruction is written clearly in a skill, yet the agent fails to follow it. The primary technique highlighted by the speaker is **leading words**.

### 5.1 Leading Words

A leading word is an established domain term or short phrase that communicates extensive meaning in few tokens. When included in a skill, the agent reuses that terminology in its internal reasoning and output, steering its overall behavior in the desired direction.

A representative example from the talk is:

> **vertical slice**

When given a large coding task, AI agents tend to implement layer-by-layer across the entire codebase:

1. Entire database layer
2. Entire schema definition
3. Entire API endpoint layer
4. Entire frontend UI layer

This is the opposite of delivering thin, working end-to-end increments to gather early feedback. Rather than adding long prose paragraphs instructing the agent "do not build layer-by-layer," consistently use the term `vertical slice`, whose meaning is already well-established in software engineering.

A leading word is not a magical incantation used in isolation:

- Select an appropriate term capable of compressing significant operational context.
- Use the exact same expression consistently throughout the entire skill.
- Inspect the agent's reasoning trace to check whether it adopts phrases like "thin vertical slice".
- Verify whether the actual implementation plan and execution pattern change alongside phrase adoption.

The speaker summarizes this concept as follows:

> “English is a pretty wide API.”

An appropriate leading word functions like a concise function call, compressing multi-sentence behavioral instructions into a small token count.

### 5.2 Leg Work: Hiding Future Steps to Increase Effort on Current Steps

There are cases where an agent does not outright ignore instructions, but devotes insufficient effort to a specific phase. The speaker describes this as **not enough leg work**.

A classic example occurs in plan mode:

1. Ask clarifying questions.
2. Write the execution plan.

Because the agent sees that the ultimate goal is writing the plan, it asks only a couple of superficial questions before rushing straight to generating the plan.

To resolve this, the speaker split the workflow into separate skills rather than keeping it as a single plan mode:

- `grill with docs`: Dedicated strictly to asking clarifying questions and performing investigation
- `two PRD`: Dedicated to writing the PRD after investigation is complete

Although the overarching workflow contains two phases, the agent sees only one phase at a time.

> **Increase leg work by hiding the future goal and future steps.**

Not every step needs to be split into a separate skill. This structural technique is reserved for phases that are consistently underperformed and require focused attention.

### 5.3 Steering Checklist Questions

- Is there a strong, established leading word that compresses the intended behavior?
- Is the terminology used consistently without mixing alternative expressions for the same concept?
- Does the phrase actually appear in the agent's internal reasoning or execution plan?
- Is the agent merely repeating the phrase without actually changing its underlying execution behavior?
- Are there steps that repeatedly suffer from insufficient leg work?
- Does splitting the skill to hide future goals improve focus and thoroughness on the current step?

---

## 6. Pruning: Removing Ineffective Content

Massive, bloated skills are rarely the root cause themselves; they are symptoms of other underlying failure modes. The speaker focuses pruning efforts around duplication, sediment, and no-ops.

### 6.1 Duplication

Maintain a **single source of truth** for all information.

- Do not repeat identical templates across multiple files.
- Do not duplicate concept definitions between the main file and reference files.
- Do not re-explain the same procedure across multiple steps.
- Check for redundancies among separate reference files as well.

### 6.2 Sediment

Sediment refers to the accumulation of historical prose that occurs when multiple contributors add content to a shared Markdown file without removing or restructuring existing text.

When pruning a skill with heavy sediment, start by auditing its structure:

1. Verify whether added content is necessary for every execution branch.
2. If it is relevant only to a specific branch, move it to that branch.
3. If it is completely irrelevant, delete it entirely.
4. If the information is stale or outdated, remove it.

### 6.3 No-ops and the Deletion Test

A no-op is an instruction that appears meaningful on the surface but exerts zero actual influence on agent behavior within the current context.

For instance, if an implementation skill contains a paragraph instructing the agent to "write detailed, descriptive commit messages," but removing that paragraph leaves the generated commit messages completely unchanged, the instruction is a no-op.

The method for identifying no-ops is the **deletion test**:

> If this sentence or paragraph is deleted, does the agent's actual output or behavior change?

Skills generated by AI agents themselves are particularly prone to containing polite, thorough-sounding sentences that fail to alter real behavior. Building compact skills is not about randomly cutting meaningful instructions, but iteratively applying:

- The deletion test
- Compressing lengthy instructions into leading words
- Removing irrelevant details
- Clearing sediment or moving it to appropriate branches

### 6.4 Pruning Checklist Questions

- Is there a single source of truth for every piece of information?
- Are procedures, definitions, or templates duplicated across multiple locations?
- Has incident-specific sediment accumulated inside shared files?
- Does the skill contain stale instructions or details irrelevant to the current execution branch?
- Have you applied the deletion test to individual paragraphs and sentences?
- Are there no-ops present whose removal leaves execution results entirely unchanged?

---

## 7. Summary Framework

| Axis | Core Evaluation | Primary Technique |
|---|---|---|
| Trigger | Who invokes the skill and what cost is incurred? | Compare context load vs cognitive load; run invocation evals. |
| Structure | What must be read always vs what is read on demand? | Separate steps/reference; use branches and context pointers. |
| Steering | Does the instruction alter actual agent behavior? | Use leading words; monitor reasoning traces; increase leg work. |
| Pruning | Is there content that contributes nothing to actual results? | Maintain single source of truth; clear sediment; run deletion tests. |

The overall workflow of the presentation can be summarized in five steps:

1. **Trigger:** Determine how the skill is invoked and consciously balance context load against cognitive load.
2. **Structure:** Separate steps from reference material, and move branch-specific documentation outside `SKILL.md`.
3. **Steering:** Compress multi-sentence rules into leading words and check whether the agent adopts them in its reasoning trace.
4. **Leg work:** If a phase is consistently underperformed, hide future goals by splitting the workflow.
5. **Pruning:** Eliminate duplication, sediment, crud, and especially no-ops.

---

## 8. Misinterpretations to Avoid

Applying the presentation's principles mechanically can harm skill quality rather than improve it.

| Misinterpretation | Actual Intention of Original Text |
|---|---|
| Convert every skill into a user-invoked skill | Consciously weigh costs of both approaches to make deliberate choices |
| Move every reference into a separate file | Externalize only reference material required for specific branches |
| Shorter skills are unconditionally superior | Remove content that fails to contribute to actual execution behavior |
| Split every step into an independent skill | Hide future goals only when a step suffers from repeated lack of leg work |
| Having a leading word completes verification | Observe actual effects in reasoning traces and execution outputs |
| Delete all historical operational notes | Evaluate validity to categorize into common rules, branch references, or deletion targets |

The true criterion for evaluation is not file size alone:

> Is each piece of content loaded at the correct moment, does it alter actual execution behavior, and can its effect be observed?

---

## 9. Additional Commentary: Practical Application Patterns Observed in Repositories

> [!note] Source Distinction
> This section is not from Matt Pocock's original presentation, but an external commentator's additional observations from inspecting 29 skills and commit histories in the speaker's public repository. A distinction should be made between the speaker's direct claims and the commentator's interpretations.

Inspecting the repository to see how the checklist principles are applied in practice reveals clear operational patterns beyond individual techniques.

### 9.1 `grill-me`: A One-Sentence Invocation Button

Introduced as the most popular skill in the repository, `grill-me` instructs the agent to interview the user before drafting a plan. Its core text consists essentially of a single sentence:

> Run a grilling session.

Including frontmatter, it contains only around 20 words. It can remain this short because the rules required for the interview are not crammed into a single file:

- `grill-me` is a high-level user-invoked skill, incurring no permanent context load.
- The actual interviewing discipline resides in a lower-level `grilling` skill invoked by the model.
- The lower-level skill contains reusable rules such as "ask one question at a time" and "investigate discoverable codebase facts yourself, asking the user only for decisions."

Instead of forcing a single skill to be artificially short, **invocation and execution discipline are separated into distinct layers**.

### 9.2 Two-Layer Skill Architecture

The skill structure observed in the repository divides broadly into two tiers:

| Layer | Role | Characteristics |
|---|---|---|
| High-level workflow skill | Invocation buttons and user task flows | Extremely short with specific targets; orchestrates required lower-level skills |
| Low-level discipline skill | Reusable engineering discipline across workflows | Defines execution patterns and evaluation standards (e.g., `grilling`, TDD, domain modeling) |

Documentation or training workflows do not repeat discipline rules in their own text; they invoke lower-level skills like TDD or domain modeling. According to the commentary, dependency directions between layers are strictly controlled:

- High-level skills may invoke low-level discipline skills.
- High-level workflow skills do not invoke one another, avoiding complex tight coupling.
- Shared disciplines are defined exactly once inside low-level skills.

This is a **dependency rule ensuring a single source of truth and predictable composition**.

### 9.3 Dog-Fooding: Applying Taught Practices to the Repository Itself

The repository contains a `context.md` file, demonstrating how the glossary practices taught to users are applied directly to the skill repository itself:

- Defines core project terminology such as `issue tracker`.
- Documents prohibited synonyms that should not be substituted for key terms.
- Maintains decision records detailing how terms with ambiguous dual meanings (like `backlog`) were resolved.

This represents dog-fooding—applying domain modeling and glossary maintenance to one's own skill repository management. To maximize the impact of leading words, one must go beyond picking terms and **maintain consistent definitions and usage across the entire repository**.

### 9.4 Continuous Pruning Verified via Commit Logs

A dedicated directory for deprecated skills preserves records of how early skills were absorbed or replaced by refined architectures. Commit logs reflect routine pruning:

- Removing unnecessary remnants
- Deleting single obsolete paragraphs
- Eliminating duplicate definitions
- Consolidating existing skills into broader disciplines

Thus, the deletion test is a routine maintenance habit practiced continuously across repository commits. A high-quality skill kit is not a repository where new skills accumulate endlessly, but **a repository with documented records of consolidation, shortening, and deprecation**.

### 9.5 Leveraging Established Engineering Terminology Over New Concepts

Examining the skills together shows few entirely novel concepts. Most core elements are drawn from long-established software engineering practices:

- Narrowing requirements through structured interviews
- Writing tests before implementation (TDD)
- Establishing glossaries and bounded contexts
- Reviewing code against code smell checklists
- Refactoring in small, incremental units

These connect directly to classic concepts from *The Pragmatic Programmer*, Domain-Driven Design, TDD, and refactoring. Because models have encountered these terms repeatedly in pretraining datasets, choosing established, strong terms recruits broad behavioral patterns with minimal token expenditure rather than inventing custom instructional prose.

This observation forms a practical skill engineering loop:

1. Observe recurring agent failure modes.
2. Identify established engineering prescriptions that address the failure.
3. Compress the prescription into established terminology the model already understands.
4. Refine the instruction into a minimal skill or reusable discipline.
5. Verify behavioral changes in reasoning traces and actual output.
6. Continuously delete ineffective sentences and duplicate prose.

### 9.6 Operational Definition of Skills: Squeezing Predictability Out of Probabilistic Systems

The most critical insight regarding skill roles is summarized as follows:

> **A skill is a device for squeezing predictability out of a probabilistic system.**

Predictability here does not mean generating identical text every run, but **increasing consistency in working methodology**—consistently verifying requirements, gathering evidence, running tests, and reviewing output regardless of changing task details.

Applying this standard alters how external skills are evaluated:

- Is this skill merely a long prompt, or does it establish a repeatable working methodology?
- Does it leverage strong concepts the model already knows?
- Does it reuse shared disciplines, or duplicate identical prose across workflows?
- Is there observable evidence that it reduces real-world failure rates?
- Have duplicate instructions and no-ops been removed before adding a new skill?

When tempted to solve a problem by adding "just one more skill," the immediate need is not addition, but auditing existing skills to prune unnecessary content.

---

## 10. Conclusion

Escaping skill hell is neither about hoarding skills nor making them short for the sake of brevity. It requires a shared language to distinguish good skills from bad ones and guide continuous improvement.

The four pillars of this shared language are:

> **Trigger, Structure, Steering, Pruning**

Auditing skills across these four axes allows one to distinguish:

- Instructions that alter real behavior
- Reference materials that should be read on demand
- Triggers that introduce invocation ambiguity or unnecessary context costs
- Future goals that cause the agent to skip crucial current steps
- Sediment accumulated from past incidents
- No-ops whose deletion leaves output completely unchanged
- Misguided instructions that reinforce incorrect behavior

Treating the initial version of a skill as a testable hypothesis—iteratively verified through real-world execution and observable results—is the ultimate operational principle of this framework.
