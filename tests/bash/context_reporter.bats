#!/usr/bin/env bats
# ============================================================================
# Tests for context-reporter.sh -- context utilization injection hook
# ============================================================================
# Focus: the model-family-conditional Context Quality Curve thresholds in
# calculate(). Fable/Mythos get the permissive family (ELEVATED 30%/300k, HIGH
# 40%/400k, CRITICAL 50%/500k); every other model -- including opus-4-8[1m],
# whose 1M window does NOT relax its Opus-class quality horizon -- gets the
# conservative family (ELEVATED 40%/150k, HIGH 60%/200k, CRITICAL 75%/250k).
#
# Also covers the main/subagent measurement split (a subagent is measured with
# ITS OWN model's family, not the session's) and fail-open behavior.
#
# SCRIPT UNDER TEST is parameterized: CONTEXT_REPORTER_SH defaults to the
# installed hook but can be pointed at a proposed copy for pre-deployment
# testing, e.g.:
#   CONTEXT_REPORTER_SH=/path/to/proposed_context-reporter.sh bats context_reporter.bats
# ============================================================================

load 'test_helper'

# Path to the script under test (override to test a proposed copy).
CONTEXT_REPORTER_SH="${CONTEXT_REPORTER_SH:-/daaf/.claude/hooks/context-reporter.sh}"

# Fixed fake session id so tests never touch a real session's /tmp caches.
FAKE_SESSION="bats-ctxrep-session"
FAKE_AGENT="bats-agent-0001"

# /tmp cache files this hook reads/writes for FAKE_SESSION (cleaned each test).
_ctx_caches() {
    printf '%s\n' \
        "/tmp/claude-ctx-window-${FAKE_SESSION}" \
        "/tmp/claude-model-${FAKE_SESSION}" \
        "/tmp/claude-ctx-ts-${FAKE_SESSION}" \
        "/tmp/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}" \
        "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
}

_clean_ctx_caches() {
    local f
    while read -r f; do
        [ -n "$f" ] && rm -f "$f"
    done < <(_ctx_caches)
}

setup() {
    common_setup
    _clean_ctx_caches
    export FAKE_SESSION FAKE_AGENT CONTEXT_REPORTER_SH
}

teardown() {
    _clean_ctx_caches
    common_teardown
}

# --- Fixture helpers ---

# Write a main-chain transcript with one assistant usage entry summing to a
# target token count. Args: $1 dest path, $2 model id, $3 total tokens.
# The three usage fields are split so their sum equals $3.
_write_main_transcript() {
    local path="$1" model="$2" total="$3"
    local a=$((total / 2))
    local b=$((total / 4))
    local c=$((total - a - b))
    {
        printf '{"type":"user","isSidechain":false,"message":{"role":"user","content":"hi"}}\n'
        printf '{"type":"assistant","isSidechain":false,"message":{"role":"assistant","model":"%s","usage":{"input_tokens":%d,"cache_read_input_tokens":%d,"cache_creation_input_tokens":%d,"output_tokens":10}}}\n' \
            "$model" "$a" "$b" "$c"
    } > "$path"
}

# Write a subagent transcript (all isSidechain:true). Same arg contract.
_write_subagent_transcript() {
    local path="$1" model="$2" total="$3"
    local a=$((total / 2))
    local b=$((total / 4))
    local c=$((total - a - b))
    mkdir -p "$(dirname "$path")"
    {
        printf '{"type":"user","isSidechain":true,"message":{"role":"user","content":"hi"}}\n'
        printf '{"type":"assistant","isSidechain":true,"message":{"role":"assistant","model":"%s","usage":{"input_tokens":%d,"cache_read_input_tokens":%d,"cache_creation_input_tokens":%d,"output_tokens":10}}}\n' \
            "$model" "$a" "$b" "$c"
    } > "$path"
}

# Emit a PreToolUse payload (main session) referencing a transcript path.
_payload_main() {
    printf '{"hook_event_name":"PreToolUse","session_id":"%s","transcript_path":"%s"}' \
        "$FAKE_SESSION" "$1"
}

# Emit a PreToolUse payload with an agent_id (subagent-fired). The
# transcript_path is the PARENT's; the hook derives the subagent transcript at
# dirname(parent)/<session>/subagents/agent-<agent>.jsonl.
_payload_subagent() {
    printf '{"hook_event_name":"PreToolUse","session_id":"%s","transcript_path":"%s","agent_id":"%s"}' \
        "$FAKE_SESSION" "$1" "$FAKE_AGENT"
}

_seed_window() { printf '%s' "$1" > "/tmp/claude-ctx-window-${FAKE_SESSION}"; }

# =========================================================================
# Syntax
# =========================================================================

@test "context-reporter.sh parses without errors" {
    run bash -n "$CONTEXT_REPORTER_SH"
    assert_success
}

# =========================================================================
# Fable family (1M window) -- permissive thresholds 30/40/50% & 300/400/500k
# =========================================================================

@test "fable: 299k on 1M window is NOMINAL (just under 300k and 30%)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 299000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[NOMINAL]"
}

@test "fable: 300k on 1M window is ELEVATED (absolute 300k leg fires at 30%)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 300000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
}

@test "fable: 400k on 1M window is HIGH" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 400000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[HIGH]"
}

@test "fable: 500k on 1M window is CRITICAL" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 500000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[CRITICAL]"
}

@test "mythos: 300k on 1M window is ELEVATED (mythos shares fable family)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-mythos-5" 300000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
}

# =========================================================================
# Conservative family (non-Fable) -- 40/60/75% & 150/200/250k
# =========================================================================

@test "sonnet: just under 40% on 200k window is NOMINAL" {
    _seed_window 200000
    # 79k / 200k = 39% (under 40%, and well under 150k)
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-sonnet-4-6" 79000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[NOMINAL]"
}

@test "sonnet: at 40% on 200k window is ELEVATED (percentage leg)" {
    _seed_window 200000
    # 80k / 200k = 40%
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-sonnet-4-6" 80000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
}

@test "conservative absolute leg: 150k on a 1M window is ELEVATED at only 15%" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-sonnet-4-6" 150000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "(15%)"
}

# =========================================================================
# opus-4-8[1m]: 1M WINDOW but CONSERVATIVE thresholds (the load-bearing case)
# =========================================================================

@test "opus-4-8[1m]: 150k on 1M window is ELEVATED (1M window, conservative family)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-opus-4-8[1m]" 150000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    # Conservative absolute leg fires at 150k even though only 15% of the 1M window.
    assert_output --partial "[ELEVATED]"
    assert_output --partial "150k / 1000k"
    assert_output --partial "(15%)"
}

@test "opus-4-8[1m]: 220k on 1M window is HIGH, NOT nominal (would be nominal under fable family)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-opus-4-8[1m]" 220000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    # 220k lands in [200k, 250k): conservative HIGH leg, below the CRITICAL leg.
    # Under the fable family this same count would be NOMINAL (< 300k), which is
    # exactly the distinction under test.
    assert_output --partial "[HIGH]"
}

# Off-by-one boundary pair for the CONSERVATIVE family's absolute legs on a 1M
# window (symmetric with the fable 299k/300k pair above). 149k sits one k below
# the 150k ELEVATED leg; 200k sits exactly on the HIGH leg. Both use the 1M
# window so the percentage legs stay far below their thresholds (149k=14%,
# 200k=20%), isolating the ABSOLUTE-leg boundary as the sole decision driver.
@test "conservative absolute leg boundary: 149k on 1M window is NOMINAL (one k under 150k)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-opus-4-8[1m]" 149000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    # 149k < 150k ELEVATED leg and 14% < 40% -> NOMINAL. (150k would be ELEVATED.)
    assert_output --partial "[NOMINAL]"
    assert_output --partial "(14%)"
}

@test "conservative absolute leg boundary: 200k on 1M window is HIGH (exactly on the 200k leg)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-opus-4-8[1m]" 200000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    # 200k == 200k HIGH leg (>= is inclusive) and 20% < 60% -> HIGH, not ELEVATED.
    assert_output --partial "[HIGH]"
    assert_output --partial "(20%)"
}

# =========================================================================
# Unknown / garbage model -> conservative family (fail-conservative)
# =========================================================================

@test "unknown model: 150k on 1M window is ELEVATED (conservative default)" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "totally-made-up-model-xyz" 150000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
}

# =========================================================================
# Mixed: Fable SESSION with a Sonnet SUBAGENT -> subagent uses conservative
# =========================================================================

@test "mixed: sonnet subagent under a fable session is measured conservatively" {
    # Session model is fable; subagent model is sonnet. The subagent is measured
    # against a 200k window (its own model) with the conservative family.
    printf 'claude-fable-5' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'claude-sonnet-4-6' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1000000  # session window is 1M; subagent correction overrides to 200k

    # Parent transcript path -> subagent transcript derived alongside it.
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    subdir="${TEST_DIR}/${FAKE_SESSION}/subagents"
    _write_subagent_transcript "${subdir}/agent-${FAKE_AGENT}.jsonl" "claude-sonnet-4-6" 150000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    # 150k against the subagent's 200k window = 75% -> conservative CRITICAL.
    # (Under a fable family this would be only ELEVATED; the point is the
    # subagent's OWN sonnet family governs, not the fable session's.)
    assert_output --partial "[CRITICAL]"
    assert_output --partial "150k / 200k"
}

@test "mixed inverse: fable subagent under a sonnet session uses permissive family" {
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'claude-fable-5' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000  # session window; subagent correction overrides to 1M

    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    subdir="${TEST_DIR}/${FAKE_SESSION}/subagents"
    _write_subagent_transcript "${subdir}/agent-${FAKE_AGENT}.jsonl" "claude-fable-5" 250000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    # 250k against the fable subagent's 1M window = 25%, under the 300k/30%
    # permissive ELEVATED leg -> NOMINAL. Under the conservative family the same
    # 250k would be CRITICAL, so this proves the fable family is applied.
    assert_output --partial "[NOMINAL]"
    assert_output --partial "250k / 1000k"
}

# =========================================================================
# Fail-open: missing caches / transcript -> exit 0, emit nothing
# =========================================================================

@test "fail-open: missing transcript exits 0 with no injection" {
    _seed_window 1000000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/does-not-exist.jsonl")
    assert_success
    refute_output --partial "Context utilization"
}

@test "fail-open: missing subagent transcript exits 0 (no fallback to parent)" {
    _seed_window 1000000
    parent="${TEST_DIR}/main.jsonl"
    _write_main_transcript "$parent" "claude-fable-5" 500000  # parent is 'busy'
    # No subagent transcript created -> hook must emit nothing, not the parent's.
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    refute_output --partial "Context utilization"
}

@test "fail-open: empty stdin exits 0" {
    run bash "$CONTEXT_REPORTER_SH" < /dev/null
    assert_success
}

# Pins the malformed-payload contract (empty transcript_path -> silent no-op).
# The pre-guard code also passed this via incidental downstream nets (the -f
# guard in calculate() and the empty-MSG exit); the explicit main-branch guard
# makes the contract survive refactoring, and this test makes its loss loud.
@test "fail-open: empty transcript_path on main-session payload exits 0 with no injection" {
    _seed_window 1000000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "")
    assert_success
    refute_output --partial "Context utilization"
}

# =========================================================================
# Rate-limit gate: a warm gate file suppresses injection
# =========================================================================

@test "rate gate: injection suppressed when gate fired within the interval" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 500000
    # Seed the gate with 'now' so the 60s interval has not elapsed.
    date +%s > "/tmp/claude-ctx-ts-${FAKE_SESSION}"
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    refute_output --partial "Context utilization"
}
