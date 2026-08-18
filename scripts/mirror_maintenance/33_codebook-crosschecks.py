# --- Config ---
# INTENT: Unit 2 of doc-audit gap-fill — cross-check 2-3 documented variable-definition
#   claims per K-12 source (+csafety) against the mirrored .xls CODEBOOK, which the skills
#   themselves declare the authoritative documentation layer ("Truth Hierarchy"/"Codebook
#   Authority"). The K-12 audit proved codebook reads feasible (script 24) but did not run
#   the per-source cross-checks; this closes that gap.
# REASONING: Adversarial. Download each codebook .xls over the pinned mirror URL, parse with
#   pl.read_excel(BytesIO) (calamine/xlrd available), print every (variable,label) row for
#   audit, then verdict each documented variable: VERIFIED if the variable NAME is present in
#   the codebook AND its label corroborates the skill (keyword match); CONTRADICTED if the
#   documented name is absent; UNTESTABLE on read failure. Labels printed verbatim as evidence.
# ASSUMES: codebook schema is (variable, format, label)-like (script 24 saw exactly that on
#   ccd directory); code tolerates alternate column names by locating the name/label columns.
# Sources & codebook paths (datasets-reference.md 54-285).
import polars as pl
import urllib.request, urllib.error, io, time
from collections import Counter

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

def fetch_codebook(rel, retries=3):
    url = f"{BASE}/{rel}.xls"
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "daaf-audit"})
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read()
            return pl.read_excel(io.BytesIO(raw))
        except Exception as e:
            last = e; time.sleep(2 * (a + 1))
    raise last

def find_col(df, *cands):
    low = {c.lower(): c for c in df.columns}
    for cand in cands:
        if cand in low:
            return low[cand]
    return None

results = []
def rec(claim, obs, verdict):
    results.append((claim, obs, verdict)); print(f"    [{verdict}] {claim} -> {obs}")

# Per-source: (codebook_path, [(documented_var, [acceptable label keywords], skill-cite)])
PLAN = {
    "ccd": ("ccd/codebook_schools_ccd_enrollment", [
        ("grade", ["grade"], "ccd var-defs grade encoding"),
        ("race", ["race"], "ccd var-defs race"),
        ("sex", ["sex"], "ccd var-defs sex"),
    ]),
    "crdc": ("crdc/codebook_schools_crdc_enrollment", [
        ("enrollment_crdc", ["enroll"], "crdc SKILL enrollment_crdc col name"),
        ("disability", ["disab", "idea", "504"], "crdc var-defs disability"),
        ("lep", ["english", "lep", "limited", "el "], "crdc var-defs lep/EL"),
    ]),
    "meps": ("meps/codebook_schools_meps", [
        ("meps_poverty_pct", ["poverty"], "meps var-defs meps_poverty_pct"),
        ("meps_poverty_se", ["error", "poverty", "se"], "meps var-defs se"),
        ("meps_poverty_ptl", ["percentile", "poverty", "ptl"], "meps var-defs percentile"),
    ]),
    "saipe": ("saipe/codebook_districts_saipe", [
        ("est_population_5_17_poverty_pct", ["poverty"], "saipe var-defs poverty pct (scale trap)"),
        ("est_population_total", ["population"], "saipe var-defs total population"),
        ("leaid", ["lea", "district", "id", "agency"], "saipe var-defs leaid"),
    ]),
    "edfacts": ("edfacts/codebook_schools_edfacts_assessments", [
        ("grade_edfacts", ["grade"], "edfacts SKILL grade_edfacts"),
        ("race", ["race"], "edfacts SKILL race"),
        ("read_test_pct_prof_midpt", ["proficient", "read", "midpoint", "percent", "prof"], "edfacts SKILL midpt"),
    ]),
    "csafety": ("csafety/codebook_colleges_csafety_hate_crimes", [
        ("bias", ["bias"], "csafety var-defs bias category"),
        ("crime_type", ["crime", "offense", "type"], "csafety var-defs crime_type"),
        ("total_hate_crimes", ["hate", "total"], "csafety hate-crimes.md total count col"),
    ]),
}

for src, (cbpath, checks) in PLAN.items():
    print(f"\n========== {src}: {cbpath}.xls ==========")
    try:
        cb = fetch_codebook(cbpath)
    except Exception as e:
        print(f"  DOWNLOAD/READ FAILED: {type(e).__name__}: {str(e)[:160]}")
        for var, kws, cite in checks:
            rec(f"{src}.{var} in codebook ({cite})", "codebook unreadable", "UNTESTABLE")
        continue
    vcol = find_col(cb, "variable", "varname", "name", "field")
    lcol = find_col(cb, "label", "description", "definition", "desc")
    if vcol is None:  # fall back to first column
        vcol = cb.columns[0]
    print(f"  codebook shape={cb.shape}; columns={cb.columns}; var_col='{vcol}'; label_col='{lcol}'")
    # Print every (variable,label) row for audit evidence
    names = [str(x) for x in cb[vcol].to_list()]
    labels = [str(x) for x in cb[lcol].to_list()] if lcol else [""] * len(names)
    name_set = set(n.strip().lower() for n in names)
    print("  --- codebook rows (variable | label) ---")
    for n, lb in zip(names, labels):
        print(f"    {n} | {lb[:90]}")
    # Verdicts
    for var, kws, cite in checks:
        vl = var.lower()
        if vl in name_set:
            idx = next(i for i, n in enumerate(names) if n.strip().lower() == vl)
            lbl = labels[idx].lower()
            kw_hit = [k for k in kws if k in lbl]
            if kw_hit:
                rec(f"{src}.{var} present w/ corroborating label ({cite})",
                    f"label='{labels[idx][:70]}' matched={kw_hit}", "VERIFIED")
            else:
                rec(f"{src}.{var} present but label lacks expected keywords {kws} ({cite})",
                    f"label='{labels[idx][:70]}'", "PRESENT-LABEL-DIFFERS")
        else:
            rec(f"{src}.{var} documented name MISSING from codebook ({cite})",
                f"not in {len(names)} codebook vars", "CONTRADICTED")

print("\n### CODEBOOK CLAIM INVENTORY = 18 (3 per source x 6 sources) ###")
print("### TALLY ###")
for k, v in Counter(v for _, _, v in results).items():
    print(f"  {k}: {v}")
print("DONE 33")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:21:33
# Command: python3 /daaf/scripts/mirror_maintenance/33_codebook-crosschecks.py
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# 
# ========== ccd: ccd/codebook_schools_ccd_enrollment.xls ==========
#   codebook shape=(9, 3); columns=['variable', 'format', 'label']; var_col='variable'; label_col='label'
#   --- codebook rows (variable | label) ---
#     year | Academic year (fall semester)
#     ncessch | National Center for Education Statistics (NCES) identification number
#     ncessch_num | National Center for Education Statistics (NCES) identification number (numeric)
#     leaid | Local education agency identification number (NCES)
#     fips | Federal Information Processing Standards state code
#     grade | Grade
#     race | Race/ethnicity
#     sex | Sex
#     enrollment | Student enrollment
#     [VERIFIED] ccd.grade present w/ corroborating label (ccd var-defs grade encoding) -> label='Grade' matched=['grade']
#     [VERIFIED] ccd.race present w/ corroborating label (ccd var-defs race) -> label='Race/ethnicity' matched=['race']
#     [VERIFIED] ccd.sex present w/ corroborating label (ccd var-defs sex) -> label='Sex' matched=['sex']
# 
# ========== crdc: crdc/codebook_schools_crdc_enrollment.xls ==========
#   codebook shape=(11, 3); columns=['variable', 'format', 'label']; var_col='variable'; label_col='label'
#   --- codebook rows (variable | label) ---
#     crdc_id | Office of Civil Rights school ID
#     year | Academic year (fall semester)
#     ncessch | National Center for Education Statistics (NCES) identification number
#     leaid | Local education agency identification number (NCES)
#     fips | Federal Information Processing Standards state code
#     sex | Student enrollment
#     race | Race/ethnicity
#     disability | Students with disabilities
#     lep | Students with limited English proficiency
#     enrollment_crdc | Student enrollment
#     psenrollment_crdc | Number of students enrolled in preschool programs
#     [VERIFIED] crdc.enrollment_crdc present w/ corroborating label (crdc SKILL enrollment_crdc col name) -> label='Student enrollment' matched=['enroll']
#     [VERIFIED] crdc.disability present w/ corroborating label (crdc var-defs disability) -> label='Students with disabilities' matched=['disab']
#     [VERIFIED] crdc.lep present w/ corroborating label (crdc var-defs lep/EL) -> label='Students with limited English proficiency' matched=['english', 'limited']
# 
# ========== meps: meps/codebook_schools_meps.xls ==========
#   codebook shape=(11, 3); columns=['variable', 'format', 'label']; var_col='variable'; label_col='label'
#   --- codebook rows (variable | label) ---
#     year | Academic year (fall semester)
#     ncessch | National Center for Education Statistics (NCES) identification number
#     ncessch_num | National Center for Education Statistics (NCES) identification number (numeric)
#     leaid | Local education agency identification number (NCES)
#     gleaid | Geographic local education agency identification number
#     fips | Federal Information Processing Standards state code
#     meps_poverty_pct | Estimated percentage of students living in poverty (MEPS)
#     meps_poverty_se | Standard error for estimated percentage of students living in poverty (MEPS)
#     meps_mod_poverty_pct | Modified estimated percentage of students living in poverty  (MEPS)
#     meps_poverty_ptl | Estimated national percentile of students living in poverty, weighted by enrollment (MEPS)
#     meps_mod_poverty_ptl | Modified estimated national percentile of students living in poverty, weighted by enrollme
#     [VERIFIED] meps.meps_poverty_pct present w/ corroborating label (meps var-defs meps_poverty_pct) -> label='Estimated percentage of students living in poverty (MEPS)' matched=['poverty']
#     [VERIFIED] meps.meps_poverty_se present w/ corroborating label (meps var-defs se) -> label='Standard error for estimated percentage of students living in poverty ' matched=['error', 'poverty']
#     [VERIFIED] meps.meps_poverty_ptl present w/ corroborating label (meps var-defs percentile) -> label='Estimated national percentile of students living in poverty, weighted ' matched=['percentile', 'poverty']
# 
# ========== saipe: saipe/codebook_districts_saipe.xls ==========
#   codebook shape=(10, 3); columns=['variable', 'format', 'label']; var_col='variable'; label_col='label'
#   --- codebook rows (variable | label) ---
#     leaid | Local education agency identification number (NCES)
#     year | Academic year (fall semester)
#     fips | Federal Information Processing Standards state code
#     district_id | District identification numbers reported in the US Census Small Area Income and Poverty Es
#     district_name | District names reported in the US Census Small Area Income and Poverty Estimates 
#     est_population_total | Estimated total population
#     est_population_5_17 | Estimated total population ages 5–17
#     est_population_5_17_pct | Share of population that is school age (ages 5–17) 
#     est_population_5_17_poverty | Estimated population ages 5–17 in poverty 
#     est_population_5_17_poverty_pct | Share of school-age population (ages 5–17) in poverty
#     [VERIFIED] saipe.est_population_5_17_poverty_pct present w/ corroborating label (saipe var-defs poverty pct (scale trap)) -> label='Share of school-age population (ages 5–17) in poverty' matched=['poverty']
#     [VERIFIED] saipe.est_population_total present w/ corroborating label (saipe var-defs total population) -> label='Estimated total population' matched=['population']
#     [VERIFIED] saipe.leaid present w/ corroborating label (saipe var-defs leaid) -> label='Local education agency identification number (NCES)' matched=['id', 'agency']
# 
# ========== edfacts: edfacts/codebook_schools_edfacts_assessments.xls ==========
#   codebook shape=(26, 3); columns=['variable', 'format', 'label']; var_col='variable'; label_col='label'
#   --- codebook rows (variable | label) ---
#     ncessch | National Center for Education Statistics (NCES) identification number
#     ncessch_num | National Center for Education Statistics (NCES) identification number (numeric)
#     year | Academic year (fall semester)
#     school_name | School name
#     leaid | Local education agency identification number (NCES)
#     leaid_num | Local education agency identification number (NCES) (numeric)
#     lea_name | Local education agency name
#     fips | Federal Information Processing Standards state code
#     grade_edfacts | Grade category (as reported in EDFacts)
#     race | Race/ethnicity
#     sex | Sex
#     lep | Students with limited English proficiency
#     homeless | Students who are homeless
#     migrant | Students who are migrants
#     disability | Students with disabilities
#     econ_disadvantaged | Students who are economically disadvantaged
#     foster_care | Students who are in foster care
#     military_connected | Students who are connected to the military
#     read_test_num_valid | Number of students who completed a reading or language arts assessment and for whom a prof
#     read_test_pct_prof_midpt | Midpoint of the range used to report the share of students scoring proficient on a reading
#     read_test_pct_prof_high | High end of the range used to report the share of students scoring proficient on a reading
#     read_test_pct_prof_low | Low end of the range used to report the share of students scoring proficient on a reading 
#     math_test_num_valid | Number of students who completed a mathematics assessment and for whom a proficiency level
#     math_test_pct_prof_midpt | Midpoint of the range used to report the share of students scoring proficient on a mathema
#     math_test_pct_prof_high | High end of the range used to report the share of students scoring proficient on a mathema
#     math_test_pct_prof_low | Low end of the range used to report the share of students scoring proficient on a mathemat
#     [VERIFIED] edfacts.grade_edfacts present w/ corroborating label (edfacts SKILL grade_edfacts) -> label='Grade category (as reported in EDFacts)' matched=['grade']
#     [VERIFIED] edfacts.race present w/ corroborating label (edfacts SKILL race) -> label='Race/ethnicity' matched=['race']
#     [VERIFIED] edfacts.read_test_pct_prof_midpt present w/ corroborating label (edfacts SKILL midpt) -> label='Midpoint of the range used to report the share of students scoring pro' matched=['proficient', 'read', 'midpoint', 'prof']
# 
# ========== csafety: csafety/codebook_colleges_csafety_hate_crimes.xls ==========
#   codebook shape=(7, 3); columns=['variable', 'format', 'label']; var_col='variable'; label_col='label'
#   --- codebook rows (variable | label) ---
#     bias | Group that was vicitimized by hate crime
#     on_campus_hate_crimes | Number of hate crimes committed on campus
#     residence_hall_hate_crimes | Number of hate crimes committed in residence halls
#     non_campus_hate_crimes | Number of hate crimes committed off campus
#     public_property_hate_crimes | Number of hate crimes committed on campus-related public property
#     other_hate_crimes | Number of hate crimes committed in other places
#     total_hate_crimes | Number of hate crimes committed
#     [PRESENT-LABEL-DIFFERS] csafety.bias present but label lacks expected keywords ['bias'] (csafety var-defs bias category) -> label='Group that was vicitimized by hate crime'
#     [CONTRADICTED] csafety.crime_type documented name MISSING from codebook (csafety var-defs crime_type) -> not in 7 codebook vars
#     [VERIFIED] csafety.total_hate_crimes present w/ corroborating label (csafety hate-crimes.md total count col) -> label='Number of hate crimes committed' matched=['hate']
# 
# ### CODEBOOK CLAIM INVENTORY = 18 (3 per source x 6 sources) ###
# ### TALLY ###
#   VERIFIED: 16
#   PRESENT-LABEL-DIFFERS: 1
#   CONTRADICTED: 1
# DONE 33
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
