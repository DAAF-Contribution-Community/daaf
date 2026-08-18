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
# REVISION 47_a: added "." (Urban's SAS-style CSV missing marker) to the missing-token
# vocabulary. Batch B flagged crdc/schools_crdc_chronic_absenteeism_2021 as MISMATCH on
# `leaid`; a scratch investigation proved it a HARNESS artifact, not a mirror defect: 5,673
# rows carry leaid="." in the bulk CSV (Urban exports missing from SAS as ".") which the
# mirror correctly converted to null. The original token set omitted ".", so "." zfilled to
# "000000." instead of unifying with the mirror's null (multiset imbalance was 0 — the 5,673
# "." corresponded exactly to 5,673 nulls; nunique 17605==17605; rows identical). Adding "."
# is the correct, generalizing fix (numeric columns already null-out ".", so this only affects
# string/id columns that use "." as a missing marker).
MISSING_TOKENS = ["-1", "-2", "-3", "", "-1.0", "-2.0", "-3.0", ".", "-1.", "-2.", "-3."]
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
            # REVISION 47_a BUGFIX: group_by().len() returns UInt32; the original
            # (n_csv - n_mir) subtracted two u32 cols and UNDERFLOWED, so a balanced
            # swapped-pair imbalance (+1 and 4294967295) summed to exactly 0 (mod 2^32),
            # masking real whole-row differences as cell_mismatch=0 -> false MATCH. Cast
            # to Int64 BEFORE the difference so the abs-sum is a true signed count.
            rec["cell_mismatch"] = int(bad.select(
                (pl.col("n_csv").cast(pl.Int64) - pl.col("n_mir").cast(pl.Int64)).abs().sum()).item())
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
# Executed: 2026-08-08 19:43:39
# Command: python3 /daaf/scripts/mirror_maintenance/47_fidelity-expansion-compare-batchB_a.py
# Duration: 28s
# Exit code: 0
#
# --- STDOUT ---
# === FIDELITY EXPANSION — BATCH B: 50 files (2.949 GB planned) ===
# Resuming: 46 files already recorded in 46_fidelity-expansion-results-batchB.parquet
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_internet_access.parquet] tier=M5-50MB build=carry-forward rows=195,585 depth=whole-row-multiset
#   [ok] CSV 10,496,756 B (cum this run 10,496,756)
#   rows csv=195,585 mir=195,585 match=True shared=10 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/schools_ccd_enrollment_1987.parquet] tier=M5-50MB build=carry-forward rows=883,551 depth=whole-row-multiset
#   [ok] CSV 45,687,091 B (cum this run 56,183,847)
#   rows csv=883,551 mir=883,551 match=True shared=9 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
#   VERDICT=MISMATCH colMM=-1 cellMM=1453492 
# 
# ------------------------------------------------------------------------
# [crdc/schools_crdc_chronic_absenteeism_2021.parquet] tier=L50-200MB build=carry-forward rows=1,938,750 depth=per-column-sorted-hash
#   [ok] CSV 111,503,040 B (cum this run 167,686,887)
#   rows csv=1,938,750 mir=1,938,750 match=True shared=11 csv_only=[] mir_only=[]
#   method=per-column-multiset-hash (order-independent sum of element hashes)
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [ccd/school-districts_lea_directory.parquet] tier=XL>200MB build=fetch-fresh rows=701,374 depth=whole-row-multiset
#   [ok] CSV 241,882,700 B (cum this run 409,569,587)
#   rows csv=701,374 mir=701,374 match=True shared=69 csv_only=[] mir_only=[]
#   method=whole-row-multiset (group_by all shared cols)
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
# │ ccd/schools_ccd_enrollment_198… ┆ MISMATCH ┆ -1            ┆ 1453492       ┆        │
# └─────────────────────────────────┴──────────┴───────────────┴───────────────┴────────┘
#   [ccd/schools_ccd_enrollment_1987.parquet] year=1987; ncessch=<NA>; leaid=1721450; fips=17 col=<whole-row> csv=n_csv=0 mir=n_mir=1
#   [ccd/schools_ccd_enrollment_1987.parquet] year=1987; ncessch=<NA>; leaid=5303960; fips=53 col=<whole-row> csv=n_csv=0 mir=n_mir=1
#   [ccd/schools_ccd_enrollment_1987.parquet] year=1987; ncessch=<NA>; leaid=1709930; fips=17 col=<whole-row> csv=n_csv=0 mir=n_mir=4
# 
# BATCH B COMPLETE (50/50 recorded).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
