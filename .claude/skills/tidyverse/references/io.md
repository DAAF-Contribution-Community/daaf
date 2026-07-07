# I/O: Reading and Writing Data

This reference covers data I/O in R using arrow (parquet, the DAAF-preferred
format), readr (CSV), and related packages.

---

## Parquet Files (Preferred)

DAAF requires parquet format for all data files. The `arrow` package provides
`read_parquet()` and `write_parquet()`.

### Read Parquet

```r
library(arrow)

# Basic read -- returns a tibble
df <- read_parquet("data/schools.parquet")

# Read specific columns only (more memory-efficient)
df <- read_parquet("data/schools.parquet", col_select = c(ncessch, state, enrollment))

# Using tidyselect in col_select
df <- read_parquet("data/schools.parquet", col_select = starts_with("enroll"))
```

### Write Parquet

```r
library(arrow)

# Basic write
write_parquet(df, "data/output.parquet")

# With compression (default is snappy)
write_parquet(df, "data/output.parquet", compression = "zstd")
write_parquet(df, "data/output.parquet", compression = "gzip")
```

### Arrow Dataset for Large/Multi-File Data

For very large datasets or partitioned data:

```r
library(arrow)

# Read a directory of parquet files
ds <- open_dataset("data/partitioned/")

# Query with dplyr verbs (lazy -- only reads what's needed)
result <- ds |>
  filter(year == 2020) |>
  select(state, enrollment) |>
  collect()   # materialize the result

# Read with schema override
ds <- open_dataset("data/", schema = schema(
  id = int64(),
  name = utf8(),
  value = float64()
))
```

### Arrow-dplyr Integration

Arrow datasets support most dplyr verbs natively, enabling lazy evaluation on
parquet files (similar to polars' scan_parquet):

```r
# This only reads the columns and rows actually needed
result <- open_dataset("data/schools.parquet") |>
  filter(year >= 2018, !is.na(enrollment)) |>
  select(state, year, enrollment) |>
  group_by(state) |>
  summarize(total = sum(enrollment)) |>
  collect()
```

Not all R functions are supported in Arrow compute -- if you get an error, add
`collect()` before the unsupported operation to materialize the data first.

---

## CSV Files

### Read CSV with readr

```r
library(readr)

# Basic read (returns tibble, shows column types)
df <- read_csv("data/schools.csv")

# With column type specification
df <- read_csv("data/schools.csv", col_types = cols(
  ncessch = col_character(),   # prevent numeric coercion of IDs
  state = col_character(),
  enrollment = col_integer(),
  frl_rate = col_double()
))

# Common options
df <- read_csv(
  "data/schools.csv",
  skip = 2,                    # skip first 2 rows
  n_max = 1000,                # read only 1000 rows
  na = c("", "NA", "N/A", "."),  # values to treat as NA
  locale = locale(encoding = "UTF-8")
)

# Read from inline string (useful for testing)
# NOTE: readr 2.2.0+ requires I() wrapper for literal data
df <- read_csv(I("
state,year,enrollment
CA,2020,6200000
TX,2020,5400000
NY,2020,2600000
"))
```

### Column Type Shortcuts

```r
# Compact column type specification
df <- read_csv("data.csv", col_types = "ccidn")
# c = character, i = integer, d = double, n = number, l = logical
# D = date, T = datetime, t = time, _ = skip column
```

### Write CSV

```r
library(readr)

# Basic write
write_csv(df, "output/result.csv")

# Without quoting
write_csv(df, "output/result.csv", quote = "none")

# Custom NA representation
write_csv(df, "output/result.csv", na = "")
```

### TSV and Other Delimited Files

```r
# Tab-separated
df <- read_tsv("data.tsv")
write_tsv(df, "output.tsv")

# Any delimiter
df <- read_delim("data.txt", delim = "|")
write_delim(df, "output.txt", delim = "|")
```

---

## Excel Files

```r
library(readxl)

# Read Excel file
df <- read_excel("data.xlsx")

# Specific sheet
df <- read_excel("data.xlsx", sheet = "Sheet2")
df <- read_excel("data.xlsx", sheet = 2)

# Cell range
df <- read_excel("data.xlsx", range = "A1:D100")

# Column types
df <- read_excel("data.xlsx", col_types = c("text", "numeric", "date", "skip"))

# List available sheets
excel_sheets("data.xlsx")
```

Note: readxl is not part of core tidyverse but is commonly installed alongside it.
For writing Excel files, use the `writexl` package:

```r
library(writexl)
write_xlsx(df, "output.xlsx")
```

---

## Remote Fetching: HTTP and String Interpolation

Data-source fetch blocks that pull from APIs or remote files rely on three
packages installed in the DAAF container but not part of core tidyverse:

| Package | Version | Role |
|---------|---------|------|
| `httr2` | 1.2.2 | HTTP requests with a pipeable request builder and automatic retry |
| `glue` | 1.8.0 | String interpolation for building URLs and query parameters |
| `readxl` | 1.4.5 | Reading Excel files returned by some sources (see Excel section above) |

```r
library(httr2)
library(glue)

# Build a URL with glue interpolation
year <- 2022
url <- glue("https://api.example.gov/data?year={year}&format=json")

# httr2 request pipeline with retry on transient failures
resp <- request(url) |>
  req_retry(max_tries = 3) |>   # backs off and retries on 429/5xx
  req_perform()

data <- resp |> resp_body_json()
```

Use `req_retry()` for resilience against transient network errors, and prefer
`glue()` over `paste0()` for readable URL construction. For sources that deliver
Excel, combine `httr2` to download and `readxl::read_excel()` to parse.

---

## data.table I/O (High-Speed Alternative)

For very large CSV files, data.table's `fread()` is significantly faster:

```r
library(data.table)

# Fast CSV read
dt <- fread("data/large_file.csv")

# Convert to tibble for dplyr pipeline
df <- as_tibble(dt)

# fread with options
dt <- fread(
  "data.csv",
  select = c("state", "enrollment"),   # read only these columns
  nrows = 10000,
  na.strings = c("", "NA", "N/A"),
  colClasses = c(ncessch = "character")
)
```

See `data-table.md` for more on data.table I/O.

---

## R Native Formats

### RDS (Single Object)

```r
# Save
saveRDS(df, "data/schools.rds")

# Load
df <- readRDS("data/schools.rds")
```

RDS preserves R object types perfectly but is not interoperable with Python. Use
parquet for cross-language compatibility in DAAF.

### RData / RDA (Multiple Objects)

```r
# Save multiple objects
save(df1, df2, model, file = "data/workspace.RData")

# Load (objects restored to original names)
load("data/workspace.RData")
```

---

## Common I/O Patterns in DAAF

### Standard Load-and-Validate Pattern

```r
# --- Load ---
# INTENT: Load parquet data with validation
library(arrow)

path <- file.path(PROJECT_DIR, "data", "2026-01-15_ccd_schools.parquet")
stopifnot(file.exists(path))

df <- read_parquet(path)
cat("Loaded:", nrow(df), "rows x", ncol(df), "cols\n")
cat("Columns:", paste(names(df), collapse = ", "), "\n")

# Validate expected columns exist
expected_cols <- c("ncessch", "state", "year", "enrollment")
missing_cols <- setdiff(expected_cols, names(df))
stopifnot(length(missing_cols) == 0)
```

### Parquet Round-Trip

```r
# --- Save ---
# INTENT: Save processed data in DAAF-standard parquet format
out_path <- file.path(PROJECT_DIR, "data", "2026-01-15_state_enrollment.parquet")
write_parquet(df, out_path)
cat("Saved:", out_path, "\n")

# Verify round-trip
df_check <- read_parquet(out_path)
stopifnot(nrow(df_check) == nrow(df))
stopifnot(ncol(df_check) == ncol(df))
cat("Round-trip verified:", nrow(df_check), "rows\n")
```

### Reading Multiple Files

```r
library(purrr)
library(arrow)

# Read and combine multiple parquet files
files <- list.files("data/by_state/", pattern = "\\.parquet$", full.names = TRUE)
df <- map(files, read_parquet) |> list_rbind()
cat("Combined:", nrow(df), "rows from", length(files), "files\n")

# Or using arrow dataset (more efficient)
df <- open_dataset("data/by_state/") |> collect()
```
