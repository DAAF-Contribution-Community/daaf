# Targeted Assist Mode

Targeted Assist mode is for specific lookup questions — coded values, variable definitions, data source details, or quick factual answers. It invokes a single relevant skill and returns a direct answer.

## Targeted Assist Workflow

```
Stage 1: Classify as Targeted Assist → Confirm with user
    ↓
Identify the single most relevant skill for the question
    ↓
Invoke skill via subagent (Plan type, read-only)
    ↓
Return direct, focused answer to user
```

## Subagent Invocation

- Invoke **one** subagent with the relevant skill (e.g., `education-data-source-ccd` for a CCD variable question)
- Use `Plan` subagent type (read-only)
- The subagent loads the skill, finds the answer, and returns it
- If the skill doesn't contain the answer, report that clearly rather than guessing

Use the Data Source Quick Lookup table in `{SKILL_REFS}/skill-catalog.md` to identify the correct skill for the question.

## Response Format

Provide a direct, actionable answer:

```
**[Variable/concept name]**

[Direct answer to the question]

**Source:** [Which skill/data source this comes from]
```

Keep responses concise. The user asked a specific question — answer it specifically.

## Boundaries

These boundaries supplement the universal boundaries in `CLAUDE.md` and `agent_reference/04_BOUNDARIES.md`.

**Always Do:**
- Answer the specific question asked
- Keep response focused and concise
- Suggest Discovery Mode if broader exploration needed
- Provide direct, actionable information

**Never Do:**
- Execute multiple skills without confirmation
- Create Plan files or generate code
- Expand into full discovery without confirmation
- Assume Full Pipeline is needed from a single question

## Escalation Triggers

**To Discovery Mode** — when the question reveals broader data exploration is needed:
> "This question touches on broader data exploration. Would you like me to switch to Discovery Mode?"

**To Full Pipeline** — when the lookup reveals an actionable analysis opportunity:
> "This lookup suggests an interesting analysis could be done. Would you like me to explore this further?"

Wait for explicit user confirmation before switching modes.
