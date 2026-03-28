# Stata-to-Python Translation Skill: Research Findings

**Research date:** 2026-03-28
**Purpose:** Inform creation of a `stata-python-translation` skill for the DAAF framework
**Scope:** Comprehensive catalog of resources for Stata-background social science researchers auditing/understanding Python code

---

## Table of Contents

- [1. General Stata-to-Python Transition Guides](#1-general-stata-to-python-transition-guides)
- [2. Package Mapping Resources](#2-package-mapping-resources)
  - [2a. Data Manipulation](#2a-data-manipulation-stata-data-commands--polarspandas)
  - [2b. Regression and Econometrics](#2b-regression-and-econometrics)
  - [2c. Visualization](#2c-visualization)
  - [2d. Survey Analysis](#2d-survey-analysis)
  - [2e. Causal Inference](#2e-causal-inference)
  - [2f. Post-Estimation and Tables](#2f-post-estimation-and-tables)
- [3. Academic and Educational Resources](#3-academic-and-educational-resources)
- [4. Stata Official Documentation Structure](#4-stata-official-documentation-structure)
- [5. Community Resources](#5-community-resources)
- [6. Key Paradigm Differences](#6-key-paradigm-differences-stata-vs-python)
- [7. Skill Architecture Recommendations](#7-skill-architecture-recommendations)

---

## 1. General Stata-to-Python Transition Guides

### 1.1 Daniel M. Sullivan: Stata to Python Equivalents

- **Title:** Stata to Python Equivalents
- **Author(s):** Daniel M. Sullivan
- **URL:** https://www.danielmsullivan.com/pages/tutorial_stata_to_python.html
- **Type:** Guide / Reference
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** The single most comprehensive Stata-to-Python command mapping available
  online. Covers 13 sections: Input/Output, Sample Selection, Data Info and Summary
  Statistics, Variable Manipulation, Bysort, Panel Data, Merging and Joining, Reshape,
  Econometrics, Plotting, and Other Differences. Maps ~80+ individual Stata commands to
  pandas/Python equivalents with code examples. Includes critical conceptual notes on
  missing value behavior (NaN vs. Stata's `.`), floating point equality, and
  composability differences.
- **Relevance to DAAF:** High -- directly maps the Stata commands social scientists use
  daily to pandas equivalents. The econometrics section references `econtools` for
  regression (now somewhat dated; pyfixest is the modern equivalent) and `statsmodels`
  for general regression.
- **Currency concern:** Moderate -- references `econtools` for regression rather than
  modern `pyfixest`; pandas API stable but some methods (e.g., `df.append()`) deprecated
  in recent pandas versions. Core mappings remain accurate for data manipulation.

### 1.2 Coding for Economists: "Coming from Stata"

- **Title:** Coming from Stata (Chapter of "Coding for Economists")
- **Author(s):** Arthur Turrell
- **URL:** https://aeturrell.github.io/coding-for-economists/coming-from-stata.html
- **Type:** Guide / Online textbook chapter
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Dedicated chapter for Stata users transitioning to Python within a
  broader economics-focused Python guide. Maps 40+ Stata commands to Python equivalents
  using pandas, statsmodels, pyfixest, and binsreg. Includes a supplementary regression
  reference table covering fixed effects, categorical variables, interaction terms,
  robust/clustered standard errors, and instrumental variables. Part of a comprehensive
  online resource that also covers data wrangling, econometrics, visualization
  (with plotnine chapter), and workflow practices.
- **Relevance to DAAF:** High -- uses the same Python stack as DAAF (pyfixest,
  statsmodels, binsreg, plotnine). The broader "Coding for Economists" book is an
  excellent companion resource covering the full Python data analysis workflow.
- **Currency concern:** Low -- actively maintained; uses modern package recommendations.

### 1.3 pandas Official Documentation: Comparison with Stata

- **Title:** Comparison with Stata (pandas documentation)
- **Author(s):** pandas development team
- **URL:** https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html
- **Type:** Official documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Official pandas page mapping Stata concepts to pandas equivalents
  across 8 sections: Data Structures, Data Input/Output, Data Operations, String
  Processing, Merging, Missing Data, GroupBy, and Other Considerations. Covers the
  complete mapping from Stata's single-dataset paradigm to pandas DataFrames. Includes
  detailed examples for `collapse`/`groupby`, `egen`/`transform`, `merge`/`pd.merge()`,
  and string operations (`subinstr`/`str.replace()`). Documents key conceptual
  differences including zero-based indexing, copies vs. in-place operations, and NaN vs.
  dot missing values.
- **Relevance to DAAF:** High -- authoritative source for core data manipulation
  mappings. While DAAF uses polars rather than pandas, the conceptual mappings are
  foundational and the Stata-to-polars skill should reference this as baseline, then
  provide polars-specific translations.
- **Currency concern:** None -- official documentation updated with each pandas release.

### 1.4 UC Berkeley Econ 148: Python for Economists

- **Title:** Python for Economists (Econ 148 Textbook)
- **Author(s):** Rohan Jha
- **URL:** https://www.econ148.org/textbook/content/01-python_v_stata/index.html
- **Type:** University course textbook
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** UC Berkeley course textbook that includes a dedicated "Python vs Stata"
  section with chapters on pedagogy, history of the languages, summary of differences
  (general-purpose vs. specialized, syntax, packages, data management, learning curve,
  cost, community), and syntax translation. Emphasizes that economists spend ~1/3 of
  their time getting and cleaning data, motivating Python's superior data engineering
  capabilities. Full textbook also covers pandas, visualization, and regression.
- **Relevance to DAAF:** Medium -- useful for motivational framing and high-level
  conceptual differences, though less detailed than Sullivan or Turrell for specific
  command mappings.
- **Currency concern:** Low -- copyright 2024, modern content.

### 1.5 QuantEcon Statistics Cheatsheet

- **Title:** Statistics Cheatsheet (Stata/Pandas/R crosswalk)
- **Author(s):** QuantEcon (Thomas J. Sargent, John Stachurski, and contributors)
- **URL:** https://cheatsheets.quantecon.org/stats-cheatsheet.html
- **Type:** Cheat sheet / Quick reference
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Compact three-column crosswalk (Stata, Pandas, Base R) covering ~29
  statistical operations organized into Basics, Filtering, Summarizing, Reshaping,
  Merging, and Plotting. Clean side-by-side format suitable for quick reference.
- **Relevance to DAAF:** Medium -- useful as a quick-reference companion but too
  abbreviated for in-depth translation work. Good supplemental material.
- **Currency concern:** Low -- core operations are stable across versions.

### 1.6 Seungjun (Josh) Kim: Python to STATA Cheat Sheet

- **Title:** Python to STATA Cheat Sheet
- **Author(s):** Seungjun (Josh) Kim
- **URL:** https://joshnjuny.medium.com/python-to-stata-cheat-sheet-for-those-struggling-to-transition-from-python-to-stata-for-f5e58ce66087
- **Type:** Blog post / Cheat sheet
- **Last verified:** 2026-03-28
- **Quality:** Fair
- **Key content:** Bidirectional cheat sheet showing Python-to-Stata and Stata-to-Python
  command mappings. Written for those transitioning in either direction. Covers common
  data manipulation operations.
- **Relevance to DAAF:** Low -- covers the same ground as Sullivan and pandas docs
  but in less depth. Useful as a secondary reference.
- **Currency concern:** Moderate -- Medium blog post, no clear update schedule.

---

## 2. Package Mapping Resources

### 2a. Data Manipulation (Stata data commands -> polars/pandas)

#### Adam Ross Nelson: StataQuickReference Crosswalk

- **Title:** Stata to Pandas Cross-Walk (StataQuickReference repository)
- **Author(s):** Adam Ross Nelson
- **URL:** https://github.com/adamrossnelson/StataQuickReference/blob/master/spcrosswlk.md
- **Type:** GitHub repository / Reference document
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Comprehensive crosswalk covering 7 major sections: Starting Out
  (loading, display, subsetting, variable creation, text/numeric operations, renaming,
  sorting, filtering), Categorical Factor Variables (tabulations, encoding, dummies),
  Merge Datasets, Append Datasets, Reshape Datasets, Loops (foreach, forvalues), and
  Exporting to Stata. Includes important notes on unicode handling and data type
  conversion when writing .dta files.
- **Relevance to DAAF:** Medium -- pandas-focused, but the Stata command inventory is
  valuable for ensuring the skill covers all common operations. The loop translation
  section (foreach/forvalues -> Python for loops) is particularly useful.
- **Currency concern:** Moderate -- repository activity unclear; pandas core API stable.

#### pyreadstat: Reading/Writing Stata Files

- **Title:** pyreadstat: Python package for reading/writing SAS, SPSS, and Stata files
- **Author(s):** Otto Fajardo (Roche)
- **URL:** https://github.com/Roche/pyreadstat
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** C library wrapper (ReadStat by Evan Miller) enabling Python to read and
  write Stata .dta files directly into pandas or polars DataFrames. Key functions:
  `read_dta()` returns both a DataFrame and a metadata object containing variable labels,
  value labels, and file-level metadata. Supports output to pandas, polars, or dict
  format via `output_format` parameter. Also writes .dta files from pandas/polars.
  Critical for preserving Stata metadata (value labels, variable labels) during
  migration.
- **Relevance to DAAF:** High -- essential tool for data interchange. The metadata
  preservation capability is critical for Stata users who rely heavily on variable and
  value labels. DAAF's parquet-first workflow means this is primarily relevant for
  initial data ingestion from Stata-format sources.
- **Currency concern:** None -- actively maintained.

#### PyStataR: Stata-Equivalent Commands for pandas

- **Title:** PyStataR: Comprehensive Python package providing Stata-equivalent commands
- **Author(s):** Bryce Wang (Stanford)
- **URL:** https://github.com/brycewang-stanford/PyStataR
- **Type:** Software / GitHub repository
- **Last verified:** 2026-03-28
- **Quality:** Fair
- **Key content:** Python package implementing Stata-like commands for pandas DataFrames.
  Covers four core Stata operations: `egen` (via pyegen -- group operations, ranking,
  row statistics), `tabulate` (via pdtab -- one-way and two-way cross-tabulation),
  `winsor2` (via pywinsor2 -- outlier treatment with IQR and percentile methods), and
  `outreg2` (via pyoutreg -- regression table export to Excel/Word).
- **Relevance to DAAF:** Low -- DAAF uses native polars/pandas idioms rather than
  Stata-like wrappers. However, documenting this package helps Stata users understand
  that the community has created bridge libraries. More useful as a conceptual reference
  than as a recommended dependency.
- **Currency concern:** Moderate -- small project, 23 commits; may not be actively maintained.

### 2b. Regression and Econometrics

#### pyfixest: Python's reghdfe/fixest Equivalent

- **Title:** pyfixest: Fast High-Dimensional Fixed Effects Regression in Python
- **Author(s):** Alexander Fischer, Styfen Schaer, and contributors
- **URL:** https://pyfixest.org/ (docs); https://github.com/py-econometrics/pyfixest (source)
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Python implementation of R's fixest, which itself was inspired by
  Stata's reghdfe. Supports OLS, WLS, IV, Poisson (pplmhdfe algorithm), and GLMs
  (logit, probit, gaussian) with multi-way high-dimensional fixed effects via
  Frisch-Waugh-Lovell demeaning. Formula syntax: `Y ~ X1 + X2 | fe1 + fe2` for FE
  absorption, `Y ~ X1 | fe1 | endo ~ instrument` for IV. Inference: iid, HC1-3,
  CRV1/CRV3 (up to two-way clustering), wild bootstrap, randomization inference.
  Includes DiD estimators: TWFE, did2s, lpdid, Sun-Abraham. Multiple estimation
  shortcuts: `sw()`, `csw()`, `split`, `fsplit`. Publication tables via `etable()`.
  The quickstart page explicitly references Stata reghdfe syntax for comparison.
- **Relevance to DAAF:** High -- primary regression package in the DAAF stack. The
  formula syntax deliberately mirrors fixest/reghdfe conventions, making it the most
  natural bridge for Stata users.
- **Currency concern:** None -- actively maintained, frequent releases.

#### statsmodels: General-Purpose Statistical Modeling

- **Title:** statsmodels: Statistical modeling and econometrics in Python
- **Author(s):** statsmodels development team (Josef Perktold, Skipper Seabold, et al.)
- **URL:** https://www.statsmodels.org/stable/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Python's primary general-purpose statistics library. Covers
  OLS/WLS/GLS, GLM (logit, probit, Poisson, negative binomial), discrete choice models
  (multinomial logit, ordered models), time series (ARIMA, SARIMAX, VAR), mixed effects,
  robust regression, and hypothesis testing. For Stata users: `Logit`/`Probit` classes
  correspond to Stata's `logit`/`probit` commands; `IV2SLS` provides basic instrumental
  variable estimation comparable to `ivregress`. Important gotcha: statsmodels does NOT
  include an intercept by default (must use `sm.add_constant()`), unlike Stata which
  always includes one.
- **Relevance to DAAF:** High -- core DAAF dependency for models beyond pyfixest's scope.
  Essential for discrete choice, time series, and GLM models.
- **Currency concern:** None -- mature, actively maintained.

#### linearmodels: Panel Data and IV

- **Title:** linearmodels: Panel data, IV/GMM, system regression, and asset pricing models
- **Author(s):** Kevin Sheppard (bashtage)
- **URL:** https://bashtage.github.io/linearmodels/ (docs); https://github.com/bashtage/linearmodels (source)
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Fills gaps in statsmodels for panel data and advanced IV estimation.
  `PanelOLS` implements entity/time fixed effects (Stata's `xtreg, fe`/`xtreg, re`).
  `BetweenOLS` for between estimator. `FirstDifferenceOLS` for first-difference.
  `IV2SLS`, `IVLIML`, `IVGMM` for cross-sectional IV (Stata's `ivregress`/`ivreg2`).
  `PanelIV` classes for panel IV (Stata's `xtivreg`/`xtivreg2`). Formula interface
  supports `EntityEffects` and `TimeEffects` special values. Supports heteroskedasticity-
  robust and cluster-robust standard errors.
- **Relevance to DAAF:** High -- primary DAAF package for panel data models and advanced
  IV. The xtreg-to-PanelOLS mapping is one of the most common Stata-to-Python
  translation needs for applied microeconomists.
- **Currency concern:** None -- actively maintained.

#### Tidy Finance with Python: Fixed Effects and Clustered SEs

- **Title:** Fixed Effects and Clustered Standard Errors with Python (Tidy Finance)
- **Author(s):** Christoph Scheuch, Stefan Voigt, Patrick Weiss
- **URL:** https://www.tidy-finance.org/python/fixed-effects-and-clustered-standard-errors.html
- **Type:** Online textbook chapter
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Practical tutorial on implementing fixed effects regressions and
  clustered standard errors in Python using pyfixest. Covers entity fixed effects, time
  fixed effects, and two-way clustering by firm and year. Finance-focused examples but
  the econometric techniques are identical to those used in applied microeconomics.
  Demonstrates the direct equivalence between Stata's `areg`/`reghdfe` and pyfixest's
  `feols()`.
- **Relevance to DAAF:** Medium -- well-written practical tutorial that complements
  pyfixest documentation. Finance focus limits direct applicability but techniques
  transfer.
- **Currency concern:** Low -- uses pyfixest, which is actively maintained.

### 2c. Visualization

#### plotnine: Grammar of Graphics for Python

- **Title:** plotnine: A Grammar of Graphics for Python
- **Author(s):** Hassan Kibirige
- **URL:** https://plotnine.org/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Python implementation of R's ggplot2 using the grammar of graphics.
  Near-identical syntax to ggplot2: `ggplot(aes(...)) + geom_point() + ...`. Covers
  geoms, aesthetics, scales, coordinates, facets, and themes. For Stata users, this
  represents a paradigm shift from Stata's imperative `graph twoway` syntax to a
  declarative, layered approach. Key mappings: `twoway scatter` -> `geom_point()`,
  `twoway line` -> `geom_line()`, `histogram` -> `geom_histogram()`, `kdensity` ->
  `geom_density()`, `graph bar` -> `geom_bar()`/`geom_col()`. Main syntax difference
  from ggplot2: column names are quoted strings in plotnine.
- **Relevance to DAAF:** High -- DAAF's primary static visualization library. The
  Stata-to-plotnine mapping requires explaining the grammar-of-graphics paradigm, which
  is fundamentally different from Stata's graph command syntax.
- **Currency concern:** None -- v0.15.3 as of verification date.

#### Coding for Economists: Visualization with plotnine

- **Title:** Data Visualisation using the Grammar of Graphics with Plotnine
  (Chapter of "Coding for Economists")
- **Author(s):** Arthur Turrell
- **URL:** https://aeturrell.github.io/coding-for-economists/vis-plotnine.html
- **Type:** Online textbook chapter
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Economics-focused plotnine tutorial within the broader Coding for
  Economists resource. Covers building plots incrementally with economics-relevant
  examples. A natural companion to the "Coming from Stata" chapter in the same book.
- **Relevance to DAAF:** High -- directly applicable economics visualization examples
  using the DAAF stack.
- **Currency concern:** Low -- actively maintained resource.

### 2d. Survey Analysis

#### svy: Complex Survey Analysis in Python

- **Title:** svy: Python Package for Complex Survey Design and Analysis
- **Author(s):** svy development team
- **URL:** https://svylab.com/docs/svy/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Python equivalent of Stata's `svy:` command prefix and R's `survey`
  package. Design specification via `svy.Design(stratum=..., psu=..., wgt=...)`,
  directly paralleling Stata's `svyset`. Supports Taylor linearization, BRR, jackknife,
  and bootstrap variance estimation. Produces design-consistent estimates for means,
  totals, proportions, ratios, medians, and regression models. Validated to be
  numerically equivalent to R's survey package. Supersedes the earlier `samplics` package.
- **Relevance to DAAF:** High -- DAAF's primary complex survey analysis library.
  Direct mapping to Stata's svy: prefix commands makes this the most natural translation
  path for Stata users working with NHANES, DHS, BRFSS, and similar survey data.
- **Currency concern:** None -- actively maintained; supersedes samplics.

#### samplics: Legacy Survey Package

- **Title:** samplics: Select, weight and analyze complex sample data
- **Author(s):** Mamadou S. Diallo
- **URL:** https://samplics-org.github.io/samplics/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Earlier Python package for complex survey design. Covers sampling
  procedures, weighting adjustments, estimation (Taylor and replication-based), and
  small area estimation (GREG, area-level, unit-level SAE). Published in JOSS. Now
  superseded by `svy` for new development, but samplics remains available.
- **Relevance to DAAF:** Low -- superseded by svy, but useful to mention for context
  (Stata users searching may find references to it).
- **Currency concern:** High -- superseded by svy; no new features planned.

### 2e. Causal Inference

#### binsreg: Binscatter Regressions

- **Title:** binsreg: Binscatter Estimation and Inference
- **Author(s):** Matias D. Cattaneo, Richard K. Crump, Max H. Farrell, Yingjie Feng
- **URL:** https://nppackages.github.io/binsreg/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Identical methodology implemented in Python, R, and Stata. Includes
  `binsreg` (least squares binscatter), `binslogit`/`binsprobit`/`binsqreg` (nonlinear),
  `binstest` (hypothesis testing), `binspwc` (pairwise comparison), `binsregselect`
  (bin selection). Supports covariate adjustment, weighting, clustering, and multi-sample
  analysis. Directly replaces Stata's older `binscatter` command.
- **Relevance to DAAF:** High -- identical package available in Python; Stata users can
  use the exact same methodology with nearly identical syntax.
- **Currency concern:** None -- actively maintained by the original methodological authors.

#### rdrobust: Regression Discontinuity Design

- **Title:** rdrobust: Statistical inference for RD designs
- **Author(s):** Sebastian Calonico, Matias D. Cattaneo, Max H. Farrell, Rocio Titiunik
- **URL:** https://rdpackages.github.io/rdrobust/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Identical methodology in Python, R, and Stata for regression
  discontinuity designs. Point estimators, confidence intervals, bandwidth selectors,
  automatic RD plots. Part of the broader `rdpackages` ecosystem including `rdhte`
  (heterogeneous treatment effects) and `rdmulti` (multiple cutoffs).
- **Relevance to DAAF:** High -- direct Python equivalent of the Stata RDD toolkit.
  Same authors maintain all three language implementations.
- **Currency concern:** None -- actively maintained; major upgrade Winter 2020.

#### pyfixest DiD Estimators

- **Title:** Difference-in-Differences Estimators in pyfixest
- **Author(s):** Alexander Fischer, Styfen Schaer, and contributors
- **URL:** https://pyfixest.org/ (DiD documentation section)
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** pyfixest includes modern DiD estimators: TWFE, did2s (Gardner 2022),
  lpdid (local projections DiD), and Sun-Abraham interaction-weighted estimators.
  These correspond to Stata packages: `did2s`, `eventstudyinteract`,
  `csdid` (Callaway-Sant'Anna), and `hdidregress` (Stata 18 built-in).
  The Python implementations are integrated into pyfixest's formula interface.
- **Relevance to DAAF:** High -- modern DiD methods are central to applied
  microeconomics. Having these in pyfixest means Stata users get the same estimators
  with a familiar formula syntax.
- **Currency concern:** None -- part of actively maintained pyfixest.

#### DoubleML: Double/Debiased Machine Learning

- **Title:** DoubleML: Double Machine Learning in Python
- **Author(s):** Philipp Bach, Victor Chernozhukov, Malte S. Kurz, Martin Spindler
- **URL:** https://docs.doubleml.org/stable/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Python implementation of double/debiased machine learning for
  treatment and structural parameter estimation. Models: Partially Linear Model,
  Interactive Model (binary treatment), Partially Linear IV, Flexible Partially Linear
  IV, Interactive IV. Integrates with scikit-learn estimators. Stata equivalent: `ddml`
  package (Ahrens, Hansen, Schaffer), which leverages `pystacked` as a frontend to
  scikit-learn.
- **Relevance to DAAF:** Medium -- relevant for users doing modern causal inference
  with machine learning. Maps directly to Stata's ddml package.
- **Currency concern:** None -- actively maintained.

### 2f. Post-Estimation and Tables

#### marginaleffects: Python Equivalent of Stata's margins

- **Title:** marginaleffects: Model to Meaning
- **Author(s):** Vincent Arel-Bundock, Noah Greifer, Andrew Heiss
- **URL:** https://marginaleffects.com/
- **Type:** Software documentation / Online textbook
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Unified interface for post-estimation analysis across 100+ model
  types in R and Python. Core functions: `predictions()`, `comparisons()` (contrasts,
  risk ratios), `slopes()` (marginal effects), `hypotheses()`. Directly corresponds to
  Stata's `margins` command. Key feature: every page has R/Python toggle showing
  equivalent code. Uncertainty via delta method, bootstrap, or simulation. Published
  in Journal of Statistical Software.
- **Relevance to DAAF:** High -- Stata's `margins` command is one of the most heavily
  used post-estimation tools. The marginaleffects package is the direct Python
  equivalent, with explicit validation against Stata output.
- **Currency concern:** None -- actively maintained with bilingual support.

#### pystout: Regression Table Export

- **Title:** pystout: Stata-style regression tables in Python
- **Author(s):** pystout developers
- **URL:** https://pypi.org/project/pystout/
- **Type:** Software documentation
- **Last verified:** 2026-03-28
- **Quality:** Fair
- **Key content:** Python package designed to replicate Stata's `estout`/`esttab`
  functionality. Exports regression results with significance stars, model statistics
  (F-stat, R-squared, N), custom rows, and notes. Tested with statsmodels OLS and
  linearmodels (OLS, IV2SLS, PanelOLS).
- **Relevance to DAAF:** Medium -- Stata users expect `esttab`/`outreg2`-style table
  output. pystout fills this gap, though pyfixest's `etable()` is the primary DAAF
  recommendation for regression tables.
- **Currency concern:** Moderate -- limited functionality compared to Stata's estout;
  may not cover all model types.

---

## 3. Academic and Educational Resources

### 3.1 The Effect (2nd ed.) by Nick Huntington-Klein

- **Title:** The Effect: An Introduction to Research Design and Causality (2nd edition)
- **Author(s):** Nick Huntington-Klein
- **URL:** https://theeffectbook.net/ (free online); Routledge/Chapman & Hall (print)
- **Type:** Textbook with R/Stata/Python code
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Free online textbook on causal inference and research design with code
  examples in R, Stata, and Python throughout. Covers identification, DAGs, matching,
  fixed effects, DiD, RDD, IV, and synthetic control. Second edition adds partial
  identification and updated methods. Companion `causaldata` package available in all
  three languages (`pip install causaldata`). 60+ video lectures accompany the text.
  The side-by-side code presentation makes it an ideal Stata-to-Python translation
  reference for causal inference methods.
- **Relevance to DAAF:** High -- the trilingual code examples are directly usable for
  translating causal inference concepts. The `causaldata` package enables hands-on
  practice with the same datasets across languages.
- **Currency concern:** Low -- 2nd edition is current; actively maintained online version.

### 3.2 Causal Inference: The Mixtape by Scott Cunningham

- **Title:** Causal Inference: The Mixtape
- **Author(s):** Scott Cunningham
- **URL:** https://mixtape.scunning.com/ (free online); Yale University Press (print)
- **Type:** Textbook with R/Stata code (Python via community notebooks)
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Free online causal inference textbook with code in R and Stata
  throughout. Covers matching, IV, RDD, DiD, and synthetic control. Community-contributed
  Python Jupyter notebooks replicate all examples
  (https://github.com/alexanderthclark/Causal-Inference-Mixtape). The `causaldata`
  package (same as The Effect) provides datasets in Python.
- **Relevance to DAAF:** High -- alongside The Effect, this is one of the two most
  popular causal inference textbooks in economics. The Stata code in the book can be
  directly mapped to Python equivalents for the skill.
- **Currency concern:** Low -- free online edition actively maintained.

### 3.3 Causal Inference for the Brave and True by Matheus Facure

- **Title:** Causal Inference for the Brave and True
- **Author(s):** Matheus Facure
- **URL:** https://matheusfacure.github.io/python-causality-handbook/ (free); O'Reilly (print)
- **Type:** Online handbook / textbook (Python-only)
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Free Python-focused causal inference resource covering RCTs, linear
  regression, propensity score, DiD (including the modern heterogeneous treatment
  effects saga), synthetic control, and synthetic DiD. All code in Python. Particularly
  strong chapter on "The Difference-in-Differences Saga" covering Callaway-Sant'Anna,
  Sun-Abraham, and imputation approaches.
- **Relevance to DAAF:** Medium -- Python-only (no Stata code), but excellent for Stata
  users who need to understand how their familiar causal inference methods are
  implemented in Python.
- **Currency concern:** Low -- actively maintained.

### 3.4 Data Analysis for Business, Economics, and Policy (Gabors)

- **Title:** Data Analysis for Business, Economics, and Policy
- **Author(s):** Gabor Bekos and Gabor Kezdi
- **URL:** https://gabors-data-analysis.com/ (free code); Cambridge University Press (print)
- **Type:** Textbook with R/Stata/Python code
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Comprehensive data analysis textbook with all code freely available in
  R, Stata, and Python via GitHub (https://github.com/gabors-data-analysis/da_case_studies).
  Covers data exploration, regression analysis (including functional form, probability
  models), predictive analytics (cross-validation, tree-based ML, classification,
  forecasting), and causal analysis. Each case study has parallel implementations in all
  three languages. Teaching guide available for course adoption.
- **Relevance to DAAF:** High -- the three-language parallel code is ideal for building
  Stata-to-Python translation tables. Case studies are drawn from real-world economics
  and policy contexts.
- **Currency concern:** Low -- published 2021 by Cambridge University Press; code
  repository actively maintained.

### 3.5 Using Python for Introductory Econometrics (Heiss & Brunner)

- **Title:** Using Python for Introductory Econometrics
- **Author(s):** Florian Heiss and Daniel Brunner
- **URL:** https://www.urfie.net/ (website); PDF freely available
- **Type:** Textbook companion
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Companion to Wooldridge's "Introductory Econometrics: A Modern
  Approach" (the most widely assigned economics econometrics textbook, which uses Stata).
  Chapters mirror Wooldridge's structure covering simple and multiple regression,
  inference, heteroskedasticity, time series, panel data, IV/2SLS, simultaneous
  equations, and limited dependent variables. All implemented in Python. Compatible
  with Wooldridge 5th, 6th, and 7th editions. Available in R, Python, and Julia versions.
  Print copy ~$27; PDF free.
- **Relevance to DAAF:** High -- since Wooldridge is the canonical Stata-based
  econometrics textbook, this companion directly bridges every Wooldridge example to
  Python. Invaluable for graduate students making the transition.
- **Currency concern:** Low -- structured around Wooldridge editions that remain current.

### 3.6 Wooldridge Dataset Package for Python

- **Title:** wooldridge: Python package with Wooldridge textbook datasets
- **Author(s):** spring-haru (maintainer)
- **URL:** https://pypi.org/project/wooldridge/
- **Type:** Data package
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Python package containing 115 datasets from Wooldridge's "Introductory
  Econometrics" textbook. Install via `pip install wooldridge`. Enables running all
  Wooldridge examples in Python without manual data downloads.
- **Relevance to DAAF:** Medium -- complementary to the Heiss & Brunner textbook.
  Enables hands-on practice translating Wooldridge Stata examples to Python.
- **Currency concern:** Low -- dataset collection is stable.

### 3.7 QuantEcon Lectures

- **Title:** Quantitative Economics with Python
- **Author(s):** Thomas J. Sargent and John Stachurski
- **URL:** https://python.quantecon.org/
- **Type:** Online lecture series
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Comprehensive open-source lecture series on quantitative economic
  modeling in Python. Multiple levels: introductory (programming fundamentals),
  intermediate (quantitative economics), and advanced. Covers dynamic programming,
  linear algebra, time series, asset pricing, search models, and more. Emphasizes
  simulation and visualization. Used in university courses globally.
- **Relevance to DAAF:** Medium -- more focused on macroeconomics/theory than applied
  micro/data analysis, but an essential reference for quantitative economists learning
  Python. Less directly relevant for Stata data analysis translation.
- **Currency concern:** None -- actively maintained.

### 3.8 LOST: Library of Statistical Techniques

- **Title:** LOST: Library of Statistical Techniques
- **Author(s):** Nick Huntington-Klein and community contributors
- **URL:** https://lost-stats.github.io/
- **Type:** Community wiki / Reference
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Rosetta Stone for statistical software. Each page covers one
  statistical technique with implementations in multiple languages (Python, R, Stata,
  SAS, and more). Seven categories: Data Manipulation, Geo-Spatial, Machine Learning,
  Model Estimation, Presentation, Time Series, and Other. Community-editable with
  GitHub-based contributions. Coverage includes OLS, matching, logit/probit, multilevel
  models, DiD, RDD, event studies, and more.
- **Relevance to DAAF:** High -- the multi-language implementations make this the best
  "look up any technique in Stata, see the Python equivalent" resource. Particularly
  valuable for DiD event studies, RDD, and other modern causal inference methods.
- **Currency concern:** Moderate -- community-maintained; some pages may be dated.
  Check individual pages for currency.

### 3.9 Python for Economists (Harvard, Alex Bell)

- **Title:** Python for Economists
- **Author(s):** Alex Bell (Harvard)
- **URL:** https://scholar.harvard.edu/files/ambell/files/python_for_economists.pdf
- **Type:** Tutorial / PDF guide
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** PDF guide teaching Python to economics researchers. Emphasizes
  capabilities beyond Stata's reach: text processing, web scraping, API access,
  and machine learning. Practical orientation for researchers who need Python for
  specific tasks that Stata cannot handle.
- **Relevance to DAAF:** Medium -- helps frame the "why Python" motivation for Stata
  users but less focused on direct command translation.
- **Currency concern:** Moderate -- PDF publication, unclear update schedule.

---

## 4. Stata Official Documentation Structure

### 4.1 Documentation Organization

Based on examination of https://www.stata.com/features/documentation/ and
https://www.stata.com/links/:

**Scale:** Stata 19 documentation consists of over 19,000 pages detailing every feature
with methods/formulas and worked examples. Every Stata installation includes the full
documentation as integrated PDFs.

**Core Manuals:**
- Getting Started guides (Windows, Mac, Unix)
- User's Guide
- Base Reference Manual
- Data Management Reference Manual
- Graphics Reference Manual
- Customizable Tables and Collected Results Reference Manual
- Reporting Reference Manual
- Functions Reference Manual

**Subject-Specific Statistics Manuals (18+):**
- Adaptive Designs
- Bayesian Analysis / Bayesian Model Averaging
- **Causal Inference and Treatment-Effects Estimation** (new in recent versions)
- Choice Models
- DSGE
- Extended Regression Models (ERM)
- Finite Mixture Models
- Item Response Theory
- Lasso
- **Longitudinal/Panel Data** (xt commands)
- Machine Learning (H2O integration)
- Meta-Analysis
- Multilevel Mixed-Effects Models
- Multiple Imputation
- Multivariate Statistics
- Power and Sample Size
- Spatial Autoregressive Models
- Structural Equation Modeling
- **Survey Data** (svy commands)
- Survival Analysis
- Time-Series

**Programming Manuals:**
- Programming Reference Manual
- Mata Matrix Programming Manual

**Documentation Design:** Reference manuals are NOT meant to be read cover-to-cover.
Each entry covers one command with syntax, options, examples, stored results, and
methods/formulas. "Quick starts" help new users; detailed sections serve as definitive
reference.

### 4.2 Official Learning Resources

From https://www.stata.com/links/resources-for-learning-stata/:
- 350+ short video tutorials (YouTube)
- NetCourses (self-paced, 6-7 weeks)
- Stata Blog (blog.stata.com)
- Statalist forum (60,000+ users)
- Stata Journal (quarterly peer-reviewed)
- Visual graph overview (100+ categorized examples)
- Python integration cheat sheet and flyer
- Stata cheat sheets by Tim Essam and Laura Hughes

### 4.3 Key Insight for Skill Design

Stata's documentation is organized around COMMANDS (one entry per command), not around
TASKS or WORKFLOWS. This means Stata users think in terms of specific commands
(`reghdfe`, `xtreg`, `margins`, `collapse`, `merge`, etc.) and need to find Python
equivalents for those specific commands. The skill should be organized to support this
lookup pattern -- users will search by Stata command name, not by Python concept.

---

## 5. Community Resources

### 5.1 Chuck Huber's Stata/Python Integration Blog Series

- **Title:** Stata/Python integration (8-part blog series)
- **Author(s):** Chuck Huber (Director of Statistical Outreach, StataCorp)
- **URL:** https://blog.stata.com/author/chuber/ (author page)
  - Part 1: https://blog.stata.com/2020/08/18/stata-python-integration-part-1-setting-up-stata-to-use-python/
  - Part 2: https://blog.stata.com/2020/08/25/stata-python-integration-part-2-three-ways-to-use-python-in-stata/
  - Part 3: https://blog.stata.com/2020/09/01/stata-python-integration-part-3-how-to-install-python-packages/
  - Part 4: https://blog.stata.com/2020/09/10/stata-python-integration-part-4-how-to-use-python-packages/
  - Part 5: https://blog.stata.com/2020/09/14/stata-python-integration-part-5-three-dimensional-surface-plots/
  - Part 6: https://blog.stata.com/2020/09/29/stata-python-integration-part-6-working-with-apis-and-json-data/
  - Part 8: https://blog.stata.com/2020/11/05/stata-python-integration-part-8-using-the-stata-function-interface/
- **Type:** Blog series
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Official 8-part series on using Python within Stata (introduced in
  Stata 16). Covers: (1) installation/setup, (2) three ways to call Python from Stata,
  (3) installing Python packages, (4) using packages, (5) 3D surface plots, (6) API/JSON
  data access, (8) Stata Function Interface (SFI) for passing data between Stata and
  Python. Written by StataCorp's Director of Statistical Outreach.
- **Relevance to DAAF:** Medium -- focused on Python-WITHIN-Stata rather than
  Python-INSTEAD-OF-Stata. However, useful for understanding how Stata officially
  positions Python integration, and for users maintaining a hybrid workflow.
- **Currency concern:** Moderate -- written 2020; core concepts remain valid but specific
  API details may have evolved in Stata 17-19.

### 5.2 Adam Ross Nelson: Rosetta Stone Repositories

- **Title:** Python, R, Stata Rosetta Stone
- **Author(s):** Adam Ross Nelson
- **URL:** https://github.com/adamrossnelson/rosetta (Rosetta Stone);
  https://github.com/adamrossnelson/crossreg (regression crosswalk);
  https://github.com/adamrossnelson/StataQuickReference (Stata-Pandas crosswalk)
- **Type:** GitHub repositories
- **Last verified:** 2026-03-28
- **Quality:** Fair
- **Key content:** Suite of repositories providing side-by-side implementations in
  Python, R, and Stata. The StataQuickReference repo contains the most useful artifact:
  a detailed Stata-to-Pandas crosswalk. The crossreg repo demonstrates OLS regression
  in all three languages. Language composition of rosetta repo: Stata 40%, Python 31%,
  R 29%.
- **Relevance to DAAF:** Medium -- the crosswalk document is useful reference material;
  the side-by-side implementations are more educational than practical.
- **Currency concern:** Moderate -- limited commit activity; core content stable.

### 5.3 German Rodriguez: Princeton Stata Tutorial

- **Title:** Stata Tutorial
- **Author(s):** German Rodriguez (Princeton University)
- **URL:** https://grodri.github.io/stata/
- **Type:** Tutorial
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Widely cited introductory Stata tutorial covering data management,
  graphics, tables, and programming. Updated for Stata 18. Recommended by stata.com as
  a primary learning resource. Understanding what this tutorial covers helps identify
  which Stata concepts need Python equivalents in the skill.
- **Relevance to DAAF:** Medium -- not a translation resource per se, but understanding
  the standard Stata tutorial path helps design the skill to meet users where they are.
- **Currency concern:** Low -- updated for Stata 18.

### 5.4 Oscar Torres-Reyna: Princeton Panel Data Tutorial

- **Title:** Panel Data Analysis: Fixed and Random Effects using Stata
- **Author(s):** Oscar Torres-Reyna (Princeton University)
- **URL:** https://www.princeton.edu/~otorres/Panel101.pdf
- **Type:** Tutorial / PDF
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Classic tutorial on panel data analysis with Stata, widely used in
  economics graduate programs. Covers `xtreg` with fixed and random effects, Hausman
  test, and practical implementation. Understanding this tutorial's approach helps design
  Python panel data equivalents (linearmodels PanelOLS).
- **Relevance to DAAF:** Medium -- Stata reference material; the skill should map every
  command in this tutorial to its Python equivalent.
- **Currency concern:** Moderate -- older tutorial, but panel data fundamentals unchanged.

### 5.5 UCLA OARC: Stata Resources

- **Title:** Statistical Methods and Data Analytics: Stata
- **Author(s):** UCLA Office of Advanced Research Computing
- **URL:** https://stats.oarc.ucla.edu/stata/
- **Type:** University resource hub
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Comprehensive Stata learning resource featuring FAQs, learning modules,
  annotated output for many statistical procedures, textbook examples, and web books.
  Extensive coverage of specific methods (logistic regression, multilevel models,
  ordinal outcomes, etc.) with step-by-step Stata implementations. Many social scientists
  learn Stata from these pages.
- **Relevance to DAAF:** Medium -- understanding how UCLA OARC teaches Stata helps
  identify common workflows that need Python translation. The annotated output sections
  are particularly useful for understanding what Stata users expect to see in output.
- **Currency concern:** Low -- regularly maintained university resource.

### 5.6 Princeton DiD Guide

- **Title:** A Step-by-Step Guide: Difference-in-Differences in Stata
- **Author(s):** Princeton University Library Research Guides
- **URL:** https://libguides.princeton.edu/stata-did
- **Type:** University guide
- **Last verified:** 2026-03-28
- **Quality:** Good
- **Key content:** Step-by-step Stata implementation of difference-in-differences methods.
  Covers traditional TWFE, event studies, and modern heterogeneous treatment effect
  estimators. Useful benchmark for what Stata-based DiD workflows look like.
- **Relevance to DAAF:** Medium -- the skill should map every Stata DiD command in this
  guide to its pyfixest/Python equivalent.
- **Currency concern:** Moderate -- check for updates on modern DiD methods.

---

## 6. Key Paradigm Differences: Stata vs. Python

This section documents the fundamental paradigm differences that the skill must explain.
These are based on synthesis of all resources reviewed above.

### 6.1 Single Dataset vs. Multiple DataFrames

**Stata:** One dataset in memory at a time. All commands operate on "the data." Variables
(columns) are referenced by name without qualification. `preserve`/`restore` provides
temporary data snapshots. `tempfile` enables passing data between stages.

**Python:** Multiple DataFrames coexist. Every operation specifies which DataFrame it acts
on (`df["column"]`). No need for preserve/restore -- just assign to a new variable
(`df_backup = df.copy()`). This is the single biggest conceptual shift for Stata users.

### 6.2 Command-Centric vs. Object-Oriented

**Stata:** Commands are verbs that act on the global dataset: `gen x = 1`, `keep if y > 0`,
`reg y x`. The verb IS the operation.

**Python:** Methods are called on objects: `df["x"] = 1`, `df = df[df["y"] > 0]`,
`pf.feols("y ~ x", data=df)`. The data object carries the methods.

### 6.3 Missing Values

**Stata:** Missing is `.` (dot). It is larger than all numbers: `10 < .` is TRUE.
Extended missing values `.a` through `.z` are ordered. Missing values propagate in
expected ways in Stata expressions.

**Python:** Missing is `np.nan` (or `None`). NaN is NOT comparable to anything:
`np.nan == np.nan` is FALSE, `np.nan > 10` is FALSE. Use `pd.isna()` / `.isna()` to
test. Integer columns with any missing value are coerced to float. This is the most
dangerous gotcha for Stata users.

### 6.4 Value Labels and Variable Labels

**Stata:** Rich metadata system. Value labels map integers to strings (e.g.,
`label define gender 0 "Male" 1 "Female"`). Variable labels describe columns.
Both are stored in the .dta file and display automatically.

**Python:** No built-in equivalent. pandas/polars DataFrames have column names but no
variable labels or value labels. Workarounds: (1) use `pyreadstat` to read metadata,
(2) store labels in a separate dictionary, (3) use Categorical dtypes, (4) use polars
`Enum` type. DAAF's parquet format does not preserve Stata labels.

### 6.5 Indexing

**Stata:** 1-based observation numbers. `_n` is the current observation number,
`_N` is the total count. `in 1/10` selects observations 1-10.

**Python:** 0-based indexing. `df.iloc[0]` is the first row, `df.iloc[0:10]` selects
rows 0-9 (10 rows). `df.head(10)` is the idiomatic equivalent of `list in 1/10`.

### 6.6 Macros vs. Variables

**Stata:** Local macros (`` `macro' ``) and global macros (`$macro`) are text
substitution mechanisms used for storing values, building dynamic commands, and
controlling loops.

**Python:** Standard variables (`x = value`). No text substitution; Python evaluates
expressions directly. f-strings (`f"text {variable}"`) for string interpolation.
Stata's `foreach var of varlist x y z` becomes Python's `for var in ["x", "y", "z"]`.

### 6.7 Do-Files vs. Python Scripts

**Stata:** `.do` files are the primary reproducibility mechanism. Master do-files call
subsidiary do-files. Logs capture all output. `set seed` for reproducibility.

**Python:** `.py` scripts serve the same role. In DAAF, sequential inline scripts mirror
do-file structure. `run_with_capture.sh` captures output appended to scripts (analogous
to Stata log files). `numpy.random.seed()` or `random.seed()` for reproducibility.

### 6.8 Package Management

**Stata:** `ssc install packagename` or `net install`. Packages are .ado files stored
in the PLUS directory. `ado describe` shows installed packages. No version locking.

**Python:** `pip install packagename`. Packages from PyPI. Virtual environments isolate
dependencies. `requirements.txt` or `pyproject.toml` for version pinning.
Version management is more robust than Stata's approach.

### 6.9 Immediate Execution vs. Assignment

**Stata:** Most commands execute immediately and modify the dataset in place.
`gen x = 1` creates the variable immediately.

**Python:** Most operations return a new object. `df["x"] = 1` modifies in place, but
many operations like `df.drop("x", axis=1)` return a copy. The `inplace=True` parameter
exists but is being deprecated in pandas. Polars is strictly immutable (always returns
new DataFrames).

### 6.10 Return Values and Stored Results

**Stata:** Commands store results in `r()` (r-class) or `e()` (e-class) scalars, macros,
and matrices. Access via `r(mean)`, `e(b)`, `_b[x]`, `_se[x]`.

**Python:** Functions return objects. Regression results are objects with attributes:
`results.params`, `results.bse`, `results.summary()`. pyfixest: `results.coef()`,
`results.se()`, `results.tstat()`.

---

## 7. Skill Architecture Recommendations

Based on this research, here is the recommended structure for the `stata-python-translation`
skill, modeled after the existing `r-python-translation` skill (~7,400 lines across 11 files):

### Recommended File Structure

```
.claude/skills/stata-python-translation/
  SKILL.md                              # Routing hub with overview tables and decision tree
  references/
    paradigm-differences.md             # Section 6 above: all core paradigm gaps
    data-management.md                  # collapse/egen/merge/reshape/append/keep/drop/gen/replace
                                        # -> polars equivalents (primary) + pandas (secondary)
    panel-data.md                       # xtreg/xtset/L./F./D. -> linearmodels PanelOLS/pyfixest
    regression-modeling.md              # reg/areg/reghdfe/ivregress/probit/logit/margins
                                        # -> pyfixest/statsmodels/linearmodels/marginaleffects
    causal-inference.md                 # DiD/RDD/IV/event studies/synthetic control
                                        # -> pyfixest DiD/rdrobust/binsreg
    visualization.md                    # graph twoway/histogram/kdensity/coefplot
                                        # -> plotnine/plotly
    survey-analysis.md                  # svy:/svyset -> svy package
    programming-workflow.md             # do-files/macros/loops/tempfile/preserve/ado
                                        # -> Python scripts/variables/for loops/pip
    data-io-labels.md                   # use/save/import/value labels/variable labels
                                        # -> pyreadstat/pd.read_stata/parquet
    gotchas.md                          # Missing values, intercepts, indexing, copies, labels
    external-resources.md               # This research document distilled into skill format
```

### Key Design Principles

1. **Command-indexed:** Stata users search by command name. Every reference file should
   have an index table mapping Stata commands to Python equivalents at the top.

2. **polars-primary, pandas-secondary:** DAAF uses polars as its primary DataFrame
   library. Provide polars translations first, with pandas alternatives noted where
   relevant (especially since most external resources use pandas).

3. **Side-by-side code blocks:** Every mapping should show Stata code and Python code
   side-by-side, not just describe the equivalence in text.

4. **Gotcha-heavy:** The paradigm differences (Section 6) generate the most confusion.
   The gotchas file should be substantial, with examples of common mistakes Stata users
   make in Python.

5. **Regression-deep:** Regression is where Stata users are most demanding. The
   regression file should cover every common estimation command with exact syntax
   translation, including standard error options, post-estimation (margins), and
   output formatting (esttab).

6. **Self-contained:** The skill should contain enough information that agents never need
   to search online for Stata-to-Python translations. All common commands should be
   documented inline.

### Coverage Priorities (by frequency of use in applied microeconomics)

**Must cover (daily use):**
- `reg`/`areg`/`reghdfe` -> pyfixest `feols()`
- `gen`/`replace`/`egen` -> polars expressions
- `merge`/`append` -> polars `join()`/`concat()`
- `collapse` -> polars `group_by().agg()`
- `keep`/`drop` -> polars `select()`/`filter()`
- `tab`/`tabulate` -> polars `value_counts()`
- `summ`/`describe` -> polars `describe()`
- `sort`/`gsort` -> polars `sort()`
- `use`/`save` -> `pl.read_parquet()`/`df.write_parquet()`
- `graph twoway` -> plotnine geoms
- `margins` -> marginaleffects
- `outreg2`/`esttab` -> pyfixest `etable()`

**Must cover (weekly use):**
- `xtreg` -> linearmodels PanelOLS
- `ivregress`/`ivreg2` -> pyfixest IV / linearmodels IV2SLS
- `logit`/`probit` -> statsmodels Logit/Probit or pyfixest feglm
- `reshape` -> polars `unpivot()`/`pivot()`
- `encode`/`decode` -> polars `cast()`
- `bysort` -> polars `group_by()`
- `foreach`/`forvalues` -> Python `for` loops
- `local`/`global` macros -> Python variables
- `preserve`/`restore` -> `df.clone()`
- `predict` -> model `.predict()` methods
- `test` -> hypothesis testing in model results

**Should cover (common in specific domains):**
- `svy:` commands -> svy package
- DiD commands (`csdid`/`did_multiplegt`/`eventstudyinteract`) -> pyfixest DiD
- `rdrobust` -> rdrobust Python
- `binscatter` -> binsreg
- `xtset`/`tsset`/`L.`/`F.`/`D.` operators -> panel setup in linearmodels
- `mixed` -> statsmodels MixedLM
- `tobit` -> statsmodels censored models
- `heckman` -> sample selection models
- `xtabond`/`xtdpd` -> GMM estimators in linearmodels

---

## Sources

### General Transition Guides
- [Stata to Python Equivalents - Daniel M. Sullivan](https://www.danielmsullivan.com/pages/tutorial_stata_to_python.html)
- [Coming from Stata - Coding for Economists](https://aeturrell.github.io/coding-for-economists/coming-from-stata.html)
- [Comparison with Stata - pandas documentation](https://pandas.pydata.org/docs/getting_started/comparison/comparison_with_stata.html)
- [Python for Economists - UC Berkeley Econ 148](https://www.econ148.org/textbook/content/01-python_v_stata/index.html)
- [QuantEcon Statistics Cheatsheet](https://cheatsheets.quantecon.org/stats-cheatsheet.html)
- [Python to STATA Cheat Sheet - Seungjun Kim](https://joshnjuny.medium.com/python-to-stata-cheat-sheet-for-those-struggling-to-transition-from-python-to-stata-for-f5e58ce66087)

### Package Mapping / Software
- [pyfixest documentation](https://pyfixest.org/)
- [statsmodels documentation](https://www.statsmodels.org/stable/)
- [linearmodels documentation](https://bashtage.github.io/linearmodels/)
- [plotnine documentation](https://plotnine.org/)
- [svy documentation](https://svylab.com/docs/svy/)
- [marginaleffects documentation](https://marginaleffects.com/)
- [pyreadstat](https://github.com/Roche/pyreadstat)
- [PyStataR](https://github.com/brycewang-stanford/PyStataR)
- [pystout](https://pypi.org/project/pystout/)
- [binsreg](https://nppackages.github.io/binsreg/)
- [rdrobust](https://rdpackages.github.io/rdrobust/)
- [DoubleML](https://docs.doubleml.org/stable/)
- [samplics](https://samplics-org.github.io/samplics/)

### Textbooks with Multi-Language Code
- [The Effect - Nick Huntington-Klein](https://theeffectbook.net/)
- [Causal Inference: The Mixtape - Scott Cunningham](https://mixtape.scunning.com/)
- [Causal Inference for the Brave and True - Matheus Facure](https://matheusfacure.github.io/python-causality-handbook/)
- [Data Analysis for Business, Economics, and Policy - Bekos & Kezdi](https://gabors-data-analysis.com/)
- [Using Python for Introductory Econometrics - Heiss & Brunner](https://www.urfie.net/)
- [Tidy Finance with Python](https://www.tidy-finance.org/python/fixed-effects-and-clustered-standard-errors.html)
- [QuantEcon Lectures](https://python.quantecon.org/)

### Community Resources
- [Stata/Python Integration Blog Series - Chuck Huber](https://blog.stata.com/author/chuber/)
- [Stata-Pandas Crosswalk - Adam Ross Nelson](https://github.com/adamrossnelson/StataQuickReference/blob/master/spcrosswlk.md)
- [Rosetta Stone repos - Adam Ross Nelson](https://github.com/adamrossnelson/rosetta)
- [LOST: Library of Statistical Techniques](https://lost-stats.github.io/)
- [Python notebooks for Causal Inference Mixtape](https://github.com/alexanderthclark/Causal-Inference-Mixtape)
- [Wooldridge datasets for Python](https://pypi.org/project/wooldridge/)

### Stata Official Documentation
- [Stata Documentation Overview](https://www.stata.com/features/documentation/)
- [Resources for Learning Stata](https://www.stata.com/links/resources-for-learning-stata/)
- [Stata Links Page](https://www.stata.com/links/)

### University Resources
- [German Rodriguez Stata Tutorial (Princeton)](https://grodri.github.io/stata/)
- [Oscar Torres-Reyna Panel Data Tutorial (Princeton)](https://www.princeton.edu/~otorres/Panel101.pdf)
- [UCLA OARC Stata Resources](https://stats.oarc.ucla.edu/stata/)
- [Princeton DiD Guide](https://libguides.princeton.edu/stata-did)
- [Python for Economists - Alex Bell (Harvard)](https://scholar.harvard.edu/files/ambell/files/python_for_economists.pdf)

### Job Market and Trends
- [Python vs R vs Stata: 2026 Job Data - Econ-Jobs](https://econ-jobs.com/media/python-vs-r-vs-stata-economist-jobs-2026/)
