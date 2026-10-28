# --- Config ---
# INTENT: Mechanically render one variable-dictionary markdown file per source (14 expected)
#         from the Portal varlist (41_variable_inventory) joined through the endpoint<->file
#         bridge (script 53). Organize each file by dataset family (year-collapsed mirror file
#         family), collapsing disaggregation-route duplicates so each variable appears once per
#         family, with the canonical mirror path and contributing endpoint routes cited.
# REASONING: A mirror-first skill rewrite needs a generated, regenerable variable reference tied
#            to concrete mirror parquet paths — not hand-maintained tables that silently drift.
# ASSUMES: Each endpoint maps to exactly ONE year-collapsed data family (verified in prep:
#          0 endpoints span >1 family; 0 families span >1 source), so the 2994 varlist rows
#          partition cleanly into family sections. Values strings are preserved verbatim
#          (only whitespace-normalized + pipe-escaped) — no code:label invention.
# REVISION _b (2026-10-28, citation-fidelity sweep batch 8 round 4): same inputs and vintage as
#          _a; adds the `# --- Overrides ---` declared-vs-observed table below, writes to a new
#          OUT_DIR so the 2026-08-08 outputs are kept, and names itself as SELF.
# REVISION _c (2026-10-28): _b failed its own Validate check 5 — the bare "research/" substring
#          test matched the Portal's IPEDS award-level labels ("Doctor's degree,
#          research/scholarship"), which are declared varlist text, not a workspace path. _c narrows
#          the check to research-workspace path forms and sets SELF to this file. Nothing else changes.
# REVISION _d (2026-10-28, round 4 cycle 2, per the review
#          PN/2026-10-28_search-agent_phase4-batch8-R4-generator-review.md): corrects override #4
#          (B1: the 2000-file schools geoid_block sentence rested on a 12-digit divisor applied to
#          10-11-digit values), scopes #12 (W1) and #2 (N1) to the files actually profiled, qualifies
#          #3 (N10), adds legend guards to the six type-only entries (N3), makes the probe date a
#          per-entry field and asserts HF_REVISION equals the probed revision (N8), widens the leak
#          check (N4), rewords the third and sentinel caveats (N5, N6), and adds per-column SAIPE
#          entries from a fresh all-column probe of the pinned file (W3, 2026-10-28). Inputs, vintage
#          and OUT_DIR are unchanged; SELF names this file.
import polars as pl
import re
from pathlib import Path
from datetime import date

BRIDGE = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/53_endpoint_file_bridge.parquet"
GT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth"
VAR_PATH = f"{GT}/41_variable_inventory.parquet"

# INTENT (_b): write to a new folder so the 2026-08-08 generated set stays untouched.
# REASONING: CLAUDE.md § Versioning & Naming — new outputs never overwrite an earlier run's outputs.
# ASSUMES: the parent workspace exists (it does: research/2026-08-06_FrameworkDev_MirrorV2Update/).
#          (_d) Overwriting _c's output in this same folder is intended: _c's files are superseded.
OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-10-28_dictionary-regeneration-overrides/generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HF_REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
GEN_DATE = date.today().isoformat()
# INTENT (_b, _c, _d): the generated headers name the script that produced them, so SELF is this revision.
SELF = "/daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries_d.py"

EXPECTED_SOURCES = ["ccd", "crdc", "csafety", "eada", "edfacts", "fsa", "ipeds",
                    "meps", "nacubo", "nccs", "nhgis", "pseo", "saipe", "scorecard"]

# --- Overrides ---
# INTENT: Declared-vs-observed override table. Each entry adds, beside the Portal varlist's
#         declared label/type/legend (kept verbatim), what file-first probes of the pinned mirror
#         (revision PROBED_REVISION) actually found where it contradicts or qualifies the declared
#         side. Variable-level entries are keyed (source, family_key, variable); family-level
#         entries are keyed (source, family_key). Each entry carries its own `probe_date`.
# REASONING: The dictionaries are generated, so hand-editing them would be lost at the next run;
#            the generator is the single place to record observed facts. Keeping the declared
#            legend verbatim and appending the observation preserves declared-vs-observed
#            transparency instead of silently replacing Portal metadata.
# ASSUMES: Each override's `expect_*` fields describe the declared side as the 2026-08-07 varlist
#          and 2026-08-08 bridge render it; the render loop and Validate fail loudly if a key
#          matches no row (stale key) or the declared side has drifted (stale override). The
#          expect_* checks cannot detect a change on the OBSERVED side: that is what the
#          HF_REVISION assert below is for — every entry describes PROBED_REVISION only.
# Evidence strings cite probe logs in a research workspace — maintainer-only, not shipped. The
# RENDERED text never cites them (asserted in Validate check 5).
PROBE_WS = "maintainer-only, not shipped: /daaf/research/2026-09-18_AdHoc_Typesafe_Classifier_Experiments/probes/"
# INTENT (_d): the revision every override was probed against, and the label template that renders it.
# REASONING: _c hard-coded the revision and the date in three literals (review N8); one constant plus a
#            per-entry `probe_date` keeps the label truthful when entries come from probes on different days.
# ASSUMES: all current entries were probed on PROBED_REVISION (each cited log asserts it via X-Repo-Commit).
PROBED_REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
OBS_LABEL_T = "**Observed on pinned mirror (rev `{rev}`, probe {date}):**"
OBS_COUNT_T = "**observed on pinned mirror (rev `{rev}`, probe {date})**"
SENT3 = '"-3" : "Suppressed data"'  # the standard sentinel legend entry, used as a legend guard (N3)
SAIPE_PROBE = "2026-10-28_r4d_saipe_allcolumns_probe.py log"

VAR_OVERRIDES = [
    # 1 — NHGIS colleges geocode_accuracy: codebook 1-4 labels not observed; a match score instead.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "geocode_accuracy",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": '"4" : "Did not geocode"', "expect_values_lacks": None,
     "obs_type": None,
     "note": "values are a geocoder match score from 61 to 100, plus -2, in all 4 census-vintage files; "
             "codes 1, 2, 3 and 4 never occur. Every row is -2 in data years 2018-2023, and no earlier row is -2.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log, each colleges file: 'geocode_accuracy min -2, max 100, "
                 "nulls 0, distinct 32, rows with value in codebook set [1, 2, 3, 4, -2]: 38564', bucket '<0 ┆ 38564', "
                 "'negative geocode_accuracy values present: [-2]'; 2026-10-27_mD_nhgis_probe_a.py log, each colleges "
                 "file: 'smallest non-negative geocode_accuracy: 61; distinct non-negative values: 31' and -2 rows by "
                 "year listing only '2018 ┆ 6857 ┆ 6857 ┆ 1.0' through '2023 ┆ 6163 ┆ 6163 ┆ 1.0'"},
    # 2 — NHGIS schools geocode_accuracy: Float64; -2 for every row 2017-2023. (_d, N1) The "both are 4"
    #     claim is scoped to the 1990 and 2010 files, the only two mD_a profiled.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}", "variable": "geocode_accuracy",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": '"4" : "Did not geocode"', "expect_values_lacks": None,
     "obs_type": "float (Float64; all values integral)",
     "note": "values are a geocoder match score up to 100, plus -2, with 805 nulls per file. Each file has 2 rows "
             "with a value from 1 to 4; in the 1990 and 2010 files (the two tested) both are 4, so codes 1, 2 and 3 "
             "do not occur there. Every row is -2 in data years 2017-2023, and no earlier row is -2 (year pattern "
             "tested in the 1990 and 2010 files).",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log, each schools file: 'dtypes: geocode_accuracy=Float64', "
                 "'min -2.0, max 100.0, nulls 805, distinct 35, rows with value in codebook set [1, 2, 3, 4, -2]: "
                 "714537, non-integer values: 0', buckets '0-4 ┆ 2' and '<0 ┆ 714535'; "
                 "2026-10-27_mD_nhgis_probe_a.py log (FILES: schools 1990 and 2010 only): 'smallest non-negative "
                 "geocode_accuracy: 4.0' and -2 rows by year listing only '2017 ┆ 102337 ┆ 102337 ┆ 1.0' through "
                 "'2023 ┆ 102274 ┆ 102274 ┆ 1.0'"},
    # 3 — NHGIS colleges geoid_block: Int64 (declared string); never a 15-digit block id. (_d, N10) The 2000
    #     claim rests on mD_a's equality test against GEOIDs rebuilt from the file's own columns (no divisor),
    #     but that file's county_fips_geo is itself not a county code (#6a), so the qualifier is rendered.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "geoid_block",
     "probe_date": "2026-10-27",
     "expect_type": "string", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": "integer (Int64 in all 4 files)",
     "note": "never a 15-digit block GEOID. In the 2010 and 2020 census-vintage files it equals the 12-digit "
             "block-group GEOID rebuilt from the file's own columns (Int64, so the leading zero drops when the "
             "state FIPS is below 10; zero-pad to 12). In the 1990 file it equals the 11-digit tract GEOID. "
             "In the 2000 file it matches neither form rebuilt from the file's own columns (whose "
             "`county_fips_geo` is not a county code; see that row).",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log: 'geoid_block=Int64' in all 8 files, lengths [10, 11] "
                 "(1990/2000) and [11, 12] (2010/2020); 2026-10-27_mD_nhgis_probe_a.py log: colleges 1990 "
                 "'geoid_block == tract GEOID (11-digit form): 331055; == block-group GEOID (12-digit form): 0', "
                 "colleges 2000 '...: 0; ...: 0', colleges 2010 '...: 0; ...: 337155', colleges 2020 '...: 0; ...: 337203' "
                 "(equality tests; mD_a code line 42 rebuilds county5 from the file's own county_fips_geo; the mD2_a "
                 "divisor line is not used here)"},
    # 4 — NHGIS schools geoid_block: same finding for 1990/2010/2020. (_d, B1) The 2000 sentence no longer
    #     claims the leading digits lack the state FIPS: that rested on mD2_a's 1e10 divisor applied to
    #     10-11-digit values; review probe r4review_03 found its 5 logged samples DO start with the state FIPS.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}", "variable": "geoid_block",
     "probe_date": "2026-10-27",
     "expect_type": "string", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": "integer (Int64 in all 4 files)",
     "note": "never a 15-digit block GEOID. In the 2010 file it equals the 12-digit block-group GEOID rebuilt from "
             "the file's own columns (Int64, so the leading zero drops when the state FIPS is below 10; zero-pad "
             "to 12); the 2020 file has the same 11-12-digit lengths and state+county prefix. In the 1990 file it "
             "equals the 11-digit tract GEOID. In the 2000 file it has 10-11 digits and its composition was not "
             "established.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe_a.py log: schools 1990 'geoid_block == tract GEOID (11-digit "
                 "form): 3627493; == block-group GEOID (12-digit form): 0', schools 2010 '...: 0; ...: 3674498'; "
                 "2026-10-27_mD_nhgis_probe.py log: schools 2020 lengths '11 ┆ 651648', '12 ┆ 3023920'; "
                 "2026-10-27_mD2_nhgis_fips_probe_a.py log: schools 2020 'leading 5 digits == county_fips_geo: "
                 "3675568'; 2026-10-27_mD_nhgis_probe.py log, schools 2000 lengths '10 ┆ 651302', '11 ┆ 2976191' "
                 "(the mD2_a divisor test assumed 12 digits and is not evidence for this file: "
                 "2026-10-28_r4review_03_geoid2000-divisor-check.py log 'matches with mD2_a's 1e10 divisor: 0 of 5; "
                 "with the 1e9 divisor: 5 of 5')"},
    # 5a — NHGIS colleges state_fips_geo: 1990 file stores state FIPS x 10.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "state_fips_geo",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": '"39" : "Ohio"', "expect_values_lacks": None,
     "obs_type": None,
     "note": "the 1990 census-vintage file stores the state code times 10 (Ohio is 390) in 331,043 of 331,049 "
             "college rows matched by unitid and year to the 2010 file; the 2000, 2010 and 2020 files store the "
             "plain code.",
     "evidence": PROBE_WS + "2026-10-27_mD2_nhgis_fips_probe_a.py log, colleges 1990: 'joined to 2010 reference on "
                 "unitid+year: 331049; state == ref: 0; state == ref*10: 331043', 'state_fips_geo range 10-560'; "
                 "colleges 2000/2010/2020: 'state == ref: 330623' (of 330629), '337155' (of 337155), '337155' (of "
                 "337155), 'state == ref*10: 0'; 2026-10-27_mD_nhgis_probe_a.py log colleges 1990 sample row "
                 "'1980 ┆ 390 ┆ 39057'"},
    # 5b — NHGIS schools state_fips_geo: same.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}", "variable": "state_fips_geo",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": '"39" : "Ohio"', "expect_values_lacks": None,
     "obs_type": None,
     "note": "the 1990 census-vintage file stores the state code times 10 (Alabama is 10) in 3,627,315 of 3,627,352 "
             "school rows matched by ncessch and year to the 2010 file; the 2000, 2010 and 2020 files store the "
             "plain code.",
     "evidence": PROBE_WS + "2026-10-27_mD2_nhgis_fips_probe_a.py log, schools 1990: 'joined to 2010 reference on "
                 "ncessch+year: 3627352; state == ref: 0; state == ref*10: 3627315', sample '10000200277 ┆ 1994 ┆ 1 ┆ "
                 "10 ┆ 1'; schools 2000/2010/2020: 'state == ref: 3624358' (of 3624395), '3674498', '3674498', "
                 "'state == ref*10: 0'"},
    # 6a — NHGIS colleges county_fips_geo: 2000 file is not a county FIPS code.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "county_fips_geo",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "the 2000 census-vintage file does not hold a county FIPS code: values run 10-990, never 5 digits, and "
             "in 239,946 of 330,629 college rows matched to the 2010 file they equal 10 times the 3-digit county "
             "code (Ohio county 057 is 570). The 1990, 2010 and 2020 files hold the 5-digit state+county code.",
     "evidence": PROBE_WS + "2026-10-27_mD2_nhgis_fips_probe_a.py log, colleges 2000: 'county_fips_geo with leading "
                 "digits == fips (5-digit state+county form): 0; values < 1000: 330635; range 10-990', 'joined to "
                 "2010 reference on unitid+year: 330629; ... county == (ref%1000)*10: 239946'; colleges "
                 "1990/2010/2020: 'values < 1000: 0'; 2026-10-27_mD_nhgis_probe_a.py log colleges 2000 sample "
                 "'1980 ┆ 39 ┆ 570' vs colleges 2010 '1980 ┆ 39 ┆ 39057'"},
    # 6b — NHGIS schools county_fips_geo: same.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}", "variable": "county_fips_geo",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "the 2000 census-vintage file does not hold a county FIPS code: values run 10-990, never 5 digits, and "
             "in 2,509,923 of 3,624,395 school rows matched to the 2010 file they equal 10 times the 3-digit county "
             "code (Alabama county 073 is 730). The 1990, 2010 and 2020 files hold the 5-digit state+county code.",
     "evidence": PROBE_WS + "2026-10-27_mD2_nhgis_fips_probe_a.py log, schools 2000: 'county_fips_geo with leading "
                 "digits == fips (5-digit state+county form): 0; values < 1000: 3624536; range 10-990', 'joined to "
                 "2010 reference on ncessch+year: 3624395; ... county == (ref%1000)*10: 2509923', sample "
                 "'10000200277 ┆ 1994 ┆ 1 ┆ 1 ┆ 1 ┆ 730 ┆ 1073'; schools 1990/2010/2020: 'values < 1000: 0'"},
    # 10 — IPEDS completions 6-digit cipcode_6digit: Int64 drops the leading zero.
    {"source": "ipeds", "family_key": "ipeds/colleges_ipeds_completions-6digcip_{year}", "variable": "cipcode_6digit",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "stored as Int64, so CIP series 01-09 lose their leading zero (CIP 03.0101 is 30101); zero-pad to 6 "
             "digits before matching NCES CIP code strings (2023 file probed).",
     "evidence": PROBE_WS + "2026-10-27_mB_ipeds-completions_probe.py log line 148 '--- 6-digit shard 2023: "
                 "cipcode_6digit dtype Int64', line 149 'UC Berkeley 6-digit codes ... [99, 30101, 30103, ...]'"},
    # 11 — PSEO opeid: String in 2001-2018 shards, Int64 in 2019-2021.
    {"source": "pseo", "family_key": "pseo/colleges_pseo_{year}", "variable": "opeid",
     "probe_date": "2026-10-27",
     "expect_type": "string", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": "string (2001-2018 files) / integer (Int64, 2019-2021 files)",
     "note": "the Int64 files drop the leading zeros (365800 where the 2018 file has \"00365800\"), so cast to "
             "string and zero-pad to 8 before concatenating years or joining.",
     "evidence": PROBE_WS + "2026-10-27_mA_pseo_probe_a.py log: 'String-opeid shards: [2001, ..., 2018]', "
                 "'Int64-opeid shards: [2019, 2020, 2021]', 2018 '00365800 ┆ 228778', 2019 '365800 ┆ 228778'"},
    # 12 — PSEO cipcode: bare 2-digit codes, not the 6-digit-style legend values. (_d, W1) Values were
    #      profiled in 2 of 21 files (mA2 PROFILE_YEARS = [2018, 2021]); the dtype in all 21.
    {"source": "pseo", "family_key": "pseo/colleges_pseo_{year}", "variable": "cipcode",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": '"110000" : "Computer and information sciences', "expect_values_lacks": None,
     "obs_type": None,
     "note": "the 2018 and 2021 files (the two profiled) hold only bare 2-digit CIP family codes stored as integers "
             "(e.g. 1, 11, 14, 52) and 99, not the 6-digit-style values this legend lists: cipcode == 11 matches "
             "150,390 rows in 2018 and 34,020 in 2021, and cipcode == 110000 matches 0 in both. The column is Int64 "
             "in all 21 files.",
     "evidence": PROBE_WS + "2026-10-27_mA2_pseo_cipcode_probe.py log: 'distinct cipcode dtypes across shards: "
                 "['Int64']'; lines 143-149: 'shard 2018 ... cipcode dtype Int64', 'distinct cipcode values (45): "
                 "[1, 3, 4, ..., 52, 54, 99]', 'cipcode == 11: 150390 rows', 'cipcode == 110000: 0 rows'; lines "
                 "182-188: shard 2021 'cipcode == 11: 34020 rows', 'cipcode == 110000: 0 rows'"},
    # 13 — EADA ath_classification_code: code 11 occurs but is missing from the Portal legend.
    {"source": "eada", "family_key": "eada/colleges_eada_inst_characteristics", "variable": "ath_classification_code",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": '"12" : " NJCAA Division I"', "expect_values_lacks": '"11" :',
     "obs_type": None,
     "note": "code \"11\" occurs although this legend omits it: 37 rows in 2002-2014, none from 2015; the rows from "
             "2004 on carry ath_classification_name \"NAIA Division III\".",
     "evidence": PROBE_WS + "2026-10-27_mE_eada_probe.py log line 99 '11 ┆ 37 ┆ 2002 ┆ 2014 ┆ [\"NAIA Division "
                 "III\"]', line 110 'code 11 rows: 37; years with code 11: [2002, ..., 2014]', line 168 "
                 "'11 ┆ NAIA Division III ┆ 24 ┆ 2004 ┆ 2014'"},
    # 14 — Campus Safety bias: no sentinel occurs; nulls instead.
    {"source": "csafety", "family_key": "csafety/colleges_csafety_hate_crimes", "variable": "bias",
     "probe_date": "2026-10-27",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2 or -3 value occurs; the non-null values are 1-9 and 99, and 352,310 rows are null.",
     "evidence": PROBE_WS + "2026-10-27_mC_campus-safety_probe_b.py log line 290 'distinct bias (non-null): [1, 2, 3, "
                 "4, 5, 6, 7, 8, 9, 99]; null bias rows: 352310'"},
    # 15-24 (_d, W3) — SAIPE, one entry per column of saipe/districts_saipe, from a fresh all-column probe of
    #     the pinned file (2026-10-28; 382,099 rows; 10 columns, all in the dictionary). Each note renders only
    #     what that probe printed for the column: dtype, nulls, -1/-2/-3 counts, other negatives, min/max.
    # REASONING: replaces the hand-added 2026-09-15 block, whose probe tested 3 of 10 columns and sits in
    #     another workspace's scratch folder; this probe covers every column and lives in {WS}/probes/.
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "leaid",
     "probe_date": "2026-10-28",
     "expect_type": "string", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": "integer (Int64)",
     "note": "no -1, -2 or -3 value and no null occurs. As an integer it carries no leading zeros: values have 7 "
             "digits in 326,894 rows, 6 in 55,204 and 4 in 1 row (range 7230-7200030), so zero-pad to 7 before "
             "joining to a string `leaid`.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 112 'leaid | Int64 | 0 | 0 | 0 | 0 | 0 | 7230 | 7200030', lines "
                 "125-127 '4 ┆ 1', '6 ┆ 55204', '7 ┆ 326894'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "year",
     "probe_date": "2026-10-28",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2 or -3 value and no null occurs; 28 distinct years between 1995 and 2024.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 111 'year | Int64 | 0 | 0 | 0 | 0 | 0 | 1995 | 2024', "
                 "'year range: 1995-2024; distinct years: 28'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "fips",
     "probe_date": "2026-10-28",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2 or -3 value and no null occurs; values run from 1 to 72.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 113 'fips | Int64 | 0 | 0 | 0 | 0 | 0 | 1 | 72'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "district_id",
     "probe_date": "2026-10-28",
     "expect_type": "string", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": "integer (Int64)",
     "note": "no -1, -2 or -3 value and no null occurs; values run from 1 to 99965.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 106 'district_id | Int64 | 0 | 0 | 0 | 0 | 0 | 1 | 99965'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "district_name",
     "probe_date": "2026-10-28",
     "expect_type": "string", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no \"-1\", \"-2\" or \"-3\" value and no null occurs.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 107 'district_name | String | 0 | 0 | 0 | 0 | 0 | (string) | (string)'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "est_population_total",
     "probe_date": "2026-10-28",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2, -3 or other negative value and no null occurs.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 108 'est_population_total | Int64 | 0 | 0 | 0 | 0 | 0 | 0 | 8622698'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "est_population_5_17",
     "probe_date": "2026-10-28",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2, -3 or other negative value and no null occurs.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 109 'est_population_5_17 | Int64 | 0 | 0 | 0 | 0 | 0 | 0 | 1399391'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "est_population_5_17_pct",
     "probe_date": "2026-10-28",
     "expect_type": "float", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2, -3 or other negative value occurs; 122 of the file's 382,099 rows are null. Values run "
             "from 0.0 to 1.0.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 102 'rows: 382099', line 115 'est_population_5_17_pct | Float64 | "
                 "122 | 0 | 0 | 0 | 0 | 0.0 | 1.0', line 117 'SCALE est_population_5_17_pct: min=0.0 max=1.0; rows > 1: 0'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "est_population_5_17_poverty",
     "probe_date": "2026-10-28",
     "expect_type": "integer", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2, -3 or other negative value and no null occurs.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 110 'est_population_5_17_poverty | Int64 | 0 | 0 | 0 | 0 | 0 | 0 | 487440'"},
    {"source": "saipe", "family_key": "saipe/districts_saipe", "variable": "est_population_5_17_poverty_pct",
     "probe_date": "2026-10-28",
     "expect_type": "float", "expect_values_contains": SENT3, "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2, -3 or other negative value occurs; 280 of the file's 382,099 rows are null. Values run "
             "from 0.0 to 1.0, a proportion, not a 0-100 percentage.",
     "evidence": PROBE_WS + SAIPE_PROBE + " line 102 'rows: 382099', line 114 'est_population_5_17_poverty_pct | "
                 "Float64 | 280 | 0 | 0 | 0 | 0 | 0.0 | 1.0', line 116 'SCALE est_population_5_17_poverty_pct: "
                 "min=0.0 max=1.0; rows > 1: 0'"},
]

FAM_OVERRIDES = [
    # 8 — IPEDS completions 2-digit: bridge counted 32 files; the pinned tree has 33 (2023 added in the v2 build).
    {"source": "ipeds", "family_key": "ipeds/colleges_ipeds_completions-2digcip_{year}",
     "probe_date": "2026-10-27",
     "expect_bridge_files": 32, "obs_files": 33, "obs_years": "1991-2023", "bullet": None,
     "evidence": PROBE_WS + "2026-10-27_mB_ipeds-completions_probe.py log line 112 '2-digit shards: 33, years [1991, "
                 "..., 2023]'"},
    # 9 — IPEDS completions 6-digit: bridge counted 40; pinned tree has 41.
    {"source": "ipeds", "family_key": "ipeds/colleges_ipeds_completions-6digcip_{year}",
     "probe_date": "2026-10-27",
     "expect_bridge_files": 40, "obs_files": 41, "obs_years": "1983-2023", "bullet": None,
     "evidence": PROBE_WS + "2026-10-27_mB_ipeds-completions_probe.py log line 113 '6-digit shards: 41, years 1983-2023'"},
    # 7a — NHGIS colleges: {year} in the path is the census-geography vintage. Heading NOT renamed
    #      (explorer colleges-datasets.md cites the § `nhgis/colleges_nhgis_geog_{year}` heading).
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}",
     "probe_date": "2026-10-27",
     "expect_bridge_files": 4, "obs_files": None, "obs_years": None,
     "bullet": "here `{year}` is the census-geography vintage (`1990`, `2000`, `2010`, `2020`), not a data year. "
               "Each of the 4 files holds every data year: 1980 and 1984-2023 (1981-1983 absent), 337,222 rows per file.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log: 'NHGIS parquet files at pinned revision (8): "
                 "[...colleges_nhgis_geog_1990 ... _2020 ...]', each colleges file 'rows 337222' and 'years: "
                 "1980-2023 (41 distinct); gaps inside range: [1981, 1982, 1983]'"},
    # 7b — NHGIS schools: same; heading cited by explorer schools-datasets.md.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}",
     "probe_date": "2026-10-27",
     "expect_bridge_files": 4, "obs_files": None, "obs_years": None,
     "bullet": "here `{year}` is the census-geography vintage (`1990`, `2000`, `2010`, `2020`), not a data year. "
               "Each of the 4 files holds every data year: 1986-2023 with no gaps, 3,676,375 rows per file.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log: each schools file 'rows 3676375' and 'years: 1986-2023 "
                 "(38 distinct); gaps inside range: []'"},
]

# INTENT: index the overrides by key and keep a hit counter per key for the Validate section.
# REASONING: a key that matches zero rendered rows is stale (renamed family/variable) and must fail loudly.
# ASSUMES: keys are unique within each list (asserted here).
VAR_OV = {(o["source"], o["family_key"], o["variable"]): o for o in VAR_OVERRIDES}
FAM_OV = {(o["source"], o["family_key"]): o for o in FAM_OVERRIDES}
assert len(VAR_OV) == len(VAR_OVERRIDES), "duplicate variable-override key"
assert len(FAM_OV) == len(FAM_OVERRIDES), "duplicate family-override key"
for k in list(VAR_OV) + list(FAM_OV):
    assert k[1].split("/")[0] == k[0], f"override key source/family mismatch: {k}"
# INTENT (_d): every entry carries a well-formed probe date (it is rendered into the label and caveat).
for o in VAR_OVERRIDES + FAM_OVERRIDES:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", o.get("probe_date") or ""), f"bad probe_date: {o['family_key']}"
# INTENT (_d, N8): refuse to render observations under a different mirror revision than the one probed.
# REASONING: the expect_* guards only see the declared side; a vintage bump with unchanged declared text would
#            otherwise carry 0ad00ce0 observations into a dictionary whose header names a new revision.
# ASSUMES: a maintainer bumping HF_REVISION re-probes each entry and updates PROBED_REVISION, or empties the lists.
if VAR_OVERRIDES or FAM_OVERRIDES:
    assert HF_REVISION == PROBED_REVISION, \
        f"HF_REVISION {HF_REVISION} != PROBED_REVISION {PROBED_REVISION}: re-probe or remove the overrides"
var_hits = {k: 0 for k in VAR_OV}
fam_hits = {k: 0 for k in FAM_OV}
print(f"Overrides loaded: {len(VAR_OV)} variable-level, {len(FAM_OV)} family-level; probed revision {PROBED_REVISION}")

# --- Load ---
bridge = pl.read_parquet(BRIDGE)
var = pl.read_parquet(VAR_PATH)
print(f"Loaded bridge: {bridge.shape}, var inventory: {var.shape}")

# --- Transform: year-collapse to family_key ---
# INTENT: family_key = canonical mirror path with the year token replaced by {year}.
# REASONING: yearly shards (schools_ccd_enrollment_1986..2022) are one dataset family; the
#            {year} placeholder is the mirror-agnostic path the skill will cite.
# ASSUMES: a year token is a 4-digit 19xx/20xx bounded by '_' (verified: 0 collapse misses).
def collapse(key):
    if key is None:
        return None
    return re.sub(r'_(19|20)\d{2}(?=$|_)', '_{year}', key)

# endpoint-linked data rows only (exclude file_no_endpoint / codebook rows)
bd = bridge.filter(
    (pl.col("kind") == "data") & pl.col("endpoint_id").is_not_null()
).with_columns(
    pl.col("canonical_key").map_elements(collapse, return_dtype=pl.Utf8).alias("family_key")
).with_columns(
    pl.col("family_key").str.split("/").list.first().alias("source")
)

# endpoint -> family map (must be 1:1)
ep_fam = bd.select(["endpoint_id", "family_key", "source", "route"]).unique()
assert ep_fam.select(["endpoint_id"]).n_unique() == ep_fam.select(["endpoint_id", "family_key"]).n_unique(), \
    "endpoint maps to >1 family_key"

# family -> concrete validated canonical keys (for path listing + validation)
fam_keys = bd.group_by("family_key").agg([
    pl.col("canonical_key").n_unique().alias("n_mirror_files"),
    pl.col("in_mirror_parquet").any().alias("any_validated_key"),  # from script 53 validation
])
# VALIDATE: every family cites >=1 canonical key that passed script 53's mirror validation
assert fam_keys.filter(~pl.col("any_validated_key")).height == 0, \
    "A family has no mirror-validated canonical key"
print(f"Families: {fam_keys.height} (all cite >=1 mirror-validated canonical key)")

# family -> contributing endpoint routes
fam_routes = bd.group_by("family_key").agg(
    pl.col("route").unique().sort().alias("routes")
)

# --- Join variables to families in varlist order ---
# INTENT: attach family + source to every varlist row via its endpoint_id (1:1 to family).
var = var.with_row_index("varlist_idx")
vf = var.join(ep_fam.select(["endpoint_id", "family_key", "source"]), on="endpoint_id", how="left")
assert vf.filter(pl.col("family_key").is_null()).height == 0, "varlist row without a family"

# --- Collapse disaggregation duplicates: one row per (family_key, variable) ---
# REASONING: disaggregation routes (e.g. .../enrollment/{year}/race/ vs .../sex/) repeat the
#            same variables; keep the FIRST occurrence in varlist order (deterministic).
# ASSUMES: within (family,variable) label/type/values are consistent (verified: only 3 label
#          and 1 filter micro-conflicts across 2235 groups; min-varlist_idx resolves them).
ROWS_IN = vf.height
vf_sorted = vf.sort("varlist_idx")
rendered = vf_sorted.unique(subset=["family_key", "variable"], keep="first", maintain_order=True)
ROWS_OUT = rendered.height
print(f"DEDUPE: varlist rows in {ROWS_IN} -> unique (family,variable) out {ROWS_OUT}")

# --- Markdown escaping helper ---
def esc(s):
    if s is None:
        return ""
    s = str(s).replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace("|", "\\|")

def clean_type(s):
    return "" if s is None else str(s).strip()

def filter_flag(s):
    # is_filter is the string "1" for filterable vars; "None"/null otherwise.
    return "yes" if (s is not None and str(s).strip() == "1") else "no"

# Precompute per-family metadata dicts
routes_map = {r["family_key"]: r["routes"] for r in fam_routes.to_dicts()}
nfiles_map = {r["family_key"]: r["n_mirror_files"] for r in fam_keys.to_dicts()}

# --- Render one file per source ---
line_counts = {}
rendered_row_tally = 0
obs_marks_expected = {}
for source in EXPECTED_SOURCES:
    sub = rendered.filter(pl.col("source") == source)
    assert sub.height > 0, f"Source {source} has zero rendered rows"
    families = sorted(sub["family_key"].unique().to_list())
    # INTENT (_b): count the overrides that target this source, to decide on the third caveat and
    #              to check the rendered "Observed on pinned mirror" marks in Validate.
    # REASONING: the third caveat only explains observed notes, so it is rendered only where notes appear.
    # ASSUMES: every override for this source matches a rendered row/family (asserted in Validate).
    src_ovs = [o for k, o in VAR_OV.items() if k[0] == source] + [o for k, o in FAM_OV.items() if k[0] == source]
    n_src_overrides = len(src_ovs)
    obs_marks_expected[source] = n_src_overrides
    # INTENT (_d): the third caveat names the probe date(s) of this source's entries, not a fixed date.
    src_dates = " and ".join(sorted({o["probe_date"] for o in src_ovs}))

    lines = []
    # Header block: HTML comment + visible prose
    lines.append(f"<!-- MECHANICALLY GENERATED by {SELF} on {GEN_DATE}")
    lines.append(f"     from the Portal varlist captured 2026-08-07 at Portal v0.26.1 — the same")
    lines.append(f"     vintage as the pinned mirror (revision {HF_REVISION}).")
    lines.append(f"     Do not hand-edit; regenerate at the next mirror vintage. -->")
    lines.append("")
    lines.append(f"# Variable Dictionary — `{source}`")
    lines.append("")
    lines.append(f"**MECHANICALLY GENERATED** by `{SELF}` on {GEN_DATE} from the Portal varlist "
                 f"captured 2026-08-07 at Portal v0.26.1 — the same vintage as the pinned mirror "
                 f"(revision `{HF_REVISION}`). Do not hand-edit; regenerate at the next mirror vintage.")
    lines.append("")
    lines.append(f"> Caveat: the `urban_csv` fallback mirror is unpinned; these facts are "
                 f"guaranteed for the pinned Hugging Face vintage only.")
    lines.append("")
    # INTENT (_d, N6): sentinel caveat; the parenthetical now cites the 2026-10-28 all-column SAIPE probe.
    # REASONING: _a's wording ("found zero sentinel values and nulls for all missing") rested on a probe of
    #            3 of SAIPE's 10 columns; the new probe tested all 10 (see the SAIPE override entries).
    # ASSUMES: the SAIPE entries above carry that probe's per-column results (asserted by their hits).
    lines.append(f"> Caveat: the `coded values` column reproduces the Portal varlist's declared "
                 f"legend (including the standard `-1`/`-2`/`-3` missing codes) and does not "
                 f"assert those codes occur in the pinned mirror file — several mirror files "
                 f"carry nulls instead (a probe of the pinned SAIPE file on 2026-10-28 found no "
                 f"`-1`/`-2`/`-3` or other negative value in any of its 10 columns; its only missing "
                 f"values are nulls, in the two `_pct` columns). Test for nulls and for sentinels before treating "
                 f"either as the missing-value convention, and defer to the source skill's "
                 f"SKILL.md where it documents the observed convention.")
    lines.append("")
    # INTENT (_b, _d N5): third standing caveat, explaining the observed notes, in files that carry them.
    # REASONING: not every entry contradicts the varlist — the IPEDS counts correct the bridge and the NHGIS
    #            bullets clarify the path — so the wording says "contradicts or qualifies" (review N5).
    # ASSUMES: src_dates is non-empty whenever n_src_overrides > 0 (every entry has a probe_date).
    if n_src_overrides > 0:
        lines.append(f"> Caveat: entries marked **Observed on pinned mirror** record what file-first "
                     f"probes of the pinned revision found on {src_dates} where it contradicts or "
                     f"qualifies the Portal varlist or the bridge's file counts; they are added beside "
                     f"the declared label, type and legend, which are kept verbatim, and override "
                     f"nothing declared.")
        lines.append("")
    lines.append(f"Source `{source}`: {len(families)} dataset famil"
                 f"{'y' if len(families)==1 else 'ies'}, {sub.height} unique variables.")
    lines.append("")

    for fam in families:
        fam_rows = sub.filter(pl.col("family_key") == fam).sort("varlist_idx")
        rendered_row_tally += fam_rows.height
        routes = routes_map.get(fam, [])
        nfiles = nfiles_map.get(fam, 0)
        # INTENT (_b): apply a family-level override when one is keyed to (source, family).
        # REASONING: the bridge's file count can lag the pinned tree (IPEDS completions gained a
        #            2023 file in the v2 build); NHGIS needs a bullet explaining its {year} token.
        # ASSUMES: expect_bridge_files equals the bridge count; Validate fails if it no longer does.
        fov = FAM_OV.get((source, fam))
        if fov is not None:
            fam_hits[(source, fam)] += 1
            assert nfiles == fov["expect_bridge_files"], \
                f"stale family override {fam}: bridge now lists {nfiles}, expected {fov['expect_bridge_files']}"
        # {year} placeholder path already embedded in fam if yearly
        lines.append(f"## `{fam}`")
        lines.append("")
        if fov is not None and fov["obs_files"] is not None:
            # INTENT (_b): render the observed shard count and year range instead of the stale bridge count.
            # REASONING: the count is bridge output, not Portal-declared content, so replacing it hides nothing
            #            declared; the label (revision + this entry's probe date) marks it as observed.
            # ASSUMES: obs_files/obs_years come from the cited shard listing on PROBED_REVISION.
            obs_count = OBS_COUNT_T.format(rev=PROBED_REVISION[:8], date=fov["probe_date"])
            lines.append(f"- **Canonical mirror path:** `{fam}.parquet` "
                         f"({fov['obs_files']} mirror files, {fov['obs_years']}; {obs_count})")
        else:
            lines.append(f"- **Canonical mirror path:** `{fam}.parquet` "
                         f"({nfiles} mirror file{'s' if nfiles != 1 else ''})")
        route_cites = ", ".join(f"`{esc(r)}`" for r in routes)
        lines.append(f"- **Contributing endpoint route(s):** {route_cites}")
        if fov is not None and fov["bullet"] is not None:
            # INTENT (_b): extra family bullet (heading left unchanged so explorer § links still resolve).
            # REASONING: renaming `{year}` in the heading would break the explorer's § citations, so the
            #            census-vintage meaning is stated in a bullet instead.
            # ASSUMES: the bullet text contains no unescaped table syntax (it is a list item, not a cell).
            lines.append(f"- {OBS_LABEL_T.format(rev=PROBED_REVISION[:8], date=fov['probe_date'])} {fov['bullet']}")
        lines.append("")
        lines.append("| variable | label | type | filter? | coded values |")
        lines.append("|---|---|---|---|---|")
        for r in fam_rows.to_dicts():
            type_cell = clean_type(r['data_type'])
            values_cell = esc(r['values'])
            # INTENT (_b): apply a variable-level override: keep the declared type and legend verbatim,
            #              then append the observed type and note.
            # REASONING: declared-vs-observed transparency — the reader sees both, never a silent swap.
            # ASSUMES: the declared side still matches the override's expectations (asserted here).
            vov = VAR_OV.get((source, fam, r['variable']))
            if vov is not None:
                var_hits[(source, fam, r['variable'])] += 1
                assert type_cell == vov["expect_type"], \
                    f"stale override {source}/{fam}/{r['variable']}: declared type now {type_cell!r}"
                if vov["expect_values_contains"] is not None:
                    assert vov["expect_values_contains"] in (r['values'] or ""), \
                        f"stale override {source}/{fam}/{r['variable']}: legend lacks {vov['expect_values_contains']!r}"
                if vov["expect_values_lacks"] is not None:
                    assert vov["expect_values_lacks"] not in (r['values'] or ""), \
                        f"stale override {source}/{fam}/{r['variable']}: legend now has {vov['expect_values_lacks']!r}"
                if vov["obs_type"] is not None:
                    type_cell = f"{type_cell}; **observed:** {esc(vov['obs_type'])}"
                # INTENT (_d): the label carries this entry's own probe date (N8).
                obs = f"{OBS_LABEL_T.format(rev=PROBED_REVISION[:8], date=vov['probe_date'])} {esc(vov['note'])}"
                values_cell = f"{values_cell} ; {obs}" if values_cell else obs
            lines.append(
                f"| `{esc(r['variable'])}` | {esc(r['label'])} | {type_cell} "
                f"| {filter_flag(r['is_filter'])} | {values_cell} |"
            )
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    out_path = OUT_DIR / f"variable-dictionary-{source}.md"
    out_path.write_text(content)
    line_counts[source] = content.count("\n")

# --- Validate ---
# 1) exactly 14 files, all non-empty
written = sorted(OUT_DIR.glob("variable-dictionary-*.md"))
assert len(written) == 14, f"Expected 14 files, got {len(written)}"
for p in written:
    assert p.stat().st_size > 0, f"Empty file: {p}"
# 2) every rendered (family,variable) row landed in exactly one file section
assert rendered_row_tally == ROWS_OUT, \
    f"Rendered {rendered_row_tally} rows != {ROWS_OUT} unique (family,variable)"
# 3) every one of the 2994 varlist rows is represented in exactly one family section:
#    each varlist row's (family_key, variable) is present in the rendered set.
rendered_pairs = set(zip(rendered["family_key"].to_list(), rendered["variable"].to_list()))
vf_pairs = list(zip(vf["family_key"].to_list(), vf["variable"].to_list()))
missing = [p for p in vf_pairs if p not in rendered_pairs]
assert len(missing) == 0, f"{len(missing)} varlist rows not represented in any family section"
print(f"VALIDATION: all {ROWS_IN} varlist rows represented in exactly one family section.")
print(f"VALIDATION: 14 files written, all non-empty.")
# 4) (_b) every override key matched exactly one rendered row / family — a stale key fails here.
bad_var = {k: n for k, n in var_hits.items() if n != 1}
bad_fam = {k: n for k, n in fam_hits.items() if n != 1}
assert not bad_var, f"variable overrides not matched exactly once: {bad_var}"
assert not bad_fam, f"family overrides not matched exactly once: {bad_fam}"
print(f"VALIDATION: all {len(var_hits)} variable-level and {len(fam_hits)} family-level overrides matched exactly once.")
# 5) (_b) rendered text: the observed-mark count per file equals the overrides applied, and no
#    rendered file cites a research/ path (evidence stays in this script only).
for source in EXPECTED_SOURCES:
    txt = (OUT_DIR / f"variable-dictionary-{source}.md").read_text()
    n_marks = txt.count("Observed on pinned mirror (rev") + txt.count("observed on pinned mirror (rev")
    assert n_marks == obs_marks_expected[source], \
        f"{source}: {n_marks} observed marks rendered, expected {obs_marks_expected[source]}"
    # INTENT (_c): detect a research-workspace path (absolute, or relative with a dated folder name).
    # REASONING: a bare "research/" test also matches declared Portal text such as IPEDS
    #            "research/scholarship" (_b failed on it); workspace folders are date-prefixed.
    # ASSUMES: every DAAF research workspace folder starts with YYYY-MM-DD (CLAUDE.md naming convention).
    ws_paths = re.findall(r"(?:/daaf/research/|research/\d{4}-\d{2}-\d{2})", txt)
    assert not ws_paths, f"{source}: rendered file cites a research workspace path: {ws_paths[:3]}"
    # INTENT (_d, N4): also reject evidence-form strings that carry no research/ path.
    # REASONING: evidence strings start with PROBE_WS ("maintainer-only, not shipped: ...") and name
    #            probes/ logs; none may reach shipped text.
    # ASSUMES: no declared Portal text contains "probes/" or "maintainer-only" (checked against _c's output
    #          before this revision ran: grep found neither in any of the 14 files).
    assert PROBE_WS not in txt and "maintainer-only" not in txt and "probes/" not in txt, \
        f"{source}: rendered file carries an evidence-form string"
    assert ("> Caveat: entries marked **Observed on pinned mirror**" in txt) == (obs_marks_expected[source] > 0), \
        f"{source}: third caveat presence does not match override presence"
print("VALIDATION: observed-mark counts match overrides; no research path or evidence string rendered; third caveat only where notes appear.")
print("\n--- OVERRIDES APPLIED PER SOURCE (variable-level, family-level) ---")
for source in EXPECTED_SOURCES:
    nv = sum(n for k, n in var_hits.items() if k[0] == source)
    nf = sum(n for k, n in fam_hits.items() if k[0] == source)
    if nv or nf:
        print(f"  {source:10s}: {nv} variable-level, {nf} family-level")

# --- Summary ---
print("\n--- PER-FILE SUMMARY (source: unique_vars, families, md_lines) ---")
for source in EXPECTED_SOURCES:
    nfam = rendered.filter(pl.col("source") == source)["family_key"].n_unique()
    nvar = rendered.filter(pl.col("source") == source).height
    print(f"  {source:10s}: {nvar:4d} vars | {nfam:2d} families | {line_counts[source]:4d} lines")
print(f"\nDedupe accounting: {ROWS_IN} varlist rows in -> {ROWS_OUT} unique variable x family out")
print(f"Output dir: {OUT_DIR}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-10-28 02:39:36
# Command: python3 /daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries_d.py
# Duration: 0s
# Exit code: 0
# Capture: COMPLETE
#
# --- STDOUT ---
# Overrides loaded: 23 variable-level, 4 family-level; probed revision 0ad00ce0e232c96b0642459e4e7326607a8d26aa
# Loaded bridge: (945, 13), var inventory: (2994, 13)
# Families: 85 (all cite >=1 mirror-validated canonical key)
# DEDUPE: varlist rows in 2994 -> unique (family,variable) out 2235
# VALIDATION: all 2994 varlist rows represented in exactly one family section.
# VALIDATION: 14 files written, all non-empty.
# VALIDATION: all 23 variable-level and 4 family-level overrides matched exactly once.
# VALIDATION: observed-mark counts match overrides; no research path or evidence string rendered; third caveat only where notes appear.
# 
# --- OVERRIDES APPLIED PER SOURCE (variable-level, family-level) ---
#   csafety   : 1 variable-level, 0 family-level
#   eada      : 1 variable-level, 0 family-level
#   ipeds     : 1 variable-level, 2 family-level
#   nhgis     : 8 variable-level, 2 family-level
#   pseo      : 2 variable-level, 0 family-level
#   saipe     : 10 variable-level, 0 family-level
# 
# --- PER-FILE SUMMARY (source: unique_vars, families, md_lines) ---
#   ccd       :  300 vars |  5 families |  354 lines
#   crdc      :  397 vars | 24 families |  603 lines
#   csafety   :   13 vars |  1 families |   37 lines
#   eada      :  165 vars |  1 families |  189 lines
#   edfacts   :   82 vars |  4 families |  128 lines
#   fsa       :   63 vars |  5 families |  117 lines
#   ipeds     :  753 vars | 32 families | 1025 lines
#   meps      :   11 vars |  1 families |   33 lines
#   nacubo    :    7 vars |  1 families |   29 lines
#   nccs      :  161 vars |  1 families |  183 lines
#   nhgis     :   87 vars |  2 families |  121 lines
#   pseo      :   18 vars |  1 families |   42 lines
#   saipe     :   10 vars |  1 families |   34 lines
#   scorecard :  168 vars |  6 families |  230 lines
# 
# Dedupe accounting: 2994 varlist rows in -> 2235 unique variable x family out
# Output dir: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-10-28_dictionary-regeneration-overrides/generated
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
