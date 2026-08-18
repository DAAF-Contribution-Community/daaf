#!/usr/bin/env python3
# =============================================================================
# 51_laneB-value-slices.py  (Lane B EXPANSION — deep per-state value slices)
# =============================================================================
# INTENT: For each slice-flagged pair from 49_a (~35 slices across 12 sources),
#   pull ONE state slice (DC, fips=11) at the pair's slice_year from BOTH the live
#   Urban API and the v2 mirror, align on the primary key (auto-augmented to
#   uniqueness where a lone id is not unique per year+state), and compare every
#   shared column CELL-BY-CELL after representation-robust normalization. Any
#   residual mismatch after documented benign normalization is reported VERBATIM
#   with keys and classified (benign-representation vs substantive) in the report.
#
# NORMALIZATION (reused verbatim engine from 21_laneB-value-slices_a_a.py, proven):
#   * Missing unified: null, "", coded {-1,-2,-3} -> single sentinel.
#   * IDs: ncessch->12 / leaid->7 zero-padded; unitid/crdc_id canonical string.
#   * Numeric: tolerance compare |a-b| <= max(0.01, 1e-4*|v|) (benign precision,
#     incl. the known API-side rounding class e.g. ccd teachers_fte, is not failed).
#   * Column-name casing lowercased both sides.
#
# KEY AUGMENTATION: if key_col is not unique per (year, fips) on either side, greedily
#   add shared disaggregation/type columns (grant_type, sex, race, cohort, ...) until
#   unique; if still not unique, record GRAIN note and skip the cell compare (count
#   parity for that pair is still covered by the sweep, script 50).
#
# API hazard: SIGALRM hard wall-clock guard (25s/request) [38_boundary-years_b.py];
#   polite ~1 req/sec; skip-on-hang recorded. Resumable: per-slice checkpoint.
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
PARTIAL = OUT_DIR / "51_value_slices_partial.parquet"
FINAL = OUT_DIR / "51_laneB_value_slices.parquet"
EX_FINAL = OUT_DIR / "51_laneB_value_mismatch_examples.parquet"
BASE = "https://educationdata.urban.org/api/v1"
UA = {"User-Agent": "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)",
      "Accept": "application/json"}
FIPS = 11  # DC — small slice; also stress-tests leading-zero ids elsewhere handled

MISS = "<NA>"
MISSING_TOKENS = {"-1", "-2", "-3", "", "-1.0", "-2.0", "-3.0"}
PAD = {"ncessch": 12, "leaid": 7}
# candidate disaggregation/type columns to augment a non-unique primary key
AUG_KEYS = ["grant_type", "loan_type", "sex", "race", "cohort", "cohort_years",
            "ftpt", "sector", "class_level", "disability", "lep", "cip_code",
            "cipcode", "award_level", "level_of_study", "living_arrangement",
            "tuition_type", "endowment_type", "crime_type", "offense", "program"]


# --- SIGALRM hard wall-clock guard (pattern from 38_boundary-years_b.py) ---
class _HardTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _HardTimeout("wall-clock deadline exceeded")


signal.signal(signal.SIGALRM, _alarm_handler)
HARD_DEADLINE = 25


def api_get_all(url, max_pages=60):
    # INTENT: fetch all pages of a slice, each request hard-bounded by SIGALRM.
    rows, count, pages, nxt = [], None, 0, url
    while nxt and pages < max_pages:
        got = None
        for attempt in range(1, 3):
            signal.alarm(HARD_DEADLINE)
            try:
                req = urllib.request.Request(nxt, headers=UA)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    got = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                return rows, count, f"HTTP {e.code}"
            except _HardTimeout as e:
                return rows, count, f"SKIP-HANG: {e}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
                if attempt == 2:
                    return rows, count, f"unreachable: {repr(e)[:60]}"
                time.sleep(2 ** attempt)
            finally:
                signal.alarm(0)
        if got is None:
            return rows, count, "no response"
        if count is None:
            count = got.get("count")
        rows.extend(got.get("results", []))
        nxt = got.get("next")
        pages += 1
        time.sleep(0.8)
    return rows, count, None


# --- normalize_frame engine (verbatim behavior from 21_a_a) ---
def str_missing_expr(col):
    return pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars().is_in(list(MISSING_TOKENS)) | \
           pl.col(col).is_null()


def normalize_frame(df):
    out = {}
    schema_str = {}
    for c in df.columns:
        miss = df.select(str_missing_expr(c).alias("m"))["m"]
        s = df[c].cast(pl.Utf8, strict=False).str.strip_chars()
        if c in PAD:
            padded = (pl.when(str_missing_expr(c)).then(pl.lit(None))
                      .otherwise(pl.col(c).cast(pl.Utf8).str.replace(r"\.0$", "").str.zfill(PAD[c])))
            out[c] = df.select(padded.alias(c))[c]
            schema_str[c] = "id"
            continue
        non_missing = s.filter(~miss)
        numeric = non_missing.len() > 0 and non_missing.cast(pl.Float64, strict=False).null_count() == 0
        if numeric:
            val = (pl.when(str_missing_expr(c)).then(pl.lit(None)).otherwise(pl.col(c).cast(pl.Float64, strict=False)))
            out[c] = df.select(val.alias(c))[c]
            schema_str[c] = "num"
        else:
            val = (pl.when(str_missing_expr(c)).then(pl.lit(MISS)).otherwise(s))
            out[c] = df.select(val.alias(c))[c]
            schema_str[c] = "str"
    return pl.DataFrame(out), schema_str


def keyexpr(df, keys):
    parts = [df[k].cast(pl.Utf8).fill_null("<NA>") for k in keys]
    out = parts[0]
    for p in parts[1:]:
        out = out + "|" + p
    return out


def augment_keys(api, mir, base_key):
    # INTENT: return a key list unique on BOTH sides; greedily add shared AUG_KEYS.
    keys = [base_key]
    shared_aug = [c for c in AUG_KEYS if c in api.columns and c in mir.columns]

    def unique_both(ks):
        ak = api.select([pl.col(k).cast(pl.Utf8).fill_null("<NA>") for k in ks]).n_unique() == api.height
        mk = mir.select([pl.col(k).cast(pl.Utf8).fill_null("<NA>") for k in ks]).n_unique() == mir.height
        return ak and mk
    if unique_both(keys):
        return keys, True
    for c in shared_aug:
        keys.append(c)
        if unique_both(keys):
            return keys, True
    return keys, unique_both(keys)


def compare_slice(p):
    label, rt, mrel = p["label"], p["route_template"], p["mirror_rel"]
    year, base_key = p["slice_year"], p["key_col"]
    rec = {"label": label, "source": p["source"], "mirror_rel": mrel, "slice_year": year,
           "base_key": base_key, "keys_used": "", "n_keys": 0, "cols_compared": 0,
           "cols_mismatch": 0, "cell_mismatch": 0, "verdict": "", "note": ""}
    mf = TREE_DIR / mrel
    if not mf.exists():
        rec["verdict"] = "UNVERIFIABLE"; rec["note"] = "mirror missing"; return rec, []

    url = f"{BASE}{rt.replace('/api/v1', '').replace('{year}', str(year))}?fips={FIPS}"
    api_rows, api_count, err = api_get_all(url)
    if err or not api_rows:
        rec["verdict"] = "SKIP" if (err and "SKIP-HANG" in err) else "UNVERIFIABLE-TODAY"
        rec["note"] = f"API: {err or 'empty'}"; return rec, []
    api = pl.from_dicts(api_rows).rename(lambda c: c.lower())

    lf = pl.scan_parquet(mf)
    names = [c.lower() for c in lf.collect_schema().names()]
    m = lf.rename({c: c.lower() for c in lf.collect_schema().names()})
    preds = [pl.col("year").cast(pl.Int64, strict=False) == year] if "year" in names else []
    if "fips" in names:
        preds.append(pl.col("fips").cast(pl.Int64, strict=False) == FIPS)
    else:
        rec["verdict"] = "UNVERIFIABLE"; rec["note"] = "mirror has no fips column"; return rec, []
    mir = m.filter(pl.all_horizontal(preds)).collect()

    if base_key not in api.columns or base_key not in mir.columns:
        rec["verdict"] = "UNVERIFIABLE"; rec["note"] = f"key {base_key} absent one side"; return rec, []

    keys, uniq = augment_keys(api, mir, base_key)
    rec["keys_used"] = "+".join(keys)
    if not uniq:
        rec["verdict"] = "UNVERIFIABLE-GRAIN"
        rec["note"] = f"key not unique after augment; api_rows={api.height} mir_rows={mir.height}"
        return rec, []

    shared = [c for c in api.columns if c in mir.columns and c not in keys]
    rec["cols_compared"] = len(shared)
    api_n, _ = normalize_frame(api.select(keys + shared))
    mir_n, sch = normalize_frame(mir.select(keys + shared))
    api_n = api_n.with_columns(keyexpr(api_n, keys).alias("__k"))
    mir_n = mir_n.with_columns(keyexpr(mir_n, keys).alias("__k"))
    joined = api_n.join(mir_n, on="__k", how="inner", suffix="__mir")
    rec["n_keys"] = joined.height
    if joined.height == 0:
        rec["verdict"] = "UNVERIFIABLE"; rec["note"] = "no overlapping keys"; return rec, []

    examples = []
    cols_mm = cell_mm = 0
    for c in shared:
        mc = f"{c}__mir"
        if mc not in joined.columns:
            continue
        kind = sch.get(c, "str")
        if kind == "num":
            a = joined[c].cast(pl.Float64, strict=False)
            b = joined[mc].cast(pl.Float64, strict=False)
            tol = pl.max_horizontal(pl.lit(0.01), (b.abs() * 1e-4))
            both_null = a.is_null() & b.is_null()
            one_null = a.is_null() ^ b.is_null()
            close = (a - b).abs() <= tol
            bad = one_null | (~both_null & ~one_null & ~close)
            diff = joined.filter(bad)
        else:
            diff = joined.filter(joined[c].cast(pl.Utf8) != joined[mc].cast(pl.Utf8))
        if diff.height:
            cols_mm += 1
            cell_mm += diff.height
            for r in diff.head(3).iter_rows(named=True):
                examples.append({"label": label, "key": str(r["__k"]), "column": c,
                                 "kind": kind, "api_value": str(r[c]), "mirror_value": str(r[mc])})
    rec["cols_mismatch"] = cols_mm
    rec["cell_mismatch"] = cell_mm
    rec["verdict"] = "MATCH" if cell_mm == 0 else "MISMATCH"
    return rec, examples


# --- Load pairs (slice-flagged only) + resume ---
pairs = pl.read_parquet(IN_PAIRS).filter(pl.col("slice_flag"))
print(f"Slice-flagged pairs: {pairs.height}")

done_labels = set()
prior_recs, prior_ex = [], []
if PARTIAL.exists():
    prev = pl.read_parquet(PARTIAL)
    prior_recs = prev.to_dicts()
    done_labels = set((r["label"], r["slice_year"]) for r in prior_recs)
    if EX_FINAL.exists():
        prior_ex = pl.read_parquet(EX_FINAL).to_dicts()
    print(f"Resume: {len(done_labels)} slices already done")

recs, examples = list(prior_recs), list(prior_ex)
n_new = 0
for p in pairs.iter_rows(named=True):
    if (p["label"], p["slice_year"]) in done_labels:
        continue
    rec, ex = compare_slice(p)
    recs.append(rec)
    examples.extend(ex)
    n_new += 1
    print(f"[{rec['label']:40s} {rec['slice_year']}] {rec['verdict']:18s} "
          f"keys={rec['n_keys']} cols={rec['cols_compared']} colMM={rec['cols_mismatch']} "
          f"cellMM={rec['cell_mismatch']} keyset={rec['keys_used']} {rec['note']}")
    if n_new % 5 == 0:
        pl.from_dicts(recs).write_parquet(PARTIAL)
        if examples:
            pl.from_dicts(examples).write_parquet(EX_FINAL)

# --- Persist + summary ---
res_df = pl.from_dicts(recs)
res_df.write_parquet(PARTIAL)
res_df.write_parquet(FINAL)
if examples:
    pl.from_dicts(examples).write_parquet(EX_FINAL)

print("\n=== VALUE SLICE SUMMARY ===")
print(res_df.group_by("verdict").len().sort("verdict"))
n_match = res_df.filter(pl.col("verdict") == "MATCH").height
print(f"MATCH={n_match}/{res_df.height} slices; distinct sources={sorted(res_df['source'].unique().to_list())}")

if examples:
    print("\n--- RESIDUAL MISMATCH EXAMPLES (verbatim, capped 60) ---")
    for e in examples[:60]:
        print(f"  [{e['label']}] key={e['key']} col={e['column']}({e['kind']}) "
              f"api={e['api_value']!r} mirror={e['mirror_value']!r}")

assert res_df.height > 0, "No slices produced"
print(f"\nSaved -> {FINAL}")
print("VALUE SLICES COMPLETE")
