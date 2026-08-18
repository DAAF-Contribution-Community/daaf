# --- Config ---
# INTENT: Execute the tidyverse io.md view-safe parquet read sample (R) verbatim
#   against the live pinned HF mirror. Source: tidyverse/references/io.md lines 47-75
#   ("View-Safe Read for External / Polars-Written Parquet"). Fetches
#   saipe/districts_saipe.parquet. Self-contained (inlines MIRROR_ROOT + REVISION).
# ASSUMES: network egress to huggingface.co; arrow present.

sample_results <- list()

# --- Download timeout (io.md notes this is required for large HTTP reads) ---
options(timeout = max(600, getOption("timeout")))

cat("\n=== SAMPLE 14: tidyverse/io.md view-safe parquet read (lines 47-75) ===\n")
sample_results[["14"]] <- tryCatch({
  library(arrow)

  # INTENT: read external parquet robustly against Arrow "view" string/binary types
  #   that Polars emits but the R arrow binding cannot convert to R vectors directly.
  MIRROR_ROOT <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve"
  REVISION <- "0ad00ce0e232c96b0642459e4e7326607a8d26aa"   # immutable commit SHA of the v2 upload
  src <- sprintf("%s/%s/saipe/districts_saipe.parquet", MIRROR_ROOT, REVISION)

  tbl <- read_parquet(src, as_data_frame = FALSE)   # C++ read tolerates view types
  sch <- tbl$schema
  fields <- lapply(seq_len(length(sch$names)), function(i) {
    fld <- sch$field(i - 1L)                         # $field() is 0-indexed (C++ convention)
    ts  <- fld$type$ToString()
    # Check large_string_view before string_view: the former's ToString() contains
    # the substring "string_view", so an unordered check would misclassify it.
    new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) large_utf8()
      else if (grepl("string_view", ts, fixed = TRUE)) utf8()
      else if (grepl("binary_view", ts, fixed = TRUE)) binary()
      else fld$type
    field(fld$name, new_type)
  })
  df <- as.data.frame(tbl$cast(schema(fields)))      # cast view->materialized, then convert

  # --- Validate ---
  stopifnot(nrow(df) > 0)
  cat(sprintf("  Read %s rows x %d cols\n", format(nrow(df), big.mark = ","), ncol(df)))
  cat(sprintf("  columns: %s\n", paste(head(names(df), 10), collapse = ", ")))
  print(utils::head(df, 3))
  list(status = "PASS",
       evidence = sprintf("view-safe read of saipe/districts_saipe: %s rows x %d cols",
                          format(nrow(df), big.mark = ","), ncol(df)))
}, error = function(e) {
  cat(sprintf("SAMPLE 14 FAILED: %s\n", conditionMessage(e)))
  list(status = "FAIL", evidence = conditionMessage(e))
})

# --- Summary ---
cat("\n=== TIDYVERSE IO SAMPLE SUMMARY ===\n")
r <- sample_results[["14"]]
cat(sprintf("  [%s] 14: %s\n", r$status, r$evidence))


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:11:40
# Command: Rscript /daaf/scripts/mirror_maintenance/14_tidyverse-io-sample.R
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# 
# === SAMPLE 14: tidyverse/io.md view-safe parquet read (lines 47-75) ===
# 
# Attaching package: ‘arrow’
# 
# The following object is masked from ‘package:utils’:
# 
#     timestamp
# 
#   Read 382,099 rows x 10 cols
#   columns: district_id, district_name, est_population_total, est_population_5_17, est_population_5_17_poverty, year, leaid, fips, est_population_5_17_poverty_pct, est_population_5_17_pct
#   district_id                district_name est_population_total
# 1           5    ALBERTVILLE CITY SCH DIST                16294
# 2          30 ALEXANDER CITY CITY SCH DIST                17704
# 3          60      ANDALUSIA CITY SCH DIST                 9602
#   est_population_5_17 est_population_5_17_poverty year  leaid fips
# 1                2779                         506 1995 100005    1
# 2                3258                         850 1995 100030    1
# 3                1706                         571 1995 100060    1
#   est_population_5_17_poverty_pct est_population_5_17_pct
# 1                       0.1820799               0.1705536
# 2                       0.2608963               0.1840262
# 3                       0.3347011               0.1776713
# 
# === TIDYVERSE IO SAMPLE SUMMARY ===
#   [PASS] 14: view-safe read of saipe/districts_saipe: 382,099 rows x 10 cols
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
