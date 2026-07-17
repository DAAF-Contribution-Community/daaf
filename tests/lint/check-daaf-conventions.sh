#!/usr/bin/env bash
# ============================================================================
# DAAF Convention Lint — custom checks beyond ShellCheck / PSScriptAnalyzer
# ============================================================================
# Checks DAAF-specific patterns that standard linters do not cover:
#   1. Bash preamble: shebang + set -euo pipefail (or set -eu / trap ERR)
#   2. PowerShell preamble: $ErrorActionPreference in first 15 code lines
#      (host-facing operational scripts/host/*.ps1 only)
#   3. DAAF_NESTED consistency: host lifecycle scripts reference DAAF_NESTED
#   4. Numbered progress: host lifecycle scripts use [N/M] indicators (warn only)
#   5. Bash 3.2 portability: host scripts avoid Bash-4.x-only constructs
#   6. ASCII purity: host-facing files contain only printable ASCII (+ tab/LF/CR)
#   7. Skill-freshness key hygiene: live surfaces carry no stale
#      skill_last_updated / provenance.skill-last-updated spellings
#   8. Data-source provenance: each *data-source* SKILL.md declares
#      skill-authored + skill-last-updated in its frontmatter metadata block
#   9. grep -q pipefail hazard: host scripts never pipe a LIVE command into
#      grep -q (only echo/printf of an already-captured value)
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
echo "--- PowerShell preamble checks (host scripts) ---"

# SCOPE: host-facing operational PowerShell scripts only (scripts/host/*.ps1) --
# the lifecycle scripts a user runs on their own machine, whose error-handling
# contract this rule actually governs. A maxdepth-1 glob over scripts/host,
# matching how sections 3-6 already scope their host checks. This deliberately
# does NOT recurse the whole repository: ignored research/, .claude/worktrees/,
# and scripts/scratch/ PowerShell residue are archival/transient copies that must
# not gate the lint, and library/test PowerShell (*.Tests.ps1, TestHelper.ps1)
# lives outside scripts/host. The glob walks the LIVE filesystem, so newly
# authored UNTRACKED host scripts are still checked; switching to `git ls-files`
# would hide them. Sourced function libraries (*_lib.ps1) remain exempt: a
# dot-sourced library must not force $ErrorActionPreference on its caller -- its
# functions save/restore EAP locally -- mirroring the *_lib.sh Bash exemption.
for ps1file in "${REPO_ROOT}"/scripts/host/*.ps1; do
    [ -f "${ps1file}" ] || continue
    relpath="${ps1file#"${REPO_ROOT}/"}"
    filename=$(basename "${ps1file}")

    case "${filename}" in
        *_lib.ps1) continue ;;
    esac

    # Check for $ErrorActionPreference in first 15 non-comment, non-blank code lines.
    # PowerShell comments start with # (like bash). Counting code lines is robust
    # against variable-length comment headers and dry-run blocks.
    code_lines=$(awk '!/^\s*#/ && !/^\s*$/ { print; if (++n == 15) exit }' "${ps1file}")
    if ! echo "${code_lines}" | grep -q 'ErrorActionPreference'; then
        fail "${relpath}: missing '\$ErrorActionPreference' in first 15 code lines"
    fi
done

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
# 6. ASCII purity (host-facing files)
# =====================================================================
echo "--- ASCII purity checks (host-facing files) ---"

# Every file under scripts/host/ is either downloaded raw to a user's machine
# (.sh / .ps1 lifecycle scripts) or round-tripped through Windows PowerShell 5.1
# read/write cycles (environment_settings_example.txt, via the settings upsert).
# Pure ASCII makes each file invariant under any codepage, editor, or PowerShell
# version -- defense-in-depth atop the -Encoding UTF8 read pin (commit 93bfb55).
# A single non-ASCII byte (em-dash, smart quote, NBSP) is exactly what a bare
# PS 5.1 Get-Content mojibakes, so this gate keeps the class extinct at the door.
#
# Allowed bytes: tab (0x09), CR (0x0D), and printable ASCII (0x20-0x7E). LF (0x0A)
# is the line delimiter and never appears within a line grep inspects. Any other
# byte -- a high-bit byte (0x80-0xFF) or a stray control char -- is flagged.
# LC_ALL=C forces byte-wise matching so the [ -~] range is exactly 0x20-0x7E on
# both GNU and BSD grep; using -E (ERE) rather than -P (PCRE) keeps this gate
# portable per the lint's own standards (BSD grep has no -P). The literal tab and
# CR are built via printf so the lint's own source stays pure ASCII too.
# -a (--text, portable on GNU and BSD grep) forces text mode so a NUL-containing
# or UTF-16-mangled file -- the check's own motivating PS 5.1 Out-File scenario --
# is flagged with line numbers instead of silently bailing to grep's binary mode
# (GNU grep treats a NUL-bearing file as binary, printing "binary file matches" to
# stderr, which 2>/dev/null discards, and nothing to stdout -- a silent false pass).
# Caveat: this gate assumes a POSIX/GNU-compatible grep binary. Interactive shells
# that alias or function grep to ugrep diverge on CR and invalid-UTF-8 handling, but
# `bash <script>` does not inherit shell functions or aliases, so the invocation
# path this lint actually runs under is unaffected.
#
# SCOPE: this walks the live filesystem under scripts/host/ (a maxdepth-1 glob),
# matching how every other section here scopes host checks. In CI only tracked
# files exist, so it is effectively a tracked-file gate; a local dev checkout may
# also carry untracked host files (e.g. nuke_daaf.sh), which the existing preamble
# / DAAF_NESTED / Bash-3.2 sections already scan the same way -- the ASCII gate
# simply follows that established convention rather than adding a git dependency.

non_ascii_re="[^$(printf '\t\r') -~]"

for hostfile in "${REPO_ROOT}"/scripts/host/*; do
    [ -f "${hostfile}" ] || continue
    filename=$(basename "${hostfile}")

    # LC_ALL=C: match on raw bytes, not the locale's multibyte interpretation.
    offending=$(LC_ALL=C grep -anE "${non_ascii_re}" "${hostfile}" 2>/dev/null || true)
    if [ -n "${offending}" ]; then
        fail "scripts/host/${filename}: contains non-ASCII byte(s) outside printable ASCII (tab/LF/CR allowed):"
        # cat -v renders the offending bytes visibly (e.g. an em-dash prints as
        # M-bM-^@M-^T) so they are reportable without corrupting the terminal.
        printf '%s\n' "${offending}" | LC_ALL=C cat -v | while IFS= read -r _line; do
            printf '        %s\n' "${_line}"
        done
    else
        pass "scripts/host/${filename}: pure ASCII"
    fi
done

echo ""

# =====================================================================
# 7. Skill-freshness metadata key hygiene (live framework surfaces)
# =====================================================================
echo "--- Skill-freshness metadata key checks (live surfaces) ---"

# The canonical skill-freshness convention is a flat, hyphenated key inside the
# frontmatter `metadata:` block: `skill-last-updated` (paired with
# `skill-authored`). See skill-authoring/references/frontmatter.md ("Data source
# skills MUST include skill-authored and skill-last-updated as metadata keys")
# and DATA_SOURCE_SKILL_TEMPLATE.md. Reader-side instructions historically
# drifted to a nonexistent nested/snake_case spelling
# (`provenance.skill_last_updated`), pointing agents at a field that does not
# exist. This gate keeps that class extinct: no live framework surface may
# contain the snake_case token `skill_last_updated` or the dotted
# `provenance.skill-last-updated` nesting.
#
# SCOPE: live framework surfaces only -- the agent/skill/reference docs agents
# actually read as instructions. Deliberately excludes research/ and benchmarks/
# (archival project artifacts) and .claude/logs/ (immutable session transcripts),
# which legitimately quote past buggy instructions and must not be rewritten. The
# scope is expressed by listing live paths explicitly (rather than excluding), so
# .claude/logs/ is naturally out of scope while .claude/agents and .claude/skills
# are in. tests/lint/ is out of scope, so this script's own comments above do not
# self-match.

freshness_bad_re='skill_last_updated|provenance\.skill-last-updated'
freshness_targets="
${REPO_ROOT}/.claude/agents
${REPO_ROOT}/.claude/skills
${REPO_ROOT}/agent_reference
${REPO_ROOT}/user_reference
${REPO_ROOT}/CLAUDE.md
${REPO_ROOT}/README.md
"

freshness_present=""
while IFS= read -r t; do
    [ -n "${t}" ] || continue
    [ -e "${t}" ] && freshness_present="${freshness_present} ${t}"
done <<EOF
${freshness_targets}
EOF

# shellcheck disable=SC2086
freshness_hits=$(grep -rnE "${freshness_bad_re}" ${freshness_present} 2>/dev/null || true)
if [ -n "${freshness_hits}" ]; then
    fail "stale skill-freshness key spelling on live surfaces (use the 'skill-last-updated' key in the frontmatter 'metadata:' block):"
    printf '%s\n' "${freshness_hits}" | while IFS= read -r _line; do
        printf '        %s\n' "${_line}"
    done
else
    pass "no stale skill-freshness key spellings on live surfaces"
fi

echo ""

# =====================================================================
# 8. Data-source skill provenance completeness
# =====================================================================
echo "--- Data-source skill provenance metadata checks ---"

# Every data-source skill MUST declare both provenance keys in its frontmatter
# metadata block (skill-authoring/references/frontmatter.md). This gate is the
# producer-side complement to check 7's reader-side hygiene: it fails if any
# *data-source* SKILL.md is missing either key, guaranteeing the reader
# instructions fixed in check 7 always have a real field to point at.

ds_found=0
for skillfile in "${REPO_ROOT}"/.claude/skills/*data-source*/SKILL.md; do
    [ -f "${skillfile}" ] || continue
    ds_found=1
    relpath="${skillfile#"${REPO_ROOT}/"}"
    missing=""
    grep -qE '(^|[[:space:]])skill-authored:' "${skillfile}" || missing="${missing} skill-authored"
    grep -qE '(^|[[:space:]])skill-last-updated:' "${skillfile}" || missing="${missing} skill-last-updated"
    if [ -n "${missing}" ]; then
        fail "${relpath}: missing required provenance metadata key(s):${missing}"
    else
        pass "${relpath}: has skill-authored + skill-last-updated"
    fi
done

if [ "${ds_found}" -eq 0 ]; then
    warn "no *data-source* SKILL.md files found to check (glob matched nothing)"
fi

echo ""

# =====================================================================
# 9. grep -q pipefail-inversion hazard (host scripts)
# =====================================================================
echo "--- grep -q pipefail-inversion checks (host scripts) ---"

# HAZARD: piping a LIVE command into `grep -q` inverts under `set -o pipefail`.
# grep -q exits on the FIRST match and closes the pipe; the still-running
# upstream producer then dies of SIGPIPE (exit 141), and pipefail turns a FOUND
# result into a false FAIL (PIPESTATUS='141 0'). Every scripts/host/*.sh runs
# under pipefail, so this class is live everywhere here.
#
# SANCTIONED IDIOM: capture-then-grep -- assign the producer's output to a
# variable first, then `printf '%s\n' "$var" | grep -q ...` (or
# `echo "$var" | grep -q ...`). An echo/printf of an already-captured value
# cannot SIGPIPE mid-stream, so the inversion cannot occur.
#
# This gate flags any `| grep -q` (any -q flag combo: -q/-qw/-qi/-qF/-qE) whose
# IMMEDIATE producer stage is not an echo/printf. The pipe pattern requires a
# non-`|` byte immediately before the `|` (`[^|]\|`) so a `||` logical-OR --
# e.g. `grep -qf a b || grep -qf a c`, which contains NO pipe into grep -- is not
# misread as a pipeline. The safe form is `(echo|printf) <non-pipe chars> |
# grep -q...`; the `[^|]*` cannot cross a pipe, so the echo/printf must be the
# direct producer to be exempt (`echo x | sort | grep -q` is still flagged --
# sort is the live producer). Full-line comments are skipped; an inline
# trailing-comment match is an accepted false positive (mirrors the
# run_with_capture.sh install-scan tradeoff). Non-piped greps
# (`grep -q PATTERN FILE`, `grep -qf`, `container_exec grep -q ...`) have no pipe
# stage and are never matched. SCOPE: scripts/host/*.sh only, matching the sibling
# host sections; the walk is over the live filesystem so untracked host scripts
# are checked too.
#
# A second accepted false-positive class: an echoed/printf'd argument that itself
# contains a literal '|' (e.g. `echo "a|b" | grep -q x`) trips the exemption regex,
# because its `[^|]*` cannot cross that embedded pipe, so the safe idiom is falsely
# flagged. This fails safe (over-flags, never under-flags), no such line exists in
# the tree today, and the workaround is capture-then-grep on the variable (or
# restructure the pipeline).

for shfile in "${REPO_ROOT}"/scripts/host/*.sh; do
    [ -f "${shfile}" ] || continue
    filename=$(basename "${shfile}")

    hazard_lines=$(grep -nE '[^|]\|[[:space:]]*grep[[:space:]]+-q' "${shfile}" \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -vE '(echo|printf)[^|]*\|[[:space:]]*grep[[:space:]]+-q' \
        || true)

    if [ -n "${hazard_lines}" ]; then
        fail "scripts/host/${filename}: live command piped into 'grep -q' (pipefail-inversion hazard; use capture-then-grep):"
        printf '%s\n' "${hazard_lines}" | while IFS= read -r _line; do
            printf '        %s\n' "${_line}"
        done
    else
        pass "scripts/host/${filename}: no unsafe '| grep -q' pipelines"
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
