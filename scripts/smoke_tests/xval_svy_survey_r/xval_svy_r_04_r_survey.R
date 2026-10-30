# scripts/scratch/xval_svy_r_04_r_survey.R
# INTENT: produce the R survey (Lumley) reference outputs for the cross-validation, on the
#   IDENTICAL parquet frame written by xval_svy_r_03_py_svy.py, under a design matched to svy's.
# REASONING: R survey 4.5 is the field's reference implementation. Matching data + design isolates
#   any svy-vs-R difference to the estimator/convention, not the inputs. marginaleffects (0.32.0)
#   is present, so avg_slopes() is the preferred AME comparator (task-preferred).
# ASSUMES: design parity with svy -> svydesign(ids=~psu, strata=~stratum, weights=~weight,
#   nest=TRUE), no FPC (svy side used no pop_size), Taylor variance (survey default). gender is a
#   character column -> factor with reference "Female" (alphabetical), matching svy's gender_Male.

# --- Config ---
library(survey)
library(arrow)
library(marginaleffects)
library(broom)
library(dplyr)

SCRATCH <- "/daaf/scripts/scratch"
FRAME_PATH <- file.path(SCRATCH, "xval_svy_r_frame.parquet")

cat("R", as.character(getRversion()), "| survey", as.character(packageVersion("survey")),
    "| marginaleffects", as.character(packageVersion("marginaleffects")), "\n")

# --- Load shared frame ---
df <- as.data.frame(read_parquet(FRAME_PATH))
cat("Loaded frame:", nrow(df), "x", ncol(df), "\n")
df$gender <- factor(df$gender)  # reference = "Female" (alphabetical), matches svy gender_Male
cat("gender levels:", paste(levels(df$gender), collapse = ", "), "(ref =", levels(df$gender)[1], ")\n")

# --- Design (Taylor, no FPC, nested) ---
des <- svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, data = df, nest = TRUE)
cat("Design df (degf) =", degf(des), "(= #PSU - #strata = 24 - 4)\n\n")

# --- Gap 1a: logistic (quasibinomial) ---
# INTENT: matches svy binomial GLM; quasibinomial avoids non-integer-success warnings on weighted data.
logit <- svyglm(employed ~ age + gender, design = des, family = quasibinomial())
logit_t <- broom::tidy(logit)
logit_t$param <- ifelse(grepl("Intercept", logit_t$term), "intercept",
                 ifelse(logit_t$term == "age", "age",
                 ifelse(grepl("gender", logit_t$term), "gender_Male", logit_t$term)))
logit_t$df <- logit$df.residual  # residual df svyglm reports
logit_out <- logit_t[, c("param", "estimate", "std.error", "statistic", "p.value", "df")]
names(logit_out) <- c("param", "estimate", "std_err", "statistic", "p_value", "df")
write_parquet(as_arrow_table(logit_out), file.path(SCRATCH, "xval_svy_r_r_logit.parquet"))
cat("R logistic (quasibinomial) coef:\n"); print(logit_out)
cat("  logit$df.residual =", logit$df.residual, "\n\n")

# --- Gap 1b: Poisson (quasipoisson) ---
pois <- svyglm(visit_count ~ age + gender, design = des, family = quasipoisson())
pois_t <- broom::tidy(pois)
pois_t$param <- ifelse(grepl("Intercept", pois_t$term), "intercept",
                ifelse(pois_t$term == "age", "age",
                ifelse(grepl("gender", pois_t$term), "gender_Male", pois_t$term)))
pois_t$df <- pois$df.residual
pois_out <- pois_t[, c("param", "estimate", "std.error", "statistic", "p.value", "df")]
names(pois_out) <- c("param", "estimate", "std_err", "statistic", "p_value", "df")
write_parquet(as_arrow_table(pois_out), file.path(SCRATCH, "xval_svy_r_r_pois.parquet"))
cat("R Poisson (quasipoisson) coef:\n"); print(pois_out)
cat("\n")

# --- Gap 2: marginal effects via marginaleffects::avg_slopes on the svyglm ---
# INTENT: preferred AME comparator; avg_slopes averages the marginal effect over the sample,
#   using the design-based vcov from svyglm.
ame <- avg_slopes(logit)
ame_df <- as.data.frame(ame)
cat("R avg_slopes() raw columns:", paste(names(ame_df), collapse = ", "), "\n")
ame_df$param <- ifelse(ame_df$term == "age", "age",
                ifelse(ame_df$term == "gender", "gender_contrast", ame_df$term))
ame_keep <- ame_df[, c("param", "term", "estimate", "std.error", "conf.low", "conf.high")]
names(ame_keep) <- c("param", "term", "margin", "se", "lci", "uci")
write_parquet(as_arrow_table(ame_keep), file.path(SCRATCH, "xval_svy_r_r_margins.parquet"))
cat("R avg_slopes() AME:\n"); print(ame_keep)
cat("\n")

# --- Gap 3: two-way cell proportions + svychisq (Rao-Scott F and Chisq) ---
# INTENT: cell proportions with design-based SE via svymean on the interaction, matching svy's
#   two-way tabulate proportions; independence test via svychisq (default F + explicit Chisq).
df$empf <- factor(df$employed)
des2 <- svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, data = df, nest = TRUE)
cellmean <- svymean(~interaction(gender, empf), des2)
cell_df <- data.frame(
  cell = names(coef(cellmean)),
  est = as.numeric(coef(cellmean)),
  se = as.numeric(SE(cellmean))
)
# interaction() names look like "interaction(gender, empf)Female.0" -> parse gender + employed
cell_df$gender <- ifelse(grepl("Female", cell_df$cell), "Female", "Male")
cell_df$employed <- ifelse(grepl("\\.1$", cell_df$cell), "1", "0")
cell_out <- cell_df[, c("gender", "employed", "est", "se")]
write_parquet(as_arrow_table(cell_out), file.path(SCRATCH, "xval_svy_r_r_twoway.parquet"))
cat("R two-way cell proportions (svymean on interaction):\n"); print(cell_out)

cs_F <- svychisq(~gender + empf, des2, statistic = "F")
cs_C <- svychisq(~gender + empf, des2, statistic = "Chisq")
cat("\nR svychisq statistic='F':\n"); print(cs_F)
cat("R svychisq statistic='Chisq':\n"); print(cs_C)
chisq_out <- data.frame(
  r_F_value = as.numeric(cs_F$statistic),
  r_F_ndf = as.numeric(cs_F$parameter["ndf"]),
  r_F_ddf = as.numeric(cs_F$parameter["ddf"]),
  r_F_p = as.numeric(cs_F$p.value),
  r_Chisq_value = as.numeric(cs_C$statistic),
  r_Chisq_p = as.numeric(cs_C$p.value)
)
write_parquet(as_arrow_table(chisq_out), file.path(SCRATCH, "xval_svy_r_r_chisq.parquet"))
cat("\nR chisq summary row:\n"); print(chisq_out)
cat("\n")

# --- Bonus: domain mean income by stratum + CI half-width (issue #3) ---
# INTENT: svyby domain means; confint() two ways -- default (normal z) and with design df (t) --
#   to diagnose which multiplier svy's domain CI half-width matches.
dom <- svyby(~income, ~stratum, des, svymean)
ci_z <- confint(dom)                       # default: normal quantile (z = 1.96)
ci_t <- confint(dom, df = degf(des))       # t quantile on design df
dom_out <- data.frame(
  stratum = as.character(dom$stratum),
  est = as.numeric(dom$income),
  se = as.numeric(SE(dom)),
  hw_z = (ci_z[, 2] - ci_z[, 1]) / 2,
  hw_t = (ci_t[, 2] - ci_t[, 1]) / 2
)
write_parquet(as_arrow_table(dom_out), file.path(SCRATCH, "xval_svy_r_r_domain.parquet"))
cat("R domain mean income by stratum (half-widths z vs t):\n"); print(dom_out)
cat("  degf(des) =", degf(des), "; z mult = 1.96, t mult =", qt(0.975, degf(des)), "\n\n")

cat("=== R side complete; all reference parquets written ===\n")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 11:54:13
# Command: Rscript /daaf/scripts/scratch/xval_svy_r_04_r_survey.R
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# Loading required package: grid
# Loading required package: Matrix
# Loading required package: survival
# 
# Attaching package: 'survey'
# 
# The following object is masked from 'package:graphics':
# 
#     dotchart
# 
# 
# Attaching package: 'arrow'
# 
# The following object is masked from 'package:utils':
# 
#     timestamp
# 
# 
# Attaching package: 'dplyr'
# 
# The following objects are masked from 'package:stats':
# 
#     filter, lag
# 
# The following objects are masked from 'package:base':
# 
#     intersect, setdiff, setequal, union
# 
# R 4.5.3 | survey 4.5 | marginaleffects 0.32.0 
# Loaded frame: 480 x 8 
# gender levels: Female, Male (ref = Female )
# Design df (degf) = 20 (= #PSU - #strata = 24 - 4)
# 
# R logistic (quasibinomial) coef:
# # A tibble: 3 x 6
#   param       estimate std_err statistic p_value    df
#   <chr>          <dbl>   <dbl>     <dbl>   <dbl> <dbl>
# 1 intercept    -0.552  0.248       -2.22 0.0393     18
# 2 age           0.0107 0.00395      2.70 0.0146     18
# 3 gender_Male   0.632  0.211        3.00 0.00777    18
#   logit$df.residual = 18 
# 
# R Poisson (quasipoisson) coef:
# # A tibble: 3 x 6
#   param       estimate std_err statistic p_value    df
#   <chr>          <dbl>   <dbl>     <dbl>   <dbl> <dbl>
# 1 intercept   0.415    0.130       3.19  0.00507    18
# 2 age         0.000838 0.00230     0.364 0.720      18
# 3 gender_Male 0.0841   0.0620      1.36  0.192      18
# 
# Warning message:
# With models of this class, it is normally good practice to specify weights using the `wts` argument. Otherwise, weights will be ignored in the computation of quantities of interest. 
# R avg_slopes() raw columns: term, contrast, estimate, std.error, statistic, p.value, s.value, conf.low, conf.high 
# R avg_slopes() AME:
#             param   term      margin           se          lci         uci
# 1             age    age 0.002531868 0.0009303313 0.0007084519 0.004355284
# 2 gender_contrast gender 0.152373463 0.0504906026 0.0534137003 0.251333225
# 
# R two-way cell proportions (svymean on interaction):
#   gender employed       est         se
# 1 Female        0 0.2573855 0.02311327
# 2   Male        0 0.1744069 0.01312595
# 3 Female        1 0.2505987 0.01961413
# 4   Male        1 0.3176088 0.02269603
# 
# R svychisq statistic='F':
# 
# 	Pearson's X^2: Rao & Scott adjustment
# 
# data:  svychisq(~gender + empf, des2, statistic = "F")
# F = 9.0067, ndf = 1, ddf = 20, p-value = 0.007058
# 
# R svychisq statistic='Chisq':
# 
# 	Pearson's X^2: Rao & Scott adjustment
# 
# data:  svychisq(~gender + empf, des2, statistic = "Chisq")
# X-squared = 11.328, df = 1, p-value = 0.00269
# 
# 
# R chisq summary row:
#   r_F_value r_F_ndf r_F_ddf       r_F_p r_Chisq_value   r_Chisq_p
# 1  9.006655       1      20 0.007058258      11.32795 0.002689983
# 
# R domain mean income by stratum (half-widths z vs t):
#   stratum      est       se      hw_z      hw_t
# 1       1 30470.31 236.2896  463.1191  492.8914
# 2       2 30510.23 565.3253 1108.0172 1179.2479
# 3       3 31336.97 513.0584 1005.5760 1070.2210
# 4       4 32287.86 672.3051 1317.6938 1402.4039
#   degf(des) = 20 ; z mult = 1.96, t mult = 2.085963 
# 
# === R side complete; all reference parquets written ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
