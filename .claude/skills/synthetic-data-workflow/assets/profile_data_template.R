#!/usr/bin/env Rscript
# =============================================================================
# DISCLOSURE-CONTROLLED DATA PROFILER (R) -- DAAF synthetic-data-workflow
# Run on YOUR machine. Raw rows stay local; review BOTH reports before sharing.
# Self-contained: base R for CSV; parquet needs arrow, Stata/SPSS/SAS needs haven.
# Minimum-support and categorical-cell checks are NOT a privacy guarantee.
# Counts are records: establish locally whether records represent individuals.
# Flat, sequential; no DAAF imports, network calls, or raw-data output.
# =============================================================================

# --- Config (EDIT THESE) -----------------------------------------------------
INPUT_PATH            <- "data.csv"
DATASET_NAME          <- "dataset"
OUTPUT_DIR            <- "."          # local, non-shared folder
TIER                  <- 2            # 1, 2, or 3; T4 uses a different template
SUPPRESSION_THRESHOLD <- 5            # minimum usable support AND categorical cell threshold
MAX_CATEGORICAL_LEVELS <- 50
RELATIONSHIP_SPEC     <- list()       # c(outcome, predictor) or categorical pairs
# -----------------------------------------------------------------------------

# --- Config -----------------------------------------------------------------
REPORT_VERSION <- "2.0"
TEMPLATE_NAME <- "profile_data_template.R"
stopifnot(TIER %in% c(1, 2, 3), length(SUPPRESSION_THRESHOLD) == 1,
          is.finite(SUPPRESSION_THRESHOLD), SUPPRESSION_THRESHOLD >= 1,
          SUPPRESSION_THRESHOLD == floor(SUPPRESSION_THRESHOLD),
          MAX_CATEGORICAL_LEVELS >= 1, MAX_CATEGORICAL_LEVELS == floor(MAX_CATEGORICAL_LEVELS),
          grepl("^[A-Za-z0-9_-]+$", DATASET_NAME))
FULL_CUTOFF <- max(SUPPRESSION_THRESHOLD, 10)
PROBS <- c(.01, .05, .10, .25, .50, .75, .90, .95, .99)
PROB_NAMES <- c("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
EMAIL_RE <- "^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$"
PHONE_RE <- "^[+]?[0-9()[:space:].-]{7,}$"
DATE_RE <- "^[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}"
ID_NAME_RE <- "(^|_)(id|uuid|guid|email|phone|ssn|account|acct)($|_)"
json_path <- file.path(OUTPUT_DIR, paste0(DATASET_NAME, "_profile_report.json"))
txt_path <- file.path(OUTPUT_DIR, paste0(DATASET_NAME, "_profile_report.txt"))
# INTENT: preserve prior reports; REASONING: a rerun must not erase review evidence.
stopifnot(dir.exists(OUTPUT_DIR), !any(file.exists(c(json_path, txt_path))))

# --- Load -------------------------------------------------------------------
# INTENT: load locally without printing rows; ASSUMES: optional readers already exist.
ext <- tolower(tools::file_ext(INPUT_PATH))
if (ext == "csv") {
  df <- read.csv(INPUT_PATH, stringsAsFactors = FALSE, check.names = TRUE)
} else if (ext == "parquet") {
  if (!requireNamespace("arrow", quietly = TRUE)) stop("Reading parquet needs the arrow dependency")
  df <- as.data.frame(arrow::read_parquet(INPUT_PATH))
} else if (ext %in% c("dta", "sav", "sas7bdat")) {
  if (!requireNamespace("haven", quietly = TRUE)) stop("This format needs the haven dependency")
  df <- as.data.frame(switch(ext, dta = haven::read_dta(INPUT_PATH),
                            sav = haven::read_sav(INPUT_PATH), sas7bdat = haven::read_sas(INPUT_PATH)))
} else stop("Unsupported extension; use .csv/.parquet/.dta/.sav/.sas7bdat")
n_rows <- nrow(df)
n_cols <- ncol(df)
stopifnot(n_rows > 0, n_cols > 0, !anyDuplicated(names(df)))
for (pair in RELATIONSHIP_SPEC) stopifnot(length(pair) == 2, all(pair %in% names(df)))
cat(sprintf("Loaded %d rows x %d columns. No raw values printed.\n", n_rows, n_cols))

# --- Profile ----------------------------------------------------------------
columns <- list()
numeric_cols <- character(0)        # full, nonconstant marginals only
categ_cols <- character(0)
col_roles <- character(0)
for (cname in names(df)) {
  x <- df[[cname]]
  x_nn <- x[!is.na(x)]
  n_nonnull <- length(x_nn)
  n_distinct <- length(unique(x_nn))
  miss_rate <- round((n_rows - n_nonnull) / n_rows, 6)
  uniq_ratio <- if (n_nonnull) n_distinct / n_nonnull else 0
  # INTENT: refuse precision-unsupported numeric input BEFORE any double conversion.
  # REASONING: >= 2^53 is an ambiguity boundary for adjacent integer values in doubles.
  # ASSUMES: native integer64 text is exact; do not cast its payload to double to test it.
  # T1 releases no values and retains its existing schema-only behavior.
  if (TIER >= 2 && inherits(x, "integer64")) {
    magnitude <- sub("^-", "", as.character(x_nn))
    if (any(nchar(magnitude) > 16 | (nchar(magnitude) == 16 & magnitude >= "9007199254740992")))
      stop("Unsupported numeric precision/range: magnitude >= 2^53. No reports written; obtain a reviewed local precision-safe profiling path.", call. = FALSE)
  } else if (TIER >= 2 && is.numeric(x)) {
    if (any(is.finite(x_nn) & abs(x_nn) >= 2^53))
      stop("Unsupported numeric precision/range: magnitude >= 2^53. No reports written; obtain a reviewed local precision-safe profiling path.", call. = FALSE)
  }
  if (is.numeric(x) || (is.logical(x) && n_nonnull == 0)) {
    dtype <- if (all(is.finite(x_nn)) && all(x_nn == round(x_nn))) "integer" else "double"
  } else {
    dtype <- "string"
    x_nn <- as.character(x_nn)
  }
  # INTENT: identifier heuristics select structure-only treatment, not privacy certification.
  # ASSUMES: numeric measurements may be unique; uniqueness alone flags only strings.
  name_is_id <- grepl(ID_NAME_RE, tolower(cname))
  val_is_email <- dtype == "string" && n_nonnull > 0 && mean(grepl(EMAIL_RE, x_nn)) > .8
  val_is_phone <- dtype == "string" && n_nonnull > 0 &&
    mean(grepl(PHONE_RE, x_nn) & nchar(gsub("[^0-9]", "", x_nn)) >= 10) > .8
  is_identifier <- name_is_id || val_is_email || val_is_phone || (uniq_ratio > .95 && dtype == "string")
  role <- if (is_identifier) "identifier" else if (dtype != "string") "numeric" else
    if (n_distinct <= MAX_CATEGORICAL_LEVELS) "categorical" else "string"
  col_roles[cname] <- role
  col <- list(name = cname, dtype = dtype)
  if (TIER == 1) {
    columns[[length(columns) + 1]] <- col   # T1 remains strictly name/dtype only
    next
  }
  # Missingness denominator is ALL records, not the missing numerator. Cardinality stays.
  col <- c(col, list(role = role, missing_rate = miss_rate, nonmissing_n = n_nonnull,
                    n_distinct = n_distinct, uniqueness_ratio = round(uniq_ratio, 6), is_identifier = is_identifier))
  if (role == "numeric") {
    # INTENT: count finite contributors BEFORE computing value summaries.
    # REASONING: four identical values are unsupported; 5,000 identical values are supported.
    # ASSUMES: a record is the contribution unit; no identity deduplication here.
    vals <- as.numeric(x_nn)
    vals <- vals[is.finite(vals)]
    n <- length(vals)
    if (n_nonnull == 0) {
      num <- list(n = 0, all_missing = TRUE)
    } else if (n < SUPPRESSION_THRESHOLD) {
      num <- list(n = n, withheld = TRUE, reason = if (n == 0) "no_finite_values" else "insufficient_support")
    } else if (all(vals == vals[1])) {
      value <- round(vals[1], 6)
      num <- list(n = n, constant = TRUE, value = value, mean = value, sd = if (n > 1) 0 else NULL)
    } else if (n < FULL_CUTOFF) {
      qs <- round(as.numeric(stats::quantile(vals, c(.25, .50, .75), type = 7)), 6)
      num <- list(n = n, small_n = TRUE, percentiles = as.list(setNames(qs, c("p25", "p50", "p75"))))
    } else {
      qs <- round(as.numeric(stats::quantile(vals, PROBS, type = 7)), 6)
      num <- list(n = n, mean = round(mean(vals), 6), sd = round(stats::sd(vals), 6),
                  percentiles = as.list(setNames(qs, PROB_NAMES)))
      numeric_cols <- c(numeric_cols, cname)
    }
    col$numeric <- num
  } else if (role == "categorical") {
    # INTENT: preserve primary binning and complementary roll-in of rare levels.
    # REASONING: the __OTHER__ aggregate must not itself be a small visible cell.
    tbl <- sort(table(x_nn), decreasing = TRUE)
    # The literal reserved label joins the pool even when its own count is large.
    # This emits one unambiguous bucket; n_levels_binned includes that source level.
    keep <- tbl[tbl >= SUPPRESSION_THRESHOLD & names(tbl) != "__OTHER__"]
    other <- sum(tbl[tbl < SUPPRESSION_THRESHOLD | names(tbl) == "__OTHER__"])
    while (other > 0 && other < SUPPRESSION_THRESHOLD && length(keep)) {
      other <- other + as.numeric(keep[length(keep)])
      keep <- keep[-length(keep)]
    }
    levels <- list()
    for (i in seq_along(keep)) levels[[length(levels) + 1]] <- list(value = names(keep)[i], count = as.numeric(keep[i]))
    if (other >= SUPPRESSION_THRESHOLD) levels[[length(levels) + 1]] <- list(value = "__OTHER__", count = other)
    col$categorical <- list(n = n_nonnull, n_levels_binned = length(tbl) - length(keep), levels = levels)
    categ_cols <- c(categ_cols, cname)
  } else {
    # INTENT: lengths and pattern summaries also require actual nonmissing support.
    # REASONING: structure-only does not exempt a statistic from the support floor.
    if (n_nonnull < SUPPRESSION_THRESHOLD) {
      struct <- list(n = n_nonnull, withheld = TRUE, reason = if (n_nonnull == 0) "all_missing" else "insufficient_support")
    } else {
      lens <- nchar(as.character(x_nn))
      lmean <- round(mean(lens), 3)
      is_date <- dtype == "string" && mean(grepl(DATE_RE, x_nn)) > .8
      struct <- list(n = n_nonnull, length_min = min(lens), length_mean = lmean, length_max = max(lens),
                     pattern_flags = list(email = val_is_email, phone = val_is_phone, date = is_date,
                                          id = name_is_id, free_text = role == "string" || (dtype == "string" && lmean > 40 && !val_is_email && !val_is_phone)))
    }
    col$string_structure <- struct
  }
  columns[[length(columns) + 1]] <- col
}

# --- Relationships ----------------------------------------------------------
relationships <- NULL
if (TIER == 3) {
  relationships <- list(cramers_v = list(), named = list(), crosstabs = list())
  # INTENT: gate each pair on finite COMPLETE pairs, not marginal sample sizes.
  # REASONING: whole-block unavailability avoids invented zero or imputed correlations.
  size <- length(numeric_cols)
  pair_n <- matrix(0, size, size)
  pear <- diag(size)
  spea <- diag(size)
  reason <- if (size < 2) "fewer_than_two_eligible_columns" else NULL
  for (a in seq_len(size)) for (b in a:size) {
    x <- as.numeric(df[[numeric_cols[a]]])
    y <- as.numeric(df[[numeric_cols[b]]])
    ok <- is.finite(x) & is.finite(y)
    n <- sum(ok)
    pair_n[a, b] <- pair_n[b, a] <- n
    if (n < max(SUPPRESSION_THRESHOLD, 2)) {
      if (is.null(reason)) reason <- "insufficient_pair_support"
      next
    }
    if (stats::sd(x[ok]) == 0 || stats::sd(y[ok]) == 0) {
      if (is.null(reason)) reason <- "zero_pair_variance"
      next
    }
    p <- stats::cor(x[ok], y[ok], method = "pearson")
    r <- stats::cor(x[ok], y[ok], method = "spearman")
    if (!all(is.finite(c(p, r)))) {
      if (is.null(reason)) reason <- "nonfinite_correlation"
      next
    }
    pear[a, b] <- pear[b, a] <- round(p, 6)
    spea[a, b] <- spea[b, a] <- round(r, 6)
  }
  for (key in c("pearson", "spearman")) {
    block <- list(available = is.null(reason), columns = numeric_cols, pair_n = pair_n,
                  matrix = if (is.null(reason)) { if (key == "pearson") pear else spea } else matrix(numeric(0), 0, 0))
    if (!is.null(reason)) block$reason <- reason
    relationships[[key]] <- block
  }
  if (length(categ_cols) >= 2) for (a in seq_len(length(categ_cols) - 1)) for (b in (a + 1):length(categ_cols)) {
    pair <- c(categ_cols[a], categ_cols[b])
    ok <- complete.cases(df[, pair, drop = FALSE])
    n <- sum(ok)
    entry <- list(pair = pair, n = n, available = FALSE)
    if (n < SUPPRESSION_THRESHOLD) {
      entry$reason <- "insufficient_support"
    } else {
      tb <- table(df[[pair[1]]][ok], df[[pair[2]]][ok])
      # INTENT: drop factor levels absent from these complete pairs, not real observations.
      # REASONING: zero margins create zero expected counts and an undefined chi-square.
      tb <- tb[rowSums(tb) > 0, colSums(tb) > 0, drop = FALSE]
      stopifnot(sum(tb) == n)
      if (min(dim(tb)) < 2) {
        entry$reason <- "degenerate_table"
      } else {
        # Retain R's existing chisq.test continuity-correction convention (2x2).
        chi <- suppressWarnings(stats::chisq.test(tb)$statistic)
        entry$available <- TRUE
        entry$v <- round(sqrt(as.numeric(chi) / (n * (min(dim(tb)) - 1))), 6)
      }
    }
    relationships$cramers_v[[length(relationships$cramers_v) + 1]] <- entry
  }
  for (pair in RELATIONSHIP_SPEC) {
    both_numeric <- all(col_roles[pair] == "numeric")
    if (both_numeric) {
      y <- as.numeric(df[[pair[1]]])
      x <- as.numeric(df[[pair[2]]])
      ok <- is.finite(x) & is.finite(y)
      n <- sum(ok)
      entry <- list(outcome = pair[1], predictor = pair[2], n = n, available = FALSE)
      if (n < FULL_CUTOFF) {
        entry$reason <- "insufficient_support"
      } else if (!all(pair %in% numeric_cols)) {
        entry$reason <- "ineligible_marginal"
      } else if (stats::sd(x[ok]) == 0 || stats::sd(y[ok]) == 0) {
        entry$reason <- "zero_pair_variance"
      } else {
        fit <- stats::lm(y[ok] ~ x[ok])
        entry$available <- TRUE
        entry$pearson <- round(stats::cor(x[ok], y[ok], method = "pearson"), 6)
        entry$spearman <- round(stats::cor(x[ok], y[ok], method = "spearman"), 6)
        entry$ols <- list(intercept = round(as.numeric(coef(fit)[1]), 6),
                          slope = round(as.numeric(coef(fit)[2]), 6),
                          r_squared = round(suppressWarnings(summary(fit)$r.squared), 6))
      }
      relationships$named[[length(relationships$named) + 1]] <- entry
    } else {
      # INTENT: no categorical fallback for identifiers, strings, or mixed numeric pairs.
      # REASONING: a rejected numeric summary must not escape as exact value cells.
      ok <- complete.cases(df[, pair, drop = FALSE])
      n <- sum(ok)
      entry <- list(pair = pair, n = n, available = FALSE)
      if (!all(col_roles[pair] == "categorical")) {
        entry$reason <- "ineligible_roles"
      } else if (n < SUPPRESSION_THRESHOLD) {
        entry$reason <- "insufficient_support"
      } else {
        tb <- table(df[[pair[1]]][ok], df[[pair[2]]][ok])
        # Drop only zero margins from unused paired factor levels; retain all paired records.
        tb <- tb[rowSums(tb) > 0, colSums(tb) > 0, drop = FALSE]
        stopifnot(sum(tb) == n)
        m <- matrix(as.numeric(tb), nrow(tb), ncol(tb))
        supp <- m > 0 & m < SUPPRESSION_THRESHOLD
        for (iter in seq_len(10)) {
          changed <- FALSE
          for (r in seq_len(nrow(m))) if (sum(supp[r, ]) == 1) {
            vis <- which(!supp[r, ])
            if (length(vis)) {
              supp[r, vis[which.min(m[r, vis])]] <- TRUE
              changed <- TRUE
            }
          }
          for (cc in seq_len(ncol(m))) if (sum(supp[, cc]) == 1) {
            vis <- which(!supp[, cc])
            if (length(vis)) {
              supp[vis[which.min(m[vis, cc])], cc] <- TRUE
              changed <- TRUE
            }
          }
          if (!changed) break
        }
        lone <- any(rowSums(supp) == 1) || any(colSums(supp) == 1)
        if (lone) supp[,] <- TRUE
        cells <- as.list(as.numeric(t(m)))    # JSON row-major, not R's column-major order
        hidden <- as.logical(t(supp))
        for (i in which(hidden)) cells[i] <- list(NULL)  # retain null list elements
        entry <- c(entry, list(rows = nrow(m), cols = ncol(m), cells = cells, cells_suppressed = sum(supp)))
        entry$available <- TRUE
        if (lone) entry$collapsed <- TRUE
      }
      relationships$crosstabs[[length(relationships$crosstabs) + 1]] <- entry
    }
  }
}

# --- Candidate --------------------------------------------------------------
# INTENT: the typed, rounded, suppressed candidate is the ONLY validation/output source.
report <- list(report_version = REPORT_VERSION, dataset_name = DATASET_NAME,
               generated_utc = format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ"),
               generator = list(language = "R", template = TEMPLATE_NAME, template_version = REPORT_VERSION),
               settings = list(tier = TIER, suppression_threshold = SUPPRESSION_THRESHOLD,
                               max_categorical_levels = MAX_CATEGORICAL_LEVELS,
                               relationship_spec = if (length(RELATIONSHIP_SPEC)) RELATIONSHIP_SPEC else NULL,
                               support_unit = "record", full_summary_cutoff = FULL_CUTOFF),
               dataset = list(row_count = n_rows, column_count = n_cols), columns = columns)
if (!is.null(relationships)) report$relationships <- relationships

# --- Validate ---------------------------------------------------------------
# No raw-data recomputation here: malformed/mutated release fields must fail themselves.
required_checks <- c("column_shapes_and_support", "percentiles_monotone", "category_counts_le_rowcount",
                     "missing_rate_in_unit_interval", "no_subthreshold_cells_emitted",
                     "correlation_matrix_symmetric", "relationship_support_and_shape")
checks <- list()
for (check_name in required_checks) {
  applicable <- TRUE
  reason <- "candidate_fields_checked"
  result <- try({
    cols <- report$columns
    rows <- report$dataset$row_count
    tier <- report$settings$tier
    threshold <- report$settings$suppression_threshold
    cutoff <- max(threshold, 10)
    col_names <- character(0)
    for (c in cols) col_names <- c(col_names, c$name)
    rels <- report$relationships
    if (check_name == "column_shapes_and_support") {
      stopifnot(identical(report$report_version, "2.0"), tier %in% c(1, 2, 3),
                length(rows) == 1, is.finite(rows), rows > 0, rows == floor(rows),
                length(cols) == report$dataset$column_count, !anyDuplicated(col_names),
                length(threshold) == 1, is.finite(threshold), threshold >= 1, threshold == floor(threshold),
                report$settings$full_summary_cutoff == cutoff, identical(report$settings$support_unit, "record"),
                !is.null(rels) == (tier == 3))
      stopifnot(setequal(names(report), c("report_version", "dataset_name", "generated_utc", "generator", "settings", "dataset", "columns", if (tier == 3) "relationships")),
                setequal(names(report$dataset), c("row_count", "column_count")),
                setequal(names(report$settings), c("tier", "suppression_threshold", "max_categorical_levels", "relationship_spec", "support_unit", "full_summary_cutoff")))
      for (c in cols) {
        stopifnot(c$dtype %in% c("integer", "double", "string"))
        if (tier == 1) { stopifnot(setequal(names(c), c("name", "dtype"))); next }
        nn <- c$nonmissing_n
        stopifnot(length(nn) == 1, is.numeric(nn), is.finite(nn), nn == floor(nn), nn >= 0, nn <= rows,
                  length(c$n_distinct) == 1, is.finite(c$n_distinct), c$n_distinct == floor(c$n_distinct),
                  c$n_distinct >= 0, c$n_distinct <= nn, length(c$uniqueness_ratio) == 1,
                  is.finite(c$uniqueness_ratio), c$uniqueness_ratio >= 0, c$uniqueness_ratio <= 1)
        key <- switch(c$role, numeric = "numeric", categorical = "categorical", identifier = "string_structure", string = "string_structure")
        stopifnot(length(key) == 1, setequal(names(c), c("name", "dtype", "role", "missing_rate", "nonmissing_n", "n_distinct", "uniqueness_ratio", "is_identifier", key)))
        b <- c[[key]]
        stopifnot(is.list(b), !anyDuplicated(names(b)))
        n <- b$n
        stopifnot(length(n) == 1, is.numeric(n), is.finite(n), n == floor(n), n >= 0, n <= nn)
        if (key != "numeric") stopifnot(n == nn)
        if (key == "numeric") {
          if (isTRUE(b$all_missing)) {
            stopifnot(setequal(names(b), c("n", "all_missing")), n == 0, nn == 0)
          } else if (isTRUE(b$withheld)) {
            stopifnot(setequal(names(b), c("n", "withheld", "reason")), nn > 0, n < threshold,
                      identical(b$reason, if (n == 0) "no_finite_values" else "insufficient_support"))
          } else if (isTRUE(b$constant)) {
            stopifnot(setequal(names(b), c("n", "constant", "value", "mean", "sd")), n >= threshold,
                      typeof(b$value) %in% c("integer", "double"), !is.object(b$value), is.null(dim(b$value)),
                      length(b$value) == 1, is.finite(b$value), identical(b$mean, b$value))
            if (n > 1) stopifnot(is.numeric(b$sd), !is.object(b$sd), is.null(dim(b$sd)), length(b$sd) == 1, b$sd == 0) else stopifnot(is.null(b$sd))
          } else if (isTRUE(b$small_n)) {
            stopifnot(setequal(names(b), c("n", "small_n", "percentiles")), n >= threshold, n < cutoff,
                      setequal(names(b$percentiles), c("p25", "p50", "p75")))
          } else {
            stopifnot(setequal(names(b), c("n", "mean", "sd", "percentiles")), n >= cutoff,
                      is.numeric(b$mean), !is.object(b$mean), is.null(dim(b$mean)),
                      is.numeric(b$sd), !is.object(b$sd), is.null(dim(b$sd)),
                      length(b$mean) == 1, length(b$sd) == 1, is.finite(b$mean), is.finite(b$sd), b$sd >= 0,
                      setequal(names(b$percentiles), PROB_NAMES))
          }
        } else if (key == "string_structure") {
          if (isTRUE(b$withheld)) {
            stopifnot(setequal(names(b), c("n", "withheld", "reason")), nn < threshold,
                      identical(b$reason, if (nn == 0) "all_missing" else "insufficient_support"))
          } else {
            stopifnot(setequal(names(b), c("n", "length_min", "length_mean", "length_max", "pattern_flags")), nn >= threshold)
            for (field in c("length_min", "length_mean", "length_max")) {
              v <- b[[field]]
              stopifnot(typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), length(v) == 1, !is.na(v), is.finite(v))
            }
            lengths <- unlist(b[c("length_min", "length_mean", "length_max")])
            stopifnot(lengths[1] >= 0, all(diff(lengths) >= 0),
                      is.list(b$pattern_flags), !anyDuplicated(names(b$pattern_flags)),
                      setequal(names(b$pattern_flags), c("email", "phone", "date", "id", "free_text")))
            for (v in b$pattern_flags) stopifnot(is.logical(v), length(v) == 1, !is.na(v))
          }
        }
      }
    } else if (check_name == "percentiles_monotone") {
      applicable <- FALSE
      for (c in cols) if (!is.null(c$numeric$percentiles)) {
        applicable <- TRUE
        b <- c$numeric$percentiles
        expected <- if (isTRUE(c$numeric$small_n)) c("p25", "p50", "p75") else PROB_NAMES
        # INTENT: validate EACH outgoing scalar, not a compensating unlist() length.
        # REASONING: NULL plus a two-element neighbor can masquerade as three quantiles.
        stopifnot(is.list(b), !anyDuplicated(names(b)), setequal(names(b), expected))
        for (field in expected) {
          v <- b[[field]]
          stopifnot(typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), length(v) == 1, !is.na(v), is.finite(v))
        }
        values <- unlist(b[expected], use.names = FALSE)
        stopifnot(all(diff(values) >= 0))
      }
    } else if (check_name == "category_counts_le_rowcount") {
      applicable <- FALSE
      for (c in cols) if (!is.null(c$categorical)) {
        applicable <- TRUE
        b <- c$categorical
        stopifnot(setequal(names(b), c("n", "n_levels_binned", "levels")),
                  length(b$n_levels_binned) == 1, is.finite(b$n_levels_binned), b$n_levels_binned >= 0,
                  b$n_levels_binned == floor(b$n_levels_binned))
        counts <- numeric(0)
        labels <- character(0)
        for (l in b$levels) {
          stopifnot(!anyDuplicated(names(l)), setequal(names(l), c("value", "count")),
                    is.character(l$value), length(l$value) == 1, !is.na(l$value),
                    length(l$count) == 1, is.numeric(l$count), is.finite(l$count), l$count == floor(l$count), l$count >= threshold)
          counts <- c(counts, l$count)
          labels <- c(labels, l$value)
        }
        stopifnot(!anyDuplicated(labels), sum(counts) <= b$n, b$n <= rows,
                  sum(counts) == if (b$n >= threshold) b$n else 0)
      }
    } else if (check_name == "missing_rate_in_unit_interval") {
      applicable <- tier >= 2
      if (applicable) for (c in cols) {
        rate <- c$missing_rate
        stopifnot(length(rate) == 1, is.numeric(rate), is.finite(rate), rate >= 0, rate <= 1,
                  abs(rate - (rows - c$nonmissing_n) / rows) <= .00000051)
      }
    } else if (check_name == "no_subthreshold_cells_emitted") {
      counts <- numeric(0)
      for (c in cols) for (l in c$categorical$levels) counts <- c(counts, l$count)
      if (!is.null(rels)) for (b in rels$crosstabs) for (v in b$cells) if (!is.null(v)) counts <- c(counts, v)
      applicable <- length(counts) > 0
      stopifnot(is.numeric(counts), all(is.finite(counts)), all(counts == floor(counts)), all(counts == 0 | counts >= threshold))
    } else if (check_name == "correlation_matrix_symmetric") {
      applicable <- FALSE
      if (!is.null(rels)) for (key in c("pearson", "spearman")) {
        b <- rels[[key]]
        if (isTRUE(b$available)) {
          applicable <- TRUE
          m <- b$matrix
          dim_n <- length(b$columns)
          stopifnot(dim_n >= 2, is.matrix(m), identical(dim(m), c(dim_n, dim_n)), all(is.finite(m)),
                    all(abs(m - t(m)) <= 1e-6), all(abs(diag(m) - 1) <= 1e-6), all(abs(m) <= 1))
        }
      }
    } else {
      applicable <- tier == 3
      if (applicable) {
        stopifnot(setequal(names(rels), c("pearson", "spearman", "named", "cramers_v", "crosstabs")))
        eligible <- character(0)
        for (c in cols) if (setequal(names(c$numeric), c("n", "mean", "sd", "percentiles"))) eligible <- c(eligible, c$name)
        for (key in c("pearson", "spearman")) {
          b <- rels[[key]]
          stopifnot(is.logical(b$available), length(b$available) == 1, !is.na(b$available), identical(b$columns, eligible))
          dim_n <- length(b$columns)
          pn <- b$pair_n
          stopifnot(is.matrix(pn), identical(dim(pn), c(dim_n, dim_n)), all(is.finite(pn)),
                    all(pn == floor(pn)), all(pn >= 0), all(pn == t(pn)))
          for (i in seq_len(dim_n)) {
            c <- cols[[match(b$columns[i], col_names)]]
            stopifnot(pn[i, i] == c$numeric$n, all(pn[i, ] <= pn[i, i]))
          }
          if (b$available) {
            stopifnot(setequal(names(b), c("available", "columns", "pair_n", "matrix")), dim_n >= 2, all(pn >= max(threshold, 2)))
          } else {
            stopifnot(setequal(names(b), c("available", "columns", "pair_n", "matrix", "reason")), length(b$matrix) == 0,
                      b$reason %in% c("fewer_than_two_eligible_columns", "insufficient_pair_support", "zero_pair_variance", "nonfinite_correlation"))
          }
        }
        for (kind in c("named", "cramers_v", "crosstabs")) for (b in rels[[kind]]) {
          stopifnot(is.logical(b$available), length(b$available) == 1, !is.na(b$available),
                    length(b$n) == 1, is.numeric(b$n), is.finite(b$n), b$n == floor(b$n), b$n >= 0, b$n <= rows)
          pair <- if (kind == "named") c(b$outcome, b$predictor) else b$pair
          stopifnot(length(pair) == 2, all(pair %in% col_names))
          for (name in pair) stopifnot(b$n <= cols[[match(name, col_names)]]$nonmissing_n)
          base <- if (kind == "named") c("outcome", "predictor", "n", "available") else c("pair", "n", "available")
          if (!b$available) {
            stopifnot(setequal(names(b), c(base, "reason")), b$reason %in% c("insufficient_support", "ineligible_marginal", "zero_pair_variance", "ineligible_roles", "degenerate_table"))
            next
          }
          stopifnot(b$n >= if (kind == "named") cutoff else threshold)
          if (kind == "named") {
            stopifnot(setequal(names(b), c(base, "pearson", "spearman", "ols")), all(pair %in% eligible),
                      is.list(b$ols), !anyDuplicated(names(b$ols)), setequal(names(b$ols), c("intercept", "slope", "r_squared")))
            for (name in pair) stopifnot(b$n <= cols[[match(name, col_names)]]$numeric$n)
            for (v in b$ols) stopifnot(length(v) == 1, typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), is.finite(v))
            for (k in c("pearson", "spearman")) stopifnot(length(b[[k]]) == 1, is.finite(b[[k]]), abs(b[[k]]) <= 1)
            stopifnot(b$ols$r_squared >= 0, b$ols$r_squared <= 1)
          } else {
            for (name in pair) stopifnot(cols[[match(name, col_names)]]$role == "categorical")
            if (kind == "cramers_v") {
              stopifnot(setequal(names(b), c(base, "v")), length(b$v) == 1, is.finite(b$v), b$v >= 0, b$v <= 1)
            } else {
              stopifnot(setequal(names(b), c(base, "rows", "cols", "cells", "cells_suppressed", if ("collapsed" %in% names(b)) "collapsed")),
                        length(b$rows) == 1, length(b$cols) == 1, b$rows > 0, b$cols > 0,
                        b$rows == floor(b$rows), b$cols == floor(b$cols), length(b$cells) == b$rows * b$cols)
              hidden <- logical(length(b$cells))
              total <- 0
              for (i in seq_along(b$cells)) {
                hidden[i] <- is.null(b$cells[[i]])
                if (!hidden[i]) {
                  v <- b$cells[[i]]
                  stopifnot(length(v) == 1, typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), is.finite(v), v == floor(v))
                  total <- total + v
                }
              }
              mask <- matrix(hidden, b$rows, b$cols, byrow = TRUE)
              stopifnot(sum(hidden) == b$cells_suppressed, total <= b$n, any(hidden) || total == b$n)
              if (isTRUE(b$collapsed)) stopifnot(all(hidden)) else
                stopifnot(!any(rowSums(mask) == 1), !any(colSums(mask) == 1))
            }
          }
        }
      }
    }
    TRUE
  }, silent = TRUE)
  if (inherits(result, "try-error")) {
    status <- "FAIL"
    applicable <- TRUE
    reason <- "candidate_validation_error"
  } else {
    status <- if (applicable) "PASS" else "NOT_APPLICABLE"
    if (!applicable) reason <- "no_released_targets_at_this_tier_or_block_unavailable"
  }
  checks[[length(checks) + 1]] <- list(name = check_name, status = status, applicable = applicable, reason = reason)
}
# INTENT: completeness is required, not vacuous all(logical(0)); exceptions cannot become N/A.
actual_names <- character(0)
all_passed <- TRUE
for (c in checks) {
  actual_names <- c(actual_names, c$name)
  all_passed <- all_passed && nzchar(c$reason) &&
    ((isTRUE(c$applicable) && identical(c$status, "PASS")) || (identical(c$applicable, FALSE) && identical(c$status, "NOT_APPLICABLE")))
}
all_passed <- all_passed && identical(actual_names, required_checks)
report$validation <- list(checks = checks, all_passed = all_passed)
if (!all_passed) {
  cat("VALIDATION FAILED -- no reports written; do not share. Failed checks:\n")
  for (c in checks) if (c$status == "FAIL") cat(c$name, "\n")
  stop("Candidate rejected", call. = FALSE)
}

# --- Summary / Serialize ----------------------------------------------------
# INTENT: encode ONLY validated typed candidate fields, with base R and no helper functions.
# This is schema-specific emission, not a general recursive JSON serializer. The small
# string pool covers report text fields; explicit codepoint escaping handles JSON controls.
text_pool <- c(report$report_version, report$dataset_name, report$generated_utc,
               unlist(report$generator), report$settings$support_unit, unlist(report$settings$relationship_spec))
for (c in report$columns) {
  text_pool <- c(text_pool, c$name, c$dtype, c$role, c$numeric$reason, c$string_structure$reason)
  for (l in c$categorical$levels) text_pool <- c(text_pool, l$value)
}
if (!is.null(report$relationships)) {
  for (key in c("pearson", "spearman")) text_pool <- c(text_pool, report$relationships[[key]]$columns, report$relationships[[key]]$reason)
  for (kind in c("named", "cramers_v", "crosstabs")) for (b in report$relationships[[kind]])
    text_pool <- c(text_pool, b$pair, b$outcome, b$predictor, b$reason)
}
for (c in report$validation$checks) text_pool <- c(text_pool, c$name, c$status, c$reason)
text_pool <- unique(text_pool)
quoted <- character(length(text_pool))
for (i in seq_along(text_pool)) {
  units <- utf8ToInt(enc2utf8(text_pool[i]))
  pieces <- character(length(units))
  for (j in seq_along(units)) {
    code <- units[j]
    pieces[j] <- if (code < 32) sprintf("\\u%04x", code) else if (code == 34) '\\"' else if (code == 92) '\\\\' else intToUtf8(code)
  }
  quoted[i] <- paste0('"', paste(pieces, collapse = ""), '"')
}
col_json <- character(0)
for (c in report$columns) {
  parts <- character(0)
  # Known scalar column metadata. Numeric formatting never rounds again after validation.
  for (key in setdiff(names(c), c("numeric", "categorical", "string_structure"))) {
    v <- c[[key]]
    value_json <- if (is.character(v)) quoted[match(v, text_pool)] else if (is.logical(v)) tolower(as.character(v)) else sprintf("%.17g", v)
    parts <- c(parts, paste0('"', key, '": ', value_json))
  }
  for (block_key in intersect(c("numeric", "categorical", "string_structure"), names(c))) {
    b <- c[[block_key]]
    fields <- character(0)
    for (key in names(b)) {
      v <- b[[key]]
      if (key == "percentiles") {
        items <- character(0)
        for (p in names(v)) items <- c(items, paste0('"', p, '": ', sprintf("%.17g", v[[p]])))
        value_json <- paste0("{", paste(items, collapse = ", "), "}")
      } else if (key == "pattern_flags") {
        items <- character(0)
        for (p in names(v)) items <- c(items, paste0('"', p, '": ', tolower(as.character(v[[p]]))))
        value_json <- paste0("{", paste(items, collapse = ", "), "}")
      } else if (key == "levels") {
        items <- character(0)
        for (l in v) items <- c(items, paste0('{"value": ', quoted[match(l$value, text_pool)], ', "count": ', sprintf("%.17g", l$count), '}'))
        value_json <- paste0("[", paste(items, collapse = ", "), "]")
      } else {
        value_json <- if (is.null(v)) "null" else if (is.character(v)) quoted[match(v, text_pool)] else if (is.logical(v)) tolower(as.character(v)) else sprintf("%.17g", v)
      }
      fields <- c(fields, paste0('"', key, '": ', value_json))
    }
    parts <- c(parts, paste0('"', block_key, '": {', paste(fields, collapse = ", "), '}'))
  }
  col_json <- c(col_json, paste0("    {", paste(parts, collapse = ", "), "}"))
}
rel_json <- character(0)
if (!is.null(report$relationships)) {
  rel_parts <- character(0)
  for (key in c("pearson", "spearman")) {
    b <- report$relationships[[key]]
    matrix_parts <- character(0)
    for (field in c("pair_n", "matrix")) {
      rows_json <- character(0)
      m <- b[[field]]
      for (r in seq_len(nrow(m))) rows_json <- c(rows_json, paste0("[", paste(sprintf("%.17g", m[r, ]), collapse = ", "), "]"))
      matrix_parts <- c(matrix_parts, paste0('"', field, '": [', paste(rows_json, collapse = ", "), ']'))
    }
    rel_parts <- c(rel_parts, paste0('"', key, '": {"available": ', tolower(as.character(b$available)),
      ', "columns": [', paste(quoted[match(b$columns, text_pool)], collapse = ", "), '], ', paste(matrix_parts, collapse = ", "),
      if (!is.null(b$reason)) paste0(', "reason": ', quoted[match(b$reason, text_pool)]) else "", '}'))
  }
  for (kind in c("cramers_v", "named", "crosstabs")) {
    entries <- character(0)
    for (b in report$relationships[[kind]]) {
      fields <- character(0)
      for (key in names(b)) {
        v <- b[[key]]
        if (key == "pair") {
          value_json <- paste0("[", paste(quoted[match(v, text_pool)], collapse = ", "), "]")
        } else if (key == "ols") {
          items <- character(0)
          for (p in names(v)) items <- c(items, paste0('"', p, '": ', sprintf("%.17g", v[[p]])))
          value_json <- paste0("{", paste(items, collapse = ", "), "}")
        } else if (key == "cells") {
          items <- character(0)
          for (cell in v) items <- c(items, if (is.null(cell)) "null" else sprintf("%.17g", cell))
          value_json <- paste0("[", paste(items, collapse = ", "), "]")
        } else {
          value_json <- if (is.character(v)) quoted[match(v, text_pool)] else if (is.logical(v)) tolower(as.character(v)) else sprintf("%.17g", v)
        }
        fields <- c(fields, paste0('"', key, '": ', value_json))
      }
      entries <- c(entries, paste0("{", paste(fields, collapse = ", "), "}"))
    }
    rel_parts <- c(rel_parts, paste0('"', kind, '": [', paste(entries, collapse = ", "), ']'))
  }
  rel_json <- paste0(',\n  "relationships": {', paste(rel_parts, collapse = ",\n    "), '}')
}
check_json <- character(0)
for (c in report$validation$checks) check_json <- c(check_json, paste0(
  '{"name": ', quoted[match(c$name, text_pool)], ', "status": ', quoted[match(c$status, text_pool)],
  ', "applicable": ', tolower(as.character(c$applicable)), ', "reason": ', quoted[match(c$reason, text_pool)], '}'))
spec_json <- "null"
if (length(report$settings$relationship_spec)) {
  items <- character(0)
  for (pair in report$settings$relationship_spec) items <- c(items, paste0("[", paste(quoted[match(pair, text_pool)], collapse = ", "), "]"))
  spec_json <- paste0("[", paste(items, collapse = ", "), "]")
}
json <- paste0('{\n  "report_version": ', quoted[match(report$report_version, text_pool)],
  ',\n  "dataset_name": ', quoted[match(report$dataset_name, text_pool)],
  ',\n  "generated_utc": ', quoted[match(report$generated_utc, text_pool)],
  ',\n  "generator": {"language": ', quoted[match(report$generator$language, text_pool)],
  ', "template": ', quoted[match(report$generator$template, text_pool)],
  ', "template_version": ', quoted[match(report$generator$template_version, text_pool)], '},',
  '\n  "settings": {"tier": ', report$settings$tier, ', "suppression_threshold": ', report$settings$suppression_threshold,
  ', "max_categorical_levels": ', report$settings$max_categorical_levels, ', "relationship_spec": ', spec_json,
  ', "support_unit": ', quoted[match(report$settings$support_unit, text_pool)], ', "full_summary_cutoff": ', report$settings$full_summary_cutoff, '},',
  '\n  "dataset": {"row_count": ', report$dataset$row_count, ', "column_count": ', report$dataset$column_count, '},',
  '\n  "columns": [\n', paste(col_json, collapse = ",\n"), '\n  ]', paste(rel_json, collapse = ""),
  ',\n  "validation": {"checks": [', paste(check_json, collapse = ",\n    "),
  '], "all_passed": ', tolower(as.character(report$validation$all_passed)), '}\n}')
# TXT includes the exact candidate, not an independently maintained raw-data summary.
txt <- c("DISCLOSURE PROFILE REVIEW -- REVIEW BEFORE SHARING",
  "Counts are records, not verified distinct individuals. Confirm the contribution unit locally.",
  "Below-threshold numeric/string summaries are withheld. Eligible constants are shared.",
  "Missingness uses all records; rare numerators do not alone veto supported rates/means.",
  "Rare categories are pooled; visible cross-tab cells are suppression-checked; null means hidden.",
  "Unavailable relationships carry reasons, not invented zero correlations.",
  "These checks do not guarantee protection from reconstruction or auxiliary-information attacks.",
  "Review ALL column names, CATEGORY level VALUES, structure flags and relationships below.",
  "Confirm real identifiers were detected, the tier/threshold are appropriate, and release is authorized.",
  "EXACT RELEASE CANDIDATE (same fields and values as JSON):", json,
  "REVIEW BEFORE SHARING either report. Share no raw rows or fitted models.",
  "Synthetic generation from this report is a code scaffold, never research findings.")
# --- Save -------------------------------------------------------------------
# Exclusive creation refuses a target that appeared after preflight. A partial new pair
# after I/O failure is NOT approved for sharing; prior targets are never overwritten.
json_con <- NULL
txt_con <- NULL
write_result <- try({
  json_con <- file(json_path, open = "wx", encoding = "UTF-8")
  writeLines(json, json_con, useBytes = TRUE)
  close(json_con)
  json_con <- NULL
  txt_con <- file(txt_path, open = "wx", encoding = "UTF-8")
  writeLines(txt, txt_con, useBytes = TRUE)
  close(txt_con)
  txt_con <- NULL
}, silent = TRUE)
if (inherits(write_result, "try-error")) {
  if (!is.null(json_con)) try(close(json_con), silent = TRUE)
  if (!is.null(txt_con)) try(close(txt_con), silent = TRUE)
  stop("OUTPUT FAILED -- do not share any partial report pair; use a fresh folder for retry", call. = FALSE)
}
cat("Wrote BOTH reports:\n  ", json_path, "\n  ", txt_path, "\n", sep = "")
cat("REVIEW THE .txt AND .json BEFORE SHARING EITHER FILE WITH DAAF.\n")
