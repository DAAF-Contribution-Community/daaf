# NCCS Variable Definitions

This reference provides definitions for key variables in NCCS datasets, including naming conventions, common financial measures, and data quality considerations.

> **Truth Hierarchy:** When interpreting variable values, apply this priority:
> 1. **Actual data file** (what you observe in the parquet/CSV) — this IS the truth
> 2. **Live codebook** (.xls in mirror, via `get_codebook_url("nccs/codebook_colleges_nccs_form_990")`) — authoritative documentation, may lag
> 3. **This file** — convenient summary, may drift from codebook
>
> If this documentation contradicts the codebook or observed data, trust the higher-priority source.

## Education Data Portal vs. Direct NCCS Access

> **CRITICAL:** Variable names and encodings differ between the Education Data Portal and direct NCCS downloads.

| Aspect | Education Data Portal | Direct NCCS |
|--------|----------------------|-------------|
| **Variable case** | lowercase (`contributions_total`) | Depends on product: Unified BMF and harmonized Core panel are lowercase (`total_contributions`); Classic (HRMN) Core and Efile are uppercase (`F9_08_REV_CONTR_TOT`); the join key `EIN2` is uppercase everywhere |
| **Naming style** | Descriptive (`prog_serv_rev`) | Descriptive (harmonized panel) or `FF_PP_NAME` form-location names (Classic, Efile); the abbreviated legacy names (`PROGREV`) are no longer used as column names |
| **FIPS encoding** | Integer (`6` for California) | May be string (`"06"`) |
| **Missing codes** | Integer (`-1`, `-2`, `-3`) | Integer or blank |
| **Data format** | Parquet (via Portal mirror) | CSV |

### Portal Variable Mapping

The second column is the legacy NCCS Core name each Portal column likely came from (the Portal does not document its sources); the third is the column to use in current harmonized Core files, with its basis tag (key under [Core Data Series Variables](#core-data-series-variables)).

| Portal Name | Legacy NCCS Core name (pre-2026) | Current harmonized Core name (basis) | Description |
|-------------|----------------------------------|--------------------------------------|-------------|
| `year` | — (Portal-derived) | — | Academic year — the Portal-aligned year corresponding to the fall semester of the academic year the filing is associated with (range 1993-2016). The codebook labels this "Academic year (fall semester)." |
| `fiscal_year` | `FISYR` (fiscal year ending year) | `tax_year` (DESC) | Fiscal year — the IRS fiscal year ending year from the Form 990 filing (range 1994-2017). Typically differs from `year` by +1 because a fiscal year ending in e.g. June 2015 corresponds to the 2014-2015 academic year (`year`=2014, `fiscal_year`=2015). |
| `unitid` | — | — | IPEDS institution ID (Portal addition) |
| `ein` | `EIN` | `ein`, formatted `XX-XXXXXXX` (SV) | Employer Identification Number (String, 9 characters with leading zeros, e.g. `042103580`; verify mirror dtype and zero-pad to 9 before joining; reformat to `XX-XXXXXXX` or `EIN-XX-XXXXXXX` before joining direct NCCS files) |
| `fips` | `FIPS` | none in Core (NF); BMF geography instead | State FIPS code (integer in Portal, 1-78) |
| `inst_name_nccs` | `NAME` | none in harmonized Core (NF); Classic `F9_00_ORG_NAME_L1`, Unified BMF `org_name_display` | Organization name from 990 filing (String) |
| `mult_ein_flag` | — | — | Multiple-EIN indicator (0=No, 1=Yes) |
| `contributions_total` | `CONT` | `total_contributions` (SV) | Total contributions |
| `prog_serv_rev` | `PROGREV` | `program_service_revenue` (SV) | Program service revenue |
| `revenue_total` | `TOTREV` | `total_revenue` (SV) | Total revenue |
| `expenses_total` | `EXPS` | `total_expenses` (SV) | Total expenses |
| `total_assets_eoy` | `TOTASS` | `total_assets_eoy` (LOC) | Total assets (end of year) |
| `net_assets_eoy` | `NETASS` | `total_net_assets_eoy` (LOC) | Net assets |
| `compensation_officers` | `COMPENS` | `compensation_current_officers` (SV) | Officer compensation |
| `salaries_other` | `OTHSAL` | `other_salaries_wages` (SV) | Other salaries |

> **Note:** The Portal dataset has 161 columns total. The table above shows selected key variables. Consult the codebook for the complete list. The full dataset includes detailed Part VIII revenue breakdowns (e.g., `prog_serv_rev_amt2a` through `prog_serv_rev_amt2f`), Part IX expense breakdowns, Part X balance sheet items, and support test variables (170/509).

## Contents

- [Variable Naming Conventions](#variable-naming-conventions)
- [Core Data Series Variables](#core-data-series-variables)
- [Business Master File Variables](#business-master-file-variables)
- [Efile Variable Naming](#efile-variable-naming)
- [Financial Measure Definitions](#financial-measure-definitions)
- [Missing Data Codes](#missing-data-codes)
- [Data Quality and Validation](#data-quality-and-validation)

---

## Variable Naming Conventions

### Core Data Series

Current NCCS Core products name columns two ways: the harmonized Core panel (merged, SOI-current and legacy tiers) uses lowercase descriptive names (`total_revenue`, `total_assets_eoy`), and the Classic NCCS format (`CORE-…-HRMN-V1.csv`) uses the same `FF_PP_NAME` naming scheme as Efile (`F9_08_REV_TOT_TOT`), keyed by `EIN2`.

**Legacy NCCS Core naming (pre-2026 files).** Older NCCS Core files used abbreviated uppercase names. No current NCCS file uses them as column names; they survive only in the `source_var` column of the harmonized Core legacy-tier dictionaries. The patterns below help read older code and documentation:

| Pattern | Meaning | Examples |
|---------|---------|----------|
| TOT* | Total | TOTREV (total revenue), TOTASS (total assets) |
| NET* | Net | NETINC (net income), NETASS (net assets) |
| *REV | Revenue | PROGREV (program revenue), INVREV (investment revenue; not in the legacy dictionaries checked) |
| *EXP | Expenses | FUNEXP (functional expenses) |
| *INC | Income | INVINC (investment income) |
| *ASS | Assets | TOTASS (total assets), SECASS (securities assets; not in the legacy dictionaries checked) |
| *LIAB | Liabilities | TOTLIAB (total liabilities) |

### Efile Database

Efile variables follow the convention `FF_PP_NAME` (form, two-digit part, name), e.g. `F9_01_REV_TOT_CY` = Form 990 Part I total revenue, current year; table files are `FF-PPP-TTT-NAME` (e.g. `F9-P00-T00-HEADER`):

```
FF_PP_VARIABLE_NAME
│  │  └── Descriptive name
│  └───── Part number (00-12)
└──────── Form (F9, SA-SR for schedules)
```

**Examples**:
| Variable | Meaning |
|----------|---------|
| `F9_00_TAX_YEAR` | Form 990, header, tax year |
| `F9_01_REV_TOT_CY` | Form 990, Part I, total revenue, current year |

In the v2_1 CSV files a column name is the dictionary's prefix plus variable name (`F9_01_` + `REV_TOT_CY`), and every table also carries the keys `EIN2`, `ORG_EIN`, `URL` and `TAX_YEAR` (observed in six 2024 table headers, 2026-10-28). The efile names in this skill's examples were checked against those headers or the efile data dictionary.

---

## Core Data Series Variables

> **Legacy names and current columns.** The first column of each table below is a pre-2026 NCCS Core name; no current NCCS file uses it as a column name. Use the current columns instead. **Harmonized Core** = the harmonized Core panel (merged, SOI-current and legacy tiers; the tier is named where a column is not in all three). **Classic / Efile** = the Classic NCCS format (`CORE-…-HRMN-V1.csv`, dictionary `CORE-HRMN_dd.csv`) and the Efile v2_1 tables, which use the same name for every Part VIII-X item listed here. The Core catalog says column mapping tables are "rolling out"; until NCCS publishes one, these tables are DAAF's own matches. **Basis** (for the harmonized name, or for the Unified BMF column where the harmonized Core has none): **SV** = the legacy name is listed in that column's `source_var` (legacy-tier dictionaries for 2000 and 2010); **LOC** = matched by the Form 990 line the current dictionary gives; **DESC** = matched by description only (inference); **XW** = a row of NCCS's legacy BMF crosswalk (`XWALK-BMF-V2.0.csv`); **NF** = no current column found. Classic and Efile names are matched by Form 990 line. (Sources: NCCS harmonized Core data dictionaries, legacy tier 2000 and 2010, merged tier 2010 and 2016, SOI-current tier 2016 and 2021; `CORE-HRMN_dd.csv`; Unified BMF data dictionary; Efile data dictionary and 2024 table headers; all fetched 2026-10-28.)

### Identification Variables

| Legacy name | Description | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|-----------------|-----------------|-------|
| `EIN` | Employer Identification Number | `ein` (`XX-XXXXXXX`) | `EIN2` (`EIN-XX-XXXXXXX`); 9-digit forms Classic `F9_00_ORG_EIN`, Efile `ORG_EIN` | SV |
| `EIN2` | EIN with consistent formatting; use for merging | — (the panel uses `ein`) | `EIN2` (`EIN-XX-XXXXXXX`), also in the Unified BMF | name unchanged |
| `NCCSKEY` | Unique key (EIN + return date) | none: the merged tier has one row per (`ein`, `tax_period`); SOI-current marks repeats with `is_amendment` | Efile `URL` (unique per filing) | NF |
| `NAME` | Organization name (legal name from 990) | none; join the Unified BMF (`org_name_display`) | Classic `F9_00_ORG_NAME_L1`; Efile `ORG_NAME_L1` | NF |
| `SEC_NAME` | Secondary/DBA name | none; Unified BMF `dba_name` (XW: `SEC_NAME` → `SORT_NAME`) | Classic `F9_00_ORG_NAME_DBA_L1` | NF |
| `FISYR` | Fiscal year (ending year), YYYY | `tax_year` ("Calendar year the filing's fiscal period ended") | Classic `F9_00_TAX_YEAR`; Efile `TAX_YEAR` | DESC |
| `TAXPER` | Tax period end date, YYYYMM | `tax_period` (character) | Classic `F9_00_TAX_PERIOD_END_DATE`; Efile `TAX_PERIOD_END_DATE` | SV |

### Location Variables

No harmonized Core tier has address or geography columns: join the Unified BMF on `ein` / `EIN2`, or use the Classic header fields.

| Legacy name | Description | Harmonized Core | Classic / Unified BMF | Basis |
|-------------|-------------|-----------------|-----------------------|-------|
| `ADDRESS` | Street address | none | Classic `F9_00_ORG_ADDR_L1`; Unified BMF `org_addr_street` | NF (XW: `ADDRESS` → `STREET`) |
| `CITY` | City | none | Classic `F9_00_ORG_ADDR_CITY`; Unified BMF `org_addr_city` | NF (XW) |
| `STATE` | Two-letter state code | none | Classic `F9_00_ORG_ADDR_STATE`; Unified BMF `org_addr_state` | NF (XW) |
| `ZIP` | ZIP code, may include ZIP+4 | none | Classic `F9_00_ORG_ADDR_ZIP`; Unified BMF `org_addr_zip` | NF (XW) |
| `ZIP5` | First 5 digits of ZIP | none | Unified BMF `org_addr_zip5` | NF (XW: `ZIP5` → `ZIP`) |
| `FIPS` | State + county FIPS code, 5 digits | none | Unified BMF has no FIPS column: join the geocoded BMF to the NCCS county FIPS crosswalk on (`geo_state_abbr`, `geo_county`) for `geo_county_fips` | NF (XW: dropped) |
| `MSA_NECH` | Metro Statistical Area (NCCS assignment) | none | NCCS CBSA crosswalk on `county_fips`, built on the OMB 2023 delineations (whether those areas match the legacy assignment was not checked) | NF (XW: dropped) |

### Classification Variables

No harmonized Core tier has NTEE, foundation or organization codes (only `subsection_cd` and `is_501c3`): join the Unified BMF.

| Legacy name | Description | Harmonized Core | Unified BMF / Classic | Basis |
|-------------|-------------|-----------------|-----------------------|-------|
| `NTEE1` | NTEE major group, A-Z | none | Unified BMF `ntee_code_major_group` | DESC (XW: dropped, "derived in current pipeline") |
| `NTEECC` | Full NTEE code (letter + 2 digits) | none | Unified BMF `ntee_code_clean` (standardized 3-character code); `ntee_code_raw` (as in the source file, 1-4 characters) | XW (`NTEECC` → `NTEE_CD`) |
| `SUBSECCD` | IRS subsection (03 = 501(c)(3), etc.) | `subsection_cd` (integer, e.g. `3`); also `is_501c3` | Unified BMF `subsection_code` (character, e.g. `"03"`); Classic `F9_00_EXEMPT_STAT_501C3_X` (501(c)(3) indicator only) | SV |
| `FNDNCD` | Foundation code | none | Unified BMF `foundation_code` | XW (`FNDNCD` → `FOUNDATION`) |
| `ORGCD` | Organization form (corporation, trust, etc.) | none | Unified BMF `organization_code` | XW (`ORGCD` → `ORGANIZATION`) |

The Unified BMF also has `nteev2` (NCCS NTEEv2 code, SUBSECTOR-CODE-TYPE). Types differ across products: `subsection_cd` is integer in all three harmonized tiers, while the Unified BMF stores `subsection_code` as character, so compare `3` in one and `"03"` in the other. The Unified BMF dictionary types `foundation_code` as character, while the BMF transform reference outputs it as integer; cast before comparing.

> Older NCCS BMF files used NTEE_IRS (official) and NTEE_NCCS (NCCS corrections; a supplement, per NCCS).

### Revenue Variables

| Legacy name | Description | 990 Location | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|--------------|-----------------|-----------------|-------|
| `TOTREV` | Total revenue | Part I, Line 12 | `total_revenue` | `F9_08_REV_TOT_TOT` (VIII-12); Efile Part I `F9_01_REV_TOT_CY` | SV |
| `TOTREV2` | Total revenue (alt calculation) | Sum of components | `total_revenue` (one column for `TOTREV` and `TOTREV2`) | `F9_08_REV_TOT_TOT` | SV |
| `CONT` | Contributions and grants | Part VIII, Line 1 | `total_contributions` | `F9_08_REV_CONTR_TOT` (VIII-1h) | SV (the legacy-tier description cites Schedule A line 15(e); the SOI-current tier gives VIII-1h) |
| `PROGREV` | Program service revenue | Part VIII, Line 2 | `program_service_revenue` | `F9_08_REV_PROG_TOT_TOT` | SV |
| `DUES` | Membership dues | Part VIII, Line 1b | `membership_dues_assessments_sec170` (legacy and merged tiers) | — | SV; the legacy dictionary says "DUES is not available in Core PC and CO files circa 2011 and newer" (reported as program service revenue from tax year 2008) |
| `INVINC` | Investment income | Part VIII, Line 3 (Part I line 10 = lines 3, 4, 7d) | `investment_income` | `F9_08_REV_OTH_INVEST_INCOME_TOT` (VIII-3); Efile Part I `F9_01_REV_INVEST_TOT_CY` (I-10) | SV |
| `DIVID` | Dividend income | Part VIII, Line 3 (dividends and interest combined on 2008+ form) | none; use `investment_income` | `F9_08_REV_OTH_INVEST_INCOME_TOT` | NF |
| `INTINC` | Interest income | Part VIII, Line 3 | none; use `investment_income` | `F9_08_REV_OTH_INVEST_INCOME_TOT` | NF |
| `NETRENT` | Net rental income | Part VIII, Line 6 | `net_rental_income` | `F9_08_REV_OTH_RENT_NET_TOT` (VIII-6d) | SV |
| `SALESEXP` | Cost or other basis of securities sold, **not** a net gain or loss (legacy dictionary) | not given in the dictionary | `cost_basis_securities` | — | SV |
| `OTHREV` | Other revenue | Part VIII, Line 11 | `other_revenue_total_11e` | `F9_08_REV_MISC_TOT_TOT` (VIII-11e) | LOC (its `source_var` is the legacy `OTHINC`) |
| `GRSRCPTS` | Gross receipts | Header item G | none (the similar `gross_receipts_total`, legacy and merged tiers, is sourced from `GRREC`) | Classic `F9_00_GRO_RCPT` (PZ files only) | NF |

### Expense Variables

| Legacy name | Description | 990 Location | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|--------------|-----------------|-----------------|-------|
| `EXPS` | Total expenses | Part I, Line 18 | `total_expenses` | `F9_09_EXP_TOT_TOT` (IX-25); Efile Part I `F9_01_EXP_TOT_CY` | SV |
| `TOTEXP` | Total functional expenses | Part IX, Line 25 | `total_expenses` | `F9_09_EXP_TOT_TOT` | LOC |
| `FUNEXP` | Functional expenses | Part IX | `total_expenses` | `F9_09_EXP_TOT_TOT` | DESC |
| `PROGEXP` | Program service expenses | Part IX, Col B | none (the legacy-tier `program_service_expense` is an estimate in the "Authorized Users Only" supplemental fields) | Efile `F9_09_EXP_TOT_PROG` (not in Classic) | NF |
| `MGTEXP` | Management/general expenses | Part IX, Col C | none | Efile `F9_09_EXP_TOT_MGMT` (not in Classic) | NF |
| `FUNDEXP` | Fundraising expenses | Part IX, Col D | none | Efile `F9_09_EXP_TOT_FUNDR` (Classic: 501CE PZ files only) | NF |
| `GRNTS` | Grants and allocations | Part IX, Lines 1-3 | no single total; SOI-current `grants_to_govt` (line 1), `grants_to_individuals` (line 2) | `F9_09_EXP_GRANT_US_ORG_TOT`, `F9_09_EXP_GRANT_US_INDIV_TOT`, `F9_09_EXP_GRANT_FRGN_TOT` (lines 1-3) | LOC |
| `COMPENS` | Compensation (officers) | Part IX, Line 5 | `compensation_current_officers` | `F9_09_EXP_COMP_DTK_TOT` | SV |
| `OTHSAL` | Other salaries | Part IX, Line 7 | `other_salaries_wages` | `F9_09_EXP_OTH_SAL_WAGE_TOT` | SV |
| `PAIDSRV` | Professional fees | Part IX, Line 11 | no single total; SOI-current `fees_for_services_management`, `fees_for_services_lobbying`, `fees_for_services_investment_mgmt`, `fees_for_services_other`, plus `professional_fundraising_fees` (11e) | Efile `F9_09_EXP_FEE_SVC_*_TOT`, one per line 11a-11g | DESC |
| `OCCUP` | Occupancy expenses | Part IX, Line 16 | `occupancy` (SOI-current) | `F9_09_EXP_OCCUPANCY_TOT` | LOC |
| `TRAVEL` | Travel expenses | Part IX, Line 17 | `travel` (SOI-current; integer) | `F9_09_EXP_TRAVEL_TOT` | LOC |
| `DEPREC` | Depreciation | Part IX, Line 22 | `depreciation_depletion` (SOI-current) | `F9_09_EXP_DEPREC_TOT` | LOC |
| `INTEREST` | Interest expense | Part IX, Line 20 | `interest_expense` (SOI-current; the legacy-tier column of that name holds interest on savings and temporary cash investments, a different field) | `F9_09_EXP_INT_TOT` | LOC |

### Balance Sheet Variables

| Legacy name | Description | 990 Location | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|--------------|-----------------|-----------------|-------|
| `TOTASS` | Total assets (EOY) | Part X, Line 16 | `total_assets_eoy` | `F9_10_ASSET_TOT_EOY`; Efile Part I `F9_01_NAFB_ASSET_TOT_EOY` | LOC (its legacy `source_var` is `ASS_EOY`, not `TOTASS`) |
| `TOTASSBEG` | Total assets (BOY) | Part X, Line 16 | `total_assets_boy` (legacy and merged tiers) | `F9_10_ASSET_TOT_BOY` | LOC |
| `TOTLIAB` | Total liabilities (EOY) | Part X, Line 26 | `total_liabilities_eoy` | `F9_10_LIAB_TOT_EOY`; Efile Part I `F9_01_NAFB_LIAB_TOT_EOY` | LOC |
| `TOTLIABBEG` | Total liabilities (BOY) | Part X, Line 26 | `total_liabilities_boy` (legacy and merged tiers) | `F9_10_LIAB_TOT_BOY` | LOC |
| `NETASS` | Net assets (EOY) | Part X, Line 33 (pre-2018 forms; Line 32 from 2018, not confirmed: see the note below the table) | `total_net_assets_eoy` | `F9_10_NAFB_TOT_EOY`; Efile Part I `F9_01_NAFB_TOT_EOY` | LOC |
| `NETASSBEG` | Net assets (BOY) | Part X, Line 33 (pre-2018 forms; Line 32 from 2018, not confirmed: see the note below the table) | `total_net_assets_boy` (legacy and merged tiers) | `F9_10_NAFB_TOT_BOY` | LOC |
| `FUNDSBAL` | Fund balance (BOY) | | none | — | NF: not in the legacy dictionaries checked; the similar `FUNDBAL` maps to `total_net_assets_eoy`, an end-of-year value, so do not use it as a beginning-of-year balance |
| `CASH` | Cash | Part X, Lines 1-2 | `noninterest_cash_eoy` (line 1) + `savings_and_temp_investments_eoy` (line 2), SOI-current | `F9_10_ASSET_CASH_EOY` + `F9_10_ASSET_SAVING_EOY` | LOC |
| `SECUR` | Gross receipts from sales of securities, **not** securities held (legacy dictionary) | Part VIII, Line 7a(i) (legacy dictionary) | `gross_sales_securities` | — | SV. For securities held (Part X lines 11-12) use SOI-current `investments_eoy` / `investments_other_eoy`, Classic `F9_10_ASSET_INVEST_SEC_EOY` / `F9_10_ASSET_INVEST_SEC_OTH_EOY` |
| `LANDBNB` | Land, buildings, equipment (net) | Part X, Line 10c | `land_bldg_equip_eoy` (SOI-current; the legacy-tier column is an estimate) | `F9_10_ASSET_LAND_BLDG_NET_EOY` | LOC |
| `RETEARN` | Retained earnings/endowment | | `retained_earnings_eoy` | `F9_10_NAFB_EARNING_RETAINED_EOY` | SV |
| `ACCTSPAY` | Accounts payable | Part X, Line 17 | `accounts_payable_eoy` (SOI-current) | `F9_10_LIAB_ACC_PAYABLE_EOY` | LOC |
| `MORTG` | Mortgages and notes | Part X, Lines 23-24 | `secured_mortgages_eoy` (line 23) + `unsecured_notes_eoy` (line 24) | `F9_10_LIAB_MTG_NOTE_EOY` + `F9_10_LIAB_NOTE_UNSEC_EOY` | LOC |

> **Net assets line number.** The NCCS dictionaries checked all give Part X line 33 and none splits by form year: SOI-current and merged `total_net_assets_eoy` "990 Core_Pt X-33(B)" (years 2012-2024), Classic `F9_10_NAFB_TOT_EOY` "F990-PC-PART-10-LINE-33-EOY" (2012-2022), Efile `F9_10_NAFB_TOT_BOY` / `_EOY` "F990-PC-PART-10-LINE-33-BOY" / "-EOY", and legacy `total_net_assets_boy` "New 990 (DocCD=93): Part X line 33 (A)". The same dictionaries give Part X line 32 to retained earnings (`retained_earnings_eoy` "990 Core_Pt X-32(B)"; Classic `F9_10_NAFB_EARNING_RETAINED_EOY` "F990-PC-PART-10-LINE-32-EOY"). They neither confirm nor refute the "Line 32 from 2018" renumbering, which DAAF has not checked against the IRS forms. Before citing a line number, read Part X of the Form 990 for the filing year. (Sources: NCCS harmonized Core data dictionaries, SOI-current, merged and legacy tiers; `CORE-HRMN_dd.csv`; Efile data dictionary; all fetched 2026-10-28.)

### Computed Variables

| Legacy name | Description | Calculation (current names) | Harmonized Core | Classic / Efile | Basis |
|-------------|-------------|-----------------------------|-----------------|-----------------|-------|
| `NETINC` | Net income | Total revenue minus total expenses | `net_income` (legacy and merged tiers) | `F9_01_EXP_REV_LESS_EXP_CY` (Part I line 19; Efile, and Classic PZ files only) | SV |
| `PROGREV_PCT` | Program revenue ratio | `program_service_revenue` / `total_revenue` | computed, not a file column | — | NF |
| `ADMIN_PCT` | Administrative expense ratio | Efile `F9_09_EXP_TOT_MGMT` / `F9_09_EXP_TOT_TOT` | computed, not a file column | — | NF |
| `FUNDR_PCT` | Fundraising expense ratio | Efile `F9_09_EXP_TOT_FUNDR` / `F9_09_EXP_TOT_TOT` | computed, not a file column | — | NF |

---

## Business Master File Variables

### Raw IRS BMF Columns and Their Unified BMF Names

The uppercase names are the columns of the raw IRS Exempt Organizations BMF extract, which the NCCS Unified BMF renames. Use the Unified BMF column on Unified BMF files. Older NCCS BMF files (`501CX-NONPROFIT-PX`) used further legacy names; NCCS's legacy BMF crosswalk (`XWALK-BMF-V2.0.csv`) maps them to these raw names (e.g. `SUBSECCD` → `SUBSECTION`, `FNDNCD` → `FOUNDATION`, `NTEECC` → `NTEE_CD`, `INCOME` → `INCOME_AMT`). The raw-to-Unified links are the input and output columns of the NCCS BMF transform reference; rows marked † are linked by the transform function's name only (inference). Every Unified BMF column listed is typed character in the Unified BMF data dictionary.

| Raw IRS name | Unified BMF column | Description | Notes |
|--------------|--------------------|-------------|-------|
| `EIN` | `ein` (`XX-XXXXXXX`); `EIN2` (`EIN-XX-XXXXXXX`) | Employer ID Number | Primary key |
| `NAME` | `org_name_raw` / `org_name_display` | Organization name | Legal name |
| `ICO` | `in_care_of_name_raw` / `in_care_of_name_clean` | In care of name | Contact person |
| `STREET` | `org_addr_street` | Street address | |
| `CITY` | `org_addr_city` | City | |
| `STATE` | `org_addr_state` | State | 2-letter code |
| `ZIP` | `org_addr_zip` (and `org_addr_zip5`) | ZIP code | |
| `GROUP` | `group_exemption_number` | Group exemption number | For affiliated orgs |
| `SUBSECTION` | `subsection_code` | IRS code subsection | 501(c)(3), etc.; character, e.g. `"03"` |
| `AFFILIATION` | `affiliation_code` | Affiliation code | Independent, central, subordinate |
| `CLASSIFICATION` | `classification_code` | Classification code | |
| `RULING` | `ruling_date` (date), `ruling_date_ym_str` | Ruling date | YYYYMM format in the raw file |
| `DEDUCTIBILITY` | `deductibility_code` | Deductibility code | 1 = contributions deductible |
| `FOUNDATION` | `foundation_code` | Foundation code | See Foundation Codes in `nonprofit-data.md`; the transform reference outputs integer, the dictionary says character |
| `ACTIVITY` | `activity_code` † | Activity codes | Historical (pre-NTEE) |
| `ORGANIZATION` | `organization_code` | Organization type | Corporation, trust, etc. |
| `STATUS` | `status_code` | Tax-exempt status | Active, revoked, etc. |
| `TAX_PERIOD` | `tax_period_ymd`, `tax_period_ym_str` | Tax period | Most recent filing |
| `ASSET_CD` | `asset_code` † | Asset code | Size category |
| `INCOME_CD` | `income_code` † | Income code | Size category |
| `FILING_REQ_CD` | `filing_requirement_code` | Filing requirement | 990, 990-EZ, 990-N |
| `PF_FILING_REQ_CD` | `pf_filing_requirement_code` | PF filing requirement | |
| `ACCT_PD` | `accounting_period` | Accounting period | Month fiscal year ends |
| `ASSET_AMT` | `asset_amount` † | Asset amount | Most recent; stored as character |
| `INCOME_AMT` | `income_amount` † | Income amount | Most recent; Unified BMF: "Total income in dollars (can be negative)", stored as character |
| `REVENUE_AMT` | `revenue_amount` † | Revenue amount | Most recent; stored as character |
| `NTEE_CD` | `ntee_code_raw` / `ntee_code_clean` | NTEE code | Official IRS code; `ntee_code_clean` is the standardized 3-character form |

### NCCS Unified BMF Additions

| Variable | Description | Notes |
|---|---|---|
| `geo_lat` / `geo_lon` | WGS 84 latitude/longitude | Geocoded variant only |
| `geo_county` / `geo_metro_area` | County and metro-area names from the geocoder | Names, not FIPS/CBSA codes; join the crosswalk layers for codes |
| `geo_score` / `geo_status` | Geocoder match score (1-100) / status (M/T/U) | |
| `first_vintage_ym` / `last_vintage_ym` | First/last BMF vintage observed | `first_year_in_bmf` / `last_year_in_bmf` are the year forms |
| `bmf_source` | current (monthly IRS BMF) or legacy (501CX-NONPROFIT-PX) | No "active" flag; use last_vintage_ym and status_code |

(Source: NCCS Unified BMF data dictionaries, fetched 2026-10-28.)

---

## Efile Variable Naming

### Form and Schedule Prefixes

| Prefix | Source |
|--------|--------|
| `F9_` | Form 990 |
| `SA_` | Schedule A (Public Charity Status) |
| `SB_` | Schedule B (Contributors) - restricted |
| `SC_` | Schedule C (Political Activity) |
| `SD_` | Schedule D (Supplemental Financials) |
| `SE_` | Schedule E (Schools) |
| `SF_` | Schedule F (Foreign Activities) |
| `SG_` | Schedule G (Fundraising/Gaming) |
| `SH_` | Schedule H (Hospitals) |
| `SI_` | Schedule I (Grants) |
| `SJ_` | Schedule J (Compensation) |
| `SK_` | Schedule K (Tax-Exempt Bonds) |
| `SL_` | Schedule L (Related Party Transactions) |
| `SM_` | Schedule M (Non-Cash Contributions) |
| `SN_` | Schedule N (Liquidation/Dissolution) |
| `SO_` | Schedule O (Supplemental Information) |
| `SR_` | Schedule R (Related Organizations) |

### Part Numbers

| Part | Content |
|------|---------|
| `00` | Header/outside of parts |
| `01` | Part I - Summary |
| `03` | Part III - Program Accomplishments |
| `04` | Part IV - Checklist |
| `05` | Part V - Other Filings |
| `06` | Part VI - Governance |
| `07` | Part VII - Compensation |
| `08` | Part VIII - Revenue |
| `09` | Part IX - Expenses |
| `10` | Part X - Balance Sheet |
| `11` | Part XI - Reconciliation |
| `12` | Part XII - Financial Statements |

---

## Financial Measure Definitions

### Revenue Measures

Names in parentheses are harmonized Core columns (legacy NCCS Core name after the semicolon); where no harmonized column exists, the Efile name is given. See [Core Data Series Variables](#core-data-series-variables) for the Classic names and the basis of each match.

**Total Revenue** (`total_revenue`; legacy `TOTREV`):
- All income from all sources
- Includes contributions, program revenue, investment income
- Before expenses

**Contributions and Grants** (`total_contributions`; legacy `CONT`):
- Donations from individuals, corporations, foundations
- Government grants (non-exchange)
- Does NOT include government contracts (those are program revenue)

**Program Service Revenue** (`program_service_revenue`; legacy `PROGREV`):
- Revenue from mission-related activities
- Tuition and fees for educational institutions
- Government contracts
- Fee-for-service activities

**Investment Income** (`investment_income`; legacy `INVINC`):
- Part I line 10 investment income = Part VIII lines 3, 4 and 7d (includes net gains from asset sales); royalties are line 5. The legacy-tier dictionary sources `investment_income` from `INVINC` and, for the 2008 and later form, gives "Part VIII Line 3A" only, so by that description it is narrower than Part I line 10 (Efile `F9_01_REV_INVEST_TOT_CY`); values were not compared

### Expense Measures

**Total Functional Expenses** (`total_expenses`, Part IX line 25 column A; legacy `TOTEXP` or `FUNEXP`):
- All operating expenses
- Allocated to program, management, fundraising

**Program Expenses** (Efile `F9_09_EXP_TOT_PROG`; legacy `PROGEXP`; no harmonized column):
- Direct costs of mission delivery
- Educational instruction, student services

**Management and General** (Efile `F9_09_EXP_TOT_MGMT`; legacy `MGTEXP`; no harmonized column):
- Administrative overhead
- Board expenses, finance, HR

**Fundraising** (Efile `F9_09_EXP_TOT_FUNDR`; legacy `FUNDEXP`; no harmonized column):
- Costs of soliciting contributions
- Development office, events

### Balance Sheet Measures

**Total Assets** (`total_assets_eoy`; legacy `TOTASS`):
- All resources owned
- Cash, investments, property, receivables

**Net Assets** (`total_net_assets_eoy`; legacy `NETASS`):
- Assets minus liabilities
- Equivalent to "fund balance" or "equity"
- Through tax year 2017 (all Portal years): unrestricted, temporarily restricted, permanently restricted
- From 2018 forms: without / with donor restrictions

### Derived Ratios

| Ratio | Calculation | Interpretation |
|-------|-------------|----------------|
| Program Ratio | `F9_09_EXP_TOT_PROG` / `F9_09_EXP_TOT_TOT` (Efile) | Higher = more efficient |
| Admin Ratio | `F9_09_EXP_TOT_MGMT` / `F9_09_EXP_TOT_TOT` (Efile) | Lower = less overhead |
| Fundraising Efficiency | `F9_09_EXP_TOT_FUNDR` / `F9_08_REV_CONTR_TOT` (Efile) | Lower = more efficient fundraising |
| Revenue Concentration | Max source / `total_revenue` | Higher = more dependent |
| Liquidity | (`noninterest_cash_eoy` + `savings_and_temp_investments_eoy`) / `total_expenses` × 12 (SOI-current) | Months of operating reserves |

---

## Missing Data Codes

### Portal Codes (Integer in Portal)

In the Education Data Portal (not NCCS source files): -1 Missing, -2 Not applicable, -3 Suppressed (generic Portal labels; rare in NCCS columns).

| Code | Meaning |
|------|---------|
| `-1` | Missing |
| `-2` | Not applicable |
| `-3` | Suppressed |
| `null` | Not reported by organization |
| `0` | Zero value (explicitly reported) |

> **Portal Note:** In the Portal dataset, `-1`/`-2`/`-3` are integer values but are **empirically rare** — most missing data appears as `null`. Only a handful of financial columns (e.g., `sale_sec_gross_net`, `changes_net_assets_other`) contain any negative coded values. Always check for both `null` and negative codes when cleaning.

### Interpreting Missing Data

**Important distinctions** (using Portal variable names):

| Observation | Interpretation |
|-------------|----------------|
| `invest_inc_total = 0` | Organization reported zero investment income |
| `invest_inc_total = null` | Organization did not report (may have income) |
| `invest_inc_total = -1` | Generic Portal "missing" code (rare in NCCS columns) |

### Handling Missing Data

**Using Portal data (Polars):**

```python
import polars as pl

# Load NCCS data via unified mirror system
DATASET_PATH = "nccs/colleges_nccs_all"
df = fetch_from_mirrors(DATASET_PATH)

# Filter out null and rare negative codes
df_clean = df.filter(
    (pl.col("invest_inc_total").is_not_null()) &
    (pl.col("invest_inc_total") >= 0)  # Excludes rare -1, -2, -3 codes
)

# Or replace negative codes with null (precautionary)
df = df.with_columns(
    pl.when(pl.col("invest_inc_total") < 0)
    .then(None)
    .otherwise(pl.col("invest_inc_total"))
    .alias("invest_inc_total_clean")
)

# Distinguish zero from missing
df = df.with_columns(
    (pl.col("invest_inc_total").is_not_null() & (pl.col("invest_inc_total") > 0))
    .alias("has_inv_income")
)
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
df <- read_parquet(paste0(mirror$root_url, "/", DATASET_PATH, ".", mirror$format))

# Filter out null and rare negative codes
df_clean <- df |>
  filter(!is.na(invest_inc_total), invest_inc_total >= 0)

# Or replace negative codes with null (precautionary)
df <- df |>
  mutate(invest_inc_total_clean = ifelse(invest_inc_total < 0, NA, invest_inc_total))

# Distinguish zero from missing
df <- df |>
  mutate(has_inv_income = !is.na(invest_inc_total) & invest_inc_total > 0)
```

**Using direct NCCS data (Polars):**

Direct NCCS files handle negatives differently from the Portal blocks above. The `-1`/`-2`/`-3` codes are Portal-only, so in a direct NCCS file a negative amount is a value the filer reported, such as an investment loss. The Core catalog lists "Filer-supplied negatives on revenue fields — IRS-supplied as-filed; not amendments.", and the 2010 legacy-tier dictionary reports a minimum `investment_income` of -30,732,551. Do not null negatives here as the Portal blocks do: that would delete real losses. Keep them and flag them:

```python
import polars as pl

# Direct NCCS harmonized Core (e.g. core_2021_990.csv): the -1/-2/-3 codes are Portal-only,
# and negative amounts are filer-supplied values (e.g. investment losses), so keep them and flag them
df = df.with_columns(
    (pl.col("investment_income").cast(pl.Float64, strict=False) < 0).alias("investment_income_negative")
)
```

```r
# Direct NCCS harmonized Core (e.g. core_2021_990.csv): the -1/-2/-3 codes are Portal-only,
# and negative amounts are filer-supplied values (e.g. investment losses), so keep them and flag them
df <- df |>
  mutate(investment_income_negative = suppressWarnings(as.numeric(investment_income)) < 0)
```

In a Classic HRMN file the same Part VIII line 3 amount is `F9_08_REV_OTH_INVEST_INCOME_TOT`.

---

## Data Quality and Validation

### Common Data Issues

| Issue | Description | Detection |
|-------|-------------|-----------|
| **Outliers** | Extreme values (errors or real) | Check against organization size |
| **Sign errors** | Negative revenue or assets | Most values should be positive; in direct NCCS files negatives are filer-supplied values, not codes, so investigate rather than null them |
| **Rounding** | Values rounded to nearest thousand | Small values may be imprecise |
| **Duplicates** | Same filing multiple times | Harmonized Core: check (`ein`, `tax_period`) uniqueness (the merged tier keeps one row per pair; the SOI-current tier flags repeats with `is_amendment`). Efile: `URL` is unique per filing |
| **Fiscal year mismatch** | Comparing different periods | Verify `tax_period` (harmonized Core) or `TAX_PERIOD_END_DATE` (Efile) alignment |

### Validation Checks

**Using Portal data (Polars, lowercase variable names):**

**Balance sheet identity**:
```python
import polars as pl

# Assets should equal Liabilities + Net Assets
df = df.with_columns(
    (pl.col("total_assets_eoy") - pl.col("total_liab_eoy") - pl.col("net_assets_eoy"))
    .abs()
    .alias("balance_check")
)
balance_errors = df.filter(pl.col("balance_check") > 100)  # Allow small rounding
```

```r
library(dplyr)

# Assets should equal Liabilities + Net Assets
df <- df |>
  mutate(balance_check = abs(total_assets_eoy - total_liab_eoy - net_assets_eoy))
balance_errors <- df |> filter(balance_check > 100)
```

**Revenue reconciliation**:
```python
# Total revenue should approximate sum of components
df = df.with_columns(
    (pl.col("contributions_total") + pl.col("prog_serv_rev") + pl.col("invest_inc_total"))
    .alias("rev_sum")
)
df = df.with_columns(
    (pl.col("revenue_total") - pl.col("rev_sum")).abs().alias("rev_check")
)
# Note: revenue_total includes other categories not shown here; some gap is expected
```

```r
# Total revenue should approximate sum of components
df <- df |>
  mutate(
    rev_sum = contributions_total + prog_serv_rev + invest_inc_total,
    rev_check = abs(revenue_total - rev_sum)
  )
# Note: revenue_total includes other categories not shown here; some gap is expected
```

**Year-over-year reasonableness**:
```python
# Flag large year-over-year changes (sorted by ein and year)
df = df.sort(["ein", "year"])
df = df.with_columns(
    (pl.col("revenue_total") / pl.col("revenue_total").shift(1).over("ein") - 1)
    .alias("rev_change")
)
unusual = df.filter(pl.col("rev_change").abs() > 1.0)  # >100% change
```

```r
# Flag large year-over-year changes (sorted by ein and year)
df <- df |>
  arrange(ein, year) |>
  group_by(ein) |>
  mutate(rev_change = revenue_total / lag(revenue_total) - 1) |>
  ungroup()
unusual <- df |> filter(abs(rev_change) > 1.0)  # >100% change
```

**Using direct NCCS data:** Replace Portal names with the product's own names: harmonized Core `total_assets_eoy`, `total_liabilities_eoy`, `total_net_assets_eoy`, `total_revenue`, `total_contributions`; Classic (HRMN) Core `F9_10_ASSET_TOT_EOY`, `F9_10_LIAB_TOT_EOY`, `F9_10_NAFB_TOT_EOY`, `F9_08_REV_TOT_TOT`, `F9_08_REV_CONTR_TOT`. Direct files sort and group on `ein` (harmonized Core) or `EIN2` (Classic, Efile), and the year is `tax_year` (harmonized Core), `F9_00_TAX_YEAR` (Classic) or `TAX_YEAR` (Efile).

### Error Checking Recommendations

1. **Check totals vs. components**: Sum of parts should equal reported total
2. **Verify balance sheet**: Assets = Liabilities + Net Assets
3. **Look for negative values**: Most financial variables should be positive
4. **Examine outliers**: Top/bottom 1% may include errors
5. **Compare to prior year**: Large changes warrant investigation
6. **Cross-check with audited financials**: When available for key institutions
7. **Verify against external sources**: IPEDS, institution websites

### Known Data Issues

**Form version changes (2008)**:
- The 2008 redesign added Part VI (independent board members, whistleblower and document-retention policies, compensation-review process); the 2007 form already asked board size, family/business relationships, and whether a written conflict-of-interest policy existed
- Compensation reporting expanded
- Some variable definitions changed

**Efile transition period (2012-2021)**:
- Not all organizations filed electronically
- Large orgs more likely to efile
- Sample may not be representative

**Fiscal year variation**:
- Organizations have different year-ends
- June 30 common for colleges
- December 31 common for others
- Some file on different cycles

### Documentation Resources

- **NCCS Data Guide**: https://nccs.urban.org/pubs/nccs-data-guide.pdf
- **Core Data Dictionary**: https://nccsdata.s3.amazonaws.com/harmonized/core/CORE-HRMN_dd.csv
- **Efile Data Dictionary**: https://nonprofit-open-data-collective.github.io/irs990efile/data-dictionary/data-dictionary.html
- **Master Concordance File**: https://github.com/Nonprofit-Open-Data-Collective/irs-efile-master-concordance-file
