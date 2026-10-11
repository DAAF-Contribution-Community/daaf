#!/usr/bin/env Rscript
# =============================================================================
# LOCAL HIGH-FIDELITY SYNTHESIS (R / synthpop)  --  DAAF synthetic-data-workflow
# =============================================================================
# T4 of the disclosure ladder. You run this on YOUR machine, on your REAL data.
# It fits a data-driven synthesizer (synthpop, CART) and writes ONLY synthetic
# rows -- which are safe to share with DAAF.
#
#   !!  YOUR REAL DATA NEVER LEAVES THIS MACHINE.                              !!
#   !!  THE FITTED MODEL OBJECT (the `syn` object) NEVER LEAVES THIS MACHINE.  !!
#   !!  A fitted synthesizer can regenerate real records -- it is as sensitive !!
#   !!  as the data itself. Share ONLY the synthetic output file + log below.  !!
#
# Self-contained: depends on NOTHING from DAAF. Requires the `synthpop` package
# (install.packages("synthpop")); optional `arrow` for parquet output.
#
# Code style: flat and sequential. Read top to bottom.
# =============================================================================

# --- Config (EDIT THESE) -----------------------------------------------------
INPUT_PATH             <- "data.csv"                 # your REAL data (stays local)
OUTPUT_SYNTHETIC_PATH  <- "synthetic_output.parquet" # ONLY this file is shareable
OUTPUT_LOG_PATH        <- "synthesis_log.txt"        # generation log (shareable)
SEED                   <- 20260715                   # reproducibility seed (record it)
N_SYNTHETIC            <- NA                          # rows to generate; NA = match real N
# -----------------------------------------------------------------------------

# --- Config (libraries) ------------------------------------------------------
if (!requireNamespace("synthpop", quietly = TRUE))
  stop("This template needs synthpop: install.packages(\"synthpop\")")
library(synthpop)
set.seed(SEED)
# INTENT: preserve prior exports; REASONING: a rerun must not silently overwrite a file
# that was already shared, which would break the audit trail on the receiving side.
# This mirrors the T1-T3 profiler's exclusive-creation refusal.
csv_fallback_path <- sub("\\.parquet$", ".csv", OUTPUT_SYNTHETIC_PATH)
if (any(file.exists(c(OUTPUT_SYNTHETIC_PATH, csv_fallback_path, OUTPUT_LOG_PATH))))
  stop("Output exists; choose a fresh output folder. Nothing was written and nothing was overwritten.", call. = FALSE)

# --- Load (REAL data -- never shared) ----------------------------------------
# ASSUMES: runs in YOUR environment on real data; nothing here touches DAAF.
ext <- tolower(tools::file_ext(INPUT_PATH))
if (ext == "csv") {
  real <- read.csv(INPUT_PATH, stringsAsFactors = TRUE)
} else if (ext == "parquet") {
  if (!requireNamespace("arrow", quietly = TRUE))
    stop("Reading parquet needs 'arrow': install.packages(\"arrow\")")
  real <- as.data.frame(arrow::read_parquet(INPUT_PATH))
} else {
  stop(paste("Unsupported extension:", ext))
}
n_real <- nrow(real)
cat(sprintf("Loaded %d real rows x %d columns (LOCAL ONLY)\n", n_real, ncol(real)))

# --- Fit synthesizer (fitted model -- never shared) --------------------------
# INTENT: fit CART synthesis (synthpop default) with a recorded seed.
# REASONING: CART respects logical constraints + missingness patterns; agency-grade.
k <- if (is.na(N_SYNTHETIC)) n_real else N_SYNTHETIC
syn_obj <- syn(real, seed = SEED, k = k)   # <- fitted model object: DO NOT SHARE

# --- Utility comparison (ONE aggregate statistic -- nothing else to disk) ----
# INTENT: record a single overall fidelity number in the shareable log, and nothing else.
# REASONING: synthpop's compare() renders PER-VARIABLE, PER-LEVEL and PER-BIN summaries of
#   the REAL data (marginal tables / frequency plots). Writing that into a file labelled
#   "shareable" would release real marginals at T4 -- precisely what T4 exists to avoid.
#   Only an aggregate propensity-score utility statistic crosses the boundary.
# ASSUMES: utility.gen() returns an overall S_pMSE; every extraction is length- and
#   type-guarded, and ANY deviation degrades to "unavailable" rather than to a fallback
#   that would print the comparison. A NOT-VERIFIED extraction never becomes a release.
# To judge fidelity yourself, run `compare(syn_obj, real)` INTERACTIVELY on this machine.
# Its output is real-data disclosure: read it locally, never paste or share it.
utility_statistic <- "unavailable"
utility_try <- try({
  gen <- synthpop::utility.gen(syn_obj, real, print.flag = FALSE)
  candidate <- gen[["S_pMSE"]]
  if (is.numeric(candidate) && length(candidate) == 1 && is.finite(candidate))
    utility_statistic <- format(round(candidate, 4), nsmall = 4)
}, silent = TRUE)

# --- Validate ----------------------------------------------------------------
# INTENT: every check prints one counted outcome line; the verdict is DERIVED from the
# counters, never asserted. REASONING: a gate whose evidence is missing has not gated.
synthesis <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)
syn_rows <- nrow(syn_obj[["syn"]])
syn_cols <- ncol(syn_obj[["syn"]])
if (identical(as.integer(syn_rows), as.integer(k))) {
  synthesis["passed"] <- synthesis["passed"] + 1L
  cat(sprintf("[PASS] synthetic_row_count: %d rows generated == %d requested\n", syn_rows, k))
} else {
  synthesis["failed"] <- synthesis["failed"] + 1L
  cat(sprintf("[FAIL] synthetic_row_count: %d rows generated vs %d requested\n", syn_rows, k))
}
if (identical(names(syn_obj[["syn"]]), names(real))) {
  synthesis["passed"] <- synthesis["passed"] + 1L
  cat(sprintf("[PASS] column_set_and_order: %d columns match the real frame\n", syn_cols))
} else {
  synthesis["failed"] <- synthesis["failed"] + 1L
  cat(sprintf("[FAIL] column_set_and_order: %d synthetic columns vs %d real columns, or order differs\n", syn_cols, ncol(real)))
}
if (length(SEED) == 1 && is.numeric(SEED) && is.finite(SEED)) {
  synthesis["passed"] <- synthesis["passed"] + 1L
  cat(sprintf("[PASS] seed_recorded: generation seed %s is set and will be written to the log\n", format(SEED)))
} else {
  synthesis["failed"] <- synthesis["failed"] + 1L
  cat("[FAIL] seed_recorded: SEED is not a finite number; the run is not reproducible\n")
}
# INTENT: the disclosure check is that NO per-variable comparison output reaches the log.
# REASONING: this always runs -- compare() output is never captured, so the claim is about
# what the script does, not about whether a statistic happened to compute. Whether the
# aggregate number is available is a log FIELD, not a gate (see the log lines below).
synthesis["passed"] <- synthesis["passed"] + 1L
cat("[PASS] no_per_variable_comparison_in_log: 0 per-variable/per-level comparison tables captured; at most 1 aggregate statistic is written\n")
cat(sprintf("Checks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            synthesis[["passed"]], synthesis[["warning"]], synthesis[["failed"]],
            synthesis[["not_verified"]], synthesis[["skipped"]]))
synthesis_verdict <- if (synthesis[["failed"]] > 0L ||
                         (synthesis[["passed"]] + synthesis[["warning"]] + synthesis[["failed"]]) == 0L) {
  "FAILED"
} else if (synthesis[["not_verified"]] > 0L) {
  "FAILED"
} else if (synthesis[["warning"]] > 0L) {
  "PASSED WITH WARNINGS"
} else {
  "PASSED"
}
cat("SYNTHESIS VALIDATION: ", synthesis_verdict, "\n", sep = "")
if (identical(synthesis_verdict, "FAILED"))
  stop("SYNTHESIS VALIDATION: FAILED -- nothing written; do not share any partial output.", call. = FALSE)
cat(sprintf("Generated %d synthetic rows.\n", syn_rows))

# --- Save (ONLY synthetic rows + log cross the boundary) ---------------------
# OUTPUT FORMAT: Parquet is the PREFERRED exchange format. CSV is only a fallback for
# when `arrow` is unavailable locally -- and it is an AUDITED boundary exception: on
# receipt DAAF converts the CSV to Parquet and records an exchange manifest, after which
# all in-container work uses the Parquet. Prefer installing `arrow` and sending Parquet.
out_ext <- tolower(tools::file_ext(OUTPUT_SYNTHETIC_PATH))
if (out_ext == "parquet" && requireNamespace("arrow", quietly = TRUE)) {
  arrow::write_parquet(syn_obj$syn, OUTPUT_SYNTHETIC_PATH)
} else {
  # Fallback: `arrow` unavailable -> write CSV (audited exception; DAAF converts to
  # Parquet on receipt). Install arrow (install.packages("arrow")) to avoid this.
  OUTPUT_SYNTHETIC_PATH <- sub("\\.parquet$", ".csv", OUTPUT_SYNTHETIC_PATH)
  write.csv(syn_obj$syn, OUTPUT_SYNTHETIC_PATH, row.names = FALSE)
}
log_lines <- c(
  "SYNTHESIS LOG (synthpop / CART) -- shareable",
  paste0("seed: ", SEED),
  paste0("synthpop_version: ", as.character(utils::packageVersion("synthpop"))),
  paste0("real_rows: ", n_real, "  synthetic_rows: ", nrow(syn_obj$syn)),
  paste0("columns: ", ncol(real)),
  "",
  "AGGREGATE UTILITY (one overall statistic only -- no per-variable output):",
  paste0("overall_S_pMSE: ", utility_statistic),
  "NOTE: per-variable/per-level comparison output (synthpop compare()) is deliberately",
  "NOT captured here -- it renders REAL-data marginals. Inspect it interactively on this",
  "machine if you want it; never write it to this log and never share it.",
  "",
  "NOTE: real data and the fitted syn object were NOT written and must NOT be shared.")
writeLines(log_lines, OUTPUT_LOG_PATH)

cat("\nWrote (SAFE TO SHARE):\n  ", OUTPUT_SYNTHETIC_PATH, "\n  ", OUTPUT_LOG_PATH, "\n")
cat("\n>>> Do NOT share the real data or the fitted model. Only the two files above. <<<\n")
