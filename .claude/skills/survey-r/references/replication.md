# survey Replicate Weight Reference

survey 4.5 on R 4.5.3 -- syntax and library guidance only.

---

## Contents

1. [Overview: Replicate Weights vs. Taylor](#overview-replicate-weights-vs-taylor)
2. [svrepdesign() -- Creating Replicate Weight Designs](#svrepdesign----creating-replicate-weight-designs)
3. [as.svrepdesign() -- Converting Taylor to Replicate](#assvrepdesign----converting-taylor-to-replicate)
4. [BRR (Balanced Repeated Replication)](#brr-balanced-repeated-replication)
5. [Jackknife (JK1, JKn)](#jackknife-jk1-jkn)
6. [Bootstrap Replicate Weights](#bootstrap-replicate-weights)
7. [Successive Difference Replication (ACS PUMS)](#successive-difference-replication-acs-pums)
8. [Estimation with Replicate Designs](#estimation-with-replicate-designs)
9. [Federal Survey Replicate Weight Patterns](#federal-survey-replicate-weight-patterns)

---

## Overview: Replicate Weights vs. Taylor

Two approaches to variance estimation in complex surveys:

| Approach | How It Works | When to Use |
|----------|-------------|-------------|
| **Taylor linearization** | Analytic formula using strata and PSU | Default; requires design variables |
| **Replicate weights** | Re-estimate with perturbed weights; variance = variability across replicates | When provided by data producer, or for nonsmooth statistics |

Both produce valid design-based SEs. The key advantage of replicate weights is
that they encode the full design information -- the analyst does not need to
know the strata/PSU structure.

### When to Prefer Replicate Weights

- Data producer supplies replicate weight columns (ACS PUMS, CPS supplements)
- Estimating medians, quantiles, or other nonsmooth statistics
- Complex derived statistics (ratios of subgroup estimates)
- Want to match published estimates exactly (use the publisher's method)

---

## svrepdesign() -- Creating Replicate Weight Designs

`svrepdesign()` creates a design object from pre-computed replicate weight
columns.

### Basic Syntax

```r
des <- svrepdesign(
  weights = ~main_weight,          # main analysis weight
  repweights = "prefix[0-9]+",     # regex matching replicate weight columns
  type = "BRR",                    # replication method
  data = df
)
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `weights` | Formula for the main analysis weight |
| `repweights` | Regex pattern matching replicate weight column names, OR a matrix/data.frame of replicate weights |
| `type` | Replication type: `"BRR"`, `"Fay"`, `"JK1"`, `"JKn"`, `"bootstrap"`, `"ACS"`, `"successive-difference"`, `"mrbbootstrap"` |
| `rho` | Fay's coefficient for `type = "Fay"` (typically 0.3-0.5) |
| `data` | Data frame |
| `mse` | If `TRUE`, compute variance around the full-sample estimate (not the mean of replicates). Default `FALSE` for most types, `TRUE` for ACS |
| `combined.weights` | If `TRUE`, replicate weights already include the base weight. Default `TRUE` |

### Specifying Replicate Weight Columns

```r
# Pattern match: columns matching regex
des <- svrepdesign(
  weights = ~pwgtp,
  repweights = "pwgtp[0-9]+",      # matches pwgtp1, pwgtp2, ..., pwgtp80
  type = "ACS",
  data = acs_data
)

# Explicit column names
des <- svrepdesign(
  weights = ~finalwgt,
  repweights = paste0("brr_wt", 1:64),
  type = "BRR",
  data = df
)
```

---

## as.svrepdesign() -- Converting Taylor to Replicate

Convert a Taylor linearization design to a replicate weight design. Useful when
you need replicate-weight variance estimation but only have design variables.

```r
# Start with a Taylor design
des_taylor <- svydesign(
  ids = ~psu, strata = ~stratum, weights = ~weight,
  data = df, nest = TRUE
)

# Convert to JKn replicate weights
des_jkn <- as.svrepdesign(des_taylor, type = "JKn")

# Convert to bootstrap
des_boot <- as.svrepdesign(des_taylor, type = "bootstrap",
                            replicates = 200)

# Convert to BRR (requires exactly 2 PSUs per stratum)
des_brr <- as.svrepdesign(des_taylor, type = "BRR")
```

### When to Convert

- Estimating quantiles or medians (replicate methods more robust)
- Creating replicate weights for distribution to other analysts
- BRR conversion requires exactly 2 PSUs per stratum (common in federal surveys)

---

## BRR (Balanced Repeated Replication)

BRR works by splitting PSUs within each stratum into two half-samples and
computing the estimate for each balanced combination.

### Requirements

- Exactly 2 PSUs per stratum (standard in many federal survey designs)
- If more than 2 PSUs, use JKn or bootstrap instead

### Setup

```r
# Direct from replicate weights
des <- svrepdesign(
  weights = ~finalwgt,
  repweights = "brr[0-9]+",
  type = "BRR",
  data = df
)

# Convert from Taylor (requires 2 PSUs/stratum)
des_brr <- as.svrepdesign(des_taylor, type = "BRR")
```

### Fay's Method (Modified BRR)

Fay's method perturbs weights by a factor rho (0 < rho < 1) instead of
completely deleting half-samples. Reduces instability for small domains.

```r
des <- svrepdesign(
  weights = ~finalwgt,
  repweights = "brr[0-9]+",
  type = "Fay",
  rho = 0.5,                       # Fay coefficient
  data = df
)
```

**Common Fay coefficients by survey:**
- NHANES III: rho = 0.3
- ECLS-K: varies by round (check documentation)

---

## Jackknife (JK1, JKn)

### JK1 -- Delete-One Jackknife

For unstratified designs. Drops one PSU at a time.

```r
des <- svrepdesign(
  weights = ~finalwgt,
  repweights = "jk[0-9]+",
  type = "JK1",
  data = df
)
```

### JKn -- Delete-One-Group (Stratified) Jackknife

For stratified designs. Drops one PSU from each stratum. Most common jackknife
method for federal surveys.

```r
des <- svrepdesign(
  weights = ~finalwgt,
  repweights = "jk[0-9]+",
  type = "JKn",
  data = df
)

# Or convert from Taylor
des_jkn <- as.svrepdesign(des_taylor, type = "JKn")
```

---

## Bootstrap Replicate Weights

Bootstrap replication generates variance estimates by resampling PSUs with
replacement within strata.

```r
# From pre-computed bootstrap weights
des <- svrepdesign(
  weights = ~finalwgt,
  repweights = "bswt[0-9]+",
  type = "bootstrap",
  data = df
)

# Generate bootstrap weights from Taylor design
des_boot <- as.svrepdesign(des_taylor, type = "bootstrap",
                            replicates = 500)
```

### Number of Replicates

- 50-200 replicates: adequate for point estimates and SEs
- 500+ replicates: needed for CI coverage properties
- More replicates = more stable SEs but more computation

---

## Successive Difference Replication (ACS PUMS)

The ACS PUMS uses a unique variance estimation method called successive
difference replication (SDR). The `survey` package supports this via
`type = "ACS"` or `type = "successive-difference"`.

```r
# Person-level ACS PUMS
des_person <- svrepdesign(
  weights = ~pwgtp,
  repweights = "pwgtp[0-9]+",      # pwgtp1 through pwgtp80
  type = "ACS",                     # = "successive-difference" + mse = TRUE
  data = acs_data
)

# Household-level ACS PUMS
des_hh <- svrepdesign(
  weights = ~wgtp,
  repweights = "wgtp[0-9]+",       # wgtp1 through wgtp80
  type = "ACS",
  data = acs_hh_data
)
```

### Key Notes for ACS

- Always use `type = "ACS"` (this sets `mse = TRUE` and the correct scale)
- Person weights: `pwgtp` (main) + `pwgtp1`-`pwgtp80` (replicates)
- Household weights: `wgtp` (main) + `wgtp1`-`wgtp80` (replicates)
- No strata or PSU variables needed -- replicate weights encode the design

---

## Estimation with Replicate Designs

Once a replicate weight design is created, all estimation functions work
identically to Taylor designs. The design object determines which variance
method is used internally.

```r
# These work the same regardless of whether des is Taylor or replicate
svymean(~income, design = des, na.rm = TRUE)
svytotal(~enrollment, design = des, na.rm = TRUE)
svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)
svyglm(y ~ x1 + x2, design = des, family = gaussian())
svyquantile(~income, design = des, quantiles = 0.5, na.rm = TRUE)
```

This is the key design principle of the `survey` package -- the estimation
interface is the same regardless of the variance estimation method. The choice
between Taylor and replicate is encoded in the design object, not in the
estimation call.

---

## Federal Survey Replicate Weight Patterns

| Survey | Type | Reps | Weight Prefix | Main Weight | Notes |
|--------|------|------|---------------|-------------|-------|
| **ACS PUMS** | ACS/SDR | 80 | `pwgtp` / `wgtp` | `pwgtp` / `wgtp` | Use `type = "ACS"` |
| **CPS ASEC** | BRR/Fay | 160 | `repwtp` | `marsupwt` | rho varies by vintage |
| **ECLS-K:2011** | JKn | varies | Round-specific | Round-specific | Check per-round docs |
| **SIPP** | BRR | varies | `repwgt` | `wpfinwgt` | Panel-specific |
| **NHANES III** | Fay BRR | varies | Survey-specific | Survey-specific | rho = 0.3 |

### ACS PUMS Complete Example

```r
# --- Config ---
library(survey)
library(arrow)

# --- Load ---
acs <- read_parquet("data/raw/acs_pums_2022.parquet")

# --- Design ---
# INTENT: ACS PUMS with successive difference replication
# REASONING: Public-use file has no design variables; replicate weights
#   encode the complex design structure
# ASSUMES: Person-level analysis; 80 replicate weight columns
des <- svrepdesign(
  weights = ~pwgtp,
  repweights = "pwgtp[0-9]+",
  type = "ACS",
  data = acs
)

# --- Estimate ---
svymean(~pincp, design = des, na.rm = TRUE)
svyby(~pincp, ~sex, design = des, svymean, na.rm = TRUE)
```
