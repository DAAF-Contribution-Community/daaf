# --- Config ---
# INTENT: Verify DATA-testable claims for education-data-source-meps, -saipe, and
#   -edfacts against the LIVE pinned mirror. Includes the task-required -2/-3
#   missing-code test on edfacts assessment (suppression-bearing) data.
# REASONING: Adversarial re-proof of MEPS/SAIPE schemas, value ranges, null-vs-coded
#   missing semantics, SAIPE 0-1 proportion scale trap, edfacts id dtypes, coded
#   values (grade_edfacts, race code 6 absence), column counts, suppression codes.
# ASSUMES: pinned public repo; concise verdict-only output to conserve context.
# Skills under test: meps/references/variable-definitions.md (schema 296-308, ranges
#   53-57, nulls 121-136); saipe/references/variable-definitions.md (schema 388-399,
#   scale-trap 403-417, nulls 301); edfacts/SKILL.md (ids 116-122, grade 154-160,
#   race 176, missing 216-223, col-counts 245-248).
import polars as pl
from collections import Counter

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"
def scan(rel): return pl.scan_parquet(f"{BASE}/{rel}.parquet")
def schema(rel): return dict(scan(rel).collect_schema())
def uvals(rel, col):
    v = scan(rel).select(col).unique().collect()[col].to_list()
    return sorted(x for x in v if x is not None), (None in v)

results = []
def rec(claim, obs, verdict):
    results.append((claim, obs, verdict)); print(f"[{verdict}] {claim} -> {obs}")

########## MEPS ##########
print("\n========== MEPS ==========")
meps = "meps/schools_meps"
msc = schema(meps)
print(f"MEPS schema ({len(msc)} cols): {msc}")
# CLAIM: id/categorical cols all Int64; estimate cols Float64 (var-defs 296-308)
exp_meps = {"year":"Int64","fips":"Int64","gleaid":"Int64","ncessch":"Int64",
    "meps_poverty_pct":"Float64","meps_poverty_se":"Float64","meps_mod_poverty_pct":"Float64",
    "meps_poverty_ptl":"Int64","meps_mod_poverty_ptl":"Int64","ncessch_num":"Int64","leaid":"Int64"}
mism = {c:(str(msc.get(c,"ABSENT")),t) for c,t in exp_meps.items() if t not in str(msc.get(c,"ABSENT"))}
rec("MEPS schema dtypes match var-defs 296-308", f"mismatches={mism}", "VERIFIED" if not mism else "CONTRADICTED")
# CLAIM: value ranges (var-defs 53-57, 84)
try:
    agg = scan(meps).select([
        pl.col("meps_poverty_pct").min().alias("pp_min"), pl.col("meps_poverty_pct").max().alias("pp_max"),
        pl.col("meps_mod_poverty_pct").min().alias("mp_min"), pl.col("meps_mod_poverty_pct").max().alias("mp_max"),
        pl.col("meps_poverty_se").min().alias("se_min"), pl.col("meps_poverty_se").max().alias("se_max"),
        pl.col("meps_poverty_ptl").min().alias("ptl_min"), pl.col("meps_poverty_ptl").max().alias("ptl_max"),
        pl.col("year").min().alias("y_min"), pl.col("year").max().alias("y_max"),
    ]).collect().to_dicts()[0]
    rec("MEPS meps_poverty_pct range ~0.0-60.5 (var-defs 53)", f"[{agg['pp_min']}, {agg['pp_max']}]",
        "VERIFIED" if agg['pp_max'] <= 65 and agg['pp_min'] >= 0 else "PRESENT-NOT-DOCUMENTED")
    rec("MEPS meps_mod_poverty_pct range ~0.0-100 (var-defs 54)", f"[{agg['mp_min']}, {agg['mp_max']}]",
        "VERIFIED" if agg['mp_max'] <= 100.5 and agg['mp_min'] >= 0 else "PRESENT-NOT-DOCUMENTED")
    rec("MEPS meps_poverty_se range ~0.52-3.77 (var-defs 84)", f"[{agg['se_min']}, {agg['se_max']}]",
        "VERIFIED" if agg['se_min'] >= 0.4 and agg['se_max'] <= 4.5 else "PRESENT-NOT-DOCUMENTED")
    rec("MEPS meps_poverty_ptl range 1-100 (var-defs 56)", f"[{agg['ptl_min']}, {agg['ptl_max']}]",
        "VERIFIED" if agg['ptl_min'] >= 1 and agg['ptl_max'] <= 100 else "PRESENT-NOT-DOCUMENTED")
    rec("MEPS year coverage 2009-2022 (SKILL desc)", f"[{agg['y_min']}, {agg['y_max']}]",
        "VERIFIED" if agg['y_min'] == 2009 and agg['y_max'] in (2022, 2023) else "PRESENT-NOT-DOCUMENTED")
except Exception as e:
    rec("MEPS ranges", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")
# CLAIM: missing = native null, NO negative codes (var-defs 121-136)
try:
    neg = scan(meps).select(pl.col("meps_poverty_pct")).filter(pl.col("meps_poverty_pct") < 0).select(pl.len()).collect().item()
    nulls = scan(meps).select(pl.col("meps_poverty_pct").null_count()).collect().item()
    rec("MEPS uses native null, no negative codes (var-defs 121)", f"neg-value rows={neg}; nulls={nulls}",
        "VERIFIED" if neg == 0 else "CONTRADICTED")
except Exception as e:
    rec("MEPS null semantics", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

########## SAIPE ##########
print("\n========== SAIPE ==========")
saipe = "saipe/districts_saipe"
ssc = schema(saipe)
print(f"SAIPE schema ({len(ssc)} cols): {ssc}")
exp_saipe = {"est_population_total":"Int","est_population_5_17":"Int","est_population_5_17_poverty":"Int",
    "est_population_5_17_poverty_pct":"Float","leaid":"Int64","fips":"Int64","year":"Int64",
    "district_id":"Int","district_name":"String"}
mism = {c:str(ssc.get(c,"ABSENT")) for c,t in exp_saipe.items() if t not in str(ssc.get(c,"ABSENT"))}
rec("SAIPE schema cols/dtypes match var-defs 388-399", f"mismatches={mism}", "VERIFIED" if not mism else "PRESENT-NOT-DOCUMENTED")
# CLAIM: est_population_5_17_poverty_pct is 0-1 PROPORTION not 0-100 (var-defs 403)
try:
    pmax = scan(saipe).select(pl.col("est_population_5_17_poverty_pct").max()).collect().item()
    pmin = scan(saipe).select(pl.col("est_population_5_17_poverty_pct").min()).collect().item()
    rec("SAIPE est_population_5_17_poverty_pct is 0-1 proportion (var-defs 403 SCALE TRAP)",
        f"range=[{pmin}, {pmax}]", "VERIFIED" if pmax is not None and pmax <= 1.5 else "CONTRADICTED")
except Exception as e:
    rec("SAIPE scale trap", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")
# CLAIM: leaid Int64 (var-defs 227, 395); missing=null no neg codes (var-defs 301)
rec("SAIPE leaid is Int64 (var-defs 227)", f"dtype={ssc.get('leaid')}", "VERIFIED" if "Int64" in str(ssc.get("leaid")) else "CONTRADICTED")
try:
    negcols = []
    for c, d in ssc.items():
        if "Int" in str(d) or "Float" in str(d):
            n = scan(saipe).select(pl.col(c)).filter(pl.col(c) < 0).select(pl.len()).collect().item()
            if n > 0: negcols.append((c, n))
    rec("SAIPE no negative coded values in any numeric col (var-defs 301)", f"cols-with-neg={negcols}",
        "VERIFIED" if not negcols else "PRESENT-NOT-DOCUMENTED")
except Exception as e:
    rec("SAIPE neg-code scan", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

########## EDFACTS ##########
print("\n========== EDFACTS ==========")
sa = "edfacts/schools_edfacts_assessments_2020"
sg = "edfacts/schools_edfacts_grad_rates_2018"
da = "edfacts/districts_edfacts_assessments_2020"
dg = "edfacts/districts_edfacts_grad_rates_2018"
sasc = schema(sa); sgsc = schema(sg); dasc = schema(da); dgsc = schema(dg)
print(f"school_assessments_2020 ({len(sasc)} cols): {list(sasc)}")
print(f"school_grad_rates_2018 ({len(sgsc)} cols): {list(sgsc)}")
# CLAIM: id dtypes all Int64 (SKILL 116-122)
for c in ["ncessch","ncessch_num","leaid","fips"]:
    if c in sasc:
        rec(f"EDFacts assessments.{c} Int64 (SKILL118-122)", f"dtype={sasc.get(c)}",
            "VERIFIED" if "Int64" in str(sasc.get(c)) else "CONTRADICTED")
# CLAIM: column counts 26/18/23/15 (SKILL 245-248)
for name, sc, exp in [("school_assessments",sasc,26),("school_grad_rates",sgsc,18),
                      ("district_assessments",dasc,23),("district_grad_rates",dgsc,15)]:
    rec(f"EDFacts {name} has {exp} cols (SKILL 245-248)", f"observed={len(sc)}",
        "VERIFIED" if len(sc)==exp else "CONTRADICTED")
# CLAIM: grad rates do NOT have sex/migrant/military_connected (SKILL 134)
absent = [c for c in ["sex","migrant","military_connected"] if c not in sgsc]
rec("EDFacts grad_rates lacks sex/migrant/military_connected (SKILL134)",
    f"absent={absent}", "VERIFIED" if len(absent)==3 else "CONTRADICTED")
# CLAIM: grade_edfacts codes 3-8,9,99 (SKILL 154-160)
if "grade_edfacts" in sasc:
    present, hn = uvals(sa, "grade_edfacts"); ps = set(present)
    claim = {3,4,5,6,7,8,9,99}
    rec("EDFacts grade_edfacts codes 3-8,9,99 (SKILL154-160)",
        f"present={sorted(ps)}; present-not-doc={sorted(ps-claim)}",
        "PRESENT-NOT-DOCUMENTED" if ps-claim else "VERIFIED")
else:
    rec("EDFacts grade_edfacts exists", "ABSENT", "CONTRADICTED")
# CLAIM: race code 6 NOT observed; 8,9,20,-1,-2,-3 not observed in race (SKILL 176)
if "race" in sasc:
    present, hn = uvals(sa, "race"); ps = set(present)
    rec("EDFacts race: 6 & 8/9/20/-1/-2/-3 NOT observed (SKILL176)",
        f"present={sorted(ps)}; 6-present={6 in ps}",
        "VERIFIED" if 6 not in ps and not ({8,9,20,-1,-2,-3} & ps) else "PRESENT-NOT-DOCUMENTED")
else:
    rec("EDFacts assessments.race exists", f"cols={list(sasc)}", "CONTRADICTED")
# CLAIM (TASK-REQUIRED): -2/-3 suppression codes present in assessment proficiency data (SKILL 216-223)
profcol = next((c for c in sasc if "pct_prof" in c and "midpt" not in c), None)
print(f"    proficiency col chosen: {profcol}")
if profcol:
    try:
        vc = (scan(sa).select(profcol).filter(pl.col(profcol).is_in([-1,-2,-3,-9]))
              .group_by(profcol).len().collect())
        counts = {r[profcol]: r["len"] for r in vc.to_dicts()}
        rec(f"EDFacts assessments -1/-2/-3 present in {profcol} (SKILL216-223; TASK-REQUIRED)",
            f"neg-code counts={counts}",
            "VERIFIED" if set(counts) & {-2,-3} else "DOCUMENTED-NOT-PRESENT")
    except Exception as e:
        rec("EDFacts assessment suppression codes", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")
# CLAIM: _midpt companion variable exists (SKILL 221-223)
midpts = [c for c in sasc if c.endswith("_midpt")]
rec("EDFacts assessments has _midpt companion vars (SKILL221)", f"midpt cols={midpts}",
    "VERIFIED" if midpts else "CONTRADICTED")

print("\n### TALLY ###")
for k, v in Counter(v for _,_,v in results).items(): print(f"  {k}: {v}")
print("DONE 27")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:14:45
# Command: python3 /daaf/scripts/mirror_maintenance/27_meps-saipe-edfacts-doc-audit.py
# Duration: 22s
# Exit code: 0
#
# --- STDOUT ---
# 
# ========== MEPS ==========
# MEPS schema (11 cols): {'year': Int64, 'fips': Int64, 'gleaid': Int64, 'ncessch': Int64, 'meps_poverty_pct': Float64, 'meps_poverty_se': Float64, 'meps_mod_poverty_pct': Float64, 'meps_poverty_ptl': Int64, 'meps_mod_poverty_ptl': Int64, 'ncessch_num': Int64, 'leaid': Int64}
# [VERIFIED] MEPS schema dtypes match var-defs 296-308 -> mismatches={}
# [VERIFIED] MEPS meps_poverty_pct range ~0.0-60.5 (var-defs 53) -> [0.0, 60.534702]
# [VERIFIED] MEPS meps_mod_poverty_pct range ~0.0-100 (var-defs 54) -> [0.0, 100.0]
# [VERIFIED] MEPS meps_poverty_se range ~0.52-3.77 (var-defs 84) -> [0.52193713, 3.7669785]
# [VERIFIED] MEPS meps_poverty_ptl range 1-100 (var-defs 56) -> [1, 100]
# [VERIFIED] MEPS year coverage 2009-2022 (SKILL desc) -> [2009, 2022]
# [VERIFIED] MEPS uses native null, no negative codes (var-defs 121) -> neg-value rows=0; nulls=29309
# 
# ========== SAIPE ==========
# SAIPE schema (10 cols): {'district_id': Int64, 'district_name': String, 'est_population_total': Int64, 'est_population_5_17': Int64, 'est_population_5_17_poverty': Int64, 'year': Int64, 'leaid': Int64, 'fips': Int64, 'est_population_5_17_poverty_pct': Float64, 'est_population_5_17_pct': Float64}
# [VERIFIED] SAIPE schema cols/dtypes match var-defs 388-399 -> mismatches={}
# [VERIFIED] SAIPE est_population_5_17_poverty_pct is 0-1 proportion (var-defs 403 SCALE TRAP) -> range=[0.0, 1.0]
# [VERIFIED] SAIPE leaid is Int64 (var-defs 227) -> dtype=Int64
# [VERIFIED] SAIPE no negative coded values in any numeric col (var-defs 301) -> cols-with-neg=[]
# 
# ========== EDFACTS ==========
# school_assessments_2020 (26 cols): ['fips', 'leaid_num', 'leaid', 'lea_name', 'ncessch_num', 'ncessch', 'school_name', 'read_test_num_valid', 'year', 'math_test_num_valid', 'race', 'sex', 'lep', 'homeless', 'migrant', 'disability', 'econ_disadvantaged', 'foster_care', 'military_connected', 'read_test_pct_prof_low', 'read_test_pct_prof_high', 'read_test_pct_prof_midpt', 'math_test_pct_prof_low', 'math_test_pct_prof_high', 'math_test_pct_prof_midpt', 'grade_edfacts']
# school_grad_rates_2018 (18 cols): ['ncessch_num', 'ncessch', 'year', 'school_name', 'leaid_num', 'leaid', 'lea_name', 'fips', 'race', 'lep', 'homeless', 'disability', 'econ_disadvantaged', 'foster_care', 'cohort_num', 'grad_rate_low', 'grad_rate_high', 'grad_rate_midpt']
# [VERIFIED] EDFacts assessments.ncessch Int64 (SKILL118-122) -> dtype=Int64
# [VERIFIED] EDFacts assessments.ncessch_num Int64 (SKILL118-122) -> dtype=Int64
# [VERIFIED] EDFacts assessments.leaid Int64 (SKILL118-122) -> dtype=Int64
# [VERIFIED] EDFacts assessments.fips Int64 (SKILL118-122) -> dtype=Int64
# [VERIFIED] EDFacts school_assessments has 26 cols (SKILL 245-248) -> observed=26
# [VERIFIED] EDFacts school_grad_rates has 18 cols (SKILL 245-248) -> observed=18
# [VERIFIED] EDFacts district_assessments has 23 cols (SKILL 245-248) -> observed=23
# [VERIFIED] EDFacts district_grad_rates has 15 cols (SKILL 245-248) -> observed=15
# [VERIFIED] EDFacts grad_rates lacks sex/migrant/military_connected (SKILL134) -> absent=['sex', 'migrant', 'military_connected']
# [VERIFIED] EDFacts grade_edfacts codes 3-8,9,99 (SKILL154-160) -> present=[3, 4, 5, 6, 7, 8, 9, 99]; present-not-doc=[]
# [VERIFIED] EDFacts race: 6 & 8/9/20/-1/-2/-3 NOT observed (SKILL176) -> present=[1, 2, 3, 4, 5, 7, 99]; 6-present=False
#     proficiency col chosen: read_test_pct_prof_low
# [VERIFIED] EDFacts assessments -1/-2/-3 present in read_test_pct_prof_low (SKILL216-223; TASK-REQUIRED) -> neg-code counts={-3: 101519}
# [VERIFIED] EDFacts assessments has _midpt companion vars (SKILL221) -> midpt cols=['read_test_pct_prof_midpt', 'math_test_pct_prof_midpt']
# 
# ### TALLY ###
#   VERIFIED: 24
# DONE 27
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
