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
# INTENT: assertions are release gates, so optimized Python must never run this synthesizer.
# REASONING: -O/-OO/PYTHONOPTIMIZE remove assert statements but would leave PASS reporting,
# so a synthetic file could be declared verified without any check having executed.
if not __debug__:
    raise SystemExit("SYNTHESIS VALIDATION: FAILED -- optimized Python is unsupported; run without -O/-OO or PYTHONOPTIMIZE. No synthetic output written.")

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
# INTENT: every check prints one counted outcome line; the verdict is DERIVED from the
# counters, never asserted. REASONING: a gate whose evidence is missing has not gated.
synthesis = {"passed": 0, "warning": 0, "failed": 0, "not_verified": 0, "skipped": 0}
if len(synthetic) == k:
    synthesis["passed"] += 1
    print(f"[PASS] synthetic_row_count: {len(synthetic)} rows generated == {k} requested")
else:
    synthesis["failed"] += 1
    print(f"[FAIL] synthetic_row_count: {len(synthetic)} rows generated vs {k} requested")
if list(synthetic.columns) == list(real.columns):
    synthesis["passed"] += 1
    print(f"[PASS] column_set_and_order: {len(synthetic.columns)} columns match the real frame")
else:
    missing = [c for c in real.columns if c not in synthetic.columns]
    extra = [c for c in synthetic.columns if c not in real.columns]
    synthesis["failed"] += 1
    print(f"[FAIL] column_set_and_order: missing {missing}, unexpected {extra}")
# INTENT: the seed must be recorded, because an unrecorded seed makes this irreproducible.
if type(SEED) is int:
    synthesis["passed"] += 1
    print(f"[PASS] seed_recorded: generation seed {SEED} is set and will be written to the log")
else:
    synthesis["failed"] += 1
    print("[FAIL] seed_recorded: SEED is not an integer; the run is not reproducible")
print("Checks: {passed} passed, {warning} warnings, {failed} failed, "
      "{not_verified} not verified, {skipped} skipped".format(**synthesis))
if (synthesis["failed"] > 0 or synthesis["not_verified"] > 0 or
        synthesis["passed"] + synthesis["warning"] + synthesis["failed"] == 0):
    synthesis_verdict = "FAILED"
elif synthesis["warning"] > 0:
    synthesis_verdict = "PASSED WITH WARNINGS"
else:
    synthesis_verdict = "PASSED"
print("SYNTHESIS VALIDATION: " + synthesis_verdict)
if synthesis_verdict == "FAILED":
    raise SystemExit("SYNTHESIS VALIDATION: FAILED -- nothing written; do not share any partial output.")
print(f"Generated {len(synthetic)} synthetic rows.")

# --- Save (ONLY synthetic rows + log cross the boundary) ---------------------
# OUTPUT FORMAT: Parquet is the PREFERRED exchange format. CSV is only a fallback for
# when pyarrow is unavailable locally -- and it is an AUDITED boundary exception: on
# receipt DAAF converts the CSV to Parquet and records an exchange manifest, after which
# all in-container work uses the Parquet. Prefer installing pyarrow and sending Parquet.
out_ext = os.path.splitext(OUTPUT_SYNTHETIC_PATH)[1].lower().lstrip(".")
if out_ext == "parquet":
    try:
        synthetic.to_parquet(OUTPUT_SYNTHETIC_PATH)
    except ImportError:
        # Fallback: pyarrow unavailable -> write CSV (audited exception; DAAF converts
        # to Parquet on receipt). Install pyarrow to avoid this.
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
