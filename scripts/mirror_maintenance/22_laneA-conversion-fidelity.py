#!/usr/bin/env python3
# =============================================================================
# 22_laneA-conversion-fidelity.py
# =============================================================================
# INTENT: Lane A of the Urban-fidelity audit. Verify the v2 mirror's CSV->parquet
#   CONVERSION is faithful to Urban's own bulk CSVs (the ACTUAL build inputs),
#   cell-exact after documented normalization. Complements Lane B (live-API
#   serving-surface consistency, script 20/21). Primary question: does the bulk
#   CSV's ccd_directory.teachers_fte carry the SAME decimals as the mirror
#   (e.g. school 110000800382 -> 28.98), proving the Lane B API-vs-mirror gap
#   (API served 28.0) is API-side rounding, not a conversion defect?
#
# WHAT WE COMPARE: for each of 6 stratified targets we re-download the current
#   Urban bulk CSV and compare it against the corresponding LOCAL mirror parquet.
#   REASONING (mirror equivalence): the local build tree mirror_v2_tree/ is proven
#   byte-identical to the pinned HF revision (497/497 sha256, wave-2 remote
#   validation), so comparing against the local parquet == comparing against the
#   shipped mirror, and saves re-downloading ~200MB of parquet from HF.
#
# METHOD (per target):
#   1. Download bulk CSV (resumable HTTP Range; 5 retries w/ exponential backoff;
#      polite pacing; 120s+ timeouts). Completeness checked vs recorded/HEAD
#      Content-Length. Cumulative download cap 2.5 GB.
#   2. Read CSV all-String (pl.read_csv infer_schema=False) = the CSV truth baseline.
#   3. Read the mirror parquet.
#   4. Classify EACH column off the AUTHORITATIVE MIRROR schema (not per-frame
#      inference) so both sides get the identical treatment:
#        - id   : columns named ncessch / leaid -> zero-pad to 12 / 7 (build contract)
#        - num  : mirror dtype is integer/float -> tolerance compare
#        - str  : everything else -> exact string compare
#   5. NORMALIZE both sides (each an analytic decision, mirroring the 21_a_a harness):
#        - Missing tokens {null, "", -1, -2, -3} -> unified missing sentinel.
#          REASONING: the drift battery proved null<->coded<->empty re-encoding is
#          the dominant BENIGN representation difference. ASSUMES these are never
#          legitimate values in the compared columns.
#        - id: strip a trailing ".0" (int->str artifact) then zfill; missing kept as
#          unified sentinel. REASONING: JSON/CSV/int round-trips drop leading zeros.
#        - num: cast Float64; tolerance |a-b| <= max(0.01, 1e-4*|v|). REASONING:
#          benign float text precision is not a defect; a real gap (28.0 vs 28.98) is.
#   6. COMPARE keyed on the natural key (composite w/ year). If keys are unique and
#      the key SETS are identical on both sides, sort-align and compare each shared
#      column positionally (full-column, every cell — no sampling). Else fall back to
#      a keyed inner join over the intersection and separately report set differences.
#      This is a FULL-COLUMN compare for every target incl. the 3.79M-row ccd file.
#   7. Also report row-count parity and column-set differences (CSV-only / mirror-only).
#   8. Any residual cell diff after normalization = a FINDING, reported verbatim w/ key.
#   9. teachers_fte adjudication: quote CSV vs mirror for the 3 Lane B keys.
#
# Read-only network GETs. No installs. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import urllib.request
import urllib.error
import time
import datetime
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OUT_DIR = PROJECT_DIR / "2026-08-07_urban-fidelity"
DL_DIR = PROJECT_DIR / "scripts" / "scratch" / "urban_fidelity"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DL_DIR.mkdir(parents=True, exist_ok=True)

CSV_BASE = "https://educationdata.urban.org/csv"
UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"
DOWNLOAD_CAP_BYTES = 2_600_000_000  # ~2.5 GB cumulative guard
MISSING_TOKENS = {"-1", "-2", "-3", "", "-1.0", "-2.0", "-3.0"}
MISS = "<NA>"
PAD = {"ncessch": 12, "leaid": 7}

# Stratified sample (per Lane B continuation recipe). csv_path -> {CSV_BASE}/{csv_path}.csv
# key_cols = natural grain key (composite with year where a single id repeats across years).
TARGETS = [
    # label, csv_path, mirror_rel, key_cols, stratum note
    ("ccd_directory", "ccd/schools_ccd_directory",
     "ccd/schools_ccd_directory.parquet", ["ncessch", "year"],
     "large K-12 (1.01GB) + resolves teachers_fte"),
    ("ipeds_sfr", "ipeds/colleges_ipeds_student-faculty-ratio",
     "ipeds/colleges_ipeds_student-faculty-ratio.parquet", ["unitid", "year"],
     "IPEDS + reference-schema-rebuilt"),
    ("saipe", "saipe/districts_saipe",
     "saipe/districts_saipe.parquet", ["leaid", "year"],
     "reference-schema-rebuilt (leaid int64 in mirror; zfill-7 case)"),
    ("meps", "meps/schools_meps",
     "meps/schools_meps.parquet", ["ncessch", "year"],
     "carried-forward; ncessch int64 in mirror (zfill-12 case)"),
    ("nacubo", "nacubo/colleges_nacubo_endow",
     "nacubo/colleges_nacubo_endow.parquet", ["unitid", "year"],
     "very small (7 cols)"),
    ("crdc_char", "crdc/schools_crdc_school_characteristics",
     "crdc/schools_crdc_school_characteristics.parquet", ["crdc_id", "year"],
     "heterogeneous id typing (crdc_id large_string)"),
]

# teachers_fte keys quoted in Lane B (DC schools) to adjudicate the one Lane B finding.
TFTE_KEYS = ["110000800382", "110000800478", "110000800479"]


# --- Download helper (resumable, retries, polite) ---
# INTENT: obtain the current bulk CSV; resume partial transfers via HTTP Range.
# REASONING: completeness checked vs expected Content-Length so a truncated transfer
#   is never converted/compared. ASSUMES Urban's S3 backend honors Range (206).
def head_content_length(url):
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as resp:
                cl = resp.headers.get("Content-Length")
                return int(cl) if cl else None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == 3:
                return None
            time.sleep(min(2 ** attempt, 20))
    return None


def download_csv(url, dest, expected_bytes):
    last_err = None
    for attempt in range(1, 6):
        if dest.exists() and expected_bytes is not None and dest.stat().st_size == expected_bytes:
            return True, None  # cached & complete
        resume_from = dest.stat().st_size if dest.exists() else 0
        headers = {"User-Agent": UA}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                mode = "ab" if (resume_from > 0 and resp.status == 206) else "wb"
                if mode == "wb":
                    resume_from = 0  # server ignored Range -> clean restart
                with open(dest, mode) as fh:
                    while True:
                        chunk = resp.read(1 << 20)  # 1 MB
                        if not chunk:
                            break
                        fh.write(chunk)
            if expected_bytes is None or dest.stat().st_size == expected_bytes:
                return True, None
            last_err = f"size {dest.stat().st_size} != expected {expected_bytes}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = repr(e)[:120]
        time.sleep(min(2 ** attempt, 20))  # backoff
    return False, last_err


# --- Normalization keyed off the authoritative mirror schema ---
# INTENT: yield, per column, a normalized comparable Series identical in treatment on
#   both CSV and mirror sides. REASONING: schema-driven (not per-frame inferred)
#   classification guarantees like-for-like. ASSUMES missing tokens never legitimate.
def classify(colname, mirror_dtype):
    if colname in PAD:
        return "id"
    if mirror_dtype in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                        pl.Float32, pl.Float64):
        return "num"
    return "str"


def missing_mask(df, col):
    return (df.select(
        (pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars().is_in(list(MISSING_TOKENS))
         | pl.col(col).is_null()).alias("m"))["m"])


def norm_col(df, col, kind):
    miss = pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars().is_in(list(MISSING_TOKENS)) \
        | pl.col(col).is_null()
    if kind == "id":
        expr = (pl.when(miss).then(pl.lit(MISS))
                .otherwise(pl.col(col).cast(pl.Utf8).str.replace(r"\.0$", "").str.zfill(PAD[col])))
        return df.select(expr.alias(col))[col]
    if kind == "num":
        expr = pl.when(miss).then(pl.lit(None)).otherwise(pl.col(col).cast(pl.Float64, strict=False))
        return df.select(expr.alias(col))[col]
    expr = pl.when(miss).then(pl.lit(MISS)).otherwise(pl.col(col).cast(pl.Utf8, strict=False).str.strip_chars())
    return df.select(expr.alias(col))[col]


def compare_target(label, csv_path, mirror_rel, key_cols, note):
    rec = {"label": label, "mirror_rel": mirror_rel, "csv_path": csv_path,
           "csv_rows": None, "mirror_rows": None, "row_match": None,
           "csv_only_cols": "", "mirror_only_cols": "", "shared_cols": 0,
           "keys_unique": None, "key_sets_equal": None, "compare_mode": "",
           "cols_mismatch": 0, "cell_mismatch": 0, "verdict": "", "detail": ""}
    examples = []

    mf = TREE_DIR / mirror_rel
    csv_fp = DL_DIR / f"{label}.csv"

    # --- Read CSV all-String (truth baseline) + mirror parquet ---
    csv = pl.read_csv(csv_fp, infer_schema=False)
    mir = pl.read_parquet(mf)
    rec["csv_rows"] = csv.height
    rec["mirror_rows"] = mir.height
    rec["row_match"] = (csv.height == mir.height)

    csv_cols = set(csv.columns)
    mir_cols = set(mir.columns)
    csv_only = sorted(csv_cols - mir_cols)
    mir_only = sorted(mir_cols - csv_cols)
    rec["csv_only_cols"] = "|".join(csv_only)
    rec["mirror_only_cols"] = "|".join(mir_only)

    # mirror is authoritative for column typing/classification
    mir_schema = dict(zip(mir.columns, mir.dtypes))
    shared = [c for c in mir.columns if c in csv_cols]  # keep mirror order
    keys = [k for k in key_cols if k in csv_cols and k in mir.columns]
    assert keys, f"{label}: no usable key among {key_cols}"
    value_cols = [c for c in shared if c not in keys]
    rec["shared_cols"] = len(value_cols)

    # --- Normalize both sides over shared columns ---
    def normalize(df):
        out = {}
        for c in shared:
            out[c] = norm_col(df, c, classify(c, mir_schema[c]))
        return pl.DataFrame(out)
    csv_n = normalize(csv)
    mir_n = normalize(mir)

    # --- Build composite key string ---
    def keyexpr(df):
        parts = [df[k].cast(pl.Utf8).fill_null(MISS) for k in keys]
        out = parts[0]
        for p in parts[1:]:
            out = out + "|" + p
        return out
    csv_n = csv_n.with_columns(keyexpr(csv_n).alias("__k"))
    mir_n = mir_n.with_columns(keyexpr(mir_n).alias("__k"))

    csv_uniq = csv_n["__k"].n_unique() == csv_n.height
    mir_uniq = mir_n["__k"].n_unique() == mir_n.height
    rec["keys_unique"] = bool(csv_uniq and mir_uniq)

    csv_keys = set(csv_n["__k"].to_list())
    mir_keys = set(mir_n["__k"].to_list())
    rec["key_sets_equal"] = (csv_keys == mir_keys)
    only_csv_k = len(csv_keys - mir_keys)
    only_mir_k = len(mir_keys - csv_keys)
    if only_csv_k or only_mir_k:
        rec["detail"] += f"[keys only-in-CSV={only_csv_k} only-in-mirror={only_mir_k}] "

    # --- Choose compare path ---
    if rec["keys_unique"] and rec["key_sets_equal"]:
        rec["compare_mode"] = "sort-align (full-column, every cell)"
        a = csv_n.sort("__k")
        b = mir_n.sort("__k")
        joined = a  # positional alignment; b columns referenced via b[...]
        get_b = {c: b[c] for c in shared}
        n_compared = a.height
        for c in value_cols:
            kind = classify(c, mir_schema[c])
            av = a[c]
            bv = get_b[c]
            if kind == "num":
                aa = av.cast(pl.Float64, strict=False)
                bb = bv.cast(pl.Float64, strict=False)
                tol = pl.max_horizontal(pl.lit(0.01), (bb.abs() * 1e-4))
                cmp = pl.DataFrame({"a": aa, "b": bb}).with_columns(tol.alias("tol"))
                both_null = cmp["a"].is_null() & cmp["b"].is_null()
                one_null = cmp["a"].is_null() ^ cmp["b"].is_null()
                close = (cmp["a"] - cmp["b"]).abs() <= cmp["tol"]
                bad_mask = one_null | (~both_null & ~one_null & ~close)
            else:
                bad_mask = av.cast(pl.Utf8) != bv.cast(pl.Utf8)
            nbad = int(bad_mask.sum())
            if nbad:
                rec["cols_mismatch"] += 1
                rec["cell_mismatch"] += nbad
                idx = [i for i, v in enumerate(bad_mask.to_list()) if v][:3]
                for i in idx:
                    examples.append({"label": label, "key": str(a["__k"][i]), "column": c,
                                     "kind": kind, "csv_value": str(av[i]), "mirror_value": str(bv[i])})
        rec["n_keys_compared"] = n_compared
    else:
        rec["compare_mode"] = "keyed-inner-join (intersection)"
        j = csv_n.join(mir_n, on="__k", how="inner", suffix="__mir")
        rec["n_keys_compared"] = j.height
        for c in value_cols:
            mc = f"{c}__mir"
            if mc not in j.columns:
                continue
            kind = classify(c, mir_schema[c])
            if kind == "num":
                aa = j[c].cast(pl.Float64, strict=False)
                bb = j[mc].cast(pl.Float64, strict=False)
                tol = pl.max_horizontal(pl.lit(0.01), (bb.abs() * 1e-4))
                cmp = pl.DataFrame({"a": aa, "b": bb}).with_columns(tol.alias("tol"))
                both_null = cmp["a"].is_null() & cmp["b"].is_null()
                one_null = cmp["a"].is_null() ^ cmp["b"].is_null()
                close = (cmp["a"] - cmp["b"]).abs() <= cmp["tol"]
                bad = j.filter(one_null | (~both_null & ~one_null & ~close))
            else:
                bad = j.filter(j[c].cast(pl.Utf8) != j[mc].cast(pl.Utf8))
            if bad.height:
                rec["cols_mismatch"] += 1
                rec["cell_mismatch"] += bad.height
                for r in bad.head(3).iter_rows(named=True):
                    examples.append({"label": label, "key": str(r["__k"]), "column": c,
                                     "kind": kind, "csv_value": str(r[c]), "mirror_value": str(r[mc])})

    rec["verdict"] = "MATCH" if (rec["cell_mismatch"] == 0 and rec["row_match"]
                                 and not csv_only and not mir_only) else (
        "MATCH*" if rec["cell_mismatch"] == 0 and rec["row_match"] else "MISMATCH")
    if rec["verdict"] == "MATCH*":
        rec["detail"] += "[values+rows exact; column-set differs - see cols]"
    return rec, examples


# --- Stage 1: plan downloads (size-probe unknown files, enforce cap) ---
print("=== LANE A: CONVERSION FIDELITY (bulk CSV vs mirror parquet) ===")
KNOWN_BYTES = {  # from build_provenance_fetched.parquet
    "ccd_directory": 1014405917,
    "ipeds_sfr": 1807729,
    "saipe": 32848756,
}
plan = []
cum = 0
for (label, csv_path, mirror_rel, keys, note) in TARGETS:
    url = f"{CSV_BASE}/{csv_path}.csv"
    exp = KNOWN_BYTES.get(label)
    if exp is None:
        exp = head_content_length(url)
        print(f"[head] {label}: content-length={exp}")
        time.sleep(1.0)
    plan.append((label, csv_path, url, mirror_rel, keys, note, exp))
    if exp:
        cum += exp
print(f"Planned cumulative download: {cum:,} bytes (cap {DOWNLOAD_CAP_BYTES:,})")
assert cum <= DOWNLOAD_CAP_BYTES, f"STOP: planned downloads {cum:,} exceed cap"

# --- Stage 2: download + compare each target ---
all_recs, all_examples = [], []
tfte_rows = []
downloaded_total = 0
for (label, csv_path, url, mirror_rel, keys, note, exp) in plan:
    print("\n" + "-" * 72)
    print(f"[{label}] {url}")
    dest = DL_DIR / f"{label}.csv"
    ok, err = download_csv(url, dest, exp)
    if not ok:
        print(f"  [FAIL download] {err}")
        all_recs.append({"label": label, "mirror_rel": mirror_rel, "csv_path": csv_path,
                         "verdict": "UNVERIFIABLE-TODAY", "detail": f"download: {err}",
                         "csv_rows": None, "mirror_rows": None, "row_match": None,
                         "csv_only_cols": "", "mirror_only_cols": "", "shared_cols": 0,
                         "keys_unique": None, "key_sets_equal": None, "compare_mode": "",
                         "cols_mismatch": 0, "cell_mismatch": 0})
        time.sleep(1.5)
        continue
    downloaded_total += dest.stat().st_size
    print(f"  [ok] CSV on disk: {dest.stat().st_size:,} B (cum {downloaded_total:,})")

    rec, ex = compare_target(label, csv_path, mirror_rel, keys, note)
    all_recs.append(rec)
    all_examples.extend(ex)
    print(f"  rows: csv={rec['csv_rows']:,} mirror={rec['mirror_rows']:,} match={rec['row_match']}")
    print(f"  cols: shared={rec['shared_cols']} csv_only=[{rec['csv_only_cols']}] mirror_only=[{rec['mirror_only_cols']}]")
    print(f"  mode={rec['compare_mode']} keysUnique={rec['keys_unique']} keySetsEqual={rec['key_sets_equal']}")
    print(f"  VERDICT={rec['verdict']} colMM={rec['cols_mismatch']} cellMM={rec['cell_mismatch']} {rec['detail']}")

    # teachers_fte adjudication (ccd only): quote CSV vs mirror for the 3 Lane B keys
    if label == "ccd_directory":
        csv = pl.read_csv(dest, infer_schema=False,
                          columns=["ncessch", "year", "teachers_fte"])
        mir = pl.read_parquet(TREE_DIR / mirror_rel, columns=["ncessch", "year", "teachers_fte"])
        for k in TFTE_KEYS:
            # CSV ncessch may lack leading zero; match on zfilled 12
            csv_hit = csv.with_columns(pl.col("ncessch").str.zfill(12).alias("nz")) \
                .filter((pl.col("nz") == k) & (pl.col("year").cast(pl.Utf8) == "2022"))
            mir_hit = mir.filter((pl.col("ncessch").cast(pl.Utf8).str.zfill(12) == k)
                                 & (pl.col("year") == 2022))
            cv = csv_hit["teachers_fte"][0] if csv_hit.height else "<absent>"
            mv = mir_hit["teachers_fte"][0] if mir_hit.height else "<absent>"
            tfte_rows.append({"ncessch": k, "year": 2022, "csv_teachers_fte": str(cv),
                              "mirror_teachers_fte": str(mv), "equal": str(cv) == str(mv)
                              or (cv != "<absent>" and mv != "<absent>"
                                  and abs(float(cv) - float(mv)) <= 0.01)})
            print(f"  [teachers_fte] ncessch={k} year=2022 CSV={cv!r} mirror={mv!r}")
    time.sleep(1.5)

# --- Save results ---
rec_df = pl.from_dicts(all_recs, infer_schema_length=None)
rec_df.write_parquet(OUT_DIR / "laneA_conversion_fidelity.parquet")
if all_examples:
    pl.from_dicts(all_examples).write_parquet(OUT_DIR / "laneA_mismatch_examples.parquet")
if tfte_rows:
    pl.from_dicts(tfte_rows).write_parquet(OUT_DIR / "laneA_teachers_fte_adjudication.parquet")

# --- Summary ---
print("\n=== LANE A SUMMARY ===")
print(rec_df.select("label", "verdict", "csv_rows", "mirror_rows", "row_match",
                    "shared_cols", "cols_mismatch", "cell_mismatch"))
n_match = rec_df.filter(pl.col("verdict").is_in(["MATCH", "MATCH*"])).height
print(f"MATCH(={n_match}) / {rec_df.height} targets  (MATCH* = values+rows exact, column-set noted)")
print(f"Total downloaded this run: {downloaded_total:,} bytes")

if tfte_rows:
    print("\n--- teachers_fte ADJUDICATION (CSV vs mirror, verbatim) ---")
    for t in tfte_rows:
        print(f"  ncessch={t['ncessch']} year={t['year']} CSV={t['csv_teachers_fte']!r} "
              f"mirror={t['mirror_teachers_fte']!r} equal={t['equal']}")

if all_examples:
    print("\n--- RESIDUAL MISMATCH EXAMPLES (verbatim, capped 40) ---")
    for e in all_examples[:40]:
        print(f"  [{e['label']}] key={e['key']} col={e['column']}({e['kind']}) "
              f"csv={e['csv_value']!r} mirror={e['mirror_value']!r}")
else:
    print("\nNo residual value mismatches across any compared column.")

print("\nLANE A COMPLETE")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 14:31:46
# Command: python3 /daaf/scripts/mirror_maintenance/22_laneA-conversion-fidelity.py
# Duration: 98s
# Exit code: 0
#
# --- STDOUT ---
# === LANE A: CONVERSION FIDELITY (bulk CSV vs mirror parquet) ===
# [head] meps: content-length=113452490
# [head] nacubo: content-length=658402
# [head] crdc_char: content-length=92239948
# Planned cumulative download: 1,255,413,242 bytes (cap 2,600,000,000)
# 
# ------------------------------------------------------------------------
# [ccd_directory] https://educationdata.urban.org/csv/ccd/schools_ccd_directory.csv
#   [ok] CSV on disk: 1,014,405,917 B (cum 1,014,405,917)
#   rows: csv=3,790,415 mirror=3,790,415 match=True
#   cols: shared=50 csv_only=[] mirror_only=[]
#   mode=sort-align (full-column, every cell) keysUnique=True keySetsEqual=True
#   VERDICT=MATCH colMM=0 cellMM=0 
#   [teachers_fte] ncessch=110000800382 year=2022 CSV='28.98' mirror=28.98
#   [teachers_fte] ncessch=110000800478 year=2022 CSV='24.96' mirror=24.96
#   [teachers_fte] ncessch=110000800479 year=2022 CSV='24.96' mirror=24.96
# 
# ------------------------------------------------------------------------
# [ipeds_sfr] https://educationdata.urban.org/csv/ipeds/colleges_ipeds_student-faculty-ratio.csv
#   [ok] CSV on disk: 1,807,729 B (cum 1,016,213,646)
#   rows: csv=102,371 mirror=102,371 match=True
#   cols: shared=2 csv_only=[] mirror_only=[]
#   mode=sort-align (full-column, every cell) keysUnique=True keySetsEqual=True
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [saipe] https://educationdata.urban.org/csv/saipe/districts_saipe.csv
#   [ok] CSV on disk: 32,848,756 B (cum 1,049,062,402)
#   rows: csv=382,099 mirror=382,099 match=True
#   cols: shared=8 csv_only=[] mirror_only=[]
#   mode=sort-align (full-column, every cell) keysUnique=True keySetsEqual=True
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [meps] https://educationdata.urban.org/csv/meps/schools_meps.csv
#   [ok] CSV on disk: 113,452,490 B (cum 1,162,514,892)
#   rows: csv=1,345,122 mirror=1,345,122 match=True
#   cols: shared=9 csv_only=[] mirror_only=[]
#   mode=sort-align (full-column, every cell) keysUnique=True keySetsEqual=True
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# ------------------------------------------------------------------------
# [nacubo] https://educationdata.urban.org/csv/nacubo/colleges_nacubo_endow.csv
#   [ok] CSV on disk: 658,402 B (cum 1,163,173,294)
#   rows: csv=8,197 mirror=8,197 match=True
#   cols: shared=5 csv_only=[] mirror_only=[]
#   mode=keyed-inner-join (intersection) keysUnique=False keySetsEqual=True
#   VERDICT=MISMATCH colMM=3 cellMM=30 
# 
# ------------------------------------------------------------------------
# [crdc_char] https://educationdata.urban.org/csv/crdc/schools_crdc_school_characteristics.csv
#   [ok] CSV on disk: 92,239,948 B (cum 1,255,413,242)
#   rows: csv=580,719 mirror=580,719 match=True
#   cols: shared=33 csv_only=[] mirror_only=[]
#   mode=sort-align (full-column, every cell) keysUnique=True keySetsEqual=True
#   VERDICT=MATCH colMM=0 cellMM=0 
# 
# === LANE A SUMMARY ===
# shape: (6, 8)
# ┌────────────┬──────────┬──────────┬────────────┬───────────┬────────────┬────────────┬────────────┐
# │ label      ┆ verdict  ┆ csv_rows ┆ mirror_row ┆ row_match ┆ shared_col ┆ cols_misma ┆ cell_misma │
# │ ---        ┆ ---      ┆ ---      ┆ s          ┆ ---       ┆ s          ┆ tch        ┆ tch        │
# │ str        ┆ str      ┆ i64      ┆ ---        ┆ bool      ┆ ---        ┆ ---        ┆ ---        │
# │            ┆          ┆          ┆ i64        ┆           ┆ i64        ┆ i64        ┆ i64        │
# ╞════════════╪══════════╪══════════╪════════════╪═══════════╪════════════╪════════════╪════════════╡
# │ ccd_direct ┆ MATCH    ┆ 3790415  ┆ 3790415    ┆ true      ┆ 50         ┆ 0          ┆ 0          │
# │ ory        ┆          ┆          ┆            ┆           ┆            ┆            ┆            │
# │ ipeds_sfr  ┆ MATCH    ┆ 102371   ┆ 102371     ┆ true      ┆ 2          ┆ 0          ┆ 0          │
# │ saipe      ┆ MATCH    ┆ 382099   ┆ 382099     ┆ true      ┆ 8          ┆ 0          ┆ 0          │
# │ meps       ┆ MATCH    ┆ 1345122  ┆ 1345122    ┆ true      ┆ 9          ┆ 0          ┆ 0          │
# │ nacubo     ┆ MISMATCH ┆ 8197     ┆ 8197       ┆ true      ┆ 5          ┆ 3          ┆ 30         │
# │ crdc_char  ┆ MATCH    ┆ 580719   ┆ 580719     ┆ true      ┆ 33         ┆ 0          ┆ 0          │
# └────────────┴──────────┴──────────┴────────────┴───────────┴────────────┴────────────┴────────────┘
# MATCH(=5) / 6 targets  (MATCH* = values+rows exact, column-set noted)
# Total downloaded this run: 1,255,413,242 bytes
# 
# --- teachers_fte ADJUDICATION (CSV vs mirror, verbatim) ---
#   ncessch=110000800382 year=2022 CSV='28.98' mirror='28.98' equal=True
#   ncessch=110000800478 year=2022 CSV='24.96' mirror='24.96' equal=True
#   ncessch=110000800479 year=2022 CSV='24.96' mirror='24.96' equal=True
# 
# --- RESIDUAL MISMATCH EXAMPLES (verbatim, capped 40) ---
#   [nacubo] key=102094.0|2012.0 col=inst_name_nacubo(str) csv='University of South Alabama Foundation' mirror='University of South Alabama'
#   [nacubo] key=102094.0|2012.0 col=inst_name_nacubo(str) csv='University of South Alabama' mirror='University of South Alabama Foundation'
#   [nacubo] key=149772.0|2012.0 col=inst_name_nacubo(str) csv='Sam Houston State University' mirror='Western Illinois University Foundation'
#   [nacubo] key=149772.0|2012.0 col=fips(num) csv='48.0' mirror='17.0'
#   [nacubo] key=168430.0|2012.0 col=fips(num) csv='37.0' mirror='25.0'
#   [nacubo] key=168430.0|2012.0 col=fips(num) csv='25.0' mirror='37.0'
#   [nacubo] key=102094.0|2012.0 col=endow_total(num) csv='298536000.0' mirror='160000000.0'
#   [nacubo] key=102094.0|2012.0 col=endow_total(num) csv='160000000.0' mirror='298536000.0'
#   [nacubo] key=149772.0|2012.0 col=endow_total(num) csv='57022000.0' mirror='31621890.0'
# 
# LANE A COMPLETE
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
