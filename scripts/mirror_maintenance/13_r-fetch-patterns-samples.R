# --- Config ---
# INTENT: Execute the R code samples from education-data-query skill files against
#   the live pinned HF mirror EXACTLY as documented. This file covers:
#     13a - SKILL.md R discovery quick-probe (lines 98-114)
#     13b - fetch-patterns.md R view-safe URL read / single-file mirror fetch (lines 369-532)
#     13c - fetch-patterns.md R large-file resumable curl::multi_download (lines 685-748)
# REASONING: Samples kept verbatim; fragments get the minimal documented preamble
#   from the same file. Each sample is wrapped in tryCatch so one failure does not
#   abort the others, and a PASS/FAIL tally is printed at the end.
# ASSUMES: network egress to huggingface.co; arrow/curl/yaml/httr2/dplyr present.

library(arrow)
library(dplyr)
library(yaml)
library(httr2)

PROJECT_DIR <- "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update"
MIRRORS_YAML <- "/daaf/.claude/skills/education-data-query/references/mirrors.yaml"

sample_results <- list()

# Shared preamble: load mirror config (documented minimal preamble — fetch-patterns.md
# R config block lines 433-436: config <- yaml::read_yaml(path); mirrors <- config$mirrors)
config <- yaml::read_yaml(MIRRORS_YAML)
mirrors <- config$mirrors

# ---------------------------------------------------------------------------
# R Semantic Translation helpers (fetch-patterns.md lines 143-217)
# Needed by sample 13b's build_mirror_url() call. Copied verbatim.
# ---------------------------------------------------------------------------
canonicalize_mirror_path <- function(path, object_kind) {
  if (!is.character(path) || length(path) != 1L || is.na(path)) {
    stop("mirror path must be one nonmissing string")
  }
  if (!(object_kind %in% c("data", "codebook"))) {
    stop("object_kind must be exactly 'data' or 'codebook'")
  }
  if (!nzchar(path) || path != trimws(path)) {
    stop("mirror path must be nonempty and have no outer whitespace")
  }
  if (startsWith(path, "/") || grepl("\\\\", path) || grepl(":", path, fixed = TRUE)) {
    stop("mirror path must be a relative POSIX path, not an absolute path or URL")
  }
  parts <- strsplit(path, "/", fixed = TRUE)[[1]]
  if (any(parts %in% c("", ".", ".."))) {
    stop("mirror path cannot contain empty, current-directory, or traversal segments")
  }

  recognized <- c(".parquet", ".csv", ".xls")
  allowed <- if (object_kind == "data") c(".parquet", ".csv") else ".xls"
  lower_path <- tolower(path)
  matched <- recognized[endsWith(lower_path, recognized)]
  if (length(matched) > 0L) {
    matched <- matched[[1]]
    if (!(matched %in% allowed)) stop("object kind and terminal extension do not match")
    canonical_key <- substr(path, 1L, nchar(path) - nchar(matched))
    if (any(endsWith(tolower(canonical_key), recognized))) {
      stop("mirror path has a doubled recognized extension")
    }
  } else {
    if (grepl("\\.", tail(parts, 1L))) stop("mirror path has an unsupported terminal extension")
    canonical_key <- path
  }
  if (!nzchar(canonical_key) || endsWith(canonical_key, "/")) {
    stop("canonical mirror key cannot be empty or directory-like")
  }
  canonical_key
}

mirror_revision <- function(mirror) {
  rev <- mirror$vintage$hf_revision
  if (is.null(rev)) "main" else as.character(rev)
}

build_mirror_url <- function(mirror, path, object_kind) {
  canonical_key <- canonicalize_mirror_path(path, object_kind)
  if (object_kind == "data") {
    expected_format <- tolower(mirror$format)
    template <- mirror$url_template
    if (!(expected_format %in% c("csv", "parquet"))) stop("invalid data mirror format")
  } else {
    if (!identical(unlist(mirror$metadata$formats), "xls")) stop("invalid codebook format")
    expected_format <- "xls"
    template <- mirror$metadata$url_template
  }
  url <- glue::glue(template, root_url = mirror$root_url,
                    revision = mirror_revision(mirror),
                    path = canonical_key, format = expected_format)
  expected_suffix <- paste0(".", expected_format)
  without_expected <- substr(url, 1L, nchar(url) - nchar(expected_suffix))
  if (!endsWith(tolower(url), expected_suffix) ||
      any(endsWith(tolower(without_expected), c(".csv", ".parquet", ".xls")))) {
    stop("URL template did not append exactly one expected extension")
  }
  as.character(url)
}


# ===========================================================================
# SAMPLE 13a
# SOURCE: education-data-query/SKILL.md lines 98-114
#   "Generic discovery — works with any mirror that supports it"
#   (second of the two SKILL.md quick-probe samples). Fragment: uses `mirrors`,
#   loaded in the shared preamble above.
# ===========================================================================
cat("\n=== SAMPLE 13a: SKILL.md R discovery quick-probe (lines 98-114) ===\n")
sample_results[["13a"]] <- tryCatch({
  # Generic discovery — works with any mirror that supports it
  # See fetch-patterns.md for the full inline R discovery pattern
  # Check primary mirror
  mirror <- mirrors[[1]]
  discovery <- mirror$discovery
  n_entries <- NA_integer_
  if (!is.null(discovery) && discovery$method == "http_json") {
    revision <- if (!is.null(mirror$vintage$hf_revision)) as.character(mirror$vintage$hf_revision) else "main"
    discovery_url <- if (!is.null(discovery$url_template)) gsub("{revision}", revision, discovery$url_template, fixed = TRUE) else discovery$url
    resp <- httr2::request(discovery_url) |> httr2::req_timeout(30) |> httr2::req_perform()
    raw <- httr2::resp_body_json(resp)
    entries <- if (!is.null(raw$results)) raw$results else raw
    cat(sprintf("Available files: %d\n", length(entries)))
    n_entries <- length(entries)
  }
  list(status = "PASS",
       evidence = sprintf("discovery returned %d tree entries (files+dirs) from pinned revision", n_entries))
}, error = function(e) {
  cat(sprintf("SAMPLE 13a FAILED: %s\n", conditionMessage(e)))
  list(status = "FAIL", evidence = conditionMessage(e))
})


# ===========================================================================
# SAMPLE 13b
# SOURCE: education-data-query/references/fetch-patterns.md lines 369-532
#   R single-file mirror fetch with the VIEW-SAFE parquet read.
#   Fragment: `years` is a documented arg — set to NULL (no year filter) as the
#   minimal documented preamble. DATASET_PATH = small SAIPE file (verbatim default).
# ===========================================================================
cat("\n=== SAMPLE 13b: fetch-patterns.md R view-safe URL read / single-file fetch (lines 369-532) ===\n")
sample_results[["13b"]] <- tryCatch({
  # --- Locale Guard (R only) ---
  if (!isTRUE(l10n_info()[["UTF-8"]])) Sys.setlocale("LC_ALL", "C.UTF-8")

  # --- Rate Limiting ---
  FETCH_DELAY_SECONDS <- 3
  last_fetch_time <- 0.0

  # --- Download Timeout (R only) ---
  options(timeout = max(600, getOption("timeout")))

  rate_limit <- function() {
    if (last_fetch_time > 0) {
      elapsed <- as.numeric(Sys.time()) - last_fetch_time
      if (elapsed < FETCH_DELAY_SECONDS) {
        wait <- FETCH_DELAY_SECONDS - elapsed
        cat(sprintf("  (rate limit: waiting %.1fs)\n", wait))
        Sys.sleep(wait)
      }
    }
    last_fetch_time <<- as.numeric(Sys.time())
  }

  # Dataset path (verbatim documented default — small SAIPE file)
  DATASET_PATH <- "saipe/districts_saipe"
  years <- NULL  # documented arg; NULL = no year filter (minimal preamble)

  rate_limit()
  last_error <- NULL
  mirror_df <- NULL

  for (mirror in mirrors) {
    mirror_name <- mirror$name
    strategy <- mirror$read_strategy

    url <- build_mirror_url(mirror, DATASET_PATH, "data")
    cat(sprintf("  Trying %s: %s\n", mirror_name, url))

    result <- tryCatch({
      if (strategy == "eager_parquet") {
        tbl <- arrow::read_parquet(url, as_data_frame = FALSE)
        sch <- tbl$schema
        fields <- lapply(seq_len(length(sch$names)), function(i) {
          fld <- sch$field(i - 1L)
          ts  <- fld$type$ToString()
          new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
            else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
            else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
            else fld$type
          arrow::field(fld$name, new_type)
        })
        mirror_df <<- as.data.frame(tbl$cast(arrow::schema(fields)))
      } else if (strategy == "lazy_csv") {
        mirror_df <<- readr::read_csv(url, show_col_types = FALSE)
      } else {
        cat(sprintf("  Skipping %s: unknown read_strategy '%s'\n", mirror_name, strategy))
        next
      }
      cat(sprintf("  Success %s: %s rows\n", mirror_name, format(nrow(mirror_df), big.mark = ",")))
      "success"
    }, error = function(e) {
      last_error <<- e
      cat(sprintf("  Failed %s: %s\n", mirror_name, conditionMessage(e)))
      "error"
    })

    if (identical(result, "success")) break
  }

  if (is.null(mirror_df)) stop(paste("All mirrors failed. Last error:", conditionMessage(last_error)))

  df <- mirror_df

  if (!is.null(years)) {
    df <- df |> filter(year %in% years)
  }
  cat(sprintf("  After filters: %s rows\n", format(nrow(df), big.mark = ",")))

  stopifnot(nrow(df) > 0)
  cat(sprintf("  head columns: %s\n", paste(head(names(df), 8), collapse = ", ")))
  print(utils::head(df, 3))
  list(status = "PASS",
       evidence = sprintf("view-safe read of saipe/districts_saipe: %s rows x %d cols",
                          format(nrow(df), big.mark = ","), ncol(df)))
}, error = function(e) {
  cat(sprintf("SAMPLE 13b FAILED: %s\n", conditionMessage(e)))
  list(status = "FAIL", evidence = conditionMessage(e))
})


# ===========================================================================
# SAMPLE 13c
# SOURCE: education-data-query/references/fetch-patterns.md lines 685-748
#   "Large Files (100MB+), R: download-to-disk variant" — resumable
#   curl::multi_download of ccd/schools_ccd_directory (~224MB), then view-safe read.
#   PROJECT_DIR resolved to the project. cache_dir points at the mandated
#   scratch/code_samples subdir (workspace rule) — the code path is identical.
# ===========================================================================
cat("\n=== SAMPLE 13c: fetch-patterns.md R large-file curl::multi_download (lines 685-748) ===\n")
sample_results[["13c"]] <- tryCatch({
  library(arrow)
  library(curl)

  # --- Config ---
  DATASET_PATH <- "ccd/schools_ccd_directory"
  root_url <- "https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve"
  REVISION <- "0ad00ce0e232c96b0642459e4e7326607a8d26aa"   # immutable commit SHA of the v2 upload
  url <- sprintf("%s/%s/%s.parquet", root_url, REVISION, DATASET_PATH)

  # DEVIATION (workspace rule): downloads go under scripts/scratch/code_samples/
  #   per the task instruction; the sample's line is cache_dir <- file.path(
  #   PROJECT_DIR, "scripts", "scratch"). Code path is otherwise identical.
  cache_dir <- file.path(PROJECT_DIR, "scripts", "scratch", "code_samples")   # inside project; NOT /tmp
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
  dest <- file.path(cache_dir, paste0(gsub("/", "_", DATASET_PATH), ".parquet"))

  # --- Download (resumable) ---
  dl <- curl::multi_download(url, dest, resume = TRUE)
  stopifnot(isTRUE(dl$success), dl$status_code %in% c(200L, 206L))
  cat(sprintf("  Downloaded %s to %s\n",
              format(file.info(dest)$size, big.mark = ","), dest))

  # --- View-safe local read ---
  tbl <- arrow::read_parquet(dest, as_data_frame = FALSE)
  sch <- tbl$schema
  fields <- lapply(seq_len(length(sch$names)), function(i) {
    fld <- sch$field(i - 1L)
    ts  <- fld$type$ToString()
    new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
      else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
      else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
      else fld$type
    arrow::field(fld$name, new_type)
  })
  df <- as.data.frame(tbl$cast(arrow::schema(fields)))

  # --- Validate ---
  stopifnot(nrow(df) > 0)
  cat(sprintf("  Read %s rows x %d cols\n", format(nrow(df), big.mark = ","), ncol(df)))
  list(status = "PASS",
       evidence = sprintf("curl::multi_download %s (status %d) + view-safe read: %s rows x %d cols",
                          format(file.info(dest)$size, big.mark = ","), dl$status_code,
                          format(nrow(df), big.mark = ","), ncol(df)))
}, error = function(e) {
  cat(sprintf("SAMPLE 13c FAILED: %s\n", conditionMessage(e)))
  list(status = "FAIL", evidence = conditionMessage(e))
})


# --- Summary ---
cat("\n=== R FETCH-PATTERNS SAMPLE SUMMARY ===\n")
for (sid in c("13a", "13b", "13c")) {
  r <- sample_results[[sid]]
  cat(sprintf("  [%s] %s: %s\n", r$status, sid, r$evidence))
}
n_pass <- sum(vapply(sample_results, function(r) r$status == "PASS", logical(1)))
cat(sprintf("\nPASS %d/%d\n", n_pass, length(sample_results)))


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:09:50
# Command: Rscript /daaf/scripts/mirror_maintenance/13_r-fetch-patterns-samples.R
# Duration: 60s
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
# 
# === SAMPLE 13a: SKILL.md R discovery quick-probe (lines 98-114) ===
# Available files: 514
# 
# === SAMPLE 13b: fetch-patterns.md R view-safe URL read / single-file fetch (lines 369-532) ===
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/saipe/districts_saipe.parquet
#   Success huggingface: 382,099 rows
#   After filters: 382,099 rows
#   head columns: district_id, district_name, est_population_total, est_population_5_17, est_population_5_17_poverty, year, leaid, fips
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
# === SAMPLE 13c: fetch-patterns.md R large-file curl::multi_download (lines 685-748) ===
# Using libcurl 8.5.0 with OpenSSL/3.0.13
# Download status: 0 done; 1 in progress (0 b/s). Total size: 15.99 Kb (0%)...Download status: 0 done; 1 in progress (7.62 Mb/s). Total size: 61.23 Mb (24%)...Download status: 0 done; 1 in progress (5.00 Mb/s). Total size: 68.64 Mb (27%)...Download status: 0 done; 1 in progress (3.71 Mb/s). Total size: 75.86 Mb (30%)...Download status: 0 done; 1 in progress (3.22 Mb/s). Total size: 83.24 Mb (32%)...Download status: 0 done; 1 in progress (2.97 Mb/s). Total size: 91.53 Mb (36%)...Download status: 0 done; 1 in progress (2.64 Mb/s). Total size: 97.86 Mb (38%)...Download status: 0 done; 1 in progress (4.12 Mb/s). Total size: 173.34 Mb (68%)...Download status: 0 done; 1 in progress (4.40 Mb/s). Total size: 208.91 Mb (81%)...Download status: 0 done; 1 in progress (4.29 Mb/s). Total size: 225.36 Mb (88%)...Download status: 1 done; 0 in progress. Total size: 256.50 Mb (100%)... done!             
#   Downloaded 268,963,550 to /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/scripts/scratch/code_samples/ccd_schools_ccd_directory.parquet
#   Read 3,790,415 rows x 52 cols
# 
# === R FETCH-PATTERNS SAMPLE SUMMARY ===
#   [PASS] 13a: discovery returned 514 tree entries (files+dirs) from pinned revision
#   [PASS] 13b: view-safe read of saipe/districts_saipe: 382,099 rows x 10 cols
#   [PASS] 13c: curl::multi_download 268,963,550 (status 200) + view-safe read: 3,790,415 rows x 52 cols
# 
# PASS 3/3
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
