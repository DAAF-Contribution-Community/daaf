---
name: svy
description: >-
  Complex survey analysis: strata/PSU/weights, variance estimation (Taylor, BRR, jackknife, bootstrap), survey GLM, domain analysis, calibration, survey data I/O (SAS, SPSS, Stata formats). Polars-native. Use for any complex-sample survey: NHANES, CPS, ACS PUMS, BRFSS, DHS, ECLS-K, MEPS-HC. CRITICAL: statsmodels WLS and pyfixest clustered SEs are NOT substitutes for proper survey-weighted analysis — they ignore stratification and unequal probability sampling. Non-survey regression: statsmodels/pyfixest. R equivalent: survey-r (use when execution language is R).
metadata:
  audience: research-coders
  domain: python-library
  library-version: "0.19.0"
  skill-last-updated: "2026-07-15"
---

# svy Skill

svy: design-based analysis of complex survey data in Python. Covers survey design specification (strata, PSU, weights, FPC), variance estimation (Taylor linearization, BRR, jackknife, bootstrap, SDR), descriptive estimation (means, totals, proportions, ratios, medians), survey-weighted GLM regression (gaussian, binomial, Poisson, gamma), domain/subpopulation analysis, calibration, and survey data I/O (SAS, SPSS, Stata). Uses Polars DataFrames natively. Use when analyzing data from complex sample surveys (NHANES, CPS, ACS PUMS, MEPS, ECLS-K, BRFSS, DHS). For non-survey regression, use statsmodels; for fixed effects, use pyfixest; for panel/IV models, use linearmodels.

Comprehensive skill for complex survey data analysis with svy. Use decision trees below to find the right guidance, then load detailed references.

## What is svy?

svy is the Python package for **design-based analysis of complex survey data**:
- **Survey-aware estimation**: Means, totals, proportions, ratios, medians with proper design-based standard errors
- **GLM regression**: Survey-weighted linear, logistic, Poisson, and gamma regression with design-adjusted inference
- **Flexible variance estimation**: Taylor linearization (default, deterministic in 0.19.0), bootstrap, BRR (including Fay's modification), jackknife (JK2/JKn), and successive-difference replication (SDR)
- **Domain estimation**: Correct subpopulation analysis without pre-filtering (preserves design structure)
- **Native Polars**: Built on Polars DataFrames, not pandas
- **Survey data I/O**: Read/write SAS (.sas7bdat/.xpt), SPSS (.sav/.zsav/.por), Stata (.dta) via the bundled `svy-io` package
- **Calibration**: Post-stratification, raking, and GREG calibration for weight adjustment

Point estimates from svy's Taylor path match independent closed-form weighted computations to floating tolerance (verified — see Version Notes). GLM inference is **cross-validated against R** (2026-07-15): coefficients, SEs, p-values, and residual df agree with R `survey::svyglm(family=quasibinomial()/quasipoisson())` to <1e-6 relative on a matched stratified-clustered design, and design-based categorical tests (Rao-Scott χ²/F) match R's `svychisq` to machine precision. One caveat remains on `margins()` — a small numerical difference (~0.1%/0.9%) plus it omits categorical-level contrasts; see `regression.md`.

## Version Notes

This skill targets **svy 0.19.0** (released 2026-07-12) and was verified against the *installed* library — not online documentation — by the smoke test at `/daaf/scripts/smoke_tests/smoke_svy_a.py` (HARD 4/4, PROBES 6/6, clean run). The published svy docs were partly aspirational at 0.19.0 (the docs themselves state "APIs and documentation continue to mature"), and the installed API diverged from them on several material points. **Where the docs and the installed library disagree, this skill follows the library**; the reference files encode the observed signatures.

### Package architecture (the svy stack)

svy ships as three coordinated packages. Install only `svy` — the others come along automatically:

| Package | Role | You depend on it? |
|---------|------|-------------------|
| **svy** (0.19.0) | Pure-Python core API: `Sample`, `Design`, `estimation`, `weighting`, `glm`, `Cat`, `RepWeights` | Yes — `pip install svy` (pinned in the Dockerfile) |
| **svy-rs** (0.10.0) | Internal compiled Rust compute backend (Taylor variance, replicate creation, GLM fitting). PyPI description: "Do not depend on this directly." | No — never import it |
| **svy-io** (0.1.1) | SAS/SPSS/Stata file I/O (ReadStat C library), returns/consumes Polars. Reached under `svy.io.*` | Indirectly — installed as a dependency |

**Dependency floors (0.19.0):** `svy-rs>=0.10.0,<0.11.0`, `svy-io>=0.1.1,<0.2.0`, `polars[pyarrow]>=1.39.1` (effective floor — svy-rs tightens svy's own stated floor, reported as `>=1.33.1` per PyPI metadata at research time), `numpy>=2.0`, `scipy>=1.13`, Python `>=3.11`. DAAF pins **polars 1.39.3**, which satisfies the floor. The polars `replace_strict`-on-Enum regression is **not** present at 1.39.3 (verified in the smoke test).

**Out of scope:** `svy-sae` (small-area estimation) is a separate Beta package that is **not** installed and is not covered here.

### Change from earlier DAAF pins (0.13.0 → 0.19.0)

If you have code written against the old skill (0.13.0), the biggest observed differences are:
- **No `fpc=` on `svy.Design`** — FPC is specified via `pop_size=` (a column) or `svy.PopSize(psu, ssu)`, and it now **works** (it was non-functional in 0.13.0).
- **`svy.Cat()` is mandatory** for string/categorical GLM predictors — a raw string column raises a strict-cast `ValueError`.
- **`where=` takes a polars expression only** (`pl.col(...)`); a string predicate raises `TypeError`.
- **Batched estimation**: passing `y=[...]` to `mean/total/prop/ratio/median` returns a **`list[Estimate]`** (one per variable), not a stacked frame.
- **svy-io signatures**: `svy.io.read_stata(path)` returns a **bare** `pl.DataFrame`; `svy.io.write_stata(sample, path)` takes a **Sample**.
- **GLM gains the gamma family** and explicit `link=` options.
- **`sample.glm.fit()` returns a `GLM` object directly**; call `.to_polars()` on it for the coefficient table.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `estimation.md` | Means, totals, proportions, ratios, medians, batched calls, domain estimation, result-frame schema | Descriptive survey statistics |
| `regression.md` | Survey-weighted GLM (gaussian/binomial/Poisson/gamma), result schema, margins, links, rpy2 cross-validation bridge | Survey regression models |
| `design-weights.md` | Design specification, FPC, replicate weights, weight creation namespace, calibration, survey data I/O, federal survey patterns | Setting up the survey design object |

### Reading Order

1. **New to svy?** Start with `design-weights.md` then `estimation.md`
2. **Need survey-weighted regression?** Read `design-weights.md` then `regression.md`
3. **Have replicate weights already?** Read `design-weights.md` (replicate design section) then `estimation.md` or `regression.md`
4. **Setting up a federal survey (NHANES, CPS, etc.)?** Read `design-weights.md` (federal survey patterns table)
5. **Coming from samplics?** Read `design-weights.md` for the API; the `Sample` object replaces `TaylorEstimator`/`ReplicateEstimator`

**The reference-file routing in this skill applies to advisory and brainstorming turns as much as implementation.** Recommending an approach, reviewing a plan, or answering a question that touches a routed topic calls for reading the routed reference file just as much as writing code does — the reference files carry curated caveats and environment-specific constraints that this overview and general knowledge lack.

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `data-scientist` | Provides methodology guidance (especially `survey-analysis.md`); svy provides implementation. Load data-scientist for "when and why" to use survey methods |
| `statsmodels` | Complement for non-survey regression (OLS, GLM, time series, diagnostics). **WLS in statsmodels is NOT survey-weighted regression** — it does not account for stratification or clustering |
| `pyfixest` | Complement for fixed effects models and DiD. pyfixest does not handle complex survey designs; use svy for survey-weighted estimation, pyfixest for FE/DiD |
| `linearmodels` | Complement for panel models (RE, FD, Fama-MacBeth) and IV/GMM. Does not handle survey designs |
| `polars` | svy uses Polars DataFrames natively. Load polars skill for data preparation before passing to svy |

## Quick Decision Trees

### "I need to analyze survey data"

```
What task?
├─ Descriptive statistics (mean, total, proportion)
│   └─ ./references/estimation.md
├─ Regression model
│   ├─ Linear (continuous outcome) → ./references/regression.md
│   ├─ Logistic (binary outcome) → ./references/regression.md
│   ├─ Poisson (count outcome) → ./references/regression.md
│   └─ Gamma (positive continuous / skewed) → ./references/regression.md
├─ Set up the survey design object
│   └─ ./references/design-weights.md
├─ Read survey data from SAS/SPSS/Stata
│   └─ ./references/design-weights.md
├─ Subpopulation / domain analysis
│   └─ ./references/estimation.md
└─ Cross-tabulation
    └─ ./references/estimation.md
```

### "I need survey-weighted regression"

```
What model?
├─ Linear regression (continuous Y)
│   └─ family="gaussian" → ./references/regression.md
├─ Logistic regression (binary Y)
│   └─ family="binomial" → ./references/regression.md
├─ Poisson regression (count Y)
│   └─ family="poisson" → ./references/regression.md
├─ Gamma regression (positive, right-skewed Y)
│   └─ family="gamma" → ./references/regression.md
├─ Ordinal logistic / Cox survival / negative binomial / IV
│   └─ Not in svy — use rpy2 + R survey package (see rpy2 bridge below)
└─ Fixed effects + survey weights
    └─ Not directly supported — see Boundaries below
```

### "I need to set up variance estimation"

```
What do you have?
├─ Design variables (strata, PSU, weights)
│   └─ Taylor linearization → ./references/design-weights.md
├─ Pre-computed replicate weights
│   ├─ BRR weights → ./references/design-weights.md
│   ├─ Jackknife weights → ./references/design-weights.md
│   └─ Bootstrap / SDR weights → ./references/design-weights.md
├─ Need to create replicate weights from design
│   └─ ./references/design-weights.md (weighting.create_*_wgts)
└─ Not sure what I have
    └─ Read survey documentation first → ./references/design-weights.md (federal survey table)
```

### "I need descriptive statistics from a survey"

```
What statistic?
├─ Population mean → ./references/estimation.md
├─ Population total → ./references/estimation.md
├─ Proportion → ./references/estimation.md
├─ Ratio (Y/X) → ./references/estimation.md
├─ Median / quantile → ./references/estimation.md
├─ Several variables at once (batched) → ./references/estimation.md
├─ By subgroup (domain estimation) → ./references/estimation.md
└─ Cross-tabulation / hypothesis test → ./references/estimation.md
```

## Boundaries

**svy covers:**
- Design-based estimation (descriptive and regression) for complex surveys
- Taylor and replicate-weight variance estimation
- Domain/subpopulation analysis
- Calibration and weight adjustment
- Survey data I/O (via svy-io)

**svy does NOT cover (use other tools):**
- Fixed effects models — use pyfixest (survey weights + FE is methodologically complex; consult data-scientist skill)
- Panel data models (RE, FD, between) — use linearmodels
- Difference-in-differences — use pyfixest
- Causal inference methods (IV, RD, synthetic control) — use pyfixest/linearmodels/statsmodels
- Time series analysis — use statsmodels
- Machine learning — use scikit-learn
- Ordinal logistic, Cox proportional hazards, negative binomial, multinomial logit — use rpy2 + R survey package
- Small-area estimation — svy-sae (separate Beta package, not installed)
- Survey sampling design and sample size calculation — use data-scientist skill for methodology

## The rpy2 Bridge

For models svy does not support (ordinal logistic, survival models, negative binomial GLM, cumulative link models), fall back to R's `survey` package via rpy2. The bridge also doubles as the **spot-check** path for inference-critical results on extraordinary designs — GLM inference and Rao-Scott categorical tests are already cross-validated against R at 0.19.0 (see `regression.md`), so routine cross-validation before publishing is no longer required.

**Decision rule:** If the model family is not `"gaussian"`, `"binomial"`, `"poisson"`, or `"gamma"`, use rpy2.

**If the session's execution language is R**, skip the bridge entirely: load the `survey-r` skill instead — it covers the full R `survey` package (including `svyolr` and `svycoxph`) natively, with no rpy2 involved. The bridge below is for Python-execution sessions only.

The R survey package (`survey::svyglm`, `survey::svyolr`, `survey::svycoxph`) covers the full range of survey-weighted models. Set up the survey design in R using the same design variables you would pass to `svy.Design`. See R survey package documentation at `r-survey.r-forge.r-project.org` for API details.

## Legacy: samplics

samplics (2020-2026) is archived. svy supersedes it with a cleaner API, Polars integration, and expanded methods. If working with legacy code that uses samplics:
- The API is **substantially different** — `TaylorEstimator`/`ReplicateEstimator` classes are replaced by `svy.Sample`
- samplics used numpy arrays; svy uses Polars DataFrames
- Consult samplics documentation at `samplics-org.github.io/samplics/` for legacy reference
- Migration requires rewriting, not find-and-replace

## File-First Execution in Research Workflows

**Important:** In data research pipelines (see `CLAUDE.md`), svy analyses are executed through **script files**, not interactively. This ensures auditability and reproducibility.

**The pattern:**
1. Write estimation/regression code to `scripts/stage8_analysis/{step}_{task-name}.py`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory file-first execution protocol. All survey analysis scripts must follow the Inline Audit Trail (IAT) standard — document design specification choices (why these strata/PSU/weights, what variance method, domain definitions) with `# INTENT:`, `# REASONING:`, and `# ASSUMES:` comments.

---

## Quick Reference

### Essential Import

```python
import svy
```

### Core Workflow

```python
# 1. Load data — svy.io.read_stata returns a BARE polars.DataFrame
data = svy.io.read_stata("nhanes.dta")

# 2. Specify design (FPC via pop_size=, NOT fpc=)
design = svy.Design(stratum="sdmvstra", psu="sdmvpsu", wgt="wtmec2yr")

# 3. Create sample object
sample = svy.Sample(data, design=design)

# 4. Estimate — result frames carry columns ['est','se','lci','uci','cv']
mean_bmi = sample.estimation.mean("bmxbmi")

# 5. Regress — string predictors MUST be wrapped in svy.Cat(); returns a GLM object
model = sample.glm.fit(y="bmxbmi", x=["ridageyr", svy.Cat("riagendr")], family="gaussian")
coef_table = model.to_polars()   # ['term','estimate','std_err','conf_low','conf_high','statistic','p_value','df']
```

### Core Operations

| Operation | Code |
|-----------|------|
| Design (Taylor) | `svy.Design(stratum="s", psu="p", wgt="w")` |
| Design + FPC | `svy.Design(stratum="s", psu="p", wgt="w", pop_size="N_col")` |
| Sample object | `svy.Sample(df, design=design)` |
| Mean | `sample.estimation.mean("var")` |
| Batched means | `sample.estimation.mean(["v1", "v2"])` → `list[Estimate]` |
| Total | `sample.estimation.total("var")` |
| Proportion | `sample.estimation.prop("var")` |
| Proportion + CI method | `sample.estimation.prop("var", ci_method="wilson")` |
| Ratio | `sample.estimation.ratio(y="num", x="denom")` |
| Median | `sample.estimation.median("var")` |
| Domain estimation | `sample.estimation.mean("var", by="group")` |
| Filtered estimation | `sample.estimation.mean("var", where=pl.col("age") >= 18)` |
| Cross-tab + design test (Rao-Scott χ²/F) | `sample.categorical.tabulate("rowvar", "colvar")` → `Table` (`.stats` carries χ²/F) |
| Linear regression | `sample.glm.fit(y="y", x=[...], family="gaussian")` |
| Logistic regression | `sample.glm.fit(y="y", x=[...], family="binomial")` |
| Poisson regression | `sample.glm.fit(y="y", x=[...], family="poisson")` |
| Gamma regression | `sample.glm.fit(y="y", x=[...], family="gamma")` |
| Categorical predictor (required for strings) | `svy.Cat("varname")` |
| Coefficient table | `model.to_polars()` |
| Average marginal effects (continuous predictors only) | `model.margins()` → `list[GLMMargins]` |
| Create bootstrap rep weights | `sample.weighting.create_bs_wgts(n_reps=500, rstate=42)` |
| Read Stata | `svy.io.read_stata("file.dta")` → `pl.DataFrame` |
| Read SAS | `svy.io.read_sas("file.sas7bdat")` → `pl.DataFrame` |
| Read SPSS | `svy.io.read_spss("file.sav")` → `pl.DataFrame` |
| Write Stata | `svy.io.write_stata(sample, "file.dta")` |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Survey design setup | `./references/design-weights.md` |
| Taylor linearization (deterministic in 0.19.0) | `./references/design-weights.md` |
| Finite population correction (pop_size / PopSize) | `./references/design-weights.md` |
| Replicate weights (BRR, jackknife, bootstrap, SDR) | `./references/design-weights.md` |
| Creating replicate weights from a design | `./references/design-weights.md` |
| Fay's BRR modification | `./references/design-weights.md` |
| Weight types and handling | `./references/design-weights.md` |
| Weighting namespace (adjust/calibrate/rake/trim/normalize) | `./references/design-weights.md` |
| Federal survey design patterns | `./references/design-weights.md` |
| Calibration and post-stratification | `./references/design-weights.md` |
| Reading/writing SAS/SPSS/Stata files (svy-io) | `./references/design-weights.md` |
| Population means / totals | `./references/estimation.md` |
| Proportions (with ci_method) | `./references/estimation.md` |
| Ratios | `./references/estimation.md` |
| Medians and quantiles | `./references/estimation.md` |
| Batched multi-variable estimation | `./references/estimation.md` |
| Domain / subpopulation estimation | `./references/estimation.md` |
| Result-frame schema (est/se/lci/uci/cv) | `./references/estimation.md` |
| Cross-tabulations / hypothesis tests (Rao-Scott χ²/F, verified vs R) | `./references/estimation.md` |
| Design effects (DEFF) | `./references/estimation.md` |
| Survey-weighted GLM (gaussian/binomial/Poisson/gamma) | `./references/regression.md` |
| GLM coefficient schema + margins | `./references/regression.md` |
| GLM link functions | `./references/regression.md` |
| Categorical predictors (svy.Cat — mandatory for strings) | `./references/regression.md` |
| Survey regression vs. WLS vs. cluster-robust | `./references/regression.md` |
| GLM inference cross-validation vs. R (verified <1e-6) | `./references/regression.md` |
| rpy2 bridge to R survey package | `./references/regression.md` |
| samplics migration | `./references/design-weights.md` |
| Polars DataFrame integration | `./references/design-weights.md` |

## Citation

When this library is used as a primary analytical tool, include in the report's
Software & Tools references:

> Diallo, M.S. svy: Python package for complex survey sampling and analysis [Computer software]. (Formerly samplics.)

**Cite when:** svy is used for survey-weighted estimation with complex survey designs (strata, PSU, replicate weights).
**Do not cite when:** Only imported but no survey estimation performed.

For method-specific citations (e.g., variance estimation techniques),
consult the reference files in this skill and `agent_reference/CITATION_REFERENCE.md`.
