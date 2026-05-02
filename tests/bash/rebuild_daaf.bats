#!/usr/bin/env bats
# ============================================================================
# Tests for rebuild_daaf.sh — DAAF Rebuild Utility
# ============================================================================
# Key testable logic: preflight checks, docker-compose.yml requirement,
# container existence check, file hash comparison.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    create_fake_compose_file
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "rebuild_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "rebuild_daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "rebuild_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "rebuild_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- Preflight: container not found ---

@test "rebuild_daaf.sh fails when container does not exist" {
    MOCK_DOCKER_INSPECT_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

# --- DAAF_NESTED behavior ---

@test "rebuild_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INSPECT_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Banner display ---

@test "rebuild_daaf.sh displays the DAAF Rebuild banner" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INSPECT_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_output --partial "DAAF Rebuild"
}

# --- Numbered progress steps ---

@test "rebuild_daaf.sh uses numbered progress steps [1/3] [2/3] [3/3]" {
    run grep -c '\[1/3\]\|\[2/3\]\|\[3/3\]' "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_success
    [ "${output}" -ge 3 ]
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "rebuild_daaf.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_success
}

@test "rebuild_daaf.sh: dry-run completes rebuild" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh" 2>&1
    assert_success
    assert_output --partial "Rebuild complete"
}

# =========================================================================
# Error paths
# =========================================================================

@test "rebuild_daaf.sh: fails when container not found (inspect fails)" {
    MOCK_DOCKER_INSPECT_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "not found"
}

@test "rebuild_daaf.sh: fails when Dockerfile copy from container fails" {
    export DAAF_NESTED=1
    # Custom docker mock: inspect succeeds, cp fails
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)
                # Fail on copy
                return 1
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to copy Dockerfile"
}

@test "rebuild_daaf.sh: fails when docker compose build fails and preserves pre-rebuild backup" {
    export DAAF_NESTED=1
    # Create a pre-existing Dockerfile so the script creates a .pre-rebuild backup
    echo "FROM old-image" > "${TEST_DIR}/Dockerfile"
    # Custom docker mock: inspect and cp succeed, compose build fails
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)
                # Simulate successful copy (write new content to Dockerfile)
                echo "FROM new-image" > ./Dockerfile
                return 0
                ;;
            compose)
                shift
                case "$1" in
                    build) return 1 ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Rebuild failed"
    assert_output --partial "pre-rebuild"
}

@test "rebuild_daaf.sh: fails when docker compose up -d fails after build" {
    export DAAF_NESTED=1
    # Custom docker mock: build succeeds, up fails
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)      return 0 ;;
            compose)
                shift
                case "$1" in
                    build) return 0 ;;
                    up) return 1 ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start"
}

@test "rebuild_daaf.sh: fails on container readiness timeout after rebuild" {
    export DAAF_NESTED=1
    # Custom docker mock: build and up succeed, exec always fails
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)      return 0 ;;
            compose)
                shift
                case "$1" in
                    build) return 0 ;;
                    up) return 0 ;;
                    exec) return 1 ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    # Override sleep to keep the test fast
    sleep() { true; }
    export -f sleep
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "did not become ready"
}

@test "rebuild_daaf.sh: fails when CLAUDE.md missing after rebuild" {
    export DAAF_NESTED=1
    # Custom docker mock: everything succeeds except test -f CLAUDE.md
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)      return 0 ;;
            compose)
                shift
                case "$1" in
                    build) return 0 ;;
                    up) return 0 ;;
                    exec)
                        local args_str="$*"
                        if [[ "${args_str}" == *"test -f"* ]]; then
                            return 1
                        fi
                        # Readiness check (exec ... true) succeeds
                        return 0
                        ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "WARNING"
    assert_output --partial "DAAF files may not be intact"
}

@test "rebuild_daaf.sh: hash comparison shows UPDATED when Dockerfile changed" {
    export DAAF_NESTED=1
    # Create a pre-existing Dockerfile with different content
    echo "FROM old-image" > "${TEST_DIR}/Dockerfile"
    # Custom docker mock: cp overwrites Dockerfile with new content
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"Dockerfile"* ]]; then
                    echo "FROM new-image" > ./Dockerfile
                fi
                if [[ "${args_str}" == *"docker-compose.yml"* ]]; then
                    # Keep compose file the same as existing
                    true
                fi
                return 0
                ;;
            compose)
                shift
                case "$1" in
                    build) return 0 ;;
                    up) return 0 ;;
                    exec)
                        # All exec calls succeed (readiness + verification)
                        return 0
                        ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_output --partial "Dockerfile: UPDATED"
}

@test "rebuild_daaf.sh: hash comparison shows no changes when files unchanged" {
    export DAAF_NESTED=1
    # Create pre-existing Dockerfile and docker-compose.yml with known content
    echo "FROM same-image" > "${TEST_DIR}/Dockerfile"
    # Custom docker mock: cp writes the same content (no changes)
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"Dockerfile"* ]]; then
                    echo "FROM same-image" > ./Dockerfile
                fi
                if [[ "${args_str}" == *"docker-compose.yml"* ]]; then
                    # Write same content to compose file
                    true
                fi
                return 0
                ;;
            compose)
                shift
                case "$1" in
                    build) return 0 ;;
                    up) return 0 ;;
                    exec) return 0 ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_output --partial "No changes detected"
}

@test "rebuild_daaf.sh: hash comparison shows UPDATED when compose file changed" {
    export DAAF_NESTED=1
    # Custom docker mock: cp overwrites docker-compose.yml with new content
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"docker-compose.yml"* ]]; then
                    echo "version: '3.9'" > ./docker-compose.yml
                fi
                return 0
                ;;
            compose)
                shift
                case "$1" in
                    build) return 0 ;;
                    up) return 0 ;;
                    exec) return 0 ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_output --partial "docker-compose.yml: UPDATED"
}

@test "rebuild_daaf.sh: fails when docker-compose.yml copy from container fails" {
    export DAAF_NESTED=1
    # Custom docker mock: Dockerfile copy succeeds, compose copy fails
    docker() {
        case "$1" in
            info)    return 0 ;;
            inspect) return 0 ;;
            cp)
                shift
                local args_str="$*"
                if [[ "${args_str}" == *"Dockerfile"* ]]; then
                    return 0
                fi
                if [[ "${args_str}" == *"docker-compose.yml"* ]]; then
                    return 1
                fi
                return 0
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/rebuild_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to copy docker-compose.yml"
}
