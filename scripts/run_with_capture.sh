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
    echo "  cp $SCRIPT_PATH ${BASE}_a.${EXT}"
    echo "Then run the new version."
    exit 1
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
    echo "SUCCESS: Script passed. Ready to commit."
else
    echo ""
    echo "FAILED: Script returned exit code $EXIT_CODE"
    echo ""
    echo "Next steps:"
    echo "  1. Review the execution log appended to the script"
    echo "  2. Create a versioned copy for fixes:"
    echo "     cp $SCRIPT_PATH ${BASE}_a.${EXT}"
    echo "  3. Apply fixes to the new version"
    echo "  4. Run the new version:"
    echo "     $0 ${BASE}_a.${EXT}"
fi

# Cleanup
rm -f "$TEMP_LOG"

exit $EXIT_CODE
