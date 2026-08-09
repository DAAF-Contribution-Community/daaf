#!/usr/bin/env python3
"""
Mirror maintenance 7/7: validate the assembled v2 tree and emit the build manifest.

Task: validate-mirror-v2-tree (Stage build unit 07 of 05->06->07)
Depends on: 05 (carry-forward provenance) + 06 (fetched/staged provenance) completed.
Inputs:
  - audit/build_provenance_carry_forward.parquet (458 rows)
  - audit/build_provenance_fetched.parquet        (39 rows)
  - delta manifest (497 rows) for cross-checks
Outputs:
  - mirror_v2_tree/build_manifest.parquet (497 per-file rows)
  - README-ready per-source table + validation figures (printed; captured into the report)
Checkpoint: MA-BUILD-07 (completeness, uniqueness, readability, per-source parity, byte totals)

Read-only over the built tree; the only write is build_manifest.parquet at the tree root.
"""

# --- Config ---
import polars as pl
import pyarrow.parquet as pq
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
AUDIT_DIR = PROJECT_DIR / "2026-08-06_mirror-v2-audit"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
MANIFEST_PATH = AUDIT_DIR / "2026-08-06_mirror-v2-delta-manifest.parquet"
CARRY_PROV_PATH = AUDIT_DIR / "build_provenance_carry_forward.parquet"
FETCHED_PROV_PATH = AUDIT_DIR / "build_provenance_fetched.parquet"
BUILD_MANIFEST_PATH = TREE_DIR / "build_manifest.parquet"

PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3

# --- Load provenance + delta manifest ---
carry = pl.read_parquet(CARRY_PROV_PATH)
fetched = pl.read_parquet(FETCHED_PROV_PATH)
manifest = pl.read_parquet(MANIFEST_PATH)
print(f"Loaded carry-forward provenance: {carry.height} rows")
print(f"Loaded fetched/staged provenance: {fetched.height} rows")
print(f"Loaded delta manifest: {manifest.height} rows")
assert carry.height == 458, f"STOP: carry provenance != 458 ({carry.height})"
assert fetched.height == 39, f"STOP: fetched provenance != 39 ({fetched.height})"

# --- Normalize to a common build-manifest schema and concat ---
# INTENT: unify the two provenance sources into one per-file manifest. REASONING: carry-forward
# rows have no source CSV metadata (they are prior parquet/xls objects), while fetched/staged rows
# carry Content-Length/Last-Modified/ETag; nulls make the union honest about which fields apply.
# ASSUMES: relative_path is the unique tree location key for every object.
carry_norm = carry.select(
    "canonical_object_key", "source", "object_kind", "relative_path", "filename",
    pl.lit("carried-forward").alias("provenance"),
    "classification", "source_url",
    pl.col("expected_size_bytes").alias("source_content_length"),
    pl.lit(None, dtype=pl.String).alias("source_last_modified"),
    pl.lit(None, dtype=pl.String).alias("source_etag"),
    "expected_oid", "oid_kind",
    "shipped_bytes", "shipped_sha256",
    pl.lit(None, dtype=pl.Int64).alias("row_count"),
    pl.lit(None, dtype=pl.Int64).alias("column_count"),
    "verification_method", "verification_result", "action", "observed_at_utc",
)
fetched_norm = fetched.select(
    "canonical_object_key", "source", "object_kind", "relative_path", "filename",
    "provenance", "classification", "source_url",
    pl.col("source_content_length").cast(pl.Int64),
    "source_last_modified", "source_etag",
    pl.lit(None, dtype=pl.String).alias("expected_oid"),
    pl.lit(None, dtype=pl.String).alias("oid_kind"),
    "shipped_bytes", "shipped_sha256",
    pl.col("row_count").cast(pl.Int64), pl.col("column_count").cast(pl.Int64),
    "verification_method", "verification_result", "action", "observed_at_utc",
)
build_manifest = pl.concat([carry_norm, fetched_norm], how="vertical")
print(f"\nUnified build manifest rows: {build_manifest.height} (target 497)")

# --- Validate: count, uniqueness, key parity vs delta manifest ---
assert build_manifest.height == 497, f"STOP: build manifest != 497 ({build_manifest.height})"
assert build_manifest["relative_path"].n_unique() == 497, "STOP: duplicate relative_path"
assert build_manifest["canonical_object_key"].n_unique() == 497, "STOP: duplicate canonical key"
mkeys = set(manifest["canonical_object_key"].to_list())
bkeys = set(build_manifest["canonical_object_key"].to_list())
assert mkeys == bkeys, (
    f"STOP: key mismatch vs delta manifest. "
    f"missing_from_build={sorted(mkeys - bkeys)[:5]}, extra_in_build={sorted(bkeys - mkeys)[:5]}"
)
assert (build_manifest["verification_result"] == "PASS").all(), "STOP: non-PASS row in build manifest"
print("[PASS] count=497, unique relative_path & keys, key parity with delta manifest, all PASS")

# --- Validate: every manifest row exists on disk exactly once ---
# INTENT: confirm the physical tree equals the manifest set with no stray/missing files.
# REASONING: an extra or absent file would corrupt the upload. ASSUMES: build_manifest.parquet
# is the only non-object file at the tree root and is excluded from the object comparison.
disk_files = [p for p in TREE_DIR.rglob("*") if p.is_file() and p.name != "build_manifest.parquet"]
disk_rel = sorted(str(p.relative_to(TREE_DIR)) for p in disk_files)
manifest_rel = sorted(build_manifest["relative_path"].to_list())
assert len(disk_rel) == 497, f"STOP: {len(disk_rel)} object files on disk, expected 497"
assert disk_rel == manifest_rel, (
    f"STOP: disk/manifest path set mismatch. "
    f"on_disk_only={sorted(set(disk_rel) - set(manifest_rel))[:5]}, "
    f"manifest_only={sorted(set(manifest_rel) - set(disk_rel))[:5]}"
)
print(f"[PASS] 497 object files on disk, exact 1:1 with manifest")

# --- Validate: every parquet opens with non-zero rows; byte-size on disk matches manifest ---
# INTENT: open each data parquet and confirm rows>0; confirm each file's on-disk size equals
# the recorded shipped_bytes. REASONING: a truncated/empty parquet would pass existence but
# fail analysis. ASSUMES: codebooks are .xls (non-parquet) and are size-checked only.
data_rows = build_manifest.filter(pl.col("relative_path").str.ends_with(".parquet"))
print(f"\nOpening {data_rows.height} parquet files to confirm non-zero rows ...")
zero_row = []
size_mismatch = []
for row in data_rows.iter_rows(named=True):
    fp = TREE_DIR / row["relative_path"]
    if fp.stat().st_size != row["shipped_bytes"]:
        size_mismatch.append(row["relative_path"])
    nrows = pq.ParquetFile(fp).metadata.num_rows
    if nrows <= 0:
        zero_row.append(row["relative_path"])
assert not zero_row, f"STOP: zero-row parquet(s): {zero_row[:5]}"
assert not size_mismatch, f"STOP: on-disk size != manifest shipped_bytes: {size_mismatch[:5]}"
codebook_rows = build_manifest.filter(~pl.col("relative_path").str.ends_with(".parquet"))
for row in codebook_rows.iter_rows(named=True):
    fp = TREE_DIR / row["relative_path"]
    assert fp.stat().st_size == row["shipped_bytes"], f"STOP: codebook size drift {row['relative_path']}"
print(f"[PASS] all {data_rows.height} parquet files non-empty; all {build_manifest.height} sizes match manifest")

# --- Spot-check schema on a sample of carried-forward parquet files ---
# INTENT: confirm carried-forward parquet objects read back with sensible column names/dtypes.
# REASONING: they are byte-verified copies of the old mirror, so this guards against a corrupt
# copy slipping the sha256 check (belt-and-suspenders). ASSUMES: >=1 parquet per sampled source.
carry_parq = carry.filter(pl.col("relative_path").str.ends_with(".parquet"))
sample = carry_parq.group_by("source").head(1).sort("source")
print("\n--- Schema spot-check (one carried-forward parquet per source) ---")
for row in sample.iter_rows(named=True):
    sch = pq.read_schema(TREE_DIR / row["relative_path"])
    assert len(sch.names) > 0, f"STOP: empty schema {row['relative_path']}"
    has_view = any(str(t).endswith("view") for t in sch.types)
    print(f"  {row['source']:9s} {row['filename']:48s} cols={len(sch.names):3d} "
          f"first3={sch.names[:3]} view_types={has_view}")

# --- Per-source README table: Source | Data Files | Codebooks | Year min-max ---
# INTENT: build the upload README's per-source summary. REASONING: reviewers need coverage at a
# glance. ASSUMES: year coverage derives from the delta manifest year_shard (filename-derived).
kind_counts = build_manifest.group_by("source").agg(
    (pl.col("object_kind") == "data").sum().alias("data_files"),
    (pl.col("object_kind") == "codebook").sum().alias("codebooks"),
    pl.len().alias("total"),
)
year_cov = manifest.group_by("source").agg(
    pl.col("year_shard").min().alias("year_min"),
    pl.col("year_shard").max().alias("year_max"),
)
per_source = kind_counts.join(year_cov, on="source", how="left").sort("source")
print("\n=== README PER-SOURCE TABLE ===")
print("| Source | Data Files | Codebooks | Year Range |")
print("|---|---:|---:|---|")
for r in per_source.iter_rows(named=True):
    if r["year_min"] is None:
        yr = "n/a"
    elif r["year_min"] == r["year_max"]:
        yr = str(int(r["year_min"]))
    else:
        yr = f"{int(r['year_min'])}-{int(r['year_max'])}"
    print(f"| {r['source']} | {r['data_files']} | {r['codebooks']} | {yr} |")

# --- Per-source parity check vs delta manifest ---
mani_counts = manifest.group_by("source").agg(pl.len().alias("m_total")).sort("source")
parity = per_source.join(mani_counts, on="source").with_columns(
    (pl.col("total") == pl.col("m_total")).alias("match")
)
assert parity["match"].all(), f"STOP: per-source count mismatch\n{parity.filter(~pl.col('match'))}"
print("\n[PASS] per-source counts match delta manifest for all sources")

# --- Provenance + kind splits, byte totals ---
print("\n=== PROVENANCE SPLIT ===")
print(build_manifest.group_by("provenance").agg(pl.len().alias("files"), pl.col("shipped_bytes").sum().alias("bytes")).sort("provenance"))
print("\n=== DATA vs CODEBOOK SPLIT ===")
split = build_manifest.group_by("object_kind").agg(pl.len().alias("files"), pl.col("shipped_bytes").sum().alias("bytes")).sort("object_kind")
print(split)
total_bytes = int(build_manifest["shipped_bytes"].sum())
data_files = int((build_manifest["object_kind"] == "data").sum())
codebook_files = int((build_manifest["object_kind"] == "codebook").sum())
print(f"\nTOTAL: {build_manifest.height} object files, {data_files} data + {codebook_files} codebooks, {total_bytes:,} bytes ({total_bytes/1e9:.2f} GB)")

# --- Save build manifest ---
build_manifest.write_parquet(BUILD_MANIFEST_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL)
print(f"\nSaved build manifest: {BUILD_MANIFEST_PATH}")
final_tree_count = len([p for p in TREE_DIR.rglob("*") if p.is_file()])
print(f"Final tree file count (incl. build_manifest.parquet): {final_tree_count} (expected 498)")
assert final_tree_count == 498, f"STOP: final tree count {final_tree_count} != 498"
print("CHECKPOINT MA-BUILD-07: PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-06 20:40:16
# Command: python3 /daaf/scripts/mirror_maintenance/07_validate-mirror-v2-tree.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Loaded carry-forward provenance: 458 rows
# Loaded fetched/staged provenance: 39 rows
# Loaded delta manifest: 497 rows
# 
# Unified build manifest rows: 497 (target 497)
# [PASS] count=497, unique relative_path & keys, key parity with delta manifest, all PASS
# [PASS] 497 object files on disk, exact 1:1 with manifest
# 
# Opening 406 parquet files to confirm non-zero rows ...
# [PASS] all 406 parquet files non-empty; all 497 sizes match manifest
# 
# --- Schema spot-check (one carried-forward parquet per source) ---
#   ccd       schools_ccd_enrollment_1986.parquet              cols=  9 first3=['year', 'ncessch', 'ncessch_num'] view_types=False
#   crdc      schools_crdc_algebra_2011.parquet                cols= 12 first3=['crdc_id', 'year', 'ncessch'] view_types=False
#   csafety   colleges_csafety_hate_crimes.parquet             cols= 13 first3=['year', 'unitid', 'inst_name'] view_types=True
#   eada      colleges_eada_inst_characteristics.parquet       cols=165 first3=['unitid', 'opeid', 'year'] view_types=False
#   edfacts   districts_edfacts_assessments_2009.parquet       cols= 23 first3=['leaid', 'leaid_num', 'year'] view_types=True
#   fsa       colleges_fsa_90_10_revenue_percentages.parquet   cols=  8 first3=['unitid', 'year', 'opeid'] view_types=True
#   ipeds     colleges_ipeds_admissions-requirements.parquet   cols= 48 first3=['unitid', 'year', 'fips'] view_types=False
#   meps      schools_meps.parquet                             cols= 11 first3=['year', 'fips', 'gleaid'] view_types=False
#   nacubo    colleges_nacubo_endow.parquet                    cols=  7 first3=['year', 'unitid', 'inst_name_nacubo'] view_types=True
#   nccs      colleges_nccs_all.parquet                        cols=161 first3=['year', 'unitid', 'ein'] view_types=True
#   nhgis     colleges_nhgis_geog_1990.parquet                 cols= 26 first3=['year', 'unitid', 'state_fips_geo'] view_types=False
#   pseo      colleges_pseo_2001.parquet                       cols= 18 first3=['unitid', 'fips', 'opeid'] view_types=False
#   scorecard colleges_scorecard_earnings.parquet              cols= 33 first3=['unitid', 'opeid', 'year'] view_types=True
# 
# === README PER-SOURCE TABLE ===
# | Source | Data Files | Codebooks | Year Range |
# |---|---:|---:|---|
# | ccd | 81 | 5 | 1986-2024 |
# | crdc | 66 | 24 | 2011-2022 |
# | csafety | 1 | 1 | n/a |
# | eada | 1 | 1 | n/a |
# | edfacts | 42 | 4 | 2009-2020 |
# | fsa | 5 | 5 | n/a |
# | ipeds | 171 | 32 | 1983-2024 |
# | meps | 1 | 1 | n/a |
# | nacubo | 1 | 1 | n/a |
# | nccs | 1 | 1 | n/a |
# | nhgis | 8 | 8 | 1990-2020 |
# | pseo | 21 | 1 | 2001-2021 |
# | saipe | 1 | 1 | n/a |
# | scorecard | 6 | 6 | n/a |
# 
# [PASS] per-source counts match delta manifest for all sources
# 
# === PROVENANCE SPLIT ===
# shape: (3, 3)
# ┌────────────────────┬───────┬────────────┐
# │ provenance         ┆ files ┆ bytes      │
# │ ---                ┆ ---   ┆ ---        │
# │ str                ┆ u32   ┆ i64        │
# ╞════════════════════╪═══════╪════════════╡
# │ carried-forward    ┆ 458   ┆ 3240546501 │
# │ fetched-2026-08-06 ┆ 31    ┆ 560253404  │
# │ staged-2026-07-21  ┆ 8     ┆ 31593547   │
# └────────────────────┴───────┴────────────┘
# 
# === DATA vs CODEBOOK SPLIT ===
# shape: (2, 3)
# ┌─────────────┬───────┬────────────┐
# │ object_kind ┆ files ┆ bytes      │
# │ ---         ┆ ---   ┆ ---        │
# │ str         ┆ u32   ┆ i64        │
# ╞═════════════╪═══════╪════════════╡
# │ codebook    ┆ 91    ┆ 2844160    │
# │ data        ┆ 406   ┆ 3829549292 │
# └─────────────┴───────┴────────────┘
# 
# TOTAL: 497 object files, 406 data + 91 codebooks, 3,832,393,452 bytes (3.83 GB)
# 
# Saved build manifest: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/mirror_v2_tree/build_manifest.parquet
# Final tree file count (incl. build_manifest.parquet): 498 (expected 498)
# CHECKPOINT MA-BUILD-07: PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
