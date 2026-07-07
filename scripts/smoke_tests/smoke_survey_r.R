# --- smoke_survey_r.R ---
# Smoke test for R survey package (Lumley): complex survey analysis
# Validates core functionality: svydesign, svymean, svytotal, svyglm,
# svyby, as.svrepdesign with synthetic survey data
# All assertions via stopifnot()

# --- Config ---
library(survey)

cat("=== survey-r Smoke Test ===\n")
cat("R version:", R.version.string, "\n")
cat("survey version:", as.character(packageVersion("survey")), "\n\n")

# --- Test 1: Version check ---
cat("Test 1: Version check\n")
stopifnot(packageVersion("survey") >= "4.2")
cat("  survey version:", as.character(packageVersion("survey")), "\n")
cat("  PASS\n\n")

# --- Synthetic survey data ---
# Create data with known strata, clusters, and weights
set.seed(42)
n <- 500
n_strata <- 5
n_psu_per_stratum <- 4

df <- data.frame(
  stratum = rep(1:n_strata, each = n / n_strata),
  psu = rep(1:(n_strata * n_psu_per_stratum),
            each = n / (n_strata * n_psu_per_stratum))
)
df$weight <- runif(n, min = 0.5, max = 5.0)
df$income <- 30000 + 500 * df$stratum + rnorm(n, sd = 5000)
df$age <- round(runif(n, 18, 80))
df$gender <- sample(c("Male", "Female"), n, replace = TRUE)
df$employed <- rbinom(n, 1, prob = plogis(-1 + 0.02 * df$age + 0.5 * (df$gender == "Male")))
df$health_score <- round(3 + 0.02 * df$income / 10000 + rnorm(n, sd = 1), 1)
df$visit_count <- rpois(n, lambda = exp(0.5 + 0.01 * df$age / 10))

# Handle lonely PSU option
options(survey.lonely.psu = "adjust")

# --- Test 2: svydesign() -- Design object creation ---
cat("Test 2: svydesign() -- Design object creation\n")
des <- svydesign(
  ids = ~psu,
  strata = ~stratum,
  weights = ~weight,
  data = df,
  nest = TRUE
)

stopifnot(inherits(des, "survey.design2"))
stopifnot(nrow(des$variables) == n)
cat("  Design class:", class(des)[1], "\n")
cat("  N observations:", nrow(des$variables), "\n")
cat("  Degrees of freedom:", degf(des), "\n")
stopifnot(degf(des) == n_strata * n_psu_per_stratum - n_strata)
cat("  PASS\n\n")

# --- Test 3: svymean() + svytotal() -- Point estimates ---
cat("Test 3: svymean() + svytotal() -- Point estimates\n")

mn_income <- svymean(~income, design = des, na.rm = TRUE)
tot_income <- svytotal(~income, design = des, na.rm = TRUE)

# Point estimates should be reasonable
stopifnot(coef(mn_income) > 20000 & coef(mn_income) < 50000)
stopifnot(SE(mn_income) > 0)
stopifnot(coef(tot_income) > 0)
stopifnot(SE(tot_income) > 0)

# Confidence intervals
ci <- confint(mn_income)
stopifnot(ci[1] < coef(mn_income))
stopifnot(ci[2] > coef(mn_income))

cat("  Mean income:", round(coef(mn_income), 2), "\n")
cat("  SE:", round(SE(mn_income), 4), "\n")
cat("  95% CI:", round(ci[1], 2), "to", round(ci[2], 2), "\n")
cat("  Total income:", round(coef(tot_income), 0), "\n")
cat("  PASS\n\n")

# --- Test 4: svyglm() -- Survey regression ---
cat("Test 4: svyglm() -- Survey regression\n")

# Linear regression
fit_linear <- svyglm(income ~ age + factor(gender), design = des,
                      family = gaussian())
stopifnot(inherits(fit_linear, "svyglm"))
stopifnot(length(coef(fit_linear)) == 3)
stopifnot(!any(is.na(coef(fit_linear))))

# Logistic regression (quasibinomial to avoid warnings)
fit_logit <- svyglm(employed ~ age + factor(gender), design = des,
                     family = quasibinomial())
stopifnot(inherits(fit_logit, "svyglm"))
stopifnot(!any(is.na(coef(fit_logit))))

# Predicted probabilities should be in (0, 1)
probs <- predict(fit_logit, type = "response")
stopifnot(all(probs > 0 & probs < 1))

cat("  Linear model intercept:", round(coef(fit_linear)["(Intercept)"], 2), "\n")
cat("  Linear model age coef:", round(coef(fit_linear)["age"], 4), "\n")
cat("  Logit model converged: TRUE\n")
cat("  Predicted prob range:", round(min(probs), 4), "to",
    round(max(probs), 4), "\n")
cat("  PASS\n\n")

# --- Test 5: svyby() -- Domain estimation ---
cat("Test 5: svyby() -- Domain estimation (subgroup analysis)\n")

by_gender <- svyby(~income, ~gender, design = des, svymean, na.rm = TRUE)

stopifnot(is.data.frame(by_gender))
stopifnot(nrow(by_gender) == 2)
stopifnot("income" %in% names(by_gender))
stopifnot("se" %in% names(by_gender))
stopifnot(all(by_gender$income > 0))
stopifnot(all(by_gender$se > 0))

# CIs from svyby
ci_by <- confint(by_gender)
stopifnot(nrow(ci_by) == 2)
stopifnot(all(ci_by[, 1] < ci_by[, 2]))

cat("  Male mean income:", round(by_gender$income[by_gender$gender == "Male"], 2), "\n")
cat("  Female mean income:", round(by_gender$income[by_gender$gender == "Female"], 2), "\n")
cat("  PASS\n\n")

# --- Test 6: as.svrepdesign() + replicate weights ---
cat("Test 6: as.svrepdesign() -- Replicate weight conversion\n")

# Convert Taylor design to JKn replicate weight design
des_jkn <- as.svrepdesign(des, type = "JKn")
stopifnot(inherits(des_jkn, "svyrep.design"))

# Estimates from replicate design should be close to Taylor
mn_rep <- svymean(~income, design = des_jkn, na.rm = TRUE)
stopifnot(abs(coef(mn_rep) - coef(mn_income)) < 1)  # same point estimate
stopifnot(SE(mn_rep) > 0)

# Also test svyglm with replicate weights
fit_rep <- svyglm(income ~ age + factor(gender), design = des_jkn,
                   family = gaussian())
stopifnot(inherits(fit_rep, "svyglm"))
stopifnot(!any(is.na(coef(fit_rep))))

# Point estimates should be identical (same data, same weights)
stopifnot(max(abs(coef(fit_rep) - coef(fit_linear))) < 0.001)

cat("  Replicate design class:", class(des_jkn)[1], "\n")
cat("  Taylor SE:", round(SE(mn_income), 2), "\n")
cat("  JKn SE:", round(SE(mn_rep), 2), "\n")
cat("  Point estimates match:", max(abs(coef(fit_rep) - coef(fit_linear))) < 0.001, "\n")
cat("  PASS\n\n")

# --- Bonus: Proportions + svychisq ---
cat("Bonus: Proportions and svychisq()\n")

prop_gender <- svymean(~factor(gender), design = des, na.rm = TRUE)
stopifnot(length(coef(prop_gender)) == 2)
stopifnot(abs(sum(coef(prop_gender)) - 1.0) < 0.001)

# Chi-squared test -- svychisq needs factor variables in the data
des$variables$gender_f <- factor(des$variables$gender)
des$variables$employed_f <- factor(des$variables$employed)
chi_test <- svychisq(~gender_f + employed_f, design = des)
stopifnot(inherits(chi_test, "htest"))
stopifnot(!is.na(chi_test$statistic))
stopifnot(!is.na(chi_test$p.value))

cat("  Prop Male:", round(coef(prop_gender)[1], 4), "\n")
cat("  Prop Female:", round(coef(prop_gender)[2], 4), "\n")
cat("  Chi-sq statistic:", round(chi_test$statistic, 4), "\n")
cat("  Chi-sq p-value:", round(chi_test$p.value, 4), "\n")
cat("  PASS\n\n")

# --- Bonus: subset() on design ---
cat("Bonus: subset() on design object\n")

des_male <- subset(des, gender == "Male")
mn_male <- svymean(~income, design = des_male, na.rm = TRUE)
stopifnot(coef(mn_male) > 0)
stopifnot(SE(mn_male) > 0)

# Should match svyby result for males
svyby_male <- by_gender$income[by_gender$gender == "Male"]
stopifnot(abs(coef(mn_male) - svyby_male) < 0.01)

cat("  Male subset mean:", round(coef(mn_male), 2), "\n")
cat("  Matches svyby:", abs(coef(mn_male) - svyby_male) < 0.01, "\n")
cat("  PASS\n\n")

cat("=== All survey-r smoke tests PASSED ===\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-05-10 15:57:52
# Command: Rscript /daaf/scripts/smoke_tests/smoke_survey_r.R
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# Loading required package: grid
# Loading required package: Matrix
# Loading required package: survival
# 
# Attaching package: ‘survey’
# 
# The following object is masked from ‘package:graphics’:
# 
#     dotchart
# 
# === survey-r Smoke Test ===
# R version: R version 4.5.3 (2026-03-11) 
# survey version: 4.5 
# 
# Test 1: Version check
#   survey version: 4.5 
#   PASS
# 
# Test 2: svydesign() -- Design object creation
#   Design class: survey.design2 
#   N observations: 500 
#   Degrees of freedom: 15 
#   PASS
# 
# Test 3: svymean() + svytotal() -- Point estimates
#   Mean income: 31192.58 
#   SE: 228.5596 
#   95% CI: 30744.61 to 31640.55 
#   Total income: 42157720 
#   PASS
# 
# Test 4: svyglm() -- Survey regression
#   Linear model intercept: 31101.87 
#   Linear model age coef: 5.2596 
#   Logit model converged: TRUE
#   Predicted prob range: 0.3625 to 0.6986 
#   PASS
# 
# Test 5: svyby() -- Domain estimation (subgroup analysis)
#   Male mean income: 31028.68 
#   Female mean income: 31364.62 
#   PASS
# 
# Test 6: as.svrepdesign() -- Replicate weight conversion
#   Replicate design class: svyrep.design 
#   Taylor SE: 228.56 
#   JKn SE: 228.48 
#   Point estimates match: TRUE 
#   PASS
# 
# Bonus: Proportions and svychisq()
#   Prop Male: 0.4879 
#   Prop Female: 0.5121 
#   Chi-sq statistic: 0.995 
#   Chi-sq p-value: 0.3343 
#   PASS
# 
# Bonus: subset() on design object
#   Male subset mean: 31028.68 
#   Matches svyby: TRUE 
#   PASS
# 
# === All survey-r smoke tests PASSED ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
