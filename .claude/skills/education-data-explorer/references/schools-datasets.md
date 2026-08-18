# Schools Datasets Reference (mirror-first)

School-level mirror dataset families for the Urban Institute Education Data mirror. Each entry gives the **canonical mirror path** (the acquisition currency — extensionless `{source}/{filename}`, with `{year}` where the family is Yearly), the entity **grain**, **year coverage** (vintage 0.26.1), curated **key variables** (real names — full lists in `variable-dictionary-{source}.md`), **join keys**, **caveats**, and a small **Portal endpoint** annotation for citation/maintenance only.

> **Vintage:** all facts keyed to pinned mirror vintage **0.26.1** (revision `0ad00ce0e232c96b0642459e4e7326607a8d26aa`). The `urban_csv` fallback is unpinned/current-Portal. Primary ID at this level is `ncessch` (12-char zero-padded NCES school ID, string); CRDC files additionally carry `crdc_id` (Office of Civil Rights school ID). Emit paths, not routes. Do not instruct fetching or probing — retrieval belongs to `education-data-query`.

---

## CCD (Common Core of Data)

### CCD School Directory & Characteristics — `ccd/schools_ccd_directory`

- **Type / years:** Single-file · 1986-2024
- **Grain:** one row per `ncessch` × `year` (national public-school directory + characteristics + school-level FRPL and staffing).
- **Key variables:** `school_name`, `lea_name`, `leaid`, `fips`, `enrollment`, `teachers_fte`, `school_level`, `school_type`, `charter`, `magnet`, `virtual`, `title_i_status`, `urban_centric_locale`, `lowest_grade_offered`, `highest_grade_offered`, `free_or_reduced_price_lunch`, `latitude`, `longitude` (full 52-var list: `variable-dictionary-ccd.md` § `ccd/schools_ccd_directory`).
- **Join keys:** `ncessch` (+ `year`) to any school source; `leaid` (+ `year`) rolls up to the LEA/district level.
- **Caveats:** `teachers_fte` is rounded in the live Portal API — the mirror/bulk file carries full precision, so prefer the mirror value (observed 2026-08-07, mirror-maintenance fidelity battery; bulk CSV confirmed 28.98 — see /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/). FRPL counts are affected by Community Eligibility Provision (CEP) coverage; for a modeled poverty measure use MEPS. `virtual`/`charter`/`magnet` coverage thins in the earliest years.
- **Codebook:** `ccd/codebook_schools_ccd_directory`
- **Portal endpoint(s):** `/schools/ccd/directory/{year}/`

### CCD School Enrollment — `ccd/schools_ccd_enrollment_{year}`

- **Type / years:** Yearly · 1986-2024 (one file per year)
- **Grain:** one row per `ncessch` × `year` × `grade` × `race` × `sex`. Disaggregation dimensions are **columns**, not URL segments — filter to the `99`/total code on each dimension for a school total (do not sum, or totals rows double-count).
- **Key variables:** `ncessch`, `leaid`, `fips`, `grade`, `race`, `sex`, `enrollment` (complete 9-var family incl. `ncessch_num`: `variable-dictionary-ccd.md` § `ccd/schools_ccd_enrollment_{year}`).
- **Join keys:** `ncessch` (+ `year`, and dimension codes where relevant).
- **Caveats:** `grade=-1` is Pre-K (**not** missing); `grade=99` is all-grades total. Fetch each needed year and concatenate. `sex=9` is Unknown; `race` uses the `1-9, 20, 99` scheme (see `variable-codes.md`).
- **Codebook:** `ccd/codebook_schools_ccd_enrollment`
- **Portal endpoint(s):** `/schools/ccd/enrollment/{year}/{grade}/` (+ `/race/`, `/sex/`, `/race/sex/`)

---

## CRDC (Civil Rights Data Collection)

OCR civil-rights collection for U.S. public schools — 24 topic-specific mirror families, each a **separate file per topic** (the Portal exposes many per-disaggregation routes — `.../disability/sex/`, `.../lep/sex/`, `.../race/sex/` — but they resolve to one mirror file per topic family). Shared structure and caveats apply to every CRDC family below and are stated once here:

- **Grain & dimensions:** primary key is `ncessch` × `year`; most topic files disaggregate by `race`, `sex`, `disability`, and/or `lep` as **columns**. Filter each dimension to its `99`/total code for a school total. `disability` uses the full `0-4/99` scheme (code `2` = Section 504 only; see `variable-codes.md`); `sex=9` is Unknown; `grade_crdc` (where present) uses banded codes (`20`=Gr 7-8, `21`=Gr 9-10, `22`=Gr 11-12, `99`=Total).
- **Collection years:** biennial 2011, 2013, 2015, 2017, 2020, 2021 (a few families extend to 2022 or stop earlier — see each entry). **2013-14 (`year=2013`) is a universe collection** (official evidence); **2020-21 (`year=2020`) is COVID-impacted** and must be interpreted with care.
- **Suppression & missing:** small cells (typically fewer than 10 students) are suppressed; suppressed = `-3`, missing/not-reported = `-1`, not-applicable = `-2` across all measures.
- **ID dtypes (no universal contract):** `crdc_id`, `ncessch`, and `leaid` are typed heterogeneously per file and even per vintage (String/Int64 mix — e.g. `discipline_k12_2020` stores `ncessch` as Int64, `school_characteristics` stores all three as String). Always inspect the actual file schema and normalize identifiers on read before joining; never assume a uniform id dtype across CRDC files.

### Enrollment & school context

#### CRDC School Characteristics — `crdc/schools_crdc_school_characteristics`

- **Type / years:** Single-file · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` (CRDC directory — the join/universe anchor for all other CRDC topics).
- **Key variables:** `school_name_crdc`, `schoolid_crdc`, `lea_name`, `leaid_crdc`, `lea_state`, `charter_crdc`, `magnet_crdc`, `alt_school`, `primarily_serve_students_w_dis`, `prek`, `k`, `g1`…`g12`, `ug` (grade-offered flags) (full 35-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_school_characteristics`).
- **Join keys:** `ncessch` (+ `year`); `crdc_id` to other CRDC files; `leaid_crdc` to LEA.
- **Caveats:** grade-offered columns (`prek`…`ug`) are per-grade indicators, not counts.
- **Codebook:** `crdc/codebook_schools_crdc_directory`
- **Portal endpoint(s):** `/schools/crdc/directory/{year}/`

#### CRDC K-12 Enrollment — `crdc/schools_crdc_enrollment_k12_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep` (dimension columns).
- **Key variables:** `enrollment_crdc`, `psenrollment_crdc` (preschool enrollment), plus dimension columns `race`, `sex`, `disability`, `lep` (full 11-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_enrollment_k12_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** CRDC enrollment is a civil-rights count and will not exactly match CCD `enrollment` (different universe/definition/year alignment).
- **Codebook:** `crdc/codebook_schools_crdc_enrollment`
- **Portal endpoint(s):** `/schools/crdc/enrollment/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC Internet Access — `crdc/schools_crdc_internet_access`

- **Type / years:** Single-file · 2020, 2021
- **Grain:** one row per `ncessch` × `year`.
- **Key variables:** `sch_internet_fiber`, `sch_internet_wifi`, `sch_internet_schdev`, `sch_internet_studdev`, `sch_internet_wifiendev` (full 10-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_internet_access`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** collected only in the COVID-era 2020/2021 waves; indicators are yes/no device/connectivity flags.
- **Codebook:** `crdc/codebook_schools_crdc_internet_access`
- **Portal endpoint(s):** `/schools/crdc/internet-access/{year}/`

### Discipline & school safety

#### CRDC K-12 Discipline — `crdc/schools_crdc_discipline_k12_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `disability` × (`race` and/or `lep`) × `sex` (dimension columns).
- **Key variables:** `students_susp_in_sch`, `students_susp_out_sch_single`, `students_susp_out_sch_multiple`, `expulsions_no_ed_serv`, `expulsions_with_ed_serv`, `expulsions_zero_tolerance`, `students_corporal_punish`, `students_arrested`, `students_referred_law_enforce`, `transfers_alt_sch_disc` (full 20-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_discipline_k12_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** `revised_flag=1` marks records where OCR revised the arrests variable. Counts are of students disciplined (unduplicated within category), not incidents — for incident counts use Discipline Instances.
- **Codebook:** `crdc/codebook_schools_crdc_discipline`
- **Portal endpoint(s):** `/schools/crdc/discipline/{year}/disability/lep/sex/` (+ `/disability/race/sex/`, `/disability/sex/`)

#### CRDC Discipline Instances — `crdc/schools_crdc_disciplineinstances`

- **Type / years:** Single-file · 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `disability` (instance counts, not student counts).
- **Key variables:** `suspensions_instances`, `suspensions_instances_preschool`, `corpinstances`, `corpinstances_preschool` (full 10-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_disciplineinstances`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, `disability`).
- **Caveats:** measures **instances** (events), distinct from the student-level discipline file; only `disability` disaggregation is present.
- **Codebook:** `crdc/codebook_schools_crdc_discipline_instances`
- **Portal endpoint(s):** `/schools/crdc/discipline-instances/{year}/`

#### CRDC Suspensions (Days) — `crdc/schools_crdc_suspensions`

- **Type / years:** Single-file · 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `days_suspended` (days of instruction missed to suspension), plus dimension columns `race`, `sex`, `disability`, `lep` (full 10-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_suspensions`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** `days_suspended` is a days count (float), not a student count.
- **Codebook:** `crdc/codebook_schools_crdc_suspensions_days`
- **Portal endpoint(s):** `/schools/crdc/suspensions-days/{year}/disability/sex` (+ `/lep/sex`, `/race/sex`)

#### CRDC Restraint & Seclusion — Students — `crdc/schools_crdc_restraint_seclusion_students_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `students_mech_restraint`, `students_phys_restraint`, `students_seclusion` (full 12-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_restraint_seclusion_students_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** counts students subjected; pair with the Instances file for event counts.
- **Codebook:** `crdc/codebook_schools_crdc_restraint-seclusion-students`
- **Portal endpoint(s):** `/schools/crdc/restraint-and-seclusion/{year}/disability/lep/sex/` (+ `/disability/race/sex/`, `/disability/sex/`)

#### CRDC Restraint & Seclusion — Instances — `crdc/schools_crdc_restraint_seclusion_instances`

- **Type / years:** Single-file · 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `disability` (instance counts).
- **Key variables:** `instances_mech_restraint`, `instances_phys_restraint`, `instances_seclusion` (full 9-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_restraint_seclusion_instances`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, `disability`).
- **Caveats:** measures **instances**, not students; only `disability` disaggregation.
- **Codebook:** `crdc/codebook_schools_crdc_restraint-seclusion-instances`
- **Portal endpoint(s):** `/schools/crdc/restraint-and-seclusion/{year}/instances/`

#### CRDC Offenses — `crdc/schools_crdc_offenses`

- **Type / years:** Single-file · 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` (school-level incident/allegation counts, undisaggregated).
- **Key variables:** `firearm_incident_ind`, `homicide_ind`, `rape_incidents`, `sexual_battery_incidents`, `robbery_w_weapon_incidents`, `attack_w_weapon_incidents`, `threats_w_weapon_incidents`, `possession_firearm_incidents`, `rape_bystudents`, `rape_bystaff` (full 33-var list incl. staff-allegation disposition columns: `variable-dictionary-crdc.md` § `crdc/schools_crdc_offenses`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** mix of indicator flags (`_ind`) and incident counts; the `alleg_*_staff_*` columns track allegation dispositions (resigned/responsible/pending) and are sparse.
- **Codebook:** `crdc/codebook_schools_crdc_offenses`
- **Portal endpoint(s):** `/schools/crdc/offenses/{year}/`

#### CRDC Harassment/Bullying — Students — `crdc/schools_crdc_harass_bully_students_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `students_disc_harass_dis`, `students_disc_harass_race`, `students_disc_harass_sex`, `students_report_harass_dis`, `students_report_harass_race`, `students_report_harass_sex` (full 15-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_harass_bully_students_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** separates students *disciplined for* vs *reported as harassed/bullied* on each basis (disability/race/sex).
- **Codebook:** `crdc/codebook_schools_crdc_harrassment-bullying-students` (note the mirror's intentional double-r "harrassment" spelling).
- **Portal endpoint(s):** `/schools/crdc/harassment-or-bullying/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC Harassment/Bullying — Allegations — `crdc/schools_crdc_harass_bully_allegations`

- **Type / years:** Single-file · 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` (school-level allegation counts, undisaggregated).
- **Key variables:** `allegations_harass_sex`, `allegations_harass_race`, `allegations_harass_disability`, `allegations_harass_orientation`, `allegations_harass_religion`, plus per-religion breakdowns (`harrass_religion_islam`, `harrass_religion_jewish`, `harass_religion_sikh`, …) (full 24-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_harass_bully_allegations`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** the detailed per-religion allegation columns are only populated in later waves and are sparse.
- **Codebook:** `crdc/codebook_schools_crdc_harrassment-bullying-allegations` (mirror uses double-r "harrassment").
- **Portal endpoint(s):** `/schools/crdc/harassment-or-bullying/{year}/allegations/`

### Course access & coursework

#### CRDC Algebra I — `crdc/schools_crdc_algebra_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `grade_crdc` × `race`/`lep`/`disability` × `sex`.
- **Key variables:** `enrl_algebra1`, `students_passing_algebra1`, plus `grade_crdc` band and dimension columns (full 12-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_algebra_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, `grade_crdc`, dimension codes).
- **Caveats:** `grade_crdc` bands (7-8 / 9-10 / 11-12) matter — Algebra I enrollment is analyzed by middle- vs high-school grade band.
- **Codebook:** `crdc/codebook_schools_crdc_algebra-1`
- **Portal endpoint(s):** `/schools/crdc/algebra1/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex`)

#### CRDC Math & Science — `crdc/schools_crdc_mathandscience`

- **Type / years:** Single-file · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `enrl_biology`, `enrl_chemistry`, `enrl_physics`, `enrl_geometry`, `enrl_algebra2`, `enrl_advanced_math`, `enrl_calculus` (full 16-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_mathandscience`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** enrollment counts, not pass counts; pair with Offerings to know whether a course was available at all.
- **Codebook:** `crdc/codebook_schools_crdc_math-and-science`
- **Portal endpoint(s):** `/schools/crdc/math-and-science/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC AP/IB Enrollment — `crdc/schools_crdc_apib_enroll`

- **Type / years:** Single-file · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `enrl_ap`, `enrl_ib`, `enrl_gifted_talented`, `enrl_ap_science`, `enrl_ap_math`, `enrl_ap_language`, `enrl_ap_compsci`, `enrl_ap_other` (full 17-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_apib_enroll`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** the legacy `ap-ib-gt` Portal route is retired; this file is the current AP/IB/gifted enrollment source.
- **Codebook:** `crdc/codebook_schools_crdc_ap-ib-enrollment`
- **Portal endpoint(s):** `/schools/crdc/ap-ib-enrollment/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC AP Exams — `crdc/schools_crdc_ap_exams_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017 (**not** collected 2020/2021)
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `students_ap_exam_none`, `students_ap_exam_oneormore`, `students_ap_exam_all`, `students_ap_pass_none`, `students_ap_pass_oneormore`, `students_ap_pass_all` (full 15-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_ap_exams_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** exam-taking/passing counts are separate from AP *enrollment* (AP/IB file); coverage stops at 2017.
- **Codebook:** `crdc/codebook_schools_crdc_ap-exams`
- **Portal endpoint(s):** `/schools/crdc/ap-exams/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC Course Offerings — `crdc/schools_crdc_offerings`

- **Type / years:** Single-file · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` (school-level offering indicators and class counts).
- **Key variables:** `num_classes_algebra1`, `num_classes_calculus`, `num_classes_physics`, `num_taught_certified_algebra1` (…and other `num_taught_certified_*`), `ap_courses_indicator`, `num_courses_ap`, `gifted_talented_indicator`, `sch_dual_indicator`, `sports_single_sex_indicator` (full 53-var list incl. single-sex class/sport counts: `variable-dictionary-crdc.md` § `crdc/schools_crdc_offerings`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** `num_taught_certified_*` pairs with `num_classes_*` to measure certified-teacher coverage; single-sex class/sport columns are a distinct policy topic within the same file.
- **Codebook:** `crdc/codebook_schools_crdc_offerings`
- **Portal endpoint(s):** `/schools/crdc/offerings/{year}/`

#### CRDC Dual Enrollment — `crdc/schools_crdc_dual_enrollment`

- **Type / years:** Single-file · 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `enrl_dual_enrollment`, plus dimension columns `race`, `sex`, `disability`, `lep` (full 10-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_dual_enrollment`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** collected from 2015 onward; use `sch_dual_indicator` in Offerings to know whether the program exists at all.
- **Codebook:** `crdc/codebook_schools_crdc_dual_enrollment`
- **Portal endpoint(s):** `/schools/crdc/dual-enrollment/{year}/disability/sex` (+ `/lep/sex`, `/race/sex`)

#### CRDC SAT/ACT Participation — `crdc/schools_crdc_sat_and_act_participation_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep`.
- **Key variables:** `students_sat_act`, plus dimension columns `race`, `sex`, `disability`, `lep` (full 10-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_sat_and_act_participation_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** single combined SAT-or-ACT participation count; not disaggregated by test.
- **Codebook:** `crdc/codebook_schools_crdc_sat-act-participation`
- **Portal endpoint(s):** `/schools/crdc/sat-act-participation/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC Credit Recovery — `crdc/schools_crdc_credit_recovery`

- **Type / years:** Single-file · 2015, 2017
- **Grain:** one row per `ncessch` × `year`.
- **Key variables:** `credit_recovery_offered` (indicator), `enrl_credit_recovery` (count) (full 7-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_credit_recovery`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** collected only in 2015 and 2017; `enrl_credit_recovery` is undefined where `credit_recovery_offered=0`.
- **Codebook:** `crdc/codebook_schools_crdc_credit-recovery`
- **Portal endpoint(s):** `/schools/crdc/credit-recovery/{year}/`

### Attendance & retention

#### CRDC Chronic Absenteeism — `crdc/schools_crdc_chronic_absenteeism_{year}`

- **Type / years:** Yearly · 2013, 2015, 2017, 2020, 2021, 2022
- **Grain:** one row per `ncessch` × `year` × `race` × `sex` × `disability` × `lep` (with a `homeless` flag).
- **Key variables:** `students_chronically_absent`, `homeless`, plus dimension columns `race`, `sex`, `disability`, `lep` (full 11-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_chronic_absenteeism_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, dimension codes).
- **Caveats:** the only CRDC topic reaching **2022**; "chronically absent" follows the OCR 15+ days definition.
- **Codebook:** `crdc/codebook_schools_crdc_chronic-absenteeism`
- **Portal endpoint(s):** `/schools/crdc/chronic-absenteeism/{year}/disability/sex/` (+ `/lep/sex/`, `/race/sex/`)

#### CRDC Retention — `crdc/schools_crdc_retention_{year}`

- **Type / years:** Yearly · 2011, 2013, 2015, 2017 (**not** collected 2020/2021)
- **Grain:** one row per `ncessch` × `year` × `grade` × `race`/`lep`/`disability` × `sex`.
- **Key variables:** `students_retained`, plus `grade` and dimension columns `race`, `sex`, `disability`, `lep` (full 11-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_retention_{year}`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`, `grade`, dimension codes).
- **Caveats:** grade-in-URL family (retention is analyzed by grade level); coverage stops at 2017.
- **Codebook:** `crdc/codebook_schools_crdc_retention`
- **Portal endpoint(s):** `/schools/crdc/retention/{year}/{grade}/disability/sex` (+ `/lep/sex`, `/race/sex`)

### Staffing & finance

#### CRDC Teachers & Staff — `crdc/schools_crdc_teacher`

- **Type / years:** Single-file · 2011, 2013, 2015, 2017, 2020, 2021
- **Grain:** one row per `ncessch` × `year` (school-level staffing FTE counts).
- **Key variables:** `teachers_fte_crdc`, `teachers_certified_fte`, `teachers_uncertified_fte`, `teachers_first_year_fte`, `teachers_absent_fte`, `counselors_fte`, `social_workers_fte`, `psychologists_fte`, `nurses_fte`, `law_enforcement_fte`, `security_guard_fte` (full 22-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_teacher`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** `teachers_fte_crdc` is the CRDC-defined FTE count and will differ from CCD `teachers_fte`; support-staff FTEs (counselors/nurses/etc.) are the civil-rights staffing-access measures.
- **Codebook:** `crdc/codebook_schools_crdc_teachers_staff`
- **Portal endpoint(s):** `/schools/crdc/teachers-staff/{year}/`

#### CRDC School Finance — `crdc/schools_crdc_finance`

- **Type / years:** Single-file · 2011, 2013, 2015, 2017
- **Grain:** one row per `ncessch` × `year` (school-level salary/expenditure figures).
- **Key variables:** `salaries_teachers`, `salaries_total`, `salaries_instruc_staff`, `salaries_instructional_aides`, `salaries_support`, `salaries_administration`, `expenditures_nonpersonnel`, `instructional_aides_fte`, `support_fte`, `administration_fte` (full 15-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_finance`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** school-level (not LEA) finance from the civil-rights collection; the file stores dollar totals — compute per-pupil from CCD/CRDC enrollment. Coverage stops at 2017.
- **Codebook:** `crdc/codebook_schools_crdc_finance`
- **Portal endpoint(s):** `/schools/crdc/school-finance/{year}/`

### COVID

#### CRDC COVID Indicators — `crdc/schools_crdc_covid_indicators`

- **Type / years:** Single-file · 2020, 2021
- **Grain:** one row per `ncessch` × `year`.
- **Key variables:** `covid_instruction_type`, `covid_virtual_type`, `covid_remote_time`, `covid_remote_time_pct` (full 9-var list: `variable-dictionary-crdc.md` § `crdc/schools_crdc_covid_indicators`).
- **Join keys:** `ncessch`/`crdc_id` (+ `year`).
- **Caveats:** categorical descriptors of 2020-21 pandemic instruction mode; specific to the COVID-impacted waves.
- **Codebook:** `crdc/codebook_schools_crdc_covid_indicators`
- **Portal endpoint(s):** `/schools/crdc/covid-indicators/{year}/`

---

## EDFacts

### School Assessments — `edfacts/schools_edfacts_assessments_{year}`

- **Type / years:** Yearly · 2009-2018, 2020 (**2019 absent** — COVID testing waivers)
- **Grain:** one row per `ncessch` × `year` × `grade_edfacts` × subgroup dimension. Subgroups are columns (`race`, `sex`, `lep`, `disability`, `econ_disadvantaged`, `homeless`, `migrant`, `foster_care`, `military_connected`).
- **Key variables:** `grade_edfacts`, `read_test_num_valid`, `read_test_pct_prof_midpt` (+ `_low`/`_high`), `math_test_num_valid`, `math_test_pct_prof_midpt` (+ `_low`/`_high`) (full 26-var list: `variable-dictionary-edfacts.md` § `edfacts/schools_edfacts_assessments_{year}`).
- **Join keys:** `ncessch` (+ `year`, `grade_edfacts`, subgroup codes); `leaid` rolls up to LEA.
- **Caveats:** proficiency is **range-reported** (`_low`/`_midpt`/`_high`) for small-cell protection — use the midpoint and carry the range. `grade_edfacts` codes are `{3-8, 9="Grades 9-12", 99}` (distinct from CCD numeric `grade`). **State assessment scores cannot be compared across states** (different tests/cut scores) — this is a within-state-only measure. `disability` uses the full 0-4/99 scheme (see `variable-codes.md`).
- **Codebook:** `edfacts/codebook_schools_edfacts_assessments`
- **Portal endpoint(s):** `/schools/edfacts/assessments/{year}/{grade_edfacts}/` (+ `/race/`, `/sex/`, `/special-populations/`)

### School Graduation Rates — `edfacts/schools_edfacts_grad_rates_{year}`

- **Type / years:** Yearly · 2010-2019
- **Grain:** one row per `ncessch` × `year` × subgroup (ACGR — adjusted cohort graduation rate).
- **Key variables:** `cohort_num`, `grad_rate_midpt` (+ `_low`/`_high`), plus subgroup columns `race`, `lep`, `disability`, `econ_disadvantaged`, `homeless`, `foster_care` (full 18-var list: `variable-dictionary-edfacts.md` § `edfacts/schools_edfacts_grad_rates_{year}`).
- **Join keys:** `ncessch` (+ `year`, subgroup codes); `leaid` rolls up to LEA.
- **Caveats:** grad rate is **range-reported** (use `grad_rate_midpt`, carry the range). ACGR is a 4-year adjusted-cohort high-school measure; not comparable to CCD completion counts and, like assessments, not comparable across states.
- **Codebook:** `edfacts/codebook_schools_edfacts_graduation`
- **Portal endpoint(s):** `/schools/edfacts/grad-rates/{year}/`

---

## MEPS (Model Estimates of Poverty in Schools)

### School Poverty — `meps/schools_meps`

- **Type / years:** Single-file · 2009-2022 (MEPS 2.0, released 2025-12-11; covers school years 2009-10 through 2022-23)
- **Grain:** one row per `ncessch` × `year` (Urban Institute modeled school-level poverty estimate).
- **Key variables:** `meps_poverty_pct` (% of students at ≤100% FPL), `meps_poverty_se`, `meps_mod_poverty_pct`, `meps_poverty_ptl`, `meps_mod_poverty_ptl`, `gleaid` (complete 11-var family: `variable-dictionary-meps.md` § `meps/schools_meps`).
- **Join keys:** `ncessch` (+ `year`) to CCD/CRDC/EDFacts; `gleaid` for geographic LEA linkage.
- **Caveats:** the poverty field is `meps_poverty_pct` (**not** `school_poverty`). MEPS 2.0 mirror coverage runs to file-year 2022; Portal year 2022 returned rows while **2023 was empty as of 2026-08-06** (re-probe before assuming 2023 availability). Prefer MEPS over CCD FRPL where FRPL is unreliable due to CEP, and for consistent cross-state measurement.
- **Codebook:** `meps/codebook_schools_meps`
- **Portal endpoint(s):** `/schools/meps/{year}/`

---

## NHGIS (Census Geography Linkage)

### School Census-Geography Crosswalks — `nhgis/schools_nhgis_geog_{census_vintage}`

- **Type / years:** four single-file census-geography vintages — `nhgis/schools_nhgis_geog_1990`, `_2000`, `_2010`, `_2020` — each covering school file-years **1986-2023**. Choose the vintage by the census-geography boundaries you need (1990/2000/2010/2020), not by data year.
- **Grain:** one row per `ncessch` × `year` (a school's location joined to census geography identifiers for the chosen census vintage).
- **Key variables:** `tract`, `block_group`, `geoid_block`, `county_fips_geo`, `state_fips_geo`, `cbsa`, `csa`, `census_region`, `census_division`, `place_fips`, `puma`, `gleaid`, `geocode_accuracy` (full 48-var list: `variable-dictionary-nhgis.md` § `nhgis/schools_nhgis_geog_{year}`).
- **Join keys:** `ncessch` (+ `year`) to any school source; the census geo IDs (`tract`, `geoid_block`, `cbsa`, `county_fips_geo`) then link outward to census/ACS data.
- **Caveats:** **geography linkage tables ONLY** — these files carry no census demographics. To browse or extract census demographic data, use the public NHGIS Data Finder (free IPUMS NHGIS account required for extracts). Match the census vintage to your demographic data's boundary year to avoid boundary-change mismatch. `geocode_accuracy`/`geocode_accuracy_detailed` flag imprecise geocodes — inspect before spatial analysis.
- **Codebook:** `nhgis/codebook_schools_nhgis_census1990` / `census2000` / `census2010` / `census2020`
- **Portal endpoint(s):** `/schools/nhgis/census-1990/{year}/` (+ `census-2000`, `census-2010`, `census-2020`)

---

## Common School Use Cases

| Question | Files (paths) | Join |
|----------|---------------|------|
| School characteristics + enrollment trend | `ccd/schools_ccd_directory` + `ccd/schools_ccd_enrollment_{year}` (multi-year) | `ncessch` + `year` (+ dimension totals) |
| Discipline disparities by race | `crdc/schools_crdc_discipline_k12_{year}` + `crdc/schools_crdc_school_characteristics` | `ncessch`/`crdc_id` + `year` |
| Course access & STEM equity | `crdc/schools_crdc_algebra_{year}` + `crdc/schools_crdc_mathandscience` + `crdc/schools_crdc_offerings` | `ncessch`/`crdc_id` + `year` |
| Poverty and achievement | `meps/schools_meps` + `edfacts/schools_edfacts_assessments_{year}` | `ncessch` + `year` |
| Graduation gaps by subgroup | `edfacts/schools_edfacts_grad_rates_{year}` + `ccd/schools_ccd_directory` | `ncessch` + `year` |
| Link schools to census tracts | `nhgis/schools_nhgis_geog_{census_vintage}` + `ccd/schools_ccd_directory` | `ncessch` + `year` |
| Staffing access (counselors, nurses, police) | `crdc/schools_crdc_teacher` + `crdc/schools_crdc_school_characteristics` | `ncessch`/`crdc_id` + `year` |
