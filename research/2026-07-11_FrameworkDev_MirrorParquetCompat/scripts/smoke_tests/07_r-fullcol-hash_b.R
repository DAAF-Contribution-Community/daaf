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

# INTENT: force C-locale byte collation so R's order() on strings sorts by raw
#   codepoint, matching Python polars .sort() (codepoint order). Without this, a
#   non-C locale would order multibyte/accented strings differently, breaking the
#   digest comparison even when the underlying VALUES are byte-identical. The digest
#   is order-sensitive by construction, so both sides must sort identically.
Sys.setlocale("LC_COLLATE", "C")

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
#   Build the byte stream via a rawConnection then hash once (serialize=FALSE).
#   FIX (v_a): prior do.call(c, chunks) crashed with "could not find function
#   <value>" — do.call dispatched on a named list element. Replaced with writeBin
#   into a rawConnection, which cannot mis-dispatch. Also switched table() ->
#   factor()+tabulate() so exact character values (incl. multibyte UTF-8) are kept
#   as levels rather than as possibly-mangled table dimnames.
digest_str_col <- function(x) {
  is_na <- is.na(x)
  n_null <- sum(is_na)
  nonna <- x[!is_na]
  f <- factor(nonna)
  vals <- levels(f)
  cnts <- tabulate(as.integer(f), nbins = length(vals))
  # sort by value ascending (match Python sort on the string; nulls_last)
  ord <- order(vals)
  vals <- vals[ord]; cnts <- cnts[ord]
  rc <- rawConnection(raw(0), "w")
  on.exit(close(rc))
  for (i in seq_along(vals)) {
    writeBin(charToRaw(enc2utf8(vals[i])), rc)
    writeBin(as.raw(0x01), rc)
    writeBin(charToRaw(as.character(cnts[i])), rc)
    writeBin(as.raw(0x02), rc)
  }
  if (n_null > 0) {
    writeBin(as.raw(0x00), rc); writeBin(charToRaw("NULL"), rc); writeBin(as.raw(0x00), rc)
    writeBin(charToRaw(as.character(n_null)), rc); writeBin(as.raw(0x02), rc)
  }
  stream <- rawConnectionValue(rc)
  dig <- digest::digest(stream, algo = "sha256", serialize = FALSE)
  list(digest = dig, n_distinct = length(vals) + as.integer(n_null > 0), n_null = as.integer(n_null))
}

digest_int_col <- function(x) {
  is_na <- is.na(x)
  n_null <- sum(is_na)
  nonna <- x[!is_na]
  # REASONING: exact decimal string keys (integer64-safe); factor+tabulate for counts.
  keys <- as.character(nonna)
  f <- factor(keys)
  uval <- levels(f)
  ucnt <- tabulate(as.integer(f), nbins = length(uval))
  # sort by NUMERIC value — integer64 ordering to avoid lexical mismatch with Python
  numkey <- as.integer64(uval)
  ord <- order(numkey)
  uval <- uval[ord]; ucnt <- ucnt[ord]
  rc <- rawConnection(raw(0), "w")
  on.exit(close(rc))
  for (i in seq_along(uval)) {
    writeBin(charToRaw(uval[i]), rc)
    writeBin(as.raw(0x01), rc)
    writeBin(charToRaw(as.character(ucnt[i])), rc)
    writeBin(as.raw(0x02), rc)
  }
  if (n_null > 0) {
    writeBin(as.raw(0x00), rc); writeBin(charToRaw("NULL"), rc); writeBin(as.raw(0x00), rc)
    writeBin(charToRaw(as.character(n_null)), rc)
  }
  stream <- rawConnectionValue(rc)
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
# Executed: 2026-07-11 19:34:01
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/07_r-fullcol-hash_b.R
# Duration: 9s
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
# [1] "C"
# 
# ### saipe : district_name ( str )
#     district_name  digest=21c3a400c9efb340... distinct=36517 null=0
# 
# ### crdc : crdc_id,ncessch,leaid ( str )
#     crdc_id        digest=6196ab3b1b441b68... distinct=97632 null=0
#     ncessch        digest=3f4c0027e2b70f2d... distinct=96570 null=81816
#     leaid          digest=5df4aee9ffffd8c9... distinct=16724 null=81816
# 
# ### meps : ncessch,ncessch_num ( int )
#     ncessch        digest=780c1afc2aeec29c... distinct=116681 null=0
#     ncessch_num    digest=780c1afc2aeec29c... distinct=116681 null=0
# 
# ### edfacts : ncessch,ncessch_num ( int )
#     ncessch        digest=8b41ac5fb6edefe6... distinct=22900 null=0
#     ncessch_num    digest=8b41ac5fb6edefe6... distinct=22900 null=0
# 
# Wrote /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/fullcol_r.json 
# 
#  ============================================================================== 
# FULL-COLUMN DIGEST COMPARISON (Python vs R view-safe)
# ============================================================================== 
#   saipe.district_name    digest=MATCH distinct=MATCH null=MATCH  => PASS
#   crdc.crdc_id           digest=MATCH distinct=MATCH null=MATCH  => PASS
#   crdc.ncessch           digest=MATCH distinct=MATCH null=MATCH  => PASS
#   crdc.leaid             digest=MATCH distinct=MATCH null=MATCH  => PASS
#   meps.ncessch           digest=MATCH distinct=MATCH null=MATCH  => PASS
#   meps.ncessch_num       digest=MATCH distinct=MATCH null=MATCH  => PASS
#   edfacts.ncessch        digest=MATCH distinct=MATCH null=MATCH  => PASS
#   edfacts.ncessch_num    digest=MATCH distinct=MATCH null=MATCH  => PASS
# 
# WHOLE-COLUMN VERDICT: PASS — every risk column byte/value-equivalent end-to-end 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
