# --- Config ---
# INTENT: Smoke test for skimr — data profiling summaries used by data-ingest.
#
# NAMING NOTE: Other smoke tests are named after DAAF skills (smoke_tidyverse,
# smoke_r_stats, ...). There is NO skimr skill — skimr backs the agent-level
# claim in .claude/agents/README.md that data-ingest "profiles with R (dplyr,
# arrow, skimr)" (parity audit finding F7). This file is therefore named after
# the package itself; if a profiling skill is authored later, fold this test
# into its smoke test.
#
# NOTE: skimr is NOT in the CURRENT image — it was added to the Dockerfile in
# Session D fix wave 2a. Until the user rebuilds the image, run with the
# Session D scratch library:
#   R_LIBS_USER=/daaf/research/2026-07-06_FrameworkDev_R_Support/scripts/scratch/Rlib_sessionD
# In the rebuilt image this test passes with no environment setup.

library(skimr)
library(dplyr)

test_count <- 0
pass_count <- 0

cat("=== skimr Smoke Test ===\n")
cat("R version:", R.version.string, "\n")
cat("skimr version:", as.character(packageVersion("skimr")), "\n\n")

# --- Test 1: Version check ---
cat("Test 1: Version check\n")
stopifnot(packageVersion("skimr") >= "2.2.2")  # P3M 2026-04-15 pin
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("  PASS\n\n")

# --- Test 2: skim() on a data.frame ---
cat("Test 2: skim() on mtcars\n")
sk <- skim(mtcars)

stopifnot(inherits(sk, "skim_df"))
stopifnot(nrow(sk) == ncol(mtcars))  # one row per profiled column
stopifnot(all(c("skim_type", "skim_variable", "n_missing",
                "complete_rate") %in% names(sk)))
stopifnot(all(sk$n_missing == 0))    # mtcars has no missing values
stopifnot(all(sk$complete_rate == 1))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("  Profiled", nrow(sk), "columns of", ncol(mtcars), "\n")
cat("  PASS\n\n")

# --- Test 3: skim() with mixed types and missing values ---
cat("Test 3: skim() with mixed types and missing values\n")
set.seed(42)
df <- data.frame(
  num = c(rnorm(95), rep(NA, 5)),
  chr = c(sample(letters, 98, replace = TRUE), NA, NA),
  fct = factor(sample(c("low", "mid", "high"), 100, replace = TRUE)),
  lgl = sample(c(TRUE, FALSE), 100, replace = TRUE)
)
sk2 <- skim(df)

stopifnot(nrow(sk2) == 4)
stopifnot(sort(unique(sk2$skim_type)) ==
            sort(c("numeric", "character", "factor", "logical")))
stopifnot(sk2$n_missing[sk2$skim_variable == "num"] == 5)
stopifnot(sk2$n_missing[sk2$skim_variable == "chr"] == 2)
stopifnot(abs(sk2$complete_rate[sk2$skim_variable == "num"] - 0.95) < 1e-9)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("  Types detected:", paste(sort(unique(sk2$skim_type)), collapse = ", "), "\n")
cat("  PASS\n\n")

# --- Test 4: dplyr integration (group_by + skim) ---
cat("Test 4: group_by() |> skim() integration\n")
sk3 <- mtcars |>
  group_by(cyl) |>
  skim(mpg)

stopifnot(inherits(sk3, "skim_df"))
stopifnot("cyl" %in% names(sk3))
stopifnot(nrow(sk3) == 3)  # one mpg row per cyl group (4, 6, 8)
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("  Grouped skim rows:", nrow(sk3), "\n")
cat("  PASS\n\n")

# --- Test 5: yank() / partition by type ---
cat("Test 5: partition() and yank() accessors\n")
parts <- partition(sk2)
stopifnot(is.list(parts))
stopifnot(all(c("numeric", "character", "factor", "logical") %in% names(parts)))
num_part <- yank(sk2, "numeric")
stopifnot(is.data.frame(num_part))
stopifnot("mean" %in% names(num_part))
test_count <- test_count + 1
pass_count <- pass_count + 1
cat("  Partitions:", paste(names(parts), collapse = ", "), "\n")
cat("  PASS\n\n")

# --- Summary ---
cat("=== SMOKE TEST SUMMARY ===\n")
cat("Tests run:", test_count, "\n")
cat("Tests passed:", pass_count, "\n")
stopifnot(pass_count == test_count)
cat("ALL SKIMR SMOKE TESTS PASSED\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 17:26:49
# Command: Rscript /daaf/scripts/smoke_tests/smoke_skimr.R
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# 
# Attaching package: ‘dplyr’
# 
# The following objects are masked from ‘package:stats’:
# 
#     filter, lag
# 
# The following objects are masked from ‘package:base’:
# 
#     intersect, setdiff, setequal, union
# 
# === skimr Smoke Test ===
# R version: R version 4.5.3 (2026-03-11) 
# skimr version: 2.2.2 
# 
# Test 1: Version check
#   PASS
# 
# Test 2: skim() on mtcars
#   Profiled 11 columns of 11 
#   PASS
# 
# Test 3: skim() with mixed types and missing values
#   Types detected: character, factor, logical, numeric 
#   PASS
# 
# Test 4: group_by() |> skim() integration
#   Grouped skim rows: 3 
#   PASS
# 
# Test 5: partition() and yank() accessors
#   Partitions: character, factor, logical, numeric 
#   PASS
# 
# === SMOKE TEST SUMMARY ===
# Tests run: 5 
# Tests passed: 5 
# ALL SKIMR SMOKE TESTS PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
