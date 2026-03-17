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

### Example Invocation

```python
Agent({
    description: "Targeted Assist: [question summary]",
    prompt: """You are answering a specific data lookup question.

**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

## SKILL LOADING
Call the skill tool with name '[skill-name-from-catalog]'.

## QUESTION
{user's specific question}

## RESPONSE FORMAT
Provide a direct, concise answer. Include:
- The specific values, definitions, or information requested
- Source attribution (which skill/documentation provided the answer)
- Any important caveats or limitations
- Confidence level (HIGH/MEDIUM/LOW)

If the question cannot be fully answered from the available skill, say so clearly and suggest what additional exploration might help.""",
    subagent_type: "Plan"
})
```

## Response Format

Provide a direct, actionable answer:

```
**[Variable/concept name]**

[Direct answer to the question]

**Source:** [Which skill/data source this comes from]
```

Keep responses concise. The user asked a specific question — answer it specifically.

## Boundaries

These boundaries supplement the universal safety boundaries in `CLAUDE.md`. The detailed execution boundaries in `agent_reference/04_BOUNDARIES.md` do not apply to Targeted Assist mode (no code execution, no data transformations, no commits).

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
