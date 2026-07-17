---
name: python-r-translation
description: >-
  Python-to-R translation for data analysis. Maps Python (polars, plotnine, pyfixest,
  statsmodels, svy, geopandas) to R (tidyverse, ggplot2, fixest, survey, sf). Use
  when user has Python background or requests Python-equivalent code comments in
  R pipelines.
metadata:
  audience: research-coders
  domain: cross-language
  skill-last-updated: "2026-05-13"
---

# Python-to-R Translation Skill

Python-to-R translation reference for quantitative social science data analysis. Maps Python ecosystem packages (polars, plotnine, pyfixest, statsmodels, linearmodels, svy, geopandas, scikit-learn) to R equivalents (tidyverse/dplyr, ggplot2, fixest, base R stats, plm, lme4, survey, sf, terra, tidymodels). Use when user mentions Python background, requests Python-equivalent code comments in R pipelines, needs to understand R analysis code from a Python perspective, or wants to translate Python data analysis concepts to R. Covers paradigm differences, verb-by-verb operation translations, regression modeling, causal inference, visualization, and workflow adaptation.

Cross-language translation reference for researchers moving between the Python and R data analysis ecosystems. This skill maps Python packages, idioms, and workflows to their DAAF R equivalents so that Python-background users can audit, understand, and learn from DAAF-produced R code, and so that code-producing agents can annotate their output with Python equivalents when directed.

This skill is a **routing hub** -- it provides overview tables, decision trees, and directs readers to the detailed reference files listed below. The reference files contain the exhaustive verb-by-verb mappings, code examples, and edge-case documentation.

## What This Skill Does

- Maps the Python data analysis ecosystem to DAAF's R stack across data wrangling, modeling, visualization, causal inference, surveys, spatial analysis, and workflow tooling
- Provides a structured annotation protocol for agents to add inline Python-equivalent comments to R code
- Identifies paradigm gaps where Python and R diverge fundamentally, so users know where to expect friction

**Use cases:**

1. Python user auditing DAAF R code and needing to understand what operations are being performed
2. Agent annotating R code with Python-equivalent comments for a Python-background researcher
3. Python user learning R for data analysis and needing a conceptual bridge
4. Translating a specific R operation or idiom to its Python equivalent
5. Understanding where Python tools have no direct R equivalent (and what the workaround is)

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `paradigm-differences.md` | Core language and paradigm differences | Encountering fundamental R-vs-Python confusion |
| `dplyr-polars.md` | Core dplyr/tidyr verbs explained for polars users (filter, mutate, joins, reshaping, window functions, piping) | Reading or writing data manipulation code |
| `strings-dates-factors.md` | String, date/time, and factor operations (stringr, lubridate, forcats for polars users) | Working with string/date/categorical columns |
| `regression-modeling.md` | fixest/stats/plm explained for pyfixest/statsmodels/linearmodels users | Reading or writing regression code |
| `visualization.md` | ggplot2/plotly R explained for plotnine/plotly Python users | Reading or writing visualization code |
| `causal-inference.md` | R causal inference ecosystem explained for Python users | Working with DiD, RDD, IV, event studies |
| `survey-spatial-ml.md` | survey/sf/tidymodels explained for svy/geopandas/scikit-learn users | Working with surveys, spatial data, or ML |
| `workflow-environment.md` | DAAF/R workflow explained for Python-background users | Adapting to DAAF's R execution model |
| `external-resources.md` | Curated guides and tutorials with provenance | Seeking additional learning materials |
| `gotchas.md` | Common Python-user mistakes in R | Debugging or reviewing code from Python perspective |

### Reading Order

1. **Python user auditing DAAF R code:** `paradigm-differences.md` then the relevant domain file (e.g., `dplyr-polars.md` for data wrangling, `regression-modeling.md` for models) then `gotchas.md`
2. **Agent annotating R code with Python equivalents:** Agent Code Annotation Protocol section below, then the relevant domain file for the code being annotated
3. **Learning R from Python background:** `paradigm-differences.md` then `dplyr-polars.md` then `workflow-environment.md` then `external-resources.md`
4. **Looking up a specific translation:** Quick Decision Trees below, then the relevant reference file

## Quick Decision Trees

### "What does this R code do in Python terms?"

```
What kind of R operation?
|-- Data wrangling (filter, mutate, join, pivot, summarise)
|   +-- ./references/dplyr-polars.md
|-- Regression / statistical modeling
|   +-- ./references/regression-modeling.md
|-- Plotting / visualization
|   +-- ./references/visualization.md
|-- Causal inference (DiD, RDD, IV, event studies)
|   +-- ./references/causal-inference.md
|-- Surveys / spatial / machine learning
|   +-- ./references/survey-spatial-ml.md
+-- Fundamental language differences (types, syntax, environment)
    +-- ./references/paradigm-differences.md
```

### "Why does this R code look different from Python?"

```
What looks unfamiliar?
|-- Pipe operator (|>)
|   +-- ./references/paradigm-differences.md
|-- Formula interface (y ~ x1 + x2)
|   +-- ./references/regression-modeling.md
|-- Unquoted column names in functions
|   +-- ./references/paradigm-differences.md
|-- library() loads everything
|   +-- ./references/gotchas.md
|-- factor() and levels
|   +-- ./references/paradigm-differences.md
|-- <- for assignment
|   +-- ./references/gotchas.md
+-- Interactive console / RStudio workflow
    +-- ./references/workflow-environment.md
```

### "What R package replaces my Python package?"

```
Which Python package?
|-- polars --> dplyr + tidyr + data.table
|   +-- ./references/dplyr-polars.md
|-- plotnine --> ggplot2
|   +-- ./references/visualization.md
|-- plotly (Python) --> plotly (R)
|   +-- ./references/visualization.md
|-- pyfixest --> fixest
|   +-- ./references/regression-modeling.md
|-- statsmodels (OLS, GLM) --> base R stats (lm, glm) + lmtest + sandwich
|   +-- ./references/regression-modeling.md
|-- linearmodels (panel, IV) --> plm + estimatr
|   +-- ./references/regression-modeling.md
|-- statsmodels MixedLM --> lme4 (lmer)
|   +-- ./references/regression-modeling.md
|-- svy --> survey (Lumley)
|   +-- ./references/survey-spatial-ml.md
|-- geopandas --> sf + terra
|   +-- ./references/survey-spatial-ml.md
|-- scikit-learn --> tidymodels / caret
|   +-- ./references/survey-spatial-ml.md
|-- marginaleffects (Python) --> marginaleffects (R)
|   +-- ./references/regression-modeling.md
|-- rdrobust (Python) --> rdrobust (R)
|   +-- ./references/causal-inference.md
+-- marimo --> Quarto / RMarkdown
    +-- ./references/workflow-environment.md
```

### "Something isn't working and I think it's a Python habit"

```
What went wrong?
|-- Used = instead of <- for assignment
|   +-- ./references/gotchas.md
|-- 0-indexed access gave wrong element
|   +-- ./references/gotchas.md
|-- Used True/False instead of TRUE/FALSE
|   +-- ./references/gotchas.md
|-- Missing value handling surprised me (NA vs None/NaN)
|   +-- ./references/paradigm-differences.md
|-- import vs library() confusion
|   +-- ./references/gotchas.md
|-- Expected method chaining, got pipe errors
|   +-- ./references/paradigm-differences.md
+-- Model output structure is different
    +-- ./references/regression-modeling.md
```

## Package Mapping Overview

| R Package | Python Equivalent | Fidelity | Key Difference |
|-----------|------------------|----------|----------------|
| dplyr + tidyr | polars | Low | Verb grammar vs expression system; pipe vs method chaining |
| fixest | pyfixest | High | Near-identical formula syntax; minor SE default differences |
| ggplot2 | plotnine | High | Same grammar of graphics; bare names vs string quoting for aes |
| plotly (R) | plotly (Python) | High | `plot_ly()` vs `px.scatter()`; similar output |
| base R stats + lmtest + sandwich | statsmodels | Medium | Single formula syntax vs three Python dialects |
| plm + estimatr | linearmodels | Medium | pdata.frame vs pandas MultiIndex for panel structure |
| lme4 | statsmodels MixedLM | Medium | `(1 \| group)` in formula vs separate `groups=`/`re_formula=` arguments |
| tidymodels / caret | scikit-learn | Medium | Declarative recipe pipeline vs imperative fit/predict |
| sf + terra | geopandas | Medium | st_*() functions vs GeoDataFrame methods; different CRS handling |
| survey (Lumley) | svy | Medium | Full GLM family coverage vs limited (gaussian/binomial/Poisson/gamma) |
| Quarto / RMarkdown | marimo | Medium | Knit-based linear execution vs reactive cells |

**Fidelity key:** High = near-direct translation, same mental model. Medium = same capability, different API patterns. Low = fundamentally different paradigm requiring conceptual remapping.

## Library Versions

Translations in this skill reference specific library versions. R versions reference
CRAN releases as of March 2026 (R 4.5.3). Python versions are pinned in DAAF's Docker
environment (Python 3.12). When syntax or behavior has changed between versions, the
reference files note the change.

| R Package | R Version (CRAN) | Python Equivalent | DAAF Version |
|---|---|---|---|
| dplyr + tidyr + data.table | dplyr 1.2.0, tidyr 1.3.2, data.table 1.18.2 | polars | 1.39.3 |
| fixest | 0.14.0 | pyfixest | 0.40.0 |
| ggplot2 | 4.0.2 | plotnine | 0.15.3 |
| plotly (R) | 4.12.0 | plotly | 6.5.2 |
| base R stats + lmtest + sandwich | lmtest 0.9-40, sandwich 3.1-1 | statsmodels | 0.14.6 |
| plm + estimatr | plm 2.6-7, estimatr 1.0.6 | linearmodels | 7.0 |
| lme4 | 2.0-1 | statsmodels MixedLM | 0.14.6 |
| tidymodels / caret | tidymodels 1.4.1, caret 7.0-1 | scikit-learn | 1.8.0 |
| sf + terra | sf 1.1-0, terra 1.9-11 | geopandas | 1.1.3 |
| survey | survey 4.5 | svy | 0.19.0 |
| marginaleffects (R) | 0.32.0 | marginaleffects | 0.5.0 |
| rdrobust (R) | 3.0.0 | rdrobust | 1.3.0 |
| Quarto / RMarkdown | Quarto 1.7.29 | marimo | 0.19.11 |

**Pinning note:** linearmodels, marginaleffects, and rdrobust are version-pinned in
DAAF's Dockerfile (`linearmodels==7.0`, `marginaleffects==0.5.0`, `rdrobust==1.3.0`)
and pre-installed alongside the rest of the Python stack. Translations reference their
documented APIs as of March 2026.

## Top 10 Paradigm Differences

These are the friction points Python users encounter most frequently when reading or writing DAAF R code. Each is covered in depth in the referenced file.

| # | Friction Point | Python Way | R Way | Reference |
|---|---------------|------------|-------|-----------|
| 1 | Pipe operator | `df.filter(...).with_columns(...)` | `df |> filter(...) |> mutate(...)` | `paradigm-differences.md` |
| 2 | Unquoted column names | `pl.col("x")` string references | `x` bare name in dplyr verbs | `paradigm-differences.md` |
| 3 | Missing values | `None`, `NaN`, and `null` (context-dependent) | Single unified `NA` type | `paradigm-differences.md` |
| 4 | Formula interface | Three incompatible Python dialects | One universal `~` syntax everywhere | `regression-modeling.md` |
| 5 | Assignment operator | `=` for assignment | `<-` for assignment (= also works but unconventional) | `gotchas.md` |
| 6 | Package loading | `import pkg as alias` (explicit namespace) | `library(pkg)` exports all names | `paradigm-differences.md` |
| 7 | Factor / categorical | `pl.Categorical` (storage only) | `factor()` with ordered levels, auto-dummies in models | `paradigm-differences.md` |
| 8 | 0-indexed vs 1-indexed | `x[0]` is first element | `x[1]` is first element | `gotchas.md` |
| 9 | Boolean values | `True` / `False` | `TRUE` / `FALSE` | `gotchas.md` |
| 10 | Data frame boundary | Must call `.to_pandas()` for modeling | Same tibble flows everywhere: wrangle, model, plot | `paradigm-differences.md` |

## Agent Code Annotation Protocol

This section defines when and how code-producing agents add inline Python-equivalent comments to DAAF R scripts.

### When to Annotate

Annotations are added **only when the orchestrator explicitly passes a Python-background directive** to the agent. This is not a default behavior.

**Trigger conditions** (orchestrator activates this when any apply):
- User states they have a Python background
- User requests Python-equivalent comments in R code
- User asks to understand R code from a Python perspective

**How the orchestrator passes the directive:** The orchestrator adds the following to the agent prompt:

> "User has Python background. Load python-r-translation skill. Add inline Python-equivalent comments for non-trivial data operations."

### Comment Format

```r
# Python: df.filter(pl.col("year") == 2020)
filtered <- df |> filter(year == 2020)

# Python: df.with_columns((pl.col("count") / pl.col("count").sum()).alias("pct"))
result <- df |>
  mutate(pct = count / sum(count))

# Python: pf.feols("y ~ x1 + x2 | state + year", data=pdf, vcov={"CRV1": "state"})
fit <- feols(y ~ x1 + x2 | state + year, data = df, vcov = ~state)
```

### What to Annotate

- **Annotate:** Data wrangling (dplyr/tidyr operations), modeling calls (fixest, lm, glm, plm), visualization layer construction (ggplot2, plotly), causal inference method calls
- **Do NOT annotate:** `library()` calls, `cat()`/`stopifnot()` validation lines, file I/O boilerplate (`read_parquet`, `write_parquet`), config sections, section separator comments

### Rules

- One `# Python:` comment per logical operation, placed on the line immediately above the R code
- Keep annotations to a single line; abbreviate complex Python pipelines if needed
- Python annotations are **in addition to** standard IAT comments (`# INTENT:`, `# REASONING:`, `# ASSUMES:`), not a replacement
- Consumer agents: research-executor, code-reviewer, debugger, data-ingest

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `tidyverse` | R-side data wrangling -- detailed API reference for the polars equivalent |
| `fixest` | R-side fixed effects regression -- detailed API for the pyfixest equivalent |
| `ggplot2` | R-side static visualization -- detailed API for the plotnine equivalent |
| `plotly-r` | R-side interactive visualization -- detailed API for plotly Python equivalent |
| `r-stats` | R-side general modeling -- covers base R stats, lmtest, sandwich equivalents |
| `plm` | R-side panel/IV models -- covers linearmodels equivalents |
| `survey-r` | R-side survey analysis -- covers svy (Python) equivalents |
| `sf-terra` | R-side spatial data -- covers geopandas equivalents |
| `tidymodels` | R-side ML -- covers scikit-learn equivalents |
| `quarto` | R-side notebooks -- covers marimo workflow equivalents |
| `r-python-translation` | Parallel skill for R-background users reading Python code -- same domain, reverse direction |
| `stata-python-translation` | Parallel skill for Stata-background users -- shares the same Python target stack |

**Note:** Individual tool skills contain library-specific usage guidance (syntax, gotchas, performance). This skill provides the Python-to-R conceptual bridge -- use both together when a Python-background user is working with a specific R library.

**ML interpretation/fairness asymmetry (honest signal):** Python's ML interpretation and fairness ecosystem is genuinely deeper (SHAP, fairlearn, and related tooling). The R-side equivalents (iml, DALEX, kernelshap, fairmodels) are installed and covered by the `tidymodels` skill's `interpretation.md` and `fairness.md`, so real R workflows exist for these tasks -- but for ML-heavy interpretation or fairness translation questions the Python direction carries more depth, and translating *to* R may surface a residual ecosystem gap rather than a one-to-one mapping.

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Pipe operator (`|>`) and method chaining | `./references/paradigm-differences.md` |
| Unquoted column names (non-standard evaluation) | `./references/paradigm-differences.md` |
| Missing value semantics (NA vs None/NaN/null) | `./references/paradigm-differences.md` |
| Type system differences | `./references/paradigm-differences.md` |
| Package/namespace model (library vs import) | `./references/paradigm-differences.md` |
| 1-indexing vs 0-indexing | `./references/paradigm-differences.md` |
| Data frame philosophy (tibble everywhere vs polars-pandas boundary) | `./references/paradigm-differences.md` |
| Copy-on-modify vs reference semantics | `./references/paradigm-differences.md` |
| dplyr verb mapping (filter, select, mutate, arrange) | `./references/dplyr-polars.md` |
| summarise / group_by equivalents | `./references/dplyr-polars.md` |
| tidyr verbs (pivot_longer, pivot_wider, separate, unite) | `./references/dplyr-polars.md` |
| Join operations (left_join, inner_join, anti_join) | `./references/dplyr-polars.md` |
| across() / where() equivalents | `./references/dplyr-polars.md` |
| case_when equivalent | `./references/dplyr-polars.md` |
| Window functions (over vs group_by + mutate) | `./references/dplyr-polars.md` |
| Pipe chaining comparison | `./references/dplyr-polars.md` |
| Lazy evaluation (scan_parquet vs arrow) | `./references/dplyr-polars.md` |
| nest/unnest equivalents | `./references/dplyr-polars.md` |
| readr I/O equivalents | `./references/dplyr-polars.md` |
| String operations (stringr vs polars .str) | `./references/strings-dates-factors.md` |
| Date operations (lubridate vs polars .dt) | `./references/strings-dates-factors.md` |
| Factor/categorical operations (forcats vs polars Categorical) | `./references/strings-dates-factors.md` |
| data.table vs polars | `./references/strings-dates-factors.md` |
| fixest formula syntax in pyfixest | `./references/regression-modeling.md` |
| lm() / glm() in statsmodels | `./references/regression-modeling.md` |
| Formula interface comparison (R universal vs three Python dialects) | `./references/regression-modeling.md` |
| Standard error specification differences | `./references/regression-modeling.md` |
| plm panel models in linearmodels | `./references/regression-modeling.md` |
| lme4 mixed effects equivalents | `./references/regression-modeling.md` |
| marginaleffects (R to Python) | `./references/regression-modeling.md` |
| Model summary / tidy output | `./references/regression-modeling.md` |
| Sandwich / robust SE equivalents | `./references/regression-modeling.md` |
| ggplot2 layer mapping to plotnine | `./references/visualization.md` |
| aes() bare names vs string quoting | `./references/visualization.md` |
| Theme customization | `./references/visualization.md` |
| Scale functions | `./references/visualization.md` |
| Faceting (facet_wrap, facet_grid) | `./references/visualization.md` |
| plotly R vs plotly Python | `./references/visualization.md` |
| ggsave equivalent | `./references/visualization.md` |
| Coefficient and effect plots | `./references/visualization.md` |
| Difference-in-differences (sunab, did2s) | `./references/causal-inference.md` |
| Regression discontinuity (rdrobust) | `./references/causal-inference.md` |
| Instrumental variables (feols IV vs pyfixest/linearmodels) | `./references/causal-inference.md` |
| Event study designs | `./references/causal-inference.md` |
| Synthetic control | `./references/causal-inference.md` |
| Matching / propensity scores | `./references/causal-inference.md` |
| Staggered DiD estimators | `./references/causal-inference.md` |
| survey package to svy | `./references/survey-spatial-ml.md` |
| svydesign / svymean / svyglm equivalents | `./references/survey-spatial-ml.md` |
| sf spatial operations to geopandas | `./references/survey-spatial-ml.md` |
| CRS / projection handling | `./references/survey-spatial-ml.md` |
| Spatial joins (st_join vs sjoin) | `./references/survey-spatial-ml.md` |
| tidymodels pipeline to scikit-learn | `./references/survey-spatial-ml.md` |
| BRR / jackknife replication weights | `./references/survey-spatial-ml.md` |
| Raster data handling (terra vs rasterio) | `./references/survey-spatial-ml.md` |
| Feature engineering (recipes vs sklearn Pipeline) | `./references/survey-spatial-ml.md` |
| Cross-validation (rsample vs sklearn) | `./references/survey-spatial-ml.md` |
| RStudio vs DAAF workflow | `./references/workflow-environment.md` |
| Quarto / RMarkdown vs marimo | `./references/workflow-environment.md` |
| File-first execution model | `./references/workflow-environment.md` |
| Package management (renv vs Docker) | `./references/workflow-environment.md` |
| Project structure conventions | `./references/workflow-environment.md` |
| Curated Python-to-R migration guides | `./references/external-resources.md` |
| Package documentation links | `./references/external-resources.md` |
| Tutorial recommendations with provenance | `./references/external-resources.md` |
| Assignment operator (<- vs =) | `./references/gotchas.md` |
| TRUE/FALSE vs True/False | `./references/gotchas.md` |
| 1-indexed vector access | `./references/gotchas.md` |
| Factor vs Categorical pitfalls | `./references/gotchas.md` |
| library() vs import habits | `./references/gotchas.md` |
| NA propagation surprises | `./references/gotchas.md` |
| Vectorized operations expectations | `./references/gotchas.md` |
| Copying semantics (R copy-on-modify vs Python references) | `./references/gotchas.md` |
| Logical operators (& / | vs and / or) | `./references/gotchas.md` |
| String interpolation (glue vs f-strings) | `./references/gotchas.md` |
| apply family vs map/list comprehension | `./references/gotchas.md` |
| Coordinate systems (coord_flip, coord_polar) | `./references/visualization.md` |
| Stat layers (stat_smooth, stat_summary) | `./references/visualization.md` |
| Color palette mapping (viridis, brewer) | `./references/visualization.md` |
| Multi-panel layouts (patchwork vs subplot) | `./references/visualization.md` |
| Parallel trends testing | `./references/causal-inference.md` |
| Environment/workspace differences (.RData vs nothing) | `./references/workflow-environment.md` |
| Debugging workflow (browser() vs breakpoint()) | `./references/workflow-environment.md` |
| R help system (?func) vs Python help(func) | `./references/workflow-environment.md` |
| Cheat sheet and quick-reference links | `./references/external-resources.md` |
| Community resources (Stack Overflow tags, forums) | `./references/external-resources.md` |
