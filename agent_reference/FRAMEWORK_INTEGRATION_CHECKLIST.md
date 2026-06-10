# Framework Integration Checklist

> **Purpose:** Comprehensive registration-point checklists for every DAAF framework component type. Used by the `framework-engineer` agent and the orchestrator during Framework Development mode to ensure no wiring point is missed.
>
> **Canonical authority:** This document is the single authoritative integration checklist for all component types. Per-skill supplementary checklists (e.g., in `agent-authoring` or `MODE_TEMPLATE.md`) provide walkthrough detail and contextual guidance but should not be used as the primary checklist. When discrepancies exist, this document governs.
>
> **When to read:** Every framework-engineer invocation. Also useful for manual framework modifications.

---

## How to Use This Document

Each section covers one component type (Skill, Agent, Mode, Reference File, Hook). Items are marked:
- **[M]** = Mandatory (must be completed for every instance)
- **[C]** = Conditional (required only when the stated condition applies)

After completing each item, note the status: Done, Skipped (with reason), or N/A.

---

## 1. Adding or Modifying a Skill

### New Skill Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| S1 | Create skill directory `.claude/skills/{skill-name}/` | [M] | — | Directory name must exactly match `name` field in frontmatter |
| S2 | Create `SKILL.md` with valid YAML frontmatter (`name`, `description`) | [M] | `.claude/skills/{skill-name}/SKILL.md` | Frontmatter: `name` (lowercase-hyphen, 1-64 chars), `description` (1-1024 chars, what + when, third person) |
| S3 | Add `metadata` dict if applicable (`audience`, `domain`) | [C] | `.claude/skills/{skill-name}/SKILL.md` | Controlled vocabulary per `skill-authoring` skill |
| S4 | Create `references/` subdirectory with reference files | [C] | `.claude/skills/{skill-name}/references/` | Flat structure (no nesting). For data source skills: 3x+ SKILL.md lines |
| S5 | For data source skills: follow `DATA_SOURCE_SKILL_TEMPLATE.md` (13 sections) | [C] | `.claude/skills/{skill-name}/SKILL.md` | Mandatory sections in exact order; Truth Hierarchy blockquote; provenance metadata |
| S6 | Verify SKILL.md body is under 500 lines / 5000 words | [M] | `.claude/skills/{skill-name}/SKILL.md` | Extract overflow to `references/` |
| S7 | Verify description triggers appropriately (no undertriggering or overtriggering) | [M] | `.claude/skills/{skill-name}/SKILL.md` | Test with realistic prompts |
| S8 | If skill should be preloaded by an agent, add to that agent's `skills:` frontmatter | [C] | `.claude/agents/{agent-name}.md` | YAML frontmatter `skills` field |
| S9 | If skill is used in a specific pipeline stage, add to `full-pipeline-mode.md` > Skill-to-Stage Mapping | [C] | `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` | Skill-to-Stage Mapping table |
| S10 | If skill is used in WORKFLOW_PHASE invocation templates, add reference there | [C] | `agent_reference/WORKFLOW_PHASE*.md` | Stage-specific invocation template |

### Modifying an Existing Skill

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| SM1 | Read the full SKILL.md before editing | [M] | Target skill | Understand structure and content flow |
| SM2 | If changing the description, verify triggering behavior hasn't degraded | [M] | Target skill | Test with prompts that should and should not trigger |
| SM3 | If adding references, verify `references/` stays flat (no nested dirs) | [C] | Target skill | Directory structure |
| SM4 | If changing the name, rename the directory to match | [M] | Target skill | Directory name = frontmatter `name` |
| SM5 | Check if any agents preload this skill (search for skill name in `skills:` fields) | [C] | `.claude/agents/*.md` | Grep for skill name in agent frontmatter |
| SM6 | If changing routing or decision-tree content, find and synchronize files that restate the routing | [C] | `.claude/agents/*.md`, `.claude/skills/daaf-orchestrator/references/*.md` | Grep for library/skill names enumerated in the changed routing (duplicated summaries drift silently) |

---

## 2. Adding or Modifying an Agent

### New Agent Checklist

> For the complete section-by-section walkthrough, invoke the `agent-authoring` skill and read `references/integration-checklist.md`. This checklist covers registration points only.

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| A1 | Create agent file following AGENT_TEMPLATE.md (all 12 sections) | [M] | `.claude/agents/{agent-name}.md` | 400-700 lines target |
| A2 | Verify Core Distinction table differentiates from closest neighbors | [M] | `.claude/agents/{agent-name}.md` | Section 2: Identity |
| A3 | Add to Agent Index table | [M] | `.claude/agents/README.md` | Agent Index table |
| A4 | Add "When to Use" subsection | [M] | `.claude/agents/README.md` | When to Use section |
| A5 | Add to Agent Coordination Matrix (producer/consumer rows) | [M] | `.claude/agents/README.md` | Agent Coordination Matrix table |
| A6 | Add to Commonly Confused Pairs if applicable | [C] | `.claude/agents/README.md` | Commonly Confused Pairs table |
| A7 | Update Orchestration Flow diagram if agent participates in pipeline | [C] | `.claude/agents/README.md` | Orchestration Flow ASCII diagram |
| A8 | Add to Subagent Type Selection table in orchestrator SKILL.md | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Named Agents table |
| A9 | Add to `full-pipeline-mode.md` Core Workflow tables if stage-specific | [C] | `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` | Core Workflow, Handoffs, Stage Gates tables |
| A10 | Add invocation template to appropriate WORKFLOW_PHASE file | [C] | `agent_reference/WORKFLOW_PHASE*.md` | Stage-specific section |
| A11 | Add to BOUNDARIES.md if agent has unique boundary considerations | [C] | `agent_reference/BOUNDARIES.md` | Appropriate section |
| A12 | Add to ERROR_RECOVERY.md if agent has error recovery patterns | [C] | `agent_reference/ERROR_RECOVERY.md` | Agent-specific section or routing table |
| A13 | Register per-agent hooks in frontmatter if coding agent | [C] | `.claude/agents/{agent-name}.md` | YAML `hooks` field (e.g., enforce-file-first.sh) |
| A14 | Update root `README.md` Agent Ecosystem table and agent count (distinct from `.claude/agents/README.md`) | [M] | `README.md` (project root) | Agent Ecosystem section |
| A15 | Update CLAUDE.md if agent affects documented workflows | [C] | `CLAUDE.md` | Relevant section |
| A16 | Update `user_reference/` docs if agent is user-visible | [C] | `user_reference/*.md` | Relevant descriptions |

### Modifying an Existing Agent

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| AM1 | Read the full agent file before editing | [M] | Target agent | Understand structure |
| AM2 | Verify changes don't overlap with another agent's responsibilities | [M] | `.claude/agents/README.md` | Commonly Confused Pairs |
| AM3 | If changing the agent's scope, update README.md When to Use + Coordination Matrix | [C] | `.claude/agents/README.md` | Affected sections |
| AM4 | If changing inputs/outputs, update consumer/producer entries | [C] | `.claude/agents/README.md` | Agent Coordination Matrix |
| AM5 | If changing the name, update all references (SKILL.md, WORKFLOW_PHASE, etc.) | [M] | Multiple files | Grep for old name |

---

## 3. Adding or Modifying a Mode

### New Mode Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| M1 | Create mode reference file following MODE_TEMPLATE.md | [M] | `.claude/skills/daaf-orchestrator/references/{mode-name}-mode.md` | Required sections: description, User Orientation, Workflow, Subagent Invocation, Output Format, Boundaries, Escalation Triggers |
| M2 | Update YAML frontmatter description (mode count) | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Frontmatter `description` field |
| M3 | Update Expanded Orientation bullet (mode count + description) | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Welcome Preamble > Expanded Orientation |
| M4 | Update Engagement Mode Classification count word | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | "classify it into one of N engagement modes" |
| M5 | Add branch to Mode Decision Framework tree | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Decision Framework code block |
| M6 | Add row to Mode Summary Table | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Summary Table |
| M7 | Add confirmation template | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Confirmation Templates by Mode |
| M8 | Add escalation paths (from AND to new mode) | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Escalation Paths table |
| M9 | Add row to Reference File Index | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | What to Load Next > Reference File Index |
| M10 | Add branch to Documentation Loading Decision Tree | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Documentation Loading Decision Tree code block |
| M11 | Add mode-specific boundaries | [M] | `agent_reference/BOUNDARIES.md` | Mode-Specific Boundaries section |
| M12 | Update README.md mode count and table | [M] | `README.md` | Engagement Modes section |
| M13 | Add mode subsection to user_reference/02 | [M] | `user_reference/02_understanding_daaf.md` | The N Engagement Modes section (header, TOC, intro, subsection, transition table) |
| M14 | Add mode-specific AI disclosure guidance | [M] | `agent_reference/AI_DISCLOSURE_REFERENCE.md` | Mode-Specific Disclosure Guidance section |
| M15 | Update session-recovery.md with recovery pattern | [M] | `.claude/skills/daaf-orchestrator/references/session-recovery.md` | Purpose section + conditional recovery steps |
| M16 | Add mode-specific error recovery (if non-trivial) | [C] | `agent_reference/ERROR_RECOVERY.md` | Mode-specific recovery section |
| M17 | Create state template (if different from Full Pipeline) | [C] | `agent_reference/STATE_TEMPLATE_{MODE}.md` | New file + add to CLAUDE.md Reference Files table |
| M18 | Update CONTRIBUTING.md if mode affects contribution workflow | [C] | `CONTRIBUTING.md` | Relevant tier sections |
| M19 | Add FAQ entry if mode is likely to generate user questions | [C] | `user_reference/07_faq_technical.md` | New Q&A entry |
| M20 | Add progressive testing level entry | [C] | `user_reference/02_understanding_daaf.md` | Progressive testing levels section |
| M21 | Update user_reference/04 if mode affects extension model | [C] | `user_reference/04_extending_daaf.md` | Relevant section |

### Modifying an Existing Mode

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| MM1 | Read the full mode reference file before editing | [M] | Target mode | Understand workflow and structure |
| MM2 | If changing trigger conditions, verify no overlap with other modes | [M] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Decision Framework tree |
| MM3 | If changing outputs, update Mode Summary Table | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Summary Table |
| MM4 | If changing escalation paths, update both directions | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Mode Escalation Paths |
| MM5 | If changing boundaries, update BOUNDARIES.md | [C] | `agent_reference/BOUNDARIES.md` | Mode-Specific Boundaries |
| MM6 | If changing user-facing description, update user_reference/02 | [C] | `user_reference/02_understanding_daaf.md` | Mode subsection |

---

## 4. Adding or Modifying a Reference File

### New Reference File Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| R1 | Create file in `agent_reference/` with clear purpose statement | [M] | `agent_reference/{file-name}.md` | First paragraph states purpose and audience |
| R2 | Add to CLAUDE.md Reference Files table | [M] | `CLAUDE.md` | Reference Files table |
| R3 | Add trigger conditions ("When to Read") in all referencing documents | [M] | Various | Agent Section 12, WORKFLOW_PHASE files, orchestrator SKILL.md |
| R4 | Wire into Documentation Loading Decision Tree if loaded by orchestrator | [C] | `.claude/skills/daaf-orchestrator/SKILL.md` | Documentation Loading Decision Tree |
| R5 | Wire into agent Section 12 if used by specific agents | [C] | `.claude/agents/{agent-name}.md` | Section 12: References table |
| R6 | Wire into WORKFLOW_PHASE file if stage-specific | [C] | `agent_reference/WORKFLOW_PHASE*.md` | Progressive loading notes |

### Modifying an Existing Reference File

| # | Item | Req | File | What to Check |
|---|------|-----|------|----|
| RM1 | Read the full file before editing | [M] | Target file | Understand structure |
| RM2 | Check which agents and skills reference this file | [M] | Multiple | Grep for filename |
| RM3 | If changing the file's scope or purpose, update CLAUDE.md table description | [C] | `CLAUDE.md` | Reference Files table |
| RM4 | If renaming, update all references across codebase | [M] | Multiple | Grep for old name |

---

## 5. Adding or Modifying a Hook

> **Note:** Hook files in `.claude/hooks/` are protected by deny rules. This checklist documents the registration points for awareness. Actual hook creation requires human intervention or explicit permission override.

### New Hook Checklist

| # | Item | Req | File | Section / Location |
|---|------|-----|------|--------------------|
| H1 | Create hook script in `.claude/hooks/` | [M] | `.claude/hooks/{hook-name}.sh` | Must follow fail-closed design (ERR trap → exit 2) |
| H1b | Set executable permissions and ensure Git tracks the executable bit | [M] | `.claude/hooks/{hook-name}.sh` | Run `chmod +x <file>`, then `git update-index --chmod=+x <file>`. Verify with `git ls-files -s <file>` — mode must be `100755`, not `100644`. |
| H2 | Register in settings.json (project-wide) OR agent frontmatter (per-agent) | [M] | `.claude/settings.json` or `.claude/agents/{agent}.md` | `hooks` section with event type + matcher |
| H3 | Add to CLAUDE.md Defense-in-Depth Architecture table | [M] | `CLAUDE.md` | Defense-in-Depth Architecture table |
| H4 | Add to hooks registration summary in framework hierarchy docs | [C] | Documentation | Hook event type table |
| H5 | Test with both allow and block scenarios | [M] | — | Verify exit code 0 (allow) and exit code 2 (block) |

> **Applies to all `.sh` files, not just hooks.** Item H1b (executable permissions) applies whenever any `.sh` file is created or modified in the repository — including utility scripts in `scripts/` (e.g., `run_with_capture.sh`, `collect_session_logs.sh`). Shell scripts that are not executable will fail silently when invoked with `./script.sh` syntax and will be stored incorrectly in Git history. Always run `chmod +x` and `git update-index --chmod=+x` for every `.sh` file.

---

## 6. Cross-Cutting Consistency Checks

After completing any component checklist above, run these universal verification steps:

| # | Check | How |
|---|-------|-----|
| CC1 | Count words are consistent | Grep for "N engagement modes", "N agents", etc. across all files |
| CC2 | Cross-references resolve | Verify every file path mentioned in any document actually exists |
| CC3 | Table schemas match | New rows have the same columns as existing rows |
| CC4 | Escalation paths are bidirectional | Both "from" and "to" modes acknowledge each path |
| CC5 | Naming conventions are followed | Skill dirs match frontmatter names; agent files are lowercase-hyphenated; mode refs end in `-mode.md` |
| CC6 | No orphaned components | Every new file is referenced by at least one other file |
| CC7 | No stale references | If anything was renamed or removed, old names don't appear elsewhere |
