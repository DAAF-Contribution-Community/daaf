# --- Config ---
# INTENT: Parse the per-endpoint variable tables documented in the three
#   explorer reference files and compare each documented endpoint's variable
#   list against the live Portal varlist (from script 41). Flag
#   DOCUMENTED-NOT-PRESENT and PRESENT-NOT-DOCUMENTED per matched endpoint.
# REASONING: The live api-endpoint-varlist surface (script 41) is authoritative
#   for which variables an endpoint actually exposes. Comparing our doc tables
#   against it isolates variable-level drift, independent of the route-name/year
#   drift the concurrent lane (scripts 37-40) covers.
# ASSUMES (revised _a): Docs use TWO endpoint-table formats:
#   (1) `**Endpoint**: `/path/{year}/`` (singular) followed by a variable table.
#   (2) `**Endpoint(s)**:` / `**Working Endpoint(s)**:` followed by a bulleted
#       list of `- `/path/` - desc` routes, one shared variable table for all.
#   The v1 parser only caught format (1), silently missing the CRDC plural-format
#   sections in schools-endpoints.md. This revision anchors on `###` heading
#   sections and, within each, harvests routes ONLY from endpoint-marker lines and
#   the bullet lines that follow them (so prose-mentioned obsolete routes are not
#   mistaken for live claims), then associates the section's variable table with
#   every route in the section.
import re
import polars as pl
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research/2026-08-06_FrameworkDev_MirrorV2Update"
REF_DIR = BASE_DIR / ".claude/skills/education-data-explorer/references"
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
INV_PATH = OUT_DIR / "41_variable_inventory.parquet"
OUT_PATH = OUT_DIR / "42_varlist_audit.parquet"

DOC_FILES = {
    "colleges": REF_DIR / "colleges-endpoints.md",
    "districts": REF_DIR / "districts-endpoints.md",
    "schools": REF_DIR / "schools-endpoints.md",
}

# --- Load ---
inv = pl.read_parquet(INV_PATH)
print(f"Inventory: {inv.shape}")

def norm_path(p):
    # INTENT: canonicalize a route path for doc<->live matching.
    p = p.strip().lower()
    p = re.sub(r"^/?api/v1", "", p)
    p = re.sub(r"\{[^}]*\}", "{}", p)
    p = p.strip("/")
    return p

live_vars = {}   # norm_path -> set(variable)
for row in inv.filter(pl.col("variable").is_not_null()).iter_rows(named=True):
    n = norm_path(row["endpoint_url"])
    live_vars.setdefault(n, set()).add(row["variable"].lower())
print(f"Live normalized endpoints with variables: {len(live_vars)}")

# --- Transform: heading-section parser handling both endpoint-table formats ---
HEADING_RE = re.compile(r"^#{2,4}\s+\S")
ENDPOINT_MARKER_RE = re.compile(r"^\*\*(Working\s+)?Endpoints?\*\*:", re.IGNORECASE)
BULLET_RE = re.compile(r"^-\s")
ROUTE_TOKEN_RE = re.compile(r"`(/[^`]+)`")  # backticked token beginning with '/'
VAR_ROW_RE = re.compile(r"^\|\s*`([a-zA-Z0-9_]+)`\s*\|")

audit_rows = []
parse_counts = {}
route_total = {}
for level, path in DOC_FILES.items():
    lines = path.read_text().splitlines()
    sec_starts = [i for i, ln in enumerate(lines) if HEADING_RE.match(ln)]
    sec_starts.append(len(lines))
    n_sections_with_ep = 0
    n_routes = 0
    for s in range(len(sec_starts) - 1):
        start, end = sec_starts[s], sec_starts[s + 1]
        block = lines[start:end]
        routes = []
        collecting = False
        for bl in block:
            stripped = bl.strip()
            if ENDPOINT_MARKER_RE.match(stripped):
                collecting = True
                routes += ROUTE_TOKEN_RE.findall(stripped)  # inline route (singular)
                continue
            if collecting:
                if BULLET_RE.match(stripped):
                    routes += ROUTE_TOKEN_RE.findall(stripped)
                    continue
                if stripped == "":
                    continue  # tolerate blank lines within a bullet list
                collecting = False  # other prose ends the route list
        doc_vars = set()
        for bl in block:
            vm = VAR_ROW_RE.match(bl.strip())
            if vm:
                doc_vars.add(vm.group(1).lower())
        if not routes:
            continue
        n_sections_with_ep += 1
        for route in routes:
            n_routes += 1
            n = norm_path(route)
            matched = n in live_vars
            if matched:
                lv = live_vars[n]
                dnp = sorted(doc_vars - lv)
                pnd = sorted(lv - doc_vars)
            else:
                dnp, pnd = [], []
            audit_rows.append({
                "level": level,
                "doc_path": route,
                "norm_path": n,
                "route_matched_live": matched,
                "n_doc_vars": len(doc_vars),
                "n_live_vars": len(live_vars.get(n, set())),
                "n_documented_not_present": len(dnp),
                "n_present_not_documented": len(pnd),
                "documented_not_present": ", ".join(dnp),
                "present_not_documented": ", ".join(pnd),
            })
    parse_counts[level] = n_sections_with_ep
    route_total[level] = n_routes

audit = pl.DataFrame(audit_rows)

# --- Validate ---
print("\nParsed sections-with-endpoints and route counts per file:")
for lvl in DOC_FILES:
    print(f"  {lvl}: {parse_counts[lvl]} sections, {route_total[lvl]} documented routes")

n_matched = audit.filter(pl.col("route_matched_live")).height
n_unmatched = audit.filter(~pl.col("route_matched_live")).height
print(f"\nDocumented route entries total: {audit.height}")
print(f"  Route-matched live (variable comparison performed): {n_matched}")
print(f"  Route NOT matched live (DEAD/renamed — lane 37-40): {n_unmatched}")

matched_norm = audit.filter(pl.col("route_matched_live")).select("norm_path").n_unique()
print(f"  Distinct matched normalized endpoints: {matched_norm}")

zero_var = audit.filter((pl.col("route_matched_live")) & (pl.col("n_doc_vars") == 0))
print(f"Matched routes with 0 extracted doc vars (parser check): {zero_var.height}")
for r in zero_var.iter_rows(named=True):
    print(f"  ZERO-VARS: [{r['level']}] {r['doc_path']}")

assert audit.height > 60, "Too few route entries parsed — format assumption broke"

# --- Save ---
audit.write_parquet(OUT_PATH)
print(f"\nSaved: {OUT_PATH} ({audit.shape})")

# --- Findings: matched endpoints with variable discrepancies ---
print("\n=== MATCHED ENDPOINTS WITH VARIABLE DISCREPANCIES ===")
disc = (
    audit.filter(
        pl.col("route_matched_live")
        & ((pl.col("n_documented_not_present") > 0) | (pl.col("n_present_not_documented") > 0))
    )
    .unique(subset=["norm_path"], keep="first")
    .sort("n_documented_not_present", descending=True)
)
print(f"Distinct matched endpoints with >=1 discrepancy: {disc.height}")
for r in disc.iter_rows(named=True):
    print(f"\n[{r['level']}] {r['doc_path']}")
    print(f"   doc_vars={r['n_doc_vars']} live_vars={r['n_live_vars']}")
    if r["documented_not_present"]:
        print(f"   DOCUMENTED-NOT-PRESENT ({r['n_documented_not_present']}): {r['documented_not_present']}")
    if r["present_not_documented"]:
        print(f"   PRESENT-NOT-DOCUMENTED ({r['n_present_not_documented']}): {r['present_not_documented']}")

clean = audit.filter(
    pl.col("route_matched_live") & (pl.col("n_documented_not_present") == 0)
).unique(subset=["norm_path"]).height
print(f"\nDistinct matched endpoints with NO documented-not-present var: {clean}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:15:16
# Command: python3 /daaf/scripts/mirror_maintenance/42_varlist-audit_a.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Inventory: (2994, 13)
# Live normalized endpoints with variables: 129
# 
# Parsed sections-with-endpoints and route counts per file:
#   colleges: 49 sections, 49 documented routes
#   districts: 12 sections, 12 documented routes
#   schools: 34 sections, 58 documented routes
# 
# Documented route entries total: 119
#   Route-matched live (variable comparison performed): 62
#   Route NOT matched live (DEAD/renamed — lane 37-40): 57
#   Distinct matched normalized endpoints: 62
# Matched routes with 0 extracted doc vars (parser check): 10
#   ZERO-VARS: [colleges] /college-university/ipeds/fall-enrollment/{year}/{level}/race/sex/
#   ZERO-VARS: [colleges] /college-university/ipeds/sfa-by-living-arrangement/{year}/
#   ZERO-VARS: [colleges] /college-university/ipeds/grad-rates-200pct/{year}/
#   ZERO-VARS: [districts] /school-districts/ccd/enrollment/{year}/{grade}/race/sex/
#   ZERO-VARS: [schools] /schools/ccd/enrollment/{year}/{grade}/race/sex/
#   ZERO-VARS: [schools] /schools/edfacts/assessments/{year}/{grade}/race/
#   ZERO-VARS: [schools] /schools/edfacts/assessments/{year}/{grade}/sex/
#   ZERO-VARS: [schools] /schools/nhgis/census-1990/{year}/
#   ZERO-VARS: [schools] /schools/nhgis/census-2000/{year}/
#   ZERO-VARS: [schools] /schools/nhgis/census-2010/{year}/
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/42_varlist_audit.parquet ((119, 10))
# 
# === MATCHED ENDPOINTS WITH VARIABLE DISCREPANCIES ===
# Distinct matched endpoints with >=1 discrepancy: 62
# 
# [colleges] /college-university/ipeds/admissions-enrollment/{year}/
#    doc_vars=26 live_vars=9
#    DOCUMENTED-NOT-PRESENT (25): act_composite_25, act_composite_75, act_english_25, act_english_75, act_math_25, act_math_75, act_scores_submitted, admissions_men, admissions_total, admissions_women, admit_rate, applicants_men, applicants_total, applicants_women, enrolled_full_time, enrolled_men, enrolled_part_time, enrolled_total, enrolled_women, sat_math_25, sat_math_75, sat_reading_25, sat_reading_75, sat_scores_submitted, yield_rate
#    PRESENT-NOT-DOCUMENTED (8): fips, number_admitted, number_applied, number_enrolled_ft, number_enrolled_pt, number_enrolled_total, sex, year
# 
# [colleges] /college-university/ipeds/finance/{year}/
#    doc_vars=21 live_vars=141
#    DOCUMENTED-NOT-PRESENT (20): assets_total, endowment_eoy, exp_academic_support, exp_auxiliary, exp_institutional_support, exp_instruction, exp_public_service, exp_research, exp_scholarships, exp_student_services, exp_total, liabilities_total, rev_auxiliary, rev_govt_federal, rev_govt_local, rev_govt_state, rev_investment, rev_private_gifts, rev_total, rev_tuition_fees
#    PRESENT-NOT-DOCUMENTED (140): assets, assets_net, athletic_expense_treatment, buildings, calc_fte, capital_assets_other, construction_in_progress, cpi, def_inflows_pension, def_inflows_resources, def_outflows_pension, def_outflows_resources, depr_capital_assets, depreciation_accumulated, endowment_beg, endowment_end, equipment, equity_beg, equity_changes_other, equity_changes_total, equity_end, equity_total, est_fte, exp_acad_inst_student_salaries, exp_acad_inst_student_total, exp_acad_supp_salaries, exp_acad_supp_total, exp_aux_ent_salaries, exp_aux_ent_total, exp_hospital_salaries, exp_hospital_total, exp_ind_op_salaries, exp_ind_op_total, exp_inst_supp_salaries, exp_inst_supp_total, exp_instruc_salaries, exp_instruc_total, exp_net_grant_aid_salaries, exp_net_grant_aid_total, exp_other_salaries, exp_other_total_funct, exp_pub_serv_salaries, exp_pub_serv_total, exp_res_pub_serv_salaries, exp_res_pub_serv_total, exp_research_salaries, exp_research_total, exp_student_serv_salaries, exp_student_serv_total, exp_total_benefits, exp_total_current, exp_total_depr, exp_total_interest, exp_total_opm, exp_total_other_nat, exp_total_salaries, fips, form_type, gasb_alternative_accounting, heca, hepi, income_net, income_tax_fed, income_tax_state, infrastructure, intangible_assets_net, invest_capital_assets, land_improvements, liabilities, longterm_debt, longterm_investments, net_equity_beg_adjust, net_pension_liability, net_position_adjustments, net_position_beginning, net_position_change, net_position_end, other_plant_prop_equip, own_endowment_assets, parent_child_allocation, parent_child_flag, parent_child_system_flag, parent_unitid, pell_grant_treatment, pension_expense, pension_info_reported, plant_prop_equip_debt, plant_prop_equip_net, plant_property_equipment, position_net, rep_fte, reporting_form, rev_additions, rev_affiliated_entities, rev_appropriations_fed, rev_appropriations_local, rev_appropriations_state, rev_auxiliary_enterprises_gross, rev_auxiliary_enterprises_net, rev_capital_approps, rev_capital_grants_gifts, rev_edu_services_sales, rev_endowment_additions, rev_endowment_income, rev_fed_approps_grants, rev_gifts_grants_contracts, rev_grants_contracts_federal, rev_grants_contracts_local, rev_grants_contracts_state, rev_hosp_ind_op_other, rev_hospital, rev_independent_operations, rev_investment_return, rev_nonoperating, rev_operating, rev_other, rev_other_additions, rev_other_nonoperating, rev_other_operating, rev_state_local_approps_grants, rev_total_current, rev_tuition_fees_gross, rev_tuition_fees_net, sch_allowances_aux_enterp, sch_allowances_total, sch_allowances_tuition_fees, sch_exp_net_fellowships, sch_grants_institutional, sch_grants_local, sch_grants_private, sch_grants_state, sch_grants_state_local, sch_other_federal_grants, sch_pell_grant, sch_restricted_inst_grants, sch_total_student_aid, sch_unrestricted_inst_grants, total_expenses_deductions, total_revenues_additions, year
# 
# [colleges] /college-university/campus-crime/hate-crimes/{year}/
#    doc_vars=14 live_vars=13
#    DOCUMENTED-NOT-PRESENT (13): aggravated_assault, arson, burglary, dating_violence, domestic_violence, drug_arrests, liquor_arrests, motor_vehicle_theft, murder, rape, robbery, stalking, weapons_arrests
#    PRESENT-NOT-DOCUMENTED (12): bias, crime_type, fips, inst_name, non_campus_hate_crimes, on_campus_hate_crimes, opeid, other_hate_crimes, public_property_hate_crimes, residence_hall_hate_crimes, total_hate_crimes, year
# 
# [colleges] /college-university/ipeds/institutional-characteristics/{year}/
#    doc_vars=14 live_vars=126
#    DOCUMENTED-NOT-PRESENT (12): books_and_supplies, graduate_application_fee, inst_name, offers_credit_for_ap, offers_credit_for_clep, offers_credit_for_life_experience, offers_rotc_airforce, offers_rotc_army, offers_rotc_navy, room_and_board, room_capacity, undergraduate_application_fee
#    PRESENT-NOT-DOCUMENTED (124): academic_counseling, academic_prog_offered, alt_tuition, ap_credit, assoc_offered, avocational_prog_offered, bach_offered, calendar_system, cert_0_1_a_offered, cert_0_1_b_offered, cert_0_1_offered, cert_1_2_offered, cert_2_4_offered, conf_number_baseball, conf_number_basketball, conf_number_football, conf_number_track, cont_prof_prog_offered, credit_for_life, disability_indicator, disability_percentage, dist_courses_offered, dist_ed_not_offered, dist_grad_courses_offered, dist_grad_not_offered, dist_grad_offered, dist_grad_progs_offered, dist_progs_all, dist_progs_offered, dist_ug_courses_offered, dist_ug_not_offered, dist_ug_offered, dist_ug_progs_offered, doctors_other_offered, doctors_professional_offered, doctors_research_offered, dormitory_capacity, dual_credit, employment_services, enrolled_doctors_first_prof, enrolled_doctors_professional, enrolled_graduate_fulltime, enrolled_graduate_parttime, enrolled_undergrad_firsttime_ft, enrolled_undergrad_firsttime_pt, enrolled_undergrad_fulltime, enrolled_undergrad_parttime, fips, inst_affiliation, library_digital, library_hours, library_physical, library_printed_collection, library_shared, library_trained_staff, masters_offered, meals_per_week, member_ath_assoc_other, member_conf_baseball, member_conf_basketball, member_conf_football, member_conf_track, member_naia, member_natl_athletic_assoc, member_ncaa, member_nccaa, member_njcaa, member_nscaa, military_training_credit, no_alt_credit, no_library, no_noncredit_edu, no_selected_services, no_special_learning_opps, no_vet_services, noncred_adult_edu_offered, noncred_cust_training_offered, noncred_hs_diploma_offered, noncred_rec_edu_offered, noncred_remedial_edu_offered, noncred_workforce_edu_offered, noncredit_esl_edu_offered, noncredit_prof_edu_offered, occupational_prog_offered, oncampus_daycare, oncampus_housing, oncampus_required, other_alt_tuition, other_degree_offered, placement_services, post_masters_cert_offered, postbac_cert_offered, postsec_tr_prog_disabilities, prepaid_tuition, primary_public_control, promise_prog_participant, religious_affiliation, remedial_prog_offered, remedial_services, room_board_charge, rotc, rotc_airforce, rotc_army, rotc_navy, rotc_navy_marinecorps, secondary_prog_offered, secondary_public_control, servicemember_opp_coll_member, student_veteran_organization, study_abroad, teacher_cert, teacher_cert_other_inst, teacher_cert_specialization, teacher_cert_state_approved, tuition_guaranteed, tuition_payment_plan, tuition_varies, typical_board_charge, typical_room_charge, undergrad_research, veteran_point_of_contact, weekend_evening_college, year, yellow_ribbon_program
# 
# [colleges] /college-university/ipeds/sfa-all-undergraduates/{year}/
#    doc_vars=12 live_vars=10
#    DOCUMENTED-NOT-PRESENT (11): avg_federal_grant, avg_grant_amount, avg_loan_amount, avg_net_price, avg_pell, pct_receiving_aid, students_receiving_aid, students_receiving_federal_grants, students_receiving_grants, students_receiving_loans, students_receiving_pell
#    PRESENT-NOT-DOCUMENTED (9): average_amount, fips, ftpt, level_of_study, number_of_students, percent_of_students, total_amount, type_of_aid, year
# 
# [colleges] /college-university/ipeds/directory/{year}/
#    doc_vars=31 live_vars=96
#    DOCUMENTED-NOT-PRESENT (11): calendar_system, county_code, enrollment_grad, enrollment_total, enrollment_undergrad, highest_degree_offered, locale, open_admissions, phone, primarily_online, website
#    PRESENT-NOT-DOCUMENTED (76): cbsa_type, cc_award_level_focus_2025, cc_basic_2000, cc_basic_2010, cc_basic_2015, cc_basic_2018, cc_basic_2021, cc_basic_2025, cc_enroll_2010, cc_enroll_2015, cc_enroll_2018, cc_enroll_2021, cc_instit_size_2025, cc_instruc_grad_2010, cc_instruc_grad_2015, cc_instruc_grad_2018, cc_instruc_grad_2021, cc_instruc_grad_2025, cc_instruc_undergrad_2010, cc_instruc_undergrad_2015, cc_instruc_undergrad_2018, cc_instruc_undergrad_2021, cc_research_act_desig_2025, cc_size_setting_2010, cc_size_setting_2015, cc_size_setting_2018, cc_size_setting_2021, cc_stud_access_earn_2025, cc_undergrad_2010, cc_undergrad_2015, cc_undergrad_2018, cc_undergrad_2021, cc_undergrad_2025, chief_admin_name, chief_admin_title, comparison_group, comparison_group_custom, county_fips, currently_active_ipeds, date_closed, duns, ein, hospital, inst_alias, inst_size, inst_status, inst_system_flag, inst_system_name, land_grant, medical_degree, necta, newid, offering_grad, offering_highest_degree, offering_highest_level, offering_undergrad, opeid, open_public, phone_number, postsec_public_active, postsec_public_active_title_iv, primarily_postsecondary, region, reporting_method, sector, title_iv_indicator, ueis, urban_centric_locale, url_application, url_athletes, url_disability_services, url_fin_aid, url_netprice, url_school, url_veterans, year_deleted
# 
# [colleges] /college-university/fsa/loans/{year}/
#    doc_vars=11 live_vars=19
#    DOCUMENTED-NOT-PRESENT (10): grad_plus_disbursements, grad_plus_recipients, loan_disbursements, loan_recipients, plus_disbursements, plus_recipients, subsidized_disbursements, subsidized_recipients, unsubsidized_disbursements, unsubsidized_recipients
#    PRESENT-NOT-DOCUMENTED (18): allocation_flag, combined_flag, fips, inst_name_fsa, loan_recipients_opeid, loan_recipients_unitid, loan_type, num_loans_disbursed_opeid, num_loans_disbursed_unitid, num_loans_originated_opeid, num_loans_originated_unitid, opeid, other_assoc_opeids, value_loan_disbursements_opeid, value_loan_disbursements_unitid, value_loans_originated_opeid, value_loans_originated_unitid, year
# 
# [schools] /schools/crdc/offerings/{year}/
#    doc_vars=10 live_vars=53
#    DOCUMENTED-NOT-PRESENT (10): offers_algebra1, offers_algebra2, offers_ap, offers_biology, offers_calculus, offers_chemistry, offers_geometry, offers_gt, offers_ib, offers_physics
#    PRESENT-NOT-DOCUMENTED (53): ap_courses_indicator, ap_courses_math_indicator, ap_courses_other_indicator, ap_courses_science_indicator, classes_single_sex_alg_geom, classes_single_sex_alg_geom_f, classes_single_sex_alg_geom_m, classes_single_sex_english, classes_single_sex_english_f, classes_single_sex_english_m, classes_single_sex_indicator, classes_single_sex_other, classes_single_sex_other_f, classes_single_sex_other_m, classes_single_sex_othermath, classes_single_sex_othermath_f, classes_single_sex_othermath_m, classes_single_sex_science, classes_single_sex_science_f, classes_single_sex_science_m, crdc_id, fips, gifted_talented_indicator, leaid, ncessch, num_classes_advanced_math, num_classes_algebra1, num_classes_algebra2, num_classes_biology, num_classes_calculus, num_classes_chemistry, num_classes_geometry, num_classes_physics, num_courses_ap, num_taught_certified_adv_math, num_taught_certified_algebra1, num_taught_certified_algebra2, num_taught_certified_biology, num_taught_certified_calculus, num_taught_certified_chemistry, num_taught_certified_geometry, num_taught_certified_physics, participants_single_sex_sports, participants_single_sex_sports_f, participants_single_sex_sports_m, sch_dual_indicator, sports_single_sex_f, sports_single_sex_indicator, sports_single_sex_m, students_select_ap_indicator, teams_single_sex_f, teams_single_sex_m, year
# 
# [schools] /schools/crdc/discipline/{year}/disability/race/sex/
#    doc_vars=10 live_vars=20
#    DOCUMENTED-NOT-PRESENT (10): expulsions_under_zero_tolerance, expulsions_with_ed, expulsions_without_ed, iss, oss_multiple, oss_one, referrals_to_law_enforcement, school_related_arrests, students_corporal_punishment, transfers_to_alt_schools
#    PRESENT-NOT-DOCUMENTED (20): crdc_id, disability, expulsions_no_ed_serv, expulsions_with_ed_serv, expulsions_zero_tolerance, fips, leaid, lep, ncessch, race, revised_flag, sex, students_arrested, students_corporal_punish, students_referred_law_enforce, students_susp_in_sch, students_susp_out_sch_multiple, students_susp_out_sch_single, transfers_alt_sch_disc, year
# 
# [schools] /schools/crdc/suspensions-days/{year}/race/sex/
#    doc_vars=10 live_vars=10
#    DOCUMENTED-NOT-PRESENT (10): expulsions_under_zero_tolerance, expulsions_with_ed, expulsions_without_ed, iss, oss_multiple, oss_one, referrals_to_law_enforcement, school_related_arrests, students_corporal_punishment, transfers_to_alt_schools
#    PRESENT-NOT-DOCUMENTED (10): crdc_id, days_suspended, disability, fips, leaid, lep, ncessch, race, sex, year
# 
# [schools] /schools/crdc/discipline/{year}/disability/sex/
#    doc_vars=10 live_vars=20
#    DOCUMENTED-NOT-PRESENT (10): expulsions_under_zero_tolerance, expulsions_with_ed, expulsions_without_ed, iss, oss_multiple, oss_one, referrals_to_law_enforcement, school_related_arrests, students_corporal_punishment, transfers_to_alt_schools
#    PRESENT-NOT-DOCUMENTED (20): crdc_id, disability, expulsions_no_ed_serv, expulsions_with_ed_serv, expulsions_zero_tolerance, fips, leaid, lep, ncessch, race, revised_flag, sex, students_arrested, students_corporal_punish, students_referred_law_enforce, students_susp_in_sch, students_susp_out_sch_multiple, students_susp_out_sch_single, transfers_alt_sch_disc, year
# 
# [schools] /schools/crdc/harassment-or-bullying/{year}/race/sex/
#    doc_vars=10 live_vars=15
#    DOCUMENTED-NOT-PRESENT (10): allegations_of_harassment_disability, allegations_of_harassment_orientation, allegations_of_harassment_race, allegations_of_harassment_religion, allegations_of_harassment_sex, students_disciplined_harassment_disability, students_disciplined_harassment_orientation, students_disciplined_harassment_race, students_disciplined_harassment_religion, students_disciplined_harassment_sex
#    PRESENT-NOT-DOCUMENTED (15): crdc_id, disability, fips, leaid, lep, ncessch, race, sex, students_disc_harass_dis, students_disc_harass_race, students_disc_harass_sex, students_report_harass_dis, students_report_harass_race, students_report_harass_sex, year
# 
# [colleges] /college-university/scorecard/repayment/{year}/
#    doc_vars=9 live_vars=31
#    DOCUMENTED-NOT-PRESENT (8): median_debt, median_debt_no_pell, median_debt_pell, monthly_payment_10yr, repay_1yr_rate, repay_3yr_rate, repay_5yr_rate, repay_7yr_rate
#    PRESENT-NOT-DOCUMENTED (30): cohort_year, fips, opeid, opeid6, repay_count, repay_count_dependent, repay_count_female, repay_count_firstgen, repay_count_highincome, repay_count_independent, repay_count_lowincome, repay_count_male, repay_count_midincome, repay_count_nopell, repay_count_notfirstgen, repay_count_pell, repay_rate, repay_rate_dependent, repay_rate_female, repay_rate_firstgen, repay_rate_highincome, repay_rate_independent, repay_rate_lowincome, repay_rate_male, repay_rate_midincome, repay_rate_nopell, repay_rate_notfirstgen, repay_rate_pell, year, years_since_entering_repay
# 
# [colleges] /college-university/scorecard/earnings/{year}/
#    doc_vars=9 live_vars=33
#    DOCUMENTED-NOT-PRESENT (8): earn_count_wne_p10, earn_count_wne_p6, earn_mean_wne_p10, earn_mean_wne_p6, earn_median_wne_p10, earn_median_wne_p6, earn_pct_gt_25k_p10, earn_pct_gt_25k_p6
#    PRESENT-NOT-DOCUMENTED (32): cohort_year, count_not_working, count_working, count_working_dep, count_working_dep_lowinc, count_working_female, count_working_highinc, count_working_ind, count_working_lowinc, count_working_male, count_working_midinc, earnings_dep_lowinc_mean, earnings_dep_mean, earnings_female_mean, earnings_greater_than_25k_pct, earnings_highinc_mean, earnings_ind_mean, earnings_lowinc_mean, earnings_male_mean, earnings_mean, earnings_med, earnings_midinc_mean, earnings_pct10, earnings_pct25, earnings_pct75, earnings_pct90, earnings_sd, fips, opeid, opeid6, year, years_after_entry
# 
# [colleges] /college-university/fsa/grants/{year}/
#    doc_vars=8 live_vars=13
#    DOCUMENTED-NOT-PRESENT (7): pell_avg_amount, pell_disbursements, pell_recipients, seog_disbursements, seog_recipients, teach_disbursements, teach_recipients
#    PRESENT-NOT-DOCUMENTED (12): allocation_flag, combined_flag, fips, grant_recipients_opeid, grant_recipients_unitid, grant_type, inst_name_fsa, opeid, other_assoc_opeids, value_grants_disbursed_opeid, value_grants_disbursed_unitid, year
# 
# [schools] /schools/crdc/directory/{year}/
#    doc_vars=12 live_vars=35
#    DOCUMENTED-NOT-PRESENT (7): alternative, charter, enrollment, jj_school, magnet, school_name, special_ed
#    PRESENT-NOT-DOCUMENTED (30): ability_grouped_math_or_eng, alt_school, alt_school_focus, charter_crdc, entire_school_magnet, g1, g10, g11, g12, g2, g3, g4, g5, g6, g7, g8, g9, k, lea_name, lea_state, leaid_crdc, magnet_crdc, prek, primarily_serve_students_w_dis, school_name_crdc, schoolid_crdc, ug, ug_elementary_school, ug_high_school, ug_middle_school
# 
# [colleges] /college-university/ipeds/admissions-requirements/{year}/
#    doc_vars=8 live_vars=48
#    DOCUMENTED-NOT-PRESENT (7): req_high_school_gpa, req_high_school_rank, req_high_school_record, req_recommendations, req_secondary_school_report, req_test_scores, req_toefl
#    PRESENT-NOT-DOCUMENTED (47): act_composite_25_pctl, act_composite_50_pctl, act_composite_75_pctl, act_english_25_pctl, act_english_50_pctl, act_english_75_pctl, act_math_25_pctl, act_math_50_pctl, act_math_75_pctl, act_number_submitting, act_percent_submitting, act_writing_25_pctl, act_writing_75_pctl, fips, no_entering_freshmen, open_admissions_policy, reqt_ability_to_benefit, reqt_age, reqt_college_prep, reqt_competencies, reqt_hs_diploma, reqt_hs_gpa, reqt_hs_rank, reqt_hs_record, reqt_legacy_status, reqt_other, reqt_other_test, reqt_personal_statement, reqt_recommendations, reqt_residence, reqt_sat_scores, reqt_test_scores, reqt_toefl, reqt_work, sat_act_report_period, sat_crit_read_25_pctl, sat_crit_read_50_pctl, sat_crit_read_75_pctl, sat_math_25_pctl, sat_math_50_pctl, sat_math_75_pctl, sat_number_submitting, sat_percent_submitting, sat_writing_25_pctl, sat_writing_75_pctl, year, years_college_reqd
# 
# [schools] /schools/crdc/math-and-science/{year}/race/sex/
#    doc_vars=7 live_vars=16
#    DOCUMENTED-NOT-PRESENT (7): advanced_math, algebra_2, biology, calculus, chemistry, geometry, physics
#    PRESENT-NOT-DOCUMENTED (16): crdc_id, disability, enrl_advanced_math, enrl_algebra2, enrl_biology, enrl_calculus, enrl_chemistry, enrl_geometry, enrl_physics, fips, leaid, lep, ncessch, race, sex, year
# 
# [schools] /schools/crdc/offenses/{year}/
#    doc_vars=6 live_vars=33
#    DOCUMENTED-NOT-PRESENT (6): offenses_alcohol, offenses_drugs, offenses_sexual, offenses_violence, offenses_weapons_firearm, offenses_weapons_other
#    PRESENT-NOT-DOCUMENTED (33): alleg_rape_staff_notresp, alleg_rape_staff_pending, alleg_rape_staff_reassign, alleg_rape_staff_resign, alleg_rape_staff_resp, alleg_sexual_batt_staff_notresp, alleg_sexual_batt_staff_pending, alleg_sexual_batt_staff_reassign, alleg_sexual_batt_staff_resign, alleg_sexual_batt_staff_resp, attack_no_weapon_incidents, attack_w_firearm_incidents, attack_w_weapon_incidents, crdc_id, fips, firearm_incident_ind, homicide_ind, leaid, ncessch, possession_firearm_incidents, rape_bystaff, rape_bystudents, rape_incidents, robbery_no_weapon_incidents, robbery_w_firearm_incidents, robbery_w_weapon_incidents, sexual_battery_bystaff, sexual_battery_bystudents, sexual_battery_incidents, threats_no_weapon_incidents, threats_w_firearm_incidents, threats_w_weapon_incidents, year
# 
# [districts] /school-districts/saipe/{year}/
#    doc_vars=12 live_vars=10
#    DOCUMENTED-NOT-PRESENT (6): children_poverty_total, lea_name, median_household_income, median_household_income_lb, median_household_income_ub, population_total
#    PRESENT-NOT-DOCUMENTED (4): district_id, district_name, est_population_5_17_pct, est_population_total
# 
# [districts] /school-districts/ccd/directory/{year}/
#    doc_vars=31 live_vars=69
#    DOCUMENTED-NOT-PRESENT (6): homeless_students, metromicro, students_free_lunch, students_reduced_lunch, teachers_fte, website
#    PRESENT-NOT-DOCUMENTED (44): agency_charter_indicator, boundary_change_indicator, bureau_indian_education, cbsa_type, city_mailing, cmsa, coordinators_fte, guidance_counselors_elem_fte, guidance_counselors_other_fte, guidance_counselors_sec_fte, guidance_counselors_total_fte, instructional_aides_fte, latitude, lea_admin_support_staff_fte, lea_administrators_fte, lea_staff_total_fte, librarian_specialists_fte, librarian_support_staff_fte, longitude, necta, other_staff_fte, school_admin_support_staff_fte, school_administrators_fte, school_counselors_fte, school_psychologists_fte, school_staff_total_fte, staff_total_fte, state_leg_district_lower, state_leg_district_upper, state_mailing, street_mailing, supervisory_union_number, support_staff_other_fte, support_staff_stu_wo_psych_fte, support_staff_students_fte, teachers_elementary_fte, teachers_kindergarten_fte, teachers_prek_fte, teachers_secondary_fte, teachers_total_fte, teachers_ungraded_fte, zip4_location, zip4_mailing, zip_mailing
# 
# [colleges] /college-university/scorecard/institutional-characteristics/{year}/
#    doc_vars=7 live_vars=27
#    DOCUMENTED-NOT-PRESENT (6): highest_degree, main_campus, online_only, ownership, predominant_degree, region
#    PRESENT-NOT-DOCUMENTED (26): accreditor, accreditor_code, city, currently_operating, fips, inst_name, latitude, longitude, menonly, min_serving_aanipi, min_serving_annh, min_serving_hispanic, min_serving_historic_black, min_serving_na_nontribal, min_serving_predominant_black, min_serving_tribal, opeid, opeid6, pred_degree_awarded_ipeds, religious_affiliation, state_abbr, title_iv_approval_date, under_investigation, womenonly, year, zip
# 
# [schools] /schools/crdc/teachers-staff/{year}/
#    doc_vars=10 live_vars=22
#    DOCUMENTED-NOT-PRESENT (5): security_guards_fte, teachers_absent_10_plus, teachers_certified, teachers_first_year, teachers_second_year
#    PRESENT-NOT-DOCUMENTED (17): crdc_id, fips, law_enforcement_ind, leaid, ncessch, security_guard_fte, teachers_absent_fte, teachers_certified_fte, teachers_current_female, teachers_current_male, teachers_current_sy, teachers_first_year_fte, teachers_fte_crdc, teachers_previous_sy, teachers_second_year_fte, teachers_uncertified_fte, year
# 
# [colleges] /college-university/fsa/financial-responsibility/{year}/
#    doc_vars=6 live_vars=8
#    DOCUMENTED-NOT-PRESENT (5): fr_composite_score, fr_equity_ratio, fr_net_income_ratio, fr_primary_reserve_ratio, fr_zone
#    PRESENT-NOT-DOCUMENTED (7): financial_resp_score, fips, inst_group_name, inst_name_fsa, multicampus_flag, opeid, year
# 
# [schools] /schools/crdc/ap-ib-enrollment/{year}/race/sex/
#    doc_vars=5 live_vars=17
#    DOCUMENTED-NOT-PRESENT (5): ap_courses_offered, ap_enrollment, ap_students_passed, gt_enrollment, ib_enrollment
#    PRESENT-NOT-DOCUMENTED (17): crdc_id, disability, enrl_ap, enrl_ap_compsci, enrl_ap_language, enrl_ap_math, enrl_ap_other, enrl_ap_science, enrl_gifted_talented, enrl_ib, fips, leaid, lep, ncessch, race, sex, year
# 
# [colleges] /college-university/scorecard/default/{year}/
#    doc_vars=5 live_vars=9
#    DOCUMENTED-NOT-PRESENT (4): cdr2, cdr3, default_rate_2yr, default_rate_3yr
#    PRESENT-NOT-DOCUMENTED (8): cohort_year, default_rate, default_rate_denom, fips, opeid, opeid6, year, years_since_entering_repay
# 
# [schools] /schools/crdc/algebra1/{year}/race/sex/
#    doc_vars=4 live_vars=12
#    DOCUMENTED-NOT-PRESENT (4): algebra1_grade7, algebra1_grade8, passed_algebra1_grade7, passed_algebra1_grade8
#    PRESENT-NOT-DOCUMENTED (12): crdc_id, disability, enrl_algebra1, fips, grade_crdc, leaid, lep, ncessch, race, sex, students_passing_algebra1, year
# 
# [schools] /schools/crdc/enrollment/{year}/race/sex/
#    doc_vars=6 live_vars=11
#    DOCUMENTED-NOT-PRESENT (2): enrollment, section504
#    PRESENT-NOT-DOCUMENTED (7): crdc_id, enrollment_crdc, fips, leaid, ncessch, psenrollment_crdc, year
# 
# [schools] /schools/crdc/dual-enrollment/{year}/race/sex/
#    doc_vars=2 live_vars=10
#    DOCUMENTED-NOT-PRESENT (2): credit_recovery, dual_enrollment
#    PRESENT-NOT-DOCUMENTED (10): crdc_id, disability, enrl_dual_enrollment, fips, leaid, lep, ncessch, race, sex, year
# 
# [colleges] /college-university/nacubo/endowments/{year}/
#    doc_vars=3 live_vars=7
#    DOCUMENTED-NOT-PRESENT (2): endowment_change_pct, endowment_eoy
#    PRESENT-NOT-DOCUMENTED (6): endow_chg_mktval, endow_per_fte, endow_total, fips, inst_name_nacubo, year
# 
# [schools] /schools/crdc/ap-exams/{year}/race/sex/
#    doc_vars=2 live_vars=15
#    DOCUMENTED-NOT-PRESENT (2): students_ap_exam, students_ap_passed
#    PRESENT-NOT-DOCUMENTED (15): crdc_id, disability, fips, leaid, lep, ncessch, race, sex, students_ap_exam_all, students_ap_exam_none, students_ap_exam_oneormore, students_ap_pass_all, students_ap_pass_none, students_ap_pass_oneormore, year
# 
# [schools] /schools/nhgis/census-2020/{year}/
#    doc_vars=5 live_vars=47
#    DOCUMENTED-NOT-PRESENT (2): block, gisjoin
#    PRESENT-NOT-DOCUMENTED (44): cbsa, cbsa_city, cbsa_name, cbsa_type, census_division, census_region, city_location, city_mailing, class_code, congress_district_id, county_code, county_fips_geo, csa, fips, geo_latitude, geo_longitude, geocode_accuracy, geocode_accuracy_detailed, geoid_block, geoid_place, gleaid, latitude, leaid, longitude, lower_chamber, lower_chamber_name, lower_chamber_type, place_fips, place_name, puma, school_id, school_name, state_fips_geo, state_leg_district_lower, state_leg_district_upper, state_location, state_mailing, street_location, street_mailing, upper_chamber, upper_chamber_name, year, zip_location, zip_mailing
# 
# [schools] /schools/crdc/internet-access/{year}/
#    doc_vars=2 live_vars=10
#    DOCUMENTED-NOT-PRESENT (2): students_no_device, students_no_internet
#    PRESENT-NOT-DOCUMENTED (10): crdc_id, fips, leaid, ncessch, sch_internet_fiber, sch_internet_schdev, sch_internet_studdev, sch_internet_wifi, sch_internet_wifiendev, year
# 
# [schools] /schools/crdc/chronic-absenteeism/{year}/race/sex/
#    doc_vars=1 live_vars=11
#    DOCUMENTED-NOT-PRESENT (1): chronic_absentees
#    PRESENT-NOT-DOCUMENTED (11): crdc_id, disability, fips, homeless, leaid, lep, ncessch, race, sex, students_chronically_absent, year
# 
# [colleges] /college-university/ipeds/student-faculty-ratio/{year}/
#    doc_vars=3 live_vars=4
#    DOCUMENTED-NOT-PRESENT (1): instructional_fte
#    PRESENT-NOT-DOCUMENTED (2): fips, year
# 
# [schools] /schools/edfacts/assessments/{year}/{grade}/
#    doc_vars=11 live_vars=26
#    DOCUMENTED-NOT-PRESENT (1): grade
#    PRESENT-NOT-DOCUMENTED (16): disability, econ_disadvantaged, foster_care, grade_edfacts, homeless, lea_name, leaid, leaid_num, lep, migrant, military_connected, ncessch_num, race, school_name, sex, year
# 
# [schools] /schools/meps/{year}/
#    doc_vars=5 live_vars=11
#    DOCUMENTED-NOT-PRESENT (1): poverty_quintile
#    PRESENT-NOT-DOCUMENTED (7): gleaid, leaid, meps_mod_poverty_ptl, meps_poverty_ptl, meps_poverty_se, ncessch_num, year
# 
# [schools] /schools/edfacts/grad-rates/{year}/
#    doc_vars=4 live_vars=18
#    DOCUMENTED-NOT-PRESENT (1): cohort_count
#    PRESENT-NOT-DOCUMENTED (15): cohort_num, disability, econ_disadvantaged, fips, foster_care, homeless, lea_name, leaid, leaid_num, lep, ncessch, ncessch_num, race, school_name, year
# 
# [schools] /schools/ccd/directory/{year}/
#    doc_vars=36 live_vars=52
#    DOCUMENTED-NOT-PRESENT (1): county_name
#    PRESENT-NOT-DOCUMENTED (17): city_mailing, direct_certification, elem_cedp, high_cedp, lunch_program, middle_cedp, school_id, seasch, shared_time, state_leaid, state_leg_district_lower, state_leg_district_upper, state_mailing, street_mailing, title_i_status, ungrade_cedp, zip_mailing
# 
# [districts] /school-districts/edfacts/assessments/{year}/{grade}/
#    doc_vars=11 live_vars=23
#    DOCUMENTED-NOT-PRESENT (1): grade
#    PRESENT-NOT-DOCUMENTED (13): disability, econ_disadvantaged, foster_care, grade_edfacts, homeless, lea_name, leaid_num, lep, migrant, military_connected, race, sex, year
# 
# [districts] /school-districts/edfacts/grad-rates/{year}/
#    doc_vars=6 live_vars=15
#    DOCUMENTED-NOT-PRESENT (1): cohort_count
#    PRESENT-NOT-DOCUMENTED (10): cohort_num, disability, econ_disadvantaged, foster_care, homeless, lea_name, leaid_num, lep, race, year
# 
# [schools] /schools/ccd/enrollment/{year}/{grade}/race/sex/
#    doc_vars=0 live_vars=9
#    PRESENT-NOT-DOCUMENTED (9): enrollment, fips, grade, leaid, ncessch, ncessch_num, race, sex, year
# 
# [schools] /schools/edfacts/assessments/{year}/{grade}/sex/
#    doc_vars=0 live_vars=26
#    PRESENT-NOT-DOCUMENTED (26): disability, econ_disadvantaged, fips, foster_care, grade_edfacts, homeless, lea_name, leaid, leaid_num, lep, math_test_num_valid, math_test_pct_prof_high, math_test_pct_prof_low, math_test_pct_prof_midpt, migrant, military_connected, ncessch, ncessch_num, race, read_test_num_valid, read_test_pct_prof_high, read_test_pct_prof_low, read_test_pct_prof_midpt, school_name, sex, year
# 
# [districts] /school-districts/ccd/enrollment/{year}/{grade}/race/
#    doc_vars=1 live_vars=7
#    PRESENT-NOT-DOCUMENTED (6): enrollment, fips, grade, leaid, sex, year
# 
# [districts] /school-districts/edfacts/assessments/{year}/{grade}/sex/
#    doc_vars=1 live_vars=23
#    PRESENT-NOT-DOCUMENTED (22): disability, econ_disadvantaged, fips, foster_care, grade_edfacts, homeless, lea_name, leaid, leaid_num, lep, math_test_num_valid, math_test_pct_prof_high, math_test_pct_prof_low, math_test_pct_prof_midpt, migrant, military_connected, race, read_test_num_valid, read_test_pct_prof_high, read_test_pct_prof_low, read_test_pct_prof_midpt, year
# 
# [districts] /school-districts/ccd/enrollment/{year}/{grade}/
#    doc_vars=5 live_vars=7
#    PRESENT-NOT-DOCUMENTED (2): race, sex
# 
# [colleges] /college-university/ipeds/fall-enrollment/{year}/{level}/race/sex/
#    doc_vars=0 live_vars=10
#    PRESENT-NOT-DOCUMENTED (10): class_level, degree_seeking, enrollment_fall, fips, ftpt, level_of_study, race, sex, unitid, year
# 
# [schools] /schools/edfacts/assessments/{year}/{grade}/special-populations/
#    doc_vars=6 live_vars=26
#    PRESENT-NOT-DOCUMENTED (20): fips, grade_edfacts, lea_name, leaid, leaid_num, math_test_num_valid, math_test_pct_prof_high, math_test_pct_prof_low, math_test_pct_prof_midpt, military_connected, ncessch, ncessch_num, race, read_test_num_valid, read_test_pct_prof_high, read_test_pct_prof_low, read_test_pct_prof_midpt, school_name, sex, year
# 
# [schools] /schools/nhgis/census-2000/{year}/
#    doc_vars=0 live_vars=42
#    PRESENT-NOT-DOCUMENTED (42): block_group, census_division, census_region, city_location, city_mailing, class_code, congress_district_id, county_code, county_fips_geo, fips, geo_latitude, geo_longitude, geocode_accuracy, geocode_accuracy_detailed, geoid_block, geoid_place, gleaid, latitude, leaid, longitude, lower_chamber, lower_chamber_name, msa_cmsa, ncessch, place_fips, place_name, puma, school_id, school_name, state_fips_geo, state_leg_district_lower, state_leg_district_upper, state_location, state_mailing, street_location, street_mailing, tract, upper_chamber, upper_chamber_name, year, zip_location, zip_mailing
# 
# [districts] /school-districts/edfacts/assessments/{year}/{grade}/special-populations/
#    doc_vars=6 live_vars=23
#    PRESENT-NOT-DOCUMENTED (17): fips, grade_edfacts, lea_name, leaid, leaid_num, math_test_num_valid, math_test_pct_prof_high, math_test_pct_prof_low, math_test_pct_prof_midpt, military_connected, race, read_test_num_valid, read_test_pct_prof_high, read_test_pct_prof_low, read_test_pct_prof_midpt, sex, year
# 
# [schools] /schools/edfacts/assessments/{year}/{grade}/race/
#    doc_vars=0 live_vars=26
#    PRESENT-NOT-DOCUMENTED (26): disability, econ_disadvantaged, fips, foster_care, grade_edfacts, homeless, lea_name, leaid, leaid_num, lep, math_test_num_valid, math_test_pct_prof_high, math_test_pct_prof_low, math_test_pct_prof_midpt, migrant, military_connected, ncessch, ncessch_num, race, read_test_num_valid, read_test_pct_prof_high, read_test_pct_prof_low, read_test_pct_prof_midpt, school_name, sex, year
# 
# [districts] /school-districts/ccd/finance/{year}/
#    doc_vars=4 live_vars=163
#    PRESENT-NOT-DOCUMENTED (159): assets_bond_fund, assets_other, assets_sinking_fund, benefits_employee_instruction, benefits_employee_total, benefits_enterprise_operations, benefits_food_service, benefits_supp_bco, benefits_supp_general_admin, benefits_supp_instruc_staff, benefits_supp_operation_plant, benefits_supp_pupils, benefits_supp_sch_admin, benefits_supp_stud_transport, censusid, debt_interest, debt_longterm_issued_fy, debt_longterm_outstand_beg_fy, debt_longterm_outstand_end_fy, debt_longterm_retired_fy, debt_shortterm_outstand_beg_fy, debt_shortterm_outstand_end_fy, enrollment_fall_school, exp_cares_act_current, exp_cares_act_food, exp_cares_act_instruction, exp_cares_act_outlay, exp_cares_act_support_services, exp_cares_act_tech_equipment, exp_cares_act_tech_plant, exp_cares_act_tech_service, exp_current_arra, exp_current_bco, exp_current_elsec_total, exp_current_enterprise, exp_current_federal_funds, exp_current_food_serv, exp_current_general_admin, exp_current_instruc_staff, exp_current_instruction_total, exp_current_operation_plant, exp_current_other, exp_current_other_elsec, exp_current_pupils, exp_current_resa, exp_current_sch_admin, exp_current_state_local_funds, exp_current_student_transport, exp_current_supp_serv_nonspec, exp_current_supp_serve_total, exp_instruction, exp_nonelsec, exp_nonelsec_adult_education, exp_nonelsec_community_serv, exp_nonelsec_other, exp_sped_current, exp_sped_instruction, exp_sped_pupil_support_services, exp_sped_staff_support_services, exp_sped_trans_support_services, exp_tech_equipment, exp_tech_supplies_services, exp_textbooks, exp_total, exp_utilities_energy, outlay_capital_arra, outlay_capital_construction, outlay_capital_instruc_equip, outlay_capital_land_structures, outlay_capital_nonspec_equip, outlay_capital_other_equip, outlay_capital_total, payments_charter_schools, payments_local_govt, payments_other_sch_system, payments_private_schools, payments_state_govt, rev_arp_esser, rev_cares_act_relief_crf, rev_cares_act_relief_esf_rem, rev_cares_act_relief_esf_rwp, rev_cares_act_relief_esser, rev_cares_act_relief_geer, rev_cares_act_relief_serv, rev_crrsa_esser_ii, rev_crrsa_geer_ii, rev_fed_arra, rev_fed_child_nutrition_act, rev_fed_direct_impact_aid, rev_fed_direct_indian_ed, rev_fed_direct_other, rev_fed_direct_rural_achievement, rev_fed_nonspec, rev_fed_state_bilingual_ed, rev_fed_state_drug_free, rev_fed_state_eff_instruction, rev_fed_state_idea, rev_fed_state_math_sci_teach, rev_fed_state_other, rev_fed_state_rural_lowinc_sch, rev_fed_state_supp_21st_lc, rev_fed_state_supp_ed, rev_fed_state_title_i, rev_fed_state_vocational, rev_fed_total, rev_local_cities_counties, rev_local_dist_activ_receipts, rev_local_fines_forfeits, rev_local_income_tax, rev_local_interest_earnings, rev_local_misc, rev_local_oth_sales_serv, rev_local_other_sch_systems, rev_local_other_tax, rev_local_parent_govt, rev_local_private_contrib, rev_local_prop_tax, rev_local_property_sale, rev_local_rents_royalties, rev_local_sales_tax, rev_local_sch_lunch, rev_local_student_fees_nonspec, rev_local_textbook_sales_rents, rev_local_total, rev_local_transportation_fees, rev_local_tuition_fees, rev_local_utility_tax, rev_nces, rev_state_bilingual_ed, rev_state_compens_basic_ed, rev_state_employee_benefits, rev_state_gen_formula_assist, rev_state_gifted_talented, rev_state_local_recovery_funds, rev_state_nonspec, rev_state_not_employee_benefits, rev_state_oth_prog, rev_state_outlay_capital_debt, rev_state_sch_lunch, rev_state_special_ed, rev_state_staff_improve, rev_state_total, rev_state_transportation, rev_state_vocational_ed, rev_total, salaries_food_service, salaries_instruction, salaries_supp_bco, salaries_supp_general_admin, salaries_supp_instruc_staff, salaries_supp_operation_plant, salaries_supp_pupils, salaries_supp_sch_admin, salaries_supp_stud_transport, salaries_teachers_other_ed, salaries_teachers_regular_prog, salaries_teachers_sped, salaries_teachers_vocational, salaries_total
# 
# [schools] /schools/ccd/enrollment/{year}/{grade}/race/
#    doc_vars=1 live_vars=9
#    PRESENT-NOT-DOCUMENTED (8): enrollment, fips, grade, leaid, ncessch, ncessch_num, sex, year
# 
# [schools] /schools/ccd/enrollment/{year}/{grade}/
#    doc_vars=6 live_vars=9
#    PRESENT-NOT-DOCUMENTED (3): ncessch_num, race, sex
# 
# [schools] /schools/nhgis/census-1990/{year}/
#    doc_vars=0 live_vars=35
#    PRESENT-NOT-DOCUMENTED (35): block_group, census_division, census_region, city_location, city_mailing, class_code, congress_district_id, county_code, county_fips_geo, fips, geo_latitude, geo_longitude, geocode_accuracy, geocode_accuracy_detailed, geoid_block, geoid_place, gleaid, latitude, leaid, longitude, msa_cmsa, ncessch, place_fips, place_name, school_id, school_name, state_fips_geo, state_location, state_mailing, street_location, street_mailing, tract, year, zip_location, zip_mailing
# 
# [districts] /school-districts/ccd/enrollment/{year}/{grade}/race/sex/
#    doc_vars=0 live_vars=7
#    PRESENT-NOT-DOCUMENTED (7): enrollment, fips, grade, leaid, race, sex, year
# 
# [districts] /school-districts/edfacts/assessments/{year}/{grade}/race/
#    doc_vars=1 live_vars=23
#    PRESENT-NOT-DOCUMENTED (22): disability, econ_disadvantaged, fips, foster_care, grade_edfacts, homeless, lea_name, leaid, leaid_num, lep, math_test_num_valid, math_test_pct_prof_high, math_test_pct_prof_low, math_test_pct_prof_midpt, migrant, military_connected, read_test_num_valid, read_test_pct_prof_high, read_test_pct_prof_low, read_test_pct_prof_midpt, sex, year
# 
# [schools] /schools/nhgis/census-2010/{year}/
#    doc_vars=0 live_vars=47
#    PRESENT-NOT-DOCUMENTED (47): block_group, cbsa, cbsa_city, cbsa_name, cbsa_type, census_division, census_region, city_location, city_mailing, class_code, congress_district_id, county_code, county_fips_geo, csa, fips, geo_latitude, geo_longitude, geocode_accuracy, geocode_accuracy_detailed, geoid_block, geoid_place, gleaid, latitude, leaid, longitude, lower_chamber, lower_chamber_name, lower_chamber_type, ncessch, place_fips, place_name, puma, school_id, school_name, state_fips_geo, state_leg_district_lower, state_leg_district_upper, state_location, state_mailing, street_location, street_mailing, tract, upper_chamber, upper_chamber_name, year, zip_location, zip_mailing
# 
# [schools] /schools/ccd/enrollment/{year}/{grade}/sex/
#    doc_vars=1 live_vars=9
#    PRESENT-NOT-DOCUMENTED (8): enrollment, fips, grade, leaid, ncessch, ncessch_num, race, year
# 
# [colleges] /college-university/ipeds/grad-rates-200pct/{year}/
#    doc_vars=0 live_vars=17
#    PRESENT-NOT-DOCUMENTED (17): add_exclusions, cohort_adj_150pct, cohort_adj_200pct, cohort_rev, cohort_year, completers_100pct, completers_150pct, completers_200pct, completion_rate_100pct, completion_rate_150pct, completion_rate_200pct, exclusions, fips, institution_level, still_enrolled_200pct, unitid, year
# 
# [colleges] /college-university/ipeds/sfa-by-living-arrangement/{year}/
#    doc_vars=0 live_vars=11
#    PRESENT-NOT-DOCUMENTED (11): class_level, degree_seeking, fips, ftpt, level_of_study, living_arrangement, number_of_students, tuition_type, type_of_aid, unitid, year
# 
# [districts] /school-districts/ccd/enrollment/{year}/{grade}/sex/
#    doc_vars=1 live_vars=7
#    PRESENT-NOT-DOCUMENTED (6): enrollment, fips, grade, leaid, race, year
# 
# Distinct matched endpoints with NO documented-not-present var: 21
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
