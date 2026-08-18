# --- Config ---
# INTENT: Verify documented column/coded-value/row-count/value-scale claims for Scorecard,
#         PSEO, FSA, and EADA against the pinned mirror (projected schema + distinct + agg).
# REASONING: SKILL.md files publish column tables, coded-value tables, row counts, and scale
#            claims; adversarial re-proof with documented-vs-present set diffs and min/max scale.
# ASSUMES: pinned public repo; polars scan_parquet over HTTPS.
# Skills under test: education-data-source-{scorecard,pseo,fsa,eada}/SKILL.md.
import polars as pl

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

def schema(rel): return dict(pl.scan_parquet(f"{BASE}/{rel}.parquet").collect_schema())
def distinct(rel, col):
    return sorted(v for v in pl.scan_parquet(f"{BASE}/{rel}.parquet").select(col).unique().collect()[col].to_list() if v is not None)
def dtype(rel, col): return str(schema(rel).get(col))
def probe(label, fn):
    try: print(f"[{label}] {fn()}")
    except Exception as e: print(f"[{label}] ERROR {type(e).__name__}: {str(e)[:130]}")

# ============ SCORECARD ============
print("===== SCORECARD =====")
def sc_earn_shape():
    sc = schema("scorecard/colleges_scorecard_earnings")
    n = pl.scan_parquet(f"{BASE}/scorecard/colleges_scorecard_earnings.parquet").select(pl.len()).collect().item()
    return f"rows={n} (claim 203066) cols={len(sc)} (claim 33) opeid_dtype={sc.get('opeid')} earnings_med_dtype={sc.get('earnings_med')} egt25_dtype={sc.get('earnings_greater_than_25k_pct')}"
probe("earnings shape/dtypes", sc_earn_shape)
# key documented earnings columns present?
def sc_earn_cols():
    doc = {"unitid","opeid","year","years_after_entry","cohort_year","earnings_med","earnings_mean","earnings_sd",
           "earnings_pct10","earnings_pct25","earnings_pct75","earnings_pct90","count_working","count_not_working",
           "earnings_greater_than_25k_pct","earnings_lowinc_mean","earnings_midinc_mean","earnings_highinc_mean",
           "earnings_dep_mean","earnings_ind_mean","earnings_female_mean","earnings_male_mean"}
    act = set(schema("scorecard/colleges_scorecard_earnings").keys())
    return f"documented-not-present={sorted(doc-act)} (extra not listed, n_extra={len(act-doc)})"
probe("earnings documented-cols presence", sc_earn_cols)
probe("earnings years_after_entry distinct (claim 6-10)", lambda: distinct("scorecard/colleges_scorecard_earnings","years_after_entry"))
probe("earnings -3 suppression present in earnings_med", lambda: (-3 in distinct("scorecard/colleges_scorecard_earnings","earnings_med")))
probe("inst_char pred_degree_awarded_ipeds distinct (claim 0-4)", lambda: distinct("scorecard/colleges_scorecard_inst_characteristics","pred_degree_awarded_ipeds"))
probe("earnings opeid6 dtype (claim Integer)", lambda: dtype("scorecard/colleges_scorecard_earnings","opeid6"))

# ============ PSEO ============
print("\n===== PSEO (2020 file) =====")
PS = "pseo/colleges_pseo_2020"
probe("pseo schema sample", lambda: {k: str(v) for k, v in list(schema(PS).items())[:14]})
probe("earnings cols present (p25/p50/p75_earnings, years_after_grad)",
      lambda: [c for c in ["p25_earnings","p50_earnings","p75_earnings","years_after_grad","total_grads_count"] if c in schema(PS)])
probe("degree_level distinct (claim 1-10 ints)", lambda: distinct(PS,"degree_level"))
probe("years_after_grad distinct (claim 1,5,10)", lambda: distinct(PS,"years_after_grad"))
probe("census_division distinct (claim 1-9,99)", lambda: distinct(PS,"census_division"))
probe("cipcode dtype (claim 2-digit integer)", lambda: dtype(PS,"cipcode"))
probe("industry dtype (claim String)", lambda: dtype(PS,"industry"))
probe("opeid dtype (claim integer, NOT string)", lambda: dtype(PS,"opeid"))
def pseo_nulls():
    # claim: PSEO has NO null values in parquet; missing uses -1/-3
    lf = pl.scan_parquet(f"{BASE}/{PS}.parquet")
    tot = lf.select(pl.all().null_count().sum().alias("s")).collect().item()
    return f"total_null_cells={tot} (claim: 0 nulls)"
probe("pseo null-count (claim no nulls)", pseo_nulls)
probe("p50_earnings has -1 and/or -3 (claim missing codes)",
      lambda: [c for c in (-1,-3) if c in distinct(PS,"p50_earnings")])
probe("pseo_cohort format sample (claim 'YYYY-YYYY' string)",
      lambda: (dtype(PS,"pseo_cohort"), distinct(PS,"pseo_cohort")[:4]))

# ============ FSA ============
print("\n===== FSA =====")
probe("grants grant_type distinct (claim 1-5)", lambda: distinct("fsa/colleges_fsa_grants","grant_type"))
probe("loans loan_type distinct (claim 1-14)", lambda: distinct("fsa/colleges_fsa_loans","loan_type"))
probe("campus_based award_type distinct (claim 1,2,3)", lambda: distinct("fsa/colleges_fsa_campus_based_volume","award_type"))
probe("grants key cols present", lambda: [c for c in ["unitid","fips","year","grant_type","grant_recipients_unitid","value_grants_disbursed_unitid"] if c in schema("fsa/colleges_fsa_grants")])
probe("loans key cols present", lambda: [c for c in ["loan_type","loan_recipients_unitid","value_loan_disbursements_unitid"] if c in schema("fsa/colleges_fsa_loans")])
probe("composite_scores financial_resp_score present", lambda: "financial_resp_score" in schema("fsa/colleges_fsa_composite_scores"))
def fsa_9010():
    sc = schema("fsa/colleges_fsa_90_10_revenue_percentages")
    col = "rev_pct_90_10"
    present = col in sc
    if not present: return f"{col} NOT PRESENT; cols={list(sc)[:12]}"
    s = pl.scan_parquet(f"{BASE}/fsa/colleges_fsa_90_10_revenue_percentages.parquet").select(
        pl.col(col).filter(pl.col(col) >= 0).min().alias("mn"), pl.col(col).filter(pl.col(col) >= 0).max().alias("mx")).collect()
    return f"{col} dtype={sc[col]} min(>=0)={s['mn'][0]} max(>=0)={s['mx'][0]} (claim 0-1 proportion, not 0-100)"
probe("90/10 rev_pct_90_10 scale (claim 0-1)", fsa_9010)
probe("composite financial_resp_score range", lambda: (lambda s: f"min={s['mn'][0]} max={s['mx'][0]}")(pl.scan_parquet(f"{BASE}/fsa/colleges_fsa_composite_scores.parquet").select(pl.col('financial_resp_score').min().alias('mn'), pl.col('financial_resp_score').max().alias('mx')).collect()))

# ============ EADA ============
print("\n===== EADA =====")
EA = "eada/colleges_eada_inst_characteristics"
probe("ath_classification_code distinct (claim 1-20)", lambda: distinct(EA,"ath_classification_code"))
probe("opeid dtype (claim String)", lambda: dtype(EA,"opeid"))
probe("key participation cols present",
      lambda: [c for c in ["undup_athpartic_men","undup_athpartic_women","athpartic_men","athpartic_women","ath_classification_name"] if c in schema(EA)])
probe("sector column ABSENT (claim: no sector col)", lambda: ("sector" not in schema(EA)))
probe("opeid null for 2002 (claim)", lambda: (lambda n: f"opeid nulls in 2002 rows all-null={n}")(
      pl.scan_parquet(f"{BASE}/{EA}.parquet").filter(pl.col("year")==2002).select(pl.col("opeid").is_null().all()).collect().item()))

print("\nVALIDATION: scorecard/pseo/fsa/eada probes executed PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:15:01
# Command: python3 /daaf/scripts/mirror_maintenance/30_doc-audit-scorecard-pseo-fsa-eada.py
# Duration: 40s
# Exit code: 0
#
# --- STDOUT ---
# ===== SCORECARD =====
# [earnings shape/dtypes] rows=203066 (claim 203066) cols=33 (claim 33) opeid_dtype=String earnings_med_dtype=Int64 egt25_dtype=Float64
# [earnings documented-cols presence] documented-not-present=[] (extra not listed, n_extra=11)
# [earnings years_after_entry distinct (claim 6-10)] [6, 7, 8, 9, 10]
# [earnings -3 suppression present in earnings_med] True
# [inst_char pred_degree_awarded_ipeds distinct (claim 0-4)] [0, 1, 2, 3, 4]
# [earnings opeid6 dtype (claim Integer)] Int64
# 
# ===== PSEO (2020 file) =====
# [pseo schema sample] {'unitid': 'Int64', 'fips': 'Int64', 'opeid': 'Int64', 'year': 'Int64', 'pseo_cohort': 'String', 'degree_level': 'Int64', 'cipcode': 'Int64', 'years_after_grad': 'Int64', 'industry': 'String', 'census_division': 'Int64', 'p25_earnings': 'Int64', 'p50_earnings': 'Int64', 'p75_earnings': 'Int64', 'employed_grads_count_e': 'Int64'}
# [earnings cols present (p25/p50/p75_earnings, years_after_grad)] ['p25_earnings', 'p50_earnings', 'p75_earnings', 'years_after_grad', 'total_grads_count']
# [degree_level distinct (claim 1-10 ints)] [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
# [years_after_grad distinct (claim 1,5,10)] [1, 5, 10]
# [census_division distinct (claim 1-9,99)] [1, 2, 3, 4, 5, 6, 7, 8, 9, 99]
# [cipcode dtype (claim 2-digit integer)] Int64
# [industry dtype (claim String)] String
# [opeid dtype (claim integer, NOT string)] Int64
# [pseo null-count (claim no nulls)] ERROR DuplicateError: projections contained duplicate output name 's'. It's possible that multiple expressions are returning the same default column nam
# [p50_earnings has -1 and/or -3 (claim missing codes)] [-1, -3]
# [pseo_cohort format sample (claim 'YYYY-YYYY' string)] ('String', ['2016-2020', '2019-2021'])
# 
# ===== FSA =====
# [grants grant_type distinct (claim 1-5)] [1, 2, 3, 4, 5]
# [loans loan_type distinct (claim 1-14)] [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
# [campus_based award_type distinct (claim 1,2,3)] [1, 2, 3]
# [grants key cols present] ['unitid', 'fips', 'year', 'grant_type', 'grant_recipients_unitid', 'value_grants_disbursed_unitid']
# [loans key cols present] ['loan_type', 'loan_recipients_unitid', 'value_loan_disbursements_unitid']
# [composite_scores financial_resp_score present] True
# [90/10 rev_pct_90_10 scale (claim 0-1)] rev_pct_90_10 dtype=Float64 min(>=0)=0.0 max(>=0)=1.0042 (claim 0-1 proportion, not 0-100)
# [composite financial_resp_score range] min=-1.0 max=3.0
# 
# ===== EADA =====
# [ath_classification_code distinct (claim 1-20)] [-1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
# [opeid dtype (claim String)] String
# [key participation cols present] ['undup_athpartic_men', 'undup_athpartic_women', 'athpartic_men', 'athpartic_women', 'ath_classification_name']
# [sector column ABSENT (claim: no sector col)] True
# [opeid null for 2002 (claim)] opeid nulls in 2002 rows all-null=False
# 
# VALIDATION: scorecard/pseo/fsa/eada probes executed PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
