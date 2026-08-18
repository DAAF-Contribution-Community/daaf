# --- Config ---
# INTENT: Verify the OLD mirror (Portal v0.24.0) is properly frozen and still serving:
#   (1) its live README carries a freeze banner naming v0.24.0; (2) a sample of old
#   resolve URLs still return HTTP 200 (old analyses keep working); (3) record the old
#   repo's current commit SHA for predecessor-block pinning.
# REASONING: Freezing the predecessor must not break reproducibility of prior analyses,
#   so both the freeze notice AND continued availability must hold.
# ASSUMES: plain HTTPS. HF resolve for LFS files 302-redirects to a CDN; urllib follows
#   redirects so a successful fetch ends at HTTP 200.
import json
import time
import re
import urllib.request
import urllib.error

OLD_REPO = "brhkim/education_data_portal_mirror"
API = f"https://huggingface.co/api/datasets/{OLD_REPO}"
TREE = f"https://huggingface.co/api/datasets/{OLD_REPO}/tree/main?recursive=true"
README_URL = f"https://huggingface.co/datasets/{OLD_REPO}/resolve/main/README.md"
RESOLVE = f"https://huggingface.co/datasets/{OLD_REPO}/resolve/main"


# --- Fetch: old repo API metadata (for current commit SHA) ---
def get_bytes(url, method="GET", timeout=60):
    # INTENT: single GET/HEAD with 3 retries + backoff. (Helper permitted: network I/O
    #   with retry is not a research transformation; keeps three probes DRY.)
    last_err = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, method=method,
                                         headers={"User-Agent": "daaf-mirror-validate/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, b"", url  # report status, don't retry 4xx/5xx bodies
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed after retries: {url}: {last_err!r}")


status, body, _ = get_bytes(API)
print(f"API status: {status}")
meta = json.loads(body.decode("utf-8"))
old_sha = meta.get("sha")
print(f"OLD repo current commit SHA: {old_sha}")
print(f"OLD repo lastModified: {meta.get('lastModified')}")

# --- Validate 1: README freeze banner ---
print("\n=== V1: OLD README FREEZE BANNER ===")
r_status, r_body, _ = get_bytes(README_URL)
readme = r_body.decode("utf-8", errors="replace")
print(f"README fetch status: {r_status}; length: {len(readme)} chars")
# INTENT: banner must contain freeze/frozen language AND name Portal v0.24.0
has_freeze = bool(re.search(r"freez|frozen", readme, re.IGNORECASE))
has_v024 = ("0.24.0" in readme)
# INTENT: quote the freeze context lines verbatim for the audit trail
freeze_lines = [ln.strip() for ln in readme.splitlines()
                if re.search(r"freez|frozen|0\.24\.0", ln, re.IGNORECASE)]
print(f"has freeze/frozen language: {has_freeze}")
print(f"names Portal v0.24.0: {has_v024}")
print("Freeze-context lines (verbatim):")
for ln in freeze_lines[:15]:
    print(f"  | {ln}")

# --- Fetch: old tree, choose 5 resolve URLs to HEAD-probe ---
print("\n=== V2: OLD RESOLVE URL HEAD PROBES ===")
t_status, t_body, _ = get_bytes(TREE)
tree = json.loads(t_body.decode("utf-8"))
old_files = [e["path"] for e in tree if e.get("type") == "file"
             and e["path"] not in {".gitattributes", "README.md"}]
old_files_sorted = sorted(old_files)
print(f"OLD repo file entries (excl control/README): {len(old_files_sorted)}")
# INTENT: deterministic evenly-spaced sample of 5 across the sorted inventory
n = len(old_files_sorted)
idxs = [int(i * (n - 1) / 4) for i in range(5)] if n >= 5 else list(range(n))
sample = [old_files_sorted[i] for i in idxs]
probe_results = []
for p in sample:
    url = f"{RESOLVE}/{p}"
    st, _, final = get_bytes(url, method="HEAD")
    ok = st == 200
    probe_results.append((p, st, ok))
    print(f"  [{'200' if ok else st}] {p}")

# --- VERDICT ---
print("\n=== VERDICT ===")
checks = {
    "api_status_200": status == 200,
    "old_sha_recorded": bool(old_sha),
    "readme_status_200": r_status == 200,
    "readme_has_freeze_language": has_freeze,
    "readme_names_v0.24.0": has_v024,
    "all_5_head_probes_200": all(ok for _, _, ok in probe_results),
}
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
all_pass = all(checks.values())
print(f"\nOLD repo current commit SHA (for predecessor pinning): {old_sha}")
print(f"SCRIPT 10 OVERALL: {'PASS' if all_pass else 'FAIL'}")
assert all_pass, f"Freeze checks FAILED: {[k for k,v in checks.items() if not v]}"
print("Old mirror is frozen (v0.24.0 banner) and still serving old resolve URLs.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:12:12
# Command: python3 /daaf/scripts/mirror_maintenance/10_old-mirror-freeze-checks.py
# Duration: 4s
# Exit code: 0
#
# --- STDOUT ---
# API status: 200
# OLD repo current commit SHA: 10fea9c7671e8e0ab90a7976674913bc2d16f8b1
# OLD repo lastModified: 2026-08-07T12:44:33.000Z
# 
# === V1: OLD README FREEZE BANNER ===
# README fetch status: 200; length: 8350 chars
# has freeze/frozen language: True
# names Portal v0.24.0: True
# Freeze-context lines (verbatim):
#   | # ⚠️ Frozen Vintage — Education Data Portal Parquet Mirror (v0.24.0, February 2026)
#   | > **This repository is frozen and will receive no further updates.** It is preserved
#   | A complete mirror of the [Urban Institute Education Data Portal](https://educationdata.urban.org) datasets **version 0.24.0**, collected on **February 7, 2026**, and converted from CSV to Apache Parquet format for efficient analytical use. Please note that the maintainers of this Huggingface Dataset have no affiliation with the Urban Institute or the Education Data Portal team.
#   | | Education Data Portal version | **0.24.0** |
#   | | Status | **Frozen** (no further updates; preserved for reproducibility) |
#   | Each file corresponds 1:1 with an entry in the Urban Institute's [download manifest](https://educationdata.urban.org/api/v1/api-downloads/) as of Portal v0.24.0. The Urban CSV download URL for any file is:
#   | where `{basename}` matches the filename in this repository (with `.parquet` replaced by `.csv`). Note that Urban's live CSV downloads track the *current* Portal release and may no longer match this frozen v0.24.0 snapshot byte-for-byte.
#   | > [Dataset name(s)], Education Data Portal (Version 0.24.0), Urban Institute, accessed [Month DD, YYYY], https://educationdata.urban.org/documentation/, made available under the ODC Attribution License.
#   | > [Dataset name(s)], via Education Data Portal v. 0.24.0, Urban Institute, under ODC Attribution License.
#   | > Common Core of Data; Integrated Postsecondary Education Data System, Education Data Portal (Version 0.24.0), Urban Institute, accessed February 9, 2026, https://educationdata.urban.org/documentation/, made available under the ODC Attribution License.
#   | Note: the version number in your citation should always match the vintage of the mirror you actually used — for this repository, that is **0.24.0**.
# 
# === V2: OLD RESOLVE URL HEAD PROBES ===
# OLD repo file entries (excl control/README): 487
#   [200] ccd/codebook_districts_ccd_directory.xls
#   [200] crdc/schools_crdc_chronic_absenteeism_2017.parquet
#   [200] ipeds/codebook_colleges_ipeds_directory.xls
#   [200] ipeds/colleges_ipeds_fall-enrollment-age_2012.parquet
#   [200] scorecard/colleges_scorecard_student_body_treasury.parquet
# 
# === VERDICT ===
#   [PASS] api_status_200
#   [PASS] old_sha_recorded
#   [PASS] readme_status_200
#   [PASS] readme_has_freeze_language
#   [PASS] readme_names_v0.24.0
#   [PASS] all_5_head_probes_200
# 
# OLD repo current commit SHA (for predecessor pinning): 10fea9c7671e8e0ab90a7976674913bc2d16f8b1
# SCRIPT 10 OVERALL: PASS
# Old mirror is frozen (v0.24.0 banner) and still serving old resolve URLs.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
