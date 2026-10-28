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
OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-10-28_dictionary-regeneration-overrides/generated")
OUT_DIR.mkdir(parents=True, exist_ok=True)

HF_REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
GEN_DATE = date.today().isoformat()
# INTENT (_b): the generated headers name the script that produced them, so SELF is this revision.
SELF = "/daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries_b.py"

EXPECTED_SOURCES = ["ccd", "crdc", "csafety", "eada", "edfacts", "fsa", "ipeds",
                    "meps", "nacubo", "nccs", "nhgis", "pseo", "saipe", "scorecard"]

# --- Overrides ---
# INTENT: Declared-vs-observed override table. Each entry adds, beside the Portal varlist's
#         declared label/type/legend (kept verbatim), what file-first probes of the pinned mirror
#         (revision 0ad00ce0, all probes run 2026-10-27) actually found where it contradicts the
#         declared side. Variable-level entries are keyed (source, family_key, variable);
#         family-level entries are keyed (source, family_key).
# REASONING: The dictionaries are generated, so hand-editing them would be lost at the next run;
#            the generator is the single place to record observed facts. Keeping the declared
#            legend verbatim and appending the observation preserves declared-vs-observed
#            transparency instead of silently replacing Portal metadata.
# ASSUMES: Each override's `expect_*` fields describe the declared side as the 2026-08-07 varlist
#          and 2026-08-08 bridge render it; the Validate section fails loudly if a key matches no
#          row (stale key) or the declared side has drifted (stale override).
# Evidence strings cite probe logs in a research workspace — maintainer-only, not shipped. The
# RENDERED text never cites research/ paths (asserted in Validate).
PROBE_WS = "maintainer-only, not shipped: /daaf/research/2026-09-18_AdHoc_Typesafe_Classifier_Experiments/probes/"
OBS_LABEL = "**Observed on pinned mirror (rev `0ad00ce0`, probe 2026-10-27):**"

VAR_OVERRIDES = [
    # 1 — NHGIS colleges geocode_accuracy: codebook 1-4 labels not observed; a match score instead.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "geocode_accuracy",
     "expect_type": "integer", "expect_values_contains": '"4" : "Did not geocode"', "expect_values_lacks": None,
     "obs_type": None,
     "note": "values are a geocoder match score from 61 to 100, plus -2, in all 4 census-vintage files; "
             "codes 1, 2, 3 and 4 never occur. Every row is -2 in data years 2018-2023, and no earlier row is -2.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log, each colleges file: 'geocode_accuracy min -2, max 100, "
                 "nulls 0, distinct 32, rows with value in codebook set [1, 2, 3, 4, -2]: 38564', bucket '<0 ┆ 38564', "
                 "'negative geocode_accuracy values present: [-2]'; 2026-10-27_mD_nhgis_probe_a.py log, each colleges "
                 "file: 'smallest non-negative geocode_accuracy: 61; distinct non-negative values: 31' and -2 rows by "
                 "year listing only '2018 ┆ 6857 ┆ 6857 ┆ 1.0' through '2023 ┆ 6163 ┆ 6163 ┆ 1.0'"},
    # 2 — NHGIS schools geocode_accuracy: Float64; 4 in 2 rows only; -2 for every row 2017-2023.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}", "variable": "geocode_accuracy",
     "expect_type": "integer", "expect_values_contains": '"4" : "Did not geocode"', "expect_values_lacks": None,
     "obs_type": "float (Float64; all values integral)",
     "note": "values are a geocoder match score up to 100, plus -2, with 805 nulls per file; codes 1, 2 and 3 never "
             "occur and 4 occurs in 2 rows. Every row is -2 in data years 2017-2023, and no earlier row is -2 "
             "(year pattern tested in the 1990 and 2010 files).",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log, each schools file: 'dtypes: geocode_accuracy=Float64', "
                 "'min -2.0, max 100.0, nulls 805, distinct 35, rows with value in codebook set [1, 2, 3, 4, -2]: "
                 "714537, non-integer values: 0', buckets '0-4 ┆ 2' and '<0 ┆ 714535'; "
                 "2026-10-27_mD_nhgis_probe_a.py log, schools 1990 and 2010: 'smallest non-negative geocode_accuracy: "
                 "4.0' and -2 rows by year listing only '2017 ┆ 102337 ┆ 102337 ┆ 1.0' through '2023 ┆ 102274 ┆ 102274 ┆ 1.0'"},
    # 3 — NHGIS colleges geoid_block: Int64 (declared string); never a 15-digit block id.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "geoid_block",
     "expect_type": "string", "expect_values_contains": None, "expect_values_lacks": None,
     "obs_type": "integer (Int64 in all 4 files)",
     "note": "never a 15-digit block GEOID. In the 2010 and 2020 census-vintage files it equals the 12-digit "
             "block-group GEOID rebuilt from the file's own columns (Int64, so the leading zero drops when the "
             "state FIPS is below 10; zero-pad to 12). In the 1990 file it equals the 11-digit tract GEOID. "
             "In the 2000 file it matches neither form.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log: 'geoid_block=Int64' in all 8 files, lengths [10, 11] "
                 "(1990/2000) and [11, 12] (2010/2020); 2026-10-27_mD_nhgis_probe_a.py log: colleges 1990 "
                 "'geoid_block == tract GEOID (11-digit form): 331055; == block-group GEOID (12-digit form): 0', "
                 "colleges 2000 '...: 0; ...: 0', colleges 2010 '...: 0; ...: 337155', colleges 2020 '...: 0; ...: 337203'"},
    # 4 — NHGIS schools geoid_block: same finding; 2020 and 2000 from probe D2.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}", "variable": "geoid_block",
     "expect_type": "string", "expect_values_contains": None, "expect_values_lacks": None,
     "obs_type": "integer (Int64 in all 4 files)",
     "note": "never a 15-digit block GEOID. In the 2010 file it equals the 12-digit block-group GEOID rebuilt from "
             "the file's own columns (Int64, so the leading zero drops when the state FIPS is below 10; zero-pad "
             "to 12); the 2020 file has the same 11-12-digit lengths and state+county prefix. In the 1990 file it "
             "equals the 11-digit tract GEOID. In the 2000 file its leading digits do not carry the state FIPS.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe_a.py log: schools 1990 'geoid_block == tract GEOID (11-digit "
                 "form): 3627493; == block-group GEOID (12-digit form): 0', schools 2010 '...: 0; ...: 3674498'; "
                 "2026-10-27_mD_nhgis_probe.py log: schools 2020 lengths '11 ┆ 651648', '12 ┆ 3023920'; "
                 "2026-10-27_mD2_nhgis_fips_probe_a.py log: schools 2020 'leading 5 digits == county_fips_geo: "
                 "3675568', schools 2000 'geoid_block leading digits (divisor 10000000000) == fips: 7 of 3624536'"},
    # 5a — NHGIS colleges state_fips_geo: 1990 file stores state FIPS x 10.
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}", "variable": "state_fips_geo",
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
     "expect_type": "integer", "expect_values_contains": None, "expect_values_lacks": None,
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
     "expect_type": "integer", "expect_values_contains": None, "expect_values_lacks": None,
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
     "expect_type": "integer", "expect_values_contains": None, "expect_values_lacks": None,
     "obs_type": None,
     "note": "stored as Int64, so CIP series 01-09 lose their leading zero (CIP 03.0101 is 30101); zero-pad to 6 "
             "digits before matching NCES CIP code strings (2023 file probed).",
     "evidence": PROBE_WS + "2026-10-27_mB_ipeds-completions_probe.py log line 148 '--- 6-digit shard 2023: "
                 "cipcode_6digit dtype Int64', line 149 'UC Berkeley 6-digit codes ... [99, 30101, 30103, ...]'"},
    # 11 — PSEO opeid: String in 2001-2018 shards, Int64 in 2019-2021.
    {"source": "pseo", "family_key": "pseo/colleges_pseo_{year}", "variable": "opeid",
     "expect_type": "string", "expect_values_contains": None, "expect_values_lacks": None,
     "obs_type": "string (2001-2018 files) / integer (Int64, 2019-2021 files)",
     "note": "the Int64 files drop the leading zeros (365800 where the 2018 file has \"00365800\"), so cast to "
             "string and zero-pad to 8 before concatenating years or joining.",
     "evidence": PROBE_WS + "2026-10-27_mA_pseo_probe_a.py log: 'String-opeid shards: [2001, ..., 2018]', "
                 "'Int64-opeid shards: [2019, 2020, 2021]', 2018 '00365800 ┆ 228778', 2019 '365800 ┆ 228778'"},
    # 12 — PSEO cipcode: bare 2-digit codes, not the 6-digit-style legend values.
    {"source": "pseo", "family_key": "pseo/colleges_pseo_{year}", "variable": "cipcode",
     "expect_type": "integer", "expect_values_contains": '"110000" : "Computer and information sciences', "expect_values_lacks": None,
     "obs_type": None,
     "note": "the file holds bare 2-digit CIP codes (e.g. 11, 14, 52) and 99, not the 6-digit-style values this "
             "legend lists: in the 2018 file cipcode == 11 matches 150,390 rows and cipcode == 110000 matches 0 "
             "(2021 file: 34,020 and 0).",
     "evidence": PROBE_WS + "2026-10-27_mA2_pseo_cipcode_probe.py log lines 143-149: 'shard 2018 ... cipcode dtype "
                 "Int64', 'distinct cipcode values (45): [1, 3, 4, ..., 52, 54, 99]', 'cipcode == 11: 150390 rows', "
                 "'cipcode == 110000: 0 rows'; lines 182-188: shard 2021 'cipcode == 11: 34020 rows', "
                 "'cipcode == 110000: 0 rows'"},
    # 13 — EADA ath_classification_code: code 11 occurs but is missing from the Portal legend.
    {"source": "eada", "family_key": "eada/colleges_eada_inst_characteristics", "variable": "ath_classification_code",
     "expect_type": "integer", "expect_values_contains": '"12" : " NJCAA Division I"', "expect_values_lacks": '"11" :',
     "obs_type": None,
     "note": "code \"11\" occurs although this legend omits it: 37 rows in 2002-2014, none from 2015; the rows from "
             "2004 on carry ath_classification_name \"NAIA Division III\".",
     "evidence": PROBE_WS + "2026-10-27_mE_eada_probe.py log line 99 '11 ┆ 37 ┆ 2002 ┆ 2014 ┆ [\"NAIA Division "
                 "III\"]', line 110 'code 11 rows: 37; years with code 11: [2002, ..., 2014]', line 168 "
                 "'11 ┆ NAIA Division III ┆ 24 ┆ 2004 ┆ 2014'"},
    # 14 — Campus Safety bias: no sentinel occurs; nulls instead.
    {"source": "csafety", "family_key": "csafety/colleges_csafety_hate_crimes", "variable": "bias",
     "expect_type": "integer", "expect_values_contains": '"-3" : "Suppressed data"', "expect_values_lacks": None,
     "obs_type": None,
     "note": "no -1, -2 or -3 value occurs; the non-null values are 1-9 and 99, and 352,310 rows are null.",
     "evidence": PROBE_WS + "2026-10-27_mC_campus-safety_probe_b.py log line 290 'distinct bias (non-null): [1, 2, 3, "
                 "4, 5, 6, 7, 8, 9, 99]; null bias rows: 352310'"},
]

FAM_OVERRIDES = [
    # 8 — IPEDS completions 2-digit: bridge counted 32 files; the pinned tree has 33 (2023 added in the v2 build).
    {"source": "ipeds", "family_key": "ipeds/colleges_ipeds_completions-2digcip_{year}",
     "expect_bridge_files": 32, "obs_files": 33, "obs_years": "1991-2023", "bullet": None,
     "evidence": PROBE_WS + "2026-10-27_mB_ipeds-completions_probe.py log line 112 '2-digit shards: 33, years [1991, "
                 "..., 2023]'"},
    # 9 — IPEDS completions 6-digit: bridge counted 40; pinned tree has 41.
    {"source": "ipeds", "family_key": "ipeds/colleges_ipeds_completions-6digcip_{year}",
     "expect_bridge_files": 40, "obs_files": 41, "obs_years": "1983-2023", "bullet": None,
     "evidence": PROBE_WS + "2026-10-27_mB_ipeds-completions_probe.py log line 113 '6-digit shards: 41, years 1983-2023'"},
    # 7a — NHGIS colleges: {year} in the path is the census-geography vintage. Heading NOT renamed
    #      (explorer colleges-datasets.md cites the § `nhgis/colleges_nhgis_geog_{year}` heading).
    {"source": "nhgis", "family_key": "nhgis/colleges_nhgis_geog_{year}",
     "expect_bridge_files": 4, "obs_files": None, "obs_years": None,
     "bullet": "here `{year}` is the census-geography vintage (`1990`, `2000`, `2010`, `2020`), not a data year. "
               "Each of the 4 files holds every data year: 1980 and 1984-2023 (1981-1983 absent), 337,222 rows per file.",
     "evidence": PROBE_WS + "2026-10-27_mD_nhgis_probe.py log: 'NHGIS parquet files at pinned revision (8): "
                 "[...colleges_nhgis_geog_1990 ... _2020 ...]', each colleges file 'rows 337222' and 'years: "
                 "1980-2023 (41 distinct); gaps inside range: [1981, 1982, 1983]'"},
    # 7b — NHGIS schools: same; heading cited by explorer schools-datasets.md.
    {"source": "nhgis", "family_key": "nhgis/schools_nhgis_geog_{year}",
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
var_hits = {k: 0 for k in VAR_OV}
fam_hits = {k: 0 for k in FAM_OV}
print(f"Overrides loaded: {len(VAR_OV)} variable-level, {len(FAM_OV)} family-level")

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
    n_src_overrides = sum(1 for k in VAR_OV if k[0] == source) + sum(1 for k in FAM_OV if k[0] == source)
    obs_marks_expected[source] = n_src_overrides

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
    lines.append(f"> Caveat: the `coded values` column reproduces the Portal varlist's declared "
                 f"legend (including the standard `-1`/`-2`/`-3` missing codes) and does not "
                 f"assert those codes occur in the pinned mirror file — several mirror files "
                 f"carry nulls instead (the SAIPE probe on 2026-09-15 found zero sentinel values "
                 f"and nulls for all missing). Test for nulls and for sentinels before treating "
                 f"either as the missing-value convention, and defer to the source skill's "
                 f"SKILL.md where it documents the observed convention.")
    lines.append("")
    # INTENT (_b): third standing caveat, explaining the observed notes, in files that carry them.
    if n_src_overrides > 0:
        lines.append(f"> Caveat: entries marked **Observed on pinned mirror** record what file-first "
                     f"probes of the pinned revision found on 2026-10-27 where it contradicts the "
                     f"Portal varlist; they are added beside the declared label, type and legend, "
                     f"which are kept verbatim, and override nothing declared.")
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
            lines.append(f"- **Canonical mirror path:** `{fam}.parquet` "
                         f"({fov['obs_files']} mirror files, {fov['obs_years']}; "
                         f"**observed on pinned mirror (rev `0ad00ce0`, probe 2026-10-27)**)")
        else:
            lines.append(f"- **Canonical mirror path:** `{fam}.parquet` "
                         f"({nfiles} mirror file{'s' if nfiles != 1 else ''})")
        route_cites = ", ".join(f"`{esc(r)}`" for r in routes)
        lines.append(f"- **Contributing endpoint route(s):** {route_cites}")
        if fov is not None and fov["bullet"] is not None:
            # INTENT (_b): extra family bullet (heading left unchanged so explorer § links still resolve).
            lines.append(f"- {OBS_LABEL} {fov['bullet']}")
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
                obs = f"{OBS_LABEL} {esc(vov['note'])}"
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
    assert "research/" not in txt, f"{source}: rendered file cites a research/ path"
    assert ("> Caveat: entries marked **Observed on pinned mirror**" in txt) == (obs_marks_expected[source] > 0), \
        f"{source}: third caveat presence does not match override presence"
print("VALIDATION: observed-mark counts match overrides; no rendered file cites research/; third caveat only where notes appear.")
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
# Executed: 2026-10-28 02:18:17
# Command: python3 /daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries_b.py
# Duration: 1s
# Exit code: 1
# Capture: COMPLETE
#
# --- STDOUT ---
# Overrides loaded: 13 variable-level, 4 family-level
# Loaded bridge: (945, 13), var inventory: (2994, 13)
# Families: 85 (all cite >=1 mirror-validated canonical key)
# DEDUPE: varlist rows in 2994 -> unique (family,variable) out 2235
# VALIDATION: all 2994 varlist rows represented in exactly one family section.
# VALIDATION: 14 files written, all non-empty.
# VALIDATION: all 13 variable-level and 4 family-level overrides matched exactly once.
# Traceback (most recent call last):
#   File "/daaf/scripts/mirror_maintenance/54_generate-variable-dictionaries_b.py", line 464, in <module>
#     assert "research/" not in txt, f"{source}: rendered file cites a research/ path"
#            ^^^^^^^^^^^^^^^^^^^^^^
# AssertionError: ipeds: rendered file cites a research/ path
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
