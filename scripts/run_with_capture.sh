#!/usr/bin/env bash
# =============================================================================
# run_with_capture.sh - Execute script with output capture and logging
# =============================================================================
#
# Usage: ./scripts/run_with_capture.sh <script_path>
#
# Supported languages: Python (.py), R (.R)
#
# This script:
# 1. Detects the script language from the file extension
# 2. Executes the script with the appropriate interpreter
# 3. Records timestamp, duration, and exit code
# 4. Appends the execution log to the script file (if successful or failed)
# 5. Returns the script's exit code
#
# Examples:
#   ./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd.py
#   ./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd.R
#
# =============================================================================

# -u: catch unset variables; -o pipefail: detect pipeline failures
# Deliberately omit -e: this script must capture non-zero exit codes from
# the target script it executes, not die on them.
set -uo pipefail

SCRIPT_PATH="$1"

if [ -z "$SCRIPT_PATH" ]; then
    echo "Usage: $0 <script_path>"
    echo "Example: $0 scripts/stage5_fetch/01_fetch-ccd.py"
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script not found: $SCRIPT_PATH"
    exit 1
fi

# Detect language from file extension
EXT="${SCRIPT_PATH##*.}"
case "$EXT" in
    py)
        INTERPRETER="python3"
        ;;
    R|r)
        INTERPRETER="Rscript"
        ;;
    *)
        echo "Error: Unsupported file extension: .$EXT"
        echo "Supported: .py (Python), .R (R)"
        exit 1
        ;;
esac

# Language-aware version suffix
BASE="${SCRIPT_PATH%.${EXT}}"

# Check if script already has an execution log
if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "WARNING: Script already has an execution log."
    echo "If you need to re-run with fixes, create a new version:"
    echo "  bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH ${BASE}_a.${EXT}"
    echo "Then run the new version."
    exit 1
fi

# --- Pre-execution package-install content scan ------------------------------
# The container environment is defined entirely by the Dockerfile; a package
# installed at runtime creates unreproducible drift a rebuild silently reverts
# (see CLAUDE.md § Boundaries & Safety > Runtime Package Installation). The
# bash-safety.sh §8 hook blocks command-line installs, but it CANNOT see an
# install call written INSIDE a script — the dominant path for R
# (install.packages()) and a real path for Python (os.system("pip install ...")).
# This wrapper is the only chokepoint that sees the script body, so it scans it
# before executing. Full-line comments are excluded so a commented-out example
# does not false-block; an inline TRAILING comment that contains a token IS an
# accepted false positive (rare, and erring toward blocking is the safe default
# for a reproducibility guard). Scan tokens are extension-specific: R is
# case-sensitive so its tokens match case-sensitively (fewer false positives);
# Python tokens match case-insensitively and cover the common string call forms
# (os.system/subprocess("pip install ..."), pipx/uv subcommands) and the
# subprocess-LIST forms (["pip","install",...], ["uv","add",...],
# ["pipx","install",...]). ACCEPTED RESIDUALS (Python): exotic forms are not
# decoded — a package name built by variable interpolation or string-join, an
# importlib/__import__("pip")._internal call, uv/pipx spelled via an absolute
# path or a shell-var indirection, or an install verb split across list elements
# with unusual whitespace. These mirror the shell-hook §8 residual class and are
# accepted (the hook and, for coding agents, enforce-file-first.sh remain in
# depth behind this scan).
if [ "$EXT" = "py" ]; then
    SCAN_TOKENS="pip3? install|pip3?['\"], *['\"]install|pipx (install|run)|pipx['\"], *['\"](install|run)|uv (pip install|add|sync|tool install)|uv['\"], *['\"](add|sync|pip|tool)|easy_install|conda install"
    INSTALL_HITS=$(grep -inE "$SCAN_TOKENS" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
else
    SCAN_TOKENS='install\.packages\(|update\.packages\(|remove\.packages\(|remotes::install_|devtools::install_|install_(github|gitlab|bitbucket|cran|version|local|url|git|svn|bioc|dev)\(|pak::(pak|pkg_install)\(|pkg_install\(|renv::(install|restore|update|rebuild)\(|BiocManager::install\(|biocLite\('
    INSTALL_HITS=$(grep -nE "$SCAN_TOKENS" "$SCRIPT_PATH" | grep -vE '^[0-9]+:[[:space:]]*#' || true)
fi

if [ -n "$INSTALL_HITS" ]; then
    echo "============================================================" >&2
    echo "BLOCKED: run_with_capture.sh — runtime package install detected" >&2
    echo "============================================================" >&2
    echo "Offending line(s) in $SCRIPT_PATH:" >&2
    echo "$INSTALL_HITS" >&2
    echo "" >&2
    echo "WHY: This container's environment is defined entirely by its" >&2
    echo "Dockerfile. A package installed at runtime creates unreproducible" >&2
    echo "drift that a rebuild silently reverts (see CLAUDE.md § Boundaries &" >&2
    echo "Safety > Runtime Package Installation). A script must not install" >&2
    echo "packages as a side effect of being executed." >&2
    echo "" >&2
    echo "WHAT TO DO:" >&2
    echo "  1. Remove the install call from the script." >&2
    echo "  2. If the package is genuinely missing, STOP and report to the" >&2
    echo "     orchestrator/user so it can be added to the Dockerfile (the" >&2
    echo "     user additions block near the end) and the container rebuilt:" >&2
    echo "     exit the container, then run 'bash rebuild_daaf.sh'" >&2
    echo "     ('.\\rebuild_daaf.ps1' on Windows) from the daaf-docker folder." >&2
    echo "" >&2
    echo "NOTE: NO execution log was appended — immutable script versioning has" >&2
    echo "NOT engaged. You may edit THIS script file in place and re-run it once" >&2
    echo "the install call is removed (no _a/_b version needed)." >&2
    echo "============================================================" >&2
    exit 3
fi

# Create temp file for output
TEMP_LOG=$(mktemp)
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

echo "============================================================"
echo "EXECUTING: $SCRIPT_PATH"
echo "Started: $TIMESTAMP"
echo "============================================================"
echo ""

# Execute with timing (integer seconds — avoids bc dependency and macOS date +%N incompatibility)
START_TIME=$(date +%s)
$INTERPRETER "$SCRIPT_PATH" 2>&1 | tee "$TEMP_LOG"
EXIT_CODE=${PIPESTATUS[0]}
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "============================================================"
echo "EXECUTION COMPLETE"
echo "Exit code: $EXIT_CODE"
echo "Duration: ${DURATION}s"
echo "============================================================"

# Append execution log to script
echo ""
echo "Appending execution log to script..."

cat >> "$SCRIPT_PATH" << EOF


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: $TIMESTAMP
# Command: $INTERPRETER $SCRIPT_PATH
# Duration: ${DURATION}s
# Exit code: $EXIT_CODE
#
# --- STDOUT ---
$(sed 's/^/# /' "$TEMP_LOG")
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
EOF

echo "Execution log appended to: $SCRIPT_PATH"

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "SUCCESS: Script passed."
else
    echo ""
    echo "FAILED: Script returned exit code $EXIT_CODE"
    echo ""
    echo "Next steps:"
    echo "  1. Review the execution log appended to the script"
    echo "  2. Create a clean revision (strips the appended execution log):"
    echo "     bash /daaf/scripts/create_script_revision.sh $SCRIPT_PATH ${BASE}_a.${EXT}"
    echo "  3. Apply fixes to the new version"
    echo "  4. Run the new version:"
    echo "     $0 ${BASE}_a.${EXT}"
fi

# Cleanup
rm -f "$TEMP_LOG"

exit $EXIT_CODE
