# data.table: High-Performance Alternative

data.table is a high-performance R package for large-dataset manipulation. It uses
a concise `DT[i, j, by]` syntax and modifies data in place for speed. Use
data.table when dplyr pipelines are too slow on large datasets (millions of rows)
or when you need the fastest possible CSV I/O.

---

## When to Use data.table vs dplyr

| Scenario | Recommendation |
|----------|---------------|
| < 1M rows | dplyr (readability, pipe chains) |
| 1-10M rows | Either works; dplyr if pipeline clarity matters |
| > 10M rows | data.table (significantly faster) |
| Very large CSV files | `fread()` (much faster than `read_csv()`) |
| Memory-constrained | data.table (in-place modification) |
| Complex grouped operations | data.table (optimized `by` operations) |
| Readability priority | dplyr (verb names are self-documenting) |

In DAAF pipelines, dplyr is the default. Switch to data.table when performance
profiling shows dplyr is the bottleneck, or when dealing with datasets exceeding
several million rows.

---

## The DT[i, j, by] Syntax

data.table's core is a single bracket `DT[i, j, by]`:

- **i** = row filter (which rows)
- **j** = column operations (what to compute)
- **by** = grouping (grouped by what)

```r
library(data.table)

# Convert data.frame or tibble to data.table
DT <- as.data.table(df)

# Or read directly
DT <- fread("data.csv")
```

### Row Filtering (i)

```r
DT[year == 2020]
DT[year == 2020 & state == "CA"]
DT[enrollment > 500]
DT[state %in% c("CA", "TX", "NY")]
```

### Column Operations (j)

```r
# Select columns (returns data.table)
DT[, .(state, enrollment)]

# Compute new values
DT[, .(total = sum(enrollment))]

# Create/modify columns in place with :=
DT[, rate := frl_count / enrollment]
DT[, c("rate", "pct") := .(frl_count / enrollment, frl_count / enrollment * 100)]

# Remove columns
DT[, frl_count := NULL]
```

### Grouping (by)

```r
# Group and aggregate
DT[, .(avg_enroll = mean(enrollment), n = .N), by = state]

# Multiple grouping columns
DT[, .(avg = mean(enrollment)), by = .(state, year)]

# Filter + group in one call
DT[year == 2020, .(avg = mean(enrollment)), by = state]
```

---

## I/O: fread() and fwrite()

### fread() -- Fast CSV Reading

```r
# Basic read (auto-detects separator, header, types)
DT <- fread("data.csv")

# With options
DT <- fread(
  "data.csv",
  select = c("state", "year", "enrollment"),  # only these columns
  colClasses = c(ncessch = "character"),        # force types
  nrows = 10000,                                # limit rows
  na.strings = c("", "NA", "N/A"),
  key = "ncessch"                               # set key for fast lookup
)

# Read and convert to tibble for dplyr pipeline
df <- as_tibble(fread("large_file.csv"))
```

fread is typically 5-10x faster than `read_csv()` for large files.

### fwrite() -- Fast CSV Writing

```r
# Basic write
fwrite(DT, "output.csv")

# With options
fwrite(DT, "output.csv",
  sep = ",",
  na = "",
  dateTimeAs = "ISO"    # ISO format for dates
)
```

---

## Key Operations

### Setting Keys (for Fast Lookup and Joins)

```r
# Set key columns (sorts data and enables binary search)
setkey(DT, state, year)

# Key-based filtering (binary search, very fast)
DT[.("CA", 2020)]   # rows where state="CA" and year=2020

# Check current key
key(DT)
```

### Joins

```r
# Key-based join (right join by default)
setkey(DT1, id)
setkey(DT2, id)
DT1[DT2]              # right join
DT2[DT1]              # left join (swap order)

# Explicit merge
merge(DT1, DT2, by = "id", all.x = TRUE)   # left join
merge(DT1, DT2, by = "id")                  # inner join

# Non-equi join
DT1[DT2, on = .(id, date >= start_date, date <= end_date)]

# Rolling join (last observation carried forward)
DT1[DT2, on = "date", roll = TRUE]
```

### Chaining

```r
# Chain operations with ][
DT[year == 2020
  ][, .(avg = mean(enrollment)), by = state
  ][order(-avg)
  ][1:10]
```

---

## Special Symbols

| Symbol | Meaning |
|--------|---------|
| `.N` | Number of rows in the group |
| `.I` | Row indices |
| `.SD` | Subset of Data (columns for the current group) |
| `.SDcols` | Columns to include in `.SD` |
| `.GRP` | Group counter |
| `.BY` | Current group values |
| `:=` | Assign by reference (modify in place) |

```r
# Count per group
DT[, .N, by = state]

# Apply function to multiple columns
DT[, lapply(.SD, mean, na.rm = TRUE), by = state, .SDcols = c("enrollment", "frl_count")]

# First row per group
DT[, .SD[1], by = state]

# Row indices of max value per group
DT[, .SD[which.max(enrollment)], by = state]
```

---

## In-Place Modification

data.table's `:=` modifies the data.table in place (no copy). This is much faster
for large data but changes the original object:

```r
# Add column (modifies DT directly)
DT[, rate := frl_count / enrollment]

# Conditional modification
DT[enrollment > 0, rate := frl_count / enrollment]

# Multiple columns
DT[, `:=`(
  rate = frl_count / enrollment,
  pct = frl_count / enrollment * 100
)]

# Remove column
DT[, rate := NULL]
```

---

## Converting Between dplyr and data.table

```r
# tibble -> data.table
DT <- as.data.table(df)

# data.table -> tibble
df <- as_tibble(DT)

# Use data.table for speed, then continue with dplyr
result <- as_tibble(
  fread("large_file.csv")[year == 2020, .(state, enrollment)]
) |>
  group_by(state) |>
  summarize(total = sum(enrollment))
```

---

## Common DAAF Pattern: data.table for Speed-Critical Steps

```r
# --- Config ---
library(data.table)
library(dplyr)
library(arrow)

# --- Load ---
# INTENT: Fast load of large CSV, convert to tibble for pipeline
# REASONING: fread is 5-10x faster than read_csv for this file size
DT <- fread(file.path(PROJECT_DIR, "data", "large_dataset.csv"),
            select = c("ncessch", "state", "year", "enrollment"),
            colClasses = c(ncessch = "character"))
cat("Loaded:", nrow(DT), "rows via fread\n")

# Convert to tibble for rest of pipeline
df <- as_tibble(DT)

# --- Transform ---
# Continue with dplyr pipeline
result <- df |>
  filter(year >= 2015) |>
  group_by(state, year) |>
  summarize(total = sum(enrollment, na.rm = TRUE), .groups = "drop")

# --- Save ---
write_parquet(result, file.path(PROJECT_DIR, "data", "state_totals.parquet"))
```

---

## Performance Tips

1. **Use `fread()`** for reading large CSV files, even if you convert to tibble immediately after
2. **Set keys** on columns used for filtering and joining -- enables binary search
3. **Use `:=`** for in-place column creation instead of creating copies
4. **Avoid `DT$col`** in j expressions -- use bare column names: `DT[, mean(x)]` not `DT[, mean(DT$x)]`
5. **Use `.SD` with `.SDcols`** to limit which columns are processed
6. **Chain with `][`** instead of creating intermediate objects
7. For parquet I/O, use arrow regardless -- data.table does not have parquet support
