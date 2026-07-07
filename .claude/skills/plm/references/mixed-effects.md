# Mixed-Effects Models (lme4)

Reference for mixed-effects (multilevel/hierarchical) models using lme4.
Covers random intercepts, random slopes, crossed and nested random effects,
and the distinction between conditional and marginal effects.

## Contents

- [When to Use Mixed Effects vs Fixed Effects](#when-to-use-mixed-effects-vs-fixed-effects)
- [lmer -- Linear Mixed-Effects Models](#lmer----linear-mixed-effects-models)
- [Formula Syntax](#formula-syntax)
- [Random Intercepts](#random-intercepts)
- [Random Slopes](#random-slopes)
- [Nested and Crossed Random Effects](#nested-and-crossed-random-effects)
- [Post-Estimation](#post-estimation)
- [ICC (Intraclass Correlation)](#icc-intraclass-correlation)
- [glmer -- Generalized Linear Mixed Models](#glmer----generalized-linear-mixed-models)
- [Conditional vs Marginal Effects](#conditional-vs-marginal-effects)
- [Convergence Issues](#convergence-issues)
- [Comparison with plm RE and fixest](#comparison-with-plm-re-and-fixest)
- [References](#references)

---

## When to Use Mixed Effects vs Fixed Effects

| Feature | plm RE | lme4 lmer | fixest feols |
|---------|--------|-----------|-------------|
| Entity effects | Random (GLS) | Random (ML/REML) | Fixed (absorbed) |
| Random slopes | No | Yes | Varying slopes (`[x]` syntax) |
| Nested groups | No | Yes | Via `^` interaction |
| Non-normal outcomes | No | glmer() | fepois/feglm |
| Hausman-testable | Yes (vs FE) | No (different framework) | N/A |
| Shrinkage/BLUPs | No | Yes (ranef()) | No |
| Cross-classified | No | Yes | Via multiple FE |

**Use lme4 when:**
- You need random slopes (coefficient heterogeneity across groups)
- The grouping structure is nested (e.g., students in schools in districts)
- You want shrinkage estimates (BLUPs) for group-level effects
- The outcome is non-normal (glmer for logit, Poisson, etc.)
- The groups are a sample from a population (inference about population variance)

**Use plm RE when:**
- Classic econometric random effects model with Hausman testing
- Simple panel structure (entity + time)
- You want to compare with FE via phtest()

**Use fixest when:**
- You want fixed effects (absorbed, not estimated)
- Speed matters (faster for large data)
- High-dimensional grouping variables

---

## lmer -- Linear Mixed-Effects Models

```r
library(lme4)

# Random intercept by entity
fit <- lmer(y ~ x1 + x2 + (1 | entity_id), data = df)
summary(fit)
```

### ML vs REML

```r
# REML (default) -- unbiased variance estimates
fit_reml <- lmer(y ~ x1 + (1 | entity), data = df, REML = TRUE)

# ML -- needed for likelihood ratio tests comparing models with
# different fixed effects
fit_ml <- lmer(y ~ x1 + (1 | entity), data = df, REML = FALSE)

# Compare nested models (use ML, not REML, for fixed-effect comparisons)
fit1 <- lmer(y ~ x1 + (1 | entity), data = df, REML = FALSE)
fit2 <- lmer(y ~ x1 + x2 + (1 | entity), data = df, REML = FALSE)
anova(fit1, fit2)
```

---

## Formula Syntax

lme4 uses a bar (`|`) to separate random effects from grouping factors:

```r
# (random_effects | grouping_variable)

# Random intercept
y ~ x1 + x2 + (1 | group)

# Random intercept + random slope for x1
y ~ x1 + x2 + (1 + x1 | group)

# Random slope only (suppress random intercept)
y ~ x1 + x2 + (0 + x1 | group)

# Uncorrelated random intercept and slope
y ~ x1 + x2 + (1 | group) + (0 + x1 | group)

# Nested random effects (students in schools)
y ~ x1 + (1 | school/student)
# Equivalent to: y ~ x1 + (1 | school) + (1 | school:student)

# Crossed random effects (items crossed with subjects)
y ~ x1 + (1 | subject) + (1 | item)
```

---

## Random Intercepts

The simplest mixed model: each group gets its own intercept, drawn from a
normal distribution.

```r
library(lme4)

# Random intercept by school
fit_ri <- lmer(score ~ ses + (1 | school_id), data = df)
summary(fit_ri)

# Extract random effects (BLUPs)
ranef(fit_ri)

# Predicted group intercepts (fixed intercept + random deviation)
coef(fit_ri)
```

### Interpreting Output

```r
summary(fit_ri)
# Random effects:
#  Groups    Name        Variance Std.Dev.
#  school_id (Intercept) 25.3     5.03      <-- between-school variance
#  Residual              100.2    10.01     <-- within-school variance
#
# Fixed effects:
#             Estimate Std. Error t value
# (Intercept) 50.123   2.345      21.37
# ses          3.456   0.789       4.38
```

---

## Random Slopes

Allow the effect of a predictor to vary across groups.

```r
# Random intercept + random slope for ses
fit_rs <- lmer(score ~ ses + (1 + ses | school_id), data = df)
summary(fit_rs)

# The (1 + ses | school_id) means:
# - Each school gets its own intercept
# - Each school gets its own ses slope
# - The intercept and slope are correlated (estimated correlation)
```

### Uncorrelated Random Effects

```r
# If you want separate (uncorrelated) random intercept and slope:
fit_uncor <- lmer(score ~ ses + (1 | school_id) + (0 + ses | school_id),
                  data = df)
# This estimates var(intercept), var(slope), but NOT their correlation
```

---

## Nested and Crossed Random Effects

### Nested (Hierarchical)

```r
# Students nested within schools within districts
fit_nest <- lmer(score ~ ses + (1 | district/school/student), data = df)
# Equivalent to:
# lmer(score ~ ses + (1 | district) + (1 | district:school) +
#                     (1 | district:school:student), data = df)
```

### Crossed

```r
# Subjects and items are crossed (not nested)
fit_cross <- lmer(rt ~ condition + (1 | subject) + (1 | item), data = df)
```

---

## Post-Estimation

```r
fit <- lmer(y ~ x1 + x2 + (1 + x1 | group), data = df)

# Fixed effects
fixef(fit)                          # Fixed effect estimates
summary(fit)$coefficients           # Coef table with SEs

# Random effects
ranef(fit)                          # BLUPs (conditional modes)
VarCorr(fit)                        # Variance components

# Group-specific coefficients (fixed + random)
coef(fit)

# Predictions
predict(fit)                        # Conditional (includes random effects)
predict(fit, re.form = NA)          # Marginal (fixed effects only)

# Confidence intervals
confint(fit, method = "Wald")       # Wald-based (fast)
confint(fit, method = "profile")    # Profile likelihood (more accurate)

# Tidy output
broom.mixed::tidy(fit)              # Tidy coefficients
broom.mixed::glance(fit)            # Model-level statistics
broom.mixed::augment(fit)           # Observation-level diagnostics
```

### Inference (p-values)

lme4 deliberately does not provide p-values for fixed effects because the
degrees of freedom for mixed models are not well-defined. Common approaches:

```r
# 1. Satterthwaite approximation (lmerTest)
library(lmerTest)
fit <- lmer(y ~ x1 + (1 | group), data = df)
summary(fit)  # Now includes p-values

# 2. Kenward-Roger approximation
anova(fit, ddf = "Kenward-Roger")

# 3. Likelihood ratio test (compare nested models, use ML)
fit0 <- lmer(y ~ 1 + (1 | group), data = df, REML = FALSE)
fit1 <- lmer(y ~ x1 + (1 | group), data = df, REML = FALSE)
anova(fit0, fit1)
```

---

## ICC (Intraclass Correlation)

The ICC measures the proportion of total variance attributable to group
differences. High ICC means groups differ substantially.

```r
fit <- lmer(y ~ (1 | group), data = df)
vc <- as.data.frame(VarCorr(fit))

# Manual ICC calculation
var_group <- vc$vcov[vc$grp == "group"]
var_resid <- vc$vcov[vc$grp == "Residual"]
icc <- var_group / (var_group + var_resid)
cat("ICC:", round(icc, 3), "\n")

# Or use performance package
# library(performance)
# icc(fit)
```

### Interpreting ICC

| ICC Range | Interpretation |
|-----------|---------------|
| < 0.05 | Negligible group effect; pooled OLS may suffice |
| 0.05 - 0.20 | Moderate; mixed model recommended |
| > 0.20 | Strong group effect; mixed model essential |

---

## glmer -- Generalized Linear Mixed Models

For non-normal outcomes (binary, count, etc.):

```r
library(lme4)

# Logistic mixed model (binary outcome)
fit_logit <- glmer(pass ~ ses + (1 | school_id),
                   data = df, family = binomial)
summary(fit_logit)

# Poisson mixed model (count outcome)
fit_pois <- glmer(count ~ x1 + (1 | group),
                  data = df, family = poisson)

# Negative binomial (via MASS::glm.nb link or lme4 nAGQ)
# lme4 does not natively support negative binomial
# Use glmmTMB package instead:
# library(glmmTMB)
# fit_nb <- glmmTMB(count ~ x1 + (1 | group), family = nbinom2, data = df)
```

---

## Conditional vs Marginal Effects

Mixed models estimate **conditional** (subject-specific) effects. The
**marginal** (population-averaged) effect may differ, especially for
non-linear models.

```r
# Conditional predictions (includes random effects)
predict(fit, type = "response")

# Marginal predictions (fixed effects only, averaged over random effects)
predict(fit, re.form = NA, type = "response")
```

For GLMMs, marginal effects can be computed via:

```r
library(marginaleffects)

# Average marginal effects (integrates over random effects distribution)
avg_slopes(fit_logit)

# Predictions at specific values
avg_predictions(fit_logit, variables = list(ses = c(0, 1)))
```

---

## Convergence Issues

lme4 models can fail to converge, especially with complex random effect
structures.

### Common Solutions

```r
# 1. Scale predictors
df$x1_scaled <- scale(df$x1)
fit <- lmer(y ~ x1_scaled + (1 + x1_scaled | group), data = df)

# 2. Simplify random effects
# Start with random intercept, add slopes one at a time
fit1 <- lmer(y ~ x1 + x2 + (1 | group), data = df)
fit2 <- lmer(y ~ x1 + x2 + (1 + x1 | group), data = df)

# 3. Use different optimizer
fit <- lmer(y ~ x1 + (1 + x1 | group), data = df,
            control = lmerControl(optimizer = "bobyqa",
                                  optCtrl = list(maxfun = 100000)))

# 4. Remove correlation between random effects
fit <- lmer(y ~ x1 + (1 | group) + (0 + x1 | group), data = df)
```

### Singular Fit Warning

"boundary (singular) fit" means a variance component was estimated at
exactly zero. This usually means the random effect structure is too complex
for the data.

```r
# Check for singular fit
isSingular(fit)
# If TRUE: simplify the random effect structure
```

---

## Comparison with plm RE and fixest

| Feature | lme4 lmer | plm RE | fixest |
|---------|-----------|--------|--------|
| Estimation | ML/REML | GLS (Swamy-Arora etc.) | OLS + FE absorption |
| Random slopes | Yes | No | Varying slopes (`[x]`) |
| Shrinkage (BLUPs) | Yes | No | No |
| Nested groups | Yes (formula) | No | Via `^` interaction |
| GLM support | glmer() | No | feglm() |
| Hausman test | No | Yes (vs FE) | No |
| Speed (large N) | Moderate | Fast | Very fast |
| Panel diagnostics | No | Yes (phtest, pcdtest) | Limited |
| DiD/event study | No | No | Yes (sunab) |

---

## References

- Bates, D., Machler, M., Bolker, B., & Walker, S. (2015). "Fitting Linear
  Mixed-Effects Models Using lme4." Journal of Statistical Software, 67(1),
  1-48.
- Kuznetsova, A., Brockhoff, P.B., & Christensen, R.H.B. (2017). "lmerTest
  Package: Tests in Linear Mixed Effects Models." Journal of Statistical
  Software, 82(13), 1-26.
- Barr, D.J., Levy, R., Scheepers, C., & Tily, H.J. (2013). "Random Effects
  Structure for Confirmatory Hypothesis Testing: Keep It Maximal." Journal of
  Memory and Language, 68(3), 255-278.
