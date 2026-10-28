# NCCS Nonprofit Data Sources

The National Center for Charitable Statistics maintains multiple datasets derived from IRS administrative records. This reference covers what data is available and how to access it.

## Contents

- [Business Master File (BMF)](#business-master-file-bmf)
- [NCCS Core Data Series](#nccs-core-data-series)
- [IRS 990 Efile Database](#irs-990-efile-database)
- [Form 990-N ePostcard](#form-990-n-epostcard)
- [Publication 78](#publication-78)
- [SOI Microdata](#soi-microdata)
- [Data Access Methods](#data-access-methods)

---

## Business Master File (BMF)

The BMF is the universe of all organizations granted tax-exempt status by the IRS. It serves as the primary sampling framework for nonprofit research.

### Overview

| Attribute | Value |
|-----------|-------|
| **Coverage** | 3,698,197 unique EINs, 1989–2026 (NCCS Unified BMF build of 2026-09-15) |
| **Update frequency** | Monthly from IRS |
| **Time span** | Historical coverage varies by BMF product; verify the current BMF catalog before use |
| **File size** | ~3.1 GB (Unified BMF; geocoded variant ~3.6 GB) |

### Key Variables

| Variable | Description |
|----------|-------------|
| `ein` / `EIN2` | Employer Identification Number formatted as XX-XXXXXXX / legacy-compatibility alias (EIN-XX-XXXXXXX) |
| `org_name_display` / `org_name_raw` | Title-cased display name / original name as in the source file |
| `org_addr_street`, `org_addr_city`, `org_addr_state`, `org_addr_zip` | Location information (cleaned; `*_raw` columns keep the source values) |
| `ntee_code_raw` / `ntee_code_clean` | Original NTEE code from the source file (1-4 characters) / standardized 3-character code (Unified BMF) |
| `nteev2` | NCCS NTEEv2 code (SUBSECTOR-CODE-TYPE) |
| `subsection_code` | IRS subsection code (03 = 501(c)(3), etc.) |
| `foundation_code` | Foundation status code (00-99) per IRS determination |
| `ruling_date` | Date of IRS ruling granting exempt status (missing assigned 1900-01-01) |
| `accounting_period` | Month the accounting period ends (01-12) |
| `income_amount` | Total income in dollars (can be negative; stored as character) |
| `asset_amount` | Total assets in dollars, most recent return (stored as character) |

(Source: NCCS Unified BMF data dictionary, fetched 2026-10-28.)

> Older NCCS BMF files used NTEE_IRS (official) and NTEE_NCCS (NCCS corrections; a supplement, per NCCS).

> Uppercase BMF names from older NCCS BMF files and the raw IRS file (`EIN`, `NAME`, `STATE`, `SUBSECCD`, `FNDNCD`, `NTEECC`, `INCOME_AMT`, `ASSET_AMT`) do not appear in the Unified BMF data dictionary; the only uppercase Unified BMF column is `EIN2`. The legacy-to-raw renames are in NCCS's legacy BMF crosswalk (`XWALK-BMF-V2.0.csv`, nccs-data-bmf repository), and the raw-to-Unified renames are in the NCCS BMF transform reference; `variable-definitions.md` (Business Master File Variables) lists both.

### NCCS Unified BMF Enhancements

The NCCS Unified BMF adds:

- **Geocoded variant**: geo_lat/geo_lon plus geocoder county and metro-area names; canonical county FIPS and metro (CBSA) codes come from optional crosswalk join layers (TIGER 2023 / OMB 2023)
- **Vintage tracking**: first_vintage_ym / last_vintage_ym and first_year_in_bmf / last_year_in_bmf (BMF vintages, not Core)
- **Historical record**: stacks current monthly IRS BMF files with legacy NCCS BMF vintages (1989 onward), so organizations no longer on the current IRS BMF remain

### Foundation Codes (`foundation_code`; legacy `FNDNCD`)

IRS EO BMF codes (IRS `eo_info.pdf`, Wayback capture 2022-12-18):

| Code | Description |
|------|-------------|
| 00 | All organizations except 501(c)(3) |
| 02 | Private operating foundation exempt from excise tax on investment income |
| 03 | Private operating foundation (other) |
| 04 | Private non-operating foundation |
| 09 | Suspense |
| 10 | Church 170(b)(1)(A)(i) |
| 11 | School 170(b)(1)(A)(ii) |
| 12 | Hospital or medical research organization 170(b)(1)(A)(iii) |
| 13 | Organization operated for benefit of a college or university owned/operated by a governmental unit 170(b)(1)(A)(iv) |
| 14 | Governmental unit 170(b)(1)(A)(v) |
| 15 | Publicly supported (government/general public) 170(b)(1)(A)(vi) |
| 16 | 509(a)(2) organization |
| 17 | 509(a)(3) supporting organization |
| 18 | Public safety testing 509(a)(4) |
| 21-24 | 509(a)(3) Type I, II, III functionally integrated, III non-functionally integrated |

**For higher education**: `foundation_code` = 11 (school); other affiliates 15/16 or 17/21-24 (supporting organizations). Code 21 is a 509(a)(3) Type I supporting organization, not a publicly supported charity.

### Download

**Via Education Data Portal mirror (recommended for education research):**

```python
import polars as pl

# Download NCCS 990 data from Portal mirror
DATASET_PATH = "nccs/colleges_nccs_all"
nccs = fetch_from_mirrors(DATASET_PATH)

# Data is pre-filtered to higher education institutions matched to IPEDS
# Variables are lowercase (e.g., fips, unitid, contributions_total)
# 161 columns, 1993-2016, ~30K institution-year rows
```

```r
library(arrow)
library(dplyr)

# Download NCCS 990 data from Portal mirror
# fetch_from_mirrors() is a Python helper; in R, build the URL from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
DATASET_PATH <- "nccs/colleges_nccs_all"
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
nccs <- read_parquet(paste0(mirror$root_url, "/", DATASET_PATH, ".", mirror$format))

# Data is pre-filtered to higher education institutions matched to IPEDS
# Variables are lowercase (e.g., fips, unitid, contributions_total)
# 161 columns, 1993-2016, ~30K institution-year rows
```

**Direct download from NCCS (for BMF, Core, Efile — outside Portal):**

```python
import polars as pl

# BMF universe file (large — ~3.1 GB); all columns read as strings so codes keep leading zeros
url = "https://nccsdata.s3.us-east-1.amazonaws.com/unified/bmf/bmf_unified.csv"
bmf = pl.read_csv(url, infer_schema_length=0)

# Filter to higher education by NTEE code (NOT available in Portal data);
# ntee_code_clean is the Unified BMF's standardized 3-character NTEE code
higher_ed = bmf.filter(pl.col("ntee_code_clean").str.starts_with("B4"))
```

```r
library(dplyr)
library(stringr)

# BMF universe file (large — ~3.1 GB); all columns read as character so codes keep leading zeros
url <- "https://nccsdata.s3.us-east-1.amazonaws.com/unified/bmf/bmf_unified.csv"
bmf <- read.csv(url, colClasses = "character")

# Filter to higher education by NTEE code (NOT available in Portal data);
# ntee_code_clean is the Unified BMF's standardized 3-character NTEE code
higher_ed <- bmf |> filter(str_starts(ntee_code_clean, "B4"))
```

> **Note:** The Portal mirror dataset contains NCCS Form 990 data matched to IPEDS institutions (~2,600 institutions). It does NOT include NTEE codes, BMF attributes, or the full nonprofit universe. For the full NCCS universe, NTEE-based filtering, or non-education nonprofits, download directly from NCCS.

---

## NCCS Core Data Series

The Core Data Series provides standardized financial information from Form 990 filings spanning 30+ years.

### Overview

| Attribute | Value |
|-----------|-------|
| **Coverage** | Form 990 and 990-EZ records; exact inclusion depends on the selected Core product |
| **Merged Core** | 1987-2024 |
| **SOI-current** | 2012-2024 |
| **Release status** | As verified on 2026-10-19, the Core catalog lists a merged panel (1987-2024), SOI-current (2012-2024), and legacy (1987-2011) harmonized tiers plus a 'Classic NCCS format'; recent tax years are in progress as the IRS continues to release returns |
| **Variables** | Vary by product and file; verify the current catalog documentation |

### Data File Types

| Type | Form Scope | Description | Variable Count |
|------|------------|-------------|----------------|
| **PC** | Full 990 only | Larger organizations, more detail | 251 (990, 2024) |
| **PZ** | 990 + 990-EZ | Broader coverage, fewer variables | 76 (990-EZ) / 53 shared (990 combined) |
| **PF** | 990-PF | Private foundations only | 187 (990-PF) |

Variable counts per NCCS Core catalog SOI-current tier.

### Organizational Scope

| Scope | Description |
|-------|-------------|
| **501C3-CHARITIES** | 501(c)(3) public charities (donations tax-deductible) |
| **501CE-NONPROFIT** | All other 501(c) types (c)(4), (c)(6), etc. |
| **PRIVATE-FOUNDATIONS** | 501(c)(3) private foundations (990-PF filers) |

### Key Financial Variables: Legacy Names and Current Columns

> **Legacy names.** The uppercase names in the first column are pre-2026 NCCS Core names. No current NCCS file uses them as column names: they survive only in the `source_var` column of the harmonized Core legacy-tier data dictionaries. The current products use the harmonized Core panel names (lowercase) or, in the Classic NCCS format (`CORE-…-HRMN-V1.csv`, dictionary `CORE-HRMN_dd.csv`) and Efile tables, `F9_PP_*` names. The Core catalog says column mapping tables are "rolling out"; until one is published, use the current-name columns below. **Basis** (for the harmonized name): **SV** = the legacy name is listed in that column's `source_var`; **LOC** = matched by the Form 990 line the dictionary gives; **DESC** = matched by description only (inference); **NF** = no current column found. Classic and Efile names are matched by Form 990 line. (Sources: NCCS harmonized Core data dictionaries, legacy tier 2000 and 2010, merged tier 2010 and 2016, SOI-current tier 2016 and 2021; `CORE-HRMN_dd.csv`; Efile data dictionary; all fetched 2026-10-28.) Full mapping: `variable-definitions.md`.

**Common to PC and PZ files:**

| Legacy name | Description | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|-----------------|-----------------|-------|
| `TOTREV` | Total revenue | `total_revenue` | `F9_08_REV_TOT_TOT` | SV |
| `TOTREV2` | Total revenue (alternative calculation) | `total_revenue` (one column for both) | `F9_08_REV_TOT_TOT` | SV |
| `EXPS` | Total expenses | `total_expenses` | `F9_09_EXP_TOT_TOT` | SV |
| `TOTASS` | Total assets (end of year) | `total_assets_eoy` | `F9_10_ASSET_TOT_EOY` | LOC |
| `TOTLIAB` | Total liabilities (end of year) | `total_liabilities_eoy` | `F9_10_LIAB_TOT_EOY` | LOC |
| `NETASS` | Net assets (assets - liabilities) | `total_net_assets_eoy` | `F9_10_NAFB_TOT_EOY` | LOC |
| `CONT` | Contributions and grants | `total_contributions` | `F9_08_REV_CONTR_TOT` | SV (the legacy-tier row's description cites Schedule A line 15(e); check before relying on it) |
| `PROGREV` | Program service revenue | `program_service_revenue` | `F9_08_REV_PROG_TOT_TOT` | SV |
| `DUES` | Membership dues | `membership_dues_assessments_sec170` (legacy and merged tiers only) | — | SV; not in Core PC files from about 2011 (moved into program service revenue on the 2008 form) |
| `INVINC` | Investment income | `investment_income` | `F9_08_REV_OTH_INVEST_INCOME_TOT` | SV |
| `OTHINC` | Other income | `other_revenue_total_11e` | `F9_08_REV_MISC_TOT_TOT` | SV |
| `GRSRCPTS` | Gross receipts | none (the similar `gross_receipts_total` is sourced from `GRREC`) | `F9_00_GRO_RCPT` (Classic PZ files only) | NF |
| `FUNDSBAL` | Fund balance (beginning of year) | none | — | NF: not in the legacy dictionaries checked; the similar `FUNDBAL` maps to `total_net_assets_eoy`, an end-of-year value, so do not use it as a beginning-of-year balance |

**Full Form 990 (PC) detail:**

| Legacy name | Description | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|-----------------|-----------------|-------|
| `COMPENS` | Compensation of officers, directors, etc. | `compensation_current_officers` | `F9_09_EXP_COMP_DTK_TOT` | SV |
| `OTHSAL` | Other salaries and wages | `other_salaries_wages` | `F9_09_EXP_OTH_SAL_WAGE_TOT` | SV |
| `PAIDSRV` | Professional fees | no single total; SOI-current `fees_for_services_*` by type | Efile `F9_09_EXP_FEE_SVC_*_TOT` (lines 11a-11g) | DESC |
| `OCCUP` | Occupancy expenses | `occupancy` (SOI-current tier) | `F9_09_EXP_OCCUPANCY_TOT` | LOC |
| `TRAVEL` | Travel expenses | `travel` (SOI-current tier) | `F9_09_EXP_TRAVEL_TOT` | LOC |
| `CONF` | Conferences and meetings | `conferences_conventions_meetings` (SOI-current tier) | `F9_09_EXP_CONF_MEETING_TOT` | DESC |
| `INTEREST` | Interest expense | `interest_expense` (SOI-current tier; the legacy-tier column of that name holds a different field, interest on savings and temporary cash investments) | `F9_09_EXP_INT_TOT` | LOC |
| `DEPREC` | Depreciation and depletion | `depreciation_depletion` (SOI-current tier) | `F9_09_EXP_DEPREC_TOT` | LOC |
| `GRANTS` | Grants paid | no single total; SOI-current `grants_to_govt` (line 1), `grants_to_individuals` (line 2) | `F9_09_EXP_GRANT_US_ORG_TOT`, `F9_09_EXP_GRANT_US_INDIV_TOT`, `F9_09_EXP_GRANT_FRGN_TOT` | LOC |
| `ALLOC` | Payments to affiliates | `payments_to_affiliates` (SOI-current tier; the legacy-tier column is an estimate) | `F9_09_EXP_PAY_AFFIL_TOT` | DESC |
| `FUNDFEES` | Fundraising fees | `professional_fundraising_fees` | `F9_09_EXP_FEE_SVC_FUNDR_TOT` | SV |
| `SECUR` | Gross receipts from sales of securities (Part VIII line 7a(i)), **not** securities held | `gross_sales_securities` | — | SV; for securities held (Part X lines 11-12) use `investments_eoy` / `investments_other_eoy` (SOI-current tier), Classic `F9_10_ASSET_INVEST_SEC_EOY` / `F9_10_ASSET_INVEST_SEC_OTH_EOY` |
| `LANDBNB` | Land, buildings, equipment (net) | `land_bldg_equip_eoy` (SOI-current tier; the legacy-tier column is an estimate) | `F9_10_ASSET_LAND_BLDG_NET_EOY` | LOC |
| `RETEARN` | Retained earnings/endowment | `retained_earnings_eoy` | `F9_10_NAFB_EARNING_RETAINED_EOY` | SV |

### File Organization

Scope files are named `CORE-{YEAR}-{501C3-CHARITIES|501CE-NONPROFIT|501C3-PRIVFOUND}-{PC|PZ|PF}[-HRMN-V{n}].csv` (NCCS Core catalog; the harmonized charity and nonprofit files are V1, the private-foundation files V0). Example: `CORE-2021-501C3-CHARITIES-PC-HRMN-V1.csv` = 501(c)(3) charities, full-990 filers (PC), file year 2021. Check in the catalog whether the year is a tax or processing year.

### Download

**Via Education Data Portal mirror (recommended for education research):**

```python
import polars as pl

# NCCS data for higher education institutions
DATASET_PATH = "nccs/colleges_nccs_all"
nccs = fetch_from_mirrors(DATASET_PATH)

# Variables use Portal naming (lowercase, descriptive)
# e.g., contributions_total, prog_serv_rev, revenue_total
```

```r
library(arrow)
library(dplyr)

# NCCS data for higher education institutions
# fetch_from_mirrors() is a Python helper; in R, build the URL from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
DATASET_PATH <- "nccs/colleges_nccs_all"
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
nccs <- read_parquet(paste0(mirror$root_url, "/", DATASET_PATH, ".", mirror$format))

# Variables use Portal naming (lowercase, descriptive)
# e.g., contributions_total, prog_serv_rev, revenue_total
```

**Direct from NCCS (outside Portal):**

Start at the official Core catalog rather than constructing or copying a legacy object URL:

`https://urbaninstitute.github.io/nccs/catalogs/catalog-core.html`

The catalog currently distinguishes merged Core (1987-2024) from SOI-current (2012-2024) and legacy (1987-2011), and warns that recent tax years are in progress as the IRS continues to release returns. Select the product and file linked by the catalog, then record the product name, tax year, retrieval date, and status note in project provenance. Use this stable official catalog as the sole documented Core navigation route.

---

## IRS 990 Efile Database

The most comprehensive source: electronic filings parsed into 125 relational tables.

### Overview

| Attribute | Value |
|-----------|-------|
| **Coverage** | 990 and 990-EZ e-filers (e-filing mandatory for most organizations from tax year 2021); no 990-PF or 990-T |
| **Time span** | 2009-2023 (2024 partial) |
| **Variables** | Fields across forms and schedules (count not verified; see the efile data dictionary) |
| **Format** | XML → converted to relational tables |

### Coverage Growth (e-filed returns in the 990 Data Commons by form type, Oct. 2025; NCCS parsed tables include only 990 and 990-EZ)

| Year | 990 | 990EZ | 990PF | 990T |
|------|-----|-------|-------|------|
| 2012 | 179,688 | 93,750 | 39,933 | 0 |
| 2015 | 233,519 | 124,894 | 58,815 | 0 |
| 2019 | 284,515 | 152,689 | 87,790 | 0 |
| 2022 | 348,034 | 205,532 | 122,533 | 22,611 |

**Note**: E-filing became mandatory for most tax-exempt organizations beginning in the 2021 tax year (the 2022 calendar year), so coverage is now comprehensive.

### Data Organization

Efile data is organized into 125 relational tables corresponding to Form 990 sections:

| Table Category | Examples |
|----------------|----------|
| **Header** | Basic org info, tax year, form type |
| **Part I** | Summary (revenue, expenses, assets) |
| **Part VII** | Compensation (officers, directors, employees) |
| **Part VIII** | Statement of Revenue |
| **Part IX** | Statement of Functional Expenses |
| **Part X** | Balance Sheet |
| **Schedule A** | Public Charity Status |
| **Schedule D** | Supplemental Financials (endowment) |
| **Schedule J** | Compensation Information |
| **Schedule R** | Related Organizations |

### Variable Naming Convention

Variables use the convention `FF_PP_NAME` (form, two-digit part, name), e.g. `F9_01_REV_TOT_CY` = Form 990 Part I total revenue, current year; table files are `FF-PPP-TTT-NAME` (e.g. `F9-P00-T00-HEADER`)

| Position | Meaning | Examples |
|----------|---------|----------|
| 1-2 | Form | F9 (990), SA-SR (Schedules A-R) |
| 4-5 | Part/Location | 01-12 (Part I-XII), 00 (header) |
| 7+ | Variable name | Descriptive name |

In the efile v2_1 CSV files the column name is the prefix plus the variable name, as the data dictionary lists them (e.g. `SD_05_ENDOW_BALANCE_EOY_CY`). Every table also carries the keys `EIN2` (`EIN-XX-XXXXXXX`), `ORG_EIN` (9-digit), `URL` (unique per filing, the merge key between tables) and `TAX_YEAR`. Observed in the header lines of six 2024 v2_1 tables (Part VI, VII, VIII and IX, Schedule D Part V, Schedule J Part II) on 2026-10-28; the efile names used in this skill's examples were checked against those headers or the data dictionary.

### Access via R Package (Direct NCCS, Not Portal)

> The package README (fetched 2026-10-28) says "This package has been **DEPRECATED**" and points to its replacement, the `ef2` package (Nonprofit-Open-Data-Collective/ef2). The `get_990_data()` call below was not checked against either package. The pre-processed v2_1 CSV tables are linked from the Efile catalog.

```r
# Install the irs990efile package
# devtools::install_github("Nonprofit-Open-Data-Collective/irs990efile")

library(irs990efile)

# Get data for specific organizations by EIN
data <- get_990_data(ein = c("123456789", "987654321"), year = 2021)
```

---

## Form 990-N ePostcard

Small nonprofits (under $50K gross receipts) file Form 990-N, a minimal electronic filing.

### Overview

| Attribute | Value |
|-----------|-------|
| **Eligibility** | Gross receipts normally ≤ $50,000 |
| **Information collected** | Name, EIN, address, website, principal officer, tax year |
| **What's missing** | All financial data |

### Key Points

- **Not in Core data**: 990-N filers excluded from Core series (no financial disclosure)
- **Important for research design**: Many grassroots organizations (PTAs, little leagues, block associations) file only 990-N
- **Compliance tracking**: Filing 990-N maintains tax-exempt status

### Download

Available from NCCS: https://nccs.urban.org/nccs/datasets/postcard/

---

## Publication 78

IRS Publication 78 lists organizations eligible to receive tax-deductible charitable contributions.

### Overview

| Attribute | Value |
|-----------|-------|
| **Purpose** | Verify charitable donation eligibility |
| **Content** | Name, city, state, EIN, deductibility code |
| **Update** | Monthly |

### Use Cases

- Verify an organization's current tax-exempt status
- Identify organizations that have lost exempt status
- Sampling frame for 501(c)(3) public charities

---

## SOI Microdata

Statistics of Income (SOI) Division extracts from IRS administrative files.

### Overview

The SOI produces statistical samples and extracts used for official IRS statistics on exempt organizations. NCCS provides access to historical SOI extract files.

| Attribute | Value |
|-----------|-------|
| **Source** | IRS Statistics of Income Division |
| **Sample** | Stratified by asset size |
| **Variables** | Curated financial measures |

### Historical Context

Before the Efile era, SOI extracts were the primary source of 990 data for researchers. NCCS's SOI-current Core panel (2012–2024) is built directly from IRS SOI extract files; the legacy panel (1987–2011) is harmonized from the historical NCCS CORE files.

---

## Data Access Methods

### Education Data Portal Mirror (Recommended for Education Research)

The Portal mirror provides NCCS data for higher education institutions in parquet format. See `datasets-reference.md` for the canonical path, `mirrors.yaml` for mirror configuration, and `fetch-patterns.md` for the `fetch_from_mirrors()` function.

```python
import polars as pl

# NCCS Form 990 data for colleges/universities
DATASET_PATH = "nccs/colleges_nccs_all"
nccs = fetch_from_mirrors(DATASET_PATH)

# Data is pre-matched to IPEDS UNITID
# Covers 1993-2016 (24 years)
# ~30K institution-year observations, 161 columns
```

```r
library(arrow)
library(dplyr)

# NCCS Form 990 data for colleges/universities
# fetch_from_mirrors() is a Python helper; in R, build the URL from the mirror root.
# Mirror failover: see `education-data-query/references/fetch-patterns.md` (R pattern)
DATASET_PATH <- "nccs/colleges_nccs_all"
mirror <- yaml::read_yaml("mirrors.yaml")$mirrors[[1]]
# NOTE: illustrative only — mirror parquet files are Polars-written and may
# declare string_view columns, so a plain read can fail under R arrow
# ("cannot handle Array of type <utf8_view>"). Real fetch scripts must use the
# view-safe parquet read from `education-data-query/references/fetch-patterns.md`.
nccs <- read_parquet(paste0(mirror$root_url, "/", DATASET_PATH, ".", mirror$format))

# Data is pre-matched to IPEDS UNITID
# Covers 1993-2016 (24 years)
# ~30K institution-year observations, 161 columns
```

**Important:** Portal data uses integer encodings for categorical variables:
- `fips`: Integer state FIPS codes (1-78, including territories); no -1/-2/-3 codes observed
- `mult_ein_flag`: 0 (No) or 1 (Yes)
- All variable names are lowercase
- NTEE codes, subsection codes, and foundation codes are NOT included (data is pre-filtered to higher ed)

### Direct NCCS Download (For Broader or Newer Data)

Use the official catalogs as the navigation and provenance layer; do not assume a copied object URL remains current. The catalog identifies available products, files, tax years, and status notes.

### Data Catalogs

- **Core Series (authoritative for Core coverage)**: `https://urbaninstitute.github.io/nccs/catalogs/catalog-core.html`
- **BMF by State**: `https://urbaninstitute.github.io/nccs/catalogs/catalog-bmf.html`
- **Efile**: `https://urbaninstitute.github.io/nccs/catalogs/catalog-efile-v2_1.html`

As verified on 2026-10-19, the Core catalog lists a merged panel (1987-2024), SOI-current (2012-2024), and legacy (1987-2011) harmonized tiers plus a 'Classic NCCS format'; recent tax years are in progress as the IRS continues to release returns.

### Sector in Brief Dashboard

Interactive dashboard for exploring and downloading nonprofit data with filtering:

https://urban-main.shinyapps.io/sector-in-brief/

### R Package: nccsdata

> **Note:** The `get_data()` function in R downloads directly from NCCS, not from the Education Data Portal mirrors. For Portal-based research, use the `fetch_from_mirrors()` approach above. The R package provides access to the full NCCS universe including BMF, Core, and Efile data with NTEE codes.

```r
# devtools::install_github("UrbanInstitute/nccsdata")
library(nccsdata)

# Download Core data with filters (direct from NCCS, not Portal)
data <- get_data(
  geo_scope = "state",
  geo_code = "CA",
  ntee_scope = "B",  # Education
  years = 2018:2021
)
```

### GitHub Repository

Code, documentation, and data processing scripts:

https://github.com/UrbanInstitute/nccs

---

## Recommended Dataset by Research Need

| Research Need | Recommended Dataset |
|---------------|---------------------|
| Identify universe of nonprofits | BMF |
| Historical financial trends | Core PZ (broad) or PC (detailed) |
| Governance and compensation | Efile |
| Private foundation grants | Core PF |
| Geographic analysis | BMF (geocoded) + Census crosswalks |
| Maximum variable detail | Efile |
| Quick sampling frame | BMF or Pub78 |
| Small grassroots organizations | 990-N ePostcard |
