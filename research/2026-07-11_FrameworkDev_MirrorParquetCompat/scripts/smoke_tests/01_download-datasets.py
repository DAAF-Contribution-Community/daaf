#!/usr/bin/env python3
"""
Smoke-test dataset acquisition for the Python<->R mirror parquet equivalence audit.

INTENT: assemble a 5-dataset test matrix in scratch/. Two files are already
present (SAIPE view-typed, MEPS plain-string). This script HEAD-checks and
downloads three more, chosen to stress distinct hazards:
  - EDFacts grad rates (view-typed strings expected: another string_view case)
  - CRDC discipline (zero-padded string IDs: crdc_id / ncessch / leaid)
  - IPEDS finance (large-magnitude integers: int64 downcast / precision risk)

Downloads are capped at ~150MB via an HTTP HEAD content-length probe; any file
over the cap is skipped and reported, never downloaded.
"""

# --- Config ---
import os
import urllib.request

SCRATCH = "/daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/scratch"
MIRROR = "https://huggingface.co/datasets/brhkim/education_data_portal_mirror/resolve/main/{path}.parquet"
SIZE_CAP_BYTES = 150 * 1024 * 1024  # 150 MB hard cap per prompt

# INTENT: (local_filename, canonical_path, rationale). Paths from datasets-reference.md.
# ASSUMES: EDFacts school grad rates 2018 exists (coverage 2010-2019, line 138).
#   CRDC discipline 2017 (coverage 2011-2021, line 88). IPEDS finance single-file
#   (line 163) is large; if >cap we fall back to a smaller IPEDS integer-heavy file.
TARGETS = [
    ("edfacts_grad_rates_2018.parquet", "edfacts/schools_edfacts_grad_rates_2018",
     "EDFacts grad rates: expected view-typed strings + ACGR bucket strings"),
    ("crdc_discipline_2017.parquet", "crdc/schools_crdc_discipline_k12_2017",
     "CRDC discipline: zero-padded string IDs crdc_id/ncessch/leaid"),
    ("ipeds_finance.parquet", "ipeds/colleges_ipeds_finance",
     "IPEDS finance: large-magnitude integers, int64 precision candidates"),
]

# --- Fetch ---
for fname, path, why in TARGETS:
    dest = os.path.join(SCRATCH, fname)
    url = MIRROR.format(path=path)
    print(f"\n### {fname}")
    print(f"    path : {path}")
    print(f"    why  : {why}")

    if os.path.exists(dest):
        # REASONING: idempotent — re-running should not re-download. Report existing size.
        sz = os.path.getsize(dest)
        print(f"    SKIP (already present): {sz:,} bytes ({sz/1024/1024:.1f} MB)")
        continue

    # INTENT: HEAD probe for content-length BEFORE committing to a download.
    # ASSUMES: HuggingFace resolve endpoint honors HEAD and returns Content-Length.
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            clen = resp.headers.get("Content-Length")
            final_url = resp.geturl()
    except Exception as e:
        print(f"    HEAD FAILED: {type(e).__name__}: {e}")
        continue

    if clen is None:
        print(f"    HEAD returned no Content-Length; final_url={final_url}")
        print("    Proceeding with a streamed download but will abort if >cap mid-stream.")
        clen_int = None
    else:
        clen_int = int(clen)
        print(f"    HEAD content-length: {clen_int:,} bytes ({clen_int/1024/1024:.1f} MB)")
        if clen_int > SIZE_CAP_BYTES:
            print(f"    SKIP: exceeds {SIZE_CAP_BYTES/1024/1024:.0f}MB cap — not downloading.")
            continue

    # --- Download (guarded) ---
    # REASONING: stream to disk; if content-length was absent, enforce cap by byte count.
    tmp = dest + ".part"
    written = 0
    aborted = False
    with urllib.request.urlopen(url, timeout=300) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > SIZE_CAP_BYTES:
                aborted = True
                break
            out.write(chunk)
    if aborted:
        os.remove(tmp)
        print(f"    ABORTED mid-stream: exceeded {SIZE_CAP_BYTES/1024/1024:.0f}MB cap.")
        continue
    os.replace(tmp, dest)
    print(f"    DOWNLOADED: {written:,} bytes ({written/1024/1024:.1f} MB)")

# --- Summary ---
print("\n" + "=" * 70)
print("Scratch directory parquet inventory:")
for f in sorted(os.listdir(SCRATCH)):
    if f.endswith(".parquet"):
        p = os.path.join(SCRATCH, f)
        sz = os.path.getsize(p)
        print(f"    {f:45s} {sz/1024/1024:8.1f} MB")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-11 19:24:49
# Command: python3 /daaf/research/2026-07-11_FrameworkDev_MirrorParquetCompat/scripts/smoke_tests/01_download-datasets.py
# Duration: 14s
# Exit code: 0
#
# --- STDOUT ---
# 
# ### edfacts_grad_rates_2018.parquet
#     path : edfacts/schools_edfacts_grad_rates_2018
#     why  : EDFacts grad rates: expected view-typed strings + ACGR bucket strings
#     HEAD content-length: 1,505,702 bytes (1.4 MB)
#     DOWNLOADED: 1,505,702 bytes (1.4 MB)
# 
# ### crdc_discipline_2017.parquet
#     path : crdc/schools_crdc_discipline_k12_2017
#     why  : CRDC discipline: zero-padded string IDs crdc_id/ncessch/leaid
#     HEAD content-length: 14,946,038 bytes (14.3 MB)
#     DOWNLOADED: 14,946,038 bytes (14.3 MB)
# 
# ### ipeds_finance.parquet
#     path : ipeds/colleges_ipeds_finance
#     why  : IPEDS finance: large-magnitude integers, int64 precision candidates
#     HEAD content-length: 31,335,157 bytes (29.9 MB)
#     DOWNLOADED: 31,335,157 bytes (29.9 MB)
# 
# ======================================================================
# Scratch directory parquet inventory:
#     crdc_discipline_2017.parquet                      14.3 MB
#     edfacts_grad_rates_2018.parquet                    1.4 MB
#     ipeds_finance.parquet                             29.9 MB
#     meps_schools_WORKING.parquet                      30.6 MB
#     saipe_districts_FAILING.parquet                    8.5 MB
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
