# --- Config ---
# INTENT: Pull the authoritative Urban Portal endpoint catalog (api-endpoints/?limit=500,
#         129 rows expected) and issue ONE live GET per catalog route to record ground-truth
#         HTTP status, row count, and the response's top-level field names. This upgrades the
#         prior catalog-level audit (2026-08-07_wave3) to direct probe evidence for every route.
# REASONING: The catalog is the planning surface; a live GET per route is the ground truth a
#            later regeneration pass will consume. example_endpoint_url gives a Portal-authored
#            valid concrete URL (documented-valid year + any extra segment values), which we use
#            to source segment substitutions; the probed year itself is the MID-RANGE year of
#            years_available per task spec, and the substitution is recorded.
# ASSUMES: API recovered from 2026-08-06 outage. 60s timeouts, 3 retries w/ exponential backoff,
#          ~1 req/sec sequential polite pacing. DRF LimitOffsetPagination -> `count` is the FULL
#          filtered total regardless of limit; limit=1 minimizes payload while exposing count and
#          first-row field names. stdlib urllib only (no installs).
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
OUT_PARQUET = OUT_DIR / "37_live_probe_inventory.parquet"
CATALOG_JSON = SCRATCH / "catalog_raw.json"

BASE = "https://educationdata.urban.org"
CATALOG_URL = f"{BASE}/api/v1/api-endpoints/?limit=500"
UA = {"User-Agent": "daaf-endpoint-audit/1.0"}


# --- Helpers (inline; sequential-script style permits these small utilities) ---
def http_get_json(url, timeout=60, retries=3):
    # INTENT: GET a URL, return (status_int_or_None, parsed_json_or_None, error_note).
    # REASONING: uniform retry/backoff wrapper so every probe is polite and resilient to the
    #            recently-recovered API. HTTPError carries a real status (e.g. 404) -> NOT retried
    #            as a transport failure; URLError/timeout ARE retried with exponential backoff.
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return resp.status, json.loads(body.decode("utf-8")), ""
        except urllib.error.HTTPError as e:
            # A documented status (404/500/etc.) — a finding, not a transport retry.
            try:
                body = e.read().decode("utf-8")
                parsed = json.loads(body) if body.strip().startswith("{") else None
            except Exception:
                parsed = None
            return e.code, parsed, f"HTTPError {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = f"{type(e).__name__}: {e}"
            wait = 2 ** attempt
            print(f"    transport fail attempt {attempt}: {last_err}; backoff {wait}s")
            time.sleep(wait)
    return None, None, f"CONN_ERROR after {retries} retries: {last_err}"


def parse_years(s):
    # INTENT: expand a years_available string into a sorted list of int years.
    # ASSUMES: HTML dashes (&ndash;) and unicode en/em dashes denote ranges; comma separates tokens.
    if s is None:
        return []
    t = (s.replace("&ndash;", "-").replace("&#8211;", "-")
          .replace("–", "-").replace("—", "-")
          .replace("‒", "-").replace("‐", "-"))
    years = set()
    for tok in t.split(","):
        nums = re.findall(r"\d{4}", tok)
        if len(nums) >= 2:
            a, b = int(nums[0]), int(nums[1])
            if a <= b:
                years.update(range(a, b + 1))
        elif len(nums) == 1:
            years.add(int(nums[0]))
    return sorted(years)


def build_probe_url(template, example, mid_year):
    # INTENT: construct a concrete probe path from the {placeholder} template, substituting the
    #         MID-RANGE year for {year} and Portal example-segment values for any other {seg}.
    # REASONING: example_endpoint_url is a Portal-authored valid concretization; borrowing its
    #            segment values guarantees documented-valid substitutions for {grade},
    #            {level_of_study}, {grade_edfacts}, etc. Records exactly what was substituted.
    tparts = template.strip("/").split("/")
    eparts = example.strip("/").split("/") if example else []
    subs = []
    out = []
    for i, seg in enumerate(tparts):
        if seg.startswith("{") and seg.endswith("}"):
            name = seg.strip("{}")
            if name == "year" and mid_year is not None:
                out.append(str(mid_year))
                subs.append(f"{name}={mid_year}(mid-range)")
            elif i < len(eparts):
                out.append(eparts[i])
                subs.append(f"{name}={eparts[i]}(from-example)")
            else:
                out.append(seg)
                subs.append(f"{name}=UNRESOLVED")
        else:
            out.append(seg)
    path = "/" + "/".join(out) + "/"
    return path, "; ".join(subs)


# --- Load: pull the full endpoint catalog (paginate defensively via `next`) ---
all_rows = []
url = CATALOG_URL
page = 0
while url is not None:
    page += 1
    status, data, note = http_get_json(url, timeout=60)
    assert status == 200 and data is not None, f"Catalog pull failed (status={status}, note={note})"
    all_rows.extend(data.get("results", []))
    url = data.get("next")
    if url:
        time.sleep(1.0)
print(f"Catalog: pulled {len(all_rows)} endpoint rows across {page} page(s)")
CATALOG_JSON.write_text(json.dumps(all_rows))  # provenance snapshot for scripts 38/39/40 reuse
print(f"Saved raw catalog snapshot: {CATALOG_JSON}")

# --- Probe: one live GET per catalog route ---
records = []
n = len(all_rows)
for idx, row in enumerate(all_rows, start=1):
    eid = row.get("endpoint_id")
    section = row.get("section")
    class_name = row.get("class_name")
    template = row.get("endpoint_url") or ""
    example = row.get("example_endpoint_url") or ""
    years_raw = row.get("years_available")
    years = parse_years(years_raw)
    mid_year = years[len(years) // 2] if years else None

    path, subs = build_probe_url(template, example, mid_year)
    probed_url = f"{BASE}{path}?limit=1"

    status, data, note = http_get_json(probed_url, timeout=60)
    count = data.get("count") if isinstance(data, dict) else None
    fields = []
    if isinstance(data, dict):
        results = data.get("results") or []
        if results and isinstance(results[0], dict):
            fields = sorted(results[0].keys())

    flag = "" if status == 200 else "NON-200"
    print(f"[{idx}/{n}] id={eid} {template} -> {status} count={count} {flag}")

    records.append({
        "endpoint_id": eid,
        "section": section,
        "class_name": class_name,
        "route_template": template,
        "example_url": example,
        "years_available": years_raw,
        "mid_year": mid_year,
        "probed_url": probed_url,
        "seg_substitutions": subs,
        "status": status,
        "count": count,
        "fields": fields,
        "error_note": note,
    })
    time.sleep(1.0)  # polite ~1 req/sec pacing

# --- Save ---
df = pl.DataFrame(records)
df.write_parquet(OUT_PARQUET)
print(f"\nSaved: {OUT_PARQUET}  shape={df.shape}")

# --- Validate ---
assert df.shape[0] == len(all_rows), "Row count mismatch vs catalog"
assert df.shape[0] >= 120, f"Expected ~129 endpoints, got {df.shape[0]}"
n_200 = df.filter(pl.col("status") == 200).height
n_non200 = df.filter((pl.col("status") != 200) | pl.col("status").is_null()).height
print(f"VALIDATION: rows={df.shape[0]} (expected ~129) PASS")
print(f"  status==200: {n_200}")
print(f"  NON-200 or error: {n_non200}")
print("\n=== NON-200 CATALOG ROUTES (findings) ===")
non200 = df.filter((pl.col("status") != 200) | pl.col("status").is_null())
if non200.height == 0:
    print("  (none — all 129 catalog routes returned 200)")
else:
    for r in non200.iter_rows(named=True):
        print(f"  id={r['endpoint_id']} {r['route_template']} status={r['status']} "
              f"note={r['error_note']} probed={r['probed_url']}")
print("\n=== ZERO-COUNT 200 ROUTES (mid-year returned 0 rows) ===")
zero = df.filter((pl.col("status") == 200) & (pl.col("count") == 0))
for r in zero.iter_rows(named=True):
    print(f"  id={r['endpoint_id']} {r['route_template']} mid_year={r['mid_year']} count=0")
if zero.height == 0:
    print("  (none)")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 15:11:58
# Command: python3 /daaf/scripts/mirror_maintenance/37_live-probe-inventory.py
# Duration: 1713s
# Exit code: 0
#
# --- STDOUT ---
# Catalog: pulled 129 endpoint rows across 1 page(s)
# Saved raw catalog snapshot: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/scripts/scratch/endpoint_audit/catalog_raw.json
# [1/129] id=1 /api/v1/college-university/ipeds/directory/{year}/ -> 200 count=6916 
# [2/129] id=24 /api/v1/schools/ccd/directory/{year}/ -> 200 count=102454 
# [3/129] id=54 /api/v1/school-districts/ccd/directory/{year}/ -> 200 count=18213 
# [4/129] id=2 /api/v1/college-university/ipeds/institutional-characteristics/{year}/ -> 200 count=6916 
# [5/129] id=25 /api/v1/schools/ccd/enrollment/{year}/{grade}/ -> 200 count=30902 
# [6/129] id=56 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/ -> 200 count=14643 
# [7/129] id=3 /api/v1/college-university/ipeds/admissions-enrollment/{year}/ -> 200 count=6780 
# [8/129] id=26 /api/v1/schools/ccd/enrollment/{year}/{grade}/race/ -> 200 count=326838 
# [9/129] id=58 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/ -> 200 count=89334 
# [10/129] id=4 /api/v1/college-university/ipeds/admissions-requirements/{year}/ -> 200 count=7052 
# [11/129] id=27 /api/v1/schools/ccd/enrollment/{year}/{grade}/sex/ -> 200 count=158943 
# [12/129] id=59 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/sex/ -> 200 count=44859 
# [13/129] id=6 /api/v1/college-university/ipeds/academic-year-tuition/{year}/ -> 200 count=18504 
# [14/129] id=28 /api/v1/schools/ccd/enrollment/{year}/{grade}/race/sex/ -> 200 count=696852 
# [15/129] id=61 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/sex/ -> 200 count=269676 
# [16/129] id=5 /api/v1/college-university/ipeds/academic-year-tuition-prof-program/{year}/ -> 200 count=1713 
#     transport fail attempt 1: TimeoutError: The read operation timed out; backoff 2s
#     transport fail attempt 2: TimeoutError: The read operation timed out; backoff 4s
# [17/129] id=29 /api/v1/school-districts/ccd/finance/{year}/ -> 200 count=16453 
# [18/129] id=73 /api/v1/schools/crdc/directory/{year}/ -> 200 count=97632 
# [19/129] id=10 /api/v1/college-university/ipeds/academic-year-room-board-other/{year}/ -> 200 count=12881 
# [20/129] id=30 /api/v1/school-districts/saipe/{year}/ -> 200 count=13545 
# [21/129] id=60 /api/v1/schools/crdc/enrollment/{year}/race/sex/ -> 200 count=2343168 
# [22/129] id=8 /api/v1/college-university/ipeds/program-year-tuition-cip/{year}/ -> 200 count=7886 
# [23/129] id=65 /api/v1/schools/crdc/enrollment/{year}/disability/sex/ -> 200 count=878688 
# [24/129] id=80 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/ -> 200 count=14213 
# [25/129] id=7 /api/v1/college-university/ipeds/program-year-room-board-other/{year}/ -> 200 count=5316 
# [26/129] id=67 /api/v1/schools/crdc/enrollment/{year}/lep/sex/ -> 200 count=585792 
# [27/129] id=81 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/race/ -> 200 count=75352 
# [28/129] id=9 /api/v1/college-university/ipeds/enrollment-full-time-equivalent/{year}/{level_of_study}/ -> 200 count=7479 
# [29/129] id=82 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/sex/ -> 200 count=43804 
# [30/129] id=83 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/special-populations/ -> 200 count=53496 
# [31/129] id=101 /api/v1/school-districts/edfacts/grad-rates/{year}/ -> 200 count=123500 
# [32/129] id=119 /api/v1/schools/crdc/discipline-instances/{year}/ -> 200 count=585450 
# [33/129] id=13 /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ -> 200 count=1795416 
# [34/129] id=69 /api/v1/schools/crdc/discipline/{year}/disability/sex/ -> 200 count=1171584 
# [35/129] id=71 /api/v1/schools/crdc/discipline/{year}/disability/race/sex/ -> 200 count=7322400 
# [36/129] id=15 /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/age/sex/ -> 200 count=275121 
# [37/129] id=72 /api/v1/schools/crdc/discipline/{year}/disability/lep/sex/ -> 200 count=2336949 
# [38/129] id=41 /api/v1/schools/crdc/harassment-or-bullying/{year}/allegations/ -> 200 count=97632 
# [39/129] id=84 /api/v1/college-university/ipeds/fall-enrollment/{year}/residence/ -> 200 count=76926 
# [40/129] id=18 /api/v1/college-university/ipeds/enrollment-headcount/{year}/{level_of_study}/ -> 200 count=187056 
# [41/129] id=42 /api/v1/schools/crdc/harassment-or-bullying/{year}/race/sex/ -> 200 count=2343168 
# [42/129] id=16 /api/v1/college-university/ipeds/fall-retention/{year}/ -> 200 count=14100 
# [43/129] id=43 /api/v1/schools/crdc/harassment-or-bullying/{year}/disability/sex/ -> 200 count=878688 
# [44/129] id=44 /api/v1/schools/crdc/harassment-or-bullying/{year}/lep/sex/ -> 200 count=585792 
# [45/129] id=91 /api/v1/college-university/ipeds/finance/{year}/ -> 200 count=9769 
# [46/129] id=17 /api/v1/college-university/ipeds/student-faculty-ratio/{year}/ -> 200 count=6371 
# [47/129] id=37 /api/v1/schools/crdc/chronic-absenteeism/{year}/race/sex/ -> 200 count=2309375 
# [48/129] id=32 /api/v1/college-university/ipeds/sfa-grants-and-net-price/{year}/ -> 200 count=42215 
# [49/129] id=38 /api/v1/schools/crdc/chronic-absenteeism/{year}/disability/sex/ -> 200 count=923750 
# [50/129] id=39 /api/v1/schools/crdc/chronic-absenteeism/{year}/lep/sex/ -> 200 count=646625 
# [51/129] id=96 /api/v1/college-university/ipeds/sfa-by-living-arrangement/{year}/ -> 200 count=51988 
# [52/129] id=34 /api/v1/schools/crdc/restraint-and-seclusion/{year}/instances/ -> 200 count=390528 
# [53/129] id=97 /api/v1/college-university/ipeds/sfa-by-tuition-type/{year}/ -> 200 count=14985 
# [54/129] id=35 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/sex/ -> 200 count=1171584 
# [55/129] id=98 /api/v1/college-university/ipeds/sfa-all-undergraduates/{year}/ -> 200 count=20877 
# [56/129] id=36 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/race/sex/ -> 200 count=7322400 
# [57/129] id=99 /api/v1/college-university/ipeds/sfa-ftft/{year}/ -> 200 count=75284 
# [58/129] id=20 /api/v1/college-university/ipeds/grad-rates/{year}/ -> 200 count=233463 
# [59/129] id=40 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/lep/sex/ -> 200 count=2050272 
# [60/129] id=19 /api/v1/college-university/ipeds/grad-rates-200pct/{year}/ -> 200 count=5652 
# [61/129] id=46 /api/v1/schools/crdc/ap-ib-enrollment/{year}/race/sex/ -> 200 count=2343168 
# [62/129] id=21 /api/v1/college-university/ipeds/grad-rates-pell/{year}/ -> 200 count=40300 
# [63/129] id=47 /api/v1/schools/crdc/ap-ib-enrollment/{year}/disability/sex/ -> 200 count=585792 
# [64/129] id=22 /api/v1/college-university/ipeds/outcome-measures/{year}/ -> 200 count=89756 
# [65/129] id=48 /api/v1/schools/crdc/ap-ib-enrollment/{year}/lep/sex/ -> 200 count=585792 
# [66/129] id=31 /api/v1/college-university/ipeds/completers/{year}/ -> 200 count=202620 
# [67/129] id=53 /api/v1/schools/crdc/ap-exams/{year}/race/sex/ -> 200 count=2312640 
# [68/129] id=23 /api/v1/college-university/ipeds/completions-cip-2/{year}/ -> 200 count=3348297 
# [69/129] id=55 /api/v1/schools/crdc/ap-exams/{year}/disability/sex/ -> 200 count=578160 
# [70/129] id=33 /api/v1/college-university/ipeds/completions-cip-6/{year}/ -> 200 count=5268336 
# [71/129] id=57 /api/v1/schools/crdc/ap-exams/{year}/lep/sex/ -> 200 count=578160 
# [72/129] id=45 /api/v1/college-university/ipeds/academic-libraries/{year}/ -> 200 count=3834 
# [73/129] id=49 /api/v1/schools/crdc/sat-act-participation/{year}/race/sex/ -> 200 count=2343168 
# [74/129] id=50 /api/v1/schools/crdc/sat-act-participation/{year}/disability/sex/ -> 200 count=585792 
# [75/129] id=102 /api/v1/college-university/ipeds/salaries-instructional-staff/{year}/ -> 200 count=114273 
# [76/129] id=51 /api/v1/schools/crdc/sat-act-participation/{year}/lep/sex/ -> 200 count=585792 
# [77/129] id=103 /api/v1/college-university/ipeds/salaries-noninstructional-staff/{year}/ -> 200 count=58688 
# [78/129] id=52 /api/v1/schools/crdc/teachers-staff/{year}/ -> 200 count=97632 
# [79/129] id=63 /api/v1/college-university/scorecard/institutional-characteristics/{year}/ -> 200 count=7055 
# [80/129] id=68 /api/v1/college-university/scorecard/student-characteristics/{year}/aid-applicants/ -> 200 count=6762 
# [81/129] id=107 /api/v1/schools/crdc/math-and-science/{year}/race/sex/ -> 200 count=2343168 
# [82/129] id=70 /api/v1/college-university/scorecard/student-characteristics/{year}/home-neighborhood/ -> 200 count=6762 
# [83/129] id=108 /api/v1/schools/crdc/math-and-science/{year}/disability/sex/ -> 200 count=585792 
# [84/129] id=62 /api/v1/college-university/scorecard/earnings/{year}/ -> 200 count=19661 
# [85/129] id=109 /api/v1/schools/crdc/math-and-science/{year}/lep/sex/ -> 200 count=585792 
# [86/129] id=64 /api/v1/college-university/scorecard/default/{year}/ -> 200 count=6574 
# [87/129] id=120 /api/v1/schools/crdc/algebra1/{year}/race/sex -> 200 count=8005824 
# [88/129] id=66 /api/v1/college-university/scorecard/repayment/{year}/ -> 200 count=20191 
# [89/129] id=121 /api/v1/schools/crdc/algebra1/{year}/disability/sex/ -> 200 count=2343168 
# [90/129] id=87 /api/v1/college-university/nhgis/census-1990/{year}/ -> 200 count=7024 
# [91/129] id=122 /api/v1/schools/crdc/algebra1/{year}/lep/sex/ -> 200 count=2343168 
# [92/129] id=86 /api/v1/college-university/nhgis/census-2000/{year}/ -> 200 count=7024 
# [93/129] id=110 /api/v1/schools/crdc/offenses/{year}/ -> 200 count=97575 
# [94/129] id=85 /api/v1/college-university/nhgis/census-2010/{year}/ -> 200 count=7024 
# [95/129] id=111 /api/v1/schools/crdc/dual-enrollment/{year}/race/sex -> 200 count=2341800 
# [96/129] id=112 /api/v1/schools/crdc/dual-enrollment/{year}/disability/sex -> 200 count=585450 
# [97/129] id=134 /api/v1/college-university/nhgis/census-2020/{year}/ -> 200 count=7024 
# [98/129] id=92 /api/v1/college-university/fsa/financial-responsibility/{year}/ -> 200 count=3401 
# [99/129] id=113 /api/v1/schools/crdc/dual-enrollment/{year}/lep/sex -> 200 count=585450 
# [100/129] id=93 /api/v1/college-university/fsa/grants/{year}/ -> 200 count=27665 
# [101/129] id=114 /api/v1/schools/crdc/credit-recovery/{year}/ -> 200 count=97632 
# [102/129] id=94 /api/v1/college-university/fsa/loans/{year}/ -> 200 count=73724 
# [103/129] id=115 /api/v1/schools/crdc/suspensions-days/{year}/race/sex -> 200 count=2341800 
# [104/129] id=95 /api/v1/college-university/fsa/campus-based-volume/{year}/ -> 200 count=12318 
# [105/129] id=116 /api/v1/schools/crdc/suspensions-days/{year}/disability/sex -> 200 count=878175 
# [106/129] id=104 /api/v1/college-university/fsa/90-10-revenue-percentages/{year}/ -> 200 count=1671 
# [107/129] id=117 /api/v1/schools/crdc/suspensions-days/{year}/lep/sex -> 200 count=585450 
# [108/129] id=105 /api/v1/college-university/nacubo/endowments/{year}/ -> 200 count=776 
# [109/129] id=118 /api/v1/schools/crdc/offerings/{year}/ -> 200 count=97632 
# [110/129] id=106 /api/v1/college-university/nccs/990-forms/{year}/ -> 200 count=1348 
# [111/129] id=123 /api/v1/schools/crdc/school-finance/{year}/ -> 200 count=96360 
# [112/129] id=124 /api/v1/schools/crdc/retention/{year}/{grade}/race/sex -> 200 count=2312640 
# [113/129] id=128 /api/v1/college-university/eada/institutional-characteristics/{year}/ -> 200 count=2090 
# [114/129] id=125 /api/v1/schools/crdc/retention/{year}/{grade}/disability/sex -> 200 count=867240 
# [115/129] id=130 /api/v1/college-university/campus-crime/hate-crimes/{year}/ -> 200 count=911365 
#     transport fail attempt 1: TimeoutError: The read operation timed out; backoff 2s
#     transport fail attempt 2: TimeoutError: The read operation timed out; backoff 4s
# [116/129] id=126 /api/v1/schools/crdc/retention/{year}/{grade}/lep/sex -> 200 count=578160 
# [117/129] id=133 /api/v1/college-university/pseo/earnings-and-flows/{year}/ -> 200 count=2849220 
# [118/129] id=131 /api/v1/schools/crdc/covid-indicators/{year}/ -> 200 count=98010 
# [119/129] id=132 /api/v1/schools/crdc/internet-access/{year}/ -> 200 count=98010 
# [120/129] id=76 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/ -> 200 count=29206 
# [121/129] id=77 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/race/ -> 200 count=259653 
# [122/129] id=78 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/sex/ -> 200 count=149384 
# [123/129] id=79 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/special-populations/ -> 200 count=149278 
# [124/129] id=100 /api/v1/schools/edfacts/grad-rates/{year}/ -> 200 count=230900 
# [125/129] id=127 /api/v1/schools/meps/{year}/ -> 200 count=96153 
# [126/129] id=90 /api/v1/schools/nhgis/census-1990/{year}/ -> 200 count=102327 
# [127/129] id=89 /api/v1/schools/nhgis/census-2000/{year}/ -> 200 count=102327 
# [128/129] id=88 /api/v1/schools/nhgis/census-2010/{year}/ -> 200 count=102327 
# [129/129] id=135 /api/v1/schools/nhgis/census-2020/{year}/ -> 200 count=102327 
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/37_live_probe_inventory.parquet  shape=(129, 13)
# VALIDATION: rows=129 (expected ~129) PASS
#   status==200: 129
#   NON-200 or error: 0
# 
# === NON-200 CATALOG ROUTES (findings) ===
#   (none — all 129 catalog routes returned 200)
# 
# === ZERO-COUNT 200 ROUTES (mid-year returned 0 rows) ===
#   (none)
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
