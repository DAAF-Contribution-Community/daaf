#!/usr/bin/env python3
# =============================================================================
# 47_fidelity-expansion-compare-batchB.py  (Lane A bulk-CSV parity — expansion, step 3/4)
# =============================================================================
# INTENT: For each file in BATCH B of the script-45 sample plan, download the current Urban
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

BATCH = "B"   # <<< the only line that differs from script 46 (batch A)

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
# Executed: 2026-08-08 19:33:38
# Command: python3 /daaf/scripts/mirror_maintenance/47_fidelity-expansion-compare-batchB.py
# Duration: 219s
# Exit code: 0
#
# --- STDOUT ---
# === FIDELITY EXPANSION — BATCH B: 50 files (2.949 GB planned) ===
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_grad-rates-200pct.parquet] tier=M5-50MB build=fetch-fresh rows=93,088 depth=whole-row-multiset
#   [ok] CSV 5,915,281 B (cum this run 5,915,281)
#   rows csv=93,088 mir=93,088 match=True shared=17 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2000.parquet] tier=M5-50MB build=carry-forward rows=221,059 depth=whole-row-multiset
#   [ok] CSV 6,887,633 B (cum this run 12,802,914)
#   rows csv=221,059 mir=221,059 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_admissions-enrollment.parquet] tier=M5-50MB build=fetch-fresh rows=215,831 depth=whole-row-multiset
#   [ok] CSV 7,333,005 B (cum this run 20,135,919)
#   rows csv=215,831 mir=215,831 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1995.parquet] tier=M5-50MB build=carry-forward rows=270,417 depth=whole-row-multiset
#   [ok] CSV 7,417,207 B (cum this run 27,553,126)
#   rows csv=270,417 mir=270,417 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1993.parquet] tier=M5-50MB build=carry-forward rows=271,866 depth=whole-row-multiset
#   [ok] CSV 7,450,951 B (cum this run 35,004,077)
#   rows csv=271,866 mir=271,866 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_lea_enrollment_1997.parquet] tier=M5-50MB build=carry-forward rows=274,018 depth=whole-row-multiset
#   [ok] CSV 7,516,524 B (cum this run 42,520,601)
#   rows csv=274,018 mir=274,018 match=True shared=7 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_academic_libraries.parquet] tier=M5-50MB build=fetch-fresh rows=43,077 depth=whole-row-multiset
#   [ok] CSV 8,060,512 B (cum this run 50,581,113)
#   rows csv=43,077 mir=43,077 match=True shared=41 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [scorecard/colleges_scorecard_repayment_fsa.parquet] tier=M5-50MB build=carry-forward rows=177,882 depth=whole-row-multiset
#   [ok] CSV 8,162,963 B (cum this run 58,744,076)
#   rows csv=177,882 mir=177,882 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-race_1989.parquet] tier=M5-50MB build=carry-forward rows=249,965 depth=whole-row-multiset
#   [ok] CSV 8,631,182 B (cum this run 67,375,258)
#   rows csv=249,965 mir=249,965 match=True shared=10 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-race_1987.parquet] tier=M5-50MB build=carry-forward rows=256,977 depth=whole-row-multiset
#   [ok] CSV 8,862,326 B (cum this run 76,237,584)
#   rows csv=256,977 mir=256,977 match=True shared=10 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2014.parquet] tier=M5-50MB build=carry-forward rows=121,230 depth=whole-row-multiset
#   [ok] CSV 9,110,992 B (cum this run 85,348,576)
#   rows csv=121,230 mir=121,230 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [edfacts/districts_edfacts_grad_rates_2016.parquet] tier=M5-50MB build=carry-forward rows=122,320 depth=whole-row-multiset
#   [ok] CSV 9,224,915 B (cum this run 94,573,491)
#   rows csv=122,320 mir=122,320 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_ay_room_board_other.parquet] tier=M5-50MB build=fetch-fresh rows=295,709 depth=whole-row-multiset
#   [ok] CSV 9,439,375 B (cum this run 104,012,866)
#   rows csv=295,709 mir=295,709 match=True shared=8 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-retention.parquet] tier=M5-50MB build=fetch-fresh rows=278,296 depth=whole-row-multiset
#   [ok] CSV 9,965,263 B (cum this run 113,978,129)
#   rows csv=278,296 mir=278,296 match=True shared=10 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_internet_access.parquet] tier=M5-50MB build=carry-forward rows=195,585 depth=whole-row-multiset
#   [ok] CSV 10,496,756 B (cum this run 124,474,885)
#   rows csv=195,585 mir=195,585 match=True shared=10 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=-1 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1983.parquet] tier=M5-50MB build=carry-forward rows=344,181 depth=whole-row-multiset
#   [ok] CSV 11,054,234 B (cum this run 135,529,119)
#   rows csv=344,181 mir=344,181 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_sfa_by_tuition_type.parquet] tier=M5-50MB build=carry-forward rows=309,885 depth=whole-row-multiset
#   [ok] CSV 11,206,890 B (cum this run 146,736,009)
#   rows csv=309,885 mir=309,885 match=True shared=12 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1986.parquet] tier=M5-50MB build=carry-forward rows=379,227 depth=whole-row-multiset
#   [ok] CSV 12,148,775 B (cum this run 158,884,784)
#   rows csv=379,227 mir=379,227 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1990.parquet] tier=M5-50MB build=carry-forward rows=389,409 depth=whole-row-multiset
#   [ok] CSV 12,487,343 B (cum this run 171,372,127)
#   rows csv=389,409 mir=389,409 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1988.parquet] tier=M5-50MB build=carry-forward rows=398,787 depth=whole-row-multiset
#   [ok] CSV 12,758,498 B (cum this run 184,130,625)
#   rows csv=398,787 mir=398,787 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1991.parquet] tier=M5-50MB build=carry-forward rows=404,367 depth=whole-row-multiset
#   [ok] CSV 13,021,802 B (cum this run 197,152,427)
#   rows csv=404,367 mir=404,367 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_completions-6digcip_1992.parquet] tier=M5-50MB build=carry-forward rows=415,092 depth=whole-row-multiset
#   [ok] CSV 13,365,602 B (cum this run 210,518,029)
#   rows csv=415,092 mir=415,092 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_enrollment-fte.parquet] tier=M5-50MB build=fetch-fresh rows=478,066 depth=whole-row-multiset
#   [ok] CSV 15,949,794 B (cum this run 226,467,823)
#   rows csv=478,066 mir=478,066 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2020.parquet] tier=M5-50MB build=carry-forward rows=577,962 depth=whole-row-multiset
#   [ok] CSV 17,940,532 B (cum this run 244,408,355)
#   rows csv=577,962 mir=577,962 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2022.parquet] tier=M5-50MB build=fetch-fresh rows=588,150 depth=whole-row-multiset
#   [ok] CSV 18,239,410 B (cum this run 262,647,765)
#   rows csv=588,150 mir=588,150 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_py_tuition_cip.parquet] tier=M5-50MB build=fetch-fresh rows=336,814 depth=whole-row-multiset
#   [ok] CSV 19,686,331 B (cum this run 282,334,096)
#   rows csv=336,814 mir=336,814 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2016.parquet] tier=M5-50MB build=carry-forward rows=639,441 depth=whole-row-multiset
#   [ok] CSV 20,451,819 B (cum this run 302,785,915)
#   rows csv=639,441 mir=639,441 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2014.parquet] tier=M5-50MB build=carry-forward rows=668,358 depth=whole-row-multiset
#   [ok] CSV 21,372,387 B (cum this run 324,158,302)
#   rows csv=668,358 mir=668,358 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_salaries_nis.parquet] tier=M5-50MB build=fetch-fresh rows=789,768 depth=whole-row-multiset
#   [ok] CSV 22,908,547 B (cum this run 347,066,849)
#   rows csv=789,768 mir=789,768 match=True shared=6 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_sfa_by_living_arrangement.parquet] tier=M5-50MB build=carry-forward rows=739,694 depth=whole-row-multiset
#   [ok] CSV 24,147,991 B (cum this run 371,214,840)
#   rows csv=739,694 mir=739,694 match=True shared=11 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_sfa_grants_and_net_price.parquet] tier=M5-50MB build=carry-forward rows=597,920 depth=whole-row-multiset
#   [ok] CSV 29,424,340 B (cum this run 400,639,180)
#   rows csv=597,920 mir=597,920 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1986.parquet] tier=M5-50MB build=carry-forward rows=557,835 depth=whole-row-multiset
#   [ok] CSV 30,160,333 B (cum this run 430,799,513)
#   rows csv=557,835 mir=557,835 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ipeds/colleges_ipeds_fall-enrollment-age_2006.parquet] tier=M5-50MB build=carry-forward rows=1,033,938 depth=whole-row-multiset
#   [ok] CSV 32,866,858 B (cum this run 463,666,371)
#   rows csv=1,033,938 mir=1,033,938 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_finance.parquet] tier=M5-50MB build=carry-forward rows=385,134 depth=whole-row-multiset
#   [ok] CSV 36,810,986 B (cum this run 500,477,357)
#   rows csv=385,134 mir=385,134 match=True shared=15 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1987.parquet] tier=M5-50MB build=carry-forward rows=883,551 depth=whole-row-multiset
#   [ok] CSV 45,687,091 B (cum this run 546,164,448)
#   rows csv=883,551 mir=883,551 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=-1 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1989.parquet] tier=L50-200MB build=carry-forward rows=951,985 depth=whole-row-multiset
#   [ok] CSV 51,153,314 B (cum this run 597,317,762)
#   rows csv=951,985 mir=951,985 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1990.parquet] tier=L50-200MB build=carry-forward rows=998,208 depth=whole-row-multiset
#   [ok] CSV 53,577,152 B (cum this run 650,894,914)
#   rows csv=998,208 mir=998,208 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1992.parquet] tier=L50-200MB build=carry-forward rows=1,002,098 depth=whole-row-multiset
#   [ok] CSV 53,834,715 B (cum this run 704,729,629)
#   rows csv=1,002,098 mir=1,002,098 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_teacher.parquet] tier=L50-200MB build=carry-forward rows=580,719 depth=whole-row-multiset
#   [ok] CSV 64,947,329 B (cum this run 769,676,958)
#   rows csv=580,719 mir=580,719 match=True shared=22 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [nhgis/colleges_nhgis_geog_1990.parquet] tier=L50-200MB build=carry-forward rows=337,222 depth=whole-row-multiset
#   [ok] CSV 66,733,307 B (cum this run 836,410,265)
#   rows csv=337,222 mir=337,222 match=True shared=26 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_chronic_absenteeism_2021.parquet] tier=L50-200MB build=carry-forward rows=1,938,750 depth=per-column-sorted-hash
#   [ok] CSV 111,503,040 B (cum this run 947,913,305)
#   rows csv=1,938,750 mir=1,938,750 match=True shared=11 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MISMATCH colMM=1 cellMM=1 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_offerings.parquet] tier=L50-200MB build=carry-forward rows=580,719 depth=whole-row-multiset
#   [ok] CSV 124,454,154 B (cum this run 1,072,367,459)
#   rows csv=580,719 mir=580,719 match=True shared=53 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [pseo/colleges_pseo_2003.parquet] tier=L50-200MB build=carry-forward rows=1,836,090 depth=per-column-sorted-hash
#   [ok] CSV 129,594,406 B (cum this run 1,201,961,865)
#   rows csv=1,836,090 mir=1,836,090 match=True shared=18 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_chronic_absenteeism_2022.parquet] tier=L50-200MB build=carry-forward rows=2,326,989 depth=per-column-sorted-hash
#   [ok] CSV 134,280,212 B (cum this run 1,336,242,077)
#   rows csv=2,326,989 mir=2,326,989 match=True shared=11 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_disciplineinstances.parquet] tier=L50-200MB build=carry-forward rows=2,143,470 depth=per-column-sorted-hash
#   [ok] CSV 135,177,261 B (cum this run 1,471,419,338)
#   rows csv=2,143,470 mir=2,143,470 match=True shared=10 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_sat_and_act_participation_2013.parquet] tier=L50-200MB build=carry-forward rows=2,865,210 depth=per-column-sorted-hash
#   [ok] CSV 155,785,844 B (cum this run 1,627,205,182)
#   rows csv=2,865,210 mir=2,865,210 match=True shared=10 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_sat_and_act_participation_2017.parquet] tier=L50-200MB build=carry-forward rows=2,928,960 depth=per-column-sorted-hash
#   [ok] CSV 159,302,833 B (cum this run 1,786,508,015)
#   rows csv=2,928,960 mir=2,928,960 match=True shared=10 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/school-districts_lea_directory.parquet] tier=XL>200MB build=fetch-fresh rows=701,374 depth=whole-row-multiset
#   [ok] CSV 241,882,700 B (cum this run 2,028,390,715)
#   rows csv=701,374 mir=701,374 match=True shared=69 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=-1 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/districts_ccd_finance.parquet] tier=XL>200MB build=fetch-fresh rows=500,194 depth=whole-row-multiset
#   [ok] CSV 343,643,170 B (cum this run 2,372,033,885)
#   rows csv=500,194 mir=500,194 match=True shared=163 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1998.parquet] tier=XL>200MB build=carry-forward rows=11,142,090 depth=per-column-sorted-hash
#   [ok] CSV 576,471,469 B (cum this run 2,948,505,354)
#   rows csv=11,142,090 mir=11,142,090 match=True shared=9 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# === BATCH B SUMMARY ===
# shape: (2, 2)
# ┌──────────┬─────┐
# │ verdict  ┆ len │
# │ ---      ┆ --- │
# │ str      ┆ u32 │
# ╞══════════╪═════╡
# │ MATCH    ┆ 49  │
# │ MISMATCH ┆ 1   │
# └──────────┴─────┘
# MATCH(+MATCH*) = 49 / 50 batch-B files
# 
# --- MISMATCHES (verbatim) ---
# shape: (1, 5)
# ┌─────────────────────────────────┬──────────┬───────────────┬───────────────┬────────┐
# │ rel                             ┆ verdict  ┆ cols_mismatch ┆ cell_mismatch ┆ detail │
# │ ---                             ┆ ---      ┆ ---           ┆ ---           ┆ ---    │
# │ str                             ┆ str      ┆ i64           ┆ i64           ┆ str    │
# ╞═════════════════════════════════╪══════════╪═══════════════╪═══════════════╪════════╡
# │ crdc/schools_crdc_chronic_abse… ┆ MISMATCH ┆ 1             ┆ 1             ┆        │
# └─────────────────────────────────┴──────────┴───────────────┴───────────────┴────────┘
#   [crdc/schools_crdc_chronic_absenteeism_2021.parquet] column multiset hash differs col=leaid csv=hashsum=1497562156248532591 mir=hashsum=8782693728324622921
# 
# BATCH B COMPLETE (50/50 recorded).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
