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
# WARNING: Restoring is a DESTRUCTIVE operation. The entire contents of the
# Docker volume are erased and replaced with the backup contents.
#
# Supports DAAF_TEST_MODE=1 for test framework sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output.
# Suppressed by DAAF_NESTED (to avoid double-pause when called from
# another script) and CI environments.
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# environment so the volume name below reflects DAAF_PROJECT_NAME and the
# `docker compose down` further below targets the right project. Canonical shared
# pattern (kept in sync with load_daaf_settings in daaf_lib.sh). Parse only these
# four keys (never `source` -- the file holds API keys); shell env wins; absent
# file = no-op; CR stripped; Bash 3.2 safe.
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
# Project-prefixed volume name "<project>_daaf-data". Default unset =>
# "daaf_daaf-data" (byte-for-byte identical to the previous hardcoded value).
VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-data"
# Second volume: Claude Code state. Restored only when the selected backup
# contains the dedicated subfolder (newer backups); older backups predating the
# volume are restored data-only with a warning.
CLAUDE_VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-claude-config"
CLAUDE_SUBDIR=".daaf-claude-config"

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI
# cross-platform smoke testing without a Docker daemon.
if [ "${DAAF_DRY_RUN:-}" = "1" ]; then
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 0 ;;
            *"ps --filter"*) return 0 ;;
            *"run --rm"*"rm -rf"*) return 0 ;;
            *"run --rm"*"cp -a"*) return 0 ;;
            *"run --rm"*"find /dest"*)
                echo "42"
                return 0
                ;;
            *)
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
    exit 1
fi

if ! docker volume inspect "${VOLUME_NAME}" &> /dev/null; then
    echo "ERROR: Docker volume '${VOLUME_NAME}' not found." >&2
    echo "Have you run the DAAF installer yet?" >&2
    exit 1
fi

# --- Check for running containers using the volume ---
RUNNING_CONTAINERS=""
RUNNING_CONTAINERS=$(docker ps --filter "volume=${VOLUME_NAME}" --format '{{.Names}}' 2>/dev/null || true)
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
    read -r -p "Stop the container now? (y/n): " STOP_CHOICE
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
    count=$(find "${dir}" -type f 2>/dev/null | wc -l | tr -d '[:space:]') || count="?"
    size=$(du -sh "${dir}" 2>/dev/null | awk '{print $1}') || size="?"
    printf "  %d) %s  (%s files, %s)\n" "$((i + 1))" "${name}" "${count}" "${size}"
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
read -r -p "Enter backup number to restore (1-${#SORTED_BACKUPS[@]}): " CHOICE

if ! [[ "${CHOICE}" =~ ^[0-9]+$ ]] || [ "${CHOICE}" -lt 1 ] || [ "${CHOICE}" -gt "${#SORTED_BACKUPS[@]}" ]; then
    echo "" >&2
    echo "ERROR: Invalid selection '${CHOICE}'. Please enter a number between 1 and ${#SORTED_BACKUPS[@]}." >&2
    exit 1
fi

SELECTED="${SORTED_BACKUPS[$((CHOICE - 1))]}"
SELECTED_NAME="$(basename "${SELECTED}")"
SELECTED_PATH="$(cd "${SELECTED}" && pwd)"

echo ""
echo "Selected: ${SELECTED_NAME}"

# --- Detect Claude Code state in the backup ---
# Newer backups nest the Claude Code state volume in a hidden subfolder. Older
# backups (created before the dedicated volume existed) lack it -- those restore
# data-only with a warning.
CLAUDE_BACKUP_PATH="${SELECTED_PATH}/${CLAUDE_SUBDIR}"
HAS_CLAUDE_BACKUP=0
# Require the subfolder to exist AND be non-empty. An empty "${CLAUDE_SUBDIR}/"
# dir (e.g., a stray pre-created folder from an interrupted backup) must NOT
# trigger the Claude restore path below -- that path CLEARS the live claude-config
# volume before copying, so restoring from an empty source would wipe the user's
# Claude Code login and session history and copy nothing back.
if [ -d "${CLAUDE_BACKUP_PATH}" ] && [ -n "$(ls -A "${CLAUDE_BACKUP_PATH}" 2>/dev/null)" ]; then
    HAS_CLAUDE_BACKUP=1
fi

# --- Count source files ---
# Exclude the Claude subfolder from the DATA-volume count -- it is restored to a
# separate volume below, not into the data volume.
echo ""
echo "Scanning backup..."
TOTAL_FILES=$(find "${SELECTED_PATH}" -type f -not -path "${CLAUDE_BACKUP_PATH}/*" | wc -l | tr -d '[:space:]')
# Size must match the file count above: data-volume contents only, excluding the
# Claude subfolder (which restores to its own volume). BSD du has no --exclude,
# so subtract the subfolder's KB from the total and humanize with awk.
TOTAL_KB=$(du -sk "${SELECTED_PATH}" 2>/dev/null | awk '{print $1}')
TOTAL_KB=${TOTAL_KB:-0}
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then
    CLAUDE_KB=$(du -sk "${CLAUDE_BACKUP_PATH}" 2>/dev/null | awk '{print $1}')
    TOTAL_KB=$(( TOTAL_KB - ${CLAUDE_KB:-0} ))
fi
TOTAL_SIZE=$(awk -v kb="${TOTAL_KB}" 'BEGIN { if (kb >= 1048576) printf "%.1fG", kb/1048576; else if (kb >= 1024) printf "%.1fM", kb/1024; else printf "%dK", kb }')
echo "Found ${TOTAL_FILES} files (${TOTAL_SIZE}) to restore."

# --- Destructive warning ---
echo ""
echo "=========================================="
echo "  *** WARNING: DESTRUCTIVE OPERATION ***"
echo "=========================================="
echo ""
echo "This will COMPLETELY ERASE the current contents of your"
echo "DAAF Docker volume and replace them with the backup."
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
echo ""
read -r -p "Type RESTORE to confirm, or anything else to cancel: " CONFIRM

if [ "${CONFIRM}" != "RESTORE" ]; then
    echo ""
    echo "Restore cancelled."
    exit 0
fi

echo ""

# --- Step 1: Clear the Docker volume ---
echo "Clearing Docker volume..."
if ! docker run --rm -v "${VOLUME_NAME}:/dest" busybox sh -c 'rm -rf /dest/* /dest/.[!.]* /dest/..?*'; then
    echo "ERROR: Failed to clear Docker volume." >&2
    echo "The volume may be in an inconsistent state." >&2
    exit 1
fi
echo "Volume cleared."
echo ""

# --- Step 2: Copy backup into volume ---
echo "Copying backup into Docker volume..."
echo "  This may take a few minutes for large backups."
echo ""

# Copy everything, then strip the Claude subfolder from the DATA volume -- it
# belongs in the separate Claude volume (restored below), not the data volume.
if ! docker run --rm \
    -v "${SELECTED_PATH}:/source:ro" \
    -v "${VOLUME_NAME}:/dest" \
    busybox sh -c "cp -a /source/. /dest/ && rm -rf \"/dest/${CLAUDE_SUBDIR}\""; then
    echo "" >&2
    echo "ERROR: File copy failed." >&2
    echo "The Docker volume may be in an inconsistent state." >&2
    echo "You may want to re-run this restore or reinstall DAAF." >&2
    exit 1
fi
echo "Copy complete."
echo ""

# --- Verify ---
echo "Verifying restore..."
RESTORED_COUNT=$(docker run --rm -v "${VOLUME_NAME}:/dest:ro" busybox sh -c 'find /dest -type f | wc -l' | tr -d '[:space:]')

if [ "${RESTORED_COUNT}" -eq 0 ]; then
    echo "" >&2
    echo "ERROR: Verification failed -- 0 files found in restored volume." >&2
    echo "The restore may have failed. Consider re-running or reinstalling DAAF." >&2
    exit 1
fi

echo "Verified: ${RESTORED_COUNT} files in restored volume."

# --- Size comparison ---
if [ "${TOTAL_FILES}" -gt 0 ] && [ "${RESTORED_COUNT}" -gt 0 ]; then
    DIFF=$((TOTAL_FILES - RESTORED_COUNT))
    if [ "${DIFF}" -lt 0 ]; then DIFF=$(( -DIFF )); fi
    TOLERANCE=$(( TOTAL_FILES / 100 ))
    if [ "${TOLERANCE}" -lt 1 ]; then TOLERANCE=1; fi
    if [ "${DIFF}" -gt "${TOLERANCE}" ]; then
        echo ""
        echo "WARNING: File count mismatch." >&2
        echo "         Backup: ${TOTAL_FILES} files, Restored: ${RESTORED_COUNT} files (difference: ${DIFF})" >&2
        echo "         The restore may be incomplete." >&2
    fi
fi

# --- Restore the Claude Code state volume ---
# Only when the backup contains it. Older backups predating the volume are
# restored data-only, with a clear warning (not an error) so the user knows
# Claude Code login/history was not part of that backup.
if [ "${HAS_CLAUDE_BACKUP}" -eq 1 ]; then
    echo ""
    echo "Restoring Claude Code state (credentials, session history, plugins)..."
    # Ensure the volume exists (a fresh install created by `docker compose up`
    # will have it; create it explicitly here in case restore runs before first
    # start). `docker volume create` is idempotent.
    docker volume create "${CLAUDE_VOLUME_NAME}" > /dev/null 2>&1 || true
    # Clear then copy, mirroring the data-volume restore semantics.
    if ! docker run --rm -v "${CLAUDE_VOLUME_NAME}:/dest" busybox sh -c 'rm -rf /dest/* /dest/.[!.]* /dest/..?*'; then
        echo "WARNING: Failed to clear the Claude Code state volume before restore." >&2
        echo "         Data volume restore above succeeded; Claude state may be inconsistent." >&2
    elif ! docker run --rm \
        -v "${CLAUDE_BACKUP_PATH}:/source:ro" \
        -v "${CLAUDE_VOLUME_NAME}:/dest" \
        busybox sh -c "cp -a /source/. /dest/"; then
        echo "WARNING: Failed to restore the Claude Code state volume." >&2
        echo "         Data volume restore above succeeded; you may need to re-run /login." >&2
    else
        echo "Claude Code state restored."
    fi
else
    echo ""
    echo "NOTE: This backup does not contain Claude Code state (it predates the"
    echo "      dedicated Claude volume). Your data was restored, but Claude Code"
    echo "      login and session history were NOT part of this backup -- you may"
    echo "      need to run /login again after starting DAAF."
fi

echo ""
echo "=========================================="
echo "  Restore complete!"
echo "=========================================="
echo ""
echo "Restored: ${SELECTED_NAME}"
echo "Files:    ${RESTORED_COUNT} files in volume"
echo ""
echo "You can now start DAAF with:"
echo "  bash run_daaf.sh"
echo ""
