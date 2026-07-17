# Strings, Dates, and Labels: Stata to R (stringr/lubridate/forcats)

> **Companion file:** For core data management (generate, replace, keep/drop,
> sorting, group operations, merging, reshaping, collapse, duplicates, missing
> values), see `data-management.md`.

---

## String Operations (stringr)

All R string operations via stringr follow the pattern `str_*(string, pattern)`.

| Stata | R (stringr) | Notes |
|-------|-------------|-------|
| `strpos(s, "pat") > 0` | `str_detect(s, "pat")` | Returns logical |
| `regexm(s, "pat")` | `str_detect(s, "pat")` | Returns logical |
| `subinstr(s, "old", "new", 1)` | `str_replace(s, "old", "new")` | First match |
| `subinstr(s, "old", "new", .)` | `str_replace_all(s, "old", "new")` | All matches |
| `substr(s, 1, 3)` | `str_sub(s, 1, 3)` | Both 1-indexed |
| `regexs(1)` after `regexm` | `str_extract(s, "(pat)")` or `str_match(s, "(pat)")[,2]` | |
| `strlower(s)` | `str_to_lower(s)` | |
| `strupper(s)` | `str_to_upper(s)` | |
| `strproper(s)` | `str_to_title(s)` | |
| `strtrim(s)` | `str_trim(s)` | Both ends |
| `strlen(s)` | `str_length(s)` | Character count |
| `word(s, 1)` | `word(s, 1)` | stringr also has `word()` |
| `s1 + " " + s2` | `paste(s1, s2)` or `paste0(s1, " ", s2)` | |
| `string(n)` | `as.character(n)` | |
| `real(s)` | `as.numeric(s)` | |

```stata
gen clean_name = strproper(strtrim(strlower(name)))
```

```r
df <- df |> mutate(clean_name = str_to_title(str_trim(str_to_lower(name))))
# Or with pipe:
df <- df |> mutate(clean_name = name |> str_to_lower() |> str_trim() |> str_to_title())
```

---

## Date System (lubridate)

Stata dates are integers from 1960-01-01 epoch. R Date objects are integers
from 1970-01-01, but this difference is hidden -- R displays human-readable dates.

| Stata | R (lubridate) | Notes |
|-------|---------------|-------|
| `date("2024-03-15", "YMD")` | `ymd("2024-03-15")` | |
| `date("March 15, 2024", "MDY")` | `mdy("March 15, 2024")` | |
| `mdy(3, 15, 2024)` | `make_date(2024, 3, 15)` | |
| `year(date)` | `year(date)` | |
| `month(date)` | `month(date)` | |
| `day(date)` | `day(date)` | |
| `dow(date)` | `wday(date)` | Stata: 0=Sun; R: 1=Sun by default |
| `quarter(date)` | `quarter(date)` | |
| `mofd(date)` | `floor_date(date, "month")` | |
| `date + 30` | `date + days(30)` | |
| `date + months(1)` | `date %m+% months(1)` | Calendar-aware |
| `date2 - date1` (days) | `as.numeric(date2 - date1)` | |

```stata
gen date = date(date_str, "YMD")
format date %td
gen yr = year(date)
```

```r
df <- df |> mutate(
  date = ymd(date_str),
  yr = year(date)
)
```

---

## Value Labels / Factors (forcats)

R's `factor()` is the direct equivalent of Stata's value label system. The
`forcats` package provides tools for manipulating factor levels.

| Stata | R | Notes |
|-------|---|-------|
| `label define lbl 1 "A" 2 "B"` + `label values var lbl` | `factor(var, levels = c(1,2), labels = c("A","B"))` | |
| `encode strvar, gen(numvar)` | `as.numeric(factor(strvar))` | |
| `decode numvar, gen(strvar)` | `as.character(numvar)` | If already factor |
| `label list lbl` | `levels(var)` | |
| `label values var .` (remove labels) | `as.numeric(as.character(var))` | Remove factor |

### forcats operations

```r
# Reorder levels by frequency (most common first)
df <- df |> mutate(category = fct_infreq(category))

# Lump infrequent levels into "Other"
df <- df |> mutate(category = fct_lump_n(category, n = 5))

# Reverse level order
df <- df |> mutate(category = fct_rev(category))

# Set reference level for regression
df <- df |> mutate(region = relevel(factor(region), ref = "Northeast"))
```

### Key Advantage Over Stata

In Stata, value labels are separate from the variable. In R, factors carry their
level information with them. This means:

- Factor ordering is preserved in plots (ggplot2 respects factor levels)
- Regression reference categories are controlled by factor levels
- No risk of label-variable mismatch

---

## Quick Reference Table

| Stata | R | Category |
|-------|---|----------|
| `substr(s, 1, 3)` | `str_sub(s, 1, 3)` | String |
| `strpos(s, "x")` | `str_detect(s, "x")` | String |
| `subinstr(s, "a", "b", .)` | `str_replace_all(s, "a", "b")` | String |
| `strtrim(s)` | `str_trim(s)` | String |
| `strlower(s)` | `str_to_lower(s)` | String |
| `regexm(s, "pat")` | `str_detect(s, "pat")` | String |
| `date("2024-03-15", "YMD")` | `ymd("2024-03-15")` | Date |
| `mdy(3, 15, 2024)` | `make_date(2024, 3, 15)` | Date |
| `year(date)` | `year(date)` | Date |
| `mofd(date)` | `floor_date(date, "month")` | Date |
| `date + 30` | `date + days(30)` | Date |
| `label define` + `label values` | `factor(var, levels, labels)` | Label |
| `encode strvar` | `as.numeric(factor(strvar))` | Label |
| `i.region` (in regression) | Factor auto-creates dummies | Categorical |
