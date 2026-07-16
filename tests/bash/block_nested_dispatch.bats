#!/usr/bin/env bats
# ============================================================================
# Tests for block-nested-dispatch.sh -- PreToolUse nested-dispatch guard
# ============================================================================
# Focus: the caller-detection contract. A Task/Agent dispatch that originates
# INSIDE a subagent must be DENIED (all dispatch authority belongs to the
# orchestrator); a main-thread (orchestrator) dispatch must be ALLOWED. The
# hook reads two caller-identifying stdin fields:
#   agent_id   -- present ONLY inside a subagent call (absent on main thread)
#   agent_type -- the subagent's type inside a subagent call; absent on the
#                 main thread. The `!= "orchestrator"` carve-out future-proofs
#                 against a harness that sends agent_type:"orchestrator"
#                 literally on the main thread -- that must still ALLOW.
#
# The guard is fail-open (orchestration-discipline guard, not a safety
# boundary): missing jq, empty stdin, and malformed JSON all ALLOW (exit 0),
# mirroring enforce-model-ceiling.sh and block-remote-isolation.sh.
#
# SCRIPT UNDER TEST is parameterized: BLOCK_NESTED_DISPATCH_SH defaults to the
# installed hook but can be pointed at a proposed copy for pre-deployment
# testing, e.g.:
#   BLOCK_NESTED_DISPATCH_SH=/path/to/draft/block-nested-dispatch.sh \
#     bats block_nested_dispatch.bats
# ============================================================================

load 'test_helper'

# Path to the script under test (override to test a proposed/deliverable copy).
BLOCK_NESTED_DISPATCH_SH="${BLOCK_NESTED_DISPATCH_SH:-${REPO_ROOT}/.claude/hooks/block-nested-dispatch.sh}"

setup() {
    common_setup
    export BLOCK_NESTED_DISPATCH_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A main-thread Agent dispatch payload: no agent_id, no agent_type (the
# orchestrator's own dispatches carry neither field).
_payload_main() {
    jq -nc '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {
            "description": "Profile the CCD enrollment extract",
            "prompt": "Read the parquet, compute enrollment by grade, save summary.",
            "subagent_type": "research-executor"
        }
    }'
}

# A payload with agent_type set literally to "orchestrator" -- the carve-out
# case: a future harness sending this on the main thread must still ALLOW.
_payload_orchestrator_typed() {
    jq -nc '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "agent_type": "orchestrator",
        "tool_input": {
            "description": "d",
            "prompt": "p",
            "subagent_type": "research-executor"
        }
    }'
}

# A subagent-fired dispatch payload identified by agent_id (present only inside
# subagent calls). Arg $1: the agent_id value.
_payload_subagent_id() {
    jq -nc --arg aid "$1" '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "agent_id": $aid,
        "agent_type": "general-purpose",
        "tool_input": {
            "description": "nested work",
            "prompt": "do a nested thing",
            "subagent_type": "general-purpose"
        }
    }'
}

# A subagent-fired dispatch payload identified by agent_type ALONE (agent_id
# absent) -- exercises the always-present positive-value detection leg. Arg $1:
# the agent_type value.
_payload_subagent_type_only() {
    jq -nc --arg atype "$1" '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Task",
        "agent_type": $atype,
        "tool_input": {
            "description": "nested work",
            "prompt": "do a nested thing",
            "subagent_type": "general-purpose"
        }
    }'
}

# =========================================================================
# Syntax
# =========================================================================

@test "block-nested-dispatch.sh parses without errors" {
    run bash -n "$BLOCK_NESTED_DISPATCH_SH"
    assert_success
}

# =========================================================================
# Case 1: main-thread payload (no agent_id/agent_type) -> ALLOW, empty stdout
# =========================================================================

@test "main thread (no agent_id/agent_type): exit 0, empty stdout (silent allow)" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < <(_payload_main)
    assert_success
    assert_output ""
}

# =========================================================================
# Case 2: agent_type:"orchestrator" present -> ALLOW (carve-out)
# =========================================================================

@test "agent_type literally 'orchestrator': exit 0, empty stdout (carve-out allows)" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < <(_payload_orchestrator_typed)
    assert_success
    assert_output ""
}

# Empty-string / null caller fields must ALLOW -- locks in the `// empty`
# jq semantics (empty string and null both normalize to "not a subagent
# caller") against a future refactor of the extraction lines.
@test "agent_id empty string + agent_type null: exit 0, empty stdout (allow)" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" \
        <<<'{"hook_event_name":"PreToolUse","tool_name":"Agent","agent_id":"","agent_type":null,"tool_input":{"description":"d","prompt":"p","subagent_type":"research-executor"}}'
    assert_success
    assert_output ""
}

# =========================================================================
# Case 3: agent_id present -> DENY
# =========================================================================

@test "agent_id present: DENY (dispatch originates inside a subagent)" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < <(_payload_subagent_id "agent-abc-123")
    assert_success
    # Output must be NON-EMPTY. On empty stdin jq -e produces zero outputs and
    # exits 0, so every downstream `echo "$output" | jq -e` would VACUOUSLY PASS
    # against a hook that (wrongly) emitted nothing. This bare test aborts on
    # empty output, forcing the deny cases to actually detect a no-emit defect.
    [ -n "$output" ]
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# =========================================================================
# Case 4: agent_type:"general-purpose" only (agent_id absent) -> DENY
# =========================================================================

@test "agent_type 'general-purpose' only (no agent_id): DENY via positive-value leg" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < <(_payload_subagent_type_only "general-purpose")
    assert_success
    [ -n "$output" ]  # non-empty guard (see case 3) -- abort on no-emit defect
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# A named-agent type alone (no agent_id) must also DENY -- any non-orchestrator
# agent_type identifies a subagent caller, not just the generic types.
@test "agent_type 'research-executor' only (no agent_id): DENY" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < <(_payload_subagent_type_only "research-executor")
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# =========================================================================
# Case 5: deny output is well-formed -- valid JSON, permissionDecision "deny",
# hookEventName "PreToolUse", and a non-empty reason.
# =========================================================================

@test "deny output: valid JSON with permissionDecision deny, hookEventName PreToolUse, reason present" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < <(_payload_subagent_id "agent-xyz")
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | length > 0' >/dev/null
    # The reason must direct the subagent to return work for redelegation.
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("orchestrator")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("nested subagents")' >/dev/null
}

# =========================================================================
# Case 6: Missing jq -> ALLOW (fail-open) with a fail-open stderr message.
# Simulated with a restricted PATH containing only symlinks to the binaries the
# hook needs MINUS jq (bash + cat). `command -v jq` then fails, hitting the
# fail-open jq-guard. We invoke via `env -i` to drop the ambient PATH entirely.
# =========================================================================

@test "missing jq: exit 0 with fail-open stderr message (allow)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    # No jq symlink -> `command -v jq` fails inside the hook.
    run env -i PATH="$bindir" bash "$BLOCK_NESTED_DISPATCH_SH" \
        <<<'{"hook_event_name":"PreToolUse","agent_id":"agent-abc","tool_input":{"description":"d","prompt":"p"}}'
    assert_success
    assert_output --partial "jq not found"
}

# =========================================================================
# Fail-open: empty stdin -> exit 0, no crash, no JSON emitted
# =========================================================================

@test "empty stdin: exit 0, fail-open (allow), no deny JSON" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" < /dev/null
    assert_success
    refute_output --partial "\"deny\""
}

# =========================================================================
# Fail-open: malformed / non-JSON stdin -> exit 0, no crash, no deny JSON
# =========================================================================

@test "malformed stdin: exit 0, fail-open (allow), no deny JSON" {
    run bash "$BLOCK_NESTED_DISPATCH_SH" <<<"this is not json {{{"
    assert_success
    refute_output --partial "\"deny\""
}
