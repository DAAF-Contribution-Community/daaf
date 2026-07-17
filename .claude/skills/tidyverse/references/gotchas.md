# Gotchas: Common Pitfalls and Debugging

This reference covers the most common mistakes, confusing behaviors, and debugging
strategies when working with tidyverse packages.

---

## 1. Non-Standard Evaluation (NSE) and Data Masking

dplyr uses **data masking** -- you can refer to column names as if they were
variables. This is convenient but creates confusion when mixing column names with
external variables.

### The Problem

```r
# This works -- "state" refers to the column
df |> filter(state == "CA")

# But what if you have a variable called "state"?
my_state <- "CA"
df |> filter(state == my_state)   # Works! R resolves my_state from environment

# Ambiguity: what if both exist?
state <- "CA"
df |> filter(state == state)      # Compares column to itself! Always TRUE
```

### The Solution: .data and .env Pronouns

```r
# Explicitly reference the data frame column
df |> filter(.data$state == "CA")

# Explicitly reference an environment variable
my_val <- "CA"
df |> filter(.data$state == .env$my_val)
```

### When Writing Reusable Code

If you need to pass column names as variables (rare in DAAF sequential scripts,
but occurs in purrr workflows):

```r
# Using {{ }} (embrace) for function arguments
my_filter <- \(data, col, val) {
  data |> filter({{ col }} == val)
}
my_filter(df, state, "CA")

# Using .data[[ ]] for string column names
col_name <- "state"
df |> filter(.data[[col_name]] == "CA")
df |> mutate("{col_name}_upper" := toupper(.data[[col_name]]))
```

---

## 2. group_by() Persistence

### The Problem

`group_by()` is sticky -- grouping persists through subsequent operations until
explicitly removed. This causes unexpected behavior:

```r
# Grouped summarize returns a STILL-GROUPED tibble (by default)
result <- df |>
  group_by(state, year) |>
  summarize(total = sum(enrollment))
# Warning: `summarise()` has grouped output by 'state'. Override with `.groups`.
# result is still grouped by state!

# Next operation silently operates within groups
result |> mutate(pct = total / sum(total))
# This computes pct within each STATE, not overall!
```

### The Solution

Always ungroup explicitly or use `.groups`:

```r
# Option 1: .groups = "drop" (preferred)
df |>
  group_by(state, year) |>
  summarize(total = sum(enrollment), .groups = "drop")

# Option 2: explicit ungroup()
df |>
  group_by(state, year) |>
  summarize(total = sum(enrollment)) |>
  ungroup()

# Option 3: use .by instead of group_by (dplyr 1.1+, auto-ungroups)
df |>
  summarize(total = sum(enrollment), .by = c(state, year))
```

**DAAF recommendation:** Use `.by` when possible (dplyr 1.1+). It avoids the
grouping persistence issue entirely.

---

## 3. across() Patterns and Pitfalls

### Passing Extra Arguments: Use a Lambda

Only the dots-forwarding form is deprecated (dplyr 1.1.0). Plain functions and
named function lists remain fully supported -- but they give you no way to pass
`na.rm = TRUE`, so in practice you usually want a lambda:

```r
# DEPRECATED (dplyr 1.1+): forwarding extra args through ...
df |> summarize(across(where(is.numeric), mean, na.rm = TRUE))
# Warning: The `...` argument of `across()` is deprecated as of dplyr 1.1.0.

# CORRECT: use a lambda to pass na.rm
df |> summarize(across(where(is.numeric), \(x) mean(x, na.rm = TRUE)))

# STILL FINE: plain function with no extra args (but NAs propagate)
df |> summarize(across(where(is.numeric), mean))

# STILL FINE: named function list -- use lambdas when you need na.rm
df |> mutate(across(c(a, b), list(
  mean = \(x) mean(x, na.rm = TRUE),
  sd = \(x) sd(x, na.rm = TRUE)
)))
```

### across() Does Not Work Everywhere

```r
# Works in mutate, summarize, filter
df |> mutate(across(where(is.numeric), \(x) round(x, 2)))

# Does NOT work in select (use tidyselect instead)
df |> select(where(is.numeric))   # correct
# df |> select(across(...))        # wrong
```

### pick() vs across() (dplyr 1.1+)

```r
# across() applies a function to each column
df |> mutate(across(c(a, b), \(x) x * 2))

# pick() selects columns without applying a function (for use inside functions)
df |> mutate(row_mean = rowMeans(pick(where(is.numeric))))
```

---

## 4. Tidyselect Helpers in Wrong Context

### The Problem

Tidyselect helpers (`starts_with()`, `where()`, etc.) work in `select()`,
`across()`, `pivot_longer()`, but NOT in other dplyr verbs directly:

```r
# Correct: inside select()
df |> select(starts_with("enroll"))

# Correct: inside across()
df |> mutate(across(starts_with("enroll"), as.numeric))

# WRONG: directly in filter
# df |> filter(starts_with("enroll") > 0)   # Error!
```

---

## 5. na.rm = TRUE

### The Problem

Most R aggregation functions return NA if any input is NA (by default):

```r
mean(c(1, 2, NA))    # NA
sum(c(1, 2, NA))     # NA
```

### The Solution

Always include `na.rm = TRUE` in aggregation:

```r
df |> summarize(
  avg = mean(enrollment, na.rm = TRUE),
  total = sum(enrollment, na.rm = TRUE),
  med = median(enrollment, na.rm = TRUE)
)
```

This is such a common source of bugs that DAAF recommends adding `na.rm = TRUE` to
every numeric aggregation unless NA propagation is specifically desired.

---

## 6. Type Coercion Surprises

### if_else() is Type-Safe, ifelse() is Not

Since dplyr 1.1.0, `if_else()` casts `true` and `false` to their common type
(vctrs rules), so integer/double mixes work -- but genuinely incompatible types
still error:

```r
# Compatible types are cast to the common type
if_else(TRUE, 1L, 2.0)   # Returns 1 (double -- integer and double share a common type)

# Incompatible types still error (this is the safety net)
if_else(TRUE, 1L, "a")
# Error: Can't combine `true` <integer> and `false` <character>.

# ifelse is loose (may coerce unexpectedly)
ifelse(TRUE, 1L, 2.0)    # Returns 1 (numeric, not integer)
```

**DAAF recommendation:** Use `if_else()` (dplyr) -- the common-type check
catches bugs like mixing labels and numbers. If you need mixed types,
explicitly cast first.

### case_when() Type Matching

```r
# All branches must return the same type
df |> mutate(
  label = case_when(
    x > 100 ~ "high",
    x > 50  ~ "medium",
    TRUE    ~ "low"         # All character -- good
  )
)

# WRONG: mixing types
df |> mutate(
  result = case_when(
    x > 100 ~ "high",
    x > 50  ~ 50,           # Error: can't mix character and numeric
    TRUE    ~ "low"
  )
)
```

---

## 7. Join Pitfalls

### Unexpected Row Multiplication

Joins can silently multiply rows if the join key is not unique in the "one" side:

```r
# If districts has duplicate leaid values, this silently multiplies rows
schools |> left_join(districts, by = "leaid")

# Guard against this:
schools |> left_join(districts, by = "leaid", relationship = "many-to-one")
# Throws error if districts has duplicate leaid
```

### Column Name Conflicts

```r
# Both data frames have a "name" column
df1 |> left_join(df2, by = "id")
# Result has name.x and name.y -- easy to miss

# Solution: select only needed columns before joining
df1 |> left_join(df2 |> select(id, district_name), by = "id")
```

### NA Keys Match Each Other by Default

Unlike SQL, dplyr's default (`na_matches = "na"`) treats two NA keys as equal --
an NA key in `df` matches an NA key in `ref`:

```r
# Default: NA matches NA
df |> anti_join(ref, by = "key")
# NA-key rows appear in the result ONLY if ref has no NA keys

# For SQL semantics (NA never matches anything), use na_matches = "never"
df |> anti_join(ref, by = "key", na_matches = "never")
# Now rows where key is NA are always "unmatched"
```

---

## 8. Pipe Operator Gotchas

### Native Pipe |> vs Magrittr %>%

```r
# Native pipe: passes as FIRST argument only
df |> filter(x > 5)        # Works: filter(df, x > 5)
df |> lm(y ~ x, data = _)  # Works in R 4.2+: _ is the placeholder

# Magrittr pipe: has . placeholder for any position
df %>% filter(x > 5)       # Works
df %>% lm(y ~ x, data = .) # Works: . can go anywhere
```

DAAF uses `|>` exclusively. For functions where the data is not the first argument,
use a lambda:

```r
# Instead of: df %>% lm(y ~ x, data = .)
df |> (\(d) lm(y ~ x, data = d))()

# Or in R 4.2+:
df |> lm(y ~ x, data = _)
```

### Debugging Pipe Chains

When a pipeline produces unexpected results, break it apart:

```r
# Instead of debugging the whole chain:
result <- df |> filter(x > 5) |> mutate(y = x * 2) |> summarize(m = mean(y))

# Add intermediate checks:
step1 <- df |> filter(x > 5)
cat("After filter:", nrow(step1), "\n")

step2 <- step1 |> mutate(y = x * 2)
cat("After mutate:", nrow(step2), "range(y):", range(step2$y), "\n")

result <- step2 |> summarize(m = mean(y))
```

---

## 9. pivot_longer/pivot_wider Gotchas

### pivot_wider with Duplicate Rows

```r
# If there are duplicate combinations of id_cols + names_from, pivot_wider warns
df |> pivot_wider(names_from = year, values_from = enrollment)
# Warning: Values are not uniquely identified; output will contain list-cols.

# Solution: aggregate first or specify values_fn
df |> pivot_wider(names_from = year, values_from = enrollment, values_fn = sum)
```

### pivot_longer Column Type Mismatch

```r
# If pivoted columns have different types, you get an error
# Columns: enrollment_2020 (integer), enrollment_2021 (character)
df |> pivot_longer(starts_with("enrollment_"))
# Error: can't combine integer and character

# Solution: coerce first
df |> mutate(across(starts_with("enrollment_"), as.numeric)) |>
  pivot_longer(starts_with("enrollment_"))
```

---

## 10. Factor Gotchas

### Numeric-Looking Factors

```r
# Factor levels that look like numbers (levels sort as text: "1", "10", "2")
x <- factor(c("10", "2", "1"))
as.numeric(x)    # Returns 2, 3, 1 (internal codes, NOT the values!)

# Correct: convert to character first
as.numeric(as.character(x))    # Returns 10, 2, 1
```

### Dropping Factor Levels After Filter

```r
# Filtering does not remove unused levels
df_filtered <- df |> filter(state %in% c("CA", "TX"))
levels(df_filtered$state)   # Still has ALL original state levels

# Remove unused levels
df_filtered |> mutate(state = fct_drop(state))
# Or
df_filtered |> mutate(state = droplevels(state))
```

---

## readr 2.2.0: Inline Data Requires `I()`

```r
# WRONG — warns in readr 2.2.0+
df <- read_csv("x,y\n1,2\n3,4")

# RIGHT — wrap literal CSV strings with I()
df <- read_csv(I("x,y\n1,2\n3,4"))
```

This only affects inline string data. File paths (`read_csv("data.csv")`) are unaffected.

---

## Debugging Checklist

When something goes wrong in a tidyverse pipeline:

1. **Check dimensions:** `nrow()`, `ncol()` at each step
2. **Check types:** `glimpse()` or `str()` to see column types
3. **Check NAs:** `colSums(is.na(df))` for NA counts per column
4. **Check groups:** `group_vars(df)` to see if data is still grouped
5. **Check duplicates:** `df |> count(key_col) |> filter(n > 1)` for duplicate keys
6. **Break the pipe:** Assign intermediate results and inspect each step
7. **Read the warning:** dplyr warnings (especially about `.groups`) are informative
