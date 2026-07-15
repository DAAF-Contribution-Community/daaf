#!/usr/bin/env python3
# =============================================================================
# LOCAL HIGH-FIDELITY SYNTHESIS (Python / SDV)  --  DAAF synthetic-data-workflow
# =============================================================================
# T4 of the disclosure ladder. You run this on YOUR machine, on your REAL data.
# It fits a data-driven synthesizer (SDV GaussianCopula) and writes ONLY
# synthetic rows -- which are safe to share with DAAF.
#
#   !!  YOUR REAL DATA NEVER LEAVES THIS MACHINE.                              !!
#   !!  THE FITTED SYNTHESIZER OBJECT NEVER LEAVES THIS MACHINE.               !!
#   !!  A fitted synthesizer can regenerate real records -- it is as sensitive !!
#   !!  as the data itself. Share ONLY the synthetic output file + log below.  !!
#
# Self-contained: depends on NOTHING from DAAF. Requires the `sdv` package
# (pip install sdv); optional pyarrow for parquet output.
#
# Code style: flat and sequential. Read top to bottom.
# =============================================================================

# --- Config (EDIT THESE) -----------------------------------------------------
INPUT_PATH            = "data.csv"                  # your REAL data (stays local)
OUTPUT_SYNTHETIC_PATH = "synthetic_output.parquet"  # ONLY this file is shareable
OUTPUT_LOG_PATH       = "synthesis_log.txt"         # generation log (shareable)
SEED                  = 20260715                    # reproducibility seed (record it)
N_SYNTHETIC           = None                         # rows to generate; None = match real N
ENFORCE_MIN_MAX       = False   # True clamps synthetic values to REAL min/max -- a mild
                                # disclosure of the real extremes. Keep False if your
                                # threat model cares about tail leakage.
# -----------------------------------------------------------------------------

# --- Config (imports) --------------------------------------------------------
import os
import numpy as np
import pandas as pd

np.random.seed(SEED)
try:
    from sdv.metadata import Metadata
    from sdv.single_table import GaussianCopulaSynthesizer
except ImportError:
    raise SystemExit("This template needs SDV: pip install sdv")

# --- Load (REAL data -- never shared) ----------------------------------------
# ASSUMES: runs in YOUR environment on real data; nothing here touches DAAF.
ext = os.path.splitext(INPUT_PATH)[1].lower().lstrip(".")
if ext == "csv":
    real = pd.read_csv(INPUT_PATH)
elif ext == "parquet":
    real = pd.read_parquet(INPUT_PATH)  # needs pyarrow
else:
    raise SystemExit(f"Unsupported extension: {ext}")
n_real = len(real)
print(f"Loaded {n_real} real rows x {real.shape[1]} columns (LOCAL ONLY)")

# --- Fit synthesizer (fitted model -- never shared) --------------------------
# INTENT: fit a Gaussian copula with a recorded seed.
# REASONING: fast, interpretable, robust on small data.
metadata = Metadata.detect_from_dataframe(real)
synth = GaussianCopulaSynthesizer(metadata, enforce_min_max_values=ENFORCE_MIN_MAX)
synth.fit(real)   # <- fitted synthesizer object: DO NOT SHARE

# --- Sample synthetic rows ---------------------------------------------------
k = n_real if N_SYNTHETIC is None else N_SYNTHETIC
synthetic = synth.sample(num_rows=k)

# --- Validate ----------------------------------------------------------------
assert len(synthetic) == k, "synthetic row count mismatch"
assert list(synthetic.columns) == list(real.columns), "column set mismatch"
print(f"Generated {len(synthetic)} synthetic rows.")

# --- Save (ONLY synthetic rows + log cross the boundary) ---------------------
out_ext = os.path.splitext(OUTPUT_SYNTHETIC_PATH)[1].lower().lstrip(".")
if out_ext == "parquet":
    try:
        synthetic.to_parquet(OUTPUT_SYNTHETIC_PATH)
    except ImportError:
        OUTPUT_SYNTHETIC_PATH = OUTPUT_SYNTHETIC_PATH.rsplit(".", 1)[0] + ".csv"
        synthetic.to_csv(OUTPUT_SYNTHETIC_PATH, index=False)
else:
    synthetic.to_csv(OUTPUT_SYNTHETIC_PATH, index=False)

try:
    import sdv as _sdv
    sdv_version = getattr(_sdv, "__version__", "unknown")
except Exception:
    sdv_version = "unknown"
log_lines = [
    "SYNTHESIS LOG (SDV / GaussianCopula) -- shareable",
    f"seed: {SEED}",
    f"sdv_version: {sdv_version}",
    f"real_rows: {n_real}  synthetic_rows: {len(synthetic)}",
    f"columns: {real.shape[1]}",
    f"enforce_min_max_values: {ENFORCE_MIN_MAX}",
    "NOTE: real data and the fitted synthesizer were NOT written and must NOT be shared.",
]
with open(OUTPUT_LOG_PATH, "w") as f:
    f.write("\n".join(log_lines) + "\n")

print(f"\nWrote (SAFE TO SHARE):\n  {OUTPUT_SYNTHETIC_PATH}\n  {OUTPUT_LOG_PATH}")
print("\n>>> Do NOT share the real data or the fitted synthesizer. Only the two files above. <<<")
