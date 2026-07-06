#!/usr/bin/env bats
# ============================================================================
# Tests for backup_daaf.sh -- DAAF Backup Utility
# ============================================================================
# Key testable logic: date-suffix versioning (a/b/c), preflight checks,
# volume existence validation.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    # backup_daaf.sh does not require docker-compose.yml
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "backup_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "backup_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "backup_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: volume not found ---

@test "backup_daaf.sh fails when Docker volume does not exist" {
    MOCK_DOCKER_VOLUME_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- DAAF_NESTED behavior ---

@test "backup_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Date-suffix versioning logic ---

@test "backup_daaf.sh generates 'a' suffix when base backup exists" {
    # Create a directory matching today's date backup name
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"

    # Mock volume inspect to succeed, mock docker run for scan
    # Scan now outputs 4 lines: file count, du -sk, du -sh, logical KB
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # Should show the suffixed backup name
    assert_output --partial "${today}a_daaf_backup"
}

@test "backup_daaf.sh generates 'b' suffix when 'a' also exists" {
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    mkdir -p "${TEST_DIR}/${today}a_daaf_backup"

    # Scan now outputs 4 lines: file count, du -sk, du -sh, logical KB
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}b_daaf_backup"
}

# --- Banner display ---

@test "backup_daaf.sh displays the DAAF Backup banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "DAAF Backup"
}

# --- Structural: safety features present ---

@test "backup_daaf.sh contains disk space pre-check" {
    run grep -c "Insufficient disk space" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh contains size-based verification" {
    run grep -c "Size verification" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh uses docker cp (not bind-mounted cp -a)" {
    # The copy mechanism is `docker create` + `docker cp` -- it must invoke a
    # quoted `docker cp "` (one for the data volume, one for the Claude state
    # volume) and must NOT use the old bind-mounted `cp -a /source` busybox copy.
    run grep -c 'docker create' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c 'docker cp "' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    run grep -c "cp -a /source" "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
}

# --- Executable-permission manifest ---

@test "backup_daaf.sh records the executable-permission manifest" {
    # The manifest ".daaf-permissions" is written into the backup root so a Windows
    # (NTFS) round-trip -- which loses POSIX modes -- can be undone on restore.
    run grep -c '\.daaf-permissions' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
    # It is generated container-side from the volume with -perm -0100 (owner-exec).
    run grep -c 'find /source -type f -perm -0100' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh writes the manifest as a WARNING-not-fatal step" {
    # A manifest write failure must not fail the backup (the data is still valid).
    run grep -c 'Could not record the executable-permission manifest' "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

# --- Date-suffix versioning edge cases ---

@test "backup: suffix picks first available letter sequentially" {
    # Create base and 'a' -- script should pick 'b' (next in sequence)
    local today
    today=$(date +%Y-%m-%d)
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    mkdir -p "${TEST_DIR}/${today}a_daaf_backup"
    # Also create 'c' to prove the script picks 'b' (first gap), not 'd'
    mkdir -p "${TEST_DIR}/${today}c_daaf_backup"

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}b_daaf_backup"
}

@test "backup: 26th backup of the day reaches suffix 'z'" {
    local today
    today=$(date +%Y-%m-%d)
    # Create base backup
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    # Create suffixes a through y (25 directories)
    for i in $(seq 0 24); do
        suffix=$(printf "\\$(printf '%03o' $((97 + i)))")
        mkdir -p "${TEST_DIR}/${today}${suffix}_daaf_backup"
    done

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}z_daaf_backup"
}

@test "backup: errors when all 26 suffixes are exhausted" {
    local today
    today=$(date +%Y-%m-%d)
    # Create base backup
    mkdir -p "${TEST_DIR}/${today}_daaf_backup"
    # Create all 26 suffixed directories (a through z)
    for i in $(seq 0 25); do
        suffix=$(printf "\\$(printf '%03o' $((97 + i)))")
        mkdir -p "${TEST_DIR}/${today}${suffix}_daaf_backup"
    done

    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "Too many backups"
}

# --- Disk space checks ---

@test "backup: fails when disk space is insufficient" {
    # Mock df to report very little available space
    df() {
        if [ "$1" = "-P" ]; then
            printf "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
            printf "/dev/sda1       100000000 99999990       10 100%% /\n"
        else
            builtin command df "$@"
        fi
    }
    export -f df

    MOCK_DOCKER_VOLUME_EXIT=0
    # Report volume size as 10000 KB (10 MB) -- much larger than 10 bytes available
    MOCK_DOCKER_RUN_OUTPUT=$'100\n10000\t/source\n10M\t/source\n9800'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "Insufficient disk space"
}

@test "backup: reports required vs available space on disk space failure" {
    df() {
        if [ "$1" = "-P" ]; then
            printf "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
            printf "/dev/sda1       100000000 99999990       10 100%% /\n"
        else
            builtin command df "$@"
        fi
    }
    export -f df

    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_RUN_OUTPUT=$'100\n10000\t/source\n10M\t/source\n9800'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    # Should report both required and available MB values
    assert_output --partial "Required:"
    assert_output --partial "Available:"
}

@test "backup: passes disk space check when sufficient space available" {
    df() {
        if [ "$1" = "-P" ]; then
            printf "Filesystem     1024-blocks    Used Available Capacity Mounted on\n"
            printf "/dev/sda1       100000000 50000000 50000000  50%% /\n"
        else
            builtin command df "$@"
        fi
    }
    export -f df

    MOCK_DOCKER_VOLUME_EXIT=0
    # Small volume (512 KB) -- plenty of space
    MOCK_DOCKER_RUN_OUTPUT=$'100\n512\t/source\n500K\t/source\n500'
    MOCK_DOCKER_RUN_EXIT=0
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # Should pass the disk space check (no "Insufficient" error)
    refute_output --partial "Insufficient disk space"
}

# --- Integrity verification: size mismatch ---

@test "backup: warns when backup size differs from source by more than 1 percent" {
    export DAAF_NESTED=1

    # Custom docker mock: scan reports 9800 logical KB source; the docker cp copy
    # creates a small file in the destination dir so FILE_COUNT > 0 and size
    # verification triggers. The backup file is ~1 KB vs 9800 KB source -- well
    # beyond 1% tolerance. The mock keys on docker subcommands (create/cp/rm) now
    # that the copy uses `docker create` + `docker cp` instead of a bind-mounted
    # `busybox cp -a`.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create)
                # Emit a fake container ID for the caller to cp from.
                echo "mockcid0000"
                return 0
                ;;
            cp)
                # `docker cp <cid>:/source/. <dest>/` -- the destination is the
                # last positional arg. Create a file there so the backup is non-empty.
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    # ~1 KB file (far less than 9800 KB source)
                    dd if=/dev/zero of="${dest_dir}/mock_file" bs=1024 count=1 2>/dev/null
                fi
                return 0
                ;;
            rm) return 0 ;;
            run)
                # Scan call: file count, du -sk, du -sh, logical KB
                printf '10\n10000\t/source\n10M\t/source\n9800\n'
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "WARNING"
    assert_output --partial "size mismatch"
}

# --- File count verification ---

@test "backup: reports file count in output on success" {
    export DAAF_NESTED=1

    # Custom docker mock: the docker cp copy step creates files so FILE_COUNT > 0.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2"
                fi
                return 0
                ;;
            rm) return 0 ;;
            run)
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "files copied"
}

# --- Core behavior ---

@test "backup: creates backup directory with date-based name" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # Custom docker mock: the docker cp copy step creates a file so the script
    # reaches success.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1"
                fi
                return 0
                ;;
            rm) return 0 ;;
            run)
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "${today}_daaf_backup"
    assert_output --partial "Backup complete"
}

@test "backup: writes .daaf-permissions manifest listing exec files on success" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # Custom docker mock: the data copy creates files; the manifest `docker run ...
    # find /source -perm -0100` call is distinguished from the scan `docker run ...
    # wc -l` call by the "-perm" substring, and returns two exec paths under
    # /source (which the script strips to volume-relative before writing).
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1"
                fi
                return 0
                ;;
            rm) return 0 ;;
            run)
                local args_str="$*"
                if [[ "${args_str}" == *"-perm -0100"* ]]; then
                    # Manifest generation: two exec files (absolute /source paths).
                    printf '/source/scripts/run.sh\n/source/hook.sh\n'
                else
                    # Scan: file count, du -sk, du -sh, logical KB
                    printf '5\n512\t/source\n500K\t/source\n500\n'
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_output --partial "Recorded"
    assert_output --partial "executable-permission manifest"
    # The manifest file exists in the backup root with volume-relative paths.
    run test -f "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    assert_success
    run cat "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    assert_output --partial "scripts/run.sh"
    assert_output --partial "hook.sh"
    refute_output --partial "/source/"
}

@test "backup: manifest preserves exec paths containing spaces verbatim" {
    export DAAF_NESTED=1
    local today
    today=$(date +%Y-%m-%d)

    # An exec file whose path contains spaces must survive the "/source/"-prefix strip
    # intact -- the `printf | sed | grep` manifest pipeline is whitespace-safe because
    # it operates line-by-line, not token-by-token. The manifest-generation `docker run
    # ... find -perm -0100` call is distinguished from the scan call by the "-perm"
    # substring; the data copy creates a file so FILE_COUNT > 0 and the script succeeds.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1"
                fi
                return 0
                ;;
            rm) return 0 ;;
            run)
                local args_str="$*"
                if [[ "${args_str}" == *"-perm -0100"* ]]; then
                    # One exec path with spaces in a directory component.
                    printf '/source/research/path with spaces/run.sh\n'
                else
                    printf '5\n512\t/source\n500K\t/source\n500\n'
                fi
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # The manifest must contain the "/source/"-stripped path VERBATIM, spaces intact.
    run cat "${TEST_DIR}/${today}_daaf_backup/.daaf-permissions"
    assert_output --partial "research/path with spaces/run.sh"
    refute_output --partial "/source/"
}

@test "backup: scan failure exits with error" {
    MOCK_DOCKER_VOLUME_EXIT=0
    # docker run for scanning fails
    MOCK_DOCKER_RUN_EXIT=1
    MOCK_DOCKER_RUN_OUTPUT=""
    export DAAF_NESTED=1

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Could not scan"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "backup_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_success
}

@test "backup_daaf.sh: dry-run produces DRY-RUN markers" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
}

@test "backup_daaf.sh: dry-run shows backup summary" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/backup_daaf.sh" 2>&1
    assert_success
    assert_output --partial "Would create backup at"
}

# =========================================================================
# --- Error paths ---
# =========================================================================

@test "backup: copy failure with zero files exits with error" {
    export DAAF_NESTED=1

    # Custom docker mock: scan succeeds, the docker cp copy fails (non-zero exit)
    # and creates no files.
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)     return 1 ;;
            rm)     return 0 ;;
            run)
                # Scan output: file count, du -sk, du -sh, logical KB
                printf '50\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
}

@test "backup: copy partially succeeds with non-zero exit but files copied shows warning" {
    export DAAF_NESTED=1

    # Custom docker mock: the docker cp copy returns non-zero but still creates files
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            create) echo "mockcid0000"; return 0 ;;
            cp)
                local dest_dir=""
                for arg in "$@"; do dest_dir="${arg}"; done
                dest_dir="${dest_dir%/}"
                if [ -n "${dest_dir}" ]; then
                    mkdir -p "${dest_dir}"
                    touch "${dest_dir}/file1" "${dest_dir}/file2" "${dest_dir}/file3"
                fi
                # Non-zero exit (partial failure)
                return 1
                ;;
            rm) return 0 ;;
            run)
                # Scan output
                printf '5\n512\t/source\n500K\t/source\n500\n'
                return 0
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    # Should succeed (files were copied) but note the warnings
    assert_output --partial "warnings"
    assert_output --partial "files were transferred"
}

@test "backup: volume scan outputs unexpected format triggers error" {
    export DAAF_NESTED=1
    MOCK_DOCKER_VOLUME_EXIT=0

    # Custom docker mock: scan returns garbage output
    docker() {
        case "$1" in
            info)   return 0 ;;
            volume) return 0 ;;
            run)
                # Return unexpected format
                printf 'unexpected_garbage_output\n'
                return 1
                ;;
            *)  return 0 ;;
        esac
    }
    export -f docker

    run bash "${REPO_ROOT}/scripts/host/backup_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
}
