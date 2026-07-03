#!/usr/bin/env bash
# ============================================================================
# DAAF Convention Lint — custom checks beyond ShellCheck / PSScriptAnalyzer
# ============================================================================
# Checks DAAF-specific patterns that standard linters do not cover:
#   1. Bash preamble: shebang + set -euo pipefail (or set -eu / trap ERR)
#   2. PowerShell preamble: $ErrorActionPreference in first 15 code lines
#   3. DAAF_NESTED consistency: host lifecycle scripts reference DAAF_NESTED
#   4. Numbered progress: host lifecycle scripts use [N/M] indicators (warn only)
#   5. Bash 3.2 portability: host scripts avoid Bash-4.x-only constructs
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
    #   - set -Eeuo pipefail (errexit + ERR-trap propagation into functions)
    #   - set -eu            (minimum)
    #   - set -o pipefail    (used by some utility scripts)
    #   - trap ... ERR       (fail-closed pattern used by hooks)
    code_lines=$(awk '!/^\s*#/ && !/^\s*$/ { print; if (++n == 10) exit }' "${shfile}")
    if ! echo "${code_lines}" | grep -qE 'set -[A-Za-z]*e|trap .* ERR'; then
        # Allow BATS test files, test helpers, and sourced function libraries
        # (*_lib.sh) to skip strict mode — a sourced library must not change
        # the caller's shell options, so it correctly has no set -e of its own.
        case "${filename}" in
            *.bats|test_helper.bash|*_lib.sh) ;;
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

    # Skip test files (*.Tests.ps1), helpers (TestHelper.ps1), and sourced
    # function libraries (*_lib.ps1). A dot-sourced library must not force
    # $ErrorActionPreference on its caller -- its functions save/restore EAP
    # locally instead -- mirroring the *_lib.sh exemption in the Bash checks.
    case "${filename}" in
        *.Tests.ps1|TestHelper.ps1|*_lib.ps1) continue ;;
    esac

    # Check for $ErrorActionPreference in first 15 non-comment, non-blank code lines.
    # PowerShell comments start with # (like bash). Counting code lines is robust
    # against variable-length comment headers and dry-run blocks.
    code_lines=$(awk '!/^\s*#/ && !/^\s*$/ { print; if (++n == 15) exit }' "${ps1file}")
    if ! echo "${code_lines}" | grep -q 'ErrorActionPreference'; then
        fail "${relpath}: missing '\$ErrorActionPreference' in first 15 code lines"
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

    # Sourced function libraries (*_lib.sh) are not lifecycle scripts: they
    # define functions only, never execute nested scripts, and have no
    # pause-on-exit trap — the DAAF_NESTED convention does not apply.
    case "${filename}" in
        *_lib.sh) continue ;;
    esac

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

    # Sourced function libraries (*_lib.ps1) are not lifecycle scripts: they
    # define functions only, never execute nested scripts, and have no
    # pause-on-exit prompt -- the DAAF_NESTED convention does not apply
    # (mirrors the *_lib.sh exemption above).
    case "${filename}" in
        *_lib.ps1) continue ;;
    esac

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
# 5. Bash 3.2 portability (host-executed scripts)
# =====================================================================
echo "--- Bash 3.2 portability checks (host scripts) ---"

# Scripts under scripts/host/ run on the *user's own machine*, not inside the
# container. On macOS the default /bin/bash is 3.2.57 (Apple ships it rather than
# a GPLv3 build), and documented usage is `bash daaf.sh` -> /bin/bash. So host
# scripts must avoid constructs introduced after Bash 3.2. ShellCheck cannot
# catch this class (it has no version pin and does not warn on, e.g., arr[-1]),
# so this grep-based gate is the practical static defense. See the
# shell-scripting skill (bash-standards.md > Host-Script Portability) for the
# full standard and reasoning.
#
# Banned constructs and the Bash version that introduced each:
#   ${arr[-1]}      negative array subscript      (4.3)
#   declare -A      associative arrays            (4.0)
#   mapfile / readarray  read lines into array    (4.0)
#   ${var,,} ${var^^}  case modification          (4.0)
#   &>>            append-redirect stdout+stderr  (4.0)
#   coproc         coprocesses                    (4.0)
#
# We strip comments before matching so that documentation mentioning these
# constructs (e.g., an "# ASSUMES: no mapfile" note) does not trip the check.
# The regexes target the actual syntax, not prose.

check_bash32_portability() {
    local file="$1"
    local relpath="$2"
    local found=0

    # Strip full-line and trailing comments to avoid false positives on prose.
    # This is a heuristic (a '#' inside a string literal would also be stripped),
    # which is acceptable here: it only ever *reduces* matches, so it cannot
    # produce a false failure — at worst it misses a construct hidden after a
    # quoted '#', which is vanishingly rare in these scripts.
    local code
    code=$(sed 's/#.*$//' "$file")

    # Negative array subscript: ${name[-N]} (arithmetic subscripts like
    # ${name[i-1]} are fine — we require a '-' immediately before a digit).
    if echo "$code" | grep -qE '\$\{[A-Za-z_][A-Za-z0-9_]*\[[[:space:]]*-[0-9]'; then
        fail "scripts/host/${relpath}: uses negative array subscript (\${arr[-1]}) — Bash 4.3+; use \${arr[\${#arr[@]}-1]}"
        found=1
    fi

    # declare -A (associative array declaration)
    if echo "$code" | grep -qE '(^|[;&|[:space:]])declare[[:space:]]+-[A-Za-z]*A'; then
        fail "scripts/host/${relpath}: uses 'declare -A' (associative arrays) — Bash 4.0+"
        found=1
    fi

    # mapfile / readarray
    if echo "$code" | grep -qE '(^|[;&|[:space:]])(mapfile|readarray)([[:space:]]|$)'; then
        fail "scripts/host/${relpath}: uses mapfile/readarray — Bash 4.0+; use a read loop"
        found=1
    fi

    # Case modification: ${var,,}, ${var^^}, ${var,}, ${var^}
    if echo "$code" | grep -qE '\$\{[A-Za-z_][A-Za-z0-9_]*(\[[^]]*\])?[,^]'; then
        fail "scripts/host/${relpath}: uses case-modification expansion (\${var,,}/\${var^^}) — Bash 4.0+; use tr"
        found=1
    fi

    # &>> append-redirect of both streams
    if echo "$code" | grep -qE '&>>'; then
        fail "scripts/host/${relpath}: uses '&>>' append redirect — Bash 4.0+; use '>>file 2>&1'"
        found=1
    fi

    # coproc
    if echo "$code" | grep -qE '(^|[;&|[:space:]])coproc([[:space:]]|$)'; then
        fail "scripts/host/${relpath}: uses 'coproc' — Bash 4.0+"
        found=1
    fi

    if [ "$found" -eq 0 ]; then
        pass "scripts/host/${relpath}: no Bash-4.x-only constructs"
    fi
}

for shfile in "${REPO_ROOT}"/scripts/host/*.sh; do
    [ -f "${shfile}" ] || continue
    filename=$(basename "${shfile}")
    check_bash32_portability "${shfile}" "${filename}"
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
