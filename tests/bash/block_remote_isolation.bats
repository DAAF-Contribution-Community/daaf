#!/usr/bin/env bats
# ============================================================================
# Tests for block-remote-isolation.sh -- PreToolUse isolation-strip hook
# ============================================================================
# Focus: the updatedInput reconstruction contract. PreToolUse updatedInput
# REPLACES tool_input wholesale (per https://code.claude.com/docs/en/hooks.md;
# there is NO merge-patch / null-deletion mechanism), so the hook must emit the
# COMPLETE original tool_input with only `isolation` removed. The v3 defect
# (commit 3444e11) emitted a partial {"isolation": null}, which replaced the
# whole payload and dropped the required `description`/`prompt` fields, breaking
# every isolation-filled Agent/Task dispatch with a schema validation error.
#
# The deep-equality cases here (updatedInput == tool_input-minus-isolation) and
# the regression sentinel (updatedInput still has description + prompt) fail
# against the v3 hook and pass against the v4 fix.
#
# The v4 guard keys on KEY PRESENCE, not truthiness: the isolation KEY is
# stripped whenever present regardless of value (string, "", null, false,
# object, array), matching the provider shim sanitizer
# (anthropic_openai_shim.py:996 -- pop "isolation" whenever present). This
# CHANGES the empty-string case relative to the truthiness draft: isolation:""
# now STRIPS (it previously passed through silently). isolation:false and
# isolation:null -- which jq's `//` operator would have leaked through
# unstripped -- also strip. Only KEY-ABSENT (or missing/non-object tool_input)
# yields the silent exit-0 pass-through.
#
# v4.1 (2026-07-13, advisory wording only): test 2 additionally pins the
# anti-re-dispatch advisory phrases ("proceeded successfully", "do not
# re-dispatch") after a GPT session re-dispatched 5x, misreading the sanitized
# rendered input as a failed parameter submission.
#
# SCRIPT UNDER TEST is parameterized: BLOCK_REMOTE_ISOLATION_SH defaults to the
# installed hook but can be pointed at a proposed copy for pre-deployment
# testing, e.g.:
#   BLOCK_REMOTE_ISOLATION_SH=/path/to/deliverables/block-remote-isolation.sh \
#     bats block_remote_isolation.bats
# ============================================================================

load 'test_helper'

# Path to the script under test (override to test a proposed/deliverable copy).
BLOCK_REMOTE_ISOLATION_SH="${BLOCK_REMOTE_ISOLATION_SH:-${REPO_ROOT}/.claude/hooks/block-remote-isolation.sh}"

setup() {
    common_setup
    export BLOCK_REMOTE_ISOLATION_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A realistic multi-field Agent payload with an isolation value. Args:
#   $1 tool_name (e.g. "Agent" / "Task")
#   $2 isolation value (e.g. "remote" / "worktree" / "banana")
# Includes a nested object field (`env`) to guard against shallow
# reconstruction that only preserves top-level scalars.
_payload() {
    local tool_name="$1" iso="$2"
    jq -nc --arg tn "$tool_name" --arg iso "$iso" '{
        "tool_name": $tn,
        "tool_input": {
            "description": "Profile the CCD enrollment extract",
            "prompt": "Read the parquet, compute enrollment by grade, save summary.",
            "subagent_type": "research-executor",
            "model": "sonnet",
            "run_in_background": true,
            "isolation": $iso,
            "env": { "STAGE": "profile", "retries": 2 }
        }
    }'
}

# Same multi-field Agent payload but with a TYPED (non-string) isolation value,
# so the JSON types false / null / 0 survive as themselves rather than becoming
# strings. Arg $1 is a raw JSON literal (e.g. false, null, "", "worktree").
_payload_typed() {
    local iso_json="$1"
    jq -nc --argjson iso "$iso_json" '{
        "tool_name": "Agent",
        "tool_input": {
            "description": "Profile the CCD enrollment extract",
            "prompt": "Read the parquet, compute enrollment by grade, save summary.",
            "subagent_type": "research-executor",
            "model": "sonnet",
            "run_in_background": true,
            "isolation": $iso,
            "env": { "STAGE": "profile", "retries": 2 }
        }
    }'
}

# The expected updatedInput for the fixtures above: the same tool_input with
# `isolation` removed. Deep-equality target for the reconstruction assertions.
# Shared by both _payload and _payload_typed (they differ only in the isolation
# value, which is stripped either way).
_expected_updated_input() {
    jq -nc '{
        "description": "Profile the CCD enrollment extract",
        "prompt": "Read the parquet, compute enrollment by grade, save summary.",
        "subagent_type": "research-executor",
        "model": "sonnet",
        "run_in_background": true,
        "env": { "STAGE": "profile", "retries": 2 }
    }'
}

# =========================================================================
# Syntax
# =========================================================================

@test "block-remote-isolation.sh parses without errors" {
    run bash -n "$BLOCK_REMOTE_ISOLATION_SH"
    assert_success
}

# =========================================================================
# Case 1: Agent + isolation:"remote" -> full reconstruction, deep equality
# =========================================================================

@test "agent + remote: output is valid JSON, updatedInput deep-equals tool_input minus isolation" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Agent" "remote")
    assert_success
    # Output must be NON-EMPTY. Critical: on empty stdin jq -e produces zero
    # outputs and exits 0, so every downstream `echo "$output" | jq -e` would
    # VACUOUSLY PASS against a hook that (wrongly) emitted nothing. This bare
    # test aborts the test on empty output (bats fails on a mid-test non-zero
    # command), forcing the strip cases to actually detect a no-emit defect.
    [ -n "$output" ]
    # Output parses as JSON.
    echo "$output" | jq -e '.' >/dev/null
    # DEEP structural equality of updatedInput against the expected object.
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    # Decision + event name.
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
    # additionalContext non-empty and mentions the stripped value.
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | length > 0' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | contains("remote")' >/dev/null
    # v4.1 anti-re-dispatch sentinels: the advisory must state that the dispatch
    # SUCCEEDED and must forbid re-dispatching — a GPT session misread the
    # sanitized (isolation-free) rendered input as a failed submission and
    # re-dispatched 5x. These phrases are load-bearing model-facing contract.
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | contains("proceeded successfully")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | contains("do not re-dispatch")' >/dev/null
}

# =========================================================================
# Case 2: Agent + isolation:"worktree" -> same guarantees
# =========================================================================

@test "agent + worktree: updatedInput deep-equals tool_input minus isolation; context mentions worktree" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Agent" "worktree")
    assert_success
    [ -n "$output" ]  # non-empty guard (see case 1) — abort on no-emit defect
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | contains("worktree")' >/dev/null
}

# =========================================================================
# Case 3: Task payload with isolation -> same preservation guarantees
# =========================================================================

@test "task + remote: same reconstruction guarantees as Agent" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Task" "remote")
    assert_success
    [ -n "$output" ]  # non-empty guard (see case 1) — abort on no-emit defect
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
}

# =========================================================================
# Case 4: Unknown isolation value -> stripped, everything else preserved
# =========================================================================

@test "agent + unknown value (banana): stripped; rest preserved via deep equality" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Agent" "banana")
    assert_success
    [ -n "$output" ]  # non-empty guard (see case 1) — abort on no-emit defect
    # isolation key must be gone regardless of the (unrecognized) value.
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("isolation") | not' >/dev/null
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | contains("banana")' >/dev/null
}

# =========================================================================
# Case 5: Nested/unusual extra fields preserved exactly (guards against
# shallow reconstruction). Uses a bespoke payload with an extra nested object
# NOT present in the shared fixture.
# =========================================================================

@test "agent: unusual extra nested field is preserved exactly (no shallow rebuild)" {
    local input expected
    input="$(jq -nc '{
        "tool_name": "Agent",
        "tool_input": {
            "description": "d",
            "prompt": "p",
            "isolation": "worktree",
            "weird_extra": { "a": [1, 2, {"deep": "kept"}], "b": null }
        }
    }')"
    expected="$(jq -nc '{
        "description": "d",
        "prompt": "p",
        "weird_extra": { "a": [1, 2, {"deep": "kept"}], "b": null }
    }')"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" <<<"$input"
    assert_success
    [ -n "$output" ]  # non-empty guard (see case 1) — abort on no-emit defect
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
}

# =========================================================================
# Case 6: No isolation field -> exit 0, empty stdout (silent pass-through)
# =========================================================================

@test "no isolation field: exit 0, empty stdout" {
    local input
    input="$(jq -nc '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"p"}}')"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" <<<"$input"
    assert_success
    assert_output ""
}

# =========================================================================
# Case 7: isolation:"" (empty string) -> now STRIPPED (key-presence contract).
# This deliberately differs from the earlier truthiness draft, where "" passed
# through silently. Under key-presence semantics the key is present, so it is
# removed and the rest of tool_input is preserved. (An empty string would fail
# the Agent enum schema anyway.)
# =========================================================================

@test "empty-string isolation: STRIPPED, other fields preserved (key-presence contract)" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload_typed '""')
    assert_success
    # Non-empty guard is load-bearing here: a truthiness-guarded hook (or v3)
    # emits NOTHING for isolation:"" and would vacuously pass every jq -e below.
    [ -n "$output" ]
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("isolation") | not' >/dev/null
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
}

# =========================================================================
# Case 7a: isolation:false -> STRIPPED. jq's `//` alternative operator treats
# JSON false as empty, so a truthiness guard would have LEAKED this through
# unstripped. The key-presence guard strips it. This is a direct regression
# guard on WARNING-1.
# =========================================================================

@test "isolation:false: STRIPPED (jq // would have leaked it), deep-equals rest" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload_typed 'false')
    assert_success
    # Load-bearing: jq's // treats false as empty, so a truthiness guard (and
    # v3) emit NOTHING here. Without this guard the jq -e assertions below would
    # vacuously pass, hiding the WARNING-1 leak. This is the crux regression.
    [ -n "$output" ]
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("isolation") | not' >/dev/null
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "allow"' >/dev/null
}

# =========================================================================
# Case 7b: isolation:null -> STRIPPED. Same WARNING-1 leak class as false
# under a truthiness guard. additionalContext must still render safely
# (tostring -> "null").
# =========================================================================

@test "isolation:null: STRIPPED (jq // would have leaked it), deep-equals rest" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload_typed 'null')
    assert_success
    # Load-bearing (same as the false case): // treats null as empty, so a
    # truthiness guard / v3 emit NOTHING and would vacuously pass without this.
    [ -n "$output" ]
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("isolation") | not' >/dev/null
    echo "$output" | jq --argjson exp "$expected" -e \
        '.hookSpecificOutput.updatedInput == $exp' >/dev/null
    # additionalContext renders the stripped null safely (jq tostring).
    echo "$output" | jq -e '.hookSpecificOutput.additionalContext | length > 0' >/dev/null
}

# =========================================================================
# Case 7c: non-object tool_input (a string) -> silent exit 0. The guard's
# `(.tool_input? | type) == "object"` check must not crash or emit JSON when
# tool_input is not an object.
# =========================================================================

@test "non-object tool_input: exit 0, empty stdout (guard rejects non-object)" {
    local input
    input="$(jq -nc '{"tool_name":"Agent","tool_input":"i-am-a-string"}')"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" <<<"$input"
    assert_success
    assert_output ""
}

# =========================================================================
# Fail-open: Malformed / non-JSON stdin -> exit 0, no crash
# =========================================================================

@test "malformed stdin: exit 0, fail-open (no crash)" {
    run bash "$BLOCK_REMOTE_ISOLATION_SH" <<<"this is not json {{{"
    assert_success
}

# =========================================================================
# Fail-open: Missing jq -> exit 0 with fail-open stderr message.
# Simulated with a restricted PATH containing only symlinks to the binaries the
# hook needs MINUS jq (bash + cat). `command -v jq` then fails, hitting the
# fail-open jq-guard. We invoke via `env -i` to drop the ambient PATH entirely.
# =========================================================================

@test "missing jq: exit 0 with fail-open stderr message" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    # No jq symlink -> `command -v jq` fails inside the hook.
    run env -i PATH="$bindir" bash "$BLOCK_REMOTE_ISOLATION_SH" \
        <<<'{"tool_name":"Agent","tool_input":{"isolation":"remote","description":"d","prompt":"p"}}'
    assert_success
    assert_output --partial "jq not found"
}

# =========================================================================
# Regression sentinel -- the exact fields whose ABSENCE caused the production
# failure. Asserts updatedInput still HAS description + prompt. This is the
# case that fails loudest against the v3 partial-object hook.
# =========================================================================

@test "regression sentinel: updatedInput retains description and prompt (the fields the v3 defect dropped)" {
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Agent" "remote")
    assert_success
    [ -n "$output" ]  # non-empty guard (see case 1) — abort on no-emit defect
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("description")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("prompt")' >/dev/null
    # And isolation must be gone.
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("isolation") | not' >/dev/null
}
