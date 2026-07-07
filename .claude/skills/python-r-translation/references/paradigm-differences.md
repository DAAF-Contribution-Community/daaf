# Paradigm Differences: Python vs R for Quantitative Social Science

This reference documents the fundamental language and paradigm differences between
Python (with polars) and R as they affect quantitative social science data analysis.
It is the foundational reference that other translation files build upon.

The perspective here is: **you know Python, you are reading R code.** Each section
explains what R does and maps it to the Python concept you already know.

> **Versions referenced:**
> R: R 4.5.3
> Python: Python 3.12, polars 1.38.1
> See SKILL.md § Library Versions for the complete version table.

## Contents

- [Pipe Operator](#pipe-operator)
- [Unquoted Column Names (Non-Standard Evaluation)](#unquoted-column-names-non-standard-evaluation)
- [Missing Values](#missing-values)
- [Indexing](#indexing)
- [Assignment and Mutability](#assignment-and-mutability)
- [Vectorized Operations](#vectorized-operations)
- [Factor / Categorical Handling](#factor--categorical-handling)
- [Type System](#type-system)
- [Package Ecosystem Philosophy](#package-ecosystem-philosophy)
- [Data Frame Philosophy](#data-frame-philosophy)
- [String Handling](#string-handling)
- [Date/Time Handling](#datetime-handling)
- [File I/O](#file-io)
- [Environment and Scoping](#environment-and-scoping)

---

## Pipe Operator

R uses the native pipe `|>` (R 4.1+) to chain operations left-to-right. Python
users know this as method chaining.

```r
# R -- pipe chains verbs left to right
result <- df |>
  filter(year == 2020) |>
  mutate(rate = count / total) |>
  group_by(state) |>
  summarise(avg_rate = mean(rate)) |>
  arrange(desc(avg_rate))
```

```python
# Python -- you know this as method chaining
result = (
    df
    .filter(pl.col("year") == 2020)
    .with_columns((pl.col("count") / pl.col("total")).alias("rate"))
    .group_by("state")
    .agg(pl.col("rate").mean().alias("avg_rate"))
    .sort("avg_rate", descending=True)
)
```

**What you know from Python:** Method chaining with `.filter().with_columns()`.
**What R does:** The pipe `|>` passes the left-hand result as the first argument
to the right-hand function. `df |> filter(x > 5)` is equivalent to `filter(df, x > 5)`.

The older magrittr pipe `%>%` works identically but is being superseded by the
native `|>`. DAAF R code uses `|>` exclusively.

> **Sources:** R Language Definition -- Pipe operator (CRAN, accessed 2026-03-28);
> Wickham et al., *R for Data Science* 2nd ed. (2023)

---

## Unquoted Column Names (Non-Standard Evaluation)

R's tidyverse uses **non-standard evaluation (NSE)**: column names appear as bare
symbols, not strings. This is the single biggest visual difference for Python users.

```r
# R -- bare column names, no quotes needed
df |> filter(year == 2020)
df |> mutate(pct = count / total)
df |> select(state, year, enrollment)
```

```python
# Python -- you know this requires pl.col() and strings
df.filter(pl.col("year") == 2020)
df.with_columns((pl.col("count") / pl.col("total")).alias("pct"))
df.select("state", "year", "enrollment")
```

**What you know from Python:** Every column reference needs `pl.col("name")` or
a string.
**What R does:** Inside tidyverse functions, column names are evaluated as symbols
in the data frame's context. `filter(df, year == 2020)` looks up `year` as a column
of `df`, not as a variable in the environment.

This is called "tidy evaluation" and is unique to R. There is no Python equivalent.
It makes R code shorter and more readable but can be confusing when variable names
shadow column names.

> **Sources:** Wickham, *Advanced R* 2nd ed., Ch. 17-20 (2019);
> rlang documentation -- Data masking (rlang.r-lib.org, accessed 2026-03-28)

---

## Missing Values

R has one unified missing value system. Python has three distinct representations.

### R: Unified NA

R has a single sentinel `NA` with typed variants (`NA_real_`, `NA_character_`,
`NA_integer_`). All share consistent behavior:

- `NA` propagates through arithmetic: `1 + NA` yields `NA`
- `NA` propagates through comparison: `NA == NA` yields `NA` (not `TRUE`)
- Logical short-circuit: `TRUE | NA` yields `TRUE`; `FALSE & NA` yields `FALSE`
- Universal detection: `is.na(x)` works on any type
- Aggregation control: `mean(x, na.rm = TRUE)` skips NAs

### Python: Three Kinds of Missing (What You Know)

| Representation | Scope | Detection | Behavior |
|----------------|-------|-----------|----------|
| `None` | Python-level | `x is None` | Coerced to `null` in polars |
| `float("nan")` / `np.nan` | Float only | `math.isnan(x)` | `NaN + 1 = NaN`; `NaN != NaN` is `True` |
| `null` (polars) | All types | `.is_null()` | Skipped by aggregations |

### Translation

| Python / Polars | R |
|-----------------|---|
| `pl.col("x").is_null()` | `is.na(x)` |
| `pl.col("x").is_not_null()` | `!is.na(x)` |
| Default (nulls skipped) | `na.rm = TRUE` |
| `df.drop_nulls()` | `df |> drop_na()` or `complete.cases(df)` |
| `pl.col("x").fill_null(0)` | `replace_na(x, 0)` or `coalesce(x, 0)` |
| `pl.coalesce("x", "y")` | `coalesce(x, y)` |

**Key insight for Python users:** R's single `NA` is much simpler. You never need
to worry about `NaN` vs `null` vs `None`. Everything is `NA`, and `is.na()` catches
it all.

> **Sources:** R Language Definition -- NA (stat.ethz.ch/R-manual, accessed 2026-03-28);
> Wickham, *Advanced R* 2nd ed., Ch. 3.5.1 (2019)

---

## Indexing

R uses 1-based indexing; Python uses 0-based. This affects vectors, lists,
data frames, and string operations.

| Operation | Python | R |
|-----------|--------|---|
| First element | `x[0]` | `x[1]` |
| First row | `df.head(1)` or `df.row(0)` | `df[1, ]` |
| Rows 1-5 | `df.head(5)` or `df.slice(0, 5)` | `df[1:5, ]` (inclusive both ends) |
| Last element | `x[-1]` | `x[length(x)]` |
| Column by name | `df.select("col")` or `df["col"]` | `df$col` or `df[["col"]]` |

```r
# R -- 1-based, inclusive ranges
x <- c(10, 20, 30, 40)
x[1]       # 10
x[2:4]     # 20, 30, 40 (inclusive on both ends)
```

```python
# Python -- you know this: 0-based, exclusive upper bound
x = [10, 20, 30, 40]
x[0]       # 10
x[1:4]     # [20, 30, 40] (exclusive upper bound)
```

**Key insight for Python users:** R's `x[2:4]` returns elements 2, 3, AND 4. Python's
`x[1:4]` returns elements at indices 1, 2, and 3. Both give three elements but
the convention differs.

> **Sources:** R Language Definition -- Indexing (CRAN, accessed 2026-03-28)

---

## Assignment and Mutability

R uses `<-` for assignment and has copy-on-modify semantics. Python uses `=`
and has reference semantics.

```r
# R -- copy-on-modify: modifying df2 never changes df
df2 <- df
df2$new_col <- 1   # triggers a copy; df is unchanged
```

```python
# Python -- you know this: reference semantics
df2 = df
# modifying df2 can affect df (in pandas)
# polars mitigates this since most ops return new DataFrames
```

**What you know from Python:** `df2 = df` creates an alias. You need `.clone()`
or `.copy()` for an independent copy.
**What R does:** `df2 <- df` creates a shallow copy. The moment you modify `df2`,
R automatically creates a deep copy of the modified portion ("copy-on-modify").
This means mutations are always isolated by default.

> **Sources:** Wickham, *Advanced R* 2nd ed., Ch. 2.3 -- Copy-on-modify (2019)

---

## Vectorized Operations

R implicitly vectorizes nearly all operations. Python's polars requires the
expression system inside a context.

```r
# R -- implicit vectorization, everything "just works"
x <- c(1, 2, 3, 4, 5)
x * 2                          # c(2, 4, 6, 8, 10)
ifelse(x > 3, "high", "low")  # vectorized conditional
df$z <- df$x * 2 + df$y       # direct column arithmetic
```

```python
# Python -- you know this requires expressions in contexts
df = df.with_columns(
    (pl.col("x") * 2).alias("x_doubled"),
    pl.when(pl.col("x") > 3)
      .then(pl.lit("high"))
      .otherwise(pl.lit("low"))
      .alias("category"),
)
```

**Key insight for Python users:** R has no equivalent of `pl.col()`, `.alias()`,
or expression contexts. Column arithmetic works directly with bare names:
`df$z <- df$x * 2` is valid R. The tidyverse version `mutate(z = x * 2)` is
even more concise.

| Python / Polars | R |
|-----------------|---|
| `df.with_columns((pl.col("x") * 2).alias("z"))` | `df |> mutate(z = x * 2)` |
| `pl.when(cond).then(a).otherwise(b)` | `ifelse(cond, a, b)` or `if_else(cond, a, b)` |
| Chained `pl.when().then().when().then().otherwise()` | `case_when(cond1 ~ val1, cond2 ~ val2, TRUE ~ default)` |
| `pl.max_horizontal("x", "y")` | `pmax(x, y)` |
| `pl.col("x").cum_sum()` | `cumsum(x)` |

> **Sources:** R Language Definition -- Vectorized operations (CRAN, accessed 2026-03-28)

---

## Factor / Categorical Handling

R factors are a first-class statistical type with automatic dummy coding in models.
Python categoricals are a storage optimization with no regression integration.

```r
# R -- factors participate directly in modeling
x <- factor(c("low", "med", "high"), levels = c("low", "med", "high"))
lm(y ~ x, data = df)     # auto-creates x[med] and x[high] dummies
contrasts(df$x)           # shows the coding scheme
relevel(x, ref = "med")   # change reference level
```

```python
# Python -- you know Categorical/Enum is for storage, not modeling
df = df.with_columns(pl.col("group").cast(pl.Categorical))
# For modeling, you need C() or i() in formulas:
pf.feols("y ~ C(group)", data=pdf)
```

**Key insight for Python users:** In R, `factor()` creates an object that models
understand natively. When you put a factor in a formula (`y ~ group`), R
auto-generates dummy variables. In Python, you must explicitly wrap categoricals
in `C()` (statsmodels) or `i()` (pyfixest) in the formula string.

> **Sources:** UCLA Statistical Consulting -- Contrast coding (stats.oarc.ucla.edu, accessed 2026-03-28);
> Polars User Guide -- Categorical data and enums (docs.pola.rs, accessed 2026-03-28)

---

## Type System

R coerces types implicitly along a hierarchy. Python and polars require explicit
conversion.

| Behavior | Python / Polars | R |
|----------|-----------------|---|
| Bool + int | `True + 1` = `2` (bool subclasses int) | `TRUE + 1` = `2` |
| Mixed vector | TypeError or explicit cast | `c(1, "a")` = `c("1", "a")` (silent coercion) |
| String to num | `int("5")` or `.cast(pl.Int64)` | `as.numeric("5")` = `5` |

R's coercion hierarchy: logical < integer < double < complex < character.
Mixed types silently promote to the more general type. Python/polars is strict
and requires explicit `.cast()`.

| Python / Polars | R |
|-----------------|---|
| `pl.col("x").cast(pl.Float64)` | `as.numeric(x)` |
| `pl.col("x").cast(pl.Int64)` | `as.integer(x)` |
| `pl.col("x").cast(pl.Utf8)` | `as.character(x)` |
| `pl.col("x").cast(pl.Boolean)` | `as.logical(x)` |

> **Sources:** R Language Definition -- Coercion (CRAN, accessed 2026-03-28)

---

## Package Ecosystem Philosophy

Python packages are specialized, requiring composition of multiple libraries.
R packages are comprehensive toolkits covering broad functionality.

```r
# R -- one package (fixest) does everything
library(fixest)
feols(y ~ x1 | fe1, data = df)       # OLS with FE
fepois(y ~ x1 | fe1, data = df)      # Poisson with FE
feols(y ~ x1 | fe1 | endog ~ z1)     # IV
etable(m1, m2, m3)                    # publication table
iplot(model)                          # coefficient plot
```

The same coverage in Python requires multiple packages:

| Python (DAAF) | R (single package) | Coverage |
|---------------|--------------------|----------|
| `pf.feols()` | `fixest::feols()` | OLS/FE/IV/Poisson |
| `pf.etable()` | `fixest::etable()` | Regression tables |
| `pf.did2s()` | `did2s::did2s()` (separate package in R too) | Two-stage DiD |
| `svy` | `survey::svyglm()` | Survey-weighted |
| `statsmodels.MixedLM` | `lme4::lmer()` | Mixed effects |

**Key insight for Python users:** R scripts typically have 2-3 `library()` calls
to cover what would require 6-10 `import` statements in Python. This consolidation
is normal in R. Do not be surprised to see `library(fixest)` providing OLS, IV,
Poisson, DiD, tables, and plots -- all from one package.

> **Sources:** fixest CRAN vignette (cran.r-project.org, accessed 2026-03-28)

---

## Data Frame Philosophy

R uses one data frame type everywhere. Python's DAAF stack uses polars for
wrangling but must convert to pandas for most modeling packages.

```r
# R -- same tibble everywhere: wrangle, model, plot
df |> filter(x > 2) |> mutate(z = x * 2)
lm(z ~ x, data = df)
ggplot(df, aes(x, z)) + geom_point()
```

```python
# Python -- you know the polars-pandas boundary
df = pl.read_parquet("data.parquet")        # polars for wrangling
df = df.filter(pl.col("x") > 2)
pdf = df.to_pandas()                         # convert for modeling
model = smf.ols("z ~ x", data=pdf).fit()    # statsmodels needs pandas
```

**Key insight for Python users:** In R, there is no data frame conversion step.
The same tibble/data.frame passes through `dplyr |>` wrangling, `lm()` modeling,
and `ggplot()` visualization without conversion. This is one of R's major
ergonomic advantages.

> **Sources:** Wickham & Grolemund, *R for Data Science* 2nd ed. -- Tibbles (2023)

---

## String Handling

R's `stringr` uses `str_*` prefix functions; polars uses `.str.*` namespace methods.

| Python (polars) | R (stringr) |
|-----------------|-------------|
| `pl.col("x").str.contains("abc")` | `str_detect(x, "abc")` |
| `pl.col("x").str.replace("old", "new")` | `str_replace(x, "old", "new")` |
| `pl.col("x").str.replace_all("old", "new")` | `str_replace_all(x, "old", "new")` |
| `pl.col("x").str.extract(r"(\d+)", 1)` | `str_extract(x, "\\d+")` |
| `pl.col("x").str.to_lowercase()` | `str_to_lower(x)` |
| `pl.col("x").str.strip_chars()` | `str_trim(x)` |
| `pl.col("x").str.len_chars()` | `str_length(x)` |
| `pl.concat_str(["x", "y"], separator="_")` | `str_c(x, y, sep = "_")` |

> **Sources:** Wickham, *R for Data Science* 2nd ed., Ch. 14 (2023)

---

## Date/Time Handling

R's `lubridate` uses intuitive named parsers. Polars uses strftime format strings.

| Python (polars) | R (lubridate) |
|-----------------|---------------|
| `pl.col("d").str.to_date("%Y-%m-%d")` | `ymd("2024-01-15")` |
| `pl.col("date").dt.year()` | `year(date)` |
| `pl.col("date").dt.month()` | `month(date)` |
| `pl.col("date").dt.truncate("1mo")` | `floor_date(date, "month")` |
| `(pl.col("d2") - pl.col("d1")).dt.total_days()` | `difftime(d2, d1, units = "days")` |
| `pl.col("date") + pl.duration(days=30)` | `date + days(30)` |

**Key insight for Python users:** R's `ymd()`, `mdy()`, `dmy()` auto-detect
separators. Polars requires an explicit format string. R's date handling is
more forgiving and intuitive.

> **Sources:** Grolemund & Wickham, *R for Data Science* 2nd ed., Ch. 17 (2023)

---

## File I/O

Both ecosystems handle common formats. DAAF standardizes on parquet.

| Python / Polars | R |
|-----------------|---|
| `pl.read_csv()` | `readr::read_csv()` |
| `pl.read_parquet()` | `arrow::read_parquet()` |
| `pl.scan_parquet()` | `arrow::open_dataset()` |
| `pd.read_stata()` | `haven::read_dta()` |
| `pl.read_excel()` | `readxl::read_excel()` |

**DAAF convention:** All data stored in parquet format. No CSV, no Excel.

> **Sources:** Polars User Guide -- I/O (docs.pola.rs, accessed 2026-03-28);
> arrow R package docs (arrow.apache.org, accessed 2026-03-28)

---

## Environment and Scoping

Python uses explicit module imports with namespace prefixes. R attaches packages
to a global search path.

```python
# Python -- you know this: explicit imports, namespaced access
import polars as pl
import pyfixest as pf

df = df.filter(pl.col("x") > 5)
model = pf.feols("y ~ x", data=pdf)
```

```r
# R -- library() makes all exports available unqualified
library(dplyr)
df |> filter(x > 5) |> mutate(y = str_to_lower(name))

# Name collisions resolved by load order (last wins)
library(dplyr)    # exports filter()
library(stats)    # also exports filter() -- masks dplyr::filter()
dplyr::filter(df, x > 5)  # disambiguate with explicit namespace
```

**Key insight for Python users:** After `library(dplyr)`, you type `filter()`
directly -- no `dplyr.filter()` needed. This is like `from dplyr import *` in
Python, which is generally discouraged in Python but is standard practice in R.
The downside is name collisions, which R resolves by "last loaded wins" or
explicit namespacing with `::`.

| Python | R |
|--------|---|
| `import polars as pl` | `library(dplyr)` |
| `import pyfixest as pf` | `library(fixest)` |
| `from plotnine import *` | `library(ggplot2)` |
| Always namespaced | Bare names after `library()` |
| Module-level scope | `.GlobalEnv` |

> **Sources:** R Language Definition -- Scope (CRAN, accessed 2026-03-28);
> Wickham, *R Packages* 2nd ed., Ch. 10 (2023)
