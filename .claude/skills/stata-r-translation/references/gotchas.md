# Stata-to-R Gotchas and False Friends

Common mistakes Stata users make when writing R, organized from most
dangerous/frequent to least.

---

## False Friends: Syntax

| Stata | R Attempt | Trap | Correct R |
|-------|-----------|------|-----------|
| `.` (missing) | `.` | Not missingness; it is a placeholder or attribute access | `NA` |
| `gen x = expr` | No `gen` function | Stata commands are not R functions | `mutate(x = expr)` |
| `replace x = expr if cond` | No `replace` command | | `mutate(x = if_else(cond, expr, x))` |
| `` `macro' `` | Backtick = non-syntactic name | No macro substitution | `variable_name` or `paste0()` |
| `$global` | `$` = list/data frame extraction | Not macro access | `variable_name` |
| `var == .` | `var == NA` | Always returns `NA`, not `TRUE` | `is.na(var)` |
| `//` (comment) | `//` is not a comment | | `#` for comments |
| `/* comment */` | Works in R too | | `#` preferred in DAAF scripts |
| `_n` | No `_n` | | `row_number()` inside `mutate()` |
| `_N` | No `_N` | | `n()` inside `mutate()` or `summarise()` |
| `L.var` | No lag operator syntax | | `lag(var)` inside grouped `mutate()` |
| `i.var` | No `i.` prefix | | `factor(var)` in formula auto-creates dummies |
| `quietly cmd` | No `quietly` | R is quiet by default | Just run the command |
| `display expr` | No `display` | | `cat(expr, "\n")` |

---

## Data Manipulation Traps

### 1. Forgetting `na.rm = TRUE`

**Severity:** Very high -- silent wrong results.

```r
# WRONG: returns NA if any value is missing
mean(df$income)

# RIGHT: exclude NAs explicitly
mean(df$income, na.rm = TRUE)

# Also applies to: sum(), sd(), min(), max(), median(), var()
```

Stata excludes missing from aggregation by default. R propagates NA by default
in base functions. dplyr's `n()` counts all rows including NA; use
`sum(!is.na(x))` to count non-missing.

### 2. The Missing Value Comparison Trap

**Severity:** Very high -- opposite behavior from Stata.

Stata: `. > 100` is `TRUE` (missing = +infinity).
R: `NA > 100` is `NA` (unknown, excluded by `filter()`).

```r
# R filter automatically excludes NA rows (safe by default)
df |> filter(income > 50000)  # NA rows are dropped

# No need for Stata's defensive: & !missing(income)
```

### 3. Forgetting `ungroup()`

**Severity:** High -- silent wrong results in subsequent operations.

```r
# WRONG: df remains grouped, affecting all subsequent operations
df <- df |> group_by(state) |> mutate(mean_score = mean(score, na.rm = TRUE))

# RIGHT: always ungroup after group_by + mutate
df <- df |> group_by(state) |> mutate(mean_score = mean(score, na.rm = TRUE)) |> ungroup()
```

### 4. `drop if` Negation

```r
# Stata: drop if income < 0
# R equivalent: keep everything NOT matching
df <- df |> filter(!(income < 0))
# Or equivalently:
df <- df |> filter(income >= 0)
```

### 5. No Automatic Merge Diagnostics

Stata creates `_merge`. R joins silently. Always validate:

```r
pre_count <- nrow(df)
df <- df |> left_join(states, by = "state_fips")
cat("Rows before:", pre_count, "after:", nrow(df), "\n")
stopifnot(nrow(df) == pre_count)  # Check for unexpected row multiplication
```

### 6. `rowSums` vs Stata `rowtotal` NA Behavior

Stata `rowtotal` treats missing as 0. R `rowSums` returns NA if any input is NA
unless `na.rm = TRUE`.

```r
# Match Stata rowtotal behavior
df <- df |> mutate(total = rowSums(pick(x1, x2, x3), na.rm = TRUE))
```

### 7. Assignment: `<-` vs `=`

Both work for assignment in R, but `<-` is conventional. Stata users may
instinctively use `=`, which works but may confuse experienced R readers.

```r
df <- df |> mutate(x = 1)   # = inside function arguments
df <- df |> filter(x == 1)  # == for comparison (same as Stata)
```

---

## Modeling Traps

### 1. Robust SEs Require Extra Steps (Without fixest)

```r
# Base R lm() -- no built-in robust SEs
fit <- lm(y ~ x1 + x2, data = df)

# Must use sandwich + lmtest for robust SEs
library(sandwich)
library(lmtest)
coeftest(fit, vcov = vcovHC(fit, type = "HC1"))  # Stata "robust"

# fixest handles this naturally (recommended)
fit <- feols(y ~ x1 + x2, data = df, vcov = "hetero")
```

### 2. Factor Reference Level

Stata: first numeric code is reference. R: first alphabetical level is reference.

```r
# Control reference level explicitly
df <- df |> mutate(region = relevel(factor(region), ref = "Northeast"))
```

### 3. `library()` Load Order Matters

If two packages export the same function name, the last-loaded wins. Common
conflict: `dplyr::filter()` vs `stats::filter()`.

```r
library(dplyr)  # Load last so dplyr::filter() wins
# Or be explicit:
df <- dplyr::filter(df, x > 0)
```

---

## Environment Traps

### 1. 1-Based Indexing (Less Friction Than Python)

Both Stata and R use 1-based indexing. This is an area of reduced friction:

```r
x[1]           # First element (same as Stata var[1])
1:10           # 1 through 10 inclusive (same as Stata forvalues i = 1/10)
```

### 2. `cat()` vs `print()` for Script Output

`cat()` is like Stata's `display` -- outputs text without formatting.
`print()` adds formatting (quotes around strings, row numbers for data frames).
In DAAF scripts, use `cat()` for clean output.

### 3. No Persistent State Across Scripts

Each R script runs in a fresh process. Data passes via parquet files, not
in-memory objects.

---

## Error Message Translation

| Stata Error | R Equivalent | Meaning |
|-------------|-------------|---------|
| `variable x not found` | `object 'x' not found` | Variable/column doesn't exist |
| `type mismatch` | `non-numeric argument to binary operator` | Wrong type |
| `no observations` | Data frame with 0 rows | Filter removed everything |
| `r(601) - file not found` | `cannot open file` | Path is wrong |
| `merge: key not unique` | Unexpected row multiplication after join | Non-unique keys |
| `command unrecognized` | `could not find function` | Package not loaded |
| `last estimates not found` | Object not found | Model not saved to variable |

---

## Quick Diagnostic Table

| Problem | Quick Fix |
|---------|-----------|
| Aggregation returns NA | Add `na.rm = TRUE` |
| `NA > 100` gives NA | R excludes NA from `filter()` automatically |
| Grouped operations affect later code | Add `ungroup()` |
| Robust SEs not available | Use `fixest::feols()` with `vcov = "hetero"` |
| Factor levels in wrong order | `fct_relevel()` or `relevel()` |
| `drop if` keeps wrong rows | Remember: `drop if cond` = `filter(!cond)` |
| Merge produced extra rows | Check for duplicate keys; validate row counts |
| `rowSums` gives NA | Add `na.rm = TRUE` |
| Script produces no output | Use explicit `cat()` or `print()` |
| Package function not found | Add `library(pkg)` at top of script |
