# Colleges Datasets Reference (mirror-first)

College/university-level mirror dataset families for the Urban Institute Education Data mirror. Each entry gives the **canonical mirror path** (the acquisition currency — extensionless `{source}/{filename}`, with `{year}` where the family is Yearly), the entity **grain**, **year coverage** (vintage 0.26.1), curated **key variables** (real names — full lists in `variable-dictionary-{source}.md`), **join keys**, **caveats**, a **codebook** path, and a small **Portal endpoint** annotation for citation/maintenance only.

> **Vintage:** all facts keyed to pinned mirror vintage **0.26.1** (revision `0ad00ce0e232c96b0642459e4e7326607a8d26aa`). The `urban_csv` fallback is unpinned/current-Portal. Primary ID at this level is `unitid` (IPEDS 6-digit integer Unit ID); federal-aid sources also carry `opeid` (8-digit Office of Postsecondary Education ID). Emit paths, not routes. Do not instruct fetching or probing — retrieval belongs to `education-data-query`.

---

## IPEDS (Integrated Postsecondary Education Data System)

IPEDS is the primary federal postsecondary source (~6,500 institutions). Its 32 mirror families are grouped thematically below — one entry per family. Every family carries `unitid`, `year`, `fips`; join any two on `unitid` (+ `year`).

### Directory & Institutional Profile

### IPEDS Directory — `ipeds/colleges_ipeds_directory`

- **Type / years:** Single-file · 1980, 1984-2024
- **Grain:** one row per `unitid` × `year` (institution directory record).
- **Key variables:** `inst_name`, `opeid`, `state_abbr`, `city`, `county_fips`, `sector`, `inst_control`, `institution_level`, `hbcu`, `carnegie` classifications (`cc_basic_2021`, `cc_basic_2025`), `longitude`, `latitude` (full 96-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_directory`).
- **Join keys:** `unitid` (+ `year`) — the canonical institution crosswalk for all college sources; `opeid` bridges to FSA/Scorecard.
- **Caveats:** the authoritative source for `sector`/`inst_control` used to interpret sector-free sources (EADA, NACUBO). Carnegie classification columns are vintage-stamped (2000-2025); pick the vintage that matches the analysis year rather than assuming one applies to all years.
- **Codebook:** `ipeds/codebook_colleges_ipeds_directory`
- **Portal endpoint(s):** `/college-university/ipeds/directory/{year}/`

### IPEDS Institutional Characteristics — `ipeds/colleges_ipeds_institutional-characteristics`

- **Type / years:** Single-file · 1980, 1984-2024
- **Grain:** one row per `unitid` × `year` (programs, services, and policies profile).
- **Key variables:** `inst_affiliation`, `bach_offered`, `masters_offered`, `doctors_research_offered`, `oncampus_housing`, `dormitory_capacity`, `calendar_system`, `religious_affiliation`, `member_ncaa`, `study_abroad`, `disability_percentage` (full 128-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_institutional-characteristics`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** offering flags are `yes/no` indicators, not counts. Distinct from `directory` — this file describes what the institution *offers/does*, the directory describes *who/where it is*.
- **Codebook:** `ipeds/codebook_colleges_ipeds_institutional-characteristics`
- **Portal endpoint(s):** `/college-university/ipeds/institutional-characteristics/{year}/`

### IPEDS Academic Libraries — `ipeds/colleges_ipeds_academic_libraries`

- **Type / years:** Single-file · 2013-2023
- **Grain:** one row per `unitid` × `year` (library collections, circulation, staffing, expenditures).
- **Key variables:** `physical_books`, `electronic_books`, `total_collections`, `total_circulations`, `interlibrary_loans_provided`, `exp_total`, `librarians_fte`, `total_lib_staff_fte` (full 42-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_academic_libraries`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** collection/expenditure counts carry `-1`/`-2`/`-3` sentinels for missing/NA/suppressed.
- **Codebook:** `ipeds/codebook_colleges_ipeds_academic-libraries`
- **Portal endpoint(s):** `/college-university/ipeds/academic-libraries/{year}/`

### Admissions & Enrollment

### IPEDS Admissions & Enrollment — `ipeds/colleges_ipeds_admissions-enrollment`

- **Type / years:** Single-file · 2001-2024
- **Grain:** one row per `unitid` × `year` × `sex` (filter `sex=99` for institution total). Applications/admissions/matriculation counts.
- **Key variables:** `number_applied`, `number_admitted`, `number_enrolled_ft`, `number_enrolled_pt`, `number_enrolled_total` (complete 9-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_admissions-enrollment`).
- **Join keys:** `unitid` (+ `year`, `sex`).
- **Caveats:** admit rate = `number_admitted`/`number_applied`; yield = `number_enrolled_total`/`number_admitted`. `sex` uses the Portal scheme (`1` Male, `2` Female, `9` Unknown, `99` Total) — filter to the `99` total to avoid double-counting.
- **Codebook:** `ipeds/codebook_colleges_ipeds_admissions-enrollment`
- **Portal endpoint(s):** `/college-university/ipeds/admissions-enrollment/{year}/`

### IPEDS Admissions Requirements & Test Scores — `ipeds/colleges_ipeds_admissions-requirements`

- **Type / years:** Single-file · 1990-2022
- **Grain:** one row per `unitid` × `year` (admissions policies + SAT/ACT score percentiles).
- **Key variables:** `open_admissions_policy`, `reqt_hs_gpa`, `reqt_test_scores`, `sat_percent_submitting`, `act_percent_submitting`, `sat_crit_read_25_pctl`, `sat_math_75_pctl`, `act_composite_25_pctl`, `act_composite_75_pctl` (full 48-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_admissions-requirements`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** `reqt_*` columns are ordinal requirement codes (`0` neither, `1` required, `2` recommended, `3` considered), not booleans. Percentile score columns are absent for open-admissions institutions.
- **Codebook:** `ipeds/codebook_colleges_ipeds_admissions-requirements`
- **Portal endpoint(s):** `/college-university/ipeds/admissions-requirements/{year}/`

### IPEDS Fall Enrollment by Race/Sex — `ipeds/colleges_ipeds_fall-enrollment-race_{year}`

- **Type / years:** Yearly (one file per year) · 1986-2024
- **Grain:** one row per `unitid` × `year` × `sex` × `race` × `ftpt` × `level_of_study` × `degree_seeking` × `class_level`. Disaggregation dimensions are **columns** — filter to the `99`/total code on each for an institution total.
- **Key variables:** `enrollment_fall`, plus dimension columns `sex`, `race`, `ftpt`, `level_of_study`, `degree_seeking`, `class_level` (complete 10-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_fall-enrollment-race_{year}`).
- **Join keys:** `unitid` (+ `year`, dimension codes).
- **Caveats:** Yearly — fetch each needed year and concatenate. Do not sum across dimension levels when a `99` total row exists (double-counts).
- **Codebook:** `ipeds/codebook_colleges_ipeds_fall-enrollment-race`
- **Portal endpoint(s):** `/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/`

### IPEDS Fall Enrollment by Age/Sex — `ipeds/colleges_ipeds_fall-enrollment-age_{year}`

- **Type / years:** Yearly · 1991, 1993, 1995, 1997, and 1999-2024 (biennial before 1999)
- **Grain:** one row per `unitid` × `year` × `sex` × `age` × `ftpt` × `level_of_study` × `degree_seeking`.
- **Key variables:** `enrollment_fall`, plus dimension columns `sex`, `age`, `ftpt`, `level_of_study`, `degree_seeking` (complete 9-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_fall-enrollment-age_{year}`).
- **Join keys:** `unitid` (+ `year`, dimension codes).
- **Caveats:** Yearly; age reported only in select (mostly odd) years before 1999 — check the coverage list before assuming a year exists.
- **Codebook:** `ipeds/codebook_colleges_ipeds_fall-enrollment-age`
- **Portal endpoint(s):** `/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/age/sex/`

### IPEDS Fall Enrollment by Residence — `ipeds/colleges_ipeds_fall-res`

- **Type / years:** Single-file · 1986, 1988, 1992, 1994, 1996, 1998, 2000-2024 (biennial before 2000)
- **Grain:** one row per `unitid` × `year` × `state_of_residence` × `type_of_freshman` (first-time freshmen by home state).
- **Key variables:** `enrollment_fall`, `state_of_residence`, `type_of_freshman` (complete 6-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_fall-res`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** covers first-time freshmen migration only, not total enrollment. Biennial before 2000.
- **Codebook:** `ipeds/codebook_colleges_ipeds_fall-enrollment-residence`
- **Portal endpoint(s):** `/college-university/ipeds/fall-enrollment/{year}/residence/`

### IPEDS 12-Month FTE Enrollment — `ipeds/colleges_ipeds_enrollment-fte`

- **Type / years:** Single-file · 1997-2023
- **Grain:** one row per `unitid` × `year` × `level_of_study` (12-month instructional activity + estimated FTE).
- **Key variables:** `credit_hours`, `contact_hours`, `est_fte`, `rep_fte`, `acttype`, `level_of_study` (complete 9-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_enrollment-fte`).
- **Join keys:** `unitid` (+ `year`, `level_of_study`).
- **Caveats:** FTE is derived from instructional activity, distinct from fall headcount. `est_fte` (estimated) vs `rep_fte` (reported) can differ.
- **Codebook:** `ipeds/codebook_colleges_ipeds_enrollment-fte`
- **Portal endpoint(s):** `/college-university/ipeds/enrollment-full-time-equivalent/{year}/{level_of_study}/`

### IPEDS 12-Month Unduplicated Headcount — `ipeds/colleges_ipeds_headcount`

- **Type / years:** Single-file · 1996-2021
- **Grain:** one row per `unitid` × `year` × `level_of_study` × `sex` × `race` (unduplicated 12-month headcount).
- **Key variables:** `headcount`, plus dimensions `level_of_study`, `sex`, `race` (complete 7-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_headcount`).
- **Join keys:** `unitid` (+ `year`, dimension codes).
- **Caveats:** unduplicated 12-month count — larger than fall headcount; do not compare directly to fall enrollment.
- **Codebook:** `ipeds/codebook_colleges_ipeds_enrollment-headcount`
- **Portal endpoint(s):** `/college-university/ipeds/enrollment-headcount/{year}/{level_of_study}/`

### Completions (Degrees & Certificates)

### IPEDS Completions by 2-digit CIP — `ipeds/colleges_ipeds_completions-2digcip_{year}`

- **Type / years:** Yearly · 1991-2022, plus a **2023** v2-build addition (see caveat)
- **Grain:** one row per `unitid` × `year` × `cipcode` (2-digit field) × `award_level` × `majornum` × `sex` × `race`.
- **Key variables:** `awards`, plus dimensions `cipcode`, `award_level`, `majornum`, `sex`, `race` (complete 9-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_completions-2digcip_{year}`).
- **Join keys:** `unitid` (+ `year`, `cipcode`, `award_level`).
- **Caveats:** Yearly. `award_level` uses the full Portal scheme (`4` associate's, `7` bachelor's, `9` master's, `22/23` doctoral variants; codes `20/21` are the pre-2008 doctoral/first-professional labels) — see `variable-codes.md`. The **2023** shard (`ipeds/colleges_ipeds_completions-2digcip_2023`) exists as a mirror file in the v2 build but was not bridged to a Portal endpoint at vintage capture; treat it as present-but-unbridged.
- **Codebook:** `ipeds/codebook_colleges_ipeds_completions-2digcip`
- **Portal endpoint(s):** `/college-university/ipeds/completions-cip-2/{year}/`

### IPEDS Completions by 6-digit CIP — `ipeds/colleges_ipeds_completions-6digcip_{year}`

- **Type / years:** Yearly · 1983-2023 (the 2023 shard is a v2-build addition; bridged shards run 1983-2022)
- **Grain:** one row per `unitid` × `year` × `cipcode_6digit` (detailed program) × `award_level` × `majornum` × `sex` × `race`.
- **Key variables:** `awards_6digit`, plus dimensions `cipcode_6digit`, `award_level`, `majornum`, `sex`, `race` (complete 9-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_completions-6digcip_{year}`).
- **Join keys:** `unitid` (+ `year`, `cipcode_6digit`, `award_level`).
- **Caveats:** Yearly; the largest IPEDS family by row count (fine-grained program detail). The **2023** shard (`ipeds/colleges_ipeds_completions-6digcip_2023`) is a v2-build mirror file unbridged to a Portal endpoint at vintage capture. Use the 2-digit family when program granularity below CIP-2 is not needed.
- **Codebook:** `ipeds/codebook_colleges_ipeds_completions-6digcip`
- **Portal endpoint(s):** `/college-university/ipeds/completions-cip-6/{year}/`

### IPEDS Completers (Unduplicated) — `ipeds/colleges_ipeds_completers`

- **Type / years:** Single-file · 2011-2021
- **Grain:** one row per `unitid` × `year` × `sex` × `race` (unduplicated count of award recipients).
- **Key variables:** `completers`, plus dimensions `sex`, `race` (complete 6-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_completers`).
- **Join keys:** `unitid` (+ `year`, dimension codes).
- **Caveats:** counts distinct *students* who completed, not *awards* — use this (not `completions-*`) when a headcount of graduates is wanted, since one student can earn multiple awards.
- **Codebook:** `ipeds/codebook_colleges_ipeds_completers`
- **Portal endpoint(s):** `/college-university/ipeds/completers/{year}/`

### Charges, Prices & Student Financial Aid

### IPEDS Academic-Year Tuition & Fees — `ipeds/colleges_ipeds_ay_tuition_fees`

- **Type / years:** Single-file · 1986-2023
- **Grain:** one row per `unitid` × `year` × `level_of_study` × `tuition_type` (in/out-of-state).
- **Key variables:** `tuition_fees_ft`, `tuition_ft`, `fees_ft`, `credit_hour_charge_pt`, `tuition_published`, `tuition_fees_published` (full 14-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_ay_tuition_fees`).
- **Join keys:** `unitid` (+ `year`, `level_of_study`, `tuition_type`).
- **Caveats:** `tuition_type` distinguishes in-district/in-state/out-of-state — always filter to the intended type. Dollar figures are nominal (not inflation-adjusted).
- **Codebook:** `ipeds/codebook_colleges_ipeds_ay_tuition_fees`
- **Portal endpoint(s):** `/college-university/ipeds/academic-year-tuition/{year}/`

### IPEDS Academic-Year Room/Board & Other Costs — `ipeds/colleges_ipeds_ay_room_board_other`

- **Type / years:** Single-file · 1999-2023
- **Grain:** one row per `unitid` × `year` × `level_of_study` × `living_arrangement`.
- **Key variables:** `room_board`, `books_supplies`, `exp_other`, `living_arrangement`, `level_of_study` (complete 8-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_ay_room_board_other`).
- **Join keys:** `unitid` (+ `year`, `level_of_study`, `living_arrangement`).
- **Caveats:** pairs with `ay_tuition_fees` to build total cost of attendance. `living_arrangement` (on/off campus) matters for net-price studies.
- **Codebook:** `ipeds/codebook_colleges_ipeds_ay_room_board_other`
- **Portal endpoint(s):** `/college-university/ipeds/academic-year-room-board-other/{year}/`

### IPEDS Program-Year Tuition by CIP — `ipeds/colleges_ipeds_py_tuition_cip`

- **Type / years:** Single-file · 1987-2023
- **Grain:** one row per `unitid` × `year` × `cipcode_6digit` × `program_size_rank` (program-reporter charges).
- **Key variables:** `tuition_fees`, `books_supplies`, `enrollment`, `program_length_hours`, `program_length_weeks`, `average_length_months` (full 15-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_py_tuition_cip`).
- **Join keys:** `unitid` (+ `year`, `cipcode_6digit`).
- **Caveats:** covers program-reporter institutions (e.g., cosmetology, trade programs) that charge by program, not academic year — a different institutional universe than `ay_tuition_fees`.
- **Codebook:** `ipeds/codebook_colleges_ipeds_py_tuition_cip`
- **Portal endpoint(s):** `/college-university/ipeds/program-year-tuition-cip/{year}/`

### IPEDS Program-Year Room/Board & Other — `ipeds/colleges_ipeds_py_room_board_other`

- **Type / years:** Single-file · 1999-2023
- **Grain:** one row per `unitid` × `year` × `living_arrangement`.
- **Key variables:** `room_board`, `exp_other`, `living_arrangement` (complete 6-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_py_room_board_other`).
- **Join keys:** `unitid` (+ `year`, `living_arrangement`).
- **Caveats:** program-reporter counterpart to `ay_room_board_other`.
- **Codebook:** `ipeds/codebook_colleges_ipeds_py_room_board_other`
- **Portal endpoint(s):** `/college-university/ipeds/program-year-room-board-other/{year}/`

### IPEDS First-Professional Tuition — `ipeds/colleges_ipeds_ay_tuition_firstprof`

- **Type / years:** Single-file · 1986-2008, 2010-2023 (2009 absent)
- **Grain:** one row per `unitid` × `year` × `prof_program` (medicine, law, etc.) × `tuition_type`.
- **Key variables:** `tuition_fees`, `tuition`, `fees`, `prof_program`, `tuition_type` (complete 8-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_ay_tuition_firstprof`).
- **Join keys:** `unitid` (+ `year`, `prof_program`, `tuition_type`).
- **Caveats:** first-professional programs only (`prof_program` codes: medicine, law, dentistry, etc.). 2009 not in coverage.
- **Codebook:** `ipeds/codebook_colleges_ipeds_ay_tuition_firstprof`
- **Portal endpoint(s):** `/college-university/ipeds/academic-year-tuition-prof-program/{year}/`

### IPEDS SFA — All Undergraduates — `ipeds/colleges_ipeds_sfa_all_undergrads`

- **Type / years:** Single-file · 2007-2021
- **Grain:** one row per `unitid` × `year` × `ftpt` × `level_of_study` × `type_of_aid`.
- **Key variables:** `number_of_students`, `percent_of_students`, `average_amount`, `total_amount`, `type_of_aid` (complete 10-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_sfa_all_undergrads`).
- **Join keys:** `unitid` (+ `year`, `type_of_aid`).
- **Caveats:** `type_of_aid` distinguishes federal grants, state/local grants, institutional grants, loans — filter to the aid type of interest.
- **Codebook:** `ipeds/codebook_colleges_ipeds_sfa_all_undergrads`
- **Portal endpoint(s):** `/college-university/ipeds/sfa-all-undergraduates/{year}/`

### IPEDS SFA — First-Time Full-Time — `ipeds/colleges_ipeds_sfa_ftft`

- **Type / years:** Single-file · 1999-2021
- **Grain:** one row per `unitid` × `year` × `ftpt` × `level_of_study` × `type_of_aid` (first-time full-time cohort).
- **Key variables:** `number_of_students`, `percent_of_students`, `average_amount`, `total_amount`, `type_of_aid`, `class_level` (complete 12-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_sfa_ftft`).
- **Join keys:** `unitid` (+ `year`, `type_of_aid`).
- **Caveats:** FTFT cohort — the standard denominator for first-year net-price and aid-receipt studies; not comparable to `sfa_all_undergrads` counts.
- **Codebook:** `ipeds/codebook_colleges_ipeds_sfa_FTFT`
- **Portal endpoint(s):** `/college-university/ipeds/sfa-ftft/{year}/`

### IPEDS SFA — Grants & Net Price — `ipeds/colleges_ipeds_sfa_grants_and_net_price`

- **Type / years:** Single-file · 2008-2021
- **Grain:** one row per `unitid` × `year` × `income_level` × dimension columns (net price by family income band).
- **Key variables:** `net_price`, `average_grant`, `total_grant`, `number_of_students`, `number_receiving_grants`, `income_level` (full 14-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_sfa_grants_and_net_price`).
- **Join keys:** `unitid` (+ `year`, `income_level`).
- **Caveats:** `net_price` is reported by `income_level` band — the primary source for income-conditional net price. Filter to the intended income band.
- **Codebook:** `ipeds/codebook_colleges_ipeds_sfa_grants_and_net_price`
- **Portal endpoint(s):** `/college-university/ipeds/sfa-grants-and-net-price/{year}/`

### IPEDS SFA — By Living Arrangement — `ipeds/colleges_ipeds_sfa_by_living_arrangement`

- **Type / years:** Single-file · 2008-2021
- **Grain:** one row per `unitid` × `year` × `living_arrangement` × aid/cohort dimensions.
- **Key variables:** `number_of_students`, `living_arrangement`, `type_of_aid`, `tuition_type`, `class_level` (complete 11-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_sfa_by_living_arrangement`).
- **Join keys:** `unitid` (+ `year`, dimension codes).
- **Caveats:** student counts only (no dollar amounts) — a distributional breakout, not an aid-value file.
- **Codebook:** `ipeds/codebook_colleges_ipeds_sfa_by_living_arrangement`
- **Portal endpoint(s):** `/college-university/ipeds/sfa-by-living-arrangement/{year}/`

### IPEDS SFA — By Tuition Type — `ipeds/colleges_ipeds_sfa_by_tuition_type`

- **Type / years:** Single-file · 1999-2021
- **Grain:** one row per `unitid` × `year` × `tuition_type` × `type_of_cohort` × cohort dimensions.
- **Key variables:** `number_of_students`, `percent_of_cohort`, `percent_of_undergrads`, `tuition_type`, `type_of_cohort` (complete 11-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_sfa_by_tuition_type`).
- **Join keys:** `unitid` (+ `year`, `tuition_type`).
- **Caveats:** counts/shares of the cohort paying in-state vs out-of-state tuition; no dollar values.
- **Codebook:** `ipeds/codebook_colleges_ipeds_sfa_by_tuition_type`
- **Portal endpoint(s):** `/college-university/ipeds/sfa-by-tuition-type/{year}/`

### Finance & Staffing

### IPEDS Finance — `ipeds/colleges_ipeds_finance`

- **Type / years:** Single-file · 1979, 1983-2017 (probed 2026-08-08 at the pinned revision — see caveat)
- **Grain:** one row per `unitid` × `year` (institutional revenues, expenditures, assets, endowment).
- **Key variables:** `rev_total_current`, `rev_tuition_fees_net`, `rev_appropriations_state`, `rev_investment_return`, `exp_total_current`, `exp_instruc_total`, `endowment_end`, `assets`, `liabilities`, `reporting_form`, `form_type` (full 141-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_finance`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** **GASB/FASB care** — public institutions report under GASB, private under FASB; the two accounting standards define revenue/expense categories differently, so cross-standard comparisons and pooled aggregates require reconciling via `reporting_form`/`form_type`/`gasb_alternative_accounting`. **Year coverage (settled by observation):** a 2026-08-08 probe of the pinned mirror parquet (`inspect_finance_mirror_years.py`) returned `year_min=1979`, `year_max=2017`, distinct years {1979, 1983-2017}, `contains_2018_plus=False`, over 227,000 rows — so mirror finance coverage is **1979, 1983-2017** at the pinned revision, matching the live API. There is no post-2017 overhang; the old docs' "1987-2022" coverage claim was fabricated. Re-derive coverage at any later mirror vintage.
- **Codebook:** `ipeds/codebook_colleges_ipeds_finance`
- **Portal endpoint(s):** `/college-university/ipeds/finance/{year}/`

### IPEDS Instructional Staff Salaries — `ipeds/colleges_ipeds_salaries_is`

- **Type / years:** Single-file · 1980, 1984, 1985, 1987, 1989-1999, 2001-2024 (non-contiguous early years)
- **Grain:** one row per `unitid` × `year` × `academic_rank` × `contract_length` × `sex`.
- **Key variables:** `instruc_staff_count`, `average_salary`, `salary_outlays`, `avg_wgtd_mon_salary`, `academic_rank`, `contract_length` (complete 11-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_salaries_is`).
- **Join keys:** `unitid` (+ `year`, `academic_rank`, `sex`).
- **Caveats:** salaries reported by rank and contract length; `avg_wgtd_mon_salary` normalizes for 9- vs 12-month contracts. Non-contiguous coverage before 2001.
- **Codebook:** `ipeds/codebook_colleges_ipeds_instructional_staff_salaries`
- **Portal endpoint(s):** `/college-university/ipeds/salaries-instructional-staff/{year}/`

### IPEDS Non-Instructional Staff Salaries — `ipeds/colleges_ipeds_salaries_nis`

- **Type / years:** Single-file · 2012-2024
- **Grain:** one row per `unitid` × `year` × `staff_category`.
- **Key variables:** `noninstruc_staff_count`, `salary_outlays`, `staff_category` (complete 6-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_salaries_nis`).
- **Join keys:** `unitid` (+ `year`, `staff_category`).
- **Caveats:** aggregate outlays per staff category (no per-person average column — compute from `salary_outlays`/`noninstruc_staff_count`).
- **Codebook:** `ipeds/codebook_colleges_ipeds_noninstructional_staff_salaries`
- **Portal endpoint(s):** `/college-university/ipeds/salaries-noninstructional-staff/{year}/`

### IPEDS Student-Faculty Ratio — `ipeds/colleges_ipeds_student-faculty-ratio`

- **Type / years:** Single-file · 2009-2024
- **Grain:** one row per `unitid` × `year`.
- **Key variables:** `student_faculty_ratio` (complete 4-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_student-faculty-ratio`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** a single reported ratio per institution-year; carries the usual `-1`/`-2`/`-3` sentinels.
- **Codebook:** `ipeds/codebook_colleges_ipeds_student-faculty-ratio`
- **Portal endpoint(s):** `/college-university/ipeds/student-faculty-ratio/{year}/`

### Outcomes (Graduation, Retention, Outcome Measures)

### IPEDS Graduation Rates (150%) — `ipeds/colleges_ipeds_grad-rates`

- **Type / years:** Single-file · 1996-2023
- **Grain:** one row per `unitid` × `year` × `race` × `sex` × `subcohort` (first-time full-time cohort graduation).
- **Key variables:** `completion_rate_150pct`, `completers_150pct`, `completers_100pct`, `cohort_rev`, `cohort_adj_150pct`, `transfers_out`, `institution_level`, `subcohort` (full 18-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_grad-rates`).
- **Join keys:** `unitid` (+ `year`, `race`, `sex`, `subcohort`).
- **Caveats:** **grad rates = first-time, full-time (FTFT) cohort** — excludes transfer and part-time entrants (a well-known coverage limitation). **Vintage revaluation:** this family was retroactively revalued in Portal 0.26.1 (now spanning 1996-2023); a rerun that must reproduce pre-2026q3 results has to pin the predecessor mirror vintage rather than 0.26.1. Rate is within 150% of normal time (6 years for a 4-year program).
- **Codebook:** `ipeds/codebook_colleges_ipeds_grad-rates`
- **Portal endpoint(s):** `/college-university/ipeds/grad-rates/{year}/`

### IPEDS Graduation Rates (200%) — `ipeds/colleges_ipeds_grad-rates-200pct`

- **Type / years:** Single-file · 2007-2023
- **Grain:** one row per `unitid` × `year` × `institution_level` (extended-time completion).
- **Key variables:** `completion_rate_100pct`, `completion_rate_150pct`, `completion_rate_200pct`, `completers_200pct`, `cohort_adj_200pct`, `add_exclusions` (full 17-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_grad-rates-200pct`).
- **Join keys:** `unitid` (+ `year`, `institution_level`).
- **Caveats:** FTFT cohort; extends the 150% window to 200% of normal time. Not disaggregated by race/sex (unlike the 150% family).
- **Codebook:** `ipeds/codebook_colleges_ipeds_grad-rates-200pct`
- **Portal endpoint(s):** `/college-university/ipeds/grad-rates-200pct/{year}/`

### IPEDS Graduation Rates — Pell — `ipeds/colleges_ipeds_grad-rates-pell`

- **Type / years:** Single-file · 2015-2023
- **Grain:** one row per `unitid` × `year` × `fed_aid_type` × `subcohort` (completion by federal-aid receipt).
- **Key variables:** `completion_rate_150pct`, `completers_150pct`, `cohort_rev`, `cohort_adj`, `fed_aid_type` (complete 12-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_grad-rates-pell`).
- **Join keys:** `unitid` (+ `year`, `fed_aid_type`).
- **Caveats:** FTFT cohort split by `fed_aid_type` (Pell recipients, Stafford-loan-no-Pell, neither) — the source for Pell vs non-Pell graduation gaps.
- **Codebook:** `ipeds/codebook_colleges_ipeds_grad-rates-pell`
- **Portal endpoint(s):** `/college-university/ipeds/grad-rates-pell/{year}/`

### IPEDS Fall Retention — `ipeds/colleges_ipeds_fall-retention`

- **Type / years:** Single-file · 2003-2024
- **Grain:** one row per `unitid` × `year` × `ftpt` (first-year retention).
- **Key variables:** `retention_rate`, `returning_students`, `prev_cohort`, `prev_cohort_adj`, `ftpt` (complete 10-var family: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_fall-retention`).
- **Join keys:** `unitid` (+ `year`, `ftpt`).
- **Caveats:** retention is measured for the full-time and part-time first-year cohorts separately (`ftpt`); one-year measure, distinct from graduation.
- **Codebook:** `ipeds/codebook_colleges_ipeds_fall-retention`
- **Portal endpoint(s):** `/college-university/ipeds/fall-retention/{year}/`

### IPEDS Outcome Measures — `ipeds/colleges_ipeds_outcome-measures`

- **Type / years:** Single-file · 2015-2021
- **Grain:** one row per `unitid` × `year` × `ftpt` × `class_level` × `fed_aid_type` (8-year outcomes for all entrants).
- **Key variables:** `completion_rate_6yr`, `completion_rate_8yr`, `completers_6yr`, `still_enroll_8yr`, `transfer_8yr`, `cohort_adj_8yr` (full 41-var list: `variable-dictionary-ipeds.md` § `ipeds/colleges_ipeds_outcome-measures`).
- **Join keys:** `unitid` (+ `year`, `ftpt`, `class_level`, `fed_aid_type`).
- **Caveats:** designed to cover **all entering degree/certificate-seekers** (including part-time and non-first-time), addressing the FTFT-only limitation of `grad-rates`. Tracks awards, transfer, and still-enrolled at 4/6/8 years.
- **Codebook:** `ipeds/codebook_colleges_ipeds_outcome-measures`
- **Portal endpoint(s):** `/college-university/ipeds/outcome-measures/{year}/`

---

## College Scorecard

Post-enrollment outcomes linking Title IV aid records to IRS/Treasury data (six mirror families). All join to IPEDS on `unitid`; `opeid`/`opeid6` bridge to FSA.

### Scorecard Earnings — `scorecard/colleges_scorecard_earnings`

- **Type / years:** Single-file · 2003-2014, 2018
- **Grain:** one row per `unitid` × `year` × `years_after_entry` × `cohort_year` (post-entry earnings distribution).
- **Key variables:** `earnings_mean`, `earnings_med`, `earnings_pct10`, `earnings_pct25`, `earnings_pct75`, `earnings_pct90`, `earnings_greater_than_25k_pct`, `count_working` (full 33-var list: `variable-dictionary-scorecard.md` § `scorecard/colleges_scorecard_earnings`).
- **Join keys:** `unitid` (+ `year`, `years_after_entry`); `opeid`/`opeid6` to FSA.
- **Caveats:** **Title IV aid recipients only** — earnings cover the federally-aided student population, not all graduates (differs from PSEO's LEHD universe). Measured at fixed years-after-entry; income-tercile and sex breakouts available.
- **Codebook:** `scorecard/codebook_colleges_scorecard_earnings`
- **Portal endpoint(s):** `/college-university/scorecard/earnings/{year}/`

### Scorecard Institutional Characteristics — `scorecard/colleges_scorecard_inst_characteristics`

- **Type / years:** Single-file · 1996-2020
- **Grain:** one row per `unitid` × `year` (Scorecard-specific institution profile).
- **Key variables:** `pred_degree_awarded_ipeds`, `accreditor`, `under_investigation`, `currently_operating`, `min_serving_hispanic`, `min_serving_historic_black`, `menonly`, `womenonly` (full 27-var list: `variable-dictionary-scorecard.md` § `scorecard/colleges_scorecard_inst_characteristics`).
- **Join keys:** `unitid` (+ `year`); `opeid`/`opeid6`.
- **Caveats:** minority-serving flags and `under_investigation` (Heightened Cash Monitoring) are Scorecard-specific; for the canonical directory use IPEDS `directory`.
- **Codebook:** `scorecard/codebook_colleges_scorecard_institutional-characteristics`
- **Portal endpoint(s):** `/college-university/scorecard/institutional-characteristics/{year}/`

### Scorecard Default Rates — `scorecard/colleges_scorecard_repayment_fsa`

- **Type / years:** Single-file · 1996-2020
- **Grain:** one row per `unitid` × `year` × `years_since_entering_repay` (cohort default rate).
- **Key variables:** `default_rate`, `default_rate_denom`, `years_since_entering_repay`, `cohort_year` (complete 9-var family: `variable-dictionary-scorecard.md` § `scorecard/colleges_scorecard_repayment_fsa`).
- **Join keys:** `unitid` (+ `year`); `opeid`.
- **Caveats:** Title IV borrowers only. Note the mirror filename (`repayment_fsa`) maps to the Portal `default` route — this is the **cohort default rate** file (distinct from `repayment_nslds`).
- **Codebook:** `scorecard/codebook_colleges_scorecard_default`
- **Portal endpoint(s):** `/college-university/scorecard/default/{year}/`

### Scorecard Repayment Rates — `scorecard/colleges_scorecard_repayment_nslds`

- **Type / years:** Single-file · 2007-2016
- **Grain:** one row per `unitid` × `year` × `years_since_entering_repay` (loan repayment progress).
- **Key variables:** `repay_rate`, `repay_rate_lowincome`, `repay_rate_pell`, `repay_rate_female`, `repay_rate_firstgen`, `repay_count` (full 31-var list: `variable-dictionary-scorecard.md` § `scorecard/colleges_scorecard_repayment_nslds`).
- **Join keys:** `unitid` (+ `year`); `opeid`.
- **Caveats:** `repay_rate` = share not in default with declining balance (rolling averages); rich subgroup breakouts (income, Pell, sex, first-gen). Distinct from the default-rate file above.
- **Codebook:** `scorecard/codebook_colleges_scorecard_repayment`
- **Portal endpoint(s):** `/college-university/scorecard/repayment/{year}/`

### Scorecard Student Body (Aid Applicants) — `scorecard/colleges_scorecard_student_body_nslds`

- **Type / years:** Single-file · 1997-2016
- **Grain:** one row per `unitid` × `year` (aided-student demographic/income composition).
- **Key variables:** `faminc_mean`, `faminc_med`, `lowincome_pct`, `first_gen_student_pct`, `female_pct`, `dependent_pct`, `age_24orolder_pct`, `veteran_pct`, `fafsa_sent_2ormore_pct` (full 52-var list: `variable-dictionary-scorecard.md` § `scorecard/colleges_scorecard_student_body_nslds`).
- **Join keys:** `unitid` (+ `year`); `opeid`.
- **Caveats:** describes the **aid-applicant** population (FAFSA/NSLDS-derived), not the full student body. Income figures in real 2015 dollars where noted.
- **Codebook:** `scorecard/codebook_colleges_scorecard_student-characteristics_aid-applicants`
- **Portal endpoint(s):** `/college-university/scorecard/student-characteristics/{year}/aid-applicants/`

### Scorecard Student Body (Home Neighborhood) — `scorecard/colleges_scorecard_student_body_treasury`

- **Type / years:** Single-file · 1997-2016
- **Grain:** one row per `unitid` × `year` (Treasury/census home-ZIP context of the earnings cohort).
- **Key variables:** `age_entry`, `hhinc_home_zip_med`, `poverty_rate_home_zip`, `unemp_rate_home_zip`, `bach_home_zip_pct`, `white_home_zip_pct`, `black_home_zip_pct`, `hispanic_home_zip_pct` (full 17-var list: `variable-dictionary-scorecard.md` § `scorecard/colleges_scorecard_student_body_treasury`).
- **Join keys:** `unitid` (+ `year`); `opeid`.
- **Caveats:** demographics are **home-ZIP census aggregates** of the earnings cohort, not individual student attributes — an ecological proxy, not a direct measure.
- **Codebook:** `scorecard/codebook_colleges_scorecard_student-characteristics_home-neighborhood`
- **Portal endpoint(s):** `/college-university/scorecard/student-characteristics/{year}/home-neighborhood/`

---

## FSA (Federal Student Aid)

Title IV aid volume at the institution level. All carry `unitid` and `opeid`; several report by both IDs (see per-ID column pairs). Join to IPEDS on `unitid`, to Scorecard on `opeid`.

### FSA Grants — `fsa/colleges_fsa_grants`

- **Type / years:** Single-file · 1999-2021
- **Grain:** one row per `unitid` × `year` × `grant_type` (Pell and other Title IV grants).
- **Key variables:** `grant_type`, `grant_recipients_unitid`, `value_grants_disbursed_unitid`, `grant_recipients_opeid`, `value_grants_disbursed_opeid`, `inst_name_fsa` (full 14-var list: `variable-dictionary-fsa.md` § `fsa/colleges_fsa_grants`).
- **Join keys:** `unitid` and/or `opeid` (+ `year`, `grant_type`).
- **Caveats:** counts/dollars reported by both unit ID and OPEID — pick one consistently; `allocation_flag`/`combined_flag` mark institutions where one ID spans multiple of the other.
- **Codebook:** `fsa/codebook_colleges_fsa_grants`
- **Portal endpoint(s):** `/college-university/fsa/grants/{year}/`

### FSA Loans — `fsa/colleges_fsa_loans`

- **Type / years:** Single-file · 1999-2021
- **Grain:** one row per `unitid` × `year` × `loan_type` (Direct/PLUS loan volume).
- **Key variables:** `loan_type`, `loan_recipients_unitid`, `num_loans_originated_unitid`, `value_loans_originated_unitid`, `value_loan_disbursements_unitid`, `loan_recipients_opeid` (full 18-var list: `variable-dictionary-fsa.md` § `fsa/colleges_fsa_loans`).
- **Join keys:** `unitid` and/or `opeid` (+ `year`, `loan_type`).
- **Caveats:** distinguishes originated vs disbursed volume; reported by both IDs. Filter to `loan_type` (subsidized, unsubsidized, PLUS).
- **Codebook:** `fsa/codebook_colleges_fsa_loans`
- **Portal endpoint(s):** `/college-university/fsa/loans/{year}/`

### FSA Campus-Based Aid Volume — `fsa/colleges_fsa_campus_based_volume`

- **Type / years:** Single-file · 2001-2021
- **Grain:** one row per `unitid` × `year` × `award_type` (FSEOG, Federal Work-Study, Perkins).
- **Key variables:** `award_type`, `campus_award_recipients_unitid`, `value_campus_disbursed_unitid`, `campus_award_fed_contr_unitid`, `campus_award_recipients_opeid` (full 15-var list: `variable-dictionary-fsa.md` § `fsa/colleges_fsa_campus_based_volume`).
- **Join keys:** `unitid` and/or `opeid` (+ `year`, `award_type`).
- **Caveats:** `campus_award_fed_contr_*` isolates the federal share (vs institutional match). Reported by both IDs.
- **Codebook:** `fsa/codebook_colleges_fsa_campus_based_volume`
- **Portal endpoint(s):** `/college-university/fsa/campus-based-volume/{year}/`

### FSA Financial Responsibility (Composite Scores) — `fsa/colleges_fsa_composite_scores`

- **Type / years:** Single-file · 2006-2016
- **Grain:** one row per `unitid` × `year` (ED financial-responsibility composite score).
- **Key variables:** `financial_resp_score`, `inst_group_name`, `multicampus_flag`, `inst_name_fsa` (complete 8-var family: `variable-dictionary-fsa.md` § `fsa/colleges_fsa_composite_scores`).
- **Join keys:** `unitid`/`opeid` (+ `year`).
- **Caveats:** composite score applies chiefly to private institutions (public institutions are generally exempt). Note the mirror filename (`composite_scores`) maps to the Portal `financial-responsibility` route.
- **Codebook:** `fsa/codebook_colleges_fsa_financial_responsibility`
- **Portal endpoint(s):** `/college-university/fsa/financial-responsibility/{year}/`

### FSA 90/10 Revenue Percentages — `fsa/colleges_fsa_90_10_revenue_percentages`

- **Type / years:** Single-file · 2014-2021
- **Grain:** one row per `unitid` × `year` (proprietary-school 90/10 revenue test).
- **Key variables:** `rev_pct_90_10`, `numerator_90_10`, `denominator_90_10`, `inst_name_fsa` (complete 8-var family: `variable-dictionary-fsa.md` § `fsa/colleges_fsa_90_10_revenue_percentages`).
- **Join keys:** `unitid`/`opeid` (+ `year`).
- **Caveats:** the 90/10 rule applies to **for-profit institutions** — coverage is effectively limited to that sector. Note the mirror filename uses `90_10`, the Portal route uses `90-10`.
- **Codebook:** `fsa/codebook_colleges_fsa_90-10_revenue_percentages`
- **Portal endpoint(s):** `/college-university/fsa/90-10-revenue-percentages/{year}/`

---

## PSEO (Post-Secondary Employment Outcomes)

### PSEO Earnings & Flows — `pseo/colleges_pseo_{year}`

- **Type / years:** Yearly · 2001-2021
- **Grain:** one row per `unitid` × `year` × `pseo_cohort` × `degree_level` × `cipcode` × `years_after_grad` × `industry`/`census_division` (Census LEHD-linked graduate earnings).
- **Key variables:** `p25_earnings`, `p50_earnings`, `p75_earnings`, `employed_grads_count_e`, `total_grads_count`, `employed_instate_grads_count`, `degree_level`, `cipcode` (full 18-var family: `variable-dictionary-pseo.md` § `pseo/colleges_pseo_{year}`).
- **Join keys:** `unitid` (+ `year`, `degree_level`, `cipcode`); `opeid`.
- **Caveats:** Yearly. Earnings are LEHD wage-record-based (broader universe than Scorecard's Title-IV-only earnings). **Partner-state coverage varies by release** — institutions in non-partner states are absent, and the covered set changes across vintages; do not treat missing institutions as zero. Earnings in 2022 dollars.
- **Codebook:** `pseo/codebook_colleges_pseo`
- **Portal endpoint(s):** `/college-university/pseo/earnings-and-flows/{year}/`

---

## EADA (Equity in Athletics)

### EADA Institutional Characteristics — `eada/colleges_eada_inst_characteristics`

- **Type / years:** Single-file · 2002-2021
- **Grain:** one row per `unitid` × `year` (institution-level athletics participation, staffing, and finances by gender).
- **Key variables:** `enrollment_men`, `enrollment_women`, `num_sports`, `athpartic_men`, `athpartic_women`, `ath_stuaid_total`, `hdcoach_salary_men`, `hdcoach_salary_women`, `ath_grnd_total_rev`, `ath_grnd_total_exp`, `ath_classification_name` (full 168-var list: `variable-dictionary-eada.md` § `eada/colleges_eada_inst_characteristics`).
- **Join keys:** `unitid` (+ `year`) — see caveat on sector.
- **Caveats:** **no sector/control column** — join IPEDS `directory` on `unitid` to obtain institution type. This is athletics **gender-equity reporting**, not Title IX compliance data. Men's/women's/coed splits are pervasive; totals are provided (e.g., `ath_grnd_total_rev/_exp`).
- **Codebook:** `eada/codebook_colleges_eada_inst-characteristics`
- **Portal endpoint(s):** `/college-university/eada/institutional-characteristics/{year}/`

---

## NACUBO (Endowments)

### NACUBO Endowments — `nacubo/colleges_nacubo_endow`

- **Type / years:** Single-file · 2012-2022
- **Grain:** one row per `unitid` × `year` (endowment size and change).
- **Key variables:** `endow_total`, `endow_per_fte`, `endow_chg_mktval`, `inst_name_nacubo` (complete 7-var family: `variable-dictionary-nacubo.md` § `nacubo/colleges_nacubo_endow`).
- **Join keys:** `unitid` (+ `year`).
- **Caveats:** **7 columns only** and ~650 institutions (NACUBO/TIAA study participants). For endowment *detail* (investment/spending policy) go to NACUBO directly; for **all-institution** endowment coverage use IPEDS `finance` (`endowment_beg`/`endowment_end`).
- **Codebook:** `nacubo/codebook_colleges_nacubo_endowments`
- **Portal endpoint(s):** `/college-university/nacubo/endowments/{year}/`

---

## NCCS (Nonprofit Form 990)

### NCCS 990 Forms — `nccs/colleges_nccs_all`

- **Type / years:** Single-file · 1993-2016
- **Grain:** one row per `unitid` × `year` (IRS Form 990 financials, IPEDS-matched).
- **Key variables:** `revenue_total`, `contributions_total`, `prog_serv_rev`, `invest_inc_total`, `expenses_total`, `net_assets_eoy`, `total_assets_eoy`, `total_liab_eoy`, `compensation_officers`, `ein` (full 160+-var list: `variable-dictionary-nccs.md` § `nccs/colleges_nccs_all`).
- **Join keys:** `unitid` (+ `year`); `ein` to IRS records.
- **Caveats:** **private nonprofit institutions only** — public institutions file no Form 990 and are absent. Mirror coverage **ends 2016**. Use when IRS financial depth beyond IPEDS is needed (governance, detailed revenue/expense lines).
- **Codebook:** `nccs/codebook_colleges_nccs_form_990`
- **Portal endpoint(s):** `/college-university/nccs/990-forms/{year}/`

---

## NHGIS (Census Geography Linkage — Colleges)

### NHGIS College Geography — `nhgis/colleges_nhgis_geog_{year}`

- **Type / years:** Yearly · file-year/linkage coverage 1980, 1984-2023 (census-geography vintages 1990-2020)
- **Grain:** one row per `unitid` × `year` (institution geocoded to census geography).
- **Key variables:** `county_fips`, `tract`, `block_group`, `geoid_block`, `census_region`, `census_division`, `cbsa`, `cbsa_name`, `puma`, `state_leg_district_upper`, `geo_latitude`, `geo_longitude` (full 39-var list: `variable-dictionary-nhgis.md` § `nhgis/colleges_nhgis_geog_{year}`).
- **Join keys:** `unitid` (+ `year`) → downstream census-geography identifiers (`geoid_block`, `tract`, `cbsa`).
- **Caveats:** **geography linkage ONLY** — provides crosswalks from institutions to census tracts/block groups/CBSAs, not census demographics. To attach demographics, browse the public NHGIS Data Finder and submit an extract with a free IPUMS NHGIS account (retrieval concern, not discovery). Four Portal census-vintage routes (1990/2000/2010/2020) feed the one mirror family; pick the geography vintage matching the analysis.
- **Codebook:** `nhgis/codebook_colleges_nhgis_census1990` (also `_census2000`, `_census2010`, `_census2020` per geography vintage)
- **Portal endpoint(s):** `/college-university/nhgis/census-1990/{year}/` (also `census-2000`, `census-2010`, `census-2020`)

---

## Campus Safety (Clery Act)

### Campus Safety Hate Crimes — `csafety/colleges_csafety_hate_crimes`

- **Type / years:** Single-file · 2005-2021
- **Grain:** one row per `unitid` × `year` × `crime_type` × `bias` (hate-crime counts by location).
- **Key variables:** `total_hate_crimes`, `on_campus_hate_crimes`, `residence_hall_hate_crimes`, `non_campus_hate_crimes`, `public_property_hate_crimes`, `crime_type`, `bias` (complete 14-var family: `variable-dictionary-csafety.md` § `csafety/colleges_csafety_hate_crimes`).
- **Join keys:** `unitid` (+ `year`, `crime_type`, `bias`); `opeid`.
- **Caveats:** the Portal mirror carries **hate crimes only** (2005-2021). Other Clery categories — primary offenses, VAWA offenses, arrests, disciplinary referrals, fire safety — are **not in the mirror** and require the Department of Education campus-safety source (ope.ed.gov) directly.
- **Codebook:** `csafety/codebook_colleges_csafety_hate_crimes`
- **Portal endpoint(s):** `/college-university/campus-crime/hate-crimes/{year}/`

---

## Common College Use Cases

| Question | Files (paths) | Join |
|----------|---------------|------|
| Institution profile + sector | `ipeds/colleges_ipeds_directory` | `unitid` (+ `year`) |
| Admissions selectivity | `ipeds/colleges_ipeds_admissions-enrollment` + `ipeds/colleges_ipeds_admissions-requirements` | `unitid` + `year` |
| Sticker price + net price | `ipeds/colleges_ipeds_ay_tuition_fees` + `ipeds/colleges_ipeds_sfa_grants_and_net_price` | `unitid` + `year` |
| Graduation gaps by race/Pell | `ipeds/colleges_ipeds_grad-rates` + `ipeds/colleges_ipeds_grad-rates-pell` | `unitid` + `year` |
| Degrees by field | `ipeds/colleges_ipeds_completions-2digcip_{year}` (or `-6digcip`) | `unitid` + `year` + `cipcode` |
| Revenue/expenditure structure | `ipeds/colleges_ipeds_finance` | `unitid` + `year` (GASB/FASB care) |
| Aid volume + default/repayment | `fsa/colleges_fsa_loans` + `scorecard/colleges_scorecard_repayment_fsa` | `unitid`/`opeid` + `year` |
| Graduate earnings | `pseo/colleges_pseo_{year}` (LEHD) or `scorecard/colleges_scorecard_earnings` (Title IV) | `unitid` + `year` |
| Endowment wealth | `ipeds/colleges_ipeds_finance` (all inst.) or `nacubo/colleges_nacubo_endow` (~650) | `unitid` + `year` |
| Athletics gender equity | `eada/colleges_eada_inst_characteristics` + `ipeds/colleges_ipeds_directory` (for sector) | `unitid` + `year` |
| Link institutions to census geography | `nhgis/colleges_nhgis_geog_{year}` | `unitid` + `year` → `geoid_block`/`tract` |
