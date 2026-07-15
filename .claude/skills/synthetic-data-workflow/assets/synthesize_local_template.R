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

# --- Utility comparison (aggregated -- safe to share) ------------------------
# INTENT: compare synthetic vs real marginals so you can judge fidelity locally, and
#         record the comparison in the shareable generation log (below) so the fidelity
#         picture travels with the synthetic rows.
utility <- compare(syn_obj, real, print.flag = FALSE)
util_txt <- tryCatch(capture.output(print(utility)),
                     error = function(e) paste("utility comparison unavailable:", conditionMessage(e)))

# --- Validate ----------------------------------------------------------------
stopifnot(nrow(syn_obj$syn) == k, ncol(syn_obj$syn) == ncol(real))
cat(sprintf("Generated %d synthetic rows.\n", nrow(syn_obj$syn)))

# --- Save (ONLY synthetic rows + log cross the boundary) ---------------------
out_ext <- tolower(tools::file_ext(OUTPUT_SYNTHETIC_PATH))
if (out_ext == "parquet" && requireNamespace("arrow", quietly = TRUE)) {
  arrow::write_parquet(syn_obj$syn, OUTPUT_SYNTHETIC_PATH)
} else {
  # fall back to CSV if arrow is unavailable
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
  "UTILITY COMPARISON (synthetic vs real marginals -- aggregated, safe to share):",
  util_txt,
  "",
  "NOTE: real data and the fitted syn object were NOT written and must NOT be shared.")
writeLines(log_lines, OUTPUT_LOG_PATH)

cat("\nWrote (SAFE TO SHARE):\n  ", OUTPUT_SYNTHETIC_PATH, "\n  ", OUTPUT_LOG_PATH, "\n")
cat("\n>>> Do NOT share the real data or the fitted model. Only the two files above. <<<\n")
