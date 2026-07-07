# R Stats GLM Reference

Generalized linear models in R: `glm()` family/link specifications, `MASS::glm.nb()`
for negative binomial, `MASS::polr()` for ordered logit/probit, deviance diagnostics,
overdispersion, and coefficient interpretation. R 4.5.3.

---

## Contents

- [GLM Framework](#glm-framework)
- [Logit and Probit](#logit-and-probit)
- [Poisson Regression](#poisson-regression)
- [Negative Binomial (MASS)](#negative-binomial-mass)
- [Gamma Regression](#gamma-regression)
- [Ordered Logit and Probit (MASS)](#ordered-logit-and-probit-mass)
- [Deviance and Model Fit](#deviance-and-model-fit)
- [Overdispersion](#overdispersion)
- [Prediction from GLMs](#prediction-from-glms)
- [Coefficient Interpretation](#coefficient-interpretation)

---

## GLM Framework

```r
# General syntax
fit <- glm(y ~ x1 + x2, data = df, family = family_spec)
summary(fit)
```

### Family Specifications

| Family | Default Link | R Code | Use For |
|--------|--------------|--------|---------|
| Gaussian | Identity | `gaussian` or `gaussian()` | Continuous outcomes (same as lm) |
| Binomial | Logit | `binomial` or `binomial()` | Binary (0/1), proportions |
| Poisson | Log | `poisson` or `poisson()` | Count data |
| Gamma | Inverse | `Gamma` or `Gamma()` | Positive continuous, right-skewed |
| Inverse Gaussian | 1/mu^2 | `inverse.gaussian()` | Positive continuous, highly skewed |
| Quasi | varies | `quasi()` | Custom mean-variance relationships |
| Quasi-binomial | Logit | `quasibinomial()` | Overdispersed binary data |
| Quasi-Poisson | Log | `quasipoisson()` | Overdispersed count data |

### Specifying Non-Default Links

```r
# Probit link with binomial family
fit <- glm(y ~ x1, data = df, family = binomial(link = "probit"))

# Complementary log-log link
fit <- glm(y ~ x1, data = df, family = binomial(link = "cloglog"))

# Log link with Gaussian family (log-linear model)
fit <- glm(y ~ x1, data = df, family = gaussian(link = "log"))

# Log link with Gamma family
fit <- glm(y ~ x1, data = df, family = Gamma(link = "log"))

# Identity link with Poisson (linear Poisson)
fit <- glm(y ~ x1, data = df, family = poisson(link = "identity"))
```

### Available Link Functions

| Link | Function g(mu) | Available For |
|------|---------------|---------------|
| `"identity"` | mu | Gaussian, Poisson, Gamma |
| `"log"` | log(mu) | Poisson, Gamma, Gaussian, Inverse Gaussian |
| `"logit"` | log(mu/(1-mu)) | Binomial |
| `"probit"` | qnorm(mu) | Binomial |
| `"cloglog"` | log(-log(1-mu)) | Binomial |
| `"inverse"` | 1/mu | Gamma, Gaussian |
| `"1/mu^2"` | 1/mu^2 | Inverse Gaussian |
| `"sqrt"` | sqrt(mu) | Poisson |

---

## Logit and Probit

### Logistic Regression (Logit)

```r
# Binary outcome coded as 0/1
fit_logit <- glm(y ~ x1 + x2, data = df, family = binomial)
summary(fit_logit)

# Equivalent explicit syntax
fit_logit <- glm(y ~ x1 + x2, data = df, family = binomial(link = "logit"))
```

### Probit Regression

```r
fit_probit <- glm(y ~ x1 + x2, data = df, family = binomial(link = "probit"))
summary(fit_probit)
```

### Odds Ratios (Logit Only)

Logit coefficients are log-odds. Exponentiate for odds ratios:

```r
# Odds ratios with 95% CI
or_table <- cbind(
  OR = exp(coef(fit_logit)),
  exp(confint(fit_logit))
)
cat("Odds Ratios:\n")
print(round(or_table, 3))

# Using broom
library(broom)
tidy(fit_logit, conf.int = TRUE, exponentiate = TRUE)
# exponentiate = TRUE converts to odds ratios automatically
```

### Predicted Probabilities

```r
# In-sample predicted probabilities
fitted(fit_logit)   # probabilities (response scale)

# Out-of-sample
predict(fit_logit, newdata = new_df, type = "response")  # probabilities
predict(fit_logit, newdata = new_df, type = "link")       # log-odds (linear predictor)
```

The `type` argument is critical -- see the Gotchas reference for details.

### Pseudo R-squared

```r
# McFadden's pseudo R-squared
null_fit <- glm(y ~ 1, data = df, family = binomial)
pseudo_r2 <- 1 - logLik(fit_logit) / logLik(null_fit)
cat("McFadden's pseudo R-squared:", as.numeric(pseudo_r2), "\n")

# Values of 0.2-0.4 are considered good fit (lower than OLS R-squared)
```

### Confusion Matrix

```r
# Predicted classes at 0.5 threshold
pred_class <- ifelse(fitted(fit_logit) > 0.5, 1, 0)
conf_table <- table(Predicted = pred_class, Actual = df$y)
cat("Confusion matrix:\n")
print(conf_table)

accuracy <- sum(diag(conf_table)) / sum(conf_table)
cat("Accuracy:", round(accuracy, 3), "\n")
```

---

## Poisson Regression

```r
fit_pois <- glm(count ~ x1 + x2, data = df, family = poisson)
summary(fit_pois)
```

### Rate Models with Offset

When modeling event rates (events per unit of exposure):

```r
# Using offset (log of exposure)
fit_rate <- glm(events ~ x1 + x2, data = df, family = poisson,
                offset = log(person_years))

# Equivalent: exposure in the formula
fit_rate <- glm(events ~ x1 + x2 + offset(log(person_years)),
                data = df, family = poisson)
```

### Incidence Rate Ratios

```r
# IRR with 95% CI
irr_table <- cbind(
  IRR = exp(coef(fit_pois)),
  exp(confint(fit_pois))
)
cat("Incidence Rate Ratios:\n")
print(round(irr_table, 3))

# Using broom
tidy(fit_pois, conf.int = TRUE, exponentiate = TRUE)
```

---

## Negative Binomial (MASS)

For overdispersed counts where Var(y) > E(y):

```r
library(MASS)

# Fits NB2 parameterization: Var(y) = mu + mu^2/theta
fit_nb <- glm.nb(count ~ x1 + x2, data = df)
summary(fit_nb)

# Theta (dispersion parameter) -- larger = less overdispersion
# As theta -> infinity, NB approaches Poisson
cat("Theta:", fit_nb$theta, "\n")
cat("SE of theta:", fit_nb$SE.theta, "\n")
```

### Comparing Poisson vs Negative Binomial

```r
fit_pois <- glm(count ~ x1 + x2, data = df, family = poisson)
fit_nb <- glm.nb(count ~ x1 + x2, data = df)

# AIC comparison
cat("Poisson AIC:", AIC(fit_pois), "\n")
cat("NB AIC:     ", AIC(fit_nb), "\n")
# Lower AIC = better fit

# Likelihood ratio test (NB vs Poisson)
# H0: Poisson is adequate (theta -> infinity)
lr_stat <- 2 * (logLik(fit_nb) - logLik(fit_pois))
lr_pval <- pchisq(as.numeric(lr_stat), df = 1, lower.tail = FALSE) / 2
cat("LR test p-value:", lr_pval, "\n")
# Divide by 2 because theta is on the boundary under H0
```

---

## Gamma Regression

For positive continuous outcomes with variance proportional to the mean squared:

```r
# Log link (most common for Gamma)
fit_gamma <- glm(y ~ x1 + x2, data = df, family = Gamma(link = "log"))
summary(fit_gamma)

# Inverse link (default)
fit_gamma_inv <- glm(y ~ x1 + x2, data = df, family = Gamma)
```

Gamma regression is useful for:
- Cost/expenditure data (positive, right-skewed)
- Duration/waiting time data
- Insurance claims amounts

---

## Ordered Logit and Probit (MASS)

For ordinal outcomes (e.g., Likert scales, education levels):

```r
library(MASS)

# Ensure outcome is ordered factor
df$rating <- ordered(df$rating, levels = c("low", "medium", "high"))

# Ordered logit (proportional odds model)
fit_ord <- polr(rating ~ x1 + x2, data = df, method = "logistic")
summary(fit_ord)

# Ordered probit
fit_ord_p <- polr(rating ~ x1 + x2, data = df, method = "probit")

# Predicted probabilities for each category
pred_probs <- predict(fit_ord, type = "probs")
head(pred_probs)
# Returns matrix: n_obs x n_categories

# Predicted class
pred_class <- predict(fit_ord, type = "class")
```

`polr()` summary does not include p-values by default. Compute them:

```r
ctable <- coef(summary(fit_ord))
p_values <- pnorm(abs(ctable[, "t value"]), lower.tail = FALSE) * 2
ctable <- cbind(ctable, "p value" = p_values)
print(round(ctable, 4))
```

---

## Deviance and Model Fit

### Residual vs Null Deviance

```r
fit <- glm(y ~ x1 + x2, data = df, family = binomial)

# Null deviance: deviance of intercept-only model
fit$null.deviance
fit$df.null

# Residual deviance: deviance of fitted model
fit$deviance       # or: deviance(fit)
fit$df.residual

# Deviance reduction (analogous to R-squared for GLM)
1 - fit$deviance / fit$null.deviance
```

### Likelihood Ratio Test (Nested Models)

```r
fit_reduced <- glm(y ~ x1, data = df, family = binomial)
fit_full <- glm(y ~ x1 + x2 + x3, data = df, family = binomial)

# LR test via anova with chi-squared test
anova(fit_reduced, fit_full, test = "Chisq")

# Manual computation
lr_stat <- fit_reduced$deviance - fit_full$deviance
lr_df <- fit_reduced$df.residual - fit_full$df.residual
lr_pval <- pchisq(lr_stat, df = lr_df, lower.tail = FALSE)
cat("LR statistic:", lr_stat, "df:", lr_df, "p-value:", lr_pval, "\n")
```

### AIC / BIC Comparison

```r
AIC(fit1, fit2, fit3)   # Returns data.frame with df and AIC columns
BIC(fit1, fit2, fit3)   # Returns data.frame with df and BIC columns
```

---

## Overdispersion

### Detecting Overdispersion in Poisson/Binomial

The dispersion parameter phi = deviance / df_residual. For Poisson and binomial,
phi is assumed to be 1. If phi >> 1, the model is overdispersed.

```r
fit_pois <- glm(count ~ x1 + x2, data = df, family = poisson)

# Quick check
phi_hat <- fit_pois$deviance / fit_pois$df.residual
cat("Estimated dispersion:", round(phi_hat, 2), "\n")
# phi >> 1 indicates overdispersion

# Formal test: use lmtest or AER
library(AER)
dispersiontest(fit_pois)
# H0: no overdispersion (equidispersion)
```

### Addressing Overdispersion

| Approach | Code | When to Use |
|----------|------|-------------|
| Quasi-Poisson | `family = quasipoisson` | Mild overdispersion; adjusts SEs |
| Negative binomial | `MASS::glm.nb()` | Mean-variance relationship is NB2 |
| Robust SEs | `sandwich::vcovHC()` on Poisson | Preserve Poisson point estimates |
| Quasi-binomial | `family = quasibinomial` | Overdispersed binary data |

```r
# Quasi-Poisson: same coefficients as Poisson, inflated SEs
fit_qpois <- glm(count ~ x1 + x2, data = df, family = quasipoisson)
summary(fit_qpois)$dispersion   # estimated phi

# Poisson with robust SEs (sandwich approach)
library(sandwich)
library(lmtest)
coeftest(fit_pois, vcov = vcovHC(fit_pois, type = "HC0"))
```

---

## Prediction from GLMs

### The type Argument

```r
fit <- glm(y ~ x1, data = df, family = binomial)

# Response scale (probabilities for binomial, counts for Poisson)
predict(fit, newdata = new_df, type = "response")

# Link scale (log-odds for logit, log-rate for Poisson)
predict(fit, newdata = new_df, type = "link")

# Terms: contribution of each predictor
predict(fit, newdata = new_df, type = "terms")
```

For logit: `type = "response"` gives probabilities (0 to 1);
`type = "link"` gives log-odds (unbounded).

For Poisson: `type = "response"` gives expected counts;
`type = "link"` gives log-counts.

### Standard Errors for Predictions

```r
# Get predictions with standard errors on the link scale
pred <- predict(fit, newdata = new_df, type = "link", se.fit = TRUE)

# Compute CI on link scale, then transform to response scale
z <- qnorm(0.975)
ci_lower <- fit$family$linkinv(pred$fit - z * pred$se.fit)
ci_upper <- fit$family$linkinv(pred$fit + z * pred$se.fit)
point_est <- fit$family$linkinv(pred$fit)

cat("Predicted probability:", round(point_est, 3), "\n")
cat("95% CI:", round(ci_lower, 3), "to", round(ci_upper, 3), "\n")
```

The correct approach: compute CI on the link scale (where the normal
approximation holds), then back-transform with `linkinv()`. Do not compute
CI on the response scale directly.

---

## Coefficient Interpretation

### By Family/Link

| Family + Link | Coefficient Scale | To Interpret |
|---------------|------------------|--------------|
| Binomial + logit | Log-odds | `exp(coef)` = odds ratio |
| Binomial + probit | z-score | Use marginal effects |
| Poisson + log | Log-rate | `exp(coef)` = incidence rate ratio |
| Gamma + log | Log-mean | `exp(coef)` = multiplicative effect |
| Gaussian + identity | Direct | Unit change (same as OLS) |
| Gaussian + log | Log-mean | `exp(coef)` = multiplicative effect |

### Marginal Effects (marginaleffects Package)

For direct interpretation on the response scale:

```r
library(marginaleffects)

fit <- glm(y ~ x1 + x2, data = df, family = binomial)

# Average marginal effects (AME)
avg_slopes(fit)
# Returns: average change in P(y=1) for unit change in each x

# Marginal effects at specific values
slopes(fit, newdata = datagrid(x1 = c(0, 1, 2)))

# Average comparisons for categorical variables
avg_comparisons(fit, variables = "group")
```

---

## References

- McCullagh, P. & Nelder, J.A. (1989). *Generalized Linear Models*, 2nd ed.
  Chapman & Hall.
- Venables, W.N. & Ripley, B.D. (2002). *Modern Applied Statistics with S*,
  4th ed. Springer.
- Agresti, A. (2013). *Categorical Data Analysis*, 3rd ed. Wiley.
- Hilbe, J.M. (2011). *Negative Binomial Regression*, 2nd ed. Cambridge
  University Press.
- Arel-Bundock, V., Greifer, N., & Heiss, A. (2024). "How to Interpret
  Statistical Models Using marginaleffects for R and Python." *Journal of
  Statistical Software*, 111(9), 1-32.
