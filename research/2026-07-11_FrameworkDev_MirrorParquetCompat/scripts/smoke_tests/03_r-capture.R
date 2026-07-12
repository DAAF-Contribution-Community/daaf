# R canonical view-safe read capture for the mirror parquet equivalence audit.
#
# INTENT: read each test parquet via the CANONICAL DAAF view-safe R path (read as
#   Arrow Table with as_data_frame=FALSE, cast any *_view types to materialized
#   equivalents, then convert) and emit the SAME JSON capture schema the Python
#   script produced. A third script diffs the two JSON files programmatically.
#
# The view-safe read is copied verbatim from fetch-patterns.md lines ~247-261 so
# this test exercises exactly the documented pattern, not a paraphrase.

# --- Config ---
library(arrow)
library(jsonlite)
library(bit64)

scratch <- "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
out_path <- file.path(scratch, "capture_r.json")

# INTENT: document the int64 downcast option in effect for this run (unset => TRUE:
#   arrow downcasts int64 to R integer when values fit in 32 bits, else integer64).
int64_downcast_opt <- getOption("arrow.int64_downcast")
cat("arrow.int64_downcast option:",
    if (is.null(int64_downcast_opt)) "UNSET (default TRUE)" else as.character(int64_downcast_opt), "\n")
cat("arrow version:", as.character(packageVersion("arrow")), "\n")

sentinels <- c(-1, -2, -3)
two_31 <- 2^31

# (dataset_key, filename, pkey cols, id cols) — must match the Python DATASETS list.
datasets <- list(
  list(key = "saipe",   file = "saipe_districts_FAILING.parquet", pkey = c("year", "leaid"),    ids = c("leaid")),
  list(key = "meps",    file = "meps_schools_WORKING.parquet",    pkey = c("year", "ncessch"),  ids = c("ncessch", "leaid")),
  list(key = "edfacts", file = "edfacts_grad_rates_2018.parquet", pkey = c("year", "ncessch"),  ids = c("ncessch", "leaid")),
  list(key = "crdc",    file = "crdc_discipline_2017.parquet",    pkey = c("year", "ncessch"),  ids = c("crdc_id", "ncessch", "leaid")),
  list(key = "ipeds",   file = "ipeds_finance.parquet",           pkey = c("year", "unitid"),   ids = c("unitid"))
)

# REASONING: canonical string rendering to match Python. integer64 -> exact decimal
#   via bit64 as.character (no precision loss). plain integer/double integers ->
#   format(x, scientific=FALSE, trim=TRUE). doubles (floats) -> tagged "float" and
#   compared with tolerance by the differ. logical -> bool. character -> str.
render_cell <- function(v, cls) {
  if (is.na(v)) {
    # ASSUMES: NaN vs NA — R doubles: is.nan() distinguishes. For our tagged floats
    #   we surface "NaN" separately below; plain NA -> null.
    if (cls == "float" && is.nan(v)) return(list(t = "float", v = "NaN"))
    return(list(t = "null", v = NULL))
  }
  if (cls == "int") {
    # REASONING: integer64 and integer both routed here; as.character on integer64
    #   is exact; on integer/double we format without scientific notation.
    if (inherits(v, "integer64")) return(list(t = "int", v = as.character(v)))
    return(list(t = "int", v = format(v, scientific = FALSE, trim = TRUE)))
  }
  if (cls == "float") {
    # REASONING: use full-precision repr; differ applies tolerance so exact string
    #   form need not match Python's repr byte-for-byte.
    return(list(t = "float", v = format(v, digits = 17, scientific = TRUE, trim = TRUE)))
  }
  if (cls == "bool") return(list(t = "bool", v = as.logical(v)))
  list(t = "str", v = as.character(v))
}

# Map an R vector's class to our dtype_class taxonomy.
class_of <- function(x) {
  if (inherits(x, "integer64")) return("int")
  if (is.integer(x)) return("int")
  if (is.numeric(x)) return("float")   # double
  if (is.logical(x)) return("bool")
  if (is.character(x)) return("str")
  "other"
}

# --- View-safe read (VERBATIM canonical pattern) ---
read_viewsafe <- function(path) {
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
  as.data.frame(tbl$cast(arrow::schema(fields)))
}

# --- Load + Profile ---
result <- list(engine = "arrow_r",
               arrow_version = as.character(packageVersion("arrow")),
               int64_downcast = if (is.null(int64_downcast_opt)) "unset_default_true" else as.character(int64_downcast_opt),
               datasets = list())

for (ds in datasets) {
  cat("\n###", ds$key, ":", ds$file, "\n")
  df <- read_viewsafe(file.path(scratch, ds$file))
  cols <- names(df)
  classes <- vapply(cols, function(c) class_of(df[[c]]), character(1))
  names(classes) <- cols
  # dtype string as R sees it: primary class token
  dtypes <- vapply(cols, function(c) {
    x <- df[[c]]
    if (inherits(x, "integer64")) "integer64"
    else paste(class(x), collapse = ",")
  }, character(1))
  names(dtypes) <- cols
  cat("    shape:", nrow(df), "x", ncol(df), "\n")

  cap <- list(
    shape = c(nrow(df), ncol(df)),
    columns = cols,
    dtypes = as.list(dtypes),
    dtype_class = as.list(classes),
    null_counts = list(),
    sentinel_counts = list(),
    int_stats = list(),
    string_integrity = list(),
    distinct_counts = list(),
    sample_rows = list()
  )

  # --- null counts ---
  for (c in cols) {
    cap$null_counts[[c]] <- sum(is.na(df[[c]]))
  }

  # --- sentinel counts (numeric cols) ---
  for (c in cols) {
    if (classes[[c]] %in% c("int", "float")) {
      x <- df[[c]]
      sc <- list()
      for (s in sentinels) {
        # REASONING: integer64 compares fine against numeric literal via bit64.
        #   NA excluded by sum(..., na.rm=TRUE).
        sc[[as.character(s)]] <- sum(x == s, na.rm = TRUE)
      }
      cap$sentinel_counts[[c]] <- sc
    }
  }

  # --- int stats + int64 depth ---
  for (c in cols) {
    if (classes[[c]] == "int") {
      x <- df[[c]]
      xnn <- x[!is.na(x)]
      if (length(xnn) == 0) {
        cap$int_stats[[c]] <- list(min = NULL, max = NULL, exceeds_2_31 = FALSE,
                                   dtype = dtypes[[c]], r_is_integer64 = inherits(x, "integer64"))
        next
      }
      cmin <- min(xnn); cmax <- max(xnn)
      # REASONING: exceed check via numeric magnitude; for integer64 use as.numeric
      #   only for the >=2^31 test (magnitude), but render min/max exactly via char.
      mag_min <- suppressWarnings(as.numeric(cmin)); mag_max <- suppressWarnings(as.numeric(cmax))
      exceeds <- (abs(mag_min) >= two_31) || (abs(mag_max) >= two_31)
      render_int <- function(v) if (inherits(v, "integer64")) as.character(v) else format(v, scientific = FALSE, trim = TRUE)
      cap$int_stats[[c]] <- list(
        min = render_int(cmin),
        max = render_int(cmax),
        exceeds_2_31 = exceeds,
        dtype = dtypes[[c]],
        r_is_integer64 = inherits(x, "integer64")
      )
    }
  }

  # --- string integrity ---
  for (c in cols) {
    if (classes[[c]] != "str") next
    x <- df[[c]]
    n_null <- sum(is.na(x))
    n_empty <- sum(x == "", na.rm = TRUE)
    si <- list(n_null = n_null, n_empty = n_empty)
    if (c %in% ds$ids) {
      nonna <- x[!is.na(x)]
      lead <- nonna[startsWith(nonna, "0") & nchar(nonna) > 1]
      si$n_leading_zero <- length(lead)
      si$leading_zero_samples <- head(sort(unique(lead)), 5)
    }
    # non-ASCII inventory
    nonna <- x[!is.na(x)]
    # REASONING: detect any codepoint > 127. Use utf8ToInt per element; a value has
    #   non-ASCII if max codepoint > 127.
    has_na_char <- vapply(nonna, function(s) {
      cps <- utf8ToInt(s)
      length(cps) > 0 && max(cps) > 127
    }, logical(1))
    if (any(has_na_char)) {
      na_vals <- head(sort(unique(nonna[has_na_char])), 10)
      si$non_ascii_count_est <- sum(has_na_char)
      si$non_ascii_samples <- lapply(na_vals, function(v) {
        list(value = v, codepoints = as.integer(utf8ToInt(v)))
      })
    } else {
      si$non_ascii_count_est <- 0L
      si$non_ascii_samples <- list()
    }
    cap$string_integrity[[c]] <- si
  }

  # --- distinct counts on key cols ---
  key_cols <- unique(c(ds$pkey, ds$ids))
  for (c in key_cols) {
    if (c %in% cols) {
      cap$distinct_counts[[c]] <- length(unique(df[[c]]))
    }
  }

  # --- deterministic sample: sort by pkey, first5 + last5 ---
  sort_cols <- ds$pkey[ds$pkey %in% cols]
  if (length(sort_cols) == 0) sort_cols <- cols[1]
  # REASONING: order() with multiple keys; NA sorted last to match Python nulls_last.
  ord <- do.call(order, c(lapply(sort_cols, function(c) df[[c]]), list(na.last = TRUE)))
  dfs <- df[ord, , drop = FALSE]
  n <- nrow(dfs)
  head_idx <- seq_len(min(5, n))
  tail_idx <- if (n >= 5) seq(n - 4, n) else seq_len(n)
  rows_to_cells <- function(idxset) {
    lapply(idxset, function(i) {
      row <- lapply(cols, function(c) render_cell(dfs[[c]][i], classes[[c]]))
      names(row) <- cols
      row
    })
  }
  cap$sample_rows <- list(
    sort_cols = sort_cols,
    head5 = rows_to_cells(head_idx),
    tail5 = rows_to_cells(tail_idx)
  )

  result$datasets[[ds$key]] <- cap
  cat("    captured:", length(cols), "cols\n")
}

# --- Save ---
# REASONING: auto_unbox so scalars serialize as JSON scalars (match Python); null
#   preserved; ensure integer64 already rendered to strings above so jsonlite never
#   sees a bare integer64 (which it would stringify inconsistently).
writeLines(toJSON(result, auto_unbox = TRUE, null = "null", pretty = TRUE, digits = NA), out_path)
cat("\nWrote", out_path, "\n")

# --- Summary ---
cat("\n", strrep("=", 70), "\n")
for (key in names(result$datasets)) {
  d <- result$datasets[[key]]
  int_cols <- names(d$int_stats)
  i64 <- int_cols[vapply(int_cols, function(c) isTRUE(d$int_stats[[c]]$r_is_integer64), logical(1))]
  exceed <- int_cols[vapply(int_cols, function(c) isTRUE(d$int_stats[[c]]$exceeds_2_31), logical(1))]
  cat(sprintf("%-9s shape=%dx%d integer64_cols=%s ge_2^31=%s\n",
              key, d$shape[1], d$shape[2],
              paste(i64, collapse = ","), paste(exceed, collapse = ",")))
}


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:27:19
# Command: Rscript /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/03_r-capture.R
# Duration: 86s
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
# arrow.int64_downcast option: UNSET (default TRUE) 
# arrow version: 23.0.1.2 
# 
# ### saipe : saipe_districts_FAILING.parquet 
#     shape: 368967 x 10 
#     captured: 10 cols
# 
# ### meps : meps_schools_WORKING.parquet 
#     shape: 1345122 x 11 
#     captured: 11 cols
# 
# ### edfacts : edfacts_grad_rates_2018.parquet 
#     shape: 274800 x 18 
#     captured: 18 cols
# 
# ### crdc : crdc_discipline_2017.parquet 
#     shape: 8487765 x 20 
#     captured: 20 cols
# 
# ### ipeds : ipeds_finance.parquet 
#     shape: 227084 x 141 
#     captured: 141 cols
# 
# Wrote /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/capture_r.json 
# 
#  ====================================================================== 
# saipe     shape=368967x10 integer64_cols= ge_2^31=
# meps      shape=1345122x11 integer64_cols=ncessch,ncessch_num ge_2^31=ncessch,ncessch_num
# edfacts   shape=274800x18 integer64_cols=ncessch_num,ncessch ge_2^31=ncessch_num,ncessch
# crdc      shape=8487765x20 integer64_cols= ge_2^31=
# ipeds     shape=227084x141 integer64_cols= ge_2^31=
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
