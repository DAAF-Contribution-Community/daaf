#!/usr/bin/env bats
# ============================================================================
# Tests for update_daaf.sh — DAAF Update Script
# ============================================================================
# update_daaf.sh is the most complex script: state machine with ahead/behind
# detection, merge/rebase paths, stash handling, conflict resolution.
# These tests focus on preflight checks and early-exit paths that can be
# tested without a real Docker daemon.
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

@test "update_daaf.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
}

# --- Preflight: missing docker-compose.yml ---

@test "update_daaf.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "update_daaf.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "update_daaf.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "update_daaf.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    # Will fail at some docker step, but should not pause
    MOCK_DOCKER_COMPOSE_EXIT=1
    MOCK_DOCKER_PS_OUTPUT=""
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    refute_output --partial "Press Enter"
}

# --- Helper function: prompt_choice ---

@test "update_daaf.sh defines prompt_choice helper function" {
    # Verify the function exists in the script source
    run grep -c "prompt_choice()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: handle_conflict ---

@test "update_daaf.sh defines handle_conflict helper function" {
    run grep -c "handle_conflict()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: sync_host_scripts ---

@test "update_daaf.sh defines sync_host_scripts helper function" {
    run grep -c "sync_host_scripts()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: check_build_changes ---

@test "update_daaf.sh defines check_build_changes helper function" {
    run grep -c "check_build_changes()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Helper function: finish_update ---

@test "update_daaf.sh defines finish_update helper function" {
    run grep -c "finish_update()" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- ERR trap defined ---

@test "update_daaf.sh defines an ERR trap for cleanup" {
    run grep -c "trap cleanup_on_error ERR" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# --- Banner display ---

@test "update_daaf.sh displays the DAAF Updater banner" {
    export DAAF_NESTED=1
    # Will fail at preflight but should show banner first
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_output --partial "DAAF Updater"
}

# --- DAAF_BRANCH override ---

@test "update_daaf.sh uses DAAF_BRANCH variable in banner tip" {
    # The script references DAAF_BRANCH for branch resolution
    run grep -c "DAAF_BRANCH" "${REPO_ROOT}/scripts/host/update_daaf.sh"
    assert_success
    [ "${output}" -ge 1 ]
}
