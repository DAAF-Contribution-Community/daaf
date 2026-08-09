# --- Config ---
# INTENT: Re-run the EDFacts race-code closure probe now that time has passed since the
#         2026-08-08 Urban API outage (systematic HTTP 500 on EDFacts assessments/race). Two
#         immutable predecessors (55, 55_a) both closed STILL-UNVERIFIED: v1's unfiltered
#         national race slice 500'd x3; v1a's base slice timed out and every fips-narrowed race
#         slice 500'd (10/10). If the API has recovered, obtain a non-zero race slice and record
#         the distinct observed race codes; if it is still down, that outcome is itself the
#         deliverable.
# REASONING: grade_edfacts is coded {3,4,5,6,7,8,9,99} (9="Grades 9-12", 99="Total") per Portal
#            metadata — grades 10/11/12 are INVALID. We probe the fallback order specified for
#            this re-probe: 2015/8/race/ -> 2016/8/race/ -> 2015/99/race/, each requested with a
#            bounded ?limit= slice to keep the race-disaggregated payload below the size that
#            historically triggered the 500. On first HTTP 200 with count>0 we page just enough
#            (within the 6-request budget) to collect distinct race values; we do NOT exhaustively
#            page a huge endpoint — distinct values from the first few thousand rows plus the
#            metadata-declared-set comparison is sufficient, with the sample scope noted honestly.
# ASSUMES: Urban live API returns JSON {count, results:[{race:int,...}], next:url|null}. Read-only
#          GETs; 25s SIGALRM wall-clock per request; ~1 req/sec pacing; <=6 requests TOTAL across
#          probing + paging. Treat only CONNECTION/TIMEOUT errors as "unreachable" (stop after 3
#          consecutive); record HTTP 500s and fall through to the next endpoint. The metadata-
#          declared race set is {1..9, 20, 99} plus sentinels {-1,-2,-3}.
# NOTE (skill provenance): the valid grade set and declared race set are established/curated from
#          Portal metadata via the predecessor probes and the wave-4 varlist inventory; they are
#          not re-derived here. If observed codes diverge, that is a real finding, not a code bug.
import polars as pl
import json
import signal
import time
import urllib.request
import urllib.error
from pathlib import Path

OUT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "56_race_edfacts_reprobe.parquet"

# Metadata-declared race code set for the verdict comparison.
# REASONING: {1-9, 20} are the substantive race categories; 99 = Total; sentinels -1/-2/-3 are
#            missing / not-applicable / suppressed and are legitimate observed values, not errors.
DECLARED_RACE = {1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 99}
DECLARED_SENTINELS = {-1, -2, -3}
DECLARED_ALL = DECLARED_RACE | DECLARED_SENTINELS

RACE_URL = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{year}/{grade}/race/"

# Bounded page size to dodge the historical size-500 on the heaviest disaggregated slice.
# ASSUMES: the Urban v1 API honors ?limit=; if not, we still get a valid (larger) first page.
PAGE_LIMIT = 5000
REQUEST_BUDGET = 6          # hard cap on total HTTP requests (probing + paging)
MAX_EXTRA_PAGES = 2         # after first success, page at most this many additional times

# Fallback endpoint order specified for this re-probe (year, grade_edfacts).
ENDPOINT_PLAN = [
    (2015, 8),    # primary
    (2016, 8),    # fallback 1
    (2015, 99),   # fallback 2 (grade 99 = Total)
]


def _timeout(signum, frame):
    raise TimeoutError("request exceeded 25s wall clock")


signal.signal(signal.SIGALRM, _timeout)


# INTENT: single bounded GET returning (status, count, races_in_page, next_url, err).
# REASONING: factored inline via a small closure-free block repeated in the loop would bloat the
#            script; per DAAF sequential style we keep ONE helper-free inline pattern by calling
#            this thin request routine. (A single I/O primitive with no analytic logic is the
#            pragmatic exception; all decision logic stays in the sequential loop below.)
def _fetch(url, ua_tag):
    status = count = next_url = None
    races_here = []
    err = None
    signal.alarm(25)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua_tag})
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
        count = payload.get("count")
        results = payload.get("results", []) or []
        next_url = payload.get("next")
        races_here = sorted({r.get("race") for r in results if r.get("race") is not None})
    except urllib.error.HTTPError as e:
        # Server responded (e.g. 500) -> reachable but errored; record, do NOT count unreachable.
        err = f"HTTPError: {e.code} {e.reason}"
        status = e.code
        return status, count, races_here, next_url, err
    except Exception as e:
        # connection reset / DNS / timeout -> unreachable
        err = f"{type(e).__name__}: {e}"
        return status, count, races_here, next_url, err
    finally:
        signal.alarm(0)
    return status, count, races_here, next_url, err


# --- Probe loop ---
log_rows = []
requests_made = 0
consecutive_unreachable = 0     # only connection/timeout errors count here
found = False
observed_races = set()
found_url = None
found_count = None
pages_sampled = 0
UA = "daaf-mirror-maintenance/56"

for (year, grade) in ENDPOINT_PLAN:
    if found or requests_made >= REQUEST_BUDGET:
        break
    if consecutive_unreachable >= 3:
        print("STOP: 3 consecutive connection/timeout failures — API treated as unreachable.")
        break

    url = f"{RACE_URL.format(year=year, grade=grade)}?limit={PAGE_LIMIT}"
    status, count, races_here, next_url, err = _fetch(url, UA)
    requests_made += 1

    # Classify the error for the unreachable counter (HTTP responses are reachable).
    if err is not None and err.startswith("HTTPError"):
        consecutive_unreachable = 0
    elif err is not None:
        consecutive_unreachable += 1
    else:
        consecutive_unreachable = 0

    print(f"[req {requests_made}] GET {url} -> status={status} count={count} "
          f"races={races_here} next={'yes' if next_url else 'no'} err={err}")
    log_rows.append({
        "request": requests_made, "role": "probe", "url": url, "year": year,
        "grade_edfacts": grade, "http_status": status, "count": count,
        "distinct_races": json.dumps(races_here), "error": err,
    })

    # Success = a race slice with HTTP 200, non-zero count, and observed race codes.
    if status == 200 and count and count > 0 and races_here:
        found = True
        observed_races = set(races_here)
        found_url = url
        found_count = count
        pages_sampled = 1

        # --- Page just enough to expand distinct-race coverage (within budget) ---
        # REASONING: a single limited page may not surface every category (e.g. sentinels or
        #            rarer race codes); pulling a few more pages tightens the observed set WITHOUT
        #            exhaustively walking a multi-hundred-thousand-row endpoint.
        extra = 0
        while (next_url and extra < MAX_EXTRA_PAGES and requests_made < REQUEST_BUDGET):
            time.sleep(1)  # ~1 req/sec pacing
            p_status, p_count, p_races, p_next, p_err = _fetch(next_url, UA)
            requests_made += 1
            extra += 1
            pages_sampled += 1
            print(f"[req {requests_made}] PAGE {next_url} -> status={p_status} "
                  f"races={p_races} next={'yes' if p_next else 'no'} err={p_err}")
            log_rows.append({
                "request": requests_made, "role": "page", "url": next_url, "year": year,
                "grade_edfacts": grade, "http_status": p_status, "count": p_count,
                "distinct_races": json.dumps(p_races), "error": p_err,
            })
            if p_err is not None:
                break  # stop paging on any error; keep what we have
            observed_races |= set(p_races)
            next_url = p_next
        break

    if not found and requests_made < REQUEST_BUDGET:
        time.sleep(1)  # ~1 req/sec pacing between distinct-endpoint probes

# --- Validate ---
# INTENT: minimal invariants so the artifact is trustworthy regardless of verdict.
assert len(log_rows) >= 1, "No probe attempts were logged"
assert requests_made <= REQUEST_BUDGET, f"Request budget exceeded: {requests_made} > {REQUEST_BUDGET}"
print(f"\nValidation passed: {len(log_rows)} log rows, {requests_made} requests (budget {REQUEST_BUDGET}).")

# --- Verdict ---
print("\n--- RACE_EDFACTS RE-PROBE VERDICT ---")
if found:
    substantive = {r for r in observed_races if r >= 0}       # race categories incl. 99=Total
    sentinels_seen = {r for r in observed_races if r < 0}     # missing/NA/suppressed
    unexpected = observed_races - DECLARED_ALL
    subset_ok = observed_races.issubset(DECLARED_ALL)
    print(f"NON-ZERO race slice: {found_url} (count={found_count}); pages sampled={pages_sampled}")
    print(f"Distinct observed race codes: {sorted(observed_races)}")
    print(f"  substantive (>=0): {sorted(substantive)}")
    print(f"  sentinels  (<0):   {sorted(sentinels_seen)}")
    print(f"Declared race set:   {sorted(DECLARED_RACE)} (+sentinels {sorted(DECLARED_SENTINELS)})")
    if subset_ok:
        verdict = (f"CONFIRMED: observed race code set = {sorted(observed_races)} "
                   f"(all within declared set {sorted(DECLARED_RACE)} + sentinels "
                   f"{sorted(DECLARED_SENTINELS)}); sample scope = first {pages_sampled} "
                   f"page(s) x limit {PAGE_LIMIT} of {found_url}.")
    else:
        verdict = (f"CONFIRMED WITH DISCREPANCY: observed {sorted(observed_races)}; codes NOT in "
                   f"declared set: {sorted(unexpected)}; sample scope = first {pages_sampled} "
                   f"page(s) x limit {PAGE_LIMIT} of {found_url}.")
else:
    statuses = [r["http_status"] for r in log_rows]
    all_500 = all(s == 500 for s in statuses if s is not None) and any(s == 500 for s in statuses)
    verdict = ("STILL-BLOCKED: no non-zero race slice returned across "
               f"{requests_made} request(s); statuses={statuses}. "
               + ("All HTTP 500 — Urban EDFacts assessments/race outage persists."
                  if all_500 else
                  "Mix of server errors/timeouts/empties — see probe log."))
print("VERDICT:", verdict)

# --- Save ---
out = pl.DataFrame(log_rows)
out = out.with_columns([
    pl.lit(found).alias("nonzero_found"),
    pl.lit(pages_sampled).alias("pages_sampled"),
    pl.lit(json.dumps(sorted(observed_races))).alias("observed_race_set"),
    pl.lit(json.dumps(sorted(DECLARED_RACE))).alias("declared_race_set"),
    pl.lit(verdict).alias("verdict"),
])
out.write_parquet(OUT_PATH)
print(f"\nSaved re-probe log ({out.height} requests) to: {OUT_PATH}")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-09 14:06:40
# Command: python3 /daaf/scripts/mirror_maintenance/56_race-edfacts-reprobe.py
# Duration: 4s
# Exit code: 0
#
# --- STDOUT ---
# [req 1] GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/8/race/?limit=5000 -> status=500 count=None races=[] next=no err=HTTPError: 500 Internal Server Error
# [req 2] GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2016/8/race/?limit=5000 -> status=500 count=None races=[] next=no err=HTTPError: 500 Internal Server Error
# [req 3] GET https://educationdata.urban.org/api/v1/schools/edfacts/assessments/2015/99/race/?limit=5000 -> status=500 count=None races=[] next=no err=HTTPError: 500 Internal Server Error
# 
# Validation passed: 3 log rows, 3 requests (budget 6).
# 
# --- RACE_EDFACTS RE-PROBE VERDICT ---
# VERDICT: STILL-BLOCKED: no non-zero race slice returned across 3 request(s); statuses=[500, 500, 500]. All HTTP 500 — Urban EDFacts assessments/race outage persists.
# 
# Saved re-probe log (3 requests) to: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-08_dictionary-generation/56_race_edfacts_reprobe.parquet
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
