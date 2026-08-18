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
import hashlib
import urllib.request
import urllib.error
import polars as pl

BASE = "/daaf/research/2026-08-06_FrameworkDev_MirrorV2Update"
MANIFEST = f"{BASE}/mirror_v2_tree/build_manifest.parquet"
REPO = "brhkim/education_data_portal_mirror_2026q3"
REVISION = "0ad00ce0e232c96b0642459e4e7326607a8d26aa"
TREE_URL = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}?recursive=true"
RESOLVE = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}"

# INTENT: expected file inventory at the pinned revision.
# REASONING: 497 data objects + build_manifest.parquet + README.md = 499, PLUS the
#   standard git/LFS control file `.gitattributes` that HuggingFace auto-creates on every
#   repo. .gitattributes is infrastructure (LFS tracking rules), NOT a data stray, so it is
#   whitelisted as a CONTROL file and excluded from data-object accounting.
EXPECTED_DATA_OBJECTS = 497
EXPECTED_DATA_BYTES = 3_837_811_864          # == manifest sum(shipped_bytes) over 497 objects
NON_MANIFEST_FILES = {"build_manifest.parquet", "README.md"}
CONTROL_FILES = {".gitattributes"}
EXPECTED_TOTAL_FILES = EXPECTED_DATA_OBJECTS + len(NON_MANIFEST_FILES) + len(CONTROL_FILES)  # 500

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
# INTENT: data objects = all remote files minus the 2 non-manifest files and the
#   whitelisted control file(s). Anything else remaining that is not in the manifest is a stray.
data_remote_paths = remote_paths - NON_MANIFEST_FILES - CONTROL_FILES
missing_vs_manifest = manifest_paths - data_remote_paths   # in manifest, not on remote
strays = data_remote_paths - manifest_paths                # on remote, not in manifest (true strays)
non_manifest_present = NON_MANIFEST_FILES & remote_paths
control_present = CONTROL_FILES & remote_paths
control_strays = (remote_paths - manifest_paths - NON_MANIFEST_FILES - CONTROL_FILES)
print(f"Data objects remote (excl. non-manifest + control): {len(data_remote_paths)} (expected {EXPECTED_DATA_OBJECTS})")
print(f"Non-manifest files present remotely: {sorted(non_manifest_present)}")
print(f"Control files present remotely (whitelisted): {sorted(control_present)}")
print(f"Missing (in manifest, absent remote): {len(missing_vs_manifest)} -> {sorted(missing_vs_manifest)[:20]}")
print(f"Strays (remote, not manifest/non-manifest/control): {len(control_strays)} -> {sorted(control_strays)[:20]}")

# --- Validate 2: per-object LFS oid/size vs manifest for every data object ---
print("\n=== V2: PER-OBJECT HASH & SIZE (all data objects) ===")
sha_match = 0
size_match = 0
lfs_count = 0
nonlfs_data = []          # data objects that were NOT LFS (the 91 xls codebooks)
sha_mismatches = []
size_mismatches = []
downloaded_sha_checks = []  # (path, downloaded_sha256, manifest_sha256, dl_bytes, manifest_bytes)
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
        # INTENT: non-LFS data object (git blob). Primary check: remote git blob oid ==
        #   manifest expected_oid (git_blob_sha1). If the manifest has no expected_oid
        #   (null), download the object bytes and verify content sha256 == shipped_sha256.
        # REASONING: git blob sha1 and content sha256 are different algorithms and cannot be
        #   compared directly, so the null-oid rows need a real content download to prove
        #   faithfulness rather than being skipped.
        nonlfs_data.append(path)
        if mrec["expected_oid"] is not None:
            if r["git_oid"] == mrec["expected_oid"]:
                sha_match += 1  # matched via git blob oid
            else:
                sha_mismatches.append((path, mrec["expected_oid"], r["git_oid"]))
        else:
            # INTENT: download bytes from the pinned resolve URL, compute sha256.
            url = f"{RESOLVE}/{path}"
            data = None
            last_err = None
            for attempt in range(1, 4):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "daaf-mirror-validate/1.0"})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = resp.read()
                    break
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                    last_err = e
                    time.sleep(2 ** attempt)
            assert data is not None, f"download failed for {path}: {last_err!r}"
            dl_sha = hashlib.sha256(data).hexdigest()
            downloaded_sha_checks.append((path, dl_sha, mrec["sha256"], len(data), mrec["bytes"]))
            if dl_sha == mrec["sha256"]:
                sha_match += 1  # matched via downloaded content sha256
            else:
                sha_mismatches.append((path, mrec["sha256"], dl_sha))
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
print(f"  content-downloaded sha256 checks (null-expected_oid codebooks): {len(downloaded_sha_checks)}")
for p, dl, mf, db, mb in downloaded_sha_checks:
    ok = "OK" if (dl == mf and db == mb) else "MISMATCH"
    print(f"    [{ok}] {p}: dl_sha={dl} manifest_sha={mf} dl_bytes={db} manifest_bytes={mb}")

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
# INTENT: data-object byte total excludes the 2 non-manifest files AND control files.
data_total_bytes = sum(
    (r["lfs_size"] if r["is_lfs"] else r["size"]) or 0
    for p, r in remote_idx.items() if p not in NON_MANIFEST_FILES and p not in CONTROL_FILES
)
manifest_sum = man["shipped_bytes"].sum()
print(f"Remote total bytes (all {len(remote_idx)} files incl. control): {remote_total_bytes:,}")
print(f"Remote data-object bytes (excl. non-manifest + control): {data_total_bytes:,} (manifest sum: {manifest_sum:,})")
print(f"Expected data-object bytes: {EXPECTED_DATA_BYTES:,}")

# --- Validate: hard assertions (definitive proof gates) ---
print("\n=== VERDICT ===")
checks = {
    "remote_file_count==500(499+gitattributes)": len(remote_idx) == EXPECTED_TOTAL_FILES,
    "data_objects==497": len(data_remote_paths) == EXPECTED_DATA_OBJECTS,
    "zero_missing": len(missing_vs_manifest) == 0,
    "zero_true_strays": len(control_strays) == 0,
    "both_non_manifest_present": non_manifest_present == NON_MANIFEST_FILES,
    "gitattributes_present": control_present == CONTROL_FILES,
    "sha_match==497": sha_match == EXPECTED_DATA_OBJECTS,
    "size_match==497": size_match == EXPECTED_DATA_OBJECTS,
    "data_bytes==manifest_sum": data_total_bytes == manifest_sum,
    "data_bytes==3837811864": data_total_bytes == EXPECTED_DATA_BYTES,
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
# Executed: 2026-08-07 13:09:36
# Command: python3 /daaf/scripts/mirror_maintenance/08_remote-inventory-vs-manifest_a.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# Loaded manifest: 497 rows x 21 cols
# Manifest sum(shipped_bytes) = 3,837,811,864
#   page 1: +514 entries (running total 514); next=no
# Fetched 514 raw tree entries across 1 page(s)
# File entries: 500
# 
# === V1: FILE COUNT & MEMBERSHIP ===
# Remote file count: 500 (expected 500)
# Data objects remote (excl. non-manifest + control): 497 (expected 497)
# Non-manifest files present remotely: ['README.md', 'build_manifest.parquet']
# Control files present remotely (whitelisted): ['.gitattributes']
# Missing (in manifest, absent remote): 0 -> []
# Strays (remote, not manifest/non-manifest/control): 0 -> []
# 
# === V2: PER-OBJECT HASH & SIZE (all data objects) ===
# Data objects compared: 497
#   LFS entries: 406 ; non-LFS data objects: 91 -> ['ccd/codebook_districts_ccd_directory.xls', 'ccd/codebook_districts_ccd_enrollment.xls', 'ccd/codebook_districts_ccd_finance.xls', 'ccd/codebook_schools_ccd_directory.xls', 'ccd/codebook_schools_ccd_enrollment.xls', 'crdc/codebook_schools_crdc_algebra-1.xls', 'crdc/codebook_schools_crdc_ap-exams.xls', 'crdc/codebook_schools_crdc_ap-ib-enrollment.xls', 'crdc/codebook_schools_crdc_chronic-absenteeism.xls', 'crdc/codebook_schools_crdc_covid_indicators.xls']
#   sha256/oid matches: 497 / 497
#   byte-size matches:  497 / 497
#   sha mismatches: 0
#   size mismatches: 0
#   content-downloaded sha256 checks (null-expected_oid codebooks): 3
#     [OK] ipeds/codebook_colleges_ipeds_completers.xls: dl_sha=438a61048c4ade8b3bd336ed68bc1907b27dcc245d6dd73c9b93de79a2bb0cf2 manifest_sha=438a61048c4ade8b3bd336ed68bc1907b27dcc245d6dd73c9b93de79a2bb0cf2 dl_bytes=35840 manifest_bytes=35840
#     [OK] ipeds/codebook_colleges_ipeds_directory.xls: dl_sha=a51b5fab574b9fe349647d8d0d33fbe3c715206e629bf932e65ab64574c8f878 manifest_sha=a51b5fab574b9fe349647d8d0d33fbe3c715206e629bf932e65ab64574c8f878 dl_bytes=97792 manifest_bytes=97792
#     [OK] ipeds/codebook_colleges_ipeds_fall-retention.xls: dl_sha=7748dce8c40057acab4ca3f92f0f5f1e9f731236e7929b0f7235c3777b7fc3bf manifest_sha=7748dce8c40057acab4ca3f92f0f5f1e9f731236e7929b0f7235c3777b7fc3bf dl_bytes=36352 manifest_bytes=36352
# 
# === V3: NON-MANIFEST FILES (build_manifest.parquet, README.md) ===
#   README.md: present, non-LFS(git-blob), oid=ba30c43e3f6653d99857bcf91a45e0224005c21c, size=10709
#   build_manifest.parquet: present, LFS, oid=729d009704fcfe6d53f2aac37de113537de1378e4d1e3549b392d788a9a4f264, size=62342
# 
# === V4: TOTAL BYTES ===
# Remote total bytes (all 500 files incl. control): 3,837,887,419
# Remote data-object bytes (excl. non-manifest + control): 3,837,811,864 (manifest sum: 3,837,811,864)
# Expected data-object bytes: 3,837,811,864
# 
# === VERDICT ===
#   [PASS] remote_file_count==500(499+gitattributes)
#   [PASS] data_objects==497
#   [PASS] zero_missing
#   [PASS] zero_true_strays
#   [PASS] both_non_manifest_present
#   [PASS] gitattributes_present
#   [PASS] sha_match==497
#   [PASS] size_match==497
#   [PASS] data_bytes==manifest_sum
#   [PASS] data_bytes==3837811864
# 
# SCRIPT 08 OVERALL: PASS
# Upload is byte-faithful to the local build manifest (all 497 data objects).
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
