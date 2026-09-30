#!/usr/bin/env bats
# ============================================================================
# Tests for restore_from_backup.sh -- DAAF Restore from Backup
# ============================================================================
# Key testable logic: backup discovery, preflight checks, running container
# detection, destructive warning, volume clearing, and verification.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
}

# Re-open any chmod-000 fixture folder (the read-error tests below) before the shared
# teardown's `rm -rf`, which cannot descend into an unreadable folder -- this runs on
# pass AND on failure, so no fixture outlives its test (backup_twin_parity.bats pattern).
teardown() {
    chmod -R u+rwx "${TEST_DIR}" 2>/dev/null || true
    common_teardown
}

# --- Syntax ---

@test "restore_from_backup.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "restore: fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "restore: fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: volume not found ---

@test "restore: fails when Docker volume does not exist" {
    MOCK_DOCKER_VOLUME_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- No backups found ---

@test "restore: fails when no backup folders exist" {
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "No backup folders found"
}

@test "restore: suggests daaf-docker folder when no backups found" {
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "daaf-docker"
}

# --- Backup discovery ---

@test "restore: discovers backup folders matching date pattern" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/file1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    # Pipe empty input so read fails and script exits
    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # Should list the backup even if selection fails
    assert_output --partial "${today}_daaf_backup"
}

@test "restore: discovers multiple backups with suffixes" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    mkdir -p "${TEST_DIR}/${today}a_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/f1"
    touch "${TEST_DIR}/${today}a_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "${today}_daaf_backup"
    assert_output --partial "${today}a_daaf_backup"
}

@test "restore: listing excludes Claude subfolder and manifest, annotates Claude state" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    # Two data files, a manifest, and a non-empty Claude subfolder.
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    touch "${TEST_DIR}/${today}_daaf_backup/data2"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    mkdir -p "${TEST_DIR}/${today}_daaf_backup/.daaf-claude-config"
    touch "${TEST_DIR}/${today}_daaf_backup/.daaf-claude-config/creds"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # Count must be the 2 data files only (not the manifest, not the Claude file).
    assert_output --partial "(2 files + Claude state,"
}

@test "restore: listing shows plain count when no Claude state present" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # 1 data file, no Claude annotation, manifest excluded from the count.
    assert_output --partial "(1 files,"
    refute_output --partial "Claude state"
}

@test "restore: ignores directories not matching backup pattern" {
    mkdir -p "${TEST_DIR}/2026-04-21_daaf_backup"
    mkdir -p "${TEST_DIR}/random_folder"
    mkdir -p "${TEST_DIR}/not_a_backup"
    touch "${TEST_DIR}/2026-04-21_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "2026-04-21_daaf_backup"
    refute_output --partial "random_folder"
    refute_output --partial "not_a_backup"
}

# --- DAAF_NESTED behavior ---

@test "restore: suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    refute_output --partial "Press Enter"
}

# --- Banner ---

@test "restore: displays the DAAF Restore banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output --partial "DAAF Restore from Backup"
}

# --- Structural: safety features present ---

@test "restore: contains destructive warning text" {
    run grep -c "DESTRUCTIVE OPERATION" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: requires RESTORE confirmation" {
    run grep -c "Type RESTORE to confirm" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: clears volume before copying" {
    run grep -c "rm -rf /dest" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: uses docker cp (not bind-mounted cp -a)" {
    # The copy mechanism is `docker create` + `docker cp` -- it must invoke a
    # quoted `docker cp "` (one for the data volume, one for the Claude state
    # volume) and must NOT use the old bind-mounted `cp -a /source` busybox copy.
    run grep -c 'docker create' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'docker cp "' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c "cp -a /source" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
}

@test "restore: repairs volume ownership after docker cp writes as root" {
    # `docker cp` INTO a container writes files as root; the restore must chown the
    # volume back to appuser (UID 1000) container-side, matching daaf-init.
    run grep -c "chown -R 1000:1000 /dest" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: replays executable permissions from the manifest" {
    # Step 2d: when ".daaf-permissions" is present, normalize files to 644 and
    # re-apply 755 to the manifest's paths (undoing NTFS mode loss).
    run grep -c '\.daaf-permissions' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'find /dest -type f -exec chmod 644' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'chmod 755' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: skips normalization when the manifest is absent (backward compat)" {
    # No manifest => no normalization (blanket 644 would strip exec from every
    # script and be worse than the fabricated 0755). The absent-manifest NOTE must
    # cover BOTH causes: an older backup, or a manifest whose write failed at backup
    # time (Fix 3) -- so it reads "may predate permission preservation".
    run grep -c 'it may predate' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'the manifest write may have failed during' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'no normalization was applied' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: replays symlinks from the manifest (Step 2e)" {
    # Step 2e: when ".daaf-symlinks" is present, recreate each link (path TAB target)
    # container-side and chown -h it, then strip the manifest from the volume.
    run grep -c '\.daaf-symlinks' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'ln -sf -- ' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'chown -h 1000:1000' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: replays symlinks for BOTH the data volume AND the Claude volume" {
    # Regression guard for the review BLOCKER (which surfaced first in the .ps1 twin):
    # a draft that recreates symlinks only for the DATA volume and silently omits the
    # Claude-state volume still PASSES a file-wide grep for ".daaf-symlinks" or
    # "ln -sf --", because the string is present at least once. Assert the replay
    # idiom (`ln -sf --`) appears exactly TWICE -- once in the data-volume Step 2e
    # block and once in the Claude-state restore block -- and that a replay is
    # actually nested inside the CLAUDE_VOLUME_NAME restore path, not only the data one.
    run bash -c "grep -c 'ln -sf -- ' \"${REPO_ROOT}/scripts/host/restore_from_backup.sh\""
    assert_success
    assert_output "2"
    # The Claude-volume replay must live below the "Restore the Claude Code state
    # volume" header and bind CLAUDE_VOLUME_NAME:/dest. Slice the file from that header
    # to EOF and confirm both a CLAUDE_VOLUME_NAME-bound `docker run ... sh -c` and an
    # `ln -sf --` inside that region -- proving the replay is wired for the second
    # volume, not just referenced globally.
    run bash -c "awk '/Restore the Claude Code state volume/{f=1} f' \"${REPO_ROOT}/scripts/host/restore_from_backup.sh\" | grep -c 'CLAUDE_VOLUME_NAME}:/dest'"
    assert_success
    run bash -c "awk '/Restore the Claude Code state volume/{f=1} f' \"${REPO_ROOT}/scripts/host/restore_from_backup.sh\" | grep -c 'ln -sf -- '"
    assert_success
    assert_output "1"
}

@test "restore: symlink replay program is quote-free (Windows arg safety)" {
    # The Step 2e sh -c replay program is shared logically with the .ps1 twin; an
    # embedded double quote would corrupt Windows PS 5.1 arg parsing. It uses octal
    # printf for the BOM (busybox sed has no \\xNN escapes), never tr -d.
    run grep -c 'bom=$(printf' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    run grep -c 'IFS=$tab read -r p t' "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: excludes .daaf-symlinks from listing and scan counts" {
    # A backup with 1 data file, both manifests, and no Claude state must list and
    # scan as "1 files" (neither manifest counted).
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    printf 'sub/link\ttarget\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-symlinks"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "(1 files,"
    refute_output --partial "(2 files"
    refute_output --partial "(3 files"
}

@test "restore: listing and scan exclude only ROOT manifests (a nested same-name data file counts)" {
    # Root-relative exclusions, the rule every count site shares: a data file named
    # .daaf-symlinks or .daaf-permissions deeper in the tree is restored content, so
    # the listing must show 3 files here, not 1 (the old name-anywhere `-not -name`
    # form dropped both nested files).
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup/sub"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    touch "${TEST_DIR}/${today}_daaf_backup/sub/.daaf-symlinks"
    touch "${TEST_DIR}/${today}_daaf_backup/sub/.daaf-permissions"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    : > "${TEST_DIR}/${today}_daaf_backup/.daaf-symlinks"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    # Select backup 1, then cancel at the RESTORE prompt: the scan count is printed
    # before the prompt, so both counts are observable without restoring.
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "(3 files,"
    assert_output --partial "Found 3 files"
    assert_output --partial "Restore cancelled."
}

@test "restore: listing and scan count a file whose NAME holds a newline once (NUL count, like the backup)" {
    # Review round 2 (F5g): the listing and scan counted lines (`wc -l`), while the
    # backup's completion report counts NULs, so a newline name made them disagree.
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup/sub"
    touch "${TEST_DIR}/${today}_daaf_backup/data1"
    touch "${TEST_DIR}/${today}_daaf_backup/sub/name"$'\n'"with-newline"
    : > "${TEST_DIR}/${today}_daaf_backup/.daaf-symlinks"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "(2 files,"
    assert_output --partial "Found 2 files"
    refute_output --partial "(3 files,"
    assert_output --partial "Restore cancelled."
    # Every host-side NUL count runs tr in the C locale (macOS multibyte tr).
    run grep -c -- "-print0.*| LC_ALL=C tr -dc '\\\\000' | wc -c" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_output "1"
}

@test "restore: replays symlinks when the backup contains a symlink manifest" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    printf 'sub/link\t../target\n' > "${TEST_DIR}/2026-01-01_daaf_backup/.daaf-symlinks"

    export DAAF_NESTED=1

    # Step 2e probes the volume with `docker run ... test -f /dest/.daaf-symlinks`.
    # Model the symlink manifest as PRESENT; the permissions manifest as ABSENT.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"test -f"* ]] && [[ "${args_str}" == *".daaf-permissions"* ]]; then
                    return 1  # permissions manifest absent
                elif [[ "${args_str}" == *"find /dest"* ]] && [[ "${args_str}" == *"wc -l"* ]]; then
                    echo "RESTORED_FILES=1"; return 0
                fi
                # symlink test -f (present), replay sh -c, clear, strip, chown: OK.
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "Restoring symlinks"
}

@test "restore: no-ops symlink replay when the manifest is absent" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    # No .daaf-symlinks manifest in this backup.

    export DAAF_NESTED=1

    # Both manifests probe ABSENT (test -f => 1); verification returns a count.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"test -f"* ]]; then
                    return 1  # both manifests absent
                elif [[ "${args_str}" == *"find /dest"* ]] && [[ "${args_str}" == *"wc -l"* ]]; then
                    echo "RESTORED_FILES=1"; return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # No symlink manifest => the "Restoring symlinks" line must NOT appear, and the
    # restore still completes. The two informational NOTEs this older-style backup
    # triggers (no permission manifest, no Claude state) do NOT latch the warnings
    # banner: the plain banner, never "WITH WARNINGS" (partial match on "complete!"
    # so "Restore completed WITH WARNINGS" cannot satisfy it).
    assert_success
    refute_output --partial "Restoring symlinks"
    assert_output --partial "NOTE: No .daaf-permissions manifest found"
    assert_output --partial "NOTE: This backup does not contain Claude Code state"
    assert_output --partial "Restore complete!"
    refute_output --partial "WITH WARNINGS"
    # The mock prints the RESTORED_FILES marker, so this is the VERIFIED happy path,
    # not the "could not verify" fallback a bare number used to drift into.
    assert_output --partial "Verified: 1 files in restored volume."
    assert_output --partial "Files:    1 files in volume"
    refute_output --partial "Could not verify the restored file count"
}

@test "restore: checks for running containers before restoring" {
    run grep -c "docker ps --filter" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: verifies file count after restore" {
    run grep -c "Verifying restore" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: includes file count mismatch check" {
    run grep -c "File count mismatch" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

# --- Invalid selection ---

@test "restore: rejects non-numeric selection" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "abc" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "Invalid selection"
}

@test "restore: rejects out-of-range selection" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'echo "99" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "Invalid selection"
}

# --- Cancellation ---

@test "restore: cancels when user does not type RESTORE" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "Restore cancelled"
}

# --- Running container detection ---

@test "restore: offers to stop running containers" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    # Override docker to return a container name for ps --filter
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)
                echo "daaf-daaf-docker-1"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    # Decline the stop prompt
    run bash -c 'echo "n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "container is currently running"
    assert_output --partial "Restore cancelled"
}

@test "restore: warns about Claude Code sessions when containers running" {
    run grep -c "Claude Code sessions" "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "restore: dry-run completes successfully with backups present" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
}

@test "restore: dry-run produces DRY-RUN markers" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

@test "restore: dry-run shows backup count" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${TEST_DIR}/2026-01-02_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    touch "${TEST_DIR}/2026-01-02_daaf_backup/f1"

    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh" 2>&1
    assert_success
    assert_output --partial "2 backup(s)"
}

@test "restore: dry-run succeeds when no backups exist" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_success
    assert_output --partial "No backup folders found"
}

# =========================================================================
# --- Error paths ---
# =========================================================================

@test "restore: running container detected offers to stop" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)
                echo "daaf-daaf-docker-1"
                return 0
                ;;
            compose)
                shift
                case "$1" in
                    down) return 0 ;;
                    *)    return 0 ;;
                esac
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    # User answers 'y' to stop, then the script continues looking for backups
    # No backups exist so it exits with failure
    run bash -c 'echo "y" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"' 2>&1
    assert_output --partial "container is currently running"
    assert_output --partial "must be stopped before restoring"
    assert_output --partial "Stopping containers"
}

@test "restore: user declines to stop container exits cleanly" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)
                echo "daaf-daaf-docker-1"
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'echo "n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restore cancelled"
}

@test "restore: volume clear fails exits with error" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    export DAAF_NESTED=1

    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"rm -rf"* ]]; then
                    # Volume clear fails
                    return 1
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    # Select backup 1, confirm with RESTORE
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to clear"
}

@test "restore: zero files after restore exits with error" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    export DAAF_NESTED=1

    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                # The copy path is now `docker create` + `docker cp` (arms above);
                # the volume-clear, Claude-subfolder strip, and ownership repair are
                # `docker run --rm ... rm -rf` / `chown`; verification is
                # `docker run --rm ... find /dest`.
                if [[ "${args_str}" == *"rm -rf"* ]]; then
                    return 0
                elif [[ "${args_str}" == *"chown"* ]]; then
                    return 0
                elif [[ "${args_str}" == *"find /dest"* ]]; then
                    # Verification: 0 files restored
                    echo "RESTORED_FILES=0"
                    return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "0 files found"
}

@test "restore: file count mismatch after restore shows warning" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    # Create enough files to make mismatch significant (beyond 1% tolerance)
    for i in $(seq 1 50); do
        touch "${TEST_DIR}/2026-01-01_daaf_backup/f${i}"
    done

    export DAAF_NESTED=1

    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                # Copy path is `docker create` + `docker cp` (arms above); clear,
                # subfolder strip, and chown are `docker run --rm`; verification is
                # `docker run --rm ... find /dest`.
                if [[ "${args_str}" == *"rm -rf"* ]]; then
                    return 0
                elif [[ "${args_str}" == *"chown"* ]]; then
                    return 0
                elif [[ "${args_str}" == *"find /dest"* ]]; then
                    # Return much lower count than actual (50 files, report 10)
                    echo "RESTORED_FILES=10"
                    return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # A mismatch is a WARNING, not fatal: exit 0, and the banner is latched.
    assert_success
    assert_output --partial "WARNING"
    assert_output --partial "File count mismatch"
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Restore complete!"
}

@test "restore: subfolder-strip failure exits with hygiene warning" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    export DAAF_NESTED=1

    # The data copy (create/cp) succeeds; the Step 2b strip of the
    # ".daaf-claude-config" subfolder fails. Both the Step 1 volume-clear and the
    # Step 2b strip are `docker run ... rm -rf`, so the mock distinguishes them by
    # the ".daaf-claude-config" substring: the clear (no substring) succeeds, the
    # strip (contains the substring) returns 1.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *".daaf-claude-config"* ]]; then
                    # Step 2b strip fails.
                    return 1
                elif [[ "${args_str}" == *"rm -rf"* ]]; then
                    # Step 1 volume-clear succeeds.
                    return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "may REMAIN inside the data volume"
}

@test "restore: ownership-repair (chown) failure exits with ownership warning" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    export DAAF_NESTED=1

    # The data copy (create/cp) and the Step 2b strip succeed; the Step 2c
    # ownership repair (`docker run ... chown`) fails.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"chown"* ]]; then
                    # Step 2c ownership repair fails.
                    return 1
                elif [[ "${args_str}" == *"rm -rf"* ]]; then
                    return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to repair ownership"
}

@test "restore: no backup folders found exits with error" {
    # No backup directories created in TEST_DIR
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/restore_from_backup.sh"
    assert_failure
    assert_output --partial "No backup folders found"
}

# --- Step 2d: permission replay ---

@test "restore: replays permissions when the backup contains a manifest" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    printf 'scripts/run.sh\n' > "${TEST_DIR}/2026-01-01_daaf_backup/.daaf-permissions"

    export DAAF_NESTED=1

    # Step 2d probes the volume with `docker run ... test -f /dest/.daaf-permissions`.
    # Model the manifest as PRESENT (test -f => 0) so the replay sh -c path runs.
    # Distinguish calls by substring: the manifest probe and replay both contain
    # ".daaf-permissions"; verification is `find /dest`.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"find /dest"* ]] && [[ "${args_str}" == *"wc -l"* ]]; then
                    # Verification: report 1 restored file (the RESTORED_FILES marker
                    # the real count program prints) so the restore succeeds.
                    echo "RESTORED_FILES=1"; return 0
                fi
                # test -f manifest probe (present), replay sh -c, clear, strip,
                # chown: all succeed.
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "Restoring executable permissions"
}

@test "restore: notes older backups that predate the permission manifest" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    # No .daaf-permissions manifest in this backup (older backup).

    export DAAF_NESTED=1

    # Step 2d probes with `docker run ... test -f /dest/.daaf-permissions`. Model the
    # manifest as ABSENT (test -f => 1) so the "predates" branch runs. Verification
    # (`find /dest ... wc -l`) still returns a non-zero count so the restore succeeds.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"test -f"* ]] && [[ "${args_str}" == *".daaf-permissions"* ]]; then
                    # Manifest absent.
                    return 1
                elif [[ "${args_str}" == *"find /dest"* ]] && [[ "${args_str}" == *"wc -l"* ]]; then
                    echo "RESTORED_FILES=1"; return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "may predate"
    assert_output --partial "permission preservation"
}

# =========================================================================
# --- Helper-container reap on `docker create` launch failure ---
# =========================================================================
# `docker create` echoes a CID to stdout; if the command then exits nonzero the
# command substitution has ALREADY captured that CID. The two launch guards must
# reap it (docker rm -f <cid>) so a launch failure does not leak a helper container.
# `docker create` is single-phase, so a fail-with-CID is near-theoretical here --
# these tests pin insurance parity with backup_daaf.sh's fixed launch guards and
# with the .ps1 twin's finally-reap. The mocks log every docker call to a file so
# the reap can be asserted after `run` (a bats array does not survive the `run`
# subshell). Each test FAILS against the pre-fix restore code (main branch: no reap
# before exit 1; Claude branch: `|| CLAUDE_CID=""` blanked the CID before the
# end-of-block reap).

@test "restore: main create launch failure reaps the captured helper container" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"

    export DAAF_NESTED=1

    # Step 1 volume-clear (`docker run --rm ... rm -rf`) succeeds; the Site A
    # `docker create` for the data volume prints a CID but exits nonzero. The error
    # branch must run `docker rm -f mockcid0000` before `exit 1`.
    docker() {
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create) echo "mockcid0000"; return 1 ;;
            cp)     return 0 ;;
            rm)     return 0 ;;
            run)    return 0 ;;
            *)      return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure
    assert_output --partial "Could not create the helper container"
    # The captured CID must have been reaped in the error branch (fix-specific).
    run grep -F 'rm -f mockcid0000' "${TEST_DIR}/docker_calls.log"
    assert_success
}

@test "restore: Claude create launch failure preserves and reaps the captured CID (WARNING, not fatal)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    # A non-empty Claude subfolder => HAS_CLAUDE_BACKUP=1, so the Claude restore path
    # runs after the data-volume restore succeeds.
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup/.daaf-claude-config"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/.daaf-claude-config/creds"

    export DAAF_NESTED=1

    # Data-volume restore succeeds (its `docker create` -> CID, exit 0). The
    # Claude-volume `docker create` prints a CID but exits nonzero; the fix keeps that
    # CID (no `|| CLAUDE_CID=""`) so the end-of-block `docker rm -f claudecid1111`
    # reaps it. The two creates are distinguished by the "claude-config" volume
    # substring. Both manifests probe ABSENT (test -f -> 1); verification returns a
    # positive count so the data restore succeeds. Claude failure stays a WARNING and
    # the script still completes (overall success).
    docker() {
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            ps)     return 0 ;;
            create)
                if printf '%s' "$*" | grep -q 'claude-config'; then
                    echo "claudecid1111"; return 1
                fi
                echo "datacid0000"; return 0
                ;;
            cp)     return 0 ;;
            rm)     return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"test -f"* ]]; then
                    return 1
                elif [[ "${args_str}" == *"find /dest"* ]] && [[ "${args_str}" == *"wc -l"* ]]; then
                    echo "RESTORED_FILES=1"; return 0
                fi
                return 0
                ;;
            *)      return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Failed to restore the Claude Code state volume"
    assert_output --partial "Verified: 1 files in restored volume."
    refute_output --partial "Could not verify the restored file count"
    # The Claude-state WARNING latches the banner (exit code unchanged: 0).
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Restore complete!"
    # The captured Claude CID must be reaped -- proving it was NOT blanked before cleanup.
    run grep -F 'rm -f claudecid1111' "${TEST_DIR}/docker_calls.log"
    assert_success
}

# =========================================================================
# --- FU1: a host read error makes the backup count a LOWER BOUND ---
# =========================================================================
# _daaf_tree_count captures find's stderr with the count; any error line makes the
# count a lower bound. The listing shows it as "N+" with a note; the scan of the
# SELECTED backup REFUSES (ERROR, exit 1) before the destructive prompt, because
# `docker cp` would hit the same unreadable files after Step 1 had erased the volume.
# The fixture is a chmod-000 subfolder inside TEST_DIR (teardown re-opens it). Root
# reads through mode 000, so these skip there.

_make_locked_backup() {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/locked"
    touch "${b}/f1"
    touch "${b}/locked/hidden"
    : > "${b}/.daaf-symlinks"
    chmod 000 "${b}/locked"
}

@test "restore FU1: listing shows an unreadable backup's count as 'N+' with a lower-bound note" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    _make_locked_backup
    export DAAF_NESTED=1
    # Empty selection: the listing prints, then the invalid selection exits 1.
    run bash -c 'echo "" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "1) 2026-01-01_daaf_backup  (1+ files,"
    assert_output --partial "(some folders in this backup could not be read; the file count is a lower bound)"
}

@test "restore FU1: the scan REFUSES an unreadable backup (exit 1) before the destructive prompt" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 folder"
    _make_locked_backup
    export DAAF_NESTED=1
    # Log every docker call: the refusal must precede Step 1's volume clear.
    docker() {
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        case "$1" in
            info|volume|ps) return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not read every file in this backup folder (at least 1 files were"
    assert_output --partial "readable), so it cannot be restored safely: the copy would hit the same problem"
    assert_output --partial "after your current data had been erased. Your DAAF data has not been changed."
    assert_output --partial "First error: find:"
    assert_output --partial "Make every folder and file in 2026-01-01_daaf_backup/ readable by your user account"
    # Never reached the destructive warning or its "Type RESTORE" prompt (bash's
    # `read -p` prints no prompt when stdin is a pipe, so the banner above it is the
    # observable anchor), and never touched the volume.
    refute_output --partial "DESTRUCTIVE OPERATION"
    refute_output --partial "Type RESTORE"
    refute_output --partial "Found "
    run grep -F 'rm -rf' "${TEST_DIR}/docker_calls.log"
    assert_failure
    run grep -E '^(create|cp) ' "${TEST_DIR}/docker_calls.log"
    assert_failure
}

# =========================================================================
# --- Unreadable FILES and an unreadable backup ROOT also refuse ---
# =========================================================================
# `find` opens folders, never regular files, so _daaf_tree_count cannot see a mode-000
# (or root-owned 0600) FILE in a readable folder. The scan's second pass tests every
# regular file with POSIX `[ -r ]` and refuses before the destructive prompt. A backup
# ROOT the user cannot enter refuses at selection time. Root reads through mode 000, so
# these skip there; teardown re-opens every mode (chmod -R u+rwx) before removal.

# Log every docker call so a test can prove no volume was touched.
_mock_logging_docker() {
    docker() {
        printf '%s\n' "$*" >> "${TEST_DIR}/docker_calls.log"
        return 0
    }
    export -f docker
}

_assert_no_volume_touched() {
    refute_output --partial "DESTRUCTIVE OPERATION"
    refute_output --partial "Found "
    if [ -f "${TEST_DIR}/docker_calls.log" ]; then
        run grep -F 'rm -rf' "${TEST_DIR}/docker_calls.log"
        assert_failure
        run grep -E '^(create|cp|rm) ' "${TEST_DIR}/docker_calls.log"
        assert_failure
    fi
}

@test "restore: a mode-000 FILE in a readable folder REFUSES before the destructive prompt" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 file"
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/sub"
    touch "${b}/f1" "${b}/sub/f2" "${b}/sub/secret"
    : > "${b}/.daaf-symlinks"
    chmod 000 "${b}/sub/secret"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    # The folder count saw nothing wrong (find lists folders, not file contents)...
    refute_output --partial "Could not read every file in this backup folder"
    # ...so the file pass is what refused.
    assert_output --partial "ERROR: 1 file(s) in this backup folder cannot be read by your user account,"
    assert_output --partial "so it cannot be restored safely: the copy would hit the same problem after"
    assert_output --partial "your current data had been erased. Your DAAF data has not been changed."
    assert_output --partial "First unreadable file: 2026-01-01_daaf_backup/sub/secret"
    assert_output --partial "Make every file in 2026-01-01_daaf_backup/ readable by your user account (check its"
    assert_output --partial "ownership and permissions -- e.g. a file created with sudo), then re-run the restore."
    _assert_no_volume_touched
}

@test "restore: unreadable files are COUNTED, including in the Claude subfolder and a root manifest" {
    [ "$(id -u)" -ne 0 ] || skip "root can read a chmod-000 file"
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/.daaf-claude-config"
    touch "${b}/f1" "${b}/.daaf-claude-config/creds"
    : > "${b}/.daaf-permissions"
    chmod 000 "${b}/.daaf-claude-config/creds" "${b}/.daaf-permissions"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    # `docker cp` copies the whole folder, so excluded-from-count paths are still checked.
    assert_output --partial "ERROR: 2 file(s) in this backup folder cannot be read by your user account,"
    _assert_no_volume_touched
}

@test "restore: a clean, fully readable backup is NOT refused by the file check" {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/sub" "${b}/.daaf-claude-config"
    touch "${b}/f1" "${b}/sub/f2" "${b}/.daaf-claude-config/creds"
    : > "${b}/.daaf-symlinks"
    : > "${b}/.daaf-permissions"
    export DAAF_NESTED=1
    _mock_logging_docker
    # Cancel at the confirmation: reaching the destructive banner is the pass condition.
    run bash -c 'printf "1\nno\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Found 2 files"
    assert_output --partial "DESTRUCTIVE OPERATION"
    assert_output --partial "Restore cancelled."
    refute_output --partial "cannot be read by your user account"
    refute_output --partial "Could not check that every file"
    refute_output --partial "ERROR:"
}

@test "restore: a file check that cannot finish REFUSES (defensive branch)" {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}"
    touch "${b}/f1"
    # A PATH shim `find` that fails ONLY the file-check invocation (`-exec sh -c ...`)
    # and passes every other call (the count) to the real find.
    local real_find
    real_find="$(command -v find)"
    mkdir -p "${TEST_DIR}/shim"
    printf '#!/usr/bin/env bash\ncase " $* " in *" -exec sh -c "*) echo "find: simulated check failure" >&2; exit 1 ;; esac\nexec "%s" "$@"\n' "${real_find}" > "${TEST_DIR}/shim/find"
    chmod +x "${TEST_DIR}/shim/find"
    export PATH="${TEST_DIR}/shim:${PATH}"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not check that every file in this backup folder is readable, so it"
    assert_output --partial "cannot be restored safely. Your DAAF data has not been changed."
    assert_output --partial "First error: find: simulated check failure"
    refute_output --partial "file(s) in this backup folder cannot be read"
    _assert_no_volume_touched
}

@test "restore: an unreadable backup ROOT refuses at selection with a refusal-style ERROR (no bare cd error)" {
    [ "$(id -u)" -ne 0 ] || skip "root can enter a chmod-000 folder"
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}"
    touch "${b}/f1"
    chmod 000 "${b}"
    export DAAF_NESTED=1
    _mock_logging_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Could not open the backup folder 2026-01-01_daaf_backup/, so it cannot be restored."
    assert_output --partial "Your DAAF data has not been changed."
    assert_output --partial "First error: "
    assert_output --partial "Permission denied"
    assert_output --partial "Make 2026-01-01_daaf_backup/ and every folder and file in it readable by your user"
    assert_output --partial "account (check its ownership and permissions), then re-run the restore."
    refute_output --partial "Selected: "
    refute_output --partial "Scanning backup..."
    _assert_no_volume_touched
}

# =========================================================================
# --- FU2: the post-restore count is a MARKER program ---
# =========================================================================
# RESTORED_FILES=<n> only when the count's stderr was empty, else
# RESTORED_COUNT_ERRORS=<lines>. Unavailable (error marker, docker failure, or no
# marker) is a WARNING with exit 0 -- never the false "0 files found" ERROR; a count
# READ as 0 still exits 1 ("restore: zero files after restore exits with error").

_mock_verify_docker() {
    docker() {
        case "$1" in
            info|volume|ps) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp) return 0 ;;
            run)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"test -f"* ]]; then
                    return 1  # no manifests in the restored volume
                elif [[ "${args_str}" == *"find /dest"* ]] && [[ "${args_str}" == *"wc -l"* ]]; then
                    case "${VERIFY_MODE}" in
                        errors) echo "RESTORED_COUNT_ERRORS=2"; return 0 ;;
                        fail) echo "verification container failed" >&2; return 1 ;;
                        bare) echo "1"; return 0 ;;
                        errorsfail) echo "RESTORED_COUNT_ERRORS=2"; return 1 ;;
                        countfail) echo "RESTORED_FILES=1"; return 1 ;;
                    esac
                fi
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
}

@test "restore FU2: a post-restore count with read errors is a WARNING, exit 0, never '0 files found'" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=errors
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "WARNING: Could not verify the restored file count: Docker hit 2 read error(s)"
    assert_output --partial "while counting the restored volume."
    assert_output --partial "The copy itself reported success, so your data is most likely in place. Start"
    assert_output --partial "Files:    not verified (the restored file count could not be read)"
    refute_output --partial "0 files found"
    refute_output --partial "File count mismatch"
    refute_output --partial "not verified files in volume"
    # An unverified count latches the banner; the exit code stays 0 (asserted above).
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
    refute_output --partial "Restore complete!"
}

@test "restore FU2: a failed or marker-less post-restore count is a WARNING, exit 0" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1
    # fail: the verification container exits 1. bare: an old-style bare number with
    # no RESTORED_FILES marker is not trusted as a count.
    for mode in fail bare; do
        export VERIFY_MODE="${mode}"
        _mock_verify_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
        assert_success
        assert_output --partial "WARNING: Could not verify the restored file count (the count inside Docker did not"
        assert_output --partial "Files:    not verified (the restored file count could not be read)"
        refute_output --partial "0 files found"
        refute_output --partial "Verified:"
        assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
        refute_output --partial "Restore complete!"
    done
}

# Marker parity with the .ps1 twin (restore_from_backup.Tests.ps1 "FU2: nonzero exit
# ..."): both parse the markers on ANY exit, let an error marker choose the read-error
# WARNING variant, and trust a count marker only on exit 0.
@test "restore FU2: nonzero exit + read-error marker gives the read-error WARNING variant (twin parity)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=errorsfail
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "WARNING: Could not verify the restored file count: Docker hit 2 read error(s)"
    assert_output --partial "while counting the restored volume."
    refute_output --partial "the count inside Docker did not"
    assert_output --partial "Files:    not verified (the restored file count could not be read)"
    refute_output --partial "0 files found"
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
}

@test "restore FU2: nonzero exit + a count marker is not trusted (exit-code WARNING variant, twin parity)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1 VERIFY_MODE=countfail
    _mock_verify_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "WARNING: Could not verify the restored file count (the count inside Docker did not"
    assert_output --partial "run cleanly, exit 1)."
    refute_output --partial "Verified:"
    assert_output --partial "Files:    not verified (the restored file count could not be read)"
    assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
}

@test "restore FU2: a post-restore count READ as RESTORED_FILES=0 exits 1 (not the unavailable WARNING)" {
    mkdir -p "${TEST_DIR}/2026-01-01_daaf_backup"
    touch "${TEST_DIR}/2026-01-01_daaf_backup/f1"
    export DAAF_NESTED=1
    docker() {
        case "$1" in
            info|volume|ps) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            run)
                shift
                if [[ "$*" == *"find /dest"* ]] && [[ "$*" == *"wc -l"* ]]; then
                    echo "RESTORED_FILES=0"; return 0
                fi
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_failure 1
    assert_output --partial "ERROR: Verification failed -- 0 files found in restored volume."
    refute_output --partial "Could not verify the restored file count"
    # A fatal exit prints neither banner.
    refute_output --partial "Restore complete!"
    refute_output --partial "Restore completed WITH WARNINGS"
}

# =========================================================================
# --- Completion banner: the WITH WARNINGS latch ---
# =========================================================================
# Every non-fatal WARNING on the success path latches HAD_WARNINGS, and the final
# banner then reads "Restore completed WITH WARNINGS -- verify before relying on it"
# instead of "Restore complete!" -- with the exit code UNCHANGED (0), because callers
# (daaf.sh run_delegate) branch on the exit code only. The mismatch, unverified-count
# and Claude-create cases above assert the latch too; these cover the clean baseline
# and the remaining WARNING sites. The fixture is a CURRENT-style backup (both root
# manifests plus a non-empty Claude subfolder), so every probe finds its manifest and
# a clean run prints no NOTE at all. BANNER_FAIL picks the one step that fails.

_make_full_backup() {
    local b="${TEST_DIR}/2026-01-01_daaf_backup"
    mkdir -p "${b}/.daaf-claude-config"
    touch "${b}/f1"
    printf 'scripts/run.sh\n' > "${b}/.daaf-permissions"
    : > "${b}/.daaf-symlinks"
    touch "${b}/.daaf-claude-config/creds"
}

_mock_banner_docker() {
    docker() {
        case "$1" in
            info|volume|ps|cp|rm) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            run)
                shift
                local a="$*"
                # Post-restore count first: the permission replay also holds "find /dest".
                if [[ "${a}" == *"find /dest"* ]] && [[ "${a}" == *"wc -l"* ]]; then
                    echo "RESTORED_FILES=1"; return 0
                fi
                case "${BANNER_FAIL:-none}" in
                    perms) [[ "${a}" == *"chmod 644"* ]] && return 1 ;;
                    symlinks) [[ "${a}" == *"daaf-data:/dest"* ]] && [[ "${a}" == *"ln -sf"* ]] && return 1 ;;
                    claudeclear) [[ "${a}" == *"claude-config:/dest"* ]] && [[ "${a}" == *"rm -rf /dest/*"* ]] && return 1 ;;
                    claudesymlinks) [[ "${a}" == *"claude-config:/dest"* ]] && [[ "${a}" == *"ln -sf"* ]] && return 1 ;;
                esac
                # Manifest probes (present), clear, strip, chown, replays: succeed.
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
}

@test "restore banner: a clean run prints 'Restore complete!' and never WITH WARNINGS" {
    _make_full_backup
    export DAAF_NESTED=1 BANNER_FAIL=none
    _mock_banner_docker
    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_success
    assert_output --partial "Restoring executable permissions"
    assert_output --partial "Restoring symlinks"
    assert_output --partial "Verified: 1 files in restored volume."
    assert_output --partial "Claude Code state restored."
    refute_output --partial "WARNING: Could not"
    refute_output --partial "WARNING: Failed"
    assert_output --partial "  Restore complete!"
    refute_output --partial "WITH WARNINGS"
    # The report and next-step lines follow the banner either way.
    assert_output --partial "Files:    1 files in volume"
    assert_output --partial "You can now start DAAF with:"
}

@test "restore banner: each remaining WARNING site latches WITH WARNINGS, exit 0" {
    _make_full_backup
    export DAAF_NESTED=1
    local step expect
    for step in perms symlinks claudeclear claudesymlinks; do
        case "${step}" in
            perms) expect="WARNING: Could not fully replay executable permissions." ;;
            symlinks) expect="WARNING: Could not fully replay symlinks from the manifest." ;;
            claudeclear) expect="WARNING: Failed to clear the Claude Code state volume before restore." ;;
            claudesymlinks) expect="WARNING: Could not fully replay Claude state symlinks." ;;
        esac
        export BANNER_FAIL="${step}"
        _mock_banner_docker
        run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
        assert_success
        assert_output --partial "${expect}"
        assert_output --partial "Restore completed WITH WARNINGS -- verify before relying on it"
        refute_output --partial "Restore complete!"
        # The verified data-volume count and the next steps still print.
        assert_output --partial "Files:    1 files in volume"
        assert_output --partial "You can now start DAAF with:"
    done
}
