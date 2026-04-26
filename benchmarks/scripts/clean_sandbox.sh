#!/usr/bin/env bash
# clean_sandbox.sh — Reset benchmark sandbox state between runs.
#
# Clears any files created by previous benchmark test cases in the
# sandbox area so each run starts from a clean state. Does NOT touch
# audit.jsonl or session archives (those are filtered by timestamp).
#
# Usage: bash benchmarks/scripts/clean_sandbox.sh [base_dir]

set -euo pipefail

BASE_DIR="${1:-/daaf}"
SANDBOX_DIR="${BASE_DIR}/benchmarks/_sandbox"

# Create sandbox if it does not exist
mkdir -p "$SANDBOX_DIR"

# Remove all contents but keep the directory
if [ -d "$SANDBOX_DIR" ]; then
    find "$SANDBOX_DIR" -mindepth 1 -delete 2>/dev/null || true
    echo "Sandbox cleaned: ${SANDBOX_DIR}"
else
    echo "Sandbox directory created: ${SANDBOX_DIR}"
fi
