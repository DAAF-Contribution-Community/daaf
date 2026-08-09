#!/usr/bin/env python3
# =============================================================================
# 20_laneB-api-count-sweep.py  (Mirror V2 -> Urban serving-surface consistency)
# =============================================================================
# INTENT: Lane B, part 1. Verify that the v2 mirror's per-year row counts agree
#   with the LIVE Urban Education Data Portal API's `count` field, for a broad
#   sweep of endpoint-year pairs spanning many sources (ccd, crdc, ipeds, saipe,
#   meps, edfacts, scorecard, fsa). Also verify the live API is still serving
#   Portal v0.26.1 (a newer live release would explain divergences and MUST be
#   reported, not silently absorbed).
#
# METHOD:
#   * Live API: GET https://educationdata.urban.org/api/v1/{level}/{source}/{topic}/{year}/[disagg]/
#     Read only the JSON `count` field (total across all pages) + the first result's
#     keys (to observe grain / disaggregation codes). First page only — cheap.
#   * Mirror: row count for that year read from the LOCAL build tree, which wave-2
#     remote validation proved byte-identical (497/497 sha256) to the HF pinned
#     revision 0ad00ce. REASONING: the local parquet IS the shipped mirror byte-for-
#     byte, so a local row count == the HF pinned file's row count; this avoids
#     multi-GB HTTP-parquet reads. ASSUMES the 497/497 proof holds — we additionally
#     spot-check 2 files directly against the HF pinned URL below to demonstrate it.
#   * For 1:1 endpoint<->file datasets (one row per entity per year) an exact count
#     match is expected. For files that aggregate multiple endpoint disaggregation
#     dimensions, the mirror filter is derived ADAPTIVELY from the API first-result's
#     disaggregation columns (grade/race/sex) so we compare like grain, and the
#     mapping used is recorded.
#
# Read-only network GETs. No installs. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import polars as pl
import urllib.request
import urllib.error
import json
import time
import datetime
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://educationdata.urban.org/api/v1"
HF_PIN = ("https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3"
          "/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa")
UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()


# --- Helper: robust GET returning parsed JSON (60s+ timeout, 3 retries, backoff) ---
# INTENT: fetch one API page politely. REASONING: Urban had a full outage 2026-08-06;
#   generous timeout + backoff tolerate a recovering/flaky API. ASSUMES JSON body.
def api_get_json(url):
    last = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                status = resp.status
                body = resp.read()
            return status, json.loads(body.decode("utf-8")), None
        except urllib.error.HTTPError as e:
            # 404 etc. are definitive answers about the endpoint, not transport errors.
            return e.code, None, f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            last = repr(e)
            time.sleep(min(2 ** attempt, 20))
    return None, None, f"unreachable after 3 tries: {last}"


# --- Version / health probe ---
# INTENT: confirm the live API is up and, if cheap, detect its Portal version so a
#   newer-than-v0.26.1 live release is surfaced. REASONING: the api-downloads manifest
#   and a directory ping are the cheapest signals. ASSUMES version may not be exposed
#   in JSON; treat as best-effort and record whatever is observable.
print("=== LIVE API HEALTH / VERSION PROBE ===")
health_url = f"{API_BASE}/college-university/ipeds/directory/2022/?fips=11"  # DC only: tiny page
hs, hj, herr = api_get_json(health_url)
if hj is not None:
    print(f"[health] {health_url}")
    print(f"[health] HTTP {hs}; count(DC 2022 directory)={hj.get('count')}; "
          f"first-result keys sample={list(hj['results'][0].keys())[:6] if hj.get('results') else 'NONE'}")
else:
    print(f"[health] FAILED: {herr}")

# Best-effort version sniff: the api-downloads manifest sometimes carries a version token.
ver_signal = "UNDETERMINED"
vs, vj, verr = api_get_json(f"{API_BASE}/api-downloads/")
if vj is not None:
    blob = json.dumps(vj)[:20000]
    for tok in ("0.26.1", "0.26", "0.27", "0.28", "v0.26", "v0.27"):
        if tok in blob:
            ver_signal = f"token '{tok}' present in api-downloads manifest"
            break
    print(f"[version] api-downloads reachable (HTTP {vs}); scan -> {ver_signal}")
else:
    print(f"[version] api-downloads probe inconclusive: {verr}")
print("[version] NOTE: Urban API does not expose an explicit Portal-version field in "
      "endpoint JSON; version is inferred from row-count agreement with the v0.26.1 "
      "mirror snapshot below. Systematic count divergence would signal a live re-release.")

# --- HF-pin equivalence spot check (prove local == HF pinned bytes for row counts) ---
# INTENT: demonstrate that reading counts from the local tree equals reading the HF
#   pinned file. REASONING: honors the task's serving-surface intent without bulk HTTP.
print("\n=== HF-PIN EQUIVALENCE SPOT CHECK (2 files) ===")
for rel in ["saipe/districts_saipe.parquet", "ipeds/colleges_ipeds_student-faculty-ratio.parquet"]:
    local_n = pl.scan_parquet(TREE_DIR / rel).select(pl.len()).collect().item()
    try:
        hf_n = pl.scan_parquet(f"{HF_PIN}/{rel}").select(pl.len()).collect().item()
        verdict = "MATCH" if hf_n == local_n else "MISMATCH"
        print(f"[hf-equiv] {rel}: local={local_n:,} hf_pinned={hf_n:,} -> {verdict}")
    except Exception as e:
        print(f"[hf-equiv] {rel}: local={local_n:,} hf_pinned=UNREACHABLE ({repr(e)[:80]})")

# --- Sweep table: (label, api_path, mirror_rel, year, grain, note) ---
# grain "1to1" => one row per entity per year, exact count match expected.
# grain "disagg" => file aggregates disaggregation dims; mirror filter derived
#   adaptively from the API first-result disaggregation columns (documented).
SWEEP = [
    # IPEDS (college-university) — institution-year grain, 1:1
    ("ipeds_directory", "college-university/ipeds/directory/2022",
     "ipeds/colleges_ipeds_directory.parquet", 2022, "1to1", "1 row/institution/year"),
    ("ipeds_inst_char", "college-university/ipeds/institutional-characteristics/2022",
     "ipeds/colleges_ipeds_institutional-characteristics.parquet", 2022, "1to1", "1 row/institution/year"),
    ("ipeds_admissions", "college-university/ipeds/admissions-enrollment/2020",
     "ipeds/colleges_ipeds_admissions-enrollment.parquet", 2020, "1to1", "1 row/institution/year"),
    ("ipeds_enroll_fte", "college-university/ipeds/enrollment-full-time-equivalent/2022",
     "ipeds/colleges_ipeds_enrollment-fte.parquet", 2022, "1to1", "endpoint enrollment-full-time-equivalent"),
    ("ipeds_stud_fac", "college-university/ipeds/student-faculty-ratio/2022",
     "ipeds/colleges_ipeds_student-faculty-ratio.parquet", 2022, "1to1", "1 row/institution/year"),
    ("ipeds_libraries", "college-university/ipeds/libraries/2022",
     "ipeds/colleges_ipeds_academic_libraries.parquet", 2022, "1to1", "endpoint libraries -> file academic_libraries"),
    # Scorecard
    ("scorecard_instchar", "college-university/scorecard/institutional-characteristics/2018",
     "scorecard/colleges_scorecard_inst_characteristics.parquet", 2018, "1to1", "1 row/institution/year"),
    ("scorecard_earnings", "college-university/scorecard/earnings/2013",
     "scorecard/colleges_scorecard_earnings.parquet", 2013, "disagg", "earnings has cohort dims; adaptive"),
    # FSA
    ("fsa_grants", "college-university/fsa/grants/2018",
     "fsa/colleges_fsa_grants.parquet", 2018, "1to1", "1 row/institution/year"),
    ("fsa_loans", "college-university/fsa/loans/2018",
     "fsa/colleges_fsa_loans.parquet", 2018, "1to1", "1 row/institution/year"),
    # CCD schools + districts
    ("ccd_sch_dir", "schools/ccd/directory/2022",
     "ccd/schools_ccd_directory.parquet", 2022, "1to1", "1 row/school/year"),
    ("ccd_dist_dir", "school-districts/ccd/directory/2022",
     "ccd/school-districts_lea_directory.parquet", 2022, "1to1", "1 row/district/year"),
    ("ccd_dist_fin", "school-districts/ccd/finance/2020",
     "ccd/districts_ccd_finance.parquet", 2020, "1to1", "1 row/district/year"),
    # SAIPE
    ("saipe", "school-districts/saipe/2021",
     "saipe/districts_saipe.parquet", 2021, "1to1", "1 row/district/year"),
    # MEPS
    ("meps", "schools/meps/2020",
     "meps/schools_meps.parquet", 2020, "1to1", "1 row/school/year"),
    # CRDC directory / school characteristics
    ("crdc_sch_char", "schools/crdc/directory/2020",
     "crdc/schools_crdc_school_characteristics.parquet", 2020, "1to1", "1 row/school/year (crdc dir)"),
    # EDFacts assessments (disaggregated by grade; API grade path segment)
    ("edfacts_assess", "schools/edfacts/assessments/2018/grade-99",
     "edfacts/schools_edfacts_assessments_2018.parquet", 2018, "disagg", "grade-99 total slice; adaptive"),
    # CCD enrollment (disaggregated by grade/race/sex; base grade endpoint = totals)
    ("ccd_sch_enroll", "schools/ccd/enrollment/2020/grade-99",
     "ccd/schools_ccd_enrollment_2020.parquet", 2020, "disagg", "grade-99 total; race/sex totals; adaptive"),
    # IPEDS grad-rates-200 (cohort dims)
    ("ipeds_gr200", "college-university/ipeds/graduation-rates-200/2020",
     "ipeds/colleges_ipeds_grad-rates-200pct.parquet", 2020, "disagg", "grad-rate cohort dims; adaptive"),
]

# --- Adaptive disaggregation-filter builder ---
# INTENT: for a disaggregated file, restrict the mirror to the same grain the API
#   base/slice endpoint returns, by matching the disaggregation columns present in
#   the API's first result to their observed value (e.g. grade=99, race=99, sex=99).
# REASONING: the mirror year-file carries every disaggregation combination; the API
#   slice returns exactly one combination per entity. ASSUMES the API first-result's
#   disaggregation code equals the code used throughout that slice (true for Urban's
#   fixed-grain endpoints). Documented per row in the output.
DISAGG_COLS = ["grade", "grade_edfacts", "race", "sex", "disability", "lep",
               "cohort", "cohort_years", "ftpt", "sector", "class_level"]

results = []
for label, api_path, mirror_rel, year, grain, note in SWEEP:
    url = f"{API_BASE}/{api_path}/"
    mf = TREE_DIR / mirror_rel
    row = {"label": label, "api_url": url, "mirror_rel": mirror_rel, "year": year,
           "grain": grain, "note": note, "api_count": None, "mirror_count": None,
           "applied_filter": "", "verdict": "", "detail": ""}

    if not mf.exists():
        row["verdict"] = "UNVERIFIABLE"
        row["detail"] = "mirror file missing locally"
        results.append(row)
        print(f"[{label:18s}] UNVERIFIABLE: mirror file missing {mirror_rel}")
        continue

    st, js, err = api_get_json(url)
    if js is None:
        row["verdict"] = "UNVERIFIABLE-TODAY"
        row["detail"] = f"API: {err}"
        results.append(row)
        print(f"[{label:18s}] UNVERIFIABLE-TODAY: {err}")
        time.sleep(1.0)
        continue

    api_count = js.get("count")
    row["api_count"] = api_count
    first = js["results"][0] if js.get("results") else {}

    lf = pl.scan_parquet(mf)
    schema_names = lf.collect_schema().names()
    preds = []
    filt_desc = []
    if "year" in schema_names:
        preds.append(pl.col("year") == year)
        filt_desc.append(f"year=={year}")

    if grain == "disagg":
        # Match every disaggregation column the API returns to its first-result value.
        for c in DISAGG_COLS:
            if c in schema_names and c in first and first[c] is not None:
                val = first[c]
                # cast comparison value to the column dtype domain via string match tolerance
                preds.append(pl.col(c).cast(pl.Utf8) == str(val))
                filt_desc.append(f"{c}=={val}")

    mirror_count = lf.filter(pl.all_horizontal(preds)).select(pl.len()).collect().item() if preds \
        else lf.select(pl.len()).collect().item()
    row["mirror_count"] = mirror_count
    row["applied_filter"] = " & ".join(filt_desc) if filt_desc else "(no filter)"

    if api_count == mirror_count:
        row["verdict"] = "MATCH"
    else:
        diff = (mirror_count - api_count) if (api_count is not None and mirror_count is not None) else None
        row["verdict"] = "MISMATCH"
        row["detail"] = f"api={api_count} mirror={mirror_count} diff(mirror-api)={diff}"
    results.append(row)
    print(f"[{label:18s}] {row['verdict']:9s} api={api_count} mirror={mirror_count} "
          f"filter=[{row['applied_filter']}]")
    time.sleep(1.2)  # polite pacing

# --- Persist + summary ---
res_df = pl.from_dicts(results)
res_df.write_parquet(OUT_DIR / "laneB_count_sweep.parquet")

print("\n=== LANE B COUNT SWEEP SUMMARY ===")
tally = res_df.group_by("verdict").len().sort("verdict")
print(tally)
n_match = res_df.filter(pl.col("verdict") == "MATCH").height
n_mism = res_df.filter(pl.col("verdict") == "MISMATCH").height
n_unv = res_df.filter(pl.col("verdict").str.starts_with("UNVERIFIABLE")).height
print(f"MATCH={n_match} MISMATCH={n_mism} UNVERIFIABLE={n_unv} of {res_df.height} pairs")
print(f"Version signal: {ver_signal}")
if n_mism:
    print("\n--- MISMATCH DETAIL ---")
    for r in res_df.filter(pl.col("verdict") == "MISMATCH").iter_rows(named=True):
        print(f"  {r['label']}: {r['detail']} | filter=[{r['applied_filter']}] | note={r['note']}")
print("\nLANE B PART 1 COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:13:01
# Command: python3 /daaf/scripts/mirror_maintenance/20_laneB-api-count-sweep.py
# Duration: 136s
# Exit code: 0
#
# --- STDOUT ---
# === LIVE API HEALTH / VERSION PROBE ===
# [health] https://educationdata.urban.org/api/v1/college-university/ipeds/directory/2022/?fips=11
# [health] HTTP 200; count(DC 2022 directory)=23; first-result keys sample=['year', 'unitid', 'inst_name', 'address', 'state_abbr', 'zip']
# [version] api-downloads reachable (HTTP 200); scan -> UNDETERMINED
# [version] NOTE: Urban API does not expose an explicit Portal-version field in endpoint JSON; version is inferred from row-count agreement with the v0.26.1 mirror snapshot below. Systematic count divergence would signal a live re-release.
# 
# === HF-PIN EQUIVALENCE SPOT CHECK (2 files) ===
# [hf-equiv] saipe/districts_saipe.parquet: local=382,099 hf_pinned=382,099 -> MATCH
# [hf-equiv] ipeds/colleges_ipeds_student-faculty-ratio.parquet: local=102,371 hf_pinned=102,371 -> MATCH
# [ipeds_directory   ] MATCH     api=6256 mirror=6256 filter=[year==2022]
# [ipeds_inst_char   ] MATCH     api=6138 mirror=6138 filter=[year==2022]
# [ipeds_admissions  ] MATCH     api=5967 mirror=5967 filter=[year==2020]
# [ipeds_enroll_fte  ] MATCH     api=17877 mirror=17877 filter=[year==2022]
# [ipeds_stud_fac    ] MATCH     api=5706 mirror=5706 filter=[year==2022]
# [ipeds_libraries   ] UNVERIFIABLE-TODAY: HTTP 404
# [scorecard_instchar] MATCH     api=6807 mirror=6807 filter=[year==2018]
# [scorecard_earnings] MATCH     api=21075 mirror=21075 filter=[year==2013]
# [fsa_grants        ] MATCH     api=25710 mirror=25710 filter=[year==2018]
# [fsa_loans         ] MATCH     api=67466 mirror=67466 filter=[year==2018]
# [ccd_sch_dir       ] MATCH     api=102268 mirror=102268 filter=[year==2022]
# [ccd_dist_dir      ] MATCH     api=19714 mirror=19714 filter=[year==2022]
# [ccd_dist_fin      ] MATCH     api=19554 mirror=19554 filter=[year==2020]
# [saipe             ] MATCH     api=13164 mirror=13164 filter=[year==2021]
# [meps              ] MATCH     api=94590 mirror=94590 filter=[year==2020]
# [crdc_sch_char     ] MATCH     api=97575 mirror=97575 filter=[year==2020]
# [edfacts_assess    ] MISMATCH  api=90376 mirror=343331 filter=[year==2018 & grade_edfacts==99 & race==99 & sex==99 & disability==99 & lep==99]
# [ccd_sch_enroll    ] MATCH     api=99310 mirror=99310 filter=[year==2020 & grade==99 & race==99 & sex==99]
# [ipeds_gr200       ] UNVERIFIABLE-TODAY: HTTP 404
# 
# === LANE B COUNT SWEEP SUMMARY ===
# shape: (3, 2)
# ┌────────────────────┬─────┐
# │ verdict            ┆ len │
# │ ---                ┆ --- │
# │ str                ┆ u32 │
# ╞════════════════════╪═════╡
# │ MATCH              ┆ 16  │
# │ MISMATCH           ┆ 1   │
# │ UNVERIFIABLE-TODAY ┆ 2   │
# └────────────────────┴─────┘
# MATCH=16 MISMATCH=1 UNVERIFIABLE=2 of 19 pairs
# Version signal: UNDETERMINED
# 
# --- MISMATCH DETAIL ---
#   edfacts_assess: api=90376 mirror=343331 diff(mirror-api)=252955 | filter=[year==2018 & grade_edfacts==99 & race==99 & sex==99 & disability==99 & lep==99] | note=grade-99 total slice; adaptive
# 
# LANE B PART 1 COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
