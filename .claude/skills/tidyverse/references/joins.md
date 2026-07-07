# Joins: Combining Data Frames

This reference covers dplyr's join functions for merging datasets by key columns.

---

## Join Types

### left_join() -- Keep All Left Rows

Returns all rows from the left data frame. Unmatched rows from the right get NA:

```r
# Basic left join
df1 |> left_join(df2, by = "key")

# Multiple keys
df1 |> left_join(df2, by = c("state", "year"))
```

This is the most common join in DAAF pipelines -- add reference data to a primary
dataset without losing any primary rows.

### inner_join() -- Keep Only Matches

Returns only rows with matches in both data frames:

```r
df1 |> inner_join(df2, by = "key")
```

Use when you need only records that exist in both sources.

### full_join() -- Keep Everything

Returns all rows from both data frames, with NA for non-matches:

```r
df1 |> full_join(df2, by = "key")
```

### right_join() -- Keep All Right Rows

```r
df1 |> right_join(df2, by = "key")
```

Equivalent to `df2 |> left_join(df1, by = "key")`.

### anti_join() -- Rows NOT in Other

Returns rows from the left that have NO match in the right. No columns from the
right are included:

```r
# Find schools in df1 that are missing from df2
df1 |> anti_join(df2, by = "ncessch")
```

Extremely useful for data validation -- finding unmatched records.

### semi_join() -- Rows WITH a Match (Filter Only)

Returns rows from the left that HAVE a match in the right, but does not add any
columns from the right:

```r
# Keep only schools that appear in the reference list
df |> semi_join(reference_schools, by = "ncessch")
```

Like `filter()` using another data frame as the condition.

### cross_join() -- Cartesian Product

```r
# Every row of df1 paired with every row of df2
df1 |> cross_join(df2)
```

Use sparingly -- creates `nrow(df1) * nrow(df2)` rows. Useful for creating complete
grids of combinations.

---

## Join Keys

### Same Column Name in Both Data Frames

```r
# Single key
df1 |> left_join(df2, by = "state")

# Multiple keys
df1 |> left_join(df2, by = c("state", "year"))
```

### Different Column Names

```r
# Column "state" in df1 matches "st" in df2
df1 |> left_join(df2, by = c("state" = "st"))

# Multiple different-named keys
df1 |> left_join(df2, by = c("state" = "st", "year" = "acad_year"))
```

### join_by() -- Flexible Join Specification (dplyr 1.1+)

```r
# Equality join (same as by =)
df1 |> left_join(df2, join_by(state, year))

# Different names
df1 |> left_join(df2, join_by(state == st, year == acad_year))

# Inequality join -- find records where date falls in a range
df1 |> left_join(
  df2,
  join_by(id, between(date, start_date, end_date))
)

# Overlap join
df1 |> left_join(
  df2,
  join_by(id, overlaps(start1, end1, start2, end2))
)

# Rolling join (closest preceding match)
df1 |> left_join(
  df2,
  join_by(id, closest(date >= ref_date))
)
```

---

## Join Validation

### Checking Join Quality

Always validate joins in DAAF pipelines:

```r
# INTENT: Join school data with district data
# REASONING: left_join preserves all schools; expect some unmatched
n_before <- nrow(schools)
result <- schools |> left_join(districts, by = "leaid")
n_after <- nrow(result)

# Check for row count changes (indicates many-to-many)
stopifnot(n_after == n_before)
cat("Rows: before =", n_before, ", after =", n_after, "\n")

# Check for unmatched records
n_unmatched <- sum(is.na(result$district_name))
cat("Unmatched schools:", n_unmatched, "(", round(n_unmatched / n_after * 100, 1), "%)\n")
```

### relationship Argument (dplyr 1.1+)

Guard against unexpected cardinality:

```r
# Expect one-to-one
df1 |> left_join(df2, by = "id", relationship = "one-to-one")

# Expect many-to-one (multiple schools per district)
schools |> left_join(districts, by = "leaid", relationship = "many-to-one")

# Expect one-to-many
districts |> left_join(schools, by = "leaid", relationship = "one-to-many")

# Allow many-to-many (explicit opt-in)
df1 |> left_join(df2, by = "key", relationship = "many-to-many")
```

If the relationship constraint is violated, dplyr throws an error -- catching data
issues at join time rather than downstream.

### unmatched Argument (dplyr 1.1+)

```r
# Error if any left-side row is unmatched (inner join semantics check)
df1 |> left_join(df2, by = "key", unmatched = "error")

# Default: silently fill with NA
df1 |> left_join(df2, by = "key", unmatched = "drop")
```

---

## Handling Duplicate Column Names

When both data frames have columns with the same name (other than the join key):

```r
# Default: adds .x and .y suffixes
df1 |> left_join(df2, by = "id")
# If both have "name" column: name.x, name.y

# Custom suffixes
df1 |> left_join(df2, by = "id", suffix = c("_left", "_right"))
```

---

## Multiple-Table Joins

### Chaining Joins

```r
# Join multiple reference tables to a primary dataset
result <- schools |>
  left_join(districts, by = "leaid") |>
  left_join(states, by = "state") |>
  left_join(poverty, by = c("leaid", "year"))
```

### Using reduce for Many Tables

```r
# Join a list of data frames sequentially
library(purrr)

tables <- list(df1, df2, df3, df4)
result <- reduce(tables, left_join, by = "id")
```

---

## Common DAAF Join Patterns

### School-District Join with Validation

```r
# INTENT: Merge school-level data with district characteristics
# REASONING: Many schools per district, so many-to-one relationship
n_schools <- nrow(schools)

merged <- schools |>
  left_join(
    districts |> select(leaid, district_name, locale_code),
    by = "leaid",
    relationship = "many-to-one"
  )

# --- Validate ---
stopifnot(nrow(merged) == n_schools)
n_missing_district <- sum(is.na(merged$district_name))
cat("Schools missing district match:", n_missing_district,
    "(", round(n_missing_district / n_schools * 100, 1), "%)\n")
```

### Finding Unmatched Records

```r
# INTENT: Identify schools in CCD that are missing from CRDC
missing_from_crdc <- ccd_schools |>
  anti_join(crdc_schools, by = "ncessch")

cat("Schools in CCD but not CRDC:", nrow(missing_from_crdc), "\n")
```

### Cross-Year Comparison

```r
# INTENT: Compare enrollment between two years for the same schools
comparison <- schools_2020 |>
  inner_join(
    schools_2021 |> select(ncessch, enrollment_2021 = enrollment),
    by = "ncessch"
  ) |>
  mutate(enrollment_change = enrollment_2021 - enrollment)
```
