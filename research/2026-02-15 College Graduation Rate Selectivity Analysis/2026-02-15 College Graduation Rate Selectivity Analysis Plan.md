---
title: "College Graduation Rate Selectivity Analysis"
date: "2026-02-15"
version: ""
status: "planning"

must_haves:
  truths:
    - "Institutions with lower admission rates have significantly higher graduation rates (expect r > 0.5)"
    - "Pell share is negatively correlated with graduation rate (expect r < -0.3)"
    - "URM share is negatively correlated with graduation rate"
    - "Within selectivity bands, Pell share still explains meaningful graduation rate variation"
    - "Adding student body composition to selectivity explains substantially more variance in graduation rates (R-squared increase > 0.10)"
    - "Some institutions graduate students at rates significantly above/below expectations given their selectivity and student body"
    - "Private nonprofit institutions have higher graduation rates than public institutions within the same selectivity band"

  artifacts:
    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/2026-02-15 College Graduation Rate Selectivity Analysis.py"
      provides: "Interactive marimo analysis notebook compiling all scripts"
      min_lines: 200
      contains: "mo.md"

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_analysis.parquet"
      provides: "Joined analysis dataset with graduation rates, selectivity, demographics, and resources"
      has_columns: ["unitid", "inst_name", "grad_rate_150pct", "admission_rate", "pell_share", "urm_share", "student_faculty_ratio", "retention_rate", "inst_control", "selectivity_band", "pell_band", "urm_band"]

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/2026-02-15 College Graduation Rate Selectivity Analysis Report.md"
      provides: "Stakeholder report with findings and visualizations"
      contains: ["## Executive Summary", "## Limitations", "## Data Sources"]

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_grad_rate_vs_admission_rate.png"
      provides: "Core scatter plot of graduation rate vs admission rate"
      min_size_kb: 50

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_heatmap_selectivity_pell.png"
      provides: "Heatmap of graduation rate by selectivity x Pell share"
      min_size_kb: 50

  key_links:
    - from: "2026-02-15 College Graduation Rate Selectivity Analysis.py"
      to: "data/processed/2026-02-15_analysis.parquet"
      via: "pl.read_parquet() in data loading cell"
      pattern: "read_parquet.*analysis"

    - from: "2026-02-15 College Graduation Rate Selectivity Analysis.py"
      to: "output/figures/"
      via: "ggplot.save() or fig.write_image()"
      pattern: "(ggsave|write_image|savefig)"

    - from: "2026-02-15 College Graduation Rate Selectivity Analysis Report.md"
      to: "output/figures/"
      via: "Markdown image references"
      pattern: "!\\[.*\\]\\(.*figures/"

execution:
  current_stage: 4
  checkpoints_passed: []
  blockers: []
---

# College Graduation Rate Selectivity Analysis

## Philosophy: Plans are Prompts

**This document is not just documentation — it is an executable specification.**

Every task in the "Executable Task Sequence" section is written as a prompt that will be dispatched directly to a subagent. The task IS the instruction.

**Key Principles:**

1. **Task actions must be specific enough to execute without clarification.**
2. **File paths must be explicit (no placeholders in the final plan).**
3. **Verification must be executable (not subjective).**
4. **Done criteria must be measurable.**

---

## Original Request & Clarifications

### Original Request

> I'm aware that graduation rates are often thought of as a key outcome for assessing a university/college's quality by the general public, but many researchers argue that there's a very strong question of chicken-or-the-egg in interpreting it that way: Are graduation rates high because the college actually did a good job in serving its students, or are graduation rates high because the college selectively admits students who are already highly competitive and academically prepared and likely to graduate/succeed anyway? I'd like to more critically explore this dynamic with data to better understand how correlated these things are, especially when thinking about additional complicating institutional factors like share of students on financial aid, other underserved or historically disadvantaged student population rates, etc. I'd like an analysis that helps provide an intuitive and holistic view on how these factors all relate to one another, and what implications that might have for broadly thinking about college 'quality' in general.

### Clarifications Received

1. **Methodology Preference:** Focus on descriptive statistics and correlations (binning characteristics like selectivity into intuitive, interpretable bands) rather than complex multivariate regressions. Regressions should be supplementary only — adding nuance to interpretation, not carrying the narrative.
2. **Analysis Year:** 2020 chosen as the target year — most recent year with student-faculty ratio and retention data; GR reflects 2014 entering cohort (pre-COVID); admissions applications were mostly pre-COVID.
3. **Scope:** Exclude for-profit institutions; focus on public 4-year and private nonprofit 4-year.

### Research Question

Are high college graduation rates a signal of institutional quality, or primarily a reflection of admissions selectivity and student body demographics? How do factors like Pell Grant share, underrepresented minority enrollment, institutional sector, and resources relate to graduation rates — and what does this imply for thinking about college "quality"?

---

## Goal & Context

### Analysis Goal

Produce a descriptive, correlation-driven analysis that reveals the interrelationship between college graduation rates, admissions selectivity, student body demographics (Pell share, URM share), institutional characteristics (sector, resources), and post-college outcomes. The analysis should make it intuitive and clear to stakeholders how tightly these factors cluster together, and what that clustering implies for interpreting graduation rates as a quality signal.

### Background Context

Graduation rates are among the most visible metrics used to evaluate college quality by prospective students, parents, policymakers, and ranking systems. However, a substantial body of higher education research demonstrates that graduation rates are heavily confounded with admissions selectivity — institutions that admit only the most prepared students naturally have higher completion rates. This creates a "chicken-or-egg" problem: does a high graduation rate signal that the institution is excellent at educating students, or that it is excellent at selecting students who would succeed anywhere? This analysis uses publicly available federal data to make this dynamic visible and quantifiable.

### Success Criteria

- [ ] Analysis dataset joins IPEDS graduation rates, admissions, directory, enrollment race, retention, student-faculty ratio, and FSA Pell data for year 2020 on `unitid`
- [ ] Descriptive statistics and cross-tabulations clearly show how graduation rates vary by selectivity, Pell share, URM share, sector, and resources
- [ ] Correlation matrix quantifies the strength of relationships among all key variables
- [ ] Supplementary regression models quantify incremental explanatory power of student body composition beyond selectivity
- [ ] "Outperformers" analysis identifies institutions beating or lagging expectations within their selectivity band
- [ ] Report synthesizes findings into an accessible narrative addressing the research question

---

## Must-Haves (Goal-Backward Verification)

### Must-Haves Specification

```yaml
must_haves:
  truths:
    - "Institutions with lower admission rates have significantly higher graduation rates (expect r > 0.5)"
    - "Pell share is negatively correlated with graduation rate (expect r < -0.3)"
    - "URM share is negatively correlated with graduation rate"
    - "Within selectivity bands, Pell share still explains meaningful graduation rate variation"
    - "Adding student body composition to selectivity explains substantially more variance (R-squared increase > 0.10)"
    - "Some institutions graduate above/below expectations given their selectivity and student body"
    - "Private nonprofit institutions have higher graduation rates than public institutions within the same selectivity band"

  artifacts:
    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_analysis.parquet"
      provides: "Joined analysis dataset"
      has_columns: ["unitid", "inst_name", "grad_rate_150pct", "admission_rate", "pell_share", "urm_share", "student_faculty_ratio", "retention_rate", "inst_control", "selectivity_band", "pell_band", "urm_band"]

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_descriptive_by_selectivity.parquet"
      provides: "Descriptive statistics by selectivity band"

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_correlation_matrix.parquet"
      provides: "Pairwise correlation matrix of all key variables"

    - path: "research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_regression_results.parquet"
      provides: "OLS regression results (Models 1-3)"

  key_links:
    - from: "2026-02-15 College Graduation Rate Selectivity Analysis.py"
      to: "data/processed/2026-02-15_analysis.parquet"
      via: "pl.read_parquet() in data loading cell"
      pattern: "read_parquet.*analysis"

    - from: "2026-02-15 College Graduation Rate Selectivity Analysis Report.md"
      to: "output/figures/"
      via: "Markdown image references"
      pattern: "!\\[.*\\]\\(.*figures/"
```

---

## Phase 1: Discovery Results

### Stage 2: Data Exploration

**Data Level:** college-university

**Candidate Endpoints:**

| Endpoint | Source | Description | Years Available |
|----------|--------|-------------|-----------------|
| `ipeds/colleges_ipeds_grad-rates` | IPEDS | Graduation rates (150% time) | 1996-2022 |
| `ipeds/colleges_ipeds_admissions-enrollment` | IPEDS | Applications, admissions, enrollment | 2001-2023 |
| `ipeds/colleges_ipeds_admissions-requirements` | IPEDS | SAT/ACT scores, test requirements | 1990-2022 |
| `ipeds/colleges_ipeds_directory` | IPEDS | Institutional characteristics | 1980-2023 |
| `fsa/colleges_fsa_grants` | FSA | Pell Grant recipients and disbursements | 1999-2021 |
| `ipeds/colleges_ipeds_fall-enrollment-race_{year}` | IPEDS | Fall enrollment by race | 1986-2022 |
| `ipeds/colleges_ipeds_student-faculty-ratio` | IPEDS | Student-faculty ratio | 2009-2020 |
| `ipeds/colleges_ipeds_fall-retention` | IPEDS | Fall retention rates | 2003-2020 |
| `scorecard/colleges_scorecard_earnings` | Scorecard | Post-college earnings | varies |
| `scorecard/colleges_scorecard_student_body_nslds` | Scorecard | First-gen %, family income | 1997-2016 |

**Key Variables Identified:**

| Variable | Endpoint | Type | Description |
|----------|----------|------|-------------|
| `completion_rate_150pct` | grad-rates | float | 150% time graduation rate |
| `number_applied` | admissions-enrollment | integer | Number of applicants |
| `number_admitted` | admissions-enrollment | integer | Number admitted |
| `number_enrolled_total` | admissions-enrollment | integer | Number enrolled |
| `inst_name` | directory | string | Institution name |
| `inst_control` | directory | integer | 1=Public, 2=Private nonprofit |
| `institution_level` | directory | integer | 4=Four-year |
| `open_admissions` | directory | integer | Open admissions flag |
| `hbcu` | directory | integer | HBCU flag |
| `cc_basic_2021` | directory | string | Carnegie Classification |
| `enrollment_undergrad` | directory | integer | Undergraduate enrollment |
| `pell_recipients` | fsa-grants | integer | Number of Pell recipients |
| `enrollment_fall` | fall-enrollment-race | integer | Enrollment by race |
| `student_faculty_ratio` | student-faculty-ratio | float | Student to faculty ratio |
| `retention_rate` | fall-retention | float | First-year retention rate |
| `earnings_med` | scorecard-earnings | float | Median earnings post-college |

**Variables Flagged for Deep-Dive:**

| Variable | Reason for Deep-Dive |
|----------|---------------------|
| `completion_rate_150pct` | Need to identify correct `subcohort` code for overall graduation rate |
| `race` in grad-rates and enrollment | Coded values for URM categories need mapping |
| `sex` in admissions | Need to filter to `sex==99` (total) for admission rate calculation |
| `pell_recipients` in FSA | Need to verify availability for year 2020 and join key compatibility |
| `subcohort` in grad-rates | Need codebook verification to find "all students" overall rate code |

**Limitations Encountered:**

| Limitation | Impact | Resolution |
|------------|--------|------------|
| Student-faculty ratio only through 2020 | Constrains analysis year to 2020 | Use 2020 as analysis year |
| Fall retention only through 2020 | Same constraint | Use 2020 |
| Median debt not available via Portal mirror | Cannot include debt analysis | Drop debt from scope |
| Finance data only through 2017 | Cannot use expenditure-per-student as resource proxy | Use student-faculty ratio instead |

**Stage 2 Completeness Assessment:**
- [x] All relevant data levels searched
- [x] Multiple potential sources considered
- [x] Year coverage verified for research question
- [x] Variables requiring deep-dive explicitly flagged
- [x] Limitations documented

---

### Stage 3: Source Deep-Dive

**Sources Investigated:**

| Source | Skill Used | Relevance |
|--------|------------|-----------|
| IPEDS | `education-data-source-ipeds` | Primary data source for all institutional metrics |
| FSA | `education-data-source-fsa` | Pell Grant recipient counts |
| Scorecard | `education-data-source-scorecard` | Supplementary earnings data |

**Source-Specific Caveats:**

#### IPEDS

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| FTFT cohort limitation | GR tracks only first-time, full-time, fall-entering students — favors selective institutions | Document as core part of research narrative |
| Admissions data coverage | Open-admission institutions may lack application/admit counts | Use `open_admissions` flag from directory to identify these; assign to "Less Selective/Open" band |
| Coded values: -1, -2, -3 | Missing, not applicable, suppressed | Filter before analysis |
| `sex==99` for totals | Admissions data has rows per sex | Filter to sex==99 for total counts |
| `race==99` for totals | Enrollment race data has rows per race category | Filter race==99 for totals; use specific codes for URM calculation |
| `institution_level==4` for 4-year | Code 4 is four-year (NOT code 3) | Filter institution_level==4 |

#### FSA

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| FSA grants available through 2021 | Covers our 2020 analysis year | No issue |
| Join on `unitid` | Compatible with IPEDS | Direct join |

#### Scorecard

| Caveat | Impact on Analysis | Mitigation |
|--------|-------------------|------------|
| Title IV bias in coverage | 30-50% coverage at elite institutions, 80%+ at less selective | Document prominently; earnings comparisons across selectivity tiers are attenuated |
| Earnings data sparseness | Not all institution-years have data | Supplementary use only |

**Coded Value Mappings:**

| Variable | Code | Meaning | Action |
|----------|------|---------|--------|
| All numeric variables | -1 | Missing/not reported | Replace with null |
| All numeric variables | -2 | Not applicable | Replace with null |
| All numeric variables | -3 | Suppressed | Replace with null |
| `sex` (admissions) | 99 | Total (both sexes) | Filter to this value |
| `race` (enrollment) | 99 | Total (all races) | Filter to this for total; use specific codes for URM |
| `inst_control` | 1 | Public | Include |
| `inst_control` | 2 | Private nonprofit | Include |
| `inst_control` | 3 | Private for-profit | Exclude |
| `institution_level` | 4 | Four-year | Filter to this value |
| `ftpt` (retention) | 1 | Full-time | Filter to this value for retention rate |
| `subcohort` (grad-rates) | TBD | All students overall | Verify via codebook during Stage 5 fetch |

**Suppression Patterns:**

| Variable | Typical Suppression Rate | Threshold | Impact |
|----------|--------------------------|-----------|--------|
| Graduation rate | Low (<5%) for 4-year institutions | <3 students in cohort | Minimal at institution level |
| Admissions counts | Low | Small cell sizes | Minimal for 4-year institutions |
| FSA Pell recipients | Low | Minimum reporting threshold | Minimal |

**Critical Warnings:**

1. **FTFT Cohort Limitation:** IPEDS graduation rates track ONLY first-time, full-time, fall-entering students. This cohort represents most students at selective institutions but a minority at open-access ones. The metric itself structurally favors selective institutions — this is part of the research story and must be prominently documented.
2. **Scorecard Title IV Bias:** Coverage varies inversely with selectivity: 30-50% at elite institutions, 80%+ at less selective ones. Earnings comparisons across selectivity tiers are inherently attenuated by this differential coverage. Use as supplementary only.
3. **`subcohort` Code Verification:** The exact subcohort code for "all students" overall graduation rate needs codebook verification during the Stage 5 fetch. The fetch script must inspect available subcohort values and select the correct one.

**Stage 3 Completeness Assessment:**
- [x] All flagged variables investigated
- [x] Source-specific skills consulted
- [x] Coded values fully documented
- [x] Suppression patterns identified
- [x] Cross-state comparability assessed (N/A — national analysis)
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
- [x] Cross-state comparability assessed (N/A)
- [x] Critical warnings have mitigation strategies
- [x] All LOW confidence findings resolved or escalated

---

## Methodology Specification

### Data Acquisition Strategy

**Multi-Source Join:** All datasets joined on `unitid` + `year` (where applicable). All are IPEDS-compatible identifiers.

**Join Strategy:**

| Left Source | Right Source | Join Key(s) | Expected Cardinality | Risks |
|-------------|--------------|-------------|---------------------|-------|
| Directory (base) | Graduation Rates | `unitid`, `year` | 1:1 (after subcohort filter) | Subcohort filter critical |
| Directory | Admissions Enrollment | `unitid`, `year` | 1:1 (after sex==99 filter) | Some open-admission schools may lack data |
| Directory | FSA Grants | `unitid`, `year` | 1:1 | FSA year availability |
| Directory | Fall Enrollment Race | `unitid`, `year` | many:1 (after race aggregation) | Need to aggregate URM races first |
| Directory | Student-Faculty Ratio | `unitid`, `year` | 1:1 | Only through 2020 |
| Directory | Fall Retention | `unitid`, `year` | 1:1 (after ftpt==1 filter) | Only through 2020 |
| Analysis dataset | Scorecard Earnings | `unitid`, `year` | 1:1 | Supplementary; sparse coverage |

### Query Specification

**Query 1: IPEDS Directory**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Directory |
| Mirror Path | `ipeds/colleges_ipeds_directory` |
| File Type | Single-file (all years) |
| Years | 2020 |
| Filters (local) | `year==2020`, `institution_level==4`, `inst_control` in [1, 2] |
| Variables | `unitid`, `year`, `inst_name`, `inst_control`, `institution_level`, `hbcu`, `degree_granting`, `open_admissions`, `urban_centric_locale`, `cc_basic_2021`, `enrollment_undergrad`, `state_abbr`, `fips` |
| Expected Records | ~2,000-3,000 (4-year public + private nonprofit) |

**Query 2: IPEDS Graduation Rates**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Graduation Rates |
| Mirror Path | `ipeds/colleges_ipeds_grad-rates` |
| File Type | Single-file (all years) |
| Years | 2020 |
| Filters (local) | `year==2020`, `race==99` (total), `sex==99` (total), subcohort TBD via codebook |
| Variables | `unitid`, `year`, `completion_rate_150pct`, `cohort_adj_150pct`, `completers_150pct` |
| Expected Records | ~2,000-3,000 after filters |

**Query 3: IPEDS Admissions Enrollment**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Admissions Enrollment |
| Mirror Path | `ipeds/colleges_ipeds_admissions-enrollment` |
| File Type | Single-file (all years) |
| Years | 2020 |
| Filters (local) | `year==2020`, `sex==99` (total) |
| Variables | `unitid`, `year`, `number_applied`, `number_admitted`, `number_enrolled_total` |
| Expected Records | ~2,000-3,000 after filters |

**Query 4: FSA Grants**

| Field | Value |
|-------|-------|
| Dataset | FSA Grants |
| Mirror Path | `fsa/colleges_fsa_grants` |
| File Type | Single-file (all years) |
| Years | 2020 |
| Filters (local) | `year==2020` |
| Variables | `unitid`, `year`, `pell_recipients`, `pell_disbursements` |
| Expected Records | ~4,000-6,000 (all institutions, will filter after join) |

**Query 5: IPEDS Fall Enrollment Race (2020)**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Fall Enrollment Race 2020 |
| Mirror Path | `ipeds/colleges_ipeds_fall-enrollment-race_2020` |
| File Type | Yearly (one file for 2020) |
| Years | 2020 |
| Filters (local) | `sex==99`, `ftpt==99` or total, `level_of_study` = undergraduate |
| Variables | `unitid`, `year`, `enrollment_fall`, `race`, `sex`, `ftpt`, `level_of_study` |
| Expected Records | ~20,000-40,000 (multiple race rows per institution; will aggregate) |

**Query 6: IPEDS Student-Faculty Ratio**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Student-Faculty Ratio |
| Mirror Path | `ipeds/colleges_ipeds_student-faculty-ratio` |
| File Type | Single-file (all years) |
| Years | 2020 |
| Filters (local) | `year==2020` |
| Variables | `unitid`, `year`, `student_faculty_ratio` |
| Expected Records | ~3,000-5,000 |

**Query 7: IPEDS Fall Retention**

| Field | Value |
|-------|-------|
| Dataset | IPEDS Fall Retention |
| Mirror Path | `ipeds/colleges_ipeds_fall-retention` |
| File Type | Single-file (all years) |
| Years | 2020 |
| Filters (local) | `year==2020`, `ftpt==1` (full-time) |
| Variables | `unitid`, `year`, `retention_rate` |
| Expected Records | ~2,000-4,000 |

**Query 8: Scorecard Earnings (Supplementary)**

| Field | Value |
|-------|-------|
| Dataset | Scorecard Earnings |
| Mirror Path | `scorecard/colleges_scorecard_earnings` |
| File Type | Single-file (all years) |
| Years | Latest available (likely 2018 or earlier) |
| Filters (local) | Most recent year available, `years_after_entry==10` if available |
| Variables | `unitid`, `year`, `earnings_med`, `count_working` |
| Expected Records | ~2,000-4,000 |

### Data Freshness Check

| Source | Requested Years | Latest Available | Lag | Impact | User Notified? |
|--------|-----------------|------------------|-----|--------|----------------|
| IPEDS Directory | 2020 | 2023 | 0 years | Current | N/A |
| IPEDS Grad Rates | 2020 | 2022 | 0 years | Current | N/A |
| IPEDS Admissions | 2020 | 2023 | 0 years | Current | N/A |
| FSA Grants | 2020 | 2021 | 0 years | Current | N/A |
| IPEDS Enrollment Race | 2020 | 2022 | 0 years | Current | N/A |
| IPEDS Student-Faculty Ratio | 2020 | 2020 | 0 years | At boundary | N/A |
| IPEDS Fall Retention | 2020 | 2020 | 0 years | At boundary | N/A |
| Scorecard Earnings | Latest | varies | TBD | Supplementary | If lag >= 3 years |

**COVID-19 Data Quality Considerations:**

| Year | Data Quality Impact | Mitigation |
|------|-------------------|------------|
| 2020 | Graduation rate for 2020 reporting year reflects the 2014 entering cohort (6-year window), so outcomes are pre-COVID. Admissions applications for fall 2020 were mostly submitted pre-COVID (fall 2019/early 2020). Student-faculty ratio and retention may be slightly affected by COVID enrollment disruptions. | Document that GR cohort is pre-COVID. Note that 2020 institutional characteristics (enrollment counts, S-F ratio) may show minor COVID effects. |

### Data Cleaning Specification

**Coded Value Handling:**

| Variable | Codes to Filter | Rationale |
|----------|-----------------|-----------|
| All numeric columns | -1, -2, -3 | Standard Education Data Portal missing/NA/suppressed codes |
| `sex` (admissions, enrollment) | Keep only 99 | Need totals, not sex-disaggregated rows |
| `race` (enrollment) | Keep specific race codes for URM calc; keep 99 for total | Need both total and race-specific counts |
| `inst_control` | Keep only 1, 2 | Exclude for-profit (3) |
| `institution_level` | Keep only 4 | Four-year institutions only |
| `ftpt` (retention) | Keep only 1 | Full-time retention rate only |

**Suppression Handling:**

- Expected suppression rate: <10% for 4-year institutions
- Threshold for STOP condition: 50%
- If exceeded: Escalate to user

### Transformation Sequence

#### Wave-Based Task Table

| Wave | Step | Task Name | Operation | Expected Outcome | Script Path | Cardinality | Depends On | Status |
|------|------|-----------|-----------|------------------|-------------|-------------|------------|--------|
| 1 | 1.1 | fetch-directory | Fetch IPEDS directory for 2020, filter to 4-yr public/private nonprofit | ~2,000-3,000 rows | `scripts/stage5_fetch/01_fetch-directory.py` | N/A | — | Pending |
| 1 | 1.2 | fetch-grad-rates | Fetch IPEDS grad rates for 2020, filter sex==99, race==99, identify subcohort | ~2,000-3,000 rows (after subcohort filter) | `scripts/stage5_fetch/02_fetch-grad-rates.py` | N/A | — | Pending |
| 1 | 1.3 | fetch-admissions | Fetch IPEDS admissions-enrollment for 2020, filter sex==99 | ~2,000-3,000 rows | `scripts/stage5_fetch/03_fetch-admissions.py` | N/A | — | Pending |
| 1 | 1.4 | fetch-fsa-grants | Fetch FSA grants for 2020 | ~4,000-6,000 rows | `scripts/stage5_fetch/04_fetch-fsa-grants.py` | N/A | — | Pending |
| 1 | 1.5 | fetch-enrollment-race | Fetch IPEDS fall enrollment race for 2020 | ~20,000-40,000 rows (multi-race) | `scripts/stage5_fetch/05_fetch-enrollment-race.py` | N/A | — | Pending |
| 2 | 2.1 | fetch-sfr | Fetch IPEDS student-faculty ratio for 2020 | ~3,000-5,000 rows | `scripts/stage5_fetch/06_fetch-sfr.py` | N/A | — | Pending |
| 2 | 2.2 | fetch-retention | Fetch IPEDS fall retention for 2020, filter ftpt==1 | ~2,000-4,000 rows | `scripts/stage5_fetch/07_fetch-retention.py` | N/A | — | Pending |
| 2 | 2.3 | fetch-scorecard | Fetch Scorecard earnings (supplementary) | ~2,000-4,000 rows | `scripts/stage5_fetch/08_fetch-scorecard.py` | N/A | — | Pending |
| 3 | 3.1 | clean-directory | Replace coded values with null, verify inst_control and institution_level filters | ~2,000-3,000 rows (same as fetch) | `scripts/stage6_clean/01_clean-directory.py` | N/A | 1.1 | Pending |
| 3 | 3.2 | clean-grad-rates | Replace coded values with null, verify subcohort filter, extract completion_rate_150pct | ~2,000-3,000 rows | `scripts/stage6_clean/02_clean-grad-rates.py` | N/A | 1.2 | Pending |
| 3 | 3.3 | clean-admissions | Replace coded values with null, compute admission_rate = number_admitted / number_applied | ~2,000-3,000 rows + derived column | `scripts/stage6_clean/03_clean-admissions.py` | N/A | 1.3 | Pending |
| 3 | 3.4 | clean-fsa-grants | Replace coded values with null | ~4,000-6,000 rows | `scripts/stage6_clean/04_clean-fsa-grants.py` | N/A | 1.4 | Pending |
| 3 | 3.5 | clean-enrollment-race | Replace coded values with null, compute URM enrollment count by aggregating specific race codes | ~2,000-3,000 rows (aggregated to institution level) | `scripts/stage6_clean/05_clean-enrollment-race.py` | N/A | 1.5 | Pending |
| 4 | 4.1 | clean-sfr | Replace coded values with null | ~3,000-5,000 rows | `scripts/stage6_clean/06_clean-sfr.py` | N/A | 2.1 | Pending |
| 4 | 4.2 | clean-retention | Replace coded values with null | ~2,000-4,000 rows | `scripts/stage6_clean/07_clean-retention.py` | N/A | 2.2 | Pending |
| 4 | 4.3 | clean-scorecard | Replace coded values with null, select most recent year with earnings data | ~2,000-4,000 rows | `scripts/stage6_clean/08_clean-scorecard.py` | N/A | 2.3 | Pending |
| 5 | 5.1 | join-core | Join directory + grad rates + admissions + FSA grants on unitid; compute pell_share | ~1,500-2,500 rows | `scripts/stage7_transform/01_join-core.py` | 1:1 per join | 3.1, 3.2, 3.3, 3.4 | Pending |
| 5 | 5.2 | join-demographics | Join core dataset + enrollment race (URM) on unitid; compute urm_share | ~1,500-2,500 rows | `scripts/stage7_transform/02_join-demographics.py` | 1:1 | 5.1, 3.5 | Pending |
| 6 | 6.1 | join-resources | Join demographics dataset + SFR + retention on unitid | ~1,500-2,500 rows | `scripts/stage7_transform/03_join-resources.py` | 1:1 per join | 5.2, 4.1, 4.2 | Pending |
| 6 | 6.2 | create-bands | Create selectivity_band, pell_band, urm_band columns from continuous variables; save final analysis dataset | ~1,500-2,500 rows + 3 derived columns | `scripts/stage7_transform/04_create-bands.py` | N/A | 6.1 | Pending |
| 7 | 7.1 | descriptive-by-selectivity | Compute median/mean/IQR of grad rate, Pell share, URM share, SFR, retention by selectivity band | Summary table | `scripts/stage8_analysis/01_descriptive-by-selectivity.py` | N/A | 6.2 | Pending |
| 7 | 7.2 | crosstab-selectivity-pell | Cross-tabulate mean graduation rate by selectivity band x Pell band | Summary table | `scripts/stage8_analysis/02_crosstab-selectivity-pell.py` | N/A | 6.2 | Pending |
| 7 | 7.3 | crosstab-selectivity-urm | Cross-tabulate mean graduation rate by selectivity band x URM band | Summary table | `scripts/stage8_analysis/03_crosstab-selectivity-urm.py` | N/A | 6.2 | Pending |
| 7 | 7.4 | correlation-matrix | Compute pairwise Pearson and Spearman correlations for all key continuous variables | Correlation matrix | `scripts/stage8_analysis/04_correlation-matrix.py` | N/A | 6.2 | Pending |
| 7 | 7.5 | outperformers | Within each selectivity band, identify institutions >1 SD above/below band median grad rate; characterize them | Outperformer table | `scripts/stage8_analysis/05_outperformers.py` | N/A | 6.2 | Pending |
| 8 | 8.1 | regression-models | Run 3 OLS regressions (bivariate, +demographics, full); compare R-squared; save coefficients | Regression results | `scripts/stage8_analysis/06_regression-models.py` | N/A | 6.2 | Pending |
| 8 | 8.2 | sector-comparison | Compare median grad rate by selectivity band split by sector (public vs private nonprofit) | Summary table | `scripts/stage8_analysis/07_sector-comparison.py` | N/A | 6.2 | Pending |
| 9 | 9.1 | viz-scatter-grad-admit | Scatter plot: graduation rate vs admission rate, colored by sector | Figure | `scripts/stage8_analysis/08_viz-scatter-grad-admit.py` | N/A | 6.2 | Pending |
| 9 | 9.2 | viz-boxplot-selectivity | Box plots: graduation rate distribution by selectivity band | Figure | `scripts/stage8_analysis/09_viz-boxplot-selectivity.py` | N/A | 6.2 | Pending |
| 9 | 9.3 | viz-heatmap-selectivity-pell | Heatmap: mean graduation rate by selectivity band x Pell band | Figure | `scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py` | N/A | 7.2 | Pending |
| 9 | 9.4 | viz-correlation-heatmap | Heatmap of correlation matrix | Figure | `scripts/stage8_analysis/11_viz-correlation-heatmap.py` | N/A | 7.4 | Pending |
| 9 | 9.5 | viz-sector-comparison | Bar chart: median grad rate by selectivity band, split by sector | Figure | `scripts/stage8_analysis/12_viz-sector-comparison.py` | N/A | 8.2 | Pending |
| 10 | 10.1 | join-scorecard | LEFT join analysis dataset + Scorecard earnings on unitid (supplementary) | ~1,500-2,500 rows (some nulls in earnings) | `scripts/stage7_transform/05_join-scorecard.py` | 1:1 | 6.2, 4.3 | Pending |
| 10 | 10.2 | viz-residual-scatter | Scatter: actual vs predicted grad rate from Model 3, highlighting outperformers | Figure | `scripts/stage8_analysis/13_viz-residual-scatter.py` | N/A | 8.1 | Pending |

**Script Path Convention:**
- Stage 5 (fetch): `scripts/stage5_fetch/`
- Stage 6 (clean): `scripts/stage6_clean/`
- Stage 7 (transform): `scripts/stage7_transform/`
- Stage 8 (analysis & viz): `scripts/stage8_analysis/`

#### Transformation Log

| Wave | Step | Task | Pre-Rows | Post-Rows | Change % | CP Status | QA Status | Revisions | Commit Hash | Notes |
|------|------|------|----------|-----------|----------|-----------|-----------|-----------|-------------|-------|
| 1 | 1.1 | fetch-directory | — | — | — | — | — | 0 | — | — |
| 1 | 1.2 | fetch-grad-rates | — | — | — | — | — | 0 | — | — |
| 1 | 1.3 | fetch-admissions | — | — | — | — | — | 0 | — | — |
| 1 | 1.4 | fetch-fsa-grants | — | — | — | — | — | 0 | — | — |
| 1 | 1.5 | fetch-enrollment-race | — | — | — | — | — | 0 | — | — |
| 2 | 2.1 | fetch-sfr | — | — | — | — | — | 0 | — | — |
| 2 | 2.2 | fetch-retention | — | — | — | — | — | 0 | — | — |
| 2 | 2.3 | fetch-scorecard | — | — | — | — | — | 0 | — | — |
| 3 | 3.1 | clean-directory | — | — | — | — | — | 0 | — | — |
| 3 | 3.2 | clean-grad-rates | — | — | — | — | — | 0 | — | — |
| 3 | 3.3 | clean-admissions | — | — | — | — | — | 0 | — | — |
| 3 | 3.4 | clean-fsa-grants | — | — | — | — | — | 0 | — | — |
| 3 | 3.5 | clean-enrollment-race | — | — | — | — | — | 0 | — | — |
| 4 | 4.1 | clean-sfr | — | — | — | — | — | 0 | — | — |
| 4 | 4.2 | clean-retention | — | — | — | — | — | 0 | — | — |
| 4 | 4.3 | clean-scorecard | — | — | — | — | — | 0 | — | — |
| 5 | 5.1 | join-core | — | — | — | — | — | 0 | — | — |
| 5 | 5.2 | join-demographics | — | — | — | — | — | 0 | — | — |
| 6 | 6.1 | join-resources | — | — | — | — | — | 0 | — | — |
| 6 | 6.2 | create-bands | — | — | — | — | — | 0 | — | — |
| 7 | 7.1 | descriptive-by-selectivity | — | — | — | — | — | 0 | — | — |
| 7 | 7.2 | crosstab-selectivity-pell | — | — | — | — | — | 0 | — | — |
| 7 | 7.3 | crosstab-selectivity-urm | — | — | — | — | — | 0 | — | — |
| 7 | 7.4 | correlation-matrix | — | — | — | — | — | 0 | — | — |
| 7 | 7.5 | outperformers | — | — | — | — | — | 0 | — | — |
| 8 | 8.1 | regression-models | — | — | — | — | — | 0 | — | — |
| 8 | 8.2 | sector-comparison | — | — | — | — | — | 0 | — | — |
| 9 | 9.1 | viz-scatter-grad-admit | — | — | — | — | — | 0 | — | — |
| 9 | 9.2 | viz-boxplot-selectivity | — | — | — | — | — | 0 | — | — |
| 9 | 9.3 | viz-heatmap-selectivity-pell | — | — | — | — | — | 0 | — | — |
| 9 | 9.4 | viz-correlation-heatmap | — | — | — | — | — | 0 | — | — |
| 9 | 9.5 | viz-sector-comparison | — | — | — | — | — | 0 | — | — |
| 10 | 10.1 | join-scorecard | — | — | — | — | — | 0 | — | — |
| 10 | 10.2 | viz-residual-scatter | — | — | — | — | — | 0 | — | — |

---

## Executable Task Sequence

### Wave 1: Primary Data Fetch (Parallel — 5 tasks)

<task name="fetch-directory" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_ipeds_directory.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `ipeds/colleges_ipeds_directory`
       - File type: Single-file (all years)
    3. Apply local filters with Polars:
       - pl.col("year") == 2020
       - pl.col("institution_level") == 4
       - pl.col("inst_control").is_in([1, 2])
    4. Select columns: unitid, year, inst_name, inst_control, institution_level, hbcu, degree_granting, open_admissions, urban_centric_locale, cc_basic_2021, enrollment_undergrad, state_abbr, fips
    5. Save to parquet format
    6. Run CP1 validation
  </action>
  <verify>
    - Row count: 2,000-4,000 expected
    - Required columns present: unitid, inst_name, inst_control, enrollment_undergrad, open_admissions
    - Years present: [2020]
    - Null rate less than 10% for unitid, inst_name, inst_control
    - inst_control only contains values 1 and 2
    - institution_level only contains value 4
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-02-15_ipeds_directory.parquet</done>
</task>

<task name="fetch-grad-rates" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_ipeds_grad_rates.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `ipeds/colleges_ipeds_grad-rates`
       - File type: Single-file (all years)
    3. Fetch full dataset for year 2020
    4. IMPORTANT: Before filtering subcohort, inspect unique subcohort values and print them. Also download and inspect the codebook at `ipeds/codebook_colleges_ipeds_grad-rates` to identify the correct subcohort code for "all students, bachelor-seeking" overall graduation rate. Document the selected subcohort code and reasoning.
    5. Apply local filters with Polars:
       - pl.col("year") == 2020
       - pl.col("sex") == 99 (total)
       - pl.col("race") == 99 (total)
       - pl.col("subcohort") == [identified code for all-students overall]
    6. Select columns: unitid, year, completion_rate_150pct, cohort_adj_150pct, completers_150pct, subcohort
    7. Save to parquet format
    8. Run CP1 validation
  </action>
  <verify>
    - Row count: 1,500-4,000 expected
    - Required columns present: unitid, completion_rate_150pct
    - Only year 2020 present
    - sex==99 and race==99 confirmed (no disaggregated rows)
    - completion_rate_150pct range: 0-100 (or 0-1 scale — document which)
    - Subcohort code documented in script output
  </verify>
  <done>CP1 PASSED, subcohort code documented, file saved to data/raw/2026-02-15_ipeds_grad_rates.parquet</done>
</task>

<task name="fetch-admissions" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_ipeds_admissions.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `ipeds/colleges_ipeds_admissions-enrollment`
       - File type: Single-file (all years)
    3. Apply local filters with Polars:
       - pl.col("year") == 2020
       - pl.col("sex") == 99 (total)
    4. Select columns: unitid, year, number_applied, number_admitted, number_enrolled_total
    5. Save to parquet format
    6. Run CP1 validation
  </action>
  <verify>
    - Row count: 1,500-4,000 expected
    - Required columns present: unitid, number_applied, number_admitted
    - Only year 2020 present
    - sex==99 confirmed
    - number_applied > 0 for most rows
    - number_admitted <= number_applied for all valid rows
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-02-15_ipeds_admissions.parquet</done>
</task>

<task name="fetch-fsa-grants" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_fsa_grants.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `fsa/colleges_fsa_grants`
       - File type: Single-file (all years)
    3. Apply local filters with Polars:
       - pl.col("year") == 2020
    4. Select columns: unitid, year, pell_recipients, pell_disbursements
    5. Save to parquet format
    6. Run CP1 validation
  </action>
  <verify>
    - Row count: 3,000-7,000 expected
    - Required columns present: unitid, pell_recipients
    - Only year 2020 present
    - pell_recipients >= 0 for valid rows
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-02-15_fsa_grants.parquet</done>
</task>

<task name="fetch-enrollment-race" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_ipeds_enrollment_race.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `ipeds/colleges_ipeds_fall-enrollment-race_2020`
       - File type: Yearly (2020 file)
    3. Fetch the 2020 file
    4. Print unique values of race, sex, ftpt, level_of_study to understand coding
    5. Apply local filters with Polars:
       - pl.col("sex") == 99 (total) OR the appropriate total code for sex
       - Level of study filter for undergraduates (inspect and document the correct code)
    6. Keep all race codes (will aggregate in cleaning step)
    7. Select columns: unitid, year, enrollment_fall, race, sex, ftpt, level_of_study
    8. Save to parquet format
    9. Run CP1 validation
  </action>
  <verify>
    - Row count: 10,000-60,000 expected (multiple race rows per institution)
    - Required columns present: unitid, enrollment_fall, race
    - Multiple race code values present
    - unitid is NOT unique (multiple rows per institution expected)
  </verify>
  <done>CP1 PASSED, race codes documented, file saved to data/raw/2026-02-15_ipeds_enrollment_race.parquet</done>
</task>

### Wave 2: Secondary Data Fetch (Parallel — 3 tasks)

<task name="fetch-sfr" type="auto" wave="2">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_ipeds_sfr.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `ipeds/colleges_ipeds_student-faculty-ratio`
       - File type: Single-file (all years)
    3. Apply local filters with Polars:
       - pl.col("year") == 2020
    4. Select columns: unitid, year, student_faculty_ratio
    5. Save to parquet format
    6. Run CP1 validation
  </action>
  <verify>
    - Row count: 2,000-6,000 expected
    - Required columns present: unitid, student_faculty_ratio
    - Only year 2020 present
    - student_faculty_ratio range: 1-100 for valid rows
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-02-15_ipeds_sfr.parquet</done>
</task>

<task name="fetch-retention" type="auto" wave="2">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_ipeds_retention.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `ipeds/colleges_ipeds_fall-retention`
       - File type: Single-file (all years)
    3. Apply local filters with Polars:
       - pl.col("year") == 2020
       - pl.col("ftpt") == 1 (full-time)
    4. Select columns: unitid, year, retention_rate
    5. Save to parquet format
    6. Run CP1 validation
  </action>
  <verify>
    - Row count: 1,500-5,000 expected
    - Required columns present: unitid, retention_rate
    - Only year 2020 present
    - retention_rate range: 0-100 for valid rows
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-02-15_ipeds_retention.parquet</done>
</task>

<task name="fetch-scorecard" type="auto" wave="2">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-02-15_scorecard_earnings.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern:
       - Dataset Path: `scorecard/colleges_scorecard_earnings`
       - File type: Single-file (all years)
    3. Inspect available years and print unique values of year
    4. Select the most recent year available
    5. If years_after_entry column exists, filter to years_after_entry == 10 (or the longest available)
    6. Select columns: unitid, year, earnings_med, earnings_mean, count_working
    7. Save to parquet format
    8. Run CP1 validation
  </action>
  <verify>
    - Row count: 1,000-5,000 expected
    - Required columns present: unitid, earnings_med
    - Year documented
    - earnings_med range: 10000-200000 for valid rows
  </verify>
  <done>CP1 PASSED, year documented, file saved to data/raw/2026-02-15_scorecard_earnings.parquet</done>
</task>

### Wave 3: Primary Cleaning (Parallel — 5 tasks)

<task name="clean-directory" type="auto" wave="3">
  <depends_on>fetch-directory</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_ipeds_directory.parquet</input>
    <output>data/processed/2026-02-15_directory_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input
    3. Replace coded values (-1, -2, -3) with null in all numeric columns
    4. Verify filters already applied: inst_control in [1, 2], institution_level == 4
    5. Confirm no for-profit institutions remain (inst_control != 3)
    6. Calculate suppression rate for enrollment_undergrad
    7. Print value_counts for inst_control, open_admissions, hbcu
    8. Save to parquet
    9. Run CP2 validation
  </action>
  <verify>
    - No coded values (-1, -2, -3) remain in numeric columns
    - Suppression rate for enrollment_undergrad less than 50%
    - inst_control only 1 or 2
    - Row count preserved (cleaning replaces values, does not drop rows)
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-02-15_directory_clean.parquet</done>
</task>

<task name="clean-grad-rates" type="auto" wave="3">
  <depends_on>fetch-grad-rates</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_ipeds_grad_rates.parquet</input>
    <output>data/processed/2026-02-15_grad_rates_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input
    3. Replace coded values (-1, -2, -3) with null in completion_rate_150pct, cohort_adj_150pct, completers_150pct
    4. Verify that completion_rate_150pct is on 0-100 scale (if 0-1, multiply by 100 and document). Print min, max, mean, median to confirm scale.
    5. Rename completion_rate_150pct to grad_rate_150pct for clarity
    6. Calculate null rate for grad_rate_150pct
    7. Save to parquet
    8. Run CP2 validation
  </action>
  <verify>
    - No coded values remain in grad_rate_150pct
    - grad_rate_150pct scale documented (0-100 expected)
    - Null rate for grad_rate_150pct less than 30%
    - Suppression rate less than 50%
  </verify>
  <done>CP2 PASSED, scale documented, file saved to data/processed/2026-02-15_grad_rates_clean.parquet</done>
</task>

<task name="clean-admissions" type="auto" wave="3">
  <depends_on>fetch-admissions</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_ipeds_admissions.parquet</input>
    <output>data/processed/2026-02-15_admissions_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input
    3. Replace coded values (-1, -2, -3) with null in number_applied, number_admitted, number_enrolled_total
    4. Compute admission_rate = number_admitted / number_applied (only where both are non-null and number_applied > 0)
       - REASONING: admission_rate is our primary selectivity measure. Computed as proportion (0-1 scale), will multiply by 100 for display but keep as proportion for analysis.
       - Set admission_rate to null where number_applied is null or zero
    5. Print admission_rate distribution: min, max, mean, median, count of nulls
    6. Verify: admission_rate should be between 0 and 1 (inclusive)
    7. Save to parquet
    8. Run CP2 validation
  </action>
  <verify>
    - No coded values remain in number_applied, number_admitted
    - admission_rate is between 0 and 1 for all non-null values
    - admission_rate null rate documented
    - Row count preserved
  </verify>
  <done>CP2 PASSED, admission_rate computed and validated, file saved to data/processed/2026-02-15_admissions_clean.parquet</done>
</task>

<task name="clean-fsa-grants" type="auto" wave="3">
  <depends_on>fetch-fsa-grants</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_fsa_grants.parquet</input>
    <output>data/processed/2026-02-15_fsa_grants_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input
    3. Replace coded values (-1, -2, -3) with null in pell_recipients, pell_disbursements
    4. Print pell_recipients distribution: min, max, mean, median, null count
    5. Save to parquet
    6. Run CP2 validation
  </action>
  <verify>
    - No coded values remain
    - pell_recipients >= 0 for all non-null values
    - Null rate for pell_recipients less than 30%
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-02-15_fsa_grants_clean.parquet</done>
</task>

<task name="clean-enrollment-race" type="auto" wave="3">
  <depends_on>fetch-enrollment-race</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_ipeds_enrollment_race.parquet</input>
    <output>data/processed/2026-02-15_enrollment_race_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from input
    3. Replace coded values (-1, -2, -3) with null in enrollment_fall
    4. Print unique race code values and their meanings (consult IPEDS documentation):
       - URM races typically include: Black/African American, Hispanic/Latino, American Indian/Alaska Native
       - Non-URM: White, Asian
       - Other: Two or more races, Unknown, Nonresident alien
       - race==99 is total
    5. Compute per-institution totals:
       a. total_enrollment: enrollment_fall where race==99 (or sum across races if 99 not reliable)
       b. urm_enrollment: SUM of enrollment_fall for URM race codes (Black, Hispanic, American Indian)
    6. Compute urm_share = urm_enrollment / total_enrollment (where total > 0)
    7. Aggregate to one row per unitid with columns: unitid, total_enrollment_race, urm_enrollment, urm_share
    8. Save to parquet
    9. Run CP2 validation
  </action>
  <verify>
    - Output has one row per unitid (unique)
    - urm_share between 0 and 1 for all non-null values
    - No coded values remain
    - Total enrollment is positive for all rows
    - Race code mapping documented in script output
  </verify>
  <done>CP2 PASSED, URM defined and computed, file saved to data/processed/2026-02-15_enrollment_race_clean.parquet</done>
</task>

### Wave 4: Secondary Cleaning (Parallel — 3 tasks)

<task name="clean-sfr" type="auto" wave="4">
  <depends_on>fetch-sfr</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_ipeds_sfr.parquet</input>
    <output>data/processed/2026-02-15_sfr_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data
    3. Replace coded values (-1, -2, -3) with null in student_faculty_ratio
    4. Print distribution: min, max, mean, median, null count
    5. Save to parquet
    6. Run CP2 validation
  </action>
  <verify>
    - No coded values remain
    - student_faculty_ratio range: 1-100 for non-null values
    - Null rate less than 30%
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-02-15_sfr_clean.parquet</done>
</task>

<task name="clean-retention" type="auto" wave="4">
  <depends_on>fetch-retention</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_ipeds_retention.parquet</input>
    <output>data/processed/2026-02-15_retention_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data
    3. Replace coded values (-1, -2, -3) with null in retention_rate
    4. Print distribution: min, max, mean, median, null count
    5. Verify retention_rate scale (0-100 expected)
    6. Save to parquet
    7. Run CP2 validation
  </action>
  <verify>
    - No coded values remain
    - retention_rate range: 0-100 for non-null values
    - Null rate less than 30%
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-02-15_retention_clean.parquet</done>
</task>

<task name="clean-scorecard" type="auto" wave="4">
  <depends_on>fetch-scorecard</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-02-15_scorecard_earnings.parquet</input>
    <output>data/processed/2026-02-15_scorecard_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data
    3. Replace coded values with null in earnings_med, earnings_mean, count_working
    4. Print distribution of earnings_med: min, max, mean, median, null count
    5. Print coverage: how many institutions have non-null earnings
    6. Save to parquet
    7. Run CP2 validation
  </action>
  <verify>
    - No coded values remain
    - earnings_med range: 10,000-300,000 for non-null values
    - Coverage rate documented
  </verify>
  <done>CP2 PASSED, coverage documented, file saved to data/processed/2026-02-15_scorecard_clean.parquet</done>
</task>

### Wave 5: Core Joins (Sequential — 2 tasks)

<task name="join-core" type="auto" wave="5">
  <depends_on>clean-directory, clean-grad-rates, clean-admissions, clean-fsa-grants</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1 for each join</cardinality>
  <files>
    <input>data/processed/2026-02-15_directory_clean.parquet</input>
    <input>data/processed/2026-02-15_grad_rates_clean.parquet</input>
    <input>data/processed/2026-02-15_admissions_clean.parquet</input>
    <input>data/processed/2026-02-15_fsa_grants_clean.parquet</input>
    <output>data/processed/2026-02-15_core_joined.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load all four cleaned datasets
    3. Capture pre-state: row counts for each dataset, key overlap between directory and each other dataset
    4. Start with directory as the base (LEFT join to preserve all 4-yr public/private nonprofit institutions):
       a. LEFT JOIN directory + grad_rates ON unitid (1:1 expected)
       b. LEFT JOIN result + admissions ON unitid (1:1 expected)
       c. LEFT JOIN result + fsa_grants ON unitid (1:1 expected)
    5. REASONING: LEFT join from directory base because directory defines our analysis universe (4-yr public/private nonprofit). Other sources may not have data for every institution. Null values in joined columns indicate data gaps, not exclusions.
    6. Compute pell_share = pell_recipients / enrollment_undergrad (where both non-null and enrollment_undergrad > 0)
    7. Validate each join:
       - Check key overlap percentage
       - Verify no fan-out (result rows == directory rows after each join)
       - Document how many institutions lack grad rate, admissions, FSA data
    8. Save to parquet
    9. Run CP3 validation
  </action>
  <verify>
    - Result row count equals directory row count (LEFT join preserves all)
    - No fan-out from any join
    - pell_share between 0 and 1 for non-null values
    - Key overlap documented for each join
    - Null rates documented for grad_rate_150pct, admission_rate, pell_share
  </verify>
  <done>CP3 PASSED, core join complete, file saved to data/processed/2026-02-15_core_joined.parquet</done>
</task>

<task name="join-demographics" type="auto" wave="5">
  <depends_on>join-core, clean-enrollment-race</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/2026-02-15_core_joined.parquet</input>
    <input>data/processed/2026-02-15_enrollment_race_clean.parquet</input>
    <output>data/processed/2026-02-15_core_demographics.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load core joined dataset and enrollment race clean dataset
    3. Capture pre-state: row counts, key overlap
    4. LEFT JOIN core + enrollment_race ON unitid (1:1 expected since enrollment_race was aggregated to institution level)
    5. Validate: no fan-out, result rows == core rows
    6. Document null rate for urm_share
    7. Save to parquet
    8. Run CP3 validation
  </action>
  <verify>
    - Result row count equals core row count
    - No fan-out
    - urm_share between 0 and 1 for non-null values
    - urm_share null rate documented
  </verify>
  <done>CP3 PASSED, file saved to data/processed/2026-02-15_core_demographics.parquet</done>
</task>

### Wave 6: Resource Joins and Banding (Sequential — 2 tasks)

<task name="join-resources" type="auto" wave="6">
  <depends_on>join-demographics, clean-sfr, clean-retention</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1 for each join</cardinality>
  <files>
    <input>data/processed/2026-02-15_core_demographics.parquet</input>
    <input>data/processed/2026-02-15_sfr_clean.parquet</input>
    <input>data/processed/2026-02-15_retention_clean.parquet</input>
    <output>data/processed/2026-02-15_pre_analysis.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load core demographics, SFR clean, retention clean
    3. Capture pre-state: row counts, key overlap
    4. LEFT JOIN core_demographics + sfr ON unitid (1:1)
    5. LEFT JOIN result + retention ON unitid (1:1)
    6. Validate: no fan-out, result rows == core_demographics rows
    7. Document null rates for student_faculty_ratio, retention_rate
    8. Print overall dataset summary: shape, columns, null rates per column
    9. Save to parquet
    10. Run CP3 validation
  </action>
  <verify>
    - Result row count equals core_demographics row count
    - No fan-out from either join
    - student_faculty_ratio and retention_rate null rates documented
    - All expected columns present: unitid, inst_name, grad_rate_150pct, admission_rate, pell_share, urm_share, student_faculty_ratio, retention_rate, inst_control, open_admissions, hbcu, enrollment_undergrad
  </verify>
  <done>CP3 PASSED, file saved to data/processed/2026-02-15_pre_analysis.parquet</done>
</task>

<task name="create-bands" type="auto" wave="6">
  <depends_on>join-resources</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_pre_analysis.parquet</input>
    <output>data/processed/2026-02-15_analysis.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load pre-analysis dataset
    3. Capture pre-state: shape, admission_rate distribution (to verify band cutpoints)
    4. Create selectivity_band based on admission_rate:
       - "Highly Selective": admission_rate less than 0.25
       - "Selective": admission_rate >= 0.25 AND less than 0.50
       - "Moderately Selective": admission_rate >= 0.50 AND less than 0.75
       - "Less Selective/Open": admission_rate >= 0.75 OR open_admissions == 1 OR admission_rate is null
       REASONING: Cutpoints at 25%, 50%, 75% create interpretable quartile-like bands. Open-admission institutions are classified as "Less Selective/Open" regardless of reported admission rate. Null admission rates (institutions not reporting) also go to "Less Selective/Open" to avoid excluding them.
    5. Create pell_band based on pell_share:
       - "Low Pell (under 20%)": pell_share less than 0.20
       - "Moderate Pell (20-40%)": pell_share >= 0.20 AND less than 0.40
       - "High Pell (40-60%)": pell_share >= 0.40 AND less than 0.60
       - "Very High Pell (60%+)": pell_share >= 0.60
       Null pell_share remains null band.
    6. Create urm_band based on urm_share:
       - "Low URM (under 20%)": urm_share less than 0.20
       - "Moderate URM (20-40%)": urm_share >= 0.20 AND less than 0.40
       - "High URM (40-60%)": urm_share >= 0.40 AND less than 0.60
       - "Very High URM (60%+)": urm_share >= 0.60
       Null urm_share remains null band.
    7. Print band distributions: value_counts for selectivity_band, pell_band, urm_band
    8. Verify all institutions have a selectivity_band assigned
    9. Save as the FINAL analysis dataset
    10. Run CP3 validation
  </action>
  <verify>
    - All rows have a selectivity_band (no nulls)
    - Band values match expected labels exactly
    - Band distributions are reasonable (no single band has less than 5% of institutions)
    - Row count unchanged from input
    - All prior columns preserved plus 3 new band columns
    - Output saved as data/processed/2026-02-15_analysis.parquet
  </verify>
  <done>CP3 PASSED, band distributions documented, FINAL analysis dataset saved to data/processed/2026-02-15_analysis.parquet</done>
</task>

### Wave 7: Primary Descriptive Analysis (Parallel — 5 tasks)

<task name="descriptive-by-selectivity" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_descriptive_by_selectivity.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Group by selectivity_band
    4. Compute for each band:
       - n (count of institutions)
       - grad_rate_150pct: median, mean, std, Q1 (25th), Q3 (75th)
       - admission_rate: median, mean
       - pell_share: median, mean
       - urm_share: median, mean
       - student_faculty_ratio: median, mean
       - retention_rate: median, mean
    5. Order bands from most to least selective
    6. Print the full summary table
    7. Save to output/analysis/ as parquet
  </action>
  <verify>
    - Output has exactly 4 rows (one per selectivity band)
    - All metric columns are non-null
    - Graduation rate medians decrease from Highly Selective to Less Selective (expected but verify)
    - n values sum to total institution count
  </verify>
  <done>Descriptive table saved to output/analysis/2026-02-15_descriptive_by_selectivity.parquet</done>
</task>

<task name="crosstab-selectivity-pell" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_crosstab_selectivity_pell.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Filter to rows where both selectivity_band and pell_band are non-null
    4. Group by selectivity_band, pell_band
    5. Compute: n, mean grad_rate_150pct, median grad_rate_150pct
    6. Pivot into a matrix format: rows = selectivity bands, columns = Pell bands
    7. Print the cross-tabulation table
    8. INTERPRETATION: Within each selectivity band, does grad rate vary by Pell share? This tests whether student body composition matters beyond selectivity.
    9. Save to output/analysis/ as parquet
  </action>
  <verify>
    - Output has rows for each selectivity x Pell band combination that exists
    - n values are positive
    - Grad rate values are in plausible range (0-100)
  </verify>
  <done>Cross-tabulation saved to output/analysis/2026-02-15_crosstab_selectivity_pell.parquet</done>
</task>

<task name="crosstab-selectivity-urm" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_crosstab_selectivity_urm.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Filter to rows where both selectivity_band and urm_band are non-null
    4. Group by selectivity_band, urm_band
    5. Compute: n, mean grad_rate_150pct, median grad_rate_150pct
    6. Pivot into a matrix format: rows = selectivity bands, columns = URM bands
    7. Print the cross-tabulation table
    8. Save to output/analysis/ as parquet
  </action>
  <verify>
    - Output has rows for each selectivity x URM band combination
    - n values are positive
    - Grad rate values in plausible range
  </verify>
  <done>Cross-tabulation saved to output/analysis/2026-02-15_crosstab_selectivity_urm.parquet</done>
</task>

<task name="correlation-matrix" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_correlation_matrix.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Select continuous variables: grad_rate_150pct, admission_rate, pell_share, urm_share, student_faculty_ratio, retention_rate
    4. Drop rows with any null in these columns (listwise deletion for correlation)
    5. Document how many rows remain after listwise deletion
    6. Compute Pearson correlation matrix using .pearson_corr() or manual computation
    7. Also compute Spearman rank correlation matrix (use .rank() then .pearson_corr())
    8. Print both matrices formatted clearly
    9. Highlight key correlations: grad_rate vs admission_rate, grad_rate vs pell_share, grad_rate vs urm_share
    10. Save both matrices (Pearson and Spearman) to output/analysis/ as parquet
  </action>
  <verify>
    - Correlation matrix is symmetric
    - Diagonal values are 1.0
    - All values between -1 and 1
    - Key correlations documented (grad_rate vs admission_rate expected negative and strong)
    - Sample size for correlation documented
  </verify>
  <done>Correlation matrices saved to output/analysis/2026-02-15_correlation_matrix.parquet</done>
</task>

<task name="outperformers" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_outperformers.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. For each selectivity_band:
       a. Compute band median and standard deviation of grad_rate_150pct
       b. Flag institutions where grad_rate_150pct > band_median + 1*SD as "overperformer"
       c. Flag institutions where grad_rate_150pct < band_median - 1*SD as "underperformer"
       d. Flag remaining as "typical"
    4. Create performance_flag column: "overperformer", "underperformer", "typical"
    5. Print count of each flag by selectivity band
    6. For overperformers and underperformers, print summary characteristics:
       - Mean pell_share, urm_share, student_faculty_ratio, retention_rate, inst_control distribution
    7. INTERPRETATION: What distinguishes institutions that beat expectations from those that lag?
    8. Save full dataset with performance_flag to output/analysis/
  </action>
  <verify>
    - All rows have a performance_flag
    - Overperformers have grad rates above band median + 1 SD
    - Underperformers have grad rates below band median - 1 SD
    - Characterization of over/underperformers documented
  </verify>
  <done>Outperformer analysis saved to output/analysis/2026-02-15_outperformers.parquet</done>
</task>

### Wave 8: Supplementary Analysis (Parallel — 2 tasks)

<task name="regression-models" type="auto" wave="8">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_regression_results.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Prepare regression data: select rows where grad_rate_150pct, admission_rate, pell_share, urm_share, student_faculty_ratio, inst_control are all non-null. Document N.
    4. Create sector_private dummy: 1 if inst_control == 2, else 0
    5. Run three OLS regressions using numpy/scipy (NOT sklearn — keep dependencies light):
       Model 1: grad_rate_150pct ~ admission_rate
       Model 2: grad_rate_150pct ~ admission_rate + pell_share + urm_share
       Model 3: grad_rate_150pct ~ admission_rate + pell_share + urm_share + student_faculty_ratio + sector_private
    6. For each model, report:
       - R-squared
       - Adjusted R-squared
       - Coefficients with standard errors
       - Sample size N
    7. KEY COMPARISON: R-squared increase from Model 1 to Model 2 quantifies how much student body composition explains beyond selectivity.
    8. Print formatted regression table
    9. REASONING: Regressions are SUPPLEMENTARY to the descriptive analysis. They add nuance by quantifying marginal contributions, but the narrative is driven by the descriptive statistics and cross-tabulations.
    10. Save regression coefficients, R-squared values, and model comparison to output/analysis/ as parquet
  </action>
  <verify>
    - All three models produce valid coefficients
    - R-squared values between 0 and 1
    - R-squared increases from Model 1 to Model 3
    - admission_rate coefficient is negative (higher admission rate = lower grad rate)
    - Sample size documented
    - Model comparison (R-squared differences) documented
  </verify>
  <done>Regression results saved to output/analysis/2026-02-15_regression_results.parquet</done>
</task>

<task name="sector-comparison" type="auto" wave="8">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/analysis/2026-02-15_sector_comparison.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Group by selectivity_band AND inst_control (1=Public, 2=Private nonprofit)
    4. Compute: n, median grad_rate_150pct, mean grad_rate_150pct, median pell_share, median urm_share
    5. Print comparison table
    6. INTERPRETATION: Within the same selectivity band, do private nonprofits have higher grad rates than publics? If so, is the gap explained by differences in Pell share and URM share?
    7. Save to output/analysis/ as parquet
  </action>
  <verify>
    - Output has rows for each selectivity band x sector combination
    - n values sum correctly
    - Grad rate values in plausible range
  </verify>
  <done>Sector comparison saved to output/analysis/2026-02-15_sector_comparison.parquet</done>
</task>

### Wave 9: Primary Visualizations (Parallel — 5 tasks)

<task name="viz-scatter-grad-admit" type="auto" wave="9">
  <depends_on>create-bands</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/figures/2026-02-15_grad_rate_vs_admission_rate.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load analysis dataset
    3. Filter to rows where both grad_rate_150pct and admission_rate are non-null
    4. Create scatter plot:
       - X-axis: admission_rate (multiply by 100 for display as percentage)
       - Y-axis: grad_rate_150pct
       - Color: inst_control mapped to "Public" / "Private Nonprofit" labels
       - Alpha: 0.5 for overplotting
       - Size: 1.5
    5. Add trend line (linear regression line) per sector
    6. Labels:
       - Title: "College Graduation Rate vs. Admission Rate"
       - Subtitle: "4-Year Public and Private Nonprofit Institutions, 2020"
       - X: "Admission Rate (%)"
       - Y: "Graduation Rate (150% time, %)"
       - Caption: "Source: IPEDS 2020. Graduation rate is for first-time, full-time bachelor-seeking students."
    7. Use colorblind-safe palette
    8. Theme: minimal, 300 DPI
    9. Save to output/figures/
  </action>
  <verify>
    - File exists and size > 50KB
    - Both sectors visible in legend
    - Axes correctly labeled
  </verify>
  <done>Figure saved to output/figures/2026-02-15_grad_rate_vs_admission_rate.png</done>
</task>

<task name="viz-boxplot-selectivity" type="auto" wave="9">
  <depends_on>create-bands</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/figures/2026-02-15_boxplot_grad_rate_by_selectivity.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load analysis dataset, filter to non-null grad_rate_150pct
    3. Create box plot:
       - X-axis: selectivity_band (ordered: Highly Selective, Selective, Moderately Selective, Less Selective/Open)
       - Y-axis: grad_rate_150pct
       - Fill: selectivity_band with colorblind-safe palette
    4. Add individual points (jittered) with low alpha for context
    5. Labels:
       - Title: "Graduation Rate Distribution by Selectivity Band"
       - Subtitle: "4-Year Public and Private Nonprofit Institutions, 2020"
       - X: "Selectivity Band"
       - Y: "Graduation Rate (150% time, %)"
       - Caption: "Source: IPEDS 2020."
    6. Theme: minimal, 300 DPI
    7. Save to output/figures/
  </action>
  <verify>
    - File exists and size > 50KB
    - Four boxes visible (one per band)
  </verify>
  <done>Figure saved to output/figures/2026-02-15_boxplot_grad_rate_by_selectivity.png</done>
</task>

<task name="viz-heatmap-selectivity-pell" type="auto" wave="9">
  <depends_on>crosstab-selectivity-pell</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-02-15_crosstab_selectivity_pell.parquet</input>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <output>output/figures/2026-02-15_heatmap_selectivity_pell.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load analysis dataset
    3. Filter to non-null grad_rate_150pct, selectivity_band, pell_band
    4. Group by selectivity_band and pell_band, compute mean grad_rate_150pct and n
    5. Create heatmap (geom_tile):
       - X-axis: pell_band (ordered)
       - Y-axis: selectivity_band (ordered)
       - Fill: mean grad_rate_150pct (continuous color scale)
       - Annotate each cell with the mean value and n
    6. Labels:
       - Title: "Mean Graduation Rate by Selectivity and Pell Share"
       - Subtitle: "Do institutions with similar selectivity but different Pell shares have different graduation rates?"
       - X: "Pell Grant Recipient Share"
       - Y: "Selectivity Band"
       - Caption: "Source: IPEDS 2020, FSA 2020. Cell values show mean graduation rate (n institutions)."
    7. Use sequential color scale (e.g., viridis or Blues)
    8. Theme: minimal, 300 DPI
    9. Save to output/figures/
  </action>
  <verify>
    - File exists and size > 50KB
    - Cells have visible annotations
    - Color scale represents graduation rate
  </verify>
  <done>Figure saved to output/figures/2026-02-15_heatmap_selectivity_pell.png</done>
</task>

<task name="viz-correlation-heatmap" type="auto" wave="9">
  <depends_on>correlation-matrix</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-02-15_correlation_matrix.parquet</input>
    <output>output/figures/2026-02-15_correlation_heatmap.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load correlation matrix from parquet
    3. Create heatmap of Pearson correlations:
       - Variables: grad_rate_150pct, admission_rate, pell_share, urm_share, student_faculty_ratio, retention_rate
       - Fill: correlation value (diverging color scale: red=negative, blue=positive)
       - Annotate each cell with the correlation coefficient (2 decimal places)
    4. Labels:
       - Title: "Correlation Matrix of Key Institutional Variables"
       - Caption: "Source: IPEDS 2020, FSA 2020. Pearson correlations. N institutions with complete data shown."
    5. Theme: minimal, 300 DPI
    6. Save to output/figures/
  </action>
  <verify>
    - File exists and size > 50KB
    - Diagonal values are 1.0
    - Color scale is diverging
    - Cell annotations visible
  </verify>
  <done>Figure saved to output/figures/2026-02-15_correlation_heatmap.png</done>
</task>

<task name="viz-sector-comparison" type="auto" wave="9">
  <depends_on>sector-comparison</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-02-15_sector_comparison.parquet</input>
    <output>output/figures/2026-02-15_sector_comparison.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load sector comparison results
    3. Create grouped bar chart:
       - X-axis: selectivity_band (ordered)
       - Y-axis: median grad_rate_150pct
       - Fill: sector (Public vs Private Nonprofit)
       - Position: dodge
    4. Labels:
       - Title: "Median Graduation Rate by Selectivity Band and Sector"
       - Subtitle: "Public vs. Private Nonprofit 4-Year Institutions, 2020"
       - X: "Selectivity Band"
       - Y: "Median Graduation Rate (%)"
       - Caption: "Source: IPEDS 2020."
    5. Use colorblind-safe palette, theme minimal, 300 DPI
    6. Save to output/figures/
  </action>
  <verify>
    - File exists and size > 50KB
    - Two bars per selectivity band (Public, Private Nonprofit)
    - Legend present
  </verify>
  <done>Figure saved to output/figures/2026-02-15_sector_comparison.png</done>
</task>

### Wave 10: Supplementary Join and Visualization (Sequential — 2 tasks)

<task name="join-scorecard" type="auto" wave="10">
  <depends_on>create-bands, clean-scorecard</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <input>data/processed/2026-02-15_scorecard_clean.parquet</input>
    <output>data/processed/2026-02-15_analysis_with_earnings.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset and scorecard clean
    3. LEFT JOIN analysis + scorecard ON unitid (1:1)
    4. Document Scorecard coverage: what percentage of analysis institutions have earnings data?
    5. Document coverage BY selectivity band (expect lower coverage for highly selective)
    6. Save to parquet
    7. Run CP3 validation
  </action>
  <verify>
    - Row count equals analysis row count (LEFT join)
    - Coverage rate documented overall and by selectivity band
    - earnings_med range plausible for non-null values
  </verify>
  <done>CP3 PASSED, Scorecard coverage documented, file saved to data/processed/2026-02-15_analysis_with_earnings.parquet</done>
</task>

<task name="viz-residual-scatter" type="auto" wave="10">
  <depends_on>regression-models</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-02-15_analysis.parquet</input>
    <input>output/analysis/2026-02-15_regression_results.parquet</input>
    <output>output/figures/2026-02-15_actual_vs_predicted.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load analysis dataset
    3. Re-fit Model 3 (or load coefficients from regression results) to compute predicted grad rate for each institution
    4. Create scatter plot:
       - X-axis: predicted grad_rate_150pct (from Model 3)
       - Y-axis: actual grad_rate_150pct
       - Add 45-degree reference line (perfect prediction)
       - Color by selectivity_band
       - Alpha: 0.5
    5. Points above the line are outperformers (graduating more than expected); below are underperformers
    6. Labels:
       - Title: "Actual vs. Predicted Graduation Rate"
       - Subtitle: "Predicted from admission rate, Pell share, URM share, student-faculty ratio, and sector"
       - X: "Predicted Graduation Rate (%)"
       - Y: "Actual Graduation Rate (%)"
       - Caption: "Source: IPEDS 2020. Points above the diagonal outperform model expectations."
    7. Theme: minimal, 300 DPI
    8. Save to output/figures/
  </action>
  <verify>
    - File exists and size > 50KB
    - 45-degree line visible
    - Points colored by selectivity band
    - Both axes have same range
  </verify>
  <done>Figure saved to output/figures/2026-02-15_actual_vs_predicted.png</done>
</task>

---

## Output Specification

### Notebook Structure

**Marimo Notebook Sections:**

1. **Setup and Imports** — Dependencies, configuration
2. **Data Loading** — Load from data/processed/2026-02-15_analysis.parquet
3. **Data Overview** — Shape, types, sample, null rates
4. **Institutional Profile by Selectivity** — Descriptive statistics table
5. **Cross-Tabulations** — Selectivity x Pell, Selectivity x URM
6. **Correlation Analysis** — Correlation matrix and heatmap
7. **Outperformer Analysis** — Who beats expectations?
8. **Sector Comparison** — Public vs. Private Nonprofit
9. **Supplementary Regression** — Models 1-3, R-squared comparison
10. **Visualizations** — All key figures
11. **Findings Summary** — Markdown synthesis

### Report Structure

**Report Sections:**

1. **Executive Summary** — Key findings in 4-5 sentences
2. **Research Question** — The chicken-or-egg problem with graduation rates
3. **Data and Methods** — IPEDS 2020, sources, cleaning, binning approach
4. **Findings** — Results organized by analysis type with visualizations
5. **Limitations** — FTFT cohort bias, Scorecard Title IV bias, single year, coded value handling
6. **Implications** — What this means for thinking about college "quality"
7. **Data Sources** — Full citations

### Analysis Requirements

| Analysis | Type | Purpose | Output File |
|----------|------|---------|-------------|
| Descriptive by selectivity | Descriptive | Show how characteristics cluster by selectivity | `2026-02-15_descriptive_by_selectivity.parquet` |
| Cross-tab selectivity x Pell | Descriptive | Test if Pell share matters within selectivity bands | `2026-02-15_crosstab_selectivity_pell.parquet` |
| Cross-tab selectivity x URM | Descriptive | Test if URM share matters within selectivity bands | `2026-02-15_crosstab_selectivity_urm.parquet` |
| Correlation matrix | Correlation | Quantify pairwise relationships | `2026-02-15_correlation_matrix.parquet` |
| Outperformers | Descriptive | Identify who beats/lags expectations | `2026-02-15_outperformers.parquet` |
| Regression (3 models) | Regression (supplementary) | Quantify incremental R-squared | `2026-02-15_regression_results.parquet` |
| Sector comparison | Descriptive | Public vs private within bands | `2026-02-15_sector_comparison.parquet` |

#### Modeling Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Correlation method | Both Pearson and Spearman | Pearson for linear; Spearman for monotonic (more robust to non-normality) |
| Regression method | OLS (numpy/scipy) | Standard linear regression; keep dependencies light |
| Outlier treatment | None (keep all institutions) | Outliers are real institutions; removing them biases toward the middle |
| Missing data in regression | Listwise deletion | Standard for OLS; document N reduction |
| Band cutpoints | Fixed quartile-like (25/50/75%) | Simple, interpretable, replicable |

### Visualization Requirements

| Figure | Type | Purpose | File Name |
|--------|------|---------|-----------|
| Grad rate vs admission rate | Scatter + trend | Core relationship | `2026-02-15_grad_rate_vs_admission_rate.png` |
| Grad rate by selectivity band | Box plot | Distribution within bands | `2026-02-15_boxplot_grad_rate_by_selectivity.png` |
| Heatmap selectivity x Pell | Heatmap (tile) | Cross-tabulation visualization | `2026-02-15_heatmap_selectivity_pell.png` |
| Correlation matrix | Heatmap | All pairwise correlations | `2026-02-15_correlation_heatmap.png` |
| Sector comparison | Grouped bar | Public vs private by band | `2026-02-15_sector_comparison.png` |
| Actual vs predicted | Scatter + 45-degree line | Outperformer identification | `2026-02-15_actual_vs_predicted.png` |

### Deliverables Checklist

| Deliverable | Location | Format |
|-------------|----------|--------|
| Plan document | `research/2026-02-15 College Graduation Rate Selectivity Analysis/` | `.md` |
| Marimo notebook | `research/2026-02-15 College Graduation Rate Selectivity Analysis/` | `.py` |
| Stakeholder report | `research/2026-02-15 College Graduation Rate Selectivity Analysis/` | `.md` |
| Raw data (8 files) | `research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/` | `.parquet` |
| Processed data | `research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/` | `.parquet` |
| Analysis results (7 files) | `research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/` | `.parquet` |
| Figures (6 files) | `research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/` | `.png` |

---

## Validation Checkpoints

### CP1: After Data Fetch

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count (directory) | 2,000-4,000 | 0 or > 10,000 |
| Row count (grad rates, after filter) | 1,500-4,000 | 0 |
| Row count (admissions, after filter) | 1,500-4,000 | 0 |
| Critical columns present | All listed in query spec | Missing unitid or primary variable |
| Year present | 2020 | Missing |
| Critical variable missingness | < 30% | > 90% |

### CP2: After Cleaning

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count change | 0% (replacing values, not dropping rows) | > 50% loss |
| Suppression rate | < 20% | > 50% |
| Coded values remaining | 0 | Any -1, -2, -3 in analysis vars |
| Derived variables valid | admission_rate in [0,1]; pell_share in [0,1]; urm_share in [0,1] | Out of range values |

### CP3: After Transformation (Joins and Banding)

| Check | Expected | STOP If |
|-------|----------|---------|
| Row count after LEFT joins | Same as directory base | > 10% increase (fan-out) |
| Key overlap | > 60% for each join | < 30% (data incompatibility) |
| Band assignment | 100% of rows have selectivity_band | Any null selectivity_band |
| No unexpected NAs in band columns | selectivity_band fully assigned | Nulls in selectivity_band |
| Analysis dataset has all required columns | 12+ columns per must-haves | Missing any must-have column |

### CP4: Before Output

| Check | Expected | STOP If |
|-------|----------|---------|
| All 6 planned figures generated | Yes | Missing figures |
| All 7 analysis output files exist | Yes | Missing analysis files |
| Report sections complete | Yes | Missing Executive Summary or Limitations |
| Notebook runs without error | Yes | Execution errors |

### QA Tolerance Decisions

| Check | Default Threshold | Project Threshold | Rationale |
|-------|-------------------|-------------------|-----------|
| Suppression rate | < 50% STOP | < 50% (same) | Standard threshold sufficient |
| Join row loss (LEFT join) | < 10% acceptable | 0% expected (LEFT join) | LEFT joins should not lose rows |
| Join key overlap | > 80% | > 60% | Some institutions may not report to all sources; 60% still viable |
| Listwise deletion for regression | N/A | Document N reduction; acceptable if N > 500 | Need sufficient sample for regression |
| Band minimum size | N/A | > 5% of institutions per band | Bands with < 5% are statistically thin |

---

## Decisions Log

| Decision | Options Considered | Choice Made | Rationale |
|----------|-------------------|-------------|-----------|
| Analysis year | 2018, 2019, 2020 | 2020 | Most recent year with SFR and retention data; GR reflects pre-COVID cohort |
| Selectivity measure | Admission rate vs SAT/ACT percentiles | Admission rate | Better coverage post-test-optional era; simpler interpretation |
| Pell data source | IPEDS SFA vs FSA grants | FSA grants | FSA available through 2021; more direct Pell count |
| Institution scope | All vs exclude for-profit | Exclude for-profit | For-profits have fundamentally different business models |
| Resource proxy | Finance data vs student-faculty ratio | Student-faculty ratio | Finance data only through 2017; SFR through 2020 |
| Methodology emphasis | Descriptive-first vs regression-first | Descriptive-first | Per user preference; regressions supplementary |
| Join type | INNER vs LEFT | LEFT from directory | Preserve all 4-yr institutions; document gaps rather than exclude |
| Debt analysis | Include vs exclude | Exclude | Median debt not available via Portal mirror |
| Earnings data | Primary vs supplementary | Supplementary | Scorecard Title IV coverage bias makes it unsuitable as primary metric |

### Key Decision Detail

#### Selectivity Measure Selection
**Question:** Should selectivity be measured by admission rate or standardized test score percentiles?
**Options:**
1. Admission rate (number_admitted / number_applied) — universally available for reporting institutions; simple interpretation
2. SAT/ACT 25th/75th percentiles — more granular; captures academic preparation directly

**Resolution:** Admission rate
**Rationale:** The post-test-optional era (accelerated by COVID-19) has reduced SAT/ACT reporting substantially. Admission rate has broader coverage and is the more commonly understood selectivity metric. SAT/ACT data from admissions-requirements could supplement but would reduce the analysis sample.
**Decided By:** Agent (within autonomous scope, confirmed by user)

#### Pell Share Data Source
**Question:** Use IPEDS Student Financial Aid (SFA) or FSA Grants for Pell recipient counts?
**Options:**
1. IPEDS SFA — Integrated with other IPEDS data; but `type_of_aid` code for Pell needs verification; available through 2017 only
2. FSA Grants — Direct Pell recipient counts; available through 2021; separate source but joins on unitid

**Resolution:** FSA Grants
**Rationale:** FSA grants cover 2020 directly, while SFA data is only through 2017 in the mirror. The Pell recipient count is a direct field in FSA, avoiding the need to filter by aid type.
**Decided By:** Agent (within autonomous scope, confirmed by user)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner/Stage |
|------|------------|--------|------------|-------------|
| Subcohort code ambiguity in grad-rates | Medium | High | Inspect codebook during Stage 5 fetch; document selected code with reasoning | Stage 5 (fetch-grad-rates) |
| Race code mapping uncertainty for URM | Medium | Medium | Inspect unique race values and codebook during fetch; document URM definition | Stage 5 (fetch-enrollment-race) |
| Low join overlap for some sources | Medium | Medium | Using LEFT join to preserve all institutions; document null rates | Stage 7 (all joins) |
| Open-admission institutions lack admissions data | High | Low | Classify as "Less Selective/Open" regardless of missing data | Stage 7 (create-bands) |
| Scorecard earnings coverage varies by selectivity | High | Low | Document as limitation; supplementary use only | Stage 7 (join-scorecard) |
| Regression assumptions violated | Medium | Low | Supplementary analysis only; note violations in report | Stage 8 (regression-models) |
| Band cutpoints produce thin bands | Low | Medium | Verify band distributions; adjust cutpoints if any band < 5% | Stage 7 (create-bands) |
| FTFT cohort bias confounds interpretation | High | Medium | Document prominently as a key caveat; part of the research narrative | Report |
| COVID effects on 2020 institutional data | Low | Low | GR reflects 2014 cohort (pre-COVID); SFR/retention may show minor effects | Document in report |

---

## Trade-offs Accepted

| We Accepted | In Order To | Downside |
|-------------|-------------|----------|
| Single year (2020) only | Have SFR and retention data available | Cannot show trends over time |
| FTFT cohort graduation rate | Use IPEDS standard measure | Systematically understates completion at open-access institutions |
| Student-faculty ratio as resource proxy | Avoid 3-year data lag from finance data | Imperfect measure of institutional resources |
| Scorecard earnings as supplementary only | Avoid Title IV coverage bias driving narrative | Cannot definitively link selectivity to post-college outcomes |
| Fixed band cutpoints (25/50/75%) | Simple, intuitive, replicable interpretation | May not match natural clustering in data |
| LEFT joins from directory base | Preserve all 4-year institutions | Some institutions have null values for key variables |
| Exclude for-profit institutions | Focus on comparable public/nonprofit institutions | Incomplete picture of all postsecondary |

---

## Binning Strategy

### Selectivity Bands

| Band | Admission Rate Condition | Additional Condition |
|------|--------------------------|---------------------|
| Highly Selective | < 25% | — |
| Selective | 25% - 49.9% | — |
| Moderately Selective | 50% - 74.9% | — |
| Less Selective/Open | >= 75% | OR open_admissions == 1 OR admission_rate is null |

**Rationale:** Quartile-like cutpoints at 25%, 50%, 75% create bands that are intuitive for non-technical audiences. Open-admission institutions and those not reporting admissions data are grouped together in "Less Selective/Open" because they effectively have no selectivity barrier.

### Pell Share Bands

| Band | Pell Share Condition |
|------|---------------------|
| Low Pell (under 20%) | < 20% |
| Moderate Pell (20-40%) | 20% - 39.9% |
| High Pell (40-60%) | 40% - 59.9% |
| Very High Pell (60%+) | >= 60% |

### URM Share Bands

| Band | URM Share Condition |
|------|---------------------|
| Low URM (under 20%) | < 20% |
| Moderate URM (20-40%) | 20% - 39.9% |
| High URM (40-60%) | 40% - 59.9% |
| Very High URM (60%+) | >= 60% |

**Note:** Band cutpoints are starting proposals. If data distributions show that any band contains fewer than 5% of institutions, the create-bands script should document this and proceed (the cutpoints are still valid for interpretability even if distribution is uneven). If a band has fewer than 10 institutions, flag as WARNING in script output.

---

## Analysis Approach

### Primary: Descriptive Statistics and Correlations (Narrative-Driving)

The analysis is organized to build an intuitive, cumulative picture:

1. **First, establish the baseline:** Show how institutional characteristics cluster by selectivity band. This makes visible that selective institutions differ from less selective ones on almost every dimension (Pell share, URM share, resources, retention).

2. **Then, test the core question:** Cross-tabulate graduation rates by selectivity AND Pell share (and URM share). If graduation rates vary meaningfully within selectivity bands based on student body composition, this suggests selectivity alone does not explain graduation rates.

3. **Quantify the relationships:** The correlation matrix provides a single summary of how tightly all variables are related. Strong correlations between selectivity, demographics, and graduation rates confirm the "chicken-or-egg" dynamic.

4. **Identify exceptions:** The outperformer analysis finds institutions that beat or lag expectations. What characterizes them? This adds nuance — some institutions do better than their selectivity profile would predict.

5. **Compare sectors:** Within the same selectivity band, do public and private nonprofit institutions differ? This adds another layer to the "quality" interpretation.

### Supplementary: Regression (Nuance-Adding)

Three OLS models quantify how much variance in graduation rates is explained by:
- Model 1: Selectivity alone (R-squared baseline)
- Model 2: Selectivity + student body composition (R-squared increase shows demographics' contribution)
- Model 3: Full model with resources and sector (R-squared shows complete picture)

The R-squared increase from Model 1 to Model 2 is the key metric: it quantifies how much of the "selectivity effect" is actually a "student body composition effect."

---

## Current Status & To-Do's

### Current Phase

**Phase:** 2
**Stage:** 4 (Plan Creation)
**Status:** In Progress

### Active To-Do's

- [ ] Plan-checker validation (Stage 4.5)
- [ ] User approval of Plan (PSU2)
- [ ] Begin data fetch (Stage 5)

### Blocked Items

| Item | Blocker | Awaiting |
|------|---------|----------|
| Stage 5 execution | Plan-checker validation + User PSU2 approval | Automated plan check + user confirmation |

---

## QA Findings Summary

*To be populated during Stages 5-8 execution*

### QA Checkpoint Summary

| Checkpoint | Stage | Scripts Reviewed | BLOCKERs | WARNINGs | INFOs | Revisions Applied |
|------------|-------|------------------|----------|----------|-------|-------------------|
| QA1 (Post-Fetch) | 5 | — | — | — | — | — |
| QA2 (Post-Clean) | 6 | — | — | — | — | — |
| QA3 (Post-Transform) | 7 | — | — | — | — | — |
| QA4a (Post-Analysis) | 8.1 | — | — | — | — | — |
| QA4b (Post-Viz) | 8.2 | — | — | — | — | — |

---

## Final Review Log

*To be completed during Phase 5, Stage 12*

---

## Data Citations

*To be generated using education-data-context skill during execution*

### Primary Data Sources

> Integrated Postsecondary Education Data System (IPEDS), National Center for Education Statistics, U.S. Department of Education. Various survey components: Directory, Graduation Rates, Admissions and Enrollment, Fall Enrollment by Race, Student-Faculty Ratio, Fall Retention. Data year: 2020. Accessed via Education Data Portal mirrors, February 2026.

> Federal Student Aid (FSA) Grants Data, U.S. Department of Education. Pell Grant recipients and disbursements. Data year: 2020. Accessed via Education Data Portal mirrors, February 2026.

### Supplementary Data Sources

> College Scorecard, U.S. Department of Education. Earnings data. Accessed via Education Data Portal mirrors, February 2026.

---

## File Manifest

| File | Path | Description |
|------|------|-------------|
| Plan | `research/2026-02-15 College Graduation Rate Selectivity Analysis/2026-02-15 College Graduation Rate Selectivity Analysis Plan.md` | This document |
| Notebook | `research/2026-02-15 College Graduation Rate Selectivity Analysis/2026-02-15 College Graduation Rate Selectivity Analysis.py` | Marimo analysis notebook |
| Report | `research/2026-02-15 College Graduation Rate Selectivity Analysis/2026-02-15 College Graduation Rate Selectivity Analysis Report.md` | Stakeholder report |
| Learnings | `research/2026-02-15 College Graduation Rate Selectivity Analysis/LEARNINGS.md` | Session learnings |
| Raw Data | `research/2026-02-15 College Graduation Rate Selectivity Analysis/data/raw/2026-02-15_*.parquet` | Original data downloads (8 files) |
| Processed Data | `research/2026-02-15 College Graduation Rate Selectivity Analysis/data/processed/2026-02-15_*.parquet` | Cleaned and joined data |
| Analysis Results | `research/2026-02-15 College Graduation Rate Selectivity Analysis/output/analysis/2026-02-15_*.parquet` | Statistical analysis outputs (7 files) |
| Figures | `research/2026-02-15 College Graduation Rate Selectivity Analysis/output/figures/2026-02-15_*.png` | Visualizations (6 files) |
| Fetch Scripts | `research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage5_fetch/*.py` | Data retrieval code (8 scripts) |
| Clean Scripts | `research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage6_clean/*.py` | Context application code (8 scripts) |
| Transform Scripts | `research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage7_transform/*.py` | Join and banding code (5 scripts) |
| Analysis Scripts | `research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/stage8_analysis/*.py` | Analysis and visualization code (13 scripts) |
| QA Scripts | `research/2026-02-15 College Graduation Rate Selectivity Analysis/scripts/cr/*.py` | QA inspection scripts |
| STATE.md | `research/2026-02-15 College Graduation Rate Selectivity Analysis/STATE.md` | Session state file |
