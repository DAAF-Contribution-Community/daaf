# Generation Patterns — R (Flagship)

How to construct a seeded synthetic dataset *from a profile report alone* in R, using `simstudy` (Gaussian copula from marginals + a correlation matrix) with `fabricatr` for hierarchical structure. This is DS-5 generation on the DAAF side of the boundary: the input is the returned JSON report (`profiling-script-spec.md`), never real data. R is DAAF's flagship path; the Python equivalents are in `generation-patterns-python.md`.

## Contents

- [Why simstudy fits the profile boundary](#why-simstudy-fits-the-profile-boundary)
- [The generation recipe](#the-generation-recipe)
- [T1: schema-only skeleton](#t1-schema-only-skeleton)
- [T2: marginals](#t2-marginals)
- [T3: relationships via copula](#t3-relationships-via-copula)
- [Categorical generation and the __OTHER__ bucket](#categorical-generation-and-the-__other__-bucket)
- [Identifier columns](#identifier-columns)
- [Missingness](#missingness)
- [fabricatr for hierarchical structure](#fabricatr-for-hierarchical-structure)
- [Seeding and output](#seeding-and-output)
- [Caveats](#caveats)

## Why simstudy fits the profile boundary

`simstudy` generates data from *declarations* — a distribution family plus parameters, and a correlation matrix — with **no microdata** (`synthetic-data-research.md` §1). That is exactly the profile boundary: the report gives us marginal parameters (percentiles, mean/SD, category proportions) and, at T3, a correlation matrix. `simstudy::genCorGen` / `addCorGen` draw correlated variables through a Gaussian copula given those inputs. Nothing fits on real rows, so nothing about the real data is needed or touched.

`synthpop`/SDV are deliberately *not* used here — they fit on real data and belong to the T4 local path (`local-synthesis-t4.md`).

## The generation recipe

1. **Read the report.** Parse the JSON; pull `row_count`, the per-column blocks, and (T3) the correlation matrix.
2. **Generate numerics** through a copula so their correlations match (T3) or independently (T2).
3. **Map each numeric to its target marginal.** simstudy draws standard normals with the target correlation structure; transform each to the target distribution by matching the reported percentiles/mean-SD.
4. **Generate categoricals** from the reported (suppressed) level proportions, including an `__OTHER__` draw.
5. **Synthesize identifier columns** structurally (right length/shape, fake values) — never reproduce real values.
6. **Inject missingness** per column at the reported rate.
7. **Validate** synthetic-vs-profile (`validation-checks.md` QA(c)) and write seeded parquet to `data/synthetic/`.

## T1: schema-only skeleton

At T1 the report carries only names, dtypes, and row count. Generate a correctly-typed, correctly-sized frame with placeholder values — enough for code to compile and run, nothing more.

```r
# --- Config ---
library(jsonlite)
library(arrow)
set.seed(20260715L)  # INTENT: reproducible synthesis; REASONING: doctrine requires seeded generation

report <- fromJSON("clients_2025_profile_report.json", simplifyVector = FALSE)
n <- report$dataset$row_count
col_names <- character(0)
for (col in report$columns) col_names <- c(col_names, col$name)  # also used by T2/T3 snippets

# --- Generate (T1 skeleton) ---
# INTENT: one placeholder column per reported column, typed to the reported dtype.
# ASSUMES: T1 carries no values — placeholders are intentionally non-informative.
stopifnot(identical(report$report_version, "2.0"))  # legacy: preserve and request local rerun
syn <- as.data.frame(lapply(report$columns, \(col) {
  switch(col$dtype,
    integer = rep(0L, n),
    double  = rep(0, n),
    string  = rep("", n),
    rep(NA, n)
  )
}), stringsAsFactors = FALSE)
names(syn) <- vapply(report$columns, \(c) c$name, character(1))
stopifnot(nrow(syn) == n)  # validate row count matches profile
```

## T2: marginals

First classify each `2.0` numeric shape; then draw eligible nonconstants against released percentiles/moments and categoricals against supported proportions — **independently** (T2 carries no relationships). Generate supported constants faithfully; withheld distributions use typed placeholders with unobserved fidelity, preserving separately reported missingness. Legacy `1.0` reports are preserved, not relabeled: request a corrected local rerun before accepting this policy. For T1, value/missingness/relationship fidelity is NOT_APPLICABLE; structural/type/seed checks still apply.

For numerics, the report's percentiles are the most faithful marginal descriptor (min/max were withheld). Two workable approaches:

- **Percentile interpolation (preferred when percentiles are present):** treat the nine reported percentiles as an empirical inverse-CDF and draw by inverse-transform sampling with linear interpolation between the percentile knots. This honors shape (skew, spread) without assuming normality.
- **Moment matching (fallback):** if only mean/SD are usable, draw from a normal (or a distribution family inferred from the percentile spacing) with those moments.

```r
# --- Generate one numeric column (all 2.0 shapes; i selects the column) ---
# INTENT: branch BEFORE using percentiles or missingness; absent targets stay unobserved.
# REASONING: a withheld distribution is not zero-valued evidence; constants are evidence.
# ASSUMES: DS-3 already validated the 2.0 schema and support counts.
stopifnot(identical(report$report_version, "2.0"))  # legacy: request corrected local rerun
col <- report$columns[[i]]
num <- col$numeric
if (isTRUE(num$all_missing)) {
  col_vals <- rep(NA_real_, n)
  fidelity <- "NOT_APPLICABLE: all-missing distribution"
} else if (isTRUE(num$withheld)) {
  col_vals <- rep(0, n)  # typed scaffold, NOT an estimated value or distribution
  fidelity <- paste("NOT_APPLICABLE: unobserved distribution", num$reason)
} else if (isTRUE(num$constant)) {
  col_vals <- rep(num$value, n)
  fidelity <- "AVAILABLE: supported constant target"
} else {
  p <- num$percentiles
  keys <- if (isTRUE(num$small_n)) c("p25", "p50", "p75") else
    c("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
  probs <- as.numeric(sub("p", "", keys, fixed = TRUE)) / 100
  knots <- as.numeric(unlist(p[keys]))
  col_vals <- approx(probs, knots, xout = runif(n), rule = 2)$y
  fidelity <- "AVAILABLE: released percentile targets only"
}
if (col$dtype == "integer") {
  # Base R integers are 32-bit: fail rather than silently overflow; use a reviewed
  # integer64 path for larger reported integer domains.
  stopifnot(all(is.na(col_vals) | abs(col_vals) <= .Machine$integer.max))
  col_vals <- as.integer(round(col_vals))
} else col_vals <- as.double(col_vals)
syn[[col$name]] <- col_vals
cat(col$name, fidelity, "\n")  # record in log; AVAILABLE is not a QA PASS
# Independently apply the reported missingness recipe below, including to placeholders.
```

Validate only the branch's available targets: emitted percentiles for reduced/full summaries, the shared value for constants, and NOT_APPLICABLE distribution fidelity for withheld/all-missing blocks. Do not reuse stale `knots` from another column. Structural/type/seed and separately available missingness checks still apply (`validation-checks.md`).

## T3: relationships via copula

At T3 draw the numeric columns *jointly* through a Gaussian copula so their pairwise correlations match the reported matrix, then map each margin to its target distribution as in T2.

The snippet below is **illustrative pseudocode to inline** (per DAAF's sequential, no-function-definitions style — do not define `get_percentiles`; pull the knots inline as shown):

```r
# --- Generate correlated numerics (T3) ---
library(simstudy)
# INTENT: draw standard-normal variates carrying the reported Pearson correlation, then
#         transform each margin to its reported percentile shape.
# ASSUMES: the reported correlation matrix is valid (symmetric, unit diagonal); if it is not
#          positive semidefinite, nearPD-project it first (see validation-checks.md tolerance note).
# Generate ALL marginals via the shape-aware T2 recipe first. Overwrite only eligible
# correlated marginals here; inject missingness AFTER this block.
col_names <- character(0)
for (col in report$columns) col_names <- c(col_names, col$name)
probs <- c(.01,.05,.10,.25,.50,.75,.90,.95,.99)
block <- report$relationships$pearson
if (is.null(block) || !isTRUE(block$available)) {
  cat("NOT_APPLICABLE: correlation target", if (is.null(block)) "not released" else block$reason, "\n")
} else {
  num_cols <- unlist(block$columns)
  k <- length(num_cols)
  corr <- matrix(unlist(block$matrix), nrow = k, byrow = TRUE)
  for (cname in num_cols) stopifnot(setequal(names(report$columns[[match(cname, col_names)]]$numeric),
                                           c("n", "mean", "sd", "percentiles")))
  # Constants, withheld, reduced, and all-missing columns are not matrix inputs.
  z <- genCorGen(n, nvars = k, corMatrix = corr, dist = "normal",
                 params1 = rep(0, k), params2 = rep(1, k), wide = TRUE)
  for (j in seq_len(k)) {
    col <- report$columns[[match(num_cols[j], col_names)]]
    p <- col$numeric$percentiles
    knots <- c(p$p1,p$p5,p$p10,p$p25,p$p50,p$p75,p$p90,p$p95,p$p99)
    vals <- approx(probs, knots, xout = pnorm(z[[paste0("V", j)]]), rule = 2)$y
    if (col$dtype == "integer") {
      stopifnot(all(is.na(vals) | abs(vals) <= .Machine$integer.max))
      vals <- as.integer(round(vals))
    }
    syn[[num_cols[j]]] <- vals
  }
}
```

### Named numeric~numeric relationships (`relationships.named`)

When the report carries an **available** named relationship (`{outcome, predictor, n, available:true, pearson, spearman, ols: {intercept, slope, r_squared}}`), honor the linear structure directly rather than only the correlation: generate the predictor from its marginal, then build the outcome as `intercept + slope·predictor + N(0, residual SD)`, with the residual SD backed out of R².

```r
# --- Honor a named linear relationship (illustrative; inline, no function defs) ---
for (rel in report$relationships$named) {
  if (!isTRUE(rel$available)) {
    cat("NOT_APPLICABLE: named relationship", rel$reason, "\n")
    next
  }
  # Use generated marginals BEFORE missingness injection.
  x_pred <- syn[[rel$predictor]]
  col <- report$columns[[match(rel$outcome, col_names)]]
  sd_y <- col$numeric$sd
  resid_sd <- sqrt(max(1 - rel$ols$r_squared, 0)) * sd_y
  vals <- rel$ols$intercept + rel$ols$slope * x_pred + rnorm(n, 0, resid_sd)
  if (col$dtype == "integer") {
    stopifnot(all(is.na(vals) | abs(vals) <= .Machine$integer.max))
    vals <- as.integer(round(vals))
  }
  syn[[rel$outcome]] <- vals
}
```

This reproduces the reported slope/intercept within tolerance (the synthetic OLS slope lands near the declared slope) and gives the outcome a realistic conditional spread. Categorical associations (Cramér's V) are weaker constraints; reproduce categoricals from their marginals (below) and, when a named *categorical* association matters, bias the linked draw conditional on the other variable. Perfect joint reproduction is neither possible nor the goal — structural validity for code development is.

## Categorical generation and the `__OTHER__` bucket

Draw categorical levels from the reported (suppressed) proportions. `__OTHER__` is one reserved aggregate, including any original source level literally named `__OTHER__` as well as pooled rare/rolled-in levels; that source label also counts toward `n_levels_binned`. Generate one synthetic bucket, never separate duplicate labels or reconstructed source detail. Validate label uniqueness before drawing. A fully-suppressed categorical column (`levels: []`, all levels sparse) carries no usable marginal — synthesize a single constant placeholder level and note the column was withheld.

Check `available` before reading any cross-tab fields: `available:false` has only pair/n/reason, with no association fidelity target. When an available crosstab informs the draw, remember its `cells` array uses **`null` for suppressed cells** (not `0`): a `null` means "unknown, withheld" and must be skipped, while a real `0` means a genuine empty combination. Never treat a `null` as a zero-probability or a zero count. A crosstab carrying `"collapsed": true` was fully suppressed and offers no association signal at all.

```r
# --- Generate a categorical column from suppressed level proportions ---
# INTENT: reproduce category frequencies; __OTHER__ stays an explicit aggregate bucket.
levs   <- vapply(cat$levels, \(l) l$value, character(1))
stopifnot(!anyDuplicated(levs))
counts <- vapply(cat$levels, \(l) l$count, numeric(1))
if (length(levs)) {
  syn[[colname]] <- sample(levs, size = n, replace = TRUE, prob = counts / sum(counts))
} else {
  syn[[colname]] <- rep("", n)
  cat(colname, "NOT_APPLICABLE: unobserved categorical distribution", "\n")
}
```

## Identifier columns

Identifier columns arrive without raw identifier values. Generate explicitly synthetic scaffolds matching the declared dtype and available length/pattern targets; unavailable structure gets NOT_APPLICABLE fidelity independently of dtype. Preserve eligible missingness. A profile alone cannot establish noncollision with unknown real identifiers.

```r
# --- Synthesize an email-shaped identifier structurally ---
# INTENT: produce right-shaped-but-fake identifiers; REASONING: real values never crossed the boundary.
col <- report$columns[[match(colname, col_names)]]
struct <- col$string_structure
# Availability logging is independent of dtype: numeric identifiers also lose structure.
if (isTRUE(struct$withheld)) cat(colname, "NOT_APPLICABLE: unobserved identifier structure", "\n")
if (col$dtype %in% c("integer", "double")) {
  # Structure-only numeric ID: preserve type, not an invented numeric marginal.
  syn[[colname]] <- if (col$dtype == "integer") seq_len(n) else as.double(seq_len(n))
} else if (isTRUE(struct$withheld)) {
  syn[[colname]] <- rep("", n)
} else if (isTRUE(struct$pattern_flags$email)) {
  syn[[colname]] <- sprintf("user%06d@example.invalid", seq_len(n))
} else {
  L <- round(struct$length_mean)
  syn[[colname]] <- rep("", n)
  for (j in seq_len(n)) syn[[colname]][j] <- paste0(sample(c(0:9, letters), L, replace = TRUE), collapse = "")
}
```

Use reserved non-routable email domains (`example.invalid`) and explicitly label identifier scaffolds as synthetic. Numeric/string placeholders can coincidentally equal unknown real values; do not promise noncollision or demand that every synthetic value look unlike anything real.

## Free-text `role: "string"` columns

A column with `role: "string"` (high-cardinality free text, non-identifier) arrives value-free — only length stats + pattern flags. Generate right-shaped fake strings from the length stats; **never** reconstruct real content. Seeded random alphanumerics of the reported mean length are enough for code development (or `stringi`/a wordlist if the code needs word-like tokens).

```r
# --- Synthesize a free-text (role "string") column from length stats only ---
# INTENT: right-shaped fake strings; REASONING: no real values ever crossed the boundary.
struct <- report$columns[[match(colname, col_names)]]$string_structure
syn[[colname]] <- rep("", n)
if (isTRUE(struct$withheld)) {
  cat(colname, "NOT_APPLICABLE: unobserved string structure", "\n")
} else {
  L <- round(struct$length_mean)
  alnum <- c(0:9, letters)
  for (j in seq_len(n)) syn[[colname]][j] <- paste0(sample(alnum, L, replace = TRUE), collapse = "")
}
```

If a `date` pattern flag is set, emit ISO-shaped fake dates (`sprintf("%04d-%02d-%02d", ...)`) instead of random strings, so downstream date parsing still exercises.

## Missingness

Inject missingness per column at the reported rate. The profile carries only the *rate*, not the *mechanism* — so this is MCAR by construction, and that limitation must be stated (real missingness is usually systematic; see `synthetic-data-research.md` §4).

```r
# --- Inject missingness at the reported rate ---
# ASSUMES: MCAR — the profile carries only a rate, not a mechanism. Real missingness is often systematic;
#          this is a known fidelity limitation of profile-based synthesis (state it in the skill notice).
# Run only at T2+ and after shape-aware marginal/relationship generation.
# Keep this eligible target even for a withheld value summary; numerator rarity is not a veto.
rate <- report$columns[[i]]$missing_rate
if (rate > 0) {
  idx <- sample(n, size = round(rate * n))
  syn[[colname]][idx] <- NA
}
```

## fabricatr for hierarchical structure

When the real data is nested (students in schools, visits in patients) and the profile records that structure, `fabricatr::add_level` builds the hierarchy declaratively (`synthetic-data-research.md` §1). Use it to generate the level sizes and nest lower-level records within higher-level units, then apply the marginal/relationship draws above within levels. fabricatr honors marginals, categorical proportions, nested structure, and pairwise rank correlation, but has no full-matrix copula solve — so for multi-way numeric correlation, generate numerics with simstudy and attach them to the fabricatr scaffold.

## Seeding and output

- **Always** `set.seed()` at the top with a recorded integer seed. The seed goes into the generation log so the synthetic data is exactly reproducible.
- Write parquet to the project's `data/synthetic/` directory (create on first use), named per DAAF conventions (`{date}_{description}_synthetic.parquet`).
- Write a generation log recording: source report path + `report_version`, seed, tier, library versions, and the synthetic-vs-profile validation results.

```r
# --- Save ---
dir.create("data/synthetic", showWarnings = FALSE, recursive = TRUE)
write_parquet(syn, "data/synthetic/2026-07-15_clients_synthetic.parquet")
cat("Seed:", 20260715L, "| rows:", nrow(syn), "| tier:", report$settings$tier, "\n")
```

## Caveats

- **simstudy recovers Poisson correlation more faithfully than binary** (`synthetic-data-research.md` §1) — for binary/low-cardinality columns, expect the achieved correlation to fall somewhat short of the target; validate and report the gap rather than forcing it.
- **A correlation matrix from a suppressed profile may not be positive semidefinite** (rounding, partial columns). Project to the nearest PD matrix (`Matrix::nearPD`) before the copula draw, and note that this slightly perturbs the target correlations — the validation tolerance in `validation-checks.md` accounts for it.
- **Do not fabricate withheld structure.** If the profile suppressed something, the synthetic data should reflect that absence (e.g., `__OTHER__` stays a bucket), not invent plausible-looking detail. Fabricated structure is worse than absent structure because it looks trustworthy.
