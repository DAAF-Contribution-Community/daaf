# Stata-to-Python Command Mappings: Research Compilation

**Date:** 2026-03-28
**Purpose:** Comprehensive research on Stata command-to-Python equivalents for social science data analysis, organized by command category. This document will inform a DAAF `stata-python-translation` skill parallel to the existing `r-python-translation` skill.

**DAAF Python Stack References:** polars (data management), pyfixest (fixed effects regression), statsmodels (general modeling), linearmodels (panel/IV/SUR), plotnine (static visualization), plotly (interactive visualization), svy (complex surveys), rdrobust (regression discontinuity), marginaleffects (post-estimation interpretation), scikit-learn (ML/matching workarounds).

---

## Table of Contents

1. [Data Management Commands](#1-data-management-commands)
2. [Estimation Commands](#2-estimation-commands)
3. [Causal Inference Commands](#3-causal-inference-commands)
4. [Survey Commands](#4-survey-commands)
5. [Output and Visualization](#5-output-and-visualization)
6. [Programming Commands](#6-programming-commands)
7. [Key Paradigm Differences](#7-key-paradigm-differences)
8. [Source Catalog](#8-source-catalog)

---

## 1. Data Management Commands

### 1.1 Data I/O: `use`, `save`, `import delimited`, `export delimited`

| Stata | Python (polars) | Python (pandas) | Notes |
|-------|----------------|-----------------|-------|
| `use myfile.dta` | `df = pl.read_parquet("myfile.parquet")` | `df = pd.read_stata("myfile.dta")` | DAAF uses parquet exclusively; polars can also read .dta via `pl.read_csv` after conversion but native .dta reading requires pandas or pyreadstat |
| `use var1 var2 using myfile.dta` | `df = pl.read_parquet("myfile.parquet", columns=["var1", "var2"])` | `df = pd.read_stata("myfile.dta", columns=["var1", "var2"])` | Column-selective read |
| `save myfile.dta, replace` | `df.write_parquet("myfile.parquet")` | `df.to_stata("myfile.dta")` | DAAF mandate: parquet only |
| `import delimited myfile.csv` | `df = pl.read_csv("myfile.csv")` | `df = pd.read_csv("myfile.csv")` | polars infers types aggressively; use `dtypes` parameter to override |
| `import delimited myfile.csv, delimiters("\t")` | `df = pl.read_csv("myfile.csv", separator="\t")` | `df = pd.read_csv("myfile.csv", sep="\t")` | Tab-delimited |
| `export delimited myfile.csv` | `df.write_csv("myfile.csv")` | `df.to_csv("myfile.csv")` | |
| `import excel myfile.xlsx` | `df = pl.read_excel("myfile.xlsx")` | `df = pd.read_excel("myfile.xlsx")` | polars requires `xlsx2csv` or `openpyxl` backend |

**Reading .dta files into polars (bridge pattern):**
```python
# Option 1: via pyreadstat (preserves Stata metadata including value labels)
import pyreadstat
df_pd, meta = pyreadstat.read_dta("myfile.dta")
df = pl.from_pandas(df_pd)
# meta.variable_value_labels contains the Stata value label mappings

# Option 2: via pandas bridge
df = pl.from_pandas(pd.read_stata("myfile.dta"))
```

**Key behavioral differences:**
- Stata loads one dataset into memory at a time. Python can hold arbitrarily many DataFrames simultaneously as separate variables. This eliminates the need for `preserve`/`restore` and `tempfile`.
- Stata's `.dta` format embeds variable labels, value labels, and format specifications. Parquet does not. Store metadata in documentation or a companion schema file.
- `pyreadstat` (Roche, open source, GitHub) reads .dta files with full metadata extraction including extended missing values (`.a`-`.z`), value labels, variable labels, and formats.

**Sources:** pandas documentation, "Comparison with Stata" (pandas.pydata.org/docs, accessed 2026-03-28); polars User Guide (docs.pola.rs, accessed 2026-03-28); pyreadstat (github.com/Roche/pyreadstat, accessed 2026-03-28).

---

### 1.2 Variable Creation and Modification: `generate`, `replace`, `rename`, `drop`, `keep`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `generate newvar = expr` | `df = df.with_columns(expr.alias("newvar"))` | polars expressions are lazy; `.alias()` names the result |
| `generate newvar = oldvar + 7` | `df = df.with_columns((pl.col("oldvar") + 7).alias("newvar"))` | |
| `generate newvar = expr if condition` | `df = df.with_columns(pl.when(condition).then(expr).otherwise(None).alias("newvar"))` | Stata sets unmet rows to missing; polars uses `when/then/otherwise` |
| `replace var = expr if condition` | `df = df.with_columns(pl.when(condition).then(expr).otherwise(pl.col("var")).alias("var"))` | Must handle the else case explicitly |
| `replace var = expr` | `df = df.with_columns(expr.alias("var"))` | Overwrites the column entirely |
| `rename old new` | `df = df.rename({"old": "new"})` | Dictionary-based; can rename multiple at once |
| `drop var1 var2` | `df = df.drop("var1", "var2")` | |
| `drop if condition` | `df = df.filter(~condition)` | Note the negation — `drop if` becomes `filter(NOT condition)` |
| `keep var1 var2` | `df = df.select("var1", "var2")` | |
| `keep if condition` | `df = df.filter(condition)` | |
| `keep varstem*` | `df = df.select(cs.starts_with("varstem"))` | Requires `import polars.selectors as cs` |
| `drop varstem*` | `df = df.select(~cs.starts_with("varstem"))` | Negate the selector with `~` |

**Conditional generation pattern (detailed):**

Stata:
```stata
generate category = "low" if income < 30000
replace category = "mid" if income >= 30000 & income < 80000
replace category = "high" if income >= 80000
```

Polars:
```python
df = df.with_columns(
    pl.when(pl.col("income") < 30000).then(pl.lit("low"))
      .when(pl.col("income") < 80000).then(pl.lit("mid"))
      .otherwise(pl.lit("high"))
      .alias("category")
)
```

**Key behavioral differences:**
- Stata modifies data in place; polars returns new DataFrames (immutable by design). Always reassign: `df = df.with_columns(...)`.
- Stata's `generate var = expr if condition` sets unmet rows to `.` (missing). In polars, use `pl.when(...).then(...).otherwise(None)` to replicate this behavior.
- Stata allows referencing the column being created in subsequent `replace` calls within the same do-file block. Polars `with_columns` cannot reference a column created in the same call.

**Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com, accessed 2026-03-28); Turrell, "Coming from Stata" in *Coding for Economists* (aeturrell.github.io, accessed 2026-03-28); pandas "Comparison with Stata" (pandas.pydata.org, accessed 2026-03-28); polars User Guide (docs.pola.rs, accessed 2026-03-28).

---

### 1.3 Sorting: `sort`, `gsort`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `sort var1 var2` | `df = df.sort("var1", "var2")` | Ascending by default |
| `gsort -var1 var2` | `df = df.sort("var1", "var2", descending=[True, False])` | `gsort` allows mixed sort order; polars uses `descending` list |
| `gsort -var1 -var2` | `df = df.sort("var1", "var2", descending=True)` | Scalar `True` applies to all |

**Key behavioral difference:** Stata sorts in place. Polars returns a new DataFrame; must reassign.

**Sources:** polars User Guide (docs.pola.rs, accessed 2026-03-28); pandas "Comparison with Stata" (pandas.pydata.org, accessed 2026-03-28).

---

### 1.4 Group Operations: `by:`, `bysort:`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `bysort group: gen total = sum(var)` | `df = df.with_columns(pl.col("var").sum().over("group").alias("total"))` | `.over()` is the polars window function (like SQL PARTITION BY) |
| `bysort group: gen mean_v = mean(var)` | `df = df.with_columns(pl.col("var").mean().over("group").alias("mean_v"))` | |
| `bysort group: gen n = _N` | `df = df.with_columns(pl.len().over("group").alias("n"))` | `_N` = group count |
| `bysort group: gen seq = _n` | `df = df.with_columns(pl.int_range(pl.len()).over("group").alias("seq"))` | `_n` = row number within group (1-based in Stata, 0-based in polars) |
| `bysort group (sort_var): keep if _n==1` | `df = df.sort("sort_var").group_by("group").first()` | Keep first obs per group after sorting |
| `bysort group (sort_var): keep if _n==_N` | `df = df.sort("sort_var").group_by("group").last()` | Keep last obs per group |
| `bysort group (sort_var): gen lag_v = var[_n-1]` | `df = df.sort("sort_var").with_columns(pl.col("var").shift(1).over("group").alias("lag_v"))` | Lagged values within group |

**The `by:` paradigm mapping:**

Stata's `by:` prefix is a split-apply-combine operation. In polars, this maps to two distinct patterns:
1. **Aggregation** (reduces rows): `df.group_by("group").agg(...)` -- equivalent to `collapse` or `by: egen` when creating summary statistics.
2. **Window functions** (preserves rows): `.over("group")` within `with_columns()` -- equivalent to `by: gen` or `by: replace` where the result broadcasts back to each row.

**Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com, accessed 2026-03-28); Turrell, "Coming from Stata" (aeturrell.github.io, accessed 2026-03-28); polars User Guide, "Window functions" (docs.pola.rs, accessed 2026-03-28).

---

### 1.5 Merging: `merge`, `append`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `merge 1:1 key using file2` | `df = df1.join(df2, on="key", how="inner")` | Default is inner join in polars |
| `merge m:1 key using file2` | `df = df1.join(df2, on="key", how="left")` | Many-to-one: left join typically desired |
| `merge 1:m key using file2` | `df = df1.join(df2, on="key", how="left")` | One-to-many: left join with df1 as the "one" side |
| `merge m:m key using file2` | `df = df1.join(df2, on="key", how="cross")` or conditional | Stata's m:m merge is unusual and rarely correct; avoid |
| `append using file2` | `df = pl.concat([df1, df2])` | Row-wise concatenation |
| `merge ..., keep(3)` | `df = df1.join(df2, on="key", how="inner")` | `_merge==3` = matched in both; same as inner join |
| `merge ..., keep(1 3)` | `df = df1.join(df2, on="key", how="left")` | Left join keeps all from master |

**Key behavioral differences:**
- Stata's `merge` creates a `_merge` variable (1=master only, 2=using only, 3=matched). Polars does not create a merge indicator automatically. To replicate, add an indicator column before joining:
  ```python
  df1 = df1.with_columns(pl.lit(True).alias("_in_master"))
  df2 = df2.with_columns(pl.lit(True).alias("_in_using"))
  df = df1.join(df2, on="key", how="outer")
  ```
- Stata requires one dataset in memory and merges from a file on disk. Python merges two in-memory DataFrames.
- Stata requires both datasets to be sorted on the merge key. Polars does not require pre-sorting.
- Multiple merge keys: Stata `merge 1:1 key1 key2 using ...` becomes `df1.join(df2, on=["key1", "key2"], how=...)`.

**Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com, accessed 2026-03-28); pandas "Comparison with Stata" (pandas.pydata.org, accessed 2026-03-28); polars User Guide, "Joins" (docs.pola.rs, accessed 2026-03-28).

---

### 1.6 Reshaping: `reshape long`, `reshape wide`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `reshape long stub, i(id) j(time)` | `df = df.unpivot(on=[col_list], index="id", variable_name="time", value_name="stub")` | polars `unpivot()` (formerly `melt()`) is the wide-to-long operation |
| `reshape wide stub, i(id) j(time)` | `df = df.pivot(on="time", index="id", values="stub")` | polars `pivot()` is the long-to-wide operation |

**Detailed reshape long example:**

Stata:
```stata
* Data has: id income2018 income2019 income2020
reshape long income, i(id) j(year)
* Now has: id year income
```

Polars:
```python
# Identify the stub columns
income_cols = [c for c in df.columns if c.startswith("income")]
df_long = df.unpivot(
    on=income_cols,
    index="id",
    variable_name="year",
    value_name="income",
)
# Clean the year column: "income2018" -> 2018
df_long = df_long.with_columns(
    pl.col("year").str.replace("income", "").cast(pl.Int32)
)
```

**Detailed reshape wide example:**

Stata:
```stata
* Data has: id year income
reshape wide income, i(id) j(year)
* Now has: id income2018 income2019 income2020
```

Polars:
```python
df_wide = df.pivot(on="year", index="id", values="income")
# Optionally prefix column names
df_wide = df_wide.rename({str(y): f"income{y}" for y in df_wide.columns if y != "id"})
```

**Key behavioral difference:** Stata's `reshape` modifies data in place and remembers the reshape specification for reversal. Polars `unpivot`/`pivot` return new DataFrames with no memory of the previous shape.

**Sources:** polars User Guide, "Pivots" (docs.pola.rs, accessed 2026-03-28); pandas "Comparison with Stata" (pandas.pydata.org, accessed 2026-03-28); QuantEcon Statistics Cheatsheet (cheatsheets.quantecon.org, accessed 2026-03-28).

---

### 1.7 Aggregation: `collapse`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `collapse (mean) var1, by(group)` | `df = df.group_by("group").agg(pl.col("var1").mean())` | |
| `collapse (sum) var1 (mean) var2, by(group)` | `df = df.group_by("group").agg(pl.col("var1").sum(), pl.col("var2").mean())` | Multiple aggregations |
| `collapse (sd) var1 (median) var2 (min) var3 (max) var4, by(group)` | `df = df.group_by("group").agg(pl.col("var1").std(), pl.col("var2").median(), pl.col("var3").min(), pl.col("var4").max())` | |
| `collapse (count) var1, by(group)` | `df = df.group_by("group").agg(pl.col("var1").count())` | `count()` excludes nulls in polars |
| `collapse (first) var1, by(group)` | `df = df.group_by("group").agg(pl.col("var1").first())` | |
| `collapse (p25) var1 (p75) var2, by(group)` | `df = df.group_by("group").agg(pl.col("var1").quantile(0.25), pl.col("var2").quantile(0.75))` | |

**Key behavioral differences:**
- Stata's `collapse` destroys the original data (reduces to group-level). Polars `group_by().agg()` returns a new DataFrame; the original is preserved.
- Stata's `collapse` without `by()` collapses to a single row. Polars: `df.select(pl.col("var1").mean())` or `df.agg(pl.col("var1").mean())`.
- Naming: Stata keeps the original variable name. Polars keeps the original column name by default but can be renamed with `.alias()`.

**Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com, accessed 2026-03-28); Turrell, "Coming from Stata" (aeturrell.github.io, accessed 2026-03-28).

---

### 1.8 Value Labels: `encode`, `decode`, `label define`, `label values`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `encode strvar, gen(numvar)` | `df = df.with_columns(pl.col("strvar").cast(pl.Categorical).to_physical().alias("numvar"))` | Creates integer codes from string; polars Categorical stores the mapping |
| `decode numvar, gen(strvar)` | Use a dictionary mapping or original Categorical | No direct equivalent; must maintain mapping externally |
| `label define lblname 1 "Low" 2 "Mid" 3 "High"` | `mapping = {1: "Low", 2: "Mid", 3: "High"}` | Python uses dictionaries for label mappings |
| `label values var lblname` | `df = df.with_columns(pl.col("var").replace(mapping).alias("var_labeled"))` | Apply the mapping dictionary |

**Polars Categorical and Enum types:**

```python
# Categorical: order determined at runtime (like Stata's encode)
df = df.with_columns(pl.col("region").cast(pl.Categorical))

# Enum: order defined in advance (like Stata's label define + label values)
region_dtype = pl.Enum(["Northeast", "South", "Midwest", "West"])
df = df.with_columns(pl.col("region").cast(region_dtype))
```

**Reading Stata value labels:**
```python
import pyreadstat
df_pd, meta = pyreadstat.read_dta("data.dta")
# meta.variable_value_labels is a dict: {"varname": {1: "label1", 2: "label2", ...}}
# meta.column_names_to_labels maps variable names to variable labels
```

**Key behavioral differences:**
- Stata's value label system is built into the data format: labels travel with the data, appear in output, and are stored in the .dta file. Python has no built-in equivalent. Labels must be managed as metadata dictionaries or via `pl.Enum`/`pl.Categorical` types.
- Stata sorts missing values as greater than all numeric values. Polars sorts nulls last by default (configurable with `nulls_last` parameter).

**Sources:** polars User Guide, "Categorical data and enums" (docs.pola.rs, accessed 2026-03-28); pyreadstat (github.com/Roche/pyreadstat, accessed 2026-03-28); pandas "Categorical data" documentation (pandas.pydata.org, accessed 2026-03-28).

---

### 1.9 `egen` Functions

| Stata `egen` Function | Python (polars) | Notes |
|----------------------|----------------|-------|
| `egen newvar = mean(var), by(group)` | `df.with_columns(pl.col("var").mean().over("group").alias("newvar"))` | Window function pattern |
| `egen newvar = sum(var), by(group)` | `df.with_columns(pl.col("var").sum().over("group").alias("newvar"))` | |
| `egen newvar = count(var), by(group)` | `df.with_columns(pl.col("var").count().over("group").alias("newvar"))` | Excludes nulls |
| `egen newvar = sd(var), by(group)` | `df.with_columns(pl.col("var").std().over("group").alias("newvar"))` | polars uses N-1 denominator by default |
| `egen newvar = min(var), by(group)` | `df.with_columns(pl.col("var").min().over("group").alias("newvar"))` | |
| `egen newvar = max(var), by(group)` | `df.with_columns(pl.col("var").max().over("group").alias("newvar"))` | |
| `egen newvar = median(var), by(group)` | `df.with_columns(pl.col("var").median().over("group").alias("newvar"))` | |
| `egen newvar = total(var)` | `df.with_columns(pl.col("var").sum().alias("newvar"))` | Without `by()`, applies to full column |
| `egen newvar = group(var1 var2)` | `df.with_columns(pl.struct("var1", "var2").rank("dense").alias("newvar"))` | Creates sequential group IDs; approximate equivalent |
| `egen newvar = tag(var1 var2)` | `df.with_columns((pl.int_range(pl.len()).over("var1", "var2") == 0).cast(pl.Int32).alias("newvar"))` | Tags first occurrence per group (1/0) |
| `egen newvar = rowtotal(var1 var2 var3)` | `df.with_columns(pl.sum_horizontal("var1", "var2", "var3").alias("newvar"))` | Row-wise sum; note `rowtotal` treats missing as 0 in Stata |
| `egen newvar = rowmean(var1 var2 var3)` | `df.with_columns(pl.mean_horizontal("var1", "var2", "var3").alias("newvar"))` | Row-wise mean |
| `egen newvar = rowmin(var1 var2 var3)` | `df.with_columns(pl.min_horizontal("var1", "var2", "var3").alias("newvar"))` | Row-wise minimum |
| `egen newvar = rowmax(var1 var2 var3)` | `df.with_columns(pl.max_horizontal("var1", "var2", "var3").alias("newvar"))` | Row-wise maximum |
| `egen bins = cut(var), group(5)` | `df.with_columns(pl.col("var").qcut(5).alias("bins"))` | Quantile-based binning |

**Key behavioral differences:**
- Stata's `egen rowtotal()` treats missing values as zeros by default. Polars' `pl.sum_horizontal()` propagates nulls. To replicate Stata behavior: `pl.sum_horizontal(pl.col("var1").fill_null(0), pl.col("var2").fill_null(0), pl.col("var3").fill_null(0))`.
- Stata's `egen group()` creates sequential integers 1, 2, 3, ... for distinct group combinations. The polars equivalent using `rank("dense")` on a struct is approximate; for exact replication, use `.group_by().agg()` to create a lookup table, then join.

**Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com, accessed 2026-03-28); Stata `egen` manual (stata.com/manuals/degen.pdf); polars User Guide (docs.pola.rs, accessed 2026-03-28).

---

### 1.10 Type Conversion: `tostring`, `destring`

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `destring var, replace` | `df = df.with_columns(pl.col("var").cast(pl.Float64))` | Converts string to float |
| `destring var, gen(numvar)` | `df = df.with_columns(pl.col("var").cast(pl.Float64).alias("numvar"))` | Creates new numeric column |
| `destring var, replace force` | `df = df.with_columns(pl.col("var").cast(pl.Float64, strict=False))` | `strict=False` coerces invalid to null (like Stata's `force`) |
| `tostring var, replace` | `df = df.with_columns(pl.col("var").cast(pl.Utf8))` | Converts numeric to string |
| `tostring var, gen(strvar) format(%9.2f)` | `df = df.with_columns(pl.col("var").round(2).cast(pl.Utf8).alias("strvar"))` | Formatted string conversion |

**Key behavioral difference:** Stata's `destring` will fail if non-numeric characters are present unless `force` is specified (which sets those to `.`). Polars' `cast(pl.Float64, strict=False)` sets unparseable values to `null`.

**Sources:** Stata `destring` manual (stata.com/manuals/ddestring.pdf); polars User Guide, "Casting" (docs.pola.rs, accessed 2026-03-28).

---

### 1.11 Missing Value Handling

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `.` (system missing) | `None` / `null` | polars uses typed `null`; pandas uses `NaN` or `pd.NA` |
| `.a` through `.z` (extended missing) | No direct equivalent | Must encode as metadata or sentinel values |
| `missing(var)` | `pl.col("var").is_null()` | Test for missing |
| `!missing(var)` | `pl.col("var").is_not_null()` | Test for non-missing |
| `var == .` | `pl.col("var").is_null()` | **Never** use `== None` in Python |
| `replace var = 0 if missing(var)` | `df = df.with_columns(pl.col("var").fill_null(0))` | Fill missing with value |
| `drop if missing(var)` | `df = df.filter(pl.col("var").is_not_null())` or `df = df.drop_nulls("var")` | |
| `mvdecode var, mv(-9 -99)` | `df = df.with_columns(pl.when(pl.col("var").is_in([-9, -99])).then(None).otherwise(pl.col("var")).alias("var"))` | Recode sentinel values to null |

**Critical behavioral differences:**

1. **Missing value ordering:** In Stata, `.` (and `.a`-`.z`) sort as **greater than all numeric values**. In polars, `null` sorts **last** by default. This can affect operations like `keep if var < threshold` where missing observations behave differently.

2. **Missing value propagation:** In Stata, any operation involving `.` returns `.`. In polars, null propagation follows similar rules, but `NaN` (which is distinct from `null` in polars float columns) behaves differently: `NaN` propagates through arithmetic but is NOT detected by `.is_null()`. Use `.is_nan()` to detect NaN specifically.

3. **Extended missing values (.a-.z):** Stata supports 27 distinct missing values (`.`, `.a`-`.z`) that can encode reasons for missingness. Python/polars has no built-in equivalent. Strategies:
   - Use a separate string column to encode the missing reason
   - Use `pyreadstat` with `user_missing=True` when reading .dta files to preserve extended missing metadata
   - Store a missingness codebook in the project documentation

4. **NaN vs null in polars:** polars distinguishes between `null` (typed missing) and `NaN` (IEEE 754 float). When reading from Stata files via pandas, missing values may arrive as `NaN`. Convert with: `df = df.with_columns(pl.when(pl.col("var").is_nan()).then(None).otherwise(pl.col("var")).alias("var"))`.

**Sources:** pandas "Working with missing data" documentation (pandas.pydata.org, accessed 2026-03-28); polars documentation, "Handling Missing Values" (docs.pola.rs, accessed 2026-03-28); "NaN vs Null in pandas & Polars" (dontusethiscode.com, Jan 2025); pyreadstat documentation (github.com/Roche/pyreadstat).

---

## 2. Estimation Commands

### 2.1 OLS Regression: `regress`

| Stata | Python | Notes |
|-------|--------|-------|
| `regress y x1 x2` | `pf.feols("y ~ x1 + x2", data=df)` | pyfixest (preferred for DAAF) |
| `regress y x1 x2` | `smf.ols("y ~ x1 + x2", data=df).fit()` | statsmodels (note: requires `.fit()`) |
| `regress y x1 x2, robust` | `pf.feols("y ~ x1 + x2", data=df, vcov="hetero")` | HC1 (Stata default "robust") |
| `regress y x1 x2, vce(cluster clvar)` | `pf.feols("y ~ x1 + x2", data=df, vcov={"CRV1": "clvar"})` | Clustered SEs |
| `regress y x1 x2, vce(cluster clvar1 clvar2)` | `pf.feols("y ~ x1 + x2", data=df, vcov={"CRV1": "clvar1+clvar2"})` | Two-way clustering |
| `predict yhat, xb` | `fit.predict()` | Fitted values |
| `predict resid, residuals` | `fit.resid()` | Residuals |
| `_b[x1]` | `fit.coef()["x1"]` | Coefficient access |
| `_se[x1]` | `fit.se()["x1"]` | Standard error access |
| `e(r2)` | `fit._r2` | R-squared |
| `e(N)` | `fit._N` | Observation count |

**Stata's `robust` = HC1:** Stata's default robust standard errors use the HC1 correction (small-sample adjusted White SEs). pyfixest's `vcov="hetero"` produces HC1 by default. statsmodels must specify `cov_type="HC1"` explicitly.

**Sources:** Fischer et al., *pyfixest* (pyfixest.org, v0.40.0, accessed 2026-03-28); Seabold & Perktold, *statsmodels* (v0.14.6); Turrell, "Coming from Stata" (aeturrell.github.io, accessed 2026-03-28); pyfixest PR #897, "Show how to replicate Stata results" (github.com/py-econometrics/pyfixest/pull/897).

---

### 2.2 Fixed Effects: `areg`, `xtreg fe`, `reghdfe`

| Stata | Python (pyfixest) | Notes |
|-------|-------------------|-------|
| `areg y x1 x2, absorb(fe_var)` | `pf.feols("y ~ x1 + x2 \| fe_var", data=df)` | Single FE absorption |
| `xtreg y x1 x2, fe` | `pf.feols("y ~ x1 + x2 \| entity", data=df)` | Panel FE (entity effects) |
| `xtreg y x1 x2, fe vce(cluster entity)` | `pf.feols("y ~ x1 + x2 \| entity", data=df, vcov={"CRV1": "entity"})` | Clustered |
| `reghdfe y x1 x2, absorb(fe1 fe2)` | `pf.feols("y ~ x1 + x2 \| fe1 + fe2", data=df)` | Multi-way FE |
| `reghdfe y x1 x2, absorb(fe1 fe2) cluster(cl1)` | `pf.feols("y ~ x1 + x2 \| fe1 + fe2", data=df, vcov={"CRV1": "cl1"})` | Multi-way FE + cluster |
| `reghdfe y x1 x2, absorb(fe1 fe2) cluster(cl1 cl2)` | `pf.feols("y ~ x1 + x2 \| fe1 + fe2", data=df, vcov={"CRV1": "cl1+cl2"})` | Two-way clustering |
| `reghdfe y x1 x2, absorb(fe1#fe2)` | `pf.feols("y ~ x1 + x2 \| fe1^fe2", data=df)` | Interacted FE |
| `reghdfe y x1 c.x2#i.cat, absorb(fe1)` | `pf.feols("y ~ x1 + x2:C(cat) \| fe1", data=df)` | Interaction with categorical |

**Random Effects: `xtreg re`**

| Stata | Python (linearmodels) | Notes |
|-------|----------------------|-------|
| `xtreg y x1 x2, re` | `RandomEffects.from_formula("y ~ 1 + x1 + x2", data=df_panel).fit()` | Requires pandas MultiIndex |

linearmodels requires a pandas DataFrame with a MultiIndex `(entity, time)`:
```python
from linearmodels.panel import PanelOLS, RandomEffects
df_panel = df.to_pandas().set_index(["entity_id", "year"])
```

**Key behavioral difference:** Stata's `reghdfe` uses an iterative demean algorithm (Correia, 2016) for high-dimensional FE. pyfixest uses the same algorithmic approach and produces numerically equivalent results. Speed: pyfixest is generally faster than `reghdfe` for datasets with many FE levels.

**Sources:** Fischer et al., *pyfixest* (pyfixest.org, v0.40.0); Correia, "reghdfe" (scorreia.com, accessed 2026-03-28); Sheppard, *linearmodels* (v7.0); Turrell, "Coming from Stata" (aeturrell.github.io).

---

### 2.3 Instrumental Variables: `ivregress 2sls`, `ivreg2`, `ivreghdfe`

| Stata | Python | Notes |
|-------|--------|-------|
| `ivregress 2sls y x_exog (x_endog = z1 z2)` | `pf.feols("y ~ x_exog \| 0 \| x_endog ~ z1 + z2", data=df)` | Three-part formula; `0` means no FE |
| `ivregress 2sls y x_exog (x_endog = z1 z2), robust` | `pf.feols("y ~ x_exog \| 0 \| x_endog ~ z1 + z2", data=df, vcov="hetero")` | |
| `ivreg2 y x_exog (x_endog = z1 z2), robust` | Same as above | `ivreg2` is community Stata command; pyfixest syntax is the same |
| `ivreghdfe y x_exog (x_endog = z1), absorb(fe1 fe2)` | `pf.feols("y ~ x_exog \| fe1 + fe2 \| x_endog ~ z1", data=df)` | IV + multi-way FE |
| `ivregress 2sls y (x_endog = z1), first` | `fit.IV_Diag()` then `fit._model_1st_stage.summary()` | First-stage diagnostics |

**Without FE (linearmodels alternative):**

| Stata | Python (linearmodels) | Notes |
|-------|----------------------|-------|
| `ivregress 2sls y x_exog (x_endog = z)` | `IV2SLS.from_formula("y ~ 1 + x_exog + [x_endog ~ z]", data=df).fit()` | Bracket notation |
| `ivregress liml y x_exog (x_endog = z1 z2)` | `IVLIML.from_formula("y ~ 1 + x_exog + [x_endog ~ z1 + z2]", data=df).fit()` | LIML estimator |
| `ivregress gmm y x_exog (x_endog = z)` | `IVGMM.from_formula("y ~ 1 + x_exog + [x_endog ~ z]", data=df).fit()` | GMM estimator |

**IV diagnostics mapping:**

| Stata | Python | Notes |
|-------|--------|-------|
| `estat firststage` | `fit.IV_Diag()` (pyfixest) or `fit.first_stage` (linearmodels) | First-stage F statistic |
| `estat overid` | `fit.sargan` (linearmodels) | Sargan/Hansen overidentification test |
| `estat endogeneity` | `fit.wu_hausman()` (linearmodels) | Wu-Hausman endogeneity test |

**Sources:** Fischer et al., *pyfixest* (pyfixest.org, v0.40.0); Sheppard, *linearmodels* (v7.0); Correia, "ivreghdfe" (github.com/sergiocorreia/ivreghdfe).

---

### 2.4 GLM: `logit`, `probit`, `ologit`, `mlogit`

| Stata | Python (statsmodels) | Notes |
|-------|---------------------|-------|
| `logit y x1 x2` | `smf.logit("y ~ x1 + x2", data=df).fit()` | Binary logit |
| `probit y x1 x2` | `smf.probit("y ~ x1 + x2", data=df).fit()` | Binary probit |
| `logit y x1 x2, or` | `np.exp(fit.params)` after `smf.logit(...)` | Odds ratios: exponentiate coefficients |
| `ologit y x1 x2` | `OrderedModel(df["y"], df[["x1","x2"]], distr="logit").fit()` | Ordered logit; from `statsmodels.miscmodels.ordinal_model` |
| `mlogit y x1 x2` | `sm.MNLogit(df["y"], sm.add_constant(df[["x1","x2"]])).fit()` | Multinomial logit; from `statsmodels.discrete.discrete_model` |
| `probit y x1 x2, vce(robust)` | `smf.probit("y ~ x1 + x2", data=df).fit(cov_type="HC1")` | Robust SEs |

**GLM with fixed effects -- the major gap:**

Stata's `logit y x1 i.fe_var` absorbs FE as dummies. Stata's unofficial `feglm` and `ppmlhdfe` can handle high-dimensional FE with GLMs.

**pyfixest's `feglm()` does NOT support fixed effects absorption.** This is the single largest feature gap between Stata and the DAAF Python stack for GLM estimation.

**Workarounds:**

| Approach | Code | When to Use |
|----------|------|-------------|
| Linear probability model | `pf.feols("binary_y ~ x \| fe", data=df)` | Most common; interpret as pp changes |
| Manual dummies + statsmodels | `smf.logit("y ~ x + C(fe_var)", data=df).fit()` | Small number of FE levels |
| Conditional logit | `sm.discrete.ConditionalLogit(...)` | Binary outcome + entity FE |
| Poisson pseudo-ML | `pf.fepois("binary_y ~ x \| fe", data=df)` | If Poisson approximation acceptable |

**Sources:** statsmodels documentation (statsmodels.org, v0.14.6); Fischer et al., *pyfixest* (pyfixest.org, v0.40.0); statsmodels ordinal_model documentation.

---

### 2.5 Count Models: `poisson`, `nbreg`

| Stata | Python | Notes |
|-------|--------|-------|
| `poisson y x1 x2` | `smf.poisson("y ~ x1 + x2", data=df).fit()` | statsmodels Poisson |
| `poisson y x1 x2, robust` | `smf.poisson("y ~ x1 + x2", data=df).fit(cov_type="HC1")` | Robust SEs |
| `ppmlhdfe y x1 x2, absorb(fe1 fe2)` | `pf.fepois("y ~ x1 + x2 \| fe1 + fe2", data=df)` | Poisson pseudo-ML with multi-way FE |
| `nbreg y x1 x2` | `sm.NegativeBinomial(df["y"], sm.add_constant(df[["x1","x2"]]), loglike_method="nb2").fit()` | Negative binomial (NB2 parameterization) |
| `nbreg y x1 x2` | `smf.glm("y ~ x1 + x2", data=df, family=sm.families.NegativeBinomial()).fit()` | GLM alternative |

**Key behavioral difference:** Stata's `nbreg` uses the NB2 parameterization by default (variance = mu + alpha*mu^2). statsmodels' `NegativeBinomial` supports `"nb2"`, `"nb1"`, and `"geometric"` via the `loglike_method` parameter.

**Sources:** statsmodels documentation, NegativeBinomial (statsmodels.org, v0.14.6); Fischer et al., *pyfixest* fepois documentation (pyfixest.org).

---

### 2.6 SUR: `sureg`

| Stata | Python (linearmodels) | Notes |
|-------|----------------------|-------|
| `sureg (eq1: y1 x1 x2) (eq2: y2 x3 x4)` | See below | Dictionary-based specification |

```python
from linearmodels.system import SUR

system = {
    "eq1": {"dependent": df["y1"], "exog": sm.add_constant(df[["x1", "x2"]])},
    "eq2": {"dependent": df["y2"], "exog": sm.add_constant(df[["x3", "x4"]])},
}
sur = SUR(system)
result = sur.fit()
print(result.summary)
```

**Key behavioral difference:** Stata's `sureg` uses a simple parenthesized equation syntax. linearmodels requires constructing a dictionary with `"dependent"` and `"exog"` keys for each equation. Each equation can have different regressors.

**Sources:** Sheppard, *linearmodels* (bashtage.github.io/linearmodels, v7.0); UCLA Statistical Methods, "SUR FAQ" (stats.oarc.ucla.edu).

---

### 2.7 Marginal Effects and Post-Estimation: `margins`, `marginsplot`

| Stata | Python (marginaleffects) | Notes |
|-------|-------------------------|-------|
| `margins, dydx(*)` | `avg_slopes(fit)` | Average marginal effects, all variables |
| `margins, dydx(x1)` | `avg_slopes(fit, variables="x1")` | AME for specific variable |
| `margins, at(x1=(0 1))` | `predictions(fit, newdata=datagrid(x1=[0, 1], model=fit))` | Predictive margins at specific values |
| `margins, at(x1=(0 1)) dydx(x2)` | `avg_slopes(fit, variables="x2", newdata=datagrid(x1=[0, 1], model=fit))` | Conditional AME |
| `marginsplot` | Manual plotting with plotnine/matplotlib | No built-in marginsplot; extract from marginaleffects output |
| `margins group, dydx(x1)` | `avg_slopes(fit, variables="x1", by="group")` | Group-specific AME |

**Stata `margins` vs Python `marginaleffects`:**

```python
from marginaleffects import avg_slopes, predictions, comparisons, hypotheses, datagrid

# After fitting any supported model (statsmodels, pyfixest, sklearn):
fit = smf.logit("y ~ x1 * x2 + x3", data=df).fit()

# Average marginal effects (Stata: margins, dydx(*))
avg_slopes(fit)

# Predictions at specific values (Stata: margins, at(x1=(0 1)))
predictions(fit, newdata=datagrid(x1=[0, 1], model=fit))

# Discrete change (Stata: margins, dydx(x1) at(x1=(0 1)) contrast(ar))
avg_comparisons(fit, variables={"x1": [0, 1]})

# Hypothesis testing (Stata: test x1 = x2)
hypotheses(fit, "x1 = x2")

# Nonlinear combination (Stata: nlcom)
hypotheses(fit, "(x1 / x2 - 1) * 100 = 0")
```

**Caveat:** The Python `marginaleffects` package is described by its author as alpha. Verify critical results against Stata for published research.

**Sources:** Arel-Bundock, Greifer, & Heiss, "How to Interpret Statistical Models Using marginaleffects for R and Python" (JSS, 2024); marginaleffects.com (accessed 2026-03-28).

---

### 2.8 Post-Estimation Testing: `test`, `lincom`, `nlcom`

| Stata | Python | Notes |
|-------|--------|-------|
| `test x1 x2` | `fit.wald_test("x1 = 0, x2 = 0")` (pyfixest) | Joint F-test |
| `test x1 = x2` | `fit.wald_test("x1 - x2 = 0")` (pyfixest) or `hypotheses(fit, "x1 = x2")` | Equality test |
| `lincom x1 + x2` | `hypotheses(fit, "x1 + x2 = 0")` (marginaleffects) | Linear combination |
| `lincom x1 - 2*x2` | `hypotheses(fit, "x1 - 2*x2 = 0")` (marginaleffects) | Linear combination |
| `nlcom _b[x1]/_b[x2]` | `hypotheses(fit, "x1 / x2 = 0")` (marginaleffects) | Nonlinear combination (delta method) |

**statsmodels alternatives:**

```python
# F-test (Stata: test x1 x2)
fit.f_test("x1 = 0, x2 = 0")

# Wald test for linear restriction (Stata: test x1 = x2)
fit.t_test("x1 - x2 = 0")

# Wald test via restriction matrix (Stata: test x1, x2 -- joint test)
fit.wald_test(np.array([[0, 1, 0], [0, 0, 1]]))  # Tests coefficients 1 and 2 = 0
```

**Sources:** Fischer et al., *pyfixest* (pyfixest.org); Arel-Bundock, *marginaleffects* (marginaleffects.com); statsmodels RegressionResults.wald_test documentation (statsmodels.org).

---

### 2.9 Regression Tables: `outreg2`, `esttab`, `eststo`

| Stata | Python | Notes |
|-------|--------|-------|
| `eststo: reg y x1` then `esttab` | `fit1 = pf.feols(...)` then `pf.etable([fit1, fit2, fit3])` | pyfixest etable (primary) |
| `outreg2 using table.tex` | `pf.etable([fit1, fit2], type="tex")` | LaTeX output |
| `esttab, se star(* 0.10 ** 0.05 *** 0.01)` | `pf.etable([fit1, fit2], signif_code=[0.01, 0.05, 0.10])` | Custom significance stars |
| `esttab, label` | `pf.etable([fit1, fit2], labels={"x1": "Education", "x2": "Experience"})` | Variable labels |
| `esttab, indicate(FE=*)` | `pf.etable([fit1, fit2], felabels={"entity": "Entity FE", "year": "Year FE"})` | FE indicator rows |
| `esttab, keep(x1 x2)` | `pf.etable([fit1, fit2], keep=["x1", "x2"])` | Show only selected variables |
| `esttab using table.md, md` | `pf.etable([fit1, fit2], type="md")` | Markdown output |

**`pf.etable()` output types:**
- `type="gt"` -- default, returns a great_tables GT object (rendered in notebooks)
- `type="md"` -- Markdown string
- `type="tex"` -- LaTeX string
- `type="df"` -- pandas DataFrame (for custom formatting)

**Descriptive statistics table (Stata: `summarize` in table form):**
```python
pf.dtable(df, vars=["y", "x1", "x2"])
```

**Sources:** Fischer et al., *pyfixest* etable documentation (pyfixest.org); Ben Jann, "estout" (repec.org/bocode/e/estout).

---

## 3. Causal Inference Commands

### 3.1 Difference-in-Differences: `diff`, TWFE DiD

| Stata | Python (pyfixest) | Notes |
|-------|-------------------|-------|
| `diff y, t(treated) p(post)` | `pf.feols("y ~ treated:post \| unit + time", data=df, vcov={"CRV1": "unit"})` | Basic 2x2 DiD |
| `reg y treated##post, cluster(unit)` | Same as above | Stata factor notation equivalent |
| `reghdfe y treated, absorb(unit year) cluster(unit)` | `pf.feols("y ~ treated \| unit + year", data=df, vcov={"CRV1": "unit"})` | TWFE DiD |

### 3.2 Modern DiD Estimators: `did_multiplegt`, `csdid`, `eventstudyinteract`

| Stata | Python | Fidelity | Notes |
|-------|--------|----------|-------|
| `did_multiplegt y group time treatment` | No direct equivalent | **Gap** | de Chaisemartin & D'Haultfoeuille estimators; no maintained Python port exists as of 2026-03 |
| `csdid y, ivar(unit) time(year) gvar(first_treat)` | `csdid.att_gt(yname="y", idname="unit", tname="year", gname="first_treat", data=df)` | Medium | Community port (d2cml-ai); verify against Stata/R for published work |
| `eventstudyinteract y lead_lag_vars, absorb(unit year) cohort(first_treat) control_cohort(never_treat)` | `pf.event_study(data=df, yname="y", idname="unit", tname="year", gname="first_treat", estimator="saturated")` | High | Sun-Abraham estimator; pyfixest implementation |

**pyfixest DiD estimators:**

| Stata Equivalent | pyfixest Function | Notes |
|-----------------|------------------|-------|
| TWFE event study with `i.rel_time` | `pf.feols("y ~ i(rel_time, ref=-1) \| unit + year", data=df)` | Manual event study |
| `did2s` (Gardner, 2022) | `pf.did2s(data=df, yname="y", first_stage="~ 0 \| unit + year", second_stage="~ i(rel_time, ref=-1)", treatment="treated", cluster="unit")` | Two-stage DiD |
| Sun-Abraham saturated | `pf.event_study(data=df, yname="y", idname="unit", tname="year", gname="first_treat", estimator="saturated")` | Fully saturated |
| LP-DiD (Dube et al., 2023) | `pf.lpdid(data=df, yname="y", idname="unit", tname="year", gname="first_treat", att=True)` | Returns DataFrame, not Feols object |

**Event study plots:**

| Stata | Python | Notes |
|-------|--------|-------|
| `coefplot` | `fit.iplot()` | Method on Feols object |
| `event_plot` | `fit.iplot(joint="both")` | With Bonferroni/Scheffe bands |
| `panelview` (if installed) | `pf.panelview(data=df, unit="unit", time="year", treat="treated")` | Treatment pattern visualization |

**Sources:** Fischer et al., *pyfixest* DiD documentation (pyfixest.org); Callaway & Sant'Anna, "Difference-in-Differences with Multiple Time Periods" (J. Econometrics, 2021); Sun & Abraham, "Estimating Dynamic Treatment Effects" (J. Econometrics, 2021); Dube et al., "A Local Projections Approach" (NBER WP 31184, 2023); de Chaisemartin & D'Haultfoeuille (AER, 2020).

---

### 3.3 Regression Discontinuity: `rdrobust`, `rdplot`

All three implementations (Stata, R, Python) are maintained by the same authors (Cattaneo, Idrobo, Titiunik), ensuring very high cross-platform fidelity.

| Stata | Python | Notes |
|-------|--------|-------|
| `rdrobust Y X, c(cutoff)` | `rdrobust(Y, X, c=cutoff)` | Point estimate + robust CI |
| `rdplot Y X, c(cutoff)` | `rdplot(Y, X, c=cutoff)` | Data-driven RD plot |
| `rdbwselect Y X, c(cutoff)` | `rdbwselect(Y, X, c=cutoff)` | Bandwidth selection |
| `rdrobust Y X, c(cutoff) fuzzy(T)` | `rdrobust(Y, X, c=cutoff, fuzzy=T)` | Fuzzy RD |
| `rdrobust Y X, c(cutoff) covs(c1 c2)` | `rdrobust(Y, X, c=cutoff, covs=covs_array)` | With covariates |
| `rdrobust Y X, c(cutoff) kernel(tri)` | `rdrobust(Y, X, c=cutoff, kernel="tri")` | Kernel specification |
| `rdrobust Y X, c(cutoff) h(h_left h_right)` | `rdrobust(Y, X, c=cutoff, h=[h_left, h_right])` | Manual bandwidth |
| `rdrobust Y X, c(cutoff) cluster(cl)` | `rdrobust(Y, X, c=cutoff, cluster=cl)` | Clustered SEs |

```python
# Install: pip install rdrobust rddensity rdmulti rdpower
from rdrobust import rdrobust, rdplot, rdbwselect
```

**Syntax differences are minimal:** Stata's `c()` for paired values becomes Python's `[]`. Stata's `cbind()` for covariate matrices becomes numpy arrays. Otherwise the API is virtually identical.

**Additional RD packages (same authors, same API across languages):**

| Tool | Stata | Python (`pip install`) |
|------|-------|----------------------|
| Manipulation test | `rddensity` | `rddensity` |
| Multi-cutoff/score | `rdmulti` | `rdmulti` |
| Power calculations | `rdpower` | `rdpower` |

**Sources:** Cattaneo, Idrobo, & Titiunik, *A Practical Introduction to Regression Discontinuity Designs* (Cambridge, 2020); rdpackages.github.io (accessed 2026-03-28); Calonico, Cattaneo, Farrell, & Titiunik, "rdrobust: Software for Regression-discontinuity Designs" (Stata Journal, 2017).

---

### 3.4 Treatment Effects and Matching: `teffects`, `psmatch2`, `cem`

This is a **significant gap** in the Python ecosystem relative to Stata's built-in `teffects` suite.

| Stata | Python Equivalent | Fidelity | Notes |
|-------|------------------|----------|-------|
| `teffects psmatch (y) (treat x1 x2)` | `pymatchit-causal` or manual sklearn | Low-Medium | `teffects` adjusts SEs for estimated propensity scores; Python packages generally do not |
| `teffects ipw (y) (treat x1 x2)` | Manual: sklearn LogisticRegression + weighting | Low | Must implement IPW manually |
| `teffects ra (y x1 x2) (treat)` | Manual: separate regressions + averaging | Low | Regression adjustment |
| `teffects ipwra (y x1 x2) (treat x1 x2)` | No direct equivalent | **Gap** | Doubly-robust AIPW |
| `teffects aipw (y x1 x2) (treat x1 x2)` | `econml.dr.DRLearner` | Medium | Different implementation |
| `psmatch2 treat x1 x2, outcome(y)` | `psmpy` or `pymatchit-causal` | Low-Medium | Community packages |
| `cem treat x1 x2, outcome(y)` | `pymatchit-causal` (CEM method) | Low-Medium | CEM available in pymatchit-causal |

**Available Python matching packages:**

| Package | Install | Methods | Quality |
|---------|---------|---------|---------|
| `pymatchit-causal` | `pip install pymatchit-causal` | Nearest neighbor, optimal, exact, subclassification, CEM | Medium -- port of R MatchIt |
| `psmpy` | `pip install psmpy` | Propensity score matching via k-NN | Medium -- academic publication |
| `pysmatch` | `pip install pysmatch` | Gradient-based propensity matching | Fair |
| Manual sklearn | Pre-installed | LogisticRegression + NearestNeighbors | N/A -- requires manual implementation |

**Critical difference:** Stata's `teffects psmatch` computes correct standard errors that account for the fact that propensity scores are estimated (Abadie & Imbens, 2016). Most Python matching packages do NOT make this correction, which means their SEs and p-values are wrong. For published research using propensity score matching, consider running the matching step in Stata or R and importing the results.

**Sources:** Stata `teffects` manual (stata.com/manuals/causal.pdf); pymatchit-causal (pypi.org, accessed 2026-03-28); psmpy (pypi.org, accessed 2026-03-28); Abadie & Imbens, "Matching on the Estimated Propensity Score" (Econometrica, 2016).

---

### 3.5 Synthetic Control: `synth`, `synth_runner`

| Stata | Python Equivalent | Fidelity | Notes |
|-------|------------------|----------|-------|
| `synth depvar predictors, trunit(id) trperiod(t)` | `SyntheticControlMethods` package | Medium | Classic ADH estimator |
| `synth_runner depvar predictors, trunit(id) trperiod(t)` | No direct equivalent | **Gap** | Automated inference for synth |
| `synth depvar predictors, ...` | `scpi` package | High | Same authors as Stata; includes prediction intervals |

```python
# Option 1: Classic SC (community package)
# pip install SyntheticControlMethods
from SyntheticControlMethods import Synth

# Option 2: scpi (official, by Cattaneo et al.)
# pip install scpi
import scpi

# Option 3: Bayesian SC (different methodology)
# pip install CausalPy
import causalpy as cp
result = cp.SyntheticControl(df, treatment_time=t0, formula="y ~ 0 + x1 + x2",
                             model=cp.pymc_models.WeightedSumFitter())
```

**The `scpi` package** (by Cattaneo, Feng, Palomba, and Titiunik) is the most rigorous Python option. It provides prediction intervals and uncertainty quantification for synthetic control estimators, with implementations available in Python, R, and Stata from the same team.

**Sources:** Abadie, Diamond, & Hainmueller (JASA, 2010); SyntheticControlMethods (pypi.org); scpi (nppackages.github.io/scpi, accessed 2026-03-28); CausalPy (pypi.org).

---

## 4. Survey Commands

### 4.1 Survey Design and Estimation: `svyset`, `svy:` prefix

| Stata | Python (svy package) | Notes |
|-------|---------------------|-------|
| `svyset psu_id, strata(stratum) weight(wgt)` | `design = svy.Design(psu="psu_id", stratum="stratum", wgt="wgt")` | Design specification |
| `svyset psu_id [pw=wgt], strata(stratum) fpc(fpc_var)` | `design = svy.Design(psu="psu_id", stratum="stratum", wgt="wgt", fpc="fpc_var")` | With finite population correction |
| (bind data to design) | `sample = svy.Sample(data=data, design=design)` | Required step; combines data + design |
| `svy: mean income` | `sample.estimation.mean("income")` | Survey-weighted mean |
| `svy: total pop_count` | `sample.estimation.total("pop_count")` | Survey-weighted total |
| `svy: proportion employed` | `sample.estimation.prop("employed")` | Survey-weighted proportion |
| `svy: ratio expend/hh_size` | `sample.estimation.ratio(y="expend", x="hh_size")` | Survey-weighted ratio |
| `svy, subpop(female): mean income` | `sample.estimation.mean("income", by="female")` | Subpopulation estimation |
| `svy: regress income age education` | `sample.glm.fit(y="income", x=["age", svy.Cat("education")], family="gaussian")` | Survey-weighted regression |
| `svy: logit employed age education` | `sample.glm.fit(y="employed", x=["age", svy.Cat("education")], family="binomial")` | Survey-weighted logit |
| `svydes` | `sample.design_summary()` or inspect the Design object | Survey design description |

**Multi-stage design example:**

Stata:
```stata
svyset psu_id [pw=final_wgt], strata(region urban_rural)
svy: mean income
svy: regress income age i.education
```

Python:
```python
import svy

design = svy.Design(
    stratum=("region", "urban_rural"),
    psu="psu_id",
    wgt="final_wgt"
)
sample = svy.Sample(data=data, design=design)

# Survey mean
sample.estimation.mean("income")

# Survey regression
model = sample.glm.fit(
    y="income",
    x=["age", svy.Cat("education")],
    family="gaussian"
)
```

**Variance estimation methods:**

| Stata | Python (svy) | Notes |
|-------|-------------|-------|
| Taylor linearization (default) | Taylor linearization (default) | Same methodology |
| `svy, vce(brr): mean y` | BRR via replicate weights | |
| `svy, vce(jackknife): mean y` | Jackknife via replicate weights | |
| `svy, vce(bootstrap): mean y` | Bootstrap via replicate weights | |

**Key behavioral difference:** Stata's `svyset` is persistent -- once declared, the `svy:` prefix uses that design for all subsequent commands until changed. Python requires explicitly passing the `sample` object to every estimation call.

**Sources:** svy package documentation (svylab.com, accessed 2026-03-28); Stata Survey Data Reference Manual (stata.com/manuals/svy.pdf); Lumley, *Complex Surveys* (Wiley, 2010).

---

## 5. Output and Visualization

### 5.1 Graphs: `graph twoway`, `graph bar`, `graph box`, `histogram`

| Stata | Python (plotnine) | Notes |
|-------|------------------|-------|
| `twoway scatter y x` | `(ggplot(df, aes("x", "y")) + geom_point())` | Grammar of graphics syntax |
| `twoway scatter y x if condition` | `(ggplot(df.filter(condition).to_pandas(), aes("x", "y")) + geom_point())` | Filter before plotting |
| `twoway (scatter y x) (lfit y x)` | `(ggplot(df_pd, aes("x", "y")) + geom_point() + geom_smooth(method="lm"))` | Scatter + fitted line |
| `twoway line y x` | `(ggplot(df_pd, aes("x", "y")) + geom_line())` | Line plot |
| `twoway area y x` | `(ggplot(df_pd, aes("x", "y")) + geom_area())` | Area plot |
| `twoway connected y x` | `(ggplot(df_pd, aes("x", "y")) + geom_line() + geom_point())` | Connected scatter |
| `graph bar (mean) y, over(group)` | `(ggplot(df_pd, aes("group", "y")) + stat_summary(fun_y=np.mean, geom="bar"))` | Bar chart of means |
| `graph box y, over(group)` | `(ggplot(df_pd, aes("group", "y")) + geom_boxplot())` | Box plot |
| `histogram y, bin(20)` | `(ggplot(df_pd, aes("y")) + geom_histogram(bins=20))` | Histogram |
| `histogram y, freq` | `(ggplot(df_pd, aes("y")) + geom_histogram(bins=20))` | Frequency histogram (default) |
| `histogram y, kdensity` | `(ggplot(df_pd, aes("y")) + geom_density())` | Kernel density |
| `graph export fig.png` | `p.save("fig.png", dpi=300)` | Save figure |

**Note:** plotnine requires pandas DataFrames, not polars. Convert with `.to_pandas()` before plotting.

**Plotly alternative (interactive):**
```python
import plotly.express as px
fig = px.scatter(df.to_pandas(), x="x", y="y", color="group")
fig.write_html("fig.html")
```

**Binscatter (Stata `binscatter` equivalent):**
```python
# pip install binsreg
import binsreg
binsreg.binsreg(y=df["y"].to_numpy(), x=df["x"].to_numpy(), nbins=20)
```

**Sources:** plotnine documentation (plotnine.org, accessed 2026-03-28); plotly documentation (plotly.com, accessed 2026-03-28); binsreg (pypi.org, accessed 2026-03-28).

---

### 5.2 Tables: `tabulate`, `tab2`, `table`, `summarize`, `describe`, `codebook`

| Stata | Python (polars) | Python (pandas) | Notes |
|-------|----------------|-----------------|-------|
| `summarize` | `df.describe()` | `df.describe()` | Summary statistics for all columns |
| `summarize var` | `df.select("var").describe()` | `df["var"].describe()` | Single variable |
| `summarize var, detail` | `df.select("var").describe()` + manual quantiles | `df["var"].describe(percentiles=[.01,.05,.10,.25,.50,.75,.90,.95,.99])` | Detailed summary |
| `describe` | `df.schema` and `df.shape` | `df.info()` | Data structure info |
| `codebook var` | Combine `df.describe()` + `df["var"].n_unique()` + `df["var"].null_count()` | `df["var"].describe()` | Comprehensive variable profile |
| `tabulate var` | `df["var"].value_counts()` | `df["var"].value_counts()` | Frequency table |
| `tabulate var1 var2` | `df.to_pandas().pipe(lambda d: pd.crosstab(d["var1"], d["var2"]))` | `pd.crosstab(df["var1"], df["var2"])` | Cross-tabulation |
| `tabulate var1 var2, chi2` | `scipy.stats.chi2_contingency(pd.crosstab(...))` | | Chi-squared test |
| `tabulate var, summarize(y)` | `df.group_by("var").agg(pl.col("y").mean(), pl.col("y").std(), pl.col("y").count())` | `df.groupby("var")["y"].describe()` | Tab with summary stats |
| `table var1 var2, stat(mean y)` | `df.pivot(on="var2", index="var1", values="y", aggregate_function="mean")` | `df.pivot_table(values="y", index="var1", columns="var2", aggfunc="mean")` | Flexible table |

**Sources:** Sullivan, "Stata to Python Equivalents" (danielmsullivan.com); pandas "Comparison with Stata" (pandas.pydata.org); polars User Guide (docs.pola.rs).

---

## 6. Programming Commands

### 6.1 Loops: `foreach`, `forvalues`

| Stata | Python | Notes |
|-------|--------|-------|
| `foreach var of varlist x1 x2 x3 { ... }` | `for var in ["x1", "x2", "x3"]: ...` | Python `for` loop over list |
| `forvalues i = 1/10 { ... }` | `for i in range(1, 11): ...` | `range()` is exclusive of endpoint |
| `forvalues i = 2000(5)2020 { ... }` | `for i in range(2000, 2021, 5): ...` | Step size as third argument |
| `foreach x in "a" "b" "c" { ... }` | `for x in ["a", "b", "c"]: ...` | |
| `foreach var of varlist pop* { ... }` | `for var in df.select(cs.starts_with("pop")).columns: ...` | Pattern-based column iteration |

**List comprehension (Pythonic alternative):**
```python
# Stata: foreach var of varlist x1 x2 x3 { gen log_`var' = log(`var') }
df = df.with_columns([
    pl.col(var).log().alias(f"log_{var}") for var in ["x1", "x2", "x3"]
])
```

**Key paradigm difference:** Stata's `foreach`/`forvalues` are essential because Stata is a command-driven language without vectorized operations across columns. Python's expression-based system (polars `pl.col()`, list comprehensions) often eliminates the need for explicit loops. Prefer vectorized operations over loops in Python.

---

### 6.2 Macros and Scalars: `local`, `global`, `scalar`

| Stata | Python | Notes |
|-------|--------|-------|
| `local myvar "income"` | `myvar = "income"` | Python variables are the direct equivalent |
| `global myvar "income"` | `myvar = "income"` (module-level) | Python has no global/local macro distinction in the Stata sense |
| `scalar myscalar = 42` | `myscalar = 42` | Python variables serve all purposes |
| `display `myvar'` | `print(myvar)` | |
| `local varlist "x1 x2 x3"` | `varlist = ["x1", "x2", "x3"]` | Python lists replace space-delimited macro lists |
| `` reg y `varlist' `` | `pf.feols(f"y ~ {' + '.join(varlist)}", data=df)` | f-strings for dynamic formula construction |

**Dynamic formula construction:**
```python
# Stata: local controls "age education income"
#        reg y treatment `controls'
controls = ["age", "education", "income"]
formula = "y ~ treatment + " + " + ".join(controls)
fit = pf.feols(formula, data=df)
```

**Key paradigm difference:** Stata macros are text substitution mechanisms. Python variables are first-class objects. Python's f-strings and string methods replace Stata's macro interpolation syntax (backtick-quote).

---

### 6.3 Temporary Objects: `tempvar`, `tempfile`

| Stata | Python | Notes |
|-------|--------|-------|
| `tempvar tv` then `gen `tv' = expr` | `df = df.with_columns(expr.alias("_temp"))` then `df = df.drop("_temp")` | No automatic cleanup; drop manually |
| `tempfile tf` then `save `tf'` | `import tempfile; tf = tempfile.NamedTemporaryFile()` | Python tempfile module; rarely needed since multiple DataFrames coexist |
| `preserve` ... `restore` | `df_backup = df.clone()` | Since polars DataFrames are immutable by default, the original is preserved automatically |

**Key paradigm difference:** Stata needs `tempvar`/`tempfile`/`preserve`/`restore` because it operates on a single dataset in memory. Python holds multiple DataFrames as separate variables, making these constructs largely unnecessary. Simply assign intermediate results to new variables:
```python
df_original = pl.read_parquet("data.parquet")
df_filtered = df_original.filter(pl.col("year") == 2020)
df_agg = df_original.group_by("state").agg(pl.col("income").mean())
# All three DataFrames coexist; no preservation needed
```

---

### 6.4 Output Suppression: `quietly`, `noisily`, `capture`

| Stata | Python | Notes |
|-------|--------|-------|
| `quietly reg y x` | `fit = pf.feols("y ~ x", data=df)` (no print by default) | Python does not print results unless you explicitly call `.summary()` or `print()` |
| `noisily reg y x` | `fit = pf.feols("y ~ x", data=df); fit.summary()` | Print explicitly |
| `capture command` | `try: ... except: pass` | Python exception handling |
| `capture noisily command` | `try: ... except Exception as e: print(e)` | Capture + display error |
| `return code _rc` | Check exception type | `_rc` becomes checking whether an exception was raised |

**Key paradigm difference:** Stata commands print output by default; `quietly` suppresses it. Python functions return objects silently by default; you must explicitly print. This is the inverse behavior. Stata users transitioning to Python should expect to add `print()` or `.summary()` calls where they want to see output.

---

## 7. Key Paradigm Differences

### Top 10 Friction Points for Stata Users

| # | Friction Point | Stata Way | Python (polars) Way |
|---|---------------|-----------|-------------------|
| 1 | Single dataset vs multiple | One dataset in memory | Arbitrarily many DataFrames as variables |
| 2 | In-place modification | `replace var = expr` modifies data | `df = df.with_columns(...)` returns new DataFrame |
| 3 | Missing value behavior | `.` sorts as > all numbers; `.a`-`.z` supported | `null` sorts last; no extended missing types |
| 4 | Output default | Commands print results by default | Functions return objects silently |
| 5 | Variable labels | Built-in (`label variable`) | No built-in equivalent; use dictionaries |
| 6 | 1-indexed vs 0-indexed | `_n` starts at 1 | Indices start at 0 |
| 7 | Macro substitution | `` `macro' `` text substitution | Variables + f-strings |
| 8 | Row operations | `_n`, `_N`, `L.var`, `F.var` | `.shift()`, `.over()`, `.with_row_index()` |
| 9 | Robust SEs | `robust` option on command | Separate `vcov=` parameter |
| 10 | Factor variables | `i.var`, `c.var#i.var` | `C(var)`, `var:C(var)` or `i(var)` (pyfixest) |

### Data Type Mapping

| Stata Type | polars Type | Notes |
|-----------|------------|-------|
| `byte`, `int`, `long` | `pl.Int8`, `pl.Int16`, `pl.Int32`, `pl.Int64` | polars has more granular integer types |
| `float` | `pl.Float32` | |
| `double` | `pl.Float64` | Default for floating point |
| `str#` (fixed-length string) | `pl.Utf8` | polars strings are always variable-length UTF-8 |
| `strL` (long string) | `pl.Utf8` | Same as above |

### Panel Data Operations

| Stata | Python (polars) | Notes |
|-------|----------------|-------|
| `xtset entity time` | No equivalent; panel structure is implicit | polars has no panel declaration; use `.sort()` and `.over()` |
| `L.var` (lag) | `pl.col("var").shift(1).over("entity")` | Must sort by time first |
| `L2.var` (2-period lag) | `pl.col("var").shift(2).over("entity")` | |
| `F.var` (lead) | `pl.col("var").shift(-1).over("entity")` | |
| `D.var` (first difference) | `(pl.col("var") - pl.col("var").shift(1)).over("entity")` | |

---

## 8. Source Catalog

### Primary Mapping References

| Resource | Author(s) | URL | Type | Quality | Currency |
|----------|-----------|-----|------|---------|----------|
| Stata to Python Equivalents | Daniel M. Sullivan | danielmsullivan.com/pages/tutorial_stata_to_python.html | Guide | Good | Active; uses pandas + econtools |
| Coming from Stata (Coding for Economists) | Arthur Turrell et al. | aeturrell.github.io/coding-for-economists/coming-from-stata.html | Book chapter | Excellent | Active; uses pyfixest |
| Comparison with Stata (pandas docs) | pandas contributors | pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html | Documentation | Excellent | Active (pandas 3.0.1) |
| Statistics Cheatsheet (QuantEcon) | QuantEcon | cheatsheets.quantecon.org/stats-cheatsheet.html | Cheat sheet | Good | Active |
| LOST (Library of Statistical Techniques) | Nick Huntington-Klein et al. | lost-stats.github.io | Rosetta stone | Excellent | Active; multi-language |

### Package Documentation

| Package | Author(s) | URL | Stata Equivalent | DAAF Version |
|---------|-----------|-----|-----------------|--------------|
| pyfixest | Fischer, Schaer et al. | pyfixest.org | `regress`, `areg`, `reghdfe`, `ivreghdfe`, `ppmlhdfe` | 0.40.0 |
| statsmodels | Seabold, Perktold et al. | statsmodels.org | `regress`, `logit`, `probit`, `poisson`, `nbreg`, `glm` | 0.14.6 |
| linearmodels | Kevin Sheppard | bashtage.github.io/linearmodels | `xtreg`, `sureg`, `ivregress` | unpinned |
| polars | Ritchie Vink et al. | docs.pola.rs | All data management commands | 1.38.1 |
| rdrobust | Cattaneo, Titiunik et al. | rdpackages.github.io/rdrobust | `rdrobust`, `rdplot`, `rdbwselect` | unpinned |
| marginaleffects | Arel-Bundock et al. | marginaleffects.com | `margins`, `marginsplot`, `lincom`, `nlcom` | unpinned |
| svy | svylab | svylab.com | `svyset`, `svy:` prefix commands | 0.13.0 |
| plotnine | Kibirige | plotnine.org | `graph twoway`, `graph bar`, `graph box`, `histogram` | 0.15.3 |
| scpi | Cattaneo, Feng, Palomba, Titiunik | nppackages.github.io/scpi | `synth` | unpinned |
| pymatchit-causal | community | pypi.org/project/pymatchit-causal | `teffects psmatch`, `psmatch2`, `cem` | unpinned |

### Textbooks with Multi-Language Code

| Resource | Author(s) | URL | Languages | Quality |
|----------|-----------|-----|-----------|---------|
| The Effect | Nick Huntington-Klein | theeffectbook.net | R, Stata, Python | Excellent |
| Causal Inference: The Mixtape | Scott Cunningham | mixtape.scunning.com | R, Stata (Python community) | Good |
| Using R, Python, and Julia for Intro Econometrics | Heiss & Brunner | urfie.net | R, Python, Julia | Good |
| Mixtape Sessions (workshops) | Cunningham et al. | mixtapesessions.io | Python, Stata | Excellent |

### Specialized Resources

| Resource | Author(s) | URL | Focus | Notes |
|----------|-----------|-----|-------|-------|
| pystata (Stata's Python integration) | StataCorp | stata.com/python | Running Stata from Python | Requires Stata license |
| pyreadstat | Roche (open source) | github.com/Roche/pyreadstat | Reading .dta files with metadata | Preserves value labels, extended missing values |
| Difference-in-Differences hub | Asjad Naqvi | asjadnaqvi.github.io/DiD | All DiD estimators across languages | Comprehensive comparison |
| Tidy Finance: DiD with Python | Tidy Finance team | tidy-finance.org/python/difference-in-differences.html | DiD in Python | Practical tutorial |
| PyStataR | Bryce Wang | github.com/brycewang-stanford/PyStataR | Stata-equivalent pandas commands | Includes `tabulate`, `egen`, `reghdfe`, `winsor2` |

---

## Appendix: Ecosystem Gap Summary

Commands where the Python ecosystem has **no adequate equivalent** to Stata's functionality:

| Stata Command | Gap Description | Severity | Workaround |
|--------------|-----------------|----------|------------|
| `feglm` / GLM with high-dimensional FE | pyfixest `feglm()` does not support FE absorption | **High** | LPM via `pf.feols()`, or manual dummies |
| `teffects ipwra` / `teffects aipw` | No doubly-robust AIPW with correct SEs | **High** | `econml.dr.DRLearner` (different implementation) |
| `did_multiplegt` | de Chaisemartin & D'Haultfoeuille estimators | **Medium** | No Python port; use R or Stata |
| Extended missing values (`.a`-`.z`) | No native support in polars/pandas | **Medium** | Metadata dictionaries; `pyreadstat` for reading |
| Value labels (embedded in data) | No equivalent to Stata's label system | **Medium** | `pl.Enum`, `pl.Categorical`, or dictionary mappings |
| `synth_runner` | Automated SC inference | **Medium** | `scpi` for prediction intervals; `CausalPy` for Bayesian SC |
| `teffects psmatch` SE correction | SEs accounting for estimated propensity scores | **Medium** | Run matching in Stata/R; import matched data |
| `codebook` | Comprehensive variable documentation | **Low** | Combine `.describe()`, `.n_unique()`, `.null_count()` |
| `label variable` / `label data` | Dataset and variable documentation metadata | **Low** | Parquet metadata; companion documentation files |
