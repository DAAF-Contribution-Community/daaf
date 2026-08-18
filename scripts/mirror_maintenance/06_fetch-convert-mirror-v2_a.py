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

REVISION 06_a — reference-schema reproduction (supersedes the universal id contract in 06):
Run 06 tried to apply a single ncessch=12 / leaid=7 zero-padded-string contract to every fetched
object. Inspection of the old-vintage copies proved the mirror types columns file-by-file (and
even year-by-year): leaid is String in districts_ccd_finance (with legitimately non-numeric
'06D0004' and width-2 values that zfill would corrupt), Int64 in lea_directory; crdc ids are
Int64 in 2020 but String in 2021; and 2020's crdc_id domain has since changed to alphanumeric.
So each fetched DATA object is now typed to reproduce its OWN authoritative reference schema —
its old-vintage copy if it is a revised object, else a same-family tree sibling. The CSV is read
all-String (preserving leading zeros / alphanumerics / sentinels) and each numeric column is cast
to the reference dtype ONLY where the source domain still fits; a revision that changed a column's
domain keeps that column as String rather than nulling real data. The 2 truly-new completions_2023
files already converted cleanly under 06's inference path (consistent with the 8 staged objects)
and are skip-reverified here, not rebuilt.

Urban had a full API outage earlier today (recovered ~19:20 UTC). Fetches use generous
timeouts, retry/backoff, and polite pacing. Per-object network failures are recorded and the
run continues; if any object is left unbuilt the script exits non-zero so a `_a` revision can
resume (idempotent: an already-built, re-validated parquet/xls is skipped, not re-fetched).
"""

# --- Config ---
import csv
import hashlib
import re
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
OLD_VINTAGE_DIR = PROJECT_DIR / "old_vintage_copies"
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

        # --- Inspect header ---
        with csv_path.open("r", encoding="utf-8-sig", newline="") as raw:
            source_columns = next(csv.reader(raw))
        assert source_columns and len(source_columns) == len(set(source_columns)), (
            f"STOP: empty/duplicate CSV header for {key}"
        )

        # --- Resolve a reference schema (faithful mirror-consistent typing) ---
        # INTENT: reproduce the schema the mirror already uses for this object. REASONING: the
        # old mirror types columns file-by-file (even year-by-year: leaid is String in
        # districts_ccd_finance, Int64 in lea_directory; crdc ids Int64 in 2020, String in 2021),
        # so a single universal identifier contract is WRONG and would corrupt data (e.g. zfill on
        # the width-2 / '06D0004' leaid values in districts_ccd_finance). ASSUMES: an old-vintage
        # copy of a revised object, or a same-family tree sibling, is the authoritative schema.
        ref_schema = None
        ref_source = "none"
        ref_path = OLD_VINTAGE_DIR / rel
        if ref_path.exists():
            ref_schema = dict(pl.scan_parquet(ref_path).collect_schema())
            ref_source = f"old-vintage:{rel}"
        else:
            family = re.sub(r"_\d{4}$", "", key)
            siblings = sorted(TREE_DIR.glob(f"{family}_*.parquet"))
            siblings = [s for s in siblings if s != dest]
            if siblings:
                ref_schema = dict(pl.scan_parquet(siblings[0]).collect_schema())
                ref_source = f"tree-sibling:{siblings[0].name}"
        print(f"  schema reference: {ref_source}")

        # --- Convert CSV -> parquet (all-String read, then data-preserving cast to reference) ---
        # INTENT: read every column as text (preserves leading zeros, alphanumerics, sentinels),
        # then cast numeric columns to the reference dtype ONLY when the source domain still fits;
        # if the revision changed a column's domain (a non-missing value fails the cast, e.g. the
        # now-alphanumeric crdc_id), keep it as String rather than silently nulling real data.
        # REASONING: this reproduces the mirror's per-file schema without guessing missing tokens
        # and never destroys populated cells. ASSUMES: "" and "." denote missing for numeric casts;
        # -1/-2/-3 are valid sentinels and are preserved (they cast cleanly to their integer form).
        polars_tmp = CSV_SCRATCH / f"{safe}.polars.parquet"
        if polars_tmp.exists():
            polars_tmp.unlink()
        MISSING_TOKENS = ["", "."]
        lazy_str = pl.scan_csv(
            csv_path, has_header=True, separator=",", quote_char='"',
            infer_schema_length=0,  # 0 => every column parsed as String (Utf8)
            ignore_errors=False, try_parse_dates=False, low_memory=True, rechunk=False, encoding="utf8",
        )
        # Guard pass: for each numeric-target column, count non-missing values that fail the cast.
        numeric_targets = {}
        guard_exprs = []
        for col in source_columns:
            tgt = ref_schema.get(col) if ref_schema else None
            if tgt is not None and tgt != pl.String:
                numeric_targets[col] = tgt
                guard_exprs.append(
                    (pl.col(col).is_not_null()
                     & ~pl.col(col).is_in(MISSING_TOKENS)
                     & pl.col(col).cast(tgt, strict=False).is_null()).sum().alias(col)
                )
        guard_counts = lazy_str.select(guard_exprs).collect().to_dicts()[0] if guard_exprs else {}
        cast_exprs = []
        kept_string_due_to_change = []
        for col, tgt in numeric_targets.items():
            if guard_counts.get(col, 0) > 0:
                kept_string_due_to_change.append(col)  # revision changed domain; preserve as text
            else:
                cast_exprs.append(pl.col(col).cast(tgt, strict=False).alias(col))
        lazy_final = lazy_str.with_columns(cast_exprs) if cast_exprs else lazy_str
        lazy_final.sink_parquet(
            polars_tmp, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS, row_group_size=PARQUET_ROW_GROUP_SIZE,
            maintain_order=True, engine="streaming", mkdir=True,
        )
        if kept_string_due_to_change:
            print(f"  [note] kept as String (revision changed domain): {kept_string_due_to_change}")

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
        # --- Schema-consistency check vs the reference (replaces the wrong universal id contract) ---
        # INTENT: confirm the built file reproduces the mirror's reference dtype for every column
        # whose domain was unchanged, and only diverges (to String) where a value could not cast.
        # REASONING: for revised objects the right correctness test is parity with the object's own
        # prior vintage, not an invented width rule. ASSUMES: kept_string_due_to_change captures every
        # intentional divergence; any other dtype mismatch is a real defect and STOPs.
        dtype_mismatches = []
        if ref_schema:
            final_by_name = {f.name: str(f.type) for f in final_schema}
            for col in source_columns:
                tgt = ref_schema.get(col)
                if tgt is None or col in kept_string_due_to_change:
                    continue
                # numeric targets should now match; String targets ship as arrow 'string'
                built = final_by_name[col]
                want_str = (tgt == pl.String and built != "string")
                want_num = (tgt != pl.String and built == "string")
                if want_str or want_num:
                    dtype_mismatches.append((col, str(tgt), built))
        assert not dtype_mismatches, f"STOP: unexpected dtype divergence for {key}: {dtype_mismatches[:8]}"

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
            "verification_method": "csv_fetch_convert_reference_schema_cast",
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
# Executed: 2026-08-06 20:32:27
# Command: python3 /daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2_a.py
# Duration: 174s
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
#   schema reference: old-vintage:ccd/districts_ccd_finance.parquet
#   [FAIL] ccd/districts_ccd_finance: AssertionError: STOP: unexpected dtype divergence for ccd/districts_ccd_finance: [('leaid', 'String', 'large_string')]
# 
# ------------------------------------------------------------------------
# [2/31] FETCH data: ccd/school-districts_lea_directory
#   schema reference: old-vintage:ccd/school-districts_lea_directory.parquet
#   [FAIL] ccd/school-districts_lea_directory: AssertionError: STOP: unexpected dtype divergence for ccd/school-districts_lea_directory: [('lea_name', 'String', 'large_string'), ('state_leaid', 'String', 'large_string'), ('street_mailing', 'String', 'large_string'), ('city_mailing', 'String', 'large_string'), ('state_mailing', 'String', 'large_string'), ('zip4_mailing', 'String', 'large_string'), ('street_location', 'String', 'large_string'), ('city_location', 'String', 'large_string')]
# 
# ------------------------------------------------------------------------
# [3/31] FETCH data: ccd/schools_ccd_directory
#   schema reference: old-vintage:ccd/schools_ccd_directory.parquet
#   [FAIL] ccd/schools_ccd_directory: AssertionError: STOP: unexpected dtype divergence for ccd/schools_ccd_directory: [('ncessch', 'String', 'large_string'), ('school_name', 'String', 'large_string'), ('leaid', 'String', 'large_string'), ('lea_name', 'String', 'large_string'), ('state_leaid', 'String', 'large_string'), ('seasch', 'String', 'large_string'), ('street_mailing', 'String', 'large_string'), ('city_mailing', 'String', 'large_string')]
# 
# ------------------------------------------------------------------------
# [4/31] FETCH data: crdc/schools_crdc_discipline_k12_2020
#   schema reference: old-vintage:crdc/schools_crdc_discipline_k12_2020.parquet
#   [note] kept as String (revision changed domain): ['crdc_id', 'leaid']
#   [ok] converted: 8,196,300 rows x 20 cols, 4,390,585 B, views=[]
# 
# ------------------------------------------------------------------------
# [5/31] FETCH data: crdc/schools_crdc_discipline_k12_2021
#   schema reference: old-vintage:crdc/schools_crdc_discipline_k12_2021.parquet
#   [FAIL] crdc/schools_crdc_discipline_k12_2021: AssertionError: STOP: unexpected dtype divergence for crdc/schools_crdc_discipline_k12_2021: [('crdc_id', 'String', 'large_string'), ('ncessch', 'String', 'large_string'), ('leaid', 'String', 'large_string')]
# 
# ------------------------------------------------------------------------
# [6/31] FETCH codebook: ipeds/codebook_colleges_ipeds_completers
#   [skip] already built codebook: 35,840 B
# 
# ------------------------------------------------------------------------
# [7/31] FETCH codebook: ipeds/codebook_colleges_ipeds_directory
#   [skip] already built codebook: 97,792 B
# 
# ------------------------------------------------------------------------
# [8/31] FETCH codebook: ipeds/codebook_colleges_ipeds_fall-retention
#   [skip] already built codebook: 36,352 B
# 
# ------------------------------------------------------------------------
# [9/31] FETCH data: ipeds/colleges_ipeds_academic_libraries
#   [skip] already built: 43,077 rows
# 
# ------------------------------------------------------------------------
# [10/31] FETCH data: ipeds/colleges_ipeds_admissions-enrollment
#   [skip] already built: 215,831 rows
# 
# ------------------------------------------------------------------------
# [11/31] FETCH data: ipeds/colleges_ipeds_ay_room_board_other
#   [skip] already built: 295,709 rows
# 
# ------------------------------------------------------------------------
# [12/31] FETCH data: ipeds/colleges_ipeds_ay_tuition_fees
#   [skip] already built: 668,761 rows
# 
# ------------------------------------------------------------------------
# [13/31] FETCH data: ipeds/colleges_ipeds_ay_tuition_firstprof
#   [skip] already built: 50,802 rows
# 
# ------------------------------------------------------------------------
# [14/31] FETCH data: ipeds/colleges_ipeds_completers
#   [skip] already built: 2,228,100 rows
# 
# ------------------------------------------------------------------------
# [15/31] FETCH data: ipeds/colleges_ipeds_directory
#   [skip] already built: 343,054 rows
# 
# ------------------------------------------------------------------------
# [16/31] FETCH data: ipeds/colleges_ipeds_enrollment-fte
#   [skip] already built: 478,066 rows
# 
# ------------------------------------------------------------------------
# [17/31] FETCH data: ipeds/colleges_ipeds_fall-enrollment-race_2020
#   [skip] already built: 3,533,310 rows
# 
# ------------------------------------------------------------------------
# [18/31] FETCH data: ipeds/colleges_ipeds_fall-res
#   [skip] already built: 3,503,286 rows
# 
# ------------------------------------------------------------------------
# [19/31] FETCH data: ipeds/colleges_ipeds_fall-retention
#   [skip] already built: 278,296 rows
# 
# ------------------------------------------------------------------------
# [20/31] FETCH data: ipeds/colleges_ipeds_grad-rates-200pct
#   [skip] already built: 93,088 rows
# 
# ------------------------------------------------------------------------
# [21/31] FETCH data: ipeds/colleges_ipeds_grad-rates-pell
#   [skip] already built: 367,628 rows
# 
# ------------------------------------------------------------------------
# [22/31] FETCH data: ipeds/colleges_ipeds_institutional-characteristics
#   [skip] already built: 341,751 rows
# 
# ------------------------------------------------------------------------
# [23/31] FETCH data: ipeds/colleges_ipeds_py_room_board_other
#   [skip] already built: 108,932 rows
# 
# ------------------------------------------------------------------------
# [24/31] FETCH data: ipeds/colleges_ipeds_py_tuition_cip
#   [skip] already built: 336,814 rows
# 
# ------------------------------------------------------------------------
# [25/31] FETCH data: ipeds/colleges_ipeds_salaries_is
#   [skip] already built: 7,932,422 rows
# 
# ------------------------------------------------------------------------
# [26/31] FETCH data: ipeds/colleges_ipeds_salaries_nis
#   [skip] already built: 789,768 rows
# 
# ------------------------------------------------------------------------
# [27/31] FETCH data: ipeds/colleges_ipeds_student-faculty-ratio
#   [skip] already built: 102,371 rows
# 
# ------------------------------------------------------------------------
# [28/31] FETCH data: saipe/districts_saipe
#   [skip] already built: 382,099 rows
# 
# ------------------------------------------------------------------------
# [29/31] FETCH data: ipeds/colleges_ipeds_completions-2digcip_2023
#   [skip] already built: 4,235,250 rows
# 
# ------------------------------------------------------------------------
# [30/31] FETCH data: ipeds/colleges_ipeds_completions-6digcip_2023
#   [skip] already built: 9,184,110 rows
# 
# ------------------------------------------------------------------------
# [31/31] FETCH data: ipeds/colleges_ipeds_grad-rates
#   [skip] already built: 6,141,988 rows
# 
# Provenance rows: 35 (target 39)
# shape: (3, 3)
# ┌────────────────────┬─────────────┬─────┐
# │ provenance         ┆ object_kind ┆ len │
# │ ---                ┆ ---         ┆ --- │
# │ str                ┆ str         ┆ u32 │
# ╞════════════════════╪═════════════╪═════╡
# │ fetched-2026-08-06 ┆ codebook    ┆ 3   │
# │ fetched-2026-08-06 ┆ data        ┆ 24  │
# │ staged-2026-07-21  ┆ data        ┆ 8   │
# └────────────────────┴─────────────┴─────┘
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/build_provenance_fetched.parquet
# 
# [INCOMPLETE] 4 object(s) failed (likely Urban availability):
#   - ccd/districts_ccd_finance: AssertionError: STOP: unexpected dtype divergence for ccd/districts_ccd_finance: [('leaid', 'String', 'large_string')]
#   - ccd/school-districts_lea_directory: AssertionError: STOP: unexpected dtype divergence for ccd/school-districts_lea_directory: [('lea_name', 'String', 'large_string'), ('state_leaid', 'String', 'large_string'), ('street_mailing', 'String', 'large_string'), ('city_mailing', 'String', 'large_string'), ('state_mailing', 'String', 'large_string'), ('zip4_mailing', 'String', 'large_string'), ('street_location', 'String', 'large_string'), ('city_location', 'String', 'large_string')]
#   - ccd/schools_ccd_directory: AssertionError: STOP: unexpected dtype divergence for ccd/schools_ccd_directory: [('ncessch', 'String', 'large_string'), ('school_name', 'String', 'large_string'), ('leaid', 'String', 'large_string'), ('lea_name', 'String', 'large_string'), ('state_leaid', 'String', 'large_string'), ('seasch', 'String', 'large_string'), ('street_mailing', 'String', 'large_string'), ('city_mailing', 'String', 'large_string')]
#   - crdc/schools_crdc_discipline_k12_2021: AssertionError: STOP: unexpected dtype divergence for crdc/schools_crdc_discipline_k12_2021: [('crdc_id', 'String', 'large_string'), ('ncessch', 'String', 'large_string'), ('leaid', 'String', 'large_string')]
# Re-run to resume via: bash /daaf/scripts/create_script_revision.sh /daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2.py /daaf/scripts/mirror_maintenance/06_fetch-convert-mirror-v2_a.py
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
