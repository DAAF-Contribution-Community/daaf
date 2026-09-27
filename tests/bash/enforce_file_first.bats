#!/usr/bin/env bats
# ============================================================================
# Tests for enforce-file-first.sh -- agent-scoped PreToolUse Bash guard
# ============================================================================
# Contract (from the hook header): all Python and R scripts must be executed
# through run_with_capture.sh, which appends an execution log to the script as
# an immutable audit artifact. Direct `python`/`python3`, `Rscript`, and
# batch-capable bare-`R` invocations bypass that audit trail and are BLOCKED
# with exit 2 plus a stderr remediation message.
#
# Scope: registered in AGENT FRONTMATTER (research-executor, code-reviewer,
# debugger, data-ingest), NOT project-wide in settings.json. It therefore does
# not fire for the orchestrator or read-only agents.
#
# Failure posture: documented as fail-CLOSED (ERR trap blocks, missing jq
# blocks, empty stdin blocks, and -- since the 2026-09-24 hook-maintenance
# pass -- stdin that is not exactly one JSON object blocks). The MALFORMED-STDIN
# tests below were flipped from the previous CURRENT-BEHAVIOR pin (malformed
# stdin allowed) to this desired behavior.
#
# Exit-code convention: 0 = allow, 2 = block (Claude Code PreToolUse).
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   ENFORCE_FILE_FIRST_SH=/path/to/draft.sh bats enforce_file_first.bats
# ============================================================================

load 'test_helper'

ENFORCE_FILE_FIRST_SH="${ENFORCE_FILE_FIRST_SH:-${REPO_ROOT}/.claude/hooks/enforce-file-first.sh}"

setup() {
    common_setup
    export ENFORCE_FILE_FIRST_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# Build a PreToolUse Bash payload carrying $1 as the command string.
# Case strings live INSIDE the suite (never on the invoking command line), so
# the live PreToolUse hooks never vet the test corpus itself.
_bash_payload() {
    jq -nc --arg c "$1" '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": $c}
    }'
}

# Run the hook against a command string and populate $status/$output.
_run_cmd() {
    run bash "$ENFORCE_FILE_FIRST_SH" < <(_bash_payload "$1")
}

# A PATH directory containing only bash + cat, so `command -v jq` genuinely
# fails inside the hook (the jq-absence simulation used by the DAAF suites).
_nojq_bin() {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -sf "$(command -v bash)" "${bindir}/bash"
    ln -sf "$(command -v cat)" "${bindir}/cat"
    printf '%s' "$bindir"
}

# =========================================================================
# Static checks
# =========================================================================

@test "enforce-file-first.sh parses without errors" {
    run bash -n "$ENFORCE_FILE_FIRST_SH"
    assert_success
}

@test "enforce-file-first.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "$ENFORCE_FILE_FIRST_SH"
    assert_success
}

# =========================================================================
# BLOCK: Python entry points
# =========================================================================

@test "BLOCK: python script.py (bare interpreter + file)" {
    _run_cmd 'python analysis.py'
    [ "$status" -eq 2 ]
    assert_output --partial "BLOCKED by enforce-file-first hook"
    assert_output --partial "Direct python execution"
}

@test "BLOCK: python3 -c one-liner" {
    _run_cmd 'python3 -c "print(1)"'
    [ "$status" -eq 2 ]
    assert_output --partial "Direct python execution"
}

@test "BLOCK: versioned interpreter python3.11" {
    _run_cmd 'python3.11 analysis.py'
    [ "$status" -eq 2 ]
}

@test "BLOCK: absolute-path interpreter /usr/bin/python3" {
    _run_cmd '/usr/bin/python3 analysis.py'
    [ "$status" -eq 2 ]
}

@test "BLOCK: env-wrapper prefix (env python script.py)" {
    _run_cmd 'env python analysis.py'
    [ "$status" -eq 2 ]
}

@test "BLOCK: env-assignment prefix (PYTHONPATH=/foo python script.py)" {
    _run_cmd 'PYTHONPATH=/foo python analysis.py'
    [ "$status" -eq 2 ]
}

@test "BLOCK: quote-wrapped interpreter ('python3' script.py) [ADV11]" {
    _run_cmd "'python3' analysis.py"
    [ "$status" -eq 2 ]
}

@test "BLOCK: no-space stdin redirect (python3<script.py) [ADV12]" {
    _run_cmd 'python3<analysis.py'
    [ "$status" -eq 2 ]
}

@test "BLOCK: interpreter after a pipe boundary (echo x | python3 -)" {
    _run_cmd 'echo hi | python3 -'
    [ "$status" -eq 2 ]
}

@test "python block message names run_with_capture.sh as the remedy" {
    _run_cmd 'python analysis.py'
    [ "$status" -eq 2 ]
    assert_output --partial "run_with_capture.sh"
    assert_output --partial "SCRIPT_EXECUTION_REFERENCE.md"
}

# =========================================================================
# BLOCK: R entry points (both Rscript and batch-capable bare R)
# =========================================================================

@test "BLOCK: Rscript script.R" {
    _run_cmd 'Rscript analysis.R'
    [ "$status" -eq 2 ]
    assert_output --partial "Direct R execution"
}

@test "BLOCK: Rscript -e one-liner" {
    _run_cmd 'Rscript -e "1+1"'
    [ "$status" -eq 2 ]
}

@test "BLOCK: bare R -e one-liner" {
    _run_cmd 'R -e "1+1"'
    [ "$status" -eq 2 ]
    assert_output --partial "Direct R execution"
}

@test "BLOCK: bare R -f script.R" {
    _run_cmd 'R -f analysis.R'
    [ "$status" -eq 2 ]
}

@test "BLOCK: R CMD BATCH script.R" {
    _run_cmd 'R CMD BATCH analysis.R'
    [ "$status" -eq 2 ]
}

@test "BLOCK: R --no-save < script.R (spaced redirect)" {
    _run_cmd 'R --no-save < analysis.R'
    [ "$status" -eq 2 ]
}

@test "BLOCK: R --no-save<script.R (no-space redirect) [ADV12]" {
    _run_cmd 'R --no-save<analysis.R'
    [ "$status" -eq 2 ]
}

@test "BLOCK: quote-wrapped bare R ('R' -e ...) [ADV11]" {
    _run_cmd "'R' -e '1+1'"
    [ "$status" -eq 2 ]
}

@test "BLOCK: env-assignment prefix (R_LIBS=/foo Rscript script.R)" {
    _run_cmd 'R_LIBS=/foo Rscript analysis.R'
    [ "$status" -eq 2 ]
}

@test "R block message enumerates all batch entry points" {
    _run_cmd 'Rscript analysis.R'
    [ "$status" -eq 2 ]
    assert_output --partial "run_with_capture.sh"
    assert_output --partial "R CMD BATCH"
}

# =========================================================================
# ALLOW: the sanctioned file-first pattern
# =========================================================================

@test "ALLOW: run_with_capture.sh wrapping a .py script" {
    _run_cmd 'bash /daaf/scripts/run_with_capture.sh /daaf/research/p/scripts/01_fetch.py'
    assert_success
    [ -z "$output" ]
}

@test "ALLOW: run_with_capture.sh wrapping a .R script" {
    _run_cmd 'bash /daaf/scripts/run_with_capture.sh /daaf/research/p/scripts/01_fetch.R'
    assert_success
}

# =========================================================================
# ALLOW: whitelisted framework utilities under ${CLAUDE_PROJECT_DIR}/scripts/
# =========================================================================

@test "ALLOW: python3 /daaf/scripts/<utility>.py (framework CLI whitelist)" {
    _run_cmd 'python3 /daaf/scripts/compare_execution_logs.py a b'
    assert_success
}

@test "ALLOW: Rscript /daaf/scripts/<utility>.R (framework CLI whitelist)" {
    _run_cmd 'Rscript /daaf/scripts/check_profile_templates.R'
    assert_success
}

@test "whitelist is scoped to the framework root, not a project scripts/ dir" {
    # A research project's own scripts/ directory must NOT inherit the
    # framework-utility carve-out -- those are pipeline scripts.
    _run_cmd 'python3 /daaf/research/proj/scripts/01_fetch.py'
    [ "$status" -eq 2 ]
}

# =========================================================================
# ALLOW: read-only inspection and non-interpreter uses of the tokens
# =========================================================================

@test "ALLOW: pip list (package inspection, not interpreter invocation)" {
    _run_cmd 'pip list'
    assert_success
}

@test "ALLOW: R --version (documented harmless interpreter probe)" {
    _run_cmd 'R --version'
    assert_success
}

# CURRENT BEHAVIOR, asymmetric with `R --version` above. The hook's R branch
# requires a batch flag before blocking, so `R --version` passes; the Python
# branch blocks on the interpreter token alone, so `python --version` is
# BLOCKED. The hook header lists `R --version` under ALLOWS but makes no
# corresponding claim for `python --version`, so this is a fail-closed
# asymmetry rather than a contract violation. Pinned so a future symmetry fix
# surfaces as a failing test to update rather than passing silently.
@test "CURRENT BEHAVIOR: python --version is blocked (asymmetric with R --version)" {
    _run_cmd 'python --version'
    [ "$status" -eq 2 ]
}

@test "ALLOW: python as a grep argument, not a command" {
    _run_cmd 'grep python notes.txt'
    assert_success
}

@test "ALLOW: interpreter-like token inside a quoted string argument" {
    _run_cmd 'grep "python3 -c" notes.md'
    assert_success
}

@test "ALLOW: python inside a path argument (ls /usr/lib/python3/...)" {
    _run_cmd 'ls /usr/lib/python3/dist-packages'
    assert_success
}

@test "ALLOW: bare R as another command's flag (git log -R)" {
    _run_cmd 'git log -R'
    assert_success
}

@test "ALLOW: marimo run notebook.py (runtime, not interpreter)" {
    _run_cmd 'marimo run notebook.py'
    assert_success
}

# =========================================================================
# Scope: non-Bash tool calls are passed through untouched
# =========================================================================

@test "non-Bash tool call: allowed without inspection" {
    run bash "$ENFORCE_FILE_FIRST_SH" < <(jq -nc '{
        "tool_name": "Read",
        "tool_input": {"file_path": "/daaf/scripts/analysis.py"}
    }')
    assert_success
}

@test "Bash call with no command field: allowed (nothing to inspect)" {
    run bash "$ENFORCE_FILE_FIRST_SH" < <(jq -nc '{"tool_name":"Bash","tool_input":{}}')
    assert_success
}

# =========================================================================
# Dependency and malformed-input posture
# =========================================================================

@test "missing jq: exit 2 (fail-closed), not a silent allow" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash "$ENFORCE_FILE_FIRST_SH" < <(printf '%s' '{"tool_name":"Bash","tool_input":{"command":"ls"}}')
    [ "$status" -eq 2 ]
    assert_output --partial "jq is not installed"
}

# Guard that the jq-absence simulation is real -- if jq ever leaked into the
# stripped PATH the test above would silently exercise the ordinary path.
@test "jq-absence simulation actually removes jq from the hook's PATH" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash -c 'command -v jq'
    assert_failure
}

@test "empty stdin: exit 2 (fail-closed on abnormal input)" {
    run bash "$ENFORCE_FILE_FIRST_SH" < /dev/null
    [ "$status" -eq 2 ]
    assert_output --partial "received empty input"
}

# DEFECT FIXED (2026-09-24 hook-maintenance pass): MALFORMED-STDIN.
# Non-JSON stdin used to make every `jq -r` fail, so TOOL_NAME resolved to ""
# and the hook exited 0 (ALLOW) at the `!= "Bash"` gate, never reaching the
# interpreter patterns -- contradicting the header's "Fail CLOSED: if anything
# unexpected goes wrong, block the command" (empty stdin already blocked).
# The hook now requires stdin to be exactly one JSON object and blocks
# otherwise. The first and last tests below are regression cases: both FAIL
# on the pre-fix hook (exit 0).
@test "malformed stdin: exit 2 (regression: was an allow, unlike empty stdin)" {
    run bash "$ENFORCE_FILE_FIRST_SH" <<<"this is not json {{{"
    [ "$status" -eq 2 ]
    assert_output --partial "not a single JSON object"
}

@test "whitespace-only stdin: exit 2 (non-empty but carries no JSON value)" {
    run bash "$ENFORCE_FILE_FIRST_SH" <<<"   "
    [ "$status" -eq 2 ]
}

@test "valid JSON that is not an object (a bare string): exit 2" {
    run bash "$ENFORCE_FILE_FIRST_SH" <<<'"python analysis.py"'
    [ "$status" -eq 2 ]
}

# Concatenated values: a benign object followed by a Bash call. Pre-fix, jq
# emitted two tool_name lines ("Read\nBash"), which is != "Bash", so the
# interpreter call was ALLOWED unseen. The single-object guard blocks it.
@test "concatenated JSON objects smuggling a python call: exit 2 (regression: was an allow)" {
    run bash "$ENFORCE_FILE_FIRST_SH" <<<'{"tool_name":"Read","tool_input":{"file_path":"/x"}}{"tool_name":"Bash","tool_input":{"command":"python analysis.py"}}'
    [ "$status" -eq 2 ]
}

# =========================================================================
# Registration: the hook is agent-scoped, not project-wide
# =========================================================================

@test "registered in the frontmatter of exactly the four coding agents" {
    run grep -l "enforce-file-first.sh" "${REPO_ROOT}"/.claude/agents/research-executor.md \
        "${REPO_ROOT}"/.claude/agents/code-reviewer.md \
        "${REPO_ROOT}"/.claude/agents/debugger.md \
        "${REPO_ROOT}"/.claude/agents/data-ingest.md
    assert_success
    [ "${#lines[@]}" -eq 4 ]
}

@test "NOT registered project-wide in settings.json" {
    run grep -c "enforce-file-first" "${REPO_ROOT}/.claude/settings.json"
    # grep -c prints 0 and exits 1 when there are no matches
    [ "$output" = "0" ]
}
