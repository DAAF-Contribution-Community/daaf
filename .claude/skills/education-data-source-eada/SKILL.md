---
name: education-data-source-eada
description: >-
  Equity in Athletics Disclosure Act (EADA) data for college athletics gender
  equity analysis. Use when analyzing athletic participation, coaching staff,
  salaries, expenses, or revenues at colleges/universities, or understanding
  Title IX context in athletics. EADA is NOT Title IX compliance data.
metadata:
  audience: data-analysts
  domain: education-data
---

# EADA Data Source Reference

The EADA provides the only standardized, publicly available dataset on college athletics participation, coaching, finances, and athletic aid by gender across ~2,000+ postsecondary institutions, enabling gender equity analysis in intercollegiate athletics.

> **CRITICAL: Value Encoding**
>
> EADA data from the Education Data Portal uses **integer codes** for categorical
> variables. Original EADA web tools use string labels; the Portal converts these
> to integers. Always verify codes against codebooks.
>
> | Context | `sector` | `ath_classification_code` | Missing values |
> |---------|----------|--------------------------|----------------|
> | **Portal (integers)** | `1` = Public | `1` = NCAA DI FBS | `-1`, `-2`, `-3` |
> | Original EADA | String labels | String labels | Blank / N/A |
>
> See `./references/variable-definitions.md` for complete encoding tables.

## What is EADA?

- **Collector**: U.S. Department of Education (Office of Postsecondary Education)
- **Coverage**: ~2,000+ coeducational postsecondary institutions with intercollegiate athletics
- **Mandate**: Institutions participating in Title IV aid with athletic programs must report
- **Frequency**: Annual (data publicly available by October 15 each year)
- **Available years**: 2003–2022 (Portal), 2002–2021 (HuggingFace mirror)
- **Primary identifier**: `unitid` (6-digit IPEDS institution ID)
- **Content**: Athletic participation, coaching staff, salaries, expenses, revenues, and athletic aid — all reported by gender

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `title-ix-context.md` | Legal framework, gender equity requirements | Understanding policy context |
| `data-elements.md` | Participation, coaches, salaries, expenses, revenues | Identifying available variables |
| `sport-level-data.md` | Data available by individual sport | Sport-specific analysis |
| `variable-definitions.md` | Key variables, codes, special values | Interpreting specific data elements |
| `limitations.md` | Data quality issues, comparability, self-reporting caveats | Assessing data reliability |
| `fetch-patterns.md` | Mirror URLs and fetch code patterns | Fetching data |

## Decision Trees

### What analysis am I conducting?

```
Research question?
├─ Gender equity overview → Start with participation + aid ratios
│   └─ See ./references/data-elements.md
├─ Coaching disparities → Coach counts + salaries by gender
│   └─ See ./references/data-elements.md (Coaching section)
├─ Financial investment → Expenses + revenues by team gender
│   └─ See ./references/data-elements.md (Financial section)
├─ Sport-specific analysis → Individual sport data
│   └─ See ./references/sport-level-data.md
├─ Title IX compliance assessment → CAUTION: EADA ≠ compliance data
│   └─ See ./references/limitations.md (Critical)
└─ Trend analysis → Year-over-year comparisons
    └─ See ./references/fetch-patterns.md
```

### What variables do I need?

```
Variable categories?
├─ Participation counts
│   ├─ Total participants by gender → `partic_men`, `partic_women`
│   ├─ Unduplicated count → `partic_men_coed`, `partic_women_coed`
│   └─ By sport → See ./references/sport-level-data.md
├─ Coaching
│   ├─ Head coaches → `hdcoach_*` variables
│   ├─ Assistant coaches → `asstcoach_*` variables
│   └─ Salaries → `salary_*` variables
├─ Financial
│   ├─ Expenses → `exp_*` variables
│   ├─ Revenues → `rev_*` variables
│   └─ Athletic aid → `aid_*` variables
└─ Detailed definitions → See ./references/variable-definitions.md
```

### How do I interpret the data?

```
Interpretation question?
├─ What counts as "participation"?
│   └─ See ./references/variable-definitions.md
├─ Why don't participation ratios match enrollment?
│   └─ See ./references/limitations.md
├─ Is this institution Title IX compliant?
│   └─ CANNOT determine from EADA data alone
│       └─ See ./references/limitations.md (Critical)
├─ Why are some values missing or zero?
│   └─ See ./references/limitations.md
└─ How do I compare across institutions?
    └─ See ./references/limitations.md (Comparability section)
```

## Quick Reference: Key Metrics

### Participation Equity Indicators

| Metric | Calculation | Interpretation |
|--------|-------------|----------------|
| Female participation ratio | `partic_women / (partic_men + partic_women)` | Compare to female enrollment ratio |
| Participation gap | Female enrollment % - Female participation % | Positive = underrepresentation |
| Opportunities per student | Total participants / Total undergrads | Athletic opportunity rate |

### Financial Equity Indicators

| Metric | Calculation | Notes |
|--------|-------------|-------|
| Aid ratio | `aid_women / (aid_men + aid_women)` | Should approximate participation ratio |
| Per-participant expense | `exp_total / partic_total` | By gender for comparison |
| Recruiting investment | `recruiting_exp` by gender | Indicator of program investment |

### Coaching Equity Indicators

| Metric | Focus | Variables |
|--------|-------|-----------|
| Female coaches of women's teams | % female | `hdcoach_women_female_ft`, `_pt` |
| Salary equity | Avg salary comparison | `salary_men_coach`, `salary_women_coach` |

### Key Identifiers

| ID | Format | Level | Example | Notes |
|----|--------|-------|---------|-------|
| `unitid` | 6-digit integer | Institution | `110635` | Same as IPEDS; primary join key |
| `year` | 4-digit integer | Reporting year | `2022` | Fiscal year ending |
| `fips` | Integer | State | `6` (California) | Federal FIPS code |

### Common Filters

| Filter | Variable | Example Values |
|--------|----------|----------------|
| Institution | `unitid` | 6-digit IPEDS ID |
| Year | `year` | 2003–2022 |
| State | `fips` | Integer FIPS code (e.g., `6` = California) |
| Sector | `sector` | 1=Public, 2=Private nonprofit, 3=Private for-profit |
| Athletic Division | `ath_classification_code` | Integer codes 1–20 (see below) |

### Athletic Classification Codes

| Code | Division | Code | Division |
|------|----------|------|----------|
| 1 | NCAA Division I FBS | 12 | NJCAA Division I |
| 2 | NCAA Division I FCS | 13 | NJCAA Division II |
| 3 | NCAA Division I (no football) | 14 | NJCAA Division III |
| 4 | NCAA Division II (with football) | 15 | NCCAA Division I |
| 5 | NCAA Division II (no football) | 16 | NCCAA Division II |
| 6 | NCAA Division III (with football) | 17 | CCCAA |
| 7 | NCAA Division III (no football) | 18 | Independent |
| 8 | Other (check `ath_classification_other`) | 19 | NWAC |
| 9 | NAIA Division I | 20 | USCAA |
| 10 | NAIA Division II | | |

### Missing Data Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| `-1` | Missing/not reported | Data not submitted by institution |
| `-2` | Not applicable | Item doesn't apply (e.g., no men's team) |
| `-3` | Suppressed | Data suppressed for privacy |

### Data Availability

| Topic | Years Available | Update Frequency |
|-------|-----------------|------------------|
| Institution-level | 2003–2022 | Annual |
| Sport-level | 2003–2022 | Annual |
| Coaching details | 2003–2022 | Annual |
| Financial data | 2003–2022 | Annual |

### Example Research Questions

| Question | Key Variables | Reference |
|----------|---------------|-----------|
| Are women underrepresented in athletics? | `partic_*`, enrollment | `data-elements.md` |
| How much do institutions invest in women's sports? | `exp_*`, `rev_*` | `data-elements.md` |
| Are coaches of women's teams paid fairly? | `salary_*` | `variable-definitions.md` |
| Which sports have most female participants? | Sport-level data | `sport-level-data.md` |
| Has participation equity improved over time? | Multi-year trend | `fetch-patterns.md` |

## Data Access

Datasets for EADA are available via the mirror system. See `datasets-reference.md` for canonical paths and `fetch-patterns.md` for fetch code patterns.

**Key datasets:**

| Dataset | Path | Type |
|---------|------|------|
| Institutional Characteristics | `eada/colleges_eada_inst_characteristics` | Single |

Codebooks: See `datasets-reference.md` codebook column. Use `get_codebook_url()` from `fetch-patterns.md`.

### Filtering

```python
# Filter by athletic division (NCAA Division I FBS only)
df_d1_fbs = df.filter(pl.col("ath_classification_code") == 1)

# Exclude coded missing values before calculations
df_clean = df.filter(
    (pl.col("partic_men") >= 0) &
    (pl.col("partic_women") >= 0)
)

# Filter by sector (public institutions only)
df_public = df.filter(pl.col("sector") == 1)
```

## Common Pitfalls

| Pitfall | Issue | Solution |
|---------|-------|----------|
| Including coded missing values | `-1`, `-2`, `-3` treated as real numbers skew totals and ratios | Filter `>= 0` on all numeric columns before aggregation |
| Assuming Title IX compliance | EADA data cannot determine Title IX compliance — it is a disclosure tool, not an enforcement mechanism | Read `./references/limitations.md`; use EADA for descriptive analysis only |
| Comparing across institutions naively | Different reporting practices, program sizes, and classification levels make raw comparisons misleading | Normalize by enrollment, filter to same classification, and note caveats |
| Using string codes | Portal uses integer encodings, not original EADA string labels | Use integer codes from `./references/variable-definitions.md` |
| Self-reported data accuracy | Institutions self-report without independent verification; errors and inconsistencies exist | Cross-check outliers against institution websites or IPEDS data |
| Ignoring zero values | Zero may mean "no team" or "not reported" depending on context | Distinguish between true zeros and missing data using `-1`/`-2` codes |

## EADA vs. Title IX Compliance

```
EADA Data                          Title IX Compliance
──────────────────────────────────────────────────────────
Self-reported                      OCR investigation
Snapshot (Oct 15)                  Continuous obligation
Participation counts only          Participation + interest + ability
No "laundry list" items           13+ treatment areas
Public disclosure                  Enforcement mechanism
```

**Always read**: `./references/limitations.md` before drawing compliance conclusions.

### Key Limitations Summary

- **Self-reported**: No independent verification
- **Counting methods**: Differ from Title IX counting
- **Not comprehensive**: Misses many equity factors
- **Comparability issues**: Different reporting practices across institutions

## Related Data Sources

| Source | Relationship | When to Use |
|--------|--------------|-------------|
| `education-data-source-ipeds` | Complementary institution data | Joining enrollment, demographics, finances via `unitid` |
| `education-data-explorer` | Parent discovery skill | Finding available endpoints across all sources |
| `education-data-query` | Data fetching | Downloading parquet/CSV files from mirrors |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Title IX law | `./references/title-ix-context.md` |
| Gender equity requirements | `./references/title-ix-context.md` |
| Three-prong test | `./references/title-ix-context.md` |
| Participation variables | `./references/data-elements.md` |
| Coaching variables | `./references/data-elements.md` |
| Salary variables | `./references/data-elements.md` |
| Expense variables | `./references/data-elements.md` |
| Revenue variables | `./references/data-elements.md` |
| Athletic aid | `./references/data-elements.md` |
| Sport-specific data | `./references/sport-level-data.md` |
| Variable definitions | `./references/variable-definitions.md` |
| Integer encoding tables | `./references/variable-definitions.md` |
| Data limitations | `./references/limitations.md` |
| Self-reporting issues | `./references/limitations.md` |
| EADA vs Title IX | `./references/limitations.md` |
| Fetch patterns | `./references/fetch-patterns.md` |
| Mirror URLs | `./references/fetch-patterns.md` |
