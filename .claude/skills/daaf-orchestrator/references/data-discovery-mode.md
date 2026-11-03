# Data Discovery Mode

Data Discovery mode is for answering "what data exists?" and "is this analysis feasible?" questions. It executes a subset of the Full Pipeline workflow (Stages 1-3 + synthesis) without producing Plans, code, or analysis artifacts.

## User Orientation

The mode confirmation already gave the user this preview, so do not repeat it after confirmation. Present these points only when the user signals they are new to DAAF or asks for more detail.

- Read-only exploration — no analysis code and no dataset downloads; web pages consulted, and any papers you pointed me to, are saved for provenance in a temporary staging folder, and nothing else is written
- If you pointed me to materials (a proposal, a variable list, a link), I read them first and tell you briefly how they shape what I explore
- Returns summary of available data and feasibility assessment
- Can escalate to full analysis if promising

**For more detail:** Consult `{BASE_DIR}/user_reference/02_understanding_daaf.md`.

---

## Scope Check

- **Tier:** Soft. A short statement, never a gate: the user's real decision point is the Findings Synthesis at the end.
- **When:** after mode confirmation, before dispatching the Stage 2 exploration, and only when the user referenced materials. Without them, go straight to Stage 2; the request alone sets the exploration.
- **Read first:** every material the user pointed to (a proposal, a variable list, a prior project, a URL), per `SKILL.md` § Scope Check > Read First. Data Discovery creates no project, so fetches, PDF ingests and any digest stay in the staging folder there; findings name a material by its title or URL, never by its staged path. If the user escalates to Full Pipeline, the staged materials move into the new project folder when its pre-flight is confirmed (§ Escalation to Full Pipeline).
- **What to say:** "Here's what I see in [materials]; here's my plan. I'm starting on it now — stop me if anything looks off." The plan names the sources or topics you will explore and how the materials changed them. Then dispatch in the same turn.
- **Hand the materials on:** list them in every Stage 2 dispatch's `USER-REFERENCED MATERIALS:` field (their staged absolute paths, so the subagent can read them, and any digest path, or "none"), and in Stage 3 dispatches when they bear on the source being examined, so subagents explore what the materials ask for rather than a guess from the request.

The tier definitions and the soft-check wording are in `SKILL.md` § Scope Check.

---

## Data Discovery Workflow

```
Stage 1: Classify as Data Discovery Mode → Confirm with user
    ↓
Read user-referenced materials, if any → soft Scope Check (§ Scope Check)
    ↓
Stage 2: Data Exploration
    ├─ Invoke domain explorer skill via subagent (search-agent; exploration only)
    ├─ Identify candidate datasets and variables
    └─ Flag variables needing source-specific deep dives
    ↓
Stage 3: Source Deep-Dive (if needed)
    ├─ Invoke domain source skill(s) via subagent(s) for flagged variables (source-researcher; read-only)
    ├─ Understand limitations, caveats, suppression patterns
    └─ Document source-specific gotchas
    ↓
Findings Synthesis
    ├─ Consolidate findings into a clear summary
    ├─ Assess feasibility of potential analyses
    └─ Present to user with escalation option
```

**Stages 2 and 3 can each run in parallel** when exploring multiple sources — dispatch one subagent per source: `search-agent` at Stage 2, `source-researcher` at Stage 3 (exploration only: no code execution or dataset downloads, per this mode's scope; § Subagent Invocation). Parallel dispatches follow the default of at most 5 subagents in flight (`SKILL.md` § Subagent Coordination > "Parallel Dispatch Guideline"), more only with the user's explicit approval.

> **Wave barrier discipline.** See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive. Treat mid-wave returns as status-only: do not begin the Multi-Source Synthesis Protocol below, present findings, or propose escalation until EVERY dispatched source subagent has returned. Synthesize once, over the complete set of returns — a source that returns early or fails still counts as a completion to fold into that single synthesis, not as a trigger to start summarizing before the rest arrive.

**Before dispatching subagents:** Read `{BASE_DIR}/agent_reference/WORKFLOW_PHASE1_DISCOVERY.md` for the detailed invocation templates (Stage 2: Domain Explorer, Stage 3: Source Deep-Dive). These templates specify the exact prompt structure, context fields, thoroughness directives, and output formats for each subagent type.

**Note:** Data Discovery mode does NOT require loading `agent_reference/BOUNDARIES.md`, or `full-pipeline-mode.md`. These contain execution-stage guidance (QA substages, code review patterns, git commit protocol) that is irrelevant to Data Discovery's read-only exploration.

## Subagent Invocation

Data Discovery dispatches `search-agent` at Stage 2 and `source-researcher` at Stage 3 to explore data availability; the mode's read-only scope binds each dispatch. Follow the invocation templates in `{BASE_DIR}/agent_reference/WORKFLOW_PHASE1_DISCOVERY.md`, with these specifics:

- **Stage 2 (`search-agent`, the Stage 2 template):** the subagent invokes the domain explorer skill (e.g., `education-data-explorer` for education domain); fill the template's `USER-REFERENCED MATERIALS:` field from § Scope Check. The agent can write its own records, but this mode's scope applies: no code execution, no dataset downloads, and no files written beyond `web_fetch.sh` fetch artifacts and, for a referenced PDF, the digest dispatch's ingest and record, all in the staging folder (§ Scope Check); findings come back as text
- **Stage 3 (`source-researcher`, the Stage 3 template):** the subagent invokes domain source skill(s) (e.g., `education-data-source-ccd`) for deep dives on specific sources flagged in Stage 2. `source-researcher` can write its own notes and run probe scripts, but the same mode scope binds it: the dispatch names no notes path and no `PROJECT_DIR`, adds "no probe scripts, no data downloads, no files written", and the report comes back as text
- **Skill lookup:** Review the skill inventory in the system message for the complete skill-to-source mapping
- **Fetch destination:** every `web_fetch.sh` call in this mode, the Stage 2 exploration fetches included, uses `{scratchpad}/scope_staging/web_fetches/` as DEST_DIR (absolute path, named in the dispatch), not an Ad Hoc workspace; the artifacts stay there unless the user escalates (§ Escalation to Full Pipeline; `web-retrieval` skill § Destination Conventions)
- **Records come back as text:** this mode has no project folder, so its Stage 2 and Stage 3 dispatches carry no `WRITE YOUR RECORD TO` or `WRITE YOUR NOTES TO` path (the templates' Full-Pipeline-only blocks are omitted) unless the user escalates to Full Pipeline

## Output Format

Present findings as a structured summary:

```
**Data Discovery Findings**

**Data Availability:**
- [Source 1]: [What's available, key variables, years covered]
- [Source 2]: [What's available, key variables, years covered]

**Feasibility Assessment:**
- [Can the user's question be answered with available data?]
- [Key limitations or caveats to be aware of]

**Recommended Next Steps:**
- [Specific suggestion — e.g., proceed to Full Pipeline, narrow scope, etc.]

**AI Disclosure Note:** This exploration was conducted using DAAF with [session model ID; and any specialist model IDs if subagents were dispatched] on [date].
DAAF version: [commit hash]. See `agent_reference/AI_DISCLOSURE_REFERENCE.md` for
disclosure guidance if incorporating these findings into published work.
```

**Turn-end briefing.** When presenting findings, follow DAAF's Turn-End Briefing standard: lead with the feasibility bottom line, order sources and caveats by how much they bear on the user's question, and reference any preliminary notes by path rather than reproducing them. See the master statement in `SKILL.md` § User-Facing Communication Standards > "Turn-End Briefing."

## Multi-Source Synthesis Protocol

When Data Discovery explores multiple data sources (multiple Stage 3 returns), the orchestrator consolidates findings directly (without dispatching the research-synthesizer agent). Follow this protocol:

1. **Merge structured outputs.** For each source-researcher return, extract: variables identified, temporal coverage, geographic coverage, key caveats, and coded values.
2. **Identify conflicts.** Flag cases where the same concept (e.g., "poverty rate") is measured differently across sources, or where temporal/geographic coverage doesn't align.
3. **Assess overall feasibility.** Based on merged findings: Can the user's question be answered with available data? What are the primary limitations? Which sources are essential vs. supplementary?
4. **Structure the synthesis** using the Output Format above, organizing by theme rather than by source.

**When NOT to synthesize here:** If findings reveal enough complexity to warrant formal analysis (multiple joins, derived measures, statistical modeling), propose escalation to Full Pipeline instead of attempting a comprehensive synthesis.

## Boundaries

These boundaries supplement the universal safety boundaries in `CLAUDE.md`. The detailed execution boundaries in `agent_reference/BOUNDARIES.md` (autonomous deviation rules, git commit protocol, STOP conditions) do not apply to Data Discovery mode's read-only exploration.

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

## Literature Review Handoffs

Both directions need the user's explicit confirmation (`SKILL.md` § Mode Escalation Paths):
- **To Literature Review:** when the user wants to know what published research has found ("what's known about …") before choosing data, propose it: "It sounds like you'd like to see what published research has found before choosing data. Literature Review mode is experimental: it works end to end and every reference and quote is still checked, but it has had limited real-world testing. Review its output more closely, and tell us what goes wrong. Want me to switch to Literature Review mode?" The conversation so far is the handoff (`literature-review-mode.md` § Escalation Triggers).
- **From Literature Review:** a review that finds a gap answerable with data hands over `output/LitReview_Handoff_v{N}.md` in its project folder: the question, the final deliverable's path, the gaps marked answerable with data, the reference list and the manifest pointer. Treat it as a user-referenced material (§ Scope Check) and explore the data for the gaps it lists. Take any fact about the literature only from the files `agent_reference/LIT_REVIEW_OUTPUT_CONTRACT.md` § Files Consumers May Read lists, never from the papers.

## Escalation to Full Pipeline

When findings suggest analysis is feasible and valuable, propose escalation:

> "Based on these findings, data is available for this analysis. Would you like me to proceed with Full Pipeline mode?"

Wait for explicit user confirmation before switching modes. If the user confirms, load `{SKILL_REFS}/full-pipeline-mode.md` to begin the full workflow. Its pre-flight Scope Check comes next; when the user confirms it, the project folder is created and any materials staged during this Data Discovery session move into it (`full-pipeline-mode.md` § Pre-Flight Checklist > On Confirmation (Gate G1)).
