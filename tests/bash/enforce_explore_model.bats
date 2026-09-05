#!/usr/bin/env bats
# ============================================================================
# Tests for enforce-explore-model.sh -- PreToolUse Explore-subagent guard
# ============================================================================
# Contract (from the hook): a dispatch whose tool_input.subagent_type is
# "Explore" is DENIED and redirected to the DAAF-native `search-agent` (Explore
# runs on Haiku, which lacks the reasoning depth DAAF wants for codebase
# analysis). Any other subagent_type is ALLOWED (exit 0, empty stdout).
#
# Failure posture: the hook only blocks on a positively identified "Explore"
# dispatch, so unidentifiable payloads (empty stdin, malformed JSON) ALLOW --
# this is a routing preference, not a safety boundary, and blocking every
# dispatch over a bookkeeping failure would halt the pipeline. Missing jq is the
# exception that was hardened: the hook checks `command -v jq` before use and,
# without jq, falls back to a whitespace-tolerant, case-sensitive raw-text match
# for a "subagent_type": "Explore" pair, blocking a match with stderr + exit 2
# (Claude Code's plain-text block). A jq-less container therefore still blocks
# Explore instead of silently allowing it. The ERR trap likewise blocks via
# stderr + exit 2 and is jq-free.
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
# Missing jq: the hook falls back to a raw-text match on the stdin payload, so
# an Explore dispatch is STILL blocked -- via stderr + exit 2 rather than deny
# JSON (which cannot be serialized without jq). Anything not positively
# identifiable as Explore continues to ALLOW.
#
# The jq-absence is simulated by running the hook under `env -i` with a PATH
# containing only symlinks to bash and cat, so `command -v jq` genuinely fails
# inside the hook. The fallback uses bash builtins only (printf, [[ =~ ]]), so
# it needs nothing beyond those symlinks.
# =========================================================================

# Guard that the simulation is real: if jq ever leaked into the sandbox PATH,
# the fallback tests below would silently exercise the ordinary jq path.
@test "jq-absence simulation actually removes jq from the hook's PATH" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash -c 'command -v jq'
    assert_failure
}

@test "missing jq + Explore: exit 2 (plain-text block), not a silent allow" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" < <(printf '%s' '{"tool_input":{"subagent_type":"Explore"}}')
    [ "$status" -eq 2 ]
    assert_output --partial "search-agent"
}

# Whitespace tolerance: JSON permits spaces around the colon, and a pretty-
# printed payload must not slip past the raw-text matcher.
@test "missing jq + Explore (spaced JSON): exit 2 (whitespace-tolerant match)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" < <(printf '%s' '{"tool_input": {"subagent_type" :  "Explore"}}')
    [ "$status" -eq 2 ]
}

@test "missing jq + non-Explore: ALLOW (exit 0, no block)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" < <(printf '%s' '{"tool_input":{"subagent_type":"search-agent"}}')
    assert_success
    refute_output --partial "search-agent instead"
}

# Case-sensitivity lock for the fallback, mirroring the jq path: lowercase
# "explore" is not a real subagent type and must ALLOW.
@test "missing jq + 'explore' (lowercase): ALLOW (case-sensitive raw match)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" < <(printf '%s' '{"tool_input":{"subagent_type":"explore"}}')
    assert_success
}

# Decision recorded here deliberately: malformed/empty stdin WITHOUT jq and
# without an Explore match ALLOWS. Reasoning -- with no parser there is no way to
# distinguish "malformed payload" from "some other subagent type", and this hook
# guards a routing preference, not a safety boundary (contrast block-webfetch.sh,
# whose decision is unconditional and therefore blocks on every path). Denying
# every dispatch whenever stdin is unparseable would halt the whole pipeline over
# a bookkeeping failure; the proportionate posture is to block only what is
# positively identifiable as Explore.
@test "missing jq + malformed stdin: ALLOW (nothing positively identifiable)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" <<<"not json at all {{{"
    assert_success
}

@test "missing jq + empty stdin: ALLOW (nothing positively identifiable)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$ENFORCE_EXPLORE_MODEL_SH" < /dev/null
    assert_success
}

# =========================================================================
# jq present: the primary path is unchanged -- an Explore dispatch still yields
# the richer JSON deny on stdout with exit 0 (the fallback must not displace it).
# =========================================================================

@test "jq present: primary path still emits JSON deny (exit 0, no exit 2)" {
    command -v jq >/dev/null  # precondition: this suite's normal environment has jq
    run bash "$ENFORCE_EXPLORE_MODEL_SH" < <(_payload "Explore")
    [ "$status" -eq 0 ]
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("search-agent")' >/dev/null
}
