# dplyr/tidyr for Polars Users: Core Data Manipulation

> **Companion file:** For string operations (stringr), date/time operations
> (lubridate), and categorical/factor operations (forcats), see
> `strings-dates-factors.md`.

This document provides verb-by-verb translations between Python's polars library
and R's core tidyverse data manipulation packages (dplyr, tidyr). The perspective
is: **you know polars, you are reading R code.**

The fundamental mental model shift: in polars, you build **expressions** that
describe what you want, then apply them inside a context (`select`, `filter`,
`with_columns`, `agg`); in dplyr, you chain **verbs** that act on a data frame
(filter, mutate, summarize) with bare column names. R's approach reads more like
natural language but relies on non-standard evaluation.

> **Versions referenced:**
> R: dplyr 1.2.0, tidyr 1.3.2
> Python: polars 1.38.1
> See SKILL.md § Library Versions for the complete version table.

---

## Section 1: Core dplyr Verbs

### filter -- Subset Rows

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.filter(pl.col("x") > 5)` | `df |> filter(x > 5)` |
| `df.filter((pl.col("x") > 5) & (pl.col("y") < 10))` | `df |> filter(x > 5, y < 10)` |
| `df.filter(pl.col("x").is_in([1, 2, 3]))` | `df |> filter(x %in% c(1, 2, 3))` |
| `df.filter(pl.col("x").is_not_null())` | `df |> filter(!is.na(x))` |
| `df.filter(pl.col("name").str.contains("Smith"))` | `df |> filter(str_detect(name, "Smith"))` |
| `df.filter(pl.col("x").is_between(10, 20))` | `df |> filter(between(x, 10, 20))` |

R uses bare column names and comma-separated conditions (implicit AND).
No parentheses needed around individual conditions in R.

### mutate -- Create or Modify Columns (with_columns)

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.with_columns((pl.col("old") * 2).alias("new"))` | `df |> mutate(new = old * 2)` |
| `df.with_columns(pl.col("x") + 1)` | `df |> mutate(x = x + 1)` |
| `df.with_columns(pl.col("x").cast(pl.Float64))` | `df |> mutate(x = as.numeric(x))` |

R uses `new_name = expression` syntax on the left side. No `.alias()` needed.

**Sequential dependency:** Unlike polars, dplyr's `mutate()` allows referencing
columns created earlier in the same call:

```r
# R -- this works: b uses a defined above
df |> mutate(
  a = x + 1,
  b = a * 2
)
```

```python
# Python -- you know this requires two chained calls
df.with_columns((pl.col("x") + 1).alias("a"))
  .with_columns((pl.col("a") * 2).alias("b"))
```

### select -- Choose Columns

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.select("col1", "col2")` | `df |> select(col1, col2)` |
| `df.select(pl.exclude("col1"))` | `df |> select(-col1)` |
| `df.select(cs.numeric())` | `df |> select(where(is.numeric))` |
| `df.select(cs.starts_with("pop"))` | `df |> select(starts_with("pop"))` |
| `df.select(pl.col("old_name").alias("new_name"))` | `df |> select(new_name = old_name)` |

### arrange / sort -- Sort Rows

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.sort("x")` | `df |> arrange(x)` |
| `df.sort("x", descending=True)` | `df |> arrange(desc(x))` |
| `df.sort("group", "value", descending=[False, True])` | `df |> arrange(group, desc(value))` |

### group_by + agg / summarise

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.group_by("g").agg(pl.col("x").mean().alias("m"))` | `df |> group_by(g) |> summarise(m = mean(x))` |
| `df.group_by("g").agg(pl.len().alias("n"))` | `df |> group_by(g) |> summarise(n = n())` |
| `df.select(pl.col("x").mean().alias("avg"))` | `df |> summarise(avg = mean(x))` |

R's `na.rm = TRUE` parameter is needed to skip NAs in aggregation functions:
`mean(x, na.rm = TRUE)`. Polars skips nulls by default.

### rename

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.rename({"old_name": "new_name"})` | `df |> rename(new_name = old_name)` |

Note the reversed direction: in polars the dict key is the old name; in dplyr
the new name is on the left of `=`.

### unique / distinct

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.unique()` | `df |> distinct()` |
| `df.unique(subset=["col1", "col2"])` | `df |> distinct(col1, col2)` |
| `df.unique(subset=["col1"], keep="first")` | `df |> distinct(col1, .keep_all = TRUE)` |

### count

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.group_by("g").len()` | `df |> count(g)` |
| `df.group_by("g").len().sort("len", descending=True)` | `df |> count(g, sort = TRUE)` |

### pull / get_column

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.get_column("col")` | `df |> pull(col)` |
| `df.get_column("col").to_list()` | `df |> pull(col)` (R vectors are already lists) |

### head / tail / slice

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.head(5)` | `df |> slice_head(n = 5)` |
| `df.tail(5)` | `df |> slice_tail(n = 5)` |
| `df.sort("x", descending=True).head(5)` | `df |> slice_max(x, n = 5)` |
| `df.sample(n=10)` | `df |> slice_sample(n = 10)` |

### concat / bind_rows

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `pl.concat([df1, df2])` | `bind_rows(df1, df2)` |
| `pl.concat([df1, df2], how="horizontal")` | `bind_cols(df1, df2)` |
| `pl.concat([df1, df2], how="diagonal")` | `bind_rows(df1, df2)` (auto-fills missing) |

---

## Section 2: Joins

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df1.join(df2, on="key", how="left")` | `df1 |> left_join(df2, by = "key")` |
| `df1.join(df2, on="key", how="inner")` | `df1 |> inner_join(df2, by = "key")` |
| `df1.join(df2, on="key", how="full")` | `df1 |> full_join(df2, by = "key")` |
| `df1.join(df2, on="key", how="anti")` | `df1 |> anti_join(df2, by = "key")` |
| `df1.join(df2, on="key", how="semi")` | `df1 |> semi_join(df2, by = "key")` |
| `df1.join(df2, how="cross")` | `df1 |> cross_join(df2)` |

**Different key names:**

```python
# Python
df1.join(df2, left_on="a", right_on="b", how="left")
```

```r
# R
df1 |> left_join(df2, by = c("a" = "b"))
```

**Multiple keys:**

```r
# R
df1 |> left_join(df2, by = c("id", "year"))
df1 |> left_join(df2, by = c("id" = "student_id", "year" = "acad_year"))
```

---

## Section 3: Reshaping (tidyr)

### unpivot / pivot_longer

| Python (polars) | R (tidyr) |
|-----------------|-----------|
| `df.unpivot(on=[...], variable_name="name", value_name="val")` | `df |> pivot_longer(cols = c(...), names_to = "name", values_to = "val")` |

### pivot / pivot_wider

| Python (polars) | R (tidyr) |
|-----------------|-----------|
| `df.pivot(on="product", values="sales")` | `df |> pivot_wider(names_from = product, values_from = sales)` |
| `df.pivot(on="product", values="sales", aggregate_function="sum")` | `df |> pivot_wider(names_from = product, values_from = sales, values_fn = sum)` |

### Other tidyr Verbs

| Python (polars) | R (tidyr) |
|-----------------|-----------|
| `pl.col("col").str.split("-").list.get(0)` | `df |> separate(col, into = c("first", "second"), sep = "-")` |
| `pl.concat_str(["col1", "col2"], separator="_")` | `df |> unite(new_col, col1, col2, sep = "_")` |
| `pl.col("x").forward_fill()` | `df |> fill(x, .direction = "down")` |
| `pl.col("x").fill_null(0)` | `df |> replace_na(list(x = 0))` |
| `df.drop_nulls()` | `df |> drop_na()` |
| `df.explode("x")` | `df |> unnest(x)` |

---

## Section 4: across() and Column Selection

R's `across()` applies functions to multiple columns. Polars achieves this with
column selectors (`cs`).

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `df.select(cs.numeric().mean())` | `df |> summarise(across(where(is.numeric), mean))` |
| `df.with_columns(pl.col("x", "y", "z").round(2))` | `df |> mutate(across(c(x, y, z), round, digits = 2))` |

---

## Section 5: Conditional Logic

### case_when / when-then

```python
# Python -- you know this
df.with_columns(
    pl.when(pl.col("x") > 100).then(pl.lit("high"))
      .when(pl.col("x") > 50).then(pl.lit("medium"))
      .otherwise(pl.lit("low"))
      .alias("category")
)
```

```r
# R -- case_when with formula syntax
df |> mutate(
  category = case_when(
    x > 100 ~ "high",
    x > 50  ~ "medium",
    TRUE    ~ "low"
  )
)
```

R uses `condition ~ value` with `~` as the separator. `TRUE ~ default` is the
catch-all (equivalent to `.otherwise()`).

---

## Section 6: Window Functions (.over vs group_by + mutate)

| Python (polars) | R (dplyr) |
|-----------------|-----------|
| `pl.col("x").mean().over("g")` | `df |> group_by(g) |> mutate(group_mean = mean(x))` |
| `pl.col("x").shift(1).over("g")` | `df |> group_by(g) |> mutate(prev_x = lag(x))` |
| `pl.col("x").cum_sum().over("g")` | `df |> group_by(g) |> mutate(running = cumsum(x))` |
| `pl.col("x").rank(method="dense").over("g")` | `df |> group_by(g) |> mutate(rnk = dense_rank(x))` |
| `(pl.col("x") / pl.col("x").sum().over("g"))` | `df |> group_by(g) |> mutate(pct = x / sum(x))` |

Polars uses `.over()` to compute within groups without collapsing rows.
R uses `group_by() |> mutate()` for the same purpose (as opposed to
`group_by() |> summarise()` which collapses).

---

## Section 7: Pipe Operator and Method Chaining

### Full Pipeline Comparison

```python
# Python (polars)
result = (
    df
    .filter(pl.col("year") == 2020)
    .with_columns((pl.col("count") / pl.col("total")).alias("rate"))
    .group_by("state")
    .agg(pl.col("rate").mean().alias("avg_rate"))
    .sort("avg_rate", descending=True)
    .head(10)
)
```

```r
# R (dplyr)
result <- df |>
  filter(year == 2020) |>
  mutate(rate = count / total) |>
  group_by(state) |>
  summarise(avg_rate = mean(rate)) |>
  arrange(desc(avg_rate)) |>
  head(10)
```

Key differences visible in the chain:
- R uses `|>` between steps; Python uses `.` method calls
- R uses bare column names; Python uses `pl.col()`
- R uses `name = expr`; Python uses `.alias("name")`
- R can reference `rate` in the same chain (sequential evaluation)

---

## Section 8: Lazy Evaluation

| Python concept | R concept |
|---------------|-----------|
| Eager mode (default) | Standard dplyr (immediate) |
| `pl.scan_parquet()` + `.collect()` | `arrow::open_dataset()` + `collect()` |
| Query optimizer (predicate/projection pushdown) | dbplyr (database backend) |

R does not have a general lazy evaluation framework for data frames like polars
does. The closest is `arrow::open_dataset()` for Parquet files or `dbplyr` for
database queries, both of which build query plans and execute on `collect()`.

---

## Quick Reference Table

| Python (polars) | R (tidyverse) | Category |
|-----------------|---------------|----------|
| `.select("a", "b")` | `select(a, b)` | Columns |
| `.select(pl.exclude("a"))` | `select(-a)` | Columns |
| `.filter(pl.col("x") > 5)` | `filter(x > 5)` | Rows |
| `.with_columns((pl.col("x") * 2).alias("y"))` | `mutate(y = x * 2)` | Transform |
| `.sort("x", descending=True)` | `arrange(desc(x))` | Sort |
| `.group_by("g").agg(pl.col("x").mean().alias("m"))` | `group_by(g) |> summarise(m = mean(x))` | Aggregate |
| `.with_columns(pl.col("x").mean().over("g").alias("m"))` | `group_by(g) |> mutate(m = mean(x))` | Window |
| `.rename({"old": "new"})` | `rename(new = old)` | Rename |
| `.unique()` | `distinct()` | Deduplicate |
| `.join(df2, on="k", how="left")` | `left_join(df2, by = "k")` | Join |
| `.unpivot(...)` | `pivot_longer(...)` | Reshape |
| `.pivot(...)` | `pivot_wider(...)` | Reshape |
| `pl.when().then().otherwise()` | `case_when(cond ~ val)` | Conditional |
| `.shift(1)` | `lag(x)` | Window |
| Method chaining | `|>` pipe | Pipe |
