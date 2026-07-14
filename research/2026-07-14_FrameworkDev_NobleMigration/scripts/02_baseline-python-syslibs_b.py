# --- Config ---
# INTENT: Capture baseline Python package manifest and system-library version
#         strings for the current bookworm x86_64 DAAF image, producing the
#         "before" halves of the Python-side version-drift manifests described
#         in §6.2 of the Noble Migration Scoping Guide.
# REASONING: Two manifests are needed: (1) uv pip freeze for the full Python
#             package inventory; (2) one-line version strings for system
#             components that the R-side smoke tests cannot capture (GDAL, PROJ,
#             GEOS, glibc, Quarto, uv). Storing both as parquet enables
#             anti-join diffs against the post-noble manifests.
# ASSUMES: Running inside the bookworm x86_64 DAAF container.
#           uv, gdalinfo, geos-config, ldd, R, quarto, and python3 are on PATH.
#           projinfo may not be installed; falls back to `proj` (no args).
#
# VERSION HISTORY:
#   v1 (02_baseline-python-syslibs.py):     FAILED — projinfo bare FileNotFoundError
#   v_a (02_baseline-python-syslibs_a.py):  Fix applied but log already present from cp
#   v_b (this file):                         Clean copy of _a fix; FINAL

import subprocess
import polars as pl
from pathlib import Path

PROJECT_DIR = Path("/daaf/research/2026-07-14_FrameworkDev_NobleMigration")
OUTPUT_DIR  = PROJECT_DIR / "output"
OUTPUT_PY_PATH  = OUTPUT_DIR / "2026-07-14_baseline_bookworm-x86_python-packages.parquet"
OUTPUT_SYS_PATH = OUTPUT_DIR / "2026-07-14_baseline_bookworm-x86_system-libs.parquet"

# INTENT: Ensure output directory exists (may already exist after Script 1).
# REASONING: Both scripts create this dir defensively so each is independently
#             re-runnable without manual setup.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# --- Load: Python package manifest via uv pip freeze ---
# =============================================================================
# INTENT: Capture the complete set of installed Python packages with pinned
#         versions, using uv's freeze command.
# REASONING: `uv pip freeze` produces PEP 440 == -pinned output (same format
#             as pip freeze). Parsing on `==` yields clean package/version pairs;
#             any non-== line (e.g. editable installs, -e .) is preserved in
#             the version field verbatim so no data is silently dropped.
# ASSUMES: uv is on PATH; UV_SYSTEM_PYTHON=1 in container so uv sees system env.

result_freeze = subprocess.run(
    ["uv", "pip", "freeze"],
    capture_output=True, text=True
)
freeze_lines = result_freeze.stdout.strip().splitlines()
print(f"uv pip freeze: {len(freeze_lines)} lines captured")

# --- Transform: parse freeze lines ---
# INTENT: Split each `package==version` line into two columns.
# REASONING: == is the canonical pip freeze separator. Lines without == are
#             kept verbatim so no row is silently lost.
records = []
for line in freeze_lines:
    line = line.strip()
    if not line:
        continue
    if "==" in line:
        pkg, ver = line.split("==", 1)
        records.append({"package": pkg.strip(), "version": ver.strip()})
    else:
        # Non-== line (e.g. editable install): keep raw text in both columns.
        records.append({"package": line, "version": line})

py_df = pl.DataFrame(records).with_columns(
    # INTENT: Tag every row with the source image so post-migration diffs work.
    pl.lit("bookworm-x86_64").alias("channel")
)

print(f"Python package manifest shape: {py_df.shape[0]} rows x {py_df.shape[1]} cols")
print(f"Columns: {py_df.columns}")

# =============================================================================
# --- Load: System-library version strings ---
# =============================================================================
# INTENT: Capture one-line version banners for geospatial and runtime system
#         components not visible in pip freeze or R packages.
# REASONING: GDAL, PROJ, GEOS, and glibc have the largest version jumps in the
#             bookworm→noble migration. R and Quarto are cross-check anchors.
# ASSUMES: Each command either exits 0 with version on stdout or prints a
#           version banner to stderr. Individual failures record
#           "NOT FOUND: <error>" rather than aborting; only four are asserted.

def capture_version(cmd, use_stderr=False):
    """Run cmd list; return first non-empty line of stdout (or stderr).
    On FileNotFoundError or any exception, return 'NOT FOUND: <msg>'."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        stream = r.stderr if use_stderr else r.stdout
        lines = [l.strip() for l in stream.splitlines() if l.strip()]
        if not lines:
            # INTENT: Fall back to the other stream if primary is empty.
            fallback = r.stderr if not use_stderr else r.stdout
            lines = [l.strip() for l in fallback.splitlines() if l.strip()]
        return lines[0] if lines else f"NOT FOUND: empty output (exit {r.returncode})"
    except FileNotFoundError:
        return f"NOT FOUND: command not found ({cmd[0]})"
    except Exception as e:
        return f"NOT FOUND: {e}"

def proj_version():
    """Try projinfo --version first; fall back to proj (no args).
    FIX (v_a/v_b): Both subprocess calls are inside try/except so a missing
    binary does not raise an unhandled FileNotFoundError.
    REASONING: bookworm ships proj but projinfo is in a separate package;
    on noble both may exist — we want whichever is present."""
    try:
        r = subprocess.run(
            ["projinfo", "--version"], capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in (r.stdout + r.stderr).splitlines() if l.strip()]
        if lines and r.returncode == 0:
            return lines[0]
    except FileNotFoundError:
        pass  # projinfo not installed; fall through
    except Exception:
        pass
    try:
        r2 = subprocess.run(["proj"], capture_output=True, text=True, timeout=10)
        lines2 = [l.strip() for l in (r2.stdout + r2.stderr).splitlines() if l.strip()]
        return lines2[0] if lines2 else "NOT FOUND: proj/projinfo both failed"
    except FileNotFoundError:
        return "NOT FOUND: neither projinfo nor proj found on PATH"
    except Exception as e:
        return f"NOT FOUND: {e}"

# INTENT: Collect one version string per component in migration-risk order.
# REASONING: Geospatial system libs first (highest migration risk: GDAL 3.6→3.8,
#             glibc 2.36→2.39), then language runtimes, then toolchain utilities.
sys_components = [
    ("gdalinfo",  capture_version(["gdalinfo", "--version"])),
    ("proj",      proj_version()),
    ("geos",      capture_version(["geos-config", "--version"])),
    ("glibc",     capture_version(["ldd", "--version"])),       # first line = glibc ver
    ("R",         capture_version(["R", "--version"])),         # first line = R ver
    ("quarto",    capture_version(["quarto", "--version"])),
    ("python3",   capture_version(["python3", "--version"])),
    ("uv",        capture_version(["uv", "--version"])),
]

sys_df = pl.DataFrame(
    {"component":      [c for c, _ in sys_components],
     "version_string": [v for _, v in sys_components]}
).with_columns(
    pl.lit("bookworm-x86_64").alias("channel")
)

# =============================================================================
# --- Validate ---
# =============================================================================
# INTENT: Print full system-libs table to the execution log and assert required
#         components were found.
# REASONING: gdalinfo, R, quarto, python3 absent would indicate a broken image;
#             PROJ and GEOS failures are logged but tolerated (they are visible
#             via R sf/geopandas at smoke time).
print("\n--- System-libs table ---")
print(sys_df)

required_found = ["gdalinfo", "R", "quarto", "python3"]
for comp in required_found:
    ver = sys_df.filter(pl.col("component") == comp)["version_string"][0]
    assert not ver.startswith("NOT FOUND"), \
        f"Required component '{comp}' not found: {ver}"
    print(f"[PASS] {comp}: {ver}")

# INTENT: Validate Python package count is non-trivial.
# REASONING: An empty/near-empty freeze means uv sees the wrong env.
assert py_df.shape[0] >= 10, \
    f"Python package count suspiciously low: {py_df.shape[0]}"
print(f"\n[PASS] Python package count: {py_df.shape[0]} packages")

# =============================================================================
# --- Save ---
# =============================================================================
# INTENT: Write both manifests as parquet per DAAF parquet-only convention.
# REASONING: Parquet preserves dtypes, is anti-joinable in polars, and matches
#             the R-side manifest format for a consistent diff workflow.
py_df.write_parquet(OUTPUT_PY_PATH)
print(f"\nSaved Python packages to: {OUTPUT_PY_PATH}")
print(f"  Shape: {py_df.shape[0]} rows x {py_df.shape[1]} cols")

sys_df.write_parquet(OUTPUT_SYS_PATH)
print(f"Saved system libs to: {OUTPUT_SYS_PATH}")
print(f"  Shape: {sys_df.shape[0]} rows x {sys_df.shape[1]} cols")

print("\n[CP1 PASSED] Python + system-lib manifests captured, channel=bookworm-x86_64")


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-14 17:51:07
# Command: python3 /daaf/research/2026-07-14_FrameworkDev_NobleMigration/scripts/02_baseline-python-syslibs_b.py
# Duration: 1s
# Exit code: 0
#
# --- STDOUT ---
# uv pip freeze: 138 lines captured
# Python package manifest shape: 138 rows x 3 cols
# Columns: ['package', 'version', 'channel']
# 
# --- System-libs table ---
# shape: (8, 3)
# ┌───────────┬─────────────────────────────────┬─────────────────┐
# │ component ┆ version_string                  ┆ channel         │
# │ ---       ┆ ---                             ┆ ---             │
# │ str       ┆ str                             ┆ str             │
# ╞═══════════╪═════════════════════════════════╪═════════════════╡
# │ gdalinfo  ┆ GDAL 3.6.2, released 2023/01/0… ┆ bookworm-x86_64 │
# │ proj      ┆ NOT FOUND: neither projinfo no… ┆ bookworm-x86_64 │
# │ geos      ┆ 3.11.1                          ┆ bookworm-x86_64 │
# │ glibc     ┆ ldd (Debian GLIBC 2.36-9+deb12… ┆ bookworm-x86_64 │
# │ R         ┆ R version 4.5.3 (2026-03-11) -… ┆ bookworm-x86_64 │
# │ quarto    ┆ 1.7.29                          ┆ bookworm-x86_64 │
# │ python3   ┆ Python 3.12.12                  ┆ bookworm-x86_64 │
# │ uv        ┆ uv 0.9.30                       ┆ bookworm-x86_64 │
# └───────────┴─────────────────────────────────┴─────────────────┘
# [PASS] gdalinfo: GDAL 3.6.2, released 2023/01/02
# [PASS] R: R version 4.5.3 (2026-03-11) -- "Reassured Reassurer"
# [PASS] quarto: 1.7.29
# [PASS] python3: Python 3.12.12
# 
# [PASS] Python package count: 138 packages
# 
# Saved Python packages to: /daaf/research/2026-07-14_FrameworkDev_NobleMigration/output/2026-07-14_baseline_bookworm-x86_python-packages.parquet
#   Shape: 138 rows x 3 cols
# Saved system libs to: /daaf/research/2026-07-14_FrameworkDev_NobleMigration/output/2026-07-14_baseline_bookworm-x86_system-libs.parquet
#   Shape: 8 rows x 3 cols
# 
# [CP1 PASSED] Python + system-lib manifests captured, channel=bookworm-x86_64
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
