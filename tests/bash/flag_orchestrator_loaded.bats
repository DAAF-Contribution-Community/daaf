#!/usr/bin/env bats
# ============================================================================
# Tests for flag-orchestrator-loaded.sh -- PostToolUse "Skill" matcher
# ============================================================================
# Contract (from the hook header): after a Skill tool call completes, if the
# loaded skill was `daaf-orchestrator`, write a session-scoped flag file that
# remind-orchestrator.sh reads to stop nagging. Any other skill is a no-op.
#
# Flag location: `${HOME}/.claude/daaf-state/orchestrator-loaded-{session_id}`
# -- the PERSISTENT home volume, deliberately NOT /tmp (changed 2026-07-15,
# because /tmp is wiped by container rebuilds while transcripts and session
# IDs survive them). That makes the whole hook redirectable in tests simply by
# overriding HOME, so no /tmp coordination path is touched by this suite.
#
# Housekeeping: flags older than 30 days are pruned at write time, pattern-
# anchored to `orchestrator-loaded-*` and -maxdepth 1, so nothing else in the
# state dir is collateral.
#
# Exit code: always 0 -- a PostToolUse hook must never block execution.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   FLAG_ORCHESTRATOR_LOADED_SH=/path/to/draft.sh bats flag_orchestrator_loaded.bats
# ============================================================================

load 'test_helper'

FLAG_ORCHESTRATOR_LOADED_SH="${FLAG_ORCHESTRATOR_LOADED_SH:-${REPO_ROOT}/.claude/hooks/flag-orchestrator-loaded.sh}"

setup() {
    common_setup
    export FLAG_ORCHESTRATOR_LOADED_SH
    # Redirect the hook's entire state surface into the bats temp dir by
    # overriding HOME. STATE_DIR is derived as "${HOME}/.claude/daaf-state",
    # so nothing is written outside TEST_DIR.
    FAKE_HOME="${TEST_DIR}/home"
    STATE_DIR="${FAKE_HOME}/.claude/daaf-state"
    mkdir -p "$FAKE_HOME"
    export FAKE_HOME STATE_DIR
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A PostToolUse Skill payload: skill $1, session_id $2 (default "sess-0001").
_skill_payload() {
    jq -nc --arg s "$1" --arg sid "${2:-sess-0001}" '{
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "session_id": $sid,
        "tool_input": {"skill": $s},
        "tool_response": "skill loaded"
    }'
}

# Run the hook with HOME redirected into TEST_DIR.
_run_hook() {
    run env HOME="$FAKE_HOME" bash "$FLAG_ORCHESTRATOR_LOADED_SH" < <(_skill_payload "$@")
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

@test "flag-orchestrator-loaded.sh parses without errors" {
    run bash -n "$FLAG_ORCHESTRATOR_LOADED_SH"
    assert_success
}

@test "flag-orchestrator-loaded.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "$FLAG_ORCHESTRATOR_LOADED_SH"
    assert_success
}

# =========================================================================
# Fires on daaf-orchestrator
# =========================================================================

@test "daaf-orchestrator load: creates the session-scoped flag file" {
    _run_hook "daaf-orchestrator" "sess-abc123"
    assert_success
    [ -f "${STATE_DIR}/orchestrator-loaded-sess-abc123" ]
}

@test "daaf-orchestrator load: creates the state dir if absent" {
    [ ! -d "$STATE_DIR" ]
    _run_hook "daaf-orchestrator" "sess-fresh"
    assert_success
    [ -d "$STATE_DIR" ]
}

@test "flag lands under HOME/.claude/daaf-state, not /tmp" {
    _run_hook "daaf-orchestrator" "sess-notmp"
    assert_success
    [ -f "${FAKE_HOME}/.claude/daaf-state/orchestrator-loaded-sess-notmp" ]
    # Nothing may be created under a /tmp coordination path by this hook.
    [ ! -e "/tmp/orchestrator-loaded-sess-notmp" ]
}

@test "flag name embeds the session id (distinct sessions, distinct flags)" {
    _run_hook "daaf-orchestrator" "sess-one"
    assert_success
    _run_hook "daaf-orchestrator" "sess-two"
    assert_success
    [ -f "${STATE_DIR}/orchestrator-loaded-sess-one" ]
    [ -f "${STATE_DIR}/orchestrator-loaded-sess-two" ]
}

@test "missing session_id falls back to the literal 'default'" {
    run env HOME="$FAKE_HOME" bash "$FLAG_ORCHESTRATOR_LOADED_SH" < <(jq -nc '{
        "tool_name": "Skill", "tool_input": {"skill": "daaf-orchestrator"}
    }')
    assert_success
    [ -f "${STATE_DIR}/orchestrator-loaded-default" ]
}

@test "re-firing for the same session is idempotent (one flag, no error)" {
    _run_hook "daaf-orchestrator" "sess-rerun"
    assert_success
    _run_hook "daaf-orchestrator" "sess-rerun"
    assert_success
    run bash -c 'ls -1 "$STATE_DIR" | wc -l'
    assert_output "1"
}

# =========================================================================
# Ignores every other skill
# =========================================================================

@test "other skill (polars): no flag written" {
    _run_hook "polars" "sess-other"
    assert_success
    [ ! -e "${STATE_DIR}/orchestrator-loaded-sess-other" ]
}

@test "other skill (skill-authoring): state dir is not even created" {
    _run_hook "skill-authoring" "sess-other2"
    assert_success
    [ ! -d "$STATE_DIR" ]
}

# Exact-match guard: a near-miss skill name must not trip the flag.
@test "near-miss skill name (daaf-orchestrator-v2): no flag written" {
    _run_hook "daaf-orchestrator-v2" "sess-near"
    assert_success
    [ ! -e "${STATE_DIR}/orchestrator-loaded-sess-near" ]
}

@test "payload with no skill field: no flag written" {
    run env HOME="$FAKE_HOME" bash "$FLAG_ORCHESTRATOR_LOADED_SH" < <(jq -nc '{
        "tool_name": "Skill", "session_id": "sess-noskill", "tool_input": {}
    }')
    assert_success
    [ ! -e "${STATE_DIR}/orchestrator-loaded-sess-noskill" ]
}

# =========================================================================
# Housekeeping: 30-day pruning is pattern-anchored
# =========================================================================

@test "stale orchestrator-loaded-* flags (>30d) are pruned at write time" {
    mkdir -p "$STATE_DIR"
    touch -d '60 days ago' "${STATE_DIR}/orchestrator-loaded-ancient"
    _run_hook "daaf-orchestrator" "sess-new"
    assert_success
    [ ! -e "${STATE_DIR}/orchestrator-loaded-ancient" ]
    [ -f "${STATE_DIR}/orchestrator-loaded-sess-new" ]
}

@test "recent flags (<30d) survive the prune" {
    mkdir -p "$STATE_DIR"
    touch -d '3 days ago' "${STATE_DIR}/orchestrator-loaded-recent"
    _run_hook "daaf-orchestrator" "sess-new2"
    assert_success
    [ -f "${STATE_DIR}/orchestrator-loaded-recent" ]
}

@test "pruning does not touch non-matching files, even when stale" {
    mkdir -p "$STATE_DIR"
    touch -d '60 days ago' "${STATE_DIR}/unrelated-state.txt"
    _run_hook "daaf-orchestrator" "sess-new3"
    assert_success
    [ -f "${STATE_DIR}/unrelated-state.txt" ]
}

@test "pruning is -maxdepth 1: stale flags in subdirectories are untouched" {
    mkdir -p "${STATE_DIR}/nested"
    touch -d '60 days ago' "${STATE_DIR}/nested/orchestrator-loaded-deep"
    _run_hook "daaf-orchestrator" "sess-new4"
    assert_success
    [ -f "${STATE_DIR}/nested/orchestrator-loaded-deep" ]
}

# =========================================================================
# Never-block posture
# =========================================================================

@test "empty stdin: exits 0 and writes nothing" {
    run env HOME="$FAKE_HOME" bash "$FLAG_ORCHESTRATOR_LOADED_SH" < /dev/null
    assert_success
    [ ! -d "$STATE_DIR" ]
}

@test "malformed stdin: exits 0 and writes nothing" {
    run env HOME="$FAKE_HOME" bash "$FLAG_ORCHESTRATOR_LOADED_SH" <<<"not json {{{"
    assert_success
    [ ! -d "$STATE_DIR" ]
}

# With jq off PATH the skill name cannot be parsed, so the hook degrades to a
# no-op and still exits 0. That is the CORRECT posture here (unlike a deny
# guard): a PostToolUse observability hook must never block, and a missed flag
# only costs one redundant reminder.
@test "missing jq: exits 0 as a no-op (never blocks tool execution)" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" HOME="$FAKE_HOME" bash "$FLAG_ORCHESTRATOR_LOADED_SH" \
        < <(printf '%s' '{"session_id":"s","tool_input":{"skill":"daaf-orchestrator"}}')
    [ "$status" -eq 0 ]
}

@test "jq-absence simulation actually removes jq from the hook's PATH" {
    local bindir
    bindir="$(_nojq_bin)"
    run env -i PATH="$bindir" bash -c 'command -v jq'
    assert_failure
}

# =========================================================================
# Registration + the consumer contract
# =========================================================================

@test "registered as a PostToolUse hook under the Skill matcher" {
    run jq -r '
        [.hooks.PostToolUse[]
         | select(.hooks[].command | test("flag-orchestrator-loaded"))
         | .matcher] | join(",")
    ' "${REPO_ROOT}/.claude/settings.json"
    assert_success
    assert_output "Skill"
}

@test "remind-orchestrator.sh reads the same flag path this hook writes" {
    run grep -c "orchestrator-loaded-" "${REPO_ROOT}/.claude/hooks/remind-orchestrator.sh"
    assert_success
    [ "$output" -ge 1 ]
}
