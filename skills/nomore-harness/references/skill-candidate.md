# Skill Candidate Inspection

Apply every relevant check below to a proposed Skill.

## Invocation

- Validate frontmatter against the current local Pi Skill documentation.
- Check whether the description names the actual trigger branches without redundant synonyms.
- Confirm that model invocation is worth its always-visible description cost; otherwise prefer user invocation.
- Check likely false-positive and false-negative triggers.

## Structure and steering

- Confirm that the Skill establishes a repeatable working method rather than an unstructured long prompt.
- Keep common steps and reference needed by every branch in the main file; place genuinely branch-specific material behind precise relative pointers.
- Resolve every relative link and inspect any scripts, assets, or embedded instructions the Skill may cause the agent to use.
- Look for strong, established terms that compress demonstrated behavior; treat generic advice and instructions the model already follows as deletion-test candidates.
- Reward sequence splitting only when a particular step is observably rushed or underperformed, not because more structure appears safer.

## Overlap and removability

- Compare the Skill with Pi behavior, AGENTS.md, tool guidance, and installed Skills.
- Identify duplicated sources of truth, stale caches, speculative rules, and context that does not change behavior.
- Check executable scripts and any filesystem, shell, network, credential, or external-action implications rather than assuming an instruction-only package is harmless.
- Confirm that disabling or removing the Skill has a clear and bounded effect.
