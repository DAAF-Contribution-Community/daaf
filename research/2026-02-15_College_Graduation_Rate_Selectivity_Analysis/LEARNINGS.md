# Learnings: College Graduation Rate Selectivity Analysis

**Date:** 2026-02-15
**Data Sources:** IPEDS (graduation rates, admissions, directory, enrollment race, student-faculty ratio, retention), FSA (grants), College Scorecard (earnings)
**Analysis Type:** Descriptive statistics and correlations examining the relationship between graduation rates and institutional selectivity, with supplementary regression analysis

---

## What Worked Well

Approaches that succeeded and should be reused:

- **Wave-based parallel execution** for independent fetch and clean tasks saved significant time (8 fetch scripts in 2 waves, 8 clean scripts in 2 waves)
- **Per-script QA interleaving** caught the grad-rates 0-1 scale issue and enrollment-race sub-dimension issue before they could propagate downstream
- **Truth Hierarchy application:** Trusting actual data over Plan assumptions (0-1 scale discovery) prevented incorrect cleaning logic

---

## What Didn't Work

Approaches that failed, with explanations:

- **Plan row count estimates** for SFR and retention underestimated (Plan said 3,000-5,000; actual 5,836 for all institution types). The Portal returns all institution types, not just 4-year. Filtering to analysis scope happens at join stage, not fetch/clean.
- **Initial grad-rates clean script** (v1) failed because it assumed 0-100 scale. Required revision to _a.py with 0-1→0-100 conversion.
- **Initial enrollment-race clean script** (v1) failed because even after column filtering (to race-specific enrollment columns), sub-dimension rows (degree_seeking, class_level) remained. Required revision to _a.py with MAX aggregation.

---

## Surprises

Unexpected findings about data, access, or methodology:

- **IPEDS proportion scale is consistent:** Both `completion_rate_150pct` and `retention_rate` arrive as 0-1 proportions despite documentation suggesting 0-100. This is a Portal-level convention, not variable-specific.
- **Scorecard earnings year gap:** Year 2020 earnings data was unavailable; had to use 2018 (yae=10). This means earnings data is 2 years older than the IPEDS institutional data.
- **IPEDS graduation rate cohort_year:** For year=2020, the 150% completion cohort is 2015 entrants, not 2014 as initially assumed. The 150% window for a 4-year program is 6 years (2015+6=2021 reporting, but the data reports in year=2020).
- **Scorecard branch campus pattern:** 420 institutions have 8-digit unitids (branch campuses) that share identical parent-institution earnings. These won't match IPEDS 6-digit unitids.
- **URM share non-significant after economic controls:** urm_share has p=0.965 in full regression after controlling for pell_share — economic composition absorbs nearly all of the racial composition effect on graduation rates.
- **Moderate bivariate correlation ≠ multicollinearity:** pell_share × urm_share r=0.638 but VIF < 2 in regression — moderate bivariate correlation does not produce problematic multicollinearity in OLS.
- **Selective band sector reversal:** Public institutions have +12pp higher graduation rates than private nonprofits in the Selective band, despite serving more disadvantaged students. Reversal absent in other bands.
- **Scorecard coverage inversely related to institution size, not selectivity:** LS/O lowest coverage (72.2%). Differential suppression in Scorecard subgroup columns is driven by institutional enrollment size, contradicting the Plan's risk assumption that coverage would track selectivity.

---

## Access/Data Gotchas

Specific issues with data sources worth documenting:

### IPEDS

- `cc_basic_2021` column is 100% null when querying year=2020 (the Carnegie Classification column name includes its own vintage year)
- `open_admissions` flag is NOT in the directory endpoint — it comes from the admissions-enrollment endpoint
- Enrollment-race endpoint returns sub-dimension rows (degree_seeking=1/2, class_level=1-5) even when filtering specific race columns. Must aggregate to institution level.
- `subcohort` code for overall graduation rate needed codebook verification during fetch (not documented in advance)
- FSA grants `pell_recipients` has 0.76% fractional values from allocation splits across campuses
- Band label values in data use "under 20%"/"60%+" not "<20%"/"≥60%" — match labels from data, not Plan assumptions
- `sector_label` values use sentence case ("Private nonprofit") not title case ("Private Nonprofit") — case-sensitive matching required

### plotnine

- `guide=False` is not supported in plotnine; use `guides(fill="none")` as a separate layer instead
- Wide-format correlation matrices need explicit `unpivot()` before passing to plotnine heatmap geoms

### FSA

- Grant type code `grant_type==4` confirmed via Truth Hierarchy (data inspection) as correct Pell filter
- 6 native nulls (0.12%) in pell_recipients — minimal impact

### College Scorecard

- At `yae=10` (years after entry = 10), 15 of 29 columns are structurally 100% null — these columns are only populated at other yae values
- Uses native nulls (not coded -1/-2/-3 sentinels like IPEDS/CCD)
- 137 institutions have `count_working < 30` — low reliability for earnings estimates
- Title IV coverage bias: 30-50% at elite institutions, 80%+ at less selective. Critical limitation for cross-selectivity earnings comparison.

---

## Time Sinks

What took longer than expected and how to avoid:

- **FSA grants fetch** required 4 revisions (_a through _d) to get the correct grant_type filter. Future: always inspect available values before filtering.
- **Session restarts** (6 sessions for Stages 1-6) due to context exhaustion. The 34-task pipeline with per-script QA generates heavy context. Future: plan for ~5-6 tasks per session maximum.
- **Scale discovery** for IPEDS variables required script revision. Future: always profile raw data distributions before writing cleaning logic.

---

## Reusable Patterns

Code snippets, queries, or approaches to extract for reuse:

- **Coded value replacement pattern:** `pl.when(pl.col(col).is_in([-1, -2, -3])).then(None).otherwise(pl.col(col))` — standard for all IPEDS/CCD numeric columns
- **Sub-dimension aggregation:** When IPEDS returns multi-row-per-institution data even after column filtering, use MAX aggregation (equivalent to SUM when sub-categories are mutually exclusive)
- **100% null column detection:** `[c for c in df.columns if df[c].null_count() == df.shape[0]]` — useful for Scorecard and any dataset with structurally empty columns
- **Correlation matrix to heatmap:** `corr_wide.unpivot(index="variable_1", variable_name="variable_2", value_name="correlation")` — wide symmetric matrices must be unpivoted for plotnine `geom_tile()` heatmaps

---

## Data Quality Notes

Issues specific to this dataset/analysis:

| Variable | Issue | Rate | Handling |
|----------|-------|------|----------|
| student_faculty_ratio | SFR=110 outlier (unitid 246035) | 1 institution | Preserved; may winsorize in Stage 7 |
| student_faculty_ratio | 1 native null | 0.02% | Preserved as null |
| retention_rate | Native nulls | 11.2% (654/5,836) | Preserved; within 30% tolerance |
| retention_rate | 0% and 100% extremes | 55 at 0%, 333 at 100% | Legitimate for small/specialized institutions |
| retention_rate | COVID effects | Visible at selective institutions | Legitimate (2020 reporting year) |
| admission_rate | Open-admission nulls | 1.2% (23/1,989) | Preserved; these institutions lack application counts |
| pell_recipients | Fractional values | 0.76% (38/4,994) | Rounded to integers |
| earnings_med | Branch campus duplication | 420 8-digit unitids | Won't match IPEDS in join; benign |
| earnings_med | Low sample sizes | 2.5% (137 with n<30) | Documented; supplementary use only |
| grad_rate_150pct | Cohort year mismatch with Plan | cohort_year=2015, not 2014 | Filtered correctly in cleaning |

---

## Questions for Future Investigation

Open questions raised by this analysis:

- [ ] Why does the Education Data Portal serve IPEDS rates as 0-1 proportions when the source documentation describes them as percentages? Is this a Portal normalization or an IPEDS change?
- [ ] How do Scorecard earnings compare when restricting to institutions with count_working >= 30 vs. including all?
- [ ] What is the actual institution at unitid 246035 with SFR=110, and is this a data quality issue or a legitimate extreme case?

---

## Recommendations for Similar Analyses

If someone were to do a similar analysis:

1. **Always profile raw data before writing cleaning logic.** IPEDS rates arrive as 0-1 proportions through the Portal mirror, not 0-100 as some documentation suggests. Two scripts needed revision because of this assumption.
2. **Plan for 5-6 tasks per session maximum** when using per-script QA interleaving with an 8-source pipeline. The 34-task pipeline required 9 sessions.
3. **Use FSA grants (grant_type==4) for Pell data**, not IPEDS financial aid tables. FSA has better coverage and more recent years. Always inspect available grant_type values before filtering.
4. **Be cautious with IPEDS graduation rate interpretation.** The FTFT cohort creates endogeneity: institutions with selective admissions have higher graduation rates partly because they're measuring a pre-selected population. This is a feature of the data, not a bug — but it's central to interpreting the analysis.
5. **Expect sparse cells when cross-tabulating selectivity × demographics.** Highly selective institutions almost never have high Pell/URM shares — this sparsity is itself a key finding about how selectivity and demographics cluster.
6. **Scorecard earnings are supplementary only** for cross-selectivity comparisons due to Title IV coverage bias (30-50% at elite institutions vs 80%+ at less selective).
7. **Within-band analysis is more robust than cross-band regression** for this type of research question, because the nonlinear selectivity-graduation relationship (28.7pp gap between HS and S, compressed among lower bands) is poorly captured by linear models.

---

## System Update Action Plan

Improvements to framework, skills, or agents based on this analysis:

| # | Category | Action | Priority | Rationale |
|---|----------|--------|----------|-----------|
| 1 | Skill | Update `education-data-source-ipeds` to document that Portal serves rates as 0-1 proportions | HIGH | Two scripts failed due to this undocumented convention |
| 2 | Skill | Add plotnine gotchas to `plotnine` skill: `guide=False` unsupported, use `guides(fill="none")` | MEDIUM | 4 of 5 viz scripts needed revision for this |
| 3 | Agent | Add wide-to-long format reminder to code-reviewer checks for visualization scripts | LOW | Correlation matrix heatmap needed explicit unpivot |
| 4 | Process | Add "inspect available coded values before filtering" to Stage 5 checklist in CLAUDE.md | MEDIUM | FSA grants fetch needed 4 revisions due to blind filtering |
| 5 | Skill | Document Scorecard's 100%-null columns at non-matching yae values in `education-data-source-scorecard` | MEDIUM | 15 of 29 columns structurally null at yae==10 |
| 6 | Process | Consider session budget estimation at Plan creation (tasks ÷ 5 ≈ sessions needed) | LOW | Pipeline scope warnings were accurate but could be quantified earlier |
