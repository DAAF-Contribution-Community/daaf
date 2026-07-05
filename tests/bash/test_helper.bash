#!/usr/bin/env bash
# ============================================================================
# BATS Test Helper -- shared setup for all DAAF shell script tests
# ============================================================================
# Source this from every .bats file via:  load 'test_helper'
#
# Provides:
#   - common_setup / common_teardown (temp dir lifecycle)
#   - mock_docker (function-override Docker mock)
#   - create_fake_compose_file (minimal docker-compose.yml in TEST_DIR)
#   - assert_success / assert_failure / assert_output helpers via bats-assert
# ============================================================================

# --- Load bats helper libraries (if available) ---
# CI installs these via bats-core/bats-action; local runs may use submodules.
# If not available, provide minimal fallback assertions.
_BATS_HELPERS_LOADED=false
for _lib_root in \
    "${BATS_TEST_DIRNAME}/../libs" \
    "${BATS_TEST_DIRNAME}/../../test/libs" \
    "/usr/lib/bats"; do
    if [ -f "${_lib_root}/bats-support/load.bash" ]; then
        load "${_lib_root}/bats-support/load"
        load "${_lib_root}/bats-assert/load"
        _BATS_HELPERS_LOADED=true
        break
    fi
done

if [ "${_BATS_HELPERS_LOADED}" != "true" ]; then
    # Minimal fallback assertions when bats-assert is not installed
    assert_success() {
        if [ "${status}" -ne 0 ]; then
            echo "assert_success failed: status=${status}"
            echo "output: ${output}"
            return 1
        fi
    }
    assert_failure() {
        if [ "${status}" -eq 0 ]; then
            echo "assert_failure failed: expected non-zero exit"
            echo "output: ${output}"
            return 1
        fi
    }
    assert_output() {
        if [ "$1" = "--partial" ]; then
            shift
            if [[ "${output}" != *"$1"* ]]; then
                echo "assert_output --partial failed"
                echo "expected to contain: $1"
                echo "actual output: ${output}"
                return 1
            fi
        else
            if [ "${output}" != "$1" ]; then
                echo "assert_output failed"
                echo "expected: $1"
                echo "actual: ${output}"
                return 1
            fi
        fi
    }
    refute_output() {
        if [ "$1" = "--partial" ]; then
            shift
            if [[ "${output}" == *"$1"* ]]; then
                echo "refute_output --partial failed"
                echo "expected NOT to contain: $1"
                echo "actual output: ${output}"
                return 1
            fi
        fi
    }
fi

# ============================================================================
# Common setup / teardown
# ============================================================================

# Path to the repository root (parent of tests/bash/)
REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"

common_setup() {
    TEST_DIR="$(mktemp -d)"
    ORIGINAL_DIR="$(pwd)"
    cd "${TEST_DIR}" || return 1
    export TEST_DIR ORIGINAL_DIR REPO_ROOT
}

common_teardown() {
    cd "${ORIGINAL_DIR}" || true
    rm -rf "${TEST_DIR}"
}

# ============================================================================
# Docker mock (Strategy 1 -- function override)
# ============================================================================
# After calling mock_docker, any `docker` invocation in the script under test
# is intercepted. Control behavior via MOCK_DOCKER_* variables.
#
# Usage in tests:
#   setup() { common_setup; mock_docker; }
#   @test "..." { MOCK_DOCKER_INFO_EXIT=1; run bash "$REPO_ROOT/script.sh"; ... }

mock_docker() {
    DOCKER_CALLS=()
    export MOCK_DOCKER_EXIT=0
    export MOCK_DOCKER_INFO_EXIT=0
    export MOCK_DOCKER_COMPOSE_EXIT=0
    export MOCK_DOCKER_EXEC_EXIT=0
    export MOCK_DOCKER_EXEC_OUTPUT=""
    export MOCK_DOCKER_CP_EXIT=0
    export MOCK_DOCKER_VOLUME_EXIT=0
    export MOCK_DOCKER_PS_OUTPUT=""
    export MOCK_DOCKER_RUN_EXIT=0
    export MOCK_DOCKER_RUN_OUTPUT=""
    export MOCK_DOCKER_INSPECT_EXIT=0
    export MOCK_DOCKER_INSPECT_OUTPUT=""
    export MOCK_DOCKER_START_EXIT=0
    # `docker compose ps -q`/`-aq daaf-docker` returns a container ID (empty when
    # the container is not running / does not exist). By default this MIRRORS
    # MOCK_DOCKER_PS_OUTPUT so existing tests that model running/stopped purely via
    # MOCK_DOCKER_PS_OUTPUT ("" = stopped, "daaf-docker" = running) keep working
    # unchanged under the new `ps -q` running-check. Set MOCK_DOCKER_PSQ_OUTPUT
    # explicitly only when a test must distinguish the ID form from the --format
    # form (e.g., "stopped but exists" for rebuild's `-aq`).
    export MOCK_DOCKER_PSQ_OUTPUT="__MIRROR_PS__"

    docker() {
        DOCKER_CALLS+=("$*")
        case "$1" in
            info)
                return "${MOCK_DOCKER_INFO_EXIT:-0}"
                ;;
            compose)
                shift
                case "$1" in
                    ps)
                        # Distinguish the ID-emitting `ps -q`/`ps -aq` form (used
                        # by the running-check and cp-target derivation) from the
                        # `ps --status running --format` form.
                        case "$*" in
                            *-q*|*-aq*)
                                if [ "${MOCK_DOCKER_PSQ_OUTPUT:-__MIRROR_PS__}" = "__MIRROR_PS__" ]; then
                                    echo "${MOCK_DOCKER_PS_OUTPUT:-}"
                                else
                                    echo "${MOCK_DOCKER_PSQ_OUTPUT:-}"
                                fi
                                ;;
                            *)
                                echo "${MOCK_DOCKER_PS_OUTPUT:-}"
                                ;;
                        esac
                        return "${MOCK_DOCKER_COMPOSE_EXIT:-0}"
                        ;;
                    exec)
                        echo "${MOCK_DOCKER_EXEC_OUTPUT:-}"
                        return "${MOCK_DOCKER_EXEC_EXIT:-0}"
                        ;;
                    up|build)
                        return "${MOCK_DOCKER_COMPOSE_EXIT:-0}"
                        ;;
                    *)
                        return "${MOCK_DOCKER_COMPOSE_EXIT:-0}"
                        ;;
                esac
                ;;
            cp)
                return "${MOCK_DOCKER_CP_EXIT:-0}"
                ;;
            volume)
                return "${MOCK_DOCKER_VOLUME_EXIT:-0}"
                ;;
            run)
                echo "${MOCK_DOCKER_RUN_OUTPUT:-}"
                return "${MOCK_DOCKER_RUN_EXIT:-0}"
                ;;
            inspect)
                echo "${MOCK_DOCKER_INSPECT_OUTPUT:-}"
                return "${MOCK_DOCKER_INSPECT_EXIT:-0}"
                ;;
            start)
                return "${MOCK_DOCKER_START_EXIT:-0}"
                ;;
            exec)
                echo "${MOCK_DOCKER_EXEC_OUTPUT:-}"
                return "${MOCK_DOCKER_EXEC_EXIT:-0}"
                ;;
            ps)
                echo "${MOCK_DOCKER_PS_OUTPUT:-}"
                return 0
                ;;
            *)
                return "${MOCK_DOCKER_EXIT:-0}"
                ;;
        esac
    }
    export -f docker
}

# ============================================================================
# Mock for `command -v docker` preflight checks
# ============================================================================
# Some scripts use `command -v docker` to check Docker is installed.
# Call mock_no_docker to make that check fail.

mock_no_docker() {
    # Override command builtin to fail for docker
    command() {
        if [ "$1" = "-v" ] && [ "$2" = "docker" ]; then
            return 1
        fi
        builtin command "$@"
    }
    export -f command
}

# ============================================================================
# Fake docker-compose.yml
# ============================================================================

create_fake_compose_file() {
    local target_dir="${1:-${TEST_DIR}}"
    cat > "${target_dir}/docker-compose.yml" <<'YAML'
name: daaf
services:
  daaf-docker:
    image: daaf:latest
    volumes:
      - daaf-data:/daaf
      - daaf-claude-config:/home/appuser/.claude
    environment:
      - CLAUDE_CONFIG_DIR=/home/appuser/.claude
volumes:
  daaf-data:
  daaf-claude-config:
YAML
}

# ============================================================================
# Mock for curl (used by install.sh and migrate_daaf.sh)
# ============================================================================

mock_curl() {
    export MOCK_CURL_EXIT=0
    curl() {
        # By default, create an empty file at the -o destination
        local outfile=""
        local args=("$@")
        for ((i=0; i<${#args[@]}; i++)); do
            if [ "${args[$i]}" = "-o" ]; then
                outfile="${args[$((i+1))]}"
                break
            fi
        done
        if [ -n "${outfile}" ]; then
            touch "${outfile}"
        fi
        return "${MOCK_CURL_EXIT:-0}"
    }
    export -f curl
}

# ============================================================================
# Mocks for daaf_lib.sh functions
# ============================================================================

mock_open_url() {
    OPENED_URLS=()
    open_url() {
        OPENED_URLS+=("$1")
        return 0
    }
    export -f open_url
}

mock_port_check() {
    export DAAF_MOCK_PORTS="${1:-}"
    check_port() {
        local port="$1"
        if echo "${DAAF_MOCK_PORTS}" | grep -q "${port}:yes"; then
            return 0
        fi
        return 1
    }
    export -f check_port
}
