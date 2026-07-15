# Generation Patterns — R (Flagship)

How to construct a seeded synthetic dataset *from a profile report alone* in R, using `simstudy` (Gaussian copula from marginals + a correlation matrix) with `fabricatr` for hierarchical structure. This is DS-5 generation on the DAAF side of the boundary: the input is the returned JSON report (`profiling-script-spec.md`), never real data. R is DAAF's flagship path; the Python equivalents are in `generation-patterns-python.md`.

## Contents

- [Why simstudy fits the profile boundary](#why-simstudy)
- [The generation recipe](#recipe)
- [T1: schema-only skeleton](#t1-skeleton)
- [T2: marginals](#t2-marginals)
- [T3: relationships via copula](#t3-relationships)
- [Categorical generation and the __OTHER__ bucket](#categorical)
- [Identifier columns](#identifiers)
- [Missingness](#missingness)
- [fabricatr for hierarchical structure](#fabricatr)
- [Seeding and output](#seeding-output)
- [Caveats](#caveats)

## Why simstudy fits the profile boundary {#why-simstudy}

`simstudy` generates data from *declarations* — a distribution family plus parameters, and a correlation matrix — with **no microdata** (`synthetic-data-research.md` §1). That is exactly the profile boundary: the report gives us marginal parameters (percentiles, mean/SD, category proportions) and, at T3, a correlation matrix. `simstudy::genCorGen` / `addCorGen` draw correlated variables through a Gaussian copula given those inputs. Nothing fits on real rows, so nothing about the real data is needed or touched.

`synthpop`/SDV are deliberately *not* used here — they fit on real data and belong to the T4 local path (`local-synthesis-t4.md`).

## The generation recipe {#recipe}

1. **Read the report.** Parse the JSON; pull `row_count`, the per-column blocks, and (T3) the correlation matrix.
2. **Generate numerics** through a copula so their correlations match (T3) or independently (T2).
3. **Map each numeric to its target marginal.** simstudy draws standard normals with the target correlation structure; transform each to the target distribution by matching the reported percentiles/mean-SD.
4. **Generate categoricals** from the reported (suppressed) level proportions, including an `__OTHER__` draw.
5. **Synthesize identifier columns** structurally (right length/shape, fake values) — never reproduce real values.
6. **Inject missingness** per column at the reported rate.
7. **Validate** synthetic-vs-profile (`validation-checks.md` QA(c)) and write seeded parquet to `data/synthetic/`.

## T1: schema-only skeleton {#t1-skeleton}

At T1 the report carries only names, dtypes, and row count. Generate a correctly-typed, correctly-sized frame with placeholder values — enough for code to compile and run, nothing more.

```r
# --- Config ---
library(jsonlite)
library(arrow)
set.seed(20260715L)  # INTENT: reproducible synthesis; REASONING: doctrine requires seeded generation

report <- fromJSON("clients_2025_profile_report.json", simplifyVector = FALSE)
n <- report$dataset$row_count

# --- Generate (T1 skeleton) ---
# INTENT: one placeholder column per reported column, typed to the reported dtype.
# ASSUMES: T1 carries no values — placeholders are intentionally non-informative.
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

## T2: marginals {#t2-marginals}

Draw each numeric column to match its reported percentiles and mean/SD, and each categorical to match its level proportions — **independently** (T2 carries no relationships).

For numerics, the report's percentiles are the most faithful marginal descriptor (min/max were withheld). Two workable approaches:

- **Percentile interpolation (preferred when percentiles are present):** treat the nine reported percentiles as an empirical inverse-CDF and draw by inverse-transform sampling with linear interpolation between the percentile knots. This honors shape (skew, spread) without assuming normality.
- **Moment matching (fallback):** if only mean/SD are usable, draw from a normal (or a distribution family inferred from the percentile spacing) with those moments.

```r
# --- Generate one numeric column from reported percentiles (T2) ---
# INTENT: reproduce the marginal shape using the percentile grid as an empirical quantile function.
# REASONING: min/max are withheld at T2+; percentiles are the disclosure-safe shape descriptor.
p <- report$columns[[i]]$numeric$percentiles
probs <- c(.01,.05,.10,.25,.50,.75,.90,.95,.99)
knots <- c(p$p1,p$p5,p$p10,p$p25,p$p50,p$p75,p$p90,p$p95,p$p99)
u <- runif(n)
# inverse-transform via linear interpolation over the percentile knots
col_vals <- approx(x = probs, y = knots, xout = u, rule = 2)$y
if (report$columns[[i]]$dtype == "integer") col_vals <- round(col_vals)
```

Validate immediately: the synthetic column's own percentiles should land within tolerance of `knots` (that check is formalized in `validation-checks.md`).

## T3: relationships via copula {#t3-relationships}

At T3 draw the numeric columns *jointly* through a Gaussian copula so their pairwise correlations match the reported matrix, then map each margin to its target distribution as in T2.

The snippet below is **illustrative pseudocode to inline** (per DAAF's sequential, no-function-definitions style — do not define `get_percentiles`; pull the knots inline as shown):

```r
# --- Generate correlated numerics (T3) ---
library(simstudy)
# INTENT: draw standard-normal variates carrying the reported Pearson correlation, then
#         transform each margin to its reported percentile shape.
# ASSUMES: the reported correlation matrix is valid (symmetric, unit diagonal); if it is not
#          positive semidefinite, nearPD-project it first (see validation-checks.md tolerance note).
# NOTE: only FULL-summary numerics appear in the correlation matrix — small_n / near_constant /
#       all_missing numerics are excluded, so every column here has a full p1..p99 grid.
corr <- matrix(unlist(report$relationships$pearson$matrix), nrow = k, byrow = TRUE)
num_cols  <- unlist(report$relationships$pearson$columns)
col_names <- vapply(report$columns, function(c) c$name, character(1))  # name -> index lookup
probs <- c(.01,.05,.10,.25,.50,.75,.90,.95,.99)

# genCorGen draws k correlated variables via a Gaussian copula from the correlation matrix alone
z <- genCorGen(n, nvars = k, corMatrix = corr, dist = "normal",
               params1 = rep(0, k), params2 = rep(1, k), wide = TRUE)
# transform each standard-normal margin (via its uniform PIT) to the target percentiles
for (j in seq_len(k)) {
  u_j <- pnorm(z[[paste0("V", j)]])                       # probability integral transform
  p   <- report$columns[[ which(col_names == num_cols[j]) ]]$numeric$percentiles  # inline: pull knots
  knots <- c(p$p1,p$p5,p$p10,p$p25,p$p50,p$p75,p$p90,p$p95,p$p99)
  syn[[num_cols[j]]] <- approx(probs, knots, xout = u_j, rule = 2)$y
}
```

### Named numeric~numeric relationships (`relationships.named`)

When the report carries a named relationship (`{outcome, predictor, pearson, spearman, ols: {intercept, slope, r_squared}, n}`), honor the linear structure directly rather than only the correlation: generate the predictor from its marginal, then build the outcome as `intercept + slope·predictor + N(0, residual SD)`, with the residual SD backed out of R².

```r
# --- Honor a named linear relationship (illustrative; inline, no function defs) ---
rel <- report$relationships$named[[1]]                    # {outcome, predictor, ols:{...}}
# predictor from its percentile marginal (as in the T2 numeric recipe)
# ... x_pred generated above ...
sd_y     <- report$columns[[ which(col_names == rel$outcome) ]]$numeric$sd
resid_sd <- sqrt(max(1 - rel$ols$r_squared, 0)) * sd_y    # residual SD from R^2
syn[[rel$outcome]] <- rel$ols$intercept + rel$ols$slope * x_pred + rnorm(n, 0, resid_sd)
```

This reproduces the reported slope/intercept within tolerance (the synthetic OLS slope lands near the declared slope) and gives the outcome a realistic conditional spread. Categorical associations (Cramér's V) are weaker constraints; reproduce categoricals from their marginals (below) and, when a named *categorical* association matters, bias the linked draw conditional on the other variable. Perfect joint reproduction is neither possible nor the goal — structural validity for code development is.

## Categorical generation and the `__OTHER__` bucket {#categorical}

Draw categorical levels from the reported (suppressed) proportions. `__OTHER__` is an aggregate of binned rare levels — generate it as a single synthetic level literally labeled `__OTHER__` (do not invent fake real-looking rare values; that would fabricate structure the profile deliberately withheld). A fully-suppressed categorical column (`levels: []`, all levels sparse) carries no usable marginal — synthesize a single constant placeholder level and note the column was withheld.

When a crosstab informs the draw, remember its `cells` array uses **`null` for suppressed cells** (not `0`): a `null` means "unknown, withheld" and must be skipped, while a real `0` means a genuine empty combination. Never treat a `null` as a zero-probability or a zero count. A crosstab carrying `"collapsed": true` was fully suppressed and offers no association signal at all.

```r
# --- Generate a categorical column from suppressed level proportions ---
# INTENT: reproduce category frequencies; __OTHER__ stays an explicit aggregate bucket.
levs   <- vapply(cat$levels, \(l) l$value, character(1))
counts <- vapply(cat$levels, \(l) l$count, numeric(1))
syn[[colname]] <- sample(levs, size = n, replace = TRUE, prob = counts / sum(counts))
```

## Identifier columns {#identifiers}

Identifier columns arrive value-free (structure-only). Synthesize fresh fake identifiers of the right shape from the reported length stats and pattern flags — never anything resembling a real value.

```r
# --- Synthesize an email-shaped identifier structurally ---
# INTENT: produce right-shaped-but-fake identifiers; REASONING: real values never crossed the boundary.
if (isTRUE(struct$pattern_flags$email)) {
  syn[[colname]] <- sprintf("user%06d@example.invalid", seq_len(n))
} else {
  # generic id of approximately the reported mean length
  L <- round(struct$length_mean)
  syn[[colname]] <- vapply(seq_len(n), \(x) paste0(
    sample(c(0:9, letters), L, replace = TRUE), collapse = ""), character(1))
}
```

Use reserved non-routable forms (`example.invalid`) so synthetic identifiers can never collide with real addresses/domains.

## Free-text `role: "string"` columns {#string-role}

A column with `role: "string"` (high-cardinality free text, non-identifier) arrives value-free — only length stats + pattern flags. Generate right-shaped fake strings from the length stats; **never** reconstruct real content. Seeded random alphanumerics of the reported mean length are enough for code development (or `stringi`/a wordlist if the code needs word-like tokens).

```r
# --- Synthesize a free-text (role "string") column from length stats only ---
# INTENT: right-shaped fake strings; REASONING: no real values ever crossed the boundary.
L <- round(report$columns[[ which(col_names == colname) ]]$string_structure$length_mean)
alnum <- c(0:9, letters)
syn[[colname]] <- vapply(seq_len(n),
  function(i) paste0(sample(alnum, L, replace = TRUE), collapse = ""), character(1))
```

If a `date` pattern flag is set, emit ISO-shaped fake dates (`sprintf("%04d-%02d-%02d", ...)`) instead of random strings, so downstream date parsing still exercises.

## Missingness {#missingness}

Inject missingness per column at the reported rate. The profile carries only the *rate*, not the *mechanism* — so this is MCAR by construction, and that limitation must be stated (real missingness is usually systematic; see `synthetic-data-research.md` §4).

```r
# --- Inject missingness at the reported rate ---
# ASSUMES: MCAR — the profile carries only a rate, not a mechanism. Real missingness is often systematic;
#          this is a known fidelity limitation of profile-based synthesis (state it in the skill notice).
rate <- report$columns[[i]]$missing_rate
if (rate > 0) {
  idx <- sample(n, size = round(rate * n))
  syn[[colname]][idx] <- NA
}
```

## fabricatr for hierarchical structure {#fabricatr}

When the real data is nested (students in schools, visits in patients) and the profile records that structure, `fabricatr::add_level` builds the hierarchy declaratively (`synthetic-data-research.md` §1). Use it to generate the level sizes and nest lower-level records within higher-level units, then apply the marginal/relationship draws above within levels. fabricatr honors marginals, categorical proportions, nested structure, and pairwise rank correlation, but has no full-matrix copula solve — so for multi-way numeric correlation, generate numerics with simstudy and attach them to the fabricatr scaffold.

## Seeding and output {#seeding-output}

- **Always** `set.seed()` at the top with a recorded integer seed. The seed goes into the generation log so the synthetic data is exactly reproducible.
- Write parquet to the project's `data/synthetic/` directory (create on first use), named per DAAF conventions (`{date}_{description}_synthetic.parquet`).
- Write a generation log recording: source report path + `report_version`, seed, tier, library versions, and the synthetic-vs-profile validation results.

```r
# --- Save ---
dir.create("data/synthetic", showWarnings = FALSE, recursive = TRUE)
write_parquet(syn, "data/synthetic/2026-07-15_clients_synthetic.parquet")
cat("Seed:", 20260715L, "| rows:", nrow(syn), "| tier:", report$settings$tier, "\n")
```

## Caveats {#caveats}

- **simstudy recovers Poisson correlation more faithfully than binary** (`synthetic-data-research.md` §1) — for binary/low-cardinality columns, expect the achieved correlation to fall somewhat short of the target; validate and report the gap rather than forcing it.
- **A correlation matrix from a suppressed profile may not be positive semidefinite** (rounding, partial columns). Project to the nearest PD matrix (`Matrix::nearPD`) before the copula draw, and note that this slightly perturbs the target correlations — the validation tolerance in `validation-checks.md` accounts for it.
- **Do not fabricate withheld structure.** If the profile suppressed something, the synthetic data should reflect that absence (e.g., `__OTHER__` stays a bucket), not invent plausible-looking detail. Fabricated structure is worse than absent structure because it looks trustworthy.
