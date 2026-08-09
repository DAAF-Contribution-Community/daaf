# --- Config ---
# INTENT: Verify the "filterable by" / disaggregation-dimension claims in the
#   three explorer doc files against (a) the Portal's authoritative per-variable
#   is_filter metadata (script 41) and (b) live filtered GETs for ~15 load-bearing
#   endpoints (confirm the documented filter returns HTTP 200 with a consistent,
#   non-empty count). Note undocumented-but-working standard filters found
#   incidentally.
# REASONING: The varlist surface marks each variable is_filter=1/None — this is
#   the Portal's own statement of which query params filter an endpoint. Live GETs
#   confirm the metadata is honored in practice and catch any drift.
# ASSUMES: A filter "works" if a GET with that param returns HTTP 200 and a count
#   that is > 0 and <= the unfiltered count. fips is the universal cheap filter.
#   ~1 req/sec pacing, 60s timeout, 3 retries.
import re
import time
import json
import urllib.request
import urllib.error
import polars as pl
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research/2026-08-06_FrameworkDev_MirrorV2Update"
REF_DIR = BASE_DIR / ".claude/skills/education-data-explorer/references"
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
INV_PATH = OUT_DIR / "41_variable_inventory.parquet"
OUT_PATH = OUT_DIR / "44_filter_claims.parquet"
API = "https://educationdata.urban.org/api/v1"

# --- Load: Portal is_filter metadata ---
inv = pl.read_parquet(INV_PATH)

def norm_path(p):
    p = p.strip().lower()
    p = re.sub(r"^/?api/v1", "", p)
    p = re.sub(r"\{[^}]*\}", "{}", p)
    return p.strip("/")

# Portal filter set per normalized endpoint (is_filter == "1").
portal_filters = {}
for row in inv.filter(pl.col("is_filter") == "1").iter_rows(named=True):
    n = norm_path(row["endpoint_url"])
    portal_filters.setdefault(n, set()).add(row["variable"].lower())
print(f"Endpoints with >=1 Portal filter var: {len(portal_filters)}")

# --- Parse documented filter claims ---
# INTENT: capture doc "Filters..." lines and their backticked filter tokens,
#   associated with the nearest preceding **Endpoint**/**Endpoints** route(s).
EP_MARKER = re.compile(r"^\*\*(Working\s+)?Endpoints?\*\*:", re.IGNORECASE)
ROUTE_TOK = re.compile(r"`(/[^`]+)`")
FILTER_LINE = re.compile(r"^\*\*Filter", re.IGNORECASE)
BACKTICK_TOK = re.compile(r"`([a-zA-Z0-9_]+)`")
HEADING = re.compile(r"^#{2,4}\s+\S")

doc_filter_claims = {}  # norm_path -> set(filter tokens)
for level in ("colleges", "districts", "schools"):
    lines = (REF_DIR / f"{level}-endpoints.md").read_text().splitlines()
    sec_starts = [i for i, ln in enumerate(lines) if HEADING.match(ln)] + [len(lines)]
    for s in range(len(sec_starts) - 1):
        block = lines[sec_starts[s]:sec_starts[s + 1]]
        routes, collecting = [], False
        filt = set()
        for bl in block:
            st = bl.strip()
            if EP_MARKER.match(st):
                collecting = True
                routes += ROUTE_TOK.findall(st)
                continue
            if collecting:
                if st.startswith("-"):
                    routes += ROUTE_TOK.findall(st)
                    continue
                if st == "":
                    continue
                collecting = False
            if FILTER_LINE.match(st):
                filt |= set(t.lower() for t in BACKTICK_TOK.findall(st))
        if routes and filt:
            for rt in routes:
                doc_filter_claims.setdefault(norm_path(rt), set()).update(filt)
print(f"Documented endpoints carrying a filter-claim line: {len(doc_filter_claims)}")

# --- Live probe helper ---
def get_json(url, retries=3):
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "daaf-audit/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(1.0)
                return r.getcode(), json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            time.sleep(1.0)
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            time.sleep(1.5)
    return None, {"__error__": last}

# --- Live filter confirmation on load-bearing endpoints ---
# INTENT: (base_url_with_year, filter_param=value) pairs; confirm filtered count
#   is 200, >0, and <= unfiltered count for the same base.
PROBES = [
    ("/college-university/ipeds/directory/2022/", "fips", "6"),
    ("/college-university/ipeds/directory/2022/", "inst_control", "1"),
    ("/college-university/ipeds/fall-enrollment/2021/99/race/sex/", "fips", "11"),
    ("/college-university/scorecard/earnings/2018/", "fips", "6"),
    ("/college-university/fsa/loans/2018/", "fips", "6"),
    ("/schools/ccd/directory/2020/", "fips", "11"),
    ("/schools/ccd/directory/2020/", "charter", "1"),
    ("/schools/ccd/enrollment/2020/grade-9/race/sex/", "fips", "11"),
    ("/schools/ccd/enrollment/2020/grade-9/race/sex/", "race", "1"),
    ("/schools/ccd/enrollment/2020/grade-9/race/sex/", "sex", "2"),
    ("/schools/crdc/enrollment/2017/race/sex/", "fips", "11"),
    ("/schools/crdc/discipline/2017/disability/race/sex/", "disability", "1"),
    ("/schools/crdc/discipline/2017/disability/race/sex/", "lep", "1"),
    ("/school-districts/ccd/directory/2020/", "fips", "11"),
    ("/school-districts/saipe/2020/", "fips", "11"),
    ("/schools/meps/2020/", "fips", "11"),
]

rows = []
base_unfiltered = {}
for base, param, val in PROBES:
    n = norm_path(base)
    # unfiltered baseline (cache per base+fips scope to keep counts comparable)
    if param == "fips":
        code, d = get_json(f"{API}{base}")
        unf = d.get("count") if code == 200 else None
        base_unfiltered[base] = unf
    else:
        # use a fips-scoped baseline so counts are comparable to a fips-scoped filter
        unf = base_unfiltered.get(base)
    code, d = get_json(f"{API}{base}?{param}={val}")
    cnt = d.get("count") if (code == 200 and "__error__" not in d) else None
    is_portal_filter = param in portal_filters.get(n, set())
    is_doc_filter = param in doc_filter_claims.get(n, set())
    works = (code == 200 and cnt is not None and cnt > 0)
    rows.append({
        "endpoint": base,
        "norm_path": n,
        "filter_param": param,
        "value": val,
        "http_code": code,
        "filtered_count": cnt,
        "unfiltered_count": base_unfiltered.get(base),
        "filter_works": works,
        "in_portal_is_filter": is_portal_filter,
        "in_doc_filter_claim": is_doc_filter,
    })
    print(f"{base} ?{param}={val} -> HTTP {code}, count={cnt}, "
          f"works={works}, portal_filter={is_portal_filter}, doc_claim={is_doc_filter}")

live = pl.DataFrame(rows)

# --- Doc-claim vs Portal-metadata filter comparison (matched endpoints) ---
claim_rows = []
for n, dfilt in doc_filter_claims.items():
    if n in portal_filters:
        pf = portal_filters[n]
        doc_not_filter = sorted(dfilt - pf)   # doc claims a filter Portal doesn't mark
        filter_not_doc = sorted(pf - dfilt)   # Portal filter our doc omits
        claim_rows.append({
            "norm_path": n,
            "n_doc_claimed": len(dfilt),
            "n_portal_filters": len(pf),
            "doc_claimed_not_portal_filter": ", ".join(doc_not_filter),
            "portal_filter_not_doc_claimed": ", ".join(filter_not_doc),
        })
claims = pl.DataFrame(claim_rows) if claim_rows else pl.DataFrame(
    schema={"norm_path": pl.Utf8})

# --- Validate ---
n_work = live.filter(pl.col("filter_works")).height
print(f"\nLive filter probes: {live.height}, working (200 & count>0): {n_work}")
failed = live.filter(~pl.col("filter_works"))
print(f"Non-working probes: {failed.height}")
for r in failed.iter_rows(named=True):
    print(f"  FAILED: {r['endpoint']} ?{r['filter_param']}={r['value']} HTTP={r['http_code']} count={r['filtered_count']}")

# Count-consistency check: fips-filtered count should not exceed unfiltered.
inconsistent = live.filter(
    pl.col("filtered_count").is_not_null()
    & pl.col("unfiltered_count").is_not_null()
    & (pl.col("filtered_count") > pl.col("unfiltered_count"))
)
print(f"Count-inconsistent probes (filtered > unfiltered): {inconsistent.height}")

assert live.height >= 15, "Fewer filter probes than planned"

# --- Save (combine live probes; claims saved as companion parquet) ---
live.write_parquet(OUT_PATH)
CLAIMS_PATH = OUT_DIR / "44_filter_doc_vs_meta.parquet"
claims.write_parquet(CLAIMS_PATH)
print(f"\nSaved live probes: {OUT_PATH} ({live.shape})")
print(f"Saved doc-vs-meta claims: {CLAIMS_PATH} ({claims.shape})")

# --- Findings: doc filter-claim discrepancies ---
print("\n=== DOC FILTER-CLAIM vs PORTAL is_filter ===")
if claims.height:
    for r in claims.iter_rows(named=True):
        if r["doc_claimed_not_portal_filter"]:
            print(f"[{r['norm_path']}] DOC-CLAIMS-NOT-PORTAL-FILTER: {r['doc_claimed_not_portal_filter']}")
print("\n=== UNDOCUMENTED-BUT-WORKING standard filters (from live probes) ===")
for r in live.filter(pl.col("filter_works") & ~pl.col("in_doc_filter_claim")).iter_rows(named=True):
    print(f"  {r['endpoint']} ?{r['filter_param']}= works but not in doc filter-claim line")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:25:24
# Command: python3 /daaf/scripts/mirror_maintenance/44_filter-claims.py
# Duration: 167s
# Exit code: 0
#
# --- STDOUT ---
# Endpoints with >=1 Portal filter var: 129
# Documented endpoints carrying a filter-claim line: 7
# /college-university/ipeds/directory/2022/ ?fips=6 -> HTTP 200, count=692, works=True, portal_filter=False, doc_claim=False
# /college-university/ipeds/directory/2022/ ?inst_control=1 -> HTTP 200, count=2019, works=True, portal_filter=False, doc_claim=False
# /college-university/ipeds/fall-enrollment/2021/99/race/sex/ ?fips=11 -> HTTP 200, count=1860, works=True, portal_filter=False, doc_claim=False
# /college-university/scorecard/earnings/2018/ ?fips=6 -> HTTP 200, count=1566, works=True, portal_filter=False, doc_claim=False
# /college-university/fsa/loans/2018/ ?fips=6 -> HTTP 200, count=7084, works=True, portal_filter=False, doc_claim=False
# /schools/ccd/directory/2020/ ?fips=11 -> HTTP 200, count=240, works=True, portal_filter=False, doc_claim=False
# /schools/ccd/directory/2020/ ?charter=1 -> HTTP 200, count=8018, works=True, portal_filter=False, doc_claim=False
# /schools/ccd/enrollment/2020/grade-9/race/sex/ ?fips=11 -> HTTP 200, count=1161, works=True, portal_filter=False, doc_claim=False
# /schools/ccd/enrollment/2020/grade-9/race/sex/ ?race=1 -> HTTP 200, count=82563, works=True, portal_filter=False, doc_claim=False
# /schools/ccd/enrollment/2020/grade-9/race/sex/ ?sex=2 -> HTTP 200, count=220168, works=True, portal_filter=False, doc_claim=False
# /schools/crdc/enrollment/2017/race/sex/ ?fips=11 -> HTTP 200, count=5472, works=True, portal_filter=False, doc_claim=False
# /schools/crdc/discipline/2017/disability/race/sex/ ?disability=1 -> HTTP 200, count=2343168, works=True, portal_filter=False, doc_claim=False
# /schools/crdc/discipline/2017/disability/race/sex/ ?lep=1 -> HTTP 200, count=0, works=False, portal_filter=False, doc_claim=False
# /school-districts/ccd/directory/2020/ ?fips=11 -> HTTP 200, count=69, works=True, portal_filter=False, doc_claim=False
# /school-districts/saipe/2020/ ?fips=11 -> HTTP 200, count=1, works=True, portal_filter=False, doc_claim=False
# /schools/meps/2020/ ?fips=11 -> HTTP 200, count=226, works=True, portal_filter=False, doc_claim=False
# 
# Live filter probes: 16, working (200 & count>0): 15
# Non-working probes: 1
#   FAILED: /schools/crdc/discipline/2017/disability/race/sex/ ?lep=1 HTTP=200 count=0
# Count-inconsistent probes (filtered > unfiltered): 0
# 
# Saved live probes: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/44_filter_claims.parquet ((16, 10))
# Saved doc-vs-meta claims: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/44_filter_doc_vs_meta.parquet ((7, 5))
# 
# === DOC FILTER-CLAIM vs PORTAL is_filter ===
# [school-districts/ccd/directory/{}] DOC-CLAIMS-NOT-PORTAL-FILTER: agency_type
# 
# === UNDOCUMENTED-BUT-WORKING standard filters (from live probes) ===
#   /college-university/ipeds/directory/2022/ ?fips= works but not in doc filter-claim line
#   /college-university/ipeds/directory/2022/ ?inst_control= works but not in doc filter-claim line
#   /college-university/ipeds/fall-enrollment/2021/99/race/sex/ ?fips= works but not in doc filter-claim line
#   /college-university/scorecard/earnings/2018/ ?fips= works but not in doc filter-claim line
#   /college-university/fsa/loans/2018/ ?fips= works but not in doc filter-claim line
#   /schools/ccd/directory/2020/ ?fips= works but not in doc filter-claim line
#   /schools/ccd/directory/2020/ ?charter= works but not in doc filter-claim line
#   /schools/ccd/enrollment/2020/grade-9/race/sex/ ?fips= works but not in doc filter-claim line
#   /schools/ccd/enrollment/2020/grade-9/race/sex/ ?race= works but not in doc filter-claim line
#   /schools/ccd/enrollment/2020/grade-9/race/sex/ ?sex= works but not in doc filter-claim line
#   /schools/crdc/enrollment/2017/race/sex/ ?fips= works but not in doc filter-claim line
#   /schools/crdc/discipline/2017/disability/race/sex/ ?disability= works but not in doc filter-claim line
#   /school-districts/ccd/directory/2020/ ?fips= works but not in doc filter-claim line
#   /school-districts/saipe/2020/ ?fips= works but not in doc filter-claim line
#   /schools/meps/2020/ ?fips= works but not in doc filter-claim line
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
