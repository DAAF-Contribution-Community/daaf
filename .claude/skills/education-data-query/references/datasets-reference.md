# Datasets Reference

Known dataset file paths for the Education Data Portal mirrors. This is a human-readable reference for planning fetch scripts. For mirrors with discovery support (see `mirrors.yaml`), the discovery endpoint is the authoritative source for what's currently available.

---

## How to Use This Reference

1. Find your dataset in the tables below
2. Note the **Type** (single-file or yearly) and available **Years**
3. Copy the per-mirror path columns into your `dataset_paths` dict
4. Use the appropriate fetch pattern from `fetch-patterns.md`
5. If unsure whether a file exists, use the mirror's discovery endpoint (see `mirrors.yaml`)
6. For codebook/metadata files, use the `codebook` column with `get_codebook_url()` from `fetch-patterns.md`

### Mirror Path Columns

Each table has columns named after mirrors defined in `mirrors.yaml`. The column values provide the URL template parameters for that mirror's `url_template`:

| Mirror Column | URL Template | Parameters in Column |
|---------------|-------------|---------------------|
| `huggingface` | `{root_url}/{path}.parquet` | `path` value |
| `urban_csv` | `{root_url}/{source}/{filename}.csv` | `source/filename` (slash-separated) |
| `codebook` | (via `get_codebook_url()` in `fetch-patterns.md`) | Full codebook path (without extension) |

**When a new mirror is added to `mirrors.yaml`**, add a corresponding column to these tables with that mirror's URL template parameters.

### Building dataset_paths from This Reference

Given a table row, construct the `dataset_paths` dict for `fetch_from_mirrors()`:

```python
# Example: SAIPE district poverty
# Table shows: huggingface = school-districts/saipe/districts_saipe
#              urban_csv = saipe/school-districts_saipe
dataset_paths = {
    "huggingface": {"path": "school-districts/saipe/districts_saipe"},
    "urban_csv": {"source": "saipe", "filename": "school-districts_saipe"},
}
```

---

## School Districts (`school-districts/`)

### CCD (Common Core of Data)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Directory | Single | All years | `school-districts/ccd/directory/school-districts_lea_directory` | `ccd/school-districts_ccd_directory` | `school-districts/ccd/directory/codebook_districts_ccd_directory` |
| Enrollment | Yearly | 1986-2023 | `school-districts/ccd/enrollment/schools_ccd_lea_enrollment_{year}` | `ccd/school-districts_ccd_enrollment` | `school-districts/ccd/enrollment/codebook_districts_ccd_enrollment` |
| Finance | Single | All years | `school-districts/ccd/finance/districts_ccd_finance` | `ccd/school-districts_ccd_finance` | — |

### EDFacts

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Assessments | Yearly | 2009-2020 | `school-districts/edfacts/assessments/districts_edfacts_assessments_{year}` | `edfacts/school-districts_edfacts_assessments` | `school-districts/edfacts/assessments/codebook_districts_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `school-districts/edfacts/grad-rates/districts_edfacts_grad_rates_{year}` | `edfacts/school-districts_edfacts_grad_rates` | `school-districts/edfacts/grad-rates/codebook_districts_edfacts_grad_rates` |

### SAIPE

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Poverty Estimates | Single | All years | `school-districts/saipe/districts_saipe` | `saipe/school-districts_saipe` | `school-districts/saipe/codebook_districts_saipe` |

---

## Schools (`schools/`)

### CCD

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Directory | Single | All years | `schools/ccd/directory/schools_ccd_directory` | `ccd/schools_ccd_directory` | `schools/ccd/directory/codebook_schools_ccd_directory` |
| Enrollment | Yearly | varies | `schools/ccd/enrollment/schools_ccd_enrollment_{year}` | `ccd/schools_ccd_enrollment` | `schools/ccd/enrollment/codebook_schools_ccd_enrollment` |

### CRDC

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Discipline | Yearly | 2011-2021 | `schools/crdc/discipline/schools_crdc_discipline_k12_{year}` | `crdc/schools_crdc_discipline` | `schools/crdc/discipline/codebook_schools_crdc_discipline` |
| AP/IB Enrollment | Single | 2011-2021 | `schools/crdc/ap-ib-enrollment/schools_crdc_apib_enroll` | `crdc/schools_crdc_ap_ib_enrollment` | `schools/crdc/ap-ib-enrollment/codebook_schools_crdc_ap_ib_enrollment` |
| Enrollment | Yearly | 2011-2021 | `schools/crdc/enrollment/schools_crdc_enrollment_k12_{year}` | `crdc/schools_crdc_enrollment` | `schools/crdc/enrollment/codebook_schools_crdc_enrollment` |
| Chronic Absenteeism | Yearly | 2013-2022 | `schools/crdc/chronic-absenteeism/schools_crdc_chronic_absenteeism_{year}` | `crdc/schools_crdc_chronic_absenteeism` | `schools/crdc/chronic-absenteeism/codebook_schools_crdc_chronic_absenteeism` |
| Harassment/Bullying | Yearly | 2011-2021 | `schools/crdc/harassment-or-bullying/schools_crdc_harass_bully_students_{year}` | `crdc/schools_crdc_harass_bully` | `schools/crdc/harassment-or-bullying/codebook_schools_crdc_harassment_or_bullying` |
| Restraint/Seclusion | Yearly | 2011-2021 | `schools/crdc/restraint-and-seclusion/schools_crdc_restraint_seclusion_students_{year}` | `crdc/schools_crdc_restraint_seclusion` | `schools/crdc/restraint-and-seclusion/codebook_schools_crdc_restraint_and_seclusion` |

#### Additional CRDC Datasets (Mirror Available)

Codebook `.xls` files exist for these topics. Data files are available in the mirror but paths are not yet documented. Use mirror discovery (see `fetch-patterns.md`) to confirm data file paths.

| Topic | codebook |
|-------|----------|
| Algebra I | `schools/crdc/algebra1/codebook_schools_crdc_algebra1` |
| AP Exams | `schools/crdc/ap-exams/codebook_schools_crdc_ap_exams` |
| COVID Indicators | `schools/crdc/covid-indicators/codebook_schools_crdc_covid_indicators` |
| Credit Recovery | `schools/crdc/credit-recovery/codebook_schools_crdc_credit_recovery` |
| Directory | `schools/crdc/directory/codebook_schools_crdc_directory` |
| Discipline Instances | `schools/crdc/discipline-instances/codebook_schools_crdc_discipline_instances` |
| Dual Enrollment | `schools/crdc/dual-enrollment/codebook_schools_crdc_dual_enrollment` |
| Internet Access | `schools/crdc/internet-access/codebook_schools_crdc_internet_access` |
| Math and Science | `schools/crdc/math-and-science/codebook_schools_crdc_math_and_science` |
| Offenses | `schools/crdc/offenses/codebook_schools_crdc_offenses` |
| Offerings | `schools/crdc/offerings/codebook_schools_crdc_offerings` |
| Retention | `schools/crdc/retention/codebook_schools_crdc_retention` |
| SAT/ACT Participation | `schools/crdc/sat-act-participation/codebook_schools_crdc_sat_act_participation` |
| School Finance | `schools/crdc/school-finance/codebook_schools_crdc_school_finance` |
| Suspensions Days | `schools/crdc/suspensions-days/codebook_schools_crdc_suspensions_days` |
| Teachers/Staff | `schools/crdc/teachers-staff/codebook_schools_crdc_teachers_staff` |

### MEPS

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Poverty | Single | varies | `schools/meps/schools_meps` | `meps/schools_meps` | `schools/meps/codebook_schools_meps` |

### EDFacts

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Assessments | Yearly | 2009-2018, 2020 | `schools/edfacts/assessments/schools_edfacts_assessments_{year}` | `edfacts/schools_edfacts_assessments` | `schools/edfacts/assessments/codebook_schools_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `schools/edfacts/grad-rates/schools_edfacts_grad_rates_{year}` | `edfacts/schools_edfacts_grad_rates` | `schools/edfacts/grad-rates/codebook_schools_edfacts_grad_rates` |

> **Note:** 2019 assessment data is NOT available due to COVID testing waivers.

### NHGIS (Census Geography)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Census 1990 | Single | 1986-2023 | `schools/nhgis/census-1990/schools_nhgis_geog_1990` | N/A | `schools/nhgis/census-1990/codebook_schools_nhgis_census1990` |
| Census 2000 | Single | 1986-2023 | `schools/nhgis/census-2000/schools_nhgis_geog_2000` | N/A | `schools/nhgis/census-2000/codebook_schools_nhgis_census2000` |
| Census 2010 | Single | 1986-2023 | `schools/nhgis/census-2010/schools_nhgis_geog_2010` | N/A | `schools/nhgis/census-2010/codebook_schools_nhgis_census2010` |
| Census 2020 | Single | 1986-2023 | `schools/nhgis/census-2020/schools_nhgis_geog_2020` | N/A | `schools/nhgis/census-2020/codebook_schools_nhgis_census2020` |

---

## College-University (`college-university/`)

### IPEDS

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Directory | Single | All years | `college-university/ipeds/directory/colleges_ipeds_directory` | `ipeds/colleges_ipeds_directory` | `college-university/ipeds/directory/codebook_colleges_ipeds_directory` |
| Admissions | Single | varies | `college-university/ipeds/admissions-enrollment/colleges_ipeds_admissions-enrollment` | `ipeds/colleges_ipeds_admissions-enrollment` | `college-university/ipeds/admissions-enrollment/codebook_colleges_ipeds_admissions-enrollment` |
| Enrollment FTE | Single | varies | `college-university/ipeds/enrollment-full-time-equivalent/colleges_ipeds_enrollment-fte` | `ipeds/colleges_ipeds_enrollment-full-time-equivalent` | `college-university/ipeds/enrollment-full-time-equivalent/codebook_colleges_ipeds_enrollment-fte` |
| Graduation Rates | Single | varies | `college-university/ipeds/grad-rates/colleges_ipeds_grad-rates` | `ipeds/colleges_ipeds_grad-rates` | `college-university/ipeds/grad-rates/codebook_colleges_ipeds_grad-rates` |
| Finance | Single | varies | `college-university/ipeds/finance/colleges_ipeds_finance` | `ipeds/colleges_ipeds_finance` | `college-university/ipeds/finance/codebook_colleges_ipeds_finance` |

#### Additional IPEDS Datasets (Mirror Available)

32 IPEDS datasets exist in the mirror (5 documented above). Codebook `.xls` files exist for all. Use mirror discovery to confirm data file paths.

| Topic | codebook |
|-------|----------|
| Academic Libraries | `college-university/ipeds/academic-libraries/codebook_colleges_ipeds_academic-libraries` |
| Academic Year Room/Board/Other | `college-university/ipeds/academic-year-room-board-other/codebook_colleges_ipeds_ay_room_board_other` |
| Academic Year Tuition | `college-university/ipeds/academic-year-tuition/codebook_colleges_ipeds_ay_tuition_fees` |
| Academic Year Tuition (Prof Program) | `college-university/ipeds/academic-year-tuition-prof-program/codebook_colleges_ipeds_ay_tuition_firstprof` |
| Admissions Requirements | `college-university/ipeds/admissions-requirements/codebook_colleges_ipeds_admissions-requirements` |
| Completers | `college-university/ipeds/completers/codebook_colleges_ipeds_completers` |
| Completions (CIP 2-digit) | `college-university/ipeds/completions-cip-2/codebook_colleges_ipeds_completions-2digcip` |
| Completions (CIP 6-digit) | `college-university/ipeds/completions-cip-6/codebook_colleges_ipeds_completions-6digcip` |
| Enrollment Headcount | `college-university/ipeds/enrollment-headcount/codebook_colleges_ipeds_enrollment-headcount` |
| Fall Enrollment (Age) | `college-university/ipeds/fall-enrollment/codebook_colleges_ipeds_fall-enrollment-age` |
| Fall Enrollment (Race) | `college-university/ipeds/fall-enrollment/codebook_colleges_ipeds_fall-enrollment-race` |
| Fall Enrollment (Residence) | `college-university/ipeds/fall-enrollment/codebook_colleges_ipeds_fall-enrollment-residence` |
| Fall Retention | `college-university/ipeds/fall-retention/codebook_colleges_ipeds_fall-retention` |
| Grad Rates (200%) | `college-university/ipeds/grad-rates-200pct/codebook_colleges_ipeds_grad-rates-200pct` |
| Grad Rates (Pell) | `college-university/ipeds/grad-rates-pell/codebook_colleges_ipeds_grad-rates-pell` |
| Institutional Characteristics | `college-university/ipeds/institutional-characteristics/codebook_colleges_ipeds_institutional-characteristics` |
| Outcome Measures | `college-university/ipeds/outcome-measures/codebook_colleges_ipeds_outcome-measures` |
| Program Year Room/Board/Other | `college-university/ipeds/program-year-room-board-other/codebook_colleges_ipeds_py_room_board_other` |
| Program Year Tuition (CIP) | `college-university/ipeds/program-year-tuition-cip/codebook_colleges_ipeds_py_tuition_cip` |
| Salaries (Instructional Staff) | `college-university/ipeds/salaries-instructional-staff/codebook_colleges_ipeds_instructional_staff_salaries` |
| Salaries (Non-Instructional Staff) | `college-university/ipeds/salaries-noninstructional-staff/codebook_colleges_ipeds_noninstructional_staff_salaries` |
| SFA (All Undergraduates) | `college-university/ipeds/sfa-all-undergraduates/codebook_colleges_ipeds_sfa_all_undergrads` |
| SFA (By Living Arrangement) | `college-university/ipeds/sfa-by-living-arrangement/codebook_colleges_ipeds_sfa_by_living_arrangement` |
| SFA (By Tuition Type) | `college-university/ipeds/sfa-by-tuition-type/codebook_colleges_ipeds_sfa_by_tuition_type` |
| SFA (FTFT) | `college-university/ipeds/sfa-ftft/codebook_colleges_ipeds_sfa_FTFT` |
| SFA (Grants and Net Price) | `college-university/ipeds/sfa-grants-and-net-price/codebook_colleges_ipeds_sfa_grants_and_net_price` |
| Student-Faculty Ratio | `college-university/ipeds/student-faculty-ratio/codebook_colleges_ipeds_student-faculty-ratio` |

### Scorecard

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Earnings | Single | varies | `college-university/scorecard/earnings/colleges_scorecard_earnings` | `scorecard/colleges_scorecard_earnings` | `college-university/scorecard/earnings/codebook_colleges_scorecard_earnings` |

#### Additional Scorecard Datasets (Mirror Available)

6 Scorecard datasets exist in the mirror (1 documented above). Codebook `.xls` files exist for all.

| Topic | codebook |
|-------|----------|
| Default | `college-university/scorecard/default/codebook_colleges_scorecard_default` |
| Institutional Characteristics | `college-university/scorecard/institutional-characteristics/codebook_colleges_scorecard_institutional-characteristics` |
| Repayment | `college-university/scorecard/repayment/codebook_colleges_scorecard_repayment` |
| Student Characteristics (Aid Applicants) | `college-university/scorecard/student-characteristics/codebook_colleges_scorecard_student-characteristics_aid-applicants` |
| Student Characteristics (Home Neighborhood) | `college-university/scorecard/student-characteristics/codebook_colleges_scorecard_student-characteristics_home-neighborhood` |

### PSEO (Postsecondary Employment Outcomes)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Earnings and Flows | Yearly | 2001-2021 | `college-university/pseo/earnings-and-flows/colleges_pseo_{year}` | `pseo/colleges_pseo_earnings_flows` | `college-university/pseo/earnings-and-flows/codebook_colleges_pseo` |

### NHGIS (Census Geography)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Census 1990 | Single | 1980-2023 | `college-university/nhgis/census-1990/colleges_nhgis_geog_1990` | N/A | `college-university/nhgis/census-1990/codebook_colleges_nhgis_census1990` |
| Census 2000 | Single | 1980-2023 | `college-university/nhgis/census-2000/colleges_nhgis_geog_2000` | N/A | `college-university/nhgis/census-2000/codebook_colleges_nhgis_census2000` |
| Census 2010 | Single | 1980-2023 | `college-university/nhgis/census-2010/colleges_nhgis_geog_2010` | N/A | `college-university/nhgis/census-2010/codebook_colleges_nhgis_census2010` |
| Census 2020 | Single | 1980-2023 | `college-university/nhgis/census-2020/colleges_nhgis_geog_2020` | N/A | `college-university/nhgis/census-2020/codebook_colleges_nhgis_census2020` |

### NCCS (Nonprofit 990 Data)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| 990 Forms | Single | 1993-2016 | `college-university/nccs/990-forms/colleges_nccs_all` | `nccs/colleges_nccs_990_forms` | `college-university/nccs/990-forms/codebook_colleges_nccs_form_990` |

### FSA (Federal Student Aid)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Grants | Yearly | 1999-2021 | `college-university/fsa/grants/colleges_fsa_grants_{year}` | `fsa/colleges_fsa_grants` | `college-university/fsa/grants/codebook_colleges_fsa_grants` |
| Loans | Yearly | 1999-2021 | `college-university/fsa/loans/colleges_fsa_loans_{year}` | `fsa/colleges_fsa_loans` | `college-university/fsa/loans/codebook_colleges_fsa_loans` |
| Campus-Based Volume | Yearly | 2001-2021 | `college-university/fsa/campus-based-volume/colleges_fsa_campus_based_vol_{year}` | `fsa/colleges_fsa_campus_based` | `college-university/fsa/campus-based-volume/codebook_colleges_fsa_campus_based_volume` |
| Financial Responsibility | Single | 2006-2016 | `college-university/fsa/financial-responsibility/colleges_fsa_fin_resp` | `fsa/colleges_fsa_fin_resp` | `college-university/fsa/financial-responsibility/codebook_colleges_fsa_financial_responsibility` |
| 90/10 Revenue | Single | 2014-2021 | `college-university/fsa/90-10-revenue-percentages/colleges_fsa_90_10_rev_pct` | `fsa/colleges_fsa_90_10` | `college-university/fsa/90-10-revenue-percentages/codebook_colleges_fsa_90-10_revenue_percentages` |

### EADA (Equity in Athletics)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Institutional Characteristics | Single | 2002-2021 | `college-university/eada/institutional-characteristics/colleges_eada_inst_characteristics` | `eada/colleges_eada_inst_characteristics` | `college-university/eada/institutional-characteristics/codebook_colleges_eada_inst-characteristics` |

### NACUBO (Endowments)

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Endowments | Single | 2012-2022 | `college-university/nacubo/endowments/colleges_nacubo_endow` | `nacubo/colleges_nacubo_endow` | `college-university/nacubo/endowments/codebook_colleges_nacubo_endowments` |

### Campus Safety

| Topic | Type | Years | huggingface | urban_csv | codebook |
|-------|------|-------|-------------|-----------|----------|
| Hate Crimes | Single | 2005-2021 | `college-university/campus-crime/hate-crimes/colleges_csafety_hate_crimes` | `csafety/colleges_csafety_hate_crimes` | `college-university/campus-crime/hate-crimes/codebook_colleges_csafety_hate_crimes` |

> **Note:** Only hate crimes data is available in the Portal mirrors. For full campus safety data (primary offenses, VAWA, arrests, fire safety), access the Department of Education Campus Safety portal directly.

---

## Notes

- **Single-file datasets** contain all years in one file. Filter locally with `pl.col("year").is_in(years)`.
- **Yearly datasets** have one file per year with `{year}` in the path. Fetch each year separately and concatenate.
- **Mirror column values** are URL template parameters, not full URLs. See `mirrors.yaml` for URL templates.
- **Codebook files** are `.xls` files available on both mirrors. The `codebook` column contains the full path (without extension); use `get_codebook_url()` from `fetch-patterns.md` to construct download URLs. Naming pattern: `codebook_{entity}_{source}_{topic}`. Codebooks are for human reference — not parsed programmatically.
- **Additional datasets** sections list mirror datasets with codebooks that are not yet fully documented with data file paths. Use mirror discovery to confirm data file paths before fetching.
- **NHGIS codebooks** are available on both mirrors (including Urban CSV), even though NHGIS data files are only available via HuggingFace.
- **Discovery:** Use each mirror's discovery mechanism (defined in `mirrors.yaml`) to verify file availability before fetching.
- **Cross-reference** source-specific skills for variable names, coded values, and caveats.
- **Adding a new mirror:** Add a column to these tables with the new mirror's name (matching `mirrors.yaml`) and fill in URL template parameters.
