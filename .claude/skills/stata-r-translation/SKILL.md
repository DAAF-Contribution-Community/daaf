---
name: stata-r-translation
description: >-
  Stata-to-R translation for data analysis. Maps Stata commands (reghdfe, xtreg,
  ivregress, margins, esttab, svy:) to R equivalents (fixest, plm, survey,
  marginaleffects, modelsummary). Use when user has Stata background or requests
  Stata-equivalent code comments in R pipelines.
metadata:
  audience: research-coders
  domain: cross-language
  skill-last-updated: "2026-07-24"
---

# Stata-to-R Translation Skill

Stata-to-R translation reference for quantitative social science data analysis. Maps Stata commands and packages (reghdfe, xtreg, ivregress, margins, esttab, svy:, graph twoway) to DAAF R equivalents (dplyr/tidyr, fixest, plm, survey, marginaleffects, modelsummary, ggplot2). Use when user mentions Stata background, requests Stata-equivalent code comments in R pipelines, needs to understand R analysis code from a Stata perspective, or wants to translate Stata data analysis concepts to R. Covers paradigm differences, command-by-command operation translations, regression modeling, causal inference, visualization, and workflow adaptation.

Cross-language translation reference for researchers moving between the Stata and R data analysis ecosystems. This skill maps Stata commands, idioms, and workflows to their DAAF R equivalents so that Stata-background users can audit, understand, and learn from DAAF-produced code, and so that code-producing agents can annotate their output with Stata equivalents when directed.

This skill is a **routing hub** -- it provides overview tables, decision trees, and directs readers to the detailed reference files listed below. The reference files contain the exhaustive command-by-command mappings, code examples, and edge-case documentation.

## What This Skill Does

- Maps the Stata command universe to DAAF's R stack across data management, regression modeling, causal inference, surveys, visualization, and workflow tooling
- Provides a structured annotation protocol for agents to add inline Stata-equivalent comments to R code
- Identifies paradigm gaps where Stata and R diverge fundamentally, so users know where to expect friction

**Use cases:**

1. Stata user auditing DAAF R code and needing to understand what operations are being performed
2. Agent annotating code with Stata-equivalent comments for a Stata-background researcher
3. Stata user learning R for data analysis and needing a conceptual bridge
4. Translating a specific Stata command or do-file idiom to its R equivalent
5. Understanding where Stata commands have no direct R equivalent (and what the workaround is)

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `paradigm-differences.md` | Core language and paradigm differences (single-dataset model, missing values, value labels, macros, by:/_n/_N) | Encountering fundamental Stata-vs-R confusion |
| `data-management.md` | gen/replace/keep/drop/sort/merge/append/reshape/collapse/egen to dplyr/tidyr | Reading or writing data manipulation code |
| `strings-dates-labels.md` | String functions, date epoch, value labels, encode/decode to stringr/lubridate/forcats | Working with string, date, or categorical columns |
| `regression-modeling.md` | regress/areg/reghdfe/xtreg/ivregress/logit/probit/margins/test/esttab to fixest/stats/plm/marginaleffects/modelsummary | Reading or writing regression code |
| `causal-inference.md` | DiD/RDD/IV/event studies/synthetic control/matching to fixest/rdrobust/did/MatchIt | Working with causal inference methods |
| `visualization.md` | graph twoway/bar/box/histogram to ggplot2/plotly | Reading or writing visualization code |
| `survey-spatial-ml.md` | svy: commands, spatial data, machine learning to survey/sf/tidymodels | Working with surveys, spatial data, or ML |
| `workflow-environment.md` | Do-files/log/macros/ado/ssc to R/DAAF execution model | Adapting to DAAF's execution model |
| `external-resources.md` | Curated guides and tutorials with provenance | Seeking additional learning materials |
| `gotchas.md` | Common Stata-user mistakes in R | Debugging or reviewing code from Stata perspective |

### Reading Order

1. **Stata user auditing DAAF code:** `paradigm-differences.md` then the relevant domain file (e.g., `data-management.md` for wrangling, `regression-modeling.md` for models) then `gotchas.md`
2. **Agent annotating code with Stata equivalents:** Agent Code Annotation Protocol section below, then the relevant domain file for the code being annotated
3. **Learning R from Stata background:** `paradigm-differences.md` then `data-management.md` then `workflow-environment.md` then `external-resources.md`
4. **Looking up a specific Stata command translation:** Quick Decision Trees below, then the relevant reference file

## Quick Decision Trees

### "How do I do X from Stata in R?"

```
What kind of Stata command?
+-  Data management (gen, replace, keep, drop, merge, reshape, collapse)
|   +-- ./references/data-management.md
+-  Group operations (by:, bysort, egen)
|   +-- ./references/data-management.md
+-  Regression / estimation (regress, areg, reghdfe, xtreg, logit, probit)
|   +-- ./references/regression-modeling.md
+-  Post-estimation (margins, test, lincom, nlcom, predict, esttab)
|   +-- ./references/regression-modeling.md
+-  Causal inference (diff, did_multiplegt, rdrobust, teffects, synth)
|   +-- ./references/causal-inference.md
+-  Surveys (svyset, svy:)
|   +-- ./references/survey-spatial-ml.md
+-  Plotting (graph twoway, histogram, graph bar)
|   +-- ./references/visualization.md
+-  String/date manipulation (substr, strpos, date, mdy)
|   +-- ./references/strings-dates-labels.md
+-  Value labels (label define, encode, decode)
|   +-- ./references/strings-dates-labels.md
+-- Programming (local, global, foreach, forvalues, tempvar, preserve)
    +-- ./references/workflow-environment.md
```

### "Why does this R code look different from Stata?"

```
What looks unfamiliar?
+-  Pipe operator (|> or %>%)
|   +-- ./references/paradigm-differences.md
+-  Missing values (NA vs .)
|   +-- ./references/paradigm-differences.md
+-  No single "dataset" -- multiple data frames everywhere
|   +-- ./references/paradigm-differences.md
+-  Value labels / factors
|   +-- ./references/paradigm-differences.md
+-  Formula interface (~) in model calls
|   +-- ./references/regression-modeling.md
+-  No `by:` prefix -- group_by() instead
|   +-- ./references/paradigm-differences.md
+-- library() calls and namespacing
    +-- ./references/gotchas.md
```

### "I want to translate a Stata do-file to R"

```
What does the do-file do?
+-  Loads and wrangles data (use, gen, replace, keep, merge, collapse)
|   +-- ./references/data-management.md
+-  Runs regressions (regress, xtreg, reghdfe, ivregress)
|   +-- ./references/regression-modeling.md
+-  Creates tables (esttab, outreg2, margins)
|   +-- ./references/regression-modeling.md
+-  Creates plots (graph twoway, histogram)
|   +-- ./references/visualization.md
+-  Uses survey weights (svyset, svy:)
|   +-- ./references/survey-spatial-ml.md
+-  Multiple of the above
|   +-- Start with ./references/paradigm-differences.md, then each relevant file
+-- Uses macros, loops, or programs
    +-- ./references/workflow-environment.md
```

### "Something isn't working and I think it's a Stata habit"

```
What went wrong?
+-  Missing values behaving differently than expected
|   +-- ./references/paradigm-differences.md
+-  gen/replace pattern not translating
|   +-- ./references/gotchas.md
+-  Merge producing wrong results
|   +-- ./references/gotchas.md
+-  Model output looks different from Stata
|   +-- ./references/regression-modeling.md
+-  Off-by-one error (0-indexed vs 1-indexed)
|   +-- ./references/gotchas.md
+-  `by:` / `_n` / `_N` not available
|   +-- ./references/paradigm-differences.md
+-- Macro syntax not working
    +-- ./references/gotchas.md
```

### "Which R package replaces my Stata command?"

```
Which Stata command?
+-  regress / areg / reghdfe -> fixest
|   +-- ./references/regression-modeling.md
+-  xtreg (fe/re) -> fixest (FE) / plm (RE)
|   +-- ./references/regression-modeling.md
+-  ivregress / ivreg2 / ivreghdfe -> fixest (ivreg not pre-installed)
|   +-- ./references/regression-modeling.md
+-  logit / probit / ologit / mlogit -> stats::glm / MASS / nnet
|   +-- ./references/regression-modeling.md
+-  poisson / nbreg / ppmlhdfe -> fixest fepois / MASS::glm.nb
|   +-- ./references/regression-modeling.md
+-  margins / marginsplot -> marginaleffects
|   +-- ./references/regression-modeling.md
+-  esttab / outreg2 -> fixest etable / modelsummary
|   +-- ./references/regression-modeling.md
+-  test / lincom / nlcom -> car::linearHypothesis / marginaleffects hypotheses()
|   +-- ./references/regression-modeling.md
+-  gen / replace / drop / keep / sort -> dplyr
|   +-- ./references/data-management.md
+-  merge / append -> dplyr joins / bind_rows
|   +-- ./references/data-management.md
+-  collapse / egen -> dplyr summarise / mutate + group_by
|   +-- ./references/data-management.md
+-  reshape long/wide -> tidyr pivot_longer / pivot_wider
|   +-- ./references/data-management.md
+-  graph twoway / histogram / graph bar -> ggplot2
|   +-- ./references/visualization.md
+-  svyset / svy: -> survey package
|   +-- ./references/survey-spatial-ml.md
+-  rdrobust -> rdrobust (R, same authors)
|   +-- ./references/causal-inference.md
+-  binscatter -> binsreg (R, same authors)
|   +-- ./references/causal-inference.md
+-  synth -> augsynth / Synth (R)
|   +-- ./references/causal-inference.md
+-- ado-file / ssc install -> install.packages()
    +-- ./references/workflow-environment.md
```

## Command Mapping Overview

| Stata Command(s) | R Package | Fidelity | Key Difference |
|-------------------|-----------|----------|----------------|
| `regress`, `areg`, `reghdfe` | fixest | Very High | Near-identical formula syntax; `\|` for FE absorption |
| `xtreg, fe` | fixest | Very High | No `xtset` needed; FE specified in formula |
| `xtreg, re` | plm | High | Requires panel structure via `pdata.frame` or formula index |
| `ivregress`, `ivreg2`, `ivreghdfe` | fixest (`ivreg` not pre-installed) | Very High | Three-part formula for IV in fixest; `ivreg` is not pre-installed and runtime installs are blocked (see Package availability note below) |
| `logit`, `probit`, `ologit`, `mlogit` | stats::glm / MASS / nnet | High | `family = binomial` for logit; separate packages for ordered/multinomial |
| `poisson`, `ppmlhdfe` | fixest `fepois` / stats::glm | Very High | `fepois` for Poisson with multi-way FE |
| `margins`, `marginsplot` | marginaleffects | Very High | Same author as R version; near-identical API |
| `esttab`, `outreg2` | fixest `etable()` / modelsummary | High | Publication-quality tables with flexible output formats |
| `gen`, `replace`, `drop`, `keep`, `sort` | dplyr | Medium | Verb grammar (mutate, filter, select) vs imperative commands |
| `merge`, `append` | dplyr joins, `bind_rows` | High | Named join types (left_join, inner_join) vs merge syntax |
| `collapse`, `egen` | dplyr `summarise` / `mutate` + `group_by` | High | Must choose summarise (collapse) vs mutate (window) |
| `reshape long/wide` | tidyr `pivot_longer` / `pivot_wider` | High | More explicit column specification |
| `graph twoway`, `histogram`, `graph bar` | ggplot2 | Medium | Grammar of graphics vs imperative graph syntax |
| `svyset`, `svy:` | survey | Very High | `svydesign()` + `svymean()` etc.; mature, comprehensive |
| `rdrobust`, `rdplot` | rdrobust (R) | Very High | Same authors; identical API |
| `binscatter`, `binsreg` | binsreg (R) | Very High | Same authors; identical API |
| `synth` | augsynth / Synth | High | Multiple implementations available |
| `local`, `global`, `foreach`, `forvalues` | R variables, `for` loops | Low | Fundamentally different paradigm (text substitution vs value binding) |

**Fidelity key:** Very High = same authors, near-identical API. High = same capability, similar syntax. Medium = same capability, different API patterns. Low = fundamentally different paradigm requiring conceptual remapping.

> **Package availability:** The core mappings above (`fixest`, `plm`, `survey`, `marginaleffects`, `rdrobust`, base `stats`, `dplyr`/`tidyr`, `ggplot2`) are pre-installed in DAAF. The specialized causal packages — `ivreg`, `binsreg`, `augsynth`, `Synth`, `MatchIt`, `did`, `rddensity` — are NOT pre-installed (for IV, pre-installed `fixest` three-part formulas or `plm` cover most cases), and runtime installs are blocked in DAAF (`install.packages()` is refused both at the command line and inside executed scripts — see CLAUDE.md § Runtime Package Installation). If one of these packages is genuinely required, escalate to the user to add it to the Dockerfile (user additions block) and rebuild before use.

## Library Versions

Translations in this skill reference specific library versions. R versions are
pinned in DAAF's Docker environment (R 4.5.3). Stata versions reference the
current release as of May 2026. When syntax or behavior has changed between
versions, the reference files note the change.

| R Package | DAAF Version | Stata Equivalent | Stata Version |
|---|---|---|---|
| dplyr + tidyr | 1.2.0, 1.3.2 | Data management commands (gen, replace, merge, etc.) | Stata 18 |
| fixest | 0.14.0 | regress, areg, reghdfe, ivreghdfe, ppmlhdfe, esttab | Stata 18 + reghdfe 6.x |
| stats (base R) | 4.5.x | regress, logit, probit, glm | Stata 18 |
| plm | 2.6-7 | xtreg | Stata 18 |
| systemfit | not pre-installed | sureg | Stata 18 |
| ggplot2 | 4.0.2 | graph twoway, graph bar, graph box, histogram | Stata 18 |
| plotly (R) | 4.12.0 | (no direct Stata equivalent; interactive charts) | N/A |
| survey | 4.5 | svyset, svy: prefix commands | Stata 18 |
| marginaleffects | 0.32.0 | margins, marginsplot, lincom, nlcom | Stata 18 |
| rdrobust (R) | 3.0.0 | rdrobust, rdplot, rdbwselect | rdrobust (SSC) |
| binsreg (R) | not pre-installed | binsreg, binscatter | binsreg (SSC) |
| modelsummary | 2.6.0 | esttab, outreg2 | Stata 18 |
| sandwich + lmtest | 3.1-1, 0.9-40 | robust, vce(robust), vce(hc3) | Stata 18 |
| MASS | 7.3-x | nbreg, ologit | Stata 18 |
| nnet | 7.3-x | mlogit | Stata 18 |
| car | 3.1-x | test, lincom | Stata 18 |
| sf + terra | 1.1-0, 1.9-11 | spmap, spregress | Stata 18 |
| tidymodels | 1.4.1 | (limited; teffects, psmatch2 partially) | Stata 18 |

**Stata version note:** Stata 18 is the current release as of May 2026. Most command
mappings apply to Stata 15+; version-specific features (frames, `hdidregress`) are noted
in the reference files.

## Top 10 Paradigm Differences

These are the friction points Stata users encounter most frequently when reading or writing DAAF R code. Each is covered in depth in the referenced file.

| # | Friction Point | Stata Way | R Way | Reference |
|---|---------------|-----------|-------|-----------|
| 1 | Single-dataset model | One dataset in memory; commands implicit | Multiple data frames as variables; must specify which | `paradigm-differences.md` |
| 2 | Missing values | `.` = +infinity; 27 types (`.a`-`.z`) | `NA` excluded from comparisons; one NA type per atomic type | `paradigm-differences.md` |
| 3 | Value labels | Three-layer system (data, variable, value labels) | `factor()` with levels and labels; ordering built-in | `paradigm-differences.md` |
| 4 | `by:`/`_n`/`_N` system | `bysort group: gen x = _N` | `group_by(group) \|> mutate(x = n())` | `paradigm-differences.md` |
| 5 | In-place modification | `replace var = expr` modifies data directly | `df <- df \|> mutate(var = expr)` creates new data frame | `paradigm-differences.md` |
| 6 | Macro system | `` `local' `` and `$global` text substitution | R variables + `paste0()` / `glue::glue()` | `paradigm-differences.md` |
| 7 | Formula interface | `regress y x1 x2` (bare names, space-separated) | `lm(y ~ x1 + x2, data = df)` (formula with `~` and `+`) | `regression-modeling.md` |
| 8 | Verb grammar | `gen z = x * 2` (command-based) | `df \|> mutate(z = x * 2)` (pipe-based verbs) | `data-management.md` |
| 9 | 1-based indexing | `_n` starts at 1; `var[1]` = first obs | R also 1-based (unlike Python) -- less friction here | `gotchas.md` |
| 10 | Package model | `ssc install pkg` then use immediately | `library(pkg)` required at top of script | `gotchas.md` |

## Agent Code Annotation Protocol

This section defines when and how code-producing agents add inline Stata-equivalent comments to DAAF R scripts.

### When to Annotate

Annotations are added **only when the orchestrator explicitly passes a Stata-background directive** to the agent. This is not a default behavior.

**Trigger conditions** (orchestrator activates this when any apply):
- User states they have a Stata background
- User requests Stata-equivalent comments in code
- User asks to understand R code from a Stata perspective

**How the orchestrator passes the directive:** The orchestrator adds the following to the agent prompt:

> "User has Stata background. Load stata-r-translation skill. Add inline Stata-equivalent comments for non-trivial data operations."

### Comment Format

```r
# Stata: keep if enrollment > 500
df <- df |> filter(enrollment > 500)

# Stata: gen log_enroll = log(enrollment)
df <- df |> mutate(log_enroll = log(enrollment))

# Stata: bysort state: egen mean_score = mean(test_score)
df <- df |> group_by(state) |> mutate(mean_score = mean(test_score)) |> ungroup()

# Stata: reghdfe wage education experience, absorb(industry year) cluster(state)
fit <- feols(wage ~ education + experience | industry + year,
             data = df, vcov = ~state)

# Stata: drop if missing(income)
df <- df |> filter(!is.na(income))

# Stata: merge 1:1 school_id using "districts.dta", keep(3) nogen
df <- df |> inner_join(districts, by = "school_id")
```

### What to Annotate

- **Annotate:** Data wrangling (dplyr/tidyr operations), modeling calls (fixest, stats, plm), visualization layer construction (ggplot2, plotly), causal inference method calls, survey estimation calls
- **Do NOT annotate:** `library()` calls, `cat()`/`stopifnot()` validation lines, file I/O boilerplate (`arrow::read_parquet`, `arrow::write_parquet`), config sections, section separator comments

### Rules

- One `# Stata:` comment per logical operation, placed on the line immediately above the R code
- Keep annotations to a single line; abbreviate complex Stata command sequences if needed
- Stata annotations are **in addition to** standard IAT comments (`# INTENT:`, `# REASONING:`, `# ASSUMES:`), not a replacement
- Consumer agents: research-executor, code-reviewer, debugger, data-ingest

## Related Skills

| Skill | Relationship |
|-------|-------------|
| `tidyverse` | R-side data wrangling -- detailed API reference for dplyr/tidyr (the gen/replace/merge/collapse equivalent) |
| `fixest` | R-side fixed effects regression -- detailed API for the regress/reghdfe/ivregress equivalent |
| `ggplot2` | R-side static visualization -- detailed API for the graph twoway equivalent |
| `plotly-r` | R-side interactive visualization -- no direct Stata equivalent |
| `r-stats` | R-side general modeling -- covers base R stats, sandwich, lmtest (logit, probit, glm equivalents) |
| `plm` | R-side panel/IV models -- covers xtreg equivalents (plm has no SUR estimator; for sureg see `systemfit` in regression-modeling.md) |
| `survey-r` | R-side survey analysis -- covers svyset and svy: prefix command equivalents |
| `sf-terra` | R-side spatial data -- covers Stata spmap/spregress equivalents |
| `tidymodels` | R-side ML -- covers limited teffects/matching equivalents |
| `quarto` | R-side notebooks -- replaces do-file + log workflow |
| `stata-python-translation` | Parallel skill for Stata-background users reading Python code |
| `r-python-translation` | R-to-Python translation for R users moving to DAAF's Python stack |

**Note:** Individual tool skills contain library-specific usage guidance (syntax, gotchas, performance). This skill provides the Stata-to-R conceptual bridge -- use both together when a Stata-background user is working with a specific library.

**ML interpretation/fairness asymmetry (honest signal):** Python's ML interpretation and fairness ecosystem is genuinely deeper (SHAP, fairlearn, and related tooling). The R-side equivalents (iml, DALEX, kernelshap, fairmodels) are installed and covered by the `tidymodels` skill's `interpretation.md` and `fairness.md`, so real R workflows exist for these tasks -- but for ML-heavy interpretation or fairness translation questions the Python direction carries more depth. For those, `stata-python-translation` (Stata-to-Python) may map to a richer target ecosystem than the R side offers.

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Single-dataset model (one dataset in memory) | `./references/paradigm-differences.md` |
| Missing values (. vs NA) | `./references/paradigm-differences.md` |
| Extended missing values (.a-.z) | `./references/paradigm-differences.md` |
| Value labels (label define, label values) vs factors | `./references/paradigm-differences.md` |
| Variable labels (label variable) | `./references/paradigm-differences.md` |
| by: prefix and _n/_N system variables | `./references/paradigm-differences.md` |
| In-place modification vs copy-on-modify | `./references/paradigm-differences.md` |
| Macro system (local, global) | `./references/paradigm-differences.md` |
| Estimation and e()/r() stored results | `./references/paradigm-differences.md` |
| Type system (destring/tostring vs as.numeric/as.character) | `./references/paradigm-differences.md` |
| Panel data operators (L./F./D. vs lag/lead) | `./references/paradigm-differences.md` |
| Package model (ssc install vs install.packages) | `./references/paradigm-differences.md` |
| gen / replace / rename | `./references/data-management.md` |
| drop / keep (variables and observations) | `./references/data-management.md` |
| sort / gsort | `./references/data-management.md` |
| merge 1:1 / m:1 / 1:m | `./references/data-management.md` |
| append | `./references/data-management.md` |
| reshape long / reshape wide | `./references/data-management.md` |
| collapse (aggregation) | `./references/data-management.md` |
| egen functions (mean, sum, count, rowtotal, group, tag) | `./references/data-management.md` |
| encode / decode | `./references/strings-dates-labels.md` |
| String functions (substr, strpos, subinstr, regexm) | `./references/strings-dates-labels.md` |
| Date system (epoch, %td, mdy(), date()) | `./references/strings-dates-labels.md` |
| destring / tostring | `./references/strings-dates-labels.md` |
| regress (OLS) | `./references/regression-modeling.md` |
| areg / reghdfe (fixed effects) | `./references/regression-modeling.md` |
| xtreg fe / xtreg re (panel models) | `./references/regression-modeling.md` |
| ivregress / ivreg2 / ivreghdfe (IV) | `./references/regression-modeling.md` |
| logit / probit / ologit / mlogit | `./references/regression-modeling.md` |
| poisson / nbreg / ppmlhdfe | `./references/regression-modeling.md` |
| sureg (seemingly unrelated regression) | `./references/regression-modeling.md` |
| margins / marginsplot (marginal effects) | `./references/regression-modeling.md` |
| test / lincom / nlcom (hypothesis testing) | `./references/regression-modeling.md` |
| esttab / outreg2 (regression tables) | `./references/regression-modeling.md` |
| predict (fitted values, residuals) | `./references/regression-modeling.md` |
| Robust and clustered standard errors | `./references/regression-modeling.md` |
| Factor variable notation (i., c., #, ##) | `./references/regression-modeling.md` |
| diff / did_multiplegt / csdid (DiD) | `./references/causal-inference.md` |
| eventstudyinteract / event studies | `./references/causal-inference.md` |
| rdrobust / rdplot (regression discontinuity) | `./references/causal-inference.md` |
| teffects / psmatch2 / cem (matching) | `./references/causal-inference.md` |
| synth / synth_runner (synthetic control) | `./references/causal-inference.md` |
| binscatter / binsreg | `./references/causal-inference.md` |
| graph twoway scatter / line / area / connected | `./references/visualization.md` |
| graph bar / graph box / histogram / kdensity | `./references/visualization.md` |
| graph export | `./references/visualization.md` |
| coefplot / iplot | `./references/visualization.md` |
| svyset / svy: prefix | `./references/survey-spatial-ml.md` |
| svy: mean / total / proportion / ratio | `./references/survey-spatial-ml.md` |
| svy: regress / logit | `./references/survey-spatial-ml.md` |
| Spatial data analysis | `./references/survey-spatial-ml.md` |
| Machine learning (teffects, matching workarounds) | `./references/survey-spatial-ml.md` |
| Do-file execution model | `./references/workflow-environment.md` |
| Log files (log using) | `./references/workflow-environment.md` |
| Ado-files and ssc install | `./references/workflow-environment.md` |
| Macros in loops (foreach, forvalues) | `./references/workflow-environment.md` |
| tempvar / tempfile / preserve / restore | `./references/workflow-environment.md` |
| quietly / capture / noisily | `./references/workflow-environment.md` |
| Curated Stata-to-R migration guides | `./references/external-resources.md` |
| Textbooks with trilingual code (Stata/R/Python) | `./references/external-resources.md` |
| Package documentation links | `./references/external-resources.md` |
| Tutorial recommendations with provenance | `./references/external-resources.md` |
| gen/replace pattern not translating | `./references/gotchas.md` |
| Missing value comparison traps | `./references/gotchas.md` |
| drop if -> filter(NOT) negation trap | `./references/gotchas.md` |
| Merge diagnostics | `./references/gotchas.md` |
| egen rowtotal missing-value behavior | `./references/gotchas.md` |
| Robust SE syntax differences | `./references/gotchas.md` |
| Macro syntax in R context | `./references/gotchas.md` |
| Error message translation table | `./references/gotchas.md` |
