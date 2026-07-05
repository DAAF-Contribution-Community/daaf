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
# with load_daaf_settings in daaf_lib.sh). Parse only these four keys (never
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
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*)
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
VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-data"
# Second volume: Claude Code state (auth/credentials, session history and
# transcripts, plugins, ~/.claude.json). Backed up into a dedicated hidden
# subfolder of the backup so it does not contaminate the data-volume file
# counts (which scan the backup root). May not exist on very old installs that
# predate the volume -- handled gracefully below.
CLAUDE_VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-claude-config"
CLAUDE_SUBDIR=".daaf-claude-config"
TODAY=$(date +%Y-%m-%d)

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker, curl) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 0 ;;
            *"run --rm"*"find /source"*)
                printf '100\n1024\t/source\n1M\t/source\n1024\n'
                return 0
                ;;
            *)
                # The dry-run path exits before any create/cp/rm, so no match arm
                # is needed for the copy mechanism -- the default is only reached
                # for unmodeled calls, which are echoed and treated as no-ops.
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
    exit 1
fi

# Check the volume exists
if ! docker volume inspect "${VOLUME_NAME}" &> /dev/null; then
    echo "ERROR: Docker volume '${VOLUME_NAME}' not found."
    echo "Have you run the DAAF installer yet?"
    exit 1
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
echo ""

# --- Count source files ---
echo "Scanning Docker volume..."
SCAN_OUTPUT=$(docker run --rm -v "${VOLUME_NAME}:/source:ro" busybox sh -c 'find /source -type f | wc -l && du -sk /source && du -sh /source && find /source -type f -exec stat -c "%s" {} + | awk "{s+=\$1} END {print int(s/1024)}"') || {
    echo ""
    echo "ERROR: Could not scan Docker volume."
    exit 1
}
TOTAL_FILES=$(echo "${SCAN_OUTPUT}" | head -1 | tr -d '[:space:]')
VOLUME_SIZE_KB=$(echo "${SCAN_OUTPUT}" | sed -n '2p' | awk '{print $1}')
TOTAL_SIZE=$(echo "${SCAN_OUTPUT}" | sed -n '3p' | awk '{print $1}')
VOLUME_LOGICAL_KB=$(echo "${SCAN_OUTPUT}" | sed -n '4p' | tr -d '[:space:]')
echo "Found ${TOTAL_FILES} files to copy (${TOTAL_SIZE})."
echo ""

# --- Disk space pre-check ---
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
echo "Copying files from Docker volume..."
printf "  Progress: 0 / %d files (0%%)" "${TOTAL_FILES}"

# Copy the data volume out via `docker create` + `docker cp` instead of a
# bind-mounted `busybox cp -a`. On Docker Desktop for Windows, every file a
# bind-mounted copy writes crosses the 9p/gRPC-FUSE host<->VM boundary
# individually, so a large volume takes minutes. `docker cp` streams the whole
# tree through the daemon in one pass, avoiding that per-file overhead entirely.
# The helper container is created but never started -- `docker cp` still reads
# the volume because the daemon mounts the container root AND its volume
# MountPoints into the archive view regardless of container state. Crucially,
# `docker cp` (without -a/--archive) extracts container->host files as the
# INVOKING user, so ownership is correct by construction -- there is no bind-mount
# UID reset and hence no chown-repair step. The trailing "/." on the source copies
# the volume's CONTENTS into "${BACKUP_NAME}" rather than nesting a "source" dir.
CID="$(docker create -v "${VOLUME_NAME}:/source:ro" busybox)"
# Install the interrupt trap right after the helper container exists so an INT/TERM
# between here and the copy still removes it. COPY_PID may not be set yet (the copy
# is backgrounded just below), so the trap guards it with ${COPY_PID:-} under set -u.
COPY_PID=""
trap 'if [ -n "${COPY_PID:-}" ]; then kill "${COPY_PID}" 2>/dev/null; wait "${COPY_PID}" 2>/dev/null; fi; docker rm -f "${CID}" > /dev/null 2>&1 || true' INT TERM

docker cp "${CID}:/source/." "${BACKUP_NAME}/" &
COPY_PID=$!

while kill -0 "${COPY_PID}" 2>/dev/null; do
    sleep 3
    if ! kill -0 "${COPY_PID}" 2>/dev/null; then
        break
    fi
    COPIED=$(find "${BACKUP_NAME}" -type f 2>/dev/null | wc -l | tr -d '[:space:]') || COPIED=0
    if [ "${TOTAL_FILES}" -gt 0 ]; then
        PERCENT=$((COPIED * 100 / TOTAL_FILES))
        if [ "${PERCENT}" -gt 100 ]; then PERCENT=100; fi
    else
        PERCENT=0
    fi
    printf "\r  Progress: %d / %d files (%d%%)   " "${COPIED}" "${TOTAL_FILES}" "${PERCENT}"
done

COPY_EXIT=0
wait "${COPY_PID}" || COPY_EXIT=$?
printf "\r  Progress: %d / %d files (100%%)   \n" "${TOTAL_FILES}" "${TOTAL_FILES}"

# Remove the helper container. Best-effort: the copy is already done, so a
# failure here must never fail the backup.
docker rm -f "${CID}" > /dev/null 2>&1 || true
trap - INT TERM

# --- Verify ---
FILE_COUNT=$(find "${BACKUP_NAME}" -type f 2>/dev/null | wc -l | tr -d '[:space:]') || FILE_COUNT=0

if [ "${FILE_COUNT}" -eq 0 ]; then
    echo ""
    if [ "${COPY_EXIT}" -ne 0 ]; then
        echo "ERROR: Backup failed (exit code ${COPY_EXIT}). Check Docker Desktop for errors."
    else
        echo "WARNING: Backup completed but 0 files were copied."
        echo "The Docker volume may be empty. Is DAAF properly installed?"
    fi
    echo "Location: $(pwd)/${BACKUP_NAME}/"
    exit 1
fi

if [ "${COPY_EXIT}" -ne 0 ]; then
    echo "Note: File copy reported warnings (exit code ${COPY_EXIT}) but all ${FILE_COUNT} files were transferred."
fi

# --- Size verification ---
# Compare source vs backup logical byte sums to detect truncated files
SOURCE_SIZE_KB="${VOLUME_LOGICAL_KB}"
BACKUP_SIZE_KB=$(find "${BACKUP_NAME}" -type f -exec ls -ln {} + 2>/dev/null | awk '{s+=$5} END {printf "%d\n", s/1024}') || BACKUP_SIZE_KB=0
if [ "${SOURCE_SIZE_KB}" -gt 0 ] && [ "${BACKUP_SIZE_KB}" -gt 0 ]; then
    # Allow 1% tolerance for filesystem metadata differences
    TOLERANCE_KB=$(( SOURCE_SIZE_KB / 100 ))
    if [ "${TOLERANCE_KB}" -lt 1 ]; then TOLERANCE_KB=1; fi
    DIFF_KB=$(( SOURCE_SIZE_KB - BACKUP_SIZE_KB ))
    # Absolute value
    if [ "${DIFF_KB}" -lt 0 ]; then DIFF_KB=$(( -DIFF_KB )); fi
    if [ "${DIFF_KB}" -gt "${TOLERANCE_KB}" ]; then
        echo ""
        echo "WARNING: Backup size mismatch." >&2
        echo "         Source: ${SOURCE_SIZE_KB} KB, Backup: ${BACKUP_SIZE_KB} KB (difference: ${DIFF_KB} KB)" >&2
        echo "         The backup may be incomplete. Consider re-running." >&2
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
    echo "Backing up Claude Code state (credentials, session history, plugins)..."
    mkdir -p "${BACKUP_NAME}/${CLAUDE_SUBDIR}"
    # Same `docker create` + `docker cp` + `docker rm` mechanism as the data
    # volume above, but synchronous (this copy is small). `docker cp` extracts as
    # the invoking user, so the Claude state files land user-owned with no chown
    # repair -- which is why the old ownership-repair step is gone entirely.
    CLAUDE_CID="$(docker create -v "${CLAUDE_VOLUME_NAME}:/source:ro" busybox)"
    # Re-register an interrupt trap around this block: the data-copy trap was
    # cleared above, so without this a Ctrl-C during the Claude create/cp window
    # would leak the helper container. Best-effort removal; guarded under set -u.
    trap 'docker rm -f "${CLAUDE_CID:-}" > /dev/null 2>&1 || true' INT TERM
    if docker cp "${CLAUDE_CID}:/source/." "${BACKUP_NAME}/${CLAUDE_SUBDIR}/"; then
        CLAUDE_FILE_COUNT=$(find "${BACKUP_NAME}/${CLAUDE_SUBDIR}" -type f 2>/dev/null | wc -l | tr -d '[:space:]') || CLAUDE_FILE_COUNT=0
        echo "Claude Code state backed up (${CLAUDE_FILE_COUNT} files)."
        CLAUDE_BACKED_UP=1
    else
        echo "WARNING: Failed to back up the Claude Code state volume." >&2
        echo "         The data volume backup above is still valid." >&2
    fi
    docker rm -f "${CLAUDE_CID}" > /dev/null 2>&1 || true
    trap - INT TERM
else
    echo ""
    echo "NOTE: No Claude Code state volume ('${CLAUDE_VOLUME_NAME}') found."
    echo "      Skipping -- this install may predate the dedicated Claude volume."
fi

echo ""
echo "=========================================="
echo "  Backup complete!"
echo "=========================================="
echo ""
echo "Location: $(pwd)/${BACKUP_NAME}/"
echo "Files:    ${FILE_COUNT} files copied"
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
echo "The restore script lets you pick which backup to restore from and"
echo "handles clearing the volume before copying to ensure a clean state."
echo ""
