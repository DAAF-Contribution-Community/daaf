# =============================================================================
# R repro + fix candidate for the utf8_view read failure on Polars-written parquet
# =============================================================================
# Reproduces `cannot handle Array of type <utf8_view>` on the local SAIPE file
# (ruling out any HTTP-layer cause), then tests candidate read patterns to find
# the minimal one a skill can prescribe universally. Verifies the final pattern
# is a no-op on the working MEPS file.

# --- Config ---
library(arrow)

scratch <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
failing <- file.path(scratch, "saipe_districts_FAILING.parquet")
working <- file.path(scratch, "meps_schools_WORKING.parquet")

cat("arrow package version:", as.character(packageVersion("arrow")), "\n")
cat("========================================================\n")

# --- Test A: baseline read_parquet (expect the utf8_view error) ---
# INTENT: confirm the failure reproduces on the LOCAL file, proving it is a
# format/binding issue, not an HTTP/streaming artifact.
cat("\n[A] arrow::read_parquet(failing) -- expect failure\n")
resA <- tryCatch({
  df <- arrow::read_parquet(failing)
  cat("    UNEXPECTED SUCCESS: rows =", nrow(df), "\n")
  "success"
}, error = function(e) {
  cat("    ERROR:", conditionMessage(e), "\n")
  "error"
})

# --- Test B: read as Arrow Table (as_data_frame = FALSE) ---
# INTENT: isolate whether Table construction (C++ layer) succeeds — the failure
# would then be confined to the R-vector conversion step.
cat("\n[B] arrow::read_parquet(failing, as_data_frame = FALSE) -- Table only\n")
tblB <- NULL
resB <- tryCatch({
  tblB <<- arrow::read_parquet(failing, as_data_frame = FALSE)
  cat("    SUCCESS: Table created. dims =", nrow(tblB), "x", ncol(tblB), "\n")
  cat("    schema:\n")
  print(tblB$schema)
  "success"
}, error = function(e) {
  cat("    ERROR:", conditionMessage(e), "\n")
  "error"
})

# --- Test C: cast view types to non-view, then convert to data.frame ---
# INTENT: build a new schema replacing every *_view type with its non-view analog
# (string_view->utf8, large_string_view->large_utf8, binary_view->binary), cast
# the Table, then convert. This is the candidate fix.
cat("\n[C] cast view columns -> non-view, then as.data.frame()\n")
dfC <- NULL
resC <- tryCatch({
  old_schema <- tblB$schema
  new_fields <- vector("list", length(old_schema$names))
  for (i in seq_along(old_schema$names)) {
    fld <- old_schema$field(i)
    tt <- fld$type
    ts <- tt$ToString()
    # REASONING: match on the type's string form; map each view variant to the
    # analogous materialized type. Non-view types pass through unchanged, making
    # this a no-op on files without view columns.
    if (grepl("string_view", ts, fixed = TRUE) || grepl("utf8_view", ts, fixed = TRUE)) {
      new_type <- arrow::utf8()
    } else if (grepl("large_string_view", ts, fixed = TRUE) || grepl("large_utf8_view", ts, fixed = TRUE)) {
      new_type <- arrow::large_utf8()
    } else if (grepl("binary_view", ts, fixed = TRUE)) {
      new_type <- arrow::binary()
    } else {
      new_type <- tt
    }
    new_fields[[i]] <- arrow::field(fld$name, new_type)
  }
  new_schema <- arrow::schema(new_fields)
  tblC <- tblB$cast(new_schema)
  dfC <<- as.data.frame(tblC)
  cat("    SUCCESS: cast + convert. rows =", nrow(dfC), " cols =", ncol(dfC), "\n")
  cat("    column names:", paste(names(dfC), collapse = ", "), "\n")
  cat("    district_name head:\n")
  print(utils::head(dfC$district_name, 3))
  "success"
}, error = function(e) {
  cat("    ERROR:", conditionMessage(e), "\n")
  "error"
})

# --- Test D: open_dataset |> collect() (alternative path) ---
# INTENT: test whether the dataset API sidesteps the view-conversion failure
# without an explicit cast — a simpler prescription if it works.
cat("\n[D] arrow::open_dataset(failing) |> dplyr::collect()\n")
resD <- tryCatch({
  suppressPackageStartupMessages(library(dplyr))
  dfD <- arrow::open_dataset(failing) |> dplyr::collect()
  cat("    SUCCESS: rows =", nrow(dfD), " cols =", ncol(dfD), "\n")
  "success"
}, error = function(e) {
  cat("    ERROR:", conditionMessage(e), "\n")
  "error"
})

# --- Test E: leading-zero integrity check on any zero-padded ID columns ---
# INTENT: SAIPE has leiaid/geo id columns; verify the cast path did not coerce
# string IDs to integers or strip leading zeros.
cat("\n[E] leading-zero / dtype integrity on cast result\n")
if (!is.null(dfC)) {
  for (cn in names(dfC)) {
    cls <- class(dfC[[cn]])[1]
    sample_val <- as.character(dfC[[cn]][1])
    cat(sprintf("    %-28s class=%-10s first=%s\n", cn, cls, sample_val))
  }
} else {
  cat("    (skipped: cast result unavailable)\n")
}

# --- Validate: run the FINAL minimal pattern on the WORKING file (no-op check) ---
# INTENT: prove the cast pattern from Test C is a safe universal default — it must
# succeed and be a no-op on files that contain no view columns.
cat("\n[V] FINAL PATTERN applied to WORKING (MEPS) file -- must be a no-op success\n")
resV <- tryCatch({
  tblW <- arrow::read_parquet(working, as_data_frame = FALSE)
  swk <- tblW$schema
  nf <- vector("list", length(swk$names))
  for (i in seq_along(swk$names)) {
    fld <- swk$field(i)
    ts <- fld$type$ToString()
    if (grepl("string_view", ts, fixed = TRUE) || grepl("utf8_view", ts, fixed = TRUE)) {
      nt <- arrow::utf8()
    } else if (grepl("large_string_view", ts, fixed = TRUE) || grepl("large_utf8_view", ts, fixed = TRUE)) {
      nt <- arrow::large_utf8()
    } else if (grepl("binary_view", ts, fixed = TRUE)) {
      nt <- arrow::binary()
    } else {
      nt <- fld$type
    }
    nf[[i]] <- arrow::field(fld$name, nt)
  }
  dfW <- as.data.frame(tblW$cast(arrow::schema(nf)))
  cat("    SUCCESS: MEPS rows =", nrow(dfW), " cols =", ncol(dfW), "\n")
  "success"
}, error = function(e) {
  cat("    ERROR:", conditionMessage(e), "\n")
  "error"
})

# --- Summary ---
cat("\n========================================================\n")
cat("RESULTS: A(baseline)=", resA, " B(table)=", resB, " C(cast)=", resC,
    " D(dataset)=", resD, " V(noop-working)=", resV, "\n")
stopifnot(resB == "success", resC == "success", resV == "success")
cat("VALIDATION PASSED: Table read + cast fix works on failing file and is a no-op on working file.\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:30:57
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/03_r-repro.R
# Duration: 1s
# Exit code: 1
#
# --- STDOUT ---
# 
# Attaching package: ‘arrow’
# 
# The following object is masked from ‘package:utils’:
# 
#     timestamp
# 
# arrow package version: 23.0.1.2 
# ========================================================
# 
# [A] arrow::read_parquet(failing) -- expect failure
#     ERROR: cannot handle Array of type <utf8_view> 
# 
# [B] arrow::read_parquet(failing, as_data_frame = FALSE) -- Table only
#     SUCCESS: Table created. dims = 368967 x 10 
#     schema:
# Schema
# district_id: int64
# district_name: string_view
# est_population_total: int64
# est_population_5_17: int64
# est_population_5_17_poverty: int64
# year: int64
# leaid: int64
# fips: int64
# est_population_5_17_poverty_pct: double
# est_population_5_17_pct: double
# 
# [C] cast view columns -> non-view, then as.data.frame()
#     ERROR: Invalid field index for schema. 
# 
# [D] arrow::open_dataset(failing) |> dplyr::collect()
#     ERROR: cannot handle Array of type <utf8_view> 
# 
# [E] leading-zero / dtype integrity on cast result
#     (skipped: cast result unavailable)
# 
# [V] FINAL PATTERN applied to WORKING (MEPS) file -- must be a no-op success
#     ERROR: Invalid field index for schema. 
# 
# ========================================================
# RESULTS: A(baseline)= error  B(table)= success  C(cast)= error  D(dataset)= error  V(noop-working)= error 
# Error: resC == "success" is not TRUE
# Execution halted
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
