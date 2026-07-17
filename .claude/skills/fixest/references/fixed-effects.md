# Fixed Effects Specification

## Contents

- [Multi-Way Fixed Effects](#multi-way-fixed-effects)
- [FE Interactions](#fe-interactions)
- [Varying Slopes](#varying-slopes)
- [Extracting Fixed Effects](#extracting-fixed-effects)
- [Singleton Removal](#singleton-removal)
- [When to Use Fixed Effects](#when-to-use-fixed-effects)

## Multi-Way Fixed Effects

### Syntax

```r
library(fixest)

# One-way FE
fit <- feols(y ~ x1 | entity, data = df)

# Two-way FE (entity + time)
fit <- feols(y ~ x1 | entity + year, data = df)

# Three-way FE
fit <- feols(y ~ x1 | entity + year + industry, data = df)
```

Each FE dimension listed after `|` with `+` is absorbed via iterative demeaning
(alternating projections). This is fast and memory-efficient — it avoids creating
dummy variable matrices.

### How FE Demeaning Works

fixest uses the Frisch-Waugh-Lovell theorem with a C++ implementation of
alternating projections. For one-way FE, this is exact demeaning (group means).
For multi-way FE, the algorithm iterates until convergence.

Key parameters:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `fixef.tol` | `1e-06` | Convergence tolerance for demeaning |
| `nthreads` | Auto-detected | Number of threads for parallel computation |
| `fixef.rm` | `"perfect_fit"` | Remove singleton/perfect-fit FE groups; tokens: `"perfect_fit"`, `"singletons"`, `"infinite_coef"`, `"none"` (since v0.13) |
| `lean` | `FALSE` | If TRUE, stores less data (saves memory) |

```r
# Increase precision for very large models
fit <- feols(y ~ x1 | entity + year, data = df, fixef.tol = 1e-10)

# Use multiple threads explicitly
setFixest_nthreads(4)
```

## FE Interactions

### The `^` Operator

The `^` operator creates interacted fixed effects (all combinations of two or
more FE dimensions):

```r
# Entity-by-year FE (one intercept per entity-year combination)
fit <- feols(y ~ x1 | entity^year, data = df)

# Three-way interaction
fit <- feols(y ~ x1 | entity^year^industry, data = df)
```

`entity^year` absorbs N_entity * N_year intercepts (one per unique entity-year
pair). This is much more flexible than `entity + year` (which absorbs only
N_entity + N_year intercepts) but consumes more degrees of freedom.

### When to Use Interacted FE

| Specification | Controls For | Use When |
|---------------|-------------|----------|
| `entity + year` | Time-invariant entity effects + common time shocks | Standard panel |
| `entity^year` | Entity-specific time trends | Testing robustness; very flexible controls |
| `entity + year + industry` | Three separate additive dimensions | Multiple grouping structures |
| `entity^industry + year` | Entity-industry-specific intercepts + time shocks | Differentiated panels |

Interacted FE can absorb a lot of variation. Be cautious about:
- Degrees of freedom: many FE levels relative to observations
- Identification: your regressors need within-group variation after demeaning
- Collinearity: if a regressor is collinear with the FE, fixest will report it

## Varying Slopes

The `[var]` notation after a FE name allows entity-specific slopes on a
continuous variable:

```r
# Entity-specific slopes on x1 (absorbed, not estimated as coefficients)
fit <- feols(y ~ x2 | entity[x1], data = df)

# Entity-specific intercepts AND slopes on x1
fit <- feols(y ~ x2 | entity + entity[x1], data = df)

# Multiple varying slopes
fit <- feols(y ~ x3 | entity[x1] + entity[x2], data = df)
```

Varying slopes `entity[x1]` absorbs entity-specific linear effects of `x1`.
This is equivalent to including `entity:x1` interactions as fixed effects rather
than estimating them as coefficients. The absorbed slopes can be recovered via
`fixef()`.

### When to Use Varying Slopes

- Entity-specific time trends: `entity[year]` absorbs linear entity-specific
  trends — useful as a robustness check in DiD to relax parallel trends
- Heterogeneous responses: `entity[x1]` when you want to control for
  entity-specific responses to `x1` rather than estimate them

## Extracting Fixed Effects

The `fixef()` function recovers the absorbed FE estimates:

```r
fit <- feols(y ~ x1 | entity + year, data = df)

# Extract fixed effects
fe <- fixef(fit)

# fe is a list with one element per FE dimension
names(fe)          # c("entity", "year")
fe$entity          # Named vector: entity FE estimates
fe$year            # Named vector: year FE estimates

# Convert to data.frame for merging
entity_fe <- data.frame(
  entity = names(fe$entity),
  fe_entity = as.numeric(fe$entity)
)
```

### Recovery Precision

FE recovery uses the algorithm from Berge (2018). For two-way FE, the recovered
values are identified only up to a normalization (one FE group is set to zero as
the reference). The `summary()` of `fixef()` shows convergence diagnostics:

```r
summary(fixef(fit))
```

### Plot Fixed Effects

```r
# Quick visualization of FE distribution
plot(fixef(fit))
```

## Singleton Removal

### What Are Singletons?

Singleton fixed effects are FE groups with exactly one observation. Since the FE
intercept perfectly fits that observation's residual, singletons contribute nothing
to parameter estimation while consuming a degree of freedom.

### Default Behavior (v0.14.0)

Since fixest 0.13, singletons are dropped by default:

```r
# Default: singletons removed
fit <- feols(y ~ x1 | entity, data = df)
# You will see: "X singleton observations removed" in output

# To keep singletons (not recommended, but possible)
fit <- feols(y ~ x1 | entity, data = df, fixef.rm = "none")
```

### Why Singletons Matter

Keeping singletons:
- Inflates R-squared (FE perfectly fits those observations)
- Can bias standard errors (spurious degrees of freedom)
- Wastes computation without improving estimation

The default `fixef.rm = "perfect_fit"` is the correct choice for almost all
applications.

### Iterative Removal

Removing singletons in one FE dimension can create new singletons in another.
fixest handles this by iterating until no more singletons remain. The reported
count reflects the total number removed across all iterations.

## When to Use Fixed Effects

Fixed effects are appropriate when:

| FE Type | Controls For | Example |
|---------|-------------|---------|
| Entity FE | Time-invariant unobserved heterogeneity | State culture, firm management quality |
| Time FE | Common shocks affecting all units | Recessions, policy changes, seasonal effects |
| Two-way FE | Both entity-level and time-level unobservables | Standard panel regression |
| Interacted FE | Flexible entity-time patterns | Entity-specific trends as robustness |

### Identification Requirement

After absorbing FE, your regressor of interest must still have variation. If
treatment varies only at the entity level and you include entity FE, treatment
is perfectly absorbed — you need within-entity (over-time) variation for
identification.

```r
# This identifies x1's effect using within-entity variation over time
fit <- feols(y ~ x1 | entity + year, data = df)

# This CANNOT identify x1 if x1 is constant within entity
# (x1 is collinear with entity FE)
```

fixest reports collinear variables and drops them. If your variable of interest
is dropped, reconsider your FE specification.

For methodology guidance on when FE identification is credible, load the
`data-scientist` skill's causal inference references.

## References

- Berge, L. (2018). "Efficient estimation of maximum likelihood models with
  multiple fixed-effects: the R package FENmlm." CREA Discussion Paper 2018-13.
- Correia, S. (2016). "A Feasible Estimator for Linear Models with Multi-Way
  Fixed Effects." Working Paper.
- fixest documentation — Fixed Effects:
  https://lrberge.github.io/fixest/articles/fixest_walkthrough.html
