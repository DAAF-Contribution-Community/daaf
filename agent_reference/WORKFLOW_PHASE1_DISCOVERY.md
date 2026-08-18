# Workflow Reference: Phase 1 — Discovery & Scoping

Stages 1, 2, 3, 3.5. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline-mode.md` (loaded only for Full Pipeline mode; not needed for standalone Data Discovery mode).

> **Wave barrier discipline (async dispatch).** This phase contains the pipeline's heaviest parallel-dispatch surface: Stage 3 fans out one source-researcher per data source (up to 5 concurrent), and Stage 2 may run alongside. Subagents dispatched via the Agent tool run in the background by default and return via completion notifications that may arrive one at a time. Treat mid-wave notifications as **status-only**: do not make gate decisions (G2, G3), revise the discovery scope, persist STATE.md conclusions, present a PSU checkpoint, or begin Stage 3.5 synthesis until EVERY member of the dispatched wave has returned. Synthesis (Stage 3.5) happens once, over the complete set of source-researcher returns — never incrementally per return. Interim narration to the user ("two of three source deep-dives have reported back") is fine; acting on partial results is not. An early return under context pressure, or a failed/skipped source-researcher, still counts as that member's completion — handle redelegation as part of whole-wave synthesis, not as an immediate mid-wave reaction.

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
   - Describe expected scope and outputs
   - Await EXPLICIT user confirmation

4. **Ask Clarifying Questions (if needed)**
   - Ambiguous scope
   - Missing constraints
   - Multiple interpretations possible

### Output

- Confirmed engagement mode
- Research question formulation
- Any clarifications received

### Gate Criteria (G1)

- [ ] Mode classified and confirmed
- [ ] Research question clearly stated
- [ ] Any clarifications documented

> **Full Pipeline Only:** The Pre-Flight Checklist is defined in `full-pipeline-mode.md` § Pre-Flight Checklist and is presented *before* this file is loaded. By the time the orchestrator reads this file, the user has already confirmed the pre-flight. Data Discovery mode does not use the Pre-Flight Checklist.

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

> **Domain extensibility:** The orchestrator resolves the explorer skill name based on the active domain (from the Plan's Domain Configuration) and provides it in the Agent prompt. The example below uses `education-data-explorer` as the demonstration domain default.

```python
Agent({
    description: "Stage 2: Data Exploration",
    prompt: """You have access to a skill tool. First, call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '{domain_explorer_skill}'.  # e.g., 'education-data-explorer'

**ORIGINAL REQUEST (for context):**
> {original_user_request_verbatim}

**RESEARCH QUESTION:**
{research_question}

**CONSTRAINTS:**
- Years of interest: {years}
- Geographic scope: {geography}
- Population: {population}

**THOROUGHNESS DIRECTIVE:**
- Search ALL relevant data levels (schools, districts, colleges as appropriate)
- Consider multiple potential data sources before recommending
- Flag ALL variables that might need deeper source-specific investigation
- Check year coverage against research question needs
- Include a 'Limitations Encountered' section in your output
- Be explicit about what you searched and what you found

**OUTPUT FORMAT:**
Return findings in this structure:

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

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "search-agent"
})
```

### Output Format

```markdown
1. Recommended Data Level: [schools | school-districts | college-university]

2. Candidate Datasets:
| Dataset Identifier | Source | Grain | Description | Years Available |
|--------------------|--------|-------|-------------|-----------------|
| ... | ... | ... | ... | ... |

3. Key Variables:
| Variable | Dataset Identifier | Type | Description |
|----------|--------------------|------|-------------|
| ... | ... | ... | ... |

4. Variables Flagged for Deep-Dive:
| Variable | Reason |
|----------|--------|
| ... | ... |

5. Limitations Encountered:
| Limitation | Impact | Resolution |
|------------|--------|------------|
| ... | ... | ... |

6. Completeness Assessment:
- [ ] Schools level searched
- [ ] Districts level searched (if relevant)
- [ ] Colleges level searched (if relevant)
- [ ] Multiple sources considered
```
### Preliminary Notes Persistence: Stage 2

After the explorer agent returns for full pipeline mode only, the orchestrator persists the full return to disk:

| Agent Return | Write To |
|-------------|----------|
| search-agent (Stage 2) | `{project_dir}/output/preliminary_notes/{date}_stage2_data-exploration.md` |

Stage 2 preliminary notes must exist on disk before dispatching Stage 3 (source-researcher). The orchestrator confirms the file was written as specified.

### Gate Criteria (G2)

- [ ] At least one candidate dataset identified (canonical dataset identifier)
- [ ] Key variables identified
- [ ] Variables for deep-dive flagged
- [ ] Year coverage verified
- [ ] Full search-agent return written to disk (full pipeline mode only)
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
   - **Parallel cap:** If >5 sources identified, sub-batch source-researcher dispatch into groups of ≤5 (hard maximum of 5 concurrent subagents)

2. **Extract Caveats**
   - Source-specific limitations
   - Population definitions
   - Data collection methodology

3. **Document Coded Values**
   - Domain-specific coded values (from Plan Domain Configuration; e.g., -1, -2, -3 for education)
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
- Include impact notes for any flagged years (per FLAG_YEARS in Plan Domain Configuration; e.g., COVID-19 years 2020-2021 for education)
```

### Invocation Template: Source-Specific Skills

**Purpose:** Deep-dive into source-specific caveats and limitations
**Subagent:** source-researcher
**Skills:** `data-scientist`, `education-data-source-*`

**Available source skills:** Review the skill inventory in the system message for the complete list of available data source skills with their coverage, key variables, and primary use cases.

> The orchestrator resolves source skill names based on the active domain and provides them in the Agent prompt.

```python
Agent({
    description: "Stage 3: Source Deep-Dive - {source_name}",
    prompt: """**BASE_DIR:** {BASE_DIR}
All relative paths in referenced files resolve from BASE_DIR.

Call the skill tool with name 'data-scientist'.
Then, call the skill tool with name '{domain}-data-source-{source}'.

**CONTEXT FROM STAGE 2:**
Candidate datasets identified: {dataset_identifiers}
Variables to investigate: {variables}

**VARIABLES REQUIRING DEEP-DIVE:**
{flagged_variables_with_reasons}

**THOROUGHNESS DIRECTIVE:**
- Extract ALL coded value mappings for flagged variables
- Document ALL suppression patterns and thresholds
- Identify ALL source-specific caveats and limitations
- Note ANY cross-state comparability issues
- Check for historical definition changes
- Include COVID-19 impact notes for 2020-2021 data
- Document population coverage (who is included/excluded)

**OUTPUT FORMAT:**
Return findings using the Source Researcher Output Format
(see your agent protocol, § Output Format).

**Emphasis for this invocation:**
- Coded value mappings for flagged variables
- Suppression patterns and thresholds
- Cross-state comparability issues
- COVID-19 impact notes for 2020-2021 data""",
    subagent_type: "source-researcher"
})
```

### Output Format

**Output Format:** The source-researcher agent follows its own Output Format (defined in `.claude/agents/source-researcher.md`). The orchestrator writes the full return to `output/preliminary_notes/{date}_stage3_{source-name}_source-research.md` before extracting a summary for its own working memory.

### Preliminary Notes Persistence: Stage 3

After each deep-dive agent returns for full pipeline mode only, the orchestrator persists the full return to disk:

| Agent Return | Write To |
|-------------|----------|
| source-researcher (Stage 3, per source) | `{project_dir}/output/preliminary_notes/{date}_stage3_{source-name}_source-research.md` |

**Gate condition:** ALL Stage 3 preliminary notes must exist on disk before dispatching Stage 3.5 (research-synthesizer). The orchestrator confirms the file was written as specified.

### Gate Criteria (G3)

- [ ] All flagged variables investigated
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings have mitigations
- [ ] All LOW confidence findings resolved
- [ ] All source-researcher returns written to disk (full pipeline mode only)

---

## Stage 3.5: Findings Synthesis

> **Full Pipeline Only:** Stage 3.5 (Findings Synthesis into PSU1) applies only when Discovery is Phase 1 of Full Pipeline. In standalone Data Discovery mode, synthesis is handled directly by the orchestrator per `data-discovery-mode.md`.

**Executor:** Subagent (general-purpose)
**Agent:** `research-synthesizer`
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
**Subagent:** general-purpose
**Skills:** `data-scientist`

For the complete invocation pattern, see `.claude/agents/research-synthesizer.md` Invocation section.
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
1. Integrated Data Model
2. Conflict Resolution Log
3. Unified Variable Mapping
4. Consolidated Limitations
5. Recommended Approach
""",
    subagent_type: "research-synthesizer"
})
```

#### Preliminary Notes Persistence: Stage 3.5

After the research-synthesizer returns, the orchestrator persists the full return to disk:

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

**Trigger:** Gate G3.5 satisfied (synthesis complete, conflicts resolved)
**Blocking:** YES — Stage 4 CANNOT begin until user confirms PSU1

**Actions:**
1. Compile discovery findings from Stages 2, 3, and 3.5
2. Present PSU1 to user using the PSU template (see full-pipeline-mode.md "Phase Status Updates (Mandatory)" section)
3. WAIT for explicit user confirmation

**PSU1 Content Requirements:**
- Data sources identified (with dataset identifiers and year ranges)
- Key variables discovered and their availability status
- Source-specific caveats and limitations (from Stage 3 deep-dives)
- Suppression patterns identified
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

#### PSU1 Content Requirements

The PSU1 checkpoint MUST include:
- Data sources identified (with dataset identifiers and year ranges)
- Key variables and their availability
- Source-specific caveats and limitations discovered
- Suppression patterns and cross-region comparability issues (e.g., cross-state for education)
- Feasibility assessment and recommended analytical approach
- Any LOW-confidence items requiring user input

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
- [ ] Source-Specific Caveats table populated (not empty)
- [ ] Coded Value Mappings complete for all flagged variables
- [ ] Suppression Patterns documented with typical rates
- [ ] Cross-region comparability assessed (if multi-region analysis, e.g., cross-state for education)
- [ ] Critical Warnings have mitigation strategies
- [ ] Confidence Assessment present
- [ ] If confidence is LOW: resolution present

### Stage 3.5 (Findings Synthesis) Verification

- [ ] All source findings consolidated into unified summary
- [ ] Cross-source conflicts identified and resolved (or flagged for Plan)
- [ ] Join feasibility assessed with key considerations documented
- [ ] Unified guidance ready for data-planner input
- [ ] Confidence Assessment present
