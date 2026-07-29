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
# volume are restored data-only with a warning.
CLAUDE_VOLUME_NAME="${DAAF_PROJECT_NAME:-daaf}_daaf-claude-config"
CLAUDE_SUBDIR=".daaf-claude-config"
# Executable-permission manifest written into the backup root by backup_daaf.sh
# (see the "Capture the executable-permission manifest" block there). Lists every
# regular file that had the owner-exec bit set at backup time. Restore uses it to
# put POSIX modes back after a Windows round-trip erased them. Absent on older
# backups -- restore handles that gracefully (no normalization; see Step 2d).
PERMISSIONS_MANIFEST=".daaf-permissions"
# Symlink manifest written into the backup root (and the Claude subfolder root) by
# backup_daaf.sh's staging step. Lists each symlink's path and target (TAB-
# separated). Restore replays it container-side to recreate the links that the
# staging step stripped so `docker cp` could stream a symlink-free tree on Windows.
# Absent on older backups / volumes with no symlinks -- restore no-ops (see Step 2e),
# matching the ".daaf-permissions" "no manifest, no action" rule.
SYMLINKS_MANIFEST=".daaf-symlinks"

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
    # Count and size the DATA-volume contents only -- exclude the hidden Claude
    # subfolder (it restores to its own volume, not the data volume) and BOTH
    # metadata manifests (".daaf-permissions", ".daaf-symlinks" -- neither is
    # restored content). This makes the listing count agree exactly with the
    # "Scanning backup" count below, the post-restore verification count, and the
    # backup script's completion report (all four count data-volume files only).
    # When Claude state is present it is noted inline rather than folded silently
    # into the number.
    claude_sub="${dir}/${CLAUDE_SUBDIR}"
    count=$(find "${dir}" -type f -not -path "${claude_sub}/*" -not -name "${PERMISSIONS_MANIFEST}" -not -name "${SYMLINKS_MANIFEST}" 2>/dev/null | wc -l | tr -d '[:space:]') || count="?"
    # BSD du has no --exclude, so total the data-volume KB by subtracting the Claude
    # subfolder's KB AND both metadata manifests' KB from the whole-folder KB, then
    # humanize with awk. Subtracting the manifests (not just the Claude subfolder)
    # keeps this size aligned with the .ps1 twin's Measure-Object, which excludes both
    # ".daaf-permissions" and ".daaf-symlinks". Mirrors the "Scanning backup" logic below.
    total_kb=$(du -sk "${dir}" 2>/dev/null | awk '{print $1}')
    total_kb=${total_kb:-0}
    for mf in "${dir}/${PERMISSIONS_MANIFEST}" "${dir}/${SYMLINKS_MANIFEST}"; do
        if [ -f "${mf}" ]; then
            mf_kb=$(du -sk "${mf}" 2>/dev/null | awk '{print $1}')
            total_kb=$(( total_kb - ${mf_kb:-0} ))
        fi
    done
    has_claude=0
    if [ -d "${claude_sub}" ] && [ -n "$(ls -A "${claude_sub}" 2>/dev/null)" ]; then
        has_claude=1
        claude_kb=$(du -sk "${claude_sub}" 2>/dev/null | awk '{print $1}')
        total_kb=$(( total_kb - ${claude_kb:-0} ))
    fi
    size=$(awk -v kb="${total_kb}" 'BEGIN { if (kb >= 1048576) printf "%.1fG", kb/1048576; else if (kb >= 1024) printf "%.1fM", kb/1024; else printf "%dK", kb }') || size="?"
    if [ "${has_claude}" -eq 1 ]; then
        printf "  %d) %s  (%s files + Claude state, %s)\n" "$((i + 1))" "${name}" "${count}" "${size}"
    else
        printf "  %d) %s  (%s files, %s)\n" "$((i + 1))" "${name}" "${count}" "${size}"
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
# separate volume below, not into the data volume. Also exclude BOTH metadata
# manifests: ".daaf-permissions" (consumed by Step 2d, then removed) and
# ".daaf-symlinks" (consumed by Step 2e, then removed). Neither is restored content,
# so counting them would make this scan disagree with the post-restore verification
# count (which runs after both manifests are stripped from the volume) and with the
# listing count above.
echo ""
echo "Scanning backup..."
TOTAL_FILES=$(find "${SELECTED_PATH}" -type f -not -path "${CLAUDE_BACKUP_PATH}/*" -not -name "${PERMISSIONS_MANIFEST}" -not -name "${SYMLINKS_MANIFEST}" | wc -l | tr -d '[:space:]')
# Size must match the file count above: data-volume contents only, excluding the
# Claude subfolder (which restores to its own volume) AND both metadata manifests.
# BSD du has no --exclude, so subtract the subfolder's KB and each manifest's KB from
# the total and humanize with awk. Subtracting the manifests keeps this aligned with
# the .ps1 twin's Measure-Object (which excludes both) and with the file count above.
TOTAL_KB=$(du -sk "${SELECTED_PATH}" 2>/dev/null | awk '{print $1}')
TOTAL_KB=${TOTAL_KB:-0}
for mf in "${SELECTED_PATH}/${PERMISSIONS_MANIFEST}" "${SELECTED_PATH}/${SYMLINKS_MANIFEST}"; do
    if [ -f "${mf}" ]; then
        MF_KB=$(du -sk "${mf}" 2>/dev/null | awk '{print $1}')
        TOTAL_KB=$(( TOTAL_KB - ${MF_KB:-0} ))
    fi
done
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

# Copy the backup into the data volume via `docker create` + `docker cp` instead
# of a bind-mounted `busybox cp -a`. On Docker Desktop for Windows, a bind-mounted
# copy reads every host file across the 9p/gRPC-FUSE host<->VM boundary
# individually, so a large restore takes minutes; `docker cp` streams the whole
# tree to the daemon in one pass and extracts it inside the VM, avoiding that
# per-file overhead. The helper container is created but never started -- `docker
# cp` still writes into the volume because the daemon mounts the container root AND
# its volume MountPoints into the archive view regardless of container state. The
# trailing "/." on the source copies the backup's CONTENTS into /dest rather than
# nesting a folder.
#
# Two asymmetries vs the backup script's copy-OUT:
#   1. Ownership: `docker cp` INTO a container writes files as ROOT (not the
#      volume's appuser, UID 1000), so a container-side chown repair is REQUIRED
#      below -- see Step 2c. (Copy-OUT needs no repair because `docker cp` extracts
#      container->host as the invoking user.)
#   2. Exclusion: `docker cp` has no exclude flag, so it copies the whole backup
#      folder INCLUDING the hidden ".daaf-claude-config/" subfolder. That subfolder
#      belongs in the separate Claude volume (restored below), not the data volume,
#      so it is stripped container-side in Step 2b -- matching the old
#      `cp -a ... && rm -rf "/dest/${CLAUDE_SUBDIR}"` outcome exactly.
CID=""
trap 'docker rm -f "${CID:-}" > /dev/null 2>&1 || true' INT TERM
# Guard the create explicitly: under `set -e`, an unguarded `CID="$(docker
# create ...)"` would abort the whole script with NO message -- and the volume
# was already cleared in Step 1, so the user would be left with an empty volume
# and no explanation. Capture into CID first, then check the status.
if ! CID="$(docker create -v "${VOLUME_NAME}:/dest" busybox)"; then
    # Best-effort reap: `docker create` can in principle fail AFTER creating the
    # container while still printing its CID to stdout, which the command
    # substitution above captured -- remove it so a launch failure does not leak a
    # helper container (mirrors backup_daaf.sh's stage-start reap and
    # backup_daaf.ps1's stage-start cleanup). `docker create` is single-phase, so a
    # fail-with-CID is near-theoretical here, but this keeps parity with the twin and
    # with the `docker cp` failure branch just below. The `${CID:-}` guard makes this
    # a harmless no-op if no CID was captured. Reap first, then drop the trap (matches
    # the cp-branch order).
    docker rm -f "${CID:-}" > /dev/null 2>&1 || true
    trap - INT TERM
    echo "" >&2
    echo "ERROR: Could not create the helper container for the volume copy." >&2
    echo "The Docker volume has already been cleared and is now EMPTY." >&2
    echo "Re-run this restore, or reinstall DAAF, to repopulate it." >&2
    exit 1
fi

if ! docker cp "${SELECTED_PATH}/." "${CID}:/dest/"; then
    docker rm -f "${CID}" > /dev/null 2>&1 || true
    trap - INT TERM
    echo "" >&2
    echo "ERROR: File copy failed." >&2
    echo "The Docker volume may be in an inconsistent state." >&2
    echo "You may want to re-run this restore or reinstall DAAF." >&2
    exit 1
fi

# Remove the helper container -- the copy is done. Best-effort; a failure here
# must not fail the restore. Subsequent container-side steps use `docker run --rm`.
docker rm -f "${CID}" > /dev/null 2>&1 || true
trap - INT TERM

# --- Step 2b: Strip the Claude subfolder from the DATA volume ---
# `docker cp` above copied the whole backup, including "${CLAUDE_SUBDIR}/". Remove
# it from the data volume container-side (fast: runs inside the VM, no bind mount)
# so the data volume matches the old copy's outcome. It is restored to its own
# volume below when present.
if ! docker run --rm -v "${VOLUME_NAME}:/dest" busybox rm -rf "/dest/${CLAUDE_SUBDIR}"; then
    echo "" >&2
    echo "ERROR: Failed to remove the ${CLAUDE_SUBDIR} subfolder from the data volume." >&2
    echo "WARNING: The restore copied the whole backup into the data volume, so Claude" >&2
    echo "         Code credentials and session data may REMAIN inside the data volume" >&2
    echo "         until this is resolved. Re-run this restore to clear them." >&2
    exit 1
fi

# --- Step 2c: Repair ownership on the data volume ---
# `docker cp` wrote the files as root; the volume must be owned by appuser (UID
# 1000) so the container can read/write it. Chown container-side (runs inside the
# VM -- no bind mount, so it is fast). The literal 1000:1000 mirrors the
# daaf-init service in docker-compose.yml, which chowns both volumes to 1000:1000
# on every startup; that init container is a second net, but restore must not
# depend on it having run.
if ! docker run --rm -v "${VOLUME_NAME}:/dest" busybox chown -R 1000:1000 /dest; then
    echo "" >&2
    echo "ERROR: Failed to repair ownership on the data volume." >&2
    echo "The files were restored intact, but the DAAF container may not be able to" >&2
    echo "read them. Re-run this restore, or restart DAAF -- the compose init service" >&2
    echo "also repairs volume ownership on startup." >&2
    exit 1
fi

# --- Step 2d: Replay executable permissions from the manifest ---
# The manifest ("${PERMISSIONS_MANIFEST}") was copied into the data volume by the
# whole-folder `docker cp` above. When it is PRESENT, restore normalizes every
# regular file to 0644 and then re-applies 0755 to exactly the paths it lists --
# undoing the mode loss a Windows (NTFS) round-trip inflicts, where `docker cp`
# fabricates 0755 for every file and git then flags every tracked 0644 file as a
# spurious 100644->100755 change.
#
# SAFETY RULE -- no manifest, no normalization: when the manifest is ABSENT (older
# backups predating this feature, OR a manifest whose write failed at backup time),
# do NOTHING. A blanket 0644 without the manifest would strip exec from every
# script and hook and make matters worse than leaving the fabricated 0755 in place.
# The manifest's presence is the signal that "these are the files that SHOULD be
# executable, and everything else should be 0644"; without it there is no safe
# baseline to normalize toward.
#
# Everything below runs container-side (inside the VM, no bind mount) so it is
# fast and immune to host-filesystem quirks:
#   - normalize:  `find -type f -exec chmod 644 {} +` -- only regular files, so
#                 directories keep 0755 (chown/normalize never touch dir modes).
#   - re-apply:   read the manifest with `while IFS= read -r`, strip a trailing CR
#                 (WriteAllLines on Windows emits CRLF) and a leading UTF-8 BOM (both
#                 as parameter-expansion prefixes/suffixes, not sed -- busybox sed has
#                 no \xNN escapes) defensively, skip blanks, chmod 0755 each path.
#   - cleanup:    remove the manifest from the volume (it is metadata, not content),
#                 mirroring the Step 2b ".daaf-claude-config" strip.
# Replay failure is a WARNING (data is intact; only permissions may be off), never
# a fatal error -- consistent with how the Claude restore below degrades.
if docker run --rm -v "${VOLUME_NAME}:/dest:ro" busybox test -f "/dest/${PERMISSIONS_MANIFEST}"; then
    echo "Restoring executable permissions from ${PERMISSIONS_MANIFEST}..."
    # The whole replay is one container-side sh script so the manifest read and the
    # chmods share a single busybox invocation. The manifest path is interpolated
    # from the (fixed, non-user) constant, so no injection surface. Trailing CR is
    # stripped with parameter expansion (busybox ash supports "${p%$cr}"); a leading
    # UTF-8 BOM on the first line is stripped the same way, as a prefix, in the loop.
    if ! docker run --rm -v "${VOLUME_NAME}:/dest" busybox sh -c '
        set -e
        manifest="/dest/'"${PERMISSIONS_MANIFEST}"'"
        # Normalize every regular file to 644 (directories are untouched: -type f).
        find /dest -type f -exec chmod 644 {} +
        # Re-apply 755 to each manifest path. Read line by line, tolerating spaces in
        # paths and stripping any trailing CR (WriteAllLines emits CRLF on Windows).
        # Also strip a leading UTF-8 BOM (bytes EF BB BF) if present on a line: busybox
        # sed does NOT understand \xNN hex escapes (it would match them literally), so
        # the BOM is derived once via octal printf (portable) and removed as a prefix
        # with "${p#$bom}" -- never with `tr -d`, which would also delete those three
        # bytes where they legitimately occur inside multi-byte UTF-8 filenames.
        cr=$(printf "\r")
        bom=$(printf "\357\273\277")
        while IFS= read -r p; do
            p="${p%$cr}"
            p="${p#$bom}"
            [ -z "$p" ] && continue
            # A false `[ -e ... ]` here does NOT trip `set -e`: a command that is part
            # of an AND-OR list (anything but the last) is exempt from errexit per
            # POSIX, so a manifest path missing from this backup is simply skipped
            # rather than aborting the whole replay. Do not "simplify" this into an
            # `if`-less bare chmod.
            [ -e "/dest/$p" ] && chmod 755 "/dest/$p"
        done < "$manifest"
        # Remove the manifest from the volume -- metadata, not restored content
        # (mirrors the Step 2b .daaf-claude-config strip).
        rm -f "$manifest"
    '; then
        echo "WARNING: Could not fully replay executable permissions." >&2
        echo "         Your data was restored intact; only file permissions may be off." >&2
        echo "         If git reports many files as changed by mode only, or a script" >&2
        echo "         will not run, repair with: chmod +x <file> inside the container." >&2
    fi
else
    echo "NOTE: No ${PERMISSIONS_MANIFEST} manifest found in this backup (it may predate"
    echo "      permission preservation, or the manifest write may have failed during"
    echo "      backup). File permissions were left as-is -- no normalization was applied."
fi

# --- Step 2e: Replay symlinks from the manifest ---
# The symlink manifest ("${SYMLINKS_MANIFEST}") was copied into the data volume by
# the whole-folder `docker cp` above. backup_daaf.sh's staging step stripped every
# symlink from the tree (so `docker cp` could stream a symlink-free archive that
# does not abort on Windows) and recorded each link's path + target here, TAB-
# separated. When the manifest is PRESENT, recreate each link, chown it to appuser
# (-h: the link itself, not its target), then remove the manifest from the volume.
#
# SAFETY / no manifest, no action: when the manifest is ABSENT (older backups, a
# volume with no symlinks, or a manifest whose write failed at backup time), do
# NOTHING -- matching the ".daaf-permissions" rule. Replay failure is a WARNING
# (the regular files are intact; such links are typically regenerable), never fatal.
#
# Windows quoting: this `sh -c` program reaches docker.exe as one command-line
# string, so it must contain NO embedded double-quotes (the Windows C runtime would
# re-parse and mangle them -- see shell-scripting gotchas.md). Unquoted expansions
# are exact because of `set -f` (no globbing) + an empty global IFS (no word
# splitting on expansion); the `IFS=$tab` prefix scopes field splitting to the
# `read` alone. A trailing CR and a leading UTF-8 BOM are stripped as parameter-
# expansion suffix/prefix (never `tr -d`, which would corrupt multi-byte UTF-8
# filenames); the BOM bytes are derived via octal printf (busybox sed has no \xNN).
if docker run --rm -v "${VOLUME_NAME}:/dest:ro" busybox test -f "/dest/${SYMLINKS_MANIFEST}"; then
    echo "Restoring symlinks from ${SYMLINKS_MANIFEST}..."
    if ! docker run --rm -v "${VOLUME_NAME}:/dest" busybox sh -c '
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
        echo "         Your data was restored intact; only symbolic links may be missing." >&2
        echo "         Such links are usually regenerable (e.g. by re-running the step that" >&2
        echo "         created them). Inspect ${SYMLINKS_MANIFEST} in the backup for the list." >&2
    fi
else
    # No symlink manifest: older backup, or a volume that had no symlinks. Silent
    # no-op (there is nothing to recreate) -- mirrors the ".daaf-permissions" rule.
    :
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
    # Clear then copy, mirroring the data-volume restore semantics. The copy uses
    # the same `docker create` + `docker cp` mechanism (with the same root->1000
    # ownership repair) as the data volume above; the claude-config volume is also
    # chowned to 1000:1000 by daaf-init in docker-compose.yml, but restore repairs
    # it here rather than depending on that init container.
    CLAUDE_CID=""
    if ! docker run --rm -v "${CLAUDE_VOLUME_NAME}:/dest" busybox sh -c 'rm -rf /dest/* /dest/.[!.]* /dest/..?*'; then
        echo "WARNING: Failed to clear the Claude Code state volume before restore." >&2
        echo "         Data volume restore above succeeded; Claude state may be inconsistent." >&2
    else
        # Best-effort helper-container cleanup on interrupt, guarded under set -u.
        trap 'docker rm -f "${CLAUDE_CID:-}" > /dev/null 2>&1 || true' INT TERM
        # Guard the create under `set -e`: a failure here is non-fatal (the data
        # volume restore already succeeded), so it must fall into the WARNING path
        # below, not abort the whole script. Capture the launch outcome in a SEPARATE
        # flag rather than blanking the CID: `docker create` can in principle fail
        # after emitting a CID, and the old `|| CLAUDE_CID=""` discarded that CID
        # before the trap above or the `docker rm -f` at the end of this block could
        # reap it -- leaking the helper container. Keep the captured CID intact so both
        # reap sites can remove it (mirrors backup_daaf.sh's CLAUDE_STAGE_START_OK flag
        # and backup_daaf.ps1's $claudeStageStartOk + finally-reap pattern). Assigning
        # inside the `if` condition keeps `set -e` from aborting on a launch failure
        # while still capturing whatever the substitution produced.
        if CLAUDE_CID="$(docker create -v "${CLAUDE_VOLUME_NAME}:/dest" busybox)"; then
            CLAUDE_CREATE_OK=1
        else
            CLAUDE_CREATE_OK=0
        fi
        if [ "${CLAUDE_CREATE_OK}" -eq 1 ] \
            && docker cp "${CLAUDE_BACKUP_PATH}/." "${CLAUDE_CID}:/dest/" \
            && docker run --rm -v "${CLAUDE_VOLUME_NAME}:/dest" busybox chown -R 1000:1000 /dest; then
            # Replay the Claude volume's own symlink manifest (staged out by backup),
            # then strip it. Same program + no-manifest-no-op + WARNING-not-fatal
            # semantics as the data-volume Step 2e. The manifest lives at the Claude
            # subfolder root, so it copied into this volume's root as /dest/.daaf-symlinks.
            if docker run --rm -v "${CLAUDE_VOLUME_NAME}:/dest:ro" busybox test -f "/dest/${SYMLINKS_MANIFEST}"; then
                if ! docker run --rm -v "${CLAUDE_VOLUME_NAME}:/dest" busybox sh -c '
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
                    echo "         Claude state was restored; only symbolic links may be missing." >&2
                fi
            fi
            echo "Claude Code state restored."
        else
            echo "WARNING: Failed to restore the Claude Code state volume." >&2
            echo "         Data volume restore above succeeded; you may need to re-run /login." >&2
        fi
        # Best-effort: a spurious rm failure must never abort AFTER a successful
        # restore. `|| true` keeps `set -e` from tripping here.
        docker rm -f "${CLAUDE_CID}" > /dev/null 2>&1 || true
        trap - INT TERM
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
