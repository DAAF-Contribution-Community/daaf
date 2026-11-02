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
# already has a log refuses to re-run. The environment-secret print scan
# (added 2026-09-26) shares the same refusal path; see its section at the end.
# 2026-09-27: os.environ.items()/values() refused only with a sink or as a
# loop header (W1, env-scrubbing allow test), NUL-byte case for both scans
# (N1, grep -a), marker text names the three real carriers (N2).
# 2026-10-30: Python package REMOVAL forms (string and list) are refused;
# read-only uv pip subcommands in list form are allowed; the string-literal
# false positive is pinned as refused.
# The researcher-decision scan (lit_corpus record-human; lit_verify settle with
# a decision flag) shares the same refusal path; see the last section.
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
# Install-scan block fixtures (R and Python, here through the NUL-byte case)
# name only the fake package daaf-fixture-nonexistent-pkg: if the scan ever
# regressed, the wrapper would EXECUTE the fixture, and a fake name keeps that
# run from changing any environment.

@test "blocks .R with install.packages() (exit 3, cites Dockerfile, no log appended)" {
    local f="${BATS_TEST_TMPDIR}/01_fetch.R"
    printf '%s\n' '# --- Load ---' 'library(sf)' 'install.packages("daaf-fixture-nonexistent-pkg")' 'cat("done\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "Dockerfile"
    assert_output --partial "install.packages"
    # The offending line number and text must be surfaced.
    assert_output --partial "3:install.packages(\"daaf-fixture-nonexistent-pkg\")"
    # Immutable versioning must NOT have engaged: no execution log appended.
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .R with remotes::install_github (exit 3)" {
    local f="${BATS_TEST_TMPDIR}/02_deps.R"
    printf '%s\n' 'remotes::install_github("daaf-fixture-nonexistent-pkg/daaf-fixture-nonexistent-pkg")' 'cat("hi\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .R with renv::rebuild() (exit 3, aligned with hook R_INSTALL_TOKENS)" {
    local f="${BATS_TEST_TMPDIR}/02b_renv.R"
    printf '%s\n' 'renv::rebuild("daaf-fixture-nonexistent-pkg")' 'cat("hi\n")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

# --- Block: Python install call inside a .py script -------------------------

@test "blocks .py with os.system pip install (exit 3, no log appended)" {
    local f="${BATS_TEST_TMPDIR}/01_fetch.py"
    printf '%s\n' 'import os' 'os.system("pip install daaf-fixture-nonexistent-pkg")' 'print("done")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "Dockerfile"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .py with subprocess.run([\"uv\",\"add\",...]) (exit 3, list-form uv coverage)" {
    local f="${BATS_TEST_TMPDIR}/01b_uv.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv","add","daaf-fixture-nonexistent-pkg"])' 'print("done")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

# --- Block: Python package REMOVAL and other mutating verbs (2026-10-30) -----
# Removal was never caught on the Python side (the R side always blocked
# remove.packages()). Each case below writes a two-line fixture whose second
# line holds the form under test; it must be refused with exit 3, the line
# number cited, and no log appended.

@test "blocks .py string form: os.system pip uninstall" {
    local f="${BATS_TEST_TMPDIR}/rm_01.py"
    printf '%s\n' 'import os' 'os.system("pip uninstall -y daaf-fixture-nonexistent-pkg")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "2:os.system"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .py string form: subprocess shell=True pip3 uninstall" {
    local f="${BATS_TEST_TMPDIR}/rm_02.py"
    printf '%s\n' 'import subprocess' 'subprocess.run("pip3 uninstall -y daaf-fixture-nonexistent-pkg", shell=True)' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
}

@test "blocks .py string form: python -m pip uninstall" {
    local f="${BATS_TEST_TMPDIR}/rm_03.py"
    printf '%s\n' 'import os' 'os.system("python -m pip uninstall -y daaf-fixture-nonexistent-pkg")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py string form: python3 -m pip uninstall" {
    local f="${BATS_TEST_TMPDIR}/rm_04.py"
    printf '%s\n' 'import os' 'os.system("python3 -m pip uninstall -y daaf-fixture-nonexistent-pkg")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py string form: uv pip uninstall" {
    local f="${BATS_TEST_TMPDIR}/rm_05.py"
    printf '%s\n' 'import os' 'os.system("uv pip uninstall -y daaf-fixture-nonexistent-pkg")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py string form: shlex.split uv pip sync (sync can remove packages)" {
    local f="${BATS_TEST_TMPDIR}/rm_06.py"
    printf '%s\n' 'import shlex, subprocess' 'subprocess.run(shlex.split("uv pip sync daaf-fixture-missing-requirements.txt"))' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py string form: uv remove" {
    local f="${BATS_TEST_TMPDIR}/rm_07.py"
    printf '%s\n' 'import os' 'os.system("uv remove daaf-fixture-nonexistent-pkg")' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py string form: pipx uninstall, uv tool uninstall, conda remove" {
    local f n=0
    for form in 'os.system("pipx uninstall daaf-fixture-nonexistent-pkg")' 'os.system("uv tool uninstall daaf-fixture-nonexistent-pkg")' 'os.system("conda remove -y daaf-fixture-nonexistent-pkg")'; do
        n=$((n + 1))
        f="${BATS_TEST_TMPDIR}/rm_08_${n}.py"
        printf '%s\n' 'import os' "$form" > "$f"
        run bash "$RUN_WITH_CAPTURE_SH" "$f"
        echo "form: $form -> status $status"
        [ "$status" -eq 3 ]
    done
}

@test "blocks .py list form: [\"pip\", \"uninstall\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_09.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["pip", "uninstall", "-y", "daaf-fixture-nonexistent-pkg"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "blocks .py list form: [sys.executable, \"-m\", \"pip\", \"uninstall\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_10.py"
    printf '%s\n' 'import subprocess, sys' 'subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "daaf-fixture-nonexistent-pkg"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form: [\"uv\", \"pip\", \"uninstall\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_11.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv", "pip", "uninstall", "daaf-fixture-nonexistent-pkg"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form: [\"uv\", \"pip\", \"sync\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_12.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv", "pip", "sync", "daaf-fixture-missing-requirements.txt"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form: [\"uv\", \"remove\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_13.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv", "remove", "daaf-fixture-nonexistent-pkg"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form: [\"uv\", \"pip\", \"install\", ...] (narrowed list rule still refuses install)" {
    local f="${BATS_TEST_TMPDIR}/rm_14.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv", "pip", "install", "daaf-fixture-nonexistent-pkg"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form with a flag before the verb: [\"uv\", \"pip\", \"--quiet\", \"install\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_14b.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv", "pip", "--quiet", "install", "daaf-fixture-nonexistent-pkg"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form with a flag before the verb: [\"uv\", \"pip\", \"-q\", \"sync\", ...]" {
    local f="${BATS_TEST_TMPDIR}/rm_14c.py"
    printf '%s\n' 'import subprocess' 'subprocess.run(["uv", "pip", "-q", "sync", "daaf-fixture-missing-requirements.txt"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
}

@test "blocks .py list form with flags before the verb: [\"pip\", \"-q\", \"install\"] and [\"uv\", \"--quiet\", \"remove\"]" {
    local f n=0
    for form in 'subprocess.run(["pip", "-q", "install", "daaf-fixture-nonexistent-pkg"])' 'subprocess.run(["uv", "--quiet", "remove", "daaf-fixture-nonexistent-pkg"])'; do
        n=$((n + 1))
        f="${BATS_TEST_TMPDIR}/rm_14d_${n}.py"
        printf '%s\n' 'import subprocess' "$form" > "$f"
        run bash "$RUN_WITH_CAPTURE_SH" "$f"
        echo "form: $form -> status $status"
        [ "$status" -eq 3 ]
    done
}

@test "blocks .py list form: [\"conda\", \"remove\", ...] and [\"conda\", \"install\", ...]" {
    local f n=0
    for form in 'subprocess.run(["conda", "remove", "daaf-fixture-nonexistent-pkg"])' 'subprocess.run(["conda", "install", "daaf-fixture-nonexistent-pkg"])'; do
        n=$((n + 1))
        f="${BATS_TEST_TMPDIR}/rm_14e_${n}.py"
        printf '%s\n' 'import subprocess' "$form" > "$f"
        run bash "$RUN_WITH_CAPTURE_SH" "$f"
        echo "form: $form -> status $status"
        [ "$status" -eq 3 ]
    done
}

@test "blocks .py string form: shlex.split(\"uv pip install daaf-fixture-nonexistent-pkg\") (regression, CVE session)" {
    local f="${BATS_TEST_TMPDIR}/rm_15.py"
    printf '%s\n' 'import shlex, subprocess' 'subprocess.run(shlex.split("uv pip install daaf-fixture-nonexistent-pkg"))' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "2:subprocess.run(shlex.split"
}

@test "refuses .py whose string literal merely holds install text (documented fail-closed false positive)" {
    # A line grep cannot tell a literal from a call. Pinned so a change to this
    # behaviour is deliberate; the header comment documents the workaround
    # (keep such text in a non-.py data file the script reads).
    local f="${BATS_TEST_TMPDIR}/rm_16.py"
    printf '%s\n' 'EXPECTED_LINE = "RUN uv pip install --system daaf-fixture-nonexistent-pkg==13.0.0"' 'print(len(EXPECTED_LINE))' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

# --- Allow: read-only uv pip subcommands (2026-10-30) ------------------------
# The old list rule refused ANY ["uv","pip",...]. Only the mutating verbs are
# tokens now. The fixtures hold the command as data and never run uv: the scan
# is a line grep, so a list literal tests the same thing as a call.

@test "allows .py list form: [\"uv\", \"pip\", compile|list|freeze|show|tree|check] (executes, log appended)" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f
    for sub in compile list freeze show tree check; do
        f="${BATS_TEST_TMPDIR}/ro_${sub}.py"
        printf '%s\n' "cmd = [\"uv\", \"pip\", \"${sub}\", \"requirements.in\"]" 'print("argc", len(cmd))' > "$f"
        run bash "$RUN_WITH_CAPTURE_SH" "$f"
        echo "subcommand: $sub -> status $status"
        assert_success
        run grep -q "^# EXECUTION LOG" "$f"
        assert_success
    done
}

@test "allows .py list form with a flag before a read-only verb: [\"uv\", \"pip\", \"-q\", \"list\"] (executes)" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f="${BATS_TEST_TMPDIR}/ro_flag_list.py"
    printf '%s\n' 'cmd = ["uv", "pip", "-q", "list"]' 'print("argc", len(cmd))' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    run grep -q "^# EXECUTION LOG" "$f"
    assert_success
}

@test "allows .py string form: shlex.split(\"uv pip compile ...\") (CVE session form, executes)" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f="${BATS_TEST_TMPDIR}/ro_shlex_compile.py"
    printf '%s\n' 'import shlex' 'cmd = shlex.split("uv pip compile req.in --universal --exclude-newer 2026-09-24T13:20:00Z -o req.txt")' 'print("argc", len(cmd))' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "argc"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_success
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

# NOTE: historically a missing argument died on the `set -u` nounset preamble
# ("$1: unbound variable") before reaching the usage echo. Fixed 2026-09-11
# (`${1:-}`); the usage-message assertion lives in the integrity section below.
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

# ============================================================================
# Evidence-capture integrity (added 2026-09-11)
# ============================================================================
# The wrapper must distinguish three outcomes -- COMPUTATION (script exit),
# CAPTURE (tee into the project-local buffer), PERSISTENCE (log appended and
# verified) -- and must never report SUCCESS or "appended" unless all three
# succeeded. Faults are injected the way the retained 2026-09-05 fixtures did
# it: exported Bash functions shadow ONE subprocess tool while the real wrapper
# runs unchanged. The "python3" shadow prints an inert marker and never runs
# any Python. Append failure is REAL (a read-only script file), not simulated.
# ============================================================================

_inert_python3() {
    python3() { printf 'INERT_COMPUTATION_COMPLETED\n'; return 0; }
    export -f python3
}

@test "verified success: single marker, Capture: COMPLETE, buffer deleted, exit 0" {
    _inert_python3
    local f="${BATS_TEST_TMPDIR}/10_ok.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "SUCCESS: Script passed."
    assert_output --partial "Execution log appended to:"
    assert_output --partial "Capture: COMPLETE"
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 1 ]
    grep -q '^# INERT_COMPUTATION_COMPLETED' "$f"
    grep -q '^# Capture: COMPLETE' "$f"
    grep -q '^# Exit code: 0' "$f"
    # Closing banner is the last line (the record is complete).
    [ "$(tail -n 1 "$f")" = "# =============================================================================" ]
    # Buffer is deleted after a verified run.
    [ -z "$(ls -A "${BATS_TEST_TMPDIR}"/.10_ok.py.capture.* 2>/dev/null)" ]
}

@test "script failure with healthy capture: returns script exit code, record complete, buffer deleted" {
    python3() { printf 'partial work\n'; return 7; }
    export -f python3
    local f="${BATS_TEST_TMPDIR}/11_fail.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 7 ]
    assert_output --partial "FAILED: Script returned exit code 7"
    assert_output --partial "Execution log appended to:"
    refute_output --partial "SUCCESS"
    refute_output --partial "EVIDENCE INCOMPLETE"
    grep -q '^# Exit code: 7' "$f"
    grep -q '^# Capture: COMPLETE' "$f"
    [ -z "$(ls -A "${BATS_TEST_TMPDIR}"/.11_fail.py.capture.* 2>/dev/null)" ]
}

@test "tee fault: exit 74, no SUCCESS, log appended and marked Capture: INCOMPLETE, buffer retained" {
    _inert_python3
    tee() { command cat; return 73; }
    export -f tee
    local f="${BATS_TEST_TMPDIR}/12_tee.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 74 ]
    assert_output --partial "EVIDENCE INCOMPLETE"
    assert_output --partial "Computation: script exited 0"
    assert_output --partial "Capture:     INCOMPLETE (tee exit 73)"
    assert_output --partial "Capture buffer retained at:"
    refute_output --partial "SUCCESS: Script passed."
    # The record exists (immutable versioning engaged) but says its stdout is untrustworthy.
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 1 ]
    grep -q '^# Capture: INCOMPLETE (tee exit 73)' "$f"
    assert_output --partial "create_script_revision.sh"
    # Buffer retained.
    [ -n "$(ls -A "${BATS_TEST_TMPDIR}"/.12_tee.py.capture.* 2>/dev/null)" ]
}

@test "append fault (read-only script): exit 74, no marker, no 'appended' claim, buffer retained, in-place guidance" {
    if [ "$(id -u)" -eq 0 ]; then skip "root ignores file permissions"; fi
    _inert_python3
    local f="${BATS_TEST_TMPDIR}/13_ro.py"
    printf '%s\n' '# inert fixture' > "$f"
    chmod 0444 "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    chmod 0644 "$f"
    [ "$status" -eq 74 ]
    assert_output --partial "EVIDENCE INCOMPLETE"
    assert_output --partial "Persistence: FAILED"
    assert_output --partial "Capture buffer retained at:"
    refute_output --partial "Execution log appended to:"
    refute_output --partial "SUCCESS: Script passed."
    # No marker: the script stays runnable in place, and the banner says so.
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
    # The retained buffer holds the computation's output as failure evidence.
    local buf
    buf=$(ls "${BATS_TEST_TMPDIR}"/.13_ro.py.capture.* | head -n 1)
    [ -f "$buf" ]
    grep -q 'INERT_COMPUTATION_COMPLETED' "$buf"
}

@test "append fault banner says the script is runnable IN PLACE (no marker present)" {
    if [ "$(id -u)" -eq 0 ]; then skip "root ignores file permissions"; fi
    _inert_python3
    local f="${BATS_TEST_TMPDIR}/14_ro.py"
    printf '%s\n' '# inert fixture' > "$f"
    chmod 0444 "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    chmod 0644 "$f"
    [ "$status" -eq 74 ]
    assert_output --partial "runnable IN PLACE"
    refute_output --partial "create_script_revision.sh"
}

@test "duplicate marker after append (concurrent-run model): exit 74, verification names marker count" {
    # Model a second invocation's block landing between the pre-append re-check
    # and the append: shadow `sed` (the wrapper's comment-prefix step, which runs
    # after the re-check and before the append) so a second marker lands on the
    # script first. Post-append verification must then count 2 and refuse.
    _inert_python3
    sed() { printf '%s\n' '# EXECUTION LOG' >> "$RWC_FIXTURE"; command sed "$@"; }
    export -f sed
    local f="${BATS_TEST_TMPDIR}/15_dup.py"
    export RWC_FIXTURE="$f"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    unset RWC_FIXTURE
    [ "$status" -eq 74 ]
    assert_output --partial "EVIDENCE INCOMPLETE"
    assert_output --partial "expected exactly 1 execution-log marker, found 2"
    refute_output --partial "SUCCESS: Script passed."
    [ -n "$(ls -A "${BATS_TEST_TMPDIR}"/.15_dup.py.capture.* 2>/dev/null)" ]
}

@test "unwritable script directory: exit 74 before execution, script untouched" {
    if [ "$(id -u)" -eq 0 ]; then skip "root ignores directory permissions"; fi
    _inert_python3
    local d="${BATS_TEST_TMPDIR}/ro_dir"
    mkdir "$d"
    local f="${d}/16_nobuf.py"
    printf '%s\n' '# inert fixture' > "$f"
    chmod 0555 "$d"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    chmod 0755 "$d"
    [ "$status" -eq 74 ]
    assert_output --partial "could not create capture buffer"
    assert_output --partial "NOT executed"
    refute_output --partial "EXECUTING:"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "interruption (SIGTERM): exit 143, no log appended, buffer retained with partial output" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f="${BATS_TEST_TMPDIR}/17_term.py"
    printf '%s\n' 'import sys, time' 'print("before sleep", flush=True)' 'time.sleep(1)' 'print("after sleep")' > "$f"
    local out="${BATS_TEST_TMPDIR}/17.out" err="${BATS_TEST_TMPDIR}/17.err"
    bash "$RUN_WITH_CAPTURE_SH" "$f" > "$out" 2> "$err" &
    local pid=$!
    sleep 0.4
    kill -TERM "$pid"
    local st=0
    wait "$pid" || st=$?
    [ "$st" -eq 143 ]
    grep -q "INTERRUPTED: run_with_capture.sh received SIGTERM" "$err"
    grep -q "Partial output retained at:" "$err"
    grep -q "remains runnable in place" "$err"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
    local buf
    buf=$(ls "${BATS_TEST_TMPDIR}"/.17_term.py.capture.* | head -n 1)
    [ -f "$buf" ]
    grep -q "before sleep" "$buf"
}

# A job started with '&' from a non-interactive shell begins with SIGINT
# IGNORED (POSIX job-control rule), so `kill -INT` on a plain background
# wrapper is silently dropped -- that is a property of the test harness, not
# of the wrapper (probed 2026-09-11: plain '&' + INT -> status 0, log appended).
# Deliver SIGINT through a launcher that restores the default disposition and
# then execs the wrapper, which is what a real Ctrl-C / harness cancel sees.
@test "interruption (SIGINT via default-disposition launcher): exit 130, no log appended, buffer retained" {
    if ! command -v python3 >/dev/null 2>&1; then skip "python3 not available"; fi
    local f="${BATS_TEST_TMPDIR}/17_int.py"
    printf '%s\n' 'import sys, time' 'print("before sleep", flush=True)' 'time.sleep(1)' 'print("after sleep")' > "$f"
    local out="${BATS_TEST_TMPDIR}/17i.out" err="${BATS_TEST_TMPDIR}/17i.err"
    python3 -c "import signal,os,sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp('bash', ['bash', sys.argv[1], sys.argv[2]])" \
        "$RUN_WITH_CAPTURE_SH" "$f" > "$out" 2> "$err" &
    local pid=$!
    sleep 0.4
    kill -INT "$pid"
    local st=0
    wait "$pid" || st=$?
    [ "$st" -eq 130 ]
    grep -q "INTERRUPTED: run_with_capture.sh received SIGINT" "$err"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
    [ -n "$(ls -A "${BATS_TEST_TMPDIR}"/.17_int.py.capture.* 2>/dev/null)" ]
}

@test "missing argument prints usage (exit 1) instead of an unbound-variable error" {
    run bash "$RUN_WITH_CAPTURE_SH"
    [ "$status" -eq 1 ]
    assert_output --partial "Usage:"
    refute_output --partial "unbound variable"
}

@test "buffer is created next to the script, not in /tmp (retained on fault)" {
    if [ "$(id -u)" -eq 0 ]; then skip "root ignores file permissions"; fi
    _inert_python3
    local d="${BATS_TEST_TMPDIR}/proj"
    mkdir "$d"
    local f="${d}/18_where.py"
    printf '%s\n' '# inert fixture' > "$f"
    chmod 0444 "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    chmod 0644 "$f"
    [ "$status" -eq 74 ]
    assert_output --partial "Capture buffer retained at: ${d}/.18_where.py.capture."
}

# --- Marker integrity, empty output, signal-after-append (review fixes 2026-09-11) ---

@test "script output containing the literal marker text cannot forge a second marker (verified run, exit 0)" {
    python3() { printf 'EXECUTION LOG\nsomething else\n'; return 0; }
    export -f python3
    local f="${BATS_TEST_TMPDIR}/19_forge.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "SUCCESS: Script passed."
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 1 ]
    grep -q '^#  EXECUTION LOG$' "$f"
    # And the neutralized line does not trip the re-run guard's regex either.
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 1 ]
    assert_output --partial "already has an execution log"
}

@test "empty script output is archived as '# (no output)' (every log line stays a comment)" {
    python3() { return 0; }
    export -f python3
    local f="${BATS_TEST_TMPDIR}/20_empty.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    grep -q '^# (no output)$' "$f"
    # No un-prefixed blank line inside the appended block (after the marker).
    [ "$(sed -n '/^# EXECUTION LOG/,$p' "$f" | grep -c '^$')" -eq 0 ]
}

@test "signal arriving after the append: banner says an unverified log is present and points to a revision" {
    _inert_python3
    # `tail` is used only in post-append verification; deliver SIGTERM from there.
    tail() { kill -TERM $$; command tail "$@"; }
    export -f tail
    local f="${BATS_TEST_TMPDIR}/21_late.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 143 ]
    assert_output --partial "INTERRUPTED: run_with_capture.sh received SIGTERM"
    assert_output --partial "ALREADY been appended"
    assert_output --partial "create_script_revision.sh"
    refute_output --partial "remains runnable in place"
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 1 ]
    [ -n "$(ls -A "${BATS_TEST_TMPDIR}"/.21_late.py.capture.* 2>/dev/null)" ]
}

@test "NUL bytes in output: verified run (exit 0), Capture line discloses the stripped count, buffer deleted" {
    python3() { printf 'a\000b\n'; return 0; }
    export -f python3
    local f="${BATS_TEST_TMPDIR}/22_nul.py"
    printf '%s\n' '# inert fixture' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "SUCCESS: Script passed."
    refute_output --partial "EVIDENCE INCOMPLETE"
    grep -q '^# Capture: COMPLETE (1 NUL byte(s)' "$f"
    [ -z "$(ls -A "${BATS_TEST_TMPDIR}"/.22_nul.py.capture.* 2>/dev/null)" ]
}

# ============================================================================
# Environment-secret print scan (added 2026-09-26)
# ============================================================================
# The wrapper refuses (exit 3, no log appended, script editable in place) a
# script whose body prints the environment or a credential-named variable,
# because captured output is appended permanently to the script file. It
# reports line NUMBERS and categories only -- never line text.
#
# SAFETY: the container environment holds REAL API keys, so nothing in this
# section may ever actually dump it. Three independent layers keep every
# BLOCK fixture inert even if the scan regressed and failed to refuse:
#   1. every test shadows BOTH interpreters (python3, Rscript) with an exported
#      function that prints an inert marker -- no real interpreter ever runs;
#   2. every BLOCK fixture exits at its top (`raise SystemExit(0)` /
#      `quit(status = 0)`) before the dump line is reached;
#   3. a scan miss makes the test FAIL (status 0 != 3, INERT marker present),
#      so a regression is caught without any value being printed.
# ALLOW controls likewise run only under the inert shadow: exit 0 + an
# appended log proves the scan let them through, without executing them.
# ============================================================================

_inert_interpreters() {
    python3() { printf 'INERT_COMPUTATION_COMPLETED\n'; return 0; }
    Rscript() { printf 'INERT_COMPUTATION_COMPLETED\n'; return 0; }
    export -f python3 Rscript
}

# _expect_secret_block EXT DUMP_LINE CATEGORY
# Writes a guarded fixture whose dump sits on line 3 (.py) or line 2 (.R) and
# asserts a full refusal naming that line and category, with no execution,
# no log, no capture buffer, and no echo of the line text.
_SECRET_CASE=0
_expect_secret_block() {
    local ext="$1" dump_line="$2" category="$3" f dump_lineno
    _SECRET_CASE=$((_SECRET_CASE + 1))
    f="${BATS_TEST_TMPDIR}/sec_${_SECRET_CASE}.${ext}"
    if [ "$ext" = "py" ]; then
        printf '%s\n' 'import os, sys, json, pprint, logging, subprocess' \
            'raise SystemExit(0)  # inert guard: nothing below runs even if the scan misses' \
            "$dump_line" > "$f"
        dump_lineno=3
    else
        printf '%s\n' 'quit(status = 0)  # inert guard: nothing below runs even if the scan misses' \
            "$dump_line" > "$f"
        dump_lineno=2
    fi
    echo "case ${_SECRET_CASE} (.${ext}): ${dump_line}"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "environment-secret print detected"
    assert_output --partial "line ${dump_lineno}: ${category}"
    refute_output --partial "EXECUTING:"
    refute_output --partial "INERT_COMPUTATION_COMPLETED"
    # Line text is withheld from the refusal banner.
    refute_output --partial "$dump_line"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
    [ -z "$(ls -A "${BATS_TEST_TMPDIR}/.sec_${_SECRET_CASE}.${ext}.capture."* 2>/dev/null)" ]
}

# _expect_scan_pass FILE -- the scan let the file through: it "executed"
# (inert shadow), exited 0, and a verified log was appended.
_expect_scan_pass() {
    local f="$1"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "SUCCESS: Script passed."
    refute_output --partial "environment-secret print detected"
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 1 ]
    grep -q '^# INERT_COMPUTATION_COMPLETED' "$f"
}

# --- Block: Python ------------------------------------------------------------

@test "secret scan blocks .py whole-environment print/serialize shapes" {
    _inert_interpreters
    local cat="whole environment printed or serialized"
    _expect_secret_block py 'print(os.environ)' "$cat"
    _expect_secret_block py 'pprint.pprint(os.environ)' "$cat"
    _expect_secret_block py 'print(dict(os.environ))' "$cat"
    _expect_secret_block py 'payload = json.dumps(dict(os.environ))' "$cat"
    _expect_secret_block py 'payload = json.dumps(os.environ.copy())' "$cat"
    _expect_secret_block py 'print("env:", os.environ)' "$cat"
    _expect_secret_block py 'print(f"{os.environ}")' "$cat"
    _expect_secret_block py 'logging.info("env=%s", os.environ)' "$cat"
}

# W1 (2026-09-27): .items()/.values() are refused only with an output sink on
# the same line or as a `for ... in` loop header; see the scrubbing allow test.
@test "secret scan blocks .py os.environ.items()/values() with a sink or as a loop header" {
    _inert_interpreters
    local cat="environment values iterated (os.environ.items/values)"
    _expect_secret_block py 'for k, v in os.environ.items(): print(k, v)' "$cat"
    _expect_secret_block py 'print(list(os.environ.values()))' "$cat"
    _expect_secret_block py 'for name in sorted(os.environ.values()):' "$cat"
    _expect_secret_block py 'logging.info("%s", dict(os.environ.items()))' "$cat"
}

@test "secret scan blocks .py credential-named lookups inside print/logging/stdout sinks" {
    _inert_interpreters
    local cat="credential-named variable printed or logged"
    _expect_secret_block py 'print(os.environ["X_API_KEY"])' "$cat"
    _expect_secret_block py "print(f\"token={os.environ.get('GITHUB_TOKEN')}\")" "$cat"
    _expect_secret_block py 'logging.info("s %s", os.getenv("DB_SECRET"))' "$cat"
    # Names match case-insensitively.
    _expect_secret_block py 'logger.debug(os.environ["db_password"])' "$cat"
    _expect_secret_block py 'sys.stdout.write(os.environ["X_AUTH"] + "\n")' "$cat"
    _expect_secret_block py 'pprint.pprint(os.environ.get("AWS_SESSION_TOKEN"))' "$cat"
}

@test "secret scan blocks .py shell-outs that dump the environment" {
    _inert_interpreters
    local cat="shell command that dumps the environment"
    _expect_secret_block py 'os.system("env")' "$cat"
    _expect_secret_block py 'os.system("printenv")' "$cat"
    _expect_secret_block py 'os.system("env | sort")' "$cat"
    _expect_secret_block py 'subprocess.run(["env"])' "$cat"
    _expect_secret_block py 'subprocess.run(["printenv", "X_API_KEY"])' "$cat"
    _expect_secret_block py 'subprocess.run("set", shell=True)' "$cat"
    _expect_secret_block py 'out = os.popen("env").read()' "$cat"
}

# --- Block: R -------------------------------------------------------------------

@test "secret scan blocks .R Sys.getenv() with no name (returns every variable)" {
    _inert_interpreters
    local cat="all environment variables requested (Sys.getenv with no name)"
    _expect_secret_block R 'print(Sys.getenv())' "$cat"
    _expect_secret_block R 'env_all <- Sys.getenv()' "$cat"
    _expect_secret_block R 'env_all <- Sys.getenv(names = TRUE)' "$cat"
}

@test "secret scan blocks .R credential-named lookups inside print/cat/message/writeLines" {
    _inert_interpreters
    local cat="credential-named variable printed"
    _expect_secret_block R 'cat(Sys.getenv("HARVARD_DATAVERSE_API_KEY"), "\n")' "$cat"
    _expect_secret_block R 'message("token: ", Sys.getenv("github_token"))' "$cat"
    _expect_secret_block R 'writeLines(Sys.getenv("X_SECRET"))' "$cat"
    _expect_secret_block R 'print(Sys.getenv("DB_PASSWORD"))' "$cat"
}

@test "secret scan blocks .R bare top-level credential lookup (Rscript auto-prints it)" {
    _inert_interpreters
    local cat="credential-named variable auto-printed (bare top-level lookup)"
    # (Name differs from the banner's own X_API_KEY example so the
    # line-text-withheld assertion stays meaningful.)
    _expect_secret_block R 'Sys.getenv("OPENAI_API_KEY")' "$cat"
    _expect_secret_block R '  Sys.getenv("X_TOKEN", unset = "")  # debugging' "$cat"
}

@test "secret scan blocks .R system()/system2() environment dumps" {
    _inert_interpreters
    local cat="shell command that dumps the environment"
    _expect_secret_block R 'system("env")' "$cat"
    _expect_secret_block R 'system2("printenv")' "$cat"
    _expect_secret_block R 'system("printenv X_API_KEY")' "$cat"
    _expect_secret_block R 'out <- system2("env", stdout = TRUE)' "$cat"
}

# --- Refusal banner contents ---------------------------------------------------

@test "secret scan refusal withholds line text (hardcoded literal never echoed) and gives the correct pattern" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/sec_banner.py"
    printf '%s\n' 'import os' 'raise SystemExit(0)  # inert guard' \
        'print(os.environ.get("X_API_KEY", "FAKE-FIXTURE-LITERAL-0000"))' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "line 3: credential-named variable printed or logged"
    assert_output --partial "line text withheld"
    refute_output --partial "FAKE-FIXTURE-LITERAL-0000"
    refute_output --partial 'os.environ.get("X_API_KEY"'
    assert_output --partial "permanent audit record"
    assert_output --partial "never print, log, or serialize it"
    assert_output --partial "NO execution log was appended"
    run grep -q "^# EXECUTION LOG" "$f"
    assert_failure
}

@test "secret scan reports every offending line, not just the first" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/sec_multi.py"
    printf '%s\n' 'import os' 'raise SystemExit(0)  # inert guard' \
        'print(os.environ)' 'x = 1' 'print(os.environ["X_TOKEN"])' > "$f"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "line 3: whole environment printed or serialized"
    assert_output --partial "line 5: credential-named variable printed or logged"
}

# --- Allow: controls that must pass the scan -----------------------------------

@test "secret scan allows .py controls: credential read into a variable/header, non-secret lookups, env copies for subprocess" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/sec_allow.py"
    printf '%s\n' \
        'import os, json, subprocess' \
        'api_key = os.environ["HARVARD_DATAVERSE_API_KEY"]' \
        'headers = {"X-Dataverse-key": os.environ["HARVARD_DATAVERSE_API_KEY"]}' \
        'home = os.environ.get("HOME")' \
        'print(os.environ["HOME"])' \
        'print(os.getcwd())' \
        'env = os.environ.copy()' \
        'subprocess.run(["python3", "-V"], env=env)' \
        'subprocess.run(["python3", "-V"], env=dict(os.environ, FOO="1"))' \
        '# print(os.environ)' \
        'print("X_API_KEY" in os.environ)' \
        'print(len(os.environ))' \
        'subprocess.run(["env", "FOO=1", "python3", "-V"])' \
        'print(os.environ["SSH_AUTH_SOCK"])' \
        'body = json.dumps({"api_key": os.environ["X_API_KEY"]})' \
        > "$f"
    _expect_scan_pass "$f"
}

# W1 (2026-09-27): the env-SCRUBBING idiom builds a child environment with the
# keys removed; it must run. The multi-line form mirrors an audited research
# script whose `for ... in os.environ.items()` continuation line was refused.
@test "secret scan allows .py env-scrubbing comprehensions and a bare values() copy" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/sec_scrub.py"
    printf '%s\n' \
        'import os, subprocess' \
        'child_env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}' \
        'env = {k: v for k, v in os.environ.items() if k != "X"}' \
        'scrubbed = {' \
        '    name: value' \
        '    for name, value in os.environ.items()' \
        '    if not name.upper().endswith("_API_KEY")' \
        '}' \
        'vals = list(os.environ.values())' \
        'subprocess.run(["python3", "-V"], env=child_env)' \
        > "$f"
    _expect_scan_pass "$f"
}

# N1 (2026-09-27): a NUL byte makes GNU grep treat the file as binary and
# print no matching lines unless -a is given; both scans must still refuse.
@test "scans still refuse when the script contains a NUL byte (install scan and secret scan)" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/nul_install.py"
    printf 'import os\nraise SystemExit(0)  # inert guard\nx = "a\000b"\nos.system("pip install daaf-fixture-nonexistent-pkg")\n' > "$f"
    [ "$(tr -cd '\000' < "$f" | wc -c)" -eq 1 ]
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "runtime package install detected"
    refute_output --partial "INERT_COMPUTATION_COMPLETED"
    f="${BATS_TEST_TMPDIR}/nul_secret.py"
    printf 'import os\nraise SystemExit(0)  # inert guard\nx = "a\000b"\nprint(os.environ)\n' > "$f"
    [ "$(tr -cd '\000' < "$f" | wc -c)" -eq 1 ]
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "line 4: whole environment printed or serialized"
    refute_output --partial "INERT_COMPUTATION_COMPLETED"
    run grep -ac "^# EXECUTION LOG" "$f"
    assert_output "0"
}

@test "secret scan allows .py whose only dump is on a full-line comment" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/sec_comment.py"
    printf '%s\n' 'import os' '    # print(os.environ)' '# os.system("env")' 'x = 1' > "$f"
    _expect_scan_pass "$f"
}

@test "secret scan allows .R controls: credential read into a variable, non-secret lookups, presence check" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/sec_allow.R"
    printf '%s\n' \
        'key <- Sys.getenv("HARVARD_DATAVERSE_API_KEY")' \
        'home <- Sys.getenv("HOME")' \
        'Sys.getenv("HOME")' \
        'print(Sys.getenv("HOME"))' \
        '# print(Sys.getenv())' \
        'has_key <- nzchar(Sys.getenv("X_API_KEY"))' \
        'cat(has_key, "\n")' \
        'Sys.getenv("SSH_AUTH_SOCK")' \
        'system2("env", c("FOO=1", "Rscript", "--version"))' \
        > "$f"
    _expect_scan_pass "$f"
}

# --- Vocabulary marker ----------------------------------------------------------

@test "secret scan carries the shared SECRET-NAME-VOCAB v1 marker and list" {
    run grep -c '^# SECRET-NAME-VOCAB v1 — keep identical in: output-scanner.sh, audit-log.sh, run_with_capture.sh$' "$RUN_WITH_CAPTURE_SH"
    assert_output "1"
    grep -q '^SECRET_NAME_VOCAB="KEY KEYS APIKEY TOKEN TOKENS SECRET SECRETS PASS PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDENTIALS CREDS AUTH COOKIE COOKIES SESSION DSN PAT"$' "$RUN_WITH_CAPTURE_SH"
    grep -q '^SECRET_NAME_ALLOWLIST="SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS XDG_SESSION_DESKTOP"$' "$RUN_WITH_CAPTURE_SH"
}

# ============================================================================
# Researcher-decision scan
# ============================================================================
# The wrapper refuses (exit 3, no log appended, script editable in place) a
# script that calls `lit_corpus adjudications record-human` or `lit_verify
# settle` with a decision flag: those record a researcher's own decision and
# are run only by the orchestrator, behind a permission prompt. It cites each
# offending line as "N:text".
#
# SAFETY: the commands in these fixtures are inert text. Every test shadows
# both interpreters (_inert_interpreters), every BLOCK fixture exits at its
# top before the call line, and the paths name no real project, so a scan
# miss fails the test (status 0, INERT marker) without recording anything.
# ============================================================================

# _expect_decision_block FILE LINE... -- a full refusal citing each LINE number.
_expect_decision_block() {
    local f="$1" ln
    shift
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "BLOCKED: This script was not run. It appears to run a command"
    assert_output --partial "researcher decision command detected"
    assert_output --partial "records a researcher's own"
    assert_output --partial "move that text into a data file"
    assert_output --partial "selftest <SCRATCH_DIR>"
    assert_output --partial "NO execution log was appended"
    refute_output --partial "EXECUTING:"
    refute_output --partial "INERT_COMPUTATION_COMPLETED"
    # A cited line reads "N:text" at the start of an output line.
    for ln in "$@"; do
        grep -qE "^${ln}:" <<< "$output"
    done
    # No log appended (a count, so $output stays the refusal for the caller).
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 0 ]
}

# _expect_decision_pass FILE -- the scan let the file through (inert run, log appended).
_expect_decision_pass() {
    local f="$1"
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    assert_success
    assert_output --partial "SUCCESS: Script passed."
    refute_output --partial "researcher decision command detected"
    [ "$(grep -c '^# EXECUTION LOG' "$f")" -eq 1 ]
    grep -q '^# INERT_COMPUTATION_COMPLETED' "$f"
}

# --- Block -----------------------------------------------------------------------

@test "decision scan blocks .py record-human through the lit_corpus.sh wrapper (list form)" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_01.py"
    printf '%s\n' 'import subprocess' 'raise SystemExit(0)  # inert guard' \
        'subprocess.run(["bash", "/daaf/scripts/lit_corpus.sh", "adjudications", "record-human", "proj", "--rows", "rows.txt", "--decision", "same_work", "--user-words", "all look right"])' > "$f"
    _expect_decision_block "$f" 3
    assert_output --partial "3:subprocess.run"
}

@test "decision scan blocks .py record-human through the lit_corpus.py module (string form and import)" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_02.py"
    printf '%s\n' 'import os, sys' 'raise SystemExit(0)  # inert guard' \
        'os.system("python3 /daaf/scripts/lit_corpus.py adjudications record-human proj --rows r.txt --decision defer --user-words later")' > "$f"
    _expect_decision_block "$f" 3
    f="${BATS_TEST_TMPDIR}/dec_02b.py"
    printf '%s\n' 'import sys' 'raise SystemExit(0)  # inert guard' 'sys.path.insert(0, "/daaf/scripts")' 'import lit_corpus' \
        'lit_corpus.main(["adjudications", "record-human", "proj", "--rows", "r.txt", "--decision", "defer", "--user-words", "later"])' > "$f"
    _expect_decision_block "$f" 5
}

@test "decision scan blocks .py record-human held in a variable" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_03.py"
    printf '%s\n' 'import subprocess' 'raise SystemExit(0)  # inert guard' 'ACTION = "record-human"' \
        'subprocess.run(["bash", "/daaf/scripts/lit_corpus.sh", "adjudications", ACTION, "proj"])' > "$f"
    _expect_decision_block "$f" 3
}

@test "decision scan blocks .py settle with --decision through the .sh wrapper and the .py module" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_04.py"
    printf '%s\n' 'import subprocess, sys' 'raise SystemExit(0)  # inert guard' \
        'subprocess.run(["bash", "/daaf/scripts/lit_verify.sh", "settle", "papers/k", "--audit", "vision_audit.json", "--items", "items.txt", "--decision", "matches", "--user-words", "they match"])' > "$f"
    _expect_decision_block "$f" 3
    f="${BATS_TEST_TMPDIR}/dec_04b.py"
    printf '%s\n' 'import subprocess, sys' 'raise SystemExit(0)  # inert guard' \
        'subprocess.run([sys.executable, "/daaf/scripts/lit_verify.py", "settle", "papers/k", "--audit", "vision_audit.json", "--items", "items.txt", "--decision", "does_not_match", "--user-words", "2 is wrong", "--rationale", "page 4 prints 0.31"])' > "$f"
    _expect_decision_block "$f" 3
}

@test "decision scan blocks .py settle whose list is split across lines (cites the settle and flag lines)" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_05.py"
    printf '%s\n' 'import subprocess' 'raise SystemExit(0)  # inert guard' \
        'LV = "/daaf/scripts/lit_verify.sh"' \
        'cmd = ["bash", LV,' \
        '       "settle", "papers/k", "--audit", "vision_audit.json",' \
        '       "--items", "items.txt",' \
        '       "--decision", "matches", "--user-words", "they match"]' \
        'subprocess.run(cmd)' > "$f"
    _expect_decision_block "$f" 5 7
}

@test "decision scan blocks .py settle with an abbreviated decision flag (--d, --dec, --decision=)" {
    _inert_interpreters
    local f n=0
    for flag in '"--d", "matches"' '"--dec", "matches"' '"--decision=matches"'; do
        n=$((n + 1))
        f="${BATS_TEST_TMPDIR}/dec_06_${n}.py"
        printf '%s\n' 'import subprocess' 'raise SystemExit(0)  # inert guard' \
            "subprocess.run([\"bash\", \"/daaf/scripts/lit_verify.sh\", \"settle\", \"papers/k\", \"--audit\", \"a.json\", \"--items\", \"i.txt\", ${flag}, \"--user-words\", \"ok\"])" > "$f"
        echo "flag form: $flag"
        _expect_decision_block "$f" 3
    done
}

@test "decision scan blocks .R settle via system2() and record-human via system()" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_07.R"
    printf '%s\n' 'quit(status = 0)  # inert guard' \
        'system2("bash", c("/daaf/scripts/lit_verify.sh", "settle", "papers/k", "--audit", "vision_audit.json", "--items", "items.txt", "--decision", "matches", "--user-words", "they match"))' > "$f"
    _expect_decision_block "$f" 2
    f="${BATS_TEST_TMPDIR}/dec_07b.R"
    printf '%s\n' 'quit(status = 0)  # inert guard' \
        "system(\"bash /daaf/scripts/lit_corpus.sh adjudications record-human proj --rows r.txt --decision defer --user-words 'later'\")" > "$f"
    _expect_decision_block "$f" 2
}

@test "decision scan refuses a string literal that only quotes the command (documented fail-closed false positive)" {
    # A line grep cannot tell a printed hint from a call. Pinned so a change is
    # deliberate; the script header gives the workaround (a data file).
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_08.py"
    printf '%s\n' 'raise SystemExit(0)  # inert guard' \
        'print("next: bash /daaf/scripts/lit_corpus.sh adjudications record-human PROJECT --rows FILE")' > "$f"
    _expect_decision_block "$f" 2
}

@test "decision scan refuses a settle --list script that prints a hint naming --decision (false positive; banner gives the workaround)" {
    # The script only lists items, then prints the next step. The banner must
    # say "appears to run" and point to the data-file workaround.
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_08b.py"
    printf '%s\n' 'import subprocess' 'raise SystemExit(0)  # inert guard' \
        'LV = "/daaf/scripts/lit_verify.sh"' \
        'subprocess.run(["bash", LV, "settle", "papers/k", "--audit", "vision_audit.json", "--list"])' \
        'print("Next: the orchestrator records the reply with --decision after the researcher answers.")' > "$f"
    _expect_decision_block "$f" 4 5
}

@test "decision scan blocks .py settle with CRLF line endings and a tab-indented list split across lines" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_09.py"
    printf 'import subprocess\r\nraise SystemExit(0)  # inert guard\r\nLV = "/daaf/scripts/lit_verify.sh"\r\ncmd = ["bash", LV,\r\n\t"settle", "papers/k",\r\n\t"--items", "items.txt",\r\n\t"--decision", "matches", "--user-words", "ok"]\r\nsubprocess.run(cmd)\r\n' > "$f"
    [ "$(tr -cd '\r' < "$f" | wc -c)" -eq 8 ]
    _expect_decision_block "$f" 5 7
}

@test "decision scan blocks a lowercase .r script with system2() and --decision=matches" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_10.r"
    printf '%s\n' 'quit(status = 0)  # inert guard' \
        'lv <- "/daaf/scripts/lit_verify.sh"' \
        'system2("bash", c(lv, "settle", "papers/k", "--items", "i.txt", "--decision=matches", "--user-words", "ok"))' > "$f"
    _expect_decision_block "$f" 3
}

@test "decision scan blocks .py settle with the --decisio prefix" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_11.py"
    printf '%s\n' 'import subprocess' 'raise SystemExit(0)  # inert guard' \
        'subprocess.run(["bash", "/daaf/scripts/lit_verify.sh", "settle", "papers/k", "--items", "i.txt", "--decisio", "matches", "--user-words", "ok"])' > "$f"
    _expect_decision_block "$f" 3
}

@test "decision scan still refuses when the script contains a NUL byte" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_nul.py"
    printf 'import subprocess\nraise SystemExit(0)  # inert guard\nx = "a\000b"\nsubprocess.run(["bash", "/daaf/scripts/lit_corpus.sh", "adjudications", "record-human", "proj"])\n' > "$f"
    [ "$(tr -cd '\000' < "$f" | wc -c)" -eq 1 ]
    run bash "$RUN_WITH_CAPTURE_SH" "$f"
    [ "$status" -eq 3 ]
    assert_output --partial "researcher decision command detected"
    refute_output --partial "INERT_COMPUTATION_COMPLETED"
}

# --- Allow -----------------------------------------------------------------------

@test "decision scan allows settle --list (.py and .R): it records no decision" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_ok_01.py"
    printf '%s\n' 'import subprocess' \
        'subprocess.run(["bash", "/daaf/scripts/lit_verify.sh", "settle", "papers/k", "--audit", "vision_audit.json", "--list"])' > "$f"
    _expect_decision_pass "$f"
    f="${BATS_TEST_TMPDIR}/dec_ok_01b.R"
    printf '%s\n' 'system2("bash", c("/daaf/scripts/lit_verify.sh", "settle", "papers/k", "--audit", "vision_audit.json", "--list"))' > "$f"
    _expect_decision_pass "$f"
}

@test "decision scan allows other lit_corpus and lit_verify calls and MANIFEST reads" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_ok_02.py"
    printf '%s\n' 'import json, subprocess' \
        'subprocess.run(["bash", "/daaf/scripts/lit_corpus.sh", "adjudications", "glance-sheet", "proj", "--deliverable", "d.md"])' \
        'subprocess.run(["bash", "/daaf/scripts/lit_corpus.sh", "manifest", "proj"])' \
        'subprocess.run(["bash", "/daaf/scripts/lit_verify.sh", "report", "proj", "d.md", "--data-version", "corpus=3"])' \
        'rows = [json.loads(l) for l in open("papers/MANIFEST.jsonl")]' \
        'settled = [r for r in rows if r.get("kind") == "lit_verify_settle" and r.get("command") == "settle"]' \
        'decisions = [r["parameters"]["decision"] for r in settled]' \
        'names = ["audit_settlement_1.json", "settle_items.txt"]' > "$f"
    _expect_decision_pass "$f"
}

@test "decision scan allows .py and .R whose only mentions are on full-line comments" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_ok_03.py"
    printf '%s\n' '# The orchestrator records the reply itself, never this script:' \
        '#   bash /daaf/scripts/lit_corpus.sh adjudications record-human PROJECT --rows FILE --decision same_work' \
        '    # bash /daaf/scripts/lit_verify.sh settle PAPER_DIR --audit A --items F --decision matches' \
        'print("ok")' > "$f"
    _expect_decision_pass "$f"
    f="${BATS_TEST_TMPDIR}/dec_ok_03b.R"
    printf '%s\n' '# system2("bash", c("/daaf/scripts/lit_verify.sh", "settle", "p", "--decision", "matches"))' \
        '# lit_corpus.sh adjudications record-human' 'cat("ok\n")' > "$f"
    _expect_decision_pass "$f"
}

@test "decision scan allows the word settle and a --decision flag in a script that never names lit_verify" {
    _inert_interpreters
    local f="${BATS_TEST_TMPDIR}/dec_ok_04.py"
    printf '%s\n' 'import argparse' \
        'print("let the estimates settle before comparing")' \
        'p = argparse.ArgumentParser()' \
        'p.add_argument("--decision")' > "$f"
    _expect_decision_pass "$f"
}
