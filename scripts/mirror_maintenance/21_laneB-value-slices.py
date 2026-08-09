#!/usr/bin/env python3
# =============================================================================
# 21_laneB-value-slices.py  (Mirror V2 -> Urban live-API deep value comparison)
# =============================================================================
# INTENT: Lane B, part 2. For a bounded slice (one year + one state) of several
#   endpoint<->file pairs, fetch the SAME slice from (a) the live Urban API and
#   (b) the v2 mirror parquet, align on the primary key, and compare values
#   column-by-column after documented normalization. Also (i) repair the two
#   endpoint-slug 404s from script 20 (libraries, graduation-rates-200) and
#   (ii) diagnose the edfacts assessments grain mismatch by aligning keys.
#
# NORMALIZATION (each rule is an analytic decision):
#   * Missing codes: INTENT map API null and the Portal coded missings {-1,-2,-3}
#     (numeric or string form) to a single sentinel "<NA>". REASONING the drift
#     battery proved null<->coded re-encoding is the dominant BENIGN representation
#     difference; comparing raw would flag benign re-encodings as mismatches.
#     ASSUMES -1/-2/-3 are never legitimate data values in these columns (true for
#     Portal coded fields).
#   * IDs: INTENT compare ncessch/leaid/crdc_id/fips as zero-padded strings
#     (ncessch->12, leaid->7) and unitid as integer. REASONING the CSV/JSON path can
#     drop leading zeros; the mirror enforces fixed width. ASSUMES numeric-string ids.
#   * Numeric rep: INTENT if a column is numeric on both sides, compare as Float64
#     rounded to 4 dp. REASONING collapses int-vs-float representation of the same
#     value. ASSUMES no meaningful precision beyond 4 dp in these fields.
#   * Column-name casing: INTENT lowercase both column-name sets before intersecting.
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
UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"
MISS = "<NA>"                      # unified missing sentinel
CODED_MISSING = {"-1", "-2", "-3"}  # Portal standardized missing codes
PAD = {"ncessch": 12, "leaid": 7}   # zero-pad widths


# --- Helper: robust paginated GET; returns (list_of_result_dicts, count, err) ---
# INTENT: pull every page of a bounded API slice politely. REASONING: a one-state
#   slice is small (<~few thousand rows) but may span >1 page; follow `next`.
#   ASSUMES the API `next` link is absolute and valid. Caps pages defensively.
def api_get_all(url, max_pages=40):
    rows = []
    count = None
    pages = 0
    nxt = url
    while nxt and pages < max_pages:
        got = None
        for attempt in range(1, 4):
            try:
                req = urllib.request.Request(nxt, headers={"User-Agent": UA,
                                                           "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=90) as resp:
                    got = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                return rows, count, f"HTTP {e.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
                if attempt == 3:
                    return rows, count, f"unreachable: {repr(e)[:80]}"
                time.sleep(min(2 ** attempt, 20))
        if got is None:
            return rows, count, "no response"
        if count is None:
            count = got.get("count")
        rows.extend(got.get("results", []))
        nxt = got.get("next")
        pages += 1
        time.sleep(0.8)  # polite
    return rows, count, None


# --- Normalization helpers ---
def norm_missing_expr(col):
    # map null and coded-missing strings to the unified sentinel
    return (pl.when(pl.col(col).is_null() | pl.col(col).cast(pl.Utf8).is_in(list(CODED_MISSING)))
            .then(pl.lit(MISS)).otherwise(pl.col(col).cast(pl.Utf8)))


def build_norm(df, key, id_cols):
    # INTENT: produce an all-Utf8 normalized frame keyed by `key` for comparison.
    # REASONING: unify types across API(JSON) and mirror(parquet) so equality is
    #   representation-agnostic. ASSUMES key is unique after slice.
    exprs = []
    for c in df.columns:
        s = df[c]
        if c in PAD:
            # zero-padded id string; keep coded-missing as literal (not padded)
            e = (pl.when(pl.col(c).is_null())
                 .then(pl.lit(MISS))
                 .when(pl.col(c).cast(pl.Utf8).is_in(list(CODED_MISSING) + [""]))
                 .then(pl.lit(MISS))
                 .otherwise(pl.col(c).cast(pl.Utf8).str.replace(r"\.0$", "").str.zfill(PAD[c]))
                 .alias(c))
            exprs.append(e)
            continue
        # try numeric: if the column casts to Float64 for all non-missing, treat numeric
        non_missing = s.cast(pl.Utf8, strict=False).filter(
            ~(s.is_null() | s.cast(pl.Utf8, strict=False).is_in(list(CODED_MISSING))))
        numeric = False
        if non_missing.len() > 0:
            casted = non_missing.cast(pl.Float64, strict=False)
            numeric = casted.null_count() == 0
        if numeric:
            e = (pl.when(pl.col(c).is_null() | pl.col(c).cast(pl.Utf8).is_in(list(CODED_MISSING)))
                 .then(pl.lit(MISS))
                 .otherwise(pl.col(c).cast(pl.Float64).round(4).cast(pl.Utf8))
                 .alias(c))
        else:
            e = norm_missing_expr(c).str.strip_chars().alias(c)
        exprs.append(e)
    return df.select(exprs)


def compare_slice(label, api_url, mirror_rel, year, fips, key, disagg_match):
    rec = {"label": label, "api_url": api_url, "mirror_rel": mirror_rel,
           "year": year, "fips": fips, "key": key, "verdict": "", "detail": "",
           "n_keys_compared": 0, "cols_compared": 0, "cols_mismatch": 0,
           "cell_mismatch": 0}
    mf = TREE_DIR / mirror_rel
    if not mf.exists():
        rec["verdict"] = "UNVERIFIABLE"; rec["detail"] = "mirror file missing"
        return rec, []

    api_rows, api_count, err = api_get_all(api_url)
    if err or not api_rows:
        rec["verdict"] = "UNVERIFIABLE-TODAY"; rec["detail"] = f"API: {err or 'empty'}"
        return rec, []
    api = pl.from_dicts(api_rows)
    # lowercase column names on both sides
    api = api.rename({c: c.lower() for c in api.columns})

    lf = pl.scan_parquet(mf)
    names = [c.lower() for c in lf.collect_schema().names()]
    ren = {c: c.lower() for c in lf.collect_schema().names()}
    m = lf.rename(ren)
    preds = []
    if "year" in names:
        preds.append(pl.col("year").cast(pl.Int64, strict=False) == year)
    if "fips" in names:
        preds.append(pl.col("fips").cast(pl.Int64, strict=False) == fips)
    for c, v in (disagg_match or {}).items():
        if c in names:
            preds.append(pl.col(c).cast(pl.Utf8) == str(v))
    mir = m.filter(pl.all_horizontal(preds)).collect() if preds else m.collect()

    if key not in api.columns or key not in mir.columns:
        rec["verdict"] = "UNVERIFIABLE"; rec["detail"] = f"key {key} absent"
        return rec, []

    # shared value columns (exclude key); intersect on lowercased names
    shared = [c for c in api.columns if c in mir.columns and c != key]
    rec["cols_compared"] = len(shared)

    # normalize both, keyed
    keep = [key] + shared
    api_n = build_norm(api.select([c for c in keep if c in api.columns]), key, PAD)
    mir_n = build_norm(mir.select([c for c in keep if c in mir.columns]), key, PAD)

    # de-duplicate keys (some slices may repeat if grain mismatch) -> report if so
    api_keys = api_n[key].n_unique()
    mir_keys = mir_n[key].n_unique()
    if api_n.height != api_keys or mir_n.height != mir_keys:
        rec["detail"] += (f"[grain: api rows={api_n.height} keys={api_keys}; "
                          f"mir rows={mir_n.height} keys={mir_keys}] ")

    joined = api_n.join(mir_n, on=key, how="inner", suffix="__mir")
    rec["n_keys_compared"] = joined.height
    if joined.height == 0:
        rec["verdict"] = "UNVERIFIABLE"; rec["detail"] += "no overlapping keys"
        return rec, []

    examples = []
    cols_mm = 0
    cell_mm = 0
    for c in shared:
        mc = f"{c}__mir"
        if mc not in joined.columns:
            continue
        diff = joined.filter(pl.col(c) != pl.col(mc))
        if diff.height:
            cols_mm += 1
            cell_mm += diff.height
            for r in diff.head(3).iter_rows(named=True):
                examples.append({"label": label, "key": str(r[key]), "column": c,
                                 "api_value": r[c], "mirror_value": r[mc]})
    rec["cols_mismatch"] = cols_mm
    rec["cell_mismatch"] = cell_mm
    rec["verdict"] = "MATCH" if cell_mm == 0 else "MISMATCH"
    return rec, examples


# --- Endpoint-slug repair probes for the two script-20 404s ---
print("=== ENDPOINT REPAIR PROBES (script-20 404s) ===")
for label, cands in [
    ("ipeds_libraries", ["college-university/ipeds/academic-libraries/2020",
                          "college-university/ipeds/libraries/2018",
                          "college-university/ipeds/academic-libraries/2018"]),
    ("ipeds_gr200", ["college-university/ipeds/graduation-rates-200pct/2020",
                     "college-university/ipeds/graduation-rates-200/2018/race",
                     "college-university/ipeds/grad-rates-200/2020"]),
]:
    for cand in cands:
        u = f"{API_BASE}/{cand}/?fips=11"
        rows, count, err = api_get_all(u, max_pages=1)
        status = "OK" if not err else err
        print(f"[repair] {label}: {cand} -> {status} count={count}")
        if not err:
            break
        time.sleep(0.6)

# --- Deep value-slice comparisons (bounded: one year + one state) ---
# fips 11 = District of Columbia (small); fips 1 = Alabama (leading-zero id stress).
SLICES = [
    ("ipeds_directory", f"{API_BASE}/college-university/ipeds/directory/2022/?fips=11",
     "ipeds/colleges_ipeds_directory.parquet", 2022, 11, "unitid", None),
    ("saipe_al", f"{API_BASE}/school-districts/saipe/2021/?fips=1",
     "saipe/districts_saipe.parquet", 2021, 1, "leaid", None),
    ("ccd_sch_dir", f"{API_BASE}/schools/ccd/directory/2022/?fips=11",
     "ccd/schools_ccd_directory.parquet", 2022, 11, "ncessch", None),
    ("meps", f"{API_BASE}/schools/meps/2020/?fips=11",
     "meps/schools_meps.parquet", 2020, 11, "ncessch", None),
    ("fsa_grants", f"{API_BASE}/college-university/fsa/grants/2018/?fips=11",
     "fsa/colleges_fsa_grants.parquet", 2018, 11, "unitid", None),
    ("scorecard_instchar", f"{API_BASE}/college-university/scorecard/institutional-characteristics/2018/?fips=11",
     "scorecard/colleges_scorecard_inst_characteristics.parquet", 2018, 11, "unitid", None),
    ("ccd_dist_fin", f"{API_BASE}/school-districts/ccd/finance/2020/?fips=11",
     "ccd/districts_ccd_finance.parquet", 2020, 11, "leaid", None),
    ("crdc_sch_char", f"{API_BASE}/schools/crdc/directory/2020/?fips=11",
     "crdc/schools_crdc_school_characteristics.parquet", 2020, 11, "ncessch", None),
    # Diagnose the edfacts grain: align on ncessch for grade-99 all-students total slice.
    ("edfacts_assess_diag", f"{API_BASE}/schools/edfacts/assessments/2018/grade-99/?fips=11",
     "edfacts/schools_edfacts_assessments_2018.parquet", 2018, 11, "ncessch",
     None),  # disagg derived below from API first-result
]

print("\n=== DEEP VALUE SLICES ===")
all_recs = []
all_examples = []
for label, api_url, mirror_rel, year, fips, key, disagg in SLICES:
    # For edfacts, derive the disagg total codes from the API first result adaptively.
    dmatch = disagg
    if label == "edfacts_assess_diag":
        rows, count, err = api_get_all(api_url, max_pages=1)
        if rows:
            fr = {k.lower(): v for k, v in rows[0].items()}
            dmatch = {}
            for dc in ["grade_edfacts", "race", "sex", "disability", "lep"]:
                if dc in fr and fr[dc] is not None:
                    dmatch[dc] = fr[dc]
            print(f"[edfacts] adaptive disagg from API first-result: {dmatch}")
    rec, ex = compare_slice(label, api_url, mirror_rel, year, fips, key, dmatch)
    all_recs.append(rec)
    all_examples.extend(ex)
    print(f"[{label:20s}] {rec['verdict']:17s} keys={rec['n_keys_compared']} "
          f"cols={rec['cols_compared']} colMM={rec['cols_mismatch']} cellMM={rec['cell_mismatch']} "
          f"{rec['detail']}")

# --- Persist + summary ---
rec_df = pl.from_dicts(all_recs)
rec_df.write_parquet(OUT_DIR / "laneB_value_slices.parquet")
if all_examples:
    pl.from_dicts(all_examples).write_parquet(OUT_DIR / "laneB_value_mismatch_examples.parquet")

print("\n=== LANE B PART 2 SUMMARY ===")
print(rec_df.select("label", "verdict", "n_keys_compared", "cols_compared",
                    "cols_mismatch", "cell_mismatch"))
n_match = rec_df.filter(pl.col("verdict") == "MATCH").height
print(f"MATCH={n_match} / {rec_df.height} slices")
if all_examples:
    print("\n--- MISMATCH EXAMPLES (verbatim, capped 30) ---")
    for e in all_examples[:30]:
        print(f"  [{e['label']}] key={e['key']} col={e['column']} "
              f"api={e['api_value']!r} mirror={e['mirror_value']!r}")
print("\nLANE B PART 2 COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:17:09
# Command: python3 /daaf/scripts/mirror_maintenance/21_laneB-value-slices.py
# Duration: 87s
# Exit code: 0
#
# --- STDOUT ---
# === ENDPOINT REPAIR PROBES (script-20 404s) ===
# [repair] ipeds_libraries: college-university/ipeds/academic-libraries/2020 -> OK count=16
# [repair] ipeds_gr200: college-university/ipeds/graduation-rates-200pct/2020 -> HTTP 404 count=None
# [repair] ipeds_gr200: college-university/ipeds/graduation-rates-200/2018/race -> HTTP 404 count=None
# [repair] ipeds_gr200: college-university/ipeds/grad-rates-200/2020 -> HTTP 404 count=None
# 
# === DEEP VALUE SLICES ===
# [ipeds_directory     ] MISMATCH          keys=23 cols=95 colMM=1 cellMM=23 
# [saipe_al            ] MISMATCH          keys=140 cols=9 colMM=1 cellMM=2 
# [ccd_sch_dir         ] MISMATCH          keys=244 cols=51 colMM=1 cellMM=122 
# [meps                ] MATCH             keys=226 cols=10 colMM=0 cellMM=0 
# [fsa_grants          ] MISMATCH          keys=400 cols=12 colMM=6 cellMM=1304 [grain: api rows=80 keys=16; mir rows=80 keys=16] 
# [scorecard_instchar  ] MISMATCH          keys=24 cols=26 colMM=3 cellMM=72 
# [ccd_dist_fin        ] MISMATCH          keys=70 cols=162 colMM=35 cellMM=403 
# [crdc_sch_char       ] MISMATCH          keys=272 cols=34 colMM=19 cellMM=366 [grain: api rows=240 keys=234; mir rows=240 keys=234] 
# [edfacts] adaptive disagg from API first-result: {'grade_edfacts': 99, 'race': 99, 'sex': 99, 'disability': 99, 'lep': 99}
# [edfacts_assess_diag ] MISMATCH          keys=782 cols=25 colMM=12 cellMM=4737 [grain: api rows=214 keys=214; mir rows=782 keys=214] 
# 
# === LANE B PART 2 SUMMARY ===
# shape: (9, 6)
# ┌─────────────────────┬──────────┬─────────────────┬───────────────┬───────────────┬───────────────┐
# │ label               ┆ verdict  ┆ n_keys_compared ┆ cols_compared ┆ cols_mismatch ┆ cell_mismatch │
# │ ---                 ┆ ---      ┆ ---             ┆ ---           ┆ ---           ┆ ---           │
# │ str                 ┆ str      ┆ i64             ┆ i64           ┆ i64           ┆ i64           │
# ╞═════════════════════╪══════════╪═════════════════╪═══════════════╪═══════════════╪═══════════════╡
# │ ipeds_directory     ┆ MISMATCH ┆ 23              ┆ 95            ┆ 1             ┆ 23            │
# │ saipe_al            ┆ MISMATCH ┆ 140             ┆ 9             ┆ 1             ┆ 2             │
# │ ccd_sch_dir         ┆ MISMATCH ┆ 244             ┆ 51            ┆ 1             ┆ 122           │
# │ meps                ┆ MATCH    ┆ 226             ┆ 10            ┆ 0             ┆ 0             │
# │ fsa_grants          ┆ MISMATCH ┆ 400             ┆ 12            ┆ 6             ┆ 1304          │
# │ scorecard_instchar  ┆ MISMATCH ┆ 24              ┆ 26            ┆ 3             ┆ 72            │
# │ ccd_dist_fin        ┆ MISMATCH ┆ 70              ┆ 162           ┆ 35            ┆ 403           │
# │ crdc_sch_char       ┆ MISMATCH ┆ 272             ┆ 34            ┆ 19            ┆ 366           │
# │ edfacts_assess_diag ┆ MISMATCH ┆ 782             ┆ 25            ┆ 12            ┆ 4737          │
# └─────────────────────┴──────────┴─────────────────┴───────────────┴───────────────┴───────────────┘
# MATCH=1 / 9 slices
# 
# --- MISMATCH EXAMPLES (verbatim, capped 30) ---
#   [ipeds_directory] key=131159.0 col=duns api='' mirror='<NA>'
#   [ipeds_directory] key=131283.0 col=duns api='' mirror='<NA>'
#   [ipeds_directory] key=131399.0 col=duns api='' mirror='<NA>'
#   [saipe_al] key=0101200 col=est_population_5_17_pct api='0.1816' mirror='0.1817'
#   [saipe_al] key=0102430 col=est_population_5_17_pct api='0.1686' mirror='0.1685'
#   [ccd_sch_dir] key=110000800382 col=teachers_fte api='28.0' mirror='28.98'
#   [ccd_sch_dir] key=110000800478 col=teachers_fte api='24.0' mirror='24.96'
#   [ccd_sch_dir] key=110000800479 col=teachers_fte api='24.0' mirror='24.96'
#   [fsa_grants] key=131159.0 col=grant_type api='2.0' mirror='1.0'
#   [fsa_grants] key=131159.0 col=grant_type api='3.0' mirror='1.0'
#   [fsa_grants] key=131159.0 col=grant_type api='4.0' mirror='1.0'
#   [fsa_grants] key=131159.0 col=grant_recipients_opeid api='1353.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=grant_recipients_opeid api='2.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=grant_recipients_opeid api='1353.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=value_grants_disbursed_opeid api='6062687.27' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=value_grants_disbursed_opeid api='2806.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=value_grants_disbursed_opeid api='6062687.27' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=grant_recipients_unitid api='1353.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=grant_recipients_unitid api='2.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=grant_recipients_unitid api='1353.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=value_grants_disbursed_unitid api='6062687.5' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=value_grants_disbursed_unitid api='2806.0' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=value_grants_disbursed_unitid api='6062687.5' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=other_assoc_opeids api='' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=other_assoc_opeids api='' mirror='<NA>'
#   [fsa_grants] key=131159.0 col=other_assoc_opeids api='' mirror='<NA>'
#   [scorecard_instchar] key=131159.0 col=accreditor api='' mirror='<NA>'
#   [scorecard_instchar] key=131283.0 col=accreditor api='' mirror='<NA>'
#   [scorecard_instchar] key=131399.0 col=accreditor api='' mirror='<NA>'
#   [scorecard_instchar] key=131159.0 col=title_iv_approval_date api='' mirror='<NA>'
# 
# LANE B PART 2 COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
