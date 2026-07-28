#!/usr/bin/env bash
set -euo pipefail

# Thin operator entry point for the route-bound GPT service-tier controller.
if ! command -v readlink >/dev/null 2>&1; then
    echo "ERROR: readlink is required but was not found." >&2
    echo "  Fix: run this command inside the DAAF container." >&2
    exit 30
fi
SCRIPT_PATH=""
if ! SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"; then
    echo "ERROR: could not resolve the GPT Fast controller path safely." >&2
    echo "  Fix: invoke the checked-in wrapper from the DAAF installation." >&2
    exit 20
fi
readonly SCRIPT_PATH
SCRIPT_DIR=""
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd -P)"
readonly SCRIPT_DIR
readonly PYTHON_CLI="${SCRIPT_DIR}/gpt_fast.py"

if [ "$#" -ne 1 ]; then
    echo "Usage: bash ${SCRIPT_DIR}/gpt_fast.sh {on|off|status}" >&2
    exit 20
fi

case "$1" in
    on|off|status)
        ;;
    *)
        echo "ERROR: unsupported command." >&2
        echo "  Fix: use exactly one of: on, off, status." >&2
        exit 20
        ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required but was not found." >&2
    echo "  Fix: run this command inside the DAAF container." >&2
    exit 30
fi

exec python3 "$PYTHON_CLI" "$1"
