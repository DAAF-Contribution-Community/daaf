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

teardown() {
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
                    echo "1"; return 0
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
                    echo "1"; return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    # No symlink manifest => the "Restoring symlinks" line must NOT appear, and the
    # restore still completes.
    refute_output --partial "Restoring symlinks"
    assert_output --partial "Restore complete"
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
                    echo "0"
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
                    echo "10"
                    return 0
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash -c 'printf "1\nRESTORE\n" | bash "'"${REPO_ROOT}"'/scripts/host/restore_from_backup.sh"'
    assert_output --partial "WARNING"
    assert_output --partial "File count mismatch"
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
                    # Verification: report 1 restored file so the restore succeeds.
                    echo "1"; return 0
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
                    echo "1"; return 0
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
                    echo "1"; return 0
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
    # The captured Claude CID must be reaped -- proving it was NOT blanked before cleanup.
    run grep -F 'rm -f claudecid1111' "${TEST_DIR}/docker_calls.log"
    assert_success
}
