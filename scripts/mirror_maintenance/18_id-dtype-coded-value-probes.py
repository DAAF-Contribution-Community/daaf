# --- Config ---
# INTENT: Verify load-bearing ID-dtype and coded-value claims from the CHANGED source
#         skills against LIVE pinned data, for broad source coverage.
# REASONING: Adversarial re-proof of the drift report's identifier claims and the
#            context skill's coded-value semantics. Prioritizes load-bearing claims
#            (id dtypes, alphanumeric leaid, missing-code sentinels, grade encoding).
# ASSUMES: pinned public repo; schema projection + tiny filtered samples over HTTP.
# Skills under test: education-data-source-ccd/SKILL.md (+variable-definitions.md),
#   education-data-source-crdc/SKILL.md, education-data-context/SKILL.md,
#   education-data-source-nhgis/SKILL.md, education-data-source-pseo/SKILL.md,
#   education-data-source-nacubo/SKILL.md, education-data-source-nccs/SKILL.md.
import polars as pl
import time

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"
findings = []

def scan(rel):
    return pl.scan_parquet(f"{BASE}/{rel}.parquet")

# --- Probe 1: CCD leaid heterogeneity (no universal id contract) ---
# CLAIM (CCD SKILL): leaid is native String incl. alphanumeric '06D0004' (widths 2-7)
# in districts_ccd_finance, but Int64 in school-districts_lea_directory and districts_saipe.
ccd_id_files = {
    "ccd/districts_ccd_finance": "String+alphanumeric",
    "ccd/school-districts_lea_directory": "Int64",
    "saipe/districts_saipe": "Int64",
}
for rel, expected in ccd_id_files.items():
    try:
        sch = dict(scan(rel).collect_schema())
        dt = str(sch.get("leaid"))
        note = ""
        if "String" in dt:
            # INTENT: pull a few alphanumeric leaid values to prove '06D0004'-style content.
            alnum = (scan(rel).select("leaid")
                     .filter(pl.col("leaid").str.contains(r"[A-Za-z]"))
                     .unique().head(5).collect()["leaid"].to_list())
            note = f"alphanumeric-sample={alnum}"
        obs = f"leaid dtype={dt}; {note}".strip()
        verdict = "VERIFIED" if expected.split("+")[0] in dt else "CONTRADICTED"
    except Exception as e:
        obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
    print(f"1. {rel:40} expect~{expected:18} -> {obs} [{verdict}]")
    findings.append(("CCD leaid dtype heterogeneity", f"CCD SKILL: {rel} leaid={expected}", obs, verdict))

# --- Probe 2: CRDC 2020 vintage id columns String + alphanumeric ---
# CLAIM (CRDC SKILL / datasets-reference): crdc_id, ncessch, leaid are String (zero-padded);
# drift report: only-genuine dtype change was Int64->String for 2020 vintage.
crdc_2020 = "crdc/schools_crdc_enrollment_k12_2020"
try:
    sch = dict(scan(crdc_2020).collect_schema())
    idcols = {c: str(sch.get(c)) for c in ["crdc_id", "ncessch", "leaid"] if c in sch}
    # Sample leaid values from FIPS 01-09 states to show preserved leading zeros/alphanumerics.
    samp = (scan(crdc_2020).select("leaid").unique()
            .filter(pl.col("leaid").str.contains(r"^0")).head(5).collect()["leaid"].to_list())
    all_str = all("String" in v for v in idcols.values()) and len(idcols) == 3
    obs = f"dtypes={idcols}; leading-zero leaid sample={samp}"
    verdict = "VERIFIED" if all_str else "CONTRADICTED"
except Exception as e:
    obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
print(f"2. {crdc_2020} id dtypes -> {obs} [{verdict}]")
findings.append(("CRDC 2020 id cols String+alnum", "CRDC SKILL/datasets-ref: crdc_id/ncessch/leaid=String", obs, verdict))

# --- Probe 3: CCD missing-code sentinels + grade encoding ---
# CLAIM (context SKILL): missing codes -1 missing, -2 not applicable, -3 suppressed;
# grade=-1 is Pre-K (not missing).
ccd_enr = "ccd/schools_ccd_enrollment_2020"
try:
    sch = dict(scan(ccd_enr).collect_schema())
    grades = sorted(int(v) for v in scan(ccd_enr).select("grade").unique().collect()["grade"].drop_nulls().to_list())
    neg_enroll = sorted(int(v) for v in (scan(ccd_enr).select("enrollment").unique()
                        .filter(pl.col("enrollment") < 0).collect()["enrollment"].drop_nulls().to_list()))
    grade_neg1 = -1 in grades
    sentinels_present = [s for s in (-1, -2, -3) if s in neg_enroll]
    obs = f"grade distinct={grades[:6]}...; grade=-1(PreK)present={grade_neg1}; negative enrollment sentinels={neg_enroll}"
    verdict = "VERIFIED" if grade_neg1 and sentinels_present else "PARTIAL"
except Exception as e:
    obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
print(f"3. {ccd_enr} coded values -> {obs} [{verdict}]")
findings.append(("CCD grade=-1 Pre-K + missing sentinels", "context SKILL: -1/-2/-3 codes; grade=-1=Pre-K", obs, verdict))

# --- Probe 4: NHGIS join keys (schools=ncessch, colleges=unitid) + unitid integer ---
# CLAIM (NHGIS SKILL): schools linked via ncessch, colleges via unitid.
# CLAIM (context SKILL): keep IPEDS unitid as integer (Int64).
for rel, key in [("nhgis/schools_nhgis_geog_2020", "ncessch"), ("nhgis/colleges_nhgis_geog_2020", "unitid")]:
    try:
        sch = dict(scan(rel).collect_schema())
        present = key in sch
        obs = f"{key} present={present}, dtype={sch.get(key)}"
        verdict = "VERIFIED" if present else "CONTRADICTED"
    except Exception as e:
        obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
    print(f"4. {rel:36} join-key={key} -> {obs} [{verdict}]")
    findings.append(("NHGIS join key present", f"NHGIS SKILL: {rel.split('/')[1]} uses {key}", obs, verdict))
# unitid integer claim on IPEDS directory
try:
    sch = dict(scan("ipeds/colleges_ipeds_directory").collect_schema())
    dt = str(sch.get("unitid"))
    obs = f"ipeds directory unitid dtype={dt}"
    verdict = "VERIFIED" if "Int" in dt else "CONTRADICTED"
except Exception as e:
    obs = f"ERR {type(e).__name__}"; verdict = "UNTESTABLE"
print(f"4b. IPEDS directory unitid -> {obs} [{verdict}]")
findings.append(("IPEDS unitid integer", "context SKILL: keep unitid as Int64", obs, verdict))

# --- Probe 5: PSEO earnings percentile columns (25/50/75 at 1/5/10 yr) ---
# CLAIM (PSEO SKILL): earnings 25th/50th/75th percentile measured 1,5,10 yrs post-grad.
pseo = "pseo/colleges_pseo_2021"
try:
    cols = scan(pseo).collect_schema().names()
    pctl = [c for c in cols if any(k in c.lower() for k in ("p25", "p50", "p75", "percentile", "earnings"))]
    yrmark = [c for c in cols if any(k in c.lower() for k in ("y1", "y5", "y10", "1yr", "5yr", "10yr", "grad_cohort", "years"))]
    obs = f"ncols={len(cols)}; earnings/percentile-like cols={pctl[:12]}"
    verdict = "VERIFIED" if pctl else "CONTRADICTED"
except Exception as e:
    obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
print(f"5. {pseo} percentile cols -> {obs} [{verdict}]")
findings.append(("PSEO earnings percentile columns", "PSEO SKILL: 25/50/75 pctile earnings", obs, verdict))

# --- Probe 6: NACUBO 7-column schema ---
# CLAIM (datasets-reference/NACUBO SKILL): Portal NACUBO has 7 columns only.
nac = "nacubo/colleges_nacubo_endow"
try:
    cols = scan(nac).collect_schema().names()
    obs = f"ncols={len(cols)}: {cols}"
    verdict = "VERIFIED" if len(cols) == 7 else "CONTRADICTED"
except Exception as e:
    obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
print(f"6. {nac} -> {obs} [{verdict}]")
findings.append(("NACUBO 7-column schema", "datasets-ref/NACUBO SKILL: 7 columns only", obs, verdict))

# --- Probe 7: NCCS IPEDS-matched (unitid present) ---
# CLAIM (NCCS SKILL): Portal mirror is IPEDS-matched; join on unitid.
nccs = "nccs/colleges_nccs_all"
try:
    sch = dict(scan(nccs).collect_schema())
    present = "unitid" in sch
    obs = f"unitid present={present}, dtype={sch.get('unitid')}; ncols={len(sch)}"
    verdict = "VERIFIED" if present else "CONTRADICTED"
except Exception as e:
    obs = f"ERR {type(e).__name__}: {str(e)[:120]}"; verdict = "UNTESTABLE"
print(f"7. {nccs} -> {obs} [{verdict}]")
findings.append(("NCCS IPEDS-matched (unitid)", "NCCS SKILL: IPEDS-matched, join on unitid", obs, verdict))

# --- Summary ---
print("\n--- SCRIPT 18 FINDINGS ---")
for claim, source, observed, verdict in findings:
    print(f"[{verdict:12}] {claim} | {source} | {observed}")

OUT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/18_id-coded-findings.parquet"
pl.DataFrame(findings, schema=["claim", "source", "observed", "verdict"], orient="row").write_parquet(OUT)
print(f"\nSaved: {OUT}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:13:03
# Command: python3 /daaf/scripts/mirror_maintenance/18_id-dtype-coded-value-probes.py
# Duration: 17s
# Exit code: 0
#
# --- STDOUT ---
# 1. ccd/districts_ccd_finance                expect~String+alphanumeric -> leaid dtype=String; alphanumeric-sample=['36D0001', '06D0025', '26D0002', '06D0024', '06D0011'] [VERIFIED]
# 1. ccd/school-districts_lea_directory       expect~Int64              -> leaid dtype=Int64; [VERIFIED]
# 1. saipe/districts_saipe                    expect~Int64              -> leaid dtype=Int64; [VERIFIED]
# 2. crdc/schools_crdc_enrollment_k12_2020 id dtypes -> dtypes={'crdc_id': 'Int64', 'ncessch': 'String', 'leaid': 'String'}; leading-zero leaid sample=[] [CONTRADICTED]
# 3. ccd/schools_ccd_enrollment_2020 coded values -> grade distinct=[-1, 0, 1, 2, 3, 4]...; grade=-1(PreK)present=True; negative enrollment sentinels=[] [PARTIAL]
# 4. nhgis/schools_nhgis_geog_2020        join-key=ncessch -> ncessch present=True, dtype=Int64 [VERIFIED]
# 4. nhgis/colleges_nhgis_geog_2020       join-key=unitid -> unitid present=True, dtype=Int64 [VERIFIED]
# 4b. IPEDS directory unitid -> ipeds directory unitid dtype=Int64 [VERIFIED]
# 5. pseo/colleges_pseo_2021 percentile cols -> ncols=18; earnings/percentile-like cols=['p25_earnings', 'p50_earnings', 'p75_earnings'] [VERIFIED]
# 6. nacubo/colleges_nacubo_endow -> ncols=7: ['year', 'unitid', 'inst_name_nacubo', 'fips', 'endow_total', 'endow_per_fte', 'endow_chg_mktval'] [VERIFIED]
# 7. nccs/colleges_nccs_all -> unitid present=True, dtype=Int64; ncols=161 [VERIFIED]
# 
# --- SCRIPT 18 FINDINGS ---
# [VERIFIED    ] CCD leaid dtype heterogeneity | CCD SKILL: ccd/districts_ccd_finance leaid=String+alphanumeric | leaid dtype=String; alphanumeric-sample=['36D0001', '06D0025', '26D0002', '06D0024', '06D0011']
# [VERIFIED    ] CCD leaid dtype heterogeneity | CCD SKILL: ccd/school-districts_lea_directory leaid=Int64 | leaid dtype=Int64;
# [VERIFIED    ] CCD leaid dtype heterogeneity | CCD SKILL: saipe/districts_saipe leaid=Int64 | leaid dtype=Int64;
# [CONTRADICTED] CRDC 2020 id cols String+alnum | CRDC SKILL/datasets-ref: crdc_id/ncessch/leaid=String | dtypes={'crdc_id': 'Int64', 'ncessch': 'String', 'leaid': 'String'}; leading-zero leaid sample=[]
# [PARTIAL     ] CCD grade=-1 Pre-K + missing sentinels | context SKILL: -1/-2/-3 codes; grade=-1=Pre-K | grade distinct=[-1, 0, 1, 2, 3, 4]...; grade=-1(PreK)present=True; negative enrollment sentinels=[]
# [VERIFIED    ] NHGIS join key present | NHGIS SKILL: schools_nhgis_geog_2020 uses ncessch | ncessch present=True, dtype=Int64
# [VERIFIED    ] NHGIS join key present | NHGIS SKILL: colleges_nhgis_geog_2020 uses unitid | unitid present=True, dtype=Int64
# [VERIFIED    ] IPEDS unitid integer | context SKILL: keep unitid as Int64 | ipeds directory unitid dtype=Int64
# [VERIFIED    ] PSEO earnings percentile columns | PSEO SKILL: 25/50/75 pctile earnings | ncols=18; earnings/percentile-like cols=['p25_earnings', 'p50_earnings', 'p75_earnings']
# [VERIFIED    ] NACUBO 7-column schema | datasets-ref/NACUBO SKILL: 7 columns only | ncols=7: ['year', 'unitid', 'inst_name_nacubo', 'fips', 'endow_total', 'endow_per_fte', 'endow_chg_mktval']
# [VERIFIED    ] NCCS IPEDS-matched (unitid) | NCCS SKILL: IPEDS-matched, join on unitid | unitid present=True, dtype=Int64; ncols=161
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/18_id-coded-findings.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
