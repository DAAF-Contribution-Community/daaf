# Agent Definition Template

> **Purpose:** Canonical template for authoring agent protocol files in the DAAF system.
> All agents in `.claude/agents/` MUST follow this structure. Sections marked REQUIRED cannot be omitted.
> Sections marked CONDITIONAL are required only for agents matching the stated criteria.
> Target length: **400-700 lines** (never exceed 1000).

---

## Template Specification

```markdown
---
# ── FRONTMATTER (REQUIRED) ──────────────────────────────────────────────
# Machine-readable metadata. `name` and `description` drive orchestrator routing.
name: agent-name-here
description: >
  [Third person. What it does AND when to use it.]
  Example: "Reviews executed scripts for correctness, methodology alignment,
  and data integrity. Invoked after each Stage 5-8 script execution."
tools: [Read, Write, Edit, Bash, Glob, Grep]   # Explicit allowlist. Omit for all.
permissionMode: default                          # Or: plan (read-only agents)
# ── Optional fields ──
# model: inherit          # sonnet | opus | haiku | inherit
# maxTurns: 50
# skills: skill-a          # Skill to preload (use YAML array [skill-a, skill-b] if multiple)
# memory: project          # user | project | local
# hooks:                   # Per-agent hook registration (scoped to this agent only)
#   PreToolUse:
#     - matcher: "Bash"
#       hooks:
#         - type: command
#           command: "$CLAUDE_PROJECT_DIR/.claude/hooks/hook-name.sh"
#           timeout: 5
---
```

### Section 1: Title and Purpose (REQUIRED)

```markdown
# [Agent Name] Agent

**Purpose:** [One sentence — what this agent does and why it exists in the system.]

**Invocation:** Via Agent tool with `subagent_type: "[agent-name]"`
```

**Guidelines:**
- Title uses `# ` H1 with agent name + "Agent" suffix
- Purpose is a single sentence, not a paragraph
- Invocation states the subagent_type used by the orchestrator

---

### Section 2: Identity and Philosophy (REQUIRED)

```markdown
## Identity

You are a **[Role Name]** — [one paragraph defining expertise, stance, and
operating philosophy. Written in second person ("You are..."). Should convey
the agent's worldview and default approach to ambiguity.]

**Philosophy:** "[Short memorable maxim — used as decision heuristic for
ambiguous situations. 5-15 words.]"

### Core Distinction

[Differentiate this agent from the 1-3 most similar agents in the system.
Use a comparison table or short paragraph. This prevents role confusion.]

| Aspect | This Agent | [Similar Agent] |
|--------|-----------|-----------------|
| Focus | [What this agent cares about] | [What the other cares about] |
| Timing | [When invoked] | [When the other is invoked] |
| Output | [What it produces] | [What the other produces] |
```

**Guidelines:**
- Philosophy maxim should be quotable and memorable (e.g., "Write first. Execute once. Capture everything.")
- Core Distinction table is REQUIRED — the multi-agent anti-pattern of overlapping responsibilities is the #1 failure mode in production systems
- Keep Identity to ~20 lines; deeper philosophical guidance goes in Core Behaviors

---

### Section 3: Upstream Inputs (REQUIRED)

```markdown
<upstream_input>

## Inputs

| Input | Source | Required | How Used |
|-------|--------|----------|----------|
| [Input 1] | Orchestrator Agent prompt | Yes | [Purpose] |
| [Input 2] | Prior stage output | Yes | [Purpose] |
| [Input 3] | Skill knowledge | No | [Purpose] |

**Context the orchestrator MUST provide:**
- [ ] [Specific item 1 — e.g., "Script path (absolute)"]
- [ ] [Specific item 2 — e.g., "Plan path (absolute)"]
- [ ] [Specific item 3 — e.g., "Research question (verbatim)"]

</upstream_input>
```

**Guidelines:**
- Use `<upstream_input>` tags for structural clarity
- Include a checklist of what the orchestrator must provide — this catches incomplete Agent prompts early
- Every input should state HOW it's used, not just that it exists

---

### Section 4: Core Behaviors (REQUIRED)

```markdown
## Core Behaviors

### 1. [Behavior Name]
[2-5 sentences describing this behavioral principle. Include concrete
guidance, not abstract platitudes.]

### 2. [Behavior Name]
[...]

### 3. [Behavior Name]
[...]
```

**Guidelines:**
- 3-7 numbered behavioral principles
- Each behavior is a principle, not a step (steps go in Protocol)
- Hit the "Goldilocks zone" — specific enough to guide, flexible enough to be heuristic
- Include concrete examples or bad/good comparisons where the behavior is non-obvious
- Domain-specific agents should include a methodology section here (e.g., data-planner's "Methodology Rigor Requirement")

---

### Section 5: Execution Protocol (REQUIRED)

```markdown
## Protocol

### Step 1: [Action Name]
[Specific instructions. Use appropriate degree of freedom:]
- **High freedom** (text): When multiple valid approaches exist
- **Medium freedom** (pseudocode): When a preferred pattern exists
- **Low freedom** (exact script): When the operation is fragile

### Step 2: [Action Name]
[...]

### Decision Points
[If/then guidance for branching logic. Use tables or decision trees:]

| Condition | Action |
|-----------|--------|
| [Condition A] | [Do X] |
| [Condition B] | [Do Y] |
```

**Guidelines:**
- Sequential steps for the main execution flow
- Decision trees or tables for branching logic
- Mark which steps are auto-execute vs. require orchestrator/user confirmation
- Reference external files rather than inlining large code blocks (progressive disclosure)
- For code-heavy protocols: provide ONE representative example inline, link the rest

---

### Section 6: Output Format (REQUIRED)

```markdown
## Output Format

Return findings in this structure:

## Summary
**Status:** [PASSED | ISSUES_FOUND | agent-specific vocabulary]
**Severity:** [BLOCKER | WARNING | INFO | None]
**[Agent-specific summary fields]**

## [Main Content Section]
[Agent-specific content organized by tables, checklists, or prose]

## Confidence Assessment
**Overall Confidence:** [HIGH | MEDIUM | LOW]

| Aspect | Confidence | Rationale |
|--------|------------|-----------|
| [Aspect 1] | [H/M/L] | [Why — evidence-based reasoning, not just label] |
| [Aspect 2] | [H/M/L] | [Why] |

**Confidence Levels:**
- **HIGH:** Evidence directly confirms correctness
- **MEDIUM:** Likely correct but some uncertainty; documented
- **LOW:** Significant uncertainty; resolution needed before proceeding

**If any aspect is LOW:**
- **Item:** [Which aspect]
- **Concern:** [What's uncertain]
- **Resolution needed:** [What would raise confidence]

## Issues Found
[If applicable — use severity levels: BLOCKER / WARNING / INFO]

## Learning Signal
**Learning Signal:** [Category] — [One-line insight] | "None"

Categories: Access | Data | Method | Perf | Process

| Category | When to Use | Example |
|----------|-------------|---------|
| **Access** | Data availability, mirrors, rate limits | "CCD mirror requires auth after 2026-02" |
| **Data** | Quality, suppression, distributions | "MEPS has 12% ambiguous school keys" |
| **Method** | Methodology edge cases, transforms | "District aggregation requires LEAID type filter" |
| **Perf** | Performance, memory, runtime | "Polars left_join on 200M rows needs 8GB" |
| **Process** | Execution patterns, error patterns | "Script versioning needed 2+ attempts 40% of the time" |

If nothing novel, emit "None" — this is the expected common case.

## Recommendations
- **Proceed?** [YES | NO - Revision Required | NO - Escalate]
- [If applicable: specific next actions]
```

**Guidelines:**
- Every agent MUST include: Status + Severity, Confidence Assessment, Learning Signal, Recommendations
- **Two-field status convention:** Status captures the outcome (PASSED, ISSUES_FOUND, or agent-specific vocabulary); Severity captures impact level (BLOCKER/WARNING/INFO/None). The orchestrator maps agent-specific status to gate decisions via the Gate Status Translation table in `.claude/skills/daaf-orchestrator/references/full-pipeline.md`.
- **Heading levels:** Output sections use `##` headings (Summary, Confidence Assessment, etc.) since the returned output is a standalone message. Add a `#` title heading at the top.
- Confidence model is STANDARDIZED across all agents (H/M/L with rationale)
- Learning Signal categories are STANDARDIZED (Access/Data/Method/Perf/Process)
- Agent-specific content goes in the middle sections
- Output should be parseable by the orchestrator without ambiguity

---

### Section 7: Downstream Consumers (REQUIRED)

```markdown
<downstream_consumer>

## Consumers

| Consumer | Receives | How They Use It |
|----------|----------|-----------------|
| Orchestrator | Status + Findings | Gate decision (proceed / revise / escalate) |
| [Next Agent] | [Specific fields] | [Specific purpose] |

**Severity-to-Action Mapping:**

| Your Status | Orchestrator Action |
|-------------|-------------------|
| PASSED | Proceed to next stage |
| WARNING | Log for Stage 10 aggregation; proceed |
| BLOCKER | Invoke revision flow (max 2 attempts) |

</downstream_consumer>
```

**Guidelines:**
- Use `<downstream_consumer>` tags for structural clarity
- Always include the orchestrator as a consumer
- Severity-to-action mapping makes the output contract explicit

---

### Section 8: Boundaries and Error Handling (REQUIRED)

```markdown
## Boundaries

### Always Do
- [Mandatory behavior 1 — no exceptions]
- [Mandatory behavior 2]

### Ask First Before
- [Action requiring approval 1]
- [Action requiring approval 2]

### Never Do
- [Hard stop 1 — absolute prohibition]
- [Hard stop 2]

### Autonomous Deviation Rules
You MAY deviate without asking for:
- **RULE 1:** [Category] — [What you can change and how to document it]
- **RULE 2:** [Category] — [What you can change and how to document it]

You MUST ask before:
- [Scope expansion, methodology changes, removing validation, etc.]

## STOP Conditions

Immediately stop and escalate when:

| Condition | Action |
|-----------|--------|
| [Condition 1] | STOP — [escalation description] |
| [Condition 2] | STOP — [escalation description] |

**STOP Format:**
**[AGENT NAME] STOP: [Condition]**

**What I Found:** [Description]
**Evidence:** [Specific data/code showing the problem]
**Impact:** [How this affects the analysis]
**Options:**
1. [Option with implications]
2. [Option with implications]
**Recommendation:** [Suggested path forward]

Awaiting guidance before proceeding.
```

**Guidelines:**
- Three-tier boundary system (Always/Ask/Never) is REQUIRED
- Autonomous Deviation Rules clarify what agents can fix independently
- STOP Conditions define circuit breakers — prevent runaway execution
- STOP format is STANDARDIZED across all agents
- Use "STOP Conditions" terminology consistently (not "When to Escalate", not "Escalation")

---

### Section 9: Anti-Patterns (REQUIRED)

```markdown
<anti_patterns>

## Anti-Patterns

| # | Anti-Pattern | Problem | Correct Approach |
|---|--------------|---------|------------------|
| 1 | [Pattern 1] | [Why it's wrong] | [What to do instead] |
| 2 | [Pattern 2] | [Why it's wrong] | [What to do instead] |

**Additional guidance:**

**DO NOT [specific prohibition].** [2-3 sentence explanation of why this is
harmful and what to do instead.]

**DO NOT [specific prohibition].** [...]

</anti_patterns>
```

**Guidelines:**
- Use `<anti_patterns>` tags for structural clarity
- ALWAYS include a 4-column table (# | Anti-Pattern | Problem | Correct Approach)
- Supplement with "DO NOT" paragraphs for nuanced anti-patterns that need explanation
- Minimum 5 anti-patterns per agent; maximum ~20
- Anti-patterns should be SPECIFIC to this agent, not generic programming advice

---

### Section 10: Quality and Completion (REQUIRED)

```markdown
## Quality Standards

**This [task] is COMPLETE when:**
1. [ ] [Measurable criterion 1]
2. [ ] [Measurable criterion 2]
3. [ ] [Measurable criterion 3]

**This [task] is INCOMPLETE if:**
- [Failure criterion 1]
- [Failure criterion 2]

### Self-Check

Before returning output, verify:

| # | Question | If NO |
|---|----------|-------|
| 1 | [Quality question 1] | [Remediation action] |
| 2 | [Quality question 2] | [Remediation action] |
| 3 | [Quality question 3] | [Remediation action] |
```

**Guidelines:**
- COMPLETE/INCOMPLETE duality makes quality bars explicit from both directions
- Self-check questions should be introspective ("Did I form my own understanding BEFORE checking the Plan?")
- Minimum 3 COMPLETE criteria, 3 INCOMPLETE criteria, 4 self-check questions

---

### Section 11: Invocation Pattern (REQUIRED)

```markdown
## Invocation

**Invocation type:** `subagent_type: "[agent-name]"`

The stage-specific invocation template with full context fields is in the relevant `agent_reference/WORKFLOW_PHASE[N]_[NAME].md` or mode reference file.
```

**Guidelines:**
- Specifies the `subagent_type` for quick reference
- References the relevant WORKFLOW_PHASE file or mode reference file for stage-specific context fields and invocation templates
- The invocation template must map to Upstream Inputs (Section 3)
- Do NOT duplicate the full Agent() call syntax here — that lives in the WORKFLOW_PHASE or mode reference files

---

### Section 12: References (CONDITIONAL — include when agent references external files)

```markdown
## References

Load on demand — do NOT read all at start:

| File | When to Read | Purpose |
|------|-------------|---------|
| `agent_reference/[file].md` | [Trigger condition] | [What it provides] |
| `agent_reference/[file].md` | [Trigger condition] | [What it provides] |
```

**Guidelines:**
- Progressive disclosure — reference, don't inline
- Keep references one level deep from the agent file
- State WHEN to read each reference (trigger condition), not just what it contains

---

## Section Order Summary

| # | Section | Required | Tag Wrapper |
|---|---------|----------|-------------|
| — | Frontmatter | REQUIRED | `---` YAML |
| 1 | Title and Purpose | REQUIRED | — |
| 2 | Identity and Philosophy | REQUIRED | — |
| 3 | Upstream Inputs | REQUIRED | `<upstream_input>` |
| 4 | Core Behaviors | REQUIRED | — |
| 5 | Execution Protocol | REQUIRED | — |
| 6 | Output Format | REQUIRED | — |
| 7 | Downstream Consumers | REQUIRED | `<downstream_consumer>` |
| 8 | Boundaries and Error Handling | REQUIRED | — |
| 9 | Anti-Patterns | REQUIRED | `<anti_patterns>` |
| 10 | Quality and Completion | REQUIRED | — |
| 11 | Invocation Pattern | REQUIRED | — |
| 12 | References | CONDITIONAL | — |

---

## Token Efficiency Rules

1. **Be deliberate about every token:** "Does the agent really need this? Would it genuinely improve stability/predictability/quality?"
2. **Minimize large inline code blocks.** If code is referenced by multiple agents, extract to a shared resource in `agent_reference/` and reference by path. If code is specific to a single agent, keep it inside the agent file.
3. **No duplicate content.** If guidance exists in `agent_reference/`, reference it — don't copy.
4. **One example per pattern.** Show ONE representative example; link additional examples.
5. **Descriptions, not dissertations.** Core Behaviors should be principles (2-5 sentences each), not essays.

## Standardized Elements (Cross-Agent Consistency)

These elements MUST be identical across all agents:

| Element | Standard |
|---------|----------|
| Confidence levels | HIGH / MEDIUM / LOW with mandatory rationale |
| Confidence aggregation | Overall = weakest component (weakest-link rule) |
| Learning Signal categories | Access / Data / Method / Perf / Process |
| Severity levels | BLOCKER / WARNING / INFO |
| STOP format | Standardized template (see Section 8) |
| Anti-pattern format | 4-column table (# | Anti-Pattern | Problem | Correct Approach) + DO NOT paragraphs |
| Terminology | "STOP Conditions" (not "Escalation", not "When to Escalate") |
| Path resolution | All paths absolute; BASE_DIR in every Agent prompt |
| Frontmatter description | Third person; includes what AND when |
| Per-agent hooks | Use `hooks` frontmatter for agent-scoped enforcement; see `agent-authoring` skill |
