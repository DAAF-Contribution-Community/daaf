# --- Config ---
# INTENT: Verify EVERY documented IPEDS column table (exact column sets + counts) and
#         key coded-value / value-scale claims against the pinned mirror, via projected
#         schema reads + tiny distinct/aggregate scans (near-free over HTTP).
# REASONING: The IPEDS references publish "Verified" column tables and coded-value tables;
#            adversarial re-proof compares documented-vs-present column sets and distinct
#            code sets, flagging DOCUMENTED-NOT-PRESENT and PRESENT-NOT-DOCUMENTED separately.
# ASSUMES: pinned public repo; polars scan_parquet over HTTPS with column projection.
# Skills under test: education-data-source-ipeds/references/survey-components.md,
#   financial-aid.md, graduation-rates.md; SKILL.md coded-value tables.
import polars as pl

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

def schema(rel):
    return dict(pl.scan_parquet(f"{BASE}/{rel}.parquet").collect_schema())

def cols(rel):
    return set(schema(rel).keys())

results = []
def check_colset(label, rel, documented, exact_count=None):
    # INTENT: compare documented column set to actual; report missing/extra separately.
    try:
        sc = schema(rel)
        actual = set(sc.keys())
        doc = set(documented)
        missing = sorted(doc - actual)   # DOCUMENTED-NOT-PRESENT
        extra = sorted(actual - doc)     # PRESENT-NOT-DOCUMENTED
        n = len(actual)
        cnt_ok = (exact_count is None) or (n == exact_count)
        verdict = "VERIFIED" if (not missing and cnt_ok and (exact_count is not None or not extra)) else "REVIEW"
        if missing:
            verdict = "CONTRADICTED"
        print(f"[{label}] {rel}")
        print(f"    actual_cols={n} documented={len(doc)} exact_count_claim={exact_count} count_ok={cnt_ok}")
        if missing: print(f"    DOCUMENTED-NOT-PRESENT: {missing}")
        if extra:   print(f"    PRESENT-NOT-DOCUMENTED: {extra}")
        print(f"    dtypes(sample)={{ {', '.join(f'{k}:{sc[k]}' for k in list(sc)[:6])} }}")
        print(f"    VERDICT={verdict}")
        results.append((label, verdict, n, exact_count, missing, extra))
        return sc
    except Exception as e:
        print(f"[{label}] {rel} ERROR {type(e).__name__}: {str(e)[:140]}  VERDICT=UNTESTABLE")
        results.append((label, "UNTESTABLE", None, exact_count, None, None))
        return {}

# ===== survey-components.md column tables =====
check_colset("enrollment-fte 9col", "ipeds/colleges_ipeds_enrollment-fte",
    ["unitid","year","fips","level_of_study","acttype","credit_hours","contact_hours","est_fte","rep_fte"], 9)
check_colset("admissions-enrollment 9col", "ipeds/colleges_ipeds_admissions-enrollment",
    ["unitid","year","fips","sex","number_applied","number_admitted","number_enrolled_ft","number_enrolled_pt","number_enrolled_total"], 9)
check_colset("fall-enrollment-race 10col(2020)", "ipeds/colleges_ipeds_fall-enrollment-race_2020",
    ["unitid","year","fips","sex","race","ftpt","level_of_study","degree_seeking","class_level","enrollment_fall"], 10)
check_colset("fall-retention 9col", "ipeds/colleges_ipeds_fall-retention",
    ["unitid","year","fips","ftpt","retention_rate","returning_students","prev_cohort","prev_exclusions","prev_cohort_adj"], 9)
check_colset("headcount 7col", "ipeds/colleges_ipeds_headcount",
    ["unitid","year","fips","headcount","level_of_study","race","sex"], 7)
check_colset("fall-res 6col", "ipeds/colleges_ipeds_fall-res",
    ["unitid","year","fips","enrollment_fall","state_of_residence","type_of_freshman"], 6)
check_colset("student-faculty-ratio 4col", "ipeds/colleges_ipeds_student-faculty-ratio",
    ["unitid","year","fips","student_faculty_ratio"], 4)
check_colset("salaries_is 11col", "ipeds/colleges_ipeds_salaries_is",
    ["unitid","year","fips","academic_rank","contract_length","sex","instruc_staff_count","salary_outlays","average_salary","total_months","avg_wgtd_mon_salary"], 11)
check_colset("salaries_nis 6col", "ipeds/colleges_ipeds_salaries_nis",
    ["unitid","year","fips","staff_category","noninstruc_staff_count","salary_outlays"], 6)

# finance: claim = 141 cols; verify count + presence of selected named columns
fin = check_colset("finance 141col(selected-names)", "ipeds/colleges_ipeds_finance",
    ["unitid","year","fips","form_type","reporting_form","gasb_alternative_accounting","parent_child_flag","parent_unitid",
     "rev_tuition_fees_gross","rev_tuition_fees_net","rev_appropriations_state","rev_total_current",
     "exp_instruc_total","exp_total_current","sch_pell_grant","assets","liabilities","endowment_beg","endowment_end",
     "est_fte","rep_fte","calc_fte","cpi","heca","hepi"], 141)

# ===== financial-aid.md SFA column tables =====
check_colset("sfa_ftft 12col", "ipeds/colleges_ipeds_sfa_ftft",
    ["unitid","year","fips","type_of_aid","ftpt","level_of_study","class_level","degree_seeking","number_of_students","percent_of_students","average_amount","total_amount"], 12)
check_colset("sfa_grants_and_net_price 15col", "ipeds/colleges_ipeds_sfa_grants_and_net_price",
    ["unitid","year","fips","type_of_aid","income_level","ftpt","level_of_study","class_level","degree_seeking","tuition_type","number_of_students","number_receiving_grants","total_grant","average_grant","net_price"], 15)
check_colset("sfa_all_undergrads 10col", "ipeds/colleges_ipeds_sfa_all_undergrads",
    ["unitid","year","fips","type_of_aid","ftpt","level_of_study","number_of_students","percent_of_students","average_amount","total_amount"], 10)
check_colset("sfa_by_living_arrangement 11col", "ipeds/colleges_ipeds_sfa_by_living_arrangement",
    ["unitid","year","fips","type_of_aid","living_arrangement","ftpt","level_of_study","class_level","degree_seeking","tuition_type","number_of_students"], 11)
check_colset("sfa_by_tuition_type 12col", "ipeds/colleges_ipeds_sfa_by_tuition_type",
    ["unitid","year","fips","tuition_type","type_of_cohort","ftpt","level_of_study","class_level","degree_seeking","number_of_students","percent_of_cohort","percent_of_undergrads"], 12)

# ===== graduation-rates.md =====
# GR key variable presence (not an exact-count claim)
gr_expected = ["unitid","year","cohort_year","cohort_adj_150pct","cohort_rev","completers_150pct","completers_100pct",
    "completion_rate_150pct","transfers_out","still_enrolled","still_enrolled_long_program","no_longer_enrolled",
    "exclusions","subcohort","race","sex","institution_level"]
grsc = check_colset("grad-rates GR-vars(presence)", "ipeds/colleges_ipeds_grad-rates", gr_expected, None)
# OM 38 cols exact
om_expected = ["unitid","year","fips","cohort_year","class_level","ftpt","fed_aid_type","cohort_adj","cohort_adj_6yr",
    "cohort_adj_8yr","cohort_rev","cohort_rev_6yr","exclusions","exclusions_6yr","exclusions_add_8yr","completers_4yr",
    "completers_6yr","completers_8yr","award_cert_4yr","award_cert_6yr","award_cert_8yr","award_assoc_4yr","award_assoc_6yr",
    "award_assoc_8yr","award_bach_4yr","award_bach_6yr","award_bach_8yr","completion_rate_4yr","completion_rate_6yr",
    "completion_rate_8yr","transfer_8yr","transfer_rate_8yr","still_enroll_8yr","still_enroll_rate_8yr",
    "still_enroll_transfer_rate_8yr","no_award_8yr","unknown_8yr","unknown_rate_8yr"]
check_colset("outcome-measures 38col", "ipeds/colleges_ipeds_outcome-measures", om_expected, 38)

# ===== Coded values & value scales =====
print("\n=== CODED VALUES / SCALES ===")
def distinct(rel, col, pred=None):
    lf = pl.scan_parquet(f"{BASE}/{rel}.parquet").select(col)
    if pred is not None:
        lf = lf.filter(pred)
    return sorted(v for v in lf.unique().collect()[col].to_list() if v is not None)

def probe(label, fn):
    try:
        print(f"[{label}] {fn()}")
    except Exception as e:
        print(f"[{label}] ERROR {type(e).__name__}: {str(e)[:120]}")

# grad rate 0-1 scale claim (data-quality: 0-1 proportions, not 0-100)
def gr_scale():
    s = (pl.scan_parquet(f"{BASE}/ipeds/colleges_ipeds_grad-rates.parquet")
         .select(pl.col("completion_rate_150pct").min().alias("mn"),
                 pl.col("completion_rate_150pct").max().alias("mx")).collect())
    return f"min={s['mn'][0]} max={s['mx'][0]} (claim: 0-1 proportions)"
probe("grad completion_rate_150pct scale", gr_scale)
probe("grad subcohort distinct (claim 1,2,99)", lambda: distinct("ipeds/colleges_ipeds_grad-rates","subcohort"))
probe("OM class_level distinct (claim 1,2,99)", lambda: distinct("ipeds/colleges_ipeds_outcome-measures","class_level"))
probe("OM ftpt distinct (claim 1,2,99)", lambda: distinct("ipeds/colleges_ipeds_outcome-measures","ftpt"))
probe("OM fed_aid_type distinct (claim 1,4,99)", lambda: distinct("ipeds/colleges_ipeds_outcome-measures","fed_aid_type"))
probe("sfa_grants income_level distinct (claim 1-5,99)", lambda: distinct("ipeds/colleges_ipeds_sfa_grants_and_net_price","income_level"))
probe("sfa_grants type_of_aid distinct (claim 3,9)", lambda: distinct("ipeds/colleges_ipeds_sfa_grants_and_net_price","type_of_aid"))
probe("sfa_ftft type_of_aid distinct (claim 1,2,3,4,5,7,8,10,11,12)", lambda: distinct("ipeds/colleges_ipeds_sfa_ftft","type_of_aid"))
probe("sfa_all_undergrads type_of_aid distinct (claim 3,5,11)", lambda: distinct("ipeds/colleges_ipeds_sfa_all_undergrads","type_of_aid"))
probe("salaries_is academic_rank distinct (claim 1-6,99)", lambda: distinct("ipeds/colleges_ipeds_salaries_is","academic_rank"))
probe("salaries_nis staff_category distinct (claim 2-14,99)", lambda: distinct("ipeds/colleges_ipeds_salaries_nis","staff_category"))
probe("finance form_type distinct (claim 1-5)", lambda: distinct("ipeds/colleges_ipeds_finance","form_type"))
# directory coded values
probe("directory inst_control distinct (claim 1,2,3,-1)", lambda: distinct("ipeds/colleges_ipeds_directory","inst_control"))
probe("directory institution_level distinct (claim 1,2,4,-1; NO 3)", lambda: distinct("ipeds/colleges_ipeds_directory","institution_level"))
probe("directory sector distinct (claim 0-9,-1)", lambda: distinct("ipeds/colleges_ipeds_directory","sector"))

# --- Validate ---
n_contra = sum(1 for r in results if r[1] == "CONTRADICTED")
n_review = sum(1 for r in results if r[1] == "REVIEW")
n_ok = sum(1 for r in results if r[1] == "VERIFIED")
print(f"\n=== TALLY (column-table checks) ===")
print(f"VERIFIED={n_ok} REVIEW(count/extra mismatch)={n_review} CONTRADICTED={n_contra} UNTESTABLE={sum(1 for r in results if r[1]=='UNTESTABLE')}")
assert len(results) >= 17, "expected 17+ column-table checks"
print("VALIDATION: column-table checks executed PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:13:44
# Command: python3 /daaf/scripts/mirror_maintenance/29_doc-audit-ipeds-schema_a.py
# Duration: 26s
# Exit code: 0
#
# --- STDOUT ---
# [enrollment-fte 9col] ipeds/colleges_ipeds_enrollment-fte
#     actual_cols=9 documented=9 exact_count_claim=9 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, level_of_study:Int64, credit_hours:Int64, contact_hours:Int64, acttype:Int64 }
#     VERDICT=VERIFIED
# [admissions-enrollment 9col] ipeds/colleges_ipeds_admissions-enrollment
#     actual_cols=9 documented=9 exact_count_claim=9 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, sex:Int64, number_applied:Int64, number_admitted:Int64 }
#     VERDICT=VERIFIED
# [fall-enrollment-race 10col(2020)] ipeds/colleges_ipeds_fall-enrollment-race_2020
#     actual_cols=10 documented=10 exact_count_claim=10 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, sex:Int64, race:Int64, ftpt:Int64 }
#     VERDICT=VERIFIED
# [fall-retention 9col] ipeds/colleges_ipeds_fall-retention
#     actual_cols=10 documented=9 exact_count_claim=9 count_ok=False
#     PRESENT-NOT-DOCUMENTED: ['prev_inclusions']
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, ftpt:Int64, retention_rate:Float64, returning_students:String }
#     VERDICT=REVIEW
# [headcount 7col] ipeds/colleges_ipeds_headcount
#     actual_cols=7 documented=7 exact_count_claim=7 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, level_of_study:Int64, race:Int64, sex:Int64 }
#     VERDICT=VERIFIED
# [fall-res 6col] ipeds/colleges_ipeds_fall-res
#     actual_cols=6 documented=6 exact_count_claim=6 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, state_of_residence:Int64, type_of_freshman:Int64, enrollment_fall:Int64 }
#     VERDICT=VERIFIED
# [student-faculty-ratio 4col] ipeds/colleges_ipeds_student-faculty-ratio
#     actual_cols=4 documented=4 exact_count_claim=4 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, student_faculty_ratio:Int64 }
#     VERDICT=VERIFIED
# [salaries_is 11col] ipeds/colleges_ipeds_salaries_is
#     actual_cols=11 documented=11 exact_count_claim=11 count_ok=True
#     dtypes(sample)={ year:Int64, unitid:Int64, fips:Int64, academic_rank:Int64, contract_length:Int64, sex:Int64 }
#     VERDICT=VERIFIED
# [salaries_nis 6col] ipeds/colleges_ipeds_salaries_nis
#     actual_cols=6 documented=6 exact_count_claim=6 count_ok=True
#     dtypes(sample)={ year:Int64, unitid:Int64, fips:Int64, staff_category:Int64, noninstruc_staff_count:Float64, salary_outlays:Float64 }
#     VERDICT=VERIFIED
# [finance 141col(selected-names)] ipeds/colleges_ipeds_finance
#     actual_cols=141 documented=25 exact_count_claim=141 count_ok=True
#     PRESENT-NOT-DOCUMENTED: ['assets_net', 'athletic_expense_treatment', 'buildings', 'capital_assets_other', 'construction_in_progress', 'def_inflows_pension', 'def_inflows_resources', 'def_outflows_pension', 'def_outflows_resources', 'depr_capital_assets', 'depreciation_accumulated', 'equipment', 'equity_beg', 'equity_changes_other', 'equity_changes_total', 'equity_end', 'equity_total', 'exp_acad_inst_student_salaries', 'exp_acad_inst_student_total', 'exp_acad_supp_salaries', 'exp_acad_supp_total', 'exp_aux_ent_salaries', 'exp_aux_ent_total', 'exp_hospital_salaries', 'exp_hospital_total', 'exp_ind_op_salaries', 'exp_ind_op_total', 'exp_inst_supp_salaries', 'exp_inst_supp_total', 'exp_instruc_salaries', 'exp_net_grant_aid_salaries', 'exp_net_grant_aid_total', 'exp_other_salaries', 'exp_other_total_funct', 'exp_pub_serv_salaries', 'exp_pub_serv_total', 'exp_res_pub_serv_salaries', 'exp_res_pub_serv_total', 'exp_research_salaries', 'exp_research_total', 'exp_student_serv_salaries', 'exp_student_serv_total', 'exp_total_benefits', 'exp_total_depr', 'exp_total_interest', 'exp_total_opm', 'exp_total_other_nat', 'exp_total_salaries', 'income_net', 'income_tax_fed', 'income_tax_state', 'infrastructure', 'intangible_assets_net', 'invest_capital_assets', 'land_improvements', 'longterm_debt', 'longterm_investments', 'net_equity_beg_adjust', 'net_pension_liability', 'net_position_adjustments', 'net_position_beginning', 'net_position_change', 'net_position_end', 'other_plant_prop_equip', 'own_endowment_assets', 'parent_child_allocation', 'parent_child_system_flag', 'pell_grant_treatment', 'pension_expense', 'pension_info_reported', 'plant_prop_equip_debt', 'plant_prop_equip_net', 'plant_property_equipment', 'position_net', 'rev_additions', 'rev_affiliated_entities', 'rev_appropriations_fed', 'rev_appropriations_local', 'rev_auxiliary_enterprises_gross', 'rev_auxiliary_enterprises_net', 'rev_capital_approps', 'rev_capital_grants_gifts', 'rev_edu_services_sales', 'rev_endowment_additions', 'rev_endowment_income', 'rev_fed_approps_grants', 'rev_gifts_grants_contracts', 'rev_grants_contracts_federal', 'rev_grants_contracts_local', 'rev_grants_contracts_state', 'rev_hosp_ind_op_other', 'rev_hospital', 'rev_independent_operations', 'rev_investment_return', 'rev_nonoperating', 'rev_operating', 'rev_other', 'rev_other_additions', 'rev_other_nonoperating', 'rev_other_operating', 'rev_state_local_approps_grants', 'sch_allowances_aux_enterp', 'sch_allowances_total', 'sch_allowances_tuition_fees', 'sch_exp_net_fellowships', 'sch_grants_institutional', 'sch_grants_local', 'sch_grants_private', 'sch_grants_state', 'sch_grants_state_local', 'sch_other_federal_grants', 'sch_restricted_inst_grants', 'sch_total_student_aid', 'sch_unrestricted_inst_grants', 'total_expenses_deductions', 'total_revenues_additions']
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, rev_tuition_fees_gross:Float64, rev_tuition_fees_net:Float64, rev_appropriations_fed:Float64 }
#     VERDICT=VERIFIED
# [sfa_ftft 12col] ipeds/colleges_ipeds_sfa_ftft
#     actual_cols=12 documented=12 exact_count_claim=12 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, ftpt:Int64, class_level:Int64, level_of_study:Int64 }
#     VERDICT=VERIFIED
# [sfa_grants_and_net_price 15col] ipeds/colleges_ipeds_sfa_grants_and_net_price
#     actual_cols=15 documented=15 exact_count_claim=15 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, ftpt:Int64, level_of_study:Int64, degree_seeking:Int64 }
#     VERDICT=VERIFIED
# [sfa_all_undergrads 10col] ipeds/colleges_ipeds_sfa_all_undergrads
#     actual_cols=10 documented=10 exact_count_claim=10 count_ok=True
#     dtypes(sample)={ level_of_study:Int64, type_of_aid:Int64, unitid:Int64, year:Int64, fips:Int64, ftpt:Int64 }
#     VERDICT=VERIFIED
# [sfa_by_living_arrangement 11col] ipeds/colleges_ipeds_sfa_by_living_arrangement
#     actual_cols=11 documented=11 exact_count_claim=11 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, ftpt:Int64, level_of_study:Int64, degree_seeking:Int64 }
#     VERDICT=VERIFIED
# [sfa_by_tuition_type 12col] ipeds/colleges_ipeds_sfa_by_tuition_type
#     actual_cols=12 documented=12 exact_count_claim=12 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, ftpt:Int64, level_of_study:Int64, degree_seeking:Int64 }
#     VERDICT=VERIFIED
# [grad-rates GR-vars(presence)] ipeds/colleges_ipeds_grad-rates
#     actual_cols=18 documented=17 exact_count_claim=None count_ok=True
#     PRESENT-NOT-DOCUMENTED: ['fips']
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, cohort_year:Int64, institution_level:Int64, subcohort:Int64 }
#     VERDICT=REVIEW
# [outcome-measures 38col] ipeds/colleges_ipeds_outcome-measures
#     actual_cols=38 documented=38 exact_count_claim=38 count_ok=True
#     dtypes(sample)={ unitid:Int64, year:Int64, fips:Int64, ftpt:Int64, class_level:Int64, fed_aid_type:Int64 }
#     VERDICT=VERIFIED
# 
# === CODED VALUES / SCALES ===
# [grad completion_rate_150pct scale] min=-1.0 max=1.0 (claim: 0-1 proportions)
# [grad subcohort distinct (claim 1,2,99)] [-2, 1, 2, 99]
# [OM class_level distinct (claim 1,2,99)] [1, 2, 99]
# [OM ftpt distinct (claim 1,2,99)] [1, 2, 99]
# [OM fed_aid_type distinct (claim 1,4,99)] [1, 4, 99]
# [sfa_grants income_level distinct (claim 1-5,99)] [1, 2, 3, 4, 5, 99]
# [sfa_grants type_of_aid distinct (claim 3,9)] [3, 9]
# [sfa_ftft type_of_aid distinct (claim 1,2,3,4,5,7,8,10,11,12)] [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12]
# [sfa_all_undergrads type_of_aid distinct (claim 3,5,11)] [3, 5, 11]
# [salaries_is academic_rank distinct (claim 1-6,99)] [1, 2, 3, 4, 5, 6, 99]
# [salaries_nis staff_category distinct (claim 2-14,99)] [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 99]
# [finance form_type distinct (claim 1-5)] [1, 2, 3, 4, 5]
# [directory inst_control distinct (claim 1,2,3,-1)] [-1, 1, 2, 3]
# [directory institution_level distinct (claim 1,2,4,-1; NO 3)] [-1, 1, 2, 4]
# [directory sector distinct (claim 0-9,-1)] [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
# 
# === TALLY (column-table checks) ===
# VERIFIED=15 REVIEW(count/extra mismatch)=2 CONTRADICTED=0 UNTESTABLE=0
# VALIDATION: column-table checks executed PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
