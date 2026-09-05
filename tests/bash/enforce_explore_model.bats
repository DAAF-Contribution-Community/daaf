#!/usr/bin/env bats
# ============================================================================
# Tests for enforce-explore-model.sh -- PreToolUse Explore-subagent guard
# ============================================================================
# Contract (from the hook): a dispatch whose tool_input.subagent_type is
# "Explore" is DENIED and redirected to the DAAF-native `search-agent` (Explore
# runs on Haiku, which lacks the reasoning depth DAAF wants for codebase
# analysis). Any other subagent_type is ALLOWED (exit 0, empty stdout).
#
# Failure posture: the hook extracts subagent_type with `... || SUBAGENT_TYPE=""`
# and only denies on an exact "Explore" match, so every uncertain path (empty
# stdin, malformed JSON, missing jq) yields an empty type and therefore ALLOWS.
# The ERR trap emits a deny only on a genuinely unexpected failure. In practice
# the only way to reach a deny is an actual Explore dispatch.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft copy:
#   ENFORCE_EXPLORE_MODEL_SH=/path/to/draft.sh bats enforce_explore_model.bats
# ============================================================================

load 'test_helper'

ENFORCE_EXPLORE_MODEL_SH="${ENFORCE_EXPLORE_MODEL_SH:-${REPO_ROOT}/.claude/hooks/enforce-explore-model.sh}"

setup() {
    common_setup
    export ENFORCE_EXPLORE_MODEL_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A dispatch payload with subagent_type = $1.
_payload() {
    jq -nc --arg stype "$1" '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Task",
        "tool_input": {
            "description": "explore the codebase",
            "prompt": "map the module layout",
            "subagent_type": $stype
        }
    }'
}

# =========================================================================
# Syntax
# =========================================================================

@test "enforce-explore-model.sh parses without errors" {
    run bash -n "$ENFORCE_EXPLORE_MODEL_SH"
    assert_success
}

# =========================================================================
# DENY: subagent_type = "Explore"
# =========================================================================

@test "subagent_type 'Explore': DENY with well-formed decision" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < <(_payload "Explore")
    assert_success
    [ -n "$output" ]  # non-empty guard: a no-emit hook would vacuously pass jq -e
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | length > 0' >/dev/null
}

@test "Explore deny reason redirects to search-agent and names Explore" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < <(_payload "Explore")
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("search-agent")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("Explore")' >/dev/null
}

# =========================================================================
# ALLOW: any non-Explore subagent_type
# =========================================================================

@test "subagent_type 'search-agent': ALLOW (exit 0, empty stdout)" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < <(_payload "search-agent")
    assert_success
    assert_output ""
}

@test "subagent_type 'general-purpose': ALLOW (exit 0, empty stdout)" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < <(_payload "general-purpose")
    assert_success
    assert_output ""
}

# Case-sensitivity lock: the match is exact "Explore"; a lowercase "explore" is
# NOT a recognized subagent type and must ALLOW (guards against a future refactor
# accidentally lowercasing the comparison and denying legitimate dispatches).
@test "subagent_type 'explore' (lowercase): ALLOW (exact-match is case-sensitive)" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < <(_payload "explore")
    assert_success
    assert_output ""
}

# =========================================================================
# Fail-open: empty stdin -> ALLOW (no type to match), no deny JSON
# =========================================================================

@test "empty stdin: exit 0, no deny JSON (no type to match)" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < /dev/null
    assert_success
    refute_output --partial "\"deny\""
}

# =========================================================================
# Fail-open: malformed / non-JSON stdin -> ALLOW, no deny JSON
# =========================================================================

@test "malformed stdin: exit 0, no deny JSON" {
    run bash "$ENFORCE_EXPLORE_MODEL_SH" <<<"not json at all {{{"
    assert_success
    refute_output --partial "\"deny\""
}

# =========================================================================
# Missing jq: the type cannot be parsed, so the hook cannot detect Explore and
# ALLOWS (exit 0). Documents the observed behavior -- jq is always present in the
# DAAF container, so this is a degradation note, not a supported operating mode.
# =========================================================================

@test "missing jq: exit 0, no deny JSON (type unparseable -> allow)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    ln -s "$(command -v echo)" "${bindir}/echo" 2>/dev/null || true
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" < <(printf '%s' '{"tool_input":{"subagent_type":"Explore"}}')
    assert_success
    refute_output --partial "\"deny\""
}
