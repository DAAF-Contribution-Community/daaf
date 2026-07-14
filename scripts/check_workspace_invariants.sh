#!/usr/bin/env bash
# check_workspace_invariants.sh — Lint the LIVE container filesystem for workspace invariants
#
# Git cannot see untracked scratch artifacts, so this lint walks the real
# filesystem under /daaf and enforces invariants that protect the backup/audit
# boundary. Scratch probes (backup gates, symlink verification harnesses) have
# repeatedly left invariant-violating filesystem objects behind — most damagingly
# symlinks with tab/newline names under scripts/scratch/, which broke real user
# backups three separate times on 2026-07-14. This lint is the checkable
# invariant that binds every future runner regardless of dispatch-prompt wording.
#
# Usage:
#   bash /daaf/scripts/check_workspace_invariants.sh        # normal (prints OK line on pass)
#   bash /daaf/scripts/check_workspace_invariants.sh -q     # quiet (suppress the OK line; still prints violations)
#
# Exit codes:
#   0 — all invariants satisfied
#   1 — one or more violations found (offending paths listed with control chars escaped)

set -euo pipefail

# --- Allowlist (edit this block to add exceptions) ---
# Prefix-match based: any path that begins with one of these strings is exempt
# from the symlink invariant. Keep each entry as specific as possible.
#
# syslibs_glpk: extracted .deb shared libraries for the R Support GLPK work.
# These .so.N symlinks are legitimate scratch provenance artifacts, not probe
# leftovers, and are intentionally retained (see 2026-07-06_FrameworkDev_R_Support).
readonly ALLOWLIST=(
    "/daaf/research/2026-07-06_FrameworkDev_R_Support/scripts/scratch/syslibs_glpk/"
)

# --- Config ---
readonly ROOT="/daaf"
QUIET=0

# --- Parse arguments ---
if [ $# -gt 0 ]; then
    case "$1" in
        -q|--quiet) QUIET=1 ;;
        *)
            echo "Usage: bash $0 [-q]" >&2
            echo "  -q, --quiet   Suppress the OK line on pass (violations still print)" >&2
            exit 1
            ;;
    esac
fi

# --- Invariant 1: no unauthorized symlinks under /daaf (excluding .git/) ---
# Collect every symlink first, then filter against the allowlist. -print0 keeps
# pathological names (tab/newline) intact through the pipeline; we read them
# NUL-delimited so a newline in a filename cannot split one path into two.

checked=0
violations=()

while IFS= read -r -d '' link; do
    checked=$((checked + 1))
    allowed=0
    for prefix in "${ALLOWLIST[@]}"; do
        # INTENT: prefix-match the symlink path against each allowlist entry.
        # REASONING: case "$link" in "$prefix"*) uses glob prefix matching without
        #   spawning a subprocess per link; the trailing * anchors to the start.
        # ASSUMES: allowlist prefixes contain no glob metacharacters (they are
        #   literal directory paths), so the only wildcard is our own trailing *.
        case "$link" in
            "$prefix"*) allowed=1; break ;;
        esac
    done
    if [ "$allowed" -eq 0 ]; then
        violations+=("$link")
    fi
done < <(find "$ROOT" -type l -not -path '*/.git/*' -print0)

# --- Report ---
if [ "${#violations[@]}" -gt 0 ]; then
    echo "WORKSPACE INVARIANT VIOLATION: unauthorized symlink(s) found under $ROOT" >&2
    echo "  (${#violations[@]} of $checked symlink(s) are not on the allowlist)" >&2
    echo "  Fix: delete these objects (a scratch probe likely leaked them)." >&2
    echo "       Symlinks are allowed only under an allowlisted prefix; see the" >&2
    echo "       ALLOWLIST block at the top of this script." >&2
    echo "  Offending paths (control characters shown escaped):" >&2
    # INTENT: render each offending path with control characters made visible.
    # REASONING: a symlink named with an embedded tab or newline is invisible/
    #   misleading in a plain echo; cat -A escapes tabs as ^I and marks line
    #   ends with $, so pathological names are identifiable and actionable.
    # ASSUMES: printf %s\n emits one path per line for cat -A to annotate; a name
    #   containing a literal newline will span lines but each segment is $-marked.
    for bad in "${violations[@]}"; do
        printf '    %s\n' "$bad" | cat -A >&2
    done
    exit 1
fi

if [ "$QUIET" -eq 0 ]; then
    echo "OK: workspace invariants satisfied ($checked symlink(s) checked, all allowlisted or none present)."
fi
exit 0
