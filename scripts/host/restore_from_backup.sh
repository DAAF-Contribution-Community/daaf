#!/usr/bin/env bash
# ============================================================================
# DAAF Restore from Backup (macOS / Linux)
# ============================================================================
# Restores a DAAF Docker volume from a previously created backup.
#
# Usage:
#   cd daaf-docker
#   bash restore_from_backup.sh
#
# The script searches the current directory for backup folders matching the
# naming pattern produced by backup_daaf.sh (e.g., 2026-04-21_daaf_backup/)
# and presents them for interactive selection.
#
# WARNING: Restoring is a DESTRUCTIVE operation: the entire contents of the
# Docker volume are replaced with the backup contents. The backup is first copied
# into a TEMPORARY Docker volume and checked there; only after you type RESTORE is
# the live volume replaced, in one step inside Docker ("copy-then-swap"). Any
# failure before that step leaves your current data untouched.
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script) and CI environments. RESTORE_PAUSE_ON_EXIT lets the copy-then-swap
# section's own EXIT handler (_restore_on_exit, which replaces this trap there) keep
# the same pause.
RESTORE_PAUSE_ON_EXIT=0
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    RESTORE_PAUSE_ON_EXIT=1
    # `|| true`: under `set -e` a failing pause read (no terminal any more) would make
    # the script exit 1 instead of with its own status.
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty || true' EXIT
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so the volume name below reflects DAAF_PROJECT_NAME and the
# `docker compose down` further below targets the right project. Canonical shared
# pattern (kept in sync with load_daaf_settings in daaf_lib.sh). Parse only these
# whitelisted keys (never `source` -- the file holds API keys); shell env wins; absent
# file = no-op; CR stripped; Bash 3.2 safe.
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
# Project-prefixed volume name "<project>_daaf-data". Default unset =>
# "daaf_daaf-data" (byte-for-byte identical to the previous hardcoded value).
# DAAF_DATA_VOLUME_NAME, when set, overrides the whole derivation with a verbatim
# full volume name (the shared-workspace escape hatch); unset => the derived
# default. Matches resolve_data_volume_name in daaf_lib.sh (inlined here because
# this standalone script does not source the library).
VOLUME_NAME="${DAAF_DATA_VOLUME_NAME:-${DAAF_PROJECT_NAME:-daaf}_daaf-data}"
# Second volume: Claude Code state. Restored only when the selected backup
# contains the dedicated subfolder (newer backups); older backups predating the
# volume are restored data-only with a NOTE.
CLAUDE_VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-claude-config"
CLAUDE_SUBDIR=".daaf-claude-config"
# Executable-permission manifest written into the backup root by backup_daaf.sh
# (see the "Capture the executable-permission manifest" block there). Lists every
# regular file that had the owner-exec bit set at backup time. Restore uses it to
# put POSIX modes back after a Windows round-trip erased them. Absent on older
# backups -- restore handles that gracefully (no normalization; see Step 3d).
PERMISSIONS_MANIFEST=".daaf-permissions"
# Symlink manifest written into the backup root (and the Claude subfolder root) by
# backup_daaf.sh's staging step. Lists each symlink's path and target (TAB-
# separated). Restore replays it container-side to recreate the links that the
# staging step stripped so `docker cp` could stream a symlink-free tree on Windows.
# Current backups always contain it (0 bytes when the volume had no symlinks); absent
# only on backups that predate the feature -- restore no-ops then (see Step 3e),
# matching the ".daaf-permissions" "no manifest, no action" rule.
SYMLINKS_MANIFEST=".daaf-symlinks"

# --- Copy-then-swap names and container programs ---
# The backup is copied into a TEMPORARY volume first, checked, and only then copied
# over the live volume inside Docker. Every name is derived from the RESOLVED volume
# names (never the project name alone: DAAF_DATA_VOLUME_NAME may override the data
# volume) and is checked by EXACT name (`docker volume inspect` / `docker container
# inspect`), never with `docker volume ls --filter name=`, which is an unanchored
# regex. `docker volume create` silently REUSES an existing volume, so a temp volume
# is only ever created after an exact-name check found none. The label marks every
# temp volume and every prepare-phase helper container so leftovers can be reaped by
# an exact `--filter label=` match; the swap containers are deliberately NOT labelled,
# so a reap can never kill a running swap. Same names and label in the .ps1 twin.
TEMP_VOLUME_NAME="${VOLUME_NAME}-restore-tmp"
CLAUDE_TEMP_VOLUME_NAME="${CLAUDE_VOLUME_NAME}-restore-tmp"
SWAP_CONTAINER_NAME="${VOLUME_NAME}-restore-swap"
CLAUDE_SWAP_CONTAINER_NAME="${CLAUDE_VOLUME_NAME}-restore-swap"
RESTORE_LABEL="org.daaf.restore-tmp-for"
# Identity of THIS run's temp volumes. Each temp volume is created with a second label,
# "${RESTORE_RUN_LABEL}=${RESTORE_RUN_ID}", whose value is unique to this run. Volume
# labels are fixed at creation, a volume that `docker volume create` silently reused
# keeps its OWN labels, and a volume that Docker auto-creates when a vanished name is
# mounted has none -- so "the temp volume still carries our token" proves it is the very
# volume this run created and checked. Re-checked (`docker volume inspect --format
# {{.Labels}}`, one quote-free argument, safe for Windows PowerShell 5.1) right after
# creation, before the state marker is written, and right before each swap. Chosen over
# the volume's CreatedAt, whose text has whole-second resolution and is set by Docker.
RESTORE_RUN_LABEL="org.daaf.restore-run"
RESTORE_RUN_ID="$(date +%Y%m%d%H%M%S)-$$-${RANDOM}${RANDOM}"
# State marker written into a temp volume right before its swap starts. The swap
# copies it to the live volume and deletes it there as its LAST step, so it only ever
# survives in the temp volume: a leftover temp volume that holds it is evidence that
# an earlier restore had started (and may not have finished) replacing live data.
SWAP_MARKER=".daaf-restore-swap-started"
# Container programs, quote-free (no `"`: Windows PowerShell 5.1 native-argument
# rule) and BYTE-IDENTICAL to the .ps1 twin's (pinned by
# tests/bash/backup_twin_parity.bats). The marker name and the label are literals in
# them (SYNC NOTE: update by hand if SWAP_MARKER changes).
#
# SPACE_PROGRAM (live volume at /dest:ro, optionally a temp volume at /src:ro):
# AVAIL_KB = free KB on the filesystem holding the volume (`stat -f`: %a = free blocks
# for unprivileged users, %S = block size; no pipeline, so a failure propagates),
# LIVE_KB = the live volume's size, SRC_KB = the temp volume's size when mounted. On
# Docker Desktop this is the free space of Docker's virtual disk, not of the host
# drive. busybox applets assumed: stat -f, du (both in the default busybox build).
SPACE_PROGRAM='a=$(stat -f -c %a /dest) && s=$(stat -f -c %S /dest) && echo AVAIL_KB=$((a*s/1024)) && set -- $(du -sk /dest) && echo LIVE_KB=$1 && if test -d /src; then set -- $(du -sk /src) && echo SRC_KB=$1; fi'
# SWAP_PROGRAM (temp volume at /src:ro, live volume at /dest): clear the live volume
# and copy the checked temp copy in, then delete the state marker from /dest. `trap :`
# FIRST: a `sh -c` running as the container's PID 1 still CATCHES SIGINT, so a
# forwarded Ctrl+C would end it after `rm` and before `cp`, leaving the live volume
# EMPTY. With the trap (and `docker run --sig-proxy=false`) only SIGKILL or a Docker
# shutdown can cut it short. It erases NOTHING unless /src holds the state marker,
# which this run writes into its own temp copy right before the swap: a /src that is
# not that copy (e.g. an empty volume Docker created because the temp volume had
# vanished) makes it exit 3 -- a code nothing else in the program uses -- with the
# live volume untouched, so the host can tell "nothing was replaced" apart from a
# failed rm/cp (exit 1). busybox `cp -a` keeps links, modes, owners and hardlinks, but
# its exit status does not report a failed mode/owner preservation -- hence
# SWAP_VERIFY_PROGRAM below.
SWAP_PROGRAM='trap : INT TERM HUP; test -f /src/.daaf-restore-swap-started || exit 3; rm -rf /dest/* /dest/.[!.]* /dest/..?* && cp -a /src/. /dest/ && rm -f /dest/.daaf-restore-swap-started'
# SWAP_VERIFY_PROGRAM (temp at /src:ro, live at /dest:ro): list both trees the same
# way -- every non-directory with its raw mode (type bits included), owner, group,
# size and name (links are listed as links: stat does not follow them), every
# directory below the root with mode, owner and group, and each link's target --
# sort, and compare. Prints SWAP_VERIFY=MATCH or MISMATCH plus the entry counts, or
# SWAP_VERIFY_ERRORS=<n> when listing hit errors. A list that could not be written
# (a failed `sort`, e.g. a full disk) or a tree that could not be entered is recorded
# as an error too, and an error file that cannot even be created stops the program
# with no verdict (exit 4). The host additionally requires SWAP_VERIFY_ENTRIES=n:n
# (n > 0 for the data volume), so two EMPTY lists never pass as a match. The root
# folder itself and the state marker are left out. busybox applets assumed: stat -c,
# readlink, sort, cmp, grep.
SWAP_VERIFY_PROGRAM='export LC_ALL=C; : > /tmp/err || exit 4; for t in src dest; do cd /$t 2>>/tmp/err && { find . ! -path ./.daaf-restore-swap-started ! -type d -exec stat -c %f:%u:%g:%s:%n {} + ; find . ! -path . -type d -exec stat -c %f:%u:%g:%n {} + ; find . -type l -exec readlink {} \; ; } 2>>/tmp/err | sort 2>>/tmp/err > /tmp/$t.lst || echo LIST_FAILED_$t >> /tmp/err; done; if test -s /tmp/err; then echo SWAP_VERIFY_ERRORS=$(grep -c ^ /tmp/err); elif cmp -s /tmp/src.lst /tmp/dest.lst; then echo SWAP_VERIFY=MATCH; else echo SWAP_VERIFY=MISMATCH; fi; echo SWAP_VERIFY_ENTRIES=$(grep -c ^ /tmp/src.lst):$(grep -c ^ /tmp/dest.lst)'
# The helper image every container step above and below runs, PINNED by digest: busybox
# 1.37.0, multi-arch OCI index (amd64, arm64/v8 and others), the tested digest below.
# Pinned because the untagged `busybox` (latest) moved to the untested busybox 1.38.0 on
# 2026-09-23 (research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/
# 04_F1_compat_audit.md). The same string is in backup_daaf.{sh,ps1},
# restore_from_backup.{sh,ps1}, migrate_daaf.{sh,ps1} and docker-compose.yml (daaf-init):
# keep every copy identical (a parity test enforces it).
BUSYBOX_IMAGE='busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'

# --- Host-side backup-folder count (never silent) ---
# A textually identical copy of backup_daaf.sh's _daaf_tree_count, from its
# `_daaf_tree_count() {` line to its closing `}` (pinned by the "_daaf_tree_count is
# byte-identical" test in tests/bash/backup_twin_parity.bats -- edit both copies
# together). See that script for the full rationale. Restore only calls it in "files"
# mode; the "kb" branch is kept so the two copies stay identical. The group's stderr is
# captured with the NUL count, which the pipeline prints last, so a read error makes the
# count a LOWER BOUND (TREE_COUNT_LOWER_BOUND=1, TREE_COUNT_ERRORS /
# TREE_COUNT_FIRST_ERROR set) instead of vanishing into `2>/dev/null` or aborting the
# script under pipefail. find only opens FOLDERS, so this catches unreadable folders,
# not unreadable files -- the scan of the selected backup below checks files separately.
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

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            "version --format"*) echo "29.1.3 29.1.3"; return 0 ;;
            "image inspect "*) return 0 ;;
            *"volume inspect"*) return 0 ;;
            *"ps --filter"*) return 0 ;;
            *"run --rm"*"rm -rf"*) return 0 ;;
            *"run --rm"*"find /dest"*)
                echo "42"
                return 0
                ;;
            *)
                # The dry-run path exits before any create/cp/rm/chown, so no match
                # arm is needed for the copy mechanism or the ownership repair -- the
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
# Usage: DAAF_TEST_MODE=1 source scripts/host/restore_from_backup.sh
if [ "${DAAF_TEST_MODE:-}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

echo ""
echo "=========================================="
echo "  DAAF Restore from Backup"
echo "=========================================="
echo ""

# --- Preflight ---
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal." >&2
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/" >&2
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker Desktop does not seem to be running. Please start it and try again." >&2
    # Old-Engine hint (F1; review round 9): a client of 25 or newer that cannot talk to an
    # Engine older than 25.0 (Docker 29 removed the older API versions) also fails
    # `docker info`, so the version check below is never reached. Read the versions
    # (stdout only, the last non-empty line); when the client's major reads as 25 or newer
    # and the Engine's version is empty or cannot be read, add a hint. The message above and
    # the exit code stay the same. Same text as the .ps1 twin and backup_daaf.{sh,ps1}.
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
                        echo "       If Docker is running, its Docker Engine may be older than 25.0 (Docker client ${DOCKER_INFO_FAIL_CLIENT})." >&2
                        echo "       The restore needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer)." >&2
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
# (stdout only, the last non-empty line) and refuse, before any prompt and before
# anything is created, when either side's major version is below 25 or cannot be read.
# A major other than the tested 29 only prints a NOTE (no WARNING latch) and continues.
# Same rule and wording as the .ps1 twin and backup_daaf.{sh,ps1} (script name varied).
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
        echo "ERROR: This Docker version is too old for the restore (Docker client ${DOCKER_CLIENT_VERSION:-unknown}, Docker Engine ${DOCKER_SERVER_VERSION:-unknown})." >&2
    else
        echo "ERROR: Could not read the Docker version (Docker client ${DOCKER_CLIENT_VERSION:-unknown}, Docker Engine ${DOCKER_SERVER_VERSION:-unknown})." >&2
    fi
    echo "       The restore needs Docker 25.0 or newer, for both the Docker client and Docker Engine" >&2
    echo "       (Docker Desktop 4.27.1 or newer). Update Docker, then run the restore again." >&2
    echo "       (Docker Desktop or Docker Engine is required; Podman is not supported.)" >&2
    echo "       Nothing was changed." >&2
    exit 1
fi
if [ "${DOCKER_VERSION_STATE}" = "untested" ]; then
    echo "NOTE: The restore has not been tested with this Docker version (Docker client ${DOCKER_CLIENT_VERSION}, Docker Engine ${DOCKER_SERVER_VERSION}; tested: 29). Continuing."
    echo ""
fi

if ! docker volume inspect "${VOLUME_NAME}" &> /dev/null; then
    echo "ERROR: Docker volume '${VOLUME_NAME}' not found." >&2
    echo "Have you run the DAAF installer yet?" >&2
    exit 1
fi

# --- Helper image check (F1 compatibility; audit 04, section 3) ---
# Every container step runs the pinned ${BUSYBOX_IMAGE}. Make sure it is on this computer
# NOW, before any prompt and before the temporary copy is prepared: when it is missing,
# download it here with its progress showing, so an offline computer is refused with
# nothing changed instead of failing partway (`docker run` exits 125 when it cannot pull).
# Docker's last stderr line is shown when the download fails. Same as the .ps1 twin and
# backup_daaf.{sh,ps1}.
if ! docker image inspect "${BUSYBOX_IMAGE}" > /dev/null 2>&1; then
    echo "Downloading the small helper image busybox that the restore needs..."
    BUSYBOX_PULL_EXIT=0
    # stdout (the progress) to the terminal through fd 3; stderr captured.
    { BUSYBOX_PULL_SAID="$(docker pull "${BUSYBOX_IMAGE}" 2>&1 1>&3 3>&-)"; } 3>&1 || BUSYBOX_PULL_EXIT=$?
    if [ "${BUSYBOX_PULL_EXIT}" -ne 0 ]; then
        BUSYBOX_PULL_SAID="$(printf '%s\n' "${BUSYBOX_PULL_SAID}" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep . | tail -n 1)" || true
        echo "" >&2
        echo "ERROR: The restore needs the small helper image busybox and could not download it." >&2
        echo "       Check the internet connection and that Docker Desktop is running, then run the restore again." >&2
        if [ -n "${BUSYBOX_PULL_SAID}" ]; then echo "       Docker said: ${BUSYBOX_PULL_SAID}" >&2; fi
        echo "       Nothing was changed." >&2
        exit 1
    fi
    echo ""
fi

# --- Check for running containers using the volume ---
# Names come from stdout only (a stderr line, e.g. a Docker config WARNING, is never a
# container). A FAILED `docker ps` is not "nothing is running" -- until 2026-10-02 the
# `|| true` here read it that way -- so refuse: nothing has been created yet. Same
# wording, outcome and exit code as the .ps1 twin, and the same first line as the
# swap-time re-check below.
RUNNING_CONTAINERS=""
RUNNING_CONTAINERS_EXIT=0
RUNNING_CONTAINERS="$(docker ps --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' 2>/dev/null)" || RUNNING_CONTAINERS_EXIT=$?
if [ "${RUNNING_CONTAINERS_EXIT}" -ne 0 ]; then
    echo "ERROR: Could not check whether DAAF is running (docker ps failed, exit ${RUNNING_CONTAINERS_EXIT})," >&2
    echo "       so the restore cannot start safely. This restore has not changed anything." >&2
    echo "       Make sure Docker Desktop is running, then run the restore again." >&2
    exit 1
fi
if [ -n "${RUNNING_CONTAINERS}" ]; then
    echo "The DAAF container is currently running:"
    echo ""
    echo "${RUNNING_CONTAINERS}" | while IFS= read -r name; do
        echo "  - ${name}"
    done
    echo ""
    echo "The container must be stopped before restoring. This will terminate"
    echo "any Claude Code sessions currently in progress."
    echo ""
    # End of input (Ctrl+D, a short pipe) is a "no", never a silent `set -e` exit.
    read -r -p "Stop the container now? (y/n): " STOP_CHOICE || STOP_CHOICE=""
    if [ "${STOP_CHOICE}" = "y" ] || [ "${STOP_CHOICE}" = "Y" ]; then
        echo ""
        echo "Stopping containers..."
        if ! docker compose down; then
            echo "ERROR: Failed to stop containers." >&2
            exit 1
        fi
        echo "Containers stopped."
        echo ""
    else
        echo ""
        echo "Restore cancelled. Stop the container manually and try again:"
        echo "  docker compose down"
        exit 0
    fi
fi

# --- Find backup folders ---
BACKUPS=()
shopt -s nullglob
for dir in ./[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*_daaf_backup; do
    if [ -d "${dir}" ]; then
        BACKUPS+=("${dir}")
    fi
done
shopt -u nullglob

if [ ${#BACKUPS[@]} -eq 0 ]; then
    if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
        echo "[DRY-RUN] No backup folders found (expected in CI)."
        echo ""
        echo "=========================================="
        echo "  Restore dry-run complete!"
        echo "=========================================="
        exit 0
    fi
    echo "No backup folders found in the current directory." >&2
    echo "" >&2
    echo "Backup folders are created by backup_daaf.sh and follow the pattern:" >&2
    echo "  2026-04-21_daaf_backup/" >&2
    echo "  2026-04-21a_daaf_backup/" >&2
    echo "" >&2
    echo "Make sure you are running this script from your daaf-docker folder." >&2
    exit 1
fi

# --- Display backups (newest first) ---
# Reverse the array so newest (alphabetically last) appears first
SORTED_BACKUPS=()
for ((i=${#BACKUPS[@]}-1; i>=0; i--)); do
    SORTED_BACKUPS+=("${BACKUPS[$i]}")
done

echo "Available backups (newest first):"
echo ""
for i in "${!SORTED_BACKUPS[@]}"; do
    dir="${SORTED_BACKUPS[$i]}"
    name="$(basename "${dir}")"
    # Count and size the DATA-volume contents only -- exclude the hidden Claude
    # subfolder (it restores to its own volume, not the data volume) and BOTH
    # metadata manifests (".daaf-permissions", ".daaf-symlinks" -- neither is
    # restored content). The exclusions are ROOT-relative, the rule every count site
    # now shares (the backup twins' snapshot and host counts, the .ps1 twin's
    # container-side and PowerShell counts): only the root manifests and the root
    # Claude subfolder are skipped, so a data file that merely has the same name
    # deeper in the tree still counts. It also counts the same way as the backup
    # script's completion report: one NUL per file (`-print0`, supported by BSD and
    # GNU find), not one line, so a file name holding a newline counts once. With the
    # same predicate AND the same counting method, this listing, the "Scanning backup"
    # count below and the backup's report agree, and match the post-restore volume
    # count (which also counts one line per file, via `stat`). (The .ps1 twin's listing
    # can show a lower bound, "N+", where Windows PowerShell cannot read very long
    # paths; macOS/Linux `find` has no such limit.) `find .` from inside the folder
    # plus POSIX `!`/`-path` keeps this working with BSD find on macOS and GNU find on
    # Linux; `LC_ALL=C tr` keeps macOS's multibyte `tr` from failing with "Illegal
    # byte sequence" on an odd byte in a name. When Claude state is present it is noted
    # inline rather than folded silently into the number. A folder that could not be
    # fully read shows its count as a lower bound ("N+"), like the .ps1 twin; the scan
    # of the selected backup below then refuses to restore it (see there).
    claude_sub="${dir}/${CLAUDE_SUBDIR}"
    _daaf_tree_count "${dir}" files
    count="${TREE_COUNT}"
    if [ "${TREE_COUNT_LOWER_BOUND}" -eq 1 ]; then count="${TREE_COUNT}+"; fi
    # BSD du has no --exclude, so total the data-volume KB by subtracting the Claude
    # subfolder's KB AND both root metadata manifests' KB from the whole-folder KB,
    # then humanize with awk. Subtracting the manifests (not just the Claude
    # subfolder) keeps this size aligned with the .ps1 twin, whose counts
    # (Measure-DaafBackupTree and the container-side $BackupCountProgram) exclude both
    # ".daaf-permissions" and ".daaf-symlinks". Mirrors the "Scanning backup" logic below.
    # `|| true` on every du below: du exits 1 on a folder it cannot read, and under
    # pipefail + set -e that aborted the whole script right here -- silently, before the
    # "N+" note -- instead of letting the scan below refuse with an explanation. du still
    # prints the total it could read, which is all this display line needs.
    total_kb=$(du -sk "${dir}" 2>/dev/null | awk '{print $1}') || true
    total_kb=${total_kb:-0}
    for mf in "${dir}/${PERMISSIONS_MANIFEST}" "${dir}/${SYMLINKS_MANIFEST}"; do
        if [ -f "${mf}" ]; then
            mf_kb=$(du -sk "${mf}" 2>/dev/null | awk '{print $1}') || true
            total_kb=$(( total_kb - ${mf_kb:-0} ))
        fi
    done
    has_claude=0
    if [ -d "${claude_sub}" ] && [ -n "$(ls -A "${claude_sub}" 2>/dev/null)" ]; then
        has_claude=1
        claude_kb=$(du -sk "${claude_sub}" 2>/dev/null | awk '{print $1}') || true
        total_kb=$(( total_kb - ${claude_kb:-0} ))
    fi
    size=$(awk -v kb="${total_kb}" 'BEGIN { if (kb >= 1048576) printf "%.1fG", kb/1048576; else if (kb >= 1024) printf "%.1fM", kb/1024; else printf "%dK", kb }') || size="?"
    if [ "${has_claude}" -eq 1 ]; then
        printf "  %d) %s  (%s files + Claude state, %s)\n" "$((i + 1))" "${name}" "${count}" "${size}"
    else
        printf "  %d) %s  (%s files, %s)\n" "$((i + 1))" "${name}" "${count}" "${size}"
    fi
    if [ "${TREE_COUNT_LOWER_BOUND}" -eq 1 ]; then
        echo "     (some folders in this backup could not be read; the file count is a lower bound)"
    fi
done
echo ""

# --- Dry-run early exit ---
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    echo "[DRY-RUN] Would present interactive selection for ${#SORTED_BACKUPS[@]} backup(s)."
    echo ""
    echo "=========================================="
    echo "  Restore dry-run complete!"
    echo "=========================================="
    exit 0
fi

# --- User selects backup ---
# End of input is an invalid (empty) selection with the usual message, never a silent
# `set -e` exit.
read -r -p "Enter backup number to restore (1-${#SORTED_BACKUPS[@]}): " CHOICE || CHOICE=""

if ! [[ "${CHOICE}" =~ ^[0-9]+$ ]] || [ "${CHOICE}" -lt 1 ] || [ "${CHOICE}" -gt "${#SORTED_BACKUPS[@]}" ]; then
    echo "" >&2
    echo "ERROR: Invalid selection '${CHOICE}'. Please enter a number between 1 and ${#SORTED_BACKUPS[@]}." >&2
    exit 1
fi

SELECTED="${SORTED_BACKUPS[$((CHOICE - 1))]}"
SELECTED_NAME="$(basename "${SELECTED}")"
# Guarded: an unguarded `$(cd ... && pwd)` under `set -e` aborted the script here with
# only bash's bare "cd: ... Permission denied" when the backup folder itself was not
# readable/searchable. Refuse in the same style as the scan below -- before anything is
# changed. cd's error is captured into SELECTED_PATH (stdout is only pwd on success).
if ! SELECTED_PATH="$(cd "${SELECTED}" 2>&1 && pwd)"; then
    echo "" >&2
    echo "ERROR: Could not open the backup folder ${SELECTED_NAME}/, so it cannot be restored." >&2
    echo "       Your DAAF data has not been changed." >&2
    if [ -n "${SELECTED_PATH}" ]; then
        echo "       First error: ${SELECTED_PATH}" >&2
    fi
    echo "       Make ${SELECTED_NAME}/ and every folder and file in it readable by your user" >&2
    echo "       account (check its ownership and permissions), then re-run the restore." >&2
    exit 1
fi

echo ""
echo "Selected: ${SELECTED_NAME}"

# --- Detect Claude Code state in the backup ---
# Newer backups nest the Claude Code state volume in a hidden subfolder. Older
# backups (created before the dedicated volume existed) lack it -- those restore
# data-only with a NOTE.
CLAUDE_BACKUP_PATH="${SELECTED_PATH}/${CLAUDE_SUBDIR}"
HAS_CLAUDE_BACKUP=0
# Require the subfolder to exist AND be non-empty. An empty "${CLAUDE_SUBDIR}/"
# dir (e.g., a stray pre-created folder from an interrupted backup) must NOT
# trigger the Claude restore path below -- that path REPLACES the live claude-config
# volume's contents, so restoring from an empty source would wipe the user's
# Claude Code login and session history and copy nothing back.
if [ -d "${CLAUDE_BACKUP_PATH}" ] && [ -n "$(ls -A "${CLAUDE_BACKUP_PATH}" 2>/dev/null)" ]; then
    HAS_CLAUDE_BACKUP=1
fi

# --- Completion-banner latch ---
# Mirrors backup_daaf.sh's HAD_WARNINGS: every non-fatal WARNING on the success path
# below (a free space that could not be checked, a permission or symlink replay
# failure in the temporary copy, a Claude-state symlink-replay failure, a restored
# file count that could not be verified, a temporary copy that could not be removed)
# sets this so the final banner can say the restore completed
# WITH WARNINGS rather than claiming an unqualified success. The exit status stays 0
# on those paths -- the banner wording is the signal, not the exit code (callers such
# as daaf.sh branch on the exit code only). The NOTEs do not latch: a backup that
# predates the permission manifest or the Claude volume restores exactly what it
# holds. Refusals and errors exit nonzero before the banner, so they need no latch.
# (Same latch set as the .ps1 twin, except that twin also latches a lower-bound
# backup count, which this twin refuses instead.)
HAD_WARNINGS=0

# --- Count source files ---
# Exclude the Claude subfolder from the DATA-volume count -- it is restored to a
# separate volume below, not into the data volume. Also exclude BOTH metadata
# manifests: ".daaf-permissions" (consumed by Step 3d, then removed) and
# ".daaf-symlinks" (consumed by Step 3e, then removed). Neither is restored content,
# so counting them would make this scan disagree with the post-restore verification
# count (which runs after both manifests are stripped from the volume) and with the
# listing count above. Root-relative, like the listing: a nested data file that
# merely shares a manifest's name is restored content and counts. One NUL per file,
# like the listing, so a name holding a newline counts once.
#
# A READ ERROR here REFUSES the restore, before the destructive prompt. This twin
# deliberately differs from the .ps1, which proceeds with an "N+" count: there the
# lower bound comes from Windows PowerShell 5.1's path-length limit, which `docker cp`
# (Go, long-path aware) does not share. On macOS/Linux `find` has no such limit, so a
# read error is a real permission or I/O problem -- and `docker cp` reads the same
# files as the same user, so the copy would most likely fail partway on it too. (The
# copy now goes into a temporary volume that is checked before anything is replaced,
# so such a failure would also leave the live data untouched; refusing up front is
# still kept -- user decision D4, 2026-10-01 -- because it names the unreadable file,
# which a failed or short copy cannot.) Previously an unguarded `$(...)` under
# pipefail aborted the script at this point with only find's own error lines as
# explanation.
#
# `find` only opens FOLDERS (to list them); it never opens a regular file, so the count
# alone catches an unreadable folder but NOT an unreadable file (a mode-000 file, or a
# root-owned 0600 file left by a one-off `sudo`). A second pass below therefore tests
# every regular file in the backup -- the whole folder, manifests and the Claude
# subfolder included, since `docker cp` copies all of it -- with POSIX `[ -r ]` (BSD
# and GNU alike; GNU find's `-readable` does not exist on macOS) and refuses the same
# way. `-exec ... {} +` batches the paths, so the cost is a few `sh` processes plus
# one access() check per file, not a process per file.
echo ""
echo "Scanning backup..."
_daaf_tree_count "${SELECTED_PATH}" files
if [ "${TREE_COUNT_LOWER_BOUND}" -eq 1 ]; then
    echo "" >&2
    echo "ERROR: Could not read every file in this backup folder (at least ${TREE_COUNT} files were" >&2
    echo "       readable), so it cannot be restored safely: the copy would most likely fail" >&2
    echo "       partway on the same problem. Your DAAF data has not been changed." >&2
    if [ -n "${TREE_COUNT_FIRST_ERROR:-}" ]; then
        echo "       First error: ${TREE_COUNT_FIRST_ERROR}" >&2
    fi
    echo "       Make every folder and file in ${SELECTED_NAME}/ readable by your user account" >&2
    echo "       (check its ownership and permissions), then re-run the restore." >&2
    exit 1
fi
# Unreadable FILES (see the note above). Each unreadable path is printed as one line
# starting "./"; any other line is an error from the check itself (e.g. a folder that
# became unreadable since the count). A file name holding a newline could over-count
# here, which only makes the refusal message's number too high -- never a false pass.
# A nonzero status with no "./" line means the check could not finish: refuse too.
UNREADABLE_STATUS=0
UNREADABLE_OUT="$(cd "${SELECTED_PATH}" && find . -type f -exec sh -c 'for f do [ -r "$f" ] || printf "%s\n" "$f"; done' sh {} + 2>&1)" || UNREADABLE_STATUS=$?
UNREADABLE_COUNT="$(printf '%s\n' "${UNREADABLE_OUT}" | grep -c '^\./')" || true
UNREADABLE_FIRST="$(printf '%s\n' "${UNREADABLE_OUT}" | grep '^\./' | head -n 1)" || true
if [ "${UNREADABLE_COUNT:-0}" -gt 0 ]; then
    echo "" >&2
    echo "ERROR: ${UNREADABLE_COUNT} file(s) in this backup folder cannot be read by your user account," >&2
    echo "       so it cannot be restored safely: the copy would most likely fail partway" >&2
    echo "       on the same files. Your DAAF data has not been changed." >&2
    echo "       First unreadable file: ${SELECTED_NAME}/${UNREADABLE_FIRST#./}" >&2
    echo "       Make every file in ${SELECTED_NAME}/ readable by your user account (check its" >&2
    echo "       ownership and permissions -- e.g. a file created with sudo), then re-run the restore." >&2
    exit 1
elif [ "${UNREADABLE_STATUS}" -ne 0 ]; then
    echo "" >&2
    echo "ERROR: Could not check that every file in this backup folder is readable, so it" >&2
    echo "       cannot be restored safely. Your DAAF data has not been changed." >&2
    UNREADABLE_FIRST="$(printf '%s\n' "${UNREADABLE_OUT}" | grep . | head -n 1)" || true
    if [ -n "${UNREADABLE_FIRST}" ]; then
        echo "       First error: ${UNREADABLE_FIRST}" >&2
    fi
    echo "       Make every folder and file in ${SELECTED_NAME}/ readable by your user account" >&2
    echo "       (check its ownership and permissions), then re-run the restore." >&2
    exit 1
fi
TOTAL_FILES="${TREE_COUNT}"
# Size must match the file count above: data-volume contents only, excluding the
# Claude subfolder (which restores to its own volume) AND both root metadata
# manifests. BSD du has no --exclude, so subtract the subfolder's KB and each
# manifest's KB from the total and humanize with awk. Subtracting the manifests keeps
# this aligned with the .ps1 twin's counts (which exclude both) and with the file
# count above.
# `|| true` on each du: see the listing above (a du read error must not abort under
# pipefail + set -e; the file count above already refused an unreadable backup).
TOTAL_KB=$(du -sk "${SELECTED_PATH}" 2>/dev/null | awk '{print $1}') || true
TOTAL_KB=${TOTAL_KB:-0}
for mf in "${SELECTED_PATH}/${PERMISSIONS_MANIFEST}" "${SELECTED_PATH}/${SYMLINKS_MANIFEST}"; do
    if [ -f "${mf}" ]; then
        MF_KB=$(du -sk "${mf}" 2>/dev/null | awk '{print $1}') || true
        TOTAL_KB=$(( TOTAL_KB - ${MF_KB:-0} ))
    fi
done
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then
    CLAUDE_KB=$(du -sk "${CLAUDE_BACKUP_PATH}" 2>/dev/null | awk '{print $1}') || true
    TOTAL_KB=$(( TOTAL_KB - ${CLAUDE_KB:-0} ))
fi
TOTAL_SIZE=$(awk -v kb="${TOTAL_KB}" 'BEGIN { if (kb >= 1048576) printf "%.1fG", kb/1048576; else if (kb >= 1024) printf "%.1fM", kb/1024; else printf "%dK", kb }')
echo "Found ${TOTAL_FILES} files (${TOTAL_SIZE}) to restore."

# ============================================================================
# Copy-then-swap
# ============================================================================
# Nothing above changed anything. From here: (1) leftovers from an earlier restore,
# (2) a free-space check, (3) copy the backup into TEMPORARY volumes and check them,
# (4) the RESTORE confirmation, (5) replace the live volumes inside Docker, (6) check
# the result and remove the temporary volumes. Until step 5 starts, every failure,
# cancel or Ctrl+C removes what this run created and leaves the live volumes
# untouched. Once step 5 has started, a temporary volume may hold the only complete
# copy, so NOTHING deletes it any more (SWAP_STARTED) -- the user is told how to
# finish instead.
TEMP_CREATED=0
CLAUDE_TEMP_CREATED=0
SWAP_STARTED=0
# 1 once every swap and its metadata check passed (the INT handler's wording).
SWAPS_DONE=0
TEMP_REMOVE_FAILED=0
# Why a temp volume was kept (message lines, newline-separated; field test 2026-10-05,
# D1/D2).
TEMP_REMOVE_NOTE=""
# 1 once the Claude Code state swap phase began: the data volume was already replaced
# and checked (the INT handler's wording; field test 2026-10-05, D3).
CLAUDE_SWAP_PHASE=0
# 1 once a pre-swap cleanup ran (or was deliberately skipped), so the EXIT handler
# does not repeat it.
TEMP_CLEANUP_TRIED=0
# 1 when the leftover check found that an earlier restore had started replacing the
# live data, or could not tell: "nothing changed" messages then say that THIS restore
# changed nothing but the data may still be incomplete from the earlier one.
EARLIER_SWAP_STARTED=0
# 1 once the state marker may have been written into a temp volume: any later removal
# of a temp copy (or a refusal that keeps one) deletes the marker first, so the next
# run does not report a swap that never ran as one that "had started replacing" data.
MARKERS_WRITTEN=0
# 1 when a temp volume under one of this run's names may belong to someone else (a new
# temp that failed its check, or a swap that provably did not run): cleanup then skips
# the label reap of prepare helpers (they could be another restore's) and removes only
# the temps that still carry THIS run's identity label.
TEMP_CLEANUP_CAREFUL=0
# 1 once the Claude swap container actually ran (any exit but its own refusal, 3): the
# live Claude Code state may then be erased, which its failure message says (S-a).
CLAUDE_SWAP_RAN=0
RERUN_COMMAND="bash restore_from_backup.sh"

# The "nothing was changed" sentence for refusals, cancels and interrupts before any
# swap. $1 = text before it on its first line (e.g. "Restore cancelled. " or an
# indent), $2 = indent for a continuation line. Prints to stdout; callers redirect.
_restore_unchanged() {
    if [ "${EARLIER_SWAP_STARTED}" -eq 1 ]; then
        echo "${1}This restore did not change anything, but your DAAF data may still be"
        echo "${2}incomplete from the earlier restore. Run the restore again to finish it."
    else
        echo "${1}Your DAAF data has not been changed."
    fi
}

# Exit 0 when the volume named $1 still carries THIS run's identity label (see
# RESTORE_RUN_LABEL). Any other answer -- a different token, no such label, no such
# volume, or an inspect that failed -- is "not ours".
_restore_temp_is_ours() {
    local labels word
    labels="$(docker volume inspect --format '{{.Labels}}' "$1" 2>/dev/null)" || return 1
    labels="${labels#map\[}"
    labels="${labels%\]}"
    for word in ${labels}; do
        if [ "${word}" = "${RESTORE_RUN_LABEL}:${RESTORE_RUN_ID}" ]; then return 0; fi
    done
    return 1
}

# Best-effort removal of every prepare-phase helper container of this volume pair
# (exact label match). A leftover helper -- even a never-started `docker create`
# one -- keeps a temp volume "in use", and `docker volume rm` then fails.
_restore_reap_helpers() {
    local lbl id
    for lbl in "${VOLUME_NAME}" "${CLAUDE_VOLUME_NAME}"; do
        docker ps -aq --filter "label=${RESTORE_LABEL}=${lbl}" 2>/dev/null | while IFS= read -r id; do
            if [ -n "${id}" ]; then docker rm -f "${id}" > /dev/null 2>&1 || true; fi
        done || true
    done
}

# Remove the temp volumes this run created. Refuses (no-op) once a swap has started,
# unless called with "final" after a fully verified swap. Sets TEMP_REMOVE_FAILED=1
# when a volume could not be removed (it is kept and named in the message). On the
# "final" call -- and on any call once a marker may have been written -- each temp
# volume's state marker is deleted first (best-effort), so a temp copy that then
# cannot be removed is not later reported as a restore that had "started replacing"
# the data. With TEMP_CLEANUP_CAREFUL=1 the label reap is skipped and a temp that no
# longer carries this run's identity label is left alone (and no longer counted as
# this run's), consistency review round 2 (SF2).
_restore_remove_temps() {
    local unmark=0 rm_mode="" rm_status
    if [ "${SWAP_STARTED}" -eq 1 ] && [ "${1:-}" != "final" ]; then return 0; fi
    TEMP_CLEANUP_TRIED=1
    TEMP_REMOVE_FAILED=0
    TEMP_REMOVE_NOTE=""
    if [ "${1:-}" = "final" ] || [ "${MARKERS_WRITTEN}" -eq 1 ]; then unmark=1; fi
    if [ "${TEMP_CLEANUP_CAREFUL}" -eq 1 ]; then
        rm_mode=careful
        if [ "${TEMP_CREATED}" -eq 1 ] && ! _restore_temp_is_ours "${TEMP_VOLUME_NAME}"; then TEMP_CREATED=0; fi
        if [ "${CLAUDE_TEMP_CREATED}" -eq 1 ] && ! _restore_temp_is_ours "${CLAUDE_TEMP_VOLUME_NAME}"; then CLAUDE_TEMP_CREATED=0; fi
    else
        _restore_reap_helpers
    fi
    # Field test 2026-10-05, D1: each removal goes through _restore_remove_volume
    # (stopped holders first, then the volume); careful cleanup removes no holder. A temp
    # that is kept stays this run's (TEMP_CREATED) and its reason is kept for the message.
    if [ "${TEMP_CREATED}" -eq 1 ]; then
        if [ "${unmark}" -eq 1 ]; then
            docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" rm -f "/dest/${SWAP_MARKER}" > /dev/null 2>&1 || true
        fi
        rm_status=0
        _restore_remove_volume "${TEMP_VOLUME_NAME}" "${rm_mode}" || rm_status=$?
        if [ "${rm_status}" -eq 0 ]; then TEMP_CREATED=0; else TEMP_REMOVE_FAILED=1; _restore_note_removal "${rm_status}"; fi
    fi
    if [ "${CLAUDE_TEMP_CREATED}" -eq 1 ]; then
        if [ "${unmark}" -eq 1 ]; then
            docker run --rm --label "${RESTORE_LABEL}=${CLAUDE_VOLUME_NAME}" -v "${CLAUDE_TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" rm -f "/dest/${SWAP_MARKER}" > /dev/null 2>&1 || true
        fi
        rm_status=0
        _restore_remove_volume "${CLAUDE_TEMP_VOLUME_NAME}" "${rm_mode}" || rm_status=$?
        if [ "${rm_status}" -eq 0 ]; then CLAUDE_TEMP_CREATED=0; else TEMP_REMOVE_FAILED=1; _restore_note_removal "${rm_status}"; fi
    fi
}

# The last non-empty line of Docker's stderr text $1, trimmed (empty when there is
# none): the "Docker said:" text of a failure message (field test 2026-10-05, D2).
_restore_last_line() {
    printf '%s\n' "$1" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' | grep . | tail -n 1 || true
}

# Field test 2026-10-05, D1: remove temp volume $1 together with the STOPPED containers
# that still reference it. A Ctrl+C between `docker run`'s create and start leaves a
# never-started ("created") container -- `--rm` acts only on exit, and an unlabelled one
# (the swap check, the space check, the marker probe) escapes the label reap -- which
# keeps the volume "in use"; it does not go away on its own while Docker keeps running
# (a Docker restart is expected to remove it: moby restore(), inference). Holders come
# from STDOUT only (a stderr line is not an ID): `docker ps -a --filter volume=<temp>`.
# Moby's `volume` filter matches a mount's volume NAME (a bind's source) or its
# DESTINATION exactly, several values OR'd (daemon/list.go, read 2026-10-05); a temp
# name never starts with "/", so it cannot match a destination. A holder in `created`,
# `exited` or `dead` is removed with a PLAIN `docker rm` (never -f): the daemon refuses a
# running one (daemon/delete.go: "stop the container before removing or force remove"),
# so a container that started since the list survives, and `docker rm` never removes a
# NAMED volume (the live one stays). Any other state -- running, restarting, paused,
# removing, or one not known here -- means another restore may still be using it:
# nothing is removed. A failed list is "could not check", never "no holders". $2 =
# careful (cleanup, SF2: the temp may be another restore's; no holder is removed) |
# check (list only) | empty. Only this run's two temp names are ever removed. Returns
# 0 removed (check: removable), 1 a removal failed, 2 in use, 3 the list failed; sets
# RESTORE_RM_SAID (Docker's last stderr line) and RESTORE_RM_PS_EXIT (docker ps's exit).
_restore_remove_volume() {
    local holders said id state ids="" status=0
    RESTORE_RM_SAID=""
    RESTORE_RM_PS_EXIT=0
    if [ "$1" != "${TEMP_VOLUME_NAME}" ] && [ "$1" != "${CLAUDE_TEMP_VOLUME_NAME}" ]; then return 1; fi
    if [ "${2:-}" != careful ]; then
        holders="$(docker ps -a --filter "volume=$1" --format '{{.ID}} {{.State}}' 2>/dev/null)" || status=$?
        if [ "${status}" -ne 0 ]; then
            RESTORE_RM_PS_EXIT="${status}"
            # The error text, read by a second call only now that the first failed.
            said="$(docker ps -a --filter "volume=$1" --format '{{.ID}} {{.State}}' 2>&1 > /dev/null)" || true
            RESTORE_RM_SAID="$(_restore_last_line "${said}")"
            return 3
        fi
        while read -r id state _; do
            [ -n "${id}" ] || continue
            case "$(printf '%s' "${state:-}" | tr '[:upper:]' '[:lower:]')" in
                created|exited|dead) ids="${ids:+${ids} }${id}" ;;
                *) return 2 ;;
            esac
        done <<EOF
$(printf '%s\n' "${holders}" | tr -d '\r')
EOF
        if [ "${2:-}" = check ]; then return 0; fi
        for id in ${ids}; do
            if ! said="$(docker rm "${id}" 2>&1 > /dev/null)"; then
                RESTORE_RM_SAID="$(_restore_last_line "${said}")"
                return 1
            fi
        done
    fi
    if ! said="$(docker volume rm "$1" 2>&1 > /dev/null)"; then
        RESTORE_RM_SAID="$(_restore_last_line "${said}")"
        return 1
    fi
    return 0
}

# Record why a temp volume was kept ($1 = _restore_remove_volume's status), once per
# cleanup: the first failure's reason is shown.
_restore_note_removal() {
    if [ -n "${TEMP_REMOVE_NOTE}" ]; then return 0; fi
    case "$1" in
        2) TEMP_REMOVE_NOTE="Something is still using it; another restore may still be running." ;;
        3) TEMP_REMOVE_NOTE="Could not check what is using it (docker ps failed, exit ${RESTORE_RM_PS_EXIT})." ;;
    esac
    if [ -n "${RESTORE_RM_SAID}" ]; then
        TEMP_REMOVE_NOTE="${TEMP_REMOVE_NOTE:+${TEMP_REMOVE_NOTE}
}Docker said: ${RESTORE_RM_SAID}"
    fi
}

# How to remove temp volume(s) $2 (space-separated) by hand (field test 2026-10-05,
# D1): the removal command, then -- for a volume Docker says is in use -- how to find
# and remove the container that holds it. $1 is the message's indent; commands get two
# more. Prints to stdout; callers redirect.
_restore_remove_hint() {
    local tv filters=""
    for tv in $2; do filters="${filters} --filter volume=${tv}"; done
    echo "${1}  docker volume rm $2"
    echo "${1}If Docker says it is in use, first run"
    echo "${1}  docker ps -a${filters}"
    echo "${1}and remove each container it lists with docker rm <ID>, then try again."
}

# The "kept temporary copy" lines after a cleanup that could not remove one: why (when
# known), and how to remove it by hand. $1 is the message's indent. Prints to stdout.
_restore_kept_temp_hint() {
    local line
    echo "${1}The temporary copy could not be removed."
    if [ -n "${TEMP_REMOVE_NOTE}" ]; then
        while IFS= read -r line; do echo "${1}${line}"; done <<EOF
${TEMP_REMOVE_NOTE}
EOF
    fi
    echo "${1}To free the space it uses, run:"
    _restore_remove_hint "$1" "$(_restore_kept_temps)"
}

# Exit 0 when the multi-line text $1 has a line that is exactly $2 (CRs ignored). A
# `case` match, not `printf | grep -q`: under pipefail, grep -q exiting at the first
# match can SIGPIPE the printf and fail the pipeline (a false "no match").
_restore_has_line() {
    local text nl
    text="$(printf '%s' "$1" | tr -d '\r')"
    nl="$(printf '\nx')"
    nl="${nl%x}"
    case "${nl}${text}${nl}" in
        *"${nl}$2${nl}"*) return 0 ;;
    esac
    return 1
}

# The exact-name fallback (review round 2, S3) for a check whose inspect failed with
# text that is not a recognised "no such ..." message (Docker's wording can change):
# list the names, STDOUT only, and compare whole lines exactly. $1 = volume |
# container (all containers) | running (running containers only), $2 = the name.
# Exit 0 = listed, 1 = not listed, 2 = the list itself failed (could not check).
_restore_name_listed() {
    local names status=0
    case "$1" in
        volume) names="$(docker volume ls -q 2>/dev/null)" || status=$? ;;
        container) names="$(docker ps -a --format '{{.Names}}' 2>/dev/null)" || status=$? ;;
        *) names="$(docker ps --format '{{.Names}}' 2>/dev/null)" || status=$? ;;
    esac
    if [ "${status}" -ne 0 ]; then return 2; fi
    if _restore_has_line "${names}" "$2"; then return 0; fi
    return 1
}

# The temp volumes this run still holds, space-separated (for removal commands).
_restore_kept_temps() {
    local names=""
    if [ "${TEMP_CREATED}" -eq 1 ]; then names="${TEMP_VOLUME_NAME}"; fi
    if [ "${CLAUDE_TEMP_CREATED}" -eq 1 ]; then names="${names:+${names} }${CLAUDE_TEMP_VOLUME_NAME}"; fi
    printf '%s' "${names}"
}

# A failure BEFORE any swap: print the ERROR lines given, remove this run's temp
# volumes, say plainly that nothing changed, exit 1.
_restore_fail_before_swap() {
    local line
    echo "" >&2
    for line in "$@"; do echo "${line}" >&2; done
    _restore_remove_temps
    _restore_unchanged "       " "       " >&2
    if [ "${TEMP_REMOVE_FAILED}" -eq 1 ]; then _restore_kept_temp_hint "       " >&2; fi
    exit 1
}

# A failure AFTER a swap started: the temp volumes are KEPT (they may hold the only
# complete copy); explain how to finish, exit 1.
_restore_fail_after_swap() {
    local line
    echo "" >&2
    for line in "$@"; do echo "${line}" >&2; done
    echo "       Your DAAF data may now be incomplete. The checked copy of the backup is" >&2
    echo "       kept in Docker (volume(s): $(_restore_kept_temps)), and your backup" >&2
    echo "       folder ${SELECTED_NAME}/ is unchanged. To finish, run this restore again" >&2
    echo "       and choose the same backup:" >&2
    echo "         ${RERUN_COMMAND}" >&2
    echo "       It will offer to remove the leftover copy (answer y) and then redo the restore." >&2
    exit 1
}

# A Claude Code state failure AFTER the data swap succeeded and was checked (review
# round 2, S5): say plainly that the project files are in place and only the login
# and history are not. Same keep-the-temps rules and next steps as the after-swap path.
# Review round 3 (S-a): once the Claude swap container ran (CLAUDE_SWAP_RAN), the old
# login may be erased too -- say so, and that the restore puts the backup's back.
_restore_fail_claude_after_data() {
    local line
    echo "" >&2
    for line in "$@"; do echo "${line}" >&2; done
    echo "       Your project files (DAAF data) were restored and checked. Only the Claude Code" >&2
    if [ "${CLAUDE_SWAP_RAN}" -eq 1 ]; then
        echo "       login and session history were not restored." >&2
        echo "       Your previous Claude Code login may also be gone now; running the restore again" >&2
        echo "       puts the backup's login and history back." >&2
        echo "       The checked copy of the backup is" >&2
    else
        echo "       login and session history were not restored. The checked copy of the backup is" >&2
    fi
    echo "       kept in Docker (volume(s): $(_restore_kept_temps)), and your backup" >&2
    echo "       folder ${SELECTED_NAME}/ is unchanged. To finish, run this restore again" >&2
    echo "       and choose the same backup:" >&2
    echo "         ${RERUN_COMMAND}" >&2
    echo "       It will offer to remove the leftover copy (answer y) and then redo the restore." >&2
    exit 1
}

# A data swap that provably replaced NOTHING (review round 2, S1): ONLY exit 3, the swap
# program's own refusal (its source lacked this run's state marker; it exits before its
# rm). Nothing was replaced, so this is NOT the after-swap path. Review round 3 (I-1):
# Docker's 125 is NOT such proof. Docker documents 125 as "the error is with Docker
# daemon itself" (Running containers guide, "Exit status"), and `docker run` can return
# 125 after the container started -- e.g. when it loses track of it in a daemon restart
# mid-swap (moby PR #34999 / #46857), possibly after the rm ran. So 125, whether or not
# the swap container still exists, takes the after-swap path (temps and marker kept).
# The temps are removed carefully (TEMP_CLEANUP_CAREFUL: identity-checked, marker first,
# no label reap) -- a temp that is no longer this run's is left alone, and it holds no
# marker of ours, so the next run reports it as a restore that "stopped before it
# replaced anything". The careful flag is set BEFORE the swap-started flag is cleared
# (S-c): a Ctrl+C between the two then still finds the swap "started" (temps kept),
# never an ordinary cleanup with a label reap.
_restore_fail_swap_not_run() {
    TEMP_CLEANUP_CAREFUL=1
    SWAP_STARTED=0
    _restore_fail_before_swap "ERROR: The temporary copy of the backup in Docker was gone or could not be used" \
        "       (exit $1), so NOTHING was replaced. Run the restore again."
}

# A temp volume that is no longer the one this run created and checked (see
# RESTORE_RUN_LABEL): refuse WITHOUT removing anything -- the volume under that name
# may belong to another restore -- and exit 1. Only used before any swap started.
# Review round 2 (S2): once the state markers were written, the marker is deleted
# (best-effort) from this run's OTHER temps that still carry its identity label, so the
# next run does not report this refusal as a restore that "had started replacing" the
# data. No volume is removed and no helper is reaped.
_restore_refuse_changed_temp() {
    local tv
    if [ "${MARKERS_WRITTEN}" -eq 1 ]; then
        for tv in $(_restore_kept_temps); do
            if [ "${tv}" != "$1" ] && _restore_temp_is_ours "${tv}"; then
                docker run --rm -v "${tv}:/dest" "${BUSYBOX_IMAGE}" rm -f "/dest/${SWAP_MARKER}" > /dev/null 2>&1 || true
            fi
        done
    fi
    TEMP_CREATED=0
    CLAUDE_TEMP_CREATED=0
    TEMP_CLEANUP_TRIED=1
    echo "" >&2
    echo "ERROR: The temporary copy of the backup in Docker (volume '$1') was changed by" >&2
    echo "       something else while this restore was running -- for example, a restore" >&2
    echo "       started in another window. It was not used, and nothing was removed." >&2
    _restore_unchanged "       " "       " >&2
    echo "       Close any other restore window, then run this restore again." >&2
    exit 1
}

# Ctrl+C / TERM. `exit` still runs the EXIT handler below (the pause prompt): these are
# separate INT/TERM traps. (The .ps1 twin: a Ctrl+C inside its try block prints the
# matching text from its finally; once the swaps are done its remaining checks run
# outside that try, where a Ctrl+C just ends PowerShell without a message.)
_restore_on_interrupt() {
    trap - INT TERM
    echo "" >&2
    if [ "${SWAPS_DONE}" -eq 1 ]; then
        echo "Restore interrupted after your DAAF data had been replaced and checked, while" >&2
        echo "the restore was finishing its last checks. The checked copy is kept in Docker" >&2
        echo "(volume(s): $(_restore_kept_temps)). To be sure everything is in place, run" >&2
        echo "this restore again and choose the same backup:" >&2
        echo "  ${RERUN_COMMAND}" >&2
    elif [ "${SWAP_STARTED}" -eq 1 ]; then
        # Field test 2026-10-05, D3: during the Claude Code state phase the data volume
        # was already replaced and checked -- say so.
        if [ "${CLAUDE_SWAP_PHASE}" -eq 1 ]; then
            echo "Restore interrupted while the Claude Code state (login and session history) was being replaced." >&2
            echo "Your project files (DAAF data) were already replaced and checked." >&2
        else
            echo "Restore interrupted while your DAAF data was being replaced." >&2
        fi
        echo "The replacement keeps running inside Docker until it finishes. Your backup" >&2
        echo "folder ${SELECTED_NAME}/ is unchanged. Wait a few minutes, then run this restore" >&2
        echo "again and choose the same backup:" >&2
        echo "  ${RERUN_COMMAND}" >&2
    else
        _restore_remove_temps
        _restore_unchanged "Restore interrupted. " "" >&2
        if [ "${TEMP_REMOVE_FAILED}" -eq 1 ]; then _restore_kept_temp_hint "" >&2; fi
    fi
    exit 130
}
trap _restore_on_interrupt INT TERM

# EXIT handler from here on (it replaces the pause-only trap at the top and keeps its
# pause). ANY exit before a swap started that left this run's temp volumes behind --
# an unexpected command failure under `set -e`, for example -- removes them here.
# Never after a swap started (a temp copy may then be the only complete one). Exits
# that already cleaned up (or deliberately left a volume alone) set TEMP_CLEANUP_TRIED.
# Review round 3 (S-b): its first act after saving the status IGNORES INT/TERM, so a
# Ctrl+C during its cleanup cannot abort it halfway (one temp removed, the other left).
# Review round 2 (I-B): just before the pause it re-arms INT/TERM to end the script with
# the status it was already exiting with, so a Ctrl+C at the pause neither runs
# _restore_on_interrupt (whose text would be wrong here) nor changes the exit code.
# (`trap - INT TERM` alone is not enough: a Ctrl+C at the pause then ends bash with
# status 130 -- observed under a pty on 2026-10-01, scratch/engineer11 probe.)
_restore_on_exit() {
    RESTORE_EXIT_STATUS=$?
    trap '' INT TERM
    if [ "${SWAP_STARTED}" -eq 0 ] && [ "${TEMP_CLEANUP_TRIED}" -eq 0 ] && [ -n "$(_restore_kept_temps)" ]; then
        _restore_remove_temps
        echo "" >&2
        echo "The restore stopped before replacing anything (see the message above)." >&2
        _restore_unchanged "" "" >&2
        if [ "${TEMP_REMOVE_FAILED}" -eq 1 ]; then
            _restore_kept_temp_hint "" >&2
        else
            echo "Its temporary copy was removed." >&2
        fi
    fi
    trap 'exit "${RESTORE_EXIT_STATUS}"' INT TERM
    if [ "${RESTORE_PAUSE_ON_EXIT}" -eq 1 ]; then
        echo ""
        read -r -p "Press Enter to continue: " < /dev/tty || true
    fi
}
trap _restore_on_exit EXIT

# Format a KB figure as GB with one decimal (user messages).
_restore_gb() { awk -v kb="$1" 'BEGIN { printf "%.1f", kb / 1048576 }'; }

# --- (1) Leftovers from an earlier restore ---
# A swap container that is still RUNNING means an earlier restore is replacing the
# data right now: refuse. A leftover temp volume or a stopped swap container is
# offered for removal (y/n). This prompt appears ONLY when a leftover exists, so the
# usual answers (y / backup number / RESTORE) are unchanged on a clean system.
# An exact-name check that FAILS for any reason other than "no such ..." could not be
# made: it is never read as "absent" (a reused or wrongly removed leftover could hold
# the only complete copy of an interrupted swap). The exact-name list is tried first
# (_restore_name_listed); only when that fails too does the restore refuse.
_restore_inspect_failed() {
    echo "" >&2
    echo "ERROR: Could not check for a temporary copy left by an earlier restore (docker" >&2
    echo "       $1 inspect failed: $2)." >&2
    echo "       This restore has not changed anything. Make sure Docker Desktop is running," >&2
    echo "       then run the restore again. If this keeps happening, restart Docker Desktop" >&2
    echo "       and try again." >&2
    exit 1
}
# A leftover temp volume $1 that something still uses ($2 = 2) or whose users could not
# be listed ($2 = 3, see _restore_remove_volume): refuse, exit 1 (field test
# 2026-10-05, D1).
_restore_leftover_refusal() {
    echo "" >&2
    if [ "$2" -eq 2 ]; then
        echo "ERROR: Something is still using the temporary copy left by the earlier restore" >&2
        echo "       (Docker volume '$1'), so it was not removed. Another restore may" >&2
        echo "       still be running." >&2
        _restore_unchanged "       " "       " >&2
        echo "       Wait a few minutes and close any other restore window, then run this" >&2
        echo "       restore again." >&2
    else
        echo "ERROR: Could not check what is using the temporary copy left by the earlier" >&2
        echo "       restore (Docker volume '$1'; docker ps failed, exit ${RESTORE_RM_PS_EXIT}), so it was not removed." >&2
        if [ -n "${RESTORE_RM_SAID}" ]; then echo "       Docker said: ${RESTORE_RM_SAID}" >&2; fi
        _restore_unchanged "       " "       " >&2
        echo "       Make sure Docker Desktop is running, then run this restore again." >&2
    fi
    exit 1
}
# Exit 0 when the inspect (or leftover rm) error text $1 says the object does not exist.
_restore_is_not_found() {
    case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
        *"no such volume"*|*"no such container"*|*"no such object"*) return 0 ;;
    esac
    return 1
}
LEFTOVER_VOLUMES=""
LEFTOVER_CONTAINERS=""
# Review round 2 (I-A): the running state is read from STDOUT only, and the swap counts
# as running when ANY line is exactly "true". (Read through `2>&1 | tail -n 1`, a
# stderr line arriving last made a RUNNING swap look stopped, and the user was then
# offered `docker rm -f` of a live swap.) The error text is read by a second call, only
# when the first failed. (S3) Error text that is not a recognised "no such ..." message
# falls back to the exact-name lists before the check is given up as "could not check".
for sc in "${SWAP_CONTAINER_NAME}" "${CLAUDE_SWAP_CONTAINER_NAME}"; do
    SC_EXIT=0
    SC_STATE="$(docker container inspect --format '{{.State.Running}}' "${sc}" 2>/dev/null)" || SC_EXIT=$?
    if [ "${SC_EXIT}" -ne 0 ]; then
        SC_ERR="$(docker container inspect --format '{{.State.Running}}' "${sc}" 2>&1 > /dev/null)" || true
        if _restore_is_not_found "${SC_ERR}"; then continue; fi
        SC_LISTED=0
        _restore_name_listed container "${sc}" || SC_LISTED=$?
        if [ "${SC_LISTED}" -eq 1 ]; then continue; fi
        if [ "${SC_LISTED}" -eq 0 ]; then
            # It exists: the running-only list says whether it runs.
            SC_LISTED=0
            _restore_name_listed running "${sc}" || SC_LISTED=$?
            if [ "${SC_LISTED}" -eq 0 ]; then SC_STATE="true"; else SC_STATE="false"; fi
        fi
        if [ "${SC_LISTED}" -eq 2 ]; then
            _restore_inspect_failed container "$(printf '%s\n' "${SC_ERR}" | grep . | head -n 1)"
        fi
    fi
    if _restore_has_line "${SC_STATE}" true; then
        echo "" >&2
        echo "ERROR: An earlier restore is still replacing your DAAF data inside Docker" >&2
        echo "       (Docker container '${sc}' is running). Wait a few minutes for it to" >&2
        echo "       finish, then run this restore again. This restore has not changed anything." >&2
        echo "       If this keeps happening, restart Docker Desktop and try again." >&2
        exit 1
    fi
    LEFTOVER_CONTAINERS="${LEFTOVER_CONTAINERS:+${LEFTOVER_CONTAINERS} }${sc}"
done
for tv in "${TEMP_VOLUME_NAME}" "${CLAUDE_TEMP_VOLUME_NAME}"; do
    TV_EXIT=0
    # Exit code only, plus the error text on failure (no output value is matched).
    TV_OUT="$(docker volume inspect "${tv}" 2>&1)" || TV_EXIT=$?
    if [ "${TV_EXIT}" -ne 0 ]; then
        if _restore_is_not_found "${TV_OUT}"; then continue; fi
        TV_LISTED=0
        _restore_name_listed volume "${tv}" || TV_LISTED=$?
        if [ "${TV_LISTED}" -eq 1 ]; then continue; fi
        if [ "${TV_LISTED}" -eq 2 ]; then
            _restore_inspect_failed volume "$(printf '%s\n' "${TV_OUT}" | grep . | head -n 1)"
        fi
    fi
    LEFTOVER_VOLUMES="${LEFTOVER_VOLUMES:+${LEFTOVER_VOLUMES} }${tv}"
done
if [ -n "${LEFTOVER_VOLUMES}${LEFTOVER_CONTAINERS}" ]; then
    # Did that earlier restore start replacing live data? Its temp volume then holds
    # the state marker (see SWAP_MARKER). 0 = no, 1 = yes, 2 = could not be checked.
    SWAP_EVIDENCE=0
    if [ -n "${LEFTOVER_CONTAINERS}" ]; then SWAP_EVIDENCE=1; fi
    for tv in ${LEFTOVER_VOLUMES}; do
        PROBE_EXIT=0
        docker run --rm -v "${tv}:/src:ro" "${BUSYBOX_IMAGE}" sh -c "test ! -e /src/${SWAP_MARKER} || exit 3" > /dev/null 2>&1 || PROBE_EXIT=$?
        if [ "${PROBE_EXIT}" -eq 3 ]; then SWAP_EVIDENCE=1
        elif [ "${PROBE_EXIT}" -ne 0 ] && [ "${SWAP_EVIDENCE}" -eq 0 ]; then SWAP_EVIDENCE=2; fi
    done
    echo ""
    echo "A temporary copy left behind by an earlier restore that did not finish was found:"
    for tv in ${LEFTOVER_VOLUMES}; do echo "  - Docker volume '${tv}'"; done
    for sc in ${LEFTOVER_CONTAINERS}; do echo "  - Docker container '${sc}' (stopped)"; done
    if [ "${SWAP_EVIDENCE}" -eq 1 ]; then
        echo "That earlier restore had started replacing your DAAF data, so your current"
        echo "DAAF data may be incomplete. Continuing redoes the restore from the backup"
        echo "folder you chose."
    elif [ "${SWAP_EVIDENCE}" -eq 2 ]; then
        echo "It could not be checked whether that earlier restore had started replacing"
        echo "your DAAF data, so your current DAAF data may be incomplete. Continuing redoes"
        echo "the restore from the backup folder you chose."
    else
        echo "That earlier restore stopped before it replaced anything, so your current"
        echo "DAAF data was not changed by it."
    fi
    if [ "${SWAP_EVIDENCE}" -ne 0 ]; then EARLIER_SWAP_STARTED=1; fi
    echo "Your backup folders are not affected, so this temporary copy is not needed."
    echo "If another restore window is still open, answer n."
    echo ""
    # End of input (Ctrl+D, a short pipe) is a "no", never a silent `set -e` exit.
    read -r -p "Remove it and continue? (y/n): " LEFTOVER_CHOICE || LEFTOVER_CHOICE=""
    if [ "${LEFTOVER_CHOICE}" != "y" ] && [ "${LEFTOVER_CHOICE}" != "Y" ]; then
        echo ""
        _restore_unchanged "Restore cancelled. " ""
        echo "To remove the temporary copy later, run:"
        if [ -n "${LEFTOVER_CONTAINERS}" ]; then echo "  docker rm ${LEFTOVER_CONTAINERS}"; fi
        if [ -n "${LEFTOVER_VOLUMES}" ]; then _restore_remove_hint "" "${LEFTOVER_VOLUMES}"; fi
        exit 0
    fi
    # Field test 2026-10-05, D1: a never-started container left by the earlier restore's
    # Ctrl+C still references its temp volume (and the live one), so `docker volume rm`
    # failed every time. Every leftover volume's holders are listed FIRST, before anything
    # is removed: one in use (or a list that fails) refuses here, with nothing removed;
    # stopped ones are removed with the volume below (_restore_remove_volume).
    for tv in ${LEFTOVER_VOLUMES}; do
        RM_STATUS=0
        _restore_remove_volume "${tv}" check || RM_STATUS=$?
        if [ "${RM_STATUS}" -ne 0 ]; then _restore_leftover_refusal "${tv}" "${RM_STATUS}"; fi
    done
    _restore_reap_helpers
    LEFTOVER_FAILED=0
    LEFTOVER_SAID=""
    # Review round 6 (R5): each leftover swap container -- found NOT running before the
    # prompt -- is removed with a PLAIN `docker rm` (never -f). The y/n prompt can wait
    # for any length of time, and a restore started meanwhile in another window runs its
    # swap under the SAME name; the daemon refuses to remove a running container without
    # -f (daemon/delete.go: "stop the container before removing or force remove"), so
    # that swap is never killed. A failed removal stops here: no leftover volume is
    # touched (a running swap may be using the temp) and the failure message below shows
    # Docker's reason. Delta review of round 7 (ISSUE 1): a swap container that is GONE by
    # now (its --rm finished, Docker restarted, another window removed it) counts as
    # removed. A plain rm of a missing container exits 1 with "No such container" (docker
    # CLI cli/command/container/rm.go at v29.1.3 ignores not-found only for -f), so that
    # text is read as success here. Any other failure -- still running, or a removal
    # already in progress -- still stops here with nothing removed.
    for sc in ${LEFTOVER_CONTAINERS}; do
        if ! RM_SAID="$(docker rm "${sc}" 2>&1 > /dev/null)"; then
            if _restore_is_not_found "${RM_SAID}"; then continue; fi
            LEFTOVER_FAILED=1
            if [ -z "${LEFTOVER_SAID}" ]; then LEFTOVER_SAID="$(_restore_last_line "${RM_SAID}")"; fi
        fi
    done
    if [ "${LEFTOVER_FAILED}" -eq 0 ]; then
        for tv in ${LEFTOVER_VOLUMES}; do
            RM_STATUS=0
            _restore_remove_volume "${tv}" || RM_STATUS=$?
            case "${RM_STATUS}" in
                0) ;;
                2|3) _restore_leftover_refusal "${tv}" "${RM_STATUS}" ;;
                *)
                    LEFTOVER_FAILED=1
                    if [ -z "${LEFTOVER_SAID}" ]; then LEFTOVER_SAID="${RESTORE_RM_SAID}"; fi
                    ;;
            esac
        done
    fi
    if [ "${LEFTOVER_FAILED}" -ne 0 ]; then
        echo "" >&2
        echo "ERROR: Could not remove the temporary copy left by the earlier restore." >&2
        if [ -n "${LEFTOVER_SAID}" ]; then echo "       Docker said: ${LEFTOVER_SAID}" >&2; fi
        _restore_unchanged "       " "       " >&2
        echo "       Make sure no other restore is running (and Docker Desktop is running), then" >&2
        echo "       run this restore again, or remove it yourself with:" >&2
        if [ -n "${LEFTOVER_CONTAINERS}" ]; then echo "         docker rm ${LEFTOVER_CONTAINERS}" >&2; fi
        if [ -n "${LEFTOVER_VOLUMES}" ]; then _restore_remove_hint "       " "${LEFTOVER_VOLUMES}" >&2; fi
        exit 1
    fi
    echo "Removed the leftover temporary copy."
fi

# --- (2) Free space inside Docker ---
# B = what the temp copy will hold (data + Claude state, from the scan above),
# L = the live data volume now, F = free space where the volumes live. Preparing
# needs B; the swap frees L and then writes B again, so the peak need is
# max(B, 2B - L), plus a margin of max(10% of B, 1 GiB) for filesystem overhead (B
# comes from `du -sk` of the backup folder -- allocated blocks on the HOST filesystem,
# which can differ from what the same files take inside Docker) and other writes. Measured inside Docker only: on
# Docker Desktop that is the free space of Docker's disk image, not of the host drive
# (no reliable way to locate the latter from here). The live Claude volume is left out
# of L (it is small), which can only make the check stricter. Unmeasurable -> a
# WARNING and continue: running out of space while PREPARING is harmless (the live
# data is untouched and the temp copy is removed).
NEED_B_KB="${TOTAL_KB}"
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then NEED_B_KB=$(( NEED_B_KB + ${CLAUDE_KB:-0} )); fi
if [ "${NEED_B_KB}" -lt 0 ]; then NEED_B_KB=0; fi
SPACE_MARGIN_KB=$(( NEED_B_KB / 10 ))
if [ "${SPACE_MARGIN_KB}" -lt 1048576 ]; then SPACE_MARGIN_KB=1048576; fi
SPACE_KNOWN=0
SPACE_EXIT=0
SPACE_OUTPUT="$(docker run --rm -v "${VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" sh -c "${SPACE_PROGRAM}" 2>&1 | tr -d '\r')" || SPACE_EXIT=$?
AVAIL_KB="$(printf '%s\n' "${SPACE_OUTPUT}" | sed -n 's/^AVAIL_KB=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
LIVE_KB="$(printf '%s\n' "${SPACE_OUTPUT}" | sed -n 's/^LIVE_KB=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
PEAK_KB="${NEED_B_KB}"
if [ "${SPACE_EXIT}" -eq 0 ] && [ -n "${AVAIL_KB}" ] && [ -n "${LIVE_KB}" ]; then
    SPACE_KNOWN=1
    if [ $(( 2 * NEED_B_KB - LIVE_KB )) -gt "${PEAK_KB}" ]; then PEAK_KB=$(( 2 * NEED_B_KB - LIVE_KB )); fi
fi
SPACE_NEEDED_KB=$(( PEAK_KB + SPACE_MARGIN_KB ))
if [ "${SPACE_KNOWN}" -eq 1 ] && [ "${AVAIL_KB}" -lt "${SPACE_NEEDED_KB}" ]; then
    echo "" >&2
    echo "ERROR: There is not enough free space inside Docker for this restore." >&2
    echo "       The restore needs about $(_restore_gb "${SPACE_NEEDED_KB}") GB free inside Docker (it makes a temporary" >&2
    echo "       copy of the backup first, then replaces your current data); Docker has" >&2
    echo "       $(_restore_gb "${AVAIL_KB}") GB free. Free up space for Docker (for example, delete unused" >&2
    echo "       images in Docker Desktop, or free space on the drive that holds Docker's" >&2
    echo "       data), then run the restore again." >&2
    _restore_unchanged "       " "       " >&2
    exit 1
elif [ "${SPACE_KNOWN}" -eq 0 ]; then
    # L unknown: quote the worst case (L = 0).
    SPACE_NEEDED_KB=$(( 2 * NEED_B_KB + SPACE_MARGIN_KB ))
    echo "" >&2
    echo "WARNING: Could not check the free space inside Docker before the restore." >&2
    echo "         The restore needs up to about $(_restore_gb "${SPACE_NEEDED_KB}") GB free inside Docker. If it" >&2
    echo "         runs out while preparing, it stops without changing your DAAF data." >&2
    HAD_WARNINGS=1
fi

# --- (3) Prepare the temporary copy of the data volume ---
# Copy the backup into the TEMP volume via `docker create` + `docker cp` instead of a
# bind-mounted `busybox cp -a`: on Docker Desktop for Windows a bind-mounted copy
# reads every host file across the host<->VM boundary one by one, while `docker cp`
# streams the whole tree to the daemon in one pass. The helper container is created
# but never started -- `docker cp` still writes into its volume. The trailing "/." on
# the source copies the backup's CONTENTS. `docker cp` INTO a container writes files
# as ROOT, so ownership is repaired below (3c); it has no exclude flag, so the Claude
# subfolder is stripped container-side (3b). The volume is checked with the same
# count program as the post-restore check before anything is replaced.
echo ""
echo "Preparing a temporary copy of the backup inside Docker..."
echo "  Your current DAAF data is not touched until you confirm below."
echo "  This may take a few minutes for large backups."
echo ""
# Right after `docker volume create` ($1 = temp volume, $2 = live volume for the label):
# the volume must carry THIS run's identity label (a reused existing volume keeps its
# own labels) AND be empty (`find /dest -mindepth 1` lists nothing). Otherwise -- or if
# the check itself fails -- it may hold another restore's copy: refuse and leave it
# alone (it is NOT marked as created by this run, so nothing removes it).
_restore_check_new_temp() {
    local listing status=0
    # STDOUT only (review round 2): a stray stderr line (a Docker config WARNING) once
    # made every new temp look non-empty. A `find` that hits an error still exits
    # nonzero, so a listing that could not be made still fails the check.
    listing="$(docker run --rm --label "${RESTORE_LABEL}=$2" -v "$1:/dest:ro" "${BUSYBOX_IMAGE}" find /dest -mindepth 1 2>/dev/null)" || status=$?
    if [ "${status}" -eq 0 ] && [ -z "${listing}" ] && _restore_temp_is_ours "$1"; then return 0; fi
    # SF2 (review round 2): the volume under that name may be another restore's, so its
    # prepare helpers are not reaped either; this run's own other temps are removed only
    # if they still carry this run's identity label.
    TEMP_CLEANUP_CAREFUL=1
    _restore_fail_before_swap "ERROR: Could not confirm that the new temporary Docker volume '$1' is empty" \
        "       and was created by this restore, so it was left as it is (it may belong to" \
        "       another restore, for example one still open in another window)." \
        "       Close any other restore window, then run this restore again: it will show" \
        "       the leftover copy and ask whether to remove it."
}
if ! docker volume create --label "${RESTORE_LABEL}=${VOLUME_NAME}" --label "${RESTORE_RUN_LABEL}=${RESTORE_RUN_ID}" "${TEMP_VOLUME_NAME}" > /dev/null 2>&1; then
    _restore_fail_before_swap "ERROR: Could not create a temporary Docker volume ('${TEMP_VOLUME_NAME}') for the restore."
fi
_restore_check_new_temp "${TEMP_VOLUME_NAME}" "${VOLUME_NAME}"
TEMP_CREATED=1
CID=""
# Guarded: an unguarded `CID="$(docker create ...)"` under `set -e` would abort with
# no message. A CID printed by a create that then failed is reaped by label.
if ! CID="$(docker create --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}")"; then
    _restore_fail_before_swap "ERROR: Could not create the helper container for the copy."
fi
if ! docker cp "${SELECTED_PATH}/." "${CID}:/dest/"; then
    _restore_fail_before_swap "ERROR: Copying the backup into Docker failed (see the message above)."
fi
# The copy is done: remove the helper container (best-effort; a leftover is reaped
# by label with the temp volume).
docker rm -f "${CID}" > /dev/null 2>&1 || true

# --- Step 3b: Strip the Claude subfolder from the temporary DATA copy ---
# `docker cp` copied the whole backup, including "${CLAUDE_SUBDIR}/"; it belongs in
# the Claude volume (prepared below), not the data volume.
if ! docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" rm -rf "/dest/${CLAUDE_SUBDIR}"; then
    _restore_fail_before_swap "ERROR: Failed to remove the ${CLAUDE_SUBDIR} subfolder from the temporary copy."
fi

# --- Step 3c: Repair ownership on the temporary copy ---
# `docker cp` wrote the files as root; the volume must be owned by appuser (UID 1000),
# mirroring the daaf-init service in docker-compose.yml (restore must not depend on
# it having run). The swap (`cp -a`) carries this ownership into the live volume.
if ! docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" chown -R 1000:1000 /dest; then
    _restore_fail_before_swap "ERROR: Failed to set file ownership in the temporary copy."
fi

# --- Step 3d: Replay executable permissions from the manifest ---
# The manifest ("${PERMISSIONS_MANIFEST}") came along with the whole-folder `docker
# cp`. When it is PRESENT, every regular file is normalized to 0644 and exactly the
# listed paths get 0755 again -- undoing the mode loss a Windows (NTFS) round-trip
# inflicts (`docker cp` fabricates 0755 for every file, and git then flags every
# tracked 0644 file as a spurious 100644->100755 change).
#
# SAFETY RULE -- no manifest, no normalization: when the manifest is ABSENT (older
# backups, or a manifest whose write failed at backup time), do NOTHING; a blanket
# 0644 would strip exec from every script and hook.
#
# Container-side and fast: `find -type f -exec chmod 644 {} +` touches regular files
# only (directories keep 0755); the manifest is read with `while IFS= read -r`, a
# trailing CR (WriteAllLines on Windows emits CRLF) and a leading UTF-8 BOM are
# stripped as parameter-expansion suffix/prefix (busybox sed has no \xNN escapes;
# `tr -d` would corrupt multi-byte UTF-8 names), and the manifest is removed after.
# Replay failure stays a latched WARNING (the copy is intact; only permissions may be
# off), as before copy-then-swap -- it does not stop the restore.
if docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" test -f "/dest/${PERMISSIONS_MANIFEST}"; then
    echo "Restoring executable permissions from ${PERMISSIONS_MANIFEST}..."
    if ! docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" sh -c '
        set -e
        manifest="/dest/'"${PERMISSIONS_MANIFEST}"'"
        # Normalize every regular file to 644 (directories are untouched: -type f).
        find /dest -type f -exec chmod 644 {} +
        # Re-apply 755 to each manifest path, line by line (spaces in paths are fine).
        cr=$(printf "\r")
        bom=$(printf "\357\273\277")
        while IFS= read -r p; do
            p="${p%$cr}"
            p="${p#$bom}"
            [ -z "$p" ] && continue
            # A false `[ -e ... ]` here does NOT trip `set -e` (a non-final command of
            # an AND-OR list is exempt), so a missing path is skipped, not fatal.
            [ -e "/dest/$p" ] && chmod 755 "/dest/$p"
        done < "$manifest"
        # Remove the manifest -- metadata, not restored content.
        rm -f "$manifest"
    '; then
        echo "WARNING: Could not fully replay executable permissions." >&2
        echo "         Your data was copied intact; only file permissions may be off." >&2
        echo "         If git reports many files as changed by mode only, or a script" >&2
        echo "         will not run, repair with: chmod +x <file> inside the container." >&2
        HAD_WARNINGS=1
    fi
else
    echo "NOTE: No ${PERMISSIONS_MANIFEST} manifest found in this backup (it may predate"
    echo "      permission preservation, or the manifest write may have failed during"
    echo "      backup). File permissions were left as-is -- no normalization was applied."
fi

# --- Step 3e: Replay symlinks from the manifest ---
# backup_daaf.sh's staging step stripped every symlink (so `docker cp` could stream a
# symlink-free tree on Windows) and recorded each link's path + target here, TAB-
# separated. When the manifest is PRESENT, recreate each link, chown it (-h: the link
# itself), then remove the manifest. No manifest, no action. Replay failure is a
# latched WARNING (regular files are intact; such links are usually regenerable).
#
# Windows quoting: this program reaches docker.exe as one command-line string in the
# .ps1 twin, so it holds NO double quote. Unquoted expansions are exact because of
# `set -f` (no globbing) + an empty global IFS (no word splitting); `IFS=$tab` scopes
# field splitting to the `read` alone. Same program, byte for byte after the manifest
# splice, as the Claude replay below and the .ps1 twin's $symlinkReplayScript.
if docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" test -f "/dest/${SYMLINKS_MANIFEST}"; then
    echo "Restoring symlinks from ${SYMLINKS_MANIFEST}..."
    if ! docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" sh -c '
        set -ef
        IFS=
        cr=$(printf \\r)
        bom=$(printf \\357\\273\\277)
        tab=$(printf \\t)
        while IFS=$tab read -r p t; do
            p=${p#$bom}
            t=${t%$cr}
            [ -z $p ] && continue
            [ -z $t ] && continue
            ln -sf -- $t /dest/$p
            chown -h 1000:1000 /dest/$p
        done < /dest/'"${SYMLINKS_MANIFEST}"'
        rm -f /dest/'"${SYMLINKS_MANIFEST}"'
    '; then
        echo "WARNING: Could not fully replay symlinks from the manifest." >&2
        echo "         Your data was copied intact; only symbolic links may be missing." >&2
        echo "         Such links are usually regenerable (e.g. by re-running the step that" >&2
        echo "         created them). Inspect ${SYMLINKS_MANIFEST} in the backup for the list." >&2
        HAD_WARNINGS=1
    fi
fi

# --- Step 3f: Check the temporary copy against the backup ---
# The same count program as the post-restore check (textually identical, pinned by
# tests/bash/backup_twin_parity.bats). The backup count above is exact here (an
# unreadable backup was refused), so the temp copy must hold EXACTLY that many files.
# A count that cannot be read, or any difference, stops the restore before anything
# is replaced.
echo "Checking the temporary copy..."
TEMP_VERIFY_EXIT=0
TEMP_VERIFY_OUTPUT="$(docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${TEMP_VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" sh -c 'set -e; : > /tmp/count_err; n=$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=$((n)); fi' 2>&1 | tr -d '\r')" || TEMP_VERIFY_EXIT=$?
TEMP_COUNT="$(printf '%s\n' "${TEMP_VERIFY_OUTPUT}" | sed -n 's/^RESTORED_FILES=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
if [ "${TEMP_VERIFY_EXIT}" -ne 0 ]; then TEMP_COUNT=""; fi
if [ -z "${TEMP_COUNT}" ]; then
    _restore_fail_before_swap "ERROR: Could not count the files in the temporary copy (exit ${TEMP_VERIFY_EXIT}), so it" \
        "       cannot be checked against the backup."
elif [ "${TEMP_COUNT}" -eq 0 ] || [ "${TEMP_COUNT}" -ne "${TOTAL_FILES}" ]; then
    _restore_fail_before_swap "ERROR: The temporary copy holds ${TEMP_COUNT} files, but the backup has ${TOTAL_FILES}," \
        "       so the copy into Docker is not complete."
fi
echo "Verified: ${TEMP_COUNT} files in the temporary copy."

# --- Restore the Claude Code state volume ---
# Step 3g: prepare its temporary copy (the swap itself is step 5b below). Only when
# the backup contains Claude state; older backups predating the volume restore
# data-only with a NOTE. Same mechanism as the data volume (create + cp + chown + its
# own symlink manifest replay). Any failure here stops the restore before ANY volume
# is replaced (user decision D2): the data and its login state stay consistent.
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then
    echo "Preparing the Claude Code state (credentials, session history, plugins)..."
    if ! docker volume create --label "${RESTORE_LABEL}=${CLAUDE_VOLUME_NAME}" --label "${RESTORE_RUN_LABEL}=${RESTORE_RUN_ID}" "${CLAUDE_TEMP_VOLUME_NAME}" > /dev/null 2>&1; then
        _restore_fail_before_swap "ERROR: Could not prepare the Claude Code state (login and session history)" \
            "       from this backup: a temporary Docker volume could not be created."
    fi
    _restore_check_new_temp "${CLAUDE_TEMP_VOLUME_NAME}" "${CLAUDE_VOLUME_NAME}"
    CLAUDE_TEMP_CREATED=1
    CLAUDE_CID=""
    CLAUDE_CREATE_OK=0
    if CLAUDE_CID="$(docker create --label "${RESTORE_LABEL}=${CLAUDE_VOLUME_NAME}" -v "${CLAUDE_TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}")"; then
        CLAUDE_CREATE_OK=1
    fi
    CLAUDE_PREP_OK=0
    if [ "${CLAUDE_CREATE_OK}" -eq 1 ] \
        && docker cp "${CLAUDE_BACKUP_PATH}/." "${CLAUDE_CID}:/dest/" \
        && docker run --rm --label "${RESTORE_LABEL}=${CLAUDE_VOLUME_NAME}" -v "${CLAUDE_TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" chown -R 1000:1000 /dest; then
        CLAUDE_PREP_OK=1
    fi
    # Best-effort reap of the captured CID (also reaped by label on failure).
    docker rm -f "${CLAUDE_CID}" > /dev/null 2>&1 || true
    if [ "${CLAUDE_PREP_OK}" -ne 1 ]; then
        _restore_fail_before_swap "ERROR: Could not prepare the Claude Code state (login and session history)" \
            "       from this backup: copying it into Docker failed."
    fi
    # Replay the Claude volume's own symlink manifest (it sits at the Claude subfolder
    # root, so it copied into this volume's root). Same program and semantics as 3e.
    if docker run --rm --label "${RESTORE_LABEL}=${CLAUDE_VOLUME_NAME}" -v "${CLAUDE_TEMP_VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" test -f "/dest/${SYMLINKS_MANIFEST}"; then
        if ! docker run --rm --label "${RESTORE_LABEL}=${CLAUDE_VOLUME_NAME}" -v "${CLAUDE_TEMP_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" sh -c '
            set -ef
            IFS=
            cr=$(printf \\r)
            bom=$(printf \\357\\273\\277)
            tab=$(printf \\t)
            while IFS=$tab read -r p t; do
                p=${p#$bom}
                t=${t%$cr}
                [ -z $p ] && continue
                [ -z $t ] && continue
                ln -sf -- $t /dest/$p
                chown -h 1000:1000 /dest/$p
            done < /dest/'"${SYMLINKS_MANIFEST}"'
            rm -f /dest/'"${SYMLINKS_MANIFEST}"'
        '; then
            echo "WARNING: Could not fully replay Claude state symlinks." >&2
            echo "         Claude state was copied; only symbolic links may be missing." >&2
            HAD_WARNINGS=1
        fi
    fi
    echo "Claude Code state prepared."
fi

# --- Re-check the free space with the temporary copy in place ---
# The swap frees the live data (L) and writes the temp copy (S) again, so it needs
# F + L >= S + margin. Unmeasurable -> said at the prompt below.
SWAP_SPACE_KNOWN=0
SPACE_EXIT=0
SPACE_OUTPUT="$(docker run --rm -v "${VOLUME_NAME}:/dest:ro" -v "${TEMP_VOLUME_NAME}:/src:ro" "${BUSYBOX_IMAGE}" sh -c "${SPACE_PROGRAM}" 2>&1 | tr -d '\r')" || SPACE_EXIT=$?
AVAIL_KB="$(printf '%s\n' "${SPACE_OUTPUT}" | sed -n 's/^AVAIL_KB=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
LIVE_KB="$(printf '%s\n' "${SPACE_OUTPUT}" | sed -n 's/^LIVE_KB=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
SRC_KB="$(printf '%s\n' "${SPACE_OUTPUT}" | sed -n 's/^SRC_KB=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
if [ "${SPACE_EXIT}" -eq 0 ] && [ -n "${AVAIL_KB}" ] && [ -n "${LIVE_KB}" ] && [ -n "${SRC_KB}" ]; then
    SWAP_SPACE_KNOWN=1
    if [ $(( AVAIL_KB + LIVE_KB )) -lt $(( SRC_KB + SPACE_MARGIN_KB )) ]; then
        _restore_fail_before_swap "ERROR: There is not enough free space inside Docker to replace your data with the" \
            "       checked copy: it needs about $(_restore_gb $(( SRC_KB + SPACE_MARGIN_KB - LIVE_KB ))) GB free, Docker has $(_restore_gb "${AVAIL_KB}") GB." \
            "       Free up space for Docker (for example, delete unused images in Docker Desktop)," \
            "       then run the restore again."
    fi
fi

# --- (4) Confirmation (after the copy was checked; user decision D1) ---
echo ""
echo "=========================================="
echo "  *** WARNING: DESTRUCTIVE OPERATION ***"
echo "=========================================="
echo ""
echo "The backup was copied into Docker and checked: ${TEMP_COUNT} files."
echo "Typing RESTORE will now COMPLETELY ERASE the current contents of your"
echo "DAAF Docker volume and replace them with this checked copy."
echo ""
echo "All existing files, git history, research data, and"
echo "configuration in the Docker volume will be permanently"
echo "deleted and overwritten by the backup contents."
echo ""
echo "Source:      ${SELECTED_NAME}/ (${TOTAL_FILES} files, ${TOTAL_SIZE})"
echo "Destination: Docker volume '${VOLUME_NAME}'"
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then
    echo ""
    echo "This backup also contains Claude Code state (credentials and session"
    echo "history), which will be restored to volume '${CLAUDE_VOLUME_NAME}',"
    echo "overwriting any existing Claude Code login/history in this install."
fi
if [ "${SWAP_SPACE_KNOWN}" -eq 0 ]; then
    echo ""
    echo "Note: The free space inside Docker could not be checked. Replacing your data"
    echo "      needs up to about $(_restore_gb "${SPACE_NEEDED_KB}") GB free. If Docker runs out of space during"
    echo "      this step, your DAAF data may be left incomplete; the checked copy is then"
    echo "      kept so you can run the restore again."
fi
echo ""
# End of input (Ctrl+D, a short pipe) is a cancel, never a silent `set -e` exit.
read -r -p "Type RESTORE to confirm, or anything else to cancel: " CONFIRM || CONFIRM=""

if [ "${CONFIRM}" != "RESTORE" ]; then
    _restore_remove_temps
    echo ""
    _restore_unchanged "Restore cancelled. " ""
    if [ "${TEMP_REMOVE_FAILED}" -eq 1 ]; then _restore_kept_temp_hint ""; fi
    exit 0
fi

# Nothing may use the live volumes while they are replaced (a container could have
# been started -- e.g. by another install sharing the volume -- since the first check).
# Names come from stdout only. A FAILED `docker ps` is not "nothing is running": the
# check could not be made, so refuse (same wording and outcome as the .ps1 twin).
RUNNING_NOW=""
RUNNING_NOW_EXIT=0
RUNNING_NOW="$(docker ps --filter "volume=${VOLUME_NAME}" --filter "volume=${CLAUDE_VOLUME_NAME}" --format '{{.Names}}' 2>/dev/null)" || RUNNING_NOW_EXIT=$?
if [ "${RUNNING_NOW_EXIT}" -ne 0 ]; then
    _restore_fail_before_swap "ERROR: Could not check whether DAAF is running (docker ps failed, exit ${RUNNING_NOW_EXIT})," \
        "       so your data cannot be replaced safely. Make sure Docker Desktop is running," \
        "       then run the restore again."
elif [ -n "${RUNNING_NOW}" ]; then
    _restore_fail_before_swap "ERROR: A container started using your DAAF data while the restore was being" \
        "       prepared: $(printf '%s' "${RUNNING_NOW}" | tr '\n' ' ')" \
        "       Stop it (docker compose down) and run the restore again."
fi

# The temp volumes must still be the ones this run created and checked: while the
# RESTORE prompt waited, a restore in another window (answering y to its leftover
# question) or a user could have removed one, or replaced it with another copy. Checked
# BEFORE the marker write, because mounting a vanished name would make Docker create a
# new, EMPTY volume.
for tv in $(_restore_kept_temps); do
    if ! _restore_temp_is_ours "${tv}"; then _restore_refuse_changed_temp "${tv}"; fi
done

# State marker: written into each temp volume right before the swaps start, so a
# leftover temp volume shows whether a swap may have run (see SWAP_MARKER).
MARKERS_WRITTEN=1
for tv in $(_restore_kept_temps); do
    if ! docker run --rm --label "${RESTORE_LABEL}=${VOLUME_NAME}" -v "${tv}:/dest" "${BUSYBOX_IMAGE}" touch "/dest/${SWAP_MARKER}"; then
        _restore_fail_before_swap "ERROR: Could not prepare the temporary copy for the final step."
    fi
done

# Exit 0 when the SWAP_VERIFY_PROGRAM output $1 proves a match: SWAP_VERIFY=MATCH AND
# SWAP_VERIFY_ENTRIES=n:n with equal counts -- and, when $2 is "nonempty", n > 0. Two
# EMPTY trees (a vanished temp volume that Docker re-created empty) or lists that
# could not be written otherwise "match". The Claude volume may legitimately be empty
# (a backup taken before any login holds only an empty symlink manifest), so it is
# checked without "nonempty"; its identity re-check guards it instead.
_restore_swap_checked() {
    local entries nl
    nl="$(printf '\nx')"
    nl="${nl%x}"
    # A `case` match, not `printf | grep -q`: under pipefail, grep -q exiting at the
    # first match can SIGPIPE the printf and fail the pipeline (a false "no match").
    case "${nl}$1${nl}" in
        *"${nl}SWAP_VERIFY=MATCH${nl}"*) ;;
        *) return 1 ;;
    esac
    entries="$(printf '%s\n' "$1" | sed -n 's/^SWAP_VERIFY_ENTRIES=\([0-9][0-9]*\):\([0-9][0-9]*\)$/\1 \2/p' | tail -n 1)"
    [ -n "${entries}" ] || return 1
    [ "${entries% *}" -eq "${entries#* }" ] || return 1
    if [ "${2:-}" = "nonempty" ] && [ "${entries% *}" -eq 0 ]; then return 1; fi
    return 0
}

# Right before the data swap (after the marker write): still our volume?
if ! _restore_temp_is_ours "${TEMP_VOLUME_NAME}"; then _restore_refuse_changed_temp "${TEMP_VOLUME_NAME}"; fi

# --- (5) Replace the live volumes inside Docker ---
# ONE container per volume, named (a re-run can see it still running) and unlabelled
# (no reap can kill it), with --sig-proxy=false so a Ctrl+C here is never forwarded:
# the swap always runs to the end inside Docker. From here on nothing deletes a temp
# volume except the final cleanup after every check passed.
echo ""
echo "Replacing your DAAF data with the checked copy..."
echo "  Do not close this window or quit Docker Desktop until this step finishes."
SWAP_STARTED=1
SWAP_EXIT=0
docker run --rm --sig-proxy=false --name "${SWAP_CONTAINER_NAME}" -v "${TEMP_VOLUME_NAME}:/src:ro" -v "${VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" sh -c "${SWAP_PROGRAM}" || SWAP_EXIT=$?
if [ "${SWAP_EXIT}" -eq 3 ]; then
    _restore_fail_swap_not_run "${SWAP_EXIT}"
elif [ "${SWAP_EXIT}" -ne 0 ]; then
    _restore_fail_after_swap "ERROR: Replacing your DAAF data did not complete (exit ${SWAP_EXIT})."
fi
SWAP_VERIFY_OUTPUT="$(docker run --rm -v "${TEMP_VOLUME_NAME}:/src:ro" -v "${VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" sh -c "${SWAP_VERIFY_PROGRAM}" 2>&1 | tr -d '\r')" || true
if ! _restore_swap_checked "${SWAP_VERIFY_OUTPUT}" nonempty; then
    _restore_fail_after_swap "ERROR: After replacing your DAAF data, it could not be confirmed to match the" \
        "       checked copy (file names, sizes, permissions and owners)."
fi

# --- (5b) Replace the Claude Code state volume ---
# Same swap program and check as the data volume, right after it (before the live
# count check, the same order as the .ps1 twin).
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then
    # Field test 2026-10-05, D3: from here an interrupt says the Claude Code state was
    # being replaced (the data volume already is, and was checked).
    CLAUDE_SWAP_PHASE=1
    echo ""
    echo "Replacing the Claude Code state..."
    # Right before the Claude swap: still our volume? (The data volume is already
    # replaced and checked, so every Claude failure below says so plainly -- S5; the
    # changed volume is not ours, so it is not listed as the kept copy.)
    if ! _restore_temp_is_ours "${CLAUDE_TEMP_VOLUME_NAME}"; then
        CLAUDE_TEMP_CREATED=0
        _restore_fail_claude_after_data "ERROR: The temporary copy of the Claude Code state (volume '${CLAUDE_TEMP_VOLUME_NAME}')" \
            "       was changed by something else -- for example, a restore started in another" \
            "       window -- so it was not used."
    fi
    SWAP_EXIT=0
    docker run --rm --sig-proxy=false --name "${CLAUDE_SWAP_CONTAINER_NAME}" -v "${CLAUDE_TEMP_VOLUME_NAME}:/src:ro" -v "${CLAUDE_VOLUME_NAME}:/dest" "${BUSYBOX_IMAGE}" sh -c "${SWAP_PROGRAM}" || SWAP_EXIT=$?
    # Exit 3 is the program's own refusal before its rm (the live Claude state is
    # untouched); any other outcome means the swap ran and may have erased it (S-a).
    if [ "${SWAP_EXIT}" -ne 3 ]; then CLAUDE_SWAP_RAN=1; fi
    if [ "${SWAP_EXIT}" -ne 0 ]; then
        _restore_fail_claude_after_data "ERROR: Replacing the Claude Code state (login and session history) did not" \
            "       complete (exit ${SWAP_EXIT})."
    fi
    SWAP_VERIFY_OUTPUT="$(docker run --rm -v "${CLAUDE_TEMP_VOLUME_NAME}:/src:ro" -v "${CLAUDE_VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" sh -c "${SWAP_VERIFY_PROGRAM}" 2>&1 | tr -d '\r')" || true
    if ! _restore_swap_checked "${SWAP_VERIFY_OUTPUT}"; then
        _restore_fail_claude_after_data "ERROR: After replacing the Claude Code state, it could not be confirmed to match" \
            "       the checked copy."
    fi
    echo "Claude Code state restored."
fi
SWAPS_DONE=1

# --- Verify ---
# Count the restored volume like with like: the same root exclusions as the backup
# count above (a root manifest left behind when a replay failed, and the
# ".daaf-claude-config" subtree) and one `stat` line per file, so a name holding a
# newline counts once. Quote-free and textually identical to the .ps1 twin's program
# (pinned by tests/bash/backup_twin_parity.bats); the names are hardcoded literals
# (SYNC NOTE: update by hand if PERMISSIONS_MANIFEST, SYMLINKS_MANIFEST or
# CLAUDE_SUBDIR changes). It is the same program that counted the temp copy (step 3f),
# and the swap copied that copy, so the two counts must be EQUAL: any difference --
# including 0 -- goes through the after-swap failure path (temp copy kept, recovery
# steps, exit 1). (The temp count itself was checked against the backup in step 3f.)
#
# READ ERRORS: a pipeline's status is its last command's (wc), so the count's stderr
# goes to the throwaway container's /tmp/count_err and the program prints
# RESTORED_FILES=<n> only when that file is empty, else RESTORED_COUNT_ERRORS=<lines>.
# Unavailable count: a WARNING, exit 0 -- the swap and its metadata check succeeded;
# only this check could not run.
echo "Verifying restore..."
VERIFY_EXIT=0
VERIFY_OUTPUT="$(docker run --rm -v "${VOLUME_NAME}:/dest:ro" "${BUSYBOX_IMAGE}" sh -c 'set -e; : > /tmp/count_err; n=$(find /dest -type f ! -path /dest/.daaf-symlinks ! -path /dest/.daaf-permissions ! -path /dest/.daaf-claude-config/\* -exec stat -c %s {} + 2>/tmp/count_err | wc -l); if test -s /tmp/count_err; then echo RESTORED_COUNT_ERRORS=$(grep -c ^ /tmp/count_err); else echo RESTORED_FILES=$((n)); fi' 2>&1 | tr -d '\r')" || VERIFY_EXIT=$?
RESTORED_COUNT="$(printf '%s\n' "${VERIFY_OUTPUT}" | sed -n 's/^RESTORED_FILES=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
RESTORED_ERRORS="$(printf '%s\n' "${VERIFY_OUTPUT}" | sed -n 's/^RESTORED_COUNT_ERRORS=\([0-9][0-9]*\)$/\1/p' | tail -n 1)"
if [ "${VERIFY_EXIT}" -ne 0 ]; then RESTORED_COUNT=""; fi
# The completion report's "Files:" value (identical wording in the .ps1 twin).
RESTORED_LABEL="${RESTORED_COUNT} files in volume"

if [ -z "${RESTORED_COUNT}" ]; then
    RESTORED_LABEL="not verified (the restored file count could not be read)"
    echo "" >&2
    if [ -n "${RESTORED_ERRORS}" ]; then
        echo "WARNING: Could not verify the restored file count: Docker hit ${RESTORED_ERRORS} read error(s)" >&2
        echo "         while counting the restored volume." >&2
    else
        echo "WARNING: Could not verify the restored file count (the count inside Docker did not" >&2
        echo "         run cleanly, exit ${VERIFY_EXIT})." >&2
    fi
    echo "         The copy itself reported success, so your data is most likely in place. Start" >&2
    echo "         DAAF and check your files; if anything is missing, re-run this restore." >&2
    HAD_WARNINGS=1
elif [ "${RESTORED_COUNT}" -ne "${TEMP_COUNT}" ]; then
    _restore_fail_after_swap "ERROR: After replacing your DAAF data, it holds ${RESTORED_COUNT} files, but the checked" \
        "       copy held ${TEMP_COUNT}."
else
    echo "Verified: ${RESTORED_COUNT} files in restored volume."
fi

if [ "${HAS_CLAUDE_BACKUP}" -ne 1 ]; then
    echo ""
    echo "NOTE: This backup does not contain Claude Code state (it predates the"
    echo "      dedicated Claude volume). Your data was restored, but Claude Code"
    echo "      login and session history were NOT part of this backup -- you may"
    echo "      need to run /login again after starting DAAF."
fi

# --- (6) Remove the temporary copies ---
# Every check passed. A removal failure does not undo the restore: a latched WARNING
# with the exact command, exit 0.
_restore_remove_temps final
trap - INT TERM
if [ "${TEMP_REMOVE_FAILED}" -eq 1 ]; then
    KEPT_TEMPS="$(_restore_kept_temps)"
    echo "" >&2
    echo "WARNING: Could not remove the temporary copy of your data (Docker volume(s): ${KEPT_TEMPS})." >&2
    if [ -n "${TEMP_REMOVE_NOTE}" ]; then
        while IFS= read -r NOTE_LINE; do echo "         ${NOTE_LINE}" >&2; done <<EOF
${TEMP_REMOVE_NOTE}
EOF
    fi
    echo "         Your DAAF data was restored. To free the space it uses, run:" >&2
    _restore_remove_hint "         " "${KEPT_TEMPS}" >&2
    HAD_WARNINGS=1
fi

echo ""
echo "=========================================="
if [ "${HAD_WARNINGS}" -eq 1 ]; then
    echo "  Restore completed WITH WARNINGS -- verify before relying on it"
else
    echo "  Restore complete!"
fi
echo "=========================================="
echo ""
echo "Restored: ${SELECTED_NAME}"
echo "Files:    ${RESTORED_LABEL}"
echo ""
echo "You can now start DAAF with:"
echo "  bash run_daaf.sh"
echo ""
