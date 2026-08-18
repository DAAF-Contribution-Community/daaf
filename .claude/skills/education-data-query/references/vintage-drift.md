# Vintage Drift: Old (v0.24.0) → Current (v0.26.1) Mirror

**What this file is.** A distilled, agent-facing map of how the current versioned
mirror (Portal **v0.26.1**, repo `education_data_portal_mirror_2026q3`, built
2026-08-06) differs from the frozen predecessor (Portal **v0.24.0**, repo
`education_data_portal_mirror`, collected 2026-02-07). Read it when a rerun's
numbers change unexpectedly, when deciding whether an old analysis must be
re-executed against the new mirror, or when reconciling a result computed under
one vintage against a result computed under the other.

**Why it exists.** The Portal revises historical values between releases *without
schema changes* — a rerun of the same fetch script against an unpinned mirror can
silently return different numbers. This file tells you *which* datasets and years
moved, *how much*, and *whether the change is real or cosmetic*, so you can size
the reproducibility impact before re-running anything.

**Evidence base.** Every figure here traces to the drift battery and build
validation for the v2 update. The underlying artifacts (read these for full
per-column detail, examples, and method notes):

- Drift report: `research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_drift-battery/2026-08-06_vintage-drift-report.md`
- Drift manifest + new-file profiles: `…/2026-08-06_drift-battery/drift_manifest.parquet`, `…/new_files_profile.parquet`, plus per-pair `drift_details/*__colstats.parquet` and `*__examples.parquet`
- Build validation (authoritative coverage numbers): `research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/2026-08-06_mirror-v2-build-validation_a.md`

**Method note (how the battery classified change).** 26 overlapping parquet pairs
+ 3 xls codebook pairs were compared on three tiers (schema / row / value) plus a
change-nature decomposition. Value comparison joined on a minimal natural key over
overlapping years only, cast keys to string to survive int↔str representation, and
used `eq_missing` (null==null is *not* a change). Crucially, Portal missing
sentinels `{-1, -2, -3}` (education-data-context: -1 missing, -2 not applicable,
-3 suppressed) are treated as **non-real** — a cell going `null → -1` is
re-encoding, not a data revision. "Substantive rate" = share of matched overlap
rows where both sides are real (non-null, not a sentinel) and differ.

---

## How to Interpret the Drift Classes

A pair's `drift_class` tells you what kind of change happened, which in turn tells
you the reproducibility risk. There are five practical categories; the first two
carry rerun risk, the last three generally do not.

| Class | Meaning | Rerun risk |
|-------|---------|------------|
| **Substantive revision** | Real values changed in overlapping years (both sides non-sentinel, differ) | **Yes** — results using the affected dataset/years change |
| **Full revision (dedup + revalue)** | The old extract was corrupted (duplicated rows) and every retained measure was recomputed | **Yes, total** — old analysis is superseded in full |
| **Row-grain expansion** | New rows added (disaggregation/entity/universe growth); matched cells stable | **Conditional** — coverage/row-count analyses change; cell-level trends on matched entities do not |
| **Cosmetic re-encoding** | Only `null → {-1,-2,-3}` missing-code recodes; 0% substantive | **No** — *if* your code already treats Portal sentinels and nulls as missing |
| **Append-only / coverage extension** | New survey years appended; overlap identical | **No** — purely additive |

**The one rule that prevents false alarms.** A raw "any-change" rate can read as
high as 100% while the substantive rate is 0% — that entire delta is `null →
sentinel` re-encoding. If your analysis maps Portal sentinels and nulls to missing
(as education-data-context instructs), those pairs are inert. An analysis that
treated `-1` as a numeric value was already wrong before the mirror changed; the
re-encoding merely exposes the pre-existing coding error.

---

## Tier 1: Coverage Additions (safe appends)

New survey years and new-only files, additive only. No overlap changes.

- **15 series gained new years** through 2024, e.g. `salaries_nis` (+2023-24),
  `fall-res` (+2021-24), `student-faculty-ratio` (+2021-24), `districts_saipe`
  (+2024), `school-districts_lea_directory` (+2024), `schools_ccd_directory`
  (+2024), `admissions-enrollment` (+2023-24).
- **10 new-only files** (no old counterpart, so no drift comparison applies):

| File | rows | year |
|------|-----:|-----:|
| `ccd/schools_ccd_enrollment_2024` | 18,349,935 | 2024 |
| `ccd/schools_ccd_lea_enrollment_2024` | 6,356,502 | 2024 |
| `ipeds/colleges_ipeds_fall-enrollment-age_2021…2024` | 0.58M–1.20M each | 2021-24 |
| `ipeds/colleges_ipeds_fall-enrollment-race_2023` | 3,686,080 | 2023 |
| `ipeds/colleges_ipeds_fall-enrollment-race_2024` | 3,642,656 | 2024 |
| `ipeds/colleges_ipeds_completions-2digcip_2023` | 4,235,250 | 2023 |
| `ipeds/colleges_ipeds_completions-6digcip_2023` | 9,184,110 | 2023 |

- **Also new to the mirror (build-level):** the eight Urban-catalog objects that
  were absent from the previous build are now included; the v2 tree is **497
  objects** (406 data parquets + 91 xls codebooks), zero Urban-catalog gaps. See
  `mirrors.yaml` coverage_notes and the build validation artifact.

---

## Tier 2: Substantive Revisions (results WILL change)

These are the pairs where a pre-v2 analysis touching the listed years produces
different numbers against v0.26.1. Ranked by substantive rate.

| Dataset | Substantive rate | Affected years | Driver |
|---------|-----------------:|----------------|--------|
| `ipeds/colleges_ipeds_grad-rates` (150%) | **100%** (dedup+revalue) | 1996-2023 (all) | See deep-dive below — full supersession |
| `ipeds/colleges_ipeds_grad-rates-pell` | **71.50%** | overlap **2015 & 2017** revised; +2018-23 new | `completion_rate_150pct` changed in 78.2% of matched rows |
| `ipeds/colleges_ipeds_salaries_is` | **3.12%** | +2023-24 append; revision in overlap | `average_salary` genuinely revised; `total_months`/`avg_wgtd_mon_salary` moves are cosmetic null→-1 |
| `ipeds/colleges_ipeds_academic_libraries` | **2.06%** | overlap year **2020** revised; +2021-23 | 659 rows real; 99.68% of raw changes are null→-1 FTE-staff re-encoding |
| `ipeds/colleges_ipeds_directory` | 0.224% | +2024, +7 `cc_*_2025` cols | 229 rows; plus Carnegie 2025 classification columns |
| `ipeds/colleges_ipeds_student-faculty-ratio` | 0.156% | overlap **2018 & 2020** | 124 rows |
| `ipeds/colleges_ipeds_fall-retention` | 0.122% | +`prev_inclusions` col, +2021-24 | 284 rows; count-column redefinition |
| `ipeds/colleges_ipeds_enrollment-fte` | 0.029% | overlap **1999-2010** | 126 rows |

**Practical read:** only the top four carry non-trivial rerun risk. Below ~0.25%
the revisions touch a few hundred rows in specific overlap years — material for a
tight institution-level replication, negligible for aggregate trends.

---

## The Grad-Rates (150%) Deep-Dive — full supersession

Portal 0.26.1's changelog documents a "grad-rates-150% year alignment
(1996-2023)" correction. Its data manifestation is the single most important drift
fact in this update:

- **Rows: 10,690,508 → 6,141,988.** The old extract carried **5,292,321 full-key
  duplicate rows (~49.5% of it)** and 761,154 exact whole-row duplicates. The new
  file has **zero** duplicates.
- **Not a year relabel.** On the clean 1:1 subset the survey year moved for 0.0%
  of entities, yet **100%** had at least one grad-rate value change. Per-column
  change rates: `completers_100pct` 100%, `still_enrolled_long_program` 99.0%,
  `exclusions` 88.1%, `completion_rate_150pct` 84.5%, `completers_150pct` 12.3%;
  `fips` 0% (identifier stable).
- **Interpretation:** the "year alignment" correction manifested as
  **(a) de-duplication of a massively duplicated old extract + (b) wholesale
  revaluation of the grad-rate measures**, not a survey-year relabel.

**Any pre-v2 analysis that used `colleges_ipeds_grad-rates` (150%) is superseded in
full** — it was computed on ~2x duplicated rows with pre-revision values. Re-run it
entirely against v0.26.1; do not attempt to reconcile old and new row-for-row.

---

## Tier 3: Row-Grain Expansion (new rows, matched cells stable)

- **`crdc/schools_crdc_discipline_k12_2020`** — 5,854,500 → 8,196,300 rows
  (4,719,721 identical rows); genuine dtype change (see Tier 5).
- **`crdc/schools_crdc_discipline_k12_2021`** — 5,880,600 → 8,232,840;
  keyed-join matched 5,830,740 rows with **0% value change**, plus **2,402,100
  new rows** (new disaggregation/entity rows).

Both are universe/disaggregation expansions of the CRDC discipline files.
Cell-level trends on matched entities are stable; anything sensitive to row counts,
coverage, or universe size changes.

---

## Tier 4: Cosmetic Re-encoding (0% substantive — benign if sentinels handled)

Nine pairs show 0% substantive change. Their raw change rates (up to 100%) are
entirely `null → {-1,-2,-3}` re-encodings:

`admissions-enrollment`, `ay_room_board_other`, `ay_tuition_fees`,
`ay_tuition_firstprof`, `grad-rates-200pct`, `institutional-characteristics`,
`py_room_board_other`, `py_tuition_cip`, `schools_ccd_directory`.

These nine are the fully-cosmetic members of the broader **cosmetic-recode drift
class**, which the battery assigns to **13** pairs. The other four —
`directory` (0.224%), `student-faculty-ratio` (0.156%), `fall-retention`
(0.122%), and `enrollment-fte` (0.029%) — are dominated by the same
`null → sentinel` re-encoding but *also* carry the sub-0.25% substantive
revisions itemized in Tier 2, so they are not fully benign. (The substantive
pairs `salaries_is` and `academic_libraries` likewise contain large re-encoding
*portions*, but their drift class is substantive-revision, not cosmetic-recode —
see Tier 2; they are not among the 13.)

Scale example: `institutional-characteristics` had **25,325,115 changed cells, 0
substantive**; `ay_tuition_fees` 3,385,392 changed cells, 0 substantive (this pair
was mis-tagged `+dtype` in a pre-correction run — the tag was a conversion
artifact, now gone). **No rerun impact if your code maps sentinels/nulls to
missing.**

---

## Tier 5: Dtype-Representation Change (genuine — one pair only)

The schema tier is nearly silent. The **only** genuine dtype change across the 26
old↔new pairs the battery compared:

- **`crdc/schools_crdc_discipline_k12_2020`**: `crdc_id` / `leaid`
  `Int64 → String`. The 2020 (and 2021) discipline id domain went alphanumeric, so
  these ids can no longer be integers. Downstream joins keying on these columns
  must cast consistently to String.

> **Scope of this claim.** "Only genuine dtype change" is scoped to the specific
> old↔new file *pairs* the drift battery compared — it is true for those pairs. It
> does **not** mean the 2020 CRDC vintage is uniformly typed: a 2026-08-07
> per-file audit found id dtypes vary *within* the 2020 vintage
> (`school_characteristics` all String; `discipline_k12_2020` `ncessch` Int64;
> `enrollment_k12_2020` `crdc_id` Int64; `harass_bully_students_2020` all three
> Int64). The Int64→String conversion above is **not** applied uniformly across all
> 2020 CRDC files. Always inspect the actual file schema before joining — see
> `datasets-reference.md` (CRDC ID columns) and `education-data-source-crdc`.

The three `+dtype` tags from an earlier pre-correction battery (saipe `leaid`,
ipeds `ay_tuition_fees` pct columns, ipeds `fall-retention` counts) were
conversion artifacts and have **vanished** — those files now match the old
vintage's dtypes.

> **Broader identifier-typing reality.** Beyond this one flip, the mirror has **no
> universal identifier contract** — per-file id typing is heterogeneous (`leaid`
> is native-width String in `districts_ccd_finance`, Int64 in `lea_directory` and
> `districts_saipe`; crdc ids Int64 in 2020's older files but String where domains
> went alphanumeric). The skills' 12/7-char string materialization guidance is an
> **analysis-time normalization** contract, not a description of raw file dtypes.
> Cast/normalize identifiers on read. See `education-data-source-ccd`
> (variable-definitions.md) and `education-data-source-crdc` (data-quality.md) for
> the per-file detail, and the `tidyverse` skill (io.md) for the R-Arrow
> `string_view` read hazard on 75 carried-forward files.

---

## Reruns-Implications Quick Table

Given a pre-v2 analysis, this is what to expect when re-running against v0.26.1:

| If your analysis used… | …expect |
|------------------------|---------|
| `grad-rates` (150%), any year | **Full re-run required** — dedup + revaluation supersedes it entirely |
| `grad-rates-pell`, years 2015/2017 | Real revision (71.5% of matched rows); re-run |
| `salaries_is` average salary | Small real revision (3.12%); re-run if institution-level |
| `academic_libraries`, year 2020 | Minor real revision (2.06%, 659 rows) |
| `directory` / `student-faculty-ratio` / `fall-retention` / `enrollment-fte` | Sub-0.25% revisions in specific overlap years — check only for tight replications |
| crdc discipline 2020/2021 | Universe expanded (~+40% rows); matched cells stable — recheck coverage/counts, not trends |
| any of the 9 fully-cosmetic recode pairs | No change **if** sentinels/nulls treated as missing (the other 4 cosmetic-class pairs are the sub-0.25% `directory`/`student-faculty-ratio`/`fall-retention`/`enrollment-fte` row above) |
| joins on crdc_id/leaid (crdc 2020/2021) | Cast to String — dtype flipped Int64→String |
| new years / new-only files | Purely additive; safe |

**Reproducibility discipline:** to reproduce a pre-2026q3 result exactly, fetch
against the **frozen predecessor** (Portal v0.24.0) per the "Reproducing a
pre-2026q3 analysis" section of the parent skill (`SKILL.md`), and cite
v0.24.0 — do not mix vintages in one analysis.
