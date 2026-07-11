#!/usr/bin/env python3
"""
Download one failing mirror parquet (SAIPE districts) and one working control
(MEPS schools) from the HuggingFace education-data mirror for local diagnosis.

Diagnostic precursor to a skill read-pattern fix. Files land in this scratch dir
(inside the backup/audit boundary; no /tmp writes).
"""

# --- Config ---
import os
import urllib.request

# INTENT: pin the exact mirror URL pattern under investigation.
# ASSUMES: resolve/main serves the raw parquet bytes (HF LFS resolve endpoint).
BASE = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main"
SCRATCH = os.path.dirname(os.path.abspath(__file__))

# REASONING: SAIPE districts is the confirmed-failing file and is small; MEPS is
# the confirmed-working control. Two files isolate the failing-vs-working contrast.
FILES = {
    "saipe_districts_FAILING.parquet": f"{BASE}/saipe/districts_saipe.parquet",
    "meps_schools_WORKING.parquet": f"{BASE}/meps/schools_meps.parquet",
}

# --- Load (download) ---
for local_name, url in FILES.items():
    dest = os.path.join(SCRATCH, local_name)
    # INTENT: stream to disk; report byte count for a download-integrity sanity check.
    req = urllib.request.Request(url, headers={"User-Agent": "daaf-diagnostic/1.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    print(f"downloaded {local_name}: {len(data):,} bytes -> {dest}")

# --- Validate ---
for local_name in FILES:
    dest = os.path.join(SCRATCH, local_name)
    size = os.path.getsize(dest)
    # INTENT: confirm the file exists and is non-trivial (guards against truncated
    # HTML error pages masquerading as parquet).
    assert size > 1000, f"{local_name} suspiciously small ({size} bytes) — possible error page"
    with open(dest, "rb") as f:
        magic = f.read(4)
    # ASSUMES: valid parquet files begin with the "PAR1" magic bytes.
    assert magic == b"PAR1", f"{local_name} does not start with PAR1 magic (got {magic!r})"
    print(f"validated {local_name}: {size:,} bytes, PAR1 magic OK")

# --- Summary ---
print("SUMMARY: both sample files downloaded and validated as parquet.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 15:29:33
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/01_download-samples.py
# Duration: 9s
# Exit code: 0
#
# --- STDOUT ---
# downloaded saipe_districts_FAILING.parquet: 8,916,771 bytes -> /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/saipe_districts_FAILING.parquet
# downloaded meps_schools_WORKING.parquet: 32,110,398 bytes -> /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch/meps_schools_WORKING.parquet
# validated saipe_districts_FAILING.parquet: 8,916,771 bytes, PAR1 magic OK
# validated meps_schools_WORKING.parquet: 32,110,398 bytes, PAR1 magic OK
# SUMMARY: both sample files downloaded and validated as parquet.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
