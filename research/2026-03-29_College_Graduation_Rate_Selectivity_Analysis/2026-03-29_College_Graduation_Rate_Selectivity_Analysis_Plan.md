---
title: "College Graduation Rate & Selectivity Analysis"
date: "2026-03-29"
version: ""
status: "planning"

must_haves:
  research_outcomes:
    - "Correlation between institutional selectivity (admission rate) and graduation rate is quantified with effect size and confidence interval"
    - "Descriptive profiles of institutions across selectivity bands (highly selective, selective, moderately selective, open/less selective) are produced with mean graduation rate, Pell share, URM share, student-faculty ratio, and retention rate"
    - "Cross-tabulation of selectivity bands with Pell Grant share quintiles characterizes how financial aid dependency varies by selectivity level"
    - "Cross-tabulation of selectivity bands with URM enrollment share quintiles characterizes how underserved population concentration varies by selectivity level"
    - "Institutions that outperform their selectivity-predicted graduation rate are identified and characterized by sector, Pell share, and URM share"
    - "OLS regression decomposing graduation rate variance into selectivity, student composition, and institutional resource components is estimated and reported with R-squared attribution"
    - "Sector differences (public vs. private nonprofit vs. private for-profit) in the selectivity-graduation relationship are characterized with descriptive statistics and visualizations"

  hypotheses:
    - id: "H1"
      statement: "Admission rate and graduation rate are strongly negatively correlated (|r| > 0.5), indicating that more selective institutions have higher graduation rates"
      basis: "Extensive prior literature on selectivity-graduation nexus (Astin & Oseguera 2005; Bound et al. 2010)"
    - id: "H2"
      statement: "After controlling for student composition (Pell share, URM share) and institutional resources (student-faculty ratio, instructional expenditure per FTE), the marginal effect of admission rate on graduation rate is substantially reduced"
      basis: "Chicken-or-egg argument: graduation rates partly reflect input quality, not institutional value-added"
    - id: "H3"
      statement: "Open-admission institutions with low Pell share outperform open-admission institutions with high Pell share, suggesting student financial need mediates outcomes even at low selectivity"
      basis: "Financial barriers literature (Dynarski 2003; Goldrick-Rab 2016)"

  artifacts:
    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"
      provides: "Interactive Marimo analysis notebook"
      min_lines: 300
      contains: "mo.md"

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_analysis.parquet"
      provides: "Merged analysis dataset with all variables"
      has_columns: ["unitid", "admit_rate", "completion_rate_150pct", "pell_share", "urm_share", "student_faculty_ratio", "selectivity_band"]

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md"
      provides: "Stakeholder report with findings and visualizations"
      contains: ["## Executive Summary", "## Limitations", "## Data Sources"]

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png"
      provides: "Scatter plot of graduation rate vs admission rate"
      min_size_kb: 50

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png"
      provides: "Box plot of graduation rates by selectivity band"
      min_size_kb: 50

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png"
      provides: "Heatmap of mean graduation rate by selectivity band x Pell quintile"
      min_size_kb: 50

  key_links:
    - from: "2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"
      to: "data/processed/2026-03-29_analysis.parquet"
      via: "pl.read_parquet() in data loading cell"
      pattern: "read_parquet.*analysis"

    - from: "2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"
      to: "output/figures/"
      via: "plotnine ggsave or matplotlib savefig"
      pattern: "(ggsave|savefig|write_image)"

    - from: "2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md"
      to: "output/figures/"
      via: "Markdown image references"
      pattern: "!\\[.*\\]\\(.*figures/"

    - from: "data/processed/2026-03-29_analysis.parquet"
      to: "data/raw/2026-03-29_*.parquet"
      via: "Cleaning and join transformations in stage 6-7 scripts"
      pattern: "read_parquet.*raw"
---

# College Graduation Rate & Selectivity Analysis

**Key Principles:**

1. **Task actions must be specific enough to execute without clarification.**
   - Invalid: "Process the data appropriately"
   - Valid: "Filter rows where enrollment == -1, save to data/processed/2026-03-29_ccd_clean.parquet"

2. **File paths must be explicit (no placeholders in the final plan).**
   - Invalid: `data/raw/[filename].parquet`
   - Valid: `data/raw/2026-03-29_ipeds_directory.parquet`

3. **Verification must be executable (not subjective).**
   - Invalid: "Data looks correct"
   - Valid: "Row count > 0 AND row count < 200000"

4. **Done criteria must be measurable.**
   - Invalid: "Task complete"
   - Valid: "CP1 PASSED, files saved to data/raw/"

---

## Companion Files

| File | Purpose |
|------|---------|
| `2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md` | Machine-readable executable task sequence -- contains all XML task blocks, wave execution rules, and task-specific operational details. Created by data-planner during Stage 4. |
| `STATE.md` | Operational state tracking during execution -- contains transformation progress, checkpoint status, runtime risks, QA findings summary, final review log, and session recovery context. Created by orchestrator during Stage 4. |
| `LEARNINGS.md` | Session learnings -- accumulated data quality insights, methodology lessons, and process observations. Created by orchestrator during Stage 4. |

> **Immutability Rule:** This Plan document and the companion Plan_Tasks.md are **100% frozen after Stage 4.5** (Plan Validation). No runtime updates of any kind. All execution state goes to STATE.md. All runtime decisions go to STATE.md Key Decisions Made. All runtime risks go to STATE.md Runtime Risks.

---

## Domain Configuration

**Active Domain:** education
**Query Skill:** education-data-query
**Explorer Skill:** education-data-explorer
**Context Skill:** education-data-context
**Coded Missing Values:** [-1, -2, -3]
**Suppression Code:** -3
**Suppression Threshold:** 0.5
**Year Column:** year
**Flag Years:** [2020, 2021]
**Governance Rules:** Cross-state assessment comparison is NEVER valid (not applicable to this analysis -- postsecondary data, no assessment scores used)

---

## Original Request & Clarifications

### Original Request

> I'm aware that graduation rates are often thought of as a key outcome for assessing a university/college's quality by the general public, but many researchers argue that there's a very strong question of chicken-or-the-egg in interpreting it that way: Are graduation rates high because the college actually did a good job in serving its students, or are graduation rates high because the college selectively admits students who are already highly competitive and academically prepared and likely to graduate/succeed anyway? I'd like to more critically explore this dynamic with data to better understand how correlated these things are, especially when thinking about additional complicating institutional factors like share of students on financial aid, other underserved or historically disadvantaged student population rates, etc. I'd like an analysis that helps provide an intuitive and holistic view on how these factors all relate to one another, and what implications that might have for broadly thinking about college 'quality' in general.

### Clarifications Received

1. **Analytical emphasis:** User wants descriptive analyses by selectivity bins as the PRIMARY analytical approach -- intuitive, easy to communicate
2. **Regression role:** Regression work should be SUPPLEMENTARY -- supporting evidence for the descriptive narrative, not the main story
3. **Communication goal:** The goal is easy communication of findings to broad audiences

### Research Question

How much of the variation in college graduation rates is attributable to institutional selectivity (admission rates) versus institutional effectiveness, and how do factors like financial aid dependency (Pell Grant share), underserved student populations (URM enrollment), institutional resources (spending, student-faculty ratio), and sector (public vs. private) complicate this relationship? What are the implications for interpreting graduation rates as a measure of college "quality"?

---

## Goal & Context

### Analysis Goal

Produce a descriptive, visually intuitive analysis that characterizes the relationship between institutional selectivity and graduation rates at U.S. four-year degree-granting institutions, with attention to how student composition (Pell share, URM share), institutional resources (student-faculty ratio, instructional expenditure per FTE), and sector (public/private nonprofit/for-profit) complicate the narrative of graduation rates as quality indicators. The primary analytical framework organizes institutions into selectivity bands and examines how outcomes and characteristics vary across those bands.

### Background Context

Graduation rates are widely used by rankings, policymakers, and the public as a proxy for institutional quality. However, a substantial body of higher education research (Astin & Oseguera 2005; Bound, Lovenheim & Turner 2010; Hoxby 2009) demonstrates that graduation rates are heavily confounded with selectivity -- institutions that admit already-prepared students naturally graduate more of them. This creates a "chicken-or-the-egg" problem: high graduation rates may reflect effective teaching and support, or simply selective admissions. This analysis uses publicly available federal data to make this relationship transparent and accessible to a general audience.

### Success Criteria

- [ ] Analysis dataset includes admission rate, graduation rate (150% FTFT), Pell share, URM share, student-faculty ratio, retention rate, and instructional expenditure per FTE for 4-year degree-granting institutions
- [ ] Selectivity bands are defined and populated: highly selective (<25% admit rate), selective (25-50%), moderately selective (50-75%), open/less selective (>75% or open admissions)
- [ ] At least 5 visualizations produced: scatter, boxplot, heatmap, correlation heatmap, sector comparison
- [ ] Outperformer institutions (positive residuals from selectivity-only model) are identified and profiled
- [ ] Report is written for a broad audience with clear, non-technical language

---

## Must-Haves (Goal-Backward Verification)

### Must-Haves Specification

```yaml
must_haves:
  research_outcomes:
    - "Correlation between institutional selectivity (admission rate) and graduation rate is quantified with effect size and confidence interval"
    - "Descriptive profiles of institutions across selectivity bands (highly selective, selective, moderately selective, open/less selective) are produced with mean graduation rate, Pell share, URM share, student-faculty ratio, and retention rate"
    - "Cross-tabulation of selectivity bands with Pell Grant share quintiles characterizes how financial aid dependency varies by selectivity level"
    - "Cross-tabulation of selectivity bands with URM enrollment share quintiles characterizes how underserved population concentration varies by selectivity level"
    - "Institutions that outperform their selectivity-predicted graduation rate are identified and characterized by sector, Pell share, and URM share"
    - "OLS regression decomposing graduation rate variance into selectivity, student composition, and institutional resource components is estimated and reported with R-squared attribution"
    - "Sector differences (public vs. private nonprofit vs. private for-profit) in the selectivity-graduation relationship are characterized with descriptive statistics and visualizations"

  hypotheses:
    - id: "H1"
      statement: "Admission rate and graduation rate are strongly negatively correlated (|r| > 0.5), indicating that more selective institutions have higher graduation rates"
      basis: "Extensive prior literature on selectivity-graduation nexus (Astin & Oseguera 2005; Bound et al. 2010)"
    - id: "H2"
      statement: "After controlling for student composition (Pell share, URM share) and institutional resources (student-faculty ratio, instructional expenditure per FTE), the marginal effect of admission rate on graduation rate is substantially reduced"
      basis: "Chicken-or-egg argument: graduation rates partly reflect input quality, not institutional value-added"
    - id: "H3"
      statement: "Open-admission institutions with low Pell share outperform open-admission institutions with high Pell share, suggesting student financial need mediates outcomes even at low selectivity"
      basis: "Financial barriers literature (Dynarski 2003; Goldrick-Rab 2016)"

  artifacts:
    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"
      provides: "Interactive Marimo analysis notebook"
      min_lines: 300
      contains: "mo.md"

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_analysis.parquet"
      provides: "Merged analysis dataset with all variables"
      has_columns: ["unitid", "admit_rate", "completion_rate_150pct", "pell_share", "urm_share", "student_faculty_ratio", "selectivity_band"]

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md"
      provides: "Stakeholder report with findings and visualizations"
      contains: ["## Executive Summary", "## Limitations", "## Data Sources"]

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png"
      provides: "Scatter plot of graduation rate vs admission rate"
      min_size_kb: 50

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png"
      provides: "Box plot of graduation rates by selectivity band"
      min_size_kb: 50

    - path: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png"
      provides: "Heatmap of mean graduation rate by selectivity band x Pell quintile"
      min_size_kb: 50

  key_links:
    - from: "2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"
      to: "data/processed/2026-03-29_analysis.parquet"
      via: "pl.read_parquet() in data loading cell"
      pattern: "read_parquet.*analysis"

    - from: "2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py"
      to: "output/figures/"
      via: "plotnine ggsave or matplotlib savefig"
      pattern: "(ggsave|savefig|write_image)"

    - from: "2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md"
      to: "output/figures/"
      via: "Markdown image references"
      pattern: "!\\[.*\\]\\(.*figures/"

    - from: "data/processed/2026-03-29_analysis.parquet"
      to: "data/raw/2026-03-29_*.parquet"
      via: "Cleaning and join transformations in stage 6-7 scripts"
      pattern: "read_parquet.*raw"
```

---

## Phase 1: Discovery Results

### Stage 2: Data Exploration

*Output from education-data-explorer skill*

**Data Level:** college-university (unitid)

**Candidate Endpoints:**

| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|
| `ipeds/colleges_ipeds_directory` | IPEDS | Institution directory: name, state, sector, control, degree-granting status, open admissions flag | 1980-2023 |
| `ipeds/colleges_ipeds_admissions-enrollment` | IPEDS | Admissions: applied, admitted, enrolled by sex | varies |
| `ipeds/colleges_ipeds_grad-rates` | IPEDS | 150% graduation rates by cohort, race, sex, Pell status | varies |
| `ipeds/colleges_ipeds_fall-enrollment-race_{year}` | IPEDS | Fall enrollment by race/ethnicity, sex, level, FT/PT (yearly files) | 1986-2022 |
| `ipeds/colleges_ipeds_student-faculty-ratio` | IPEDS | Student-to-faculty ratio | 2009-2020 |
| `ipeds/colleges_ipeds_fall-retention` | IPEDS | First-year retention rates (FT and PT) | 2003-2020 |
| `ipeds/colleges_ipeds_finance` | IPEDS | Revenue, expenses, assets by GASB/FASB standard | varies (through 2017) |
| `ipeds/colleges_ipeds_enrollment-fte` | IPEDS | Estimated FTE enrollment | varies |
| `fsa/colleges_fsa_grants` | FSA | Pell Grant recipients and disbursements by institution | 1999-2021 |
| `ipeds/colleges_ipeds_outcome-measures` | IPEDS | 8-year outcomes including PT and transfer students | 2015-2022 |

**Key Variables Identified:**

| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|
| `unitid` | All IPEDS/FSA | Integer (6-digit) | Institution identifier -- primary join key |
| `number_applied` | admissions-enrollment | Integer | Total applicants |
| `number_admitted` | admissions-enrollment | Integer | Total admitted |
| `sex` | admissions-enrollment | Integer code | Must filter sex==99 for totals |
| `completion_rate_150pct` | grad-rates | Float | 150% time graduation rate |
| `cohort` | grad-rates | Integer code | Subcohort: 2=bachelor's-seeking 4-yr, 8=Pell recipients, 12=total degree-seeking (UNDOCUMENTED -- verify during fetch) |
| `race` | grad-rates, fall-enrollment-race | Integer code | Race/ethnicity (1-9, 20, 99) |
| `enrollment_fall` | fall-enrollment-race | Integer | Fall enrollment headcount |
| `student_faculty_ratio` | student-faculty-ratio | Float | Student-to-faculty ratio |
| `retention_rate` | fall-retention | Float/String | First-year retention rate |
| `ftpt` | fall-retention | Integer code | 1=FT, 2=PT |
| `grant_type` | fsa grants | Integer code | 1=Pell Grant |
| `grant_recipients_unitid` | fsa grants | Integer | Number of Pell recipients at institution |
| `open_public` | directory | Integer | Open admissions indicator |
| `degree_granting` | directory | Integer | 1=degree-granting |
| `institution_level` | directory | Integer code | 4=four-year or above |
| `inst_control` | directory | Integer code | 1=public, 2=private nonprofit, 3=private for-profit |
| `est_fte` | enrollment-fte / finance | Float | Estimated FTE enrollment (denominator for per-FTE calcs) |
| `level_of_study` | fall-enrollment-race | Integer code | 1=undergraduate |
| `degree_seeking` | fall-enrollment-race | Integer code | 99=total |

**Variables Flagged for Deep-Dive:**

| Variable | Reason for Deep-Dive |
|----------|---------------------|
| `cohort` (grad-rates) | Subcohort codes undocumented in skill -- must verify from data during fetch |
| `retention_rate` | Some columns are String type, not numeric -- need casting |
| Finance data year cutoff | Portal finance data may only extend to 2017 |
| `completion_rate_150pct` | Coded values -1/-2/-3 must not be treated as zero |
| Fall enrollment race codes | Post-2010 codes 6 and 7 added; pre-2010 incompatible |

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| Scorecard EXCLUDED | pct_pell, pct_black, pct_hispanic NOT in Portal Scorecard; coverage bias correlates with selectivity | Use IPEDS + FSA exclusively |
| Admissions has only 9 columns | No admit_rate column -- must compute number_admitted/number_applied | Compute during cleaning |
| Finance data possibly limited to 2017 | 3+ year lag for expenditure data | Accept lag -- instructional spending is slow-moving; document in limitations |
| FTFT-only grad rates | Excludes transfers (~40%) and PT (~40%) students | Use as primary metric with caveat; Outcome Measures as robustness check |

**Stage 2 Completeness Assessment:**
- [x] All relevant data levels searched (college-university)
- [x] Multiple potential sources considered (IPEDS, FSA, Scorecard -- Scorecard excluded with rationale)
- [x] Year coverage verified for research question (target 2020-2021)
- [x] Variables requiring deep-dive explicitly flagged
- [x] Limitations documented

---

### Stage 3: Source Deep-Dive

*Output from education-data-source-ipeds and education-data-source-fsa skills*

**Sources Investigated:**

| Source | Skill Used | Relevance |
|--------|------------|-----------|
| IPEDS | `education-data-source-ipeds` | Primary: directory, admissions, grad rates, enrollment, SFR, retention, finance |
| FSA | `education-data-source-fsa` | Primary: Pell Grant recipient counts (for Pell share computation) |
| Scorecard | `education-data-source-scorecard` | EXCLUDED: key student characteristic variables not in Portal |

**Source-Specific Caveats:**

#### IPEDS

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| Grad rates track FTFT only (first-time, full-time, fall-entering) | Excludes ~40% transfers, ~40% PT students | Document limitation; note community colleges most affected; use Outcome Measures as robustness |
| institution_level uses code 4 for 4-year (NOT code 3) | Incorrect filter would miss all institutions | Use `institution_level == 4` (verified from IPEDS skill) |
| Finance data only through 2017 in Portal | 3+ year lag for expenditure variables | Accept lag -- instructional spending changes slowly; use est_fte from finance dataset for per-FTE calculations |
| Admissions data disaggregated by sex | Unfiltered data has ~3x duplicate rows per institution | Filter `sex == 99` for institution totals |
| Retention rate may be String type | Direct numeric operations will fail | Cast to Float64 during cleaning, handle coded values first |
| Fall enrollment race: yearly files (~3.5M rows each) | Large files; need careful filtering | Filter to sex==99, ftpt==99, level_of_study==1, degree_seeking==99, class_level==99 for institution-level UG totals |
| Open admissions flagged in Directory | open_public variable identifies institutions that don't use admissions criteria | Incorporate into selectivity band assignment (open admissions = "open/less selective" band regardless of admit rate) |

**Coded Value Mappings:**

| Variable | Code | Meaning | Action |
|----------|------|---------|--------|
| All numeric IPEDS | -1 | Missing/not reported | Replace with null |
| All numeric IPEDS | -2 | Not applicable | Replace with null |
| All numeric IPEDS | -3 | Suppressed for privacy | Replace with null |
| `race` | 1 | White | Include in domestic known-race total |
| `race` | 2 | Black | Include in URM numerator and denominator |
| `race` | 3 | Hispanic | Include in URM numerator and denominator |
| `race` | 4 | Asian | Include in domestic known-race denominator only |
| `race` | 5 | American Indian/Alaska Native | Include in URM numerator and denominator |
| `race` | 6 | Native Hawaiian/Pacific Islander | Include in URM numerator and denominator (post-2010) |
| `race` | 7 | Two or more races | Include in domestic known-race denominator only (post-2010) |
| `race` | 8 | Nonresident alien | EXCLUDE from URM calculation |
| `race` | 9 | Unknown race | EXCLUDE from URM calculation |
| `race` | 99 | Total | Use for institution-level totals when filtering |
| `sex` | 99 | Total | Filter to this for institution-level totals |
| `inst_control` | 1 | Public | Sector grouping |
| `inst_control` | 2 | Private nonprofit | Sector grouping |
| `inst_control` | 3 | Private for-profit | Sector grouping |
| `institution_level` | 4 | 4-year or above | Population filter |
| `degree_granting` | 1 | Degree-granting | Population filter |
| `ftpt` (retention) | 1 | Full-time | Use for primary retention rate |
| `grant_type` (FSA) | 1 | Federal Pell Grant | Filter for Pell recipients |

**Suppression Patterns:**

| Variable | Typical Suppression Rate | Threshold | Impact |
|----------|--------------------------|-----------|--------|
| `completion_rate_150pct` | ~5-10% for small cohorts | -3 code | Small institutions may have suppressed grad rates |
| `enrollment_fall` by race | ~10-15% at small institutions | -3 code | Affects URM share calculation for small institutions |
| `grant_recipients_unitid` | <5% | -1/-2/-3 codes | Minimal impact on Pell share |

**Cross-State Comparability:**

| Analysis Type | Valid Across States? | Notes |
|---------------|---------------------|-------|
| Graduation rates (IPEDS 150% FTFT) | Yes | Federal definition, consistent methodology |
| Admission rates | Yes | Computed from IPEDS standard fields |
| Pell share | Yes | Federal program, consistent definition |
| URM share | Yes | Federal race/ethnicity categories |
| Student-faculty ratio | Yes | IPEDS standard definition |
| Instructional expenditure | Conditional | GASB (public) vs FASB (private) -- compare within sector for levels; cross-sector for ratios normalized per-FTE |

**Critical Warnings:**

1. **Admissions data must be filtered to sex==99:** Unfiltered admissions data contains separate rows per sex, tripling the apparent number of institutions. Always filter `sex == 99` before computing admission rates.
2. **Coded missing values (-1, -2, -3) must NEVER be treated as zero:** These sentinel values in IPEDS numeric columns would corrupt all statistical calculations (e.g., mean graduation rate would be dragged toward zero by -1/-2/-3 values).
3. **Grad-rate subcohort codes are undocumented in skill:** Must examine actual data during Stage 5 fetch to identify correct cohort filter for bachelor's-seeking students at 4-year institutions.
4. **Finance data lag:** Instructional expenditure data may only be available through 2017 -- a 3-4 year lag relative to other variables targeting 2020-2021. This is acceptable because institutional spending patterns change slowly.

#### FSA

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| No enrollment denominator in FSA | Cannot compute Pell share from FSA alone | Join Pell recipients to IPEDS UG enrollment for denominator |
| Pell is undergrad-only | Denominator must be undergraduate enrollment, not total | Use IPEDS UG enrollment (level_of_study==1 from fall-enrollment-race, or enrollment-fte UG component) |
| Year-Round Pell post-2017 may inflate counts | Slight discontinuity in recipient counts | Use 2020 or 2021 year consistently; document caveat |
| allocation_flag and combined_flag | Multi-campus institutions may have consolidated reporting | Filter allocation_flag==0 OR document; most 4-yr institutions are single-campus |

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| Scorecard student characteristics not in Portal | Cannot use pct_pell, pct_black directly from Scorecard | Compute from IPEDS enrollment + FSA Pell data |
| Outcome Measures only from 2015 | Limited time range for robustness check | Use latest available year; note as supplementary |
| Grad-rate subcohort codes undocumented | Uncertainty about correct cohort filter | Resolve during Stage 5 by examining actual data |

**Stage 3 Completeness Assessment:**
- [x] All flagged variables investigated
- [x] Source-specific skill(s) loaded and consulted (IPEDS, FSA)
- [x] Coded values fully documented
- [x] Suppression patterns identified
- [x] Cross-state comparability assessed (all analyses valid cross-state)
- [x] Critical warnings documented with mitigations

---

### Phase 1 Overall Assessment

**Completeness Status:** COMPLETE

**Phase 1 Integration Checklist:**

- [x] All candidate endpoints documented with year coverage
- [x] All key variables documented with types and descriptions
- [x] All source-specific caveats captured
- [x] All coded value mappings complete
- [x] Suppression patterns documented
- [x] Cross-state comparability assessed (valid for all planned analyses)
- [x] Critical warnings have mitigation strategies
- [x] All LOW confidence findings documented with resolution plan (subcohort codes, finance year cutoff, retention string columns -- all resolved during Stage 5-6)

---

## Methodology Specification

### Data Acquisition Strategy

**Single Source or Multi-Source:** Multi-Source Join (8 IPEDS endpoints + 1 FSA endpoint)

**Join Strategy:**

| Left Source | Right Source | Join Key(s) | Expected Cardinality | Risks |
|-------------|--------------|-------------|---------------------|-------|
| IPEDS Directory (filtered) | IPEDS Admissions | `unitid` | 1:1 | Not all institutions report admissions (open admissions may not) |
| Core (Directory+Admissions) | IPEDS Grad Rates | `unitid` | 1:1 | Small institutions may have suppressed rates |
| Core+GradRates | FSA Pell | `unitid` | 1:1 | ~95% match expected |
| Core+GradRates+Pell | IPEDS Fall Enrollment Race (URM) | `unitid` | 1:1 | Pre-aggregated to institution level before join |
| Core+Demographics | IPEDS Student-Faculty Ratio | `unitid` | 1:1 | SFR available 2009-2020; high match expected |
| Core+Demographics+SFR | IPEDS Fall Retention | `unitid` | 1:1 | Retention data available 2003-2020 |
| Core+All | IPEDS Finance (instructional expenditure per FTE) | `unitid` | 1:1 | Finance data may be from 2017; accept lag |

### Query Specification

**Query 1: IPEDS Directory**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Institutional Directory |
| Mirror Paths | `ipeds/colleges_ipeds_directory` |
| File Type | Single-file (all years) |
| Years | 2020, 2021 |
| Filters (local) | `degree_granting == 1`, `institution_level == 4` |
| Variables | `unitid`, `year`, `inst_name`, `fips`, `inst_control`, `institution_level`, `degree_granting`, `open_public`, `hbcu`, `tribal_college` |
| Expected Records | ~3,000-4,000 per year (4-yr degree-granting) |

**Query 2: IPEDS Admissions-Enrollment**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Admissions and Enrollment |
| Mirror Paths | `ipeds/colleges_ipeds_admissions-enrollment` |
| File Type | Single-file (all years) |
| Years | 2020, 2021 |
| Filters (local) | `sex == 99` (totals only) |
| Variables | `unitid`, `year`, `sex`, `number_applied`, `number_admitted`, `number_enrolled_ft`, `number_enrolled_pt`, `number_enrolled_total` |
| Expected Records | ~2,000-3,000 per year (not all 4-yr institutions report admissions) |

**Query 3: IPEDS Graduation Rates**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Graduation Rates |
| Mirror Paths | `ipeds/colleges_ipeds_grad-rates` |
| File Type | Single-file (all years) |
| Years | 2020, 2021 |
| Filters (local) | `race == 99`, `sex == 99` (totals); cohort filter TBD (verify subcohort codes from data) |
| Variables | `unitid`, `year`, `cohort`, `race`, `sex`, `completion_rate_150pct`, `completers_150pct`, `cohort_count` |
| Expected Records | ~3,000-6,000 per year (multiple subcohorts per institution) |

**Query 4: FSA Grants (Pell)**

| Field | Value |
|-------|-------|
| Dataset | FSA Grants |
| Mirror Paths | `fsa/colleges_fsa_grants` |
| File Type | Single-file (all years) |
| Years | 2020, 2021 |
| Filters (local) | `grant_type == 1` (Pell Grant) |
| Variables | `unitid`, `year`, `fips`, `grant_type`, `grant_recipients_unitid`, `value_grants_disbursed_unitid` |
| Expected Records | ~5,000-6,000 per year |

**Query 5: IPEDS Fall Enrollment by Race (for URM share)**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Fall Enrollment Race |
| Mirror Paths | `ipeds/colleges_ipeds_fall-enrollment-race_2020` (yearly file) |
| File Type | Yearly |
| Years | 2020 |
| Filters (local) | `sex == 99`, `ftpt == 99`, `level_of_study == 1` (UG), `degree_seeking == 99`, `class_level == 99` |
| Variables | `unitid`, `year`, `race`, `sex`, `ftpt`, `level_of_study`, `degree_seeking`, `class_level`, `enrollment_fall` |
| Expected Records | ~3.5M raw rows per year; after filters ~50,000 (institution x race combinations) |

**Query 6: IPEDS Student-Faculty Ratio**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Student-Faculty Ratio |
| Mirror Paths | `ipeds/colleges_ipeds_student-faculty-ratio` |
| File Type | Single-file |
| Years | 2020 |
| Filters (local) | None |
| Variables | `unitid`, `year`, `fips`, `student_faculty_ratio` |
| Expected Records | ~4,000-6,000 |

**Query 7: IPEDS Fall Retention**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Fall Retention |
| Mirror Paths | `ipeds/colleges_ipeds_fall-retention` |
| File Type | Single-file |
| Years | 2020 |
| Filters (local) | `ftpt == 1` (full-time) |
| Variables | `unitid`, `year`, `ftpt`, `retention_rate` |
| Expected Records | ~4,000-6,000 |

**Query 8: IPEDS Finance (Instructional Expenditure)**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Finance |
| Mirror Paths | `ipeds/colleges_ipeds_finance` |
| File Type | Single-file |
| Years | 2017 (latest available in Portal) |
| Filters (local) | None initially; will extract instructional expenditure and est_fte |
| Variables | `unitid`, `year`, `fips`, instructional expenditure columns (TBD -- examine during fetch), `est_fte` |
| Expected Records | ~6,000-8,000 |

### Data Freshness Check

**IMPORTANT:** This section is populated during Stage 5 (CP1 validation).

| Source | Requested Years | Latest Available | Lag | Impact | User Notified? |
|--------|-----------------|------------------|-----|--------|----------------|
| IPEDS Directory | 2020-2021 | TBD (Stage 5) | TBD | TBD | N/A |
| IPEDS Admissions | 2020-2021 | TBD | TBD | TBD | N/A |
| IPEDS Grad Rates | 2020-2021 | TBD | TBD | TBD | N/A |
| FSA Grants | 2020-2021 | 2021 | 0 | Current | N/A |
| IPEDS Fall Enrollment Race | 2020 | 2022 | 0 | Current | N/A |
| IPEDS Student-Faculty Ratio | 2020 | 2020 | 0 | Current | N/A |
| IPEDS Fall Retention | 2020 | 2020 | 0 | Current | N/A |
| IPEDS Finance | 2017 | 2017 | 3-4 years | Accepted (slow-moving metric) | Will confirm at Stage 5 |

**COVID-19 Data Quality Considerations:**

| Year | Data Quality Impact | Mitigation |
|------|-------------------|------------|
| 2020 | COVID disruptions may affect enrollment counts, admissions processes (test-optional policies emerged), and institutional finances. Graduation rates for 2020 reflect cohorts entering ~2014 (150% time = 6 years), so the outcome variable itself is pre-COVID. | Graduation rates are largely unaffected (pre-COVID cohorts). Admissions and enrollment may show COVID effects. Document as caveat. Flag year in analysis. |
| 2021 | Partial recovery. Admissions may still reflect test-optional policies. | Same as 2020 -- document and flag. |

### Data Cleaning Specification

**Coded Value Handling:**

| Variable | Codes to Filter | Rationale |
|----------|-----------------|-----------|
| `number_applied`, `number_admitted` | -1, -2, -3 | Missing/not applicable/suppressed -- cannot compute admission rate |
| `completion_rate_150pct` | -1, -2, -3 | Missing/not applicable/suppressed graduation rate |
| `enrollment_fall` | -1, -2, -3 | Missing enrollment counts -- exclude from URM calculation |
| `student_faculty_ratio` | -1, -2, -3 | Missing ratio |
| `retention_rate` | -1, -2, -3 (after String-to-Float cast) | Missing retention data |
| `grant_recipients_unitid` | -1, -2, -3 | Missing/suppressed Pell recipient count |

**Suppression Handling:**

- Expected suppression rate: <10% overall
- Threshold for STOP condition: 50%
- If exceeded: Escalate to user -- consider aggregating or narrowing scope

### Transformation Sequence

#### Wave-Based Task Table

| Wave | Step | Task Name | Operation | Expected Outcome | Script Path | Cardinality | Depends On |
|------|------|-----------|-----------|------------------|-------------|-------------|------------|
| 1 | 1.1 | fetch-directory | Fetch IPEDS Directory | ~8,000 rows (2 yrs x ~4,000 institutions) | `scripts/stage5_fetch/01_fetch-directory.py` | N/A | -- |
| 1 | 1.2 | fetch-admissions | Fetch IPEDS Admissions | ~6,000 rows (2 yrs x ~3,000) | `scripts/stage5_fetch/02_fetch-admissions.py` | N/A | -- |
| 1 | 1.3 | fetch-grad-rates | Fetch IPEDS Grad Rates | ~12,000 rows (multiple subcohorts) | `scripts/stage5_fetch/03_fetch-grad-rates.py` | N/A | -- |
| 1 | 1.4 | fetch-fsa-grants | Fetch FSA Pell Grants | ~6,000 rows | `scripts/stage5_fetch/04_fetch-fsa-grants.py` | N/A | -- |
| 1 | 1.5 | fetch-enrollment-race | Fetch IPEDS Fall Enrollment Race 2020 | ~50,000 rows (after initial filters) | `scripts/stage5_fetch/05_fetch-enrollment-race.py` | N/A | -- |
| 2 | 2.1 | fetch-sfr | Fetch IPEDS Student-Faculty Ratio | ~5,000 rows | `scripts/stage5_fetch/06_fetch-sfr.py` | N/A | -- |
| 2 | 2.2 | fetch-retention | Fetch IPEDS Fall Retention | ~5,000 rows | `scripts/stage5_fetch/07_fetch-retention.py` | N/A | -- |
| 2 | 2.3 | fetch-finance | Fetch IPEDS Finance | ~7,000 rows | `scripts/stage5_fetch/08_fetch-finance.py` | N/A | -- |
| 3 | 3.1 | clean-directory | Clean Directory: filter to 4-yr degree-granting, handle coded values | ~3,500 rows (single target year) | `scripts/stage6_clean/01_clean-directory.py` | N/A | 1.1 |
| 3 | 3.2 | clean-admissions | Clean Admissions: filter sex==99, compute admit_rate, handle coded values | ~2,500 rows | `scripts/stage6_clean/02_clean-admissions.py` | N/A | 1.2 |
| 3 | 3.3 | clean-grad-rates | Clean Grad Rates: identify correct cohort, filter race==99/sex==99, handle coded values | ~3,000 rows | `scripts/stage6_clean/03_clean-grad-rates.py` | N/A | 1.3 |
| 3 | 3.4 | clean-fsa-grants | Clean FSA: filter grant_type==1, handle coded values | ~5,000 rows | `scripts/stage6_clean/04_clean-fsa-grants.py` | N/A | 1.4 |
| 3 | 3.5 | clean-enrollment-race | Clean Enrollment Race: compute URM share per institution | ~3,500 rows (1 per institution) | `scripts/stage6_clean/05_clean-enrollment-race.py` | N/A | 1.5 |
| 4 | 4.1 | clean-sfr | Clean SFR: handle coded values, cast types | ~4,000 rows | `scripts/stage6_clean/06_clean-sfr.py` | N/A | 2.1 |
| 4 | 4.2 | clean-retention | Clean Retention: filter ftpt==1, cast String to Float, handle coded values | ~3,500 rows | `scripts/stage6_clean/07_clean-retention.py` | N/A | 2.2 |
| 4 | 4.3 | clean-finance | Clean Finance: extract instructional expenditure, compute per-FTE, handle coded values | ~6,000 rows | `scripts/stage6_clean/08_clean-finance.py` | N/A | 2.3 |
| 5 | 5.1 | join-core | Join Directory + Admissions + Grad Rates | ~2,000-2,500 rows | `scripts/stage7_transform/01_join-core.py` | 1:1 on unitid | 3.1, 3.2, 3.3 |
| 5 | 5.2 | join-demographics | Join Core + Pell + URM | ~2,000-2,400 rows | `scripts/stage7_transform/02_join-demographics.py` | 1:1 on unitid | 5.1, 3.4, 3.5 |
| 6 | 6.1 | join-resources | Join Demographics + SFR + Retention + Finance | ~1,800-2,200 rows | `scripts/stage7_transform/03_join-resources.py` | 1:1 on unitid | 5.2, 4.1, 4.2, 4.3 |
| 6 | 6.2 | create-bands | Create selectivity bands + Pell/URM quintiles | Same row count + 3 new columns | `scripts/stage7_transform/04_create-bands.py` | N/A | 6.1 |
| 7 | 7.1 | descriptive-by-selectivity | Descriptive stats by selectivity band | Summary table ~4-5 rows | `scripts/stage8_analysis/01_descriptive-by-selectivity.py` | N/A | 6.2 |
| 7 | 7.2 | crosstab-selectivity-pell | Cross-tab selectivity band x Pell quintile | 4x5 table of mean grad rates | `scripts/stage8_analysis/02_crosstab-selectivity-pell.py` | N/A | 6.2 |
| 7 | 7.3 | crosstab-selectivity-urm | Cross-tab selectivity band x URM quintile | 4x5 table of mean grad rates | `scripts/stage8_analysis/03_crosstab-selectivity-urm.py` | N/A | 6.2 |
| 8 | 8.1 | correlation-matrix | Correlation matrix of all continuous variables | Correlation table | `scripts/stage8_analysis/04_correlation-matrix.py` | N/A | 6.2 |
| 8 | 8.2 | outperformers | Identify outperformer institutions (positive residuals from selectivity-only OLS) | Outperformer list + characteristics | `scripts/stage8_analysis/05_outperformers.py` | N/A | 6.2 |
| 9 | 9.1 | regression-models | Hierarchical OLS regression (supplementary) | Regression results table | `scripts/stage8_analysis/06_regression-models.py` | N/A | 6.2 |
| 9 | 9.2 | sector-comparison | Sector-level descriptive analysis | Summary by sector | `scripts/stage8_analysis/07_sector-comparison.py` | N/A | 6.2 |
| 10 | 10.1 | viz-scatter-grad-admit | Scatter: graduation rate vs admission rate | Figure file | `scripts/stage8_analysis/08_viz-scatter-grad-admit.py` | N/A | 6.2 |
| 10 | 10.2 | viz-boxplot-selectivity | Boxplot: grad rate by selectivity band | Figure file | `scripts/stage8_analysis/09_viz-boxplot-selectivity.py` | N/A | 6.2 |
| 10 | 10.3 | viz-heatmap-selectivity-pell | Heatmap: selectivity band x Pell quintile | Figure file | `scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py` | N/A | 7.2 |
| 10 | 10.4 | viz-correlation-heatmap | Heatmap: correlation matrix | Figure file | `scripts/stage8_analysis/11_viz-correlation-heatmap.py` | N/A | 8.1 |
| 10 | 10.5 | viz-sector-comparison | Bar chart: sector comparison | Figure file | `scripts/stage8_analysis/12_viz-sector-comparison.py` | N/A | 9.2 |
| 11 | 11.1 | viz-residual-scatter | Scatter: actual vs predicted grad rate (outperformers highlighted) | Figure file | `scripts/stage8_analysis/13_viz-residual-scatter.py` | N/A | 8.2 |

**Script Path Convention:**
- Pattern: `scripts/stage{N}_{type}/{step:02d}_{task-name}.py`
- Stage 5 (fetch) -> `scripts/stage5_fetch/`
- Stage 6 (clean) -> `scripts/stage6_clean/`
- Stage 7 (transform) -> `scripts/stage7_transform/`
- Stage 8 (analysis & viz) -> `scripts/stage8_analysis/`

> **Full Task Definitions:** The complete XML task specifications for each entry in this table are in the companion `Plan_Tasks.md` file. See `agent_reference/PLAN_TASKS_TEMPLATE.md` for the task definition template.

### Stage Interface Specifications

#### Stage 5 -> Stage 6 (Raw -> Clean)
- **Artifact pattern:** `data/raw/2026-03-29_{source}.parquet`
- **Expected columns:** unitid, year + source-specific columns per query specification
- **Row count range:** 3,000-50,000 per dataset (varies by source)
- **Key invariants:** year column is not null; unitid is present in all files

#### Stage 6 -> Stage 7 (Clean -> Transform)
- **Artifact pattern:** `data/processed/2026-03-29_{source}_clean.parquet`
- **Expected columns:** unitid + cleaned/computed variables (admit_rate, completion_rate_150pct, pell_recipients, urm_share, etc.)
- **Row count range:** 2,500-5,000 per dataset (after filtering to target year and removing coded values)
- **Key invariants:** no coded missing values (-1, -2, -3) remain in critical numeric columns; unitid is unique per dataset

#### Stage 7 -> Stage 8 (Transform -> Analysis)
- **Artifact pattern:** `data/processed/2026-03-29_analysis.parquet`
- **Expected columns:** unitid, inst_name, inst_control, admit_rate, completion_rate_150pct, pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte, selectivity_band, pell_quintile, urm_quintile, open_public
- **Row count range:** 1,800-2,500 (institutions with complete data across all sources)
- **Key invariants:** one row per institution (unitid is unique); selectivity_band is non-null for all rows; admit_rate between 0 and 100 (or null for open admissions institutions included via open_public flag); completion_rate_150pct between 0 and 100

### Aggregation Specification

| Aggregation | Group By | Metrics | Output |
|-------------|----------|---------|--------|
| URM share | `unitid` | SUM(enrollment_fall) for URM races (2,3,5,6) / SUM(enrollment_fall) for domestic known-race (1,2,3,4,5,6,7) | `urm_share` column (0-1 proportion) |
| Pell share | `unitid` | `grant_recipients_unitid` / IPEDS UG enrollment | `pell_share` column (0-1 proportion) |
| Instr. expend per FTE | `unitid` | instructional expenditure / `est_fte` | `instr_expend_per_fte` column |
| Descriptive by band | `selectivity_band` | MEAN, MEDIAN, SD, N for all continuous variables | Summary table |
| Cross-tab | `selectivity_band`, `pell_quintile` | MEAN(completion_rate_150pct), N | 4x5 matrix |

### Analysis Approach

**PRIMARY: Descriptive analyses by selectivity bands**

The core analytical framework organizes institutions into four selectivity bands based on admission rate (or open admissions flag):

| Band | Definition | Expected N |
|------|-----------|-----------|
| Highly Selective | admit_rate < 25% | ~150-250 |
| Selective | 25% <= admit_rate < 50% | ~300-500 |
| Moderately Selective | 50% <= admit_rate < 75% | ~500-800 |
| Open/Less Selective | admit_rate >= 75% OR open_public == 1 | ~500-800 |

For each band, compute:
- Mean, median, SD, IQR, and N of: graduation rate, Pell share, URM share, student-faculty ratio, retention rate, instructional expenditure per FTE
- Sector composition (% public, % private nonprofit, % for-profit)

Cross-tabulations:
- Selectivity band x Pell quintile: mean graduation rate in each cell
- Selectivity band x URM quintile: mean graduation rate in each cell

Outperformer identification:
- Fit OLS: completion_rate_150pct ~ admit_rate (selectivity-only model)
- Residuals > 1 SD above predicted = "outperformers"
- Profile outperformers by sector, Pell share, URM share, SFR

**SUPPLEMENTARY: Hierarchical OLS regression**

Three nested models to decompose variance:
1. Model 1: completion_rate_150pct ~ admit_rate (selectivity only)
2. Model 2: + pell_share + urm_share (add student composition)
3. Model 3: + student_faculty_ratio + retention_rate + instr_expend_per_fte (add institutional resources)

Report R-squared for each model to show how much variance is "explained away" by adding student composition and resource controls. Use robust (HC1) standard errors. Include sector fixed effects (inst_control dummies) in Model 3 variant.

**Sector analysis:**
- Repeat descriptive profiles within each sector (public, private nonprofit, private for-profit)
- Compare selectivity-graduation slopes across sectors

---

## Output Specification

**Target Audience:** general public / mixed (descriptive, intuitive, easy-to-communicate findings per user clarification)

### Notebook Structure

**Marimo Notebook Sections:**

1. **Setup & Imports** -- Dependencies, configuration
2. **Data Loading** -- Load from data/processed/2026-03-29_analysis.parquet
3. **Data Overview** -- Shape, types, sample; selectivity band distribution
4. **Selectivity Band Profiles** -- Descriptive statistics by band (primary analysis)
5. **Cross-Tabulations** -- Selectivity x Pell quintile; Selectivity x URM quintile
6. **Correlation Analysis** -- Full correlation matrix; key relationships highlighted
7. **Outperformer Analysis** -- Institutions beating their selectivity-predicted grad rate
8. **Regression Summary** -- Hierarchical OLS results (supplementary)
9. **Sector Comparison** -- Public vs private nonprofit vs for-profit
10. **Visualizations** -- All 6 figures with contextual narrative
11. **Findings Summary** -- Markdown synthesis answering research question

### Report Structure

**Report Sections:**

1. **Executive Summary** -- Key findings in 4-5 sentences accessible to general audience
2. **Research Question** -- The chicken-or-the-egg problem with graduation rates
3. **Data & Methods** -- Sources (IPEDS, FSA), year (2020), population (4-yr degree-granting), selectivity band definitions, analytical approach
4. **Key Findings** -- Organized by selectivity bands with visualizations embedded
5. **Outperformers: Beating the Odds** -- Institutions that succeed despite low selectivity
6. **The Role of Student Composition** -- How Pell share and URM share complicate the picture
7. **Supplementary: Regression Evidence** -- What controls "explain away"
8. **Implications for Thinking About College Quality** -- Synthesis answering the user's question
9. **Limitations** -- FTFT-only grad rates, finance data lag, COVID caveats, cross-sectional design
10. **Data Sources** -- Full citations for IPEDS and FSA

### Analysis Requirements

| Analysis | Type | Purpose | Output File |
|----------|------|---------|-------------|
| Descriptive by selectivity band | Descriptive | Primary: characterize how institutions differ across selectivity levels | `2026-03-29_descriptive_by_selectivity.parquet` |
| Cross-tab selectivity x Pell | Descriptive | How financial aid dependency interacts with selectivity | `2026-03-29_crosstab_selectivity_pell.parquet` |
| Cross-tab selectivity x URM | Descriptive | How underserved population share interacts with selectivity | `2026-03-29_crosstab_selectivity_urm.parquet` |
| Correlation matrix | Descriptive | Quantify pairwise relationships among all variables | `2026-03-29_correlation_matrix.parquet` |
| Outperformer identification | Descriptive/Modeling | Identify institutions beating selectivity-predicted grad rate | `2026-03-29_outperformers.parquet`, `2026-03-29_selectivity_model.parquet` |
| Hierarchical OLS regression | Modeling (supplementary) | Decompose variance in graduation rates | `2026-03-29_regression_results.parquet` |
| Sector comparison | Descriptive | Compare selectivity-graduation relationship across sectors | `2026-03-29_sector_comparison.parquet` |

#### Modeling Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary metric | Descriptive by selectivity bands | User preference: intuitive, easy to communicate |
| Regression role | Supplementary | User clarification: supporting evidence only |
| Graduation rate measure | 150% FTFT (completion_rate_150pct) | Federal standard; most comparable across institutions |
| Standard errors | HC1 robust | Heteroscedasticity likely across institution types |
| Outperformer threshold | 1 SD above predicted | Balances specificity with sufficient N |
| Selectivity bands | <25%, 25-50%, 50-75%, >=75%/open | Standard categories used in higher ed research |
| URM definition | Black + Hispanic + AIAN + NHPI | Standard federal underrepresented minority definition |
| Pell share denominator | UG enrollment from IPEDS fall enrollment race (race==99 total) | Best available undergraduate denominator |
| Cross-year finance join | 2017 finance data joined to 2020 analysis | Instructional spending is slow-moving; acceptable lag per literature |

### Visualization Requirements

| Figure | Type | Purpose | File Name |
|--------|------|---------|-----------|
| Grad rate vs admission rate | Scatter + trend | Core relationship visualization (H1) | `2026-03-29_grad_rate_vs_admission_rate.png` |
| Grad rate by selectivity band | Box plot + jitter | Distribution within each band | `2026-03-29_boxplot_grad_rate_by_selectivity.png` |
| Selectivity x Pell heatmap | Tile heatmap | How Pell share interacts with selectivity | `2026-03-29_heatmap_selectivity_pell.png` |
| Correlation heatmap | Tile heatmap | All pairwise relationships | `2026-03-29_correlation_heatmap.png` |
| Sector comparison | Faceted scatter or bar | Sector differences | `2026-03-29_sector_comparison.png` |
| Actual vs predicted | Scatter + reference line | Outperformer visualization | `2026-03-29_actual_vs_predicted.png` |

### Deliverables Checklist

| Deliverable | Location | Format |
|-------------|----------|--------|
| Plan document | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/` | `.md` |
| Plan Tasks | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/` | `.md` |
| Marimo notebook | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/` | `.py` |
| Stakeholder report | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/` | `.md` |
| Raw data (8 files) | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/` | `.parquet` |
| Processed data (8 cleaned + 4 joined/analysis) | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/` | `.parquet` |
| Analysis results (7 files) | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/` | `.parquet` |
| Figures (6 files) | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/` | `.png` |

---

## Validation Checkpoints

### CP1: After Data Fetch

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count (per dataset) | 3,000-50,000 (varies) | 0 rows |
| Required columns | Per query specification | Missing critical columns (unitid, year, primary variable) |
| Years present | [2020] or [2020, 2021] | No target years present |
| Critical variable missingness | <10% for identifiers | >90% null for primary variable |
| Finance data year | 2017 (possibly later) | No years available |
| Grad rate subcohort codes | Documented in log | Cannot identify bachelor's-seeking cohort |

### CP2: After Cleaning

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count change | -10% to -60% (filtering to target population + year) | >90% loss |
| Suppression rate | <10% overall | >50% |
| Coded values remaining | 0 in critical columns | Any -1, -2, -3 in analysis variables |
| admit_rate range | 0-100 | Values outside 0-100 |
| completion_rate_150pct range | 0-100 | Values outside 0-100 |
| pell_share range | 0-1 | Values > 1.5 (allows slight overcount) |
| urm_share range | 0-1 | Values > 1 |

### CP3: After Transformation

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| Join row count | LEFT join preserves left rows | >90% loss on any join |
| Join key overlap | >60% for each source | <30% overlap (key mismatch) |
| Fan-out | None (all 1:1 joins) | Result rows > left rows (indicates duplicate keys) |
| selectivity_band distribution | 4 non-null categories | Any band with N < 50 |
| Final analysis N | 1,500-2,500 | <500 (insufficient for analysis) |
| New columns exist | selectivity_band, pell_quintile, urm_quintile | Missing derived columns |

### CP4: Before Output

**Expected Values:**

| Check | Expected | STOP If |
|-------|----------|---------|
| All 7 analysis outputs generated | Yes | Missing analysis files |
| All 6 figures generated | Yes | Missing figure files |
| Figure file sizes | >50 KB each | Any figure < 10 KB |
| Report sections complete | All 10 sections | Missing Executive Summary or Key Findings |
| Notebook runs without error | Yes | Execution errors |
| Research Outcomes addressed | All 7 | Any outcome not addressed |

### QA Tolerance Decisions

| Check | Default Threshold | Project Threshold | Rationale |
|-------|-------------------|-------------------|-----------|
| Suppression rate | <50% STOP | <50% (default) | Standard threshold; suppression expected to be low for institutional-level data |
| Join row loss | <10% acceptable | <40% acceptable | Multiple LEFT joins -- some institutions will not appear in all datasets; 40% loss across 7+ joins is realistic |
| Finance data year lag | 3+ years triggers notification | Accepted (2017 data) | Pre-approved in Plan: instructional spending is slow-moving |
| Minimum N per selectivity band | N/A | N >= 100 | Need sufficient N for meaningful group statistics |
| Minimum N per cross-tab cell | N/A | N >= 10 (WARN if < 10) | Small cells get reported but flagged |
| Listwise deletion for regression | <10% default | <30% acceptable | Many variables from different sources -- complete cases across 7+ variables will lose more rows than typical |

---

## Decisions Log

> **Frozen after Stage 4.5.** This section captures planning-phase decisions only.

| Decision | Options Considered | Choice Made | Rationale |
|----------|-------------------|-------------|-----------|
| Primary data source | IPEDS + FSA vs. Scorecard vs. IPEDS-only | IPEDS + FSA | Scorecard missing key variables in Portal; FSA provides Pell recipient counts |
| Scorecard inclusion | Include vs. Exclude | Exclude | pct_pell, pct_black, pct_hispanic NOT in Portal; coverage bias correlates with selectivity |
| Primary analytical approach | Descriptive by bands vs. Regression-first | Descriptive by bands | User clarification: intuitive, easy to communicate |
| Target year | 2020 vs. 2021 vs. multi-year | 2020 (primary) | Best overlap across all sources; 2021 as backup |
| Graduation rate measure | 150% FTFT vs. 200% vs. Outcome Measures | 150% FTFT | Federal standard; most widely available; OM as robustness only |
| URM definition | Black+Hispanic only vs. including AIAN+NHPI | Include AIAN+NHPI (codes 2,3,5,6) | Standard federal URM definition; inclusive |
| Finance data year | 2017 (latest available) vs. Exclude finance | Accept 2017 with lag caveat | Instructional spending changes slowly; better to include with caveat than exclude |
| Selectivity band cutpoints | Equal thirds vs. <25/25-50/50-75/>75 | <25/25-50/50-75/>75 with open admissions | Standard in higher ed research; aligns with common reporting |
| Pell share denominator | Total enrollment vs. UG enrollment | UG enrollment (from fall-enrollment-race, race==99) | Pell is UG-only; denominator should match |
| Open admissions handling | Exclude vs. Separate band vs. Include in >75% | Include in Open/Less Selective band | open_public flag overrides admit_rate for these institutions |

### Key Decision Detail

#### Scorecard Exclusion
**Question:** Should College Scorecard data be used for student demographic characteristics?
**Options:**
1. Include Scorecard -- provides pct_pell, pct_black, pct_hispanic directly
2. Exclude Scorecard -- compute from IPEDS enrollment + FSA Pell data

**Resolution:** Option 2 -- Exclude Scorecard
**Rationale:** Stage 2-3 discovery confirmed that pct_pell, pct_black, and pct_hispanic are NOT available in the Portal's Scorecard datasets. Furthermore, Scorecard coverage is biased: 30-50% coverage at selective institutions vs. 70-90%+ at open-access institutions, meaning any Scorecard-based analysis would systematically undercount selective institutions -- directly undermining the core research question about selectivity.
**Decided By:** Agent (within autonomous scope, based on discovery findings)

#### Analytical Emphasis
**Question:** Should the analysis lead with regression or descriptive analyses?
**Options:**
1. Regression-first with descriptive support
2. Descriptive-first with regression support

**Resolution:** Option 2 -- Descriptive-first
**Rationale:** User explicitly requested "intuitive and holistic view" and "easy communication of findings to broad audiences." Selectivity bands are the organizing framework; regression provides supplementary variance decomposition.
**Decided By:** User (via clarification)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner/Stage |
|------|------------|--------|------------|-------------|
| Grad-rate subcohort codes differ from expected | Medium | High | Examine cohort value_counts during Stage 5 fetch; adapt filter based on observed data | Stage 5 (Task 1.3) |
| Finance data unavailable or extremely limited | Low | Medium | If finance endpoint fails or has <1,000 rows, proceed without instr_expend_per_fte; remove from regression Model 3 | Stage 5 (Task 2.3) |
| High join attrition across 7+ LEFT joins | Medium | Medium | Track match rates at each join; if final analysis N < 500, switch to INNER join on core variables only (admit_rate + grad_rate) and use separate analyses for each supplementary variable | Stage 7 (Tasks 5.1-6.1) |
| Few for-profit 4-year institutions in data | High | Low | If N < 30 for for-profit sector, collapse to public vs. private (combining NP and FP) for sector comparison | Stage 8 (Task 9.2) |
| COVID-19 effects on 2020 admissions data | Medium | Low | Graduation rates reflect pre-COVID cohorts (entered ~2014); admissions may show test-optional effects. Document as limitation. | Stage 6-8 |
| Retention rate String type causing cleaning errors | Medium | Medium | Check dtype during cleaning; cast with strict=False to handle gracefully | Stage 6 (Task 4.2) |
| Sparse cross-tab cells (N < 10) | Medium | Low | Report cells with N < 10 but flag with warning; do not draw conclusions from sparse cells | Stage 8 (Tasks 7.2, 7.3) |

---

## Trade-offs Accepted

| We Accepted | In Order To | Downside |
|-------------|-------------|----------|
| FTFT-only graduation rates | Use the most widely available and comparable metric | Excludes ~40% transfers and ~40% PT students; most impacts community colleges and open-access institutions |
| 2017 finance data (3-year lag) | Include institutional resource measures in analysis | Instructional spending may have changed modestly; documented as limitation |
| Cross-sectional design (single year) | Keep analysis scope manageable and intuitive | Cannot assess trends or make causal claims about changes over time |
| LEFT joins allowing nulls | Maximize analysis sample size and retain institutions even with partial data | Some analyses (regression) will have smaller complete-case N; documented via listwise deletion logging |
| No causal identification strategy | Focus on descriptive characterization per user request | Cannot claim selectivity "causes" higher graduation rates -- only association |
| Excluding Scorecard | Avoid coverage bias that would undermine selectivity analysis | Lose some convenience variables (pct_pell directly); must compute from components |

---

## Data Citations

### Primary Data Sources

> National Center for Education Statistics. (2022). Integrated Postsecondary Education Data System (IPEDS). U.S. Department of Education. Retrieved from Education Data Portal (Urban Institute), https://educationdata.urban.org.

> U.S. Department of Education, Federal Student Aid. (2022). Title IV Program Volume Reports: Pell Grant Data. Retrieved from Education Data Portal (Urban Institute), https://educationdata.urban.org.

### Additional Sources

> Urban Institute. (2022). Education Data Portal. https://educationdata.urban.org. Accessed via Hugging Face mirror: https://huggingface.co/datasets/brhkim/education_data_portal_mirror.

---

## File Manifest

| File | Path | Description |
|------|------|-------------|
| Plan | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md` | This document |
| Plan Tasks | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan_Tasks.md` | Executable task sequence (companion to Plan) |
| Notebook | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis.py` | Marimo analysis notebook |
| Report | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Report.md` | Stakeholder report |
| **Learnings** | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/LEARNINGS.md` | **Session learnings** |
| Raw: Directory | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_directory.parquet` | IPEDS Directory data |
| Raw: Admissions | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_admissions.parquet` | IPEDS Admissions data |
| Raw: Grad Rates | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_grad_rates.parquet` | IPEDS Graduation Rates |
| Raw: FSA Grants | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_fsa_grants.parquet` | FSA Pell Grant data |
| Raw: Enrollment Race | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_enrollment_race.parquet` | IPEDS Fall Enrollment by Race |
| Raw: SFR | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_sfr.parquet` | IPEDS Student-Faculty Ratio |
| Raw: Retention | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_retention.parquet` | IPEDS Fall Retention |
| Raw: Finance | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/raw/2026-03-29_ipeds_finance.parquet` | IPEDS Finance data |
| Processed: Directory | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_directory_clean.parquet` | Cleaned directory |
| Processed: Admissions | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_admissions_clean.parquet` | Cleaned admissions with admit_rate |
| Processed: Grad Rates | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_grad_rates_clean.parquet` | Cleaned graduation rates |
| Processed: FSA Pell | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_fsa_pell_clean.parquet` | Cleaned Pell recipients |
| Processed: URM Share | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_urm_share_clean.parquet` | URM share per institution |
| Processed: SFR | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_sfr_clean.parquet` | Cleaned student-faculty ratio |
| Processed: Retention | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_retention_clean.parquet` | Cleaned retention rates |
| Processed: Finance | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_finance_clean.parquet` | Instructional expenditure per FTE |
| Processed: Core | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_core.parquet` | Directory + Admissions + Grad Rates |
| Processed: Demographics | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_core_demographics.parquet` | Core + Pell + URM |
| Processed: Merged | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_merged.parquet` | All sources merged |
| Processed: Analysis | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/data/processed/2026-03-29_analysis.parquet` | Final analysis dataset with bands |
| Analysis: Descriptive | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_descriptive_by_selectivity.parquet` | Descriptive stats by band |
| Analysis: Crosstab Pell | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_crosstab_selectivity_pell.parquet` | Selectivity x Pell cross-tab |
| Analysis: Crosstab URM | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_crosstab_selectivity_urm.parquet` | Selectivity x URM cross-tab |
| Analysis: Correlation | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_correlation_matrix.parquet` | Correlation matrix |
| Analysis: Outperformers | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_outperformers.parquet` | Outperformer profiles |
| Analysis: Selectivity Model | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_selectivity_model.parquet` | OLS predictions and residuals |
| Analysis: Regression | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_regression_results.parquet` | Hierarchical OLS results |
| Analysis: Sector | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_sector_comparison.parquet` | Sector comparison |
| Figure: Scatter | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_grad_rate_vs_admission_rate.png` | Grad rate vs admission rate |
| Figure: Boxplot | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png` | Boxplot by selectivity band |
| Figure: Heatmap Pell | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_heatmap_selectivity_pell.png` | Selectivity x Pell heatmap |
| Figure: Correlation | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_correlation_heatmap.png` | Correlation heatmap |
| Figure: Sector | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_sector_comparison.png` | Sector comparison |
| Figure: Residuals | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/figures/2026-03-29_actual_vs_predicted.png` | Actual vs predicted scatter |
| Fetch Scripts | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage5_fetch/*.py` | Data retrieval code (8 scripts) |
| Clean Scripts | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage6_clean/*.py` | Context application code (8 scripts) |
| Transform Scripts | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage7_transform/*.py` | Transformation code (4 scripts) |
| Analysis & Viz Scripts | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/*.py` | Analysis and visualization code (13 scripts) |
| **QA Scripts** | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/*.py` | **QA inspection scripts from code-reviewer** |
| Debug Scripts | `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/debug/*.py` | Diagnostic scripts (if any) |

