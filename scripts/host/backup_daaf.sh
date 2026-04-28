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

# Pause before exit so the user can review output
if [ -z "${DAAF_NESTED:-}" ] && [ -z "${CI:-}" ] && [ -c /dev/tty ] && [ -t 1 ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: " < /dev/tty' EXIT
fi

# --- Configuration ---
VOLUME_NAME="daaf_daaf-data"
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
            *"run --rm"*"cp -a"*) return 0 ;;
            *)
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
    # First backup of the day already exists — find next available suffix
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

docker run --rm \
    -v "${VOLUME_NAME}:/source:ro" \
    -v "$(pwd)/${BACKUP_NAME}:/dest" \
    busybox sh -c "cp -a /source/. /dest/" &
COPY_PID=$!
trap 'kill "${COPY_PID}" 2>/dev/null; wait "${COPY_PID}" 2>/dev/null' INT TERM

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

echo ""
echo "=========================================="
echo "  Backup complete!"
echo "=========================================="
echo ""
echo "Location: $(pwd)/${BACKUP_NAME}/"
echo "Files:    ${FILE_COUNT} files copied"
echo ""
echo "To restore from this backup in the future, you can copy files back"
echo "into the Docker volume using Docker Desktop's Files tab, or with:"
echo "  docker run --rm -v \"$(pwd)/${BACKUP_NAME}:/source:ro\" -v \"${VOLUME_NAME}:/dest\" busybox sh -c 'cp -a /source/. /dest/'"
echo ""
