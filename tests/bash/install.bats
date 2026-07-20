#!/usr/bin/env bats
# ============================================================================
# Tests for install.sh -- DAAF One-Line Installer
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    mock_curl
    # install.sh does NOT require docker-compose.yml to exist beforehand
    # (it creates the install directory itself)
}

teardown() {
    common_teardown
}

# --- Syntax ---

@test "install.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
}

# --- Preflight: missing Docker ---

@test "install.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "install.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "install.sh suppresses pause trap when DAAF_NESTED=1" {
    # With DAAF_NESTED=1, the script should not set the EXIT trap
    # for read -r -p. We test this indirectly: the script will fail
    # (mocked docker info succeeds but curl creates empty files which
    # won't build), but the important thing is it does not hang on
    # "Press Enter".
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should not contain the pause prompt
    refute_output --partial "Press Enter"
}

# --- Existing installation detection ---

@test "install.sh detects existing installation and warns" {
    # Create the install directory with a compose file
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    # Mock docker volume inspect to succeed (volume exists)
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    # Run from a directory where daaf-docker/ exists
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "WARNING"
    assert_output --partial "existing DAAF installation"
}

# --- Download file list ---

@test "install.sh attempts to download required files" {
    export DAAF_NESTED=1
    # curl mock creates empty files; compose build will fail but we can
    # check that it gets past the download step
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # The script should have tried to download and then failed at build
    assert_failure
    assert_output --partial "Downloading"
}

# --- Branch override ---

@test "install.sh respects DAAF_BRANCH environment variable" {
    export DAAF_BRANCH="dev"
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "Branch: dev"
}

# --- Fresh install proceeds when no compose file exists ---

@test "install.sh proceeds with downloads when no prior installation exists" {
    # No compose file in daaf-docker/ -- fresh install path
    export DAAF_NESTED=1
    # Build will fail, but downloads should be attempted
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should reach the download step (no "existing installation" block)
    assert_output --partial "Downloading"
    refute_output --partial "existing DAAF installation"
}

# --- Incomplete installation detection ---

@test "install.sh proceeds when compose file exists but volume does not" {
    # Compose file present but volume inspect fails -- incomplete install
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should note incomplete install and continue
    assert_output --partial "previous install attempt"
    assert_output --partial "incomplete"
    assert_output --partial "Downloading"
}

# --- DAAF_FORCE_REINSTALL bypasses existing check ---

@test "install.sh proceeds when DAAF_FORCE_REINSTALL=1 despite existing installation" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_COMPOSE_EXIT=1
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should note force reinstall and proceed (not block)
    assert_output --partial "DAAF_FORCE_REINSTALL"
    assert_output --partial "Downloading"
    refute_output --partial "To update DAAF instead"
}

# --- Default branch is 'main' ---

@test "install.sh defaults to branch 'main' when DAAF_BRANCH is unset" {
    unset DAAF_BRANCH
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "Branch: main"
}

# --- Download failure exits non-zero ---

@test "install.sh exits with error when downloads fail" {
    export DAAF_NESTED=1
    MOCK_CURL_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to download"
}

# --- Download file list coverage ---

@test "install.sh downloads all required lifecycle scripts" {
    # Override curl to log the URLs it receives
    curl() {
        local outfile=""
        local url=""
        local args=("$@")
        for ((i=0; i<${#args[@]}; i++)); do
            case "${args[$i]}" in
                -o) outfile="${args[$((i+1))]}" ;;
                http*) url="${args[$i]}" ;;
            esac
        done
        echo "CURL_URL: ${url}" >> "${TEST_DIR}/curl_log.txt"
        if [ -n "${outfile}" ]; then
            touch "${outfile}"
        fi
        return 0
    }
    export -f curl

    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"

    # Verify all expected files were requested
    [ -f "${TEST_DIR}/curl_log.txt" ]
    run grep -c "CURL_URL:" "${TEST_DIR}/curl_log.txt"
    # Should download: Dockerfile, docker-compose.yml, run_daaf.sh,
    # backup_daaf.sh, rebuild_daaf.sh, update_daaf.sh, view_logs.sh, environment_settings_example.txt
    [ "$output" -ge 8 ]

    run cat "${TEST_DIR}/curl_log.txt"
    assert_output --partial "Dockerfile"
    assert_output --partial "docker-compose.yml"
    assert_output --partial "daaf.sh"
    assert_output --partial "daaf_lib.sh"
    assert_output --partial "run_daaf.sh"
    assert_output --partial "backup_daaf.sh"
    assert_output --partial "update_daaf.sh"
    assert_output --partial "view_logs.sh"
    assert_output --partial "view_notebooks.sh"
    assert_output --partial "view_quarto.sh"
    assert_output --partial "environment_settings_example.txt"
    assert_output --partial "README.txt"
}

# --- Download URLs use correct path prefix ---

@test "install.sh download URLs contain scripts/host/ prefix for lifecycle scripts" {
    curl() {
        local url=""
        local outfile=""
        local args=("$@")
        for ((i=0; i<${#args[@]}; i++)); do
            case "${args[$i]}" in
                -o) outfile="${args[$((i+1))]}" ;;
                http*) url="${args[$i]}" ;;
            esac
        done
        echo "${url}" >> "${TEST_DIR}/curl_urls.txt"
        if [ -n "${outfile}" ]; then
            touch "${outfile}"
        fi
        return 0
    }
    export -f curl

    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"

    [ -f "${TEST_DIR}/curl_urls.txt" ]
    # All .sh and environment_settings_example.txt downloads should use scripts/host/ prefix
    run grep "scripts/host/" "${TEST_DIR}/curl_urls.txt"
    assert_success
}

# --- Creates daaf-docker directory ---

@test "install.sh creates daaf-docker directory" {
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # The directory should have been created
    [ -d "${TEST_DIR}/daaf-docker" ]
}

# --- Build step invoked ---

@test "install.sh invokes docker compose build" {
    export DAAF_NESTED=1
    # Let build succeed, but up fail so we don't reach later steps
    MOCK_DOCKER_COMPOSE_EXIT=0
    # Actually: compose mock returns same exit for build and up.
    # We need compose to eventually stop. Let exec fail for the readiness check.
    MOCK_DOCKER_EXEC_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "Building Docker image"
}

# --- Readiness check looks for CLAUDE.md ---

@test "install.sh verifies CLAUDE.md exists in container" {
    export DAAF_NESTED=1
    # exec mock returns success -- test -f /daaf/CLAUDE.md passes
    MOCK_DOCKER_EXEC_EXIT=0
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # If readiness + clone + verify all succeed, should reach completion
    assert_output --partial "Installation complete"
}

# --- Existing installation suggests update_daaf.sh ---

@test "install.sh suggests update_daaf.sh when blocking on existing installation" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "update_daaf.sh"
}

# =========================================================================
# Dry-run mode
# =========================================================================

@test "install.sh: dry-run completes successfully" {
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    # Clean up the daaf-docker directory created by install.sh
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}

@test "install.sh: dry-run produces DRY-RUN markers" {
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh" 2>&1
    assert_success
    assert_output --partial "[DRY-RUN]"
    # Clean up the daaf-docker directory created by install.sh
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}

# --- Regression: non-writing dry-run (2026-07-14 root-stub incident) ---
# Root cause: the dry-run curl mock touched a zero-byte stub for every -o
# target under $INSTALL_DIR (=<CWD>/daaf-docker). A dry-run install must now
# create NOTHING on disk -- no daaf-docker/ directory, no stub files. See:
# research/2026-07-15_FrameworkDev_CwdLeakRootStubs/SESSION_NOTES.md

@test "install.sh: dry-run creates no daaf-docker directory or files" {
    cd "${TEST_DIR}"
    local before_listing
    before_listing="$(ls -A "${TEST_DIR}" | sort)"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    # No daaf-docker/ directory (the install target) should exist.
    [ ! -e "${TEST_DIR}/daaf-docker" ]
    # The directory contents must be identical before and after.
    local after_listing
    after_listing="$(ls -A "${TEST_DIR}" | sort)"
    [ "${before_listing}" = "${after_listing}" ]
}

# =========================================================================
# Diagnostic builder (DAAF_DIAG_BUILD=1)
# =========================================================================

@test "install.sh: DAAF_DIAG_BUILD=1 creates the diagnostic builder (inspect miss -> create)" {
    cd "${TEST_DIR}"
    # The dry-run docker mock returns non-zero for `buildx inspect` (builder
    # absent) and zero for `buildx create`, so the create arm runs and the diag
    # builder is selected.
    run env DAAF_DRY_RUN=1 DAAF_DIAG_BUILD=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh" 2>&1
    assert_success
    assert_output --partial "Created diagnostic buildx builder"
    assert_output --partial "separate build cache"
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}

@test "install.sh: DAAF_DIAG_BUILD=1 reuses an existing diagnostic builder (inspect hit)" {
    cd "${TEST_DIR}"
    # Custom mock: buildx inspect SUCCEEDS (builder already exists), so the reuse
    # arm runs. Every other arm returns success so the install completes.
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *"buildx inspect"*) return 0 ;;
            *"buildx create"*)  return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    curl() {
        local outfile="" args=("$@") i
        for (( i=0; i<${#args[@]}; i++ )); do
            if [ "${args[$i]}" = "-o" ] && [ $((i+1)) -lt ${#args[@]} ]; then
                outfile="${args[$((i+1))]}"; break
            fi
        done
        if [ -n "${outfile}" ]; then mkdir -p "$(dirname "${outfile}")"; touch "${outfile}"; fi
        return 0
    }
    export -f curl
    sleep() { true; }
    export -f sleep
    run env DAAF_DIAG_BUILD=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh" 2>&1
    assert_success
    assert_output --partial "Reusing existing diagnostic buildx builder"
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}

@test "install.sh: DAAF_DIAG_BUILD=1 falls back to default builder when create fails (fail-open)" {
    cd "${TEST_DIR}"
    # Custom mock: buildx inspect AND create both fail; the build must still run.
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *"buildx inspect"*) return 1 ;;
            *"buildx create"*)  return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    curl() {
        local outfile="" args=("$@") i
        for (( i=0; i<${#args[@]}; i++ )); do
            if [ "${args[$i]}" = "-o" ] && [ $((i+1)) -lt ${#args[@]} ]; then
                outfile="${args[$((i+1))]}"; break
            fi
        done
        if [ -n "${outfile}" ]; then mkdir -p "$(dirname "${outfile}")"; touch "${outfile}"; fi
        return 0
    }
    export -f curl
    sleep() { true; }
    export -f sleep
    run env DAAF_DIAG_BUILD=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/install.sh" 2>&1
    assert_success
    assert_output --partial "could not be"
    refute_output --partial "Created diagnostic buildx builder"
    rm -r "${TEST_DIR}/daaf-docker" 2>/dev/null || true
}

@test "install.sh: build-failure hint mentions DAAF_DIAG_BUILD for clipped logs" {
    export DAAF_NESTED=1
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "DAAF_DIAG_BUILD=1"
}

# =========================================================================
# Error paths
# =========================================================================

@test "install.sh: fails when docker compose build fails" {
    export DAAF_NESTED=1
    # Custom docker mock: volume inspect fails (no existing install),
    # compose build returns non-zero
    # Match patterns are space/flag-anchored so they cannot collide with the
    # random mktemp INSTALL_DIR path embedded in "$*" (a "/tmp/tmp.XXXXXXXX"
    # suffix is alphanumeric -- no spaces, no hyphens, no long literals).
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "build failed"
}

@test "install.sh: fails when docker compose up -d fails" {
    export DAAF_NESTED=1
    # Custom docker mock: build succeeds, up fails
    # Space/flag-anchored patterns -- immune to the random mktemp path in "$*".
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start"
}

@test "install.sh: fails on container readiness timeout" {
    export DAAF_NESTED=1
    # Custom docker mock: build and up succeed, exec always fails (readiness never achieved)
    # Space/flag-anchored patterns -- immune to the random mktemp path in "$*".
    # The generic-exec fallback matches "exec -T daaf-docker" (the fixed flag +
    # service string every install.sh exec call carries), never a path fragment.
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"exec -T daaf-docker"*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    # Override MAX_RETRIES via the script's sleep loop -- we can't override
    # the variable directly since the script sets it. Instead, trust that
    # the loop will exit after MAX_RETRIES. To keep the test fast, override
    # sleep to be a no-op.
    sleep() { true; }
    export -f sleep
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "did not become ready"
}

@test "install.sh: fails when curl download fails" {
    export DAAF_NESTED=1
    MOCK_CURL_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to download"
}

@test "install.sh: fails when git clone into container fails" {
    export DAAF_NESTED=1
    # Custom docker mock: build/up/readiness succeed, but exec for git clone fails
    # Space/flag-anchored patterns -- immune to the random mktemp path in "$*".
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"git clone"*) return 1 ;;
            *"exec -T daaf-docker"*) return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to clone"
}

@test "install.sh: fails when CLAUDE.md verification fails post-install" {
    export DAAF_NESTED=1
    # Custom docker mock: everything succeeds except the final test -f check
    # Space/flag-anchored patterns -- immune to the random mktemp path in "$*".
    # The verification arm matches the full literal "test -f /daaf/CLAUDE.md"
    # so it can never be shadowed by an earlier loose arm colliding with the
    # temp path (the historical flake: "$*" containing "up" matched *compose*up*
    # first and returned 0, so the intended verification failure never fired).
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"test -f /daaf/CLAUDE.md"*) return 1 ;;
            *"exec -T daaf-docker"*) return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "CLAUDE.md was not found"
}

@test "install.sh: force reinstall proceeds with existing volume" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    # Let it proceed past existing check and then fail at build
    # (to confirm it did NOT block on existing installation)
    MOCK_DOCKER_VOLUME_EXIT=0
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Should have proceeded past the existing-installation check
    assert_output --partial "DAAF_FORCE_REINSTALL"
    assert_output --partial "Downloading"
    # Should NOT contain the blocking message
    refute_output --partial "To update DAAF instead"
}

@test "install.sh: existing installation detected without force flag exits 1" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_DOCKER_VOLUME_EXIT=0
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "WARNING"
    assert_output --partial "existing DAAF installation"
}

@test "install.sh: success message mentions daaf.sh as recommended entry point" {
    export DAAF_NESTED=1
    MOCK_DOCKER_EXEC_EXIT=0
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "bash daaf.sh"
    assert_output --partial "DAAF Control Panel (recommended)"
}

@test "install.sh: fails when copy repo files into container fails" {
    export DAAF_NESTED=1
    # Custom docker mock: git clone succeeds, but bash -c cp fails
    # Space/flag-anchored patterns -- immune to the random mktemp path in "$*".
    # NOTE: install.sh issues TWO `bash -c` exec calls -- the pre-clone
    # `rm -rf /daaf/.git ...` cleanup (line ~275) and the post-clone `cp -a`
    # (line ~294). This test targets the copy step, but the earlier rm cleanup
    # runs with `|| true`, so returning 1 for it is harmless; the assertion
    # ("Failed to copy repository files") fires only when the cp `bash -c`
    # returns non-zero, which this arm forces. Matching the full literal
    # "cp -a /tmp/daaf-clone" would be more precise, but "bash -c" preserves the
    # original arm's intent (both calls carry it) and is path-proof.
    docker() {
        case "$*" in
            "info")   return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"bash -c"*) return 1 ;;
            *"exec -T daaf-docker"*) return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to copy repository files"
}

# =========================================================================
# Settings seeding (environment_settings.txt from process-env DAAF_*)
# =========================================================================
# The installer seeds a fresh environment_settings.txt from the example template,
# upserting any DAAF_* choices present in the process environment. Binding rules:
# never overwrite an existing file, never fail the install, never persist a
# DAAF_BRANCH that resolves to a version tag (symbolic-ref probe), and stay fully
# DAAF_DRY_RUN gated. These behavioral tests reach the seeder via the full
# success path (MOCK_DOCKER_EXEC_EXIT=0 -> CLAUDE.md verify passes -> completion).

@test "install.sh: seeds environment_settings.txt from process-env DAAF_* when absent" {
    export DAAF_NESTED=1
    export DAAF_PROJECT_NAME="myproj"
    export DAAF_PORT_MARIMO="9990"
    MOCK_DOCKER_EXEC_EXIT=0
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "seeded these values"
    assert_output --partial "DAAF_PROJECT_NAME"
    [ -f "${TEST_DIR}/daaf-docker/environment_settings.txt" ]
    run cat "${TEST_DIR}/daaf-docker/environment_settings.txt"
    assert_output --partial "DAAF_PROJECT_NAME=myproj"
    assert_output --partial "DAAF_PORT_MARIMO=9990"
}

@test "install.sh: seeds DAAF_DATA_VOLUME_NAME from the process environment when set" {
    # The data-volume override rides the same seeding array as the multi-instance
    # keys, so a value exported for the install persists into the settings file.
    export DAAF_NESTED=1
    export DAAF_PROJECT_NAME="myproj"
    export DAAF_DATA_VOLUME_NAME="shared_workspace_vol"
    MOCK_DOCKER_EXEC_EXIT=0
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "seeded these values"
    [ -f "${TEST_DIR}/daaf-docker/environment_settings.txt" ]
    run cat "${TEST_DIR}/daaf-docker/environment_settings.txt"
    assert_output --partial "DAAF_DATA_VOLUME_NAME=shared_workspace_vol"
}

@test "install.sh: preserves an existing environment_settings.txt (never overwrites)" {
    export DAAF_NESTED=1
    export DAAF_PROJECT_NAME="ignored"
    MOCK_DOCKER_EXEC_EXIT=0
    cd "${TEST_DIR}"
    mkdir -p "${TEST_DIR}/daaf-docker"
    printf 'DAAF_PROJECT_NAME=original\n# my real API keys\n' > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    before="$(cat "${TEST_DIR}/daaf-docker/environment_settings.txt")"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "left untouched"
    after="$(cat "${TEST_DIR}/daaf-docker/environment_settings.txt")"
    [ "${before}" = "${after}" ]
}

@test "install.sh: does not seed DAAF_BRANCH when it resolves to a version tag" {
    export DAAF_NESTED=1
    export DAAF_BRANCH="v1.2.3"
    export DAAF_PROJECT_NAME="myproj"
    # Custom mock: container clone is detached (tag) -> symbolic-ref fails; every
    # other exec (readiness, clone, cp, CLAUDE.md verify) succeeds so the install
    # completes and reaches the seeder.
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"symbolic-ref"*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "is a version tag"
    [ -f "${TEST_DIR}/daaf-docker/environment_settings.txt" ]
    run cat "${TEST_DIR}/daaf-docker/environment_settings.txt"
    refute_output --partial "DAAF_BRANCH="
    assert_output --partial "DAAF_PROJECT_NAME=myproj"
}

@test "install.sh: could-not-verify (exec failure) skips DAAF_BRANCH without a false tag claim" {
    export DAAF_NESTED=1
    export DAAF_BRANCH="v1.2.3"
    export DAAF_PROJECT_NAME="myproj"
    # Custom mock: the health probe (`git rev-parse HEAD`) fails, simulating a
    # stopped container / transient exec error; the branch-vs-tag classification
    # is therefore UNVERIFIED (not "tag"). Every other exec succeeds so the install
    # completes and reaches the seeder. rev-parse HEAD is used ONLY by the seeder's
    # health probe (verified), so failing it is surgical.
    docker() {
        case "$*" in
            "info") return 0 ;;
            *"volume inspect"*) return 1 ;;
            *" build --progress"*) return 0 ;;
            *" up -d"*) return 0 ;;
            *"rev-parse HEAD"*) return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    mock_curl
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    # Honest "could not verify" note, and crucially NO false "is a version tag" claim.
    assert_output --partial "could not verify whether 'v1.2.3' is"
    refute_output --partial "is a version tag"
    # DAAF_BRANCH was not seeded; the other key still was.
    [ -f "${TEST_DIR}/daaf-docker/environment_settings.txt" ]
    run cat "${TEST_DIR}/daaf-docker/environment_settings.txt"
    refute_output --partial "DAAF_BRANCH="
    assert_output --partial "DAAF_PROJECT_NAME=myproj"
}

@test "install.sh: settings-seeding failure does not fail the install" {
    export DAAF_NESTED=1
    export DAAF_PROJECT_NAME="myproj"
    MOCK_DOCKER_EXEC_EXIT=0
    # Force the seeder's `cp "${SEED_SRC}" "${SEED_DST}"` to fail. cp is used on
    # the host ONLY by the seeder (and its inlined upsert, which is never reached
    # once the seed copy fails), so overriding it is surgical.
    cp() { return 1; }
    export -f cp
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "did not fully complete"
    [ ! -f "${TEST_DIR}/daaf-docker/environment_settings.txt" ]
}

@test "install.sh: dry-run does not create environment_settings.txt (seeder zero-write)" {
    cd "${TEST_DIR}"
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 DAAF_PROJECT_NAME=myproj bash "${REPO_ROOT}/scripts/host/install.sh" 2>&1
    assert_success
    assert_output --partial "Would seed"
    [ ! -f "${TEST_DIR}/daaf-docker/environment_settings.txt" ]
    [ ! -e "${TEST_DIR}/daaf-docker" ]
}
