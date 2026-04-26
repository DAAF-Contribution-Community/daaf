#!/usr/bin/env bash
# ============================================================================
# DAAF Convention Lint — custom checks beyond ShellCheck / PSScriptAnalyzer
# ============================================================================
# Checks DAAF-specific patterns that standard linters do not cover:
#   1. Bash preamble: shebang + set -euo pipefail (or set -eu / trap ERR)
#   2. PowerShell preamble: $ErrorActionPreference set within first 30 lines
#   3. DAAF_NESTED consistency: host lifecycle scripts reference DAAF_NESTED
#   4. Numbered progress: host lifecycle scripts use [N/M] indicators (warn only)
#
# Usage:
#   bash tests/lint/check-daaf-conventions.sh
#   bash tests/lint/check-daaf-conventions.sh /path/to/repo
#
# Exit codes:
#   0 — all checks pass
#   1 — one or more checks failed
# ============================================================================

set -euo pipefail

REPO_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
FAIL_COUNT=0
WARN_COUNT=0

# Colors (disabled if NO_COLOR is set or stdout is not a terminal)
if [ -z "${NO_COLOR:-}" ] && [ -t 1 ]; then
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    GREEN='\033[0;32m'
    RESET='\033[0m'
else
    RED=''
    YELLOW=''
    GREEN=''
    RESET=''
fi

fail() {
    printf "${RED}FAIL${RESET}: %s\n" "$1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

warn() {
    printf "${YELLOW}WARN${RESET}: %s\n" "$1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

pass() {
    printf "${GREEN}PASS${RESET}: %s\n" "$1"
}

echo ""
echo "=========================================="
echo "  DAAF Convention Lint"
echo "=========================================="
echo ""
echo "Repository: ${REPO_ROOT}"
echo ""

# =====================================================================
# 1. Bash preamble check
# =====================================================================
echo "--- Bash preamble checks ---"

# Find all .sh files (excluding .git, node_modules, test libs)
while IFS= read -r -d '' shfile; do
    # Skip files inside .git, node_modules, test libraries, .claude/, and
    # scripts/ root-level utility scripts (which use specialized error
    # patterns — managed separately). scripts/host/ lifecycle scripts ARE
    # checked.
    case "${shfile}" in
        */.git/*|*/node_modules/*|*/libs/*|*/.claude/*|*/research/*) continue ;;
        */scripts/*.sh) # Skip root-level scripts/ utilities (not in subdirs)
            case "${shfile}" in
                */scripts/host/*) ;; # Allow host lifecycle scripts through
                *) continue ;;
            esac
            ;;
    esac

    filename=$(basename "${shfile}")
    relpath="${shfile#"${REPO_ROOT}/"}"

    # Check shebang (first line)
    # Accept: #!/usr/bin/env bash, #!/usr/bin/env bats, #!/bin/bash, #!/bin/sh
    first_line=$(head -1 "${shfile}")
    case "${first_line}" in
        "#!/usr/bin/env bash"|"#!/usr/bin/env bats"|"#!/bin/bash"|"#!/bin/sh")
            ;; # Valid shebang
        *)
            fail "${relpath}: missing or non-standard shebang (got: '${first_line}')"
            ;;
    esac

    # Check for error handling in first 10 non-comment, non-blank code lines.
    # Counting code lines (not raw lines) is robust against variable-length
    # comment headers — even a 100-line documentation block won't cause a
    # false failure as long as error handling appears early in actual code.
    # Accept any of:
    #   - set -euo pipefail  (preferred)
    #   - set -eu            (minimum)
    #   - set -o pipefail    (used by some utility scripts)
    #   - trap ... ERR       (fail-closed pattern used by hooks)
    code_lines=$(grep -v '^\s*#' "${shfile}" | grep -v '^\s*$' | head -10)
    if ! echo "${code_lines}" | grep -qE 'set -e|trap .* ERR'; then
        # Allow BATS test files and test helpers to skip strict mode
        case "${filename}" in
            *.bats|test_helper.bash) ;;
            *)
                fail "${relpath}: missing error handling (set -e / set -euo pipefail / trap ERR) in first 10 code lines"
                ;;
        esac
    fi
done < <(find "${REPO_ROOT}" -name '*.sh' -type f -not -path '*/.git/*' -print0)

echo ""

# =====================================================================
# 2. PowerShell preamble check
# =====================================================================
echo "--- PowerShell preamble checks ---"

while IFS= read -r -d '' ps1file; do
    case "${ps1file}" in
        */.git/*|*/node_modules/*|*/libs/*) continue ;;
    esac

    relpath="${ps1file#"${REPO_ROOT}/"}"
    filename=$(basename "${ps1file}")

    # Skip test files (*.Tests.ps1) and helpers (TestHelper.ps1)
    case "${filename}" in
        *.Tests.ps1|TestHelper.ps1) continue ;;
    esac

    # Check for $ErrorActionPreference within first 30 lines.
    # DAAF PS1 scripts have large comment headers (15-20 lines), so the
    # preamble typically appears around line 19-20.
    head_lines=$(head -30 "${ps1file}")
    if ! echo "${head_lines}" | grep -q 'ErrorActionPreference'; then
        fail "${relpath}: missing '\$ErrorActionPreference' set within first 30 lines"
    fi
done < <(find "${REPO_ROOT}" -name '*.ps1' -type f -not -path '*/.git/*' -print0)

echo ""

# =====================================================================
# 3. DAAF_NESTED consistency
# =====================================================================
echo "--- DAAF_NESTED consistency checks ---"

# Host lifecycle .sh scripts (scripts/host/ — compose with each other)
for shfile in "${REPO_ROOT}"/scripts/host/*.sh; do
    [ -f "${shfile}" ] || continue
    filename=$(basename "${shfile}")

    if ! grep -q 'DAAF_NESTED' "${shfile}"; then
        fail "scripts/host/${filename}: lifecycle script does not reference DAAF_NESTED"
    else
        pass "scripts/host/${filename}: references DAAF_NESTED"
    fi
done

# Host lifecycle .ps1 scripts
for ps1file in "${REPO_ROOT}"/scripts/host/*.ps1; do
    [ -f "${ps1file}" ] || continue
    filename=$(basename "${ps1file}")

    if ! grep -q 'DAAF_NESTED' "${ps1file}"; then
        fail "scripts/host/${filename}: lifecycle script does not reference DAAF_NESTED"
    else
        pass "scripts/host/${filename}: references DAAF_NESTED"
    fi
done

echo ""

# =====================================================================
# 4. Numbered progress pattern (warn only)
# =====================================================================
echo "--- Progress indicator checks (warnings only) ---"

for shfile in "${REPO_ROOT}"/scripts/host/*.sh; do
    [ -f "${shfile}" ] || continue
    filename=$(basename "${shfile}")

    if ! grep -qE '\[[0-9]+/[0-9]+\]' "${shfile}"; then
        warn "scripts/host/${filename}: no [N/M] progress indicators found"
    else
        pass "scripts/host/${filename}: has [N/M] progress indicators"
    fi
done

for ps1file in "${REPO_ROOT}"/scripts/host/*.ps1; do
    [ -f "${ps1file}" ] || continue
    filename=$(basename "${ps1file}")

    if ! grep -qE '\[[0-9]+/[0-9]+\]' "${ps1file}"; then
        warn "scripts/host/${filename}: no [N/M] progress indicators found"
    else
        pass "scripts/host/${filename}: has [N/M] progress indicators"
    fi
done

echo ""

# =====================================================================
# Summary
# =====================================================================
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""
echo "  Failures: ${FAIL_COUNT}"
echo "  Warnings: ${WARN_COUNT}"
echo ""

if [ "${FAIL_COUNT}" -gt 0 ]; then
    printf "${RED}Convention lint FAILED with ${FAIL_COUNT} error(s).${RESET}\n"
    exit 1
else
    printf "${GREEN}Convention lint passed (${WARN_COUNT} warning(s)).${RESET}\n"
    exit 0
fi
