# =============================================================================
# END-TO-END VERIFICATION: canonical documented R fetch pattern vs the original
#   failure case (ccd/schools_ccd_directory).
#
# Context: Before the fetch-patterns.md / SKILL.md / mirrors.yaml edits, an R
#   fetch of ccd/schools_ccd_directory truncated the ~224MB huggingface parquet
#   at download.file()'s 60s default timeout and silently fell through to the
#   urban_csv mirror. This script replicates the CANONICAL updated pattern exactly
#   as now documented in fetch-patterns.md (read mirrors.yaml from its real path,
#   raised timeout, priority-ordered mirror loop, view-safe read) and asserts the
#   huggingface parquet mirror is the one that serves the file — the proof the
#   documented pattern as-written fixes the original failure.
#
# INTENT: prove the as-documented pattern (a) uses the huggingface parquet mirror
#   (not the CSV fallback), and (b) returns the full 3,688,237 x 52 table.
# ASSUMES: network egress allowed; ~5 min runtime at real CDN throughput; the
#   file is read in-memory (no 224MB scratch artifact retained).
# STAGE: smoke_tests
# =============================================================================

# --- Config ---
library(arrow)
library(dplyr)
library(readr)
library(yaml)

# INTENT: read the mirror config from its real skill path (single source of truth),
#   exactly as a research fetch script would after copying/pointing at it.
MIRRORS_YAML <- "/daaf/.claude/skills/education-data-query/references/mirrors.yaml"
stopifnot(file.exists(MIRRORS_YAML))
config <- yaml::read_yaml(MIRRORS_YAML)
mirrors <- config$mirrors

DATASET_PATH <- "ccd/schools_ccd_directory"

# --- Download Timeout (R only) — canonical Fix A ---
# REASONING: both read strategies route through download.file(), capped at
#   getOption("timeout") (default 60s) on the whole transfer. Raise it so the
#   ~224MB huggingface parquet completes instead of truncating to the CSV mirror.
options(timeout = max(600, getOption("timeout")))
cat(sprintf("timeout set to: %s s\n", getOption("timeout")))

# --- Fetch: try each mirror in priority order (canonical single-file loop) ---
last_error <- NULL
df <- NULL
mirror_used <- NA_character_
t0 <- Sys.time()

for (mirror in mirrors) {
  mirror_name <- mirror$name
  strategy <- mirror$read_strategy

  url <- glue::glue(mirror$url_template,
                     root_url = mirror$root_url,
                     path = DATASET_PATH,
                     format = mirror$format)
  cat(sprintf("  Trying %s: %s\n", mirror_name, url))

  result <- tryCatch({
    if (strategy == "eager_parquet") {
      # View-safe read: cast any string_view/large_string_view/binary_view columns
      #   to materialized types, then convert. No-op on plain-string files.
      tbl <- arrow::read_parquet(url, as_data_frame = FALSE)
      sch <- tbl$schema
      fields <- lapply(seq_len(length(sch$names)), function(i) {
        fld <- sch$field(i - 1L)                   # 0-indexed (C++ convention)
        ts  <- fld$type$ToString()
        new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
          else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
          else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
          else fld$type
        arrow::field(fld$name, new_type)
      })
      df <<- as.data.frame(tbl$cast(arrow::schema(fields)))
    } else if (strategy == "lazy_csv") {
      df <<- readr::read_csv(url, show_col_types = FALSE)
    } else {
      cat(sprintf("  Skipping %s: unknown read_strategy '%s'\n", mirror_name, strategy))
      next
    }
    mirror_used <<- mirror_name
    cat(sprintf("  Success %s: %s rows\n", mirror_name, format(nrow(df), big.mark = ",")))
    "success"
  }, error = function(e) {
    last_error <<- e
    cat(sprintf("  Failed %s: %s\n", mirror_name, conditionMessage(e)))
    "error"
  }, warning = function(w) {
    # A truncated download surfaces as a warning ("downloaded length X != reported
    #   length Y") — treat it as a failure so we do not accept a partial read.
    last_error <<- w
    cat(sprintf("  Warning %s: %s\n", mirror_name, conditionMessage(w)))
    "error"
  })

  if (identical(result, "success")) break
}

elapsed <- as.numeric(difftime(Sys.time(), t0, units = "secs"))

if (is.null(df)) stop(paste("All mirrors failed. Last error:", conditionMessage(last_error)))

# --- Validate ---
# INTENT: prove the documented pattern serves the file from the huggingface
#   parquet mirror (original failure fell through to urban_csv) and returns the
#   full table with the expected shape and key columns.
cat("\n=== VERIFICATION ===\n")
cat(sprintf("mirror used   : %s\n", mirror_used))
cat(sprintf("rows          : %s\n", format(nrow(df), big.mark = ",")))
cat(sprintf("cols          : %d\n", ncol(df)))
cat(sprintf("elapsed       : %.1f s\n", elapsed))
cat(sprintf("ncessch present: %s\n", "ncessch" %in% names(df)))
cat(sprintf("year present   : %s\n", "year" %in% names(df)))

stopifnot(identical(mirror_used, "huggingface"))   # NOT the urban_csv fallback
stopifnot(nrow(df) == 3688237)
stopifnot(ncol(df) == 52)
stopifnot("ncessch" %in% names(df))
stopifnot("year" %in% names(df))

# --- Summary ---
cat("\n[PASS] Documented R pattern fetches ccd/schools_ccd_directory from the\n")
cat("       huggingface parquet mirror at full 3,688,237 x 52 shape — the\n")
cat("       original 60s-timeout truncation/CSV-fallback failure is fixed.\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 23:32:52
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/09_ccd-directory-hf-fetch.R
# Duration: 378s
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
# timeout set to: 600 s
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/ccd/schools_ccd_directory.parquet
#   Failed huggingface: cannot change value of locked binding for 'df'
#   Trying urban_csv: https://educationdata.urban.org/csv/ccd/schools_ccd_directory.csv
#   Failed urban_csv: cannot change value of locked binding for 'df'
# Error: All mirrors failed. Last error: cannot change value of locked binding for 'df'
# Execution halted
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
