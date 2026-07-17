# External Resources for Stata-to-R Translation

Curated catalog of resources for Stata users transitioning to R in quantitative
social science contexts. Each entry includes provenance and quality assessment.

---

## Package-Specific Documentation

### fixest Documentation
- **URL:** https://lrberge.github.io/fixest/
- **Author:** Laurent Berge
- **Quality:** Excellent
- **Key content:** R implementation of high-dimensional FE estimation. Formula syntax:
  `Y ~ X1 + X2 | fe1 + fe2`. Includes `sunab()` for Sun-Abraham DiD, `etable()` for
  publication tables, `iplot()`/`coefplot()` for visualization. Explicitly references
  both Stata reghdfe and pyfixest for cross-language users.
- **Relevance:** High -- primary regression package in DAAF R stack.

### marginaleffects Documentation
- **URL:** https://marginaleffects.com/
- **Author:** Vincent Arel-Bundock
- **Quality:** Excellent
- **Key content:** Direct R equivalent of Stata's `margins`. Core functions:
  `predictions()`, `comparisons()`, `slopes()`, `hypotheses()`. Every documentation
  page has R/Python toggle. Published in JSS (v111, i09).
- **Relevance:** High -- the original package (Python version is a port).

### survey Package Documentation
- **URL:** https://r-survey.r-forge.r-project.org/survey/
- **Author:** Thomas Lumley
- **Quality:** Excellent
- **Key content:** The gold standard for design-based inference. `svydesign()`,
  `svymean()`, `svyglm()`, replicate weights. More comprehensive than both Stata's
  `svy:` and Python's `svy` package.
- **Relevance:** High -- most mature survey analysis implementation across languages.

### rdrobust (R) Documentation
- **URL:** https://rdpackages.github.io/rdrobust/
- **Authors:** Cattaneo, Idrobo, Titiunik
- **Quality:** Excellent
- **Key content:** Identical API across Stata, R, Python. Local polynomial RD.
- **Relevance:** Very High -- mechanical translation from Stata.

---

## Textbooks with Dual-Language Code

### The Effect: An Introduction to Research Design and Causality
- **Author:** Nick Huntington-Klein
- **URL:** https://theeffectbook.net/
- **Quality:** Excellent. All methods chapters include R, Stata, and Python code.
- **Relevance:** High -- trilingual code examples are the gold standard.

### Causal Inference: The Mixtape
- **Author:** Scott Cunningham
- **URL:** https://mixtape.scunning.com/
- **Quality:** Excellent. Official code in R and Stata.
- **Relevance:** High -- canonical causal inference textbook.

### Data Analysis for Business, Economics, and Policy
- **Authors:** Gabor Bekes and Gabor Kezdi
- **URL:** https://gabors-data-analysis.com/
- **Quality:** Excellent. All code freely available in R, Stata, and Python.
- **Relevance:** High -- 47 case studies with parallel implementations.

### Using R for Introductory Econometrics
- **Author:** Florian Heiss
- **URL:** https://www.urfie.net/
- **Quality:** Good. Companion to Wooldridge's Stata-based textbook.
- **Relevance:** High -- bridges every Wooldridge example to R.

---

## General Stata-to-R Guides

### Coding for Economists: Coming from Stata
- **Author:** Arthur Turrell
- **URL:** https://aeturrell.github.io/coding-for-economists/coming-from-stata.html
- **Quality:** Excellent. Actively maintained. Covers both R and Python.

### LOST: Library of Statistical Techniques
- **URL:** https://lost-stats.github.io/
- **Quality:** Good. Multi-language Rosetta Stone for statistical methods.
- **Relevance:** High -- look up any technique in Stata, see R equivalent.

### Oscar Torres-Reyna: Panel Data in R
- **URL:** https://www.princeton.edu/~otorres/Panel101R.pdf
- **Quality:** Good. Classic tutorial bridging Stata xtreg to R plm.

---

## Stata Official Documentation (for Reference)

- **Stata Documentation:** https://www.stata.com/features/documentation/
- **Stata Graph Gallery:** https://www.stata.com/support/faqs/graphics/gph/stata-graphs/

Understanding Stata's documentation helps predict which commands users consider
standard and need R translations for.

---

> **Sources:** All resources accessed and verified 2026-05-13.
