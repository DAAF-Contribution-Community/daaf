# --- Config ---
# INTENT: Exhaustively verify DATA-testable claims in education-data-source-crdc
#   (SKILL.md + variable-definitions.md) against LIVE pinned mirror. Explicitly
#   exercises the -2/-3 missing-code claims on suppression-bearing discipline data.
# REASONING: Adversarial re-proof of id-typing heterogeneity, race/sex/disability/lep
#   coded-value sets, sex=3 presence, absence of grade column, universe row counts.
# ASSUMES: pinned public repo; concise verdict-only output to conserve context.
# Skills under test: crdc/SKILL.md (149-213), crdc/references/variable-definitions.md
#   (race 43-62, sex 96-116, disability 144-164, lep 192-198, missing 359-364, grade 526-528).
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

# --- 1. Identifier typing heterogeneity (SKILL 157) ---
print("\n### SECTION 1: ID TYPING ###")
id_files = {
    "crdc/schools_crdc_school_characteristics": ("all String", ["crdc_id","ncessch","leaid"]),
    "crdc/schools_crdc_enrollment_k12_2020": ("crdc_id Int64", ["crdc_id","ncessch","leaid"]),
    "crdc/schools_crdc_harass_bully_students_2020": ("all Int64", ["crdc_id","ncessch","leaid"]),
}
schemas = {}
for rel, (exp, cols) in id_files.items():
    try:
        sc = schema(rel); schemas[rel] = sc
        dts = {c: str(sc.get(c, "ABSENT")) for c in cols}
        rec(f"CRDC id typing {rel} (SKILL157: {exp})", f"{dts}", "INFO")
    except Exception as e:
        rec(f"CRDC id typing {rel}", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

# --- 2. Column-name claims (SKILL 356-358; var-defs 430) ---
print("\n### SECTION 2: COLUMN NAMES ###")
enr20 = "crdc/schools_crdc_enrollment_k12_2020"
disc20 = "crdc/schools_crdc_discipline_k12_2020"
esc = schemas.get(enr20) or schema(enr20)
dsc = schema(disc20)
rec("CRDC enrollment has 'enrollment_crdc' col (SKILL357)",
    f"present={'enrollment_crdc' in esc}", "VERIFIED" if "enrollment_crdc" in esc else "CONTRADICTED")
rec("CRDC discipline has 'students_susp_out_sch_single' col (SKILL348)",
    f"present={'students_susp_out_sch_single' in dsc}",
    "VERIFIED" if "students_susp_out_sch_single" in dsc else "CONTRADICTED")
rec("CRDC has NO 'grade' column (var-defs 526-528)",
    f"grade in enrollment schema={'grade' in esc}", "VERIFIED" if "grade" not in esc else "CONTRADICTED")
print(f"    enrollment_2020 cols: {list(esc)}")
print(f"    discipline_2020 cols: {list(dsc)}")

# --- 3. Coded values: race / sex / disability / lep in enrollment + discipline ---
print("\n### SECTION 3: CODED VALUES ###")
def check(rel, col, claim_set, note):
    if col not in (schemas.get(rel) or schema(rel)):
        rec(f"{rel}.{col} exists ({note})", "ABSENT", "CONTRADICTED"); return
    try:
        present, hn = uvals(rel, col); ps = set(present)
        pnd = ps - claim_set
        rec(f"{rel.split('/')[1]}.{col} ({note})",
            f"present={sorted(ps)}; present-not-doc={sorted(pnd)}; null={hn}",
            "PRESENT-NOT-DOCUMENTED" if pnd else "VERIFIED")
    except Exception as e:
        rec(f"{rel}.{col}", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

RACE = {1,2,3,4,5,6,7,8,9,20,99,-1,-2,-3}          # var-defs full codebook set
SEX  = {1,2,3,9,99,-1,-2,-3}
DIS  = {0,1,2,3,4,99,-1,-2,-3}
LEP  = {1,99,-1,-2,-3}
for col, cs, note in [("race",RACE,"1-7,99 obs; 8/9/20 defined-not-obs"),
                      ("sex",SEX,"1,2,99 (+3 newer)"),
                      ("disability",DIS,"enrollment~[1,2,99]"),
                      ("lep",LEP,"1,99")]:
    check(enr20, col, cs, note)
for col, cs, note in [("race",RACE,"disc 1-7,99"),
                      ("sex",SEX,"disc 1,2,99"),
                      ("disability",DIS,"disc~[0,1,2,4,99]"),
                      ("lep",LEP,"disc 1,99")]:
    check(disc20, col, cs, note)

# --- 4. sex=3 presence in 2021 collection (var-defs 114: ~174K rows w/ real data) ---
print("\n### SECTION 4: SEX=3 IN 2021 ###")
enr21 = "crdc/schools_crdc_enrollment_k12_2021"
try:
    e21 = schema(enr21)
    if "sex" in e21 and "enrollment_crdc" in e21:
        s3 = scan(enr21).filter(pl.col("sex") == 3)
        total3 = s3.select(pl.len()).collect().item()
        real3 = s3.filter(pl.col("enrollment_crdc") >= 0).select(pl.len()).collect().item()
        rec("CRDC sex=3 exists in enrollment_2021 w/ ~174K real rows (var-defs 114)",
            f"total sex=3 rows={total3}; rows w/ enrollment_crdc>=0={real3}",
            "VERIFIED" if total3 > 0 else "CONTRADICTED")
    else:
        rec("CRDC sex=3 2021 testable", f"cols missing: {[c for c in ['sex','enrollment_crdc'] if c not in e21]}", "UNTESTABLE")
except Exception as e:
    rec("CRDC sex=3 2021", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

# --- 5. Missing-code sentinels -1/-2/-3 in suppression-bearing discipline data ---
print("\n### SECTION 5: MISSING CODES -1/-2/-3 IN DISCIPLINE ###")
try:
    col = "students_susp_out_sch_single"
    vc = (scan(disc20).select(col)
          .filter(pl.col(col).is_in([-1,-2,-3,-9]))
          .group_by(col).len().collect())
    present_neg = sorted(vc[col].to_list())
    counts = {r[col]: r["len"] for r in vc.to_dicts()}
    rec("CRDC discipline -1/-2/-3 sentinels present (var-defs 359-364; task-required)",
        f"neg codes present={present_neg}; counts={counts}",
        "VERIFIED" if set(present_neg) & {-2,-3} else "DOCUMENTED-NOT-PRESENT")
except Exception as e:
    rec("CRDC discipline missing codes", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

# --- 6. Universe row/school-count claim: 2013-14 ~95,507 schools (SKILL 122) ---
print("\n### SECTION 6: 2013 UNIVERSE SCHOOL COUNT ###")
try:
    enr13 = "crdc/schools_crdc_enrollment_k12_2013"
    e13 = schema(enr13)
    idcol = "ncessch" if "ncessch" in e13 else ("crdc_id" if "crdc_id" in e13 else None)
    if idcol:
        nsch = scan(enr13).select(pl.col(idcol).n_unique()).collect().item()
        rec("CRDC 2013-14 ~95,507 schools (SKILL122)",
            f"distinct {idcol}={nsch}",
            "VERIFIED" if 90000 <= nsch <= 100000 else "PRESENT-NOT-DOCUMENTED")
    else:
        rec("CRDC 2013 school count", f"no id col; cols={list(e13)[:10]}", "UNTESTABLE")
except Exception as e:
    rec("CRDC 2013 school count", f"ERR {type(e).__name__}: {str(e)[:100]}", "UNTESTABLE")

print("\n### TALLY ###")
for k, v in Counter(v for _,_,v in results).items(): print(f"  {k}: {v}")
print("DONE 26")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:12:20
# Command: python3 /daaf/scripts/mirror_maintenance/26_crdc-doc-audit.py
# Duration: 27s
# Exit code: 0
#
# --- STDOUT ---
# 
# ### SECTION 1: ID TYPING ###
# [INFO] CRDC id typing crdc/schools_crdc_school_characteristics (SKILL157: all String) -> {'crdc_id': 'String', 'ncessch': 'String', 'leaid': 'String'}
# [INFO] CRDC id typing crdc/schools_crdc_enrollment_k12_2020 (SKILL157: crdc_id Int64) -> {'crdc_id': 'Int64', 'ncessch': 'String', 'leaid': 'String'}
# [INFO] CRDC id typing crdc/schools_crdc_harass_bully_students_2020 (SKILL157: all Int64) -> {'crdc_id': 'Int64', 'ncessch': 'Int64', 'leaid': 'Int64'}
# 
# ### SECTION 2: COLUMN NAMES ###
# [VERIFIED] CRDC enrollment has 'enrollment_crdc' col (SKILL357) -> present=True
# [VERIFIED] CRDC discipline has 'students_susp_out_sch_single' col (SKILL348) -> present=True
# [VERIFIED] CRDC has NO 'grade' column (var-defs 526-528) -> grade in enrollment schema=False
#     enrollment_2020 cols: ['ncessch', 'crdc_id', 'year', 'sex', 'race', 'disability', 'lep', 'psenrollment_crdc', 'enrollment_crdc', 'fips', 'leaid']
#     discipline_2020 cols: ['crdc_id', 'year', 'ncessch', 'leaid', 'fips', 'race', 'sex', 'disability', 'lep', 'expulsions_with_ed_serv', 'expulsions_no_ed_serv', 'expulsions_zero_tolerance', 'students_susp_in_sch', 'students_susp_out_sch_single', 'students_susp_out_sch_multiple', 'students_corporal_punish', 'students_referred_law_enforce', 'students_arrested', 'transfers_alt_sch_disc', 'revised_flag']
# 
# ### SECTION 3: CODED VALUES ###
# [VERIFIED] schools_crdc_enrollment_k12_2020.race (1-7,99 obs; 8/9/20 defined-not-obs) -> present=[1, 2, 3, 4, 5, 6, 7, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_enrollment_k12_2020.sex (1,2,99 (+3 newer)) -> present=[1, 2, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_enrollment_k12_2020.disability (enrollment~[1,2,99]) -> present=[1, 2, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_enrollment_k12_2020.lep (1,99) -> present=[1, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_discipline_k12_2020.race (disc 1-7,99) -> present=[1, 2, 3, 4, 5, 6, 7, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_discipline_k12_2020.sex (disc 1,2,99) -> present=[1, 2, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_discipline_k12_2020.disability (disc~[0,1,2,4,99]) -> present=[0, 1, 2, 4, 99]; present-not-doc=[]; null=False
# [VERIFIED] schools_crdc_discipline_k12_2020.lep (disc 1,99) -> present=[1, 99]; present-not-doc=[]; null=False
# 
# ### SECTION 4: SEX=3 IN 2021 ###
# [VERIFIED] CRDC sex=3 exists in enrollment_2021 w/ ~174K real rows (var-defs 114) -> total sex=3 rows=3626370; rows w/ enrollment_crdc>=0=173823
# 
# ### SECTION 5: MISSING CODES -1/-2/-3 IN DISCIPLINE ###
# [VERIFIED] CRDC discipline -1/-2/-3 sentinels present (var-defs 359-364; task-required) -> neg codes present=[-3, -2, -1]; counts={-2: 166068, -1: 84, -3: 864671}
# 
# ### SECTION 6: 2013 UNIVERSE SCHOOL COUNT ###
# [VERIFIED] CRDC 2013-14 ~95,507 schools (SKILL122) -> distinct ncessch=94338
# 
# ### TALLY ###
#   INFO: 3
#   VERIFIED: 14
# DONE 26
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
