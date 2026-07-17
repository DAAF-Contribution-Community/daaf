# Quickstart: Core dplyr Verbs and Pipe Chains

This reference covers the essential dplyr verbs for everyday data manipulation in R.
These are the building blocks of every tidyverse pipeline.

## The Pipe Operator

R 4.1+ provides the native pipe `|>`. DAAF uses `|>` exclusively (not magrittr's `%>%`):

```r
# Each step takes the result of the previous step as its first argument
result <- df |>
  filter(year == 2020) |>
  select(state, enrollment, frl_count) |>
  mutate(frl_rate = frl_count / enrollment) |>
  arrange(desc(frl_rate))
```

The pipe makes code read top-to-bottom like a recipe. Every dplyr verb takes a data
frame as its first argument and returns a data frame, making them naturally pipeable.

---

## filter() -- Subset Rows

Keep rows that match conditions:

```r
# Single condition
df |> filter(year == 2020)

# Multiple conditions (AND -- comma or &)
df |> filter(year == 2020, state == "CA")
df |> filter(year == 2020 & state == "CA")

# OR conditions
df |> filter(year == 2020 | year == 2021)

# Membership
df |> filter(state %in% c("CA", "TX", "NY"))

# Negated membership
df |> filter(!(state %in% c("CA", "TX")))

# NA handling
df |> filter(!is.na(enrollment))
df |> filter(is.na(frl_count))

# Between
df |> filter(between(enrollment, 100, 500))

# String matching (requires stringr)
df |> filter(str_detect(school_name, "Elementary"))
```

**Common patterns in DAAF pipelines:**

```r
# INTENT: Filter to valid school records for analysis year
# ASSUMES: year column uses academic year start (e.g., 2020 = 2020-21)
df_filtered <- df |>
  filter(
    year == 2020,
    !is.na(enrollment),
    enrollment > 0
  )
cat("Rows after filter:", nrow(df_filtered), "\n")
stopifnot(nrow(df_filtered) > 0)
```

---

## select() -- Choose Columns

Pick, drop, rename, or reorder columns:

```r
# Pick by name
df |> select(state, school_name, enrollment)

# Drop columns
df |> select(-fips, -ncessch_num)

# Range of columns
df |> select(state:enrollment)

# Tidyselect helpers
df |> select(starts_with("enroll"))
df |> select(ends_with("_rate"))
df |> select(contains("poverty"))
df |> select(matches("^pop_\\d{4}$"))

# By type
df |> select(where(is.numeric))
df |> select(where(is.character))

# Select and rename
df |> select(school = school_name, enroll = enrollment)

# Reorder (move columns to front, everything() keeps the rest)
df |> select(state, year, everything())

# Negative selection with helpers
df |> select(-starts_with("flag_"))
```

---

## mutate() -- Create or Modify Columns

Add new columns or transform existing ones:

```r
# Create new column
df |> mutate(frl_rate = frl_count / enrollment)

# Overwrite existing column
df |> mutate(enrollment = as.numeric(enrollment))

# Multiple columns at once
df |> mutate(
  frl_rate = frl_count / enrollment,
  frl_pct = frl_rate * 100
)

# Conditional with if_else (type-safe: casts to common type, errors on incompatible types)
df |> mutate(
  size = if_else(enrollment > 500, "large", "small")
)

# Multiple conditions with case_when
df |> mutate(
  size_cat = case_when(
    enrollment > 1000 ~ "very_large",
    enrollment > 500  ~ "large",
    enrollment > 100  ~ "medium",
    TRUE              ~ "small"
  )
)

# recode_values for direct value mapping (dplyr 1.2+; supersedes case_match,
# which is soft-deprecated as of dplyr 1.2.0)
df |> mutate(
  region = recode_values(
    state,
    c("CA", "OR", "WA") ~ "West",
    c("NY", "NJ", "CT") ~ "Northeast",
    default = "Other"
  )
)

# Type conversion
df |> mutate(
  year = as.integer(year),
  school_name = as.character(school_name)
)

# Across multiple columns
df |> mutate(across(where(is.numeric), \(x) round(x, 2)))
df |> mutate(across(c(col1, col2, col3), \(x) x / 100))
```

**Sequential dependency:** Unlike polars, dplyr's `mutate()` processes columns
sequentially -- a column created earlier in the same `mutate()` call is available
to later expressions:

```r
# This works in dplyr -- rate is available for pct
df |> mutate(
  rate = count / total,
  pct = rate * 100       # uses rate from above
)
```

---

## arrange() -- Sort Rows

```r
# Ascending (default)
df |> arrange(state)

# Descending
df |> arrange(desc(enrollment))

# Multiple sort columns
df |> arrange(state, desc(enrollment))

# NA placement (NAs go last by default in arrange)
df |> arrange(enrollment)
```

---

## group_by() + summarize() -- Aggregate

Compute summary statistics by group:

```r
# Basic grouped summary
df |>
  group_by(state) |>
  summarize(
    avg_enroll = mean(enrollment, na.rm = TRUE),
    total_enroll = sum(enrollment, na.rm = TRUE),
    n_schools = n()
  )

# Multiple grouping columns
df |>
  group_by(state, year) |>
  summarize(
    avg_enroll = mean(enrollment, na.rm = TRUE),
    .groups = "drop"   # drop grouping after summarize
  )

# Inline grouping with .by (dplyr 1.1+, no ungroup needed)
df |>
  summarize(
    avg_enroll = mean(enrollment, na.rm = TRUE),
    n_schools = n(),
    .by = state
  )

df |>
  summarize(
    avg_enroll = mean(enrollment, na.rm = TRUE),
    .by = c(state, year)
  )
```

**Common aggregation functions:**

| Function | Purpose |
|----------|---------|
| `mean(x, na.rm = TRUE)` | Average |
| `median(x, na.rm = TRUE)` | Median |
| `sum(x, na.rm = TRUE)` | Sum |
| `sd(x, na.rm = TRUE)` | Standard deviation |
| `min(x, na.rm = TRUE)` / `max()` | Min / Max |
| `n()` | Count of rows in group |
| `n_distinct(x)` | Count of unique values |
| `first(x)` / `last(x)` | First / last value |
| `quantile(x, 0.25)` | Quantile |

Always include `na.rm = TRUE` for numeric summaries unless you specifically want
NA propagation.

**The `.groups` argument:** `summarize()` warns about grouping behavior by default.
Use `.groups = "drop"` to fully ungroup, `.groups = "drop_last"` to drop the last
grouping level (default), or `.groups = "keep"` to retain all grouping.

---

## rename() -- Rename Columns

```r
# Rename: new_name = old_name
df |> rename(school = school_name, enroll = enrollment)

# Rename with a function
df |> rename_with(toupper)
df |> rename_with(tolower, starts_with("ENROLL"))
df |> rename_with(\(x) paste0("col_", x))
```

---

## distinct() -- Unique Rows

```r
# All unique rows
df |> distinct()

# Unique combinations of specific columns
df |> distinct(state, year)

# Keep all columns (.keep_all)
df |> distinct(state, .keep_all = TRUE)
```

---

## count() and tally() -- Quick Counts

```r
# Count by group
df |> count(state)
df |> count(state, year)

# Sorted count
df |> count(state, sort = TRUE)

# Weighted count
df |> count(state, wt = enrollment)

# Add count as column (don't collapse)
df |> add_count(state, name = "state_n")
```

---

## slice() -- Subset by Position

```r
# First N rows
df |> slice_head(n = 5)

# Last N rows
df |> slice_tail(n = 5)

# Top N by a variable
df |> slice_max(enrollment, n = 10)

# Bottom N by a variable
df |> slice_min(enrollment, n = 10)

# Random sample
df |> slice_sample(n = 100)
df |> slice_sample(prop = 0.1)   # 10% sample

# Grouped slice (top 3 per state)
df |>
  group_by(state) |>
  slice_max(enrollment, n = 3)
```

---

## pull() -- Extract a Column as a Vector

```r
# Extract as vector
df |> pull(state)

# Last column
df |> pull(-1)

# Use in assertions
states <- df |> distinct(state) |> pull(state)
stopifnot(length(states) > 0)
```

---

## across() -- Apply Functions to Multiple Columns

```r
# Summarize all numeric columns (lambda -- passing na.rm through ... is deprecated)
df |> summarize(across(where(is.numeric), \(x) mean(x, na.rm = TRUE)))

# Mutate specific columns
df |> mutate(across(c(col1, col2), \(x) round(x, 2)))

# Multiple functions with naming
df |> summarize(
  across(
    c(enrollment, frl_count),
    list(mean = \(x) mean(x, na.rm = TRUE),
         sd = \(x) sd(x, na.rm = TRUE)),
    .names = "{.col}_{.fn}"
  )
)
# Produces: enrollment_mean, enrollment_sd, frl_count_mean, frl_count_sd
```

---

## Putting It Together: Full DAAF Pipeline Example

```r
# --- Config ---
library(dplyr)
library(arrow)

PROJECT_DIR <- "/daaf/research/2026-01-15_School_Analysis"

# --- Load ---
# INTENT: Load school-level CCD data
df <- read_parquet(file.path(PROJECT_DIR, "data", "2026-01-15_ccd_schools.parquet"))
cat("Loaded:", nrow(df), "rows x", ncol(df), "cols\n")

# --- Transform ---
# INTENT: Calculate state-level enrollment summaries for 2020
# ASSUMES: enrollment column is non-negative; year uses academic year start
result <- df |>
  filter(year == 2020, !is.na(enrollment), enrollment > 0) |>
  group_by(state) |>
  summarize(
    total_enroll = sum(enrollment),
    avg_enroll = mean(enrollment),
    n_schools = n(),
    .groups = "drop"
  ) |>
  mutate(pct_of_total = total_enroll / sum(total_enroll) * 100) |>
  arrange(desc(total_enroll))

# --- Validate ---
stopifnot(nrow(result) > 0)
stopifnot(all(result$total_enroll > 0))
stopifnot(abs(sum(result$pct_of_total) - 100) < 0.01)
cat("States:", nrow(result), "\n")
cat("Total enrollment:", sum(result$total_enroll), "\n")

# --- Save ---
write_parquet(result, file.path(PROJECT_DIR, "data", "2026-01-15_state_enrollment.parquet"))
cat("Saved: state_enrollment.parquet\n")
```
