#!/usr/bin/env python3
"""
Mirror maintenance 6/7: fetch + convert new/revised objects and fold in July-staged objects.

Task: fetch-convert-mirror-v2 (Stage build unit 06 of 05->06->07)
Depends on: delta manifest (build_action == "fetch-fresh": 39 objects)
Inputs (read-only GET from Urban Education Data Portal):
  - 28 new/revised DATA objects  -> fresh CSV fetch, convert CSV->parquet
  -  3 candidate-revised CODEBOOK objects (.xls) -> fresh fetch, no conversion
  -  8 July-staged DATA objects -> copied as-is from the 2026-07-21 staging dir (NOT re-fetched)
Outputs:
  - mirror_v2_tree/{source}/{filename}.{parquet|xls}  (39 files)
  - audit/build_provenance_fetched.parquet             (39 rows)
Checkpoint: MA-BUILD-06

Conversion follows 02_stage-education-portal-mirror_b.py conventions: zstd level-3 parquet,
row-group 100k, statistics on, maintain_order; identifier-width contract ncessch=12 /
leaid=7 zero-padded strings; unitid Int64; Arrow view types materialized to string/binary
for cross-language (R Arrow) compatibility.

DELIBERATE GENERALIZATION vs 02_b: 02_b applied the ncessch/leaid string contract only to
`ccd/` objects (the only prefixes it staged). This build also fetches `crdc/` and `saipe/`
DATA objects that carry ncessch/leaid identifiers, which would lose leading zeros if inferred
as integers. The contract is therefore applied to ANY object carrying these columns. This is
strictly safer (identifiers stay fixed-width strings) and self-guarding: a value that cannot
reach the canonical width trips the post-conversion width assertion and STOPs. Flagged in the
build report as a deviation for orchestrator awareness.

Urban had a full API outage earlier today (recovered ~19:20 UTC). Fetches use generous
timeouts, retry/backoff, and polite pacing. Per-object network failures are recorded and the
run continues; if any object is left unbuilt the script exits non-zero so a `_a` revision can
resume (idempotent: an already-built, re-validated parquet/xls is skipped, not re-fetched).
"""

# --- Config ---
import csv
import hashlib
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
AUDIT_DIR = PROJECT_DIR / "2026-08-06_mirror-v2-audit"
MANIFEST_PATH = AUDIT_DIR / "2026-08-06_mirror-v2-delta-manifest.parquet"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
CSV_SCRATCH = PROJECT_DIR / "scripts" / "scratch" / "csv_build"
FETCHED_PROV_PATH = AUDIT_DIR / "build_provenance_fetched.parquet"

STAGED_DIR = (
    BASE_DIR / "research" / "2026-07-21_FrameworkDev_EducationPortalSkills"
    / "2026-07-21_education-portal-mirror-staging" / "staged"
)

PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3
PARQUET_ROW_GROUP_SIZE = 100_000
PARQUET_STATISTICS = True
CHUNK_BYTES = 8 * 1024 * 1024
CONNECT_TIMEOUT = 60
READ_TIMEOUT = 900          # generous: large CSVs (up to ~300 MB) over a recovering API
POLITE_SLEEP_SECONDS = 1.5  # polite pacing between Urban requests

CSV_SCRATCH.mkdir(parents=True, exist_ok=True)

# --- Load ---
manifest = pl.read_parquet(MANIFEST_PATH)
fetch_df = manifest.filter(pl.col("build_action") == "fetch-fresh")
print(f"fetch-fresh objects: {fetch_df.height} (expected 39)")
assert fetch_df.height == 39, f"STOP: expected 39 fetch-fresh, got {fetch_df.height}"

staged_df = fetch_df.filter(pl.col("is_july_staged"))
fresh_df = fetch_df.filter(~pl.col("is_july_staged"))
print(f"  July-staged (copy as-is): {staged_df.height} (expected 8)")
print(f"  Fresh fetch from Urban:   {fresh_df.height} (expected 31)")
print(f"    fresh DATA:     {fresh_df.filter(pl.col('object_kind') == 'data').height} (expected 28)")
print(f"    fresh CODEBOOK: {fresh_df.filter(pl.col('object_kind') == 'codebook').height} (expected 3)")
assert staged_df.height == 8, "STOP: expected 8 July-staged"
assert fresh_df.height == 31, "STOP: expected 31 fresh"

# --- HTTP session with retry/backoff ---
session = requests.Session()
retry = Retry(
    total=6, connect=6, read=6, backoff_factor=2.0,
    status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
)
session.mount("https://", HTTPAdapter(max_retries=retry))
session.headers.update({"Accept-Encoding": "identity", "User-Agent": "daaf-mirror-v2-build/1.0"})

provenance_records = []
failures = []

# --- Stage 1: fold in the 8 July-staged objects (copy as-is) ---
# INTENT: copy verified July-staged parquet objects unchanged. REASONING: the delta audit
# re-verified them still-current today (byte+ETag); re-fetching would waste bandwidth and
# risk drift. ASSUMES: staged file lives at STAGED_DIR/{canonical_key}.parquet.
for row in staged_df.iter_rows(named=True):
    key = row["canonical_object_key"]
    rel = f"{key}.parquet"
    src = STAGED_DIR / rel
    dest = TREE_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    assert src.exists(), f"STOP: staged source missing for {key}: {src}"
    if not dest.exists():
        shutil.copy2(src, dest)
    # verify parquet opens with rows, capture sha256/bytes
    with dest.open("rb") as fh:
        head = fh.read(4)
        fh.seek(-4, 2)
        tail = fh.read(4)
    assert head == b"PAR1" and tail == b"PAR1", f"STOP: bad parquet magic (staged) {key}"
    pf = pq.ParquetFile(dest)
    assert pf.metadata.num_rows > 0, f"STOP: zero rows (staged) {key}"
    hasher = hashlib.sha256()
    with dest.open("rb") as fh:
        while True:
            c = fh.read(CHUNK_BYTES)
            if not c:
                break
            hasher.update(c)
    provenance_records.append({
        "canonical_object_key": key, "source": row["source"], "object_kind": "data",
        "relative_path": rel, "filename": Path(rel).name, "provenance": "staged-2026-07-21",
        "classification": row["classification"],
        "source_url": row["urban_url"],
        "source_content_length": row["current_source_bytes"],
        "source_last_modified": row["current_last_modified"],
        "source_etag": row["current_etag"],
        "source_sha256": None,
        "shipped_bytes": dest.stat().st_size, "shipped_sha256": hasher.hexdigest(),
        "row_count": pf.metadata.num_rows, "column_count": pf.metadata.num_columns,
        "verification_method": "staged_byte_etag_2026-07-21_plus_parquet_readable",
        "verification_result": "PASS", "action": "copied_staged",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[staged] {key}: {pf.metadata.num_rows:,} rows, {dest.stat().st_size:,} B")

# --- Stage 2: fresh fetch (+ convert data / copy codebook) ---
for idx, row in enumerate(fresh_df.iter_rows(named=True), start=1):
    key = row["canonical_object_key"]
    source = row["source"]
    kind = row["object_kind"]
    url = row["urban_url"]
    expected_source_bytes = row["current_source_bytes"]
    expected_etag = row["current_etag"]
    ext = ".parquet" if kind == "data" else Path(url).suffix  # codebook keeps its .xls
    rel = f"{key}{ext}"
    dest = TREE_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("\n" + "-" * 72)
    print(f"[{idx}/{fresh_df.height}] FETCH {kind}: {key}")

    # INTENT: idempotent skip — a data parquet that opens with rows, or a codebook whose
    # bytes match the audited source length, is treated as already built. REASONING: makes
    # `_a` resume cheap after an Urban outage. ASSUMES: a previously-built object is good.
    if dest.exists():
        if kind == "data":
            try:
                pf = pq.ParquetFile(dest)
                if pf.metadata.num_rows > 0:
                    hasher = hashlib.sha256()
                    with dest.open("rb") as fh:
                        while True:
                            c = fh.read(CHUNK_BYTES)
                            if not c:
                                break
                            hasher.update(c)
                    provenance_records.append({
                        "canonical_object_key": key, "source": source, "object_kind": kind,
                        "relative_path": rel, "filename": Path(rel).name,
                        "provenance": "fetched-2026-08-06", "classification": row["classification"],
                        "source_url": url, "source_content_length": expected_source_bytes,
                        "source_last_modified": row["current_last_modified"], "source_etag": expected_etag,
                        "source_sha256": None, "shipped_bytes": dest.stat().st_size,
                        "shipped_sha256": hasher.hexdigest(), "row_count": pf.metadata.num_rows,
                        "column_count": pf.metadata.num_columns,
                        "verification_method": "resume_reverified_parquet_readable",
                        "verification_result": "PASS", "action": "skipped_reverified",
                        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                    })
                    print(f"  [skip] already built: {pf.metadata.num_rows:,} rows")
                    continue
            except Exception:
                dest.unlink()
        else:
            if expected_source_bytes is not None and dest.stat().st_size == int(expected_source_bytes):
                hasher = hashlib.sha256()
                with dest.open("rb") as fh:
                    while True:
                        c = fh.read(CHUNK_BYTES)
                        if not c:
                            break
                        hasher.update(c)
                provenance_records.append({
                    "canonical_object_key": key, "source": source, "object_kind": kind,
                    "relative_path": rel, "filename": Path(rel).name,
                    "provenance": "fetched-2026-08-06", "classification": row["classification"],
                    "source_url": url, "source_content_length": expected_source_bytes,
                    "source_last_modified": row["current_last_modified"], "source_etag": expected_etag,
                    "source_sha256": None, "shipped_bytes": dest.stat().st_size,
                    "shipped_sha256": hasher.hexdigest(), "row_count": None, "column_count": None,
                    "verification_method": "resume_reverified_codebook_bytes",
                    "verification_result": "PASS", "action": "skipped_reverified",
                    "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                })
                print(f"  [skip] already built codebook: {dest.stat().st_size:,} B")
                continue
            dest.unlink()

    try:
        if kind == "codebook":
            # --- Fetch codebook (.xls) as-is ---
            # INTENT: download the binary codebook unchanged. REASONING: codebooks are
            # reference artifacts, not tabular data; no conversion applies. ASSUMES: the
            # audited Content-Length is the definitive size check.
            hasher = hashlib.sha256()
            written = 0
            resp = session.get(url, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            assert resp.status_code == 200, f"STOP: HTTP {resp.status_code} for {key}"
            with dest.open("wb") as out:
                for c in resp.iter_content(chunk_size=CHUNK_BYTES):
                    if not c:
                        continue
                    written += len(c)
                    hasher.update(c)
                    out.write(c)
            resp.close()
            if expected_source_bytes is not None:
                assert written == int(expected_source_bytes), (
                    f"STOP: codebook byte drift for {key}: {written} != {expected_source_bytes}"
                )
            provenance_records.append({
                "canonical_object_key": key, "source": source, "object_kind": kind,
                "relative_path": rel, "filename": Path(rel).name,
                "provenance": "fetched-2026-08-06", "classification": row["classification"],
                "source_url": url, "source_content_length": expected_source_bytes,
                "source_last_modified": row["current_last_modified"], "source_etag": expected_etag,
                "source_sha256": hasher.hexdigest(), "shipped_bytes": written,
                "shipped_sha256": hasher.hexdigest(), "row_count": None, "column_count": None,
                "verification_method": "content_length_match", "verification_result": "PASS",
                "action": "fetched", "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            })
            print(f"  [ok] codebook fetched: {written:,} B")
            time.sleep(POLITE_SLEEP_SECONDS)
            continue

        # --- Fetch CSV to scratch ---
        # INTENT: stream the source CSV to a project-local scratch file while hashing.
        # REASONING: conversion needs the full CSV on disk; hashing during transfer records
        # source provenance. ASSUMES: Accept-Encoding identity => byte counts are source bytes.
        safe = key.replace("/", "__")
        csv_path = CSV_SCRATCH / f"{safe}.csv"
        if csv_path.exists():
            csv_path.unlink()  # discard any stale partial; fetch fresh (object-level idempotency)
        src_hasher = hashlib.sha256()
        written = 0
        resp = session.get(url, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        assert resp.status_code == 200, f"STOP: HTTP {resp.status_code} for {key}"
        resp_len = resp.headers.get("Content-Length")
        resp_etag = resp.headers.get("ETag")
        resp_lastmod = resp.headers.get("Last-Modified")
        with csv_path.open("wb") as out:
            for c in resp.iter_content(chunk_size=CHUNK_BYTES):
                if not c:
                    continue
                written += len(c)
                src_hasher.update(c)
                out.write(c)
        resp.close()
        source_sha256 = src_hasher.hexdigest()
        if expected_source_bytes is not None and written != int(expected_source_bytes):
            print(f"  [warn] source bytes {written:,} != audited {expected_source_bytes:,} "
                  f"(Urban may have regenerated the CSV; proceeding with fetched bytes)")

        # --- Inspect header + build identifier overrides ---
        with csv_path.open("r", encoding="utf-8-sig", newline="") as raw:
            source_columns = next(csv.reader(raw))
        assert source_columns and len(source_columns) == len(set(source_columns)), (
            f"STOP: empty/duplicate CSV header for {key}"
        )
        overrides = {}
        if "ncessch" in source_columns:
            overrides["ncessch"] = pl.String
        if "leaid" in source_columns:
            overrides["leaid"] = pl.String
        if "unitid" in source_columns:
            overrides["unitid"] = pl.Int64

        # --- Convert CSV -> parquet ---
        # INTENT: strict lazy parse, zero-pad CCD identifiers to canonical width, stream to a
        # deterministic parquet. REASONING: ignore_errors=False surfaces unmodeled type drift;
        # zfill repairs already-string identifiers to fixed width. ASSUMES: UTF-8 comma CSV.
        polars_tmp = CSV_SCRATCH / f"{safe}.polars.parquet"
        if polars_tmp.exists():
            polars_tmp.unlink()
        lazy = pl.scan_csv(
            csv_path, has_header=True, separator=",", quote_char='"',
            infer_schema_length=100_000, schema_overrides=overrides or None,
            ignore_errors=False, try_parse_dates=False, low_memory=True, rechunk=False, encoding="utf8",
        )
        id_expr = []
        for id_name, id_width in [("ncessch", 12), ("leaid", 7)]:
            if id_name in source_columns:
                id_expr.append(
                    pl.when(pl.col(id_name).is_null() | pl.col(id_name).is_in(["", "-1", "-2", "-3"]))
                    .then(pl.col(id_name))
                    .otherwise(pl.col(id_name).str.zfill(id_width))
                    .alias(id_name)
                )
        if id_expr:
            lazy = lazy.with_columns(id_expr)
        lazy.sink_parquet(
            polars_tmp, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS, row_group_size=PARQUET_ROW_GROUP_SIZE,
            maintain_order=True, engine="streaming", mkdir=True,
        )

        # --- Materialize Arrow view types (utf8_view/binary_view -> string/binary) ---
        # INTENT: rewrite view-typed columns so R Arrow can read the file. REASONING: polars
        # emits utf8_view which R Arrow cannot convert. ASSUMES: flat (non-nested) CSV schema.
        arrow_schema = pq.read_schema(polars_tmp)
        view_fields = []
        mat_fields = []
        for field in arrow_schema:
            if pa.types.is_string_view(field.type):
                view_fields.append(field.name)
                mat_fields.append(pa.field(field.name, pa.string(), nullable=field.nullable))
            elif pa.types.is_binary_view(field.type):
                view_fields.append(field.name)
                mat_fields.append(pa.field(field.name, pa.binary(), nullable=field.nullable))
            else:
                mat_fields.append(field)
        if view_fields:
            mat_schema = pa.schema(mat_fields)
            reader = pq.ParquetFile(polars_tmp)
            writer = pq.ParquetWriter(
                dest, mat_schema, compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL, write_statistics=PARQUET_STATISTICS,
                use_dictionary=True,
            )
            try:
                for batch in reader.iter_batches(batch_size=PARQUET_ROW_GROUP_SIZE):
                    writer.write_table(pa.Table.from_batches([batch]).cast(mat_schema),
                                       row_group_size=PARQUET_ROW_GROUP_SIZE)
            finally:
                writer.close()
            polars_tmp.unlink()
        else:
            polars_tmp.replace(dest)

        # --- Validate staged parquet ---
        final_schema = pq.read_schema(dest)
        assert not any(pa.types.is_string_view(f.type) or pa.types.is_binary_view(f.type) for f in final_schema), (
            f"STOP: Arrow view type remains in {key}"
        )
        with dest.open("rb") as fh:
            head = fh.read(4)
            fh.seek(-4, 2)
            tail = fh.read(4)
        assert head == b"PAR1" and tail == b"PAR1", f"STOP: bad parquet magic for {key}"
        pf = pq.ParquetFile(dest)
        row_count = pf.metadata.num_rows
        col_count = pf.metadata.num_columns
        assert row_count > 0, f"STOP: zero rows for {key}"
        assert list(final_schema.names) == source_columns, (
            f"STOP: column name/order drift for {key}"
        )
        # Identifier width/domain checks (mirror 02_b contract)
        checks = []
        for id_name, id_width in [("ncessch", 12), ("leaid", 7)]:
            if id_name in source_columns:
                valid = pl.col(id_name).is_not_null() & ~pl.col(id_name).is_in(["", "-1", "-2", "-3"])
                checks.extend([
                    pl.col(id_name).filter(valid & (pl.col(id_name).str.len_chars() != id_width)).len().alias(f"{id_name}_badw"),
                    pl.col(id_name).filter(valid & ~pl.col(id_name).str.contains(r"^\d+$")).len().alias(f"{id_name}_nonnum"),
                ])
        if "unitid" in source_columns:
            checks.append(pl.col("unitid").filter(pl.col("unitid").is_not_null() & ~pl.col("unitid").is_in([-1, -2, -3]) & (pl.col("unitid") <= 0)).len().alias("unitid_nonpos"))
        if checks:
            cvals = pl.scan_parquet(dest).select(checks).collect().to_dicts()[0]
            for cname, cval in cvals.items():
                assert cval == 0, f"STOP: identifier check {cname}={cval} for {key}"

        # --- parquet sha256 + provenance ---
        p_hasher = hashlib.sha256()
        with dest.open("rb") as fh:
            while True:
                c = fh.read(CHUNK_BYTES)
                if not c:
                    break
                p_hasher.update(c)
        csv_path.unlink()  # free scratch immediately
        provenance_records.append({
            "canonical_object_key": key, "source": source, "object_kind": kind,
            "relative_path": rel, "filename": Path(rel).name,
            "provenance": "fetched-2026-08-06", "classification": row["classification"],
            "source_url": url, "source_content_length": (int(resp_len) if resp_len else written),
            "source_last_modified": resp_lastmod or row["current_last_modified"],
            "source_etag": resp_etag or expected_etag, "source_sha256": source_sha256,
            "shipped_bytes": dest.stat().st_size, "shipped_sha256": p_hasher.hexdigest(),
            "row_count": row_count, "column_count": col_count,
            "verification_method": "csv_fetch_convert_identifier_contract",
            "verification_result": "PASS", "action": "fetched_converted",
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        print(f"  [ok] converted: {row_count:,} rows x {col_count} cols, {dest.stat().st_size:,} B, views={view_fields}")
        time.sleep(POLITE_SLEEP_SECONDS)

    except Exception as exc:
        # INTENT: record the failure and keep going. REASONING: an Urban outage should not
        # abort objects that would otherwise succeed; a `_a` revision resumes the remainder.
        # ASSUMES: partial scratch/dest artifacts are cleaned so resume re-fetches cleanly.
        failures.append({"canonical_object_key": key, "error": f"{type(exc).__name__}: {exc}"})
        if dest.exists():
            dest.unlink()
        print(f"  [FAIL] {key}: {type(exc).__name__}: {exc}")
        time.sleep(POLITE_SLEEP_SECONDS)

# --- Validate + Save provenance ---
prov = pl.from_dicts(provenance_records, infer_schema_length=None)
print(f"\nProvenance rows: {prov.height} (target 39)")
print(prov.group_by("provenance", "object_kind").len().sort("provenance", "object_kind"))
prov.write_parquet(FETCHED_PROV_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL)
print(f"Saved: {FETCHED_PROV_PATH}")

if failures:
    print(f"\n[INCOMPLETE] {len(failures)} object(s) failed (likely Urban availability):")
    for f in failures:
        print(f"  - {f['canonical_object_key']}: {f['error']}")
    print("Re-run to resume via: bash /daaf/scripts/create_script_revision.sh "
          "/daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2.py "
          "/daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2_a.py")
    raise SystemExit(1)

assert prov.height == 39, f"STOP: expected 39 fetched/staged rows, got {prov.height}"
assert (prov["verification_result"] == "PASS").all(), "STOP: non-PASS verification present"
print("CHECKPOINT MA-BUILD-06: PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-06 20:19:27
# Command: python3 /daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2.py
# Duration: 313s
# Exit code: 1
#
# --- STDOUT ---
# fetch-fresh objects: 39 (expected 39)
#   July-staged (copy as-is): 8 (expected 8)
#   Fresh fetch from Urban:   31 (expected 31)
#     fresh DATA:     28 (expected 28)
#     fresh CODEBOOK: 3 (expected 3)
# [staged] ccd/schools_ccd_enrollment_2024: 18,349,935 rows, 16,638,298 B
# [staged] ccd/schools_ccd_lea_enrollment_2024: 6,356,502 rows, 5,222,694 B
# [staged] ipeds/colleges_ipeds_fall-enrollment-age_2021: 1,204,011 rows, 1,421,252 B
# [staged] ipeds/colleges_ipeds_fall-enrollment-age_2022: 588,150 rows, 819,617 B
# [staged] ipeds/colleges_ipeds_fall-enrollment-age_2023: 1,188,693 rows, 1,425,175 B
# [staged] ipeds/colleges_ipeds_fall-enrollment-age_2024: 575,208 rows, 826,642 B
# [staged] ipeds/colleges_ipeds_fall-enrollment-race_2023: 3,686,080 rows, 2,614,507 B
# [staged] ipeds/colleges_ipeds_fall-enrollment-race_2024: 3,642,656 rows, 2,625,362 B
# 
# ------------------------------------------------------------------------
# [1/31] FETCH data: ccd/districts_ccd_finance
#   [FAIL] ccd/districts_ccd_finance: AssertionError: STOP: identifier check leaid_nonnum=314 for ccd/districts_ccd_finance
# 
# ------------------------------------------------------------------------
# [2/31] FETCH data: ccd/school-districts_lea_directory
#   [FAIL] ccd/school-districts_lea_directory: ComputeError: could not parse `.` as dtype `i64` at column 'supervisory_union_number' (column number 30)
# 
# The current offset in the file is 228 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `.` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
# 
# ------------------------------------------------------------------------
# [3/31] FETCH data: ccd/schools_ccd_directory
#   [FAIL] ccd/schools_ccd_directory: ComputeError: could not parse `505M` as dtype `i64` at column 'phone' (column number 18)
# 
# The current offset in the file is 467248 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `505M` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
# 
# ------------------------------------------------------------------------
# [4/31] FETCH data: crdc/schools_crdc_discipline_k12_2020
#   [FAIL] crdc/schools_crdc_discipline_k12_2020: ComputeError: could not parse `32SOP0199999` as dtype `i64` at column 'crdc_id' (column number 1)
# 
# The current offset in the file is 306532 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `32SOP0199999` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
# 
# ------------------------------------------------------------------------
# [5/31] FETCH data: crdc/schools_crdc_discipline_k12_2021
#   [FAIL] crdc/schools_crdc_discipline_k12_2021: ComputeError: could not parse `25SOP0199979` as dtype `i64` at column 'crdc_id' (column number 1)
# 
# The current offset in the file is 342111 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `25SOP0199979` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
# 
# ------------------------------------------------------------------------
# [6/31] FETCH codebook: ipeds/codebook_colleges_ipeds_completers
#   [ok] codebook fetched: 35,840 B
# 
# ------------------------------------------------------------------------
# [7/31] FETCH codebook: ipeds/codebook_colleges_ipeds_directory
#   [ok] codebook fetched: 97,792 B
# 
# ------------------------------------------------------------------------
# [8/31] FETCH codebook: ipeds/codebook_colleges_ipeds_fall-retention
#   [ok] codebook fetched: 36,352 B
# 
# ------------------------------------------------------------------------
# [9/31] FETCH data: ipeds/colleges_ipeds_academic_libraries
#   [ok] converted: 43,077 rows x 41 cols, 3,421,863 B, views=[]
# 
# ------------------------------------------------------------------------
# [10/31] FETCH data: ipeds/colleges_ipeds_admissions-enrollment
#   [ok] converted: 215,831 rows x 9 cols, 1,499,046 B, views=[]
# 
# ------------------------------------------------------------------------
# [11/31] FETCH data: ipeds/colleges_ipeds_ay_room_board_other
#   [ok] converted: 295,709 rows x 8 cols, 1,273,340 B, views=[]
# 
# ------------------------------------------------------------------------
# [12/31] FETCH data: ipeds/colleges_ipeds_ay_tuition_fees
#   [ok] converted: 668,761 rows x 14 cols, 3,844,239 B, views=[]
# 
# ------------------------------------------------------------------------
# [13/31] FETCH data: ipeds/colleges_ipeds_ay_tuition_firstprof
#   [ok] converted: 50,802 rows x 8 cols, 339,599 B, views=[]
# 
# ------------------------------------------------------------------------
# [14/31] FETCH data: ipeds/colleges_ipeds_completers
#   [ok] converted: 2,228,100 rows x 6 cols, 1,877,469 B, views=[]
# 
# ------------------------------------------------------------------------
# [15/31] FETCH data: ipeds/colleges_ipeds_directory
#   [ok] converted: 343,054 rows x 96 cols, 12,103,192 B, views=[]
# 
# ------------------------------------------------------------------------
# [16/31] FETCH data: ipeds/colleges_ipeds_enrollment-fte
#   [ok] converted: 478,066 rows x 9 cols, 2,586,397 B, views=[]
# 
# ------------------------------------------------------------------------
# [17/31] FETCH data: ipeds/colleges_ipeds_fall-enrollment-race_2020
#   [ok] converted: 3,533,310 rows x 10 cols, 8,647,920 B, views=[]
# 
# ------------------------------------------------------------------------
# [18/31] FETCH data: ipeds/colleges_ipeds_fall-res
#   [ok] converted: 3,503,286 rows x 6 cols, 6,787,818 B, views=[]
# 
# ------------------------------------------------------------------------
# [19/31] FETCH data: ipeds/colleges_ipeds_fall-retention
#   [ok] converted: 278,296 rows x 10 cols, 1,328,459 B, views=[]
# 
# ------------------------------------------------------------------------
# [20/31] FETCH data: ipeds/colleges_ipeds_grad-rates-200pct
#   [ok] converted: 93,088 rows x 17 cols, 1,330,198 B, views=[]
# 
# ------------------------------------------------------------------------
# [21/31] FETCH data: ipeds/colleges_ipeds_grad-rates-pell
#   [ok] converted: 367,628 rows x 12 cols, 2,043,520 B, views=[]
# 
# ------------------------------------------------------------------------
# [22/31] FETCH data: ipeds/colleges_ipeds_institutional-characteristics
#   [ok] converted: 341,751 rows x 126 cols, 5,081,646 B, views=[]
# 
# ------------------------------------------------------------------------
# [23/31] FETCH data: ipeds/colleges_ipeds_py_room_board_other
#   [ok] converted: 108,932 rows x 6 cols, 505,373 B, views=[]
# 
# ------------------------------------------------------------------------
# [24/31] FETCH data: ipeds/colleges_ipeds_py_tuition_cip
#   [ok] converted: 336,814 rows x 15 cols, 2,291,102 B, views=[]
# 
# ------------------------------------------------------------------------
# [25/31] FETCH data: ipeds/colleges_ipeds_salaries_is
#   [ok] converted: 7,932,422 rows x 11 cols, 45,787,304 B, views=[]
# 
# ------------------------------------------------------------------------
# [26/31] FETCH data: ipeds/colleges_ipeds_salaries_nis
#   [ok] converted: 789,768 rows x 6 cols, 5,517,922 B, views=[]
# 
# ------------------------------------------------------------------------
# [27/31] FETCH data: ipeds/colleges_ipeds_student-faculty-ratio
#   [ok] converted: 102,371 rows x 4 cols, 137,473 B, views=[]
# 
# ------------------------------------------------------------------------
# [28/31] FETCH data: saipe/districts_saipe
#   [ok] converted: 382,099 rows x 10 cols, 9,569,592 B, views=[]
# 
# ------------------------------------------------------------------------
# [29/31] FETCH data: ipeds/colleges_ipeds_completions-2digcip_2023
#   [ok] converted: 4,235,250 rows x 9 cols, 2,417,116 B, views=[]
# 
# ------------------------------------------------------------------------
# [30/31] FETCH data: ipeds/colleges_ipeds_completions-6digcip_2023
#   [ok] converted: 9,184,110 rows x 9 cols, 3,579,373 B, views=[]
# 
# ------------------------------------------------------------------------
# [31/31] FETCH data: ipeds/colleges_ipeds_grad-rates
#   [ok] converted: 6,141,988 rows x 18 cols, 33,485,045 B, views=[]
# 
# Provenance rows: 34 (target 39)
# shape: (3, 3)
# ┌────────────────────┬─────────────┬─────┐
# │ provenance         ┆ object_kind ┆ len │
# │ ---                ┆ ---         ┆ --- │
# │ str                ┆ str         ┆ u32 │
# ╞════════════════════╪═════════════╪═════╡
# │ fetched-2026-08-06 ┆ codebook    ┆ 3   │
# │ fetched-2026-08-06 ┆ data        ┆ 23  │
# │ staged-2026-07-21  ┆ data        ┆ 8   │
# └────────────────────┴─────────────┴─────┘
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/build_provenance_fetched.parquet
# 
# [INCOMPLETE] 5 object(s) failed (likely Urban availability):
#   - ccd/districts_ccd_finance: AssertionError: STOP: identifier check leaid_nonnum=314 for ccd/districts_ccd_finance
#   - ccd/school-districts_lea_directory: ComputeError: could not parse `.` as dtype `i64` at column 'supervisory_union_number' (column number 30)
# 
# The current offset in the file is 228 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `.` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
#   - ccd/schools_ccd_directory: ComputeError: could not parse `505M` as dtype `i64` at column 'phone' (column number 18)
# 
# The current offset in the file is 467248 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `505M` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
#   - crdc/schools_crdc_discipline_k12_2020: ComputeError: could not parse `32SOP0199999` as dtype `i64` at column 'crdc_id' (column number 1)
# 
# The current offset in the file is 306532 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `32SOP0199999` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
#   - crdc/schools_crdc_discipline_k12_2021: ComputeError: could not parse `25SOP0199979` as dtype `i64` at column 'crdc_id' (column number 1)
# 
# The current offset in the file is 342111 bytes.
# 
# You might want to try:
# - increasing `infer_schema_length` (e.g. `infer_schema_length=10000`),
# - specifying correct dtype with the `schema_overrides` argument
# - setting `ignore_errors` to `True`,
# - adding `25SOP0199979` to the `null_values` list.
# 
# Original error: ```invalid primitive value found during CSV parsing```
# Re-run to resume via: bash /daaf/scripts/create_script_revision.sh /daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2.py /daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2_a.py
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
