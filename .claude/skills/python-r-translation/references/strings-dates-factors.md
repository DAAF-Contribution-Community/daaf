# R String, Date/Time, and Categorical Operations for Polars Users

> **Companion file:** For core data manipulation (dplyr verbs, joins, reshaping,
> window functions, piping), see `dplyr-polars.md`.

This document provides translations between Python's polars library and R's
type-specific tidyverse packages (stringr, lubridate, forcats) for string,
date/time, and categorical operations. The perspective is: **you know polars
.str/.dt namespaces, you are reading R code.**

> **Versions referenced:**
> R: stringr 1.6.0, lubridate 1.9.5, forcats 1.0.1, data.table 1.18.2
> Python: polars 1.39.3
> See SKILL.md § Library Versions for the complete version table.

---

## Section 1: String Operations (polars .str to stringr)

R's `stringr` uses `str_*` prefix functions. Polars uses `.str.*` namespace methods.

### Detection and Matching

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.col("x").str.contains("pat")` | `str_detect(x, "pat")` |
| `pl.col("x").str.starts_with("pre")` | `str_starts(x, "pre")` |
| `pl.col("x").str.ends_with("suf")` | `str_ends(x, "suf")` |
| `pl.col("x").str.count_matches("pat")` | `str_count(x, "pat")` |

### Replacement

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.col("x").str.replace("old", "new")` | `str_replace(x, "old", "new")` |
| `pl.col("x").str.replace_all("old", "new")` | `str_replace_all(x, "old", "new")` |
| `pl.col("x").str.replace("pat", "")` | `str_remove(x, "pat")` |
| `pl.col("x").str.replace_all("pat", "")` | `str_remove_all(x, "pat")` |

### Extraction

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.col("x").str.extract(r"(\d+)", group_index=1)` | `str_extract(x, "\\d+")` |
| `pl.col("x").str.extract_all(r"\d+")` | `str_extract_all(x, "\\d+")` |

R's `str_extract()` returns the full match directly. Polars requires a capture
group and group index.

### Case and Trimming

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.col("x").str.to_lowercase()` | `str_to_lower(x)` |
| `pl.col("x").str.to_uppercase()` | `str_to_upper(x)` |
| `pl.col("x").str.to_titlecase()` | `str_to_title(x)` |
| `pl.col("x").str.strip_chars()` | `str_trim(x)` |
| `pl.col("x").str.strip_chars_start()` | `str_trim(x, "left")` |

### Length and Substrings

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.col("x").str.len_chars()` | `str_length(x)` |
| `pl.col("x").str.slice(0, 3)` | `str_sub(x, 1, 3)` |

Note the indexing: polars uses 0-based offset; R uses 1-based start position.
`str.slice(0, 3)` and `str_sub(x, 1, 3)` both extract the first 3 characters.

### Concatenation and Splitting

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.concat_str(["x", "y"], separator="_")` | `str_c(x, y, sep = "_")` |
| `pl.concat_str(["x", "y"], separator="")` | `paste0(x, y)` |
| `pl.col("x").str.split(",")` | `str_split(x, ",")` |
| `pl.col("x").str.zfill(5)` | `str_pad(x, 5, "left", "0")` |

### Pipeline Comparison

```python
# Python
df = df.with_columns(
    pl.col("name").str.to_lowercase().str.strip_chars()
      .str.replace_all(r"[^a-z ]", "").alias("clean")
)
```

```r
# R
df <- df |> mutate(
  clean = name |> str_to_lower() |> str_trim() |> str_replace_all("[^a-z ]", "")
)
```

---

## Section 2: Date/Time Operations (polars .dt to lubridate)

R's `lubridate` uses intuitive named parsers. Polars uses strftime format strings
and a `.dt` namespace.

### Parsing Dates

| Python (polars) | R (lubridate) |
|-----------------|---------------|
| `pl.col("x").str.to_date("%Y-%m-%d")` | `ymd(x)` |
| `pl.col("x").str.to_date("%m/%d/%Y")` | `mdy(x)` |
| `pl.col("x").str.to_datetime("%Y-%m-%d %H:%M:%S")` | `ymd_hms(x)` |
| `pl.col("x").cast(pl.Date)` | `as_date(x)` |

R's parsers (`ymd`, `mdy`, `dmy`) auto-detect separators. Polars requires exact
format strings.

### Extracting Components

| Python (polars) | R (lubridate) |
|-----------------|---------------|
| `pl.col("x").dt.year()` | `year(x)` |
| `pl.col("x").dt.month()` | `month(x)` |
| `pl.col("x").dt.day()` | `day(x)` |
| `pl.col("x").dt.hour()` | `hour(x)` |
| `pl.col("x").dt.weekday()` | `wday(x)` |
| `pl.col("x").dt.quarter()` | `quarter(x)` |
| `pl.col("x").dt.ordinal_day()` | `yday(x)` |

Weekday numbering differs: polars returns 1=Monday through 7=Sunday (ISO).
R's `wday()` returns 1=Sunday by default (configurable with `week_start`).

### Rounding / Truncating

| Python (polars) | R (lubridate) |
|-----------------|---------------|
| `pl.col("x").dt.truncate("1mo")` | `floor_date(x, "month")` |
| `pl.col("x").dt.truncate("1w")` | `floor_date(x, "week")` |
| `pl.col("x").dt.truncate("1y")` | `floor_date(x, "year")` |

R also has `ceiling_date()` and `round_date()`, which polars lacks as built-ins.

### Date Arithmetic

| Python (polars) | R (lubridate) |
|-----------------|---------------|
| `pl.col("x") + pl.duration(days=5)` | `x + days(5)` |
| `pl.col("x").dt.offset_by("1mo")` | `x + months(1)` |
| `pl.col("x").dt.offset_by("1y")` | `x + years(1)` |
| `(pl.col("x") - pl.col("y")).dt.total_days()` | `as.numeric(x - y, "days")` |

### Creating Date Sequences

```python
# Python
pl.date_range(pl.date(2020, 1, 1), pl.date(2020, 12, 31), interval="1mo", eager=True)
```

```r
# R
seq(as.Date("2020-01-01"), as.Date("2020-12-31"), by = "month")
```

---

## Section 3: Categorical / Factor Operations (polars to forcats)

R's `factor()` creates ordered categorical variables that integrate with modeling.
Polars has `pl.Categorical` and `pl.Enum` for storage optimization.

### Creating

| Python (polars) | R |
|-----------------|---|
| `pl.col("x").cast(pl.Categorical)` | `factor(x)` |
| `pl.Enum(["low", "med", "high"])` | `factor(x, levels = c("low", "med", "high"))` |
| `pl.col("x").to_physical()` | `as.numeric(factor(x))` |
| `pl.col("x").cat.get_categories()` | `levels(x)` |

### Common forcats Operations

| Python (polars) | R (forcats) |
|-----------------|-------------|
| Cast to `pl.Enum(["a", "b", ...])` | `fct_relevel(x, "a", "b")` |
| `.replace({"old": "new"}).cast(pl.Categorical)` | `fct_recode(x, new = "old")` |
| `.replace({"a": "grp", "b": "grp"})` | `fct_collapse(x, grp = c("a", "b"))` |
| Manual: count top-N, replace rest | `fct_lump_n(x, 5)` |
| Reverse the Enum level list | `fct_rev(x)` |
| Sort by frequency then cast to Enum | `fct_infreq(x)` |

---

## Section 4: data.table Sidebar

For Python users who have encountered R's `data.table`, polars' expression model
shares design principles: performance-first, expression-oriented, implicit
optimization, no row index.

| Python (polars) | R (data.table) |
|-----------------|----------------|
| `df.filter(...)` | `DT[i]` (row filter) |
| `df.select(...)` / `df.with_columns(...)` | `DT[, j]` (select/compute) |
| `df.group_by(...).agg(...)` | `DT[, , by]` (group) |
| `df.with_columns(...)` (immutable) | `DT[, x := y * 2]` (modify in place) |
| `df.group_by("g").len()` | `DT[, .N, by = g]` |
| `pl.col("x").shift(1).over("g")` | `DT[, shift(x, 1), by = g]` |
| `df.join(df2, on="key", how="left")` | `DT1[DT2, on = "key"]` |

The main adjustment: polars separates `i`, `j`, and `by` into distinct method
calls (`filter`, `select`/`with_columns`, `group_by`) rather than packing them
into `DT[i, j, by]`.

---

## Quick Reference Table

| Python (polars) | R (tidyverse) | Category |
|-----------------|---------------|----------|
| `.str.contains("p")` | `str_detect(x, "p")` | String |
| `.str.replace_all("a", "b")` | `str_replace_all(x, "a", "b")` | String |
| `.str.extract(r"(\d+)", group_index=1)` | `str_extract(x, "\\d+")` | String |
| `.str.to_lowercase()` | `str_to_lower(x)` | String |
| `.str.strip_chars()` | `str_trim(x)` | String |
| `.str.zfill(5)` | `str_pad(x, 5, "left", "0")` | String |
| `pl.concat_str(["x","y"], separator="_")` | `str_c(x, y, sep = "_")` | String |
| `.dt.year()` | `year(x)` | DateTime |
| `.dt.month()` | `month(x)` | DateTime |
| `.str.to_date("%Y-%m-%d")` | `ymd(x)` | DateTime |
| `.dt.truncate("1mo")` | `floor_date(x, "month")` | DateTime |
| `+ pl.duration(days=7)` | `+ days(7)` | DateTime |
| `.dt.offset_by("1mo")` | `+ months(1)` | DateTime |
| `.cast(pl.Enum([...]))` | `factor(x, levels = ...)` | Categorical |
| `.replace({"old": "new"})` | `fct_recode(x, new = "old")` | Categorical |
| Manual top-N + replace | `fct_lump_n(x, 5)` | Categorical |
