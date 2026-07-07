# --- smoke_r_stats.R ---
# Smoke test for R stats ecosystem: base stats, sandwich, lmtest, car, broom, MASS
# Validates core functionality: lm, glm, robust SEs, diagnostics, tidy output,
# classical tests, negative binomial
# All assertions via stopifnot()
#
# REVISION _b (Session D fix wave 2a): adds Test 11 — tseries stationarity
# tests (adf.test/kpss.test/pp.test) and jarque.bera.test, backing the r-stats
# skill's time-series.md and diagnostics.md claims.
# NOTE: Test 11 requires tseries, which the CURRENT image does not have — it
# was added to the Dockerfile in this wave. Until the user rebuilds the image,
# run with the Session D scratch library:
#   R_LIBS_USER=/daaf/research/2026-07-06_FrameworkDev_R_Support/scripts/scratch/Rlib_sessionD
# In the rebuilt image this test passes with no environment setup.

# --- Config ---
library(sandwich)
library(lmtest)
library(car)
library(broom)
library(MASS)
library(tseries)

cat("=== r-stats Smoke Test ===\n")
cat("R version:", R.version.string, "\n")
cat("sandwich version:", as.character(packageVersion("sandwich")), "\n")
cat("lmtest version:", as.character(packageVersion("lmtest")), "\n")
cat("car version:", as.character(packageVersion("car")), "\n")
cat("broom version:", as.character(packageVersion("broom")), "\n")
cat("MASS version:", as.character(packageVersion("MASS")), "\n")
cat("tseries version:", as.character(packageVersion("tseries")), "\n\n")

# --- Test 1: Version check ---
cat("Test 1: Version check\n")
stopifnot(packageVersion("sandwich") >= "3.1.0")
stopifnot(packageVersion("lmtest") >= "0.9.40")
stopifnot(packageVersion("car") >= "3.1.0")
stopifnot(packageVersion("broom") >= "1.0.0")
stopifnot(packageVersion("MASS") >= "7.3.0")
stopifnot(packageVersion("tseries") >= "0.10.61")  # P3M 2026-04-15 pin: 0.10-61
cat("  PASS: all package versions meet minimum requirements\n\n")

# --- Synthetic data ---
set.seed(42)
n <- 200
df <- data.frame(
  x1 = rnorm(n),
  x2 = rnorm(n),
  group = sample(c("A", "B", "C"), n, replace = TRUE)
)
df$y <- 2 + 1.5 * df$x1 - 0.8 * df$x2 + rnorm(n, sd = 1)
df$y_binary <- rbinom(n, 1, plogis(-0.5 + 0.8 * df$x1 + 0.3 * df$x2))
df$y_count <- rpois(n, exp(0.5 + 0.3 * df$x1 + 0.2 * df$x2))

# --- Test 2: Basic OLS via lm() + summary() ---
cat("Test 2: Basic OLS via lm() + summary()\n")
fit_ols <- lm(y ~ x1 + x2, data = df)
s <- summary(fit_ols)

stopifnot(inherits(fit_ols, "lm"))
stopifnot(length(coef(fit_ols)) == 3)
stopifnot(!any(is.na(coef(fit_ols))))
stopifnot(s$r.squared > 0.5)

cat("  Intercept:", round(coef(fit_ols)["(Intercept)"], 4), "\n")
cat("  x1:", round(coef(fit_ols)["x1"], 4), "\n")
cat("  x2:", round(coef(fit_ols)["x2"], 4), "\n")
cat("  R-squared:", round(s$r.squared, 4), "\n")
cat("  PASS\n\n")

# --- Test 3: Logistic regression via glm() ---
cat("Test 3: Logistic regression via glm()\n")
fit_logit <- glm(y_binary ~ x1 + x2, data = df, family = binomial)

stopifnot(inherits(fit_logit, "glm"))
stopifnot(length(coef(fit_logit)) == 3)
stopifnot(!any(is.na(coef(fit_logit))))
stopifnot(fit_logit$converged)

# Predicted probabilities should be in (0, 1)
probs <- predict(fit_logit, type = "response")
stopifnot(all(probs > 0 & probs < 1))

cat("  Logit converged:", fit_logit$converged, "\n")
cat("  Coef x1:", round(coef(fit_logit)["x1"], 4), "\n")
cat("  Predicted prob range:", round(min(probs), 4), "to", round(max(probs), 4), "\n")
cat("  PASS\n\n")

# --- Test 4: Robust SEs via sandwich::vcovHC() + lmtest::coeftest() ---
cat("Test 4: Robust SEs via sandwich + lmtest\n")
V_hc1 <- vcovHC(fit_ols, type = "HC1")
ct_robust <- coeftest(fit_ols, vcov = V_hc1)

stopifnot(inherits(ct_robust, "coeftest"))
stopifnot(nrow(ct_robust) == 3)
stopifnot(!any(is.na(ct_robust)))

# Robust SEs should differ from standard SEs
se_standard <- s$coefficients[, "Std. Error"]
se_robust <- ct_robust[, "Std. Error"]
stopifnot(!all(abs(se_standard - se_robust) < 1e-10))

cat("  SE(x1) standard:", round(se_standard["x1"], 4), "\n")
cat("  SE(x1) HC1:     ", round(se_robust["x1"], 4), "\n")
cat("  PASS\n\n")

# --- Test 5: car::linearHypothesis() ---
cat("Test 5: Joint hypothesis test via car::linearHypothesis()\n")
lh_result <- linearHypothesis(fit_ols, c("x1 = 0", "x2 = 0"))

stopifnot(inherits(lh_result, "anova"))
stopifnot("Pr(>F)" %in% names(lh_result))
f_pval <- lh_result[["Pr(>F)"]][2]
stopifnot(!is.na(f_pval))
# Both x1 and x2 are significant, so joint test should reject
stopifnot(f_pval < 0.05)

cat("  F-statistic:", round(lh_result[["F"]][2], 4), "\n")
cat("  p-value:", format(f_pval, digits = 4), "\n")
cat("  PASS\n\n")

# --- Test 6: confint() ---
cat("Test 6: Confidence intervals via confint()\n")
ci <- confint(fit_ols)

stopifnot(is.matrix(ci))
stopifnot(nrow(ci) == 3)
stopifnot(ncol(ci) == 2)
stopifnot(all(ci[, 1] < ci[, 2]))  # lower < upper

# x1 CI should not contain zero (x1 is significant)
stopifnot(ci["x1", 1] > 0 | ci["x1", 2] < 0)

cat("  x1 95% CI:", round(ci["x1", 1], 4), "to", round(ci["x1", 2], 4), "\n")
cat("  x2 95% CI:", round(ci["x2", 1], 4), "to", round(ci["x2", 2], 4), "\n")
cat("  PASS\n\n")

# --- Test 7: predict() with newdata ---
cat("Test 7: predict() with newdata\n")
new_df <- data.frame(x1 = c(0, 1, 2), x2 = c(0, 0, 0))
preds <- predict(fit_ols, newdata = new_df)

stopifnot(length(preds) == 3)
stopifnot(!any(is.na(preds)))
# With x2=0, increase in x1 by 1 should increase y by ~1.5
diff_pred <- preds[2] - preds[1]
stopifnot(abs(diff_pred - coef(fit_ols)["x1"]) < 1e-10)

# Prediction intervals
pred_int <- predict(fit_ols, newdata = new_df, interval = "prediction")
stopifnot(ncol(pred_int) == 3)
stopifnot(all(pred_int[, "lwr"] < pred_int[, "fit"]))
stopifnot(all(pred_int[, "fit"] < pred_int[, "upr"]))

cat("  Predictions:", round(preds, 4), "\n")
cat("  Prediction interval width:", round(pred_int[1, "upr"] - pred_int[1, "lwr"], 4), "\n")
cat("  PASS\n\n")

# --- Test 8: broom::tidy() + broom::glance() ---
cat("Test 8: broom::tidy() + broom::glance()\n")
tidy_df <- tidy(fit_ols, conf.int = TRUE)
glance_df <- glance(fit_ols)

stopifnot(is.data.frame(tidy_df))
stopifnot(nrow(tidy_df) == 3)
stopifnot(all(c("term", "estimate", "std.error", "statistic",
                "p.value", "conf.low", "conf.high") %in% names(tidy_df)))

stopifnot(is.data.frame(glance_df))
stopifnot(nrow(glance_df) == 1)
stopifnot(all(c("r.squared", "adj.r.squared", "sigma", "AIC", "BIC",
                "nobs") %in% names(glance_df)))
stopifnot(glance_df$nobs == n)

cat("  tidy() columns:", paste(names(tidy_df), collapse = ", "), "\n")
cat("  glance() R-sq:", round(glance_df$r.squared, 4), "\n")
cat("  PASS\n\n")

# --- Test 9: t.test() + chisq.test() ---
cat("Test 9: Classical tests (t.test + chisq.test)\n")

# t-test: compare y between groups A and B
t_result <- t.test(y ~ group, data = df[df$group %in% c("A", "B"), ])
stopifnot(inherits(t_result, "htest"))
stopifnot(!is.na(t_result$statistic))
stopifnot(!is.na(t_result$p.value))
stopifnot(length(t_result$conf.int) == 2)

# broom works on t.test
tidy_t <- tidy(t_result)
stopifnot("estimate" %in% names(tidy_t))

# Chi-squared test
tab <- table(df$group, df$y_binary)
chi_result <- chisq.test(tab)
stopifnot(inherits(chi_result, "htest"))
stopifnot(!is.na(chi_result$statistic))
stopifnot(!is.na(chi_result$p.value))

cat("  t-test statistic:", round(t_result$statistic, 4), "\n")
cat("  t-test p-value:", round(t_result$p.value, 4), "\n")
cat("  Chi-sq statistic:", round(chi_result$statistic, 4), "\n")
cat("  Chi-sq p-value:", round(chi_result$p.value, 4), "\n")
cat("  PASS\n\n")

# --- Test 10: MASS::glm.nb() ---
cat("Test 10: Negative binomial via MASS::glm.nb()\n")

# Generate overdispersed count data
set.seed(123)
df$y_nb <- rnbinom(n, mu = exp(0.5 + 0.3 * df$x1), size = 2)

fit_nb <- glm.nb(y_nb ~ x1 + x2, data = df)

stopifnot(inherits(fit_nb, "negbin"))
stopifnot(fit_nb$converged)
stopifnot(!any(is.na(coef(fit_nb))))
stopifnot(fit_nb$theta > 0)

# Compare AIC with Poisson (NB should fit better for overdispersed data)
fit_pois_nb <- glm(y_nb ~ x1 + x2, data = df, family = poisson)
stopifnot(AIC(fit_nb) < AIC(fit_pois_nb))

# broom works on glm.nb
tidy_nb <- tidy(fit_nb, conf.int = TRUE, exponentiate = TRUE)
stopifnot("estimate" %in% names(tidy_nb))
stopifnot(all(tidy_nb$estimate > 0))  # exponentiated = IRRs > 0

cat("  NB theta:", round(fit_nb$theta, 4), "\n")
cat("  NB AIC:", round(AIC(fit_nb), 2), "\n")
cat("  Poisson AIC:", round(AIC(fit_pois_nb), 2), "\n")
cat("  NB converged:", fit_nb$converged, "\n")
cat("  IRR x1:", round(tidy_nb$estimate[tidy_nb$term == "x1"], 4), "\n")
cat("  PASS\n\n")

# --- Test 11: tseries stationarity tests + Jarque-Bera ---
# Backs r-stats time-series.md (Stationarity Tests section: adf.test,
# kpss.test, pp.test) and diagnostics.md (jarque.bera.test on residuals).
# Requires the rebuilt image (tseries added to Dockerfile, Session D wave 2a)
# or the scratch library — see header note.
cat("Test 11: tseries stationarity tests + Jarque-Bera\n")

set.seed(7)
y_stat <- as.numeric(arima.sim(model = list(ar = 0.5), n = 200))  # stationary AR(1)
y_rw <- cumsum(rnorm(200))                                        # random walk

adf_stat <- suppressWarnings(adf.test(y_stat))
kpss_stat <- suppressWarnings(kpss.test(y_stat))
pp_stat <- suppressWarnings(pp.test(y_stat))
adf_rw <- suppressWarnings(adf.test(y_rw))

stopifnot(inherits(adf_stat, "htest"), inherits(kpss_stat, "htest"),
          inherits(pp_stat, "htest"))
stopifnot(!is.na(adf_stat$p.value), !is.na(kpss_stat$p.value),
          !is.na(pp_stat$p.value))
# Stationary series: ADF and PP reject unit root; KPSS fails to reject
stopifnot(adf_stat$p.value < 0.05)
stopifnot(pp_stat$p.value < 0.05)
stopifnot(kpss_stat$p.value > 0.05)
# Random walk: ADF should NOT reject the unit root
stopifnot(adf_rw$p.value > 0.05)

# Jarque-Bera normality test on OLS residuals
jb <- jarque.bera.test(residuals(fit_ols))
stopifnot(inherits(jb, "htest"))
stopifnot(!is.na(jb$p.value))
stopifnot(jb$p.value > 0.05)  # Gaussian DGP residuals: should not reject

cat("  ADF (stationary AR1) p-value:", round(adf_stat$p.value, 4), "\n")
cat("  KPSS (stationary AR1) p-value:", round(kpss_stat$p.value, 4), "\n")
cat("  PP (stationary AR1) p-value:", round(pp_stat$p.value, 4), "\n")
cat("  ADF (random walk) p-value:", round(adf_rw$p.value, 4), "\n")
cat("  Jarque-Bera p-value:", round(jb$p.value, 4), "\n")
cat("  PASS\n\n")

# --- Bonus: VIF via car::vif() ---
cat("Bonus: VIF via car::vif()\n")
vif_vals <- vif(fit_ols)
stopifnot(length(vif_vals) == 2)  # x1, x2 (no intercept)
stopifnot(all(vif_vals > 0))
stopifnot(all(vif_vals < 10))  # no multicollinearity in synthetic data

cat("  VIF x1:", round(vif_vals["x1"], 4), "\n")
cat("  VIF x2:", round(vif_vals["x2"], 4), "\n")
cat("  PASS\n\n")

# --- Bonus: Clustered SEs via sandwich::vcovCL() ---
cat("Bonus: Clustered SEs via sandwich::vcovCL()\n")
V_cl <- vcovCL(fit_ols, cluster = df$group)
ct_cl <- coeftest(fit_ols, vcov = V_cl)
stopifnot(inherits(ct_cl, "coeftest"))
stopifnot(!any(is.na(ct_cl)))

cat("  SE(x1) clustered:", round(ct_cl["x1", "Std. Error"], 4), "\n")
cat("  PASS\n\n")

cat("=== All r-stats smoke tests PASSED ===\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 17:26:31
# Command: Rscript /daaf/scripts/smoke_tests/smoke_r_stats_b.R
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Loading required package: zoo
# 
# Attaching package: ‘zoo’
# 
# The following objects are masked from ‘package:base’:
# 
#     as.Date, as.Date.numeric
# 
# Loading required package: carData
# Registered S3 method overwritten by 'quantmod':
#   method            from
#   as.zoo.data.frame zoo 
# === r-stats Smoke Test ===
# R version: R version 4.5.3 (2026-03-11) 
# sandwich version: 3.1.1 
# lmtest version: 0.9.40 
# car version: 3.1.5 
# broom version: 1.0.12 
# MASS version: 7.3.65 
# tseries version: 0.10.61 
# 
# Test 1: Version check
#   PASS: all package versions meet minimum requirements
# 
# Test 2: Basic OLS via lm() + summary()
#   Intercept: 1.9295 
#   x1: 1.4506 
#   x2: -0.8029 
#   R-squared: 0.7554 
#   PASS
# 
# Test 3: Logistic regression via glm()
#   Logit converged: TRUE 
#   Coef x1: 0.7204 
#   Predicted prob range: 0.048 to 0.8195 
#   PASS
# 
# Test 4: Robust SEs via sandwich + lmtest
#   SE(x1) standard: 0.0692 
#   SE(x1) HC1:      0.0691 
#   PASS
# 
# Test 5: Joint hypothesis test via car::linearHypothesis()
#   F-statistic: 304.2193 
#   p-value: 5.764e-61 
#   PASS
# 
# Test 6: Confidence intervals via confint()
#   x1 95% CI: 1.3141 to 1.5871 
#   x2 95% CI: -0.9433 to -0.6624 
#   PASS
# 
# Test 7: predict() with newdata
#   Predictions: 1.9295 3.3801 4.8307 
#   Prediction interval width: 3.7497 
#   PASS
# 
# Test 8: broom::tidy() + broom::glance()
#   tidy() columns: term, estimate, std.error, statistic, p.value, conf.low, conf.high 
#   glance() R-sq: 0.7554 
#   PASS
# 
# Test 9: Classical tests (t.test + chisq.test)
#   t-test statistic: -1.1225 
#   t-test p-value: 0.2637 
#   Chi-sq statistic: 2.6737 
#   Chi-sq p-value: 0.2627 
#   PASS
# 
# Test 10: Negative binomial via MASS::glm.nb()
#   NB theta: 2.453 
#   NB AIC: 680.42 
#   Poisson AIC: 708.44 
#   NB converged: TRUE 
#   IRR x1: 1.4415 
#   PASS
# 
# Test 11: tseries stationarity tests + Jarque-Bera
#   ADF (stationary AR1) p-value: 0.01 
#   KPSS (stationary AR1) p-value: 0.1 
#   PP (stationary AR1) p-value: 0.01 
#   ADF (random walk) p-value: 0.2371 
#   Jarque-Bera p-value: 0.3087 
#   PASS
# 
# Bonus: VIF via car::vif()
#   VIF x1: 1.0065 
#   VIF x2: 1.0065 
#   PASS
# 
# Bonus: Clustered SEs via sandwich::vcovCL()
#   SE(x1) clustered: 0.1136 
#   PASS
# 
# === All r-stats smoke tests PASSED ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
