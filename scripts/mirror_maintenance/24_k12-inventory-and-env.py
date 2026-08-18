# --- Config ---
# INTENT: Enumerate the K-12 mirror file inventory (ccd, crdc, edfacts, meps, saipe,
#   csafety) from the build manifest, and test whether an xls-codebook reader is
#   available in-container. Foundation for the exhaustive K-12 doc audit.
# REASONING: Before verifying skill claims about columns/coded values, establish
#   ground truth on which files actually exist in the pinned mirror and whether the
#   91 mirrored .xls codebooks can be parsed here (calamine/xlrd/openpyxl).
# ASSUMES: build_manifest.parquet lists relative_path for every shipped object.
import polars as pl

BASE = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update"
MANIFEST = f"{BASE}/mirror_v2_tree/build_manifest.parquet"

man = pl.read_parquet(MANIFEST)
print("MANIFEST COLUMNS:", man.columns)
print("MANIFEST ROWS:", man.height)

# --- K-12 source inventory ---
# INTENT: list every parquet + xls per K-12 source dir so claim inventory maps to real files.
k12 = ["ccd", "crdc", "edfacts", "meps", "saipe", "csafety"]
paths = man.get_column("relative_path").to_list()
for src in k12:
    parquet = sorted(p for p in paths if p.startswith(f"{src}/") and p.endswith(".parquet"))
    xls = sorted(p for p in paths if p.startswith(f"{src}/") and p.endswith(".xls"))
    print(f"\n===== {src}: {len(parquet)} parquet, {len(xls)} xls =====")
    for p in parquet:
        print("  P", p.split("/", 1)[1])
    for p in xls:
        print("  X", p.split("/", 1)[1])

# --- xls reader availability ---
# INTENT: determine if codebook cross-checks are feasible in-container.
print("\n===== XLS READER PROBE =====")
for mod in ["xlrd", "openpyxl", "fastexcel", "calamine", "python_calamine"]:
    try:
        m = __import__(mod)
        print(f"  {mod}: AVAILABLE {getattr(m, '__version__', '?')}")
    except Exception as e:
        print(f"  {mod}: MISSING ({type(e).__name__})")

# INTENT: try polars.read_excel on one mirrored codebook via pinned URL.
PIN = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
RESOLVE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{PIN}"
cb = next((p for p in paths if p.startswith("ccd/") and p.endswith(".xls")), None)
print("  sample codebook:", cb)
if cb:
    import urllib.request
    try:
        url = f"{RESOLVE}/{cb}"
        req = urllib.request.Request(url, headers={"User-Agent": "daaf-audit"})
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
        print(f"  downloaded {len(raw)} bytes")
        import io
        try:
            df = pl.read_excel(io.BytesIO(raw))
            print(f"  polars.read_excel OK: shape={df.shape}, cols={df.columns[:8]}")
        except Exception as e:
            print(f"  polars.read_excel FAILED: {type(e).__name__}: {str(e)[:150]}")
    except Exception as e:
        print(f"  codebook download FAILED: {type(e).__name__}: {str(e)[:150]}")

print("\nDONE 24")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:09:16
# Command: python3 /daaf/scripts/mirror_maintenance/24_k12-inventory-and-env.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# MANIFEST COLUMNS: ['canonical_object_key', 'source', 'object_kind', 'relative_path', 'filename', 'provenance', 'classification', 'source_url', 'source_content_length', 'source_last_modified', 'source_etag', 'expected_oid', 'oid_kind', 'shipped_bytes', 'shipped_sha256', 'row_count', 'column_count', 'verification_method', 'verification_result', 'action', 'observed_at_utc']
# MANIFEST ROWS: 497
# 
# ===== ccd: 81 parquet, 5 xls =====
#   P districts_ccd_finance.parquet
#   P school-districts_lea_directory.parquet
#   P schools_ccd_directory.parquet
#   P schools_ccd_enrollment_1986.parquet
#   P schools_ccd_enrollment_1987.parquet
#   P schools_ccd_enrollment_1988.parquet
#   P schools_ccd_enrollment_1989.parquet
#   P schools_ccd_enrollment_1990.parquet
#   P schools_ccd_enrollment_1991.parquet
#   P schools_ccd_enrollment_1992.parquet
#   P schools_ccd_enrollment_1993.parquet
#   P schools_ccd_enrollment_1994.parquet
#   P schools_ccd_enrollment_1995.parquet
#   P schools_ccd_enrollment_1996.parquet
#   P schools_ccd_enrollment_1997.parquet
#   P schools_ccd_enrollment_1998.parquet
#   P schools_ccd_enrollment_1999.parquet
#   P schools_ccd_enrollment_2000.parquet
#   P schools_ccd_enrollment_2001.parquet
#   P schools_ccd_enrollment_2002.parquet
#   P schools_ccd_enrollment_2003.parquet
#   P schools_ccd_enrollment_2004.parquet
#   P schools_ccd_enrollment_2005.parquet
#   P schools_ccd_enrollment_2006.parquet
#   P schools_ccd_enrollment_2007.parquet
#   P schools_ccd_enrollment_2008.parquet
#   P schools_ccd_enrollment_2009.parquet
#   P schools_ccd_enrollment_2010.parquet
#   P schools_ccd_enrollment_2011.parquet
#   P schools_ccd_enrollment_2012.parquet
#   P schools_ccd_enrollment_2013.parquet
#   P schools_ccd_enrollment_2014.parquet
#   P schools_ccd_enrollment_2015.parquet
#   P schools_ccd_enrollment_2016.parquet
#   P schools_ccd_enrollment_2017.parquet
#   P schools_ccd_enrollment_2018.parquet
#   P schools_ccd_enrollment_2019.parquet
#   P schools_ccd_enrollment_2020.parquet
#   P schools_ccd_enrollment_2021.parquet
#   P schools_ccd_enrollment_2022.parquet
#   P schools_ccd_enrollment_2023.parquet
#   P schools_ccd_enrollment_2024.parquet
#   P schools_ccd_lea_enrollment_1986.parquet
#   P schools_ccd_lea_enrollment_1987.parquet
#   P schools_ccd_lea_enrollment_1988.parquet
#   P schools_ccd_lea_enrollment_1989.parquet
#   P schools_ccd_lea_enrollment_1990.parquet
#   P schools_ccd_lea_enrollment_1991.parquet
#   P schools_ccd_lea_enrollment_1992.parquet
#   P schools_ccd_lea_enrollment_1993.parquet
#   P schools_ccd_lea_enrollment_1994.parquet
#   P schools_ccd_lea_enrollment_1995.parquet
#   P schools_ccd_lea_enrollment_1996.parquet
#   P schools_ccd_lea_enrollment_1997.parquet
#   P schools_ccd_lea_enrollment_1998.parquet
#   P schools_ccd_lea_enrollment_1999.parquet
#   P schools_ccd_lea_enrollment_2000.parquet
#   P schools_ccd_lea_enrollment_2001.parquet
#   P schools_ccd_lea_enrollment_2002.parquet
#   P schools_ccd_lea_enrollment_2003.parquet
#   P schools_ccd_lea_enrollment_2004.parquet
#   P schools_ccd_lea_enrollment_2005.parquet
#   P schools_ccd_lea_enrollment_2006.parquet
#   P schools_ccd_lea_enrollment_2007.parquet
#   P schools_ccd_lea_enrollment_2008.parquet
#   P schools_ccd_lea_enrollment_2009.parquet
#   P schools_ccd_lea_enrollment_2010.parquet
#   P schools_ccd_lea_enrollment_2011.parquet
#   P schools_ccd_lea_enrollment_2012.parquet
#   P schools_ccd_lea_enrollment_2013.parquet
#   P schools_ccd_lea_enrollment_2014.parquet
#   P schools_ccd_lea_enrollment_2015.parquet
#   P schools_ccd_lea_enrollment_2016.parquet
#   P schools_ccd_lea_enrollment_2017.parquet
#   P schools_ccd_lea_enrollment_2018.parquet
#   P schools_ccd_lea_enrollment_2019.parquet
#   P schools_ccd_lea_enrollment_2020.parquet
#   P schools_ccd_lea_enrollment_2021.parquet
#   P schools_ccd_lea_enrollment_2022.parquet
#   P schools_ccd_lea_enrollment_2023.parquet
#   P schools_ccd_lea_enrollment_2024.parquet
#   X codebook_districts_ccd_directory.xls
#   X codebook_districts_ccd_enrollment.xls
#   X codebook_districts_ccd_finance.xls
#   X codebook_schools_ccd_directory.xls
#   X codebook_schools_ccd_enrollment.xls
# 
# ===== crdc: 66 parquet, 24 xls =====
#   P schools_crdc_algebra_2011.parquet
#   P schools_crdc_algebra_2013.parquet
#   P schools_crdc_algebra_2015.parquet
#   P schools_crdc_algebra_2017.parquet
#   P schools_crdc_algebra_2020.parquet
#   P schools_crdc_algebra_2021.parquet
#   P schools_crdc_ap_exams_2011.parquet
#   P schools_crdc_ap_exams_2013.parquet
#   P schools_crdc_ap_exams_2015.parquet
#   P schools_crdc_ap_exams_2017.parquet
#   P schools_crdc_apib_enroll.parquet
#   P schools_crdc_chronic_absenteeism_2013.parquet
#   P schools_crdc_chronic_absenteeism_2015.parquet
#   P schools_crdc_chronic_absenteeism_2017.parquet
#   P schools_crdc_chronic_absenteeism_2020.parquet
#   P schools_crdc_chronic_absenteeism_2021.parquet
#   P schools_crdc_chronic_absenteeism_2022.parquet
#   P schools_crdc_covid_indicators.parquet
#   P schools_crdc_credit_recovery.parquet
#   P schools_crdc_discipline_k12_2011.parquet
#   P schools_crdc_discipline_k12_2013.parquet
#   P schools_crdc_discipline_k12_2015.parquet
#   P schools_crdc_discipline_k12_2017.parquet
#   P schools_crdc_discipline_k12_2020.parquet
#   P schools_crdc_discipline_k12_2021.parquet
#   P schools_crdc_disciplineinstances.parquet
#   P schools_crdc_dual_enrollment.parquet
#   P schools_crdc_enrollment_k12_2011.parquet
#   P schools_crdc_enrollment_k12_2013.parquet
#   P schools_crdc_enrollment_k12_2015.parquet
#   P schools_crdc_enrollment_k12_2017.parquet
#   P schools_crdc_enrollment_k12_2020.parquet
#   P schools_crdc_enrollment_k12_2021.parquet
#   P schools_crdc_finance.parquet
#   P schools_crdc_harass_bully_allegations.parquet
#   P schools_crdc_harass_bully_students_2011.parquet
#   P schools_crdc_harass_bully_students_2013.parquet
#   P schools_crdc_harass_bully_students_2015.parquet
#   P schools_crdc_harass_bully_students_2017.parquet
#   P schools_crdc_harass_bully_students_2020.parquet
#   P schools_crdc_harass_bully_students_2021.parquet
#   P schools_crdc_internet_access.parquet
#   P schools_crdc_mathandscience.parquet
#   P schools_crdc_offenses.parquet
#   P schools_crdc_offerings.parquet
#   P schools_crdc_restraint_seclusion_instances.parquet
#   P schools_crdc_restraint_seclusion_students_2011.parquet
#   P schools_crdc_restraint_seclusion_students_2013.parquet
#   P schools_crdc_restraint_seclusion_students_2015.parquet
#   P schools_crdc_restraint_seclusion_students_2017.parquet
#   P schools_crdc_restraint_seclusion_students_2020.parquet
#   P schools_crdc_restraint_seclusion_students_2021.parquet
#   P schools_crdc_retention_2011.parquet
#   P schools_crdc_retention_2013.parquet
#   P schools_crdc_retention_2015.parquet
#   P schools_crdc_retention_2017.parquet
#   P schools_crdc_retention_2020.parquet
#   P schools_crdc_sat_and_act_participation_2011.parquet
#   P schools_crdc_sat_and_act_participation_2013.parquet
#   P schools_crdc_sat_and_act_participation_2015.parquet
#   P schools_crdc_sat_and_act_participation_2017.parquet
#   P schools_crdc_sat_and_act_participation_2020.parquet
#   P schools_crdc_sat_and_act_participation_2021.parquet
#   P schools_crdc_school_characteristics.parquet
#   P schools_crdc_suspensions.parquet
#   P schools_crdc_teacher.parquet
#   X codebook_schools_crdc_algebra-1.xls
#   X codebook_schools_crdc_ap-exams.xls
#   X codebook_schools_crdc_ap-ib-enrollment.xls
#   X codebook_schools_crdc_chronic-absenteeism.xls
#   X codebook_schools_crdc_covid_indicators.xls
#   X codebook_schools_crdc_credit-recovery.xls
#   X codebook_schools_crdc_directory.xls
#   X codebook_schools_crdc_discipline.xls
#   X codebook_schools_crdc_discipline_instances.xls
#   X codebook_schools_crdc_dual_enrollment.xls
#   X codebook_schools_crdc_enrollment.xls
#   X codebook_schools_crdc_finance.xls
#   X codebook_schools_crdc_harrassment-bullying-allegations.xls
#   X codebook_schools_crdc_harrassment-bullying-students.xls
#   X codebook_schools_crdc_internet_access.xls
#   X codebook_schools_crdc_math-and-science.xls
#   X codebook_schools_crdc_offenses.xls
#   X codebook_schools_crdc_offerings.xls
#   X codebook_schools_crdc_restraint-seclusion-instances.xls
#   X codebook_schools_crdc_restraint-seclusion-students.xls
#   X codebook_schools_crdc_retention.xls
#   X codebook_schools_crdc_sat-act-participation.xls
#   X codebook_schools_crdc_suspensions_days.xls
#   X codebook_schools_crdc_teachers_staff.xls
# 
# ===== edfacts: 42 parquet, 4 xls =====
#   P districts_edfacts_assessments_2009.parquet
#   P districts_edfacts_assessments_2010.parquet
#   P districts_edfacts_assessments_2011.parquet
#   P districts_edfacts_assessments_2012.parquet
#   P districts_edfacts_assessments_2013.parquet
#   P districts_edfacts_assessments_2014.parquet
#   P districts_edfacts_assessments_2015.parquet
#   P districts_edfacts_assessments_2016.parquet
#   P districts_edfacts_assessments_2017.parquet
#   P districts_edfacts_assessments_2018.parquet
#   P districts_edfacts_assessments_2020.parquet
#   P districts_edfacts_grad_rates_2010.parquet
#   P districts_edfacts_grad_rates_2011.parquet
#   P districts_edfacts_grad_rates_2012.parquet
#   P districts_edfacts_grad_rates_2013.parquet
#   P districts_edfacts_grad_rates_2014.parquet
#   P districts_edfacts_grad_rates_2015.parquet
#   P districts_edfacts_grad_rates_2016.parquet
#   P districts_edfacts_grad_rates_2017.parquet
#   P districts_edfacts_grad_rates_2018.parquet
#   P districts_edfacts_grad_rates_2019.parquet
#   P schools_edfacts_assessments_2009.parquet
#   P schools_edfacts_assessments_2010.parquet
#   P schools_edfacts_assessments_2011.parquet
#   P schools_edfacts_assessments_2012.parquet
#   P schools_edfacts_assessments_2013.parquet
#   P schools_edfacts_assessments_2014.parquet
#   P schools_edfacts_assessments_2015.parquet
#   P schools_edfacts_assessments_2016.parquet
#   P schools_edfacts_assessments_2017.parquet
#   P schools_edfacts_assessments_2018.parquet
#   P schools_edfacts_assessments_2020.parquet
#   P schools_edfacts_grad_rates_2010.parquet
#   P schools_edfacts_grad_rates_2011.parquet
#   P schools_edfacts_grad_rates_2012.parquet
#   P schools_edfacts_grad_rates_2013.parquet
#   P schools_edfacts_grad_rates_2014.parquet
#   P schools_edfacts_grad_rates_2015.parquet
#   P schools_edfacts_grad_rates_2016.parquet
#   P schools_edfacts_grad_rates_2017.parquet
#   P schools_edfacts_grad_rates_2018.parquet
#   P schools_edfacts_grad_rates_2019.parquet
#   X codebook_districts_edfacts_assessments.xls
#   X codebook_districts_edfacts_graduation.xls
#   X codebook_schools_edfacts_assessments.xls
#   X codebook_schools_edfacts_graduation.xls
# 
# ===== meps: 1 parquet, 1 xls =====
#   P schools_meps.parquet
#   X codebook_schools_meps.xls
# 
# ===== saipe: 1 parquet, 1 xls =====
#   P districts_saipe.parquet
#   X codebook_districts_saipe.xls
# 
# ===== csafety: 1 parquet, 1 xls =====
#   P colleges_csafety_hate_crimes.parquet
#   X codebook_colleges_csafety_hate_crimes.xls
# 
# ===== XLS READER PROBE =====
#   xlrd: AVAILABLE 2.0.2
#   openpyxl: AVAILABLE 3.1.5
#   fastexcel: AVAILABLE 0.19.0
#   calamine: MISSING (ModuleNotFoundError)
#   python_calamine: MISSING (ModuleNotFoundError)
#   sample codebook: ccd/codebook_districts_ccd_directory.xls
#   downloaded 49152 bytes
#   polars.read_excel OK: shape=(69, 3), cols=['variable', 'format', 'label']
# 
# DONE 24
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
