# smoke_ml_native.R -- Smoke test for native-compiled ML packages
# Validates: xgboost, lightgbm, rugarch -- each with a tiny real fit and an
#            assertion that predictions/fits are finite and converged.
# Part of the Noble base-image migration T3 functional tier: these packages
# ship compiled native code (OpenMP, libstdc++) whose behavior can shift
# across the glibc 2.36 -> 2.39 jump, so a real train+predict is the probe
# (a bare namespace load would not exercise the native runtime).
#
# All fits use small in-script synthetic data (no external files, no /tmp).

# --- Config ---
library(xgboost)
library(lightgbm)
library(rugarch)

cat("=== ml-native Smoke Test ===\n\n")

set.seed(42)

# --- Test 1: Version checks ---
cat("Test 1: Version checks\n")
xgb_ver  <- as.character(packageVersion("xgboost"))
lgb_ver  <- as.character(packageVersion("lightgbm"))
rug_ver  <- as.character(packageVersion("rugarch"))
cat("  xgboost:", xgb_ver, "\n")
cat("  lightgbm:", lgb_ver, "\n")
cat("  rugarch:", rug_ver, "\n")
stopifnot(numeric_version(xgb_ver) >= "1.5.0")
stopifnot(numeric_version(lgb_ver) >= "3.0.0")
stopifnot(numeric_version(rug_ver) >= "1.4.0")
cat("  PASS: All versions meet minimum requirements\n\n")

# --- Test 2: xgboost tiny train + finite predictions ---
cat("Test 2: xgboost train() + predict()\n")
n <- 100
X <- matrix(rnorm(n * 3), ncol = 3)
# A linear signal so a shallow boosted model can learn it.
y <- 2 * X[, 1] - 1.5 * X[, 2] + 0.5 * X[, 3] + rnorm(n, sd = 0.1)
dtrain <- xgb.DMatrix(data = X, label = y)
bst <- xgb.train(
  params = list(objective = "reg:squarederror", max_depth = 3, eta = 0.3, nthread = 1),
  data = dtrain,
  nrounds = 10,
  verbose = 0
)
preds_xgb <- predict(bst, X)
stopifnot(length(preds_xgb) == n)
stopifnot(all(is.finite(preds_xgb)))
rmse <- sqrt(mean((preds_xgb - y)^2))
stopifnot(is.finite(rmse))
cat("  Predictions:", length(preds_xgb), "(all finite)\n")
cat("  Train RMSE:", round(rmse, 4), "\n")
cat("  PASS\n\n")

# --- Test 3: lightgbm tiny train + finite predictions ---
cat("Test 3: lightgbm lgb.train() + predict()\n")
dtrain_lgb <- lgb.Dataset(data = X, label = y)
lgb_params <- list(
  objective = "regression",
  metric = "l2",
  num_leaves = 7,
  learning_rate = 0.3,
  num_threads = 1,
  verbosity = -1
)
lgb_model <- lgb.train(
  params = lgb_params,
  data = dtrain_lgb,
  nrounds = 10
)
preds_lgb <- predict(lgb_model, X)
stopifnot(length(preds_lgb) == n)
stopifnot(all(is.finite(preds_lgb)))
rmse_lgb <- sqrt(mean((preds_lgb - y)^2))
stopifnot(is.finite(rmse_lgb))
cat("  Predictions:", length(preds_lgb), "(all finite)\n")
cat("  Train RMSE:", round(rmse_lgb, 4), "\n")
cat("  PASS\n\n")

# --- Test 4: rugarch GARCH(1,1) fit converges ---
cat("Test 4: rugarch ugarchspec() + ugarchfit()\n")
# Simulate a series with a nonzero AR term so arima.sim's stationarity check
# has a real root to evaluate (ar = 0.0 triggers a benign polyroot warning),
# then let the GARCH model fit its conditional variance.
ret <- as.numeric(arima.sim(n = 500, list(ar = 0.2), sd = 1)) * 0.01
spec <- ugarchspec(
  variance.model = list(model = "sGARCH", garchOrder = c(1, 1)),
  mean.model = list(armaOrder = c(0, 0), include.mean = TRUE),
  distribution.model = "norm"
)
fit <- ugarchfit(spec = spec, data = ret, solver = "hybrid")
# convergence == 0 signals a converged solver in rugarch.
conv <- fit@fit$convergence
coefs <- coef(fit)
stopifnot(!is.null(conv))
stopifnot(conv == 0)
stopifnot(all(is.finite(coefs)))
cat("  Convergence code:", conv, "(0 = converged)\n")
cat("  Fitted coefficients:", paste(names(coefs), collapse = ", "), "\n")
cat("  omega:", signif(unname(coefs["omega"]), 4), "\n")
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 4 tests PASSED ===\n")
cat("Tested: xgboost", xgb_ver, "/ lightgbm", lgb_ver, "/ rugarch", rug_ver, "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-14 18:00:55
# Command: Rscript /daaf/scripts/smoke_tests/smoke_ml_native.R
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# Loading required package: parallel
# === ml-native Smoke Test ===
# 
# Test 1: Version checks
#   xgboost: 3.2.1.1 
#   lightgbm: 4.6.0 
#   rugarch: 1.5.5 
#   PASS: All versions meet minimum requirements
# 
# Test 2: xgboost train() + predict()
#   Predictions: 100 (all finite)
#   Train RMSE: 0.4133 
#   PASS
# 
# Test 3: lightgbm lgb.train() + predict()
#   Predictions: 100 (all finite)
#   Train RMSE: 0.9014 
#   PASS
# 
# Test 4: rugarch ugarchspec() + ugarchfit()
#   Convergence code: 0 (0 = converged)
#   Fitted coefficients: mu, omega, alpha1, beta1 
#   omega: 1.908e-07 
#   PASS
# 
# === All 4 tests PASSED ===
# Tested: xgboost 3.2.1.1 / lightgbm 4.6.0 / rugarch 1.5.5 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
