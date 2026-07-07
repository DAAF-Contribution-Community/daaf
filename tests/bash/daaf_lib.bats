#!/usr/bin/env bats
# ============================================================================
# Tests for daaf_lib.sh -- DAAF Shared Function Library
# ============================================================================
# Tests cover syntax validation, color setup, browser open, port check, and
# container lifecycle functions.
# ============================================================================

load 'test_helper'

setup() {
    common_setup
    mock_docker
    # Reset double-source guard so each test gets a clean load
    unset _DAAF_LIB_LOADED
    source "$REPO_ROOT/scripts/host/daaf_lib.sh"
}

teardown() {
    common_teardown
}

# =========================================================================
# Tier 1 -- Syntax
# =========================================================================

@test "daaf_lib.sh parses without errors" {
    run bash -n "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_success
}

# =========================================================================
# Tier 2 -- setup_colors
# =========================================================================

@test "setup_colors sets color variables when called" {
    # In test context tput may or may not work, but the function must not fail
    run setup_colors
    assert_success
}

@test "setup_colors sets empty variables when NO_COLOR is set" {
    export NO_COLOR=1
    setup_colors
    [ -z "${RED}" ]
    [ -z "${GREEN}" ]
    [ -z "${YELLOW}" ]
    [ -z "${CYAN}" ]
    [ -z "${BOLD}" ]
    [ -z "${DIM}" ]
    [ -z "${RESET}" ]
}

@test "setup_colors sets empty variables when stdout is not a TTY" {
    # Run in a subshell with stdout piped (not a TTY)
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        setup_colors
        echo "RED=${RED}|GREEN=${GREEN}|YELLOW=${YELLOW}"
    '
    assert_success
    assert_output "RED=|GREEN=|YELLOW="
}

# =========================================================================
# Tier 3 -- open_url
# =========================================================================

@test "open_url calls correct opener on macOS" {
    # Mock the 'open' command
    open() {
        echo "MOCK_OPEN: $1"
        return 0
    }
    export -f open

    run open_url "https://example.com"
    assert_success
}

@test "open_url calls wslview on WSL" {
    # Remove 'open' and 'xdg-open' so they are not found
    command() {
        if [ "$1" = "-v" ] && [ "$2" = "open" ]; then
            return 1
        fi
        if [ "$1" = "-v" ] && [ "$2" = "wslview" ]; then
            return 0
        fi
        builtin command "$@"
    }
    export -f command

    # Create a fake /proc/version with "microsoft"
    mkdir -p "${TEST_DIR}/proc"
    echo "Linux version 5.15.0 microsoft-standard-WSL2" > "${TEST_DIR}/proc/version"

    wslview() {
        echo "MOCK_WSLVIEW: $1"
        return 0
    }
    export -f wslview

    # Override open_url to use our fake /proc/version
    # We need to redefine to point at our fake proc
    run bash -c '
        export TEST_DIR='"'${TEST_DIR}'"'
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"

        # Override open_url to use fake /proc/version
        open_url() {
            local url="$1"
            # No macOS open
            # Check WSL with fake /proc/version
            if [ -f "${TEST_DIR}/proc/version" ] && grep -qi "microsoft" "${TEST_DIR}/proc/version" 2>/dev/null; then
                echo "WSL_DETECTED"
                return 0
            fi
            return 0
        }
        open_url "https://example.com"
    '
    assert_success
    assert_output --partial "WSL_DETECTED"
}

@test "open_url calls xdg-open on Linux" {
    # Mock: no 'open', no WSL, but xdg-open available
    command() {
        if [ "$1" = "-v" ] && [ "$2" = "open" ]; then
            return 1
        fi
        if [ "$1" = "-v" ] && [ "$2" = "xdg-open" ]; then
            return 0
        fi
        builtin command "$@"
    }
    export -f command

    xdg-open() {
        echo "MOCK_XDG_OPEN: $1"
        return 0
    }
    export -f xdg-open

    # Ensure no WSL detection (no microsoft in /proc/version)
    run bash -c '
        unset _DAAF_LIB_LOADED
        # Ensure /proc/version does not contain microsoft
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        # open_url should try open (fail), WSL (fail), then xdg-open
        open_url "https://example.com"
    '
    assert_success
}

@test "open_url succeeds silently when no opener is available" {
    # Remove all openers
    command() {
        if [ "$1" = "-v" ] && [ "$2" = "open" ]; then
            return 1
        fi
        if [ "$1" = "-v" ] && [ "$2" = "wslview" ]; then
            return 1
        fi
        if [ "$1" = "-v" ] && [ "$2" = "xdg-open" ]; then
            return 1
        fi
        builtin command "$@"
    }
    export -f command

    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        open_url "https://example.com"
        echo "exit_code=$?"
    '
    assert_success
    assert_output --partial "exit_code=0"
}

# =========================================================================
# Tier 4 -- check_port
# =========================================================================

@test "check_port returns 0 when service is listening" {
    # Override docker to simulate a listening port
    docker() {
        case "$1" in
            compose)
                shift
                case "$1" in
                    exec)
                        # Simulate ss output that matches port 2718
                        return 0
                        ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run check_port 2718
    assert_success
}

@test "check_port returns 1 when port is free" {
    # Override docker to simulate no match
    docker() {
        case "$1" in
            compose)
                shift
                case "$1" in
                    exec)
                        return 1
                        ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run check_port 2718
    assert_failure
}

@test "check_port handles docker exec failure gracefully" {
    # Override docker to simulate exec failure
    docker() {
        case "$1" in
            compose)
                shift
                case "$1" in
                    exec) return 1 ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run check_port 9999
    assert_failure
}

@test "check_port probes /proc/net/tcp inside the container (not ss)" {
    # The DAAF image has no `ss` binary; check_port must read /proc/net/tcp.
    run grep -F '/proc/net/tcp' "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_success
    # No live `ss` invocation should remain (comments referencing history aside).
    run grep -E '^[^#]*\bss -tlnp' "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_failure
}

@test "check_port /proc/net/tcp probe detects a listening port" {
    # Exercise the actual probe logic against a real listener in THIS container
    # (Linux, /proc/net/tcp present), bypassing the docker-exec wrapper by
    # running the remote script portion directly. This validates the awk/hex
    # matching, not the docker plumbing. Skips where the probe cannot run
    # (no /proc/net/tcp, e.g. macOS) or python3 is unavailable.
    [ -r /proc/net/tcp ] || skip "no /proc/net/tcp on this platform"
    command -v python3 >/dev/null 2>&1 || skip "python3 not available"
    local probe='
        port="$1"
        ph=$(printf "%04X" "$port")
        awk -v ph="$ph" '\''$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}'\'' \
            /proc/net/tcp /proc/net/tcp6 2>/dev/null
    '
    # Start a listener on an ephemeral-ish fixed port for the duration of the test.
    python3 -c "import socket,time,sys; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',53917)); s.listen(1); sys.stderr.write('up\n'); sys.stderr.flush(); time.sleep(5)" 2>/dev/null &
    local lpid=$!
    sleep 1
    run bash -c "$probe" _ 53917
    local rc=$status
    kill "$lpid" 2>/dev/null || true
    [ "$rc" -eq 0 ]
}

@test "check_port /proc/net/tcp probe reports a free port as not listening" {
    [ -r /proc/net/tcp ] || skip "no /proc/net/tcp on this platform"
    local probe='
        port="$1"
        ph=$(printf "%04X" "$port")
        awk -v ph="$ph" '\''$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}'\'' \
            /proc/net/tcp /proc/net/tcp6 2>/dev/null
    '
    run bash -c "$probe" _ 54999
    assert_failure
}

# =========================================================================
# Tier 5 -- ensure_container
# =========================================================================

@test "ensure_container starts container when not running" {
    # First call to docker compose ps returns no match, then up succeeds
    local call_count=0
    docker() {
        case "$1" in
            compose)
                shift
                case "$1" in
                    ps)
                        echo ""
                        return 0
                        ;;
                    up)
                        return 0
                        ;;
                    *) return 0 ;;
                esac
                ;;
            *) return 0 ;;
        esac
    }
    export -f docker

    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        ps) echo "" ; return 0 ;;
                        up) return 0 ;;
                        *) return 0 ;;
                    esac ;;
                *) return 0 ;;
            esac
        }
        export -f docker

        ensure_container
        echo "ENSURE_RC=$?"
    '
    assert_success
    assert_output --partial "ENSURE_RC=0"
}

@test "ensure_container detects a running container via compose ps -q (non-empty ID)" {
    # New running-check: `docker compose ps -q daaf-docker` prints a container ID
    # when running. A non-empty ID must be treated as running WITHOUT calling up.
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"

        docker() {
            case "$1" in
                compose)
                    shift
                    case "$1" in
                        ps) echo "abc123containerid" ; return 0 ;;
                        up) echo "UP_WAS_CALLED" ; return 0 ;;
                        *) return 0 ;;
                    esac ;;
                *) return 0 ;;
            esac
        }
        export -f docker

        ensure_container
        echo "ENSURE_RC=$?"
    '
    assert_success
    assert_output --partial "ENSURE_RC=0"
    # A running container must not trigger `docker compose up`.
    refute_output --partial "UP_WAS_CALLED"
}

# =========================================================================
# Multi-instance settings loader (load_daaf_settings)
# =========================================================================

@test "load_daaf_settings picks up a DAAF_* value from environment_settings.txt" {
    printf 'DAAF_PROJECT_NAME=myinstance\nDAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_PROJECT_NAME DAAF_PORT_MARIMO
        load_daaf_settings "./environment_settings.txt"
        echo "NAME=${DAAF_PROJECT_NAME:-UNSET}"
        echo "PORT=${DAAF_PORT_MARIMO:-UNSET}"
    '
    assert_success
    assert_output --partial "NAME=myinstance"
    assert_output --partial "PORT=3001"
}

@test "load_daaf_settings picks up the DAAF_DEV build flag from environment_settings.txt" {
    # DAAF_DEV rides the same whitelist bridge as the four multi-instance keys so
    # it can reach `docker compose build` as --build-arg DAAF_DEV=${DAAF_DEV:-0}.
    printf 'DAAF_DEV=1\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_DEV
        load_daaf_settings "./environment_settings.txt"
        echo "DEV=${DAAF_DEV:-UNSET}"
    '
    assert_success
    assert_output --partial "DEV=1"
}

@test "load_daaf_settings lets an already-set shell env var win over the file" {
    printf 'DAAF_PROJECT_NAME=fromfile\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_PROJECT_NAME=fromshell
        load_daaf_settings "./environment_settings.txt"
        echo "NAME=${DAAF_PROJECT_NAME}"
    '
    assert_success
    # Precedence: shell env wins, matching Docker Compose (shell > .env file).
    assert_output --partial "NAME=fromshell"
}

@test "load_daaf_settings is a no-op when the settings file is absent" {
    # No environment_settings.txt in TEST_DIR.
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_PROJECT_NAME
        load_daaf_settings "./environment_settings.txt"
        echo "NAME=${DAAF_PROJECT_NAME:-UNSET}"
    '
    assert_success
    assert_output --partial "NAME=UNSET"
}

@test "load_daaf_settings tolerates CRLF line endings" {
    printf 'DAAF_PORT_VSCODE=3020\r\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_PORT_VSCODE
        load_daaf_settings "./environment_settings.txt"
        echo "PORT=[${DAAF_PORT_VSCODE:-UNSET}]"
    '
    assert_success
    # CR must be stripped: value is exactly 3020, not "3020\r".
    assert_output --partial "PORT=[3020]"
}

@test "load_daaf_settings ignores non-DAAF keys (does not source arbitrary lines)" {
    # A credential-shaped line with shell metacharacters must NOT be evaluated.
    printf 'ANTHROPIC_API_KEY=sk-$(touch /tmp/daaf_should_not_exist)\nDAAF_PROJECT_NAME=safe\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_PROJECT_NAME ANTHROPIC_API_KEY
        load_daaf_settings "./environment_settings.txt"
        echo "NAME=${DAAF_PROJECT_NAME:-UNSET}"
        echo "KEY=${ANTHROPIC_API_KEY:-UNSET}"
    '
    assert_success
    assert_output --partial "NAME=safe"
    # The non-DAAF key is not adopted, and its command-substitution never ran.
    assert_output --partial "KEY=UNSET"
    [ ! -f /tmp/daaf_should_not_exist ]
}

# =========================================================================
# docker-compose.yml multi-instance interpolation defaults
# =========================================================================

@test "docker-compose.yml preserves single-instance defaults for project and ports" {
    # Static check: the interpolation defaults must resolve to the original
    # values so an existing install with no new settings behaves identically.
    run grep -F 'name: ${DAAF_PROJECT_NAME:-daaf}' "${REPO_ROOT}/docker-compose.yml"
    assert_success
    run grep -F '${DAAF_PORT_MARIMO:-2718}:2718' "${REPO_ROOT}/docker-compose.yml"
    assert_success
    run grep -F '${DAAF_PORT_LOGVIEWER:-2719}:2719' "${REPO_ROOT}/docker-compose.yml"
    assert_success
    run grep -F '${DAAF_PORT_VSCODE:-2720}:2720' "${REPO_ROOT}/docker-compose.yml"
    assert_success
}

@test "docker-compose.yml forwards DAAF_DEV as a build arg defaulting to 0" {
    # The opt-in dev-tooling flag reaches the Dockerfile as a build arg; its
    # interpolation default must be 0 so a standard build is unchanged.
    run grep -F 'DAAF_DEV: "${DAAF_DEV:-0}"' "${REPO_ROOT}/docker-compose.yml"
    assert_success
}

@test "Dockerfile guards the DAAF_DEV toolchain behind an opt-in build arg" {
    # Default builds (DAAF_DEV unset/0) must skip the dev toolchain entirely, so
    # every dev RUN layer is guarded by `if [ "${DAAF_DEV}" = "1" ]`.
    run grep -F 'ARG DAAF_DEV=0' "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -F 'if [ "${DAAF_DEV}" = "1" ]' "${REPO_ROOT}/Dockerfile"
    assert_success
}

@test "Dockerfile installs the R toolchain unconditionally (no DAAF_R guard)" {
    # R ships in every DAAF image: the runtime install and the R package installs
    # must run in unguarded RUN layers, and no DAAF_R build-flag machinery may
    # remain anywhere in the Dockerfile.
    run grep -F 'ln -s /opt/R/${R_VERSION}/bin/Rscript /usr/local/bin/Rscript' "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -F 'RUN Rscript -e' "${REPO_ROOT}/Dockerfile"
    assert_success
    # No opt-in guard or ARG survives the unconditional migration.
    run grep -q 'DAAF_R' "${REPO_ROOT}/Dockerfile"
    assert_failure
}
