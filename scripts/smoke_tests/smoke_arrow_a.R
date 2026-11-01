# smoke_arrow.R -- Smoke test for arrow (Apache Arrow R bindings)
# Validates: parquet round-trip with varied column types (int, double,
#            character, Date, POSIXct), value fidelity after write+read,
#            and arrow build-feature availability (compression codecs).
# Part of the Noble base-image migration T3 functional tier: arrow links
# against the system Arrow/parquet C++ libraries, so a value-fidelity
# round-trip is the migration risk probe (glibc/GDAL-adjacent lib jumps).
#
# Scratch files are written under a per-script working directory in the repo's
# tool scratch folder (NEVER /tmp -- /tmp is outside the backup/audit boundary
# per CLAUDE.md). Cleanup uses tryCatch(finally=) rather than on.exit(): a
# top-level on.exit() does NOT fire under `Rscript` (verified 2026-07-14), so
# it would leak the scratch dir. finally{} runs on both success and error.
#
# --- Revision note (_a, 2026-11-01) ---
# The working folder moves. smoke_arrow.R wrote its parquet file to
# arrow_smoke_work/ beside the script, inside the tracked scripts/smoke_tests/
# folder, which git does not ignore, so a folder left by an interrupted run
# showed up as an untracked file there. This revision uses the repo's tool
# scratch folder, /daaf/scripts/scratch/smoke_arrow_work/ (CLAUDE.md § Scratch
# Files), like the other smoke tests: cleared of anything a failed run left
# behind and created in Config, and removed by the existing finally{} block.
# The path is hard-coded because smoke tests run only inside the DAAF
# container at /daaf, and CI runs log-stripped copies staged under
# scripts/scratch/smoke_live/, where a script-relative folder would land
# somewhere else. Test logic and the Test 1 version lines are unchanged.

# --- Config ---
library(arrow)

cat("=== arrow Smoke Test ===\n\n")

# Working folder for this test's temp files (tool scratch, never /tmp).
# Hard-coded in-container path: fail loudly when run outside the container.
stopifnot(dir.exists("/daaf/scripts"))
work_dir <- "/daaf/scripts/scratch/smoke_arrow_work"
unlink(work_dir, recursive = TRUE)  # clear a folder left by a failed run
dir.create(work_dir, showWarnings = FALSE, recursive = TRUE)
stopifnot(dir.exists(work_dir))

tryCatch({

  # --- Test 1: Version + build features ---
  cat("Test 1: Version and build features\n")
  arrow_ver <- as.character(packageVersion("arrow"))
  cat("  arrow:", arrow_ver, "\n")
  stopifnot(numeric_version(arrow_ver) >= "10.0.0")

  info <- arrow::arrow_info()
  # arrow_info()$capabilities is a named logical vector of build feature flags
  caps <- info$capabilities
  cat("  Capabilities:\n")
  for (nm in names(caps)) {
    cat("    ", nm, ": ", caps[[nm]], "\n", sep = "")
  }
  # Parquet + at least one compression codec are required for DAAF's parquet-only
  # data policy. snappy is the parquet default and must be present.
  stopifnot("snappy" %in% names(caps))
  stopifnot(isTRUE(caps[["snappy"]]))
  cat("  PASS: arrow built with snappy compression\n\n")

  # --- Test 2: Build a data.frame with varied types ---
  cat("Test 2: Construct varied-type data.frame\n")
  df <- data.frame(
    i    = c(1L, 2L, 3L, 4L),
    x    = c(1.5, 2.25, -3.75, 0.0),
    s    = c("alpha", "beta", "gamma", "delta"),
    d    = as.Date(c("2026-01-01", "2026-04-15", "2026-07-14", "2025-12-31")),
    ts   = as.POSIXct(
             c("2026-01-01 08:30:00", "2026-04-15 12:00:00",
               "2026-07-14 17:45:30", "2025-12-31 23:59:59"),
             tz = "UTC"),
    stringsAsFactors = FALSE
  )
  stopifnot(nrow(df) == 4)
  stopifnot(inherits(df$d, "Date"))
  stopifnot(inherits(df$ts, "POSIXct"))
  cat("  Rows:", nrow(df), "Cols:", ncol(df), "\n")
  cat("  PASS\n\n")

  # --- Test 3: Parquet round-trip with value fidelity ---
  cat("Test 3: write_parquet() / read_parquet() round-trip\n")
  pq_path <- file.path(work_dir, "roundtrip.parquet")
  write_parquet(df, pq_path, compression = "snappy")
  stopifnot(file.exists(pq_path))
  stopifnot(file.info(pq_path)$size > 0)

  df_read <- read_parquet(pq_path)
  stopifnot(nrow(df_read) == nrow(df))
  stopifnot(identical(names(df_read), names(df)))

  # Value fidelity across every type. read_parquet returns a tibble; coerce to
  # data.frame for a direct identical() comparison of values.
  df_read <- as.data.frame(df_read)
  stopifnot(identical(df_read$i, df$i))
  stopifnot(identical(df_read$x, df$x))
  stopifnot(identical(df_read$s, df$s))
  stopifnot(identical(df_read$d, df$d))
  # POSIXct: compare numeric instants (tz attribute round-trips as UTC).
  stopifnot(all(as.numeric(df_read$ts) == as.numeric(df$ts)))
  cat("  Parquet file:", file.info(pq_path)$size, "bytes\n")
  cat("  All columns round-tripped with identical values\n")
  cat("  PASS\n\n")

  # --- Test 4: Arrow Table interconversion ---
  cat("Test 4: as_arrow_table() / as.data.frame() interconversion\n")
  tbl <- arrow::as_arrow_table(df)
  stopifnot(inherits(tbl, "Table"))
  stopifnot(tbl$num_rows == 4)
  back <- as.data.frame(tbl)
  stopifnot(identical(as.data.frame(back)$s, df$s))
  cat("  Table rows:", tbl$num_rows, "cols:", tbl$num_columns, "\n")
  cat("  PASS\n\n")

  # --- Summary ---
  cat("=== All 4 tests PASSED ===\n")
  cat("Tested: arrow", arrow_ver, "(parquet round-trip + snappy compression)\n")

}, finally = {
  # Remove scratch on both success and error (on.exit is unreliable here).
  unlink(work_dir, recursive = TRUE)
})


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-11-01 19:43:40
# Command: Rscript /daaf/scripts/smoke_tests/smoke_arrow_a.R
# Duration: 1s
# Exit code: 0
# Capture: COMPLETE
#
# --- STDOUT ---
# 
# Attaching package: ‘arrow’
# 
# The following object is masked from ‘package:utils’:
# 
#     timestamp
# 
# === arrow Smoke Test ===
# 
# Test 1: Version and build features
#   arrow: 23.0.1.2 
#   Capabilities:
#     acero: TRUE
#     dataset: TRUE
#     substrait: FALSE
#     parquet: TRUE
#     json: TRUE
#     s3: TRUE
#     gcs: TRUE
#     utf8proc: TRUE
#     re2: TRUE
#     snappy: TRUE
#     gzip: TRUE
#     brotli: TRUE
#     zstd: TRUE
#     lz4: TRUE
#     lz4_frame: TRUE
#     lzo: FALSE
#     bz2: TRUE
#   PASS: arrow built with snappy compression
# 
# Test 2: Construct varied-type data.frame
#   Rows: 4 Cols: 5 
#   PASS
# 
# Test 3: write_parquet() / read_parquet() round-trip
#   Parquet file: 2174 bytes
#   All columns round-tripped with identical values
#   PASS
# 
# Test 4: as_arrow_table() / as.data.frame() interconversion
#   Table rows: 4 cols: 5 
#   PASS
# 
# === All 4 tests PASSED ===
# Tested: arrow 23.0.1.2 (parquet round-trip + snappy compression)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
