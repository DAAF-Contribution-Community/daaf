#!/usr/bin/env bash
# check_workspace_invariants.sh — Lint the LIVE container filesystem for workspace invariants
#
# Git cannot see untracked scratch artifacts, so this lint walks the real
# filesystem under /daaf and enforces invariants that protect the backup/audit
# boundary.
#
# Invariant 1 (no unauthorized symlinks): Scratch probes (backup gates, symlink
# verification harnesses) have repeatedly left invariant-violating filesystem
# objects behind — most damagingly symlinks with tab/newline names under
# scripts/scratch/, which broke real user backups three separate times on
# 2026-07-14.
#
# Invariant 2 (no leak artifacts at repo root): A host tool run with the wrong
# CWD scatters stub files at the repo root. On 2026-07-14 a `migrate_daaf.sh`
# dry-run executed with CWD=/daaf left 13 zero-byte stub files plus a
# `docker-compose.yml.pre-migrate` at the repo root; an `install.sh` dry-run in
# the same position leaves a stray `daaf-docker/` directory. These pollute the
# tracked tree and are easy to miss by eye. See
# research/2026-07-15_FrameworkDev_CwdLeakRootStubs/.
#
# Together these are the checkable invariants that bind every future runner
# regardless of dispatch-prompt wording.
#
# Usage:
#   bash /daaf/scripts/check_workspace_invariants.sh        # normal (prints OK line on pass)
#   bash /daaf/scripts/check_workspace_invariants.sh -q     # quiet (suppress the OK line; still prints violations)
#
# Root override (for tests only): set DAAF_INVARIANT_ROOT to point the checker at
# a fixture tree instead of the default /daaf, e.g.
#   DAAF_INVARIANT_ROOT=/tmp/fixture bash /daaf/scripts/check_workspace_invariants.sh
# Default behavior with no env var and no args is byte-for-byte compatible with
# existing callers.
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

# --- Root-leak allowlist (edit this block to add exceptions) ---
# Prefix-match based, same idiom as ALLOWLIST above: any repo-root entry whose
# path begins with one of these strings is exempt from Invariant 2. Intentionally
# empty — no legitimate zero-byte / *.pre-migrate / daaf-docker root artifact is
# known. Populate only with a documented rationale.
readonly ROOT_LEAK_ALLOWLIST=(
)

# --- Config ---
# ROOT defaults to /daaf; DAAF_INVARIANT_ROOT overrides it for fixture-based
# testing. The default path keeps existing no-arg callers byte-for-byte identical.
readonly ROOT="${DAAF_INVARIANT_ROOT:-/daaf}"
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

# Track whether any invariant failed so we can report both before exiting.
any_violation=0

# --- Invariant 1: no unauthorized symlinks under $ROOT (excluding .git/) ---
# Collect every symlink first, then filter against the allowlist. -print0 keeps
# pathological names (tab/newline) intact through the pipeline; we read them
# NUL-delimited so a newline in a filename cannot split one path into two.

checked=0
sym_violations=()

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
        sym_violations+=("$link")
    fi
done < <(find "$ROOT" -type l -not -path '*/.git/*' -print0)

# --- Invariant 2: no leak artifacts at repo root ($ROOT, maxdepth 1) ---
# A wrong-CWD host-tool dry-run scatters stubs directly under the repo root. We
# scan only the top level (-maxdepth 1) because these are always deposited at
# CWD=$ROOT, never nested. Flagged shapes:
#   (a) zero-byte regular files      — the migrate dry-run stub signature
#   (b) *.pre-migrate files          — migrate's pre-move backup, e.g. docker-compose.yml.pre-migrate
#   (c) an unexpected daaf-docker/   — the shape an install.sh dry-run leaves
# .git is excluded as Invariant 1 does. -print0 + NUL-delimited read handle
# pathological names identically to Invariant 1.

root_scanned=0
root_violations=()

# INTENT: scan the repo-root top level for the three leak-artifact shapes in one walk.
# REASONING: a single find with -maxdepth 1 and a grouped OR predicate is cheaper
#   than three separate walks and keeps NUL-delimited output uniform. -mindepth 1
#   excludes $ROOT itself; -not -path '*/.git*' drops the .git dir (at depth 1 the
#   path is "$ROOT/.git", so the trailing-slash-free pattern matches it).
# ASSUMES: (a) zero-byte regular file = `-type f -size 0`; (b) *.pre-migrate = name
#   glob on any type; (c) stray daaf-docker = a directory literally named daaf-docker.
#   The daaf-docker check is a directory *name* match, not a content probe — a wrong
#   CWD install dry-run creates the dir shape regardless of what it puts inside.
while IFS= read -r -d '' entry; do
    root_scanned=$((root_scanned + 1))
    allowed=0
    for prefix in "${ROOT_LEAK_ALLOWLIST[@]}"; do
        # Same prefix-match idiom as Invariant 1's allowlist.
        case "$entry" in
            "$prefix"*) allowed=1; break ;;
        esac
    done
    if [ "$allowed" -eq 0 ]; then
        root_violations+=("$entry")
    fi
done < <(find "$ROOT" -mindepth 1 -maxdepth 1 -not -path '*/.git' \
    \( \( -type f -size 0 \) -o -name '*.pre-migrate' -o \( -type d -name 'daaf-docker' \) \) \
    -print0)

# --- Report: Invariant 1 ---
if [ "${#sym_violations[@]}" -gt 0 ]; then
    any_violation=1
    echo "WORKSPACE INVARIANT VIOLATION: unauthorized symlink(s) found under $ROOT" >&2
    echo "  (${#sym_violations[@]} of $checked symlink(s) are not on the allowlist)" >&2
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
    for bad in "${sym_violations[@]}"; do
        printf '    %s\n' "$bad" | cat -A >&2
    done
fi

# --- Report: Invariant 2 ---
if [ "${#root_violations[@]}" -gt 0 ]; then
    any_violation=1
    echo "WORKSPACE INVARIANT VIOLATION: leak artifact(s) found at repo root ($ROOT)" >&2
    echo "  (${#root_violations[@]} of $root_scanned top-level entry/entries flagged)" >&2
    echo "  Fix: delete these objects. They are the signature of a host tool" >&2
    echo "       (migrate/install) run with the wrong CWD — zero-byte stubs," >&2
    echo "       *.pre-migrate backups, or a stray daaf-docker/ directory." >&2
    echo "       See research/2026-07-15_FrameworkDev_CwdLeakRootStubs/." >&2
    echo "  Offending paths (control characters shown escaped):" >&2
    # Same control-char-rendering rationale as Invariant 1's report block.
    for bad in "${root_violations[@]}"; do
        printf '    %s\n' "$bad" | cat -A >&2
    done
fi

# --- Exit ---
if [ "$any_violation" -ne 0 ]; then
    exit 1
fi

if [ "$QUIET" -eq 0 ]; then
    echo "OK: workspace invariants satisfied ($checked symlink(s) checked, all allowlisted or none present; $root_scanned repo-root leak candidate(s) checked, all allowlisted or none present)."
fi
exit 0
