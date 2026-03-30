#!/usr/bin/env python3
"""
Stage 8.1: Outperformer analysis -- identify institutions that graduate students
at rates significantly above/below what selectivity alone predicts.

Task: outperformers
Wave: 8, Step: 5, Stage: 8
Depends on: create-bands (Stage 7)
Input: data/processed/2026-03-29_analysis.parquet
Output: output/analysis/2026-03-29_selectivity_model.parquet
        output/analysis/2026-03-29_outperformers.parquet
Checkpoint: CP4
"""

import polars as pl
import numpy as np
import pandas as pd
import statsmodels.api as sm
from pathlib import Path

# --- Config ---
# Configuration for outperformer identification via OLS residual analysis.
# The "selectivity-only" model regresses completion rate on admission rate to
# establish what selectivity alone predicts. Residuals reveal which institutions
# exceed or fall short of that expectation.
PROJECT_DIR = Path("/daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis")
DATE_PREFIX = "2026-03-29"

INPUT_PATH = PROJECT_DIR / "data" / "processed" / f"{DATE_PREFIX}_analysis.parquet"
OUTPUT_MODEL_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_selectivity_model.parquet"
OUTPUT_OUTPERFORMERS_PATH = PROJECT_DIR / "output" / "analysis" / f"{DATE_PREFIX}_outperformers.parquet"

OUTCOME_VAR = "completion_rate_150pct"
PREDICTOR_VAR = "admit_rate"

# REASONING: 1 SD threshold for outperformer/underperformer classification is
# standard in residual analysis -- it identifies institutions meaningfully above
# or below the regression line while keeping the groups substantively sized
# (roughly ~15-20% at each tail for approximately normal residuals).
OUTPERFORMER_SD_THRESHOLD = 1.0

# Profile variables for characterizing outperformers vs underperformers
PROFILE_CONTINUOUS = [
    "pell_share", "urm_share", "student_faculty_ratio",
    "retention_rate", "instr_expend_per_fte"
]
PROFILE_CATEGORICAL_SECTOR = "inst_control"
PROFILE_HBCU = "hbcu"

# --- Load ---
# Load the analysis dataset produced by Stage 7 (create-bands).
print("=" * 60)
print("Stage 8.1: Outperformer Analysis (Selectivity-Only OLS)")
print("=" * 60)

df = pl.read_parquet(INPUT_PATH)
print(f"Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")

# --- Pre-state ---
# Capture full dataset shape before filtering to complete cases.
pre_rows = df.shape[0]
pre_cols = df.columns.copy()
print(f"Pre-state: {pre_rows:,} rows, {len(pre_cols)} cols")

# Check missingness in key variables before filtering
admit_null = df[PREDICTOR_VAR].null_count()
completion_null = df[OUTCOME_VAR].null_count()
print(f"\nMissingness before filter:")
print(f"  {PREDICTOR_VAR}: {admit_null:,} null ({admit_null / pre_rows * 100:.1f}%)")
print(f"  {OUTCOME_VAR}: {completion_null:,} null ({completion_null / pre_rows * 100:.1f}%)")

# --- Filter to complete cases ---
# INTENT: Restrict to institutions where both admit_rate and completion_rate_150pct
# are non-null. The ~39.5% of institutions with null admit_rate are open-admissions
# schools that do not report admission rates -- they cannot be modeled in a
# selectivity framework.
#
# REASONING: Listwise deletion on these two variables is appropriate because:
#   - Open-admissions schools have a structurally different selection process
#   - The research question specifically examines selectivity's role
#   - These are not randomly missing; they represent a different population
#
# ASSUMES:
#   - admit_rate is null for open-admissions institutions (not data errors)
#   - completion_rate_150pct is non-null for the vast majority of institutions
df_model = df.drop_nulls(subset=[PREDICTOR_VAR, OUTCOME_VAR])
dropped = pre_rows - df_model.shape[0]
print(f"\nComplete cases for model: {df_model.shape[0]:,} ({dropped:,} dropped, {dropped / pre_rows * 100:.1f}%)")

# --- Note DeVry data artifact ---
# INTENT: Flag the known data artifact for DeVry (unitid 482538) which shows
# admit_rate=0% due to 2 applications / 0 admits. This is a data quality issue,
# not a real zero admission rate.
# REASONING: The task specification notes this; flagging in output for transparency.
devry_check = df_model.filter(pl.col("unitid") == 482538)
if devry_check.shape[0] > 0:
    devry_admit = devry_check["admit_rate"][0]
    print(f"\nNOTE: DeVry (unitid 482538) in model data with admit_rate={devry_admit}% -- known data artifact")

# --- Fit OLS Model ---
# INTENT: Fit a simple bivariate OLS regression of completion_rate_150pct on
# admit_rate to establish the "selectivity-only" baseline prediction.
#
# REASONING: This is the first-stage model that quantifies how much of graduation
# rate variation is attributable to selectivity alone. HC1 robust SEs are used
# because heteroskedasticity is expected -- variance in graduation rates likely
# differs across the selectivity spectrum (highly selective schools cluster near
# high completion rates with less spread; less selective schools show more spread).
#
# ASSUMES:
#   - Linear approximation is adequate for the selectivity-completion relationship
#   - No omitted variable bias concerns for this descriptive model (we are
#     intentionally estimating the unadjusted association)
#   - HC1 (MacKinnon-White) is appropriate for cross-sectional data
df_pd = df_model.select(["unitid", "inst_name", PREDICTOR_VAR, OUTCOME_VAR]).to_pandas()

X = sm.add_constant(df_pd[PREDICTOR_VAR])
y = df_pd[OUTCOME_VAR]

# REASONING: Using array API with add_constant for explicit control over the
# design matrix. HC1 robust standard errors account for heteroskedasticity
# without assuming a specific variance structure.
model = sm.OLS(y, X)
results = model.fit(cov_type="HC1")

print("\n" + "=" * 60)
print("MODEL SUMMARY: completion_rate_150pct ~ admit_rate (HC1)")
print("=" * 60)
print(f"N:           {int(results.nobs):,}")
print(f"R-squared:   {results.rsquared:.4f}")
print(f"Adj R-sq:    {results.rsquared_adj:.4f}")
print(f"F-statistic: {results.fvalue:.2f} (p = {results.f_pvalue:.2e})")
print(f"\nCoefficients:")
print(f"  {'Variable':<20} {'Coef':>10} {'Std Err':>10} {'t':>8} {'P>|t|':>10} {'[0.025':>10} {'0.975]':>10}")
print(f"  {'-' * 80}")
ci = results.conf_int()
for var in results.params.index:
    print(f"  {var:<20} {results.params[var]:>10.4f} {results.bse[var]:>10.4f} "
          f"{results.tvalues[var]:>8.2f} {results.pvalues[var]:>10.4e} "
          f"{ci.loc[var, 0]:>10.4f} {ci.loc[var, 1]:>10.4f}")

# --- Compute predicted values and residuals ---
# INTENT: Generate predicted completion rates and residuals for every institution
# in the model sample. Residuals measure how far each institution's actual
# graduation rate is from what selectivity alone would predict.
#
# REASONING: Using the model's fittedvalues and resid attributes directly from
# the statsmodels results object for consistency with the fitted model.
df_pd["predicted"] = results.fittedvalues.values
df_pd["residual"] = results.resid.values

# --- Compute residual SD and classify outperformers/underperformers ---
# INTENT: Use the standard deviation of residuals to define thresholds for
# outperformer (+1 SD) and underperformer (-1 SD) classification.
#
# REASONING: The SD of residuals (not RMSE, which adjusts for df) is used as
# the classification threshold because we want the unconditional spread of
# residuals for defining "unusual" performance, not the df-adjusted estimate.
# In practice, SD and RMSE are nearly identical for large N.
resid_sd = np.std(df_pd["residual"], ddof=0)  # Population SD of residuals
resid_mean = np.mean(df_pd["residual"])  # Should be ~0 by OLS properties
print(f"\nResidual statistics:")
print(f"  Mean:   {resid_mean:.4f} (should be ~0)")
print(f"  SD:     {resid_sd:.4f}")
print(f"  Threshold (1 SD): +/- {resid_sd:.4f}")

# INTENT: Classify institutions based on residual magnitude.
# +1 SD = outperformer (graduates more students than selectivity predicts)
# -1 SD = underperformer (graduates fewer students than selectivity predicts)
# Between = typical (within 1 SD of prediction)
upper_threshold = OUTPERFORMER_SD_THRESHOLD * resid_sd
lower_threshold = -OUTPERFORMER_SD_THRESHOLD * resid_sd

df_pd["outperformer_flag"] = "typical"
df_pd.loc[df_pd["residual"] > upper_threshold, "outperformer_flag"] = "outperformer"
df_pd.loc[df_pd["residual"] < lower_threshold, "outperformer_flag"] = "underperformer"

n_out = (df_pd["outperformer_flag"] == "outperformer").sum()
n_under = (df_pd["outperformer_flag"] == "underperformer").sum()
n_typical = (df_pd["outperformer_flag"] == "typical").sum()
n_total = len(df_pd)

print(f"\nClassification:")
print(f"  Outperformers:    {n_out:,} ({n_out / n_total * 100:.1f}%)")
print(f"  Typical:          {n_typical:,} ({n_typical / n_total * 100:.1f}%)")
print(f"  Underperformers:  {n_under:,} ({n_under / n_total * 100:.1f}%)")

# --- Merge classification back to full Polars DataFrame for profiling ---
# INTENT: Join the model results (predicted, residual, outperformer_flag) back
# to the full model dataset so we can profile outperformers using all variables.
#
# REASONING: Working in Polars for profiling because the full dataset with
# profile variables is already in Polars. The pandas model results are joined
# via unitid.
df_results = pl.from_pandas(df_pd[["unitid", "inst_name", PREDICTOR_VAR, OUTCOME_VAR,
                                     "predicted", "residual", "outperformer_flag"]])

# Join profile variables from the original model data
profile_cols = ["unitid"] + PROFILE_CONTINUOUS + [PROFILE_CATEGORICAL_SECTOR, PROFILE_HBCU]
existing_profile_cols = [c for c in profile_cols if c in df_model.columns]
df_profile = df_model.select(existing_profile_cols)

df_full = df_results.join(df_profile, on="unitid", how="left")

# --- Profile outperformers ---
# INTENT: Characterize outperformers by their institutional attributes to understand
# what differentiates institutions that exceed selectivity-based expectations.
print("\n" + "=" * 60)
print("OUTPERFORMER PROFILE")
print("=" * 60)

df_out = df_full.filter(pl.col("outperformer_flag") == "outperformer")
df_under = df_full.filter(pl.col("outperformer_flag") == "underperformer")

# Continuous variable profiles
print(f"\n{'Variable':<30} {'Outperformer Mean':>18} {'Outperformer Med':>18} {'Underperformer Mean':>20} {'Underperformer Med':>20}")
print("-" * 110)

profile_rows = []
for var in PROFILE_CONTINUOUS:
    if var in df_full.columns:
        out_mean = df_out[var].drop_nulls().mean()
        out_median = df_out[var].drop_nulls().median()
        under_mean = df_under[var].drop_nulls().mean()
        under_median = df_under[var].drop_nulls().median()
        print(f"  {var:<28} {out_mean:>18.2f} {out_median:>18.2f} {under_mean:>20.2f} {under_median:>20.2f}")
        profile_rows.append({
            "variable": var,
            "outperformer_mean": out_mean,
            "outperformer_median": out_median,
            "underperformer_mean": under_mean,
            "underperformer_median": under_median,
        })

# --- Sector distribution ---
# INTENT: Show the share of outperformers and underperformers by institutional
# sector (public, private NP, for-profit) to reveal whether sector composition
# differs between the two groups.
#
# REASONING: Sector is a key structural variable -- for-profits and privates
# may have different incentive structures affecting graduation rates.
# inst_control: 1=public, 2=private NP, 3=for-profit
print("\nSector Distribution:")
sector_labels = {1: "Public", 2: "Private NP", 3: "For-Profit"}

for group_name, group_df in [("Outperformers", df_out), ("Underperformers", df_under)]:
    print(f"\n  {group_name} (N={group_df.shape[0]:,}):")
    if PROFILE_CATEGORICAL_SECTOR in group_df.columns:
        sector_counts = group_df.group_by(PROFILE_CATEGORICAL_SECTOR).len().sort(PROFILE_CATEGORICAL_SECTOR)
        for row in sector_counts.iter_rows(named=True):
            sector_val = row[PROFILE_CATEGORICAL_SECTOR]
            count = row["len"]
            pct = count / group_df.shape[0] * 100
            label = sector_labels.get(sector_val, f"Unknown ({sector_val})")
            print(f"    {label}: {count:,} ({pct:.1f}%)")
            profile_rows.append({
                "variable": f"sector_{label.lower().replace(' ', '_').replace('-', '')}_{group_name.lower()}",
                "outperformer_mean": pct if group_name == "Outperformers" else None,
                "outperformer_median": None,
                "underperformer_mean": pct if group_name == "Underperformers" else None,
                "underperformer_median": None,
            })

# --- HBCU count ---
# INTENT: Count HBCUs among outperformers and underperformers. HBCUs serve
# predominantly Black student populations and may show distinct graduation
# patterns relative to selectivity.
print("\nHBCU Presence:")
for group_name, group_df in [("Outperformers", df_out), ("Underperformers", df_under)]:
    if PROFILE_HBCU in group_df.columns:
        hbcu_count = group_df.filter(pl.col(PROFILE_HBCU) == 1).shape[0]
        hbcu_pct = hbcu_count / group_df.shape[0] * 100 if group_df.shape[0] > 0 else 0
        print(f"  {group_name}: {hbcu_count} HBCUs ({hbcu_pct:.1f}%)")

# --- Save model results ---
# INTENT: Save the full institution-level model results (predicted values,
# residuals, outperformer flag) for downstream use by viz-residual-scatter
# (Task 11.1) and the final report.
#
# REASONING: Saving as parquet to output/analysis/ per task specification.
# This includes unitid for joining back to the full dataset if needed.
OUTPUT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

df_results.write_parquet(OUTPUT_MODEL_PATH)
print(f"\nSaved model results: {OUTPUT_MODEL_PATH}")
print(f"  Shape: {df_results.shape[0]:,} rows x {df_results.shape[1]} cols")

# --- Save outperformer profile summary ---
# INTENT: Save the profiling summary as a structured parquet for report generation.
profile_df = pl.DataFrame(profile_rows)
profile_df.write_parquet(OUTPUT_OUTPERFORMERS_PATH)
print(f"Saved outperformer profile: {OUTPUT_OUTPERFORMERS_PATH}")
print(f"  Shape: {profile_df.shape[0]:,} rows x {profile_df.shape[1]} cols")

# --- CP4 Validation ---
# Checkpoint validation: verify model produced valid results, outperformer
# classification is reasonable, output files exist and are non-zero.
print("\n" + "=" * 60)
print("CHECKPOINT 4 VALIDATION")
print("=" * 60)

cp4_passed = True

# CP4.1: Output files exist and are non-zero
for fpath, label in [(OUTPUT_MODEL_PATH, "selectivity_model"),
                      (OUTPUT_OUTPERFORMERS_PATH, "outperformers")]:
    exists = fpath.exists()
    size = fpath.stat().st_size if exists else 0
    ok = exists and size > 0
    if not ok:
        cp4_passed = False
    print(f"  [{'PASS' if ok else 'FAIL'}] {label} exists and non-zero: {exists}, {size:,} bytes")

# CP4.2: R-squared in valid range [0, 1]
r2_valid = 0 <= results.rsquared <= 1
if not r2_valid:
    cp4_passed = False
print(f"  [{'PASS' if r2_valid else 'FAIL'}] R-squared in [0, 1]: {results.rsquared:.4f}")

# CP4.3: Outperformer percentage is substantively reasonable (~15-20% for 1 SD)
out_pct = n_out / n_total * 100
pct_reasonable = 5 <= out_pct <= 30  # Generous bounds for 1 SD threshold
if not pct_reasonable:
    cp4_passed = False
print(f"  [{'PASS' if pct_reasonable else 'FAIL'}] Outperformer % reasonable: {out_pct:.1f}% (expected 5-30%)")

# CP4.4: Outperformer profile includes sector distribution
sector_in_profile = any("sector_" in str(row.get("variable", "")) for row in profile_rows)
if not sector_in_profile:
    cp4_passed = False
print(f"  [{'PASS' if sector_in_profile else 'FAIL'}] Profile includes sector distribution")

# CP4.5: Sample sizes documented
n_documented = n_total > 0 and n_out > 0 and n_under > 0
if not n_documented:
    cp4_passed = False
print(f"  [{'PASS' if n_documented else 'FAIL'}] Sample sizes: total={n_total:,}, outperformers={n_out:,}, underperformers={n_under:,}")

# CP4.6: All coefficients finite
all_finite = np.all(np.isfinite(results.params.values)) and np.all(np.isfinite(results.bse.values))
if not all_finite:
    cp4_passed = False
print(f"  [{'PASS' if all_finite else 'FAIL'}] All coefficients finite")

# CP4.7: Model results parquet is readable and has expected columns
verify_df = pl.read_parquet(OUTPUT_MODEL_PATH)
expected_cols = ["unitid", "inst_name", PREDICTOR_VAR, OUTCOME_VAR, "predicted", "residual", "outperformer_flag"]
missing_cols = [c for c in expected_cols if c not in verify_df.columns]
cols_ok = len(missing_cols) == 0
if not cols_ok:
    cp4_passed = False
print(f"  [{'PASS' if cols_ok else 'FAIL'}] Model parquet has expected columns (missing: {missing_cols})")

assert cp4_passed, "CP4 VALIDATION FAILED -- see details above"

print(f"\n{'=' * 60}")
print("CP4 VALIDATION: PASSED")
print("=" * 60)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-30 12:14:26
# Command: python3 /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/scripts/stage8_analysis/05_outperformers.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ============================================================
# Stage 8.1: Outperformer Analysis (Selectivity-Only OLS)
# ============================================================
# Loaded: 1,946 rows x 25 cols
# Pre-state: 1,946 rows, 25 cols
# 
# Missingness before filter:
#   admit_rate: 321 null (16.5%)
#   completion_rate_150pct: 0 null (0.0%)
# 
# Complete cases for model: 1,625 (321 dropped, 16.5%)
# 
# NOTE: DeVry (unitid 482538) in model data with admit_rate=0.0% -- known data artifact
# 
# ============================================================
# MODEL SUMMARY: completion_rate_150pct ~ admit_rate (HC1)
# ============================================================
# N:           1,625
# R-squared:   0.0999
# Adj R-sq:    0.0994
# F-statistic: 142.86 (p = 1.28e-31)
# 
# Coefficients:
#   Variable                   Coef    Std Err        t      P>|t|     [0.025     0.975]
#   --------------------------------------------------------------------------------
#   const                   78.1231     1.8432    42.38 0.0000e+00    74.5105    81.7357
#   admit_rate              -0.2890     0.0242   -11.95 6.3175e-33    -0.3364    -0.2416
# 
# Residual statistics:
#   Mean:   -0.0000 (should be ~0)
#   SD:     17.8241
#   Threshold (1 SD): +/- 17.8241
# 
# Classification:
#   Outperformers:    248 (15.3%)
#   Typical:          1,126 (69.3%)
#   Underperformers:  251 (15.4%)
# 
# ============================================================
# OUTPERFORMER PROFILE
# ============================================================
# 
# Variable                        Outperformer Mean   Outperformer Med  Underperformer Mean   Underperformer Med
# --------------------------------------------------------------------------------------------------------------
#   pell_share                                 0.11               0.10                 0.13                 0.12
#   urm_share                                  0.19               0.17                 0.46                 0.39
#   student_faculty_ratio                     11.76              11.00                14.49                14.00
#   retention_rate                            87.31              89.00                62.69                63.00
#   instr_expend_per_fte                   21116.21           16653.34              7739.78              6143.22
# 
# Sector Distribution:
# 
#   Outperformers (N=248):
#     Public: 55 (22.2%)
#     Private NP: 187 (75.4%)
#     For-Profit: 6 (2.4%)
# 
#   Underperformers (N=251):
#     Public: 66 (26.3%)
#     Private NP: 163 (64.9%)
#     For-Profit: 22 (8.8%)
# 
# HBCU Presence:
#   Outperformers: 1 HBCUs (0.4%)
#   Underperformers: 37 HBCUs (14.7%)
# 
# Saved model results: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_selectivity_model.parquet
#   Shape: 1,625 rows x 7 cols
# Saved outperformer profile: /daaf/research/2026-03-29_College_Graduation_Rate_Selectivity_Analysis/output/analysis/2026-03-29_outperformers.parquet
#   Shape: 11 rows x 5 cols
# 
# ============================================================
# CHECKPOINT 4 VALIDATION
# ============================================================
#   [PASS] selectivity_model exists and non-zero: True, 60,269 bytes
#   [PASS] outperformers exists and non-zero: True, 2,365 bytes
#   [PASS] R-squared in [0, 1]: 0.0999
#   [PASS] Outperformer % reasonable: 15.3% (expected 5-30%)
#   [PASS] Profile includes sector distribution
#   [PASS] Sample sizes: total=1,625, outperformers=248, underperformers=251
#   [PASS] All coefficients finite
#   [PASS] Model parquet has expected columns (missing: [])
# 
# ============================================================
# CP4 VALIDATION: PASSED
# ============================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
