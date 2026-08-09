# --- Config ---
# INTENT: Exhaustively audit every DATA-testable claim in the
#   education-data-source-campus-safety skill (SKILL.md + references/variable-definitions.md
#   + references/hate-crimes.md) against the LIVE pinned mirror parquet for csafety.
#   This is Unit 1 of the doc-audit gap-fill (the K-12 audit left campus-safety unaudited).
# REASONING: Adversarial (docs guilty until data confirms). Schema projection +
#   .unique()/null_count/range aggregates over HTTP via pl.scan_parquet. Column
#   projection only; no full download. Mirrors method of scripts 24-27.
# ASSUMES: pinned public repo reachable; csafety single-file dataset
#   csafety/colleges_csafety_hate_crimes.parquet (datasets-reference.md line 285).
# Skill claims under test (file:line):
#   SKILL.md: unitid 6-digit int (47,183); year 2005-2021 (46); crime_type 1-18 no 99 (142);
#     bias 1-9,99 (144-157); missing null-only no -1/-2/-3, ~352k bias nulls (216-219);
#     inst_name not instnm, branch/address/city/zip/state/sector/enrollment absent (188).
#   variable-definitions.md: unitid Int64 (50); opeid String 126 nulls (51); inst_name String (52);
#     fips Int64 59 unique (53); count cols on_campus/residence_hall/non_campus/public_property/
#     other/total_hate_crimes (123); crime_type 1-18 only no 99 (197); bias 1-9,99+null (154-168);
#     no -1/-2/-3 codes, 352,310 bias nulls (256); year Int64 2005-2021, survey_year absent (244-247);
#     primary-offense/fire count cols NOT in mirror (84,210).
#   hate-crimes.md: NOTE line 234 says crime_type "(1-18, 99)" — INTERNAL DOC CONFLICT with
#     var-defs 197/SKILL 142 (no 99). Data resolves it.
import polars as pl
from collections import Counter

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"
REL = "csafety/colleges_csafety_hate_crimes"

def scan():
    return pl.scan_parquet(f"{BASE}/{REL}.parquet")

results = []
def rec(claim, obs, verdict):
    results.append((claim, obs, verdict)); print(f"[{verdict}] {claim} -> {obs}")

# --- Load (schema only first) ---
sc = dict(scan().collect_schema())
cols = list(sc)
print(f"csafety schema ({len(sc)} cols): {sc}\n")

# --- Validate: identifiers ---
# CLAIM 1: unitid Int64 (var-defs 50, SKILL 183)
rec("csafety unitid is Int64 (var-defs 50)", f"dtype={sc.get('unitid')}",
    "VERIFIED" if "Int64" in str(sc.get("unitid")) else "CONTRADICTED")
# CLAIM 2: opeid String (var-defs 51, SKILL 184)
rec("csafety opeid is String (var-defs 51)", f"dtype={sc.get('opeid')}",
    "VERIFIED" if "String" in str(sc.get("opeid")) else "CONTRADICTED")
# CLAIM 3: opeid ~126 null values (var-defs 51, SKILL 184)
try:
    opn = scan().select(pl.col("opeid").null_count()).collect().item()
    rec("csafety opeid null count ~126 (var-defs 51)", f"nulls={opn}",
        "VERIFIED" if opn == 126 else ("PRESENT-NOT-DOCUMENTED" if opn is not None else "UNTESTABLE"))
except Exception as e:
    rec("csafety opeid nulls", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")
# CLAIM 4: inst_name present as String; instnm NOT a column (var-defs 52,55; SKILL 188,320)
rec("csafety uses inst_name (String), NOT instnm (var-defs 52, SKILL 320)",
    f"inst_name={sc.get('inst_name')}; instnm_present={'instnm' in cols}",
    "VERIFIED" if ("String" in str(sc.get("inst_name")) and "instnm" not in cols) else "CONTRADICTED")
# CLAIM 5: fips Int64 (var-defs 53, SKILL 186)
rec("csafety fips is Int64 (var-defs 53)", f"dtype={sc.get('fips')}",
    "VERIFIED" if "Int64" in str(sc.get("fips")) else "CONTRADICTED")
# CLAIM 6: fips 59 unique values (var-defs 53)
try:
    fipsn = scan().select(pl.col("fips").n_unique()).collect().item()
    rec("csafety fips 59 unique values (var-defs 53)", f"n_unique={fipsn}",
        "VERIFIED" if fipsn == 59 else "PRESENT-NOT-DOCUMENTED")
except Exception as e:
    rec("csafety fips n_unique", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

# --- Validate: year ---
# CLAIM 7: year Int64 (var-defs 244)
rec("csafety year is Int64 (var-defs 244)", f"dtype={sc.get('year')}",
    "VERIFIED" if "Int64" in str(sc.get("year")) else "CONTRADICTED")
# CLAIM 8: year coverage 2005-2021 (SKILL 46, var-defs 247)
try:
    yr = scan().select(pl.col("year").min().alias("mn"), pl.col("year").max().alias("mx")).collect().to_dicts()[0]
    rec("csafety year coverage 2005-2021 (SKILL 46)", f"[{yr['mn']}, {yr['mx']}]",
        "VERIFIED" if yr["mn"] == 2005 and yr["mx"] == 2021 else "PRESENT-NOT-DOCUMENTED")
except Exception as e:
    rec("csafety year coverage", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

# --- Validate: coded values ---
# CLAIM 9: crime_type present, values subset {1..18}, 99 ABSENT (var-defs 197, SKILL 142;
#   resolves internal conflict vs hate-crimes.md 234 which claims 99 present)
if "crime_type" in cols:
    ct = scan().select("crime_type").unique().collect()["crime_type"].to_list()
    cts = set(x for x in ct if x is not None); has_null_ct = None in ct
    extra = cts - set(range(1, 19))
    rec("csafety crime_type in 1-18 only, 99 ABSENT (var-defs 197 vs hate-crimes.md 234)",
        f"present={sorted(cts)}; 99_present={99 in cts}; null_present={has_null_ct}; out-of-1-18={sorted(extra)}",
        "VERIFIED" if (99 not in cts and not extra) else "CONTRADICTED")
else:
    rec("csafety crime_type column exists", f"cols={cols}", "CONTRADICTED")
# CLAIM 10: bias values subset {1..9,99}; null present (var-defs 154-168, SKILL 144-157)
if "bias" in cols:
    bv = scan().select("bias").unique().collect()["bias"].to_list()
    bvs = set(x for x in bv if x is not None); has_null_b = None in bv
    doc_bias = set(range(1, 10)) | {99}
    rec("csafety bias in {1-9,99}+null (var-defs 154-168)",
        f"present={sorted(bvs)}; null_present={has_null_b}; not-documented={sorted(bvs-doc_bias)}",
        "VERIFIED" if (not (bvs - doc_bias) and has_null_b) else "PRESENT-NOT-DOCUMENTED")
else:
    rec("csafety bias column exists", f"cols={cols}", "CONTRADICTED")
# CLAIM 11: bias null count ~352,310 (var-defs 256, SKILL 216)
try:
    bn = scan().select(pl.col("bias").null_count()).collect().item()
    rec("csafety bias null count ~352,310 (var-defs 256)", f"nulls={bn}",
        "VERIFIED" if bn == 352310 else "PRESENT-NOT-DOCUMENTED")
except Exception as e:
    rec("csafety bias nulls", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")
# CLAIM 12: NO -1/-2/-3 negative codes in any numeric column; missing = null (var-defs 256, SKILL 219)
try:
    negcols = []
    for c, d in sc.items():
        if "Int" in str(d) or "Float" in str(d):
            n = scan().select(pl.col(c)).filter(pl.col(c) < 0).select(pl.len()).collect().item()
            if n and n > 0:
                negcols.append((c, n))
    rec("csafety no negative missing-codes (-1/-2/-3) in any numeric col (var-defs 256)",
        f"cols-with-neg={negcols}", "VERIFIED" if not negcols else "CONTRADICTED")
except Exception as e:
    rec("csafety neg-code scan", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

# --- Validate: geographic count columns present ---
# CLAIM 13: hate-crime count cols present (var-defs 123, hate-crimes.md 236-241)
count_cols = ["on_campus_hate_crimes", "residence_hall_hate_crimes", "non_campus_hate_crimes",
              "public_property_hate_crimes", "other_hate_crimes", "total_hate_crimes"]
present_cc = [c for c in count_cols if c in cols]
rec("csafety geographic hate-crime count cols present (var-defs 123)",
    f"present={present_cc}; missing={[c for c in count_cols if c not in cols]}",
    "VERIFIED" if len(present_cc) == len(count_cols) else "CONTRADICTED")

# --- Validate: absent full-CSS columns (hate-crimes-only scope) ---
# CLAIM 14: full-CSS institutional cols NOT in mirror (var-defs 55, SKILL 188)
absent_expected = ["branch", "address", "city", "zip", "state", "sector", "control",
                   "enrollment", "fte_enrollment", "housing", "campus_id", "main_campus", "survey_year"]
still_present = [c for c in absent_expected if c in cols]
rec("csafety full-CSS institutional/time cols absent (var-defs 55, SKILL 188, var-defs 247)",
    f"unexpectedly-present={still_present}", "VERIFIED" if not still_present else "CONTRADICTED")
# CLAIM 15: hate-crimes-ONLY scope — primary-offense & fire count cols NOT in mirror
#   (var-defs 84 crime stats, 210 fire; SKILL 49 "hate crimes only")
non_hate_cols = ["murder", "rape", "robbery", "aggravated_assault", "burglary", "arson",
                 "fires_total", "fire_injuries", "fire_deaths", "drug_arrests",
                 "liquor_arrests", "weapons_arrests", "domestic_violence", "stalking"]
leaked = [c for c in non_hate_cols if c in cols]
rec("csafety scope is hate-crimes-only — no primary-offense/VAWA/arrest/fire cols (SKILL 49, var-defs 84/210)",
    f"leaked-non-hate-cols={leaked}", "VERIFIED" if not leaked else "CONTRADICTED")

print("\n### CLAIM INVENTORY = 15 DATA-testable claims enumerated & tested ###")
print("### TALLY ###")
for k, v in Counter(v for _, _, v in results).items():
    print(f"  {k}: {v}")
print("DONE 32")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:19:49
# Command: python3 /daaf/scripts/mirror_maintenance/32_csafety-doc-audit.py
# Duration: 21s
# Exit code: 0
#
# --- STDOUT ---
# csafety schema (13 cols): {'year': Int64, 'unitid': Int64, 'inst_name': String, 'opeid': String, 'fips': Int64, 'crime_type': Int64, 'residence_hall_hate_crimes': Int64, 'bias': Int64, 'other_hate_crimes': Int64, 'on_campus_hate_crimes': Int64, 'non_campus_hate_crimes': Int64, 'public_property_hate_crimes': Int64, 'total_hate_crimes': Int64}
# 
# [VERIFIED] csafety unitid is Int64 (var-defs 50) -> dtype=Int64
# [VERIFIED] csafety opeid is String (var-defs 51) -> dtype=String
# [VERIFIED] csafety opeid null count ~126 (var-defs 51) -> nulls=126
# [VERIFIED] csafety uses inst_name (String), NOT instnm (var-defs 52, SKILL 320) -> inst_name=String; instnm_present=False
# [VERIFIED] csafety fips is Int64 (var-defs 53) -> dtype=Int64
# [VERIFIED] csafety fips 59 unique values (var-defs 53) -> n_unique=59
# [VERIFIED] csafety year is Int64 (var-defs 244) -> dtype=Int64
# [VERIFIED] csafety year coverage 2005-2021 (SKILL 46) -> [2005, 2021]
# [VERIFIED] csafety crime_type in 1-18 only, 99 ABSENT (var-defs 197 vs hate-crimes.md 234) -> present=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]; 99_present=False; null_present=False; out-of-1-18=[]
# [VERIFIED] csafety bias in {1-9,99}+null (var-defs 154-168) -> present=[1, 2, 3, 4, 5, 6, 7, 8, 9, 99]; null_present=True; not-documented=[]
# [VERIFIED] csafety bias null count ~352,310 (var-defs 256) -> nulls=352310
# [VERIFIED] csafety no negative missing-codes (-1/-2/-3) in any numeric col (var-defs 256) -> cols-with-neg=[]
# [VERIFIED] csafety geographic hate-crime count cols present (var-defs 123) -> present=['on_campus_hate_crimes', 'residence_hall_hate_crimes', 'non_campus_hate_crimes', 'public_property_hate_crimes', 'other_hate_crimes', 'total_hate_crimes']; missing=[]
# [VERIFIED] csafety full-CSS institutional/time cols absent (var-defs 55, SKILL 188, var-defs 247) -> unexpectedly-present=[]
# [VERIFIED] csafety scope is hate-crimes-only — no primary-offense/VAWA/arrest/fire cols (SKILL 49, var-defs 84/210) -> leaked-non-hate-cols=[]
# 
# ### CLAIM INVENTORY = 15 DATA-testable claims enumerated & tested ###
# ### TALLY ###
#   VERIFIED: 15
# DONE 32
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
