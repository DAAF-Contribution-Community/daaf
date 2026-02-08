---
name: education-data-source-eada
description: Equity in Athletics Disclosure Act (EADA) data for college athletics gender equity analysis. Use when analyzing athletic participation, coaching staff, salaries, expenses, or revenues at colleges/universities, or understanding Title IX context in athletics.
metadata:
  audience: data-analysts
  domain: education-data
---

# Education Data Source: EADA (Equity in Athletics)

Guide for understanding and using Equity in Athletics Disclosure Act data through the Urban Institute Education Data Portal.

## What is EADA?

The Equity in Athletics Disclosure Act (EADA) requires coeducational postsecondary institutions that:
- Participate in Title IV federal student financial aid programs, AND
- Have an intercollegiate athletic program

to submit annual reports on:

- **Athletic Participation**: Number of participants by sport and gender
- **Coaching Staff**: Head and assistant coaches by gender and employment status
- **Salaries**: Coach compensation by gender of teams coached
- **Expenses**: Operating, recruiting, and total expenses by team
- **Revenues**: Athletic revenues by team
- **Athletic Aid**: Scholarships and grants-in-aid by gender

**Key Fact**: ~2,000+ institutions report annually; data publicly available by October 15 each year.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `title-ix-context.md` | Legal framework, gender equity requirements | Understanding policy context |
| `data-elements.md` | Participation, coaches, salaries, expenses, revenues | Identifying available variables |
| `sport-level-data.md` | Data available by individual sport | Sport-specific analysis |
| `variable-definitions.md` | Key variables and their meanings | Query construction |
| `limitations.md` | Data quality issues, not Title IX compliance | Interpreting results |
| `api-endpoints.md` | Urban Institute API access patterns | Fetching data |

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
    └─ See ./references/api-endpoints.md
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
│   └─ See ./references/limitations.md (Critical)
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

## Quick Reference: Common Filters

| Filter | Variable | Example Values |
|--------|----------|----------------|
| Institution | `unitid` | 6-digit IPEDS ID |
| Year | `year` | 2003-2022 |
| State | `fips` | Integer FIPS code (e.g., `6` = California) |
| Sector | `sector` | 1=Public, 2=Private nonprofit, 3=Private for-profit |
| Athletic Division | `ath_classification_code` | Integer codes 1-20 (see below) |

### Athletic Classification Codes (Portal Integer Encoding)

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

| Code | Meaning |
|------|---------|
| `-1` | Missing/not reported |
| `-2` | Not applicable |
| `-3` | Suppressed |

## Quick Reference: Data Availability

| Topic | Years Available | Update Frequency |
|-------|-----------------|------------------|
| Institution-level | 2003-2022 | Annual |
| Sport-level | 2003-2022 | Annual |
| Coaching details | 2003-2022 | Annual |
| Financial data | 2003-2022 | Annual |

## Critical Context

### EADA is NOT Title IX Compliance Data

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

> **CRITICAL: Portal Integer Encoding**
>
> EADA data from the Education Data Portal uses **integer codes** for categorical variables and missing data. Always filter coded missing values (`-1`, `-2`, `-3`) before calculations.
>
> See `./references/variable-definitions.md` for complete code mappings.

## Example Research Questions

| Question | Key Variables | Reference |
|----------|---------------|-----------|
| Are women underrepresented in athletics? | `partic_*`, enrollment | `data-elements.md` |
| How much do institutions invest in women's sports? | `exp_*`, `rev_*` | `data-elements.md` |
| Are coaches of women's teams paid fairly? | `salary_*` | `variable-definitions.md` |
| Which sports have most female participants? | Sport-level data | `sport-level-data.md` |
| Has participation equity improved over time? | Multi-year trend | `api-endpoints.md` |

## Related Skills

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| `education-data-explorer` | Find other college data | Joining with IPEDS |
| `education-data-query` | Construct API queries | Fetching EADA data |

### EADA Codebook

| Dataset | Codebook Path |
|---------|---------------|
| Institutional Characteristics | `college-university/eada/institutional-characteristics/codebook_colleges_eada_inst-characteristics` |

> Codebook is an `.xls` file on both mirrors. See `fetch-patterns.md` for `get_codebook_url()`. For human reference — not parsed programmatically.

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
| Data limitations | `./references/limitations.md` |
| Self-reporting issues | `./references/limitations.md` |
| EADA vs Title IX | `./references/limitations.md` |
| API endpoints | `./references/api-endpoints.md` |
| Query examples | `./references/api-endpoints.md` |
