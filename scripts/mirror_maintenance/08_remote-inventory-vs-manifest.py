# --- Config ---
# INTENT: Definitively prove the new HF mirror upload is byte-faithful to the local
#   build tree by comparing the COMPLETE remote file tree (at the pinned revision)
#   against the local build_manifest.parquet — all files, not a sample.
# REASONING: The manifest carries per-file shipped_sha256 + shipped_bytes for all 497
#   data objects. HF's LFS tree entries expose lfs.oid (= sha256) and lfs.size, so an
#   exact object-by-object match across the full set is the strongest faithfulness proof.
# ASSUMES: huggingface_hub is NOT installed -> plain HTTPS via urllib. Tree API paginates
#   via RFC-5988 Link headers. LFS entries carry lfs.oid/lfs.size; small non-LFS files
#   (README.md, possibly build_manifest.parquet) carry only a git blob oid.
import json
import time
import urllib.request
import urllib.error
import polars as pl

BASE = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update"
MANIFEST = f"{BASE}/mirror_v2_tree/build_manifest.parquet"
REPO = "brhkim/education_data_portal_mirror_2026q3"
REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
TREE_URL = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}?recursive=true"

EXPECTED_TOTAL_FILES = 499          # 497 data objects + build_manifest.parquet + README.md
EXPECTED_DATA_OBJECTS = 497
EXPECTED_TOTAL_BYTES = 3_837_811_864
NON_MANIFEST_FILES = {"build_manifest.parquet", "README.md"}

# --- Load: local manifest (ground truth) ---
man = pl.read_parquet(MANIFEST)
print(f"Loaded manifest: {man.shape[0]} rows x {man.shape[1]} cols")
assert man.shape[0] == EXPECTED_DATA_OBJECTS, f"manifest rows {man.shape[0]} != {EXPECTED_DATA_OBJECTS}"
# INTENT: canonical local index keyed by tree path (= relative_path in the flat layout)
man_idx = {
    r["relative_path"]: {
        "sha256": r["shipped_sha256"],
        "bytes": r["shipped_bytes"],
        "expected_oid": r["expected_oid"],
        "oid_kind": r["oid_kind"],
    }
    for r in man.iter_rows(named=True)
}
print(f"Manifest sum(shipped_bytes) = {man['shipped_bytes'].sum():,}")

# --- Fetch: full remote tree, paginated via Link rel=next, with retries+backoff ---
# REASONING: follow rel="next" until absent so we capture every entry (no page cap).
entries = []
next_url = TREE_URL
page = 0
while next_url is not None:
    page += 1
    last_err = None
    resp_headers = None
    body = None
    for attempt in range(1, 4):  # up to 3 tries per page
        try:
            req = urllib.request.Request(next_url, headers={"User-Agent": "daaf-mirror-validate/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
                resp_headers = resp.headers
            break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  page {page} attempt {attempt} failed: {e!r}; backoff {wait}s")
            time.sleep(wait)
    assert body is not None, f"page {page} failed after retries: {last_err!r}"
    chunk = json.loads(body.decode("utf-8"))
    entries.extend(chunk)
    # INTENT: parse RFC-5988 Link header for the rel="next" cursor
    link = resp_headers.get("Link") if resp_headers else None
    next_url = None
    if link:
        for part in link.split(","):
            segs = part.split(";")
            if len(segs) >= 2 and 'rel="next"' in segs[1]:
                next_url = segs[0].strip().strip("<>")
    print(f"  page {page}: +{len(chunk)} entries (running total {len(entries)}); next={'yes' if next_url else 'no'}")

print(f"Fetched {len(entries)} raw tree entries across {page} page(s)")

# --- Transform: keep only files (drop any directory entries) ---
files = [e for e in entries if e.get("type") == "file"]
print(f"File entries: {len(files)}")

# INTENT: build a remote index keyed by path; capture lfs presence, oid, size.
remote_idx = {}
for e in files:
    path = e["path"]
    lfs = e.get("lfs")
    remote_idx[path] = {
        "is_lfs": lfs is not None,
        "lfs_oid": (lfs or {}).get("oid"),
        "lfs_size": (lfs or {}).get("size"),
        "git_oid": e.get("oid"),
        "size": e.get("size"),
    }

# --- Validate 1: file count + set membership ---
print("\n=== V1: FILE COUNT & MEMBERSHIP ===")
print(f"Remote file count: {len(remote_idx)} (expected {EXPECTED_TOTAL_FILES})")
remote_paths = set(remote_idx)
manifest_paths = set(man_idx)
# The two non-manifest files must be present remotely but absent from the manifest.
data_remote_paths = remote_paths - NON_MANIFEST_FILES
missing_vs_manifest = manifest_paths - data_remote_paths   # in manifest, not on remote
strays = data_remote_paths - manifest_paths                # on remote, not in manifest
non_manifest_present = NON_MANIFEST_FILES & remote_paths
print(f"Data objects remote (excl. 2 non-manifest): {len(data_remote_paths)} (expected {EXPECTED_DATA_OBJECTS})")
print(f"Non-manifest files present remotely: {sorted(non_manifest_present)}")
print(f"Missing (in manifest, absent remote): {len(missing_vs_manifest)} -> {sorted(missing_vs_manifest)[:20]}")
print(f"Strays (remote, not in manifest, excl. 2 non-manifest): {len(strays)} -> {sorted(strays)[:20]}")

# --- Validate 2: per-object LFS oid/size vs manifest for every data object ---
print("\n=== V2: PER-OBJECT HASH & SIZE (all data objects) ===")
sha_match = 0
size_match = 0
lfs_count = 0
nonlfs_data = []          # data objects that were NOT LFS (unexpected)
sha_mismatches = []
size_mismatches = []
for path, mrec in man_idx.items():
    r = remote_idx.get(path)
    if r is None:
        continue  # already counted as missing above
    if r["is_lfs"]:
        lfs_count += 1
        if r["lfs_oid"] == mrec["sha256"]:
            sha_match += 1
        else:
            sha_mismatches.append((path, mrec["sha256"], r["lfs_oid"]))
        if r["lfs_size"] == mrec["bytes"]:
            size_match += 1
        else:
            size_mismatches.append((path, mrec["bytes"], r["lfs_size"]))
    else:
        # INTENT: fallback for any non-LFS data object -> compare git blob oid vs expected_oid
        nonlfs_data.append(path)
        if r["git_oid"] == mrec["expected_oid"]:
            sha_match += 1  # matched via git blob oid path
        else:
            sha_mismatches.append((path, mrec["expected_oid"], r["git_oid"]))
        if r["size"] == mrec["bytes"]:
            size_match += 1
        else:
            size_mismatches.append((path, mrec["bytes"], r["size"]))

print(f"Data objects compared: {len(man_idx)}")
print(f"  LFS entries: {lfs_count} ; non-LFS data objects: {len(nonlfs_data)} -> {nonlfs_data[:10]}")
print(f"  sha256/oid matches: {sha_match} / {len(man_idx)}")
print(f"  byte-size matches:  {size_match} / {len(man_idx)}")
print(f"  sha mismatches: {len(sha_mismatches)}")
for mm in sha_mismatches[:20]:
    print(f"    MISMATCH sha {mm[0]}: manifest={mm[1]} remote={mm[2]}")
print(f"  size mismatches: {len(size_mismatches)}")
for mm in size_mismatches[:20]:
    print(f"    MISMATCH size {mm[0]}: manifest={mm[1]} remote={mm[2]}")

# --- Validate 3: the two non-manifest files, handled explicitly ---
print("\n=== V3: NON-MANIFEST FILES (build_manifest.parquet, README.md) ===")
for f in sorted(NON_MANIFEST_FILES):
    r = remote_idx.get(f)
    if r is None:
        print(f"  {f}: ABSENT remotely (UNEXPECTED)")
    else:
        kind = "LFS" if r["is_lfs"] else "non-LFS(git-blob)"
        oid = r["lfs_oid"] if r["is_lfs"] else r["git_oid"]
        size = r["lfs_size"] if r["is_lfs"] else r["size"]
        print(f"  {f}: present, {kind}, oid={oid}, size={size}")

# --- Validate 4: total remote bytes ---
print("\n=== V4: TOTAL BYTES ===")
# INTENT: sum reported sizes across ALL remote files (LFS size or git size).
remote_total_bytes = sum(
    (r["lfs_size"] if r["is_lfs"] else r["size"]) or 0 for r in remote_idx.values()
)
data_total_bytes = sum(
    (r["lfs_size"] if r["is_lfs"] else r["size"]) or 0
    for p, r in remote_idx.items() if p not in NON_MANIFEST_FILES
)
print(f"Remote total bytes (all {len(remote_idx)} files): {remote_total_bytes:,}")
print(f"Remote data-object bytes (excl. 2 non-manifest): {data_total_bytes:,} (manifest sum: {man['shipped_bytes'].sum():,})")
print(f"Expected local tree total (499 files): {EXPECTED_TOTAL_BYTES:,}")

# --- Validate: hard assertions (definitive proof gates) ---
print("\n=== VERDICT ===")
checks = {
    "remote_file_count==499": len(remote_idx) == EXPECTED_TOTAL_FILES,
    "data_objects==497": len(data_remote_paths) == EXPECTED_DATA_OBJECTS,
    "zero_missing": len(missing_vs_manifest) == 0,
    "zero_strays": len(strays) == 0,
    "both_non_manifest_present": non_manifest_present == NON_MANIFEST_FILES,
    "sha_match==497": sha_match == EXPECTED_DATA_OBJECTS,
    "size_match==497": size_match == EXPECTED_DATA_OBJECTS,
    "data_bytes==manifest_sum": data_total_bytes == man["shipped_bytes"].sum(),
    "total_bytes==3837811864": remote_total_bytes == EXPECTED_TOTAL_BYTES,
}
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
all_pass = all(checks.values())
print(f"\nSCRIPT 08 OVERALL: {'PASS' if all_pass else 'FAIL'}")
assert all_pass, f"Faithfulness proof FAILED: {[k for k,v in checks.items() if not v]}"
print("Upload is byte-faithful to the local build manifest (all 497 data objects).")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-07 13:07:31
# Command: python3 /daaf/scripts/mirror_maintenance/08_remote-inventory-vs-manifest.py
# Duration: 1s
# Exit code: 1
#
# --- STDOUT ---
# Loaded manifest: 497 rows x 21 cols
# Manifest sum(shipped_bytes) = 3,837,811,864
#   page 1: +514 entries (running total 514); next=no
# Fetched 514 raw tree entries across 1 page(s)
# File entries: 500
# 
# === V1: FILE COUNT & MEMBERSHIP ===
# Remote file count: 500 (expected 499)
# Data objects remote (excl. 2 non-manifest): 498 (expected 497)
# Non-manifest files present remotely: ['README.md', 'build_manifest.parquet']
# Missing (in manifest, absent remote): 0 -> []
# Strays (remote, not in manifest, excl. 2 non-manifest): 1 -> ['.gitattributes']
# 
# === V2: PER-OBJECT HASH & SIZE (all data objects) ===
# Data objects compared: 497
#   LFS entries: 406 ; non-LFS data objects: 91 -> ['ccd/codebook_districts_ccd_directory.xls', 'ccd/codebook_districts_ccd_enrollment.xls', 'ccd/codebook_districts_ccd_finance.xls', 'ccd/codebook_schools_ccd_directory.xls', 'ccd/codebook_schools_ccd_enrollment.xls', 'crdc/codebook_schools_crdc_algebra-1.xls', 'crdc/codebook_schools_crdc_ap-exams.xls', 'crdc/codebook_schools_crdc_ap-ib-enrollment.xls', 'crdc/codebook_schools_crdc_chronic-absenteeism.xls', 'crdc/codebook_schools_crdc_covid_indicators.xls']
#   sha256/oid matches: 494 / 497
#   byte-size matches:  497 / 497
#   sha mismatches: 3
#     MISMATCH sha ipeds/codebook_colleges_ipeds_completers.xls: manifest=None remote=67577d3e4fc6a7766fa80417ff3f24de8e1bf13a
#     MISMATCH sha ipeds/codebook_colleges_ipeds_directory.xls: manifest=None remote=6ce02a1f5aa5f51f62a8bb21f94bea66007b13a1
#     MISMATCH sha ipeds/codebook_colleges_ipeds_fall-retention.xls: manifest=None remote=3150e354939fa9bfd2e237bdf4aca7de3b9a1090
#   size mismatches: 0
# 
# === V3: NON-MANIFEST FILES (build_manifest.parquet, README.md) ===
#   README.md: present, non-LFS(git-blob), oid=ba30c43e3f6653d99857bcf91a45e0224005c21c, size=10709
#   build_manifest.parquet: present, LFS, oid=729d009704fcfe6d53f2aac37de113537de1378e4d1e3549b392d788a9a4f264, size=62342
# 
# === V4: TOTAL BYTES ===
# Remote total bytes (all 500 files): 3,837,887,419
# Remote data-object bytes (excl. 2 non-manifest): 3,837,814,368 (manifest sum: 3,837,811,864)
# Expected local tree total (499 files): 3,837,811,864
# 
# === VERDICT ===
#   [FAIL] remote_file_count==499
#   [FAIL] data_objects==497
#   [PASS] zero_missing
#   [FAIL] zero_strays
#   [PASS] both_non_manifest_present
#   [FAIL] sha_match==497
#   [PASS] size_match==497
#   [FAIL] data_bytes==manifest_sum
#   [FAIL] total_bytes==3837811864
# 
# SCRIPT 08 OVERALL: FAIL
# Traceback (most recent call last):
#   File "/daaf/scripts/mirror_maintenance/08_remote-inventory-vs-manifest.py", line 201, in <module>
#     assert all_pass, f"Faithfulness proof FAILED: {[k for k,v in checks.items() if not v]}"
#            ^^^^^^^^
# AssertionError: Faithfulness proof FAILED: ['remote_file_count==499', 'data_objects==497', 'zero_strays', 'sha_match==497', 'data_bytes==manifest_sum', 'total_bytes==3837811864']
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
