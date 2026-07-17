# svy Estimation Reference

svy v0.19.0 — syntax and library guidance only. Signatures and result schemas below were
verified against the installed library (`/daaf/scripts/smoke_tests/smoke_svy_a.py`).
Constructs not exercised by the smoke test are flagged **[unverified at 0.19.0]**.

---

## Contents

1. [Prerequisites: Design and Sample Setup](#prerequisites-design-and-sample-setup)
2. [The Result Object and Its Schema](#the-result-object-and-its-schema)
3. [Population Means](#population-means)
4. [Batched Multi-Variable Estimation](#batched-multi-variable-estimation)
5. [Population Totals](#population-totals)
6. [Proportions](#proportions)
7. [Ratios](#ratios)
8. [Medians and Quantiles](#medians-and-quantiles)
9. [Domain / Subpopulation Estimation](#domain--subpopulation-estimation)
10. [Filtering with where=](#filtering-with-where)
11. [Cross-Tabulations and Hypothesis Tests](#cross-tabulations-and-hypothesis-tests)
12. [Design Effects (DEFF)](#design-effects-deff)
13. [Working with Polars DataFrames](#working-with-polars-dataframes)
14. [Common Patterns and Pitfalls](#common-patterns-and-pitfalls)

---

## Prerequisites: Design and Sample Setup

All estimation requires a `svy.Sample` object combining data with a design specification. See `design-weights.md` for full design setup. Brief recap:

```python
import svy

# --- Taylor linearization design (most common) ---
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)
```

For replicate weight designs, see `design-weights.md`. Once the `Sample` is created, estimation methods are identical regardless of the variance estimation method — the design object determines how SEs are computed. To force replication variance on a sample carrying replicate weights, pass `method="replication"` (e.g., `sample.estimation.mean("income", method="replication")`).

---

## The Result Object and Its Schema

Every scalar estimation call returns an **`Estimate`** object. Call `.to_polars()` to get a Polars DataFrame. The observed column schema is:

```
['est', 'se', 'lci', 'uci', 'cv']
```

| Column | Meaning |
|--------|---------|
| `est` | Point estimate |
| `se` | Design-based standard error |
| `lci` / `uci` | Lower / upper confidence-interval bound (95% by default; set `alpha=`) |
| `cv` | Coefficient of variation (`se / est`) |

```python
res = sample.estimation.mean("income")
df = res.to_polars()
point = df.item(0, "est")     # extract the estimate
se    = df.item(0, "se")
```

When a call groups (`by=`) or estimates a categorical proportion, the grouping/category column is **prepended** to this schema (e.g., `['stratum', 'est', 'se', 'lci', 'uci', 'cv']`), with one row per group/level. There is no `estimate`/`stderr` column — code that looks for those names (0.13.0-era) will not find the estimate.

---

## Population Means

### Basic Mean

```python
# Population mean with design-based SE
result = sample.estimation.mean("bmxbmi")
print(result.to_polars())    # ['est','se','lci','uci','cv']
```

### Full `mean()` Signature (observed)

```python
sample.estimation.mean(
    y, *,
    by=None,               # domain grouping column(s)
    where=None,            # polars expression filter (see "Filtering with where=")
    method=None,           # "replication" to force replicate variance
    deff=False,            # request the design effect
    fay_coef=None,         # Fay coefficient for BRR replication
    as_factor=False,       # treat y as a factor
    variance_center=None,  # "rep_mean" or "estimate" for replicate centering
    alpha=0.05,            # 1 - confidence level (0.05 -> 95% CI)
    drop_nulls=True,       # drop rows null in y (default)
)
```

`total`, `prop`, `ratio`, and `median` are used with the same core parameters (`by=`, `where=`, `alpha=`, `drop_nulls=`) — these four were confirmed in use (`by=`/`where=` were smoke-tested on these methods), but each method's full signature was not individually introspected, so verify additional parameters against the installed build. `prop` additionally takes `ci_method=` (below).

### Handling Missing Data

```python
result = sample.estimation.mean("bmxbmi", drop_nulls=True)
```

svy uses Polars null handling. Rows with null values in the analysis variable are excluded from the estimate by default. **Critical:** Dropping nulls changes the effective domain of estimation. If missingness is non-random (which it usually is in surveys), acknowledge this limitation in your analysis. Document it with an `# ASSUMES:` comment in research scripts.

---

## Batched Multi-Variable Estimation

**New in 0.19.0:** `mean`, `total`, `prop`, `ratio`, and `median` accept a **list** of variables and estimate all of them in one call. The return is a **`list[Estimate]`** — one element per requested variable, **not** a single stacked frame. Iterate the list.

```python
# Batched means -> list of 2 Estimate objects (one per variable)
results = sample.estimation.mean(["income", "age"])
assert isinstance(results, list) and len(results) == 2
for var, est in zip(["income", "age"], results):
    row = est.to_polars()
    print(f"{var}: {row.item(0, 'est'):.2f} (se {row.item(0, 'se'):.2f})")

# Batched ratios: several numerators over one denominator -> list, one per numerator
ratios = sample.estimation.ratio(["income", "visit_count"], "age")   # list len 2

# Batched proportions -> list, one Estimate per variable
props = sample.estimation.prop(["employed", "gender"])                # list len 2
```

> Do **not** expect a `variable` column identifying which frame is which — the correspondence is positional (element `i` is the `i`-th variable you passed). A single-variable call (`mean("income")`) still returns a single `Estimate`, not a length-1 list.

---

## Population Totals

```python
result = sample.estimation.total("income")
print(result.to_polars())    # ['est','se','lci','uci','cv']
```

Totals estimate the sum of a variable across the entire target population, not just the sample. The SE reflects the uncertainty of this population-level estimate.

### When to Use Totals vs. Means vs. Proportions

- **Totals** for aggregate quantities: total enrollment, total expenditure, total population count
- **Means** for per-unit averages: mean income, mean BMI, mean test score
- **Proportions** for binary/categorical shares: percent employed, percent below poverty

---

## Proportions

### Basic Proportion

```python
result = sample.estimation.prop("employed")
print(result.to_polars())
```

For a categorical variable, svy returns one row per level (the level column is prepended to the `est/se/lci/uci/cv` schema), each with its design-based SE and CI.

### Confidence-Interval Method

`prop()` takes a `ci_method=` argument controlling the interval construction (observed default `"logit"`):

```python
sample.estimation.prop("employed", ci_method="wilson")
```

Observed options: `"logit"` (default), `"wilson"`, `"beta"`, `"korn-graubard"`. Use `"korn-graubard"` or `"beta"` for exact intervals on small domains or proportions near 0/1, where the logit interval degrades.

---

## Ratios

### Basic Ratio

```python
# y is numerator, x is denominator
result = sample.estimation.ratio(y="total_expenditure", x="household_size")
print(result.to_polars())
```

Ratio estimation is used when the quantity of interest is a ratio of two survey variables (e.g., per-capita expenditure). The SE accounts for the covariance between numerator and denominator.

### Ratio vs. Mean of a Derived Variable

**Do not** compute `expenditure / household_size` as a new column and then estimate its mean. This gives incorrect SEs because it ignores the covariance structure. Use `estimation.ratio()` for proper variance estimation of ratios.

```python
# WRONG: pre-computing the ratio then estimating the mean
# data = data.with_columns((pl.col("expenditure") / pl.col("hh_size")).alias("per_capita"))
# sample.estimation.mean("per_capita")  # <-- incorrect SEs

# CORRECT: use ratio estimation
sample.estimation.ratio(y="expenditure", x="hh_size")  # <-- correct SEs
```

---

## Medians and Quantiles

```python
result = sample.estimation.median("income")
print(result.to_polars())    # ['est','se','lci','uci','cv']
```

Median estimation for survey data uses weighted quantile computation with linearization-based or replicate-weight-based variance estimation. SEs for medians are typically larger than for means, and medians are a case where replicate weights are often preferred over Taylor.

---

## Domain / Subpopulation Estimation

### The `by` Parameter

Domain estimation computes statistics for subgroups of the population while preserving the full survey design structure. The result has one row per group, with the group column prepended to the standard schema.

```python
result = sample.estimation.mean("bmxbmi", by="riagendr")
print(result.to_polars())    # ['riagendr','est','se','lci','uci','cv'], one row per group
```

> **Domain estimation is cross-validated against R (2026-07-15).** Domain means and SEs match R `svyby(..., svymean)` to machine precision (≤7e-16 rel), and domain confidence intervals use the **t multiplier on the full design df** — matching R's t-based CIs exactly. (Note: R's `confint.svyby` *defaults* to a normal z multiplier; svy's t-based choice is the more defensible one, not a discrepancy. Evidence: `/daaf/scripts/scratch/xval_svy_r_05_compare.py`.)

```python
# Proportions by region
result = sample.estimation.prop("employed", by="region")
```

### Why Not Pre-Filter?

**Never pre-filter the data for domain estimation.** Pre-filtering removes observations needed for correct variance estimation.

```python
# WRONG: filtering before estimation
# females_only = data.filter(pl.col("gender") == "Female")
# female_sample = svy.Sample(females_only, design=design)
# female_sample.estimation.mean("income")  # <-- WRONG SEs

# CORRECT: use domain estimation
sample.estimation.mean("income", by="gender")  # <-- correct SEs for each gender
```

Pre-filtering discards PSUs and strata from the design, which can:
1. Produce incorrect variance estimates (too small or too large)
2. Create singleton PSU problems (strata with only one PSU after filtering)
3. Change the degrees of freedom for inference

### Multiple Grouping Variables

```python
result = sample.estimation.mean("income", by=("gender", "education"))
```

---

## Filtering with where=

The `where=` parameter restricts an estimate to a subpopulation **without** breaking the design (the correct way to estimate on a subset). It requires a **polars expression** — a string predicate raises `TypeError: Unsupported expression type: 'str'`.

```python
import polars as pl

# CORRECT: polars expression
sample.estimation.mean("income", where=pl.col("gender") == "Male")

# WRONG: string predicate -> TypeError
# sample.estimation.mean("income", where="gender == 'Male'")
```

`where=` and `by=` may reference the **same** column (fixed in 0.19.0, issue #9) — e.g., estimate stratum-domain means restricted to the first three strata:

```python
sample.estimation.mean("income", by="stratum", where=pl.col("stratum") <= 3)
# -> 3 domain rows (strata 1-3)
```

`where=` is the design-safe equivalent of subsetting: prefer it over building a filtered `Sample`.

---

## Cross-Tabulations and Hypothesis Tests

**`tabulate()` verified against R at 0.19.0 (2026-07-15).** `sample.categorical` is a `Categorical` object exposing exactly three public methods — `tabulate()`, `ranktest()`, and `ttest()`. There is **no** `chisq`/`crosstab`/`table` method (those names raise `AttributeError`). Of the three, `tabulate()` is cross-validated to machine precision against R; `ranktest()`/`ttest()` are signature-introspected but **not** yet cross-validated — spot-check those against R (`svyranktest`, `svyttest`) before publishing.

### Design-Based Cross-Tabulation with `tabulate()` (verified)

Observed signature: `tabulate(rowvar, colvar=None, *, units='proportion'|'percent'|'count', count_total=None, alpha=0.05, drop_nulls=False, use_labels=None) -> Table`.

```python
tab = sample.categorical.tabulate(
    "employment_status",           # rowvar (positional)
    "education_level",             # colvar (positional; omit for a one-way table)
    units="proportion",            # "proportion" | "percent" | "count"
    alpha=0.05,
)
cells = tab.to_polars()
# schema: ['employment_status','education_level','est','se','lci','uci','table_type','alpha']
```

Cell proportions and SEs match R `svymean`/`svytable` to machine precision (≤5e-16 rel). The design-based independence test lives on **`Table.stats`**, populated **only for two-way** tables (`.stats is None` for a one-way table):

```python
tab.stats
# TableStats(chisq=ChiSquare(df=1, value=11.327947, p_value=0.0026900),
#            f=FDist(df_num=1.0, df_den=20.0, value=9.006655, p_value=0.0070583))
```

- `chisq` = Rao-Scott–adjusted Pearson X² (matches R `svychisq(..., statistic="Chisq")`).
- `f` = Rao-Scott **F**, which is `svychisq`'s **default** statistic (matches R `svychisq(..., statistic="F")`), with denominator df = # PSUs − # strata.

Both statistics and their p-values are verified equal to R to machine precision (≤3e-15 rel). Evidence: `/daaf/scripts/scratch/xval_svy_r_03_py_svy.py`, `xval_svy_r_04_r_survey.R`, `xval_svy_r_05_compare.py`. *Scope: verified on one synthetic 2×2 design (24 PSUs); multi-level categorical predictors were not cross-validated.*

### Cell Estimates via `prop()` with `by=`

An alternative that yields only cell proportions and SEs (no formal test) uses `prop()` with `by=`:

```python
# Estimated population proportion of employment_status within each education level
result = sample.estimation.prop("employment_status", by="education_level")
```

This is equivalent to R's `svyby(~var, ~by_var, design, svymean)`. Use `tabulate()` when you need the design-based independence test (Rao-Scott χ²/F); use `prop(..., by=)` when you only need cell estimates and SEs.

### `ranktest()` and `ttest()` (introspected, not yet cross-validated)

```python
# Signatures introspected on the installed build; NOT cross-validated against R — spot-check first
sample.categorical.ranktest(y, group=..., method="kruskal-wallis")  # "kruskal-wallis"|"vander-waerden"|"median"
sample.categorical.ttest(y, mean_h0=0, group=None, y_pair=None, by=None, where=None)
```

Survey-weighted tests differ from unweighted tests: they use the survey weights in the point estimate, the design-based variance (stratification + clustering), and design-based degrees of freedom (roughly # PSUs − # strata, typically far smaller than n − 1), producing wider intervals under clustering. Cross-validate `ranktest`/`ttest` against R (`svyranktest`, `svyttest`) before publishing results that lean on them.

---

## Design Effects (DEFF)

The design effect (DEFF) measures how much the variance of an estimate is inflated (or deflated) by the complex design compared to a simple random sample of the same size.

```
DEFF = Var_complex / Var_SRS
```

- **DEFF = 1.0**: The complex design is as efficient as SRS
- **DEFF > 1.0**: The complex design increases variance (common with clustered designs)
- **DEFF < 1.0**: The complex design decreases variance (common with stratified designs)
- **Typical range**: 1.5 to 5.0 for clustered household surveys

Request the design effect by passing `deff=True` to an estimation call (e.g., `sample.estimation.mean("bmxbmi", deff=True)`). The `Sample` object also exposes a `deff_w` attribute for the weighting design effect.

### Effective Sample Size

```
n_eff = n / DEFF
```

A survey of 10,000 respondents with DEFF = 4.0 has the statistical precision of an SRS of only 2,500. Always consider the effective sample size when evaluating whether a survey has adequate power for a particular analysis.

---

## Working with Polars DataFrames

svy uses Polars DataFrames natively. Data loaded via `svy.io` readers returns Polars DataFrames. If you have data in other formats:

### From Parquet (Common in DAAF Pipelines)

```python
import polars as pl
import svy

data = pl.read_parquet("data/raw/nhanes_demo.parquet")
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)
```

### From Pandas

```python
import pandas as pd
import polars as pl

data = pl.from_pandas(pd.read_csv("survey_data.csv"))
```

### Data Wrangling Within svy

> **[unverified at 0.19.0]** The `wrangling` accessor (`clean_names`, `recode`, `categorize`, `mutate`, etc.) and the `svy.core.expr.col` helper documented for 0.13.0 were not exercised or confirmed present in the 0.19.0 verification pass. For any non-trivial data preparation, do the work in **Polars directly** (a fully supported path) before constructing the `Sample`, rather than relying on the wrangling accessor:

```python
import polars as pl
data = data.with_columns(
    (pl.col("age") ** 2).alias("age_sq"),
)
sample = svy.Sample(data, design=design)
```

If you do want the wrangling accessor, confirm it first: `[m for m in dir(sample) if "wrangl" in m.lower()]`.

---

## Common Patterns and Pitfalls

### Pattern: Complete Estimation Workflow

```python
import svy
import polars as pl

# --- Config ---
DATA_PATH = "data/raw/nhanes_demo.parquet"

# --- Load ---
data = pl.read_parquet(DATA_PATH)

# --- Design ---
# INTENT: NHANES uses a complex multi-stage stratified cluster design
# REASONING: sdmvstra = pseudo-strata, sdmvpsu = pseudo-PSU, wtmec2yr = 2-year MEC exam weight
# ASSUMES: Analysis population is the MEC-examined subsample
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")
sample = svy.Sample(data, design=design)

# --- Estimate ---
mean_bmi = sample.estimation.mean("bmxbmi").to_polars()
print(mean_bmi)                                   # ['est','se','lci','uci','cv']

mean_bmi_by_gender = sample.estimation.mean("bmxbmi", by="riagendr").to_polars()
print(mean_bmi_by_gender)                          # one row per gender

prop_obese = sample.estimation.prop("obese_flag").to_polars()
print(prop_obese)

# --- Validate ---
print(f"Sample size: {data.shape[0]}")
assert data.shape[0] > 0, "No data loaded"
assert mean_bmi.item(0, "se") > 0, "SE must be positive/finite"
```

### Pitfall: Using Unweighted Statistics

Never use `pl.col("var").mean()` or pandas `.mean()` on survey data. Unweighted statistics are biased for the target population and do not have correct standard errors.

### Pitfall: Ignoring Weight Variable Selection

Surveys often provide multiple weight variables for different analysis populations (e.g., NHANES has `wtint2yr` for interview data and `wtmec2yr` for examination data). Using the wrong weight produces biased estimates. Always consult the survey documentation to select the appropriate weight.

### Pitfall: Expecting a Stacked Frame from Batched Calls

A batched call (`mean(["a", "b"])`) returns a `list[Estimate]`, not one frame. Iterate the list; the correspondence to your input variables is positional.

### Pitfall: Passing a String to where=

`where=` requires a polars expression (`pl.col(...)`). A string predicate raises `TypeError`. This is the design-safe way to subset — do not build a filtered `Sample` for domain estimates.

### Pitfall: Treating Survey SEs as Cluster-Robust SEs

Survey-weighted SEs and cluster-robust SEs (e.g., from pyfixest or statsmodels with `cov_type="cluster"`) are **not the same thing**:
- Survey SEs account for stratification, clustering, **and** unequal probability of selection
- Cluster-robust SEs only account for within-cluster correlation
- Survey SEs use design-based degrees of freedom; cluster-robust SEs use large-sample approximations

Use svy when you have a complex survey with known design variables. Use cluster-robust SEs when you have non-survey data with clustered observations.
