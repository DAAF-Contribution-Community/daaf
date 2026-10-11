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
# Nothing to declare: the profiler marks a check not applicable itself, with a fixed reason.
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
# INTENT: refuse a pair that names one column twice, or a pair listed twice, before anything is written.
# REASONING: one pair tabulated twice can be suppressed differently each time, and the two tables
# combined recover cells that each one hides. Messages name pair positions (1-based), never values.
spec_problems <- character(0)
for (j in seq_along(RELATIONSHIP_SPEC)) {
  p <- RELATIONSHIP_SPEC[[j]]
  if (p[1] == p[2]) spec_problems <- c(spec_problems, paste0("pair ", j, " names one column twice"))
  for (i in seq_len(j - 1)) if (all(RELATIONSHIP_SPEC[[i]] == p))
    spec_problems <- c(spec_problems, paste0("pair ", j, " repeats pair ", i))
}
if (length(spec_problems) > 0) stop(paste0("Invalid relationship spec: ", paste(spec_problems, collapse = "; ")), call. = FALSE)
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
    # Order: count descending, ties by code-point label order (radix = C-locale byte order),
    # so the level the roll-in below pools matches Python, not the session's locale collation.
    tbl <- table(x_nn)
    tbl <- tbl[order(-as.numeric(tbl), names(tbl), method = "radix")]
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
# INTENT: refuse a reversed repeat (c(b, a) after c(a, b)) now that roles are known; nothing is written yet.
# REASONING: two numeric columns in both orders are two different regressions (y ~ x and x ~ y)
# and release no cells, so only that case may stay; any other reversed pair repeats one table.
for (j in seq_along(RELATIONSHIP_SPEC)) {
  p <- RELATIONSHIP_SPEC[[j]]
  for (i in seq_len(j - 1)) if (all(RELATIONSHIP_SPEC[[i]] == p[c(2, 1)]) && !all(col_roles[p] == "numeric"))
    spec_problems <- c(spec_problems, paste0("pair ", j, " reverses pair ", i, "; only two numeric columns may be listed in both orders"))
}
if (length(spec_problems) > 0) stop(paste0("Invalid relationship spec: ", paste(spec_problems, collapse = "; ")), call. = FALSE)

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
      # INTENT: release a regression only when each column's complement group -- records with
      # that column finite but the other not -- is empty or holds at least k records.
      # REASONING: the released mean of x describes the numeric block's n_x records; the fitted
      # line pins the mean of x over the n pair-complete records (via the released mean of y,
      # or via the reversed regression), so n_x * mean_x - n * that mean recovers the mean of
      # the n_x - n records lacking y. A group of 1 to k-1 records would leak its mean.
      # ASSUMES: the numeric block's n (finite values) is the population its mean describes.
      # Order: the gates decidable from released counts (insufficient_support,
      # ineligible_marginal, small_complement_group), then value-dependent zero_pair_variance.
      complement <- numeric(0)
      for (name in pair) for (col_entry in columns) if (identical(col_entry$name, name)) complement <- c(complement, col_entry$numeric$n - n)
      if (n < FULL_CUTOFF) {
        entry$reason <- "insufficient_support"
      } else if (!all(pair %in% numeric_cols)) {
        entry$reason <- "ineligible_marginal"
      } else if (any(complement > 0 & complement < SUPPRESSION_THRESHOLD)) {
        entry$reason <- "small_complement_group"
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
        # INTENT: tabulate on each column's RELEASED categories, not its raw source levels.
        # REASONING: if a level pooled into __OTHER__ kept a row of its own, a fully visible
        # row could be subtracted from the released __OTHER__ count and isolate a rare
        # level. So every pooled source level (a literal "__OTHER__" label included) maps to
        # ONE pooled category. Order: kept labels in code-point order (radix), then the pooled
        # category last; the factor levels fix that full set, so a released level with no
        # pair-complete record is a row/column of structural zeros and rows and cols always
        # equal the released level counts. Cramer's V above still uses the full table.
        # ASSUMES: a column with a pooled source level always releases __OTHER__ (pair
        # support >= k implies the pool reached k); the stopifnot below enforces it.
        mapped <- list()
        totals <- list()          # released level count per category, in category order
        nonmissing <- numeric(0)  # each pair column's nonmissing_n (NA excluded)
        for (cname in pair) {
          released <- character(0)
          released_counts <- numeric(0)
          for (c in columns) if (identical(c$name, cname)) {
            for (l in c$categorical$levels) {
              released <- c(released, l$value)
              released_counts <- c(released_counts, l$count)
            }
            nonmissing <- c(nonmissing, c$nonmissing_n)
          }
          kept <- sort(released[released != "__OTHER__"], method = "radix")
          categories <- c(kept, if ("__OTHER__" %in% released) "__OTHER__")
          totals[[length(totals) + 1]] <- released_counts[match(categories, released)]
          values <- as.character(df[[cname]][ok])
          values[!(values %in% kept)] <- "__OTHER__"
          stopifnot(all(values %in% categories))
          mapped[[length(mapped) + 1]] <- factor(values, levels = categories)
        }
        tb <- table(mapped[[1]], mapped[[2]])
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
        # INTENT: no hidden cell may be exactly recoverable from the row/column totals.
        # REASONING: read hidden cells as edges of a graph whose vertices are the table's
        # rows and columns. Differencing the totals pins a hidden cell exactly iff its edge
        # is a BRIDGE (lies on no cycle); a lone hidden cell is only the degree-1 case, so
        # two hidden cycles joined by one cell pass the rule above yet leak that cell.
        # ASSUMES: every row/column total is known (worst case); interval bounds from
        # non-negativity are out of scope. Python and R follow the same rule exactly.
        n_r <- nrow(m)
        n_c <- ncol(m)
        # INTENT: no missing-partner count below k may be pinned by the released totals either.
        # REASONING: a record whose partner column is missing is outside this table but inside
        # the categorical blocks' counts. Extend the table by a "partner missing" column (this
        # row's category, column variable missing) and a "partner missing" row (row variable
        # missing, this column's category). Every total of the extended table is released (level
        # counts, row_count - nonmissing_n), and so is the both-missing corner: corner =
        # row_missing + col_missing - (row_count - n). So the extended table's hidden cells --
        # hidden core cells plus every missing-partner cell -- are edges of the same row/column
        # graph with one extra vertex for the missing row and one for the missing column; the
        # corner is known, not an edge. A missing-partner line whose cells sum to zero is a line
        # of known zeros and adds no edge, so with no missing value in either column nothing
        # below changes. The BASELINE is what the released counts reveal with every core cell
        # hidden: the core is then one connected block, so a missing-partner cell is a bridge
        # only when its line has a single partner (the missing column of a one-row table, the
        # missing row of a one-column table). Released n and missing counts already fix those
        # cells, no cell suppression can reach them, and they are exempt. Every other
        # missing-partner cell with 0 < count < k must not be a bridge.
        # ASSUMES: missing means NA, exactly as nonmissing_n counts it.
        ext_col <- totals[[1]] - rowSums(m)    # row category i, column variable missing
        ext_row <- totals[[2]] - colSums(m)    # row variable missing, column category j
        stopifnot(all(c(ext_col, ext_row) >= 0), sum(ext_col) == nonmissing[1] - n, sum(ext_row) == nonmissing[2] - n)
        miss_row <- n_r + n_c + 1
        miss_col <- n_r + n_c + 2
        # Missing-partner edges (row-side vertex, column-side vertex, count, exempt), extended row-major order.
        ext_u <- numeric(0)
        ext_w <- numeric(0)
        ext_count <- numeric(0)
        ext_exempt <- logical(0)
        if (sum(ext_col) > 0) {
          ext_u <- c(ext_u, seq_len(n_r))
          ext_w <- c(ext_w, rep(miss_col, n_r))
          ext_count <- c(ext_count, ext_col)
          ext_exempt <- c(ext_exempt, rep(n_r == 1, n_r))
        }
        if (sum(ext_row) > 0) {
          ext_u <- c(ext_u, rep(miss_row, n_c))
          ext_w <- c(ext_w, n_r + seq_len(n_c))
          ext_count <- c(ext_count, ext_row)
          ext_exempt <- c(ext_exempt, rep(n_c == 1, n_c))
        }
        # One deterministic loop serves both rules. Each step takes the FIRST violation: a
        # core bridge in row-major order (hidden core cells, core totals treated as known),
        # else the first non-exempt missing-partner cell with 0 < count < k that is a bridge of
        # the extended graph, in extended row-major order (partner-missing column cells for
        # rows 0..rows-1, then partner-missing row cells for columns 0..cols-1). It splits that
        # graph without the bridge into the bridge row's side and the bridge column's side and
        # hides the smallest visible NON-ZERO core cell joining the two sides (ties: first in
        # row-major order), which puts the bridge on a cycle. Zeros are structural and stay
        # visible. Each joining step puts the bridge it targets on a cycle.
        # (A missing-partner cell with no joining cell gets the primary-cell treatment
        # described below.) Every step hides at least one more cell, so rows x cols + rows +
        # cols + 2 iterations always suffice; if a core bridge has no joining cell, a lone
        # hidden cell remains, or the bound is reached, the whole table collapses, which
        # leaves exactly the baseline. With no missing-partner edge the loop is the core
        # rule alone, step for step.
        bridge_free <- FALSE
        for (step in seq_len(n_r * n_c + n_r + n_c + 2)) {
          if (lone) break
          bridge <- NULL
          for (r in seq_len(n_r)) for (cc in seq_len(n_c)) {
            if (!is.null(bridge) || !supp[r, cc]) next
            # Component labels of the hidden-cell graph WITHOUT cell (r, cc); vertex
            # i <= n_r is row i, vertex n_r + j is column j; a label is the smallest
            # vertex of its component, so traversal order is moot.
            label <- rep(0L, n_r + n_c)
            for (start in seq_len(n_r + n_c)) {
              if (label[start] > 0L) next
              label[start] <- start
              stack <- start
              while (length(stack) > 0) {
                vertex <- stack[length(stack)]
                stack <- stack[-length(stack)]
                if (vertex <= n_r) {
                  nbrs <- n_r + which(supp[vertex, ])
                  nbrs <- nbrs[!(vertex == r & nbrs == n_r + cc)]
                } else {
                  nbrs <- which(supp[, vertex - n_r])
                  nbrs <- nbrs[!(nbrs == r & vertex - n_r == cc)]
                }
                for (w in nbrs) if (label[w] == 0L) {
                  label[w] <- start
                  stack <- c(stack, w)
                }
              }
            }
            if (label[r] != label[n_r + cc]) bridge <- list(u = r, w = n_r + cc, label = label, ext = FALSE)
          }
          if (is.null(bridge) && length(ext_u) > 0) {
            # Extended graph: vertices 1..n_r rows, n_r+1..n_r+n_c columns, then the missing
            # row and the missing column; edges are the hidden core cells, then the
            # missing-partner cells. Each candidate is tested by dropping its own edge.
            core_r <- row(supp)[supp]
            core_c <- col(supp)[supp]
            edge_u <- c(core_r, ext_u)
            edge_w <- c(n_r + core_c, ext_w)
            edge_id <- seq_along(edge_u)
            adj_nbr <- split(c(edge_w, edge_u), factor(c(edge_u, edge_w), levels = seq_len(n_r + n_c + 2)))
            adj_id <- split(c(edge_id, edge_id), factor(c(edge_u, edge_w), levels = seq_len(n_r + n_c + 2)))
            for (x in seq_along(ext_u)) {
              if (!is.null(bridge) || ext_exempt[x] || !(ext_count[x] > 0 && ext_count[x] < SUPPRESSION_THRESHOLD)) next
              skip <- length(core_r) + x
              label <- rep(0L, n_r + n_c + 2)
              for (start in seq_len(n_r + n_c + 2)) {
                if (label[start] > 0L) next
                label[start] <- start
                stack <- start
                while (length(stack) > 0) {
                  vertex <- stack[length(stack)]
                  stack <- stack[-length(stack)]
                  nbrs <- adj_nbr[[vertex]][adj_id[[vertex]] != skip]
                  for (w in nbrs) if (label[w] == 0L) {
                    label[w] <- start
                    stack <- c(stack, w)
                  }
                }
              }
              if (label[ext_u[x]] != label[ext_w[x]]) bridge <- list(u = ext_u[x], w = ext_w[x], label = label, ext = TRUE)
            }
          }
          if (is.null(bridge)) {
            bridge_free <- TRUE
            break
          }
          label <- bridge$label
          side_row <- label[bridge$u]
          side_col <- label[bridge$w]
          best <- NULL
          for (i in seq_len(n_r)) for (j in seq_len(n_c)) {
            joins <- (label[i] == side_row && label[n_r + j] == side_col) || (label[i] == side_col && label[n_r + j] == side_row)
            if (joins && !supp[i, j] && m[i, j] > 0 && (is.null(best) || m[i, j] < m[best[1], best[2]])) best <- c(i, j)
          }
          if (is.null(best) && bridge$ext) {
            # INTENT: no joining cell for an exposed missing-partner cell (typically its row
            # or column has no hidden core cell) -- treat it like a primary cell instead of
            # collapsing: hide the smallest visible NON-ZERO core cell on its own row (partner-
            # missing column) or column (partner-missing row), first in order on ties, then
            # re-run complementary suppression on non-zero cells (a hidden cell alone in its
            # row/column gets the smallest visible non-zero partner, first index on ties), up
            # to ten passes. The loop then re-checks both rules. Zeros stay visible.
            line_hidden <- FALSE
            if (bridge$w == miss_col) {
              vis <- which(!supp[bridge$u, ] & m[bridge$u, ] > 0)
              if (length(vis)) {
                supp[bridge$u, vis[which.min(m[bridge$u, vis])]] <- TRUE
                line_hidden <- TRUE
              }
            } else {
              vis <- which(!supp[, bridge$w - n_r] & m[, bridge$w - n_r] > 0)
              if (length(vis)) {
                supp[vis[which.min(m[vis, bridge$w - n_r])], bridge$w - n_r] <- TRUE
                line_hidden <- TRUE
              }
            }
            if (line_hidden) {
              for (rerun in seq_len(10)) {
                changed <- FALSE
                for (r in seq_len(n_r)) {
                  vis <- which(!supp[r, ] & m[r, ] > 0)
                  if (sum(supp[r, ]) == 1 && length(vis)) {
                    supp[r, vis[which.min(m[r, vis])]] <- TRUE
                    changed <- TRUE
                  }
                }
                for (cc in seq_len(n_c)) {
                  vis <- which(!supp[, cc] & m[, cc] > 0)
                  if (sum(supp[, cc]) == 1 && length(vis)) {
                    supp[vis[which.min(m[vis, cc])], cc] <- TRUE
                    changed <- TRUE
                  }
                }
                if (!changed) break
              }
              lone <- any(rowSums(supp) == 1) || any(colSums(supp) == 1)
              next
            }
          }
          if (is.null(best)) break
          supp[best[1], best[2]] <- TRUE
        }
        collapse <- lone || !bridge_free
        if (collapse) supp[,] <- TRUE
        cells <- as.list(as.numeric(t(m)))    # JSON row-major, not R's column-major order
        hidden <- as.logical(t(supp))
        for (i in which(hidden)) cells[i] <- list(NULL)  # retain null list elements
        entry <- c(entry, list(rows = nrow(m), cols = ncol(m), cells = cells, cells_suppressed = sum(supp)))
        entry$available <- TRUE
        if (collapse) entry$collapsed <- TRUE
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
# INTENT: no researcher declarations. A check is NOT_APPLICABLE only where the candidate has
# no target for it, and its reason is one of the fixed forms below -- never free text, which
# would cross the boundary. The disclosure sweep has no such form: it always runs.
# Wire status enum: PASS | FAIL | NOT_APPLICABLE | NOT_VERIFIED. The stdout token for
# NOT_APPLICABLE is [SKIPPED]; a skipped check is never silent.
status_tokens <- list(PASS = "[PASS]", FAIL = "[FAIL]", NOT_APPLICABLE = "[SKIPPED]", NOT_VERIFIED = "[NOT VERIFIED]")
counter_keys <- list(PASS = "passed", FAIL = "failed", NOT_APPLICABLE = "skipped", NOT_VERIFIED = "not_verified")
checks <- list()
check_details <- list()
for (check_name in required_checks) {
  status <- "PASS"
  applicable <- TRUE
  reason <- "candidate_fields_checked"
  detail <- ""
  result <- try({
    cols <- report[["columns"]]
    rows <- report[["dataset"]][["row_count"]]
    tier <- report[["settings"]][["tier"]]
    threshold <- report[["settings"]][["suppression_threshold"]]
    cutoff <- max(threshold, 10)
    col_names <- character(0)
    for (c in cols) col_names <- c(col_names, c[["name"]])
    rels <- report[["relationships"]]
    if (check_name == "column_shapes_and_support") {
      stopifnot(identical(report[["report_version"]], "2.0"), tier %in% c(1, 2, 3),
                length(rows) == 1, is.finite(rows), rows > 0, rows == floor(rows),
                length(cols) == report[["dataset"]][["column_count"]], !anyDuplicated(col_names),
                length(threshold) == 1, is.finite(threshold), threshold >= 1, threshold == floor(threshold),
                report[["settings"]][["full_summary_cutoff"]] == cutoff,
                identical(report[["settings"]][["support_unit"]], "record"),
                !is.null(rels) == (tier == 3))
      stopifnot(setequal(names(report), c("report_version", "dataset_name", "generated_utc", "generator", "settings", "dataset", "columns", if (tier == 3) "relationships")),
                setequal(names(report[["dataset"]]), c("row_count", "column_count")),
                setequal(names(report[["settings"]]), c("tier", "suppression_threshold", "max_categorical_levels", "relationship_spec", "support_unit", "full_summary_cutoff")))
      shape_column <- NA_character_
      shape_result <- try({
        for (c in cols) {
          shape_column <- c[["name"]]
          stopifnot(c[["dtype"]] %in% c("integer", "double", "string"))
          if (tier == 1) { stopifnot(setequal(names(c), c("name", "dtype"))); next }
          nn <- c[["nonmissing_n"]]
          stopifnot(length(nn) == 1, is.numeric(nn), is.finite(nn), nn == floor(nn), nn >= 0, nn <= rows,
                    length(c[["n_distinct"]]) == 1, is.finite(c[["n_distinct"]]), c[["n_distinct"]] == floor(c[["n_distinct"]]),
                    c[["n_distinct"]] >= 0, c[["n_distinct"]] <= nn, length(c[["uniqueness_ratio"]]) == 1,
                    is.finite(c[["uniqueness_ratio"]]), c[["uniqueness_ratio"]] >= 0, c[["uniqueness_ratio"]] <= 1)
          key <- switch(c[["role"]], numeric = "numeric", categorical = "categorical", identifier = "string_structure", string = "string_structure")
          stopifnot(length(key) == 1, setequal(names(c), c("name", "dtype", "role", "missing_rate", "nonmissing_n", "n_distinct", "uniqueness_ratio", "is_identifier", key)))
          b <- c[[key]]
          stopifnot(is.list(b), !anyDuplicated(names(b)))
          n <- b[["n"]]
          stopifnot(length(n) == 1, is.numeric(n), is.finite(n), n == floor(n), n >= 0, n <= nn)
          if (key != "numeric") stopifnot(n == nn)
          if (key == "numeric") {
            if (isTRUE(b[["all_missing"]])) {
              stopifnot(setequal(names(b), c("n", "all_missing")), n == 0, nn == 0)
            } else if (isTRUE(b[["withheld"]])) {
              stopifnot(setequal(names(b), c("n", "withheld", "reason")), nn > 0, n < threshold,
                        identical(b[["reason"]], if (n == 0) "no_finite_values" else "insufficient_support"))
            } else if (isTRUE(b[["constant"]])) {
              stopifnot(setequal(names(b), c("n", "constant", "value", "mean", "sd")), n >= threshold,
                        typeof(b[["value"]]) %in% c("integer", "double"), !is.object(b[["value"]]), is.null(dim(b[["value"]])),
                        length(b[["value"]]) == 1, is.finite(b[["value"]]), identical(b[["mean"]], b[["value"]]))
              if (n > 1) stopifnot(is.numeric(b[["sd"]]), !is.object(b[["sd"]]), is.null(dim(b[["sd"]])), length(b[["sd"]]) == 1, b[["sd"]] == 0) else stopifnot(is.null(b[["sd"]]))
            } else if (isTRUE(b[["small_n"]])) {
              stopifnot(setequal(names(b), c("n", "small_n", "percentiles")), n >= threshold, n < cutoff,
                        setequal(names(b[["percentiles"]]), c("p25", "p50", "p75")))
            } else {
              stopifnot(setequal(names(b), c("n", "mean", "sd", "percentiles")), n >= cutoff,
                        is.numeric(b[["mean"]]), !is.object(b[["mean"]]), is.null(dim(b[["mean"]])),
                        is.numeric(b[["sd"]]), !is.object(b[["sd"]]), is.null(dim(b[["sd"]])),
                        length(b[["mean"]]) == 1, length(b[["sd"]]) == 1, is.finite(b[["mean"]]), is.finite(b[["sd"]]), b[["sd"]] >= 0,
                        setequal(names(b[["percentiles"]]), PROB_NAMES))
            }
          } else if (key == "string_structure") {
            if (isTRUE(b[["withheld"]])) {
              stopifnot(setequal(names(b), c("n", "withheld", "reason")), nn < threshold,
                        identical(b[["reason"]], if (nn == 0) "all_missing" else "insufficient_support"))
            } else {
              stopifnot(setequal(names(b), c("n", "length_min", "length_mean", "length_max", "pattern_flags")), nn >= threshold)
              for (field in c("length_min", "length_mean", "length_max")) {
                v <- b[[field]]
                stopifnot(typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), length(v) == 1, !is.na(v), is.finite(v))
              }
              lengths <- unlist(b[c("length_min", "length_mean", "length_max")])
              stopifnot(lengths[1] >= 0, all(diff(lengths) >= 0),
                        is.list(b[["pattern_flags"]]), !anyDuplicated(names(b[["pattern_flags"]])),
                        setequal(names(b[["pattern_flags"]]), c("email", "phone", "date", "id", "free_text")))
              for (v in b[["pattern_flags"]]) stopifnot(is.logical(v), length(v) == 1, !is.na(v))
            }
          }
        }
      }, silent = TRUE)
      # INTENT: a shape/support failure must name the offending COLUMN, not just a condition class.
      if (inherits(shape_result, "try-error"))
        stop(paste0("column '", shape_column, "': ", conditionMessage(attr(shape_result, "condition"))), call. = FALSE)
      detail <- paste0(length(cols), " columns checked for shape and support at tier ", tier)
    } else if (check_name == "percentiles_monotone") {
      # INTENT: enumerate the DECLARED numeric columns, then the grids they release.
      # REASONING: an absent grid on a column that declares role numeric is missing evidence
      # (NOT VERIFIED); a report releasing no grids at all is a structural fact with its own counts.
      numeric_columns <- list()
      for (c in cols) if (identical(c[["role"]], "numeric")) numeric_columns[[length(numeric_columns) + 1]] <- c
      grids <- list()
      grid_names <- character(0)
      grid_expected <- list()
      for (c in numeric_columns) {
        b <- c[["numeric"]]
        if (is.null(b) || !is.list(b)) {
          status <- "NOT_VERIFIED"
          reason <- paste0("column '", c[["name"]], "' declares role numeric with no numeric block")
          break
        }
        if ("percentiles" %in% names(b)) {
          grids[[length(grids) + 1]] <- b[["percentiles"]]
          grid_names <- c(grid_names, c[["name"]])
          grid_expected[[length(grid_expected) + 1]] <- if (isTRUE(b[["small_n"]])) c("p25", "p50", "p75") else PROB_NAMES
        }
      }
      if (identical(status, "PASS") && length(numeric_columns) == 0) {
        status <- "NOT_APPLICABLE"
        applicable <- FALSE
        reason <- paste0("report declares 0 numeric columns at tier ", tier)
      } else if (identical(status, "PASS") && length(grids) == 0) {
        status <- "NOT_APPLICABLE"
        applicable <- FALSE
        reason <- paste0("0 of ", length(numeric_columns), " numeric columns release a percentile grid")
      } else if (identical(status, "PASS")) {
        n_values <- 0L
        for (i in seq_along(grids)) {
          expected <- grid_expected[[i]]
          grid_result <- try({
            b <- grids[[i]]
            # INTENT: validate EACH outgoing scalar, not a compensating unlist() length.
            # REASONING: NULL plus a two-element neighbor can masquerade as three quantiles.
            stopifnot(is.list(b), !anyDuplicated(names(b)), setequal(names(b), expected))
            for (field in expected) {
              v <- b[[field]]
              stopifnot(typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), length(v) == 1, !is.na(v), is.finite(v))
            }
            values <- unlist(b[expected], use.names = FALSE)
            stopifnot("percentile grid is not non-decreasing" = all(diff(values) >= 0))
          }, silent = TRUE)
          if (inherits(grid_result, "try-error"))
            stop(paste0("column '", grid_names[i], "': ", conditionMessage(attr(grid_result, "condition"))), call. = FALSE)
          n_values <- n_values + length(expected)
        }
        detail <- paste0(length(grids), " columns x ", n_values, " percentiles checked, all finite and non-decreasing")
      }
    } else if (check_name == "category_counts_le_rowcount") {
      categorical_columns <- list()
      for (c in cols) if (identical(c[["role"]], "categorical")) categorical_columns[[length(categorical_columns) + 1]] <- c
      blocks <- list()
      block_names <- character(0)
      for (c in categorical_columns) {
        b <- c[["categorical"]]
        if (is.null(b) || !is.list(b)) {
          status <- "NOT_VERIFIED"
          reason <- paste0("column '", c[["name"]], "' declares role categorical with no categorical block")
          break
        }
        blocks[[length(blocks) + 1]] <- b
        block_names <- c(block_names, c[["name"]])
      }
      if (identical(status, "PASS") && length(blocks) == 0) {
        status <- "NOT_APPLICABLE"
        applicable <- FALSE
        reason <- paste0("report declares 0 categorical columns at tier ", tier)
      } else if (identical(status, "PASS")) {
        n_levels <- 0L
        for (i in seq_along(blocks)) {
          block_result <- try({
            b <- blocks[[i]]
            stopifnot(setequal(names(b), c("n", "n_levels_binned", "levels")),
                      length(b[["n_levels_binned"]]) == 1, is.finite(b[["n_levels_binned"]]), b[["n_levels_binned"]] >= 0,
                      b[["n_levels_binned"]] == floor(b[["n_levels_binned"]]))
            counts <- numeric(0)
            labels <- character(0)
            for (l in b[["levels"]]) {
              stopifnot(!anyDuplicated(names(l)), setequal(names(l), c("value", "count")),
                        is.character(l[["value"]]), length(l[["value"]]) == 1, !is.na(l[["value"]]),
                        length(l[["count"]]) == 1, is.numeric(l[["count"]]), is.finite(l[["count"]]),
                        l[["count"]] == floor(l[["count"]]), l[["count"]] >= threshold)
              counts <- c(counts, l[["count"]])
              labels <- c(labels, l[["value"]])
            }
            stopifnot(!anyDuplicated(labels), sum(counts) <= b[["n"]], b[["n"]] <= rows,
                      sum(counts) == if (b[["n"]] >= threshold) b[["n"]] else 0)
            n_levels <- n_levels + length(labels)
          }, silent = TRUE)
          if (inherits(block_result, "try-error"))
            stop(paste0("column '", block_names[i], "': ", conditionMessage(attr(block_result, "condition"))), call. = FALSE)
        }
        detail <- paste0(length(blocks), " columns x ", n_levels, " released levels checked against row count ", rows)
      }
    } else if (check_name == "missing_rate_in_unit_interval") {
      if (tier < 2) {
        status <- "NOT_APPLICABLE"
        applicable <- FALSE
        reason <- "tier 1 releases name and dtype only"
      } else {
        for (c in cols) {
          rate <- c[["missing_rate"]]
          rate_ok <- length(rate) == 1 && is.numeric(rate) && !is.na(rate) && is.finite(rate) &&
            rate >= 0 && rate <= 1 && abs(rate - (rows - c[["nonmissing_n"]]) / rows) <= .00000051
          if (!isTRUE(rate_ok))
            stop(paste0("column '", c[["name"]], "': missing_rate is absent, non-numeric, NA, outside [0,1], or disagrees with nonmissing_n"), call. = FALSE)
        }
        detail <- paste0(length(cols), " columns checked, every rate in [0, 1] and consistent with nonmissing_n")
      }
    } else if (check_name == "no_subthreshold_cells_emitted") {
      # INTENT: scan COMPLETENESS is itself the check -- a block we failed to reach is a FAIL.
      # REASONING: an empty sweep list is indistinguishable from a clean sweep, so the blocks
      # scanned are counted and reconciled against the blocks the report declares.
      # ASSUMES: evidence stays aggregate; no cell value, minimum, or per-level count is printed.
      declared_blocks <- 0L
      scanned_blocks <- 0L
      visible_cells <- 0L
      hidden_checked <- 0L
      ext_checked <- 0L
      unreachable <- character(0)
      for (c in cols) {
        if (!identical(c[["role"]], "categorical")) next
        declared_blocks <- declared_blocks + 1L
        b <- c[["categorical"]]
        if (is.null(b) || !is.list(b) || !("levels" %in% names(b))) {
          unreachable <- c(unreachable, paste0("column:", c[["name"]]))
          next
        }
        scanned_blocks <- scanned_blocks + 1L
        for (l in b[["levels"]]) {
          v <- l[["count"]]
          cell_ok <- length(v) == 1 && is.numeric(v) && !is.na(v) && is.finite(v) &&
            v == floor(v) && (v == 0 || v >= threshold)
          if (!isTRUE(cell_ok))
            stop(paste0("column '", c[["name"]], "': released level below threshold"), call. = FALSE)
          visible_cells <- visible_cells + 1L
        }
      }
      if (tier == 3 && (is.null(rels) || !("crosstabs" %in% names(rels)))) {
        status <- "NOT_VERIFIED"
        reason <- "crosstab collection absent at tier 3; the sweep could not be completed"
      } else if (!is.null(rels) && "crosstabs" %in% names(rels)) {
        for (b in rels[["crosstabs"]]) {
          declared_blocks <- declared_blocks + 1L
          pair_label <- paste(b[["pair"]], collapse = " x ")
          if (!isTRUE(b[["available"]])) {
            # An unavailable block must carry no cells at all; cells here would be a release.
            if ("cells" %in% names(b))
              stop(paste0("crosstab ", pair_label, ": unavailable block carries cells"), call. = FALSE)
            scanned_blocks <- scanned_blocks + 1L
            next
          }
          if (!("cells" %in% names(b))) {
            unreachable <- c(unreachable, paste0("crosstab:", pair_label))
            next
          }
          scanned_blocks <- scanned_blocks + 1L
          hidden_positions <- integer(0)
          for (position in seq_along(b[["cells"]])) {
            v <- b[["cells"]][[position]]
            if (is.null(v)) {
              hidden_positions <- c(hidden_positions, position)
              next
            }
            cell_ok <- length(v) == 1 && is.numeric(v) && !is.na(v) && is.finite(v) &&
              v == floor(v) && (v == 0 || v >= threshold)
            if (!isTRUE(cell_ok))
              stop(paste0("crosstab ", pair_label, " cell position ", position, ": below threshold"), call. = FALSE)
            visible_cells <- visible_cells + 1L
          }
          # INTENT: a hidden cell the released totals pin exactly is an emitted cell.
          # REASONING: with hidden cells as edges of the row/column graph, differencing
          # the totals recovers exactly the bridge edges (cells on no cycle). Each hidden
          # cell is tested by removing it and asking whether its row still reaches its
          # column through other hidden cells.
          # ASSUMES: every margin is known (worst case); a collapsed entry whose cells are
          # all null releases no visible cell and is exempt. A FAIL names positions only
          # (0-based row/column indices, as in the JSON).
          n_r <- b[["rows"]]
          n_c <- b[["cols"]]
          shape_ok <- length(n_r) == 1 && length(n_c) == 1 && is.numeric(n_r) && is.numeric(n_c) &&
            is.finite(n_r) && is.finite(n_c) && n_r == floor(n_r) && n_c == floor(n_c) &&
            n_r > 0 && n_c > 0 && n_r * n_c == length(b[["cells"]])
          if (!isTRUE(shape_ok))
            stop(paste0("crosstab ", pair_label, ": rows x cols does not match the released cells"), call. = FALSE)
          if (length(hidden_positions) > 0 && !(isTRUE(b[["collapsed"]]) && length(hidden_positions) == n_r * n_c)) {
            hidden_grid <- matrix(FALSE, n_r, n_c)
            for (position in hidden_positions) hidden_grid[(position - 1) %/% n_c + 1, (position - 1) %% n_c + 1] <- TRUE
            for (position in hidden_positions) {
              hr <- (position - 1) %/% n_c + 1
              hc <- (position - 1) %% n_c + 1
              label <- rep(0L, n_r + n_c)
              for (start in seq_len(n_r + n_c)) {
                if (label[start] > 0L) next
                label[start] <- start
                stack <- start
                while (length(stack) > 0) {
                  vertex <- stack[length(stack)]
                  stack <- stack[-length(stack)]
                  if (vertex <= n_r) {
                    nbrs <- n_r + which(hidden_grid[vertex, ])
                    nbrs <- nbrs[!(vertex == hr & nbrs == n_r + hc)]
                  } else {
                    nbrs <- which(hidden_grid[, vertex - n_r])
                    nbrs <- nbrs[!(nbrs == hr & vertex - n_r == hc)]
                  }
                  for (w in nbrs) if (label[w] == 0L) {
                    label[w] <- start
                    stack <- c(stack, w)
                  }
                }
              }
              if (label[hr] != label[n_r + hc])
                stop(paste0("crosstab ", pair_label, ": hidden cell at row index ", hr - 1, ", column index ", hc - 1,
                            " is recoverable from the released totals"), call. = FALSE)
              hidden_checked <- hidden_checked + 1L
            }
          }
          # INTENT: no missing-partner count below threshold is pinned by the released totals,
          # beyond the baseline the released counts fix on their own.
          # REASONING: rebuilt from released facts only -- level counts, nonmissing_n,
          # row_count, entry n and visible cells -- as an analyst would. The extended table adds
          # a partner-missing column and row; the both-missing corner is known from released
          # counts. A missing-partner cell that is a bridge of the extended graph is the only
          # hidden cell crossing the cut around its side, so its count is the totals of the rows
          # on that side, minus the totals of the columns on that side, minus the known cells
          # leaving the side, plus the known cells entering it. Exempt (baseline): the missing
          # column of a one-row table and the missing row of a one-column table.
          # ASSUMES: a FAIL names the row or column index only (0-based, as in the JSON), never a
          # count. Without the pair columns' released categories the sweep cannot run: a FAIL.
          pair_cols <- list()
          for (name in b[["pair"]]) pair_cols[[length(pair_cols) + 1]] <- cols[[match(name, col_names)]]
          nonmissing <- c(pair_cols[[1]][["nonmissing_n"]], pair_cols[[2]][["nonmissing_n"]])
          residual <- nonmissing - b[["n"]]
          if (!isTRUE(all(residual >= 0)))
            stop(paste0("crosstab ", pair_label, ": entry n exceeds a pair column's nonmissing_n"), call. = FALSE)
          if (any(residual > 0)) {
            totals <- list()
            for (pc in pair_cols) {
              level_values <- character(0)
              level_counts <- numeric(0)
              for (l in pc[["categorical"]][["levels"]]) {
                level_values <- c(level_values, l[["value"]])
                level_counts <- c(level_counts, l[["count"]])
              }
              kept <- sort(level_values[level_values != "__OTHER__"], method = "radix")
              totals[[length(totals) + 1]] <- level_counts[match(c(kept, if ("__OTHER__" %in% level_values) "__OTHER__"), level_values)]
            }
            if (!isTRUE(length(totals[[1]]) == n_r && length(totals[[2]]) == n_c))
              stop(paste0("crosstab ", pair_label, ": rows x cols differ from the released categories; the missing-partner sweep could not run"), call. = FALSE)
            miss_row <- n_r + n_c + 1
            miss_col <- n_r + n_c + 2
            row_vertices <- c(seq_len(n_r), miss_row)
            col_vertices <- c(n_r + seq_len(n_c), miss_col)
            row_total <- c(totals[[1]], rows - nonmissing[1])
            col_total <- c(totals[[2]], rows - nonmissing[2])
            corner <- (rows - nonmissing[1]) + (rows - nonmissing[2]) - (rows - b[["n"]])
            visible <- setdiff(seq_along(b[["cells"]]), hidden_positions)
            known_r <- c((visible - 1) %/% n_c + 1, miss_row)
            known_c <- c(n_r + (visible - 1) %% n_c + 1, miss_col)
            known_v <- corner
            if (length(visible) > 0) known_v <- c(unlist(b[["cells"]][visible]), corner)
            ext_u <- numeric(0)
            ext_w <- numeric(0)
            ext_exempt <- logical(0)
            if (residual[1] > 0) {
              ext_u <- c(ext_u, seq_len(n_r))
              ext_w <- c(ext_w, rep(miss_col, n_r))
              ext_exempt <- c(ext_exempt, rep(n_r == 1, n_r))
            }
            if (residual[2] > 0) {
              ext_u <- c(ext_u, rep(miss_row, n_c))
              ext_w <- c(ext_w, n_r + seq_len(n_c))
              ext_exempt <- c(ext_exempt, rep(n_c == 1, n_c))
            }
            edge_u <- c((hidden_positions - 1) %/% n_c + 1, ext_u)
            edge_w <- c(n_r + (hidden_positions - 1) %% n_c + 1, ext_w)
            edge_id <- seq_along(edge_u)
            adj_nbr <- split(c(edge_w, edge_u), factor(c(edge_u, edge_w), levels = seq_len(n_r + n_c + 2)))
            adj_id <- split(c(edge_id, edge_id), factor(c(edge_u, edge_w), levels = seq_len(n_r + n_c + 2)))
            for (x in seq_along(ext_u)) {
              if (ext_exempt[x]) next
              skip <- length(hidden_positions) + x
              label <- rep(0L, n_r + n_c + 2)
              for (start in seq_len(n_r + n_c + 2)) {
                if (label[start] > 0L) next
                label[start] <- start
                stack <- start
                while (length(stack) > 0) {
                  vertex <- stack[length(stack)]
                  stack <- stack[-length(stack)]
                  nbrs <- adj_nbr[[vertex]][adj_id[[vertex]] != skip]
                  for (w in nbrs) if (label[w] == 0L) {
                    label[w] <- start
                    stack <- c(stack, w)
                  }
                }
              }
              ext_checked <- ext_checked + 1L
              if (label[ext_u[x]] == label[ext_w[x]]) next
              in_side <- label == label[ext_u[x]]
              value <- sum(row_total[in_side[row_vertices]]) - sum(col_total[in_side[col_vertices]]) -
                sum(known_v[in_side[known_r] & !in_side[known_c]]) + sum(known_v[in_side[known_c] & !in_side[known_r]])
              if (value > 0 && value < threshold)
                stop(paste0("crosstab ", pair_label, ": missing-partner cell at ",
                            if (ext_w[x] == miss_col) paste0("row index ", ext_u[x] - 1) else paste0("column index ", ext_w[x] - n_r - 1),
                            " is recoverable from the released totals"), call. = FALSE)
            }
          }
        }
      }
      if (identical(status, "PASS") && length(unreachable) > 0) {
        status <- "FAIL"
        reason <- paste0("scanned ", scanned_blocks, " of ", declared_blocks,
                         " declared blocks; unreachable: ", paste(unreachable, collapse = ", "))
      } else if (identical(status, "PASS")) {
        detail <- paste0(scanned_blocks, " of ", declared_blocks, " declared blocks scanned, ",
                         visible_cells, " visible cells, all >= threshold ", threshold, "; ",
                         hidden_checked, " hidden cross-tab cells checked, none recoverable from the row and column totals; ",
                         ext_checked, " missing-partner cells checked, none below threshold recoverable from the released totals")
      }
    } else if (check_name == "correlation_matrix_symmetric") {
      if (tier != 3) {
        status <- "NOT_APPLICABLE"
        applicable <- FALSE
        reason <- paste0("tier ", tier, " releases no correlations")
      } else if (is.null(rels) || !all(c("pearson", "spearman") %in% names(rels))) {
        status <- "NOT_VERIFIED"
        reason <- "pearson/spearman block absent at tier 3"
      } else {
        released <- character(0)
        for (key in c("pearson", "spearman")) if (isTRUE(rels[[key]][["available"]])) released <- c(released, key)
        if (length(released) == 0) {
          declared_reason <- rels[["pearson"]][["reason"]]
          if (!(is.character(declared_reason) && length(declared_reason) == 1 && nzchar(declared_reason)))
            declared_reason <- "no reason stated"
          status <- "NOT_APPLICABLE"
          applicable <- FALSE
          reason <- paste0("0 of 2 correlation blocks released (", declared_reason, ")")
        } else {
          max_asymmetry <- 0
          shapes <- character(0)
          for (key in released) {
            b <- rels[[key]]
            m <- b[["matrix"]]
            dim_n <- length(b[["columns"]])
            stopifnot(dim_n >= 2, is.matrix(m), identical(dim(m), c(dim_n, dim_n)), all(is.finite(m)),
                      all(abs(m - t(m)) <= 1e-6), all(abs(diag(m) - 1) <= 1e-6), all(abs(m) <= 1))
            max_asymmetry <- max(max_asymmetry, max(abs(m - t(m))))
            shapes <- c(shapes, paste0(key, " ", dim_n, "x", dim_n))
          }
          detail <- paste0(paste(shapes, collapse = ", "), "; max asymmetry ",
                           format(max_asymmetry, scientific = TRUE, digits = 3), " <= 1e-06 tolerance")
        }
      }
    } else {
      if (tier != 3) {
        status <- "NOT_APPLICABLE"
        applicable <- FALSE
        reason <- paste0("tier ", tier, " releases no relationships")
      } else if (is.null(rels)) {
        status <- "NOT_VERIFIED"
        reason <- "relationships block absent at tier 3"
      } else {
        stopifnot(setequal(names(rels), c("pearson", "spearman", "named", "cramers_v", "crosstabs")))
        eligible <- character(0)
        for (c in cols) if (setequal(names(c[["numeric"]]), c("n", "mean", "sd", "percentiles"))) eligible <- c(eligible, c[["name"]])
        for (key in c("pearson", "spearman")) {
          b <- rels[[key]]
          stopifnot(is.logical(b[["available"]]), length(b[["available"]]) == 1, !is.na(b[["available"]]), identical(b[["columns"]], eligible))
          dim_n <- length(b[["columns"]])
          pn <- b[["pair_n"]]
          stopifnot(is.matrix(pn), identical(dim(pn), c(dim_n, dim_n)), all(is.finite(pn)),
                    all(pn == floor(pn)), all(pn >= 0), all(pn == t(pn)))
          for (i in seq_len(dim_n)) {
            c <- cols[[match(b[["columns"]][i], col_names)]]
            stopifnot(pn[i, i] == c[["numeric"]][["n"]], all(pn[i, ] <= pn[i, i]))
          }
          if (isTRUE(b[["available"]])) {
            stopifnot(setequal(names(b), c("available", "columns", "pair_n", "matrix")), dim_n >= 2, all(pn >= max(threshold, 2)))
          } else {
            stopifnot(setequal(names(b), c("available", "columns", "pair_n", "matrix", "reason")), length(b[["matrix"]]) == 0,
                      b[["reason"]] %in% c("fewer_than_two_eligible_columns", "insufficient_pair_support", "zero_pair_variance", "nonfinite_correlation"))
          }
        }
        for (kind in c("named", "cramers_v", "crosstabs")) for (b in rels[[kind]]) {
          stopifnot(is.logical(b[["available"]]), length(b[["available"]]) == 1, !is.na(b[["available"]]),
                    length(b[["n"]]) == 1, is.numeric(b[["n"]]), is.finite(b[["n"]]), b[["n"]] == floor(b[["n"]]), b[["n"]] >= 0, b[["n"]] <= rows)
          pair <- if (kind == "named") c(b[["outcome"]], b[["predictor"]]) else b[["pair"]]
          stopifnot(length(pair) == 2, all(pair %in% col_names))
          for (name in pair) stopifnot(b[["n"]] <= cols[[match(name, col_names)]][["nonmissing_n"]])
          base <- if (kind == "named") c("outcome", "predictor", "n", "available") else c("pair", "n", "available")
          if (!isTRUE(b[["available"]])) {
            stopifnot(setequal(names(b), c(base, "reason")), b[["reason"]] %in% c("insufficient_support", "ineligible_marginal", "small_complement_group", "zero_pair_variance", "ineligible_roles", "degenerate_table"))
            next
          }
          stopifnot(b[["n"]] >= if (kind == "named") cutoff else threshold)
          if (kind == "named") {
            stopifnot(setequal(names(b), c(base, "pearson", "spearman", "ols")), all(pair %in% eligible),
                      is.list(b[["ols"]]), !anyDuplicated(names(b[["ols"]])), setequal(names(b[["ols"]]), c("intercept", "slope", "r_squared")))
            for (name in pair) stopifnot(b[["n"]] <= cols[[match(name, col_names)]][["numeric"]][["n"]])
            # Complement groups (finite in one column, not the other) are 0 or >= threshold.
            for (name in pair) {
              group <- cols[[match(name, col_names)]][["numeric"]][["n"]] - b[["n"]]
              if (!isTRUE(group == 0 || group >= threshold))
                stop(paste0("named entry (", pair[1], " ~ ", pair[2], "): a complement group is below threshold"), call. = FALSE)
            }
            for (v in b[["ols"]]) stopifnot(length(v) == 1, typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), is.finite(v))
            for (k in c("pearson", "spearman")) stopifnot(length(b[[k]]) == 1, is.finite(b[[k]]), abs(b[[k]]) <= 1)
            stopifnot(b[["ols"]][["r_squared"]] >= 0, b[["ols"]][["r_squared"]] <= 1)
          } else {
            for (name in pair) stopifnot(cols[[match(name, col_names)]][["role"]] == "categorical")
            if (kind == "cramers_v") {
              stopifnot(setequal(names(b), c(base, "v")), length(b[["v"]]) == 1, is.finite(b[["v"]]), b[["v"]] >= 0, b[["v"]] <= 1)
            } else {
              stopifnot(setequal(names(b), c(base, "rows", "cols", "cells", "cells_suppressed", if ("collapsed" %in% names(b)) "collapsed")),
                        length(b[["rows"]]) == 1, length(b[["cols"]]) == 1, b[["rows"]] > 0, b[["cols"]] > 0,
                        b[["rows"]] == floor(b[["rows"]]), b[["cols"]] == floor(b[["cols"]]), length(b[["cells"]]) == b[["rows"]] * b[["cols"]])
              hidden <- logical(length(b[["cells"]]))
              total <- 0
              for (i in seq_along(b[["cells"]])) {
                hidden[i] <- is.null(b[["cells"]][[i]])
                if (!hidden[i]) {
                  v <- b[["cells"]][[i]]
                  stopifnot(length(v) == 1, typeof(v) %in% c("integer", "double"), !is.object(v), is.null(dim(v)), is.finite(v), v == floor(v))
                  total <- total + v
                }
              }
              mask <- matrix(hidden, b[["rows"]], b[["cols"]], byrow = TRUE)
              stopifnot(sum(hidden) == b[["cells_suppressed"]], total <= b[["n"]], any(hidden) || total == b[["n"]])
              if (isTRUE(b[["collapsed"]])) stopifnot(all(hidden)) else
                stopifnot(!any(rowSums(mask) == 1), !any(colSums(mask) == 1))
            }
          }
        }
        # INTENT: each cross-tab sits on its own pair and on the released categories.
        # REASONING: a second table of one pair can be suppressed differently and combined
        # with the first; a row or column for a pooled source level can be subtracted from
        # __OTHER__. Rows/cols equal to the released level counts rule the latter out.
        # Messages name the entry index (0-based, as in the JSON) and column names only.
        for (i in seq_along(rels[["crosstabs"]])) {
          b <- rels[["crosstabs"]][[i]]
          pair <- b[["pair"]]
          if (pair[1] == pair[2]) stop(paste0("crosstab entry ", i - 1, ": pair names one column twice"), call. = FALSE)
          for (j in seq_len(i - 1)) if (setequal(rels[["crosstabs"]][[j]][["pair"]], pair))
            stop(paste0("crosstab entry ", i - 1, ": repeats the pair of an earlier entry"), call. = FALSE)
          if (isTRUE(b[["available"]])) {
            level_counts <- c(length(cols[[match(pair[1], col_names)]][["categorical"]][["levels"]]),
                              length(cols[[match(pair[2], col_names)]][["categorical"]][["levels"]]))
            if (!isTRUE(b[["rows"]] == level_counts[1] && b[["cols"]] == level_counts[2]))
              stop(paste0("crosstab entry ", i - 1, " (", pair[1], " x ", pair[2],
                          "): rows x cols differ from the released level counts of its pair columns"), call. = FALSE)
          }
        }
        entries <- length(rels[["named"]]) + length(rels[["cramers_v"]]) + length(rels[["crosstabs"]])
        detail <- paste0("2 correlation blocks + ", entries, " relationship entries checked for support and shape")
      }
    }
    TRUE
  }, silent = TRUE)
  if (inherits(result, "try-error")) {
    # INTENT: a FAIL names the failing field/column and what was observed, not just a class.
    status <- "FAIL"
    applicable <- TRUE
    # A condition can carry an empty message; the reason must stay non-empty or the
    # aggregation would downgrade it to NOT VERIFIED and lose the fact that a check
    # actually ran and actually failed.
    condition_text <- conditionMessage(attr(result, "condition"))
    if (!(is.character(condition_text) && length(condition_text) == 1 && nzchar(condition_text)))
      condition_text <- "assertion failed without a message"
    reason <- paste0("candidate_validation_error: ", substr(condition_text, 1, 300))
  }
  if (identical(status, "PASS") && !nzchar(detail)) detail <- reason
  check_details[[check_name]] <- if (nzchar(detail)) detail else reason
  checks[[length(checks) + 1]] <- list(name = check_name, status = status, applicable = applicable, reason = reason)
}
# INTENT: completeness is required, not vacuous all(logical(0)); exceptions cannot become N/A.
# REASONING: counters derive the verdict; a NULL/empty reason is NOT VERIFIED, never a silent pass.
profile <- c(passed = 0L, warning = 0L, failed = 0L, not_verified = 0L, skipped = 0L)
actual_names <- character(0)
for (i in seq_along(checks)) {
  entry <- checks[[i]]
  actual_names <- c(actual_names, entry[["name"]])
  reason_ok <- is.character(entry[["reason"]]) && length(entry[["reason"]]) == 1 && nzchar(entry[["reason"]])
  if (!isTRUE(reason_ok)) {
    entry[["status"]] <- "NOT_VERIFIED"
    entry[["applicable"]] <- TRUE
    entry[["reason"]] <- "check carries an empty reason"
    check_details[[entry[["name"]]]] <- entry[["reason"]]
  }
  if (!(entry[["status"]] %in% names(status_tokens))) {
    entry[["status"]] <- "NOT_VERIFIED"
    entry[["applicable"]] <- TRUE
    entry[["reason"]] <- "unrecognized validation status"
    check_details[[entry[["name"]]]] <- entry[["reason"]]
  }
  checks[[i]] <- entry
  counter <- counter_keys[[entry[["status"]]]]
  profile[counter] <- profile[counter] + 1L
  line <- if (entry[["name"]] %in% names(check_details)) check_details[[entry[["name"]]]] else entry[["reason"]]
  cat(status_tokens[[entry[["status"]]]], " ", entry[["name"]], ": ", line, "\n", sep = "")
}
all_passed <- profile[["failed"]] == 0L && profile[["not_verified"]] == 0L &&
  identical(actual_names, required_checks)
cat(sprintf("Checks: %d passed, %d warnings, %d failed, %d not verified, %d skipped\n",
            profile[["passed"]], profile[["warning"]], profile[["failed"]],
            profile[["not_verified"]], profile[["skipped"]]))
profile_verdict <- if (profile[["failed"]] > 0L || profile[["not_verified"]] > 0L || !all_passed ||
                       (profile[["passed"]] + profile[["warning"]] + profile[["failed"]]) == 0L) {
  "FAILED"
} else if (profile[["warning"]] > 0L) {
  "PASSED WITH WARNINGS"
} else {
  "PASSED"
}
cat("PROFILE VALIDATION: ", profile_verdict, "\n", sep = "")
report[["validation"]] <- list(checks = checks, all_passed = all_passed)
if (!all_passed) {
  cat("VALIDATION FAILED -- no reports written; do not share. Failed checks:\n")
  unresolved <- character(0)
  for (entry in checks) if (entry[["status"]] %in% c("FAIL", "NOT_VERIFIED")) unresolved <- c(unresolved, entry[["name"]])
  if (length(unresolved) > 0) {
    cat(paste(unresolved, collapse = ", "), "\n")
  } else {
    cat("(required checks missing from the validation list)\n")
  }
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
