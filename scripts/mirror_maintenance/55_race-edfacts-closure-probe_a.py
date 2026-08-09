# --- Config ---
# INTENT: Close the open race_edfacts verification. v1 used VALID grade_edfacts values (fixing
#         the wave-4 count-0 miss) but the UNFILTERED national schools race slice returned HTTP
#         500 x3 — Urban's heaviest disaggregated query commonly 500s on size, not because the
#         codes are wrong. This revision (a) confirms the endpoint is reachable via the base
#         (non-race) slice, then (b) probes NARROWED fips-filtered race slices to obtain a
#         non-zero slice and record the distinct observed race codes.
# REASONING: grade_edfacts is coded {3,4,5,6,7,8,9,99} (9="Grades 9-12", 99="Total"). A fips
#            filter (single small state) shrinks the race-disaggregated payload below the size
#            that triggers the 500, without changing the endpoint or the codes under test.
# ASSUMES: Urban live API returns JSON {count, results:[{race:int,...}]}. Read-only GETs;
#          25s SIGALRM per request; ~1 req/sec; <=10 requests total; treat only CONNECTION/
#          TIMEOUT errors as "unreachable" (stop after 3 consecutive); record 500s and keep
#          trying narrower slices within the request budget.
import polars as pl
import json
import signal
import time
import urllib.request
from pathlib import Path

OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "55_race_edfacts_probe.parquet"

# Expected race code set per varlist (for verdict comparison).
EXPECTED_RACE = {1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 99}

RACE_URL = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{year}/{grade}/race/"
BASE_URL = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{year}/{grade}/"

# Probe plan (<=10 requests). kind: 'base' = reachability diagnostic (no race disagg);
# 'race' = race slice, optionally narrowed by fips (single state) to dodge the size-500.
# fips 8=Colorado, 50=Vermont, 44=Rhode Island (small states -> small payloads).
PROBE_PLAN = [
    {"kind": "base", "year": 2015, "grade": 8, "fips": None},   # reachability check
    {"kind": "race", "year": 2015, "grade": 8, "fips": 8},
    {"kind": "race", "year": 2015, "grade": 8, "fips": 50},
    {"kind": "race", "year": 2016, "grade": 8, "fips": 8},
    {"kind": "race", "year": 2015, "grade": 4, "fips": 8},
    {"kind": "race", "year": 2017, "grade": 8, "fips": 44},
    {"kind": "race", "year": 2015, "grade": 8, "fips": None},   # last resort: unfiltered
    {"kind": "race", "year": 2018, "grade": 8, "fips": 8},
    {"kind": "race", "year": 2014, "grade": 8, "fips": 50},
    {"kind": "race", "year": 2016, "grade": 4, "fips": 8},
]

def _timeout(signum, frame):
    raise TimeoutError("request exceeded 25s wall clock")

signal.signal(signal.SIGALRM, _timeout)

# --- Probe loop ---
log_rows = []
consecutive_unreachable = 0   # only connection/timeout errors count here
found = False
observed_races = set()
found_url = None
found_count = None

for i, p in enumerate(PROBE_PLAN):
    if found:
        break
    if consecutive_unreachable >= 3:
        print("STOP: 3 consecutive connection/timeout failures — API treated as unreachable.")
        break
    tmpl = RACE_URL if p["kind"] == "race" else BASE_URL
    url = tmpl.format(year=p["year"], grade=p["grade"])
    if p["fips"] is not None:
        url = f"{url}?fips={p['fips']}"
    status = None
    count = None
    races_here = []
    err = None
    signal.alarm(25)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "daaf-mirror-maintenance/55a"})
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
        count = payload.get("count")
        results = payload.get("results", []) or []
        # 'race' field only present on race-disaggregated slices
        races_here = sorted({r.get("race") for r in results if r.get("race") is not None})
        consecutive_unreachable = 0
        # Success = a RACE slice with a non-zero count and observed race codes.
        if p["kind"] == "race" and count and count > 0 and races_here:
            found = True
            observed_races = set(races_here)
            found_url = url
            found_count = count
    except urllib.error.HTTPError as e:
        # Server responded (e.g., 500) -> reachable but errored; record, do NOT count unreachable.
        err = f"HTTPError: {e.code} {e.reason}"
        status = e.code
        consecutive_unreachable = 0
    except Exception as e:  # connection/timeout -> unreachable
        err = f"{type(e).__name__}: {e}"
        consecutive_unreachable += 1
    finally:
        signal.alarm(0)

    print(f"[{i+1}] {p['kind']:4s} GET {url} -> status={status} count={count} races={races_here} err={err}")
    log_rows.append({
        "attempt": i + 1, "kind": p["kind"], "url": url, "year": p["year"],
        "grade_edfacts": p["grade"], "fips": p["fips"], "http_status": status,
        "count": count, "distinct_races": json.dumps(races_here), "error": err,
    })
    if not found:
        time.sleep(1)  # ~1 req/sec pacing

# --- Verdict ---
print("\n--- RACE_EDFACTS VERDICT ---")
base_ok = any(r["kind"] == "base" and r["count"] and r["count"] > 0 for r in log_rows)
print(f"Base (non-race) slice reachable with data: {base_ok}")
if found:
    matches_expected = observed_races.issubset(EXPECTED_RACE)
    unexpected = observed_races - EXPECTED_RACE
    print(f"NON-ZERO race slice: {found_url} (count={found_count})")
    print(f"Distinct observed race codes: {sorted(observed_races)}")
    print(f"Expected (varlist) race set:  {sorted(EXPECTED_RACE)}")
    verdict = (f"CONFIRMED: race code set observed = {sorted(observed_races)} "
               f"(all within varlist-declared set {sorted(EXPECTED_RACE)})") if matches_expected else \
              (f"CONFIRMED WITH DISCREPANCY: observed {sorted(observed_races)}; "
               f"codes not in varlist set: {sorted(unexpected)}")
else:
    verdict = ("STILL UNVERIFIED: no non-zero race slice returned across "
               f"{len(log_rows)} probe(s). Base slice reachable={base_ok}; race slices "
               f"returned server errors/empties (see probe log http_status/count).")
print("VERDICT:", verdict)

# --- Save probe log ---
out = pl.DataFrame(log_rows)
out = out.with_columns([
    pl.lit(found).alias("nonzero_found"),
    pl.lit(base_ok).alias("base_slice_reachable"),
    pl.lit(json.dumps(sorted(observed_races))).alias("observed_race_set"),
    pl.lit(verdict).alias("verdict"),
])
out.write_parquet(OUT_PATH)
print(f"\nSaved probe log ({out.height} attempts) to: {OUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 22:24:39
# Command: python3 /daaf/scripts/mirror_maintenance/55_race-edfacts-closure-probe_a.py
# Duration: 48s
# Exit code: 0
#
# --- STDOUT ---
# [1] base GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/8/ -> status=None count=None races=[] err=TimeoutError: request exceeded 25s wall clock
# [2] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/8/race/?fips=8 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [3] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/8/race/?fips=50 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [4] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2016/8/race/?fips=8 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [5] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/4/race/?fips=8 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [6] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2017/8/race/?fips=44 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [7] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/8/race/ -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [8] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2018/8/race/?fips=8 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [9] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2014/8/race/?fips=50 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# [10] race GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2016/4/race/?fips=8 -> status=500 count=None races=[] err=HTTPError: 500 Internal Server Error
# 
# --- RACE_EDFACTS VERDICT ---
# Base (non-race) slice reachable with data: False
# VERDICT: STILL UNVERIFIED: no non-zero race slice returned across 10 probe(s). Base slice reachable=False; race slices returned server errors/empties (see probe log http_status/count).
# 
# Saved probe log (10 attempts) to: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/55_race_edfacts_probe.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
