# Workflow Reference: Phase 1 — Discovery & Scoping

Stages 1, 2, 3, 3.5. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md` (loaded only for Full Pipeline mode; not needed for standalone Data Discovery mode).

> **Wave barrier discipline (async dispatch).** This phase contains the pipeline's heaviest parallel-dispatch surface: Stage 3 fans out one source-researcher per data source (by default up to 5 at once). See `SKILL.md` § Subagent Coordination > Wave Barrier Discipline (Async Dispatch) for how results arrive. The barrier applies however they arrive. Treat mid-wave returns as **status-only**: do not make gate decisions (G2, G3), revise the discovery scope, persist STATE.md conclusions, present a PSU checkpoint, or begin Stage 3.5 synthesis until EVERY member of the dispatched wave has returned. Synthesis (Stage 3.5) happens once, over the complete set of source-researcher returns — never incrementally per return. Interim narration to the user ("two of three source deep-dives have reported back") is fine; acting on partial results is not. An early return under context pressure, or a failed/skipped source-researcher, still counts as that member's completion — handle redelegation as part of whole-wave synthesis, not as an immediate mid-wave reaction.

---

## Stage 1: Initial Intake

**Executor:** Orchestrator (main context)
**Purpose:** Understand the user's request and classify engagement mode

### Actions

1. **Parse Request**
   - Identify key terms and objectives
   - Note any explicit constraints (years, geography, etc.)
   - Identify implied requirements

2. **Classify Mode**
   - Apply mode classification decision tree
   - Consider trigger keywords
   - Assess scope and complexity

3. **Confirm Mode**
   - State classification with reasoning
   - Preview the process (the mode's arc, checkpoints, kinds of output) and name every material the user referenced — no scope estimates, because nothing has been read yet (`SKILL.md` § Mode Confirmation Gate)
   - Await EXPLICIT user confirmation

4. **Read Referenced Materials (after confirmation)**
   - Read what the user pointed to (papers, documents, prior analyses, URLs) per `SKILL.md` § Scope Check > Read First, or have one search-agent digest it (always for a PDF). No project exists yet, so fetches, PDF ingests and any digest are staged in the session scratchpad's `scope_staging/` folder
   - Scope is proposed after this read, never before: at the pre-flight Scope Check in Full Pipeline, in the soft Scope Check in Data Discovery (`data-discovery-mode.md` § Scope Check)
   - Full Pipeline: when the user confirms the pre-flight, the project folder is created and the staged materials move into it (`full-pipeline-mode.md` § Pre-Flight Checklist > On Confirmation (Gate G1)); their paths in the project fill the Stage 2 and Stage 3 `USER-REFERENCED MATERIALS:` fields
   - Data Discovery: there is no project, so the staged materials stay where they are; the fields carry their staged absolute paths so the subagent can read them, and findings name them by title or URL

5. **Ask Clarifying Questions (if needed)**
   - Ambiguous scope
   - Missing constraints
   - Multiple interpretations possible

### Output

- Confirmed engagement mode
- Research question formulation
- Any clarifications received
- User-referenced materials (paths and any digest path), or "none"

### Gate Criteria (G1)

In Full Pipeline, Gate G1 is **the pre-flight Scope Check confirmed** (which includes mode confirmation), as in `full-pipeline-mode.md` § Stage Gates. Data Discovery has no pre-flight, so there the first item is the mode confirmation alone.

- [ ] Pre-flight Scope Check confirmed by the user (Full Pipeline; Data Discovery: mode confirmed)
- [ ] Research question clearly stated
- [ ] Any clarifications documented
- [ ] User-referenced materials read and listed for Stage 2 (or none referenced)
- [ ] Full Pipeline: project folder created on that confirmation, staged materials moved into it, confirmed pre-flight recorded (`full-pipeline-mode.md` § Pre-Flight Checklist > On Confirmation (Gate G1))

> **Full Pipeline Only:** The Pre-Flight Checklist is Full Pipeline's Scope Check, defined in `full-pipeline-mode.md` § Pre-Flight Checklist. The referenced materials are read before it, and it is presented *before* this file is loaded. By the time the orchestrator reads this file, the user has confirmed the pre-flight and the project folder exists, so the Stage 2, 3 and 3.5 records below write into it and Stage 4 reuses it. Data Discovery mode does not use the Pre-Flight Checklist and has no project: its Stage 2 and Stage 3 records come back as text, with no `WRITE YOUR RECORD TO` or `WRITE YOUR NOTES TO` path, unless the user escalates to Full Pipeline (`data-discovery-mode.md` § Subagent Invocation).

---

## Stage 2: Data Exploration

**Executor:** Subagent (search-agent)
**Skill:** Domain explorer skill (e.g., `education-data-explorer`)
**Purpose:** Identify available data sources and variables

### Actions

1. **Determine Data Level**
   - Schools (K-12 individual schools)
   - School districts (LEAs)
   - College/university (postsecondary)

2. **Route to Canonical Datasets**
   - Consult the explorer routing references (for education: `schools-datasets.md`, `districts-datasets.md`, `colleges-datasets.md`)
   - Identify relevant sources and their canonical dataset identifiers — the identifier the domain's retrieval skill consumes (for education: the canonical mirror path, `{source}/{filename}`)
   - Check year coverage against the source's pinned vintage (for education: the pinned mirror vintage)

3. **Identify Variables**
   - List variables relevant to research question (real column names, verified against the domain's variable reference — for education: `variable-dictionary-{source}.md`)
   - Note data types
   - Flag variables needing deep-dive

4. **Document Limitations**
   - What couldn't be found
   - Data gaps
   - Coverage limitations

### Thoroughness Directive

```
- Search ALL relevant data levels
- Consider multiple potential data sources
- Flag ALL variables that might need deeper investigation
- Check year coverage against research question needs
- Include 'Limitations Encountered' section
```

### Invocation Template: Domain Explorer Skill

**Purpose:** Identify available datasets and variables
**Subagent:** search-agent
**Skills:** `data-scientist`, `{domain_explorer_skill}`

> **Domain extensibility:** The orchestrator resolves the explorer skill name based on the active domain (from the data sources in the confirmed pre-flight scope; no Plan exists yet, and the Plan records the domain later in its Domain Configuration) and provides it in the Agent prompt. The example below uses `education-data-explorer` as the demonstration domain default.

```python
Agent({
    description: "Stage 2: Data Exploration",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

You have access to a skill tool. First, call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '{domain_explorer_skill}'.  # e.g., 'education-data-explorer'

**ORIGINAL REQUEST (for context):**
> {original_user_request_verbatim}

**RESEARCH QUESTION:**
{research_question}

**CONSTRAINTS:**
- Years of interest: {years}
- Geographic scope: {geography}
- Population: {population}

**USER-REFERENCED MATERIALS:**
{absolute path of each material the user pointed to, plus any digest path (Full Pipeline: their paths in the project folder; Data Discovery: their staged paths), each with one line on what it says about data, variables, years or definitions — or "none"}
Read these (or the digest) before searching. Where they name data sources,
variables, years or definitions, check those first and say whether the data
supports them.

**WRITE YOUR RECORD TO:** {project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md
Write the full findings there in the OUTPUT FORMAT below, then return a summary
with the path (your agent protocol, Core Behavior 7). Full pipeline mode only;
outside it, omit this block and return the full findings as text.

**THOROUGHNESS DIRECTIVE:**
- Search ALL relevant data levels (schools, districts, colleges as appropriate)
- Consider multiple potential data sources before recommending
- Flag ALL variables that might need deeper source-specific investigation
- Check year coverage against research question needs
- Include a 'Limitations Encountered' section in your output
- Be explicit about what you searched and what you found

**OUTPUT FORMAT:**
Write the findings (or, outside full pipeline mode, return them) in this structure:

### 1. Recommended Data Level
[schools | school-districts | college-university] with rationale

### 2. Candidate Datasets
*Dataset Identifier = the canonical identifier the domain's retrieval skill consumes (for education data: the canonical mirror path, e.g. `ccd/schools_ccd_directory`).*
| Dataset Identifier | Source | Grain | Description | Years Available |
|--------------------|--------|-------|-------------|-----------------|

### 3. Key Variables
| Variable | Dataset Identifier | Type | Description |
|----------|--------------------|------|-------------|

### 4. Variables Flagged for Deep-Dive
| Variable | Reason for Deep-Dive |
|----------|---------------------|

### 5. Limitations Encountered
| Limitation | Impact | Recommended Resolution |
|------------|--------|------------------------|

### 6. Completeness Assessment
- [ ] Schools level searched: [Yes/No/NA]
- [ ] Districts level searched: [Yes/No/NA]
- [ ] Colleges level searched: [Yes/No/NA]
- [ ] Multiple sources considered: [list sources checked]

### 7. Confidence Assessment
| Finding | Confidence | Rationale |
|---------|------------|-----------|
| [key finding] | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After loading both skills and searching, write the findings in the format
above to the path named, then return the summary (outside full pipeline mode,
return the findings in full).""",
    subagent_type: "search-agent"
})
```

### Output Format

The Stage 2 output format is the **OUTPUT FORMAT** block in the invocation template above: sections 1-7, ending with the Confidence Assessment. It is the only Stage 2 format, and it is the one the gate condition below checks.

### Preliminary Notes Persistence: Stage 2

For full pipeline mode only, the dispatch names the notes path and search-agent writes the file itself:

| Agent | Writes To |
|-------------|----------|
| search-agent (Stage 2) | `{project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md` |

The orchestrator persists a return itself (full and unmodified, with the provenance header, per `SKILL.md` § Subagent Return Processing steps 2a-2c) only when it came back inline: the agent reports a failed write or a rejected name, or the dispatch named no path.

**Gate condition:** Stage 2 preliminary notes must exist on disk before dispatching Stage 3 (source-researcher). The orchestrator confirms the file exists at the named path and holds every section (1-7) of the dispatch's OUTPUT FORMAT (step 2's carve-out in `SKILL.md` § Subagent Return Processing).

### Gate Criteria (G2)

- [ ] At least one candidate dataset identified (canonical dataset identifier)
- [ ] Key variables identified
- [ ] Variables for deep-dive flagged
- [ ] Year coverage verified
- [ ] search-agent notes on disk at the named path (full pipeline mode only)
- [ ] **If no data found:** STOP, escalate to user

---

## Stage 3: Source Deep-Dive

**Executor:** Subagent (source-researcher)
**Skills:** `*-data-source-*` (one per source)
**Purpose:** Understand source-specific limitations and caveats

### Actions

1. **Load Source Skill**
   - Identify which `*-data-source-*` skill(s) to load
   - One invocation per source
   - **Parallel cap:** If >5 sources identified, sub-batch source-researcher dispatch into groups of ≤5 (the default parallel dispatch limit in the orchestrator SKILL.md § Subagent Coordination > "Parallel Dispatch Guideline"; a larger batch only with the user's explicit approval)

2. **Extract Caveats**
   - Source-specific limitations
   - Population definitions
   - Data collection methodology

3. **Document Coded Values**
   - Domain-specific coded values (from the source's data-source skill; e.g., -1, -2, -3 for education)
   - Source-specific codes
   - Action for each code

4. **Assess Suppression**
   - Suppression thresholds
   - Typical suppression rates
   - Impact on analysis

5. **Check Comparability**
   - Cross-state validity
   - Cross-year consistency
   - Definition changes over time

### Thoroughness Directive

```
- Extract ALL coded value mappings
- Document ALL suppression patterns
- Identify ALL source-specific caveats
- Note ANY cross-state comparability issues
- Check for historical definition changes
- Include impact notes for any years the source's data-source skill flags (education example: COVID-19 years 2020-2021)
```

### Invocation Template: Source-Specific Skills

**Purpose:** Deep-dive into source-specific caveats and limitations
**Subagent:** source-researcher
**Skills:** `{domain}-data-source-{source}` (source-researcher preloads `data-scientist` via frontmatter; do not add a skill call for it)

**Available source skills:** Review the skill inventory in the system message for the complete list of available data source skills with their coverage, key variables, and primary use cases.

> The orchestrator resolves source skill names based on the active domain and provides them in the Agent prompt. It fills `{flag_years}` with the years the source skill flags within the confirmed year range, or "none".

```python
Agent({
    description: "Stage 3: Source Deep-Dive - {source_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.
**PROJECT_DIR:** {project_dir}

Call the skill tool with name '{domain}-data-source-{source}'.

**WRITE YOUR NOTES TO:** {project_dir}/output/preliminary_notes/{date}_stage3_{source-name}_source-research.md
Write the full report there, then return a summary with the path (your agent
protocol, Core Behavior 6). Any read-only probe script goes under
{project_dir}/scripts/scratch/ and runs only via run_with_capture.sh; a probe
your notes cite moves first, unchanged, to {project_dir}/scripts/probes/ (mv),
and the notes cite that path. Full pipeline mode only; outside it (Data
Discovery), omit this block and PROJECT_DIR, and return the full report as text.

**RESEARCH QUESTION (verbatim):**
{research_question}

**CONSTRAINTS:**
- Years of interest: {years}
- Geographic scope: {geography}

**CONTEXT FROM STAGE 2:**
Candidate datasets identified: {dataset_identifiers}
Variables to investigate: {variables}

**VARIABLES REQUIRING DEEP-DIVE:**
{flagged_variables_with_reasons}

**USER-REFERENCED MATERIALS:**
{absolute paths of the user's materials (or digest) that bear on this source, e.g. a codebook or a paper's variable definitions — or "none"}
Where they define a variable or coded value differently from the source skill,
report the difference rather than settling it.

**THOROUGHNESS DIRECTIVE:**
- Extract ALL coded value mappings for flagged variables
- Document ALL suppression patterns and thresholds
- Identify ALL source-specific caveats and limitations
- Note ANY cross-state comparability issues
- Check for historical definition changes
- Include impact notes for any years the source skill flags ({flag_years}; education example: COVID-19 years 2020-2021)
- Document population coverage (who is included/excluded)

**OUTPUT FORMAT:**
Write the notes in the Source Researcher Output Format (see your agent
protocol, § Output Format); return the summary.

**Emphasis for this invocation:**
- Coded value mappings for flagged variables
- Suppression patterns and thresholds
- Cross-state comparability issues
- Impact notes for flagged years ({flag_years}; education example: COVID-19 years 2020-2021)""",
    subagent_type: "source-researcher"
})
```

### Output Format

**Output Format:** The source-researcher agent follows its own Output Format (defined in `.claude/agents/source-researcher.md`). It writes the full report to the `output/preliminary_notes/{date}_stage3_{source-name}_source-research.md` path the dispatch names and returns a summary with that path, which the orchestrator keeps in its working memory.

### Preliminary Notes Persistence: Stage 3

For full pipeline mode only, each dispatch names the notes path and source-researcher writes the file itself:

| Agent | Writes To |
|-------------|----------|
| source-researcher (Stage 3, per source) | `{project_dir}/output/preliminary_notes/{date}_stage3_{source-name}_source-research.md` |

The orchestrator persists a return itself (full and unmodified, with the provenance header, per `SKILL.md` § Subagent Return Processing steps 2a-2c) only when it came back inline: the agent reports a failed write or a rejected name, or the dispatch named no path.

**Gate condition:** ALL Stage 3 preliminary notes must exist on disk before dispatching Stage 3.5 (research-synthesizer). The orchestrator confirms each file exists at the named path and holds the complete five-section report.

### Gate Criteria (G3)

- [ ] All flagged variables investigated
- [ ] Coded values fully documented (VARIABLES > Coded Value Reference, a handling action per code)
- [ ] Suppression rules and typical rates documented (CAVEATS)
- [ ] Cross-state comparability assessed
- [ ] Every caveat and pitfall has a mitigation
- [ ] All LOW confidence findings resolved
- [ ] All source-researcher notes on disk at their named paths (full pipeline mode only)

---

## Stage 3.5: Findings Synthesis

> **Full Pipeline Only:** Stage 3.5 (Findings Synthesis into PSU1) applies only when Discovery is Phase 1 of Full Pipeline. In standalone Data Discovery mode, synthesis is handled directly by the orchestrator per `data-discovery-mode.md`.

**Executor:** Subagent (research-synthesizer)
**Purpose:** Consolidate findings from Stage 2-3 explorations into unified planning guidance

### Actions

1. **Consolidate Parallel Findings**
   - Merge Stage 2 exploration results
   - Merge Stage 3 deep-dive findings per source
   - Identify overlapping variables and entities

2. **Resolve Conflicts**
   - Flag contradictions between sources
   - Document resolution rationale
   - Choose primary vs. supplementary sources

3. **Create Unified Context**
   - Single integrated data model
   - Unified variable mapping
   - Consolidated limitations list

### Invocation Template: research-synthesizer

**Purpose:** Consolidate Stage 2-3 findings into unified planning guidance
**Stage:** 3.5 (after all Stage 3 source research completes)
**Agent:** `research-synthesizer` (see `.claude/agents/research-synthesizer.md`)
**Skills:** `data-scientist`

The orchestrator provides all Stage 2 and Stage 3 outputs as context. The agent returns
a unified synthesis with cross-source conflict resolution and join feasibility assessment.

**Skill Loading:** The `research-synthesizer` agent preloads `data-scientist` via frontmatter —
do NOT include a redundant `Call the skill tool` instruction in the Agent prompt. The skill
provides methodological rigor for assessing data quality findings and join feasibility across sources.

**PSU Note:** This task concludes Phase 1. The orchestrator will present PSU1 to the user using findings from this synthesis. Ensure the User-Facing Summary provides a clear, complete picture of discovery results suitable for user review.

```python
Agent({
    description: "Stage 3.5: Findings Synthesis",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

**RESEARCH QUESTION (verbatim):**
{research_question}

**CONSTRAINTS:**
- Years of interest: {years}
- Geographic scope: {geography}

**SOURCES IDENTIFIED IN STAGE 2:** {count} ({source names})
Every one of them must have a Stage 3 report below.

**STAGE 2 FINDINGS:**
Read the full preliminary notes at: {project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md

**STAGE 3 FINDINGS (per source):**
Read the full preliminary notes at:
- {project_dir}/output/preliminary_notes/{date}_stage3_{source1}_source-research.md
- {project_dir}/output/preliminary_notes/{date}_stage3_{source2}_source-research.md
[...one path per source-researcher dispatch]

**ORCHESTRATOR SUMMARY (for quick orientation — read full preliminary notes above for detail):**
[Brief 3-5 bullet summary of key findings across sources]

**TASK:**
Consolidate these parallel findings into a unified context for Plan creation.

**OUTPUT FORMAT:**
Return the synthesis in your agent protocol's Output Format (§ Output Format),
with its Status line, Confidence Assessment and User-Facing Summary. The
orchestrator builds the discovery checkpoint (PSU1) from the User-Facing Summary.
Return it as text and write no file: the orchestrator saves it, unmodified, to
{project_dir}/output/preliminary_notes/{date}_stage3.5_research-synthesis.md.
""",
    subagent_type: "research-synthesizer"
})
```

#### Preliminary Notes Persistence: Stage 3.5

After the research-synthesizer returns, the orchestrator persists the full return to disk (full and unmodified, with the provenance header, per `SKILL.md` § Subagent Return Processing steps 2a-2c):

| Agent Return | Write To |
|-------------|----------|
| research-synthesizer (Stage 3.5) | `{project_dir}/output/preliminary_notes/{date}_stage3.5_research-synthesis.md` |

**Gate condition:** Stage 3.5 preliminary notes must exist on disk before presenting PSU1 to the user and before dispatching Stage 4 (data-planner). The orchestrator confirms the file was written as specified.

> **Full Pipeline Only:** Gate G3.5 applies only to Full Pipeline mode. In standalone Data Discovery mode, the orchestrator manages synthesis and presentation directly.

### Gate Criteria (G3.5)

- [ ] All source findings integrated
- [ ] Conflicts identified and resolved
- [ ] Unified context ready for data-planner
- [ ] Full research-synthesizer return written to disk (full pipeline mode only)
- [ ] **PSU1 presented to user**
- [ ] **User confirmed PSU1**

> **Full Pipeline Only:** PSU1 is presented only in Full Pipeline mode. In standalone Data Discovery mode, findings are presented using the output format in `data-discovery-mode.md`.

### Phase Status Update 1 (PSU1): Discovery Complete

**Trigger:** Every G3.5 item above the two PSU1 items is checked (synthesis complete, conflicts resolved)
**Blocking:** YES — Stage 4 CANNOT begin until user confirms PSU1

**Actions:**
1. Compile discovery findings from Stages 2, 3, and 3.5
2. Present PSU1 to user using the PSU template (see full-pipeline-mode.md "Phase Status Updates (Mandatory)" section), headed `**Checkpoint: Discovery Complete**`
3. WAIT for explicit user confirmation

**PSU1 Content Requirements (the checkpoint MUST include; every item lands in text the user reads, so word it per the Plain-Language Rule in `SKILL.md` § User-Facing Communication Standards):**
- Data sources identified (with dataset identifiers and year ranges)
- Key variables discovered and their availability status
- Source-specific caveats and limitations (from Stage 3 deep-dives)
- Suppression patterns, and cross-region comparability issues (e.g., cross-state for education)
- Cross-source conflicts and how they were resolved (from Stage 3.5)
- Feasibility assessment: can the research question be answered with available data?
- Recommended analytical approach for the Plan
- Any LOW-confidence items that need user input before planning

**User Response Handling:**
- **Approve** → Proceed to Stage 4 (Plan Creation)
- **Request more exploration** → Return to Stage 2 or 3 for additional discovery
- **Adjust scope** → Update research question/scope, re-confirm, then proceed to Stage 4
- **Ask questions** → Answer, then re-present approval request

#### PSU1 Checkpoint Purpose

Include in the "Why this checkpoint" field:
> "I'm pausing here to make sure we've identified the right data and understand its limitations before investing time in methodology design."

#### PSU1 Phase Transition Bridge

Include in the "What Comes Next" field:
> "Now that we know what data is available and what its limitations are, I'll design a detailed analysis plan — including the methodology, the specific data to acquire, and the sequence of analytical steps. You'll review the full plan before any code runs."

#### PSU1 Feedback Guidance

Include in the "What's Most Useful From You Here" field:
> "Are these the right data sources for your question? Any sources I may have missed? Any concerns about the limitations I identified?"

---

### Re-run Guidance

See `agent_reference/ERROR_RECOVERY.md` > "Re-run Procedures" for complete re-run decision trees when Discovery stages need to be repeated.

---

## Verification Checklists

Apply the relevant checklist after each subagent returns findings for the corresponding stage.

### Stage 2 (Data Exploration) Verification

- [ ] Recommended Data Level specified (not "TBD" or placeholder)
- [ ] Candidate Datasets table has ≥1 dataset identifier with complete rows
- [ ] Key Variables table has actual variable names (not "[add more]")
- [ ] Variables Flagged for Deep-Dive has rationale for each flag
- [ ] Completeness Assessment checkboxes all marked
- [ ] Confidence Assessment present with overall confidence level
- [ ] If confidence is LOW: resolution plan or escalation present

### Stage 3 (Source Deep-Dive) Verification

- [ ] Source name explicitly stated
- [ ] SOURCE_SUMMARY present (coverage, years, provider)
- [ ] VARIABLES includes the Coded Value Reference table, with a handling action for every code of each flagged variable
- [ ] CAVEATS includes suppression rules and typical rates, and cross-region comparability when the scope spans regions (e.g., cross-state for education)
- [ ] PATTERNS includes join patterns when the analysis is multi-source
- [ ] PITFALLS has at least one critical pitfall with detection and avoidance; every caveat and pitfall has a mitigation
- [ ] Confidence Assessment present, with a rating and rationale per section
- [ ] If confidence is LOW: resolution present

### Stage 3.5 (Findings Synthesis) Verification

- [ ] All source findings consolidated into unified summary
- [ ] Cross-source conflicts identified and resolved (or flagged for Plan)
- [ ] Join feasibility assessed with key considerations documented
- [ ] Unified guidance ready for data-planner input
- [ ] Status line present (PASSED, WARNING or BLOCKER)
- [ ] Confidence Assessment present
- [ ] User-Facing Summary present (the basis of PSU1)
