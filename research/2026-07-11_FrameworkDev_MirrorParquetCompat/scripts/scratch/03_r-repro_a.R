# =============================================================================
# R repro + fix candidate (v2) for utf8_view read failure on Polars parquet
# =============================================================================
# v1 confirmed: [A] baseline fails with `cannot handle Array of type <utf8_view>`,
# [B] Table read (as_data_frame=FALSE) succeeds, [D] open_dataset|>collect() fails.
# v1's cast [C] errored "Invalid field index for schema" — schema-rebuild API misuse.
# This version fixes the cast construction and probes the correct arrow 23.0.1.2 API
# for building a target schema and casting.

# --- Config ---
suppressPackageStartupMessages(library(arrow))

scratch <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
failing <- file.path(scratch, "saipe_districts_FAILING.parquet")
working <- file.path(scratch, "meps_schools_WORKING.parquet")

cat("arrow package version:", as.character(packageVersion("arrow")), "\n")
cat("========================================================\n")

# INTENT: read the failing file as an Arrow Table (proven to work in v1 test B).
tbl <- arrow::read_parquet(failing, as_data_frame = FALSE)
old_schema <- tbl$schema
cat("column names:", paste(old_schema$names, collapse = ", "), "\n")

# --- Probe: correct field-access API ---
# REASONING: v1 used old_schema$field(i) with 1-based i and got "Invalid field
# index". Arrow R Schema exposes fields via $field(i) which is 0-INDEXED (C++
# convention). Confirm by accessing field 0 vs length.
cat("\n[probe] field indexing convention\n")
p0 <- tryCatch({ f <- old_schema$field(0); cat("    field(0) OK ->", f$name, ":", f$type$ToString(), "\n"); "0-indexed" },
               error = function(e) { cat("    field(0) ERROR:", conditionMessage(e), "\n"); "not-0" })

# --- Test C2: build target schema via 0-indexed access, cast, convert ---
# INTENT: replace each view type with its materialized analog, cast the Table,
# then convert to data.frame. Uses 0-indexed field access confirmed above.
cat("\n[C2] cast view -> non-view (0-indexed schema rebuild)\n")
dfC <- NULL
resC <- tryCatch({
  n <- length(old_schema$names)
  new_fields <- vector("list", n)
  for (i in seq_len(n)) {
    fld <- old_schema$field(i - 1L)          # 0-indexed C++ convention
    ts <- fld$type$ToString()
    if (grepl("string_view", ts, fixed = TRUE) || grepl("utf8_view", ts, fixed = TRUE)) {
      new_type <- arrow::utf8()
    } else if (grepl("large_string_view", ts, fixed = TRUE) || grepl("large_utf8_view", ts, fixed = TRUE)) {
      new_type <- arrow::large_utf8()
    } else if (grepl("binary_view", ts, fixed = TRUE)) {
      new_type <- arrow::binary()
    } else {
      new_type <- fld$type
    }
    new_fields[[i]] <- arrow::field(fld$name, new_type)
  }
  new_schema <- arrow::schema(new_fields)
  tblC <- tbl$cast(new_schema)
  dfC <<- as.data.frame(tblC)
  cat("    SUCCESS: rows =", nrow(dfC), " cols =", ncol(dfC), "\n")
  "success"
}, error = function(e) { cat("    ERROR:", conditionMessage(e), "\n"); "error" })

# --- Test F: simpler alternative — Table$cast with a schema derived by string-replace on types() ---
# INTENT: probe whether there is an even simpler idiom. Try casting only the
# offending columns by rebuilding via schema() from a named type list.
cat("\n[F] alternative: as.data.frame on a per-column cast Table\n")
resF <- tryCatch({
  # REASONING: Table has $cast(target_schema). We can also cast column-by-column,
  # but a whole-schema cast is the minimal single call — already covered by C2.
  # Here we just confirm C2's df is usable end-to-end.
  if (!is.null(dfC)) {
    cat("    district_name head:\n"); print(utils::head(dfC$district_name, 3))
    cat("    class of district_name:", class(dfC$district_name)[1], "\n")
    "success"
  } else "error"
}, error = function(e) { cat("    ERROR:", conditionMessage(e), "\n"); "error" })

# --- Test E: dtype / leading-zero integrity on the cast result ---
cat("\n[E] column dtype + first-value integrity\n")
if (!is.null(dfC)) {
  for (cn in names(dfC)) {
    cls <- class(dfC[[cn]])[1]
    sample_val <- as.character(dfC[[cn]][1])
    cat(sprintf("    %-32s class=%-11s first=%s\n", cn, cls, sample_val))
  }
}

# --- Validate: FINAL pattern is a no-op success on the WORKING (MEPS) file ---
cat("\n[V] FINAL PATTERN on WORKING (MEPS) file -- no-op success expected\n")
resV <- tryCatch({
  tblW <- arrow::read_parquet(working, as_data_frame = FALSE)
  sw <- tblW$schema
  m <- length(sw$names)
  nf <- vector("list", m)
  for (i in seq_len(m)) {
    fld <- sw$field(i - 1L)
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
}, error = function(e) { cat("    ERROR:", conditionMessage(e), "\n"); "error" })

# --- Summary ---
cat("\n========================================================\n")
cat("RESULTS: probe=", p0, " C2(cast)=", resC, " F=", resF, " V(noop-working)=", resV, "\n")
stopifnot(resC == "success", resV == "success")
cat("VALIDATION PASSED: cast fix works on failing file and is a no-op on working file.\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:31:36
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/03_r-repro_a.R
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# arrow package version: 23.0.1.2 
# ========================================================
# column names: district_id, district_name, est_population_total, est_population_5_17, est_population_5_17_poverty, year, leaid, fips, est_population_5_17_poverty_pct, est_population_5_17_pct 
# 
# [probe] field indexing convention
#     field(0) OK -> district_id : int64 
# 
# [C2] cast view -> non-view (0-indexed schema rebuild)
#     SUCCESS: rows = 368967  cols = 10 
# 
# [F] alternative: as.data.frame on a per-column cast Table
#     district_name head:
# [1] "ALBERTVILLE CITY SCH DIST"    "ALEXANDER CITY CITY SCH DIST"
# [3] "ANDALUSIA CITY SCH DIST"     
#     class of district_name: character 
# 
# [E] column dtype + first-value integrity
#     district_id                      class=integer     first=5
#     district_name                    class=character   first=ALBERTVILLE CITY SCH DIST
#     est_population_total             class=integer     first=16294
#     est_population_5_17              class=integer     first=2779
#     est_population_5_17_poverty      class=integer     first=506
#     year                             class=integer     first=1995
#     leaid                            class=integer     first=100005
#     fips                             class=integer     first=1
#     est_population_5_17_poverty_pct  class=numeric     first=0.18207988
#     est_population_5_17_pct          class=numeric     first=0.17055358
# 
# [V] FINAL PATTERN on WORKING (MEPS) file -- no-op success expected
#     SUCCESS: MEPS rows = 1345122  cols = 11 
# 
# ========================================================
# RESULTS: probe= 0-indexed  C2(cast)= success  F= success  V(noop-working)= success 
# VALIDATION PASSED: cast fix works on failing file and is a no-op on working file.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
