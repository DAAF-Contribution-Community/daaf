# Common Gotchas and Troubleshooting

## Contents

- [Cumulative Breaking Changes (0.40 → 0.60)](#cumulative-breaking-changes-040--060)
- [feglm Now Supports Fixed Effects](#feglm-now-supports-fixed-effects)
- [numba Optional; Rust Demeaner Default](#numba-optional-rust-demeaner-default)
- [Formula Parsing](#formula-parsing)
- [CRV3 Memory Usage](#crv3-memory-usage)
- [Convergence in fepois](#convergence-in-fepois)
- [Singleton Fixed Effects](#singleton-fixed-effects)
- [lpdid Returns a DataFrame](#lpdid-returns-a-dataframe)
- [HC2/HC3 Restrictions](#hc2hc3-restrictions)
- [fixest (R) vs pyfixest Differences](#fixest-r-vs-pyfixest-differences)
- [Matching Stata Results](#matching-stata-results)

## Cumulative Breaking Changes (0.40 → 0.60)

DAAF ships pyfixest 0.60.0. The behavior-changing releases between the old 0.40
target and now are 0.40.0 (fixest-0.13 alignment), 0.50.0 (maketables + FE-GLMs),
and 0.60.0 (Rust demeaner default, numba optional, typed backend API). The items
below **silently change results** or break old code. (There are no 0.41–0.49
releases.)

### Default Standard Errors Changed (0.40)

**Before 0.40:** Default SE was cluster-robust by the first fixed effect variable.
**Since 0.40:** Default SE is `"iid"`.

```python
# Old behavior: fit.vcov was auto-set to {"CRV1": "f1"}
# New behavior: fit.vcov is "iid"

# If you want the old behavior, specify explicitly:
fit = pf.feols("Y ~ X | f1", data=df, vcov={"CRV1": "f1"})
```

**Impact:** Code that relied on the old default will produce **different standard errors, t-statistics, and p-values** without any error or warning. Always specify `vcov` explicitly to avoid ambiguity.

### ssc() Arguments Renamed (0.40)

| Old Name (pre-0.40) | New Name (0.40+) |
|----------------------|-------------------|
| `adj` | `k_adj` |
| `fixef_k` | `k_fixef` |
| `cluster_adj` | `G_adj` |
| `cluster_df` | `G_df` |

```python
# Old argument NAMES still work but raise a DeprecationWarning (verified live on 0.60):
pf.ssc(adj=True, cluster_adj=True, cluster_df="min")   # DeprecationWarning x3

# New (preferred)
pf.ssc(k_adj=True, k_fixef="nonnested", G_adj=True)
```

Note: the option *value* `"nested"` was renamed to `"nonnested"`. Unlike the
argument names, the old value is **not** back-compatible — `pf.ssc(k_fixef="nested")`
raises `TypeError: k_fixef must be 'none', 'full', or 'nonnested'` (verified live).
The live `ssc()` default for `k_fixef` is `"nonnested"`.

### Singleton Removal Default Changed (0.40)

**Before 0.40:** `fixef_rm="none"` — singletons kept by default.
**Since 0.40:** `fixef_rm="singleton"` — singletons dropped by default.

Singleton fixed effects are groups with only one observation. Keeping them can inflate degrees of freedom and produce misleading inference.

```python
# To preserve old behavior (not recommended):
fit = pf.feols("Y ~ X | fe", data=df, fixef_rm="none")
```

### Multicollinearity Tolerance (0.40)

Default `collin_tol` changed from 1e-10 to 1e-09. This may cause some near-collinear variables to be dropped that were previously kept.

### etable Moved to maketables (0.50)

`etable()`/`dtable()` render through the `maketables` backend since 0.50 (pyfixest
no longer depends on `great_tables` directly — maketables wraps it for HTML/GT
output). The **public API is unchanged**, and on
0.60.0 the default and `type="gt"` still return a `great_tables.gt.GT` object
(rendered via maketables, verified live). One behavior trap: significance stars are
now governed by the `coef_fmt` string's `*` token. Stars are on by default, but a
custom `coef_fmt` that omits `*` drops them. See `tables-and-plots.md` § Output
Formats. (A stars-dropping regression here was fixed in 0.50.1.)

### Gelbach decompose() Return Type (0.40)

`fit.decompose()` returns a `GelbachDecomposition` object (was a `pd.DataFrame`),
the argument is `decomp_var` (was `param`), and it defaults to normalized effects.
See `advanced-inference.md` § Gelbach Decomposition.

### Typed Demeaner API; Loose Kwargs Deprecated (0.60)

The `demeaner_backend`, `fixef_tol`, and `fixef_maxiter` keyword arguments are
deprecated in favor of a typed `demeaner=pf.MapDemeaner(...)` / `pf.LsmrDemeaner(...)`
object. The old kwargs still work but raise a `DeprecationWarning` (verified live).
The `jax` MAP backend and the `cupy`/`scipy` LSMR *backends* are deprecated. See
`fixed-effects.md` § Backend Options.

## feglm Now Supports Fixed Effects

**This reverses earlier guidance.** Since 0.50, `feglm()` supports fixed-effects
demeaning for the `logit`, `probit`, and `gaussian` families. Verified live on
0.60.0:

```python
# All of these fit and return finite coefficients on 0.60.0:
pf.feglm("binary_Y ~ X1 | entity", data=df, family="logit")
pf.feglm("binary_Y ~ X1 | entity", data=df, family="probit")
pf.feglm("binary_Y ~ X1 | entity + year", data=df, family="logit")
```

Pyfixest before 0.50 raised `NotImplementedError` for `feglm()` with fixed effects,
and older skill guidance recommended the linear probability model (LPM) as a
workaround. That software limitation is gone.

**Remaining caveat (statistical, not a bug):** Nonlinear FE-GLMs with many *small*
FE groups can suffer incidental-parameters bias — a property of the estimator, not
of pyfixest. When FE groups are small, the LPM (`pf.feols("binary_Y ~ X | fe", ...)`,
coefficients as percentage-point changes) remains a useful robustness comparison.

## numba Optional; Rust Demeaner Default

Since 0.60 the **default FE demeaning backend is a compiled Rust extension** shipped
in the wheel — there is no numba JIT warm-up on the default path. **numba is now an
optional extra** (`pyfixest[numba]`); it is still used for `MapDemeaner(backend="numba")`
and the fast randomization-inference path (`ritest(..., choose_algorithm="fast")`).

**In the DAAF image:** numba is present transitively (via umap-learn/wildboottest;
the smoke test recorded numba 0.66.0), so the numba paths remain available here
without any action. You do not need to worry about numba installation in DAAF.

**First-call latency:** The old numba JIT warm-up on the first call no longer applies
to the default Rust path. If you explicitly select `MapDemeaner(backend="numba")`,
the first call still pays a one-time JIT compilation cost.

## Formula Parsing

pyfixest uses **formulaic** (not patsy) for formula parsing. This produces some syntax differences from statsmodels:

### Categorical Variables

```python
# pyfixest (formulaic)
"Y ~ C(state)"              # Basic categorical
"Y ~ i(state, ref='CA')"    # With reference level (preferred)

# statsmodels (patsy)
"Y ~ C(state, Treatment('CA'))"   # Reference via Treatment() — NOT supported in pyfixest
```

### Interactions

```python
# Both pyfixest and statsmodels
"Y ~ X1 * X2"      # Main effects + interaction
"Y ~ X1 : X2"      # Interaction only (no main effects)

# pyfixest-specific: i() for categorical interactions
"Y ~ i(group, X1, ref='control')"  # Group-specific slopes
```

### Common Parsing Errors

```python
# Error: variable names with spaces or special characters
# Fix: rename columns before estimation
df = df.rename(columns={"my variable": "my_variable"})

# Error: transformations not recognized
# formulaic supports: C(), np.log(), np.sqrt(), etc.
# Use numpy explicitly:
import numpy as np
"Y ~ np.log(X1) + X2"
```

## CRV3 Memory Usage

CRV3 (cluster jackknife) standard errors require storing a G × k matrix where G = number of clusters and k = number of parameters.

**Problem:** With many clusters and many parameters, this can exhaust memory.

```python
# Example: 1000 clusters × 500 parameters = large matrix
fit = pf.feols("Y ~ X1 + ... + X500 | fe", data=df)
fit.vcov({"CRV3": "cluster"})  # May run out of memory
```

**Fix:** Use CRV1 or wild bootstrap instead:

```python
fit.vcov({"CRV1": "cluster"})  # Much less memory
# Or for few clusters:
fit.wildboottest(param="X1", cluster="cluster", reps=9999)
```

## Convergence in fepois

### Symptoms

```python
# Warning: Maximum number of iterations reached
# Warning: Separation detected
```

### Causes and Fixes

**Slow convergence (many FE with sparse data):**

```python
fit = pf.fepois("Y ~ X | f1 + f2 + f3", data=df,
                iwls_maxiter=100,     # Increase from default 25
                iwls_tol=1e-06,       # Relax tolerance slightly
                )
```

**Separation (FE levels that perfectly predict zero):**

Some combinations of FE levels may have zero counts in all observations. These separated observations have infinite likelihood and must be removed. pyfixest can detect separation, but you may need to investigate which FE levels are problematic.

```python
# Check for zero-count FE groups
print(df.groupby(["f1", "f2"])["Y"].sum().value_counts())
```

## Singleton Fixed Effects

Singletons are FE groups with exactly one observation. Since v0.40, pyfixest drops them by default (`fixef_rm="singleton"`).

### Why Singletons Are Dropped

A singleton FE perfectly fits that observation's residual, contributing nothing to parameter estimation while consuming a degree of freedom. Keeping singletons inflates R² and can bias standard errors.

### Warning Messages

```python
# "X singleton observations removed"
# This is expected and correct behavior
```

If many singletons are removed, investigate whether your panel is very unbalanced or whether your FE specification is too fine-grained.

## lpdid Returns a DataFrame

Unlike `feols()`, `did2s()`, and `event_study()`, the `lpdid()` function returns a **pandas DataFrame**, not a `Feols` object:

```python
result = pf.lpdid(data=df, yname="Y", idname="entity",
                  tname="year", gname="treatment_year")

# result is a DataFrame with columns like:
# period, estimate, std_error, ci_lower, ci_upper, etc.

# This does NOT work:
# result.summary()     # AttributeError
# result.iplot()       # AttributeError
# pf.etable([result])  # TypeError
```

To visualize `lpdid()` results, use the returned DataFrame directly with matplotlib or plotnine.

## HC2/HC3 Restrictions

HC2 and HC3 standard errors are **not supported** with fixed effects or instrumental variables:

```python
# These will error:
fit = pf.feols("Y ~ X | fe", data=df)
fit.vcov("HC2")  # Error: HC2 not supported with FE

fit = pf.feols("Y ~ 1 | 0 | X ~ Z", data=df)
fit.vcov("HC3")  # Error: HC3 not supported with IV
```

**Why:** HC2 and HC3 require the hat matrix, which is expensive to compute when FE are absorbed via demeaning. Use HC1 ("hetero") or cluster-robust SEs instead.

## fixest (R) vs pyfixest Differences

| Feature | R fixest | pyfixest | Notes |
|---------|----------|----------|-------|
| Sun-Abraham | `sunab()` function | `event_study(estimator="saturated")` | Different API, same estimator |
| etable maturity | Full-featured | maketables backend (since 0.50) | R version still more polished for styling |
| feglm with FE | Supported | Supported (since 0.50) | Formerly a gap; now closed |
| Default SE (0.40+) | iid | iid | Aligned (fixest 0.13 / pyfixest 0.40) |
| Wild bootstrap | `fwildclusterboot` (R) | `wildboottest` (Python) | Separate packages |
| sunab aggregation | `aggregate()` | `fit.aggregate()` | Similar API |
| Formula syntax | Nearly identical | Nearly identical | `i()` and `|` notation shared |
| `etable()` type argument | `"latex"`, `"md"` | `"gt"` (default), `"df"`, `"md"`, `"tex"`, `"typst"`, `"html"` | Slight naming difference; `typst`/`html` added 0.60 |
| Multiple LHS | `c(Y1, Y2)` | `Y1 + Y2` | Syntax differs |

### Features in R fixest Not Yet in pyfixest

Check the pyfixest GitHub issues and changelog for current status:
- Some `etable()` customization options
- Some specialized FE features
- Certain post-estimation utilities

When a feature is missing in pyfixest, consider whether `statsmodels`, `linearmodels`, or manual implementation can fill the gap.

## Matching Stata Results

### Clustered Standard Errors

Stata and pyfixest use slightly different default small-sample corrections:

```python
# To match Stata's one-way clustering:
fit = pf.feols("Y ~ X | fe", data=df,
               vcov={"CRV1": "cluster"},
               ssc=pf.ssc(k_adj=True, k_fixef="none", G_adj=True))

# To match Stata's two-way clustering:
fit = pf.feols("Y ~ X | fe", data=df,
               vcov={"CRV1": "cluster1+cluster2"},
               ssc=pf.ssc(G_df="conventional"))
```

### HC3 Standard Errors

```python
# To match Stata's HC3 (robust, small):
fit_no_fe = pf.feols("Y ~ X", data=df)
fit_no_fe.vcov("HC3")
# Use ssc=pf.ssc(k_adj=False) if results don't match
```

### OLS Precision

With IID standard errors, pyfixest and R fixest match to ~10^-18 precision. Poisson matches to ~10^-8 to 10^-9. Differences beyond these thresholds suggest a specification mismatch, not a numerical issue.

## Polars DataFrame Input

pyfixest expects a **pandas DataFrame** as input. If your data pipeline uses Polars (as DAAF recommends), convert before passing to estimation functions:

```python
# Convert Polars → pandas before estimation
df = df_polars.to_pandas()
fit = pf.feols("Y ~ X1 | fe", data=df)
```

Passing a Polars DataFrame directly may raise a `TypeError` or produce unexpected behavior. Always convert explicitly. See `quickstart.md` for the full conversion pattern.

## Quick Diagnostic Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| TypeError with Polars DataFrame | pyfixest expects pandas | `df = df_polars.to_pandas()` |
| Different SEs from old code | 0.40 default SE change (now iid) | Specify `vcov` explicitly |
| Missing significance stars in etable | Custom `coef_fmt` without a `*` token (0.60) | Include `*` in `coef_fmt` (e.g. `"b* \n (se)"`) |
| `DeprecationWarning` on `demeaner_backend`/`fixef_tol` | Loose kwargs deprecated in 0.60 | Use `demeaner=pf.MapDemeaner(...)` |
| Very slow first call with `backend="numba"` | numba JIT compilation | Normal for numba; the default Rust demeaner has no JIT warm-up |
| Memory error with CRV3 | Too many clusters × params | Use CRV1 or wild bootstrap |
| Poisson won't converge | Separation or sparse data | Increase maxiter, check for separation |
| Many singletons dropped | Fine-grained FE | Expected; check FE specification |
| `AttributeError` on lpdid result | lpdid returns DataFrame | Use DataFrame methods, not Feols methods |
| HC2/HC3 error with FE | Not implemented with FE | Use HC1 or clustered SEs |

## References and Further Reading

- pyfixest changelog: https://pyfixest.org/changelog.html
- pyfixest GitHub issues: https://github.com/py-econometrics/pyfixest/issues
- Berge, L., Butts, K., and McDermott, G. (2026). "Fast and User-Friendly Econometrics Estimations: The R Package fixest." arXiv:2601.21749
- Cameron, A.C. and Miller, D.L. (2015). "A Practitioner's Guide to Cluster-Robust Inference." *Journal of Human Resources*, 50(2), 317-372
