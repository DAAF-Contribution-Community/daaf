# =============================================================================
# VERIFICATION (smoke): fixed canonical single-file mirror loop (mirror_df)
#
# Context: Review found the documented loop's `df <<-` idiom collides with the
#   locked stats::df binding — at top level, `<<-` searches the package search
#   path (skipping globalenv), so `df <<- x` errors with "cannot change value of
#   locked binding for 'df'" even when `df <- NULL` exists in globalenv. The
#   canonical pattern in fetch-patterns.md was renamed to `mirror_df`.
#
# INTENT: (a) prove the mechanism (old name fails, new name works) at top level;
#   (b) execute the FIXED canonical loop verbatim against saipe/districts_saipe
#   (view-typed, 368,967 x 10) and confirm the huggingface mirror succeeds and
#   the `df <- mirror_df` handoff yields the expected data.
# =============================================================================

# --- Config ---
library(arrow)
library(dplyr)
library(readr)
library(yaml)

MIRRORS_YAML <- "/daaf/.claude/skills/education-data-query/references/mirrors.yaml"

# --- Probe: <<- name-collision mechanism at top level ---
# REASONING: tryCatch's expression evaluates in the calling (global) frame, so
#   `<<-` inside it behaves as top-level superassignment: it searches the package
#   search path first. `df` masks stats::df (locked) -> error. `mirror_df` masks
#   nothing -> assigns in globalenv.
cat("=== Probe: top-level <<- collision ===\n")
df <- NULL
probe_old <- tryCatch({ df <<- 42; "assigned" },
                      error = function(e) conditionMessage(e))
cat(sprintf("  old name (df <<-)       : %s\n", probe_old))
stopifnot(grepl("locked binding", probe_old, fixed = TRUE))

mirror_df <- NULL
probe_new <- tryCatch({ mirror_df <<- 42; "assigned" },
                      error = function(e) conditionMessage(e))
cat(sprintf("  new name (mirror_df <<-): %s\n", probe_new))
stopifnot(identical(probe_new, "assigned"))
stopifnot(identical(mirror_df, 42))
cat("  [PASS] mechanism confirmed: df fails, mirror_df works\n")

# --- Fixed canonical loop (verbatim structure from fetch-patterns.md) ---
cat("\n=== Fixed canonical single-file loop vs saipe/districts_saipe ===\n")
options(timeout = max(600, getOption("timeout")))

config <- yaml::read_yaml(MIRRORS_YAML)
mirrors <- config$mirrors
DATASET_PATH <- "saipe/districts_saipe"

last_error <- NULL
mirror_df <- NULL
mirror_used <- NA_character_

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

  if (identical(result, "success")) { mirror_used <- mirror_name; break }
}

if (is.null(mirror_df)) stop(paste("All mirrors failed. Last error:", conditionMessage(last_error)))

# Hand off to the conventional working name (as documented)
df <- mirror_df

# --- Validate ---
cat("\n=== VALIDATION ===\n")
cat(sprintf("  mirror used : %s\n", mirror_used))
cat(sprintf("  rows x cols : %s x %d\n", format(nrow(df), big.mark = ","), ncol(df)))
cat(sprintf("  district_name first: %s\n", df$district_name[1]))
stopifnot(identical(mirror_used, "huggingface"))
stopifnot(nrow(df) == 368967)
stopifnot(ncol(df) == 10)
stopifnot(identical(df$district_name[1], "ALBERTVILLE CITY SCH DIST"))
cat("  [PASS] Fixed canonical loop: huggingface succeeds, handoff intact,\n")
cat("         values match the verified reference.\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 23:51:07
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/10_verify-fixed-mirror-loop.R
# Duration: 3s
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
# === Probe: top-level <<- collision ===
#   old name (df <<-)       : cannot change value of locked binding for 'df'
#   new name (mirror_df <<-): assigned
#   [PASS] mechanism confirmed: df fails, mirror_df works
# 
# === Fixed canonical single-file loop vs saipe/districts_saipe ===
#   Trying huggingface: https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/saipe/districts_saipe.parquet
#   Success huggingface: 368,967 rows
# 
# === VALIDATION ===
#   mirror used : huggingface
#   rows x cols : 368,967 x 10
#   district_name first: ALBERTVILLE CITY SCH DIST
#   [PASS] Fixed canonical loop: huggingface succeeds, handoff intact,
#          values match the verified reference.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
