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
- [Column types CPS-GEN can compare](#column-types-cps-gen-can-compare)
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
7. **Validate** synthetic-vs-profile (QAS-C, see `validation-checks.md`, which routes to `agent_reference/QA_CHECKPOINTS.md` § Synthetic-Path QA Checkpoints) and the shipped CPS-GEN block in `agent_reference/VALIDATION_CHECKPOINTS.md`, and write seeded parquet to `data/synthetic/`.

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

Draw categorical levels from the reported (suppressed) proportions. `__OTHER__` is one reserved aggregate, including any original source level literally named `__OTHER__` as well as pooled rare/rolled-in levels; that source label also counts toward `n_levels_binned`. Generate one synthetic bucket, never separate duplicate labels or reconstructed source detail. Validate label uniqueness before drawing. A fully-suppressed categorical column (`levels: []`, all levels sparse) carries no usable marginal. When `n_levels_binned > 0`, every source level was pooled away (the profiler's shape when the column's support is below the threshold), so fill it with the literal `__OTHER__` (or `NA`) and note that the column was withheld. `NA` is allowed, but a column filled with `NA` no longer matches its reported missing rate, so it may cost a `missingness_within_tolerance` WARNING; `__OTHER__` does not. Never fill it with `""`. CPS-GEN's `synthetic_levels_within_released_levels` admits `__OTHER__` for exactly this shape and nothing else, so an empty-string level is a synthetic level outside the released set and is a `[FAIL]`.

Check `available` before reading any cross-tab fields: `available:false` has only pair/n/reason, with no association fidelity target. When an available crosstab informs the draw, remember its `cells` array uses **`null` for suppressed cells** (not `0`): a `null` means "unknown, withheld" and must be skipped, while a real `0` means a genuine empty combination. Never treat a `null` as a zero-probability or a zero count. A crosstab carrying `"collapsed": true` was fully suppressed and offers no association signal at all. **Row and column order:** `cells` is row-major over the pair's *released categories*: the kept labels in code-point order (R `sort(kept, method = "radix")`, never the session locale's collation), then `__OTHER__` last when the column releases it. That is **not** the order of the column's categorical `levels` block, which lists counts descending. So map cells to labels by label — rebuild the category vector as `sort(kept, method = "radix")` plus `"__OTHER__"` only when it is released, and index `cells[[(i - 1) * cols + j]]` with it — never by pairing the `levels` list positionally with the rows or columns.

```r
# --- Generate a categorical column from suppressed level proportions (i selects the column) ---
# INTENT: reproduce category frequencies; __OTHER__ stays an explicit aggregate bucket.
# REASONING: write the column in the dtype the report DECLARES. CPS-GEN's column_set_and_dtypes
#            FAILs a character column where the report declares integer or double, and a
#            numeric or logical column where it declares string.
col     <- report$columns[[i]]
colname <- col$name
cat_blk <- col$categorical
levs    <- vapply(cat_blk$levels, \(l) l$value, character(1))
stopifnot(!anyDuplicated(levs))
counts  <- vapply(cat_blk$levels, \(l) l$count, numeric(1))
if (length(levs)) {
  draws <- sample(levs, size = n, replace = TRUE, prob = counts / sum(counts))
  if (col$dtype %in% c("integer", "double")) {
    # ASSUMES: a numeric-declared column's labels are numbers whose canonical text is the
    #          label itself, so the level checks still match them; no numeric type holds __OTHER__.
    stopifnot(!"__OTHER__" %in% levs)
    num <- suppressWarnings(as.double(levs))
    stopifnot(identical(ifelse(num == round(num), sprintf("%.0f", num), sprintf("%.17g", num)), levs))
    draws <- if (col$dtype == "integer") as.integer(draws) else as.double(draws)
  }
  syn[[colname]] <- draws
} else {
  # INTENT: a fully pooled column (levels: [], n_levels_binned > 0) gets the literal
  #         __OTHER__ placeholder; with nothing pooled, or a numeric dtype, NA.
  # REASONING: CPS-GEN admits __OTHER__ as the one label a fully pooled column may carry;
  #            "" is a level outside the released set and FAILs the level checks.
  syn[[colname]] <- switch(col$dtype, integer = rep(NA_integer_, n), double = rep(NA_real_, n),
                           rep(if (cat_blk$n_levels_binned > 0) "__OTHER__" else NA_character_, n))
  cat(colname, "NOT_APPLICABLE: unobserved categorical distribution", "\n")
}
```

**Write the declared dtype.** The shipped profilers make a column categorical only when it is text, so they declare every categorical `string`, and the character branch is the one their reports exercise. That covers logical source columns too. The R profiler releases any logical column as the labels `TRUE`/`FALSE`, and the Python profiler releases a boolean column that has nulls as `True`/`False`, both declared `string`. Keep them `character`: a `logical` column fails `column_set_and_dtypes` against a declared `string`. (A Python boolean column with no nulls is profiled as an `integer` numeric column of 0/1, not as a categorical.) The integer/double branch serves a report that declares a numeric categorical, which the shipped profilers do not produce. It stops rather than write a column CPS-GEN must fail: no numeric type holds `__OTHER__`, and each label has to come back unchanged through the canonical text form (see [Column types CPS-GEN can compare](#column-types-cps-gen-can-compare)), so `"1"` works and `"1.0"` does not.

## Identifier columns

Identifier columns arrive without raw identifier values. Generate explicitly synthetic scaffolds matching the declared dtype and available length/pattern targets; unavailable structure gets NOT_APPLICABLE fidelity independently of dtype. Preserve eligible missingness. A profile alone cannot establish noncollision with unknown real identifiers.

```r
# --- Synthesize an identifier column structurally (unique, value-free scaffold) ---
# INTENT: produce right-shaped-but-fake identifiers; REASONING: real values never crossed the boundary.
# REASONING: CPS-GEN's identifier_columns_value_free FAILs an identifier column that repeats a
#            value or equals any released categorical label, so every branch is index-based
#            (unique by construction) and is checked against the released labels before use.
col <- report$columns[[match(colname, col_names)]]
struct <- col$string_structure
released <- character(0)
for (cc in report$columns) if (identical(cc$role, "categorical"))
  for (l in cc$categorical$levels) released <- c(released, l$value)
# Availability logging is independent of dtype: numeric identifiers also lose structure.
if (isTRUE(struct$withheld)) cat(colname, "NOT_APPLICABLE: unobserved identifier structure", "\n")
if (col$dtype %in% c("integer", "double")) {
  # Structure-only numeric ID: preserve type, not an invented numeric marginal.
  # REASONING: offset away from integer-coded released labels ("1", "2", ...).
  ids <- 10000000L + seq_len(n)
  vals <- sprintf("%d", ids)                 # the canonical text CPS-GEN compares with labels
  syn[[colname]] <- if (col$dtype == "integer") ids else as.double(ids)
} else {
  if (isTRUE(struct$withheld)) {
    vals <- sprintf("ID%07d", seq_len(n))    # no length/pattern target: a prefixed index
  } else if (isTRUE(struct$pattern_flags$email)) {
    vals <- sprintf("user%06d@example.invalid", seq_len(n))
  } else {
    # The reported mean length, widened only when n needs more digits than that leaves.
    width <- max(round(struct$length_mean) - 2, nchar(n))
    vals <- paste0("ID", formatC(seq_len(n), width = width, flag = "0"))
  }
  syn[[colname]] <- vals
}
stopifnot(!anyDuplicated(vals), !any(vals %in% released))  # unique, and reuses no released label
```

Use reserved non-routable email domains (`example.invalid`) and explicitly label identifier scaffolds as synthetic. Numeric/string placeholders can coincidentally equal unknown real values; do not promise noncollision or demand that every synthetic value look unlike anything real.

**Unique, and offset away from released labels.** Real values are unknowable, but released labels are not. CPS-GEN's `identifier_columns_value_free` tests two things: every non-null identifier value is unique across rows, and none has a canonical text (see [Column types CPS-GEN can compare](#column-types-cps-gen-can-compare)) equal to a level label released for *any* categorical column. Random draws guarantee neither: `sample()` of two alphanumerics over a few hundred rows repeats values, and a one-character draw can equal a released label such as `"a"`. So each branch above is an index. A withheld structure gets a plain prefixed index rather than one repeated placeholder: `""` on every row is one value repeated, which fails the uniqueness test. Many reports release integer-coded labels (`"1"`, `"2"`, …), so `seq_len(n)` collides with them, and so does a double ID such as `1`. Start numeric IDs above every integer-coded released label. The default above starts just past 10,000,000, which is safe unless a report releases labels that large. Character IDs carry a non-numeric prefix (`ID0000001`). The `stopifnot()` at the end checks both rules against this report's own labels, so a collision stops generation instead of failing CPS-GEN later; if it fires, change the prefix or the offset. Missingness injected afterwards does not break uniqueness, because the check ignores nulls.

## Free-text `role: "string"` columns

A column with `role: "string"` (high-cardinality free text, non-identifier) arrives value-free — only length stats + pattern flags. Generate right-shaped fake strings from the length stats; **never** reconstruct real content. Seeded random alphanumerics of the reported mean length are enough for code development (or `stringi`/a wordlist if the code needs word-like tokens).

```r
# --- Synthesize free-text (role "string") columns from length stats only ---
# INTENT: right-shaped fake strings; REASONING: no real values ever crossed the boundary.
# REASONING: the snippet walks every role "string" column itself, so it needs no column
#            selected by the categorical or identifier snippets; a report can carry free text
#            and no identifier. Draws use the RNG seeded by set.seed() in the T1 Config.
# ASSUMES: the T1 snippet defined report, n, and syn.
for (col in report$columns) {
  if (!identical(col$role, "string")) next
  struct <- col$string_structure
  syn[[col$name]] <- rep("", n)
  if (isTRUE(struct$withheld)) {
    cat(col$name, "NOT_APPLICABLE: unobserved string structure", "\n")
  } else {
    L <- round(struct$length_mean)
    alnum <- c(0:9, letters)
    for (j in seq_len(n)) syn[[col$name]][j] <- paste0(sample(alnum, L, replace = TRUE), collapse = "")
  }
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

## Column types CPS-GEN can compare

CPS-GEN (`agent_reference/VALIDATION_CHECKPOINTS.md` § CPS-GEN: Synthetic Generation Validation (DS-5)) compares synthetic values with the report's released labels as text, and its Python and R blocks must read every value the same way. The R block classifies each column by the arrow type `write_parquet()` stored, so every synthetic column has to land in one of these classes:

| Class | R column type → stored arrow type | Note |
|---|---|---|
| text | `character` → `string` | A column the report declares `string` must be this plain string type |
| text (dictionary-encoded) | `factor` → `dictionary<values=string>` | Compared as its string values, but `column_set_and_dtypes` does **not** accept it for a declared `string` column. Keep categoricals as `character` (`sample()` on a character vector already does) |
| integer | `integer` → `int32`; `bit64::integer64` → `int64` | Every value must be below 2^53 in magnitude |
| float | `double` → `double` | |
| boolean | `logical` → `bool` | |

Anything else counts as "other": `Date`, `POSIXct`, `difftime`, `hms`, list columns, and decimal or binary types. So does an integer column holding a value of 2^53 or more. A categorical or identifier column of that kind is a `[FAIL]` (`column '<c>' holds values outside the text-comparable types (string, categorical, integer below 2^53, float, boolean) — its levels cannot be compared`). Write dates as ISO text, as the free-text section does. Declared dtypes are matched by class: `string` needs a plain string column, `double` accepts integer or double, and `integer` accepts an integer column or a double column whose values are all whole.

**Canonical text form.** Before any comparison with released labels, each synthetic value becomes one canonical text, identical in both languages and matching what the profilers write as labels:

- Text is used as written.
- An integer, or a finite double with a whole value, becomes integer text (`sprintf("%.0f", v + 0)`), so `1L` and `1` both become `"1"` and `-0` becomes `"0"`.
- Any other finite double becomes `%.17g` text. Infinities become `inf` / `-inf`, and `NaN` counts as missing.
- A logical becomes `true` / `false` and is compared with released labels case-insensitively, so the R profiler's `"TRUE"` and the Python profiler's `"True"` both match.

An integer-coded categorical can therefore be written in its declared integer type and still match its released labels. A non-whole double label is fragile, so write such a column as the released strings when the report declares it `string`. The same canonical text is what an identifier must never equal (see the identifier offset above).

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
