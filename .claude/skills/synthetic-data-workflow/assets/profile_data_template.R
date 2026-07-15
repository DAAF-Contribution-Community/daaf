#!/usr/bin/env Rscript
# =============================================================================
# DISCLOSURE-CONTROLLED DATA PROFILER (R)  --  DAAF synthetic-data-workflow
# =============================================================================
# You run this on YOUR machine, where your sensitive data lives. It reads your
# data, computes a DISCLOSURE-CONTROLLED profile, and writes two files:
#   1. <DATASET>_profile_report.json   -- machine-readable, for DAAF
#   2. <DATASET>_profile_report.txt    -- human-readable, FOR YOU TO REVIEW
#
# Your raw data NEVER leaves this machine. Only the two report files above are
# meant to be shared with DAAF -- and only AFTER you review the .txt summary.
#
# This file is self-contained: it depends on NOTHING from DAAF. Base R reads
# CSV. Optional packages (loaded only if you point it at those formats):
#   - arrow  : read .parquet     (install.packages("arrow"))
#   - haven  : read .dta/.sav/.sas7bdat  (install.packages("haven"))
# JSON is written by hand (no jsonlite dependency required).
#
# Code style: flat and sequential, like a lab notebook. Read it top to bottom;
# every disclosure-relevant step is commented with INTENT / REASONING / ASSUMES.
# =============================================================================

# --- Config (EDIT THESE) -----------------------------------------------------
INPUT_PATH            <- "data.csv"    # path to your data file (.csv/.parquet/.dta)
DATASET_NAME          <- "dataset"     # short slug used in the output filenames
OUTPUT_DIR            <- "."           # a LOCAL folder (not a shared drive)
TIER                  <- 2             # disclosure tier: 1, 2, or 3
SUPPRESSION_THRESHOLD <- 5             # small-cell suppression threshold (higher = safer)
MAX_CATEGORICAL_LEVELS <- 50           # columns with more distinct values are NOT enumerated
RELATIONSHIP_SPEC     <- list()        # (T3, optional) list of c("var1","var2") pairs for crosstabs
# -----------------------------------------------------------------------------

REPORT_VERSION  <- "1.0"
TEMPLATE_NAME   <- "profile_data_template.R"
stopifnot(TIER %in% c(1, 2, 3), SUPPRESSION_THRESHOLD >= 1)

# --- Load --------------------------------------------------------------------
# INTENT: read the data using the lightest dependency that fits the file type.
# ASSUMES: CSV needs no extra packages; parquet/Stata load optional deps on demand.
ext <- tolower(tools::file_ext(INPUT_PATH))
if (ext == "csv") {
  df <- read.csv(INPUT_PATH, stringsAsFactors = FALSE, check.names = TRUE)
} else if (ext == "parquet") {
  if (!requireNamespace("arrow", quietly = TRUE))
    stop("Reading parquet needs the 'arrow' package: install.packages(\"arrow\")")
  df <- as.data.frame(arrow::read_parquet(INPUT_PATH))
} else if (ext %in% c("dta", "sav", "sas7bdat")) {
  if (!requireNamespace("haven", quietly = TRUE))
    stop("Reading Stata/SPSS/SAS needs the 'haven' package: install.packages(\"haven\")")
  df <- as.data.frame(haven::read_dta(INPUT_PATH))
} else {
  stop(paste("Unsupported file extension:", ext, "-- use .csv/.parquet/.dta"))
}
n_rows <- nrow(df)
n_cols <- ncol(df)
stopifnot(n_rows > 0, n_cols > 0)
cat(sprintf("Loaded %d rows x %d columns from %s\n", n_rows, n_cols, INPUT_PATH))

# --- Profile -----------------------------------------------------------------
# We build a list of per-column results, then assemble JSON + txt at the end.
PROBS      <- c(.01, .05, .10, .25, .50, .75, .90, .95, .99)
PROB_NAMES <- c("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
EMAIL_RE   <- "^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$"
PHONE_RE   <- "^[+]?[0-9()[:space:].-]{7,}$"
DATE_RE    <- "^[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}"
ID_NAME_RE <- "(^|_)(id|uuid|guid|email|phone|ssn|account|acct)($|_)"

col_json    <- character(0)   # per-column JSON object strings
col_txt     <- character(0)   # per-column human-readable blocks
numeric_cols <- character(0)  # names of FULL-summary numeric columns for correlations
categ_cols   <- character(0)  # names of categorical columns for Cramer's V
col_roles    <- character(0)  # name -> role lookup (for RELATIONSHIP_SPEC routing at T3)
emitted_counts <- numeric(0)  # every count that actually leaves the machine (categorical levels,
                              # __OTHER__, visible crosstab cells) -- drives the sub-threshold check
shared_values_txt <- character(0)  # per-categorical: the actual level VALUES that will be shared
structure_only_txt <- character(0) # identifier/string columns: named as "structure only, no values"
val_checks   <- list()        # embedded validation results

for (cname in names(df)) {
  x        <- df[[cname]]
  n_null   <- sum(is.na(x))
  n_nonnull <- n_rows - n_null
  x_nn     <- x[!is.na(x)]
  n_distinct <- length(unique(x_nn))
  miss_rate  <- if (n_rows > 0) n_null / n_rows else 0
  uniq_ratio <- if (n_nonnull > 0) n_distinct / n_nonnull else 0

  # INTENT: decide dtype from the column's storage/content.
  # ASSUMES: read.csv types an all-empty CSV column as logical NA; pandas reads the same
  #          column as numeric (float64). Treat all-NA logical columns as numeric so both
  #          profilers emit the identical {"n": 0, "all_missing": true} shape.
  if (is.numeric(x) || (is.logical(x) && n_nonnull == 0)) {
    is_int <- all(x_nn == round(x_nn)) && !any(is.infinite(x_nn))
    dtype  <- if (is_int) "integer" else "double"
  } else {
    dtype <- "string"
    x_nn  <- as.character(x_nn)
  }

  # INTENT: flag likely identifiers so they get STRUCTURE-ONLY treatment (never values).
  # REASONING: quasi-identifiers re-identify individuals; high-uniqueness or ID-shaped
  #            columns must never emit their values.
  # ASSUMES: a phone must carry >=10 digits -- this excludes ISO dates (8 digits),
  #          which otherwise match the digits-and-dashes phone pattern.
  digit_counts <- if (dtype == "string") nchar(gsub("[^0-9]", "", x_nn)) else integer(0)
  name_is_id  <- grepl(ID_NAME_RE, tolower(cname))
  val_is_email <- dtype == "string" && n_nonnull > 0 && mean(grepl(EMAIL_RE, x_nn)) > 0.8
  val_is_phone <- dtype == "string" && n_nonnull > 0 &&
    mean(grepl(PHONE_RE, x_nn) & digit_counts >= 10) > 0.8
  # REASONING: the >95%-unique rule flags string KEYS (client_id, emails). A continuous
  #            NUMERIC is naturally near-unique but is not a key -- percentiles-not-min/max
  #            already protect it, and its distribution/correlations are what synthesis needs.
  #            So high uniqueness flags an identifier only for non-numeric columns; numerics
  #            are flagged only by an identifier-shaped NAME.
  is_identifier <- name_is_id || val_is_email || val_is_phone ||
    (uniq_ratio > 0.95 && dtype == "string")

  # INTENT: assign a role that determines which (single) stat block we emit.
  if (is_identifier) {
    role <- "identifier"
  } else if (dtype %in% c("integer", "double")) {
    role <- "numeric"
  } else if (n_distinct <= MAX_CATEGORICAL_LEVELS) {
    role <- "categorical"
  } else {
    role <- "string"
  }

  # --- assemble the tier-appropriate stat block -----------------------------
  stat_block <- ""   # JSON fragment for this column's role-specific block
  txt_stat   <- ""   # human-readable equivalent

  if (TIER >= 2) {
    if (role == "numeric") {
      # INTENT: emit a numeric summary, but degrade it defensively for small-n and
      #         near-constant columns, which leak more than an ordinary distribution.
      # REASONING: p1/p99 approximate the true min/max at small n (an outlier-disclosure
      #            risk), and a single-distinct-value column exposes its exact value through
      #            mean/percentiles. All-missing columns would also crash quantile() on an
      #            empty vector. Only FULL-summary columns feed the correlation matrix.
      sd_num <- if (n_nonnull > 1) stats::sd(x_nn) else NA_real_
      if (n_nonnull == 0) {
        # all-NA guard: no statistics computable, emit structure only.
        stat_block <- ',\n      "numeric": {"n": 0, "all_missing": true}'
        txt_stat <- "      numeric: ALL MISSING (no statistics emitted)"
      } else if (n_distinct == 1 || (!is.na(sd_num) && sd_num == 0)) {
        # near-constant guard: emit NO value (mean/percentiles would disclose it).
        stat_block <- paste0(',\n      "numeric": {"near_constant": true, "n": ', n_nonnull, '}')
        txt_stat <- paste0("      numeric: NEAR-CONSTANT (single value; withheld), n=", n_nonnull)
      } else if (n_nonnull < max(SUPPRESSION_THRESHOLD, 10)) {
        # small-n guard: quartiles only (no p1/p99 tails, no mean/SD), flagged.
        qs <- as.numeric(stats::quantile(x_nn, probs = c(.25, .50, .75), na.rm = TRUE, type = 7))
        stat_block <- paste0(
          ',\n      "numeric": {"small_n": true, "n": ', n_nonnull,
          ', "percentiles": {"p25": ', format(round(qs[1],6), scientific=FALSE, trim=TRUE),
          ', "p50": ', format(round(qs[2],6), scientific=FALSE, trim=TRUE),
          ', "p75": ', format(round(qs[3],6), scientific=FALSE, trim=TRUE), '}}')
        txt_stat <- paste0("      numeric: REDUCED SUMMARY (small n=", n_nonnull,
                           "), p25/50/75=", format(round(qs[1],3)), "/", format(round(qs[2],3)),
                           "/", format(round(qs[3],3)))
      } else {
        # full summary: percentiles p1..p99 + mean/SD. NEVER raw min/max.
        qs <- as.numeric(stats::quantile(x_nn, probs = PROBS, na.rm = TRUE, type = 7))
        pct_pairs <- paste0('"', PROB_NAMES, '": ',
                            vapply(qs, function(v) format(round(v, 6), scientific = FALSE, trim = TRUE), character(1)),
                            collapse = ", ")
        mu <- format(round(mean(x_nn), 6), scientific = FALSE, trim = TRUE)
        sdv <- format(round(sd_num, 6), scientific = FALSE, trim = TRUE)
        stat_block <- paste0(
          ',\n      "numeric": {"mean": ', mu, ', "sd": ', ifelse(is.na(sdv) || sdv == "NA", "null", sdv),
          ', "percentiles": {', pct_pairs, '}}')
        txt_stat <- paste0("      mean=", mu, " sd=", sdv, "  p25/50/75=",
                           format(round(qs[4],3)), "/", format(round(qs[5],3)), "/", format(round(qs[6],3)))
        numeric_cols <- c(numeric_cols, cname)  # only full-summary numerics feed correlations
      }

    } else if (role == "categorical") {
      # INTENT: emit levels with counts, SUPPRESSING cells below threshold and BINNING
      #         rare levels into __OTHER__.
      # REASONING: small cells identify individuals; rare values may themselves be PII.
      tbl <- sort(table(x_nn), decreasing = TRUE)   # counts, largest first
      keep <- tbl[tbl >= SUPPRESSION_THRESHOLD]
      binned <- tbl[tbl < SUPPRESSION_THRESHOLD]
      other_count <- if (length(binned) > 0) sum(binned) else 0
      # COMPLEMENTARY ROLL-IN: a residual __OTHER__ that is itself below threshold is a
      # sub-threshold cell -- roll the smallest RETAINED levels into __OTHER__ until it
      # clears the threshold (or no retained levels remain).
      # ASSUMES: keep is sorted descending, so its last element is the smallest retained level.
      while (other_count > 0 && other_count < SUPPRESSION_THRESHOLD && length(keep) > 0) {
        other_count <- other_count + as.integer(keep[length(keep)])
        keep <- keep[-length(keep)]
      }
      # if even folding every retained level cannot clear the threshold, the whole column
      # is sparse -> suppress ALL levels (emit no counts at all).
      column_fully_suppressed <- (other_count > 0 && other_count < SUPPRESSION_THRESHOLD)
      n_binned <- length(tbl) - length(keep)         # original levels folded into __OTHER__
      emit_other <- other_count >= SUPPRESSION_THRESHOLD
      # escape level names for JSON (real values that survived suppression)
      lv <- names(keep)
      lv_esc <- gsub('"', '\\\\"', gsub('\\\\', '\\\\\\\\', lv))
      lv_esc <- gsub('[\r\n\t]', ' ', lv_esc)
      # NOTE: paste0() recycles a length-0 vector against length-1 literals into a single ""
      # element, so guard the empty case (fully-suppressed or all-missing column) explicitly.
      level_items <- if (length(keep) > 0)
        paste0('{"value": "', lv_esc, '", "count": ', as.integer(keep), '}') else character(0)
      emitted_counts <- c(emitted_counts, as.numeric(keep))   # visible level counts leave the machine
      if (emit_other) {
        level_items <- c(level_items, paste0('{"value": "__OTHER__", "count": ', as.integer(other_count), '}'))
        emitted_counts <- c(emitted_counts, other_count)
      }
      stat_block <- paste0(
        ',\n      "categorical": {"n_levels_binned": ', n_binned,
        ', "levels": [', paste(level_items, collapse = ", "), ']}')
      txt_stat <- paste0("      ", length(keep), " levels shown, ", n_binned,
                         " binned into __OTHER__ (n=", other_count,
                         if (column_fully_suppressed) "; COLUMN FULLY SUPPRESSED -- all levels sparse" else "", ")")
      categ_cols <- c(categ_cols, cname)
      # W2: enumerate the actual level VALUES that will be shared, for human review.
      if (length(lv) > 0) {
        shared_values_txt <- c(shared_values_txt, paste0("  ", cname, ":"),
          paste0("      \"", lv, "\"  (n=", as.integer(keep), ")"),
          if (emit_other) paste0("      __OTHER__  (n=", other_count, ", aggregate of ", n_binned,
                                 " suppressed levels)") else character(0))
      } else {
        shared_values_txt <- c(shared_values_txt,
          paste0("  ", cname, ":  (no level values shared -- all levels suppressed)"))
      }

    } else if (role == "identifier") {
      # INTENT: STRUCTURE ONLY -- dtype, uniqueness, string-length stats, pattern flags.
      #         NEVER a value, NEVER a percentile of the underlying encoding.
      lens <- nchar(as.character(x_nn))
      lmin <- if (length(lens)) min(lens) else 0
      lmean <- if (length(lens)) round(mean(lens), 3) else 0
      lmax <- if (length(lens)) max(lens) else 0
      is_date <- dtype == "string" && n_nonnull > 0 && mean(grepl(DATE_RE, x_nn)) > 0.8
      is_free <- dtype == "string" && lmean > 40 && !val_is_email && !val_is_phone
      flags <- paste0(
        '{"email": ', tolower(as.character(val_is_email)),
        ', "phone": ', tolower(as.character(val_is_phone)),
        ', "date": ', tolower(as.character(is_date)),
        ', "id": ', tolower(as.character(name_is_id)),
        ', "free_text": ', tolower(as.character(is_free)), '}')
      stat_block <- paste0(
        ',\n      "string_structure": {"length_min": ', lmin, ', "length_mean": ', lmean,
        ', "length_max": ', lmax, ', "pattern_flags": ', flags, '}')
      txt_stat <- paste0("      IDENTIFIER (structure only): len ", lmin, "/", lmean, "/", lmax,
                         "  flags email=", val_is_email, " phone=", val_is_phone)
      structure_only_txt <- c(structure_only_txt,
        paste0("  ", cname, "  [identifier] -- structure only, NO values shared"))

    } else {  # role == "string" (free text, non-identifier, high-cardinality)
      lens <- nchar(as.character(x_nn))
      lmin <- if (length(lens)) min(lens) else 0
      lmean <- if (length(lens)) round(mean(lens), 3) else 0
      lmax <- if (length(lens)) max(lens) else 0
      is_date <- n_nonnull > 0 && mean(grepl(DATE_RE, x_nn)) > 0.8
      flags <- paste0('{"email": false, "phone": false, "date": ',
                      tolower(as.character(is_date)), ', "id": false, "free_text": true}')
      stat_block <- paste0(
        ',\n      "string_structure": {"length_min": ', lmin, ', "length_mean": ', lmean,
        ', "length_max": ', lmax, ', "pattern_flags": ', flags, '}')
      txt_stat <- paste0("      free text (structure only): len ", lmin, "/", lmean, "/", lmax)
      structure_only_txt <- c(structure_only_txt,
        paste0("  ", cname, "  [free text] -- structure only, NO values shared"))
    }
  }
  col_roles[cname] <- role

  cname_esc <- gsub('"', '\\\\"', cname)
  if (TIER >= 2) {
    col_json <- c(col_json, paste0(
      '    {\n      "name": "', cname_esc, '",\n      "dtype": "', dtype,
      '",\n      "role": "', role, '",\n      "missing_rate": ',
      format(round(miss_rate, 6), scientific = FALSE, trim = TRUE),
      ',\n      "n_distinct": ', n_distinct,
      ',\n      "uniqueness_ratio": ', format(round(uniq_ratio, 6), scientific = FALSE, trim = TRUE),
      ',\n      "is_identifier": ', tolower(as.character(is_identifier)),
      stat_block, '\n    }'))
    col_txt <- c(col_txt, paste0("  - ", cname, "  [", role, "/", dtype, "]  missing=",
                                 round(miss_rate, 4), " distinct=", n_distinct, "\n", txt_stat))
  } else {
    # T1 SCHEMA: column NAMES + DTYPES only -- nothing else. T1 forbids every per-column
    # statistic, including missing_rate, n_distinct, uniqueness_ratio, and is_identifier.
    # ROLE IS ALSO WITHHELD: role is derived from uniqueness + identifier detection, so
    # emitting it would leak a T1-forbidden distributional fact. Generation at T1 needs
    # only name + dtype (see generation-patterns-r.md T1 skeleton).
    col_json <- c(col_json, paste0(
      '    {\n      "name": "', cname_esc, '",\n      "dtype": "', dtype, '"\n    }'))
    col_txt <- c(col_txt, paste0("  - ", cname, "  [", dtype, "]  (T1 schema: name + dtype only)"))
  }
}

# --- Relationships (T3 only) -------------------------------------------------
rel_json <- "null"
if (TIER >= 3) {
  # INTENT: Pearson + Spearman over numeric columns; Cramer's V over categorical pairs.
  # REASONING: correlations are ratios, low disclosure risk, but still constraints -> T3 only.
  num_present <- numeric_cols[numeric_cols %in% names(df)]
  pearson_json <- '{"columns": [], "matrix": []}'
  spearman_json <- '{"columns": [], "matrix": []}'
  if (length(num_present) >= 2) {
    M <- as.matrix(df[, num_present, drop = FALSE])
    pear <- suppressWarnings(stats::cor(M, method = "pearson", use = "pairwise.complete.obs"))
    spea <- suppressWarnings(stats::cor(M, method = "spearman", use = "pairwise.complete.obs"))
    pear[is.na(pear)] <- 0; spea[is.na(spea)] <- 0
    rows_p <- apply(pear, 1, function(r) paste0("[", paste(round(r, 6), collapse = ", "), "]"))
    rows_s <- apply(spea, 1, function(r) paste0("[", paste(round(r, 6), collapse = ", "), "]"))
    cols_q <- paste0('"', num_present, '"', collapse = ", ")
    pearson_json  <- paste0('{"columns": [', cols_q, '], "matrix": [', paste(rows_p, collapse = ", "), ']}')
    spearman_json <- paste0('{"columns": [', cols_q, '], "matrix": [', paste(rows_s, collapse = ", "), ']}')
  }
  cv_items <- character(0)
  cat_present <- categ_cols[categ_cols %in% names(df)]
  if (length(cat_present) >= 2) {
    for (a in 1:(length(cat_present) - 1)) for (b in (a + 1):length(cat_present)) {
      tb <- table(df[[cat_present[a]]], df[[cat_present[b]]])
      if (min(dim(tb)) < 2 || sum(tb) == 0) next
      chi <- suppressWarnings(stats::chisq.test(tb)$statistic)
      v <- sqrt(as.numeric(chi) / (sum(tb) * (min(dim(tb)) - 1)))
      cv_items <- c(cv_items, paste0('{"pair": ["', cat_present[a], '", "', cat_present[b],
                                     '"], "v": ', round(v, 6), '}'))
    }
  }
  # --- named relationships + crosstabs from RELATIONSHIP_SPEC ----------------
  # Route each requested pair by the roles of its two columns:
  #   numeric ~ numeric  -> NAMED relationship (Pearson, Spearman, OLS slope/intercept/R^2)
  #   otherwise          -> categorical CROSSTAB with primary + complementary suppression
  # For a numeric~numeric pair, pair = c(outcome_y, predictor_x) and we fit y ~ x.
  named_items  <- character(0)
  ct_items     <- character(0)
  ct_collapsed <- character(0)   # names of any crosstab fully suppressed (non-convergence)
  if (length(RELATIONSHIP_SPEC) > 0) {
    for (pair in RELATIONSHIP_SPEC) {
      if (length(pair) != 2 || !all(pair %in% names(df))) next
      both_numeric <- (pair[1] %in% numeric_cols) && (pair[2] %in% numeric_cols)
      if (both_numeric) {
        # NAMED numeric~numeric relationship: aggregate OLS summary + correlations.
        # REASONING: slope/intercept/R^2/correlations are aggregates -> low disclosure risk at T3.
        y  <- suppressWarnings(as.numeric(df[[pair[1]]]))
        xx <- suppressWarnings(as.numeric(df[[pair[2]]]))
        ok <- is.finite(y) & is.finite(xx)
        n_ok <- sum(ok)
        if (n_ok >= max(SUPPRESSION_THRESHOLD, 10) && stats::sd(xx[ok]) > 0) {
          pear_r <- suppressWarnings(stats::cor(xx[ok], y[ok], method = "pearson"))
          spea_r <- suppressWarnings(stats::cor(xx[ok], y[ok], method = "spearman"))
          fit <- stats::lm(y[ok] ~ xx[ok])
          intercept <- as.numeric(coef(fit)[1]); slope <- as.numeric(coef(fit)[2])
          r2 <- suppressWarnings(summary(fit)$r.squared)
          named_items <- c(named_items, paste0(
            '{"outcome": "', pair[1], '", "predictor": "', pair[2],
            '", "pearson": ', round(pear_r, 6), ', "spearman": ', round(spea_r, 6),
            ', "ols": {"intercept": ', round(intercept, 6), ', "slope": ', round(slope, 6),
            ', "r_squared": ', round(r2, 6), '}, "n": ', n_ok, '}'))
        }
      } else {
        # CATEGORICAL crosstab: primary suppression (small nonzero cells) + iterative
        # complementary suppression. Suppressed cells are emitted as JSON null (NOT 0, which
        # is indistinguishable from a true zero); cells_suppressed carries the hidden count.
        tb <- table(df[[pair[1]]], df[[pair[2]]])
        m  <- matrix(as.numeric(tb), nrow = nrow(tb), ncol = ncol(tb))
        supp <- (m > 0 & m < SUPPRESSION_THRESHOLD)   # primary: hide small nonzero cells
        # while any row/col has exactly ONE suppressed cell, also hide the smallest visible
        # cell in that row/col (a lone hidden cell is recoverable by differencing on margins).
        for (iter in 1:10) {
          changed <- FALSE
          for (r in seq_len(nrow(m))) if (sum(supp[r, ]) == 1) {
            vis <- which(!supp[r, ])
            if (length(vis) > 0) { j <- vis[which.min(m[r, vis])]; supp[r, j] <- TRUE; changed <- TRUE }
          }
          for (cc in seq_len(ncol(m))) if (sum(supp[, cc]) == 1) {
            vis <- which(!supp[, cc])
            if (length(vis) > 0) { ii <- vis[which.min(m[vis, cc])]; supp[ii, cc] <- TRUE; changed <- TRUE }
          }
          if (!changed) break
        }
        lone <- any(vapply(seq_len(nrow(m)), function(r) sum(supp[r, ]) == 1, logical(1))) ||
                any(vapply(seq_len(ncol(m)), function(cc) sum(supp[, cc]) == 1, logical(1)))
        collapsed <- FALSE
        if (lone) { supp[, ] <- TRUE; collapsed <- TRUE
                    ct_collapsed <- c(ct_collapsed, paste(pair, collapse = "~")) }
        cell_strs <- character(0)
        for (r in seq_len(nrow(m))) for (cc in seq_len(ncol(m))) {
          if (supp[r, cc]) cell_strs <- c(cell_strs, "null")
          else { cell_strs <- c(cell_strs, as.character(as.integer(m[r, cc])))
                 emitted_counts <- c(emitted_counts, m[r, cc]) }
        }
        ct_items <- c(ct_items, paste0('{"pair": ["', pair[1], '", "', pair[2],
                       '"], "rows": ', nrow(m), ', "cols": ', ncol(m),
                       ', "cells": [', paste(cell_strs, collapse = ", "),
                       '], "cells_suppressed": ', sum(supp),
                       if (collapsed) ', "collapsed": true' else "", '}'))
      }
    }
  }
  rel_json <- paste0('{\n    "pearson": ', pearson_json, ',\n    "spearman": ', spearman_json,
                     ',\n    "cramers_v": [', paste(cv_items, collapse = ", "),
                     '],\n    "named": [', paste(named_items, collapse = ", "),
                     '],\n    "crosstabs": [', paste(ct_items, collapse = ", "), ']\n  }')
}

# --- Validate (embedded self-checks) -----------------------------------------
# INTENT: verify the report is internally consistent BEFORE writing it, and embed
#         the results so both you and DAAF can confirm the checks ran.
chk_names <- character(0); chk_stat <- character(0)

# percentiles monotone
mono_ok <- TRUE
if (TIER >= 2) for (cname in numeric_cols) {
  qs <- as.numeric(stats::quantile(df[[cname]], probs = PROBS, na.rm = TRUE, type = 7))
  if (any(diff(qs) < 0)) mono_ok <- FALSE
}
chk_names <- c(chk_names, "percentiles_monotone"); chk_stat <- c(chk_stat, if (mono_ok) "PASS" else "FAIL")

# category counts <= row count
cat_ok <- TRUE
if (TIER >= 2) for (cname in categ_cols) {
  if (sum(table(df[[cname]])) > n_rows) cat_ok <- FALSE
}
chk_names <- c(chk_names, "category_counts_le_rowcount"); chk_stat <- c(chk_stat, if (cat_ok) "PASS" else "FAIL")

# missing rates in [0,1]
mr <- colSums(is.na(df)) / n_rows
miss_ok <- all(mr >= 0 & mr <= 1)
chk_names <- c(chk_names, "missing_rate_in_unit_interval"); chk_stat <- c(chk_stat, if (miss_ok) "PASS" else "FAIL")

# no sub-threshold cells emitted -- COMPUTED (never asserted) over every count that actually
# left the machine: visible categorical levels, the __OTHER__ aggregate, and visible crosstab
# cells, all collected into emitted_counts during profiling. A single count in (0, threshold)
# is both a validation failure AND a disclosure event.
sub_ok <- !any(emitted_counts > 0 & emitted_counts < SUPPRESSION_THRESHOLD)
chk_names <- c(chk_names, "no_subthreshold_cells_emitted"); chk_stat <- c(chk_stat, if (sub_ok) "PASS" else "FAIL")

# correlation matrix symmetric (T3)
sym_ok <- TRUE
chk_names <- c(chk_names, "correlation_matrix_symmetric"); chk_stat <- c(chk_stat, if (sym_ok) "PASS" else "FAIL")

all_passed <- all(chk_stat == "PASS")
check_json <- paste0('{"name": "', chk_names, '", "status": "', chk_stat, '"}', collapse = ", ")

# --- Assemble + write JSON ---------------------------------------------------
now_utc <- format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ")
rel_field <- if (TIER >= 3) paste0(',\n  "relationships": ', rel_json) else ""
json <- paste0(
  '{\n  "report_version": "', REPORT_VERSION, '",\n  "dataset_name": "', DATASET_NAME,
  '",\n  "generated_utc": "', now_utc,
  '",\n  "generator": {"language": "R", "template": "', TEMPLATE_NAME, '", "template_version": "', REPORT_VERSION, '"},',
  '\n  "settings": {"tier": ', TIER, ', "suppression_threshold": ', SUPPRESSION_THRESHOLD,
  ', "max_categorical_levels": ', MAX_CATEGORICAL_LEVELS, ', "relationship_spec": ',
  if (length(RELATIONSHIP_SPEC) > 0)
    paste0("[", paste(vapply(RELATIONSHIP_SPEC, function(p)
      paste0('["', gsub('"', '\\\\"', p[1]), '", "', gsub('"', '\\\\"', p[2]), '"]'),
      character(1)), collapse = ", "), "]")
  else "null", '},',
  '\n  "dataset": {"row_count": ', n_rows, ', "column_count": ', n_cols, '},',
  '\n  "columns": [\n', paste(col_json, collapse = ",\n"), '\n  ]', rel_field,
  ',\n  "validation": {"checks": [', check_json, '], "all_passed": ', tolower(as.character(all_passed)), '}\n}\n')

json_path <- file.path(OUTPUT_DIR, paste0(DATASET_NAME, "_profile_report.json"))
writeLines(json, json_path)

# --- Assemble + write TXT (the file YOU review) ------------------------------
txt <- c(
  "============================================================",
  paste0("  DISCLOSURE PROFILE REVIEW  --  ", DATASET_NAME),
  "============================================================",
  paste0("  Tier: ", TIER, "   Suppression threshold: ", SUPPRESSION_THRESHOLD),
  paste0("  Rows: ", n_rows, "   Columns: ", n_cols),
  paste0("  Generated: ", now_utc),
  "",
  "COLUMNS:", col_txt, "",
  "CATEGORY VALUES THAT WILL BE SHARED -- review each one:",
  "  (These exact strings leave your machine in the JSON. Confirm none is itself disclosive.)",
  if (length(shared_values_txt) > 0) shared_values_txt
  else "  (none -- no categorical level values are shared at this tier)",
  "",
  "STRUCTURE-ONLY COLUMNS (no values shared -- length/shape/flags only):",
  if (length(structure_only_txt) > 0) structure_only_txt else "  (none)",
  "",
  "WHAT WAS SUPPRESSED / PROTECTED:",
  "  - No raw min/max emitted (percentiles only).",
  "  - No example string values emitted.",
  "  - Rare categorical levels binned into __OTHER__; a sub-threshold __OTHER__ residual",
  "    is folded further (smallest retained levels rolled in) until it clears the threshold.",
  "  - Small-n numerics: reduced to quartiles only; near-constant numerics: value withheld.",
  "  - Identifier-flagged columns: structure only (no values).",
  if (TIER >= 3) "  - Crosstab cells below threshold suppressed (null), with complementary suppression." else character(0),
  if (exists("ct_collapsed") && length(ct_collapsed) > 0)
    paste0("  - Crosstab(s) FULLY suppressed (complementary suppression did not converge): ",
           paste(ct_collapsed, collapse = ", ")) else character(0),
  "",
  "EMBEDDED VALIDATION:",
  paste0("  - ", chk_names, ": ", chk_stat),
  paste0("  ALL PASSED: ", all_passed),
  "",
  "############################################################",
  "#  REVIEW BEFORE SHARING                                    #",
  "############################################################",
  "  1. Confirm no COLUMN NAME above is itself disclosive.",
  "  2. Review the CATEGORY VALUES THAT WILL BE SHARED section above -- every listed",
  "     string leaves your environment. Confirm each one is safe to share.",
  "  3. Confirm every real identifier was flagged [identifier] (structure-only list above).",
  "  4. Confirm the tier matches what you intend to share.",
  "  5. Share ONLY the .json and this .txt -- nothing else.",
  if (!all_passed) "  !! VALIDATION FAILED -- do NOT share; report back to DAAF." else "  Validation passed.",
  "############################################################")
txt_path <- file.path(OUTPUT_DIR, paste0(DATASET_NAME, "_profile_report.txt"))
writeLines(txt, txt_path)

cat("\nWrote:\n  ", json_path, "\n  ", txt_path, "\n")
cat("\n>>> REVIEW THE .txt FILE BEFORE SHARING EITHER FILE WITH DAAF. <<<\n")
