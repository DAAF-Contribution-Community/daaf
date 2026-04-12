---
# Plan Frontmatter
# This YAML block contains machine-readable metadata for orchestration

title: "[Analysis Title]"
date: "YYYY-MM-DD"
version: ""                           # Empty for original, "a", "b", etc. for revisions
status: "planning"                    # planning | in_progress | complete

# Goal-Backward Verification Criteria
must_haves:
  research_outcomes:
    - "[What must be examined/measured/reported — Outcome 1]"
    - "[What must be examined/measured/reported — Outcome 2]"
    - "[What must be examined/measured/reported — Outcome 3]"

  hypotheses:  # Optional — directional expectations from theory or prior literature
    # - id: "H1"
    #   statement: "[Directional prediction based on prior knowledge]"
    #   basis: "[Why expected — cite theory, prior research, or domain knowledge]"

  artifacts:
    - path: "research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title].py"
      provides: "[What this file delivers]"
      min_lines: 200
      contains: "[Pattern or text that must be present]"

    - path: "research/YYYY-MM-DD_[Title]/data/processed/YYYY-MM-DD_analysis.parquet"
      provides: "[What this file delivers]"
      has_columns: ["col1", "col2", "col3"]

    - path: "research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Report.md"
      provides: "[What this file delivers]"
      contains: ["## Section 1", "## Section 2"]

  key_links:
    - from: "[source file]"
      to: "[target file or resource]"
      via: "[connection mechanism]"
      pattern: "[regex pattern to verify connection]"
---

# [Analysis Title]

**Key Principles:**

1. **Task actions must be specific enough to execute without clarification.**
   - Invalid: "Process the data appropriately"
   - Valid: "Filter rows where enrollment == -1, save to data/processed/2026-01-31_ccd_clean.parquet"

2. **File paths must be explicit (no placeholders in the final plan).**
   - Invalid: `data/raw/[filename].parquet`
   - Valid: `data/raw/2026-01-31_ccd_schools.parquet`

3. **Verification must be executable (not subjective).**
   - Invalid: "Data looks correct"
   - Valid: "Row count > 0 AND row count < 200000"

4. **Done criteria must be measurable.**
   - Invalid: "Task complete"
   - Valid: "CP1 PASSED, files saved to data/raw/"

---

## Version Information

*Include this section for all revisions. Omit for original deliveries.*

**Version:** [a | b | c | ...]
**Based On:** `YYYY-MM-DD[prior-suffix]_[Title]_Plan.md` (same folder)
**Prior Versions:**
- `YYYY-MM-DD[x]_[Title]_Plan.md` — [revision type, brief note]
- `YYYY-MM-DD_[Title]_Plan.md` — Original delivery

**Revision Trigger:**
> [Verbatim user request that triggered this revision]

**Revision Type:** [Documentation Re-research | Logic Correction | Output Adjustment | Minor Fix | Scope Expansion]

**Summary of Changes:**
- [Key change 1]
- [Key change 2]

**Data Regeneration Note:** Data regenerated fresh for this revision (not copied from prior version).

---

## Companion Files

| File | Purpose |
|------|---------|
| `YYYY-MM-DD_[Title]_Plan_Tasks.md` | Machine-readable executable task sequence — contains all XML task blocks, wave execution rules, and task-specific operational details. Created by data-planner during Stage 4. |
| `STATE.md` | Operational state tracking during execution — contains transformation progress, checkpoint status, runtime risks, QA findings summary, final review log, and session recovery context. Created by orchestrator during Stage 4. |
| `LEARNINGS.md` | Session learnings — accumulated data quality insights, methodology lessons, and process observations. Created by orchestrator during Stage 4. |

> **Immutability Rule:** This Plan document and the companion Plan_Tasks.md are **100% frozen after Stage 4.5** (Plan Validation). No runtime updates of any kind. All execution state goes to STATE.md. All runtime decisions go to STATE.md Key Decisions Made. All runtime risks go to STATE.md Runtime Risks.

---

## Domain Configuration

> **Purpose:** This section specifies the active data domain and its associated skills, coded values, and governance rules. All domain-specific behavior throughout the pipeline (skill loading, validation thresholds, coded value handling) is driven by these settings. For domains without a particular feature (e.g., no suppression codes), set the value to N/A or "none".

**Active Domain:** [domain name, e.g., "education"]
**Query Skill:** [skill name, e.g., "education-data-query"]
**Explorer Skill:** [skill name, e.g., "education-data-explorer"]
**Context Skill:** [skill name or N/A, e.g., "education-data-context"]
**Coded Missing Values:** [list or "none", e.g., [-1, -2, -3]]
**Suppression Code:** [value or N/A, e.g., -3]
**Suppression Threshold:** [decimal or N/A, e.g., 0.5]
**Year Column:** [column name or N/A, e.g., "year"]
**Flag Years:** [list or "none", e.g., [2020, 2021] for COVID-impacted years]
**Governance Rules:** [list or "none", e.g., "Cross-state assessment comparison is NEVER valid"]

---

## Original Request & Clarifications

### Original Request

> [Paste the verbatim user request here]

### Clarifications Received

1. **[Topic]:** [User's response]
2. **[Topic]:** [User's response]

### Research Question

[Your interpretation of the request as a clear, answerable research question]

---

## Goal & Context

### Analysis Goal

[Clear statement of the analysis objective — what will be produced and why it matters]

### Background Context

[Business/policy context that informs the analysis approach]

### Success Criteria

- [ ] [Measurable outcome 1]
- [ ] [Measurable outcome 2]
- [ ] [Measurable outcome 3]

---

## Must-Haves (Goal-Backward Verification)

**Purpose:** This section defines what must be rigorously investigated and produced for the analysis to be considered complete. Derived using goal-backward methodology — working from the research question to identify research outcomes, required artifacts, and critical connections.

### Deriving Must-Haves

**Goal-backward planning asks:** "What must be EXAMINED for the research question to be rigorously answered?" rather than "What should we build?"

**Step 1: State the Goal (Outcome, Not Task)**
- Good: "Analysis characterizes enrollment trends by poverty level" (outcome)
- Bad: "Create enrollment visualization" (task)

**Step 2: Derive Research Outcomes (What Must Be Investigated)**
Ask: "What must be EXAMINED for this research question to be rigorously answered?"
List 3-7 outcomes that define the scope of rigorous investigation. Each outcome states what must be measured, characterized, or reported — not what the result should be.

- Good: "Relationship between poverty rate and enrollment is characterized (direction, magnitude, significance)"
- Bad: "Poverty is negatively correlated with enrollment (expect r < -0.3)"

Research outcomes define the **scope and rigor** of the investigation. They are assessed as ADDRESSED or NOT ADDRESSED based on whether the analysis thoroughly investigated and reported on the stated topic. Surprising or null findings are equally valid — the outcome is ADDRESSED if the investigation was rigorous.

**Step 2b: State Hypotheses (Optional — Pre-Registration)**
If prior literature, domain knowledge, or theory suggests directional expectations, state them transparently as hypotheses with their basis. Hypotheses are pre-registered predictions, not success criteria. A rigorously refuted hypothesis is excellent science.

- Each hypothesis must include an `id`, `statement`, and `basis` (citation or rationale)
- Hypotheses are assessed as SUPPORTED / NOT SUPPORTED / PARTIALLY SUPPORTED
- Either outcome is equally valid and informative
- Hypotheses belong here, NOT in research outcomes — any directional prediction in a research outcome should be moved to this section

**Step 3: Derive Required Artifacts**
For each research outcome, ask: "What must EXIST for this to be investigated?"
Identify specific files with expected content.

**Step 4: Identify Key Links (Critical Connections)**
Ask: "Where is this most likely to break?"
Key links are connections that, if missing, cause cascading failures.

### Must-Haves Specification

```yaml
must_haves:
  research_outcomes:
    - "Enrollment trends by year are measured and reported with appropriate statistical testing"
    - "School-level poverty rates are calculated and their distribution characterized"
    - "Suppression rates are documented with impact assessment on analytical validity"
    - "Data limitations are explicitly stated in the report with scope implications"
    - "Key relationships are visualized with uncertainty quantification where applicable"

  hypotheses:  # Optional — remove section if no directional predictions
    - id: "H1"
      statement: "Schools with higher poverty rates have lower enrollment growth"
      basis: "Prior literature on demographic shifts and school choice patterns (cite specific studies)"

  artifacts:
    - path: "research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title].py"
      provides: "Interactive analysis notebook"
      min_lines: 200
      contains: "mo.md"  # Marimo markdown cells present

    - path: "research/YYYY-MM-DD_[Title]/data/processed/YYYY-MM-DD_analysis.parquet"
      provides: "Cleaned analysis dataset"
      has_columns: ["ncessch", "year", "enrollment", "frl_rate"]

    - path: "research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Report.md"
      provides: "Stakeholder report with findings"
      contains: ["## Executive Summary", "## Limitations", "## Data Sources"]

    - path: "research/YYYY-MM-DD_[Title]/output/figures/YYYY-MM-DD_enrollment_trends.png"
      provides: "Trend visualization"
      min_size_kb: 50

  key_links:
    - from: "YYYY-MM-DD_[Title].py"
      to: "data/processed/YYYY-MM-DD_analysis.parquet"
      via: "pl.read_parquet() in data loading cell"
      pattern: "read_parquet.*analysis"

    - from: "YYYY-MM-DD_[Title].py"
      to: "output/figures/"
      via: "ggplot.save() or fig.write_html()"
      pattern: "(ggsave|write_image|write_html|savefig)"

    - from: "YYYY-MM-DD_[Title]_Report.md"
      to: "output/figures/"
      via: "Markdown image references"
      pattern: "!\\[.*\\]\\(.*figures/"

    - from: "data/processed/*"
      to: "data/raw/*"
      via: "Cleaning transformations in notebook"
      pattern: "filter.*-[123]"  # Coded value filtering
```

### Common Must-Have Failures

| Failure Type | Bad Example | Good Example |
|--------------|-------------|--------------|
| **Outcomes too vague** | "Analysis is complete" | "Year-over-year enrollment change is measured and reported with statistical significance testing" |
| **Outcomes not verifiable** | "Data is clean" | "No coded values (-1, -2, -3) remain in analysis columns" |
| **Outcomes are confirmatory** | "Poverty is negatively correlated with enrollment (expect r < -0.3)" | "Relationship between poverty rate and enrollment is characterized (direction, magnitude, significance, confidence intervals)" |
| **Hypotheses missing basis** | "We expect r > 0.5" | "H1: Based on Smith et al. 2020 selectivity literature, we expect \|r\| > 0.5 between admission rate and graduation rate" |
| **Artifacts too abstract** | "Analysis files" | "research/2026-01-31_School_Poverty/2026-01-31_School_Poverty.py" |
| **Artifacts missing content spec** | path only | path + provides + contains/has_columns |
| **Missing wiring** | Listing files without connections | "Notebook loads from data/processed/ via pl.read_parquet()" |
| **Key links too generic** | "Notebook uses data" | "Cell 3 loads YYYY-MM-DD_analysis.parquet with enrollment, frl columns" |

### Must-Haves Verification Checklist

*Use during Stage 12 (Final Review) to verify all must-haves are addressed:*

**Research Outcomes Verification:**
- [ ] Each research outcome can be verified by examining whether the analysis rigorously investigated and reported on the stated topic
- [ ] No research outcome pre-specifies a directional result (those belong in Hypotheses)
- [ ] No research outcome requires subjective judgment to assess
- [ ] Research outcomes collectively cover the core research question

**Hypotheses Verification (if any):**
- [ ] Each hypothesis has a stated basis (theory, prior literature, domain knowledge)
- [ ] Each hypothesis is clearly separated from research outcomes
- [ ] Each hypothesis is assessed as SUPPORTED / NOT SUPPORTED / PARTIALLY SUPPORTED with evidence
- [ ] Refuted hypotheses are reported as valid findings, not as failures

**Artifacts Verification:**
- [ ] All artifact paths exist
- [ ] Content specifications are satisfied (contains, has_columns, min_lines)
- [ ] File sizes are reasonable (not empty, not stub)

**Key Links Verification:**
- [ ] Each key link pattern can be found in source file
- [ ] Links form complete data flow (raw → processed → analysis → output)
- [ ] No orphaned artifacts (files that nothing references)

---

## Phase 1: Discovery Results

### Stage 2: Data Exploration

*Output from domain explorer skill (per Domain Configuration; e.g., `education-data-explorer`)*

**Data Level:** [schools | school-districts | college-university]

**Candidate Endpoints:**

| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|
| `/schools/ccd/directory/` | CCD | School directory info | 1986-2022 |
| [add more] | | | |

**Key Variables Identified:**

| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|
| `enrollment` | `/schools/ccd/enrollment/` | integer | Total student enrollment |
| [add more] | | | |

**Variables Flagged for Deep-Dive:**

| Variable | Reason for Deep-Dive |
|----------|---------------------|
| [variable] | [reason: coded values, suppression, caveats] |

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| [What could not be found] | [Effect on analysis] | [How addressed] |

**Stage 2 Completeness Assessment:**
- [ ] All relevant data levels searched (schools, districts, colleges as appropriate)
- [ ] Multiple potential sources considered
- [ ] Year coverage verified for research question
- [ ] Variables requiring deep-dive explicitly flagged
- [ ] Limitations documented

---

### Stage 3: Source Deep-Dive

*Output from `*-data-source-*` skill(s)*

**Sources Investigated:**

| Source | Skill Used | Relevance |
|--------|------------|-----------|
| CCD | `education-data-source-ccd` | Primary data source |
| [add more] | | |

**Source-Specific Caveats:**

#### [Source Name] (e.g., CCD)

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| Public schools only | Cannot analyze private schools | Document limitation |
| [add more] | | |

**Coded Value Mappings:**

| Variable | Code | Meaning | Action |
|----------|------|---------|--------|
| `charter` | 1 | Charter school | Include in filter |
| `charter` | 2 | Not charter | Include in filter |
| [variable] | -1 | Missing/not reported | Exclude from calculations |
| [variable] | -2 | Not applicable | Exclude from analysis |
| [variable] | -3 | Suppressed | Document; cannot recover |

**Suppression Patterns:**

| Variable | Typical Suppression Rate | Threshold | Impact |
|----------|--------------------------|-----------|--------|
| [variable] | ~15% | <3 students | Affects small schools |

**Cross-State Comparability:**

| Analysis Type | Valid Across States? | Notes |
|---------------|---------------------|-------|
| Enrollment counts | Yes | Comparable definitions |
| Assessment scores | **NO** | Different state tests |
| Graduation rates | Conditional | ACGR comparable; other rates vary |

*(Education domain example — replace with your domain's cross-region comparability rules per Domain Configuration.)*

**Critical Warnings:**

1. **[Warning]:** [Description and required mitigation]
2. **[Warning]:** [Description and required mitigation]

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| [What could not be found] | [Effect on analysis] | [How addressed] |

**Stage 3 Completeness Assessment:**
- [ ] All flagged variables investigated
- [ ] Source-specific skill(s) loaded and consulted
- [ ] Coded values fully documented
- [ ] Suppression patterns identified
- [ ] Cross-state comparability assessed
- [ ] Critical warnings documented with mitigations

---

### Phase 1 Overall Assessment

**Completeness Status:** [COMPLETE | GAPS IDENTIFIED]

**If GAPS IDENTIFIED:**

| Gap | Source | Resolution |
|-----|--------|------------|
| [Description] | Stage [N] | [How addressed or escalated] |

**Phase 1 Integration Checklist:**

*Complete before proceeding to Phase 2:*

- [ ] All candidate endpoints documented with year coverage
- [ ] All key variables documented with types and descriptions
- [ ] All source-specific caveats captured
- [ ] All coded value mappings complete
- [ ] Suppression patterns documented
- [ ] Cross-state comparability assessed (if applicable)
- [ ] Critical warnings have mitigation strategies
- [ ] All LOW confidence findings resolved or escalated

---

## Methodology Specification

### Data Acquisition Strategy

**Single Source or Multi-Source:** [Single | Multi-Source Join]

**If Multi-Source, Join Strategy:**

| Left Source | Right Source | Join Key(s) | Expected Cardinality | Risks |
|-------------|--------------|-------------|---------------------|-------|
| CCD schools | CRDC | `ncessch` | 1:1 | Some schools may not appear in both |

### Query Specification

**Query 1: [Description]**

| Field | Value |
|-------|-------|
| Dataset | CCD Schools Directory |
| Mirror Paths | Per-mirror path parameters from datasets-reference.md |
| File Type | Single-file (all years) / Yearly |
| Years | `2020, 2021, 2022` |
| Filters (local) | `fips=6` (California), `charter=1` |
| Variables | `ncessch, school_name, enrollment, frl` |
| Expected Records | ~10,000 |

**Query 2: [Description]** (if applicable)

[Repeat structure]

### Data Freshness Check

**IMPORTANT:** This section is populated during Stage 5 (CP1 validation). If significant lag is discovered, the orchestrator MUST update the user before proceeding.

| Source | Requested Years | Latest Available | Lag | Impact | User Notified? |
|--------|-----------------|------------------|-----|--------|----------------|
| CCD | 2020-2023 | 2023 | 0 years | ✅ Current | N/A |
| CRDC | 2020-2021 | 2021 | 1 year | ✅ Acceptable | N/A |
| [add row per source] | | | | | |

**Lag Assessment Guidelines:**
- **No lag (0 years):** Data is current ✅ — Proceed normally
- **Minor lag (1-2 years):** Acceptable for most analyses ✅ — Document in report
- **Significant lag (3+ years):** ⚠️ **MUST update user before proceeding**
  - Explain the lag and its implications
  - Offer options: proceed with caveat, adjust year range, wait for updated data
  - Document user decision in Decisions Log

**Orchestrator Protocol for Significant Lag:**
If CP1 Check 6 detects lag ≥3 years:
1. PAUSE execution after Stage 5
2. Update this table with lag details
3. Report to user:
   ```
   **Data Lag Detected**
   Requested: {max_year_requested}
   Latest available: {max_year_available}
   Lag: {lag_years} years
   
   Options:
   1. Proceed with {max_year_available} data (document limitation)
   2. Adjust analysis to {revised_year_range}
   3. Wait for {expected_release_date}
   
   How would you like to proceed?
   ```
4. Document decision in Decisions Log
5. Update analysis scope if years changed

**COVID-19 Data Quality Considerations:**
If analysis includes 2020 or 2021 data, CP1 Check 7 will flag this automatically. Document the following:

| Year | Data Quality Impact | Mitigation |
|------|-------------------|------------|
| 2020 | [Collection disruptions, missing data, non-representative samples] | [Exclude year, document caveat, compare to pre/post-COVID trends] |
| 2021 | [Recovery period, partial return to normal collection] | [Document caveat, note recovery status] |

**Note:** Data freshness verified during Stage 5 (CP1 Check 6). COVID impact flagged by CP1 Check 7. Both are updated before proceeding to Stage 6.

### Data Cleaning Specification

**Coded Value Handling:**

*For complete coded value definitions, invoke the domain context skill (per Domain Configuration) via subagent.*

| Variable | Codes to Filter | Rationale |
|----------|-----------------|-----------|
| `enrollment` | -1, -2 | Missing/not applicable (domain-specific codes per Domain Configuration) |
| `frl` | -1, -2, -3 | Missing/not applicable/suppressed (domain-specific codes per Domain Configuration) |

**Suppression Handling:**

- Expected suppression rate: [X]%
- Threshold for STOP condition: 50%
- If exceeded: [escalate to user | aggregate to higher level | document and proceed]

### Transformation Sequence

**IMPORTANT:** Execute transformations following the Wave-Based Execution Protocol. Tasks in the same wave can run in parallel with independent subagent contexts. Tasks in later waves must wait for all prior waves to complete.

#### Wave-Based Task Table

| Wave | Step | Task Name | Operation | Expected Outcome | Script Path | Cardinality | Depends On |
|------|------|-----------|-----------|------------------|-------------|-------------|------------|
| 1 | 1.1 | fetch-ccd | Fetch CCD schools data | ~100K rows | `scripts/stage5_fetch/01_fetch-ccd.py` | N/A | — |
| 1 | 1.2 | fetch-meps | Fetch MEPS poverty data | ~100K rows | `scripts/stage5_fetch/02_fetch-meps.py` | N/A | — |
| 2 | 2.1 | clean-ccd | Filter coded values | ~95K rows (5% loss) | `scripts/stage6_clean/01_clean-ccd.py` | N/A | 1.1 |
| 2 | 2.2 | clean-meps | Filter coded values | ~98K rows (2% loss) | `scripts/stage6_clean/02_clean-meps.py` | N/A | 1.2 |
| 3 | 3.1 | join-data | Join CCD + MEPS on ncessch | ~93K rows | `scripts/stage7_transform/01_join-data.py` | 1:1 | 2.1, 2.2 |
| 4 | 4.1 | filter-state | Filter to FIPS == 6 (CA) | ~9K rows (10% retained) | `scripts/stage7_transform/02_filter-state.py` | N/A | 3.1 |
| 4 | 4.2 | calc-ratio | Calculate student-teacher ratio | Add 1 column | `scripts/stage7_transform/03_calc-ratio.py` | N/A | 3.1 |
| 5 | 5.1 | aggregate | Aggregate by district | ~1K rows | `scripts/stage7_transform/04_aggregate.py` | N/A | 4.1, 4.2 |

**Script Path Convention:**
- Pattern: `scripts/stage{N}_{type}/{step:02d}_{task-name}.py`
- Stage 5 (fetch) → `scripts/stage5_fetch/`
- Stage 6 (clean) → `scripts/stage6_clean/`
- Stage 7 (transform) → `scripts/stage7_transform/`
- Stage 8 (analysis & viz) → `scripts/stage8_analysis/`

> **Full Task Definitions:** The complete XML task specifications for each entry in this table are in the companion `Plan_Tasks.md` file. See `agent_reference/PLAN_TASKS_TEMPLATE.md` for the task definition template.

### Stage Interface Specifications

Define the expected data contracts between stages. The data-planner populates these during Plan creation. Code-reviewer validates against them during QA.

#### Stage 5 → Stage 6 (Raw → Clean)
- **Artifact pattern:** `data/raw/{date}_{source}.parquet`
- **Expected columns:** [list key columns per dataset]
- **Row count range:** [estimated min-max]
- **Key invariants:** [e.g., "year column is not null", "ncessch is unique per year"]

#### Stage 6 → Stage 7 (Clean → Transform)
- **Artifact pattern:** `data/processed/{date}_{source}_clean.parquet`
- **Expected columns:** [columns surviving cleaning]
- **Row count range:** [post-cleaning estimate]
- **Key invariants:** [e.g., "no coded missing values remain in critical columns"]

#### Stage 7 → Stage 8 (Transform → Analysis)
- **Artifact pattern:** `data/processed/{date}_analysis.parquet`
- **Expected columns:** [final analysis columns including derived variables]
- **Row count range:** [post-transformation estimate]
- **Key invariants:** [e.g., "one row per school per year", "poverty_rate between 0 and 1"]

*Populate the bracketed fields with specifics for this analysis. Add or remove interface sections as needed based on the actual stage sequence.*

### Aggregation Specification

| Aggregation | Group By | Metrics | Output |
|-------------|----------|---------|--------|
| [Description] | [columns] | [functions] | [result name] |

### Analysis Approach

[Describe the analytical methodology: descriptive statistics, comparisons, trends, regressions, effect sizes, etc. This section provides the high-level analysis strategy that maps to Stage 8 task specifications in Plan_Tasks.md.]

---

## Output Specification

**Target Audience:** [technical/academic | policy | executive | general public | media | mixed]
(Determines report style and whether science-communication guidance is applied. Default: technical/academic)

### Notebook Structure

**Marimo Notebook Sections:**

1. **Setup & Imports** — Dependencies, configuration
2. **Data Loading** — Load from processed data files
3. **Data Overview** — Shape, types, sample
4. **Exploratory Analysis** — Distributions, patterns
5. **Main Analysis** — [Specific analysis sections]
6. **Visualizations** — Key charts and graphs
7. **Findings Summary** — Markdown synthesis
8. **Interactive Elements** — [If applicable: filters, selectors]

**UI Elements (if applicable):**

| Element | Type | Purpose |
|---------|------|---------|
| State selector | `mo.ui.dropdown` | Filter analysis by state |
| Year range | `mo.ui.range_slider` | Select year range |

### Report Structure

**Report Sections:**

1. **Executive Summary** — Key findings in 4-5 sentences
2. **Research Question** — What we set out to answer
3. **Data & Methods** — Sources, cleaning, analysis approach
4. **Findings** — Results with visualizations
5. **Limitations** — Caveats and constraints
6. **Data Sources** — Full citations

> **Note:** The report-writer agent (Stage 11) uses this Output Specification to structure the final report. The Research Outcomes section is particularly critical — each outcome is cross-checked against Key Findings in the report.

### Analysis Requirements

| Analysis | Type | Purpose | Output File |
|----------|------|---------|-------------|
| [e.g., Poverty-enrollment correlation] | [Correlation/Regression/Descriptive/Comparative] | [What question it answers] | `YYYY-MM-DD_[analysis-name].parquet` |

#### Modeling Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [e.g., Correlation method] | [e.g., Spearman rank] | [e.g., Non-normal distribution of poverty rates] |
| [e.g., Outlier treatment] | [e.g., Winsorize at 1st/99th percentile] | [e.g., Extreme values from data entry errors] |

### Visualization Requirements

| Figure | Type | Purpose | File Name |
|--------|------|---------|-----------|
| Enrollment trends | Line chart | Show change over time | `YYYY-MM-DD_enrollment_trends.png` |
| Distribution | Histogram | Show enrollment distribution | `YYYY-MM-DD_enrollment_dist.png` |

### Deliverables Checklist

| Deliverable | Location | Format |
|-------------|----------|--------|
| Plan document | `research/[project]/` | `.md` |
| Marimo notebook | `research/[project]/` | `.py` |
| Stakeholder report | `research/[project]/` | `.md` |
| Raw data | `research/[project]/data/raw/` | `.parquet` |
| Processed data | `research/[project]/data/processed/` | `.parquet` |
| Figures | `research/[project]/output/figures/` | `.png` |
| Discovery preliminary notes | `research/[project]/output/preliminary_notes/` | `.md` |

---

## Validation Checkpoints

### CP1: After Data Fetch

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count | ~10,000 | 0 or >100,000 |
| Columns | 15 | Missing critical columns |
| Years present | 2020, 2021, 2022 | Missing years |
| Critical variable missingness | <10% | >90% |

### CP2: After Cleaning

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count change | -5% to -15% | >50% loss |
| Suppression rate | <20% | >50% |
| Coded values remaining | 0 | Any -1, -2, -3 in analysis vars |

### CP3: After Transformation

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count | Same as CP2 | >90% loss |
| New columns exist | Yes | Missing derived columns |
| Unexpected NAs | 0 | >10% NAs in derived columns |

### CP4: Before Output

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| All planned figures generated | Yes | Missing figures |
| Report sections complete | Yes | Missing sections |
| Notebook runs without error | Yes | Execution errors |

### QA Tolerance Decisions

*Document project-specific tolerance thresholds and WHY they differ from defaults (if they do).
Code-reviewer uses these to calibrate BLOCKER vs WARNING severity.*

| Check | Default Threshold | Project Threshold | Rationale |
|-------|-------------------|-------------------|-----------|
| Suppression rate | <50% STOP | [Same or custom] | [Why, if different] |
| Join row loss | <10% acceptable | [Same or custom] | [Why, if different] |
| [Custom check] | [N/A] | [threshold] | [rationale] |

---

## Decisions Log

> **Frozen after Stage 4.5.** This section captures planning-phase decisions only. All runtime decisions made during Stages 5-12 are recorded in STATE.md `## Key Decisions Made`.

| Decision | Options Considered | Choice Made | Rationale |
|----------|-------------------|-------------|-----------|
| Data source | CCD vs. PSS | CCD | Research question focuses on public schools |
| Year range | 2018-2022 vs. 2020-2022 | 2020-2022 | Recent years sufficient; avoids COVID transition |
| Suppression handling | Exclude vs. Impute | Exclude | Imputation would introduce bias |

### Key Decision Detail

*For decisions where multiple valid approaches existed, document the full reasoning.
Skip this for obvious choices (e.g., "CCD because the question is about public schools").*

#### [Decision Title] (e.g., "Poverty Measure Selection")
**Question:** [The ambiguity that needed resolution]
**Options:**
1. [Option A] — [Implications if chosen]
2. [Option B] — [Implications if chosen]

**Resolution:** [Which option chosen]
**Rationale:** [Why]
**Decided By:** [User | Agent (within autonomous scope)]

---

## Risk Register

Document risks identified during discovery and planning, with mitigation strategies.

> **Frozen after Stage 4.5.** This section captures planning-phase risks identified during Stages 1-4. Risks discovered during execution (Stages 5-12) are recorded in STATE.md `## Runtime Risks`.

| Risk | Likelihood | Impact | Mitigation | Owner/Stage |
|------|------------|--------|------------|-------------|
| High suppression in key variable | Medium | High | Aggregate to district level if >30%; proceed with caveat if 30-50% | Stage 6 |
| COVID data quality issues (2020) | High | Medium | Exclude 2020 or document caveat prominently | Stage 3 |
| Cross-state variation in reporting | Medium | Medium | Check CRDC state-specific notes; restrict to comparable states | Stage 3 |

**Risk Categories:**
- **Data Availability:** Risk that needed data doesn't exist or has insufficient coverage
- **Data Quality:** Risk of high suppression, missingness, or known collection issues
- **Methodological:** Risk that analysis approach may not be valid for this data
- **Scope:** Risk that analysis scope is too broad or complex
- **Timeline:** Risk that data sources have unexpected lag times
- **QA:** Risk that secondary validation will find issues requiring revision or escalation

**Update Triggers:** See `full-pipeline-mode.md` > "Runtime Risk Tracking" for complete trigger list. Planning-phase risks are documented here; runtime risks go to STATE.md `## Runtime Risks`.

**When to Update (during planning, Stages 1-4 only):**
- **Stage 3 (Source Deep-Dive):** Add risks from source caveats that affect validity/completeness
- **Any planning stage:** Add risks when data definitions changed between years or other quality issues arise

> **Execution-phase risks** (Stage 5+), such as unexpected row loss or cardinality violations, are recorded in STATE.md `## Runtime Risks`.

---

## Trade-offs Accepted

*Explicit acknowledgment of what was sacrificed for what benefit.
Every non-trivial analysis involves trade-offs — document them here so stakeholders
and QA reviewers understand what was intentionally accepted.*

| We Accepted | In Order To | Downside |
|-------------|-------------|----------|
| [e.g., Older data (2022 vs 2023)] | [Use MEPS poverty measure] | [1-year lag] |
| [e.g., State-only scope] | [Avoid cross-state comparability issues] | [Less generalizable] |

---

## Data Citations

*Generated using domain context skill (per Domain Configuration)*

### Primary Data Source

> [Full citation for primary data source]

### Additional Sources

> [Citation 2]

> [Citation 3]

---

## File Manifest

*Updated at delivery*

| File | Path | Description |
|------|------|-------------|
| Plan | `research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Plan.md` | This document |
| Plan Tasks | `research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Plan_Tasks.md` | Executable task sequence (companion to Plan) |
| Notebook | `research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title].py` | Marimo analysis notebook |
| Report | `research/YYYY-MM-DD_[Title]/YYYY-MM-DD_[Title]_Report.md` | Stakeholder report |
| **Learnings** | `research/YYYY-MM-DD_[Title]/LEARNINGS.md` | **Session learnings (skeleton at Stage 4, incremental during 5-8, consolidated at Stage 12)** |
| Raw Data | `research/YYYY-MM-DD_[Title]/data/raw/YYYY-MM-DD_*.parquet` | Original data downloads |
| Processed Data | `research/YYYY-MM-DD_[Title]/data/processed/YYYY-MM-DD_*.parquet` | Cleaned data |
| Figures | `research/YYYY-MM-DD_[Title]/output/figures/YYYY-MM-DD_*.png` | Visualizations |
| Discovery Preliminary Notes | `research/YYYY-MM-DD_[Title]/output/preliminary_notes/{date}_stage{N}_{desc}.md` | Lossless agent findings from discovery phase (Stages 2, 3, 3.5) |
| Fetch Scripts | `research/YYYY-MM-DD_[Title]/scripts/stage5_fetch/*.py` | Data retrieval code |
| Clean Scripts | `research/YYYY-MM-DD_[Title]/scripts/stage6_clean/*.py` | Context application code |
| Transform Scripts | `research/YYYY-MM-DD_[Title]/scripts/stage7_transform/*.py` | Transformation code |
| Analysis & Viz Scripts | `research/YYYY-MM-DD_[Title]/scripts/stage8_analysis/*.py` | Statistical analysis and visualization code |
| **QA Scripts** | `research/YYYY-MM-DD_[Title]/scripts/cr/*.py` | **QA inspection scripts from code-reviewer** |
| Debug Scripts | `research/YYYY-MM-DD_[Title]/scripts/debug/*.py` | Diagnostic scripts (if any) |
