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

# The expected updatedInput for the fixtures above: the same tool_input with
# `isolation` removed. Deep-equality target for the reconstruction assertions.
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
}

# =========================================================================
# Case 2: Agent + isolation:"worktree" -> same guarantees
# =========================================================================

@test "agent + worktree: updatedInput deep-equals tool_input minus isolation; context mentions worktree" {
    local expected
    expected="$(_expected_updated_input)"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Agent" "worktree")
    assert_success
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
# Case 7: isolation:"" (empty string) -> exit 0, empty stdout (current policy)
# =========================================================================

@test "empty-string isolation: exit 0, empty stdout (silent pass-through)" {
    local input
    input="$(jq -nc '{"tool_name":"Agent","tool_input":{"description":"d","prompt":"p","isolation":""}}')"
    run bash "$BLOCK_REMOTE_ISOLATION_SH" <<<"$input"
    assert_success
    assert_output ""
}

# =========================================================================
# Case 8: Malformed / non-JSON stdin -> exit 0, no crash (fail-open)
# =========================================================================

@test "malformed stdin: exit 0, fail-open (no crash)" {
    run bash "$BLOCK_REMOTE_ISOLATION_SH" <<<"this is not json {{{"
    assert_success
}

# =========================================================================
# Case 9: Missing jq -> exit 0 with fail-open stderr message.
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
# Case 10: Regression sentinel -- the exact fields whose ABSENCE caused the
# production failure. Asserts updatedInput still HAS description + prompt.
# This is the case that fails loudest against the v3 partial-object hook.
# =========================================================================

@test "regression sentinel: updatedInput retains description and prompt (the fields the v3 defect dropped)" {
    run bash "$BLOCK_REMOTE_ISOLATION_SH" < <(_payload "Agent" "remote")
    assert_success
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("description")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("prompt")' >/dev/null
    # And isolation must be gone.
    echo "$output" | jq -e '.hookSpecificOutput.updatedInput | has("isolation") | not' >/dev/null
}
