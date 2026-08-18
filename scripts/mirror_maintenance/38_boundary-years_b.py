# REVISION _b: _a still hung. Two independent _a runs (prior-session orphan + this session's) both
#   stalled at the SAME endpoint (id=51 schools/crdc/sat-act-participation/{year}/lep/sex, last
#   boundary) with the process in interruptible I/O sleep (STAT=Sl, ~12s CPU over 12min wall) —
#   proof the 20s urllib SOCKET timeout does NOT catch a slow-TRICKLE response: bytes arrive within
#   each read window, so the per-read timeout keeps resetting and never fires. FIX: enforce a HARD
#   WALL-CLOCK deadline per request via signal.SIGALRM (a real-time alarm independent of socket
#   activity). On deadline the blocking urlopen/read is interrupted, the probe is recorded as
#   CONN_ERROR and SKIPPED, and the sweep proceeds. SIGALRM is valid here: this is a single-threaded,
#   sequential script running in the main thread (signal-handler + main-thread requirement met).
#   REASONING: socket timeout guards inter-byte gaps; a wall-clock alarm guards total request time —
#   the trickle pathology needs the latter. ASSUMES: no other SIGALRM user in this script (true).
#   All other logic (probe set, checkpointing every 10, anomaly classification) is identical to _a.
# REVISION _a (superseded): v1 hung on the recovering Portal API; _a tightened the socket timeout to
#   20s + 2 retries + incremental checkpoints. Insufficient against slow-trickle reads (see above).
# --- Config ---
# INTENT: For every LIVE endpoint (37 probe status==200), probe the FIRST and LAST year of its
#         years_available (count retrieval only) to verify the catalog's advertised coverage
#         boundaries. A boundary year returning 404 or 0 rows is a catalog-OVERSTATEMENT finding
#         (0 rows may be legitimate for some subgroup endpoints — record, do NOT fail).
# REASONING: The prior audit only boundary-checked IPEDS finance; this generalizes verified year
#            ranges to all live routes, producing the per-route verified coverage the regeneration
#            pass needs. Non-year segment values are sourced from 37's example_url (Portal-valid).
# ASSUMES: 37 wrote 37_live_probe_inventory.parquet with route_template, example_url,
#          years_available, status. DRF `count` is the full filtered total. stdlib urllib only.
import json
import re
import signal
import time
import urllib.request
import urllib.error
from pathlib import Path
import polars as pl


# INTENT: hard per-request wall-clock guard. SIGALRM fires after HARD_DEADLINE real seconds
#         regardless of socket read activity, so a slow-trickle response (which keeps the socket
#         read timeout from ever firing) is still aborted. Single-threaded main-thread script, so
#         signal.alarm() is valid and reliable here.
class _HardTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    # REASONING: raising inside the handler unwinds the blocking urlopen/read call in the main
    #            thread, converting an unbounded network wait into a catchable timeout.
    raise _HardTimeout("wall-clock deadline exceeded")


signal.signal(signal.SIGALRM, _alarm_handler)
HARD_DEADLINE = 25  # seconds of real time per attempt (> the 20s socket timeout, < a true hang)

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
OUT_DIR = PROJECT_DIR / "2026-08-07_endpoint-ground-truth"
IN_PARQUET = OUT_DIR / "37_live_probe_inventory.parquet"
OUT_PARQUET = OUT_DIR / "38_boundary_years.parquet"
BASE = "https://educationdata.urban.org"
UA = {"User-Agent": "daaf-endpoint-audit/1.0"}


def http_get_status(url, timeout=20, retries=2):
    # INTENT: return (status, count, note). Each attempt is bounded by BOTH the socket read
    #         timeout (inter-byte gaps) AND a SIGALRM hard wall-clock deadline (total request
    #         time) so no attempt can hang the sweep, including on slow-trickle responses.
    last_err = ""
    for attempt in range(1, retries + 1):
        signal.alarm(HARD_DEADLINE)  # arm hard deadline for this attempt
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return resp.status, (data.get("count") if isinstance(data, dict) else None), ""
        except urllib.error.HTTPError as e:
            return e.code, None, f"HTTPError {e.code}"
        except _HardTimeout as e:
            # ASSUMES: a wall-clock timeout means the endpoint is pathologically slow — skip it
            #          (recorded as CONN_ERROR) rather than retry into another long hang.
            return None, None, f"CONN_ERROR: HardTimeout after {HARD_DEADLINE}s: {e}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)
        finally:
            signal.alarm(0)  # always disarm so pacing sleeps / polars I/O are never interrupted
    return None, None, f"CONN_ERROR: {last_err}"


def parse_years(s):
    if s is None:
        return []
    t = (s.replace("&ndash;", "-").replace("&#8211;", "-")
          .replace("–", "-").replace("—", "-").replace("‒", "-").replace("‐", "-"))
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


def build_probe_url(template, example, year):
    # INTENT: concrete path substituting the given boundary year for {year} and example-segment
    #         values for any other {placeholder} (Portal-valid concretization).
    tparts = template.strip("/").split("/")
    eparts = example.strip("/").split("/") if example else []
    out = []
    for i, seg in enumerate(tparts):
        if seg.startswith("{") and seg.endswith("}"):
            name = seg.strip("{}")
            if name == "year":
                out.append(str(year))
            elif i < len(eparts):
                out.append(eparts[i])
            else:
                out.append(seg)
        else:
            out.append(seg)
    return "/" + "/".join(out) + "/"


# --- Load: live endpoints from 37 ---
inv = pl.read_parquet(IN_PARQUET)
live = inv.filter(pl.col("status") == 200)
print(f"Loaded 37 inventory: {inv.height} rows; live (200): {live.height}")

# --- Probe: first & last year of each live endpoint's years_available ---
records = []
rows = live.iter_rows(named=True)
live_list = list(rows)
for i, r in enumerate(live_list, start=1):
    years = parse_years(r["years_available"])
    if not years:
        print(f"  id={r['endpoint_id']} {r['route_template']}: no parseable years; skip")
        continue
    for boundary, yr in (("first", years[0]), ("last", years[-1])):
        path = build_probe_url(r["route_template"], r["example_url"], yr)
        probed_url = f"{BASE}{path}?limit=1"
        status, count, note = http_get_status(probed_url)
        anomaly = ""
        if status == 404:
            anomaly = "404-OVERSTATEMENT"
        elif status == 200 and (count == 0):
            anomaly = "ZERO-ROWS"
        print(f"[{i}/{len(live_list)}] id={r['endpoint_id']} {r['route_template']} "
              f"{boundary}={yr} -> {status} count={count} {anomaly}")
        records.append({
            "endpoint_id": r["endpoint_id"],
            "section": r["section"],
            "route_template": r["route_template"],
            "years_available": r["years_available"],
            "boundary": boundary,
            "year": yr,
            "probed_url": probed_url,
            "status": status,
            "count": count,
            "anomaly": anomaly,
            "error_note": note,
        })
        time.sleep(1.0)  # polite pacing
    # INTENT: incremental checkpoint so partial boundary evidence survives an interrupt/hang.
    if i % 10 == 0 and records:
        pl.DataFrame(records).write_parquet(OUT_PARQUET)
        print(f"  [checkpoint] wrote {len(records)} rows after {i}/{len(live_list)} endpoints")

# --- Save ---
df = pl.DataFrame(records)
df.write_parquet(OUT_PARQUET)
print(f"\nSaved: {OUT_PARQUET}  shape={df.shape}")

# --- Validate ---
assert df.height > 0, "No boundary probes recorded"
print(f"VALIDATION: rows={df.height} PASS")
print("\n=== BOUNDARY-YEAR ANOMALIES ===")
anom = df.filter(pl.col("anomaly") != "")
if anom.height == 0:
    print("  (none — all boundary years returned 200 with >0 rows)")
for r in anom.iter_rows(named=True):
    print(f"  id={r['endpoint_id']} {r['route_template']} {r['boundary']}={r['year']} "
          f"-> {r['status']} count={r['count']} [{r['anomaly']}]")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 16:51:43
# Command: python3 /daaf/scripts/mirror_maintenance/38_boundary-years_b.py
# Duration: 788s
# Exit code: 0
#
# --- STDOUT ---
# Loaded 37 inventory: 129 rows; live (200): 129
# [1/129] id=1 /api/v1/college-university/ipeds/directory/{year}/ first=1980 -> 200 count=3675 
# [1/129] id=1 /api/v1/college-university/ipeds/directory/{year}/ last=2024 -> 200 count=6072 
# [2/129] id=24 /api/v1/schools/ccd/directory/{year}/ first=1986 -> 200 count=85288 
# [2/129] id=24 /api/v1/schools/ccd/directory/{year}/ last=2024 -> 200 count=102178 
# [3/129] id=54 /api/v1/school-districts/ccd/directory/{year}/ first=1986 -> 200 count=17051 
# [3/129] id=54 /api/v1/school-districts/ccd/directory/{year}/ last=2024 -> 200 count=19636 
# [4/129] id=2 /api/v1/college-university/ipeds/institutional-characteristics/{year}/ first=1980 -> 200 count=3675 
# [4/129] id=2 /api/v1/college-university/ipeds/institutional-characteristics/{year}/ last=2024 -> 200 count=5963 
# [5/129] id=25 /api/v1/schools/ccd/enrollment/{year}/{grade}/ first=1986 -> 200 count=23253 
# [5/129] id=25 /api/v1/schools/ccd/enrollment/{year}/{grade}/ last=2024 -> 200 count=33485 
# [6/129] id=56 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/ first=1986 -> 200 count=13349 
# [6/129] id=56 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/ last=2024 -> 200 count=16203 
# [7/129] id=3 /api/v1/college-university/ipeds/admissions-enrollment/{year}/ first=2001 -> 200 count=29307 
# [7/129] id=3 /api/v1/college-university/ipeds/admissions-enrollment/{year}/ last=2024 -> 200 count=9780 
# [8/129] id=26 /api/v1/schools/ccd/enrollment/{year}/{grade}/race/ first=1986 -> 200 count=48531 
# [8/129] id=26 /api/v1/schools/ccd/enrollment/{year}/{grade}/race/ last=2024 -> 200 count=488376 
# [9/129] id=58 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/ first=1986 -> 200 count=14141 
# [9/129] id=58 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/ last=2024 -> 200 count=146358 
# [10/129] id=4 /api/v1/college-university/ipeds/admissions-requirements/{year}/ first=1990 -> 200 count=10287 
# [10/129] id=4 /api/v1/college-university/ipeds/admissions-requirements/{year}/ last=2022 -> 200 count=6138 
#   [checkpoint] wrote 20 rows after 10/129 endpoints
# [11/129] id=27 /api/v1/schools/ccd/enrollment/{year}/{grade}/sex/ first=1986 -> 200 count=46367 
# [11/129] id=27 /api/v1/schools/ccd/enrollment/{year}/{grade}/sex/ last=2024 -> 200 count=211688 
# [12/129] id=59 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/sex/ first=1986 -> 200 count=14085 
# [12/129] id=59 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/sex/ last=2024 -> 200 count=65292 
# [13/129] id=6 /api/v1/college-university/ipeds/academic-year-tuition/{year}/ first=1986 -> 200 count=8197 
# [13/129] id=6 /api/v1/college-university/ipeds/academic-year-tuition/{year}/ last=2023 -> 200 count=17608 
# [14/129] id=28 /api/v1/schools/ccd/enrollment/{year}/{grade}/race/sex/ first=1986 -> 200 count=38853 
# [14/129] id=28 /api/v1/schools/ccd/enrollment/{year}/{grade}/race/sex/ last=2024 -> 200 count=1019979 
# [15/129] id=61 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/sex/ first=1986 -> 200 count=14031 
# [15/129] id=61 /api/v1/school-districts/ccd/enrollment/{year}/{grade}/race/sex/ last=2024 -> 200 count=444204 
# [16/129] id=5 /api/v1/college-university/ipeds/academic-year-tuition-prof-program/{year}/ first=1986 -> 200 count=608 
# [16/129] id=5 /api/v1/college-university/ipeds/academic-year-tuition-prof-program/{year}/ last=2023 -> 200 count=1575 
# [17/129] id=29 /api/v1/school-districts/ccd/finance/{year}/ first=1991 -> 200 count=16229 
# [17/129] id=29 /api/v1/school-districts/ccd/finance/{year}/ last=2020 -> 200 count=19554 
# [18/129] id=73 /api/v1/schools/crdc/directory/{year}/ first=2011 -> 200 count=95635 
# [18/129] id=73 /api/v1/schools/crdc/directory/{year}/ last=2021 -> 200 count=98010 
# [19/129] id=10 /api/v1/college-university/ipeds/academic-year-room-board-other/{year}/ first=1999 -> 200 count=11024 
# [19/129] id=10 /api/v1/college-university/ipeds/academic-year-room-board-other/{year}/ last=2023 -> 200 count=11475 
# [20/129] id=30 /api/v1/school-districts/saipe/{year}/ first=1995 -> 200 count=14468 
# [20/129] id=30 /api/v1/school-districts/saipe/{year}/ last=2024 -> 200 count=13132 
#   [checkpoint] wrote 40 rows after 20/129 endpoints
# [21/129] id=60 /api/v1/schools/crdc/enrollment/{year}/race/sex/ first=2011 -> 200 count=2295240 
# [21/129] id=60 /api/v1/schools/crdc/enrollment/{year}/race/sex/ last=2021 -> 200 count=3136320 
# [22/129] id=8 /api/v1/college-university/ipeds/program-year-tuition-cip/{year}/ first=1987 -> 200 count=8725 
# [22/129] id=8 /api/v1/college-university/ipeds/program-year-tuition-cip/{year}/ last=2023 -> 200 count=7953 
# [23/129] id=65 /api/v1/schools/crdc/enrollment/{year}/disability/sex/ first=2011 -> 200 count=860715 
# [23/129] id=65 /api/v1/schools/crdc/enrollment/{year}/disability/sex/ last=2021 -> 200 count=1960200 
# [24/129] id=80 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/ first=2009 -> 200 count=13921 
# [24/129] id=80 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/ last=2020 -> 200 count=14455 
# [25/129] id=7 /api/v1/college-university/ipeds/program-year-room-board-other/{year}/ first=1999 -> 200 count=2252 
# [25/129] id=7 /api/v1/college-university/ipeds/program-year-room-board-other/{year}/ last=2023 -> 200 count=4250 
# [26/129] id=67 /api/v1/schools/crdc/enrollment/{year}/lep/sex/ first=2011 -> 200 count=573810 
# [26/129] id=67 /api/v1/schools/crdc/enrollment/{year}/lep/sex/ last=2021 -> 200 count=1176120 
# [27/129] id=81 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/race/ first=2009 -> 200 count=72406 
# [27/129] id=81 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/race/ last=2020 -> 200 count=74719 
# [28/129] id=9 /api/v1/college-university/ipeds/enrollment-full-time-equivalent/{year}/{level_of_study}/ first=1997 -> 200 count=9744 
# [28/129] id=9 /api/v1/college-university/ipeds/enrollment-full-time-equivalent/{year}/{level_of_study}/ last=2023 -> 200 count=5861 
# [29/129] id=82 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/sex/ first=2009 -> 200 count=43028 
# [29/129] id=82 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/sex/ last=2020 -> 200 count=43631 
# [30/129] id=83 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/special-populations/ first=2009 -> 200 count=50343 
# [30/129] id=83 /api/v1/school-districts/edfacts/assessments/{year}/{grade_edfacts}/special-populations/ last=2020 -> 200 count=66923 
#   [checkpoint] wrote 60 rows after 30/129 endpoints
# [31/129] id=101 /api/v1/school-districts/edfacts/grad-rates/{year}/ first=2010 -> 200 count=113260 
# [31/129] id=101 /api/v1/school-districts/edfacts/grad-rates/{year}/ last=2019 -> 200 count=93655 
# [32/129] id=119 /api/v1/schools/crdc/discipline-instances/{year}/ first=2015 -> 200 count=481800 
# [32/129] id=119 /api/v1/schools/crdc/discipline-instances/{year}/ last=2021 -> 200 count=588060 
# [33/129] id=13 /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ first=1986 -> 200 count=1382688 
# [33/129] id=13 /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/race/sex/ last=2024 -> 200 count=2941600 
# [34/129] id=69 /api/v1/schools/crdc/discipline/{year}/disability/sex/ first=2011 -> 200 count=1147620 
# [34/129] id=69 /api/v1/schools/crdc/discipline/{year}/disability/sex/ last=2021 -> 200 count=1176120 
# [35/129] id=71 /api/v1/schools/crdc/discipline/{year}/disability/race/sex/ first=2011 -> 200 count=7172625 
# [35/129] id=71 /api/v1/schools/crdc/discipline/{year}/disability/race/sex/ last=2021 -> 200 count=7350750 
# [36/129] id=15 /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/age/sex/ first=1991 -> 200 count=968172 
# [36/129] id=15 /api/v1/college-university/ipeds/fall-enrollment/{year}/{level_of_study}/age/sex/ last=2024 -> 200 count=235008 
# [37/129] id=72 /api/v1/schools/crdc/discipline/{year}/disability/lep/sex/ first=2011 -> 200 count=2008335 
# [37/129] id=72 /api/v1/schools/crdc/discipline/{year}/disability/lep/sex/ last=2021 -> 200 count=2058210 
# [38/129] id=41 /api/v1/schools/crdc/harassment-or-bullying/{year}/allegations/ first=2013 -> 200 count=95507 
# [38/129] id=41 /api/v1/schools/crdc/harassment-or-bullying/{year}/allegations/ last=2021 -> 200 count=98010 
# [39/129] id=84 /api/v1/college-university/ipeds/fall-enrollment/{year}/residence/ first=1986 -> 200 count=111784 
# [39/129] id=84 /api/v1/college-university/ipeds/fall-enrollment/{year}/residence/ last=2024 -> 200 count=140238 
# [40/129] id=18 /api/v1/college-university/ipeds/enrollment-headcount/{year}/{level_of_study}/ first=1996 -> 200 count=9896 
# [40/129] id=18 /api/v1/college-university/ipeds/enrollment-headcount/{year}/{level_of_study}/ last=2021 -> 200 count=172740 
#   [checkpoint] wrote 80 rows after 40/129 endpoints
# [41/129] id=42 /api/v1/schools/crdc/harassment-or-bullying/{year}/race/sex/ first=2011 -> 200 count=2295240 
# [41/129] id=42 /api/v1/schools/crdc/harassment-or-bullying/{year}/race/sex/ last=2021 -> 200 count=2352240 
# [42/129] id=16 /api/v1/college-university/ipeds/fall-retention/{year}/ first=2003 -> 200 count=12162 
# [42/129] id=16 /api/v1/college-university/ipeds/fall-retention/{year}/ last=2024 -> 200 count=11156 
# [43/129] id=43 /api/v1/schools/crdc/harassment-or-bullying/{year}/disability/sex/ first=2011 -> 200 count=860715 
# [43/129] id=43 /api/v1/schools/crdc/harassment-or-bullying/{year}/disability/sex/ last=2021 -> 200 count=882090 
# [44/129] id=44 /api/v1/schools/crdc/harassment-or-bullying/{year}/lep/sex/ first=2011 -> 200 count=573810 
# [44/129] id=44 /api/v1/schools/crdc/harassment-or-bullying/{year}/lep/sex/ last=2021 -> 200 count=588060 
# [45/129] id=91 /api/v1/college-university/ipeds/finance/{year}/ first=1979 -> 200 count=3189 
# [45/129] id=91 /api/v1/college-university/ipeds/finance/{year}/ last=2017 -> 200 count=6857 
# [46/129] id=17 /api/v1/college-university/ipeds/student-faculty-ratio/{year}/ first=2009 -> 200 count=6672 
# [46/129] id=17 /api/v1/college-university/ipeds/student-faculty-ratio/{year}/ last=2024 -> 200 count=5578 
# [47/129] id=37 /api/v1/schools/crdc/chronic-absenteeism/{year}/race/sex/ first=2013 -> 200 count=2267424 
# [47/129] id=37 /api/v1/schools/crdc/chronic-absenteeism/{year}/race/sex/ last=2022 -> 200 count=1756348 
# [48/129] id=32 /api/v1/college-university/ipeds/sfa-grants-and-net-price/{year}/ first=2008 -> 200 count=44211 
# [48/129] id=32 /api/v1/college-university/ipeds/sfa-grants-and-net-price/{year}/ last=2021 -> 200 count=37009 
# [49/129] id=38 /api/v1/schools/crdc/chronic-absenteeism/{year}/disability/sex/ first=2013 -> 200 count=850284 
# [49/129] id=38 /api/v1/schools/crdc/chronic-absenteeism/{year}/disability/sex/ last=2022 -> 200 count=925225 
# [50/129] id=39 /api/v1/schools/crdc/chronic-absenteeism/{year}/lep/sex/ first=2013 -> 200 count=566856 
# [50/129] id=39 /api/v1/schools/crdc/chronic-absenteeism/{year}/lep/sex/ last=2022 -> 200 count=759246 
#   [checkpoint] wrote 100 rows after 50/129 endpoints
# [51/129] id=96 /api/v1/college-university/ipeds/sfa-by-living-arrangement/{year}/ first=2008 -> 200 count=63184 
# [51/129] id=96 /api/v1/college-university/ipeds/sfa-by-living-arrangement/{year}/ last=2021 -> 200 count=45994 
# [52/129] id=34 /api/v1/schools/crdc/restraint-and-seclusion/{year}/instances/ first=2013 -> 200 count=382028 
# [52/129] id=34 /api/v1/schools/crdc/restraint-and-seclusion/{year}/instances/ last=2021 -> 200 count=588060 
# [53/129] id=97 /api/v1/college-university/ipeds/sfa-by-tuition-type/{year}/ first=1999 -> 200 count=14285 
# [53/129] id=97 /api/v1/college-university/ipeds/sfa-by-tuition-type/{year}/ last=2021 -> 200 count=16206 
# [54/129] id=35 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/sex/ first=2011 -> 200 count=1129308 
# [54/129] id=35 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/sex/ last=2021 -> 200 count=1176120 
# [55/129] id=98 /api/v1/college-university/ipeds/sfa-all-undergraduates/{year}/ first=2007 -> 200 count=13048 
# [55/129] id=98 /api/v1/college-university/ipeds/sfa-all-undergraduates/{year}/ last=2021 -> 200 count=17127 
# [56/129] id=36 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/race/sex/ first=2011 -> 200 count=7058175 
# [56/129] id=36 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/race/sex/ last=2021 -> 200 count=6860700 
# [57/129] id=99 /api/v1/college-university/ipeds/sfa-ftft/{year}/ first=1999 -> 200 count=26999 
# [57/129] id=99 /api/v1/college-university/ipeds/sfa-ftft/{year}/ last=2021 -> 200 count=59939 
# [58/129] id=20 /api/v1/college-university/ipeds/grad-rates/{year}/ first=1996 -> 200 count=191850 
# [58/129] id=20 /api/v1/college-university/ipeds/grad-rates/{year}/ last=2023 -> 200 count=200675 
# [59/129] id=40 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/lep/sex/ first=2011 -> 200 count=1976289 
# [59/129] id=40 /api/v1/schools/crdc/restraint-and-seclusion/{year}/disability/lep/sex/ last=2021 -> 200 count=2058210 
# [60/129] id=19 /api/v1/college-university/ipeds/grad-rates-200pct/{year}/ first=2007 -> 200 count=5605 
# [60/129] id=19 /api/v1/college-university/ipeds/grad-rates-200pct/{year}/ last=2023 -> 200 count=4838 
#   [checkpoint] wrote 120 rows after 60/129 endpoints
# [61/129] id=46 /api/v1/schools/crdc/ap-ib-enrollment/{year}/race/sex/ first=2011 -> 200 count=2295240 
# [61/129] id=46 /api/v1/schools/crdc/ap-ib-enrollment/{year}/race/sex/ last=2021 -> 200 count=2352240 
# [62/129] id=21 /api/v1/college-university/ipeds/grad-rates-pell/{year}/ first=2015 -> 200 count=44188 
# [62/129] id=21 /api/v1/college-university/ipeds/grad-rates-pell/{year}/ last=2023 -> 200 count=38832 
# [63/129] id=47 /api/v1/schools/crdc/ap-ib-enrollment/{year}/disability/sex/ first=2011 -> 200 count=573810 
# [63/129] id=47 /api/v1/schools/crdc/ap-ib-enrollment/{year}/disability/sex/ last=2021 -> 200 count=882090 
# [64/129] id=22 /api/v1/college-university/ipeds/outcome-measures/{year}/ first=2015 -> 200 count=31917 
# [64/129] id=22 /api/v1/college-university/ipeds/outcome-measures/{year}/ last=2021 -> 200 count=88550 
# [65/129] id=48 /api/v1/schools/crdc/ap-ib-enrollment/{year}/lep/sex/ first=2011 -> 200 count=573810 
# [65/129] id=48 /api/v1/schools/crdc/ap-ib-enrollment/{year}/lep/sex/ last=2021 -> 200 count=588060 
# [66/129] id=31 /api/v1/college-university/ipeds/completers/{year}/ first=2011 -> 200 count=223440 
# [66/129] id=31 /api/v1/college-university/ipeds/completers/{year}/ last=2021 -> 200 count=181620 
# [67/129] id=53 /api/v1/schools/crdc/ap-exams/{year}/race/sex/ first=2011 -> 200 count=2295240 
# [67/129] id=53 /api/v1/schools/crdc/ap-exams/{year}/race/sex/ last=2017 -> 200 count=2343168 
# [68/129] id=23 /api/v1/college-university/ipeds/completions-cip-2/{year}/ first=1991 -> 200 count=1420464 
# [68/129] id=23 /api/v1/college-university/ipeds/completions-cip-2/{year}/ last=2022 -> 200 count=4159980 
# [69/129] id=55 /api/v1/schools/crdc/ap-exams/{year}/disability/sex/ first=2011 -> 200 count=573810 
# [69/129] id=55 /api/v1/schools/crdc/ap-exams/{year}/disability/sex/ last=2017 -> 200 count=585792 
# [70/129] id=33 /api/v1/college-university/ipeds/completions-cip-6/{year}/ first=1983 -> 200 count=344181 
# [70/129] id=33 /api/v1/college-university/ipeds/completions-cip-6/{year}/ last=2023 -> 200 count=9184110 
#   [checkpoint] wrote 140 rows after 70/129 endpoints
# [71/129] id=57 /api/v1/schools/crdc/ap-exams/{year}/lep/sex/ first=2011 -> 200 count=573810 
# [71/129] id=57 /api/v1/schools/crdc/ap-exams/{year}/lep/sex/ last=2017 -> 200 count=585792 
# [72/129] id=45 /api/v1/college-university/ipeds/academic-libraries/{year}/ first=2013 -> 200 count=4271 
# [72/129] id=45 /api/v1/college-university/ipeds/academic-libraries/{year}/ last=2023 -> 200 count=3652 
# [73/129] id=49 /api/v1/schools/crdc/sat-act-participation/{year}/race/sex/ first=2011 -> 200 count=2295240 
# [73/129] id=49 /api/v1/schools/crdc/sat-act-participation/{year}/race/sex/ last=2021 -> 200 count=2352240 
# [74/129] id=50 /api/v1/schools/crdc/sat-act-participation/{year}/disability/sex/ first=2011 -> 200 count=573810 
# [74/129] id=50 /api/v1/schools/crdc/sat-act-participation/{year}/disability/sex/ last=2021 -> 200 count=588060 
# [75/129] id=102 /api/v1/college-university/ipeds/salaries-instructional-staff/{year}/ first=1980 -> 200 count=52602 
# [75/129] id=102 /api/v1/college-university/ipeds/salaries-instructional-staff/{year}/ last=2024 -> 200 count=365184 
# [76/129] id=51 /api/v1/schools/crdc/sat-act-participation/{year}/lep/sex/ first=2011 -> 200 count=573810 
# [76/129] id=51 /api/v1/schools/crdc/sat-act-participation/{year}/lep/sex/ last=2021 -> 200 count=588060 
# [77/129] id=103 /api/v1/college-university/ipeds/salaries-noninstructional-staff/{year}/ first=2012 -> 200 count=67956 
# [77/129] id=103 /api/v1/college-university/ipeds/salaries-noninstructional-staff/{year}/ last=2024 -> 200 count=54796 
# [78/129] id=52 /api/v1/schools/crdc/teachers-staff/{year}/ first=2011 -> 200 count=95635 
# [78/129] id=52 /api/v1/schools/crdc/teachers-staff/{year}/ last=2021 -> 200 count=98010 
# [79/129] id=63 /api/v1/college-university/scorecard/institutional-characteristics/{year}/ first=1996 -> 200 count=7007 
# [79/129] id=63 /api/v1/college-university/scorecard/institutional-characteristics/{year}/ last=2020 -> 200 count=6681 
# [80/129] id=68 /api/v1/college-university/scorecard/student-characteristics/{year}/aid-applicants/ first=1997 -> 200 count=6470 
# [80/129] id=68 /api/v1/college-university/scorecard/student-characteristics/{year}/aid-applicants/ last=2016 -> 200 count=6976 
#   [checkpoint] wrote 160 rows after 80/129 endpoints
# [81/129] id=107 /api/v1/schools/crdc/math-and-science/{year}/race/sex/ first=2011 -> 200 count=2295240 
# [81/129] id=107 /api/v1/schools/crdc/math-and-science/{year}/race/sex/ last=2021 -> 200 count=2352240 
# [82/129] id=70 /api/v1/college-university/scorecard/student-characteristics/{year}/home-neighborhood/ first=1997 -> 200 count=6470 
# [82/129] id=70 /api/v1/college-university/scorecard/student-characteristics/{year}/home-neighborhood/ last=2016 -> 200 count=6976 
# [83/129] id=108 /api/v1/schools/crdc/math-and-science/{year}/disability/sex/ first=2011 -> 200 count=573810 
# [83/129] id=108 /api/v1/schools/crdc/math-and-science/{year}/disability/sex/ last=2021 -> 200 count=588060 
# [84/129] id=62 /api/v1/college-university/scorecard/earnings/{year}/ first=2003 -> 200 count=6189 
# [84/129] id=62 /api/v1/college-university/scorecard/earnings/{year}/ last=2018 -> 200 count=16761 
# [85/129] id=109 /api/v1/schools/crdc/math-and-science/{year}/lep/sex/ first=2011 -> 200 count=573810 
# [85/129] id=109 /api/v1/schools/crdc/math-and-science/{year}/lep/sex/ last=2021 -> 200 count=588060 
# [86/129] id=64 /api/v1/college-university/scorecard/default/{year}/ first=1996 -> 200 count=6249 
# [86/129] id=64 /api/v1/college-university/scorecard/default/{year}/ last=2020 -> 200 count=5779 
# [87/129] id=120 /api/v1/schools/crdc/algebra1/{year}/race/sex first=2011 -> 200 count=7842070 
# [87/129] id=120 /api/v1/schools/crdc/algebra1/{year}/race/sex last=2021 -> 200 count=7056720 
# [88/129] id=66 /api/v1/college-university/scorecard/repayment/{year}/ first=2007 -> 200 count=5986 
# [88/129] id=66 /api/v1/college-university/scorecard/repayment/{year}/ last=2016 -> 200 count=18325 
# [89/129] id=121 /api/v1/schools/crdc/algebra1/{year}/disability/sex/ first=2011 -> 200 count=2295240 
# [89/129] id=121 /api/v1/schools/crdc/algebra1/{year}/disability/sex/ last=2021 -> 200 count=1764180 
# [90/129] id=87 /api/v1/college-university/nhgis/census-1990/{year}/ first=1980 -> 200 count=3664 
# [90/129] id=87 /api/v1/college-university/nhgis/census-1990/{year}/ last=2023 -> 200 count=6163 
#   [checkpoint] wrote 180 rows after 90/129 endpoints
# [91/129] id=122 /api/v1/schools/crdc/algebra1/{year}/lep/sex/ first=2011 -> 200 count=2295240 
# [91/129] id=122 /api/v1/schools/crdc/algebra1/{year}/lep/sex/ last=2021 -> 200 count=1764180 
# [92/129] id=86 /api/v1/college-university/nhgis/census-2000/{year}/ first=1980 -> 200 count=3664 
# [92/129] id=86 /api/v1/college-university/nhgis/census-2000/{year}/ last=2023 -> 200 count=6163 
# [93/129] id=110 /api/v1/schools/crdc/offenses/{year}/ first=2015 -> 200 count=94652 
# [93/129] id=110 /api/v1/schools/crdc/offenses/{year}/ last=2021 -> 200 count=98010 
# [94/129] id=85 /api/v1/college-university/nhgis/census-2010/{year}/ first=1980 -> 200 count=3664 
# [94/129] id=85 /api/v1/college-university/nhgis/census-2010/{year}/ last=2023 -> 200 count=6163 
# [95/129] id=111 /api/v1/schools/crdc/dual-enrollment/{year}/race/sex first=2015 -> 200 count=2271648 
# [95/129] id=111 /api/v1/schools/crdc/dual-enrollment/{year}/race/sex last=2021 -> 200 count=2352240 
# [96/129] id=112 /api/v1/schools/crdc/dual-enrollment/{year}/disability/sex first=2015 -> 200 count=567912 
# [96/129] id=112 /api/v1/schools/crdc/dual-enrollment/{year}/disability/sex last=2021 -> 200 count=588060 
# [97/129] id=134 /api/v1/college-university/nhgis/census-2020/{year}/ first=1980 -> 200 count=3664 
# [97/129] id=134 /api/v1/college-university/nhgis/census-2020/{year}/ last=2023 -> 200 count=6163 
# [98/129] id=92 /api/v1/college-university/fsa/financial-responsibility/{year}/ first=2006 -> 200 count=3150 
# [98/129] id=92 /api/v1/college-university/fsa/financial-responsibility/{year}/ last=2016 -> 200 count=3627 
# [99/129] id=113 /api/v1/schools/crdc/dual-enrollment/{year}/lep/sex first=2015 -> 200 count=567912 
# [99/129] id=113 /api/v1/schools/crdc/dual-enrollment/{year}/lep/sex last=2021 -> 200 count=588060 
# [100/129] id=93 /api/v1/college-university/fsa/grants/{year}/ first=1999 -> 200 count=25730 
# [100/129] id=93 /api/v1/college-university/fsa/grants/{year}/ last=2021 -> 200 count=24600 
#   [checkpoint] wrote 200 rows after 100/129 endpoints
# [101/129] id=114 /api/v1/schools/crdc/credit-recovery/{year}/ first=2015 -> 200 count=96360 
# [101/129] id=114 /api/v1/schools/crdc/credit-recovery/{year}/ last=2017 -> 200 count=97632 
# [102/129] id=94 /api/v1/college-university/fsa/loans/{year}/ first=1999 -> 200 count=65842 
# [102/129] id=94 /api/v1/college-university/fsa/loans/{year}/ last=2021 -> 200 count=64540 
# [103/129] id=115 /api/v1/schools/crdc/suspensions-days/{year}/race/sex first=2015 -> 200 count=2312640 
# [103/129] id=115 /api/v1/schools/crdc/suspensions-days/{year}/race/sex last=2021 -> 200 count=2352240 
# [104/129] id=95 /api/v1/college-university/fsa/campus-based-volume/{year}/ first=2001 -> 200 count=12051 
# [104/129] id=95 /api/v1/college-university/fsa/campus-based-volume/{year}/ last=2021 -> 200 count=10863 
# [105/129] id=116 /api/v1/schools/crdc/suspensions-days/{year}/disability/sex first=2015 -> 200 count=867240 
# [105/129] id=116 /api/v1/schools/crdc/suspensions-days/{year}/disability/sex last=2021 -> 200 count=882090 
# [106/129] id=104 /api/v1/college-university/fsa/90-10-revenue-percentages/{year}/ first=2014 -> 200 count=1909 
# [106/129] id=104 /api/v1/college-university/fsa/90-10-revenue-percentages/{year}/ last=2021 -> 200 count=1626 
# [107/129] id=117 /api/v1/schools/crdc/suspensions-days/{year}/lep/sex first=2015 -> 200 count=578160 
# [107/129] id=117 /api/v1/schools/crdc/suspensions-days/{year}/lep/sex last=2021 -> 200 count=588060 
# [108/129] id=105 /api/v1/college-university/nacubo/endowments/{year}/ first=2012 -> 200 count=813 
# [108/129] id=105 /api/v1/college-university/nacubo/endowments/{year}/ last=2022 -> 200 count=664 
# [109/129] id=118 /api/v1/schools/crdc/offerings/{year}/ first=2011 -> 200 count=95635 
# [109/129] id=118 /api/v1/schools/crdc/offerings/{year}/ last=2021 -> 200 count=98010 
# [110/129] id=106 /api/v1/college-university/nccs/990-forms/{year}/ first=1993 -> 200 count=661 
# [110/129] id=106 /api/v1/college-university/nccs/990-forms/{year}/ last=2016 -> 200 count=1561 
#   [checkpoint] wrote 220 rows after 110/129 endpoints
# [111/129] id=123 /api/v1/schools/crdc/school-finance/{year}/ first=2011 -> 200 count=95635 
# [111/129] id=123 /api/v1/schools/crdc/school-finance/{year}/ last=2017 -> 200 count=97632 
# [112/129] id=124 /api/v1/schools/crdc/retention/{year}/{grade}/race/sex first=2011 -> 200 count=2295240 
# [112/129] id=124 /api/v1/schools/crdc/retention/{year}/{grade}/race/sex last=2020 -> 200 count=0 ZERO-ROWS
# [113/129] id=128 /api/v1/college-university/eada/institutional-characteristics/{year}/ first=2002 -> 200 count=1968 
# [113/129] id=128 /api/v1/college-university/eada/institutional-characteristics/{year}/ last=2021 -> 200 count=2028 
# [114/129] id=125 /api/v1/schools/crdc/retention/{year}/{grade}/disability/sex first=2011 -> 200 count=860715 
# [114/129] id=125 /api/v1/schools/crdc/retention/{year}/{grade}/disability/sex last=2017 -> 200 count=878688 
# [115/129] id=130 /api/v1/college-university/campus-crime/hate-crimes/{year}/ first=2005 -> 200 count=86980 
# [115/129] id=130 /api/v1/college-university/campus-crime/hate-crimes/{year}/ last=2021 -> 200 count=1344042 
# [116/129] id=126 /api/v1/schools/crdc/retention/{year}/{grade}/lep/sex first=2011 -> None count=None 
# [116/129] id=126 /api/v1/schools/crdc/retention/{year}/{grade}/lep/sex last=2017 -> None count=None 
# [117/129] id=133 /api/v1/college-university/pseo/earnings-and-flows/{year}/ first=2001 -> 200 count=1838520 
# [117/129] id=133 /api/v1/college-university/pseo/earnings-and-flows/{year}/ last=2021 -> 200 count=793620 
# [118/129] id=131 /api/v1/schools/crdc/covid-indicators/{year}/ first=2020 -> 200 count=97575 
# [118/129] id=131 /api/v1/schools/crdc/covid-indicators/{year}/ last=2021 -> 200 count=98010 
# [119/129] id=132 /api/v1/schools/crdc/internet-access/{year}/ first=2020 -> 200 count=97575 
# [119/129] id=132 /api/v1/schools/crdc/internet-access/{year}/ last=2021 -> 200 count=98010 
# [120/129] id=76 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/ first=2009 -> 200 count=31232 
# [120/129] id=76 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/ last=2020 -> 200 count=28513 
#   [checkpoint] wrote 240 rows after 120/129 endpoints
# [121/129] id=77 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/race/ first=2009 -> 200 count=274163 
# [121/129] id=77 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/race/ last=2020 -> 200 count=241709 
# [122/129] id=78 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/sex/ first=2009 -> 200 count=154822 
# [122/129] id=78 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/sex/ last=2020 -> 200 count=134708 
# [123/129] id=79 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/special-populations/ first=2009 -> 200 count=162963 
# [123/129] id=79 /api/v1/schools/edfacts/assessments/{year}/{grade_edfacts}/special-populations/ last=2020 -> 200 count=165202 
# [124/129] id=100 /api/v1/schools/edfacts/grad-rates/{year}/ first=2010 -> 200 count=213350 
# [124/129] id=100 /api/v1/schools/edfacts/grad-rates/{year}/ last=2019 -> 200 count=172783 
# [125/129] id=127 /api/v1/schools/meps/{year}/ first=2009 -> 200 count=97555 
# [125/129] id=127 /api/v1/schools/meps/{year}/ last=2022 -> 200 count=94941 
# [126/129] id=90 /api/v1/schools/nhgis/census-1990/{year}/ first=1986 -> 200 count=83415 
# [126/129] id=90 /api/v1/schools/nhgis/census-1990/{year}/ last=2023 -> 200 count=102274 
# [127/129] id=89 /api/v1/schools/nhgis/census-2000/{year}/ first=1986 -> 200 count=83415 
# [127/129] id=89 /api/v1/schools/nhgis/census-2000/{year}/ last=2023 -> 200 count=102274 
# [128/129] id=88 /api/v1/schools/nhgis/census-2010/{year}/ first=1986 -> 200 count=83415 
# [128/129] id=88 /api/v1/schools/nhgis/census-2010/{year}/ last=2023 -> 200 count=102274 
# [129/129] id=135 /api/v1/schools/nhgis/census-2020/{year}/ first=1986 -> 200 count=83415 
# [129/129] id=135 /api/v1/schools/nhgis/census-2020/{year}/ last=2023 -> 200 count=102274 
# 
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth/38_boundary_years.parquet  shape=(258, 11)
# VALIDATION: rows=258 PASS
# 
# === BOUNDARY-YEAR ANOMALIES ===
#   id=124 /api/v1/schools/crdc/retention/{year}/{grade}/race/sex last=2020 -> 200 count=0 [ZERO-ROWS]
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
