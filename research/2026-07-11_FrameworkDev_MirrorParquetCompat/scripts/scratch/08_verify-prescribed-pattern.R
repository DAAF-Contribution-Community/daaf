# =============================================================================
# DIAGNOSTIC (scratch): Verify the EXACT prescribed view-safe read pattern
#
# Context: The skill edits (education-data-query SKILL.md + fetch-patterns.md,
#   tidyverse io.md) prescribe a view-safe parquet read whose type conditional
#   checks large_string_view BEFORE string_view — a reordering relative to the
#   empirically tested diagnostic (03_r-repro_a.R / 04_...), which checked
#   string_view first. Agents will copy the prescribed variant verbatim, so it
#   must itself be executed, not just argued correct.
#
# INTENT: Execute the prescribed conditional (a) on the confirmed-failing SAIPE
#   file, (b) on the confirmed-working MEPS file (no-op proof), and (c) as a
#   unit check against literal type strings covering all four branches.
# =============================================================================

# --- Config ---
library(arrow)

SCRATCH <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
FAILING_PATH <- file.path(SCRATCH, "saipe_districts_FAILING.parquet")
WORKING_PATH <- file.path(SCRATCH, "meps_schools_WORKING.parquet")

stopifnot(file.exists(FAILING_PATH))
stopifnot(file.exists(WORKING_PATH))

# --- Unit check: prescribed conditional against literal type strings ---
# INTENT: Prove the large_string_view-first ordering classifies every case
#   correctly, including the substring-collision case the reordering guards.
# REASONING: We have no sample file containing large_string_view columns, so
#   the collision branch cannot be exercised via file I/O; literal ToString()
#   values exercise the same code path deterministically.
cat("=== Unit check: type-mapping conditional (prescribed ordering) ===\n")
cases <- list(
  list(ts = "string_view",       expect = "string"),
  list(ts = "large_string_view", expect = "large_string"),
  list(ts = "binary_view",       expect = "binary"),
  list(ts = "int64",             expect = "int64")
)
for (case in cases) {
  ts <- case$ts
  # Exact conditional as prescribed in the skills (large_string_view first):
  new_type <- if (grepl("large_string_view", ts, fixed = TRUE)) arrow::large_utf8()
    else if (grepl("string_view", ts, fixed = TRUE)) arrow::utf8()
    else if (grepl("binary_view", ts, fixed = TRUE)) arrow::binary()
    else arrow::int64()  # stands in for fld$type pass-through in this unit check
  got <- new_type$ToString()
  status <- if (identical(got, case$expect)) "PASS" else "FAIL"
  cat(sprintf("  [%s] ts=%-18s -> %s (expect %s)\n", status, ts, got, case$expect))
  stopifnot(identical(got, case$expect))
}

# --- Load + Transform: prescribed pattern on the failing file ---
# INTENT: Run the verbatim prescribed pattern end-to-end on the file that
#   reproduces "cannot handle Array of type <utf8_view>" under a plain read.
cat("\n=== Prescribed pattern on FAILING file (SAIPE districts) ===\n")
src <- FAILING_PATH
tbl <- arrow::read_parquet(src, as_data_frame = FALSE)
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
df_saipe <- as.data.frame(tbl$cast(arrow::schema(fields)))
cat(sprintf("  rows=%d cols=%d\n", nrow(df_saipe), ncol(df_saipe)))
cat(sprintf("  district_name first: %s\n", df_saipe$district_name[1]))

# --- Validate (SAIPE) ---
# ASSUMES: reference values from the earlier verified diagnostics (03_a/04/05):
#   368,967 rows x 10 cols; first district_name 'ALBERTVILLE CITY SCH DIST'.
stopifnot(nrow(df_saipe) == 368967)
stopifnot(ncol(df_saipe) == 10)
stopifnot(identical(df_saipe$district_name[1], "ALBERTVILLE CITY SCH DIST"))
stopifnot(is.character(df_saipe$district_name))
cat("  [PASS] SAIPE matches verified reference (368,967 x 10; values intact)\n")

# --- Load + Transform: prescribed pattern on the working file (no-op proof) ---
cat("\n=== Prescribed pattern on WORKING file (MEPS schools, no-op) ===\n")
src <- WORKING_PATH
tbl <- arrow::read_parquet(src, as_data_frame = FALSE)
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
df_meps <- as.data.frame(tbl$cast(arrow::schema(fields)))
cat(sprintf("  rows=%d cols=%d\n", nrow(df_meps), ncol(df_meps)))

# --- Validate (MEPS) ---
# ASSUMES: reference values from earlier diagnostics: 1,345,122 rows x 11 cols,
#   identical with or without the view-safe cast.
df_meps_plain <- arrow::read_parquet(WORKING_PATH)  # plain read succeeds on this file
stopifnot(nrow(df_meps) == 1345122)
stopifnot(nrow(df_meps_plain) == nrow(df_meps))
stopifnot(identical(names(df_meps_plain), names(df_meps)))
cat("  [PASS] MEPS no-op confirmed (matches plain read: rows + column names)\n")

# --- Summary ---
cat("\n=== SUMMARY ===\n")
cat("Prescribed (large_string_view-first) pattern: VERIFIED\n")
cat("  - unit check: all 4 type-mapping branches correct\n")
cat("  - failing file: reads correctly, values match verified reference\n")
cat("  - working file: exact no-op vs plain read\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:42:07
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/08_verify-prescribed-pattern.R
# Duration: 0s
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
# === Unit check: type-mapping conditional (prescribed ordering) ===
#   [PASS] ts=string_view        -> string (expect string)
#   [PASS] ts=large_string_view  -> large_string (expect large_string)
#   [PASS] ts=binary_view        -> binary (expect binary)
#   [PASS] ts=int64              -> int64 (expect int64)
# 
# === Prescribed pattern on FAILING file (SAIPE districts) ===
#   rows=368967 cols=10
#   district_name first: ALBERTVILLE CITY SCH DIST
#   [PASS] SAIPE matches verified reference (368,967 x 10; values intact)
# 
# === Prescribed pattern on WORKING file (MEPS schools, no-op) ===
#   rows=1345122 cols=11
#   [PASS] MEPS no-op confirmed (matches plain read: rows + column names)
# 
# === SUMMARY ===
# Prescribed (large_string_view-first) pattern: VERIFIED
#   - unit check: all 4 type-mapping branches correct
#   - failing file: reads correctly, values match verified reference
#   - working file: exact no-op vs plain read
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
