#!/usr/bin/env python3
"""
Mirror maintenance 1/3: audit the complete Education Data Portal mirror catalog.

Task: audit-education-portal-mirror
Lifecycle: local audit and staging only
Depends on: live Urban API catalogs and Hugging Face read-only tree API
Inputs: Urban endpoint catalog, Urban bulk manifest, Hugging Face recursive tree
Outputs: dated Parquet catalog snapshots, reconciliation manifest, bridge, audit summary
Checkpoint: MA1

This script has no remote-write path. Network operations are bounded to GET, HEAD,
and one-byte Range GET requests against public read-only catalog/data endpoints.
"""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import polars as pl
import requests

# --- Config ---
# This section defines the immutable run boundary, expected safety envelope, and
# dated output paths. The eight-key allowlist is a user-approved guardrail rather
# than the source of the observed diff: the script derives the live diff first.
BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-07-21_FrameworkDev_EducationPortalSkills"
STAGING_ROOT = PROJECT_DIR / "2026-07-21_education-portal-mirror-staging"
CATALOG_DIR = STAGING_ROOT / "catalog"
DATE_PREFIX = "2026-07-21"

ENDPOINT_CATALOG_URL = "https://educationdata.urban.org/api/v1/api-endpoints/"
URBAN_MANIFEST_URL = "https://educationdata.urban.org/api/v1/api-downloads/"
HF_TREE_URL = (
    "https://huggingface.co/api/datasets/brhkim/education_data_portal_mirror/"
    "tree/main?recursive=true&limit=1000"
)
URBAN_CSV_ROOT = "https://educationdata.urban.org/csv"
HF_RESOLVE_ROOT = (
    "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main"
)

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
MAX_MISSING_OBJECTS = 8
MAX_EXACT_SOURCE_BYTES = 1_500_000_000
BASELINE_ENDPOINT_ROWS = 129
BASELINE_MANIFEST_ROWS = 958
BASELINE_UNIQUE_OBJECTS = 495
BASELINE_HF_TREE_ENTRIES = 503
BASELINE_HF_FILES = 489
BASELINE_HF_SOURCE_OBJECTS = 487
BASELINE_MATCHES = 487
BASELINE_MISSING = 8
BASELINE_EXACT_SOURCE_BYTES = 1_428_846_087
REQUEST_TIMEOUT_SECONDS = 120
PARSER_VERSION = "years-v1-html-unescape-inclusive-ranges"
SNAPSHOT_ID = "2026-07-21_live-education-portal-mirror-audit"
OBSERVED_AT_UTC = datetime.now(timezone.utc).isoformat()
ACCESS_DATE = OBSERVED_AT_UTC[:10]

ENDPOINT_SNAPSHOT_PATH = CATALOG_DIR / f"{DATE_PREFIX}_urban-api-endpoint-catalog.parquet"
URBAN_SNAPSHOT_PATH = CATALOG_DIR / f"{DATE_PREFIX}_urban-download-manifest.parquet"
HF_SNAPSHOT_PATH = CATALOG_DIR / f"{DATE_PREFIX}_huggingface-tree.parquet"
OBJECT_MANIFEST_PATH = CATALOG_DIR / f"{DATE_PREFIX}_mirror-object-reconciliation.parquet"
BRIDGE_PATH = CATALOG_DIR / f"{DATE_PREFIX}_endpoint-object-bridge.parquet"
AUDIT_SUMMARY_PATH = CATALOG_DIR / f"{DATE_PREFIX}_mirror-audit-summary.parquet"

# --- Load ---
# Fetch all three live catalog surfaces independently. Urban catalogs are followed
# through their `next` links with a ten-page fail-closed bound; the Hugging Face
# recursive tree is likewise cursor-followed if a Link header advertises a next page.
print("=" * 80)
print("MIRROR MAINTENANCE 1/3: FULL-CATALOG AUDIT")
print("=" * 80)
print(f"Observed at UTC: {OBSERVED_AT_UTC}")

CATALOG_DIR.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers.update({"User-Agent": "DAAF-local-mirror-audit/1.0"})

# INTENT: Retrieve every endpoint-catalog row while retaining page-level response
# evidence. REASONING: following the API's own `next` URL avoids assuming the live
# one-page baseline will remain true. ASSUMES: the response envelope has `results`.
endpoint_rows = []
endpoint_page_evidence = []
next_url = ENDPOINT_CATALOG_URL
page_number = 0
while next_url is not None:
    page_number += 1
    assert page_number <= 10, "STOP: endpoint catalog exceeded 10-page safety bound"
    response = session.get(next_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict) and isinstance(payload.get("results"), list), (
        "STOP: unexpected endpoint catalog response schema"
    )
    endpoint_rows.extend(payload["results"])
    endpoint_page_evidence.append(
        {
            "page_number": page_number,
            "request_url": response.url,
            "http_status": response.status_code,
            "response_etag": response.headers.get("ETag"),
            "response_last_modified": response.headers.get("Last-Modified"),
            "declared_count": payload.get("count"),
            "page_rows": len(payload["results"]),
        }
    )
    next_url = payload.get("next")
print(f"Urban endpoint catalog: {len(endpoint_rows):,} rows across {page_number} page(s)")

# INTENT: Retrieve every Urban bulk-manifest row without deduplicating it.
# REASONING: row-level `id` and endpoint links are audit evidence; deduplication is
# deferred to the object model. ASSUMES: each result is a dictionary.
urban_rows = []
urban_page_evidence = []
next_url = URBAN_MANIFEST_URL
page_number = 0
while next_url is not None:
    page_number += 1
    assert page_number <= 10, "STOP: Urban manifest exceeded 10-page safety bound"
    response = session.get(next_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, dict) and isinstance(payload.get("results"), list), (
        "STOP: unexpected Urban manifest response schema"
    )
    urban_rows.extend(payload["results"])
    urban_page_evidence.append(
        {
            "page_number": page_number,
            "request_url": response.url,
            "http_status": response.status_code,
            "response_etag": response.headers.get("ETag"),
            "response_last_modified": response.headers.get("Last-Modified"),
            "declared_count": payload.get("count"),
            "page_rows": len(payload["results"]),
        }
    )
    next_url = payload.get("next")
print(f"Urban download manifest: {len(urban_rows):,} rows across {page_number} page(s)")

# INTENT: Retrieve the complete recursive Hugging Face tree, including directories
# and administrative files. REASONING: preserving the raw tree prevents a filtered
# source-object count from masquerading as the repository-entry count. ASSUMES: each
# response is a flat JSON list and RFC Link headers use angle-bracket URLs.
hf_rows = []
hf_page_evidence = []
next_url = HF_TREE_URL
page_number = 0
while next_url is not None:
    page_number += 1
    assert page_number <= 10, "STOP: Hugging Face tree exceeded 10-page safety bound"
    response = session.get(next_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    assert isinstance(payload, list), "STOP: unexpected Hugging Face tree response schema"
    hf_rows.extend(payload)
    hf_page_evidence.append(
        {
            "page_number": page_number,
            "request_url": response.url,
            "http_status": response.status_code,
            "response_etag": response.headers.get("ETag"),
            "response_last_modified": response.headers.get("Last-Modified"),
            "page_rows": len(payload),
        }
    )
    link_header = response.headers.get("Link", "")
    next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    next_url = next_match.group(1) if next_match else None
print(f"Hugging Face recursive tree: {len(hf_rows):,} entries across {page_number} page(s)")

# --- Transform: Raw snapshots ---
# Normalize only serialization concerns needed for durable Parquet snapshots. Raw
# source fields remain present; request provenance is added as separate columns.
# INTENT: materialize the endpoint response as one Parquet row per live endpoint.
# REASONING: stringifying only nested values prevents mixed object types from making
# Arrow schema inference unstable. ASSUMES: scalar API fields retain their values.
endpoint_snapshot_records = []
for row in endpoint_rows:
    record = {}
    for key, value in row.items():
        record[key] = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
    endpoint_url_raw = str(row.get("endpoint_url") or "").strip()
    endpoint_path = urlparse(endpoint_url_raw).path if "://" in endpoint_url_raw else endpoint_url_raw
    endpoint_family_key = re.sub(r"/+", "/", endpoint_path).strip().lower().rstrip("/")
    endpoint_parts = [part for part in endpoint_family_key.split("/") if part]
    endpoint_source_slug = None
    if "v1" in endpoint_parts:
        v1_index = endpoint_parts.index("v1")
        if len(endpoint_parts) > v1_index + 2:
            endpoint_source_slug = endpoint_parts[v1_index + 2]
    if endpoint_source_slug is None and len(endpoint_parts) >= 2:
        endpoint_source_slug = endpoint_parts[-2]

    # INTENT: deterministically parse declared year expressions while preserving the
    # original `years_available`. REASONING: inclusive four-digit ranges are expanded;
    # no parsed year is treated as observed object availability. ASSUMES: malformed
    # tokens are retained only in the raw field and do not fabricate years.
    years_raw = row.get("years_available")
    years_text = html.unescape(str(years_raw or ""))
    years_text = years_text.replace("–", "-").replace("—", "-")
    years_text = re.sub(r"\band\b", ",", years_text, flags=re.IGNORECASE)
    parsed_years = []
    for token in [part.strip() for part in years_text.split(",") if part.strip()]:
        range_match = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", token)
        single_match = re.fullmatch(r"\d{4}", token)
        if range_match:
            start_year = int(range_match.group(1))
            end_year = int(range_match.group(2))
            if start_year <= end_year and end_year - start_year <= 200:
                parsed_years.extend(range(start_year, end_year + 1))
        elif single_match:
            parsed_years.append(int(token))

    record.update(
        {
            "snapshot_id": SNAPSHOT_ID,
            "observed_at_utc": OBSERVED_AT_UTC,
            "access_date": ACCESS_DATE,
            "catalog_url": ENDPOINT_CATALOG_URL,
            "endpoint_family_key": endpoint_family_key,
            "endpoint_source_slug": endpoint_source_slug,
            "years_normalized": sorted(set(parsed_years)),
            "years_parser_version": PARSER_VERSION,
            "campus_crime_naming_note": (
                "display=Campus Crime; endpoint_slug=campus-crime; bulk_dir=csafety"
                if str(row.get("class_name") or "").strip().lower() == "campus crime"
                or endpoint_source_slug == "campus-crime"
                else None
            ),
        }
    )
    endpoint_snapshot_records.append(record)
endpoint_snapshot = pl.from_dicts(endpoint_snapshot_records, infer_schema_length=None)

# INTENT: preserve every raw bulk-manifest row and derive exact object identity.
# REASONING: `file_dir/file_name` is the deduplication key; manifest `id` remains the
# row key. ASSUMES: file names end in .csv or .xls for live data/codebook rows.
urban_snapshot_records = []
for row in urban_rows:
    file_dir = str(row.get("file_dir") or "").strip("/")
    file_name = str(row.get("file_name") or "").strip()
    bulk_object_path = f"{file_dir}/{file_name}"
    lower_name = file_name.lower()
    if lower_name.endswith(".csv"):
        object_kind = "data"
        object_stem = file_name[:-4]
        source_extension = ".csv"
    elif lower_name.endswith(".xls"):
        object_kind = "codebook"
        object_stem = file_name[:-4]
        source_extension = ".xls"
    else:
        object_kind = "other"
        object_stem = file_name
        source_extension = Path(file_name).suffix.lower()
    canonical_object_key = f"{file_dir}/{object_stem}"
    year_match = re.search(r"_(\d{4})$", object_stem) if object_kind == "data" else None
    year_shard = int(year_match.group(1)) if year_match else None
    bulk_family_stem = object_stem[: year_match.start()] if year_match else object_stem
    bulk_family_key = f"{file_dir}/{bulk_family_stem}"

    record = dict(row)
    record.update(
        {
            "snapshot_id": SNAPSHOT_ID,
            "observed_at_utc": OBSERVED_AT_UTC,
            "access_date": ACCESS_DATE,
            "catalog_url": URBAN_MANIFEST_URL,
            "bulk_row_key": row.get("id"),
            "bulk_object_path": bulk_object_path,
            "canonical_object_key": canonical_object_key,
            "object_kind": object_kind,
            "source_extension": source_extension,
            "bulk_family_key": bulk_family_key,
            "year_shard": year_shard,
            "urban_url": f"{URBAN_CSV_ROOT}/{bulk_object_path}",
            "source_display_name": "Campus Crime" if file_dir == "csafety" else None,
            "endpoint_source_slug_expected": "campus-crime" if file_dir == "csafety" else file_dir,
            "campus_crime_naming_note": (
                "display=Campus Crime; endpoint_slug=campus-crime; bulk_dir=csafety"
                if file_dir == "csafety"
                else None
            ),
        }
    )
    urban_snapshot_records.append(record)
urban_snapshot = pl.from_dicts(urban_snapshot_records, infer_schema_length=None)

# INTENT: flatten Hugging Face LFS metadata while preserving every tree entry.
# REASONING: nested structs are useful raw evidence but explicit columns make catalog
# reconciliation and byte-size checks deterministic. ASSUMES: `path` is repository-relative.
hf_snapshot_records = []
for row in hf_rows:
    lfs = row.get("lfs") if isinstance(row.get("lfs"), dict) else {}
    hf_path = str(row.get("path") or "")
    if hf_path.lower().endswith(".parquet"):
        object_kind = "data"
        canonical_object_key = hf_path[:-8]
        source_extension = ".parquet"
    elif hf_path.lower().endswith(".xls"):
        object_kind = "codebook"
        canonical_object_key = hf_path[:-4]
        source_extension = ".xls"
    else:
        object_kind = "administrative" if row.get("type") == "file" else "directory"
        canonical_object_key = None
        source_extension = Path(hf_path).suffix.lower() if row.get("type") == "file" else None
    hf_snapshot_records.append(
        {
            "snapshot_id": SNAPSHOT_ID,
            "observed_at_utc": OBSERVED_AT_UTC,
            "access_date": ACCESS_DATE,
            "catalog_url": HF_TREE_URL,
            "type": row.get("type"),
            "oid": row.get("oid"),
            "size": row.get("size"),
            "path": hf_path,
            "lfs_oid": lfs.get("oid"),
            "lfs_size": lfs.get("size"),
            "lfs_pointer_size": lfs.get("pointerSize"),
            "xet_hash": row.get("xetHash"),
            "object_kind": object_kind,
            "canonical_object_key": canonical_object_key,
            "source_extension": source_extension,
            "hf_url": f"{HF_RESOLVE_ROOT}/{hf_path}" if row.get("type") == "file" else None,
        }
    )
hf_snapshot = pl.from_dicts(hf_snapshot_records, infer_schema_length=None)

# --- Validate: Snapshot identity and raw counts ---
# Validate key uniqueness before any reconciliation. Count changes from the baseline
# are classified as drift, while semantic-key violations fail because they make the
# comparison ambiguous.
assert endpoint_snapshot.height == len(endpoint_rows), "STOP: endpoint snapshot row loss"
assert urban_snapshot.height == len(urban_rows), "STOP: Urban snapshot row loss"
assert hf_snapshot.height == len(hf_rows), "STOP: Hugging Face snapshot row loss"
assert endpoint_snapshot["endpoint_family_key"].n_unique() == endpoint_snapshot.height, (
    "STOP: normalized endpoint-family key is not unique"
)
assert urban_snapshot["bulk_row_key"].n_unique() == urban_snapshot.height, (
    "STOP: Urban bulk-row id is not unique"
)
print("[PASS] Snapshot row preservation and endpoint/bulk-row key uniqueness")

# --- Transform: Endpoint-object bridge ---
# INTENT: preserve every manifest-row association with its endpoint family.
# REASONING: a 958-row bridge retains duplicated presentation links instead of
# collapsing them to a misleading one-endpoint/one-file model. ASSUMES: every
# manifest endpoint_id resolves to the current endpoint snapshot.
endpoint_lookup = endpoint_snapshot.select(
    pl.col("endpoint_id"),
    pl.col("endpoint_family_key"),
    pl.col("endpoint_source_slug"),
    pl.col("class_name").alias("source_display_name_endpoint"),
    pl.col("section"),
    pl.col("topic"),
    pl.col("sub_topic"),
    pl.col("years_available").alias("years_available_raw"),
    pl.col("years_normalized"),
)
bridge = urban_snapshot.select(
    pl.col("snapshot_id"),
    pl.col("observed_at_utc"),
    pl.col("bulk_row_key"),
    pl.col("endpoint_id"),
    pl.col("bulk_object_path"),
    pl.col("canonical_object_key"),
    pl.col("object_kind"),
    pl.col("bulk_family_key"),
    pl.col("year_shard"),
).join(endpoint_lookup, on="endpoint_id", how="left", validate="m:1")
assert bridge.height == urban_snapshot.height, "STOP: bridge join changed manifest row count"
assert bridge["endpoint_family_key"].null_count() == 0, (
    "STOP: one or more manifest endpoint_id values do not resolve"
)
print(f"[PASS] Endpoint-object bridge preserves all {bridge.height:,} manifest associations")

# --- Transform: Deduplicated object reconciliation ---
# INTENT: aggregate Urban rows to one exact bulk object before cross-mirror comparison.
# REASONING: repeated labels and endpoint links are evidence retained as list fields;
# downloading before this aggregation would fetch duplicate paths. ASSUMES: rows with
# the same exact path represent one byte object even when labels/sizes conflict.
urban_objects = (
    urban_snapshot.group_by("canonical_object_key")
    .agg(
        pl.col("object_kind").first().alias("object_kind"),
        pl.col("file_dir").first().alias("bulk_dir"),
        pl.col("bulk_object_path").first().alias("urban_path"),
        pl.col("urban_url").first().alias("urban_url"),
        pl.col("bulk_family_key").first().alias("bulk_family_key"),
        pl.col("year_shard").first().alias("year_shard"),
        pl.col("bulk_row_key").sort().alias("urban_manifest_ids"),
        pl.col("endpoint_id").unique().sort().alias("endpoint_ids"),
        pl.col("file_label").unique().sort().alias("file_labels_raw"),
        pl.col("file_size").unique().sort().alias("file_sizes_raw"),
        pl.col("hide").unique().sort().alias("hide_values"),
        pl.len().alias("manifest_row_count"),
    )
    .with_columns(
        (pl.col("manifest_row_count") > 1).alias("has_duplicate_manifest_rows"),
        (
            (pl.col("file_labels_raw").list.len() > 1)
            | (pl.col("file_sizes_raw").list.len() > 1)
            | (pl.col("hide_values").list.len() > 1)
        ).alias("has_manifest_metadata_conflict"),
        pl.lit(True).alias("present_urban"),
    )
)

# INTENT: reduce the HF tree to one row per source object only (.parquet/.xls).
# REASONING: README and .gitattributes are administrative, not Urban source objects.
# ASSUMES: source-object canonical keys are unique in the recursive tree.
hf_source_objects = hf_snapshot.filter(pl.col("object_kind").is_in(["data", "codebook"]))
assert hf_source_objects["canonical_object_key"].n_unique() == hf_source_objects.height, (
    "STOP: duplicate canonical source keys in Hugging Face tree"
)
hf_objects = hf_source_objects.select(
    pl.col("canonical_object_key"),
    pl.col("path").alias("hf_path"),
    pl.col("hf_url"),
    pl.col("size").alias("hf_size_bytes"),
    pl.col("oid").alias("hf_oid"),
    pl.col("lfs_oid").alias("hf_lfs_oid"),
    pl.col("lfs_size").alias("hf_lfs_size_bytes"),
    pl.col("xet_hash").alias("hf_xet_hash"),
    pl.col("object_kind").alias("hf_object_kind"),
    pl.lit(True).alias("present_hf"),
)

# INTENT: full-join the format-neutral keys so both Urban-only and HF-only objects
# remain visible. REASONING: coalescing the key after a full join gives one auditable
# row per union object. ASSUMES: Urban and HF maps are each unique on the join key.
reconciliation = urban_objects.join(
    hf_objects,
    on="canonical_object_key",
    how="full",
    coalesce=True,
    validate="1:1",
).with_columns(
    pl.col("present_urban").fill_null(False),
    pl.col("present_hf").fill_null(False),
).with_columns(
    pl.when(pl.col("present_urban") & pl.col("present_hf"))
    .then(pl.lit("exact_normalized_match"))
    .when(pl.col("present_urban") & ~pl.col("present_hf"))
    .then(pl.lit("urban_only"))
    .when(~pl.col("present_urban") & pl.col("present_hf"))
    .then(pl.lit("huggingface_only"))
    .otherwise(pl.lit("invalid"))
    .alias("comparison_status"),
    pl.when((pl.col("object_kind") == "data") & (pl.col("hf_object_kind") == "data"))
    .then(pl.lit("csv_to_parquet"))
    .when((pl.col("object_kind") == "codebook") & (pl.col("hf_object_kind") == "codebook"))
    .then(pl.lit("xls_exact_extension"))
    .otherwise(pl.lit(None, dtype=pl.String))
    .alias("extension_relation"),
    pl.lit(SNAPSHOT_ID).alias("snapshot_id"),
    pl.lit(OBSERVED_AT_UTC).alias("observed_at_utc"),
    pl.lit(ACCESS_DATE).alias("access_date"),
)

# INTENT: enrich reconciled objects with all endpoint semantics through list-valued
# aggregations. REASONING: endpoint declarations remain metadata, not observed years.
# ASSUMES: bridge canonical keys map many-to-one into reconciliation.
endpoint_semantics = bridge.group_by("canonical_object_key").agg(
    pl.col("endpoint_family_key").unique().sort().alias("endpoint_family_keys"),
    pl.col("endpoint_source_slug").unique().sort().alias("endpoint_source_slugs"),
    pl.col("source_display_name_endpoint").unique().sort().alias("source_display_names"),
    pl.col("section").unique().sort().alias("sections"),
    pl.col("topic").unique().sort().alias("topics"),
    pl.col("sub_topic").drop_nulls().unique().sort().alias("sub_topics"),
    pl.col("years_available_raw").unique().sort().alias("years_available_raw"),
    pl.col("years_normalized").explode().drop_nulls().unique().sort().alias("years_normalized"),
)
reconciliation = reconciliation.join(
    endpoint_semantics,
    on="canonical_object_key",
    how="left",
    validate="1:1",
)

# --- Validate: Live diff and safety envelope ---
# Derive the live missing set first, then compare it to the bounded allowlist. Any
# new/different object fails closed even if total count and bytes are small.
data_reconciliation = reconciliation.filter(
    (pl.col("object_kind") == "data") | (pl.col("hf_object_kind") == "data")
)
codebook_reconciliation = reconciliation.filter(
    (pl.col("object_kind") == "codebook") | (pl.col("hf_object_kind") == "codebook")
)
missing = data_reconciliation.filter(pl.col("comparison_status") == "urban_only").sort(
    "canonical_object_key"
)
hf_only = data_reconciliation.filter(pl.col("comparison_status") == "huggingface_only")
codebook_gaps = codebook_reconciliation.filter(pl.col("comparison_status") != "exact_normalized_match")
missing_keys = set(missing["canonical_object_key"].to_list())

print("\nDerived live reconciliation:")
print(f"  Urban unique objects: {urban_objects.height:,}")
print(f"  HF source objects: {hf_source_objects.height:,}")
print(
    "  Exact normalized matches: "
    f"{reconciliation.filter(pl.col('comparison_status') == 'exact_normalized_match').height:,}"
)
print(f"  Urban-only data objects: {missing.height:,}")
print(f"  HF-only data objects: {hf_only.height:,}")
print(f"  Codebook gaps: {codebook_gaps.height:,}")
for key in sorted(missing_keys):
    print(f"    MISSING {key}")

assert missing_keys == EXPECTED_MISSING_KEYS, (
    "STOP: live missing set differs from the approved eight-object allowlist; "
    f"unexpected={sorted(missing_keys - EXPECTED_MISSING_KEYS)}, "
    f"no_longer_missing={sorted(EXPECTED_MISSING_KEYS - missing_keys)}"
)
assert missing.height <= MAX_MISSING_OBJECTS, "STOP: missing-object count exceeds cap"
assert hf_only.height == 0, "STOP: unexpected Hugging-Face-only data object(s)"
assert codebook_gaps.height == 0, "STOP: codebook reconciliation gap(s) detected"
print("[PASS] Live missing set exactly equals approved eight-object allowlist")

# --- Load: Exact source byte probes ---
# Probe exact sizes and validators only after the live set passes the allowlist gate.
# HEAD is preferred; a one-byte Range GET is the explicit fail-closed fallback when
# Content-Length is absent. No full data bytes are downloaded during this audit.
probe_records = []
for record in missing.select("canonical_object_key", "urban_url").iter_rows(named=True):
    key = record["canonical_object_key"]
    url = record["urban_url"]
    head_response = session.head(url, allow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
    head_status = head_response.status_code
    exact_bytes = None
    byte_evidence_method = None
    if head_response.ok and head_response.headers.get("Content-Length") is not None:
        exact_bytes = int(head_response.headers["Content-Length"])
        byte_evidence_method = "HEAD Content-Length"
    else:
        range_response = session.get(
            url,
            headers={"Range": "bytes=0-0"},
            stream=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        assert range_response.status_code == 206, (
            f"STOP: exact-size fallback for {key} did not return HTTP 206"
        )
        content_range = range_response.headers.get("Content-Range", "")
        range_match = re.fullmatch(r"bytes\s+0-0/(\d+)", content_range)
        assert range_match, f"STOP: malformed Content-Range for {key}: {content_range!r}"
        exact_bytes = int(range_match.group(1))
        byte_evidence_method = "GET Range bytes=0-0 Content-Range"
        range_response.close()
    assert exact_bytes is not None and exact_bytes > 0, f"STOP: no exact byte size for {key}"
    probe_records.append(
        {
            "canonical_object_key": key,
            "source_head_http_status": head_status,
            "source_exact_bytes": exact_bytes,
            "source_byte_evidence_method": byte_evidence_method,
            "source_etag": head_response.headers.get("ETag"),
            "source_last_modified": head_response.headers.get("Last-Modified"),
            "source_accept_ranges": head_response.headers.get("Accept-Ranges"),
            "source_content_type": head_response.headers.get("Content-Type"),
            "source_final_url": head_response.url,
            "source_probe_observed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    print(f"  [SIZE] {key}: {exact_bytes:,} bytes via {byte_evidence_method}")
probe_df = pl.from_dicts(probe_records, infer_schema_length=None)
reconciliation = reconciliation.join(
    probe_df,
    on="canonical_object_key",
    how="left",
    validate="1:1",
)
exact_source_bytes = int(probe_df["source_exact_bytes"].sum())
assert exact_source_bytes <= MAX_EXACT_SOURCE_BYTES, (
    f"STOP: exact source bytes {exact_source_bytes:,} exceed cap {MAX_EXACT_SOURCE_BYTES:,}"
)
print(f"[PASS] Exact missing-source total: {exact_source_bytes:,} bytes (cap {MAX_EXACT_SOURCE_BYTES:,})")

# --- Validate: Canonicalization and semantic edge cases ---
# Confirm year stripping is terminal-only and the Campus Crime identity triad is
# explicitly represented rather than collapsed to one misleading source token.
assert reconciliation.filter(
    pl.col("canonical_object_key").str.contains(r"_\d{4}$")
).select((pl.col("bulk_family_key") != pl.col("canonical_object_key")).all()).item(), (
    "STOP: terminal year shards were not separated from bulk-family keys"
)
unsuffixed_data = urban_objects.filter(
    (pl.col("object_kind") == "data") & pl.col("year_shard").is_null()
)
assert unsuffixed_data.height > 0, "STOP: expected unsuffixed multi-year data objects"
assert unsuffixed_data.select(
    (pl.col("bulk_family_key") == pl.col("canonical_object_key")).all()
).item(), "STOP: unsuffixed object stem was altered"

campus_endpoint = endpoint_snapshot.filter(
    (pl.col("class_name") == "Campus Crime") | (pl.col("endpoint_source_slug") == "campus-crime")
)
campus_bulk = urban_snapshot.filter(pl.col("file_dir") == "csafety")
assert campus_endpoint.height >= 1 and campus_bulk.height >= 1, (
    "STOP: Campus Crime/campus-crime/csafety identity triad not observed"
)
assert campus_endpoint["campus_crime_naming_note"].null_count() == 0
assert campus_bulk["campus_crime_naming_note"].null_count() == 0
print("[PASS] Terminal-only year canonicalization and Campus Crime naming triad")

# --- Transform: Audit summary ---
# Store one row per metric so drift is machine-readable. Baseline differences are
# classifications, not silent assertion changes; only the staging safety envelope
# above is a hard prerequisite for continuing to script 2.
hf_file_count = hf_snapshot.filter(pl.col("type") == "file").height
hf_directory_count = hf_snapshot.filter(pl.col("type") == "directory").height
exact_match_count = reconciliation.filter(
    pl.col("comparison_status") == "exact_normalized_match"
).height
summary_metrics = [
    ("urban_endpoint_rows", len(endpoint_rows), BASELINE_ENDPOINT_ROWS),
    ("urban_manifest_rows", len(urban_rows), BASELINE_MANIFEST_ROWS),
    ("urban_unique_objects", urban_objects.height, BASELINE_UNIQUE_OBJECTS),
    ("hf_tree_entries", hf_snapshot.height, BASELINE_HF_TREE_ENTRIES),
    ("hf_directories", hf_directory_count, 14),
    ("hf_files", hf_file_count, BASELINE_HF_FILES),
    ("hf_source_objects", hf_source_objects.height, BASELINE_HF_SOURCE_OBJECTS),
    ("exact_normalized_matches", exact_match_count, BASELINE_MATCHES),
    ("urban_only_data_objects", missing.height, BASELINE_MISSING),
    ("hf_only_data_objects", hf_only.height, 0),
    ("codebook_gaps", codebook_gaps.height, 0),
    ("missing_exact_source_bytes", exact_source_bytes, BASELINE_EXACT_SOURCE_BYTES),
]
audit_summary = pl.from_dicts(
    [
        {
            "snapshot_id": SNAPSHOT_ID,
            "observed_at_utc": OBSERVED_AT_UTC,
            "metric": metric,
            "observed_value": observed,
            "baseline_value": baseline,
            "drift_classification": "MATCH_BASELINE" if observed == baseline else "DRIFT_OBSERVED",
            "staging_gate_status": "PASS",
        }
        for metric, observed, baseline in summary_metrics
    ]
)

# --- Save ---
# Persist all durable tabular artifacts as Parquet with explicit, stable settings.
# Zstandard level 3 and statistics are fixed here and reused across the lifecycle.
endpoint_snapshot.write_parquet(
    ENDPOINT_SNAPSHOT_PATH, compression="zstd", compression_level=3, statistics=True
)
urban_snapshot.write_parquet(
    URBAN_SNAPSHOT_PATH, compression="zstd", compression_level=3, statistics=True
)
hf_snapshot.write_parquet(
    HF_SNAPSHOT_PATH, compression="zstd", compression_level=3, statistics=True
)
bridge.write_parquet(BRIDGE_PATH, compression="zstd", compression_level=3, statistics=True)
reconciliation.sort("canonical_object_key").write_parquet(
    OBJECT_MANIFEST_PATH, compression="zstd", compression_level=3, statistics=True
)
audit_summary.write_parquet(
    AUDIT_SUMMARY_PATH, compression="zstd", compression_level=3, statistics=True
)

# --- Validate: Durable outputs ---
# Independently reopen each output and compare exact shapes to its in-memory source.
# This validates both serialization and immediate readability before staging begins.
for output_path, expected_shape in [
    (ENDPOINT_SNAPSHOT_PATH, endpoint_snapshot.shape),
    (URBAN_SNAPSHOT_PATH, urban_snapshot.shape),
    (HF_SNAPSHOT_PATH, hf_snapshot.shape),
    (BRIDGE_PATH, bridge.shape),
    (OBJECT_MANIFEST_PATH, reconciliation.shape),
    (AUDIT_SUMMARY_PATH, audit_summary.shape),
]:
    assert output_path.exists(), f"STOP: missing audit output {output_path}"
    reopened = pl.read_parquet(output_path)
    assert reopened.shape == expected_shape, (
        f"STOP: durable shape mismatch for {output_path.name}: "
        f"{reopened.shape} != {expected_shape}"
    )
    print(f"  [PASS] {output_path.name}: {reopened.height:,} rows x {reopened.width} columns")

print("\n" + "=" * 80)
print("MA1 VALIDATION: PASSED")
print(f"Live allowlisted missing objects: {missing.height}")
print(f"Exact source bytes: {exact_source_bytes}")
print(f"Object manifest: {OBJECT_MANIFEST_PATH}")
print(f"Endpoint-object bridge: {BRIDGE_PATH}")
print("=" * 80)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-21 18:48:48
# Command: python3 /daaf/scripts/mirror_maintenance/01_audit-education-portal-mirror.py
# Duration: 2s
# Exit code: 0
#
# --- STDOUT ---
# ================================================================================
# MIRROR MAINTENANCE 1/3: FULL-CATALOG AUDIT
# ================================================================================
# Observed at UTC: 2026-07-21T18:48:48.831318+00:00
# Urban endpoint catalog: 129 rows across 1 page(s)
# Urban download manifest: 958 rows across 1 page(s)
# Hugging Face recursive tree: 503 entries across 1 page(s)
# [PASS] Snapshot row preservation and endpoint/bulk-row key uniqueness
# [PASS] Endpoint-object bridge preserves all 958 manifest associations
# 
# Derived live reconciliation:
#   Urban unique objects: 495
#   HF source objects: 487
#   Exact normalized matches: 487
#   Urban-only data objects: 8
#   HF-only data objects: 0
#   Codebook gaps: 0
#     MISSING ccd/schools_ccd_enrollment_2024
#     MISSING ccd/schools_ccd_lea_enrollment_2024
#     MISSING ipeds/colleges_ipeds_fall-enrollment-age_2021
#     MISSING ipeds/colleges_ipeds_fall-enrollment-age_2022
#     MISSING ipeds/colleges_ipeds_fall-enrollment-age_2023
#     MISSING ipeds/colleges_ipeds_fall-enrollment-age_2024
#     MISSING ipeds/colleges_ipeds_fall-enrollment-race_2023
#     MISSING ipeds/colleges_ipeds_fall-enrollment-race_2024
# [PASS] Live missing set exactly equals approved eight-object allowlist
#   [SIZE] ccd/schools_ccd_enrollment_2024: 930,870,805 bytes via HEAD Content-Length
#   [SIZE] ccd/schools_ccd_lea_enrollment_2024: 158,903,014 bytes via HEAD Content-Length
#   [SIZE] ipeds/colleges_ipeds_fall-enrollment-age_2021: 37,028,939 bytes via HEAD Content-Length
#   [SIZE] ipeds/colleges_ipeds_fall-enrollment-age_2022: 18,239,410 bytes via HEAD Content-Length
#   [SIZE] ipeds/colleges_ipeds_fall-enrollment-age_2023: 36,566,443 bytes via HEAD Content-Length
#   [SIZE] ipeds/colleges_ipeds_fall-enrollment-age_2024: 17,850,786 bytes via HEAD Content-Length
#   [SIZE] ipeds/colleges_ipeds_fall-enrollment-race_2023: 115,349,116 bytes via HEAD Content-Length
#   [SIZE] ipeds/colleges_ipeds_fall-enrollment-race_2024: 114,037,574 bytes via HEAD Content-Length
# [PASS] Exact missing-source total: 1,428,846,087 bytes (cap 1,500,000,000)
# [PASS] Terminal-only year canonicalization and Campus Crime naming triad
#   [PASS] 2026-07-21_urban-api-endpoint-catalog.parquet: 129 rows x 27 columns
#   [PASS] 2026-07-21_urban-download-manifest.parquet: 958 rows x 23 columns
#   [PASS] 2026-07-21_huggingface-tree.parquet: 503 rows x 16 columns
#   [PASS] 2026-07-21_endpoint-object-bridge.parquet: 958 rows x 17 columns
#   [PASS] 2026-07-21_mirror-object-reconciliation.parquet: 495 rows x 47 columns
#   [PASS] 2026-07-21_mirror-audit-summary.parquet: 12 rows x 7 columns
# 
# ================================================================================
# MA1 VALIDATION: PASSED
# Live allowlisted missing objects: 8
# Exact source bytes: 1428846087
# Object manifest: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/catalog/2026-07-21_mirror-object-reconciliation.parquet
# Endpoint-object bridge: /daaf/research/2026-07-21_FrameworkDev_EducationPortalSkills/2026-07-21_education-portal-mirror-staging/catalog/2026-07-21_endpoint-object-bridge.parquet
# ================================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
