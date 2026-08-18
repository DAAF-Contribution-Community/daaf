#!/usr/bin/env python3
"""
Mirror maintenance 5/7: carry forward hash-verified unchanged objects into the v2 tree.

Task: carry-forward-mirror-v2 (Stage build unit 05 of 05->06->07)
Depends on: 2026-08-06 mirror-v2 delta manifest (authoritative classifications)
Inputs (read-only GET from old Hugging Face mirror):
  - 458 build_action == "carry-forward" objects (presumed-unchanged; .parquet + .xls)
  - 29 build_action == "fetch-fresh" objects whose old_mirror_url is non-null
    (the revised + candidate-revised set; OLD versions only, for the comparison battery)
Outputs:
  - mirror_v2_tree/{source}/{filename}.{parquet|xls}  (458 carried-forward files)
  - old_vintage_copies/{source}/{filename}.{parquet|xls}  (29 old-vintage files)
  - audit/build_provenance_carry_forward.parquet  (458 rows)
  - audit/build_provenance_old_vintage.parquet     (29 rows)
Checkpoint: MA-BUILD-05 (per-file sha256/size verification against HF LFS/git-blob oids)

Network operations are read-only GET only. Every file is verified after download:
LFS objects (64-hex oid) by SHA-256; non-LFS git-blob objects (40-hex oid) by the
git blob SHA-1 (sha1(b"blob {size}\\0" + content)) plus exact byte size. The script is
idempotent/resumable: an already-present file that re-verifies is skipped, not re-downloaded.
"""

# --- Config ---
# INTENT: bind the build to the authoritative delta manifest and fix stable download
# policy (timeouts, retry/backoff, polite pacing). REASONING: HF resolve URLs 302 to a
# CDN for LFS blobs; requests follows redirects, so downloaded bytes are the object bytes
# and their SHA-256 must equal the LFS oid. ASSUMES: manifest classifications are trusted.
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
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
CARRY_PROV_PATH = AUDIT_DIR / "build_provenance_carry_forward.parquet"
VINTAGE_PROV_PATH = AUDIT_DIR / "build_provenance_old_vintage.parquet"

DATE_PREFIX = "2026-08-06"
PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 3
CHUNK_BYTES = 8 * 1024 * 1024
CONNECT_TIMEOUT = 60
READ_TIMEOUT = 600
POLITE_SLEEP_SECONDS = 0.15  # gentle pacing between HF requests

# --- Load ---
manifest = pl.read_parquet(MANIFEST_PATH)
print(f"Loaded delta manifest: {manifest.shape[0]} rows x {manifest.shape[1]} cols")

# INTENT: split the manifest into the two HF-download roles this script handles.
# REASONING: carry-forward populates the shippable tree; old-vintage populates a side
# directory for the upcoming old-vs-new comparison battery. Both verify identically.
# ASSUMES: build_action is authoritative; the 10 truly-new objects have null old_mirror_url
# and are therefore excluded from the old-vintage set automatically.
carry_df = manifest.filter(pl.col("build_action") == "carry-forward")
vintage_df = manifest.filter(
    (pl.col("build_action") == "fetch-fresh") & pl.col("old_mirror_url").is_not_null()
)
print(f"Carry-forward objects: {carry_df.height} (expected 458)")
print(f"Old-vintage objects:   {vintage_df.height} (expected 29)")
assert carry_df.height == 458, f"STOP: expected 458 carry-forward, got {carry_df.height}"
assert vintage_df.height == 29, f"STOP: expected 29 old-vintage, got {vintage_df.height}"
assert carry_df["old_mirror_url"].null_count() == 0, "STOP: null old_mirror_url in carry-forward"
assert carry_df["old_mirror_path"].null_count() == 0, "STOP: null old_mirror_path in carry-forward"
assert carry_df["old_mirror_lfs_sha256"].null_count() == 0, "STOP: null oid in carry-forward"

# --- Build the combined download task list ---
# INTENT: assemble one flat list of (url, dest, expected size/oid, role) records so a
# single sequential loop handles both roles without helper functions (DAAF flat-script
# style). REASONING: DRY without abstraction; identical verification path for both roles.
# ASSUMES: old_mirror_path already carries the correct extension (.parquet / .xls) and the
# {source}/{filename} layout that the v2 tree must reproduce exactly.
tasks = []
for row in carry_df.iter_rows(named=True):
    tasks.append({
        "canonical_object_key": row["canonical_object_key"],
        "source": row["source"],
        "object_kind": row["object_kind"],
        "classification": row["classification"],
        "relative_path": row["old_mirror_path"],
        "url": row["old_mirror_url"],
        "expected_size_bytes": row["old_mirror_size_bytes"],
        "expected_oid": row["old_mirror_lfs_sha256"],
        "provenance_role": "carried-forward",
        "dest_root": str(TREE_DIR),
    })
for row in vintage_df.iter_rows(named=True):
    tasks.append({
        "canonical_object_key": row["canonical_object_key"],
        "source": row["source"],
        "object_kind": row["old_mirror_object_kind"],
        "classification": row["classification"],
        "relative_path": row["old_mirror_path"],
        "url": row["old_mirror_url"],
        "expected_size_bytes": row["old_mirror_size_bytes"],
        "expected_oid": row["old_mirror_lfs_sha256"],
        "provenance_role": "old-vintage",
        "dest_root": str(OLD_VINTAGE_DIR),
    })
print(f"Total download tasks: {len(tasks)} (expected 487)")
assert len(tasks) == 487, f"STOP: expected 487 tasks, got {len(tasks)}"

# --- HTTP session with retry/backoff ---
session = requests.Session()
retry = Retry(
    total=5, connect=5, read=5, backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"],
)
session.mount("https://", HTTPAdapter(max_retries=retry))
session.headers.update({"Accept-Encoding": "identity", "User-Agent": "daaf-mirror-v2-build/1.0"})

# --- Transfer + verify (one object per iteration; checkpoint each) ---
# INTENT: stream each object to disk while hashing, then verify against its oid.
# REASONING: verify-then-keep guarantees no unverified byte ships. An oid of 64 hex chars
# is an LFS SHA-256; 40 hex chars is a git blob SHA-1 (small non-LFS file). ASSUMES: the
# HF resolve URL returns the resolved object body (LFS redirect handled by requests).
provenance_records = []
skipped = 0
downloaded = 0
for i, task in enumerate(tasks, start=1):
    key = task["canonical_object_key"]
    dest = Path(task["dest_root"]) / task["relative_path"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected_size = int(task["expected_size_bytes"])
    expected_oid = task["expected_oid"].strip().lower()
    # INTENT: choose the verification scheme from oid length. REASONING: HF tree API
    # returns lfs.oid (sha256, 64 hex) for LFS files and the git blob oid (sha1, 40 hex)
    # for small non-LFS files. ASSUMES: no other oid lengths occur (asserted below).
    if len(expected_oid) == 64:
        oid_kind, verification_method = "lfs_sha256", "sha256_vs_lfs_oid"
    elif len(expected_oid) == 40:
        oid_kind, verification_method = "git_blob_sha1", "git_blob_sha1_plus_size"
    else:
        raise AssertionError(f"STOP: unexpected oid length {len(expected_oid)} for {key}")

    # INTENT: resumable skip — recompute the hash of an existing file and verify it before
    # skipping. REASONING: path existence alone is insufficient evidence of a good file
    # (a prior run may have been interrupted mid-write). ASSUMES: a re-verified file is
    # byte-identical to what a fresh download would produce. Hashing is inlined (flat-script
    # style: no helper functions); the git-blob SHA-1 is computed in one pass since the
    # existing file size is known from the first read.
    action = None
    if dest.exists():
        existing_size = dest.stat().st_size
        eh256 = hashlib.sha256()
        egit = hashlib.sha1()
        egit.update(b"blob " + str(existing_size).encode() + b"\x00")
        with dest.open("rb") as fh:
            while True:
                chunk = fh.read(CHUNK_BYTES)
                if not chunk:
                    break
                eh256.update(chunk)
                egit.update(chunk)
        existing_sha256 = eh256.hexdigest()
        existing_git = egit.hexdigest() if oid_kind == "git_blob_sha1" else None
        matched = (existing_git == expected_oid) if oid_kind == "git_blob_sha1" else (existing_sha256 == expected_oid)
        if matched and existing_size == expected_size:
            shipped_sha256, computed_git, shipped_bytes = existing_sha256, existing_git, existing_size
            action = "skipped_reverified"
            skipped += 1
        else:
            dest.unlink()  # corrupt/incomplete prior artifact; re-download

    if action is None:
        # --- Download ---
        h256 = hashlib.sha256()
        shipped_bytes = 0
        resp = session.get(task["url"], stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), allow_redirects=True)
        assert resp.status_code == 200, f"STOP: HTTP {resp.status_code} for {key} ({task['url']})"
        with dest.open("wb") as out:
            for chunk in resp.iter_content(chunk_size=CHUNK_BYTES):
                if not chunk:
                    continue
                shipped_bytes += len(chunk)
                h256.update(chunk)
                out.write(chunk)
        resp.close()
        shipped_sha256 = h256.hexdigest()
        # git blob sha1 needs the final size, so compute in a second small pass if needed
        computed_git = None
        if oid_kind == "git_blob_sha1":
            gsh = hashlib.sha1()
            gsh.update(b"blob " + str(shipped_bytes).encode() + b"\x00")
            with dest.open("rb") as fh:
                while True:
                    c = fh.read(CHUNK_BYTES)
                    if not c:
                        break
                    gsh.update(c)
            computed_git = gsh.hexdigest()
        action = "downloaded"
        downloaded += 1
        time.sleep(POLITE_SLEEP_SECONDS)

    # --- Verify ---
    # INTENT: fail loudly on any size/oid mismatch. REASONING: an unverified carry-forward
    # would silently ship stale or corrupt data. ASSUMES: exact byte-size equality is
    # required (no re-compression); oid equality is the definitive content check.
    size_ok = shipped_bytes == expected_size
    if oid_kind == "lfs_sha256":
        oid_ok = shipped_sha256 == expected_oid
    else:
        oid_ok = computed_git == expected_oid
    verification_result = "PASS" if (size_ok and oid_ok) else "FAIL"
    assert verification_result == "PASS", (
        f"STOP: verification FAIL for {key}: size_ok={size_ok} "
        f"(got {shipped_bytes} vs {expected_size}), oid_ok={oid_ok} ({oid_kind})"
    )

    # Parquet readability spot-guard for data objects (magic bytes only; full check in 07)
    if task["relative_path"].endswith(".parquet"):
        with dest.open("rb") as fh:
            head = fh.read(4)
            fh.seek(-4, 2)
            tail = fh.read(4)
        assert head == b"PAR1" and tail == b"PAR1", f"STOP: bad parquet magic for {key}"

    provenance_records.append({
        "canonical_object_key": key,
        "source": task["source"],
        "object_kind": task["object_kind"],
        "relative_path": task["relative_path"],
        "filename": Path(task["relative_path"]).name,
        "provenance_role": task["provenance_role"],
        "classification": task["classification"],
        "source_url": task["url"],
        "expected_size_bytes": expected_size,
        "expected_oid": expected_oid,
        "oid_kind": oid_kind,
        "shipped_bytes": shipped_bytes,
        "shipped_sha256": shipped_sha256,
        "computed_git_blob_sha1": computed_git,
        "verification_method": verification_method,
        "verification_result": verification_result,
        "action": action,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    if i % 25 == 0 or i == len(tasks):
        print(f"[{i}/{len(tasks)}] {action:18s} {key}  ({shipped_bytes:,} B, {verification_result})")

# --- Validate + Save provenance ---
prov = pl.from_dicts(provenance_records, infer_schema_length=None)
carry_prov = prov.filter(pl.col("provenance_role") == "carried-forward")
vintage_prov = prov.filter(pl.col("provenance_role") == "old-vintage")
print(f"\nProvenance rows: carry={carry_prov.height}, vintage={vintage_prov.height}")
assert carry_prov.height == 458, "STOP: carry provenance count off"
assert vintage_prov.height == 29, "STOP: vintage provenance count off"
assert (prov["verification_result"] == "PASS").all(), "STOP: non-PASS verification present"

carry_prov.write_parquet(CARRY_PROV_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL)
vintage_prov.write_parquet(VINTAGE_PROV_PATH, compression=PARQUET_COMPRESSION, compression_level=PARQUET_COMPRESSION_LEVEL)

# On-disk existence + count validation for the carry-forward tree
tree_files = [p for p in TREE_DIR.rglob("*") if p.is_file()]
vintage_files = [p for p in OLD_VINTAGE_DIR.rglob("*") if p.is_file()]
print(f"Tree files on disk (this stage only): {len(tree_files)}")
print(f"Old-vintage files on disk: {len(vintage_files)}")
print("\n--- Verification method breakdown ---")
print(prov.group_by("provenance_role", "oid_kind", "verification_method").len().sort("provenance_role", "oid_kind"))
print(f"\nSummary: {downloaded} downloaded, {skipped} skipped(re-verified), total {len(tasks)}")
total_bytes = int(carry_prov["shipped_bytes"].sum())
print(f"Carry-forward total bytes: {total_bytes:,}")
print(f"Saved: {CARRY_PROV_PATH}")
print(f"Saved: {VINTAGE_PROV_PATH}")
print("CHECKPOINT MA-BUILD-05: PASS")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-08-06 19:54:59
# Command: python3 /daaf/scripts/mirror_maintenance/05_carry-forward-mirror-v2.py
# Duration: 1440s
# Exit code: 0
#
# --- STDOUT ---
# Loaded delta manifest: 497 rows x 30 cols
# Carry-forward objects: 458 (expected 458)
# Old-vintage objects:   29 (expected 29)
# Total download tasks: 487 (expected 487)
# [25/487] downloaded         ccd/schools_ccd_enrollment_2005  (17,838,991 B, PASS)
# [50/487] downloaded         ccd/schools_ccd_lea_enrollment_1992  (511,860 B, PASS)
# [75/487] downloaded         ccd/schools_ccd_lea_enrollment_2017  (4,891,873 B, PASS)
# [100/487] downloaded         crdc/codebook_schools_crdc_restraint-seclusion-instances  (17,920 B, PASS)
# [125/487] downloaded         crdc/schools_crdc_discipline_k12_2011  (8,549,758 B, PASS)
# [150/487] downloaded         crdc/schools_crdc_restraint_seclusion_students_2011  (1,725,547 B, PASS)
# [175/487] downloaded         edfacts/codebook_districts_edfacts_graduation  (21,504 B, PASS)
# [200/487] downloaded         edfacts/schools_edfacts_assessments_2010  (29,407,762 B, PASS)
# [225/487] downloaded         fsa/colleges_fsa_90_10_revenue_percentages  (254,280 B, PASS)
# [250/487] downloaded         ipeds/codebook_colleges_ipeds_outcome-measures  (40,448 B, PASS)
# [275/487] downloaded         ipeds/colleges_ipeds_completions-2digcip_2006  (1,523,169 B, PASS)
# [300/487] downloaded         ipeds/colleges_ipeds_completions-6digcip_1991  (641,621 B, PASS)
# [325/487] downloaded         ipeds/colleges_ipeds_completions-6digcip_2016  (3,348,636 B, PASS)
# [350/487] downloaded         ipeds/colleges_ipeds_fall-enrollment-age_2013  (3,303,132 B, PASS)
# [375/487] downloaded         ipeds/colleges_ipeds_fall-enrollment-race_2003  (5,416,589 B, PASS)
# [400/487] downloaded         ipeds/colleges_ipeds_sfa_ftft  (9,271,304 B, PASS)
# [425/487] downloaded         pseo/colleges_pseo_2001  (2,093,916 B, PASS)
# [450/487] downloaded         scorecard/codebook_colleges_scorecard_repayment  (21,504 B, PASS)
# [475/487] downloaded         ipeds/colleges_ipeds_fall-enrollment-race_2020  (8,648,663 B, PASS)
# [487/487] downloaded         ipeds/colleges_ipeds_grad-rates  (41,612,928 B, PASS)
# 
# Provenance rows: carry=458, vintage=29
# Tree files on disk (this stage only): 458
# Old-vintage files on disk: 29
# 
# --- Verification method breakdown ---
# shape: (4, 4)
# ┌─────────────────┬───────────────┬─────────────────────────┬─────┐
# │ provenance_role ┆ oid_kind      ┆ verification_method     ┆ len │
# │ ---             ┆ ---           ┆ ---                     ┆ --- │
# │ str             ┆ str           ┆ str                     ┆ u32 │
# ╞═════════════════╪═══════════════╪═════════════════════════╪═════╡
# │ carried-forward ┆ git_blob_sha1 ┆ git_blob_sha1_plus_size ┆ 88  │
# │ carried-forward ┆ lfs_sha256    ┆ sha256_vs_lfs_oid       ┆ 370 │
# │ old-vintage     ┆ git_blob_sha1 ┆ git_blob_sha1_plus_size ┆ 2   │
# │ old-vintage     ┆ lfs_sha256    ┆ sha256_vs_lfs_oid       ┆ 27  │
# └─────────────────┴───────────────┴─────────────────────────┴─────┘
# 
# Summary: 487 downloaded, 0 skipped(re-verified), total 487
# Carry-forward total bytes: 3,240,546,501
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/build_provenance_carry_forward.parquet
# Saved: /daaf/research/2026-08-06_FrameworkDev_MirrorV2Update/2026-08-06_mirror-v2-audit/build_provenance_old_vintage.parquet
# CHECKPOINT MA-BUILD-05: PASS
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
