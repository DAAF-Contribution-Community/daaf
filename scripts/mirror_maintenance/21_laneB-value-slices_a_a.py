#!/usr/bin/env python3
# =============================================================================
# 21_laneB-value-slices_a.py  (revision of 21_laneB-value-slices.py)
# =============================================================================
# INTENT: Lane B, part 2 (revised). Deep value comparison of live-API slices vs
#   the v2 mirror parquet, aligned on the CORRECT grain key, with representation-
#   robust normalization. Fixes to the v1 harness (v1 preserved with its log):
#     FIX-1 empty-string "" from the API is a missing representation -> unify with
#           null and coded {-1,-2,-3} to a common sentinel (v1 flagged ''-vs-null).
#     FIX-2 composite grain keys where the primary id is not unique per year+state:
#           fsa_grants -> (unitid, grant_type); crdc_sch_char -> crdc_id;
#           edfacts total slice -> also constrain every special-population dim to 99.
#     FIX-3 numeric columns compared with tolerance (|a-b| <= max(0.01, 1e-4*|v|))
#           instead of 4-dp string equality, so benign precision (e.g. saipe pct
#           0.1816 vs 0.1817) is not a mismatch while real gaps (28.0 vs 28.98) are.
#   A residual MISMATCH after these fixes is a substantive API<->mirror value
#   difference and is reported verbatim with keys.
#
# NORMALIZATION (each an analytic decision):
#   * Missing: null, "", and coded {-1,-2,-3} -> unified missing. REASONING drift
#     battery proved null<->coded re-encoding (and now empty-string) is the dominant
#     BENIGN representation difference. ASSUMES these are never real values here.
#   * IDs: ncessch->12 / leaid->7 zero-padded strings; unitid/crdc_id compared as
#     their canonical string. REASONING JSON/CSV can drop leading zeros.
#   * Numeric: tolerance compare (see FIX-3). Column-name casing: lowercase both.
#
# Read-only network GETs. No installs. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import polars as pl
import urllib.request
import urllib.error
import json
import time
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://educationdata.urban.org/api/v1"
UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"
MISS = "<NA>"
MISSING_TOKENS = {"-1", "-2", "-3", "", "-1.0", "-2.0", "-3.0"}
PAD = {"ncessch": 12, "leaid": 7}
EDFACTS_TOTAL_DIMS = ["grade_edfacts", "race", "sex", "lep", "homeless", "migrant",
                      "disability", "econ_disadvantaged", "foster_care", "military_connected"]


def api_get_all(url, max_pages=40):
    rows, count, pages, nxt = [], None, 0, url
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
        time.sleep(0.8)
    return rows, count, None


# --- Typed normalization: classify each column numeric vs string, unify missing ---
# INTENT: yield, per column, a numeric value (or null) OR a normalized string, so
#   comparison uses tolerance for numeric and exact for string. REASONING:
#   representation-agnostic comparison across JSON vs parquet. ASSUMES missing tokens
#   are never legitimate values.
def str_missing_expr(col):
    return pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars().is_in(list(MISSING_TOKENS)) | \
           pl.col(col).is_null()


def normalize_frame(df):
    out = {}
    schema_str = {}
    for c in df.columns:
        # FIX: evaluate the missing mask as a Series (not an Expr) so Series.filter works.
        miss = df.select(str_missing_expr(c).alias("m"))["m"]
        s = df[c].cast(pl.Utf8, strict=False).str.strip_chars()
        if c in PAD:
            padded = (pl.when(str_missing_expr(c)).then(pl.lit(None))
                      .otherwise(pl.col(c).cast(pl.Utf8).str.replace(r"\.0$", "").str.zfill(PAD[c])))
            out[c] = df.select(padded.alias(c))[c]
            schema_str[c] = "id"
            continue
        non_missing = s.filter(~miss)
        numeric = non_missing.len() > 0 and non_missing.cast(pl.Float64, strict=False).null_count() == 0
        if numeric:
            val = (pl.when(str_missing_expr(c)).then(pl.lit(None)).otherwise(pl.col(c).cast(pl.Float64, strict=False)))
            out[c] = df.select(val.alias(c))[c]
            schema_str[c] = "num"
        else:
            val = (pl.when(str_missing_expr(c)).then(pl.lit(MISS)).otherwise(s))
            out[c] = df.select(val.alias(c))[c]
            schema_str[c] = "str"
    return pl.DataFrame(out), schema_str


def compare_slice(label, api_url, mirror_rel, year, fips, keys, disagg_match):
    rec = {"label": label, "mirror_rel": mirror_rel, "year": year, "fips": fips,
           "keys": "+".join(keys), "verdict": "", "detail": "",
           "n_keys_compared": 0, "cols_compared": 0, "cols_mismatch": 0, "cell_mismatch": 0}
    mf = TREE_DIR / mirror_rel
    if not mf.exists():
        rec["verdict"] = "UNVERIFIABLE"; rec["detail"] = "mirror file missing"; return rec, []

    api_rows, api_count, err = api_get_all(api_url)
    if err or not api_rows:
        rec["verdict"] = "UNVERIFIABLE-TODAY"; rec["detail"] = f"API: {err or 'empty'}"; return rec, []
    api = pl.from_dicts(api_rows).rename(lambda c: c.lower())

    lf = pl.scan_parquet(mf)
    orig_names = lf.collect_schema().names()
    m = lf.rename({c: c.lower() for c in orig_names})
    names = [c.lower() for c in orig_names]
    preds = []
    if "year" in names:
        preds.append(pl.col("year").cast(pl.Int64, strict=False) == year)
    if "fips" in names:
        preds.append(pl.col("fips").cast(pl.Int64, strict=False) == fips)
    for c, v in (disagg_match or {}).items():
        if c in names:
            preds.append(pl.col(c).cast(pl.Int64, strict=False) == int(v))
    mir = m.filter(pl.all_horizontal(preds)).collect() if preds else m.collect()

    keys = [k for k in keys if k in api.columns and k in mir.columns]
    if not keys:
        rec["verdict"] = "UNVERIFIABLE"; rec["detail"] = "no usable key"; return rec, []

    shared = [c for c in api.columns if c in mir.columns and c not in keys]
    rec["cols_compared"] = len(shared)

    api_n, _ = normalize_frame(api.select(keys + shared))
    mir_n, sch = normalize_frame(mir.select(keys + shared))

    def keyexpr(df):
        parts = [df[k].cast(pl.Utf8).fill_null("<NA>") for k in keys]
        out = parts[0]
        for p in parts[1:]:
            out = out + "|" + p
        return out
    api_n = api_n.with_columns(keyexpr(api_n).alias("__k"))
    mir_n = mir_n.with_columns(keyexpr(mir_n).alias("__k"))

    if api_n["__k"].n_unique() != api_n.height or mir_n["__k"].n_unique() != mir_n.height:
        rec["detail"] += (f"[grain: api rows={api_n.height} keys={api_n['__k'].n_unique()}; "
                          f"mir rows={mir_n.height} keys={mir_n['__k'].n_unique()}] ")

    joined = api_n.join(mir_n, on="__k", how="inner", suffix="__mir")
    rec["n_keys_compared"] = joined.height
    if joined.height == 0:
        rec["verdict"] = "UNVERIFIABLE"; rec["detail"] += "no overlapping keys"; return rec, []

    examples = []
    cols_mm = cell_mm = 0
    for c in shared:
        mc = f"{c}__mir"
        if mc not in joined.columns:
            continue
        kind = sch.get(c, "str")
        if kind == "num":
            a = joined[c].cast(pl.Float64, strict=False)
            b = joined[mc].cast(pl.Float64, strict=False)
            tol = pl.max_horizontal(pl.lit(0.01), (b.abs() * 1e-4))
            both_null = a.is_null() & b.is_null()
            one_null = a.is_null() ^ b.is_null()
            close = (a - b).abs() <= tol
            bad = one_null | (~both_null & ~one_null & ~close)
            diff = joined.filter(bad)
        else:
            diff = joined.filter(joined[c].cast(pl.Utf8) != joined[mc].cast(pl.Utf8))
        if diff.height:
            cols_mm += 1
            cell_mm += diff.height
            for r in diff.head(3).iter_rows(named=True):
                examples.append({"label": label, "key": str(r["__k"]), "column": c,
                                 "kind": kind, "api_value": str(r[c]), "mirror_value": str(r[mc])})
    rec["cols_mismatch"] = cols_mm
    rec["cell_mismatch"] = cell_mm
    rec["verdict"] = "MATCH" if cell_mm == 0 else "MISMATCH"
    return rec, examples


# --- Slices (composite keys; edfacts uses full total-dim constraint) ---
SLICES = [
    ("ipeds_directory", f"{API_BASE}/college-university/ipeds/directory/2022/?fips=11",
     "ipeds/colleges_ipeds_directory.parquet", 2022, 11, ["unitid"], None),
    ("saipe_al", f"{API_BASE}/school-districts/saipe/2021/?fips=1",
     "saipe/districts_saipe.parquet", 2021, 1, ["leaid"], None),
    ("ccd_sch_dir", f"{API_BASE}/schools/ccd/directory/2022/?fips=11",
     "ccd/schools_ccd_directory.parquet", 2022, 11, ["ncessch"], None),
    ("meps", f"{API_BASE}/schools/meps/2020/?fips=11",
     "meps/schools_meps.parquet", 2020, 11, ["ncessch"], None),
    ("fsa_grants", f"{API_BASE}/college-university/fsa/grants/2018/?fips=11",
     "fsa/colleges_fsa_grants.parquet", 2018, 11, ["unitid", "grant_type"], None),
    ("scorecard_instchar", f"{API_BASE}/college-university/scorecard/institutional-characteristics/2018/?fips=11",
     "scorecard/colleges_scorecard_inst_characteristics.parquet", 2018, 11, ["unitid"], None),
    ("ccd_dist_fin", f"{API_BASE}/school-districts/ccd/finance/2020/?fips=11",
     "ccd/districts_ccd_finance.parquet", 2020, 11, ["leaid"], None),
    ("crdc_sch_char", f"{API_BASE}/schools/crdc/directory/2020/?fips=11",
     "crdc/schools_crdc_school_characteristics.parquet", 2020, 11, ["crdc_id"], None),
    ("edfacts_assess", f"{API_BASE}/schools/edfacts/assessments/2018/grade-99/?fips=11",
     "edfacts/schools_edfacts_assessments_2018.parquet", 2018, 11, ["ncessch"],
     {d: 99 for d in EDFACTS_TOTAL_DIMS}),
    ("ipeds_libraries", f"{API_BASE}/college-university/ipeds/academic-libraries/2020/?fips=11",
     "ipeds/colleges_ipeds_academic_libraries.parquet", 2020, 11, ["unitid"], None),
]

print("=== DEEP VALUE SLICES (revised harness) ===")
all_recs, all_examples = [], []
for label, api_url, mirror_rel, year, fips, keys, disagg in SLICES:
    rec, ex = compare_slice(label, api_url, mirror_rel, year, fips, keys, disagg)
    all_recs.append(rec)
    all_examples.extend(ex)
    print(f"[{label:20s}] {rec['verdict']:17s} keys={rec['n_keys_compared']} "
          f"cols={rec['cols_compared']} colMM={rec['cols_mismatch']} cellMM={rec['cell_mismatch']} "
          f"{rec['detail']}")

rec_df = pl.from_dicts(all_recs)
rec_df.write_parquet(OUT_DIR / "laneB_value_slices.parquet")
if all_examples:
    pl.from_dicts(all_examples).write_parquet(OUT_DIR / "laneB_value_mismatch_examples.parquet")

print("\n=== LANE B PART 2 (revised) SUMMARY ===")
print(rec_df.select("label", "verdict", "n_keys_compared", "cols_compared", "cols_mismatch", "cell_mismatch"))
n_match = rec_df.filter(pl.col("verdict") == "MATCH").height
print(f"MATCH={n_match} / {rec_df.height} slices")
if all_examples:
    print("\n--- RESIDUAL MISMATCH EXAMPLES (verbatim, capped 40) ---")
    for e in all_examples[:40]:
        print(f"  [{e['label']}] key={e['key']} col={e['column']}({e['kind']}) "
              f"api={e['api_value']!r} mirror={e['mirror_value']!r}")
print("\nLANE B PART 2 (revised) COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:22:56
# Command: python3 /daaf/scripts/mirror_maintenance/21_laneB-value-slices_a_a.py
# Duration: 12s
# Exit code: 0
#
# --- STDOUT ---
# === DEEP VALUE SLICES (revised harness) ===
# [ipeds_directory     ] MATCH             keys=23 cols=95 colMM=0 cellMM=0 
# [saipe_al            ] MATCH             keys=140 cols=9 colMM=0 cellMM=0 
# [ccd_sch_dir         ] MISMATCH          keys=244 cols=51 colMM=1 cellMM=122 
# [meps                ] MATCH             keys=226 cols=10 colMM=0 cellMM=0 
# [fsa_grants          ] MATCH             keys=80 cols=11 colMM=0 cellMM=0 
# [scorecard_instchar  ] MATCH             keys=24 cols=26 colMM=0 cellMM=0 
# [ccd_dist_fin        ] MATCH             keys=70 cols=162 colMM=0 cellMM=0 
# [crdc_sch_char       ] MATCH             keys=240 cols=34 colMM=0 cellMM=0 
# [edfacts_assess      ] MATCH             keys=214 cols=25 colMM=0 cellMM=0 
# [ipeds_libraries     ] MATCH             keys=16 cols=40 colMM=0 cellMM=0 
# 
# === LANE B PART 2 (revised) SUMMARY ===
# shape: (10, 6)
# ┌────────────────────┬──────────┬─────────────────┬───────────────┬───────────────┬───────────────┐
# │ label              ┆ verdict  ┆ n_keys_compared ┆ cols_compared ┆ cols_mismatch ┆ cell_mismatch │
# │ ---                ┆ ---      ┆ ---             ┆ ---           ┆ ---           ┆ ---           │
# │ str                ┆ str      ┆ i64             ┆ i64           ┆ i64           ┆ i64           │
# ╞════════════════════╪══════════╪═════════════════╪═══════════════╪═══════════════╪═══════════════╡
# │ ipeds_directory    ┆ MATCH    ┆ 23              ┆ 95            ┆ 0             ┆ 0             │
# │ saipe_al           ┆ MATCH    ┆ 140             ┆ 9             ┆ 0             ┆ 0             │
# │ ccd_sch_dir        ┆ MISMATCH ┆ 244             ┆ 51            ┆ 1             ┆ 122           │
# │ meps               ┆ MATCH    ┆ 226             ┆ 10            ┆ 0             ┆ 0             │
# │ fsa_grants         ┆ MATCH    ┆ 80              ┆ 11            ┆ 0             ┆ 0             │
# │ scorecard_instchar ┆ MATCH    ┆ 24              ┆ 26            ┆ 0             ┆ 0             │
# │ ccd_dist_fin       ┆ MATCH    ┆ 70              ┆ 162           ┆ 0             ┆ 0             │
# │ crdc_sch_char      ┆ MATCH    ┆ 240             ┆ 34            ┆ 0             ┆ 0             │
# │ edfacts_assess     ┆ MATCH    ┆ 214             ┆ 25            ┆ 0             ┆ 0             │
# │ ipeds_libraries    ┆ MATCH    ┆ 16              ┆ 40            ┆ 0             ┆ 0             │
# └────────────────────┴──────────┴─────────────────┴───────────────┴───────────────┴───────────────┘
# MATCH=9 / 10 slices
# 
# --- RESIDUAL MISMATCH EXAMPLES (verbatim, capped 40) ---
#   [ccd_sch_dir] key=110000800382 col=teachers_fte(num) api='28.0' mirror='28.98'
#   [ccd_sch_dir] key=110000800478 col=teachers_fte(num) api='24.0' mirror='24.96'
#   [ccd_sch_dir] key=110000800479 col=teachers_fte(num) api='24.0' mirror='24.96'
# 
# LANE B PART 2 (revised) COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
