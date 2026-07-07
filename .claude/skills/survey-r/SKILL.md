---
name: survey-r
description: >-
  Complex survey analysis in R with survey (Lumley): svydesign, svymean/svytotal,
  svyglm, svyby domains, replicate weights (BRR, jackknife, bootstrap). Use when
  execution language is R. Python equivalent: svy. lm(weights=) is NOT survey
  analysis.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "survey 4.5"
  skill-last-updated: "2026-05-08"
  tags: ["r", "survey", "complex-samples", "stratification", "clustering"]
---

# R Survey Skill

R's `survey` package by Thomas Lumley -- the canonical tool for design-based
analysis of complex survey data. Covers survey design specification (strata, PSU,
weights, FPC), variance estimation (Taylor linearization, BRR, jackknife,
bootstrap), descriptive estimation (means, totals, proportions, ratios,
quantiles), survey-weighted GLM regression (gaussian, binomial, Poisson, ordinal,
Cox PH), domain/subpopulation analysis, calibration, and replicate weight
handling. The Python `svy` package is modeled after this R implementation. Use
when execution language is R and the data comes from a complex sample survey
(NHANES, CPS, ACS PUMS, BRFSS, DHS, ECLS-K, MEPS-HC). For non-survey regression
in R, use `r-stats`; for fixed effects use `fixest`; for panel RE/between use
`plm`.

## What is the survey Package?

The `survey` package is the definitive implementation of design-based inference
for complex survey data. First released in 2003, it is the reference
implementation that Python's `svy` and Stata's `svy:` prefix are modeled after.

- **Design object**: `svydesign()` -- specifies strata, PSU, weights, FPC
- **Survey-aware estimation**: `svymean()`, `svytotal()`, `svyratio()`,
  `svyquantile()` with design-based standard errors
- **GLM regression**: `svyglm()` for linear, logistic, Poisson, and more with
  design-adjusted inference
- **Domain estimation**: `svyby()` for correct subpopulation analysis without
  pre-filtering
- **Replicate weights**: `svrepdesign()` for BRR, jackknife, bootstrap, Fay
- **Calibration**: `calibrate()`, `postStratify()`, `rake()` for weight
  adjustment
- **Model extensions**: `svyolr()` for ordinal logistic, `svycoxph()` for
  survival analysis -- models not available in Python's svy

## Version Notes

This skill targets **survey 4.5** on **R 4.5.3**. Key features available:

- `svydesign()` and `svrepdesign()` for all design types
- `svyglm()` with quasi-family support (quasibinomial, quasipoisson)
- `as.svrepdesign()` to convert Taylor designs to replicate weight designs
- `svycontrast()` for custom linear/nonlinear contrasts
- Lonely PSU handling via `options(survey.lonely.psu = ...)`
- `svyby()` for domain estimation across arbitrary grouping variables

**Note on emmeans:** The `emmeans` package is NOT installed in this environment.
For marginal means or pairwise comparisons from survey models, use
`svycontrast()` for custom contrasts, or compute predicted values manually via
`predict(svyglm_fit, newdata = ...)`. See `./references/regression.md` for
patterns.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | svydesign(), svymean(), svytotal(), confint(), basic workflow | Starting with survey or need design setup |
| `estimation.md` | Point estimates, ratios, quantiles, svyby() for domains, svycontrast() | Descriptive survey statistics |
| `regression.md` | svyglm() for linear/logit/Poisson, update(), summary output, marginal effects without emmeans | Survey regression models |
| `replication.md` | svrepdesign(), as.svrepdesign(), BRR, jackknife, bootstrap, replicate weight surveys | Working with replicate weights |
| `domains.md` | svyby() domain estimation, interaction of strata with subgroups, conditional analysis | Subpopulation analysis |
| `gotchas.md` | Lonely PSU handling, degrees of freedom, WLS-is-not-survey, subsetting (subset= not filter), calibration | Debugging common issues |

### Reading Order

1. **New to survey in R?** Start with `quickstart.md` then `estimation.md`
2. **Need survey-weighted regression?** Read `quickstart.md` then `regression.md`
3. **Have replicate weights?** Read `replication.md` then `estimation.md` or
   `regression.md`
4. **Need subpopulation estimates?** Read `domains.md`
5. **Setting up a federal survey (NHANES, CPS)?** Read `quickstart.md` (federal
   survey patterns table)
6. **Coming from Python svy?** Read `quickstart.md` -- the R API is the original
   that svy was modeled after

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `svy` | Python equivalent for complex survey analysis. Python's `svy` is modeled after R's `survey`. If execution language is Python, use `svy` instead |
| `data-scientist` | Provides methodology guidance (especially `survey-analysis.md`); survey-r provides R implementation. Load data-scientist for "when and why" |
| `r-stats` | Complement for non-survey regression (OLS, GLM, diagnostics). **base R `lm()` with weights is NOT survey-weighted regression** -- it does not account for stratification or clustering |
| `fixest` | Complement for fixed effects models and DiD. fixest does not handle complex survey designs; use survey-r for survey-weighted estimation |
| `plm` | Complement for panel models (RE, between, first difference). Does not handle survey designs |
| `tidyverse` | Use for data preparation before passing to survey design objects. survey uses base R data.frames |

## Quick Decision Trees

### "I need to analyze survey data in R"

```
What task?
+-- Descriptive statistics (mean, total, proportion)
|   +-- ./references/estimation.md
+-- Regression model
|   +-- Linear (continuous outcome) --> ./references/regression.md
|   +-- Logistic (binary outcome) --> ./references/regression.md
|   +-- Poisson (count outcome) --> ./references/regression.md
|   +-- Ordinal logistic --> ./references/regression.md (svyolr)
|   +-- Cox survival --> ./references/regression.md (svycoxph)
+-- Set up the survey design object
|   +-- ./references/quickstart.md
+-- Subpopulation / domain analysis
|   +-- ./references/domains.md
+-- Replicate weight design (BRR, jackknife, bootstrap)
|   +-- ./references/replication.md
+-- Something isn't working
    +-- ./references/gotchas.md
```

### "I need survey-weighted regression in R"

```
What model?
+-- Linear regression (continuous Y)
|   +-- svyglm(family = gaussian()) --> ./references/regression.md
+-- Logistic regression (binary Y)
|   +-- svyglm(family = quasibinomial()) --> ./references/regression.md
+-- Poisson regression (count Y)
|   +-- svyglm(family = quasipoisson()) --> ./references/regression.md
+-- Ordinal logistic (ordered categories)
|   +-- svyolr() --> ./references/regression.md
+-- Cox proportional hazards (survival)
|   +-- svycoxph() --> ./references/regression.md
+-- Negative binomial (overdispersed counts)
|   +-- svyglm(family = quasipoisson()) as approximation
|   +-- Or: MASS::glm.nb() ignores survey design -- use with caution
+-- Fixed effects + survey weights
    +-- Methodologically complex -- consult data-scientist skill
```

### "I need to set up variance estimation"

```
What do you have?
+-- Design variables (strata, PSU, weights)
|   +-- Taylor linearization via svydesign() --> ./references/quickstart.md
+-- Pre-computed replicate weights
|   +-- BRR --> ./references/replication.md
|   +-- Jackknife --> ./references/replication.md
|   +-- Bootstrap --> ./references/replication.md
+-- Need to create replicate weights from design
|   +-- as.svrepdesign() --> ./references/replication.md
+-- Not sure what I have
    +-- Read survey documentation --> ./references/quickstart.md (federal survey
        table)
```

## Boundaries

**survey covers:**
- Design-based estimation (descriptive and regression) for complex surveys
- Taylor and replicate-weight variance estimation
- Domain/subpopulation analysis via `svyby()` and `subset()`
- Calibration (post-stratification, raking, GREG)
- Ordinal logistic (`svyolr`), Cox PH (`svycoxph`) -- models NOT in Python svy
- Interaction with `broom::tidy()` for tidy output

**survey does NOT cover (use other tools):**
- Fixed effects models -- use `fixest` (survey weights + FE is methodologically
  complex; consult `data-scientist` skill)
- Panel data models (RE, FD, between) -- use `plm`
- Difference-in-differences -- use `fixest`
- Machine learning -- use `tidymodels` or `scikit-learn` via reticulate
- Survey sampling design and sample size calculation -- use `data-scientist`
  skill for methodology
- Marginal means via `emmeans` -- emmeans is NOT installed; use `svycontrast()`
  or manual `predict()` instead

## File-First Execution in Research Workflows

**Important:** In data research pipelines (see `CLAUDE.md`), R analyses are
executed through **script files**, not interactively. This ensures auditability
and reproducibility.

**The pattern:**
1. Write survey analysis code to `scripts/stage8_analysis/{step}_{task-name}.R`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory
file-first execution protocol. All survey analysis scripts must follow the Inline
Audit Trail (IAT) standard -- document design specification choices (why these
strata/PSU/weights, what variance method, domain definitions) with `# INTENT:`,
`# REASONING:`, and `# ASSUMES:` comments.

---

## Quick Reference

### Essential Library Loading

```r
# --- Config ---
library(survey)
```

### Core Workflow

```r
# 1. Load data
data <- arrow::read_parquet("data/raw/nhanes_demo.parquet")

# 2. Specify design
# INTENT: NHANES uses a complex multi-stage stratified cluster design
# REASONING: sdmvstra = pseudo-strata, sdmvpsu = pseudo-PSU,
#   wtmec2yr = 2-year MEC exam weight
# ASSUMES: Analysis population is the MEC-examined subsample
des <- svydesign(
  ids = ~sdmvpsu,
  strata = ~sdmvstra,
  weights = ~wtmec2yr,
  data = data,
  nest = TRUE
)

# 3. Estimate
svymean(~bmxbmi, design = des, na.rm = TRUE)
svytotal(~bmxbmi, design = des, na.rm = TRUE)
confint(svymean(~bmxbmi, design = des, na.rm = TRUE))

# 4. Regression
fit <- svyglm(bmxbmi ~ ridageyr + factor(riagendr), design = des)
summary(fit)
```

### Core Operations

| Operation | Code |
|-----------|------|
| Design (Taylor) | `svydesign(ids = ~psu, strata = ~strat, weights = ~wt, data = df, nest = TRUE)` |
| Design (replicate) | `svrepdesign(weights = ~wt, repweights = "wt[0-9]+", type = "BRR", data = df)` |
| Mean | `svymean(~var, design = des, na.rm = TRUE)` |
| Total | `svytotal(~var, design = des, na.rm = TRUE)` |
| Proportion | `svymean(~factor(var), design = des)` |
| Ratio | `svyratio(~num, ~denom, design = des)` |
| Quantile | `svyquantile(~var, design = des, quantiles = 0.5)` |
| Domain estimation | `svyby(~var, ~group, design = des, svymean)` |
| Linear regression | `svyglm(y ~ x, design = des, family = gaussian())` |
| Logistic regression | `svyglm(y ~ x, design = des, family = quasibinomial())` |
| Poisson regression | `svyglm(y ~ x, design = des, family = quasipoisson())` |
| Ordinal logistic | `svyolr(ordered(y) ~ x, design = des)` |
| Cox PH | `svycoxph(Surv(time, event) ~ x, design = des)` |
| Subset design | `subset(des, age >= 18)` |
| Confidence intervals | `confint(svymean(...))` |
| Tidy output | `broom::tidy(svyglm_fit, conf.int = TRUE)` |
| Convert to replicate | `as.svrepdesign(des, type = "JKn")` |
| Calibrate | `calibrate(des, formula = ~age_group, population = pop_totals)` |

### Formula Syntax in survey

```r
# Single variable
svymean(~income, design = des)

# Multiple variables
svymean(~income + age, design = des)

# Factor variable (for proportions)
svymean(~factor(education), design = des)

# Domain estimation
svyby(~income, ~gender, design = des, svymean)

# Regression with interaction
svyglm(y ~ x1 * factor(x2), design = des)
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| svydesign() setup | `./references/quickstart.md` |
| Taylor linearization | `./references/quickstart.md` |
| svymean() / svytotal() | `./references/quickstart.md` |
| confint() for survey estimates | `./references/quickstart.md` |
| Federal survey design patterns | `./references/quickstart.md` |
| Point estimates | `./references/estimation.md` |
| Proportions | `./references/estimation.md` |
| Ratios | `./references/estimation.md` |
| Quantiles / medians | `./references/estimation.md` |
| svyby() for domain estimation | `./references/estimation.md` |
| svycontrast() | `./references/estimation.md` |
| Design effects (DEFF) | `./references/estimation.md` |
| Cross-tabulations (svytable) | `./references/estimation.md` |
| Chi-squared test (svychisq) | `./references/estimation.md` |
| svyglm() linear | `./references/regression.md` |
| svyglm() logistic | `./references/regression.md` |
| svyglm() Poisson | `./references/regression.md` |
| svyolr() ordinal logistic | `./references/regression.md` |
| svycoxph() Cox PH | `./references/regression.md` |
| Model comparison / update() | `./references/regression.md` |
| Marginal effects without emmeans | `./references/regression.md` |
| Odds ratios and IRR | `./references/regression.md` |
| svrepdesign() | `./references/replication.md` |
| as.svrepdesign() | `./references/replication.md` |
| BRR / Fay's method | `./references/replication.md` |
| Jackknife (JK1, JKn) | `./references/replication.md` |
| Bootstrap replicate weights | `./references/replication.md` |
| ACS PUMS successive difference | `./references/replication.md` |
| Domain estimation (svyby) | `./references/domains.md` |
| Subsetting designs (subset=) | `./references/domains.md` |
| Interaction domains | `./references/domains.md` |
| Lonely PSU handling | `./references/gotchas.md` |
| Degrees of freedom | `./references/gotchas.md` |
| WLS is not survey regression | `./references/gotchas.md` |
| subset() vs filter() | `./references/gotchas.md` |
| Calibration (calibrate, rake, postStratify) | `./references/gotchas.md` |
| Weight selection | `./references/gotchas.md` |

## Citation

When the survey package is used as a primary analytical tool, include in the
report's Software & Tools references:

> Lumley, T. (2004). "Analysis of Complex Survey Samples." Journal of
> Statistical Software, 9(8), 1-19.

> Lumley, T. (2023). survey: Analysis of Complex Survey Samples. R package
> version 4.5.

**Cite when:** survey is used for survey-weighted estimation with complex survey
designs (strata, PSU, replicate weights).
**Do not cite when:** Only loaded but no survey estimation performed.
