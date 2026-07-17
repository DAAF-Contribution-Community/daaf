#!/usr/bin/env bats
# ============================================================================
# Tests for normalize_project_dir.py -- RV-1 Python/R path normalization
# ============================================================================
# Test workspaces stay under scripts/scratch/ so every filesystem artifact remains
# inside DAAF's backup/audit boundary. Teardown removes each isolated workspace.
# ============================================================================

load 'test_helper'

setup() {
    ORIGINAL_DIR="$(pwd)"
    TEST_DIR="${REPO_ROOT}/scripts/scratch/normalize-project-dir-${BATS_TEST_NUMBER:-0}-$$"
    mkdir -p "${TEST_DIR}/scripts"
    cd "${TEST_DIR}" || return 1
    export ORIGINAL_DIR TEST_DIR
}

teardown() {
    cd "${ORIGINAL_DIR}" || true
    rm -rf "${TEST_DIR}"
}

@test "normalizer preserves existing Python Path and string behavior" {
    cat > "${TEST_DIR}/scripts/01_path.py" <<'PY'
from pathlib import Path
PROJECT_DIR = Path("/daaf/research/original")  # keep path comment
print(PROJECT_DIR)
PY
    cat > "${TEST_DIR}/scripts/02_string.py" <<'PY'
PROJECT_DIR = '/daaf/research/original'  # keep string comment
print(PROJECT_DIR)
PY

    local target="${TEST_DIR}/reproduction"
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    assert_output --partial "Files scanned     : 2"
    assert_output --partial "RESULT: 2 normalized, 0 unchanged, 0 no match"
    grep -F "PROJECT_DIR = Path(\"${target}\")  # keep path comment" \
        "${TEST_DIR}/scripts/01_path.py"
    grep -F "PROJECT_DIR = '${target}'  # keep string comment" \
        "${TEST_DIR}/scripts/02_string.py"
}

@test "normalizer rewrites R quoted strings with either assignment operator" {
    cat > "${TEST_DIR}/scripts/01_arrow.R" <<'R'
PROJECT_DIR <- '/daaf/research/original'  # keep arrow comment
cat(PROJECT_DIR, "\n")
R
    cat > "${TEST_DIR}/scripts/02_equals.R" <<'R'
  PROJECT_DIR = "/daaf/research/original" # keep equals comment
cat(PROJECT_DIR, "\n")
R

    local target="${TEST_DIR}/reproduction"
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    assert_output --partial "Files scanned     : 2"
    assert_output --partial "RESULT: 2 normalized, 0 unchanged, 0 no match"
    grep -F "PROJECT_DIR <- '${target}'  # keep arrow comment" \
        "${TEST_DIR}/scripts/01_arrow.R"
    grep -F "  PROJECT_DIR = \"${target}\" # keep equals comment" \
        "${TEST_DIR}/scripts/02_equals.R"
}

@test "normalizer rewrites canonical R file.path expressions deterministically" {
    cat > "${TEST_DIR}/scripts/01_file_path.R" <<'R'
BASE_DIR <- "/daaf"
PROJECT_DIR <- file.path(BASE_DIR, "research", "original")  # keep file.path comment
cat(PROJECT_DIR, "\n")
R
    cat > "${TEST_DIR}/scripts/02_file_path_equals.R" <<'R'
PROJECT_DIR = file.path('/daaf', 'research/original') # keep equals comment
cat(PROJECT_DIR, "\n")
R

    local target="${TEST_DIR}/reproduction"
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    assert_output --partial "RESULT: 2 normalized, 0 unchanged, 0 no match"
    grep -F "PROJECT_DIR <- file.path(\"${target}\")  # keep file.path comment" \
        "${TEST_DIR}/scripts/01_file_path.R"
    grep -F "PROJECT_DIR = file.path('${target}') # keep equals comment" \
        "${TEST_DIR}/scripts/02_file_path_equals.R"
}

@test "normalizer processes mixed Python and R trees in one report" {
    mkdir -p "${TEST_DIR}/scripts/stage5_fetch" "${TEST_DIR}/scripts/stage6_clean"
    cat > "${TEST_DIR}/scripts/stage5_fetch/01_fetch.R" <<'R'
PROJECT_DIR <- "/daaf/research/original"
R
    cat > "${TEST_DIR}/scripts/stage6_clean/01_clean.py" <<'PY'
from pathlib import Path
PROJECT_DIR = Path("/daaf/research/original")
PY

    local target="${TEST_DIR}/reproduction"
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    assert_output --partial "Files scanned     : 2"
    assert_output --partial "stage5_fetch/01_fetch.R"
    assert_output --partial "stage6_clean/01_clean.py"
    assert_output --partial "RESULT: 2 normalized, 0 unchanged, 0 no match (out of 2 files scanned)"
}

@test "normalizer leaves already-normalized and unmatched supported scripts unchanged" {
    local target="${TEST_DIR}/reproduction"
    cat > "${TEST_DIR}/scripts/01_already.R" <<R
PROJECT_DIR <- "${target}"
R
    cat > "${TEST_DIR}/scripts/02_no_match.R" <<'R'
BASE_DIR <- "/daaf"
message("No project assignment here")
R

    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    assert_output --partial "Normalized : 0"
    assert_output --partial "Unchanged  : 1"
    assert_output --partial "No match   : 1"
    assert_output --partial "RESULT: 0 normalized, 1 unchanged, 1 no match"
}

@test "normalizer changes only the first canonical PROJECT_DIR assignment" {
    cat > "${TEST_DIR}/scripts/01_first_only.R" <<'R'
PROJECT_DIR <- "/daaf/research/first"
PROJECT_DIR <- "/daaf/research/second"
R

    local target="${TEST_DIR}/reproduction"
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    [ "$(grep -F -c "PROJECT_DIR <- \"${target}\"" "${TEST_DIR}/scripts/01_first_only.R")" -eq 1 ]
    [ "$(grep -F -c 'PROJECT_DIR <- "/daaf/research/second"' "${TEST_DIR}/scripts/01_first_only.R")" -eq 1 ]
}

@test "normalizer safely escapes quote and backslash target paths for Python and R" {
    cat > "${TEST_DIR}/scripts/01_path.py" <<'PY'
from pathlib import Path
PROJECT_DIR = Path("/daaf/research/original")
print(PROJECT_DIR)
PY
    cat > "${TEST_DIR}/scripts/02_string.py" <<'PY'
PROJECT_DIR = '/daaf/research/original'
print(PROJECT_DIR)
PY
    cat > "${TEST_DIR}/scripts/03_string.R" <<'R'
PROJECT_DIR <- "/daaf/research/original"
cat(PROJECT_DIR)
R
    cat > "${TEST_DIR}/scripts/04_file_path.R" <<'R'
PROJECT_DIR <- file.path('/daaf', 'research', 'original')
cat(PROJECT_DIR)
R

    local target="${TEST_DIR}/repro\"double'single\\segment"
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    assert_success
    assert_output --partial "RESULT: 4 normalized, 0 unchanged, 0 no match"

    run python3 "${TEST_DIR}/scripts/01_path.py"
    assert_success
    assert_output "${target}"
    run python3 "${TEST_DIR}/scripts/02_string.py"
    assert_success
    assert_output "${target}"
    run Rscript --vanilla "${TEST_DIR}/scripts/03_string.R"
    assert_success
    assert_output "${target}"
    run Rscript --vanilla "${TEST_DIR}/scripts/04_file_path.R"
    assert_success
    assert_output "${target}"

    run python3 "${REPO_ROOT}/scripts/audit_reproduction_paths.py" \
        "${TEST_DIR}/scripts" "/daaf/research/original" "${target}"
    assert_success
    assert_output --partial '"overall": "MATCH"'
}

@test "normalizer rejects control-character target paths atomically" {
    cat > "${TEST_DIR}/scripts/01_python.py" <<'PY'
PROJECT_DIR = "/daaf/research/original"
PY
    cat > "${TEST_DIR}/scripts/02_r.R" <<'R'
PROJECT_DIR <- "/daaf/research/original"
R
    local before_python before_r target
    before_python="$(sha256sum "${TEST_DIR}/scripts/01_python.py")"
    before_r="$(sha256sum "${TEST_DIR}/scripts/02_r.R")"
    target="${TEST_DIR}/unsafe"$'\t'"path"

    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${target}"

    [ "${status}" -eq 1 ]
    assert_output --partial "target_project_dir contains an unsupported control character"
    assert_output --partial "no files were modified"
    [ "$(sha256sum "${TEST_DIR}/scripts/01_python.py")" = "${before_python}" ]
    [ "$(sha256sum "${TEST_DIR}/scripts/02_r.R")" = "${before_r}" ]
}

@test "normalizer rejects a missing scripts directory" {
    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/missing" "${TEST_DIR}/reproduction"

    assert_failure
    assert_output --partial "scripts_dir is not a directory"
}

@test "normalizer rejects a tree with no supported Python or R scripts" {
    printf '%s\n' 'PROJECT_DIR <- "/daaf/research/original"' \
        > "${TEST_DIR}/scripts/ignored.r"
    printf '%s\n' 'not a script' > "${TEST_DIR}/scripts/notes.txt"

    run python3 "${REPO_ROOT}/scripts/normalize_project_dir.py" \
        "${TEST_DIR}/scripts" "${TEST_DIR}/reproduction"

    assert_failure
    assert_output --partial "No .py or .R files found"
}
