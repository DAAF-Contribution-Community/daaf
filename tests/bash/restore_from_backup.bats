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
