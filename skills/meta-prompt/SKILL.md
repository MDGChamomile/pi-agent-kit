---
name: meta-prompt
description: Write and improve ready-to-use prompts.
disable-model-invocation: true
---

# Meta Prompt

Create the smallest complete prompt that achieves the user's intended outcome.

## Workflow

1. Infer the target model or surface, intended outcome, available inputs, required output, constraints, and completion criteria.
2. Ask one focused question only when a missing detail materially changes the prompt. Otherwise state a reasonable assumption briefly outside it.
3. Consult current official documentation only when model- or surface-specific behavior materially affects the result.
4. Write a directly usable, task-specific prompt. Include only applicable parts of this contract:
   - **Outcome:** completed result;
   - **Evidence:** inputs, sources, dates, and attribution;
   - **Boundaries:** approval requirements and non-goals;
   - **Verification:** observable completion checks.
5. For tool-using prompts, specify purpose, read/write boundary, invocation limits, trusted fields, failure handling, and result merging only where needed. Keep private inputs out of external documentation searches.
6. For coding prompts, require current-behavior inspection, the smallest compatible change, relevant regression verification, and reporting of checks that could not run. Do not imply authorization for deployment, merging, destructive actions, or secret changes.
7. Read the prompt back. Preserve every material fact, decision, exception, boundary, next action, and completion criterion; merge repeated meanings.

## Output

Unless the user requests critique, comparison, a diff, or variants, return one directly copyable fenced prompt. Add only essential assumptions or usage notes outside it.
