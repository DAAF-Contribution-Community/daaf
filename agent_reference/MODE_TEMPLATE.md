# Mode Template

Use this template when adding a new engagement mode to the DAAF orchestrator. A mode defines a distinct workflow pattern triggered by a specific category of user request.

## Adding a New Mode: Checklist

1. Create a mode reference file at `{BASE_DIR}/.claude/skills/daaf-orchestrator/references/[mode-name]-mode.md` using the structure below
2. Add a row to the Mode Summary Table in `SKILL.md` > Engagement Mode Classification
3. Add a branch to the Mode Decision Framework tree in `SKILL.md`
4. Add a row to the Reference File Index in `SKILL.md` > What to Load Next
5. Add mode-specific boundaries to `agent_reference/BOUNDARIES.md` > Mode-Specific Boundaries
6. If the mode uses escalation, add entries to the Mode Escalation Paths table in `SKILL.md`

## Mode Reference File Structure

```markdown
# [Mode Name] Mode

[1-2 sentence description of when this mode is used and what it produces.]

## [Mode Name] Workflow

[ASCII flowchart showing the stage sequence, similar to other mode files]

## Subagent Invocation

[Which agents are used, what subagent types, what context to provide]

## Output Format

[Template or example of what the mode delivers to the user]

## Boundaries

[Mode-specific constraints — what this mode does and does NOT do]
[Pointer to agent_reference/BOUNDARIES.md > [Mode Name] Mode]

## Escalation Triggers

[When to propose switching to a different mode, with explicit user confirmation]
```

## Mode Design Principles

- Each mode should have a clear, non-overlapping trigger condition
- Mode workflows should be a subset of or complement to the Full Pipeline stages
- All modes require the Mode Confirmation Protocol before proceeding
- Modes should specify their outputs explicitly
- Boundary definitions prevent mode scope from creeping into other modes' territory
