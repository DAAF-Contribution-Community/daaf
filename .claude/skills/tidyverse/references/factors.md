# Factors: forcats for Categorical Data

This reference covers forcats functions for manipulating factors (categorical
variables) in R. Factors are essential for controlling the order of categories in
tables, plots, and models.

---

## What Are Factors?

Factors are R's way of representing categorical variables with a fixed set of
possible values (levels). The level order controls how categories appear in tables,
plots, and model output:

```r
# Create a factor
x <- factor(c("low", "high", "medium", "low"))
x
# [1] low    high   medium low
# Levels: high low medium   <-- alphabetical by default

# With explicit level order
x <- factor(c("low", "high", "medium", "low"),
            levels = c("low", "medium", "high"))
x
# Levels: low medium high   <-- custom order
```

---

## Inspecting Factors

```r
levels(x)          # character vector of levels
nlevels(x)         # count of levels
fct_count(x)       # tibble of level counts
fct_unique(x)      # unique levels in order
```

---

## Reordering Levels

### fct_relevel() -- Manual Reordering

```r
# Move specific levels to the front
fct_relevel(x, "medium")           # medium first, rest alphabetical
fct_relevel(x, "low", "medium", "high")  # full explicit order

# Move to a specific position
fct_relevel(x, "high", after = 2)  # high after the 2nd level

# Move to the end
fct_relevel(x, "other", after = Inf)

# In a pipeline
df |> mutate(
  size = fct_relevel(size, "small", "medium", "large")
)
```

### fct_reorder() -- Order by Another Variable

Order factor levels by a summary of another variable (most useful for plots):

```r
# Order states by median enrollment (ascending)
df |> mutate(
  state = fct_reorder(state, enrollment, .fun = median)
)

# Descending order
df |> mutate(
  state = fct_reorder(state, enrollment, .fun = median, .desc = TRUE)
)

# Order by a specific statistic
df |> mutate(
  state = fct_reorder(state, poverty_rate, .fun = mean)
)
```

### fct_reorder2() -- Order by Two Variables

Useful for line plots where you want the legend order to match the line endpoints:

```r
# Order by the last value of y for each level
df |> mutate(
  state = fct_reorder2(state, year, enrollment)
)
```

### fct_infreq() -- Order by Frequency

```r
# Most common levels first
df |> mutate(
  school_type = fct_infreq(school_type)
)

# Reverse: least common first
df |> mutate(
  school_type = fct_rev(fct_infreq(school_type))
)
```

### fct_rev() -- Reverse Level Order

```r
df |> mutate(size = fct_rev(size))
```

### fct_shift() -- Shift Levels

```r
# Rotate levels: first becomes last
fct_shift(x, n = 1)

# Rotate in the other direction
fct_shift(x, n = -1)
```

---

## Modifying Levels

### fct_recode() -- Rename Specific Levels

```r
df |> mutate(
  locale = fct_recode(locale,
    "City"     = "11",
    "City"     = "12",
    "City"     = "13",
    "Suburb"   = "21",
    "Suburb"   = "22",
    "Suburb"   = "23",
    "Town"     = "31",
    "Town"     = "32",
    "Town"     = "33",
    "Rural"    = "41",
    "Rural"    = "42",
    "Rural"    = "43"
  )
)
```

### fct_collapse() -- Merge Levels into Groups

```r
df |> mutate(
  region = fct_collapse(state,
    "West"      = c("CA", "OR", "WA", "NV"),
    "Northeast" = c("NY", "NJ", "CT", "MA"),
    "South"     = c("TX", "FL", "GA", "NC"),
    other_level = "Other"
  )
)
```

### fct_lump() -- Lump Infrequent Levels Together

```r
# Keep top N most frequent, lump rest into "Other"
df |> mutate(
  school_type = fct_lump_n(school_type, n = 5)
)

# Keep levels with at least min proportion
df |> mutate(
  school_type = fct_lump_prop(school_type, prop = 0.01)
)

# Keep levels with at least min count
df |> mutate(
  school_type = fct_lump_min(school_type, min = 100)
)

# Custom "other" label
df |> mutate(
  school_type = fct_lump_n(school_type, n = 5, other_level = "All other")
)

# Lump least frequent levels (no n argument) so "Other" stays the smallest level
df |> mutate(
  school_type = fct_lump_lowfreq(school_type)
)
```

### fct_other() -- Keep Specific, Lump Rest

```r
# Keep only these levels, lump everything else
df |> mutate(
  state = fct_other(state, keep = c("CA", "TX", "NY"))
)

# Drop specific levels to "Other"
df |> mutate(
  state = fct_other(state, drop = c("AS", "GU", "PR", "VI"))
)
```

---

## Adding and Removing Levels

### fct_expand() -- Add New Levels

```r
# Add levels that don't appear in the data yet
df |> mutate(
  status = fct_expand(status, "pending", "archived")
)
```

### fct_drop() -- Remove Unused Levels

```r
# After filtering, some levels may have zero observations
filtered <- df |> filter(state %in% c("CA", "TX"))
filtered |> mutate(state = fct_drop(state))
```

### fct_na_value_to_level() -- Make NA a Level

```r
# Convert NA to an explicit factor level
df |> mutate(
  locale = fct_na_value_to_level(locale, level = "Unknown")
)
```

---

## Factor Conversion

```r
# Character to factor
df |> mutate(state = as.factor(state))

# Factor to character
df |> mutate(state = as.character(state))

# Factor to numeric (get underlying integer codes)
as.numeric(x)

# Factor to numeric (get label values)
as.numeric(as.character(x))
# Or: as.numeric(levels(x))[x]
```

---

## Common DAAF Patterns

### Creating Ordered Categories for Analysis

```r
# INTENT: Create poverty tercile groups for tabulation
# REASONING: Equal-frequency bins ensure similar group sizes
df |> mutate(
  poverty_group = cut(
    poverty_rate,
    breaks = quantile(poverty_rate, c(0, 1/3, 2/3, 1), na.rm = TRUE),
    labels = c("Low", "Medium", "High"),
    include.lowest = TRUE
  ),
  poverty_group = fct_relevel(poverty_group, "Low", "Medium", "High")
)
```

### Preparing Factors for ggplot2

```r
# INTENT: Order states by enrollment for a bar chart
plot_data <- df |>
  group_by(state) |>
  summarize(total = sum(enrollment), .groups = "drop") |>
  mutate(state = fct_reorder(state, total))

# Now ggplot2 will display states in enrollment order
```

### Collapsing Locale Codes

```r
# INTENT: Collapse 12 locale codes to 4 categories
# ASSUMES: locale_code follows NCES locale classification (11-43)
df |> mutate(
  locale_type = fct_collapse(as.character(locale_code),
    "City"   = c("11", "12", "13"),
    "Suburb" = c("21", "22", "23"),
    "Town"   = c("31", "32", "33"),
    "Rural"  = c("41", "42", "43")
  )
)
```
