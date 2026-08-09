#!/usr/bin/env python3
# =============================================================================
# 50_laneB-count-sweep.py  (Lane B EXPANSION — broad endpoint-year count sweep)
# =============================================================================
# INTENT: For every clean 1:1 pair selected in 49_a (54 pairs x up to 3 years =
#   ~159 endpoint-year comparisons across 12 sources), compare the LIVE Urban API
#   `count` (full, unfiltered, for that year) against the v2 mirror's row count
#   filtered to that year. An exact match is the expectation for a 1:1 endpoint<->
#   file pair; a mismatch is either (a) a grain artifact (the "1:1" endpoint is in
#   fact row-multiplied, e.g. one row per offense/crime-type — reclassify, do NOT
#   fail the mirror), or (b) a substantive count divergence (report verbatim).
#
# METHOD:
#   * Live: GET {BASE}{route_template with {year}} + ?limit=1 ; read JSON `count`
#     (DRF returns the full filtered total regardless of page size). First page only.
#   * Mirror: pl.scan_parquet(file).filter(year==Y).select(pl.len()) on the LOCAL
#     build tree (byte-identical to HF pinned 497/497, wave-2). Column projection:
#     only the `year` column is scanned. REASONING: local == shipped bytes, so this
#     is the mirror's served row count without a multi-GB HTTP-parquet read.
#   * API hazard (hard-won): Urban intermittently serves slow-TRICKLE responses that
#     defeat socket timeouts. Guard every request with a signal.SIGALRM HARD wall-
#     clock deadline (~25s) [pattern from 38_boundary-years_b.py]; on deadline the
#     request is SKIPPED and recorded (verdict SKIP-HANG), sweep proceeds. Polite
#     ~1 req/sec pacing.
#   * Resumable: results checkpointed to 50_count_sweep_partial.parquet every 10
#     comparisons; a re-run loads it and skips already-done (label, year) cells.
#
# Read-only network GETs. No installs. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import json
import signal
import time
import urllib.request
import urllib.error
from pathlib import Path
import polars as pl

PROJECT_DIR = Path("/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update")
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
IN_PAIRS = OUT_DIR / "49_laneB_pairs.parquet"
PARTIAL = OUT_DIR / "50_count_sweep_partial.parquet"
FINAL = OUT_DIR / "50_laneB_count_sweep.parquet"
BASE = "https://educationdata.urban.org"
UA = {"User-Agent": "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)",
      "Accept": "application/json"}


# --- Hard wall-clock guard (SIGALRM) — pattern from 38_boundary-years_b.py ---
class _HardTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _HardTimeout("wall-clock deadline exceeded")


signal.signal(signal.SIGALRM, _alarm_handler)
HARD_DEADLINE = 25  # real seconds per attempt; catches slow-trickle that socket timeout misses


def api_count(url, retries=2):
    # INTENT: return (count, note). Each attempt bounded by BOTH socket timeout AND a
    #   SIGALRM hard deadline so no attempt can hang the sweep.
    last = ""
    for attempt in range(1, retries + 1):
        signal.alarm(HARD_DEADLINE)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return (data.get("count") if isinstance(data, dict) else None), ""
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code}"
        except _HardTimeout as e:
            return None, f"SKIP-HANG: {e}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            last = f"{type(e).__name__}: {repr(e)[:60]}"
            time.sleep(2 ** attempt)
        finally:
            signal.alarm(0)
    return None, f"CONN_ERROR: {last}"


# --- Load pairs + any prior checkpoint (resume) ---
pairs = pl.read_parquet(IN_PAIRS)
print(f"Loaded {pairs.height} pairs; total planned comparisons = "
      f"{int(pairs.select(pl.col('sweep_years').list.len().sum()).item())}")

done = {}
# RESUME-RETRY FIX (50_a): only DEFINITIVE verdicts count as "done" on resume.
# INTENT: transient live-API failures (SKIP-HANG, UNVERIFIABLE-TODAY) must be
#   RE-PROBED on a re-run, not skipped.
# REASONING: the prior logic loaded every checkpoint row into the done-set, so a
#   cell that failed only because the API was flaky was permanently frozen as
#   unverifiable across re-runs — defeating the whole point of a resumable sweep.
# ASSUMES: MATCH / MISMATCH are true mirror-vs-API outcomes and UNVERIFIABLE
#   (mirror file has no year column) is a structural fact — none of these change
#   on retry, so they stay in the done-set to avoid needless re-probing.
DEFINITIVE = {"MATCH", "MISMATCH", "UNVERIFIABLE"}
if PARTIAL.exists():
    prev = pl.read_parquet(PARTIAL)
    n_retry = 0
    for r in prev.iter_rows(named=True):
        if r["verdict"] in DEFINITIVE:
            done[(r["label"], r["route_template"], r["year"])] = r
        else:
            n_retry += 1  # non-definitive -> excluded from done-set, will retry
    print(f"Resume: {len(done)} DEFINITIVE comparisons kept; {n_retry} non-definitive will retry")

# Cache mirror year-count columns per file (scan once, group_by year).
mirror_year_counts = {}


def mirror_count_for(mirror_rel, year):
    if mirror_rel not in mirror_year_counts:
        lf = pl.scan_parquet(TREE_DIR / mirror_rel)
        names = [n.lower() for n in lf.collect_schema().names()]
        if "year" not in names:
            mirror_year_counts[mirror_rel] = None
        else:
            # map year(int) -> count, projecting only `year`
            gc = (lf.select(pl.col("year").cast(pl.Int64, strict=False))
                    .group_by("year").len().collect())
            mirror_year_counts[mirror_rel] = {row["year"]: row["len"] for row in gc.iter_rows(named=True)}
    m = mirror_year_counts[mirror_rel]
    if m is None:
        return None
    return m.get(year, 0)


# --- Sweep ---
results = list(done.values())
n_new = 0
for p in pairs.iter_rows(named=True):
    label, rt, mrel = p["label"], p["route_template"], p["mirror_rel"]
    for year in p["sweep_years"]:
        kkey = (label, rt, year)
        if kkey in done:
            continue
        url = f"{BASE}{rt.replace('{year}', str(year))}?limit=1"
        api_c, note = api_count(url)
        mir_c = mirror_count_for(mrel, year)
        if api_c is None:
            verdict = "SKIP" if note.startswith("SKIP-HANG") else "UNVERIFIABLE-TODAY"
        elif mir_c is None:
            verdict = "UNVERIFIABLE"
            note = "mirror file has no year column"
        elif api_c == mir_c:
            verdict = "MATCH"
        else:
            verdict = "MISMATCH"
        rec = {"label": label, "route_template": rt, "source": p["source"], "level": p["level"],
               "mirror_rel": mrel, "year": year, "api_count": api_c, "mirror_count": mir_c,
               "diff_mirror_minus_api": (mir_c - api_c) if (api_c is not None and mir_c is not None) else None,
               "verdict": verdict, "note": note}
        results.append(rec)
        done[kkey] = rec
        n_new += 1
        print(f"[{label:40s} {year}] {verdict:18s} api={api_c} mirror={mir_c} {note}")
        # incremental checkpoint every 10 new comparisons (resumable)
        if n_new % 10 == 0:
            pl.from_dicts(results).write_parquet(PARTIAL)
        time.sleep(1.1)  # polite ~1 req/sec pacing

# --- Persist final + summary ---
res_df = pl.from_dicts(results)
res_df.write_parquet(PARTIAL)
res_df.write_parquet(FINAL)

print("\n=== COUNT SWEEP SUMMARY ===")
print(res_df.group_by("verdict").len().sort("verdict"))
n_total = res_df.height
n_match = res_df.filter(pl.col("verdict") == "MATCH").height
n_mis = res_df.filter(pl.col("verdict") == "MISMATCH").height
print(f"MATCH={n_match}/{n_total}  MISMATCH={n_mis}  "
      f"other={n_total - n_match - n_mis}")
print(f"distinct sources: {sorted(res_df['source'].unique().to_list())}")

if n_mis:
    print("\n--- MISMATCHES (verbatim; classify grain-artifact vs substantive in report) ---")
    for r in res_df.filter(pl.col("verdict") == "MISMATCH").sort("label", "year").iter_rows(named=True):
        ratio = (r["mirror_count"] / r["api_count"]) if r["api_count"] else None
        print(f"  [{r['label']} {r['year']}] api={r['api_count']} mirror={r['mirror_count']} "
              f"diff={r['diff_mirror_minus_api']} ratio(mir/api)={ratio:.3f}" if ratio else
              f"  [{r['label']} {r['year']}] api={r['api_count']} mirror={r['mirror_count']}")

# --- Validate ---
assert n_total > 0, "No comparisons produced"
print(f"\nSaved -> {FINAL}")
print("COUNT SWEEP COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-08 20:13:33
# Command: python3 /daaf/scripts/mirror_maintenance/50_laneB-count-sweep_a_a_a.py
# Duration: 4s
# Exit code: 0
#
# --- STDOUT ---
# Loaded 54 pairs; total planned comparisons = 159
# Resume: 157 DEFINITIVE comparisons kept; 2 non-definitive will retry
# [ipeds_outcome_measures                   2015] MATCH              api=31917 mirror=31917 
# [scorecard_institutional_characteristics  1996] MATCH              api=7007 mirror=7007 
# 
# === COUNT SWEEP SUMMARY ===
# shape: (1, 2)
# ┌─────────┬─────┐
# │ verdict ┆ len │
# │ ---     ┆ --- │
# │ str     ┆ u32 │
# ╞═════════╪═════╡
# │ MATCH   ┆ 159 │
# └─────────┴─────┘
# MATCH=159/159  MISMATCH=0  other=0
# distinct sources: ['campus-crime', 'ccd', 'crdc', 'eada', 'fsa', 'ipeds', 'meps', 'nacubo', 'nccs', 'nhgis', 'saipe', 'scorecard']
# 
# Saved -> /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/50_laneB_count_sweep.parquet
# COUNT SWEEP COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
