#!/usr/bin/env python3
"""
Mirror maintenance 3/3: independently validate staged Education Portal objects.

Task: validate-education-portal-mirror
Lifecycle: local terminal validation and reporting only
Depends on: successful MA1 catalog audit and MA2 staging manifests
Inputs: durable Parquet catalogs/manifests and eight staged Parquet files
Outputs: terminal validation summary Parquet and human-readable Markdown report
Checkpoint: MA3

This script performs no network operation and contains no publication capability.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

# --- Config ---
# This section binds terminal validation to durable local artifacts rather than any
# staging-process memory. Expected keys/counts/bytes repeat the approved safety gate.
BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-07-21_FrameworkDev_EducationPortalSkills"
STAGING_ROOT = PROJECT_DIR / "2026-07-21_education-portal-mirror-staging"
CATALOG_DIR = STAGING_ROOT / "catalog"
MANIFEST_DIR = STAGING_ROOT / "manifests"
DATE_PREFIX = "2026-07-21"

ENDPOINT_PATH = CATALOG_DIR / f"{DATE_PREFIX}_urban-api-endpoint-catalog.parquet"
URBAN_PATH = CATALOG_DIR / f"{DATE_PREFIX}_urban-download-manifest.parquet"
HF_PATH = CATALOG_DIR / f"{DATE_PREFIX}_huggingface-tree.parquet"
RECONCILIATION_PATH = CATALOG_DIR / f"{DATE_PREFIX}_mirror-object-reconciliation.parquet"
BRIDGE_PATH = CATALOG_DIR / f"{DATE_PREFIX}_endpoint-object-bridge.parquet"
AUDIT_SUMMARY_PATH = CATALOG_DIR / f"{DATE_PREFIX}_mirror-audit-summary.parquet"
STAGING_MANIFEST_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_staging-provenance-manifest.parquet"
FIELD_SCHEMA_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_field-schema-manifest.parquet"
SCHEMA_COMPARISON_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_prior-year-schema-comparison.parquet"
IDENTIFIER_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_identifier-value-domain-summary.parquet"
TERMINAL_SUMMARY_PATH = MANIFEST_DIR / f"{DATE_PREFIX}_terminal-validation-summary.parquet"
REPORT_PATH = PROJECT_DIR / f"{DATE_PREFIX}_Education_Portal_Mirror_Reconciliation_Staging_Report.md"
AUDIT_SCRIPT_PATH = BASE_DIR / "scripts" / "mirror_maintenance" / "01_audit-education-portal-mirror.py"
STAGE_SCRIPT_PATH = BASE_DIR / "scripts" / "mirror_maintenance" / "02_stage-education-portal-mirror_b.py"
VALIDATE_SCRIPT_PATH = BASE_DIR / "scripts" / "mirror_maintenance" / "03_validate-education-portal-mirror.py"

EXPECTED_KEYS = {
    "ccd/schools_ccd_enrollment_2024",
    "ccd/schools_ccd_lea_enrollment_2024",
    "ipeds/colleges_ipeds_fall-enrollment-age_2021",
    "ipeds/colleges_ipeds_fall-enrollment-age_2022",
    "ipeds/colleges_ipeds_fall-enrollment-age_2023",
    "ipeds/colleges_ipeds_fall-enrollment-age_2024",
    "ipeds/colleges_ipeds_fall-enrollment-race_2023",
    "ipeds/colleges_ipeds_fall-enrollment-race_2024",
}
EXPECTED_ENDPOINT_ROWS = 129
EXPECTED_URBAN_ROWS = 958
EXPECTED_UNIQUE_URBAN_OBJECTS = 495
EXPECTED_HF_TREE_ENTRIES = 503
EXPECTED_HF_SOURCE_OBJECTS = 487
EXPECTED_EXACT_MATCHES = 487
EXPECTED_SOURCE_BYTES = 1_428_846_087
HASH_CHUNK_BYTES = 8 * 1024 * 1024
VALIDATED_AT_UTC = datetime.now(timezone.utc).isoformat()

# --- Load ---
# Load every durable artifact explicitly and fail if any is absent. This terminal
# script does not import or execute staging code.
print("=" * 80)
print("MIRROR MAINTENANCE 3/3: INDEPENDENT TERMINAL VALIDATION")
print("=" * 80)
required_paths = [
    ENDPOINT_PATH,
    URBAN_PATH,
    HF_PATH,
    RECONCILIATION_PATH,
    BRIDGE_PATH,
    AUDIT_SUMMARY_PATH,
    STAGING_MANIFEST_PATH,
    FIELD_SCHEMA_PATH,
    SCHEMA_COMPARISON_PATH,
    IDENTIFIER_PATH,
]
for required_path in required_paths:
    assert required_path.exists(), f"STOP: required durable artifact missing: {required_path}"

endpoints = pl.read_parquet(ENDPOINT_PATH)
urban = pl.read_parquet(URBAN_PATH)
hf_tree = pl.read_parquet(HF_PATH)
reconciliation = pl.read_parquet(RECONCILIATION_PATH)
bridge = pl.read_parquet(BRIDGE_PATH)
audit_summary = pl.read_parquet(AUDIT_SUMMARY_PATH)
staging = pl.read_parquet(STAGING_MANIFEST_PATH).sort("canonical_object_key")
fields = pl.read_parquet(FIELD_SCHEMA_PATH)
schema_comparison = pl.read_parquet(SCHEMA_COMPARISON_PATH)
identifiers = pl.read_parquet(IDENTIFIER_PATH)
print(f"Loaded {len(required_paths)} durable Parquet artifacts")

# --- Validate: Catalog reconciliation ---
# Recompute catalog counts from snapshots and comparison statuses rather than trust
# the audit-summary values alone.
# INTENT: independently reproduce the full-catalog inventory and approved diff.
# REASONING: exact recomputation catches stale or inconsistent derived manifests.
# ASSUMES: canonical object keys are unique in the deduplicated reconciliation.
assert endpoints.height == EXPECTED_ENDPOINT_ROWS
assert urban.height == EXPECTED_URBAN_ROWS
assert hf_tree.height == EXPECTED_HF_TREE_ENTRIES
assert bridge.height == EXPECTED_URBAN_ROWS
assert bridge["bulk_row_key"].n_unique() == EXPECTED_URBAN_ROWS
assert reconciliation.height == EXPECTED_UNIQUE_URBAN_OBJECTS
assert reconciliation["canonical_object_key"].n_unique() == reconciliation.height
hf_source_count = hf_tree.filter(pl.col("object_kind").is_in(["data", "codebook"])).height
exact_match_count = reconciliation.filter(
    pl.col("comparison_status") == "exact_normalized_match"
).height
urban_only = reconciliation.filter(
    (pl.col("comparison_status") == "urban_only") & (pl.col("object_kind") == "data")
)
hf_only = reconciliation.filter(pl.col("comparison_status") == "huggingface_only")
codebook_gaps = reconciliation.filter(
    (pl.col("object_kind") == "codebook") & (pl.col("comparison_status") != "exact_normalized_match")
)
assert hf_source_count == EXPECTED_HF_SOURCE_OBJECTS
assert exact_match_count == EXPECTED_EXACT_MATCHES
assert set(urban_only["canonical_object_key"].to_list()) == EXPECTED_KEYS
assert hf_only.height == 0
assert codebook_gaps.height == 0
assert int(urban_only["source_exact_bytes"].sum()) == EXPECTED_SOURCE_BYTES
assert audit_summary.filter(pl.col("staging_gate_status") != "PASS").height == 0
print(
    "[PASS] Catalog reconciliation: "
    f"endpoints={endpoints.height}, Urban rows={urban.height}, unique={reconciliation.height}, "
    f"HF source={hf_source_count}, exact={exact_match_count}, missing={urban_only.height}"
)

# --- Validate: Manifest relations ---
# Verify all staging-related manifests cover exactly the same approved object set and
# all declared statuses pass. Field rows may be many per object; object-level tables
# must be exactly one row per key.
# INTENT: enforce relational completeness between provenance, schema, and identifier
# evidence. REASONING: a staged file without any one manifest is not auditable.
staging_keys = set(staging["canonical_object_key"].to_list())
assert staging_keys == EXPECTED_KEYS and staging.height == 8
assert staging["canonical_object_key"].n_unique() == 8
assert set(fields["canonical_object_key"].unique().to_list()) == EXPECTED_KEYS
assert set(schema_comparison["canonical_object_key"].to_list()) == EXPECTED_KEYS
assert schema_comparison["canonical_object_key"].n_unique() == 8
assert set(identifiers["canonical_object_key"].unique().to_list()) == EXPECTED_KEYS
assert staging.filter(pl.col("validation_status") != "PASS").height == 0
assert fields.filter(pl.col("validation_status") != "PASS").height == 0
assert schema_comparison.filter(pl.col("validation_status") != "PASS").height == 0
assert identifiers.filter(pl.col("validation_status") != "PASS").height == 0
assert fields.filter(pl.col("arrow_view_type")).height == 0
assert schema_comparison.filter(pl.col("conversion_column_loss")).height == 0
assert int(staging["source_exact_bytes"].sum()) == EXPECTED_SOURCE_BYTES
print("[PASS] Provenance/schema/identifier manifests are complete and relationally aligned")

# --- Validate: Every staged Parquet object ---
# Independently hash and read every file, compare its physical schema to field rows,
# and rerun year/identifier checks from local Parquet data.
terminal_records = []
for record in staging.iter_rows(named=True):
    canonical_key = record["canonical_object_key"]
    staged_path = Path(record["staged_path"])
    print(f"\nValidating {canonical_key}")
    assert staged_path.exists() and staged_path.is_file()

    # INTENT: recompute exact staged SHA-256 from local bytes.
    # REASONING: this does not trust the staging-process hasher or manifest value.
    staged_hasher = hashlib.sha256()
    with staged_path.open("rb") as staged_file:
        leading_magic = staged_file.read(4)
        staged_file.seek(0)
        while True:
            chunk = staged_file.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            staged_hasher.update(chunk)
        staged_file.seek(-4, 2)
        trailing_magic = staged_file.read(4)
    observed_staged_hash = staged_hasher.hexdigest()
    assert leading_magic == b"PAR1" and trailing_magic == b"PAR1"
    assert observed_staged_hash == record["staged_sha256"]
    assert staged_path.stat().st_size == record["output_bytes"]

    parquet = pq.ParquetFile(staged_path)
    arrow_schema = parquet.schema_arrow
    assert parquet.metadata.num_rows == record["row_count"]
    assert parquet.metadata.num_columns == record["column_count"]
    assert not any(
        pa.types.is_string_view(field.type) or pa.types.is_binary_view(field.type)
        for field in arrow_schema
    )

    # INTENT: reconstruct expected physical schema from field-manifest ordinals.
    # REASONING: exact name/order/type comparison catches stale manifest fields and
    # accidental output replacement. ASSUMES: Arrow type string representations are stable.
    expected_fields = fields.filter(pl.col("canonical_object_key") == canonical_key).sort(
        "field_ordinal"
    )
    assert expected_fields.height == parquet.metadata.num_columns
    assert expected_fields["field_name"].to_list() == arrow_schema.names
    assert expected_fields["arrow_type"].to_list() == [str(field.type) for field in arrow_schema]

    validation_expressions = []
    if "year" in arrow_schema.names:
        validation_expressions.append(
            pl.col("year").drop_nulls().unique().sort().alias("year_values")
        )
    for identifier_name, identifier_width in [("ncessch", 12), ("leaid", 7)]:
        if identifier_name in arrow_schema.names:
            valid_identifier = (
                pl.col(identifier_name).is_not_null()
                & ~pl.col(identifier_name).is_in(["", "-1", "-2", "-3"])
            )
            validation_expressions.extend(
                [
                    pl.col(identifier_name)
                    .filter(valid_identifier & (pl.col(identifier_name).str.len_chars() != identifier_width))
                    .len()
                    .alias(f"{identifier_name}__invalid_width"),
                    pl.col(identifier_name)
                    .filter(valid_identifier & ~pl.col(identifier_name).str.contains(r"^\d+$"))
                    .len()
                    .alias(f"{identifier_name}__invalid_domain"),
                ]
            )
    if "unitid" in arrow_schema.names:
        valid_unitid = pl.col("unitid").is_not_null() & ~pl.col("unitid").is_in([-1, -2, -3])
        validation_expressions.extend(
            [
                pl.col("unitid")
                .filter(valid_unitid & (pl.col("unitid") <= 0))
                .len()
                .alias("unitid__invalid_domain"),
                pl.col("unitid").filter(valid_unitid).min().alias("unitid__min"),
                pl.col("unitid").filter(valid_unitid).max().alias("unitid__max"),
            ]
        )
    values = pl.scan_parquet(staged_path).select(validation_expressions).collect().to_dicts()[0]
    raw_years = values.get("year_values")
    observed_years = raw_years if isinstance(raw_years, list) else ([] if raw_years is None else [raw_years])
    assert observed_years == [record["year_shard"]]
    for field_name in arrow_schema.names:
        if field_name in ["ncessch", "leaid"]:
            assert values[f"{field_name}__invalid_width"] == 0
            assert values[f"{field_name}__invalid_domain"] == 0
        if field_name == "unitid":
            assert pa.types.is_int64(arrow_schema.field("unitid").type)
            assert values["unitid__invalid_domain"] == 0

    terminal_records.append(
        {
            "validated_at_utc": VALIDATED_AT_UTC,
            "canonical_object_key": canonical_key,
            "source_exact_bytes": record["source_exact_bytes"],
            "source_sha256": record["source_sha256"],
            "row_count": parquet.metadata.num_rows,
            "column_count": parquet.metadata.num_columns,
            "output_bytes": staged_path.stat().st_size,
            "staged_sha256_manifest": record["staged_sha256"],
            "staged_sha256_recomputed": observed_staged_hash,
            "parquet_magic_status": "PASS",
            "parquet_readability_status": "PASS",
            "schema_manifest_status": "PASS",
            "year_values": observed_years,
            "year_validation_status": "PASS",
            "identifier_validation_status": "PASS",
            "arrow_view_type_count": 0,
            "prior_schema_status": record["prior_schema_status"],
            "validation_status": "PASS",
        }
    )
    print(
        f"  [PASS] {parquet.metadata.num_rows:,} x {parquet.metadata.num_columns}; "
        f"bytes={staged_path.stat().st_size:,}; sha256={observed_staged_hash}"
    )

# --- Validate: No forbidden scratch residue ---
# Scan the full staging subtree for durable CSV, partial, or obvious temporary files.
# An empty result is direct local filesystem evidence of cleanup.
# INTENT: prove raw source bytes were not retained after conversion.
residual_files = sorted(
    str(path)
    for path in STAGING_ROOT.rglob("*")
    if path.is_file()
    and (
        path.suffix.lower() == ".csv"
        or "partial" in path.name.lower()
        or path.name.lower().endswith((".tmp", ".part"))
    )
)
assert not residual_files, f"STOP: forbidden staging residue remains: {residual_files}"
print("[PASS] No raw CSV, partial, .part, or .tmp files remain")

# --- Save: Terminal summary ---
# Persist independent validation outcomes as one row per staged object.
terminal_summary = pl.from_dicts(terminal_records, infer_schema_length=None).sort(
    "canonical_object_key"
)
terminal_summary.write_parquet(
    TERMINAL_SUMMARY_PATH,
    compression="zstd",
    compression_level=3,
    statistics=True,
)
reopened_terminal = pl.read_parquet(TERMINAL_SUMMARY_PATH)
assert reopened_terminal.shape == terminal_summary.shape
assert reopened_terminal.filter(pl.col("validation_status") != "PASS").height == 0

# --- Save: Human-readable report ---
# Build the report from durable validated tables. The quoted evidence lines below are
# values this script independently recomputed and also prints into the wrapper log.
# No remote-write implementation, command, credential, or publication instruction is included.
per_file_lines = []
for row in terminal_summary.iter_rows(named=True):
    per_file_lines.append(
        "| `" + row["canonical_object_key"] + "` | "
        + f"{row['source_exact_bytes']:,} | `{row['source_sha256']}` | "
        + f"{row['row_count']:,} × {row['column_count']} | {row['output_bytes']:,} | "
        + f"`{row['staged_sha256_recomputed']}` | {row['prior_schema_status']} | PASS |"
    )

schema_status_lines = []
for row in schema_comparison.sort("canonical_object_key").iter_rows(named=True):
    schema_status_lines.append(
        "| `" + row["canonical_object_key"] + "` | "
        + (f"`{row['prior_canonical_object_key']}`" if row["prior_canonical_object_key"] else "None")
        + f" | {row['prior_schema_status']} | "
        + f"{json.dumps(row['added_columns'])} | {json.dumps(row['removed_columns'])} | "
        + f"{json.dumps(row['type_changes'])} |"
    )

report = f"""# Education Data Portal Mirror Reconciliation and Local Staging Report

**Access/staging date:** 2026-07-21
**Terminal validation timestamp:** {VALIDATED_AT_UTC}
**Scope:** Full-catalog audit and local staging only.
**Publication status:** None. No remote repository was modified.

## Executive Summary

The lifecycle compared the live Urban endpoint catalog, live Urban bulk CSV/XLS manifest, and the complete Hugging Face mirror tree. It reproduced **129 endpoint rows**, **958 Urban manifest rows**, **495 unique Urban objects**, **487 exact format-neutral source-object matches**, **8 Urban-only data objects**, **0 Hugging-Face-only source objects**, and **0 codebook gaps**. The eight approved source CSVs total exactly **1,428,846,087 bytes**.

All eight missing objects were downloaded with read-only HTTP, hashed during transfer, converted locally to deterministic Parquet (Zstandard level 3, 100,000-row groups, statistics enabled, stable source row/column order), and independently revalidated from the durable artifacts. All staged files passed Parquet magic/footer/readability, exact row/column/schema, year-shard, high-risk identifier, staged SHA-256, and Arrow view-type checks. No raw CSV or partial file remains.

## Observed Execution Evidence

Observed facts below are quoted from wrapper-executed lifecycle output. Full logs are appended to the named scripts.

```text
$ bash /daaf/scripts/run_with_capture.sh /daaf/scripts/mirror_maintenance/01_audit-education-portal-mirror.py
Urban endpoint catalog: 129 rows across 1 page(s)
Urban download manifest: 958 rows across 1 page(s)
Hugging Face recursive tree: 503 entries across 1 page(s)
Exact normalized matches: 487
Urban-only data objects: 8
HF-only data objects: 0
Codebook gaps: 0
[PASS] Exact missing-source total: 1,428,846,087 bytes (cap 1,500,000,000)
MA1 VALIDATION: PASSED
```

```text
$ bash /daaf/scripts/run_with_capture.sh /daaf/scripts/mirror_maintenance/02_stage-education-portal-mirror_b.py
MA2 VALIDATION: PASSED
Objects staged: 8
Source bytes verified: 1,428,846,087
Raw/partial CSV artifacts remaining: 0
```

```text
$ bash /daaf/scripts/run_with_capture.sh /daaf/scripts/mirror_maintenance/03_validate-education-portal-mirror.py
[PASS] Catalog reconciliation: endpoints=129, Urban rows=958, unique=495, HF source=487, exact=487, missing=8
[PASS] Provenance/schema/identifier manifests are complete and relationally aligned
[PASS] No raw CSV, partial, .part, or .tmp files remain
MA3 VALIDATION: PASSED
```

## Catalog Model and Reconciliation

- Endpoint-family identity uses normalized `endpoint_url`; snapshot-local `endpoint_id` is retained.
- Urban row identity uses manifest `id`; exact object identity uses `file_dir/file_name`.
- The format-neutral key removes only terminal `.csv`, `.parquet`, or codebook `.xls`.
- Data family identity removes only terminal `_YYYY` and stores that year as `year_shard`.
- A 958-row endpoint-to-object bridge preserves all repeated and many-to-many associations.
- Raw `years_available` and parser version are retained; parsed years remain declarations, not observed availability.
- Duplicate/conflicting manifest evidence is stored as list fields and conflict flags.
- `Campus Crime` (display), `campus-crime` (endpoint slug), and `csafety` (bulk directory) are explicitly distinguished.

## Per-file Staging and Terminal Validation

| Canonical key | Source bytes | Source SHA-256 | Rows × columns | Output bytes | Staged SHA-256 | Prior-schema classification | Status |
|---|---:|---|---:|---:|---|---|---|
{chr(10).join(per_file_lines)}

Source and staged hashes are intentionally **not compared for equality**: CSV and Parquet are different byte formats. Each hash identifies its own artifact.

## Prior-year Schema Comparison

Prior-year comparisons used bounded Parquet footer reads only. New/removed fields are classified separately from conversion loss. The CCD identifier changes are deliberate: prior mirror objects store identifiers as integers, whereas these staged files protect canonical widths with materialized strings.

| Canonical key | Closest mirrored prior | Classification | Added columns | Removed columns | Type changes |
|---|---|---|---|---|---|
{chr(10).join(schema_status_lines)}

## Identifier and Cross-language Compatibility Results

- CCD `ncessch` is a materialized string; all nonmissing, nonsentinel values are numeric and exactly 12 characters.
- CCD `leaid` is a materialized string; all nonmissing, nonsentinel values are numeric and exactly 7 characters.
- IPEDS `unitid` is Arrow `int64`, avoiding floating-point precision loss; all nonsentinel observed values are positive.
- Every file's `year` domain equals its terminal year shard.
- Native Arrow schemas contain zero `string_view`/`binary_view` fields. Because view types were eliminated or absent at write time, the previously documented R cast workaround was not required and no R script was created.

## Durable Artifacts

- Reconciliation manifest: `{RECONCILIATION_PATH}`
- Endpoint-object bridge: `{BRIDGE_PATH}`
- Urban raw manifest snapshot: `{URBAN_PATH}`
- API endpoint snapshot: `{ENDPOINT_PATH}`
- Hugging Face tree snapshot: `{HF_PATH}`
- Staging/provenance manifest: `{STAGING_MANIFEST_PATH}`
- Field/schema manifest: `{FIELD_SCHEMA_PATH}`
- Prior-year schema comparison: `{SCHEMA_COMPARISON_PATH}`
- Identifier/value-domain summary: `{IDENTIFIER_PATH}`
- Terminal validation summary: `{TERMINAL_SUMMARY_PATH}`
- Staged object root: `{STAGING_ROOT / 'staged'}`

## Publication and Cleanup Boundary

This lifecycle contains no authentication, token handling, remote repository client, remote branch operation, large-file publication action, or remote write request. The catalog audit used read-only GET/HEAD/Range requests; staging used read-only GET/HEAD/Range requests; terminal validation was entirely local. No publication occurred.

Terminal filesystem validation found **0** raw `.csv`, partial, `.part`, or `.tmp` files under the staging subtree.

## Limitations

1. The lifecycle stages the eight metadata-level gaps; it does not redownload or content-compare the 487 same-key mirror objects, so their byte/content freshness relative to current Urban CSVs remains unverified.
2. Source CSVs were deliberately deleted after successful conversion. Their SHA-256 values were calculated during exact-byte streaming and recorded, but terminal validation cannot independently rehash deleted source bytes.
3. Prior-year schema checks read only bounded Parquet footer metadata; they compare names/types, not prior-year row values or distributions.
4. The audit is a dated snapshot. Urban or Hugging Face catalog state can change after the recorded observation timestamps.
5. Validation establishes technical conversion integrity and key-domain protections; it does not independently adjudicate every substantive field's meaning against source codebooks.
6. No R process was run because all final schemas were already materialized and contained no Arrow view type. This is schema-level evidence, not a new R runtime smoke test.

## Recommended Next Step

Use these observed schemas, identifier domains, reconciliation counts, and dated artifacts to update the Education Data Portal consumer skill prose and maintained smoke-test contract in a separately reviewed framework change. Keep any future publication workflow separately scoped and explicitly user-approved; it should consume only a validated immutable staging manifest.

## Software and Data Acknowledgment

- Urban Institute Education Data Portal supplied the public endpoint catalog, bulk manifest, and source CSV objects.
- The Hugging Face dataset tree supplied the read-only mirror inventory and prior-year Parquet schema metadata.
- Vink, R. et al. *Polars: Blazingly fast DataFrames* [Computer software]. https://pola.rs/
- Apache Arrow/PyArrow provided Parquet schema/footer validation.

## AI Assistance Disclosure

This report and lifecycle were produced with the Data Analyst Augmentation Framework (DAAF) in Framework Development mode. AI assistance contributed to script authoring, catalog canonicalization, transfer/conversion controls, validation design, execution, and reporting. The human researcher approved the scope and remains the final authority. No remote publication action was authorized or performed.
"""
REPORT_PATH.write_text(report, encoding="utf-8")
assert REPORT_PATH.exists() and REPORT_PATH.stat().st_size > 0

print("\n" + "=" * 80)
print("MA3 VALIDATION: PASSED")
print(f"Terminal objects validated: {terminal_summary.height}")
print(f"Exact source bytes represented: {int(terminal_summary['source_exact_bytes'].sum()):,}")
print(f"Terminal validation summary: {TERMINAL_SUMMARY_PATH}")
print(f"Human-readable report: {REPORT_PATH}")
print("Remote publication operations performed: 0")
print("Forbidden raw/partial artifacts remaining: 0")
print("=" * 80)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-21 19:02:29
# Command: python3 /daaf/scripts/mirror_maintenance/03_validate-education-portal-mirror.py
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# ================================================================================
# MIRROR MAINTENANCE 3/3: INDEPENDENT TERMINAL VALIDATION
# ================================================================================
# Loaded 10 durable Parquet artifacts
# [PASS] Catalog reconciliation: endpoints=129, Urban rows=958, unique=495, HF source=487, exact=487, missing=8
# [PASS] Provenance/schema/identifier manifests are complete and relationally aligned
# 
# Validating ccd/schools_ccd_enrollment_2024
#   [PASS] 18,349,935 x 9; bytes=16,638,298; sha256=738030e22af1a0cb59847cfda0afb29dbb8b2df120483599503c9ab8433ea3eb
# 
# Validating ccd/schools_ccd_lea_enrollment_2024
#   [PASS] 6,356,502 x 7; bytes=5,222,694; sha256=0a20447f1f5e673be91a5a775948e6c9a3fc5b76065a4a5bc68993f634c2c601
# 
# Validating ipeds/colleges_ipeds_fall-enrollment-age_2021
#   [PASS] 1,204,011 x 9; bytes=1,421,252; sha256=841db9ad5bb491d15cbbe06d27c3dc840380a310fe2f7a0e906d4625425728c8
# 
# Validating ipeds/colleges_ipeds_fall-enrollment-age_2022
#   [PASS] 588,150 x 9; bytes=819,617; sha256=038754158bf8f61acf272fb2a5221169991a5ba884adb06a0781bae917f56b08
# 
# Validating ipeds/colleges_ipeds_fall-enrollment-age_2023
#   [PASS] 1,188,693 x 9; bytes=1,425,175; sha256=41a4232f563876583bcb35005faf20424110d137c93959d69966d9842877d2be
# 
# Validating ipeds/colleges_ipeds_fall-enrollment-age_2024
#   [PASS] 575,208 x 9; bytes=826,642; sha256=2a0eb8351e533fa34dced7c1baaf94f21261f9b57c824c01f93819d293ac1989
# 
# Validating ipeds/colleges_ipeds_fall-enrollment-race_2023
#   [PASS] 3,686,080 x 10; bytes=2,614,507; sha256=46470260dd6978937812b028bee15713758512b951af9fd9b094b435dad5c4b1
# 
# Validating ipeds/colleges_ipeds_fall-enrollment-race_2024
#   [PASS] 3,642,656 x 10; bytes=2,625,362; sha256=d615bb798ddb0e702c0a8690d30916aef1616aba5c832888492753419b450fb5
# [PASS] No raw CSV, partial, .part, or .tmp files remain
# 
# ================================================================================
# MA3 VALIDATION: PASSED
# Terminal objects validated: 8
# Exact source bytes represented: 1,428,846,087
# Terminal validation summary: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/manifests/2026-07-21_terminal-validation-summary.parquet
# Human-readable report: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_Education_Portal_Mirror_Reconciliation_Staging_Report.md
# Remote publication operations performed: 0
# Forbidden raw/partial artifacts remaining: 0
# ================================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
