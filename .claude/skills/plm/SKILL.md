---
name: plm
description: |
  R panel data models with plm: within (FE), random (RE), between, first
  difference, Fama-MacBeth. Hausman test, panel unit root tests. Includes
  estimatr for robust estimation and lme4 for mixed effects. Use when
  execution language is R. Python equivalent: linearmodels. For high-
  dimensional FE use fixest; for cross-sectional OLS/GLM use r-stats.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "plm 2.6-7"
  skill-last-updated: "2026-05-08"
  tags: ["r", "panel-data", "plm", "random-effects", "mixed-effects"]
---

# plm Skill

R's canonical panel data modeling package. Covers within (FE), random effects
(RE), between, first difference, pooled OLS, and Fama-MacBeth estimators via
`plm()`. Provides the Hausman test (`phtest()`) for FE vs RE selection, panel
serial correlation tests (`plmtest()`, `pbsytest()`), cross-sectional
dependence tests (`pcdtest()`), and panel unit root tests (`purtest()`,
`cipstest()`). Includes `estimatr` for robust/cluster-robust estimation
(`lm_robust()`, `iv_robust()`) and `lme4` for mixed-effects models
(`lmer()`, `glmer()`). Use when execution language is R and the analysis
involves panel data requiring RE, between, first-difference, or Hausman
testing. Python equivalent: `linearmodels`. For high-dimensional fixed effects,
IV with FE, or DiD, use `fixest`. For cross-sectional OLS/GLM without panel
structure, use `r-stats`.

## What is plm?

plm (Croissant & Millo, 2008) is the standard R package for linear panel data
models. It provides a unified formula interface that mirrors base R's `lm()` but
adds panel-aware estimation:

- **Panel-aware data**: `pdata.frame()` declares entity and time identifiers
- **Five estimators**: within (FE), random (RE), between, first difference (fd),
  pooling -- selected via the `model=` argument to `plm()`
- **Fama-MacBeth**: `pmg()` with `model = "mg"` or `model = "cmg"`
- **Hausman test**: `phtest()` for FE vs RE model selection
- **Dynamic panels**: `pgmm()` for Arellano-Bond and Blundell-Bond GMM
- **Panel IV**: `plm()` with `instruments` argument for 2SLS within panels
- **Rich diagnostics**: serial correlation, cross-sectional dependence, unit
  root tests, all panel-specific

This skill also covers two companion packages:

| Package | Version | Role |
|---------|---------|------|
| `estimatr` | 1.0.6 | `lm_robust()` and `iv_robust()` with HC/CR standard errors |
| `lme4` | 2.0-1 | `lmer()` for random intercepts/slopes (mixed-effects models) |

## Version Notes

This skill targets **plm 2.6-7** (R 4.5.3). Key features:
- `pdata.frame()` for explicit panel structure declaration
- `plm()` formula interface: `y ~ x1 + x2 | instruments`
- Default vcov is classical (homoskedastic) -- always specify robust/clustered
  vcov explicitly
- `pgmm()` supports both Arellano-Bond ("ab") and Blundell-Bond ("bb")
  transformations

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | pdata.frame, plm() basics, model= argument, summary, coeftest | Starting with plm or panel data in R |
| `models.md` | within, random, between, fd, Fama-MacBeth, comparison | Choosing or switching between panel estimators |
| `diagnostics.md` | phtest() Hausman, plmtest(), pcdtest(), panel unit root | Testing assumptions, model selection |
| `iv.md` | Panel IV via plm() instruments, Sargan/Hansen, pgmm() | IV estimation within panel structure |
| `robust.md` | estimatr lm_robust/iv_robust, HC/CR SEs, plm vcov options | Robust or clustered standard errors |
| `mixed-effects.md` | lme4 lmer/glmer, random intercepts/slopes, ICC | Mixed-effects / multilevel models |
| `gotchas.md` | pdata.frame requirements, FE vs RE, fixest vs plm routing | Debugging or package selection |

### Reading Order

1. **New to plm?** Start with `quickstart.md` then `models.md`
2. **FE vs RE decision?** Read `quickstart.md` then `diagnostics.md`
3. **Need robust SEs?** Read `robust.md`
4. **Panel IV or GMM?** Read `iv.md`
5. **Mixed-effects models?** Read `mixed-effects.md`
6. **Coming from linearmodels (Python)?** Read `quickstart.md` then `gotchas.md`

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `linearmodels` | Python equivalent for panel data. plm covers the same estimators (FE, RE, between, FD, Fama-MacBeth) with R-native formula syntax. Key API difference: plm uses `pdata.frame()` for panel declaration; linearmodels uses pandas MultiIndex |
| `fixest` | Preferred for high-dimensional FE, FE + IV, DiD, fast FE demeaning, publication tables. Use plm when fixest cannot do what you need (RE, between, Hausman test, Fama-MacBeth, panel diagnostics, dynamic GMM) |
| `r-stats` | Base R regression without panel structure. Use r-stats for cross-sectional OLS, GLM, classical tests. plm extends the lm() formula interface for panel data |
| `data-scientist` | Methodology guidance -- load for "why and when" behind model choices |
| `tidyverse` | Data preparation before estimation; plm accepts data.frames directly from dplyr pipelines |
| `gt` | Publication-quality tables -- plm model output feeds into modelsummary/gt for formatted regression tables |

## Quick Decision Trees

### "I need a panel model in R"

```
What panel estimation method?
+-- Fixed effects (within estimator)
|   +-- 1-2 way FE, no IV --> plm (model = "within") or fixest feols
|   +-- 3+ way FE --> fixest (plm max 2-way via twoways)
|   +-- FE + IV combined --> plm with instruments or fixest 3-part formula
|   +-- FE + DiD --> fixest (plm has no DiD)
+-- Random effects (GLS) --> plm (model = "random")
|   --> ./references/models.md
+-- FE vs RE comparison --> plm phtest() (Hausman test)
|   --> ./references/diagnostics.md
+-- Between estimator --> plm (model = "between")
|   --> ./references/models.md
+-- First difference --> plm (model = "fd")
|   --> ./references/models.md
+-- Pooled OLS (panel-aware) --> plm (model = "pooling")
|   --> ./references/models.md
+-- Fama-MacBeth --> plm pmg(model = "mg")
|   --> ./references/models.md
+-- Dynamic panel (Arellano-Bond/Blundell-Bond) --> plm pgmm()
|   --> ./references/iv.md
```

### "I need robust standard errors"

```
What inference?
+-- Heteroskedasticity-robust (HC) --> ./references/robust.md
|   +-- For plm models: vcovHC() from plm
|   +-- For lm models: estimatr::lm_robust()
+-- Clustered SEs --> ./references/robust.md
|   +-- For plm models: vcovHC(type = "HC1", cluster = "group")
|   +-- For lm models: estimatr::lm_robust(clusters = group)
+-- Newey-West (panel HAC) --> ./references/robust.md
|   +-- vcovNW() from plm
+-- Driscoll-Kraay --> ./references/robust.md
|   +-- vcovSCC() from plm
+-- Bootstrap --> sandwich::vcovBS
```

### "I need panel diagnostics"

```
What diagnostic?
+-- FE vs RE decision --> ./references/diagnostics.md
|   +-- Hausman test: phtest()
+-- Serial correlation --> ./references/diagnostics.md
|   +-- Breusch-Godfrey: pbgtest()
|   +-- Breusch-Pagan LM: plmtest()
+-- Cross-sectional dependence --> ./references/diagnostics.md
|   +-- Pesaran CD: pcdtest()
+-- Unit root (stationarity) --> ./references/diagnostics.md
|   +-- purtest() (Levin-Lin-Chu, Im-Pesaran-Shin, etc.)
|   +-- cipstest() (Pesaran CIPS)
+-- Poolability (F-test for FE) --> ./references/diagnostics.md
|   +-- pooltest()
```

### "Something isn't working"

```
Having issues?
+-- Error about pdata.frame or index --> ./references/gotchas.md
+-- Hausman test gives warnings --> ./references/gotchas.md
+-- Results differ from fixest --> ./references/gotchas.md
+-- Unbalanced panel handling --> ./references/gotchas.md
+-- Want to compare with linearmodels (Python) --> ./references/gotchas.md
+-- plm vs fixest: which to use? --> ./references/gotchas.md
```

## File-First Execution in Research Workflows

**Important:** In DAAF research pipelines, plm regressions are executed through
**script files**, not interactively. This ensures auditability and reproducibility.

**The pattern:**
1. Write regression code to `scripts/stage8_analysis/{step}_{task-name}.R`
2. Execute via Bash with automatic output capture wrapper script
3. Validation results get automatically embedded in scripts as comments
4. If failed, create versioned copy for fixes

Closely read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the mandatory
file-first execution protocol covering complete code file writing, output capture,
and file versioning rules. All regression scripts must follow the Inline Audit
Trail (IAT) standard -- see `agent_reference/INLINE_AUDIT_TRAIL.md`. For regression
code, document model specification choices (why this estimator, why this clustering
level, what identifying assumptions) with `# INTENT:`, `# REASONING:`, and
`# ASSUMES:` comments.

**See:**
- `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` -- Stage 8 (Analysis & Visualization)
- `agent_reference/INLINE_AUDIT_TRAIL.md` -- IAT documentation standard

The examples below show plm syntax. In research workflows, wrap them in scripts
following the file-first pattern.

---

## Quick Reference

### Essential Setup

```r
library(plm)
library(estimatr)    # lm_robust, iv_robust
library(lme4)        # lmer, glmer
library(lmtest)      # coeftest with custom vcov
library(arrow)       # For parquet I/O (DAAF convention)
```

### Data Setup (pdata.frame)

```r
# Declare panel structure -- entity and time identifiers
pdf <- pdata.frame(df, index = c("entity_id", "year"))

# Verify
pdim(pdf)            # Panel dimensions
is.pbalanced(pdf)    # Check balance
```

### Core Operations

| Operation | Code |
|-----------|------|
| Panel FE (within) | `plm(y ~ x1 + x2, data = pdf, model = "within")` |
| Two-way FE | `plm(y ~ x1 + x2, data = pdf, model = "within", effect = "twoways")` |
| Random effects | `plm(y ~ x1 + x2, data = pdf, model = "random")` |
| Between | `plm(y ~ x1 + x2, data = pdf, model = "between")` |
| First difference | `plm(y ~ x1 + x2, data = pdf, model = "fd")` |
| Pooled OLS | `plm(y ~ x1 + x2, data = pdf, model = "pooling")` |
| Panel IV | `plm(y ~ x1 + x2 \| z1 + z2, data = pdf, model = "within")` |
| Hausman test | `phtest(fe_fit, re_fit)` |
| Robust SEs | `coeftest(fit, vcov = vcovHC(fit, type = "HC1"))` |
| Clustered SEs | `coeftest(fit, vcov = vcovHC(fit, cluster = "group"))` |
| Driscoll-Kraay | `coeftest(fit, vcov = vcovSCC(fit))` |
| Summary | `summary(fit)` |
| Dynamic GMM | `pgmm(y ~ lag(y, 1) + x1 \| lag(y, 2:99), data = pdf)` |

### Formula Syntax

```r
# Standard panel formula
y ~ x1 + x2

# Panel IV: instruments after |
y ~ x1 + x_endog | z1 + z2 + x1

# Interactions
y ~ x1 * x2          # x1 + x2 + x1:x2

# Transformations
y ~ log(x1) + I(x2^2)

# Suppress intercept (for within estimator, intercept is absorbed anyway)
y ~ x1 + x2 - 1
```

### Post-Estimation

```r
fit <- plm(y ~ x1 + x2, data = pdf, model = "within")

summary(fit)                          # Full summary
coef(fit)                             # Coefficients
vcov(fit)                             # Variance-covariance matrix
fixef(fit)                            # Fixed effects estimates
pFtest(fit, plm(y ~ x1 + x2, data = pdf, model = "pooling"))  # F-test for FE
within_intercept(fit)                 # Overall intercept for within model
broom::tidy(fit, conf.int = TRUE)     # Tidy output
broom::glance(fit)                    # Model-level statistics
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| pdata.frame setup | `./references/quickstart.md` |
| plm() basics | `./references/quickstart.md` |
| model= argument | `./references/quickstart.md` |
| summary() output | `./references/quickstart.md` |
| pdim(), is.pbalanced() | `./references/quickstart.md` |
| Comparison to linearmodels (Python) | `./references/quickstart.md` |
| Within (FE) estimator | `./references/models.md` |
| Random effects (RE) | `./references/models.md` |
| Between estimator | `./references/models.md` |
| First difference (FD) | `./references/models.md` |
| Pooled OLS | `./references/models.md` |
| Fama-MacBeth (pmg) | `./references/models.md` |
| Two-way effects | `./references/models.md` |
| Model comparison | `./references/models.md` |
| Weighted estimation | `./references/models.md` |
| Hausman test (phtest) | `./references/diagnostics.md` |
| Poolability F-test | `./references/diagnostics.md` |
| Serial correlation tests | `./references/diagnostics.md` |
| Cross-sectional dependence | `./references/diagnostics.md` |
| Panel unit root tests | `./references/diagnostics.md` |
| Panel IV (plm instruments) | `./references/iv.md` |
| Sargan/Hansen test | `./references/iv.md` |
| Dynamic GMM (pgmm) | `./references/iv.md` |
| Arellano-Bond test | `./references/iv.md` |
| vcovHC (heteroskedasticity-robust) | `./references/robust.md` |
| Clustered SEs | `./references/robust.md` |
| Newey-West (vcovNW) | `./references/robust.md` |
| Driscoll-Kraay (vcovSCC) | `./references/robust.md` |
| estimatr lm_robust | `./references/robust.md` |
| estimatr iv_robust | `./references/robust.md` |
| lme4 lmer | `./references/mixed-effects.md` |
| lme4 glmer | `./references/mixed-effects.md` |
| Random intercepts/slopes | `./references/mixed-effects.md` |
| ICC (intraclass correlation) | `./references/mixed-effects.md` |
| Conditional vs marginal effects | `./references/mixed-effects.md` |
| pdata.frame requirements | `./references/gotchas.md` |
| Unbalanced panels | `./references/gotchas.md` |
| FE vs RE choice | `./references/gotchas.md` |
| fixest vs plm routing | `./references/gotchas.md` |
| linearmodels vs plm comparison | `./references/gotchas.md` |

## Citation

When plm is used as a primary analytical tool, include in the report's
Software & Tools references:

> Croissant, Y. & Millo, G. (2008). "Panel Data Econometrics in R: The plm
> Package." Journal of Statistical Software, 27(2), 1-43.

For estimatr:

> Blair, G., Cooper, J., Coppock, A., Humphreys, M., & Sonnet, L. (2022).
> estimatr: Fast Estimators for Design-Based Inference. R package.
> https://CRAN.R-project.org/package=estimatr

For lme4:

> Bates, D., Machler, M., Bolker, B., & Walker, S. (2015). "Fitting Linear
> Mixed-Effects Models Using lme4." Journal of Statistical Software, 67(1),
> 1-48.

**Cite when:** plm is used for panel estimation (FE, RE, between, FD),
Hausman testing, or panel diagnostics. Cite estimatr when HC/CR SEs are the
primary inference approach. Cite lme4 when mixed-effects models are estimated.
**Do not cite when:** Only loaded but no estimation performed.

For method-specific citations (e.g., individual estimators or techniques),
consult the reference files in this skill and `agent_reference/CITATION_REFERENCE.md`.
