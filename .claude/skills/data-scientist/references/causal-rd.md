# Regression Discontinuity: Implementation with rdrobust

A practitioner's implementation reference for Regression Discontinuity (RD) designs
using the `rdrobust` package in Python. This reference covers the full implementation
workflow: estimation, bandwidth selection, visualization, diagnostics, and reporting.
For the methodology behind RD -- identification assumptions, sharp vs. fuzzy designs,
the role of RD in the causal inference toolkit -- see `causal-inference.md` > "Regression
Discontinuity: Design Essentials."

## Contents

- [Package Overview](#package-overview)
- [Sharp RD: Basic Estimation](#sharp-rd-basic-estimation)
- [Reading rdrobust Output](#reading-rdrobust-output)
- [Bandwidth Selection](#bandwidth-selection)
- [Fuzzy RD](#fuzzy-rd)
- [Kink RD](#kink-rd)
- [Covariates](#covariates)
- [Clustering and Weights](#clustering-and-weights)
- [RD Visualization](#rd-visualization)
- [Manipulation Testing](#manipulation-testing)
- [Covariate Balance at the Cutoff](#covariate-balance-at-the-cutoff)
- [Bandwidth Sensitivity Analysis](#bandwidth-sensitivity-analysis)
- [Placebo Cutoff Tests](#placebo-cutoff-tests)
- [Donut RD](#donut-rd)
- [Complete RD Analysis Template](#complete-rd-analysis-template)
- [Gotchas](#gotchas)
- [References](#references)

## Package Overview

The DAAF environment includes `rdrobust` v1.3.0. The package provides three functions:

| Function | Purpose | Status in v1.3.0 |
|----------|---------|-------------------|
| `rdrobust()` | Local polynomial RD estimation with robust bias-corrected inference | Working |
| `rdbwselect()` | Data-driven bandwidth selection (10 methods) | Working |
| `rdplot()` | RD visualization with binned scatter + polynomial fit | **Broken** -- crashes with `ValueError: assignment destination is read-only` (NumPy/pandas compatibility bug at line 692). Use manual plotting workaround below. |

**Not installed:** `rddensity` (manipulation testing), `rdmulti` (multiple cutoffs),
`rdlocrand` (local randomization inference), `rdpower` (power calculations). Manual
alternatives for manipulation testing are documented below.

**Version note:** v2.0.0 is available on PyPI with bug fixes (including the rdplot
crash) and new features (e.g., `cr3` variance estimator). The code in this reference
targets v1.3.0 as installed.

```python
from rdrobust import rdrobust, rdbwselect, rdplot
import polars as pl
import numpy as np
```

## Sharp RD: Basic Estimation

The core function takes a numpy array of outcomes (`y`) and a numpy array of the
running variable (`x`). The cutoff defaults to 0.

```python
# --- Load ---
df = pl.read_parquet(f"{DATA_DIR}/analysis_data.parquet")

# --- Estimate ---
# Extract numpy arrays (rdrobust requires array-like, not Polars Series)
y = df["outcome"].to_numpy()
x = df["running_var"].to_numpy()

# Sharp RD at cutoff = 0 (default)
result = rdrobust(y, x)
print(result)
```

### Non-Zero Cutoff

```python
# Cutoff at 50 (e.g., test score threshold)
result = rdrobust(y, x, c=50)
print(result)
```

### Key Defaults

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `p` | 1 | Local linear regression (strongly recommended; see Gelman and Imbens 2019) |
| `kernel` | `"tri"` | Triangular kernel (assigns highest weight to observations closest to cutoff) |
| `bwselect` | `"mserd"` | MSE-optimal bandwidth, common (same) for both sides |
| `vce` | `"nn"` | Nearest-neighbor variance estimator |
| `masspoints` | `"adjust"` | Adjusts for mass points (repeated values) in the running variable |
| `level` | 95 | 95% confidence intervals |

## Reading rdrobust Output

The `rdrobust()` return object contains several DataFrames. Understanding which
row to report is critical.

### The Three Estimation Rows

```python
result = rdrobust(y, x, c=50)

# Point estimates and inference
print(result.coef)   # 3 rows: Conventional, Bias-Corrected, Robust
print(result.se)     # Standard errors for each
print(result.pv)     # p-values
print(result.ci)     # Confidence intervals
```

| Row (index) | Label | What It Is | When to Use |
|-------------|-------|------------|-------------|
| 0 | Conventional | Local polynomial estimate with conventional SE | Rarely -- ignores bias |
| 1 | Bias-Corrected | Bias-corrected estimate with conventional SE | Rarely -- SE not adjusted for bias correction |
| **2** | **Robust** | **Bias-corrected estimate with robust SE** | **Always -- this is the recommended inference** (Calonico, Cattaneo, and Titiunik 2014) |

The Robust row uses the bias-corrected point estimate AND adjusts the standard
errors to account for the bias correction procedure. Reporting the Conventional
row ignores the entire methodological contribution of the CCT framework.

### Extracting Results Programmatically

```python
result = rdrobust(y, x, c=50)

# --- Extract key results ---
# INTENT: Extract the Robust row (index 2) for reporting
tau = result.coef.iloc[2, 0]          # Bias-corrected point estimate
se = result.se.iloc[2, 0]            # Robust standard error
pval = result.pv.iloc[2, 0]          # Robust p-value
ci_lower = result.ci.iloc[2, 0]      # Robust CI lower bound
ci_upper = result.ci.iloc[2, 1]      # Robust CI upper bound

# Bandwidth and sample sizes
h_left = result.bws.iloc[0, 0]       # Bandwidth, left of cutoff
h_right = result.bws.iloc[0, 1]      # Bandwidth, right of cutoff
n_left = result.N_h[0]               # Observations within bandwidth, left
n_right = result.N_h[1]              # Observations within bandwidth, right

print(f"RD Estimate (robust): {tau:.3f}")
print(f"Robust SE: {se:.3f}")
print(f"Robust 95% CI: [{ci_lower:.3f}, {ci_upper:.3f}]")
print(f"p-value: {pval:.4f}")
print(f"Bandwidth (h): {h_left:.3f} (left), {h_right:.3f} (right)")
print(f"Effective N: {n_left} (left) + {n_right} (right) = {n_left + n_right}")
```

### The Estimate DataFrame

```python
# The Estimate attribute gives a compact summary
print(result.Estimate)
# Columns: tau.us (conventional), tau.bc (bias-corrected), se.us, se.rb
# tau.bc is the bias-corrected estimate; se.rb is the robust SE
```

### Bandwidth DataFrame

```python
print(result.bws)
# Rows: h (estimation bandwidth), b (bias bandwidth)
# Columns: left, right
# h is the main bandwidth; b is used for bias estimation (typically wider)
```

## Bandwidth Selection

Bandwidth is the single most consequential implementation choice in RD. Too narrow
yields imprecision; too wide introduces bias from observations far from the cutoff.

### Data-Driven Bandwidth Selection

```python
# Standalone bandwidth selection (same computation rdrobust does internally)
bw = rdbwselect(y, x, c=50)
print(bw)
```

### Bandwidth Selection Methods

`rdbwselect()` offers 10 methods in two families:

| Family | Methods | Use Case |
|--------|---------|----------|
| **MSE-optimal** | `mserd` (default), `msetwo`, `msesum`, `msecomb1`, `msecomb2` | Point estimation -- minimizes MSE of the RD estimator |
| **CER-optimal** | `cerrd`, `certwo`, `cersum`, `cercomb1`, `cercomb2` | Inference -- minimizes coverage error of confidence intervals |

```python
# MSE-optimal (default) -- good for point estimation
bw_mse = rdbwselect(y, x, c=50, bwselect="mserd")

# CER-optimal -- narrower, better coverage properties
bw_cer = rdbwselect(y, x, c=50, bwselect="cerrd")

# Two-sided (different bandwidths left and right)
bw_two = rdbwselect(y, x, c=50, bwselect="msetwo")
```

The `"mserd"` selector produces a common bandwidth for both sides. Use `"msetwo"`
to allow different bandwidths left and right of the cutoff, which is useful when
the data density or curvature differs on each side.

**Deprecated selectors:** `"IK"`, `"CCT"`, and `"CV"` are no longer supported and
will raise errors. These correspond to older bandwidth selection methods; use the
MSE/CER family instead.

### Manual Bandwidth Specification

```python
# Symmetric bandwidth
result = rdrobust(y, x, c=50, h=10)

# Asymmetric bandwidth (different left and right)
result = rdrobust(y, x, c=50, h=[8, 12])

# Set bias bandwidth separately
result = rdrobust(y, x, c=50, h=10, b=15)
```

## Fuzzy RD

In a fuzzy RD, crossing the cutoff changes the *probability* of treatment but not
deterministically. Pass the treatment variable to the `fuzzy` parameter. Internally,
`rdrobust` computes a Wald ratio (reduced form / first stage) at the cutoff,
estimating a LATE for compliers.

```python
# --- Fuzzy RD ---
# INTENT: Estimate LATE where cutoff affects treatment probability, not assignment
y = df["outcome"].to_numpy()
x = df["running_var"].to_numpy()       # Running variable (score)
d = df["treatment_received"].to_numpy() # Actual treatment take-up (binary)

result = rdrobust(y, x, c=50, fuzzy=d)
print(result)
```

### Diagnosing Weak First Stage

Fuzzy RD shares the weak instrument problem with IV. If the first-stage
discontinuity (jump in treatment probability at the cutoff) is small, the Wald
ratio amplifies noise and produces unreliable estimates.

```python
# INTENT: Check that the first stage is strong
# Run rdrobust with treatment as the outcome
first_stage = rdrobust(d, x, c=50)
print(first_stage)
# REASONING: The point estimate should show a meaningful jump in treatment
# probability. If the jump is small relative to its SE, the fuzzy RD is
# unreliable -- analogous to a weak instrument.
```

## Kink RD

A kink RD estimates the change in the *slope* (not level) of the relationship at
the cutoff. Use `deriv=1` to estimate the treatment effect on the first derivative.

```python
# --- Kink RD ---
# INTENT: Estimate change in slope at the cutoff (not level)
# ASSUMES: Policy creates a kink (slope change), not a jump, at the threshold
result = rdrobust(y, x, c=50, deriv=1)
print(result)
```

Kink RD requires `p >= 2` (at minimum local quadratic) because estimating a
derivative requires a higher-order polynomial. If you set `deriv=1` with the
default `p=1`, rdrobust will automatically adjust.

## Covariates

Including pre-determined covariates can improve precision without affecting
consistency (the RD estimate is consistent without covariates if the continuity
assumption holds).

```python
# --- With covariates ---
# INTENT: Include pre-determined covariates for precision gains
# ASSUMES: Covariates are predetermined (not affected by treatment)
covs = df[["age", "female", "baseline_score"]].to_pandas()
# Note: covariates must be a DataFrame or 2D array, not a Series

result = rdrobust(y, x, c=50, covs=covs)
print(result)
```

### Covariate Handling Details

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `covs` | None | Pre-determined covariates (DataFrame or 2D array) |
| `covs_drop` | True | Drop collinear covariates automatically |

Covariates enter the local polynomial regression as additional regressors.
They do NOT change the target parameter -- the RD estimate is still the
discontinuity in the conditional expectation of Y at the cutoff.

## Clustering and Weights

### Clustered Standard Errors

```python
# Cluster SEs at the school level
cluster_var = df["school_id"].to_numpy()
result = rdrobust(y, x, c=50, cluster=cluster_var)
print(result)
```

### Sampling Weights

```python
# With sampling weights
w = df["weight"].to_numpy()
result = rdrobust(y, x, c=50, weights=w)
print(result)
```

### Variance Estimator Options

| VCE | Description | When to Use |
|-----|-------------|-------------|
| `"nn"` (default) | Nearest-neighbor | General purpose; robust to heteroskedasticity |
| `"hc0"` | Heteroskedasticity-consistent (HC0) | When NN is undesirable |
| `"hc1"` | HC1 (small-sample adjustment) | Small samples |
| `"hc2"` | HC2 (leverage-adjusted) | When leverage varies substantially |
| `"hc3"` | HC3 (jackknife-like) | Conservative small-sample inference |

Note: `"cr3"` (cluster-robust with small-sample correction) is NOT available in
v1.3.0 -- it was added in v2.0.0.

## RD Visualization

### Why rdplot() Cannot Be Used

`rdplot()` in v1.3.0 crashes with `ValueError: assignment destination is read-only`
due to a NumPy/pandas compatibility issue at line 692 of `rdplot.py`. This is fixed
in v2.0.0, but v1.3.0 is what is installed. Use the manual plotting workaround below.

### Manual RD Plot with plotnine

The standard RD visualization shows: (1) binned scatter of outcome vs. running
variable, (2) fitted local polynomial curves on each side of the cutoff, and
(3) a visible gap at the cutoff representing the treatment effect.

```python
from plotnine import (
    ggplot, aes, geom_point, geom_vline, geom_line, geom_smooth,
    labs, theme_minimal, scale_color_manual
)
import numpy as np
import polars as pl

# --- Config ---
CUTOFF = 50
BIN_COUNT = 40  # Number of bins for the scatter (20 per side is typical)

# --- Prepare binned means ---
# INTENT: Create binned scatter plot data (evenly spaced bins on each side)
df_plot = df.with_columns(
    pl.when(pl.col("running_var") < CUTOFF)
    .then(pl.lit("below"))
    .otherwise(pl.lit("above"))
    .alias("side")
)

# Bin within each side separately for even spacing
left = df_plot.filter(pl.col("side") == "below")
right = df_plot.filter(pl.col("side") == "above")

def make_bins(data, col, outcome, n_bins):
    """Create binned means for RD scatter plot."""
    arr = data[col].to_numpy()
    out = data[outcome].to_numpy()
    bins = np.linspace(arr.min(), arr.max(), n_bins + 1)
    bin_centers = []
    bin_means = []
    for i in range(len(bins) - 1):
        mask = (arr >= bins[i]) & (arr < bins[i + 1])
        if i == len(bins) - 2:
            mask = (arr >= bins[i]) & (arr <= bins[i + 1])
        if mask.sum() > 0:
            bin_centers.append((bins[i] + bins[i + 1]) / 2)
            bin_means.append(out[mask].mean())
    return pl.DataFrame({"x": bin_centers, "y": bin_means})

bins_left = make_bins(left, "running_var", "outcome", BIN_COUNT // 2)
bins_right = make_bins(right, "running_var", "outcome", BIN_COUNT // 2)

bins_all = pl.concat([
    bins_left.with_columns(pl.lit("Below cutoff").alias("side")),
    bins_right.with_columns(pl.lit("Above cutoff").alias("side")),
]).to_pandas()

# --- Fitted curves ---
# INTENT: Overlay local polynomial fits on each side (matching rdrobust's p=1 default)
from numpy.polynomial.polynomial import polyfit, polyval

x_left = left["running_var"].to_numpy()
y_left = left["outcome"].to_numpy()
x_right = right["running_var"].to_numpy()
y_right = right["outcome"].to_numpy()

# Local linear fit (p=1) on each side
coef_left = polyfit(x_left, y_left, deg=1)
coef_right = polyfit(x_right, y_right, deg=1)

x_grid_left = np.linspace(x_left.min(), CUTOFF, 100)
x_grid_right = np.linspace(CUTOFF, x_right.max(), 100)

fit_df = pl.concat([
    pl.DataFrame({
        "x": x_grid_left,
        "y_fit": polyval(x_grid_left, coef_left),
        "side": ["Below cutoff"] * len(x_grid_left),
    }),
    pl.DataFrame({
        "x": x_grid_right,
        "y_fit": polyval(x_grid_right, coef_right),
        "side": ["Above cutoff"] * len(x_grid_right),
    }),
]).to_pandas()

# --- Plot ---
p = (
    ggplot()
    + geom_point(aes(x="x", y="y", color="side"), data=bins_all, size=2, alpha=0.7)
    + geom_line(aes(x="x", y="y_fit", color="side"), data=fit_df, size=1)
    + geom_vline(xintercept=CUTOFF, linetype="dashed", color="gray")
    + scale_color_manual(values={"Below cutoff": "#2166AC", "Above cutoff": "#B2182B"})
    + labs(
        x="Running Variable",
        y="Outcome",
        title="Regression Discontinuity Plot",
        color="",
    )
    + theme_minimal()
)
p.save(f"{OUTPUT_DIR}/rd_plot.png", width=10, height=6, dpi=150)
print(f"[SAVED] {OUTPUT_DIR}/rd_plot.png")
```

### Simplified RD Plot (Quick Version)

For a faster visualization without custom binning, use `geom_smooth` directly:

```python
import pandas as pd

df_pd = df.select(["running_var", "outcome"]).to_pandas()
df_pd["side"] = np.where(df_pd["running_var"] < CUTOFF, "Below", "Above")

p = (
    ggplot(df_pd, aes(x="running_var", y="outcome", color="side"))
    + geom_point(alpha=0.1, size=0.5)
    + geom_smooth(method="lm", se=True)
    + geom_vline(xintercept=CUTOFF, linetype="dashed")
    + scale_color_manual(values={"Below": "#2166AC", "Above": "#B2182B"})
    + labs(x="Running Variable", y="Outcome", title="RD Plot (Quick)")
    + theme_minimal()
)
```

This is less precise than the binned version (global linear fit, not local) but
adequate for a first look.

## Manipulation Testing

If agents can manipulate the running variable to sort above or below the cutoff,
the RD design is invalid. The McCrary (2008) density test checks for a discontinuity
in the density of the running variable at the cutoff.

### Without rddensity (Manual Approach)

Since `rddensity` is not installed, use a visual histogram approach:

```python
import matplotlib.pyplot as plt

# --- Manipulation check: histogram ---
# INTENT: Visual test for sorting/bunching at the cutoff
x_arr = df["running_var"].to_numpy()

fig, ax = plt.subplots(figsize=(10, 5))
bins = np.linspace(x_arr.min(), x_arr.max(), 80)
ax.hist(x_arr[x_arr < CUTOFF], bins=bins[bins < CUTOFF], color="#2166AC",
        alpha=0.7, label="Below cutoff", edgecolor="white")
ax.hist(x_arr[x_arr >= CUTOFF], bins=bins[bins >= CUTOFF], color="#B2182B",
        alpha=0.7, label="Above cutoff", edgecolor="white")
ax.axvline(CUTOFF, color="black", linestyle="--", linewidth=1.5, label="Cutoff")
ax.set_xlabel("Running Variable")
ax.set_ylabel("Frequency")
ax.set_title("McCrary-Style Density Check")
ax.legend()
fig.savefig(f"{OUTPUT_DIR}/density_check.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"[SAVED] {OUTPUT_DIR}/density_check.png")
# REASONING: A visible jump in density at the cutoff suggests manipulation.
# This is a visual check only -- for formal inference, install rddensity.
```

### Formal Density Test (If rddensity Is Installed)

```python
# pip install rddensity  # Not installed by default
from rddensity import rddensity

# Formal manipulation test
density_test = rddensity(x_arr, c=CUTOFF)
print(density_test.summary())
# REASONING: Null hypothesis is no discontinuity in density.
# Rejection (p < 0.05) indicates manipulation -- the RD design is compromised.
```

## Covariate Balance at the Cutoff

Pre-determined covariates should be continuous through the cutoff. A discontinuity
in covariates suggests either manipulation or confounding that invalidates the RD
design.

```python
# --- Covariate balance test ---
# INTENT: Verify no discontinuity in pre-determined covariates at cutoff
# REASONING: Each covariate is used as outcome in rdrobust; significant
# discontinuity suggests sorting or confounding

covariates = ["age", "female", "baseline_score", "income"]

balance_results = []
for cov in covariates:
    cov_y = df[cov].to_numpy()
    cov_result = rdrobust(cov_y, x, c=CUTOFF)
    tau = cov_result.coef.iloc[2, 0]
    pval = cov_result.pv.iloc[2, 0]
    balance_results.append({
        "covariate": cov,
        "rd_estimate": round(tau, 4),
        "robust_pval": round(pval, 4),
        "balanced": "Yes" if pval > 0.05 else "NO -- IMBALANCE",
    })

balance_df = pl.DataFrame(balance_results)
print(balance_df)
# ASSUMES: All covariates are pre-determined (measured before treatment).
# If any p-value < 0.05, investigate -- the discontinuity is suspicious.
```

## Bandwidth Sensitivity Analysis

The MSE-optimal bandwidth is a single data-driven choice. Robustness requires
showing that results hold across a range of bandwidths.

```python
# --- Bandwidth sensitivity ---
# INTENT: Verify results are robust to bandwidth choice
# REASONING: Standard practice per Cattaneo, Idrobo, and Titiunik (2020)

# Get the optimal bandwidth first
base_result = rdrobust(y, x, c=CUTOFF)
h_opt = base_result.bws.iloc[0, 0]  # Left-side optimal bandwidth

multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
sensitivity_results = []

for mult in multipliers:
    h = h_opt * mult
    res = rdrobust(y, x, c=CUTOFF, h=h)
    tau = res.coef.iloc[2, 0]
    se = res.se.iloc[2, 0]
    pval = res.pv.iloc[2, 0]
    ci_lo = res.ci.iloc[2, 0]
    ci_hi = res.ci.iloc[2, 1]
    n_eff = res.N_h[0] + res.N_h[1]
    sensitivity_results.append({
        "bandwidth_mult": mult,
        "bandwidth": round(h, 2),
        "estimate": round(tau, 4),
        "robust_se": round(se, 4),
        "robust_pval": round(pval, 4),
        "ci_lower": round(ci_lo, 4),
        "ci_upper": round(ci_hi, 4),
        "n_effective": n_eff,
    })

sens_df = pl.DataFrame(sensitivity_results)
print(sens_df)
# REASONING: If the sign/significance changes dramatically across bandwidths,
# the result is fragile and should be interpreted with caution.
```

## Placebo Cutoff Tests

Run the RD estimation at fake cutoffs where no treatment effect should exist. A
significant "effect" at a placebo cutoff suggests the model is picking up a smooth
relationship rather than a true discontinuity.

```python
# --- Placebo cutoff tests ---
# INTENT: Verify no spurious effects at cutoffs away from the true threshold
# REASONING: Standard practice to rule out smooth functional form as an
# alternative explanation for the observed discontinuity

# Use median of each side as placebo cutoffs
x_arr = df["running_var"].to_numpy()
placebo_left = np.median(x_arr[x_arr < CUTOFF])
placebo_right = np.median(x_arr[x_arr >= CUTOFF])

placebo_cutoffs = [placebo_left, placebo_right]
placebo_results = []

for pc in placebo_cutoffs:
    # Restrict to the appropriate side of the true cutoff
    if pc < CUTOFF:
        mask = x_arr < CUTOFF
    else:
        mask = x_arr >= CUTOFF
    res = rdrobust(y[mask], x_arr[mask], c=pc)
    tau = res.coef.iloc[2, 0]
    pval = res.pv.iloc[2, 0]
    placebo_results.append({
        "placebo_cutoff": round(pc, 2),
        "side": "left" if pc < CUTOFF else "right",
        "estimate": round(tau, 4),
        "robust_pval": round(pval, 4),
        "significant": "Yes -- CONCERN" if pval < 0.05 else "No (expected)",
    })

placebo_df = pl.DataFrame(placebo_results)
print(placebo_df)
# REASONING: Significant effects at placebo cutoffs undermine the causal
# interpretation at the true cutoff.
```

## Donut RD

A donut RD drops observations very close to the cutoff, which can be useful when:
- Manipulation is suspected near (but not exactly at) the cutoff
- There are mass points at the cutoff itself
- Heaping behavior concentrates observations at round numbers near the threshold

```python
# --- Donut RD ---
# INTENT: Exclude observations within a donut hole around the cutoff
# ASSUMES: Observations very close to cutoff may be problematic

donut_width = 1  # Exclude observations within 1 unit of cutoff
subset_mask = np.abs(x - CUTOFF) > donut_width

result_donut = rdrobust(y, x, c=CUTOFF, subset=subset_mask)
print(result_donut)
# REASONING: If the donut RD estimate differs substantially from the
# standard estimate, observations near the cutoff are driving the result --
# investigate why.
```

## Complete RD Analysis Template

This template provides the full diagnostic and estimation sequence for a sharp RD
analysis, suitable for adaptation into a DAAF pipeline script.

```python
# --- Config ---
import numpy as np
import polars as pl
from rdrobust import rdrobust, rdbwselect

CUTOFF = 50
OUTCOME = "test_score"
RUNNING = "assignment_score"
COVARIATES = ["age", "female", "baseline_score"]

# --- Load ---
df = pl.read_parquet(f"{DATA_DIR}/analysis_data.parquet")

y = df[OUTCOME].to_numpy()
x = df[RUNNING].to_numpy()

# --- Step 1: Manipulation test (visual) ---
# [Insert histogram code from Manipulation Testing section]

# --- Step 2: Covariate balance ---
for cov in COVARIATES:
    cov_y = df[cov].to_numpy()
    res = rdrobust(cov_y, x, c=CUTOFF)
    pval = res.pv.iloc[2, 0]
    print(f"  {cov}: RD estimate = {res.coef.iloc[2, 0]:.4f}, p = {pval:.4f}")
    assert pval > 0.01, f"CRITICAL: {cov} shows large imbalance (p={pval:.4f})"

# --- Step 3: Main estimation ---
result = rdrobust(y, x, c=CUTOFF)
print(result)

tau = result.coef.iloc[2, 0]
se = result.se.iloc[2, 0]
pval = result.pv.iloc[2, 0]
ci_lo, ci_hi = result.ci.iloc[2, 0], result.ci.iloc[2, 1]
h = result.bws.iloc[0, 0]
n_eff = result.N_h[0] + result.N_h[1]

print(f"\n=== Main Result (Robust) ===")
print(f"RD Estimate: {tau:.4f} (SE: {se:.4f})")
print(f"95% CI: [{ci_lo:.4f}, {ci_hi:.4f}]")
print(f"p-value: {pval:.4f}")
print(f"Bandwidth: {h:.2f} | Effective N: {n_eff}")

# --- Step 4: Bandwidth sensitivity ---
h_opt = result.bws.iloc[0, 0]
for mult in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
    res = rdrobust(y, x, c=CUTOFF, h=h_opt * mult)
    print(f"  h={h_opt * mult:.1f} ({mult}x): "
          f"tau={res.coef.iloc[2, 0]:.4f}, p={res.pv.iloc[2, 0]:.4f}")

# --- Step 5: Placebo cutoffs ---
x_below = x[x < CUTOFF]
x_above = x[x >= CUTOFF]
for label, pc, mask in [
    ("left", np.median(x_below), x < CUTOFF),
    ("right", np.median(x_above), x >= CUTOFF),
]:
    res = rdrobust(y[mask], x[mask], c=pc)
    print(f"  Placebo ({label}, c={pc:.1f}): "
          f"tau={res.coef.iloc[2, 0]:.4f}, p={res.pv.iloc[2, 0]:.4f}")

# --- Step 6: RD plot ---
# [Insert manual RD plot code from RD Visualization section]

# --- Validate ---
print(f"\n=== Validation ===")
print(f"Total N: {len(y)}")
print(f"N below cutoff: {np.sum(x < CUTOFF)}")
print(f"N above cutoff: {np.sum(x >= CUTOFF)}")
print(f"Running variable range: [{x.min():.2f}, {x.max():.2f}]")
assert n_eff > 20, f"Effective sample size too small: {n_eff}"
```

## Gotchas

### 1. rdplot() Crashes in v1.3.0

`rdplot()` raises `ValueError: assignment destination is read-only` due to a
NumPy/pandas compatibility bug at line 692 of `rdplot.py`. Use the manual plotting
workaround in the RD Visualization section. Fixed in v2.0.0.

### 2. Covariates May Crash in v1.3.0

The `covs` parameter in `rdrobust()` may crash with `TypeError: only 0-dimensional
arrays can be converted to Python scalars` due to the same NumPy/pandas compatibility
bug that affects `rdplot()`. This is fixed in v2.0.0. If you encounter this error,
estimate without covariates -- the RD estimate is consistent without covariates if the
continuity assumption holds (covariates only improve precision).

### 3. cr3 VCE Not Available

The `vce="cr3"` option (cluster-robust with small-sample correction) was added in
v2.0.0 and is not available in v1.3.0. Use `vce="nn"` (default) with `cluster=`
for clustered inference.

### 4. Deprecated Bandwidth Selectors Raise Errors

The old selectors `"IK"` (Imbens-Kalyanaraman), `"CCT"` (Calonico-Cattaneo-Titiunik
2014), and `"CV"` (cross-validation) are deprecated and raise errors. Use the
MSE/CER family: `"mserd"`, `"msetwo"`, `"cerrd"`, etc.

### 5. Report the Robust Row, Not Conventional

The Robust row (index 2) of `result.coef`, `result.se`, `result.pv`, and `result.ci`
is the recommended inference. The Conventional row (index 0) ignores bias correction
and understates uncertainty. This is the most common reporting error in applied RD
work. Source: Calonico, Cattaneo, and Titiunik (2014).

### 6. rdplot Defaults Differ from rdrobust

If rdplot were working, note that it uses `p=4` (quartic) and `kernel="uni"` (uniform)
by default -- different from rdrobust's `p=1` (local linear) and `kernel="tri"`
(triangular). The rdplot defaults are for display smoothness, not inference. Do not
confuse the visual fit with the inferential model.

### 7. masspoints="adjust" Changes Results

The default `masspoints="adjust"` detects repeated values (mass points) in the
running variable and adjusts bandwidth selection and variance estimation accordingly.
Setting `masspoints="off"` ignores this adjustment and can produce different results.
If your running variable has many ties (e.g., integer-valued test scores), the
adjustment is important.

### 8. Bandwidth Can Be Scalar or Tuple

The `h` parameter accepts a scalar (symmetric bandwidth) or a list/tuple of two
values `[h_left, h_right]` (asymmetric). The same applies to `b` (bias bandwidth).

```python
# Symmetric
rdrobust(y, x, h=10)

# Asymmetric
rdrobust(y, x, h=[8, 12])
```

### 9. Covariates Must Be DataFrame or 2D Array

When passing multiple covariates, `covs` must be a DataFrame or 2D numpy array.
A single pandas Series works for one covariate, but a list of Series will fail.

```python
# Wrong: list of Series
covs = [df["age"].to_pandas(), df["female"].to_pandas()]  # Will fail

# Right: DataFrame
covs = df[["age", "female"]].to_pandas()
```

### 10. Do NOT Use High-Order Polynomials

Gelman and Imbens (2019) demonstrated that high-order polynomial RD estimators
(p > 2) are noisy, sensitive to the degree of the polynomial, and lead to
unreliable confidence intervals. Local linear (p=1) or local quadratic (p=2) are
strongly preferred. The default p=1 is almost always the right choice.

### 11. Do NOT Cluster on the Running Variable

Kolesar and Rothe (2018) showed that clustering standard errors on the running
variable is invalid in RD designs. If clustering is needed, cluster on a
substantive grouping variable (school, district, etc.), not the running variable
itself.

### 12. Discrete Running Variables Break Standard RD

When the running variable takes only a few distinct values (e.g., class size
thresholds with integer enrollment counts), the standard continuity-based RD
framework does not apply directly. See Kolesar and Rothe (2018) for alternative
inference methods. With many distinct values (e.g., test scores with fine
granularity), the standard approach with `masspoints="adjust"` is appropriate.

### 13. Fuzzy RD Has Weak Instrument Problems

When the first-stage jump in treatment probability at the cutoff is small, the
fuzzy RD Wald ratio amplifies noise, producing wide confidence intervals and
potentially misleading point estimates. Always check the first stage (run
`rdrobust(d, x)` where d is treatment) before interpreting fuzzy RD results.
See the Fuzzy RD section above.

### 14. RD Estimates Are Inherently LOCAL

The RD estimate is identified only at the cutoff. It says nothing about treatment
effects at other values of the running variable. Extrapolating the RD estimate to
the full population is not justified by the design. This is a feature, not a bug --
the local estimate has strong internal validity precisely because it exploits only
local variation.

### 15. McCrary/rddensity Rejection Compromises the Design

If a manipulation test rejects the null of continuity in the running variable's
density at the cutoff, the RD design is compromised. This is not a caveat to
note in passing -- it undermines the entire identification strategy. If rejection
occurs, investigate the source of manipulation and consider whether a donut RD
or alternative design is more appropriate. See McCrary (2008) and Cattaneo,
Jansson, and Ma (2020).

## References

### Core rdrobust Papers

Calonico, S., Cattaneo, M.D., and Titiunik, R. (2014). "Robust Nonparametric
Confidence Intervals for Regression-Discontinuity Designs." *Econometrica*,
82(6), 2295-2326. https://doi.org/10.3982/ECTA11757

Calonico, S., Cattaneo, M.D., Farrell, M.H., and Titiunik, R. (2017). "rdrobust:
Software for Regression-Discontinuity Designs." *Stata Journal*, 17(2), 372-404.
https://doi.org/10.1177/1536867X1701700208

### RD Methodology Textbooks

Cattaneo, M.D., Idrobo, N., and Titiunik, R. (2020). *A Practical Introduction to
Regression Discontinuity Designs: Foundations.* Cambridge Elements in Quantitative
and Computational Methods for the Social Sciences. Cambridge University Press.
https://doi.org/10.1017/9781108684606

Cattaneo, M.D., Idrobo, N., and Titiunik, R. (2024). *A Practical Introduction to
Regression Discontinuity Designs: Extensions.* Cambridge Elements in Quantitative
and Computational Methods for the Social Sciences. Cambridge University Press.
https://doi.org/10.1017/9781009441896

Cunningham, S. (2021). *Causal Inference: The Mixtape.* Yale University Press.
Ch. 6: Regression Discontinuity. https://mixtape.scunning.com/

### Methodology Papers

Lee, D.S. and Lemieux, T. (2010). "Regression Discontinuity Designs in Economics."
*Journal of Economic Literature*, 48(2), 281-355.
https://doi.org/10.1257/jel.48.2.281

Imbens, G.W. and Lemieux, T. (2008). "Regression Discontinuity Designs: A Guide
to Practice." *Journal of Econometrics*, 142(2), 615-635.
https://doi.org/10.1016/j.jeconom.2007.05.001

Gelman, A. and Imbens, G.W. (2019). "Why High-Order Polynomials Should Not Be Used
in Regression Discontinuity Designs." *Journal of Business & Economic Statistics*,
37(3), 447-456. https://doi.org/10.1080/07350015.2017.1366909

### Manipulation and Discrete Running Variables

McCrary, J. (2008). "Manipulation of the Running Variable in the Regression
Discontinuity Design: A Density Test." *Journal of Econometrics*, 142(2), 698-714.
https://doi.org/10.1016/j.jeconom.2007.05.005

Cattaneo, M.D., Jansson, M., and Ma, X. (2020). "Simple Local Polynomial Density
Estimators." *Journal of the American Statistical Association*, 115(531), 1449-1455.
https://doi.org/10.1080/01621459.2019.1635480

Kolesar, M. and Rothe, C. (2018). "Inference in Regression Discontinuity Designs
with a Discrete Running Variable." *American Economic Review*, 108(8), 2277-2304.
https://doi.org/10.1257/aer.20160945
