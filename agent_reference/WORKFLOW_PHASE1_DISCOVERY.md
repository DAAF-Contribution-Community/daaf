# Workflow Reference: Phase 1 — Discovery & Scoping

Stages 1, 2, 3, 3.5. Cross-phase orchestration guidance (invocation templates, QA protocols, context requirements) is in `full-pipeline.md` (loaded only for Full Pipeline mode; not needed for standalone Data Discovery mode).

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

> **Full Pipeline Only:** The Pre-Flight Checklist below applies only to Full Pipeline mode. Data Discovery mode skips this section.

### Pre-Flight Checklist (Full Pipeline Mode Only)

**REQUIRED:** Before proceeding past Stage 1 in Full Pipeline mode, confirm scope with user:

```
**Full Pipeline Analysis: Pre-Flight Check**

This analysis will create:
- [ ] Research Plan documents (Plan.md + Plan_Tasks.md) summarizing all key goals, considerations, decisions, risks, interpretations, work stage summaries, and final work review notes
- [ ] STATE.md session state file (for progress tracking and session recovery)
- [ ] Comprehensive analytic scripts covering data fetch, clean, join, transformation, analysis, and QA for all of the above
- [ ] Validated datasets (raw + processed)
- [ ] Marimo notebook "walkthrough" of successfully completed analysis scripts and their execution runtime logs for inspection
- [ ] Illustrative key data visualizations
- [ ] Summary stakeholder report synthesizing key findings and interpreting key data visualizations
- [ ] LEARNINGS.md lessons learned

Estimated scope:
- Data sources: [identified sources]
- Years: [year range]
- Approximate records: [estimate]
- Geographic scope: [geography]

**Please confirm whether you'd like me to begin with this approach, or let me know if you have any changes you'd like to make.**
```

**User may:**
- Confirm → Proceed to Stage 2
- Request scope adjustment → Clarify and reconfirm
- Decline → Switch to Data Discovery or Data Lookup mode
You MUST wait for user confirmation before proceeding.

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

2. **Search Endpoints**
   - Query Education Data Portal metadata
   - Identify relevant sources (CCD, IPEDS, CRDC, etc.)
   - Check year coverage

3. **Identify Variables**
   - List variables relevant to research question
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

### 2. Candidate Endpoints
| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|

### 3. Key Variables
| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|

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

2. Candidate Endpoints:
| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|
| ... | ... | ... | ... |

3. Key Variables:
| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|
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

### Gate Criteria (G2)

- [ ] At least one candidate endpoint identified
- [ ] Key variables identified
- [ ] Variables for deep-dive flagged
- [ ] Year coverage verified
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
Endpoints identified: {endpoints}
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
Return findings in this structure:

### Source: {source_name}

### 1. Source-Specific Caveats
| Caveat | Impact on Analysis | Mitigation Strategy |
|--------|-------------------|---------------------|

### 2. Coded Value Mappings
| Variable | Code | Meaning | Recommended Action |
|----------|------|---------|-------------------|
| [var] | -1 | Missing/not reported | Filter before calculations |
| [var] | -2 | Not applicable | Exclude from analysis |
| [var] | -3 | Suppressed | Document; cannot recover |

### 3. Suppression Patterns
| Variable | Typical Rate | Threshold | Impact on Analysis |
|----------|--------------|-----------|-------------------|

### 4. Cross-State Comparability
| Analysis Type | Valid Across States? | Notes |
|---------------|---------------------|-------|

### 5. Critical Warnings
1. **[Warning Name]:** [Description]
   - **Mitigation:** [How to handle]

### 6. Limitations Encountered
| Limitation | Impact | Resolution |
|------------|--------|------------|

### 7. Confidence Assessment
| Finding | Confidence | Rationale |
|---------|------------|-----------|
| [key finding] | HIGH/MEDIUM/LOW | [why this confidence level] |

**Overall Confidence:** [HIGH | MEDIUM | LOW]
**LOW Confidence Items Requiring Resolution:** [list or "None"]

After completing the skill's Required Actions, return findings using the format above.""",
    subagent_type: "source-researcher"
})
```

### Output Format

**Output Format:** See `.claude/agents/source-researcher.md` > "Output Format" section for the authoritative output structure. The source-researcher agent returns a structured report with five deliverables (SOURCE_SUMMARY, VARIABLES, CAVEATS, PATTERNS, PITFALLS) plus confidence assessment and learning signal.

### Gate Criteria (G3)

- [ ] All flagged variables investigated
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings have mitigations
- [ ] All LOW confidence findings resolved

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
[Insert Stage 2 output]

**STAGE 3 FINDINGS (per source):**
[Insert Stage 3 outputs for each source]

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

> **Full Pipeline Only:** Gate G3.5 applies only to Full Pipeline mode. In standalone Data Discovery mode, the orchestrator manages synthesis and presentation directly.

### Gate Criteria (G3.5)

- [ ] All source findings integrated
- [ ] Conflicts identified and resolved
- [ ] Unified context ready for data-planner
- [ ] **PSU1 presented to user**
- [ ] **User confirmed PSU1**

> **Full Pipeline Only:** PSU1 is presented only in Full Pipeline mode. In standalone Data Discovery mode, findings are presented using the output format in `data-discovery-mode.md`.

### Phase Status Update 1 (PSU1): Discovery Complete

**Trigger:** Gate G3.5 satisfied (synthesis complete, conflicts resolved)
**Blocking:** YES — Stage 4 CANNOT begin until user confirms PSU1

**Actions:**
1. Compile discovery findings from Stages 2, 3, and 3.5
2. Present PSU1 to user using the PSU template (see full-pipeline.md "Phase Status Updates (Mandatory)" section)
3. WAIT for explicit user confirmation

**PSU1 Content Requirements:**
- Data sources identified (with endpoints and year ranges)
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
- Data sources identified (with endpoints and year ranges)
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
- [ ] Candidate Endpoints table has ≥1 endpoint with complete rows
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
