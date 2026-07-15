# scripts/scratch/xval_svy_r_03_py_svy.py
# INTENT: fit the svy (Python) side of the cross-validation vs R survey. Generate the shared
#   synthetic survey frame ONCE, write it to parquet (both languages read the same file), then
#   compute every quantity under test and write each to a parquet for the compare step.
# REASONING: paired-script pattern (rpy2 not installed). This script owns the frame + all svy
#   outputs; xval_svy_r_04_r_survey.R produces the R outputs on the identical parquet; the
#   compare step (05) joins and verdicts. Design parity: strata=stratum, ids=psu, weights=weight,
#   PSUs globally unique (nest belt-and-suspenders), NO FPC (no pop_size), Taylor variance.
# ASSUMES: svy 0.19.0 installed API (verified by smoke_svy_a.py + the two introspection probes):
#   Design(stratum=, wgt=, psu=); Sample(df, design=); glm.fit returns GLM with .to_polars()
#   schema [term,estimate,std_err,conf_low,conf_high,statistic,p_value,df]; margins() -> list
#   [GLMMargins] each .to_polars() [term,margin,se,lci,uci]; categorical.tabulate(row,col) -> Table
#   whose .stats is TableStats(chisq=ChiSquare(df,value,p_value), f=FDist(df_num,df_den,value,
#   p_value)); estimation.mean(by=) -> Estimate with per-domain [group,est,se,lci,uci,cv].

# --- Config ---
import numpy as np
import polars as pl
import svy

SCRATCH = "/daaf/scripts/scratch"
FRAME_PATH = f"{SCRATCH}/xval_svy_r_frame.parquet"

print(f"svy {svy.__version__} | polars {pl.__version__}")

# --- Build shared synthetic frame (identical seeding to smoke_svy_a.py) ---
# INTENT: 4 strata x 6 globally-unique PSUs x 20 obs = 480 rows, seeded rng(42).
# REASONING: reusing the smoke test's exact construction makes svy results here identical to
#   the smoke-test log, and writing to parquet guarantees R reads byte-identical inputs.
# ASSUMES: PSU ids run 1..24 globally (nested design), so nest=TRUE in R is a no-op safety net.
rng = np.random.default_rng(42)
n_strata, n_psu, n_obs = 4, 6, 20
n = n_strata * n_psu * n_obs
stratum = np.repeat(np.arange(1, n_strata + 1), n_psu * n_obs)
psu = np.repeat(np.arange(1, n_strata * n_psu + 1), n_obs)
weight = rng.uniform(0.5, 5.0, size=n)
income = 30000.0 + 500.0 * stratum + rng.normal(0.0, 5000.0, size=n)
age = rng.integers(18, 81, size=n).astype(float)
gender = rng.choice(["Male", "Female"], size=n)
_p = 1.0 / (1.0 + np.exp(-(-1.0 + 0.02 * age + 0.5 * (gender == "Male"))))
employed = rng.binomial(1, _p).astype(float)
visit_count = rng.poisson(np.exp(0.5 + 0.01 * age / 10.0)).astype(float)

df = pl.DataFrame({
    "stratum": stratum, "psu": psu, "weight": weight, "income": income, "age": age,
    "gender": gender, "employed": employed, "visit_count": visit_count,
})
df.write_parquet(FRAME_PATH)
print(f"Wrote shared frame: {df.shape} -> {FRAME_PATH}")

# --- Design + Sample (Taylor, no FPC) ---
design = svy.Design(stratum="stratum", wgt="weight", psu="psu")
sample = svy.Sample(df, design=design)
print("Design(stratum, wgt, psu) + Sample built (Taylor, no FPC)\n")


def canon_term(t):
    # INTENT: map svy term labels to a language-neutral key for joining with R.
    # REASONING: svy uses '_intercept_'/'age'/'gender_Male'; R uses '(Intercept)'/'age'/
    #   'genderMale'. A shared key lets the compare step align rows without guessing.
    tl = t.lower()
    if "intercept" in tl:
        return "intercept"
    if tl == "age":
        return "age"
    if "gender" in tl and "male" in tl:
        return "gender_Male"
    return tl


# --- Gap 1a: logistic GLM ---
# INTENT: survey-weighted logistic, employed ~ age + Cat(gender).
# REASONING: matches R svyglm(family=quasibinomial()); upstream issue #5 is about p-value
#   agreement, so capture estimate/std_err/statistic/p_value/df for every term.
# ASSUMES: string predictor MUST be svy.Cat() (raw string raises strict-cast ValueError).
logit = sample.glm.fit(y="employed", x=["age", svy.Cat("gender")], family="binomial")
logit_pl = logit.to_polars().with_columns(
    pl.col("term").map_elements(canon_term, return_dtype=pl.Utf8).alias("param")
)
logit_pl.write_parquet(f"{SCRATCH}/xval_svy_r_svy_logit.parquet")
print("svy logistic GLM coef table:")
print(logit_pl.select(["param", "estimate", "std_err", "statistic", "p_value", "df"]))
print()

# --- Gap 1b: Poisson GLM ---
# INTENT: survey-weighted Poisson, visit_count ~ age + Cat(gender), vs R quasipoisson.
pois = sample.glm.fit(y="visit_count", x=["age", svy.Cat("gender")], family="poisson")
pois_pl = pois.to_polars().with_columns(
    pl.col("term").map_elements(canon_term, return_dtype=pl.Utf8).alias("param")
)
pois_pl.write_parquet(f"{SCRATCH}/xval_svy_r_svy_pois.parquet")
print("svy Poisson GLM coef table:")
print(pois_pl.select(["param", "estimate", "std_err", "statistic", "p_value", "df"]))
print()

# --- Gap 2: marginal effects (AME) on the logistic model ---
# INTENT: average marginal effects, compared to marginaleffects::avg_slopes on the R svyglm.
# ASSUMES: margins() returns list[GLMMargins]; each .to_polars() -> [term,margin,se,lci,uci].
marg_list = logit.margins()
marg_frames = []
for gm in marg_list:
    marg_frames.append(gm.to_polars())
marg_pl = pl.concat(marg_frames, how="vertical_relaxed").with_columns(
    pl.col("term").map_elements(canon_term, return_dtype=pl.Utf8).alias("param")
)
marg_pl.write_parquet(f"{SCRATCH}/xval_svy_r_svy_margins.parquet")
print("svy margins() AME:")
print(marg_pl)
print()

# --- Gap 3: two-way categorical tabulation + Rao-Scott chi-square / F ---
# INTENT: two-way gender x employed cell proportions + the design-based independence test,
#   vs R svymean(~interaction) for cells and svychisq() for the test.
# ASSUMES: tabulate(row,col) -> Table; .to_polars() cell proportions; .stats = TableStats(...).
tab2 = sample.categorical.tabulate("gender", "employed", units="proportion")
tab2_pl = tab2.to_polars().with_columns([
    pl.col("gender").cast(pl.Utf8),
    pl.col("employed").cast(pl.Utf8),
])
tab2_pl.write_parquet(f"{SCRATCH}/xval_svy_r_svy_twoway.parquet")
print("svy two-way tabulation (proportions):")
print(tab2_pl.select(["gender", "employed", "est", "se"]))

ts = tab2.stats  # TableStats(chisq=ChiSquare(df,value,p_value), f=FDist(df_num,df_den,value,p_value))
chisq_pl = pl.DataFrame({
    "chisq_value": [float(ts.chisq.value)],
    "chisq_df": [float(ts.chisq.df)],
    "chisq_p": [float(ts.chisq.p_value)],
    "f_value": [float(ts.f.value)],
    "f_df_num": [float(ts.f.df_num)],
    "f_df_den": [float(ts.f.df_den)],
    "f_p": [float(ts.f.p_value)],
})
chisq_pl.write_parquet(f"{SCRATCH}/xval_svy_r_svy_chisq.parquet")
print("svy Rao-Scott chisq/F:")
print(chisq_pl)
print()

# --- Bonus: domain mean income by stratum + CI half-width (issue #3) ---
# INTENT: per-stratum mean income with CI; compare CI half-width to R svyby+confint.
# REASONING: upstream issue #3 concerns domain CI degrees of freedom; the half-width encodes
#   whether svy uses a t (design-df) or z multiplier.
dom = sample.estimation.mean("income", by="stratum")
dom_pl = dom.to_polars().with_columns(
    ((pl.col("uci") - pl.col("lci")) / 2.0).alias("half_width")
).with_columns(pl.col("stratum").cast(pl.Utf8))
dom_pl.write_parquet(f"{SCRATCH}/xval_svy_r_svy_domain.parquet")
print("svy domain mean income by stratum:")
print(dom_pl.select(["stratum", "est", "se", "lci", "uci", "half_width"]))
print()

print("=== svy side complete; all result parquets written ===")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 11:53:02
# Command: python3 /daaf/scripts/scratch/xval_svy_r_03_py_svy.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# svy 0.19.0 | polars 1.39.3
# Wrote shared frame: (480, 8) -> /daaf/scripts/scratch/xval_svy_r_frame.parquet
# Design(stratum, wgt, psu) + Sample built (Taylor, no FPC)
# 
# svy logistic GLM coef table:
# shape: (3, 6)
# ┌─────────────┬───────────┬──────────┬───────────┬──────────┬─────┐
# │ param       ┆ estimate  ┆ std_err  ┆ statistic ┆ p_value  ┆ df  │
# │ ---         ┆ ---       ┆ ---      ┆ ---       ┆ ---      ┆ --- │
# │ str         ┆ f64       ┆ f64      ┆ f64       ┆ f64      ┆ i64 │
# ╞═════════════╪═══════════╪══════════╪═══════════╪══════════╪═════╡
# │ intercept   ┆ -0.551967 ┆ 0.248351 ┆ -2.222527 ┆ 0.039301 ┆ 18  │
# │ age         ┆ 0.010673  ┆ 0.003952 ┆ 2.700641  ┆ 0.014632 ┆ 18  │
# │ gender_Male ┆ 0.6325    ┆ 0.211176 ┆ 2.995137  ┆ 0.007767 ┆ 18  │
# └─────────────┴───────────┴──────────┴───────────┴──────────┴─────┘
# 
# svy Poisson GLM coef table:
# shape: (3, 6)
# ┌─────────────┬──────────┬──────────┬───────────┬──────────┬─────┐
# │ param       ┆ estimate ┆ std_err  ┆ statistic ┆ p_value  ┆ df  │
# │ ---         ┆ ---      ┆ ---      ┆ ---       ┆ ---      ┆ --- │
# │ str         ┆ f64      ┆ f64      ┆ f64       ┆ f64      ┆ i64 │
# ╞═════════════╪══════════╪══════════╪═══════════╪══════════╪═════╡
# │ intercept   ┆ 0.414763 ┆ 0.130011 ┆ 3.190223  ┆ 0.00507  ┆ 18  │
# │ age         ┆ 0.000838 ┆ 0.002301 ┆ 0.364373  ┆ 0.719825 ┆ 18  │
# │ gender_Male ┆ 0.084059 ┆ 0.061981 ┆ 1.356222  ┆ 0.191798 ┆ 18  │
# └─────────────┴──────────┴──────────┴───────────┴──────────┴─────┘
# 
# svy margins() AME:
# shape: (1, 6)
# ┌──────┬──────────┬──────────┬──────────┬──────────┬───────┐
# │ term ┆ margin   ┆ se       ┆ lci      ┆ uci      ┆ param │
# │ ---  ┆ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---   │
# │ str  ┆ f64      ┆ f64      ┆ f64      ┆ f64      ┆ str   │
# ╞══════╪══════════╪══════════╪══════════╪══════════╪═══════╡
# │ age  ┆ 0.002535 ┆ 0.000939 ┆ 0.000563 ┆ 0.004508 ┆ age   │
# └──────┴──────────┴──────────┴──────────┴──────────┴───────┘
# 
# svy two-way tabulation (proportions):
# shape: (4, 4)
# ┌────────┬──────────┬──────────┬──────────┐
# │ gender ┆ employed ┆ est      ┆ se       │
# │ ---    ┆ ---      ┆ ---      ┆ ---      │
# │ str    ┆ str      ┆ f64      ┆ f64      │
# ╞════════╪══════════╪══════════╪══════════╡
# │ Female ┆ 0        ┆ 0.257386 ┆ 0.023113 │
# │ Female ┆ 1        ┆ 0.250599 ┆ 0.019614 │
# │ Male   ┆ 0        ┆ 0.174407 ┆ 0.013126 │
# │ Male   ┆ 1        ┆ 0.317609 ┆ 0.022696 │
# └────────┴──────────┴──────────┴──────────┘
# svy Rao-Scott chisq/F:
# shape: (1, 7)
# ┌─────────────┬──────────┬─────────┬──────────┬──────────┬──────────┬──────────┐
# │ chisq_value ┆ chisq_df ┆ chisq_p ┆ f_value  ┆ f_df_num ┆ f_df_den ┆ f_p      │
# │ ---         ┆ ---      ┆ ---     ┆ ---      ┆ ---      ┆ ---      ┆ ---      │
# │ f64         ┆ f64      ┆ f64     ┆ f64      ┆ f64      ┆ f64      ┆ f64      │
# ╞═════════════╪══════════╪═════════╪══════════╪══════════╪══════════╪══════════╡
# │ 11.327947   ┆ 1.0      ┆ 0.00269 ┆ 9.006655 ┆ 1.0      ┆ 20.0     ┆ 0.007058 │
# └─────────────┴──────────┴─────────┴──────────┴──────────┴──────────┴──────────┘
# 
# svy domain mean income by stratum:
# shape: (4, 6)
# ┌─────────┬──────────────┬────────────┬──────────────┬──────────────┬─────────────┐
# │ stratum ┆ est          ┆ se         ┆ lci          ┆ uci          ┆ half_width  │
# │ ---     ┆ ---          ┆ ---        ┆ ---          ┆ ---          ┆ ---         │
# │ str     ┆ f64          ┆ f64        ┆ f64          ┆ f64          ┆ f64         │
# ╞═════════╪══════════════╪════════════╪══════════════╪══════════════╪═════════════╡
# │ 1       ┆ 30470.313914 ┆ 236.289583 ┆ 29977.42248  ┆ 30963.205348 ┆ 492.891434  │
# │ 2       ┆ 30510.226338 ┆ 565.325303 ┆ 29330.978421 ┆ 31689.474255 ┆ 1179.247917 │
# │ 3       ┆ 31336.966138 ┆ 513.058388 ┆ 30266.745093 ┆ 32407.187183 ┆ 1070.221045 │
# │ 4       ┆ 32287.856503 ┆ 672.305113 ┆ 30885.452611 ┆ 33690.260395 ┆ 1402.403892 │
# └─────────┴──────────────┴────────────┴──────────────┴──────────────┴─────────────┘
# 
# === svy side complete; all result parquets written ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
