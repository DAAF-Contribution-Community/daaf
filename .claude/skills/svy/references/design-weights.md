# svy Design and Weights Reference

svy v0.19.0 — syntax and library guidance only. Signatures below were verified against
the installed library (`/daaf/scripts/smoke_tests/smoke_svy_a.py`); where a construct was
not exercised by the smoke test it is flagged **[not smoke-tested at 0.19.0]** and you
should introspect (`inspect.signature`, a live call) before relying on it.

---

## Contents

1. [Core Concepts](#core-concepts)
2. [Creating a Taylor Linearization Design](#creating-a-taylor-linearization-design)
3. [Finite Population Correction (FPC)](#finite-population-correction-fpc)
4. [Pre-Existing Replicate Weights](#pre-existing-replicate-weights)
5. [Creating Replicate Weights From a Design](#creating-replicate-weights-from-a-design)
6. [Weight Types and Selection](#weight-types-and-selection)
7. [The Weighting Namespace: Calibration and Adjustment](#the-weighting-namespace-calibration-and-adjustment)
8. [Singleton PSU Handling](#singleton-psu-handling)
9. [Reading and Writing Survey Data Files (svy-io)](#reading-and-writing-survey-data-files-svy-io)
10. [Federal Survey Design Quick-Reference](#federal-survey-design-quick-reference)
11. [Combining Survey Cycles](#combining-survey-cycles)
12. [Polars Integration Notes](#polars-integration-notes)
13. [Migration from samplics](#migration-from-samplics)

---

## Core Concepts

Every svy analysis starts with two objects:

1. **`svy.Design`** — describes the sampling structure (how units were selected)
2. **`svy.Sample`** — binds data to a design, enabling estimation

The design determines how variance is estimated. Two approaches:

| Approach | When to Use | What You Need |
|----------|-------------|---------------|
| **Taylor linearization** | Default; most common | Stratum, PSU, and weight columns in the data |
| **Replicate weights** | When provided by data producer, or when Taylor assumptions are problematic | Pre-computed replicate weight columns + main weight, or created from the design |

Both produce valid design-based inference. Taylor linearization requires design variables (strata, PSU); replicate weights encode the design information within the weight columns themselves. **Taylor variance is deterministic in 0.19.0** (PSUs are sorted and the std HashSet dropped in svy-rs) — the smoke test confirmed the mean and its SE are bitwise-equal across repeated runs, so results are reproducible without setting a seed.

### The `svy.Sample` constructor

Observed signature:

```python
svy.Sample(data, design=None, *, catalog=None, questionnaire=None)
```

- `data` is positional (a Polars DataFrame). `svy.Sample(df, design=design)` works.
- **`design` is optional.** A design-less `Sample` is a valid container — useful purely for I/O (writing survey files, see the svy-io section) even when no design has been attached.

---

## Creating a Taylor Linearization Design

Taylor linearization (also called the "ultimate cluster" method) is the default and most common approach. It requires knowing the stratification and primary sampling unit (PSU) variables.

### Minimal Design (Weight Only)

```python
import svy

# Simple random sample with unequal weights
design = svy.Design(wgt="weight")
sample = svy.Sample(data, design=design)
```

This assumes no stratification and no clustering — only unequal selection probabilities. Variance is computed using a with-replacement approximation.

### Stratified Design (No Clustering)

```python
design = svy.Design(stratum="region", wgt="weight")
sample = svy.Sample(data, design=design)
```

### Clustered Design (No Stratification)

```python
design = svy.Design(psu="school_id", wgt="weight")
sample = svy.Sample(data, design=design)
```

### Full Complex Design (Stratified Clustered)

```python
# Complex multi-stage design — most federal surveys
design = svy.Design(
    stratum="sdmvstra",
    psu="sdmvpsu",
    wgt="wtmec2yr",
)
sample = svy.Sample(data, design=design)
```

### Two-Stage Clustering (PSU + SSU)

svy exposes a second-stage cluster parameter, `ssu` (secondary sampling unit):

```python
design = svy.Design(stratum="stratum", psu="psu", ssu="ssu", wgt="weight")
sample = svy.Sample(data, design=design)
```

### `svy.Design` Parameters (observed signature)

```python
svy.Design(row_index=None, stratum=None, wgt=None, prob=None, hit=None,
           mos=None, psu=None, ssu=None, pop_size=None, wr=False, rep_wgts=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `wgt` | `str` | Survey weight column name. Effectively required for estimation. |
| `stratum` | `str` or `tuple[str, ...]` | Stratification variable(s). Optional. Pass a tuple for nested strata. |
| `psu` | `str` | Primary sampling unit (cluster) variable. Optional. |
| `ssu` | `str` | Secondary sampling unit (second-stage cluster). Optional. |
| `pop_size` | `str` or `svy.PopSize` | Finite population correction. See FPC section. Optional. **Functional in 0.19.0.** |
| `prob` | `str` | Selection-probability column (alternative to a weight). Optional. |
| `rep_wgts` | `svy.RepWeights` | Pre-existing replicate-weight specification. See below. Optional. |
| `hit` | `str` | Hits/measure-of-selection column (multi-phase / PPS designs). Optional. **[not smoke-tested at 0.19.0]** |
| `mos` | `str` | Measure-of-size column (PPS designs). Optional. **[not smoke-tested at 0.19.0]** |
| `wr` | `bool` | With-replacement flag (default `False`). **[not smoke-tested at 0.19.0]** |
| `row_index` | `str` | Explicit row-index column. Optional; svy adds `svy_row_index` internally. **[not smoke-tested at 0.19.0]** |

> **Note:** There is **no `fpc=` parameter** — a `svy.Design(..., fpc=...)` call raises `TypeError: unexpected keyword argument 'fpc'`. FPC is specified through `pop_size=` (see next section). This is the single most common breakage when porting 0.13.0-era or docs-derived code.

### Multiple Stratification Variables

Some designs have nested stratification (e.g., region within urban/rural):

```python
design = svy.Design(
    stratum=("region_id", "urban_rural"),
    psu="psu_id",
    wgt="final_weight",
)
sample = svy.Sample(data, design=design)
```

---

## Finite Population Correction (FPC)

The FPC adjusts variance estimates when a substantial fraction of the population is sampled (typically > 5-10%). Without FPC, variance estimates are conservative (too large). **FPC works in 0.19.0** — the 0.13.0 `TypeError` bug is fixed.

### Single-Stage FPC (column of population sizes)

Pass `pop_size=` a column name giving the stratum (or PSU) population size. This form is smoke-tested:

```python
# FPC via a population-size column — Design built + mean computed cleanly
design = svy.Design(
    stratum="stratum",
    psu="psu",
    wgt="weight",
    pop_size="fpc_pop",     # column containing the population size
)
sample = svy.Sample(data, design=design)
```

### Two-Stage FPC (svy.PopSize)

For a two-stage FPC (population sizes at both the PSU and SSU stages), pass a `svy.PopSize` object. Observed signature:

```python
svy.PopSize(psu, ssu=None)      # psu/ssu are column names holding stage population sizes
```

```python
design = svy.Design(
    stratum="stratum",
    psu="psu",
    ssu="ssu",
    wgt="weight",
    pop_size=svy.PopSize(psu="N_psu", ssu="N_ssu"),
)
```

> The single-column `pop_size="col"` form was exercised end-to-end by the smoke test (Design built, mean and SE computed). The `svy.PopSize(psu=, ssu=)` object form is signature-confirmed but **[not smoke-tested at 0.19.0]** — introspect the two-stage result before relying on the second-stage correction.

**When to apply FPC:**
- Sampling fraction > 5% of the population within strata
- Self-representing (certainty) strata where all units are selected
- Small population surveys (e.g., all schools in a small state)

**When to skip FPC:**
- Large national surveys sampling << 1% of the population (NHANES, CPS, etc.)
- When population size is unknown
- When a conservative variance estimate is acceptable

---

## Pre-Existing Replicate Weights

When the data provider supplies replicate weights (common for public-use files from NCES, Census, BLS), use them instead of Taylor linearization. Replicate weights encode the design information and often provide more accurate variance estimates for complex statistics.

The pattern is: build a `svy.RepWeights` describing the existing columns, then pass it to `svy.Design(rep_wgts=...)`. The `Design(rep_wgts=)` parameter is confirmed present; the observed metadata object looks like:

```
RepWeights(method=Bootstrap, prefix='weight', n_reps=20, df=19.0)
```

so `RepWeights` carries `method`, `prefix`, `n_reps`, and `df`.

```python
# Bootstrap replicate weights already in the data (columns pwgtp1 .. pwgtp80)
rep_wgts = svy.RepWeights(
    prefix="pwgtp",        # matches pwgtp1, pwgtp2, ...
    n_reps=80,             # number of replicate weight columns
    method="Bootstrap",    # replication method (see caveat below)
)
design = svy.Design(wgt="pwgtp", rep_wgts=rep_wgts)
sample = svy.Sample(data, design=design)
```

> **[not smoke-tested at 0.19.0]** The smoke test exercised replicate *creation* from a Taylor design (next section), not construction of a `RepWeights` object from pre-existing columns. Before using this path, introspect `inspect.signature(svy.RepWeights)` and confirm how the method is specified — the observed metadata renders the method as `Bootstrap` (an enum-like member), and earlier docs described a `svy.EstimationMethod` enum (`TAYLOR`, `BRR`, `BOOTSTRAP`, `JACKKNIFE`, `SDR`) and a `fay_coef` argument for Fay-BRR. Verify the enum-vs-string convention and the Fay parameter name against the installed build rather than assuming.

### When to Use Replicate Weights vs. Taylor

| Scenario | Recommended Method |
|----------|-------------------|
| Replicate weights provided in the data | Use replicate weights |
| Only design variables available (strata, PSU) | Use Taylor linearization |
| Estimating medians or other nonsmooth statistics | Prefer replicate weights (more robust) |
| Complex derived statistics (ratios of subgroup estimates) | Prefer replicate weights |
| Want to match published estimates exactly | Use whichever method the publisher used |
| No design information at all | Cannot do design-based inference — reconsider |

---

## Creating Replicate Weights From a Design

When you have a Taylor design and want replicate-based variance (for robustness, or to match a publisher), svy creates replicate weights through the `sample.weighting.create_*_wgts` methods. **This path is smoke-tested.**

### Observed behavior (bootstrap example)

```python
# Confirmed signature:
#   create_bs_wgts(n_reps=500, *, rep_prefix=None, drop_nulls=False, rstate=None)
bs = sample.weighting.create_bs_wgts(n_reps=500, rstate=42)
```

Key observed facts:
- The method **returns a NEW `Sample`** (not a DataFrame, not the same object).
- The returned sample's `.data` gains a `svy_row_index` column plus one column per replicate, named `weight1 .. weightN` (the default prefix is the base weight column's name — here `weight`). Override with `rep_prefix=`.
- Replicate metadata is exposed on `bs.rep_wgts` (a `RepWeights` object with `.n_reps`, `.method`, `.prefix`, `.df`).
- Estimate on the returned sample with the replication variance method: `bs.estimation.mean("income", method="replication")`.
- Replication variance is deterministic across runs with the same `rstate` (confirmed bitwise-equal).

```python
# Full pattern
bs = sample.weighting.create_bs_wgts(n_reps=200, rstate=42)
print(bs.rep_wgts)                       # RepWeights(method=Bootstrap, prefix='weight', n_reps=200, ...)
res = bs.estimation.mean("income", method="replication").to_polars()
```

### Available creators

| Method | Purpose | Notes |
|--------|---------|-------|
| `create_bs_wgts(n_reps=500, *, rep_prefix=None, drop_nulls=False, rstate=None)` | Bootstrap replicate weights | Signature confirmed; return shape smoke-tested |
| `create_jk_wgts(...)` | Jackknife replicate weights (JKn / paired JK2 via `paired=`) | `create_jk_wgts()` no-arg call confirmed to return a Sample; `paired=` documented, **[not smoke-tested]** |
| `create_brr_wgts(...)` | BRR (and Fay-BRR) replicate weights | Present; signature **[not smoke-tested]** |
| `create_sdr_wgts(...)` | Successive-difference replication (ACS-style) | Present; signature **[not smoke-tested]** |
| `create_variance_strata(...)` | Build pseudo variance strata for designs lacking them | Present; signature **[not smoke-tested]** |

Introspect the exact signatures of the non-bootstrap creators before relying on their keyword arguments.

---

## Weight Types and Selection

### Common Weight Types in Federal Surveys

| Weight Type | Purpose | When to Use |
|-------------|---------|-------------|
| **Base weight** | Inverse of selection probability (1/pi) | Rarely used directly; starting point for adjustments |
| **Nonresponse-adjusted weight** | Base weight adjusted for unit nonresponse | When nonresponse adjustment is the final step |
| **Post-stratified / calibrated weight** | Adjusted to match population totals | Most analyses — this is usually the "final" weight |
| **Replicate weight** | Perturbed version of the final weight for variance estimation | Used alongside the main weight for replicate variance |
| **Subsample weight** | Weight for a subset who completed additional measures | When analyzing variables only collected from the subsample |

### Choosing the Right Weight

1. **Identify the analysis population**: Which respondents have non-missing data for your variables?
2. **Match the weight to the population**: Use the weight designed for that subset
3. **Consult the survey documentation**: Weight variable names and usage instructions are survey-specific

**Example — NHANES weight selection:**
- Interview data only: use `wtint2yr` (interview weight)
- Examination data: use `wtmec2yr` (MEC exam weight)
- Fasting subsample: use `wtsaf2yr` (fasting subsample weight)
- Diet recall (day 1): use `wtdrd1` (dietary day 1 weight)

Using the wrong weight produces biased estimates. The weight must correspond to the most restrictive component of data collection used in your analysis.

---

## The Weighting Namespace: Calibration and Adjustment

svy exposes weight-adjustment methods on the `sample.weighting` accessor. The full observed namespace is: `adjust`, `calibrate`, `poststratify`, `rake`, `normalize`, `trim`, plus the replicate creators above (`create_bs_wgts`, `create_jk_wgts`, `create_brr_wgts`, `create_sdr_wgts`, `create_variance_strata`). Method **names** are confirmed present; the calibration signatures below reflect the documented API and are **[not smoke-tested at 0.19.0]** — introspect before relying on exact keyword arguments.

### Post-Stratification

Post-stratification adjusts weights so that weighted sample totals match known population totals (e.g., Census counts by age/sex/race).

```python
sample = sample.weighting.poststratify(
    controls={"18-34": 50_000_000, "35-64": 60_000_000, "65+": 40_000_000},
    by="age_group",
)
```

### Raking (Iterative Proportional Fitting)

```python
sample = sample.weighting.rake(
    controls={
        "gender": {"Male": 160_000_000, "Female": 165_000_000},
        "age_group": {"18-34": 50_000_000, "35-64": 60_000_000, "65+": 40_000_000},
    }
)
```

### GREG (Generalized Regression Estimator)

```python
sample = sample.weighting.calibrate(
    controls={svy.Cat("gender"): {"Male": 160_000_000, "Female": 165_000_000}}
)
```

### Trimming and Normalization

`sample.weighting.trim(...)` caps extreme weights (optionally redistributing the trimmed mass); `sample.weighting.normalize(...)` rescales weights (e.g., to sum to the sample size). Introspect their signatures for the exact bound/redistribution arguments.

**Note:** Calibration is typically performed by the data producer before public release. Analysts working with public-use files usually do not need to calibrate — the provided weights already incorporate these adjustments. Only calibrate if you are working with raw sampling weights or need to adjust for a specific target population.

---

## Singleton PSU Handling

A "singleton PSU" (or "lonely PSU") occurs when a stratum contains only one primary sampling unit. This makes within-stratum variance undefined, because variance estimation requires at least two PSUs per stratum.

### Common Causes

- Rare subpopulations where domain estimation leaves some strata with only one PSU
- Data subsetting that removes PSUs from strata
- Design strata that genuinely have only one PSU (certainty selections)

> **[not re-verified at 0.19.0]** The 0.13.0 skill documented a `sample.singleton` accessor with methods `exists()`, `summary()`, `certainty()`, `center()`, `combine()`, `collapse()`, `pool()`, `scale()`, `skip()` and a `SingletonHandling` enum. This accessor was not exercised by the 0.19.0 smoke test and was not visible in the (truncated) attribute listing captured during introspection. Before relying on it, confirm the accessor and its method names on the installed build (`[a for a in dir(sample) if "singl" in a.lower()]`). The methodological guidance below is version-independent.

**Best practice:** Centering at the grand mean (R's "adjust") or pooling neighboring strata is generally safest. Zeroing the variance contribution (treating a singleton as a certainty selection) is appropriate only when the stratum truly is a certainty selection. Always report how singleton PSUs were handled.

### Prevention

- Avoid domain estimation on very small subgroups
- If subsetting is necessary, consider collapsing strata before analysis
- Use replicate weights when available (the replication method handles singletons implicitly)

---

## Reading and Writing Survey Data Files (svy-io)

svy's file I/O lives in the bundled **svy-io** package, reached as `svy.io.*` (also mirrored as top-level `svy.read_stata`, `svy.write_stata`, etc.). Readers return a **bare `pl.DataFrame`**; writers take a **`Sample`**.

### Observed signatures (the important asymmetry)

```python
# READERS return a bare polars.DataFrame (NOT a (df, metadata) tuple)
svy.io.read_stata(path, *, columns=None, **kwargs) -> pl.DataFrame
svy.io.read_sas(path,   *, columns=None, **kwargs) -> pl.DataFrame
svy.io.read_spss(path,  *, columns=None, **kwargs) -> pl.DataFrame

# WRITERS take a Sample object (NOT a DataFrame) and return None
svy.io.write_stata(sample, path, **kwargs) -> None
```

```python
# Read a Stata file
data = svy.io.read_stata("nhanes_2017_2020.dta")   # -> pl.DataFrame
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)

# Write a Sample back out (design optional — a design-less Sample is a valid I/O container)
svy.io.write_stata(svy.Sample(data), "roundtrip.dta")
```

The smoke test round-tripped a 480-row frame through `write_stata(sample, path)` → `read_stata(path)` with the checksum preserved.

### Full svy.io surface (observed)

| Category | Functions |
|----------|-----------|
| Stata | `read_stata`, `write_stata`, `read_dta`, `write_dta`, `read_stata_with_labels`, `read_dta_with_labels` |
| SAS | `read_sas`, `write_sas`, `read_sas_with_labels` |
| SPSS | `read_spss`, `write_spss`, `read_sav`, `write_sav`, `read_spss_with_labels`, `read_sav_with_labels` |
| CSV / Parquet | `read_csv`, `write_csv`, `scan_csv`, `read_parquet`, `write_parquet`, `scan_parquet` |
| Sample constructors | `create_from_dta`, `create_from_stata`, `create_from_sas`, `create_from_sav`, `create_from_spss`, `create_from_csv`, `create_from_parquet` |

- The **`*_with_labels`** readers preserve value/variable labels as metadata alongside the frame.
- The **`create_from_*`** helpers read a file and return a `svy.Sample` in one step (e.g., `svy.create_from_dta(path, name=None) -> Sample`).
- A lower-level `svy_io` package is also importable directly (labelled-value helpers: `apply_value_labels`, `zap_labels`, `read_xpt`, `read_por`, etc.), but prefer the `svy.io.*` surface for normal use.

### Parquet in DAAF pipelines

In DAAF research pipelines, data is stored as parquet after initial conversion. Use `svy.io` for the initial read from the original survey format, then persist as parquet (`svy.io.write_parquet` or Polars' own `pl.write_parquet`) for subsequent stages:

```python
import polars as pl
data = pl.read_parquet("data/raw/survey_data.parquet")   # native Polars is fine
```

---

## Federal Survey Design Quick-Reference

A quick-reference table for setting up svy designs for commonly used federal surveys. **Always verify against the current survey documentation** — design variable names can change across survey cycles.

| Survey | Strata | PSU | Weight(s) | Variance Method | Notes |
|--------|--------|-----|-----------|-----------------|-------|
| **NHANES** | `sdmvstra` | `sdmvpsu` | `wtmec2yr`, `wtint2yr`, subsample weights | Taylor | Pseudo-strata/PSU for confidentiality; use appropriate weight for analysis domain |
| **ACS PUMS** | None (use replicate weights) | None | `pwgtp` (person) / `wgtp` (household) | Replicate: SDR (80 reps) | `pwgtp1`-`pwgtp80` replicate weights; no design variables in public-use file |
| **CPS ASEC** | `gestfips` + `gtco` (approx.) | Implicit | `marsupwt` (March supplement) | Replicate (160 reps) | Replicate weights preferred; design variables partially available |
| **MEPS** | `varstr` | `varpsu` | `perwt__f` (person), `famwt__f` (family) | Taylor | Panel design; weight suffix varies by year |
| **ECLS-K:2011** | Survey-specific strata var | Survey-specific PSU var | Multiple (round-specific) | Taylor or JKn | Consult documentation for variable names per round; NCES provides jackknife replicate weights |
| **BRFSS** | `_ststr` | `_psu` | `_llcpwt` (landline + cell) | Taylor | State-level stratification; combined landline/cell design post-2011 |
| **NHIS** | `strat_p` | `psu_p` | `wtfa_sa` (sample adult) | Taylor | Redesigned in 2019; variable names differ pre/post redesign |
| **NSDUH** | Provided | Provided | `analwt_c` | Taylor | Design variables vary by public-use file version |

### NHANES Example

```python
import svy
import polars as pl

data = pl.read_parquet("data/raw/nhanes_demo.parquet")

# INTENT: Standard NHANES complex design for MEC-examined participants
# REASONING: sdmvstra and sdmvpsu are masked design variables;
#   wtmec2yr is the 2-year MEC exam weight for exam-based analyses
# ASSUMES: All analysis variables were collected during the MEC examination
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)
```

### ACS PUMS Example (Replicate Weights)

```python
import svy
import polars as pl

data = pl.read_parquet("data/raw/acs_pums_2022.parquet")

# INTENT: ACS PUMS uses successive-difference replication (SDR)
# REASONING: No design variables in public-use file; must use replicate weights
# ASSUMES: Person-level analysis using person weight and person replicate weights
# NOTE: Confirm the RepWeights method specifier by introspection (see "Pre-Existing
#   Replicate Weights") — the SDR construction path was not smoke-tested at 0.19.0.
rep_wgts = svy.RepWeights(prefix="pwgtp", n_reps=80, method="SDR")
design = svy.Design(wgt="pwgtp", rep_wgts=rep_wgts)
sample = svy.Sample(data, design=design)
```

### MEPS Example

```python
import svy

data = svy.io.read_sas("h233.sas7bdat")   # -> pl.DataFrame

# INTENT: MEPS household component, full-year consolidated file
# REASONING: varstr/varpsu are the standard MEPS design variables
# ASSUMES: Person-level analysis for FY 2021
design = svy.Design(stratum="varstr", psu="varpsu", wgt="perwt21f")
sample = svy.Sample(data, design=design)
```

---

## Combining Survey Cycles

Some analyses require combining multiple cycles of a survey (e.g., NHANES 2017-2018 + 2019-2020) to increase sample size for rare subpopulations.

### Weight Adjustment

When combining N two-year cycles, divide the survey weight by N:

```python
import polars as pl

cycle1 = pl.read_parquet("data/raw/nhanes_2017_2018.parquet")
cycle2 = pl.read_parquet("data/raw/nhanes_2019_2020.parquet")
combined = pl.concat([cycle1, cycle2])

# INTENT: Adjust weights for combined 4-year analysis
# REASONING: NHANES analytic guidelines require dividing 2-year weights by
#   the number of cycles combined to produce correct population estimates
# ASSUMES: Both cycles use the same design structure and weight definitions
combined = combined.with_columns(
    (pl.col("wtmec2yr") / 2).alias("wtmec4yr")
)

design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec4yr")
sample = svy.Sample(combined, design=design)
```

### Important Caveats

- Only combine cycles with the same design structure
- Consult survey-specific guidelines for the correct weight adjustment
- For NHANES: the analytic guidelines at `wwwn.cdc.gov/nchs/nhanes/tutorials/` provide detailed instructions
- For ACS: combining 1-year and 5-year estimates requires separate methodology
- The variance structure may change across cycles — check for redesign years

---

## Polars Integration Notes

### svy Expects Polars DataFrames

`svy.Sample` expects a Polars DataFrame as the `data` argument. Data loaded via `svy.io` readers returns Polars DataFrames automatically.

### Converting from Other Formats

```python
import polars as pl

# From pandas
import pandas as pd
pd_df = pd.read_csv("survey.csv")
pl_df = pl.from_pandas(pd_df)

# From parquet (native Polars)
pl_df = pl.read_parquet("data.parquet")
```

### Column Type Requirements

- **Weight column**: Must be numeric (Float64 or Int64)
- **Strata column**: Can be string or integer; treated as categorical
- **PSU column**: Can be string or integer; treated as categorical
- **Analysis variables**: Numeric for estimation; string/categorical for proportions and grouping. **For GLM predictors, string/categorical columns must be wrapped in `svy.Cat()`** (see `regression.md`) — svy does not auto-detect them and a raw string predictor raises a strict-cast `ValueError`.

### Accessing the Underlying DataFrame

```python
sample.data   # Returns the Polars DataFrame
```

---

## Migration from samplics

svy replaces samplics with a fundamentally different API. Key migration points:

### Design Specification

```python
# samplics (OLD — archived)
from samplics.estimation import TaylorEstimator
estimator = TaylorEstimator("mean")
estimator.estimate(
    y=data["income"].to_numpy(),
    samp_weight=data["weight"].to_numpy(),
    stratum=data["stratum"].to_numpy(),
    psu=data["psu"].to_numpy(),
)

# svy (NEW)
import svy
design = svy.Design(stratum="stratum", psu="psu", wgt="weight")
sample = svy.Sample(data, design=design)
result = sample.estimation.mean("income")
```

### Key Differences

| Aspect | samplics | svy |
|--------|---------|-----|
| Data format | numpy arrays | Polars DataFrames |
| Design specification | Per-call parameters | Persistent Design + Sample objects |
| Estimation | `TaylorEstimator("mean").estimate(y=..., ...)` | `sample.estimation.mean("var")` |
| Replicate estimation | `ReplicateEstimator("mean").estimate(...)` | Same estimation API — design/method determines variance |
| Regression | `SurveyGLM(...)` | `sample.glm.fit(...)` |
| Tabulation | `Tabulation(...)` | `sample.estimation.prop(var, by=...)` |

### Why the Change Matters

samplics required passing design variables on every estimation call. svy's `Sample` object binds data and design once, then all estimation and regression methods automatically use the correct design. This reduces errors from inconsistent design specification across calls.
