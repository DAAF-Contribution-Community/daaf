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
    # Optional expected status, as in bats-assert (`assert_failure 3`). Without it, a
    # fallback run passed every status-specific pin (exit 1 vs 3 vs 130) whenever the
    # status was merely nonzero, so in-container runs could not catch a wrong exit code.
    # A non-numeric expected status (a typo such as `assert_failure l`) fails LOUDLY:
    # otherwise `[ ... -ne "$1" ]` errors out, its test is false, and the pin passes.
    assert_failure() {
        if [ "$#" -gt 0 ]; then
            case "$1" in
                ''|*[!0-9]*)
                    echo "assert_failure failed: expected status '$1' is not a number"
                    return 1
                    ;;
            esac
        fi
        if [ "${status}" -eq 0 ]; then
            echo "assert_failure failed: expected non-zero exit"
            echo "output: ${output}"
            return 1
        fi
        if [ "$#" -gt 0 ] && [ "${status}" -ne "$1" ]; then
            echo "assert_failure failed: expected status $1, got ${status}"
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
# Shared docker arms: the startup checks of backup_daaf.sh / restore_from_backup.sh
# ============================================================================
# Fix pass #26 (F1 compatibility, research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/
# scoping/04_F1_compat_audit.md) added three docker calls BEFORE anything is created:
#   docker version --format '{{.Client.Version}} {{.Server.Version}}'   (refuse < 25)
#   docker image inspect <pinned busybox>                               (present?)
#   docker pull <pinned busybox>                                        (only if absent)
# A mock arm that prints nothing on exit 0 reads as "Could not read the Docker version"
# and every run refuses (pass #26: 181 bats failures had that one cause), so EVERY docker
# mock -- mock_docker below and each suite's inline docker() -- delegates these calls to
# ONE shared function instead of copying the arms. Use as the FIRST line of a stub:
#
#   docker() {
#       if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
#       ...the stub's own arms...
#   }
#
# It returns 0 when it HANDLED the call (the call's exit code is in
# MOCK_DOCKER_ARM_STATUS) and 1 when the stub must handle it. Run inside `if`, so the
# script's `set -e` never sees the 1. A stub that logs its calls keeps logging only the
# calls it handles, so existing call-log assertions keep their meaning; the full argv
# log is MOCK_DOCKER_ARGV_LOG below. Knobs (all optional, read at call time):
#   MOCK_DOCKER_VERSION        stdout of `docker version` (default "29.1.3 29.1.3"; set it
#                              to "" for NO output, e.g. an unreadable version)
#   MOCK_DOCKER_VERSION_EXIT   its exit code (default 0)
#   MOCK_DOCKER_IMAGE_INSPECT_EXIT  `docker image inspect` exit (default 0 = image present;
#                              nonzero prints Docker's "No such image" line on stderr)
#   MOCK_DOCKER_PULL_EXIT      `docker pull` exit (default 0)
#   MOCK_DOCKER_PULL_STDERR    stderr text of a FAILED pull (may hold several lines)
#   MOCK_DOCKER_ARGV_LOG       a file: EVERY docker call that reaches a stub (handled here
#                              or not) is appended as one line, each argument followed by
#                              the unit separator \037 (embedded newlines folded to spaces),
#                              so the image argument of a run/create can be found exactly
# The pinned helper image (the ONE string in backup_daaf / restore_from_backup /
# migrate_daaf {.sh,.ps1} and docker-compose.yml). A test that expects a different string
# must fail: a digest change is deliberate and updates this line in the same commit.
DAAF_BUSYBOX_PIN='busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
# The same string escaped for grep -E / BRE patterns (only `.` is special in it); sed,
# not ${x//./\\.}, whose backslash handling inside double quotes changed in bash 4.3.
DAAF_BUSYBOX_PIN_RE="$(printf '%s\n' "${DAAF_BUSYBOX_PIN}" | sed 's/\./\\./g')"
export DAAF_BUSYBOX_PIN DAAF_BUSYBOX_PIN_RE

mock_docker_shared_arms() {
    MOCK_DOCKER_ARM_STATUS=0
    if [ -n "${MOCK_DOCKER_ARGV_LOG:-}" ]; then
        local _mda_arg _mda_line=""
        for _mda_arg in "$@"; do _mda_line="${_mda_line}${_mda_arg//$'\n'/ }"$'\037'; done
        printf '%s\n' "${_mda_line}" >> "${MOCK_DOCKER_ARGV_LOG}"
    fi
    case "${1:-}" in
        version)
            # ${VAR-default}, no colon: an explicitly EMPTY MOCK_DOCKER_VERSION prints nothing.
            if [ -n "${MOCK_DOCKER_VERSION-29.1.3 29.1.3}" ]; then
                printf '%s\n' "${MOCK_DOCKER_VERSION-29.1.3 29.1.3}"
            fi
            MOCK_DOCKER_ARM_STATUS="${MOCK_DOCKER_VERSION_EXIT:-0}"
            return 0
            ;;
        image)
            if [ "${2:-}" = "inspect" ]; then
                MOCK_DOCKER_ARM_STATUS="${MOCK_DOCKER_IMAGE_INSPECT_EXIT:-0}"
                if [ "${MOCK_DOCKER_ARM_STATUS}" != "0" ]; then
                    echo "Error response from daemon: No such image: ${3:-}" >&2
                fi
                return 0
            fi
            ;;
        pull)
            MOCK_DOCKER_ARM_STATUS="${MOCK_DOCKER_PULL_EXIT:-0}"
            if [ "${MOCK_DOCKER_ARM_STATUS}" = "0" ]; then
                echo "1.37.0: Pulling from library/busybox"
                echo "Status: Downloaded newer image for ${2:-}"
            elif [ -n "${MOCK_DOCKER_PULL_STDERR:-}" ]; then
                printf '%s\n' "${MOCK_DOCKER_PULL_STDERR}" >&2
            fi
            return 0
            ;;
    esac
    return 1
}
export -f mock_docker_shared_arms

# Print a MOCK_DOCKER_ARGV_LOG file ($1) readably: one call per line, every argument in
# [brackets], so argument BOUNDARIES are visible (`[version] [--format] [{{.Client.Version}}
# {{.Server.Version}}]` proves the format string arrived as ONE argument).
mock_docker_argv_show() {
    awk -F '\037' '{ s = ""; for (i = 1; i < NF; i++) s = s (i > 1 ? " " : "") "[" $i "]"; print s }' "$1"
}

# Print the IMAGE argument of every `docker run` / `docker create` in a
# MOCK_DOCKER_ARGV_LOG file ($1), one per line: the first argument after the subcommand
# that is not an option and not the value of an option that takes one (-v/--volume,
# --label/-l, --name, -e/--env, -w/--workdir, -u/--user, --entrypoint, --network,
# --mount, --platform). A run/create with no image prints "<no image>", so a
# miscounted parse cannot hide a call.
mock_docker_argv_images() {
    awk -F '\037' '
        $1 == "run" || $1 == "create" {
            img = "<no image>"
            for (i = 2; i < NF; i++) {
                a = $i
                if (a ~ /^(-v|--volume|--label|-l|--name|-e|--env|-w|--workdir|-u|--user|--entrypoint|--network|--mount|--platform)$/) { i++; continue }
                if (a ~ /^-/) continue
                img = a
                break
            }
            print img
        }
    ' "$1"
}
export -f mock_docker_argv_show mock_docker_argv_images

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
    export MOCK_DOCKER_CREATE_EXIT=0
    export MOCK_DOCKER_CREATE_OUTPUT=""
    export MOCK_DOCKER_VOLUME_EXIT=0
    export MOCK_DOCKER_PS_OUTPUT=""
    export MOCK_DOCKER_RUN_EXIT=0
    export MOCK_DOCKER_RUN_OUTPUT=""
    # `docker run -d ... busybox sh -c <STAGE_PROGRAM>` launches the symlink-strip
    # staging container (backup_daaf.{sh,ps1}). It returns a CID on stdout; `docker
    # wait <cid>` then prints the staging program's exit status. Defaults: staging
    # starts (emits a stable fake CID) and waits to a 0 (success) status. Override
    # MOCK_DOCKER_WAIT_OUTPUT per-test to model a nonzero staging exit.
    export MOCK_DOCKER_RUND_OUTPUT="stagecid0000"
    export MOCK_DOCKER_RUND_EXIT=0
    export MOCK_DOCKER_WAIT_OUTPUT="0"
    export MOCK_DOCKER_WAIT_EXIT=0
    export MOCK_DOCKER_INSPECT_EXIT=0
    export MOCK_DOCKER_INSPECT_OUTPUT=""
    export MOCK_DOCKER_START_EXIT=0
    # `docker buildx inspect <name>` probes an existing builder; `buildx create`
    # makes one. Both are used only by the opt-in DAAF_DIAG_BUILD path in
    # install.sh / rebuild_daaf.sh. Default: inspect FAILS (builder absent) so the
    # create arm is exercised, and create SUCCEEDS. Override per-test when a
    # different builder state must be modeled.
    export MOCK_DOCKER_BUILDX_INSPECT_EXIT=1
    export MOCK_DOCKER_BUILDX_CREATE_EXIT=0
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
        # version / image inspect / pull: the shared arms above (knobs MOCK_DOCKER_VERSION,
        # MOCK_DOCKER_IMAGE_INSPECT_EXIT, MOCK_DOCKER_PULL_*; full argv log
        # MOCK_DOCKER_ARGV_LOG).
        if mock_docker_shared_arms "$@"; then return "${MOCK_DOCKER_ARM_STATUS}"; fi
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
            buildx)
                shift
                case "$1" in
                    inspect) return "${MOCK_DOCKER_BUILDX_INSPECT_EXIT:-1}" ;;
                    create)  return "${MOCK_DOCKER_BUILDX_CREATE_EXIT:-0}" ;;
                    *)       return "${MOCK_DOCKER_EXIT:-0}" ;;
                esac
                ;;
            create)
                # `docker create ... busybox` returns a container ID on stdout.
                # Emit a stable fake CID so a script capturing it (e.g. the backup
                # copy path: CID=$(docker create ...)) binds a non-empty value.
                # Previously `create` fell through to the default arm, which
                # returns 0 but prints nothing -- silently giving an empty CID and
                # masking copy-path bugs in any test reaching it via the shared
                # mock. Override with a custom docker() in a test only when the
                # create/cp/rm dispatch must be modeled per-arm.
                echo "${MOCK_DOCKER_CREATE_OUTPUT:-mockcid0000}"
                return "${MOCK_DOCKER_CREATE_EXIT:-0}"
                ;;
            cp)
                return "${MOCK_DOCKER_CP_EXIT:-0}"
                ;;
            volume)
                # `docker volume inspect <name>-restore-tmp` is restore_from_backup.sh's
                # exact-name check for a TEMPORARY volume left by an earlier restore.
                # Default: ABSENT (exit 1), whatever MOCK_DOCKER_VOLUME_EXIT says about the
                # live volume -- otherwise every test reaching the copy-then-swap section
                # would see a phantom leftover and its stdin would answer the leftover
                # prompt. No other script uses that suffix, so other callers are unchanged.
                # "Absent" says so on stderr like Docker: restore treats any OTHER inspect
                # failure as "could not check" and refuses (review round 1, I2).
                if [ "${2:-}" = "inspect" ]; then
                    case "${3:-}" in
                        *-restore-tmp)
                            if [ "${MOCK_DOCKER_RESTORE_TMP_EXIT:-1}" != "0" ]; then
                                echo "Error response from daemon: get ${3}: no such volume" >&2
                            fi
                            return "${MOCK_DOCKER_RESTORE_TMP_EXIT:-1}"
                            ;;
                    esac
                fi
                return "${MOCK_DOCKER_VOLUME_EXIT:-0}"
                ;;
            container)
                # `docker container inspect --format ... <name>-restore-swap` is restore's
                # exact-name check for a swap container left by an earlier restore.
                # Default: ABSENT (exit 1). Every other `docker container ...` call keeps
                # the old default-arm behavior (MOCK_DOCKER_EXIT).
                if [ "${2:-}" = "inspect" ]; then
                    local _last=""
                    for _last in "$@"; do :; done
                    case "${_last}" in
                        *-restore-swap)
                            if [ "${MOCK_DOCKER_RESTORE_SWAP_EXIT:-1}" != "0" ]; then
                                echo "Error: No such container: ${_last}" >&2
                            fi
                            return "${MOCK_DOCKER_RESTORE_SWAP_EXIT:-1}"
                            ;;
                    esac
                fi
                return "${MOCK_DOCKER_EXIT:-0}"
                ;;
            run)
                # Distinguish the detached staging launch (`run -d ...`) from the
                # ephemeral `run --rm ...` scan/replay calls: the former returns a CID
                # for `docker wait` to block on; the latter emits scan/verify output.
                if [ "${2:-}" = "-d" ]; then
                    echo "${MOCK_DOCKER_RUND_OUTPUT:-stagecid0000}"
                    return "${MOCK_DOCKER_RUND_EXIT:-0}"
                fi
                echo "${MOCK_DOCKER_RUN_OUTPUT:-}"
                return "${MOCK_DOCKER_RUN_EXIT:-0}"
                ;;
            wait)
                # `docker wait <cid>` prints the staging container's exit status.
                echo "${MOCK_DOCKER_WAIT_OUTPUT:-0}"
                return "${MOCK_DOCKER_WAIT_EXIT:-0}"
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
