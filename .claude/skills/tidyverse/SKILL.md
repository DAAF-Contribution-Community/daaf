---
name: tidyverse
description: >-
  R data manipulation with dplyr, tidyr, readr, purrr, stringr, forcats,
  lubridate. Verb pipelines, reshaping, joins, string/date ops, parquet via
  arrow. Includes data.table for performance. Use when execution language is R.
  Python equivalent: polars.
autoload: never
metadata:
  audience: research-coders
  domain: r-library
  library-version: "dplyr 1.2.1"
  skill-last-updated: "2026-05-08"
  tags: ["r", "data-manipulation", "tidyverse", "dplyr", "tidyr"]
---

# Tidyverse Skill

R data manipulation with the core tidyverse packages: dplyr (verb-based data transformation), tidyr (reshaping and tidying), readr (fast delimited file I/O), purrr (functional iteration over lists and vectors), stringr (consistent string operations), forcats (factor manipulation for categorical data), and lubridate (date-time parsing and arithmetic). Also covers arrow for parquet I/O and data.table as a high-performance alternative for large datasets. Use when the execution language is R and the task involves data wrangling, reshaping, joining, string processing, date handling, or file I/O. Python equivalent: the polars skill.

## What is the Tidyverse?

The tidyverse is a collection of R packages that share a common design philosophy for data science:

- **Verb-based grammar**: Operations read as sentences -- `filter()`, `select()`, `mutate()`, `summarize()` describe what you want to do
- **Pipe-friendly**: Every function takes a data frame as its first argument and returns a data frame, enabling `|>` pipe chains
- **Tidy data**: One observation per row, one variable per column -- functions assume this structure
- **Consistent API**: Shared conventions across packages (tidyselect helpers, data masking, `.data` pronoun)
- **Readable pipelines**: Code reads top-to-bottom like a recipe, making it self-documenting

The tidyverse is not a single package but a curated set of packages that work together. This skill covers the data manipulation subset; for visualization see the ggplot2 skill; for statistical modeling see the r-stats skill.

## Version Notes

Versions installed in the DAAF container (R 4.5.3):

| Package | Version | Key Notes |
|---------|---------|-----------|
| dplyr | 1.2.1 | `.by` inline grouping, `reframe()`, `pick()` |
| tidyr | 1.3.2 | `pivot_longer()`/`pivot_wider()` with `.value` sentinel |
| readr | 2.2.0 | Second-edition parser, `read_csv()` returns tibble |
| purrr | 1.2.2 | `list_c()`, `list_rbind()`, `list_cbind()` |
| stringr | 1.6.0 | Consistent `str_*` functions wrapping stringi |
| forcats | 1.0.1 | `fct_na_value_to_level()`, `fct_cross()` |
| lubridate | 1.9.5 | `ymd()` family, `interval()`, date arithmetic |
| data.table | 1.18.2.1 | `DT[i, j, by]` syntax, `fread()`/`fwrite()` |
| arrow | 23.0.1.2 | `read_parquet()`/`write_parquet()`, Arrow-dplyr integration |

**dplyr 1.1+ changes to be aware of:**
- `.by` argument in `mutate()`, `summarize()`, `filter()`, `slice_*()` for inline grouping (no `group_by()` needed)
- `reframe()` replaces `summarize()` when results have multiple rows per group
- `pick()` replaces `across()` inside `cur_data()` contexts
- `recode_values()` for value-matching (simpler than `case_when()` for direct mappings; supersedes `case_match()`, which is soft-deprecated as of dplyr 1.2.0)
- `consecutive_id()` for run-length grouping
- `join_by()` for inequality and overlap joins

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Core verbs: filter, select, mutate, group_by + summarize, arrange, pipe | Starting an R data pipeline, basic wrangling |
| `reshaping.md` | pivot_longer, pivot_wider, separate, unite, nest/unnest | Converting between wide and long formats |
| `joins.md` | left_join, inner_join, anti_join, semi_join, join keys, validation | Combining data frames |
| `io.md` | Parquet via arrow, CSV via readr, Excel via readxl, remote fetching via httr2/glue, data import patterns | Reading or writing data files, fetching from HTTP APIs |
| `strings-dates.md` | stringr ops (str_detect, str_replace, regex), lubridate (ymd, date arithmetic) | String processing or date handling |
| `purrr-functional.md` | map/map_dfr/map2, walk, list-columns, nested data patterns | Iterating over lists or nested data |
| `factors.md` | forcats: fct_relevel, fct_reorder, fct_lump, factor ordering | Categorical variable manipulation |
| `window-ranking.md` | row_number, lag/lead, cumsum, ntile, rolling operations | Window functions and ranking within groups |
| `data-table.md` | data.table DT[i, j, by] syntax, fread/fwrite, when to prefer over dplyr | Performance-critical operations on large data |
| `gotchas.md` | NSE vs data masking, .data pronoun, across() patterns, group_by footguns | Debugging unexpected behavior |

### Reading Order

1. **New to tidyverse?** Start with `quickstart.md` then `io.md`
2. **Reshaping data?** Read `reshaping.md`
3. **Combining datasets?** Read `joins.md`
4. **String or date problems?** Read `strings-dates.md`
5. **Performance issues with large data?** Read `data-table.md`
6. **Something not working?** Check `gotchas.md` first

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `polars` | Python equivalent -- covers the same data manipulation domain for Python pipelines |
| `data-scientist` | Methodology routing -- determines which analysis to run; tidyverse implements it |
| `ggplot2` | Visualization -- takes tidy data produced by tidyverse and creates plots |
| `r-stats` | Statistical modeling -- lm/glm, sandwich robust SEs, diagnostics; tidyverse prepares data for modeling |
| `fixest` | Fixed effects regression -- high-dimensional FE, IV, DiD; tidyverse prepares data for fixest |
| `r-python-translation` | Cross-language reference -- maps tidyverse to polars for bilingual annotation |

## Quick Decision Trees

### "I need to manipulate data"

```
Data manipulation task?
├─ Select/drop columns → ./references/quickstart.md (select)
├─ Filter rows → ./references/quickstart.md (filter)
├─ Create/modify columns → ./references/quickstart.md (mutate)
├─ Sort rows → ./references/quickstart.md (arrange)
├─ Aggregate by group → ./references/quickstart.md (group_by + summarize)
├─ Reshape wide to long → ./references/reshaping.md (pivot_longer)
├─ Reshape long to wide → ./references/reshaping.md (pivot_wider)
├─ Join two data frames → ./references/joins.md
├─ Window functions (lag, rank) → ./references/window-ranking.md
└─ Large data performance → ./references/data-table.md
```

### "I need to work with specific types"

```
Type-specific operation?
├─ String matching/replacement → ./references/strings-dates.md (stringr)
├─ Date parsing/arithmetic → ./references/strings-dates.md (lubridate)
├─ Categorical/factor levels → ./references/factors.md (forcats)
└─ Iterate over lists → ./references/purrr-functional.md (purrr)
```

### "I need to read or write data"

```
Data I/O?
├─ Read/write parquet (preferred) → ./references/io.md (arrow)
├─ Read/write CSV → ./references/io.md (readr)
├─ Read Excel → ./references/io.md (readxl)
├─ Fetch from HTTP API → ./references/io.md (httr2, glue)
└─ High-speed CSV for large files → ./references/data-table.md (fread)
```

## File-First Execution in Research Workflows

In DAAF research pipelines, R transformations follow the **file-first execution protocol** -- code is written to `.R` script files and executed via the `run_with_capture.sh` wrapper, never run interactively.

**The pattern:**
1. Write transformation code to `scripts/stage{N}_{type}/{step}_{task-name}.R`
2. Execute via Bash: `bash {BASE_DIR}/scripts/run_with_capture.sh {PROJECT_DIR}/scripts/{script_name}.R`
3. `run_with_capture.sh` detects the `.R` extension and uses `Rscript` automatically
4. stdout/stderr are appended to the script file as comments
5. If a script fails, create a versioned copy (`_a.R`, `_b.R`, etc.) for fixes

Read `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` for the complete protocol.

**R script structure follows DAAF conventions:**

```r
# --- Config ---
library(dplyr)
library(arrow)

PROJECT_DIR <- "/daaf/research/YYYY-MM-DD_Project"

# --- Load ---
# INTENT: Load cleaned school-level data for analysis
df <- read_parquet(file.path(PROJECT_DIR, "data", "schools_clean.parquet"))
cat("Loaded:", nrow(df), "rows,", ncol(df), "columns\n")

# --- Transform ---
# INTENT: Calculate poverty rate by state
# ASSUMES: enrollment > 0 for all rows (validated in cleaning)
result <- df |>
  mutate(poverty_rate = frl_count / enrollment) |>
  group_by(state) |>
  summarize(
    avg_poverty = mean(poverty_rate, na.rm = TRUE),
    n_schools = n(),
    .groups = "drop"
  ) |>
  arrange(desc(avg_poverty))

# --- Validate ---
stopifnot(nrow(result) > 0)
stopifnot(all(result$avg_poverty >= 0 & result$avg_poverty <= 1))
cat("States:", nrow(result), "\n")
cat("Range:", range(result$avg_poverty), "\n")

# --- Save ---
write_parquet(result, file.path(PROJECT_DIR, "data", "state_poverty.parquet"))
cat("Saved: state_poverty.parquet\n")
```

## Quick Reference

### Essential Setup

```r
library(dplyr)
library(tidyr)
library(readr)
library(stringr)
library(lubridate)
library(arrow)     # for parquet I/O
```

### Core Operations

| Operation | Code | Package |
|-----------|------|---------|
| Filter rows | `df |> filter(x > 5)` | dplyr |
| Select columns | `df |> select(a, b, c)` | dplyr |
| Create column | `df |> mutate(y = x * 2)` | dplyr |
| Sort | `df |> arrange(desc(x))` | dplyr |
| Group + summarize | `df |> group_by(g) |> summarize(m = mean(x))` | dplyr |
| Rename | `df |> rename(new = old)` | dplyr |
| Distinct rows | `df |> distinct(a, b)` | dplyr |
| Count | `df |> count(group_col)` | dplyr |
| Left join | `df1 |> left_join(df2, by = "key")` | dplyr |
| Pivot longer | `df |> pivot_longer(cols, names_to, values_to)` | tidyr |
| Pivot wider | `df |> pivot_wider(names_from, values_from)` | tidyr |
| Read parquet | `read_parquet("file.parquet")` | arrow |
| Write parquet | `write_parquet(df, "file.parquet")` | arrow |
| Read CSV | `read_csv("file.csv")` | readr |
| String detect | `str_detect(x, "pattern")` | stringr |
| Parse date | `ymd("2024-01-15")` | lubridate |
| Native pipe | `df |> verb1() |> verb2()` | base R 4.1+ |

### The Pipe Operator

R 4.1+ provides the native pipe `|>` which passes the left-hand side as the first argument to the right-hand side. Use `|>` (not the magrittr `%>%`) for all DAAF pipelines:

```r
# Native pipe -- preferred in DAAF
result <- df |>
  filter(year == 2020) |>
  mutate(rate = count / total) |>
  group_by(state) |>
  summarize(avg_rate = mean(rate)) |>
  arrange(desc(avg_rate))
```

## Topic Index

| Topic | Reference File |
|-------|---------------|
| filter, select, mutate | `./references/quickstart.md` |
| arrange, group_by, summarize | `./references/quickstart.md` |
| Pipe operator | `./references/quickstart.md` |
| slice, distinct, count | `./references/quickstart.md` |
| across(), pick() | `./references/quickstart.md` |
| case_when, if_else | `./references/quickstart.md` |
| pivot_longer | `./references/reshaping.md` |
| pivot_wider | `./references/reshaping.md` |
| separate, unite | `./references/reshaping.md` |
| nest, unnest | `./references/reshaping.md` |
| complete, fill | `./references/reshaping.md` |
| left_join, inner_join | `./references/joins.md` |
| anti_join, semi_join | `./references/joins.md` |
| Join keys, by argument | `./references/joins.md` |
| Join validation | `./references/joins.md` |
| read_parquet, write_parquet | `./references/io.md` |
| read_csv, write_csv | `./references/io.md` |
| Arrow integration | `./references/io.md` |
| httr2, glue remote fetch | `./references/io.md` |
| str_detect, str_replace | `./references/strings-dates.md` |
| str_extract, regex | `./references/strings-dates.md` |
| ymd, date arithmetic | `./references/strings-dates.md` |
| Date components | `./references/strings-dates.md` |
| map, map_dfr, walk | `./references/purrr-functional.md` |
| List-columns | `./references/purrr-functional.md` |
| fct_relevel, fct_reorder | `./references/factors.md` |
| fct_lump, factor ordering | `./references/factors.md` |
| row_number, lag, lead | `./references/window-ranking.md` |
| cumsum, ntile | `./references/window-ranking.md` |
| Rolling operations | `./references/window-ranking.md` |
| DT[i, j, by] syntax | `./references/data-table.md` |
| fread, fwrite | `./references/data-table.md` |
| NSE and data masking | `./references/gotchas.md` |
| .data pronoun | `./references/gotchas.md` |
| Common pitfalls | `./references/gotchas.md` |

## Citation

When this library collection is used as a primary analytical tool, include in the report's Software & Tools references:

> Wickham, H. et al. (2019). Welcome to the Tidyverse. *Journal of Open Source Software*, 4(43), 1686. https://doi.org/10.21105/joss.01686

**Cite when:** Tidyverse packages are the core data processing engine for the analysis.
**Do not cite when:** Only used for trivial file I/O in a script primarily using another tool.
