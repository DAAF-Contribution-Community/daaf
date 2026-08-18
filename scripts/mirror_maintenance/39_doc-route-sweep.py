# --- Config ---
# INTENT: Systematically extract every documented route template from the three explorer
#         *-endpoints.md doc files, match each against the LIVE catalog route templates
#         (from 37's catalog_raw.json snapshot), and for every documented route that does NOT
#         match a live catalog route, issue ONE direct year-substituted GET to record the
#         observed HTTP status. This upgrades the prior audit's catalog-ABSENCE inferences to
#         OBSERVED 404s — and surfaces any route that works despite catalog absence (a finding).
# REASONING: Doc routes are declared uniformly as `**Endpoint**: `<route>`` markers — a clean,
#            systematic extraction surface. Normalizing placeholders lets `{level}` match the
#            catalog's `{level_of_study}` etc. A dead/renamed route path 404s regardless of the
#            substituted year (out-of-range years return 200/count=0, not 404), so a 404 here is
#            strong evidence the ROUTE PATH itself is gone.
# ASSUMES: 37 already wrote catalog_raw.json. Segment substitutions for unmatched probes use
#          broadly-covered values (year=2016) and plausible categorical values; for genuinely
#          dead routes the value is immaterial (path 404s). stdlib urllib only.
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
import polars as pl

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
SCRATCH = PROJECT_DIR / "scripts/scratch/endpoint_audit"
CATALOG_JSON = SCRATCH / "catalog_raw.json"
OUT_PARQUET = OUT_DIR / "39_doc_route_sweep.parquet"

DOC_DIR = Path("/daaf/.claude/skills/education-data-explorer/references")
DOC_FILES = {
    "colleges-endpoints.md": DOC_DIR / "colleges-endpoints.md",
    "districts-endpoints.md": DOC_DIR / "districts-endpoints.md",
    "schools-endpoints.md": DOC_DIR / "schools-endpoints.md",
}
BASE = "https://educationdata.urban.org"
UA = {"User-Agent": "daaf-endpoint-audit/1.0"}

# Substitution values for unmatched-route probes (year broadly covered; categoricals plausible).
SEG_SUBS = {"year": "2016", "grade": "grade-9", "level": "99",
            "level_of_study": "99", "grade_edfacts": "grade-9"}


def http_get_status(url, timeout=60, retries=3):
    # INTENT: GET url; return (status_int_or_None, count_or_None, error_note).
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, (data.get("count") if isinstance(data, dict) else None), ""
        except urllib.error.HTTPError as e:
            return e.code, None, f"HTTPError {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)
    return None, None, f"CONN_ERROR: {last_err}"


def normalize(route):
    # INTENT: canonical form for matching a doc route to a catalog route.
    # REASONING: strip /api/v1 prefix, lowercase, collapse every {placeholder} to {} (so
    #            {level} == {level_of_study}), strip surrounding slashes.
    r = route.strip()
    r = re.sub(r"^/api/v1", "", r)
    r = re.sub(r"\{[^}]*\}", "{}", r)
    return r.strip("/").lower()


# --- Load: extract doc route templates (systematic `**Endpoint**: `route`` markers) ---
doc_routes = []  # (doc_file, raw_route)
endpoint_re = re.compile(r"\*\*Endpoint\*\*:\s*`([^`]+)`")
for fname, fpath in DOC_FILES.items():
    text = fpath.read_text()
    found = endpoint_re.findall(text)
    for route in found:
        doc_routes.append((fname, route.strip()))
    print(f"Extracted {len(found)} routes from {fname}")
print(f"TOTAL doc routes extracted: {len(doc_routes)}")

# --- Load: live catalog route templates (normalized) from 37 snapshot ---
catalog = json.loads(CATALOG_JSON.read_text())
live_norm_to_template = {}
for row in catalog:
    tmpl = row.get("endpoint_url") or ""
    live_norm_to_template.setdefault(normalize(tmpl), tmpl)
print(f"Live catalog route templates (normalized, unique): {len(live_norm_to_template)}")

# --- Probe: match each doc route; direct-GET the unmatched ---
records = []
n_matched = 0
n_probed = 0
for fname, route in doc_routes:
    norm = normalize(route)
    matched = live_norm_to_template.get(norm)
    if matched is not None:
        n_matched += 1
        records.append({
            "doc_file": fname, "doc_route": route,
            "matched_catalog_route_or_null": matched,
            "probed_url": "", "status": None, "count": None, "error_note": "MATCHED",
        })
        continue
    # Unmatched -> build a concrete probe URL and GET once.
    parts = route.strip("/").split("/")
    out = []
    for seg in parts:
        if seg.startswith("{") and seg.endswith("}"):
            out.append(SEG_SUBS.get(seg.strip("{}"), "x"))
        else:
            out.append(seg)
    probed_url = f"{BASE}/api/v1/" + "/".join(out) + "/?limit=1"
    status, count, note = http_get_status(probed_url)
    n_probed += 1
    flag = "WORKS-DESPITE-ABSENCE" if status == 200 else ("DEAD-404" if status == 404 else "OTHER")
    print(f"  [{fname}] UNMATCHED {route} -> {status} count={count} [{flag}]")
    records.append({
        "doc_file": fname, "doc_route": route,
        "matched_catalog_route_or_null": None,
        "probed_url": probed_url, "status": status, "count": count, "error_note": note,
    })
    time.sleep(1.0)  # polite pacing

# --- Save ---
df = pl.DataFrame(records)
df.write_parquet(OUT_PARQUET)
print(f"\nSaved: {OUT_PARQUET}  shape={df.shape}")

# --- Validate ---
assert df.shape[0] == len(doc_routes), "Row count mismatch vs extracted doc routes"
print(f"VALIDATION: rows={df.shape[0]} == extracted doc routes ({len(doc_routes)}) PASS")
print("\n=== EXTRACTION COUNTS PER FILE ===")
for fname in DOC_FILES:
    c = sum(1 for f, _ in doc_routes if f == fname)
    print(f"  {fname}: {c}")
print(f"\nMatched-to-live: {n_matched}")
print(f"Unmatched (directly probed): {n_probed}")
dead = df.filter(pl.col("status") == 404)
works = df.filter(pl.col("status") == 200)
other = df.filter(pl.col("matched_catalog_route_or_null").is_null()
                  & (pl.col("status") != 404) & (pl.col("status") != 200))
print(f"  DEAD-confirmed-404: {dead.height}")
print(f"  WORKS-despite-catalog-absence (200): {works.height}")
print(f"  OTHER status (non-200/404 or conn error): {other.height}")
print("\n=== DEAD-CONFIRMED-404 (documented routes, observed 404) ===")
for r in dead.iter_rows(named=True):
    print(f"  [{r['doc_file']}] {r['doc_route']} -> 404  ({r['probed_url']})")
print("\n=== WORKS-DESPITE-ABSENCE (documented, not-in-catalog, yet 200) ===")
if works.height == 0:
    print("  (none)")
for r in works.iter_rows(named=True):
    print(f"  [{r['doc_file']}] {r['doc_route']} -> 200 count={r['count']}  ({r['probed_url']})")
print("\n=== OTHER (needs manual look) ===")
if other.height == 0:
    print("  (none)")
for r in other.iter_rows(named=True):
    print(f"  [{r['doc_file']}] {r['doc_route']} -> {r['status']} note={r['error_note']}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:46:39
# Command: python3 /daaf/scripts/mirror_maintenance/39_doc-route-sweep.py
# Duration: 64s
# Exit code: 0
#
# --- STDOUT ---
# Extracted 49 routes from colleges-endpoints.md
# Extracted 12 routes from districts-endpoints.md
# Extracted 22 routes from schools-endpoints.md
# TOTAL doc routes extracted: 83
# Live catalog route templates (normalized, unique): 129
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/student-charges-academic-year/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/student-charges-academic-year/{year}/{level}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/student-charges-academic-year/{year}/living-arrangement/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/student-charges-program-year/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/student-charges-program-year/{year}/program/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/enrollment-full-time-equivalent/{year}/ -> 200 count=20355 [WORKS-DESPITE-ABSENCE]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/enrollment-headcount/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/fall-enrollment/{year}/{level}/ -> 200 count=556500 [WORKS-DESPITE-ABSENCE]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/fall-enrollment/{year}/{level}/race/ -> 200 count=556500 [WORKS-DESPITE-ABSENCE]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/fall-enrollment/{year}/{level}/sex/ -> 200 count=556500 [WORKS-DESPITE-ABSENCE]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/fall-enrollment-age/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/libraries/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/salaries/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/sfa-by-income/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/sfa-by-tuition-status/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/net-price-by-income/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/graduation-rates/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/graduation-rates/{year}/race/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/graduation-rates/{year}/sex/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/completions-cip/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/completions-cip/{year}/race/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/completions-cip/{year}/sex/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/ipeds/completions-cip/{year}/race/sex/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/scorecard/student-characteristics/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/scorecard/completion-by-income/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/fsa/campus-based/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/fsa/ninety-ten/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/nccs/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/eada/{year}/ -> 404 count=None [DEAD-404]
#   [colleges-endpoints.md] UNMATCHED /college-university/pseo/{year}/ -> 404 count=None [DEAD-404]
#   [schools-endpoints.md] UNMATCHED /schools/crdc/finance/{year}/ -> 404 count=None [DEAD-404]
#   [schools-endpoints.md] UNMATCHED /schools/crdc/covid/{year}/ -> 404 count=None [DEAD-404]
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/39_doc_route_sweep.parquet  shape=(83, 7)
# VALIDATION: rows=83 == extracted doc routes (83) PASS
# 
# === EXTRACTION COUNTS PER FILE ===
#   colleges-endpoints.md: 49
#   districts-endpoints.md: 12
#   schools-endpoints.md: 22
# 
# Matched-to-live: 51
# Unmatched (directly probed): 32
#   DEAD-confirmed-404: 28
#   WORKS-despite-catalog-absence (200): 4
#   OTHER status (non-200/404 or conn error): 0
# 
# === DEAD-CONFIRMED-404 (documented routes, observed 404) ===
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-academic-year/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/student-charges-academic-year/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-academic-year/{year}/{level}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/student-charges-academic-year/2016/99/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-academic-year/{year}/living-arrangement/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/student-charges-academic-year/2016/living-arrangement/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-program-year/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/student-charges-program-year/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/student-charges-program-year/{year}/program/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/student-charges-program-year/2016/program/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/enrollment-headcount/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/enrollment-headcount/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment-age/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment-age/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/libraries/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/libraries/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/salaries/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/salaries/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/sfa-by-income/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/sfa-by-income/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/sfa-by-tuition-status/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/sfa-by-tuition-status/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/net-price-by-income/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/net-price-by-income/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/graduation-rates/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/graduation-rates/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/graduation-rates/{year}/race/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/graduation-rates/2016/race/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/graduation-rates/{year}/sex/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/graduation-rates/2016/sex/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/completions-cip/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/race/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/completions-cip/2016/race/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/sex/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/completions-cip/2016/sex/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/completions-cip/{year}/race/sex/ -> 404  (https://educationdata.urban.org/api/v1/college-university/ipeds/completions-cip/2016/race/sex/?limit=1)
#   [colleges-endpoints.md] /college-university/scorecard/student-characteristics/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/scorecard/student-characteristics/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/scorecard/completion-by-income/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/scorecard/completion-by-income/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/fsa/campus-based/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/fsa/campus-based/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/fsa/ninety-ten/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/fsa/ninety-ten/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/nccs/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/nccs/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/eada/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/eada/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/pseo/{year}/ -> 404  (https://educationdata.urban.org/api/v1/college-university/pseo/2016/?limit=1)
#   [schools-endpoints.md] /schools/crdc/finance/{year}/ -> 404  (https://educationdata.urban.org/api/v1/schools/crdc/finance/2016/?limit=1)
#   [schools-endpoints.md] /schools/crdc/covid/{year}/ -> 404  (https://educationdata.urban.org/api/v1/schools/crdc/covid/2016/?limit=1)
# 
# === WORKS-DESPITE-ABSENCE (documented, not-in-catalog, yet 200) ===
#   [colleges-endpoints.md] /college-university/ipeds/enrollment-full-time-equivalent/{year}/ -> 200 count=20355  (https://educationdata.urban.org/api/v1/college-university/ipeds/enrollment-full-time-equivalent/2016/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment/{year}/{level}/ -> 200 count=556500  (https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/2016/99/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment/{year}/{level}/race/ -> 200 count=556500  (https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/2016/99/race/?limit=1)
#   [colleges-endpoints.md] /college-university/ipeds/fall-enrollment/{year}/{level}/sex/ -> 200 count=556500  (https://educationdata.urban.org/api/v1/college-university/ipeds/fall-enrollment/2016/99/sex/?limit=1)
# 
# === OTHER (needs manual look) ===
#   (none)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
