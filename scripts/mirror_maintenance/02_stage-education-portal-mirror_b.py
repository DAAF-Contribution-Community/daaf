#!/usr/bin/env python3
"""
Mirror maintenance 2/3: locally stage approved Urban CSV gaps as Parquet.

Task: stage-education-portal-mirror
Lifecycle: local audit and staging only
Depends on: successful MA1 durable reconciliation manifest
Input: eight dynamically selected Urban CSV objects within the approved safety envelope
Outputs: staged Parquet objects plus provenance, field/schema, schema-drift, and
         identifier/value-domain Parquet manifests
Checkpoint: MA2

Network operations are read-only GET, HEAD, and Range requests. Source CSV bytes
exist only as partial scratch files inside the project and are removed in `finally`.
"""

import csv
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import requests

# --- Config ---
# This section binds staging to the MA1 artifact and repeats the user-approved
# allowlist/count/byte gates as defense in depth. Stable Parquet settings are fixed
# here so every object uses the same materialized-string, Zstandard level-3 policy.
BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-07-21_FrameworkDev_EducationPortalSkills"
STAGING_ROOT = PROJECT_DIR / "2026-07-21_education-portal-mirror-staging"
CATALOG_DIR = STAGING_ROOT / "catalog"
STAGED_DATA_DIR = STAGING_ROOT / "staged"
SCRATCH_DIR = STAGING_ROOT / "scratch"
MANIFEST_DIR = STAGING_ROOT / "manifests"
DATE_PREFIX = "2026-07-21"

OBJECT_MANIFEST_PATH = CATALOG_DIR / f"{DATE_PREFIX}_mirror-object-reconciliation.parquet"
STAGING_MANIFEST_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_staging-provenance-manifest.parquet"
FIELD_SCHEMA_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_field-schema-manifest.parquet"
SCHEMA_COMPARISON_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_prior-year-schema-comparison.parquet"
IDENTIFIER_SUMMARY_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_identifier-value-domain-summary.parquet"

EXPECTED_MISSING_KEYS = {
    "ccd/schools_ccd_enrollment_2024",
    "ccd/schools_ccd_lea_enrollment_2024",
    "ipeds/colleges_ipeds_fall-enrollment-age_2021",
    "ipeds/colleges_ipeds_fall-enrollment-age_2022",
    "ipeds/colleges_ipeds_fall-enrollment-age_2023",
    "ipeds/colleges_ipeds_fall-enrollment-age_2024",
    "ipeds/colleges_ipeds_fall-enrollment-race_2023",
    "ipeds/colleges_ipeds_fall-enrollment-race_2024",
}
MAX_OBJECTS = 8
MAX_EXACT_SOURCE_BYTES = 1_500_000_000
REQUEST_CONNECT_TIMEOUT_SECONDS = 60
REQUEST_READ_TIMEOUT_SECONDS = 600
DOWNLOAD_CHUNK_BYTES = 8 * 1024 * 1024
PRIOR_FOOTER_MAX_BYTES = 16 * 1024 * 1024
PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3
PARQUET_ROW_GROUP_SIZE = 100_000
PARQUET_STATISTICS = True

# --- Load ---
# Load the durable audit output independently. Staging selection is an anti-filter
# over `comparison_status`, never a hard-coded list of URLs or file sizes.
print("=" * 80)
print("MIRROR MAINTENANCE 2/3: BOUNDED LOCAL STAGING")
print("=" * 80)
assert OBJECT_MANIFEST_PATH.exists(), f"STOP: MA1 manifest missing: {OBJECT_MANIFEST_PATH}"
reconciliation = pl.read_parquet(OBJECT_MANIFEST_PATH)
print(f"Loaded reconciliation: {reconciliation.height:,} rows x {reconciliation.width} columns")

# INTENT: derive the current staging set from MA1's observed Urban-only data rows.
# REASONING: the allowlist validates the result after derivation; it does not create
# the result. ASSUMES: MA1 recorded exact source sizes for every selected object.
to_stage = reconciliation.filter(
    (pl.col("comparison_status") == "urban_only") & (pl.col("object_kind") == "data")
).sort("canonical_object_key")
derived_keys = set(to_stage["canonical_object_key"].to_list())
derived_exact_bytes = int(to_stage["source_exact_bytes"].sum())

assert derived_keys == EXPECTED_MISSING_KEYS, (
    "STOP: MA1 staging set differs from approved allowlist; "
    f"unexpected={sorted(derived_keys - EXPECTED_MISSING_KEYS)}, "
    f"no_longer_missing={sorted(EXPECTED_MISSING_KEYS - derived_keys)}"
)
assert to_stage.height <= MAX_OBJECTS, "STOP: staging object count exceeds cap"
assert derived_exact_bytes <= MAX_EXACT_SOURCE_BYTES, "STOP: staging byte total exceeds cap"
assert to_stage["source_exact_bytes"].null_count() == 0, "STOP: selected object lacks exact size"
print(f"[PASS] Derived allowlisted staging set: {to_stage.height} objects")
print(f"[PASS] Exact source bytes: {derived_exact_bytes:,} <= {MAX_EXACT_SOURCE_BYTES:,}")

STAGED_DATA_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers.update(
    {
        "User-Agent": "DAAF-local-mirror-stage/1.0",
        "Accept-Encoding": "identity",
    }
)

# Load any object-level checkpoints left by an earlier versioned attempt. A record is
# trusted only after its staged hash is recomputed below; this avoids blind transfer
# repetition while preserving the immutable-script lifecycle.
staging_records = (
    pl.read_parquet(STAGING_MANIFEST_PATH).to_dicts() if STAGING_MANIFEST_PATH.exists() else []
)
field_records = pl.read_parquet(FIELD_SCHEMA_PATH).to_dicts() if FIELD_SCHEMA_PATH.exists() else []
schema_comparison_records = (
    pl.read_parquet(SCHEMA_COMPARISON_PATH).to_dicts() if SCHEMA_COMPARISON_PATH.exists() else []
)
identifier_records = (
    pl.read_parquet(IDENTIFIER_SUMMARY_PATH).to_dicts() if IDENTIFIER_SUMMARY_PATH.exists() else []
)
checkpoint_by_key = {record["canonical_object_key"]: record for record in staging_records}

# --- Recover predecessor's completed conversion ---
# INTENT: recover the first attempt's fully written Parquet object after its later
# year-shape assertion failed, instead of repeating a verified 930 MB transfer.
# REASONING: the predecessor execution log proves exact source bytes/SHA-256 and
# reached the year assertion only after Parquet magic, schema, row/column, and
# Arrow-view checks passed. This revision independently rehashes/revalidates the
# staged bytes and completes the missing manifests before treating it as a checkpoint.
# ASSUMES: only the known first allowlisted object can be an unmanifested predecessor
# output; any other orphan staged file remains a fail-closed condition in the main loop.
PREDECESSOR_SCRIPT_PATH = BASE_DIR / "scripts" / "mirror_maintenance" / "02_stage-education-portal-mirror.py"
RECOVERABLE_KEY = "ccd/schools_ccd_enrollment_2024"
recoverable_path = STAGED_DATA_DIR / f"{RECOVERABLE_KEY}.parquet"
if recoverable_path.exists() and RECOVERABLE_KEY not in checkpoint_by_key:
    predecessor_text = PREDECESSOR_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "FAILED: Script returned exit code 1" not in predecessor_text  # wrapper does not append this banner
    assert "AssertionError: STOP: year shard mismatch" in predecessor_text, (
        "STOP: predecessor failure was not the expected post-conversion year-shape assertion"
    )
    source_hash_matches = re.findall(
        r"\[PASS\] Transfer bytes/hash: 930,870,805 / ([0-9a-f]{64})",
        predecessor_text,
    )
    assert len(source_hash_matches) == 1, "STOP: predecessor source hash evidence is ambiguous"
    recovered_source_sha256 = source_hash_matches[0]
    recovery_source_record = to_stage.filter(
        pl.col("canonical_object_key") == RECOVERABLE_KEY
    ).row(0, named=True)
    recovery_year = recovery_source_record["year_shard"]

    # INTENT: prove the recovered Parquet has intact magic/footer, readable metadata,
    # materialized Arrow types, exact year, and protected CCD identifier domains.
    # REASONING: these independent checks make recovery evidence at least as strong
    # as a normal post-conversion checkpoint. ASSUMES: schema columns are the exact
    # CSV columns because the predecessor passed its column-name/order assertions.
    with recoverable_path.open("rb") as recovered_file:
        recovered_leading_magic = recovered_file.read(4)
        recovered_file.seek(-4, 2)
        recovered_trailing_magic = recovered_file.read(4)
    assert recovered_leading_magic == b"PAR1" and recovered_trailing_magic == b"PAR1"
    recovered_parquet = pq.ParquetFile(recoverable_path)
    recovered_schema = recovered_parquet.schema_arrow
    assert recovered_parquet.metadata.num_rows > 0
    assert not any(
        pa.types.is_string_view(field.type) or pa.types.is_binary_view(field.type)
        for field in recovered_schema
    )
    recovered_validation = pl.scan_parquet(recoverable_path).select(
        pl.col("year").drop_nulls().unique().sort().alias("year_values"),
        pl.col("ncessch")
        .filter(
            pl.col("ncessch").is_not_null()
            & ~pl.col("ncessch").is_in(["", "-1", "-2", "-3"])
            & (pl.col("ncessch").str.len_chars() != 12)
        )
        .len()
        .alias("ncessch__invalid_width_count"),
        pl.col("ncessch")
        .filter(
            pl.col("ncessch").is_not_null()
            & ~pl.col("ncessch").is_in(["", "-1", "-2", "-3"])
            & ~pl.col("ncessch").str.contains(r"^\d+$")
        )
        .len()
        .alias("ncessch__nonnumeric_count"),
        pl.col("ncessch").null_count().alias("ncessch__null_count"),
        pl.col("ncessch").filter(pl.col("ncessch").is_in(["-1", "-2", "-3"])).len().alias(
            "ncessch__sentinel_count"
        ),
        pl.col("ncessch")
        .filter(pl.col("ncessch").is_not_null() & ~pl.col("ncessch").is_in(["", "-1", "-2", "-3"]))
        .str.len_chars()
        .min()
        .alias("ncessch__min_width"),
        pl.col("ncessch")
        .filter(pl.col("ncessch").is_not_null() & ~pl.col("ncessch").is_in(["", "-1", "-2", "-3"]))
        .str.len_chars()
        .max()
        .alias("ncessch__max_width"),
        pl.col("ncessch").n_unique().alias("ncessch__n_unique"),
        pl.col("leaid")
        .filter(
            pl.col("leaid").is_not_null()
            & ~pl.col("leaid").is_in(["", "-1", "-2", "-3"])
            & (pl.col("leaid").str.len_chars() != 7)
        )
        .len()
        .alias("leaid__invalid_width_count"),
        pl.col("leaid")
        .filter(
            pl.col("leaid").is_not_null()
            & ~pl.col("leaid").is_in(["", "-1", "-2", "-3"])
            & ~pl.col("leaid").str.contains(r"^\d+$")
        )
        .len()
        .alias("leaid__nonnumeric_count"),
        pl.col("leaid").null_count().alias("leaid__null_count"),
        pl.col("leaid").filter(pl.col("leaid").is_in(["-1", "-2", "-3"])).len().alias(
            "leaid__sentinel_count"
        ),
        pl.col("leaid")
        .filter(pl.col("leaid").is_not_null() & ~pl.col("leaid").is_in(["", "-1", "-2", "-3"]))
        .str.len_chars()
        .min()
        .alias("leaid__min_width"),
        pl.col("leaid")
        .filter(pl.col("leaid").is_not_null() & ~pl.col("leaid").is_in(["", "-1", "-2", "-3"]))
        .str.len_chars()
        .max()
        .alias("leaid__max_width"),
        pl.col("leaid").n_unique().alias("leaid__n_unique"),
    ).collect().to_dicts()[0]
    recovered_year_raw = recovered_validation["year_values"]
    recovered_year_values = (
        recovered_year_raw
        if isinstance(recovered_year_raw, list)
        else ([] if recovered_year_raw is None else [recovered_year_raw])
    )
    assert recovered_year_values == [recovery_year]
    assert recovered_validation["ncessch__invalid_width_count"] == 0
    assert recovered_validation["ncessch__nonnumeric_count"] == 0
    assert recovered_validation["leaid__invalid_width_count"] == 0
    assert recovered_validation["leaid__nonnumeric_count"] == 0

    recovered_hasher = hashlib.sha256()
    with recoverable_path.open("rb") as recovered_file:
        while True:
            chunk = recovered_file.read(DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            recovered_hasher.update(chunk)
    recovered_staged_sha256 = recovered_hasher.hexdigest()

    # INTENT: compare the recovered schema to the closest mirrored prior year using
    # only bounded footer Range requests. REASONING: schema metadata lives in the
    # footer, so no prior-year row groups need downloading.
    recovery_prior_candidates = reconciliation.filter(
        (pl.col("bulk_family_key") == recovery_source_record["bulk_family_key"])
        & pl.col("year_shard").is_not_null()
        & (pl.col("year_shard") < recovery_year)
        & pl.col("present_hf")
        & pl.col("hf_url").is_not_null()
    ).sort("year_shard", descending=True)
    assert recovery_prior_candidates.height > 0, "STOP: no prior year for recovered schema comparison"
    recovery_prior = recovery_prior_candidates.row(0, named=True)
    recovery_prior_head = session.head(
        recovery_prior["hf_url"],
        allow_redirects=True,
        timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
    )
    recovery_prior_head.raise_for_status()
    recovery_prior_size = int(recovery_prior_head.headers["Content-Length"])
    recovery_footer_response = session.get(
        recovery_prior["hf_url"],
        headers={
            "Range": f"bytes={recovery_prior_size - 8}-{recovery_prior_size - 1}",
            "Accept-Encoding": "identity",
        },
        timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
    )
    assert recovery_footer_response.status_code == 206
    recovery_footer = recovery_footer_response.content
    assert len(recovery_footer) == 8 and recovery_footer[4:] == b"PAR1"
    recovery_metadata_length = struct.unpack("<I", recovery_footer[:4])[0]
    assert 0 < recovery_metadata_length <= PRIOR_FOOTER_MAX_BYTES
    recovery_metadata_start = recovery_prior_size - 8 - recovery_metadata_length
    recovery_metadata_response = session.get(
        recovery_prior["hf_url"],
        headers={
            "Range": f"bytes={recovery_metadata_start}-{recovery_prior_size - 9}",
            "Accept-Encoding": "identity",
        },
        timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
    )
    assert recovery_metadata_response.status_code == 206
    recovery_metadata_bytes = recovery_metadata_response.content
    assert len(recovery_metadata_bytes) == recovery_metadata_length
    recovery_prior_metadata = pq.read_metadata(
        pa.BufferReader(b"PAR1" + recovery_metadata_bytes + recovery_footer)
    )
    recovery_prior_schema = recovery_prior_metadata.schema.to_arrow_schema()
    recovered_types = {
        field.name: str(field.type).replace("string_view", "string").replace("binary_view", "binary")
        for field in recovered_schema
    }
    recovery_prior_types = {
        field.name: str(field.type).replace("string_view", "string").replace("binary_view", "binary")
        for field in recovery_prior_schema
    }
    recovery_added = [name for name in recovered_schema.names if name not in recovery_prior_types]
    recovery_removed = [name for name in recovery_prior_schema.names if name not in recovered_types]
    recovery_type_changes = [
        f"{name}:{recovery_prior_types[name]}->{recovered_types[name]}"
        for name in recovered_schema.names
        if name in recovery_prior_types and recovery_prior_types[name] != recovered_types[name]
    ]
    # INTENT: distinguish deliberate identifier-protection changes from unexplained
    # conversion drift. REASONING: prior HF CCD Parquet stores ncessch/leaid as
    # int64, but this lifecycle is explicitly required to preserve canonical widths;
    # forcing those observed CSV fields to strings is therefore a validated safety
    # correction. ASSUMES: only ncessch/leaid may change from an integer prior type
    # to materialized string; every other type change remains fail-closed.
    recovery_intentional_identifier_changes = [
        change
        for change in recovery_type_changes
        if change.split(":", 1)[0] in {"ncessch", "leaid"}
        and change.split("->", 1)[0].endswith(("int64", "int32"))
        and change.split("->", 1)[1] in {"string", "large_string"}
    ]
    recovery_unexpected_type_changes = [
        change for change in recovery_type_changes if change not in recovery_intentional_identifier_changes
    ]
    assert not recovery_unexpected_type_changes, (
        f"STOP: recovered prior-year type drift requires review: {recovery_unexpected_type_changes}"
    )
    if recovery_intentional_identifier_changes:
        recovery_prior_status = "INTENTIONAL_IDENTIFIER_PROTECTION_TYPE_CHANGE"
    elif recovery_added and recovery_removed:
        recovery_prior_status = "SOURCE_NEW_AND_REMOVED_COLUMN_DRIFT"
    elif recovery_added:
        recovery_prior_status = "SOURCE_NEW_COLUMN_DRIFT"
    elif recovery_removed:
        recovery_prior_status = "SOURCE_REMOVED_COLUMN_DRIFT"
    else:
        recovery_prior_status = "MATCH_PRIOR_YEAR_SCHEMA"

    recovered_field_rows = [
        {
            "canonical_object_key": RECOVERABLE_KEY,
            "year_shard": recovery_year,
            "field_ordinal": ordinal,
            "field_name": field.name,
            "arrow_type": str(field.type),
            "nullable": field.nullable,
            "source_csv_column_present": True,
            "identifier_override_applied": field.name in ["ncessch", "leaid"],
            "arrow_view_type": False,
            "view_materialization_action": "recovered_no_view_types_observed_materialized_schema_retained",
            "validation_status": "PASS",
        }
        for ordinal, field in enumerate(recovered_schema)
    ]
    recovered_identifier_rows = []
    for recovered_identifier, recovered_width in [("ncessch", 12), ("leaid", 7)]:
        recovered_identifier_rows.append(
            {
                "canonical_object_key": RECOVERABLE_KEY,
                "year_shard": recovery_year,
                "identifier_column": recovered_identifier,
                "staged_arrow_type": str(recovered_schema.field(recovered_identifier).type),
                "expected_rule": f"string digits width {recovered_width}; null/-1/-2/-3 excluded",
                "null_count": recovered_validation[f"{recovered_identifier}__null_count"],
                "sentinel_count": recovered_validation[f"{recovered_identifier}__sentinel_count"],
                "invalid_width_count": recovered_validation[f"{recovered_identifier}__invalid_width_count"],
                "nonnumeric_or_nonpositive_count": recovered_validation[f"{recovered_identifier}__nonnumeric_count"],
                "min_width_or_value": str(recovered_validation[f"{recovered_identifier}__min_width"]),
                "max_width_or_value": str(recovered_validation[f"{recovered_identifier}__max_width"]),
                "n_unique_including_null": recovered_validation[f"{recovered_identifier}__n_unique"],
                "observed_year_values": recovered_year_values,
                "year_validation_status": "PASS",
                "validation_status": "PASS",
            }
        )
    recovered_schema_summary = json.dumps(
        [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in recovered_schema],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    recovered_staging_record = {
        "canonical_object_key": RECOVERABLE_KEY,
        "bulk_family_key": recovery_source_record["bulk_family_key"],
        "year_shard": recovery_year,
        "urban_path": recovery_source_record["urban_path"],
        "source_url": recovery_source_record["urban_url"],
        "urban_manifest_ids": recovery_source_record["urban_manifest_ids"],
        "endpoint_ids": recovery_source_record["endpoint_ids"],
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_http_status": 200,
        "source_etag": recovery_source_record["source_etag"],
        "source_last_modified": recovery_source_record["source_last_modified"],
        "source_content_range": "recovered from predecessor exact full-body transfer",
        "source_exact_bytes": int(recovery_source_record["source_exact_bytes"]),
        "source_sha256": recovered_source_sha256,
        "staged_path": str(recoverable_path),
        "staged_sha256": recovered_staged_sha256,
        "row_count": recovered_parquet.metadata.num_rows,
        "column_count": recovered_parquet.metadata.num_columns,
        "schema_summary_json": recovered_schema_summary,
        "field_schema_manifest_path": str(FIELD_SCHEMA_PATH),
        "identifier_summary_manifest_path": str(IDENTIFIER_SUMMARY_PATH),
        "prior_schema_status": recovery_prior_status,
        "view_materialization_action": "recovered_no_view_types_observed_materialized_schema_retained",
        "parquet_compression": PARQUET_COMPRESSION,
        "parquet_compression_level": PARQUET_COMPRESSION_LEVEL,
        "parquet_row_group_size": PARQUET_ROW_GROUP_SIZE,
        "parquet_statistics": PARQUET_STATISTICS,
        "output_bytes": recoverable_path.stat().st_size,
        "year_validation_status": "PASS",
        "validation_status": "PASS",
    }
    recovered_schema_comparison = {
        "canonical_object_key": RECOVERABLE_KEY,
        "year_shard": recovery_year,
        "prior_canonical_object_key": recovery_prior["canonical_object_key"],
        "prior_year_shard": recovery_prior["year_shard"],
        "prior_schema_status": recovery_prior_status,
        "added_columns": recovery_added,
        "removed_columns": recovery_removed,
        "type_changes": recovery_type_changes,
        "prior_schema_bytes_fetched": len(recovery_footer) + len(recovery_metadata_bytes),
        "conversion_column_loss": False,
        "validation_status": "PASS",
    }
    staging_records.append(recovered_staging_record)
    field_records.extend(recovered_field_rows)
    schema_comparison_records.append(recovered_schema_comparison)
    identifier_records.extend(recovered_identifier_rows)
    pl.from_dicts(staging_records, infer_schema_length=None).write_parquet(
        STAGING_MANIFEST_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL
    )
    pl.from_dicts(field_records, infer_schema_length=None).write_parquet(
        FIELD_SCHEMA_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL
    )
    pl.from_dicts(schema_comparison_records, infer_schema_length=None).write_parquet(
        SCHEMA_COMPARISON_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL
    )
    pl.from_dicts(identifier_records, infer_schema_length=None).write_parquet(
        IDENTIFIER_SUMMARY_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL
    )
    checkpoint_by_key[RECOVERABLE_KEY] = recovered_staging_record
    print(
        f"[PASS] Recovered predecessor output without retransferring: {RECOVERABLE_KEY}; "
        f"{recovered_parquet.metadata.num_rows:,} x {recovered_parquet.metadata.num_columns}; "
        f"source_sha256={recovered_source_sha256}; staged_sha256={recovered_staged_sha256}"
    )

# --- Transform: Transfer, conversion, and per-object validation ---
# Process one object at a time so peak scratch storage is one CSV plus one Parquet.
# Each successful object is checkpointed immediately in the durable manifests.
for object_record in to_stage.iter_rows(named=True):
    canonical_key = object_record["canonical_object_key"]
    source_url = object_record["urban_url"]
    expected_source_bytes = int(object_record["source_exact_bytes"])
    expected_etag = object_record.get("source_etag")
    expected_last_modified = object_record.get("source_last_modified")
    year_shard = object_record.get("year_shard")
    staged_path = STAGED_DATA_DIR / f"{canonical_key}.parquet"
    safe_name = canonical_key.replace("/", "__")
    raw_partial_path = SCRATCH_DIR / f"{safe_name}.partial-source.csv"
    polars_partial_path = SCRATCH_DIR / f"{safe_name}.partial-polars.parquet"
    materialized_partial_path = SCRATCH_DIR / f"{safe_name}.partial-materialized.parquet"

    print("\n" + "-" * 80)
    print(f"OBJECT: {canonical_key}")
    print(f"SOURCE: {source_url}")
    print(f"EXPECTED SOURCE BYTES: {expected_source_bytes:,}")

    # INTENT: skip a completed checkpoint only after recomputing its exact staged
    # SHA-256 and shape. REASONING: this is safe cross-revision resumability; path
    # existence alone is insufficient evidence. ASSUMES: checkpoint status PASS
    # means source transfer and conversion already completed in a prior attempt.
    if canonical_key in checkpoint_by_key:
        checkpoint = checkpoint_by_key[canonical_key]
        checkpoint_path = Path(checkpoint["staged_path"])
        assert checkpoint.get("validation_status") == "PASS", (
            f"STOP: non-PASS checkpoint exists for {canonical_key}"
        )
        assert checkpoint_path == staged_path and staged_path.exists(), (
            f"STOP: checkpoint output missing or moved for {canonical_key}"
        )
        staged_hasher = hashlib.sha256()
        with staged_path.open("rb") as staged_file:
            while True:
                chunk = staged_file.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                staged_hasher.update(chunk)
        assert staged_hasher.hexdigest() == checkpoint["staged_sha256"], (
            f"STOP: checkpoint staged hash mismatch for {canonical_key}"
        )
        checkpoint_meta = pq.ParquetFile(staged_path).metadata
        assert checkpoint_meta.num_rows == checkpoint["row_count"]
        assert checkpoint_meta.num_columns == checkpoint["column_count"]
        print(f"[PASS] Reused validated checkpoint: {checkpoint_meta.num_rows:,} rows")
        continue

    assert not staged_path.exists(), (
        f"STOP: unmanifested staged output already exists for {canonical_key}: {staged_path}"
    )
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    object_observed_at_utc = datetime.now(timezone.utc).isoformat()
    transfer_http_status = None
    transfer_etag = None
    transfer_last_modified = None
    transfer_content_range = None
    source_sha256 = None
    source_column_names = None
    source_schema_overrides = {}
    source_bytes_written = 0
    view_materialization_action = "not_evaluated"

    try:
        # --- Transfer ---
        # INTENT: stream exact source bytes into a project-local partial file while
        # hashing during transfer. REASONING: an existing abrupt-termination partial
        # is resumed only if the server honors Range with the audited total; otherwise
        # staging fails rather than silently restarting or concatenating. ASSUMES:
        # Accept-Encoding identity makes byte counts/hash refer to the source object.
        source_hasher = hashlib.sha256()
        existing_bytes = raw_partial_path.stat().st_size if raw_partial_path.exists() else 0
        assert existing_bytes <= expected_source_bytes, (
            f"STOP: partial source exceeds expected size for {canonical_key}"
        )
        if existing_bytes > 0:
            with raw_partial_path.open("rb") as existing_file:
                while True:
                    chunk = existing_file.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    source_hasher.update(chunk)
            print(f"Resuming verified partial prefix: {existing_bytes:,} bytes")

        if existing_bytes < expected_source_bytes:
            request_headers = {"Accept-Encoding": "identity"}
            file_mode = "wb"
            if existing_bytes > 0:
                request_headers["Range"] = f"bytes={existing_bytes}-"
                if expected_etag:
                    request_headers["If-Range"] = expected_etag
                elif expected_last_modified:
                    request_headers["If-Range"] = expected_last_modified
                file_mode = "ab"
            transfer_response = session.get(
                source_url,
                headers=request_headers,
                stream=True,
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
            )
            transfer_http_status = transfer_response.status_code
            transfer_etag = transfer_response.headers.get("ETag")
            transfer_last_modified = transfer_response.headers.get("Last-Modified")
            transfer_content_range = transfer_response.headers.get("Content-Range")
            if existing_bytes == 0:
                assert transfer_http_status == 200, (
                    f"STOP: fresh transfer returned HTTP {transfer_http_status} for {canonical_key}"
                )
                response_length = transfer_response.headers.get("Content-Length")
                assert response_length is not None and int(response_length) == expected_source_bytes, (
                    f"STOP: transfer Content-Length drift for {canonical_key}: "
                    f"{response_length} != {expected_source_bytes}"
                )
            else:
                assert transfer_http_status == 206, (
                    f"STOP: resume request not honored for {canonical_key}; "
                    f"HTTP {transfer_http_status}"
                )
                range_match = re.fullmatch(
                    r"bytes\s+(\d+)-(\d+)/(\d+)", transfer_content_range or ""
                )
                assert range_match, f"STOP: malformed resume Content-Range for {canonical_key}"
                assert int(range_match.group(1)) == existing_bytes
                assert int(range_match.group(3)) == expected_source_bytes
            if expected_etag and transfer_etag:
                assert transfer_etag == expected_etag, f"STOP: ETag drift for {canonical_key}"
            if expected_last_modified and transfer_last_modified:
                assert transfer_last_modified == expected_last_modified, (
                    f"STOP: Last-Modified drift for {canonical_key}"
                )

            source_bytes_written = existing_bytes
            with raw_partial_path.open(file_mode) as raw_file:
                for chunk in transfer_response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if not chunk:
                        continue
                    source_bytes_written += len(chunk)
                    assert source_bytes_written <= expected_source_bytes, (
                        f"STOP: transfer exceeded audited bytes for {canonical_key}"
                    )
                    source_hasher.update(chunk)
                    raw_file.write(chunk)
            transfer_response.close()
        else:
            source_bytes_written = existing_bytes
            transfer_http_status = object_record.get("source_head_http_status")
            transfer_etag = expected_etag
            transfer_last_modified = expected_last_modified
            transfer_content_range = "complete partial recovered without network body"

        assert raw_partial_path.exists(), f"STOP: source partial missing for {canonical_key}"
        assert raw_partial_path.stat().st_size == expected_source_bytes, (
            f"STOP: source byte mismatch for {canonical_key}: "
            f"{raw_partial_path.stat().st_size} != {expected_source_bytes}"
        )
        assert source_bytes_written == expected_source_bytes
        source_sha256 = source_hasher.hexdigest()
        print(f"[PASS] Transfer bytes/hash: {expected_source_bytes:,} / {source_sha256}")

        # --- Inspect source schema ---
        # INTENT: read the actual CSV header before constructing type overrides.
        # REASONING: only observed identifier columns receive overrides; absent fields
        # are never invented. ASSUMES: the first record is a UTF-8 CSV header.
        with raw_partial_path.open("r", encoding="utf-8-sig", newline="") as raw_text:
            csv_reader = csv.reader(raw_text)
            source_column_names = next(csv_reader)
        assert source_column_names and len(source_column_names) == len(set(source_column_names)), (
            f"STOP: empty or duplicate CSV header for {canonical_key}"
        )
        assert all(name == name.strip() and name for name in source_column_names), (
            f"STOP: blank/whitespace CSV column name for {canonical_key}"
        )
        if canonical_key.startswith("ccd/"):
            if "ncessch" in source_column_names:
                source_schema_overrides["ncessch"] = pl.String
            if "leaid" in source_column_names:
                source_schema_overrides["leaid"] = pl.String
        if canonical_key.startswith("ipeds/"):
            assert "unitid" in source_column_names, f"STOP: IPEDS source lacks unitid: {canonical_key}"
            source_schema_overrides["unitid"] = pl.Int64
        print(f"[PASS] Inspected source header: {len(source_column_names)} columns")
        print(f"Identifier overrides applied only when observed: {sorted(source_schema_overrides)}")

        # --- Convert ---
        # INTENT: parse the complete CSV lazily, protect observed identifiers, normalize
        # CCD key widths, and stream to a deterministic Parquet intermediate.
        # REASONING: strict parsing (`ignore_errors=False`) fails on unmodeled type drift;
        # stable row order and fixed compression settings make conversion reproducible.
        # ASSUMES: Portal CSV is UTF-8 and comma-delimited with one header row.
        source_lazy = pl.scan_csv(
            raw_partial_path,
            has_header=True,
            separator=",",
            quote_char='"',
            infer_schema_length=100_000,
            schema_overrides=source_schema_overrides or None,
            ignore_errors=False,
            try_parse_dates=False,
            low_memory=True,
            rechunk=False,
            encoding="utf8",
        )
        id_expressions = []
        for identifier_name, identifier_width in [("ncessch", 12), ("leaid", 7)]:
            if identifier_name in source_column_names:
                # INTENT: preserve null/sentinel identifiers and zero-pad every other
                # observed CCD key to its canonical width. REASONING: force-string alone
                # cannot repair an already-truncated leading zero. ASSUMES: values wider
                # than the canonical width are true anomalies caught after conversion.
                id_expressions.append(
                    pl.when(
                        pl.col(identifier_name).is_null()
                        | pl.col(identifier_name).is_in(["", "-1", "-2", "-3"])
                    )
                    .then(pl.col(identifier_name))
                    .otherwise(pl.col(identifier_name).str.zfill(identifier_width))
                    .alias(identifier_name)
                )
        if id_expressions:
            source_lazy = source_lazy.with_columns(id_expressions)
        source_lazy.sink_parquet(
            polars_partial_path,
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS,
            row_group_size=PARQUET_ROW_GROUP_SIZE,
            maintain_order=True,
            engine="streaming",
            mkdir=True,
        )
        assert polars_partial_path.exists(), f"STOP: Polars output missing for {canonical_key}"

        # --- Materialize Arrow view types ---
        # INTENT: inspect the native Arrow schema and rewrite any view-typed field to
        # its materialized string/binary equivalent before final placement.
        # REASONING: R Arrow cannot directly convert utf8_view arrays. Materializing at
        # write time makes the staged artifact cross-language compatible without an R
        # workaround script. ASSUMES: CSV outputs are flat schemas (no nested views).
        polars_arrow_schema = pq.read_schema(polars_partial_path)
        materialized_fields = []
        source_view_fields = []
        for field in polars_arrow_schema:
            field_type_text = str(field.type)
            if pa.types.is_string_view(field.type):
                source_view_fields.append(field.name)
                materialized_fields.append(pa.field(field.name, pa.string(), nullable=field.nullable))
            elif pa.types.is_binary_view(field.type):
                source_view_fields.append(field.name)
                materialized_fields.append(pa.field(field.name, pa.binary(), nullable=field.nullable))
            else:
                materialized_fields.append(field)
        materialized_schema = pa.schema(materialized_fields)

        if source_view_fields:
            view_materialization_action = "rewritten_view_types_to_materialized"
            parquet_reader = pq.ParquetFile(polars_partial_path)
            parquet_writer = pq.ParquetWriter(
                materialized_partial_path,
                materialized_schema,
                compression=PARQUET_COMPRESSION,
                compression_level=PARQUET_COMPRESSION_LEVEL,
                write_statistics=PARQUET_STATISTICS,
                use_dictionary=True,
            )
            try:
                for batch in parquet_reader.iter_batches(batch_size=PARQUET_ROW_GROUP_SIZE):
                    batch_table = pa.Table.from_batches([batch]).cast(materialized_schema)
                    parquet_writer.write_table(batch_table, row_group_size=PARQUET_ROW_GROUP_SIZE)
            finally:
                parquet_writer.close()
            polars_partial_path.unlink()
            materialized_partial_path.replace(staged_path)
        else:
            view_materialization_action = "no_view_types_observed_materialized_schema_retained"
            polars_partial_path.replace(staged_path)
        final_arrow_schema = pq.read_schema(staged_path)
        assert not any(
            pa.types.is_string_view(field.type) or pa.types.is_binary_view(field.type)
            for field in final_arrow_schema
        ), f"STOP: Arrow view type remains in {canonical_key}"
        print(f"[PASS] Arrow compatibility: {view_materialization_action}")

        # --- Validate staged file ---
        # Verify magic bytes/footer/readability, exact shape, source-column retention,
        # year consistency, and source/staged format-specific hashes.
        with staged_path.open("rb") as staged_file:
            leading_magic = staged_file.read(4)
            staged_file.seek(-4, 2)
            trailing_magic = staged_file.read(4)
        assert leading_magic == b"PAR1" and trailing_magic == b"PAR1", (
            f"STOP: Parquet magic/footer failure for {canonical_key}"
        )
        parquet_file = pq.ParquetFile(staged_path)
        row_count = parquet_file.metadata.num_rows
        column_count = parquet_file.metadata.num_columns
        staged_column_names = final_arrow_schema.names
        assert row_count > 0, f"STOP: zero staged rows for {canonical_key}"
        assert column_count == len(source_column_names), f"STOP: column count loss for {canonical_key}"
        assert staged_column_names == source_column_names, (
            f"STOP: column name/order drift for {canonical_key}: "
            f"source_only={sorted(set(source_column_names) - set(staged_column_names))}, "
            f"staged_only={sorted(set(staged_column_names) - set(source_column_names))}"
        )

        # INTENT: compute year and identifier validations in one projection-only
        # Parquet scan. REASONING: column pruning avoids repeatedly reading wide data.
        # ASSUMES: year_shard, when present, is the expected value of a source `year` field.
        validation_expressions = []
        if "year" in staged_column_names:
            validation_expressions.extend(
                [
                    pl.col("year").drop_nulls().unique().sort().alias("year_values"),
                    pl.col("year").null_count().alias("year_null_count"),
                ]
            )
        for identifier_name, identifier_width in [("ncessch", 12), ("leaid", 7)]:
            if identifier_name in staged_column_names:
                valid_identifier = (
                    pl.col(identifier_name).is_not_null()
                    & ~pl.col(identifier_name).is_in(["", "-1", "-2", "-3"])
                )
                validation_expressions.extend(
                    [
                        pl.col(identifier_name).null_count().alias(f"{identifier_name}__null_count"),
                        pl.col(identifier_name)
                        .filter(pl.col(identifier_name).is_in(["-1", "-2", "-3"]))
                        .len()
                        .alias(f"{identifier_name}__sentinel_count"),
                        pl.col(identifier_name)
                        .filter(valid_identifier & (pl.col(identifier_name).str.len_chars() != identifier_width))
                        .len()
                        .alias(f"{identifier_name}__invalid_width_count"),
                        pl.col(identifier_name)
                        .filter(valid_identifier & ~pl.col(identifier_name).str.contains(r"^\d+$"))
                        .len()
                        .alias(f"{identifier_name}__nonnumeric_count"),
                        pl.col(identifier_name)
                        .filter(valid_identifier)
                        .str.len_chars()
                        .min()
                        .alias(f"{identifier_name}__min_width"),
                        pl.col(identifier_name)
                        .filter(valid_identifier)
                        .str.len_chars()
                        .max()
                        .alias(f"{identifier_name}__max_width"),
                        pl.col(identifier_name).n_unique().alias(f"{identifier_name}__n_unique"),
                    ]
                )
        if "unitid" in staged_column_names:
            valid_unitid = pl.col("unitid").is_not_null() & ~pl.col("unitid").is_in([-1, -2, -3])
            validation_expressions.extend(
                [
                    pl.col("unitid").null_count().alias("unitid__null_count"),
                    pl.col("unitid").filter(pl.col("unitid").is_in([-1, -2, -3])).len().alias(
                        "unitid__sentinel_count"
                    ),
                    pl.col("unitid").filter(valid_unitid & (pl.col("unitid") <= 0)).len().alias(
                        "unitid__nonpositive_count"
                    ),
                    pl.col("unitid").filter(valid_unitid).min().alias("unitid__min_value"),
                    pl.col("unitid").filter(valid_unitid).max().alias("unitid__max_value"),
                    pl.col("unitid").n_unique().alias("unitid__n_unique"),
                ]
            )
        validation_result = (
            pl.scan_parquet(staged_path).select(validation_expressions).collect()
            if validation_expressions
            else pl.DataFrame({"validation_placeholder": [True]})
        )
        validation_values = validation_result.to_dicts()[0]

        raw_observed_year_values = validation_values.get("year_values", [])
        # INTENT: normalize Polars' aggregation shape to a Python list.
        # REASONING: depending on projection context, a sole unique value can be
        # returned as scalar `2024` rather than list `[2024]`; both represent the
        # same observed domain and must not create a false failure.
        observed_year_values = (
            raw_observed_year_values
            if isinstance(raw_observed_year_values, list)
            else ([] if raw_observed_year_values is None else [raw_observed_year_values])
        )
        year_validation_status = "NOT_APPLICABLE_NO_YEAR_COLUMN"
        if "year" in staged_column_names:
            year_validation_status = (
                "PASS"
                if year_shard is not None and observed_year_values == [year_shard]
                else "FAIL"
            )
            assert year_validation_status == "PASS", (
                f"STOP: year shard mismatch for {canonical_key}: "
                f"expected={year_shard}, observed={observed_year_values}"
            )

        object_identifier_records = []
        for identifier_name, identifier_width in [("ncessch", 12), ("leaid", 7)]:
            if identifier_name in staged_column_names:
                invalid_width_count = validation_values[f"{identifier_name}__invalid_width_count"]
                nonnumeric_count = validation_values[f"{identifier_name}__nonnumeric_count"]
                identifier_status = (
                    "PASS" if invalid_width_count == 0 and nonnumeric_count == 0 else "FAIL"
                )
                assert identifier_status == "PASS", (
                    f"STOP: {identifier_name} width/domain failure for {canonical_key}"
                )
                object_identifier_records.append(
                    {
                        "canonical_object_key": canonical_key,
                        "year_shard": year_shard,
                        "identifier_column": identifier_name,
                        "staged_arrow_type": str(final_arrow_schema.field(identifier_name).type),
                        "expected_rule": f"string digits width {identifier_width}; null/-1/-2/-3 excluded",
                        "null_count": validation_values[f"{identifier_name}__null_count"],
                        "sentinel_count": validation_values[f"{identifier_name}__sentinel_count"],
                        "invalid_width_count": invalid_width_count,
                        "nonnumeric_or_nonpositive_count": nonnumeric_count,
                        "min_width_or_value": str(validation_values[f"{identifier_name}__min_width"]),
                        "max_width_or_value": str(validation_values[f"{identifier_name}__max_width"]),
                        "n_unique_including_null": validation_values[f"{identifier_name}__n_unique"],
                        "observed_year_values": observed_year_values,
                        "year_validation_status": year_validation_status,
                        "validation_status": identifier_status,
                    }
                )
        if "unitid" in staged_column_names:
            unitid_field_type = final_arrow_schema.field("unitid").type
            unitid_nonpositive = validation_values["unitid__nonpositive_count"]
            unitid_status = (
                "PASS" if pa.types.is_int64(unitid_field_type) and unitid_nonpositive == 0 else "FAIL"
            )
            assert unitid_status == "PASS", f"STOP: unitid type/domain failure for {canonical_key}"
            object_identifier_records.append(
                {
                    "canonical_object_key": canonical_key,
                    "year_shard": year_shard,
                    "identifier_column": "unitid",
                    "staged_arrow_type": str(unitid_field_type),
                    "expected_rule": "Arrow int64; positive except null/-1/-2/-3 sentinels",
                    "null_count": validation_values["unitid__null_count"],
                    "sentinel_count": validation_values["unitid__sentinel_count"],
                    "invalid_width_count": None,
                    "nonnumeric_or_nonpositive_count": unitid_nonpositive,
                    "min_width_or_value": str(validation_values["unitid__min_value"]),
                    "max_width_or_value": str(validation_values["unitid__max_value"]),
                    "n_unique_including_null": validation_values["unitid__n_unique"],
                    "observed_year_values": observed_year_values,
                    "year_validation_status": year_validation_status,
                    "validation_status": unitid_status,
                }
            )
        assert object_identifier_records, f"STOP: no high-risk identifier observed for {canonical_key}"

        # INTENT: hash the completed Parquet bytes independently of the source hash.
        # REASONING: formats differ, so the two hashes identify separate artifacts and
        # are never compared for equality. ASSUMES: staged file is immutable after hash.
        staged_hasher = hashlib.sha256()
        with staged_path.open("rb") as staged_file:
            while True:
                chunk = staged_file.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                staged_hasher.update(chunk)
        staged_sha256 = staged_hasher.hexdigest()
        output_bytes = staged_path.stat().st_size

        # --- Prior-year schema comparison ---
        # INTENT: select the closest older mirrored object from the same terminal-year
        # family and obtain only its bounded Parquet footer metadata via Range GET.
        # REASONING: schema comparison does not require downloading prior-year columns.
        # ASSUMES: the server honors byte ranges and footer metadata is <=16 MiB.
        prior_candidates = reconciliation.filter(
            (pl.col("bulk_family_key") == object_record["bulk_family_key"])
            & pl.col("year_shard").is_not_null()
            & (pl.col("year_shard") < year_shard)
            & pl.col("present_hf")
            & pl.col("hf_url").is_not_null()
        ).sort("year_shard", descending=True)
        prior_key = None
        prior_year = None
        prior_schema = None
        prior_schema_status = "NO_PRIOR_YEAR_AVAILABLE"
        added_columns = []
        removed_columns = []
        type_changes = []
        prior_schema_bytes_fetched = 0
        if prior_candidates.height > 0:
            prior_record = prior_candidates.row(0, named=True)
            prior_key = prior_record["canonical_object_key"]
            prior_year = prior_record["year_shard"]
            prior_url = prior_record["hf_url"]
            prior_head = session.head(
                prior_url,
                allow_redirects=True,
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
            )
            prior_head.raise_for_status()
            prior_size = int(prior_head.headers["Content-Length"])
            footer_response = session.get(
                prior_url,
                headers={"Range": f"bytes={prior_size - 8}-{prior_size - 1}", "Accept-Encoding": "identity"},
                stream=True,
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
            )
            assert footer_response.status_code == 206, (
                f"STOP: prior-year footer Range unsupported for {prior_key}"
            )
            footer_bytes = footer_response.content
            footer_response.close()
            assert len(footer_bytes) == 8 and footer_bytes[4:] == b"PAR1", (
                f"STOP: invalid prior-year Parquet footer for {prior_key}"
            )
            metadata_length = struct.unpack("<I", footer_bytes[:4])[0]
            assert 0 < metadata_length <= PRIOR_FOOTER_MAX_BYTES, (
                f"STOP: prior-year footer metadata exceeds bound for {prior_key}"
            )
            metadata_start = prior_size - 8 - metadata_length
            metadata_response = session.get(
                prior_url,
                headers={
                    "Range": f"bytes={metadata_start}-{prior_size - 9}",
                    "Accept-Encoding": "identity",
                },
                stream=True,
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
            )
            assert metadata_response.status_code == 206, (
                f"STOP: prior-year metadata Range unsupported for {prior_key}"
            )
            metadata_bytes = metadata_response.content
            metadata_response.close()
            assert len(metadata_bytes) == metadata_length
            prior_schema_bytes_fetched = len(footer_bytes) + len(metadata_bytes)
            synthetic_footer_file = b"PAR1" + metadata_bytes + footer_bytes
            prior_metadata = pq.read_metadata(pa.BufferReader(synthetic_footer_file))
            prior_schema = prior_metadata.schema.to_arrow_schema()

            current_types = {
                field.name: str(field.type).replace("string_view", "string").replace("binary_view", "binary")
                for field in final_arrow_schema
            }
            prior_types = {
                field.name: str(field.type).replace("string_view", "string").replace("binary_view", "binary")
                for field in prior_schema
            }
            added_columns = [name for name in staged_column_names if name not in prior_types]
            removed_columns = [name for name in prior_schema.names if name not in current_types]
            type_changes = [
                f"{name}:{prior_types[name]}->{current_types[name]}"
                for name in staged_column_names
                if name in prior_types and prior_types[name] != current_types[name]
            ]
            # INTENT: classify the required CCD identifier-protection conversion as
            # intentional while rejecting every unrelated type change.
            # REASONING: a prior int64 cannot preserve display width/leading zeros;
            # this run's source-inspected ncessch/leaid strings are width-validated.
            intentional_identifier_type_changes = [
                change
                for change in type_changes
                if change.split(":", 1)[0] in {"ncessch", "leaid"}
                and change.split("->", 1)[0].endswith(("int64", "int32"))
                and change.split("->", 1)[1] in {"string", "large_string"}
            ]
            unexpected_type_changes = [
                change for change in type_changes if change not in intentional_identifier_type_changes
            ]
            assert not unexpected_type_changes, (
                f"STOP: prior-year type drift requires review for {canonical_key}: "
                f"{unexpected_type_changes}"
            )
            if intentional_identifier_type_changes:
                prior_schema_status = "INTENTIONAL_IDENTIFIER_PROTECTION_TYPE_CHANGE"
            elif added_columns and removed_columns:
                prior_schema_status = "SOURCE_NEW_AND_REMOVED_COLUMN_DRIFT"
            elif added_columns:
                prior_schema_status = "SOURCE_NEW_COLUMN_DRIFT"
            elif removed_columns:
                prior_schema_status = "SOURCE_REMOVED_COLUMN_DRIFT"
            else:
                prior_schema_status = "MATCH_PRIOR_YEAR_SCHEMA"
            # New/removed source fields are not conversion errors because the final
            # staged columns already matched this run's exact CSV header above.
        print(
            f"[PASS] Prior schema comparison: {prior_schema_status}; "
            f"prior={prior_key}; added={added_columns}; removed={removed_columns}"
        )

        # --- Save manifests/checkpoint ---
        # Create one field row per staged column and one object-level prior comparison.
        object_field_records = []
        for ordinal, field in enumerate(final_arrow_schema):
            object_field_records.append(
                {
                    "canonical_object_key": canonical_key,
                    "year_shard": year_shard,
                    "field_ordinal": ordinal,
                    "field_name": field.name,
                    "arrow_type": str(field.type),
                    "nullable": field.nullable,
                    "source_csv_column_present": field.name in source_column_names,
                    "identifier_override_applied": field.name in source_schema_overrides,
                    "arrow_view_type": pa.types.is_string_view(field.type) or pa.types.is_binary_view(field.type),
                    "view_materialization_action": view_materialization_action,
                    "validation_status": "PASS",
                }
            )
        object_schema_comparison_record = {
            "canonical_object_key": canonical_key,
            "year_shard": year_shard,
            "prior_canonical_object_key": prior_key,
            "prior_year_shard": prior_year,
            "prior_schema_status": prior_schema_status,
            "added_columns": added_columns,
            "removed_columns": removed_columns,
            "type_changes": type_changes,
            "prior_schema_bytes_fetched": prior_schema_bytes_fetched,
            "conversion_column_loss": False,
            "validation_status": "PASS",
        }
        schema_summary = json.dumps(
            [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in final_arrow_schema],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        staging_record = {
            "canonical_object_key": canonical_key,
            "bulk_family_key": object_record["bulk_family_key"],
            "year_shard": year_shard,
            "urban_path": object_record["urban_path"],
            "source_url": source_url,
            "urban_manifest_ids": object_record["urban_manifest_ids"],
            "endpoint_ids": object_record["endpoint_ids"],
            "observed_at_utc": object_observed_at_utc,
            "source_http_status": transfer_http_status,
            "source_etag": transfer_etag or expected_etag,
            "source_last_modified": transfer_last_modified or expected_last_modified,
            "source_content_range": transfer_content_range,
            "source_exact_bytes": expected_source_bytes,
            "source_sha256": source_sha256,
            "staged_path": str(staged_path),
            "staged_sha256": staged_sha256,
            "row_count": row_count,
            "column_count": column_count,
            "schema_summary_json": schema_summary,
            "field_schema_manifest_path": str(FIELD_SCHEMA_PATH),
            "identifier_summary_manifest_path": str(IDENTIFIER_SUMMARY_PATH),
            "prior_schema_status": prior_schema_status,
            "view_materialization_action": view_materialization_action,
            "parquet_compression": PARQUET_COMPRESSION,
            "parquet_compression_level": PARQUET_COMPRESSION_LEVEL,
            "parquet_row_group_size": PARQUET_ROW_GROUP_SIZE,
            "parquet_statistics": PARQUET_STATISTICS,
            "output_bytes": output_bytes,
            "year_validation_status": year_validation_status,
            "validation_status": "PASS",
        }

        staging_records = [r for r in staging_records if r["canonical_object_key"] != canonical_key]
        field_records = [r for r in field_records if r["canonical_object_key"] != canonical_key]
        schema_comparison_records = [
            r for r in schema_comparison_records if r["canonical_object_key"] != canonical_key
        ]
        identifier_records = [r for r in identifier_records if r["canonical_object_key"] != canonical_key]
        staging_records.append(staging_record)
        field_records.extend(object_field_records)
        schema_comparison_records.append(object_schema_comparison_record)
        identifier_records.extend(object_identifier_records)

        pl.from_dicts(staging_records, infer_schema_length=None).sort("canonical_object_key").write_parquet(
            STAGING_MANIFEST_PATH,
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS,
        )
        pl.from_dicts(field_records, infer_schema_length=None).sort(
            "canonical_object_key", "field_ordinal"
        ).write_parquet(
            FIELD_SCHEMA_PATH,
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS,
        )
        pl.from_dicts(schema_comparison_records, infer_schema_length=None).sort(
            "canonical_object_key"
        ).write_parquet(
            SCHEMA_COMPARISON_PATH,
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS,
        )
        pl.from_dicts(identifier_records, infer_schema_length=None).sort(
            "canonical_object_key", "identifier_column"
        ).write_parquet(
            IDENTIFIER_SUMMARY_PATH,
            compression=PARQUET_COMPRESSION,
            compression_level=PARQUET_COMPRESSION_LEVEL,
            statistics=PARQUET_STATISTICS,
        )
        checkpoint_by_key[canonical_key] = staging_record
        print(
            f"[PASS] Staged {row_count:,} rows x {column_count} columns; "
            f"output={output_bytes:,} bytes; sha256={staged_sha256}"
        )

    finally:
        # --- Cleanup ---
        # INTENT: remove all source CSV and incomplete Parquet scratch artifacts after
        # success or a caught failure. REASONING: durable raw CSVs are outside the
        # approved artifact contract; abrupt process termination is handled by the
        # verified Range-resume branch on a versioned retry.
        if raw_partial_path.exists():
            raw_partial_path.unlink()
        if polars_partial_path.exists():
            polars_partial_path.unlink()
        if materialized_partial_path.exists():
            materialized_partial_path.unlink()

# --- Validate: Completed staging set ---
# Reopen all four durable manifests and prove one PASS provenance record and one
# readable staged object exist for every dynamically selected key.
staging_manifest = pl.read_parquet(STAGING_MANIFEST_PATH).sort("canonical_object_key")
field_manifest = pl.read_parquet(FIELD_SCHEMA_PATH)
schema_comparison_manifest = pl.read_parquet(SCHEMA_COMPARISON_PATH)
identifier_manifest = pl.read_parquet(IDENTIFIER_SUMMARY_PATH)
assert set(staging_manifest["canonical_object_key"].to_list()) == derived_keys
assert staging_manifest.height == MAX_OBJECTS
assert staging_manifest.filter(pl.col("validation_status") != "PASS").height == 0
assert field_manifest.filter(pl.col("validation_status") != "PASS").height == 0
assert schema_comparison_manifest.filter(pl.col("validation_status") != "PASS").height == 0
assert identifier_manifest.filter(pl.col("validation_status") != "PASS").height == 0
assert field_manifest.filter(pl.col("arrow_view_type")).height == 0

# INTENT: detect any source CSV or partial file still present anywhere under the
# staging subtree. REASONING: terminal glob checks provide a second cleanup layer.
remaining_partial_files = sorted(
    str(path)
    for path in STAGING_ROOT.rglob("*")
    if path.is_file() and ("partial" in path.name.lower() or path.suffix.lower() == ".csv")
)
assert not remaining_partial_files, f"STOP: raw/partial staging artifacts remain: {remaining_partial_files}"

for record in staging_manifest.iter_rows(named=True):
    staged_path = Path(record["staged_path"])
    assert staged_path.exists()
    staged_meta = pq.ParquetFile(staged_path).metadata
    assert staged_meta.num_rows == record["row_count"]
    assert staged_meta.num_columns == record["column_count"]
    print(
        f"  [PASS] {record['canonical_object_key']}: "
        f"{record['row_count']:,} x {record['column_count']}, "
        f"source={record['source_exact_bytes']:,}, output={record['output_bytes']:,}"
    )

print("\n" + "=" * 80)
print("MA2 VALIDATION: PASSED")
print(f"Objects staged: {staging_manifest.height}")
print(f"Source bytes verified: {int(staging_manifest['source_exact_bytes'].sum()):,}")
print(f"Staging manifest: {STAGING_MANIFEST_PATH}")
print(f"Field/schema manifest: {FIELD_SCHEMA_PATH}")
print(f"Identifier/domain summary: {IDENTIFIER_SUMMARY_PATH}")
print("Raw/partial CSV artifacts remaining: 0")
print("=" * 80)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-21 18:59:12
# Command: python3 /daaf/scripts/mirror_maintenance/02_stage-education-portal-mirror_b.py
# Duration: 50s
# Exit code: 0
#
# --- STDOUT ---
# ================================================================================
# MIRROR MAINTENANCE 2/3: BOUNDED LOCAL STAGING
# ================================================================================
# Loaded reconciliation: 495 rows x 47 columns
# [PASS] Derived allowlisted staging set: 8 objects
# [PASS] Exact source bytes: 1,428,846,087 <= 1,500,000,000
# [PASS] Recovered predecessor output without retransferring: ccd/schools_ccd_enrollment_2024; 18,349,935 x 9; source_sha256=a64b1e38a44dcd162dd879d4283a9071e47eca5302fc035fcd74446aa7863aa8; staged_sha256=738030e22af1a0cb59847cfda0afb29dbb8b2df120483599503c9ab8433ea3eb
# 
# --------------------------------------------------------------------------------
# OBJECT: ccd/schools_ccd_enrollment_2024
# SOURCE: https://educationdata.urban.org/csv/ccd/schools_ccd_enrollment_2024.csv
# EXPECTED SOURCE BYTES: 930,870,805
# [PASS] Reused validated checkpoint: 18,349,935 rows
# 
# --------------------------------------------------------------------------------
# OBJECT: ccd/schools_ccd_lea_enrollment_2024
# SOURCE: https://educationdata.urban.org/csv/ccd/schools_ccd_lea_enrollment_2024.csv
# EXPECTED SOURCE BYTES: 158,903,014
# [PASS] Transfer bytes/hash: 158,903,014 / ad6fb43e537d96c5b87e06c3ca6ce747da7306b376dd7cc8a411f56bb58f88a3
# [PASS] Inspected source header: 7 columns
# Identifier overrides applied only when observed: ['leaid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: INTENTIONAL_IDENTIFIER_PROTECTION_TYPE_CHANGE; prior=ccd/schools_ccd_lea_enrollment_2023; added=[]; removed=[]
# [PASS] Staged 6,356,502 rows x 7 columns; output=5,222,694 bytes; sha256=0a20447f1f5e673be91a5a775948e6c9a3fc5b76065a4a5bc68993f634c2c601
# 
# --------------------------------------------------------------------------------
# OBJECT: ipeds/colleges_ipeds_fall-enrollment-age_2021
# SOURCE: https://educationdata.urban.org/csv/ipeds/colleges_ipeds_fall-enrollment-age_2021.csv
# EXPECTED SOURCE BYTES: 37,028,939
# [PASS] Transfer bytes/hash: 37,028,939 / fa528dd82f7fc7a18aca8042a6f678b18f872bf7a801a226b950b26da054e919
# [PASS] Inspected source header: 9 columns
# Identifier overrides applied only when observed: ['unitid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: MATCH_PRIOR_YEAR_SCHEMA; prior=ipeds/colleges_ipeds_fall-enrollment-age_2020; added=[]; removed=[]
# [PASS] Staged 1,204,011 rows x 9 columns; output=1,421,252 bytes; sha256=841db9ad5bb491d15cbbe06d27c3dc840380a310fe2f7a0e906d4625425728c8
# 
# --------------------------------------------------------------------------------
# OBJECT: ipeds/colleges_ipeds_fall-enrollment-age_2022
# SOURCE: https://educationdata.urban.org/csv/ipeds/colleges_ipeds_fall-enrollment-age_2022.csv
# EXPECTED SOURCE BYTES: 18,239,410
# [PASS] Transfer bytes/hash: 18,239,410 / 9faa777996240238ffb3fa655c7f2bb2ad35bee7182628358bf56e1b1e5b810f
# [PASS] Inspected source header: 9 columns
# Identifier overrides applied only when observed: ['unitid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: MATCH_PRIOR_YEAR_SCHEMA; prior=ipeds/colleges_ipeds_fall-enrollment-age_2020; added=[]; removed=[]
# [PASS] Staged 588,150 rows x 9 columns; output=819,617 bytes; sha256=038754158bf8f61acf272fb2a5221169991a5ba884adb06a0781bae917f56b08
# 
# --------------------------------------------------------------------------------
# OBJECT: ipeds/colleges_ipeds_fall-enrollment-age_2023
# SOURCE: https://educationdata.urban.org/csv/ipeds/colleges_ipeds_fall-enrollment-age_2023.csv
# EXPECTED SOURCE BYTES: 36,566,443
# [PASS] Transfer bytes/hash: 36,566,443 / 13c3fec032d7cc0eb3b9688ef32c55dcaf4955e90fa4327ca8aaf105d32421b6
# [PASS] Inspected source header: 9 columns
# Identifier overrides applied only when observed: ['unitid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: MATCH_PRIOR_YEAR_SCHEMA; prior=ipeds/colleges_ipeds_fall-enrollment-age_2020; added=[]; removed=[]
# [PASS] Staged 1,188,693 rows x 9 columns; output=1,425,175 bytes; sha256=41a4232f563876583bcb35005faf20424110d137c93959d69966d9842877d2be
# 
# --------------------------------------------------------------------------------
# OBJECT: ipeds/colleges_ipeds_fall-enrollment-age_2024
# SOURCE: https://educationdata.urban.org/csv/ipeds/colleges_ipeds_fall-enrollment-age_2024.csv
# EXPECTED SOURCE BYTES: 17,850,786
# [PASS] Transfer bytes/hash: 17,850,786 / 65a3b44a174299a717c0d1b73fed9075176ea619289bde21495b7ca9e8d23453
# [PASS] Inspected source header: 9 columns
# Identifier overrides applied only when observed: ['unitid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: MATCH_PRIOR_YEAR_SCHEMA; prior=ipeds/colleges_ipeds_fall-enrollment-age_2020; added=[]; removed=[]
# [PASS] Staged 575,208 rows x 9 columns; output=826,642 bytes; sha256=2a0eb8351e533fa34dced7c1baaf94f21261f9b57c824c01f93819d293ac1989
# 
# --------------------------------------------------------------------------------
# OBJECT: ipeds/colleges_ipeds_fall-enrollment-race_2023
# SOURCE: https://educationdata.urban.org/csv/ipeds/colleges_ipeds_fall-enrollment-race_2023.csv
# EXPECTED SOURCE BYTES: 115,349,116
# [PASS] Transfer bytes/hash: 115,349,116 / e66e9e289c8524f6eb65f2464cd4b29d0ff9d92536a4ea324efb9804d55155ce
# [PASS] Inspected source header: 10 columns
# Identifier overrides applied only when observed: ['unitid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: MATCH_PRIOR_YEAR_SCHEMA; prior=ipeds/colleges_ipeds_fall-enrollment-race_2022; added=[]; removed=[]
# [PASS] Staged 3,686,080 rows x 10 columns; output=2,614,507 bytes; sha256=46470260dd6978937812b028bee15713758512b951af9fd9b094b435dad5c4b1
# 
# --------------------------------------------------------------------------------
# OBJECT: ipeds/colleges_ipeds_fall-enrollment-race_2024
# SOURCE: https://educationdata.urban.org/csv/ipeds/colleges_ipeds_fall-enrollment-race_2024.csv
# EXPECTED SOURCE BYTES: 114,037,574
# [PASS] Transfer bytes/hash: 114,037,574 / e554129408c6a57fa19000ef4f08586988793f0e1aa8a9c19a0b22b9c72a5988
# [PASS] Inspected source header: 10 columns
# Identifier overrides applied only when observed: ['unitid']
# [PASS] Arrow compatibility: no_view_types_observed_materialized_schema_retained
# [PASS] Prior schema comparison: MATCH_PRIOR_YEAR_SCHEMA; prior=ipeds/colleges_ipeds_fall-enrollment-race_2022; added=[]; removed=[]
# [PASS] Staged 3,642,656 rows x 10 columns; output=2,625,362 bytes; sha256=d615bb798ddb0e702c0a8690d30916aef1616aba5c832888492753419b450fb5
#   [PASS] ccd/schools_ccd_enrollment_2024: 18,349,935 x 9, source=930,870,805, output=16,638,298
#   [PASS] ccd/schools_ccd_lea_enrollment_2024: 6,356,502 x 7, source=158,903,014, output=5,222,694
#   [PASS] ipeds/colleges_ipeds_fall-enrollment-age_2021: 1,204,011 x 9, source=37,028,939, output=1,421,252
#   [PASS] ipeds/colleges_ipeds_fall-enrollment-age_2022: 588,150 x 9, source=18,239,410, output=819,617
#   [PASS] ipeds/colleges_ipeds_fall-enrollment-age_2023: 1,188,693 x 9, source=36,566,443, output=1,425,175
#   [PASS] ipeds/colleges_ipeds_fall-enrollment-age_2024: 575,208 x 9, source=17,850,786, output=826,642
#   [PASS] ipeds/colleges_ipeds_fall-enrollment-race_2023: 3,686,080 x 10, source=115,349,116, output=2,614,507
#   [PASS] ipeds/colleges_ipeds_fall-enrollment-race_2024: 3,642,656 x 10, source=114,037,574, output=2,625,362
# 
# ================================================================================
# MA2 VALIDATION: PASSED
# Objects staged: 8
# Source bytes verified: 1,428,846,087
# Staging manifest: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/manifests/2026-07-21_staging-provenance-manifest.parquet
# Field/schema manifest: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/manifests/2026-07-21_field-schema-manifest.parquet
# Identifier/domain summary: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/manifests/2026-07-21_identifier-value-domain-summary.parquet
# Raw/partial CSV artifacts remaining: 0
# ================================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
