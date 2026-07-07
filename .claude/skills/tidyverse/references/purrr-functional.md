# purrr: Functional Iteration

This reference covers purrr's map functions for iterating over lists, vectors, and
nested data structures. purrr replaces `for` loops and `*apply` functions with a
consistent, type-safe API.

---

## Core Concept

purrr's `map()` family applies a function to each element of a list or vector:

```
map(.x, .f) -> list
```

Where `.x` is the input (list or vector) and `.f` is the function to apply.

---

## map() Variants by Return Type

| Function | Returns | Use When |
|----------|---------|----------|
| `map()` | list | Default; any output type |
| `map_chr()` | character vector | Each result is a single string |
| `map_dbl()` | double vector | Each result is a single number |
| `map_int()` | integer vector | Each result is a single integer |
| `map_lgl()` | logical vector | Each result is TRUE/FALSE |
| `map_vec()` | vector (auto-typed) | Simplified output, purrr 1.0+ |
| `list_rbind()` | data frame (row-bind) | Each result is a data frame |
| `list_cbind()` | data frame (col-bind) | Each result is a data frame |
| `list_c()` | vector (concatenated) | Each result is a vector |

### Basic Examples

```r
library(purrr)

# map returns a list
map(1:3, \(x) x^2)       # list(1, 4, 9)

# map_dbl returns a numeric vector
map_dbl(1:3, \(x) x^2)   # c(1, 4, 9)

# map_chr returns a character vector
map_chr(1:3, \(x) paste0("item_", x))   # c("item_1", "item_2", "item_3")

# map_lgl returns a logical vector
map_lgl(1:3, \(x) x > 1)   # c(FALSE, TRUE, TRUE)
```

### Lambda (Anonymous Function) Syntax

```r
# Modern R lambda (preferred in DAAF)
map(x, \(item) item + 1)

# purrr formula shorthand (legacy but common)
map(x, ~ .x + 1)

# Named function
map(x, sqrt)

# Function with extra arguments
map(x, round, digits = 2)
```

---

## Iterating Over Multiple Inputs

### map2() -- Two Parallel Inputs

```r
# Apply function to pairs of elements
map2(1:3, 4:6, \(x, y) x + y)   # list(5, 7, 9)
map2_dbl(1:3, 4:6, \(x, y) x + y)   # c(5, 7, 9)

# Common: read files with parameters
map2(file_paths, file_names, \(path, name) {
  df <- read_parquet(path)
  df |> mutate(source = name)
})
```

### pmap() -- Many Parallel Inputs

```r
# Apply function to rows of a data frame or list of lists
params <- list(
  x = 1:3,
  y = 4:6,
  z = 7:9
)
pmap_dbl(params, \(x, y, z) x + y + z)   # c(12, 15, 18)
```

---

## walk() -- Iterate for Side Effects

`walk()` is like `map()` but returns the input invisibly -- use for side effects
(printing, writing files, plotting):

```r
# Write multiple data frames to parquet files
walk2(data_list, file_paths, \(df, path) {
  write_parquet(df, path)
  cat("Wrote:", path, "\n")
})

# Print summaries
walk(data_list, \(df) {
  cat("Rows:", nrow(df), "Cols:", ncol(df), "\n")
})
```

---

## Working with Lists

### List Extraction

```r
# Extract named elements
x <- list(list(a = 1, b = 2), list(a = 3, b = 4))

map(x, "a")           # list(1, 3) -- extract by name
map_dbl(x, "a")       # c(1, 3)
map(x, 1)             # list(1, 3) -- extract by position
```

### pluck() -- Deep Extraction

```r
# Extract nested elements
x <- list(
  list(name = "A", data = list(value = 10)),
  list(name = "B", data = list(value = 20))
)

map_dbl(x, \(item) pluck(item, "data", "value"))   # c(10, 20)

# Or use list indexing shorthand
map_dbl(x, list("data", "value"))   # c(10, 20)
```

### keep() and discard() -- Filter Lists

```r
# Keep elements matching a predicate
x <- list(1, "a", 2, "b", 3)
keep(x, is.numeric)      # list(1, 2, 3)
discard(x, is.numeric)   # list("a", "b")

# With data frames in a list
keep(df_list, \(df) nrow(df) > 100)
```

### compact() -- Remove NULL/Empty

```r
x <- list(1, NULL, 3, NULL, 5)
compact(x)   # list(1, 3, 5)
```

### reduce() -- Accumulate

```r
# Combine a list of data frames with a joining function
reduce(df_list, left_join, by = "id")

# Numeric reduction
reduce(1:4, `+`)   # 10 (((1+2)+3)+4)
```

---

## List-Columns and Nested Data

List-columns store complex objects (data frames, models, vectors) inside tibble
cells. Combined with purrr, this enables powerful group-and-apply workflows.

### Creating List-Columns

```r
# Via nest()
nested <- df |> nest(.by = state)
# | state | data        |
# | CA    | <tibble>    |
# | TX    | <tibble>    |

# Via summarize with list()
df |>
  group_by(state) |>
  summarize(enrollments = list(enrollment), .groups = "drop")
```

### Operating on List-Columns

```r
# Apply a function to each nested data frame
nested |> mutate(
  n_rows = map_int(data, nrow),
  avg_enroll = map_dbl(data, \(d) mean(d$enrollment, na.rm = TRUE))
)

# Fit models per group
nested |> mutate(
  model = map(data, \(d) lm(enrollment ~ year, data = d)),
  coefs = map(model, broom::tidy)
)
```

### Unnesting Results

```r
# Unnest a list-column of data frames
nested |>
  mutate(coefs = map(model, broom::tidy)) |>
  unnest(coefs)

# Unnest a list-column of vectors
df |>
  mutate(parts = map(text, \(t) str_split(t, ",")[[1]])) |>
  unnest(parts)
```

---

## Reading Multiple Files

One of the most common purrr patterns in DAAF:

```r
library(purrr)
library(arrow)

# List all parquet files
files <- list.files("data/", pattern = "\\.parquet$", full.names = TRUE)

# Read and combine
df <- map(files, read_parquet) |> list_rbind()
cat("Combined:", nrow(df), "rows from", length(files), "files\n")

# Read with file source tracking
df <- map(files, \(f) {
  read_parquet(f) |> mutate(source_file = basename(f))
}) |> list_rbind()

# Read CSV files with error handling
results <- map(files, possibly(read_csv, otherwise = NULL))
df <- compact(results) |> list_rbind()
cat("Successfully read:", length(compact(results)), "of", length(files), "files\n")
```

---

## Error Handling

### possibly() -- Return Default on Error

```r
# Wrap a function to return a default instead of erroring
safe_read <- possibly(read_parquet, otherwise = NULL)
results <- map(files, safe_read)
successful <- compact(results)
```

### safely() -- Capture Both Result and Error

```r
safe_read <- safely(read_parquet)
results <- map(files, safe_read)

# results is a list of list(result = ..., error = ...)
successes <- map(results, "result") |> compact()
errors <- map(results, "error") |> compact()
cat("Successes:", length(successes), "Errors:", length(errors), "\n")
```

### insistently() -- Retry on Error

```r
# Retry up to 3 times with backoff
resilient_fetch <- insistently(fetch_data, rate = rate_backoff(max_times = 3))
result <- resilient_fetch(url)
```

---

## imap() -- Iterate with Index/Name

```r
# .x is the element, .y is the index (or name)
imap(list(a = 1, b = 2), \(val, name) paste(name, "=", val))
# list("a = 1", "b = 2")

# With numeric index
imap_chr(letters[1:3], \(val, idx) paste0(idx, ": ", val))
# c("1: a", "2: b", "3: c")
```
