# 36_crdc-race-code-probe_a.py
# Revision _a: extend the CRDC race-code probe across ALL mirror vintages
# (2011-2021 per datasets-reference.md:92) so the variable-codes.md adjudication
# covers the full documented year range, not just 2020/2021.
# (Created as a fresh revision per immutable-script versioning; 36 v1 carries its
# execution log and established {1-7,99} for 2020/2021.)

import polars as pl

# --- Config ---
# INTENT: Distinct race codes per CRDC enrollment vintage, 2011-2021.
# REASONING: variable-codes.md:154 documents "1-7, 20, 99". v1 of this probe
#   found {1-7,99} in 2020/2021; older vintages might carry 20 (or 8/9), so the
#   correct documentation depends on the union across vintages.
# ASSUMES: enrollment files exist for the documented years 2011-2021 (yearly);
#   any 404 is reported, not fatal.
REV = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
BASE = f"https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/{REV}"

union = set()
# --- Load + Profile ---
for year in range(2011, 2022):
    path = f"crdc/schools_crdc_enrollment_k12_{year}"
    url = f"{BASE}/{path}.parquet"
    try:
        lf = pl.scan_parquet(url)
        names = lf.collect_schema().names()
        if "race" not in names:
            print(f"{year}: NO race column (cols sample: {names[:8]})")
            continue
        vals = (
            lf.select(pl.col("race").unique().sort())
            .collect()
            .get_column("race")
            .to_list()
        )
        union.update(v for v in vals if v is not None)
        print(f"{year}: race distinct = {vals}")
    except Exception as e:  # noqa: BLE001 - report and continue per-vintage
        print(f"{year}: UNAVAILABLE ({type(e).__name__}: {e})")

# --- Validate ---
# INTENT: explicit adjudication of the documented set {1-7, 20, 99}.
print(f"UNION across available vintages = {sorted(union)}")
print(f"code 20 present anywhere: {20 in union}")
print(f"code 9 present anywhere: {9 in union}")
print(f"code 8 present anywhere: {8 in union}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:47:23
# Command: python3 /daaf/scripts/mirror_maintenance/36_crdc-race-code-probe_a.py
# Duration: 13s
# Exit code: 0
#
# --- STDOUT ---
# 2011: race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# 2012: UNAVAILABLE (OSError: object-store error: Object at location  not found: Error performing HEAD https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2012.parquet in 88.105648ms - Server returned non-2xx status code: 404 Not Found:  (path: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2012.parquet))
# 2013: race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# 2014: UNAVAILABLE (OSError: object-store error: Object at location  not found: Error performing HEAD https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2014.parquet in 93.061779ms - Server returned non-2xx status code: 404 Not Found:  (path: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2014.parquet))
# 2015: race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# 2016: UNAVAILABLE (OSError: object-store error: Object at location  not found: Error performing HEAD https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2016.parquet in 86.405099ms - Server returned non-2xx status code: 404 Not Found:  (path: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2016.parquet))
# 2017: race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# 2018: UNAVAILABLE (OSError: object-store error: Object at location  not found: Error performing HEAD https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2018.parquet in 96.05487ms - Server returned non-2xx status code: 404 Not Found:  (path: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2018.parquet))
# 2019: UNAVAILABLE (OSError: object-store error: Object at location  not found: Error performing HEAD https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2019.parquet in 79.195236ms - Server returned non-2xx status code: 404 Not Found:  (path: https://huggingface.co/datasets/brhkim/education_data_portal_mirror_2026q3/resolve/0ad00ce0e232c96b0642459e4e7326607a8d26aa/crdc/schools_crdc_enrollment_k12_2019.parquet))
# 2020: race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# 2021: race distinct = [1, 2, 3, 4, 5, 6, 7, 99]
# UNION across available vintages = [1, 2, 3, 4, 5, 6, 7, 99]
# code 20 present anywhere: False
# code 9 present anywhere: False
# code 8 present anywhere: False
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
