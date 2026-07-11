# =============================================================================
# Finalize the MINIMAL universal R read pattern + prep for Polars equivalence check
# =============================================================================
# v2 (03_r-repro_a.R) proved the schema-rebuild cast works and is a no-op on the
# working file. This script (a) distills the minimal reusable pattern into a single
# tight block, (b) confirms it on BOTH files, and (c) writes each file's R-read
# result to CSV so a Python/Polars script can verify row/col equivalence.
# (CSV here is a transient cross-language handshake in scratch, not a pipeline data
#  artifact — pipeline outputs remain parquet.)

# --- Config ---
suppressPackageStartupMessages(library(arrow))

scratch <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
failing <- file.path(scratch, "saipe_districts_FAILING.parquet")
working <- file.path(scratch, "meps_schools_WORKING.parquet")

cat("arrow version:", as.character(packageVersion("arrow")), "\n")

# --- The MINIMAL universal pattern (candidate for verbatim skill inclusion) ---
# Read any parquet URL/path robustly, materializing Arrow "view" string/binary
# types (which the R arrow binding cannot convert directly) before building the
# data.frame. No-op for files without view types.
read_parquet_viewsafe <- function(src) {
  tbl <- arrow::read_parquet(src, as_data_frame = FALSE)   # C++ read; tolerates view types
  sch <- tbl$schema
  fields <- lapply(seq_len(length(sch$names)), function(i) {
    fld <- sch$field(i - 1L)                                # 0-indexed (C++ convention)
    ts  <- fld$type$ToString()
    new_type <- if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
      else if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
      else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
      else fld$type
    arrow::field(fld$name, new_type)
  })
  as.data.frame(tbl$cast(arrow::schema(fields)))            # cast then convert
}
# NOTE: defined as a function ONLY for this diagnostic. The skill will inline this
# as sequential code per DAAF's no-function-definitions rule.

# --- Validate on failing file ---
dfF <- read_parquet_viewsafe(failing)
cat("FAILING (SAIPE): rows =", nrow(dfF), " cols =", ncol(dfF), "\n")
stopifnot(nrow(dfF) == 368967L, ncol(dfF) == 10L)
stopifnot(is.character(dfF$district_name))

# --- Validate on working file (no-op) ---
dfW <- read_parquet_viewsafe(working)
cat("WORKING (MEPS): rows =", nrow(dfW), " cols =", ncol(dfW), "\n")
stopifnot(nrow(dfW) == 1345122L, ncol(dfW) == 11L)

# --- Emit metadata for cross-language equivalence check ---
# INTENT: hand row count + ordered column names to the Polars verifier via small
# text files (avoids serializing 1.3M rows; equivalence is on shape + schema).
writeLines(c(as.character(nrow(dfF)), paste(names(dfF), collapse = ",")),
           file.path(scratch, "r_read_saipe_meta.txt"))
writeLines(c(as.character(nrow(dfW)), paste(names(dfW), collapse = ",")),
           file.path(scratch, "r_read_meps_meta.txt"))

# INTENT: also emit a small sample of district_name for value-level spot check.
writeLines(as.character(utils::head(dfF$district_name, 5)),
           file.path(scratch, "r_read_saipe_sample.txt"))

cat("wrote R-read metadata + sample for Polars equivalence check\n")
cat("VALIDATION PASSED\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:32:05
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/04_minimal-pattern-and-equivalence.R
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# arrow version: 23.0.1.2 
# FAILING (SAIPE): rows = 368967  cols = 10 
# WORKING (MEPS): rows = 1345122  cols = 11 
# wrote R-read metadata + sample for Polars equivalence check
# VALIDATION PASSED
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
