# Reshaping: pivot_longer, pivot_wider, separate, unite, nest/unnest

This reference covers tidyr functions for converting between data layouts and
splitting/combining columns.

---

## pivot_longer() -- Wide to Long

Converts columns into rows. Use when data has values spread across column names
(e.g., `pop_2020`, `pop_2021`, `pop_2022`).

### Basic Usage

```r
# Wide format: each year is a column
# | state | pop_2020 | pop_2021 | pop_2022 |
# | CA    | 39500    | 39200    | 39000    |

df |> pivot_longer(
  cols = c(pop_2020, pop_2021, pop_2022),
  names_to = "year",
  values_to = "population"
)

# Result:
# | state | year     | population |
# | CA    | pop_2020 | 39500      |
# | CA    | pop_2021 | 39200      |
# | CA    | pop_2022 | 39000      |
```

### Column Selection in `cols`

```r
# By name
df |> pivot_longer(cols = c(pop_2020, pop_2021, pop_2022))

# With tidyselect helpers
df |> pivot_longer(cols = starts_with("pop_"))
df |> pivot_longer(cols = matches("^pop_\\d{4}$"))

# Everything except identifier columns
df |> pivot_longer(cols = -c(state, county))
df |> pivot_longer(cols = !c(state, county))
```

### Parsing Column Names

Extract structured information from column names:

```r
# Names contain a prefix and a year: pop_2020, pop_2021
df |> pivot_longer(
  cols = starts_with("pop_"),
  names_to = "year",
  names_prefix = "pop_",     # strip prefix before storing
  values_to = "population"
)
# year column now contains "2020", "2021", etc.

# Parse names into multiple columns
# Columns like: male_2020, female_2020, male_2021, female_2021
df |> pivot_longer(
  cols = -state,
  names_to = c("sex", "year"),
  names_sep = "_",
  values_to = "count"
)

# Using .value sentinel -- values go to multiple columns
# Columns like: enrollment_2020, enrollment_2021, frl_2020, frl_2021
df |> pivot_longer(
  cols = -state,
  names_to = c(".value", "year"),
  names_sep = "_"
)
# Creates columns: year, enrollment, frl (two value columns, not one)
```

### Type Conversion

```r
df |> pivot_longer(
  cols = starts_with("pop_"),
  names_to = "year",
  names_prefix = "pop_",
  names_transform = list(year = as.integer),  # convert year to integer
  values_to = "population",
  values_transform = list(population = as.numeric)
)
```

### Dropping NAs

```r
df |> pivot_longer(
  cols = starts_with("val_"),
  names_to = "variable",
  values_to = "value",
  values_drop_na = TRUE   # drop rows where value is NA
)
```

---

## pivot_wider() -- Long to Wide

Converts rows into columns. The inverse of `pivot_longer()`.

### Basic Usage

```r
# Long format:
# | state | year | population |
# | CA    | 2020 | 39500      |
# | CA    | 2021 | 39200      |

df |> pivot_wider(
  names_from = year,
  values_from = population
)

# Result:
# | state | 2020  | 2021  |
# | CA    | 39500 | 39200 |
```

### Controlling Column Names

```r
# Add prefix to column names
df |> pivot_wider(
  names_from = year,
  values_from = population,
  names_prefix = "pop_"
)
# Columns: state, pop_2020, pop_2021

# Combine multiple name columns
# Long: | state | sex | year | count |
df |> pivot_wider(
  names_from = c(sex, year),
  values_from = count,
  names_sep = "_"
)
# Columns: state, male_2020, female_2020, male_2021, ...
```

### Specifying ID Columns

```r
# Explicit id columns (keeps only these + new columns)
df |> pivot_wider(
  id_cols = c(state, county),
  names_from = year,
  values_from = population
)
```

### Handling Duplicates

When there are multiple values for a combination, use an aggregation function:

```r
df |> pivot_wider(
  names_from = year,
  values_from = population,
  values_fn = sum        # or mean, first, list, etc.
)

# Fill missing combinations with a value
df |> pivot_wider(
  names_from = year,
  values_from = population,
  values_fill = 0
)
```

---

## separate() and separate_wider_*() -- Split a Column

### separate_wider_delim() (tidyr 1.3+, preferred)

```r
# Split "city-state" into two columns
df |> separate_wider_delim(
  location,
  delim = "-",
  names = c("city", "state")
)

# Handle extra pieces
df |> separate_wider_delim(
  col,
  delim = "-",
  names = c("first", "second"),
  too_many = "merge"    # merge extras into last column
)

# Handle too few pieces
df |> separate_wider_delim(
  col,
  delim = "-",
  names = c("first", "second"),
  too_few = "align_start"  # fill missing from right with NA
)
```

### separate_wider_position()

```r
# Split by character position (e.g., FIPS codes)
# State FIPS = first 2 chars, county = next 3
df |> separate_wider_position(
  fips,
  widths = c(state_fips = 2, county_fips = 3)
)
```

### separate_wider_regex()

```r
# Split by regex pattern
df |> separate_wider_regex(
  col,
  patterns = c(
    prefix = "[A-Z]+",
    "-",
    number = "\\d+"
  )
)
```

### Legacy separate()

```r
# Still works but the wider variants are preferred
df |> separate(col, into = c("first", "second"), sep = "-")
df |> separate(col, into = c("first", "second"), sep = 3)  # by position
```

---

## unite() -- Combine Columns

```r
# Combine columns with a separator
df |> unite(full_fips, state_fips, county_fips, sep = "")

# Keep original columns
df |> unite(full_fips, state_fips, county_fips, sep = "", remove = FALSE)

# Handle NAs
df |> unite(label, col1, col2, sep = "_", na.rm = TRUE)
```

---

## nest() and unnest() -- Nested Data Frames

### nest() -- Create Nested Tibbles

```r
# Nest all non-grouping columns into a list-column
df |> nest(data = c(year, enrollment, frl_count))

# Nest by group (shorthand)
df |> nest(.by = state)
# Creates: | state | data |
# Where data is a list of tibbles, one per state
```

### unnest() -- Expand Nested Tibbles

```r
# Unnest a list-column back to rows
nested_df |> unnest(data)

# Unnest specific columns
nested_df |> unnest(c(data, metadata))

# Control column naming for multiple list-columns
nested_df |> unnest_wider(info)   # list elements become columns
nested_df |> unnest_longer(vals)  # list elements become rows
```

### Nested Data Workflow

Nesting is powerful for applying operations per group:

```r
# INTENT: Fit a model per state and extract coefficients
library(purrr)

results <- df |>
  nest(.by = state) |>
  mutate(
    model = map(data, \(d) lm(enrollment ~ year, data = d)),
    coefs = map(model, broom::tidy)
  ) |>
  unnest(coefs) |>
  select(state, term, estimate, p.value)
```

---

## complete() -- Make Implicit Missing Values Explicit

```r
# Ensure every combination of state and year exists
df |> complete(state, year)

# With fill values for new rows
df |> complete(state, year, fill = list(enrollment = 0, frl_count = 0))

# Crossing specific values
df |> complete(state, year = 2015:2022)

# Nesting to avoid impossible combinations
df |> complete(nesting(state, county), year = 2015:2022)
```

---

## fill() -- Fill Missing Values Down/Up

```r
# Fill NAs downward (last observation carried forward)
df |> fill(value, .direction = "down")

# Fill upward
df |> fill(value, .direction = "up")

# Fill in both directions (down first, then up)
df |> fill(value, .direction = "downup")

# Fill within groups
df |>
  group_by(state) |>
  fill(value, .direction = "down") |>
  ungroup()
```

---

## replace_na() -- Replace NAs with a Value

```r
# Replace NAs in specific columns
df |> mutate(
  enrollment = replace_na(enrollment, 0),
  school_name = replace_na(school_name, "Unknown")
)

# Or using tidyr::replace_na on the whole data frame
df |> replace_na(list(enrollment = 0, frl_count = 0))
```

---

## drop_na() -- Remove Rows with NAs

```r
# Drop rows with any NA
df |> drop_na()

# Drop rows with NA in specific columns
df |> drop_na(enrollment, frl_count)
```

---

## Common Reshaping Patterns in DAAF

### Wide CCD Data to Tidy Format

```r
# INTENT: Reshape enrollment-by-race columns to long format
# ASSUMES: Columns follow pattern enrollment_{race} (e.g., enrollment_white, enrollment_black)
tidy_enrollment <- df |>
  pivot_longer(
    cols = starts_with("enrollment_"),
    names_to = "race",
    names_prefix = "enrollment_",
    values_to = "enrollment"
  )
cat("Rows:", nrow(tidy_enrollment), "(expect", nrow(df), "x num_race_cols)\n")
```

### Panel Data Completeness Check

```r
# INTENT: Ensure balanced panel (every school-year combination)
complete_panel <- df |>
  complete(ncessch, year) |>
  mutate(is_missing = is.na(enrollment))

missing_pct <- mean(complete_panel$is_missing) * 100
cat("Missing school-years:", round(missing_pct, 1), "%\n")
```
