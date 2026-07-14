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
#           projinfo may not accept --version; fall back to `proj` (no args).

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
# ASSUMES: uv is on PATH; the virtual/system environment accessible to uv
#           contains the packages we care about (UV_SYSTEM_PYTHON=1 is set in
#           the container so uv operates on the system Python environment).

result_freeze = subprocess.run(
    ["uv", "pip", "freeze"],
    capture_output=True, text=True
)
freeze_lines = result_freeze.stdout.strip().splitlines()
print(f"uv pip freeze: {len(freeze_lines)} lines captured")

# --- Transform: parse freeze lines ---
# INTENT: Split each `package==version` line into two columns.
# REASONING: == is the canonical pip freeze separator. Lines without == are
#             kept with their raw text in `version` so the row is not lost;
#             these are rare (editable installs) but must not raise exceptions.
records = []
for line in freeze_lines:
    line = line.strip()
    if not line:
        continue
    if "==" in line:
        pkg, ver = line.split("==", 1)
        records.append({"package": pkg.strip(), "version": ver.strip()})
    else:
        # Non-== line: keep verbatim in version, package = raw line
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
#         components that are NOT visible in either pip freeze or R packages.
# REASONING: GDAL, PROJ, GEOS, and glibc are the system libraries with the
#             largest version jumps in the bookworm→noble migration (GDAL 3.6→3.8,
#             PROJ stays, glibc 2.36→2.39). Quarto and R are captured here as
#             cross-checks against the R-side manifest. `uv --version` rounds out
#             the Python toolchain anchor.
# ASSUMES: Each command either exits 0 with version on stdout or exits non-zero
#           with a version banner on stderr. Individual failures record
#           "NOT FOUND: <error>" rather than aborting the script; only the four
#           components named in the assertion block are required.

def capture_version(cmd, use_stderr=False):
    """Run cmd list, return first non-empty line of stdout (or stderr if
    use_stderr=True). On error return 'NOT FOUND: <msg>'."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        stream = r.stderr if use_stderr else r.stdout
        # Take first non-blank line from preferred stream; fall back to other.
        lines = [l.strip() for l in stream.splitlines() if l.strip()]
        if not lines:
            fallback = r.stderr if not use_stderr else r.stdout
            lines = [l.strip() for l in fallback.splitlines() if l.strip()]
        return lines[0] if lines else f"NOT FOUND: empty output (exit {r.returncode})"
    except FileNotFoundError:
        return f"NOT FOUND: command not found ({cmd[0]})"
    except Exception as e:
        return f"NOT FOUND: {e}"

# --- projinfo fallback ---
# INTENT: projinfo --version works on newer PROJ; fall back to `proj` (no args)
#         which prints the version banner to stderr on bookworm PROJ 9.x.
# REASONING: Different PROJ versions expose version differently; we probe both
#             and use whichever succeeds first. Both calls are wrapped in
#             try/except because either binary may simply not exist in this image
#             (bookworm ships proj but projinfo is in a separate package).
# FIX (v_a): Original crashed with bare FileNotFoundError because projinfo was
#             called outside try/except. Now both attempts are fully guarded.
def proj_version():
    try:
        r = subprocess.run(["projinfo", "--version"], capture_output=True, text=True, timeout=10)
        lines = [l.strip() for l in (r.stdout + r.stderr).splitlines() if l.strip()]
        if lines and r.returncode == 0:
            return lines[0]
    except FileNotFoundError:
        pass  # projinfo not installed; fall through to proj
    except Exception:
        pass
    # Fallback: `proj` with no args prints banner to stderr
    try:
        r2 = subprocess.run(["proj"], capture_output=True, text=True, timeout=10)
        lines2 = [l.strip() for l in (r2.stdout + r2.stderr).splitlines() if l.strip()]
        return lines2[0] if lines2 else "NOT FOUND: proj/projinfo both failed"
    except FileNotFoundError:
        return "NOT FOUND: neither projinfo nor proj found on PATH"
    except Exception as e:
        return f"NOT FOUND: {e}"

# INTENT: Collect one version string per component in a consistent order.
# REASONING: Components are ordered by migration risk (geospatial system libs
#             first, then language runtimes, then toolchain utilities).
sys_components = [
    ("gdalinfo",    capture_version(["gdalinfo", "--version"])),
    ("proj",        proj_version()),
    ("geos",        capture_version(["geos-config", "--version"])),
    ("glibc",       capture_version(["ldd", "--version"])),          # first line = glibc ver
    ("R",           capture_version(["R", "--version"])),            # first line = R ver
    ("quarto",      capture_version(["quarto", "--version"])),
    ("python3",     capture_version(["python3", "--version"])),
    ("uv",          capture_version(["uv", "--version"])),
]

sys_df = pl.DataFrame(
    {"component": [c for c, _ in sys_components],
     "version_string": [v for _, v in sys_components]}
).with_columns(
    pl.lit("bookworm-x86_64").alias("channel")
)

# =============================================================================
# --- Validate ---
# =============================================================================
# INTENT: Assert that all four required system components were found.
# REASONING: gdalinfo, R, quarto, and python3 are the components most critical
#             for the migration — their absence would indicate a broken image
#             state that invalidates the baseline manifest.
print("\n--- System-libs table ---")
print(sys_df)

required_found = ["gdalinfo", "R", "quarto", "python3"]
for comp in required_found:
    ver = sys_df.filter(pl.col("component") == comp)["version_string"][0]
    assert not ver.startswith("NOT FOUND"), \
        f"Required component '{comp}' not found: {ver}"
    print(f"[PASS] {comp}: {ver}")

# INTENT: Validate Python package count is non-trivial.
# REASONING: An empty or near-empty freeze output would indicate uv is not
#             seeing the installed packages (wrong env), making the manifest useless.
assert py_df.shape[0] >= 10, \
    f"Python package count suspiciously low: {py_df.shape[0]}"
print(f"\n[PASS] Python package count: {py_df.shape[0]} packages")

# =============================================================================
# --- Save ---
# =============================================================================
# INTENT: Write both manifests as parquet per DAAF convention.
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
# Executed: 2026-07-14 17:49:48
# Command: python3 /daaf/research/2026-07-14_FrameworkDev_NobleMigration/scripts/02_baseline-python-syslibs.py
# Duration: 0s
# Exit code: 1
#
# --- STDOUT ---
# uv pip freeze: 138 lines captured
# Python package manifest shape: 138 rows x 3 cols
# Columns: ['package', 'version', 'channel']
# Traceback (most recent call last):
#   File "/daaf/research/2026-07-14_FrameworkDev_NobleMigration/scripts/02_baseline-python-syslibs.py", line 126, in <module>
#     ("proj",        proj_version()),
#                     ^^^^^^^^^^^^^^
#   File "/daaf/research/2026-07-14_FrameworkDev_NobleMigration/scripts/02_baseline-python-syslibs.py", line 112, in proj_version
#     r = subprocess.run(["projinfo", "--version"], capture_output=True, text=True, timeout=10)
#         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/subprocess.py", line 548, in run
#     with Popen(*popenargs, **kwargs) as process:
#          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/subprocess.py", line 1026, in __init__
#     self._execute_child(args, executable, preexec_fn, close_fds,
#   File "/usr/local/lib/python3.12/subprocess.py", line 1955, in _execute_child
#     raise child_exception_type(errno_num, err_msg, err_filename)
# FileNotFoundError: [Errno 2] No such file or directory: 'projinfo'
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
