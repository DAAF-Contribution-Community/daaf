#!/usr/bin/env python3
# =============================================================================
# 07_validate-mirror-v2-tree_a.py  (Mirror V2 corrective re-validation)
# =============================================================================
# INTENT: After 06_c rebuilt the 23 skipped_reverified data parquets through the
#   reference-schema path, (1) regenerate mirror_v2_tree/build_manifest.parquet with the
#   updated sha256/bytes/row_count/column_count/action for those 23 rows, (2) re-validate
#   the whole 497-object tree (1:1 with manifest, parquets open non-zero, on-disk sizes ==
#   manifest, sha256 == manifest), and (3) regenerate the build-validation report with a
#   CONTENT-BASED per-source year table (the QA BLOCKER: script 07 derived year ranges from
#   `year_shard` filenames, which are null for pooled/single-file families).
#
# YEAR METHOD (QA-corrected): per source, over every DATA parquet carrying a `year` column,
#   take min/max of the actual `year` column (cast Int64). This is the qa3 method and must
#   reproduce QA's authoritative table.
#
# Read-only over inputs except: overwrites build_manifest.parquet (regenerated) and writes a
# NEW-version validation report (_a.md; original preserved). No installs. No /tmp.
# =============================================================================

# --- Config ---
import polars as pl
import pyarrow.parquet as pq
import pyarrow as pa
import hashlib
import datetime
from pathlib import Path

BASE_DIR = Path("/daaf")
PROJECT_DIR = BASE_DIR / "research" / "2026-08-06_FrameworkDev_MirrorV2Update"
AUDIT_DIR = PROJECT_DIR / "2026-08-06_mirror-v2-audit"
TREE_DIR = PROJECT_DIR / "mirror_v2_tree"
MANIFEST_FP = TREE_DIR / "build_manifest.parquet"
REPORT_FP = AUDIT_DIR / "2026-08-06_mirror-v2-build-validation_a.md"
NOW_ISO = datetime.datetime.now(datetime.timezone.utc).isoformat()

# QA authoritative content-based year table (qa3) — the regenerated table MUST match this.
AUTHORITATIVE_YEARS = {
    "ccd": "1986-2024", "crdc": "2011-2022", "csafety": "2005-2021", "eada": "2002-2021",
    "edfacts": "2009-2020", "fsa": "1999-2021", "ipeds": "1979-2024", "meps": "2009-2022",
    "nacubo": "2012-2022", "nccs": "1993-2016", "nhgis": "1980-2023", "pseo": "2001-2021",
    "saipe": "1995-2024", "scorecard": "1996-2020",
}

# --- Load manifest + 06_c patch ---
manifest = pl.read_parquet(MANIFEST_FP)
patch = pl.read_parquet(AUDIT_DIR / "rebuilt_23_provenance.parquet")
print(f"Existing manifest: {manifest.shape}; patch rows: {patch.height}")
assert patch.height == 23, "expected 23 patch rows"

patch_map = {r["relative_path"]: r for r in patch.iter_rows(named=True)}

# --- Regenerate manifest: patch the 23 rebuilt rows in place ---
# INTENT: only the 23 rebuilt rows change (sha256, bytes, row/col counts, action, verification,
#   observed_at); provenance stays 'fetched-2026-08-06'; all other 474 rows untouched.
# REASONING: preserves the audited carry-forward / staged / fetched_converted rows exactly.
new_rows = []
patched = 0
for r in manifest.iter_rows(named=True):
    rel = r["relative_path"]
    if rel in patch_map:
        p = patch_map[rel]
        r = dict(r)
        r["shipped_bytes"] = p["shipped_bytes"]
        r["shipped_sha256"] = p["shipped_sha256"]
        r["row_count"] = p["row_count"]
        r["column_count"] = p["column_count"]
        r["action"] = p["action"]                       # rebuilt-reference-schema-2026-08-06
        r["verification_method"] = p["verification_method"]
        r["verification_result"] = p["verification_result"]
        r["observed_at_utc"] = p["observed_at_utc"]
        patched += 1
    new_rows.append(r)
assert patched == 23, f"patched {patched} rows, expected 23"
new_manifest = pl.DataFrame(new_rows, schema=manifest.schema)
print(f"Patched {patched} manifest rows; new action counts:")
print(new_manifest.group_by("provenance", "action").len().sort("provenance", "action"))

# --- VALIDATION 1: disk 1:1 with manifest (data + codebooks; exclude build_manifest itself) ---
disk_objs = sorted(str(p.relative_to(TREE_DIR)) for p in TREE_DIR.rglob("*")
                   if p.is_file() and p.name != "build_manifest.parquet")
man_objs = sorted(new_manifest["relative_path"].to_list())
disk_set, man_set = set(disk_objs), set(man_objs)
missing_on_disk = sorted(man_set - disk_set)
strays_on_disk = sorted(disk_set - man_set)
v1_pass = (len(disk_objs) == new_manifest.height) and not missing_on_disk and not strays_on_disk
print(f"\n[V1] disk objects={len(disk_objs)}, manifest rows={new_manifest.height}, "
      f"missing={len(missing_on_disk)}, strays={len(strays_on_disk)} -> {'PASS' if v1_pass else 'FAIL'}")
if missing_on_disk[:5]:
    print("  missing:", missing_on_disk[:5])
if strays_on_disk[:5]:
    print("  strays:", strays_on_disk[:5])

# --- VALIDATION 2: sizes, sha256, parquet-readability (all 497) ---
size_mism, sha_mism, empty_parq, unreadable = [], [], [], []
n_parq = 0
for r in new_manifest.iter_rows(named=True):
    rel = r["relative_path"]
    fp = TREE_DIR / rel
    # on-disk size
    dbytes = fp.stat().st_size
    if dbytes != r["shipped_bytes"]:
        size_mism.append((rel, r["shipped_bytes"], dbytes))
    # sha256 (chunked)
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for blk in iter(lambda: fh.read(8 << 20), b""):
            h.update(blk)
    if h.hexdigest() != r["shipped_sha256"]:
        sha_mism.append(rel)
    # parquet readability + non-zero rows
    if rel.endswith(".parquet"):
        n_parq += 1
        try:
            nr = pq.read_metadata(fp).num_rows
            if nr <= 0:
                empty_parq.append(rel)
        except Exception as e:
            unreadable.append((rel, repr(e)))
v2_pass = not size_mism and not sha_mism and not empty_parq and not unreadable
print(f"[V2] parquets={n_parq}, size_mismatch={len(size_mism)}, sha_mismatch={len(sha_mism)}, "
      f"empty={len(empty_parq)}, unreadable={len(unreadable)} -> {'PASS' if v2_pass else 'FAIL'}")
for m in size_mism[:5]:
    print("  size:", m)
for m in sha_mism[:5]:
    print("  sha:", m)

# --- VALIDATION 3: rebuilt 23 carry no large_string/view (method-uniformity check) ---
bad_types = []
for rel in patch_map:
    sch = pq.read_schema(TREE_DIR / rel)
    if any(pa.types.is_large_string(t) or pa.types.is_large_binary(t)
           or pa.types.is_string_view(t) or pa.types.is_binary_view(t) for t in sch.types):
        bad_types.append(rel)
v3_pass = not bad_types
print(f"[V3] rebuilt-23 large/view type carriers={len(bad_types)} -> {'PASS' if v3_pass else 'FAIL'}")

# --- VALIDATION 4: content-based per-source year table (QA BLOCKER fix) ---
year_rows = []
for source in sorted(new_manifest["source"].unique().to_list()):
    rows = new_manifest.filter(
        (pl.col("source") == source) & (pl.col("object_kind") == "data")
        & pl.col("relative_path").str.ends_with(".parquet"))
    cmins, cmaxs, n_year = [], [], 0
    for r in rows.iter_rows(named=True):
        fp = TREE_DIR / r["relative_path"]
        if "year" not in pl.scan_parquet(fp).collect_schema().names():
            continue
        n_year += 1
        st = pl.scan_parquet(fp).select(
            pl.col("year").cast(pl.Int64, strict=False).min().alias("mn"),
            pl.col("year").cast(pl.Int64, strict=False).max().alias("mx")).collect().to_dicts()[0]
        if st["mn"] is not None:
            cmins.append(st["mn"])
        if st["mx"] is not None:
            cmaxs.append(st["mx"])
    if n_year == 0:
        rng = "n/a"
    else:
        lo, hi = min(cmins), max(cmaxs)
        rng = str(lo) if lo == hi else f"{lo}-{hi}"
    year_rows.append({"source": source, "content_year_range": rng, "files_with_year": n_year,
                      "authoritative": AUTHORITATIVE_YEARS.get(source, "?"),
                      "match": rng == AUTHORITATIVE_YEARS.get(source)})
year_df = pl.from_dicts(year_rows).sort("source")
print("\n[V4] content-based year table:")
print(year_df)
year_mismatches = year_df.filter(~pl.col("match"))
v4_pass = year_mismatches.height == 0
print(f"[V4] year table matches QA authoritative -> {'PASS' if v4_pass else 'FAIL'} "
      f"({year_mismatches.height} mismatches)")
if year_mismatches.height:
    print(year_mismatches)

# --- Gate: only regenerate manifest + report if ALL validations pass ---
all_pass = v1_pass and v2_pass and v3_pass and v4_pass
assert all_pass, f"validation failed: V1={v1_pass} V2={v2_pass} V3={v3_pass} V4={v4_pass}"

# --- Regenerate build_manifest.parquet (atomic) ---
tmp = MANIFEST_FP.with_suffix(".parquet.tmp")
new_manifest.write_parquet(tmp)
tmp.replace(MANIFEST_FP)
print(f"\nRegenerated {MANIFEST_FP} ({new_manifest.height} rows)")

# --- Per-source data/codebook counts for the report ---
counts = (new_manifest.group_by("source", "object_kind").len()
          .pivot(values="len", index="source", on="object_kind")
          .fill_null(0).sort("source"))
data_total = new_manifest.filter(pl.col("object_kind") == "data").height
cb_total = new_manifest.filter(pl.col("object_kind") == "codebook").height
tree_bytes = int(new_manifest["shipped_bytes"].sum())

# --- Write validation report (NEW version) ---
lines = []
lines.append("# Mirror V2 Build Validation (corrective re-validation, _a)")
lines.append("")
lines.append(f"_Generated: {NOW_ISO}_  ")
lines.append("Supersedes `2026-08-06_mirror-v2-build-validation.md` after the QA-driven "
             "corrective rebuild (06_c) of the 23 skipped_reverified data parquets and the "
             "content-based year-range fix (07_a).")
lines.append("")
lines.append("## Corrective actions applied")
lines.append("- **23 files rebuilt through the reference-schema path** (06_c): re-converted "
             "from source CSV via all-String read -> data-preserving cast to each file's own "
             "old-vintage (or carried-forward family-sibling) normalized dtypes. Provenance "
             "`fetched-2026-08-06`; action `rebuilt-reference-schema-2026-08-06`.")
lines.append("- **Year table regenerated content-based** (07_a): min/max of the actual `year` "
             "column per source, replacing the filename (`year_shard`)-derived ranges.")
lines.append("")
lines.append("## Tree validation")
lines.append(f"- **V1 disk 1:1 with manifest:** {'PASS' if v1_pass else 'FAIL'} — "
             f"{len(disk_objs)} objects == {new_manifest.height} manifest rows "
             f"(0 missing, 0 strays), +1 build_manifest.parquet.")
lines.append(f"- **V2 size + sha256 + parquet-readable:** {'PASS' if v2_pass else 'FAIL'} — "
             f"{new_manifest.height}/{new_manifest.height} on-disk bytes == manifest, "
             f"sha256 == manifest; {n_parq}/{n_parq} parquets open with rows>0.")
lines.append(f"- **V3 rebuilt-23 arrow types:** {'PASS' if v3_pass else 'FAIL'} — 0 of 23 carry "
             "large_string/large_binary/string_view/binary_view (regular `string` only).")
lines.append(f"- **V4 content-based year table:** {'PASS' if v4_pass else 'FAIL'} — reproduces "
             "the QA (qa3) authoritative table exactly.")
lines.append("")
lines.append(f"Tree total: **{new_manifest.height} objects** "
             f"({data_total} data + {cb_total} codebooks) + build_manifest.parquet; "
             f"{tree_bytes:,} bytes.")
lines.append("")
lines.append("## Content-based per-source year ranges (CORRECTED)")
lines.append("")
lines.append("| Source | Year range (content) | Files with `year` |")
lines.append("|---|---|---|")
for r in year_df.iter_rows(named=True):
    lines.append(f"| {r['source']} | {r['content_year_range']} | {r['files_with_year']} |")
lines.append("")
lines.append("_Footnote: nhgis `year` is the education-data linkage year, not the census vintage._")
lines.append("")
lines.append("## Per-source object counts")
lines.append("")
lines.append("| Source | data | codebook |")
lines.append("|---|---|---|")
for r in counts.iter_rows(named=True):
    lines.append(f"| {r['source']} | {r.get('data', 0)} | {r.get('codebook', 0)} |")
lines.append("")
lines.append("## Manifest action composition (post-rebuild)")
lines.append("")
comp = new_manifest.group_by("provenance", "action").len().sort("provenance", "action")
lines.append("| provenance | action | files |")
lines.append("|---|---|---|")
for r in comp.iter_rows(named=True):
    lines.append(f"| {r['provenance']} | {r['action']} | {r['len']} |")
lines.append("")

REPORT_FP.write_text("\n".join(lines))
print(f"Wrote validation report: {REPORT_FP}")
print("\nMA-BUILD-07A PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-06 21:13:21
# Command: python3 /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/scripts/mirror_maintenance/07_validate-mirror-v2-tree_a.py
# Duration: 6s
# Exit code: 0
#
# --- STDOUT ---
# Existing manifest: (497, 21); patch rows: 23
# Patched 23 manifest rows; new action counts:
# shape: (5, 3)
# ┌────────────────────┬─────────────────────────────────┬─────┐
# │ provenance         ┆ action                          ┆ len │
# │ ---                ┆ ---                             ┆ --- │
# │ str                ┆ str                             ┆ u32 │
# ╞════════════════════╪═════════════════════════════════╪═════╡
# │ carried-forward    ┆ downloaded                      ┆ 458 │
# │ fetched-2026-08-06 ┆ fetched_converted               ┆ 5   │
# │ fetched-2026-08-06 ┆ rebuilt-reference-schema-2026-… ┆ 23  │
# │ fetched-2026-08-06 ┆ skipped_reverified              ┆ 3   │
# │ staged-2026-07-21  ┆ copied_staged                   ┆ 8   │
# └────────────────────┴─────────────────────────────────┴─────┘
# 
# [V1] disk objects=497, manifest rows=497, missing=0, strays=0 -> PASS
# [V2] parquets=406, size_mismatch=0, sha_mismatch=0, empty=0, unreadable=0 -> PASS
# [V3] rebuilt-23 large/view type carriers=0 -> PASS
# 
# [V4] content-based year table:
# shape: (14, 5)
# ┌───────────┬────────────────────┬─────────────────┬───────────────┬───────┐
# │ source    ┆ content_year_range ┆ files_with_year ┆ authoritative ┆ match │
# │ ---       ┆ ---                ┆ ---             ┆ ---           ┆ ---   │
# │ str       ┆ str                ┆ i64             ┆ str           ┆ bool  │
# ╞═══════════╪════════════════════╪═════════════════╪═══════════════╪═══════╡
# │ ccd       ┆ 1986-2024          ┆ 81              ┆ 1986-2024     ┆ true  │
# │ crdc      ┆ 2011-2022          ┆ 66              ┆ 2011-2022     ┆ true  │
# │ csafety   ┆ 2005-2021          ┆ 1               ┆ 2005-2021     ┆ true  │
# │ eada      ┆ 2002-2021          ┆ 1               ┆ 2002-2021     ┆ true  │
# │ edfacts   ┆ 2009-2020          ┆ 42              ┆ 2009-2020     ┆ true  │
# │ …         ┆ …                  ┆ …               ┆ …             ┆ …     │
# │ nccs      ┆ 1993-2016          ┆ 1               ┆ 1993-2016     ┆ true  │
# │ nhgis     ┆ 1980-2023          ┆ 8               ┆ 1980-2023     ┆ true  │
# │ pseo      ┆ 2001-2021          ┆ 21              ┆ 2001-2021     ┆ true  │
# │ saipe     ┆ 1995-2024          ┆ 1               ┆ 1995-2024     ┆ true  │
# │ scorecard ┆ 1996-2020          ┆ 6               ┆ 1996-2020     ┆ true  │
# └───────────┴────────────────────┴─────────────────┴───────────────┴───────┘
# [V4] year table matches QA authoritative -> PASS (0 mismatches)
# 
# Regenerated /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/mirror_v2_tree/build_manifest.parquet (497 rows)
# Wrote validation report: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/2026-08-06_mirror-v2-build-validation_a.md
# 
# MA-BUILD-07A PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
