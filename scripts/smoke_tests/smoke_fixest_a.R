# --- smoke_fixest.R ---
# Smoke test for fixest R package
# Validates core functionality: OLS, FE, clustering, IV, Poisson,
# etable, coefplot, sunab, and multi-estimation
# All assertions via stopifnot()

# --- Config ---
library(fixest)

cat("=== fixest Smoke Test ===\n")
cat("fixest version:", as.character(packageVersion("fixest")), "\n")
cat("R version:", R.version.string, "\n\n")

# --- Test 1: Version check ---
cat("Test 1: Version check\n")
ver <- packageVersion("fixest")
stopifnot(ver >= "0.14.0")
cat("  PASS: fixest", as.character(ver), "\n\n")

# --- Test 2: Basic OLS (feols without FE) ---
cat("Test 2: Basic OLS (feols without FE)\n")
data(trade, package = "fixest")
fit_ols <- feols(log(Euros) ~ log(dist_km), data = trade)
stopifnot(inherits(fit_ols, "fixest"))
stopifnot(length(coef(fit_ols)) == 2)  # Intercept + log(dist_km)
stopifnot(!is.na(coef(fit_ols)["log(dist_km)"]))
cat("  Coef log(dist_km):", round(coef(fit_ols)["log(dist_km)"], 4), "\n")
cat("  PASS\n\n")

# --- Test 3: Multi-way FE ---
cat("Test 3: Multi-way FE (feols with two-way FE)\n")
fit_fe <- feols(log(Euros) ~ log(dist_km) | Origin + Destination, data = trade)
stopifnot(inherits(fit_fe, "fixest"))
stopifnot(length(coef(fit_fe)) == 1)  # Only log(dist_km) (FE absorbed)
stopifnot(!is.na(coef(fit_fe)["log(dist_km)"]))
fe_list <- fixef(fit_fe)
stopifnot("Origin" %in% names(fe_list))
stopifnot("Destination" %in% names(fe_list))
cat("  Coef log(dist_km):", round(coef(fit_fe)["log(dist_km)"], 4), "\n")
cat("  Origin FE levels:", length(fe_list$Origin), "\n")
cat("  Destination FE levels:", length(fe_list$Destination), "\n")
cat("  PASS\n\n")

# --- Test 4: Clustered SEs (vcov = ~group) ---
cat("Test 4: Clustered SEs\n")
fit_cl <- feols(log(Euros) ~ log(dist_km) | Origin + Destination,
                data = trade, vcov = ~Origin)
se_cl <- se(fit_cl)
stopifnot(length(se_cl) == 1)
stopifnot(se_cl > 0)

# Compare with IID SEs (clustered should be different)
fit_iid <- feols(log(Euros) ~ log(dist_km) | Origin + Destination,
                 data = trade, vcov = "iid")
se_iid <- se(fit_iid)
stopifnot(abs(se_cl - se_iid) > 0.001)  # Should differ
cat("  SE (IID):", round(se_iid, 4), "\n")
cat("  SE (Clustered ~Origin):", round(se_cl, 4), "\n")
cat("  PASS\n\n")

# --- Test 5: IV estimation ---
cat("Test 5: IV estimation\n")
set.seed(42)
n <- 500
z <- rnorm(n)
x_endog <- 0.5 * z + rnorm(n, sd = 0.5)
entity <- rep(1:50, each = 10)
y <- 2 * x_endog + rnorm(n) + entity / 50
iv_data <- data.frame(y = y, x_endog = x_endog, z = z, entity = entity)

fit_iv <- feols(y ~ 1 | entity | x_endog ~ z, data = iv_data)
stopifnot(inherits(fit_iv, "fixest"))
iv_coef <- coef(fit_iv)["fit_x_endog"]
stopifnot(!is.na(iv_coef))
# IV estimate should be close to 2 (the true value)
stopifnot(abs(iv_coef - 2) < 1.0)
cat("  IV coef (true=2):", round(iv_coef, 4), "\n")

# First-stage F
fs <- fitstat(fit_iv, type = "ivf")
cat("  First-stage F:", round(fs$ivf$stat, 2), "\n")
stopifnot(fs$ivf$stat > 10)  # Strong instrument
cat("  PASS\n\n")

# --- Test 6: Poisson regression (fepois) ---
cat("Test 6: Poisson regression (fepois)\n")
set.seed(123)
pois_data <- data.frame(
  count_y = rpois(500, lambda = exp(1 + 0.3 * rep(1:50, each = 10) / 50)),
  x1 = rnorm(500),
  entity = rep(1:50, each = 10)
)
fit_pois <- fepois(count_y ~ x1 | entity, data = pois_data)
stopifnot(inherits(fit_pois, "fixest"))
stopifnot(!is.na(coef(fit_pois)["x1"]))
cat("  Poisson coef x1:", round(coef(fit_pois)["x1"], 4), "\n")
cat("  PASS\n\n")

# --- Test 7: etable output ---
cat("Test 7: etable output\n")
et <- etable(fit_ols, fit_fe, tex = FALSE)
stopifnot(inherits(et, "data.frame"))
stopifnot(ncol(et) >= 2)
stopifnot(nrow(et) > 0)
cat("  etable rows:", nrow(et), "cols:", ncol(et), "\n")

# LaTeX output
et_tex <- etable(fit_ols, fit_fe, tex = TRUE)
stopifnot(is.character(et_tex))
stopifnot(any(grepl("tabular", et_tex)))
cat("  LaTeX output generated: TRUE\n")
cat("  PASS\n\n")

# --- Test 8: coefplot renders ---
cat("Test 8: coefplot renders\n")
tmpfile <- tempfile(fileext = ".png")
png(tmpfile, width = 800, height = 600)
coefplot(fit_ols)
dev.off()
stopifnot(file.exists(tmpfile))
stopifnot(file.info(tmpfile)$size > 0)
cat("  coefplot saved:", tmpfile, "\n")
cat("  File size:", file.info(tmpfile)$size, "bytes\n")
file.remove(tmpfile)
cat("  PASS\n\n")

# --- Test 9: sunab for staggered DiD ---
cat("Test 9: sunab for staggered DiD\n")
data(base_stagg, package = "fixest")
fit_sa <- feols(y ~ x1 + sunab(year_treated, year) | id + year,
                data = base_stagg, vcov = ~id)
stopifnot(inherits(fit_sa, "fixest"))
stopifnot(length(coef(fit_sa)) > 1)

# ATT aggregation
s_att <- summary(fit_sa, agg = "ATT")
att_coef <- coef(s_att)
stopifnot(!is.na(att_coef))
stopifnot(length(att_coef) >= 1)
cat("  sunab ATT estimate:", round(att_coef[1], 4), "\n")
cat("  Number of SA coefficients:", length(coef(fit_sa)), "\n")

# iplot should work with sunab
tmpfile2 <- tempfile(fileext = ".png")
png(tmpfile2, width = 800, height = 600)
iplot(fit_sa, main = "Sun-Abraham Event Study")
dev.off()
stopifnot(file.exists(tmpfile2))
stopifnot(file.info(tmpfile2)$size > 0)
cat("  iplot saved:", tmpfile2, "\n")
file.remove(tmpfile2)
cat("  PASS\n\n")

# --- Test 10: Multiple estimation (csw) ---
cat("Test 10: Multiple estimation (csw)\n")
data(base_did, package = "fixest")
fits_csw <- feols(y ~ csw(x1, treat) | id, data = base_did)
stopifnot(inherits(fits_csw, "fixest_multi"))
stopifnot(length(fits_csw) == 2)
cat("  Number of models:", length(fits_csw), "\n")

# etable with fixest_multi
et_multi <- etable(fits_csw, tex = FALSE)
stopifnot(inherits(et_multi, "data.frame"))
cat("  etable with fixest_multi: rows=", nrow(et_multi),
    " cols=", ncol(et_multi), "\n")
cat("  PASS\n\n")

# --- Summary ---
cat("===========================================\n")
cat("All 10 fixest smoke tests PASSED\n")
cat("fixest", as.character(packageVersion("fixest")),
    "on R", R.version.string, "\n")
cat("===========================================\n")


# =============================================================================


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 15:18:41
# Command: Rscript /daaf/scripts/smoke_tests/smoke_fixest_a.R
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# === fixest Smoke Test ===
# fixest version: 0.14.0 
# R version: R version 4.5.3 (2026-03-11) 
# 
# Test 1: Version check
#   PASS: fixest 0.14.0 
# 
# Test 2: Basic OLS (feols without FE)
#   Coef log(dist_km): -1.9096 
#   PASS
# 
# Test 3: Multi-way FE (feols with two-way FE)
#   Coef log(dist_km): -2.0721 
#   Origin FE levels: 15 
#   Destination FE levels: 15 
#   PASS
# 
# Test 4: Clustered SEs
#   SE (IID): 0.0271 
#   SE (Clustered ~Origin): 0.1435 
#   PASS
# 
# Test 5: IV estimation
#   IV coef (true=2): 2.0825 
#   First-stage F: 401.79 
#   PASS
# 
# Test 6: Poisson regression (fepois)
#   Poisson coef x1: -0.006 
#   PASS
# 
# Test 7: etable output
#   etable rows: 12 cols: 3 
#   LaTeX output generated: TRUE
#   PASS
# 
# Test 8: coefplot renders
# null device 
#           1 
#   coefplot saved: /tmp/RtmpZLI4nX/file87fe14b5ed91.png 
#   File size: 8653 bytes
# [1] TRUE
#   PASS
# 
# Test 9: sunab for staggered DiD
#   sunab ATT estimate: 0.9947 
#   Number of SA coefficients: 18 
# null device 
#           1 
#   iplot saved: /tmp/RtmpZLI4nX/file87fe4f6f5e15.png 
# [1] TRUE
#   PASS
# 
# Test 10: Multiple estimation (csw)
# Notes from the estimations:
# [x 1] The variable 'treat' has been removed because of collinearity (see
# $collin.var).
#   Number of models: 2 
#   etable with fixest_multi: rows= 10  cols= 3 
#   PASS
# 
# ===========================================
# All 10 fixest smoke tests PASSED
# fixest 0.14.0 on R R version 4.5.3 (2026-03-11) 
# ===========================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
