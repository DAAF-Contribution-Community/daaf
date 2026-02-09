# Datasets Reference

Known dataset file paths for the Education Data Portal mirrors. This is a human-readable reference for planning fetch scripts. For mirrors with discovery support (see `mirrors.yaml`), the discovery endpoint is the authoritative source for what's currently available.

---

## How to Use This Reference

1. Find your dataset in the tables below
2. Note the **Type** (single-file or yearly) and available **Years**
3. Copy the `path` value into your fetch call
4. Use the appropriate fetch pattern from `fetch-patterns.md`
5. If unsure whether a file exists, use the mirror's discovery endpoint (see `mirrors.yaml`)
6. For codebook/metadata files, use the `codebook` column with `get_codebook_url()` from `fetch-patterns.md`

### Unified Path Model

All mirrors use the same canonical `path` from this reference. Each mirror appends its own format extension:

| Mirror | URL Template | Result |
|--------|-------------|--------|
| HuggingFace | `{root_url}/{path}.parquet` | `https://huggingface.co/.../ccd/schools_ccd_directory.parquet` |
| Urban CSV | `{root_url}/{path}.csv` | `https://educationdata.urban.org/csv/ccd/schools_ccd_directory.csv` |

### Building a Fetch Call

```python
# Example: SAIPE district poverty
DATASET_PATH = "saipe/geography_saipe"
df = fetch_from_mirrors(DATASET_PATH, years=[2020, 2021, 2022])
```

No per-mirror path dicts needed — one path works for all mirrors.

---

## School Districts

### CCD (Common Core of Data)

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Directory | Single | All years | `ccd/school-districts_lea_directory` | `ccd/codebook_districts_ccd_directory` |
| Enrollment | Yearly | 1986-2023 | `ccd/schools_ccd_lea_enrollment_{year}` | `ccd/codebook_districts_ccd_enrollment` |
| Finance | Single | All years | `ccd/districts_ccd_finance` | — |

### EDFacts

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Assessments | Yearly | 2009-2020 | `edfacts/districts_edfacts_assessments_{year}` | `edfacts/codebook_districts_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `edfacts/districts_edfacts_grad_rates_{year}` | `edfacts/codebook_districts_edfacts_grad_rates` |

### SAIPE

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Poverty Estimates | Single | All years | `saipe/geography_saipe` | `saipe/codebook_districts_saipe` |

---

## Schools

### CCD

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Directory | Single | All years | `ccd/schools_ccd_directory` | `ccd/codebook_schools_ccd_directory` |
| Enrollment | Yearly | varies | `ccd/schools_ccd_enrollment_{year}` | `ccd/codebook_schools_ccd_enrollment` |

### CRDC

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Discipline | Yearly | 2011-2021 | `crdc/schools_crdc_discipline_k12_{year}` | `crdc/codebook_schools_crdc_discipline` |
| AP/IB Enrollment | Single | 2011-2021 | `crdc/schools_crdc_apib_enroll` | `crdc/codebook_schools_crdc_ap_ib_enrollment` |
| Enrollment | Yearly | 2011-2021 | `crdc/schools_crdc_enrollment_k12_{year}` | `crdc/codebook_schools_crdc_enrollment` |
| Chronic Absenteeism | Yearly | 2013-2022 | `crdc/schools_crdc_chronic_absenteeism_{year}` | `crdc/codebook_schools_crdc_chronic_absenteeism` |
| Harassment/Bullying | Yearly | 2011-2021 | `crdc/schools_crdc_harass_bully_students_{year}` | `crdc/codebook_schools_crdc_harassment_or_bullying` |
| Restraint/Seclusion | Yearly | 2011-2021 | `crdc/schools_crdc_restraint_seclusion_students_{year}` | `crdc/codebook_schools_crdc_restraint_and_seclusion` |

#### Additional CRDC Datasets (Mirror Available)

Codebook `.xls` files exist for these topics. Data files are available in the mirror but paths are not yet documented. Use mirror discovery (see `fetch-patterns.md`) to confirm data file paths.

| Topic | codebook |
|-------|----------|
| Algebra I | `crdc/codebook_schools_crdc_algebra1` |
| AP Exams | `crdc/codebook_schools_crdc_ap_exams` |
| COVID Indicators | `crdc/codebook_schools_crdc_covid_indicators` |
| Credit Recovery | `crdc/codebook_schools_crdc_credit_recovery` |
| Directory | `crdc/codebook_schools_crdc_directory` |
| Discipline Instances | `crdc/codebook_schools_crdc_discipline_instances` |
| Dual Enrollment | `crdc/codebook_schools_crdc_dual_enrollment` |
| Internet Access | `crdc/codebook_schools_crdc_internet_access` |
| Math and Science | `crdc/codebook_schools_crdc_math_and_science` |
| Offenses | `crdc/codebook_schools_crdc_offenses` |
| Offerings | `crdc/codebook_schools_crdc_offerings` |
| Retention | `crdc/codebook_schools_crdc_retention` |
| SAT/ACT Participation | `crdc/codebook_schools_crdc_sat_act_participation` |
| School Finance | `crdc/codebook_schools_crdc_school_finance` |
| Suspensions Days | `crdc/codebook_schools_crdc_suspensions_days` |
| Teachers/Staff | `crdc/codebook_schools_crdc_teachers_staff` |

### MEPS

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Poverty | Single | varies | `meps/schools_meps` | `meps/codebook_schools_meps` |

### EDFacts

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Assessments | Yearly | 2009-2018, 2020 | `edfacts/schools_edfacts_assessments_{year}` | `edfacts/codebook_schools_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `edfacts/schools_edfacts_grad_rates_{year}` | `edfacts/codebook_schools_edfacts_grad_rates` |

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
| Directory | Single | All years | `ipeds/colleges_ipeds_directory` | `ipeds/codebook_colleges_ipeds_directory` |
| Admissions | Single | varies | `ipeds/colleges_ipeds_admissions-enrollment` | `ipeds/codebook_colleges_ipeds_admissions-enrollment` |
| Enrollment FTE | Single | varies | `ipeds/colleges_ipeds_enrollment-fte` | `ipeds/codebook_colleges_ipeds_enrollment-fte` |
| Graduation Rates | Single | varies | `ipeds/colleges_ipeds_grad-rates` | `ipeds/codebook_colleges_ipeds_grad-rates` |
| Finance | Single | varies | `ipeds/colleges_ipeds_finance` | `ipeds/codebook_colleges_ipeds_finance` |

#### Additional IPEDS Datasets (Mirror Available)

32 IPEDS datasets exist in the mirror (5 documented above). Codebook `.xls` files exist for all. Use mirror discovery to confirm data file paths.

| Topic | codebook |
|-------|----------|
| Academic Libraries | `ipeds/codebook_colleges_ipeds_academic-libraries` |
| Academic Year Room/Board/Other | `ipeds/codebook_colleges_ipeds_ay_room_board_other` |
| Academic Year Tuition | `ipeds/codebook_colleges_ipeds_ay_tuition_fees` |
| Academic Year Tuition (Prof Program) | `ipeds/codebook_colleges_ipeds_ay_tuition_firstprof` |
| Admissions Requirements | `ipeds/codebook_colleges_ipeds_admissions-requirements` |
| Completers | `ipeds/codebook_colleges_ipeds_completers` |
| Completions (CIP 2-digit) | `ipeds/codebook_colleges_ipeds_completions-2digcip` |
| Completions (CIP 6-digit) | `ipeds/codebook_colleges_ipeds_completions-6digcip` |
| Enrollment Headcount | `ipeds/codebook_colleges_ipeds_enrollment-headcount` |
| Fall Enrollment (Age) | `ipeds/codebook_colleges_ipeds_fall-enrollment-age` |
| Fall Enrollment (Race) | `ipeds/codebook_colleges_ipeds_fall-enrollment-race` |
| Fall Enrollment (Residence) | `ipeds/codebook_colleges_ipeds_fall-enrollment-residence` |
| Fall Retention | `ipeds/codebook_colleges_ipeds_fall-retention` |
| Grad Rates (200%) | `ipeds/codebook_colleges_ipeds_grad-rates-200pct` |
| Grad Rates (Pell) | `ipeds/codebook_colleges_ipeds_grad-rates-pell` |
| Institutional Characteristics | `ipeds/codebook_colleges_ipeds_institutional-characteristics` |
| Outcome Measures | `ipeds/codebook_colleges_ipeds_outcome-measures` |
| Program Year Room/Board/Other | `ipeds/codebook_colleges_ipeds_py_room_board_other` |
| Program Year Tuition (CIP) | `ipeds/codebook_colleges_ipeds_py_tuition_cip` |
| Salaries (Instructional Staff) | `ipeds/codebook_colleges_ipeds_instructional_staff_salaries` |
| Salaries (Non-Instructional Staff) | `ipeds/codebook_colleges_ipeds_noninstructional_staff_salaries` |
| SFA (All Undergraduates) | `ipeds/codebook_colleges_ipeds_sfa_all_undergrads` |
| SFA (By Living Arrangement) | `ipeds/codebook_colleges_ipeds_sfa_by_living_arrangement` |
| SFA (By Tuition Type) | `ipeds/codebook_colleges_ipeds_sfa_by_tuition_type` |
| SFA (FTFT) | `ipeds/codebook_colleges_ipeds_sfa_FTFT` |
| SFA (Grants and Net Price) | `ipeds/codebook_colleges_ipeds_sfa_grants_and_net_price` |
| Student-Faculty Ratio | `ipeds/codebook_colleges_ipeds_student-faculty-ratio` |

### Scorecard

| Topic | Type | Years | path | codebook |
|-------|------|-------|------|----------|
| Earnings | Single | varies | `scorecard/colleges_scorecard_earnings` | `scorecard/codebook_colleges_scorecard_earnings` |

#### Additional Scorecard Datasets (Mirror Available)

6 Scorecard datasets exist in the mirror (1 documented above). Codebook `.xls` files exist for all.

| Topic | codebook |
|-------|----------|
| Default | `scorecard/codebook_colleges_scorecard_default` |
| Institutional Characteristics | `scorecard/codebook_colleges_scorecard_institutional-characteristics` |
| Repayment | `scorecard/codebook_colleges_scorecard_repayment` |
| Student Characteristics (Aid Applicants) | `scorecard/codebook_colleges_scorecard_student-characteristics_aid-applicants` |
| Student Characteristics (Home Neighborhood) | `scorecard/codebook_colleges_scorecard_student-characteristics_home-neighborhood` |

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
- **Path values** are canonical — they work with all mirrors. Each mirror's `url_template` (in `mirrors.yaml`) appends its own format extension (`.parquet`, `.csv`).
- **Codebook files** are `.xls` files available on all mirrors. The `codebook` column contains the canonical path (without extension); use `get_codebook_url()` from `fetch-patterns.md` to construct download URLs. Naming pattern: `codebook_{entity}_{source}_{topic}`. Codebooks are for human reference — not parsed programmatically.
- **Additional datasets** sections list mirror datasets with codebooks that are not yet fully documented with data file paths. Use mirror discovery to confirm data file paths before fetching.
- **Discovery:** Use each mirror's discovery mechanism (defined in `mirrors.yaml`) to verify file availability before fetching.
- **Cross-reference** source-specific skills for variable names, coded values, and caveats.
- **Adding a new mirror:** Only update `mirrors.yaml`. The paths in this file work for all mirrors.
