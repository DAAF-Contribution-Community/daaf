#!/usr/bin/env bats
# ============================================================================
# Tests for run_vscode.sh -- DAAF Code Browser (VS Code in the browser)
# and for the container-side launcher it calls, scripts/launch_code_server.sh
# ============================================================================
# Thin wrapper script -- tests focus on preflight checks, container lifecycle,
# dry-run behavior, and structural markers. The last section tests
# launch_code_server.sh (NODE_OPTIONS trust-store flag) with a fake code-server.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    create_fake_compose_file
}

teardown() {
    # The unreadable-settings test chmods the fixture to 000; give it its
    # permissions back so the fixture tree is left in a normal state for removal.
    if [ -e "${TEST_DIR}/environment_settings.txt" ]; then
        chmod 644 "${TEST_DIR}/environment_settings.txt" 2>/dev/null || true
    fi
    common_teardown
}

# =========================================================================
# Tier 1 -- Syntax
# =========================================================================

@test "run_vscode.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
}

# =========================================================================
# Tier 2 -- Preflight checks
# =========================================================================

# --- Preflight: missing docker-compose.yml ---

@test "run_vscode.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "run_vscode.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "run_vscode.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "run_vscode.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    refute_output --partial "Press Enter"
}

# --- Preflight: unreadable environment_settings.txt ---

@test "run_vscode.sh exits with a permissions message when environment_settings.txt is unreadable" {
    # The loader's open check is silent, so the script must name the file and
    # the fix itself rather than exit 1 with no output (a dry run otherwise
    # succeeds, so exit 1 here means the settings load stopped it).
    printf 'DAAF_PORT_VSCODE=3003\n' > "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    if [ -r "${TEST_DIR}/environment_settings.txt" ]; then
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" </dev/null
    assert_failure 1
    assert_output --partial "ERROR: Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it."
    assert_output --partial "Fix that (or move the file aside), then run run_vscode.sh again."
    refute_output --partial "Permission denied"
    refute_output --partial "Press Enter"
}

# =========================================================================
# Tier 3 -- Script structure
# =========================================================================

@test "run_vscode.sh includes set -euo pipefail" {
    run grep -c "set -euo pipefail" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh checks for docker-compose.yml" {
    run grep -c "docker-compose.yml" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh checks command -v docker" {
    run grep -c "command -v docker" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh checks docker info" {
    run grep -c "docker info" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh references launch_code_server.sh" {
    run grep -c "launch_code_server.sh" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh mentions Code Browser in output" {
    run grep -c "Code Browser" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh supports DAAF_TEST_MODE guard" {
    run grep -c "DAAF_TEST_MODE" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh supports DAAF_DRY_RUN" {
    run grep -c "DAAF_DRY_RUN" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# =========================================================================
# Tier 4 -- Behavioral (DAAF_TEST_MODE)
# =========================================================================

@test "run_vscode.sh exits cleanly when sourced with DAAF_TEST_MODE=1" {
    export DAAF_TEST_MODE=1
    run bash -c "source '${REPO_ROOT}/scripts/host/run_vscode.sh'"
    assert_success
}

# =========================================================================
# Tier 5 -- Dry-run
# =========================================================================

@test "run_vscode.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
}

@test "run_vscode.sh: dry-run completes without real Docker" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
    assert_output --partial "Code Browser"
}

@test "run_vscode.sh: dry-run shows Code Browser message" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" 2>&1
    assert_success
    assert_output --partial "Code Browser"
}

@test "run_vscode.sh: dry-run reports container running" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Tier 6 -- Error paths
# =========================================================================

# --- Container not running → start attempt ---

@test "run_vscode.sh attempts to start container when not running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=0
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_output --partial "Starting DAAF container"
}

# --- Container start fails ---

@test "run_vscode.sh fails when container start fails" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start the container"
}

# --- Code-server launch fails ---

@test "run_vscode.sh reports error when code-server fails to start" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start code-server"
    # code-server's own messages print in this terminal; a bare `docker compose
    # logs` would not show them (and would read the default install's log).
    assert_output --partial "If you stopped it yourself with Ctrl+C, you can ignore this."
    refute_output --partial "docker compose logs"
}

# --- Container already running ---

@test "run_vscode.sh reports container already running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Browser auto-open (open_url integration)
# =========================================================================

@test "run_vscode.sh sources daaf_lib.sh when present" {
    run grep -c "source.*daaf_lib.sh" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "run_vscode.sh calls open_url with the host VS Code port (default 2720)" {
    # The URL uses the overridable host port var (defaults to 2720). Assert the
    # parameterized form plus the default resolution.
    run grep 'open_url.*DAAF_PORT_VSCODE' "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    assert_output --partial 'http://localhost:${DAAF_PORT_VSCODE}'
    run grep 'DAAF_PORT_VSCODE:-2720' "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
}

@test "run_vscode.sh guards open_url behind command -v check" {
    # Verify the script uses a guard pattern so open_url is only called
    # when the function is actually available (backwards compatible when
    # daaf_lib.sh is absent).
    run grep "command -v open_url" "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    assert_output --partial "open_url"
}

@test "run_vscode.sh dry-run completes with library sourcing" {
    # With daaf_lib.sh present, open_url is a no-op in dry-run mode.
    # Confirms the full script (including library sourcing) works end-to-end.
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/run_vscode.sh"
    assert_success
    assert_output --partial "Code Browser"
}

# =========================================================================
# Container-side launcher (launch_code_server.sh): TLS trust store
# =========================================================================
# code-server's bundled Node must use the OS CA store (--use-openssl-ca), not
# its built-in root list, which still trusts emSign ECC Root CA - G3. A fake
# code-server on PATH records the NODE_OPTIONS it was started with. Port 1 is
# passed so the launcher's own listener probe never finds a running server.

_fake_code_server() {
    mkdir -p "${TEST_DIR}/bin"
    printf '#!/usr/bin/env bash\nprintf "%%s\\n" "${NODE_OPTIONS-<unset>}" > "%s/node_options.log"\n' "${TEST_DIR}" > "${TEST_DIR}/bin/code-server"
    chmod +x "${TEST_DIR}/bin/code-server"
}

@test "launch_code_server.sh adds --use-openssl-ca when NODE_OPTIONS is unset" {
    _fake_code_server
    run env -u NODE_OPTIONS PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1
    assert_success
    run cat "${TEST_DIR}/node_options.log"
    assert_output "--use-openssl-ca"
}

@test "launch_code_server.sh appends --use-openssl-ca to an existing NODE_OPTIONS" {
    _fake_code_server
    run env NODE_OPTIONS="--max-old-space-size=4096" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1
    assert_success
    run cat "${TEST_DIR}/node_options.log"
    assert_output "--max-old-space-size=4096 --use-openssl-ca"
}

@test "launch_code_server.sh does not duplicate --use-openssl-ca" {
    _fake_code_server
    run env NODE_OPTIONS="--use-openssl-ca --max-old-space-size=4096" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1
    assert_success
    run cat "${TEST_DIR}/node_options.log"
    assert_output "--use-openssl-ca --max-old-space-size=4096"
}

@test "launch_code_server.sh leaves an explicit --use-bundled-ca alone and warns" {
    # Node refuses --use-openssl-ca together with --use-bundled-ca (exit 9), so
    # appending would stop code-server from starting at all.
    _fake_code_server
    run env NODE_OPTIONS="--use-bundled-ca" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1
    assert_success
    assert_output --partial "WARNING: NODE_OPTIONS contains --use-bundled-ca"
    refute_output --partial "contains both"
    run cat "${TEST_DIR}/node_options.log"
    assert_output "--use-bundled-ca"
}

@test "launch_code_server.sh treats an empty NODE_OPTIONS like an unset one" {
    _fake_code_server
    run env NODE_OPTIONS="" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1
    assert_success
    run cat "${TEST_DIR}/node_options.log"
    assert_output "--use-openssl-ca"
}

@test "launch_code_server.sh warns when NODE_OPTIONS holds both CA flags" {
    # Node exits 9 on that combination, so code-server would not start; the
    # value is passed on unchanged, in either order, adjacent or not.
    local value
    for value in "--use-openssl-ca --use-bundled-ca" "--use-bundled-ca --max-old-space-size=64 --use-openssl-ca"; do
        _fake_code_server
        rm -f "${TEST_DIR}/node_options.log"
        run env NODE_OPTIONS="${value}" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1
        assert_success
        assert_output --partial "WARNING: NODE_OPTIONS contains both --use-openssl-ca and --use-bundled-ca"
        run cat "${TEST_DIR}/node_options.log"
        assert_output "${value}"
    done
}

@test "launch_code_server.sh --background hands code-server the same NODE_OPTIONS" {
    # The background path starts code-server under nohup with output discarded,
    # so wait (up to 5 s) for the fake to write what it inherited.
    _fake_code_server
    run env NODE_OPTIONS="--max-old-space-size=4096" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_code_server.sh" "${TEST_DIR}" --port 1 --background
    assert_success
    assert_output --partial "Server started in background"
    local i=0
    while [ ! -s "${TEST_DIR}/node_options.log" ] && [ "${i}" -lt 50 ]; do
        sleep 0.1
        i=$((i + 1))
    done
    run cat "${TEST_DIR}/node_options.log"
    assert_output "--max-old-space-size=4096 --use-openssl-ca"
}

@test "launch_code_server.sh exports NODE_OPTIONS before both code-server launch lines" {
    local export_line launch_lines line
    export_line="$(grep -n '^export NODE_OPTIONS$' "${REPO_ROOT}/scripts/launch_code_server.sh" | cut -d: -f1)"
    [ -n "${export_line}" ]
    launch_lines="$(grep -n -E '^[[:space:]]*(exec |nohup )code-server' "${REPO_ROOT}/scripts/launch_code_server.sh" | cut -d: -f1)"
    [ "$(printf '%s\n' "${launch_lines}" | wc -l)" -eq 2 ]
    for line in ${launch_lines}; do
        [ "${export_line}" -lt "${line}" ]
    done
}

@test "launch_code_server.sh leaves the password logic unchanged" {
    run grep -F 'PASSWORD="${PASSWORD:-daaf}"' "${REPO_ROOT}/scripts/launch_code_server.sh"
    assert_success
}
