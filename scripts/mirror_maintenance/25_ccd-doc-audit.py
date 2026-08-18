# --- Config ---
# INTENT: Exhaustively verify DATA-testable claims in education-data-source-ccd
#   (SKILL.md + variable-definitions.md) against the LIVE pinned mirror.
# REASONING: Adversarial re-proof of column existence, id dtypes, coded-value sets,
#   grade/race/sex encodings, missing-code sentinels, finance column count.
# ASSUMES: pinned public repo; schema projection + distinct() over HTTP is cheap.
# Skills under test: education-data-source-ccd/SKILL.md (lines 125-200, 251-257, 327-345),
#   education-data-source-ccd/references/variable-definitions.md (grade/race/sex/locale/
#   school_type/school_level/agency_type/status/charter/magnet/virtual/title_i tables).
import polars as pl

PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"

def scan(rel):
    return pl.scan_parquet(f"{BASE}/{rel}.parquet")

def schema(rel):
    return dict(scan(rel).collect_schema())

def uniques(rel, col, cast_int=False):
    s = scan(rel).select(col)
    if cast_int:
        s = s.select(pl.col(col))
    vals = s.unique().collect()[col].to_list()
    try:
        return sorted(v for v in vals if v is not None), (None in vals)
    except TypeError:
        return vals, (None in vals)

results = []
def rec(claim, obs, verdict):
    results.append((claim, obs, verdict))
    print(f"[{verdict}] {claim}\n      -> {obs}")

# --- 1. Schemas of key CCD files (column existence + id dtypes) ---
print("\n########## SECTION 1: SCHEMAS ##########")
key_files = {
    "ccd/schools_ccd_directory": None,
    "ccd/school-districts_lea_directory": None,
    "ccd/schools_ccd_enrollment_2020": None,
    "ccd/schools_ccd_lea_enrollment_2020": None,
    "ccd/districts_ccd_finance": None,
}
schemas = {}
for rel in key_files:
    try:
        sc = schema(rel)
        schemas[rel] = sc
        print(f"\n-- {rel}: {len(sc)} cols --")
        for c, d in sc.items():
            print(f"     {c}: {d}")
    except Exception as e:
        print(f"\n-- {rel}: ERR {type(e).__name__}: {str(e)[:120]}")
        schemas[rel] = {}

# --- 2. Identifier dtype claims (SKILL.md 137-144, 329) ---
print("\n########## SECTION 2: IDENTIFIER DTYPES ##########")
# CLAIM: leaid String(+alnum) in finance, Int64 in lea_directory & saipe; ncessch present.
id_claims = {
    "ccd/districts_ccd_finance": ("leaid", "String"),
    "ccd/school-districts_lea_directory": ("leaid", "Int64"),
    "saipe/districts_saipe": ("leaid", "Int64"),
}
for rel, (col, exp) in id_claims.items():
    sc = schemas.get(rel) or schema(rel)
    dt = str(sc.get(col, "ABSENT"))
    rec(f"CCD id: {rel}.{col} dtype≈{exp}", f"dtype={dt}", "VERIFIED" if exp in dt else "CONTRADICTED")

# --- 3. Finance: 163 columns + leaid String (SKILL.md 327-329) ---
print("\n########## SECTION 3: FINANCE ##########")
sc = schemas.get("ccd/districts_ccd_finance", {})
n = len(sc)
rec("CCD finance has 163 columns (SKILL 327)", f"observed {n} cols",
    "VERIFIED" if n == 163 else "CONTRADICTED")
rec("CCD finance leaid is String (SKILL 329)", f"dtype={sc.get('leaid')}",
    "VERIFIED" if "String" in str(sc.get("leaid")) else "CONTRADICTED")

# --- 4. Enrollment coded values: grade / race / sex (var-defs 189-308) ---
print("\n########## SECTION 4: ENROLLMENT CODED VALUES (2020) ##########")
enr = "ccd/schools_ccd_enrollment_2020"
esc = schemas.get(enr, {})
for col, claim_set, note in [
    ("grade", {-1,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,99,999},
     "var-defs 189-198: -1 PreK,0 K,1-12,13,14,15,99 total,999"),
    ("race", {1,2,3,4,5,6,7,9,99}, "var-defs 267-281: 1-7,9,99; 8&20 absent in CCD"),
    ("sex", {1,2,9,99}, "var-defs 301-308: 1,2,9,99; 3 absent in CCD enrollment"),
]:
    if col not in esc:
        rec(f"CCD enrollment.{col} exists", "column ABSENT", "CONTRADICTED"); continue
    try:
        present, has_null = uniques(enr, col)
        present_set = set(present)
        documented_absent = claim_set - present_set
        present_not_doc = present_set - claim_set
        verdict = "VERIFIED"
        if present_not_doc:
            verdict = "PRESENT-NOT-DOCUMENTED"
        obs = f"present={sorted(present_set)}; doc-not-present={sorted(documented_absent)}; present-not-doc={sorted(present_not_doc)}; null={has_null}"
        rec(f"CCD enrollment.{col} coded values ({note})", obs, verdict)
    except Exception as e:
        rec(f"CCD enrollment.{col} coded values", f"ERR {type(e).__name__}: {str(e)[:120]}", "UNTESTABLE")

# --- 5. Directory coded values (var-defs school_type/school_level/charter/magnet/locale/status) ---
print("\n########## SECTION 5: SCHOOL DIRECTORY CODED VALUES ##########")
sdir = "ccd/schools_ccd_directory"
ssc = schemas.get(sdir, {})
dir_checks = [
    ("school_type", {1,2,3,4,5,-1,-2,-3}, "var-defs 367-376"),
    ("school_level", {0,1,2,3,4,5,6,7,-1,-2,-3}, "var-defs 380-392"),
    ("charter", {0,1,-1,-2,-3}, "var-defs 531-540"),
    ("magnet", {0,1,-1,-2,-3}, "var-defs 542-549"),
    ("urban_centric_locale", {11,12,13,21,22,23,31,32,33,41,42,43,9,-1,-2,-3}, "var-defs 318-337"),
]
for col, claim_set, note in dir_checks:
    if col not in ssc:
        rec(f"CCD schools_ccd_directory.{col} exists", "column ABSENT", "CONTRADICTED"); continue
    try:
        present, has_null = uniques(sdir, col)
        present_set = set(present)
        present_not_doc = present_set - claim_set
        verdict = "PRESENT-NOT-DOCUMENTED" if present_not_doc else "VERIFIED"
        obs = f"present={sorted(present_set)[:30]}; doc-not-present={sorted(claim_set-present_set)}; present-not-doc={sorted(present_not_doc)}; null={has_null}"
        rec(f"CCD schools_ccd_directory.{col} ({note})", obs, verdict)
    except Exception as e:
        rec(f"CCD schools_ccd_directory.{col}", f"ERR {type(e).__name__}: {str(e)[:120]}", "UNTESTABLE")

# --- 6. Grade-span directory vars: lowest/highest_grade_offered exist; -1 present (MISSING) ---
print("\n########## SECTION 6: GRADE-SPAN DIRECTORY VARS ##########")
for col in ["lowest_grade_offered", "highest_grade_offered"]:
    if col not in ssc:
        rec(f"CCD directory.{col} exists (var-defs 241)", f"ABSENT; dir cols sample={list(ssc)[:20]}", "DOCUMENTED-NOT-PRESENT"); continue
    try:
        present, has_null = uniques(sdir, col)
        rec(f"CCD directory.{col} present values (var-defs 241: -1=MISSING)",
            f"values={sorted(set(present))[:25]}; null={has_null}",
            "VERIFIED" if -1 in present else "PRESENT-NOT-DOCUMENTED")
    except Exception as e:
        rec(f"CCD directory.{col}", f"ERR {type(e).__name__}: {str(e)[:120]}", "UNTESTABLE")

# --- 7. LEA directory agency_type codes 1-9 (var-defs 396-406) ---
print("\n########## SECTION 7: LEA DIRECTORY agency_type ##########")
lea = "ccd/school-districts_lea_directory"
lsc = schemas.get(lea, {})
if "agency_type" in lsc:
    try:
        present, has_null = uniques(lea, "agency_type")
        claim_set = {1,2,3,4,5,6,7,8,9,-1,-2,-3}
        present_not_doc = set(present) - claim_set
        rec("CCD lea_directory.agency_type codes 1-9 (var-defs 396-406)",
            f"present={sorted(set(present))}; present-not-doc={sorted(present_not_doc)}; null={has_null}",
            "PRESENT-NOT-DOCUMENTED" if present_not_doc else "VERIFIED")
    except Exception as e:
        rec("CCD lea_directory.agency_type", f"ERR {type(e).__name__}: {str(e)[:120]}", "UNTESTABLE")
else:
    rec("CCD lea_directory.agency_type exists", f"ABSENT; cols={list(lsc)[:20]}", "CONTRADICTED")

# --- Summary ---
print("\n########## VERDICT TALLY ##########")
from collections import Counter
tally = Counter(v for _, _, v in results)
for k, v in tally.items():
    print(f"  {k}: {v}")
print("DONE 25")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:10:26
# Command: python3 /daaf/scripts/mirror_maintenance/25_ccd-doc-audit.py
# Duration: 26s
# Exit code: 0
#
# --- STDOUT ---
# 
# ########## SECTION 1: SCHEMAS ##########
# 
# -- ccd/schools_ccd_directory: 52 cols --
#      year: Int64
#      ncessch: String
#      ncessch_num: Int64
#      school_id: Int64
#      school_name: String
#      leaid: String
#      lea_name: String
#      state_leaid: String
#      seasch: String
#      street_mailing: String
#      city_mailing: String
#      state_mailing: String
#      zip_mailing: String
#      street_location: String
#      city_location: String
#      state_location: String
#      zip_location: Int64
#      phone: String
#      fips: Int64
#      latitude: Float64
#      longitude: Float64
#      csa: Int64
#      cbsa: Int64
#      urban_centric_locale: Int64
#      county_code: Int64
#      school_level: Int64
#      school_type: Int64
#      school_status: Int64
#      lowest_grade_offered: Int64
#      highest_grade_offered: Int64
#      bureau_indian_education: Int64
#      title_i_status: Int64
#      title_i_eligible: Int64
#      title_i_schoolwide: Int64
#      charter: Int64
#      magnet: Int64
#      shared_time: Int64
#      virtual: Int64
#      teachers_fte: Float64
#      free_lunch: Int64
#      reduced_price_lunch: Int64
#      free_or_reduced_price_lunch: Int64
#      direct_certification: Int64
#      enrollment: Int64
#      ungrade_cedp: Int64
#      elem_cedp: Int64
#      middle_cedp: Int64
#      high_cedp: Int64
#      lunch_program: Int64
#      congress_district_id: Int64
#      state_leg_district_lower: String
#      state_leg_district_upper: String
# 
# -- ccd/school-districts_lea_directory: 69 cols --
#      leaid: Int64
#      year: Int64
#      lea_name: String
#      fips: Int64
#      state_leaid: String
#      street_mailing: String
#      city_mailing: String
#      state_mailing: String
#      zip_mailing: Int64
#      zip4_mailing: String
#      street_location: String
#      city_location: String
#      state_location: String
#      zip_location: Int64
#      zip4_location: String
#      phone: String
#      latitude: Float64
#      longitude: Float64
#      urban_centric_locale: Int64
#      cbsa: Int64
#      cbsa_type: Int64
#      csa: Int64
#      cmsa: Int64
#      county_code: Int64
#      county_name: String
#      congress_district_id: Int64
#      state_leg_district_lower: String
#      state_leg_district_upper: String
#      bureau_indian_education: Int64
#      supervisory_union_number: Float64
#      agency_type: Int64
#      agency_level: Int64
#      boundary_change_indicator: Int64
#      agency_charter_indicator: Int64
#      lowest_grade_offered: Int64
#      highest_grade_offered: Int64
#      number_of_schools: Int64
#      enrollment: Int64
#      spec_ed_students: Int64
#      english_language_learners: Int64
#      migrant_students: Int64
#      teachers_prek_fte: Float64
#      teachers_kindergarten_fte: Float64
#      teachers_elementary_fte: Float64
#      teachers_secondary_fte: Float64
#      teachers_ungraded_fte: Float64
#      teachers_total_fte: Float64
#      instructional_aides_fte: Float64
#      coordinators_fte: Float64
#      guidance_counselors_elem_fte: Float64
#      guidance_counselors_sec_fte: Float64
#      guidance_counselors_other_fte: Float64
#      guidance_counselors_total_fte: Float64
#      school_counselors_fte: Float64
#      librarian_specialists_fte: Float64
#      librarian_support_staff_fte: Float64
#      lea_administrators_fte: Float64
#      lea_admin_support_staff_fte: Float64
#      lea_staff_total_fte: Float64
#      school_administrators_fte: Float64
#      school_admin_support_staff_fte: Float64
#      school_staff_total_fte: Float64
#      school_psychologists_fte: Float64
#      support_staff_stu_wo_psych_fte: Float64
#      support_staff_other_fte: Float64
#      staff_total_fte: Float64
#      other_staff_fte: Float64
#      necta: Int64
#      support_staff_students_fte: Float64
# 
# -- ccd/schools_ccd_enrollment_2020: 9 cols --
#      year: Int64
#      ncessch: Int64
#      ncessch_num: Int64
#      leaid: Int64
#      fips: Int64
#      grade: Int64
#      race: Int64
#      sex: Int64
#      enrollment: Int64
# 
# -- ccd/schools_ccd_lea_enrollment_2020: 7 cols --
#      year: Int64
#      leaid: Int64
#      fips: Int64
#      grade: Int64
#      race: Int64
#      sex: Int64
#      enrollment: Int64
# 
# -- ccd/districts_ccd_finance: 163 cols --
#      leaid: String
#      censusid: Int64
#      year: Int64
#      fips: Int64
#      enrollment_fall_responsible: Int64
#      enrollment_fall_school: Int64
#      rev_total: Float64
#      rev_fed_total: Float64
#      rev_fed_state_title_i: Int64
#      rev_fed_state_idea: Int64
#      rev_fed_state_vocational: Int64
#      rev_fed_state_eff_instruction: Int64
#      rev_fed_state_supp_ed: Int64
#      rev_fed_state_supp_21st_LC: Int64
#      rev_fed_state_rural_lowinc_sch: Int64
#      rev_fed_state_bilingual_ed: Int64
#      rev_fed_state_other: Int64
#      rev_fed_child_nutrition_act: Int64
#      rev_fed_nonspec: Int64
#      rev_fed_direct_impact_aid: Int64
#      rev_fed_direct_indian_ed: Int64
#      rev_fed_direct_rural_achievement: Int64
#      rev_fed_direct_other: Int64
#      rev_state_total: Float64
#      rev_state_gen_formula_assist: Float64
#      rev_state_staff_improve: Int64
#      rev_state_special_ed: Int64
#      rev_state_compens_basic_ed: Int64
#      rev_state_bilingual_ed: Int64
#      rev_state_gifted_talented: Int64
#      rev_state_vocational_ed: Int64
#      rev_state_sch_lunch: Int64
#      rev_state_outlay_capital_debt: Int64
#      rev_state_transportation: Int64
#      rev_state_oth_prog: Float64
#      rev_state_nonspec: Int64
#      rev_state_employee_benefits: Int64
#      rev_state_not_employee_benefits: Int64
#      rev_local_total: Float64
#      rev_local_parent_govt: Float64
#      rev_local_prop_tax: Float64
#      rev_local_sales_tax: Int64
#      rev_local_utility_tax: Int64
#      rev_local_income_tax: Int64
#      rev_local_other_tax: Int64
#      rev_local_other_sch_systems: Int64
#      rev_local_cities_counties: Int64
#      rev_local_tuition_fees: Int64
#      rev_local_transportation_fees: Int64
#      rev_local_sch_lunch: Int64
#      rev_local_textbook_sales_rents: Int64
#      rev_local_dist_activ_receipts: Int64
#      rev_local_student_fees_nonspec: Int64
#      rev_local_oth_sales_serv: Int64
#      rev_local_rents_royalties: Int64
#      rev_local_property_sale: Int64
#      rev_local_interest_earnings: Int64
#      rev_local_fines_forfeits: Int64
#      rev_local_private_contrib: Int64
#      rev_local_misc: Int64
#      rev_nces: Int64
#      exp_total: Float64
#      exp_current_elsec_total: Float64
#      exp_current_instruction_total: Float64
#      exp_instruction: Int64
#      payments_private_schools: Int64
#      payments_charter_schools: Int64
#      exp_current_supp_serve_total: Float64
#      exp_current_pupils: Int64
#      exp_current_instruc_staff: Int64
#      exp_current_general_admin: Int64
#      exp_current_sch_admin: Int64
#      exp_current_operation_plant: Int64
#      exp_current_student_transport: Int64
#      exp_current_bco: Int64
#      exp_current_supp_serv_nonspec: Int64
#      exp_current_other: Int64
#      exp_current_food_serv: Int64
#      exp_current_enterprise: Int64
#      exp_current_other_elsec: Int64
#      exp_nonelsec: Int64
#      exp_nonelsec_community_serv: Int64
#      exp_nonelsec_adult_education: Int64
#      exp_nonelsec_other: Int64
#      outlay_capital_total: Float64
#      outlay_capital_construction: Float64
#      outlay_capital_land_structures: Int64
#      outlay_capital_instruc_equip: Int64
#      outlay_capital_other_equip: Int64
#      outlay_capital_nonspec_equip: Int64
#      payments_state_govt: Int64
#      payments_local_govt: Int64
#      payments_other_sch_system: Int64
#      debt_interest: Int64
#      salaries_total: Float64
#      salaries_instruction: Float64
#      salaries_teachers_regular_prog: Float64
#      salaries_teachers_sped: Float64
#      salaries_teachers_vocational: Int64
#      salaries_teachers_other_ed: Int64
#      salaries_supp_pupils: Int64
#      salaries_supp_instruc_staff: Int64
#      salaries_supp_general_admin: Int64
#      salaries_supp_sch_admin: Int64
#      salaries_supp_operation_plant: Int64
#      salaries_supp_stud_transport: Int64
#      salaries_supp_bco: Int64
#      salaries_food_service: Int64
#      benefits_employee_total: Float64
#      benefits_employee_instruction: Float64
#      benefits_supp_pupils: Float64
#      benefits_supp_instruc_staff: Float64
#      benefits_supp_general_admin: Float64
#      benefits_supp_sch_admin: Float64
#      benefits_supp_operation_plant: Float64
#      benefits_supp_stud_transport: Float64
#      benefits_supp_bco: Int64
#      benefits_food_service: Int64
#      benefits_enterprise_operations: Int64
#      exp_textbooks: Int64
#      debt_longterm_outstand_beg_FY: Float64
#      debt_longterm_issued_FY: Float64
#      debt_longterm_retired_FY: Int64
#      debt_longterm_outstand_end_FY: Float64
#      debt_shortterm_outstand_beg_FY: Int64
#      debt_shortterm_outstand_end_FY: Float64
#      assets_sinking_fund: Int64
#      assets_bond_fund: Float64
#      assets_other: Float64
#      exp_utilities_energy: Float64
#      exp_tech_supplies_services: Float64
#      exp_tech_equipment: Float64
#      exp_current_state_local_funds: Float64
#      exp_current_federal_funds: Float64
#      exp_current_resa: Float64
#      exp_sped_current: Int64
#      exp_sped_instruction: Int64
#      exp_sped_pupil_support_services: Int64
#      exp_sped_staff_support_services: Int64
#      exp_sped_trans_support_services: Int64
#      rev_cares_act_relief_esser: Int64
#      rev_cares_act_relief_geer: Int64
#      rev_cares_act_relief_esf_rem: Int64
#      rev_cares_act_relief_esf_rwp: Int64
#      rev_cares_act_relief_serv: Int64
#      rev_cares_act_relief_crf: Int64
#      exp_cares_act_current: Int64
#      exp_cares_act_instruction: Int64
#      exp_cares_act_support_services: Int64
#      exp_cares_act_outlay: Int64
#      exp_cares_act_tech_service: Int64
#      exp_cares_act_tech_equipment: Int64
#      rev_crrsa_esser_ii: Int64
#      rev_arp_esser: Int64
#      rev_crrsa_geer_ii: Int64
#      rev_state_local_recovery_funds: Int64
#      exp_cares_act_tech_plant: Int64
#      exp_cares_act_food: Int64
#      rev_fed_state_math_sci_teach: Int64
#      rev_fed_state_drug_free: Int64
#      rev_fed_arra: Int64
#      exp_current_arra: Int64
#      outlay_capital_arra: Int64
# 
# ########## SECTION 2: IDENTIFIER DTYPES ##########
# [VERIFIED] CCD id: ccd/districts_ccd_finance.leaid dtype≈String
#       -> dtype=String
# [VERIFIED] CCD id: ccd/school-districts_lea_directory.leaid dtype≈Int64
#       -> dtype=Int64
# [VERIFIED] CCD id: saipe/districts_saipe.leaid dtype≈Int64
#       -> dtype=Int64
# 
# ########## SECTION 3: FINANCE ##########
# [VERIFIED] CCD finance has 163 columns (SKILL 327)
#       -> observed 163 cols
# [VERIFIED] CCD finance leaid is String (SKILL 329)
#       -> dtype=String
# 
# ########## SECTION 4: ENROLLMENT CODED VALUES (2020) ##########
# [VERIFIED] CCD enrollment.grade coded values (var-defs 189-198: -1 PreK,0 K,1-12,13,14,15,99 total,999)
#       -> present=[-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 99, 999]; doc-not-present=[]; present-not-doc=[]; null=False
# [VERIFIED] CCD enrollment.race coded values (var-defs 267-281: 1-7,9,99; 8&20 absent in CCD)
#       -> present=[1, 2, 3, 4, 5, 6, 7, 9, 99]; doc-not-present=[]; present-not-doc=[]; null=False
# [VERIFIED] CCD enrollment.sex coded values (var-defs 301-308: 1,2,9,99; 3 absent in CCD enrollment)
#       -> present=[1, 2, 9, 99]; doc-not-present=[]; present-not-doc=[]; null=False
# 
# ########## SECTION 5: SCHOOL DIRECTORY CODED VALUES ##########
# [VERIFIED] CCD schools_ccd_directory.school_type (var-defs 367-376)
#       -> present=[1, 2, 3, 4, 5]; doc-not-present=[-3, -2, -1]; present-not-doc=[]; null=True
# [VERIFIED] CCD schools_ccd_directory.school_level (var-defs 380-392)
#       -> present=[-2, -1, 0, 1, 2, 3, 4, 5, 6, 7]; doc-not-present=[-3]; present-not-doc=[]; null=True
# [VERIFIED] CCD schools_ccd_directory.charter (var-defs 531-540)
#       -> present=[-2, -1, 0, 1]; doc-not-present=[-3]; present-not-doc=[]; null=True
# [VERIFIED] CCD schools_ccd_directory.magnet (var-defs 542-549)
#       -> present=[-2, -1, 0, 1]; doc-not-present=[-3]; present-not-doc=[]; null=True
# [PRESENT-NOT-DOCUMENTED] CCD schools_ccd_directory.urban_centric_locale (var-defs 318-337)
#       -> present=[-2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43]; doc-not-present=[-3, 9]; present-not-doc=[1, 2, 3, 4, 5, 6, 7, 8]; null=True
# 
# ########## SECTION 6: GRADE-SPAN DIRECTORY VARS ##########
# [VERIFIED] CCD directory.lowest_grade_offered present values (var-defs 241: -1=MISSING)
#       -> values=[-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]; null=True
# [VERIFIED] CCD directory.highest_grade_offered present values (var-defs 241: -1=MISSING)
#       -> values=[-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]; null=True
# 
# ########## SECTION 7: LEA DIRECTORY agency_type ##########
# [VERIFIED] CCD lea_directory.agency_type codes 1-9 (var-defs 396-406)
#       -> present=[1, 2, 3, 4, 5, 6, 7, 8, 9]; present-not-doc=[]; null=True
# 
# ########## VERDICT TALLY ##########
#   VERIFIED: 15
#   PRESENT-NOT-DOCUMENTED: 1
# DONE 25
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
