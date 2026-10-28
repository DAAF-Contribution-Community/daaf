# NCCS Data for Higher Education Research

This reference explains how NCCS nonprofit data relates to higher education institutions and how to use it to supplement traditional education data sources like IPEDS.

## Contents

- [Private Nonprofit Colleges as 501(c)(3) Organizations](#private-nonprofit-colleges-as-501c3-organizations)
- [What NCCS Adds to Education Research](#what-nccs-adds-to-education-research)
- [Identifying Higher Education Institutions](#identifying-higher-education-institutions)
- [Linking NCCS to IPEDS](#linking-nccs-to-ipeds)
- [Key Research Applications](#key-research-applications)
- [Data Comparability Considerations](#data-comparability-considerations)
- [Example Queries](#example-queries)

---

## Private Nonprofit Colleges as 501(c)(3) Organizations

Private nonprofit colleges and universities operate as tax-exempt organizations under IRS Section 501(c)(3). This status:

- **Exempts** them from federal income tax
- **Allows** donors to deduct contributions
- **Requires** annual Form 990 filing (or 990-N for very small schools)

### Organizational Structure

Most private colleges are classified as:
- **IRS Subsection**: 501(c)(3)
- **Foundation Code**: 11 (School under 170(b)(1)(A)(ii)); other affiliates 15/16 or 17/21-24 (supporting organizations)
- **NTEE Codes**: B40-B50 (higher education)

### What's Included in NCCS

| Institution Type | In NCCS? | Notes |
|------------------|----------|-------|
| Private nonprofit 4-year colleges | Yes | Full 990 filers (most) |
| Private nonprofit universities | Yes | Often file consolidated 990 |
| Private 2-year colleges | Yes | Full 990 or 990-EZ |
| Public colleges/universities | No | Government entities, don't file 990 |
| For-profit colleges | No | File corporate tax returns, not 990 |
| Religious colleges | Mixed | Some file 990, some claim church exemption |

### Important Exclusions

**Public institutions** (state universities, community colleges) are not in NCCS because:
- They are government instrumentalities
- They don't file Form 990
- Use IPEDS exclusively for these institutions

**For-profit institutions** are not in NCCS because:
- They are taxable corporations
- They file Form 1120 (corporate tax return), not 990

---

## What NCCS Adds to Education Research

NCCS provides data not available through IPEDS:

### Financial Depth

| Data Element | NCCS (990) | IPEDS |
|--------------|------------|-------|
| Endowment details | Schedule D Part V | Summary totals only |
| Investment income breakdown | Part VIII | Limited |
| Fundraising expenses | Part IX column D | Not separated |
| Functional expense allocation | Full breakdown | Different categories |
| Executive compensation | Part VII, Schedule J | Aggregated only |
| Related party transactions | Schedule L | Not collected |
| Debt details | Part X | Limited |

### Governance Information

| Data Element | NCCS (990) | IPEDS |
|--------------|------------|-------|
| Board size | Part VI | Not collected |
| Board independence | Part VI | Not collected |
| Conflict of interest policy | Part VI | Not collected |
| CEO compensation review | Part VI | Not collected |
| Individual board members | Part VII | Not collected |
| Key employee compensation | Part VII | Not collected |

### Organizational Context

| Data Element | NCCS (990) | IPEDS |
|--------------|------------|-------|
| Related organizations | Schedule R | Limited |
| Mission statement | Part III | Not collected |
| Program descriptions | Part III | Different format |
| Affiliations | Schedule R | Not collected |

---

## Identifying Higher Education Institutions

### Using NTEE Codes

Filter NCCS data by education NTEE codes:

| Code | Description | Examples |
|------|-------------|----------|
| B40 | Higher Education Institutions (General) | Small colleges |
| B41 | Two-Year Colleges | Private community colleges |
| B42 | Undergraduate Colleges | Liberal arts colleges |
| B43 | Universities | Research universities |
| B50 | Graduate/Professional Schools | Law schools, medical schools |

### NTEEV2 Format

In the newer NTEEV2 format, higher education is tagged:

```
UNI - Universities (B40, B41, B42, B43, B50)
```

This makes filtering easier (full NCCS data only, not Portal):
```python
import polars as pl

# Filter for universities using NTEEV2 industry group
universities = df.filter(pl.col("nteev2").str.starts_with("UNI-"))
```

```r
library(dplyr)
library(stringr)

# Filter for universities using NTEEV2 industry group
universities <- df |> filter(str_starts(nteev2, "UNI-"))
```

### Using Foundation Code

Many colleges have foundation code 11 (School):
```python
import polars as pl

# Schools under 170(b)(1)(A)(ii) — full NCCS BMF data only (Unified BMF foundation_code;
# cast to integer because the dictionaries disagree on its storage: character in the Unified BMF,
# integer in the harmonized legacy BMF)
schools = bmf.filter(pl.col("foundation_code").cast(pl.Int64, strict=False) == 11)
```

```r
# Schools under 170(b)(1)(A)(ii) — full NCCS BMF data only (Unified BMF foundation_code;
# cast to integer because the dictionaries disagree on its storage: character in the Unified BMF,
# integer in the harmonized legacy BMF)
schools <- bmf |> filter(suppressWarnings(as.integer(foundation_code)) == 11L)
```

### Filtering Strategy

> **Note:** These filters apply to the **full NCCS Unified BMF** (no harmonized Core file has an NTEE column), not the Portal dataset. The Portal dataset (`nccs/colleges_nccs_all`) is already pre-filtered to higher education institutions matched to IPEDS UNITIDs — no NTEE filtering needed. The blocks below assume `bmf` was read with every column as a string (as in the BMF download example in `nonprofit-data.md`); with default type inference `subsection_code` can be read as a number (`3`), and the `"03"` comparison then fails or matches nothing.

Recommended approach for full NCCS data:
```python
import polars as pl

# Step 1: Filter by NTEE (Unified BMF standardized 3-character code)
higher_ed = bmf.filter(pl.col("ntee_code_clean").str.contains(r"^B4[0-9]|^B50"))

# Step 2: Verify 501(c)(3) status
higher_ed = higher_ed.filter(pl.col("subsection_code") == "03")

# Step 3: Exclude tiny organizations (likely support orgs, not colleges);
# income_amount is total income in dollars, stored as character
higher_ed = higher_ed.filter(pl.col("income_amount").cast(pl.Float64, strict=False) > 1_000_000)  # >$1M income
```

```r
library(dplyr)
library(stringr)

# Step 1: Filter by NTEE (Unified BMF standardized 3-character code)
higher_ed <- bmf |> filter(str_detect(ntee_code_clean, "^B4[0-9]|^B50"))

# Step 2: Verify 501(c)(3) status
higher_ed <- higher_ed |> filter(subsection_code == "03")

# Step 3: Exclude tiny organizations (likely support orgs, not colleges);
# income_amount is total income in dollars, stored as character
higher_ed <- higher_ed |> filter(suppressWarnings(as.numeric(income_amount)) > 1000000)
```

---

## Linking NCCS to IPEDS

### Identifier Mapping

| System | Identifier | Format |
|--------|------------|--------|
| NCCS/IRS | `ein` / `EIN2` (direct NCCS); `ein` (Portal) | `XX-XXXXXXX` (Unified BMF, harmonized Core); `EIN-XX-XXXXXXX` (`EIN2`: Unified BMF, Classic Core, Efile); 9-digit padded, e.g. `042104327` (Portal `ein`, Efile `ORG_EIN`, raw legacy files) |
| IPEDS | UNITID | 6-digit number (e.g., 110635) |

IPEDS Institutional Characteristics (Portal `ipeds/directory`, column `ein`) carries an institution-reported EIN, which is the first-choice EIN-UNITID link. It is not a validated crosswalk: system offices, foundations, and consolidated filers make many-to-one matches common, so validate before relying on it. Linking options:

### Linking Methods

**1. Portal Dataset (Pre-linked)**

The Portal dataset already includes `unitid` for IPEDS matching. No fuzzy matching needed:

```python
import polars as pl

# Portal data already has unitid
nccs = fetch_from_mirrors("nccs/colleges_nccs_all")
ipeds = fetch_from_mirrors("ipeds/colleges_ipeds_directory")

# Direct join on unitid and year
combined = nccs.join(
    ipeds.select(["unitid", "year", "inst_name", "sector"]),
    on=["unitid", "year"],
    how="left"
)
```

```r
library(arrow)
library(dplyr)

# fetch_from_mirrors() is a Python helper; in R, build URLs from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]

# Portal data already has unitid
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
nccs <- read_parquet(paste0(mirror$root_url, "/", "nccs/colleges_nccs_all", ".", mirror$format))
ipeds <- read_parquet(paste0(mirror$root_url, "/", "ipeds/colleges_ipeds_directory", ".", mirror$format))

# Direct join on unitid and year
combined <- nccs |>
  left_join(ipeds |> select(unitid, year, inst_name, sector),
            by = c("unitid", "year"))
```

**2. Full NCCS Data (Fuzzy Matching Required)**

When working with the full NCCS universe (outside Portal), start from the IPEDS `ein` column (institution-reported, not a validated crosswalk) and fall back to fuzzy name/location matching for unmatched or many-to-one cases:

```python
# Fuzzy matching on name and location (uses rapidfuzz or fuzzywuzzy)
from rapidfuzz import fuzz

# This is inherently row-level work; consider converting to pandas for iterrows()
# or use Polars with map_elements for small datasets
```

```r
# Fuzzy matching on name (base R). stringdist/fuzzyjoin offer richer string
# distances but are NOT installed in this environment — agrepl()/adist() are
# always available in base R.
# agrepl: approximate matching via edit distance; adist: edit-distance matrix
candidates <- ipeds_names[agrepl(nccs_name, ipeds_names, max.distance = 0.15)]
distances <- adist(nccs_name, candidates)
best_match <- candidates[which.min(distances)]
```

**3. Address Matching**

Use geocoded addresses to narrow matches:
```python
import polars as pl

# Match on city + state first, then name (full NCCS data)
# ipeds_df: Portal IPEDS directory (columns city, state_abbr);
# nccs_city / nccs_state: Unified BMF org_addr_city / org_addr_state (two-letter abbreviation)
same_location = ipeds_df.filter(
    (pl.col("city") == nccs_city) &
    (pl.col("state_abbr") == nccs_state)
)
```

```r
# Match on city + state first, then name (full NCCS data)
# ipeds_df: Portal IPEDS directory (columns city, state_abbr);
# nccs_city / nccs_state: Unified BMF org_addr_city / org_addr_state (two-letter abbreviation)
same_location <- ipeds_df |> filter(city == nccs_city, state_abbr == nccs_state)
```

**4. Published Crosswalks**

Some researchers have created EIN-UNITID crosswalks:
- Check data repositories (ICPSR, Dataverse)
- Academic publications with supplementary data
- ProPublica Nonprofit Explorer (sometimes includes IPEDS match)

### Linking Challenges

| Challenge | Description | Mitigation |
|-----------|-------------|------------|
| **Name variations** | "University of X" vs "X University" | Fuzzy matching, standardization |
| **Multiple EINs** | University systems with separate EINs | Identify parent organization |
| **Consolidated filings** | One 990 for entire system | Map to multiple UNITIDs |
| **Support organizations** | Foundations, athletics, etc. | Filter by NTEE, revenue size |
| **Name changes** | Mergers, rebranding | Check historical names |

### Related Organizations

Many universities have multiple EINs for:
- Main institution
- Foundation/development office
- Hospital/medical center
- Athletic association
- Alumni association

Schedule R of Form 990 lists related organizations.

---

## Key Research Applications

### 1. Executive Compensation Studies

NCCS provides individual-level compensation data:

```python
# Get compensation for college presidents
# Efile Part VII Section A table (F9-P07-T01-COMPENSATION); Schedule J Part II is SJ-P02-T01-COMPENSATION-DTK
import polars as pl

compensation = efile_partVII.filter(
    pl.col("F9_07_COMP_DTK_TITLE").str.contains("(?i)President|Chancellor")
)
```

```r
# Get compensation for college presidents
# Efile Part VII Section A table (F9-P07-T01-COMPENSATION); Schedule J Part II is SJ-P02-T01-COMPENSATION-DTK
compensation <- efile_partVII |>
  filter(str_detect(F9_07_COMP_DTK_TITLE, regex("President|Chancellor", ignore_case = TRUE)))
```

**Research questions**:
- How does president pay vary by institution size?
- Is there a relationship between endowment size and compensation?
- How has executive pay changed over time?

### 2. Endowment Analysis

Schedule D provides endowment details not in IPEDS:

```python
# Endowment data from Schedule D Part V, current-year column (A)
# (Efile table SD-P05-T00-ENDOWMENT; names from the Efile data dictionary)
endowment_cols = [
    'SD_05_ENDOW_BALANCE_BOY_CY',   # Beginning of year balance (line 1a)
    'SD_05_ENDOW_CONTR_CY',         # Contributions (line 1b)
    'SD_05_ENDOW_INVEST_CY',        # Investment earnings or losses (line 1c)
    'SD_05_ENDOW_GRANT_CY',         # Grants or scholarships (line 1d)
    'SD_05_ENDOW_EXP_OTH_CY',       # Other expenditures (line 1e)
    'SD_05_ENDOW_EXP_ADMIN_CY',     # Administrative expenses (line 1f)
    'SD_05_ENDOW_BALANCE_EOY_CY'    # End of year balance (line 1g)
]
```

```r
# Endowment data from Schedule D Part V, current-year column (A)
# (Efile table SD-P05-T00-ENDOWMENT; names from the Efile data dictionary)
endowment_cols <- c(
  "SD_05_ENDOW_BALANCE_BOY_CY",   # Beginning of year balance (line 1a)
  "SD_05_ENDOW_CONTR_CY",         # Contributions (line 1b)
  "SD_05_ENDOW_INVEST_CY",        # Investment earnings or losses (line 1c)
  "SD_05_ENDOW_GRANT_CY",         # Grants or scholarships (line 1d)
  "SD_05_ENDOW_EXP_OTH_CY",       # Other expenditures (line 1e)
  "SD_05_ENDOW_EXP_ADMIN_CY",     # Administrative expenses (line 1f)
  "SD_05_ENDOW_BALANCE_EOY_CY"    # End of year balance (line 1g)
)
```

The same table carries Part V columns (B) to (E) under suffixes `_M1` to `_M4` (e.g. `SD_05_ENDOW_BALANCE_EOY_CY_M1` = line 1g, column B, per the Efile data dictionary; present in the 2024 file header).

**Research questions**:
- What is the endowment spending rate?
- How much comes from new gifts vs. investment returns?
- How do administrative costs compare across institutions?

### 3. Governance Research

NCCS uniquely provides governance data:

```python
# Governance indicators from Part VI (Efile table F9-P06-T00-GOVERNANCE)
governance_vars = [
    'F9_06_GVRN_NUM_VOTING_MEMB',        # Number of voting governing body members (line 1a)
    'F9_06_GVRN_NUM_VOTING_MEMB_IND',    # Number of independent voting members (line 1b)
    'F9_06_GVRN_DTK_FAMBIZ_RELATION_X',  # Family or business relationship among officers etc. (line 2)
    'F9_06_POLICY_COI_X',                # Conflict of interest policy (line 12a)
    'F9_06_POLICY_WHSTLBLWR_X',          # Whistleblower policy (line 13)
    'F9_06_POLICY_COMP_PROCESS_CEO_X'    # Compensation process for CEO (line 15a)
]
```

```r
# Governance indicators from Part VI (Efile table F9-P06-T00-GOVERNANCE)
governance_vars <- c(
  "F9_06_GVRN_NUM_VOTING_MEMB",        # Number of voting governing body members (line 1a)
  "F9_06_GVRN_NUM_VOTING_MEMB_IND",    # Number of independent voting members (line 1b)
  "F9_06_GVRN_DTK_FAMBIZ_RELATION_X",  # Family or business relationship among officers etc. (line 2)
  "F9_06_POLICY_COI_X",                # Conflict of interest policy (line 12a)
  "F9_06_POLICY_WHSTLBLWR_X",          # Whistleblower policy (line 13)
  "F9_06_POLICY_COMP_PROCESS_CEO_X"    # Compensation process for CEO (line 15a)
)
```

**Research questions**:
- Does board composition affect institutional outcomes?
- Do governance practices correlate with financial health?
- How do governance structures vary by institution type?

### 4. Financial Efficiency Studies

Functional expense allocation enables efficiency analysis:

```python
import polars as pl

# Calculate fundraising efficiency
# df: Efile F9-P08-T00-REVENUE joined to F9-P09-T00-EXPENSES on URL (the unique filing key)
df = df.with_columns(
    (pl.col("F9_09_EXP_TOT_FUNDR").cast(pl.Float64, strict=False)
     / pl.col("F9_08_REV_CONTR_TOT").cast(pl.Float64, strict=False)).alias("fundraising_ratio"),
    # Program expense ratio
    (pl.col("F9_09_EXP_TOT_PROG").cast(pl.Float64, strict=False)
     / pl.col("F9_09_EXP_TOT_TOT").cast(pl.Float64, strict=False)).alias("program_ratio"),
)
```

```r
library(dplyr)

# Calculate fundraising efficiency
# df: Efile F9-P08-T00-REVENUE joined to F9-P09-T00-EXPENSES on URL (the unique filing key)
df <- df |>
  mutate(
    fundraising_ratio = as.numeric(F9_09_EXP_TOT_FUNDR) / as.numeric(F9_08_REV_CONTR_TOT),
    program_ratio = as.numeric(F9_09_EXP_TOT_PROG) / as.numeric(F9_09_EXP_TOT_TOT)
  )
```

Zero contributions or zero total expenses give an infinite ratio (`inf` / `Inf`); filter or guard the denominators before summarizing. Efile tables, not Classic Core, are used here because the Classic dictionary (`CORE-HRMN_dd.csv`) has no `F9_09_EXP_TOT_PROG` or `F9_09_EXP_TOT_MGMT`, and lists `F9_09_EXP_TOT_FUNDR` only for 501CE PZ files.

### 5. Related Party Analysis

Schedule L and R reveal related party transactions:

**Research questions**:
- What is the relationship between college and affiliated foundation?
- How are hospital revenues reflected in university finances?
- Do athletics generate net revenue or costs?

---

## Data Comparability Considerations

### NCCS vs. IPEDS Financial Differences

| Item | Form 990 | IPEDS |
|------|----------|-------|
| **Accounting basis** | Tax reporting (modified cash or accrual) | GAAP, GASB, or FASB |
| **Consolidation** | Varies | Full consolidation |
| **Fiscal year** | Tax year (may differ) | Institution fiscal year |
| **Revenue categories** | IRS-defined | Education-specific |
| **Expense categories** | Functional (program/admin/fundraising) | Natural + functional |

### Common Discrepancies

**Total revenue differences**:
- IPEDS includes unrealized investment gains; 990 may not
- IPEDS may consolidate hospital; 990 may be separate
- Timing differences if fiscal years don't align

**Expense differences**:
- 990 requires functional allocation (program/admin/fundraising)
- IPEDS uses education-specific categories (instruction, research, etc.)
- Depreciation treatment may differ

### Reconciliation Tips

1. **Check fiscal year ends**: Ensure comparing same time periods
2. **Identify consolidation scope**: Review Schedule R for related orgs
3. **Note accounting method**: Part XII indicates cash vs. accrual
4. **Compare to audited financials**: Often available on institution websites

---

## Example Queries

### Using Education Data Portal

**Get NCCS Data for Higher Education:**

```python
import polars as pl

# Load NCCS data via unified mirror system
DATASET_PATH = "nccs/colleges_nccs_all"
nccs = fetch_from_mirrors(DATASET_PATH)

# Filter to California (FIPS = 6) - note: integer codes!
ca_institutions = nccs.filter(pl.col("fips") == 6)

# Get latest year data
latest = nccs.filter(pl.col("year") == nccs["year"].max())

# Financial summary
print(f"Total Revenue: ${latest['revenue_total'].mean():,.0f}")
print(f"Total Assets: ${latest['total_assets_eoy'].mean():,.0f}")
```

```r
library(arrow)
library(dplyr)

# Load NCCS data via unified mirror system
# fetch_from_mirrors() is a Python helper; in R, build the URL from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
DATASET_PATH <- "nccs/colleges_nccs_all"
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
nccs <- read_parquet(paste0(mirror$root_url, "/", DATASET_PATH, ".", mirror$format))

# Filter to California (FIPS = 6) - note: integer codes!
ca_institutions <- nccs |> filter(fips == 6)

# Get latest year data
latest <- nccs |> filter(year == max(year))

# Financial summary
cat(sprintf("Total Revenue: $%s\n", format(mean(latest$revenue_total, na.rm = TRUE), big.mark = ",")))
cat(sprintf("Total Assets: $%s\n", format(mean(latest$total_assets_eoy, na.rm = TRUE), big.mark = ",")))
```

**Join with IPEDS:**

```python
import polars as pl

# NCCS data includes unitid for IPEDS matching
NCCS_PATH = "nccs/colleges_nccs_all"
nccs = fetch_from_mirrors(NCCS_PATH)

# IPEDS directory for institution names
IPEDS_PATH = "ipeds/colleges_ipeds_directory"
ipeds = fetch_from_mirrors(IPEDS_PATH)

# Join on unitid and year
combined = nccs.join(
    ipeds.select(["unitid", "year", "inst_name", "sector"]),
    on=["unitid", "year"],
    how="left"
)
```

```r
library(arrow)
library(dplyr)

# fetch_from_mirrors() is a Python helper; in R, build URLs from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]

# NCCS data includes unitid for IPEDS matching
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
NCCS_PATH <- "nccs/colleges_nccs_all"
nccs <- read_parquet(paste0(mirror$root_url, "/", NCCS_PATH, ".", mirror$format))

# IPEDS directory for institution names
IPEDS_PATH <- "ipeds/colleges_ipeds_directory"
ipeds <- read_parquet(paste0(mirror$root_url, "/", IPEDS_PATH, ".", mirror$format))

# Join on unitid and year
combined <- nccs |>
  left_join(ipeds |> select(unitid, year, inst_name, sector),
            by = c("unitid", "year"))
```

### Using Direct NCCS Data

> **Note:** These examples use full NCCS data downloaded directly (not the Portal mirror). Column names differ by product: the Unified BMF uses lowercase names (`ein`, `org_name_display`, `org_addr_state`, `subsection_code`, `ntee_code_clean`, `income_amount`, `asset_amount`; amounts are stored as character) plus an uppercase `EIN2` alias, the Classic-format harmonized Core files (`CORE-…-HRMN-V1.csv`) use uppercase `F9_*` names keyed by `EIN2`, and the Efile v2_1 tables use `F9_*` / `SD_*` / `SJ_*` names, also with `EIN2` (NCCS Unified BMF and Core HRMN data dictionaries; Efile table headers). NCCS's EIN format convention lists `EIN2` (`EIN-XX-XXXXXXX`, e.g. `EIN-04-2104327`) as the key of the "harmonized CORE marts, Unified BMF, NODC `efile_v2_1`", so these three join on `EIN2` directly. The Portal `ein` is the 9-digit padded form and needs reformatting before it can join them. For Portal data, use the lowercase Portal variable names shown in the "Using Education Data Portal" section above.

**Find All Private Universities in a State:**

```python
import polars as pl

# Load BMF (all columns as strings: codes such as subsection_code "03" keep their leading zero)
bmf = pl.read_csv("bmf_unified.csv", infer_schema_length=0)

# Filter to California private universities
ca_universities = bmf.filter(
    (pl.col("org_addr_state") == "CA") &
    (pl.col("subsection_code") == "03") &  # 501(c)(3)
    (pl.col("ntee_code_clean").str.contains(r"^B4[0-3]")) &
    (pl.col("income_amount").cast(pl.Float64, strict=False) > 1_000_000)  # Total income > $1M
)

print(f"Found {ca_universities.height} private universities in California")
```

```r
library(dplyr)
library(stringr)

# Load BMF (all columns as character: codes such as subsection_code "03" keep their leading zero)
bmf <- read.csv("bmf_unified.csv", colClasses = "character")

# Filter to California private universities
ca_universities <- bmf |>
  filter(
    org_addr_state == "CA",
    subsection_code == "03",
    str_detect(ntee_code_clean, "^B4[0-3]"),
    suppressWarnings(as.numeric(income_amount)) > 1000000  # Total income > $1M
  )

cat(sprintf("Found %d private universities in California\n", nrow(ca_universities)))
```

**Get Financial Data for a Specific Institution:**

```python
# Find Stanford University
stanford = bmf.filter(pl.col("org_name_display").str.contains("(?i)stanford university"))
stanford_ein2 = stanford["EIN2"][0]

# Load Core data (harmonized file: uppercase F9_* names keyed by EIN2)
core = pl.read_csv("CORE-2021-501C3-CHARITIES-PC-HRMN-V1.csv", infer_schema_length=0)
# ASSUMES: BMF EIN2 and Core EIN2 share the EIN-XX-XXXXXXX format (NCCS EIN format convention; see the note above)
stanford_990 = core.filter(pl.col("EIN2") == stanford_ein2)

print(f"Total Revenue: ${float(stanford_990['F9_08_REV_TOT_TOT'][0]):,.0f}")
print(f"Total Assets: ${float(stanford_990['F9_10_ASSET_TOT_EOY'][0]):,.0f}")
```

```r
# Find Stanford University
stanford <- bmf |> filter(grepl("stanford university", org_name_display, ignore.case = TRUE))
stanford_ein2 <- stanford$EIN2[1]

# Load Core data (harmonized file: uppercase F9_* names keyed by EIN2)
core <- read.csv("CORE-2021-501C3-CHARITIES-PC-HRMN-V1.csv", colClasses = "character")
# ASSUMES: BMF EIN2 and Core EIN2 share the EIN-XX-XXXXXXX format (NCCS EIN format convention; see the note above)
stanford_990 <- core |> filter(EIN2 == stanford_ein2)

cat(sprintf("Total Revenue: $%s\n", format(as.numeric(stanford_990$F9_08_REV_TOT_TOT[1]), big.mark = ",", scientific = FALSE)))
cat(sprintf("Total Assets: $%s\n", format(as.numeric(stanford_990$F9_10_ASSET_TOT_EOY[1]), big.mark = ",", scientific = FALSE)))
```

**Compare Endowments Across Institutions:**

```python
# Load Efile Schedule D Part V table (one file per year: SD-P05-T00-ENDOWMENT-{YEAR}.CSV)
sched_d = pl.read_csv("SD-P05-T00-ENDOWMENT-2021.CSV", infer_schema_length=0)

# Join with BMF for institution names (Efile and Unified BMF both carry EIN2, EIN-XX-XXXXXXX)
endowments = sched_d.join(
    bmf.select(["EIN2", "org_name_display", "org_addr_state"]),
    on="EIN2"
)

# Filter to higher ed
endowments = endowments.filter(pl.col("EIN2").is_in(ca_universities["EIN2"]))

# Sort by end-of-year endowment balance (Schedule D Part V line 1g, current year)
endowments = endowments.sort(
    pl.col("SD_05_ENDOW_BALANCE_EOY_CY").cast(pl.Float64, strict=False), descending=True
)
```

```r
library(dplyr)

# Load Efile Schedule D Part V table (one file per year: SD-P05-T00-ENDOWMENT-{YEAR}.CSV)
sched_d <- read.csv("SD-P05-T00-ENDOWMENT-2021.CSV", colClasses = "character")

# Join with BMF for institution names (Efile and Unified BMF both carry EIN2, EIN-XX-XXXXXXX)
# (inner_join matches the Python twin: Polars .join() defaults to how="inner")
endowments <- sched_d |>
  inner_join(bmf |> select(EIN2, org_name_display, org_addr_state), by = "EIN2")

# Filter to higher ed
endowments <- endowments |> filter(EIN2 %in% ca_universities$EIN2)

# Sort by end-of-year endowment balance (Schedule D Part V line 1g, current year)
endowments <- endowments |> arrange(desc(as.numeric(SD_05_ENDOW_BALANCE_EOY_CY)))
```

The yearly files are linked from the NCCS Efile catalog (`https://nccs-efile.s3.us-east-1.amazonaws.com/public/efile_v2_1/SD-P05-T00-ENDOWMENT-2021.CSV`). The Efile tables also carry the filer's name (`ORG_NAME_L1`), so the BMF join is needed only for BMF fields such as state or NTEE code.

**Analyze Executive Compensation:**

```python
# Load Schedule J Part II compensation table (one row per listed person: SJ-P02-T01-COMPENSATION-DTK-{YEAR}.CSV)
sched_j = pl.read_csv("SJ-P02-T01-COMPENSATION-DTK-2021.CSV", infer_schema_length=0)

# Filter to presidents/chancellors at universities (EIN2 on both Efile and Unified BMF)
presidents = sched_j.filter(
    (pl.col("SJ_02_COMP_DTK_TITLE").str.contains("(?i)President|Chancellor")) &
    (pl.col("EIN2").is_in(higher_ed["EIN2"]))
)

# Total compensation from the filing organization: Schedule J Part II column (E),
# the total of base (B)(i), bonus (B)(ii), other (B)(iii), deferred (C) and nontaxable benefits (D)
presidents = presidents.with_columns(
    pl.col("SJ_02_COMP_DTK_TOT_ORG").cast(pl.Float64, strict=False).alias("total_comp_org")
)

# Summary statistics
print(presidents["total_comp_org"].describe())
```

```r
library(dplyr)
library(stringr)

# Load Schedule J Part II compensation table (one row per listed person: SJ-P02-T01-COMPENSATION-DTK-{YEAR}.CSV)
sched_j <- read.csv("SJ-P02-T01-COMPENSATION-DTK-2021.CSV", colClasses = "character")

# Filter to presidents/chancellors at universities (EIN2 on both Efile and Unified BMF)
presidents <- sched_j |>
  filter(
    str_detect(SJ_02_COMP_DTK_TITLE, regex("President|Chancellor", ignore_case = TRUE)),
    EIN2 %in% higher_ed$EIN2
  )

# Total compensation from the filing organization: Schedule J Part II column (E),
# the total of base (B)(i), bonus (B)(ii), other (B)(iii), deferred (C) and nontaxable benefits (D)
presidents <- presidents |>
  mutate(total_comp_org = as.numeric(SJ_02_COMP_DTK_TOT_ORG))

# Summary statistics
summary(presidents$total_comp_org)
```

Schedule J, not Part VII, holds the compensation components (base, bonus, other, deferred, nontaxable benefits: `SJ_02_COMP_DTK_BASE_ORG`, `_BONUS_ORG`, `_OTH_ORG`, `_DEFERRED_ORG`, `_BENFIT_ORG` (sic), total `_TOT_ORG`); Part VII Section A has only reportable compensation from the organization and from related organizations plus other compensation (`F9_07_COMP_DTK_COMP_ORG`, `_COMP_RLTD`, `_COMP_OTH`). Only some filers attach Schedule J, and the `_ORG` columns exclude compensation from related organizations (the `_RLTD` columns hold it).

---

## Best Practices

### For Linking to IPEDS

1. Start with known institutions to validate matching approach
2. Use multiple matching criteria (name + location + size)
3. Manually verify matches for key institutions
4. Document matching methodology and success rate
5. Note unmatched institutions and potential reasons

### For Financial Analysis

1. Always check fiscal year alignment
2. Verify consolidation scope using Schedule R
3. Compare to audited financials when available
4. Account for form version changes (pre-2008 vs. post-2008)
5. Use multiple years to identify outliers/errors

### For Governance Research

1. The 2008 redesign added Part VI (independent board members, whistleblower and document-retention policies, compensation-review process); the 2007 form already asked board size, family/business relationships, and whether a written conflict-of-interest policy existed.
2. Board composition data is self-reported
3. Policy existence doesn't indicate implementation quality
4. Compare across similar institution types
