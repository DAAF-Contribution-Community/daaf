# --- Config ---
# INTENT: datasets-reference.md existence sweep — verify every POSTSECONDARY (colleges)
#         data path AND codebook path documented in
#         education-data-query/references/datasets-reference.md actually exists on the
#         pinned mirror tree, via ONE recursive tree-API listing (cheap existence check).
# REASONING: The catalog is the authoritative planning surface; a documented path that
#            404s is a CONTRADICTED existence claim. Uses the tree API once, then set-membership.
# ASSUMES: pinned public repo; huggingface_hub not installed -> plain urllib. Tree API
#          paginates via RFC-5988 Link headers. Yearly datasets expand over stated year ranges.
# Skills under test: education-data-query/references/datasets-reference.md
#   (IPEDS/Scorecard/PSEO/NHGIS-colleges/NCCS/FSA/EADA/NACUBO rows: path + codebook columns).
import json
import time
import urllib.request
import urllib.error

REPO = "datasets/brhkim/education_data_portal_mirror_2026q3"
REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
TREE_URL = f"https://huggingface.co/api/{REPO}/tree/{REVISION}?recursive=true"

# --- Fetch: full remote tree, paginated via Link rel=next, with retries+backoff ---
entries = []
next_url = TREE_URL
page = 0
while next_url is not None:
    page += 1
    body = None
    last_err = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(next_url, headers={"User-Agent": "daaf-doc-audit/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                resp_headers = resp.headers
            break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  page {page} attempt {attempt} failed: {e!r}; backoff {wait}s")
            time.sleep(wait)
    assert body is not None, f"page {page} failed after retries: {last_err!r}"
    chunk = json.loads(body.decode("utf-8"))
    entries.extend(chunk)
    link = resp_headers.get("Link") if resp_headers else None
    next_url = None
    if link:
        for part in link.split(","):
            segs = part.split(";")
            if len(segs) >= 2 and 'rel="next"' in segs[1]:
                next_url = segs[0].strip().strip("<>")
print(f"Fetched {len(entries)} raw tree entries across {page} page(s)")

# INTENT: build a set of all file paths present on the mirror (relative, extensionful)
present = {e["path"] for e in entries if e.get("type") == "file"}
print(f"File entries present: {len(present)}")

# --- Build: expected POSTSECONDARY paths from datasets-reference.md (verbatim) ---
# Each tuple: (canonical_path, kind) where kind in {parquet-single, parquet-yearly, xls-codebook}
# Yearly datasets carry a year list to expand.
single_data = [
    # IPEDS single-file (datasets-reference.md lines ~163-201)
    "ipeds/colleges_ipeds_directory",
    "ipeds/colleges_ipeds_admissions-enrollment",
    "ipeds/colleges_ipeds_enrollment-fte",
    "ipeds/colleges_ipeds_grad-rates",
    "ipeds/colleges_ipeds_finance",
    "ipeds/colleges_ipeds_academic_libraries",
    "ipeds/colleges_ipeds_admissions-requirements",
    "ipeds/colleges_ipeds_ay_room_board_other",
    "ipeds/colleges_ipeds_ay_tuition_fees",
    "ipeds/colleges_ipeds_ay_tuition_firstprof",
    "ipeds/colleges_ipeds_completers",
    "ipeds/colleges_ipeds_headcount",
    "ipeds/colleges_ipeds_fall-res",
    "ipeds/colleges_ipeds_fall-retention",
    "ipeds/colleges_ipeds_grad-rates-200pct",
    "ipeds/colleges_ipeds_grad-rates-pell",
    "ipeds/colleges_ipeds_institutional-characteristics",
    "ipeds/colleges_ipeds_salaries_is",
    "ipeds/colleges_ipeds_salaries_nis",
    "ipeds/colleges_ipeds_outcome-measures",
    "ipeds/colleges_ipeds_py_room_board_other",
    "ipeds/colleges_ipeds_py_tuition_cip",
    "ipeds/colleges_ipeds_sfa_all_undergrads",
    "ipeds/colleges_ipeds_sfa_by_living_arrangement",
    "ipeds/colleges_ipeds_sfa_by_tuition_type",
    "ipeds/colleges_ipeds_sfa_ftft",
    "ipeds/colleges_ipeds_sfa_grants_and_net_price",
    "ipeds/colleges_ipeds_student-faculty-ratio",
    # Scorecard (6 families)
    "scorecard/colleges_scorecard_earnings",
    "scorecard/colleges_scorecard_repayment_fsa",
    "scorecard/colleges_scorecard_inst_characteristics",
    "scorecard/colleges_scorecard_repayment_nslds",
    "scorecard/colleges_scorecard_student_body_nslds",
    "scorecard/colleges_scorecard_student_body_treasury",
    # NHGIS colleges (4)
    "nhgis/colleges_nhgis_geog_1990",
    "nhgis/colleges_nhgis_geog_2000",
    "nhgis/colleges_nhgis_geog_2010",
    "nhgis/colleges_nhgis_geog_2020",
    # NCCS (1)
    "nccs/colleges_nccs_all",
    # FSA (5)
    "fsa/colleges_fsa_grants",
    "fsa/colleges_fsa_loans",
    "fsa/colleges_fsa_campus_based_volume",
    "fsa/colleges_fsa_composite_scores",
    "fsa/colleges_fsa_90_10_revenue_percentages",
    # EADA (1)
    "eada/colleges_eada_inst_characteristics",
    # NACUBO (1)
    "nacubo/colleges_nacubo_endow",
]

# Yearly datasets (path template -> list of years, from datasets-reference.md)
yearly_data = {
    # Completions 2digcip 1991-2023 (all years)
    "ipeds/colleges_ipeds_completions-2digcip_{y}": list(range(1991, 2024)),
    # Completions 6digcip 1983-2023 (all years)
    "ipeds/colleges_ipeds_completions-6digcip_{y}": list(range(1983, 2024)),
    # Fall Enrollment Age: non-contiguous 1991,1993,1995,1997,1999-2024
    "ipeds/colleges_ipeds_fall-enrollment-age_{y}": [1991, 1993, 1995, 1997] + list(range(1999, 2025)),
    # Fall Enrollment Race: 1986-2024 (all years)
    "ipeds/colleges_ipeds_fall-enrollment-race_{y}": list(range(1986, 2025)),
    # PSEO 2001-2021 (all years)
    "pseo/colleges_pseo_{y}": list(range(2001, 2022)),
}

# Codebook paths (.xls) documented in datasets-reference.md for postsecondary rows
codebooks = [
    "ipeds/codebook_colleges_ipeds_directory",
    "ipeds/codebook_colleges_ipeds_admissions-enrollment",
    "ipeds/codebook_colleges_ipeds_enrollment-fte",
    "ipeds/codebook_colleges_ipeds_grad-rates",
    "ipeds/codebook_colleges_ipeds_finance",
    "ipeds/codebook_colleges_ipeds_academic-libraries",
    "ipeds/codebook_colleges_ipeds_admissions-requirements",
    "ipeds/codebook_colleges_ipeds_completers",
    "ipeds/codebook_colleges_ipeds_enrollment-headcount",
    "ipeds/codebook_colleges_ipeds_fall-enrollment-residence",
    "ipeds/codebook_colleges_ipeds_fall-retention",
    "ipeds/codebook_colleges_ipeds_grad-rates-200pct",
    "ipeds/codebook_colleges_ipeds_grad-rates-pell",
    "ipeds/codebook_colleges_ipeds_institutional-characteristics",
    "ipeds/codebook_colleges_ipeds_instructional_staff_salaries",
    "ipeds/codebook_colleges_ipeds_noninstructional_staff_salaries",
    "ipeds/codebook_colleges_ipeds_outcome-measures",
    "ipeds/codebook_colleges_ipeds_sfa_all_undergrads",
    "ipeds/codebook_colleges_ipeds_sfa_by_living_arrangement",
    "ipeds/codebook_colleges_ipeds_sfa_by_tuition_type",
    "ipeds/codebook_colleges_ipeds_sfa_FTFT",  # NOTE: case-sensitive per naming note
    "ipeds/codebook_colleges_ipeds_sfa_grants_and_net_price",
    "ipeds/codebook_colleges_ipeds_student-faculty-ratio",
    "ipeds/codebook_colleges_ipeds_completions-2digcip",
    "ipeds/codebook_colleges_ipeds_completions-6digcip",
    "ipeds/codebook_colleges_ipeds_fall-enrollment-age",
    "ipeds/codebook_colleges_ipeds_fall-enrollment-race",
    "scorecard/codebook_colleges_scorecard_earnings",
    "scorecard/codebook_colleges_scorecard_default",
    "scorecard/codebook_colleges_scorecard_institutional-characteristics",
    "scorecard/codebook_colleges_scorecard_repayment",
    "scorecard/codebook_colleges_scorecard_student-characteristics_aid-applicants",
    "scorecard/codebook_colleges_scorecard_student-characteristics_home-neighborhood",
    "pseo/codebook_colleges_pseo",
    "nhgis/codebook_colleges_nhgis_census1990",
    "nhgis/codebook_colleges_nhgis_census2000",
    "nhgis/codebook_colleges_nhgis_census2010",
    "nhgis/codebook_colleges_nhgis_census2020",
    "nccs/codebook_colleges_nccs_form_990",
    "fsa/codebook_colleges_fsa_grants",
    "fsa/codebook_colleges_fsa_loans",
    "fsa/codebook_colleges_fsa_campus_based_volume",
    "fsa/codebook_colleges_fsa_financial_responsibility",
    "fsa/codebook_colleges_fsa_90-10_revenue_percentages",
    "eada/codebook_colleges_eada_inst-characteristics",
    "nacubo/codebook_colleges_nacubo_endowments",
]

# --- Verify: existence checks against the present-set ---
missing = []
checked = 0

# Single-file data paths -> expect .parquet
for p in single_data:
    checked += 1
    if f"{p}.parquet" not in present:
        missing.append((f"{p}.parquet", "single-parquet DOCUMENTED-NOT-PRESENT"))

# Yearly data paths -> expect each year .parquet
for tmpl, years in yearly_data.items():
    for y in years:
        checked += 1
        pth = tmpl.format(y=y) + ".parquet"
        if pth not in present:
            missing.append((pth, "yearly-parquet DOCUMENTED-NOT-PRESENT"))

# Codebooks -> expect .xls
for c in codebooks:
    checked += 1
    if f"{c}.xls" not in present:
        missing.append((f"{c}.xls", "codebook-xls DOCUMENTED-NOT-PRESENT"))

print(f"\n=== EXISTENCE SWEEP (postsecondary) ===")
print(f"Total documented paths checked: {checked}")
print(f"DOCUMENTED-NOT-PRESENT count: {len(missing)}")
for pth, tag in missing:
    print(f"  MISSING: {pth}  [{tag}]")

# INTENT: also report PRESENT-NOT-DOCUMENTED colleges/* parquet files (undocumented datasets).
# REASONING: catch new postsecondary datasets on the mirror not listed in the catalog.
documented_data_exact = {f"{p}.parquet" for p in single_data}
for tmpl, years in yearly_data.items():
    for y in years:
        documented_data_exact.add(tmpl.format(y=y) + ".parquet")
present_college_parquet = {p for p in present if p.endswith(".parquet") and "/colleges_" in p}
undocumented = sorted(present_college_parquet - documented_data_exact)
print(f"\nPRESENT-NOT-DOCUMENTED colleges/* parquet (not in datasets-reference postsec catalog): {len(undocumented)}")
for u in undocumented:
    print(f"  UNDOCUMENTED: {u}")

# --- Validate ---
assert checked > 200, "Expected 200+ documented postsecondary paths; enumeration too small"
print(f"\nVALIDATION: checked={checked} (expected >200) PASS")
print("VERDICT tallies:")
print(f"  data/codebook existence VERIFIED: {checked - len(missing)}")
print(f"  DOCUMENTED-NOT-PRESENT: {len(missing)}")
print(f"  PRESENT-NOT-DOCUMENTED (undocumented college parquet): {len(undocumented)}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:11:35
# Command: python3 /daaf/scripts/mirror_maintenance/28_doc-audit-existence-sweep.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Fetched 514 raw tree entries across 1 page(s)
# File entries present: 500
# 
# === EXISTENCE SWEEP (postsecondary) ===
# Total documented paths checked: 256
# DOCUMENTED-NOT-PRESENT count: 0
# 
# PRESENT-NOT-DOCUMENTED colleges/* parquet (not in datasets-reference postsec catalog): 1
#   UNDOCUMENTED: csafety/colleges_csafety_hate_crimes.parquet
# 
# VALIDATION: checked=256 (expected >200) PASS
# VERDICT tallies:
#   data/codebook existence VERIFIED: 256
#   DOCUMENTED-NOT-PRESENT: 0
#   PRESENT-NOT-DOCUMENTED (undocumented college parquet): 1
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
