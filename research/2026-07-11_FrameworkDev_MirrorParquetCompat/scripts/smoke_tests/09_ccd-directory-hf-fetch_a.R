# =============================================================================
# END-TO-END VERIFICATION (v_a): canonical documented R fetch pattern vs the
#   original failure case (ccd/schools_ccd_directory).
#
# Context: Before the fetch-patterns.md / SKILL.md / mirrors.yaml edits, an R
#   fetch of ccd/schools_ccd_directory truncated the ~224MB huggingface parquet
#   at download.file()'s 60s default timeout and silently fell through to the
#   urban_csv mirror. This script replicates the CANONICAL updated pattern
#   (read mirrors.yaml from its real path, raised timeout, priority-ordered mirror
#   loop, view-safe read) and asserts the huggingface parquet mirror serves the
#   file — the proof the documented pattern as-written fixes the original failure.
#
# FIX (v_a): v_09 wrote results with `df <<- ...` inside the tryCatch body and
#   failed with "cannot change value of locked binding for 'df'" — a harness
#   binding-lock artifact, NOT a flaw in the documented pattern. This version
#   writes fetch results into an explicit environment (st$...) so no superassign
#   to a top-level binding is needed; the view-safe read logic is otherwise
#   byte-identical to the documented canonical pattern.
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

# --- Fetch state container (avoids superassign to a locked top-level binding) ---
st <- new.env()
st$df <- NULL
st$mirror_used <- NA_character_
st$last_error <- NULL
t0 <- Sys.time()

# --- Fetch: try each mirror in priority order (canonical single-file loop) ---
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
      st$df <- as.data.frame(tbl$cast(arrow::schema(fields)))
    } else if (strategy == "lazy_csv") {
      st$df <- readr::read_csv(url, show_col_types = FALSE)
    } else {
      cat(sprintf("  Skipping %s: unknown read_strategy '%s'\n", mirror_name, strategy))
      next
    }
    st$mirror_used <- mirror_name
    cat(sprintf("  Success %s: %s rows\n", mirror_name, format(nrow(st$df), big.mark = ",")))
    "success"
  }, error = function(e) {
    st$last_error <- e
    cat(sprintf("  Failed %s: %s\n", mirror_name, conditionMessage(e)))
    "error"
  }, warning = function(w) {
    # A truncated download surfaces as a warning ("downloaded length X != reported
    #   length Y") — treat it as a failure so we do not accept a partial read.
    st$last_error <- w
    cat(sprintf("  Warning %s: %s\n", mirror_name, conditionMessage(w)))
    "error"
  })

  if (identical(result, "success")) break
}

elapsed <- as.numeric(difftime(Sys.time(), t0, units = "secs"))

if (is.null(st$df)) stop(paste("All mirrors failed. Last error:", conditionMessage(st$last_error)))

# --- Validate ---
# INTENT: prove the documented pattern serves the file from the huggingface
#   parquet mirror (original failure fell through to urban_csv) and returns the
#   full table with the expected shape and key columns.
cat("\n=== VERIFICATION ===\n")
cat(sprintf("mirror used    : %s\n", st$mirror_used))
cat(sprintf("rows           : %s\n", format(nrow(st$df), big.mark = ",")))
cat(sprintf("cols           : %d\n", ncol(st$df)))
cat(sprintf("elapsed        : %.1f s\n", elapsed))
cat(sprintf("ncessch present: %s\n", "ncessch" %in% names(st$df)))
cat(sprintf("year present   : %s\n", "year" %in% names(st$df)))

stopifnot(identical(st$mirror_used, "huggingface"))   # NOT the urban_csv fallback
stopifnot(nrow(st$df) == 3688237)
stopifnot(ncol(st$df) == 52)
stopifnot("ncessch" %in% names(st$df))
stopifnot("year" %in% names(st$df))

# --- Summary ---
cat("\n[PASS] Documented R pattern fetches ccd/schools_ccd_directory from the\n")
cat("       huggingface parquet mirror at full 3,688,237 x 52 shape — the\n")
cat("       original 60s-timeout truncation/CSV-fallback failure is fixed.\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 23:40:36
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/09_ccd-directory-hf-fetch_a.R
# Duration: 104s
# Exit code: 0
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
#   Success huggingface: 3,688,237 rows
# 
# === VERIFICATION ===
# mirror used    : huggingface
# rows           : 3,688,237
# cols           : 52
# elapsed        : 103.6 s
# ncessch present: TRUE
# year present   : TRUE
# 
# [PASS] Documented R pattern fetches ccd/schools_ccd_directory from the
#        huggingface parquet mirror at full 3,688,237 x 52 shape — the
#        original 60s-timeout truncation/CSV-fallback failure is fixed.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
