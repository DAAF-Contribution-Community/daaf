# Data Management: Stata to R (dplyr/tidyr)

> **Companion file:** For string operations, date/time operations, and value
> labels / categorical types, see `strings-dates-labels.md`.

Command-by-command translation between Stata's core data management commands
and R's dplyr/tidyr. The fundamental shift: Stata operates on a single implicit
dataset and modifies it in place; R operates on explicitly named data frames and
returns new objects via pipe chains.

> **Versions referenced:** R: dplyr 1.2.0, tidyr 1.3.2, arrow (for parquet I/O)
> See SKILL.md for the complete version table.

---

## Data I/O

| Stata | R | Notes |
|-------|---|-------|
| `use myfile.dta` | `df <- arrow::read_parquet("myfile.parquet")` | DAAF uses parquet exclusively |
| `use var1 var2 using myfile.dta` | `df <- arrow::read_parquet("myfile.parquet", col_select = c("var1", "var2"))` | Column-selective read |
| `save myfile.dta, replace` | `arrow::write_parquet(df, "myfile.parquet")` | DAAF mandate: parquet only |
| `import delimited myfile.csv` | `df <- readr::read_csv("myfile.csv")` | Type-guessing |
| `use "file.dta"` (Stata format) | `df <- haven::read_dta("file.dta")` | Preserves Stata labels as attributes |

---

## Variable Creation and Modification

### generate / mutate

```stata
* Stata
gen newvar = oldvar + 7
gen category = "low" if income < 30000
replace category = "mid" if income >= 30000 & income < 80000
replace category = "high" if income >= 80000
```

```r
# R
df <- df |> mutate(newvar = oldvar + 7)
df <- df |> mutate(
  category = case_when(
    income < 30000 ~ "low",
    income < 80000 ~ "mid",
    TRUE ~ "high"
  )
)
```

### replace / mutate with if_else

```stata
* Stata
replace income = 0 if missing(income)
replace income = income / 1000
```

```r
# R
df <- df |> mutate(income = replace_na(income, 0))
df <- df |> mutate(income = income / 1000)
```

### rename

```stata
rename old new
rename (old1 old2) (new1 new2)
```

```r
df <- df |> rename(new = old)
df <- df |> rename(new1 = old1, new2 = old2)
```

---

## Sample Selection

### keep / drop variables and observations

| Stata | R | Notes |
|-------|---|-------|
| `keep var1 var2 var3` | `df \|> select(var1, var2, var3)` | |
| `keep varstem*` | `df \|> select(starts_with("varstem"))` | |
| `drop var1 var2` | `df \|> select(-var1, -var2)` | |
| `keep if year == 2020` | `df \|> filter(year == 2020)` | |
| `keep if enrollment > 500` | `df \|> filter(enrollment > 500)` | NA excluded automatically |
| `drop if missing(income)` | `df \|> filter(!is.na(income))` or `df \|> drop_na(income)` | |
| `keep if inlist(state, "CA", "NY")` | `df \|> filter(state %in% c("CA", "NY"))` | |
| `keep in 1/10` | `df \|> slice_head(n = 10)` | |
| `keep in -5/l` | `df \|> slice_tail(n = 5)` | |

---

## Sorting

| Stata | R |
|-------|---|
| `sort var1 var2` | `df \|> arrange(var1, var2)` |
| `gsort -var1 var2` | `df \|> arrange(desc(var1), var2)` |

---

## Group Operations

### Window functions (preserves rows -- like `bysort: gen/egen`)

```stata
bysort state: egen mean_score = mean(test_score)
bysort state: gen state_count = _N
bysort state: gen state_obs = _n
```

```r
df <- df |>
  group_by(state) |>
  mutate(
    mean_score = mean(test_score, na.rm = TRUE),
    state_count = n(),
    state_obs = row_number()
  ) |>
  ungroup()
```

### Aggregation (reduces rows -- like `collapse`)

```stata
collapse (mean) test_score (sum) enrollment (count) n=school_id, by(state)
```

```r
state_stats <- df |>
  group_by(state) |>
  summarise(
    test_score = mean(test_score, na.rm = TRUE),
    enrollment = sum(enrollment, na.rm = TRUE),
    n = n()
  )
```

### egen functions mapping

| Stata `egen` | R (inside `group_by \|> mutate`) | Notes |
|--------------|-----------------------------------|-------|
| `egen mean_x = mean(x), by(g)` | `mean(x, na.rm = TRUE)` | |
| `egen sum_x = sum(x), by(g)` | `sum(x, na.rm = TRUE)` | |
| `egen count_x = count(x), by(g)` | `sum(!is.na(x))` | |
| `egen sd_x = sd(x), by(g)` | `sd(x, na.rm = TRUE)` | |
| `egen min_x = min(x), by(g)` | `min(x, na.rm = TRUE)` | |
| `egen max_x = max(x), by(g)` | `max(x, na.rm = TRUE)` | |
| `egen rank_x = rank(x), by(g)` | `rank(x)` or `min_rank(x)` | |

### Row-wise functions

| Stata `egen` | R | Notes |
|--------------|---|-------|
| `egen total = rowtotal(x1 x2 x3)` | `rowSums(pick(x1, x2, x3), na.rm = TRUE)` | Stata treats NA as 0; match with `na.rm = TRUE` |
| `egen avg = rowmean(x1 x2 x3)` | `rowMeans(pick(x1, x2, x3), na.rm = TRUE)` | |

---

## Merging

| Stata | R | Notes |
|-------|---|-------|
| `merge 1:1 key using file2` | `inner_join(df2, by = "key")` | |
| `merge m:1 key using file2` | `left_join(df2, by = "key")` | |
| `merge 1:m key using file2` | `left_join(df2, by = "key")` | |
| `merge ..., keep(3)` | `inner_join(df2, by = "key")` | Matched only |
| `merge ..., keep(1 3)` | `left_join(df2, by = "key")` | Master + matched |

```stata
merge m:1 state_fips using "state_names.dta"
tab _merge
keep if _merge == 3
drop _merge
```

```r
df <- df |> left_join(state_names, by = "state_fips")
```

### Different key names

```r
df <- df |> left_join(states, by = c("stfips" = "state_fips"))
```

### Join types (complete mapping)

| Stata equivalent | R | Description |
|-----------------|---|-------------|
| `merge ..., keep(3)` | `inner_join()` | Only matched rows |
| `merge ..., keep(1 3)` | `left_join()` | All from left + matched |
| `merge ..., keep(2 3)` | `right_join()` | All from right + matched |
| `merge ..., keep(1 2 3)` | `full_join()` | All rows from both |
| (no equivalent) | `anti_join()` | Rows in left NOT in right |
| (no equivalent) | `semi_join()` | Rows in left that HAVE match |

---

## Appending

```stata
append using "file2.dta"
```

```r
df <- bind_rows(df1, df2)
df <- bind_rows(df1, df2, df3)
```

`bind_rows()` handles different column sets automatically (fills missing with
NA), matching Stata's `append` behavior.

---

## Reshaping

### reshape long (wide to long)

```stata
reshape long income, i(id) j(year)
```

```r
df_long <- df |>
  pivot_longer(
    cols = starts_with("income"),
    names_to = "year",
    names_prefix = "income",
    names_transform = list(year = as.integer),
    values_to = "income"
  )
```

### reshape wide (long to wide)

```stata
reshape wide income, i(id) j(year)
```

```r
df_wide <- df |>
  pivot_wider(
    id_cols = id,
    names_from = year,
    names_prefix = "income",
    values_from = income
  )
```

---

## Duplicates

| Stata | R |
|-------|---|
| `duplicates report` | `df \|> count() \|> filter(n > 1)` |
| `duplicates tag key, gen(dup)` | `df \|> add_count(key, name = "dup") \|> mutate(dup = dup - 1)` |
| `duplicates drop` | `df \|> distinct()` |
| `duplicates drop key, force` | `df \|> distinct(key, .keep_all = TRUE)` |

---

## Quick Reference Table

| Stata | R (dplyr/tidyr) | Category |
|-------|-----------------|----------|
| `use myfile.dta` | `arrow::read_parquet("myfile.parquet")` | I/O |
| `save myfile.dta, replace` | `arrow::write_parquet(df, "myfile.parquet")` | I/O |
| `gen newvar = expr` | `mutate(newvar = expr)` | Create |
| `replace var = expr if cond` | `mutate(var = if_else(cond, expr, var))` | Modify |
| `rename old new` | `rename(new = old)` | Rename |
| `keep var1 var2` | `select(var1, var2)` | Columns |
| `drop var1 var2` | `select(-var1, -var2)` | Columns |
| `keep if condition` | `filter(condition)` | Rows |
| `drop if condition` | `filter(!condition)` | Rows |
| `sort var1 var2` | `arrange(var1, var2)` | Sort |
| `gsort -var1 var2` | `arrange(desc(var1), var2)` | Sort |
| `bysort g: egen m = mean(x)` | `group_by(g) \|> mutate(m = mean(x, na.rm = TRUE)) \|> ungroup()` | Window |
| `collapse (mean) x, by(g)` | `group_by(g) \|> summarise(x = mean(x, na.rm = TRUE))` | Aggregate |
| `merge m:1 key using file` | `left_join(df2, by = "key")` | Join |
| `append using file2` | `bind_rows(df1, df2)` | Stack |
| `reshape long stub, i(id) j(t)` | `pivot_longer(cols, names_to, values_to)` | Reshape |
| `reshape wide stub, i(id) j(t)` | `pivot_wider(names_from, values_from)` | Reshape |
| `duplicates drop key, force` | `distinct(key, .keep_all = TRUE)` | Dedup |
| `drop if missing(var)` | `filter(!is.na(var))` or `drop_na(var)` | Missing |
| `destring var, replace` | `mutate(var = as.numeric(var))` | Type |
| `tostring var, replace` | `mutate(var = as.character(var))` | Type |
