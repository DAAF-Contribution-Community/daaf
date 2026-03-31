---
parent_plan: "research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md"
title: "College Graduation Rate & Selectivity Analysis"
date: "2026-03-29"
version: ""
total_tasks: 33
total_waves: 11
---

# College Graduation Rate & Selectivity Analysis - Executable Task Sequence

> **Parent Plan:** `research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/2026-03-29_College_Graduation_Rate_Selectivity_Analysis_Plan.md`
>
> This file contains the machine-readable executable task sequence for the analysis.
> It is a companion to Plan.md, which contains the strategic specification.
>
> **Immutability:** Both Plan.md and this file are frozen after Stage 4.5 (Plan Validation).

## Task Index

| Step | Task Name | Wave | Stage | Script Path | Depends On |
|------|-----------|------|-------|-------------|------------|
| 1.1 | fetch-directory | 1 | 5 | `scripts/stage5_fetch/01_fetch-directory.py` | -- |
| 1.2 | fetch-admissions | 1 | 5 | `scripts/stage5_fetch/02_fetch-admissions.py` | -- |
| 1.3 | fetch-grad-rates | 1 | 5 | `scripts/stage5_fetch/03_fetch-grad-rates.py` | -- |
| 1.4 | fetch-fsa-grants | 1 | 5 | `scripts/stage5_fetch/04_fetch-fsa-grants.py` | -- |
| 1.5 | fetch-enrollment-race | 1 | 5 | `scripts/stage5_fetch/05_fetch-enrollment-race.py` | -- |
| 2.1 | fetch-sfr | 2 | 5 | `scripts/stage5_fetch/06_fetch-sfr.py` | -- |
| 2.2 | fetch-retention | 2 | 5 | `scripts/stage5_fetch/07_fetch-retention.py` | -- |
| 2.3 | fetch-finance | 2 | 5 | `scripts/stage5_fetch/08_fetch-finance.py` | -- |
| 3.1 | clean-directory | 3 | 6 | `scripts/stage6_clean/01_clean-directory.py` | 1.1 |
| 3.2 | clean-admissions | 3 | 6 | `scripts/stage6_clean/02_clean-admissions.py` | 1.2 |
| 3.3 | clean-grad-rates | 3 | 6 | `scripts/stage6_clean/03_clean-grad-rates.py` | 1.3 |
| 3.4 | clean-fsa-grants | 3 | 6 | `scripts/stage6_clean/04_clean-fsa-grants.py` | 1.4 |
| 3.5 | clean-enrollment-race | 3 | 6 | `scripts/stage6_clean/05_clean-enrollment-race.py` | 1.5 |
| 4.1 | clean-sfr | 4 | 6 | `scripts/stage6_clean/06_clean-sfr.py` | 2.1 |
| 4.2 | clean-retention | 4 | 6 | `scripts/stage6_clean/07_clean-retention.py` | 2.2 |
| 4.3 | clean-finance | 4 | 6 | `scripts/stage6_clean/08_clean-finance.py` | 2.3 |
| 5.1 | join-core | 5 | 7 | `scripts/stage7_transform/01_join-core.py` | 3.1, 3.2, 3.3 |
| 5.2 | join-demographics | 5 | 7 | `scripts/stage7_transform/02_join-demographics.py` | 5.1, 3.4, 3.5 |
| 6.1 | join-resources | 6 | 7 | `scripts/stage7_transform/03_join-resources.py` | 5.2, 4.1, 4.2, 4.3 |
| 6.2 | create-bands | 6 | 7 | `scripts/stage7_transform/04_create-bands.py` | 6.1 |
| 7.1 | descriptive-by-selectivity | 7 | 8.1 | `scripts/stage8_analysis/01_descriptive-by-selectivity.py` | 6.2 |
| 7.2 | crosstab-selectivity-pell | 7 | 8.1 | `scripts/stage8_analysis/02_crosstab-selectivity-pell.py` | 6.2 |
| 7.3 | crosstab-selectivity-urm | 7 | 8.1 | `scripts/stage8_analysis/03_crosstab-selectivity-urm.py` | 6.2 |
| 8.1 | correlation-matrix | 8 | 8.1 | `scripts/stage8_analysis/04_correlation-matrix.py` | 6.2 |
| 8.2 | outperformers | 8 | 8.1 | `scripts/stage8_analysis/05_outperformers.py` | 6.2 |
| 9.1 | regression-models | 9 | 8.1 | `scripts/stage8_analysis/06_regression-models.py` | 6.2 |
| 9.2 | sector-comparison | 9 | 8.1 | `scripts/stage8_analysis/07_sector-comparison.py` | 6.2 |
| 10.1 | viz-scatter-grad-admit | 10 | 8.2 | `scripts/stage8_analysis/08_viz-scatter-grad-admit.py` | 6.2 |
| 10.2 | viz-boxplot-selectivity | 10 | 8.2 | `scripts/stage8_analysis/09_viz-boxplot-selectivity.py` | 6.2 |
| 10.3 | viz-heatmap-selectivity-pell | 10 | 8.2 | `scripts/stage8_analysis/10_viz-heatmap-selectivity-pell.py` | 7.2 |
| 10.4 | viz-correlation-heatmap | 10 | 8.2 | `scripts/stage8_analysis/11_viz-correlation-heatmap.py` | 8.1 |
| 10.5 | viz-sector-comparison | 10 | 8.2 | `scripts/stage8_analysis/12_viz-sector-comparison.py` | 9.2 |
| 11.1 | viz-residual-scatter | 11 | 8.2 | `scripts/stage8_analysis/13_viz-residual-scatter.py` | 8.2 |

---

## Executable Task Sequence

### Wave 1: Data Acquisition -- Batch 1 (Parallel, 5 tasks)

### Task 1.1: fetch-directory [Stage 5]

<task name="fetch-directory" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_directory.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `ipeds/colleges_ipeds_directory`
       - File type: single (all years in one file)
    3. Apply local filters with Polars:
       - Years: pl.col("year").is_in([2020, 2021])
       - No additional filters at fetch (apply population filters during cleaning)
    4. Save to data/raw/2026-03-29_ipeds_directory.parquet
    5. Run CP1 validation
  </action>
  <verify>
    - Row count: 6,000-15,000 expected (2 years x 3,000-7,500 institutions including non-4-year)
    - Required columns present: unitid, year, inst_name, fips, inst_control, institution_level, degree_granting, open_public
    - Years present: [2020, 2021]
    - Null rate < 10% for unitid, year
    - Mirror used logged in script output
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_directory.parquet</done>
</task>

### Task 1.2: fetch-admissions [Stage 5]

<task name="fetch-admissions" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_admissions.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `ipeds/colleges_ipeds_admissions-enrollment`
       - File type: single (all years in one file)
    3. Apply local filters with Polars:
       - Years: pl.col("year").is_in([2020, 2021])
    4. Save to data/raw/2026-03-29_ipeds_admissions.parquet
    5. Run CP1 validation
    6. IMPORTANT: Log all column names found -- the dataset has only 9 columns (unitid, year, fips, sex, number_applied, number_admitted, number_enrolled_ft, number_enrolled_pt, number_enrolled_total)
  </action>
  <verify>
    - Row count: 15,000-30,000 expected (multiple sex categories per institution-year)
    - Required columns present: unitid, year, sex, number_applied, number_admitted
    - Years present: [2020, 2021]
    - Null rate < 10% for unitid, year
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_admissions.parquet</done>
</task>

### Task 1.3: fetch-grad-rates [Stage 5]

<task name="fetch-grad-rates" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_grad_rates.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `ipeds/colleges_ipeds_grad-rates`
       - File type: single (all years in one file)
    3. Apply local filters with Polars:
       - Years: pl.col("year").is_in([2020, 2021])
    4. Save to data/raw/2026-03-29_ipeds_grad_rates.parquet
    5. Run CP1 validation
    6. CRITICAL: Log all unique values of `cohort` column with value_counts() to document subcohort codes. This resolves the LOW-confidence item from Stage 3 about undocumented subcohort codes. Expected codes: 2=bachelor's-seeking at 4-yr, 8=Pell recipients, 12=total degree-seeking. Verify from data.
    7. Log all unique values of `race` and `sex` columns
  </action>
  <verify>
    - Row count: 50,000-500,000 expected (many subcohort x race x sex combinations per institution)
    - Required columns present: unitid, year, cohort, race, sex, completion_rate_150pct
    - Years present: [2020, 2021]
    - Subcohort codes logged and documented
    - Null rate < 10% for unitid, year
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_grad_rates.parquet; subcohort codes documented in execution log</done>
</task>

### Task 1.4: fetch-fsa-grants [Stage 5]

<task name="fetch-fsa-grants" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_fsa_grants.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `fsa/colleges_fsa_grants`
       - File type: single (all years in one file)
    3. Apply local filters with Polars:
       - Years: pl.col("year").is_in([2020, 2021])
       - grant_type: pl.col("grant_type") == 1 (Pell Grant only)
    4. Save to data/raw/2026-03-29_fsa_grants.parquet
    5. Run CP1 validation
    6. Log summary: number of unique unitids, total grant recipients, range of grant_recipients_unitid values
  </action>
  <verify>
    - Row count: 8,000-15,000 expected (2 years x 4,000-7,500 Pell-participating institutions)
    - Required columns present: unitid, year, grant_type, grant_recipients_unitid, value_grants_disbursed_unitid
    - Years present: [2020, 2021]
    - grant_type contains only value 1 (Pell)
    - Null rate < 10% for unitid, year, grant_recipients_unitid
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_fsa_grants.parquet</done>
</task>

### Task 1.5: fetch-enrollment-race [Stage 5]

<task name="fetch-enrollment-race" type="auto" wave="1">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_enrollment_race.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (yearly file):
       - Dataset Path: `ipeds/colleges_ipeds_fall-enrollment-race_2020`
       - File type: yearly (one file per year)
    3. Apply local filters with Polars AFTER loading:
       - sex == 99 (total)
       - ftpt == 99 (total FT+PT)
       - level_of_study == 1 (undergraduate)
       - degree_seeking == 99 (total)
       - class_level == 99 (total)
    4. Save filtered data to data/raw/2026-03-29_ipeds_enrollment_race.parquet
    5. Run CP1 validation
    6. Log unique race codes found and enrollment_fall distribution
    7. NOTE: This is a LARGE file (~3.5M rows before filtering). Use lazy scan if CSV mirror, or eager read if parquet. Filtering reduces to ~50,000 rows.
  </action>
  <verify>
    - Row count: 30,000-70,000 expected (after filters: ~4,000-7,000 institutions x up to 12 race categories)
    - Required columns present: unitid, year, race, enrollment_fall
    - Year present: [2020]
    - Race codes include: 1, 2, 3, 4, 5, 6, 7, 8, 9, 99
    - Null rate < 5% for unitid
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_enrollment_race.parquet</done>
</task>

---

### Wave 2: Data Acquisition -- Batch 2 (Parallel, 3 tasks)

### Task 2.1: fetch-sfr [Stage 5]

<task name="fetch-sfr" type="auto" wave="2">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_sfr.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `ipeds/colleges_ipeds_student-faculty-ratio`
       - File type: single (all years)
    3. Apply local filters with Polars:
       - Years: pl.col("year") == 2020
    4. Save to data/raw/2026-03-29_ipeds_sfr.parquet
    5. Run CP1 validation
    6. Log columns found (expected: unitid, year, fips, student_faculty_ratio)
  </action>
  <verify>
    - Row count: 3,000-7,000 expected
    - Required columns present: unitid, year, student_faculty_ratio
    - Year present: [2020]
    - Null rate < 10% for student_faculty_ratio
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_sfr.parquet</done>
</task>

### Task 2.2: fetch-retention [Stage 5]

<task name="fetch-retention" type="auto" wave="2">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_retention.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `ipeds/colleges_ipeds_fall-retention`
       - File type: single (all years)
    3. Apply local filters with Polars:
       - Years: pl.col("year") == 2020
    4. Save to data/raw/2026-03-29_ipeds_retention.parquet
    5. Run CP1 validation
    6. Log dtypes of all columns -- retention_rate may be String type per Stage 3 findings
    7. Log unique values of ftpt column
  </action>
  <verify>
    - Row count: 5,000-15,000 expected (multiple ftpt rows per institution)
    - Required columns present: unitid, year, ftpt, retention_rate
    - Year present: [2020]
    - ftpt values include 1 (FT) and 2 (PT)
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_retention.parquet</done>
</task>

### Task 2.3: fetch-finance [Stage 5]

<task name="fetch-finance" type="auto" wave="2">
  <depends_on>none</depends_on>
  <skill>education-data-query</skill>
  <agent>research-executor</agent>
  <files>
    <output>data/raw/2026-03-29_ipeds_finance.parquet</output>
  </files>
  <action>
    1. Load education-data-query skill
    2. Use mirror fetch pattern (single-file):
       - Dataset Path: `ipeds/colleges_ipeds_finance`
       - File type: single (all years)
    3. Apply local filters with Polars:
       - Years: pl.col("year") == 2017 (latest expected in Portal per Stage 3 findings)
       - NOTE: If 2017 is not available, try years 2016, 2018, 2019, 2020 in order. Log the actual year used.
    4. Save to data/raw/2026-03-29_ipeds_finance.parquet
    5. Run CP1 validation
    6. CRITICAL: Log ALL column names found. We need to identify instructional expenditure columns and est_fte. Column names for instructional expenditure are not yet confirmed from codebook -- document what columns exist.
    7. Log the max year available in the dataset to verify finance data cutoff.
  </action>
  <verify>
    - Row count: 3,000-10,000 expected
    - Required columns present: unitid, year (plus instructional expenditure and FTE columns -- names TBD from data inspection)
    - Year present: at least one year in [2015, 2016, 2017, 2018, 2019, 2020]
    - Log actual max year available
  </verify>
  <done>CP1 PASSED, file saved to data/raw/2026-03-29_ipeds_finance.parquet; actual year and column names documented in execution log</done>
</task>

---

### Wave 3: Data Cleaning -- Batch 1 (Parallel, 5 tasks)

### Task 3.1: clean-directory [Stage 6]

<task name="clean-directory" type="auto" wave="3">
  <depends_on>fetch-directory</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_directory.parquet</input>
    <output>data/processed/2026-03-29_directory_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_directory.parquet
    3. Filter to target population:
       - pl.col("degree_granting") == 1
       - pl.col("institution_level") == 4  (4-year institutions; NOTE: code is 4, NOT 3)
       - pl.col("year") == 2020  (use single target year for cross-sectional analysis)
    4. Replace coded missing values in numeric columns:
       - For columns [open_public, hbcu, tribal_college]: replace -1, -2, -3 with null
    5. Verify unitid uniqueness after filtering (should be 1 row per institution)
    6. Select columns: unitid, inst_name, fips, inst_control, open_public, hbcu, tribal_college
    7. Generate citation text for IPEDS Directory
    8. Save to data/processed/2026-03-29_directory_clean.parquet
    9. Run CP2 validation
  </action>
  <verify>
    - Row count: 2,500-4,500 (4-year degree-granting institutions in 2020)
    - No coded values (-1, -2, -3) remain in inst_control
    - unitid is unique (1 row per institution)
    - inst_control values in [1, 2, 3] only
    - Data loss < 90% from raw
    - Citation text complete
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_directory_clean.parquet</done>
</task>

### Task 3.2: clean-admissions [Stage 6]

<task name="clean-admissions" type="auto" wave="3">
  <depends_on>fetch-admissions</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_admissions.parquet</input>
    <output>data/processed/2026-03-29_admissions_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_admissions.parquet
    3. Filter to institution-level totals:
       - pl.col("sex") == 99  (CRITICAL: without this filter, each institution appears ~3x)
       - pl.col("year") == 2020
    4. Replace coded missing values:
       - For columns [number_applied, number_admitted, number_enrolled_ft, number_enrolled_pt, number_enrolled_total]: replace -1, -2, -3 with null
    5. Compute admission rate:
       - admit_rate = (number_admitted / number_applied) * 100
       - Only compute where number_applied > 0 AND number_applied is not null AND number_admitted is not null
       - Set admit_rate to null where number_applied == 0 or is null
    6. Validate admit_rate range: should be 0-100 for all non-null values
    7. Select columns: unitid, number_applied, number_admitted, number_enrolled_total, admit_rate
    8. Generate citation text for IPEDS Admissions
    9. Save to data/processed/2026-03-29_admissions_clean.parquet
    10. Run CP2 validation
  </action>
  <verify>
    - Row count: 2,000-3,500 (institutions reporting admissions in 2020, sex==99)
    - No coded values (-1, -2, -3) remain in number_applied, number_admitted
    - admit_rate values between 0 and 100 (where non-null)
    - unitid is unique
    - Data loss < 90% from raw
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_admissions_clean.parquet</done>
</task>

### Task 3.3: clean-grad-rates [Stage 6]

<task name="clean-grad-rates" type="auto" wave="3">
  <depends_on>fetch-grad-rates</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_grad_rates.parquet</input>
    <output>data/processed/2026-03-29_grad_rates_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_grad_rates.parquet
    3. Examine cohort codes from data (resolve LOW-confidence item):
       - Print value_counts() for cohort column
       - Identify the code for "bachelor's-seeking at 4-year institutions" (expected: cohort == 2)
       - If cohort == 2 is not present, try cohort values and use the one that gives ~3,000 institutions matching 4-yr population
    4. Filter to target subcohort:
       - pl.col("cohort") == 2 (bachelor's-seeking at 4-yr; VERIFY from step 3)
       - pl.col("race") == 99  (total, all races)
       - pl.col("sex") == 99  (total, all sexes)
       - pl.col("year") == 2020
    5. Replace coded missing values:
       - For completion_rate_150pct: replace -1, -2, -3 with null
    6. Validate completion_rate_150pct range: should be 0-100 for all non-null values
    7. Select columns: unitid, completion_rate_150pct, cohort_count (if available)
    8. Generate citation text for IPEDS Graduation Rates
    9. Save to data/processed/2026-03-29_grad_rates_clean.parquet
    10. Run CP2 validation
  </action>
  <verify>
    - Row count: 2,000-4,000 (4-yr institutions with grad rates, single subcohort/race/sex)
    - No coded values (-1, -2, -3) remain in completion_rate_150pct
    - completion_rate_150pct between 0 and 100 (where non-null)
    - unitid is unique
    - Cohort code used is documented in execution log
    - Data loss < 90% from raw
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_grad_rates_clean.parquet; cohort code confirmed and documented</done>
</task>

### Task 3.4: clean-fsa-grants [Stage 6]

<task name="clean-fsa-grants" type="auto" wave="3">
  <depends_on>fetch-fsa-grants</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_fsa_grants.parquet</input>
    <output>data/processed/2026-03-29_fsa_pell_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_fsa_grants.parquet
    3. Verify grant_type == 1 (Pell) -- should already be filtered from fetch
    4. Filter to target year:
       - pl.col("year") == 2020
    5. Replace coded missing values:
       - For grant_recipients_unitid: replace -1, -2, -3 with null
       - For value_grants_disbursed_unitid: replace -1, -2, -3 with null
    6. Filter: grant_recipients_unitid > 0 (exclude institutions with zero or null Pell recipients)
    7. Select columns: unitid, grant_recipients_unitid (rename to pell_recipients), value_grants_disbursed_unitid (rename to pell_disbursed)
    8. Generate citation text for FSA Grants
    9. Save to data/processed/2026-03-29_fsa_pell_clean.parquet
    10. Run CP2 validation
  </action>
  <verify>
    - Row count: 4,000-7,000 (Pell-participating institutions in 2020)
    - No coded values (-1, -2, -3) remain in pell_recipients
    - pell_recipients > 0 for all rows
    - unitid is unique
    - Data loss < 90% from raw
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_fsa_pell_clean.parquet</done>
</task>

### Task 3.5: clean-enrollment-race [Stage 6]

<task name="clean-enrollment-race" type="auto" wave="3">
  <depends_on>fetch-enrollment-race</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_enrollment_race.parquet</input>
    <output>data/processed/2026-03-29_urm_share_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_enrollment_race.parquet
    3. Data should already be filtered to sex==99, ftpt==99, level_of_study==1, degree_seeking==99, class_level==99 from fetch
    4. Replace coded missing values:
       - For enrollment_fall: replace -1, -2, -3 with null
    5. Compute URM share per institution:
       a. URM numerator = SUM(enrollment_fall) WHERE race IN (2, 3, 5, 6)
          - 2=Black, 3=Hispanic, 5=AIAN, 6=NHPI
       b. Domestic known-race denominator = SUM(enrollment_fall) WHERE race IN (1, 2, 3, 4, 5, 6, 7)
          - Excludes 8=Nonresident alien, 9=Unknown, 99=Total
       c. urm_share = URM numerator / domestic known-race denominator
       d. Also compute total_ug_enrollment = enrollment_fall WHERE race == 99 (for Pell share denominator)
    6. Group by unitid, producing one row per institution with:
       - urm_share (float, 0-1)
       - total_ug_enrollment (integer)
    7. Validate urm_share range: 0-1 for all non-null values
    8. Generate citation text for IPEDS Fall Enrollment Race
    9. Save to data/processed/2026-03-29_urm_share_clean.parquet
    10. Run CP2 validation
  </action>
  <verify>
    - Row count: 3,000-7,000 (one row per institution)
    - urm_share between 0 and 1 (where non-null)
    - total_ug_enrollment > 0 for all rows
    - unitid is unique
    - No coded values remain
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_urm_share_clean.parquet</done>
</task>

---

### Wave 4: Data Cleaning -- Batch 2 (Parallel, 3 tasks)

### Task 4.1: clean-sfr [Stage 6]

<task name="clean-sfr" type="auto" wave="4">
  <depends_on>fetch-sfr</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_sfr.parquet</input>
    <output>data/processed/2026-03-29_sfr_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_sfr.parquet
    3. Replace coded missing values:
       - For student_faculty_ratio: replace -1, -2, -3 with null
    4. Cast student_faculty_ratio to Float64 if not already numeric
    5. Filter: student_faculty_ratio > 0 AND student_faculty_ratio is not null
    6. Validate student_faculty_ratio range: reasonable values 1-100 (flag any > 100 as WARN)
    7. Select columns: unitid, student_faculty_ratio
    8. Save to data/processed/2026-03-29_sfr_clean.parquet
    9. Run CP2 validation
  </action>
  <verify>
    - Row count: 3,000-6,000
    - No coded values (-1, -2, -3) remain in student_faculty_ratio
    - student_faculty_ratio > 0 for all rows
    - unitid is unique
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_sfr_clean.parquet</done>
</task>

### Task 4.2: clean-retention [Stage 6]

<task name="clean-retention" type="auto" wave="4">
  <depends_on>fetch-retention</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_retention.parquet</input>
    <output>data/processed/2026-03-29_retention_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_retention.parquet
    3. Filter to full-time retention:
       - pl.col("ftpt") == 1  (full-time students)
    4. Handle String type issue (per Stage 3 findings):
       - Check dtype of retention_rate
       - If String: cast to Float64 using pl.col("retention_rate").cast(pl.Float64, strict=False)
       - This will convert coded string values like "-1" to -1.0
    5. Replace coded missing values (now numeric):
       - For retention_rate: replace -1, -2, -3 with null
    6. Validate retention_rate range: should be 0-100 for all non-null values
    7. Select columns: unitid, retention_rate
    8. Save to data/processed/2026-03-29_retention_clean.parquet
    9. Run CP2 validation
  </action>
  <verify>
    - Row count: 2,500-5,000 (institutions with FT retention data)
    - No coded values (-1, -2, -3) remain in retention_rate
    - retention_rate between 0 and 100 (where non-null)
    - unitid is unique
    - Data loss < 90% from raw
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_retention_clean.parquet</done>
</task>

### Task 4.3: clean-finance [Stage 6]

<task name="clean-finance" type="auto" wave="4">
  <depends_on>fetch-finance</depends_on>
  <skill>education-data-context</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/raw/2026-03-29_ipeds_finance.parquet</input>
    <output>data/processed/2026-03-29_finance_clean.parquet</output>
  </files>
  <action>
    1. Load education-data-context skill
    2. Load raw data from data/raw/2026-03-29_ipeds_finance.parquet
    3. Identify instructional expenditure column:
       - Print all column names
       - Look for columns containing "instruction" or "expenditure" in name
       - Use the identified column (likely varies by GASB/FASB reporting standard)
       - Document the exact column name used
    4. Identify est_fte column:
       - Look for columns containing "fte" or "est_fte"
    5. Replace coded missing values:
       - For instructional expenditure column: replace -1, -2, -3 with null
       - For est_fte: replace -1, -2, -3 with null
    6. Compute instructional expenditure per FTE:
       - instr_expend_per_fte = instructional_expenditure / est_fte
       - Only compute where both values are non-null and est_fte > 0
    7. Validate instr_expend_per_fte range: reasonable values $1,000-$200,000 (flag outliers)
    8. Select columns: unitid, instr_expend_per_fte
    9. Save to data/processed/2026-03-29_finance_clean.parquet
    10. Run CP2 validation
    11. NOTE: Finance data year may differ from other datasets (expected 2017). This is acceptable per Plan -- instructional spending is slow-moving.
  </action>
  <verify>
    - Row count: 3,000-8,000
    - No coded values (-1, -2, -3) remain in output columns
    - instr_expend_per_fte > 0 for all non-null rows
    - unitid is unique
    - Actual year and column names documented in execution log
  </verify>
  <done>CP2 PASSED, file saved to data/processed/2026-03-29_finance_clean.parquet; finance column names and year documented</done>
</task>

---

### Wave 5: Core Join (2 tasks, sequential dependency within wave)

### Task 5.1: join-core [Stage 7]

<task name="join-core" type="auto" wave="5">
  <depends_on>clean-directory, clean-admissions, clean-grad-rates</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/2026-03-29_directory_clean.parquet</input>
    <input>data/processed/2026-03-29_admissions_clean.parquet</input>
    <input>data/processed/2026-03-29_grad_rates_clean.parquet</input>
    <output>data/processed/2026-03-29_core.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load all three input files
    3. Capture pre-state: row counts and unitid overlap for each pair
    4. Join 1: Directory LEFT JOIN Admissions ON unitid
       - LEFT join because not all 4-yr institutions report admissions (open admissions may not)
       - Expected: admit_rate will be null for institutions not reporting admissions
       - Cardinality: 1:1 (both have unique unitid)
    5. Join 2: Result LEFT JOIN Grad Rates ON unitid
       - LEFT join to retain all directory institutions
       - Expected: completion_rate_150pct will be null for institutions without grad rate data
       - Cardinality: 1:1
    6. Validate:
       - Result row count should equal Directory row count (LEFT join preserves left side)
       - No fan-out (result rows <= directory rows)
       - Check nulls introduced by each join
    7. Save to data/processed/2026-03-29_core.parquet
    8. Run CP3 validation
  </action>
  <verify>
    - Join key overlap: Admissions matches > 60% of Directory; Grad Rates matches > 70% of Directory
    - No fan-out (result rows == directory rows for LEFT join)
    - Result has columns: unitid, inst_name, fips, inst_control, open_public, hbcu, tribal_college, number_applied, number_admitted, number_enrolled_total, admit_rate, completion_rate_150pct
    - No unexpected nulls in unitid or inst_control
  </verify>
  <done>CP3 PASSED (join validation), file saved to data/processed/2026-03-29_core.parquet</done>
</task>

### Task 5.2: join-demographics [Stage 7]

<task name="join-demographics" type="auto" wave="5">
  <depends_on>join-core, clean-fsa-grants, clean-enrollment-race</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/2026-03-29_core.parquet</input>
    <input>data/processed/2026-03-29_fsa_pell_clean.parquet</input>
    <input>data/processed/2026-03-29_urm_share_clean.parquet</input>
    <output>data/processed/2026-03-29_core_demographics.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load core dataset and both demographic files
    3. Capture pre-state: row counts and unitid overlap
    4. Join 1: Core LEFT JOIN FSA Pell ON unitid
       - LEFT join to retain all core institutions
       - Cardinality: 1:1
    5. Join 2: Result LEFT JOIN URM Share ON unitid
       - LEFT join to retain all institutions
       - Cardinality: 1:1
    6. Compute Pell share:
       - pell_share = pell_recipients / total_ug_enrollment
       - Only where both values are non-null and total_ug_enrollment > 0
       - Validate pell_share range: 0-1 (values > 1 indicate data quality issue -- flag as WARN)
    7. Validate:
       - Result row count should equal Core row count
       - pell_share and urm_share ranges are valid
    8. Save to data/processed/2026-03-29_core_demographics.parquet
    9. Run CP3 validation
  </action>
  <verify>
    - Join key overlap: Pell matches > 80% of Core; URM matches > 80% of Core
    - No fan-out
    - pell_share between 0 and 1 (where non-null)
    - urm_share between 0 and 1 (where non-null)
    - Result has new columns: pell_recipients, pell_share, urm_share, total_ug_enrollment
  </verify>
  <done>CP3 PASSED (join validation), file saved to data/processed/2026-03-29_core_demographics.parquet</done>
</task>

---

### Wave 6: Resource Join + Band Creation (2 tasks, sequential)

### Task 6.1: join-resources [Stage 7]

<task name="join-resources" type="auto" wave="6">
  <depends_on>join-demographics, clean-sfr, clean-retention, clean-finance</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <cardinality>1:1</cardinality>
  <files>
    <input>data/processed/2026-03-29_core_demographics.parquet</input>
    <input>data/processed/2026-03-29_sfr_clean.parquet</input>
    <input>data/processed/2026-03-29_retention_clean.parquet</input>
    <input>data/processed/2026-03-29_finance_clean.parquet</input>
    <output>data/processed/2026-03-29_merged.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load core demographics dataset and all three resource files
    3. Capture pre-state: row counts and unitid overlap for each resource file
    4. Join 1: Core Demographics LEFT JOIN SFR ON unitid (1:1)
    5. Join 2: Result LEFT JOIN Retention ON unitid (1:1)
    6. Join 3: Result LEFT JOIN Finance ON unitid (1:1)
       - NOTE: Finance data is from ~2017 while other data is from 2020. This cross-year join is intentional per Plan (instructional spending is slow-moving).
    7. Validate:
       - Result row count should equal Core Demographics row count
       - No fan-out from any join
       - Document match rates for each resource join
    8. Save to data/processed/2026-03-29_merged.parquet
    9. Run CP3 validation
  </action>
  <verify>
    - Result row count equals Core Demographics row count
    - No fan-out (result rows <= input rows)
    - SFR match rate > 70%; Retention match rate > 70%; Finance match rate > 60%
    - New columns present: student_faculty_ratio, retention_rate, instr_expend_per_fte
    - No unexpected total null columns
  </verify>
  <done>CP3 PASSED (join validation), file saved to data/processed/2026-03-29_merged.parquet</done>
</task>

### Task 6.2: create-bands [Stage 7]

<task name="create-bands" type="auto" wave="6">
  <depends_on>join-resources</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_merged.parquet</input>
    <output>data/processed/2026-03-29_analysis.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load merged dataset from data/processed/2026-03-29_merged.parquet
    3. Create selectivity_band column:
       - "Highly Selective": admit_rate < 25
       - "Selective": 25 <= admit_rate < 50
       - "Moderately Selective": 50 <= admit_rate < 75
       - "Open/Less Selective": admit_rate >= 75 OR open_public == 1
       - For institutions with admit_rate IS NULL AND open_public == 1: assign "Open/Less Selective"
       - For institutions with admit_rate IS NULL AND open_public != 1: assign null (exclude from band-based analyses)
    4. Create pell_quintile column:
       - Compute quintiles of pell_share using pl.col("pell_share").qcut(5, labels=["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"])
       - Only for rows where pell_share is not null
    5. Create urm_quintile column:
       - Compute quintiles of urm_share using pl.col("urm_share").qcut(5, labels=["Q1 (Lowest)", "Q2", "Q3", "Q4", "Q5 (Highest)"])
       - Only for rows where urm_share is not null
    6. Log distribution of selectivity_band (value_counts)
    7. Log distribution of pell_quintile and urm_quintile
    8. Filter to analysis population: require at least completion_rate_150pct AND selectivity_band to be non-null
    9. Save to data/processed/2026-03-29_analysis.parquet
    10. Run CP3 validation
  </action>
  <verify>
    - selectivity_band has 4 distinct non-null values
    - selectivity_band distribution: each band has N >= 100
    - pell_quintile has 5 distinct non-null values (where pell_share is available)
    - urm_quintile has 5 distinct non-null values (where urm_share is available)
    - Row count: 1,500-2,500 (institutions with grad rate + selectivity band)
    - admit_rate between 0 and 100 (where non-null)
    - completion_rate_150pct between 0 and 100 for all rows
    - Output has all expected columns: unitid, inst_name, inst_control, admit_rate, completion_rate_150pct, pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte, selectivity_band, pell_quintile, urm_quintile, open_public
  </verify>
  <done>CP3 PASSED, file saved to data/processed/2026-03-29_analysis.parquet; band distribution documented</done>
</task>

---

### Wave 7: Primary Descriptive Analyses (Parallel, 3 tasks)

### Task 7.1: descriptive-by-selectivity [Stage 8.1]

<task name="descriptive-by-selectivity" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_descriptive_by_selectivity.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset from data/processed/2026-03-29_analysis.parquet
    3. Group by selectivity_band
    4. For each band, compute:
       - N (count of institutions)
       - Mean, Median, SD of: completion_rate_150pct, admit_rate, pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte
       - Sector composition: count and percentage of inst_control == 1 (public), == 2 (private NP), == 3 (for-profit)
    5. Order bands: Highly Selective, Selective, Moderately Selective, Open/Less Selective
    6. Print formatted summary table to stdout
    7. Save to output/analysis/2026-03-29_descriptive_by_selectivity.parquet
    8. Run CP4 validation (output exists, non-zero, reasonable values)
  </action>
  <verify>
    - Output file exists and is non-zero
    - 4 rows (one per selectivity band)
    - All summary statistics are substantively reasonable (e.g., mean grad rate 0-100, mean pell_share 0-1)
    - N per band >= 100
  </verify>
  <done>CP4 PASSED (descriptive analysis), file saved to output/analysis/</done>
</task>

### Task 7.2: crosstab-selectivity-pell [Stage 8.1]

<task name="crosstab-selectivity-pell" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_crosstab_selectivity_pell.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Filter to rows where both selectivity_band and pell_quintile are non-null
    4. Group by [selectivity_band, pell_quintile]
    5. Compute: MEAN(completion_rate_150pct), MEDIAN(completion_rate_150pct), COUNT(*) as N
    6. Pivot to create 4x5 matrix (bands as rows, Pell quintiles as columns)
    7. Print formatted cross-tabulation to stdout
    8. Also compute: within each selectivity band, the difference in mean grad rate between Q1 (lowest Pell) and Q5 (highest Pell) -- this is the "Pell gap" within selectivity level
    9. Save to output/analysis/2026-03-29_crosstab_selectivity_pell.parquet
    10. Run CP4 validation
  </action>
  <verify>
    - Output file exists and is non-zero
    - Cross-tab has 20 cells (4 bands x 5 quintiles) -- some may have low N
    - Mean grad rates are between 0 and 100
    - N per cell >= 10 (WARN if any cell < 10)
  </verify>
  <done>CP4 PASSED (cross-tabulation), file saved to output/analysis/</done>
</task>

### Task 7.3: crosstab-selectivity-urm [Stage 8.1]

<task name="crosstab-selectivity-urm" type="auto" wave="7">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_crosstab_selectivity_urm.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Filter to rows where both selectivity_band and urm_quintile are non-null
    4. Group by [selectivity_band, urm_quintile]
    5. Compute: MEAN(completion_rate_150pct), MEDIAN(completion_rate_150pct), COUNT(*) as N
    6. Pivot to create 4x5 matrix (bands as rows, URM quintiles as columns)
    7. Print formatted cross-tabulation to stdout
    8. Also compute: within each selectivity band, the difference in mean grad rate between Q1 (lowest URM) and Q5 (highest URM)
    9. Save to output/analysis/2026-03-29_crosstab_selectivity_urm.parquet
    10. Run CP4 validation
  </action>
  <verify>
    - Output file exists and is non-zero
    - Cross-tab has 20 cells (4 bands x 5 quintiles)
    - Mean grad rates between 0 and 100
    - N per cell >= 10 (WARN if any cell < 10)
  </verify>
  <done>CP4 PASSED (cross-tabulation), file saved to output/analysis/</done>
</task>

---

### Wave 8: Secondary Analyses (Parallel, 2 tasks)

### Task 8.1: correlation-matrix [Stage 8.1]

<task name="correlation-matrix" type="auto" wave="8">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_correlation_matrix.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Select continuous variables for correlation: admit_rate, completion_rate_150pct, pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte
    4. Drop rows with any null in the selected variables (pairwise complete cases)
    5. Compute Pearson correlation matrix using polars or numpy
    6. Also compute Spearman rank correlations for robustness (some variables may be non-normal)
    7. Print both correlation matrices to stdout with variable names
    8. Log N used for correlation computation
    9. Highlight the key correlation: admit_rate vs completion_rate_150pct (tests H1)
    10. Save Pearson matrix to output/analysis/2026-03-29_correlation_matrix.parquet
    11. Run CP4 validation
  </action>
  <verify>
    - Output file exists and is non-zero
    - Correlation values between -1 and 1
    - Matrix is symmetric
    - Diagonal values are 1.0
    - N documented in execution log
  </verify>
  <done>CP4 PASSED (correlation analysis), file saved to output/analysis/</done>
</task>

### Task 8.2: outperformers [Stage 8.1]

<task name="outperformers" type="auto" wave="8">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, statsmodels</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_outperformers.parquet</output>
    <output>output/analysis/2026-03-29_selectivity_model.parquet</output>
  </files>
  <action>
    1. Load data-scientist and statsmodels skills
    2. Load analysis dataset
    3. Filter to rows where both admit_rate and completion_rate_150pct are non-null
    4. Fit simple OLS: completion_rate_150pct ~ admit_rate
       - Use statsmodels OLS with HC1 robust standard errors
       - This is the "selectivity-only" model
    5. Compute predicted values and residuals for each institution
    6. Compute residual SD
    7. Define outperformers: institutions with residual > 1 SD above zero (beating their selectivity-predicted grad rate by more than 1 SD)
    8. Define underperformers: institutions with residual < -1 SD below zero
    9. Profile outperformers:
       - Mean and median of: pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte
       - Sector distribution: % public, % private NP, % for-profit
       - HBCU count and percentage
    10. Profile underperformers similarly for comparison
    11. Save full model results (predicted, residual, outperformer flag) to output/analysis/2026-03-29_selectivity_model.parquet
    12. Save outperformer profile summary to output/analysis/2026-03-29_outperformers.parquet
    13. Print model summary (R-squared, coefficients) and outperformer profile to stdout
    14. Run CP4 validation
  </action>
  <verify>
    - Output files exist and are non-zero
    - Model R-squared between 0 and 1
    - Number of outperformers is substantively reasonable (expected 15-20% of institutions if using 1 SD threshold)
    - Outperformer profile includes sector distribution
    - Sample sizes documented
  </verify>
  <done>CP4 PASSED (outperformer analysis), files saved to output/analysis/</done>
</task>

---

### Wave 9: Supplementary Analyses (Parallel, 2 tasks)

### Task 9.1: regression-models [Stage 8.1]

<task name="regression-models" type="auto" wave="9">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, statsmodels</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_regression_results.parquet</output>
  </files>
  <action>
    1. Load data-scientist and statsmodels skills
    2. Load analysis dataset
    3. Create complete-case dataset: drop rows with ANY null in: admit_rate, completion_rate_150pct, pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte
    4. Log complete-case N and % dropped
    5. Estimate three hierarchical OLS models with HC1 robust standard errors:
       Model 1: completion_rate_150pct ~ admit_rate
       Model 2: completion_rate_150pct ~ admit_rate + pell_share + urm_share
       Model 3: completion_rate_150pct ~ admit_rate + pell_share + urm_share + student_faculty_ratio + retention_rate + instr_expend_per_fte
    6. Also estimate Model 3b with sector dummies:
       Model 3b: Model 3 + C(inst_control)  (inst_control as categorical: 1=public ref, 2=private NP, 3=for-profit)
    7. For each model, extract and report:
       - R-squared and Adjusted R-squared
       - Coefficient, SE, t-stat, p-value for each variable
       - N observations
    8. Compute R-squared change: Model 1 -> Model 2 (student composition contribution) and Model 2 -> Model 3 (resource contribution)
    9. Print formatted regression table to stdout
    10. Save coefficients and model statistics to output/analysis/2026-03-29_regression_results.parquet
    11. Run CP4 validation
  </action>
  <verify>
    - Output file exists and is non-zero
    - R-squared values between 0 and 1
    - R-squared increases from Model 1 to Model 3 (adding predictors should not decrease R-squared)
    - Sample sizes documented for each model
    - Coefficients are finite (no convergence issues)
    - H2 assessment: compare admit_rate coefficient between Model 1 and Model 3
  </verify>
  <done>CP4 PASSED (regression analysis), file saved to output/analysis/</done>
</task>

### Task 9.2: sector-comparison [Stage 8.1]

<task name="sector-comparison" type="auto" wave="9">
  <depends_on>create-bands</depends_on>
  <skill>data-scientist, polars</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/analysis/2026-03-29_sector_comparison.parquet</output>
  </files>
  <action>
    1. Load data-scientist and polars skills
    2. Load analysis dataset
    3. Map inst_control to sector labels:
       - 1 = "Public"
       - 2 = "Private Nonprofit"
       - 3 = "Private For-Profit"
    4. Group by sector (inst_control label)
    5. For each sector, compute:
       - N (count of institutions)
       - Mean, Median, SD of: completion_rate_150pct, admit_rate, pell_share, urm_share, student_faculty_ratio, retention_rate, instr_expend_per_fte
       - Distribution of selectivity_band within sector (percentage in each band)
    6. Also compute: within each sector, the Pearson correlation between admit_rate and completion_rate_150pct
    7. Print formatted sector comparison table to stdout
    8. Save to output/analysis/2026-03-29_sector_comparison.parquet
    9. Run CP4 validation
  </action>
  <verify>
    - Output file exists and is non-zero
    - 3 rows (one per sector) or fewer if for-profit 4-yr institutions are rare
    - All summary statistics substantively reasonable
    - N per sector documented
  </verify>
  <done>CP4 PASSED (sector comparison), file saved to output/analysis/</done>
</task>

---

### Wave 10: Visualizations -- Batch 1 (Parallel, 5 tasks)

### Task 10.1: viz-scatter-grad-admit [Stage 8.2]

<task name="viz-scatter-grad-admit" type="auto" wave="10">
  <depends_on>create-bands</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/figures/2026-03-29_grad_rate_vs_admission_rate.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load analysis dataset
    3. Create scatter plot:
       - X axis: admit_rate (Admission Rate %)
       - Y axis: completion_rate_150pct (Graduation Rate %)
       - Color: selectivity_band (4 categories) using colorblind-safe palette
       - Add OLS trend line (geom_smooth method="lm")
       - Add Pearson r annotation
       - Title: "Graduation Rate vs. Admission Rate at U.S. Four-Year Institutions"
       - Subtitle: "Each point is one institution. Lower admission rate = more selective."
       - Caption: "Source: IPEDS 2020. Graduation rate = 150% time, first-time full-time students."
    4. Apply clean theme (theme_minimal or similar), 300 DPI
    5. Export to output/figures/2026-03-29_grad_rate_vs_admission_rate.png at 10x7 inches, 300 DPI
    6. Verify file exists and size > 0
  </action>
  <verify>
    - File exists at output/figures/2026-03-29_grad_rate_vs_admission_rate.png
    - File size > 50 KB
  </verify>
  <done>CP4 PASSED (visualization), figure saved</done>
</task>

### Task 10.2: viz-boxplot-selectivity [Stage 8.2]

<task name="viz-boxplot-selectivity" type="auto" wave="10">
  <depends_on>create-bands</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load analysis dataset
    3. Create box plot:
       - X axis: selectivity_band (ordered: Highly Selective, Selective, Moderately Selective, Open/Less Selective)
       - Y axis: completion_rate_150pct (Graduation Rate %)
       - Fill: selectivity_band using colorblind-safe palette
       - Add individual points with jitter (alpha=0.2) for data density
       - Add mean markers (diamond or similar)
       - Title: "Graduation Rate Distribution by Selectivity Band"
       - Caption: "Source: IPEDS 2020. Boxes show IQR; diamonds show means."
    4. Apply clean theme, 300 DPI
    5. Export to output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png at 10x7 inches, 300 DPI
    6. Verify file exists and size > 0
  </action>
  <verify>
    - File exists at output/figures/2026-03-29_boxplot_grad_rate_by_selectivity.png
    - File size > 50 KB
  </verify>
  <done>CP4 PASSED (visualization), figure saved</done>
</task>

### Task 10.3: viz-heatmap-selectivity-pell [Stage 8.2]

<task name="viz-heatmap-selectivity-pell" type="auto" wave="10">
  <depends_on>crosstab-selectivity-pell</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-03-29_crosstab_selectivity_pell.parquet</input>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/figures/2026-03-29_heatmap_selectivity_pell.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load cross-tab results (or recompute from analysis dataset if easier)
    3. Create heatmap:
       - X axis: pell_quintile (Q1 Lowest to Q5 Highest)
       - Y axis: selectivity_band (ordered)
       - Fill: mean completion_rate_150pct (use sequential blue or viridis palette)
       - Add text labels in each cell showing mean grad rate and N
       - Title: "Mean Graduation Rate by Selectivity and Pell Grant Share"
       - Subtitle: "Darker cells = higher graduation rates. Cell labels show mean grad rate (N)."
       - Caption: "Source: IPEDS 2020 + FSA 2020."
    4. Use geom_tile + geom_text for heatmap construction
    5. Apply clean theme, 300 DPI
    6. Export to output/figures/2026-03-29_heatmap_selectivity_pell.png at 10x8 inches, 300 DPI
    7. Verify file exists and size > 0
  </action>
  <verify>
    - File exists at output/figures/2026-03-29_heatmap_selectivity_pell.png
    - File size > 50 KB
  </verify>
  <done>CP4 PASSED (visualization), figure saved</done>
</task>

### Task 10.4: viz-correlation-heatmap [Stage 8.2]

<task name="viz-correlation-heatmap" type="auto" wave="10">
  <depends_on>correlation-matrix</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-03-29_correlation_matrix.parquet</input>
    <output>output/figures/2026-03-29_correlation_heatmap.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load correlation matrix from output/analysis/2026-03-29_correlation_matrix.parquet
    3. Create correlation heatmap:
       - Axes: variable names (formatted for readability: "Admission Rate", "Graduation Rate", "Pell Share", "URM Share", "Student-Faculty Ratio", "Retention Rate", "Instr. Spending/FTE")
       - Fill: Pearson correlation coefficient (diverging red-white-blue palette, centered at 0)
       - Add text labels showing correlation values in each cell
       - Title: "Correlation Matrix: Institutional Characteristics"
       - Caption: "Source: IPEDS 2020 + FSA 2020. Pearson correlations."
    4. Use geom_tile + geom_text
    5. Apply clean theme, 300 DPI
    6. Export to output/figures/2026-03-29_correlation_heatmap.png at 9x8 inches, 300 DPI
    7. Verify file exists and size > 0
  </action>
  <verify>
    - File exists at output/figures/2026-03-29_correlation_heatmap.png
    - File size > 50 KB
  </verify>
  <done>CP4 PASSED (visualization), figure saved</done>
</task>

### Task 10.5: viz-sector-comparison [Stage 8.2]

<task name="viz-sector-comparison" type="auto" wave="10">
  <depends_on>sector-comparison</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-03-29_sector_comparison.parquet</input>
    <input>data/processed/2026-03-29_analysis.parquet</input>
    <output>output/figures/2026-03-29_sector_comparison.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load sector comparison results or analysis dataset
    3. Create grouped bar chart or faceted plot:
       - Show mean graduation rate, mean Pell share, mean admit rate by sector
       - Use facet_wrap or side-by-side grouped bars
       - Alternatively: create a scatter plot faceted by sector showing grad rate vs admit rate with trend lines per sector
       - Title: "Selectivity-Graduation Relationship by Institutional Sector"
       - Caption: "Source: IPEDS 2020."
    4. Apply clean theme with colorblind-safe palette, 300 DPI
    5. Export to output/figures/2026-03-29_sector_comparison.png at 12x7 inches, 300 DPI
    6. Verify file exists and size > 0
  </action>
  <verify>
    - File exists at output/figures/2026-03-29_sector_comparison.png
    - File size > 50 KB
  </verify>
  <done>CP4 PASSED (visualization), figure saved</done>
</task>

---

### Wave 11: Final Visualization (1 task)

### Task 11.1: viz-residual-scatter [Stage 8.2]

<task name="viz-residual-scatter" type="auto" wave="11">
  <depends_on>outperformers</depends_on>
  <skill>plotnine</skill>
  <agent>research-executor</agent>
  <files>
    <input>output/analysis/2026-03-29_selectivity_model.parquet</input>
    <output>output/figures/2026-03-29_actual_vs_predicted.png</output>
  </files>
  <action>
    1. Load plotnine skill
    2. Load selectivity model results (includes predicted, residual, outperformer flag)
    3. Create scatter plot:
       - X axis: predicted graduation rate (from selectivity-only model)
       - Y axis: actual graduation rate (completion_rate_150pct)
       - Add 45-degree reference line (y=x, where actual equals predicted)
       - Color: outperformer status (3 categories: outperformer, typical, underperformer)
       - Use colorblind-safe palette (e.g., green for outperformers, gray for typical, red for underperformers)
       - Optionally label top outperformers by inst_name
       - Title: "Actual vs. Predicted Graduation Rate (Selectivity Model)"
       - Subtitle: "Points above the line graduate more students than selectivity alone predicts."
       - Caption: "Source: IPEDS 2020. Model: OLS, grad rate ~ admission rate."
    4. Apply clean theme, 300 DPI
    5. Export to output/figures/2026-03-29_actual_vs_predicted.png at 10x8 inches, 300 DPI
    6. Verify file exists and size > 0
  </action>
  <verify>
    - File exists at output/figures/2026-03-29_actual_vs_predicted.png
    - File size > 50 KB
  </verify>
  <done>CP4 PASSED (visualization), figure saved</done>
</task>
