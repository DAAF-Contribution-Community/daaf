# Omnibus Plan: First-Class R Language Support in DAAF

**Date:** 2026-04-17 (revised 2026-04-18)
**Mode:** Framework Development
**Status:** PLAN (not yet executed) — user-confirmed scope
**Scope:** Add R as a first-class analysis language alongside Python in DAAF

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Design Philosophy](#2-design-philosophy)
3. [Architecture: Language Preference System](#3-architecture-language-preference-system)
4. [Wing 1: Container Environment (Dockerfile)](#4-wing-1-container-environment-dockerfile)
5. [Wing 2: Execution Infrastructure](#5-wing-2-execution-infrastructure)
6. [Wing 3: R Library Skills](#6-wing-3-r-library-skills)
7. [Wing 4: Data-Scientist Routing Skill](#7-wing-4-data-scientist-routing-skill)
8. [Wing 5: Agent Definitions](#8-wing-5-agent-definitions)
9. [Wing 6: CLAUDE.md and Core Framework](#9-wing-6-claudemd-and-core-framework)
10. [Wing 7: Reference Files and Templates](#10-wing-7-reference-files-and-templates)
11. [Wing 8: Orchestrator and Mode Files](#11-wing-8-orchestrator-and-mode-files)
12. [Wing 9: User-Facing Documentation](#12-wing-9-user-facing-documentation)
13. [Wing 10: Translation Skills Refactor](#13-wing-10-translation-skills-refactor)
14. [Wing 11: Notebook and Report Infrastructure](#14-wing-11-notebook-and-report-infrastructure)
15. [Wing 12: Data Source Skills](#15-wing-12-data-source-skills)
16. [Cross-Cutting Concerns](#16-cross-cutting-concerns)
17. [Dependency Graph and Execution Order](#17-dependency-graph-and-execution-order)
18. [Wing 13: Smoke Tests for R Library Skills](#18-wing-13-smoke-tests-for-r-library-skills)
19. [Risk Assessment](#19-risk-assessment)
20. [Validation Strategy](#20-validation-strategy)
21. [Appendix A: Complete File Inventory](#appendix-a-complete-file-inventory)
22. [Appendix B: R Package Manifest](#appendix-b-r-package-manifest)
23. [Appendix C: Skill Structure Template (R)](#appendix-c-skill-structure-template-r)
24. [Appendix D: Resolved Design Decisions](#appendix-d-resolved-design-decisions)

---

## 1. Executive Summary

This plan adds R as a **first-class analysis language** in DAAF, enabling users to
run entire pipelines in R with the same rigor, reproducibility, and auditability
that Python pipelines currently enjoy. This is not an annotation layer (which
already exists via `r-python-translation`) -- it is full execution support: R
scripts written, executed, validated, reviewed, and assembled into notebooks.

### Scope Metrics

| Dimension | Count |
|-----------|-------|
| New skill directories to create | ~13 (11 R library + 2 translation) |
| New reference files to write | ~75-110 |
| Existing files to modify | ~55-65 |
| New Dockerfile layers | 3-4 |
| New/modified shell scripts | 2-3 |
| Agent definitions to modify | 6 |
| Estimated new content | ~25,000-40,000 lines |
| Estimated modifications | ~2,000-4,000 lines across existing files |

### What Changes vs. What Stays

| Stays the Same | Changes |
|----------------|---------|
| IAT comment syntax (`# INTENT:`, etc.) | Execution dispatch (`python3` -> `python3` or `Rscript`) |
| Parquet-only data format rule | File extensions (`.py` -> `.py` or `.R`) |
| File-first execution philosophy | Code style guide (Python-specific -> dual) |
| Stage-based pipeline structure | Skill routing (Python-only -> language-conditional) |
| QA checkpoint classification system | QA checkpoint code templates (need R versions) |
| Section separator convention (`# ---`) | Notebook format (Marimo -> Marimo or Quarto) |
| Project folder structure (conceptual) | Agent skill-loading tables (add R skills) |
| All existing Python skills (untouched) | Translation skill architecture (annotation -> bidirectional) |

---

## 2. Design Philosophy

### 2.1. Parallel Tracks, Not Replacement

R support runs **alongside** Python. The framework does not become language-agnostic
in the abstract -- it becomes **bilingual with explicit routing**. A pipeline is
either Python or R, determined by the user's execution language preference. Mixed
pipelines (some scripts Python, some R) are explicitly out of scope for v1 due to
the complexity of cross-language data handoff validation.

### 2.2. The Language Preference as a Global Switch

The user's execution language preference acts as a **compile-time constant** that
flows through the entire framework:

```
User sets "Primary execution language: R"
  -> Orchestrator propagates to all code-producing agents
  -> Agents load R skills instead of Python skills
  -> Scripts written as .R files
  -> run_with_capture.sh dispatches to Rscript
  -> enforce-file-first.sh monitors Rscript
  -> Notebook assembled as Quarto .qmd
  -> Report cites R packages
```

### 2.3. Skill Parity Principle

Every Python library skill that is loadable during pipeline execution must have an
R counterpart skill that covers the same analytical capability. The R skill need
not mirror the Python skill's structure section-for-section (since the R ecosystem
is organized differently), but it must cover the same *use cases*.

### 2.4. R-First, Not R-Translated

R skills are written from an **R-native perspective**, not as translations of
Python skills. An R user loading the `ggplot2` skill should feel like they are
reading idiomatic R documentation, not a port of the `plotnine` skill. R patterns,
idioms, and ecosystem conventions are respected.

### 2.5. Forward-Compatible with Mixed-Language Pipelines

While mixed-language pipelines (some scripts Python, some R within a single
project) are **out of scope for v1**, all architectural decisions must be
**forward-compatible** with that future capability. Concretely:

- **Never hardcode a single-language assumption** where a language-agnostic
  abstraction is equally simple (e.g., `run_with_capture.sh` detects language
  from extension, not from a global flag)
- **Parquet as the universal data format** already enables cross-language data
  handoff -- preserve this
- **Per-script language detection** (via file extension) rather than per-project
  language settings in execution infrastructure
- **Do not add language guards** that would reject an `.R` file in a Python
  project or vice versa at the infrastructure level
- **The "Primary execution language" preference** determines what agents *default*
  to writing; it should not *prevent* the other language from being used

The goal: a future v2 could enable mixed pipelines by relaxing agent-level
constraints without modifying infrastructure.

---

## 3. Architecture: Language Preference System

### 3.1. Current State (2 settings)

```
Primary analysis language background: Python
Cross-language code annotations: disabled
```

The current system conflates "language background" with "execution language."
R/Stata support is annotation-only -- Python code is always generated, with
optional inline comments showing R/Stata equivalents.

### 3.2. Proposed State (3 settings)

```
Primary execution language: Python          # NEW — determines script language
Primary analysis language background: Python  # EXISTING — determines annotations
Cross-language code annotations: disabled     # EXISTING — enables/disables annotations
```

**How the three settings interact:**

| Execution Language | Background | Annotations | Result |
|-------------------|------------|-------------|--------|
| Python | Python | disabled | Current default. Python scripts, no annotations. |
| Python | R | enabled | Current R-background mode. Python scripts with `# R:` annotations. |
| Python | Stata | enabled | Current Stata-background mode. Python scripts with `# Stata:` annotations. |
| R | R | disabled | **New R-native mode.** R scripts, no annotations. |
| R | Python | enabled | **New.** R scripts with `# Python:` annotations for Python-background users. |
| R | Stata | enabled | **New.** R scripts with `# Stata:` annotations. |

### 3.3. Detection and Setup Flow

The orchestrator's Language Background Detection (already in the orchestrator skill)
expands to detect execution language preference:

**Explicit signals for R execution:**
- "I want to work in R"
- "Generate R code"
- "Use R for the analysis"
- "R pipeline"

**Implicit signals:**
- User provides `.R` scripts for revision
- User references R functions without translation context
- User's existing project contains `.R` files

**Proposed prompt:**
> "I see you'd like to work in R. DAAF supports full R pipelines -- I'll write
> all analysis scripts in R using tidyverse, fixest, ggplot2, and the rest of the
> R ecosystem. Would you also like Python-equivalent annotations in the code to
> help bridge the two ecosystems? I'll save your preference so it carries across
> sessions."

### 3.4. Propagation Architecture

When execution language is R, the orchestrator includes this directive in every
prompt to code-producing agents:

```
**Execution Language: R**
Load R library skills (tidyverse, ggplot2, fixest, etc.) instead of Python
equivalents (polars, plotnine, pyfixest, etc.). Write all scripts as .R files.
Use Rscript via run_with_capture.sh for execution. Follow the "Sequential Inline R"
code style from CLAUDE.md.
[If annotations enabled:] User has Python background. Load python-r-translation
skill. Add inline Python-equivalent comments for non-trivial data operations.
```

---

## 4. Wing 1: Container Environment (Dockerfile)

### 4.1. Current State

The Dockerfile is based on `ghcr.io/astral-sh/uv:0.9.30-python3.12-bookworm`
(Debian Bookworm). It installs:
- System deps: git, curl, jq, poppler-utils, GDAL/GEOS/PROJ
- Python packages via `uv pip install`: ~50 packages across 5 RUN layers
- Non-root user, Claude Code CLI

### 4.2. Changes Required

#### 4.2.1. New System Dependencies

Add a new RUN layer **after** the existing geospatial system libraries layer:

```dockerfile
# ============================================
# Install R and System Dependencies for R Packages
# ============================================
# Add CRAN repository for current R (4.6.x)
# Key: Johannes Ranke (95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7) replaced
# the former marutter_pubkey.asc which was removed from CRAN mirrors.
RUN apt-get update && apt-get install -y --no-install-recommends \
    dirmngr \
    gnupg \
    && gpg --keyserver keyserver.ubuntu.com \
       --recv-key '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7' \
    && gpg --armor --export '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7' \
       > /usr/share/keyrings/r-project.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/r-project.gpg] https://cloud.r-project.org/bin/linux/debian bookworm-cran46/" \
    > /etc/apt/sources.list.d/r-project.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    r-base \
    r-base-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Additional system libraries for R packages
# (libgdal-dev, libgeos-dev, libproj-dev already installed above for Python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gfortran \
    libcurl4-openssl-dev \
    libxml2-dev \
    libfontconfig1-dev \
    libudunits2-dev \
    libtbb-dev \
    libnetcdf-dev \
    libsqlite3-dev \
    libssl-dev \
    libhdf5-dev \
    cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

**Key notes:**
- `libudunits2-dev` is **critical** -- must be installed before `sf` R package
- `libtbb-dev` required by `terra`
- `cmake` required by `lightgbm` R bindings
- GDAL/GEOS/PROJ are already present (shared with Python geospatial stack)

#### 4.2.2. R Package Installation

Use Posit Public Package Manager (P3M) for binary packages on Debian Bookworm.
**r2u is Ubuntu-only and cannot be used with this Dockerfile's Debian base.**

```dockerfile
# ============================================
# Configure R Package Repository (P3M date-pinned snapshot for reproducibility)
# ============================================
# Pin to a specific date snapshot so rebuilds produce identical package versions.
# Update the date when intentionally upgrading R packages (and update skill metadata).
ARG P3M_SNAPSHOT_DATE=2026-04-15
RUN echo "options(repos = c(CRAN = 'https://p3m.dev/cran/__linux__/bookworm/${P3M_SNAPSHOT_DATE}'))" \
    >> /etc/R/Rprofile.site \
    && echo 'options(Ncpus = parallel::detectCores())' \
    >> /etc/R/Rprofile.site

# ============================================
# Install R Data Science Packages
# ============================================

# Core data manipulation and I/O
RUN Rscript -e 'install.packages(c( \
    "data.table", "dplyr", "tidyr", "tibble", "readr", "purrr", "stringr", \
    "forcats", "lubridate", "glue", "rlang", \
    "arrow", "readxl", "writexl", "haven", "jsonlite", "yaml" \
    ))'

# Statistics and econometrics
RUN Rscript -e 'install.packages(c( \
    "fixest", "sandwich", "lmtest", "car", "plm", "estimatr", \
    "marginaleffects", "rdrobust", "fwildclusterboot", \
    "survey", "rugarch", "broom", "modelsummary" \
    ))'

# Geospatial
RUN Rscript -e 'install.packages(c( \
    "sf", "terra", "stars", \
    "spdep", "spatialreg", "classInt", "exactextractr", \
    "leaflet", "maptiles", "tidygeocoder", "osmdata" \
    ))'

# Visualization
RUN Rscript -e 'install.packages(c( \
    "ggplot2", "scales", "ggridges", "ggrepel", "patchwork", "ggdist", \
    "plotly", "gt", "knitr", "kableExtra", "viridis" \
    ))'

# ML and interpretation
RUN Rscript -e 'install.packages(c( \
    "tidymodels", "ranger", "glmnet", "xgboost", "lightgbm", \
    "iml", "uwot", "fairmodels" \
    ))'
```

#### 4.2.3. Quarto Installation

```dockerfile
# ============================================
# Install Quarto CLI (language-agnostic notebook system)
# ============================================
RUN curl -fsSL https://github.com/quarto-dev/quarto-cli/releases/download/v1.7/quarto-1.7-linux-amd64.deb \
    -o /tmp/quarto.deb \
    && dpkg -i /tmp/quarto.deb \
    && rm /tmp/quarto.deb
```

**Note:** Pin the Quarto version (replace `v1.7` with the latest stable at
implementation time). Quarto is a standalone binary -- it does not depend on R
or Python package managers.

#### 4.2.4. Image Size Impact

| Component | Estimated Addition |
|-----------|--------------------|
| R base + dev | ~300-400 MB |
| Additional system deps | ~200-300 MB |
| Core R packages | ~400-600 MB |
| Geospatial R packages | ~300-500 MB |
| Viz + ML packages | ~200-400 MB |
| Quarto CLI | ~200-300 MB |
| **Total** | **~1.6-2.5 GB** |

Current image is estimated at 3-5 GB. Post-R the image will be ~5-7 GB. This is
acceptable for a comprehensive data science environment.

#### 4.2.5. Dockerfile Structure Decision

**Option A (recommended): Single Dockerfile, layered sections.**
Keep one Dockerfile with clearly separated Python and R sections. Docker layer
caching means unchanged Python layers don't rebuild when R layers change.

**Option B: Multi-stage or separate Dockerfiles.**
Rejected -- adds operational complexity without meaningful benefit. Users who want
Python-only can simply not use R features; the R layers add build time but not
runtime cost.

#### 4.2.6. Customization Documentation

Update the existing "CUSTOMIZATION" comment block in the Dockerfile to include R:

```
# To add an R package, append it to the appropriate Rscript install block below.
# For R packages needing C/Fortran libraries, add system deps to the apt-get block.
# See: user_reference/04_extending_daaf.md
```

---

## 5. Wing 2: Execution Infrastructure

### 5.1. `run_with_capture.sh` Modifications

**File:** `/daaf/scripts/run_with_capture.sh`
**Current:** Hardcodes `python3 "$SCRIPT_PATH"` on line 55.
**Change magnitude:** Small (~15 lines modified)

#### 5.1.1. Language Detection Logic

Add after the existing argument validation:

```bash
# Detect language from file extension
case "${SCRIPT_PATH##*.}" in
    py)
        INTERPRETER="python3"
        ;;
    R|r)
        INTERPRETER="Rscript"
        ;;
    *)
        echo "ERROR: Unsupported file extension: ${SCRIPT_PATH##*.}"
        echo "Supported: .py (Python), .R (R)"
        exit 1
        ;;
esac
```

Replace `python3 "$SCRIPT_PATH"` with `$INTERPRETER "$SCRIPT_PATH"`.

#### 5.1.2. Version Suffix Logic

Update the version suffix guidance (currently `${SCRIPT_PATH%.py}_a.py`):

```bash
# Language-aware version suffix
EXT="${SCRIPT_PATH##*.}"
BASE="${SCRIPT_PATH%.${EXT}}"
NEW_PATH="${BASE}_a.${EXT}"
```

#### 5.1.3. Compatibility

- The `# EXECUTION LOG` marker uses `#` comments -- works for both Python and R
- The log-appending mechanism uses `#` prefix -- works for both
- The timestamp/duration/exit-code recording is language-agnostic
- The `tee`-based stdout/stderr capture is language-agnostic
- **No separate `run_with_capture_r.sh` is needed** -- the existing script can
  handle both languages with the extension-detection addition

### 5.2. `enforce-file-first.sh` Modifications

**File:** `/daaf/.claude/hooks/enforce-file-first.sh`
**Current:** Only detects and blocks `python`/`python3` invocations.
**Change magnitude:** Moderate (~30 lines added)

#### 5.2.1. Add R Detection

The hook currently matches `python3?[.0-9]*` patterns. Add parallel detection:

```bash
# Block direct Rscript execution (must use run_with_capture.sh)
if echo "$COMMAND" | grep -qE '^\s*(Rscript|R\s+--vanilla|R\s+-e|Rscript\.exe)'; then
    # Check if it's within run_with_capture.sh (allowed)
    if echo "$COMMAND" | grep -q 'run_with_capture\.sh'; then
        exit 0  # Allowed
    fi
    echo "BLOCKED: Direct Rscript execution. Use run_with_capture.sh wrapper."
    exit 2
fi
```

#### 5.2.2. Whitelist Updates

The current whitelist allows `python3` for framework utilities. Add equivalent for
R if any R-based utilities are created (unlikely in v1, but the pattern should be
documented for future reference).

### 5.3. `settings.json` Updates

**File:** `/daaf/.claude/settings.json`
**Current:** `permissions.allow` includes `"Bash(python *)"` and `"Bash(python3 *)"`.
**Change:** Add `"Bash(Rscript *)"` to the allow list.

Also review the `permissions.deny` list for any patterns that would inadvertently
block R execution.

---

## 6. Wing 3: R Library Skills

### 6.1. Overview

Each Python library skill needs an R counterpart. These are **new skills**, not
modifications of existing ones. The Python skills remain unchanged.

### 6.2. Skill Mapping

| # | Python Skill | R Skill Name | R Packages Covered | Fidelity | Priority |
|---|-------------|-------------|-------------------|----------|----------|
| 1 | `polars` | `tidyverse` | dplyr, tidyr, readr, purrr, stringr, forcats, lubridate + data.table | Low (paradigm shift) | P1 - Critical |
| 2 | `plotnine` | `ggplot2` | ggplot2, scales, ggridges, ggrepel, patchwork, ggdist | High (plotnine IS ggplot2) | P1 - Critical |
| 3 | `plotly` | `plotly-r` | plotly (R), htmlwidgets | High (same library) | P2 |
| 4 | `geopandas` | `sf-terra` | sf, terra, stars, spdep, spatialreg | Medium | P2 |
| 5 | `pyfixest` | `fixest` | fixest | Very High (same project) | P1 - Critical |
| 6 | `statsmodels` | `r-stats` | base R stats, sandwich, lmtest, car, broom | Medium | P1 - Critical |
| 7 | `linearmodels` | `plm` | plm, estimatr, lme4 | Medium | P2 |
| 8 | `scikit-learn` | `tidymodels` | tidymodels, recipes, parsnip, tune, ranger, glmnet, xgboost | Low (paradigm shift) | P2 |
| 9 | `svy` | `survey-r` | survey (Lumley) | High (R is the original) | P2 |
| 10 | `marimo` | `quarto` | Quarto CLI, knitr, rmarkdown | Low (different paradigm) | P1 - Critical |
| 11 | (tables) | `gt` | gt, kableExtra, modelsummary | High (gt is the R original) | P3 |

**Note:** `data.table` is covered within the `tidyverse` skill as a performance
alternative (similar to how the `polars` Python skill acknowledges pandas). No
standalone `data-table` skill is needed for v1.

### 6.3. Skill Structure (Common Pattern)

Each R skill follows the same structural template as Python skills (see Appendix C):

1. **Frontmatter:** `name`, `description`, `metadata` with `domain: r-library`
2. **Identity paragraph:** Scope, "use when", "use X instead" routing
3. **"What is [Library]?"** section
4. **Version Notes:** Current version, breaking changes
5. **"How to Use This Skill"** section with reference file table
6. **Related Skills:** Cross-references to Python counterpart and other R skills
7. **Quick Decision Trees:** R-native routing
8. **File-First Execution:** Adapted for R (Rscript, `.R` files)
9. **Quick Reference:** Essential R syntax, `library()` calls, core operations
10. **Topic Index**
11. **Citation**

### 6.4. Reference Files Per Skill (Estimated)

| R Skill | Est. Reference Files | Est. Total Lines | Notes |
|---------|---------------------|-----------------|-------|
| `tidyverse` | 10-12 | 3,500-4,500 | Covers dplyr, tidyr, readr, purrr, stringr, data I/O; includes data.table as performance alternative |
| `ggplot2` | 6-8 | 1,500-2,500 | Geoms, aesthetics, themes, extensions, facets |
| `plotly-r` | 5-6 | 1,500-2,000 | plot_ly(), ggplotly(), layouts, export |
| `sf-terra` | 8-10 | 3,000-4,000 | Vector (sf), raster (terra), spatial stats, mapping |
| `fixest` | 6-8 | 2,000-2,500 | feols, fepois, etable, coefplot, DiD |
| `r-stats` | 6-8 | 3,000-4,000 | lm/glm, diagnostics, sandwich, hypothesis tests |
| `plm` | 5-7 | 2,000-2,500 | Panel models, RE/FE, IV, dynamic panels |
| `tidymodels` | 10-14 | 3,000-4,000 | recipes, parsnip, workflows, tune, resampling |
| `survey-r` | 3-5 | 1,500-2,000 | svydesign, svyglm, calibration, replication |
| `quarto` | 6-8 | 2,000-3,000 | .qmd format, code chunks, output formats, publishing |
| `gt` | 3-4 | 1,000-1,500 | Table creation, formatting, export |
| **TOTAL** | **~68-90** | **~23,000-34,500** | |

### 6.5. Authoring Approach

Each R skill should be authored by a `framework-engineer` subagent that:
1. Reads the corresponding Python skill as a structural model
2. Reads the `r-python-translation` skill's reference files for mapping knowledge
3. Uses WebSearch to verify current R package APIs and best practices
4. Writes R-native content following DAAF skill authoring conventions
5. Includes cross-references to the Python counterpart in the Related Skills table

### 6.6. Skill Naming Convention

R skills use descriptive names reflecting the R package, not the Python equivalent:

- `tidyverse` (not `r-polars`)
- `ggplot2` (not `r-plotnine`)
- `fixest` (not `r-pyfixest`)
- `sf-terra` (not `r-geopandas`)

This follows the R-First principle (Section 2.4).

---

## 7. Wing 4: Data-Scientist Routing Skill

### 7.1. Current State

The `data-scientist` skill (`/daaf/.claude/skills/data-scientist/SKILL.md`, 827
lines) is the methodology hub. It routes to Python library skills:

```
Statistical modeling -> load statsmodels or pyfixest or linearmodels
Visualization -> load plotnine (static) or plotly (interactive)
Geospatial -> load geopandas
ML -> load scikit-learn
Survey -> load svy
```

Its 15 reference files are **mostly methodology-focused** (concepts, not syntax),
making them largely reusable across languages.

### 7.2. Required Changes

#### 7.2.1. Language-Conditional Routing

The routing decision trees need a language fork. Two implementation options:

**Option A (recommended): Language-conditional routing in SKILL.md**

Add a section at the top of the SKILL.md:

```markdown
## Language Routing

This skill routes to **language-specific library skills** based on the execution
language set in the agent's prompt:

| Method | Python Skill | R Skill |
|--------|-------------|---------|
| Data manipulation | `polars` | `tidyverse` |
| Static visualization | `plotnine` | `ggplot2` |
| Interactive visualization | `plotly` | `plotly-r` |
| Fixed effects / DiD | `pyfixest` | `fixest` |
| OLS / GLM / time series | `statsmodels` | `r-stats` |
| Panel / IV / system | `linearmodels` | `plm` |
| Survey statistics | `svy` | `survey-r` |
| ML / clustering / PCA | `scikit-learn` | `tidymodels` |
| Geospatial | `geopandas` | `sf-terra` |
| Notebook | `marimo` | `quarto` |
| Tables | (great-tables) | `gt` |
```

Each existing decision tree that currently says "Load `pyfixest` skill" would
become "Load `pyfixest` skill (Python) or `fixest` skill (R)."

**Option B: Separate R data-scientist skill**

Rejected -- the methodology content (15 reference files, ~7,400 lines) is
language-agnostic. Duplicating it would create a maintenance burden.

#### 7.2.2. Reference File Audit

The 15 methodology reference files need auditing for Python-specific code snippets:

| Reference File | Python Code? | Action |
|----------------|-------------|--------|
| `eda-checklist.md` | Likely minimal | Audit and add R alternatives where present |
| `data-documentation.md` | Minimal | Audit |
| `transformation-validation.md` | Yes (Polars examples) | Add R dplyr/data.table alternatives |
| `code-documentation.md` | Yes (Python comment examples) | Add R equivalents (same `#` syntax, mostly compatible) |
| `research-questions.md` | No | No change |
| `visualization-design.md` | Minimal (concept-focused) | Audit |
| `visualization-execution.md` | Yes (plotnine/plotly code) | Add R ggplot2/plotly alternatives |
| `descriptive-analysis.md` | Yes (Polars code) | Add R alternatives |
| `statistical-modeling.md` | Yes (statsmodels code) | Add R lm/glm alternatives |
| `causal-inference.md` | Yes (pyfixest code) | Add R fixest alternatives |
| `survey-analysis.md` | Yes (svy code) | Add R survey alternatives |
| `geospatial-analysis.md` | Yes (geopandas code) | Add R sf alternatives |
| `geospatial-operations.md` | Yes (geopandas code) | Add R sf/terra alternatives |
| `exploratory-unsupervised.md` | Yes (sklearn code) | Add R tidymodels/stats alternatives |
| `supervised-ml.md` | Yes (sklearn code) | Add R tidymodels alternatives |

**Approach:** For each reference file that contains code, add a parallel R code
block below each Python block, fenced with ` ```r `. Label blocks:

```
**Python:**
```python
df.filter(pl.col("year") == 2020)
```

**R:**
```r
df |> filter(year == 2020)
```
```

This keeps both languages visible in one document, which aids cross-language
understanding and reduces maintenance burden vs. separate files.

---

## 8. Wing 5: Agent Definitions

### 8.1. Agents Requiring Modification

Six agent definitions need updates to support R:

| Agent | File | Change Magnitude |
|-------|------|-----------------|
| `research-executor` | `.claude/agents/research-executor.md` | Major |
| `code-reviewer` | `.claude/agents/code-reviewer.md` | Major |
| `debugger` | `.claude/agents/debugger.md` | Moderate |
| `data-ingest` | `.claude/agents/data-ingest.md` | Moderate |
| `notebook-assembler` | `.claude/agents/notebook-assembler.md` | Major |
| `README.md` | `.claude/agents/README.md` | Minor |

### 8.2. research-executor Changes

The research-executor is the primary code-writing agent. Key changes:

1. **Skill loading table:** Add R skills as alternatives, conditional on execution
   language directive in the prompt:

   | When Task Involves | Python Skill | R Skill |
   |-------------------|-------------|---------|
   | Data manipulation | `polars` | `tidyverse` |
   | Fixed effects regression | `pyfixest` | `fixest` |
   | Static visualization | `plotnine` | `ggplot2` |
   | ... | ... | ... |

2. **Script file extension:** Where the agent currently writes `.py` files, it must
   write `.R` files when the execution language is R.

3. **Code patterns:** The agent's embedded code examples (validation snippets,
   template references) need R alternatives.

4. **Preloaded skill:** Currently preloads `data-scientist`. This remains unchanged
   (data-scientist handles the routing).

### 8.3. code-reviewer Changes

1. **QA script language:** Currently writes Python QA scripts to `scripts/cr/`.
   When reviewing R scripts, it must write R QA scripts.

2. **CR template:** The complete Python CR template (currently ~100 lines of
   Polars code) needs an R equivalent using dplyr/data.table.

3. **R-specific checks:** Add checks for common R issues:
   - Unintended factor coercion
   - Partial matching with `$`
   - Non-standard evaluation pitfalls
   - Missing `library()` calls

### 8.4. debugger Changes

1. **R error patterns:** Add R-specific error types to the "Modeling Library
   Gotchas" section:
   - `Error in ...`: general R errors
   - `subscript out of bounds`: indexing errors
   - `could not find function`: missing library loads
   - `non-conformable arguments`: dimension mismatches
   - `cannot allocate vector of size`: memory issues

2. **Diagnostic script language:** Write R diagnostic scripts when debugging R
   pipelines.

### 8.5. data-ingest Changes

1. **Profiling scripts:** Can be written in R when the user's execution language
   is R. Uses `arrow::read_parquet()`, `dplyr::glimpse()`, etc.

2. **API acquisition:** R equivalent of `requests` library: `httr2` package.

### 8.6. notebook-assembler Changes (Major)

This is the most impacted agent because Marimo is Python-only.

1. **Dual notebook support:** The agent must support:
   - **Marimo** (`.py` notebooks) for Python pipelines (current behavior, unchanged)
   - **Quarto** (`.qmd` notebooks) for R pipelines (new)

2. **Quarto assembly pattern:** Instead of Marimo's `def _():` cell wrappers,
   Quarto uses fenced code chunks:

   ````markdown
   ```{r}
   #| label: load-data
   #| echo: true
   library(arrow)
   df <- read_parquet("data/raw/2026-01-24_ccd_schools.parquet")
   ```
   ````

3. **Script-to-chunk conversion:** The existing logic for extracting script code
   and execution logs adapts to R scripts (which also use `#` comments).

4. **Preloaded skill:** Add `quarto` skill alongside `marimo` (conditional on
   execution language).

### 8.7. Agent README Updates

Update `.claude/agents/README.md`:
- Note R capability in agent descriptions
- Update the skill loading coordination table
- Add R to the "Tools Available" section where relevant

---

## 9. Wing 6: CLAUDE.md and Core Framework

### 9.1. User Preferences Section

**Current (lines 505-517):**
```markdown
- **Primary analysis language background:** Python
- **Cross-language code annotations:** disabled
```

**Proposed:**
```markdown
- **Primary execution language:** Python
  <!-- Options: Python, R. Determines the language for all pipeline scripts,
       notebooks, and validation code. -->
- **Primary analysis language background:** Python
  <!-- The user's native/preferred language for reading and understanding code.
       Used for annotation direction when cross-language annotations are enabled. -->
- **Cross-language code annotations:** disabled
  <!-- Set to "enabled" to have code-producing agents add inline comments showing
       equivalent syntax in the user's background language. Only meaningful when
       execution language differs from background language. -->
```

### 9.2. Code Style Section

**Current title:** "Code Style: Sequential Inline Python"

**Proposed:** Rename to "Code Style: Sequential Inline Scripts" and add R rules:

```markdown
## Code Style: Sequential Inline Scripts

All code produced by agents follows a **flat, sequential** style. Scripts read
top-to-bottom like lab notebooks.

### Python Rules
[existing content, moved under a subsection]

### R Rules

1. **No function definitions** -- No reusable functions, no `source()` of external
   modules. Exception: Quarto cell structure.
2. **Inline validation** -- Use `cat()` for output and `stopifnot()` for assertions,
   never a separate `validation.R` module.
3. **Section separators** -- Same convention: `# --- Config ---`, `# --- Load ---`,
   `# --- Transform ---`, `# --- Validate ---`, `# --- Save ---`
4. **Library calls at top** -- All `library()` calls in the `# --- Config ---`
   section.
5. **Pipe style** -- Use native pipe `|>` (R 4.1+), not magrittr `%>%`.
6. **No test files** -- Validation is inline (`stopifnot()` + `cat()`), not in
   `tests/` directories.
```

### 9.3. Execution Philosophy Section

Generalize "Python code" to "code":

**Current:** "You NEVER execute Python code interactively"
**Proposed:** "You NEVER execute code interactively (neither Python nor R)"

**Current:** "Never run `python script.py` directly"
**Proposed:** "Never run `python script.py` or `Rscript script.R` directly"

### 9.4. File Naming Conventions

Add `.R` as an alternative extension:

| File Type | Python Pattern | R Pattern |
|-----------|---------------|-----------|
| Script | `{step}_{task-name}.py` | `{step}_{task-name}.R` |
| Notebook | `YYYY-MM-DD_Title.py` | `YYYY-MM-DD_Title.qmd` |
| Versioned | `01_task_a.py` | `01_task_a.R` |

### 9.5. Example Project Structures

Add a parallel R example project structure showing `.R` scripts and `.qmd`
notebook.

### 9.6. Defense-in-Depth Table

Add row for R enforcement:

| Layer | Mechanism | Coverage |
|-------|-----------|----------|
| PreToolUse Hook (agent-scoped) | `enforce-file-first.sh` | Blocks direct `python`/`python3` AND `Rscript`/`R` execution |

---

## 10. Wing 7: Reference Files and Templates

### 10.1. Files Requiring Major Changes

#### `SCRIPT_EXECUTION_REFERENCE.md`

The "single source of truth for how scripts are written." Currently 1,460 lines,
entirely Python.

**Changes:**
- Add R script format template (parallel to the Python template)
- Add R shebang: `#!/usr/bin/env Rscript`
- Add R stage-specific examples (Stage 5-8) showing idiomatic R code
- Restructure as: "Part 1: Universal Protocol" + "Part 2: Python Templates" +
  "Part 3: R Templates"

**Estimated addition:** ~500-700 lines of R template content.

#### `VALIDATION_CHECKPOINTS.md`

Contains Python code templates for all validation checkpoints (CP1-CP4, CPP1-CPP4).
~45 Python code blocks.

**Changes:**
- Add R equivalents for each checkpoint code template
- R assertions use `stopifnot()` instead of `assert`
- R shape checks use `nrow()`/`ncol()` instead of `.shape`
- R null checks use `sum(is.na())` instead of `.null_count()`
- Restructure each checkpoint as: concept (language-agnostic) + Python code + R code

**Estimated addition:** ~400-600 lines of R validation code.

#### `QA_CHECKPOINTS.md`

Contains QA script templates (QA1-QA4b). All Python/Polars.

**Changes:**
- Add R QA script templates for each checkpoint level
- R QA scripts use dplyr for data inspection, `testthat`-style checks

**Estimated addition:** ~300-500 lines of R QA code.

#### `ERROR_RECOVERY.md`

Python-specific error types and recovery examples.

**Changes:**
- Add R error types section: parse errors, class mismatches, memory allocation
- Add R recovery code examples alongside Python ones
- Update script versioning to handle `.R` extensions

**Estimated addition:** ~150-250 lines.

### 10.2. Files Requiring Moderate Changes

| File | Change Description |
|------|-------------------|
| `BOUNDARIES.md` | Generalize "Execute Python interactively" to cover R. Add R-specific code practice boundaries (e.g., no bare `tryCatch()` without condition classes). |
| `PLAN_TEMPLATE.md` | Add R alternatives in artifact paths, key links patterns. Replace Polars examples with language-conditional versions. |
| `PLAN_TASKS_TEMPLATE.md` | Add R skill references alongside Python ones in action blocks. |
| `INLINE_AUDIT_TRAIL.md` | Minor -- change "all Python scripts" to "all scripts". Add R code examples. The `# INTENT:` syntax is identical. |
| `DATA_SOURCE_SKILL_TEMPLATE.md` | Add R code examples in Sections 9 (Data Access) and 11.5 (Multi-File Structure) alongside Python. |
| `CITATION_REFERENCE.md` | Add R package citations (fixest, survey, sf, ggplot2, etc.) to the Software & Tools table. |
| `STATE_TEMPLATE.md` | Update "marimo" reference to "marimo/Quarto" as language-conditional. |
| `REPORT_TEMPLATE.md` | Make Technical Notes language-conditional: "Python 3.12" or "R 4.x". |
| `REPRODUCTION_REPORT_TEMPLATE.md` | Add "R Version" field alongside "Python Version." |

### 10.3. Files Requiring Minor Changes

| File | Change Description |
|------|-------------------|
| `AI_DISCLOSURE_REFERENCE.md` | Note R tool citations where applicable. |
| `FRAMEWORK_INTEGRATION_CHECKLIST.md` | Already language-neutral. No changes needed. |
| `STATE_TEMPLATE_ONBOARDING.md` | Minor language references if present. |

---

## 11. Wing 8: Orchestrator and Mode Files

### 11.1. Orchestrator SKILL.md

**File:** `/daaf/.claude/skills/daaf-orchestrator/SKILL.md`

**Changes:**
1. **Language Background Detection (lines 58-88):** Expand to detect execution
   language preference alongside annotation preference. Add explicit signals list.
2. **User Language Preference Propagation (lines 482-488):** Add the R execution
   directive template (see Section 3.4 of this plan).
3. **Welcome Preamble:** Mention R support as a capability.
4. **Mode Confirmation Templates:** Where templates reference "Marimo notebook"
   as a deliverable, make language-conditional ("Marimo notebook" / "Quarto notebook").

### 11.2. Mode Reference Files

#### `full-pipeline-mode.md` (Major)

This is the largest mode file and the most Python-coupled.

1. **Pre-flight checklist:** Make deliverables language-conditional (Marimo vs. Quarto)
2. **Stage overview table:** Add R skills to skill-to-stage mappings:

   | Stage | Python Skills | R Skills |
   |-------|--------------|----------|
   | 5-6 | polars, education-data-query | tidyverse, arrow |
   | 7 | polars | tidyverse |
   | 8.1 | pyfixest, statsmodels, linearmodels, svy, scikit-learn | fixest, r-stats, plm, survey-r, tidymodels |
   | 8.2 | plotnine, plotly, geopandas | ggplot2, plotly-r, sf-terra |
   | 9 | marimo | quarto |

3. **Invocation templates:** Each agent dispatch template that currently says
   "Load `polars` skill" needs a language-conditional fork.
4. **Composite execution pattern:** Works identically for R -- the concept of
   "one script, one execution, one QA review" is language-agnostic.

#### `data-onboarding-mode.md` (Moderate)

1. Script paths: `.py` -> language-conditional
2. API acquisition: `requests` -> `httr2` for R
3. Profiling script templates: need R equivalents

#### `ad-hoc-collaboration-mode.md` (Minor)

1. Dispatch table: Add R skills alongside Python skills
2. The conversational nature makes this less language-coupled

#### `revision-and-extension-mode.md` (Minor)

1. Script versioning: handle `.R` extensions
2. Re-execution dispatch: language-conditional skill loading

#### `reproducibility-verification-mode.md` (Moderate)

1. Script decompilation: handle Quarto `.qmd` -> `.R` scripts
2. Re-execution: dispatch to `Rscript` via `run_with_capture.sh`
3. Output comparison: language-agnostic (parquet files)

### 11.3. Workflow Phase Files

| File | Changes |
|------|---------|
| `WORKFLOW_PHASE1_DISCOVERY.md` | Minor -- essentially language-agnostic already |
| `WORKFLOW_PHASE2_PLANNING.md` | Minor -- script path conventions |
| `WORKFLOW_PHASE3_ACQUISITION.md` | Moderate -- CP1/CP2 validation code, fetch templates |
| `WORKFLOW_PHASE4_ANALYSIS.md` | Major -- all Stage 7-9 content needs R alternatives |
| `WORKFLOW_PHASE5_SYNTHESIS.md` | Moderate -- verification code, notebook references |

### 11.4. Profiling Workflow

`WORKFLOW_PHASE_DO_PROFILING.md` and `WORKFLOW_PHASE_DO_AUTHORING.md`: All profiling
script templates need R equivalents. The profiling workflow structure (Parts A-D)
is language-agnostic; only the code templates change.

---

## 12. Wing 9: User-Facing Documentation

### 12.1. `README.md`

- Update capability description to mention R support
- Update the tech stack section to include R packages
- Update skill count if it changes

### 12.2. `user_reference/01_installation_and_quickstart.md`

- Note R availability in the environment
- No installation instructions needed (R comes pre-installed in the Docker image)

### 12.3. `user_reference/02_understanding_daaf.md`

- Replace "a complete set of versioned, validated Python scripts" with
  "a complete set of versioned, validated scripts (Python or R)"
- Update tool references (plotnine -> plotnine/ggplot2, marimo -> marimo/Quarto)
- Note R as a supported execution language

### 12.4. `user_reference/04_extending_daaf.md`

- **Critical:** Remove/update the statement "DAAF is a Python-based environment
  and does not include R" (line 481)
- Add "Customizing Your R Environment" section parallel to "Customizing Your
  Python Environment"
- Document `install.packages()` for adding R packages
- Document `renv` as R's virtual environment equivalent (if applicable)

### 12.5. `user_reference/07_faq_technical.md`

- Add R-specific FAQ entries:
  - "How do I add an R package?"
  - "Can I mix R and Python in one pipeline?"
  - "How do I switch between R and Python?"

### 12.6. `CONTRIBUTING.md`

- Update Python-specific contribution instructions to include R
- Note that R skills follow the same authoring template

### 12.7. `user_reference/06_faq_philosophy.md`

- No changes expected (philosophy is language-agnostic)

---

## 13. Wing 10: Translation Skills Refactor

### 13.1. Current State

- `r-python-translation`: Maps R -> Python (for R-background users reading Python code)
- `stata-python-translation`: Maps Stata -> Python (for Stata-background users reading Python code)

### 13.2. New Architecture

With R as a first-class language, translation becomes **bidirectional**:

| Execution Language | User Background | Translation Skill Needed |
|-------------------|----------------|------------------------|
| Python | R | `r-python-translation` (existing -- R user reads Python) |
| Python | Stata | `stata-python-translation` (existing -- Stata user reads Python) |
| R | Python | `python-r-translation` (**NEW** -- Python user reads R) |
| R | Stata | `stata-r-translation` (**NEW** -- Stata user reads R) |
| Python | Python | None |
| R | R | None |

### 13.3. New Skills Needed

#### `python-r-translation` (NEW)

For Python-background users working with R-generated code. Provides `# Python:`
annotations above R code.

**Content source:** Much of the mapping knowledge already exists in
`r-python-translation/references/` -- it just needs to be presented from the
reverse direction. The reference files contain bidirectional mappings.

**Structure:**
- SKILL.md (~350-400 lines)
- References: ~8-10 files (~3,000-4,000 lines)
- Many reference files can be shared or lightly adapted from `r-python-translation`

#### `stata-r-translation` (NEW)

For Stata-background users working with R-generated code. Completes the
translation matrix so all three language backgrounds (Python, R, Stata) have
annotation support regardless of execution language.

**Structure:**
- SKILL.md (~350-400 lines)
- References: ~8-10 files (~3,000-4,000 lines)
- Can leverage structural patterns from `stata-python-translation` and mapping
  knowledge from `r-python-translation`

### 13.4. Existing Skill Updates

The existing `r-python-translation` and `stata-python-translation` skills remain
unchanged -- they serve their current purpose for Python pipelines with R/Stata-
background users.

---

## 14. Wing 11: Notebook and Report Infrastructure

### 14.1. Quarto as R's Notebook Format

Quarto replaces Marimo for R pipelines. Key architectural decisions:

1. **File format:** `.qmd` (Quarto Markdown) instead of `.py` (Marimo Python)
2. **Execution model:** Quarto renders linearly (like R Markdown), vs. Marimo's
   reactive cells. This is a closer match to DAAF's sequential script philosophy.
3. **Data inspection:** Quarto can display interactive tables via `DT::datatable()`
   or static via `knitr::kable()`, replacing Marimo's `mo.ui.table()`.
4. **Assembly pattern:** The notebook-assembler converts stage scripts into Quarto
   chunks with YAML headers, vs. Marimo's Python cell functions.

### 14.2. Quarto Notebook Structure (R Pipeline)

```markdown
---
title: "Analysis Title"
date: "2026-01-24"
format:
  html:
    code-fold: show
    toc: true
execute:
  echo: true
  warning: false
---

## Data Acquisition

```{r}
#| label: fetch-data
# [Script content from stage5_fetch/01_fetch-ccd.R]
```

## Data Cleaning

```{r}
#| label: clean-data
# [Script content from stage6_clean/01_clean-ccd.R]
```

[... etc.]
```

### 14.3. Report Template Updates

The REPORT_TEMPLATE.md Technical Notes section currently hardcodes Python:

```
- Python 3.12
- Key packages: polars, plotnine, marimo
```

This becomes language-conditional:

```
[If Python:] Python 3.12 — Key packages: polars, plotnine, marimo
[If R:] R 4.x — Key packages: tidyverse, ggplot2, fixest, Quarto
```

---

## 15. Wing 12: Data Source Skills

### 15.1. Current State

There are ~14 existing data source skills (CCD, IPEDS, CRDC, Scorecard, etc.).
Each contains a Section 9 "Data Access" with Python/Polars fetch code.

### 15.2. Required Changes

Each data source skill's Data Access section needs R code examples alongside
Python. The pattern:

**Current:**
```python
import polars as pl
df = pl.read_parquet("path/to/data.parquet")
```

**Proposed addition:**
```r
library(arrow)
df <- read_parquet("path/to/data.parquet")
```

Since DAAF data source skills use Polars to read from mirror parquet files, the
R equivalent is straightforward: `arrow::read_parquet()` reads the same parquet
files.

### 15.3. education-data-query Skill

This skill manages downloading from configured mirror sources. It would need an
R-equivalent fetch function or the R path would use `arrow::read_parquet()` with
direct URLs.

### 15.4. Scope

This is a **lower priority** wing because:
- The parquet files are language-agnostic (R reads the same files Python writes)
- The `arrow` R package provides `read_parquet()` which is a direct equivalent
- The data source skills' primary value is **domain knowledge** (coded values,
  caveats, year coverage), which is language-agnostic
- Adding R examples is mechanical: ~2-5 lines per skill's Data Access section

---

## 16. Cross-Cutting Concerns

### 16.1. Testing Strategy

Since DAAF doesn't have a test suite (validation is inline), testing R support
means:

1. **Dockerfile build test:** Build the image and verify R + all packages install
2. **Execution test:** Run `run_with_capture.sh` on a sample `.R` script
3. **Hook test:** Verify `enforce-file-first.sh` blocks bare `Rscript` calls
4. **End-to-end test:** Run a simple Full Pipeline in R to verify the entire chain

### 16.2. Versioning

This is a major framework extension. Consider:
- Incrementing the DAAF version (e.g., v3.0)
- Creating a changelog entry
- Tagging the pre-R state for reference

### 16.3. Backward Compatibility

- All existing Python functionality is untouched
- Existing projects with Python scripts continue to work
- The default execution language remains Python
- No existing files are deleted or renamed

### 16.4. R Package Version Pinning (CONFIRMED)

**Decision:** Use P3M date-pinned snapshot URLs for the Dockerfile.

The Dockerfile uses `ARG P3M_SNAPSHOT_DATE=2026-04-15` to pin the CRAN mirror to
a specific date. All `install.packages()` calls pull from that snapshot, ensuring
reproducible builds without needing per-package version specifications.

**Critical alignment requirement:** When authoring each R library skill, the
skill's `library-version` metadata field must be verified against the actual
version installed from the pinned snapshot. The smoke-test sequence (Wing 13)
validates this alignment -- each smoke test begins by printing
`packageVersion("pkg")` and the skill SKILL.md records that version. If a skill
references API features from a newer version than what the snapshot provides,
the smoke test will catch the mismatch.

**Upgrade workflow:** When upgrading R packages:
1. Update `P3M_SNAPSHOT_DATE` in the Dockerfile
2. Rebuild the image
3. Re-run smoke tests for all R skills to detect API changes
4. Update `library-version` in affected SKILL.md files
5. Update any reference file content that references changed APIs

### 16.5. `renv` Integration

R's equivalent of Python virtual environments. For DAAF's Docker-based setup,
`renv` is not strictly necessary (the container IS the environment). However,
consider:
- Including `renv` in the image for users who want project-level isolation
- Documenting `renv` in `user_reference/04_extending_daaf.md` as an optional tool

### 16.6. Session Recovery

`STATE.md` currently tracks Python-specific session state. Add a field:

```markdown
**Execution Language:** R
```

This ensures session recovery correctly dispatches R skills and writes R scripts.

---

## 17. Dependency Graph and Execution Order

### 17.1. Dependency Relationships

```
Wing 1 (Dockerfile)
  |
  v
Wing 2 (Execution Infrastructure: run_with_capture.sh, enforce-file-first.sh)
  |
  +-- Wing 6 (CLAUDE.md: code style, preferences, file conventions)
  |     |
  |     v
  |   Wing 5 (Agent Definitions: research-executor, code-reviewer, etc.)
  |     |
  |     v
  |   Wing 7 (Reference Files: SCRIPT_EXECUTION_REFERENCE, VALIDATION_CHECKPOINTS, etc.)
  |
  +-- Wing 3 (R Library Skills: tidyverse, ggplot2, fixest, etc.)
  |     |
  |     v
  |   Wing 4 (Data-Scientist Routing: language-conditional decision trees)
  |     |
  |     v
  |   Wing 12 (Data Source Skills: add R code examples)
  |
  +-- Wing 10 (Translation Skills: python-r-translation)
  |
  +-- Wing 11 (Notebook Infrastructure: Quarto skill + notebook-assembler)
  |
  v
Wing 8 (Orchestrator + Mode Files: language routing, skill mappings)
  |
  v
Wing 9 (User Documentation: README, user_reference/)
```

### 17.2. Recommended Execution Waves

#### Wave 0: Foundation (blocking everything else)
- [ ] Wing 1: Dockerfile R installation
- [ ] Wing 2: `run_with_capture.sh` + `enforce-file-first.sh` + `settings.json`
- [ ] Wing 6: CLAUDE.md core changes (preferences, code style, file conventions)

#### Wave 1: Core Skills (can parallelize across skills)
- [ ] Wing 3, Priority 1: `tidyverse` skill
- [ ] Wing 3, Priority 1: `ggplot2` skill
- [ ] Wing 3, Priority 1: `fixest` skill
- [ ] Wing 3, Priority 1: `r-stats` skill
- [ ] Wing 3, Priority 1: `quarto` skill

#### Wave 2: Agent + Template Updates (depends on Wave 0)
- [ ] Wing 5: All 6 agent definitions
- [ ] Wing 7: All reference file updates (SCRIPT_EXECUTION_REFERENCE, etc.)
- [ ] Wing 11: Notebook-assembler Quarto support

#### Wave 3: Secondary Skills (can parallelize, depends on Wave 1 patterns)
- [ ] Wing 3, Priority 2: `plotly-r` skill
- [ ] Wing 3, Priority 2: `sf-terra` skill
- [ ] Wing 3, Priority 2: `plm` skill
- [ ] Wing 3, Priority 2: `tidymodels` skill
- [ ] Wing 3, Priority 2: `survey-r` skill

#### Wave 4: Routing and Integration (depends on Wave 1-3)
- [ ] Wing 4: Data-scientist skill routing updates
- [ ] Wing 8: Orchestrator and mode file updates
- [ ] Wing 10: New translation skills (python-r-translation, stata-r-translation)

#### Wave 5: Documentation and Polish (depends on all above)
- [ ] Wing 9: All user-facing documentation updates
- [ ] Wing 12: Data source skill R code examples
- [ ] Wing 3, Priority 3: `gt` skill

#### Wave 6: Smoke Tests and Validation
- [ ] Wing 13: Smoke tests for all R library skills (see Section 18)
- [ ] End-to-end test: Full Pipeline in R
- [ ] Cross-cutting review: consistency, completeness, integration checklist

### 17.3. Parallelism Opportunities

Within each wave, significant parallelism is possible:

- **Wave 1:** All 5 P1 skills can be authored in parallel (independent subagents)
- **Wave 2:** Agent updates and reference file updates can proceed in parallel
- **Wave 3:** All 5 P2 skills can be authored in parallel
- **Wave 4:** Orchestrator, mode files, and translation skills can be parallel

---

## 18. Wing 13: Smoke Tests for R Library Skills

### 18.1. Purpose and Philosophy

Every R library skill must be validated against the **actual installed library** in
the Docker container before the skill is considered complete. Smoke tests serve
three critical functions:

1. **Version alignment:** Verify that the `library-version` in SKILL.md metadata
   matches the version installed from the P3M date-pinned snapshot
2. **API accuracy:** Confirm that code patterns documented in the skill's reference
   files actually run correctly -- catching stale syntax, renamed functions,
   changed defaults, or deprecated arguments
3. **Documentation fidelity:** Ensure that the skill's Quick Reference table and
   code examples produce the outputs described in the documentation

### 18.2. Smoke Test Execution Model

Smoke tests are **real R scripts** executed via `run_with_capture.sh`, following
DAAF's file-first execution protocol. They live in a dedicated directory:

```
scripts/smoke_tests/
  smoke_tidyverse.R
  smoke_ggplot2.R
  smoke_fixest.R
  smoke_r_stats.R
  smoke_quarto.R
  smoke_plotly_r.R
  smoke_sf_terra.R
  smoke_plm.R
  smoke_tidymodels.R
  smoke_survey_r.R
  smoke_gt.R
```

Each smoke test is executed via:
```bash
bash /daaf/scripts/run_with_capture.sh /daaf/scripts/smoke_tests/smoke_{skill}.R
```

The execution log appended to each script serves as the permanent verification
record.

### 18.3. Smoke Test Structure (Universal Template)

Every smoke test follows this structure:

```r
# --- Config ---
# INTENT: Smoke test for {skill-name} skill — verify installed version and
#         core API patterns documented in skill reference files

# --- Version Check ---
cat("=== VERSION CHECK ===\n")
cat("Package: {package}\n")
cat("Installed version:", as.character(packageVersion("{package}")), "\n")
cat("Skill metadata version: {version-from-SKILL.md}\n")
stopifnot(
  "Version mismatch between installed package and skill metadata" =
    packageVersion("{package}") >= "{minimum-version}"
)
cat("PASS: Version aligned\n\n")

# --- Core API Tests ---
cat("=== CORE API TESTS ===\n")

# Test 1: {Description from Quick Reference or reference file}
# INTENT: Verify {specific pattern} from references/{file}.md
{code from skill documentation}
stopifnot({validation condition})
cat("PASS: {test description}\n")

# Test 2: ...
# [repeat for each major API pattern documented in the skill]

# --- Integration Tests ---
cat("=== INTEGRATION TESTS ===\n")

# Test: Parquet round-trip (all data skills must read/write parquet)
# INTENT: Verify parquet I/O works as documented
{write and read back a small test dataframe}
stopifnot({data matches})
cat("PASS: Parquet round-trip\n")

# --- Summary ---
cat("\n=== SMOKE TEST SUMMARY ===\n")
cat("Skill: {skill-name}\n")
cat("Tests run: {N}\n")
cat("All tests PASSED\n")
```

### 18.4. Per-Skill Smoke Test Specifications

#### `smoke_tidyverse.R`
Tests against: `tidyverse` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | dplyr, tidyr, readr, purrr, stringr versions | SKILL.md metadata |
| 2 | `filter()` + `select()` + `mutate()` | Core verb pipeline | quickstart.md |
| 3 | `group_by()` + `summarize()` | Aggregation pattern | quickstart.md |
| 4 | `pivot_longer()` + `pivot_wider()` | Reshaping | reshaping.md |
| 5 | `left_join()` + `anti_join()` | Join operations | joins.md |
| 6 | `arrow::read_parquet()` + `arrow::write_parquet()` | Parquet I/O | io.md |
| 7 | Native pipe `\|>` works | Pipe operator | quickstart.md |
| 8 | `readr::read_csv()` on inline data | CSV parsing | io.md |
| 9 | `stringr::str_detect()` + `str_replace()` | String ops | strings-dates.md |
| 10 | `lubridate::ymd()` + date arithmetic | Date handling | strings-dates.md |
| 11 | `data.table` basic operations | data.table as performance alternative | data-table.md |

#### `smoke_ggplot2.R`
Tests against: `ggplot2` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | ggplot2, scales, patchwork versions | SKILL.md metadata |
| 2 | `ggplot() + geom_point() + geom_smooth()` | Basic scatter + trend | quickstart.md |
| 3 | `geom_bar()` + `geom_col()` | Bar charts | geoms.md |
| 4 | `geom_histogram()` + `geom_density()` | Distribution plots | geoms.md |
| 5 | `facet_wrap()` + `facet_grid()` | Faceting | facets.md |
| 6 | `scale_*_continuous()` + `scale_color_viridis_d()` | Scale customization | scales.md |
| 7 | `theme_minimal()` + custom `theme()` elements | Theming | themes.md |
| 8 | `ggsave()` to PNG | File export | quickstart.md |
| 9 | `patchwork` composition (`p1 + p2`) | Multi-panel | extensions.md |
| 10 | `ggrepel::geom_text_repel()` | Label extension | extensions.md |

#### `smoke_fixest.R`
Tests against: `fixest` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | fixest version | SKILL.md metadata |
| 2 | `feols(y ~ x1 + x2, data)` | Basic OLS | quickstart.md |
| 3 | `feols(y ~ x \| fe1 + fe2)` | Multi-way FE | fixed-effects.md |
| 4 | `feols(y ~ x, cluster = ~id)` | Clustered SEs | standard-errors.md |
| 5 | `feols(y ~ 1 \| id \| x ~ z)` | IV estimation | iv.md |
| 6 | `fepois(y ~ x \| fe)` | Poisson regression | models.md |
| 7 | `etable()` output | Regression tables | reporting.md |
| 8 | `coefplot()` renders | Coefficient plot | reporting.md |
| 9 | `sunab()` for staggered DiD | DiD estimator | did.md |
| 10 | Multiple estimation `feols(y ~ csw(x1, x2, x3))` | Stepwise | quickstart.md |

#### `smoke_r_stats.R`
Tests against: `r-stats` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | sandwich, lmtest, car versions | SKILL.md metadata |
| 2 | `lm(y ~ x1 + x2)` + `summary()` | Basic OLS | quickstart.md |
| 3 | `glm(y ~ x, family = binomial)` | Logistic regression | glm.md |
| 4 | `sandwich::vcovHC()` + `lmtest::coeftest()` | Robust SEs | robust-se.md |
| 5 | `car::linearHypothesis()` | Joint hypothesis test | diagnostics.md |
| 6 | `confint()` | Confidence intervals | quickstart.md |
| 7 | `predict()` with `newdata` | Prediction | quickstart.md |
| 8 | `broom::tidy()` + `broom::glance()` | Tidy model output | reporting.md |
| 9 | `t.test()` + `chisq.test()` | Classic tests | tests.md |
| 10 | `MASS::glm.nb()` | Negative binomial | glm.md |

#### `smoke_quarto.R`
Tests against: `quarto` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | `quarto --version` (system call) | Quarto CLI installed | SKILL.md metadata |
| 2 | Write minimal `.qmd` with R chunk | File creation | quickstart.md |
| 3 | `quarto render` to HTML | Render pipeline | rendering.md |
| 4 | YAML frontmatter parsed correctly | Format options | format.md |
| 5 | Code chunk with `#\| echo: true` | Chunk options | chunks.md |
| 6 | Inline R expression `` `r expr` `` | Inline code | chunks.md |
| 7 | Figure output from ggplot2 chunk | Plot embedding | figures.md |
| 8 | Table output from gt/kable chunk | Table embedding | tables.md |

#### `smoke_plotly_r.R`
Tests against: `plotly-r` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | plotly version | SKILL.md metadata |
| 2 | `plot_ly(x, y, type = "scatter")` | Basic scatter | quickstart.md |
| 3 | `plot_ly(type = "bar")` | Bar chart | chart-types.md |
| 4 | `ggplotly()` conversion | ggplot2 bridge | ggplotly.md |
| 5 | `layout()` customization | Axes, titles | layouts.md |
| 6 | `htmlwidgets::saveWidget()` | HTML export | export.md |
| 7 | `subplot()` composition | Multi-panel | subplots.md |

#### `smoke_sf_terra.R`
Tests against: `sf-terra` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | sf, terra, spdep versions | SKILL.md metadata |
| 2 | `st_read()` / `st_write()` | Vector I/O | quickstart.md |
| 3 | `st_transform()` CRS reprojection | CRS handling | crs.md |
| 4 | `st_join()` spatial join | Spatial operations | spatial-ops.md |
| 5 | `st_buffer()` + `st_intersection()` | Geometry ops | spatial-ops.md |
| 6 | `terra::rast()` + basic operations | Raster creation | raster.md |
| 7 | `ggplot() + geom_sf()` | Static map | mapping.md |
| 8 | `spdep::poly2nb()` + `moran.test()` | Spatial autocorrelation | spatial-stats.md |
| 9 | `leaflet()` + `addPolygons()` | Interactive map | interactive.md |
| 10 | `classInt::classIntervals()` | Classification | mapping.md |

#### `smoke_plm.R`
Tests against: `plm` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | plm, estimatr versions | SKILL.md metadata |
| 2 | `plm(y ~ x, model = "within")` | Fixed effects | quickstart.md |
| 3 | `plm(y ~ x, model = "random")` | Random effects | models.md |
| 4 | `phtest()` Hausman test | FE vs RE | diagnostics.md |
| 5 | `plm(y ~ x \| z, model = "within")` | Panel IV | iv.md |
| 6 | `pgmm()` | Dynamic GMM | gmm.md |
| 7 | `estimatr::lm_robust()` | Robust SEs | robust.md |

#### `smoke_tidymodels.R`
Tests against: `tidymodels` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | tidymodels, ranger, glmnet versions | SKILL.md metadata |
| 2 | `recipe()` + `step_normalize()` | Preprocessing | recipes.md |
| 3 | `rand_forest() \|> set_engine("ranger")` | Model spec | models.md |
| 4 | `workflow()` + `fit()` | Workflow fitting | workflows.md |
| 5 | `vfold_cv()` + `tune_grid()` | Cross-validation | tuning.md |
| 6 | `collect_metrics()` | Results extraction | tuning.md |
| 7 | `glmnet` Lasso via parsnip | Regularization | models.md |
| 8 | `predict()` on new data | Prediction | quickstart.md |
| 9 | `uwot::umap()` | UMAP embedding | unsupervised.md |

#### `smoke_survey_r.R`
Tests against: `survey-r` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | survey version | SKILL.md metadata |
| 2 | `svydesign(ids, strata, weights)` | Design object | quickstart.md |
| 3 | `svymean()` + `svytotal()` | Point estimates | estimation.md |
| 4 | `svyglm(y ~ x)` | Survey regression | regression.md |
| 5 | `svyby()` domain estimation | Subgroup analysis | domains.md |
| 6 | `as.svrepdesign()` + replicate weights | BRR/Jackknife | replication.md |

#### `smoke_gt.R`
Tests against: `gt` skill reference files

| # | Test | What It Validates | Source Reference |
|---|------|-------------------|-----------------|
| 1 | Version check | gt, kableExtra versions | SKILL.md metadata |
| 2 | `gt()` basic table | Table creation | quickstart.md |
| 3 | `fmt_number()` + `fmt_percent()` | Formatting | formatting.md |
| 4 | `tab_header()` + `tab_spanner()` | Structure | structure.md |
| 5 | `gtsave()` to HTML/PNG | Export | export.md |
| 6 | `modelsummary()` regression table | Model tables | model-tables.md |

### 18.5. Smoke Test Execution Protocol

#### When to Run

Smoke tests are run at **two points**:

1. **During skill authoring (Wave 1 + Wave 3):** After each skill's SKILL.md and
   reference files are written, the corresponding smoke test is authored and
   executed. Any failures trigger revision of the skill documentation.

2. **Wave 6 (Validation):** All smoke tests are re-run as a batch to verify
   cross-skill consistency after all integration work is complete.

#### Authoring Workflow (Per Skill)

```
1. Write SKILL.md + reference files
2. Author smoke_test_{skill}.R based on documented patterns
3. Execute via run_with_capture.sh
4. If FAIL:
   a. Diagnose: Is it a documentation error or a library issue?
   b. If documentation error: fix the skill reference file, re-run
   c. If library version issue: update SKILL.md metadata, adjust code
   d. Re-run smoke test until PASS
5. Verify library-version in SKILL.md matches packageVersion() output
6. Skill is now verified ✓
```

#### Failure Handling

| Failure Type | Root Cause | Resolution |
|-------------|------------|------------|
| Version mismatch | SKILL.md claims version X, container has version Y | Update SKILL.md `library-version` to match container |
| Function not found | Documented function renamed or removed in installed version | Update reference file to use correct function name |
| Argument deprecated | Documented argument no longer accepted | Update reference file code examples |
| Different default | Function behavior changed (e.g., SE type) | Update gotchas.md and affected reference files |
| Output format changed | Return value structure differs from documented | Update reference file descriptions and examples |

### 18.6. Batch Execution Script

A convenience script for running all smoke tests:

```bash
#!/usr/bin/env bash
# scripts/smoke_tests/run_all_smoke_tests.sh
# Executes all R skill smoke tests and reports results

SMOKE_DIR="$(dirname "$0")"
BASE_DIR="$(cd "$SMOKE_DIR/../.." && pwd)"
CAPTURE="$BASE_DIR/scripts/run_with_capture.sh"
PASSED=0
FAILED=0
FAILURES=""

for test_script in "$SMOKE_DIR"/smoke_*.R; do
    skill_name=$(basename "$test_script" .R | sed 's/smoke_//')
    echo "--- Running smoke test: $skill_name ---"
    if bash "$CAPTURE" "$test_script"; then
        echo "PASS: $skill_name"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL: $skill_name"
        FAILED=$((FAILED + 1))
        FAILURES="$FAILURES $skill_name"
    fi
    echo ""
done

echo "================================="
echo "SMOKE TEST RESULTS"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
if [ $FAILED -gt 0 ]; then
    echo "Failures:$FAILURES"
    exit 1
fi
echo "All smoke tests passed."
```

### 18.7. Scope Summary

| Metric | Count |
|--------|-------|
| Smoke test scripts | 11 |
| Total individual test cases | ~95-100 |
| Estimated lines per script | 100-180 |
| Estimated total lines | ~1,200-1,800 |

---

## 19. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| P3M doesn't provide Bookworm binaries for all packages | Medium | High (build time explodes) | Test build early; fall back to source compilation for specific packages |
| R skills diverge in quality from Python skills | Medium | Medium | Use Python skills as structural templates; review pass after authoring |
| Quarto integration is more complex than Marimo | Medium | Medium | Prototype the notebook-assembler changes early |
| Image size exceeds practical limits | Low | Medium | Monitor during test build; consider optional R layer |
| Mixed-language pipeline requests | High | Low | Out of scope for v1; architecture is forward-compatible (per Section 2.5) |
| Agent context exhaustion from dual-language skill loading | Medium | Medium | Language-conditional loading (never load both Python and R skills) |
| `enforce-file-first.sh` regex complexity | Low | High | Test hook with both `Rscript` and `R --vanilla` invocations |
| R package API drift from skill content | Medium | Medium | Skills note version; R ecosystem evolves faster in some areas |
| data-scientist reference files become unwieldy with dual code blocks | Medium | Medium | Consider separate "Python Examples" and "R Examples" subsections rather than interleaved blocks |
| Smoke tests reveal significant API drift from skill content | Medium | High | Smoke tests run during authoring (not after); each skill is verified before moving to the next. Budget revision cycles per skill. |
| P3M snapshot date packages have incompatible transitive dependencies | Low | High | Test build with full package set early; resolve conflicts before writing skills against those versions |

---

## 20. Validation Strategy

### 20.1. Per-Wing Validation

| Wing | Validation Method |
|------|-------------------|
| 1 (Dockerfile) | `docker compose up -d --build` succeeds; `Rscript -e 'library(sf); library(fixest); library(ggplot2)'` runs in container |
| 2 (Execution) | `run_with_capture.sh test_script.R` produces correct output with appended log |
| 2 (Hook) | `enforce-file-first.sh` blocks `Rscript script.R` but allows `bash run_with_capture.sh script.R` |
| 3 (R Skills) | Each skill has valid frontmatter, SKILL.md structure matches template, all referenced files exist |
| 4 (Routing) | data-scientist SKILL.md parses correctly; routing table is complete |
| 5 (Agents) | Agent definitions are valid; skill-loading tables are consistent |
| 6 (CLAUDE.md) | No broken cross-references; all file patterns include R extensions |
| 7 (References) | R code templates compile; validation checkpoint R code runs |
| 8 (Orchestrator) | Mode files reference correct R skills; invocation templates are complete |
| 9 (Docs) | No remaining "Python-only" language in user docs |
| 10 (Translation) | python-r-translation produces correct annotations |
| 11 (Notebook) | Quarto notebook renders from assembled R scripts |
| 12 (Data Sources) | R code examples in data source skills execute correctly |
| 13 (Smoke Tests) | All 11 smoke test scripts pass; version alignment confirmed for all skills |

### 20.2. Integration Validation

After all wings complete:
1. **FRAMEWORK_INTEGRATION_CHECKLIST.md:** Execute all applicable sections for each new skill
2. **Consistency review:** 3 search-agent subagents (per Framework Development protocol)
3. **End-to-end test:** Run a complete Full Pipeline in R mode through all stages

---

## Appendix A: Complete File Inventory

### New Files to Create

| # | Path | Type | Est. Lines |
|---|------|------|-----------|
| 1 | `.claude/skills/tidyverse/SKILL.md` | R skill | 300-350 |
| 2 | `.claude/skills/tidyverse/references/*.md` (10-12 files) | Refs | 3,500-4,500 |
| 3 | `.claude/skills/ggplot2/SKILL.md` | R skill | 200-250 |
| 4 | `.claude/skills/ggplot2/references/*.md` (6-8 files) | Refs | 1,500-2,500 |
| 5 | `.claude/skills/fixest/SKILL.md` | R skill | 250-300 |
| 6 | `.claude/skills/fixest/references/*.md` (6-8 files) | Refs | 2,000-2,500 |
| 7 | `.claude/skills/r-stats/SKILL.md` | R skill | 280-320 |
| 8 | `.claude/skills/r-stats/references/*.md` (6-8 files) | Refs | 3,000-4,000 |
| 9 | `.claude/skills/quarto/SKILL.md` | R skill | 250-300 |
| 10 | `.claude/skills/quarto/references/*.md` (6-8 files) | Refs | 2,000-3,000 |
| 11 | `.claude/skills/plotly-r/SKILL.md` | R skill | 200-250 |
| 12 | `.claude/skills/plotly-r/references/*.md` (5-6 files) | Refs | 1,500-2,000 |
| 13 | `.claude/skills/sf-terra/SKILL.md` | R skill | 280-320 |
| 14 | `.claude/skills/sf-terra/references/*.md` (8-10 files) | Refs | 3,000-4,000 |
| 15 | `.claude/skills/plm/SKILL.md` | R skill | 250-280 |
| 16 | `.claude/skills/plm/references/*.md` (5-7 files) | Refs | 2,000-2,500 |
| 17 | `.claude/skills/tidymodels/SKILL.md` | R skill | 300-350 |
| 18 | `.claude/skills/tidymodels/references/*.md` (10-14 files) | Refs | 3,000-4,000 |
| 19 | `.claude/skills/survey-r/SKILL.md` | R skill | 250-280 |
| 20 | `.claude/skills/survey-r/references/*.md` (3-5 files) | Refs | 1,500-2,000 |
| 21 | `.claude/skills/gt/SKILL.md` | R skill | 180-220 |
| 22 | `.claude/skills/gt/references/*.md` (3-4 files) | Refs | 1,000-1,500 |
| 23 | `.claude/skills/python-r-translation/SKILL.md` | Translation | 350-400 |
| 24 | `.claude/skills/python-r-translation/references/*.md` (8-10 files) | Refs | 3,000-4,000 |
| 25 | `.claude/skills/stata-r-translation/SKILL.md` | Translation | 350-400 |
| 26 | `.claude/skills/stata-r-translation/references/*.md` (8-10 files) | Refs | 3,000-4,000 |
| 27 | `scripts/smoke_tests/` (11 R scripts, 1 per skill) | Smoke tests | ~1,200-1,800 |

### Existing Files to Modify

| # | Path | Magnitude | Primary Change |
|---|------|-----------|----------------|
| 1 | `Dockerfile` | Major | Add R, system deps, R packages, Quarto |
| 2 | `scripts/run_with_capture.sh` | Small | Language detection, dual dispatch |
| 3 | `.claude/hooks/enforce-file-first.sh` | Moderate | Add Rscript detection |
| 4 | `.claude/settings.json` | Small | Add `Bash(Rscript *)` to allow list |
| 5 | `CLAUDE.md` | Major | Preferences, code style, file conventions, execution philosophy |
| 6 | `.claude/agents/research-executor.md` | Major | R skill loading, .R scripts |
| 7 | `.claude/agents/code-reviewer.md` | Major | R QA templates |
| 8 | `.claude/agents/debugger.md` | Moderate | R error patterns |
| 9 | `.claude/agents/data-ingest.md` | Moderate | R profiling scripts |
| 10 | `.claude/agents/notebook-assembler.md` | Major | Quarto support |
| 11 | `.claude/agents/README.md` | Minor | R capability notes |
| 12 | `.claude/skills/data-scientist/SKILL.md` | Major | Language-conditional routing |
| 13 | `.claude/skills/data-scientist/references/*.md` (~10 files) | Moderate | Add R code blocks |
| 14 | `.claude/skills/daaf-orchestrator/SKILL.md` | Moderate | Language detection, propagation |
| 15 | `.claude/skills/daaf-orchestrator/references/full-pipeline-mode.md` | Major | R skill mappings, invocation templates |
| 16 | `.claude/skills/daaf-orchestrator/references/data-onboarding-mode.md` | Moderate | R profiling, API scripts |
| 17 | `.claude/skills/daaf-orchestrator/references/ad-hoc-collaboration-mode.md` | Minor | Dispatch table R skills |
| 18 | `.claude/skills/daaf-orchestrator/references/revision-and-extension-mode.md` | Minor | .R extension handling |
| 19 | `.claude/skills/daaf-orchestrator/references/reproducibility-verification-mode.md` | Moderate | Quarto decompilation |
| 20 | `agent_reference/SCRIPT_EXECUTION_REFERENCE.md` | Major | R templates (~500-700 lines added) |
| 21 | `agent_reference/VALIDATION_CHECKPOINTS.md` | Major | R checkpoint code (~400-600 lines added) |
| 22 | `agent_reference/QA_CHECKPOINTS.md` | Major | R QA templates (~300-500 lines added) |
| 23 | `agent_reference/ERROR_RECOVERY.md` | Moderate | R error types (~150-250 lines added) |
| 24 | `agent_reference/BOUNDARIES.md` | Moderate | Generalize Python -> dual-language |
| 25 | `agent_reference/PLAN_TEMPLATE.md` | Moderate | R artifact paths, code examples |
| 26 | `agent_reference/PLAN_TASKS_TEMPLATE.md` | Moderate | R skill refs, action blocks |
| 27 | `agent_reference/REPORT_TEMPLATE.md` | Minor | Language-conditional Technical Notes |
| 28 | `agent_reference/REPRODUCTION_REPORT_TEMPLATE.md` | Minor | R version field |
| 29 | `agent_reference/INLINE_AUDIT_TRAIL.md` | Minor | Generalize "Python scripts" -> "scripts" |
| 30 | `agent_reference/DATA_SOURCE_SKILL_TEMPLATE.md` | Moderate | R code examples |
| 31 | `agent_reference/CITATION_REFERENCE.md` | Moderate | R package citations |
| 32 | `agent_reference/STATE_TEMPLATE.md` | Minor | Execution language field |
| 33 | `agent_reference/WORKFLOW_PHASE1_DISCOVERY.md` | Minor | Script path conventions |
| 34 | `agent_reference/WORKFLOW_PHASE2_PLANNING.md` | Minor | Script path conventions |
| 35 | `agent_reference/WORKFLOW_PHASE3_ACQUISITION.md` | Moderate | R fetch templates, CP code |
| 36 | `agent_reference/WORKFLOW_PHASE4_ANALYSIS.md` | Major | R analysis templates, Stage 9 Quarto |
| 37 | `agent_reference/WORKFLOW_PHASE5_SYNTHESIS.md` | Moderate | Verification code, notebook refs |
| 38 | `.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_PROFILING.md` | Moderate | R profiling templates |
| 39 | `.claude/skills/daaf-orchestrator/references/WORKFLOW_PHASE_DO_AUTHORING.md` | Minor | Language references |
| 40-53 | `.claude/skills/{each-data-source}/SKILL.md` (~14 files) | Minor | R code examples in Data Access |
| 54 | `README.md` | Minor | R support mention |
| 55 | `CONTRIBUTING.md` | Minor | R contribution guidance |
| 56 | `user_reference/01_installation_and_quickstart.md` | Minor | R availability |
| 57 | `user_reference/02_understanding_daaf.md` | Minor | R support mention |
| 58 | `user_reference/04_extending_daaf.md` | Major | R environment customization |
| 59 | `user_reference/07_faq_technical.md` | Minor | R FAQ entries |
| 60 | `.claude/hooks/first-run-transparency.txt` | Minor | R mention |

---

## Appendix B: R Package Manifest

Complete list of R packages to install, organized by category:

### Core Data Manipulation and I/O
| Package | Purpose | Python Equivalent |
|---------|---------|-------------------|
| `data.table` | High-performance data manipulation | polars (performance) |
| `dplyr` | Verb-based data manipulation | polars (API) |
| `tidyr` | Data reshaping (pivot, unnest) | polars (melt/pivot) |
| `tibble` | Modern data frames | polars DataFrame |
| `readr` | Fast CSV/delimited file reading | polars scan_csv |
| `purrr` | Functional programming tools | Python map/comprehensions |
| `stringr` | String manipulation | polars str namespace |
| `forcats` | Factor handling | polars categorical |
| `lubridate` | Date/time manipulation | polars dt namespace |
| `glue` | String interpolation | f-strings |
| `rlang` | Tidy evaluation infrastructure | (internal) |
| `arrow` | Apache Arrow, parquet I/O | pyarrow |
| `readxl` | Excel file reading | openpyxl |
| `writexl` | Excel file writing | openpyxl |
| `haven` | SPSS/Stata/SAS file reading | (no Python equiv in stack) |
| `jsonlite` | JSON parsing | json (stdlib) |
| `yaml` | YAML parsing | pyyaml |

### Statistics and Econometrics
| Package | Purpose | Python Equivalent |
|---------|---------|-------------------|
| `fixest` | Fixed effects, DiD, multi-way clustering | pyfixest |
| `sandwich` | Robust/clustered standard errors | statsmodels HC/HAC |
| `lmtest` | Hypothesis tests for linear models | statsmodels diagnostics |
| `car` | Regression diagnostics, ANOVA | statsmodels |
| `plm` | Panel data models (FE, RE, IV, GMM) | linearmodels |
| `estimatr` | Robust standard errors for lm/iv | linearmodels |
| `marginaleffects` | Marginal effects, contrasts, predictions | marginaleffects |
| `rdrobust` | Regression discontinuity | rdrobust |
| `fwildclusterboot` | Wild cluster bootstrap | wildboottest |
| `survey` | Complex survey statistics | svy |
| `rugarch` | GARCH models | arch |
| `broom` | Tidy model output | (built into pyfixest/statsmodels) |
| `modelsummary` | Regression tables | great-tables + etable |

### Geospatial
| Package | Purpose | Python Equivalent |
|---------|---------|-------------------|
| `sf` | Simple Features (vector data) | geopandas |
| `terra` | Raster and vector data | rasterio |
| `stars` | Spatiotemporal arrays | xarray |
| `spdep` | Spatial dependence, weights, autocorrelation | libpysal + esda |
| `spatialreg` | Spatial regression models | spreg |
| `classInt` | Classification intervals | mapclassify |
| `exactextractr` | Zonal statistics | rasterstats |
| `leaflet` | Interactive web maps | folium |
| `maptiles` | Basemap tiles | contextily |
| `tidygeocoder` | Geocoding | geopy |
| `osmdata` | OpenStreetMap queries | osmnx |

### Visualization
| Package | Purpose | Python Equivalent |
|---------|---------|-------------------|
| `ggplot2` | Grammar of graphics (static) | plotnine |
| `scales` | Scale functions for ggplot2 | (built into plotnine) |
| `ggridges` | Ridge/joy plots | (seaborn) |
| `ggrepel` | Non-overlapping text labels | (matplotlib adjustText) |
| `patchwork` | Multi-panel plot composition | (matplotlib subplots) |
| `ggdist` | Distribution visualizations | (seaborn) |
| `plotly` | Interactive charts | plotly |
| `gt` | Publication-quality tables | great-tables |
| `knitr` | Dynamic report generation | (marimo) |
| `kableExtra` | Enhanced table formatting | (great-tables) |
| `viridis` | Color scales | (built into matplotlib/plotnine) |

### ML and Interpretation
| Package | Purpose | Python Equivalent |
|---------|---------|-------------------|
| `tidymodels` | ML meta-framework | scikit-learn |
| `ranger` | Fast random forests | scikit-learn RandomForest |
| `glmnet` | Regularized regression (Lasso/Ridge) | scikit-learn Lasso/Ridge |
| `xgboost` | Gradient boosting | (not in current stack) |
| `lightgbm` | Gradient boosting | lightgbm |
| `iml` | Model interpretation | shap |
| `uwot` | UMAP dimensionality reduction | umap-learn |
| `fairmodels` | Fairness metrics | fairlearn |

### Notebook and Reporting
| Package | Purpose | Python Equivalent |
|---------|---------|-------------------|
| Quarto CLI | Notebook rendering | marimo |
| `rmarkdown` | R Markdown (legacy, Quarto dependency) | (N/A) |

---

## Appendix C: Skill Structure Template (R)

Template for new R library skills, following the pattern established by existing
Python library skills:

```markdown
---
name: {skill-name}
description: |
  {One-line description}. {Key capabilities}. Use when {trigger conditions}.
  {Routing guidance for alternatives}.
autoload: never
metadata:
  audience: code-producing agents
  domain: r-library
  library-version: "{version}"
  skill-last-updated: "2026-04-17"
  tags: ["{tag1}", "{tag2}"]
---

# {Library Name}

{Identity paragraph: what this skill covers, when to use it, when to use
something else instead. Include Python counterpart reference.}

## What is {Library}?

- {Key feature 1}
- {Key feature 2}
- {Key feature 3}
- {Key feature 4}

## Version Notes

**Current version in DAAF:** {version}
{Any breaking changes from prior versions}

## How to Use This Skill

| File | Purpose | When to Read |
|------|---------|-------------|
| `references/quickstart.md` | Essential patterns | Always read first |
| `references/{topic1}.md` | {Description} | {Trigger} |
| ... | ... | ... |
| `references/gotchas.md` | Common pitfalls | Before finalizing code |

## Related Skills

| Skill | Relationship | When to Use Instead |
|-------|-------------|-------------------|
| `{python-counterpart}` | Python equivalent | When execution language is Python |
| `data-scientist` | Methodology hub | For "which method?" decisions |
| ... | ... | ... |

## Quick Decision Trees

### {Task Category 1}
- {Condition} -> Read `references/{file}.md`
- {Condition} -> Read `references/{file}.md`

## File-First Execution

All R code must follow DAAF's file-first execution model:
1. **WRITE** complete script to `scripts/{stage}/` as `.R` file
2. **EXECUTE** via `bash {BASE_DIR}/scripts/run_with_capture.sh {script}.R`
3. **CAPTURE** is automatic -- stdout/stderr appended to script

## Quick Reference

### Essential Setup
```r
library({package})
library(arrow)  # For parquet I/O
```

### Core Operations

| Task | Code |
|------|------|
| {Operation 1} | `{code}` |
| {Operation 2} | `{code}` |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| {Topic 1} | `references/{file}.md` |
| ... | ... |

## Citation

{Package} citation:
> {Citation text}
```

---

## Appendix D: Resolved Design Decisions

Decisions confirmed by the user on 2026-04-18 and incorporated into this plan:

| # | Decision | Resolution | Sections Affected |
|---|----------|------------|-------------------|
| 1 | **R package version pinning** | Use P3M date-pinned snapshot URLs (`ARG P3M_SNAPSHOT_DATE`). Verify installed versions match skill metadata during smoke tests. | 4.2.2, 16.4, 18.2 |
| 2 | **Standalone `data-table` skill** | Not needed for v1. data.table covered as a performance alternative within the `tidyverse` skill. | 6.2, 6.4, Appendix A |
| 3 | **`stata-r-translation` skill** | Include in v1 (not deferred). Completes the full translation matrix for all three language backgrounds. | 13.3, Wave 4 |
| 4 | **Image size (~5-7 GB)** | Accepted as necessary for a comprehensive dual-language environment. | 4.2.4 |
| 5 | **Mixed-language pipelines** | Out of scope for v1, but architecture must be forward-compatible. No infrastructure-level guards that would prevent future mixed-language support. | 2.5, 5.1.1 |
| 6 | **Smoke tests for R skills** | Every R library skill requires a smoke test that validates version alignment and API accuracy against actual library execution. Tests run during authoring and again in Wave 6. | 18 (entire section) |

---

*This plan was generated during a DAAF Framework Development session on 2026-04-17,
revised 2026-04-18 with user-confirmed decisions. It represents a comprehensive scope
assessment and implementation roadmap for adding first-class R language support.
No framework files were modified during planning.*
