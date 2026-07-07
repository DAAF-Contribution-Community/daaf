---
name: fixest
description: |
  Fast high-dimensional fixed effects in R: feols/fepois/feglm/fenegbin with
  multi-way FE; IV estimation; DiD (TWFE, Sun-Abraham via sunab); clustered/
  heteroskedasticity-robust SEs; etable/coefplot/iplot for reporting. Use when
  execution language is R. Python equivalent: pyfixest. For panel RE/between
  use plm; for GLM without FE use r-stats.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "fixest 0.14.0"
  skill-last-updated: "2026-05-08"
  tags: ["r", "econometrics", "fixed-effects", "did", "iv"]
---

# fixest Skill

fixest: the canonical R package for fast high-dimensional fixed effects estimation.
Covers OLS (feols), Poisson (fepois), GLM (feglm, including logit/probit with FE),
negative binomial (fenegbin), and nonlinear models (feNmlm) with multi-way absorbed
fixed effects. Supports instrumental variables via three-part formula; difference-in-
differences via TWFE and Sun-Abraham (sunab); standard errors including clustered,
heteroskedasticity-robust, Newey-West, Driscoll-Kraay, and Conley spatial; and
publication output via etable, coefplot, and iplot. Use when execution language is R
and the analysis involves fixed effects regression, IV, DiD, or publication-quality
regression tables. Python equivalent: pyfixest (which is a port of this package).
For panel random/between effects, use plm. For GLM/time series without fixed effects,
use base R stats or dedicated packages.

Comprehensive skill for fixed effects regression, instrumental variables, and
difference-in-differences estimation with the fixest R package. Use decision trees
below to find the right guidance, then load detailed references.

## What is fixest?

fixest (Berge, 2018) is the most widely-used R package for fast fixed effects
estimation in applied economics and quantitative social science:

- **Fast**: Multi-way FE demeaning via alternating projections (C++ backend)
- **Concise formula syntax**: Fixed effects after `|`, IV after second `|`,
  multi-estimation via `sw()`/`csw()`/`csw0()`
- **Full GLM support with FE**: feglm handles logit, probit, and other GLMs
  with absorbed high-dimensional FE (unlike pyfixest, which lacks this)
- **Sun-Abraham DiD**: Built-in `sunab()` formula function for staggered DiD
- **Flexible inference**: Switch SE types post-estimation; one-sided formulas
  for clustering (`vcov = ~group`)
- **Publication output**: `etable()` for regression tables, `coefplot()` and
  `iplot()` for coefficient and event study visualization

## Version Notes

This skill targets **fixest 0.14.0** (R 4.5.3). fixest 0.13 introduced the
breaking changes that pyfixest 0.40.0 adopted (default SE changed to IID,
singleton removal by default, ssc argument renames). fixest 0.14.0 is a stable
release building on those defaults.

Key defaults in 0.14.0:
- Default standard errors: `"iid"` (not cluster-by-first-FE as in pre-0.13)
- Singleton removal: on by default (`fixef.rm = "perfect_fit"`)
- `ssc()` arguments: `adj`, `fixef.K`, `cluster.adj`, `cluster.df`

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | feols() basics, formula syntax, multi-estimation (csw, sw, sw0), data requirements | Starting with fixest |
| `fixed-effects.md` | Multi-way FE syntax, FE interactions (^), varying slopes, FE recovery via fixef() | FE models and specification |
| `standard-errors.md` | Clustered SEs (vcov), HC robust, Conley spatial, Driscoll-Kraay, Newey-West, two-way clustering | Inference choices |
| `iv.md` | IV three-part formula, first-stage diagnostics, weak instrument tests | IV/2SLS estimation |
| `did.md` | TWFE with feols, sunab() for staggered DiD, event study plots via iplot() | DiD designs |
| `reporting.md` | etable() for regression tables (LaTeX, data.frame), coefplot(), iplot(), fixef() for FE extraction | Presenting results |
| `models.md` | fepois (Poisson), feglm (GLM with FE), fenegbin (negative binomial), feNmlm (nonlinear), model families | Non-OLS models |
| `gotchas.md` | Singleton observations, separation in Poisson, formula parsing pitfalls, SE defaults, panel vs cross-section | Debugging issues |

### Reading Order

1. **New to fixest?** Start with `quickstart.md` then `fixed-effects.md`
2. **Running DiD?** Read `quickstart.md`, then `did.md`
3. **Need IV?** Read `quickstart.md`, then `iv.md`
4. **Making tables?** Check `reporting.md`
5. **Non-OLS models?** Read `models.md`
6. **Coming from pyfixest?** Read `quickstart.md` then `gotchas.md`

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `pyfixest` | Python port of this package — near-identical formula syntax, some features missing (feglm with FE, etable maturity). Load when execution language is Python. |
| `data-scientist` | Methodology guidance — load for "why and when" behind methods |
| `r-python-translation` | Cross-language mappings for R fixest vs Python pyfixest and statsmodels |
| `plm` | Random effects, between estimator, Hausman test — complements fixest when FE-only is insufficient |
| `r-stats` | Base R glm(), lm() without FE — use when FE absorption is not needed |
| `gt` | Publication-quality tables — use gt/modelsummary for formatted regression output (alternative to etable) |

## Quick Decision Trees

### "I need to run a regression"

```
What kind of regression?
├─ OLS with fixed effects → ./references/quickstart.md
├─ OLS without fixed effects → ./references/quickstart.md
├─ IV / 2SLS with FE → ./references/iv.md
├─ Poisson (count data) with FE → ./references/models.md
├─ Logit / Probit with FE → ./references/models.md (feglm)
├─ Negative binomial with FE → ./references/models.md (fenegbin)
├─ Multiple models at once → ./references/quickstart.md (sw/csw)
└─ Nonlinear custom model → ./references/models.md (feNmlm)
```

### "I need difference-in-differences"

```
DiD design?
├─ Simple 2×2 DiD (one treatment date) → ./references/did.md
├─ Staggered treatment timing → ./references/did.md
│   ├─ Sun-Abraham saturated (sunab) → ./references/did.md
│   └─ TWFE (caution with heterogeneity) → ./references/did.md
├─ Event study plot → ./references/did.md + ./references/reporting.md
└─ Parallel trends assessment → ./references/did.md
```

### "I need to choose standard errors"

```
What inference?
├─ Heteroskedasticity-robust (HC1) → ./references/standard-errors.md
├─ Clustered (one-way / two-way) → ./references/standard-errors.md
├─ Newey-West (HAC) → ./references/standard-errors.md
├─ Driscoll-Kraay (panel with cross-sect dependence) → ./references/standard-errors.md
├─ Conley spatial → ./references/standard-errors.md
└─ Small sample corrections (ssc) → ./references/standard-errors.md
```

### "I need to present results"

```
Presenting results?
├─ Regression table (multiple models) → ./references/reporting.md
├─ Coefficient plot → ./references/reporting.md
├─ Event study plot → ./references/reporting.md
├─ LaTeX table output → ./references/reporting.md
└─ Extract fixed effects → ./references/reporting.md
```

### "Something isn't working"

```
Having issues?
├─ Different results from old code → ./references/gotchas.md
├─ Singleton warnings → ./references/gotchas.md
├─ Poisson separation/convergence → ./references/gotchas.md
├─ Formula parsing errors → ./references/gotchas.md
├─ pyfixest vs fixest differences → ./references/gotchas.md
└─ Collinearity with FE → ./references/gotchas.md
```

## File-First Execution in Research Workflows

**Important:** In DAAF research pipelines, fixest regressions are executed through
**script files**, not interactively. This ensures auditability and reproducibility.

**The pattern:**
1. Write regression code to `scripts/stage8_analysis/{step}_{task-name}.R`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory
file-first execution protocol covering complete code file writing, output capture,
and file versioning rules. All regression scripts must follow the Inline Audit
Trail (IAT) standard — see `agent_reference/INLINE_AUDIT_TRAIL.md`. For regression
code, document model specification choices (why this estimator, why this clustering
level, what identifying assumptions) with `# INTENT:`, `# REASONING:`, and
`# ASSUMES:` comments.

**See:**
- `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` — Stage 8 (Analysis & Visualization)
- `agent_reference/INLINE_AUDIT_TRAIL.md` — IAT documentation standard

The examples below show fixest syntax. In research workflows, wrap them in
scripts following the file-first pattern.

---

## Quick Reference

### Essential Setup

```r
library(fixest)
library(arrow)  # For parquet I/O (DAAF convention)
```

### Core Estimation Functions

| Function | Purpose |
|----------|---------|
| `feols(y ~ x \| fe, data)` | OLS with fixed effects |
| `fepois(y ~ x \| fe, data)` | Poisson with fixed effects |
| `feglm(y ~ x \| fe, data, family)` | GLM (logit, probit, etc.) with fixed effects |
| `fenegbin(y ~ x \| fe, data)` | Negative binomial with fixed effects |
| `feNmlm(fml, data, family)` | Nonlinear models with fixed effects |

### Formula Syntax Quick Reference

| Pattern | Meaning | Example |
|---------|---------|---------|
| `y ~ x1 + x2` | No FE | `y ~ educ + exper` |
| `y ~ x \| fe1 + fe2` | With FE | `y ~ educ \| state + year` |
| `y ~ x \| fe \| x_endo ~ z` | FE + IV | `y ~ exper \| state \| educ ~ college_prox` |
| `i(factor, ref = val)` | Categorical with ref | `y ~ i(year, ref = 2000) \| state` |
| `sunab(cohort, period)` | Sun-Abraham DiD | `y ~ sunab(cohort, period) \| id + period` |
| `sw(x1, x2)` | Stepwise alternatives | `y ~ sw(educ, exper) \| state` |
| `csw0(x1, x2)` | Cumulative stepwise | `y ~ csw0(educ, exper) \| state` |
| `c(y1, y2) ~ x` | Multiple outcomes | `c(wage, hours) ~ educ \| state` |

### Post-Estimation Essentials

```r
fit <- feols(y ~ x1 + x2 | fe, data = df)

summary(fit)                             # Print results
summary(fit, vcov = "hetero")            # Re-estimate with robust SEs
summary(fit, vcov = ~state)              # Clustered SEs
coef(fit)                                # Named vector of coefficients
se(fit)                                  # Standard errors
confint(fit)                             # Confidence intervals
predict(fit)                             # Fitted values
resid(fit)                               # Residuals
fixef(fit)                               # List of FE estimates
r2(fit, type = "r2")                     # R-squared
r2(fit, type = "wr2")                    # Within R-squared
fitstat(fit, type = "ivf")               # First-stage F (IV only)
```

### Reporting

```r
etable(fit1, fit2, fit3)                # Console regression table
etable(fit1, fit2, tex = TRUE)          # LaTeX output
coefplot(fit1, fit2)                    # Coefficient plot
iplot(fit)                              # Event study / interaction plot
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| First regression | `./references/quickstart.md` |
| Formula syntax | `./references/quickstart.md` |
| Multi-estimation (sw, csw, csw0) | `./references/quickstart.md` |
| Multiple outcomes (c(y1,y2)) | `./references/quickstart.md` |
| Data requirements | `./references/quickstart.md` |
| Multi-way fixed effects | `./references/fixed-effects.md` |
| FE interactions (^) | `./references/fixed-effects.md` |
| Varying slopes | `./references/fixed-effects.md` |
| FE recovery (fixef) | `./references/fixed-effects.md` |
| Singleton removal | `./references/fixed-effects.md` |
| Clustered SEs | `./references/standard-errors.md` |
| HC robust SEs | `./references/standard-errors.md` |
| Two-way clustering | `./references/standard-errors.md` |
| Newey-West (NW) | `./references/standard-errors.md` |
| Driscoll-Kraay (DK) | `./references/standard-errors.md` |
| Conley spatial | `./references/standard-errors.md` |
| Small sample corrections (ssc) | `./references/standard-errors.md` |
| IV formula syntax | `./references/iv.md` |
| First-stage diagnostics | `./references/iv.md` |
| Weak instrument tests | `./references/iv.md` |
| TWFE DiD | `./references/did.md` |
| Sun-Abraham (sunab) | `./references/did.md` |
| Event study plots | `./references/did.md` |
| Parallel trends | `./references/did.md` |
| etable | `./references/reporting.md` |
| coefplot | `./references/reporting.md` |
| iplot | `./references/reporting.md` |
| LaTeX output | `./references/reporting.md` |
| Poisson (fepois) | `./references/models.md` |
| GLM with FE (feglm) | `./references/models.md` |
| Negative binomial (fenegbin) | `./references/models.md` |
| Nonlinear (feNmlm) | `./references/models.md` |
| Singleton observations | `./references/gotchas.md` |
| Poisson separation | `./references/gotchas.md` |
| Formula parsing pitfalls | `./references/gotchas.md` |
| SE default changes | `./references/gotchas.md` |
| pyfixest vs fixest differences | `./references/gotchas.md` |

## Citation

When this library is used as a primary analytical tool, include in the report's
Software & Tools references:

> Berge, L. (2018). "Efficient estimation of maximum likelihood models with
> multiple fixed-effects: the R package FENmlm." CREA Discussion Paper 2018-13.
> Updated as: Berge, L. (2026). fixest: Fast Fixed-Effects Estimations
> [Computer software]. https://CRAN.R-project.org/package=fixest

**Cite when:** fixest is used for regression estimation (OLS, Poisson, GLM, IV)
or difference-in-differences analysis.
**Do not cite when:** Only loaded but no estimation performed.

For the arXiv methods paper:

> Berge, L., Butts, K., & McDermott, G. (2026). "Fast and User-Friendly
> Econometrics Estimations: The R Package fixest." arXiv:2601.21749.

For method-specific citations (e.g., Sun-Abraham, individual DiD estimators),
consult the reference files in this skill and `agent_reference/CITATION_REFERENCE.md`.
