---
name: education-data-explorer
description: >-
  Mirror-first discovery for Urban Institute Education Data: maps a research question to the mirror dataset FILES that answer it — canonical path, entity grain, year coverage, key variables, and join keys — for CCD, IPEDS, CRDC, College Scorecard, SAIPE, EDFacts, FSA, MEPS, NHGIS, PSEO, NACUBO, NCCS, EADA, and Campus Safety. Discovery output is the mirror path (plus grain, years, variables, caveats), the currency planning and acquisition consume. A pure readable-reference skill for read-only discovery agents — no code, no live HTTP probes; all facts keyed to pinned mirror vintage 0.26.1. Load BEFORE education-data-query — routing (which file, what grain) here, retrieval (fetch code, mirror config) there.
metadata:
  audience: research-planner
  domain: data-access
---

# Education Data Explorer

Discovers which Urban Institute Education Data **mirror files** answer a research question and returns them as acquisition-ready routing facts: the canonical mirror path, what one row represents (grain), year coverage, curated key variables, and join keys. This is the discovery half of the education-data workflow — it owns question→file routing judgment, grain semantics, variable/code meaning, and cross-source joins. It does **not** own fetch mechanics: retrieval code, mirror configuration, codebook-URL construction, and the curated path catalog live in `education-data-query`. Load this skill first (routing), then `education-data-query` (retrieval). Every inventory fact here — years, variables, coded values — is keyed to **mirror vintage 0.26.1 (pinned)**; the discovery path is pure markdown reading, with no instruction to fetch, probe, or execute anything.

## Why mirror-first (and why no API)

DAAF's education pipeline never touches Urban's live REST API. All acquisition is **mirror-based**: a revision-pinned HuggingFace parquet mirror (Portal vintage 0.26.1, revision `0ad00ce0e232c96b0642459e4e7326607a8d26aa`), with an unpinned `urban_csv` bulk-CSV fallback that uses the identical canonical paths. Acquisition consumes **canonical mirror paths** of the form `{source}/{filename}` (extensionless — the mirror layer appends `.parquet` or `.csv`). So discovery's job is to emit those paths, not URL routes. Portal endpoint routes appear here only as small citation/maintenance annotations, never as the thing you hand downstream.

The live REST API moves quarterly (endpoints rename, variables drift); a prior version of this skill hand-documented that API and went badly stale. The mirror is a frozen, reproducible snapshot — so the facts below are stable for vintage 0.26.1 and can be read as reference rather than re-probed.

> **Standing caveat (vintage + fallback).** All year coverage, variables, and coded values below are exact for the **pinned HuggingFace mirror at vintage 0.26.1**. The `urban_csv` fallback is unpinned/current-Portal, so if a fetch falls through to it, vintage guarantees no longer hold exactly. Cite Portal version 0.26.1 for data fetched from the pinned mirror.

## Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `references/schools-datasets.md` | K-12 **school-level** mirror families (CCD, CRDC, EDFacts, MEPS, NHGIS) | Researching individual schools |
| `references/districts-datasets.md` | **District/LEA-level** mirror families (CCD, SAIPE, EDFacts) | Researching school districts |
| `references/colleges-datasets.md` | **College-level** mirror families (IPEDS, Scorecard, FSA, PSEO, EADA, NACUBO, NCCS, NHGIS, Campus Safety) | Researching higher education |
| `references/variable-dictionary-{source}.md` | Complete per-source variable inventory (2,235 per-source variables, deduplicated from 2,994 endpoint-variable rows; verbatim labels/types/filter flags/coded values) | Confirming a real variable name or its coded values |
| `references/variable-codes.md` | Curated, analytically load-bearing coded-value schemes with cross-source populated-subset notes | Interpreting or filtering categorical codes |
| `references/maintenance-live-api.md` | Live-API catalog surfaces + regeneration mechanics — **maintenance sessions only** | Rebuilding the mirror/dictionaries at a new vintage |

> The 14 `variable-dictionary-{source}.md` files are mechanically generated from the Portal varlist at vintage 0.26.1. The routing files curate 5-12 **key** variables per family and point to the full dictionary entry for the rest. Never invent a variable name — if it is not in the dictionary, it is not in the mirror.

## Decision Trees

### What data level (and file) do I need?

```
What entity is one row of my analysis?
├─ An individual K-12 school (ncessch) → schools level
│   └─ references/schools-datasets.md → pick a CCD/CRDC/EDFacts/MEPS/NHGIS family
├─ A school district / LEA (leaid) → school-districts level
│   └─ references/districts-datasets.md → pick a CCD/SAIPE/EDFacts family
└─ A college / university (unitid) → college-university level
    └─ references/colleges-datasets.md → pick an IPEDS/Scorecard/FSA/PSEO/EADA/NACUBO/NCCS/csafety family
```

### What topic → which mirror family?

```
Research topic?
├─ K-12 enrollment / demographics → ccd/schools_ccd_enrollment_{year} (or ccd/schools_ccd_lea_enrollment_{year} at district level)
├─ School/district directory & staffing → ccd/schools_ccd_directory | ccd/school-districts_lea_directory
├─ District finance → ccd/districts_ccd_finance
├─ District poverty → saipe/districts_saipe
├─ Civil rights / discipline / course access → crdc/schools_crdc_* (see schools-datasets.md — one file per topic)
├─ K-12 assessments / grad rates → edfacts/{schools,districts}_edfacts_assessments_{year} | _grad_rates_{year}
├─ School poverty measure → meps/schools_meps
├─ College directory / characteristics → ipeds/colleges_ipeds_directory | _institutional-characteristics
├─ College enrollment → ipeds/colleges_ipeds_fall-enrollment-race_{year} | _enrollment-fte | _headcount
├─ College completions (by CIP) → ipeds/colleges_ipeds_completions-2digcip_{year} | -6digcip_{year}
├─ College graduation rates → ipeds/colleges_ipeds_grad-rates | -200pct | -pell
├─ College finance / endowment → ipeds/colleges_ipeds_finance | nacubo/colleges_nacubo_endow | nccs/colleges_nccs_all
├─ Student aid / loans → ipeds/colleges_ipeds_sfa_* | fsa/colleges_fsa_grants | _loans | _campus_based_volume
├─ Post-college earnings → scorecard/colleges_scorecard_earnings | pseo/colleges_pseo_{year}
├─ Athletics equity → eada/colleges_eada_inst_characteristics
├─ Campus crime (hate crimes) → csafety/colleges_csafety_hate_crimes
└─ Census geography crosswalk → nhgis/{schools,colleges}_nhgis_geog_{census-year}
```

### How do I confirm a variable name or code?

```
Need a variable?
├─ Curated key variables → the family entry in the *-datasets.md routing file
├─ Every variable in a family → references/variable-dictionary-{source}.md (§ that family)
└─ What a categorical code means → references/variable-codes.md
```

## Quick Reference: Data Levels

| Level | Key Sources | Primary ID | ID Format |
|-------|-------------|------------|-----------|
| schools | CCD, CRDC, EDFacts, MEPS, NHGIS | `ncessch` | 12-char zero-padded string |
| school-districts | CCD, SAIPE, EDFacts | `leaid` | 7-char zero-padded string |
| college-university | IPEDS, Scorecard, FSA, PSEO, EADA, NACUBO, NCCS, NHGIS, Campus Safety | `unitid` | 6-digit integer |

> **Zero-padded IDs:** `ncessch` (12) and `leaid` (7) are zero-padded numeric strings — leading zeros are load-bearing (FIPS 01-09 states). `education-data-query` handles the force-string/pad-and-assert read recipe; discovery just needs to name the join key.

## Quick Reference: Join Keys

| Join across | Key | Example use |
|-------------|-----|-------------|
| School sources (CCD ↔ CRDC ↔ EDFacts ↔ MEPS ↔ NHGIS) | `ncessch` (+ `year`) | Enrollment + discipline + poverty |
| District sources (CCD ↔ SAIPE ↔ EDFacts) | `leaid` (+ `year`) | Directory + poverty + outcomes |
| College sources (IPEDS ↔ Scorecard ↔ FSA ↔ PSEO ↔ EADA ↔ NACUBO ↔ NCCS ↔ csafety) | `unitid` (+ `year`) | Characteristics + earnings + aid |
| School → district rollup | `leaid` present on school files | Aggregate schools to their LEA |
| Any level → census geography | `ncessch`/`unitid` via NHGIS crosswalk | Link to tract/CBSA/region |

Match on `year` when joining — coverage windows differ across families (see below), so align years before merging.

## Year Coverage Overview (vintage 0.26.1)

Verified ranges from the endpoint-file bridge and route reconciliation. Non-contiguous families are flagged; see the routing files for exact year lists.

| Family (representative) | Coverage | Note |
|-------------------------|----------|------|
| CCD directory / enrollment | 1986-2024 | Annual |
| CCD district finance | 1991, 1994-2020 | Non-contiguous early years |
| CRDC (most topics) | 2011, 2013, 2015, 2017, 2020, 2021 | Biennial; chronic-absenteeism reaches 2022 |
| EDFacts assessments | 2009-2018, 2020 | 2019 absent (COVID testing waivers) |
| EDFacts grad rates | 2010-2019 | — |
| IPEDS directory / inst-characteristics | 1980, 1984-2024 | — |
| IPEDS finance | 1979, 1983-2017 | Mirror ends 2017 (API reaches further back, differently packaged) |
| IPEDS grad-rates (150%) | 1996-2023 | Wholesale-revalued in v0.26.1 — re-run any pre-2026q3 analysis |
| IPEDS completions (2-/6-dig CIP) | 1991-2023 / 1983-2023 | Yearly shards |
| Scorecard earnings | 2003-2014, 2018 | Sparse; other Scorecard families 1996-2020 |
| SAIPE | 1995, 1997, 1999-2024 | Poverty pct on a 0-1 scale despite `_pct` |
| FSA | 1999-2021 | 90/10 from 2014; campus-based from 2001 |
| MEPS | 2009-2022 | 2023 empty on 2026-08-06 probe |
| NHGIS (schools / colleges) | 1986-2023 / 1980-2023 | Crosswalk file-years; census vintages 1990-2020 |
| PSEO | 2001-2021 | Yearly shards |
| NACUBO / NCCS / EADA / Campus Safety | 2012-2022 / 1993-2016 / 2002-2021 / 2005-2021 | — |

## Grain Logic: What a Row Represents

A mirror file's **grain** is the set of columns that uniquely identify a row. Reading it correctly is the difference between a clean join and a silent fan-out.

- **Base grain** is the entity ID + `year` (e.g., one row per `ncessch` × `year` in CCD directory).
- **Disaggregation dimensions multiply rows.** In the live API these appear as URL path segments (`.../enrollment/{year}/{grade}/race/sex/`); in the mirror file the **same dimensions are columns** (`grade`, `race`, `sex`) and each combination is its own row. So CCD enrollment is one row per `ncessch` × `year` × `grade` × `race` × `sex`. To get a school total, filter to the `99`/total code on each dimension rather than summing (summing double-counts the totals rows).
- **CRDC** files carry `disability` and `lep` dimensions in addition to `race`/`sex`; a discipline file is one row per school × year × the disaggregation the file name advertises.
- **Yearly vs Single files.** "Yearly" families have one file per year with `{year}` in the path (fetch each year, concatenate). "Single" families pack all years into one file (filter on `year` locally). The routing files mark each family Single or Yearly.
- **Coded totals.** Categorical dimensions use `99` = Total and negative sentinels for missing (`-1/-2/-3/-99`) — see `variable-codes.md`. A "total" row and its component rows coexist in the same file.

## What Discovery Should Emit (the acquisition currency)

Discovery output feeds planning, then acquisition. For each dataset a research question needs, emit:

1. **Canonical mirror path(s)** — `{source}/{filename}`, extensionless, with `{year}` placeholder where the family is Yearly. This is the primary currency.
2. **Grain** — what one row represents, including disaggregation dimensions.
3. **Years** — the specific years needed, within the family's coverage window.
4. **Key variables** — the real column names (from the routing file / dictionary) the analysis will use.
5. **Join keys** — the ID(s) linking this file to the others in the plan.
6. **Caveats** — load-bearing warnings (suppression, revaluation, scale, coverage gaps).

Portal endpoint routes are optional citation annotations only — never the hand-off artifact. Do **not** instruct downstream to probe, fetch, or call an API; naming the path and years is sufficient for `education-data-query` to construct the fetch.

## Cross-Reference to Related Skills

| Skill | Purpose | When |
|-------|---------|------|
| `education-data-query` | Fetch code, mirror config, codebook URLs, path catalog | After identifying paths/years/variables here |
| `education-data-context` | Portal-wide interpretation (missing codes, grade encoding, licensing, joins) | Before analyzing retrieved data |
| `education-data-source-{ccd,ipeds,crdc,scorecard,saipe,edfacts,fsa,meps,nhgis,nccs,nacubo,eada,campus-safety,pseo}` | Deep source context: methodology, limitations, historical changes | When you need collection methodology or source-specific caveats beyond routing |

Load a `education-data-source-*` skill when a question needs collection methodology, known limitations, or historical coding changes for a specific source. Each source skill carries a `skill-last-updated` provenance date — flag stale ones to the orchestrator.

## Worked Example: Planning a Discovery Output

**Question:** "Relationship between school poverty and AP course offerings in California high schools?"

- **Level / grain:** schools — one row per `ncessch` × `year`.
- **Files:**
  - `crdc/schools_crdc_apib_enroll` (Single; 2011-2021) — AP/IB enrollment. Key vars: `enrl_ap`, `enrl_ap_math`, `enrl_ap_science`, `enrl_ib`, `enrl_gifted_talented`. Grain adds `race`/`sex`/`disability`/`lep` columns — filter to totals for a school-level measure.
  - `meps/schools_meps` (Single; 2009-2022) — modeled poverty. Key var: `meps_poverty_pct`.
- **Join:** `ncessch` + `year`; overlap window 2011-2021.
- **Filter:** `fips == 6` (California), high schools via CCD `school_level == 3` (join `ccd/schools_ccd_directory`).
- **Emit:** the three paths, the year window, the key variables, the `ncessch` join key, and the CRDC disaggregation-totals caveat. Then load `education-data-query` to fetch.

## Common Pitfalls

- **Emitting a route instead of a path.** Downstream needs `crdc/schools_crdc_discipline_k12_{year}`, not `/schools/crdc/discipline/{year}/...`.
- **Summing disaggregated rows.** Total rows (`99`) coexist with component rows — filter, don't sum.
- **Assuming a variable exists.** If it is not in `variable-dictionary-{source}.md`, it is not in the mirror.
- **Ignoring the coverage window.** Align `year` across families before joining; several have gaps (EDFacts 2019, IPEDS finance ends 2017).
- **Trusting fallback vintage.** Facts are exact for the pinned mirror only; the `urban_csv` fallback is current-Portal.
