# --- Config ---
# INTENT: Adjudicate the two year-audit CONTRADICTIONS from script 16 and verify
#         SAIPE column-naming + gap-year claims, all against LIVE pinned data.
# REASONING: Script 16 found (a) IPEDS grad-rates(150%) content reaches 2023 while
#            datasets-reference.md + IPEDS SKILL claim 2022, and (b) IPEDS Directory
#            min is 1980 while the "ipeds 1979-2024" authoritative range + IPEDS
#            SKILL "content minimum is 1979 (not 1980)" claim 1979. Here we (1) confirm
#            grad-rates distinct years, (2) hunt for ANY IPEDS file whose content
#            reaches 1979 to fairly adjudicate the 1979 claim, (3) test SAIPE claims.
# ASSUMES: pinned public repo; year/schema projection over HTTP.
# Skills under test: education-data-source-ipeds/SKILL.md,
#   education-data-query/references/datasets-reference.md,
#   education-data-source-saipe/SKILL.md, education-data-context/SKILL.md.
import polars as pl
import time

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

def_findings = []

# --- Probe A: IPEDS grad-rates(150%) distinct years (confirm 2023 present) ---
# CLAIM (datasets-reference row + IPEDS SKILL): "150% grad-rates file reaches 2022".
# CONTEXT SKILL instead says correction covered "1996-2023". Adjudicate from content.
url = f"{BASE}/ipeds/colleges_ipeds_grad-rates.parquet"
gr_years = None
for attempt in range(3):
    try:
        gr_years = sorted(int(v) for v in pl.scan_parquet(url).select("year").unique().collect()["year"].drop_nulls().to_list())
        break
    except Exception as e:
        print(f"[retry A {attempt}] {type(e).__name__}: {str(e)[:150]}"); time.sleep(3)
print(f"A. grad-rates(150%) distinct years: {gr_years}")
print(f"   min={gr_years[0]} max={gr_years[-1]} n={len(gr_years)}  2023_present={2023 in gr_years}")
def_findings.append(("IPEDS grad-rates(150%) terminal year", "datasets-reference row=2022 / IPEDS SKILL='reaches 2022'",
                     f"content max={gr_years[-1]}, 2023_present={2023 in gr_years}",
                     "CONTRADICTED" if gr_years[-1] != 2022 else "VERIFIED"))

# --- Probe B: IPEDS 1979 minimum hunt across single-file datasets ---
# CLAIM (IPEDS SKILL): "content minimum is 1979 (not 1980)"; authoritative range ipeds 1979-2024.
ipeds_singles = [
    "colleges_ipeds_directory", "colleges_ipeds_admissions-enrollment", "colleges_ipeds_enrollment-fte",
    "colleges_ipeds_grad-rates", "colleges_ipeds_finance", "colleges_ipeds_academic_libraries",
    "colleges_ipeds_admissions-requirements", "colleges_ipeds_ay_room_board_other",
    "colleges_ipeds_ay_tuition_fees", "colleges_ipeds_ay_tuition_firstprof", "colleges_ipeds_completers",
    "colleges_ipeds_headcount", "colleges_ipeds_fall-res", "colleges_ipeds_fall-retention",
    "colleges_ipeds_grad-rates-200pct", "colleges_ipeds_grad-rates-pell",
    "colleges_ipeds_institutional-characteristics", "colleges_ipeds_salaries_is", "colleges_ipeds_salaries_nis",
    "colleges_ipeds_outcome-measures", "colleges_ipeds_py_room_board_other", "colleges_ipeds_py_tuition_cip",
    "colleges_ipeds_sfa_all_undergrads", "colleges_ipeds_sfa_by_living_arrangement",
    "colleges_ipeds_sfa_by_tuition_type", "colleges_ipeds_sfa_ftft", "colleges_ipeds_sfa_grants_and_net_price",
    "colleges_ipeds_student-faculty-ratio",
]
min_years = {}
for name in ipeds_singles:
    u = f"{BASE}/ipeds/{name}.parquet"
    mn = None
    for attempt in range(3):
        try:
            mn = int(pl.scan_parquet(u).select(pl.col("year").min()).collect().item())
            break
        except Exception as e:
            err = f"{type(e).__name__}"; time.sleep(2)
    min_years[name] = mn
    flag = "  <<< 1979" if mn == 1979 else ""
    print(f"B. min-year {name:44} = {mn}{flag}")
files_1979 = [n for n, m in min_years.items() if m == 1979]
overall_min = min(m for m in min_years.values() if m is not None)
print(f"B-SUMMARY: overall IPEDS single-file content min across {len(ipeds_singles)} files = {overall_min}; files reaching 1979 = {files_1979}")
def_findings.append(("IPEDS content minimum year (1979 claim)", "IPEDS SKILL 'content minimum is 1979 (not 1980)'",
                     f"min across {len(ipeds_singles)} single files = {overall_min}; 1979-files={files_1979}",
                     "VERIFIED" if files_1979 else "CONTRADICTED"))

# --- Probe C: SAIPE column naming + gap years ---
# CLAIM: SAIPE columns follow est_population_5_17_* naming (task Unit2 #3);
#        SAIPE SKILL: available years 1995-2024 with gaps at 1996, 1998.
u = f"{BASE}/saipe/districts_saipe.parquet"
saipe_cols = None; saipe_years = None
for attempt in range(3):
    try:
        saipe_cols = pl.scan_parquet(u).collect_schema().names()
        saipe_years = sorted(int(v) for v in pl.scan_parquet(u).select("year").unique().collect()["year"].drop_nulls().to_list())
        break
    except Exception as e:
        print(f"[retry C {attempt}] {type(e).__name__}: {str(e)[:150]}"); time.sleep(3)
est_cols = [c for c in saipe_cols if c.startswith("est_population_5_17")]
missing = [y for y in range(1995, 2025) if y not in saipe_years]
print(f"C. SAIPE columns ({len(saipe_cols)}): {saipe_cols}")
print(f"   est_population_5_17* columns: {est_cols}")
print(f"   years {saipe_years[0]}-{saipe_years[-1]} n={len(saipe_years)}; missing in 1995-2024 = {missing}")
def_findings.append(("SAIPE est_population_5_17_* naming", "task Unit2 #3 / SAIPE columns",
                     f"matching cols={est_cols}", "VERIFIED" if est_cols else "CONTRADICTED"))
def_findings.append(("SAIPE gap years (1996,1998)", "SAIPE SKILL 'gaps at 1996, 1998'",
                     f"observed missing years={missing}", "VERIFIED" if missing == [1996, 1998] else "CONTRADICTED"))

# --- Summary ---
print("\n--- SCRIPT 17 FINDINGS ---")
for claim, source, observed, verdict in def_findings:
    print(f"[{verdict:12}] {claim} | {source} | observed: {observed}")

OUT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/17_ipeds-saipe-findings.parquet"
pl.DataFrame(def_findings, schema=["claim", "source", "observed", "verdict"], orient="row").write_parquet(OUT)
print(f"\nSaved: {OUT}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:11:09
# Command: python3 /daaf/scripts/mirror_maintenance/17_ipeds-saipe-claim-probes.py
# Duration: 34s
# Exit code: 0
#
# --- STDOUT ---
# A. grad-rates(150%) distinct years: [1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]
#    min=1996 max=2023 n=28  2023_present=True
# B. min-year colleges_ipeds_directory                     = 1980
# B. min-year colleges_ipeds_admissions-enrollment         = 2001
# B. min-year colleges_ipeds_enrollment-fte                = 1997
# B. min-year colleges_ipeds_grad-rates                    = 1996
# B. min-year colleges_ipeds_finance                       = 1979  <<< 1979
# B. min-year colleges_ipeds_academic_libraries            = 2013
# B. min-year colleges_ipeds_admissions-requirements       = 1990
# B. min-year colleges_ipeds_ay_room_board_other           = 1999
# B. min-year colleges_ipeds_ay_tuition_fees               = 1986
# B. min-year colleges_ipeds_ay_tuition_firstprof          = 1986
# B. min-year colleges_ipeds_completers                    = 2011
# B. min-year colleges_ipeds_headcount                     = 1996
# B. min-year colleges_ipeds_fall-res                      = 1986
# B. min-year colleges_ipeds_fall-retention                = 2003
# B. min-year colleges_ipeds_grad-rates-200pct             = 2007
# B. min-year colleges_ipeds_grad-rates-pell               = 2015
# B. min-year colleges_ipeds_institutional-characteristics = 1980
# B. min-year colleges_ipeds_salaries_is                   = 1980
# B. min-year colleges_ipeds_salaries_nis                  = 2012
# B. min-year colleges_ipeds_outcome-measures              = 2015
# B. min-year colleges_ipeds_py_room_board_other           = 1999
# B. min-year colleges_ipeds_py_tuition_cip                = 1987
# B. min-year colleges_ipeds_sfa_all_undergrads            = 2007
# B. min-year colleges_ipeds_sfa_by_living_arrangement     = 2008
# B. min-year colleges_ipeds_sfa_by_tuition_type           = 1999
# B. min-year colleges_ipeds_sfa_ftft                      = 1999
# B. min-year colleges_ipeds_sfa_grants_and_net_price      = 2008
# B. min-year colleges_ipeds_student-faculty-ratio         = 2009
# B-SUMMARY: overall IPEDS single-file content min across 28 files = 1979; files reaching 1979 = ['colleges_ipeds_finance']
# C. SAIPE columns (10): ['district_id', 'district_name', 'est_population_total', 'est_population_5_17', 'est_population_5_17_poverty', 'year', 'leaid', 'fips', 'est_population_5_17_poverty_pct', 'est_population_5_17_pct']
#    est_population_5_17* columns: ['est_population_5_17', 'est_population_5_17_poverty', 'est_population_5_17_poverty_pct', 'est_population_5_17_pct']
#    years 1995-2024 n=28; missing in 1995-2024 = [1996, 1998]
# 
# --- SCRIPT 17 FINDINGS ---
# [CONTRADICTED] IPEDS grad-rates(150%) terminal year | datasets-reference row=2022 / IPEDS SKILL='reaches 2022' | observed: content max=2023, 2023_present=True
# [VERIFIED    ] IPEDS content minimum year (1979 claim) | IPEDS SKILL 'content minimum is 1979 (not 1980)' | observed: min across 28 single files = 1979; 1979-files=['colleges_ipeds_finance']
# [VERIFIED    ] SAIPE est_population_5_17_* naming | task Unit2 #3 / SAIPE columns | observed: matching cols=['est_population_5_17', 'est_population_5_17_poverty', 'est_population_5_17_poverty_pct', 'est_population_5_17_pct']
# [VERIFIED    ] SAIPE gap years (1996,1998) | SAIPE SKILL 'gaps at 1996, 1998' | observed: observed missing years=[1996, 1998]
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_skill-spotcheck/17_ipeds-saipe-findings.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
