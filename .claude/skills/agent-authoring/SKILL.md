---
name: agent-authoring
description: >
  Guide for creating new DAAF agent definition files with full ecosystem integration.
  Use when adding a new specialized agent, revising agent structure, or verifying
  agent integration completeness across documentation.
---

# Agent Authoring

Create new DAAF agents that conform to the canonical template and are fully wired into the system documentation for discoverability and usability.

## What This Skill Does

- Guides creation of agent `.md` files conforming to `agent_reference/AGENT_TEMPLATE.md` (12 mandatory sections)
- Ensures cross-agent consistency (standardized confidence model, Learning Signal, STOP format, etc.)
- Provides a **complete integration checklist** covering every file that references agents across the codebase to ensure it is discoverable and its invocation patterns are well-understood by the system agents
- Complements `skill-authoring`: this skill handles the behavioral protocol file; if the new agent also needs a companion skill, invoke `skill-authoring` separately

## Decision Tree: What Do You Need?

```
What are you doing?
│
├─ Creating a brand-new agent
│   └─ Follow "New Agent Workflow" below
│
├─ Revising an existing agent to match the template
│   └─ Read: references/template-walkthrough.md
│          + agent_reference/AGENT_TEMPLATE.md (the canonical blueprint)
│
├─ Checking if an agent is fully integrated into the ecosystem
│   └─ Read: references/integration-checklist.md
│
├─ Understanding what must be identical across all agents
│   └─ Read: references/cross-agent-standards.md
│
└─ Understanding the current agent landscape before adding to it
    └─ Read: agents/README.md (Agent Index + "Commonly Confused Pairs")
```

## New Agent Workflow

### Phase 1: Design (before writing)

Before beginning, you MUST have a clear, coherent, and compelling answer to each of the following questions:

1. **Define the role** in one sentence — what does this agent do and why does it exist?
2. **Identify pipeline stage(s)** — which stage(s) does it operate in, or is it "any/on-demand"?
3. **Identify similar agents** — read `agents/README.md` (Agent Index + "Commonly Confused Pairs") to find the 1-3 most similar existing agents. You MUST differentiate from these in your Core Distinction table.
4. **Determine subagent type:**
   - `general-purpose` — needs file writes, code execution, or tool access beyond reading
   - `Plan` — read-only validation, discovery, or verification
5. **Determine skill dependencies** — will this agent need to invoke any skills?

If any of these answers are vague, in doubt, or incomplete, the quality and reliability of the ensuing agent file will suffer. If the agent authoring process has been initiated by the user, make sure to ask these questions directly, and ask follow-up questions to enhance the quality of their responses as you go. Before proceeding to Phase 2, make sure the user agrees with your enhanced answers explicitly.

### Phase 2: Author (write the definition)

1. Read `agent_reference/AGENT_TEMPLATE.md` for the canonical 12-section structure
2. Read `references/template-walkthrough.md` for section-by-section guidance and common mistakes
3. Read `references/cross-agent-standards.md` for mandatory standardized elements
4. Write the agent file to `agents/[agent-name].md` following the template exactly
5. Run self-validation:
   - [ ] All 12 sections present (11 REQUIRED + 1 CONDITIONAL)
   - [ ] Core Distinction table differentiates from identified similar agents
   - [ ] Confidence Assessment uses standardized H/M/L model with rationale
   - [ ] Learning Signal uses standardized 5-category model
   - [ ] Anti-patterns in 4-column table format (# | Anti-Pattern | Problem | Correct Approach) (minimum 5)
   - [ ] STOP Conditions use standardized format
   - [ ] Invocation Pattern shows complete Task() syntax with BASE_DIR
   - [ ] COMPLETE criteria: minimum 3
   - [ ] INCOMPLETE criteria: minimum 3
   - [ ] Self-Check has minimum 4 questions
   - [ ] Total length 400-700 lines (flag if approaching 800+)
   - [ ] Large inline code blocks minimized (extract to `agent_reference/` only if shared across agents)

### Phase 3: Integrate (wire into the ecosystem)

1. Read `references/integration-checklist.md` for the COMPLETE list of files to update
2. Execute Tier 1 updates (MANDATORY for every new agent — 6 files)
3. Execute Tier 2 updates (CONDITIONAL — if agent maps to a specific stage)
4. Execute Tier 3 updates (CONDITIONAL — if agent affects specific workflow areas)
5. Update the agent count in `README.md` "Agent Ecosystem" header

### Phase 4: Validate (confirm completeness)

Run these verification checks:

```bash
# 1. Verify agent appears in all registry files
grep -l "agent-name" agents/README.md CLAUDE.md README.md

# 2. Cross-agent consistency (run for new agent file)
grep -c "HIGH.*MEDIUM.*LOW\|BLOCKER.*WARNING.*INFO\|Learning Signal\|STOP Conditions" agents/[agent-name].md

# 3. Verify agent count matches actual count
ls agents/*.md | grep -v README | grep -v _revised | wc -l
# Compare with the number in README.md "Agent Ecosystem (N Specialized Agents)"
```

### Phase 5: Human review

Before any agent authoring process is fully complete, a human user MUST review it for accuracy, intention, completeness, and value. When Phase 4 is complete, you MUST ask the user for review, providing as many details, file references, and decision points as possible to ensure full clarity for their awareness and revision if needed.

## Quick Reference: Current Agent Landscape

Consult `agents/README.md` for the authoritative Agent Index with:
- Agent name, purpose, subagent type, stage(s), and key distinction
- Commonly Confused Pairs (critical for writing your Core Distinction)
- Agent Coordination Matrix (producer/consumer relationships)
- Invocation patterns for every agent

## Reference Files

| File | When to Read | Purpose |
|------|-------------|---------|
| `references/template-walkthrough.md` | Writing or revising an agent | Section-by-section guidance for AGENT_TEMPLATE.md |
| `references/integration-checklist.md` | After writing, during Phase 3 | Complete list of files to update |
| `references/cross-agent-standards.md` | During writing, for consistency | Mandatory identical elements across all agents |

## Relationship to Other Skills and Resources

| Resource | Relationship |
|----------|-------------|
| `skill-authoring` skill | Invoke separately if the new agent also needs a companion skill |
| `agent_reference/AGENT_TEMPLATE.md` | The structural blueprint — read directly during Phase 2 |
| `agent_reference/PLAN_TEMPLATE.md` | Reference for wave-based task sequencing and plan structure |
| `agents/README.md` | The single source of truth for the agent landscape — read during Phase 1 |
| `data-ingest` agent | Related: creates new data source skills; agent-authoring creates new agents |

## Naming Convention

- **File:** `agents/[lowercase-hyphenated].md`
- **Frontmatter name:** `lowercase-hyphenated` (must match directory/file convention)
- **Title:** `# [Agent Name] Agent` (title case with "Agent" suffix)
- **Description:** Third person, includes WHAT the agent does AND WHEN to use it
