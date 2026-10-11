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
    # The unreadable-settings loader tests chmod the fixture to 000; give it its
    # permissions back so the fixture tree is left in a normal state for removal.
    if [ -e "${TEST_DIR}/environment_settings.txt" ]; then
        chmod 644 "${TEST_DIR}/environment_settings.txt" 2>/dev/null || true
    fi
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

@test "load_daaf_settings rejects a whitespace-padded key (column-0 strict, parity with PS)" {
    # A leading-space "  DAAF_PROJECT_NAME=..." line is not flush at column 0, so the
    # column-0 `case` glob rejects it. This is the conformance anchor the PowerShell
    # loaders were fixed to match (PS now extracts the key WITHOUT .Trim()), so a padded
    # key resolves to nothing on BOTH platforms rather than silently working on one.
    printf '  DAAF_PROJECT_NAME=padded\n' > "${TEST_DIR}/environment_settings.txt"
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

@test "load_daaf_settings returns non-zero on an unreadable file and adopts nothing" {
    # An existing file that cannot be opened must be a tested failure, not a
    # silent no-op: under `set -e`, a caller's `if ! load_daaf_settings` runs the
    # loader with errexit off, so only an explicit non-zero return reaches it.
    # Nothing is adopted (the read never starts), so the env and tracker are
    # exactly as before the call; an exported value is untouched.
    printf 'DAAF_PROJECT_NAME=fromfile\nDAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    if [ -r "${TEST_DIR}/environment_settings.txt" ]; then
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    run bash -c '
        set -Eeuo pipefail
        trap "echo \"ERR_TRAP: \${BASH_COMMAND}\"" ERR
        unset _DAAF_LIB_LOADED DAAF_PROJECT_NAME DAAF_PORT_MARIMO
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_DEV=7
        if load_daaf_settings "./environment_settings.txt"; then
            echo "RC=0"
        else
            echo "RC=nonzero"
        fi
        echo "NAME=${DAAF_PROJECT_NAME:-UNSET}"
        echo "PORT=${DAAF_PORT_MARIMO:-UNSET}"
        echo "DEV=${DAAF_DEV}"
        echo "TRACKED=[${_DAAF_KEYS_FROM_FILE}]"
    '
    assert_success
    assert_output --partial "RC=nonzero"
    assert_output --partial "NAME=UNSET"
    assert_output --partial "PORT=UNSET"
    assert_output --partial "DEV=7"
    assert_output --partial "TRACKED=[]"
    # Tested in a condition, the failure never reaches the ERR trap.
    refute_output --partial "ERR_TRAP"
    # The open check is silent: the caller prints its own message, so bash's raw
    # redirection error must not appear above it.
    refute_output --partial "Permission denied"
}

@test "load_daaf_settings on an unreadable file returns a status in POSIX mode (POSIXLY_CORRECT)" {
    # The silent open check must use a regular builtin (`true`), not `:`: in
    # POSIX mode a redirection error on a special builtin exits the whole shell
    # silently, so the caller never gets to print its message.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    if [ -r "${TEST_DIR}/environment_settings.txt" ]; then
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    run env POSIXLY_CORRECT=1 bash -c '
        set -Eeuo pipefail
        unset _DAAF_LIB_LOADED DAAF_PORT_MARIMO
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        if load_daaf_settings "./environment_settings.txt"; then
            echo "RC=0"
        else
            echo "RC=nonzero"
        fi
        echo "AFTER_CALL_REACHED"
    '
    assert_success
    assert_output --partial "RC=nonzero"
    assert_output --partial "AFTER_CALL_REACHED"
    refute_output --partial "Permission denied"
}

@test "load_daaf_settings on an unreadable file still stops a plain set -e caller" {
    # A caller that runs the loader unguarded is still ended by the non-zero
    # return under `set -e`. The open check is silent, so such a caller exits
    # without bash's raw "Permission denied" line -- and without any message.
    # That is why every shipped caller tests the result and explains the failure
    # itself (daaf.sh, view_quarto.sh, view_notebooks.sh, view_logs.sh,
    # run_vscode.sh; each suite pins its message).
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    if [ -r "${TEST_DIR}/environment_settings.txt" ]; then
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    run bash -c '
        set -euo pipefail
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        load_daaf_settings "./environment_settings.txt"
        echo "SHOULD_NOT_PRINT"
    '
    assert_failure
    refute_output --partial "Permission denied"
    refute_output --partial "SHOULD_NOT_PRINT"
}

@test "load_daaf_settings silences only the failed open, not later errors" {
    # The 2>/dev/null is scoped to the open check alone. A copy of the library
    # gets one extra stderr line just after that check (a stand-in for any
    # loader bug); it must reach the caller, and the load must still succeed.
    # The source-file seam (sed on a unique source line) does not depend on how
    # `declare -f` formats the body, which differs across bash versions.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    sed 's/^    local key val line$/    local key val line; echo "INJECTED_LOADER_STDERR" >\&2/' \
        "${REPO_ROOT}/scripts/host/daaf_lib.sh" > "${TEST_DIR}/lib_injected.sh"
    [ "$(grep -c 'INJECTED_LOADER_STDERR' "${TEST_DIR}/lib_injected.sh")" -eq 1 ]
    run bash -c '
        set -Eeuo pipefail
        trap "echo \"ERR_TRAP: \${BASH_COMMAND}\"" ERR
        unset _DAAF_LIB_LOADED DAAF_PORT_MARIMO
        source "./lib_injected.sh"
        if load_daaf_settings "./environment_settings.txt"; then
            echo "RC=0"
        else
            echo "RC=nonzero"
        fi
        echo "PORT=${DAAF_PORT_MARIMO:-UNSET}"
    '
    assert_success
    assert_output --partial "INJECTED_LOADER_STDERR"
    assert_output --partial "RC=0"
    assert_output --partial "PORT=3001"
    refute_output --partial "ERR_TRAP"
}

@test "load_daaf_settings does not hide an unbound-variable bug from a guarded caller" {
    # The shape a closing review found hidden: a nounset error inside the loader,
    # called as `if ! load_daaf_settings`. Bash ends the script on it either way;
    # the error text must be visible, and the caller's "cannot read" branch must
    # not run in its place.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    sed 's/^    local key val line$/    local key val line; : "${_DAAF_TEST_INJECTED_UNBOUND}"/' \
        "${REPO_ROOT}/scripts/host/daaf_lib.sh" > "${TEST_DIR}/lib_injected.sh"
    [ "$(grep -c '_DAAF_TEST_INJECTED_UNBOUND' "${TEST_DIR}/lib_injected.sh")" -eq 1 ]
    run bash -c '
        set -Eeuo pipefail
        unset _DAAF_LIB_LOADED _DAAF_TEST_INJECTED_UNBOUND
        source "./lib_injected.sh"
        if ! load_daaf_settings "./environment_settings.txt"; then
            echo "CALLER_SAYS_CANNOT_READ"
        fi
        echo "SHOULD_NOT_PRINT"
    '
    assert_failure
    assert_output --partial "_DAAF_TEST_INJECTED_UNBOUND: unbound variable"
    refute_output --partial "CALLER_SAYS_CANNOT_READ"
    refute_output --partial "SHOULD_NOT_PRINT"
}

# =========================================================================
# Settings provenance + reload (reload_daaf_settings)
# =========================================================================
# load_daaf_settings records which keys it adopted FROM THE FILE in
# _DAAF_KEYS_FROM_FILE; reload_daaf_settings unsets exactly those and reloads,
# so an edited file takes effect while user-exported values keep winning.

@test "reload_daaf_settings picks up a value changed in the file after the first load" {
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED DAAF_PORT_MARIMO
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        load_daaf_settings
        echo "FIRST=${DAAF_PORT_MARIMO}"
        printf "DAAF_PORT_MARIMO=3002\n" > ./environment_settings.txt
        load_daaf_settings
        echo "PLAIN_RELOAD=${DAAF_PORT_MARIMO}"
        reload_daaf_settings
        echo "AFTER_RELOAD=${DAAF_PORT_MARIMO}"
    '
    assert_success
    assert_output --partial "FIRST=3001"
    # A plain second load keeps the first value (already-set wins) -- the reason
    # reload_daaf_settings exists.
    assert_output --partial "PLAIN_RELOAD=3001"
    assert_output --partial "AFTER_RELOAD=3002"
}

@test "reload_daaf_settings keeps a user-exported value winning over the file" {
    printf 'DAAF_PROJECT_NAME=fromfile\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_PROJECT_NAME=fromshell
        load_daaf_settings
        printf "DAAF_PROJECT_NAME=edited\n" > ./environment_settings.txt
        reload_daaf_settings
        echo "NAME=${DAAF_PROJECT_NAME}"
        echo "TRACKED=[${_DAAF_KEYS_FROM_FILE}]"
    '
    assert_success
    assert_output --partial "NAME=fromshell"
    # The user export was never adopted from the file, so it is never recorded.
    assert_output --partial "TRACKED=[]"
}

@test "reload_daaf_settings unsets a key that was removed from the file" {
    printf 'DAAF_PORT_VSCODE=3020\n' > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED DAAF_PORT_VSCODE
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        load_daaf_settings
        printf "# DAAF_PORT_VSCODE removed\n" > ./environment_settings.txt
        reload_daaf_settings
        echo "PORT=${DAAF_PORT_VSCODE:-UNSET}"
    '
    assert_success
    assert_output --partial "PORT=UNSET"
}

@test "load_daaf_settings tracks only file-adopted keys, without duplicates" {
    # DAAF_DEV is pre-exported (not adopted); DAAF_PORT_MARIMO appears twice with an
    # empty first value, so it is adopted twice but must be listed once.
    printf 'DAAF_PROJECT_NAME=inst\nDAAF_PORT_MARIMO=\nDAAF_PORT_MARIMO=3001\nDAAF_DEV=1\n' \
        > "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        unset _DAAF_LIB_LOADED DAAF_PROJECT_NAME DAAF_PORT_MARIMO
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_DEV=0
        load_daaf_settings
        load_daaf_settings
        reload_daaf_settings
        load_daaf_settings
        echo "TRACKED=[${_DAAF_KEYS_FROM_FILE}]"
        echo "PORT=${DAAF_PORT_MARIMO}"
        echo "DEV=${DAAF_DEV}"
    '
    assert_success
    assert_output --partial "TRACKED=[DAAF_PROJECT_NAME DAAF_PORT_MARIMO]"
    assert_output --partial "PORT=3001"
    assert_output --partial "DEV=0"
}

@test "reload_daaf_settings propagates a read failure (tracked keys stay unset)" {
    # The reload unsets the file-adopted keys BEFORE it reads, so on a read
    # failure they stay unset and the tracker stays empty; a user-exported value
    # (never tracked) keeps its value. Callers that must keep their settings
    # snapshot first (daaf.sh handle_restart) -- this test pins what they undo.
    printf 'DAAF_PORT_MARIMO=3001\n' > "${TEST_DIR}/environment_settings.txt"
    chmod 000 "${TEST_DIR}/environment_settings.txt"
    if [ -r "${TEST_DIR}/environment_settings.txt" ]; then
        skip "chmod 000 does not block reads here (running as root?) -- cannot stage an unreadable settings file"
    fi
    chmod 644 "${TEST_DIR}/environment_settings.txt"
    run bash -c '
        set -Eeuo pipefail
        trap "echo \"ERR_TRAP: \${BASH_COMMAND}\"" ERR
        unset _DAAF_LIB_LOADED DAAF_PORT_MARIMO
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_PROJECT_NAME=fromshell
        load_daaf_settings
        echo "BEFORE=${DAAF_PORT_MARIMO} TRACKED=[${_DAAF_KEYS_FROM_FILE}]"
        chmod 000 ./environment_settings.txt
        if reload_daaf_settings; then
            echo "RC=0"
        else
            echo "RC=nonzero"
        fi
        echo "PORT=${DAAF_PORT_MARIMO:-UNSET}"
        echo "NAME=${DAAF_PROJECT_NAME}"
        echo "TRACKED=[${_DAAF_KEYS_FROM_FILE}]"
    '
    assert_success
    assert_output --partial "BEFORE=3001 TRACKED=[DAAF_PORT_MARIMO]"
    assert_output --partial "RC=nonzero"
    assert_output --partial "PORT=UNSET"
    assert_output --partial "NAME=fromshell"
    assert_output --partial "TRACKED=[]"
    refute_output --partial "ERR_TRAP"
}

@test "reload_daaf_settings only ever unsets DAAF_* names (tampered tracker)" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        _DAAF_KEYS_FROM_FILE="HOME DAAF_PORT_MARIMO"
        export DAAF_PORT_MARIMO=1234
        reload_daaf_settings
        echo "HOME_SET=${HOME:+yes}"
        echo "PORT=${DAAF_PORT_MARIMO:-UNSET}"
    '
    assert_success
    assert_output --partial "HOME_SET=yes"
    assert_output --partial "PORT=UNSET"
}

@test "daaf_lib.sh resets the provenance tracker at load (an inherited value is ignored)" {
    run env _DAAF_KEYS_FROM_FILE="DAAF_PROJECT_NAME" bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        echo "TRACKED=[${_DAAF_KEYS_FROM_FILE}]"
    '
    assert_success
    assert_output --partial "TRACKED=[]"
}

# =========================================================================
# Data-volume name resolver (resolve_data_volume_name)
# =========================================================================
# Precedence: DAAF_DATA_VOLUME_NAME (verbatim) > "<project>_daaf-data" default.
# An unset override reproduces the historical hardcoded derivation byte-for-byte.

@test "resolve_data_volume_name derives the default when no override and no project name" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_DATA_VOLUME_NAME DAAF_PROJECT_NAME
        resolve_data_volume_name
    '
    assert_success
    # Unset override + unset project name => the legacy hardcoded name, unchanged.
    assert_output "daaf_daaf-data"
}

@test "resolve_data_volume_name applies the project prefix when only DAAF_PROJECT_NAME is set" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_DATA_VOLUME_NAME
        export DAAF_PROJECT_NAME=daaf2
        resolve_data_volume_name
    '
    assert_success
    # A second instance owns "<project>_daaf-data" without touching the override.
    assert_output "daaf2_daaf-data"
}

@test "resolve_data_volume_name uses DAAF_DATA_VOLUME_NAME verbatim when set (ignores project prefix)" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_DATA_VOLUME_NAME=shared_workspace_vol
        export DAAF_PROJECT_NAME=daaf2
        resolve_data_volume_name
    '
    assert_success
    # Set override wins verbatim -- no project prefix is added (shared-workspace hatch).
    assert_output "shared_workspace_vol"
}

@test "resolve_data_volume_name treats a set-but-empty override as unset (derived default)" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_DATA_VOLUME_NAME=
        unset DAAF_PROJECT_NAME
        resolve_data_volume_name
    '
    assert_success
    # The `:-` default treats empty and unset alike, so it falls through to derived.
    assert_output "daaf_daaf-data"
}

# =========================================================================
# Compose project-name normalization (resolve_project_name) and its copies
# =========================================================================
# Docker Compose normalizes the project name (compose-go NormalizeProjectName:
# lowercase, keep [a-z0-9_-], trim leading '_'/'-'), so `Work` in the settings file
# makes the volume "work_daaf-data". Every host script that derives a Docker name
# from the project must use that same name. The helper lives in daaf_lib.sh; the
# standalone scripts (backup_daaf.sh, restore_from_backup.sh, update_daaf.sh, and the
# maintainer harness test_migration.sh) carry a byte-identical copy, and install.sh
# carries its own two inline lines. The tests below pin all of them to one fixed
# input set.
#
# The scripts that carry an inline copy (word-split on purpose: plain file names).
_PROJECT_NAME_COPIES="backup_daaf.sh restore_from_backup.sh update_daaf.sh test_migration.sh"
#
# The fixed input set: "<printf format of the input><TAB><expected>". Non-ASCII
# inputs are octal escapes so this file stays ASCII: \303\204 is A-umlaut, \342\204\252
# the Kelvin sign U+212A (Go's Unicode lowercasing would keep it as 'k'; every DAAF
# copy drops it, review 45q NIT-1), \304\260 a dotted capital I. An empty expected
# value means the name is refused.
_project_name_cases() {
    printf '%s\t%s\n' \
        'Work' 'work' \
        'work ' 'work' \
        'x # mine' 'xmine' \
        '"x' 'x' \
        '_x' 'x' \
        '-x' 'x' \
        '-_x' 'x' \
        'x.y' 'xy' \
        '\303\204BC' 'bc' \
        '\342\204\252x' 'x' \
        '\304\260x' 'x' \
        '___' '' \
        '@@' '' \
        'daaf' 'daaf' \
        'daaf2' 'daaf2' \
        'My_Proj-1' 'my_proj-1' \
        '--a-b_' 'a-b_'
}

# Run the normalizer defined in the file $1 (which must define resolve_project_name)
# over the fixed input set, printing "OK" or "MISMATCH" per case, then the two
# default cases (unset and empty DAAF_PROJECT_NAME => "daaf").
_run_project_name_cases() {
    local def="$1" fmt want got
    while IFS="$(printf '\t')" read -r fmt want; do
        # `--` so inputs such as "-x" are not read as printf options.
        # shellcheck disable=SC2059  # the case column IS a printf format (octal escapes)
        got="$(DAAF_PROJECT_NAME="$(printf -- "${fmt}")" bash -c 'source "$1"; resolve_project_name' _ "${def}")"
        if [ "${got}" = "${want}" ]; then echo "OK [${fmt}]"; else echo "MISMATCH [${fmt}] want=[${want}] got=[${got}]"; fi
    done <<EOF
$(_project_name_cases)
EOF
    got="$(env -u DAAF_PROJECT_NAME bash -c 'source "$1"; resolve_project_name' _ "${def}")"
    echo "UNSET=[${got}]"
    got="$(DAAF_PROJECT_NAME= bash -c 'source "$1"; resolve_project_name' _ "${def}")"
    echo "EMPTY=[${got}]"
}

@test "resolve_project_name normalizes DAAF_PROJECT_NAME as Docker Compose does (fixed input set)" {
    run _run_project_name_cases "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_success
    refute_output --partial "MISMATCH"
    # 17 table cases, plus the two defaults.
    [ "$(printf '%s\n' "${output}" | grep -c '^OK ')" -eq 17 ]
    assert_output --partial "UNSET=[daaf]"
    assert_output --partial "EMPTY=[daaf]"
}

@test "resolve_data_volume_name uses the normalized project name (Work -> work_daaf-data)" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_DATA_VOLUME_NAME
        export DAAF_PROJECT_NAME="-Work.1"
        resolve_data_volume_name
    '
    assert_success
    # Compose created "work1_daaf-data" for this name, not "-Work.1_daaf-data".
    assert_output "work1_daaf-data"
}

@test "resolve_data_volume_name never normalizes the DAAF_DATA_VOLUME_NAME override" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        export DAAF_DATA_VOLUME_NAME="My.Shared_Vol"
        export DAAF_PROJECT_NAME="Work"
        resolve_data_volume_name
    '
    assert_success
    # The override is a literal Docker volume name: upper case and '.' are kept.
    assert_output "My.Shared_Vol"
}

@test "resolve_data_volume_name prints nothing and fails when the project name normalizes to nothing" {
    run bash -c '
        unset _DAAF_LIB_LOADED
        source "'"${REPO_ROOT}"'/scripts/host/daaf_lib.sh"
        unset DAAF_DATA_VOLUME_NAME
        export DAAF_PROJECT_NAME="___"
        resolve_data_volume_name
    '
    assert_failure
    assert_output ""
}

@test "resolve_project_name copies in backup/restore/update/test_migration are byte-identical to daaf_lib.sh" {
    # The standalone scripts do not source daaf_lib.sh, so each carries the function
    # inline. Extract each definition (from the `resolve_project_name() {` line to
    # the first column-0 `}`) and compare bytes with the library's.
    local lib f extracted
    lib="$(sed -n '/^resolve_project_name() {$/,/^}$/p' "${REPO_ROOT}/scripts/host/daaf_lib.sh")"
    # Guard against an empty or wrong extraction making every copy "equal".
    [ "$(printf '%s\n' "${lib}" | grep -c 'LC_ALL=C tr -cd')" -eq 1 ]
    for f in ${_PROJECT_NAME_COPIES}; do
        extracted="$(sed -n '/^resolve_project_name() {$/,/^}$/p' "${REPO_ROOT}/scripts/host/${f}")"
        if [ "${extracted}" != "${lib}" ]; then
            echo "DIFFERS: ${f}"
            diff <(printf '%s\n' "${lib}") <(printf '%s\n' "${extracted}") || true
            return 1
        fi
    done
}

@test "resolve_project_name: each inline copy and install.sh give the library's results on the fixed input set" {
    local f n
    # The library is the reference (pinned to the expected column above); every copy
    # is run over the same cases and must give the same per-case lines.
    run _run_project_name_cases "${REPO_ROOT}/scripts/host/daaf_lib.sh"
    assert_success
    local want="${output}"
    for f in ${_PROJECT_NAME_COPIES}; do
        sed -n '/^resolve_project_name() {$/,/^}$/p' "${REPO_ROOT}/scripts/host/${f}" > "${TEST_DIR}/copy_${f}"
        run _run_project_name_cases "${TEST_DIR}/copy_${f}"
        assert_success
        [ "${output}" = "${want}" ] || { echo "COPY ${f} differs:"; echo "${output}"; return 1; }
    done
    # install.sh runs standalone (curl | bash) and keeps its own two lines: the
    # lowercase-and-filter line and the leading-'_'/'-' trim. Wrap exactly those
    # lines (each must occur once) in a resolve_project_name with the installer's
    # own default and empty handling, then run the same cases.
    n="$(grep -cF 'INSTALL_TARGET_PROJECT="$(printf' "${REPO_ROOT}/scripts/host/install.sh")"
    [ "${n}" -eq 1 ]
    n="$(grep -cF 'INSTALL_TARGET_PROJECT="${INSTALL_TARGET_PROJECT#' "${REPO_ROOT}/scripts/host/install.sh")"
    [ "${n}" -eq 1 ]
    {
        echo 'resolve_project_name() {'
        echo '    PROJECT_NAME_GIVEN="${DAAF_PROJECT_NAME:-}"'
        echo '    INSTALL_TARGET_PROJECT="daaf"'
        echo '    if [ -n "${PROJECT_NAME_GIVEN}" ]; then'
        grep -F 'INSTALL_TARGET_PROJECT="$(printf' "${REPO_ROOT}/scripts/host/install.sh"
        grep -F 'INSTALL_TARGET_PROJECT="${INSTALL_TARGET_PROJECT#' "${REPO_ROOT}/scripts/host/install.sh"
        echo '    fi'
        echo '    printf "%s\n" "${INSTALL_TARGET_PROJECT}"'
        echo '}'
    } > "${TEST_DIR}/copy_install.sh"
    run _run_project_name_cases "${TEST_DIR}/copy_install.sh"
    assert_success
    [ "${output}" = "${want}" ] || { echo "install.sh differs:"; echo "${output}"; return 1; }
}

@test "resolve_project_name: no host script derives a Docker name from the RAW DAAF_PROJECT_NAME" {
    # The copies above are only useful if the scripts call them. Every code line (not
    # a comment) that once read "${DAAF_PROJECT_NAME:-daaf}" for a volume or container
    # name must now go through resolve_project_name, so a revert of any one site fails
    # here. (The backup/restore/update suites check the names behaviourally; this pin
    # also covers test_migration.sh, which needs Docker and a network to run.)
    local f n
    for f in daaf_lib.sh ${_PROJECT_NAME_COPIES}; do
        n="$(grep -v '^[[:space:]]*#' "${REPO_ROOT}/scripts/host/${f}" | grep -c 'DAAF_PROJECT_NAME:-daaf' || true)"
        [ "${n}" -eq 0 ] || { echo "${f}: ${n} raw DAAF_PROJECT_NAME:-daaf code line(s)"; return 1; }
    done
    for f in backup_daaf.sh restore_from_backup.sh test_migration.sh; do
        n="$(grep -cxF 'PROJECT_NAME="$(resolve_project_name)"' "${REPO_ROOT}/scripts/host/${f}" || true)"
        [ "${n}" -eq 1 ] || { echo "${f}: PROJECT_NAME is not taken from resolve_project_name (${n})"; return 1; }
    done
    # test_migration.sh: every identifier it checks is built from that PROJECT_NAME.
    n="$(grep -cE '^readonly (VOLUME_NAME|CLAUDE_VOLUME_NAME|CONTAINER_MAIN|CONTAINER_INIT|IMAGE_NAME)="\$\{PROJECT_NAME\}[-_]' "${REPO_ROOT}/scripts/host/test_migration.sh" || true)"
    [ "${n}" -eq 5 ]
    # daaf_lib.sh's own data-volume resolver calls the helper.
    n="$(sed -n '/^resolve_data_volume_name() {$/,/^}$/p' "${REPO_ROOT}/scripts/host/daaf_lib.sh" | grep -cF 'project="$(resolve_project_name)"' || true)"
    [ "${n}" -eq 1 ]
}

@test "resolve_project_name: test_migration.sh refuses a project name that normalizes to nothing" {
    # Static: the harness needs Docker and a network to run. Its empty-name refusal
    # must follow the derivation and exit before any identifier is used.
    local sh="${REPO_ROOT}/scripts/host/test_migration.sh" derive refuse first_use
    derive="$(grep -nxF 'PROJECT_NAME="$(resolve_project_name)"' "${sh}" | cut -d: -f1)"
    refuse="$(grep -nxF 'if [ -z "${PROJECT_NAME}" ]; then' "${sh}" | head -n 1 | cut -d: -f1)"
    first_use="$(grep -nE '^readonly VOLUME_NAME=' "${sh}" | cut -d: -f1)"
    echo "derive=${derive} refuse=${refuse} first_use=${first_use}"
    [ -n "${derive}" ] && [ -n "${refuse}" ] && [ -n "${first_use}" ]
    [ "${derive}" -lt "${refuse}" ]
    [ "${refuse}" -lt "${first_use}" ]
    run sed -n "${refuse},$((refuse + 5))p" "${sh}"
    assert_output --partial "cannot be used as a Docker Compose project name."
    assert_output --partial "exit 1"
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
    # The opt-in dev-tooling flag reaches the Dockerfile as a build arg; 0 builds
    # the standard image with Codex included and contributor/test tooling excluded.
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

@test "Dockerfile installs Codex in every image while developer tools remain opt-in" {
    # Match active ARG directives only; comments cannot satisfy either assertion.
    run grep -E '^[[:space:]]*ARG CODEX_VERSION=0\.153\.2[[:space:]]*$' "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -E '^[[:space:]]*ARG DAAF_DEV_CODEX_VERSION([=[:space:]]|$)' "${REPO_ROOT}/Dockerfile"
    assert_failure

    # Extract active syntax between stable section headers. The first active
    # Codex directive must be an unconditional RUN, with no DAAF_DEV guard.
    run awk '
        /^# OpenAI Codex CLI from the GitHub release tarball/ { in_block = 1; next }
        /^# GitHub CLI \(gh\) from the GitHub release tarball/ { in_block = 0 }
        in_block && $0 !~ /^[[:space:]]*#/ && $0 !~ /^[[:space:]]*$/ { print }
    ' "${REPO_ROOT}/Dockerfile"
    assert_success
    [ "${lines[0]}" = 'RUN DEB_ARCH=$(dpkg --print-architecture) \' ]
    refute_output --partial 'if [ "${DAAF_DEV}" = "1" ]'
    assert_output --partial 'CODEX_TGZ="codex-${CODEX_TRIPLE}-unknown-linux-musl.tar.gz"'
    assert_output --partial 'https://github.com/openai/codex/releases/download/rust-v${CODEX_VERSION}/${CODEX_TGZ}'
    assert_output --partial 'mv "/tmp/codex-${CODEX_TRIPLE}-unknown-linux-musl" /usr/local/bin/codex'
    assert_output --partial 'chmod +x /usr/local/bin/codex'
    assert_output --partial 'rm -f "/tmp/${CODEX_TGZ}"'

    # A representative true developer-tool block must retain its active guard.
    run awk '
        /^# shellcheck \+ bats from the Debian repo/ { in_block = 1; next }
        /^# PowerShell 7 from the GitHub release tarball/ { in_block = 0 }
        in_block && $0 !~ /^[[:space:]]*#/ && $0 !~ /^[[:space:]]*$/ { print }
    ' "${REPO_ROOT}/Dockerfile"
    assert_success
    [ "${lines[0]}" = 'RUN if [ "${DAAF_DEV}" = "1" ]; then \' ]
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

@test "Dockerfile freezes the build to one environment date (digests, uv cutoff, apt snapshot)" {
    # Base image: digest-pinned via a pre-FROM ARG, and the only FROM is that ARG.
    run grep -E '^ARG UBUNTU_BASE_IMAGE=ubuntu:24\.04@sha256:[0-9a-f]{64}$' "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -E '^FROM ' "${REPO_ROOT}/Dockerfile"
    assert_success
    [ "${#lines[@]}" -eq 1 ]
    [ "${lines[0]}" = 'FROM ${UBUNTU_BASE_IMAGE}' ]

    # uv binaries: tag AND index digest on the literal COPY --from reference.
    run grep -E '^COPY --from=ghcr\.io/astral-sh/uv:[0-9]+\.[0-9]+\.[0-9]+@sha256:[0-9a-f]{64} /uv /uvx /usr/local/bin/$' "${REPO_ROOT}/Dockerfile"
    assert_success

    # Python cutoff: full RFC 3339 UTC timestamp (never a TZ-dependent bare
    # date), persisted as ENV so in-container dry-runs see the same date.
    run grep -E '^ARG UV_EXCLUDE_NEWER=[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' "${REPO_ROOT}/Dockerfile"
    assert_success
    local uv_cutoff="${output#ARG UV_EXCLUDE_NEWER=}"
    run grep -E '^ENV UV_EXCLUDE_NEWER=\$\{UV_EXCLUDE_NEWER\}$' "${REPO_ROOT}/Dockerfile"
    assert_success

    # apt snapshot ID, and it must name the SAME instant as the uv cutoff.
    run grep -E '^ARG UBUNTU_SNAPSHOT=[0-9]{8}T[0-9]{6}Z$' "${REPO_ROOT}/Dockerfile"
    assert_success
    local snapshot_id="${output#ARG UBUNTU_SNAPSHOT=}"
    local cutoff_compact="${uv_cutoff//[-:]/}"
    [ "${cutoff_compact}" = "${snapshot_id}" ]

    # apt is frozen by DIRECT snapshot URIs (architecture-independent), not by
    # apt's Snapshot: field / APT::Snapshot (shadowed live-archive fetches, or a
    # silent live fallback) and not by a ports.ubuntu.com host-mapping conf.
    run grep -F 'SNAPSHOT_URI="https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/"' "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -F '"URIs: ${SNAPSHOT_URI}"' "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -E '^[^#]*(50daaf-snapshot|Snapshot: \$|APT::Snapshot|--snapshot)' "${REPO_ROOT}/Dockerfile"
    assert_failure

    # The snapshot origin guard helper is defined and refreshes with --error-on=any.
    run grep -F "COPY --chmod=0755 <<'DAAF_APT_UPDATE_EOF' /usr/local/bin/daaf-apt-update" "${REPO_ROOT}/Dockerfile"
    assert_success
    run grep -F 'apt-get update --error-on=any "$@"' "${REPO_ROOT}/Dockerfile"
    assert_success

    # No bare `apt-get update` anywhere outside the helper heredoc: neither in an
    # active instruction nor in a commented example (examples teach the pattern).
    # Prose comments that merely mention the command are allowed.
    run awk '
        /^COPY --chmod=0755 <<.DAAF_APT_UPDATE_EOF. / { in_helper = 1; next }
        /^DAAF_APT_UPDATE_EOF$/ { in_helper = 0; next }
        in_helper { next }
        /apt-get update/ && ($0 !~ /^[[:space:]]*#/ || $0 ~ /^[[:space:]]*#[[:space:]]*RUN /) { print NR ": " $0 }
    ' "${REPO_ROOT}/Dockerfile"
    assert_success
    [ -z "${output}" ]

    # Every apt layer calls the helper: snapshot layer x2 branches + 7 install
    # layers (system deps, universe self-heal, geospatial, DAAF_DEV
    # shellcheck/bats, R runtime .deb, R system libs, nodejs) = 9. The helper's
    # own COPY line is excluded, and the commented USER ADDITIONS example is
    # excluded by matching active lines only. An exact count makes a dropped
    # call site fail this test.
    run bash -c "grep -E '^[^#]*daaf-apt-update( |;|\$)' '${REPO_ROOT}/Dockerfile' | grep -vc '^COPY '"
    assert_success
    [ "${output}" -eq 9 ]
}
