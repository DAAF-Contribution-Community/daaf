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
            DAAF_PROJECT_NAME=*|DAAF_PORT_MARIMO=*|DAAF_PORT_LOGVIEWER=*|DAAF_PORT_VSCODE=*|DAAF_DEV=*|DAAF_BRANCH=*)
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
# Symlink manifest: backup-root sibling of .daaf-permissions. On Windows hosts,
# `docker cp` extraction ABORTS the moment it hits a symlink it cannot create
# (symlink creation needs admin/Developer Mode), silently dropping every file that
# sorts after it in the archive stream. To make backups symlink-safe, the volume is
# first STAGED into a throwaway container: the staging step records each symlink's
# path+target into this manifest and then removes the symlinks, so the tree
# `docker cp` streams contains NO symlinks. Restore replays the manifest to
# recreate the links (see restore_from_backup.sh Step 2e). Absent manifest (older
# backup, or a volume with no symlinks) = no-op on restore, matching the
# ".daaf-permissions" "no manifest, no action" rule.
SYMLINKS_MANIFEST=".daaf-symlinks"
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
            "run -d"*)
                # Staging container launch (symlink strip) -- emit a fake CID.
                echo "stagecid0000"
                return 0
                ;;
            "wait"*) echo "0"; return 0 ;;
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
# The staging program contains NO embedded double quotes: it is shared logically
# with the .ps1 twin, where embedded double quotes corrupt Windows arg parsing on
# PS 5.1. Its /tmp writes are inside the throwaway container's own layer (NOT the
# DAAF container's /tmp), so there is no provenance concern.
#
# `docker cp CID:/staging/.` then streams the staged (symlink-free) tree host-side
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
STAGE_PROGRAM='set -e
cp -a /source /staging
cd /staging
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
find /staging -type l -exec rm -f {} +'

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
if ! STAGE_CID="$(docker run -d -v "${VOLUME_NAME}:/source:ro" busybox sh -c "${STAGE_PROGRAM}")"; then
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

echo "Copying files from Docker volume..."
printf "  Progress: 0 / %d files (0%%)" "${TOTAL_FILES}"

docker cp "${STAGE_CID}:/staging/." "${BACKUP_NAME}/" &
COPY_PID=$!
# Extend the interrupt trap to also kill the copy child now that it exists.
trap 'if [ -n "${COPY_PID:-}" ]; then kill "${COPY_PID}" 2>/dev/null; wait "${COPY_PID}" 2>/dev/null; fi; docker rm -f "${STAGE_CID:-}" > /dev/null 2>&1 || true' INT TERM

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

# Remove the staging container. Best-effort: the copy is already done, so a
# failure here must never fail the backup.
docker rm -f "${STAGE_CID}" > /dev/null 2>&1 || true
trap - INT TERM

# Latch for the completion banner: any of the non-fatal WARNING paths below
# (file-count mismatch, size mismatch, Claude-state copy failure, permission-manifest
# failure) sets this so the final banner can say the backup completed WITH WARNINGS
# rather than claiming an unqualified success. The exit status stays 0 on those paths
# -- the banner wording is the signal, not the exit code (the corroborated short-copy
# case below is the one that is fatal, and it exits before the banner).
HAD_WARNINGS=0

# --- Verify ---
# The staged tree the copy streamed = volume regular files + 1 symlink manifest
# - symlinks. Symlinks were never counted by the `find -type f` volume scan
# (TOTAL_FILES), and the manifest is metadata, not volume content -- so exclude the
# manifest here to keep the copied count aligned with TOTAL_FILES. (Do NOT exclude
# it from the completion "files copied" number below either; both must count
# data-volume files only.)
FILE_COUNT=$(find "${BACKUP_NAME}" -type f -not -name "${SYMLINKS_MANIFEST}" 2>/dev/null | wc -l | tr -d '[:space:]') || FILE_COUNT=0
# Print the ACTUAL final host-side count, not a fabricated "100%". On a truncated
# copy (the Windows symlink-abort this staging step now prevents, or any other
# partial copy) an unconditional "100%" would lie about completeness.
if [ "${TOTAL_FILES}" -gt 0 ]; then
    FINAL_PERCENT=$((FILE_COUNT * 100 / TOTAL_FILES))
    if [ "${FINAL_PERCENT}" -gt 100 ]; then FINAL_PERCENT=100; fi
else
    FINAL_PERCENT=0
fi
printf "\r  Progress: %d / %d files (%d%%)   \n" "${FILE_COUNT}" "${TOTAL_FILES}" "${FINAL_PERCENT}"

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

# --- Corroborated short-copy check (fatal) ---
# A nonzero docker cp exit AND a copied count short of the volume scan are two
# independent signals that agree the backup is truncated -- the nonzero exit
# corroborates the shortfall, so no tolerance is applied here (unlike the 1% count
# and size tolerances below, which absorb benign filesystem/metadata drift on an
# otherwise-clean copy). A truncated backup that passed as usable could cost a user
# their data on restore, so fail hard: name the partial folder, tell them to delete
# it, and exit before the completion banner. (A nonzero exit with a FULL count falls
# through to the Note below -- warnings without an actual shortfall.)
if [ "${COPY_EXIT}" -ne 0 ] && [ "${FILE_COUNT}" -lt "${TOTAL_FILES}" ]; then
    echo ""
    echo "ERROR: Backup failed (exit code ${COPY_EXIT}); only ${FILE_COUNT} of ${TOTAL_FILES} expected files were copied."
    echo "       This backup is incomplete and must not be relied on. Delete this"
    echo "       partial backup folder and re-run once the copy issue is resolved."
    echo "Location: $(pwd)/${BACKUP_NAME}/"
    exit 1
elif [ "${COPY_EXIT}" -ne 0 ]; then
    echo "Note: File copy reported warnings (exit code ${COPY_EXIT}); ${FILE_COUNT} of ${TOTAL_FILES} expected files were transferred."
fi

# --- File-count verification ---
# Do NOT trust docker cp's exit code as the sole failure signal: the Windows
# symlink-abort truncation surfaced with a ZERO exit on the user's run. A nonzero
# exit that ALSO comes up short on the count is already fatal (the corroborated
# short-copy branch above). This block catches the harder case -- a clean ZERO exit
# that still copied too few files -- comparing the copied data-file count (manifest
# excluded) against the source scan count and warning loudly on a shortfall beyond a
# 1% tolerance. The count and size checks are the authoritative completeness signals,
# not COPY_EXIT.
if [ "${TOTAL_FILES}" -gt 0 ] && [ "${FILE_COUNT}" -gt 0 ]; then
    COUNT_TOLERANCE=$(( TOTAL_FILES / 100 ))
    if [ "${COUNT_TOLERANCE}" -lt 1 ]; then COUNT_TOLERANCE=1; fi
    COUNT_DIFF=$(( TOTAL_FILES - FILE_COUNT ))
    if [ "${COUNT_DIFF}" -lt 0 ]; then COUNT_DIFF=$(( -COUNT_DIFF )); fi
    if [ "${COUNT_DIFF}" -gt "${COUNT_TOLERANCE}" ]; then
        echo ""
        echo "WARNING: Backup file-count mismatch." >&2
        echo "         Source: ${TOTAL_FILES} files, Backup: ${FILE_COUNT} files (difference: ${COUNT_DIFF})" >&2
        echo "         The backup may be incomplete. Consider re-running." >&2
        HAD_WARNINGS=1
    fi
fi

# --- Size verification ---
# Compare source vs backup logical byte sums to detect truncated files
SOURCE_SIZE_KB="${VOLUME_LOGICAL_KB}"
# Exclude the ".daaf-symlinks" manifest from the backup byte sum: it exists in the
# backup but not the volume, and the source side (VOLUME_LOGICAL_KB) never counted
# it -- so counting it here would skew the comparison (as .daaf-permissions is
# likewise negligible/excluded by not being under -type f in the source scan).
BACKUP_SIZE_KB=$(find "${BACKUP_NAME}" -type f -not -name "${SYMLINKS_MANIFEST}" -exec ls -ln {} + 2>/dev/null | awk '{s+=$5} END {printf "%d\n", s/1024}') || BACKUP_SIZE_KB=0
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
    echo "Backing up Claude Code state (credentials, session history, plugins)..."
    mkdir -p "${BACKUP_NAME}/${CLAUDE_SUBDIR}"
    # Same STAGING mechanism as the data volume above (this volume ALSO carries
    # symlinks -- e.g. codex-daaf/tmp/arg0/... -- which is why the "Failed to back
    # up the Claude Code state volume" warning appeared on Windows: `docker cp`
    # aborted on the first link). Stage into a throwaway container to strip the
    # symlinks into this subfolder's own ".daaf-symlinks" manifest, then cp the
    # symlink-free staged tree out. Synchronous (this copy is small). `docker cp`
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
    if CLAUDE_STAGE_CID="$(docker run -d -v "${CLAUDE_VOLUME_NAME}:/source:ro" busybox sh -c "${STAGE_PROGRAM}")"; then
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
    if [ "${CLAUDE_STAGE_STATUS}" = "0" ] && docker cp "${CLAUDE_STAGE_CID}:/staging/." "${BACKUP_NAME}/${CLAUDE_SUBDIR}/"; then
        # Count data files only -- exclude the symlink manifest (metadata, not
        # volume content), mirroring the data-volume FILE_COUNT exclusion.
        CLAUDE_FILE_COUNT=$(find "${BACKUP_NAME}/${CLAUDE_SUBDIR}" -type f -not -name "${SYMLINKS_MANIFEST}" 2>/dev/null | wc -l | tr -d '[:space:]') || CLAUDE_FILE_COUNT=0
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
PERMISSIONS_MANIFEST=".daaf-permissions"
echo ""
echo "Recording executable-permission manifest..."
if EXEC_PATHS=$(docker run --rm -v "${VOLUME_NAME}:/source:ro" busybox sh -c 'find /source -type f -perm -0100' 2>/dev/null); then
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
