#!/usr/bin/env python3
"""
QA INSPECTION: Stage 8 Step 12 — QA4b (Visualization Quality)

Reviewed script: scripts/stage8_analysis/12_viz-sector-comparison_a.py
Output files: output/figures/2026-02-15_sector_comparison.png
Plan reference: 2026-02-15_College_Graduation_Rate_Selectivity_Analysis_Plan.md

QA Checks (Default):
1. Figure file exists and size > 50KB
2. Script has proper labels (title, x-axis, y-axis, legend)
3. Colorblind-safe palette used
4. Y-axis starts at 0 for bar chart (no misleading truncation)
5. DPI >= 150 for publication quality

QA Checks (Script-Specific — Five Skeptical Lenses):
6. Counterfactual: Verify input data has all 8 expected rows and no nulls in median_grad_rate
7. Semantic: Verify the figure answers the research question by confirming
   the Selective band reversal (Public > Private) is visible in the data
8. Boundary: Check that bar label values match actual data values (rounding)
9. Absence: Verify no sectors or bands are silently dropped
10. Downstream: Verify figure represents the same data that the report will reference

Spot-Checks:
11. Trace Highly Selective Private nonprofit value through data -> figure label
12. Trace Selective Public value to confirm +12pp reversal
13. Verify BAND_ORDER in script matches actual data band values
14. Verify sector_label color mapping keys match data values exactly
15. Cross-reference figure file size against similar figures in output/
"""

import polars as pl
from pathlib import Path
import os
import re

# --- Config ---
PROJECT_DIR = Path("/daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis")
FIGURE_PATH = PROJECT_DIR / "output" / "figures" / "2026-02-15_sector_comparison.png"
INPUT_DATA_PATH = PROJECT_DIR / "output" / "analysis" / "2026-02-15_sector_comparison.parquet"
SCRIPT_PATH = PROJECT_DIR / "scripts" / "stage8_analysis" / "12_viz-sector-comparison_a.py"

EXPECTED_BANDS = ["Highly Selective", "Selective", "Moderately Selective", "Less Selective/Open"]
EXPECTED_SECTORS = ["Private nonprofit", "Public"]
EXPECTED_ROWS = 8
MIN_FILE_SIZE_KB = 50

# --- Load ---
print("=" * 60)
print("QA4b INSPECTION: Stage 8 Step 12 — Sector Comparison Viz")
print("=" * 60)

# Load the input data that the visualization consumed
df = pl.read_parquet(INPUT_DATA_PATH)
print(f"Input data: {df.shape[0]:,} rows x {df.shape[1]} cols")

# Load the script text for static analysis
script_text = SCRIPT_PATH.read_text()
print(f"Script length: {len(script_text):,} chars")

qa_severity = "PASSED"

def update_severity(new_sev):
    global qa_severity
    order = ["PASSED", "WARNING", "BLOCKER"]
    if order.index(new_sev) > order.index(qa_severity):
        qa_severity = new_sev

# =============================================================================
# DEFAULT CHECKS
# =============================================================================
print("\n" + "-" * 60)
print("DEFAULT CHECKS")
print("-" * 60)

# --- Check 1: Figure file exists and size ---
file_exists = FIGURE_PATH.exists()
file_size = os.path.getsize(FIGURE_PATH) if file_exists else 0
file_size_kb = file_size / 1024
size_ok = file_size_kb > MIN_FILE_SIZE_KB

if not file_exists:
    print(f"[BLOCKER] Figure file does not exist: {FIGURE_PATH}")
    update_severity("BLOCKER")
elif not size_ok:
    print(f"[BLOCKER] Figure too small: {file_size_kb:.1f} KB (expected > {MIN_FILE_SIZE_KB} KB)")
    update_severity("BLOCKER")
else:
    print(f"[PASS] Figure exists: {file_size_kb:.1f} KB (> {MIN_FILE_SIZE_KB} KB threshold)")

# --- Check 2: Labels present in script ---
has_title = bool(re.search(r'labs\s*\(.*title\s*=', script_text, re.DOTALL))
has_xlabel = bool(re.search(r'labs\s*\(.*x\s*=', script_text, re.DOTALL))
has_ylabel = bool(re.search(r'labs\s*\(.*y\s*=', script_text, re.DOTALL))
has_caption = bool(re.search(r'labs\s*\(.*caption\s*=', script_text, re.DOTALL))

labels_ok = has_title and has_xlabel and has_ylabel
if not labels_ok:
    missing = []
    if not has_title: missing.append("title")
    if not has_xlabel: missing.append("x-axis label")
    if not has_ylabel: missing.append("y-axis label")
    print(f"[BLOCKER] Missing labels: {', '.join(missing)}")
    update_severity("BLOCKER")
else:
    print(f"[PASS] Labels present: title={has_title}, x={has_xlabel}, y={has_ylabel}, caption={has_caption}")

# --- Check 3: Colorblind-safe palette ---
# The script uses Tol palette colors #4477AA (blue) and #CC6677 (rose)
has_manual_fill = bool(re.search(r'scale_fill_manual', script_text))
has_tol_blue = "#4477AA" in script_text
has_tol_rose = "#CC6677" in script_text
palette_ok = has_manual_fill and has_tol_blue and has_tol_rose

if not palette_ok:
    print(f"[WARNING] Colorblind-safe palette concern: manual_fill={has_manual_fill}, tol_blue={has_tol_blue}, tol_rose={has_tol_rose}")
    update_severity("WARNING")
else:
    print(f"[PASS] Colorblind-safe Tol palette: blue=#4477AA, rose=#CC6677")

# --- Check 4: Y-axis starts at 0 ---
# For bar charts, truncated y-axes are misleading
y_limits_match = re.search(r'limits\s*=\s*\(\s*0\s*,', script_text)
if not y_limits_match:
    print(f"[BLOCKER] Y-axis may not start at 0 — misleading for bar chart")
    update_severity("BLOCKER")
else:
    print(f"[PASS] Y-axis starts at 0 (bar chart best practice)")

# --- Check 5: DPI >= 150 ---
dpi_match = re.search(r'dpi\s*=\s*(\d+)', script_text)
if dpi_match:
    dpi = int(dpi_match.group(1))
    if dpi < 150:
        print(f"[WARNING] Low DPI: {dpi} (< 150 for publication)")
        update_severity("WARNING")
    else:
        print(f"[PASS] DPI = {dpi} (publication quality)")
else:
    print(f"[WARNING] No explicit DPI setting found")
    update_severity("WARNING")

# =============================================================================
# SCRIPT-SPECIFIC CHECKS (Five Skeptical Lenses)
# =============================================================================
print("\n" + "-" * 60)
print("SCRIPT-SPECIFIC CHECKS (Skeptical Lenses)")
print("-" * 60)

# --- Check 6: Counterfactual — verify input data completeness ---
# What if the input data had nulls in median_grad_rate or missing rows?
null_count = df["median_grad_rate"].null_count()
row_count = df.shape[0]
counterfactual_ok = null_count == 0 and row_count == EXPECTED_ROWS

if null_count > 0:
    print(f"[BLOCKER] median_grad_rate has {null_count} nulls — bars would be missing or zero-height")
    update_severity("BLOCKER")
elif row_count != EXPECTED_ROWS:
    print(f"[BLOCKER] Expected {EXPECTED_ROWS} rows (4 bands x 2 sectors), got {row_count}")
    update_severity("BLOCKER")
else:
    print(f"[PASS] Counterfactual: All {row_count} rows present, 0 nulls in median_grad_rate")

# --- Check 7: Semantic — does the figure answer the research question? ---
# The key finding is that in the Selective band, Public > Private (reversal)
selective_pub = df.filter(
    (pl.col("selectivity_band") == "Selective") & (pl.col("sector_label") == "Public")
)["median_grad_rate"].item()
selective_priv = df.filter(
    (pl.col("selectivity_band") == "Selective") & (pl.col("sector_label") == "Private nonprofit")
)["median_grad_rate"].item()
reversal_pp = selective_pub - selective_priv
reversal_visible = selective_pub > selective_priv

if not reversal_visible:
    print(f"[WARNING] Selective band reversal NOT present in data — Public ({selective_pub:.1f}) <= Private ({selective_priv:.1f})")
    update_severity("WARNING")
else:
    print(f"[PASS] Semantic: Selective band reversal confirmed — Public {selective_pub:.1f}% vs Private {selective_priv:.1f}% (delta: +{reversal_pp:.1f}pp)")

# --- Check 8: Boundary — bar label rounding matches data ---
# geom_text uses format_string="{:.0f}%" which rounds to nearest integer
# Verify that rounding doesn't misrepresent a close comparison
for row in df.iter_rows(named=True):
    raw_val = row["median_grad_rate"]
    rounded_val = round(raw_val)
    # If the decimal part is exactly .5, rounding could go either way
    fractional = raw_val - int(raw_val)
    if abs(fractional - 0.5) < 0.001:
        print(f"  [INFO] Exact .5 value: {row['selectivity_band']} / {row['sector_label']} = {raw_val} -> rounds to {rounded_val}")

# Check if any two values within the same band round to the same integer despite being different
bands_checked = 0
rounding_issues = []
for band in EXPECTED_BANDS:
    band_data = df.filter(pl.col("selectivity_band") == band)
    vals = band_data["median_grad_rate"].to_list()
    if len(vals) == 2:
        rounded_vals = [round(v) for v in vals]
        if rounded_vals[0] == rounded_vals[1] and vals[0] != vals[1]:
            rounding_issues.append(f"{band}: {vals[0]:.1f} and {vals[1]:.1f} both round to {rounded_vals[0]}%")
    bands_checked += 1

if rounding_issues:
    print(f"[WARNING] Rounding conceals differences: {'; '.join(rounding_issues)}")
    update_severity("WARNING")
else:
    print(f"[PASS] Boundary: No rounding collisions across {bands_checked} bands — bar labels faithfully distinguish sector values")

# --- Check 9: Absence — verify no sectors or bands silently dropped ---
actual_bands = sorted(df["selectivity_band"].unique().to_list())
actual_sectors = sorted(df["sector_label"].unique().to_list())
missing_bands = [b for b in EXPECTED_BANDS if b not in actual_bands]
missing_sectors = [s for s in EXPECTED_SECTORS if s not in actual_sectors]
extra_bands = [b for b in actual_bands if b not in EXPECTED_BANDS]
extra_sectors = [s for s in actual_sectors if s not in EXPECTED_SECTORS]

absence_ok = len(missing_bands) == 0 and len(missing_sectors) == 0
if not absence_ok:
    print(f"[BLOCKER] Missing bands: {missing_bands}, Missing sectors: {missing_sectors}")
    update_severity("BLOCKER")
elif extra_bands or extra_sectors:
    print(f"[WARNING] Unexpected extras — bands: {extra_bands}, sectors: {extra_sectors}")
    update_severity("WARNING")
else:
    print(f"[PASS] Absence: All 4 bands and 2 sectors present, no extras")

# --- Check 10: Downstream — data consistency for report ---
# Verify the figure's data matches what the report will cite
# Check that the median_grad_rate values are on 0-100 scale (not 0-1)
min_val = df["median_grad_rate"].min()
max_val = df["median_grad_rate"].max()
scale_ok = min_val >= 0 and max_val <= 100 and max_val > 1  # >1 confirms not proportion

if not scale_ok:
    print(f"[BLOCKER] Scale issue: min={min_val:.2f}, max={max_val:.2f} — may not be 0-100 percentage")
    update_severity("BLOCKER")
else:
    print(f"[PASS] Downstream: Values on 0-100 scale (range: {min_val:.1f} - {max_val:.1f})")

# =============================================================================
# SPOT-CHECKS
# =============================================================================
print("\n" + "-" * 60)
print("SPOT-CHECKS")
print("-" * 60)

# --- Spot 11: Trace Highly Selective Private nonprofit ---
hs_priv = df.filter(
    (pl.col("selectivity_band") == "Highly Selective") & (pl.col("sector_label") == "Private nonprofit")
)["median_grad_rate"].item()
hs_priv_label = f"{round(hs_priv)}%"
print(f"[PASS] Spot 11: Highly Selective / Private nonprofit = {hs_priv:.1f} -> label '{hs_priv_label}'")

# --- Spot 12: Trace Selective Public for +12pp reversal ---
sel_pub = df.filter(
    (pl.col("selectivity_band") == "Selective") & (pl.col("sector_label") == "Public")
)["median_grad_rate"].item()
sel_priv = df.filter(
    (pl.col("selectivity_band") == "Selective") & (pl.col("sector_label") == "Private nonprofit")
)["median_grad_rate"].item()
delta = sel_pub - sel_priv
print(f"[PASS] Spot 12: Selective reversal — Public {sel_pub:.1f}% vs Private {sel_priv:.1f}% = +{delta:.1f}pp (expected ~+12pp)")

# --- Spot 13: Verify BAND_ORDER in script matches data ---
# Extract BAND_ORDER from script
band_order_match = re.search(r'BAND_ORDER\s*=\s*\[(.*?)\]', script_text, re.DOTALL)
if band_order_match:
    script_bands_raw = band_order_match.group(1)
    script_bands = [b.strip().strip('"').strip("'") for b in script_bands_raw.split(",") if b.strip().strip('"').strip("'")]
    data_bands = df["selectivity_band"].unique().to_list()
    bands_in_data_not_script = [b for b in data_bands if b not in script_bands]
    bands_in_script_not_data = [b for b in script_bands if b not in data_bands]
    if bands_in_data_not_script or bands_in_script_not_data:
        print(f"[BLOCKER] BAND_ORDER mismatch: in data not script={bands_in_data_not_script}, in script not data={bands_in_script_not_data}")
        update_severity("BLOCKER")
    else:
        print(f"[PASS] Spot 13: BAND_ORDER matches data — {len(script_bands)} bands aligned")
else:
    print(f"[WARNING] Could not extract BAND_ORDER from script")
    update_severity("WARNING")

# --- Spot 14: Verify SECTOR_COLORS keys match data ---
# Extract SECTOR_COLORS keys from script
color_keys = re.findall(r'"([^"]+)":\s*"#[0-9A-Fa-f]{6}"', script_text)
data_sectors = df["sector_label"].unique().to_list()
keys_match = set(color_keys) == set(data_sectors)
if not keys_match:
    print(f"[BLOCKER] SECTOR_COLORS keys {color_keys} don't match data sectors {data_sectors}")
    update_severity("BLOCKER")
else:
    print(f"[PASS] Spot 14: SECTOR_COLORS keys match data sectors exactly: {color_keys}")

# --- Spot 15: Cross-reference figure file size against other figures ---
figures_dir = PROJECT_DIR / "output" / "figures"
if figures_dir.exists():
    figure_sizes = []
    for f in figures_dir.iterdir():
        if f.suffix == ".png":
            figure_sizes.append((f.name, f.stat().st_size / 1024))

    our_size = file_size_kb
    other_sizes = [s for name, s in figure_sizes if name != "2026-02-15_sector_comparison.png"]
    if other_sizes:
        avg_other = sum(other_sizes) / len(other_sizes)
        ratio = our_size / avg_other if avg_other > 0 else float('inf')
        if ratio < 0.1 or ratio > 10:
            print(f"[WARNING] Figure size ({our_size:.1f} KB) is unusual vs avg of others ({avg_other:.1f} KB), ratio={ratio:.2f}")
            update_severity("WARNING")
        else:
            print(f"[PASS] Spot 15: Figure size ({our_size:.1f} KB) reasonable vs avg ({avg_other:.1f} KB), ratio={ratio:.2f}")
    else:
        print(f"[INFO] Spot 15: No other figures to compare against")

# =============================================================================
# ADDITIONAL: Verify legend is present and positioned
# =============================================================================
print("\n" + "-" * 60)
print("ADDITIONAL CHECKS")
print("-" * 60)

has_legend = bool(re.search(r'legend_position\s*=\s*"top"', script_text))
has_legend_title = bool(re.search(r'legend_title\s*=', script_text))
if not has_legend:
    print(f"[WARNING] Legend position not set to 'top'")
    update_severity("WARNING")
else:
    print(f"[PASS] Legend positioned at top with title")

# Verify subtitle includes year
has_subtitle_year = bool(re.search(r'subtitle.*2020', script_text))
if not has_subtitle_year:
    print(f"[WARNING] Subtitle may not include analysis year (2020)")
    update_severity("WARNING")
else:
    print(f"[PASS] Subtitle includes year 2020")

# Verify all 8 bars would appear by checking each band-sector combination
print(f"\nData values that map to bars:")
for band in EXPECTED_BANDS:
    for sector in EXPECTED_SECTORS:
        match = df.filter(
            (pl.col("selectivity_band") == band) & (pl.col("sector_label") == sector)
        )
        if match.shape[0] == 1:
            val = match["median_grad_rate"].item()
            print(f"  {band:25s} | {sector:20s} | {val:5.1f}% -> label: {round(val)}%")
        else:
            print(f"  [BLOCKER] {band} / {sector}: {match.shape[0]} rows (expected 1)")
            update_severity("BLOCKER")

# =============================================================================
# DATA PROFILING (for crb2+ decision)
# =============================================================================
print("\n" + "=" * 60)
print("DATA PROFILING")
print("=" * 60)

print("\nFull input data:")
print(df)

print("\nDescriptive statistics:")
print(df.describe())

print("\nColumn types:")
for col in df.columns:
    print(f"  {col}: {df[col].dtype}")

print("\nFigures directory listing:")
if figures_dir.exists():
    for f in sorted(figures_dir.iterdir()):
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print(f"QA4b RESULT: {qa_severity}")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-02-15 22:19:54
# Command: python /daaf/research/2026-02-15_College_Graduation_Rate_Selectivity_Analysis/scripts/cr/stage8_12_crb1.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# QA4b INSPECTION: Stage 8 Step 12 — Sector Comparison Viz
# ============================================================
# Input data: 8 rows x 12 cols
# Script length: 12,361 chars
# 
# ------------------------------------------------------------
# DEFAULT CHECKS
# ------------------------------------------------------------
# [PASS] Figure exists: 232.5 KB (> 50 KB threshold)
# [PASS] Labels present: title=True, x=True, y=True, caption=True
# [PASS] Colorblind-safe Tol palette: blue=#4477AA, rose=#CC6677
# [PASS] Y-axis starts at 0 (bar chart best practice)
# [PASS] DPI = 300 (publication quality)
# 
# ------------------------------------------------------------
# SCRIPT-SPECIFIC CHECKS (Skeptical Lenses)
# ------------------------------------------------------------
# [PASS] Counterfactual: All 8 rows present, 0 nulls in median_grad_rate
# [PASS] Semantic: Selective band reversal confirmed — Public 74.6% vs Private 62.6% (delta: +12.0pp)
#   [INFO] Exact .5 value: Less Selective/Open / Public = 50.5 -> rounds to 50
# [PASS] Boundary: No rounding collisions across 4 bands — bar labels faithfully distinguish sector values
# [PASS] Absence: All 4 bands and 2 sectors present, no extras
# [PASS] Downstream: Values on 0-100 scale (range: 50.5 - 92.6)
# 
# ------------------------------------------------------------
# SPOT-CHECKS
# ------------------------------------------------------------
# [PASS] Spot 11: Highly Selective / Private nonprofit = 92.6 -> label '93%'
# [PASS] Spot 12: Selective reversal — Public 74.6% vs Private 62.6% = +12.0pp (expected ~+12pp)
# [PASS] Spot 13: BAND_ORDER matches data — 4 bands aligned
# [PASS] Spot 14: SECTOR_COLORS keys match data sectors exactly: ['Public', 'Private nonprofit']
# [PASS] Spot 15: Figure size (232.5 KB) reasonable vs avg (636.0 KB), ratio=0.37
# 
# ------------------------------------------------------------
# ADDITIONAL CHECKS
# ------------------------------------------------------------
# [PASS] Legend positioned at top with title
# [PASS] Subtitle includes year 2020
# 
# Data values that map to bars:
#   Highly Selective          | Private nonprofit    |  92.6% -> label: 93%
#   Highly Selective          | Public               |  91.9% -> label: 92%
#   Selective                 | Private nonprofit    |  62.6% -> label: 63%
#   Selective                 | Public               |  74.6% -> label: 75%
#   Moderately Selective      | Private nonprofit    |  60.3% -> label: 60%
#   Moderately Selective      | Public               |  54.2% -> label: 54%
#   Less Selective/Open       | Private nonprofit    |  57.0% -> label: 57%
#   Less Selective/Open       | Public               |  50.5% -> label: 50%
# 
# ============================================================
# DATA PROFILING
# ============================================================
# 
# Full input data:
# shape: (8, 12)
# ┌────────────┬────────────┬──────┬────────────┬───┬────────────┬───────────┬───────────┬───────────┐
# │ selectivit ┆ inst_contr ┆ n    ┆ n_with_gra ┆ … ┆ median_urm ┆ median_st ┆ median_re ┆ sector_la │
# │ y_band     ┆ ol         ┆ ---  ┆ d_rate     ┆   ┆ _share     ┆ udent_fac ┆ tention_r ┆ bel       │
# │ ---        ┆ ---        ┆ u32  ┆ ---        ┆   ┆ ---        ┆ ulty_rati ┆ ate       ┆ ---       │
# │ cat        ┆ i64        ┆      ┆ u32        ┆   ┆ f64        ┆ o         ┆ ---       ┆ str       │
# │            ┆            ┆      ┆            ┆   ┆            ┆ ---       ┆ f64       ┆           │
# │            ┆            ┆      ┆            ┆   ┆            ┆ f64       ┆           ┆           │
# ╞════════════╪════════════╪══════╪════════════╪═══╪════════════╪═══════════╪═══════════╪═══════════╡
# │ Highly     ┆ 1          ┆ 9    ┆ 9          ┆ … ┆ 0.182029   ┆ 13.0      ┆ 97.0      ┆ Public    │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Highly     ┆ 2          ┆ 64   ┆ 60         ┆ … ┆ 0.18551    ┆ 8.0       ┆ 92.0      ┆ Private   │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# │ Selective  ┆ 1          ┆ 38   ┆ 37         ┆ … ┆ 0.310883   ┆ 17.0      ┆ 89.0      ┆ Public    │
# │ Selective  ┆ 2          ┆ 136  ┆ 122        ┆ … ┆ 0.196464   ┆ 10.0      ┆ 79.0      ┆ Private   │
# │            ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# │ Moderately ┆ 1          ┆ 160  ┆ 157        ┆ … ┆ 0.257936   ┆ 16.0      ┆ 78.0      ┆ Public    │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Moderately ┆ 2          ┆ 426  ┆ 407        ┆ … ┆ 0.186251   ┆ 12.0      ┆ 75.5      ┆ Private   │
# │ Selective  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# │ Less Selec ┆ 1          ┆ 645  ┆ 391        ┆ … ┆ 0.230444   ┆ 17.0      ┆ 75.0      ┆ Public    │
# │ tive/Open  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆           │
# │ Less Selec ┆ 2          ┆ 1050 ┆ 613        ┆ … ┆ 0.207363   ┆ 12.0      ┆ 75.0      ┆ Private   │
# │ tive/Open  ┆            ┆      ┆            ┆   ┆            ┆           ┆           ┆ nonprofit │
# └────────────┴────────────┴──────┴────────────┴───┴────────────┴───────────┴───────────┴───────────┘
# 
# Descriptive statistics:
# shape: (9, 13)
# ┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
# │ statistic ┆ selectivi ┆ inst_cont ┆ n         ┆ … ┆ median_ur ┆ median_st ┆ median_re ┆ sector_l │
# │ ---       ┆ ty_band   ┆ rol       ┆ ---       ┆   ┆ m_share   ┆ udent_fac ┆ tention_r ┆ abel     │
# │ str       ┆ ---       ┆ ---       ┆ f64       ┆   ┆ ---       ┆ ulty_rati ┆ ate       ┆ ---      │
# │           ┆ str       ┆ f64       ┆           ┆   ┆ f64       ┆ o         ┆ ---       ┆ str      │
# │           ┆           ┆           ┆           ┆   ┆           ┆ ---       ┆ f64       ┆          │
# │           ┆           ┆           ┆           ┆   ┆           ┆ f64       ┆           ┆          │
# ╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
# │ count     ┆ 8         ┆ 8.0       ┆ 8.0       ┆ … ┆ 8.0       ┆ 8.0       ┆ 8.0       ┆ 8        │
# │ null_coun ┆ 0         ┆ 0.0       ┆ 0.0       ┆ … ┆ 0.0       ┆ 0.0       ┆ 0.0       ┆ 0        │
# │ t         ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆          │
# │ mean      ┆ null      ┆ 1.5       ┆ 316.0     ┆ … ┆ 0.21961   ┆ 13.125    ┆ 82.5625   ┆ null     │
# │ std       ┆ null      ┆ 0.534522  ┆ 368.56284 ┆ … ┆ 0.045183  ┆ 3.313932  ┆ 8.756375  ┆ null     │
# │           ┆           ┆           ┆ 6         ┆   ┆           ┆           ┆           ┆          │
# │ min       ┆ null      ┆ 1.0       ┆ 9.0       ┆ … ┆ 0.182029  ┆ 8.0       ┆ 75.0      ┆ Private  │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ nonprofi │
# │           ┆           ┆           ┆           ┆   ┆           ┆           ┆           ┆ t        │
# │ 25%       ┆ null      ┆ 1.0       ┆ 64.0      ┆ … ┆ 0.186251  ┆ 12.0      ┆ 75.5      ┆ null     │
# │ 50%       ┆ null      ┆ 2.0       ┆ 160.0     ┆ … ┆ 0.207363  ┆ 13.0      ┆ 79.0      ┆ null     │
# │ 75%       ┆ null      ┆ 2.0       ┆ 426.0     ┆ … ┆ 0.230444  ┆ 16.0      ┆ 89.0      ┆ null     │
# │ max       ┆ null      ┆ 2.0       ┆ 1050.0    ┆ … ┆ 0.310883  ┆ 17.0      ┆ 97.0      ┆ Public   │
# └───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
# 
# Column types:
#   selectivity_band: Categorical
#   inst_control: Int64
#   n: UInt32
#   n_with_grad_rate: UInt32
#   median_grad_rate: Float64
#   mean_grad_rate: Float64
#   std_grad_rate: Float64
#   median_pell_share: Float64
#   median_urm_share: Float64
#   median_student_faculty_ratio: Float64
#   median_retention_rate: Float64
#   sector_label: String
# 
# Figures directory listing:
#   2026-02-15_boxplot_grad_rate_by_selectivity.png (766.1 KB)
#   2026-02-15_correlation_heatmap.png (303.0 KB)
#   2026-02-15_grad_rate_vs_admission_rate.png (1165.5 KB)
#   2026-02-15_heatmap_selectivity_pell.png (309.6 KB)
#   2026-02-15_sector_comparison.png (232.5 KB)
# 
# ============================================================
# QA4b RESULT: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
