# Python-to-R Gotchas and False Friends

Common mistakes Python users make when reading or writing R, organized from most
dangerous/frequent to least. Each entry documents what Python users expect, what
R actually does, and the correct approach.

This reference focuses on the DAAF R stack: tidyverse for data manipulation,
fixest for modeling, and ggplot2 for visualization.

> **Versions referenced:**
> R: R 4.5.3
> Python: Python 3.12, polars 1.39.3
> See SKILL.md § Library Versions for the complete version table.

---

## False Friends: Syntax

These are constructs that look similar between Python and R but behave differently.

| Python | R Attempt | Trap | Correct R |
|--------|-----------|------|-----------|
| `=` (assignment) | `=` | Works but unconventional | `<-` for assignment |
| `True` / `False` | `True` / `False` | `Error: object 'True' not found` | `TRUE` / `FALSE` |
| `None` | `None` | `Error: object 'None' not found` | `NA` or `NULL` |
| `x[0]` (first element) | `x[0]` | Returns empty vector (0 is not a valid index) | `x[1]` (1-based) |
| `x[-1]` (last element) | `x[-1]` | **Removes** the first element (negative indexing = exclusion) | `x[length(x)]` or `tail(x, 1)` |
| `[1, 2, 3]` (list) | `[1, 2, 3]` | Syntax error | `c(1, 2, 3)` |
| `{"key": "val"}` (dict) | `{"key": "val"}` | Syntax error | `list(key = "val")` |
| `len(x)` | `len(x)` | No `len()` function | `length(x)` or `nrow(df)` |
| `x.append(val)` | `x.append(val)` | No method dispatch on vectors | `x <- c(x, val)` |
| `print("text")` | `print("text")` | Works but adds `[1]` prefix | `cat("text\n")` for clean output |
| `assert condition` | `assert condition` | No `assert` keyword | `stopifnot(condition)` |
| `for i in range(10):` | `for i in range(10):` | No `range()` function | `for (i in 1:10) { }` or `seq_len(10)` |
| `if x:` | `if (x)` | Missing parentheses | `if (x) { }` (parentheses required) |
| `elif` | `elif` | Not a keyword | `else if` |
| `import pkg` | `import(pkg)` | Not how R loads packages | `library(pkg)` |
| `f"value: {x}"` | No direct equivalent | No f-strings | `glue::glue("value: {x}")` or `paste0("value: ", x)` |
| `# comment` | `# comment` | Same! | `# comment` |
| `"""docstring"""` | `"""docstring"""` | Syntax error | `#' @description` (roxygen) or `#` comments |
| `and` / `or` (scalar) | `and` / `or` | Not keywords | `&&` / `||` (scalar) |
| `&` / `|` (bitwise/vectorized) | `&` / `|` | Same meaning (vectorized logical) | `&` / `|` (same!) |
| `not x` | `not x` | Not a keyword | `!x` |
| `x % 2` (modulo) | `x %% 2` | Double percent for modulo | `x %% 2` |
| `x // 2` (integer division) | `x %/% 2` | Percent-slash-percent | `x %/% 2` |
| `x ** 2` (power) | `x ** 2` | Actually works in R! | `x^2` (conventional) or `x ** 2` |

---

## Data Manipulation Traps

### 1. Negative Indexing Means Exclusion

**Severity:** Very high -- silent wrong results.

**What Python does:** `x[-1]` returns the last element.
**What R does:** `x[-1]` **removes** the first element and returns everything else.

```r
x <- c(10, 20, 30, 40)
x[-1]      # c(20, 30, 40) -- REMOVES first element
x[-c(1,2)] # c(30, 40) -- REMOVES first two elements

# To get the last element:
x[length(x)]  # 40
tail(x, 1)    # 40
```

### 2. 1-Based Indexing Throughout

**Severity:** High -- off-by-one errors everywhere.

```r
x <- c("a", "b", "c")
x[1]    # "a" (not x[0])
x[1:3]  # "a", "b", "c" (inclusive on both ends!)
```

R's `x[1:3]` returns elements 1, 2, AND 3. Python's `x[0:3]` returns elements
at indices 0, 1, and 2. Both give three elements but the convention differs.

### 3. `=` vs `<-` for Assignment

**Severity:** Medium -- works but marks you as a Python transplant.

```r
# Both work, but <- is conventional:
x <- 5     # R convention
x = 5      # Works but considered bad style by R community

# Where = and <- actually differ:
f(x = 5)   # Named argument to function
f(x <- 5)  # Assigns 5 to x in calling scope, then passes
```

Inside function calls, `=` passes a named argument while `<-` performs assignment
in the parent scope. This subtle difference is why R uses `<-` for assignment.

### 4. R Recycles Vectors Silently

**Severity:** High -- silent wrong results.

```r
x <- c(1, 2, 3, 4, 5, 6)
y <- c(10, 20)
x + y    # c(11, 22, 13, 24, 15, 26) -- y recycled!
```

**What Python does:** Raises an error for mismatched lengths.
**What R does:** Silently repeats the shorter vector to match the longer one.
If the longer is not a multiple of the shorter, R gives a warning (not an error).

### 5. Single `[` vs Double `[[` for Lists

**Severity:** Medium -- confusing behavior.

```r
my_list <- list(a = 1, b = "hello", c = TRUE)
my_list["a"]     # Returns a LIST containing element a
my_list[["a"]]   # Returns the VALUE of element a (like Python dict access)
my_list$a        # Same as [["a"]] -- shorthand
```

Python's `my_dict["key"]` is equivalent to R's `my_list[["key"]]` or `my_list$key`.
Single bracket `[` returns a sub-list, not the element itself.

### 6. NA Propagation in Comparisons

**Severity:** High -- silent filter failures.

```r
x <- c(1, NA, 3)
x == 1       # TRUE, NA, FALSE (not TRUE, FALSE, FALSE!)
x > 2        # FALSE, NA, TRUE

# This filter includes NA rows!
df |> filter(x == 1 | x > 2)  # Rows where x is 1, 3, AND NA

# Safe pattern:
df |> filter(!is.na(x) & (x == 1 | x > 2))
```

**What Python does:** `None == 1` returns `False`. Polars' `null` comparisons
return `null` (filtered out by `filter()`).
**What R does:** `NA == 1` returns `NA`, which in logical contexts can propagate
through `|` operations. dplyr's `filter()` drops NA results, but base R's `[`
subsetting keeps them.

---

## Modeling Traps

### 1. No `.fit()` Needed

**What Python users expect:** `smf.ols("y ~ x", data=df).fit()` -- two steps.
**What R does:** `lm(y ~ x, data = df)` -- returns a fitted model directly.

```r
# R -- one step
fit <- lm(y ~ x1 + x2, data = df)
summary(fit)   # Works immediately

# fixest -- also one step
fit <- feols(y ~ x1 + x2 | fe, data = df)
```

### 2. Formula Is Not a String

**What Python users expect:** `"y ~ x1 + x2"` as a string.
**What R does:** `y ~ x1 + x2` is a formula **object**, not a string.

```r
# R -- unquoted formula (a special R object type)
fit <- lm(y ~ x1 + x2, data = df)

# NOT a string:
# fit <- lm("y ~ x1 + x2", data = df)  # Would error in most contexts
```

### 3. Factors Auto-Dummy in Models

**What Python users expect:** Must wrap categoricals in `C()` or `i()`.
**What R does:** `factor()` columns automatically create dummies in formulas.

```r
df$region <- factor(df$region)
fit <- lm(y ~ region, data = df)  # Auto-creates region dummies
# No C() or i() needed!
```

---

## Environment Traps

### 1. `library()` Exports Everything

**What Python users expect:** `import pkg as alias` keeps functions namespaced.
**What R does:** `library(dplyr)` makes ALL dplyr functions available without prefix.

```r
library(dplyr)
library(stats)   # Also exports filter() -- masks dplyr::filter()!

# Which filter() am I calling?
filter(df, x > 5)   # Last loaded wins -- stats::filter()!
dplyr::filter(df, x > 5)  # Explicit disambiguation
```

### 2. No Block Scoping

**What Python users expect:** Variables in `if`/`for` blocks are scoped.
**What R does:** Variables defined inside `if`/`for` are visible outside.

```r
if (TRUE) {
  temp_var <- 42
}
print(temp_var)   # 42 -- still accessible!
```

### 3. `print()` Adds Formatting

**What Python users expect:** `print("hello")` outputs `hello`.
**What R does:** `print("hello")` outputs `[1] "hello"` (with index and quotes).

```r
print("hello")       # [1] "hello"
cat("hello\n")       # hello        (clean output -- use this for validation)
```

Use `cat()` for clean output in DAAF scripts. `print()` is for interactive use.

### 4. No Dictionary Type

**What Python users expect:** `{"key": "value"}` creates a dictionary.
**What R does:** R has no dictionary type. Use named lists or named vectors.

```r
# Named list (like a Python dict)
config <- list(name = "analysis", year = 2020, active = TRUE)
config$name        # "analysis"
config[["year"]]   # 2020

# Named vector (all same type)
codes <- c(AL = "Alabama", AK = "Alaska", AZ = "Arizona")
codes["AL"]        # "Alabama"
```

---

## Common Error Messages Translated

| Python Error | R Equivalent | Meaning |
|-------------|-------------|---------|
| `NameError: name 'x' is not defined` | `Error: object 'x' not found` | Variable does not exist |
| `ImportError: No module named 'x'` | `Error: there is no package called 'x'` | Package not installed |
| `TypeError` | `Error: non-numeric argument to binary operator` | Wrong type in operation |
| `IndexError: list index out of range` | `Error: subscript out of bounds` | Index exceeds length |
| `KeyError` | `Error: $ operator is invalid for atomic vectors` | Wrong access method |
| `FileNotFoundError` | `Error: cannot open the connection` | File path wrong |
| `AttributeError` | `Error: could not find function "f"` | Function does not exist |

---

## Quick Diagnostic Table

| Problem | Quick Fix |
|---------|-----------|
| `TRUE`/`FALSE` not recognized | Capitalize: `TRUE`, `FALSE` (not `True`, `False`) |
| Got wrong element with negative index | R uses negative index for EXCLUSION, not from-end access |
| Off-by-one error | R is 1-indexed; `x[1]` is first element |
| `NA` propagating unexpectedly | Use `is.na()` checks; add `na.rm = TRUE` to aggregations |
| Can't find a function after `library()` | Name collision; use `pkg::function()` explicitly |
| `print()` output has brackets and quotes | Use `cat()` for clean output |
| Assignment behaves oddly in function call | Use `<-` for assignment, `=` for named arguments |
| Vector recycling gave wrong answer | Ensure vectors are same length or use explicit operations |
| List access returns a list, not the value | Use `[[` or `$` instead of `[` |
| String interpolation not working | Use `glue::glue("text {var}")` or `paste0("text ", var)` |
