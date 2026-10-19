# State Coverage

Participating states, coverage rates, data partners, and experimental data status.

## Contents

- [Coverage Overview](#coverage-overview)
- [Participating States and Partners](#participating-states-and-partners)
- [Coverage Rates](#coverage-rates)
- [Experimental Data Status](#experimental-data-status)
- [Coverage Implications](#coverage-implications)
- [Joining PSEO](#joining-pseo)

## Coverage Overview

PSEO coverage is **partner-based and release-specific**. Census release **V4.14.1 (2026Q2, posted 2026-08-25)** contains:

- **1,117 institution rows** (1,116 eight-digit OPEIDs plus `0033290W`, Penn State World Campus)
- Partners in **37 states plus the District of Columbia** (Maryland, New Jersey, New Mexico, Tennessee and Vermont added since V4.13.0)
- Western Governors University as an online-only participating institution

These counts were verified from Census latest-release files on 2026-10-19. The prior release, V4.13.0 (2025Q4), listed 952 institutions and partners in 32 states plus D.C. They do **not** establish a national percentage of all U.S. graduates, so this reference does not quote one.

Coverage varies because institutions and systems enter the product through separate data partnerships. Partner composition, institution counts, cohorts, and available outcomes can change between releases.

## Participating States and Partners

Do not treat a copied state or institution roster as permanently current. Use the Census release files as the authoritative participation inventory:

| Evidence | Stable Latest-Release URL | Use |
|----------|---------------------------|-----|
| Version | `https://lehd.ces.census.gov/data/pseo/latest_release/all/version_pseo.txt` | Record the exact release identifier and quarter |
| Institutions | `https://lehd.ces.census.gov/data/pseo/latest_release/all/pseo_all_institutions.csv` | Verify institution membership and count |
| Partners | `https://lehd.ces.census.gov/data/pseo/latest_release/all/pseo_all_partners.txt` | Verify participating states, D.C., systems, and institutions |

For reproducible reporting, save the release identifier alongside the analysis and state whether coverage refers to the current Census release or to the fixed Education Data Portal snapshot.

## Coverage Rates

The latest-release partner and institution files establish participation, but they do not by themselves provide a single current national graduate-coverage percentage. If a project needs a state or national coverage rate:

1. Select a clearly defined denominator, such as IPEDS completions for a specified year and credential scope.
2. Match only institutions present in the exact PSEO release being analyzed.
3. Report the PSEO release, denominator source/year, matching rules, and unmatched institutions.
4. Treat the result as an analyst-derived estimate, not as a Census-published national coverage statistic.

Historical state percentages based on 2015 IPEDS completions are not carried forward here because partner composition has changed. Recompute rates for the release and denominator relevant to the study.

## Experimental Data Status

### What "Experimental" Means

PSEO is designated as an **experimental data product** by the Census Bureau:

| Characteristic | Implication |
|----------------|-------------|
| **Not official statistics** | May not meet all federal statistical standards |
| **Methodology may change** | Future releases may use different methods |
| **Partial coverage** | Not representative of all U.S. graduates |
| **Quality varies** | Some cells have higher noise/uncertainty |
| **User feedback incorporated** | Product evolves based on user input |

### Experimental vs. Official Products

| Feature | Experimental (PSEO) | Official (e.g., QWI) |
|---------|---------------------|----------------------|
| Federal standards | Developing | Fully compliant |
| Coverage | Partial (participating institutions) | Comprehensive |
| Methodology | May evolve | Stable |
| Use guidance | Research/exploration | Official statistics |
| OMB clearance | Limited | Full |

### Appropriate Uses

**Appropriate:**
- Research and analysis
- Program evaluation
- Student information tools
- Policy exploration
- Institutional planning

**Caution required:**
- Comparisons across institutions with different coverage
- Time series with changing partner composition
- Small-cell estimates (high noise)

**Not appropriate:**
- Definitive rankings without caveats
- High-stakes decisions without supplementary data

## Coverage Implications

### Selection Bias Concerns

Participating states/institutions may differ from non-participants:

| Potential Bias | Direction |
|----------------|-----------|
| State policy environment | Progressive states may be more likely to participate |
| Institutional resources | Large systems more likely to have data infrastructure |
| Student outcomes | Unknown if participating institutions differ systematically |

### Interpreting Results

When analyzing PSEO data:

1. **Check coverage**: Identify the exact release, partners, institutions, cohorts, and rows represented
2. **Consider selection**: Participating institutions may not be representative
3. **Note changes**: Partner composition changes over time
4. **Report limitations**: Always disclose experimental status and avoid unsupported national percentages

### Comparison Guidelines

| Comparison | Validity | Notes |
|------------|----------|-------|
| Same institution over time | High | If institution continuously participates |
| Programs within same institution | High | Same data source/methodology |
| Same program across institutions (same state) | Medium | Same state partner, but institutional differences |
| Same program across states | Lower | Different data sources, selection |
| State-level aggregates | Medium | Coverage rates vary |

## Joining PSEO

### PSEO Coalition

The **PSEO Coalition** coordinates partnerships between:
- State higher education agencies
- University systems
- Individual institutions
- Census Bureau LEHD program

### Partnership Process

1. **Initial contact**: Institution/agency contacts Census Bureau or PSEO Coalition
2. **Data sharing agreement**: Legal framework established
3. **Data specification review**: Ensure transcript data meets requirements
4. **Secure data transmission**: Transfer graduation records to Census
5. **Processing and validation**: Census matches and validates data
6. **Publication**: Data included in next release

### Data Requirements

Partners must provide for each graduate:
- Social Security Number (required for matching)
- Date of birth
- Graduation year
- Degree/credential type
- Major (CIP code)
- Institution identifier (OPEID)

### Contact Information

- **Census Bureau PSEO Team**: CES.PSEO.Feedback@census.gov
- **PSEO Coalition**: https://pseocoalition.org/contact/

### Benefits of Participation

| Benefit | Description |
|---------|-------------|
| National earnings data | Track graduates across state lines |
| Comparative benchmarking | Compare to similar institutions |
| Program evaluation | Assess employment outcomes by major |
| Consumer information | Inform prospective students |
| No additional surveys | Uses existing administrative data |
| Privacy protection | Differential privacy protects individuals |

## Timeline of Coverage Expansion

| Release / Year | Milestone |
|----------------|-----------|
| 2018 | First PSEO data released |
| R2022Q4 | Partners in 24 states (Census pseo_all_partners.txt for that release) |
| V4.13.0 (2025Q4) | 952 institutions; partners in 32 states plus D.C. |
| V4.14.1 (2026Q2) | 1,117 institution rows; partners in 37 states plus D.C. |

The last two rows are release-specific, verified on 2026-10-19 from the Census institution, partner, and version files for each release (V4.13.0 was first counted on 2026-07-21). Recheck those files before reusing the count.
