# Full-column hash comparison (R side) using the canonical view-safe read.
#
# INTENT: recompute the SAME per-column digests as 06 (Python) over the ENTIRE
#   column, using the R view-safe read, then compare digests directly. Matching
#   digests prove whole-column value + byte + multiplicity equivalence — not just
#   the 10-row sample from 04. Any single mangled value anywhere flips the digest.
#
# The digest algorithm must be byte-identical to 06's: sort unique (value,count)
#   pairs, hash raw UTF-8 bytes + sep + count-ascii + sep. For ints, sort by
#   numeric value, hash decimal-string + count. NULL handled with the same tokens.

# --- Config ---
library(arrow)
library(jsonlite)
library(bit64)
library(digest)

scratch <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
py_path <- file.path(scratch, "fullcol_python.json")
out_path <- file.path(scratch, "fullcol_r.json")

targets <- list(
  list(key = "saipe",   file = "saipe_districts_FAILING.parquet", cols = c("district_name"), kind = "str"),
  list(key = "crdc",    file = "crdc_discipline_2017.parquet",    cols = c("crdc_id", "ncessch", "leaid"), kind = "str"),
  list(key = "meps",    file = "meps_schools_WORKING.parquet",    cols = c("ncessch", "ncessch_num"), kind = "int"),
  list(key = "edfacts", file = "edfacts_grad_rates_2018.parquet", cols = c("ncessch", "ncessch_num"), kind = "int")
)

# --- View-safe read (verbatim canonical pattern) ---
read_viewsafe <- function(path, columns = NULL) {
  tbl <- arrow::read_parquet(path, as_data_frame = FALSE)
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
  if (!is.null(columns)) df <- df[, columns, drop = FALSE]
  df
}

# REASONING: streaming sha256 to byte-match Python's incremental h.update() calls.
#   digest::sha256 via a serializer won't match; instead build the exact byte stream
#   in a raw vector then hash once. We assemble per-pair chunks identical to 06.
digest_str_col <- function(x) {
  # value_counts equivalent: table over character (NA handled separately)
  is_na <- is.na(x)
  n_null <- sum(is_na)
  nonna <- x[!is_na]
  tab <- table(nonna, useNA = "no")
  vals <- names(tab)
  cnts <- as.integer(tab)
  # sort by value ascending (match Python sort on the string; nulls_last)
  ord <- order(vals)
  vals <- vals[ord]; cnts <- cnts[ord]
  # Python iterates NULL row in-place within the value-sorted vc (nulls_last), so
  # after all non-null pairs, if n_null>0 the NULL token pair appears LAST.
  # REASONING: build the byte stream exactly as 06: for each pair -> UTF8(value)+0x01
  #   + ascii(count)+0x02 ; NULL pair -> 0x00 NULL 0x00 + ascii(count) + 0x02.
  con <- raw(0)
  chunks <- vector("list", length(vals) + as.integer(n_null > 0))
  j <- 1
  for (i in seq_along(vals)) {
    chunks[[j]] <- c(charToRaw(enc2utf8(vals[i])), as.raw(0x01),
                     charToRaw(as.character(cnts[i])), as.raw(0x02)); j <- j + 1
  }
  if (n_null > 0) {
    chunks[[j]] <- c(as.raw(0x00), charToRaw("NULL"), as.raw(0x00),
                     charToRaw(as.character(n_null)), as.raw(0x02))
  }
  stream <- do.call(c, chunks)
  dig <- digest::digest(stream, algo = "sha256", serialize = FALSE)
  list(digest = dig, n_distinct = length(vals) + as.integer(n_null > 0), n_null = as.integer(n_null))
}

digest_int_col <- function(x) {
  is_na <- is.na(x)
  n_null <- sum(is_na)
  nonna <- x[!is_na]
  # REASONING: unique values with counts. For integer64 use bit64-aware table via
  #   as.character keys (exact), counting duplicates. Sort by numeric value.
  keys <- as.character(nonna)  # exact decimal strings (integer64-safe)
  tabc <- table(keys)
  uval <- names(tabc)
  ucnt <- as.integer(tabc)
  # sort by NUMERIC value — use integer64 ordering to avoid lexical order mismatch
  numkey <- as.integer64(uval)
  ord <- order(numkey)
  uval <- uval[ord]; ucnt <- ucnt[ord]
  chunks <- vector("list", length(uval))
  for (i in seq_along(uval)) {
    chunks[[i]] <- c(charToRaw(uval[i]), as.raw(0x01),
                     charToRaw(as.character(ucnt[i])), as.raw(0x02))
  }
  stream <- do.call(c, chunks)
  if (n_null > 0) {
    stream <- c(stream, as.raw(0x00), charToRaw("NULL"), as.raw(0x00),
                charToRaw(as.character(n_null)))
  }
  dig <- digest::digest(stream, algo = "sha256", serialize = FALSE)
  list(digest = dig, n_distinct = length(uval), n_null = as.integer(n_null))
}

# --- Load + digest ---
result <- list(engine = "arrow_r", columns = list())
for (t in targets) {
  df <- read_viewsafe(file.path(scratch, t$file), columns = t$cols)
  cat("\n###", t$key, ":", paste(t$cols, collapse = ","), "(", t$kind, ")\n")
  for (c in t$cols) {
    x <- df[[c]]
    d <- if (t$kind == "str") digest_str_col(x) else digest_int_col(x)
    result$columns[[paste0(t$key, ".", c)]] <- d
    cat(sprintf("    %-14s digest=%s... distinct=%d null=%d\n",
                c, substr(d$digest, 1, 16), d$n_distinct, d$n_null))
  }
}

# --- Save ---
writeLines(toJSON(result, auto_unbox = TRUE, null = "null", pretty = TRUE), out_path)
cat("\nWrote", out_path, "\n")

# --- Compare against Python digests inline ---
py <- fromJSON(py_path, simplifyVector = FALSE)
cat("\n", strrep("=", 78), "\n")
cat("FULL-COLUMN DIGEST COMPARISON (Python vs R view-safe)\n")
cat(strrep("=", 78), "\n")
all_ok <- TRUE
for (name in names(result$columns)) {
  pc <- py$columns[[name]]
  rc <- result$columns[[name]]
  match_dig <- identical(pc$digest, rc$digest)
  match_distinct <- identical(as.integer(pc$n_distinct), as.integer(rc$n_distinct))
  match_null <- identical(as.integer(pc$n_null), as.integer(rc$n_null))
  ok <- match_dig && match_distinct && match_null
  if (!ok) all_ok <- FALSE
  cat(sprintf("  %-22s digest=%s distinct=%s null=%s  => %s\n",
              name,
              if (match_dig) "MATCH" else "DIFFER",
              if (match_distinct) "MATCH" else sprintf("DIFFER(py=%s,r=%s)", pc$n_distinct, rc$n_distinct),
              if (match_null) "MATCH" else sprintf("DIFFER(py=%s,r=%s)", pc$n_null, rc$n_null),
              if (ok) "PASS" else "FAIL"))
}
cat("\nWHOLE-COLUMN VERDICT:", if (all_ok) "PASS — every risk column byte/value-equivalent end-to-end" else "FAIL — see DIFFER above", "\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:32:08
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/07_r-fullcol-hash.R
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
# Loading required package: bit
# 
# Attaching package: ‘bit’
# 
# The following object is masked from ‘package:base’:
# 
#     xor
# 
# Attaching package bit64
# package:bit64 (c) 2011-2017 Jens Oehlschlaegel
# creators: integer64 runif64 seq :
# coercion: as.integer64 as.vector as.logical as.integer as.double as.character as.bitstring
# logical operator: ! & | xor != == < <= >= >
# arithmetic operator: + - * / %/% %% ^
# math: sign abs sqrt log log2 log10
# math: floor ceiling trunc round
# querying: is.integer64 is.vector [is.atomic} [length] format print str
# values: is.na is.nan is.finite is.infinite
# aggregation: any all min max range sum prod
# cumulation: diff cummin cummax cumsum cumprod
# access: length<- [ [<- [[ [[<-
# combine: c rep cbind rbind as.data.frame
# WARNING don't use as subscripts
# WARNING semantics differ from integer
# for more help type ?bit64
# 
# Attaching package: ‘bit64’
# 
# The following object is masked from ‘package:utils’:
# 
#     hashtab
# 
# The following objects are masked from ‘package:base’:
# 
#     :, %in%, colSums, is.double, match, order, rank, rowSums
# 
# 
# ### saipe : district_name ( str )
# Error in district_name(as.raw(c(0x41, 0x20, 0x43, 0x20, 0x43, 0x45, 0x4e,  : 
#   could not find function "district_name"
# Calls: digest_str_col -> do.call
# Execution halted
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
