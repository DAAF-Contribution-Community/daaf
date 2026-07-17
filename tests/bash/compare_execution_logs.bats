#!/usr/bin/env bats
# ============================================================================
# Public-behavior regression tests for compare_execution_logs.py
# ============================================================================
# Each test creates .R fixtures in a unique repo-local scripts/scratch workspace
# and removes that workspace in teardown; no fixture files are written to /tmp.
# ============================================================================

load 'test_helper'

setup() {
    ORIGINAL_DIR="$(pwd)"
    TEST_WORKSPACE="${REPO_ROOT}/scripts/scratch/compare-execution-logs-${BATS_TEST_NUMBER:-0}-$$"
    UTILITY="${REPO_ROOT}/scripts/compare_execution_logs.py"

    mkdir -p "${TEST_WORKSPACE}"
    cd "${TEST_WORKSPACE}" || return 1
    export ORIGINAL_DIR TEST_WORKSPACE UTILITY
}

teardown() {
    cd "${ORIGINAL_DIR}" || true
    rm -rf "${TEST_WORKSPACE}"
}

write_r_fixture() {
    local fixture_path="$1"
    shift
    printf '%s\n' "$@" > "${fixture_path}"
}

report_value() {
    local prefix="$1"
    local line

    while IFS= read -r line; do
        case "${line}" in
            "${prefix}"*)
                printf '%s\n' "${line#"${prefix}"}"
                return 0
                ;;
        esac
    done <<< "${output}"
    return 1
}

@test "consistent R logs exit 0 and report log-only consistency" {
    local original_script="${TEST_WORKSPACE}/matching-original.R"
    local reproduced_script="${TEST_WORKSPACE}/matching-reproduced.R"

    write_r_fixture "${original_script}" \
        'message("fixture only")' \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# shape: (1,234, 12)' \
        '# CP1 VALIDATION: PASSED' \
        '# mean: 42.125' \
        '# 3 assertions passed' \
        '# Warning: fixture warning retained identically'
    write_r_fixture "${reproduced_script}" \
        'message("fixture only")' \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# shape: (1,234, 12)' \
        '# CP1 VALIDATION: PASSED' \
        '# mean: 42.125' \
        '# 3 assertions passed' \
        '# Warning: fixture warning retained identically'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 0 ]
    [ "$(report_value 'Overall: ')" = 'CONSISTENT' ]
    [[ "${output}" == *'Scope: appended execution-log metrics only; output artifacts were not compared.'* ]]
    [[ "${output}" == *'Original: 1234  Reproduced: 1234  Match: YES'* ]]
    [[ "${output}" == *'Original: 12  Reproduced: 12  Match: YES'* ]]
    [[ "${output}" == *'mean: Original=42.125  Reproduced=42.125  Within tolerance: YES'* ]]
    [[ "${output}" == *'CP1: Original=PASSED  Reproduced=PASSED  Match: YES'* ]]
}

@test "reordered uniquely labeled metrics align by normalized identity" {
    local original_script="${TEST_WORKSPACE}/reordered-original.R"
    local reproduced_script="${TEST_WORKSPACE}/reordered-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# training rows: 80' \
        '# shape: (100, 5)' \
        '# columns: 7' \
        '# mean: 9.5' \
        '# median: 8.0' \
        '# training min: 1.0' \
        '# testing min: 2.0'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# testing min: 2.0' \
        '# median: 8.0' \
        '# columns: 7' \
        '# shape: (100, 5)' \
        '# training min: 1.0' \
        '# mean: 9.5' \
        '# training rows: 80'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 0 ]
    [ "$(report_value 'Overall: ')" = 'CONSISTENT' ]
    [[ "${output}" == *'mean: Original=9.5  Reproduced=9.5  Within tolerance: YES'* ]]
    [[ "${output}" == *'median: Original=8.0  Reproduced=8.0  Within tolerance: YES'* ]]
    [[ "${output}" == *'min [occurrence 1]: Original=1.0  Reproduced=1.0  Within tolerance: YES'* ]]
    [[ "${output}" == *'min [occurrence 2]: Original=2.0  Reproduced=2.0  Within tolerance: YES'* ]]
    [[ "${output}" == *'Identity: shape rows; aligned by identity + context'* ]]
    [[ "${output}" == *'Identity: column count; aligned by identity + context'* ]]
}

@test "same numeric values under different labels never match" {
    local original_script="${TEST_WORKSPACE}/different-label-original.R"
    local reproduced_script="${TEST_WORKSPACE}/different-label-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# training rows: 10' \
        '# input columns: 5' \
        '# mean: 7'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# testing rows: 10' \
        '# output columns: 5' \
        '# median: 7'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 1 ]
    [ "$(report_value 'Overall: ')" = 'DIVERGED' ]
    [ "$(report_value 'Matches: ')" = '1' ]
    [ "$(report_value 'Mismatches: ')" = '6' ]
    [[ "${output}" == *'training rows: 10 [occurrence 1]'* ]]
    [[ "${output}" == *'testing rows: 10 [occurrence 2]'* ]]
    [[ "${output}" == *'input columns: 5 [occurrence 1]'* ]]
    [[ "${output}" == *'output columns: 5 [occurrence 2]'* ]]
    [[ "${output}" != *'Original: 10  Reproduced: 10  Match: YES'* ]]
    [[ "${output}" != *'Original: 5  Reproduced: 5  Match: YES'* ]]
    [[ "${output}" == *'mean: Original=7.0  Reproduced=(missing)  Within tolerance: NO'* ]]
    [[ "${output}" == *'median: Original=(missing)  Reproduced=7.0  Within tolerance: NO'* ]]
    [[ "${output}" != *'Original=7.0  Reproduced=7.0  Within tolerance: YES'* ]]
}

@test "duplicate labels without stable occurrence context are inconclusive" {
    local original_script="${TEST_WORKSPACE}/duplicate-original.R"
    local reproduced_script="${TEST_WORKSPACE}/duplicate-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# mean: 1' \
        '# mean: 2'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# mean: 1' \
        '# mean: 2'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCONCLUSIVE (ambiguous duplicate metric identities)' ]
    [ "$(report_value 'Ambiguities: ')" = '1' ]
    [[ "${output}" == *'AMBIGUOUS: mean: duplicate identity lacks distinct stable context'* ]]
    [[ "${output}" != *'mean: Original=1.0  Reproduced=1.0'* ]]
}

@test "agreeing duplicate exit-code lines are ambiguous and exit 3" {
    local original_script="${TEST_WORKSPACE}/duplicate-exit-agree-original.R"
    local reproduced_script="${TEST_WORKSPACE}/duplicate-exit-agree-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# Exit code: 0'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCONCLUSIVE (ambiguous duplicate exit/checkpoint identities)' ]
    [ "$(report_value 'Ambiguities: ')" = '1' ]
    [[ "${output}" == *'Original:   [0, 0] (2 occurrences)'* ]]
    [[ "${output}" == *'AMBIGUOUS: duplicate dedicated exit-code identity; no occurrence was selected.'* ]]
    [[ "${output}" != *'Match: YES'* ]]
}

@test "conflicting duplicate exit-code lines remain ambiguous and exit 3" {
    local original_script="${TEST_WORKSPACE}/duplicate-exit-conflict-original.R"
    local reproduced_script="${TEST_WORKSPACE}/duplicate-exit-conflict-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# Exit code: 1'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCONCLUSIVE (ambiguous duplicate exit/checkpoint identities)' ]
    [[ "${output}" == *'Original:   [0, 1] (2 occurrences)'* ]]
    [[ "${output}" == *'AMBIGUOUS: duplicate dedicated exit-code identity; no occurrence was selected.'* ]]
    [[ "${output}" != *'Overall: DIVERGED'* ]]
}

@test "agreeing duplicate checkpoint IDs are ambiguous and exit 3" {
    local original_script="${TEST_WORKSPACE}/duplicate-checkpoint-agree-original.R"
    local reproduced_script="${TEST_WORKSPACE}/duplicate-checkpoint-agree-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# CP1: PASSED' \
        '# CP1 VALIDATION: PASSED'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# CP1: PASSED'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCONCLUSIVE (ambiguous duplicate exit/checkpoint identities)' ]
    [ "$(report_value 'Ambiguities: ')" = '1' ]
    [[ "${output}" == *'CP1: AMBIGUOUS duplicate checkpoint ID; Original=[PASSED, PASSED] (2 occurrences); Reproduced=[PASSED] (1 occurrence); no occurrence was selected.'* ]]
    [[ "${output}" != *'CP1: Original=PASSED  Reproduced=PASSED  Match: YES'* ]]
}

@test "conflicting duplicate checkpoint IDs remain ambiguous and exit 3" {
    local original_script="${TEST_WORKSPACE}/duplicate-checkpoint-conflict-original.R"
    local reproduced_script="${TEST_WORKSPACE}/duplicate-checkpoint-conflict-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# CP2: PASSED' \
        '# CP2: FAILED'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# CP2: PASSED'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCONCLUSIVE (ambiguous duplicate exit/checkpoint identities)' ]
    [[ "${output}" == *'CP2: AMBIGUOUS duplicate checkpoint ID; Original=[PASSED, FAILED] (2 occurrences); Reproduced=[PASSED] (1 occurrence); no occurrence was selected.'* ]]
    [[ "${output}" != *'Overall: DIVERGED'* ]]
}

@test "divergent R logs exit 1 and identify mismatched evidence" {
    local original_script="${TEST_WORKSPACE}/diverged-original.R"
    local reproduced_script="${TEST_WORKSPACE}/diverged-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# CP2: PASSED' \
        '# median: 12.5'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 1' \
        '# CP2: FAILED' \
        '# median: 13.0'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 1 ]
    [ "$(report_value 'Overall: ')" = 'DIVERGED' ]
    [[ "${output}" == *'CP2: Original=PASSED  Reproduced=FAILED  Match: NO'* ]]
    [[ "${output}" == *'median: Original=12.5  Reproduced=13.0  Within tolerance: NO'* ]]
}

@test "consistent R tidyverse tibble and assertion logs report consistency" {
    local original_script="${TEST_WORKSPACE}/tibble-original.R"
    local reproduced_script="${TEST_WORKSPACE}/tibble-reproduced.R"

    write_r_fixture "${original_script}" \
        'stopifnot(nrow(df) == 1234)' \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# # A tibble: 1,234 × 12' \
        '# CP1 VALIDATION: PASSED' \
        '# 3 assertions passed'
    write_r_fixture "${reproduced_script}" \
        'stopifnot(nrow(df) == 1234)' \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# # A tibble: 1,234 × 12' \
        '# CP1 VALIDATION: PASSED' \
        '# 3 assertions passed'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 0 ]
    [ "$(report_value 'Overall: ')" = 'CONSISTENT' ]
    [[ "${output}" == *'Original: 1234  Reproduced: 1234  Match: YES'* ]]
    [[ "${output}" == *'Original: 12  Reproduced: 12  Match: YES'* ]]
    [[ "${output}" == *'Identity: tibble rows; aligned by identity + context'* ]]
    [[ "${output}" == *'Identity: tibble columns; aligned by identity + context'* ]]
}

@test "divergent R tibble row count and stopifnot failure exit 1" {
    local original_script="${TEST_WORKSPACE}/tibble-diverge-original.R"
    local reproduced_script="${TEST_WORKSPACE}/tibble-diverge-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# # A tibble: 1,234 × 12'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 1' \
        '# # A tibble: 1,200 × 12' \
        '# Error: nrow(df) == 1234 is not TRUE'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 1 ]
    [ "$(report_value 'Overall: ')" = 'DIVERGED' ]
    [[ "${output}" == *'Original: 1234  Reproduced: 1200  Match: NO'* ]]
    [[ "${output}" == *'Reproduced: 0 passed, 1 failed'* ]]
}

@test "consistent .py-named logs exercise the shared extractor and exit 0" {
    local original_script="${TEST_WORKSPACE}/matching-original.py"
    local reproduced_script="${TEST_WORKSPACE}/matching-reproduced.py"

    write_r_fixture "${original_script}" \
        'print("fixture only")' \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# shape: (500, 8)' \
        '# mean: 3.14' \
        '# 2 assertions passed'
    write_r_fixture "${reproduced_script}" \
        'print("fixture only")' \
        '# EXECUTION LOG' \
        '# Exit code: 0' \
        '# shape: (500, 8)' \
        '# mean: 3.14' \
        '# 2 assertions passed'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 0 ]
    [ "$(report_value 'Overall: ')" = 'CONSISTENT' ]
    [[ "${output}" == *'Original: 500  Reproduced: 500  Match: YES'* ]]
    [[ "${output}" == *'Original: 8  Reproduced: 8  Match: YES'* ]]
}

@test "one missing execution log exits 3 as incomplete" {
    local original_script="${TEST_WORKSPACE}/missing-log-original.R"
    local reproduced_script="${TEST_WORKSPACE}/present-log-reproduced.R"

    write_r_fixture "${original_script}" \
        'message("the phrase # EXECUTION LOG appears, but no marker line exists")'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# Exit code: 0'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCOMPLETE (missing execution log)' ]
    [[ "${output}" == *'WARNING: No execution log found in original script.'* ]]
    [[ "${output}" != *'Overall: CONSISTENT'* ]]
}

@test "two missing execution logs exit 3 as incomplete" {
    local original_script="${TEST_WORKSPACE}/both-missing-original.R"
    local reproduced_script="${TEST_WORKSPACE}/both-missing-reproduced.R"

    write_r_fixture "${original_script}" 'message("no execution log")'
    write_r_fixture "${reproduced_script}" 'message("no execution log")'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Overall: ')" = 'INCOMPLETE (missing execution log)' ]
    [[ "${output}" == *'WARNING: No execution log found in original script.'* ]]
    [[ "${output}" == *'WARNING: No execution log found in reproduced script.'* ]]
}

@test "metric-free execution logs exit 3 as inconclusive" {
    local original_script="${TEST_WORKSPACE}/metric-free-original.R"
    local reproduced_script="${TEST_WORKSPACE}/metric-free-reproduced.R"

    write_r_fixture "${original_script}" \
        '# EXECUTION LOG' \
        '# R console started successfully'
    write_r_fixture "${reproduced_script}" \
        '# EXECUTION LOG' \
        '# R console started successfully'

    run python3 "${UTILITY}" "${original_script}" "${reproduced_script}"

    [ "${status}" -eq 3 ]
    [ "$(report_value 'Metrics compared: ')" = '0' ]
    [ "$(report_value 'Overall: ')" = 'INCONCLUSIVE (no comparable metrics found)' ]
}

@test "invalid invocation and unreadable input path exit 2" {
    run python3 "${UTILITY}"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'usage:'* ]]

    run python3 "${UTILITY}" \
        "${TEST_WORKSPACE}/does-not-exist.R" \
        "${TEST_WORKSPACE}/also-does-not-exist.R"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'Error: Original script is not a readable file:'* ]]
}

@test "help publicly documents exact exit statuses and log-only scope" {
    run python3 "${UTILITY}" --help

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'0=CONSISTENT; 1=DIVERGED;'* ]]
    [[ "${output}" == *'2=invalid invocation or input read/parse failure;'* ]]
    [[ "${output}" == *'3=INCOMPLETE or INCONCLUSIVE evidence.'* ]]
    [[ "${output}" == *'never artifact equivalence.'* ]]
}
