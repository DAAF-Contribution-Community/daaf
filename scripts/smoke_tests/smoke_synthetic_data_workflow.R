# smoke_synthetic_data_workflow.R -- Smoke test for simstudy + fabricatr
# (synthetic-data-workflow skill, flagship R generation path)
# Validates: seeded simstudy marginal generation (normal/binary/poisson),
#            genCorGen copula generation honoring a declared correlation
#            matrix (the profile-only DS-5 flagship pattern), a named
#            outcome~predictor linear relationship via defData formula
#            syntax, fabricatr hierarchical generation with draw_binary,
#            and seed-identical reproducibility for both packages.
# All tests use declared parameters only (no external files needed) --
# mirroring the profile-only boundary: generation from specifications alone.
#
# NOT YET EXECUTED: simstudy and fabricatr are added to the Dockerfile
# framework R block (Synthetic data generation) but are NOT loadable until
# the container is rebuilt. Run this test after `bash rebuild_daaf.sh` from
# the daaf-docker folder.

# --- Config ---
library(simstudy)
library(fabricatr)
library(data.table)

SEED <- 20260715
TOL_MEAN <- 0.10   # relative tolerance on recovered means (n = 5000)
TOL_CORR <- 0.08   # absolute tolerance on recovered correlations (n = 5000)
N <- 5000

cat("=== synthetic-data-workflow Smoke Test (R: simstudy + fabricatr) ===\n\n")

# --- Test 1: Version checks ---
cat("Test 1: Version checks\n")
simstudy_ver <- as.character(packageVersion("simstudy"))
fabricatr_ver <- as.character(packageVersion("fabricatr"))
cat("  simstudy:", simstudy_ver, "\n")
cat("  fabricatr:", fabricatr_ver, "\n")
# INTENT: assert loadability + print versions for skill-metadata sync.
# REASONING: exact pins come from the P3M snapshot; record them here on first
#            successful run, then tighten to equality checks if desired.
stopifnot(nzchar(simstudy_ver), nzchar(fabricatr_ver))
cat("  PASS: both packages load\n\n")

# --- Test 2: simstudy marginal generation from declarations ---
cat("Test 2: simstudy marginals (normal / binary / poisson)\n")
set.seed(SEED)
def <- defData(varname = "x_norm", dist = "normal", formula = 50, variance = 25)
def <- defData(def, varname = "x_bin", dist = "binary", formula = 0.3)
def <- defData(def, varname = "x_pois", dist = "poisson", formula = 4)
dd <- genData(N, def)
stopifnot(nrow(dd) == N)
stopifnot(abs(mean(dd$x_norm) - 50) / 50 < TOL_MEAN)
stopifnot(abs(mean(dd$x_bin) - 0.3) / 0.3 < TOL_MEAN)
stopifnot(abs(mean(dd$x_pois) - 4) / 4 < TOL_MEAN)
cat("  means recovered: x_norm", round(mean(dd$x_norm), 2),
    "| x_bin", round(mean(dd$x_bin), 3),
    "| x_pois", round(mean(dd$x_pois), 2), "\n")
cat("  PASS: declared marginals recovered within tolerance\n\n")

# --- Test 3: genCorGen copula honoring a declared correlation matrix ---
cat("Test 3: genCorGen correlated generation (profile-only flagship pattern)\n")
# INTENT: generate correlated normals from a declared corr matrix ALONE --
#         exactly what DS-5 does with a T3 profile report's pearson block.
corM <- matrix(c(1, 0.6, 0.3,
                 0.6, 1, 0.4,
                 0.3, 0.4, 1), nrow = 3)
set.seed(SEED)
dc <- genCorGen(N, nvars = 3, params1 = c(10, 20, 30), params2 = c(4, 9, 16),
                dist = "normal", corMatrix = corM, wide = TRUE)
emp <- cor(as.matrix(dc[, c("V1", "V2", "V3")]))
cat("  declared r12=0.60 r13=0.30 r23=0.40 | recovered r12=",
    round(emp[1, 2], 3), " r13=", round(emp[1, 3], 3),
    " r23=", round(emp[2, 3], 3), "\n", sep = "")
stopifnot(abs(emp[1, 2] - 0.6) < TOL_CORR)
stopifnot(abs(emp[1, 3] - 0.3) < TOL_CORR)
stopifnot(abs(emp[2, 3] - 0.4) < TOL_CORR)
cat("  PASS: declared correlation matrix honored within tolerance\n\n")

# --- Test 4: named outcome~predictor relationship via defData formula ---
cat("Test 4: named linear relationship (outcome = 5 + 2*x + noise)\n")
set.seed(SEED)
def2 <- defData(varname = "x", dist = "normal", formula = 0, variance = 1)
def2 <- defData(def2, varname = "y", dist = "normal",
                formula = "5 + 2 * x", variance = 1)
d2 <- genData(N, def2)
fit <- lm(y ~ x, data = d2)
slope <- unname(coef(fit)["x"])
cat("  declared slope 2.00 | recovered", round(slope, 3), "\n")
stopifnot(abs(slope - 2) < 0.1)
cat("  PASS: named relationship honored\n\n")

# --- Test 5: fabricatr hierarchical generation ---
cat("Test 5: fabricatr nested structure + draw_binary\n")
set.seed(SEED)
fd <- fabricate(
  school = add_level(N = 20, urban = draw_binary(prob = 0.4, N = N)),
  student = add_level(N = 50, treated = draw_binary(prob = 0.5, N = N))
)
stopifnot(nrow(fd) == 20 * 50)
stopifnot(length(unique(fd$school)) == 20)
prop_treated <- mean(fd$treated)
cat("  1000 students in 20 schools | treated prop", round(prop_treated, 3), "\n")
stopifnot(abs(prop_treated - 0.5) < 0.1)
cat("  PASS: hierarchical generation works\n\n")

# --- Test 6: seeded reproducibility (both packages) ---
cat("Test 6: seed-identical reproducibility\n")
set.seed(SEED); a1 <- genData(100, def)
set.seed(SEED); a2 <- genData(100, def)
stopifnot(identical(a1, a2))
set.seed(SEED); b1 <- fabricate(unit = add_level(N = 100, z = draw_binary(prob = 0.3, N = N)))
set.seed(SEED); b2 <- fabricate(unit = add_level(N = 100, z = draw_binary(prob = 0.3, N = N)))
stopifnot(identical(b1, b2))
cat("  PASS: identical seeds produce identical data (audit-trail requirement)\n\n")

cat("=== ALL synthetic-data-workflow R SMOKE TESTS PASSED ===\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 17:53:24
# Command: Rscript /daaf/scripts/smoke_tests/smoke_synthetic_data_workflow.R
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# === synthetic-data-workflow Smoke Test (R: simstudy + fabricatr) ===
# 
# Test 1: Version checks
#   simstudy: 0.9.2 
#   fabricatr: 1.0.2 
#   PASS: both packages load
# 
# Test 2: simstudy marginals (normal / binary / poisson)
#   means recovered: x_norm 50.02 | x_bin 0.298 | x_pois 4.08 
#   PASS: declared marginals recovered within tolerance
# 
# Test 3: genCorGen correlated generation (profile-only flagship pattern)
#   declared r12=0.60 r13=0.30 r23=0.40 | recovered r12=0.606 r13=0.306 r23=0.391
#   PASS: declared correlation matrix honored within tolerance
# 
# Test 4: named linear relationship (outcome = 5 + 2*x + noise)
#   declared slope 2.00 | recovered 2.01 
#   PASS: named relationship honored
# 
# Test 5: fabricatr nested structure + draw_binary
#   1000 students in 20 schools | treated prop 0.483 
#   PASS: hierarchical generation works
# 
# Test 6: seed-identical reproducibility
#   PASS: identical seeds produce identical data (audit-trail requirement)
# 
# === ALL synthetic-data-workflow R SMOKE TESTS PASSED ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
