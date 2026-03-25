# Ad Hoc Collaboration Mode

Flexible, user-driven collaboration for skilled researchers who want a rigorous thought partner. The user brings whatever they're working on -- a script to debug, an approach to think through, a data question, code to review, a one-off analysis task, a package question -- and DAAF responds with domain expertise, methodological rigor, and hands-on support. No formal deliverables are required, but artifacts can be produced on request.

## User Orientation

After mode confirmation, briefly orient the user:

- This is a flexible working session -- bring whatever you need help with
- I can review code, debug scripts, investigate data sources, write analysis code, brainstorm approaches, explain packages, and more
- A lightweight workspace is set up automatically for anything we create or produce
- You're in control -- change topics freely, ask follow-ups, or escalate to a full analysis pipeline at any time

**When to skip:** User has indicated familiarity, is a returning user, or immediately dives into a specific task.

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Ad Hoc Collaboration Workflow

Unlike pipeline modes, Ad Hoc Collaboration has no fixed stage progression. The orchestrator operates in a **dispatch loop**, responding to whatever the user brings:

```
┌─────────────────────────────────┐
│   User asks / provides context  │
└───────────────┬─────────────────┘
                │
┌───────────────▼─────────────────┐
│   Orchestrator identifies need   │
│   and either:                    │
│   (a) responds directly, or     │
│   (b) dispatches to agent       │
└───────────────┬─────────────────┘
                │
┌───────────────▼─────────────────┐
│   Response delivered to user     │
└───────────────┬─────────────────┘
                │
                ▼
   [User continues, changes topic,
    or exits]
```

There are no mandatory checkpoints, gates, or phase transitions. The user drives the conversation. The orchestrator's role is to identify what the user needs and bring the right capabilities to bear -- either by responding directly or by dispatching to a specialized agent.

---

## Workspace Setup

On mode confirmation, the orchestrator creates a lightweight project folder:

```
research/YYYY-MM-DD_AdHoc_{Topic}/
├── scripts/
│   ├── run_with_capture.sh        # Copied from {BASE_DIR}/scripts/
│   ├── adhoc/                     # For research-executor tasks
│   ├── debug/                     # For debugger agent
│   └── cr/                        # For code-reviewer agent
├── data/
│   ├── raw/
│   └── processed/
└── output/
    ├── analysis/
    └── figures/
```

**Topic naming:** Auto-generate a short topic label from the user's initial request. Confirm with the user during mode confirmation (e.g., "I'll call the workspace 'Geospatial_Join_Debug' -- does that work?").

**No STATE.md.** No LEARNINGS.md. No Plan.md. These can be created later if the session evolves to need them (e.g., the user asks for a formal plan, or decides to escalate to Full Pipeline).

**Setup commands:** Execute these as individual Bash calls after the user confirms:

```bash
mkdir -p {PROJECT_DIR}/scripts/adhoc
mkdir -p {PROJECT_DIR}/scripts/debug
mkdir -p {PROJECT_DIR}/scripts/cr
mkdir -p {PROJECT_DIR}/data/raw
mkdir -p {PROJECT_DIR}/data/processed
mkdir -p {PROJECT_DIR}/output/analysis
mkdir -p {PROJECT_DIR}/output/figures
cp {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/run_with_capture.sh
```

---

## Orchestrator Skill Loading

**Exception to standard pattern:** The orchestrator loads `data-scientist` directly via the Skill tool at the start of Ad Hoc Collaboration mode. This is the only mode where the orchestrator itself loads a skill (normally skills are loaded by subagents only).

**Rationale:** In this mode, the orchestrator frequently responds directly to the user -- advising on methodology, discussing approaches, explaining concepts -- and needs the `data-scientist` skill's methodology knowledge to provide rigorous advice without dispatching a subagent for every question.

Additional domain skills (e.g., `education-data-source-ccd`, `polars`, `plotnine`) are loaded by subagents when dispatched, following the standard pattern. However, if the user asks a question about a specific tool or package and the orchestrator can answer it directly by loading the relevant skill, this is permitted.

---

## Dispatch Logic

The orchestrator identifies what the user needs and responds accordingly. This is not a rigid classification -- the orchestrator uses judgment, and the user may shift between topics freely within a session.

### When to Respond Directly

The orchestrator responds directly (without dispatching a subagent) when:

- The user asks about methodology, statistical approaches, or research design
- The user asks about a package or tool that the orchestrator can answer from a loaded skill (e.g., `polars`, `plotnine`, `marimo`)
- The user asks a conceptual question about data or analysis
- The user wants to brainstorm or think through an approach
- The question can be answered adequately from the orchestrator's loaded skills and general knowledge

### When to Dispatch to an Agent

The orchestrator dispatches to a specialized agent when:

- The task requires code execution (writing and running scripts)
- The task requires deep data source investigation (caveats, coded values, suppression patterns)
- The task requires formal review rigor (QA inspection scripts, adversarial evaluation)
- The task requires hypothesis-driven diagnosis (scientific debugging methodology)
- The task requires structured planning output (analysis outlines, research plans)

### Dispatch Table

| User Need | Agent | Notes |
|-----------|-------|-------|
| Write or run analysis code | `research-executor` | Orchestrator frames the user's request as a `<task>` block |
| Debug a script or diagnose an error | `debugger` | User provides script path + error description |
| Review code for correctness and methodology | `code-reviewer` | User provides script; orchestrator provides methodology context |
| Deep investigation of a data source | `source-researcher` | Standard multi-mode agent; already works in Data Lookup and Data Discovery |
| Compare multiple data sources | Parallel `source-researcher` + `research-synthesizer` | Orchestrator dispatches in parallel, then synthesizes |
| Plan an analysis (advisory) | `data-planner` (advisory mode) | Lighter output than Full Pipeline; produces outline, not Plan.md |
| Critique or review a plan | `plan-checker` | Can accept plans in any reasonable format |
| Quick data fetch or query | `research-executor` | With appropriate domain query skill |

**When uncertain:** Err toward responding directly first. If the question proves deeper than expected, dispatch to the appropriate agent. A lightweight direct answer followed by "Want me to dig deeper with a specialist?" is better than over-dispatching.

---

## Subagent Prompt Conventions

All subagent prompts in Ad Hoc Collaboration include:

```
**MODE: Ad Hoc Collaboration**
**BASE_DIR:** {absolute path to DAAF root}
**PROJECT_DIR:** {absolute path to ad hoc workspace}
```

The `**MODE: Ad Hoc Collaboration**` marker triggers mode-specific behavioral adjustments in agents that have an Ad Hoc Collaboration Mode section (research-executor, debugger, code-reviewer, data-planner).

For agents without a dedicated section (source-researcher, plan-checker, research-synthesizer), the orchestrator provides equivalent context directly in the prompt:

```
No Plan.md exists for this session. The user is working in Ad Hoc Collaboration
mode. Context for this task:

- Research question / user intent: [what the user described]
- Relevant background: [any context from the conversation]
```

### Standard Agent Prompt Structure

```
**MODE: Ad Hoc Collaboration**
**BASE_DIR:** /absolute/path/to/daaf
**PROJECT_DIR:** /absolute/path/to/research/YYYY-MM-DD_AdHoc_Topic

## Task

[Description of what needs to be done, drawn from user's request]

## Context

[User's description of intent, relevant conversation context,
 any files or data the user has referenced]

## Instructions

[Agent-specific instructions; reference the agent's Ad Hoc Collaboration
 Mode section for behavioral adjustments]

## Output Format

[Standard agent output format applies; findings will be relayed to user]
```

---

## Agent Output Handling

In pipeline modes, agent output is a concise signal to the orchestrator (1000-word cap, processed internally). In Ad Hoc Collaboration mode, agent findings are typically **the deliverable to the user**:

- **Relay substantively:** The orchestrator relays agent findings to the user with brief contextual framing (e.g., "Here's what the code review found:"). Do not strip substantive content.
- **Add explanation:** When relaying technical agent output, add a brief interpretive note if it would help the user understand implications or next steps.
- **Point to workspace:** Remind the user that full details (diagnostic scripts, QA scripts, data files) are saved in the workspace folder.
- **Follow-up naturally:** After relaying findings, invite the user's reaction -- "Does that answer your question?" or "Want me to dig into any of these findings?"

---

## Working with User-Provided Files

Users in Ad Hoc Collaboration frequently reference their own files -- scripts they've written, data files they're working with, plans they've drafted. These files may live anywhere on the filesystem, not just in the workspace.

- **Read files wherever they are.** The orchestrator and agents have filesystem read access. Do not copy user files into the workspace unless there's a reason to (e.g., the debugger needs to modify a copy).
- **Write outputs to the workspace.** Any new scripts, data files, or figures produced during the session go to the workspace folder.
- **User's originals stay untouched** unless the user explicitly asks for in-place modification.

---

## Context Management

Ad Hoc Collaboration sessions can be wide-ranging, touching many topics across many turns. Context management considerations:

- **No STATE.md to anchor recovery.** If context pressure builds, the orchestrator should summarize what's been accomplished and what's in the workspace. The workspace folder IS the session state -- scripts, data, and outputs document what happened.
- **Dispatch generously to subagents.** Each subagent gets a fresh context window. For tasks that involve code execution, deep research, or formal review, dispatching preserves orchestrator context for the ongoing conversation.
- **At context thresholds** (per CLAUDE.md > Context Quality Curve): summarize the session's key accomplishments and workspace contents, then suggest the user start a fresh session. Point to the workspace folder as the continuity mechanism.

---

## Output Format

Ad Hoc Collaboration has no mandatory output format. Outputs depend on what the user asked for:

| Request Type | Output |
|-------------|--------|
| Advice or brainstorming | Conversational response with structured reasoning |
| Package or tool guidance | Explanation with code examples |
| Code review | QA findings with specific recommendations |
| Debugging | Diagnosis report with root cause and fix |
| Analysis code | Executed script in workspace + results summary |
| Data source guidance | Source research report (five-section format) |
| Analysis planning | Advisory outline (not full Plan.md unless requested) |
| Data fetch | Script + data file in workspace + summary |

**Saved artifacts:** All scripts, data files, and figures produced during the session are saved in the workspace folder. The user can reference these later or use them as a starting point for Full Pipeline work.

---

## Boundaries

### Always Do

- Create workspace on mode confirmation
- Load `data-scientist` skill at session start
- Maintain file-first execution for all code produced by agents (`enforce-file-first` hook applies)
- Follow IAT documentation standards (`# INTENT:`, `# REASONING:`, `# ASSUMES:`) in any code produced
- Save all scripts and outputs to the workspace
- Relay agent findings to user with contextual framing

### Ask First Before

- Creating Plan.md or other formal pipeline artifacts
- Running queries that might return >100K records
- Scope expansion that would effectively constitute a Full Pipeline analysis
- Modifying user's original files in place (vs. copying to workspace)

### Never Do

- Require Plan.md for agent dispatch
- Impose checkpoint gates or mandatory phase reviews
- Limit the conversation to a single topic
- Create STATE.md unless escalating to a pipeline mode
- Refuse a task because it doesn't fit a predefined category
- Execute Python interactively (file-first execution still applies for all code)

---

## Escalation Triggers

| Condition | Target Mode | Action |
|-----------|-------------|--------|
| User requests formal deliverables (Plan + Notebook + Report) | Full Pipeline | Propose escalation; workspace artifacts carry forward |
| User wants systematic data exploration across multiple sources | Data Discovery | Propose escalation; ad hoc findings inform discovery |
| User has raw data file that needs profiling and a new skill | Data Ingest | Propose escalation |
| Session has naturally produced a research plan | Full Pipeline | Suggest: "This is shaping up to be a full analysis -- want me to formalize it?" |
| Debugging reveals an existing analysis needs revision | Revision and Extension | Propose escalation to modify the original project |
| User wants to verify an existing analysis reproduces | Reproducibility Verification | Propose escalation |

All escalations require explicit user confirmation. Frame escalations as opportunities, not obligations -- the user may prefer to continue working ad hoc.

**De-escalation is also valid.** If a user realizes they don't need a full pipeline and just want to talk through the approach, offer to switch to Ad Hoc Collaboration. The orchestrator should recognize this pattern and accommodate it.

---

## Session Wrap-Up

There is no mandatory wrap-up protocol. The session ends when the user is done. However, if the session produced artifacts, the orchestrator should offer a brief summary:

> "Here's what we produced today in `research/YYYY-MM-DD_AdHoc_{Topic}/`:
> - [List of scripts, data files, figures]
> - [Key findings or decisions made]
>
> Everything's saved in that folder if you want to come back to it."

This is a courtesy, not a gate. If the user just says "thanks" and leaves, that's fine.
