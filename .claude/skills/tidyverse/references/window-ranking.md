# Window Functions and Ranking

This reference covers window operations that compute values across rows within
groups without collapsing the data: ranking, lag/lead, cumulative operations,
and rolling aggregations.

---

## Grouped Mutate vs Grouped Summarize

Window functions operate inside `group_by() |> mutate()` (or `.by` in mutate).
They produce one value per row, unlike `summarize()` which collapses to one row
per group:

```r
# summarize: one row per group
df |> group_by(state) |> summarize(avg = mean(enrollment))

# mutate with window: one value per row, preserving all rows
df |> group_by(state) |> mutate(state_avg = mean(enrollment))
# Or with .by:
df |> mutate(state_avg = mean(enrollment), .by = state)
```

---

## Ranking Functions

### row_number() -- Sequential Row Numbers

```r
# Row number within groups (no ties handling -- breaks ties by position)
df |>
  group_by(state) |>
  mutate(rank = row_number()) |>
  ungroup()

# Row number by a specific ordering
df |>
  group_by(state) |>
  mutate(rank = row_number(desc(enrollment))) |>
  ungroup()
```

### min_rank() -- Minimum Rank (Ties Get Same Rank, Gaps After)

```r
# Ties get the same (minimum) rank; gaps appear after ties
# Values: 100, 100, 80 -> ranks: 1, 1, 3 (gap at 2)
df |> mutate(rank = min_rank(desc(enrollment)), .by = state)
```

### dense_rank() -- Dense Rank (No Gaps After Ties)

```r
# Ties get the same rank; no gaps
# Values: 100, 100, 80 -> ranks: 1, 1, 2 (no gap)
df |> mutate(rank = dense_rank(desc(enrollment)), .by = state)
```

### percent_rank() -- Percentile Rank (0 to 1)

```r
# Rescaled to [0, 1]
df |> mutate(pct_rank = percent_rank(enrollment), .by = state)
```

### cume_dist() -- Cumulative Distribution (Proportion <= Value)

```r
# Proportion of values <= current value
df |> mutate(cume = cume_dist(enrollment), .by = state)
```

### ntile() -- Equal-Sized Bins

```r
# Divide into N roughly equal groups
df |> mutate(quartile = ntile(enrollment, 4), .by = state)
df |> mutate(decile = ntile(enrollment, 10), .by = state)
```

### Ranking Comparison

| Function | 100, 100, 80 | Gaps? |
|----------|-------------|-------|
| `row_number()` | 1, 2, 3 | N/A (no ties) |
| `min_rank()` | 1, 1, 3 | Yes |
| `dense_rank()` | 1, 1, 2 | No |
| `percent_rank()` | 0, 0, 1 | Scaled |
| `cume_dist()` | 0.67, 0.67, 1 | Proportion |

---

## lag() and lead() -- Shifted Values

### Basic Usage

```r
# Previous value (lag)
df |> mutate(prev_enrollment = lag(enrollment))

# Next value (lead)
df |> mutate(next_enrollment = lead(enrollment))

# Lag by N positions
df |> mutate(prev2 = lag(enrollment, n = 2))

# Default for first/last values (instead of NA)
df |> mutate(prev = lag(enrollment, default = 0))
```

### Grouped Lag/Lead

```r
# Lag within groups (shift resets at group boundaries)
df |>
  arrange(state, year) |>
  group_by(state) |>
  mutate(
    prev_enrollment = lag(enrollment),
    enrollment_change = enrollment - lag(enrollment),
    pct_change = (enrollment - lag(enrollment)) / lag(enrollment) * 100
  ) |>
  ungroup()

# Or with .by (requires data to be sorted)
df |>
  arrange(state, year) |>
  mutate(
    prev_enrollment = lag(enrollment),
    enrollment_change = enrollment - lag(enrollment),
    .by = state
  )
```

### Year-Over-Year Change

```r
# INTENT: Calculate year-over-year enrollment change per school
# ASSUMES: Data sorted by school and year; one row per school-year
result <- df |>
  arrange(ncessch, year) |>
  group_by(ncessch) |>
  mutate(
    prev_year_enroll = lag(enrollment),
    yoy_change = enrollment - prev_year_enroll,
    yoy_pct = yoy_change / prev_year_enroll * 100
  ) |>
  ungroup()

# Validate: first year per school should have NA for prev
n_na <- sum(is.na(result$prev_year_enroll))
cat("Rows with NA prev_year (expected = n_schools):", n_na, "\n")
```

---

## Cumulative Functions

### Built-in Cumulative Functions

```r
df |> mutate(
  running_total = cumsum(enrollment),
  running_max = cummax(enrollment),
  running_min = cummin(enrollment),
  running_product = cumprod(growth_rate)
)
```

### Grouped Cumulative

```r
df |>
  arrange(state, year) |>
  group_by(state) |>
  mutate(
    cum_enrollment = cumsum(enrollment),
    cum_mean = cumsum(enrollment) / row_number()
  ) |>
  ungroup()
```

### Cumulative Logical

```r
# cumall: TRUE until first FALSE
df |> mutate(all_positive_so_far = cumall(value > 0))

# cumany: FALSE until first TRUE
df |> mutate(ever_exceeded = cumany(value > threshold))
```

---

## Rolling / Sliding Window Operations

Base R does not have built-in rolling window functions. Use the `slider` package
or `zoo::rollmean()`:

### With slider Package

```r
library(slider)

# Rolling mean with window of 3 (current + 2 preceding)
df |> mutate(
  rolling_avg = slide_dbl(enrollment, mean, .before = 2, .complete = TRUE)
)

# Rolling sum
df |> mutate(
  rolling_sum = slide_dbl(enrollment, sum, .before = 6)
)

# Rolling with both before and after (centered window)
df |> mutate(
  centered_avg = slide_dbl(enrollment, mean, .before = 1, .after = 1)
)

# Rolling within groups
df |>
  arrange(state, year) |>
  group_by(state) |>
  mutate(
    rolling_avg = slide_dbl(enrollment, mean, .before = 2, .complete = TRUE)
  ) |>
  ungroup()
```

### With zoo Package

```r
library(zoo)

# Rolling mean (trailing window)
df |> mutate(
  rolling_avg = rollmean(enrollment, k = 3, fill = NA, align = "right")
)

# Rolling sum
df |> mutate(
  rolling_sum = rollsum(enrollment, k = 3, fill = NA, align = "right")
)
```

---

## Combining Window Functions

### Top N Per Group

```r
# Top 5 schools per state by enrollment
df |>
  group_by(state) |>
  slice_max(enrollment, n = 5) |>
  ungroup()

# Or using rank
df |>
  mutate(rank = dense_rank(desc(enrollment)), .by = state) |>
  filter(rank <= 5)
```

### Running Percentage of Total

```r
df |>
  arrange(state, desc(enrollment)) |>
  group_by(state) |>
  mutate(
    cum_enroll = cumsum(enrollment),
    total_enroll = sum(enrollment),
    cum_pct = cum_enroll / total_enroll * 100
  ) |>
  ungroup()
```

### Consecutive ID (Run-Length Grouping, dplyr 1.1+)

```r
# Assign IDs to consecutive runs of the same value
df |> mutate(
  run_id = consecutive_id(status)
)
# status: A, A, B, B, B, A -> run_id: 1, 1, 2, 2, 2, 3
```

---

## DAAF Pattern: Enrollment Trend with Validation

```r
# INTENT: Calculate 3-year rolling average enrollment per school
# ASSUMES: Panel is sorted and balanced within the rolling window
library(slider)

result <- df |>
  arrange(ncessch, year) |>
  group_by(ncessch) |>
  mutate(
    enroll_3yr_avg = slide_dbl(enrollment, mean, .before = 2, .complete = TRUE),
    yoy_change = enrollment - lag(enrollment)
  ) |>
  ungroup()

# Validate
n_complete <- sum(!is.na(result$enroll_3yr_avg))
cat("Rows with 3yr avg:", n_complete, "of", nrow(result), "\n")
cat("Rows with NA (expected for first 2 years per school):",
    sum(is.na(result$enroll_3yr_avg)), "\n")
```
