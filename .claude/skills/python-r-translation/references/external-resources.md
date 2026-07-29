# External Resources for Python-to-R Translation

Curated catalog of resources for Python users transitioning to R in quantitative
social science contexts. Each entry includes provenance tracking, quality
assessment, and key takeaways.

Resources are assessed for currency, accuracy, and relevance to the DAAF R stack
(tidyverse, fixest, ggplot2, survey, sf). Entries marked with currency concerns
should be cross-checked against current documentation.

---

## Package-Specific Documentation

### fixest Documentation

- **Author(s):** Laurent Berge
- **URL:** https://lrberge.github.io/fixest/
- **Type:** Documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Complete documentation for R's premier fixed effects regression
  package. Covers OLS, IV, Poisson, negative binomial with multi-way FE, clustered
  SEs, etable, coefplot/iplot, Sun-Abraham DiD. Python users familiar with pyfixest
  will find the API intentionally parallel.
- **For Python users:** The formula syntax is nearly identical to pyfixest. The
  main differences are clustering syntax (`~entity` vs `{"CRV1": "entity"}`) and
  that R fixest's `feglm()` covers more GLM families with FE (e.g., Gamma) plus
  `fenegbin`; pyfixest's `feglm()` supports FE for logit/probit/gaussian since 0.50.

### ggplot2 Documentation

- **Author(s):** Hadley Wickham et al.
- **URL:** https://ggplot2.tidyverse.org/
- **Type:** Documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Definitive reference for the grammar of graphics in R. plotnine
  users will find the function reference organized identically. The main adjustment
  is bare column names vs strings in `aes()`.

### dplyr Documentation

- **URL:** https://dplyr.tidyverse.org/
- **Type:** Documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **For Python users:** Maps directly to polars operations. `mutate()` = `with_columns()`,
  `filter()` = `filter()`, `select()` = `select()`, `summarise()` = `agg()`,
  `left_join()` = `join(how="left")`.

### marginaleffects: Model to Meaning

- **Author(s):** Vincent Arel-Bundock, Noah Greifer, Andrew Heiss
- **URL:** https://marginaleffects.com/
- **Type:** Documentation / Book
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Every page has an R/Python toggle showing equivalent code. The
  gold standard for cross-language post-estimation analysis. Covers predictions,
  comparisons, slopes, and hypothesis testing. Published in JSS (v111, i09).

### rdrobust: RD Packages

- **Author(s):** Calonico, Cattaneo, Titiunik et al.
- **URL:** https://rdpackages.github.io/rdrobust/
- **Type:** Documentation
- **Last verified:** 2026-03-28
- **Quality:** Excellent
- **Key content:** Unified documentation for R, Python, and Stata with identical
  APIs and function names. The translation is nearly mechanical.

### survey Package Documentation

- **URL:** https://cran.r-project.org/package=survey
- **Type:** Documentation
- **Last verified:** 2026-03-28
- **For Python users:** R's `survey` covers substantially more model families than
  `svy`. The formula interface (`~varname`) replaces string arguments.

### sf (r-spatial) Documentation

- **URL:** https://r-spatial.github.io/sf/
- **Type:** Documentation
- **Last verified:** 2026-03-28
- **For Python users:** `st_read()` = `gpd.read_file()`, `st_join()` = `gpd.sjoin()`,
  `st_transform()` = `gdf.to_crs()`. R uses standalone `st_*()` functions where
  Python uses GeoDataFrame methods.

---

## Textbooks with Dual-Language Code

### The Effect: An Introduction to Research Design and Causality

- **Author(s):** Nick Huntington-Klein
- **URL:** https://theeffectbook.net/
- **Quality:** Excellent
- **Key content:** Causal inference textbook with code in R, Stata, and Python.
  The triple-language examples make this the best single resource for seeing how
  the same method is implemented across ecosystems. Free online.

### Using R, Python, and Julia for Introductory Econometrics

- **Author(s):** Florian Heiss, Daniel Brunner
- **URL:** https://www.urfie.net/
- **Quality:** Good
- **Key content:** Parallel implementations of Wooldridge's econometrics examples.
  Every example exists in R, Python, and Julia with identical expected results.

### R for Data Science (2nd Edition)

- **Author(s):** Hadley Wickham, Mine Cetinkaya-Rundel, Garrett Grolemund
- **URL:** https://r4ds.hadley.nz/
- **Quality:** Excellent
- **Key content:** The definitive tidyverse guide. Understanding dplyr patterns
  here maps directly to polars translations. R-only but essential as the "target
  language" reference.

### Causal Inference: The Mixtape

- **Author(s):** Scott Cunningham
- **URL:** https://mixtape.scunning.com/
- **Quality:** Good
- **Key content:** Causal inference with R and Stata code. Accessible writing with
  real-world examples. The Mixtape Sessions workshops (mixtapesessions.io) provide
  Python and Stata implementations.

---

## General Python-to-R Guides

### Coding for Economists: Coming from R

- **Author(s):** Arthur Turrell
- **URL:** https://aeturrell.github.io/coding-for-economists/coming-from-r.html
- **Quality:** Excellent
- **Key content:** While titled "Coming from R," the side-by-side comparisons work
  equally well in reverse. Provides package equivalency tables and code comparisons
  for common operations.

### Polars' Rgonomic Patterns

- **Author(s):** Emily Riederer
- **URL:** https://www.emilyriederer.com/post/py-rgo-polars/
- **Quality:** Excellent
- **Key content:** Deep analysis of how polars mirrors dplyr's ergonomic design.
  Reading this in reverse helps Python users understand why dplyr feels natural
  to R users and what design principles they share.

### Tidy Data Manipulation: dplyr vs polars

- **Author(s):** Christoph Scheuch
- **URL:** https://blog.tidy-intelligence.com/posts/dplyr-vs-polars/
- **Quality:** Good
- **Key content:** Systematic function-by-function comparison. Highlights that
  dplyr allows referencing new columns in the same mutate block while polars
  does not.

---

## R Package Documentation (Target Language References)

| R Package | URL | Python Equivalent |
|-----------|-----|------------------|
| dplyr | https://dplyr.tidyverse.org/ | polars |
| ggplot2 | https://ggplot2.tidyverse.org/ | plotnine |
| fixest | https://lrberge.github.io/fixest/ | pyfixest |
| survey | https://cran.r-project.org/package=survey | svy |
| sf | https://r-spatial.github.io/sf/ | geopandas |
| tidymodels | https://www.tidymodels.org/ | scikit-learn |
| Quarto | https://quarto.org/ | marimo |
| plm | https://cran.r-project.org/package=plm | linearmodels |

---

## Community Resources

| Resource | URL | Notes |
|----------|-----|-------|
| Stack Overflow `[r]` tag | https://stackoverflow.com/questions/tagged/r | Most R questions answered |
| RStudio Community | https://community.rstudio.com/ | Friendly, moderated |
| R-bloggers | https://www.r-bloggers.com/ | Aggregated R tutorials |
| #rstats on social media | Various | Active community |
| CRAN Task Views | https://cran.r-project.org/web/views/ | Package discovery by topic |
