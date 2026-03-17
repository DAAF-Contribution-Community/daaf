# Invocation Templates Quick Reference

This file provides quick-reference pointers for constructing subagent invocation prompts. For the **complete, authoritative invocation templates**, read `agent_reference/03_SKILL_INVOCATIONS.md`.

## Common Invocation Patterns

### research-executor (Stages 5-8)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "research-executor" section
- **Agent protocol:** `agents/research-executor.md`
- **Subagent type:** `general-purpose`
- **Key context:** Include Plan task specification, file paths, skill name, verification criteria

### code-reviewer (QA after each script)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "code-reviewer (QA Agent)" section
- **Agent protocol:** `agents/code-reviewer.md`
- **Subagent type:** `general-purpose`
- **Key context:** Include script path, Plan expectations INLINED, QA thresholds, prior QA findings

### data-planner (Stage 4)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "data-planner" section
- **Agent protocol:** `agents/data-planner.md`
- **Subagent type:** `general-purpose`
- **Key context:** Include all Phase 1 findings, research question, Plan template path

### plan-checker (Stage 4.5)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "plan-checker" section
- **Agent protocol:** `agents/plan-checker.md`
- **Subagent type:** `Plan`
- **Key context:** Include Plan path, STATE.md path, LEARNINGS.md path

### source-researcher (Stage 3)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "source-researcher" section
- **Agent protocol:** `agents/source-researcher.md`
- **Subagent type:** `Plan`
- **Key context:** Include source name, flagged variables, domain source skill name

### research-synthesizer (Stage 3.5)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "research-synthesizer" section
- **Agent protocol:** `agents/research-synthesizer.md`
- **Subagent type:** `general-purpose`
- **Key context:** Include all Stage 2 and Stage 3 findings

### notebook-assembler (Stage 9)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "notebook-assembler" section
- **Agent protocol:** `agents/notebook-assembler.md`
- **Subagent type:** `general-purpose`
- **Key context:** Include script paths, execution log paths, output file path

### report-writer (Stage 11)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "report-writer" section
- **Agent protocol:** `agents/report-writer.md`
- **Subagent type:** `general-purpose`
- **Key context:** Include Plan path, notebook path, STATE.md, LEARNINGS.md, QA summary

### data-verifier (Stage 12)
- **Template location:** `agent_reference/03_SKILL_INVOCATIONS.md` → "data-verifier" section
- **Agent protocol:** `agents/data-verifier.md`
- **Subagent type:** `Plan`
- **Key context:** Include all artifact paths, original research question

## Path Resolution Reminder

All file paths in Agent prompts MUST be absolute. Include a `BASE_DIR` line in every prompt:
```
**BASE_DIR:** /absolute/path/to/project-root
All relative paths in referenced files resolve from BASE_DIR.
```
