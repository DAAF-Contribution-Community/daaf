# smoke_stata_r_translation.R -- Smoke test for the stata-r-translation skill
# The skill is a text-only mapping document (Stata -> R). This test verifies
# that the R-side TARGETS of every mapping in the skill's Command Mapping
# Overview and Library Versions tables actually exist in this container: each
# mapped package loads, and the key mapped functions are defined after library().
#
# Mapping source: .claude/skills/stata-r-translation/SKILL.md
#   regress/areg/reghdfe/xtreg,fe/ivregress/ppmlhdfe -> fixest
#   xtreg,re / sureg                                 -> plm
#   logit/probit/glm                                 -> stats::glm
#   ologit/nbreg                                      -> MASS
#   mlogit                                            -> nnet
#   margins/marginsplot/lincom/nlcom                  -> marginaleffects
#   esttab/outreg2                                    -> fixest etable + modelsummary
#   test/lincom                                       -> car
#   gen/replace/merge/collapse/reshape                -> dplyr + tidyr
#   graph twoway/bar/box/histogram                    -> ggplot2
#   (interactive charts)                              -> plotly (R)
#   svyset/svy:                                        -> survey
#   rdrobust/rdplot                                   -> rdrobust
#   robust/vce()                                       -> sandwich + lmtest
#   spmap/spregress                                    -> sf + terra
#   teffects/psmatch2 (partial)                        -> tidymodels
#
# On-demand method packages named in the skill's Library Versions table /
# reference-file examples but NOT in DAAF's base R image (binsreg, ivreg,
# augsynth, Synth, MatchIt, WeightIt, did, DIDmultiplegt, rddensity) are
# reported informationally, not asserted. binsreg appears in the skill's
# Library Versions table (unpinned) yet is installed on demand -- its absence
# from the base image is a genuine but expected environment finding, surfaced
# below rather than papered over.

# --- Config ---
library(dplyr)
library(tidyr)
library(fixest)
library(plm)
library(MASS)
library(nnet)
library(marginaleffects)
library(modelsummary)
library(car)
library(ggplot2)
library(plotly)
library(survey)
library(rdrobust)
library(sandwich)
library(lmtest)
library(sf)
library(terra)
library(tidymodels)

cat("=== stata-r-translation Skill Smoke Test ===\n")
cat("Verifying R-side mapping targets exist and key functions are defined.\n\n")

# Helper: named functions must exist as functions after library(). When `ns` is
# supplied, existence is checked inside that package's namespace -- required for
# formula-helpers (e.g. fixest::sunab) exported but not bound globally.
check_fns <- function(label, fns, ns = NULL) {
  for (fn in fns) {
    if (is.null(ns)) {
      ok <- exists(fn, mode = "function")
    } else {
      ok <- exists(fn, where = asNamespace(ns), mode = "function")
    }
    cat(sprintf("  %-24s %s\n", paste0(fn, "()"), if (ok) "OK" else "MISSING"))
    stopifnot(ok)
  }
  cat("  PASS:", label, "\n\n")
}

# --- Test 1: regress/reghdfe/xtreg,fe/ivregress/ppmlhdfe -> fixest ---
cat("Test 1: reghdfe / ivregress / ppmlhdfe -> fixest\n")
check_fns("fixest estimators + reporting present",
          c("feols", "fepois", "feglm", "sunab", "etable", "iplot", "coefplot"),
          ns = "fixest")

# --- Test 2: xtreg,re / sureg -> plm ---
cat("Test 2: xtreg,re / sureg -> plm\n")
check_fns("plm panel estimators present",
          c("plm", "pdata.frame", "phtest", "pFtest"))

# --- Test 3: logit/probit/glm -> stats::glm ---
cat("Test 3: logit / probit / glm -> stats::glm\n")
check_fns("base R GLM present", c("glm", "lm", "binomial", "poisson"))

# --- Test 4: ologit/nbreg -> MASS ---
cat("Test 4: ologit / nbreg -> MASS (polr / glm.nb)\n")
check_fns("MASS ordered logit + neg-binomial present",
          c("polr", "glm.nb"))

# --- Test 5: mlogit -> nnet ---
cat("Test 5: mlogit -> nnet (multinom)\n")
check_fns("nnet multinomial logit present", c("multinom"))

# --- Test 6: margins/marginsplot/lincom/nlcom -> marginaleffects ---
cat("Test 6: margins / lincom / nlcom -> marginaleffects\n")
check_fns("marginaleffects present",
          c("avg_slopes", "avg_comparisons", "predictions", "hypotheses"))

# --- Test 7: esttab/outreg2 -> modelsummary (+ fixest etable) ---
cat("Test 7: esttab / outreg2 -> modelsummary\n")
check_fns("modelsummary table builders present",
          c("modelsummary", "datasummary", "modelplot"))

# --- Test 8: test/lincom -> car ---
cat("Test 8: test / lincom -> car (linearHypothesis / vif)\n")
check_fns("car hypothesis testing present",
          c("linearHypothesis", "vif", "Anova"))

# --- Test 9: gen/replace/merge/collapse/reshape -> dplyr + tidyr ---
cat("Test 9: gen / merge / collapse / reshape -> dplyr + tidyr\n")
check_fns("dplyr/tidyr verbs present",
          c("mutate", "filter", "left_join", "inner_join", "summarise",
            "group_by", "pivot_longer", "pivot_wider", "bind_rows"))

# --- Test 10: graph twoway/bar/box/histogram -> ggplot2 ---
cat("Test 10: graph twoway / bar / histogram -> ggplot2\n")
check_fns("ggplot2 grammar present",
          c("ggplot", "aes", "geom_line", "geom_bar", "geom_histogram", "ggsave"))

# --- Test 11: interactive charts -> plotly (R) ---
cat("Test 11: interactive charts -> plotly (R)\n")
check_fns("plotly R present", c("plot_ly", "ggplotly", "layout"))

# --- Test 12: svyset/svy: -> survey ---
cat("Test 12: svyset / svy: -> survey\n")
check_fns("survey design + estimators present",
          c("svydesign", "svymean", "svyglm", "svyby", "svytotal"))

# --- Test 13: rdrobust/rdplot -> rdrobust ---
cat("Test 13: rdrobust / rdplot -> rdrobust\n")
check_fns("rdrobust present", c("rdrobust", "rdplot", "rdbwselect"))

# --- Test 14: robust/vce() -> sandwich + lmtest ---
cat("Test 14: robust / vce() -> sandwich + lmtest\n")
check_fns("robust/clustered SE machinery present",
          c("vcovHC", "vcovCL", "coeftest"))

# --- Test 15: spmap/spregress -> sf + terra ---
cat("Test 15: spmap / spregress -> sf + terra\n")
check_fns("sf/terra spatial ops present",
          c("st_read", "st_as_sf", "st_transform", "rast", "vect"))

# --- Test 16: teffects/psmatch2 (partial) -> tidymodels ---
cat("Test 16: teffects / psmatch2 (partial) -> tidymodels\n")
check_fns("tidymodels pipeline verbs present",
          c("recipe", "workflow", "vfold_cv", "tune_grid"))

# --- Test 17: functional -- reghdfe -> feols with clustered SEs ---
cat("Test 17: functional -- feols() FE + clustered SEs (reghdfe equivalent)\n")
set.seed(10)
n <- 300
sdat <- data.frame(
  wage = rnorm(n, 10, 2),
  educ = rnorm(n),
  ind = factor(sample(1:6, n, replace = TRUE)),
  state = factor(sample(1:8, n, replace = TRUE))
)
sdat$wage <- sdat$wage + 0.4 * sdat$educ
fit_hd <- feols(wage ~ educ | ind, data = sdat, vcov = ~state)
stopifnot(inherits(fit_hd, "fixest"))
cat("  feols coef(educ) =", round(unname(coef(fit_hd)["educ"]), 4), "\n")
cat("  PASS\n\n")

# --- Test 18: functional -- margins -> marginaleffects::avg_slopes on a logit ---
cat("Test 18: functional -- avg_slopes() on a logit (margins equivalent)\n")
sdat$hi <- as.integer(sdat$wage > median(sdat$wage))
logit_fit <- glm(hi ~ educ, data = sdat, family = binomial)
mfx <- avg_slopes(logit_fit)
stopifnot(is.data.frame(mfx))
stopifnot("estimate" %in% names(mfx))
cat("  avg_slopes(educ) estimate =", round(mfx$estimate[mfx$term == "educ"], 4), "\n")
cat("  PASS\n\n")

# --- Test 19: functional -- esttab -> modelsummary rendering ---
cat("Test 19: functional -- modelsummary() renders a two-model table\n")
m1 <- lm(wage ~ educ, data = sdat)
m2 <- feols(wage ~ educ | ind, data = sdat)
tbl <- modelsummary(list("OLS" = m1, "FE" = m2), output = "markdown")
stopifnot(!is.null(tbl))
cat("  modelsummary produced a table object of class:", class(tbl)[1], "\n")
cat("  PASS\n\n")

# --- Summary ---
cat("=== All 16 mapping groups + 3 functional tests PASSED ===\n")
cat("All R-side targets in stata-r-translation SKILL.md mapping tables verified.\n\n")

# Informational: on-demand method packages in the skill's Library Versions
# table / reference examples that are installed on demand, not in the base image.
cat("Informational -- on-demand packages (skill tables/examples, not base image):\n")
optional <- c("binsreg", "ivreg", "augsynth", "Synth", "MatchIt", "WeightIt",
              "did", "DIDmultiplegt", "rddensity")
for (p in optional) {
  cat(sprintf("  %-14s installed: %s\n", p, requireNamespace(p, quietly = TRUE)))
}
cat("(binsreg is named in the skill Library Versions table but is not in DAAF's\n")
cat(" Dockerfile R manifest -- installed on demand; absence here is expected.)\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-07 15:25:56
# Command: Rscript /daaf/scripts/smoke_tests/smoke_stata_r_translation.R
# Duration: 4s
# Exit code: 0
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
# Attaching package: ‘plm’
# 
# The following objects are masked from ‘package:dplyr’:
# 
#     between, lag, lead
# 
# 
# Attaching package: ‘MASS’
# 
# The following object is masked from ‘package:dplyr’:
# 
#     select
# 
# Loading required package: carData
# 
# Attaching package: ‘car’
# 
# The following object is masked from ‘package:dplyr’:
# 
#     recode
# 
# 
# Attaching package: ‘plotly’
# 
# The following object is masked from ‘package:ggplot2’:
# 
#     last_plot
# 
# The following object is masked from ‘package:MASS’:
# 
#     select
# 
# The following object is masked from ‘package:stats’:
# 
#     filter
# 
# The following object is masked from ‘package:graphics’:
# 
#     layout
# 
# Loading required package: grid
# Loading required package: Matrix
# 
# Attaching package: ‘Matrix’
# 
# The following objects are masked from ‘package:tidyr’:
# 
#     expand, pack, unpack
# 
# Loading required package: survival
# 
# Attaching package: ‘survey’
# 
# The following object is masked from ‘package:graphics’:
# 
#     dotchart
# 
# Loading required package: zoo
# 
# Attaching package: ‘zoo’
# 
# The following objects are masked from ‘package:base’:
# 
#     as.Date, as.Date.numeric
# 
# Linking to GEOS 3.11.1, GDAL 3.6.2, PROJ 9.1.1; sf_use_s2() is TRUE
# terra 1.9.11
# 
# Attaching package: ‘terra’
# 
# The following object is masked from ‘package:zoo’:
# 
#     time<-
# 
# The following object is masked from ‘package:grid’:
# 
#     depth
# 
# The following object is masked from ‘package:MASS’:
# 
#     area
# 
# The following object is masked from ‘package:fixest’:
# 
#     panel
# 
# The following object is masked from ‘package:tidyr’:
# 
#     extract
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
# ✖ plm::between()    masks dplyr::between()
# ✖ dials::buffer()   masks terra::buffer()
# ✖ purrr::discard()  masks scales::discard()
# ✖ Matrix::expand()  masks tidyr::expand()
# ✖ terra::extract()  masks tidyr::extract()
# ✖ plotly::filter()  masks dplyr::filter(), stats::filter()
# ✖ plm::lag()        masks dplyr::lag(), stats::lag()
# ✖ plm::lead()       masks dplyr::lead()
# ✖ Matrix::pack()    masks tidyr::pack()
# ✖ dials::prune()    masks marginaleffects::prune()
# ✖ car::recode()     masks dplyr::recode()
# ✖ plotly::select()  masks MASS::select(), dplyr::select()
# ✖ purrr::some()     masks car::some()
# ✖ recipes::step()   masks stats::step()
# ✖ Matrix::unpack()  masks tidyr::unpack()
# ✖ recipes::update() masks terra::update(), Matrix::update(), stats::update()
# === stata-r-translation Skill Smoke Test ===
# Verifying R-side mapping targets exist and key functions are defined.
# 
# Test 1: reghdfe / ivregress / ppmlhdfe -> fixest
#   feols()                  OK
#   fepois()                 OK
#   feglm()                  OK
#   sunab()                  OK
#   etable()                 OK
#   iplot()                  OK
#   coefplot()               OK
#   PASS: fixest estimators + reporting present 
# 
# Test 2: xtreg,re / sureg -> plm
#   plm()                    OK
#   pdata.frame()            OK
#   phtest()                 OK
#   pFtest()                 OK
#   PASS: plm panel estimators present 
# 
# Test 3: logit / probit / glm -> stats::glm
#   glm()                    OK
#   lm()                     OK
#   binomial()               OK
#   poisson()                OK
#   PASS: base R GLM present 
# 
# Test 4: ologit / nbreg -> MASS (polr / glm.nb)
#   polr()                   OK
#   glm.nb()                 OK
#   PASS: MASS ordered logit + neg-binomial present 
# 
# Test 5: mlogit -> nnet (multinom)
#   multinom()               OK
#   PASS: nnet multinomial logit present 
# 
# Test 6: margins / lincom / nlcom -> marginaleffects
#   avg_slopes()             OK
#   avg_comparisons()        OK
#   predictions()            OK
#   hypotheses()             OK
#   PASS: marginaleffects present 
# 
# Test 7: esttab / outreg2 -> modelsummary
#   modelsummary()           OK
#   datasummary()            OK
#   modelplot()              OK
#   PASS: modelsummary table builders present 
# 
# Test 8: test / lincom -> car (linearHypothesis / vif)
#   linearHypothesis()       OK
#   vif()                    OK
#   Anova()                  OK
#   PASS: car hypothesis testing present 
# 
# Test 9: gen / merge / collapse / reshape -> dplyr + tidyr
#   mutate()                 OK
#   filter()                 OK
#   left_join()              OK
#   inner_join()             OK
#   summarise()              OK
#   group_by()               OK
#   pivot_longer()           OK
#   pivot_wider()            OK
#   bind_rows()              OK
#   PASS: dplyr/tidyr verbs present 
# 
# Test 10: graph twoway / bar / histogram -> ggplot2
#   ggplot()                 OK
#   aes()                    OK
#   geom_line()              OK
#   geom_bar()               OK
#   geom_histogram()         OK
#   ggsave()                 OK
#   PASS: ggplot2 grammar present 
# 
# Test 11: interactive charts -> plotly (R)
#   plot_ly()                OK
#   ggplotly()               OK
#   layout()                 OK
#   PASS: plotly R present 
# 
# Test 12: svyset / svy: -> survey
#   svydesign()              OK
#   svymean()                OK
#   svyglm()                 OK
#   svyby()                  OK
#   svytotal()               OK
#   PASS: survey design + estimators present 
# 
# Test 13: rdrobust / rdplot -> rdrobust
#   rdrobust()               OK
#   rdplot()                 OK
#   rdbwselect()             OK
#   PASS: rdrobust present 
# 
# Test 14: robust / vce() -> sandwich + lmtest
#   vcovHC()                 OK
#   vcovCL()                 OK
#   coeftest()               OK
#   PASS: robust/clustered SE machinery present 
# 
# Test 15: spmap / spregress -> sf + terra
#   st_read()                OK
#   st_as_sf()               OK
#   st_transform()           OK
#   rast()                   OK
#   vect()                   OK
#   PASS: sf/terra spatial ops present 
# 
# Test 16: teffects / psmatch2 (partial) -> tidymodels
#   recipe()                 OK
#   workflow()               OK
#   vfold_cv()               OK
#   tune_grid()              OK
#   PASS: tidymodels pipeline verbs present 
# 
# Test 17: functional -- feols() FE + clustered SEs (reghdfe equivalent)
#   feols coef(educ) = 0.3409 
#   PASS
# 
# Test 18: functional -- avg_slopes() on a logit (margins equivalent)
#   avg_slopes(educ) estimate = 0.0372 
#   PASS
# 
# Test 19: functional -- modelsummary() renders a two-model table
#   modelsummary produced a table object of class: tinytable 
#   PASS
# 
# === All 16 mapping groups + 3 functional tests PASSED ===
# All R-side targets in stata-r-translation SKILL.md mapping tables verified.
# 
# Informational -- on-demand packages (skill tables/examples, not base image):
#   binsreg        installed: FALSE
#   ivreg          installed: FALSE
#   augsynth       installed: FALSE
#   Synth          installed: FALSE
#   MatchIt        installed: FALSE
#   WeightIt       installed: FALSE
#   did            installed: FALSE
#   DIDmultiplegt  installed: FALSE
#   rddensity      installed: FALSE
# (binsreg is named in the skill Library Versions table but is not in DAAF's
#  Dockerfile R manifest -- installed on demand; absence here is expected.)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
