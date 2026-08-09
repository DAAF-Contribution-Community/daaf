#!/usr/bin/env python3
# =============================================================================
# 23_grad-rates-200-slug.py
# =============================================================================
# INTENT: Close the Lane B small loose end — the LIVE-API endpoint slug for IPEDS
#   graduation-rates-200(%). Three candidate slugs 404'd for the prior agent. Query
#   the authoritative endpoint catalog, find every row whose slug/name mentions "200",
#   then run ONE count probe against the resolved live endpoint and reconcile it with
#   the mirror file ipeds/colleges_ipeds_grad-rates-200pct.parquet (93,088 rows at rest).
#   If no live slug resolves, mark UNVERIFIABLE-TODAY with the quoted probe.
#
# Read-only network GETs. No installs. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import polars as pl
import urllib.request
import urllib.error
import json
import time
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API = "https://educationdata.urban.org/api/v1"
CATALOG = f"{API}/api-endpoints/?limit=500"
UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"
MIRROR_REL = "ipeds/colleges_ipeds_grad-rates-200pct.parquet"


def get_json(url, timeout=90):
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8")), None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            if attempt == 3:
                return None, f"unreachable: {repr(e)[:80]}"
            time.sleep(min(2 ** attempt, 20))
    return None, "no response"


# --- Stage 1: pull the endpoint catalog, page through, collect "200" rows ---
print("=== grad-rates-200 slug resolution ===")
rows, err = get_json(CATALOG)
assert rows is not None, f"STOP: catalog fetch failed: {err}"
recs = rows.get("results", rows if isinstance(rows, list) else [])
# paginate if needed
nxt = rows.get("next") if isinstance(rows, dict) else None
pages = 1
while nxt and pages < 10:
    more, e2 = get_json(nxt)
    if more is None:
        break
    recs.extend(more.get("results", []))
    nxt = more.get("next")
    pages += 1
    time.sleep(0.8)
print(f"catalog rows: {len(recs)} (pages={pages})")

# INTENT: find rows referencing "200" in slug/endpoint/name fields. REASONING: the
#   graduation-rates-200% endpoint should name-match "200"; inspect field shapes robustly.
def rowtext(r):
    return " ".join(str(r.get(k, "")) for k in r.keys()).lower()

hits = [r for r in recs if "200" in rowtext(r) and "grad" in rowtext(r)]
print(f"rows matching grad + 200: {len(hits)}")
for r in hits:
    # print candidate url/slug-bearing fields verbatim
    keys_of_interest = {k: r[k] for k in r.keys()
                        if any(t in k.lower() for t in ("url", "endpoint", "slug", "name", "id"))}
    print(f"  CANDIDATE: {json.dumps(keys_of_interest)[:400]}")

# --- Stage 2: derive candidate live count URLs and probe ---
# Build candidate endpoint paths from any URL/endpoint field on the hits, plus known guesses.
candidates = []
for r in hits:
    for k, v in r.items():
        if isinstance(v, str) and "/api/v1/" in v and "200" in v:
            candidates.append(v)
        if isinstance(v, str) and v.startswith("college-university") and "200" in v:
            candidates.append(f"{API}/{v.strip('/')}/2020/")
# explicit guesses (prior audit suggested grad-rates-200pct)
for slug in ["grad-rates-200pct", "graduation-rates-200pct", "grad-rates-200"]:
    candidates.append(f"{API}/college-university/ipeds/{slug}/2020/")

# de-dup preserving order
seen = set()
candidates = [c for c in candidates if not (c in seen or seen.add(c))]
print(f"\nprobing {len(candidates)} candidate count URLs:")

resolved = None
probe_log = []
for c in candidates:
    # ensure a year segment present for a bounded count
    probe = c if c.rstrip("/").split("/")[-1].isdigit() else c.rstrip("/") + "/2020/"
    j, e = get_json(probe, timeout=90)
    if e is None and isinstance(j, dict) and "count" in j:
        cnt = j.get("count")
        probe_log.append({"url": probe, "result": f"HTTP 200 count={cnt}"})
        print(f"  [OK ] {probe} -> count={cnt}")
        if resolved is None:
            resolved = (probe, cnt)
    else:
        probe_log.append({"url": probe, "result": e or "no count field"})
        print(f"  [{e or 'no-count':>8}] {probe}")
    time.sleep(1.0)

# --- Stage 3: reconcile with mirror (year 2020) ---
mf = TREE_DIR / MIRROR_REL
mir_2020 = None
if mf.exists():
    mir_2020 = int(pl.scan_parquet(mf).filter(pl.col("year") == 2020).select(pl.len()).collect().item())
    mir_total = int(pl.scan_parquet(mf).select(pl.len()).collect().item())
    print(f"\nmirror {MIRROR_REL}: total_rows={mir_total:,} year2020_rows={mir_2020:,}")
else:
    print(f"\n[warn] mirror file missing: {MIRROR_REL}")

# --- Save + verdict ---
out = {"resolved_slug_url": resolved[0] if resolved else None,
       "resolved_year2020_count": resolved[1] if resolved else None,
       "mirror_year2020_rows": mir_2020,
       "verdict": ""}
if resolved:
    match = (mir_2020 is not None and resolved[1] == mir_2020)
    out["verdict"] = f"RESOLVED ({'count MATCHES mirror 2020' if match else 'count vs mirror differs'})"
else:
    out["verdict"] = "UNVERIFIABLE-TODAY (no live slug returned a count)"

pl.from_dicts(probe_log).write_parquet(OUT_DIR / "grad_rates_200_slug_probes.parquet")
print("\n=== grad-rates-200 VERDICT ===")
print(json.dumps(out, indent=2))
print("\nDONE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:35:50
# Command: python3 /daaf/scripts/mirror_maintenance/23_grad-rates-200-slug.py
# Duration: 71s
# Exit code: 0
#
# --- STDOUT ---
# === grad-rates-200 slug resolution ===
# catalog rows: 129 (pages=1)
# rows matching grad + 200: 20
#   CANDIDATE: {"endpoint_id": 3, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/admissions-enrollment/2001/", "endpoint_url": "/api/v1/college-university/ipeds/admissions-enrollment/{year}/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 3, "hide": 0}
#   CANDIDATE: {"endpoint_id": 28, "page_id": 2, "example_endpoint_url": "/api/v1/schools/ccd/enrollment/2007/grade-6/race/sex/", "endpoint_url": "/api/v1/schools/ccd/enrollment/{year}/{grade}/race/sex/", "class_name": "CCD", "datasource_id": 2, "var_list_id": 19, "hide": 0}
#   CANDIDATE: {"endpoint_id": 61, "page_id": 3, "example_endpoint_url": "/api/v1/school-districts/ccd/enrollment/2007/grade-6/race/sex/", "endpoint_url": "/api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/sex/", "class_name": "CCD", "datasource_id": 2, "var_list_id": 37, "hide": 0}
#   CANDIDATE: {"endpoint_id": 80, "page_id": 3, "example_endpoint_url": "/api/v1/school-districts/edfacts/assessments/2014/grade-8/", "endpoint_url": "/api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 49, "hide": 0}
#   CANDIDATE: {"endpoint_id": 81, "page_id": 3, "example_endpoint_url": "/api/v1/school-districts/edfacts/assessments/2013/grade-3/race/", "endpoint_url": "/api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/race/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 49, "hide": 0}
#   CANDIDATE: {"endpoint_id": 9, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/enrollment-full-time-equivalent/2004/2/", "endpoint_url": "/api/v1/college-university/ipeds/enrollment-full-time-equivalent/{year}/{level_of_study}/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 9, "hide": 0}
#   CANDIDATE: {"endpoint_id": 82, "page_id": 3, "example_endpoint_url": "/api/v1/school-districts/edfacts/assessments/2012/grade-5/sex/", "endpoint_url": "/api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/sex/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 49, "hide": 0}
#   CANDIDATE: {"endpoint_id": 83, "page_id": 3, "example_endpoint_url": "/api/v1/school-districts/edfacts/assessments/2016/grade-9/special-populations/", "endpoint_url": "/api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/special-populations/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 49, "hide": 0}
#   CANDIDATE: {"endpoint_id": 13, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/fall-enrollment/2015/undergraduate/race/sex/", "endpoint_url": "/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 10, "hide": 0}
#   CANDIDATE: {"endpoint_id": 15, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/fall-enrollment/2008/undergraduate/age/sex/", "endpoint_url": "/api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/age/sex/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 22, "hide": 0}
#   CANDIDATE: {"endpoint_id": 84, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/fall-enrollment/2017/residence/", "endpoint_url": "/api/v1/college-university/ipeds/fall-enrollment/{year}/residence/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 50, "hide": 0}
#   CANDIDATE: {"endpoint_id": 17, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/student-faculty-ratio/2014/", "endpoint_url": "/api/v1/college-university/ipeds/student-faculty-ratio/{year}/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 23, "hide": 0}
#   CANDIDATE: {"endpoint_id": 98, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/sfa-all-undergraduates/2017/", "endpoint_url": "/api/v1/college-university/ipeds/sfa-all-undergraduates/{year}/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 66, "hide": 0}
#   CANDIDATE: {"endpoint_id": 20, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/grad-rates/2002/", "endpoint_url": "/api/v1/college-university/ipeds/grad-rates/{year}/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 14, "hide": 0}
#   CANDIDATE: {"endpoint_id": 19, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/ipeds/grad-rates-200pct/2007/", "endpoint_url": "/api/v1/college-university/ipeds/grad-rates-200pct/{year}/", "class_name": "IPEDS", "datasource_id": 1, "var_list_id": 13, "hide": 0}
#   CANDIDATE: {"endpoint_id": 133, "page_id": 1, "example_endpoint_url": "/api/v1/college-university/pseo/earnings-and-flows/2016/", "endpoint_url": "/api/v1/college-university/pseo/earnings-and-flows/{year}/", "class_name": "PSEO", "datasource_id": 16, "var_list_id": 91, "hide": 0}
#   CANDIDATE: {"endpoint_id": 76, "page_id": 2, "example_endpoint_url": "/api/v1/schools/edfacts/assessments/2014/grade-8/", "endpoint_url": "/api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 48, "hide": 0}
#   CANDIDATE: {"endpoint_id": 77, "page_id": 2, "example_endpoint_url": "/api/v1/schools/edfacts/assessments/2013/grade-3/race/", "endpoint_url": "/api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/race/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 48, "hide": 0}
#   CANDIDATE: {"endpoint_id": 78, "page_id": 2, "example_endpoint_url": "/api/v1/schools/edfacts/assessments/2012/grade-5/sex/", "endpoint_url": "/api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/sex/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 48, "hide": 0}
#   CANDIDATE: {"endpoint_id": 79, "page_id": 2, "example_endpoint_url": "/api/v1/schools/edfacts/assessments/2009/grade-6/special-populations/", "endpoint_url": "/api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/special-populations/", "class_name": "EDFacts", "datasource_id": 8, "var_list_id": 48, "hide": 0}
# 
# probing 12 candidate count URLs:
#   [unreachable: ValueError("unknown url type: '/api/v1/college-university/ipeds/admissions-enrol] /api/v1/college-university/ipeds/admissions-enrollment/2001/
#   [unreachable: ValueError("unknown url type: '/api/v1/schools/ccd/enrollment/2007/grade-6/race/] /api/v1/schools/ccd/enrollment/2007/grade-6/race/sex/2020/
#   [unreachable: ValueError("unknown url type: '/api/v1/school-districts/ccd/enrollment/2007/grad] /api/v1/school-districts/ccd/enrollment/2007/grade-6/race/sex/2020/
#   [unreachable: ValueError("unknown url type: '/api/v1/college-university/ipeds/enrollment-full-] /api/v1/college-university/ipeds/enrollment-full-time-equivalent/2004/2/
#   [unreachable: ValueError("unknown url type: '/api/v1/college-university/ipeds/fall-enrollment/] /api/v1/college-university/ipeds/fall-enrollment/2008/undergraduate/age/sex/2020/
#   [unreachable: ValueError("unknown url type: '/api/v1/college-university/ipeds/grad-rates/2002/] /api/v1/college-university/ipeds/grad-rates/2002/
#   [unreachable: ValueError("unknown url type: '/api/v1/college-university/ipeds/grad-rates-200pc] /api/v1/college-university/ipeds/grad-rates-200pct/2007/
#   [unreachable: ValueError("unknown url type: '/api/v1/college-university/ipeds/grad-rates-200pc] /api/v1/college-university/ipeds/grad-rates-200pct/{year}/2020/
#   [unreachable: ValueError("unknown url type: '/api/v1/schools/edfacts/assessments/2009/grade-6/] /api/v1/schools/edfacts/assessments/2009/grade-6/special-populations/2020/
#   [OK ] https://educationdata.urban.org/api/v1/college-university/ipeds/grad-rates-200pct/2020/ -> count=5068
#   [HTTP 404] https://educationdata.urban.org/api/v1/college-university/ipeds/graduation-rates-200pct/2020/
#   [HTTP 404] https://educationdata.urban.org/api/v1/college-university/ipeds/grad-rates-200/2020/
# 
# mirror ipeds/colleges_ipeds_grad-rates-200pct.parquet: total_rows=93,088 year2020_rows=5,068
# 
# === grad-rates-200 VERDICT ===
# {
#   "resolved_slug_url": "https://educationdata.urban.org/api/v1/college-university/ipeds/grad-rates-200pct/2020/",
#   "resolved_year2020_count": 5068,
#   "mirror_year2020_rows": 5068,
#   "verdict": "RESOLVED (count MATCHES mirror 2020)"
# }
# 
# DONE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
