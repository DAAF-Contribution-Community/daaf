#!/usr/bin/env bash
# ============================================================================
# DAAF Backup Utility (macOS / Linux)
# ============================================================================
# Creates a timestamped backup of your DAAF Docker volume on the host.
#
# Usage:
#   cd daaf-docker
#   bash backup_daaf.sh
#
# Backups are created in the current directory with date-versioned names:
#   2026-04-21_daaf_backup/     (first backup of the day)
#   2026-04-21a_daaf_backup/    (second backup)
#   2026-04-21b_daaf_backup/    (third backup)
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script like migrate_daaf.sh).
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so the volume name below reflects DAAF_PROJECT_NAME. This script
# operates on the Docker volume via raw `docker run`/`docker volume` (not
# `docker compose`), so compose interpolation does not apply -- we must derive the
# project-prefixed volume name ourselves. Canonical shared pattern (kept in sync
# with load_daaf_settings in daaf_lib.sh). Parse only these whitelisted keys (never
# `source` -- the file holds API keys); shell env wins; absent file = no-op; CR
# stripped; Bash 3.2 safe.
_daaf_load_settings() {
    local settings_file="./environment_settings.txt"
    [ -f "${settings_file}" ] || return 0
    local key val line
    while IFS= read -r line || [ -n "${line}" ]; do
        line="$(printf '%s' "${line}" | tr -d '\r')"
        case "${line}" in ''|'#'*) continue ;; esac
        case "${line}" in
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*|DAAF_DEV=*|DAAF_BRANCH=*|DAAF_DATA_VOLUME_NAME=*)
                key="${line%%=*}"; val="${line#*=}"
                case "${val}" in
                    \"*\") val="${val#\"}"; val="${val%\"}" ;;
                    \'*\') val="${val#\'}"; val="${val%\'}" ;;
                esac
                if [ -z "${!key:-}" ]; then
                    export "${key}=${val}"
                fi
                ;;
            *) continue ;;
        esac
    done < "${settings_file}"
}
_daaf_load_settings

# --- Configuration ---
# The Docker named volume is project-prefixed: "<project>_daaf-data". Compose
# derives the prefix from the project name (default "daaf"), so a second instance
# with DAAF_PROJECT_NAME=daaf2 owns the volume "daaf2_daaf-data". Default unset =>
# "daaf_daaf-data" (byte-for-byte identical to the previous hardcoded value).
# DAAF_DATA_VOLUME_NAME, when set, overrides the whole derivation with a verbatim
# full volume name (the shared-workspace escape hatch); unset => the derived
# default. Matches resolve_data_volume_name in daaf_lib.sh (inlined here because
# this standalone script does not source the library).
VOLUME_NAME="${DAAF_DATA_VOLUME_NAME:-${DAAF_PROJECT_NAME:-daaf}_daaf-data}"
# Second volume: Claude Code state (auth/credentials, session history and
# transcripts, plugins, ~/.claude.json). Backed up into a dedicated hidden
# subfolder of the backup so it does not contaminate the data-volume file
# counts (which scan the backup root). May not exist on very old installs that
# predate the volume -- handled gracefully below.
CLAUDE_VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-claude-config"
CLAUDE_SUBDIR=".daaf-claude-config"
# Where that volume is mounted INSIDE the DAAF container (docker-compose.yml:
# `daaf-claude-config:/home/appuser/.claude`). Used only in a warning's next step
# (_daaf_case_report); update it by hand if the compose mount moves.
CLAUDE_CONTAINER_PATH="/home/appuser/.claude"
# Symlink manifest: backup-root sibling of .daaf-permissions. On Windows hosts,
# `docker cp` extraction ABORTS the moment it hits a symlink it cannot create
# (symlink creation needs admin/Developer Mode), silently dropping every file that
# sorts after it in the archive stream. To make backups symlink-safe, the volume is
# first STAGED into a throwaway container: the staging step records each symlink's
# path+target into this manifest and then removes the symlinks, so the tree
# `docker cp` streams contains NO symlinks. Restore replays the manifest to
# recreate the links (see restore_from_backup.sh Step 3e). The staging step ALWAYS
# writes it (0 bytes when the volume has no symlinks). Absent manifest (a backup that
# predates this feature) = no-op on restore, matching the ".daaf-permissions" "no
# manifest, no action" rule.
# The same staging step also DELETES special files -- named pipes (FIFOs), sockets,
# and block/char device nodes -- with no manifest: Windows `docker cp` creates
# nothing for them and then aborts on the follow-up timestamp call, the same
# truncation class as the symlink abort. They are runtime rendezvous objects with no
# content (e.g. stale provider-shim `output.fifo` stream files), so restore does not
# recreate them; the scan below counts them so the skip is visible to the user.
SYMLINKS_MANIFEST=".daaf-symlinks"
# Executable-permission manifest, written into the backup root after verification
# (see "Capture the executable-permission manifest" below). Declared here because
# the backup-folder count excludes it too.
PERMISSIONS_MANIFEST=".daaf-permissions"
# The helper image every container step runs, PINNED by digest: busybox 1.37.0,
# multi-arch OCI index (amd64, arm64/v8 and others), the tested digest below. Pinned
# because the untagged `busybox` (latest) moved to the untested busybox 1.38.0 on
# 2026-09-23 (research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/
# 04_F1_compat_audit.md). The same string is in backup_daaf.{sh,ps1},
# restore_from_backup.{sh,ps1}, migrate_daaf.{sh,ps1} and docker-compose.yml (daaf-init):
# keep every copy identical (a parity test enforces it).
BUSYBOX_IMAGE='busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
TODAY=$(date +%Y-%m-%d)
# Name-handling switch for the staging program (see UNCREATABLE NAMES in the
# STAGE_PROGRAM comments below), passed as `-e DAAF_STAGE_NAMES=...`. This twin NEVER removes a
# name -- names Windows cannot create are legal on macOS/Linux disks. On macOS it asks
# for "casewarn": list names that differ only in upper/lower case (the default macOS
# disk format is case-insensitive, so one of each pair can overwrite the other). On
# Linux the value is empty and the step does not run. Only backup_daaf.ps1 passes "win".
STAGE_NAMES_MODE=""
if [ "$(uname -s 2>/dev/null || true)" = "Darwin" ]; then
    STAGE_NAMES_MODE="casewarn"
fi

# --- Host-side backup-folder count (never silent) ---
# Counts the data files ("files") or their logical KB ("kb") under a backup folder,
# with the root-relative exclusions every count site shares (the root manifests and
# the root Claude subfolder), and says whether the count is COMPLETE. The old form,
# `$(cd ... && find ... 2>/dev/null | ...) || FILE_COUNT=0`, discarded find's read
# errors and, under pipefail, replaced a partial count with 0: one unreadable folder
# printed "0 files were copied. The Docker volume may be empty." and exited 1.
#
# Here the group's stderr (find's read errors, and any from tr/wc/ls/awk) lands in the
# SAME captured string as the result, which the pipeline prints LAST: wc/awk write
# only after reading EOF, i.e. after find has exited, so every error line precedes the
# result line. No temp file is involved, so an interrupt leaves nothing behind and the
# EXIT trap (the pause prompt) stays untouched. Any error line, a nonzero status
# (pipefail carries find's exit 1 on a read error), or a result line that is not
# digits (e.g. `cd` failed) makes the value a LOWER BOUND -- 0 when nothing could be
# read -- which callers show as "N+" and never treat as proof of loss or emptiness.
# Sets TREE_COUNT, TREE_COUNT_LOWER_BOUND (1/0), TREE_COUNT_ERRORS (error lines) and
# TREE_COUNT_FIRST_ERROR. Bash 3.2 + BSD userland safe (`LC_ALL=C tr`: macOS's
# multibyte-aware tr can fail with "Illegal byte sequence" on a non-UTF-8 name byte).
_daaf_tree_count() {
    local dir="$1" mode="$2" raw last status=0
    if [ "${mode}" = "kb" ]; then
        raw=$( { cd "${dir}" && find . -type f ! -path "./${SYMLINKS_MANIFEST}" ! -path "./${PERMISSIONS_MANIFEST}" ! -path "./${CLAUDE_SUBDIR}/*" -exec ls -ln {} + | awk '{s+=$5} END {printf "%d\n", s/1024}'; } 2>&1 ) || status=$?
    else
        # One NUL per file (`-print0`, GNU and BSD find), so a name holding a newline
        # counts once, matching the snapshot's one-`stat`-line-per-file count.
        raw=$( { cd "${dir}" && find . -type f ! -path "./${SYMLINKS_MANIFEST}" ! -path "./${PERMISSIONS_MANIFEST}" ! -path "./${CLAUDE_SUBDIR}/*" -print0 | LC_ALL=C tr -dc '\000' | wc -c; } 2>&1 ) || status=$?
    fi
    last="$(printf '%s\n' "${raw}" | tail -n 1 | tr -d '[:space:]')"
    case "${last}" in
        ''|*[!0-9]*)
            # No result line: nothing could be counted; every line is an error.
            TREE_COUNT=0
            TREE_COUNT_LOWER_BOUND=1
            TREE_COUNT_ERRORS="$(printf '%s\n' "${raw}" | grep -c .)" || true
            TREE_COUNT_FIRST_ERROR="$(printf '%s\n' "${raw}" | grep . | head -n 1)" || true
            ;;
        *)
            TREE_COUNT="${last}"
            TREE_COUNT_ERRORS="$(printf '%s\n' "${raw}" | sed '$d' | grep -c .)" || true
            TREE_COUNT_FIRST_ERROR="$(printf '%s\n' "${raw}" | sed '$d' | grep . | head -n 1)" || true
            TREE_COUNT_LOWER_BOUND=0
            if [ "${status}" -ne 0 ] || [ "${TREE_COUNT_ERRORS:-0}" -gt 0 ]; then
                TREE_COUNT_LOWER_BOUND=1
            fi
            ;;
    esac
}

# --- Case-clash report (macOS "casewarn" staging mode) ---
# Reads a staging log ($1) for the lines the staging program prints in "casewarn" mode
# (see UNCREATABLE NAMES in the STAGE_PROGRAM comments): "STAGE_CASE_FILE" (a clash that
# involves a file) or "STAGE_CASE_DIR" (two folders), then a TAB, the path, a TAB, and
# the first path of the clash in byte order. The case list never holds a control byte,
# so the fields cannot contain a tab. When there are any, it prints a WARNING naming
# them (at most 20, then "... and N more") for the volume named in $2 and latches
# HAD_WARNINGS. Nothing is removed on macOS -- the names are legal here -- but the
# default macOS disk format is case-insensitive, so one name of each pair can overwrite
# the other when the backup lands (or, for a file and a folder, stop the copy, which the
# zero-tolerance count check then reports). WARNING to stderr like the others.
#
# $3 = 1 when the caller EXPECTS the list: casewarn mode and a staging run that exited
# 0. Such a run always ends its log with STAGED_FILES= (or STAGED_COUNT_ERRORS= when
# its count hit read errors), printed AFTER the case lines, so a log without either
# final marker could not be read back (`docker logs` failed, came back empty, or was
# cut short) and case-only pairs may be in the backup unnamed. That prints its own
# WARNING and latches, twin of the .ps1's unreadable-list WARNING (which keys on its
# win-mode STAGED_STRIPPED_NAMES marker; casewarn mode prints no such marker). Never on
# Linux: the callers pass 1 only when STAGE_NAMES_MODE is set. $4 = the volume's mount
# point inside the DAAF container when it is not /daaf (the Claude Code state volume),
# for the next step: the invariants checker walks /daaf unless DAAF_INVARIANT_ROOT says
# otherwise. Both hints pass --names-only, which runs only the checker's names check:
# its symlink and repo-root checks are DAAF-folder rules that flag files belonging in
# Claude Code's folder and say to delete them.
_daaf_case_report() {
    local log="$1" where="$2" expect="${3:-0}" check_root="${4:-}" tab lines n
    tab="$(printf '\t')"
    # grep reads the whole log (no -q): an early -q exit could SIGPIPE printf, and
    # pipefail would then turn a found marker into a false "could not read".
    if [ "${expect}" = "1" ] && ! printf '%s\n' "${log}" | grep -E '^STAGED_(FILES|COUNT_ERRORS)=[0-9]+$' > /dev/null; then
        echo "" >&2
        echo "WARNING: Could not read the list of paths in the ${where} that differ only in upper/lower" >&2
        echo "         case, so such pairs may be in this backup without being named here (this Mac's" >&2
        echo "         disk most likely keeps only one of each pair). Re-run the backup; if this warning" >&2
        if [ -z "${check_root}" ]; then
            echo "         comes back, list such names inside DAAF with:" >&2
            echo "           bash scripts/check_workspace_invariants.sh --names-only" >&2
        else
            echo "         comes back, list such names inside DAAF with:" >&2
            echo "           DAAF_INVARIANT_ROOT=${check_root} bash scripts/check_workspace_invariants.sh --names-only" >&2
        fi
        HAD_WARNINGS=1
    fi
    lines="$(printf '%s\n' "${log}" | grep -E "^STAGE_CASE_(FILE|DIR)${tab}" || true)"
    [ -n "${lines}" ] || return 0
    n="$(printf '%s\n' "${lines}" | grep -c .)" || n=0
    echo "" >&2
    echo "WARNING: ${n} path(s) in the ${where} are the same as another path except for upper/lower" >&2
    echo "         case (like ./Data/x and ./data/x). This Mac's disk most likely treats each pair as ONE" >&2
    echo "         path, so the backup may keep only one of them (or the copy may stop early):" >&2
    printf '%s\n' "${lines}" | head -n 20 | while IFS="${tab}" read -r _ path first; do
        echo "           ${path}   (same as ${first} except for upper/lower case)" >&2
    done || true
    if [ "${n}" -gt 20 ]; then echo "           ... and $(( n - 20 )) more" >&2; fi
    echo "         Rename one name of each pair inside DAAF, then back up again." >&2
    HAD_WARNINGS=1
}

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            "version --format"*) echo "29.1.3 29.1.3"; return 0 ;;
            "image inspect "*) return 0 ;;
            *"volume inspect"*) return 0 ;;
            *"run --rm"*"find /source"*)
                # Scan: file count, du -sk, du -sh, logical KB, special-file count
                # (nonzero so the dry-run exercises the skipped-special-files note).
                printf '100\n1024\t/source\n1M\t/source\n1024\n2\n'
                return 0
                ;;
            "run -d"*)
                # Staging container launch (symlink strip) -- emit a fake CID.
                echo "stagecid0000"
                return 0
                ;;
            "wait"*) echo "0"; return 0 ;;
            "logs "*)
                # Staging log after a clean `docker wait`: the snapshot count markers
                # (the dry run exits before staging; modeled so the parse stays
                # compatible if the early exit ever moves).
                printf 'STAGED_FILES=100\nSTAGED_KB=1024\n'
                return 0
                ;;
            *)
                # The dry-run path exits before any cp/rm or the staging step's
                # cp/wait, so no match arm is needed for the copy mechanism -- the
                # default is only reached for unmodeled calls, which are echoed and
                # treated as no-ops.
                echo "[DRY-RUN] docker $*" >&2
                return 0
                ;;
        esac
    }
fi

# --- Test Mode Guard ---
# When sourced for testing, define functions but skip execution.
# Usage: DAAF_TEST_MODE=1 source scripts/host/backup_daaf.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

echo ""
echo "=========================================="
echo "  DAAF Backup"
echo "=========================================="
echo ""

# --- Preflight ---
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal."
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again."
    # Old-Engine hint (F1; review round 9): a client of 25 or newer that cannot talk to an
    # Engine older than 25.0 (Docker 29 removed the older API versions) also fails
    # `docker info`, so the version check below is never reached. Read the versions
    # (stdout only, the last non-empty line); when the client's major reads as 25 or newer
    # and the Engine's version is empty or cannot be read, add a hint. The message above and
    # the exit code stay the same (and its stream: stdout here, as above). Same text as the
    # .ps1 twin and restore_from_backup.{sh,ps1}.
    DOCKER_INFO_FAIL_LINE="$(docker version --format '{{.Client.Version}} {{.Server.Version}}' 2>/dev/null | tr -d '\r' | awk 'NF {l=$0} END {print l}')" || true
    DOCKER_INFO_FAIL_CLIENT="$(printf '%s\n' "${DOCKER_INFO_FAIL_LINE}" | awk '{print $1}')"
    DOCKER_INFO_FAIL_SERVER="$(printf '%s\n' "${DOCKER_INFO_FAIL_LINE}" | awk '{print $2}')"
    DOCKER_INFO_FAIL_CLIENT_MAJOR="${DOCKER_INFO_FAIL_CLIENT%%.*}"
    DOCKER_INFO_FAIL_SERVER_MAJOR="${DOCKER_INFO_FAIL_SERVER%%.*}"
    case "${DOCKER_INFO_FAIL_CLIENT_MAJOR}" in
        ''|*[!0-9]*|??????*) ;;
        *)
            if [ "${DOCKER_INFO_FAIL_CLIENT_MAJOR}" -ge 25 ]; then
                case "${DOCKER_INFO_FAIL_SERVER_MAJOR}" in
                    ''|*[!0-9]*|??????*)
                        echo "       If Docker is running, its Docker Engine may be older than 25.0 (Docker client ${DOCKER_INFO_FAIL_CLIENT})."
                        echo "       The backup needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer)."
                        ;;
                esac
            fi
            ;;
    esac
    exit 1
fi

# --- Docker version check (F1 compatibility; audit 04, section 3) ---
# Docker 29 removed API versions below 1.44: a 29.x client cannot drive an Engine older
# than 25.0, and a 29.0-29.2 Engine refuses an older client. So read both versions
# (stdout only, the last non-empty line) and refuse, before anything is created, when
# either side's major version is below 25 or cannot be read. A major other than the
# tested 29 only prints a NOTE (no HAD_WARNINGS latch) and continues. Same rule and
# wording as the .ps1 twin and restore_from_backup.{sh,ps1} (script name varied).
DOCKER_VERSION_LINE="$(docker version --format '{{.Client.Version}} {{.Server.Version}}' 2>/dev/null | tr -d '\r' | awk 'NF {l=$0} END {print l}')" || true
DOCKER_CLIENT_VERSION="$(printf '%s\n' "${DOCKER_VERSION_LINE}" | awk '{print $1}')"
DOCKER_SERVER_VERSION="$(printf '%s\n' "${DOCKER_VERSION_LINE}" | awk '{print $2}')"
DOCKER_VERSION_STATE="ok"
for docker_v in "${DOCKER_CLIENT_VERSION}" "${DOCKER_SERVER_VERSION}"; do
    docker_major="${docker_v%%.*}"
    case "${docker_major}" in
        ''|*[!0-9]*|??????*) DOCKER_VERSION_STATE="unreadable" ;;
        *)
            if [ "${docker_major}" -lt 25 ]; then
                if [ "${DOCKER_VERSION_STATE}" != "unreadable" ]; then DOCKER_VERSION_STATE="old"; fi
            elif [ "${docker_major}" -ne 29 ] && [ "${DOCKER_VERSION_STATE}" = "ok" ]; then
                DOCKER_VERSION_STATE="untested"
            fi
            ;;
    esac
done
if [ "${DOCKER_VERSION_STATE}" = "old" ] || [ "${DOCKER_VERSION_STATE}" = "unreadable" ]; then
    if [ "${DOCKER_VERSION_STATE}" = "old" ]; then
        echo "ERROR: This Docker version is too old for the backup (Docker client ${DOCKER_CLIENT_VERSION:-unknown}, Docker Engine ${DOCKER_SERVER_VERSION:-unknown})." >&2
    else
        echo "ERROR: Could not read the Docker version (Docker client ${DOCKER_CLIENT_VERSION:-unknown}, Docker Engine ${DOCKER_SERVER_VERSION:-unknown})." >&2
    fi
    echo "       The backup needs Docker 25.0 or newer, for both the Docker client and Docker Engine" >&2
    echo "       (Docker Desktop 4.27.1 or newer). Update Docker, then run the backup again." >&2
    echo "       (Docker Desktop or Docker Engine is required; Podman is not supported.)" >&2
    echo "       Nothing was changed." >&2
    exit 1
fi
if [ "${DOCKER_VERSION_STATE}" = "untested" ]; then
    echo "NOTE: The backup has not been tested with this Docker version (Docker client ${DOCKER_CLIENT_VERSION}, Docker Engine ${DOCKER_SERVER_VERSION}; tested: 29). Continuing."
    echo ""
fi

# Check the volume exists
if ! docker volume inspect "${VOLUME_NAME}" &> /dev/null; then
    echo "ERROR: Docker volume '${VOLUME_NAME}' not found."
    echo "Have you run the DAAF installer yet?"
    exit 1
fi

# --- Helper image check (F1 compatibility; audit 04, section 3) ---
# Every container step runs the pinned ${BUSYBOX_IMAGE}. Make sure it is on this computer
# NOW, before the backup folder is created and before the long scan and staging steps:
# when it is missing, download it here with its progress showing, so an offline computer
# is refused with nothing changed instead of failing partway (`docker run` exits 125
# when it cannot pull). Docker's last stderr line is shown when the download fails. Same
# as the .ps1 twin and restore_from_backup.{sh,ps1}.
if ! docker image inspect "${BUSYBOX_IMAGE}" > /dev/null 2>&1; then
    echo "Downloading the small helper image busybox that the backup needs..."
    BUSYBOX_PULL_EXIT=0
    # stdout (the progress) to the terminal through fd 3; stderr captured.
    { BUSYBOX_PULL_SAID="$(docker pull "${BUSYBOX_IMAGE}" 2>&1 1>&3 3>&-)"; } 3>&1 || BUSYBOX_PULL_EXIT=$?
    if [ "${BUSYBOX_PULL_EXIT}" -ne 0 ]; then
        BUSYBOX_PULL_SAID="$(printf '%s\n' "${BUSYBOX_PULL_SAID}" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep . | tail -n 1)" || true
        echo "" >&2
        echo "ERROR: The backup needs the small helper image busybox and could not download it." >&2
        echo "       Check the internet connection and that Docker Desktop is running, then run the backup again." >&2
        if [ -n "${BUSYBOX_PULL_SAID}" ]; then echo "       Docker said: ${BUSYBOX_PULL_SAID}" >&2; fi
        echo "       Nothing was changed." >&2
        exit 1
    fi
    echo ""
fi

# --- Generate date-versioned backup name ---
BACKUP_NAME="${TODAY}_daaf_backup"

if [ -e "${BACKUP_NAME}" ]; then
    # First backup of the day already exists -- find next available suffix
    SUFFIX_NUM=0
    while true; do
        # Convert number to letter: 0=a, 1=b, 2=c, ...
        SUFFIX=$(printf "\\$(printf '%03o' $((97 + SUFFIX_NUM)))")
        BACKUP_NAME="${TODAY}${SUFFIX}_daaf_backup"
        if [ ! -e "${BACKUP_NAME}" ]; then
            break
        fi
        SUFFIX_NUM=$((SUFFIX_NUM + 1))
        if [ "${SUFFIX_NUM}" -ge 26 ]; then
            echo "ERROR: Too many backups for today (26 max). Please remove some old backups."
            exit 1
        fi
    done
fi

echo "Backup name: ${BACKUP_NAME}/"
# Name the volume being copied (the resolved name, so DAAF_PROJECT_NAME and the
# DAAF_DATA_VOLUME_NAME override both show; twin of the .ps1 line). With more than
# one install on a machine, nothing else in the output said which volume a backup
# came from.
echo "Source volume: ${VOLUME_NAME}"
echo ""

# --- Count source files ---
echo "Scanning Docker volume..."
# Scan output, one value per line (line order is a parsing contract shared with the
# .ps1 twin -- append new lines at the END only): 1 regular-file count, 2 `du -sk`,
# 3 `du -sh`, 4 logical KB, 5 special-file count (named pipes, sockets, block/char
# device nodes -- the set the staging program deletes). Line 6 is RESERVED: the .ps1
# twin appends a Windows long-path count there (files whose path in the backup folder
# will be 260+ characters). This twin does not emit it -- macOS/Linux have no such
# limit. A future value shared by both twins goes at line 7, with this twin then
# emitting a placeholder at 6 so the indices stay aligned.
# tests/bash/backup_daaf.bats runs this program and pins exactly 5 output lines.
# Lines 1 and 4 use the SNAPSHOT COUNT's `find` predicate and one-line-per-file
# counting (see STAGE_PROGRAM below): run from /source, the root ".daaf-symlinks",
# ".daaf-permissions" and ".daaf-claude-config" subtree are excluded, and one `find
# -exec stat -c %s {} + | awk` pass yields "<files> <KB>" into `c` (a `find | wc -l`
# would count a name holding a newline twice). So a "Snapshot: N files (M fewer than
# the scan ...)" difference is genuine live-volume change, not a predicate gap, and on
# the fallback path the scan is a like-for-like expected count. The names are
# hardcoded literals (SYNC NOTE: update them by hand if SYMLINKS_MANIFEST,
# PERMISSIONS_MANIFEST or CLAUDE_SUBDIR changes); tests/bash/backup_twin_parity.bats
# pins the predicate against the .ps1 twin's scan and the snapshot count.
SCAN_OUTPUT=$(docker run --rm -v "${VOLUME_NAME}:/source:ro" "${BUSYBOX_IMAGE}" sh -c 'cd /source && c=$(find . -type f ! -path ./.daaf-symlinks ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + | awk "{n++; s+=\$1} END {print n+0, int(s/1024)}") && echo ${c% *} && du -sk /source && du -sh /source && echo ${c#* } && find /source \( -type p -o -type s -o -type b -o -type c \) | wc -l') || {
    echo ""
    echo "ERROR: Could not scan Docker volume."
    exit 1
}
TOTAL_FILES=$(echo "${SCAN_OUTPUT}" | head -1 | tr -d '[:space:]')
VOLUME_SIZE_KB=$(echo "${SCAN_OUTPUT}" | sed -n '2p' | awk '{print $1}')
TOTAL_SIZE=$(echo "${SCAN_OUTPUT}" | sed -n '3p' | awk '{print $1}')
VOLUME_LOGICAL_KB=$(echo "${SCAN_OUTPUT}" | sed -n '4p' | tr -d '[:space:]')
# Line 5 is informational only: a missing or non-numeric value (e.g. a mock that
# emits the older 4-line scan) reads as 0 rather than failing the backup. Special
# files are never regular files, so they are already outside TOTAL_FILES and the
# file-count verification below is unaffected by skipping them.
SPECIAL_FILES=$(echo "${SCAN_OUTPUT}" | sed -n '5p' | tr -d '[:space:]')
case "${SPECIAL_FILES}" in
    ''|*[!0-9]*) SPECIAL_FILES=0 ;;
esac
echo "Found ${TOTAL_FILES} files to copy (${TOTAL_SIZE})."
if [ "${SPECIAL_FILES}" -gt 0 ]; then
    echo "Note: skipping ${SPECIAL_FILES} named pipe/socket/device file(s) -- runtime-only, not backed up."
fi
echo ""

# --- Disk space pre-check ---
# This checks free space on the HOST drive where the backup folder lands. Note it
# does NOT cover the staging step's transient cost: staging `cp -a /source /staging`
# inside the throwaway container roughly DOUBLES the volume's footprint on the Docker
# VM's own internal disk (the Docker Desktop disk image), which is invisible to this
# host-drive check. If that internal disk is full, staging fails and the fatal
# staging-failure error below points the user at the Docker Desktop disk image.
AVAILABLE_KB=$(df -P . | awk 'NR==2 {print $4}')
# Add 10% buffer to account for filesystem overhead
REQUIRED_KB=$(( VOLUME_SIZE_KB * 110 / 100 ))
if [ "${AVAILABLE_KB}" -lt "${REQUIRED_KB}" ]; then
    echo "ERROR: Insufficient disk space for backup." >&2
    echo "       Required: ~$(( REQUIRED_KB / 1024 )) MB (includes 10% buffer), Available: $(( AVAILABLE_KB / 1024 )) MB" >&2
    exit 1
fi

# --- Dry-run early exit ---
# The mock docker copy creates no files, so file-count verification would fail.
# Exit after validating the full pre-backup logic path.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo ""
    echo "[DRY-RUN] Would create backup at: $(pwd)/${BACKUP_NAME}/"
    echo "[DRY-RUN] Source: ${TOTAL_FILES} files (${TOTAL_SIZE}), Space required: ~$((REQUIRED_KB / 1024)) MB"
    exit 0
fi

# --- Create backup ---
mkdir -p "${BACKUP_NAME}"

# Copy the data volume out via a STAGING container + `docker cp`, instead of
# `docker cp`ing the volume directly. On Windows hosts, `docker cp`'s host-side
# extraction ABORTS the instant it meets a symlink it cannot create (symlink
# creation needs admin/Developer Mode), silently truncating the archive stream and
# dropping every file that sorts after the failing link. To make the tree
# `docker cp` streams symlink-free, first stage the volume into a throwaway busybox
# container: `cp -a /source /staging` freezes the tree, two `find` passes record
# each symlink's path and target line-for-line (identical traversal order, so
# `paste` pairs them exactly -- the `cp -a` freeze is a correctness requirement,
# not an optimization) into the ".daaf-symlinks" manifest at the staging root, and
# `find -type l -exec rm` strips the links. Restore replays the manifest.
#
# The final `find` then deletes special files (`-type p` named pipes, `-type s`
# sockets, `-type b`/`-type c` device nodes). For FIFOs and device nodes, Windows
# `docker cp` has the same abort-and-truncate failure as for symlinks: moby's Windows
# archive extractor creates nothing for a FIFO/device entry, then its timestamp step
# (`chtimes`) fails on the missing path and aborts the whole extraction -- after the
# CLI has already printed "Successfully copied" (field failure 2026-09-29, sibling
# project on a variant of this script: a stale provider-shim `output.fifo` stopped a
# Windows backup; last progress reading 94%). Sockets are stripped defensively (how
# Docker archives them was not verified). None of these carry data, so they are
# dropped with NO manifest and restore does not recreate them. The
# grouped `\( ... \)` predicates keep `-exec` bound to all four types; with no
# matches `find` runs no `rm` and exits 0, so `set -e` is safe on a clean volume.
#
# The staged tree `docker cp` streams therefore holds only directories, regular
# files, and the ".daaf-symlinks" manifest.
#
# The staging program contains NO embedded double quotes: it is shared logically
# with the .ps1 twin, where embedded double quotes corrupt Windows arg parsing on
# PS 5.1. Its /tmp writes are inside the throwaway container's own layer (NOT the
# DAAF container's /tmp), so there is no provenance concern.
#
# `docker cp CID:/staging/.` then streams the staged (symlink- and special-file-free) tree host-side
# as the INVOKING user (no -a/--archive), so ownership is correct by construction
# and no chown-repair step is needed. The trailing "/." copies the CONTENTS into
# "${BACKUP_NAME}" rather than nesting a "staging" dir.
#
# FATAL unsupported-character gate: the manifest is a line-based, TAB-separated
# "path<TAB>target" file, and restore replays it by splitting each line on the first
# tab. Two characters embedded in a symlink's own path or target silently corrupt
# that contract: (1) a TAB in a name shifts the field boundary, so restore parses the
# wrong path/target; (2) a NEWLINE in a name splits one logical entry across multiple
# lines, which also desyncs `paste` (it pairs path line N with target line N) for
# every entry after it. Neither is detectable at restore time. So gate HERE, loudly:
# a true link count immune to newlines is `find . -type l -exec printf x ;` (one x per
# link, counted by `wc -c`); if either `wc -l` of link_paths/link_targets disagrees
# with it, a name holds a newline. A literal tab in either file is caught by grep. Any
# hit exits nonzero, which trips the fatal staging-failure path host-side (see the
# `docker wait` status check below) -- so NO corrupt manifest is ever written. On a
# hit the gate first NAMES the offenders to STDOUT before `exit 3`: the tab branch
# prints the matching lines (`grep -f` without `-q`, re-using the pattern file); the
# newline branch cannot isolate the culprit from mismatched line counts, so it prints
# the whole (typically short) symlink path list under a "one of these embeds a
# newline" header. The driver relays that STDOUT to the user via `docker logs` on the
# failure path below (the staging container is detached, so its output would
# otherwise be lost). WHY STDOUT, not stderr: on a real Windows host, PS 5.1's
# native-command `2>&1` merge dropped the staging container's stderr, so the offender
# list never reached the user's terminal (field failure 2026-07-14). The staging
# program's stdout is otherwise unused (`docker run -d` detaches; the CID comes from
# the daemon, not the program), and stdout survives `docker logs` retrieval on every
# PowerShell version -- stderr was the fragile leg. The `\\t` / `\\011`
# double-backslash forms survive the single-quote string so the container `sh` hands
# printf ONE backslash (mirrors the restore-replay octal idiom); the echo/cat/grep
# offender lines add no printf escapes and stay quote-free for PS 5.1 twin parity.
#
# SNAPSHOT COUNT: on success only (every earlier step is under `set -e`), the program
# ends by printing STAGED_FILES=<n> and STAGED_KB=<n> to STDOUT -- the regular files of
# the FROZEN staged tree the copy streams, with the source scan's logical-KB formula
# (sum of `stat -c %s`, int(s/1024)). The source scan runs on the LIVE volume before
# `cp -a`, so it can drift from what is actually backed up; this count cannot, which
# is what lets the verification below run at ZERO tolerance. The `find` predicate
# excludes exactly what the host-side count below (and the .ps1 twin's
# $BackupCountProgram) excludes: the root manifest, a root ".daaf-permissions", and a
# root ".daaf-claude-config" subtree. Restore's permission replay can leave a stray
# root ".daaf-permissions" in the volume when it fails; counting it on one side only
# produced a false zero-tolerance mismatch. SYNC NOTE: those two names are hardcoded
# literals here (only the symlink manifest is spliced in), so update them by hand if
# PERMISSIONS_MANIFEST or CLAUDE_SUBDIR ever changes.
#
# ONE traversal yields both numbers: `stat -c %s` prints one size line per file (even
# for a name that holds a newline, which `find | wc -l` would count twice) and awk
# prints "<files> <KB>" at END (`n+0` so an empty tree prints 0, not an empty field);
# `${counts% *}` / `${counts#* }` split the pair. The awk program is backslash-escaped
# rather than quoted: the program must stay quote-free (PS 5.1 argv; and a line
# ending in a single quote would end the parity extractor in
# tests/bash/backup_twin_parity.bats). A pipeline's status is its last command's, so
# the count line cannot trip `set -e`, and with no files `find` runs no `stat` and
# awk prints 0 0.
#
# That same rule makes a `find`/`stat` read error SILENT. busybox ash does support
# `set -o pipefail` (BASH_PIPEFAIL = ENABLE_ASH_BASH_COMPAT, and ASH_BASH_COMPAT is
# `default y`; read in the busybox source, not executed under busybox), but this
# program does not turn it on, so awk would print a short count and the program would
# exit 0. So the count's stderr goes to /tmp/count_err (the throwaway container's own
# /tmp), and the markers are printed only when it is empty; otherwise
# STAGED_COUNT_ERRORS=<lines> is printed INSTEAD. Missing markers take the existing "Could not read the snapshot's
# file count" fallback below; the `if` never fails `set -e`, so staging still exits 0.
#
# UNCREATABLE NAMES (runs right after `cd /staging`, BEFORE the symlink manifest, so a
# symlink inside a removed folder never enters ".daaf-symlinks" and restore's replay
# cannot trip on it; it is also why the pinned tail of the program is untouched). A
# name Windows cannot create makes Windows `docker cp` ABORT mid-extraction and drop
# every later entry (field failure 2026-09-30, Docker Client 29.1.3: `docker cp`
# stopped at a file named `name<LF>nl` -- "The filename, directory name, or volume
# label syntax is incorrect" -- after 72,386 of 73,785 files). The step is switched by
# the DAAF_STAGE_NAMES environment variable, passed with `docker run -e` AFTER the
# `-v` (the program itself stays byte-identical in both twins):
#   win      -- backup_daaf.ps1 ONLY. Removes (rm -rf, so a folder takes its subtree)
#               every non-symlink entry whose own name Windows cannot create: control
#               bytes 0x01-0x1F, any of < > : " | ? * \, a trailing dot or space, and
#               the device names CON PRN AUX NUL COM1-9 LPT1-9 (also COM/LPT with the
#               superscript digits 1-3, CONIN$, CONOUT$), case-insensitively and with
#               any extension. `-prune` keeps a removed folder's children off the list.
#               Then, for each case-insensitive full-path clash that involves a FILE
#               (file+file: Windows silently keeps only one; file+folder: `docker cp`
#               aborts with "cannot overwrite"), keeps the FIRST path in C-locale byte
#               order and removes the others. Folder+folder clashes are LISTED only
#               (Windows merges them; clashing children are caught at the full-path
#               level). Prints STAGE_STRIP_NAME / STAGE_CASE_FILE / STAGE_CASE_DIR lines
#               and STAGED_STRIPPED_NAMES=<entries> / STAGED_STRIPPED_FILES=<regular files
#               removed, counted with the snapshot predicate> BEFORE the final markers,
#               so the markers stay last (last-match-wins parsing).
#   casewarn -- this twin on macOS (Darwin). LISTS case-only clashes (the macOS disk is
#               case-insensitive by default), removes nothing.
#   empty    -- this twin on Linux: the step does not run (these names are legal on
#               macOS/Linux disks, so they are never removed there).
# Symlinks are never removed here (`! -type l`): they are stripped into the manifest
# below as before, and the fatal tab/newline symlink gate still applies to them.
# Hostile names cannot spoof a marker: every listed path follows a fixed prefix on its
# own line, and `tr` turns NUL separators into newlines and every control byte 0x01-0x1F
# inside a name (newline, CR, tab, ESC ...) into `?` (32 bytes in, 32 out: \012 plus
# the 31 `?` in Q). The case list excludes control-byte paths (`! -path $C`: in win mode
# they are already gone), so its tab-separated "prefix, path, first path" lines are
# unambiguous. The step runs in a subshell with `set -f` (the bracket patterns must not
# glob in /staging), IFS= (no word splitting of the pattern variables) and LC_ALL=C
# (byte ranges, byte sort, ASCII tolower). The awk program is written by a here-document
# (`\$` keeps the dollars literal) and uses no string literals, so the program stays
# free of double quotes; -v passes the words it prints. Tested under dash + GNU
# find/awk/tr/sort (tests/bash/backup_daaf.bats); busybox is not installed in the dev
# image, and a one-shot host probe ran the real program under busybox on Windows
# (2026-10-01, matched exactly: research/2026-09-29_FrameworkDev_BackupLongPathCount/
# 2026-09-30_busybox_host_probe.md). Two busybox differences are designed around from
# its source: (1) busybox `-iname` upcases the NAME when libc lacks
# FNM_CASEFOLD, so every -iname pattern is written in upper case; (2) busybox `find`
# runs the final batch of an `-exec ... {} +` only for actions at the TOP level of the
# expression (flush_exec_plus() walks the top-level OR branches and never looks
# inside `\( \)`; Alpine aports MR !75008), so a batched -exec inside parentheses
# silently never runs for the last -- usually the only -- batch. The case listing
# therefore uses two top-level OR branches, each with its own `! -path $C`, instead of
# a parenthesized group (identical output under GNU find), and
# tests/bash/backup_twin_parity.bats fails on any `{} +` inside `\( \)` in these
# container programs.
STAGE_PROGRAM='set -e
cp -a /source /staging
cd /staging
if [ ${DAAF_STAGE_NAMES:-0} = win ] || [ ${DAAF_STAGE_NAMES:-0} = casewarn ]; then
(
set -f
IFS=
export LC_ALL=C
C=$(printf \\052[\\001-\\037]\\052)
R=$(printf \\052[\\074\\076:\\042\\174?\\052\\134\\134]\\052)
S=$(printf \\302[\\262\\263\\271])
Q=$(printf %31s | tr \\040 \\077)
T=$(printf \\011)
M=0
: > /tmp/name_list
: > /tmp/case_strip
if [ $DAAF_STAGE_NAMES = win ]; then
M=1
before=$(find . -type f ! -path ./'"${SYMLINKS_MANIFEST}"' ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + | wc -l)
find . -mindepth 1 ! -type l \( -name $C -o -name $R -o -name \*[.\ ] \
-o -iname CON -o -iname CON.\* -o -iname PRN -o -iname PRN.\* -o -iname AUX -o -iname AUX.\* \
-o -iname NUL -o -iname NUL.\* -o -iname COM[1-9] -o -iname COM[1-9].\* -o -iname LPT[1-9] -o -iname LPT[1-9].\* \
-o -iname COM$S -o -iname COM$S.\* -o -iname LPT$S -o -iname LPT$S.\* \
-o -iname CONIN\$ -o -iname CONIN\$.\* -o -iname CONOUT\$ -o -iname CONOUT\$.\* \) \
-prune -print0 -exec rm -rf {} + > /tmp/name_list
fi
cat > /tmp/case_awk <<EOF
{ p = substr(\$0, 1, length(\$0) - 2); t = substr(\$0, length(\$0)); k = tolower(p) }
!(k in first) { first[k] = p; ft[k] = t; next }
{ q = p; while (match(q, /\/[^\/]*\$/)) { q = substr(q, 1, RSTART - 1); if (q in gone) next } }
t == D && ft[k] == D { print PD, p, first[k]; next }
{ print PF, p, first[k] }
M == 1 { print p > F; if (t == D) gone[p] = 1 }
EOF
find . -mindepth 1 ! -path $C -type d -exec printf %s\\011d\\n {} + -o ! -path $C -type f -exec printf %s\\011f\\n {} + | sort > /tmp/case_sorted
awk -v D=d -v PD=STAGE_CASE_DIR -v PF=STAGE_CASE_FILE -v M=$M -v F=/tmp/case_strip -v OFS=$T -f /tmp/case_awk /tmp/case_sorted
while read -r p; do rm -rf -- $p; done < /tmp/case_strip
if [ $M = 1 ]; then
after=$(find . -type f ! -path ./'"${SYMLINKS_MANIFEST}"' ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + | wc -l)
tr \\000\\001-\\037 \\012$Q < /tmp/name_list | sed s/^/STAGE_STRIP_NAME$T/
n1=$(tr -dc \\000 < /tmp/name_list | wc -c)
n2=$(wc -l < /tmp/case_strip)
echo STAGED_STRIPPED_NAMES=$((n1 + n2))
echo STAGED_STRIPPED_FILES=$((before - after))
fi
)
fi
find . -type l > /tmp/link_paths
find . -type l -exec readlink {} \; > /tmp/link_targets
printf \\011 > /tmp/tab_pat
true_links=$(find . -type l -exec printf x \; | wc -c)
path_lines=$(wc -l < /tmp/link_paths)
target_lines=$(wc -l < /tmp/link_targets)
if [ $true_links -ne $path_lines ] || [ $true_links -ne $target_lines ]; then
echo STAGE_ERR_NEWLINE
echo One of these symlink names embeds a newline -- rename or remove the offending link:
cat /tmp/link_paths
exit 3
fi
if grep -qf /tmp/tab_pat /tmp/link_paths || grep -qf /tmp/tab_pat /tmp/link_targets; then
echo STAGE_ERR_TAB
echo These symlink paths or targets embed a tab -- rename or remove the offending link:
grep -f /tmp/tab_pat /tmp/link_paths || true
grep -f /tmp/tab_pat /tmp/link_targets || true
exit 3
fi
paste /tmp/link_paths /tmp/link_targets > /staging/'"${SYMLINKS_MANIFEST}"'
find /staging -type l -exec rm -f {} +
find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +
counts=$(find . -type f ! -path ./'"${SYMLINKS_MANIFEST}"' ! -path ./.daaf-permissions ! -path ./.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | awk \{n++\;s+=\$1\}\ END\ \{print\ n+0,int\(s/1024\)\})
if test -s /tmp/count_err; then
echo STAGED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err)
else
echo STAGED_FILES=${counts% *}
echo STAGED_KB=${counts#* }
fi'

echo "Preparing volume snapshot (staging + symlink strip)... (this may take a while for large volumes)"
# Launch the staging container detached and wait for it. `docker run -d` returns a
# CID immediately; `docker wait` blocks until the staging program finishes and
# prints its exit status, which MUST be checked -- a nonzero status means staging
# failed before any host bytes were written, so the backup aborts fatally (nothing
# useful was produced). Install the interrupt trap right after the CID exists so an
# INT/TERM removes the container.
# Guard the launch explicitly: under `set -e`, an unguarded `STAGE_CID="$(docker
# run -d ...)"` would abort the whole script with NO message if `docker run` failed
# -- and the backup dir was already `mkdir`ed above, so the user would be left with
# an empty backup folder and no explanation. Capture into STAGE_CID inside the `if`
# so a launch failure falls into the fatal ERROR path below (precedent:
# restore_from_backup.sh's `if ! CID="$(docker create ...)"` guard).
if ! STAGE_CID="$(docker run -d -v "${VOLUME_NAME}:/source:ro" -e "DAAF_STAGE_NAMES=${STAGE_NAMES_MODE}" "${BUSYBOX_IMAGE}" sh -c "${STAGE_PROGRAM}")"; then
    echo "" >&2
    echo "ERROR: Could not start the staging container for a symlink-safe backup." >&2
    echo "       No backup files were written. Check Docker Desktop for errors and re-run." >&2
    # Best-effort reap: `docker run -d` can fail AFTER creating the container
    # (Created/Exited state) while still printing its CID to stdout, which the
    # command substitution above captured -- remove it so a launch failure does not
    # leak a helper container (mirrors backup_daaf.ps1's stage-start cleanup). The
    # `${STAGE_CID:-}` guard makes this a harmless no-op if no CID was captured.
    docker rm -f "${STAGE_CID:-}" > /dev/null 2>&1 || true
    exit 1
fi
trap 'docker rm -f "${STAGE_CID:-}" > /dev/null 2>&1 || true' INT TERM
STAGE_STATUS="$(docker wait "${STAGE_CID}" 2>/dev/null || echo 1)"
if [ "${STAGE_STATUS}" != "0" ]; then
    # The staging container is DETACHED (`docker run -d`), so the gate's STDOUT --
    # including the offender list it prints on an exit-3 -- went to the container
    # log, NOT this terminal. Fetch and show that log BEFORE `docker rm -f` removes
    # the container (order matters: after removal the log is gone). Best-effort: a
    # `docker logs` failure must not mask the original staging error. (The gate prints
    # offenders to STDOUT, not stderr: PS 5.1's native `2>&1` merge dropped the
    # container's stderr in the field 2026-07-14, so the offender list never reached
    # the user; stdout is version-agnostic. The `2>&1` here still merges both streams
    # into the log for completeness.)
    STAGE_LOG="$(docker logs "${STAGE_CID}" 2>&1 || true)"
    docker rm -f "${STAGE_CID}" > /dev/null 2>&1 || true
    trap - INT TERM
    echo "" >&2
    echo "ERROR: Failed to stage the Docker volume for a symlink-safe backup (exit ${STAGE_STATUS})." >&2
    echo "       No backup files were written." >&2
    echo "" >&2
    echo "Details from the staging scan:" >&2
    if [ -n "${STAGE_LOG}" ]; then
        printf '%s\n' "${STAGE_LOG}" | sed 's/^/       /' >&2
    else
        # Empty/whitespace log: label the silence rather than omit the block, so a
        # future stream regression is visible rather than ambiguous.
        echo "       (no details could be retrieved from the staging container)" >&2
    fi
    echo "" >&2
    echo "       Exit 3 means a symlink's path or target contains an unsupported" >&2
    echo "       character (a TAB or a NEWLINE), which would corrupt the symlink" >&2
    echo "       manifest -- rename or remove the offending symbolic link named above" >&2
    echo "       and re-run." >&2
    echo "       Otherwise, staging can also fail if the Docker Desktop disk image is" >&2
    echo "       full (staging transiently duplicates the volume inside it); check" >&2
    echo "       Docker Desktop for errors, free space, and re-run." >&2
    exit 1
fi

# --- Snapshot count (the verification target) ---
# Staging exited 0, so its last step printed STAGED_FILES/STAGED_KB to STDOUT (see
# SNAPSHOT COUNT above). The container is detached, so its log is the only channel:
# read it now, before the `docker rm -f` after the copy. When both markers parse
# (anchored, digits only), the snapshot is the expected count and verification is
# exact (zero tolerance); otherwise (including a count that hit read errors and
# printed STAGED_COUNT_ERRORS instead) fall back to the live-volume scan and its 1%
# tolerance, and say so -- a Note, not a warning: the copy itself is unaffected.
STAGE_DONE_LOG="$(docker logs "${STAGE_CID}" 2>/dev/null | tr -d '\r')" || STAGE_DONE_LOG=""
STAGED_FILES="$(printf '%s\n' "${STAGE_DONE_LOG}" | sed -n 's/^STAGED_FILES=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
STAGED_KB="$(printf '%s\n' "${STAGE_DONE_LOG}" | sed -n 's/^STAGED_KB=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
# Regular files the staging step removed because their names cannot be created on the
# destination (see UNCREATABLE NAMES above; only the .ps1 twin's "win" mode removes
# any, so this is 0 here in practice -- parsed anyway so both twins do the same
# snapshot arithmetic). They were in the scan but are not in the snapshot, so they are
# subtracted before the difference is blamed on live-volume change.
STAGED_STRIPPED_FILES="$(printf '%s\n' "${STAGE_DONE_LOG}" | sed -n 's/^STAGED_STRIPPED_FILES=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
if [ -z "${STAGED_STRIPPED_FILES}" ]; then STAGED_STRIPPED_FILES=0; fi
if [ -n "${STAGED_FILES}" ] && [ -n "${STAGED_KB}" ]; then
    HAVE_STAGED_COUNTS=1
    EXPECTED_FILES="${STAGED_FILES}"
    EXPECTED_KB="${STAGED_KB}"
    SNAPSHOT_ACCOUNTED=$(( STAGED_FILES + STAGED_STRIPPED_FILES ))
    if [ "${STAGED_STRIPPED_FILES}" -gt 0 ]; then
        echo "Snapshot: ${STAGED_FILES} files (${STAGED_STRIPPED_FILES} more left out because their names cannot be"
        echo "          created on this computer -- see the WARNING after the copy)."
    fi
    if [ "${SNAPSHOT_ACCOUNTED}" -eq "${TOTAL_FILES}" ]; then
        if [ "${STAGED_STRIPPED_FILES}" -eq 0 ]; then
            echo "Snapshot: ${STAGED_FILES} files."
        fi
    else
        # Net change only: the scan saw the live volume moments before `cp -a` froze it
        # (the scan's line 1 uses the snapshot's own predicate, so this is real change).
        if [ "${SNAPSHOT_ACCOUNTED}" -gt "${TOTAL_FILES}" ]; then
            SNAPSHOT_DELTA="$(( SNAPSHOT_ACCOUNTED - TOTAL_FILES )) more"
        else
            SNAPSHOT_DELTA="$(( TOTAL_FILES - SNAPSHOT_ACCOUNTED )) fewer"
        fi
        if [ "${STAGED_STRIPPED_FILES}" -gt 0 ]; then
            echo "          Apart from those, the snapshot has ${SNAPSHOT_DELTA} files than the scan -- the live"
            echo "          volume changed in between; the snapshot is what gets backed up."
        else
            echo "Snapshot: ${STAGED_FILES} files (${SNAPSHOT_DELTA} than the scan -- the live volume changed in"
            echo "          between; the snapshot is what gets backed up)."
        fi
    fi
else
    HAVE_STAGED_COUNTS=0
    EXPECTED_FILES="${TOTAL_FILES}"
    EXPECTED_KB="${VOLUME_LOGICAL_KB}"
    echo "Note: Could not read the snapshot's file count; verifying against the volume scan"
    echo "      instead (1% tolerance)."
fi

echo "Copying files from Docker volume..."
printf "  Progress: 0 / %d files (0%%)" "${EXPECTED_FILES}"

docker cp "${STAGE_CID}:/staging/." "${BACKUP_NAME}/" &
COPY_PID=$!
# Extend the interrupt trap to also kill the copy child now that it exists.
trap 'if [ -n "${COPY_PID:-}" ]; then kill "${COPY_PID}" 2>/dev/null; wait "${COPY_PID}" 2>/dev/null; fi; docker rm -f "${STAGE_CID:-}" > /dev/null 2>&1 || true' INT TERM

while kill -0 "${COPY_PID}" 2>/dev/null; do
    sleep 3
    if ! kill -0 "${COPY_PID}" 2>/dev/null; then
        break
    fi
    # Progress display only. Counted with the SAME root exclusions as the snapshot it is
    # shown against (_daaf_tree_count, as in the verification below): the staged tree
    # always carries the root ".daaf-symlinks" manifest, which the snapshot excludes, so
    # a plain `find | wc -l` read one high at the end of the copy (the .ps1 twin showed
    # "73848 / 73847" in the field, 2026-10-01) and counted a name holding a newline twice.
    _daaf_tree_count "${BACKUP_NAME}" files
    COPIED="${TREE_COUNT}"
    if [ "${EXPECTED_FILES}" -gt 0 ]; then
        PERCENT=$((COPIED * 100 / EXPECTED_FILES))
        if [ "${PERCENT}" -gt 100 ]; then PERCENT=100; fi
    else
        PERCENT=0
    fi
    printf "\r  Progress: %d / %d files (%d%%)   " "${COPIED}" "${EXPECTED_FILES}" "${PERCENT}"
done

COPY_EXIT=0
wait "${COPY_PID}" || COPY_EXIT=$?

# Remove the staging container. Best-effort: the copy is already done, so a
# failure here must never fail the backup.
docker rm -f "${STAGE_CID}" > /dev/null 2>&1 || true
trap - INT TERM

# Latch for the completion banner: any of the non-fatal WARNING paths below
# (nonzero copy exit code, a backup folder missing its symlink manifest, a
# lower-bound count or size total, file-count mismatch, size mismatch, case-only name
# clashes on macOS or a macOS case list that could not be read, Claude-state copy
# failure, permission-manifest failure) sets this
# so the final banner can say the
# backup completed WITH WARNINGS rather than claiming an unqualified success. The
# exit status stays 0 on those paths -- the banner wording is the signal, not the
# exit code (the corroborated short-copy case below is the one that is fatal, and it
# exits before the banner).
HAD_WARNINGS=0

# --- Symlink-manifest presence ---
# The staging step writes the root ".daaf-symlinks" into EVERY backup (0 bytes when the
# volume has no symlinks), so a copy that lacks it did not finish cleanly -- and
# restore could not recreate this backup's symbolic links. The count below excludes the
# manifest, so without this check a copy that lost only the manifest would pass
# cleanly. Twin of backup_daaf.ps1's missing-manifest WARNING (same wording and next
# step; the .ps1 checks it wherever its container count did not already prove the file
# is there via the BACKUP_SENTINEL marker).
if [ ! -f "${BACKUP_NAME}/${SYMLINKS_MANIFEST}" ]; then
    echo "" >&2
    echo "WARNING: The backup folder is missing its ${SYMLINKS_MANIFEST} file (every backup writes one)," >&2
    echo "         so the copy did not finish cleanly." >&2
    echo "         Re-run the backup; restoring this one would not recreate symbolic links." >&2
    HAD_WARNINGS=1
fi

# --- Verify ---
# The staged tree the copy streamed = volume regular files + 1 symlink manifest
# (symlinks and special files were stripped). Count the host copy with the SAME
# root-relative predicates as the staged count (the root ".daaf-symlinks", a root
# ".daaf-permissions" and the ".daaf-claude-config" subtree are excluded on both), so
# the two are comparable file-for-file, mirroring the .ps1 twin's container-side
# count. The staged count counts one `stat` line per file, so this side counts one
# NUL per file (`-print0`, supported by GNU and BSD find) rather than lines: a name
# holding a newline would otherwise count twice here and trip the zero-tolerance
# check. The completion "files copied" number below is this same data-volume count.
# Host-side `find` is authoritative here: macOS/Linux have no path-length limit that
# could hide files (the .ps1 twin counts inside Docker for exactly that reason). It
# can still hit a READ error (e.g. a folder this user cannot read): _daaf_tree_count
# (see above) then reports a LOWER BOUND, shown as "N+", with the .ps1 twin's
# lower-bound semantics -- a WARNING that latches WITH WARNINGS, never "may be empty",
# never the fatal short-copy branch, and "could not be verified" (exit 1) at 0.
_daaf_tree_count "${BACKUP_NAME}" files
FILE_COUNT="${TREE_COUNT}"
COUNT_IS_LOWER_BOUND="${TREE_COUNT_LOWER_BOUND}"
FILE_COUNT_LABEL="${FILE_COUNT}"
if [ "${COUNT_IS_LOWER_BOUND}" -eq 1 ]; then
    FILE_COUNT_LABEL="${FILE_COUNT}+"
    echo "" >&2
    if [ "${TREE_COUNT_ERRORS:-0}" -gt 0 ]; then
        echo "WARNING: Could not read ${TREE_COUNT_ERRORS} folder(s) or file(s) in the backup folder, so the count" >&2
    else
        echo "WARNING: Could not read the whole backup folder, so the count" >&2
    fi
    echo "         below is a LOWER BOUND (${FILE_COUNT_LABEL} files): the backup may be complete, but this" >&2
    echo "         run could not prove it. Check that your user account can read every folder in it." >&2
    if [ -n "${TREE_COUNT_FIRST_ERROR:-}" ]; then
        echo "         First error: ${TREE_COUNT_FIRST_ERROR}" >&2
    fi
    HAD_WARNINGS=1
fi
# Print the ACTUAL final host-side count, not a fabricated "100%". On a truncated
# copy (the Windows symlink/special-file abort this staging step now prevents, or
# any other partial copy) an unconditional "100%" would lie about completeness.
if [ "${EXPECTED_FILES}" -gt 0 ]; then
    FINAL_PERCENT=$((FILE_COUNT * 100 / EXPECTED_FILES))
    if [ "${FINAL_PERCENT}" -gt 100 ]; then FINAL_PERCENT=100; fi
else
    FINAL_PERCENT=0
fi
printf "\r  Progress: %s / %d files (%d%%)   \n" "${FILE_COUNT_LABEL}" "${EXPECTED_FILES}" "${FINAL_PERCENT}"

# --- Case-only name clashes (macOS) ---
# In "casewarn" mode the staging log lists names that differ only in upper/lower case
# (see UNCREATABLE NAMES). Reported HERE -- right after the final count line and
# BEFORE the two fatal exits below (zero files; corroborated short copy) -- because a
# file+folder clash can itself stop the copy on a case-insensitive disk, and a list
# printed after those exits would never reach the user of the run that needs it
# (review round 7). Printed exactly once per volume. Skipped on Linux, where the step
# does not run. The data-volume staging exited 0 to get here, so the list is expected
# (1): a log without its final marker warns that the list could not be read.
if [ -n "${STAGE_NAMES_MODE}" ]; then
    _daaf_case_report "${STAGE_DONE_LOG}" "Docker volume" 1
fi

# Zero files counted. When that 0 is a LOWER BOUND (the folder could not be read), it
# is not evidence of an empty or failed copy -- nothing could be counted. It still
# exits 1 like the other zero-file cases (twin of the .ps1): an unverifiable backup
# must not pass as good, and exit 1 makes a calling updater or migration stop instead
# of building on it. The wording never suggests the volume is empty.
if [ "${FILE_COUNT}" -eq 0 ]; then
    echo ""
    if [ "${COUNT_IS_LOWER_BOUND}" -eq 1 ]; then
        echo "ERROR: The backup could not be verified: the backup folder could not be read, so no"
        echo "       files could be counted. This does not show the backup is empty, but do not"
        echo "       rely on it. Check that your user account can read the backup folder, then"
        echo "       re-run the backup."
        if [ "${COPY_EXIT}" -ne 0 ]; then
            echo "       The file copy also reported an error (exit code ${COPY_EXIT})."
        fi
    elif [ "${COPY_EXIT}" -ne 0 ]; then
        echo "ERROR: Backup failed (exit code ${COPY_EXIT}). Check Docker Desktop for errors."
    else
        echo "WARNING: Backup completed but 0 files were copied."
        echo "The Docker volume may be empty. Is DAAF properly installed?"
    fi
    echo "Location: $(pwd)/${BACKUP_NAME}/"
    exit 1
fi

# --- Corroborated short-copy check (fatal) ---
# A nonzero docker cp exit AND a copied count short of the expected count (the
# snapshot, or the scan on the fallback path) are two independent signals that
# agree the backup is truncated -- the nonzero exit corroborates the shortfall, so no
# tolerance is applied here. A truncated backup that passed as usable could cost a
# user their data on restore, so fail hard: name the partial folder, tell them to
# delete it, and exit before the completion banner. (A nonzero exit with a FULL count
# falls through to the Note below, which latches the WITH WARNINGS banner -- warnings
# without an actual shortfall.)
#
# LOWER-BOUND count (the folder could not be fully read): not a second signal -- the
# "missing" files may only be unreadable -- so a nonzero exit with a short lower-bound
# count is downgraded to a WARNING (latched, exit 0), as in the .ps1 twin.
if [ "${COPY_EXIT}" -ne 0 ] && [ "${FILE_COUNT}" -lt "${EXPECTED_FILES}" ] && [ "${COUNT_IS_LOWER_BOUND}" -eq 1 ]; then
    echo ""
    echo "WARNING: The file copy reported an error (exit code ${COPY_EXIT}), and only ${FILE_COUNT_LABEL} of ${EXPECTED_FILES}" >&2
    echo "         expected files could be counted. That count is a lower bound (some folders could not" >&2
    echo "         be read), so this run cannot tell whether files are missing. Do not rely on this" >&2
    echo "         backup until a run finishes without this warning." >&2
    HAD_WARNINGS=1
elif [ "${COPY_EXIT}" -ne 0 ] && [ "${FILE_COUNT}" -lt "${EXPECTED_FILES}" ]; then
    echo ""
    echo "ERROR: Backup failed (exit code ${COPY_EXIT}); only ${FILE_COUNT} of ${EXPECTED_FILES} expected files were copied."
    echo "       This backup is incomplete and must not be relied on. Delete this"
    echo "       partial backup folder and re-run once the copy issue is resolved."
    echo "Location: $(pwd)/${BACKUP_NAME}/"
    exit 1
elif [ "${COPY_EXIT}" -ne 0 ]; then
    # A nonzero exit is a copy-reported problem even when the count came up full,
    # so latch the warnings banner: "Backup complete!" would overstate a run the
    # copy itself flagged. Exit status stays 0 (no shortfall, so not fatal).
    echo "Note: File copy reported warnings (exit code ${COPY_EXIT}); ${FILE_COUNT_LABEL} of ${EXPECTED_FILES} expected files were transferred."
    HAD_WARNINGS=1
fi

# --- File-count verification ---
# Do NOT trust docker cp's exit code as the sole failure signal: the Windows
# symlink-abort truncation surfaced with a ZERO exit on the user's run. A nonzero
# exit that ALSO comes up short on the count is already fatal (the corroborated
# short-copy branch above). This block catches the harder case -- a clean ZERO exit
# that still copied the wrong number of files -- and warns loudly (latching the WITH
# WARNINGS banner) on a mismatch in either direction beyond the tolerance below.
#
# ZERO tolerance when the snapshot markers were read: the snapshot is exactly the
# tree `docker cp` streamed and both counts use the same predicates, so any
# difference is a real one (the old 1% tolerance hid a Windows gap of 197 files out
# of 73,031 on 2026-09-29 -- 187 hidden by the PowerShell 5.1 long-path skip, plus 10
# most likely live-volume drift between scan and snapshot -- a volume-vs-backup diff
# found every surviving pre-backup file present -- and a probed FIFO-abort
# truncation of 714 of 71,820 files). The 1% tolerance survives ONLY on the fallback
# path, where the expected count is the live-volume scan and benign drift between
# scan and snapshot is possible, so a mismatch there is only "may be incomplete".
#
# Against the snapshot the wording follows the direction (same structure as the .ps1
# twin; the example file names and the "names this disk cannot store" hint differ by
# platform on purpose): FEWER files is a proven loss; MORE files is not a loss
# (something the snapshot never held landed in the folder, e.g. an OS-added
# .DS_Store), so it still
# latches WITH WARNINGS but says the DAAF data appears complete.
if [ "${HAVE_STAGED_COUNTS}" -eq 1 ]; then
    COUNT_TOLERANCE=0
    EXPECTED_LABEL="Snapshot"
else
    COUNT_TOLERANCE=$(( TOTAL_FILES / 100 ))
    if [ "${COUNT_TOLERANCE}" -lt 1 ]; then COUNT_TOLERANCE=1; fi
    EXPECTED_LABEL="Source"
fi
if [ "${HAVE_STAGED_COUNTS}" -eq 1 ] || [ "${TOTAL_FILES}" -gt 0 ]; then
    COUNT_DIFF=$(( EXPECTED_FILES - FILE_COUNT ))
    if [ "${COUNT_DIFF}" -lt 0 ]; then COUNT_DIFF=$(( -COUNT_DIFF )); fi
    if [ "${COUNT_DIFF}" -gt "${COUNT_TOLERANCE}" ]; then
        # A lower-bound count bounds the difference only one way: a shortfall is "up
        # to" it, an excess is "at least" it (same labels as the .ps1 twin).
        COUNT_DIFF_LABEL="${COUNT_DIFF}"
        if [ "${COUNT_IS_LOWER_BOUND}" -eq 1 ]; then
            if [ "${FILE_COUNT}" -lt "${EXPECTED_FILES}" ]; then COUNT_DIFF_LABEL="up to ${COUNT_DIFF}"; else COUNT_DIFF_LABEL="at least ${COUNT_DIFF}"; fi
            COUNT_DIFF_LABEL="${COUNT_DIFF_LABEL}; the backup count is a lower bound"
        fi
        echo ""
        echo "WARNING: Backup file-count mismatch." >&2
        echo "         ${EXPECTED_LABEL}: ${EXPECTED_FILES} files, Backup: ${FILE_COUNT_LABEL} files (difference: ${COUNT_DIFF_LABEL})" >&2
        if [ "${HAVE_STAGED_COUNTS}" -ne 1 ]; then
            echo "         The backup may be incomplete. Consider re-running." >&2
        elif [ "${FILE_COUNT}" -gt "${EXPECTED_FILES}" ]; then
            echo "         The backup folder holds files that are not in the snapshot, for example" >&2
            echo "         .DS_Store, desktop.ini or Thumbs.db files added by the operating system or a" >&2
            echo "         sync app. The DAAF data itself appears complete." >&2
        elif [ "${COUNT_IS_LOWER_BOUND}" -eq 1 ]; then
            echo "         Some folders could not be read, so this run cannot tell whether these files" >&2
            echo "         are missing or only uncounted. Do not rely on this backup until a run" >&2
            echo "         finishes without this warning." >&2
        else
            echo "         ${COUNT_DIFF} file(s) from the snapshot are missing from this backup. Do not rely on it." >&2
            echo "         One possible cause that re-running will not fix: file names this disk cannot" >&2
            echo "         store side by side, such as names that differ only in upper/lower case on a" >&2
            echo "         case-insensitive disk (the macOS default). On a Mac, any such pairs are listed" >&2
            echo "         in a WARNING above." >&2
        fi
        HAD_WARNINGS=1
    fi
fi

# --- Size verification ---
# Compare expected vs backup logical byte sums (KB) to detect truncated files, with
# the same root-relative exclusions as FILE_COUNT (the ".daaf-symlinks" manifest is
# metadata the volume never held). Same tolerance rule as the file count: zero
# against the snapshot, 1% against the live-volume scan on the fallback path.
# Against the snapshot, a size difference with EQUAL file counts means file contents
# differ, so the wording says not to rely on the backup; with unequal counts it points
# back at the file-count warning.
SOURCE_SIZE_KB="${EXPECTED_KB}"
# A read error makes the size a LOWER BOUND (see _daaf_tree_count), labelled "+" below;
# the file count above already warned when the same folders were unreadable.
_daaf_tree_count "${BACKUP_NAME}" kb
BACKUP_SIZE_KB="${TREE_COUNT}"
SIZE_IS_LOWER_BOUND="${TREE_COUNT_LOWER_BOUND}"
if [ "${SIZE_IS_LOWER_BOUND}" -eq 1 ] && [ "${COUNT_IS_LOWER_BOUND}" -eq 0 ]; then
    # The count pass read everything but the size pass did not (a file changed or
    # became unreadable in between): say so rather than compare silently.
    echo "WARNING: Could not read every file while totalling the backup size; the size check" >&2
    echo "         below uses a lower bound (${BACKUP_SIZE_KB}+ KB)." >&2
    HAD_WARNINGS=1
fi
if [ "${HAVE_STAGED_COUNTS}" -eq 1 ]; then
    TOLERANCE_KB=0
else
    TOLERANCE_KB=$(( SOURCE_SIZE_KB / 100 ))
    if [ "${TOLERANCE_KB}" -lt 1 ]; then TOLERANCE_KB=1; fi
fi
if [ "${HAVE_STAGED_COUNTS}" -eq 1 ] || { [ "${SOURCE_SIZE_KB}" -gt 0 ] && [ "${BACKUP_SIZE_KB}" -gt 0 ]; }; then
    DIFF_KB=$(( SOURCE_SIZE_KB - BACKUP_SIZE_KB ))
    # Absolute value
    if [ "${DIFF_KB}" -lt 0 ]; then DIFF_KB=$(( -DIFF_KB )); fi
    if [ "${DIFF_KB}" -gt "${TOLERANCE_KB}" ]; then
        BACKUP_SIZE_LABEL="${BACKUP_SIZE_KB} KB"
        DIFF_KB_LABEL="${DIFF_KB} KB"
        if [ "${SIZE_IS_LOWER_BOUND}" -eq 1 ]; then
            BACKUP_SIZE_LABEL="${BACKUP_SIZE_KB}+ KB"
            DIFF_KB_LABEL="${DIFF_KB} KB; the backup size is a lower bound"
        fi
        echo ""
        echo "WARNING: Backup size mismatch." >&2
        echo "         ${EXPECTED_LABEL}: ${SOURCE_SIZE_KB} KB, Backup: ${BACKUP_SIZE_LABEL} (difference: ${DIFF_KB_LABEL})" >&2
        if [ "${HAVE_STAGED_COUNTS}" -ne 1 ]; then
            echo "         The backup may be incomplete. Consider re-running." >&2
        elif [ "${SIZE_IS_LOWER_BOUND}" -eq 1 ]; then
            echo "         Some files could not be read, so this run cannot prove the contents match." >&2
            echo "         Do not rely on this backup until a run finishes without this warning." >&2
        elif [ "${FILE_COUNT}" -eq "${EXPECTED_FILES}" ]; then
            echo "         The file counts match, but the file contents differ in size from the" >&2
            echo "         snapshot. Do not rely on this backup." >&2
        else
            echo "         See the file-count mismatch above." >&2
        fi
        HAD_WARNINGS=1
    fi
fi

# --- Back up the Claude Code state volume ---
# Copy the second volume into a dedicated hidden subfolder. This runs AFTER the
# data-volume verification above so the earlier `find "${BACKUP_NAME}"` counts
# are unaffected by these files. If the volume does not exist (older install
# predating it), skip with a note rather than failing -- the data backup is still
# valid on its own.
CLAUDE_BACKED_UP=0
if docker volume inspect "${CLAUDE_VOLUME_NAME}" &> /dev/null; then
    echo ""
    echo "Backing up Claude Code state from volume ${CLAUDE_VOLUME_NAME} (credentials, session history, plugins)..."
    mkdir -p "${BACKUP_NAME}/${CLAUDE_SUBDIR}"
    # Same STAGING mechanism as the data volume above (this volume ALSO carries
    # symlinks -- e.g. codex-daaf/tmp/arg0/... -- which is why the "Failed to back
    # up the Claude Code state volume" warning appeared on Windows: `docker cp`
    # aborted on the first link). Stage into a throwaway container to strip the
    # symlinks into this subfolder's own ".daaf-symlinks" manifest (and delete any
    # special files, unreported here -- the scan above covers the data volume only),
    # then cp the stripped staged tree out. Synchronous (this copy is small). `docker cp`
    # extracts as the invoking user, so the files land user-owned with no chown
    # repair. The manifest lands at "${CLAUDE_SUBDIR}/${SYMLINKS_MANIFEST}"; restore
    # replays it against the claude volume.
    # Guard the launch so a `docker run -d` failure does NOT abort the whole backup
    # under `set -e` -- the Claude backup is best-effort (failure must be a WARNING,
    # never fatal; the data backup above already succeeded). Capture the launch
    # outcome in a SEPARATE flag rather than blanking the CID: `docker run -d` can
    # fail AFTER creating the container (Created/Exited) while still printing its CID,
    # and the old `|| CLAUDE_STAGE_CID=""` discarded that CID before any cleanup could
    # reap it -- leaking the helper container. Keep the captured CID intact so the
    # trap below and the `docker rm -f` at the end of this block can remove it
    # (mirrors backup_daaf.ps1's $claudeStageStartOk flag + finally-reap pattern).
    # Assigning inside the `if` condition keeps `set -e` from aborting on a launch
    # failure while still capturing whatever the substitution produced.
    if CLAUDE_STAGE_CID="$(docker run -d -v "${CLAUDE_VOLUME_NAME}:/source:ro" -e "DAAF_STAGE_NAMES=${STAGE_NAMES_MODE}" "${BUSYBOX_IMAGE}" sh -c "${STAGE_PROGRAM}")"; then
        CLAUDE_STAGE_START_OK=1
    else
        CLAUDE_STAGE_START_OK=0
    fi
    # Re-register an interrupt trap around this block: the data-copy trap was
    # cleared above, so without this a Ctrl-C during the Claude staging/cp window
    # would leak the helper container. Best-effort removal; guarded under set -u.
    trap 'docker rm -f "${CLAUDE_STAGE_CID:-}" > /dev/null 2>&1 || true' INT TERM
    # Only wait on a container that actually launched; a launch failure is treated as
    # a nonzero staging status so control flows into the WARNING path below (with the
    # CID preserved so the reap at the end of this block can remove it).
    if [ "${CLAUDE_STAGE_START_OK}" -eq 1 ]; then
        CLAUDE_STAGE_STATUS="$(docker wait "${CLAUDE_STAGE_CID}" 2>/dev/null || echo 1)"
    else
        CLAUDE_STAGE_STATUS=1
    fi
    # On a staging-gate trip the offender list went to the DETACHED container's log.
    # Capture it now, before the `docker rm -f` below removes the container, so the
    # WARNING branch can relay it. Kept asymmetric with the data volume: this stays a
    # WARNING (best-effort), never fatal. Best-effort fetch (only when staging failed).
    CLAUDE_STAGE_LOG=""
    if [ "${CLAUDE_STAGE_STATUS}" != "0" ]; then
        CLAUDE_STAGE_LOG="$(docker logs "${CLAUDE_STAGE_CID}" 2>&1 || true)"
    fi
    # On a clean staging run in "casewarn" mode (macOS), keep the log for the case-clash
    # report after the copy attempt (same reason: read it before the `docker rm -f` below).
    # CLAUDE_CASE_EXPECT=1 marks exactly that case (casewarn + staging exited 0): only
    # then must the log carry its final marker (see _daaf_case_report). A failed staging
    # run never printed it, and the WARNING above already covers that.
    CLAUDE_STAGE_DONE_LOG=""
    CLAUDE_CASE_EXPECT=0
    if [ "${CLAUDE_STAGE_STATUS}" = "0" ] && [ -n "${STAGE_NAMES_MODE}" ]; then
        CLAUDE_CASE_EXPECT=1
        CLAUDE_STAGE_DONE_LOG="$(docker logs "${CLAUDE_STAGE_CID}" 2>/dev/null | tr -d '\r' || true)"
    fi
    if [ "${CLAUDE_STAGE_STATUS}" = "0" ] && docker cp "${CLAUDE_STAGE_CID}:/staging/." "${BACKUP_NAME}/${CLAUDE_SUBDIR}/"; then
        # Count data files only, with the snapshot count's root-relative predicate
        # (the same STAGE_PROGRAM staged this volume): exclude the subfolder's ROOT
        # ".daaf-symlinks" and ".daaf-permissions" and a root ".daaf-claude-config"
        # subtree, exactly like the data-volume FILE_COUNT and the .ps1 twin's Claude
        # count. A nested file that merely has the same name is data and counts.
        # Display only (the copy's success is judged by the docker cp exit code): a
        # count that hit read errors is shown as "N+" (lower bound), like the .ps1 twin.
        _daaf_tree_count "${BACKUP_NAME}/${CLAUDE_SUBDIR}" files
        CLAUDE_FILE_COUNT="${TREE_COUNT}"
        if [ "${TREE_COUNT_LOWER_BOUND}" -eq 1 ]; then CLAUDE_FILE_COUNT="${TREE_COUNT}+"; fi
        echo "Claude Code state backed up (${CLAUDE_FILE_COUNT} files)."
        CLAUDE_BACKED_UP=1
    else
        echo "WARNING: Failed to back up the Claude Code state volume." >&2
        echo "         Details from the staging scan:" >&2
        if [ -n "${CLAUDE_STAGE_LOG}" ]; then
            printf '%s\n' "${CLAUDE_STAGE_LOG}" | sed 's/^/         /' >&2
        else
            # Empty/whitespace log: label the silence rather than omit the detail,
            # so a future stream regression is visible rather than ambiguous.
            echo "         (no details could be retrieved from the staging container)" >&2
        fi
        echo "         The data volume backup above is still valid." >&2
        HAD_WARNINGS=1
    fi
    # Case-clash list for this volume (macOS "casewarn"; empty log elsewhere), after
    # EITHER branch: when the copy failed, a file+folder clash may be why, so the list
    # must not be skipped on that path. Printed once.
    _daaf_case_report "${CLAUDE_STAGE_DONE_LOG}" "Claude Code state volume" "${CLAUDE_CASE_EXPECT}" "${CLAUDE_CONTAINER_PATH}"
    docker rm -f "${CLAUDE_STAGE_CID}" > /dev/null 2>&1 || true
    trap - INT TERM
else
    echo ""
    echo "NOTE: No Claude Code state volume ('${CLAUDE_VOLUME_NAME}') found."
    echo "      Skipping -- this install may predate the dedicated Claude volume."
fi

# --- Capture the executable-permission manifest ---
# Why: NTFS (and the FAT/exFAT of external drives) stores no POSIX permission
# bits, so when a backup lands on a Windows host every file's mode is lost. On
# restore, `docker cp` INTO the volume fabricates 0755 for every file, and git
# inside the container then reports every tracked 0644 file as modified (a pure
# 100644->100755 mode diff, no content change). To make restore able to put the
# modes back, record -- here, from the volume, where the modes are still intact --
# the relative path of every regular file that has the owner-exec bit set. Restore
# normalizes everything to 0644 and re-applies 0755 to exactly these paths.
#
# This runs AFTER the data-volume file-count/size verification above (same reason
# the Claude subfolder copy does): the backup script compares backup-folder
# counts/sizes against the volume scan, and the manifest file must not skew that
# comparison. It is written into the backup ROOT (not a subfolder) so restore
# finds it via the whole-folder `docker cp`.
#
# Generate the list container-side from the volume: `find -type f -perm -0100`
# matches regular files with the owner-exec bit set; strip the "/source/" prefix
# so the paths are volume-relative. Manifest write failure is a WARNING, not
# fatal -- the data backup is still valid, and restore degrades gracefully (an
# absent manifest simply means no permission normalization happens).
# (PERMISSIONS_MANIFEST is declared in the Configuration section.)
echo ""
echo "Recording executable-permission manifest..."
if EXEC_PATHS=$(docker run --rm -v "${VOLUME_NAME}:/source:ro" "${BUSYBOX_IMAGE}" sh -c 'find /source -type f -perm -0100' 2>/dev/null); then
    # Strip the leading "/source/" from each path so entries are volume-relative,
    # then write LF-terminated (printf, not echo -e). An empty result is fine --
    # a zero-line manifest still signals to restore that this backup DOES preserve
    # permissions (so restore normalizes to 644 with no exec re-applied), which is
    # different from an absent manifest (older backup: restore leaves modes alone).
    # Write the volume-relative paths, dropping blank lines. `grep -v '^$'` exits 1
    # when it selects NO lines (a legitimately empty manifest -- zero exec files),
    # which is NOT a failure, so the write outcome is judged by whether the file was
    # actually created rather than by the pipeline's exit status. The redirection
    # still creates a 0-byte file in the empty case, and that empty file is the
    # correct signal to restore ("preserves permissions, re-apply exec to nothing").
    printf '%s\n' "${EXEC_PATHS}" | sed 's|^/source/||' | grep -v '^$' > "${BACKUP_NAME}/${PERMISSIONS_MANIFEST}" || true
    if [ -f "${BACKUP_NAME}/${PERMISSIONS_MANIFEST}" ]; then
        EXEC_COUNT=$(grep -c . "${BACKUP_NAME}/${PERMISSIONS_MANIFEST}" 2>/dev/null | tr -d '[:space:]') || EXEC_COUNT=0
        echo "Recorded ${EXEC_COUNT} executable file(s) in ${PERMISSIONS_MANIFEST}."
    else
        # The write itself failed (e.g. disk full) -- the redirection never created the
        # file. A missing manifest must not fail the backup: warn (mirroring the
        # scan-failure branch below) and let restore degrade gracefully (an absent
        # manifest simply means no permission normalization on restore).
        echo "WARNING: Could not record the executable-permission manifest." >&2
        echo "         The backup is still valid; on restore, file permissions may need" >&2
        echo "         manual repair if this backup is restored on a Windows host." >&2
        HAD_WARNINGS=1
    fi
else
    echo "WARNING: Could not record the executable-permission manifest." >&2
    echo "         The backup is still valid; on restore, file permissions may need" >&2
    echo "         manual repair if this backup is restored on a Windows host." >&2
    HAD_WARNINGS=1
fi

echo ""
echo "=========================================="
if [ "${HAD_WARNINGS}" -eq 1 ]; then
    echo "  Backup completed WITH WARNINGS -- verify before relying on it"
else
    echo "  Backup complete!"
fi
echo "=========================================="
echo ""
echo "Location: $(pwd)/${BACKUP_NAME}/"
echo "Files:    ${FILE_COUNT_LABEL} files copied"
if [ "${CLAUDE_BACKED_UP}" -eq 1 ]; then
    echo ""
    echo "IMPORTANT: This backup INCLUDES your Claude Code credentials and session"
    echo "history (in ${CLAUDE_SUBDIR}/). Treat the backup folder as sensitive --"
    echo "store it somewhere private and do not share it."
fi
echo ""
echo "To restore from this backup, run the restore script from this folder:"
echo ""
echo "  bash restore_from_backup.sh"
echo ""
echo "The restore script lets you pick which backup to restore from. It first"
echo "copies the backup into a temporary Docker volume and checks it there; only"
echo "after you confirm does it replace your current DAAF data."
echo ""
