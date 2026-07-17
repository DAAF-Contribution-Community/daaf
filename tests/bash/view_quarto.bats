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

# Install a viewer-specific Docker fake for end-to-end argument, discovery, and
# picker tests. The fake sorts discovery output as the container-side command
# would, logs every argument with visible boundaries, and never needs Docker.
install_viewer_docker_mock() {
    export MOCK_VIEWER_DISCOVERY_OUTPUT="${MOCK_VIEWER_DISCOVERY_OUTPUT:-}"
    export MOCK_VIEWER_DISCOVERY_EXIT="${MOCK_VIEWER_DISCOVERY_EXIT:-0}"
    export MOCK_VIEWER_FILE_EXIT="${MOCK_VIEWER_FILE_EXIT:-0}"
    export MOCK_VIEWER_RENDER_EXIT="${MOCK_VIEWER_RENDER_EXIT:-0}"
    export MOCK_VIEWER_CP_EXIT="${MOCK_VIEWER_CP_EXIT:-0}"
    export MOCK_VIEWER_LOG="${TEST_DIR}/viewer-docker.log"
    : > "${MOCK_VIEWER_LOG}"

    docker() {
        {
            printf 'docker'
            for viewer_arg in "$@"; do
                printf ' <%s>' "${viewer_arg}"
            done
            printf '\n'
        } >> "${MOCK_VIEWER_LOG}"

        case "${1:-}" in
            info)
                return 0
                ;;
            compose)
                case "${2:-}" in
                    ps)
                        printf '%s\n' 'abc123'
                        return 0
                        ;;
                    up)
                        return 0
                        ;;
                    exec)
                        case " $* " in
                            *" test -f "*)
                                return "${MOCK_VIEWER_FILE_EXIT}"
                                ;;
                            *" bash -o pipefail -c "*)
                                if [ "${MOCK_VIEWER_DISCOVERY_EXIT}" -ne 0 ]; then
                                    return "${MOCK_VIEWER_DISCOVERY_EXIT}"
                                fi
                                if [ -n "${MOCK_VIEWER_DISCOVERY_OUTPUT}" ]; then
                                    printf '%s\n' "${MOCK_VIEWER_DISCOVERY_OUTPUT}" | LC_ALL=C sort
                                fi
                                return 0
                                ;;
                            *" quarto render "*)
                                return "${MOCK_VIEWER_RENDER_EXIT}"
                                ;;
                        esac
                        return 0
                        ;;
                    cp)
                        return "${MOCK_VIEWER_CP_EXIT}"
                        ;;
                esac
                ;;
        esac
        return 0
    }
    export -f docker

    # Prevent the real opener from launching while retaining an observable call.
    open_url() {
        printf 'open_url <%s>\n' "$1" >> "${MOCK_VIEWER_LOG}"
    }
    export -f open_url
    export _DAAF_LIB_LOADED=1
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

@test "view_quarto.sh suppresses its standalone pause during dry-run" {
    run grep -F '[ "${DAAF_DRY_RUN:-}" != "1" ]' "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
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

@test "view_quarto.sh: dry-run discovery offers the recursive picker" {
    run env DAAF_DRY_RUN=1 DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 2>&1
    assert_success
    assert_output --partial "Discovering Quarto notebooks under research/"
    assert_output --partial "Searching recursively at every depth."
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

# =========================================================================
# Tier 7 -- Recursive discovery and picker behavior
# =========================================================================

@test "view_quarto.sh recursively discovers a deep notebook and selects it" {
    MOCK_VIEWER_DISCOVERY_OUTPUT='research/2026-07-15_AdHoc_Quarto_Viewer_Sample/output/analysis/2026-07-15a_Quarto_Viewer_Sample.qmd'
    install_viewer_docker_mock

    run bash -c 'printf "1\n" | DAAF_NESTED=1 bash "$1"' _ \
        "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    assert_output --partial "1) research/2026-07-15_AdHoc_Quarto_Viewer_Sample/output/analysis/2026-07-15a_Quarto_Viewer_Sample.qmd"
    assert_output --partial "Rendering research/2026-07-15_AdHoc_Quarto_Viewer_Sample/output/analysis/2026-07-15a_Quarto_Viewer_Sample.qmd"
    grep -F '<bash> <-o> <pipefail> <-c> <cd /daaf && find research -type f -name "*.qmd" -print | LC_ALL=C sort>' "${MOCK_VIEWER_LOG}"
    [ "$(grep -c '<quarto> <render>' "${MOCK_VIEWER_LOG}")" -eq 1 ]
    [ "$(grep -c 'compose> <cp>' "${MOCK_VIEWER_LOG}")" -eq 1 ]
    [ "$(grep -c 'open_url' "${MOCK_VIEWER_LOG}")" -eq 1 ]
}

@test "view_quarto.sh picker uses C-locale order and can select first and last" {
    MOCK_VIEWER_DISCOVERY_OUTPUT=$'research/z/output/analysis/z.qmd\nresearch/a/output/analysis/a.qmd'
    install_viewer_docker_mock

    run bash -c 'printf "1\n" | DAAF_NESTED=1 bash "$1"' _ \
        "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    assert_output --partial "Rendering research/a/output/analysis/a.qmd"

    : > "${MOCK_VIEWER_LOG}"
    run bash -c 'printf "2\n" | DAAF_NESTED=1 bash "$1"' _ \
        "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    assert_output --partial "Rendering research/z/output/analysis/z.qmd"
}

@test "view_quarto.sh picker reprompts without rediscovery after malformed huge and out-of-range input" {
    MOCK_VIEWER_DISCOVERY_OUTPUT=$'research/a.qmd\nresearch/b.qmd'
    install_viewer_docker_mock

    run bash -c 'printf "%s\n" "+1" "1.0" "01" "999999999999999999999999999999999999" "3" "2" | DAAF_NESTED=1 bash "$1"' _ \
        "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    assert_output --partial "Invalid selection. Enter a number from 1 to 2, or 0 to cancel."
    assert_output --partial "Rendering research/b.qmd"
    [ "$(grep -c '<bash> <-o> <pipefail> <-c> <cd /daaf && find research -type f' "${MOCK_VIEWER_LOG}")" -eq 1 ]
}

@test "view_quarto.sh picker cancels cleanly on zero blank q Q and EOF" {
    MOCK_VIEWER_DISCOVERY_OUTPUT='research/a.qmd'
    install_viewer_docker_mock

    local input_case
    for input_case in '0' '' 'q' 'Q' '__EOF__'; do
        : > "${MOCK_VIEWER_LOG}"
        if [ "${input_case}" = '__EOF__' ]; then
            run bash -c 'DAAF_NESTED=1 bash "$1" < /dev/null' _ \
                "${REPO_ROOT}/scripts/host/view_quarto.sh"
        else
            run bash -c 'printf "%s\n" "$1" | DAAF_NESTED=1 bash "$2"' _ \
                "${input_case}" "${REPO_ROOT}/scripts/host/view_quarto.sh"
        fi
        assert_success
        assert_output --partial "Quarto notebook selection cancelled."
        ! grep -F '<quarto> <render>' "${MOCK_VIEWER_LOG}"
        ! grep -F 'compose> <cp>' "${MOCK_VIEWER_LOG}"
        ! grep -F 'open_url' "${MOCK_VIEWER_LOG}"
    done
}

@test "view_quarto.sh preserves a selected path with spaces and metacharacters without executing it" {
    local sentinel="${TEST_DIR}/injection-sentinel"
    MOCK_VIEWER_DISCOVERY_OUTPUT='research/odd project/output/analysis/name #?% $(touch INJECTION_SENTINEL); [x].qmd'
    install_viewer_docker_mock

    run bash -c 'printf "1\n" | DAAF_NESTED=1 bash "$1"' _ \
        "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_success
    grep -F '<quarto> <render> </daaf/research/odd project/output/analysis/name #?% $(touch INJECTION_SENTINEL); [x].qmd>' "${MOCK_VIEWER_LOG}"
    grep -F 'open_url <'"${TEST_DIR}"'/quarto_html/name #?% $(touch INJECTION_SENTINEL); [x].html>' "${MOCK_VIEWER_LOG}"
    ! grep -F 'open_url <file://' "${MOCK_VIEWER_LOG}"
    [ ! -e "${sentinel}" ]
    [ ! -e "${TEST_DIR}/INJECTION_SENTINEL" ]
}

@test "view_quarto.sh distinguishes empty discovery from Docker discovery failure" {
    MOCK_VIEWER_DISCOVERY_OUTPUT=''
    install_viewer_docker_mock

    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_failure
    assert_output --partial "No Quarto notebooks (.qmd) found under research/."
    refute_output --partial "Could not discover"

    MOCK_VIEWER_DISCOVERY_EXIT=17
    export MOCK_VIEWER_DISCOVERY_EXIT
    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
    assert_failure
    assert_output --partial "Could not discover Quarto notebooks"
    refute_output --partial "No Quarto notebooks"
}

@test "view_quarto.sh inner discovery pipeline propagates find failure" {
    run bash -o pipefail -c 'find /definitely-missing-daaf-quarto-root -type f -name "*.qmd" -print 2>/dev/null | LC_ALL=C sort'
    assert_failure
}

@test "view_quarto.sh recursively resolves exactly one deep project notebook" {
    MOCK_VIEWER_DISCOVERY_OUTPUT='research/project/output/analysis/deep.qmd'
    install_viewer_docker_mock

    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 'project'
    assert_success
    assert_output --partial "Rendering research/project/output/analysis/deep.qmd"
    grep -F '<bash> <-o> <pipefail> <-c> <cd /daaf && find "research/$1" -type f -name "*.qmd" -print | LC_ALL=C sort>' "${MOCK_VIEWER_LOG}"
    grep -F '<_> <project>' "${MOCK_VIEWER_LOG}"
}

@test "view_quarto.sh reports project discovery failure separately from zero matches" {
    MOCK_VIEWER_DISCOVERY_OUTPUT=''
    install_viewer_docker_mock

    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 'project'
    assert_failure
    assert_output --partial "No Quarto notebook (.qmd) found in project: project"

    MOCK_VIEWER_DISCOVERY_EXIT=23
    export MOCK_VIEWER_DISCOVERY_EXIT
    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 'project'
    assert_failure
    assert_output --partial "Could not search project 'project' for Quarto notebooks"
}

@test "view_quarto.sh refuses sorted recursive project ambiguity" {
    MOCK_VIEWER_DISCOVERY_OUTPUT=$'research/project/z/deep-z.qmd\nresearch/project/a/deep-a.qmd'
    install_viewer_docker_mock

    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" 'project'
    assert_failure
    assert_output --partial "Multiple Quarto notebooks found"
    local a_line z_line
    a_line="$(printf '%s\n' "${output}" | grep -n 'deep-a.qmd' | cut -d: -f1)"
    z_line="$(printf '%s\n' "${output}" | grep -n 'deep-z.qmd' | cut -d: -f1)"
    [ "${a_line}" -lt "${z_line}" ]
    ! grep -F '<quarto> <render>' "${MOCK_VIEWER_LOG}"
}

@test "view_quarto.sh preserves direct-path success and missing-path failure" {
    install_viewer_docker_mock
    local direct='research/odd project/output/analysis/direct [x].qmd'

    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" "${direct}"
    assert_success
    grep -F "<test> <-f> </daaf/${direct}>" "${MOCK_VIEWER_LOG}"
    grep -F "<quarto> <render> </daaf/${direct}>" "${MOCK_VIEWER_LOG}"

    MOCK_VIEWER_FILE_EXIT=1
    export MOCK_VIEWER_FILE_EXIT
    run env DAAF_NESTED=1 bash "${REPO_ROOT}/scripts/host/view_quarto.sh" "${direct}"
    assert_failure
    assert_output --partial "Quarto notebook not found"
}

@test "view_quarto.sh dry-run auto-selects a deep fixture and performs no writes for all input modes" {
    local dry_root="${TEST_DIR}/dry-run-output"
    local deep='research/2026-07-15_Project/output/analysis/deep.qmd'
    local mode_arg

    for mode_arg in '__NOARG__' "${deep}" '2026-07-15_Project'; do
        if [ "${mode_arg}" = '__NOARG__' ]; then
            run env DAAF_DRY_RUN=1 DAAF_NESTED=1 QUARTO_HTML_DIR="${dry_root}" \
                bash "${REPO_ROOT}/scripts/host/view_quarto.sh"
        else
            run env DAAF_DRY_RUN=1 DAAF_NESTED=1 QUARTO_HTML_DIR="${dry_root}" \
                bash "${REPO_ROOT}/scripts/host/view_quarto.sh" "${mode_arg}"
        fi
        assert_success
        assert_output --partial "[DRY-RUN]"
        assert_output --partial "output/analysis"
        [ ! -e "${dry_root}" ]
    done
}
