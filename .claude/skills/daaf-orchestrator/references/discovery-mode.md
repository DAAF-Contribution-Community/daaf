# Discovery Mode

Discovery mode is for answering "what data exists?" and "is this analysis feasible?" questions. It executes a subset of the Full Pipeline workflow (Stages 1-3 + synthesis) without producing Plans, code, or analysis artifacts.

## Discovery Workflow

```
Stage 1: Classify as Discovery Mode → Confirm with user
    ↓
Stage 2: Data Exploration
    ├─ Invoke domain explorer skill via subagent (Plan type, read-only)
    ├─ Identify available endpoints and variables
    └─ Flag variables needing source-specific deep dives
    ↓
Stage 3: Source Deep-Dive (if needed)
    ├─ Invoke domain source skill(s) via subagent(s) for flagged variables
    ├─ Understand limitations, caveats, suppression patterns
    └─ Document source-specific gotchas
    ↓
Findings Synthesis
    ├─ Consolidate findings into a clear summary
    ├─ Assess feasibility of potential analyses
    └─ Present to user with escalation option
```

**Stage 2-3 can run in parallel** when exploring multiple sources — dispatch one subagent per source following the Universal Prompt Requirements in `SKILL.md` and the invocation templates in `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md`. Use `Plan` subagent type (read-only is sufficient for exploration).

## Subagent Invocation

Discovery uses read-only subagents to explore data availability. Follow the Universal Prompt Requirements in `SKILL.md` and the invocation templates in `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md`, with these specifics:

- **Stage 2:** Subagent invokes the domain explorer skill (e.g., `education-data-explorer` for education domain)
- **Stage 3:** Subagent invokes domain source skill(s) (e.g., `education-data-source-ccd`) for deep dives on specific sources flagged in Stage 2
- **Skill lookup:** See `{SKILL_REFS}/skill-catalog.md` for the complete skill-to-source mapping
- **Subagent type:** `Plan` (read-only — no data downloads or code execution)

## Output Format

Present findings as a structured summary:

```
**Discovery Findings**

**Data Availability:**
- [Source 1]: [What's available, key variables, years covered]
- [Source 2]: [What's available, key variables, years covered]

**Feasibility Assessment:**
- [Can the user's question be answered with available data?]
- [Key limitations or caveats to be aware of]

**Recommended Next Steps:**
- [Specific suggestion — e.g., proceed to Full Pipeline, narrow scope, etc.]
```

## Boundaries

These boundaries supplement the universal boundaries in `CLAUDE.md` and `agent_reference/04_BOUNDARIES.md`.

**Always Do:**
- Focus on data availability and feasibility
- Provide clear findings summary
- Note when Full Pipeline escalation might be beneficial
- Document what was searched and what was found

**Never Do:**
- Create Plan files
- Generate analysis code or notebooks
- Invoke code-generation agents (research-executor, notebook-assembler, etc.)
- Execute data queries beyond metadata exploration
- Over-scope beyond what user asked

## Escalation to Full Pipeline

When findings suggest analysis is feasible and valuable, propose escalation:

> "Based on these findings, data is available for this analysis. Would you like me to proceed with Full Pipeline mode?"

Wait for explicit user confirmation before switching modes. If the user confirms, load `{SKILL_REFS}/full-pipeline.md` to begin the full workflow.
