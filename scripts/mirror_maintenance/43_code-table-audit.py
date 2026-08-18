# --- Config ---
# INTENT: Audit all coded-value tables in variable-codes.md against (a) the
#   Portal's authoritative per-variable `values` metadata (from the varlist
#   surface captured in script 41) and (b) live observed distinct values for the
#   highest-value/contested variables. Classify each table's discrepancies as
#   CONTRADICTED (live value outside our documented set, or our documented code
#   provably absent from BOTH Portal metadata and live data) vs
#   DOCUMENTED-NOT-OBSERVED (our code absent from the probed subset — may be
#   subsetting or a legacy/unpopulated code).
# REASONING: The varlist `values` string is format-tied (global per data format),
#   so it CANNOT reveal per-source differences (CCD vs CRDC vs IPEDS vs EDFacts
#   race sets) — those require live data probes. Metadata handles stable federal
#   standards (FIPS, locale, Carnegie, grade) cheaply; live probes ground the
#   contested categoricals.
# ASSUMES: fips=11 (DC) yields tiny K-12 responses; fips=6 (CA) a ~700-row
#   directory slice sufficient to observe inst_control/sector/institution_level.
#   Live probes with count==0 across all candidate years/params are recorded as
#   PROBE-EMPTY (not a contradiction). ~1 req/sec pacing, 60s timeout, 3 retries.
import re
import time
import json
import urllib.request
import urllib.error
import polars as pl
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research/2026-08-06_FrameworkDev_MirrorV2Update"
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
INV_PATH = OUT_DIR / "41_variable_inventory.parquet"
OUT_PATH = OUT_DIR / "43_code_table_audit.parquet"
API = "https://educationdata.urban.org/api/v1"

# --- Load: Portal metadata varlist ---
inv = pl.read_parquet(INV_PATH)

def parse_values(vs):
    # INTENT: parse a Portal `values` string into {code:label}.
    # Format after JSON decode: '"1" : "Semester","2" : "Quarter",...'
    if vs is None:
        return {}
    out = {}
    for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]*)"', vs):
        out[m.group(1).strip()] = m.group(2).strip()
    return out

# INTENT: aggregate Portal-metadata code sets per variable (format-tied, so the
#   union across endpoints is the Portal's global definition). Exclude the
#   universal sentinels -1/-2/-3 when comparing substantive category codes.
SENTINELS = {"-1", "-2", "-3"}
def portal_codes(varname):
    rows = inv.filter(pl.col("variable") == varname).select("values").to_series().to_list()
    codes = {}
    for vs in rows:
        codes.update(parse_values(vs))
    return codes

def endpoints_for(varname):
    return (inv.filter(pl.col("variable") == varname)
            .select("endpoint_url").unique().to_series().to_list())

# --- Live probe helper ---
def get_json(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "daaf-audit/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(1.0)  # polite pacing ~1 req/sec
                return json.loads(r.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = str(e)
            time.sleep(1.5)
    return {"__error__": last}

def distinct_live(path_variants, colnames, fips):
    # INTENT: try candidate URL variants; return distinct observed values for the
    #   requested columns from the first variant returning rows.
    for path in path_variants:
        url = f"{API}{path}?fips={fips}"
        d = get_json(url)
        if "__error__" in d:
            continue
        results = d.get("results", [])
        if not results:
            continue
        observed = {c: sorted({str(row[c]) for row in results if c in row and row[c] is not None})
                    for c in colnames}
        return {"url": url, "count": d.get("count"), "observed": observed}
    return {"url": path_variants[0] if path_variants else None, "count": 0, "observed": {}}

# --- Our documented code sets (parsed from variable-codes.md, 2026-08-07) ---
# REASONING: hard-coded from the current file text (the fix pass corrected
#   institution_level and CCD race rows; we treat current text as the claim set).
DOC = {
    "grade":                {"-1","0","1","2","3","4","5","6","7","8","9","10","11","12","13","14","99"},
    "race_master":          {"1","2","3","4","5","6","7","8","9","20","99"},
    "race_ccd":             {"1","2","3","4","5","6","7","9","99"},
    "race_crdc":            {"1","2","3","4","5","6","7","99"},
    "race_ipeds":           {"1","2","3","4","5","6","7","8","9","99"},
    "race_edfacts":         {"1","2","3","4","5","6","7","99"},
    "sex":                  {"1","2","3","4","9","99"},
    "sex_k12":              {"1","2","99"},
    "school_level":         {"0","1","2","3","4"},
    "school_type":          {"1","2","3","4"},
    "urban_centric_locale": {"11","12","13","21","22","23","31","32","33","41","42","43"},
    "inst_control":         {"1","2","3"},
    "institution_level":    {"1","2","4"},   # our doc: "no code 3"
    "sector":               {"0","1","2","3","4","5","6","7","8","9"},
    "award_level":          {"1","2","3","4","5","6","7","8","9","10","11","12"},
    "disability":           {"0","1","99"},
    "econ":                 {"0","1","99"},
    "lep":                  {"0","1","99"},
    "missing":              {"-1","-2","-3","-4","-9"},
    "calendar_system":      {"1","2","3","4","5","6","7"},
    "attendance":           {"1","2","99"},
}

findings = []
def record(table, depth, method, doc_set, portal_set, live_set, notes):
    doc_sub = set(doc_set) - SENTINELS
    portal_sub = set(portal_set) - SENTINELS
    live_sub = set(live_set) - SENTINELS if live_set is not None else None
    doc_not_portal = sorted(doc_sub - portal_sub, key=lambda x: (len(x), x))
    portal_not_doc = sorted(portal_sub - doc_sub, key=lambda x: (len(x), x))
    if live_sub is not None:
        live_not_doc = sorted(live_sub - set(doc_set), key=lambda x: (len(x), x))
        doc_not_live = sorted(doc_sub - live_sub, key=lambda x: (len(x), x))
    else:
        live_not_doc, doc_not_live = [], []
    findings.append({
        "table": table,
        "verification_depth": depth,
        "method": method,
        "doc_codes": ",".join(sorted(doc_set, key=lambda x: (len(x), x))),
        "portal_meta_codes": ",".join(sorted(portal_set, key=lambda x: (len(x), x))) if portal_set else "",
        "live_observed_codes": ",".join(sorted(live_set, key=lambda x: (len(x), x))) if live_set else "",
        "doc_not_in_portal_meta": ",".join(doc_not_portal),
        "portal_meta_not_in_doc": ",".join(portal_not_doc),
        "live_value_not_in_doc": ",".join(live_not_doc),   # CONTRADICTED signal
        "doc_not_observed_live": ",".join(doc_not_live),
        "notes": notes,
    })

print("=== PORTAL METADATA CODE SETS (key variables) ===")
for v in ["race","sex","institution_level","inst_control","sector","calendar_system",
          "award_level","school_level","school_type","urban_centric_locale",
          "disability","lep","fips","grade"]:
    pc = portal_codes(v)
    eps = endpoints_for(v)
    print(f"\n{v}: {len(eps)} endpoints; portal codes ({len(pc)}): "
          f"{sorted(pc.keys(), key=lambda x:(len(x),x))}")
    if v in ("institution_level","calendar_system","sector","award_level"):
        print(f"   labels: {pc}")

# ---------------------------------------------------------------------------
# LIVE PROBES (contested / high-value)
# ---------------------------------------------------------------------------
print("\n=== LIVE PROBES ===")

# Race + sex by source (combined race/sex routes give both).
ccd = distinct_live([f"/schools/ccd/enrollment/{y}/grade-9/race/sex/" for y in (2020,2018,2016)],
                    ["race","sex"], 11)
print(f"CCD race/sex: {ccd['url']} count={ccd['count']} -> {ccd['observed']}")
crdc = distinct_live([f"/schools/crdc/enrollment/{y}/race/sex/" for y in (2017,2015,2020,2013,2011)],
                     ["race","sex"], 11)
print(f"CRDC race/sex: {crdc['url']} count={crdc['count']} -> {crdc['observed']}")
ipeds_rs = distinct_live(
    [f"/college-university/ipeds/fall-enrollment/{y}/{lv}/race/sex/"
     for y in (2021,2020,2022) for lv in (99,1,2)],
    ["race","sex"], 11)
print(f"IPEDS fall-enrollment race/sex: {ipeds_rs['url']} count={ipeds_rs['count']} -> {ipeds_rs['observed']}")
edf = distinct_live(
    [f"/schools/edfacts/assessments/{y}/{g}/race/" for y in (2018,2016,2019) for g in (9,8,99)],
    ["race"], 11)
print(f"EDFacts assessments race: {edf['url']} count={edf['count']} -> {edf['observed']}")

# IPEDS 2022 sex (codes 3/4 availability)
ipeds_sex22 = distinct_live(
    [f"/college-university/ipeds/fall-enrollment/{y}/{lv}/race/sex/"
     for y in (2022,) for lv in (99,1,2)],
    ["sex"], 11)
print(f"IPEDS 2022 sex: {ipeds_sex22['url']} count={ipeds_sex22['count']} -> {ipeds_sex22['observed']}")

# Directory slice (CA) -> inst_control, sector, institution_level distinct
directory = distinct_live(["/college-university/ipeds/directory/2022/"],
                          ["inst_control","sector","institution_level"], 6)
print(f"IPEDS directory 2022 CA: count={directory['count']} -> {directory['observed']}")

# institution_level=3 existence across years (settle the 'no code 3' claim)
il3 = {}
for y in (1990, 2004, 2022):
    d = get_json(f"{API}/college-university/ipeds/directory/{y}/?institution_level=3")
    il3[y] = d.get("count") if "__error__" not in d else d
print(f"institution_level=3 counts by year: {il3}")

# disability / lep distinct from CRDC discipline route
disab = distinct_live([f"/schools/crdc/discipline/{y}/disability/race/sex/" for y in (2017,2015,2020,2013)],
                      ["disability"], 11)
print(f"CRDC disability: {disab['url']} count={disab['count']} -> {disab['observed']}")

# Missing-code -4 / -9 presence anywhere in Portal metadata corpus
all_values = inv.select("values").to_series().to_list()
meta_neg_codes = set()
for vs in all_values:
    for c in parse_values(vs):
        if c.startswith("-"):
            meta_neg_codes.add(c)
print(f"All negative sentinel codes present in Portal metadata corpus: {sorted(meta_neg_codes)}")

# --- Build findings ---
# Metadata + live grounded tables:
race_ccd_live = set(ccd["observed"].get("race", []))
race_crdc_live = set(crdc["observed"].get("race", []))
race_ipeds_live = set(ipeds_rs["observed"].get("race", []))
race_edf_live = set(edf["observed"].get("race", []))
sex_ccd_live = set(ccd["observed"].get("sex", []))
sex_ipeds22_live = set(ipeds_sex22["observed"].get("sex", []))

pcodes_race = set(portal_codes("race").keys())
pcodes_sex = set(portal_codes("sex").keys())

record("race_master (main table)", "metadata+live-4-sources", "varlist+CCD/CRDC/IPEDS/EDFacts probes",
       DOC["race_master"], pcodes_race,
       race_ccd_live | race_crdc_live | race_ipeds_live | race_edf_live,
       "code 20 legacy; 8 IPEDS-only expected")
record("race_ccd", "live", ccd["url"] or "CCD probe", DOC["race_ccd"], pcodes_race, race_ccd_live, "")
record("race_crdc", "live", crdc["url"] or "CRDC probe", DOC["race_crdc"], pcodes_race, race_crdc_live, "")
record("race_ipeds", "live", ipeds_rs["url"] or "IPEDS probe", DOC["race_ipeds"], pcodes_race, race_ipeds_live, "")
record("race_edfacts", "live", edf["url"] or "EDFacts probe", DOC["race_edfacts"], pcodes_race, race_edf_live, "")
record("sex (master)", "metadata+live", "varlist + CCD/IPEDS", DOC["sex"], pcodes_sex,
       sex_ccd_live | sex_ipeds22_live, "codes 3/4 IPEDS 2022+")
record("sex_k12 (CCD)", "live", ccd["url"] or "CCD", DOC["sex_k12"], pcodes_sex, sex_ccd_live, "")
record("institution_level", "metadata+live-3yr",
       "varlist + directory + il=3 probe 1990/2004/2022",
       DOC["institution_level"], set(portal_codes("institution_level").keys()),
       set(directory["observed"].get("institution_level", [])),
       f"Portal metadata DEFINES code 3 (Less than four years); live count(il=3)={il3}")
record("inst_control", "metadata+live", "varlist + directory CA",
       DOC["inst_control"], set(portal_codes("inst_control").keys()),
       set(directory["observed"].get("inst_control", [])), "")
record("sector", "metadata+live", "varlist + directory CA",
       DOC["sector"], set(portal_codes("sector").keys()),
       set(directory["observed"].get("sector", [])), "")
record("disability", "metadata+live", disab["url"] or "CRDC",
       DOC["disability"], set(portal_codes("disability").keys()),
       set(disab["observed"].get("disability", [])), "")
record("calendar_system", "metadata", "varlist only (stable)",
       DOC["calendar_system"], set(portal_codes("calendar_system").keys()), None,
       f"endpoints carrying var: {len(endpoints_for('calendar_system'))}")
record("award_level", "metadata", "varlist only (stable federal)",
       DOC["award_level"], set(portal_codes("award_level").keys()), None,
       f"endpoints carrying var: {len(endpoints_for('award_level'))}")
record("school_level", "metadata", "varlist only",
       DOC["school_level"], set(portal_codes("school_level").keys()), None, "")
record("school_type", "metadata", "varlist only",
       DOC["school_type"], set(portal_codes("school_type").keys()), None, "")
record("urban_centric_locale", "metadata", "varlist only (stable federal)",
       DOC["urban_centric_locale"], set(portal_codes("urban_centric_locale").keys()), None, "")
record("grade", "metadata+prior-live", "varlist + wave3 grade=-1 pk",
       DOC["grade"], set(portal_codes("grade").keys()), None, "")
record("fips", "metadata-sample (stable federal)", "varlist only",
       {"1","2","6","11","48","72","99"}, set(portal_codes("fips").keys()), None,
       "spot subset only; full 50-state+territory table treated as federal standard")
record("missing_codes", "metadata-corpus", "scan all `values`",
       DOC["missing"], meta_neg_codes, None,
       "Portal metadata sentinels are the observed set; our -4/-9 beyond it")
record("lep", "metadata", "varlist only",
       DOC["lep"], set(portal_codes("lep").keys()), None, "")

audit = pl.DataFrame(findings)

# --- Validate ---
assert audit.height >= 18, "Fewer tables audited than expected"
print("\n=== CODE TABLE AUDIT SUMMARY ===")
for r in audit.iter_rows(named=True):
    flag = "CONTRADICTED" if r["live_value_not_in_doc"] else (
        "DOC>PORTAL" if r["doc_not_in_portal_meta"] else "OK/subset")
    print(f"\n[{flag}] {r['table']}  (depth={r['verification_depth']})")
    print(f"   doc={r['doc_codes']}")
    if r["portal_meta_codes"]:
        print(f"   portal_meta={r['portal_meta_codes']}")
    if r["live_observed_codes"]:
        print(f"   live={r['live_observed_codes']}")
    if r["live_value_not_in_doc"]:
        print(f"   *** LIVE-VALUE-NOT-IN-DOC (CONTRADICTED): {r['live_value_not_in_doc']}")
    if r["doc_not_in_portal_meta"]:
        print(f"   DOC-CODE-NOT-IN-PORTAL-META: {r['doc_not_in_portal_meta']}")
    if r["doc_not_observed_live"]:
        print(f"   DOC-NOT-OBSERVED-LIVE: {r['doc_not_observed_live']}")
    if r["notes"]:
        print(f"   note: {r['notes']}")

# --- Save ---
audit.write_parquet(OUT_PATH)
print(f"\nSaved: {OUT_PATH} ({audit.shape})")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:21:37
# Command: python3 /daaf/scripts/mirror_maintenance/43_code-table-audit.py
# Duration: 115s
# Exit code: 0
#
# --- STDOUT ---
# === PORTAL METADATA CODE SETS (key variables) ===
# 
# race: 63 endpoints; portal codes (14): ['1', '2', '3', '4', '5', '6', '7', '8', '9', '-1', '-2', '-3', '20', '99']
# 
# sex: 64 endpoints; portal codes (8): ['1', '2', '3', '9', '-1', '-2', '-3', '99']
# 
# institution_level: 4 endpoints; portal codes (7): ['1', '2', '3', '4', '-1', '-2', '-3']
#    labels: {'1': "Less than two years (below associate's)", '2': 'At least two but less than four years', '3': 'Less than four years', '4': 'Four or more years', '-1': 'Missing/not reported', '-2': 'Not applicable', '-3': 'Suppressed data'}
# 
# inst_control: 1 endpoints; portal codes (6): ['1', '2', '3', '-1', '-2', '-3']
# 
# sector: 1 endpoints; portal codes (13): ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-1', '-2', '-3']
#    labels: {'0': 'Administrative unit', '1': 'Public, four-year or above', '2': 'Private not-for-profit, four-year or above', '3': 'Private for-profit, four-year or above', '4': 'Public, two-year', '5': 'Private not-for-profit, two-year', '6': 'Private for-profit, two-year', '7': 'Public, less-than two-year', '8': 'Private not-for-profit, less-than-two-year', '9': 'Private for-profit, less-than-two-year', '-1': 'Sector unknown (not active)', '-2': 'Not applicable', '-3': 'Suppressed data'}
# 
# calendar_system: 1 endpoints; portal codes (10): ['1', '2', '3', '4', '5', '6', '7', '-1', '-2', '-3']
#    labels: {'1': 'Semester', '2': 'Quarter', '3': 'Trimester', '4': 'Four-one-four plan', '5': 'Other academic year', '6': 'Differs by program', '7': 'Continuous', '-1': 'Missing/not reported', '-2': 'Not applicable', '-3': 'Suppressed data'}
# 
# award_level: 2 endpoints; portal codes (22): ['1', '2', '3', '4', '5', '6', '7', '8', '9', '-1', '-2', '-3', '20', '21', '22', '23', '24', '30', '31', '32', '33', '99']
#    labels: {'1': 'Award of less than one academic year', '2': 'Award of less than two academic years', '3': 'Award of at least one but less than two academic years', '4': "Associate's degree", '5': 'Award of at least one but less than four academic years', '6': 'Award of at least two but less than four academic years', '7': "Bachelor's degree", '8': "Postbaccalaureate or post-master's certificate", '9': "Master's degree", '20': "Doctor's degree (until 2008)", '21': 'First-professional degree (until 2008)', '22': "Doctor's degree, research/scholarship (starting 2007)", '23': "Doctor's degree, professional practice (starting 2007)", '24': "Doctor's degree, other (starting 2007)", '30': 'Certificate of less than 12 weeks', '31': 'Certificates of at least 12 weeks but less than 1 year', '32': 'Certificate of at least 1 year but less than 2 years', '33': 'Certificate of at least 2 years but less than 4 years', '99': 'Total', '-1': 'Missing/not reported', '-2': 'Not applicable', '-3': 'Suppressed data'}
# 
# school_level: 1 endpoints; portal codes (11): ['0', '1', '2', '3', '4', '5', '6', '7', '-1', '-2', '-3']
# 
# school_type: 1 endpoints; portal codes (8): ['1', '2', '3', '4', '5', '-1', '-2', '-3']
# 
# urban_centric_locale: 3 endpoints; portal codes (24): ['1', '2', '3', '4', '5', '6', '7', '8', '9', '-1', '-2', '-3', '11', '12', '13', '21', '22', '23', '31', '32', '33', '41', '42', '43']
# 
# disability: 51 endpoints; portal codes (9): ['0', '1', '2', '3', '4', '-1', '-2', '-3', '99']
# 
# lep: 49 endpoints; portal codes (5): ['1', '-1', '-2', '-3', '99']
# 
# fips: 129 endpoints; portal codes (83): ['1', '2', '3', '4', '5', '6', '7', '8', '9', '-1', '-2', '-3', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '50', '51', '52', '53', '54', '55', '56', '58', '59', '60', '61', '63', '64', '65', '66', '67', '68', '69', '70', '71', '72', '74', '75', '76', '78', '79', '81', '84', '86', '89', '95']
# 
# grade: 11 endpoints; portal codes (19): ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-1', '10', '11', '12', '13', '14', '15', '99', '999']
# 
# === LIVE PROBES ===
# CCD race/sex: https://educationdata.urban.org/api/v1/schools/ccd/enrollment/2020/grade-9/race/sex/?fips=11 count=1161 -> {'race': ['1', '2', '3', '4', '5', '6', '7', '9', '99'], 'sex': ['1', '2', '9', '99']}
# CRDC race/sex: https://educationdata.urban.org/api/v1/schools/crdc/enrollment/2017/race/sex/?fips=11 count=5472 -> {'race': ['1', '2', '3', '4', '5', '6', '7', '99'], 'sex': ['1', '2', '99']}
# IPEDS fall-enrollment race/sex: https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/2021/99/race/sex/?fips=11 count=1860 -> {'race': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '99'], 'sex': ['1', '2', '99']}
# EDFacts assessments race: /schools/edfacts/assessments/2018/9/race/ count=0 -> {}
# IPEDS 2022 sex: https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/2022/99/race/sex/?fips=11 count=2048 -> {'sex': ['1', '2', '3', '4', '99']}
# IPEDS directory 2022 CA: count=692 -> {'inst_control': ['1', '2', '3'], 'sector': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'], 'institution_level': ['1', '2', '4']}
# institution_level=3 counts by year: {1990: 0, 2004: 0, 2022: 0}
# CRDC disability: https://educationdata.urban.org/api/v1/schools/crdc/discipline/2017/disability/race/sex/?fips=11 count=17100 -> {'disability': ['0', '1', '2', '99']}
# All negative sentinel codes present in Portal metadata corpus: ['-1', '-2', '-3', '-99']
# 
# === CODE TABLE AUDIT SUMMARY ===
# 
# [OK/subset] race_master (main table)  (depth=metadata+live-4-sources)
#    doc=1,2,3,4,5,6,7,8,9,20,99
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,20,99
#    live=1,2,3,4,5,6,7,8,9,99
#    DOC-NOT-OBSERVED-LIVE: 20
#    note: code 20 legacy; 8 IPEDS-only expected
# 
# [OK/subset] race_ccd  (depth=live)
#    doc=1,2,3,4,5,6,7,9,99
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,20,99
#    live=1,2,3,4,5,6,7,9,99
# 
# [OK/subset] race_crdc  (depth=live)
#    doc=1,2,3,4,5,6,7,99
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,20,99
#    live=1,2,3,4,5,6,7,99
# 
# [OK/subset] race_ipeds  (depth=live)
#    doc=1,2,3,4,5,6,7,8,9,99
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,20,99
#    live=1,2,3,4,5,6,7,8,9,99
# 
# [OK/subset] race_edfacts  (depth=live)
#    doc=1,2,3,4,5,6,7,99
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,20,99
#    DOC-NOT-OBSERVED-LIVE: 1,2,3,4,5,6,7,99
# 
# [DOC>PORTAL] sex (master)  (depth=metadata+live)
#    doc=1,2,3,4,9,99
#    portal_meta=1,2,3,9,-1,-2,-3,99
#    live=1,2,3,4,9,99
#    DOC-CODE-NOT-IN-PORTAL-META: 4
#    note: codes 3/4 IPEDS 2022+
# 
# [CONTRADICTED] sex_k12 (CCD)  (depth=live)
#    doc=1,2,99
#    portal_meta=1,2,3,9,-1,-2,-3,99
#    live=1,2,9,99
#    *** LIVE-VALUE-NOT-IN-DOC (CONTRADICTED): 9
# 
# [OK/subset] institution_level  (depth=metadata+live-3yr)
#    doc=1,2,4
#    portal_meta=1,2,3,4,-1,-2,-3
#    live=1,2,4
#    note: Portal metadata DEFINES code 3 (Less than four years); live count(il=3)={1990: 0, 2004: 0, 2022: 0}
# 
# [OK/subset] inst_control  (depth=metadata+live)
#    doc=1,2,3
#    portal_meta=1,2,3,-1,-2,-3
#    live=1,2,3
# 
# [OK/subset] sector  (depth=metadata+live)
#    doc=0,1,2,3,4,5,6,7,8,9
#    portal_meta=0,1,2,3,4,5,6,7,8,9,-1,-2,-3
#    live=0,1,2,3,4,5,6,7,8,9
# 
# [CONTRADICTED] disability  (depth=metadata+live)
#    doc=0,1,99
#    portal_meta=0,1,2,3,4,-1,-2,-3,99
#    live=0,1,2,99
#    *** LIVE-VALUE-NOT-IN-DOC (CONTRADICTED): 2
# 
# [OK/subset] calendar_system  (depth=metadata)
#    doc=1,2,3,4,5,6,7
#    portal_meta=1,2,3,4,5,6,7,-1,-2,-3
#    note: endpoints carrying var: 1
# 
# [DOC>PORTAL] award_level  (depth=metadata)
#    doc=1,2,3,4,5,6,7,8,9,10,11,12
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,20,21,22,23,24,30,31,32,33,99
#    DOC-CODE-NOT-IN-PORTAL-META: 10,11,12
#    note: endpoints carrying var: 2
# 
# [OK/subset] school_level  (depth=metadata)
#    doc=0,1,2,3,4
#    portal_meta=0,1,2,3,4,5,6,7,-1,-2,-3
# 
# [OK/subset] school_type  (depth=metadata)
#    doc=1,2,3,4
#    portal_meta=1,2,3,4,5,-1,-2,-3
# 
# [OK/subset] urban_centric_locale  (depth=metadata)
#    doc=11,12,13,21,22,23,31,32,33,41,42,43
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,11,12,13,21,22,23,31,32,33,41,42,43
# 
# [OK/subset] grade  (depth=metadata+prior-live)
#    doc=0,1,2,3,4,5,6,7,8,9,-1,10,11,12,13,14,99
#    portal_meta=0,1,2,3,4,5,6,7,8,9,-1,10,11,12,13,14,15,99,999
# 
# [DOC>PORTAL] fips  (depth=metadata-sample (stable federal))
#    doc=1,2,6,11,48,72,99
#    portal_meta=1,2,3,4,5,6,7,8,9,-1,-2,-3,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,58,59,60,61,63,64,65,66,67,68,69,70,71,72,74,75,76,78,79,81,84,86,89,95
#    DOC-CODE-NOT-IN-PORTAL-META: 99
#    note: spot subset only; full 50-state+territory table treated as federal standard
# 
# [DOC>PORTAL] missing_codes  (depth=metadata-corpus)
#    doc=-1,-2,-3,-4,-9
#    portal_meta=-1,-2,-3,-99
#    DOC-CODE-NOT-IN-PORTAL-META: -4,-9
#    note: Portal metadata sentinels are the observed set; our -4/-9 beyond it
# 
# [DOC>PORTAL] lep  (depth=metadata)
#    doc=0,1,99
#    portal_meta=1,-1,-2,-3,99
#    DOC-CODE-NOT-IN-PORTAL-META: 0
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/43_code_table_audit.parquet ((20, 11))
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
