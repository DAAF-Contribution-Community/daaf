#!/usr/bin/env bats
# ============================================================================
# Tests for create_script_revision.sh -- the sanctioned script-revision tool
# ============================================================================
# create_script_revision.sh replaces the flawed `cp original_a.py` revision
# mechanism. A plain `cp` of an already-executed script drags the appended
# `^# EXECUTION LOG` marker into the copy, which run_with_capture.sh then
# refuses to run. This utility copies the ORIGINAL code and strips the appended
# execution-log block so the revision starts clean.
#
# SCRIPT UNDER TEST is parameterized: CREATE_SCRIPT_REVISION_SH defaults to the
# in-repo utility but can be pointed at a draft copy for pre-deployment testing.
#
# Fixtures live in $BATS_TEST_TMPDIR (auto-created and auto-removed per test).
# ============================================================================

load 'test_helper'

CREATE_SCRIPT_REVISION_SH="${CREATE_SCRIPT_REVISION_SH:-${REPO_ROOT}/scripts/create_script_revision.sh}"

setup() {
    export CREATE_SCRIPT_REVISION_SH
}

# Build a fixture that mimics run_with_capture.sh output: the clean code,
# followed by two blank lines and the appended execution-log banner block.
# $1 = path to the clean-code file, $2 = path to the executed (marker-bearing)
# fixture to create.
_make_executed_fixture() {
    local clean="$1" executed="$2"
    cp "$clean" "$executed"
    {
        printf '\n\n'
        printf '%s\n' '# ============================================================================='
        printf '%s\n' '# EXECUTION LOG'
        printf '%s\n' '# ============================================================================='
        printf '%s\n' '#'
        printf '%s\n' '# Executed: 2026-07-16 12:00:00'
        printf '%s\n' '# Exit code: 1'
        printf '%s\n' '#'
        printf '%s\n' '# --- STDOUT ---'
        printf '%s\n' '# some captured output'
        printf '%s\n' '# ============================================================================='
    } >> "$executed"
}

# --- Syntax -----------------------------------------------------------------

@test "create_script_revision.sh parses without errors" {
    run bash -n "$CREATE_SCRIPT_REVISION_SH"
    assert_success
}

# --- Marker present: strip the appended execution log -----------------------

@test "strips execution log; revision has no marker and code above is intact byte-for-byte" {
    local clean="${BATS_TEST_TMPDIR}/clean.py"
    local executed="${BATS_TEST_TMPDIR}/01_task.py"
    local dest="${BATS_TEST_TMPDIR}/01_task_a.py"
    printf '%s\n' 'print("hello")' 'x = 1 + 1' 'print("world")' > "$clean"
    _make_executed_fixture "$clean" "$executed"

    run bash "$CREATE_SCRIPT_REVISION_SH" "$executed" "$dest"
    assert_success
    assert_output --partial "execution log stripped"

    # No marker survived.
    run grep -q "^# EXECUTION LOG" "$dest"
    assert_failure

    # Code above the log block is byte-for-byte identical to the clean source
    # (trailing blank lines removed cleanly).
    run diff "$clean" "$dest"
    assert_success
}

@test "revision ends cleanly (no trailing blank lines from the stripped banner)" {
    local clean="${BATS_TEST_TMPDIR}/clean.py"
    local executed="${BATS_TEST_TMPDIR}/02_task.py"
    local dest="${BATS_TEST_TMPDIR}/02_task_a.py"
    printf '%s\n' 'print("only line")' > "$clean"
    _make_executed_fixture "$clean" "$executed"

    run bash "$CREATE_SCRIPT_REVISION_SH" "$executed" "$dest"
    assert_success

    # Last line must be the code line, not a blank line.
    run tail -n 1 "$dest"
    assert_output 'print("only line")'
}

# --- Marker absent: verbatim whole-copy with informational note -------------

@test "copies verbatim (with note) when the source has no execution log" {
    local src="${BATS_TEST_TMPDIR}/03_new.py"
    local dest="${BATS_TEST_TMPDIR}/03_new_a.py"
    printf '%s\n' 'print("never executed")' 'y = 2' > "$src"

    run bash "$CREATE_SCRIPT_REVISION_SH" "$src" "$dest"
    assert_success
    assert_output --partial "no execution log"

    run diff "$src" "$dest"
    assert_success
}

# --- Refusals ---------------------------------------------------------------

@test "refuses to overwrite an existing destination (immutable versioning)" {
    local src="${BATS_TEST_TMPDIR}/04_task.py"
    local dest="${BATS_TEST_TMPDIR}/04_task_a.py"
    printf '%s\n' 'print("x")' > "$src"
    printf '%s\n' 'print("pre-existing")' > "$dest"

    run bash "$CREATE_SCRIPT_REVISION_SH" "$src" "$dest"
    assert_failure
    assert_output --partial "already exists"

    # The pre-existing destination must be untouched.
    run cat "$dest"
    assert_output 'print("pre-existing")'
}

@test "refuses when the source does not exist" {
    run bash "$CREATE_SCRIPT_REVISION_SH" "${BATS_TEST_TMPDIR}/does-not-exist.py" "${BATS_TEST_TMPDIR}/out.py"
    assert_failure
    assert_output --partial "not found"
}

@test "refuses when source and destination extensions differ" {
    local src="${BATS_TEST_TMPDIR}/05_task.py"
    printf '%s\n' 'print("x")' > "$src"
    run bash "$CREATE_SCRIPT_REVISION_SH" "$src" "${BATS_TEST_TMPDIR}/05_task_a.R"
    assert_failure
    assert_output --partial "Extension mismatch"
}

@test "refuses an unsupported extension" {
    local src="${BATS_TEST_TMPDIR}/06_notes.txt"
    printf '%s\n' 'not a script' > "$src"
    run bash "$CREATE_SCRIPT_REVISION_SH" "$src" "${BATS_TEST_TMPDIR}/06_notes_a.txt"
    assert_failure
    assert_output --partial "Unsupported source extension"
}

@test "missing arguments print usage and exit non-zero" {
    run bash "$CREATE_SCRIPT_REVISION_SH"
    assert_failure
    assert_output --partial "Usage:"
}

# --- R support --------------------------------------------------------------

@test "strips execution log from a .R source" {
    local clean="${BATS_TEST_TMPDIR}/clean.R"
    local executed="${BATS_TEST_TMPDIR}/07_task.R"
    local dest="${BATS_TEST_TMPDIR}/07_task_a.R"
    printf '%s\n' 'library(arrow)' 'cat("hi\n")' > "$clean"
    _make_executed_fixture "$clean" "$executed"

    run bash "$CREATE_SCRIPT_REVISION_SH" "$executed" "$dest"
    assert_success
    run grep -q "^# EXECUTION LOG" "$dest"
    assert_failure
    run diff "$clean" "$dest"
    assert_success
}

# --- Temp-file hygiene --------------------------------------------------------

@test "no temp file is left behind after success or refusal runs" {
    local clean="${BATS_TEST_TMPDIR}/clean.py"
    local executed="${BATS_TEST_TMPDIR}/09_task.py"
    local dest="${BATS_TEST_TMPDIR}/09_task_a.py"
    printf '%s\n' 'print("tidy")' > "$clean"
    _make_executed_fixture "$clean" "$executed"

    # Success path: the temp file is mv'd into place.
    run bash "$CREATE_SCRIPT_REVISION_SH" "$executed" "$dest"
    assert_success

    # Refusal path: destination now exists, so the run exits non-zero.
    run bash "$CREATE_SCRIPT_REVISION_SH" "$executed" "$dest"
    assert_failure

    # No mktemp artifact (.create_script_revision.*) remains in the directory
    # on either path — the EXIT trap (or the mv) must have consumed it.
    run bash -c "ls \"${BATS_TEST_TMPDIR}\"/.create_script_revision.* 2>/dev/null"
    assert_failure
}

# --- Source is never modified -----------------------------------------------

@test "source is left unmodified after creating a revision" {
    local clean="${BATS_TEST_TMPDIR}/clean.py"
    local executed="${BATS_TEST_TMPDIR}/08_task.py"
    local dest="${BATS_TEST_TMPDIR}/08_task_a.py"
    printf '%s\n' 'print("keep me")' > "$clean"
    _make_executed_fixture "$clean" "$executed"

    # Snapshot the source before the run.
    cp "$executed" "${executed}.snapshot"

    run bash "$CREATE_SCRIPT_REVISION_SH" "$executed" "$dest"
    assert_success

    run diff "$executed" "${executed}.snapshot"
    assert_success
    # And the marker is still present in the untouched source.
    run grep -q "^# EXECUTION LOG" "$executed"
    assert_success
}
