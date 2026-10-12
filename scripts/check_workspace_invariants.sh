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
# Invariant 3 (no Windows-incompatible names): Windows cannot create a file or
# folder whose name contains a control character (0x01-0x1F) or any of
# < > : " | ? * \, ends in a dot or space, or is a reserved device name (CON,
# PRN, AUX, NUL, COM1-9, LPT1-9, COM/LPT with superscript 1-3, CONIN$, CONOUT$ --
# case-insensitive, with or without an extension such as nul.txt). It also
# treats two names in one directory that differ only in case as the same name.
# On Windows, `docker cp` stops extracting at the first such name and drops
# every later file, so a single leftover hostile test fixture (a file named
# with an embedded newline, on 2026-09-30) aborted a real Windows backup. The
# check covers every name under the root except .git internals, including
# .claude/logs, because a hostile name anywhere in the volume breaks a backup.
# The classes follow Microsoft's "Naming Files, Paths, and Namespaces" and Git
# for Windows' core.protectNTFS, and are kept identical in scope to the
# backup scripts' own name check (scripts/host/backup_daaf.{sh,ps1}). Not
# flagged: DEL (0x7F), COM0/LPT0, CONSOLE, "CON foo". See
# research/2026-09-29_FrameworkDev_BackupLongPathCount/.
#
# Together these are the checkable invariants that bind every future runner
# regardless of dispatch-prompt wording.
#
# Usage:
#   bash /daaf/scripts/check_workspace_invariants.sh               # normal (prints OK line on pass)
#   bash /daaf/scripts/check_workspace_invariants.sh -q            # quiet (suppress the OK line; still prints violations)
#   bash /daaf/scripts/check_workspace_invariants.sh --names-only  # Invariant 3 only (combinable with -q)
#
# --names-only runs ONLY Invariant 3 (names Windows cannot create + case-only
# clashes): Invariants 1-2 are not walked, and the OK line and violation report
# cover names alone. It exists for the backup scripts' "could not read the list
# of names" WARNING (scripts/host/backup_daaf.{sh,ps1}), which sends users here
# to list such names themselves. Invariants 1-2 are rules for the DAAF folder
# only: pointed at another folder they flag legitimate files and say "delete
# these objects" (observed 2026-10-01 on /home/appuser/.claude: Codex's
# symlinks, a CLAUDE.md and .claude.json.tmp* files), so the hint must never
# run them there. Its advice line also drops the "a test fixture or scratch
# probe likely leaked them" guess, which is a DAAF-development assumption.
#
# Root override: set DAAF_INVARIANT_ROOT to point the checker at another tree
# instead of the default /daaf. Two uses:
#   - tests: a fixture tree, e.g.
#       DAAF_INVARIANT_ROOT=<fixture dir> bash /daaf/scripts/check_workspace_invariants.sh
#   - users (with --names-only): the Claude Code state volume, which the backup
#     hint names for that volume, e.g.
#       DAAF_INVARIANT_ROOT=/home/appuser/.claude bash scripts/check_workspace_invariants.sh --names-only
#     Do not run the full check (without --names-only) on a folder other than
#     /daaf -- see above.
#
# Allowlist override: set DAAF_INVARIANT_ALLOWLIST to REPLACE the built-in
# symlink allowlist (the ALLOWLIST block below) for one run. It exists for
# tests: the built-in entries are DAAF dev-container paths that a CI checkout
# does not have, so a fixture can only be exempted through this variable, e.g.
#       DAAF_INVARIANT_ROOT=<fixture> DAAF_INVARIANT_ALLOWLIST=<fixture>/allowed/ \
#           bash /daaf/scripts/check_workspace_invariants.sh
#   - Format: one absolute path prefix per line (newline-separated); several
#     entries can be built with "$(printf '%s\n' "$a" "$b")". Newline, not
#     colon: a prefix may contain spaces, tabs or colons (a parent folder of the
#     root, which Invariant 3 does not check, can hold a colon), and every
#     character but newline is kept as written. A newline cannot be part of a
#     prefix -- harmless, since a name with a newline in it is itself an
#     Invariant 3 violation.
#   - Replace, not extend: while it is set, ONLY its entries exempt a symlink;
#     the built-in entries do not apply. A test can then show that its own
#     prefix is exempt and that nothing else is.
#   - Set but empty (or blank lines only): no prefix at all, so every symlink is
#     flagged (fail safe). Blank lines are skipped and never become an empty
#     prefix, which would match every path.
#   - Relative entries (anything not starting with /) are refused: the run
#     stops with exit 1 before any walk. Entries are compared as literal text
#     (glob characters included) with the start of each symlink path as find
#     prints it, "$ROOT/...", so a relative entry could never match and can
#     only be a mistake. End each entry with / so it cannot match a sibling
#     name such as allowed_not/.
#   - An entry that would exempt the whole checked folder (/, $ROOT/, or any
#     other prefix of "$ROOT/") is refused the same way: it would turn the
#     symlink check off while the run still exits 0.
#   - While it is set, every full run prints a NOTE on stderr (also with -q),
#     so a leftover export cannot quietly change the gate. --names-only skips
#     Invariant 1, so it prints no NOTE, but a relative entry still stops it.
# Default behavior with neither env var set and no args is byte-for-byte
# compatible with existing callers.
#
# Exit codes:
#   0 — all invariants satisfied (with --names-only: Invariant 3 satisfied)
#   1 — one or more violations found (offending paths listed with control chars escaped),
#       the Invariant 3 name walk did not complete (fail closed), an unknown
#       argument was given (usage printed), or a DAAF_INVARIANT_ALLOWLIST entry
#       is not an absolute path (nothing walked)

set -euo pipefail

# --- Allowlist (edit this block to add exceptions) ---
# Prefix-match based: any path that begins with one of these strings is exempt
# from the symlink invariant. Keep each entry as specific as possible.
# DAAF_INVARIANT_ALLOWLIST, when set, replaces this list (see the header).
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
NAMES_ONLY=0

# --- Parse arguments ---
# Each argument is checked on its own, so -q and --names-only combine in either
# order; anything else prints the usage and exits 1, as before.
for arg in "$@"; do
    case "$arg" in
        -q|--quiet) QUIET=1 ;;
        --names-only) NAMES_ONLY=1 ;;
        *)
            echo "Usage: bash $0 [-q] [--names-only]" >&2
            echo "  -q, --quiet     Suppress the OK line on pass (violations still print)" >&2
            echo "  --names-only    Check only Invariant 3 (names Windows cannot create and" >&2
            echo "                  case-only clashes); use this outside /daaf" >&2
            exit 1
            ;;
    esac
done

# --- Symlink allowlist in effect: built-in, or the DAAF_INVARIANT_ALLOWLIST override ---
# INTENT: pick the prefixes Invariant 1 exempts: the built-in ALLOWLIST when
#   DAAF_INVARIANT_ALLOWLIST is unset, otherwise ONLY the override's entries.
# REASONING: `${VAR+set}` tells unset apart from set-but-empty, so an empty value
#   means "no exemptions" (fail safe), never a fallback to the built-in list or
#   "allow everything". Blank lines are skipped before they can become an empty
#   prefix, which `"$prefix"*` would match against every path. A relative entry
#   is refused before any walk, because it could only be a mistake that exempts
#   nothing. Reading through printf instead of a here-string keeps bash from
#   writing a temp file.
# ASSUMES: entries are newline-separated (see the header); IFS= and read -r keep
#   each line exactly as written, spaces and backslashes included.
allowlist_override=0
active_allowlist=()
if [ -n "${DAAF_INVARIANT_ALLOWLIST+set}" ]; then
    allowlist_override=1
    while IFS= read -r allow_entry; do
        [ -n "$allow_entry" ] || continue
        case "$allow_entry" in
            /*) ;;
            *)
                echo "WORKSPACE INVARIANT ERROR: every DAAF_INVARIANT_ALLOWLIST entry must be an absolute path (start with /)." >&2
                printf '  Relative entry (control characters shown escaped): %s\n' "$allow_entry" | cat -A >&2
                echo "  Nothing was checked." >&2
                exit 1
                ;;
        esac
        # INTENT: refuse an entry that would exempt the WHOLE checked tree.
        # REASONING: matching is a literal prefix test, so an entry such as `/`,
        #   `/da` or `$ROOT/` matches every symlink under ROOT and turns Invariant 1
        #   off while the run still exits 0 (review 55, SUGGESTION). Callers such as
        #   the deploy-smoke probe judge by exit code alone, so this must be an error.
        # ASSUMES: every checked path starts with "${ROOT%/}/", with or without a
        #   trailing slash on ROOT.
        case "${ROOT%/}/" in
            "$allow_entry"*)
                echo "WORKSPACE INVARIANT ERROR: a DAAF_INVARIANT_ALLOWLIST entry would exempt the whole checked folder (${ROOT})." >&2
                printf '  Entry (control characters shown escaped): %s\n' "$allow_entry" | cat -A >&2
                echo "  Nothing was checked." >&2
                exit 1
                ;;
        esac
        active_allowlist+=("$allow_entry")
    done < <(printf '%s\n' "$DAAF_INVARIANT_ALLOWLIST")
    if [ "$NAMES_ONLY" -eq 0 ]; then
        echo "NOTE: DAAF_INVARIANT_ALLOWLIST is set, so its ${#active_allowlist[@]} prefix(es) replace the built-in symlink allowlist for this run." >&2
    fi
else
    active_allowlist=("${ALLOWLIST[@]}")
fi
readonly allowlist_override active_allowlist

# Track whether any invariant failed so we can report both before exiting.
any_violation=0

# --- Invariant 1: no unauthorized symlinks under $ROOT (excluding .git/) ---
# Collect every symlink first, then filter against the allowlist. -print0 keeps
# pathological names (tab/newline) intact through the pipeline; we read them
# NUL-delimited so a newline in a filename cannot split one path into two.

checked=0
sym_violations=()

# INTENT: with --names-only, skip the Invariant 1 and 2 walks entirely.
# REASONING: each walk's input below is `[ "$NAMES_ONLY" -eq 1 ] || find ...`, so
#   the loop reads an empty stream and its counters and violation lists stay
#   empty -- the reports for both invariants then print nothing. Guarding the
#   input instead of wrapping each loop in an `if` keeps the loop bodies as they
#   were.
# ASSUMES: an empty stream is the only effect needed; nothing else reads
#   $checked / $root_scanned except the full-check OK line, which --names-only
#   replaces.
while IFS= read -r -d '' link; do
    checked=$((checked + 1))
    allowed=0
    for prefix in "${active_allowlist[@]}"; do
        # INTENT: prefix-match the symlink path against each allowlist entry.
        # REASONING: case "$link" in "$prefix"*) uses glob prefix matching without
        #   spawning a subprocess per link; the trailing * anchors to the start.
        # ASSUMES: the quoted "$prefix" matches as literal text, so a glob
        #   character in an entry (e.g. a * from the override) is not a wildcard;
        #   the only wildcard is our own trailing * (checked with bash 5.2).
        case "$link" in
            "$prefix"*) allowed=1; break ;;
        esac
    done
    if [ "$allowed" -eq 0 ]; then
        sym_violations+=("$link")
    fi
done < <([ "$NAMES_ONLY" -eq 1 ] || find "$ROOT" -type l -not -path '*/.git/*' -print0)

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
done < <([ "$NAMES_ONLY" -eq 1 ] || find "$ROOT" -mindepth 1 -maxdepth 1 -not -path '*/.git' \
    \( \( -type f -size 0 \) -o -name '*.pre-migrate' -o \( -type d -name 'daaf-docker' \) \) \
    -print0)

# --- Invariant 3: no Windows-incompatible names under $ROOT (excluding .git) ---
# Every name in the tree must be creatable on Windows, and no two names in one
# directory may differ only in (ASCII) case. No allowlist: a hostile name
# anywhere in the volume breaks a Windows backup, so there is no safe exception.

names_checked=0
name_summary_seen=0
name_violations=()
name_reasons=()
clash_pairs=()

# INTENT: walk the tree ONCE and classify every name in a single awk process.
# REASONING: a bash `read -d ''` loop over the full ~100k-entry list costs one
#   read syscall per byte (~8s on /daaf), and per-file subprocesses would be
#   worse. find streams "<type> <path>" records NUL-delimited into one awk, which
#   counts, classifies, and detects clashes at C speed; only the (normally zero)
#   offenders come back to bash. `-name .git -prune` skips .git internals without
#   descending into them (machine-generated hash names, never hostile).
# ASSUMES: LC_ALL=C gives byte semantics — tolower() folds ASCII only (the clash
#   spec is ASCII case), and the \302\271 / \302\262 / \302\263 octal escapes
#   match the UTF-8 bytes of superscript 1/2/3 literally. awk (mawk or gawk)
#   accepts RS="\0" for NUL-delimited records; the awk program emits NUL-
#   delimited fields back (OFS=ORS="\0") so hostile names survive the round trip.
#   Output records: "U" <reasons> <path> | "C" <type> <path> <type> <path> |
#   "N" <count> (always last, from END — its absence means awk did not finish).
while IFS= read -r -d '' kind; do
    case "$kind" in
        U)
            IFS= read -r -d '' reasons
            IFS= read -r -d '' path
            name_reasons+=("$reasons")
            name_violations+=("$path")
            ;;
        C)
            IFS= read -r -d '' type_a
            IFS= read -r -d '' path_a
            IFS= read -r -d '' type_b
            IFS= read -r -d '' path_b
            clash_pairs+=("$path_a ($type_a) <-> $path_b ($type_b)")
            ;;
        N)
            IFS= read -r -d '' names_checked
            name_summary_seen=1
            ;;
    esac
done < <(find "$ROOT" -mindepth 1 \( -name .git -prune \) -o -printf '%y %p\0' \
    | LC_ALL=C awk '
        BEGIN { RS = "\0"; OFS = "\0"; ORS = "\0" }
        {
            names++
            # "%y %p": one type letter, a space, then the full path.
            type = substr($0, 1, 1)
            path = substr($0, 3)
            if (type == "f") type = "file"
            else if (type == "d") type = "dir"
            else if (type == "l") type = "symlink"
            else type = "special"
            base = path
            sub(/.*\//, "", base)
            parent = substr(path, 1, length(path) - length(base))

            # INTENT: tag each Windows-uncreatable name with every class it hits.
            # REASONING: listing the reason tells the fixer what to rename; one
            #   name may hit several classes (e.g. "CON." is reserved + trailing).
            # ASSUMES: "." and ".." never reach here (find -mindepth 1 emits real
            #   entries only); they are guarded anyway because Windows allows them.
            reasons = ""
            if (base ~ /[\001-\037]/) reasons = reasons ", control character"
            if (base ~ /[<>:"|?*\\]/) reasons = reasons ", reserved character"
            if (base != "." && base != ".." && base ~ /[. ]$/) reasons = reasons ", trailing dot or space"
            # Reserved device names match on the stem before the FIRST dot, so
            # nul.txt and Nul.tar.gz are reserved exactly like NUL.
            stem = base
            sub(/\..*/, "", stem)
            stem = tolower(stem)
            if (stem ~ /^(con|prn|aux|nul|com[1-9]|lpt[1-9]|com\302[\271\262\263]|lpt\302[\271\262\263]|conin\$|conout\$)$/) reasons = reasons ", reserved device name"
            if (reasons != "") print "U", substr(reasons, 3), path

            # INTENT: find names in the SAME directory that differ only in case.
            # REASONING: keying on the exact parent path plus the lowercased name
            #   reports sibling pairs only. Children of a clashing directory pair
            #   (CDIR/x vs cdir/x) have different exact parents, so they are not
            #   re-reported — renaming the directory pair resolves them.
            # ASSUMES: ASCII case folding matches the Windows collision we guard
            #   against for the names DAAF produces; later duplicates in a group
            #   are each paired with the first-seen name.
            key = parent tolower(base)
            if (key in first_path) print "C", first_type[key], first_path[key], type, path
            else { first_path[key] = path; first_type[key] = type }
        }
        END { print "N", names + 0 }
    ')

# Fail closed: without the END summary the walk did not finish, so a clean
# result could not be trusted.
if [ "$name_summary_seen" -eq 0 ]; then
    any_violation=1
    echo "WORKSPACE INVARIANT ERROR: the Windows-name walk under $ROOT did not complete" >&2
    echo "  (find/awk ended without its summary record); treating as a violation." >&2
fi

# --- Report: Invariant 1 ---
if [ "${#sym_violations[@]}" -gt 0 ]; then
    any_violation=1
    echo "WORKSPACE INVARIANT VIOLATION: unauthorized symlink(s) found under $ROOT" >&2
    echo "  (${#sym_violations[@]} of $checked symlink(s) are not on the allowlist)" >&2
    echo "  Fix: delete these objects (a scratch probe likely leaked them)." >&2
    if [ "$allowlist_override" -eq 1 ]; then
        echo "       Symlinks are allowed only under an allowlisted prefix; this run" >&2
        echo "       used the DAAF_INVARIANT_ALLOWLIST override, not the ALLOWLIST block." >&2
    else
        echo "       Symlinks are allowed only under an allowlisted prefix; see the" >&2
        echo "       ALLOWLIST block at the top of this script." >&2
    fi
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

# --- Report: Invariant 3 ---
if [ "${#name_violations[@]}" -gt 0 ] || [ "${#clash_pairs[@]}" -gt 0 ]; then
    any_violation=1
    echo "WORKSPACE INVARIANT VIOLATION: Windows-incompatible name(s) found under $ROOT" >&2
    echo "  (${#name_violations[@]} name(s) Windows cannot create and ${#clash_pairs[@]} case-only clash pair(s), of $names_checked name(s) checked)" >&2
    echo "  Fix: rename or delete; these names break Windows backups (docker cp aborts)." >&2
    echo "       Windows cannot create names with a control character, any of" >&2
    echo "       < > : \" | ? * \\, a trailing dot or space, or a reserved device name" >&2
    echo "       (CON, PRN, AUX, NUL, COM1-9, LPT1-9 and COM¹-³/LPT¹-³, CONIN\$, CONOUT\$;" >&2
    echo "       also with an extension, e.g. nul.txt), and treats names differing only in" >&2
    # The "leaked" guess fits the DAAF folder (where these names come from test
    # fixtures and probes), not a folder checked with --names-only from a backup
    # hint, so that mode gives neutral advice instead.
    if [ "$NAMES_ONLY" -eq 1 ]; then
        echo "       case as one name. Rename or remove them inside DAAF, then back up again." >&2
    else
        echo "       case as one name. A test fixture or scratch probe likely leaked them." >&2
    fi
    # Same control-char-rendering rationale as Invariant 1's report block; the
    # [reason] prefix names the class(es) each offending name hits.
    if [ "${#name_violations[@]}" -gt 0 ]; then
        echo "  Names Windows cannot create (control characters shown escaped):" >&2
        for i in "${!name_violations[@]}"; do
            printf '    [%s] %s\n' "${name_reasons[$i]}" "${name_violations[$i]}" | cat -A >&2
        done
    fi
    if [ "${#clash_pairs[@]}" -gt 0 ]; then
        echo "  Case-only clashes in one directory (Windows treats each pair as one name):" >&2
        for pair in "${clash_pairs[@]}"; do
            printf '    %s\n' "$pair" | cat -A >&2
        done
    fi
fi

# --- Exit ---
if [ "$any_violation" -ne 0 ]; then
    exit 1
fi

if [ "$QUIET" -eq 1 ]; then
    exit 0
fi
if [ "$NAMES_ONLY" -eq 1 ]; then
    echo "OK: Windows name check passed under $ROOT ($names_checked name(s) checked, none Windows-uncreatable or case-clashing)."
else
    echo "OK: workspace invariants satisfied ($checked symlink(s) checked, all allowlisted or none present; $root_scanned repo-root leak candidate(s) checked, all allowlisted or none present; $names_checked name(s) checked, none Windows-uncreatable or case-clashing)."
fi
exit 0
