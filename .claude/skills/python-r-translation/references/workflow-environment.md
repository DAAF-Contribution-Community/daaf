# Workflow and Environment: R/DAAF Explained for Python Users

Beyond syntax, R and Python differ in *how you work with them*. This reference
covers the practical adjustments a Python user needs to make when working within
DAAF's R execution mode, framed as "here is what you know from Python, here is
how R does it."

> **Versions referenced:**
> R: R 4.5.3, Quarto 1.7.29
> Python: marimo 0.19.11, Python 3.12
> See SKILL.md § Library Versions for the complete version table.

---

## Section 1: File-First Execution (Same as Python DAAF)

DAAF's file-first execution model is the same regardless of language. If you have
used DAAF with Python, the R workflow is identical in structure:

1. **Write** a complete R script to a file
2. **Execute** via the capture wrapper:
   `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/stage7_transform/01_join-data.R`
3. **Review** output appended to the script
4. Create versioned copies (`_a.R`, `_b.R`) for fixes

The `run_with_capture.sh` wrapper detects `.R` files and runs them with `Rscript`.

---

## Section 2: Quarto vs marimo

### What You Know (marimo)

marimo is a **reactive** Python notebook with dependency-graph execution, stored
as `.py` files.

### What R Does (Quarto / RMarkdown)

Quarto runs **top-to-bottom** when rendered (knitted):

```
marimo:   Cell A --> Cell C --> Cell D    (dependency graph, reactive)
                /               /
          Cell B ---------------

Quarto:   Chunk 1 -> Chunk 2 -> Chunk 3 -> Chunk 4  (linear, sequential)
```

```
---
title: "Analysis"
format: html
---

## Load Data

```{r}
library(dplyr)
df <- arrow::read_parquet("data.parquet")
```

## Transform

```{r}
result <- df |> filter(year == 2020) |> mutate(pct = x / sum(x))
```
```

### Key Differences

| marimo (Python) | Quarto (R) |
|-----------------|-----------|
| Reactive cells (dependency graph) | Linear chunks (top-to-bottom) |
| `.py` file | `.qmd` file |
| `@app.cell` / `def _():` wrappers | ` ```{r} ` code fences |
| Variables scoped by dependency | Variables in shared environment |
| Change a cell, dependents re-run | Change a chunk, re-render everything |

**In DAAF pipelines,** Quarto notebooks are assembled at Stage 9 as read-only
compilations of executed scripts, just like marimo notebooks in Python mode.

---

## Section 3: Project Organization

### What You Know (Python DAAF)

```
research/2026-01-24_Analysis/
|-- scripts/
|   |-- stage5_fetch/     01_fetch.py, 01_fetch_a.py ...
|   |-- stage6_clean/     01_clean.py ...
|-- data/raw/             parquet files
|-- data/processed/       parquet files
```

### R DAAF (Identical Structure, Different Extensions)

```
research/2026-01-24_Analysis/
|-- scripts/
|   |-- stage5_fetch/     01_fetch.R, 01_fetch_a.R ...
|   |-- stage6_clean/     01_clean.R ...
|-- data/raw/             parquet files
|-- data/processed/       parquet files
```

The only difference is `.R` extensions instead of `.py`. All DAAF conventions
(stage-based directories, immutable scripts after execution, IAT documentation)
apply identically.

---

## Section 4: Package Management

| Python | R |
|--------|---|
| `import polars as pl` (namespaced) | `library(dplyr)` (exports all names) |
| `pip install pkg` or Docker pins | `install.packages("pkg")` or Docker pins |
| No name conflicts (namespace prefix) | Conflicts resolved by load order |
| `from sklearn.ensemble import RandomForestClassifier` | `library(ranger)` then `ranger()` |

### The Namespace Difference

```python
# Python -- always clear which package
import polars as pl
import pyfixest as pf
df = df.filter(pl.col("x") > 5)
```

```r
# R -- bare names after library()
library(dplyr)
library(fixest)
df <- df |> filter(x > 5)    # dplyr::filter, not base::filter
```

In R, `filter()` alone refers to `dplyr::filter()` because it was loaded last.
Use `dplyr::filter()` or `stats::filter()` to disambiguate.

---

## Section 5: Getting Help

| Python | R |
|--------|---|
| `help(function)` | `?function` or `help(function)` |
| `type(obj)` | `class(object)` |
| `df.shape` | `dim(df)` |
| `df.columns` | `names(df)` or `colnames(df)` |
| `len(df)` | `nrow(df)` |
| `df.schema` (polars) | `str(df)` or `glimpse(df)` |
| `df.describe()` | `summary(df)` |
| Online docs | `vignette("topic")` |

---

## Section 6: Reproducibility

| Python | R |
|--------|---|
| `random.seed(42)` / `np.random.seed(42)` | `set.seed(42)` |
| Docker pins versions | `renv::snapshot()` or Docker |
| No workspace persistence | `.RData` (common but discouraged) |
| f-strings for output | `glue::glue()` or `paste()` |
| `assert condition` | `stopifnot(condition)` |
| `print("text")` | `cat("text\n")` |

### IAT in R Scripts

The same Inline Audit Trail applies in R:

```r
# INTENT: Remove records with missing enrollment for complete-case analysis
# REASONING: 3.2% of records have null enrollment; MCAR pattern confirmed
# ASSUMES: Missingness is MCAR -- if MNAR, results may undercount small schools
df <- df |> filter(!is.na(enrollment))
```

---

## Section 7: Common Workflow Questions

**"I want to explore data interactively."**
Write a profiling script with `cat()` and `print()` statements, execute via
`run_with_capture.sh`. The output is appended to the script.

**"I want to `source()` another script."**
DAAF scripts are self-contained. Each loads its own data from parquet and includes
all `library()` calls. No sourcing.

**"Where is my plot?"**
Plots are saved to files: `ggsave("output/figures/plot.png", p, width=10, height=8)`.
No interactive plot viewer in file-first mode.

**"How do I see my data's structure?"**
```r
cat(paste("Shape:", nrow(df), "x", ncol(df), "\n"))
cat("Columns:\n"); print(names(df))
cat("Types:\n"); print(sapply(df, class))
cat("Nulls:\n"); print(colSums(is.na(df)))
print(head(df, 10))
print(summary(df))
```

**"I want method chaining like polars."**
R uses the pipe `|>` for the same purpose:
```r
result <- df |>
  filter(year == 2020) |>
  group_by(state) |>
  summarise(mean_x = mean(x, na.rm = TRUE))
```

> **Sources:** Quarto documentation (quarto.org, accessed 2026-03-28);
> marimo documentation (docs.marimo.io, accessed 2026-03-28)
