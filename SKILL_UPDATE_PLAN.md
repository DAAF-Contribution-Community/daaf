# Education Data Skills Update Plan

**Created:** 2026-02-08
**Updated:** 2026-02-08
**Purpose:** Systematic update of all education data skills following transition from API to mirror-based data fetching
**Status:** ALL PHASES COMPLETE (1-5)

---

## Executive Summary

Following the major workflow revision from paginated API calls to full dataset downloads from mirrors (Huggingface parquet + Urban CSV), 14 education data source skills and 2 cross-cutting skills require updates. This plan documents all required changes with specific file locations and proposed edits.

### Scope Summary

| Category | Count | Estimated Effort |
|----------|-------|------------------|
| Files to REMOVE | 1 | Low |
| Files requiring MAJOR rewrites | 8 | High |
| Files requiring MODERATE updates | 15 | Medium |
| Files requiring MINOR updates | 12 | Low |
| New content to ADD | 6 dataset entries | Low |

---

## Phase 1: Critical Path Updates (HIGH Priority)

These changes are blocking or affect multiple downstream skills.

### 1.1 Update datasets-reference.md (CENTRAL FILE)

**File:** `/daaf/.claude/skills/education-data-query/references/datasets-reference.md`

**Action:** Add missing dataset entries for 6 sources

**Add after line 115 (after existing College-University section):**

```markdown
### PSEO

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Earnings and Flows | Yearly | 2001-2021 | `college-university/pseo/earnings-and-flows/colleges_pseo_{year}` | `pseo/colleges_pseo_earnings_flows` |

### NHGIS (Schools)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Census 1990 Geography | Single | 1986-2023 | `schools/nhgis/census-1990/schools_nhgis_geog_1990` | N/A |
| Census 2000 Geography | Single | 1986-2023 | `schools/nhgis/census-2000/schools_nhgis_geog_2000` | N/A |
| Census 2010 Geography | Single | 1986-2023 | `schools/nhgis/census-2010/schools_nhgis_geog_2010` | N/A |
| Census 2020 Geography | Single | 1986-2023 | `schools/nhgis/census-2020/schools_nhgis_geog_2020` | N/A |

### NHGIS (Colleges)

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Census 1990 Geography | Single | 1980-2023 | `college-university/nhgis/census-1990/colleges_nhgis_geog_1990` | N/A |
| Census 2000 Geography | Single | 1980-2023 | `college-university/nhgis/census-2000/colleges_nhgis_geog_2000` | N/A |
| Census 2010 Geography | Single | 1980-2023 | `college-university/nhgis/census-2010/colleges_nhgis_geog_2010` | N/A |
| Census 2020 Geography | Single | 1980-2023 | `college-university/nhgis/census-2020/colleges_nhgis_geog_2020` | N/A |

### NCCS

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| 990 Forms | Single | 1993-2016 | `college-university/nccs/990-forms/colleges_nccs_all` | `nccs/colleges_nccs_990_forms` |

### EADA

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Institutional Characteristics | Single | 2002-2021 | `college-university/eada/institutional-characteristics/colleges_eada_inst_characteristics` | `eada/colleges_eada_inst_characteristics` |

### NACUBO

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Endowments | Single | 2012-2022 | `college-university/nacubo/endowments/colleges_nacubo_endow` | `nacubo/colleges_nacubo_endow` |

### Campus Safety

| Topic | Type | Years | huggingface | urban_csv |
|-------|------|-------|-------------|-----------|
| Hate Crimes | Single | 2005-2021 | `college-university/campus-crime/hate-crimes/colleges_csafety_hate_crimes` | `campus-crime/colleges_csafety_hate_crimes` |

> **Note:** Only hate crimes data is available in the Portal mirrors. For full campus safety data (primary offenses, VAWA, arrests, fire safety), access the Department of Education directly.
```

---

### 1.2 Fix CRDC Paths in datasets-reference.md

**File:** `/daaf/.claude/skills/education-data-query/references/datasets-reference.md`

**Current (lines 79-82 - INCORRECT):**
```markdown
| Discipline | Single | biennial | `schools/crdc/discipline/schools_crdc_discipline` | `crdc/schools_crdc_discipline` |
| AP/IB | Single | biennial | `schools/crdc/ap-ib-enrollment/schools_crdc_ap_ib_enrollment` | `crdc/schools_crdc_ap_ib_enrollment` |
```

**Replace with:**
```markdown
| Discipline | Yearly | 2011-2021 | `schools/crdc/discipline/schools_crdc_discipline_k12_{year}` | `crdc/schools_crdc_discipline` |
| AP/IB Enrollment | Single | 2011-2021 | `schools/crdc/ap-ib-enrollment/schools_crdc_apib_enroll` | `crdc/schools_crdc_ap_ib_enrollment` |
| Enrollment | Yearly | 2011-2021 | `schools/crdc/enrollment/schools_crdc_enrollment_k12_{year}` | `crdc/schools_crdc_enrollment` |
| Chronic Absenteeism | Yearly | 2013-2022 | `schools/crdc/chronic-absenteeism/schools_crdc_chronic_absenteeism_{year}` | TBD |
| Harassment/Bullying | Yearly | 2011-2021 | `schools/crdc/harassment-or-bullying/schools_crdc_harass_bully_students_{year}` | TBD |
```

---

### 1.3 Fix EDFacts Paths in datasets-reference.md

**File:** `/daaf/.claude/skills/education-data-query/references/datasets-reference.md`

**Current (lines 89-94):**
```markdown
| Grad Rates | Single | varies | `schools/edfacts/grad-rates/schools_edfacts_grad_rates` | `edfacts/schools_edfacts_grad_rates` |
```

**Replace with:**
```markdown
| Grad Rates | Yearly | 2010-2019 | `schools/edfacts/grad-rates/schools_edfacts_grad_rates_{year}` | `edfacts/schools_edfacts_grad_rates` |
```

**Also update Assessments note:**
```markdown
| Assessments | Yearly | 2009-2018, 2020 | `schools/edfacts/assessments/schools_edfacts_assessments_{year}` | ... |
```
*Add note: "2019 assessment data is MISSING due to COVID waivers"*

---

### 1.4 Remove Vestigial EADA API File

**File:** `/daaf/.claude/skills/education-data-source-eada/references/api-endpoints.md`

**Action:** DELETE entire file (400+ lines of API-specific documentation)

**Replacement:** Create new file `/daaf/.claude/skills/education-data-source-eada/references/fetch-patterns.md`:

```markdown
# EADA Data Access

EADA data is fetched from mirrors via the `education-data-query` skill.

## Mirror Path

| Dataset | Path |
|---------|------|
| Institutional Characteristics | `college-university/eada/institutional-characteristics/colleges_eada_inst_characteristics.parquet` |

## Example Fetch

```python
import polars as pl

# Fetch EADA institutional data
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/college-university/eada/institutional-characteristics/colleges_eada_inst_characteristics.parquet"
df = pl.read_parquet(url)

# Filter by year and state
df = df.filter(
    (pl.col("year") == 2021) &
    (pl.col("fips") == 6)  # California
)
```

## Available Columns

Key columns in Portal data (165 total):
- `unitid`, `year`, `fips`, `inst_name`
- `undup_athpartic_men`, `undup_athpartic_women` (unduplicated participation)
- `athpartic_men`, `athpartic_women` (total participation)
- `men_fthdcoach_male`, `women_fthdcoach_fem` (coaching staff)
- `hdcoach_salary_men`, `hdcoach_salary_women` (salary data)
- `ath_exp_men`, `ath_exp_women` (expenses)
- `ath_rev_men`, `ath_rev_women` (revenues)
- `ath_stuaid_men`, `ath_stuaid_women` (student aid)

See `variable-definitions.md` for complete column documentation.
```

---

## Phase 2: API Reference Removal (MEDIUM Priority)

Remove or replace API-specific sections in individual skill files.

### 2.1 CCD Skill

**File:** `/daaf/.claude/skills/education-data-source-ccd/SKILL.md`

**Action:** Replace lines 210-250 (API patterns section)

**Remove:**
```markdown
## Education Data Portal API Patterns

> **API Implementation:** For URL construction patterns, pagination, and error handling...
[... entire section about disaggregator rules, URL paths, etc. ...]
```

**Replace with:**
```markdown
## Data Fetching

CCD data is fetched from mirrors (parquet or CSV), not via REST API. See the `education-data-query` skill for:
- Mirror configuration (`mirrors.yaml`)
- Fetch patterns (`fetch-patterns.md`)
- Dataset file paths (`datasets-reference.md`)

### CCD Dataset Paths

| Topic | Type | Huggingface Path |
|-------|------|------------------|
| School Directory | Single | `schools/ccd/directory/schools_ccd_directory` |
| School Enrollment | Yearly | `schools/ccd/enrollment/schools_ccd_enrollment_{year}` |
| District Directory | Single | `school-districts/ccd/directory/school-districts_lea_directory` |
| District Enrollment | Yearly | `school-districts/ccd/enrollment/schools_ccd_lea_enrollment_{year}` |
| District Finance | Single | `school-districts/ccd/finance/districts_ccd_finance` |

### Filtering CCD Data

All filtering is done locally with Polars after download:

```python
import polars as pl

# Filter by state (California)
df = df.filter(pl.col("fips") == 6)

# Filter by year
df = df.filter(pl.col("year").is_in([2020, 2021, 2022]))

# Get totals only (enrollment)
df = df.filter(pl.col("grade") == 99)
```
```

**Additional CCD update - Add prominent warning after Quick Reference:**
```markdown
## CRITICAL: Grade -1 Encoding

In CCD enrollment data:
- `grade = -1` means **Pre-Kindergarten**, NOT missing data
- `grade = 99` means **Total** across all grades

Do NOT filter `grade >= 0` — this removes all Pre-K students!

```python
# WRONG - removes Pre-K students!
df = df.filter(pl.col("grade") >= 0)

# CORRECT
pre_k = df.filter(pl.col("grade") == -1)  # Pre-K only
k12 = df.filter(pl.col("grade").is_between(0, 12))  # K-12
total = df.filter(pl.col("grade") == 99)  # All grades
```
```

---

### 2.2 CRDC Skill

**File:** `/daaf/.claude/skills/education-data-source-crdc/SKILL.md`

**Action:** Replace lines 175-214 (API section)

**Remove:** "API Access via Education Data Portal" section

**Replace with:**
```markdown
## Data Access via Mirrors

CRDC data is available through configured mirrors (see `education-data-query` skill).

### File Structure

| Topic | File Pattern | Type |
|-------|-------------|------|
| Discipline | `schools_crdc_discipline_k12_{year}.parquet` | Yearly (2011-2021) |
| AP/IB Enrollment | `schools_crdc_apib_enroll.parquet` | Single file (all years) |
| Enrollment | `schools_crdc_enrollment_k12_{year}.parquet` | Yearly |

### Example Fetch

```python
import polars as pl

# Discipline (yearly file)
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/crdc/discipline/schools_crdc_discipline_k12_2017.parquet"
df = pl.read_parquet(url)

# AP/IB (single file)
url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/crdc/ap-ib-enrollment/schools_crdc_apib_enroll.parquet"
df = pl.read_parquet(url)
```
```

---

### 2.3 EDFacts Skill

**File:** `/daaf/.claude/skills/education-data-source-edfacts/SKILL.md`

**Action:** Replace lines 209-240 (API endpoints section)

**Remove:** "Urban Institute Education Data Portal Endpoints" section

**Replace with:**
```markdown
## Data Access via Mirrors

EDFacts data is available through configured mirrors (see `education-data-query` skill).

### File Structure

| Topic | File Pattern | Type | Years |
|-------|-------------|------|-------|
| Assessments | `schools_edfacts_assessments_{year}.parquet` | Yearly | 2009-2018, 2020 (NO 2019) |
| Graduation Rates | `schools_edfacts_grad_rates_{year}.parquet` | Yearly | 2010-2019 |

**Note:** 2019 assessment data is NOT available due to COVID testing waivers.

### Grade Filtering

EDFacts uses `grade_edfacts` column with integer codes:
- 3-8: Grades 3-8
- 9: High school
- 99: All grades combined
```

**Also update year availability table (lines 225-229):**
```markdown
| Data Type | Years Available | Notes |
|-----------|-----------------|-------|
| Assessments | 2009-2018, 2020 | **2019 is MISSING** (COVID waivers) |
| Graduation Rates | 2010-2019 | 2020 NOT available in mirror |
```

---

### 2.4 MEPS Skill

**File:** `/daaf/.claude/skills/education-data-source-meps/SKILL.md`

**Action:**
1. Remove line 36 API endpoint reference
2. Replace lines 147-162 "Quick Reference: API Endpoint" section

**Replace with:**
```markdown
## Quick Reference: Data Access

| Mirror | Path |
|--------|------|
| huggingface | `schools/meps/schools_meps.parquet` |
| urban_csv | `meps/schools_meps.csv` |

### Example Fetch

```python
import polars as pl

url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/schools/meps/schools_meps.parquet"
df = pl.read_parquet(url)

# Filter by state and year
df = df.filter(
    (pl.col("fips") == 6) &
    (pl.col("year") == 2018)
)
```
```

**File:** `/daaf/.claude/skills/education-data-source-meps/references/api-usage.md`

**Action:** Rename to `data-access.md` and add deprecation header:

```markdown
# MEPS Data Access

> **Note:** This skill has been updated for mirror-based data fetching. The API examples below are retained for reference but are not the primary access method. See `education-data-query` skill for fetch patterns.

## Mirror-Based Access (Primary)

[Add mirror fetch example here]

## API Access (Legacy Reference)

[Keep existing content but mark as secondary]
```

---

### 2.5 SAIPE Skill

**File:** `/daaf/.claude/skills/education-data-source-saipe/SKILL.md`

**Action:** Replace lines 174-194 (Education Data Portal Access section)

**Replace with:**
```markdown
## Data Access via Mirrors

SAIPE data is available through configured mirrors (see `education-data-query` skill).

| Mirror | Path |
|--------|------|
| huggingface | `school-districts/saipe/districts_saipe.parquet` |
| urban_csv | `saipe/school-districts_saipe.csv` |

### Example Fetch

```python
import polars as pl

url = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/school-districts/saipe/districts_saipe.parquet"
df = pl.read_parquet(url)

# Filter by state and year
df = df.filter(
    (pl.col("fips") == 6) &
    (pl.col("year") == 2020)
)
```
```

---

### 2.6 IPEDS Skill

**File:** `/daaf/.claude/skills/education-data-source-ipeds/SKILL.md`

**Action:** Rename section "Education Data Portal API Gotchas" (lines 291-371) to "Portal Data Considerations"

**Remove:**
- Line 293: Reference to "pagination and error handling"
- Lines 349-357: "Path Segments That Fail" section (API-specific)

**Keep (still relevant):**
- Sex disaggregation warning for admissions data
- Variable name mappings
- `inst_size` categorical encoding note

---

### 2.7 FSA Skill

**File:** `/daaf/.claude/skills/education-data-source-fsa/SKILL.md`

**Action:** Update lines 78-88 (decision tree) to use mirror paths instead of API paths

**Replace API-style paths:**
```markdown
| Dataset | Mirror Path |
|---------|-------------|
| Grants | `college-university/fsa/grants/colleges_fsa_grants` |
| Loans | `college-university/fsa/loans/colleges_fsa_loans` |
| Campus-Based | `college-university/fsa/campus-based-volume/colleges_fsa_campus_based_vol` |
| Financial Responsibility | `college-university/fsa/financial-responsibility/colleges_fsa_fin_resp` |
| 90/10 Revenue | `college-university/fsa/90-10-revenue-percentages/colleges_fsa_90_10_rev_pct` |
```

---

### 2.8 Scorecard Skill

**File:** `/daaf/.claude/skills/education-data-source-scorecard/SKILL.md`

**Action:** Add Portal data structure note explaining LONG format

**Add new section after Quick Reference:**
```markdown
## Portal Data Structure (CRITICAL)

The Portal uses **LONG format** with time horizon as a column, NOT the WIDE format documented in original Scorecard files.

### Key Differences

| Scorecard (WIDE) | Portal (LONG) | How to Get |
|------------------|---------------|------------|
| `MD_EARN_WNE_P6` | `earnings_med` | Filter: `years_after_entry == 6` |
| `MD_EARN_WNE_P10` | `earnings_med` | Filter: `years_after_entry == 10` |
| `COUNT_WNE_P6` | `count_working` | Filter: `years_after_entry == 6` |
| `CONTROL`, `INSTNM` | NOT IN FILE | Join to IPEDS directory |

### Example Query

```python
# Get 10-year earnings for California colleges
df = df.filter(
    (pl.col("fips") == 6) &
    (pl.col("years_after_entry") == 10)
)
```

### Missing Values

Both `-3` (suppressed) and `null` (missing) appear in Portal data:
```python
# Filter for valid earnings
df = df.filter(
    (pl.col("earnings_med").is_not_null()) &
    (pl.col("earnings_med") != -3)
)
```
```

---

## Phase 3: Cross-Cutting Skills (MEDIUM Priority)

### 3.1 education-data-explorer

**File:** `/daaf/.claude/skills/education-data-explorer/SKILL.md`

**Actions (5 sections to update):**

1. **Lines 14-20 (Identity statement):** Replace "Free, public API" with "Comprehensive education data" framing
2. **Lines 93-97 (Data Levels table):** Change "Base URL" column to "Mirror Path Prefix"
3. **Lines 179-193 (URL Pattern Structure):** Rename to "Dataset Path Structure", update examples to mirror paths
4. **Lines 195-217 (Filtering):** Replace API query parameters with Polars filter examples
5. **Lines 309-344 (Pre-Query Validation):** Update to show parquet inspection instead of API calls

**File:** `/daaf/.claude/skills/education-data-explorer/references/metadata-api.md`

**Action:** Add deprecation header:
```markdown
> **Note:** This file documents the Education Data Portal's REST metadata API. With the mirror-based workflow, file discovery uses mirror-specific methods (see `mirrors.yaml`). This documentation remains useful for understanding variable definitions but is not the primary data access method.
```

---

### 3.2 education-data-context

**File:** `/daaf/.claude/skills/education-data-context/references/data-relationships.md`

**Action:** Replace all `educationdata.get_education_data()` examples with Polars mirror-based patterns

**Example replacement:**
```python
# OLD
schools = educationdata.get_education_data(
    level="schools",
    source="ccd",
    topic="directory",
    filters={"year": 2020}
)

# NEW
import polars as pl

# Load from mirror (see education-data-query skill for full pattern)
schools = pl.read_parquet("data/raw/schools_ccd_directory.parquet").filter(
    pl.col("year") == 2020
)
```

---

## Phase 4: Variable Definition Updates (LOW Priority)

### 4.1 Add Missing Encoding Values

**Files to update:**
- `/daaf/.claude/skills/education-data-source-ccd/references/variable-definitions.md` - Add race=9 (Unknown)
- `/daaf/.claude/skills/education-data-source-ipeds/references/variable-definitions.md` - Add NCES-to-Portal column mapping

### 4.2 Fix Variable Name Mismatches

| Skill | Documented | Actual Portal Name |
|-------|------------|-------------------|
| CCD | `locale` | `urban_centric_locale` |
| IPEDS | `instnm` | `inst_name` |
| IPEDS | `control` | `inst_control` |
| CRDC | `students_expelled_with_services` | `expulsions_with_ed_serv` |
| CRDC | `ap_enrollment` | `enrl_ap` |
| FSA | `pell_recipients` | `grant_recipients_unitid` (filter by grant_type=1) |
| EADA | `partic_men` | `undup_athpartic_men` |
| PSEO | `opeid` (documented as Int) | `opeid` (actual: String) |

---

## Phase 5: Documentation Additions (LOW Priority)

### 5.1 Add Limited Coverage Warnings

**Campus Safety:** Add prominent note that only hate crimes data is in Portal mirrors

**NACUBO:** Add note that only 7 columns (market values) are in Portal, not full investment/governance data

### 5.2 Add Schema Difference Notes

**NHGIS:** Note that schools NHGIS (47 cols) has different schema than colleges NHGIS (26 cols)

---

## Implementation Order

| Phase | Priority | Files | Estimated Changes |
|-------|----------|-------|-------------------|
| 1.1-1.4 | HIGH | 2 files | 4 major edits |
| 2.1-2.8 | MEDIUM | 8 files | 8 section replacements |
| 3.1-3.2 | MEDIUM | 3 files | 6 section updates |
| 4.1-4.2 | LOW | 6 files | Variable table updates |
| 5.1-5.2 | LOW | 3 files | Warning notes |

---

## Validation Checklist

After implementation, verify:

- [ ] All 6 new sources appear in datasets-reference.md
- [ ] CRDC discipline path includes `{year}` placeholder
- [ ] EDFacts grad rates path includes `{year}` placeholder
- [ ] No remaining references to `/api/v1/` in any skill SKILL.md
- [ ] No remaining `educationdata.get_education_data()` calls in examples
- [ ] All fetch examples use Polars + mirror URLs
- [ ] Test fetch for each source still works

---

## Files Summary

### To DELETE
1. `/daaf/.claude/skills/education-data-source-eada/references/api-endpoints.md`

### To CREATE
1. `/daaf/.claude/skills/education-data-source-eada/references/fetch-patterns.md`

### To UPDATE (Major)
1. `/daaf/.claude/skills/education-data-query/references/datasets-reference.md`
2. `/daaf/.claude/skills/education-data-source-ccd/SKILL.md`
3. `/daaf/.claude/skills/education-data-source-crdc/SKILL.md`
4. `/daaf/.claude/skills/education-data-source-edfacts/SKILL.md`
5. `/daaf/.claude/skills/education-data-source-meps/SKILL.md`
6. `/daaf/.claude/skills/education-data-source-scorecard/SKILL.md`
7. `/daaf/.claude/skills/education-data-explorer/SKILL.md`
8. `/daaf/.claude/skills/education-data-context/references/data-relationships.md`

### To UPDATE (Moderate)
1. `/daaf/.claude/skills/education-data-source-saipe/SKILL.md`
2. `/daaf/.claude/skills/education-data-source-ipeds/SKILL.md`
3. `/daaf/.claude/skills/education-data-source-fsa/SKILL.md`
4. `/daaf/.claude/skills/education-data-source-meps/references/api-usage.md` (rename)
5. `/daaf/.claude/skills/education-data-source-pseo/references/api-access.md`
6. `/daaf/.claude/skills/education-data-source-campus-safety/SKILL.md`
7. `/daaf/.claude/skills/education-data-source-nacubo/SKILL.md`
8. `/daaf/.claude/skills/education-data-explorer/references/metadata-api.md`

### To UPDATE (Minor)
1. `/daaf/.claude/skills/education-data-source-ccd/references/variable-definitions.md`
2. `/daaf/.claude/skills/education-data-source-ipeds/references/variable-definitions.md`
3. `/daaf/.claude/skills/education-data-source-crdc/references/variable-definitions.md`
4. `/daaf/.claude/skills/education-data-source-crdc/references/data-elements.md`
5. `/daaf/.claude/skills/education-data-source-eada/SKILL.md`
6. `/daaf/.claude/skills/education-data-source-eada/references/variable-definitions.md`
7. `/daaf/.claude/skills/education-data-source-nacubo/references/variable-definitions.md`
8. `/daaf/.claude/skills/education-data-source-campus-safety/references/variable-definitions.md`
9. `/daaf/.claude/skills/education-data-source-nhgis/SKILL.md`
10. `/daaf/.claude/skills/education-data-source-pseo/SKILL.md`
11. `/daaf/.claude/skills/education-data-context/references/crdc-context.md`
12. `/daaf/.claude/skills/education-data-context/references/ipeds-context.md`
