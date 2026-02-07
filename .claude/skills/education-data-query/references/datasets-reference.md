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

## Schools (`schools/`) — Coming Soon

*These paths are expected based on the portal structure. Verify with mirror discovery before using.*

### CCD

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Directory | Single | All years | `schools/ccd/directory/schools_ccd_directory` | `ccd/schools_ccd_directory` |
| Enrollment | Yearly | varies | `schools/ccd/enrollment/schools_ccd_enrollment_{year}` | `ccd/schools_ccd_enrollment` |

### CRDC

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Discipline | Single | biennial | `schools/crdc/discipline/schools_crdc_discipline` | `crdc/schools_crdc_discipline` |
| AP/IB | Single | biennial | `schools/crdc/ap-ib-enrollment/schools_crdc_ap_ib_enrollment` | `crdc/schools_crdc_ap_ib_enrollment` |

### MEPS

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Poverty | Single | varies | `schools/meps/schools_meps` | `meps/schools_meps` |

### EDFacts

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Assessments | Yearly | 2009-2020 | `schools/edfacts/assessments/schools_edfacts_assessments_{year}` | `edfacts/schools_edfacts_assessments` |
| Grad Rates | Single | varies | `schools/edfacts/grad-rates/schools_edfacts_grad_rates` | `edfacts/schools_edfacts_grad_rates` |

---

## College-University (`college-university/`) — Coming Soon

*These paths are expected. Verify with mirror discovery before using.*

### IPEDS

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Directory | Single | All years | `college-university/ipeds/directory/colleges_ipeds_directory` | `ipeds/colleges_ipeds_directory` |
| Admissions | Single | varies | `college-university/ipeds/admissions-enrollment/colleges_ipeds_admissions_enrollment` | `ipeds/colleges_ipeds_admissions-enrollment` |
| Enrollment FTE | Single | varies | `college-university/ipeds/enrollment-full-time-equivalent/colleges_ipeds_enrollment_fte` | `ipeds/colleges_ipeds_enrollment-full-time-equivalent` |
| Graduation Rates | Single | varies | `college-university/ipeds/grad-rates/colleges_ipeds_grad_rates` | `ipeds/colleges_ipeds_grad-rates` |
| Finance | Single | varies | `college-university/ipeds/finance/colleges_ipeds_finance` | `ipeds/colleges_ipeds_finance` |

### Scorecard

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Earnings | Single | varies | `college-university/scorecard/earnings/colleges_scorecard_earnings` | `scorecard/colleges_scorecard_earnings` |

---

## Notes

- **Single-file datasets** contain all years in one file. Filter locally with `pl.col("year").is_in(years)`.
- **Yearly datasets** have one file per year with `{year}` in the path. Fetch each year separately and concatenate.
- **Mirror column values** are URL template parameters, not full URLs. See `mirrors.yaml` for URL templates.
- **Discovery:** Use each mirror's discovery mechanism (defined in `mirrors.yaml`) to verify file availability before fetching.
- **Cross-reference** source-specific skills for variable names, coded values, and caveats.
- **Adding a new mirror:** Add a column to these tables with the new mirror's name (matching `mirrors.yaml`) and fill in URL template parameters.
