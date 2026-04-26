#!/usr/bin/env bash
# run_benchmark.sh — Entry point for DAAF Framework Adherence Benchmarks.
#
# Runs the benchmark harness from within the DAAF container.
# All arguments are forwarded to the Python runner.
#
# Usage:
#   bash benchmarks/scripts/run_benchmark.sh --category mode_classification
#   bash benchmarks/scripts/run_benchmark.sh --model claude-haiku-4-5-20251001 --test-id mc-01
#   bash benchmarks/scripts/run_benchmark.sh --dry-run
#
# From host (via docker exec):
#   docker exec daaf-daaf-docker-1 bash /daaf/benchmarks/scripts/run_benchmark.sh --dry-run

set -euo pipefail

BASE_DIR="${DAAF_BASE_DIR:-/daaf}"

# Ensure we are in the right directory
cd "$BASE_DIR"

# Clean sandbox before run
bash "${BASE_DIR}/benchmarks/scripts/clean_sandbox.sh" "$BASE_DIR"

# Run the benchmark harness
python3 -m benchmarks.harness.runner --base-dir "$BASE_DIR" "$@"
