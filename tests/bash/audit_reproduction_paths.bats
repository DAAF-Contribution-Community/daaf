#!/usr/bin/env bats
# ============================================================================
# Focused tests for audit_reproduction_paths.py -- bounded RV path containment
# ============================================================================

load 'test_helper'

setup() {
    ORIGINAL_DIR="$(pwd)"
    TEST_WORKSPACE="${REPO_ROOT}/scripts/scratch/audit-reproduction-paths-${BATS_TEST_NUMBER:-0}-$$"
    SCRIPTS_ROOT="${TEST_WORKSPACE}/scripts"
    ORIGINAL_ROOT="${TEST_WORKSPACE}/original-project"
    EXPECTED_ROOT="${TEST_WORKSPACE}/reproduction-project"
    UTILITY="${REPO_ROOT}/scripts/audit_reproduction_paths.py"
    mkdir -p "${SCRIPTS_ROOT}"
    cd "${TEST_WORKSPACE}" || return 1
    export ORIGINAL_DIR TEST_WORKSPACE SCRIPTS_ROOT ORIGINAL_ROOT EXPECTED_ROOT UTILITY
}

teardown() {
    cd "${ORIGINAL_DIR}" || true
    rm -rf "${TEST_WORKSPACE}"
}

@test "clean mixed Python and R scripts pass without being rewritten" {
    mkdir -p "${SCRIPTS_ROOT}/stage5_fetch" "${SCRIPTS_ROOT}/stage6_clean"
    cat > "${SCRIPTS_ROOT}/stage5_fetch/01_fetch.py" <<PY
from pathlib import Path
PROJECT_DIR = Path("${EXPECTED_ROOT}").resolve()  # canonical safe suffix
print(PROJECT_DIR)
PY
    cat > "${SCRIPTS_ROOT}/stage6_clean/01_clean.R" <<R
PROJECT_DIR <- file.path("${TEST_WORKSPACE}", "reproduction-project")
cat(PROJECT_DIR, "\\n")
R
    local before_python before_r
    before_python="$(sha256sum "${SCRIPTS_ROOT}/stage5_fetch/01_fetch.py")"
    before_r="$(sha256sum "${SCRIPTS_ROOT}/stage6_clean/01_clean.R")"

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"files_scanned": 2'* ]]
    [[ "${output}" == *'"issues": []'* ]]
    [[ "${output}" == *"does not prove arbitrary dynamically constructed paths safe"* ]]
    local report_json="${output}"
    run jq -e '.overall == "MATCH" and .files_scanned == 2' <<< "${report_json}"
    [ "${status}" -eq 0 ]
    [ "$(sha256sum "${SCRIPTS_ROOT}/stage5_fetch/01_fetch.py")" = "${before_python}" ]
    [ "$(sha256sum "${SCRIPTS_ROOT}/stage6_clean/01_clean.R")" = "${before_r}" ]
}

@test "missing canonical PROJECT_DIR assignment fails with file evidence" {
    cat > "${SCRIPTS_ROOT}/01_missing.py" <<'PY'
print("no project assignment")
PY

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"code": "MISSING_PROJECT_DIR_ASSIGNMENT"'* ]]
    [[ "${output}" == *'"file": "01_missing.py"'* ]]
    [[ "${output}" == *'"line": 1'* ]]
    [[ "${output}" == *'"line_end": 1'* ]]
}

@test "multiple canonical assignments fail as ambiguous with every assignment line" {
    cat > "${SCRIPTS_ROOT}/01_multiple.R" <<R
PROJECT_DIR <- "${EXPECTED_ROOT}"
PROJECT_DIR = file.path("${EXPECTED_ROOT}")
R

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"code": "AMBIGUOUS_PROJECT_DIR_ASSIGNMENT"'* ]]
    [[ "${output}" == *'"line": 1'* ]]
    [[ "${output}" == *'"line": 2'* ]]
    [[ "${output}" == *"does not trust the first assignment"* ]]
}

@test "wrong canonical assignment fails with file line and resolved-root evidence" {
    local wrong_root="${TEST_WORKSPACE}/wrong-project"
    cat > "${SCRIPTS_ROOT}/01_wrong.py" <<PY
PROJECT_DIR = "${wrong_root}"
PY

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"code": "WRONG_PROJECT_DIR_ASSIGNMENT"'* ]]
    [[ "${output}" == *'"file": "01_wrong.py"'* ]]
    [[ "${output}" == *'"line": 1'* ]]
    [[ "${output}" == *"${wrong_root}"* ]]
}

@test "exact original-root residue in executable source fails even when assignment is correct" {
    cat > "${SCRIPTS_ROOT}/01_residue.R" <<R
PROJECT_DIR <- "${EXPECTED_ROOT}"
message("legacy location: ${ORIGINAL_ROOT}/data/raw")
R

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"code": "ORIGINAL_ROOT_RESIDUE"'* ]]
    [[ "${output}" == *'"file": "01_residue.R"'* ]]
    [[ "${output}" == *'"line": 2'* ]]
    [[ "${output}" == *"legacy location: ${ORIGINAL_ROOT}/data/raw"* ]]
}

@test "authentic original-root paths only in immutable execution logs pass with informational evidence" {
    cat > "${SCRIPTS_ROOT}/01_logged.py" <<PY
from pathlib import Path
PROJECT_DIR = Path("${EXPECTED_ROOT}")
print(PROJECT_DIR)
# EXECUTION LOG
# Command: python3 /daaf/scripts/run_with_capture.sh ${ORIGINAL_ROOT}/scripts/01_logged.py
# cwd: ${ORIGINAL_ROOT}
PY

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 0 ]
    [[ "${output}" == *'"overall": "MATCH"'* ]]
    [[ "${output}" == *'"code": "ORIGINAL_ROOT_LOG_RESIDUE"'* ]]
    [[ "${output}" == *'"issues": []'* ]]
    [[ "${output}" == *'immutable historical execution-log provenance'* ]]
    local report_json="${output}"
    run jq -e '
        .overall == "MATCH" and
        (.informational_evidence | length) == 1 and
        .informational_evidence[0].scope == "IN_SCOPE" and
        .file_assessments[0].assessment == "MATCH"
    ' <<< "${report_json}"
    [ "${status}" -eq 0 ]
}

@test "multiple canonical execution-log boundaries fail closed" {
    cat > "${SCRIPTS_ROOT}/01_ambiguous.R" <<R
PROJECT_DIR <- "${EXPECTED_ROOT}"
# EXECUTION LOG
# historical output
# EXECUTION LOG
# duplicate boundary
R

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"code": "AMBIGUOUS_EXECUTION_LOG_BOUNDARY"'* ]]
    [[ "${output}" == *'"line": 2'* ]]
    [[ "${output}" == *'"line": 4'* ]]
}

@test "validated exclusions preserve in-scope MATCH and excluded issue evidence" {
    cat > "${SCRIPTS_ROOT}/01_in_scope.py" <<PY
PROJECT_DIR = "${EXPECTED_ROOT}"
PY
    cat > "${SCRIPTS_ROOT}/02_excluded.R" <<R
PROJECT_DIR <- "${EXPECTED_ROOT}"
message("legacy executable path: ${ORIGINAL_ROOT}/data/raw")
R

    run python3 "${UTILITY}" \
        "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}" \
        --exclude "02_excluded.R"

    [ "${status}" -eq 0 ]
    local report_json="${output}"
    run jq -e '
        .overall == "MATCH" and
        .files_in_scope == 1 and
        .files_excluded == 1 and
        .scope.included_files == ["01_in_scope.py"] and
        .scope.excluded_files == ["02_excluded.R"] and
        .issues == [] and
        (.excluded_issues | map(.code)) == ["ORIGINAL_ROOT_RESIDUE"] and
        (.file_assessments | map(select(.file == "01_in_scope.py")) | .[0]) == {
            "assessment": "MATCH",
            "file": "01_in_scope.py",
            "informational_evidence": [],
            "issues": [],
            "scope": "IN_SCOPE"
        } and
        (.file_assessments | map(select(.file == "02_excluded.R")) | .[0].scope) == "EXCLUDED" and
        (.file_assessments | map(select(.file == "02_excluded.R")) | .[0].assessment) == "DIVERGED"
    ' <<< "${report_json}"
    [ "${status}" -eq 0 ]
}

@test "invalid exclusion returns unavailable without silently changing scope" {
    cat > "${SCRIPTS_ROOT}/01_valid.py" <<PY
PROJECT_DIR = "${EXPECTED_ROOT}"
PY

    run python3 "${UTILITY}" \
        "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}" \
        --exclude "../01_valid.py"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"code": "INVALID_EXCLUSION"'* ]]
    [[ "${output}" == *'canonical POSIX-style relative path'* ]]
}

@test "empty supported-script tree fails with explicit evidence" {
    printf '%s\n' 'PROJECT_DIR <- "ignored lowercase extension"' > "${SCRIPTS_ROOT}/ignored.r"
    printf '%s\n' 'not a script' > "${SCRIPTS_ROOT}/notes.txt"

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"overall": "DIVERGED"'* ]]
    [[ "${output}" == *'"code": "NO_SUPPORTED_SCRIPTS"'* ]]
    [[ "${output}" == *'"files_scanned": 0'* ]]
}

@test "canonical-looking Path expression with a root-changing suffix fails closed" {
    cat > "${SCRIPTS_ROOT}/01_dynamic.py" <<PY
from pathlib import Path
PROJECT_DIR = Path("${EXPECTED_ROOT}") / "nested"
PY

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 1 ]
    [[ "${output}" == *'"code": "UNRESOLVABLE_PROJECT_DIR_ASSIGNMENT"'* ]]
    [[ "${output}" == *"non-canonical suffix that can change the assigned root"* ]]
    [[ "${output}" == *'"line": 2'* ]]
}

@test "unreadable supported script returns unavailable evidence with file context" {
    cat > "${SCRIPTS_ROOT}/01_unreadable.R" <<R
PROJECT_DIR <- "${EXPECTED_ROOT}"
R
    chmod 000 "${SCRIPTS_ROOT}/01_unreadable.R"

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "${ORIGINAL_ROOT}" "${EXPECTED_ROOT}"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"code": "SCRIPT_UNREADABLE"'* ]]
    [[ "${output}" == *'"file": "01_unreadable.R"'* ]]
    [[ "${output}" == *"Line evidence is unavailable"* ]]
}

@test "relative root invocation is rejected with documented unavailable exit" {
    cat > "${SCRIPTS_ROOT}/01_valid.py" <<PY
PROJECT_DIR = "${EXPECTED_ROOT}"
PY

    run python3 "${UTILITY}" "${SCRIPTS_ROOT}" "relative/original" "${EXPECTED_ROOT}"

    [ "${status}" -eq 2 ]
    [[ "${output}" == *'"overall": "NOT DIRECTLY VERIFIED"'* ]]
    [[ "${output}" == *'"code": "INVALID_ROOT_ARGUMENT"'* ]]
}
