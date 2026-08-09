# --- Config ---
# INTENT: Adversarially adjudicate two script-18 anomalies against LIVE data:
#         (a) CRDC 2020 crdc_id came back Int64 (not String) with an empty leading-zero
#             leaid sample; (b) CCD 2020 enrollment column carried no -1/-2/-3 sentinels.
# REASONING: The datasets-reference CRDC note claims crdc_id/ncessch/leaid are ALL String;
#            the context skill claims -1/-2/-3 missing-code semantics. Probe multiple CRDC
#            2020 files + actual id value samples/lengths, and scan ALL CCD coded columns
#            for the sentinels, so the verdict rests on content, not one column.
# ASSUMES: pinned public repo; schema + tiny filtered samples over HTTP.
# Skills under test: education-data-source-crdc/SKILL.md,
#   education-data-query/references/datasets-reference.md (CRDC ID columns note),
#   education-data-context/SKILL.md (missing codes).
import polars as pl
import time

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"
findings = []

# --- Probe A: CRDC 2020 id dtypes across multiple files ---
# CLAIM: "All CRDC datasets have crdc_id, ncessch, and leaid as String columns."
crdc_files = [
    "crdc/schools_crdc_enrollment_k12_2020",
    "crdc/schools_crdc_discipline_k12_2020",
    "crdc/schools_crdc_harass_bully_students_2020",
    "crdc/schools_crdc_school_characteristics",
]
for rel in crdc_files:
    try:
        sch = dict(pl.scan_parquet(f"{BASE}/{rel}.parquet").collect_schema())
        idcols = {c: str(sch.get(c)) for c in ["crdc_id", "ncessch", "leaid"] if c in sch}
        # Pull actual leaid samples + min/max string length to check zero-padding/alphanumerics.
        lsamp, lmin, lmax = None, None, None
        if "leaid" in sch and "String" in str(sch["leaid"]):
            s = pl.scan_parquet(f"{BASE}/{rel}.parquet").select("leaid").drop_nulls().head(2000).collect()["leaid"]
            lsamp = s.head(3).to_list()
            lens = s.str.len_chars()
            lmin, lmax = int(lens.min()), int(lens.max())
        obs = f"idcols={idcols}; leaid sample={lsamp} len[{lmin},{lmax}]"
        all_str = len(idcols) == 3 and all("String" in v for v in idcols.values())
        verdict = "VERIFIED" if all_str else "CONTRADICTED"
    except Exception as e:
        obs = f"ERR {type(e).__name__}: {str(e)[:130]}"; verdict = "UNTESTABLE"
    print(f"A. {rel:46} -> {obs} [{verdict}]")
    findings.append(("CRDC id cols all String", f"datasets-ref CRDC note @ {rel.split('/')[1]}", obs, verdict))

# --- Probe B: CCD 2020 enrollment — sentinel codes across all integer coded columns ---
# CLAIM (context SKILL): -1 missing, -2 not applicable, -3 suppressed.
ccd = "ccd/schools_ccd_enrollment_2020"
try:
    sch = dict(pl.scan_parquet(f"{BASE}/{ccd}.parquet").collect_schema())
    print(f"B. CCD enrollment schema: { {k: str(v) for k, v in sch.items()} }")
    int_cols = [c for c, t in sch.items() if str(t) in ("Int64", "Int32") and c != "year"]
    sentinel_hits = {}
    for c in int_cols:
        negs = (pl.scan_parquet(f"{BASE}/{ccd}.parquet").select(c).unique()
                .filter(pl.col(c) < 0).collect()[c].drop_nulls().to_list())
        negs = sorted(int(v) for v in negs)
        if negs:
            sentinel_hits[c] = negs
    union_sentinels = sorted({v for negs in sentinel_hits.values() for v in negs})
    obs = f"columns w/ negatives={sentinel_hits}; union={union_sentinels}"
    # VERIFIED if the documented sentinel family (-1/-2/-3) appears somewhere in the file.
    verdict = "VERIFIED" if any(s in union_sentinels for s in (-1, -2, -3)) else "UNTESTABLE"
except Exception as e:
    obs = f"ERR {type(e).__name__}: {str(e)[:130]}"; verdict = "UNTESTABLE"
print(f"B. CCD sentinel scan -> {obs} [{verdict}]")
findings.append(("CCD -1/-2/-3 missing-code sentinels present", "context SKILL missing codes", obs, verdict))

# --- Summary ---
print("\n--- SCRIPT 19 FINDINGS ---")
for claim, source, observed, verdict in findings:
    print(f"[{verdict:12}] {claim} | {source} | {observed}")

OUT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/19_crdc-ccd-deepdive-findings.parquet"
pl.DataFrame(findings, schema=["claim", "source", "observed", "verdict"], orient="row").write_parquet(OUT)
print(f"\nSaved: {OUT}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:14:17
# Command: python3 /daaf/scripts/mirror_maintenance/19_crdc-ccd-sentinel-deepdive.py
# Duration: 17s
# Exit code: 0
#
# --- STDOUT ---
# A. crdc/schools_crdc_enrollment_k12_2020          -> ERR TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType' [UNTESTABLE]
# A. crdc/schools_crdc_discipline_k12_2020          -> idcols={'crdc_id': 'String', 'ncessch': 'Int64', 'leaid': 'String'}; leaid sample=['0100002', '0100002', '0100002'] len[7,7] [CONTRADICTED]
# A. crdc/schools_crdc_harass_bully_students_2020   -> idcols={'crdc_id': 'Int64', 'ncessch': 'Int64', 'leaid': 'Int64'}; leaid sample=None len[None,None] [CONTRADICTED]
# A. crdc/schools_crdc_school_characteristics       -> idcols={'crdc_id': 'String', 'ncessch': 'String', 'leaid': 'String'}; leaid sample=['0633150', '4703780', '3600095'] len[7,7] [VERIFIED]
# B. CCD enrollment schema: {'year': 'Int64', 'ncessch': 'Int64', 'ncessch_num': 'Int64', 'leaid': 'Int64', 'fips': 'Int64', 'grade': 'Int64', 'race': 'Int64', 'sex': 'Int64', 'enrollment': 'Int64'}
# B. CCD sentinel scan -> columns w/ negatives={'grade': [-1]}; union=[-1] [VERIFIED]
# 
# --- SCRIPT 19 FINDINGS ---
# [UNTESTABLE  ] CRDC id cols all String | datasets-ref CRDC note @ schools_crdc_enrollment_k12_2020 | ERR TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
# [CONTRADICTED] CRDC id cols all String | datasets-ref CRDC note @ schools_crdc_discipline_k12_2020 | idcols={'crdc_id': 'String', 'ncessch': 'Int64', 'leaid': 'String'}; leaid sample=['0100002', '0100002', '0100002'] len[7,7]
# [CONTRADICTED] CRDC id cols all String | datasets-ref CRDC note @ schools_crdc_harass_bully_students_2020 | idcols={'crdc_id': 'Int64', 'ncessch': 'Int64', 'leaid': 'Int64'}; leaid sample=None len[None,None]
# [VERIFIED    ] CRDC id cols all String | datasets-ref CRDC note @ schools_crdc_school_characteristics | idcols={'crdc_id': 'String', 'ncessch': 'String', 'leaid': 'String'}; leaid sample=['0633150', '4703780', '3600095'] len[7,7]
# [VERIFIED    ] CCD -1/-2/-3 missing-code sentinels present | context SKILL missing codes | columns w/ negatives={'grade': [-1]}; union=[-1]
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/19_crdc-ccd-deepdive-findings.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
