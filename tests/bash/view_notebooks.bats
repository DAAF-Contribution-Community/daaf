#!/usr/bin/env bats
# ============================================================================
# Tests for view_notebooks.sh -- DAAF Notebook Browser
# and for the container-side launcher it calls, scripts/launch_marimo.sh
# ============================================================================
# Thin wrapper script -- tests focus on preflight checks, container lifecycle,
# dry-run behavior, and structural markers. The last section tests
# launch_marimo.sh (token file, --print-token) behaviourally with a fake marimo.
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

@test "view_notebooks.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
}

# =========================================================================
# Tier 2 -- Preflight checks
# =========================================================================

# --- Preflight: missing docker-compose.yml ---

@test "view_notebooks.sh fails when docker-compose.yml is missing" {
    rm -f docker-compose.yml
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "docker-compose.yml"
}

# --- Preflight: missing Docker ---

@test "view_notebooks.sh fails when docker command is not found" {
    mock_no_docker
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker"
}

# --- Preflight: Docker daemon not running ---

@test "view_notebooks.sh fails when Docker daemon is not running" {
    MOCK_DOCKER_INFO_EXIT=1
    export DAAF_NESTED=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Docker Desktop"
}

# --- DAAF_NESTED behavior ---

@test "view_notebooks.sh suppresses pause trap when DAAF_NESTED=1" {
    export DAAF_NESTED=1
    MOCK_DOCKER_INFO_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    refute_output --partial "Press Enter"
}

# --- Preflight: unreadable environment_settings.txt ---

@test "view_notebooks.sh exits with a permissions message when environment_settings.txt is unreadable" {
    # The loader's open check is silent, so the script must name the file and
    # the fix itself rather than exit 1 with no output (a dry run otherwise
    # succeeds, so exit 1 here means the settings load stopped it).
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    if [ -r "${TEST_DIR}/environment_settings.txt" ]; then
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" </dev/null
    assert_failure 1
    assert_output --partial "ERROR: Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it."
    assert_output --partial "Fix that (or move the file aside), then run view_notebooks.sh again."
    refute_output --partial "Permission denied"
    refute_output --partial "Press Enter"
}

# =========================================================================
# Tier 3 -- Script structure
# =========================================================================

@test "view_notebooks.sh includes set -euo pipefail" {
    run grep -c "set -euo pipefail" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh checks for docker-compose.yml" {
    run grep -c "docker-compose.yml" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh checks command -v docker" {
    run grep -c "command -v docker" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh checks docker info" {
    run grep -c "docker info" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh references launch_marimo.sh" {
    run grep -c "launch_marimo.sh" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh mentions Notebook Browser in output" {
    run grep -c "Notebook Browser" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh supports DAAF_TEST_MODE guard" {
    run grep -c "DAAF_TEST_MODE" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh supports DAAF_DRY_RUN" {
    run grep -c "DAAF_DRY_RUN" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

# =========================================================================
# Tier 4 -- Behavioral (DAAF_TEST_MODE)
# =========================================================================

@test "view_notebooks.sh exits cleanly when sourced with DAAF_TEST_MODE=1" {
    export DAAF_TEST_MODE=1
    run bash -c "source '${REPO_ROOT}/scripts/host/view_notebooks.sh'"
    assert_success
}

# =========================================================================
# Tier 5 -- Dry-run
# =========================================================================

@test "view_notebooks.sh: dry-run completes successfully" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
}

@test "view_notebooks.sh: dry-run completes without real Docker" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
    assert_output --partial "Notebook Browser"
}

@test "view_notebooks.sh: dry-run shows Notebook Browser message" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" 2>&1
    assert_success
    assert_output --partial "Notebook Browser"
}

@test "view_notebooks.sh: dry-run reports container running" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh" 2>&1
    assert_success
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Tier 6 -- Error paths
# =========================================================================

# --- Container not running → start attempt ---

@test "view_notebooks.sh attempts to start container when not running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=0
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_output --partial "Starting DAAF container"
}

# --- Container start fails ---

@test "view_notebooks.sh fails when container start fails" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT=""
    MOCK_DOCKER_COMPOSE_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_failure
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start the container"
}

# --- Notebook browser launch fails ---

@test "view_notebooks.sh reports error when notebook browser fails to start" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=1
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_output --partial "ERROR"
    assert_output --partial "Failed to start the notebook browser"
}

# --- Container already running ---

@test "view_notebooks.sh reports container already running" {
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_EXIT=0
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_output --partial "DAAF container is running"
}

# =========================================================================
# Browser auto-open (open_url integration)
# =========================================================================

@test "view_notebooks.sh sources daaf_lib.sh when present" {
    run grep -c "source.*daaf_lib.sh" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ "${output}" -ge 1 ]
}

@test "view_notebooks.sh calls open_url with the host notebook port (default 2718)" {
    # The URL uses the overridable host port var (defaults to 2718). Assert the
    # parameterized form plus the default resolution.
    run grep 'open_url.*DAAF_PORT_MARIMO' "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    assert_output --partial 'http://localhost:${DAAF_PORT_MARIMO}/?access_token=${MARIMO_TOKEN}'
    run grep 'DAAF_PORT_MARIMO:-2718' "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
}

@test "view_notebooks.sh guards open_url behind command -v check" {
    # Verify the script uses a guard pattern so open_url is only called
    # when the function is actually available (backwards compatible when
    # daaf_lib.sh is absent).
    run grep "command -v open_url" "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    assert_output --partial "open_url"
}

@test "view_notebooks.sh dry-run completes with library sourcing" {
    # With daaf_lib.sh present, open_url is a no-op in dry-run mode.
    # Confirms the full script (including library sourcing) works end-to-end.
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    assert_output --partial "Notebook Browser"
}

# =========================================================================
# Access token (marimo runs with a per-launch token, not --no-token)
# =========================================================================

# Fake browser openers that log the URL they were given. open_url (daaf_lib.sh)
# tries open, then wslview (WSL), then xdg-open, so all three are faked; the
# fake bin dir goes first on PATH so no real browser is ever launched.
_fake_openers() {
    mkdir -p "${TEST_DIR}/bin"
    local name
    for name in open wslview xdg-open; do
        printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$1" >> "%s/opened.log"\n' "${TEST_DIR}" > "${TEST_DIR}/bin/${name}"
        chmod +x "${TEST_DIR}/bin/${name}"
    done
    export PATH="${TEST_DIR}/bin:${PATH}"
}

@test "view_notebooks.sh asks the running server for its token with launch_marimo.sh --print-token (no TTY)" {
    run grep -F 'docker compose exec -T daaf-docker bash /daaf/scripts/launch_marimo.sh --print-token' "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
}

@test "view_notebooks.sh opens the tokenized URL on the HOST-published port" {
    _fake_openers
    export DAAF_NESTED=1
    export DAAF_PORT_MARIMO=3001
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_OUTPUT="feedc0de42"
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    assert_output --partial "Opening the notebook browser in your default browser"
    run cat "${TEST_DIR}/opened.log"
    assert_success
    assert_output "http://localhost:3001/?access_token=feedc0de42"
}

@test "view_notebooks.sh opens nothing when --print-token fails (e.g. an older --no-token server, exit 5)" {
    _fake_openers
    export DAAF_NESTED=1
    docker() {
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
        case "$*" in
            info) return 0 ;;
            *"compose ps -q daaf-docker"*) echo "abc123" ;;
            *"--print-token"*) echo "ERROR: started without an access token" >&2; return 5 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    refute_output --partial "Opening the notebook browser in your default browser"
    [ ! -e "${TEST_DIR}/opened.log" ]
}

@test "view_notebooks.sh opens nothing when the token is malformed" {
    # The token is pasted into a URL, so anything outside [A-Za-z0-9_-] is refused.
    _fake_openers
    export DAAF_NESTED=1
    MOCK_DOCKER_PS_OUTPUT="daaf-docker"
    MOCK_DOCKER_EXEC_OUTPUT='abc&next=//evil.example'
    run bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    [ ! -e "${TEST_DIR}/opened.log" ]
}

@test "view_notebooks.sh: dry-run reaches the tokenized browser open" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_notebooks.sh"
    assert_success
    assert_output --partial "Opening the notebook browser in your default browser"
}

# =========================================================================
# Container-side launcher (launch_marimo.sh)
# =========================================================================

# launch_marimo.sh's own listener probe (/proc/net/tcp, 2718 = 0x0A9E). In a dev
# container with the notebook server running, the fresh-launch tests cannot run.
_skip_if_2718_listening() {
    if awk '$2 ~ ":0A9E$" && $4 == "0A"' /proc/net/tcp /proc/net/tcp6 2>/dev/null | grep -q .; then
        skip "port 2718 is already listening here (a notebook server is running)"
    fi
}

@test "launch_marimo.sh never starts marimo with --no-token" {
    # Every `marimo edit` launch line passes the per-launch token file instead.
    run grep -E '^[[:space:]]*(exec |nohup )?marimo edit' "${REPO_ROOT}/scripts/launch_marimo.sh"
    assert_success
    [ "${#lines[@]}" -eq 2 ]
    local line
    for line in "${lines[@]}"; do
        [[ "${line}" == *'--token-password-file "$TOKEN_FILE"'* ]]
        [[ "${line}" != *"--no-token"* ]]
    done
}

@test "launch_marimo.sh keeps the token file outside /daaf" {
    run grep -F 'TOKEN_DIR="${HOME:?HOME is not set}/.local/state/daaf"' "${REPO_ROOT}/scripts/launch_marimo.sh"
    assert_success
}

@test "launch_marimo.sh writes a private 256-bit token and prints the tokenized URL" {
    # A fake marimo records its argv, so the launch runs without a real server.
    # The default port 2718 is used so DAAF_PORT_MARIMO's display remap applies;
    # a real server already listening there would take the already-running path.
    _skip_if_2718_listening
    mkdir -p "${TEST_DIR}/bin" "${TEST_DIR}/browse"
    printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$*" > "%s/marimo_args.log"\n' "${TEST_DIR}" > "${TEST_DIR}/bin/marimo"
    chmod +x "${TEST_DIR}/bin/marimo"
    run env HOME="${TEST_DIR}/home" PATH="${TEST_DIR}/bin:${PATH}" DAAF_PORT_MARIMO=3001 \
        bash "${REPO_ROOT}/scripts/launch_marimo.sh" "${TEST_DIR}/browse"
    assert_success
    local token_file="${TEST_DIR}/home/.local/state/daaf/marimo-token-2718"
    [ -f "${token_file}" ]
    local token
    token="$(cat "${token_file}")"
    [[ "${token}" =~ ^[0-9a-f]{64}$ ]]
    [ "$(stat -c %a "${token_file}")" = "600" ]
    [ "$(stat -c %a "${TEST_DIR}/home/.local/state/daaf")" = "700" ]
    # Display port follows DAAF_PORT_MARIMO (host remap); the server binds 2718.
    assert_output --partial "http://localhost:3001/?access_token=${token}"
    run cat "${TEST_DIR}/marimo_args.log"
    assert_output --partial "--port 2718 --token-password-file ${token_file}"
    refute_output --partial "--no-token"
    refute_output --partial "${token}"
}

@test "launch_marimo.sh writes a new token on every launch" {
    _skip_if_2718_listening
    mkdir -p "${TEST_DIR}/bin" "${TEST_DIR}/browse"
    printf '#!/usr/bin/env bash\nexit 0\n' > "${TEST_DIR}/bin/marimo"
    chmod +x "${TEST_DIR}/bin/marimo"
    local token_file="${TEST_DIR}/home/.local/state/daaf/marimo-token-2718"
    run env HOME="${TEST_DIR}/home" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_marimo.sh" "${TEST_DIR}/browse"
    assert_success
    local first
    first="$(cat "${token_file}")"
    run env HOME="${TEST_DIR}/home" PATH="${TEST_DIR}/bin:${PATH}" bash "${REPO_ROOT}/scripts/launch_marimo.sh" "${TEST_DIR}/browse"
    assert_success
    [ "$(cat "${token_file}")" != "${first}" ]
    # The temp file used for the atomic replace never survives.
    run find "${TEST_DIR}/home/.local/state/daaf" -name '.marimo-token-*'
    assert_output ""
}

@test "launch_marimo.sh --print-token exits 4 when no server listens" {
    run env HOME="${TEST_DIR}/home" bash "${REPO_ROOT}/scripts/launch_marimo.sh" --print-token --port 1
    assert_failure 4
    assert_output --partial "No marimo server is listening on port 1"
    assert_output --partial "Fix: start one first"
}

@test "launch_marimo.sh --print-token errors (exits 4, 5, 6) each say how to fix it" {
    # Two-part error messages (shell-scripting skill, error-handling.md): the
    # line right before each of these exits is a "  Fix:" line. Exits 5 and 6
    # need a live marimo server, so they are pinned by text here.
    local code prev
    for code in 4 5 6; do
        prev="$(grep -B1 -E "^[[:space:]]*exit ${code}\$" "${REPO_ROOT}/scripts/launch_marimo.sh" | head -1)"
        [[ "${prev}" == *'echo "  Fix: '* ]]
        [[ "${prev}" == *'>&2' ]]
    done
}

@test "launch_marimo.sh --help documents --print-token and the tokenized link" {
    run bash "${REPO_ROOT}/scripts/launch_marimo.sh" --help
    assert_success
    assert_output --partial "--print-token"
    assert_output --partial "?access_token="
}
