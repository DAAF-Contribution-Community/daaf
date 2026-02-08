# Datasets Reference

Known dataset file paths for the Education Data Portal mirrors. This is a human-readable reference for planning fetch scripts. For mirrors with discovery support (see `mirrors.yaml`), the discovery endpoint is the authoritative source for what's currently available.

---

## How to Use This Reference

1. Find your dataset in the tables below
2. Note the **Type** (single-file or yearly) and available **Years**
3. Copy the per-mirror path columns into your `dataset_paths` dict
4. Use the appropriate fetch pattern from `fetch-patterns.md`
5. If unsure whether a file exists, use the mirror's discovery endpoint (see `mirrors.yaml`)

### Mirror Path Columns

Each table has columns named after mirrors defined in `mirrors.yaml`. The column values provide the URL template parameters for that mirror's `url_template`:

| Mirror Column | URL Template | Parameters in Column |
|---------------|-------------|---------------------|
| `huggingface` | `{root_url}/{path}.parquet` | `path` value |
| `urban_csv` | `{root_url}/{source}/{filename}.csv` | `source/filename` (slash-separated) |

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

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Directory | Single | All years | `school-districts/ccd/directory/school-districts_lea_directory` | `ccd/school-districts_ccd_directory` |
| Enrollment | Yearly | 1986-2023 | `school-districts/ccd/enrollment/schools_ccd_lea_enrollment_{year}` | `ccd/school-districts_ccd_enrollment` |
| Finance | Single | All years | `school-districts/ccd/finance/districts_ccd_finance` | `ccd/school-districts_ccd_finance` |

### EDFacts

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Assessments | Yearly | 2009-2020 | `school-districts/edfacts/assessments/districts_edfacts_assessments_{year}` | `edfacts/school-districts_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `school-districts/edfacts/grad-rates/districts_edfacts_grad_rates_{year}` | `edfacts/school-districts_edfacts_grad_rates` |

### SAIPE

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Poverty Estimates | Single | All years | `school-districts/saipe/districts_saipe` | `saipe/school-districts_saipe` |

---

## Schools (`schools/`)

### CCD

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Directory | Single | All years | `schools/ccd/directory/schools_ccd_directory` | `ccd/schools_ccd_directory` |
| Enrollment | Yearly | varies | `schools/ccd/enrollment/schools_ccd_enrollment_{year}` | `ccd/schools_ccd_enrollment` |

### CRDC

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Discipline | Yearly | 2011-2021 | `schools/crdc/discipline/schools_crdc_discipline_k12_{year}` | `crdc/schools_crdc_discipline` |
| AP/IB Enrollment | Single | 2011-2021 | `schools/crdc/ap-ib-enrollment/schools_crdc_apib_enroll` | `crdc/schools_crdc_ap_ib_enrollment` |
| Enrollment | Yearly | 2011-2021 | `schools/crdc/enrollment/schools_crdc_enrollment_k12_{year}` | `crdc/schools_crdc_enrollment` |
| Chronic Absenteeism | Yearly | 2013-2022 | `schools/crdc/chronic-absenteeism/schools_crdc_chronic_absenteeism_{year}` | `crdc/schools_crdc_chronic_absenteeism` |
| Harassment/Bullying | Yearly | 2011-2021 | `schools/crdc/harassment-or-bullying/schools_crdc_harass_bully_students_{year}` | `crdc/schools_crdc_harass_bully` |
| Restraint/Seclusion | Yearly | 2011-2021 | `schools/crdc/restraint-and-seclusion/schools_crdc_restraint_seclusion_students_{year}` | `crdc/schools_crdc_restraint_seclusion` |

### MEPS

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Poverty | Single | varies | `schools/meps/schools_meps` | `meps/schools_meps` |

### EDFacts

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Assessments | Yearly | 2009-2018, 2020 | `schools/edfacts/assessments/schools_edfacts_assessments_{year}` | `edfacts/schools_edfacts_assessments` |
| Grad Rates | Yearly | 2010-2019 | `schools/edfacts/grad-rates/schools_edfacts_grad_rates_{year}` | `edfacts/schools_edfacts_grad_rates` |

> **Note:** 2019 assessment data is NOT available due to COVID testing waivers.

### NHGIS (Census Geography)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Census 1990 | Single | 1986-2023 | `schools/nhgis/census-1990/schools_nhgis_geog_1990` | N/A |
| Census 2000 | Single | 1986-2023 | `schools/nhgis/census-2000/schools_nhgis_geog_2000` | N/A |
| Census 2010 | Single | 1986-2023 | `schools/nhgis/census-2010/schools_nhgis_geog_2010` | N/A |
| Census 2020 | Single | 1986-2023 | `schools/nhgis/census-2020/schools_nhgis_geog_2020` | N/A |

---

## College-University (`college-university/`)

### IPEDS

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Directory | Single | All years | `college-university/ipeds/directory/colleges_ipeds_directory` | `ipeds/colleges_ipeds_directory` |
| Admissions | Single | varies | `college-university/ipeds/admissions-enrollment/colleges_ipeds_admissions-enrollment` | `ipeds/colleges_ipeds_admissions-enrollment` |
| Enrollment FTE | Single | varies | `college-university/ipeds/enrollment-full-time-equivalent/colleges_ipeds_enrollment-fte` | `ipeds/colleges_ipeds_enrollment-full-time-equivalent` |
| Graduation Rates | Single | varies | `college-university/ipeds/grad-rates/colleges_ipeds_grad-rates` | `ipeds/colleges_ipeds_grad-rates` |
| Finance | Single | varies | `college-university/ipeds/finance/colleges_ipeds_finance` | `ipeds/colleges_ipeds_finance` |

### Scorecard

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Earnings | Single | varies | `college-university/scorecard/earnings/colleges_scorecard_earnings` | `scorecard/colleges_scorecard_earnings` |

### PSEO (Postsecondary Employment Outcomes)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Earnings and Flows | Yearly | 2001-2021 | `college-university/pseo/earnings-and-flows/colleges_pseo_{year}` | `pseo/colleges_pseo_earnings_flows` |

### NHGIS (Census Geography)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Census 1990 | Single | 1980-2023 | `college-university/nhgis/census-1990/colleges_nhgis_geog_1990` | N/A |
| Census 2000 | Single | 1980-2023 | `college-university/nhgis/census-2000/colleges_nhgis_geog_2000` | N/A |
| Census 2010 | Single | 1980-2023 | `college-university/nhgis/census-2010/colleges_nhgis_geog_2010` | N/A |
| Census 2020 | Single | 1980-2023 | `college-university/nhgis/census-2020/colleges_nhgis_geog_2020` | N/A |

### NCCS (Nonprofit 990 Data)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| 990 Forms | Single | 1993-2016 | `college-university/nccs/990-forms/colleges_nccs_all` | `nccs/colleges_nccs_990_forms` |

### FSA (Federal Student Aid)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Grants | Yearly | 1999-2021 | `college-university/fsa/grants/colleges_fsa_grants_{year}` | `fsa/colleges_fsa_grants` |
| Loans | Yearly | 1999-2021 | `college-university/fsa/loans/colleges_fsa_loans_{year}` | `fsa/colleges_fsa_loans` |
| Campus-Based Volume | Yearly | 2001-2021 | `college-university/fsa/campus-based-volume/colleges_fsa_campus_based_vol_{year}` | `fsa/colleges_fsa_campus_based` |
| Financial Responsibility | Single | 2006-2016 | `college-university/fsa/financial-responsibility/colleges_fsa_fin_resp` | `fsa/colleges_fsa_fin_resp` |
| 90/10 Revenue | Single | 2014-2021 | `college-university/fsa/90-10-revenue-percentages/colleges_fsa_90_10_rev_pct` | `fsa/colleges_fsa_90_10` |

### EADA (Equity in Athletics)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Institutional Characteristics | Single | 2002-2021 | `college-university/eada/institutional-characteristics/colleges_eada_inst_characteristics` | `eada/colleges_eada_inst_characteristics` |

### NACUBO (Endowments)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Endowments | Single | 2012-2022 | `college-university/nacubo/endowments/colleges_nacubo_endow` | `nacubo/colleges_nacubo_endow` |

### Campus Safety

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Hate Crimes | Single | 2005-2021 | `college-university/campus-crime/hate-crimes/colleges_csafety_hate_crimes` | `campus-crime/colleges_csafety_hate_crimes` |

> **Note:** Only hate crimes data is available in the Portal mirrors. For full campus safety data (primary offenses, VAWA, arrests, fire safety), access the Department of Education Campus Safety portal directly.

---

## Notes

- **Single-file datasets** contain all years in one file. Filter locally with `pl.col("year").is_in(years)`.
- **Yearly datasets** have one file per year with `{year}` in the path. Fetch each year separately and concatenate.
- **Mirror column values** are URL template parameters, not full URLs. See `mirrors.yaml` for URL templates.
- **Discovery:** Use each mirror's discovery mechanism (defined in `mirrors.yaml`) to verify file availability before fetching.
- **Cross-reference** source-specific skills for variable names, coded values, and caveats.
- **Adding a new mirror:** Add a column to these tables with the new mirror's name (matching `mirrors.yaml`) and fill in URL template parameters.
