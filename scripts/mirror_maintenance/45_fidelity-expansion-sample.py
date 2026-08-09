#!/usr/bin/env python3
# =============================================================================
# 45_fidelity-expansion-sample.py  (Lane A bulk-CSV parity — expansion, step 1/4)
# =============================================================================
# INTENT: Select ~100 ADDITIONAL mirror parquet files (beyond the 6 already verified
#   cell-exact in Lane A) to verify against fresh Urban bulk-CSV downloads. Produce a
#   stratified, budget-bounded sample PLAN parquet that scripts 46/47 consume, and PRINT
#   the planned composition (source x build-path x size-tier) BEFORE any download occurs.
#
# WHY THIS SAMPLING FRAME (grounded, not inferred):
#   - Universe = the 406 mirror DATA parquets in mirror_v2_tree/ (proven byte-identical to
#     the pinned HF revision, 497/497 sha256 wave-2), MINUS the 6 already verified in Lane A
#     (ccd_directory, ipeds_sfr, saipe, meps, nacubo, crdc_char).
#   - CSV URL for every file = the delta-manifest's own `urban_url`, joined on the derived
#     stem URL (rel minus .parquet -> {CSV_BASE}/{stem}.csv). A prior scratch probe confirmed
#     ALL 406 tree files match a manifest urban_url with 0 unmatched, so the stem->CSV mapping
#     is exact (incl. year-sharded files like *_2023.csv). ASSUMES that 1:1 mapping holds.
#   - Size budget uses the manifest's `current_source_bytes` (live HEAD Content-Length of the
#     CSV), so the plan's cumulative download is known before fetching. Cap ~10 GB.
#   - Build path = manifest `build_action` in {carry-forward, fetch-fresh}. The task's
#     "reference-schema-rebuilt" cohort is the 23 rebuilt by 06_c and is a subset of
#     fetch-fresh; we stratify on build_action and guarantee >= a floor of fetch-fresh.
#
# STRATIFICATION (per task):
#   - Proportional across ALL available sources (largest-remainder to 100, floor 1 each so
#     every available source is represented; single-file sources saipe/meps/nacubo are
#     already exhausted by the verified-6 and thus fall out — noted in output).
#   - Size mix favoring BREADTH: within each source pick the SMALLEST CSVs first (keeps the
#     budget wide), then GUARANTEE >= 5 large (>200 MB) files via same-source swaps so the
#     per-source counts and N=100 are preserved.
#   - Both build paths: GUARANTEE >= 8 fetch-fresh via same-source swaps.
#   - Row counts (for the per-file compare-depth decision in 46/47) read from parquet
#     metadata (num_rows) — cheap, no data load.
#
# DEPTH POLICY (recorded per file; executed in 46/47):
#   - rows <= 1_500_000  -> "whole-row-multiset"  (every column participates in the row
#                            signature; strongest, row-correlated fidelity test)
#   - rows >  1_500_000  -> "per-column-sorted-hash" (each column's sorted normalized values
#                            hashed and compared; full-column, memory-friendly for XL files)
#
# OUTPUT: 2026-08-07_urban-fidelity/45_fidelity-expansion-sample-plan.parquet
#   (rel, source, csv_url, csv_bytes, build_action, classification, tier, n_rows,
#    depth, batch)  + printed plan summary.
#
# Read-only. No downloads in THIS script. No installs. No /tmp. File-first via run_with_capture.
# =============================================================================

# --- Config ---
import polars as pl
import pyarrow.parquet as pq
import math
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
AUDIT_DIR = PROJECT_DIR / "2026-08-06_mirror-v2-audit"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_BASE = "https://educationdata.urban.org/csv"
TARGET_N = 100
BUDGET_CAP_BYTES = 10_500_000_000     # ~10 GB download budget
XL_THRESHOLD = 200_000_000            # >200 MB CSV == "large" (XL) tier boundary
MIN_XL = 5                            # guarantee >= 5 large files
MIN_FETCH_FRESH = 8                   # guarantee >= 8 fetch-fresh (both build paths)
WHOLE_ROW_MAX_ROWS = 1_500_000        # depth split threshold

# The 6 files already verified cell-exact in Lane A (exact rels from the Lane A report).
ALREADY_VERIFIED = {
    "ccd/schools_ccd_directory.parquet",
    "ipeds/colleges_ipeds_student-faculty-ratio.parquet",
    "saipe/districts_saipe.parquet",
    "meps/schools_meps.parquet",
    "nacubo/colleges_nacubo_endow.parquet",
    "crdc/schools_crdc_school_characteristics.parquet",
}

pl.Config.set_tbl_rows(60)
pl.Config.set_fmt_str_lengths(80)

# --- Load: enumerate tree data parquets + join manifest for URL/size/build-path ---
# INTENT: build the full available universe with every attribute the sample needs.
# REASONING: manifest is authoritative for CSV URL + live CSV byte size + build classification;
#   tree enumeration is authoritative for which parquets actually shipped.
parquets = sorted(p for p in TREE_DIR.rglob("*.parquet") if p.name != "build_manifest.parquet")
rows = []
for p in parquets:
    rel = str(p.relative_to(TREE_DIR))
    stem = rel[:-len(".parquet")]
    rows.append({"rel": rel, "source": rel.split("/")[0],
                 "csv_url": f"{CSV_BASE}/{stem}.csv"})
tree = pl.DataFrame(rows)

dm = pl.read_parquet(AUDIT_DIR / "2026-08-06_mirror-v2-delta-manifest.parquet")
dmd = dm.filter(pl.col("object_kind") == "data").select(
    ["urban_url", "current_source_bytes", "classification", "build_action"])
frame = tree.join(dmd, left_on="csv_url", right_on="urban_url", how="left")
assert frame.filter(pl.col("current_source_bytes").is_null()).height == 0, \
    "STOP: some tree files did not match a manifest urban_url (stem->CSV mapping broke)"
frame = frame.rename({"current_source_bytes": "csv_bytes"})

# --- Exclude the 6 already-verified files ---
# INTENT: sample only NEW files; the prior 6 are folded back in by script 48's combined verdict.
pre = frame.height
frame = frame.filter(~pl.col("rel").is_in(list(ALREADY_VERIFIED)))
print(f"Universe: {pre} data parquets; available after excluding {pre - frame.height} verified = {frame.height}")
assert pre - frame.height == 6, f"expected to drop exactly 6 verified files, dropped {pre - frame.height}"

# --- Size tier label ---
frame = frame.with_columns(
    pl.when(pl.col("csv_bytes") < 5_000_000).then(pl.lit("S<5MB"))
    .when(pl.col("csv_bytes") < 50_000_000).then(pl.lit("M5-50MB"))
    .when(pl.col("csv_bytes") < XL_THRESHOLD).then(pl.lit("L50-200MB"))
    .otherwise(pl.lit("XL>200MB")).alias("tier"))

# --- Proportional per-source allocation (largest remainder, floor 1) ---
# INTENT: every available source represented; counts proportional to source file counts.
# REASONING: largest-remainder keeps sum == TARGET_N exactly; floor 1 guarantees coverage.
src_counts = (frame.group_by("source").len().rename({"len": "avail"}).sort("source"))
sources = src_counts["source"].to_list()
avails = dict(zip(sources, src_counts["avail"].to_list()))
total_avail = sum(avails.values())

raw = {s: TARGET_N * avails[s] / total_avail for s in sources}
alloc = {s: max(1, int(math.floor(raw[s]))) for s in sources}   # floor 1 each
# reconcile to exactly TARGET_N via largest fractional remainder (respecting availability caps)
def reconcile(alloc):
    while sum(alloc.values()) != TARGET_N:
        diff = TARGET_N - sum(alloc.values())
        if diff > 0:
            # add to sources with room, largest remainder first
            cands = sorted([s for s in sources if alloc[s] < avails[s]],
                           key=lambda s: (raw[s] - alloc[s]), reverse=True)
            if not cands:
                break
            alloc[cands[0]] += 1
        else:
            # remove from sources above floor 1, smallest remainder first
            cands = sorted([s for s in sources if alloc[s] > 1],
                           key=lambda s: (raw[s] - alloc[s]))
            if not cands:
                break
            alloc[cands[0]] -= 1
    return alloc
alloc = reconcile(alloc)
print("\nPer-source allocation (proportional, floor 1):")
for s in sources:
    print(f"  {s:10s} avail={avails[s]:>3}  alloc={alloc[s]:>3}")
print(f"  TOTAL alloc = {sum(alloc.values())} (target {TARGET_N})")

# --- Within-source pick: smallest CSVs first (favor breadth/budget) ---
selected = set()
by_source = {s: frame.filter(pl.col("source") == s).sort("csv_bytes") for s in sources}
for s in sources:
    picks = by_source[s].head(alloc[s])["rel"].to_list()
    selected.update(picks)
assert len(selected) == TARGET_N, f"selection size {len(selected)} != {TARGET_N}"

relrow = {r["rel"]: r for r in frame.iter_rows(named=True)}

# --- GUARANTEE >= MIN_XL large files via same-source swaps (preserves counts + N) ---
# INTENT: ensure the sample includes real large-file coverage without inflating N.
# REASONING: swap a selected small file OUT and an unselected XL file IN within the SAME
#   source, so per-source allocation and total N are untouched. ASSUMES a source with both.
def count_xl():
    return sum(1 for r in selected if relrow[r]["csv_bytes"] >= XL_THRESHOLD)
xl_swaps = []
guard = 0
while count_xl() < MIN_XL and guard < 200:
    guard += 1
    done = False
    for s in sources:
        sel_s = [r for r in selected if relrow[r]["source"] == s]
        sel_small = sorted([r for r in sel_s if relrow[r]["csv_bytes"] < XL_THRESHOLD],
                           key=lambda r: relrow[r]["csv_bytes"])   # smallest selected small
        uns_xl = sorted([r for r in by_source[s]["rel"].to_list()
                         if r not in selected and relrow[r]["csv_bytes"] >= XL_THRESHOLD],
                        key=lambda r: relrow[r]["csv_bytes"])       # smallest unselected XL
        if sel_small and uns_xl:
            out_r, in_r = sel_small[0], uns_xl[0]
            selected.discard(out_r); selected.add(in_r)
            xl_swaps.append((s, out_r, in_r)); done = True
            break
    if not done:
        break
print(f"\nXL guarantee: {count_xl()} large files selected (min {MIN_XL}); swaps={len(xl_swaps)}")

# --- GUARANTEE >= MIN_FETCH_FRESH via same-source swaps ---
def count_ff():
    return sum(1 for r in selected if relrow[r]["build_action"] == "fetch-fresh")
ff_swaps = []
guard = 0
while count_ff() < MIN_FETCH_FRESH and guard < 200:
    guard += 1
    done = False
    for s in sources:
        sel_s = [r for r in selected if relrow[r]["source"] == s]
        sel_cf = sorted([r for r in sel_s if relrow[r]["build_action"] == "carry-forward"],
                        key=lambda r: relrow[r]["csv_bytes"], reverse=True)  # largest CF out
        uns_ff = sorted([r for r in by_source[s]["rel"].to_list()
                         if r not in selected and relrow[r]["build_action"] == "fetch-fresh"],
                        key=lambda r: relrow[r]["csv_bytes"])                 # smallest FF in
        if sel_cf and uns_ff:
            out_r, in_r = sel_cf[0], uns_ff[0]
            selected.discard(out_r); selected.add(in_r)
            ff_swaps.append((s, out_r, in_r)); done = True
            break
    if not done:
        break
print(f"fetch-fresh guarantee: {count_ff()} fetch-fresh selected (min {MIN_FETCH_FRESH}); swaps={len(ff_swaps)}")
assert len(selected) == TARGET_N, f"post-swap selection size {len(selected)} != {TARGET_N}"

# --- Budget check; if over cap, reduce via same-source small swaps ---
def total_bytes():
    return sum(relrow[r]["csv_bytes"] for r in selected)
guard = 0
while total_bytes() > BUDGET_CAP_BYTES and guard < 500:
    guard += 1
    # swap the largest selected NON-XL-guaranteed file for a smaller unselected in same source
    biggest = max((r for r in selected if relrow[r]["csv_bytes"] < XL_THRESHOLD),
                  key=lambda r: relrow[r]["csv_bytes"], default=None)
    if biggest is None:
        break
    s = relrow[biggest]["source"]
    smaller = sorted([r for r in by_source[s]["rel"].to_list()
                      if r not in selected and relrow[r]["csv_bytes"] < relrow[biggest]["csv_bytes"]],
                     key=lambda r: relrow[r]["csv_bytes"])
    if not smaller:
        break
    selected.discard(biggest); selected.add(smaller[0])
print(f"\nPlanned cumulative download: {total_bytes():,} bytes ({total_bytes()/1e9:.3f} GB); cap {BUDGET_CAP_BYTES:,}")
assert total_bytes() <= BUDGET_CAP_BYTES, f"STOP: plan {total_bytes():,} exceeds cap {BUDGET_CAP_BYTES:,}"

# --- Read row counts (parquet metadata; no data load) + assign depth ---
plan_rows = []
for r in sorted(selected):
    n_rows = pq.read_metadata(TREE_DIR / r).num_rows
    depth = "whole-row-multiset" if n_rows <= WHOLE_ROW_MAX_ROWS else "per-column-sorted-hash"
    rr = relrow[r]
    plan_rows.append({"rel": r, "source": rr["source"], "csv_url": rr["csv_url"],
                      "csv_bytes": int(rr["csv_bytes"]), "build_action": rr["build_action"],
                      "classification": rr["classification"], "tier": rr["tier"],
                      "n_rows": int(n_rows), "depth": depth})
plan = pl.from_dicts(plan_rows)

# --- Assign batch A/B: greedy bin-balance by bytes so each batch ~ half the download ---
# REASONING: 46 runs batch A, 47 runs batch B; balanced bytes -> balanced runtime, each
#   independently resumable so a Bash-timeout rerun never restarts from zero.
plan = plan.sort("csv_bytes", descending=True)
a_bytes, b_bytes, batch = 0, 0, []
for b in plan.iter_rows(named=True):
    if a_bytes <= b_bytes:
        batch.append("A"); a_bytes += b["csv_bytes"]
    else:
        batch.append("B"); b_bytes += b["csv_bytes"]
plan = plan.with_columns(pl.Series("batch", batch)).sort(["batch", "source", "rel"])
plan.write_parquet(OUT_DIR / "45_fidelity-expansion-sample-plan.parquet")

# --- Plan summary (printed BEFORE any download, per task) ---
print("\n=== SAMPLE PLAN SUMMARY (no downloads yet) ===")
print(f"N selected = {plan.height}")
print("\nsource x count + GB:")
print(plan.group_by("source").agg(pl.len().alias("n"),
      (pl.col("csv_bytes").sum() / 1e9).round(3).alias("gb")).sort("source"))
print("\nbuild_action x count + GB:")
print(plan.group_by("build_action").agg(pl.len().alias("n"),
      (pl.col("csv_bytes").sum() / 1e9).round(3).alias("gb")).sort("build_action"))
print("\nclassification x count:")
print(plan.group_by("classification").agg(pl.len().alias("n")).sort("classification"))
print("\nsize tier x count + GB:")
print(plan.group_by("tier").agg(pl.len().alias("n"),
      (pl.col("csv_bytes").sum() / 1e9).round(3).alias("gb")).sort("gb"))
print("\ndepth x count:")
print(plan.group_by("depth").agg(pl.len().alias("n")).sort("depth"))
print("\nbatch x count + GB:")
print(plan.group_by("batch").agg(pl.len().alias("n"),
      (pl.col("csv_bytes").sum() / 1e9).round(3).alias("gb")).sort("batch"))
print("\nsource x build_action crosstab:")
print(plan.pivot("build_action", index="source", values="rel", aggregate_function="len").fill_null(0).sort("source"))

# --- Validate ---
assert plan.height == TARGET_N
assert plan.filter(pl.col("tier") == "XL>200MB").height >= MIN_XL
assert plan.filter(pl.col("build_action") == "fetch-fresh").height >= MIN_FETCH_FRESH
assert plan["source"].n_unique() == len(sources), "not every available source represented"
print(f"\nVALIDATION PASSED: N={plan.height}, XL={plan.filter(pl.col('tier')=='XL>200MB').height}, "
      f"fetch-fresh={plan.filter(pl.col('build_action')=='fetch-fresh').height}, "
      f"sources={plan['source'].n_unique()}/{len(sources)}")
print("\nSingle-file sources already exhausted by the verified-6 (not in this sample): saipe, meps, nacubo")
print("\n45 COMPLETE — plan written; scripts 46/47 will download+compare batches A/B.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 19:27:33
# Command: python3 /daaf/scripts/mirror_maintenance/45_fidelity-expansion-sample.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Universe: 406 data parquets; available after excluding 6 verified = 400
# 
# Per-source allocation (proportional, floor 1):
#   ccd        avail= 80  alloc= 20
#   crdc       avail= 65  alloc= 16
#   csafety    avail=  1  alloc=  1
#   eada       avail=  1  alloc=  1
#   edfacts    avail= 42  alloc= 10
#   fsa        avail=  5  alloc=  1
#   ipeds      avail=170  alloc= 42
#   nccs       avail=  1  alloc=  1
#   nhgis      avail=  8  alloc=  2
#   pseo       avail= 21  alloc=  5
#   scorecard  avail=  6  alloc=  1
#   TOTAL alloc = 100 (target 100)
# 
# XL guarantee: 5 large files selected (min 5); swaps=4
# fetch-fresh guarantee: 15 fetch-fresh selected (min 8); swaps=0
# 
# Planned cumulative download: 5,896,889,727 bytes (5.897 GB); cap 10,500,000,000
# 
# === SAMPLE PLAN SUMMARY (no downloads yet) ===
# N selected = 100
# 
# source x count + GB:
# shape: (11, 3)
# ┌───────────┬─────┬───────┐
# │ source    ┆ n   ┆ gb    │
# │ ---       ┆ --- ┆ ---   │
# │ str       ┆ u32 ┆ f64   │
# ╞═══════════╪═════╪═══════╡
# │ ccd       ┆ 20  ┆ 1.817 │
# │ crdc      ┆ 16  ┆ 1.479 │
# │ csafety   ┆ 1   ┆ 1.071 │
# │ eada      ┆ 1   ┆ 0.027 │
# │ edfacts   ┆ 10  ┆ 0.092 │
# │ fsa       ┆ 1   ┆ 0.001 │
# │ ipeds     ┆ 42  ┆ 0.653 │
# │ nccs      ┆ 1   ┆ 0.019 │
# │ nhgis     ┆ 2   ┆ 0.152 │
# │ pseo      ┆ 5   ┆ 0.578 │
# │ scorecard ┆ 1   ┆ 0.008 │
# └───────────┴─────┴───────┘
# 
# build_action x count + GB:
# shape: (2, 3)
# ┌───────────────┬─────┬───────┐
# │ build_action  ┆ n   ┆ gb    │
# │ ---           ┆ --- ┆ ---   │
# │ str           ┆ u32 ┆ f64   │
# ╞═══════════════╪═════╪═══════╡
# │ carry-forward ┆ 85  ┆ 5.156 │
# │ fetch-fresh   ┆ 15  ┆ 0.741 │
# └───────────────┴─────┴───────┘
# 
# classification x count:
# shape: (3, 2)
# ┌────────────────────┬─────┐
# │ classification     ┆ n   │
# │ ---                ┆ --- │
# │ str                ┆ u32 │
# ╞════════════════════╪═════╡
# │ candidate-revised  ┆ 13  │
# │ new                ┆ 2   │
# │ presumed-unchanged ┆ 85  │
# └────────────────────┴─────┘
# 
# size tier x count + GB:
# shape: (4, 3)
# ┌───────────┬─────┬───────┐
# │ tier      ┆ n   ┆ gb    │
# │ ---       ┆ --- ┆ ---   │
# │ str       ┆ u32 ┆ f64   │
# ╞═══════════╪═════╪═══════╡
# │ S<5MB     ┆ 3   ┆ 0.006 │
# │ M5-50MB   ┆ 69  ┆ 1.091 │
# │ L50-200MB ┆ 23  ┆ 2.364 │
# │ XL>200MB  ┆ 5   ┆ 2.437 │
# └───────────┴─────┴───────┘
# 
# depth x count:
# shape: (2, 2)
# ┌────────────────────────┬─────┐
# │ depth                  ┆ n   │
# │ ---                    ┆ --- │
# │ str                    ┆ u32 │
# ╞════════════════════════╪═════╡
# │ per-column-sorted-hash ┆ 15  │
# │ whole-row-multiset     ┆ 85  │
# └────────────────────────┴─────┘
# 
# batch x count + GB:
# shape: (2, 3)
# ┌───────┬─────┬───────┐
# │ batch ┆ n   ┆ gb    │
# │ ---   ┆ --- ┆ ---   │
# │ str   ┆ u32 ┆ f64   │
# ╞═══════╪═════╪═══════╡
# │ A     ┆ 50  ┆ 2.948 │
# │ B     ┆ 50  ┆ 2.949 │
# └───────┴─────┴───────┘
# 
# source x build_action crosstab:
# shape: (11, 3)
# ┌───────────┬───────────────┬─────────────┐
# │ source    ┆ carry-forward ┆ fetch-fresh │
# │ ---       ┆ ---           ┆ ---         │
# │ str       ┆ u32           ┆ u32         │
# ╞═══════════╪═══════════════╪═════════════╡
# │ ccd       ┆ 18            ┆ 2           │
# │ crdc      ┆ 16            ┆ 0           │
# │ csafety   ┆ 1             ┆ 0           │
# │ eada      ┆ 1             ┆ 0           │
# │ edfacts   ┆ 10            ┆ 0           │
# │ fsa       ┆ 1             ┆ 0           │
# │ ipeds     ┆ 29            ┆ 13          │
# │ nccs      ┆ 1             ┆ 0           │
# │ nhgis     ┆ 2             ┆ 0           │
# │ pseo      ┆ 5             ┆ 0           │
# │ scorecard ┆ 1             ┆ 0           │
# └───────────┴───────────────┴─────────────┘
# 
# VALIDATION PASSED: N=100, XL=5, fetch-fresh=15, sources=11/11
# 
# Single-file sources already exhausted by the verified-6 (not in this sample): saipe, meps, nacubo
# 
# 45 COMPLETE — plan written; scripts 46/47 will download+compare batches A/B.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
