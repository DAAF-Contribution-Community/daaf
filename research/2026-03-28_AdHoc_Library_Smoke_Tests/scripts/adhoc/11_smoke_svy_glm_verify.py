#!/usr/bin/env python3
"""Focused GLM result extraction verification for svy 0.13.0.

Systematically probes the ACTUAL API for:
  1. glm = sample.glm.fit(...) — what is returned? what attributes?
  2. glm.coefs — type, attributes, per-coefficient access
  3. glm.fitted — type, attributes, to_polars() column names
  4. glm.stats — type, attributes (aic, bic, etc.)
  5. to_polars() on every object that might have it — actual column names
  6. glm.predict() — signature, return type, residuals, yhat, to_polars()
  7. AIC/BIC access patterns

Uses synthetic survey data with known structure.
"""

import traceback
import numpy as np
import polars as pl
import svy

# --- Synthetic survey data ---
np.random.seed(42)
n = 500

strata = np.repeat(np.arange(1, 11), n // 10)
psus = np.tile(np.repeat([1, 2], n // 20), 10)
weights = np.random.uniform(500, 5000, size=n)

x1 = np.random.normal(50, 10, size=n)
x2 = np.random.normal(100, 25, size=n)
y_cont = 10 + 0.5 * x1 + 0.3 * x2 + np.random.normal(0, 5, size=n)
y_binary = (y_cont > np.median(y_cont)).astype(int)
cat_var = np.random.choice(["A", "B", "C"], size=n)

data = pl.DataFrame({
    "stratum": strata,
    "psu": psus,
    "weight": weights,
    "x1": x1,
    "x2": x2,
    "y_cont": y_cont,
    "y_binary": y_binary,
    "cat_var": cat_var,
})

design = svy.Design(stratum="stratum", psu="psu", wgt="weight")
sample = svy.Sample(data=data, design=design)

print("=" * 70)
print("SVY 0.13.0 GLM RESULT EXTRACTION — DEEP API VERIFICATION")
print("=" * 70)
print(f"Data shape: {data.shape}")
print()

# =============================================================================
# SECTION 1: What does sample.glm.fit() return?
# =============================================================================
print("=" * 70)
print("SECTION 1: Return type of sample.glm.fit()")
print("=" * 70)

glm = sample.glm.fit(y="y_cont", x=["x1", "x2"], family="gaussian")
print(f"type(glm): {type(glm)}")
print(f"repr(glm): {repr(glm)[:200]}")

# INTENT: Get all non-dunder attributes to understand the object shape
glm_attrs = [a for a in dir(glm) if not a.startswith("_")]
print(f"Non-dunder attributes of glm: {glm_attrs}")
print()

# =============================================================================
# SECTION 2: glm.fitted — the GLMFit object
# =============================================================================
print("=" * 70)
print("SECTION 2: glm.fitted (GLMFit object)")
print("=" * 70)

try:
    fit = glm.fitted
    print(f"type(glm.fitted): {type(fit)}")
    fit_attrs = [a for a in dir(fit) if not a.startswith("_")]
    print(f"Non-dunder attributes of fitted: {fit_attrs}")
    print()
except AttributeError as e:
    print(f"glm.fitted DOES NOT EXIST: {e}")
    # INTENT: Try alternatives
    for alt in ["result", "results", "fit", "model", "summary"]:
        if hasattr(glm, alt):
            print(f"  Found alternative: glm.{alt} -> {type(getattr(glm, alt))}")
    print()

# =============================================================================
# SECTION 3: glm.coefs — coefficient access directly on glm
# =============================================================================
print("=" * 70)
print("SECTION 3: glm.coefs (direct on glm object)")
print("=" * 70)

try:
    coefs_direct = glm.coefs
    print(f"type(glm.coefs): {type(coefs_direct)}")
    print(f"repr: {repr(coefs_direct)[:300]}")
    if hasattr(coefs_direct, '__len__'):
        print(f"len(glm.coefs): {len(coefs_direct)}")
    coefs_attrs = [a for a in dir(coefs_direct) if not a.startswith("_")]
    print(f"Attributes: {coefs_attrs}")
except AttributeError:
    print("glm.coefs DOES NOT EXIST on glm directly")

# INTENT: Also try on glm.fitted if it exists
try:
    fit = glm.fitted
    if hasattr(fit, 'coefs'):
        coefs = fit.coefs
        print(f"\ntype(glm.fitted.coefs): {type(coefs)}")
        if hasattr(coefs, '__len__'):
            print(f"len: {len(coefs)}")
        if hasattr(coefs, '__iter__'):
            for i, c in enumerate(coefs):
                print(f"\n  Coef [{i}]:")
                print(f"    type: {type(c)}")
                c_attrs = [a for a in dir(c) if not a.startswith("_")]
                print(f"    attributes: {c_attrs}")
                # INTENT: Try every plausible attribute name for each coefficient
                for attr_name in ["term", "name", "variable", "est", "estimate",
                                  "se", "std_err", "lci", "uci", "conf_low",
                                  "conf_high", "wald", "statistic", "t_stat",
                                  "p_value", "pvalue", "df"]:
                    if hasattr(c, attr_name):
                        val = getattr(c, attr_name)
                        print(f"    c.{attr_name} = {val} (type: {type(val).__name__})")
                # Only show first 2 coefficients in detail
                if i >= 1:
                    print(f"  ... ({len(coefs)} total coefficients)")
                    break
except Exception as e:
    print(f"Error accessing glm.fitted.coefs: {e}")
print()

# =============================================================================
# SECTION 4: glm.stats — model statistics
# =============================================================================
print("=" * 70)
print("SECTION 4: glm.stats (model statistics)")
print("=" * 70)

# INTENT: Try stats on glm directly
try:
    stats_direct = glm.stats
    print(f"type(glm.stats): {type(stats_direct)}")
    stats_attrs = [a for a in dir(stats_direct) if not a.startswith("_")]
    print(f"Attributes: {stats_attrs}")
    for attr_name in ["n", "r_squared", "rsquared", "aic", "bic", "deviance",
                      "df", "df_resid", "df_model", "nobs", "sigma"]:
        if hasattr(stats_direct, attr_name):
            val = getattr(stats_direct, attr_name)
            print(f"  glm.stats.{attr_name} = {val} (type: {type(val).__name__})")
except AttributeError:
    print("glm.stats DOES NOT EXIST on glm directly")

# INTENT: Try stats on glm.fitted
try:
    fit = glm.fitted
    if hasattr(fit, 'stats'):
        stats = fit.stats
        print(f"\ntype(glm.fitted.stats): {type(stats)}")
        stats_attrs = [a for a in dir(stats) if not a.startswith("_")]
        print(f"Attributes: {stats_attrs}")
        for attr_name in ["n", "r_squared", "rsquared", "aic", "bic", "deviance",
                          "df", "df_resid", "df_model", "nobs", "sigma"]:
            if hasattr(stats, attr_name):
                val = getattr(stats, attr_name)
                print(f"  fit.stats.{attr_name} = {val} (type: {type(val).__name__})")
except Exception as e:
    print(f"Error accessing glm.fitted.stats: {e}")
print()

# =============================================================================
# SECTION 5: to_polars() on every object that might have it
# =============================================================================
print("=" * 70)
print("SECTION 5: to_polars() on every candidate object")
print("=" * 70)

# INTENT: Systematically find which objects have to_polars() and what columns result
candidates = {
    "glm": glm,
}
try:
    candidates["glm.fitted"] = glm.fitted
except:
    pass

for name, obj in candidates.items():
    if hasattr(obj, 'to_polars'):
        try:
            df_result = obj.to_polars()
            print(f"\n{name}.to_polars():")
            print(f"  type: {type(df_result)}")
            print(f"  columns: {df_result.columns}")
            print(f"  dtypes: {df_result.dtypes}")
            print(f"  shape: {df_result.shape}")
            print(f"  first 3 rows:\n{df_result.head(3)}")
        except Exception as e:
            print(f"\n{name}.to_polars() EXISTS but FAILED: {e}")
    else:
        print(f"\n{name} does NOT have to_polars()")

# INTENT: Also check if coefs objects individually have to_polars()
try:
    fit = glm.fitted
    if hasattr(fit, 'coefs') and hasattr(fit.coefs, '__iter__'):
        first_coef = list(fit.coefs)[0]
        if hasattr(first_coef, 'to_polars'):
            print(f"\nIndividual GLMCoef has to_polars(): YES")
            try:
                coef_df = first_coef.to_polars()
                print(f"  columns: {coef_df.columns}")
                print(f"  data:\n{coef_df}")
            except Exception as e:
                print(f"  but it FAILED: {e}")
        else:
            print(f"\nIndividual GLMCoef has to_polars(): NO")
except Exception as e:
    print(f"Error checking coef to_polars: {e}")
print()

# =============================================================================
# SECTION 6: glm.predict() — signature and return structure
# =============================================================================
print("=" * 70)
print("SECTION 6: glm.predict() — signatures and return object")
print("=" * 70)

# INTENT: Test predict with various argument combinations

# Test 6a: predict(new_data=data) — without y_col
print("\n--- 6a: glm.predict(new_data=data) ---")
try:
    pred = glm.predict(new_data=data)
    print(f"type(pred): {type(pred)}")
    pred_attrs = [a for a in dir(pred) if not a.startswith("_")]
    print(f"Attributes: {pred_attrs}")

    for attr_name in ["yhat", "fitted", "values", "se", "std_err",
                      "residuals", "resid", "lci", "uci", "conf_low",
                      "conf_high", "linear_predictor"]:
        if hasattr(pred, attr_name):
            val = getattr(pred, attr_name)
            vtype = type(val).__name__
            vlen = len(val) if hasattr(val, '__len__') else "N/A"
            if val is None:
                print(f"  pred.{attr_name} = None")
            else:
                print(f"  pred.{attr_name}: type={vtype}, len={vlen}")
                if hasattr(val, '__getitem__') and vlen != "N/A" and vlen > 0:
                    print(f"    first 3 values: {val[:3]}")
except Exception as e:
    print(f"FAILED: {e}")
    traceback.print_exc()

# Test 6b: predict(new_data=data, y_col="y_cont") — with y_col for residuals
print("\n--- 6b: glm.predict(new_data=data, y_col='y_cont') ---")
try:
    pred_y = glm.predict(new_data=data, y_col="y_cont")
    print(f"type(pred_y): {type(pred_y)}")
    pred_y_attrs = [a for a in dir(pred_y) if not a.startswith("_")]
    print(f"Attributes: {pred_y_attrs}")

    for attr_name in ["yhat", "fitted", "values", "se", "std_err",
                      "residuals", "resid", "lci", "uci", "conf_low",
                      "conf_high", "linear_predictor"]:
        if hasattr(pred_y, attr_name):
            val = getattr(pred_y, attr_name)
            vtype = type(val).__name__
            vlen = len(val) if hasattr(val, '__len__') else "N/A"
            if val is None:
                print(f"  pred_y.{attr_name} = None")
            else:
                print(f"  pred_y.{attr_name}: type={vtype}, len={vlen}")
                if hasattr(val, '__getitem__') and vlen != "N/A" and vlen > 0:
                    print(f"    first 3 values: {val[:3]}")
except Exception as e:
    print(f"FAILED: {e}")
    traceback.print_exc()

# Test 6c: predict without new_data
print("\n--- 6c: glm.predict() with no arguments ---")
try:
    pred_noarg = glm.predict()
    print(f"type: {type(pred_noarg)}")
except Exception as e:
    print(f"FAILED (expected): {type(e).__name__}: {e}")

# Test 6d: to_polars() on prediction objects
print("\n--- 6d: pred.to_polars() ---")
try:
    pred_for_df = glm.predict(new_data=data, y_col="y_cont")
    if hasattr(pred_for_df, 'to_polars'):
        pred_df = pred_for_df.to_polars()
        print(f"pred.to_polars() columns: {pred_df.columns}")
        print(f"pred.to_polars() dtypes: {pred_df.dtypes}")
        print(f"pred.to_polars() shape: {pred_df.shape}")
        print(f"first 3 rows:\n{pred_df.head(3)}")
    else:
        print("pred does NOT have to_polars()")
except Exception as e:
    print(f"FAILED: {e}")

# Test 6e: to_polars() on predict without y_col
print("\n--- 6e: pred.to_polars() without y_col ---")
try:
    pred_no_y = glm.predict(new_data=data)
    if hasattr(pred_no_y, 'to_polars'):
        pred_df_no_y = pred_no_y.to_polars()
        print(f"pred (no y_col).to_polars() columns: {pred_df_no_y.columns}")
        print(f"first 3 rows:\n{pred_df_no_y.head(3)}")
    else:
        print("pred does NOT have to_polars()")
except Exception as e:
    print(f"FAILED: {e}")
print()

# =============================================================================
# SECTION 7: Logistic model — verify same structure
# =============================================================================
print("=" * 70)
print("SECTION 7: Logistic (binomial) model — structure verification")
print("=" * 70)

try:
    glm_logit = sample.glm.fit(y="y_binary", x=["x1", "x2"], family="binomial")
    fit_logit = glm_logit.fitted
    print(f"type(glm_logit): {type(glm_logit)}")
    print(f"type(fit_logit): {type(fit_logit)}")

    if hasattr(fit_logit, 'to_polars'):
        logit_df = fit_logit.to_polars()
        print(f"fit.to_polars() columns: {logit_df.columns}")
        print(f"data:\n{logit_df}")

    if hasattr(fit_logit, 'stats'):
        stats_logit = fit_logit.stats
        stats_attrs_logit = [a for a in dir(stats_logit) if not a.startswith("_")]
        print(f"fit.stats attributes: {stats_attrs_logit}")
        for attr_name in ["n", "r_squared", "aic", "bic", "deviance"]:
            if hasattr(stats_logit, attr_name):
                print(f"  stats.{attr_name} = {getattr(stats_logit, attr_name)}")
except Exception as e:
    print(f"FAILED: {e}")
    traceback.print_exc()
print()

# =============================================================================
# SECTION 8: Model with categorical predictors
# =============================================================================
print("=" * 70)
print("SECTION 8: Model with svy.Cat() — term naming")
print("=" * 70)

try:
    glm_cat = sample.glm.fit(
        y="y_cont",
        x=["x1", svy.Cat("cat_var")],
        family="gaussian"
    )
    fit_cat = glm_cat.fitted
    if hasattr(fit_cat, 'to_polars'):
        cat_df = fit_cat.to_polars()
        print(f"Columns: {cat_df.columns}")
        print(f"Term names with categorical:\n{cat_df}")
    if hasattr(fit_cat, 'coefs') and hasattr(fit_cat.coefs, '__iter__'):
        print("\nCoefficient terms:")
        for c in fit_cat.coefs:
            if hasattr(c, 'term'):
                print(f"  term='{c.term}'")
            elif hasattr(c, 'name'):
                print(f"  name='{c.name}'")
except Exception as e:
    print(f"FAILED: {e}")
    traceback.print_exc()
print()

# =============================================================================
# SECTION 9: print(model) output — what does the __str__ look like?
# =============================================================================
print("=" * 70)
print("SECTION 9: print(model) output")
print("=" * 70)

print("print(glm):")
print(glm)
print()

# =============================================================================
# SECTION 10: Wald test object on coefficients
# =============================================================================
print("=" * 70)
print("SECTION 10: Wald / test statistic object on coefficients")
print("=" * 70)

try:
    fit = glm.fitted
    if hasattr(fit, 'coefs') and hasattr(fit.coefs, '__iter__'):
        c = list(fit.coefs)[0]
        if hasattr(c, 'wald'):
            wald = c.wald
            print(f"type(c.wald): {type(wald)}")
            wald_attrs = [a for a in dir(wald) if not a.startswith("_")]
            print(f"wald attributes: {wald_attrs}")
            for attr_name in ["value", "p_value", "pvalue", "statistic",
                              "df", "t_value", "t_stat"]:
                if hasattr(wald, attr_name):
                    print(f"  wald.{attr_name} = {getattr(wald, attr_name)}")
        else:
            print("Coefficient does NOT have .wald")
            # Check for alternative test statistic access
            for alt in ["t_test", "test", "tstat", "z_test"]:
                if hasattr(c, alt):
                    print(f"  Found alternative: c.{alt} -> {type(getattr(c, alt))}")
except Exception as e:
    print(f"Error: {e}")
print()

# =============================================================================
# SUMMARY: Confirmed API Structure
# =============================================================================
print("=" * 70)
print("SUMMARY: CONFIRMED API STRUCTURE")
print("=" * 70)
print("""
This section will be filled by reading the output above. Key questions:
1. glm = sample.glm.fit(...) returns what type?
2. glm.fitted returns what type? What attributes?
3. glm.coefs: does it exist on glm? on fit? what type?
4. fit.to_polars(): exact column names
5. fit.stats: exact attributes (aic, bic, n, r_squared, etc.)
6. glm.predict(new_data, y_col): return type, residuals, yhat, to_polars() cols
7. Individual coef: .term, .est, .se, .lci, .uci, .wald
""")

print("\nDONE — Script complete.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-03-28 20:45:24
# Command: python3 /daaf/research/2026-03-28_AdHoc_Library_Smoke_Tests/scripts/adhoc/11_smoke_svy_glm_verify.py
# Duration: s
# Exit code: 0
#
# --- STDOUT ---
# ======================================================================
# SVY 0.13.0 GLM RESULT EXTRACTION — DEEP API VERIFICATION
# ======================================================================
# Data shape: (500, 8)
# 
# ======================================================================
# SECTION 1: Return type of sample.glm.fit()
# ======================================================================
# type(glm): <class 'svy.regression.glm.GLM'>
# repr(glm): <GLM: Fitted Gaussian (identity) on y 'y_cont'>
# Non-dunder attributes of glm: ['PRINT_WIDTH', 'coefs', 'fit', 'fitted', 'margins', 'predict', 'set_default_print_width', 'set_print_width', 'stats']
# 
# ======================================================================
# SECTION 2: glm.fitted (GLMFit object)
# ======================================================================
# type(glm.fitted): <class 'svy.regression.results.GLMFit'>
# Non-dunder attributes of fitted: ['coefs', 'cov_matrix', 'family', 'feature_names', 'link', 'stats', 'term_info', 'to_dict', 'to_polars', 'y']
# 
# ======================================================================
# SECTION 3: glm.coefs (direct on glm object)
# ======================================================================
# type(glm.coefs): <class 'list'>
# repr: [GLMCoef(term='_intercept_', est=np.float64(11.998108337972237), se=np.float64(1.3906916591220808), lci=np.float64(8.899454221149078), uci=np.float64(15.096762454795396), wald=TDist(df=10, value=np.float64(8.62743963356078), p_value=np.float64(6.041801698191928e-06)), wald_adj=None), GLMCoef(term='x
# len(glm.coefs): 3
# Attributes: ['append', 'clear', 'copy', 'count', 'extend', 'index', 'insert', 'pop', 'remove', 'reverse', 'sort']
# 
# type(glm.fitted.coefs): <class 'list'>
# len: 3
# 
#   Coef [0]:
#     type: <class 'svy.regression.results.GLMCoef'>
#     attributes: ['est', 'lci', 'se', 'term', 'to_dict', 'uci', 'wald', 'wald_adj']
#     c.term = _intercept_ (type: str)
#     c.est = 11.998108337972237 (type: float64)
#     c.se = 1.3906916591220808 (type: float64)
#     c.lci = 8.899454221149078 (type: float64)
#     c.uci = 15.096762454795396 (type: float64)
#     c.wald = TDist(df=10, value=np.float64(8.62743963356078), p_value=np.float64(6.041801698191928e-06)) (type: TDist)
# 
#   Coef [1]:
#     type: <class 'svy.regression.results.GLMCoef'>
#     attributes: ['est', 'lci', 'se', 'term', 'to_dict', 'uci', 'wald', 'wald_adj']
#     c.term = x1 (type: str)
#     c.est = 0.470171945504796 (type: float64)
#     c.se = 0.017854033758840645 (type: float64)
#     c.lci = 0.43039067922204866 (type: float64)
#     c.uci = 0.5099532117875434 (type: float64)
#     c.wald = TDist(df=10, value=np.float64(26.334213985228104), p_value=np.float64(1.4368011745780549e-10)) (type: TDist)
#   ... (3 total coefficients)
# 
# ======================================================================
# SECTION 4: glm.stats (model statistics)
# ======================================================================
# type(glm.stats): <class 'svy.regression.results.GLMStats'>
# Attributes: ['aic', 'bic', 'deviance', 'iterations', 'n', 'r_squared', 'r_squared_adj', 'scale', 'to_dict', 'wald', 'wald_adj']
#   glm.stats.n = 500 (type: int)
#   glm.stats.r_squared = 0.7728381978111071 (type: float)
#   glm.stats.aic = 11876.720652495422 (type: float)
#   glm.stats.bic = 11889.364476790688 (type: float)
#   glm.stats.deviance = 11870.720652495422 (type: float)
# 
# type(glm.fitted.stats): <class 'svy.regression.results.GLMStats'>
# Attributes: ['aic', 'bic', 'deviance', 'iterations', 'n', 'r_squared', 'r_squared_adj', 'scale', 'to_dict', 'wald', 'wald_adj']
#   fit.stats.n = 500 (type: int)
#   fit.stats.r_squared = 0.7728381978111071 (type: float)
#   fit.stats.aic = 11876.720652495422 (type: float)
#   fit.stats.bic = 11889.364476790688 (type: float)
#   fit.stats.deviance = 11870.720652495422 (type: float)
# 
# ======================================================================
# SECTION 5: to_polars() on every candidate object
# ======================================================================
# 
# glm does NOT have to_polars()
# 
# glm.fitted.to_polars():
#   type: <class 'polars.dataframe.frame.DataFrame'>
#   columns: ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']
#   dtypes: [String, Float64, Float64, Float64, Float64, Float64, Float64, Int64]
#   shape: (3, 8)
#   first 3 rows:
# shape: (3, 8)
# ┌─────────────┬───────────┬──────────┬──────────┬───────────┬───────────┬────────────┬─────┐
# │ term        ┆ estimate  ┆ std_err  ┆ conf_low ┆ conf_high ┆ statistic ┆ p_value    ┆ df  │
# │ ---         ┆ ---       ┆ ---      ┆ ---      ┆ ---       ┆ ---       ┆ ---        ┆ --- │
# │ str         ┆ f64       ┆ f64      ┆ f64      ┆ f64       ┆ f64       ┆ f64        ┆ i64 │
# ╞═════════════╪═══════════╪══════════╪══════════╪═══════════╪═══════════╪════════════╪═════╡
# │ _intercept_ ┆ 11.998108 ┆ 1.390692 ┆ 8.899454 ┆ 15.096762 ┆ 8.62744   ┆ 0.000006   ┆ 10  │
# │ x1          ┆ 0.470172  ┆ 0.017854 ┆ 0.430391 ┆ 0.509953  ┆ 26.334214 ┆ 1.4368e-10 ┆ 10  │
# │ x2          ┆ 0.299334  ┆ 0.00831  ┆ 0.280818 ┆ 0.317849  ┆ 36.021168 ┆ 6.4601e-12 ┆ 10  │
# └─────────────┴───────────┴──────────┴──────────┴───────────┴───────────┴────────────┴─────┘
# 
# Individual GLMCoef has to_polars(): NO
# 
# ======================================================================
# SECTION 6: glm.predict() — signatures and return object
# ======================================================================
# 
# --- 6a: glm.predict(new_data=data) ---
# type(pred): <class 'svy.regression.prediction.GLMPred'>
# Attributes: ['alpha', 'conf_level', 'df', 'lci', 'residuals', 'se', 'to_dict', 'to_polars', 'uci', 'yhat']
#   pred.yhat: type=ndarray, len=500
#     first 3 values: [71.41664913 71.57259734 74.32877245]
#   pred.se: type=ndarray, len=500
#     first 3 values: [0.32299488 0.45870952 0.39054853]
#   pred.residuals = None
#   pred.lci: type=ndarray, len=500
#     first 3 values: [70.6969717  70.55052884 73.4585761 ]
#   pred.uci: type=ndarray, len=500
#     first 3 values: [72.13632657 72.59466585 75.19896881]
# 
# --- 6b: glm.predict(new_data=data, y_col='y_cont') ---
# type(pred_y): <class 'svy.regression.prediction.GLMPred'>
# Attributes: ['alpha', 'conf_level', 'df', 'lci', 'residuals', 'se', 'to_dict', 'to_polars', 'uci', 'yhat']
#   pred_y.yhat: type=ndarray, len=500
#     first 3 values: [71.41664913 71.57259734 74.32877245]
#   pred_y.se: type=ndarray, len=500
#     first 3 values: [0.32299488 0.45870952 0.39054853]
#   pred_y.residuals: type=ndarray, len=500
#     first 3 values: [6.18029858 7.92112216 0.01327871]
#   pred_y.lci: type=ndarray, len=500
#     first 3 values: [70.6969717  70.55052884 73.4585761 ]
#   pred_y.uci: type=ndarray, len=500
#     first 3 values: [72.13632657 72.59466585 75.19896881]
# 
# --- 6c: glm.predict() with no arguments ---
# FAILED (expected): TypeError: GLM.predict() missing 1 required positional argument: 'new_data'
# 
# --- 6d: pred.to_polars() ---
# pred.to_polars() columns: ['yhat', 'se', 'lci', 'uci', 'residuals']
# pred.to_polars() dtypes: [Float64, Float64, Float64, Float64, Float64]
# pred.to_polars() shape: (500, 5)
# first 3 rows:
# shape: (3, 5)
# ┌───────────┬──────────┬───────────┬───────────┬───────────┐
# │ yhat      ┆ se       ┆ lci       ┆ uci       ┆ residuals │
# │ ---       ┆ ---      ┆ ---       ┆ ---       ┆ ---       │
# │ f64       ┆ f64      ┆ f64       ┆ f64       ┆ f64       │
# ╞═══════════╪══════════╪═══════════╪═══════════╪═══════════╡
# │ 71.416649 ┆ 0.322995 ┆ 70.696972 ┆ 72.136327 ┆ 6.180299  │
# │ 71.572597 ┆ 0.45871  ┆ 70.550529 ┆ 72.594666 ┆ 7.921122  │
# │ 74.328772 ┆ 0.390549 ┆ 73.458576 ┆ 75.198969 ┆ 0.013279  │
# └───────────┴──────────┴───────────┴───────────┴───────────┘
# 
# --- 6e: pred.to_polars() without y_col ---
# pred (no y_col).to_polars() columns: ['yhat', 'se', 'lci', 'uci']
# first 3 rows:
# shape: (3, 4)
# ┌───────────┬──────────┬───────────┬───────────┐
# │ yhat      ┆ se       ┆ lci       ┆ uci       │
# │ ---       ┆ ---      ┆ ---       ┆ ---       │
# │ f64       ┆ f64      ┆ f64       ┆ f64       │
# ╞═══════════╪══════════╪═══════════╪═══════════╡
# │ 71.416649 ┆ 0.322995 ┆ 70.696972 ┆ 72.136327 │
# │ 71.572597 ┆ 0.45871  ┆ 70.550529 ┆ 72.594666 │
# │ 74.328772 ┆ 0.390549 ┆ 73.458576 ┆ 75.198969 │
# └───────────┴──────────┴───────────┴───────────┘
# 
# ======================================================================
# SECTION 7: Logistic (binomial) model — structure verification
# ======================================================================
# type(glm_logit): <class 'svy.regression.glm.GLM'>
# type(fit_logit): <class 'svy.regression.results.GLMFit'>
# fit.to_polars() columns: ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']
# data:
# shape: (3, 8)
# ┌─────────────┬────────────┬──────────┬────────────┬───────────┬───────────┬───────────┬─────┐
# │ term        ┆ estimate   ┆ std_err  ┆ conf_low   ┆ conf_high ┆ statistic ┆ p_value   ┆ df  │
# │ ---         ┆ ---        ┆ ---      ┆ ---        ┆ ---       ┆ ---       ┆ ---       ┆ --- │
# │ str         ┆ f64        ┆ f64      ┆ f64        ┆ f64       ┆ f64       ┆ f64       ┆ i64 │
# ╞═════════════╪════════════╪══════════╪════════════╪═══════════╪═══════════╪═══════════╪═════╡
# │ _intercept_ ┆ -19.418816 ┆ 1.209765 ┆ -22.114341 ┆ -16.72329 ┆ -16.05172 ┆ 1.8200e-8 ┆ 10  │
# │ x1          ┆ 0.161341   ┆ 0.016251 ┆ 0.125131   ┆ 0.19755   ┆ 9.928149  ┆ 0.000002  ┆ 10  │
# │ x2          ┆ 0.111925   ┆ 0.00573  ┆ 0.099158   ┆ 0.124691  ┆ 19.534711 ┆ 2.7011e-9 ┆ 10  │
# └─────────────┴────────────┴──────────┴────────────┴───────────┴───────────┴───────────┴─────┘
# fit.stats attributes: ['aic', 'bic', 'deviance', 'iterations', 'n', 'r_squared', 'r_squared_adj', 'scale', 'to_dict', 'wald', 'wald_adj']
#   stats.n = 500
#   stats.r_squared = 0.5356353168583798
#   stats.aic = 63.85138778401271
#   stats.bic = 76.49521207927928
#   stats.deviance = 57.85138778401271
# 
# ======================================================================
# SECTION 8: Model with svy.Cat() — term naming
# ======================================================================
# Columns: ['term', 'estimate', 'std_err', 'conf_low', 'conf_high', 'statistic', 'p_value', 'df']
# Term names with categorical:
# shape: (4, 8)
# ┌─────────────┬───────────┬──────────┬───────────┬───────────┬───────────┬───────────┬─────┐
# │ term        ┆ estimate  ┆ std_err  ┆ conf_low  ┆ conf_high ┆ statistic ┆ p_value   ┆ df  │
# │ ---         ┆ ---       ┆ ---      ┆ ---       ┆ ---       ┆ ---       ┆ ---       ┆ --- │
# │ str         ┆ f64       ┆ f64      ┆ f64       ┆ f64       ┆ f64       ┆ f64       ┆ i64 │
# ╞═════════════╪═══════════╪══════════╪═══════════╪═══════════╪═══════════╪═══════════╪═════╡
# │ _intercept_ ┆ 41.383262 ┆ 1.915138 ┆ 37.116069 ┆ 45.650455 ┆ 21.608503 ┆ 1.0062e-9 ┆ 10  │
# │ x1          ┆ 0.498197  ┆ 0.03553  ┆ 0.41903   ┆ 0.577363  ┆ 14.021764 ┆ 6.6726e-8 ┆ 10  │
# │ cat_var_B   ┆ 1.130856  ┆ 1.215703 ┆ -1.577898 ┆ 3.83961   ┆ 0.930208  ┆ 0.374174  ┆ 10  │
# │ cat_var_C   ┆ -1.052859 ┆ 0.706024 ┆ -2.625978 ┆ 0.520261  ┆ -1.491251 ┆ 0.166751  ┆ 10  │
# └─────────────┴───────────┴──────────┴───────────┴───────────┴───────────┴───────────┴─────┘
# 
# Coefficient terms:
#   term='_intercept_'
#   term='x1'
#   term='cat_var_B'
#   term='cat_var_C'
# 
# ======================================================================
# SECTION 9: print(model) output
# ======================================================================
# print(glm):
# GLM: Gaussian (identity)
#   y = 'y_cont'
#   n = 500
# 
# Coefficients:
#   _intercept_                     est=   11.9981  se=    1.3907  [8.8995, 15.0968]
#   x1                              est=    0.4702  se=    0.0179  [0.4304, 0.5100]
#   x2                              est=    0.2993  se=    0.0083  [0.2808, 0.3178]
# 
# ======================================================================
# SECTION 10: Wald / test statistic object on coefficients
# ======================================================================
# type(c.wald): <class 'svy.core.containers.TDist'>
# wald attributes: ['df', 'p_value', 'value']
#   wald.value = 8.62743963356078
#   wald.p_value = 6.041801698191928e-06
#   wald.df = 10
# 
# ======================================================================
# SUMMARY: CONFIRMED API STRUCTURE
# ======================================================================
# 
# This section will be filled by reading the output above. Key questions:
# 1. glm = sample.glm.fit(...) returns what type?
# 2. glm.fitted returns what type? What attributes?
# 3. glm.coefs: does it exist on glm? on fit? what type?
# 4. fit.to_polars(): exact column names
# 5. fit.stats: exact attributes (aic, bic, n, r_squared, etc.)
# 6. glm.predict(new_data, y_col): return type, residuals, yhat, to_polars() cols
# 7. Individual coef: .term, .est, .se, .lci, .uci, .wald
# 
# 
# DONE — Script complete.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
