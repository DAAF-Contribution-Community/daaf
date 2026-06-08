#!/usr/bin/env python3
"""
Setup: Create project workspace directories.

Task: setup-dirs
Purpose: Create the standard DAAF project directory structure for ad hoc profiling.
"""

from pathlib import Path

# --- Config ---
PROJECT_DIR = Path("/daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session")

# --- Create directories ---
dirs = [
    PROJECT_DIR / "scripts" / "adhoc",
    PROJECT_DIR / "data" / "raw",
    PROJECT_DIR / "data" / "processed",
    PROJECT_DIR / "output" / "analysis",
    PROJECT_DIR / "output" / "figures",
]

for d in dirs:
    d.mkdir(parents=True, exist_ok=True)
    print(f"Created: {d}")

print("\nAll directories created successfully.")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-06-08 02:20:34
# Command: python3 /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc/00_setup-dirs.py
# Duration: 0s
# Exit code: 0
#
# --- STDOUT ---
# Created: /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/scripts/adhoc
# Created: /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/raw
# Created: /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/data/processed
# Created: /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/output/analysis
# Created: /daaf/benchmarks/_sandbox/run_dc-11_Opus_4.6_0/research/2026-06-08_AdHoc_Session/output/figures
# 
# All directories created successfully.
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
