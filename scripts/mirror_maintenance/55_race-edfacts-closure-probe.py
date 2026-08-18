# --- Config ---
# INTENT: Close the open race_edfacts verification: the wave-4 audit could not confirm EDFacts
#         race codes live because its guessed grade values returned count-0. Use the VALID
#         grade_edfacts values from the varlist and probe the live assessments/race endpoint
#         until a non-zero slice is found, then record the distinct observed race codes.
# REASONING: grade_edfacts is coded {3,4,5,6,7,8,9,99} (9="Grades 9-12", 99="Total") per
#            41_variable_inventory — grades 10/11/12 are INVALID and explain the count-0 misses.
# ASSUMES: The Urban live API returns JSON with 'count' and 'results' (list of records carrying
#          an integer 'race' field). Read-only GETs; 25s SIGALRM wall-clock per request;
#          ~1 req/sec pacing; <=10 requests; stop after 3 consecutive failures.
import polars as pl
import json
import signal
import time
import urllib.request
from pathlib import Path

GT = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_endpoint-ground-truth"
OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "55_race_edfacts_probe.parquet"

# Valid grade_edfacts codes (from varlist EP 76/77); ordered to try commonly-populated grades first.
VALID_GRADES = [8, 4, 5, 6, 7, 3, 9, 99]
# Expected race code set per varlist (for verdict comparison).
EXPECTED_RACE = {1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 99}

BASE = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{year}/{grade}/race/"
# Probe plan: (year, grade) combos, mid-range years first, capped at 10 requests.
PROBE_PLAN = [
    (2015, 8), (2016, 8), (2015, 4), (2017, 8), (2018, 8),
    (2014, 8), (2015, 99), (2013, 8), (2016, 4), (2015, 5),
]

def _timeout(signum, frame):
    raise TimeoutError("request exceeded 25s wall clock")

signal.signal(signal.SIGALRM, _timeout)

# --- Probe loop ---
log_rows = []
consecutive_failures = 0
found = False
observed_races = set()
found_url = None
found_count = None

for i, (year, grade) in enumerate(PROBE_PLAN):
    if found:
        break
    if consecutive_failures >= 3:
        print("STOP: 3 consecutive request failures — API treated as unreachable.")
        break
    url = BASE.format(year=year, grade=grade)
    status = None
    count = None
    races_here = []
    err = None
    signal.alarm(25)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "daaf-mirror-maintenance/55"})
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
        count = payload.get("count")
        results = payload.get("results", []) or []
        races_here = sorted({r.get("race") for r in results if r.get("race") is not None})
        consecutive_failures = 0
        if count and count > 0 and races_here:
            found = True
            observed_races = set(races_here)
            found_url = url
            found_count = count
    except Exception as e:  # network/timeout/HTTP error -> record and continue
        err = f"{type(e).__name__}: {e}"
        status = getattr(e, "code", None)
        consecutive_failures += 1
    finally:
        signal.alarm(0)

    print(f"[{i+1}] GET {url} -> status={status} count={count} races={races_here} err={err}")
    log_rows.append({
        "attempt": i + 1, "url": url, "year": year, "grade_edfacts": grade,
        "http_status": status, "count": count,
        "distinct_races": json.dumps(races_here), "error": err,
    })
    if not found:
        time.sleep(1)  # ~1 req/sec pacing

# --- Verdict ---
print("\n--- RACE_EDFACTS VERDICT ---")
if found:
    matches_expected = observed_races.issubset(EXPECTED_RACE)
    print(f"NON-ZERO slice found at: {found_url} (count={found_count})")
    print(f"Distinct observed race codes: {sorted(observed_races)}")
    print(f"Expected (varlist) race set: {sorted(EXPECTED_RACE)}")
    print(f"Observed subset of expected: {matches_expected}")
    unexpected = observed_races - EXPECTED_RACE
    verdict = (f"CONFIRMED: race code set observed = {sorted(observed_races)} "
               f"(all within varlist-declared set)") if matches_expected else \
              (f"CONFIRMED WITH DISCREPANCY: observed {sorted(observed_races)}; "
               f"codes not in varlist set: {sorted(unexpected)}")
else:
    verdict = ("STILL UNVERIFIED: no non-zero slice returned across "
               f"{len(log_rows)} probe(s); see probe log for statuses/counts.")
print("VERDICT:", verdict)

# --- Save probe log ---
out = pl.DataFrame(log_rows)
out = out.with_columns([
    pl.lit(found).alias("nonzero_found"),
    pl.lit(json.dumps(sorted(observed_races))).alias("observed_race_set"),
    pl.lit(verdict).alias("verdict"),
])
out.write_parquet(OUT_PATH)
print(f"\nSaved probe log ({out.height} attempts) to: {OUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 22:23:20
# Command: python3 /daaf/scripts/mirror_maintenance/55_race-edfacts-closure-probe.py
# Duration: 5s
# Exit code: 0
#
# --- STDOUT ---
# [1] GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/8/race/ -> status=500 count=None races=[] err=HTTPError: HTTP Error 500: Internal Server Error
# [2] GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2016/8/race/ -> status=500 count=None races=[] err=HTTPError: HTTP Error 500: Internal Server Error
# [3] GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/4/race/ -> status=500 count=None races=[] err=HTTPError: HTTP Error 500: Internal Server Error
# STOP: 3 consecutive request failures — API treated as unreachable.
# 
# --- RACE_EDFACTS VERDICT ---
# VERDICT: STILL UNVERIFIED: no non-zero slice returned across 3 probe(s); see probe log for statuses/counts.
# 
# Saved probe log (3 attempts) to: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/55_race_edfacts_probe.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
