#!/usr/bin/env python3
"""
Mirror maintenance 4/N: delta-classify the old HF mirror against the live
Education Data Portal v0.26.1 catalog to plan a new versioned mirror build.

Task: delta-classify-mirror-v2
Lifecycle: local audit / build-planning only (no remote-write path)
Depends on: live Urban api-downloads manifest, live Hugging Face old-mirror tree,
            2026-07-21 audit reconciliation (July HEAD baseline + HF fallback),
            8 July-staged parquet objects (on-disk sizes for the CSV->parquet ratio)
Inputs: Urban download manifest (authoritative v0.26.1 object catalog);
        old HF mirror recursive tree (per-file sizes + LFS sha256);
        July reconciliation parquet; July staged parquet files
Outputs: dated delta-classification manifest (Parquet) + build size estimate
         (Parquet) + human-readable Markdown summary
Checkpoint: MV2-B1 (Workstream B step 1 of the Mirror V2 Update)

Network operations are bounded to GET (catalog pages) and HEAD (per-object source
metadata) against public read-only endpoints. No source data bytes are downloaded:
sizes come from HEAD Content-Length only. There is no upload/commit/publish path.

Network robustness: Urban's API was intermittently unavailable earlier today.
Every per-object HEAD is wrapped in try/except; a consecutive-failure circuit
breaker stops probing (rather than hammering) a downed API, records how far the
run got, and still emits a COMPLETE classification manifest (unprobed objects are
classified conservatively as candidate-revised). The manifest fetch — the one
hard dependency — retries with backoff before giving up.
"""

import re
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import requests

# --- Config ---
# Immutable run boundary, dated output paths, and the ground-truth facts the audit
# reconciles against. The old mirror is FROZEN at its v0.24.0-era vintage (487
# source objects = 396 parquet data + 91 xls codebooks); the live Urban catalog is
# v0.26.1 (released 2026-08-05). This script computes the object-level delta between
# those two states so a new versioned mirror can be assembled.
BASE_DIR = Path("/daaf")
V2_PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
OUTPUT_DIR = V2_PROJECT_DIR / "2026-08-06_mirror-v2-audit"
DATE_PREFIX = "2026-08-06"

# Prior-session artifacts reused as baselines (read-only).
JULY_PROJECT_DIR = BASE_DIR / "research" / "2026-07-21_FrameworkDev_EducationPortalSkills"
JULY_STAGING_ROOT = JULY_PROJECT_DIR / "2026-07-21_education-portal-mirror-staging"
JULY_RECONCILIATION_PATH = (
    JULY_STAGING_ROOT / "catalog" / "2026-07-21_mirror-object-reconciliation.parquet"
)
JULY_HF_TREE_PATH = JULY_STAGING_ROOT / "catalog" / "2026-07-21_huggingface-tree.parquet"
JULY_STAGED_ROOT = JULY_STAGING_ROOT / "staged"

# Live endpoints (same repo/URL patterns as 01_audit-education-portal-mirror.py).
URBAN_MANIFEST_URL = "https://educationdata.urban.org/api/v1/api-downloads/"
HF_TREE_URL = (
    "https://huggingface.co/api/datasets/brhkim/education_data_portal_mirror/"
    "tree/main?recursive=true&limit=1000"
)
URBAN_CSV_ROOT = "https://educationdata.urban.org/csv"
HF_RESOLVE_ROOT = (
    "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main"
)

# Ground-truth composition of the frozen old mirror (see task context + July audit).
OLD_MIRROR_DATA_OBJECTS = 396
OLD_MIRROR_CODEBOOK_OBJECTS = 91
OLD_MIRROR_TOTAL_OBJECTS = 487

# The 14 known Portal source directories (bulk file_dir values). New sources would
# be reported as drift; a MISSING known source fails the coverage assertion.
EXPECTED_SOURCES = {
    "ccd", "ipeds", "crdc", "saipe", "edfacts", "scorecard", "fsa",
    "nhgis", "nccs", "nacubo", "csafety", "meps", "pseo", "eada",
}

# Old-mirror collection date: files whose current source Last-Modified post-dates
# this were regenerated after our snapshot and are therefore candidate-revised.
OLD_MIRROR_COLLECTION_DATE = datetime(2026, 2, 7, tzinfo=timezone.utc)

# Changelog-authoritative revision rule (Portal v0.26.1 release notes, 2026-08-05):
# "corrected year alignment of IPEDS Graduation Rates 150% data covering 1996-2023"
# — a retroactive revision of EXISTING data. REVISION (v04a): the live catalog serves
# Graduation Rates 150% as a SINGLE multi-year file `ipeds/colleges_ipeds_grad-rates`
# (no per-year shard; the base object covers all years 1996-2023), confirmed by the
# 2026-08-06 audit. The v04 regex assumed a `grad-rates_{year}` shard that does not
# exist, so it matched nothing. This pattern matches the base 150% object and, for
# robustness, any hypothetical per-year form, while the trailing-dash boundary keeps
# `-200pct`/`-pell` (added/appended, not retroactively corrected) out of the strict
# changelog bucket — those remain caught by the Last-Modified rule as candidate-revised.
GRAD_RATES_150_PATTERN = re.compile(r"^ipeds/colleges_ipeds_grad-rates(?:_(\d{4}))?$")
GRAD_RATES_150_REVISED_MIN_YEAR = 1996
GRAD_RATES_150_REVISED_MAX_YEAR = 2023

# The 8 objects staged in the 2026-07-21 session (checked for currency in step e).
JULY_STAGED_KEYS = {
    "ccd/schools_ccd_enrollment_2024",
    "ccd/schools_ccd_lea_enrollment_2024",
    "ipeds/colleges_ipeds_fall-enrollment-age_2021",
    "ipeds/colleges_ipeds_fall-enrollment-age_2022",
    "ipeds/colleges_ipeds_fall-enrollment-age_2023",
    "ipeds/colleges_ipeds_fall-enrollment-age_2024",
    "ipeds/colleges_ipeds_fall-enrollment-race_2023",
    "ipeds/colleges_ipeds_fall-enrollment-race_2024",
}

REQUEST_TIMEOUT_SECONDS = 60
MANIFEST_MAX_RETRIES = 3
MANIFEST_MAX_PAGES = 20
HEAD_PACING_SECONDS = 0.2
CONSECUTIVE_FAILURE_BREAKER = 20

SNAPSHOT_ID = "2026-08-06_mirror-v2-delta-classification"
OBSERVED_AT_UTC = datetime.now(timezone.utc).isoformat()
ACCESS_DATE = OBSERVED_AT_UTC[:10]

MANIFEST_OUT_PATH = OUTPUT_DIR / f"{DATE_PREFIX}_mirror-v2-delta-manifest.parquet"
BUILD_ESTIMATE_OUT_PATH = OUTPUT_DIR / f"{DATE_PREFIX}_mirror-v2-build-estimate.parquet"
SUMMARY_MD_PATH = OUTPUT_DIR / f"{DATE_PREFIX}_mirror-v2-delta-summary.md"

print("=" * 80)
print("MIRROR MAINTENANCE 4/N: DELTA CLASSIFICATION (old mirror vs Portal v0.26.1)")
print("=" * 80)
print(f"Observed at UTC: {OBSERVED_AT_UTC}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "DAAF-local-mirror-delta-audit/1.0"})

# --- Load: Urban catalog (authoritative v0.26.1 object list) ---
# INTENT: retrieve every api-downloads row, following the API's own `next` link.
# REASONING: this manifest is the one hard dependency, so it retries with backoff
# before giving up rather than failing on a single transient timeout. ASSUMES: the
# response envelope exposes `results` (list) and an optional `next` URL.
urban_rows = []
next_url = URBAN_MANIFEST_URL
page_number = 0
while next_url is not None:
    page_number += 1
    assert page_number <= MANIFEST_MAX_PAGES, "STOP: Urban manifest exceeded page bound"
    payload = None
    last_error = None
    for attempt in range(1, MANIFEST_MAX_RETRIES + 1):
        try:
            response = session.get(next_url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as error:  # noqa: BLE001 - transient network is expected here
            last_error = error
            wait_seconds = 5 * attempt
            print(f"  [RETRY] manifest page {page_number} attempt {attempt} failed: {error!r}; waiting {wait_seconds}s")
            time.sleep(wait_seconds)
    assert payload is not None, (
        f"STOP: Urban manifest page {page_number} unreachable after "
        f"{MANIFEST_MAX_RETRIES} attempts (last error: {last_error!r}). The manifest "
        "is the authoritative catalog and cannot be substituted; rerun when Urban recovers."
    )
    assert isinstance(payload, dict) and isinstance(payload.get("results"), list), (
        "STOP: unexpected Urban manifest response schema"
    )
    urban_rows.extend(payload["results"])
    next_url = payload.get("next")
print(f"Urban download manifest (v0.26.1): {len(urban_rows):,} rows across {page_number} page(s)")

# --- Load: old HF mirror inventory (live, with July fallback) ---
# INTENT: retrieve the frozen mirror's per-file sizes and LFS sha256 oids.
# REASONING: the tree API is the size basis for carry-forward bytes and the sha256
# is the identity anchor for unchanged objects. If the live tree is unreachable we
# fall back to the July snapshot (the mirror is frozen, so it has not changed) and
# record the provenance. ASSUMES: each live response is a flat JSON list paginated
# by RFC Link headers.
hf_rows = []
hf_inventory_source = None
try:
    next_url = HF_TREE_URL
    page_number = 0
    while next_url is not None:
        page_number += 1
        assert page_number <= 10, "STOP: HF tree exceeded page bound"
        response = session.get(next_url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        assert isinstance(payload, list), "STOP: unexpected HF tree response schema"
        hf_rows.extend(payload)
        link_header = response.headers.get("Link", "")
        next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
        next_url = next_match.group(1) if next_match else None
    hf_inventory_source = "live_hf_tree"
    print(f"Hugging Face old-mirror tree (live): {len(hf_rows):,} entries across {page_number} page(s)")
except Exception as error:  # noqa: BLE001 - fall back to frozen-mirror July snapshot
    print(f"  [FALLBACK] live HF tree unreachable ({error!r}); using July snapshot")
    assert JULY_HF_TREE_PATH.exists(), f"STOP: July HF snapshot missing: {JULY_HF_TREE_PATH}"
    july_hf = pl.read_parquet(JULY_HF_TREE_PATH)
    # July snapshot already carries flattened columns; reshape to the raw-tree shape
    # this script consumes below so downstream logic is source-agnostic.
    hf_rows = [
        {
            "type": row["type"],
            "oid": row["oid"],
            "size": row["size"],
            "path": row["path"],
            "lfs": {"oid": row["lfs_oid"], "size": row["lfs_size"]},
        }
        for row in july_hf.iter_rows(named=True)
    ]
    hf_inventory_source = "july_snapshot_fallback"
    print(f"Hugging Face old-mirror tree (July fallback): {len(hf_rows):,} entries")

# --- Transform: canonical object identity (shared scheme with 01_audit) ---
# INTENT: derive one format-neutral canonical key per object on both sides so the
# CSV-vs-Parquet extension difference does not create false new/removed pairs.
# REASONING: canonical_object_key = "{file_dir}/{stem}" where stem drops the source
# extension; this is the exact key 01_audit reconciled on. ASSUMES: data files end
# in .csv (Urban) / .parquet (HF) and codebooks end in .xls on both sides.
urban_records = []
for row in urban_rows:
    file_dir = str(row.get("file_dir") or "").strip("/")
    file_name = str(row.get("file_name") or "").strip()
    lower_name = file_name.lower()
    if lower_name.endswith(".csv"):
        object_kind, stem = "data", file_name[:-4]
    elif lower_name.endswith(".xls"):
        object_kind, stem = "codebook", file_name[:-4]
    else:
        object_kind, stem = "other", file_name
    canonical_object_key = f"{file_dir}/{stem}"
    year_match = re.search(r"_(\d{4})$", stem) if object_kind == "data" else None
    urban_records.append(
        {
            "canonical_object_key": canonical_object_key,
            "source": file_dir,
            "object_kind": object_kind,
            "year_shard": int(year_match.group(1)) if year_match else None,
            "urban_url": f"{URBAN_CSV_ROOT}/{file_dir}/{file_name}",
        }
    )
# Deduplicate the manifest to one row per exact object (the manifest repeats objects
# across presentation endpoints, exactly as 01_audit observed).
urban_catalog = (
    pl.from_dicts(urban_records, infer_schema_length=None)
    .filter(pl.col("object_kind").is_in(["data", "codebook"]))
    .group_by("canonical_object_key")
    .agg(
        pl.col("source").first(),
        pl.col("object_kind").first(),
        pl.col("year_shard").first(),
        pl.col("urban_url").first(),
    )
)
urban_keys = set(urban_catalog["canonical_object_key"].to_list())
print(f"Urban catalog unique source objects: {urban_catalog.height:,}")

hf_records = []
for row in hf_rows:
    if row.get("type") != "file":
        continue
    hf_path = str(row.get("path") or "")
    lower_path = hf_path.lower()
    lfs = row.get("lfs") if isinstance(row.get("lfs"), dict) else {}
    if lower_path.endswith(".parquet"):
        object_kind, canonical_object_key = "data", hf_path[:-8]
    elif lower_path.endswith(".xls"):
        object_kind, canonical_object_key = "codebook", hf_path[:-4]
    else:
        continue  # README/.gitattributes are administrative, not source objects
    hf_records.append(
        {
            "canonical_object_key": canonical_object_key,
            "old_mirror_path": hf_path,
            "old_mirror_object_kind": object_kind,
            "old_mirror_size_bytes": row.get("size"),
            "old_mirror_lfs_sha256": (lfs.get("oid") if lfs else None) or row.get("oid"),
            "old_mirror_url": f"{HF_RESOLVE_ROOT}/{hf_path}",
        }
    )
old_mirror = pl.from_dicts(hf_records, infer_schema_length=None)
old_mirror_keys = set(old_mirror["canonical_object_key"].to_list())
old_data_count = old_mirror.filter(pl.col("old_mirror_object_kind") == "data").height
old_codebook_count = old_mirror.filter(pl.col("old_mirror_object_kind") == "codebook").height
print(f"Old mirror source objects: {old_mirror.height:,} ({old_data_count} data + {old_codebook_count} codebook)")

# --- Validate: frozen old-mirror composition ---
# The entire delta premise is that the old mirror is frozen at 396+91=487. If the
# live tree disagrees, the baseline is not what we think it is: fail loudly.
assert old_mirror["canonical_object_key"].n_unique() == old_mirror.height, (
    "STOP: duplicate canonical keys in old-mirror inventory"
)
assert old_data_count == OLD_MIRROR_DATA_OBJECTS, (
    f"STOP: old-mirror data objects {old_data_count} != expected {OLD_MIRROR_DATA_OBJECTS}"
)
assert old_codebook_count == OLD_MIRROR_CODEBOOK_OBJECTS, (
    f"STOP: old-mirror codebook objects {old_codebook_count} != expected {OLD_MIRROR_CODEBOOK_OBJECTS}"
)
assert old_mirror.height == OLD_MIRROR_TOTAL_OBJECTS, (
    f"STOP: old-mirror total {old_mirror.height} != expected {OLD_MIRROR_TOTAL_OBJECTS}"
)
print(f"[PASS] Old mirror composition reconciles to {OLD_MIRROR_TOTAL_OBJECTS} (396 data + 91 codebook)")

# --- Load: July HEAD baseline for the 8 staged objects ---
# INTENT: recover the source metadata the July audit recorded for the 8 staged
# objects. REASONING: step (e) compares CURRENT source HEAD against this baseline to
# decide whether each staged parquet is still current. ASSUMES: the July
# reconciliation parquet carries source_exact_bytes / source_etag / source_last_modified.
july_baseline = {}
if JULY_RECONCILIATION_PATH.exists():
    july_recon = pl.read_parquet(JULY_RECONCILIATION_PATH)
    july_cols = set(july_recon.columns)
    baseline_cols = [c for c in ["source_exact_bytes", "source_etag", "source_last_modified"] if c in july_cols]
    if baseline_cols:
        july_slice = july_recon.filter(
            pl.col("canonical_object_key").is_in(list(JULY_STAGED_KEYS))
        ).select(["canonical_object_key", *baseline_cols])
        july_baseline = {r["canonical_object_key"]: r for r in july_slice.iter_rows(named=True)}
    print(f"July HEAD baseline recovered for {len(july_baseline)} staged object(s); columns={baseline_cols}")
else:
    print("  [WARN] July reconciliation parquet absent; staged-object currency falls back to conservative")

# --- Load: on-disk staged parquet sizes (CSV->parquet ratio basis) ---
# INTENT: measure the realized CSV->parquet compression of the 8 staged objects.
# REASONING: this empirical ratio (staged parquet bytes / recorded source CSV bytes)
# is the most defensible basis for estimating the parquet footprint of fresh
# fetches, since it comes from THIS pipeline's own conversion settings. ASSUMES: the
# staged files are the zstd-3 parquet outputs of the July staging run.
staged_parquet_bytes_total = 0
staged_csv_bytes_total = 0
staged_ratio_pairs = 0
for key in sorted(JULY_STAGED_KEYS):
    staged_file = JULY_STAGED_ROOT / f"{key}.parquet"
    if not staged_file.exists():
        continue
    parquet_bytes = staged_file.stat().st_size
    baseline = july_baseline.get(key)
    csv_bytes = int(baseline["source_exact_bytes"]) if baseline and baseline.get("source_exact_bytes") is not None else None
    staged_parquet_bytes_total += parquet_bytes
    if csv_bytes:
        staged_csv_bytes_total += csv_bytes
        staged_ratio_pairs += 1
if staged_csv_bytes_total > 0:
    CSV_TO_PARQUET_RATIO = staged_parquet_bytes_total / staged_csv_bytes_total
    ratio_basis = f"{staged_ratio_pairs} July-staged object(s): {staged_parquet_bytes_total:,} parquet / {staged_csv_bytes_total:,} csv"
else:
    # Conservative documented fallback if the July CSV baseline is unavailable.
    CSV_TO_PARQUET_RATIO = 0.15
    ratio_basis = "fallback assumption 0.15 (no July CSV baseline available)"
print(f"CSV->parquet ratio: {CSV_TO_PARQUET_RATIO:.4f} (basis: {ratio_basis})")

# --- Transform: union object frame + membership ---
# INTENT: one row per union object (old mirror UNION current catalog) so both
# removed (old-only) and new (catalog-only) objects stay visible alongside the
# intersection. REASONING: an outer join on the canonical key is the auditable
# structure; membership booleans drive classification. ASSUMES: keys are unique on
# each side (asserted above / below).
assert urban_catalog["canonical_object_key"].n_unique() == urban_catalog.height, (
    "STOP: duplicate canonical keys in Urban catalog after dedup"
)
delta = urban_catalog.join(
    old_mirror, on="canonical_object_key", how="full", coalesce=True, validate="1:1"
).with_columns(
    pl.col("canonical_object_key").is_in(list(urban_keys)).alias("in_current_catalog"),
    pl.col("canonical_object_key").is_in(list(old_mirror_keys)).alias("in_old_mirror"),
)
# Coalesce source/kind from whichever side is present (old-only rows lack Urban cols).
delta = delta.with_columns(
    pl.coalesce(pl.col("source"), pl.col("canonical_object_key").str.split("/").list.first()).alias("source"),
    pl.coalesce(pl.col("object_kind"), pl.col("old_mirror_object_kind")).alias("object_kind"),
)
print(f"Union objects (old UNION catalog): {delta.height:,}")

# --- Load: per-object source HEAD probes (intersection + new) ---
# INTENT: capture current source Content-Length / Last-Modified / ETag for every
# object present in the live catalog. REASONING: Last-Modified vs the old-mirror
# collection date is the primary hard evidence for the revised/unchanged split, and
# Content-Length is the fresh-fetch byte basis. Removed (old-only) objects have no
# live URL and are skipped. ASSUMES: Urban serves pre-generated CSVs whose
# Last-Modified reflects regeneration time.
#
# Robustness: each HEAD is isolated in try/except; a run of CONSECUTIVE_FAILURE_BREAKER
# failures trips the breaker (Urban likely down) — probing stops, remaining objects
# are left unprobed (classified conservatively below), and the run still completes.
probe_targets = delta.filter(pl.col("in_current_catalog")).select(
    "canonical_object_key", "urban_url"
).sort("canonical_object_key")
probe_records = []
consecutive_failures = 0
breaker_tripped = False
probed_ok = 0
probed_failed = 0
print(f"HEAD-probing {probe_targets.height:,} live-catalog objects (pacing {HEAD_PACING_SECONDS}s)...")
for i, record in enumerate(probe_targets.iter_rows(named=True)):
    key = record["canonical_object_key"]
    url = record["urban_url"]
    if breaker_tripped:
        probe_records.append({"canonical_object_key": key, "head_probe_ok": False,
                              "head_probe_method": "skipped_breaker_tripped"})
        continue
    try:
        head = session.head(url, allow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
        content_length = head.headers.get("Content-Length")
        probe_records.append({
            "canonical_object_key": key,
            "urban_head_http_status": head.status_code,
            "current_source_bytes": int(content_length) if content_length is not None else None,
            "current_last_modified": head.headers.get("Last-Modified"),
            "current_etag": head.headers.get("ETag"),
            "head_probe_ok": bool(head.ok),
            "head_probe_method": "HEAD Content-Length" if content_length is not None else "HEAD no Content-Length",
        })
        consecutive_failures = 0
        probed_ok += 1
    except Exception as error:  # noqa: BLE001 - per-object isolation; keep going
        probe_records.append({"canonical_object_key": key, "head_probe_ok": False,
                              "head_probe_method": f"probe_failed: {type(error).__name__}"})
        consecutive_failures += 1
        probed_failed += 1
        if consecutive_failures >= CONSECUTIVE_FAILURE_BREAKER:
            breaker_tripped = True
            print(f"  [BREAKER] {consecutive_failures} consecutive HEAD failures at object {i + 1}; "
                  "halting probes (Urban likely down). Remaining objects left unprobed.")
    time.sleep(HEAD_PACING_SECONDS)
probe_df = pl.from_dicts(probe_records, infer_schema_length=None)
print(f"HEAD probes: {probed_ok:,} ok, {probed_failed:,} failed, breaker_tripped={breaker_tripped}")

delta = delta.join(probe_df, on="canonical_object_key", how="left")

# --- Transform: classification ---
# INTENT: assign every union object exactly one of new / removed / revised /
# candidate-revised / presumed-unchanged, with the evidence method recorded.
# REASONING: membership decides new vs removed vs intersection; within the
# intersection the evidence hierarchy is (1) changelog-authoritative grad-rates-150%
# revision, (2) HEAD Last-Modified vs the collection date, (3) conservative
# candidate-revised when evidence is missing. A false "revised" only costs a
# re-download; a false "unchanged" ships stale data — so ambiguity resolves toward
# candidate-revised. ASSUMES: Last-Modified is parseable RFC-1123.
def _parse_last_modified(value):
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _is_grad_rates_150(key):
    match = GRAD_RATES_150_PATTERN.match(key)
    if not match:
        return False
    # Single multi-year file (no year group) is always the 150% object; a per-year
    # form (should one ever appear) is bounded to the corrected 1996-2023 window.
    if match.group(1) is None:
        return True
    year = int(match.group(1))
    return GRAD_RATES_150_REVISED_MIN_YEAR <= year <= GRAD_RATES_150_REVISED_MAX_YEAR


classified = []
for row in delta.iter_rows(named=True):
    key = row["canonical_object_key"]
    in_catalog = row["in_current_catalog"]
    in_old = row["in_old_mirror"]
    if in_catalog and not in_old:
        classification, method, evidence = "new", "catalog_membership", "present in v0.26.1 catalog, absent from old mirror"
    elif in_old and not in_catalog:
        classification, method, evidence = "removed", "catalog_membership", "present in old mirror, absent from v0.26.1 catalog"
    else:
        # Intersection: apply the evidence hierarchy.
        if _is_grad_rates_150(key):
            classification = "revised"
            method = "changelog_v0.26.1_retroactive"
            evidence = (
                "IPEDS Grad Rates 150% (single multi-year file, 1996-2023) retroactively "
                f"corrected in Portal v0.26.1; corroborated by source Last-Modified "
                f"{row.get('current_last_modified')}"
            )
        else:
            last_modified_dt = _parse_last_modified(row.get("current_last_modified"))
            if not row.get("head_probe_ok"):
                classification = "candidate-revised"
                method = "conservative_no_probe"
                evidence = f"source HEAD unavailable ({row.get('head_probe_method')}); conservative"
            elif last_modified_dt is None:
                classification = "candidate-revised"
                method = "conservative_no_last_modified"
                evidence = "HEAD ok but no parseable Last-Modified; conservative"
            elif last_modified_dt > OLD_MIRROR_COLLECTION_DATE:
                classification = "candidate-revised"
                method = "head_last_modified_after_collection"
                evidence = f"source Last-Modified {row.get('current_last_modified')} > collection 2026-02-07"
            else:
                classification = "presumed-unchanged"
                method = "head_last_modified_before_collection"
                evidence = f"source Last-Modified {row.get('current_last_modified')} <= collection 2026-02-07"
    classified.append({"canonical_object_key": key, "classification": classification,
                       "classification_method": method, "classification_evidence": evidence})
classified_df = pl.from_dicts(classified, infer_schema_length=None)
delta = delta.join(classified_df, on="canonical_object_key", how="left", validate="1:1")

# --- Transform: build action + estimated parquet footprint ---
# INTENT: attach the build decision and a size estimate to each object.
# REASONING: presumed-unchanged data/codebooks carry forward from the old mirror at
# their known HF size (no re-fetch); new + revised + candidate-revised objects are
# fetched fresh from Urban. Data objects convert CSV->parquet at the empirical
# ratio; codebooks are carried as .xls at their source size. Removed objects are
# dropped. ASSUMES: current_source_bytes is present for fresh objects (else the
# estimate is null and flagged).
delta = delta.with_columns(
    pl.when(pl.col("classification") == "presumed-unchanged").then(pl.lit("carry-forward"))
    .when(pl.col("classification") == "removed").then(pl.lit("drop"))
    .otherwise(pl.lit("fetch-fresh")).alias("build_action")
).with_columns(
    pl.when(pl.col("build_action") == "carry-forward")
    .then(pl.col("old_mirror_size_bytes"))
    .when((pl.col("build_action") == "fetch-fresh") & (pl.col("object_kind") == "data"))
    .then((pl.col("current_source_bytes") * CSV_TO_PARQUET_RATIO).round(0).cast(pl.Int64))
    .when((pl.col("build_action") == "fetch-fresh") & (pl.col("object_kind") == "codebook"))
    .then(pl.col("current_source_bytes"))
    .otherwise(None)
    .alias("est_build_bytes")
)

# --- Transform: July-staged object currency (step e) ---
# INTENT: for each of the 8 staged objects, decide whether the staged parquet is
# still current. REASONING: compare CURRENT source HEAD (bytes/etag/last-modified)
# against the July baseline; matching bytes+etag => still current; any change or
# missing baseline => re-stage (candidate-revised). ASSUMES: identical
# Content-Length AND ETag is strong evidence the source CSV is byte-identical.
staged_verdicts = []
for key in sorted(JULY_STAGED_KEYS):
    row = delta.filter(pl.col("canonical_object_key") == key)
    baseline = july_baseline.get(key)
    if row.height == 0:
        verdict, detail = "re-stage", "no longer present in current catalog"
    else:
        r = row.row(0, named=True)
        cur_bytes = r.get("current_source_bytes")
        cur_etag = r.get("current_etag")
        if not r.get("head_probe_ok"):
            verdict, detail = "re-stage-conservative", "current source HEAD unavailable"
        elif baseline is None:
            verdict, detail = "re-stage-conservative", "no July source baseline recorded"
        else:
            base_bytes = baseline.get("source_exact_bytes")
            base_etag = baseline.get("source_etag")
            if base_bytes is not None and cur_bytes is not None and int(base_bytes) == int(cur_bytes) and (
                base_etag is None or cur_etag is None or base_etag == cur_etag
            ):
                verdict = "still-current"
                detail = f"bytes match ({cur_bytes:,}); etag {'match' if base_etag == cur_etag else 'unconfirmed'}"
            else:
                verdict = "re-stage"
                detail = f"July bytes={base_bytes} vs current={cur_bytes}; etag July={base_etag} current={cur_etag}"
    staged_verdicts.append({"canonical_object_key": key, "is_july_staged": True,
                            "july_staged_verdict": verdict, "july_staged_detail": detail})
staged_df = pl.from_dicts(staged_verdicts, infer_schema_length=None)
delta = delta.join(staged_df, on="canonical_object_key", how="left").with_columns(
    pl.col("is_july_staged").fill_null(False)
)

# --- Finalize manifest columns + provenance ---
delta = delta.with_columns(
    pl.lit(SNAPSHOT_ID).alias("snapshot_id"),
    pl.lit(OBSERVED_AT_UTC).alias("observed_at_utc"),
    pl.lit(ACCESS_DATE).alias("access_date"),
    pl.lit(hf_inventory_source).alias("old_mirror_inventory_source"),
).sort(["classification", "canonical_object_key"])

# --- Validate ---
# Every union object classified exactly once; catalog objects fully covered; all 14
# known sources represented; counts reconcile against the 487-object old mirror.
assert delta["canonical_object_key"].n_unique() == delta.height, "STOP: duplicate object rows in manifest"
assert delta["classification"].null_count() == 0, "STOP: unclassified object(s)"
valid_classes = {"new", "removed", "revised", "candidate-revised", "presumed-unchanged"}
observed_classes = set(delta["classification"].unique().to_list())
assert observed_classes.issubset(valid_classes), f"STOP: unexpected classification(s): {observed_classes - valid_classes}"
catalog_covered = set(delta.filter(pl.col("in_current_catalog"))["canonical_object_key"].to_list())
assert catalog_covered == urban_keys, "STOP: catalog objects not fully covered by manifest"
observed_sources = set(delta["source"].to_list())
missing_sources = EXPECTED_SOURCES - observed_sources
assert not missing_sources, f"STOP: missing coverage for known source(s): {sorted(missing_sources)}"
for src in sorted(EXPECTED_SOURCES):
    assert delta.filter(pl.col("source") == src).height > 0, f"STOP: empty coverage for source {src}"
# Intersection + removed must reconcile to the 487-object old mirror.
intersection_count = delta.filter(pl.col("in_old_mirror") & pl.col("in_current_catalog")).height
removed_count = delta.filter(pl.col("classification") == "removed").height
assert intersection_count + removed_count == OLD_MIRROR_TOTAL_OBJECTS, (
    f"STOP: intersection {intersection_count} + removed {removed_count} != old mirror {OLD_MIRROR_TOTAL_OBJECTS}"
)
# Guard: the changelog-authoritative grad-rates-150% object must be classified
# "revised" (not merely candidate-revised). This catches naming-scheme drift that
# would otherwise silently empty the changelog-confirmed bucket (the v04 defect).
grad_rates_150 = delta.filter(
    pl.col("canonical_object_key") == "ipeds/colleges_ipeds_grad-rates"
)
assert grad_rates_150.height == 1, "STOP: base IPEDS grad-rates 150% object not found in catalog"
assert grad_rates_150["classification"].item() == "revised", (
    "STOP: IPEDS grad-rates 150% object not classified 'revised' — changelog rule regressed"
)
print("[PASS] Manifest validation: unique, fully classified, 14-source coverage, 487 reconciliation")
print("[PASS] Changelog guard: IPEDS grad-rates 150% classified 'revised'")

# --- Transform: headline counts + build size estimate ---
class_counts = {
    c: delta.filter(pl.col("classification") == c).height
    for c in sorted(valid_classes)
}
carry_forward_bytes = int(
    delta.filter(pl.col("build_action") == "carry-forward")["est_build_bytes"].fill_null(0).sum()
)
fresh_fetch_csv_bytes = int(
    delta.filter(pl.col("build_action") == "fetch-fresh")["current_source_bytes"].fill_null(0).sum()
)
fresh_fetch_est_parquet_bytes = int(
    delta.filter(pl.col("build_action") == "fetch-fresh")["est_build_bytes"].fill_null(0).sum()
)
est_total_mirror_bytes = carry_forward_bytes + fresh_fetch_est_parquet_bytes
fresh_missing_size = delta.filter(
    (pl.col("build_action") == "fetch-fresh") & pl.col("current_source_bytes").is_null()
).height

build_estimate = pl.from_dicts([
    {"snapshot_id": SNAPSHOT_ID, "observed_at_utc": OBSERVED_AT_UTC, "metric": m, "value": v}
    for m, v in [
        ("old_mirror_objects", old_mirror.height),
        ("current_catalog_objects", urban_catalog.height),
        ("union_objects", delta.height),
        ("count_new", class_counts["new"]),
        ("count_revised", class_counts["revised"]),
        ("count_candidate_revised", class_counts["candidate-revised"]),
        ("count_presumed_unchanged", class_counts["presumed-unchanged"]),
        ("count_removed", class_counts["removed"]),
        ("carry_forward_bytes", carry_forward_bytes),
        ("fresh_fetch_csv_bytes", fresh_fetch_csv_bytes),
        ("fresh_fetch_est_parquet_bytes", fresh_fetch_est_parquet_bytes),
        ("est_total_new_mirror_bytes", est_total_mirror_bytes),
        ("fresh_objects_missing_size", fresh_missing_size),
        ("head_probes_ok", probed_ok),
        ("head_probes_failed", probed_failed),
    ]
], infer_schema_length=None)

# --- Save: manifest + estimate ---
delta.write_parquet(MANIFEST_OUT_PATH, compression="zstd", compression_level=3, statistics=True)
build_estimate.write_parquet(BUILD_ESTIMATE_OUT_PATH, compression="zstd", compression_level=3, statistics=True)

# --- Save: human-readable Markdown summary ---
def _fmt_bytes(n):
    return f"{n / 1_000_000_000:.2f} GB" if n >= 1_000_000_000 else f"{n / 1_000_000:.1f} MB"


per_source = (
    delta.group_by("source")
    .agg(
        pl.col("classification").eq("new").sum().alias("new"),
        pl.col("classification").eq("revised").sum().alias("revised"),
        pl.col("classification").eq("candidate-revised").sum().alias("candidate_revised"),
        pl.col("classification").eq("presumed-unchanged").sum().alias("unchanged"),
        pl.col("classification").eq("removed").sum().alias("removed"),
        pl.col("est_build_bytes").fill_null(0).sum().alias("est_bytes"),
    )
    .sort("source")
)
removed_objects = delta.filter(pl.col("classification") == "removed").sort("canonical_object_key")
staged_report = delta.filter(pl.col("is_july_staged")).sort("canonical_object_key")

lines = []
lines.append("# Mirror V2 Delta Classification Summary")
lines.append("")
lines.append(f"- **Snapshot:** {SNAPSHOT_ID}")
lines.append(f"- **Observed (UTC):** {OBSERVED_AT_UTC}")
lines.append(f"- **Old mirror:** {old_mirror.height} objects ({old_data_count} parquet data + {old_codebook_count} xls codebooks), vintage v0.24.0-era")
lines.append(f"- **Current catalog:** Portal v0.26.1 (released 2026-08-05), {urban_catalog.height} source objects")
lines.append(f"- **Old-mirror inventory source:** {hf_inventory_source}")
lines.append(f"- **HEAD probes:** {probed_ok} ok / {probed_failed} failed (circuit-breaker tripped: {breaker_tripped})")
lines.append("")
lines.append("## Headline delta")
lines.append("")
lines.append("| Classification | Objects |")
lines.append("|---|---:|")
lines.append(f"| new | {class_counts['new']} |")
lines.append(f"| revised (changelog-confirmed) | {class_counts['revised']} |")
lines.append(f"| candidate-revised | {class_counts['candidate-revised']} |")
lines.append(f"| presumed-unchanged | {class_counts['presumed-unchanged']} |")
lines.append(f"| removed | {class_counts['removed']} |")
lines.append(f"| **union total** | **{delta.height}** |")
lines.append("")
lines.append("## Build size estimate")
lines.append("")
lines.append(f"- Carry-forward from old mirror (presumed-unchanged): **{_fmt_bytes(carry_forward_bytes)}** ({carry_forward_bytes:,} bytes)")
lines.append(f"- Fresh CSV bytes to fetch from Urban (new + revised + candidate-revised): **{_fmt_bytes(fresh_fetch_csv_bytes)}** ({fresh_fetch_csv_bytes:,} bytes)")
lines.append(f"- Estimated parquet footprint of fresh objects (ratio {CSV_TO_PARQUET_RATIO:.4f}): **{_fmt_bytes(fresh_fetch_est_parquet_bytes)}** ({fresh_fetch_est_parquet_bytes:,} bytes)")
lines.append(f"- **Estimated total new-mirror size:** **{_fmt_bytes(est_total_mirror_bytes)}** ({est_total_mirror_bytes:,} bytes)")
lines.append(f"- CSV->parquet ratio basis: {ratio_basis}")
if fresh_missing_size:
    lines.append(f"- WARNING: {fresh_missing_size} fresh object(s) lack a source size (HEAD unavailable) — excluded from byte totals")
lines.append("")
lines.append("## Per-source breakdown")
lines.append("")
lines.append("| Source | New | Revised | Cand-Revised | Unchanged | Removed | Est. bytes |")
lines.append("|---|---:|---:|---:|---:|---:|---:|")
for r in per_source.iter_rows(named=True):
    lines.append(
        f"| {r['source']} | {r['new']} | {r['revised']} | {r['candidate_revised']} | "
        f"{r['unchanged']} | {r['removed']} | {_fmt_bytes(int(r['est_bytes']))} |"
    )
lines.append("")
lines.append("## Removed objects")
lines.append("")
if removed_objects.height == 0:
    lines.append("_None — no old-mirror object is absent from the current catalog._")
else:
    for r in removed_objects.iter_rows(named=True):
        lines.append(f"- `{r['canonical_object_key']}`")
lines.append("")
lines.append("## July-staged object currency (step e)")
lines.append("")
lines.append("| Object | Classification | Staged verdict | Detail |")
lines.append("|---|---|---|---|")
for r in staged_report.iter_rows(named=True):
    lines.append(f"| `{r['canonical_object_key']}` | {r['classification']} | {r['july_staged_verdict']} | {r['july_staged_detail']} |")
lines.append("")
lines.append("## Method & limitations")
lines.append("")
lines.append("- **new/removed:** decided by catalog membership (canonical-key set difference), format-neutral (CSV/parquet vs xls).")
lines.append("- **revised:** IPEDS Grad Rates 150% files 1996-2023 are changelog-authoritative revisions per Portal v0.26.1 (retroactive year-alignment correction).")
lines.append("- **candidate-revised vs presumed-unchanged:** primary hard evidence is the source CSV's current `Last-Modified` vs the old-mirror collection date (2026-02-07). Later => candidate-revised; earlier/equal => presumed-unchanged. Missing Last-Modified or failed HEAD => conservative candidate-revised.")
lines.append("- **Limitation — Last-Modified semantics:** if Urban regenerates all bulk CSVs on each quarterly release, `Last-Modified` may post-date collection even for semantically-unchanged files, over-classifying them as candidate-revised. This is the deliberately conservative direction (a false 'revised' costs a re-download; a false 'unchanged' ships stale data). Byte-level confirmation (sha256 after fetch) is the definitive check, deferred to the build step.")
lines.append("- **Limitation — no prior HEAD baseline for the intersection:** the July audit only probed the 8 then-missing objects, so intersection classification relies on current Last-Modified rather than a before/after diff.")
lines.append(f"- **Size estimate:** parquet footprint uses an empirical CSV->parquet ratio ({ratio_basis}); codebooks (.xls) are carried at source size (no conversion). Estimates are planning figures, not exact build sizes.")
lines.append("")
SUMMARY_MD_PATH.write_text("\n".join(lines))

# --- Validate: durable outputs ---
for output_path, expected_shape in [
    (MANIFEST_OUT_PATH, delta.shape),
    (BUILD_ESTIMATE_OUT_PATH, build_estimate.shape),
]:
    assert output_path.exists(), f"STOP: missing output {output_path}"
    reopened = pl.read_parquet(output_path)
    assert reopened.shape == expected_shape, f"STOP: durable shape mismatch for {output_path.name}"
    print(f"  [PASS] {output_path.name}: {reopened.height:,} rows x {reopened.width} columns")
assert SUMMARY_MD_PATH.exists(), "STOP: markdown summary not written"

print("\n" + "=" * 80)
print("MV2-B1 DELTA CLASSIFICATION: COMPLETE")
print(f"  new={class_counts['new']} revised={class_counts['revised']} "
      f"candidate-revised={class_counts['candidate-revised']} "
      f"presumed-unchanged={class_counts['presumed-unchanged']} removed={class_counts['removed']}")
print(f"  carry-forward: {carry_forward_bytes:,} bytes")
print(f"  fresh CSV: {fresh_fetch_csv_bytes:,} bytes -> est parquet {fresh_fetch_est_parquet_bytes:,} bytes")
print(f"  est total new mirror: {est_total_mirror_bytes:,} bytes")
print(f"  manifest: {MANIFEST_OUT_PATH}")
print(f"  build estimate: {BUILD_ESTIMATE_OUT_PATH}")
print(f"  summary: {SUMMARY_MD_PATH}")
if breaker_tripped or probed_failed > 0:
    print(f"  NOTE: {probed_failed} HEAD probe(s) failed; affected objects classified conservatively.")
print("=" * 80)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-06 19:39:15
# Command: python3 /daaf/scripts/mirror_maintenance/04_delta-classify-mirror-v2_a.py
# Duration: 247s
# Exit code: 0
#
# --- STDOUT ---
# ================================================================================
# MIRROR MAINTENANCE 4/N: DELTA CLASSIFICATION (old mirror vs Portal v0.26.1)
# ================================================================================
# Observed at UTC: 2026-08-06T19:39:15.327745+00:00
# Urban download manifest (v0.26.1): 960 rows across 1 page(s)
# Hugging Face old-mirror tree (live): 503 entries across 1 page(s)
# Urban catalog unique source objects: 497
# Old mirror source objects: 487 (396 data + 91 codebook)
# [PASS] Old mirror composition reconciles to 487 (396 data + 91 codebook)
# July HEAD baseline recovered for 8 staged object(s); columns=['source_exact_bytes', 'source_etag', 'source_last_modified']
# CSV->parquet ratio: 0.0221 (basis: 8 July-staged object(s): 31,593,547 parquet / 1,428,846,087 csv)
# Union objects (old UNION catalog): 497
# HEAD-probing 497 live-catalog objects (pacing 0.2s)...
# HEAD probes: 497 ok, 0 failed, breaker_tripped=False
# [PASS] Manifest validation: unique, fully classified, 14-source coverage, 487 reconciliation
# [PASS] Changelog guard: IPEDS grad-rates 150% classified 'revised'
#   [PASS] 2026-08-06_mirror-v2-delta-manifest.parquet: 497 rows x 30 columns
#   [PASS] 2026-08-06_mirror-v2-build-estimate.parquet: 15 rows x 4 columns
# 
# ================================================================================
# MV2-B1 DELTA CLASSIFICATION: COMPLETE
#   new=10 revised=1 candidate-revised=28 presumed-unchanged=458 removed=0
#   carry-forward: 3,240,546,501 bytes
#   fresh CSV: 6,164,459,832 bytes -> est parquet 136,470,024 bytes
#   est total new mirror: 3,377,016,525 bytes
#   manifest: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/2026-08-06_mirror-v2-delta-manifest.parquet
#   build estimate: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/2026-08-06_mirror-v2-build-estimate.parquet
#   summary: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/2026-08-06_mirror-v2-delta-summary.md
# ================================================================================
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
