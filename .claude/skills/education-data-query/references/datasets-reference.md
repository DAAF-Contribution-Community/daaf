# Datasets Reference

Known dataset file paths for the Education Data Portal mirrors. This is a human-readable reference for planning fetch scripts. For mirrors with discovery support (see `mirrors.yaml`), the discovery endpoint is the authoritative source for what's currently available.

> **Discovery vs. fetch.** Complete question→dataset routing (which mirror file answers a research question, across all 85 dataset families — grain, year coverage, key variables, join keys) now lives in the `education-data-explorer` skill's `*-datasets.md` references. This file is the fetch-time path catalog: use it once discovery has named the datasets, to look up the exact canonical `path` and year list to fetch.

> **Vintage note.** Year ranges below reflect mirror vintage **2026q3 / Portal v0.26.1** (collected 2026-08-06). Historical values and coverage differ from the frozen v0.24.0 predecessor; see `vintage-drift.md` for what changed (revised datasets/years, cosmetic vs. substantive) before reconciling a result across vintages.

---

## How to Use This Reference

1. Find your dataset in the tables below
2. Note the **Type** (single-file or yearly) and available **Years**
3. Copy the `path` value into your fetch call
4. Use the appropriate fetch pattern from `fetch-patterns.md`
5. If unsure whether a file exists, use the mirror's discovery endpoint (see `mirrors.yaml`)
6. For codebook/metadata files, use the `codebook` column with `get_codebook_url()` from `fetch-patterns.md`

### Unified Path Model

All mirrors use the same extensionless canonical `path` from this reference. Data discovery removes exactly one terminal `.csv` or `.parquet`; codebook discovery removes exactly one terminal `.xls`. URL templates append the appropriate extension. Do not pass an extension-bearing discovery result to a fetch template, because that would construct a doubled extension. See `mirrors.yaml` for definitions and `fetch-patterns.md` for canonicalization.

### Building a Fetch Call

```python
# Example: SAIPE district poverty
DATASET_PATH = "saipe/districts_saipe"
df = fetch_from_mirrors(DATASET_PATH, years=[2020, 2021, 2022])
```

```r
# Example: SAIPE district poverty
# See fetch-patterns.md for the full R mirror resolution pattern.
# NOTE: this abbreviated snippet uses a plain arrow::read_parquet() for brevity, but
# saipe/districts_saipe is a Polars-written file with string_view columns — a plain
# read fails under R arrow with "cannot handle Array of type <utf8_view>". In real
# fetch scripts use the VIEW-SAFE read pattern from fetch-patterns.md (eager_parquet
# branch), not this one-liner.
dataset_path <- "saipe/districts_saipe"
config <- yaml::read_yaml(mirrors_yaml_path)
mirror <- config$mirrors[[1]]
url <- paste0(mirror$root_url, "/", dataset_path, ".", mirror$format)
df <- arrow::read_parquet(url) |>   # illustrative only — see view-safe note above
  filter(year %in% c(2020, 2021, 2022))
```

No per-mirror path dicts needed — one path works for all mirrors.

---

## School Districts

### CCD (Common Core of Data)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Directory | Single | varies | `ccd/school-districts_lea_directory` | `ccd/codebook_districts_ccd_directory` |
| Enrollment | Yearly | 1986-2024 | `ccd/schools_ccd_lea_enrollment_{year}` | `ccd/codebook_districts_ccd_enrollment` |
| Finance | Single | varies | `ccd/districts_ccd_finance` | `ccd/codebook_districts_ccd_finance` |

### EDFacts

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Assessments | Yearly | 2009-2018, 2020 | `edfacts/districts_edfacts_assessments_{year}` | `edfacts/codebook_districts_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `edfacts/districts_edfacts_grad_rates_{year}` | `edfacts/codebook_districts_edfacts_graduation` |

> **Note:** 2019 assessment data is NOT available (at any level) due to COVID testing waivers.

### SAIPE

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Poverty Estimates | Single | 1995-2024 | `saipe/districts_saipe` | `saipe/codebook_districts_saipe` |

---

## Schools

### CCD

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Directory | Single | varies | `ccd/schools_ccd_directory` | `ccd/codebook_schools_ccd_directory` |
| Enrollment | Yearly | 1986-2024 | `ccd/schools_ccd_enrollment_{year}` | `ccd/codebook_schools_ccd_enrollment` |

### CRDC

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Discipline | Yearly | 2011-2021 | `crdc/schools_crdc_discipline_k12_{year}` | `crdc/codebook_schools_crdc_discipline` |
| AP/IB Enrollment | Single | 2011-2021 | `crdc/schools_crdc_apib_enroll` | `crdc/codebook_schools_crdc_ap-ib-enrollment` |
| Enrollment | Yearly | 2011-2021 | `crdc/schools_crdc_enrollment_k12_{year}` | `crdc/codebook_schools_crdc_enrollment` |
| Chronic Absenteeism | Yearly | 2013-2022 | `crdc/schools_crdc_chronic_absenteeism_{year}` | `crdc/codebook_schools_crdc_chronic-absenteeism` |
| Harassment/Bullying | Yearly | 2011-2021 | `crdc/schools_crdc_harass_bully_students_{year}` | `crdc/codebook_schools_crdc_harrassment-bullying-students` |
| Restraint/Seclusion | Yearly | 2011-2021 | `crdc/schools_crdc_restraint_seclusion_students_{year}` | `crdc/codebook_schools_crdc_restraint-seclusion-students` |

#### Additional CRDC Datasets — Yearly

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Algebra | Yearly | 2011, 2013, 2015, 2017, 2020, 2021 | `crdc/schools_crdc_algebra_{year}` | `crdc/codebook_schools_crdc_algebra-1` |
| AP Exams | Yearly | 2011, 2013, 2015, 2017 | `crdc/schools_crdc_ap_exams_{year}` | `crdc/codebook_schools_crdc_ap-exams` |
| Retention | Yearly | 2011, 2013, 2015, 2017, 2020 | `crdc/schools_crdc_retention_{year}` | `crdc/codebook_schools_crdc_retention` |
| SAT/ACT Participation | Yearly | 2011, 2013, 2015, 2017, 2020, 2021 | `crdc/schools_crdc_sat_and_act_participation_{year}` | `crdc/codebook_schools_crdc_sat-act-participation` |

#### Additional CRDC Datasets — Single-File

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| COVID Indicators | Single | 2020-2021 | `crdc/schools_crdc_covid_indicators` | `crdc/codebook_schools_crdc_covid_indicators` |
| Credit Recovery | Single | varies | `crdc/schools_crdc_credit_recovery` | `crdc/codebook_schools_crdc_credit-recovery` |
| Directory/Characteristics | Single | varies | `crdc/schools_crdc_school_characteristics` | `crdc/codebook_schools_crdc_directory` |
| Discipline Instances | Single | varies | `crdc/schools_crdc_disciplineinstances` | `crdc/codebook_schools_crdc_discipline_instances` |
| Dual Enrollment | Single | varies | `crdc/schools_crdc_dual_enrollment` | `crdc/codebook_schools_crdc_dual_enrollment` |
| Harassment/Bullying Allegations | Single | varies | `crdc/schools_crdc_harass_bully_allegations` | `crdc/codebook_schools_crdc_harrassment-bullying-allegations` |
| Internet Access | Single | 2020-2021 | `crdc/schools_crdc_internet_access` | `crdc/codebook_schools_crdc_internet_access` |
| Math and Science | Single | varies | `crdc/schools_crdc_mathandscience` | `crdc/codebook_schools_crdc_math-and-science` |
| Offenses | Single | varies | `crdc/schools_crdc_offenses` | `crdc/codebook_schools_crdc_offenses` |
| Offerings | Single | varies | `crdc/schools_crdc_offerings` | `crdc/codebook_schools_crdc_offerings` |
| Restraint/Seclusion Instances | Single | varies | `crdc/schools_crdc_restraint_seclusion_instances` | `crdc/codebook_schools_crdc_restraint-seclusion-instances` |
| School Finance | Single | varies | `crdc/schools_crdc_finance` | `crdc/codebook_schools_crdc_finance` |
| Suspensions (Days) | Single | varies | `crdc/schools_crdc_suspensions` | `crdc/codebook_schools_crdc_suspensions_days` |
| Teachers/Staff | Single | varies | `crdc/schools_crdc_teacher` | `crdc/codebook_schools_crdc_teachers_staff` |

> **CRDC naming note:** CRDC codebook filenames frequently use hyphens where data paths use underscores or concatenated names. Additionally, some codebook names differ structurally from their data counterparts (e.g., data `harass_bully_students` vs codebook `harrassment-bullying-students`; data `restraint_seclusion_students` vs codebook `restraint-seclusion-students`). Note the mirror's codebook files spell "harassment" as "harrassment" (double r) — this is intentional and must be preserved. Always use the exact paths shown above.

> **CRDC ID columns (no universal dtype contract):** CRDC `crdc_id`, `ncessch`, and `leaid` are **not** uniformly String — id typing is heterogeneous per file, even within the single 2020 vintage. Observed on the v2 mirror (2026-08-07): `schools_crdc_school_characteristics` stores all three as String; `discipline_k12_2020` has `ncessch` as Int64; `enrollment_k12_2020` has `crdc_id` as Int64; `harass_bully_students_2020` has all three as Int64. Always inspect the actual file schema before joining and cast/normalize identifiers on read — never assume a uniform id dtype across CRDC files. Where these ids are String they are zero-padded **numeric** strings (e.g. `0100002`, FIPS 01), not alphanumeric, so they must not be cast to Int without care. The CSV-fallback trap still applies to any numeric-string id: when reading from CSV, force String via `schema_overrides` — Polars infers Int64 and silently destroys leading zeros for ~19% of rows (FIPS 01-09 states: AL, AK, AZ, AR, CA, CO, CT). Parquet preserves whatever dtype the file was written with (which is why the per-file typing above varies). See `education-data-source-crdc` skill for full details.
>
> **Zero-padded IDs are not CRDC-only.** The same CSV-fallback trap applies to EDFacts and SAIPE `ncessch`/`leaid`, and force-string alone is not always enough: 2019 EDFacts source files ship *already-truncated* IDs, so the canonical recipe is force-string **plus** pad-and-assert (`ncessch`→12, `leaid`→7) after read. See the "Zero-padded ID columns" bullets in `fetch-patterns.md` § Format Handling for the bilingual pattern and per-source specifics.

### MEPS

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Poverty | Single | varies | `meps/schools_meps` | `meps/codebook_schools_meps` |

### EDFacts

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Assessments | Yearly | 2009-2018, 2020 | `edfacts/schools_edfacts_assessments_{year}` | `edfacts/codebook_schools_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `edfacts/schools_edfacts_grad_rates_{year}` | `edfacts/codebook_schools_edfacts_graduation` |

> **Note:** 2019 assessment data is NOT available due to COVID testing waivers.

### NHGIS (Census Geography)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Census 1990 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_1990` | `nhgis/codebook_schools_nhgis_census1990` |
| Census 2000 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_2000` | `nhgis/codebook_schools_nhgis_census2000` |
| Census 2010 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_2010` | `nhgis/codebook_schools_nhgis_census2010` |
| Census 2020 | Single | 1986-2023 | `nhgis/schools_nhgis_geog_2020` | `nhgis/codebook_schools_nhgis_census2020` |

---

## Colleges & Universities

### IPEDS

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Directory | Single | varies | `ipeds/colleges_ipeds_directory` | `ipeds/codebook_colleges_ipeds_directory` |
| Admissions | Single | varies | `ipeds/colleges_ipeds_admissions-enrollment` | `ipeds/codebook_colleges_ipeds_admissions-enrollment` |
| Enrollment FTE | Single | varies | `ipeds/colleges_ipeds_enrollment-fte` | `ipeds/codebook_colleges_ipeds_enrollment-fte` |
| Graduation Rates | Single | 1996-2023 | `ipeds/colleges_ipeds_grad-rates` | `ipeds/codebook_colleges_ipeds_grad-rates` |
| Finance | Single | varies | `ipeds/colleges_ipeds_finance` | `ipeds/codebook_colleges_ipeds_finance` |

> **Graduation Rates (150%) vintage note:** the `grad-rates` file content reaches **2023**. In Portal v0.26.1 it was de-duplicated and wholesale-revalued (10.69M → 6.14M rows) under the "grad-rates-150% year alignment" correction — any pre-2026q3 analysis of it must be fully re-run. See `vintage-drift.md`.

#### Additional IPEDS Datasets (Mirror Available)

32 IPEDS datasets exist in the mirror (5 documented above). Codebook `.xls` files exist for all. Discovered via Urban CSV mirror `api-downloads` endpoint.

##### Additional Single-File Datasets

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Academic Libraries | Single | 2013-2023 | `ipeds/colleges_ipeds_academic_libraries` | `ipeds/codebook_colleges_ipeds_academic-libraries` |
| Admissions Requirements | Single | 1990-2022 | `ipeds/colleges_ipeds_admissions-requirements` | `ipeds/codebook_colleges_ipeds_admissions-requirements` |
| AY Room, Board, and Other | Single | 1999-2023 | `ipeds/colleges_ipeds_ay_room_board_other` | `ipeds/codebook_colleges_ipeds_ay_room_board_other` |
| AY Tuition and Fees | Single | 1986-2023 | `ipeds/colleges_ipeds_ay_tuition_fees` | `ipeds/codebook_colleges_ipeds_ay_tuition_fees` |
| AY Tuition (First-Professional) | Single | 1986-2023 | `ipeds/colleges_ipeds_ay_tuition_firstprof` | `ipeds/codebook_colleges_ipeds_ay_tuition_firstprof` |
| Completers | Single | 2011-2021 | `ipeds/colleges_ipeds_completers` | `ipeds/codebook_colleges_ipeds_completers` |
| Enrollment Headcount | Single | 1996-2021 | `ipeds/colleges_ipeds_headcount` | `ipeds/codebook_colleges_ipeds_enrollment-headcount` |
| Fall Enrollment (Residence) | Single | 1986-2024 | `ipeds/colleges_ipeds_fall-res` | `ipeds/codebook_colleges_ipeds_fall-enrollment-residence` |
| Fall Retention | Single | 2003-2024 | `ipeds/colleges_ipeds_fall-retention` | `ipeds/codebook_colleges_ipeds_fall-retention` |
| Grad Rates (200%) | Single | 2007-2023 | `ipeds/colleges_ipeds_grad-rates-200pct` | `ipeds/codebook_colleges_ipeds_grad-rates-200pct` |
| Grad Rates (Pell) | Single | 2015-2023 | `ipeds/colleges_ipeds_grad-rates-pell` | `ipeds/codebook_colleges_ipeds_grad-rates-pell` |
| Institutional Characteristics | Single | 1980-2024 | `ipeds/colleges_ipeds_institutional-characteristics` | `ipeds/codebook_colleges_ipeds_institutional-characteristics` |
| Instructional Staff Salaries | Single | 1980-2024 | `ipeds/colleges_ipeds_salaries_is` | `ipeds/codebook_colleges_ipeds_instructional_staff_salaries` |
| Noninstructional Staff Salaries | Single | 2012-2024 | `ipeds/colleges_ipeds_salaries_nis` | `ipeds/codebook_colleges_ipeds_noninstructional_staff_salaries` |
| Outcome Measures | Single | 2015-2021 | `ipeds/colleges_ipeds_outcome-measures` | `ipeds/codebook_colleges_ipeds_outcome-measures` |
| PY Room, Board, and Other | Single | 1999-2023 | `ipeds/colleges_ipeds_py_room_board_other` | `ipeds/codebook_colleges_ipeds_py_room_board_other` |
| PY Tuition by CIP Code | Single | 1987-2023 | `ipeds/colleges_ipeds_py_tuition_cip` | `ipeds/codebook_colleges_ipeds_py_tuition_cip` |
| SFA All Undergraduates | Single | 2007-2017 | `ipeds/colleges_ipeds_sfa_all_undergrads` | `ipeds/codebook_colleges_ipeds_sfa_all_undergrads` |
| SFA by Living Arrangement | Single | 2008-2017 | `ipeds/colleges_ipeds_sfa_by_living_arrangement` | `ipeds/codebook_colleges_ipeds_sfa_by_living_arrangement` |
| SFA by Tuition Type | Single | 1999-2017 | `ipeds/colleges_ipeds_sfa_by_tuition_type` | `ipeds/codebook_colleges_ipeds_sfa_by_tuition_type` |
| SFA FTFT | Single | 1999-2017 | `ipeds/colleges_ipeds_sfa_ftft` | `ipeds/codebook_colleges_ipeds_sfa_FTFT` |
| SFA Grants and Net Price | Single | 2008-2021 | `ipeds/colleges_ipeds_sfa_grants_and_net_price` | `ipeds/codebook_colleges_ipeds_sfa_grants_and_net_price` |
| Student-Faculty Ratio | Single | 2009-2024 | `ipeds/colleges_ipeds_student-faculty-ratio` | `ipeds/codebook_colleges_ipeds_student-faculty-ratio` |

##### Additional Yearly Datasets

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Completions (CIP 2-digit) | Yearly | 1991-2023 | `ipeds/colleges_ipeds_completions-2digcip_{year}` | `ipeds/codebook_colleges_ipeds_completions-2digcip` |
| Completions (CIP 6-digit) | Yearly | 1983-2023 | `ipeds/colleges_ipeds_completions-6digcip_{year}` | `ipeds/codebook_colleges_ipeds_completions-6digcip` |
| Fall Enrollment (Age) | Yearly | 1991-2024 | `ipeds/colleges_ipeds_fall-enrollment-age_{year}` | `ipeds/codebook_colleges_ipeds_fall-enrollment-age` |
| Fall Enrollment (Race) | Yearly | 1986-2024 | `ipeds/colleges_ipeds_fall-enrollment-race_{year}` | `ipeds/codebook_colleges_ipeds_fall-enrollment-race` |

> **IPEDS naming note:** Some data file paths differ from their codebook counterparts. Notable mismatches: data `headcount` vs codebook `enrollment-headcount`; data `fall-res` vs codebook `fall-enrollment-residence`; data `salaries_is` vs codebook `instructional_staff_salaries`; data `salaries_nis` vs codebook `noninstructional_staff_salaries`; data `sfa_ftft` vs codebook `sfa_FTFT` (case difference). Always use the exact paths shown above.

> **IPEDS yearly datasets:** Fall Enrollment (Age) has non-contiguous years (1991, 1993, 1995, 1997, 1999-2024). Fall Enrollment (Race) has all years 1986-2024. Completions datasets have all years within their stated ranges.

### Scorecard

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Earnings | Single | varies | `scorecard/colleges_scorecard_earnings` | `scorecard/codebook_colleges_scorecard_earnings` |

#### Additional Scorecard Datasets (Mirror Available)

6 Scorecard datasets exist in the mirror (1 documented above). Codebook `.xls` files exist for all. Discovered via Urban CSV mirror `api-downloads` endpoint.

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Default | Single | 1996-2020 | `scorecard/colleges_scorecard_repayment_fsa` | `scorecard/codebook_colleges_scorecard_default` |
| Institutional Characteristics | Single | 1996-2020 | `scorecard/colleges_scorecard_inst_characteristics` | `scorecard/codebook_colleges_scorecard_institutional-characteristics` |
| Repayment | Single | 2007-2016 | `scorecard/colleges_scorecard_repayment_nslds` | `scorecard/codebook_colleges_scorecard_repayment` |
| Student Characteristics (Aid Applicants) | Single | 1997-2016 | `scorecard/colleges_scorecard_student_body_nslds` | `scorecard/codebook_colleges_scorecard_student-characteristics_aid-applicants` |
| Student Characteristics (Home Neighborhood) | Single | 1997-2016 | `scorecard/colleges_scorecard_student_body_treasury` | `scorecard/codebook_colleges_scorecard_student-characteristics_home-neighborhood` |

> **Scorecard naming note:** Data file paths differ significantly from codebook paths. Notable mismatches: data `repayment_fsa` vs codebook `default`; data `inst_characteristics` vs codebook `institutional-characteristics`; data `repayment_nslds` vs codebook `repayment`; data `student_body_nslds` vs codebook `student-characteristics_aid-applicants`; data `student_body_treasury` vs codebook `student-characteristics_home-neighborhood`. Always use the exact paths shown above.

### PSEO (Postsecondary Employment Outcomes)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Earnings and Flows | Yearly | 2001-2021 | `pseo/colleges_pseo_{year}` | `pseo/codebook_colleges_pseo` |

### NHGIS (Census Geography)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Census 1990 | Single | 1980-2023 | `nhgis/colleges_nhgis_geog_1990` | `nhgis/codebook_colleges_nhgis_census1990` |
| Census 2000 | Single | 1980-2023 | `nhgis/colleges_nhgis_geog_2000` | `nhgis/codebook_colleges_nhgis_census2000` |
| Census 2010 | Single | 1980-2023 | `nhgis/colleges_nhgis_geog_2010` | `nhgis/codebook_colleges_nhgis_census2010` |
| Census 2020 | Single | 1980-2023 | `nhgis/colleges_nhgis_geog_2020` | `nhgis/codebook_colleges_nhgis_census2020` |

### NCCS (Nonprofit 990 Data)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| 990 Forms | Single | 1993-2016 | `nccs/colleges_nccs_all` | `nccs/codebook_colleges_nccs_form_990` |

### FSA (Federal Student Aid)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Grants | Single | 1999-2021 | `fsa/colleges_fsa_grants` | `fsa/codebook_colleges_fsa_grants` |
| Loans | Single | 1999-2021 | `fsa/colleges_fsa_loans` | `fsa/codebook_colleges_fsa_loans` |
| Campus-Based Volume | Single | 2001-2021 | `fsa/colleges_fsa_campus_based_volume` | `fsa/codebook_colleges_fsa_campus_based_volume` |
| Financial Responsibility | Single | 2006-2016 | `fsa/colleges_fsa_composite_scores` | `fsa/codebook_colleges_fsa_financial_responsibility` |
| 90/10 Revenue | Single | 2014-2021 | `fsa/colleges_fsa_90_10_revenue_percentages` | `fsa/codebook_colleges_fsa_90-10_revenue_percentages` |

> **FSA naming note:** The Financial Responsibility dataset uses `composite_scores` in its data path but `financial_responsibility` in its codebook path. The 90/10 Revenue dataset uses underscores (`90_10`) in the data path but hyphens (`90-10`) in the codebook path. Always use the exact paths shown above.

### EADA (Equity in Athletics)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Institutional Characteristics | Single | 2002-2021 | `eada/colleges_eada_inst_characteristics` | `eada/codebook_colleges_eada_inst-characteristics` |

### NACUBO (Endowments)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Endowments | Single | 2012-2022 | `nacubo/colleges_nacubo_endow` | `nacubo/codebook_colleges_nacubo_endowments` |

### Campus Safety

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Hate Crimes | Single | 2005-2021 | `csafety/colleges_csafety_hate_crimes` | `csafety/codebook_colleges_csafety_hate_crimes` |

> **Note:** Only hate crimes data is available in the Portal mirrors. For full campus safety data (primary offenses, VAWA, arrests, fire safety), access the Department of Education Campus Safety portal directly.

---

## Notes

- **Single-file datasets** contain all years in one file. Filter locally with `pl.col("year").is_in(years)`.
- **Yearly datasets** have one file per year with `{year}` in the path. Fetch each year separately and concatenate.
- **Codebook canonical paths** are extensionless and distinct from data paths. Current discovery can observe `.xls` objects on both configured surfaces; `get_codebook_url()` appends `.xls`. Codebooks are for human reference — not parsed programmatically. Verify the specific object instead of assuming universal mirror coverage.
- **Cross-reference** source-specific skills for variable names, coded values, and caveats.
