#!/usr/bin/env bats
# ============================================================================
# Tests for install.sh -- DAAF One-Line Installer
# ============================================================================

load 'test_helper'

# install.sh's volume probe (daaf_volume_state) runs `docker volume inspect NAME`
# and, only when that fails, the exact-name list `docker volume ls -q`. The shared
# mock_docker answers EVERY `docker volume ...` call with MOCK_DOCKER_VOLUME_EXIT,
# which would turn "absent" (inspect exits 1) into "the list failed too" (unknown,
# a refusal). This wrapper gives this suite its own volume arms and hands every
# other call to the shared mock, copied to _install_base_docker. Knobs:
#   MOCK_INSTALL_VOLUMES        unset: inspect exits MOCK_DOCKER_VOLUME_EXIT and the
#                               list prints nothing. Set (space-separated names, may
#                               be empty): exactly these volumes exist -- inspect
#                               exits 0 only for them, the list prints them.
#   MOCK_DOCKER_VOLUME_LS_EXIT  exit code of `docker volume ls` (default 0).
#   MOCK_INSTALL_CALL_LOG       a file: every `volume inspect` is logged as
#                               "volume inspect <name>", and every `compose -f <file>
#                               <args>` as "compose <args> | P=.. M=.. L=.. V=.. D=..",
#                               the DAAF_PROJECT_NAME / DAAF_PORT_MARIMO /
#                               _LOGVIEWER / _VSCODE / DAAF_DEV values in the
#                               EXPORTED environment at that call (read with
#                               printenv, so a set-but-unexported shell variable
#                               reads as <unset>, as it would for the real Compose).
#   MOCK_INSTALL_FAIL_ON        a literal substring: a `docker compose ...` call whose
#                               argument string contains it exits 1 (after logging).
#                               Use flag-anchored strings (" up -d", "git clone",
#                               "cp -a /tmp/daaf-clone", "--force-recreate") so the
#                               random temp path in "$*" cannot match.
install_mock_volume_arms() {
    eval "_install_base_docker() $(declare -f docker | tail -n +2)"
    export -f _install_base_docker
    docker() {
        if [ -n "${MOCK_INSTALL_CALL_LOG:-}" ]; then
            if [ "${1:-}" = "volume" ] && [ "${2:-}" = "inspect" ]; then
                echo "volume inspect ${3:-}" >> "${MOCK_INSTALL_CALL_LOG}"
            elif [ "${1:-}" = "compose" ]; then
                local _env_p _env_m _env_l _env_v _env_d
                _env_p="$(printenv DAAF_PROJECT_NAME)" || _env_p="<unset>"
                _env_m="$(printenv DAAF_PORT_MARIMO)" || _env_m="<unset>"
                _env_l="$(printenv DAAF_PORT_LOGVIEWER)" || _env_l="<unset>"
                _env_v="$(printenv DAAF_PORT_VSCODE)" || _env_v="<unset>"
                _env_d="$(printenv DAAF_DEV)" || _env_d="<unset>"
                echo "compose ${*:4} | P=${_env_p} M=${_env_m} L=${_env_l} V=${_env_v} D=${_env_d}" >> "${MOCK_INSTALL_CALL_LOG}"
            fi
        fi
        if [ -n "${MOCK_INSTALL_FAIL_ON:-}" ] && [ "${1:-}" = "compose" ]; then
            case "$*" in
                *"${MOCK_INSTALL_FAIL_ON}"*) return 1 ;;
            esac
        fi
        if [ "${1:-}" = "volume" ]; then
            case "${2:-}" in
                inspect)
                    if [ -n "${MOCK_INSTALL_VOLUMES+x}" ]; then
                        case " ${MOCK_INSTALL_VOLUMES} " in
                            *" ${3:-} "*) return 0 ;;
                        esac
                        echo "Error response from daemon: get ${3:-}: no such volume" >&2
                        return 1
                    fi
                    return "${MOCK_DOCKER_VOLUME_EXIT:-0}"
                    ;;
                ls)
                    if [ "${MOCK_DOCKER_VOLUME_LS_EXIT:-0}" != "0" ]; then
                        echo "Cannot connect to the Docker daemon" >&2
                        return "${MOCK_DOCKER_VOLUME_LS_EXIT}"
                    fi
                    if [ -n "${MOCK_INSTALL_VOLUMES:-}" ]; then
                        # shellcheck disable=SC2086  # word-split the name list on purpose
                        printf '%s\n' ${MOCK_INSTALL_VOLUMES}
                    fi
                    return 0
                    ;;
            esac
        fi
        _install_base_docker "$@"
    }
    export -f docker
}

setup() {
    common_setup
    mock_docker
    install_mock_volume_arms
    mock_curl
    # Baseline: a machine with NO DAAF data volume. (The shared mock's default,
    # MOCK_DOCKER_VOLUME_EXIT=0, means "the volume exists"; since the existing-
    # install check no longer depends on a docker-compose.yml in the install
    # folder, that default would make every fresh-install test a case-2 refusal.)
    # Tests that model an existing install set MOCK_DOCKER_VOLUME_EXIT=0 or
    # MOCK_INSTALL_VOLUMES explicitly.
    export MOCK_DOCKER_VOLUME_EXIT=1
    unset MOCK_INSTALL_VOLUMES MOCK_DOCKER_VOLUME_LS_EXIT
    # Hermetic volume naming: a DAAF dev container exports its own DAAF_PROJECT_NAME
    # and DAAF_DATA_VOLUME_NAME (observed 2026-10-06), which would otherwise steer
    # which volume install.sh checks. Tests that need them set them explicitly.
    unset DAAF_PROJECT_NAME DAAF_DATA_VOLUME_NAME DAAF_FORCE_REINSTALL
    # The installer also bridges these from an existing environment_settings.txt;
    # start every test with none of them set.
    unset DAAF_PORT_MARIMO DAAF_PORT_LOGVIEWER DAAF_PORT_VSCODE DAAF_DEV MOCK_INSTALL_CALL_LOG MOCK_INSTALL_FAIL_ON
    # install.sh does NOT require docker-compose.yml to exist beforehand
    # (it creates the install directory itself)
}

# Replace curl with one that records every URL it is asked for (and writes the
# empty -o target like mock_curl), so a test can prove nothing was downloaded.
install_log_curl() {
    curl() {
        local outfile="" url="" args=("$@") i
        for (( i=0; i<${#args[@]}; i++ )); do
            case "${args[$i]}" in
                -o) outfile="${args[$((i+1))]}" ;;
                http*) url="${args[$i]}" ;;
            esac
        done
        echo "CURL_URL: ${url}" >> "${TEST_DIR}/curl_log.txt"
        if [ -n "${outfile}" ]; then mkdir -p "$(dirname "${outfile}")"; touch "${outfile}"; fi
        return 0
    }
    export -f curl
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
# Existing-install guard does not depend on the install folder (B-1)
# =========================================================================
# Before 2026-10-06 the data-volume check ran only when THIS folder held a
# docker-compose.yml, so the installer run from another folder with the same
# project name rebuilt and `up -d`'d that install's Compose project and copied a
# fresh clone over its framework files and git history. Cases (see install.sh):
#   1. volume + compose here -> WARNING, exit 1 (tests above)
#   2. volume, no compose    -> refuse, exit 1, before any download/build (below)
#   3. no volume + compose   -> "incomplete" NOTE, proceed (test above)
#   4. no volume, no compose -> fresh install (tests above)
# Case 2 checks the volume THIS run would write: "${DAAF_PROJECT_NAME:-daaf}_daaf-data".

@test "install.sh: case 2 -- volume exists, no compose file here: refuses before any download or build" {
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_DOCKER_ARGV_LOG="${TEST_DIR}/docker_argv.log"
    install_log_curl
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "A DAAF installation using Docker volume 'daaf_daaf-data' (project 'daaf')"
    assert_output --partial "already exists, probably installed from another folder, or its daaf-docker"
    assert_output --partial "folder was moved or deleted."
    assert_output --partial "Nothing has been downloaded or changed."
    # Default project: the FORCE hint needs no DAAF_PROJECT_NAME.
    # Whole-line match; the branch segment is whatever DAAF_BRANCH resolves to.
    grep -Exq -- '  DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
    refute_output --partial "DAAF_PROJECT_NAME=daaf DAAF_FORCE_REINSTALL"
    # Stopped before step [1/4]: no folder, no download, no compose build/up.
    refute_output --partial "[1/4]"
    refute_output --partial "Downloading"
    [ ! -e "${TEST_DIR}/daaf-docker" ]
    [ ! -f "${TEST_DIR}/curl_log.txt" ]
    run grep -c "compose" "${MOCK_DOCKER_ARGV_LOG}"
    [ "${output}" = "0" ]
}

@test "install.sh: case 2 refusal names update, second-instance, and force escapes" {
    export DAAF_PROJECT_NAME="myproj"
    MOCK_INSTALL_VOLUMES="myproj_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "Docker volume 'myproj_daaf-data'"
    assert_output --partial "(project 'myproj')"
    assert_output --partial "bash update_daaf.sh"
    # The second-instance variables, named as the installation guide names them.
    assert_output --partial "export DAAF_PROJECT_NAME="
    assert_output --partial "export DAAF_PORT_MARIMO="
    assert_output --partial "export DAAF_PORT_LOGVIEWER="
    assert_output --partial "export DAAF_PORT_VSCODE="
    assert_output --partial "Running multiple DAAF instances"
    assert_output --partial "01_installation_and_quickstart.md#running-multiple-daaf-instances"
    assert_output --partial "DAAF_FORCE_REINSTALL=1 bash -c"
    # It is NOT the case-1 text (that one says "cd <this folder>").
    refute_output --partial "An existing DAAF installation was detected."
}

@test "install.sh: case 2 FORCE hint for a non-default project names DAAF_PROJECT_NAME on the same line (42q I-1)" {
    # Without the project on the FORCE line, a re-run from a new terminal (or with
    # a one-shot prefix) falls back to project 'daaf' and could take that over.
    export DAAF_PROJECT_NAME="myproj"
    MOCK_INSTALL_VOLUMES="myproj_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    # Whole-line match; the branch segment is whatever DAAF_BRANCH resolves to.
    grep -Exq -- '  DAAF_PROJECT_NAME=myproj DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
    # The second-copy example is a different project from the refused one, and
    # (refused project not 'daaf') avoids the guide's example ports 2818-2820.
    assert_output --partial "  export DAAF_PROJECT_NAME=daaf-work"
    assert_output --partial "  export DAAF_PORT_MARIMO=2918"
}

@test "install.sh: following the printed case-2 FORCE hint in a fresh shell re-targets the same project" {
    # Take the env prefix of the printed FORCE line and run the installer with
    # ONLY that prefix (DAAF_PROJECT_NAME unset in the parent): the forced run must
    # check and name myproj's volume, never fall back to daaf's (which also exists).
    export DAAF_PROJECT_NAME="myproj"
    MOCK_INSTALL_VOLUMES="myproj_daaf-data daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    hint="$(grep -F -- 'DAAF_FORCE_REINSTALL=1 bash -c' <<< "${output}")"
    prefix="${hint%% bash -c*}"
    [ -n "${prefix}" ]
    unset DAAF_PROJECT_NAME
    # shellcheck disable=SC2086  # the hint's env prefix is split into assignments on purpose
    run env ${prefix} bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "NOTE: An existing DAAF installation using Docker volume 'myproj_daaf-data' (project 'myproj')"
    refute_output --partial "'daaf_daaf-data'"
    assert_output --partial "Downloading"
}

@test "install.sh: case 2 refusing project daaf-personal gives a different second-copy example (name and ports)" {
    export DAAF_PROJECT_NAME="daaf-personal"
    MOCK_INSTALL_VOLUMES="daaf-personal_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "(project 'daaf-personal')"
    assert_output --partial "  export DAAF_PROJECT_NAME=daaf-work"
    assert_output --partial "  export DAAF_PORT_MARIMO=2918"
    assert_output --partial "  export DAAF_PORT_LOGVIEWER=2919"
    assert_output --partial "  export DAAF_PORT_VSCODE=2920"
    refute_output --partial "export DAAF_PROJECT_NAME=daaf-personal"
    refute_output --partial "export DAAF_PORT_MARIMO=2818"
    assert_output --partial "  DAAF_PROJECT_NAME=daaf-personal DAAF_FORCE_REINSTALL=1 bash -c"
}

@test "install.sh: case 2 with DAAF_FORCE_REINSTALL=1 proceeds with a NOTE" {
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "NOTE: An existing DAAF installation using Docker volume 'daaf_daaf-data'"
    assert_output --partial "re-install from this folder (DAAF_FORCE_REINSTALL=1)."
    assert_output --partial "Downloading"
    refute_output --partial "Nothing has been downloaded or changed."
}

@test "install.sh: no compose file here -- a settings file's project is checked AND built (case 2 and 4 agree with Compose)" {
    # A settings file without a compose file (a partial folder) names project
    # 'other'. The installer adopts and exports it (F-a), so the volume it checks
    # and the project Compose builds are both 'other' -- never 'daaf', whose
    # volume exists. Later launches from this folder read the same file.
    unset DAAF_PROJECT_NAME
    mkdir -p "${TEST_DIR}/daaf-docker"
    printf 'DAAF_PROJECT_NAME=other\n' > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    refute_output --partial "already exists, probably installed from"
    assert_output --partial "Downloading"
    run grep -x "volume inspect other_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "daaf_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
    run grep -x "compose build --progress plain | P=other M=<unset> L=<unset> V=<unset> D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    # Same folder (its downloaded compose file removed again), but 'other' already
    # has a volume: refused, naming 'other', and the FORCE hint carries it.
    rm -f "${MOCK_INSTALL_CALL_LOG}" "${TEST_DIR}/daaf-docker/docker-compose.yml"
    MOCK_INSTALL_VOLUMES="other_daaf-data daaf_daaf-data"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "Docker volume 'other_daaf-data' (project 'other')"
    grep -Exq -- '  DAAF_PROJECT_NAME=other DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
    refute_output --partial "Downloading"
}

@test "install.sh: case 2 ignores DAAF_DATA_VOLUME_NAME (shared-workspace Step 3 still installs)" {
    # Installation guide, "Sharing One Research Workspace Across Two Installs",
    # Step 3: a second copy is installed from a new folder with a distinct project
    # name and DAAF_DATA_VOLUME_NAME naming install #1's EXISTING volume. The run
    # writes its own daaf-gpt_daaf-data (absent), so it must not be refused.
    export DAAF_PROJECT_NAME="daaf-gpt"
    export DAAF_DATA_VOLUME_NAME="daaf_daaf-data"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    refute_output --partial "already exists, probably installed from"
    assert_output --partial "Downloading"
}

@test "install.sh: case 2 refuses when only DAAF_DATA_VOLUME_NAME is set (default project volume exists)" {
    # Step 3 done wrong: no distinct project name, so this run would take over
    # project 'daaf' and its existing daaf_daaf-data.
    unset DAAF_PROJECT_NAME
    export DAAF_DATA_VOLUME_NAME="daaf_daaf-data"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "Docker volume 'daaf_daaf-data'"
}

@test "install.sh: case 4 -- another project's volume does not block a fresh install" {
    export DAAF_PROJECT_NAME="daaf-personal"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    refute_output --partial "already exists, probably installed from"
    refute_output --partial "Could not check"
    assert_output --partial "Downloading"
}

@test "install.sh: volume check that cannot run (inspect AND list fail) refuses, never reads as absent" {
    export MOCK_DOCKER_VOLUME_EXIT=1
    export MOCK_DOCKER_VOLUME_LS_EXIT=1
    install_log_curl
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "Could not check whether a DAAF installation already exists"
    assert_output --partial "'daaf_daaf-data'"
    refute_output --partial "Downloading"
    [ ! -f "${TEST_DIR}/curl_log.txt" ]
    # Default project: the FORCE hint needs no DAAF_PROJECT_NAME.
    # Whole-line match; the branch segment is whatever DAAF_BRANCH resolves to.
    grep -Exq -- '  DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
    refute_output --partial "DAAF_PROJECT_NAME="
}

@test "install.sh: 'could not check' FORCE hint for a non-default project names DAAF_PROJECT_NAME on the same line (42q I-1)" {
    export DAAF_PROJECT_NAME="myproj"
    export MOCK_DOCKER_VOLUME_EXIT=1
    export MOCK_DOCKER_VOLUME_LS_EXIT=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "looking for 'myproj_daaf-data'"
    # Whole-line match; the branch segment is whatever DAAF_BRANCH resolves to.
    grep -Exq -- '  DAAF_PROJECT_NAME=myproj DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
}

@test "install.sh: unknown volume state with compose here also refuses (not the 'incomplete' NOTE)" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    export MOCK_DOCKER_VOLUME_EXIT=1
    export MOCK_DOCKER_VOLUME_LS_EXIT=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "Could not check whether a DAAF installation already exists"
    refute_output --partial "appears incomplete"
}

@test "install.sh: unknown volume state with DAAF_FORCE_REINSTALL=1 proceeds with a NOTE" {
    export MOCK_DOCKER_VOLUME_EXIT=1
    export MOCK_DOCKER_VOLUME_LS_EXIT=1
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "NOTE: Could not check whether Docker volume 'daaf_daaf-data' already exists."
    assert_output --partial "Downloading"
}

@test "install.sh: daaf_volume_state -- a failed inspect falls back to an exact-name list" {
    # Sourced in test mode (the helper is defined before the guard). Custom docker:
    # inspect always fails; the list prints a near-miss name and one exact name.
    docker() {
        case "$*" in
            "volume inspect"*) return 1 ;;
            "volume ls -q") printf '%s\n' "daaf_daaf-data-restore-tmp" "DAAF_DAAF-DATA" "listed_vol"; return 0 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash -c 'DAAF_TEST_MODE=1 source "$1"; daaf_volume_state listed_vol; daaf_volume_state daaf_daaf-data' _ "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    [ "${lines[0]}" = "present" ]
    # Neither a longer name nor a case variant matches.
    [ "${lines[1]}" = "absent" ]
}

@test "install.sh: daaf_volume_state -- inspect success is present; a failed list is unknown" {
    docker() {
        case "$*" in
            "volume inspect here") return 0 ;;
            "volume inspect"*) return 1 ;;
            "volume ls -q") return 1 ;;
            *) return 0 ;;
        esac
    }
    export -f docker
    run bash -c 'DAAF_TEST_MODE=1 source "$1"; daaf_volume_state here; daaf_volume_state gone' _ "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    [ "${lines[0]}" = "present" ]
    [ "${lines[1]}" = "unknown" ]
}

# =========================================================================
# One project-name source (F-a) and the second-copy example (F-c)
# =========================================================================
# The installer bridges DAAF_PROJECT_NAME, the three DAAF_PORT_* keys and DAAF_DEV
# from an existing environment_settings.txt into the EXPORTED environment, as the
# launchers' load_daaf_settings does (shell value wins), and derives the target
# project once. The volume checked, every compose call (logged by the mock with the
# exported env, MOCK_INSTALL_CALL_LOG) and every printed hint must use that one
# project. Before F-a the file's project only named the volume checked: Compose
# built and started project 'daaf' on the default ports (reviews 42q I-2, 43d
# ISSUE-1).

# Write a named instance's folder: <TEST_DIR>/daaf-docker with a compose file and
# a settings file holding project x and ports 3101-3103 (plus a comment line).
install_named_folder() {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    printf '%s\n' "# my real API keys" "DAAF_PROJECT_NAME=x" "DAAF_PORT_MARIMO=3101" \
        "DAAF_PORT_LOGVIEWER=3102" "DAAF_PORT_VSCODE=3103" > "${TEST_DIR}/daaf-docker/environment_settings.txt"
}

@test "install.sh F-a: a re-install from a named instance's own folder builds, starts and execs the settings-file project and ports" {
    install_named_folder
    MOCK_INSTALL_VOLUMES="x_daaf-data daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "NOTE: Existing installation detected. Proceeding with re-install (DAAF_FORCE_REINSTALL=1)."
    assert_output --partial "Installation complete"
    # The check examined x's volume, never daaf's.
    run grep -x "volume inspect x_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "daaf_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
    # Build, start and every exec see project x and its ports in the exported env.
    run grep -x "compose build --progress plain | P=x M=3101 L=3102 V=3103 D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -x "compose up -d | P=x M=3101 L=3102 V=3103 D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "^compose " "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" -ge 4 ]
    [ "$(grep '^compose ' "${MOCK_INSTALL_CALL_LOG}" | grep -vc ' | P=x M=3101 L=3102 V=3103 D=<unset>$' || true)" = "0" ]
}

@test "install.sh F-a: a shell value wins over the settings file, key by key" {
    install_named_folder
    export DAAF_PROJECT_NAME="y"
    export DAAF_PORT_MARIMO="4001"
    MOCK_INSTALL_VOLUMES="y_daaf-data x_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    run grep -x "volume inspect y_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "x_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
    # Project and Marimo port from the shell; the two ports the shell left unset
    # come from the file.
    run grep -x "compose build --progress plain | P=y M=4001 L=3102 V=3103 D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
}

@test "install.sh F-a: settings-file parsing follows load_daaf_settings (column 0, quotes, CR, comments, repeated empty key)" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    printf '%s\r\n' "# DAAF_PROJECT_NAME=commented" "  DAAF_PORT_MARIMO=9999" "DAAF_PROJECT_NAME=\"x\"" \
        "DAAF_PORT_MARIMO='3101'" "DAAF_PORT_LOGVIEWER=" "DAAF_PORT_LOGVIEWER=3102" "DAAF_DEV=1" \
        > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    MOCK_INSTALL_VOLUMES=""
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "previous install attempt was detected but appears incomplete"
    run grep -x "volume inspect x_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -x "compose build --progress plain | P=x M=3101 L=3102 V=<unset> D=1" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
}

@test "install.sh F-a: the case-1 WARNING names the settings-file project, and following its FORCE hint targets that project" {
    install_named_folder
    MOCK_INSTALL_VOLUMES="x_daaf-data daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "WARNING: An existing DAAF installation was detected."
    assert_output --partial "         (Docker volume 'x_daaf-data', project 'x')"
    # Whole-line match; the branch segment is whatever DAAF_BRANCH resolves to.
    grep -Exq -- '  DAAF_PROJECT_NAME=x DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
    hint="$(grep -F -- 'DAAF_FORCE_REINSTALL=1 bash -c' <<< "${output}")"
    prefix="${hint%% bash -c*}"
    [ -f "${MOCK_INSTALL_CALL_LOG}" ]
    run grep -c "^compose " "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
    # Follow the printed line with ONLY its env prefix, from a folder that has no
    # settings file (the hint alone must carry the project): x is checked and
    # built, never daaf.
    mkdir -p "${TEST_DIR}/elsewhere"
    cd "${TEST_DIR}/elsewhere"
    rm -f "${MOCK_INSTALL_CALL_LOG}"
    MOCK_DOCKER_COMPOSE_EXIT=1
    # shellcheck disable=SC2086  # the hint's env prefix is split into assignments on purpose
    run env ${prefix} bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "NOTE: An existing DAAF installation using Docker volume 'x_daaf-data' (project 'x')"
    refute_output --partial "'daaf_daaf-data'"
    run grep -x "compose build --progress plain | P=x M=<unset> L=<unset> V=<unset> D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
}

@test "install.sh F-a: the 'could not check' hint carries the settings-file project, and following it builds that project (43d ISSUE-1)" {
    install_named_folder
    export MOCK_DOCKER_VOLUME_EXIT=1
    export MOCK_DOCKER_VOLUME_LS_EXIT=1
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "looking for 'x_daaf-data'"
    grep -Exq -- '  DAAF_PROJECT_NAME=x DAAF_FORCE_REINSTALL=1 bash -c "\$\(curl -fsSL https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh\)"' <<< "${output}"
    hint="$(grep -F -- 'DAAF_FORCE_REINSTALL=1 bash -c' <<< "${output}")"
    prefix="${hint%% bash -c*}"
    # Follow it in the same folder, the shell project still unset (Docker still
    # cannot answer): the forced run names and builds project x.
    MOCK_DOCKER_COMPOSE_EXIT=1
    # shellcheck disable=SC2086  # the hint's env prefix is split into assignments on purpose
    run env ${prefix} bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "NOTE: Could not check whether Docker volume 'x_daaf-data' already exists."
    run grep -x "compose build --progress plain | P=x M=3101 L=3102 V=3103 D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "P=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
}

@test "install.sh F-a: a shared-workspace install's own folder -- the file's DAAF_DATA_VOLUME_NAME is not checked, and Compose never targets project daaf" {
    # Install #2 of the guide's "Sharing One Research Workspace" (project daaf-gpt,
    # DAAF_DATA_VOLUME_NAME=daaf_daaf-data in its settings file), re-run from its own
    # folder with nothing exported. The re-downloaded compose file has the shared
    # block commented out, so this run writes daaf-gpt_daaf-data: that is the volume
    # checked. Before F-a, Compose built project 'daaf' here and its `up -d` + clone
    # copy landed on install #1's daaf_daaf-data.
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    printf '%s\n' "DAAF_PROJECT_NAME=daaf-gpt" "DAAF_PORT_MARIMO=2818" "DAAF_PORT_LOGVIEWER=2819" \
        "DAAF_PORT_VSCODE=2820" "DAAF_DATA_VOLUME_NAME=daaf_daaf-data" > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    # Step 4 deleted the transitional daaf-gpt_daaf-data: only the shared volume exists.
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_output --partial "previous install attempt was detected but appears incomplete"
    run grep -x "volume inspect daaf-gpt_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "volume inspect daaf_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
    run grep -x "compose build --progress plain | P=daaf-gpt M=2818 L=2819 V=2820 D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    # With its own volume present, it is the case-1 WARNING for daaf-gpt.
    MOCK_INSTALL_VOLUMES="daaf_daaf-data daaf-gpt_daaf-data"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "(Docker volume 'daaf-gpt_daaf-data', project 'daaf-gpt')"
}

@test "install.sh F-a: shared-workspace Step 3 from a new folder still installs, as daaf-gpt on its own ports" {
    export DAAF_PROJECT_NAME="daaf-gpt"
    export DAAF_PORT_MARIMO="2818"
    export DAAF_PORT_LOGVIEWER="2819"
    export DAAF_PORT_VSCODE="2820"
    export DAAF_DATA_VOLUME_NAME="daaf_daaf-data"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    refute_output --partial "already exists, probably installed from"
    run grep -x "volume inspect daaf-gpt_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -x "compose up -d | P=daaf-gpt M=2818 L=2819 V=2820 D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run cat "${TEST_DIR}/daaf-docker/environment_settings.txt"
    assert_output --partial "DAAF_PROJECT_NAME=daaf-gpt"
    assert_output --partial "DAAF_DATA_VOLUME_NAME=daaf_daaf-data"
}

@test "install.sh F-a: a fresh install is unchanged -- no settings file, nothing bridged, project left to Compose's default" {
    # (A DAAF dev container exports DAAF_BRANCH, which the seeder would persist.)
    unset DAAF_BRANCH
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "Created environment_settings.txt from the template"
    run grep -x "volume inspect daaf_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c "^compose " "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" -ge 4 ]
    [ "$(grep '^compose ' "${MOCK_INSTALL_CALL_LOG}" | grep -vc ' | P=<unset> M=<unset> L=<unset> V=<unset> D=<unset>$' || true)" = "0" ]
}

@test "install.sh F-a: values adopted from an existing settings file are never written back (seeding leaves the file byte-identical)" {
    install_named_folder
    printf '%s\n' "DAAF_DEV=1" >> "${TEST_DIR}/daaf-docker/environment_settings.txt"
    cp "${TEST_DIR}/daaf-docker/environment_settings.txt" "${TEST_DIR}/settings.before"
    MOCK_INSTALL_VOLUMES="x_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "An existing environment_settings.txt was found and left untouched."
    refute_output --partial "seeded these values"
    refute_output --partial "Restarting the container"
    cmp "${TEST_DIR}/settings.before" "${TEST_DIR}/daaf-docker/environment_settings.txt"
    # DAAF_DEV is bridged too; no post-seed --force-recreate happened.
    run grep -x "compose build --progress plain | P=x M=3101 L=3102 V=3103 D=1" "${MOCK_INSTALL_CALL_LOG}"
    assert_success
    run grep -c -- "--force-recreate" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
}

@test "install.sh F-c: the second-copy example never repeats the refused project and avoids 2818-2820 for any non-default project" {
    # Deterministic table: daaf -> daaf-personal 2818-2820; daaf-work -> daaf-lab
    # 3018-3020; any other project -> daaf-work 2918-2920. daaf-personal and
    # daaf-gpt are the installation guide's examples on 2818-2820; daafmac is the
    # Mac test doc's.
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    for refused in daaf daaf-personal daaf-gpt daafmac daaf-work daaf-lab myproj; do
        case "${refused}" in
            daaf) want="daaf-personal 2818 2819 2820" ;;
            daaf-work) want="daaf-lab 3018 3019 3020" ;;
            *) want="daaf-work 2918 2919 2920" ;;
        esac
        MOCK_INSTALL_VOLUMES="${refused}_daaf-data"
        export MOCK_INSTALL_VOLUMES
        if [ "${refused}" = "daaf" ]; then unset DAAF_PROJECT_NAME; else export DAAF_PROJECT_NAME="${refused}"; fi
        run bash "${REPO_ROOT}/scripts/host/install.sh"
        [ "${status}" -eq 1 ]
        name="$(sed -n 's/^  export DAAF_PROJECT_NAME=//p' <<< "${output}")"
        marimo="$(sed -n 's/^  export DAAF_PORT_MARIMO=//p' <<< "${output}")"
        logviewer="$(sed -n 's/^  export DAAF_PORT_LOGVIEWER=//p' <<< "${output}")"
        vscode="$(sed -n 's/^  export DAAF_PORT_VSCODE=//p' <<< "${output}")"
        echo "refused=${refused} example=${name} ${marimo} ${logviewer} ${vscode}"
        [ "${name} ${marimo} ${logviewer} ${vscode}" = "${want}" ]
        [ "${name}" != "${refused}" ]
        if [ "${refused}" != "daaf" ]; then
            case " ${marimo} ${logviewer} ${vscode} " in
                *" 2818 "*|*" 2819 "*|*" 2820 "*) false ;;
            esac
        fi
    done
}

# =========================================================================
# Round #45: the project name as Compose uses it, printed commands that carry it
# =========================================================================
# Review 44q (research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/reviews/):
#   ISSUE-1  Compose normalizes `name:` (compose-go NormalizeProjectName: lowercase,
#            keep [a-z0-9_-], trim leading '_'/'-'); the installer checked the raw
#            value. Now the normalized name is checked, exported and printed; a name
#            that normalizes to nothing is refused before anything is downloaded.
#   ISSUE-2  manual `docker compose ...` commands and "re-run" texts printed on
#            failure carry -p <project> (and, for `up -d`, the ports).
#   SUGGESTION-1/2/3, NIT-1: all-five shell-wins, the case-1 no-settings-file
#            lines, the adopted-settings NOTE, the unreadable-file ERROR.

INSTALL_URL_RE='https://raw\.githubusercontent\.com/DAAF-Contribution-Community/daaf/[^/ ]+/scripts/host/install\.sh'

@test "install.sh #45 ISSUE-1: a settings-file project name is normalized as Compose does -- check, Compose and NOTE (no compose file, and with one)" {
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    MOCK_INSTALL_VOLUMES=""
    export MOCK_INSTALL_VOLUMES
    i=0
    # One input per branch of the rule: lowercase, drop, trim '_', trim '-', and a
    # mixed leading run (review 45q SUGGESTION-1: the '-' trim had no input).
    for pair in 'Work|work' 'work |work' 'x # mine|xmine' '"x|x' '_x|x' '-x|x' '-_x|x'; do
        raw="${pair%|*}"
        norm="${pair##*|}"
        for withcompose in no yes; do
            i=$((i + 1))
            mkdir -p "${TEST_DIR}/n${i}/daaf-docker"
            if [ "${withcompose}" = "yes" ]; then create_fake_compose_file "${TEST_DIR}/n${i}/daaf-docker"; fi
            printf 'DAAF_PROJECT_NAME=%s\n' "${raw}" > "${TEST_DIR}/n${i}/daaf-docker/environment_settings.txt"
            export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/n${i}/calls.log"
            cd "${TEST_DIR}/n${i}"
            run bash "${REPO_ROOT}/scripts/host/install.sh"
            echo "raw=[${raw}] norm=${norm} compose=${withcompose}"
            grep -Fxq "NOTE: Using these settings from daaf-docker/environment_settings.txt:" <<< "${output}"
            grep -Fxq "        DAAF_PROJECT_NAME=${raw}" <<< "${output}"
            grep -Fxq "      Docker Compose uses the project name '${norm}' for '${raw}'." <<< "${output}"
            assert_output --partial "Downloading"
            # Exactly one volume checked: the normalized project's.
            [ "$(grep -c '^volume inspect ' "${MOCK_INSTALL_CALL_LOG}")" = "1" ]
            grep -Fxq "volume inspect ${norm}_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
            # Compose receives the normalized name (it would normalize the raw one the same way).
            grep -Fxq "compose build --progress plain | P=${norm} M=<unset> L=<unset> V=<unset> D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
        done
    done
}

@test "install.sh #45 ISSUE-1: the case-2 refusal holds again for 'x ', '\"x', 'x # mine' and 'Work' (review 44q rows 45/49/53), and case 1 warns for them" {
    export DAAF_NESTED=1
    install_log_curl
    MOCK_INSTALL_VOLUMES="daaf_daaf-data x_daaf-data xmine_daaf-data work_daaf-data"
    export MOCK_INSTALL_VOLUMES
    i=0
    for pair in 'x |x' '"x|x' 'x # mine|xmine' 'Work|work'; do
        raw="${pair%|*}"
        norm="${pair##*|}"
        i=$((i + 1))
        mkdir -p "${TEST_DIR}/r${i}/daaf-docker"
        printf 'DAAF_PROJECT_NAME=%s\n' "${raw}" > "${TEST_DIR}/r${i}/daaf-docker/environment_settings.txt"
        cd "${TEST_DIR}/r${i}"
        run bash "${REPO_ROOT}/scripts/host/install.sh"
        echo "case 2: raw=[${raw}] norm=${norm}"
        [ "${status}" -eq 1 ]
        assert_output --partial "WARNING: A DAAF installation using Docker volume '${norm}_daaf-data' (project '${norm}')"
        grep -Exq -- "  DAAF_PROJECT_NAME=${norm} DAAF_FORCE_REINSTALL=1 bash -c \"\\\$\\(curl -fsSL ${INSTALL_URL_RE}\\)\"" <<< "${output}"
        refute_output --partial "[1/4]"
        [ ! -f "${TEST_DIR}/curl_log.txt" ]
        # Same folder with its compose file: the case-1 WARNING names the same volume.
        create_fake_compose_file "${TEST_DIR}/r${i}/daaf-docker"
        run bash "${REPO_ROOT}/scripts/host/install.sh"
        echo "case 1: raw=[${raw}] norm=${norm}"
        [ "${status}" -eq 1 ]
        grep -Fxq "         (Docker volume '${norm}_daaf-data', project '${norm}')" <<< "${output}"
        grep -Exq -- "  DAAF_PROJECT_NAME=${norm} DAAF_FORCE_REINSTALL=1 bash -c \"\\\$\\(curl -fsSL ${INSTALL_URL_RE}\\)\"" <<< "${output}"
        [ ! -f "${TEST_DIR}/curl_log.txt" ]
    done
    # The reviewer's exact volume set (no xmine_daaf-data): 'x # mine' is project
    # xmine, whose volume is absent, so this is a fresh install of xmine -- Compose
    # would create xmine_daaf-data and touch neither existing install.
    MOCK_INSTALL_VOLUMES="daaf_daaf-data x_daaf-data"
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    MOCK_DOCKER_COMPOSE_EXIT=1
    mkdir -p "${TEST_DIR}/r49/daaf-docker"
    printf 'DAAF_PROJECT_NAME=x # mine\n' > "${TEST_DIR}/r49/daaf-docker/environment_settings.txt"
    cd "${TEST_DIR}/r49"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    refute_output --partial "already exists, probably installed from"
    grep -Fxq "volume inspect xmine_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    grep -Fxq "compose build --progress plain | P=xmine M=<unset> L=<unset> V=<unset> D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
}

@test "install.sh #45 ISSUE-1: a shell project name is normalized too, the NOTE says so, and a new settings file is seeded with the normalized name" {
    unset DAAF_BRANCH
    export DAAF_PROJECT_NAME="Work"
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    grep -Fxq "NOTE: Docker Compose uses the project name 'work' for 'Work'." <<< "${output}"
    refute_output --partial "Using these settings from"
    grep -Fxq "volume inspect work_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    [ "$(grep '^compose ' "${MOCK_INSTALL_CALL_LOG}" | grep -vc ' | P=work M=<unset> L=<unset> V=<unset> D=<unset>$' || true)" = "0" ]
    # Seeded normalized: backup/restore derive the volume name from the raw value.
    run grep -E '^DAAF_PROJECT_NAME=' "${TEST_DIR}/daaf-docker/environment_settings.txt"
    [ "${output}" = "DAAF_PROJECT_NAME=work" ]
}

@test "install.sh #47 (45q NIT-1): a non-ASCII letter is dropped, not lowercased -- Kelvin sign + 'x' is project 'x' (file and shell; twin of Pester)" {
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    MOCK_INSTALL_VOLUMES=""
    export MOCK_INSTALL_VOLUMES
    # U+212A (KELVIN SIGN) as its UTF-8 bytes, so this file stays ASCII. Lowercased
    # with Unicode rules it would be 'k'; both twins drop it, so the project is 'x'.
    raw="$(printf '\342\204\252x')"
    for src in file shell; do
        mkdir -p "${TEST_DIR}/k_${src}/daaf-docker"
        export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/k_${src}/calls.log"
        if [ "${src}" = "file" ]; then
            unset DAAF_PROJECT_NAME
            printf 'DAAF_PROJECT_NAME=%s\n' "${raw}" > "${TEST_DIR}/k_${src}/daaf-docker/environment_settings.txt"
        else
            export DAAF_PROJECT_NAME="${raw}"
        fi
        cd "${TEST_DIR}/k_${src}"
        run bash "${REPO_ROOT}/scripts/host/install.sh"
        echo "src=${src}"
        grep -Fq "Docker Compose uses the project name 'x' for '${raw}'." <<< "${output}"
        [ "$(grep -c '^volume inspect ' "${MOCK_INSTALL_CALL_LOG}")" = "1" ]
        grep -Fxq "volume inspect x_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
        grep -Fxq "compose build --progress plain | P=x M=<unset> L=<unset> V=<unset> D=<unset>" "${MOCK_INSTALL_CALL_LOG}"
    done
}

@test "install.sh #45 ISSUE-1: a name that normalizes to nothing is refused before anything is downloaded (file and shell, with and without a compose file)" {
    export DAAF_NESTED=1
    install_log_curl
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    i=0
    for src in file shell; do
        for withcompose in no yes; do
            i=$((i + 1))
            mkdir -p "${TEST_DIR}/e${i}"
            export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/e${i}/calls.log"
            if [ "${withcompose}" = "yes" ]; then
                mkdir -p "${TEST_DIR}/e${i}/daaf-docker"
                create_fake_compose_file "${TEST_DIR}/e${i}/daaf-docker"
            fi
            if [ "${src}" = "file" ]; then
                val="___"
                unset DAAF_PROJECT_NAME
                mkdir -p "${TEST_DIR}/e${i}/daaf-docker"
                printf 'DAAF_PROJECT_NAME=%s\n' "${val}" > "${TEST_DIR}/e${i}/daaf-docker/environment_settings.txt"
            else
                val="@@"
                export DAAF_PROJECT_NAME="${val}"
            fi
            cd "${TEST_DIR}/e${i}"
            run bash "${REPO_ROOT}/scripts/host/install.sh"
            echo "src=${src} compose=${withcompose} val=${val}"
            [ "${status}" -eq 1 ]
            grep -Fxq "ERROR: DAAF_PROJECT_NAME='${val}' cannot be used as a Docker Compose" <<< "${output}"
            grep -Fxq "       project name. A project name may use lowercase letters, digits, '-'" <<< "${output}"
            grep -Fxq "       and '_', and must start with a letter or digit." <<< "${output}"
            grep -Fxq "       Nothing has been downloaded or changed." <<< "${output}"
            if [ "${src}" = "file" ]; then
                grep -Fxq "       (This value was read from daaf-docker/environment_settings.txt.)" <<< "${output}"
            else
                refute_output --partial "(This value was read from"
            fi
            refute_output --partial "[1/4]"
            refute_output --partial "NOTE: Using these settings"
            [ ! -f "${TEST_DIR}/curl_log.txt" ]
            # Stopped before the volume check and before any compose call.
            [ ! -f "${MOCK_INSTALL_CALL_LOG}" ]
        done
    done
}

@test "install.sh #45 ISSUE-2: with a settings-file project, every failure-path command carries -p and every re-run text names the project" {
    export DAAF_NESTED=1
    sleep() { true; }
    export -f sleep
    install_named_folder
    MOCK_INSTALL_VOLUMES=""
    export MOCK_INSTALL_VOLUMES
    cd "${TEST_DIR}"
    compose_f="${TEST_DIR}/daaf-docker/docker-compose.yml"
    retry="(set DAAF_PROJECT_NAME=x, and DAAF_FORCE_REINSTALL=1 if prompted)."
    for fail in " build --progress" " up -d" "exec -T daaf-docker true" "git clone" "cp -a /tmp/daaf-clone" "test -f /daaf/CLAUDE.md"; do
        export MOCK_INSTALL_FAIL_ON="${fail}"
        run bash "${REPO_ROOT}/scripts/host/install.sh"
        echo "fail=[${fail}]"
        [ "${status}" -eq 1 ]
        case "${fail}" in
            " build --progress")
                grep -Fxq "You can safely re-run this installer to retry ${retry}" <<< "${output}"
                grep -Exq -- "  DAAF_PROJECT_NAME=x DAAF_DIAG_BUILD=1 bash -c \"\\\$\\(curl -fsSL ${INSTALL_URL_RE}\\)\"" <<< "${output}" ;;
            " up -d")
                grep -Fxq "You can safely re-run this installer to retry ${retry}" <<< "${output}" ;;
            "exec -T daaf-docker true")
                grep -Fxq "  DAAF_PORT_MARIMO=3101 DAAF_PORT_LOGVIEWER=3102 DAAF_PORT_VSCODE=3103 docker compose -p x -f ${compose_f} up -d" <<< "${output}" ;;
            "git clone")
                [ "$(grep -Fxc "  docker compose -p x -f ${compose_f} exec -T daaf-docker \\" <<< "${output}")" = "2" ]
                grep -Fxq "You can also safely re-run this installer to retry from scratch ${retry}" <<< "${output}" ;;
            "cp -a /tmp/daaf-clone")
                [ "$(grep -Fxc "  docker compose -p x -f ${compose_f} exec -T daaf-docker \\" <<< "${output}")" = "1" ]
                grep -Fxq "You can also safely re-run this installer to retry from scratch ${retry}" <<< "${output}" ;;
            "test -f /daaf/CLAUDE.md")
                grep -Fxq "  docker compose -p x exec daaf-docker bash" <<< "${output}" ;;
        esac
        # No printed compose command without the project, no bare retry text.
        refute_output --regexp 'docker compose (-f|exec|down|up)'
        refute_output --partial "(set DAAF_FORCE_REINSTALL=1 if prompted)"
    done
}

@test "install.sh #45 ISSUE-2: a shell project that is seeded -- the recreate-failure and final-summary commands carry -p" {
    unset DAAF_BRANCH
    export DAAF_PROJECT_NAME="x"
    export MOCK_INSTALL_FAIL_ON="--force-recreate"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    assert_success
    assert_output --partial "Could not restart the container to apply the seeded settings"
    grep -Fxq "        docker compose -p x down" <<< "${output}"
    grep -Fxq "  docker compose -p x exec daaf-docker bash   # enter the container" <<< "${output}"
    refute_output --regexp 'docker compose (-f|exec|down|up)'
}

@test "install.sh #45 ISSUE-2: for the default project every printed command and re-run text is unchanged (no -p)" {
    unset DAAF_BRANCH
    export DAAF_NESTED=1
    sleep() { true; }
    export -f sleep
    MOCK_INSTALL_VOLUMES=""
    export MOCK_INSTALL_VOLUMES
    cd "${TEST_DIR}"
    compose_f="${TEST_DIR}/daaf-docker/docker-compose.yml"
    retry="(set DAAF_FORCE_REINSTALL=1 if prompted)."
    # --force-recreate last: only then is there still no settings file to seed.
    for fail in " build --progress" " up -d" "exec -T daaf-docker true" "git clone" "cp -a /tmp/daaf-clone" "test -f /daaf/CLAUDE.md" "--force-recreate"; do
        export MOCK_INSTALL_FAIL_ON="${fail}"
        run bash "${REPO_ROOT}/scripts/host/install.sh"
        echo "fail=[${fail}]"
        case "${fail}" in
            " build --progress")
                grep -Fxq "You can safely re-run this installer to retry ${retry}" <<< "${output}"
                grep -Exq -- "  DAAF_DIAG_BUILD=1 bash -c \"\\\$\\(curl -fsSL ${INSTALL_URL_RE}\\)\"" <<< "${output}" ;;
            " up -d")
                grep -Fxq "You can safely re-run this installer to retry ${retry}" <<< "${output}" ;;
            "exec -T daaf-docker true")
                grep -Fxq "  docker compose -f ${compose_f} up -d" <<< "${output}" ;;
            "git clone")
                [ "$(grep -Fxc "  docker compose -f ${compose_f} exec -T daaf-docker \\" <<< "${output}")" = "2" ]
                grep -Fxq "You can also safely re-run this installer to retry from scratch ${retry}" <<< "${output}" ;;
            "cp -a /tmp/daaf-clone")
                [ "$(grep -Fxc "  docker compose -f ${compose_f} exec -T daaf-docker \\" <<< "${output}")" = "1" ]
                grep -Fxq "You can also safely re-run this installer to retry from scratch ${retry}" <<< "${output}" ;;
            "test -f /daaf/CLAUDE.md")
                grep -Fxq "  docker compose exec daaf-docker bash" <<< "${output}" ;;
            "--force-recreate")
                assert_success
                grep -Fxq "        docker compose down" <<< "${output}"
                grep -Fxq "  docker compose exec daaf-docker bash   # enter the container" <<< "${output}" ;;
        esac
        refute_output --partial "docker compose -p"
        refute_output --partial "DAAF_PROJECT_NAME="
        refute_output --partial "NOTE: Using these settings"
    done
}

@test "install.sh #45 ISSUE-2: ports set for the default project ride on the printed up -d command (no -p)" {
    export DAAF_PORT_MARIMO="3101"
    export MOCK_INSTALL_FAIL_ON="exec -T daaf-docker true"
    export DAAF_NESTED=1
    sleep() { true; }
    export -f sleep
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    grep -Fxq "  DAAF_PORT_MARIMO=3101 docker compose -f ${TEST_DIR}/daaf-docker/docker-compose.yml up -d" <<< "${output}"
}

@test "install.sh #45 SUGGESTION-1: a shell value wins over the settings file for ALL FIVE keys" {
    install_named_folder
    printf '%s\n' "DAAF_DEV=1" >> "${TEST_DIR}/daaf-docker/environment_settings.txt"
    export DAAF_PROJECT_NAME="y"
    export DAAF_PORT_MARIMO="4001"
    export DAAF_PORT_LOGVIEWER="4002"
    export DAAF_PORT_VSCODE="4003"
    export DAAF_DEV="0"
    MOCK_INSTALL_VOLUMES="y_daaf-data x_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_FORCE_REINSTALL=1
    export DAAF_NESTED=1
    MOCK_DOCKER_COMPOSE_EXIT=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    # Nothing was adopted, so no NOTE.
    refute_output --partial "NOTE: Using these settings"
    grep -Fxq "volume inspect y_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    run grep -c "x_daaf-data" "${MOCK_INSTALL_CALL_LOG}"
    [ "${output}" = "0" ]
    grep -Fxq "compose build --progress plain | P=y M=4001 L=4002 V=4003 D=0" "${MOCK_INSTALL_CALL_LOG}"
    [ "$(grep '^compose ' "${MOCK_INSTALL_CALL_LOG}" | grep -vc ' | P=y M=4001 L=4002 V=4003 D=0$' || true)" = "0" ]
}

@test "install.sh #45 SUGGESTION-2: the case-1 WARNING says when the folder has no environment_settings.txt (first line unchanged)" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    expected="$(printf '%s\n' "WARNING: An existing DAAF installation was detected." \
        "         (Docker volume 'daaf_daaf-data', project 'daaf')" \
        "         This folder has no environment_settings.txt, so the project name comes" \
        "         from your shell (default 'daaf'). If you meant to install a separate" \
        "         copy here, set DAAF_PROJECT_NAME (and its ports) again first.")"
    [ "$(grep -A4 -Fx 'WARNING: An existing DAAF installation was detected.' <<< "${output}")" = "${expected}" ]
    # With a settings file in the folder the lines are not printed.
    printf '%s\n' "# my real API keys" > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    assert_output --partial "WARNING: An existing DAAF installation was detected."
    refute_output --partial "This folder has no environment_settings.txt"
}

@test "install.sh #45 SUGGESTION-3: one NOTE lists the adopted settings before the decision; none for a template-seeded file or when nothing is adopted" {
    mkdir -p "${TEST_DIR}/daaf-docker"
    create_fake_compose_file "${TEST_DIR}/daaf-docker"
    # An empty adopted value changes nothing for Compose and is not listed.
    printf '%s\n' "# keys" "DAAF_PROJECT_NAME=x" "DAAF_PORT_MARIMO=3101" "DAAF_PORT_LOGVIEWER=" "DAAF_DEV=1" \
        > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    MOCK_INSTALL_VOLUMES="x_daaf-data"
    export MOCK_INSTALL_VOLUMES
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    expected="$(printf '%s\n' "NOTE: Using these settings from daaf-docker/environment_settings.txt:" \
        "        DAAF_PROJECT_NAME=x" "        DAAF_PORT_MARIMO=3101" "        DAAF_DEV=1" "")"
    [ "$(grep -A4 -Fx 'NOTE: Using these settings from daaf-docker/environment_settings.txt:' <<< "${output}")" = "${expected}" ]
    [ "$(grep -c '^NOTE: Using these settings' <<< "${output}")" = "1" ]
    refute_output --partial "Docker Compose uses the project name"
    # Printed before the existing-install decision.
    note_line="$(grep -n '^NOTE: Using these settings' <<< "${output}" | cut -d: -f1)"
    warn_line="$(grep -n '^WARNING: An existing DAAF installation was detected.' <<< "${output}" | cut -d: -f1)"
    [ "${note_line}" -lt "${warn_line}" ]
    # CI-shaped: the shipped template (bridged keys commented out) plus an active
    # DAAF_BRANCH, as the seeder writes it: nothing adopted, no NOTE.
    cp "${REPO_ROOT}/scripts/host/environment_settings_example.txt" "${TEST_DIR}/daaf-docker/environment_settings.txt"
    printf '%s\n' "DAAF_BRANCH=main" >> "${TEST_DIR}/daaf-docker/environment_settings.txt"
    MOCK_INSTALL_VOLUMES="daaf_daaf-data"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    [ "${status}" -eq 1 ]
    refute_output --partial "NOTE: Using these settings"
    refute_output --partial "This folder has no environment_settings.txt"
    grep -Fxq "         (Docker volume 'daaf_daaf-data', project 'daaf')" <<< "${output}"
}

@test "install.sh #45 NIT-1: a settings file that cannot be read stops with a plain ERROR before anything is downloaded, even when the shell supplies every key" {
    [ "$(id -u)" != "0" ] || skip "root can open a mode-000 file"
    mkdir -p "${TEST_DIR}/daaf-docker"
    printf 'DAAF_PROJECT_NAME=x\n' > "${TEST_DIR}/daaf-docker/environment_settings.txt"
    chmod 000 "${TEST_DIR}/daaf-docker/environment_settings.txt"
    export DAAF_PROJECT_NAME="y"
    export DAAF_PORT_MARIMO="4001"
    export DAAF_PORT_LOGVIEWER="4002"
    export DAAF_PORT_VSCODE="4003"
    export DAAF_DEV="0"
    install_log_curl
    export MOCK_INSTALL_CALL_LOG="${TEST_DIR}/calls.log"
    export DAAF_NESTED=1
    cd "${TEST_DIR}"
    run bash "${REPO_ROOT}/scripts/host/install.sh"
    chmod 600 "${TEST_DIR}/daaf-docker/environment_settings.txt"
    [ "${status}" -eq 1 ]
    expected="$(printf '%s\n' "ERROR: Could not read daaf-docker/environment_settings.txt. Check its" \
        "       permissions, and close any program that has it open, then run the" \
        "       installer again. Nothing has been downloaded or changed.")"
    [ "$(grep -A2 -Fx 'ERROR: Could not read daaf-docker/environment_settings.txt. Check its' <<< "${output}")" = "${expected}" ]
    refute_output --partial "Permission denied"
    refute_output --partial "[1/4]"
    [ ! -f "${TEST_DIR}/curl_log.txt" ]
    [ ! -f "${MOCK_INSTALL_CALL_LOG}" ]
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
