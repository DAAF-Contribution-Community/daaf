# Strings and Dates: stringr and lubridate

This reference covers string operations with stringr and date/time handling with
lubridate.

---

## stringr: String Operations

All stringr functions start with `str_` and take the string vector as the first
argument, making them pipe-friendly. They wrap the stringi package for consistent
cross-platform behavior.

### Detection and Matching

```r
# Does the string contain the pattern?
str_detect("Hello World", "World")    # TRUE
df |> filter(str_detect(name, "Elementary"))

# Does it start/end with?
str_starts("Hello", "He")            # TRUE
str_ends("file.csv", ".csv")         # TRUE

# Count pattern occurrences
str_count("banana", "a")             # 3
df |> mutate(n_digits = str_count(id, "\\d"))
```

### Replacement

```r
# Replace first match
str_replace("Hello World", "World", "R")    # "Hello R"

# Replace all matches
str_replace_all("aaa", "a", "b")            # "bbb"

# Remove pattern (replace with "")
str_remove("prefix_value", "prefix_")       # "value"
str_remove_all("a1b2c3", "\\d")             # "abc"

# Common DAAF patterns
df |> mutate(
  # INTENT: Clean school names for matching
  clean_name = school_name |>
    str_to_lower() |>
    str_replace_all("\\s+", " ") |>
    str_trim()
)
```

### Extraction

```r
# Extract first match
str_extract("Report 2024-Q1", "\\d{4}")     # "2024"

# Extract all matches (returns list)
str_extract_all("a1b2c3", "\\d")            # list("1", "2", "3")

# Extract with capture groups
str_match("John Smith, age 30", "(\\w+) (\\w+), age (\\d+)")
# Returns matrix: [1,] "John Smith, age 30" "John" "Smith" "30"

# In a pipeline
df |> mutate(
  year = str_extract(date_string, "\\d{4}"),
  state_fips = str_extract(fips, "^\\d{2}")
)
```

### Case Transformation

```r
str_to_lower("HELLO")      # "hello"
str_to_upper("hello")      # "HELLO"
str_to_title("hello world") # "Hello World"
str_to_sentence("hello world") # "Hello world"
```

### Trimming and Padding

```r
# Trim whitespace
str_trim("  hello  ")              # "hello"
str_trim("  hello  ", side = "left")   # "hello  "
str_squish("  hello   world  ")    # "hello world" (trim + collapse internal)

# Pad to fixed width
str_pad("42", width = 5, side = "left", pad = "0")   # "00042"
str_pad("hi", width = 10, side = "right")             # "hi        "

# FIPS code padding (common in DAAF)
df |> mutate(
  state_fips = str_pad(state_fips, 2, "left", "0"),
  county_fips = str_pad(county_fips, 3, "left", "0"),
  full_fips = paste0(state_fips, county_fips)
)
```

### Length and Substrings

```r
# String length
str_length("hello")        # 5

# Substring by position (1-indexed, inclusive)
str_sub("abcdef", 1, 3)   # "abc"
str_sub("abcdef", -3)     # "def" (last 3)

# Truncate
str_trunc("A very long string", width = 10)   # "A very ..."

# Word extraction
word("Jane Doe Smith", 1)     # "Jane"
word("Jane Doe Smith", -1)    # "Smith"
```

### Splitting and Concatenation

```r
# Split into pieces
str_split("a,b,c", ",")                # list(c("a", "b", "c"))
str_split_fixed("a,b,c", ",", n = 2)   # matrix: "a" "b,c"

# Concatenation
str_c("hello", "world", sep = " ")     # "hello world"
str_c(c("a", "b"), c("1", "2"))        # c("a1", "b2") (vectorized)

# Collapse vector into single string
str_c(c("a", "b", "c"), collapse = ", ")   # "a, b, c"

# Glue-style interpolation
name <- "World"
str_glue("Hello {name}")   # "Hello World"
```

### Regex Essentials

stringr uses ICU-style regex by default:

| Pattern | Matches |
|---------|---------|
| `\\d` | Digit (0-9) |
| `\\D` | Non-digit |
| `\\w` | Word character (letter, digit, underscore) |
| `\\W` | Non-word character |
| `\\s` | Whitespace |
| `\\S` | Non-whitespace |
| `.` | Any character except newline |
| `^` | Start of string |
| `$` | End of string |
| `[abc]` | Character class |
| `[^abc]` | Negated class |
| `*` | 0 or more |
| `+` | 1 or more |
| `?` | 0 or 1 |
| `{3}` | Exactly 3 |
| `{2,5}` | 2 to 5 |
| `(...)` | Capture group |
| `\\1` | Back-reference |

```r
# Common patterns in education data
str_detect(id, "^\\d{12}$")          # 12-digit NCES school ID
str_extract(fips, "^\\d{2}")          # state FIPS from full FIPS
str_replace_all(name, "[^a-zA-Z ]", "")  # keep only letters and spaces
```

---

## lubridate: Date and Time Operations

### Parsing Dates

lubridate provides flexible parsing functions named after the component order:

```r
library(lubridate)

# Standard formats
ymd("2024-01-15")         # 2024-01-15
ymd("20240115")           # 2024-01-15 (no separators)
ymd("2024/01/15")         # 2024-01-15 (any separator)
mdy("01-15-2024")         # 2024-01-15
dmy("15/01/2024")         # 2024-01-15

# With time
ymd_hms("2024-01-15 14:30:00")
ymd_hm("2024-01-15 14:30")

# Parse in a pipeline
df |> mutate(date = ymd(date_string))
```

The parsing functions are flexible about separators -- `ymd()` handles hyphens,
slashes, spaces, and no separators. This is more forgiving than base R's
`as.Date()` which requires exact format strings.

### Extracting Components

```r
d <- ymd("2024-03-15")

year(d)       # 2024
month(d)      # 3
month(d, label = TRUE)   # "Mar" (ordered factor)
month(d, label = TRUE, abbr = FALSE)   # "March"
day(d)        # 15
wday(d)       # 6 (Friday, 1=Sunday by default)
wday(d, label = TRUE)   # "Fri"
wday(d, week_start = 1)  # 5 (Monday-start: 1=Monday)
yday(d)       # 75 (day of year)
week(d)       # 11
quarter(d)    # 1

# In a pipeline
df |> mutate(
  yr = year(date),
  mo = month(date),
  qtr = quarter(date)
)
```

### Date Arithmetic

```r
d <- ymd("2024-01-15")

# Add/subtract periods
d + days(7)          # 2024-01-22
d + months(1)        # 2024-02-15
d + years(1)         # 2025-01-15
d - weeks(2)         # 2024-01-01

# Duration (exact time)
d + ddays(7)         # exactly 7 * 86400 seconds

# Difference between dates
end <- ymd("2024-06-30")
end - d              # Time difference of 167 days
as.numeric(end - d, units = "days")   # 167

# In a pipeline
df |> mutate(
  next_year = date + years(1),
  days_elapsed = as.numeric(end_date - start_date, units = "days")
)
```

**Periods vs durations:** `months(1)` adds a calendar month (Jan 15 + 1 month =
Feb 15). `dmonths(1)` adds an average month in seconds (30.44 days). Use periods
for calendar arithmetic.

### Rounding and Truncating

```r
d <- ymd("2024-03-15")

floor_date(d, "month")    # 2024-03-01
floor_date(d, "year")     # 2024-01-01
floor_date(d, "week")     # 2024-03-11 (Monday)

ceiling_date(d, "month")  # 2024-04-01
round_date(d, "month")    # 2024-03-01 (rounds to nearest)

# Common: group by month
df |> mutate(month_start = floor_date(date, "month"))
```

### Intervals

```r
# Create an interval
int <- interval(ymd("2024-01-01"), ymd("2024-12-31"))

# Test membership
ymd("2024-06-15") %within% int   # TRUE
ymd("2025-01-01") %within% int   # FALSE

# Duration of an interval
int / days(1)      # number of days
int / months(1)    # number of months (approximate)
```

### Date Sequences

```r
seq(ymd("2024-01-01"), ymd("2024-12-01"), by = "month")
seq(ymd("2024-01-01"), ymd("2024-01-31"), by = "day")
seq(ymd("2015-01-01"), ymd("2024-01-01"), by = "year")
```

### Formatting Dates to Strings

```r
d <- ymd("2024-03-15")

format(d, "%B %d, %Y")     # "March 15, 2024"
format(d, "%Y-%m")          # "2024-03"
format(d, "%m/%d/%Y")       # "03/15/2024"

# Common format codes
# %Y = 4-digit year, %y = 2-digit year
# %m = 2-digit month, %B = full month name, %b = abbreviated
# %d = 2-digit day
# %A = full weekday, %a = abbreviated
```

### Academic Year Convention

Education data often uses academic year start as the year value:

```r
# INTENT: Create academic year label from a date
# ASSUMES: Academic year runs Aug-Jul (e.g., 2020-21 starts Aug 2020)
df |> mutate(
  acad_year = if_else(month(date) >= 8, year(date), year(date) - 1),
  acad_label = paste0(acad_year, "-", str_sub(as.character(acad_year + 1), 3, 4))
)
# Aug 2020 -> acad_year 2020, label "2020-21"
# Mar 2021 -> acad_year 2020, label "2020-21"
```

---

## Combined Patterns

### Clean and Parse Date Strings

```r
# INTENT: Parse messy date column with mixed formats
df |> mutate(
  date_clean = date_string |>
    str_trim() |>
    str_replace_all("/", "-"),
  date = ymd(date_clean)
)
```

### Extract Numeric Values from Text

```r
# INTENT: Extract enrollment from text like "Enrollment: 1,234 students"
df |> mutate(
  enrollment = name |>
    str_extract("[\\d,]+") |>
    str_remove_all(",") |>
    as.integer()
)
```
