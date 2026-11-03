#!/usr/bin/env bats
# ============================================================================
# Tests for deny-claude-code-guide.sh -- PreToolUse Task/Agent deny guard
# ============================================================================
# Contract (from the hook header): the built-in `claude-code-guide` agent runs
# on Haiku and carries an opaque system prompt, so it is DENIED. Any other
# subagent_type passes through untouched. The decision is carried in a
# `permissionDecision: deny` JSON body on stdout with exit 0 -- the Task/Agent
# tool-hook convention (contrast the Bash hooks, which block via exit 2).
#
# Registration: settings.json PreToolUse, under BOTH the "Task" and "Agent"
# matchers (verified by a test below).
#
# Failure posture (2026-09-24 hook-maintenance pass): mirrors the sibling
# enforce-explore-model.sh. With jq absent, a jq-free raw-text match on
# "subagent_type":"claude-code-guide" blocks via stderr + exit 2; other types
# still allow. The ERR trap is jq-free and blocks (exit 2). The JQ-ABSENCE
# tests near the bottom were flipped from the previous CURRENT-BEHAVIOR pin
# (a silent fail-OPEN allow) to this desired behavior.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   DENY_CLAUDE_CODE_GUIDE_SH=/path/to/draft.sh bats deny_claude_code_guide.bats
# ============================================================================

load 'test_helper'

DENY_CLAUDE_CODE_GUIDE_SH="${DENY_CLAUDE_CODE_GUIDE_SH:-${REPO_ROOT}/.claude/hooks/deny-claude-code-guide.sh}"

setup() {
    common_setup
    export DENY_CLAUDE_CODE_GUIDE_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A PreToolUse dispatch payload for subagent_type $1 under tool $2 (default Agent).
_dispatch_payload() {
    jq -nc --arg t "$1" --arg tool "${2:-Agent}" '{
        "hook_event_name": "PreToolUse",
        "tool_name": $tool,
        "tool_input": {
            "subagent_type": $t,
            "description": "probe dispatch",
            "prompt": "do a thing"
        }
    }'
}

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

@test "deny-claude-code-guide.sh parses without errors" {
    run bash -n "$DENY_CLAUDE_CODE_GUIDE_SH"
    assert_success
}

@test "deny-claude-code-guide.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "$DENY_CLAUDE_CODE_GUIDE_SH"
    assert_success
}

# =========================================================================
# DENY: claude-code-guide
# =========================================================================

@test "claude-code-guide via Agent: DENY with well-formed decision JSON" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "claude-code-guide" "Agent")
    assert_success
    [ -n "$output" ]  # non-empty guard: a no-emit hook would vacuously pass jq -e
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | length > 0' >/dev/null
}

@test "claude-code-guide via Task: DENY as well (both matchers registered)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "claude-code-guide" "Task")
    assert_success
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

@test "deny reason redirects to search-agent + WebSearch + web_fetch.sh" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "claude-code-guide")
    assert_success
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("search-agent")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("WebSearch")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("web_fetch.sh")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("web-retrieval")' >/dev/null
}

@test "hook process exits 0 while carrying the deny in the JSON body" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "claude-code-guide")
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# =========================================================================
# ALLOW: every other subagent_type passes through with no decision emitted
# =========================================================================

@test "search-agent: allowed (no decision emitted)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "search-agent")
    assert_success
    [ -z "$output" ]
}

@test "research-executor: allowed (no decision emitted)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "research-executor")
    assert_success
    [ -z "$output" ]
}

@test "general-purpose: allowed (no decision emitted)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "general-purpose")
    assert_success
    [ -z "$output" ]
}

# The match is exact equality, not a substring test -- a near-miss name is a
# different agent and must not be denied by accident.
@test "near-miss name (claude-code-guide-v2): allowed, not denied" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(_dispatch_payload "claude-code-guide-v2")
    assert_success
    [ -z "$output" ]
}

@test "payload with no subagent_type at all: allowed" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(jq -nc '{"tool_name":"Agent","tool_input":{"description":"x"}}')
    assert_success
    [ -z "$output" ]
}

# =========================================================================
# Malformed / empty input
# =========================================================================

@test "empty stdin: exits 0 with no decision (no crash)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < /dev/null
    assert_success
    [ -z "$output" ]
}

@test "malformed stdin: exits 0 with no decision (no crash)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" <<<"this is not json {{{"
    assert_success
    [ -z "$output" ]
}

# =========================================================================
# jq absence -- jq-free fallback (2026-09-24 hook-maintenance pass)
#
# DEFECT FIXED: the hook used to read subagent_type with `jq -r` and serialize
# its ERR-trap deny with `jq -n`. With jq off PATH, SUBAGENT_TYPE resolved to
# "" and the hook exited 0 emitting nothing -- which the harness reads as
# ALLOW, letting claude-code-guide spawn (a fail-OPEN path in a deny guard,
# contrary to the agent-authoring hook convention: "neither the trap nor the
# deny path may depend on the very tool whose absence they cover").
#
# DESIRED BEHAVIOR (now pinned): like enforce-explore-model.sh, a jq-free
# raw-text match on "subagent_type":"claude-code-guide" blocks with the
# redirect message on stderr + exit 2 (Claude Code's plain-text block);
# every other subagent type still allows. The first test below is the
# regression case: it FAILS on the pre-fix hook (exit 0, empty output).
# =========================================================================

@test "missing jq: claude-code-guide is BLOCKED via stderr + exit 2 (regression: was a silent allow)" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s' '{"tool_name":"Agent","tool_input":{"subagent_type":"claude-code-guide"}}')
    [ "$status" -eq 2 ]
    assert_output --partial "claude-code-guide is NOT permitted"
    assert_output --partial "search-agent"
}

@test "missing jq: whitespace around the colon still matches (JSON permits it)" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s' '{"tool_name":"Task","tool_input":{"subagent_type" :  "claude-code-guide"}}')
    [ "$status" -eq 2 ]
}

@test "missing jq: other subagent types still allowed (exit 0, silent)" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s' '{"tool_name":"Agent","tool_input":{"subagent_type":"search-agent"}}')
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "missing jq: near-miss name (claude-code-guide-v2) still allowed" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s' '{"tool_name":"Agent","tool_input":{"subagent_type":"claude-code-guide-v2"}}')
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# The ERR trap must not depend on jq either (static probe of the trap line).
@test "ERR trap is jq-free and blocks with exit 2" {
    run grep -E '^trap ' "$DENY_CLAUDE_CODE_GUIDE_SH"
    assert_success
    refute_output --partial "jq"
    assert_output --partial "exit 2"
}

@test "jq-absence simulation actually removes jq from the hook's PATH" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash -c 'command -v jq'
    assert_failure
}

# =========================================================================
# Multi-value stdin (2026-09-26, hook bundle revision _a)
#
# DEFECT FIXED: `jq -r '.tool_input.subagent_type // empty'` printed one line
# per top-level value, so a benign Agent object glued to a claude-code-guide
# object yielded a two-line SUBAGENT_TYPE that never equalled
# "claude-code-guide" -> ALLOW. Probed 2026-09-26 on the 2026-09-24 bundle
# copy: all four concatenated orders, banned+garbage, garbage+banned and a
# top-level array gave rc 0 with no decision. The fix denies when ANY value
# carries the banned subagent_type (streaming parse, plus the raw-text match
# when jq reports an error). Plain malformed/empty stdin still ALLOWS (pinned
# above). These DENY cases FAIL on the pre-fix hook.
# =========================================================================

_benign_obj() { _dispatch_payload "general-purpose" "Agent"; }
_guide_obj() { _dispatch_payload "claude-code-guide" "Agent"; }

_assert_json_deny() {
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

@test "concat: benign object + claude-code-guide object (no separator): DENY" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s%s' "$(_benign_obj)" "$(_guide_obj)")
    _assert_json_deny
}

@test "concat: claude-code-guide object + benign object (no separator): DENY" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s%s' "$(_guide_obj)" "$(_benign_obj)")
    _assert_json_deny
}

@test "concat: benign NEWLINE claude-code-guide: DENY" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s\n%s\n' "$(_benign_obj)" "$(_guide_obj)")
    _assert_json_deny
}

@test "concat: claude-code-guide NEWLINE benign: DENY" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s\n%s\n' "$(_guide_obj)" "$(_benign_obj)")
    _assert_json_deny
}

@test "concat: claude-code-guide object followed by garbage: DENY (values before the parse error count)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s garbage{{' "$(_guide_obj)")
    _assert_json_deny
}

@test "concat: garbage followed by a claude-code-guide pair: DENY (raw-text match after a parse error)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf 'garbage{{ %s' "$(_guide_obj)")
    _assert_json_deny
}

@test "top-level array containing a claude-code-guide object: DENY" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '[%s,%s]' "$(_benign_obj)" "$(_guide_obj)")
    _assert_json_deny
}

@test "concat: two benign objects: ALLOW (no decision)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s%s' "$(_benign_obj)" "$(_dispatch_payload "search-agent")")
    assert_success
    [ -z "$output" ]
}

@test "concat: benign + near-miss claude-code-guide-v2: ALLOW (exact match only)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s%s' "$(_benign_obj)" "$(_dispatch_payload "claude-code-guide-v2")")
    assert_success
    [ -z "$output" ]
}

@test "malformed stdin mentioning claude-code-guide only in prose: ALLOW (no subagent_type pair)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" <<<'not json {{{ please use claude-code-guide'
    assert_success
    [ -z "$output" ]
}

@test "a subagent_type with an embedded newline before claude-code-guide: ALLOW (whole-value match)" {
    run bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(jq -nc '{"tool_name":"Agent","tool_input":{"subagent_type":"x\nclaude-code-guide"}}')
    assert_success
    [ -z "$output" ]
}

@test "missing jq + concatenated benign + claude-code-guide: exit 2 (raw-text fallback)" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash "$DENY_CLAUDE_CODE_GUIDE_SH" < <(printf '%s%s' '{"tool_name":"Agent","tool_input":{"subagent_type":"general-purpose"}}' '{"tool_name":"Agent","tool_input":{"subagent_type":"claude-code-guide"}}')
    [ "$status" -eq 2 ]
}

# =========================================================================
# Registration
# =========================================================================

@test "registered under both the Task and Agent PreToolUse matchers" {
    run jq -r '
        [.hooks.PreToolUse[]
         | select(.hooks[].command | test("deny-claude-code-guide"))
         | .matcher]
        | sort | join(",")
    ' "${REPO_ROOT}/.claude/settings.json"
    assert_success
    assert_output "Agent,Task"
}
