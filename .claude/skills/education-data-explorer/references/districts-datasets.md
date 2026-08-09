# Districts Datasets Reference (mirror-first)

District/LEA-level mirror dataset families for the Urban Institute Education Data mirror. Each entry gives the **canonical mirror path** (the acquisition currency — extensionless `{source}/{filename}`, with `{year}` where the family is Yearly), the entity **grain**, **year coverage** (vintage 0.26.1), curated **key variables** (real names — full lists in `variable-dictionary-{source}.md`), **join keys**, **caveats**, and a small **Portal endpoint** annotation for citation/maintenance only.

> **Vintage:** all facts keyed to pinned mirror vintage **0.26.1** (revision `0ad00ce0e232c96b0642459e4e7326607a8d26aa`). The `urban_csv` fallback is unpinned/current-Portal. Primary ID at this level is `leaid` (7-char zero-padded string). Emit paths, not routes. Do not instruct fetching or probing — retrieval belongs to `education-data-query`.

---

## CCD (Common Core of Data)

### CCD District Directory & Staffing — `ccd/school-districts_lea_directory`

- **Type / years:** Single-file · 1986-2024
- **Grain:** one row per `leaid` × `year` (LEA directory + staffing counts).
- **Key variables:** `lea_name`, `fips`, `enrollment`, `number_of_schools`, `urban_centric_locale`, `agency_type`, `agency_level`, `lowest_grade_offered`, `highest_grade_offered`, `teachers_total_fte`, `spec_ed_students`, `english_language_learners` (full 69-var list: `variable-dictionary-ccd.md` § `ccd/school-districts_lea_directory`).
- **Join keys:** `leaid` (+ `year`) to any district source; schools roll up to their LEA via `leaid`.
- **Caveats:** `agency_type` is **not** a Portal filter despite older docs (use post-fetch filtering). FTE staffing counts are LEA-reported and can carry `-1`/`-2` sentinels.
- **Codebook:** `ccd/codebook_districts_ccd_directory`
- **Portal endpoint(s):** `/school-districts/ccd/directory/{year}/`

### CCD District Finance — `ccd/districts_ccd_finance`

- **Type / years:** Single-file · 1991, 1994-2020 (non-contiguous early years)
- **Grain:** one row per `leaid` × `year` (F-33 fiscal record).
- **Key variables:** `rev_total`, `rev_fed_total`, `rev_state_total`, `rev_local_total`, `rev_local_prop_tax`, `exp_total`, `exp_current_elsec_total`, `exp_current_instruction_total`, `exp_current_supp_serve_total`, `salaries_total`, `salaries_instruction`, `enrollment_fall_responsible` (full 163-var list — includes CARES/CRRSA/ARP ESSER relief columns and detailed rev/exp/salary/benefit/debt breakdowns: `variable-dictionary-ccd.md` § `ccd/districts_ccd_finance`).
- **Per-pupil:** compute from `exp_current_elsec_total` / enrollment; the mirror finance file stores dollar totals, not pre-divided per-pupil columns.
- **Join keys:** `leaid` (+ `year`) — commonly joined to `ccd/school-districts_lea_directory` (characteristics) and `saipe/districts_saipe` (poverty).
- **Caveats:** fiscal year lags the school year (~2 years); mirror coverage ends 2020. Census `censusid` present for cross-linking to Census fiscal data.
- **Codebook:** `ccd/codebook_districts_ccd_finance`
- **Portal endpoint(s):** `/school-districts/ccd/finance/{year}/`

### CCD District Enrollment — `ccd/schools_ccd_lea_enrollment_{year}`

- **Type / years:** Yearly · 1986-2024 (one file per year)
- **Grain:** one row per `leaid` × `year` × `grade` × `race` × `sex`. Disaggregation dimensions are **columns**, not URL segments — filter to the `99`/total code on each dimension for an LEA total (do not sum, or totals rows double-count).
- **Key variables:** `leaid`, `year`, `fips`, `grade`, `race`, `sex`, `enrollment` (complete 7-var family: `variable-dictionary-ccd.md` § `ccd/schools_ccd_lea_enrollment_{year}`).
- **Join keys:** `leaid` (+ `year`, and dimension codes where relevant).
- **Caveats:** `grade=-1` is Pre-K (not missing); `grade=99` is all-grades total. Fetch each needed year and concatenate.
- **Codebook:** `ccd/codebook_districts_ccd_enrollment`
- **Portal endpoint(s):** `/school-districts/ccd/enrollment/{year}/{grade}/` (+ `/race/`, `/sex/`, `/race/sex/`)

---

## SAIPE (Small Area Income and Poverty Estimates)

### District Poverty — `saipe/districts_saipe`

- **Type / years:** Single-file · 1995, 1997, 1999-2024 (non-contiguous early years)
- **Grain:** one row per `leaid` × `year` (Census model-based district poverty estimate).
- **Key variables:** `district_id`, `district_name`, `est_population_total`, `est_population_5_17`, `est_population_5_17_pct`, `est_population_5_17_poverty`, `est_population_5_17_poverty_pct` (complete 10-var family: `variable-dictionary-saipe.md`).
- **Join keys:** `leaid` (+ `year`) to CCD district directory/finance and EDFacts.
- **Caveats:** `est_population_5_17_poverty_pct` is on a **0-1 scale despite the `_pct` suffix** — verify scale before treating as a percentage. No race/ethnicity disaggregation at district level (use ACS 5-year for that). ~18-month release lag. `saipe/districts_saipe` is a Polars-written parquet with `string_view` columns — the R arrow reader needs the view-safe pattern (see `education-data-query`).
- **Codebook:** `saipe/codebook_districts_saipe`
- **Portal endpoint(s):** `/school-districts/saipe/{year}/`

---

## EDFacts

### District Assessments — `edfacts/districts_edfacts_assessments_{year}`

- **Type / years:** Yearly · 2009-2018, 2020 (**2019 absent** — COVID testing waivers)
- **Grain:** one row per `leaid` × `year` × `grade_edfacts` × subgroup dimension. Subgroups are columns (`race`, `sex`, `lep`, `disability`, `econ_disadvantaged`, `homeless`, `migrant`, `foster_care`, `military_connected`).
- **Key variables:** `grade_edfacts`, `read_test_num_valid`, `read_test_pct_prof_midpt` (+ `_low`/`_high`), `math_test_num_valid`, `math_test_pct_prof_midpt` (+ `_low`/`_high`) (full 24-var list: `variable-dictionary-edfacts.md` § `edfacts/districts_edfacts_assessments_{year}`).
- **Join keys:** `leaid` (+ `year`, `grade_edfacts`, subgroup codes).
- **Caveats:** proficiency is **range-reported** (`_low`/`_midpt`/`_high`) for small-cell protection — use the midpoint and carry the range. `grade_edfacts` codes are `{3-8, 9="Grades 9-12", 99}` (distinct from CCD numeric `grade`). **State assessment scores cannot be compared across states** (different tests/cut scores). `disability` uses the full 0-4/99 scheme (see `variable-codes.md`).
- **Codebook:** `edfacts/codebook_districts_edfacts_assessments`
- **Portal endpoint(s):** `/school-districts/edfacts/assessments/{year}/{grade_edfacts}/` (+ `/race/`, `/sex/`, `/special-populations/`)

### District Graduation Rates — `edfacts/districts_edfacts_grad_rates_{year}`

- **Type / years:** Yearly · 2010-2019
- **Grain:** one row per `leaid` × `year` × subgroup (ACGR — adjusted cohort graduation rate).
- **Key variables:** `cohort_num`, `grad_rate_midpt` (+ `_low`/`_high`), plus subgroup columns `race`, `lep`, `disability`, `econ_disadvantaged`, `homeless`, `foster_care` (full 15-var list: `variable-dictionary-edfacts.md` § `edfacts/districts_edfacts_grad_rates_{year}`).
- **Join keys:** `leaid` (+ `year`, subgroup codes).
- **Caveats:** grad rate is **range-reported** (use `grad_rate_midpt`). ACGR is a 4-year adjusted cohort measure; not comparable to CCD/IPEDS completion counts.
- **Codebook:** `edfacts/codebook_districts_edfacts_graduation`
- **Portal endpoint(s):** `/school-districts/edfacts/grad-rates/{year}/`

---

## Common District Use Cases

| Question | Files (paths) | Join |
|----------|---------------|------|
| District characteristics + spending | `ccd/school-districts_lea_directory` + `ccd/districts_ccd_finance` | `leaid` + `year` |
| Poverty and achievement | `saipe/districts_saipe` + `edfacts/districts_edfacts_assessments_{year}` | `leaid` + `year` |
| Enrollment trends | `ccd/schools_ccd_lea_enrollment_{year}` (multi-year) | `leaid` + `year` (+ dimension totals) |
| Spending and graduation | `ccd/districts_ccd_finance` + `edfacts/districts_edfacts_grad_rates_{year}` | `leaid` + `year` |
