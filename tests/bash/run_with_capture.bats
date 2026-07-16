#!/usr/bin/env bats
# ============================================================================
# Tests for run_with_capture.sh -- the file-first execution wrapper
# ============================================================================
# Focus: the pre-execution package-install content scan added 2026-07-16. The
# wrapper is the only chokepoint that sees a script's BODY, so it scans for
# install calls that shell-level hooks (bash-safety.sh) cannot see and refuses
# to execute (exit 3) WITHOUT appending an execution log -- leaving the script
# editable in place. Also regresses the pre-existing behaviors this edit sits
# next to: a clean script executes and gets a log appended; a script that
# already has a log refuses to re-run.
#
# SCRIPT UNDER TEST is parameterized: RUN_WITH_CAPTURE_SH defaults to the
# in-repo wrapper but can be pointed at a draft copy for pre-deployment testing.
#
# Fixtures live in $BATS_TEST_TMPDIR (auto-created and auto-removed per test).
# The install-token strings written into fixtures are inert data fed to a file,
# never executed as commands, and bash-safety only vets the top-level `bats`
# invocation -- not the wrapper's internal interpreter call.
# ============================================================================

load 'test_helper'

RUN_WITH_CAPTURE_SH="${RUN_WITH_CAPTURE_SH:-${REPO_ROOT}/scripts/run_with_capture.sh}"

setup() {
    export RUN_WITH_CAPTURE_SH
}

# --- Syntax -----------------------------------------------------------------

@test "run_with_capture.sh parses without errors" {
    run bash -n "$RUN_WITH_CAPTURE_SH"
    assert_success
}

# --- Block: R install calls inside a .R script ------------------------------

@test "blocks .R with install.packages() (exit 3, cites Dockerfile, no log appended)" {
    local f="${BATS_TEST_TMPDIR}/01_fetch.R"
    printf '%s\n' '# --- Load ---' 'library(sf)' 'install.packages("sf")' 'cat("done\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "Dockerfile"
    assert_output --partial "install.packages"
    # The offending line number and text must be surfaced.
    assert_output --partial "3:install.packages(\"sf\")"
    # Immutable versioning must NOT have engaged: no execution log appended.
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .R with remotes::install_github (exit 3)" {
    local f="${BATS_TEST_TMPDIR}/02_deps.R"
    printf '%s\n' 'remotes::install_github("user/repo")' 'cat("hi\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .R with renv::rebuild() (exit 3, aligned with hook R_INSTALL_TOKENS)" {
    local f="${BATS_TEST_TMPDIR}/02b_renv.R"
    printf '%s\n' 'renv::rebuild()' 'cat("hi\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

# --- Block: Python install call inside a .py script -------------------------

@test "blocks .py with os.system pip install (exit 3, no log appended)" {
    local f="${BATS_TEST_TMPDIR}/01_fetch.py"
    printf '%s\n' 'import os' 'os.system("pip install requests")' 'print("done")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "Dockerfile"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .py with subprocess.run([\"uv\",\"add\",...]) (exit 3, list-form uv coverage)" {
    local f="${BATS_TEST_TMPDIR}/01b_uv.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv","add","httpx"])' 'print("done")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

# --- Allow: token appears ONLY on a full-line comment -----------------------

@test "allows .py whose only token is on a full-line comment (executes, log appended)" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f="${BATS_TEST_TMPDIR}/03_clean.py"
    printf '%s\n' '# to add a dep, do NOT pip install here -- edit the Dockerfile' 'print("ok")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "SUCCESS"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_success
}

# --- Allow: a clean script executes and gets a log appended -----------------

@test "allows a clean .py script (executes, exit 0, log appended)" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f="${BATS_TEST_TMPDIR}/04_clean.py"
    printf '%s\n' 'print("hello from clean script")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "hello from clean script"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_success
}

@test "allows a clean .R script when Rscript is available (executes, log appended)" {
    if ! command -v Rscript >/dev/null 2>&1; then skip "Rscript not available"; fi
    local f="${BATS_TEST_TMPDIR}/05_clean.R"
    printf '%s\n' 'cat("hello from R\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    run grep -q "^# EXECUTION LOG" "$f"
    assert_success
}

# --- Regression: refuse re-run when an execution log is already present ------

@test "refuses to re-run a script that already has an execution log (exit 1)" {
    local f="${BATS_TEST_TMPDIR}/06_done.py"
    printf '%s\n' 'print("x")' '' '# EXECUTION LOG' '# (prior run)' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_failure
    assert_output --partial "already has an execution log"
    # Must not be the scan's exit 3 -- this is the pre-existing exit 1 path.
    [ "$status" -eq 1 ]
}

# --- Regression: usage / missing-file paths unchanged -----------------------

# NOTE: with no argument the wrapper exits non-zero from the `set -u` nounset
# preamble ("$1: unbound variable") BEFORE reaching its own usage echo -- a
# pre-existing behavior of run_with_capture.sh, unrelated to the content scan.
# The load-bearing contract is only that a missing arg does not proceed to
# execution; we assert that, not a specific message.
@test "missing file argument does not proceed (exits non-zero)" {
    run bash "$RUN_WITH_CAPTURE_SH"
    assert_failure
    refute_output --partial "EXECUTING:"
}

@test "nonexistent script path exits non-zero with error" {
    run bash "$RUN_WITH_CAPTURE_SH" "${BATS_TEST_TMPDIR}/does-not-exist.py"
    assert_failure
    assert_output --partial "not found"
}
