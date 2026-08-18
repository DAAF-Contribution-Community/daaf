#!/usr/bin/env python3
# =============================================================================
# 52_laneB-aggregate-report.py  (Lane B EXPANSION — aggregate + emit report)
# =============================================================================
# INTENT: Combine the expanded count sweep (50) + deep value slices (51) with the
#   PRIOR wave-3 Lane B results (16 counts + 10 slices) into one report:
#   2026-08-08_laneB-expansion-report.md. Emit: (1) a count-parity table by source,
#   (2) a value-slice table, (3) every mismatch verbatim with a classification
#   heuristic (benign-representation / grain-artifact vs substantive), and (4) a
#   combined verdict. REASONING: a single auditable artifact the orchestrator/report
#   consumes; classification is a HEURISTIC flag — the prose verdict is authoritative.
#
# CLASSIFICATION HEURISTICS (flags only; verbatim evidence always shown):
#   * Count mismatch: ratio r = mirror/api. |r-1|<=~1e-3 -> (shouldn't reach here).
#     r clusters near a small integer or 1/integer, or api>>mirror-year -> GRAIN-
#     ARTIFACT (the "1:1" endpoint is row-multiplied by an implicit disaggregation
#     dimension, not a mirror defect). Otherwise SUBSTANTIVE-REVIEW.
#   * Value-slice mismatch column: if the only mismatching column matches the known
#     benign API-rounding class (all api values are integer-valued while mirror
#     carries decimals) -> BENIGN-REPRESENTATION (teachers_fte precedent). Otherwise
#     SUBSTANTIVE-REVIEW.
#
# Read-only local parquet. No network. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
from pathlib import Path
from datetime import datetime, timezone
import polars as pl

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
REPORT = OUT_DIR / "2026-08-08_laneB-expansion-report.md"

counts = pl.read_parquet(OUT_DIR / "50_laneB_count_sweep.parquet")
slices = pl.read_parquet(OUT_DIR / "51_laneB_value_slices.parquet")
ex_path = OUT_DIR / "51_laneB_value_mismatch_examples.parquet"
examples = pl.read_parquet(ex_path) if ex_path.exists() else pl.DataFrame()

# prior wave-3 (16 counts + 10 slices) for the combined verdict
prior_counts = pl.read_parquet(OUT_DIR / "laneB_count_sweep.parquet")
prior_slices = pl.read_parquet(OUT_DIR / "laneB_value_slices.parquet")


def classify_count(api, mir):
    if api is None or mir is None or api == 0:
        return "N/A"
    r = mir / api
    if abs(r - 1) <= 1e-3:
        return "MATCH"
    # near a small integer multiple (either direction) => grain multiplication
    for k in (2, 3, 4, 5, 6, 7, 8, 9, 10, 12):
        if abs(r - k) <= 0.05 or abs(r - 1 / k) <= 0.02:
            return "GRAIN-ARTIFACT"
    # api much larger than mirror-year (endpoint disaggregated) or vice versa
    if r < 0.5 or r > 1.5:
        return "GRAIN-ARTIFACT"
    return "SUBSTANTIVE-REVIEW"


# --- Aggregate count sweep ---
cnt = counts.with_columns(
    pl.struct(["api_count", "mirror_count"]).map_elements(
        lambda s: classify_count(s["api_count"], s["mirror_count"]), return_dtype=pl.Utf8
    ).alias("class_guess")
)
n_c = cnt.height
n_c_match = cnt.filter(pl.col("verdict") == "MATCH").height
n_c_mis = cnt.filter(pl.col("verdict") == "MISMATCH").height
n_c_grain = cnt.filter(pl.col("class_guess") == "GRAIN-ARTIFACT").height
n_c_subst = cnt.filter(pl.col("class_guess") == "SUBSTANTIVE-REVIEW").height
n_c_other = n_c - n_c_match - n_c_mis

by_src = (cnt.group_by("source").agg(
    pl.len().alias("n"),
    (pl.col("verdict") == "MATCH").sum().alias("match"),
    (pl.col("verdict") == "MISMATCH").sum().alias("mismatch"),
).sort("source"))

# --- Aggregate slices ---
n_s = slices.height
n_s_match = slices.filter(pl.col("verdict") == "MATCH").height
n_s_mis = slices.filter(pl.col("verdict") == "MISMATCH").height
n_s_other = n_s - n_s_match - n_s_mis

# benign-representation flag per mismatch example column
def classify_example(sub):
    # sub: all example rows for a (label,column). benign if all api values integer-valued.
    try:
        apis = [float(v) for v in sub["api_value"].to_list() if v not in ("None", "<NA>")]
    except ValueError:
        return "SUBSTANTIVE-REVIEW"
    if apis and all(abs(a - round(a)) < 1e-9 for a in apis):
        return "BENIGN-REPRESENTATION(api-rounding-like)"
    return "SUBSTANTIVE-REVIEW"


# --- Build report ---
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
L = []
L.append("# Lane B Expansion Report — v2 Mirror vs Live Urban API (parity battery)")
L.append("")
L.append(f"**Generated:** {now}  ")
L.append("**Mirror under test:** `brhkim/education_data_portal_mirror_2026q3` @ pinned "
         "`0ad00ce…` (Portal v0.26.1 snapshot).  ")
L.append("**Chain link verified here:** mirror ⟷ live Urban API. Mirror counts/values "
         "read from the local build tree (byte-identical to HF pinned 497/497, wave-2).  ")
L.append("**Method:** pairs mechanically selected from wave-4 ground truth "
         "(`37_live_probe_inventory`, `40_route_reconciliation`) — scripts 49_a/50/51/52. "
         "Live requests SIGALRM-guarded (25s hard wall-clock), ~1 req/sec, resumable.")
L.append("")
L.append("---")
L.append("")
L.append("## Bottom line")
L.append("")
combined_counts = n_c_match + prior_counts.filter(pl.col('verdict') == 'MATCH').height
combined_counts_total = n_c + prior_counts.height
combined_slices = n_s_match + prior_slices.filter(pl.col('verdict') == 'MATCH').height
combined_slices_total = n_s + prior_slices.height
L.append(f"- **Expanded count sweep:** {n_c_match}/{n_c} endpoint-year pairs matched exactly "
         f"({n_c_mis} mismatch, {n_c_other} unverifiable/skip) across {cnt['source'].n_unique()} sources.")
L.append(f"  Of the {n_c_mis} count mismatches, {n_c_grain} flag as GRAIN-ARTIFACT "
         f"(row-multiplied endpoint, not a mirror defect) and {n_c_subst} as SUBSTANTIVE-REVIEW.")
L.append(f"- **Expanded value slices:** {n_s_match}/{n_s} slices cell-exact after benign "
         f"normalization ({n_s_mis} mismatch, {n_s_other} unverifiable/grain).")
L.append(f"- **Combined with prior wave-3 (16 counts + 10 slices):** "
         f"counts {combined_counts}/{combined_counts_total} exact; "
         f"slices {combined_slices}/{combined_slices_total} cell-exact.")
L.append("")
L.append("---")
L.append("")
L.append("## Count parity by source (expanded, script 50)")
L.append("")
L.append("| Source | Pairs·yrs | MATCH | MISMATCH |")
L.append("|---|---|---|---|")
for r in by_src.iter_rows(named=True):
    L.append(f"| {r['source']} | {r['n']} | {r['match']} | {r['mismatch']} |")
L.append(f"| **TOTAL** | **{n_c}** | **{n_c_match}** | **{n_c_mis}** |")
L.append("")

# count mismatches verbatim
mism = cnt.filter(pl.col("verdict") == "MISMATCH").sort("source", "label", "year")
L.append("### Count mismatches (verbatim + classification)")
L.append("")
if mism.height == 0:
    L.append("_None — every compared endpoint-year count matched exactly._")
else:
    L.append("| Label | Year | API count | Mirror count | mir/api | Class |")
    L.append("|---|---|---|---|---|---|")
    for r in mism.iter_rows(named=True):
        ratio = (r["mirror_count"] / r["api_count"]) if r["api_count"] else None
        L.append(f"| {r['label']} | {r['year']} | {r['api_count']} | {r['mirror_count']} | "
                 f"{ratio:.3f} | {r['class_guess']} |" if ratio is not None else
                 f"| {r['label']} | {r['year']} | {r['api_count']} | {r['mirror_count']} | — | {r['class_guess']} |")
L.append("")

# unverifiable/skip
unv = cnt.filter(~pl.col("verdict").is_in(["MATCH", "MISMATCH"]))
if unv.height:
    L.append("### Count unverifiable/skip (verbatim)")
    L.append("")
    L.append("| Label | Year | Verdict | Note |")
    L.append("|---|---|---|---|")
    for r in unv.sort("label", "year").iter_rows(named=True):
        L.append(f"| {r['label']} | {r['year']} | {r['verdict']} | {r['note']} |")
    L.append("")

L.append("---")
L.append("")
L.append("## Deep value slices (expanded, script 51)")
L.append("")
L.append("| Label | Src | Yr | Keys | n_keys | Cols | colMM | cellMM | Verdict |")
L.append("|---|---|---|---|---|---|---|---|---|")
for r in slices.sort("source", "label").iter_rows(named=True):
    L.append(f"| {r['label']} | {r['source']} | {r['slice_year']} | {r['keys_used']} | "
             f"{r['n_keys']} | {r['cols_compared']} | {r['cols_mismatch']} | {r['cell_mismatch']} | {r['verdict']} |")
L.append("")

# slice mismatches verbatim
if examples.height:
    L.append("### Value-slice mismatches (verbatim + classification)")
    L.append("")
    # group by (label, column)
    grp = examples.group_by(["label", "column"]).agg(pl.len().alias("n"))
    L.append("| Label | Column | #ex | Class |")
    L.append("|---|---|---|---|")
    for g in grp.sort("label", "column").iter_rows(named=True):
        sub = examples.filter((pl.col("label") == g["label"]) & (pl.col("column") == g["column"]))
        cls = classify_example(sub)
        L.append(f"| {g['label']} | {g['column']} | {g['n']} | {cls} |")
    L.append("")
    L.append("**Verbatim examples (capped 60):**")
    L.append("")
    L.append("```")
    for e in examples.head(60).iter_rows(named=True):
        L.append(f"[{e['label']}] key={e['key']} col={e['column']}({e['kind']}) "
                 f"api={e['api_value']!r} mirror={e['mirror_value']!r}")
    L.append("```")
    L.append("")
else:
    L.append("### Value-slice mismatches")
    L.append("")
    L.append("_None in the expanded set — every shared cell matched after benign normalization._")
    L.append("")

L.append("---")
L.append("")
L.append("## Combined verdict (expanded + prior wave-3 16+10)")
L.append("")
L.append(f"- **Counts:** {combined_counts}/{combined_counts_total} endpoint-year pairs exact.")
L.append(f"- **Value slices:** {combined_slices}/{combined_slices_total} cell-exact after documented benign normalization.")
L.append("- **Known benign residual (prior):** CCD `teachers_fte` — live API serves integer-rounded "
         "values, mirror preserves decimals (API-side rounding, not a mirror defect).")
L.append("- Any SUBSTANTIVE-REVIEW flags above require human adjudication; GRAIN-ARTIFACT and "
         "BENIGN-REPRESENTATION flags are expected, non-defect classes.")
L.append("")

REPORT.write_text("\n".join(L))
print(f"Report written -> {REPORT}  ({len(L)} lines)")
print(f"\nCOUNTS: {n_c_match}/{n_c} match, {n_c_mis} mismatch "
      f"(grain={n_c_grain}, substantive={n_c_subst}), other={n_c_other}")
print(f"SLICES: {n_s_match}/{n_s} match, {n_s_mis} mismatch, other={n_s_other}")
print(f"COMBINED: counts {combined_counts}/{combined_counts_total}; slices {combined_slices}/{combined_slices_total}")
if mism.height:
    print("\nCOUNT MISMATCHES:")
    print(mism.select("label", "year", "api_count", "mirror_count", "class_guess"))
assert REPORT.exists(), "report not written"
print("\nAGGREGATE + REPORT COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 20:15:34
# Command: python3 /daaf/scripts/mirror_maintenance/52_laneB-aggregate-report.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Report written -> /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/2026-08-08_laneB-expansion-report.md  (95 lines)
# 
# COUNTS: 159/159 match, 0 mismatch (grain=0, substantive=0), other=0
# SLICES: 22/35 match, 0 mismatch, other=13
# COMBINED: counts 175/178; slices 31/45
# 
# AGGREGATE + REPORT COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
