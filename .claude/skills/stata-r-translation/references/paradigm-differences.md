# Paradigm Differences: Stata vs R for Quantitative Social Science

This reference documents the fundamental language and paradigm differences between
Stata and R (tidyverse) as they affect quantitative social science data analysis.
It is the foundational reference that other translation files build upon.

> **Versions referenced:**
> R: R 4.5.3, dplyr 1.2.0, tidyr 1.3.2
> Stata: Stata 18
> See SKILL.md -- Library Versions for the complete version table.

---

## The Single-Dataset Model

Stata's architecture is built around a single dataset in memory. Every command
operates on "the dataset" implicitly.

### Stata: Implicit Single Dataset

```stata
use "schools.dta", clear
keep if enrollment > 500
gen log_enroll = log(enrollment)
summarize log_enroll
regress test_score log_enroll poverty_rate
```

### R: Explicit Multi-Object Workspace

```r
schools <- arrow::read_parquet("schools.parquet")
districts <- arrow::read_parquet("districts.parquet")
ca_schools <- schools |> filter(state == "CA")
merged <- schools |> left_join(districts, by = "district_id")
# 'schools' is never modified
```

### Key Mental Model Shift

| Stata Mental Model | R Mental Model |
|--------------------|----------------|
| "The dataset" (singular, implicit) | "This data frame" (explicit, one of many) |
| Commands modify the dataset in place | Operations return new objects (copy-on-modify) |
| `merge` and `append` build up *the* dataset | Multiple data frames coexist; join when needed |
| `preserve`/`restore` for temporary modifications | Just assign to a new variable |
| Column = "variable" (bare name) | Column = bare name inside dplyr verbs (tidy evaluation) |

---

## Missing Values

### Stata: Missing = Positive Infinity

Stata supports 27 distinct missing values: `.` and `.a` through `.z`. Missing
sorts as **greater than all numeric values**: `. > 100` is `TRUE`.

```stata
* DANGEROUS: this includes missing values!
count if income > 50000

* CORRECT: explicitly exclude missing
count if income > 50000 & !missing(income)
```

### R: NA Propagates

R has typed NA values (`NA_real_`, `NA_integer_`, `NA_character_`), but in
practice all behave as a single `NA` concept. The key difference from Stata:
comparisons with `NA` return `NA`, not `TRUE` or `FALSE`.

```r
NA > 100     # NA (not TRUE like Stata's .)
NA == NA     # NA (not TRUE)
is.na(NA)    # TRUE (the proper test)

# R filter behavior -- NA rows are EXCLUDED by default
df |> filter(income > 50000)
# Rows where income is NA are dropped (safe by default)
```

### Common Translation Patterns

| Stata | R |
|-------|---|
| `missing(var)` | `is.na(var)` |
| `!missing(var)` | `!is.na(var)` |
| `var == .` | `is.na(var)` (never `== NA`) |
| `replace var = 0 if missing(var)` | `mutate(var = replace_na(var, 0))` or `mutate(var = coalesce(var, 0))` |
| `drop if missing(var)` | `filter(!is.na(var))` or `drop_na(var)` |
| `mvdecode var, mv(-9 -99)` | `mutate(var = na_if(var, -9))` (one value) or `mutate(var = if_else(var %in% c(-9, -99), NA, var))` |
| `count if income > 50000` (includes missing) | `sum(income > 50000, na.rm = TRUE)` (excludes NA -- safe) |

### Key Behavioral Differences

- Stata: `mean income` silently ignores missing. R: `mean(income)` returns `NA`
  unless `na.rm = TRUE` is specified.
- Stata: aggregation functions exclude missing by default. R: many base R
  functions propagate NA by default (must use `na.rm = TRUE`). dplyr
  functions like `n()` count NAs; `sum(!is.na(x))` counts non-missing.
- R has no extended missing values (`.a` through `.z`). Use a separate column
  to encode missingness reasons.

---

## Value Labels vs Factors

### Stata: Three-Layer Label System

Stata stores integers and displays text via value labels:

```stata
label define race_lbl 1 "White" 2 "Black" 3 "Hispanic" 4 "Asian"
label values race race_lbl
tabulate race   * Shows "White", "Black", etc.
regress y race  * Uses integers 1-4
```

### R: Factors

R's `factor()` type combines storage and display in one mechanism:

```r
df <- df |> mutate(
  race = factor(race, levels = c(1, 2, 3, 4),
                labels = c("White", "Black", "Hispanic", "Asian"))
)
table(df$race)  # Shows "White", "Black", etc.
# In regression, factors auto-create dummies (reference = first level)
lm(y ~ race, data = df)
```

| Stata | R |
|-------|---|
| `label define lbl 1 "A" 2 "B"` then `label values var lbl` | `factor(var, levels = c(1,2), labels = c("A","B"))` |
| `encode strvar, gen(numvar)` | `as.numeric(factor(strvar))` |
| `decode numvar, gen(strvar)` | `as.character(numvar)` (if already a factor) |
| `label variable var "description"` | No built-in equivalent; use comments or metadata |
| Integer storage + text display (automatic) | Factor stores text; `as.numeric()` extracts codes |
| `i.region` in regression auto-creates dummies | Factors auto-create dummies in formulas |
| `ib2.region` (base category = 2) | `relevel(region, ref = "South")` |

R's factor system is actually closer to Stata's value labels than Python's approach,
making this a relatively smooth transition.

---

## The by: Prefix and System Variables

### Stata: by:, _n, _N

```stata
bysort state: gen state_n = _N
bysort state: gen state_obs = _n
bysort state: egen mean_score = mean(test_score)
bysort state (year): gen prev_score = test_score[_n-1]
```

### R: group_by + mutate / summarise

R separates into two patterns just like Python, but the syntax is more natural:

**Window functions (preserves rows -- like `egen` with `by:`):**

```r
df <- df |>
  group_by(state) |>
  mutate(
    state_n = n(),                      # _N
    state_obs = row_number(),           # _n (1-based, like Stata)
    mean_score = mean(test_score, na.rm = TRUE)
  ) |>
  ungroup()
```

**Aggregation (reduces rows -- like `collapse`):**

```r
state_stats <- df |>
  group_by(state) |>
  summarise(
    mean_score = mean(test_score, na.rm = TRUE),
    total_enroll = sum(enrollment, na.rm = TRUE),
    n = n()
  )
```

**Lag/lead within groups:**

```r
df <- df |>
  arrange(state, year) |>
  group_by(state) |>
  mutate(
    prev_score = lag(test_score),
    lead_score = lead(test_score)
  ) |>
  ungroup()
```

### Key Mental Model Shift

| Stata | R |
|-------|---|
| `bysort g: egen x = mean(y)` | `group_by(g) \|> mutate(x = mean(y, na.rm = TRUE)) \|> ungroup()` |
| `bysort g: gen obs = _n` | `group_by(g) \|> mutate(obs = row_number()) \|> ungroup()` |
| `bysort g: gen n = _N` | `group_by(g) \|> mutate(n = n()) \|> ungroup()` |
| `bysort g (t): gen lag_y = y[_n-1]` | `arrange(g, t) \|> group_by(g) \|> mutate(lag_y = lag(y)) \|> ungroup()` |
| `collapse (mean) y, by(g)` | `group_by(g) \|> summarise(y = mean(y, na.rm = TRUE))` |

**Important:** Always `ungroup()` after `group_by() |> mutate()`. Forgetting to
ungroup causes subtle bugs in subsequent operations.

---

## In-Place Modification vs Copy-on-Modify

Stata modifies data in place. R returns new objects (copy-on-modify semantics).

```stata
* Stata: modifies in place
drop if missing(income)
gen log_income = log(income)
replace income = income / 1000
```

```r
# R: reassign to save changes
df <- df |> filter(!is.na(income))
df <- df |> mutate(log_income = log(income))
df <- df |> mutate(income = income / 1000)
```

Every dplyr verb returns a new data frame. The original is unchanged unless you
reassign (`df <- df |> ...`). This is similar to polars in Python but contrasts
with Stata's in-place model.

---

## The Macro System vs R Variables

### Stata: Text Substitution

```stata
local controls "education experience age"
local outcome "wage"
regress `outcome' `controls', robust
```

### R: Variables and Formulas

```r
controls <- c("education", "experience", "age")
outcome <- "wage"
formula <- as.formula(paste(outcome, "~", paste(controls, collapse = " + ")))
lm(formula, data = df)

# Or more directly with fixest:
feols(wage ~ education + experience + age, data = df, vcov = "hetero")
```

| Stata Macros | R Variables |
|--------------|-------------|
| Text substitution (evaluated at parse time) | Value binding (evaluated at runtime) |
| `` `localname' `` (backtick-apostrophe) | `variable_name` (bare name) |
| `$globalname` (dollar sign) | `variable_name` (no scope distinction in syntax) |
| `local x "a b c"` stores a string | `x <- c("a", "b", "c")` stores a vector |

---

## Estimation and Post-Estimation

### Stata: Global Return Values

```stata
regress wage education experience, robust
display e(r2)
display _b[education]
```

### R: Persistent Model Objects

```r
fit <- feols(wage ~ education + experience, data = df, vcov = "hetero")
summary(fit)
coef(fit)["education"]
```

| Stata | R |
|-------|---|
| One active estimation result at a time (`e()`) | Multiple model objects coexist as variables |
| `_b[varname]` | `coef(fit)["varname"]` |
| `_se[varname]` | `se(fit)["varname"]` (fixest) |
| `e(r2)` | `r2(fit)` (fixest) or `summary(fit)$r.squared` |
| `e(N)` | `nobs(fit)` |
| `estimates store m1` | `m1 <- feols(...)` (already stored) |
| `esttab m1 m2` | `etable(m1, m2)` |

---

## Panel Data Operators

### Stata: Declare Once, Use Everywhere

```stata
xtset state_id year
gen lag_score = L.test_score
gen lead_score = F.test_score
gen diff_score = D.test_score
```

### R: Explicit Every Time

```r
df <- df |>
  arrange(state_id, year) |>
  group_by(state_id) |>
  mutate(
    lag_score = lag(test_score),
    lead_score = lead(test_score),
    diff_score = test_score - lag(test_score)
  ) |>
  ungroup()
```

| Stata | R |
|-------|---|
| `xtset entity time` | No equivalent; structure is implicit |
| `L.var` | `lag(var)` inside `group_by(entity) \|> mutate()` |
| `F.var` | `lead(var)` inside `group_by(entity) \|> mutate()` |
| `D.var` | `var - lag(var)` inside `group_by(entity) \|> mutate()` |

---

## Package and Namespace Model

### Stata: Flat Namespace

```stata
ssc install reghdfe
reghdfe y x1 x2, absorb(fe1 fe2) cluster(cl1)
```

Once installed, commands are immediately available with no import.

### R: library() Required

```r
library(fixest)
library(dplyr)

df <- df |> filter(x > 5)         # dplyr verb
fit <- feols(y ~ x | fe, data = df)  # fixest function
```

After `library()`, functions are available by bare name (unlike Python where
prefixes are always needed). Name conflicts are resolved by load order (last
loaded wins), which can cause subtle bugs.

| Stata | R |
|-------|---|
| `ssc install reghdfe` | `install.packages("fixest")` |
| Use immediately after install | `library(fixest)` required at script top |
| No prefix needed | No prefix after `library()` (unlike Python) |
| `which reghdfe` | `packageVersion("fixest")` |

---

## Indexing: Both 1-Based

This is an area of reduced friction compared to Python. Both Stata and R use
1-based indexing:

| Concept | Stata | R |
|---------|-------|---|
| First element | `var[1]` | `x[1]` |
| Row number in group | `_n` (starts at 1) | `row_number()` (starts at 1) |
| Range | `in 1/10` | `1:10` |

This means lag/lead semantics are also consistent: `lag(x, 1)` in R shifts by
one position, just like `x[_n-1]` in Stata.

> **Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com, accessed
> 2026-03-28); Turrell, "Coming from Stata" in *Coding for Economists*
> (aeturrell.github.io, accessed 2026-03-28); Wickham & Grolemund, *R for Data
> Science* 2e (r4ds.hadley.nz, accessed 2026-05-13); R documentation (r-project.org)
