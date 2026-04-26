#!/usr/bin/env bats
# ============================================================================
# Tests for install.sh — DAAF One-Line Installer
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
