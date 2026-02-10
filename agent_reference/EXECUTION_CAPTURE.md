# Execution Capture Reference

This document provides utilities and patterns for the file-first execution workflow. Use these tools to execute scripts, capture output, append logs, and manage script versions.

---

## Overview

The file-first workflow requires:
1. Writing Python code to a script file before execution
2. Executing via Bash with output capture
3. Appending the captured output to the script as comments
4. Creating versioned copies for any fixes (never modifying after append)

This document provides the utilities to support this workflow.

---

## Bash Execution Wrapper

Save this script as `scripts/run_with_capture.sh` in each project:

```bash
#!/bin/bash
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

set -o pipefail

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

# Execute with timing
START_TIME=$(date +%s.%N)
python "$SCRIPT_PATH" 2>&1 | tee "$TEMP_LOG"
EXIT_CODE=${PIPESTATUS[0]}
END_TIME=$(date +%s.%N)
DURATION=$(echo "$END_TIME - $START_TIME" | bc)

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
# Command: python $SCRIPT_PATH
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
```

### Usage

```bash
# Make the wrapper executable (one time)
chmod +x scripts/run_with_capture.sh

# Execute a script
./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd.py

# If it fails, create a versioned copy and fix
cp scripts/stage5_fetch/01_fetch-ccd.py scripts/stage5_fetch/01_fetch-ccd_a.py
# Edit 01_fetch-ccd_a.py with fixes
./scripts/run_with_capture.sh scripts/stage5_fetch/01_fetch-ccd_a.py
```

---

## Execution Capture Approach

All execution capture is handled by the bash wrapper `run_with_capture.sh` (see above).

**Do NOT create:**
- A `validation.py` module
- Python utility functions for execution capture
- Helper functions for log appending or script versioning

Script versioning (creating `_a.py`, `_b.py` copies) is done by the orchestrator/agent using bash commands (e.g., `cp script.py script_a.py`), not by Python utility functions. Checking whether a script already has an execution log, appending output, and managing versions are all handled by the bash wrapper or by straightforward inline shell commands.

---

## Marimo Integration

Notebook assembly is handled by the **notebook-assembler** agent during Stage 9. The agent copies successful script contents verbatim into marimo cells. There is no Python utility function for this -- the agent performs the assembly directly.

### Marimo Notebook Structure

Every marimo notebook ends with the following boilerplate. This is auto-generated by the marimo framework and is an exception to the "no `if __name__` blocks" rule:

```python
# NOTE: This is marimo framework boilerplate, auto-generated by marimo.
# It is NOT user-written code. This is the one permitted exception to
# the project rule against if __name__ == "__main__" patterns.
if __name__ == "__main__":
    app.run()
```

See `agents/notebook-assembler.md` for the complete notebook compilation protocol.

---

## Workflow Summary

### For Each Task in the Transformation Sequence:

1. **Write the script:**
   ```python
   # Use Write tool to create scripts/stage{N}_{type}/{step}_{task}.py
   # Follow SCRIPT_TEMPLATE.md format
   ```

2. **Execute with capture:**
   ```bash
   cd /daaf/research/[project]/
   ./scripts/run_with_capture.sh scripts/stage{N}_{type}/{step}_{task}.py
   ```

3. **If failed:**
   ```bash
   # Script already has failed output appended
   # Create versioned copy
   cp scripts/stage{N}_{type}/{step}_{task}.py scripts/stage{N}_{type}/{step}_{task}_a.py
   # Edit _a.py with fixes
   # Run _a.py
   ./scripts/run_with_capture.sh scripts/stage{N}_{type}/{step}_{task}_a.py
   ```

4. **Commit all versions:**
   ```bash
   git add scripts/stage{N}_{type}/{step}_{task}*.py
   git commit -m "feat(stage{N}-{step}): {description}

   - Final version: {step}_{task}_b.py
   - Validation: CP{N} PASSED
   - Revisions: 2 (key mismatch, type error)

   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

5. **For Stage 9:** The notebook-assembler agent compiles final successful script versions into the Marimo notebook.

---

## Critical Rules

| Rule | Rationale |
|------|-----------|
| **NEVER execute before writing to file** | Scripts are the primary artifact |
| **NEVER modify after appending log** | The log documents that exact code |
| **ALWAYS version for fixes** | Preserves full history |
| **ALWAYS commit all versions** | Audit trail of evolution |
| **ALWAYS use final version in notebook** | Notebook shows what succeeded |
