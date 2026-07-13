#!/usr/bin/env bats
# ============================================================================
# Tests for view_quarto.sh -- DAAF Quarto Document Viewer
# ============================================================================
# Renders R Quarto notebooks (.qmd) to self-contained HTML, copies them out of
# the container, and opens them in the browser. Tests focus on preflight checks,
# container lifecycle, argument handling (discovery / project / direct path),
# dry-run behavior, and structural markers. Mirrors view_notebooks.bats.
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

# =========================================================================
# Tier 1 -- Syntax
# =========================================================================

@test "view_quarto.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
}

# =========================================================================
# Tier 2 -- Preflight checks
# =========================================================================

@test "view_quarto.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

@test "view_quarto.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

@test "view_quarto.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

@test "view_quarto.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
    refute_output --partial "Press Enter"
}

# =========================================================================
# Tier 3 -- Script structure
# =========================================================================

@test "view_quarto.sh includes set -euo pipefail" {
    run grep -c "set -euo pipefail" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh checks for docker-compose.yml" {
    run grep -c "docker-compose.yml" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh checks command -v docker" {
    run grep -c "command -v docker" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh checks docker info" {
    run grep -c "docker info" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh invokes quarto render" {
    run grep -c "quarto render" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh forces embed-resources for a self-contained HTML" {
    # The single-portable-file guarantee depends on this metadata flag being
    # passed regardless of the source .qmd's YAML.
    run grep -c "embed-resources:true" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh copies the rendered HTML out with docker compose cp" {
    run grep -c "compose cp" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh supports DAAF_TEST_MODE guard" {
    run grep -c "DAAF_TEST_MODE" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh supports DAAF_DRY_RUN" {
    run grep -c "DAAF_DRY_RUN" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh sources daaf_lib.sh when present" {
    run grep -c "source.*daaf_lib.sh" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_quarto.sh guards open_url behind command -v check" {
    run grep "command -v open_url" "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    assert_output --partial "open_url"
}

# =========================================================================
# Tier 4 -- Behavioral (DAAF_TEST_MODE)
# =========================================================================

@test "view_quarto.sh exits cleanly when sourced with DAAF_TEST_MODE=1" {
    export DAAF_TEST_MODE=1
    run bash -c "source '${REPO_ROOT}/scripts/host/view_quarto.sh'"
    assert_success
}

# =========================================================================
# Tier 5 -- Help
# =========================================================================

@test "view_quarto.sh --help prints usage and exits 0" {
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh" --help
    assert_success
    assert_output --partial "Usage"
    assert_output --partial ".qmd"
}

@test "view_quarto.sh rejects an unknown option" {
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh" --bogus
    assert_failure
    assert_output --partial "ERROR"
}

@test "view_quarto.sh rejects more than one positional argument" {
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_quarto.sh" projA projB
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Too many arguments"
}

# =========================================================================
# Tier 6 -- Dry-run
# =========================================================================

@test "view_quarto.sh: dry-run discovery lists available notebooks" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 2>&1
    assert_success
    assert_output --partial "Available Quarto notebooks"
    assert_output --partial ".qmd"
}

@test "view_quarto.sh: dry-run reports container running" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
}

@test "view_quarto.sh: dry-run render with a direct .qmd path completes" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" \
        research/2026-01-24_Sample_R_Project/2026-01-24_Sample_R_Project.qmd 2>&1
    assert_success
    assert_output --partial "Rendering"
    assert_output --partial "copied to"
}

@test "view_quarto.sh: dry-run render with a project folder completes" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" \
        2026-01-24_Sample_R_Project 2>&1
    assert_success
    assert_output --partial "Rendering"
    assert_output --partial "copied to"
}
