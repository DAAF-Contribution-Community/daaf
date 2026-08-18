#!/usr/bin/env python3
# =============================================================================
# 48_fidelity-expansion-aggregate-report.py  (Lane A bulk-CSV parity — expansion, step 4/4)
# =============================================================================
# INTENT: Aggregate the batch-A (46) and batch-B (47) per-file comparison results with the
#   6 files verified in the original Lane A run, and emit the deliverable Markdown report
#   `2026-08-08_urban-fidelity-expansion-report.md`: a per-file table (source, build path,
#   rows, depth, normalizations, MATCH/MISMATCH), every MISMATCH verbatim with keys, and the
#   combined verdict over all 106 files.
#
# REASONING: the report is generated PROGRAMMATICALLY from the checkpoint parquets (not hand-
#   written), so it is reproducible and grounded in the recorded evidence. Build-path labels
#   for the prior 6 are recovered by joining their rels to the delta-manifest (same authoritative
#   source script 45 used), not guessed.
#
# Read-only (reads result parquets + manifest). No downloads. No installs. No /tmp. File-first.
# =============================================================================

# --- Config ---
import polars as pl
from pathlib import Path
import datetime

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
AUDIT_DIR = PROJECT_DIR / "2026-08-06_mirror-v2-audit"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
REPORT_FP = OUT_DIR / "2026-08-08_urban-fidelity-expansion-report.md"
COMBINED_FP = OUT_DIR / "48_fidelity-expansion-combined.parquet"

NORMALIZATIONS = ("id zero-pad (ncessch->12, leaid->7) + strip trailing '.0'; "
                  "numeric cast Float64 round 4dp; unify missing {null,\"\",-1,-2,-3,'.'}->sentinel")

# Adjudicated findings (raw verdict kept in the parquet; narrative + status set here from a
# documented scratch investigation whose evidence is quoted in the report).
ADJUDICATIONS = {
    "ccd/schools_ccd_enrollment_1987.parquet": {
        "status": "MIRROR-FAITHFUL (Urban current-CSV defect)",
        "evidence": ("Only ncessch/ncessch_num differ; the other 7 columns (year, leaid, fips, "
                     "grade, race, sex, enrollment) match cell-exact. The MIRROR holds clean "
                     "Int64 school IDs (13,247 distinct); Urban's CURRENT bulk CSV export has "
                     "scientific-notation corruption in ncessch/ncessch_num (e.g. '00000002E+11', "
                     "'000001.3E+11', '000002.2E+11'), inflating ncessch to 25,955 spurious "
                     "distinct tokens. The mirror carried forward the correct integer IDs from "
                     "the prior vintage -> an Urban CSV-EXPORT defect on this 1987 file, NOT a "
                     "mirror conversion defect. The mirror is faithful (and cleaner than the "
                     "current CSV)."),
    },
}

pl.Config.set_tbl_rows(120)

# --- Load batch A + B expansion results ---
frames = []
for b in ("A", "B"):
    # NOTE: both batch harnesses (46, 47_a) write their result parquet with the "46_" prefix
    # (shared f-string); batch is distinguished by the trailing A/B, not the numeric prefix.
    fp = OUT_DIR / f"46_fidelity-expansion-results-batch{b}.parquet"
    assert fp.exists(), f"missing {fp}"
    frames.append(pl.read_parquet(fp))
exp = pl.concat(frames, how="vertical_relaxed")
print(f"Expansion results loaded: {exp.height} files (expect 100)")

# --- Load the 6 prior Lane A results; join manifest for build_action/source ---
prior = pl.read_parquet(OUT_DIR / "laneA_conversion_fidelity.parquet")
dm = pl.read_parquet(AUDIT_DIR / "2026-08-06_mirror-v2-delta-manifest.parquet").filter(
    pl.col("object_kind") == "data")
CSV_BASE = "https://educationdata.urban.org/csv"
prior = prior.with_columns([
    pl.col("mirror_rel").alias("rel"),
    pl.col("mirror_rel").str.split("/").list.first().alias("source"),
    (pl.lit(CSV_BASE + "/") + pl.col("mirror_rel").str.replace(r"\.parquet$", "") + ".csv").alias("csv_url"),
])
prior = prior.join(dm.select(["urban_url", "build_action", "classification"]),
                   left_on="csv_url", right_on="urban_url", how="left")
prior_norm = prior.select([
    pl.col("rel"), pl.col("source"), pl.col("build_action"),
    pl.col("classification"),
    pl.lit("PRIOR").alias("tier"),
    pl.col("compare_mode").alias("compare_method"),
    pl.col("csv_rows").alias("n_rows"),
    pl.col("csv_rows"), pl.col("mirror_rows"), pl.col("row_match"),
    pl.col("shared_cols"), pl.col("csv_only_cols"), pl.col("mirror_only_cols"),
    pl.col("cols_mismatch"), pl.col("cell_mismatch"), pl.col("verdict"),
    pl.lit("Lane A original (script 22_a)").alias("detail"),
    pl.lit(0).cast(pl.Int64).alias("csv_bytes"),
    pl.lit("prior").alias("cohort"),
])

exp_norm = exp.select([
    pl.col("rel"), pl.col("source"), pl.col("build_action"), pl.col("classification"),
    pl.col("tier"), pl.col("compare_method"), pl.col("csv_rows").alias("n_rows"),
    pl.col("csv_rows"), pl.col("mirror_rows"), pl.col("row_match"),
    pl.col("shared_cols"), pl.col("csv_only_cols"), pl.col("mirror_only_cols"),
    pl.col("cols_mismatch"), pl.col("cell_mismatch"), pl.col("verdict"), pl.col("detail"),
    pl.col("csv_bytes"), pl.lit("expansion").alias("cohort"),
])

combined = pl.concat([exp_norm, prior_norm], how="vertical_relaxed").sort(["cohort", "source", "rel"])
combined.write_parquet(COMBINED_FP)

# --- Load mismatch examples (if any) ---
ex_rows = []
for b in ("A", "B"):
    efp = OUT_DIR / f"46_fidelity-expansion-mismatches-batch{b}.parquet"
    if efp.exists():
        ex_rows.append(pl.read_parquet(efp))
examples = pl.concat(ex_rows, how="vertical_relaxed") if ex_rows else None

# --- Counts (defined before tallies/adjudication use them) ---
n_new = exp_norm.height
n_all = combined.height

# --- Tallies ---
def tally(df):
    return {v: df.filter(pl.col("verdict") == v).height
            for v in ["MATCH", "MATCH*", "MISMATCH", "UNVERIFIABLE-TODAY"]}
t_exp = tally(exp_norm)
t_all = tally(combined)
mism = combined.filter(pl.col("verdict") == "MISMATCH")
unver = combined.filter(pl.col("verdict") == "UNVERIFIABLE-TODAY")
mism_rels = set(mism["rel"].to_list())
adjudicated_rels = set(ADJUDICATIONS.keys()) & mism_rels
unresolved_rels = mism_rels - adjudicated_rels
n_faithful_all = n_all - len(unresolved_rels)   # adjudicated-benign count as mirror-faithful

print("Expansion tally:", t_exp)
print("Combined tally:", t_all)

# --- Compose Markdown report ---
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
L = []
L.append("# Urban Fidelity Report — Lane A Expansion (mirror parquet vs Urban bulk CSVs)")
L.append("")
L.append(f"**Generated:** {now} (programmatically by `scripts/mirror_maintenance/48_fidelity-expansion-aggregate-report.py`)")
L.append("**Companion to:** `2026-08-07_urban-fidelity-laneA-report.md` (original 6-file Lane A run).")
L.append("**Mirror under test:** `brhkim/education_data_portal_mirror_2026q3` @ pinned "
         "`0ad00ce0e232c96b0642459e4e7326607a8d26aa` (Portal v0.26.1 snapshot).")
L.append("**Mirror equivalence:** compared against the local build tree `mirror_v2_tree/`, "
         "proven byte-identical to the pinned HF revision (497/497 sha256, wave-2). "
         "Comparing the freshly-downloaded bulk CSV against the local parquet **is** comparing "
         "it against the shipped mirror.")
L.append("")
L.append("## Bottom-line verdict")
L.append("")
n_new = exp_norm.height
n_new_match = t_exp["MATCH"] + t_exp["MATCH*"]
n_all = combined.height
n_all_match = t_all["MATCH"] + t_all["MATCH*"]
total_rows = int(exp_norm["csv_rows"].fill_null(0).sum())
verdict_word = "faithful" if (t_all["MISMATCH"] == 0) else "NOT uniformly faithful"
L.append(f"Across **{n_new} newly-sampled files** (stratified over all 11 non-exhausted sources, "
         f"both build paths, a size mix favoring breadth with {combined.filter((pl.col('cohort')=='expansion') & (pl.col('tier')=='XL>200MB')).height} large >200MB files), "
         f"**{n_new_match}/{n_new} matched** the current Urban bulk CSV cell-exact after documented "
         f"benign normalization ({NORMALIZATIONS}). Combined with the original 6 Lane A files, "
         f"**{n_all_match}/{n_all}** mirror files are verified faithful to their Urban bulk-CSV build input.")
if adjudicated_rels:
    L.append(f"\n**{len(adjudicated_rels)} raw MISMATCH adjudicated to MIRROR-FAITHFUL**: "
             f"{', '.join('`'+r+'`' for r in sorted(adjudicated_rels))} — the divergence is a "
             f"defect in Urban's *current* bulk CSV, not in the mirror (evidence in the Mismatches "
             f"section). Counting adjudicated files as faithful, **{n_faithful_all}/{n_all}** mirror "
             f"files are verified faithful.")
if unresolved_rels:
    L.append(f"\n**{len(unresolved_rels)} UNRESOLVED MISMATCH(es)** — see the Mismatches section (verbatim).")
if t_exp["UNVERIFIABLE-TODAY"]:
    L.append(f"\n**{t_exp['UNVERIFIABLE-TODAY']} file(s) UNVERIFIABLE today** (download failure) — "
             f"listed below; rerun 46/47 to resume (resumable checkpoints).")
L.append("")
_hi = (len(unresolved_rels) == 0 and t_all["UNVERIFIABLE-TODAY"] == 0)
L.append(f"**Combined mirror ⟷ Urban conversion fidelity: {'HIGH' if _hi else 'SEE FINDINGS'}.**")
L.append("")

# --- Composition summary ---
L.append("## Sample composition (expansion cohort, N=100)")
L.append("")
def md_table(df, cols, headers):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in df.iter_rows(named=True):
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return out
src_tab = (exp_norm.group_by("source").agg(
    pl.len().alias("n"), (pl.col("csv_bytes").sum() / 1e9).round(3).alias("csv_gb")).sort("source"))
L += md_table(src_tab, ["source", "n", "csv_gb"], ["source", "n files", "CSV GB"])
L.append("")
ba_tab = exp_norm.group_by("build_action").agg(pl.len().alias("n")).sort("build_action")
L += md_table(ba_tab, ["build_action", "n"], ["build path", "n files"])
L.append("")
tier_tab = exp_norm.group_by("tier").agg(pl.len().alias("n")).sort("tier")
L += md_table(tier_tab, ["tier", "n"], ["size tier", "n files"])
L.append("")
depth_tab = exp_norm.group_by("compare_method").agg(pl.len().alias("n")).sort("compare_method")
L += md_table(depth_tab, ["compare_method", "n"], ["compare depth/method", "n files"])
L.append("")
L.append(f"**Normalizations applied to every file (both sides, benign):** {NORMALIZATIONS}.")
L.append("")
L.append("Depth policy: files with <=1.5M rows compared via **whole-row multiset** (group-by over "
         "all shared columns; every cell participates in the row signature); files with >1.5M rows "
         "compared via **per-column multiset hash** (order-independent sum of Polars element hashes "
         "per column; equivalent to comparing sorted values, memory-friendly for XL files) plus "
         "row-count and column-set parity.")
L.append("")

# --- Mismatches / unverifiable ---
L.append("## Mismatches")
L.append("")
if mism.height == 0:
    L.append("**None.** Every compared file matched cell-exact (0 residual cell/column mismatches, "
             "row counts identical, column sets identical) after normalization.")
else:
    L += md_table(mism.select(["rel", "source", "build_action", "cols_mismatch", "cell_mismatch", "detail"]),
                  ["rel", "source", "build_action", "cols_mismatch", "cell_mismatch", "detail"],
                  ["file", "source", "build path", "col MM", "cell MM", "detail"])
    L.append("")
    for r in sorted(adjudicated_rels):
        a = ADJUDICATIONS[r]
        L.append(f"**Adjudication — `{r}` → {a['status']}:** {a['evidence']}")
        L.append("")
    if unresolved_rels:
        L.append(f"**Unresolved mismatches requiring follow-up:** "
                 f"{', '.join('`'+r+'`' for r in sorted(unresolved_rels))}.")
        L.append("")
    if examples is not None and examples.height:
        L.append("### Mismatch row signatures (verbatim, from the harness examples parquet)")
        for e in examples.filter(pl.col("rel").is_in(list(mism_rels))).iter_rows(named=True):
            L.append(f"- `{e['rel']}` — {e['signature']} col=`{e['column']}` "
                     f"csv={e['csv_value']} mirror={e['mirror_value']}")
L.append("")
if unver.height:
    L.append("### Unverifiable today (download failure — rerun to resume)")
    L += md_table(unver.select(["rel", "source", "detail"]), ["rel", "source", "detail"],
                  ["file", "source", "detail"])
    L.append("")

# --- Full per-file table ---
L.append("## Per-file results (all 106: 100 expansion + 6 prior)")
L.append("")
full = combined.select([
    pl.col("rel").alias("file"), pl.col("source"), pl.col("build_action").alias("build_path"),
    pl.col("csv_rows").alias("rows"), pl.col("shared_cols").alias("cols"),
    pl.col("compare_method").alias("depth"), pl.col("verdict"),
    pl.col("cell_mismatch").alias("cellMM"), pl.col("cohort"),
]).sort(["cohort", "source", "file"])
L += md_table(full, ["file", "source", "build_path", "rows", "cols", "depth", "verdict", "cellMM"],
              ["file", "source", "build path", "rows", "cols", "depth", "verdict", "cellMM"])
L.append("")
L.append("## Artifacts")
L.append("- Scripts: `45_fidelity-expansion-sample.py`, `46_fidelity-expansion-compare-batchA.py`, "
         "`47_fidelity-expansion-compare-batchB.py`, `48_fidelity-expansion-aggregate-report.py` "
         "(all with execution logs appended).")
L.append("- Data: `45_fidelity-expansion-sample-plan.parquet`, "
         "`46_fidelity-expansion-results-batchA.parquet`, `47_fidelity-expansion-results-batchB.parquet`, "
         "`48_fidelity-expansion-combined.parquet`" +
         (", mismatch example parquets" if (examples is not None) else "") + ".")
L.append("- Downloaded CSVs were deleted immediately after each comparison (disk-hygiene deviation, "
         "orchestrator-approved); the result parquets + appended execution logs are the provenance record.")

REPORT_FP.write_text("\n".join(L) + "\n")

# --- Summary ---
print(f"\nReport written: {REPORT_FP}")
print(f"Combined parquet: {COMBINED_FP}")
print(f"Expansion: {n_new_match}/{n_new} MATCH(+MATCH*); MISMATCH={t_exp['MISMATCH']}; UNVERIFIABLE={t_exp['UNVERIFIABLE-TODAY']}")
print(f"Combined (incl prior 6): {n_all_match}/{n_all} MATCH(+MATCH*); MISMATCH={t_all['MISMATCH']}")
assert exp_norm.height == 100, f"expected 100 expansion files, got {exp_norm.height}"
print("\n48 COMPLETE.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 19:47:47
# Command: python3 /daaf/scripts/mirror_maintenance/48_fidelity-expansion-aggregate-report_b.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# Expansion results loaded: 100 files (expect 100)
# Expansion tally: {'MATCH': 99, 'MATCH*': 0, 'MISMATCH': 1, 'UNVERIFIABLE-TODAY': 0}
# Combined tally: {'MATCH': 105, 'MATCH*': 0, 'MISMATCH': 1, 'UNVERIFIABLE-TODAY': 0}
# 
# Report written: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/2026-08-08_urban-fidelity-expansion-report.md
# Combined parquet: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/48_fidelity-expansion-combined.parquet
# Expansion: 99/100 MATCH(+MATCH*); MISMATCH=1; UNVERIFIABLE=0
# Combined (incl prior 6): 105/106 MATCH(+MATCH*); MISMATCH=1
# 
# 48 COMPLETE.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
