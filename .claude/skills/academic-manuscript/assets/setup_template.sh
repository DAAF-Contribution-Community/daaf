#!/usr/bin/env bash
set -euo pipefail
# =============================================================================
# code/00_setup.sh -- build the Python environment for this replication package
#
# >>> TEMPLATE NOTE (removed by the package assembler)
# TEMPLATE (academic-manuscript skill, assets/setup_template.sh). The package
# assembler copies it to <package>/code/00_setup.sh.
# <<< TEMPLATE NOTE
# The Windows twin is code/00_setup.ps1.
#
# RUNS ON THE REPLICATOR'S MACHINE ONLY. It is never executed inside DAAF:
# installing packages at runtime there is prohibited (the container is defined by
# its Dockerfile), so it refuses to run when it detects a DAAF container. DAAF's
# own proof run checks environment equivalence instead (main.py compares
# installed versions with requirements-lock.txt).
#
# What it does:
#   1. Finds a Python 3.12 interpreter (override with PYTHON_BIN=/path/to/python).
#   2. Creates a virtual environment in <package>/.venv (AEA asks for a native
#      venv or conda environment with top-level requirements specified).
#   3. Installs the exact solved package set from requirements-lock.txt.
#      requirements.txt lists only the top-level packages the code imports.
#
# Usage (from anywhere):
#   bash code/00_setup.sh
#   PYTHON_BIN=/usr/local/bin/python3.12 bash code/00_setup.sh
# Then run the package:
#   .venv/bin/python main.py
# =============================================================================

# INTENT: resolve the package root from this file's location, not the caller's CWD.
# ASSUMES: this file lives at <package>/code/00_setup.sh.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly LOCK_FILE="${ROOT}/requirements-lock.txt"
readonly VENV_DIR="${ROOT}/.venv"
readonly EXPECTED_MINOR="3.12"

# INTENT: refuse to install packages inside a DAAF container.
# REASONING: DAAF forbids runtime installs; /etc/daaf/ubuntu-snapshot is written by
#   the DAAF image build, so its presence identifies the container.
if [ -e /etc/daaf/ubuntu-snapshot ]; then
    echo "REFUSED: this looks like a DAAF container. Do not install packages here." >&2
    echo "DAAF verifies the package by comparing installed versions with the lock file instead." >&2
    exit 3
fi

if [ ! -f "${LOCK_FILE}" ]; then
    echo "ERROR: ${LOCK_FILE} not found. Run this script from an unmodified package." >&2
    exit 1
fi

# INTENT: pick an interpreter; prefer an explicit override, then python3.12, then python3.
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "${PYTHON_BIN}" ]; then
    if command -v python3.12 >/dev/null 2>&1; then
        PYTHON_BIN="python3.12"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        echo "ERROR: no Python interpreter found. Install Python ${EXPECTED_MINOR} and retry," >&2
        echo "or set PYTHON_BIN to its path." >&2
        exit 1
    fi
fi

found_minor="$("${PYTHON_BIN}" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [ "${found_minor}" != "${EXPECTED_MINOR}" ]; then
    echo "WARNING: this package was verified with Python ${EXPECTED_MINOR}; ${PYTHON_BIN} is ${found_minor}." >&2
    echo "Results may differ. Set PYTHON_BIN to a Python ${EXPECTED_MINOR} interpreter if you can." >&2
fi

if [ -e "${VENV_DIR}" ]; then
    echo "Using existing environment: ${VENV_DIR}"
else
    echo "Creating virtual environment: ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "Installing the locked package set from requirements-lock.txt"
"${VENV_DIR}/bin/python" -m pip install --requirement "${LOCK_FILE}"

echo ""
echo "Setup complete. Run the package with:"
echo "  \"${VENV_DIR}/bin/python\" \"${ROOT}/main.py\""
