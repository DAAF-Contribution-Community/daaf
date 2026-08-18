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
# Executed: 2026-08-08 19:47:13
# Command: python3 /daaf/scripts/mirror_maintenance/50_laneB-count-sweep_a.py
# Duration: 1417s
# Exit code: 0
#
# --- STDOUT ---
# Loaded 54 pairs; total planned comparisons = 159
# Resume: 17 DEFINITIVE comparisons kept; 13 non-definitive will retry
# [ipeds_directory                          1980] MATCH              api=3675 mirror=3675 
# [ccd_directory                            1986] MATCH              api=85288 mirror=85288 
# [ccd_directory                            2005] MATCH              api=102454 mirror=102454 
# [ccd_directory                            2024] MATCH              api=102178 mirror=102178 
# [ccd_directory                            1986] MATCH              api=17051 mirror=17051 
# [ccd_directory                            2005] MATCH              api=18213 mirror=18213 
# [ccd_directory                            2024] MATCH              api=19636 mirror=19636 
# [ipeds_institutional_characteristics      1980] MATCH              api=3675 mirror=3675 
# [ipeds_institutional_characteristics      2024] MATCH              api=5963 mirror=5963 
# [ccd_finance                              1991] MATCH              api=16229 mirror=16229 
# [ccd_finance                              2020] MATCH              api=19554 mirror=19554 
# [crdc_directory                           2011] MATCH              api=95635 mirror=95635 
# [crdc_directory                           2021] MATCH              api=98010 mirror=98010 
# [ipeds_academic_year_room_board_other     1999] MATCH              api=11024 mirror=11024 
# [ipeds_academic_year_room_board_other     2011] MATCH              api=12881 mirror=12881 
# [ipeds_academic_year_room_board_other     2023] MATCH              api=11475 mirror=11475 
# [saipe_base                               1995] MATCH              api=14468 mirror=14468 
# [saipe_base                               2011] MATCH              api=13545 mirror=13545 
# [saipe_base                               2024] MATCH              api=13132 mirror=13132 
# [ipeds_program_year_tuition_cip           1987] MATCH              api=8725 mirror=8725 
# [ipeds_program_year_tuition_cip           2005] MATCH              api=7886 mirror=7886 
# [ipeds_program_year_tuition_cip           2023] MATCH              api=7953 mirror=7953 
# [ipeds_program_year_room_board_other      1999] MATCH              api=2252 mirror=2252 
# [ipeds_program_year_room_board_other      2011] MATCH              api=5316 mirror=5316 
# [ipeds_program_year_room_board_other      2023] MATCH              api=4250 mirror=4250 
# [crdc_discipline_instances                2015] MATCH              api=481800 mirror=481800 
# [crdc_discipline_instances                2020] MATCH              api=585450 mirror=585450 
# [crdc_discipline_instances                2021] MATCH              api=588060 mirror=588060 
# [ipeds_fall_retention                     2003] MATCH              api=12162 mirror=12162 
# [ipeds_fall_retention                     2014] MATCH              api=14100 mirror=14100 
# [ipeds_fall_retention                     2024] MATCH              api=11156 mirror=11156 
# [ipeds_finance                            1979] MATCH              api=3189 mirror=3189 
# [ipeds_finance                            2000] UNVERIFIABLE-TODAY api=None mirror=9769 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [ipeds_finance                            2017] MATCH              api=6857 mirror=6857 
# [ipeds_student_faculty_ratio              2009] MATCH              api=6672 mirror=6672 
# [ipeds_student_faculty_ratio              2017] MATCH              api=6371 mirror=6371 
# [ipeds_student_faculty_ratio              2024] MATCH              api=5578 mirror=5578 
# [ipeds_sfa_grants_and_net_price           2008] MATCH              api=44211 mirror=44211 
# [ipeds_sfa_grants_and_net_price           2015] MATCH              api=42215 mirror=42215 
# [ipeds_sfa_grants_and_net_price           2021] MATCH              api=37009 mirror=37009 
# [ipeds_sfa_by_living_arrangement          2008] MATCH              api=63184 mirror=63184 
# [ipeds_sfa_by_living_arrangement          2015] MATCH              api=51988 mirror=51988 
# [ipeds_sfa_by_living_arrangement          2021] MATCH              api=45994 mirror=45994 
# [ipeds_sfa_by_tuition_type                1999] MATCH              api=14285 mirror=14285 
# [ipeds_sfa_by_tuition_type                2010] MATCH              api=14985 mirror=14985 
# [ipeds_sfa_by_tuition_type                2021] MATCH              api=16206 mirror=16206 
# [ipeds_sfa_all_undergraduates             2007] MATCH              api=13048 mirror=13048 
# [ipeds_sfa_all_undergraduates             2014] MATCH              api=20877 mirror=20877 
# [ipeds_sfa_all_undergraduates             2021] MATCH              api=17127 mirror=17127 
# [ipeds_sfa_ftft                           1999] MATCH              api=26999 mirror=26999 
# [ipeds_sfa_ftft                           2010] MATCH              api=75284 mirror=75284 
# [ipeds_sfa_ftft                           2021] MATCH              api=59939 mirror=59939 
# [ipeds_grad_rates                         1996] MATCH              api=191850 mirror=191850 
# [ipeds_grad_rates                         2010] MATCH              api=233463 mirror=233463 
# [ipeds_grad_rates                         2023] MATCH              api=200675 mirror=200675 
# [ipeds_grad_rates_200pct                  2007] MATCH              api=5605 mirror=5605 
# [ipeds_grad_rates_200pct                  2015] MATCH              api=5652 mirror=5652 
# [ipeds_grad_rates_200pct                  2023] MATCH              api=4838 mirror=4838 
# [ipeds_grad_rates_pell                    2015] MATCH              api=44188 mirror=44188 
# [ipeds_grad_rates_pell                    2019] MATCH              api=40300 mirror=40300 
# [ipeds_grad_rates_pell                    2023] MATCH              api=38832 mirror=38832 
# [ipeds_outcome_measures                   2015] UNVERIFIABLE-TODAY api=None mirror=31917 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [ipeds_outcome_measures                   2018] MATCH              api=89756 mirror=89756 
# [ipeds_outcome_measures                   2021] MATCH              api=88550 mirror=88550 
# [ipeds_completers                         2011] MATCH              api=223440 mirror=223440 
# [ipeds_completers                         2016] MATCH              api=202620 mirror=202620 
# [ipeds_completers                         2021] MATCH              api=181620 mirror=181620 
# [ipeds_academic_libraries                 2013] MATCH              api=4271 mirror=4271 
# [ipeds_academic_libraries                 2018] MATCH              api=3834 mirror=3834 
# [ipeds_academic_libraries                 2023] MATCH              api=3652 mirror=3652 
# [ipeds_salaries_instructional_staff       1980] MATCH              api=52602 mirror=52602 
# [ipeds_salaries_instructional_staff       2005] MATCH              api=114273 mirror=114273 
# [ipeds_salaries_instructional_staff       2024] MATCH              api=365184 mirror=365184 
# [ipeds_salaries_noninstructional_staff    2012] MATCH              api=67956 mirror=67956 
# [ipeds_salaries_noninstructional_staff    2018] MATCH              api=58688 mirror=58688 
# [ipeds_salaries_noninstructional_staff    2024] MATCH              api=54796 mirror=54796 
# [crdc_teachers_staff                      2011] MATCH              api=95635 mirror=95635 
# [crdc_teachers_staff                      2017] MATCH              api=97632 mirror=97632 
# [crdc_teachers_staff                      2021] MATCH              api=98010 mirror=98010 
# [scorecard_institutional_characteristics  1996] UNVERIFIABLE-TODAY api=None mirror=7007 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [scorecard_institutional_characteristics  2008] MATCH              api=7055 mirror=7055 
# [scorecard_institutional_characteristics  2020] MATCH              api=6681 mirror=6681 
# [scorecard_earnings                       2003] MATCH              api=6189 mirror=6189 
# [scorecard_earnings                       2009] UNVERIFIABLE-TODAY api=None mirror=19661 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [scorecard_earnings                       2018] MATCH              api=16761 mirror=16761 
# [scorecard_default                        1996] MATCH              api=6249 mirror=6249 
# [scorecard_default                        2008] MATCH              api=6574 mirror=6574 
# [scorecard_default                        2020] MATCH              api=5779 mirror=5779 
# [scorecard_repayment                      2007] MATCH              api=5986 mirror=5986 
# [scorecard_repayment                      2012] MATCH              api=20191 mirror=20191 
# [scorecard_repayment                      2016] MATCH              api=18325 mirror=18325 
# [crdc_offenses                            2015] MATCH              api=94652 mirror=94652 
# [crdc_offenses                            2020] MATCH              api=97575 mirror=97575 
# [crdc_offenses                            2021] MATCH              api=98010 mirror=98010 
# [nhgis_census_2020                        1980] MATCH              api=3664 mirror=3664 
# [nhgis_census_2020                        2003] MATCH              api=7024 mirror=7024 
# [nhgis_census_2020                        2023] MATCH              api=6163 mirror=6163 
# [fsa_financial_responsibility             2006] MATCH              api=3150 mirror=3150 
# [fsa_financial_responsibility             2011] MATCH              api=3401 mirror=3401 
# [fsa_financial_responsibility             2016] MATCH              api=3627 mirror=3627 
# [fsa_grants                               1999] MATCH              api=25730 mirror=25730 
# [fsa_grants                               2010] MATCH              api=27665 mirror=27665 
# [fsa_grants                               2021] MATCH              api=24600 mirror=24600 
# [crdc_credit_recovery                     2015] MATCH              api=96360 mirror=96360 
# [crdc_credit_recovery                     2017] MATCH              api=97632 mirror=97632 
# [fsa_loans                                1999] MATCH              api=65842 mirror=65842 
# [fsa_loans                                2010] MATCH              api=73724 mirror=73724 
# [fsa_loans                                2021] MATCH              api=64540 mirror=64540 
# [fsa_campus_based_volume                  2001] MATCH              api=12051 mirror=12051 
# [fsa_campus_based_volume                  2011] MATCH              api=12318 mirror=12318 
# [fsa_campus_based_volume                  2021] MATCH              api=10863 mirror=10863 
# [fsa_90_10_revenue_percentages            2014] MATCH              api=1909 mirror=1909 
# [fsa_90_10_revenue_percentages            2018] MATCH              api=1671 mirror=1671 
# [fsa_90_10_revenue_percentages            2021] MATCH              api=1626 mirror=1626 
# [nacubo_endowments                        2012] MATCH              api=813 mirror=813 
# [nacubo_endowments                        2017] MATCH              api=776 mirror=776 
# [nacubo_endowments                        2022] MATCH              api=664 mirror=664 
# [crdc_offerings                           2011] UNVERIFIABLE-TODAY api=None mirror=95635 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [crdc_offerings                           2017] UNVERIFIABLE-TODAY api=None mirror=97632 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [crdc_offerings                           2021] UNVERIFIABLE-TODAY api=None mirror=98010 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [nccs_990_forms                           1993] MATCH              api=661 mirror=661 
# [nccs_990_forms                           2005] MATCH              api=1348 mirror=1348 
# [nccs_990_forms                           2016] MATCH              api=1561 mirror=1561 
# [crdc_school_finance                      2011] MATCH              api=95635 mirror=95635 
# [crdc_school_finance                      2015] MATCH              api=96360 mirror=96360 
# [crdc_school_finance                      2017] MATCH              api=97632 mirror=97632 
# [eada_institutional_characteristics       2002] MATCH              api=1968 mirror=1968 
# [eada_institutional_characteristics       2012] MATCH              api=2090 mirror=2090 
# [eada_institutional_characteristics       2021] MATCH              api=2028 mirror=2028 
# [campus-crime_hate_crimes                 2005] MATCH              api=86980 mirror=86980 
# [campus-crime_hate_crimes                 2013] MATCH              api=911365 mirror=911365 
# [campus-crime_hate_crimes                 2021] MATCH              api=1344042 mirror=1344042 
# [crdc_covid_indicators                    2020] MATCH              api=97575 mirror=97575 
# [crdc_covid_indicators                    2021] MATCH              api=98010 mirror=98010 
# [crdc_internet_access                     2020] MATCH              api=97575 mirror=97575 
# [crdc_internet_access                     2021] MATCH              api=98010 mirror=98010 
# [meps_base                                2009] MATCH              api=97555 mirror=97555 
# [meps_base                                2016] MATCH              api=96153 mirror=96153 
# [meps_base                                2022] MATCH              api=94941 mirror=94941 
# [nhgis_census_2020                        1986] MATCH              api=83415 mirror=83415 
# [nhgis_census_2020                        2005] UNVERIFIABLE-TODAY api=None mirror=102327 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# [nhgis_census_2020                        2023] UNVERIFIABLE-TODAY api=None mirror=102274 CONN_ERROR: TimeoutError: TimeoutError('The read operation timed out')
# 
# === COUNT SWEEP SUMMARY ===
# shape: (2, 2)
# ┌────────────────────┬─────┐
# │ verdict            ┆ len │
# │ ---                ┆ --- │
# │ str                ┆ u32 │
# ╞════════════════════╪═════╡
# │ MATCH              ┆ 150 │
# │ UNVERIFIABLE-TODAY ┆ 9   │
# └────────────────────┴─────┘
# MATCH=150/159  MISMATCH=0  other=9
# distinct sources: ['campus-crime', 'ccd', 'crdc', 'eada', 'fsa', 'ipeds', 'meps', 'nacubo', 'nccs', 'nhgis', 'saipe', 'scorecard']
# 
# Saved -> /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-07_urban-fidelity/50_laneB_count_sweep.parquet
# COUNT SWEEP COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
