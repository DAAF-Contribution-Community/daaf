#!/usr/bin/env python3
# =============================================================================
# 46_fidelity-expansion-compare-batchA.py  (Lane A bulk-CSV parity — expansion, step 2/4)
# =============================================================================
# INTENT: For each file in BATCH A of the script-45 sample plan, download the current Urban
#   bulk CSV, compare it cell-for-cell against the shipped mirror parquet, record MATCH /
#   MISMATCH with any residual mismatch verbatim, then DELETE the CSV. Resumable: results are
#   checkpointed per-file so a rerun (e.g. after a Bash-timeout) never restarts from zero.
#
# METHOD reuses the proven Lane A harness (22_laneA-conversion-fidelity_a.py):
#   - Download: resumable HTTP Range, 3 retries w/ backoff, 60s timeout, polite pacing;
#     completeness checked vs the plan's recorded csv_bytes (manifest HEAD Content-Length).
#   - Read CSV all-String (pl.read_csv infer_schema=False) = the CSV truth baseline; read the
#     mirror parquet from the local build tree (proven byte-identical to the pinned HF revision
#     497/497 sha256 wave-2, so local parquet == shipped mirror).
#   - Normalize both sides, schema-driven off the AUTHORITATIVE MIRROR dtype:
#       * id cols (ncessch/leaid/unitid/crdc_id/fips/district_id): strip trailing ".0",
#         zero-pad ncessch->12 / leaid->7 (the build's identifier-width contract);
#       * numeric cols: cast Float64 then round to 4 dp (canonical grid — benign float text
#         precision is not a defect; this is the proven nacubo canonicalization);
#       * string cols: strip; then unify missing tokens {null,"",-1,-2,-3} -> "<NA>".
#   - COMPARE DEPTH (from the plan; recorded per file):
#       * whole-row-multiset (rows <= 1.5M): canonicalize all shared cols, group_by all shared
#         cols and compare per-signature counts. Any imbalance = residual finding (reported with
#         the row's identifier signature). Row-correlated, every cell compared.
#       * per-column-multiset-hash (rows > 1.5M; plan labels this "per-column-sorted-hash"):
#         for each shared column, sum Polars' per-element hash of the canonicalized values (an
#         order-independent multiset hash — equivalent to comparing sorted values, but memory-
#         friendly for XL files). Mismatch => that column's multiset differs. Row count + col
#         set checked separately. ASSUMES 64-bit multiset-hash collision prob is negligible and
#         row-count parity guards against a same-hash different-length coincidence.
#   - Row-count parity and column-set differences (csv_only / mirror_only) always recorded;
#     a column-set difference alone (values+rows exact) is flagged MATCH* not MISMATCH.
#
# DISK HYGIENE (explicit orchestrator-approved deviation from retain-scratch): each CSV is
#   DELETED immediately after its comparison. The result parquet + this appended execution log
#   are the provenance record; caching ~6 GB of CSV inside the backup boundary is the greater
#   harm. Downloads live transiently under scripts/scratch/urban_fidelity_expansion/.
#
# Read-only network GETs. No installs. No /tmp writes. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import polars as pl
import urllib.request
import urllib.error
import time
from pathlib import Path

BATCH = "A"   # <<< the only line that differs from script 47 (batch B)

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
DL_DIR = PROJECT_DIR / "scripts" / "scratch" / "urban_fidelity_expansion"
DL_DIR.mkdir(parents=True, exist_ok=True)

PLAN_FP = OUT_DIR / "45_fidelity-expansion-sample-plan.parquet"
RESULT_FP = OUT_DIR / f"46_fidelity-expansion-results-batch{BATCH}.parquet"
EXAMPLES_FP = OUT_DIR / f"46_fidelity-expansion-mismatches-batch{BATCH}.parquet"

UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"
TIMEOUT = 60
RETRIES = 3
MISSING_TOKENS = ["-1", "-2", "-3", "", "-1.0", "-2.0", "-3.0"]
MISS = "<NA>"
PAD = {"ncessch": 12, "leaid": 7}
ID_COLS = {"ncessch", "leaid", "unitid", "crdc_id", "fips", "district_id", "ope_id", "year"}
NUM_DTYPES = (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32,
              pl.UInt64, pl.Float32, pl.Float64)


# --- Download helper (resumable, retries, polite) ---
def download_csv(url, dest, expected_bytes):
    last_err = None
    for attempt in range(1, RETRIES + 1):
        if dest.exists() and expected_bytes is not None and dest.stat().st_size == expected_bytes:
            return True, None
        resume_from = dest.stat().st_size if dest.exists() else 0
        headers = {"User-Agent": UA}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                mode = "ab" if (resume_from > 0 and resp.status == 206) else "wb"
                if mode == "wb":
                    resume_from = 0
                with open(dest, mode) as fh:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
            if expected_bytes is None or dest.stat().st_size == expected_bytes:
                return True, None
            last_err = f"size {dest.stat().st_size} != expected {expected_bytes}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = repr(e)[:140]
        time.sleep(min(2 ** attempt, 15))
    return False, last_err


# --- Normalization keyed off the authoritative mirror schema ---
def classify(colname, mirror_dtype):
    if colname in PAD:
        return "id"
    if colname in ID_COLS:
        return "id_plain"   # id-like but not width-padded (unitid, crdc_id, fips, year, ...)
    if mirror_dtype in NUM_DTYPES:
        return "num"
    return "str"


def canon_col_exprs(shared, mir_schema):
    # Return polars expressions that canonicalize each shared column identically on both sides.
    exprs = []
    for c in shared:
        kind = classify(c, mir_schema[c])
        miss = (pl.col(c).cast(pl.Utf8, strict=False).str.strip_chars().is_in(MISSING_TOKENS)
                | pl.col(c).is_null())
        if kind == "id":
            e = (pl.when(miss).then(pl.lit(MISS))
                 .otherwise(pl.col(c).cast(pl.Utf8).str.replace(r"\.0$", "").str.zfill(PAD[c])))
        elif kind == "id_plain":
            # strip trailing ".0" int->str artifact; keep as string; missing -> sentinel
            e = (pl.when(miss).then(pl.lit(MISS))
                 .otherwise(pl.col(c).cast(pl.Utf8).str.strip_chars().str.replace(r"\.0$", "")))
        elif kind == "num":
            # numeric -> Float64 -> round 4dp -> canonical string; missing -> sentinel
            e = (pl.when(miss).then(pl.lit(MISS))
                 .otherwise(pl.col(c).cast(pl.Float64, strict=False).round(4).cast(pl.Utf8)))
        else:
            e = (pl.when(miss).then(pl.lit(MISS))
                 .otherwise(pl.col(c).cast(pl.Utf8, strict=False).str.strip_chars()))
        exprs.append(e.alias(c))
    return exprs


# --- Load plan (batch subset) + resume checkpoint ---
plan = pl.read_parquet(PLAN_FP).filter(pl.col("batch") == BATCH).sort("csv_bytes")
print(f"=== FIDELITY EXPANSION — BATCH {BATCH}: {plan.height} files "
      f"({plan['csv_bytes'].sum()/1e9:.3f} GB planned) ===")

done_rels = set()
results = []
examples = []
if RESULT_FP.exists():
    prev = pl.read_parquet(RESULT_FP)
    done_rels = set(prev["rel"].to_list())
    results = prev.to_dicts()
    print(f"Resuming: {len(done_rels)} files already recorded in {RESULT_FP.name}")
if EXAMPLES_FP.exists():
    examples = pl.read_parquet(EXAMPLES_FP).to_dicts()

downloaded_total = 0
for prow in plan.iter_rows(named=True):
    rel = prow["rel"]
    if rel in done_rels:
        continue
    url = prow["csv_url"]
    exp = prow["csv_bytes"]
    depth = prow["depth"]
    print("\n" + "-" * 72)
    print(f"[{rel}] tier={prow['tier']} build={prow['build_action']} rows={prow['n_rows']:,} depth={depth}")
    dest = DL_DIR / rel.replace("/", "__")

    rec = {"rel": rel, "source": prow["source"], "build_action": prow["build_action"],
           "classification": prow["classification"], "tier": prow["tier"],
           "planned_depth": depth, "compare_method": "", "csv_rows": None, "mirror_rows": None,
           "row_match": None, "shared_cols": 0, "csv_only_cols": "", "mirror_only_cols": "",
           "cols_mismatch": 0, "cell_mismatch": 0, "verdict": "", "detail": "",
           "csv_bytes": int(exp)}

    ok, err = download_csv(url, dest, exp)
    if not ok:
        rec["verdict"] = "UNVERIFIABLE-TODAY"
        rec["detail"] = f"download: {err}"
        print(f"  [FAIL download] {err}")
        results.append(rec)
        pl.from_dicts(results, infer_schema_length=None).write_parquet(RESULT_FP)
        if dest.exists():
            dest.unlink()
        time.sleep(1.2)
        continue
    downloaded_total += dest.stat().st_size
    print(f"  [ok] CSV {dest.stat().st_size:,} B (cum this run {downloaded_total:,})")

    # --- Read both sides ---
    csv = pl.read_csv(dest, infer_schema=False)
    mir = pl.read_parquet(TREE_DIR / rel)
    rec["csv_rows"], rec["mirror_rows"] = csv.height, mir.height
    rec["row_match"] = (csv.height == mir.height)

    csv_cols, mir_cols = set(csv.columns), set(mir.columns)
    csv_only, mir_only = sorted(csv_cols - mir_cols), sorted(mir_cols - csv_cols)
    rec["csv_only_cols"], rec["mirror_only_cols"] = "|".join(csv_only), "|".join(mir_only)
    mir_schema = dict(zip(mir.columns, mir.dtypes))
    shared = [c for c in mir.columns if c in csv_cols]  # mirror order
    rec["shared_cols"] = len(shared)

    csv_c = csv.select(canon_col_exprs(shared, mir_schema))
    mir_c = mir.select(canon_col_exprs(shared, mir_schema))

    if depth == "whole-row-multiset":
        rec["compare_method"] = "whole-row-multiset (group_by all shared cols)"
        ha = csv_c.group_by(shared).len().rename({"len": "n_csv"})
        hb = mir_c.group_by(shared).len().rename({"len": "n_mir"})
        merged = ha.join(hb, on=shared, how="full", coalesce=True).with_columns(
            pl.col("n_csv").fill_null(0), pl.col("n_mir").fill_null(0))
        bad = merged.filter(pl.col("n_csv") != pl.col("n_mir"))
        if bad.height:
            rec["cols_mismatch"] = -1  # N/A: whole-row signatures compared
            rec["cell_mismatch"] = int(bad.select((pl.col("n_csv") - pl.col("n_mir")).abs().sum()).item())
            sig_cols = [c for c in shared if c in ID_COLS] or shared[:3]
            for r in bad.head(3).iter_rows(named=True):
                sig = "; ".join(f"{c}={r[c]}" for c in sig_cols)
                examples.append({"rel": rel, "signature": sig, "column": "<whole-row>",
                                 "csv_value": f"n_csv={r['n_csv']}", "mirror_value": f"n_mir={r['n_mir']}"})
    else:
        rec["compare_method"] = "per-column-multiset-hash (order-independent sum of element hashes)"
        col_mm = 0
        for c in shared:
            ha = int(csv_c.select(pl.col(c).hash().sum()).item())
            hb = int(mir_c.select(pl.col(c).hash().sum()).item())
            if ha != hb:
                col_mm += 1
                examples.append({"rel": rel, "signature": f"column multiset hash differs",
                                 "column": c, "csv_value": f"hashsum={ha}", "mirror_value": f"hashsum={hb}"})
        rec["cols_mismatch"] = col_mm
        rec["cell_mismatch"] = col_mm  # per-column granularity for XL files

    # --- Verdict ---
    if rec["cell_mismatch"] == 0 and rec["row_match"] and not csv_only and not mir_only:
        rec["verdict"] = "MATCH"
    elif rec["cell_mismatch"] == 0 and rec["row_match"]:
        rec["verdict"] = "MATCH*"
        rec["detail"] = "values+rows exact; column-set differs"
    else:
        rec["verdict"] = "MISMATCH"
    print(f"  rows csv={rec['csv_rows']:,} mir={rec['mirror_rows']:,} match={rec['row_match']} "
          f"shared={rec['shared_cols']} csv_only={csv_only} mir_only={mir_only}")
    print(f"  method={rec['compare_method']}")
    print(f"  VERDICT={rec['verdict']} colMM={rec['cols_mismatch']} cellMM={rec['cell_mismatch']} {rec['detail']}")

    results.append(rec)
    # --- Checkpoint after EVERY file (resumability) ---
    pl.from_dicts(results, infer_schema_length=None).write_parquet(RESULT_FP)
    if examples:
        pl.from_dicts(examples, infer_schema_length=None).write_parquet(EXAMPLES_FP)

    # --- DISK HYGIENE: delete the CSV now that its comparison is recorded ---
    dest.unlink()
    time.sleep(1.2)

# --- Summary ---
res = pl.from_dicts(results, infer_schema_length=None)
res_batch = res.filter(pl.col("rel").is_in(plan["rel"].to_list()))
print(f"\n=== BATCH {BATCH} SUMMARY ===")
print(res_batch.group_by("verdict").len().sort("verdict"))
n_match = res_batch.filter(pl.col("verdict").is_in(["MATCH", "MATCH*"])).height
print(f"MATCH(+MATCH*) = {n_match} / {res_batch.height} batch-{BATCH} files")
mism = res_batch.filter(pl.col("verdict") == "MISMATCH")
if mism.height:
    print("\n--- MISMATCHES (verbatim) ---")
    print(mism.select("rel", "verdict", "cols_mismatch", "cell_mismatch", "detail"))
    if examples:
        for e in examples:
            if e["rel"] in mism["rel"].to_list():
                print(f"  [{e['rel']}] {e['signature']} col={e['column']} "
                      f"csv={e['csv_value']} mir={e['mirror_value']}")
else:
    print("No MISMATCHes in this batch.")
print(f"\nBATCH {BATCH} COMPLETE ({res_batch.height}/{plan.height} recorded).")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 19:29:26
# Command: python3 /daaf/scripts/mirror_maintenance/46_fidelity-expansion-compare-batchA.py
# Duration: 240s
# Exit code: 0
#
# --- STDOUT ---
# === FIDELITY EXPANSION — BATCH A: 50 files (2.948 GB planned) ===
# 
# ------------------------------------------------------------------------
# [fsa/colleges_fsa_90_10_revenue_percentages.parquet] tier=S<5MB build=carry-forward rows=13,821 depth=whole-row-multiset
#   [ok] CSV 1,190,112 B (cum this run 1,190,112)
#   rows csv=13,821 mir=13,821 match=True shared=8 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_ay_tuition_firstprof.parquet] tier=S<5MB build=fetch-fresh rows=50,802 depth=whole-row-multiset
#   [ok] CSV 1,695,639 B (cum this run 2,885,751)
#   rows csv=50,802 mir=50,802 match=True shared=8 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_py_room_board_other.parquet] tier=S<5MB build=fetch-fresh rows=108,932 depth=whole-row-multiset
#   [ok] CSV 2,828,150 B (cum this run 5,713,901)
#   rows csv=108,932 mir=108,932 match=True shared=6 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2019.parquet] tier=M5-50MB build=carry-forward rows=93,655 depth=whole-row-multiset
#   [ok] CSV 7,065,069 B (cum this run 12,778,970)
#   rows csv=93,655 mir=93,655 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1988.parquet] tier=M5-50MB build=carry-forward rows=269,780 depth=whole-row-multiset
#   [ok] CSV 7,382,637 B (cum this run 20,161,607)
#   rows csv=269,780 mir=269,780 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1994.parquet] tier=M5-50MB build=carry-forward rows=270,828 depth=whole-row-multiset
#   [ok] CSV 7,426,166 B (cum this run 27,587,773)
#   rows csv=270,828 mir=270,828 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1992.parquet] tier=M5-50MB build=carry-forward rows=273,591 depth=whole-row-multiset
#   [ok] CSV 7,492,364 B (cum this run 35,080,137)
#   rows csv=273,591 mir=273,591 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1991.parquet] tier=M5-50MB build=carry-forward rows=276,294 depth=whole-row-multiset
#   [ok] CSV 7,561,905 B (cum this run 42,642,042)
#   rows csv=276,294 mir=276,294 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1990.parquet] tier=M5-50MB build=carry-forward rows=276,568 depth=whole-row-multiset
#   [ok] CSV 7,563,203 B (cum this run 50,205,245)
#   rows csv=276,568 mir=276,568 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2010.parquet] tier=M5-50MB build=carry-forward rows=113,260 depth=whole-row-multiset
#   [ok] CSV 8,490,814 B (cum this run 58,696,059)
#   rows csv=113,260 mir=113,260 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2011.parquet] tier=M5-50MB build=carry-forward rows=113,490 depth=whole-row-multiset
#   [ok] CSV 8,517,093 B (cum this run 67,213,152)
#   rows csv=113,490 mir=113,490 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2012.parquet] tier=M5-50MB build=carry-forward rows=119,670 depth=whole-row-multiset
#   [ok] CSV 8,956,119 B (cum this run 76,169,271)
#   rows csv=119,670 mir=119,670 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2013.parquet] tier=M5-50MB build=carry-forward rows=121,580 depth=whole-row-multiset
#   [ok] CSV 9,119,923 B (cum this run 85,289,194)
#   rows csv=121,580 mir=121,580 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2015.parquet] tier=M5-50MB build=carry-forward rows=123,500 depth=whole-row-multiset
#   [ok] CSV 9,304,857 B (cum this run 94,594,051)
#   rows csv=123,500 mir=123,500 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_credit_recovery.parquet] tier=M5-50MB build=carry-forward rows=193,992 depth=whole-row-multiset
#   [ok] CSV 9,553,766 B (cum this run 104,147,817)
#   rows csv=193,992 mir=193,992 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_covid_indicators.parquet] tier=M5-50MB build=carry-forward rows=195,585 depth=whole-row-multiset
#   [ok] CSV 10,146,498 B (cum this run 114,294,315)
#   rows csv=195,585 mir=195,585 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=-1 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2018.parquet] tier=M5-50MB build=carry-forward rows=141,984 depth=whole-row-multiset
#   [ok] CSV 10,736,099 B (cum this run 125,030,414)
#   rows csv=141,984 mir=141,984 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2017.parquet] tier=M5-50MB build=carry-forward rows=147,744 depth=whole-row-multiset
#   [ok] CSV 11,106,330 B (cum this run 136,136,744)
#   rows csv=147,744 mir=147,744 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1984.parquet] tier=M5-50MB build=carry-forward rows=349,815 depth=whole-row-multiset
#   [ok] CSV 11,234,961 B (cum this run 147,371,705)
#   rows csv=349,815 mir=349,815 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1985.parquet] tier=M5-50MB build=carry-forward rows=352,437 depth=whole-row-multiset
#   [ok] CSV 11,317,253 B (cum this run 158,688,958)
#   rows csv=352,437 mir=352,437 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1989.parquet] tier=M5-50MB build=carry-forward rows=388,410 depth=whole-row-multiset
#   [ok] CSV 12,448,310 B (cum this run 171,137,268)
#   rows csv=388,410 mir=388,410 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1987.parquet] tier=M5-50MB build=carry-forward rows=393,315 depth=whole-row-multiset
#   [ok] CSV 12,586,020 B (cum this run 183,723,288)
#   rows csv=393,315 mir=393,315 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_sfa_all_undergrads.parquet] tier=M5-50MB build=carry-forward rows=286,648 depth=whole-row-multiset
#   [ok] CSV 13,342,450 B (cum this run 197,065,738)
#   rows csv=286,648 mir=286,648 match=True shared=10 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1993.parquet] tier=M5-50MB build=carry-forward rows=418,980 depth=whole-row-multiset
#   [ok] CSV 13,501,033 B (cum this run 210,566,771)
#   rows csv=418,980 mir=418,980 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_grad-rates-pell.parquet] tier=M5-50MB build=fetch-fresh rows=367,628 depth=whole-row-multiset
#   [ok] CSV 15,710,843 B (cum this run 226,277,614)
#   rows csv=367,628 mir=367,628 match=True shared=12 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2024.parquet] tier=M5-50MB build=fetch-fresh rows=575,208 depth=whole-row-multiset
#   [ok] CSV 17,850,786 B (cum this run 244,128,400)
#   rows csv=575,208 mir=575,208 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [nccs/colleges_nccs_all.parquet] tier=M5-50MB build=carry-forward rows=29,889 depth=whole-row-multiset
#   [ok] CSV 18,653,267 B (cum this run 262,781,667)
#   rows csv=29,889 mir=29,889 match=True shared=161 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2018.parquet] tier=M5-50MB build=carry-forward rows=612,648 depth=whole-row-multiset
#   [ok] CSV 19,000,418 B (cum this run 281,782,085)
#   rows csv=612,648 mir=612,648 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_admissions-requirements.parquet] tier=M5-50MB build=carry-forward rows=270,905 depth=whole-row-multiset
#   [ok] CSV 20,361,888 B (cum this run 302,143,973)
#   rows csv=270,905 mir=270,905 match=True shared=48 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2010.parquet] tier=M5-50MB build=carry-forward rows=646,554 depth=whole-row-multiset
#   [ok] CSV 20,727,915 B (cum this run 322,871,888)
#   rows csv=646,554 mir=646,554 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2008.parquet] tier=M5-50MB build=carry-forward rows=670,215 depth=whole-row-multiset
#   [ok] CSV 21,462,306 B (cum this run 344,334,194)
#   rows csv=670,215 mir=670,215 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2012.parquet] tier=M5-50MB build=carry-forward rows=721,341 depth=whole-row-multiset
#   [ok] CSV 23,046,742 B (cum this run 367,380,936)
#   rows csv=721,341 mir=721,341 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [eada/colleges_eada_inst_characteristics.parquet] tier=M5-50MB build=carry-forward rows=40,634 depth=whole-row-multiset
#   [ok] CSV 26,969,715 B (cum this run 394,350,651)
#   rows csv=40,634 mir=40,634 match=True shared=165 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_1999.parquet] tier=M5-50MB build=carry-forward rows=923,598 depth=whole-row-multiset
#   [ok] CSV 29,441,717 B (cum this run 423,792,368)
#   rows csv=923,598 mir=923,598 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2002.parquet] tier=M5-50MB build=carry-forward rows=1,012,239 depth=whole-row-multiset
#   [ok] CSV 32,186,683 B (cum this run 455,979,051)
#   rows csv=1,012,239 mir=1,012,239 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_harass_bully_allegations.parquet] tier=M5-50MB build=carry-forward rows=485,084 depth=whole-row-multiset
#   [ok] CSV 44,501,055 B (cum this run 500,480,106)
#   rows csv=485,084 mir=485,084 match=True shared=24 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1988.parquet] tier=M5-50MB build=carry-forward rows=923,881 depth=whole-row-multiset
#   [ok] CSV 49,651,270 B (cum this run 550,131,376)
#   rows csv=923,881 mir=923,881 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_offenses.parquet] tier=L50-200MB build=carry-forward rows=385,796 depth=whole-row-multiset
#   [ok] CSV 52,245,582 B (cum this run 602,376,958)
#   rows csv=385,796 mir=385,796 match=True shared=33 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1991.parquet] tier=L50-200MB build=carry-forward rows=1,000,365 depth=whole-row-multiset
#   [ok] CSV 53,742,538 B (cum this run 656,119,496)
#   rows csv=1,000,365 mir=1,000,365 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1993.parquet] tier=L50-200MB build=carry-forward rows=1,006,409 depth=whole-row-multiset
#   [ok] CSV 54,065,573 B (cum this run 710,185,069)
#   rows csv=1,006,409 mir=1,006,409 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [pseo/colleges_pseo_2021.parquet] tier=L50-200MB build=carry-forward rows=793,620 depth=whole-row-multiset
#   [ok] CSV 54,749,385 B (cum this run 764,934,454)
#   rows csv=793,620 mir=793,620 match=True shared=18 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [nhgis/colleges_nhgis_geog_2000.parquet] tier=L50-200MB build=carry-forward rows=337,222 depth=whole-row-multiset
#   [ok] CSV 85,019,743 B (cum this run 849,954,197)
#   rows csv=337,222 mir=337,222 match=True shared=33 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=-1 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_restraint_seclusion_instances.parquet] tier=L50-200MB build=carry-forward rows=2,331,506 depth=per-column-sorted-hash
#   [ok] CSV 116,910,135 B (cum this run 966,864,332)
#   rows csv=2,331,506 mir=2,331,506 match=True shared=9 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [pseo/colleges_pseo_2002.parquet] tier=L50-200MB build=carry-forward rows=1,836,090 depth=per-column-sorted-hash
#   [ok] CSV 129,591,526 B (cum this run 1,096,455,858)
#   rows csv=1,836,090 mir=1,836,090 match=True shared=18 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [pseo/colleges_pseo_2001.parquet] tier=L50-200MB build=carry-forward rows=1,838,520 depth=per-column-sorted-hash
#   [ok] CSV 129,754,301 B (cum this run 1,226,210,159)
#   rows csv=1,838,520 mir=1,838,520 match=True shared=18 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [pseo/colleges_pseo_2004.parquet] tier=L50-200MB build=carry-forward rows=1,909,620 depth=per-column-sorted-hash
#   [ok] CSV 134,774,761 B (cum this run 1,360,984,920)
#   rows csv=1,909,620 mir=1,909,620 match=True shared=18 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_sat_and_act_participation_2011.parquet] tier=L50-200MB build=carry-forward rows=2,869,050 depth=per-column-sorted-hash
#   [ok] CSV 155,711,638 B (cum this run 1,516,696,558)
#   rows csv=2,869,050 mir=2,869,050 match=True shared=10 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_sat_and_act_participation_2015.parquet] tier=L50-200MB build=carry-forward rows=2,890,800 depth=per-column-sorted-hash
#   [ok] CSV 156,803,238 B (cum this run 1,673,499,796)
#   rows csv=2,890,800 mir=2,890,800 match=True shared=10 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_2016.parquet] tier=XL>200MB build=carry-forward rows=6,283,716 depth=per-column-sorted-hash
#   [ok] CSV 203,618,308 B (cum this run 1,877,118,104)
#   rows csv=6,283,716 mir=6,283,716 match=True shared=7 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [csafety/colleges_csafety_hate_crimes.parquet] tier=XL>200MB build=carry-forward rows=15,230,698 depth=per-column-sorted-hash
#   [ok] CSV 1,071,266,269 B (cum this run 2,948,384,373)
#   rows csv=15,230,698 mir=15,230,698 match=True shared=13 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# === BATCH A SUMMARY ===
# shape: (1, 2)
# ┌─────────┬─────┐
# │ verdict ┆ len │
# │ ---     ┆ --- │
# │ str     ┆ u32 │
# ╞═════════╪═════╡
# │ MATCH   ┆ 50  │
# └─────────┴─────┘
# MATCH(+MATCH*) = 50 / 50 batch-A files
# No MISMATCHes in this batch.
# 
# BATCH A COMPLETE (50/50 recorded).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
