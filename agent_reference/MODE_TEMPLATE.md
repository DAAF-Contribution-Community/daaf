# Mode Template

Use this template when adding a new engagement mode to the DAAF orchestrator. A mode defines a distinct workflow pattern triggered by a specific category of user request.

> **Comprehensive checklist:** The full registration-point checklist for modes (items M1-M21 plus lettered sub-items such as M1a and M7a, mandatory and conditional) is in `agent_reference/FRAMEWORK_INTEGRATION_CHECKLIST.md` § 3. The abbreviated checklist below covers the essential steps; use the comprehensive checklist for production-quality mode additions.

## Adding a New Mode: Abbreviated Checklist

### Mandatory (every new mode)

1. Create mode reference file at `.claude/skills/daaf-orchestrator/references/{mode-name}-mode.md` using the structure below
2. Update orchestrator `SKILL.md` (11 registration points):
   - [ ] YAML frontmatter `description` — update mode count
   - [ ] Expanded Orientation bullet — update mode count + add mode description
   - [ ] Engagement Mode Classification intro — update count word
   - [ ] Mode Decision Framework tree — add new branch
   - [ ] Mode Summary Table — add new row
   - [ ] Confirmation Templates by Mode — add a process-only template block: names the mode, restates the goal, previews the arc, checkpoints and kinds of output, names what the user referenced and where scope gets confirmed, and ends with a question. No scope estimates: nothing has been read yet (§ Mode Confirmation Gate)
   - [ ] Scope Check > Tiers — add a row with the mode's tier (Hard / Soft / None) and where the check happens (see item 8)
   - [ ] Scope Check > Read First staging list — add the mode to the right bullet: stage, then graduate on confirmation; no staging, the folder exists; or stage, never graduate unless the user escalates (see item 8)
   - [ ] Mode Escalation Paths — add rows (both FROM and TO the new mode)
   - [ ] Reference File Index — add new row
   - [ ] Documentation Loading Decision Tree — add new branch
3. Add mode-specific boundaries to `agent_reference/BOUNDARIES.md` > Mode-Specific Boundaries
4. Update `README.md` — mode count word + new table row
5. Update `user_reference/02_understanding_daaf.md`:
   - [ ] Section header — update count word
   - [ ] TOC entry — update to match header
   - [ ] Introductory paragraph — update count word
   - [ ] Add mode subsection (Trigger words, What it is, What you get, When to use, When NOT to use)
   - [ ] Mode transition table — add rows for escalation paths
6. Add mode-specific AI disclosure guidance to `agent_reference/AI_DISCLOSURE_REFERENCE.md`
7. Update session recovery in `.claude/skills/daaf-orchestrator/references/session-recovery.md`; hard-tier modes: add a session-recovery.md § Step 5c row naming a record with a status field (awaiting confirmation / confirmed), so a resumed session knows whether to re-present the Scope Check
8. Declare the mode's Scope Check tier and location: the row in `SKILL.md` § Scope Check > Tiers (item 2) and a `## Scope Check` section in the mode file right after `## User Orientation`. Decide its staging too (the Read First staging list, item 2, and the section's Staging bullet): whether a folder for the task exists when a material is read decides where read-first artifacts go. A hard-tier mode embeds the standard block (`SKILL.md` § Scope Check > Standard Block) in its first checkpoint's template, keeping that checkpoint's own fields

### Conditional

9. Add mode-specific error recovery to `agent_reference/ERROR_RECOVERY.md` (if mode has non-trivial error patterns)
10. Create mode-specific state template in `agent_reference/` (if different from Full Pipeline's STATE_TEMPLATE.md)
11. Update `CLAUDE.md` Reference Files table (if new template file created)
12. Update `CONTRIBUTING.md` (if mode affects contribution workflow)
13. Update `user_reference/07_faq_technical.md` (if mode is likely to generate FAQ questions)
14. Update `user_reference/04_extending_daaf.md` (if mode affects extension model)

---

## Mode Reference File Structure

```markdown
# [Mode Name] Mode

[1-2 sentence description of when this mode is used and what it produces.]

## User Orientation

The mode confirmation already gave the user this preview, so do not repeat it after confirmation. Present these points only when the user signals they are new to DAAF or asks for more detail.

- [What the mode does, in plain language]
- [What the user will receive]
- [How many checkpoints / what level of user interaction to expect]
- [Key constraint or characteristic (e.g., "read-only", "new version created")]

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Scope Check

- **Tier:** [Hard / Soft / None, with one line on why]
- **Where:** [the named checkpoint that carries it, with a pointer to its template; "—" for None]
- **Read first:** [what the orchestrator reads before proposing scope, and how it reaches subagents]
- **Staging:** [where read-first fetches, PDF ingests and a digest go, per `SKILL.md` § Scope Check > Read First: a folder for the task already exists when a material is read → write into it, additively, never touching an original's deliverables; none exists → stage in `{scratchpad}/scope_staging/` and graduate into the project on confirmation, or, for a mode that never creates a project, leave them staged unless the user escalates]
- **[Mode-specific carve-out, if any]:** [e.g., Data Onboarding keeps data files behind the sensitivity question]
- **On resume:** [Hard tier only: the record that shows the Scope Check as awaiting confirmation or confirmed (STATE.md, SESSION_NOTES.md or a mode report), and that a confirmed scope is not re-presented; mirror it in the session-recovery.md § Step 5c row (item 7)]

The read-first rule, the tier table and the standard block are in `SKILL.md` § Scope Check.

---

## [Mode Name] Workflow

[ASCII flowchart showing the stage sequence. Use the box-and-arrow style
consistent with other mode files (┌─┐, │, └─┘, ▼, ★ for checkpoints).
Show user checkpoints explicitly.]

---

## Subagent Invocation

[Dispatch logic: when the orchestrator responds directly vs. dispatches.
Which agents are used, what subagent types, what context to provide.
Include a Standard Agent Prompt Structure template if the mode has
a dedicated agent (like framework-engineer for Framework Development).

If the mode dispatches more than one subagent in a turn, add a wave
barrier discipline note: mid-wave completion notifications are status-only
— do not synthesize, advance the workflow, or present user checkpoints
until EVERY dispatched agent has returned. See `SKILL.md` § Subagent
Coordination > "Wave Barrier Discipline (Async Dispatch)" for the
canonical statement, and any existing mode reference for the standard
blockquote form.]

---

## Output Format

[Template or table of what the mode delivers to the user. If outputs
vary by request type, use a table mapping request types to outputs.]

---

## Boundaries

[Mode-specific constraints — Always Do / Ask First Before / Never Do.
Pointer to agent_reference/BOUNDARIES.md > [Mode Name] Mode.]

---

## Escalation Triggers

[Table of conditions, target modes, and actions. All escalations
require explicit user confirmation.]
```

### Required Design Decisions

When creating a new mode, explicitly document the following:

- **LEARNINGS.md behavior** — Does this mode create LEARNINGS.md? If yes, when (skeleton vs. full)? If no, document the exemption and where equivalent observations go. If the mode produces reusable insights, it should participate in the LEARNINGS.md lifecycle. Reference existing patterns: Full Pipeline (mandatory, gated at G4 and G12), Data Onboarding (mandatory, initialized at DI-2), Ad Hoc Collaboration (optional, only if reusable insights emerge), Reproducibility Verification (exempt — observations go in Reproduction Report).

### Optional Sections (include when applicable)

- **Orchestrator Skill Loading** — if the orchestrator loads skills directly (exception to standard pattern)
- **Workspace Setup** — if the mode creates or uses a workspace folder
- **Session Notes and Continuity** — if the mode uses SESSION_NOTES.md or a custom state mechanism
- **User Treatment** — if the mode has specific tone/treatment guidance (e.g., "treat as advanced")
- **Session Wrap-Up** — if the mode has a specific wrap-up protocol

---

## Exemplar Mode References

When creating a new mode, read 1-2 existing mode files as structural exemplars:

| Exemplar | Best for | Why |
|----------|----------|-----|
| `full-pipeline-mode.md` | Modes with formal stages, gates, and QA | Most comprehensive — PSU templates, gate definitions, invocation templates, error budgets |
| `data-onboarding-mode.md` | Modes with subagent dispatch and multi-phase profiling | Clear workflow diagram, detailed PSU templates, checkpoint-based user interaction |
| `ad-hoc-collaboration-mode.md` | Lightweight modes with flexible dispatch loops | SESSION_NOTES.md pattern, deferred workspace, direct skill loading exception |
| `framework-development-mode.md` | Modes with mandatory review passes and adaptive design | Adaptive Phase 2, mandatory multi-angle review, integration checklist pattern |

---

## Mode Design Principles

- Each mode should have a **clear, non-overlapping trigger condition** — test against all existing modes' triggers
- Mode workflows should be a **subset of or complement to** the Full Pipeline stages
- All modes require the **Mode Confirmation Protocol** before proceeding (HARD GATE; the only exceptions, session recovery and the User Support update-conflict flow, are listed in `SKILL.md` § Mode Confirmation Gate)
- All modes include a **User Orientation** section: an on-request expansion of the confirmation's preview, presented only when the user is new or asks for more
- Modes should **specify their outputs explicitly** — both the primary deliverable and any supporting artifacts
- **Boundary definitions** prevent mode scope from creeping into other modes' territory
- **Escalation paths** must be bidirectional where applicable (both FROM and TO the new mode)
- **Process preview at confirmation:** the confirmation template in SKILL.md previews how the mode works (its arc, its checkpoints and what each decides, the kinds of output) and names what the user referenced. It carries no scope estimates, because nothing has been read yet and a guessed scope anchors the user
- **Grounded scope after reading:** what exactly the mode will do is proposed at its Scope Check, after the user's materials are read. Choose the tier deliberately: Hard (a blocking first checkpoint) when the mode commits to substantial work; Soft (a non-blocking "here's my plan") for conversational or exploratory modes; None for single-answer modes
- Consider the mode's **session state mechanism** — does it need STATE.md, SESSION_NOTES.md, or a custom document?
- Consider the mode's **error recovery pattern** — what kinds of errors are likely and how should they be handled?

---

## Mode Naming Conventions

- Mode reference files: `{kebab-case-mode-name}-mode.md` (e.g., `framework-development-mode.md`)
- Mode names in prose: Title Case with spaces (e.g., "Framework Development")
- Mode names in tables: **Bold** Title Case (e.g., **Framework Development**)

---

## Post-Creation Verification

After completing the checklist, verify:

1. **Count consistency:** Grep for the old count word (e.g., "seven") across all framework files — should be zero occurrences
2. **Cross-references resolve:** Every file path mentioned in the new mode reference file exists
3. **Escalation paths are bidirectional:** Both the "from" and "to" modes in the escalation table acknowledge the path
4. **Confirmation template ends with a question:** The template in SKILL.md must name the mode and end with an explicit confirmation question in bold (the deploy smoke test T3.1 checks both in a live Data Lookup reply), and must carry no scope estimates
5. **Decision tree branch is correctly positioned:** More specific triggers appear earlier to prevent misclassification
