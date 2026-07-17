# survey Regression Reference

survey 4.5 on R 4.5.3 -- syntax and library guidance only.

---

## Contents

1. [Overview: svyglm()](#overview-svyglm)
2. [Survey-Weighted Linear Regression](#survey-weighted-linear-regression)
3. [Survey-Weighted Logistic Regression](#survey-weighted-logistic-regression)
4. [Survey-Weighted Poisson Regression](#survey-weighted-poisson-regression)
5. [Ordinal Logistic Regression (svyolr)](#ordinal-logistic-regression-svyolr)
6. [Cox Proportional Hazards (svycoxph)](#cox-proportional-hazards-svycoxph)
7. [Extracting Results](#extracting-results)
8. [Model Comparison](#model-comparison)
9. [Marginal Effects Without emmeans](#marginal-effects-without-emmeans)
10. [Survey Regression vs. WLS vs. Cluster-Robust SEs](#survey-regression-vs-wls-vs-cluster-robust-ses)
11. [Domain-Specific Regression](#domain-specific-regression)
12. [Complete Regression Workflow](#complete-regression-workflow)

---

## Overview: svyglm()

`svyglm()` fits generalized linear models that account for the complex survey
design in both point estimation and variance estimation. It is the R analog of
Python's `svy.Sample.glm.fit()`.

```r
fit <- svyglm(
  formula = y ~ x1 + x2 + factor(x3),
  design = des,
  family = gaussian()        # or quasibinomial(), quasipoisson()
)
summary(fit)
```

### Supported Families

| Family | Use Case | R Code |
|--------|----------|--------|
| Gaussian | Continuous outcome (linear regression) | `gaussian()` |
| Quasi-binomial | Binary outcome (logistic regression) | `quasibinomial()` |
| Quasi-Poisson | Count outcome (Poisson regression) | `quasipoisson()` |
| Gamma | Positive continuous, right-skewed | `Gamma(link = "log")` |
| Inverse Gaussian | Positive continuous | `inverse.gaussian()` |

### Why Quasi-Families?

Use `quasibinomial()` and `quasipoisson()` instead of `binomial()` and
`poisson()` for survey-weighted regression. The quasi-families suppress
warnings about non-integer successes and non-integer counts that arise from
weighted data. Point estimates are identical; only the internal scaling differs.

```r
# Preferred: quasibinomial suppresses spurious warnings
fit <- svyglm(y ~ x1 + x2, design = des, family = quasibinomial())

# Works but produces warnings about non-integer successes
# fit <- svyglm(y ~ x1 + x2, design = des, family = binomial())
```

### Models NOT in svyglm() (Use Dedicated Functions)

| Model | Function | Notes |
|-------|----------|-------|
| Ordinal logistic | `svyolr()` | See section below |
| Cox proportional hazards | `svycoxph()` | See section below |
| Negative binomial | No direct equivalent | Use `quasipoisson()` or base `MASS::glm.nb()` without design |
| Multinomial logistic | Not available | Consider alternatives or `nnet::multinom()` without design |

---

## Survey-Weighted Linear Regression

### Basic Linear Model

```r
# INTENT: Estimate association between age and BMI, controlling for gender
# REASONING: Gaussian family for continuous outcome with design-based SEs
# ASSUMES: Linear relationship; additive effects
fit <- svyglm(
  bmxbmi ~ ridageyr + factor(riagendr),
  design = des,
  family = gaussian()
)
summary(fit)
```

### Multiple Continuous Predictors

```r
fit <- svyglm(
  bmxbmi ~ ridageyr + indfmpir + lbxtc,
  design = des,
  family = gaussian()
)
```

### Interactions

```r
# Full interaction (main effects + interaction)
fit <- svyglm(y ~ x1 * factor(group), design = des)

# Interaction only
fit <- svyglm(y ~ x1 + factor(group) + x1:factor(group), design = des)

# Polynomial (protect arithmetic with I())
fit <- svyglm(y ~ x1 + I(x1^2), design = des)
```

### Interpreting Linear Model Output

Coefficients are interpreted the same as OLS:
- Each coefficient = expected change in Y for a one-unit change in X
- The intercept = expected Y when all predictors are zero
- SEs and p-values reflect the complex survey design, not SRS assumptions
- Degrees of freedom are design-based (PSUs - strata), which can affect p-values

---

## Survey-Weighted Logistic Regression

### Basic Logistic Model

```r
# INTENT: Model probability of obesity as a function of demographics
# REASONING: Binary outcome requires logistic regression; quasibinomial
#   avoids warnings from weighted data
# ASSUMES: Outcome coded 0/1
fit <- svyglm(
  obese_flag ~ ridageyr + indfmpir + factor(riagendr) + factor(ridreth1),
  design = des,
  family = quasibinomial()
)
summary(fit)
```

### Odds Ratios

```r
# Coefficients are on the log-odds scale
# Exponentiate for odds ratios
exp(coef(fit))

# Exponentiated CIs
exp(confint(fit))

# Combined table
cbind(
  OR = exp(coef(fit)),
  exp(confint(fit))
)
```

### Using broom for Odds Ratios

```r
library(broom)
tidy(fit, conf.int = TRUE, exponentiate = TRUE)
```

---

## Survey-Weighted Poisson Regression

### Basic Poisson Model

```r
# INTENT: Model count of doctor visits
# REASONING: Count outcome suits Poisson; quasipoisson for weighted data
# ASSUMES: Conditional mean ~ conditional variance (Poisson assumption)
fit <- svyglm(
  doctor_visits ~ ridageyr + factor(health_status) + factor(insurance),
  design = des,
  family = quasipoisson()
)
summary(fit)
```

### Incidence Rate Ratios

```r
# Exponentiate coefficients for IRRs
exp(coef(fit))
exp(confint(fit))

# Or via broom
broom::tidy(fit, conf.int = TRUE, exponentiate = TRUE)
```

### Overdispersion

Survey-weighted Poisson regression using `quasipoisson()` implicitly accounts
for overdispersion through the quasi-likelihood scale parameter. For severe
overdispersion, the sandwich SEs from the design-based approach provide
additional robustness.

---

## Ordinal Logistic Regression (svyolr)

`svyolr()` fits proportional-odds logistic regression for ordered categorical
outcomes. This is NOT available in Python's `svy` package.

```r
# Ordered outcome variable
data$health_ordered <- ordered(data$health_status,
                                levels = c("Poor", "Fair", "Good", "Excellent"))

fit <- svyolr(health_ordered ~ age + income + factor(gender), design = des)
summary(fit)
```

### Interpreting svyolr Output

- Coefficients are log-odds of being in a higher category vs. lower
- Positive coefficient = higher odds of better health for a one-unit increase
- The proportional-odds assumption: the coefficient is the same across all cut
  points (parallel slopes)
- Intercepts (thresholds) define the cut points between categories

---

## Cox Proportional Hazards (svycoxph)

`svycoxph()` fits survey-weighted Cox PH models for survival analysis. Also NOT
available in Python's `svy` package.

```r
library(survival)

fit <- svycoxph(Surv(time, event) ~ age + treatment + factor(stage),
                design = des)
summary(fit)
```

### Interpreting Cox PH Output

- Coefficients are log-hazard ratios
- Exponentiate for hazard ratios: `exp(coef(fit))`
- HR > 1: higher hazard (worse survival) for a one-unit increase
- HR < 1: lower hazard (better survival) for a one-unit increase

---

## Extracting Results

### summary() Output

```r
fit <- svyglm(income ~ age + factor(gender), design = des)
s <- summary(fit)

# Coefficient table
s$coefficients   # estimate, SE, t-value, p-value

# Individual components
coef(fit)        # point estimates
confint(fit)     # 95% CI
vcov(fit)        # variance-covariance matrix
```

### Using broom

```r
library(broom)

# Coefficient-level results
tidy(fit, conf.int = TRUE)
# Columns: term, estimate, std.error, statistic, p.value, conf.low, conf.high

# Model-level results
glance(fit)
# Columns: null.deviance, df.null, AIC, BIC, deviance, df.residual, nobs

# Observation-level results (fitted values, residuals)
augment(fit)
```

### Predictions

```r
# Predicted values for existing data
fitted_values <- predict(fit)

# Predictions for new data
new_df <- data.frame(age = c(25, 45, 65), gender = c(1, 1, 2))
preds <- predict(fit, newdata = new_df)

# Predictions with SEs
preds_se <- predict(fit, newdata = new_df, se.fit = TRUE)
preds_se$fit     # predictions
preds_se$se.fit  # standard errors

# For logistic: get predicted probabilities
fit_logit <- svyglm(y ~ x, design = des, family = quasibinomial())
predict(fit_logit, type = "response")  # probabilities
predict(fit_logit, type = "link")      # log-odds
```

---

## Model Comparison

### Using update() for Nested Models

```r
# Base model
fit1 <- svyglm(income ~ age + factor(gender), design = des)

# Add education
fit2 <- update(fit1, . ~ . + factor(education))

# Add interaction
fit3 <- update(fit2, . ~ . + age:factor(gender))
```

### Wald Tests for Nested Models (regTermTest)

```r
# Test whether a group of terms is jointly significant
# Equivalent to car::linearHypothesis but designed for survey models
regTermTest(fit2, ~factor(education))

# Compare nested models via the difference in coefficients
anova(fit1, fit2)
```

### AIC/BIC Comparison

```r
# AIC and BIC from glance()
library(broom)
glance(fit1)$AIC
glance(fit2)$AIC
```

AIC/BIC from survey GLMs should be compared cautiously -- they are based on
quasi-likelihood, not full likelihood. Use Wald tests (`regTermTest()`) as the
primary tool for model comparison.

---

## Marginal Effects Without emmeans

Since `emmeans` is NOT installed, use these alternative approaches for marginal
effects and predicted means.

### Approach 1: Manual Predicted Means via predict()

```r
fit <- svyglm(income ~ age + factor(education), design = des)

# Create prediction data at each education level, holding age at mean
mean_age <- coef(svymean(~age, design = des))
pred_data <- data.frame(
  age = rep(mean_age, 3),
  education = factor(c("HS", "BA", "MA"))
)

# Predicted means with SEs
preds <- predict(fit, newdata = pred_data, se.fit = TRUE)
result <- data.frame(
  education = pred_data$education,
  predicted_mean = preds$fit,
  se = preds$se.fit,
  ci_low = preds$fit - 1.96 * preds$se.fit,
  ci_high = preds$fit + 1.96 * preds$se.fit
)
print(result)
```

### Approach 2: svycontrast() for Pairwise Differences

```r
# After getting predicted means, use svycontrast for differences
fit <- svyglm(income ~ factor(education), design = des)

# Coefficients are: intercept (= HS mean), BA-HS diff, MA-HS diff
# Pairwise: BA vs MA = (BA-HS) - (MA-HS)
svycontrast(fit, list(
  ba_vs_hs = c(0, 1, 0),
  ma_vs_hs = c(0, 0, 1),
  ma_vs_ba = c(0, -1, 1)
))
```

### Approach 3: Average Marginal Effects via Manual Computation

```r
# For continuous predictors in a logistic model
fit <- svyglm(y ~ age + income, design = des, family = quasibinomial())

# Compute predicted probabilities at observed values
p_hat <- predict(fit, type = "response")

# Average marginal effect of age:
# AME = mean(beta_age * p_hat * (1 - p_hat))
beta_age <- coef(fit)["age"]
ame_age <- mean(beta_age * p_hat * (1 - p_hat))
cat("AME of age:", round(ame_age, 5), "\n")
```

This is an approximation -- for delta-method SEs on AMEs, `marginaleffects`
supports `svyglm` objects and propagates the survey design's variance. Verify
that the design is carried through as expected for your specification, and
document the approximation with an `# ASSUMES:` comment.

---

## Survey Regression vs. WLS vs. Cluster-Robust SEs

This distinction is critical and parallels the same issue in Python (see `svy`
skill `regression.md`).

### 1. Survey-Weighted Regression (survey::svyglm)

```r
# Accounts for strata, PSU, and unequal selection probabilities
des <- svydesign(ids = ~psu, strata = ~strat, weights = ~wt, data = df,
                  nest = TRUE)
fit <- svyglm(y ~ x1 + x2, design = des)
```

**What it does:** Uses weights in point estimation + full design (strata + PSU +
weights) for variance estimation. Design-based degrees of freedom.

### 2. Weighted Least Squares (base R lm with weights)

```r
# Uses weights for point estimates ONLY -- NOT survey-aware
fit <- lm(y ~ x1 + x2, data = df, weights = wt)
```

**What it does:** Weights in point estimation only. Does NOT account for
stratification or clustering. Assumes independent observations. Produces
**incorrect SEs for survey data** -- typically too small.

### 3. Cluster-Robust SEs (sandwich::vcovCL)

```r
# Accounts for clustering only -- NOT full survey design
fit <- lm(y ~ x1 + x2, data = df)
coeftest(fit, vcov = vcovCL(fit, cluster = df$psu))
```

**What it does:** Accounts for within-cluster correlation. Does NOT use survey
weights and does NOT account for stratification. Large-sample approximation.

### Summary

| Aspect | svyglm | lm(weights=) | vcovCL |
|--------|--------|--------------|--------|
| Weights in estimates | Yes | Yes | No |
| Stratification in SE | Yes | No | No |
| Clustering in SE | Yes | No | Yes |
| Unequal selection in SE | Yes | No | No |
| Degrees of freedom | Design-based | Model-based | Large-sample |
| Correct for surveys | **Yes** | **No** | **No** |

**If you have survey data with design variables, use `svyglm()`.** There is no
shortcut.

---

## Domain-Specific Regression

To fit a regression within a subpopulation, use `subset()` on the design object.

```r
# CORRECT: subset the design object (preserves full design structure)
des_female <- subset(des, gender == "Female")
fit <- svyglm(income ~ age + education, design = des_female)

# WRONG: filter the data and create a new design
# females <- df[df$gender == "Female", ]
# des_f <- svydesign(ids = ~psu, strata = ~strat, weights = ~wt,
#                     data = females)
# svyglm(income ~ age, design = des_f)  # <-- WRONG SEs
```

`subset()` on the design object preserves the full sampling structure for
variance estimation while restricting the model to the subpopulation.

---

## Complete Regression Workflow

```r
# --- Config ---
library(survey)
library(broom)
library(arrow)

# --- Load ---
data <- read_parquet("data/raw/2026-05-08_nhanes_demo_exam.parquet")
cat("Loaded", nrow(data), "rows,", ncol(data), "columns\n")

# --- Design ---
# INTENT: NHANES 2017-2020 complex multi-stage probability design
# REASONING: sdmvstra/sdmvpsu are masked design variables; wtmec2yr is the
#   MEC exam weight appropriate for variables collected during examination
# ASSUMES: Analysis restricted to MEC-examined participants aged 20+
des <- svydesign(
  ids = ~sdmvpsu,
  strata = ~sdmvstra,
  weights = ~wtmec2yr,
  data = data,
  nest = TRUE
)

# Subset to adults
des_adult <- subset(des, ridageyr >= 20)

# --- Analysis ---
# INTENT: Estimate association between demographics and BMI
# REASONING: Gaussian family for continuous outcome; design-based SEs
# ASSUMES: Linear in parameters; additive effects
fit <- svyglm(
  bmxbmi ~ ridageyr + I(ridageyr^2) + indfmpir +
    factor(riagendr) + factor(ridreth1),
  design = des_adult,
  family = gaussian()
)

# --- Results ---
cat("\n--- Model Summary ---\n")
print(summary(fit))

# Tidy output
tidy_df <- tidy(fit, conf.int = TRUE)
cat("\n--- Tidy Coefficients ---\n")
print(tidy_df)

# Model statistics
glance_df <- glance(fit)
cat("\nN:", glance_df$nobs, "\n")
cat("AIC:", round(glance_df$AIC, 2), "\n")

# --- Validate ---
cat("\nInput data rows:", nrow(data), "\n")
cat("Design df:", degf(des_adult), "\n")
stopifnot(nrow(data) > 0)
stopifnot(all(!is.na(coef(fit))))
```
