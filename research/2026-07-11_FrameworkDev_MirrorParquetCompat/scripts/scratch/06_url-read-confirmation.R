# =============================================================================
# Confirm the view-safe pattern works reading DIRECTLY from the mirror URL
# =============================================================================
# The skill prescribes reading straight from the HuggingFace mirror URL, so the
# fix must hold over HTTP, not just on a local file. Also confirms the baseline
# URL read fails the same way (parity with the originally reported field error).

# --- Config ---
suppressPackageStartupMessages(library(arrow))

base <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main"
url_failing <- file.path(base, "saipe/districts_saipe.parquet")

cat("arrow version:", as.character(packageVersion("arrow")), "\n")

# --- Test: baseline URL read fails (matches originally reported error) ---
cat("\n[baseline] arrow::read_parquet(url) -- expect utf8_view failure\n")
resBase <- tryCatch({
  df <- arrow::read_parquet(url_failing)
  cat("    UNEXPECTED SUCCESS rows =", nrow(df), "\n"); "success"
}, error = function(e) { cat("    ERROR:", conditionMessage(e), "\n"); "error" })

# --- Test: view-safe pattern over URL ---
# INTENT: same minimal pattern, source is the URL. read_parquet accepts a URL
# directly (arrow opens it via its filesystem/HTTP layer).
cat("\n[fix] view-safe read over URL\n")
resFix <- tryCatch({
  tbl <- arrow::read_parquet(url_failing, as_data_frame = FALSE)
  sch <- tbl$schema
  fields <- lapply(seq_len(length(sch$names)), function(i) {
    fld <- sch$field(i - 1L)
    ts  <- fld$type$ToString()
    new_type <- if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
      else if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
      else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
      else fld$type
    arrow::field(fld$name, new_type)
  })
  df <- as.data.frame(tbl$cast(arrow::schema(fields)))
  cat("    SUCCESS: rows =", nrow(df), " cols =", ncol(df), "\n")
  cat("    district_name first:", df$district_name[1], "\n")
  "success"
}, error = function(e) { cat("    ERROR:", conditionMessage(e), "\n"); "error" })

# --- Summary ---
cat("\nRESULTS: baseline-url=", resBase, " fix-url=", resFix, "\n")
stopifnot(resFix == "success")
cat("VALIDATION PASSED: view-safe pattern works reading directly from the mirror URL.\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:32:46
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/06_url-read-confirmation.R
# Duration: 3s
# Exit code: 0
#
# --- STDOUT ---
# arrow version: 23.0.1.2 
# 
# [baseline] arrow::read_parquet(url) -- expect utf8_view failure
#     ERROR: cannot handle Array of type <utf8_view> 
# 
# [fix] view-safe read over URL
#     SUCCESS: rows = 368967  cols = 10 
#     district_name first: ALBERTVILLE CITY SCH DIST 
# 
# RESULTS: baseline-url= error  fix-url= success 
# VALIDATION PASSED: view-safe pattern works reading directly from the mirror URL.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
