#!/usr/bin/env python3
"""
Python canonical-read capture for the mirror parquet equivalence audit.

INTENT: read each test parquet via the canonical Python path (pl.read_parquet)
and emit a language-neutral JSON capture per dataset. A parallel R script emits
the same schema from the canonical view-safe R read; a third script diffs the two
JSON sets programmatically. No eyeball comparison.

Captured per dataset (mirrors the 7-check test matrix + int64 depth):
  1. shape + column names/order
  2. per-column logical type (polars dtype string)
  3. per-column null counts
  4. sentinel counts (-1,-2,-3) in numeric columns
  5. deterministic value sample: sort by pkey, first5+last5 rows, ALL columns,
     values rendered as canonical strings (ints exact; floats round-trip repr;
     nulls as a sentinel token) so cross-language byte comparison is unambiguous
  6. string integrity: NA-vs-empty counts per string col; leading-zero ID scan;
     non-ASCII value inventory (value + codepoints) for byte-identity check
  7. distinct-value counts on key columns
  int64 depth: for every integer column, min/max, whether |max|>=2^31, and the
     exact min/max rendered as decimal strings (so R downcast/precision loss shows)
"""

# --- Config ---
import os
import json
import polars as pl

SCRATCH = "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
OUT = os.path.join(SCRATCH, "capture_python.json")

# INTENT: (dataset_key, filename, primary_key_cols, id_cols_expected_zeropad).
# pkey drives deterministic sort for sample rows; id_cols get leading-zero checks.
DATASETS = [
    ("saipe", "saipe_districts_FAILING.parquet", ["year", "leaid"], ["leaid"]),
    ("meps", "meps_schools_WORKING.parquet", ["year", "ncessch"], ["ncessch", "leaid"]),
    ("edfacts", "edfacts_grad_rates_2018.parquet", ["year", "ncessch"], ["ncessch", "leaid"]),
    ("crdc", "crdc_discipline_2017.parquet", ["year", "ncessch"], ["crdc_id", "ncessch", "leaid"]),
    ("ipeds", "ipeds_finance.parquet", ["year", "unitid"], ["unitid"]),
]

SENTINELS = [-1, -2, -3]
TWO_31 = 2 ** 31

# REASONING: canonical string rendering. Integers -> exact decimal str. Floats ->
#   repr() which round-trips IEEE754 in Python; R must match its own float->str,
#   so the diff script applies float tolerance rather than requiring byte equality
#   on floats (we tag each cell with its type-class to let the differ choose).
def render_cell(v, dtype_class):
    if v is None:
        return {"t": "null", "v": None}
    if dtype_class == "int":
        return {"t": "int", "v": str(int(v))}
    if dtype_class == "float":
        # ASSUMES: NaN distinct from null; render both explicitly.
        if v != v:
            return {"t": "float", "v": "NaN"}
        return {"t": "float", "v": repr(float(v))}
    if dtype_class == "bool":
        return {"t": "bool", "v": bool(v)}
    # string / other
    return {"t": "str", "v": str(v)}

def dtype_class(dt):
    if dt in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
        return "int"
    if dt in (pl.Float32, pl.Float64):
        return "float"
    if dt == pl.Boolean:
        return "bool"
    if dt in (pl.Utf8, pl.String):
        return "str"
    return "other"

# --- Load + Profile ---
result = {"engine": "polars", "polars_version": pl.__version__, "datasets": {}}

for key, fname, pkey, id_cols in DATASETS:
    path = os.path.join(SCRATCH, fname)
    print(f"\n### {key}: {fname}")

    # INTENT: canonical Python read. Exactly the documented pattern pl.read_parquet.
    df = pl.read_parquet(path)
    cols = df.columns
    dtypes = {c: str(df.schema[c]) for c in cols}
    classes = {c: dtype_class(df.schema[c]) for c in cols}
    print(f"    shape: {df.shape}")

    cap = {
        "shape": [df.height, df.width],
        "columns": cols,
        "dtypes": dtypes,
        "dtype_class": classes,
        "null_counts": {},
        "sentinel_counts": {},
        "int_stats": {},
        "string_integrity": {},
        "distinct_counts": {},
        "sample_rows": {},
    }

    # --- null counts (all columns) ---
    nulls = df.null_count().to_dicts()[0]
    cap["null_counts"] = {c: int(nulls[c]) for c in cols}

    # --- sentinel counts (numeric columns only) ---
    for c in cols:
        if classes[c] in ("int", "float"):
            sc = {}
            for s in SENTINELS:
                # REASONING: exact equality; for float cols -1.0==-1 holds. Nulls excluded.
                sc[str(s)] = int(df.select((pl.col(c) == s).sum()).item() or 0)
            cap["sentinel_counts"][c] = sc

    # --- int stats + int64 depth (integer columns) ---
    for c in cols:
        if classes[c] == "int":
            nn = df.select(pl.col(c).drop_nulls())
            if nn.height == 0:
                cap["int_stats"][c] = {"min": None, "max": None, "exceeds_2_31": False, "dtype": dtypes[c]}
                continue
            cmin = df.select(pl.col(c).min()).item()
            cmax = df.select(pl.col(c).max()).item()
            exceeds = (cmin is not None and abs(int(cmin)) >= TWO_31) or (cmax is not None and abs(int(cmax)) >= TWO_31)
            cap["int_stats"][c] = {
                "min": str(int(cmin)) if cmin is not None else None,
                "max": str(int(cmax)) if cmax is not None else None,
                "exceeds_2_31": bool(exceeds),
                "dtype": dtypes[c],
            }

    # --- string integrity (string columns) ---
    for c in cols:
        if classes[c] != "str":
            continue
        n_null = int(df.select(pl.col(c).is_null().sum()).item())
        n_empty = int(df.select((pl.col(c) == "").sum()).item() or 0)
        si = {"n_null": n_null, "n_empty": n_empty}
        # leading-zero check for declared id columns
        if c in id_cols:
            n_leadzero = int(df.select(
                (pl.col(c).str.starts_with("0") & (pl.col(c).str.len_chars() > 1)).sum()
            ).item() or 0)
            # sample a few leading-zero values for byte comparison
            lz_vals = (df.filter(pl.col(c).str.starts_with("0") & (pl.col(c).str.len_chars() > 1))
                       .select(pl.col(c)).unique().sort(c).head(5).to_series().to_list())
            si["n_leading_zero"] = n_leadzero
            si["leading_zero_samples"] = lz_vals
        # non-ASCII inventory: values containing any codepoint > 127
        # REASONING: byte-identity is the real test; render codepoints so R can match.
        na_mask = df.filter(pl.col(c).is_not_null()).select(
            pl.col(c).map_elements(lambda x: any(ord(ch) > 127 for ch in x), return_dtype=pl.Boolean).alias("m")
        ).to_series()
        if na_mask.sum() and na_mask.sum() > 0:
            na_vals = (df.filter(pl.col(c).is_not_null())
                       .filter(pl.col(c).map_elements(lambda x: any(ord(ch) > 127 for ch in x), return_dtype=pl.Boolean))
                       .select(pl.col(c)).unique().sort(c).head(10).to_series().to_list())
            si["non_ascii_count_est"] = int(na_mask.sum())
            si["non_ascii_samples"] = [{"value": v, "codepoints": [ord(ch) for ch in v]} for v in na_vals]
        else:
            si["non_ascii_count_est"] = 0
            si["non_ascii_samples"] = []
        cap["string_integrity"][c] = si

    # --- distinct counts on key columns (pkey + id cols, capped) ---
    key_cols = list(dict.fromkeys(pkey + id_cols))
    for c in key_cols:
        if c in cols:
            cap["distinct_counts"][c] = int(df.select(pl.col(c).n_unique()).item())

    # --- deterministic sample: sort by available pkey cols, first5 + last5 ---
    sort_cols = [c for c in pkey if c in cols]
    if not sort_cols:
        sort_cols = cols[:1]
    # REASONING: nulls_last for stable deterministic ordering across languages.
    dfs = df.sort(sort_cols, nulls_last=True)
    head = dfs.head(5)
    tail = dfs.tail(5)
    def rows_to_cells(sub):
        out = []
        recs = sub.to_dicts()
        for r in recs:
            out.append({c: render_cell(r[c], classes[c]) for c in cols})
        return out
    cap["sample_rows"] = {
        "sort_cols": sort_cols,
        "head5": rows_to_cells(head),
        "tail5": rows_to_cells(tail),
    }

    result["datasets"][key] = cap
    print(f"    captured: {len(cols)} cols, {cap['null_counts']} nulls-summary-len={len(cap['null_counts'])}")

# --- Save ---
with open(OUT, "w") as f:
    json.dump(result, f, indent=1, ensure_ascii=True, sort_keys=True)
print(f"\nWrote {OUT}")

# --- Summary ---
print("\n" + "=" * 70)
for key in result["datasets"]:
    d = result["datasets"][key]
    n_view_risk_cols = sum(1 for c in d["dtype_class"] if d["dtype_class"][c] == "str")
    exceed = [c for c in d["int_stats"] if d["int_stats"][c]["exceeds_2_31"]]
    print(f"{key:9s} shape={d['shape']} str_cols={n_view_risk_cols} int_cols_ge_2^31={exceed}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:25:52
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/02_python-capture.py
# Duration: 26s
# Exit code: 0
#
# --- STDOUT ---
# 
# ### saipe: saipe_districts_FAILING.parquet
#     shape: (368967, 10)
#     captured: 10 cols, {'district_id': 0, 'district_name': 0, 'est_population_total': 0, 'est_population_5_17': 0, 'est_population_5_17_poverty': 0, 'year': 0, 'leaid': 0, 'fips': 0, 'est_population_5_17_poverty_pct': 275, 'est_population_5_17_pct': 121} nulls-summary-len=10
# 
# ### meps: meps_schools_WORKING.parquet
#     shape: (1345122, 11)
#     captured: 11 cols, {'year': 0, 'fips': 0, 'gleaid': 0, 'ncessch': 0, 'meps_poverty_pct': 29309, 'meps_poverty_se': 22268, 'meps_mod_poverty_pct': 30165, 'meps_poverty_ptl': 29309, 'meps_mod_poverty_ptl': 30165, 'ncessch_num': 0, 'leaid': 258} nulls-summary-len=11
# 
# ### edfacts: edfacts_grad_rates_2018.parquet
#     shape: (274800, 18)
#     captured: 18 cols, {'ncessch_num': 0, 'ncessch': 0, 'year': 0, 'school_name': 0, 'leaid_num': 0, 'leaid': 0, 'lea_name': 0, 'fips': 0, 'race': 0, 'lep': 0, 'homeless': 0, 'disability': 0, 'econ_disadvantaged': 0, 'foster_care': 0, 'cohort_num': 81047, 'grad_rate_low': 81047, 'grad_rate_high': 81047, 'grad_rate_midpt': 81047} nulls-summary-len=18
# 
# ### crdc: crdc_discipline_2017.parquet
#     shape: (8487765, 20)
#     captured: 20 cols, {'crdc_id': 0, 'year': 0, 'ncessch': 81816, 'leaid': 81816, 'fips': 0, 'race': 0, 'sex': 0, 'disability': 0, 'lep': 0, 'revised_flag': 8487765, 'expulsions_with_ed_serv': 0, 'expulsions_no_ed_serv': 0, 'expulsions_zero_tolerance': 0, 'students_susp_in_sch': 0, 'students_susp_out_sch_single': 0, 'students_susp_out_sch_multiple': 0, 'students_corporal_punish': 0, 'students_referred_law_enforce': 0, 'students_arrested': 0, 'transfers_alt_sch_disc': 0} nulls-summary-len=20
# 
# ### ipeds: ipeds_finance.parquet
#     shape: (227084, 141)
#     captured: 141 cols, {'unitid': 0, 'year': 0, 'fips': 177, 'rev_tuition_fees_gross': 45752, 'rev_tuition_fees_net': 103305, 'rev_appropriations_fed': 213173, 'rev_appropriations_state': 160082, 'rev_appropriations_local': 202011, 'rev_grants_contracts_federal': 122650, 'rev_grants_contracts_state': 145839, 'rev_grants_contracts_local': 188053, 'rev_fed_approps_grants': 108782, 'rev_state_local_approps_grants': 127906, 'rev_gifts_grants_contracts': 134625, 'rev_affiliated_entities': 220519, 'rev_investment_return': 152301, 'rev_edu_services_sales': 152910, 'rev_auxiliary_enterprises_gross': 114600, 'rev_auxiliary_enterprises_net': 166952, 'rev_independent_operations': 220140, 'rev_other_operating': 193193, 'rev_other_nonoperating': 210334, 'rev_other_additions': 220824, 'rev_other': 97925, 'rev_hospital': 224002, 'rev_hosp_ind_op_other': 95402, 'rev_operating': 194617, 'rev_nonoperating': 194940, 'rev_capital_approps': 211141, 'rev_capital_grants_gifts': 213975, 'rev_endowment_income': 209021, 'rev_endowment_additions': 221745, 'rev_additions': 204052, 'rev_total_current': 43564, 'sch_pell_grant': 65653, 'sch_other_federal_grants': 106353, 'sch_grants_state': 144411, 'sch_grants_local': 216116, 'sch_grants_state_local': 129014, 'sch_restricted_inst_grants': 164412, 'sch_unrestricted_inst_grants': 152843, 'sch_grants_institutional': 115925, 'sch_grants_private': 202898, 'sch_total_student_aid': 63207, 'sch_allowances_tuition_fees': 148115, 'sch_allowances_aux_enterp': 207211, 'sch_allowances_total': 196210, 'sch_exp_net_fellowships': 199486, 'exp_instruc_total': 45002, 'exp_instruc_salaries': 102526, 'exp_research_total': 185392, 'exp_research_salaries': 194867, 'exp_pub_serv_total': 162049, 'exp_pub_serv_salaries': 177778, 'exp_res_pub_serv_total': 149920, 'exp_res_pub_serv_salaries': 169946, 'exp_acad_supp_total': 90568, 'exp_acad_supp_salaries': 115419, 'exp_student_serv_total': 89770, 'exp_student_serv_salaries': 113783, 'exp_inst_supp_total': 84802, 'exp_inst_supp_salaries': 109273, 'exp_acad_inst_student_total': 49460, 'exp_acad_inst_student_salaries': 105513, 'exp_aux_ent_total': 116097, 'exp_aux_ent_salaries': 169673, 'exp_net_grant_aid_total': 143921, 'exp_net_grant_aid_salaries': 225881, 'exp_hospital_total': 223955, 'exp_hospital_salaries': 225306, 'exp_ind_op_total': 222565, 'exp_ind_op_salaries': 225012, 'exp_other_total_funct': 145916, 'exp_other_salaries': 216283, 'exp_total_current': 56672, 'exp_total_salaries': 97479, 'exp_total_benefits': 104270, 'exp_total_opm': 117960, 'exp_total_depr': 160371, 'exp_total_interest': 182170, 'exp_total_other_nat': 145170, 'endowment_beg': 180879, 'endowment_end': 180722, 'own_endowment_assets': 155565, 'longterm_investments': 197015, 'depr_capital_assets': 210243, 'assets': 134464, 'liabilities': 135029, 'assets_net': 168453, 'def_outflows_resources': 223127, 'longterm_debt': 206335, 'def_inflows_resources': 223251, 'invest_capital_assets': 201022, 'position_net': 222542, 'plant_prop_equip_debt': 214944, 'equity_total': 198066, 'land_improvements': 128375, 'infrastructure': 213016, 'buildings': 129464, 'equipment': 125899, 'construction_in_progress': 196178, 'other_plant_prop_equip': 221996, 'plant_property_equipment': 119779, 'depreciation_accumulated': 182401, 'intangible_assets_net': 222484, 'capital_assets_other': 225517, 'plant_prop_equip_net': 207605, 'total_revenues_additions': 124965, 'total_expenses_deductions': 124919, 'equity_changes_total': 215007, 'income_net': 162288, 'equity_changes_other': 202071, 'equity_beg': 163918, 'net_equity_beg_adjust': 203004, 'equity_end': 162881, 'net_position_change': 198920, 'net_position_beginning': 200651, 'net_position_adjustments': 213564, 'net_position_end': 200514, 'income_tax_fed': 225335, 'income_tax_state': 225327, 'pension_info_reported': 219170, 'def_inflows_pension': 221590, 'def_outflows_pension': 221504, 'pension_expense': 222888, 'net_pension_liability': 222921, 'parent_child_flag': 50887, 'parent_child_system_flag': 205553, 'parent_unitid': 60346, 'parent_child_allocation': 219409, 'reporting_form': 83139, 'form_type': 37476, 'gasb_alternative_accounting': 83139, 'pell_grant_treatment': 177095, 'athletic_expense_treatment': 124010, 'cpi': 0, 'hepi': 6857, 'heca': 6857, 'est_fte': 77308, 'rep_fte': 77308, 'calc_fte': 37424} nulls-summary-len=141
# 
# Wrote /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/capture_python.json
# 
# ======================================================================
# saipe     shape=[368967, 10] str_cols=1 int_cols_ge_2^31=[]
# meps      shape=[1345122, 11] str_cols=0 int_cols_ge_2^31=['ncessch', 'ncessch_num']
# edfacts   shape=[274800, 18] str_cols=2 int_cols_ge_2^31=['ncessch_num', 'ncessch']
# crdc      shape=[8487765, 20] str_cols=4 int_cols_ge_2^31=[]
# ipeds     shape=[227084, 141] str_cols=0 int_cols_ge_2^31=[]
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
