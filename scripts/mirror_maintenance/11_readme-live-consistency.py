# --- Config ---
# INTENT: Verify the NEW repo's LIVE README (at the pinned revision) is internally
#   consistent with the validated build facts: object counts (497/406/91), 14 sources,
#   overall span 1979-2024, Portal version 0.26.1, and a per-source year table that
#   matches the authoritative content-based ranges from the build validation report.
# REASONING: A published README that disagrees with the shipped data misleads downstream
#   users; this is the last gate proving the human-facing description matches ground truth.
# ASSUMES: plain HTTPS. README year ranges use en-dash (U+2013) or hyphen; nhgis row
#   carries a trailing footnote marker. Regex tolerates both dash forms + trailing chars.
import re
import time
import urllib.request
import urllib.error

NEW_REPO = "brhkim/education_data_portal_mirror_2026q3"
REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
README_URL = f"https://huggingface.co/datasets/{NEW_REPO}/resolve/{REVISION}/README.md"

# INTENT: authoritative content-based per-source year ranges (build-validation_a.md §CORRECTED)
EXPECTED_YEARS = {
    "ccd": (1986, 2024), "crdc": (2011, 2022), "csafety": (2005, 2021),
    "eada": (2002, 2021), "edfacts": (2009, 2020), "fsa": (1999, 2021),
    "ipeds": (1979, 2024), "meps": (2009, 2022), "nacubo": (2012, 2022),
    "nccs": (1993, 2016), "nhgis": (1980, 2023), "pseo": (2001, 2021),
    "saipe": (1995, 2024), "scorecard": (1996, 2020),
}

# --- Fetch: live README at pinned revision (3 retries + backoff) ---
readme = None
last_err = None
for attempt in range(1, 4):
    try:
        req = urllib.request.Request(README_URL, headers={"User-Agent": "daaf-mirror-validate/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            readme = resp.read().decode("utf-8", errors="replace")
        break
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        last_err = e
        time.sleep(2 ** attempt)
assert readme is not None, f"README fetch failed: {last_err!r}"
print(f"Fetched live README at pinned revision: status={status}, {len(readme)} chars")

# --- Validate 1: global counts / version / span ---
print("\n=== V1: GLOBAL COUNTS, VERSION, SPAN ===")
global_checks = {
    "says_497_files": bool(re.search(r"\*\*497 files\*\*", readme)),
    "says_406_data_files": ("406 data files" in readme),
    "says_91_codebooks": ("91 codebooks" in readme),
    "says_14_data_sources": bool(re.search(r"\*\*14 data sources\*\*", readme)),
    "says_span_1979_to_2024": ("1979 to 2024" in readme),
    "names_version_0.26.1": ("0.26.1" in readme),
    "predecessor_0.24.0_present": ("0.24.0" in readme),  # predecessor reference expected
}
for k, v in global_checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")

# --- Validate 2: per-source year table matches authoritative ranges ---
print("\n=== V2: PER-SOURCE YEAR RANGES (README vs build-validation authoritative) ===")
lines = readme.splitlines()
year_results = {}
year_all_ok = True
data_total = 0
cb_total = 0
count_parse_ok = True
for src, (emin, emax) in EXPECTED_YEARS.items():
    # INTENT: locate the table row for this source (backtick-wrapped token in a table row)
    row = next((ln for ln in lines if f"`{src}`" in ln and ln.lstrip().startswith("|")), None)
    if row is None:
        year_results[src] = ("ROW-NOT-FOUND", None, None)
        year_all_ok = False
        continue
    # INTENT: extract the YYYY-YYYY range (en-dash or hyphen) from the Years column
    m = re.search(r"(\d{4})\s*[–\-]\s*(\d{4})", row)
    if not m:
        year_results[src] = ("RANGE-NOT-PARSED", None, None)
        year_all_ok = False
        continue
    rmin, rmax = int(m.group(1)), int(m.group(2))
    ok = (rmin == emin and rmax == emax)
    year_all_ok = year_all_ok and ok
    year_results[src] = (f"{rmin}-{rmax}", f"{emin}-{emax}", ok)
    # INTENT: opportunistically parse Data Files / Codebooks columns to cross-check totals
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    nums = [c for c in cells if re.fullmatch(r"\d+", c)]
    if len(nums) >= 2:
        data_total += int(nums[0])
        cb_total += int(nums[1])
    else:
        count_parse_ok = False
    print(f"  [{'PASS' if ok else 'FAIL'}] {src:10s} readme={year_results[src][0]:>11s} expected={emin}-{emax}")

print(f"\nParsed per-source count totals: data_files={data_total}, codebooks={cb_total} (expected 406 / 91)")

# --- VERDICT ---
print("\n=== VERDICT ===")
checks = dict(global_checks)
checks["all_per_source_year_ranges_match"] = year_all_ok
checks["per_source_data_files_sum==406"] = (data_total == 406)
checks["per_source_codebooks_sum==91"] = (cb_total == 91)
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
all_pass = all(checks.values())
print(f"\nSCRIPT 11 OVERALL: {'PASS' if all_pass else 'FAIL'}")
assert all_pass, f"README consistency FAILED: {[k for k,v in checks.items() if not v]}"
print("Live README is consistent with validated build facts (counts, version, span, year table).")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:13:28
# Command: python3 /daaf/scripts/mirror_maintenance/11_readme-live-consistency.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Fetched live README at pinned revision: status=200, 10620 chars
# 
# === V1: GLOBAL COUNTS, VERSION, SPAN ===
#   [PASS] says_497_files
#   [PASS] says_406_data_files
#   [PASS] says_91_codebooks
#   [PASS] says_14_data_sources
#   [PASS] says_span_1979_to_2024
#   [PASS] names_version_0.26.1
#   [PASS] predecessor_0.24.0_present
# 
# === V2: PER-SOURCE YEAR RANGES (README vs build-validation authoritative) ===
#   [PASS] ccd        readme=  1986-2024 expected=1986-2024
#   [PASS] crdc       readme=  2011-2022 expected=2011-2022
#   [PASS] csafety    readme=  2005-2021 expected=2005-2021
#   [PASS] eada       readme=  2002-2021 expected=2002-2021
#   [PASS] edfacts    readme=  2009-2020 expected=2009-2020
#   [PASS] fsa        readme=  1999-2021 expected=1999-2021
#   [PASS] ipeds      readme=  1979-2024 expected=1979-2024
#   [PASS] meps       readme=  2009-2022 expected=2009-2022
#   [PASS] nacubo     readme=  2012-2022 expected=2012-2022
#   [PASS] nccs       readme=  1993-2016 expected=1993-2016
#   [PASS] nhgis      readme=  1980-2023 expected=1980-2023
#   [PASS] pseo       readme=  2001-2021 expected=2001-2021
#   [PASS] saipe      readme=  1995-2024 expected=1995-2024
#   [PASS] scorecard  readme=  1996-2020 expected=1996-2020
# 
# Parsed per-source count totals: data_files=406, codebooks=91 (expected 406 / 91)
# 
# === VERDICT ===
#   [PASS] says_497_files
#   [PASS] says_406_data_files
#   [PASS] says_91_codebooks
#   [PASS] says_14_data_sources
#   [PASS] says_span_1979_to_2024
#   [PASS] names_version_0.26.1
#   [PASS] predecessor_0.24.0_present
#   [PASS] all_per_source_year_ranges_match
#   [PASS] per_source_data_files_sum==406
#   [PASS] per_source_codebooks_sum==91
# 
# SCRIPT 11 OVERALL: PASS
# Live README is consistent with validated build facts (counts, version, span, year table).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
