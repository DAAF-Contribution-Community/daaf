# Stata-Python Fundamental Paradigm Differences: Research Notes

**Date:** 2026-03-28
**Purpose:** Inform construction of a `stata-python-translation` skill for DAAF
**Researcher:** DAAF subagent (web research)

---

## 1. The "One Dataset in Memory" Model

### How Stata Handles It

Stata's architecture is built around a single dataset in memory. The dataset is a matrix where each column is a "variable" with a unique name and each row has a number (the special system variable `_n`). Every command operates on this one dataset implicitly -- there is no need to specify *which* dataset you mean.

```stata
* Stata -- implicit single dataset
use "schools.dta", clear
keep if enrollment > 500
gen log_enroll = log(enrollment)
summarize log_enroll
regress test_score log_enroll poverty_rate
```

No variable is ever prefixed with a dataset name. The verbs `keep`, `gen`, `summarize`, and `regress` all implicitly target "the dataset."

**The `frame` system (Stata 16+):** Frames allow holding multiple datasets in memory simultaneously, addressing the traditional single-dataset limitation. Key commands:

- `frame create framename` -- create a new named frame
- `frame change framename` -- switch active dataset
- `frame framename: command` -- execute a command on a specific frame without switching
- `frame put varlist if expr, into(framename)` -- copy a subset into a new frame
- `frlink m:1 keyvar, frame(other)` -- link frames without merging (alias variables)
- `frame copy source dest` -- duplicate a frame

Frames are relatively new and adoption remains limited. As one guide noted, "being a relatively new feature in Stata, few use it or understand its importance." The traditional one-dataset mental model still dominates Stata workflows.

**`preserve` / `restore`:** Before frames, Stata's mechanism for temporarily modifying data was `preserve`/`restore`. `preserve` saves the current dataset state; `restore` returns to it. In modern Stata (16+), preserve/restore is implemented using hidden frames behind the scenes, which can yield up to 20% speedups in Stata/MP.

```stata
* Stata -- preserve/restore pattern
preserve
keep if state == "CA"
collapse (mean) test_score, by(district)
save "ca_district_means.dta", replace
restore
* Original dataset is back, unmodified
```

### How Python Handles It Differently

Python's workspace holds any number of objects simultaneously. DataFrames are just variables, and operations always specify which DataFrame to operate on.

```python
# Python / polars -- explicit multi-object workspace
schools = pl.read_parquet("schools.parquet")
districts = pl.read_parquet("districts.parquet")
ca_schools = schools.filter(pl.col("state") == "CA")
merged = schools.join(districts, on="district_id", how="left")
```

The `preserve`/`restore` pattern is unnecessary because creating a subset doesn't destroy the original -- assignment creates a new object (or in polars, operations return new DataFrames by default).

```python
# Python equivalent of preserve/restore
ca_means = (
    schools.filter(pl.col("state") == "CA")
    .group_by("district")
    .agg(pl.col("test_score").mean())
)
# 'schools' is never modified
```

### Key Mental Model Shift

| Stata Mental Model | Python Mental Model |
|--------------------|---------------------|
| "The dataset" (singular, implicit) | "This DataFrame" (explicit, one of many) |
| Commands modify the dataset in place | Operations return new objects |
| `merge` and `append` build up *the* dataset | Multiple DataFrames coexist; join when needed |
| `preserve`/`restore` for temporary modifications | Just assign to a new variable |
| Column = "variable" (bare name) | Column = string in a DataFrame (`df["col"]`) |

### Common Mistakes During Transition

1. **Forgetting to specify the DataFrame:** Stata users expect `gen newvar = expr` to "just work." In Python, every operation must specify which DataFrame: `df = df.with_columns(...)`.
2. **Destructive habits:** Stata users expect `keep if condition` to permanently modify the dataset. In polars, `df.filter(cond)` returns a *new* DataFrame -- the original is unchanged unless reassigned.
3. **Merge accumulation:** Stata users build up one master dataset through successive merges. Python users should keep source DataFrames separate and merge only when needed for analysis.
4. **Frame unfamiliarity:** Even Stata users may not know frames exist, since they were introduced in Stata 16 (2019).

### Sources

- Sullivan, D.M. "Stata to Python Equivalents." danielmsullivan.com. Accessed 2026-03-28. https://www.danielmsullivan.com/pages/tutorial_stata_to_python.html
- Turrell, A. "Coming from Stata." *Coding for Economists*. aeturrell.github.io. Accessed 2026-03-28. https://aeturrell.github.io/coding-for-economists/coming-from-stata.html
- pandas documentation. "Comparison with Stata." pandas.pydata.org. Accessed 2026-03-28. https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html
- StataCorp. "Data frames: multiple datasets in memory." stata.com. Accessed 2026-03-28. https://www.stata.com/features/overview/multiple-datasets-in-memory/
- Naqvi, A. "The Stata Frames Guide." Medium / The Stata Guide. Accessed 2026-03-28. https://medium.com/the-stata-guide/the-stata-frames-guide-1149b50864e3
- StataCorp. "preserve -- Preserve and restore data." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/ppreserve.pdf
- Statalist. "preserve versus frames." statalist.org. Accessed 2026-03-28. https://www.statalist.org/forums/forum/general-stata-discussion/general/1776237-preserve-versus-frames

---

## 2. Stata's Value Labels System

### How Stata Handles It

Stata has a three-layer labeling system that has no direct equivalent in Python:

**Layer 1: Dataset labels** (`label data "description"`) -- attaches a description to the entire dataset.

**Layer 2: Variable labels** (`label variable varname "description"`) -- attaches a human-readable description to each column. These appear in output, `describe`, and the Variables window.

**Layer 3: Value labels** -- a two-step system that maps integer codes to text labels:

```stata
* Step 1: Define a label set (name -> integer -> text mapping)
label define race_lbl 1 "White" 2 "Black" 3 "Hispanic" 4 "Asian" 5 "Other"

* Step 2: Attach the label set to a variable
label values race race_lbl

* Now 'race' is stored as integers (1-5) but displays as text
tabulate race
*    Race |  Freq.  Percent
*   White |   500     50.0
*   Black |   200     20.0
* Hispanic|   150     15.0
*   Asian |   100     10.0
*   Other |    50      5.0
```

**Critical design choice:** The variable stores *integers* but *displays* text. This means:
- Regression models use the integers directly (no dummy coding needed for ordinal treatment)
- Tabulations show the labels
- The same label set can be attached to multiple variables
- `encode` converts a string variable to labeled numeric; `decode` does the reverse

```stata
* encode: string -> labeled numeric
encode state_name, gen(state_code)
* state_code is now 1, 2, 3... with labels "Alabama", "Alaska", ...

* decode: labeled numeric -> string
decode state_code, gen(state_string)
```

**`label variable` for column descriptions:**

```stata
label variable enrollment "Total student enrollment (K-12), fall count"
label variable frpl_pct "Percent of students eligible for free/reduced price lunch"
```

These descriptive labels appear in Stata's GUI, in `describe` output, and in regression tables -- they serve as built-in documentation.

### How Python Handles It Differently

Python has no built-in equivalent to Stata's value label system. The concept must be approximated through several mechanisms:

**For value labels (integer-to-text mapping):**

```python
# Approach 1: Dictionary mapping (most common)
race_labels = {1: "White", 2: "Black", 3: "Hispanic", 4: "Asian", 5: "Other"}
df = df.with_columns(
    pl.col("race").replace(race_labels).alias("race_label")
)

# Approach 2: Polars Enum type (fixed, ordered categories)
race_enum = pl.Enum(["White", "Black", "Hispanic", "Asian", "Other"])
df = df.with_columns(pl.col("race_str").cast(race_enum))

# Approach 3: Pandas Categorical (closer to Stata but not identical)
pdf["race"] = pd.Categorical(pdf["race"], categories=["White", "Black", "Hispanic", "Asian", "Other"])
```

**For variable labels (column descriptions):**

```python
# No native support in polars or pandas
# Workaround: maintain a metadata dictionary
var_labels = {
    "enrollment": "Total student enrollment (K-12), fall count",
    "frpl_pct": "Percent of students eligible for free/reduced price lunch",
}
```

**Reading Stata files preserves labels:**

```python
# pandas reads Stata value labels via StataReader
import pandas as pd
reader = pd.StataReader("data.dta")
var_labels = reader.variable_labels()    # dict: varname -> label string
val_labels = reader.value_labels()       # dict: labelname -> {int: string}

# pyreadstat offers similar functionality
import pyreadstat
df, meta = pyreadstat.read_dta("data.dta")
meta.column_labels       # variable labels
meta.value_labels        # value labels
```

### Key Mental Model Shift

| Stata | Python |
|-------|--------|
| Data + metadata are unified (labels travel with the dataset) | Data and metadata are separate concerns |
| Integer storage + text display (automatic) | Store as string OR integer (choose one) |
| One label set shared across variables | Each variable manages its own categories |
| `encode`/`decode` bridges strings and numerics | Manual mapping or `.cast()` between types |
| `label variable` documents columns inline | No built-in column documentation |

### Common Mistakes During Transition

1. **Losing labels on import:** When reading `.dta` files, value labels may be converted to strings (losing the integer codes) or ignored entirely, depending on the `convert_categoricals` parameter.
2. **Assuming categoricals equal value labels:** Python's `pd.Categorical` or `pl.Enum` handles ordering and memory efficiency but does not replicate the integer-storage-with-text-display paradigm. Models in Python see the category strings, not hidden integer codes.
3. **Forgetting to encode for modeling:** In Stata, a labeled numeric variable goes directly into regression. In Python, string categoricals must be explicitly dummy-coded (`C(var)` in formulas, `pd.get_dummies()` manually).
4. **Missing variable documentation:** Stata users rely on `label variable` for self-documenting datasets. Python users must maintain documentation externally (DAAF's IAT comments serve a similar purpose).

### Sources

- StataCorp. "How to label the values of categorical variables." stata.com. Accessed 2026-03-28. https://www.stata.com/links/stata-basics/label-values-categorical-variables/
- UCLA Statistical Consulting. "Labeling data." stats.oarc.ucla.edu. Accessed 2026-03-28. https://stats.oarc.ucla.edu/stata/modules/labeling-data/
- Poverty Action. "Value Labels." povertyaction.github.io. Accessed 2026-03-28. https://povertyaction.github.io/guides/cleaning/documentation/valuelabels/
- Plante, T. "Extracting variable labels and categorical/ordinal value labels in Stata." blog.uvm.edu. Accessed 2026-03-28. https://blog.uvm.edu/tbplante/2021/08/04/extracting-variable-labels-and-categorical-ordinal-value-labels-in-stata/
- pandas documentation. "pandas.io.stata.StataReader.variable_labels." pandas.pydata.org. Accessed 2026-03-28. https://pandas.pydata.org/docs/reference/api/pandas.io.stata.StataReader.variable_labels.html
- pandas documentation. "Stata Format." Accessed 2026-03-28. https://tedboy.github.io/pandas/io/io12.html
- GitHub/pandas. "Variable labels as a dataframe field." Issue #11179. Accessed 2026-03-28. https://github.com/pandas-dev/pandas/issues/11179

---

## 3. Stata's Missing Value System

### How Stata Handles It

Stata has a 27-type missing value system that is fundamentally different from any Python approach:

- **System missing:** `.` -- the default missing value
- **Extended missing:** `.a` through `.z` -- 26 additional missing types for encoding *reasons* for missingness (e.g., `.r` = refused, `.d` = don't know, `.n` = not applicable)

**The critical design decision:** Missing values are treated as **positive infinity** in all comparisons. The ordering is:

```
all nonmissing numbers < . < .a < .b < ... < .z
```

This means:

```stata
* DANGEROUS: this includes missing values!
count if income > 50000
* Returns observations with income > 50000 AND observations where income is missing

* CORRECT: explicitly exclude missing
count if income > 50000 & !missing(income)
* Or equivalently:
count if income > 50000 & income < .
```

**Why this design?** Stata uses two-valued logic (true/false), not three-valued logic (true/false/unknown). Every `if` condition must resolve to true or false -- there is no "skip this observation because the value is unknown." Treating missing as +infinity provides consistent behavior: `keep if x > 0` and `drop if x <= 0` produce identical results.

**Extended missing values in practice:**

```stata
* Encode different reasons for missingness
replace income = .r if refused_income == 1
replace income = .d if dont_know_income == 1
replace income = .n if not_applicable == 1

* All three are still "missing" for analysis purposes
summarize income     /* all three excluded from mean calculation */

* But you can distinguish them
count if income == .r    /* number who refused */
count if income == .d    /* number who don't know */
count if income >= .     /* all missing, any type */
```

### How Python Handles It Differently

Python has three distinct missing-value representations, none of which behaves like Stata's:

| Representation | Scope | Comparison Behavior | Aggregation |
|----------------|-------|---------------------|-------------|
| `None` | Python-level | `None == None` is `True` | Coerced to `null` in polars |
| `float("nan")` / `np.nan` | Float columns only | `NaN != NaN` is `True` | **Propagates** through arithmetic |
| `null` (polars) | All column types | Cannot compare with `==` | **Skipped** by default |

**Critical difference:** In Python, `NaN` comparisons always return `False`:

```python
import math
math.nan > 100     # False
math.nan < 100     # False
math.nan == 100    # False
math.nan == math.nan  # False!
```

This is the **opposite** of Stata, where `. > 100` is `True`.

**No extended missing types:** Python has no native way to encode *why* a value is missing. You must use a separate column:

```python
# Python workaround for extended missing types
df = df.with_columns(
    pl.when(pl.col("refused_income") == 1).then(pl.lit("refused"))
      .when(pl.col("dont_know_income") == 1).then(pl.lit("dont_know"))
      .when(pl.col("not_applicable") == 1).then(pl.lit("not_applicable"))
      .otherwise(pl.lit(None))
      .alias("income_missing_reason")
)
```

**Polars null vs NaN trap:**

```python
# In polars, null and NaN are DIFFERENT
df = pl.DataFrame({"x": [1.0, float("nan"), None]})
df.select(pl.col("x").is_null())     # False, False, True
df.select(pl.col("x").is_nan())      # False, True, False
df.select(pl.col("x").mean())        # NaN (NaN propagates!)

# Safe pattern: convert NaN to null first
df.select(pl.col("x").fill_nan(None).mean())  # 1.0
```

### Key Mental Model Shift

| Stata | Python (polars) |
|-------|-----------------|
| Missing = +infinity (`. > 100` is TRUE) | Missing comparison returns False/null |
| 27 missing types (., .a-.z) | One null type; reasons stored separately |
| `if x > 100` INCLUDES missing | `pl.col("x") > 100` EXCLUDES null |
| Two-valued logic (true/false) | Three-valued logic (true/false/null) |
| `missing(x)` detects all types | `.is_null()` for null, `.is_nan()` for NaN |
| Aggregations skip missing by default | Aggregations skip null but propagate NaN |

### Common Mistakes During Transition

1. **The "greater than" trap (Stata to Python):** Stata users learn to always add `& !missing(x)` when using `>` comparisons. In Python, this is unnecessary because null is excluded automatically. But the *habit* of worrying about missing in comparisons is actually a good one -- just the direction of the risk reverses.
2. **The "greater than" trap (Python to Stata):** Python users who start writing Stata code may write `keep if income > 50000` and accidentally include missing observations.
3. **NaN vs null confusion:** When reading Stata `.dta` files, Stata's `.` becomes `NaN` in pandas (float columns) or `null` in polars. If NaN is not converted to null, aggregations will silently propagate NaN through all calculations.
4. **Lost missing-type information:** Extended missing values (.a-.z) are lost when reading into Python. The pyreadstat library preserves them as special NaN values but most downstream operations discard the distinction.
5. **Integer column promotion:** In pandas, any integer column with a missing value gets promoted to float (because NaN is a float). Polars handles this better with nullable integer types.

### Sources

- StataCorp. "Logical expressions and missing values." FAQ. stata.com. Accessed 2026-03-28. https://www.stata.com/support/faqs/data-management/logical-expressions-and-missing-values/
- Statalist. "Why are missing values treated as positive infinity in Stata?" statalist.org. Accessed 2026-03-28. https://www.statalist.org/forums/forum/general-stata-discussion/general/1587053-why-are-missing-values-treated-as-positive-infinity-in-stata
- Poverty Action. "Missing Values." povertyaction.github.io. Accessed 2026-03-28. https://povertyaction.github.io/guides/cleaning/variablemanagement/missingvalues/
- Wlm. "Stata Guide: Missing Values." wlm.userweb.mwn.de. Accessed 2026-03-28. https://wlm.userweb.mwn.de/Stata/wstamiss.htm
- StataCorp. "Missing values -- Quick reference." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/dmissingvalues.pdf
- UCLA Statistical Consulting. "Missing Values." Stata Learning Modules. stats.oarc.ucla.edu. Accessed 2026-03-28. https://stats.oarc.ucla.edu/stata/modules/missing-values/
- *The Stata Journal*. "Stata Tip 86: The Missing() Function." 2010. https://journals.sagepub.com/doi/pdf/10.1177/1536867X1001000210

---

## 4. Stata's `by:` Prefix vs Python Group Operations

### How Stata Handles It

Stata's `by:` prefix (or `bysort:`) is a powerful mechanism that repeats a command for each group defined by one or more variables. Combined with system variables `_n` (observation number within group) and `_N` (total observations in group), it enables complex within-group operations.

```stata
* Sort and group: create group-level statistics
bysort state: gen state_n = _N                          /* count per state */
bysort state: gen state_obs = _n                        /* row number within state */
bysort state (year): gen first_year = year[1]           /* first year per state */
bysort state (year): gen prev_score = test_score[_n-1]  /* lag within group */
bysort state (year): gen lead_score = test_score[_n+1]  /* lead within group */
```

Key aspects of the `by:` system:
- `_n` is the observation number within the current by-group (1-based)
- `_N` is the total number of observations in the current by-group
- `bysort var1 (var2):` sorts by var1 AND var2 but groups only by var1
- Subscript notation `var[_n-1]` accesses the previous observation's value

**`egen` functions extend `by:`:**

```stata
* egen = "extensions to generate" -- group-aware functions
bysort state: egen mean_score = mean(test_score)        /* group mean */
bysort state: egen total_enroll = total(enrollment)     /* group sum */
bysort state: egen sd_score = sd(test_score)            /* group SD */
bysort state: egen rank_score = rank(test_score)        /* within-group rank */
bysort state: egen pct_score = pctile(test_score), p(75) /* group percentile */
egen state_id = group(state)                            /* numeric group ID */
egen quintile = xtile(income), nq(5)                    /* quintile bins */
```

The key design: `egen` with `by:` creates a new column at the *observation level* (not collapsed) -- each row gets its group's statistic. This is different from `collapse`, which reduces the dataset to one row per group.

### How Python Handles It Differently

Python uses explicit `group_by()` operations. The critical distinction is between aggregation (reducing rows) and window/transform operations (preserving rows).

**Polars equivalents:**

```python
# --- Group aggregation (Stata: collapse) ---
state_stats = df.group_by("state").agg(
    pl.col("test_score").mean().alias("mean_score"),
    pl.col("enrollment").sum().alias("total_enroll"),
    pl.len().alias("state_n"),
)

# --- Window functions / transform (Stata: bysort + egen) ---
# Equivalent to bysort state: egen mean_score = mean(test_score)
df = df.with_columns(
    pl.col("test_score").mean().over("state").alias("mean_score"),
    pl.col("enrollment").sum().over("state").alias("total_enroll"),
    pl.len().over("state").alias("state_n"),
)

# --- _n and _N equivalents ---
df = df.with_columns(
    # _n (row number within group, but 0-based in polars)
    pl.col("test_score").cum_count().over("state").alias("state_obs"),
    # _N (group size)
    pl.len().over("state").alias("state_N"),
)

# --- Lag/lead within groups (Stata: var[_n-1]) ---
df = df.sort("state", "year").with_columns(
    pl.col("test_score").shift(1).over("state").alias("prev_score"),
    pl.col("test_score").shift(-1).over("state").alias("lead_score"),
)
```

**Pandas equivalents (for reference):**

```python
# transform = egen (preserves row count)
pdf["mean_score"] = pdf.groupby("state")["test_score"].transform("mean")

# agg = collapse (reduces to groups)
state_stats = pdf.groupby("state")["test_score"].agg(["mean", "sum", "count"])

# _n equivalent
pdf["state_obs"] = pdf.groupby("state").cumcount() + 1  # 1-based to match Stata

# lag within groups
pdf["prev_score"] = pdf.sort_values("year").groupby("state")["test_score"].shift(1)
```

### Key Mental Model Shift

| Stata (`by:` / `egen`) | Python (polars) |
|-------------------------|-----------------|
| `bysort state: egen mean_x = mean(x)` | `pl.col("x").mean().over("state")` |
| `bysort state: gen obs_num = _n` | `pl.col("x").cum_count().over("state")` |
| `bysort state: gen group_size = _N` | `pl.len().over("state")` |
| `bysort state (year): gen lag_x = x[_n-1]` | `pl.col("x").shift(1).over("state")` after sorting |
| `collapse (mean) x, by(state)` | `df.group_by("state").agg(pl.col("x").mean())` |
| `egen quintile = xtile(x), nq(5)` | `pl.col("x").qcut(5, labels=...)` |
| Result always added to THE dataset | Must choose: `.over()` (window) vs `.agg()` (collapse) |

### Common Mistakes During Transition

1. **Confusing aggregation and transformation:** In Stata, `egen` always preserves the original row count (like a window function). In Python, `group_by().agg()` collapses rows -- use `.over()` in polars or `.transform()` in pandas to replicate Stata's behavior.
2. **Forgetting to sort before lag/lead:** Stata's `bysort state (year):` sorts within groups automatically. Polars' `.shift()` operates on whatever order the data is in -- sort first.
3. **0-based vs 1-based `_n`:** Stata's `_n` starts at 1. Python's `.cum_count()` or `.cumcount()` starts at 0.
4. **Subscript access:** Stata's `x[_n-1]` notation for accessing adjacent observations has no direct polars equivalent -- use `.shift()` instead.
5. **Multiple group variables:** `bysort var1 var2:` groups by both. In polars: `.over(["var1", "var2"])`.

### Sources

- Sullivan, D.M. "Stata to Python Equivalents." danielmsullivan.com. Accessed 2026-03-28. https://www.danielmsullivan.com/pages/tutorial_stata_to_python.html
- pandas documentation. "Comparison with Stata." pandas.pydata.org. Accessed 2026-03-28. https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html
- Notre Dame Library. "by, _n, _N." Data Analysis with Stata. libguides.library.nd.edu. Accessed 2026-03-28. https://libguides.library.nd.edu/data-analysis-stata/bnn
- Poverty Action. "Sort, by, bysort, egen." povertyaction.github.io. Accessed 2026-03-28. https://povertyaction.github.io/guides/cleaning/05%20Outcome%20Creation/01%20Sort,%20by,%20bysort,%20and%20egen/

---

## 5. Stata's Estimation / Post-Estimation Workflow

### How Stata Handles It

Stata has a uniquely structured two-phase workflow for statistical modeling that has no direct equivalent in any other language:

**Phase 1: Estimation** -- Run a model. Results are stored in `e()` return values.

```stata
regress wage education experience i.industry, robust
```

**Phase 2: Post-estimation** -- Interrogate the model using specialized commands.

```stata
* Access stored results
display e(N)         /* number of observations */
display e(r2)        /* R-squared */
display e(F)         /* F-statistic */
matrix list e(b)     /* coefficient vector */
matrix list e(V)     /* variance-covariance matrix */

* Specific coefficient access
display _b[education]    /* coefficient on education */
display _se[education]   /* standard error on education */

* Hypothesis testing
test education = experience                /* F-test: are coefficients equal? */
test education experience                  /* F-test: joint significance */

* Linear combinations
lincom education + 2*experience            /* test a linear combination */

* Non-linear combinations
nlcom _b[education] / _b[experience]       /* ratio of coefficients */

* Margins and marginal effects
margins industry                           /* predictive margins by industry */
margins, dydx(education)                   /* average marginal effect */
marginsplot                                /* visualize margins */

* Predictions
predict yhat, xb                           /* fitted values */
predict resid, residuals                   /* residuals */
predict leverage, leverage                 /* leverage values */
```

**The return-value system has two classes:**

| Class | Commands | Access | Replaced By |
|-------|----------|--------|-------------|
| `e()` (estimation) | `regress`, `logit`, `probit`, etc. | `ereturn list` | Next estimation command |
| `r()` (general) | `summarize`, `correlate`, `test`, etc. | `return list` | Next r-class command |

```stata
* r-class example
summarize income
display r(mean)     /* 45000 */
display r(sd)       /* 12000 */
display r(N)        /* 5000 */
gen centered_income = income - r(mean)
```

**Model storage and comparison:**

```stata
* Store multiple models for comparison
regress wage education
estimates store m1
regress wage education experience
estimates store m2
regress wage education experience i.industry
estimates store m3

* Compare models
estimates table m1 m2 m3, star stats(N r2 r2_a)
esttab m1 m2 m3, se r2       /* community-contributed */

* Restore a specific model for post-estimation
estimates restore m2
margins, dydx(education)
```

### How Python Handles It Differently

Python uses a model-object approach where each fitted model is a persistent object with methods and attributes:

```python
import pyfixest as pf
import statsmodels.formula.api as smf

# --- pyfixest approach ---
m1 = pf.feols("wage ~ education", data=pdf)
m2 = pf.feols("wage ~ education + experience", data=pdf)
m3 = pf.feols("wage ~ education + experience | industry", data=pdf)

# Access results (attributes on the model object)
m1.coef()                 # coefficient series
m1.se()                   # standard errors
m1.nobs                   # number of observations
m1.r2                     # R-squared

# Model comparison table
pf.etable([m1, m2, m3])

# --- statsmodels approach ---
result = smf.ols("wage ~ education + experience + C(industry)", data=pdf).fit(
    cov_type="HC1"        # robust SEs
)

# Access results
result.params             # coefficient series
result.bse                # standard errors
result.rsquared           # R-squared
result.nobs               # observations
result.conf_int()         # confidence intervals
result.summary()          # full summary table

# Hypothesis testing
result.f_test("education = experience")           # F-test
result.t_test("education + 2*experience = 0")     # linear combination

# Predictions
result.predict()          # fitted values
result.resid              # residuals
```

**For margins/marginal effects, Python uses the `marginaleffects` package:**

```python
import marginaleffects as me

# Average marginal effects (Stata: margins, dydx(education))
me.avg_slopes(result, variables="education")

# Predictive margins by group (Stata: margins industry)
me.avg_predictions(result, by="industry")

# Marginal effects at specific values
me.slopes(result, variables="education", newdata=datagrid(experience=[5, 10, 15]))
```

### Key Mental Model Shift

| Stata | Python |
|-------|--------|
| One active estimation result at a time | Multiple model objects coexist |
| `e()` / `r()` global return values | Attributes/methods on model objects |
| `estimates store m1` to save | `m1 = model.fit()` (already saved) |
| `estimates restore m1` to reactivate | Just use `m1.attribute` directly |
| `_b[varname]`, `_se[varname]` | `result.params["varname"]`, `result.bse["varname"]` |
| `test var1 = var2` | `result.f_test("var1 = var2")` |
| `lincom` / `nlcom` | `result.t_test()` / manual delta method |
| `margins` (built-in, universal) | `marginaleffects` package (separate install) |
| `predict newvar, xb` | `result.predict()` (returns array, not added to dataset) |
| `esttab` (community) | `pf.etable()` or `stargazer` |

### Common Mistakes During Transition

1. **Expecting global state:** Stata users expect `e(r2)` to be available after running a regression. In Python, you must capture the result object: `result = model.fit()`. If you forget to assign it, the results are lost.
2. **Overwriting results:** In Stata, running a new regression overwrites `e()`. In Python, each `model.fit()` returns an independent object -- you can have as many as memory allows.
3. **Missing `margins` equivalent:** Stata's `margins` command is extraordinarily powerful and built-in. Python requires the separate `marginaleffects` package, which covers most but not all `margins` functionality.
4. **Post-estimation command availability:** Stata's post-estimation ecosystem (dozens of `estat` commands per model type) has no unified equivalent in Python. You must find the right method on the right results object.
5. **`predict` adds to dataset vs returns array:** Stata's `predict newvar, xb` creates a new column in the dataset. Python's `result.predict()` returns an array that must be explicitly added to the DataFrame.

### Sources

- UCLA Statistical Consulting. "How can I access information stored after I run a command in Stata (returned results)?" stats.oarc.ucla.edu. Accessed 2026-03-28. https://stats.oarc.ucla.edu/stata/faq/how-can-i-access-information-stored-after-i-run-a-command-in-stata-returned-results/
- StataCorp. "estimates store." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/restimatesstore.pdf
- StataCorp. "Estimation and postestimation commands." User's Guide, Ch. 20. stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/u20.pdf
- GitHub/statsmodels. "FAQ: statsmodels for Stata users." Issue #1718. Accessed 2026-03-28. https://github.com/statsmodels/statsmodels/issues/1718
- Arel-Bundock, V., Greifer, N., Heiss, A. "marginaleffects: Marginal Effects for Model Objects." *Journal of Statistical Software* (forthcoming). marginaleffects.com. Accessed 2026-03-28. https://marginaleffects.com/
- Tidy Intelligence. "Tidy Fixed Effects Regressions: fixest vs pyfixest." blog.tidy-intelligence.com. Accessed 2026-03-28. https://blog.tidy-intelligence.com/posts/fixed-effects-regressions/

---

## 6. Stata's Do-file Execution Model

### How Stata Handles It

Stata's execution model is built around three interrelated concepts:

**1. Do-files (.do) -- sequential script execution:**

```stata
* typical_analysis.do
clear all
set more off
log using "analysis_log.txt", replace

* Load data
use "schools.dta", clear

* Clean
drop if missing(enrollment)
gen log_enroll = log(enrollment)

* Analyze
regress test_score log_enroll poverty_rate, robust
estimates store m1

* Export
esttab m1 using "results.rtf", replace se r2

log close
```

Key characteristics:
- Do-files execute sequentially, top-to-bottom
- `clear all` resets state at the start (defensive programming)
- `log using` captures ALL output (commands + results) to a file
- `set more off` prevents pagination pauses
- Commands modify the single in-memory dataset
- No function definitions, no imports, no module system

**2. Log files -- complete audit trail:**

```stata
log using "my_analysis.log", replace text
* Every command and its output is captured
summarize income
*   Variable |  Obs   Mean    Std. dev.    Min    Max
*   income   | 5000  45000    12000       10000  200000
log close
```

The log captures both the command AND its output -- creating a complete record of what was done and what happened.

**3. Ado-files (.ado) -- community extensions:**

Ado-files are Stata programs stored as text files. When Stata encounters a command it doesn't recognize, it searches for an ado-file of that name in predefined directories:

```
PERSONAL:  ~/ado/personal/
PLUS:      ~/ado/plus/        (ssc install goes here)
SITE:      /usr/local/ado/
BASE:      /usr/local/stata/ado/base/
```

Installing community commands:

```stata
ssc install reghdfe          /* from SSC archive */
net install ftools, from("https://...")   /* from URL */
```

Once installed, community commands are indistinguishable from built-in commands.

### How Python Handles It Differently

**Script execution (DAAF file-first model):**

```python
# 01_clean-schools.py
# --- Config ---
import polars as pl
BASE_DIR = "/daaf"
PROJECT_DIR = f"{BASE_DIR}/research/2026-01-24_School_Analysis"

# --- Load ---
df = pl.read_parquet(f"{PROJECT_DIR}/data/raw/schools.parquet")

# --- Transform ---
df = df.filter(pl.col("enrollment").is_not_null())
df = df.with_columns(pl.col("enrollment").log().alias("log_enroll"))

# --- Validate ---
assert df.height > 0, "No rows remaining after filter"
print(f"Rows: {df.height}")

# --- Save ---
df.write_parquet(f"{PROJECT_DIR}/data/processed/schools_clean.parquet")
```

Executed via: `bash run_with_capture.sh scripts/01_clean-schools.py`

**Key differences:**

| Stata Do-file | Python Script (DAAF) |
|---------------|----------------------|
| `log using` captures all output | `run_with_capture.sh` appends stdout/stderr to script |
| `clear all` resets environment | Each script starts fresh (no shared state) |
| Commands auto-apply to one dataset | Must specify DataFrame for every operation |
| `ssc install pkg` for community code | `pip install pkg` or `uv add pkg` |
| Ado-files auto-discovered by name | `import package` must be explicit |
| `.do` files can call other `.do` files | Python scripts are independent |
| Interactive line-by-line execution common | File-first execution (DAAF requirement) |

**DAAF's `run_with_capture.sh` serves the same purpose as `log using`:**
- Stata: `log using analysis.log, replace` captures commands + output
- DAAF: `run_with_capture.sh script.py` appends stdout/stderr to the script file

Both create an audit trail where the researcher can see what was executed and what happened. DAAF's approach goes further by making the output part of the script file itself (immutable after execution).

### Key Mental Model Shift

| Stata | Python (DAAF) |
|-------|---------------|
| Interactive REPL is primary workflow | File-first execution (no interactive REPL) |
| One script modifies one dataset across stages | Each stage has its own script |
| `log using` = audit trail | `run_with_capture.sh` = audit trail |
| Ado-files extend Stata transparently | Packages imported explicitly |
| `do "other_script.do"` nests scripts | Scripts are independent units |
| `clear all` + `use data` = fresh start | Each script loads its own input |
| Output = printed results | Output = parquet files + print validation |

### Common Mistakes During Transition

1. **Missing the REPL:** Stata users are accustomed to executing commands interactively and seeing results immediately. DAAF's file-first requirement feels restrictive but produces better audit trails.
2. **Expecting global state across scripts:** In Stata, variables from a previous `do` file persist. In DAAF, each script is independent -- data must be saved and loaded.
3. **Not capturing output:** Stata's `log using` is familiar. Python users must remember to use `run_with_capture.sh`, not bare `python script.py`.
4. **Monolithic scripts:** Stata users often write one long do-file for an entire analysis. DAAF's stage-based script organization (stage5_fetch, stage6_clean, etc.) requires breaking work into smaller units.

### Sources

- StataCorp. "16 Do-files." User's Guide. stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals13/u16.pdf
- StataCorp. "17 Ado-files." User's Guide. stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals13/u17.pdf
- DIME Wiki. "Stata Coding Practices: Programming (Ado-files)." dimewiki.worldbank.org. Accessed 2026-03-28. https://dimewiki.worldbank.org/Stata_Coding_Practices:_Programming_(Ado-files)
- COMET/UBC. "Working with Do-Files." comet.arts.ubc.ca. Accessed 2026-03-28. https://comet.arts.ubc.ca/docs/5_Research/econ490-stata/02_Working_Dofiles.html
- Reinbergs, E. "Stata .do file template." erikreinbergs.com. Accessed 2026-03-28. https://www.erikreinbergs.com/stata-do-file-template/
- University of South Australia. "Introduction to Stata: Using do and log files." lo.unisa.edu.au. Accessed 2026-03-28. https://lo.unisa.edu.au/mod/book/view.php?id=641259&chapterid=103833
- StataCorp. "ssc -- Install and uninstall packages from SSC." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/rssc.pdf

---

## 7. Stata's String and Date Handling

### String Functions

Stata's string functions are standalone functions (not methods on objects). The key functions:

| Stata Function | Purpose | Python / Polars Equivalent |
|----------------|---------|---------------------------|
| `substr(s, n1, n2)` | Extract substring from position n1, length n2 | `pl.col("s").str.slice(n1-1, n2)` (0-based) |
| `strpos(s1, s2)` | Position of s2 in s1 (0 if not found) | `pl.col("s1").str.find(s2)` (-1 if not found) |
| `subinstr(s1, s2, s3, n)` | Replace first n occurrences of s2 with s3 | `pl.col("s1").str.replace(s2, s3)` / `.str.replace_all()` |
| `regexm(s, re)` | Regex match (returns 0/1) | `pl.col("s").str.contains(re)` |
| `regexs(n)` | Return nth capture group from last regexm | `pl.col("s").str.extract(re, n)` |
| `strtrim(s)` | Remove leading and trailing whitespace | `pl.col("s").str.strip_chars()` |
| `strlower(s)` / `strupper(s)` | Case conversion | `.str.to_lowercase()` / `.str.to_uppercase()` |
| `strproper(s)` | Title case | `.str.to_titlecase()` |
| `word(s, n)` | Extract nth word (space-separated) | `.str.split(" ").list.get(n-1)` (0-based) |
| `strlen(s)` | String length (bytes) | `.str.len_bytes()` |
| `ustrlen(s)` | String length (characters, Unicode-aware) | `.str.len_chars()` |
| `string(n)` | Number to string | `.cast(pl.Utf8)` |
| `real(s)` | String to number | `.cast(pl.Float64)` |
| `destring varname, replace` | In-place string to numeric | `.cast(pl.Int64)` or `.cast(pl.Float64)` |

```stata
* Stata string operations
gen clean_name = strtrim(strlower(name))
gen state_abbr = substr(fips_code, 1, 2)
gen has_elementary = regexm(school_type, "Elementary")
gen name_length = ustrlen(school_name)
gen first_word = word(address, 1)
replace phone = subinstr(phone, "-", "", .)    /* remove all dashes */
```

```python
# Polars equivalents
df = df.with_columns(
    pl.col("name").str.to_lowercase().str.strip_chars().alias("clean_name"),
    pl.col("fips_code").str.slice(0, 2).alias("state_abbr"),
    pl.col("school_type").str.contains("Elementary").alias("has_elementary"),
    pl.col("school_name").str.len_chars().alias("name_length"),
    pl.col("address").str.split(" ").list.first().alias("first_word"),
    pl.col("phone").str.replace_all("-", "").alias("phone"),
)
```

**Key differences:**
- Stata string positions are 1-based; Python is 0-based
- Stata's `strpos` returns 0 for not-found; Python returns -1
- Stata's `subinstr` with missing n replaces all; polars distinguishes `replace` (first) vs `replace_all`
- Stata's `regexm` + `regexs` is a two-step process; polars `.str.extract()` does both at once
- Stata's `word()` is 1-based; the polars equivalent via `.list.get()` is 0-based

### Date System

Stata dates are fundamentally different from Python dates -- they are plain integers with display formatting.

**The epoch:** January 1, 1960 = day 0.

| Stata Date Type | Storage Unit | Format Code | Example Value |
|-----------------|-------------|-------------|---------------|
| Daily date | Days since 1960-01-01 | `%td` | 0 = 01jan1960 |
| Clock (datetime) | Milliseconds since 1960-01-01 00:00:00 | `%tc` | 0 = midnight |
| Monthly | Months since 1960m1 | `%tm` | 0 = 1960m1 |
| Quarterly | Quarters since 1960q1 | `%tq` | 0 = 1960q1 |
| Weekly | Weeks since 1960w1 | `%tw` | 0 = 1960w1 |
| Yearly | Just the year number | `%ty` | 1960 = 1960 |

```stata
* String-to-date conversion
gen date = date("March 15, 2024", "MDY")     /* daily date */
gen dt = clock("2024-03-15 14:30", "YMD hm") /* datetime */
format date %td                                /* display format */
format dt %tc

* Date from components
gen date2 = mdy(3, 15, 2024)                 /* from month, day, year */
gen monthly = ym(2024, 3)                      /* from year, month */

* Date extraction
gen y = year(date)
gen m = month(date)
gen d = day(date)
gen dow = dow(date)       /* day of week: 0=Sunday */
gen doy = doy(date)       /* day of year */
gen q = quarter(date)

* Date arithmetic
gen next_month = date + 30              /* just add days */
gen monthly_diff = mofd(date2) - mofd(date1)  /* months between dates */
```

**Critical: Stata dates are just integers.** Without a format applied, they display as raw numbers. The `%td` format tells Stata *how to display* the integer, not how to store it. This is fundamentally different from Python, where dates are typed objects.

```python
# Python / polars date handling
df = df.with_columns(
    # String to date (explicit format string required)
    pl.col("date_str").str.to_date("%B %d, %Y").alias("date"),
    pl.col("dt_str").str.to_datetime("%Y-%m-%d %H:%M").alias("datetime"),
)

# Date from components (no direct equivalent -- build string then parse)
df = df.with_columns(
    pl.concat_str([
        pl.col("year").cast(pl.Utf8),
        pl.lit("-"),
        pl.col("month").cast(pl.Utf8).str.pad_start(2, "0"),
        pl.lit("-"),
        pl.col("day").cast(pl.Utf8).str.pad_start(2, "0"),
    ]).str.to_date("%Y-%m-%d").alias("date")
)

# Date extraction
df = df.with_columns(
    pl.col("date").dt.year().alias("y"),
    pl.col("date").dt.month().alias("m"),
    pl.col("date").dt.day().alias("d"),
    pl.col("date").dt.weekday().alias("dow"),  # 1=Monday (not 0=Sunday like Stata)
    pl.col("date").dt.ordinal_day().alias("doy"),
    pl.col("date").dt.quarter().alias("q"),
)

# Date arithmetic
df = df.with_columns(
    (pl.col("date") + pl.duration(days=30)).alias("next_month"),
)

# Monthly difference (no direct Stata mofd() equivalent)
df = df.with_columns(
    ((pl.col("date2").dt.year() - pl.col("date1").dt.year()) * 12
     + (pl.col("date2").dt.month() - pl.col("date1").dt.month())).alias("monthly_diff"),
)
```

### Key Mental Model Shift

| Stata Dates | Python Dates |
|-------------|-------------|
| Integers with display formats | Typed Date/Datetime objects |
| Epoch: January 1, 1960 | Epoch: varies (Unix: 1970-01-01) |
| `date("Mar 15 2024", "MDY")` = mask-based parsing | `str.to_date("%B %d %Y")` = strftime format |
| `%td` format controls display only | Type system controls both storage and display |
| `mdy(3, 15, 2024)` builds from components | Build string then parse (no direct equivalent) |
| Date arithmetic = integer arithmetic | Date arithmetic requires duration objects |
| `dow()` returns 0=Sunday | `weekday()` returns 1=Monday |

### Common Gotchas

1. **Epoch mismatch:** When reading Stata `.dta` files, date values need conversion from the 1960 epoch. `pd.read_stata()` handles this automatically, but raw integer values will be wrong if interpreted as Unix timestamps.
2. **Format string differences:** Stata uses "MDY", "YMD", "DMY" masks. Python uses strftime codes ("%m/%d/%Y", "%Y-%m-%d"). Getting the format wrong produces nulls in polars (silent failure).
3. **Day-of-week numbering:** Stata: 0=Sunday. Polars: 1=Monday. Off-by-one errors are common.
4. **`mdy()` has no polars equivalent:** Stata's `mdy(month, day, year)` constructs dates from components directly. Polars requires building a string first, then parsing.
5. **Integer display:** A Stata date variable without `format %td` applied looks like "23350" (meaningless to a human). Python dates always display in human-readable form.

### Sources

- Stata Blog. "A tour of datetime in Stata." blog.stata.com. 2015. Accessed 2026-03-28. https://blog.stata.com/2015/12/17/a-tour-of-datetime-in-stata-i/
- StataCorp. "Datetime -- Date and time values." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/ddatetime.pdf
- StataCorp. "25 Working with dates and times." User's Guide. stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/u25.pdf
- UCLA Statistical Consulting. "How can I turn a string variable containing dates into a date variable?" stats.oarc.ucla.edu. Accessed 2026-03-28. https://stats.oarc.ucla.edu/stata/faq/how-can-i-turn-a-string-variable-containing-dates-into-a-date-variable-stata-can-recognize/
- SSCC/UW-Madison. "Working with Text Data (Strings) in Stata." sscc.wisc.edu. Accessed 2026-03-28. https://sscc.wisc.edu/sscc/pubs/stata_text/stata_text.html
- pandas documentation. "Comparison with Stata." pandas.pydata.org. Accessed 2026-03-28. https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html
- StataTex Blog. "Useful string functions in Stata." statatexblog.com. 2022. Accessed 2026-03-28. https://statatexblog.com/2022/10/17/useful-string-functions-in-stata/

---

## 8. Stata's Macro System

### How Stata Handles It

Stata's macro system is a text-substitution mechanism fundamentally different from Python variables. Macros store text strings that are *substituted* into commands before execution.

**Local macros** (scoped to current do-file or program):

```stata
* Define a local macro
local controls "education experience age"
local outcome "wage"
local year 2024

* Use a local macro (backtick + apostrophe)
regress `outcome' `controls'
* Stata sees: regress wage education experience age

* Numeric expression
local threshold = 50000
keep if income > `threshold'

* Extended macro functions
local ncontrols : word count `controls'    /* = 3 */
local first_var : word 1 of `controls'     /* = "education" */
```

**Critical syntax:** Local macros are referenced with a **backtick** (`) on the left and an **apostrophe** (') on the right: `` `macroname' ``. This is a constant source of confusion for new Stata programmers and is unlike any syntax in Python.

**Global macros** (persist for entire session):

```stata
* Define a global macro
global datadir "C:/projects/school_analysis/data/"
global controls "education experience age"

* Use a global macro (dollar sign)
use "${datadir}schools.dta", clear
regress wage $controls
```

**Macros in loops:**

```stata
* Looping over variables using local macros
local outcomes "math_score reading_score science_score"
foreach outcome of local outcomes {
    regress `outcome' poverty_rate, robust
    estimates store m_`outcome'
}

* Looping over values
forvalues year = 2015/2024 {
    use "data_`year'.dta", clear
    gen sample_year = `year'
    save "processed_`year'.dta", replace
}
```

**Extended macro functions** provide programmatic access to metadata:

```stata
local vartype : type income           /* "float", "str20", etc. */
local varlabel : variable label income  /* variable label text */
local vallabel : value label race      /* name of value label attached */
local nobs = _N                        /* store observation count */
```

### How Python Handles It Differently

Python variables are direct value bindings, not text-substitution macros. The concept is much simpler but lacks some of Stata's string-building flexibility.

```python
# Python equivalents of Stata macros
controls = ["education", "experience", "age"]
outcome = "wage"
year = 2024
datadir = "/projects/school_analysis/data/"

# Use in a formula (string concatenation or f-strings)
formula = f"{outcome} ~ {' + '.join(controls)}"
# formula = "wage ~ education + experience + age"
model = pf.feols(formula, data=pdf)

# Loop over outcomes
outcomes = ["math_score", "reading_score", "science_score"]
results = {}
for outcome in outcomes:
    results[outcome] = pf.feols(f"{outcome} ~ poverty_rate", data=pdf)

# Loop over years
for year in range(2015, 2025):
    df = pl.read_parquet(f"data_{year}.parquet")
    df = df.with_columns(pl.lit(year).alias("sample_year"))
    df.write_parquet(f"processed_{year}.parquet")
```

### Key Mental Model Shift

| Stata Macros | Python Variables |
|--------------|-----------------|
| Text substitution (evaluated at parse time) | Value binding (evaluated at runtime) |
| `` `localname' `` (backtick-apostrophe) | `variable_name` (bare name) |
| `$globalname` | `variable_name` (no scope distinction in syntax) |
| `local x "a b c"` stores a string | `x = ["a", "b", "c"]` stores a list |
| Macro expanded *before* command parses | Variables resolved *during* execution |
| Extended macro functions for metadata | Built-in functions, type introspection |
| Macros can build variable names dynamically | f-strings build strings; dict keys for dynamic access |

**The substitution model matters.** In Stata, `` regress `outcome' `controls' `` first substitutes the macro text, producing `regress wage education experience age`, then Stata parses and executes that text. In Python, `pf.feols(formula, data=pdf)` passes a string *object* to a function -- there is no pre-parse text substitution step.

This means Stata macros can construct *any* part of a command dynamically:

```stata
* This works in Stata because macros are text substitution
local cmd "regress"
local opts ", robust"
`cmd' wage education `opts'
* Expands to: regress wage education, robust
```

In Python, this level of dynamic command construction requires `eval()` or similar metaprogramming, which is generally discouraged.

### Common Mistakes During Transition

1. **Backtick confusion:** Stata's `` `macro' `` syntax is unlike anything in Python. New Stata users consistently mix up backticks and apostrophes; transitioning users find Python's bare variable names refreshingly simple.
2. **Scope expectations:** Stata's local/global distinction maps roughly to Python's function-local/module-level scope, but Stata's globals persist across `do` files in a session while Python scripts are isolated.
3. **String vs list:** A Stata macro `local x "a b c"` stores a single space-separated string. Python would naturally use a list: `x = ["a", "b", "c"]`. When building formulas, Python users join lists: `" + ".join(controls)`.
4. **Dynamic variable names:** Stata users often build variable names dynamically with macros: `` gen `varprefix'_`year' = ... ``. Python achieves this with f-strings in column names: `f"{prefix}_{year}"`.

### Sources

- Wlm. "Stata Guide: Macros." wlm.userweb.mwn.de. Accessed 2026-03-28. https://wlm.userweb.mwn.de/Stata/wstatmac.htm
- StataCorp. "macro -- Macro definition and manipulation." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/pmacro.pdf
- StataCorp. "18 Programming Stata." User's Guide. stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals13/u18.pdf
- NYU Shanghai. "Automating Your Work." shanghai.hosting.nyu.edu. Accessed 2026-03-28. https://shanghai.hosting.nyu.edu/data/stata/automating-your-work.html
- The Analysis Factor. "Macros in Stata, Why and How to Use Them." theanalysisfactor.com. Accessed 2026-03-28. https://www.theanalysisfactor.com/macros-stata-why-how/
- Stata Blog. "Programming an estimation command in Stata: Global macros versus local macros." blog.stata.com. 2015. Accessed 2026-03-28. https://blog.stata.com/2015/11/03/programming-an-estimation-command-in-stata-global-macros-versus-local-macros/
- UVA Library. "Stata Basics: foreach and forvalues." library.virginia.edu. Accessed 2026-03-28. https://library.virginia.edu/data/articles/stata-basics-foreach-and-forvalues
- Rodriquez, G. "Programming Stata." grodri.github.io. Accessed 2026-03-28. https://grodri.github.io/stata/programming

---

## Additional Cross-Cutting Paradigm Differences

### Panel Data / Time Series Declarations

Stata requires explicit declaration of panel structure:

```stata
xtset state_id year            /* declare panel structure */
gen lag_score = L.test_score   /* lag operator */
gen lead_score = F.test_score  /* lead operator */
gen diff_score = D.test_score  /* first difference */
gen S4.score                    /* seasonal difference (4 periods) */
```

Python has no equivalent "declaration" -- panel operations must be explicit:

```python
# Polars -- sort and shift within groups
df = df.sort("state_id", "year").with_columns(
    pl.col("test_score").shift(1).over("state_id").alias("lag_score"),
    pl.col("test_score").shift(-1).over("state_id").alias("lead_score"),
    (pl.col("test_score") - pl.col("test_score").shift(1).over("state_id")).alias("diff_score"),
)
```

### Merge Paradigm

Stata requires specifying merge type and produces a `_merge` diagnostic variable:

```stata
merge 1:1 school_id using "other.dta"
tab _merge
keep if _merge == 3    /* keep only matched */
drop _merge
```

Python infers merge type from key uniqueness:

```python
merged = df1.join(df2, on="school_id", how="inner")  # no _merge diagnostic
```

Stata's `_merge` variable (values 1=master only, 2=using only, 3=matched) has no automatic equivalent in polars. DAAF's validation checkpoints should include merge diagnostics explicitly.

### In-Place Modification vs Functional Returns

```stata
* Stata: commands modify the dataset in place
drop if missing(income)        /* dataset is now smaller */
gen log_income = log(income)   /* new column added */
replace income = income / 1000 /* column modified */
rename income income_thousands /* column renamed */
```

```python
# Polars: operations return new DataFrames
df = df.filter(pl.col("income").is_not_null())              # new DataFrame
df = df.with_columns(pl.col("income").log().alias("log_income"))  # new DataFrame
df = df.with_columns((pl.col("income") / 1000).alias("income"))  # new DataFrame
df = df.rename({"income": "income_thousands"})               # new DataFrame
```

### Weighted Operations

Stata has built-in weight syntax across most commands:

```stata
summarize income [aw=weight]              /* analytic weights */
regress outcome treatment [pw=weight]     /* probability weights */
tabulate race [fw=freq_weight]            /* frequency weights */
```

Python requires explicit handling per library:

```python
# Weighted mean in polars
weighted_mean = (df["income"] * df["weight"]).sum() / df["weight"].sum()

# Weighted regression in statsmodels
import statsmodels.api as sm
model = sm.WLS(y, X, weights=pdf["weight"]).fit()

# Survey weights via svy skill
import samplics
# ... design specification required
```

### Sources (Additional)

- StataCorp. "tsset -- Declare data to be time-series data." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/tstsset.pdf
- StataCorp. "xtset -- Declare data to be panel data." stata.com/manuals. Accessed 2026-03-28. https://www.stata.com/manuals/xtxtset.pdf
- StataCorp. "Time-series operators." FAQ. stata.com. Accessed 2026-03-28. https://www.stata.com/support/faqs/statistics/time-series-operators/

---

## Summary: Top 10 Paradigm Friction Points for Stata-to-Python Transition

| # | Friction Point | Stata Way | Python Way | Severity |
|---|---------------|-----------|------------|----------|
| 1 | One dataset vs many | Implicit single dataset | Explicit named DataFrames | HIGH |
| 2 | Missing = +infinity | `. > 100` is TRUE | `null > 100` is null/excluded | CRITICAL |
| 3 | Value labels | Integer storage + text display | String or categorical (choose one) | HIGH |
| 4 | by: prefix / _n / _N | `bysort state: gen x = _n` | `.over("state")`, `.shift()`, `.cum_count()` | MEDIUM |
| 5 | Post-estimation workflow | `e(r2)`, `test`, `margins` | Model object attributes + marginaleffects pkg | HIGH |
| 6 | In-place modification | `keep`, `drop`, `replace` modify dataset | Operations return new DataFrames | MEDIUM |
| 7 | Macro system | Text substitution (`` `macro' ``) | Python variables + f-strings | LOW |
| 8 | Date system | Integers + `%td` format from 1960 epoch | Typed Date objects | MEDIUM |
| 9 | Do-file / log workflow | `log using` captures everything | `run_with_capture.sh` for audit trail | LOW |
| 10 | Panel declaration | `xtset id time` + `L.` / `F.` / `D.` | Explicit sort + `.shift()` + `.over()` | MEDIUM |

**Severity key:**
- CRITICAL = Will cause silent data errors if not addressed
- HIGH = Major workflow disruption; requires significant conceptual remapping
- MEDIUM = Noticeable difference; requires learning new syntax
- LOW = Conceptually similar; mainly syntactic adaptation
