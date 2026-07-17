# smoke_python_r_translation.R -- Smoke test for the python-r-translation skill
# The skill is a text-only mapping document (Python -> R). This test verifies
# that the R-side TARGETS of every mapping in the skill's Package Mapping
# Overview and Library Versions tables actually exist in this container: each
# mapped package loads, and the key mapped functions are defined after library().
#
# Mapping source: .claude/skills/python-r-translation/SKILL.md
#   polars           -> dplyr + tidyr + data.table
#   plotnine         -> ggplot2
#   plotly (Python)  -> plotly (R)
#   pyfixest         -> fixest
#   statsmodels      -> base R stats + lmtest + sandwich
#   linearmodels     -> plm + lme4 + estimatr
#   scikit-learn     -> tidymodels
#   geopandas        -> sf + terra
#   svy              -> survey (Lumley)
#   marginaleffects  -> marginaleffects (R)
#   rdrobust         -> rdrobust (R)
#
# On-demand method packages named only in the skill's reference-file examples
# (caret, ivreg, did, did2s, augsynth, MatchIt, rddensity, umap, Rtsne) are NOT
# part of DAAF's base R image (see Dockerfile R install manifest) and are
# reported informationally, not asserted -- their absence is expected.

# --- Config ---
library(dplyr)
library(tidyr)
library(data.table)
library(fixest)
library(ggplot2)
library(plotly)
library(lmtest)
library(sandwich)
library(plm)
library(lme4)
library(estimatr)
library(tidymodels)
library(sf)
library(terra)
library(survey)
library(marginaleffects)
library(rdrobust)

cat("=== python-r-translation Skill Smoke Test ===\n")
cat("Verifying R-side mapping targets exist and key functions are defined.\n\n")

# Helper expectation: named function must exist and be a function after library()
check_fns <- function(label, fns) {
  for (fn in fns) {
    ok <- exists(fn, mode = "function")
    cat(sprintf("  %-22s %s\n", paste0(fn, "()"), if (ok) "OK" else "MISSING"))
    stopifnot(ok)
  }
  cat("  PASS:", label, "\n\n")
}

# --- Test 1: polars -> dplyr + tidyr + data.table ---
cat("Test 1: polars -> dplyr + tidyr + data.table\n")
check_fns("dplyr/tidyr/data.table verbs present",
          c("filter", "mutate", "summarise", "group_by", "left_join",
            "pivot_longer", "pivot_wider", "data.table"))

# --- Test 2: plotnine -> ggplot2 ---
cat("Test 2: plotnine -> ggplot2\n")
check_fns("ggplot2 grammar present",
          c("ggplot", "aes", "geom_point", "facet_wrap", "ggsave"))

# --- Test 3: plotly (Python) -> plotly (R) ---
cat("Test 3: plotly (Python) -> plotly (R)\n")
check_fns("plotly R present", c("plot_ly", "ggplotly", "layout"))

# --- Test 4: pyfixest -> fixest ---
cat("Test 4: pyfixest -> fixest (feols / sunab / etable / iplot)\n")
check_fns("fixest FE/DiD/reporting present",
          c("feols", "fepois", "feglm", "sunab", "etable", "iplot", "coefplot"))

# --- Test 5: statsmodels -> base R stats + lmtest + sandwich ---
cat("Test 5: statsmodels -> stats + lmtest + sandwich\n")
check_fns("OLS/GLM + robust SE machinery present",
          c("lm", "glm", "coeftest", "vcovHC", "bptest"))

# --- Test 6: linearmodels -> plm + lme4 + estimatr ---
cat("Test 6: linearmodels -> plm + lme4 + estimatr\n")
check_fns("panel / mixed / robust OLS present",
          c("plm", "pdata.frame", "lmer", "lm_robust"))

# --- Test 7: scikit-learn -> tidymodels ---
cat("Test 7: scikit-learn -> tidymodels\n")
check_fns("tidymodels pipeline verbs present",
          c("recipe", "workflow", "rand_forest", "vfold_cv", "tune_grid"))

# --- Test 8: geopandas -> sf + terra ---
cat("Test 8: geopandas -> sf + terra\n")
check_fns("sf/terra spatial ops present",
          c("st_read", "st_join", "st_transform", "st_as_sf", "rast", "vect"))

# --- Test 9: svy -> survey (Lumley) ---
cat("Test 9: svy -> survey (svydesign / svymean / svyglm)\n")
check_fns("survey design + estimators present",
          c("svydesign", "svymean", "svyglm", "svyby"))

# --- Test 10: marginaleffects (Python) -> marginaleffects (R) ---
cat("Test 10: marginaleffects -> marginaleffects (avg_slopes)\n")
check_fns("marginaleffects present",
          c("avg_slopes", "avg_comparisons", "predictions", "slopes"))

# --- Test 11: rdrobust (Python) -> rdrobust (R) ---
cat("Test 11: rdrobust -> rdrobust\n")
check_fns("rdrobust present", c("rdrobust", "rdplot", "rdbwselect"))

# --- Test 12: functional call -- fixest::feols on toy data ---
cat("Test 12: functional -- feols() fit on toy data\n")
set.seed(1)
toy <- data.frame(y = rnorm(200), x = rnorm(200),
                  g = factor(sample(1:5, 200, replace = TRUE)))
fit_fe <- feols(y ~ x | g, data = toy)
stopifnot(inherits(fit_fe, "fixest"))
stopifnot(is.numeric(coef(fit_fe)["x"]))
cat("  feols coef(x) =", round(unname(coef(fit_fe)["x"]), 4), "\n")
cat("  PASS\n\n")

# --- Test 13: functional call -- marginaleffects::avg_slopes on toy lm ---
cat("Test 13: functional -- avg_slopes() on toy lm()\n")
lm_toy <- lm(y ~ x, data = toy)
sl <- avg_slopes(lm_toy)
stopifnot(is.data.frame(sl))
stopifnot("estimate" %in% names(sl))
cat("  avg_slopes estimate =", round(sl$estimate[1], 4), "\n")
cat("  PASS\n\n")

# --- Test 14: functional call -- survey::svyglm on toy design ---
cat("Test 14: functional -- svyglm() on toy survey design\n")
svy_toy <- toy
svy_toy$w <- runif(nrow(svy_toy), 0.5, 2)
des <- svydesign(ids = ~1, weights = ~w, data = svy_toy)
svy_fit <- svyglm(y ~ x, design = des)
stopifnot(inherits(svy_fit, "svyglm"))
cat("  svyglm coef(x) =", round(unname(coef(svy_fit)["x"]), 4), "\n")
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 14 mapping-target tests PASSED ===\n")
cat("All R-side targets in python-r-translation SKILL.md mapping tables verified.\n\n")

# Informational: on-demand method packages named only in reference-file examples.
cat("Informational -- on-demand packages (reference examples, not base image):\n")
optional <- c("caret", "ivreg", "did", "did2s", "augsynth", "MatchIt",
              "rddensity", "umap", "Rtsne")
for (p in optional) {
  cat(sprintf("  %-12s installed: %s\n", p, requireNamespace(p, quietly = TRUE)))
}
cat("(Absence expected -- these are installed on demand per the skill's reference files.)\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 15:22:58
# Command: Rscript /daaf/scripts/smoke_tests/smoke_python_r_translation.R
# Duration: 3s
# Exit code: 1
#
# --- STDOUT ---
# 
# Attaching package: ‘dplyr’
# 
# The following objects are masked from ‘package:stats’:
# 
#     filter, lag
# 
# The following objects are masked from ‘package:base’:
# 
#     intersect, setdiff, setequal, union
# 
# 
# Attaching package: ‘data.table’
# 
# The following objects are masked from ‘package:dplyr’:
# 
#     between, first, last
# 
# 
# Attaching package: ‘plotly’
# 
# The following object is masked from ‘package:ggplot2’:
# 
#     last_plot
# 
# The following object is masked from ‘package:stats’:
# 
#     filter
# 
# The following object is masked from ‘package:graphics’:
# 
#     layout
# 
# Loading required package: zoo
# 
# Attaching package: ‘zoo’
# 
# The following objects are masked from ‘package:data.table’:
# 
#     yearmon, yearqtr
# 
# The following objects are masked from ‘package:base’:
# 
#     as.Date, as.Date.numeric
# 
# 
# Attaching package: ‘plm’
# 
# The following object is masked from ‘package:data.table’:
# 
#     between
# 
# The following objects are masked from ‘package:dplyr’:
# 
#     between, lag, lead
# 
# Loading required package: Matrix
# 
# Attaching package: ‘Matrix’
# 
# The following objects are masked from ‘package:tidyr’:
# 
#     expand, pack, unpack
# 
# ── Attaching packages ────────────────────────────────────── tidymodels 1.4.1 ──
# ✔ broom        1.0.12     ✔ rsample      1.3.2 
# ✔ dials        1.4.3      ✔ tailor       0.1.0 
# ✔ infer        1.1.0      ✔ tune         2.0.1 
# ✔ modeldata    1.5.1      ✔ workflows    1.3.0 
# ✔ parsnip      1.5.0      ✔ workflowsets 1.1.1 
# ✔ purrr        1.2.2      ✔ yardstick    1.4.0 
# ✔ recipes      1.3.2      
# ── Conflicts ───────────────────────────────────────── tidymodels_conflicts() ──
# ✖ plm::between()      masks data.table::between(), dplyr::between()
# ✖ purrr::discard()    masks scales::discard()
# ✖ Matrix::expand()    masks tidyr::expand()
# ✖ plotly::filter()    masks dplyr::filter(), stats::filter()
# ✖ data.table::first() masks dplyr::first()
# ✖ plm::lag()          masks dplyr::lag(), stats::lag()
# ✖ data.table::last()  masks dplyr::last()
# ✖ plm::lead()         masks dplyr::lead()
# ✖ Matrix::pack()      masks tidyr::pack()
# ✖ recipes::step()     masks stats::step()
# ✖ purrr::transpose()  masks data.table::transpose()
# ✖ Matrix::unpack()    masks tidyr::unpack()
# ✖ recipes::update()   masks Matrix::update(), stats::update()
# Linking to GEOS 3.11.1, GDAL 3.6.2, PROJ 9.1.1; sf_use_s2() is TRUE
# terra 1.9.11
# 
# Attaching package: ‘terra’
# 
# The following object is masked from ‘package:dials’:
# 
#     buffer
# 
# The following object is masked from ‘package:scales’:
# 
#     rescale
# 
# The following object is masked from ‘package:zoo’:
# 
#     time<-
# 
# The following object is masked from ‘package:fixest’:
# 
#     panel
# 
# The following object is masked from ‘package:data.table’:
# 
#     shift
# 
# The following object is masked from ‘package:tidyr’:
# 
#     extract
# 
# Loading required package: grid
# 
# Attaching package: ‘grid’
# 
# The following object is masked from ‘package:terra’:
# 
#     depth
# 
# Loading required package: survival
# 
# Attaching package: ‘survey’
# 
# The following object is masked from ‘package:graphics’:
# 
#     dotchart
# 
# 
# Attaching package: ‘marginaleffects’
# 
# The following object is masked from ‘package:dials’:
# 
#     prune
# 
# The following object is masked from ‘package:lme4’:
# 
#     refit
# 
# === python-r-translation Skill Smoke Test ===
# Verifying R-side mapping targets exist and key functions are defined.
# 
# Test 1: polars -> dplyr + tidyr + data.table
#   filter()               OK
#   mutate()               OK
#   summarise()            OK
#   group_by()             OK
#   left_join()            OK
#   pivot_longer()         OK
#   pivot_wider()          OK
#   data.table()           OK
#   PASS: dplyr/tidyr/data.table verbs present 
# 
# Test 2: plotnine -> ggplot2
#   ggplot()               OK
#   aes()                  OK
#   geom_point()           OK
#   facet_wrap()           OK
#   ggsave()               OK
#   PASS: ggplot2 grammar present 
# 
# Test 3: plotly (Python) -> plotly (R)
#   plot_ly()              OK
#   ggplotly()             OK
#   layout()               OK
#   PASS: plotly R present 
# 
# Test 4: pyfixest -> fixest (feols / sunab / etable / iplot)
#   feols()                OK
#   fepois()               OK
#   feglm()                OK
#   sunab()                MISSING
# Error in check_fns("fixest FE/DiD/reporting present", c("feols", "fepois",  : 
#   ok is not TRUE
# Calls: check_fns -> stopifnot
# Execution halted
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
