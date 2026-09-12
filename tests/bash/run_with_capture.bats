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
