---
name: education-data-source-scorecard
description: >-
  College Scorecard — post-enrollment outcomes linking aid records to IRS/Treasury earnings. Earnings, loan repayment, debt via six Portal sub-datasets. Use when tax-record-based earnings needed. Tracks only Title IV aid recipients, not all students.
metadata:
  audience: any-agent
  domain: data-source
  skill-authored: "2026-02-09"
  skill-last-updated: "2026-07-21"
---

# Scorecard Data Source Reference

College Scorecard — the primary institutional-level source for post-enrollment labor market outcomes, linking NSLDS financial aid records to IRS/Treasury earnings data. Use when comparing institutions on post-graduation earnings, loan repayment, or student debt, or when actual tax-record-based earnings are required rather than survey estimates. The Portal mirrors six institution-level families and does not mirror program/field-of-study data; use the official Scorecard Data page or documented API for program-level work. Critical limitation: tracks only Title IV federal aid recipients, not all students.

Federal data on post-college outcomes including earnings, debt, and repayment for students who received Title IV financial aid. Links education records to IRS tax data for actual earnings, making it the primary source for post-college labor market outcomes.

> **CRITICAL: Value Encoding and Missing Data**
>
> The Education Data Portal uses **integer encodings** for all categorical variables
> and **lowercase, restructured variable names** that differ from the original
> Scorecard column names. Suppression encoding differs by dataset:
>
> - **Earnings/counts**: `-3` integer code is the primary suppression indicator
> - **Yes/No flags** (institutional characteristics): `null` for missing, `0`/`1` for valid
> - **Rates** (repayment, default): `null` for missing
> - The original Scorecard string `"PrivacySuppressed"` does NOT appear in Portal data
>
> | Context | `pred_degree_awarded_ipeds` | HBCU / tribal flags | `religious_affiliation` |
> |---------|----------------------------|---------------------|-------------------------|
> | **Portal (integer)** | `0`-`4` | `0` / `1` | Integer codes 22-200 |
> | Original Scorecard | String labels | String labels | String labels |
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is College Scorecard?

- **Publisher**: U.S. Department of Education
- **Primary value**: Post-college labor market outcomes (earnings) and debt/repayment metrics
- **Data sources**: NSLDS (loans/aid), IRS/Treasury (earnings), IPEDS (institutional characteristics)
- **Coverage**: **Title IV federal aid recipients only** — not all students
- **Unique feature**: Links education to IRS tax records for actual earnings data
- **Access**: Education Data Portal mirrors (parquet/CSV); see `datasets-reference.md` for paths, `mirrors.yaml` for mirror config, `fetch-patterns.md` for fetch code
- **Primary identifier**: `unitid` (IPEDS institution ID)

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `earnings-data.md` | Post-college earnings methodology, cohorts, time horizons | Analyzing earnings outcomes |
| `debt-repayment.md` | Student debt, repayment rates, default rates | Analyzing debt or loan outcomes |
| `completion-rates.md` | Completion metrics vs IPEDS | Comparing graduation rates |
| `population-coverage.md` | Title IV limitation details, who is included/excluded | Understanding data representativeness |
| `variable-definitions.md` | Key variables, naming conventions, special values | Building queries or interpreting results |
| `data-quality.md` | Suppression rules, selection bias, known limitations | Assessing data reliability |
| `field-of-study.md` | Program-level earnings and debt data | Analyzing outcomes by major/CIP code |

## Decision Trees

### What outcome am I researching?

```
Outcome type?
├─ Post-college earnings
│   ├─ Institution-level → Portal earnings family; ./references/earnings-data.md
│   └─ Program/field of study → NOT in Portal; use https://collegescorecard.ed.gov/data/
│       └─ Choose "Most Recent Data by Field of Study" or the documented API; see ./references/field-of-study.md
├─ Student debt levels
│   ├─ Institution-level borrowing → Portal repayment families; ./references/debt-repayment.md
│   └─ Debt by program/field → NOT in Portal; use the official Data page or documented API
├─ Loan repayment/default
│   └─ Repayment rates → ./references/debt-repayment.md
├─ Completion rates
│   └─ Scorecard completion → ./references/completion-rates.md
└─ Understanding limitations
    ├─ Who is included → ./references/population-coverage.md
    └─ Data quality issues → ./references/data-quality.md
```

### How do I interpret this data?

```
Interpretation question?
├─ Why are earnings suppressed?
│   └─ Privacy thresholds → ./references/data-quality.md
├─ What does "6-year earnings" mean?
│   └─ Cohort timing → ./references/earnings-data.md
├─ Why don't Scorecard rates match IPEDS?
│   └─ Different cohorts → ./references/completion-rates.md
├─ What loans are included in debt?
│   └─ Federal only → ./references/debt-repayment.md
└─ How representative is this data?
    └─ Title IV coverage → ./references/population-coverage.md
```

### Building a query?

```
Query construction?
├─ Portal institution-level family → Use exact path in "All Scorecard Datasets" below
├─ Variable names and codes → ./references/variable-definitions.md
├─ Suppression flags to handle → ./references/data-quality.md
├─ Understanding cohort years → ./references/earnings-data.md
└─ Program/field-level query → Not mirrored by Portal
    └─ Use https://collegescorecard.ed.gov/data/ or documented API; see ./references/field-of-study.md
```

## Quick Reference: Scorecard Variables

### Portal Data Structure (CRITICAL)

The Portal uses **LONG format** with time horizon as a column, NOT the WIDE format from original Scorecard bulk download files. **Portal column names are all lowercase** and differ significantly from original Scorecard names.

| Original Scorecard (WIDE) | Portal Column (LONG) | How to Get |
|---------------------------|----------------------|------------|
| `MD_EARN_WNE_P6` | `earnings_med` | Filter: `years_after_entry == 6` |
| `MD_EARN_WNE_P10` | `earnings_med` | Filter: `years_after_entry == 10` |
| `COUNT_WNE_P6` | `count_working` | Filter: `years_after_entry == 6` |
| `MN_EARN_WNE_P6` | `earnings_mean` | Filter: `years_after_entry == 6` |
| `CONTROL`, `INSTNM` | NOT IN EARNINGS | Join to IPEDS directory or `inst_characteristics` dataset |
| `CDR3` | `default_rate` | In `repayment_fsa` dataset; filter: `years_since_entering_repay` |
| `RPY_3YR_RT` | `repay_rate` | In `repayment_nslds` dataset; filter: `years_since_entering_repay == 3` |

### Earnings Dataset Columns (Actual Portal Names)

> **Source dataset:** `scorecard/colleges_scorecard_earnings` (203,066 rows x 33 columns)

| Portal Column | Type | Description | Original Scorecard |
|---------------|------|-------------|-------------------|
| `unitid` | Int64 | IPEDS institution ID | `UNITID` |
| `opeid` | String | OPE ID (8-digit, zero-padded) | `OPEID` |
| `year` | Int64 | Data year (2003-2014, 2018) | File year |
| `years_after_entry` | Int64 | Years since first enrollment (6-10) | Encoded in variable name |
| `cohort_year` | Int64 | Entry cohort year | Encoded in variable name |
| `earnings_med` | Int64 | Median earnings (W-2) | `MD_EARN_WNE_P*` |
| `earnings_mean` | Int64 | Mean earnings | `MN_EARN_WNE_P*` |
| `earnings_sd` | Int64 | Standard deviation of earnings | `SD_EARN_WNE_P*` |
| `earnings_pct10` | Int64 | 10th percentile earnings | `PCT10_EARN_WNE_P*` |
| `earnings_pct25` | Int64 | 25th percentile earnings | `PCT25_EARN_WNE_P*` |
| `earnings_pct75` | Int64 | 75th percentile earnings | `PCT75_EARN_WNE_P*` |
| `earnings_pct90` | Int64 | 90th percentile earnings | `PCT90_EARN_WNE_P*` |
| `count_working` | Int64 | Count working and not enrolled | `COUNT_WNE_P*` |
| `count_not_working` | Int64 | Count not working and not enrolled | `COUNT_NWNE_P*` |
| `earnings_greater_than_25k_pct` | Float64 | Share earning > $25K | `GT_25K_P*` |
| `earnings_lowinc_mean` | Int64 | Mean earnings, low-income | `MN_EARN_WNE_INC1_P*` |
| `earnings_midinc_mean` | Int64 | Mean earnings, mid-income | `MN_EARN_WNE_INC2_P*` |
| `earnings_highinc_mean` | Int64 | Mean earnings, high-income | `MN_EARN_WNE_INC3_P*` |
| `earnings_dep_mean` | Int64 | Mean earnings, dependent students | — |
| `earnings_dep_lowinc_mean` | Int64 | Mean earnings, dependent low-income | — |
| `earnings_ind_mean` | Int64 | Mean earnings, independent students | — |
| `earnings_female_mean` | Int64 | Mean earnings, female | — |
| `earnings_male_mean` | Int64 | Mean earnings, male | — |
| `count_working_*` | Int64 | Count working by subgroup | — |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `unitid` | 6-digit integer | Institution | `110635` | Same as IPEDS unitid; primary join key |
| `opeid` | 8-digit string | OPE (Title IV) | `"00100200"` | Zero-padded; present in all datasets |
| `opeid6` | Integer | 6-digit OPE | `1002` | Numeric, no zero-padding |

### Data Timing

| Metric | Dimension Column | Values | Typical Lag |
|--------|-----------------|--------|-------------|
| Earnings | `years_after_entry` | 6, 7, 8, 9, 10 | Data from 7+ years ago |
| Default | `years_since_entering_repay` | 2, 3 | Varies |
| Repayment | `years_since_entering_repay` | 1, 3, 5, 7 | Varies |

**"After entry" means after first enrollment**, not after graduation.

### Categorical Value Encodings (Institutional Characteristics Dataset)

| Variable | Values |
|----------|--------|
| `pred_degree_awarded_ipeds` | 0=Not classified, 1=Certificate, 2=Associate's, 3=Bachelor's, 4=Graduate |
| Yes/No flags (HBCU, tribal, etc.) | 0=No, 1=Yes, null=Missing |
| `religious_affiliation` | 76 integer codes 22-200 (see variable-definitions.md for complete mapping), null=None/Missing |

### Missing Data Codes

| Code | Meaning | Which Datasets |
|------|---------|----------------|
| `-3` | Suppressed for privacy | **Earnings dataset** (earnings and count columns) — primary suppression indicator |
| `null` | Missing/not applicable | **Institutional characteristics** (yes/no flags), **repayment/default** (rates) |
| Positive numeric | Actual value | Earnings, debt, counts, rates |

```python
import polars as pl

# Filter for valid earnings (handle -3 suppression code)
valid = df.filter(
    (pl.col("earnings_med").is_not_null()) &
    (pl.col("earnings_med") != -3)
)

# Filter for 6-year earnings specifically
six_yr_valid = valid.filter(pl.col("years_after_entry") == 6)
```
```r
# Filter for valid earnings (handle -3 suppression code)
valid <- df |> filter(!is.na(earnings_med), earnings_med != -3)

# Filter for 6-year earnings specifically
six_yr_valid <- valid |> filter(years_after_entry == 6)
```

## Data Access

Datasets for Scorecard are available via the mirror system. See `datasets-reference.md` for canonical paths, `mirrors.yaml` for mirror configuration, and `fetch-patterns.md` for fetch code patterns.

Codebooks are `.xls` files co-located with data in all mirrors. Use `get_codebook_url()` from `fetch-patterns.md` to construct download URLs.

> **Truth Hierarchy:** When interpreting variable values, apply this priority:
> 1. **Actual data file** (what you observe in the parquet/CSV) — this IS the truth
> 2. **Live codebook** (.xls in mirror) — authoritative documentation, may lag
> 3. **This skill documentation** — convenient summary, may drift from codebook
>
> If this documentation contradicts the codebook, trust the codebook. If the codebook contradicts observed data, trust the data and investigate.

### All Portal Scorecard Datasets (6 Institution-Level Families)

The Portal manifest exposes the six families below. It does **not** expose a field-of-study/program-level family. For current program data, go to `https://collegescorecard.ed.gov/data/` and choose **Most Recent Data by Field of Study**, or use the documented Scorecard API. Do not make a date-stamped ZIP URL the only access route.

| Dataset | Path | Codebook | Type | Years |
|---------|------|----------|------|-------|
| Earnings | `scorecard/colleges_scorecard_earnings` | `scorecard/codebook_colleges_scorecard_earnings` | Single | varies |
| Default | `scorecard/colleges_scorecard_repayment_fsa` | `scorecard/codebook_colleges_scorecard_default` | Single | 1996-2020 |
| Institutional Characteristics | `scorecard/colleges_scorecard_inst_characteristics` | `scorecard/codebook_colleges_scorecard_institutional-characteristics` | Single | 1996-2020 |
| Repayment | `scorecard/colleges_scorecard_repayment_nslds` | `scorecard/codebook_colleges_scorecard_repayment` | Single | 2007-2016 |
| Student Characteristics (Aid) | `scorecard/colleges_scorecard_student_body_nslds` | `scorecard/codebook_colleges_scorecard_student-characteristics_aid-applicants` | Single | 1997-2016 |
| Student Characteristics (Home) | `scorecard/colleges_scorecard_student_body_treasury` | `scorecard/codebook_colleges_scorecard_student-characteristics_home-neighborhood` | Single | 1997-2016 |

> **Scorecard naming note:** Data file paths differ significantly from codebook paths. Notable mismatches: data `repayment_fsa` vs codebook `default`; data `inst_characteristics` vs codebook `institutional-characteristics`; data `repayment_nslds` vs codebook `repayment`; data `student_body_nslds` vs codebook `student-characteristics_aid-applicants`; data `student_body_treasury` vs codebook `student-characteristics_home-neighborhood`. Always use the exact paths shown above.

### Fetching Data

```python
import polars as pl

# Load `education-data-query` before authoring the Stage 5 script, then copy its
# documented `fetch_from_mirrors()` helper contract inline from
# `education-data-query/references/fetch-patterns.md`. There is no local
# `fetch_utils` module to import. The inline helper handles mirror priority,
# failover, and local filtering under the shared query contract.

# Fetch earnings data
earnings = fetch_from_mirrors("scorecard/colleges_scorecard_earnings")

# Filter by time horizon (LONG format — filter, don't use wide column names)
six_yr = earnings.filter(pl.col("years_after_entry") == 6)

# Filter for valid earnings (exclude -3 suppression code)
valid = six_yr.filter(
    (pl.col("earnings_med").is_not_null()) &
    (pl.col("earnings_med") != -3)
)

# Institution names/control are NOT in the earnings dataset.
# Join to inst_characteristics or IPEDS directory:
inst = fetch_from_mirrors("scorecard/colleges_scorecard_inst_characteristics",
                          years=[2020])
valid = valid.join(
    inst.select("unitid", "inst_name", "pred_degree_awarded_ipeds"),
    on="unitid", how="left"
)
```
```r
# Fetch earnings data.
# fetch_from_mirrors() is a Python helper; in R, build the URL from the mirror
# root in mirrors.yaml and read directly.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern).
config <- yaml::read_yaml("mirrors.yaml")
mirror <- config$mirrors[[1]]
url <- paste0(mirror$root_url, "/", "scorecard/colleges_scorecard_earnings", ".", mirror$format)
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
earnings <- arrow::read_parquet(url)

# Filter by time horizon (LONG format — filter, don't use wide column names)
six_yr <- earnings |> filter(years_after_entry == 6)

# Filter for valid earnings (exclude -3 suppression code)
valid <- six_yr |> filter(!is.na(earnings_med), earnings_med != -3)

# Institution names/control are NOT in the earnings dataset.
# Join to inst_characteristics or IPEDS directory (filter years locally):
url <- paste0(mirror$root_url, "/", "scorecard/colleges_scorecard_inst_characteristics", ".", mirror$format)
inst <- arrow::read_parquet(url) |> filter(year == 2020)
valid <- valid |> left_join(
  inst |> select(unitid, inst_name, pred_degree_awarded_ipeds),
  by = "unitid"
)
```

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| "All graduates" claims | Scorecard covers Title IV recipients only, not all students | Note Title IV limitation prominently in any analysis |
| Wage comparison | Comparing to BLS wages or Census income uses different populations | Use for relative comparisons, not absolute claims; document population differences |
| Ignoring suppression | Many programs have no data due to privacy thresholds | Check suppression rates before analyzing; document coverage |
| Time lag ignored | Earnings reflect old cohorts (6-year = data from 7+ years ago) | Document data vintage and cohort years explicitly |
| Total borrowing assumption | Scorecard debt includes only federal loans, not private | State "federal loans only" when reporting debt figures |
| String codes from docs | Original Scorecard uses string labels; Portal uses integers | Verify actual data types in Portal parquet files; use integer codes |
| Wide-format variable names | Using `MD_EARN_WNE_P10` column name on Portal data | Portal uses LONG format — filter `years_after_entry` instead |
| Assuming null = suppressed | Earnings dataset uses `-3` for suppression, not null | Filter both: `is_not_null() & != -3` |
| Using uppercase names | Original Scorecard uses `MD_EARN_WNE_P6`; Portal uses `earnings_med` | Always use lowercase Portal names from actual data |

## Critical Limitation: Title IV Recipients Only

**The single most important caveat for all Scorecard analysis:**

Scorecard tracks ONLY students who received federal financial aid (Title IV):
- Pell Grants
- Federal student loans (Direct, Perkins, PLUS)
- Federal work-study

| Excluded Group | Impact |
|----------------|--------|
| Full-pay students | Often higher-income; different outcomes |
| Students with only state/institutional aid | Missing from data |
| International students | Not eligible for federal aid |
| Some graduate students | If they received no federal aid |

**Coverage varies dramatically by institution type:**

| Institution Type | Typical Title IV Coverage |
|-----------------|---------------------------|
| For-profit colleges | 80-90%+ |
| Community colleges | 60-80% |
| Public flagships | 50-70% |
| Selective private colleges | 30-50% |

**Data systematically overrepresents lower-income students** who are more likely to need federal aid.

## What Scorecard Data Does NOT Include

| Excluded | Why It Matters |
|----------|----------------|
| Non-Title IV students | Often higher-income; different outcomes |
| Self-employment income | 1099 income excluded from earnings |
| Students still in school | Not working = not in earnings data |
| Private student loans | Only federal loans tracked |
| Students who left the country | Lost to follow-up |

## Comparison: Scorecard vs IPEDS

| Aspect | College Scorecard | IPEDS |
|--------|------------------|-------|
| **Who's tracked** | Title IV aid recipients | First-time, full-time students |
| **Includes part-time** | Yes | No (for grad rates) |
| **Includes transfers-in** | Yes | No (tracked at origin) |
| **Outcome focus** | Earnings, debt, repayment | Completion, retention |
| **Data source** | NSLDS + IRS | Institution-reported |

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ipeds` | Institutional characteristics, enrollment, finance | Join on `unitid` for institution names, control type, enrollment context |
| `education-data-source-pseo` | Alternative post-college earnings (Census LEHD) | When broader population coverage needed (not limited to Title IV) |
| `education-data-source-fsa` | Federal student aid details | Deeper analysis of aid types and disbursements |
| `education-data-explorer` | Parent discovery skill | Routing questions to mirror dataset files |
| `education-data-query` | Data fetching | Downloading parquet/CSV files |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Earnings methodology | `./references/earnings-data.md` |
| Cohort definitions | `./references/earnings-data.md` |
| IRS data matching | `./references/earnings-data.md` |
| Earnings suppression | `./references/data-quality.md` |
| Debt metrics | `./references/debt-repayment.md` |
| Repayment rates | `./references/debt-repayment.md` |
| Default rates | `./references/debt-repayment.md` |
| NSLDS data | `./references/debt-repayment.md` |
| Completion methodology | `./references/completion-rates.md` |
| IPEDS comparison | `./references/completion-rates.md` |
| Title IV coverage | `./references/population-coverage.md` |
| Who is excluded | `./references/population-coverage.md` |
| Selection bias | `./references/population-coverage.md` |
| Variable names | `./references/variable-definitions.md` |
| Special values | `./references/variable-definitions.md` |
| Privacy suppression | `./references/data-quality.md` |
| Data limitations | `./references/data-quality.md` |
| Program-level data | `./references/field-of-study.md` |
| CIP codes | `./references/field-of-study.md` |
