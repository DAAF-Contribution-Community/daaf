# scripts/scratch/xval_svy_r_05_compare.py
# INTENT: join the svy and R result parquets, compute absolute + relative differences per
#   quantity, and emit a verdict (MATCH / NEAR / DIVERGE) for each — the evidence that closes
#   the three svy-skill verification gaps.
# REASONING: verdict thresholds per task: MATCH if rel diff < 1e-4 OR abs < 1e-8; NEAR if small
#   and systematic (mechanism identified); DIVERGE if material. Comparing exact float values
#   (not the rounded console prints) is the only defensible basis for the verdict.
# ASSUMES: all xval_svy_r_svy_*.parquet and xval_svy_r_r_*.parquet exist (written by steps 03/04);
#   term keys aligned via the shared `param` column.

# --- Config ---
import polars as pl

SCRATCH = "/daaf/scripts/scratch"


def relmatch(svy_v, r_v):
    # INTENT: absolute + relative diff and a verdict string, per the task's tolerance rules.
    ad = abs(svy_v - r_v)
    denom = max(abs(r_v), 1e-30)
    rd = ad / denom
    if rd < 1e-4 or ad < 1e-8:
        v = "MATCH"
    elif rd < 1e-2:
        v = "NEAR"
    else:
        v = "DIVERGE"
    return ad, rd, v


rows = []


def add(quantity, svy_v, r_v):
    ad, rd, v = relmatch(float(svy_v), float(r_v))
    rows.append({
        "quantity": quantity, "svy": float(svy_v), "R": float(r_v),
        "abs_diff": ad, "rel_diff": rd, "verdict": v,
    })


# --- Gap 1a: logistic GLM ---
sl = pl.read_parquet(f"{SCRATCH}/xval_svy_r_svy_logit.parquet")
rl = pl.read_parquet(f"{SCRATCH}/xval_svy_r_r_logit.parquet")
jl = sl.join(rl, on="param", suffix="_r")
for row in jl.iter_rows(named=True):
    p = row["param"]
    add(f"logit[{p}].estimate", row["estimate"], row["estimate_r"])
    add(f"logit[{p}].std_err", row["std_err"], row["std_err_r"])
    add(f"logit[{p}].p_value", row["p_value"], row["p_value_r"])
    add(f"logit[{p}].df", row["df"], row["df_r"])

# --- Gap 1b: Poisson GLM ---
sp = pl.read_parquet(f"{SCRATCH}/xval_svy_r_svy_pois.parquet")
rp = pl.read_parquet(f"{SCRATCH}/xval_svy_r_r_pois.parquet")
jp = sp.join(rp, on="param", suffix="_r")
for row in jp.iter_rows(named=True):
    p = row["param"]
    add(f"pois[{p}].estimate", row["estimate"], row["estimate_r"])
    add(f"pois[{p}].std_err", row["std_err"], row["std_err_r"])
    add(f"pois[{p}].p_value", row["p_value"], row["p_value_r"])

# --- Gap 2: margins (AME) — age is the only svy-reported term ---
sm = pl.read_parquet(f"{SCRATCH}/xval_svy_r_svy_margins.parquet")
rm = pl.read_parquet(f"{SCRATCH}/xval_svy_r_r_margins.parquet")
sm_age = sm.filter(pl.col("param") == "age")
rm_age = rm.filter(pl.col("param") == "age")
add("margins[age].AME", sm_age.item(0, "margin"), rm_age.item(0, "margin"))
add("margins[age].se", sm_age.item(0, "se"), rm_age.item(0, "se"))
# gender contrast: R reports it, svy does not — record as UNAVAILABLE-on-svy note below.
r_gender_ame = rm.filter(pl.col("param") == "gender_contrast")
svy_has_gender_margin = sm.filter(pl.col("param").str.contains("gender")).height > 0

# --- Gap 3: two-way proportions ---
st = pl.read_parquet(f"{SCRATCH}/xval_svy_r_svy_twoway.parquet")
rt = pl.read_parquet(f"{SCRATCH}/xval_svy_r_r_twoway.parquet")
jt = st.join(rt, on=["gender", "employed"], suffix="_r")
for row in jt.iter_rows(named=True):
    cell = f'{row["gender"]}.{row["employed"]}'
    add(f"twoway[{cell}].prop", row["est"], row["est_r"])
    add(f"twoway[{cell}].se", row["se"], row["se_r"])

# --- Gap 3: Rao-Scott chisq / F ---
sc = pl.read_parquet(f"{SCRATCH}/xval_svy_r_svy_chisq.parquet").row(0, named=True)
rc = pl.read_parquet(f"{SCRATCH}/xval_svy_r_r_chisq.parquet").row(0, named=True)
add("chisq.F_value", sc["f_value"], rc["r_F_value"])
add("chisq.F_ddf", sc["f_df_den"], rc["r_F_ddf"])
add("chisq.F_p", sc["f_p"], rc["r_F_p"])
add("chisq.Pearson_value", sc["chisq_value"], rc["r_Chisq_value"])
add("chisq.Pearson_p", sc["chisq_p"], rc["r_Chisq_p"])

# --- Bonus: domain CI half-width (svy vs R t-based and z-based) ---
sd = pl.read_parquet(f"{SCRATCH}/xval_svy_r_svy_domain.parquet")
rd = pl.read_parquet(f"{SCRATCH}/xval_svy_r_r_domain.parquet")
jd = sd.join(rd, on="stratum", suffix="_r")
for row in jd.iter_rows(named=True):
    s = row["stratum"]
    add(f"domain[s{s}].est", row["est"], row["est_r"])
    add(f"domain[s{s}].se", row["se"], row["se_r"])
    add(f"domain[s{s}].halfwidth_vs_Rt", row["half_width"], row["hw_t"])
    add(f"domain[s{s}].halfwidth_vs_Rz", row["half_width"], row["hw_z"])

# --- Report ---
comp = pl.DataFrame(rows)
with pl.Config(tbl_rows=200, tbl_width_chars=200, fmt_str_lengths=60):
    print(comp)

print("\n=== verdict tallies ===")
print(comp.group_by("verdict").agg(pl.len().alias("n")).sort("verdict"))

print("\n=== NEAR / DIVERGE detail (mechanism candidates) ===")
nd = comp.filter(pl.col("verdict") != "MATCH")
with pl.Config(tbl_rows=200, tbl_width_chars=200, fmt_str_lengths=60):
    print(nd)

print("\n=== margins gender contrast availability ===")
print(f"  svy reports a gender marginal effect: {svy_has_gender_margin}")
print(f"  R avg_slopes gender contrast AME = {r_gender_ame.item(0, 'margin'):.6f} "
      f"(se {r_gender_ame.item(0, 'se'):.6f}) — NO svy counterpart (margins() returned age only)")

print("\n=== domain half-width mechanism ===")
hw_t = comp.filter(pl.col("quantity").str.contains("halfwidth_vs_Rt"))
hw_z = comp.filter(pl.col("quantity").str.contains("halfwidth_vs_Rz"))
print(f"  svy half-width vs R t-based (design df): max rel diff "
      f"{hw_t.get_column('rel_diff').max():.2e} -> {set(hw_t.get_column('verdict').to_list())}")
print(f"  svy half-width vs R z-based (normal):   max rel diff "
      f"{hw_z.get_column('rel_diff').max():.2e} -> {set(hw_z.get_column('verdict').to_list())}")

print("\n=== COMPARE COMPLETE ===")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 11:55:05
# Command: python3 /daaf/scripts/scratch/xval_svy_r_05_compare.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# shape: (52, 6)
# ┌─────────────────────────────┬──────────────┬──────────────┬────────────┬────────────┬─────────┐
# │ quantity                    ┆ svy          ┆ R            ┆ abs_diff   ┆ rel_diff   ┆ verdict │
# │ ---                         ┆ ---          ┆ ---          ┆ ---        ┆ ---        ┆ ---     │
# │ str                         ┆ f64          ┆ f64          ┆ f64        ┆ f64        ┆ str     │
# ╞═════════════════════════════╪══════════════╪══════════════╪════════════╪════════════╪═════════╡
# │ logit[intercept].estimate   ┆ -0.551967    ┆ -0.551967    ┆ 5.0504e-13 ┆ 9.1498e-13 ┆ MATCH   │
# │ logit[intercept].std_err    ┆ 0.248351     ┆ 0.248351     ┆ 1.0502e-8  ┆ 4.2287e-8  ┆ MATCH   │
# │ logit[intercept].p_value    ┆ 0.039301     ┆ 0.039301     ┆ 7.3871e-9  ┆ 1.8796e-7  ┆ MATCH   │
# │ logit[intercept].df         ┆ 18.0         ┆ 18.0         ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ logit[age].estimate         ┆ 0.010673     ┆ 0.010673     ┆ 1.0212e-14 ┆ 9.5688e-13 ┆ MATCH   │
# │ logit[age].std_err          ┆ 0.003952     ┆ 0.003952     ┆ 3.5411e-10 ┆ 8.9607e-8  ┆ MATCH   │
# │ logit[age].p_value          ┆ 0.014632     ┆ 0.014632     ┆ 7.5202e-9  ┆ 5.1396e-7  ┆ MATCH   │
# │ logit[age].df               ┆ 18.0         ┆ 18.0         ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ logit[gender_Male].estimate ┆ 0.6325       ┆ 0.6325       ┆ 3.6871e-13 ┆ 5.8293e-13 ┆ MATCH   │
# │ logit[gender_Male].std_err  ┆ 0.211176     ┆ 0.211176     ┆ 1.4666e-9  ┆ 6.9448e-9  ┆ MATCH   │
# │ logit[gender_Male].p_value  ┆ 0.007767     ┆ 0.007767     ┆ 3.5119e-10 ┆ 4.5215e-8  ┆ MATCH   │
# │ logit[gender_Male].df       ┆ 18.0         ┆ 18.0         ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ pois[intercept].estimate    ┆ 0.414763     ┆ 0.414763     ┆ 1.8274e-13 ┆ 4.4060e-13 ┆ MATCH   │
# │ pois[intercept].std_err     ┆ 0.130011     ┆ 0.130011     ┆ 2.1196e-10 ┆ 1.6303e-9  ┆ MATCH   │
# │ pois[intercept].p_value     ┆ 0.00507      ┆ 0.00507      ┆ 5.7961e-11 ┆ 1.1432e-8  ┆ MATCH   │
# │ pois[age].estimate          ┆ 0.000838     ┆ 0.000838     ┆ 1.0474e-15 ┆ 1.2494e-12 ┆ MATCH   │
# │ pois[age].std_err           ┆ 0.002301     ┆ 0.002301     ┆ 1.5697e-11 ┆ 6.8222e-9  ┆ MATCH   │
# │ pois[age].p_value           ┆ 0.719825     ┆ 0.719825     ┆ 1.8245e-9  ┆ 2.5346e-9  ┆ MATCH   │
# │ pois[gender_Male].estimate  ┆ 0.084059     ┆ 0.084059     ┆ 1.3686e-12 ┆ 1.6281e-11 ┆ MATCH   │
# │ pois[gender_Male].std_err   ┆ 0.061981     ┆ 0.061981     ┆ 1.4109e-10 ┆ 2.2764e-9  ┆ MATCH   │
# │ pois[gender_Male].p_value   ┆ 0.191798     ┆ 0.191798     ┆ 9.5708e-10 ┆ 4.9900e-9  ┆ MATCH   │
# │ margins[age].AME            ┆ 0.002535     ┆ 0.002532     ┆ 0.000004   ┆ 0.001408   ┆ NEAR    │
# │ margins[age].se             ┆ 0.000939     ┆ 0.00093      ┆ 0.000008   ┆ 0.009131   ┆ NEAR    │
# │ twoway[Female.0].prop       ┆ 0.257386     ┆ 0.257386     ┆ 1.1102e-16 ┆ 4.3135e-16 ┆ MATCH   │
# │ twoway[Female.0].se         ┆ 0.023113     ┆ 0.023113     ┆ 1.0408e-17 ┆ 4.5032e-16 ┆ MATCH   │
# │ twoway[Male.0].prop         ┆ 0.174407     ┆ 0.174407     ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ twoway[Male.0].se           ┆ 0.013126     ┆ 0.013126     ┆ 5.2042e-18 ┆ 3.9648e-16 ┆ MATCH   │
# │ twoway[Female.1].prop       ┆ 0.250599     ┆ 0.250599     ┆ 5.5511e-17 ┆ 2.2151e-16 ┆ MATCH   │
# │ twoway[Female.1].se         ┆ 0.019614     ┆ 0.019614     ┆ 3.4694e-18 ┆ 1.7689e-16 ┆ MATCH   │
# │ twoway[Male.1].prop         ┆ 0.317609     ┆ 0.317609     ┆ 1.1102e-16 ┆ 3.4956e-16 ┆ MATCH   │
# │ twoway[Male.1].se           ┆ 0.022696     ┆ 0.022696     ┆ 6.9389e-18 ┆ 3.0573e-16 ┆ MATCH   │
# │ chisq.F_value               ┆ 9.006655     ┆ 9.006655     ┆ 2.4869e-14 ┆ 2.7612e-15 ┆ MATCH   │
# │ chisq.F_ddf                 ┆ 20.0         ┆ 20.0         ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ chisq.F_p                   ┆ 0.007058     ┆ 0.007058     ┆ 9.5410e-16 ┆ 1.3517e-13 ┆ MATCH   │
# │ chisq.Pearson_value         ┆ 11.327947    ┆ 11.327947    ┆ 2.8422e-14 ┆ 2.5090e-15 ┆ MATCH   │
# │ chisq.Pearson_p             ┆ 0.00269      ┆ 0.00269      ┆ 7.1124e-17 ┆ 2.6440e-14 ┆ MATCH   │
# │ domain[s1].est              ┆ 30470.313914 ┆ 30470.313914 ┆ 1.8190e-11 ┆ 5.9697e-16 ┆ MATCH   │
# │ domain[s1].se               ┆ 236.289583   ┆ 236.289583   ┆ 1.7053e-13 ┆ 7.2170e-16 ┆ MATCH   │
# │ domain[s1].halfwidth_vs_Rt  ┆ 492.891434   ┆ 492.891434   ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ domain[s1].halfwidth_vs_Rz  ┆ 492.891434   ┆ 463.119073   ┆ 29.772361  ┆ 0.064287   ┆ DIVERGE │
# │ domain[s2].est              ┆ 30510.226338 ┆ 30510.226338 ┆ 7.2760e-12 ┆ 2.3848e-16 ┆ MATCH   │
# │ domain[s2].se               ┆ 565.325303   ┆ 565.325303   ┆ 3.4106e-13 ┆ 6.0330e-16 ┆ MATCH   │
# │ domain[s2].halfwidth_vs_Rt  ┆ 1179.247917  ┆ 1179.247917  ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ domain[s2].halfwidth_vs_Rz  ┆ 1179.247917  ┆ 1108.017233  ┆ 71.230684  ┆ 0.064287   ┆ DIVERGE │
# │ domain[s3].est              ┆ 31336.966138 ┆ 31336.966138 ┆ 1.0914e-11 ┆ 3.4828e-16 ┆ MATCH   │
# │ domain[s3].se               ┆ 513.058388   ┆ 513.058388   ┆ 1.1369e-13 ┆ 2.2159e-16 ┆ MATCH   │
# │ domain[s3].halfwidth_vs_Rt  ┆ 1070.221045  ┆ 1070.221045  ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ domain[s3].halfwidth_vs_Rz  ┆ 1070.221045  ┆ 1005.575963  ┆ 64.645081  ┆ 0.064287   ┆ DIVERGE │
# │ domain[s4].est              ┆ 32287.856503 ┆ 32287.856503 ┆ 7.2760e-12 ┆ 2.2535e-16 ┆ MATCH   │
# │ domain[s4].se               ┆ 672.305113   ┆ 672.305113   ┆ 2.2737e-13 ┆ 3.3820e-16 ┆ MATCH   │
# │ domain[s4].halfwidth_vs_Rt  ┆ 1402.403892  ┆ 1402.403892  ┆ 0.0        ┆ 0.0        ┆ MATCH   │
# │ domain[s4].halfwidth_vs_Rz  ┆ 1402.403892  ┆ 1317.693809  ┆ 84.710083  ┆ 0.064287   ┆ DIVERGE │
# └─────────────────────────────┴──────────────┴──────────────┴────────────┴────────────┴─────────┘
# 
# === verdict tallies ===
# shape: (3, 2)
# ┌─────────┬─────┐
# │ verdict ┆ n   │
# │ ---     ┆ --- │
# │ str     ┆ u32 │
# ╞═════════╪═════╡
# │ DIVERGE ┆ 4   │
# │ MATCH   ┆ 46  │
# │ NEAR    ┆ 2   │
# └─────────┴─────┘
# 
# === NEAR / DIVERGE detail (mechanism candidates) ===
# shape: (6, 6)
# ┌────────────────────────────┬─────────────┬─────────────┬───────────┬──────────┬─────────┐
# │ quantity                   ┆ svy         ┆ R           ┆ abs_diff  ┆ rel_diff ┆ verdict │
# │ ---                        ┆ ---         ┆ ---         ┆ ---       ┆ ---      ┆ ---     │
# │ str                        ┆ f64         ┆ f64         ┆ f64       ┆ f64      ┆ str     │
# ╞════════════════════════════╪═════════════╪═════════════╪═══════════╪══════════╪═════════╡
# │ margins[age].AME           ┆ 0.002535    ┆ 0.002532    ┆ 0.000004  ┆ 0.001408 ┆ NEAR    │
# │ margins[age].se            ┆ 0.000939    ┆ 0.00093     ┆ 0.000008  ┆ 0.009131 ┆ NEAR    │
# │ domain[s1].halfwidth_vs_Rz ┆ 492.891434  ┆ 463.119073  ┆ 29.772361 ┆ 0.064287 ┆ DIVERGE │
# │ domain[s2].halfwidth_vs_Rz ┆ 1179.247917 ┆ 1108.017233 ┆ 71.230684 ┆ 0.064287 ┆ DIVERGE │
# │ domain[s3].halfwidth_vs_Rz ┆ 1070.221045 ┆ 1005.575963 ┆ 64.645081 ┆ 0.064287 ┆ DIVERGE │
# │ domain[s4].halfwidth_vs_Rz ┆ 1402.403892 ┆ 1317.693809 ┆ 84.710083 ┆ 0.064287 ┆ DIVERGE │
# └────────────────────────────┴─────────────┴─────────────┴───────────┴──────────┴─────────┘
# 
# === margins gender contrast availability ===
#   svy reports a gender marginal effect: False
#   R avg_slopes gender contrast AME = 0.152373 (se 0.050491) — NO svy counterpart (margins() returned age only)
# 
# === domain half-width mechanism ===
#   svy half-width vs R t-based (design df): max rel diff 0.00e+00 -> {'MATCH'}
#   svy half-width vs R z-based (normal):   max rel diff 6.43e-02 -> {'DIVERGE'}
# 
# === COMPARE COMPLETE ===
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
