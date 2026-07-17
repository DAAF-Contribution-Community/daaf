# Workflow and Environment: Stata to DAAF R

Stata's do-file execution model maps naturally to DAAF's file-first approach.
The mental model of "write a script, execute it, review the log" translates
directly to "write an R script, execute via run_with_capture.sh, review the
appended output."

---

## Do-Files to R Scripts

### Stata Do-File

```stata
clear all
set more off
log using "analysis_log.txt", replace
use "schools.dta", clear
drop if missing(enrollment)
gen log_enroll = log(enrollment)
regress test_score log_enroll poverty_rate, robust
log close
```

### DAAF R Script

```r
# scripts/stage6_clean/01_clean-schools.R
# --- Config ---
library(dplyr)
library(arrow)

BASE_DIR <- "/daaf"
PROJECT_DIR <- file.path(BASE_DIR, "research/2026-01-24_School_Analysis")

# --- Load ---
# INTENT: Load raw school data for cleaning
df <- read_parquet(file.path(PROJECT_DIR, "data/raw/schools.parquet"))
cat("Loaded:", nrow(df), "rows x", ncol(df), "cols\n")

# --- Transform ---
# INTENT: Remove records with missing enrollment for complete-case analysis
# REASONING: 2.1% of records have null enrollment; confirmed MCAR in profiling
# ASSUMES: Missingness is MCAR
df <- df |> filter(!is.na(enrollment))
df <- df |> mutate(log_enroll = log(enrollment))

# --- Validate ---
stopifnot(nrow(df) > 0)
cat("Rows after cleaning:", nrow(df), "\n")

# --- Save ---
write_parquet(df, file.path(PROJECT_DIR, "data/processed/schools_clean.parquet"))
cat("Saved cleaned data\n")
```

### Why the Transition Is Natural

| Stata Do-file | DAAF R Script | Similarity |
|---------------|---------------|------------|
| `log using` | `run_with_capture.sh` appends output | Same purpose: audit trail |
| Sequential, top-to-bottom | Sequential, top-to-bottom | Identical model |
| `clear all` resets state | Each script starts a fresh R process | Same clean-slate |
| No function definitions | No function definitions (DAAF convention) | Identical style |
| Comments | IAT comments (`# INTENT:`, `# REASONING:`, `# ASSUMES:`) | Structured version |

---

## Macros to Variables

```stata
local controls "education experience age"
local outcome "wage"
regress `outcome' `controls', robust

foreach outcome of local outcomes {
    regress `outcome' poverty_rate, robust
}
```

```r
controls <- c("education", "experience", "age")
outcome <- "wage"
formula <- as.formula(paste(outcome, "~", paste(controls, collapse = " + ")))
feols(formula, data = df, vcov = "hetero")

outcomes <- c("math", "reading", "science")
models <- list()
for (outcome in outcomes) {
  f <- as.formula(paste(outcome, "~ poverty_rate"))
  models[[outcome]] <- feols(f, data = df, vcov = "hetero")
}
etable(models)
```

---

## Program Flow

| Stata | R |
|-------|---|
| `foreach var of varlist x*` | `for (var in names(df)[startsWith(names(df), "x")])` |
| `forvalues i = 1/10` | `for (i in 1:10)` |
| `capture command` | `tryCatch(expr, error = function(e) ...)` |
| `quietly regress y x` | R is quiet by default; use `summary(fit)` to print |
| `display "text"` | `cat("text\n")` |
| `assert expr` | `stopifnot(expr)` |

---

## Package Management

| Stata | R |
|-------|---|
| `ssc install reghdfe` | `install.packages("fixest")` (pre-installed in DAAF Docker) |
| Use immediately | `library(fixest)` required at script top |
| `which reghdfe` | `packageVersion("fixest")` |
| `ado describe` | `installed.packages()` |
| Flat namespace (no prefix) | After `library()`, functions available by bare name |

---

## Project Structure

| Stata | DAAF R |
|-------|--------|
| `master.do` calls sub-scripts | Stage-based directories replace master |
| `01_clean.do` | `01_clean-ccd.R` |
| Overwrite do-file on fix | Immutable after execution (`_a.R`, `_b.R`) |
| `.dta` files | Parquet exclusively |
| `set seed 42` | `set.seed(42)` |
| `do "other_script.do"` | Each script independent; data via parquet |

---

## Common Workflow Questions

**"I want to browse my data."**
Use `cat(head(df, 20))` or `print(head(df, 20))` in your script.

**"I want to use preserve/restore."**
Just assign to a new variable: `df_subset <- df |> filter(...)`. The original
is unchanged (R's copy-on-modify semantics).

**"Where is my Results window?"**
Results come from `cat()` and `print()` statements. `run_with_capture.sh`
appends all output to the script file.

**"I want to pipe things together."**
Use the native pipe `|>` (R 4.1+):
```r
result <- df |>
  filter(year == 2020) |>
  group_by(state) |>
  summarise(mean_income = mean(income, na.rm = TRUE)) |>
  arrange(desc(mean_income))
```
