#!/usr/bin/env python3
# =============================================================================
# 06_fetch-convert-mirror-v2_c.py  (Mirror V2 corrective rebuild)
# =============================================================================
# INTENT: Rebuild the 23 `skipped_reverified` fetched DATA parquets through the
#   reference-schema path (the method 06_b applied to only 5 of 28 fetched files).
#   QA (qa5/qa6) proved these 23 survived via skip-reverify carrying run-06's
#   inference / abandoned-universal-contract typing (e.g. saipe.leaid zfilled-to-7
#   large_string; ipeds directory large_string; ay_tuition_fees pct_increase int64
#   where old vintage was double; fall-retention count cols int64 where old vintage
#   was string). This re-converts each from its source CSV so it reproduces its own
#   OLD-VINTAGE schema (names, order, normalized dtypes), preserving revision-driven
#   domain growth as String and never nulling a populated cell.
#
# METHOD (per file):
#   1. Download source CSV (resumable via HTTP Range; retries w/ backoff; polite pace).
#      Completeness verified against source_content_length from the provenance parquet.
#   2. Read CSV all-String (pl.read_csv infer_schema=False) -> the CSV "truth" baseline.
#   3. Reference schema = old_vintage_copies/<rel> (normalized large_string/string_view
#      -> string, large_binary/binary_view -> binary). For the 2 completions_*_2023
#      shards with NO old vintage, reference = their carried-forward _2022 family sibling.
#   4. Per column, data-preserving cast String -> normalized reference dtype:
#        - string/binary target -> keep String
#        - numeric target -> cast(strict=False); if it would null any populated cell
#          the domain outgrew the old dtype -> KEEP String + log evidence
#        - genuinely-new column (in CSV, absent from reference) -> data-preserving
#          inference: Int64 if lossless, else Float64 if lossless, else String
#   5. Reorder to reference column order; append genuinely-new columns after.
#   6. Cast to an exact normalized Arrow schema (guarantees regular `string`, never
#      large_string/string_view) and write parquet atomically (temp -> os.replace).
#
# PER-FILE ASSERTIONS (06_b parity + task additions):
#   A. row_count(out) == CSV row_count.
#   B. non-null(out[col]) == non-null(CSV[col]) for EVERY column (no cast nulled a
#      populated cell).
#   C. schema parity vs old vintage: normalized rebuilt dtype == normalized old dtype
#      for every common column, EXCEPT justified domain-String keeps (logged).
#   D. identifier columns (leaid/ncessch/unitid/crdc_id/fips/district_id) match the
#      old-vintage dtype EXACTLY unless a domain change is evidenced (logged).
#   E. output Arrow schema carries no large_string/large_binary/*_view.
#
# OUTPUTS: overwrites the 23 tree parquets in mirror_v2_tree/; writes
#   2026-08-06_mirror-v2-audit/rebuilt_23_provenance.parquet (manifest patch input for
#   07_a) and rebuilt_23_evidence.parquet (domain-String keeps + new-col typing).
#
# NOTE (audit trail): the predecessor scripts 05/06/06_a/06_b/07 named in the build
#   return were not persisted to disk (research/ is gitignored; only qa/ + drift_battery/
#   scripts remain), so create_script_revision.sh had no source to strip — this _c
#   revision was authored directly. All inputs it relies on (provenance parquet,
#   old_vintage_copies/, build_manifest, live Urban CSVs) are present and were verified.
#
# Read-only network GETs. No installs. No /tmp. File-first via run_with_capture.sh.
# =============================================================================

# --- Config ---
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import urllib.request
import urllib.error
import hashlib
import os
import re
import time
import datetime
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
AUDIT_DIR = PROJECT_DIR / "2026-08-06_mirror-v2-audit"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
OLD_VINTAGE_DIR = PROJECT_DIR / "old_vintage_copies"
CSV_DIR = PROJECT_DIR / "scripts" / "scratch" / "csv_build"
CSV_DIR.mkdir(parents=True, exist_ok=True)

NOW_ISO = datetime.datetime.now(datetime.timezone.utc).isoformat()
NEW_ACTION = "rebuilt-reference-schema-2026-08-06"
NEW_VERIF = "rebuilt_reference_schema_2026-08-06_parquet_readable"

# ASSUMES: normalized Arrow type strings map to these polars / arrow dtypes.
PL_MAP = {"int64": pl.Int64, "int32": pl.Int32, "int16": pl.Int16, "int8": pl.Int8,
          "uint64": pl.UInt64, "uint32": pl.UInt32, "uint16": pl.UInt16, "uint8": pl.UInt8,
          "double": pl.Float64, "float": pl.Float32, "string": pl.String, "bool": pl.Boolean}
PA_MAP = {"int64": pa.int64(), "int32": pa.int32(), "int16": pa.int16(), "int8": pa.int8(),
          "uint64": pa.uint64(), "uint32": pa.uint32(), "uint16": pa.uint16(), "uint8": pa.uint8(),
          "double": pa.float64(), "float": pa.float32(), "string": pa.string(), "bool": pa.bool_()}
NUMERIC = {"int64", "int32", "int16", "int8", "uint64", "uint32", "uint16", "uint8", "double", "float"}
ID_COLS = {"leaid", "ncessch", "unitid", "crdc_id", "fips", "district_id"}
UA = "DAAF-mirror-maintenance/1.0 (research; contact brhkim@gmail.com)"

# --- Load target list (authoritative: skipped_reverified DATA parquets) ---
prov = pl.read_parquet(AUDIT_DIR / "build_provenance_fetched.parquet")
targets = (prov.filter((pl.col("action") == "skipped_reverified") & (pl.col("object_kind") == "data"))
           .sort("relative_path"))
print(f"Rebuild targets: {targets.height} data parquets (expect 23)")
assert targets.height == 23, f"expected 23 targets, got {targets.height}"

# Build a manifest lookup for family-sibling reference (no-old-vintage shards)
manifest = pl.read_parquet(TREE_DIR / "build_manifest.parquet")
carried = set(manifest.filter(pl.col("provenance") == "carried-forward")["relative_path"].to_list())

records = []   # manifest-patch rows for 07_a
evidence = []  # domain-String keeps + new-col typing

# --- Rebuild loop (one atomic conversion per target) ---
for tr in targets.iter_rows(named=True):
    rel = tr["relative_path"]
    url = tr["source_url"]
    expected_csv_bytes = tr["source_content_length"]
    out_fp = TREE_DIR / rel
    csv_fp = CSV_DIR / rel.replace("/", "__").replace(".parquet", ".csv")

    # --- Download (resumable, retries, polite) ---
    # INTENT: obtain the current source CSV; resume partial downloads via HTTP Range.
    # REASONING: completeness is checked against the recorded source_content_length so a
    #   truncated transfer is never converted. ASSUMES Urban S3 backend honors Range (206).
    last_err = None
    for attempt in range(1, 6):
        if csv_fp.exists() and expected_csv_bytes is not None and csv_fp.stat().st_size == expected_csv_bytes:
            break  # cached & complete
        resume_from = csv_fp.stat().st_size if csv_fp.exists() else 0
        headers = {"User-Agent": UA}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                mode = "ab" if (resume_from > 0 and resp.status == 206) else "wb"
                if mode == "wb":
                    resume_from = 0  # server ignored Range -> restart clean
                with open(csv_fp, mode) as fh:
                    while True:
                        chunk = resp.read(1 << 20)  # 1 MB
                        if not chunk:
                            break
                        fh.write(chunk)
            if expected_csv_bytes is None or csv_fp.stat().st_size == expected_csv_bytes:
                break
            last_err = f"size {csv_fp.stat().st_size} != expected {expected_csv_bytes}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = repr(e)
        time.sleep(min(2 ** attempt, 20))  # backoff
    else:
        raise RuntimeError(f"download failed for {rel}: {last_err}")
    if expected_csv_bytes is not None:
        assert csv_fp.stat().st_size == expected_csv_bytes, f"{rel}: incomplete CSV"

    # --- Read CSV all-String (the truth baseline) ---
    # INTENT: read every field as String so no silent type inference occurs; the cast to
    #   the reference dtype is then explicit and data-preserving.
    df = pl.read_csv(csv_fp, infer_schema=False)
    n_rows = df.height
    csv_cols = df.columns
    base_nn = {c: int(df.select(pl.col(c).is_not_null().sum()).item()) for c in csv_cols}

    # --- Resolve reference schema (normalized) + column order ---
    ov_fp = OLD_VINTAGE_DIR / rel
    if ov_fp.exists():
        ov_sch = pq.read_schema(ov_fp)
        ref_norm = {}
        for f in ov_sch:
            t = (str(f.type).replace("large_string", "string").replace("string_view", "string")
                 .replace("large_binary", "binary").replace("binary_view", "binary"))
            ref_norm[f.name] = t
        ref_order = list(ov_sch.names)
        ref_source = f"old_vintage:{rel}"
    else:
        # No old vintage (year-sharded new shard): use carried-forward _YYYY family sibling.
        m = re.search(r"_(\d{4})\.parquet$", rel)
        assert m, f"{rel}: no old vintage and no _YYYY token to find a sibling"
        yr = int(m.group(1))
        sib_rel = None
        for cand_yr in range(yr - 1, yr - 40, -1):
            cand = re.sub(r"_\d{4}\.parquet$", f"_{cand_yr}.parquet", rel)
            if cand in carried:
                sib_rel = cand
                break
        assert sib_rel, f"{rel}: no carried-forward family sibling found"
        sib_sch = pq.read_schema(TREE_DIR / sib_rel)
        ref_norm = {}
        for f in sib_sch:
            t = (str(f.type).replace("large_string", "string").replace("string_view", "string")
                 .replace("large_binary", "binary").replace("binary_view", "binary"))
            ref_norm[f.name] = t
        ref_order = list(sib_sch.names)
        ref_source = f"sibling:{sib_rel}"

    new_cols = [c for c in csv_cols if c not in ref_norm]
    final_order = [c for c in ref_order if c in csv_cols] + new_cols

    # --- Decide final normalized dtype per column (data-preserving) ---
    final_norm = {}
    for c in final_order:
        base = base_nn[c]
        if c in ref_norm:
            at = ref_norm[c]
            if at in ("string", "binary"):
                final_norm[c] = "string"
            elif at in NUMERIC:
                after = int(df.select(pl.col(c).cast(PL_MAP[at], strict=False).is_not_null().sum()).item())
                if after == base:
                    final_norm[c] = at
                else:
                    final_norm[c] = "string"  # domain outgrew old dtype -> keep String
                    evidence.append({"relative_path": rel, "column": c, "kind": "domain-string-keep",
                                     "detail": f"old={at}; cast would null {base - after} of {base} populated cells"})
            else:
                final_norm[c] = "string"
        else:
            # genuinely-new column: infer the narrowest lossless numeric type, else String
            after_i = int(df.select(pl.col(c).cast(pl.Int64, strict=False).is_not_null().sum()).item())
            if after_i == base:
                final_norm[c] = "int64"
            else:
                after_f = int(df.select(pl.col(c).cast(pl.Float64, strict=False).is_not_null().sum()).item())
                final_norm[c] = "double" if after_f == base else "string"
            evidence.append({"relative_path": rel, "column": c, "kind": "new-col-typed",
                             "detail": f"no reference; typed {final_norm[c]}"})

    # --- Cast + reorder ---
    cast_exprs = []
    for c in final_order:
        fn = final_norm[c]
        if fn == "string":
            cast_exprs.append(pl.col(c).cast(pl.String))
        else:
            cast_exprs.append(pl.col(c).cast(PL_MAP[fn], strict=False))
    df_cast = df.select(cast_exprs)  # select in final_order -> reorders columns

    # --- Lock exact normalized Arrow schema (regular string, never large_string/view) ---
    tbl = df_cast.to_arrow()
    target_schema = pa.schema([pa.field(c, PA_MAP[final_norm[c]]) for c in final_order])
    tbl = tbl.cast(target_schema)

    # --- Assertions ---
    # A: row count preserved vs CSV
    assert tbl.num_rows == n_rows, f"{rel}: row count {tbl.num_rows} != CSV {n_rows}"
    # B: non-null preserved per column vs CSV
    out_df = pl.from_arrow(tbl)
    for c in final_order:
        onn = int(out_df.select(pl.col(c).is_not_null().sum()).item())
        assert onn == base_nn[c], f"{rel}.{c}: non-null {onn} != CSV {base_nn[c]} (populated cell nulled)"
    # C: schema parity vs old vintage (common cols) except logged domain-String keeps
    dstr = {(e["relative_path"], e["column"]) for e in evidence if e["kind"] == "domain-string-keep"}
    if ov_fp.exists():
        out_norm = {}
        for f in tbl.schema:
            out_norm[f.name] = (str(f.type).replace("large_string", "string").replace("string_view", "string")
                                .replace("large_binary", "binary").replace("binary_view", "binary"))
        for c in ref_order:
            if c in out_norm:
                if out_norm[c] != ref_norm[c]:
                    assert (rel, c) in dstr, (f"{rel}.{c}: dtype {out_norm[c]} != old {ref_norm[c]} "
                                              f"with no domain-change evidence")
        # D: identifier-column exactness
        for c in (ID_COLS & set(ref_order) & set(out_norm.keys())):
            if out_norm[c] != ref_norm[c]:
                assert (rel, c) in dstr, f"{rel}.{c}: identifier dtype {out_norm[c]} != old {ref_norm[c]} unevidenced"
    # E: no large_string / view in output
    bad = [f.name for f in tbl.schema
           if pa.types.is_large_string(f.type) or pa.types.is_large_binary(f.type)
           or pa.types.is_string_view(f.type) or pa.types.is_binary_view(f.type)]
    assert not bad, f"{rel}: output still carries large/view types: {bad}"

    # --- Write atomically ---
    tmp_fp = out_fp.with_suffix(".parquet.tmp")
    pq.write_table(tbl, tmp_fp, compression="zstd")
    os.replace(tmp_fp, out_fp)

    # --- Record manifest patch row (sha256 = LFS-style sha256 of shipped bytes) ---
    raw = out_fp.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    records.append({
        "relative_path": rel,
        "shipped_bytes": len(raw),
        "shipped_sha256": sha,
        "row_count": n_rows,
        "column_count": len(final_order),
        "provenance": "fetched-2026-08-06",
        "action": NEW_ACTION,
        "verification_method": NEW_VERIF,
        "verification_result": "PASS",
        "observed_at_utc": NOW_ISO,
        "ref_source": ref_source,
        "n_new_cols": len(new_cols),
    })
    ndiv = "|".join(sorted({c for (r, c) in dstr if r == rel}))
    print(f"[ok] {rel:58s} rows={n_rows:>9,} cols={len(final_order):>3} "
          f"new={len(new_cols)} domainString=[{ndiv}] bytes={len(raw):,}")

# --- Persist manifest patch + evidence ---
rec_df = pl.from_dicts(records)
rec_df.write_parquet(AUDIT_DIR / "rebuilt_23_provenance.parquet")
ev_df = pl.from_dicts(evidence) if evidence else pl.DataFrame(
    {"relative_path": [], "column": [], "kind": [], "detail": []})
ev_df.write_parquet(AUDIT_DIR / "rebuilt_23_evidence.parquet")

# --- Checkpoint MA-BUILD-06C summary ---
print("\n=== MA-BUILD-06C SUMMARY ===")
print(f"Rebuilt: {rec_df.height}/23 files")
print(f"Total rebuilt bytes: {rec_df['shipped_bytes'].sum():,}")
print(f"Domain-String keeps: {ev_df.filter(pl.col('kind') == 'domain-string-keep').height}")
if ev_df.filter(pl.col("kind") == "domain-string-keep").height:
    print(ev_df.filter(pl.col("kind") == "domain-string-keep"))
print(f"New-column typings: {ev_df.filter(pl.col('kind') == 'new-col-typed').height}")
print(ev_df.filter(pl.col("kind") == "new-col-typed"))
assert rec_df.height == 23, "did not rebuild all 23"
print("\nMA-BUILD-06C PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-06 21:09:17
# Command: python3 /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/scripts/mirror_maintenance/06_fetch-convert-mirror-v2_c.py
# Duration: 122s
# Exit code: 0
#
# --- STDOUT ---
# Rebuild targets: 23 data parquets (expect 23)
# [ok] ipeds/colleges_ipeds_academic_libraries.parquet            rows=   43,077 cols= 41 new=0 domainString=[] bytes=3,679,086
# [ok] ipeds/colleges_ipeds_admissions-enrollment.parquet         rows=  215,831 cols=  9 new=0 domainString=[] bytes=1,568,476
# [ok] ipeds/colleges_ipeds_ay_room_board_other.parquet           rows=  295,709 cols=  8 new=0 domainString=[] bytes=1,580,663
# [ok] ipeds/colleges_ipeds_ay_tuition_fees.parquet               rows=  668,761 cols= 14 new=0 domainString=[] bytes=4,168,512
# [ok] ipeds/colleges_ipeds_ay_tuition_firstprof.parquet          rows=   50,802 cols=  8 new=0 domainString=[] bytes=333,233
# [ok] ipeds/colleges_ipeds_completers.parquet                    rows=2,228,100 cols=  6 new=0 domainString=[] bytes=2,177,214
# [ok] ipeds/colleges_ipeds_completions-2digcip_2023.parquet      rows=4,235,250 cols=  9 new=0 domainString=[] bytes=2,830,863
# [ok] ipeds/colleges_ipeds_completions-6digcip_2023.parquet      rows=9,184,110 cols=  9 new=0 domainString=[] bytes=4,092,786
# [ok] ipeds/colleges_ipeds_directory.parquet                     rows=  343,054 cols= 96 new=7 domainString=[] bytes=13,159,042
# [ok] ipeds/colleges_ipeds_enrollment-fte.parquet                rows=  478,066 cols=  9 new=0 domainString=[] bytes=2,548,938
# [ok] ipeds/colleges_ipeds_fall-enrollment-race_2020.parquet     rows=3,533,310 cols= 10 new=0 domainString=[] bytes=8,981,895
# [ok] ipeds/colleges_ipeds_fall-res.parquet                      rows=3,503,286 cols=  6 new=0 domainString=[] bytes=7,301,276
# [ok] ipeds/colleges_ipeds_fall-retention.parquet                rows=  278,296 cols= 10 new=1 domainString=[] bytes=1,300,581
# [ok] ipeds/colleges_ipeds_grad-rates-200pct.parquet             rows=   93,088 cols= 17 new=0 domainString=[] bytes=1,243,241
# [ok] ipeds/colleges_ipeds_grad-rates-pell.parquet               rows=  367,628 cols= 12 new=0 domainString=[] bytes=2,074,249
# [ok] ipeds/colleges_ipeds_grad-rates.parquet                    rows=6,141,988 cols= 18 new=0 domainString=[] bytes=31,968,148
# [ok] ipeds/colleges_ipeds_institutional-characteristics.parquet rows=  341,751 cols=126 new=0 domainString=[] bytes=5,132,008
# [ok] ipeds/colleges_ipeds_py_room_board_other.parquet           rows=  108,932 cols=  6 new=0 domainString=[] bytes=533,054
# [ok] ipeds/colleges_ipeds_py_tuition_cip.parquet                rows=  336,814 cols= 15 new=0 domainString=[] bytes=2,369,312
# [ok] ipeds/colleges_ipeds_salaries_is.parquet                   rows=7,932,422 cols= 11 new=0 domainString=[] bytes=47,289,351
# [ok] ipeds/colleges_ipeds_salaries_nis.parquet                  rows=  789,768 cols=  6 new=0 domainString=[] bytes=5,306,933
# [ok] ipeds/colleges_ipeds_student-faculty-ratio.parquet         rows=  102,371 cols=  4 new=0 domainString=[] bytes=142,902
# [ok] saipe/districts_saipe.parquet                              rows=  382,099 cols= 10 new=0 domainString=[] bytes=11,091,655
# 
# === MA-BUILD-06C SUMMARY ===
# Rebuilt: 23/23 files
# Total rebuilt bytes: 160,873,418
# Domain-String keeps: 0
# New-column typings: 8
# shape: (8, 4)
# ┌──────────────────────────────┬─────────────────────────────┬───────────────┬─────────────────────┐
# │ relative_path                ┆ column                      ┆ kind          ┆ detail              │
# │ ---                          ┆ ---                         ┆ ---           ┆ ---                 │
# │ str                          ┆ str                         ┆ str           ┆ str                 │
# ╞══════════════════════════════╪═════════════════════════════╪═══════════════╪═════════════════════╡
# │ ipeds/colleges_ipeds_directo ┆ cc_award_level_focus_2025   ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_directo ┆ cc_undergrad_2025           ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_directo ┆ cc_instruc_grad_2025        ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_directo ┆ cc_basic_2025               ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_directo ┆ cc_research_act_desig_2025  ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_directo ┆ cc_stud_access_earn_2025    ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_directo ┆ cc_instit_size_2025         ┆ new-col-typed ┆ no reference; typed │
# │ ry…                          ┆                             ┆               ┆ int64               │
# │ ipeds/colleges_ipeds_fall-re ┆ prev_inclusions             ┆ new-col-typed ┆ no reference; typed │
# │ te…                          ┆                             ┆               ┆ int64               │
# └──────────────────────────────┴─────────────────────────────┴───────────────┴─────────────────────┘
# 
# MA-BUILD-06C PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
