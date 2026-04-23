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
# ============================================================================

set -euo pipefail

# Pause before exit so the user can review output (skip when called from another script)
if [ -z "${DAAF_NESTED:-}" ]; then
    trap 'echo ""; read -r -p "Press Enter to continue: "' EXIT
fi

# --- Configuration ---
VOLUME_NAME="daaf_daaf-data"
TODAY=$(date +%Y-%m-%d)

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
SCAN_OUTPUT=$(docker run --rm -v "${VOLUME_NAME}:/source:ro" busybox sh -c "find /source -type f | wc -l && du -sh /source")
TOTAL_FILES=$(echo "${SCAN_OUTPUT}" | head -1 | tr -d '[:space:]')
TOTAL_SIZE=$(echo "${SCAN_OUTPUT}" | tail -1 | awk '{print $1}')
echo "Found ${TOTAL_FILES} files to copy (${TOTAL_SIZE})."
echo ""

# --- Create backup ---
mkdir -p "${BACKUP_NAME}"
echo "Copying files from Docker volume..."
printf "  Progress: 0 / %d files (0%%)" "${TOTAL_FILES}"

docker run --rm \
    -v "${VOLUME_NAME}:/source:ro" \
    -v "$(pwd)/${BACKUP_NAME}:/dest" \
    busybox sh -c "cp -a /source/. /dest/" &
COPY_PID=$!

while kill -0 "${COPY_PID}" 2>/dev/null; do
    sleep 3
    if ! kill -0 "${COPY_PID}" 2>/dev/null; then
        break
    fi
    COPIED=$(find "${BACKUP_NAME}" -type f 2>/dev/null | wc -l | tr -d '[:space:]') || COPIED=0
    if [ "${TOTAL_FILES}" -gt 0 ]; then
        PERCENT=$((COPIED * 100 / TOTAL_FILES))
    else
        PERCENT=0
    fi
    printf "\r  Progress: %d / %d files (%d%%)   " "${COPIED}" "${TOTAL_FILES}" "${PERCENT}"
done

if ! wait "${COPY_PID}"; then
    echo ""
    echo ""
    echo "ERROR: Backup failed. Check Docker Desktop for errors."
    exit 1
fi
printf "\r  Progress: %d / %d files (100%%)   \n" "${TOTAL_FILES}" "${TOTAL_FILES}"

# --- Verify ---
FILE_COUNT=$(find "${BACKUP_NAME}" -type f 2>/dev/null | wc -l | tr -d '[:space:]') || FILE_COUNT=0

if [ "${FILE_COUNT}" -eq 0 ]; then
    echo ""
    echo "WARNING: Backup completed but 0 files were copied."
    echo "The Docker volume may be empty. Is DAAF properly installed?"
    echo "Location: $(pwd)/${BACKUP_NAME}/"
    exit 1
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
