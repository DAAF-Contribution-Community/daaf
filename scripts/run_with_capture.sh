#!/usr/bin/env bash
# =============================================================================
# run_with_capture.sh - Execute Python script with output capture and logging
# =============================================================================
#
# Usage: ./scripts/run_with_capture.sh <script_path>
#
# This script:
# 1. Executes the Python script with output capture
# 2. Records timestamp, duration, and exit code
# 3. Appends the execution log to the script file (if successful or failed)
# 4. Returns the script's exit code
#
# Example:
#   ./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd.py
#
# =============================================================================

# -u: catch unset variables; -o pipefail: detect pipeline failures
# Deliberately omit -e: this script must capture non-zero exit codes from
# the Python script it executes, not die on them.
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

# Check if script already has an execution log
if grep -q "^# EXECUTION LOG" "$SCRIPT_PATH"; then
    echo "WARNING: Script already has an execution log."
    echo "If you need to re-run with fixes, create a new version:"
    echo "  cp $SCRIPT_PATH ${SCRIPT_PATH%.py}_a.py"
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
python3 "$SCRIPT_PATH" 2>&1 | tee "$TEMP_LOG"
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
# Command: python3 $SCRIPT_PATH
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
    echo "     cp $SCRIPT_PATH ${SCRIPT_PATH%.py}_a.py"
    echo "  3. Apply fixes to the new version"
    echo "  4. Run the new version:"
    echo "     $0 ${SCRIPT_PATH%.py}_a.py"
fi

# Cleanup
rm -f "$TEMP_LOG"

exit $EXIT_CODE
