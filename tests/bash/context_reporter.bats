#!/usr/bin/env bats
# ============================================================================
# Tests for context-reporter.sh -- context utilization injection hook
# ============================================================================
# Focus: the model-conditional Context Quality Curve threshold tiers in
# calculate(). Fable/Mythos use ELEVATED 30%/300k, HIGH 40%/400k, and
# CRITICAL 50%/500k. Exact GPT 5.6 Sol ids use ELEVATED 40%/300k, HIGH
# 60%/400k, and CRITICAL 75%/500k. Every other model -- including
# opus-4-8[1m] and non-exact Sol variants -- uses ELEVATED 40%/150k, HIGH
# 60%/200k, and CRITICAL 75%/250k.
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
CONTEXT_REPORTER_SH="${CONTEXT_REPORTER_SH:-${REPO_ROOT}/.claude/hooks/context-reporter.sh}"
CONTEXT_BAR_SH="${CONTEXT_BAR_SH:-${REPO_ROOT}/.claude/scripts/context-bar.sh}"

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
        "/tmp/claude-model-${FAKE_SESSION}.transcript-signature" \
        "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}" \
        "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}.transcript-signature"
}

_clean_ctx_caches() {
    local f
    while read -r f; do
        [ -n "$f" ] && rm -f "$f"
    done < <(_ctx_caches)
    rm -f /tmp/claude-model-"${FAKE_SESSION}".tmp.*
    rm -f /tmp/claude-model-"${FAKE_SESSION}".transcript-signature.tmp.*
    rm -f /tmp/claude-subagent-model-"${FAKE_SESSION}"-*.tmp.*
    rm -f /tmp/claude-subagent-model-"${FAKE_SESSION}"-*.transcript-signature.tmp.*
}

setup() {
    common_setup
    _clean_ctx_caches
    unset CLAUDE_CODE_MAX_CONTEXT_TOKENS
    unset DAAF_PROVIDER_SHIM
    unset SHIM_BACKEND_MODE
    export FAKE_SESSION FAKE_AGENT CONTEXT_REPORTER_SH CONTEXT_BAR_SH
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

_append_model_usage() {
    # Args: path, model id, total tokens, isSidechain JSON boolean.
    local path="$1" model="$2" total="$3" sidechain="$4"
    local a=$((total / 2))
    local b=$((total / 4))
    local c=$((total - a - b))
    printf '{"type":"assistant","isSidechain":%s,"message":{"role":"assistant","model":"%s","usage":{"input_tokens":%d,"cache_read_input_tokens":%d,"cache_creation_input_tokens":%d,"output_tokens":10}}}\n' \
        "$sidechain" "$model" "$a" "$b" "$c" >> "$path"
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

# Emit the production-shaped statusline payload that writes the shared cache.
# Args: $1 model id, $2 transcript path, $3 incoming context window.
_payload_statusline() {
    printf '{"model":{"id":"%s","display_name":"%s"},"cwd":"%s","transcript_path":"%s","session_id":"%s","context_window":{"context_window_size":%s}}' \
        "$1" "$1" "$TEST_DIR" "$2" "$FAKE_SESSION" "$3"
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
# GPT 5.6 Sol exact tier: 1.05M window, standard percentages + retained absolutes
# =========================================================================

@test "GPT 5.6 Sol: 299k on 1050k window is NOMINAL" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" 299000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "299k / 1050k"
}

@test "GPT 5.6 Sol: 300k on 1050k window is ELEVATED" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" 300000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1050k"
}

@test "provider-prefixed GPT 5.6 Sol[1m]: 400k on 1050k window is HIGH" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "openrouter/openai/gpt-5.6-sol[1m]" 400000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "400k / 1050k"
}

@test "provider-prefixed GPT 5.6 Sol: 500k on 1050k window is CRITICAL" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "openai/gpt-5.6-sol" 500000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "500k / 1050k"
}

@test "exact Sol ChatGPT boundaries use 40/60/75% on the final 370k denominator" {
    local boundary tokens expected_severity expected_pct
    _seed_window 1050000
    for boundary in \
        "147999 NOMINAL 39" \
        "148000 ELEVATED 40" \
        "221999 ELEVATED 59" \
        "222000 HIGH 60" \
        "277499 HIGH 74" \
        "277500 CRITICAL 75"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
        _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" "$tokens"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "[${expected_severity}]"
        assert_output --partial "/ 370k tokens (${expected_pct}%)"
    done
}

@test "provider-prefixed exact Sol[1m] retains 300k/400k/500k boundaries on 1050k" {
    local boundary tokens expected_severity expected_pct
    _seed_window 1050000
    for boundary in \
        "299999 NOMINAL 28" \
        "300000 ELEVATED 28" \
        "399999 ELEVATED 38" \
        "400000 HIGH 38" \
        "499999 HIGH 47" \
        "500000 CRITICAL 47"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
        _write_main_transcript "${TEST_DIR}/t.jsonl" \
            "openrouter/openai/gpt-5.6-sol[1m]" "$tokens"
        run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "[${expected_severity}]"
        assert_output --partial "/ 1050k tokens (${expected_pct}%)"
    done
}

@test "GPT 5.6 non-Sol and near-miss variants stay conservative" {
    local model
    for model in \
        gpt-5.6-terra \
        gpt-5.6-luna \
        xgpt-5.6-sol \
        foo-gpt-5.6-sol \
        notgpt-5.6-sol \
        'vendor/notgpt-5.6-sol[1m]' \
        gpt-5.6-sol-pro \
        gpt-5.6-sol-mini \
        gpt-5.6-sol-chat \
        gpt-5.6-sol-20260715 \
        gpt-5.6-sol-future \
        'gpt-5.6-sol[1m]-x'; do
        _clean_ctx_caches
        _seed_window 1050000
        _write_main_transcript "${TEST_DIR}/t.jsonl" "$model" 300000
        run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "[CRITICAL]"
        assert_output --partial "300k / 1050k"
    done
}

@test "mixed: GPT 5.6 Sol subagent under sonnet session gets 1050k and retained absolute gates" {
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1050k"
    assert_output --partial "(28%)"
}

# =========================================================================
# Conservative tier (non-Fable/Mythos and non-exact-Sol)
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
# GLM-5.2: 1,048,576 physical window, conservative quality thresholds
# =========================================================================

@test "mixed: exact GLM-5.2 subagent maps to 1048k and is ELEVATED at 150k" {
    printf 'claude-fable-5' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1000000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "z-ai/glm-5.2" 150000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "150k / 1048k"
    assert_output --partial "(14%)"
}

@test "mixed: date-suffixed GLM-5.2 subagent maps to 1048k and is HIGH at 200k" {
    printf 'claude-fable-5' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2-20260715' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1000000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "z-ai/glm-5.2-20260715" 200000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "200k / 1048k"
    assert_output --partial "(19%)"
}

@test "mixed: GLM-5.2 Air subagent stays on the generic 200k window" {
    printf 'claude-fable-5' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2-air' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1000000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "z-ai/glm-5.2-air" 90000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "90k / 200k"
    assert_output --partial "(45%)"
}

@test "mixed: explicit override wins for an exact GLM-5.2 subagent" {
    printf 'claude-fable-5' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1000000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "z-ai/glm-5.2" 140000

    run env CLAUDE_CODE_MAX_CONTEXT_TOKENS=333333 bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "140k / 333k"
    assert_output --partial "(42%)"
}

@test "mixed: exact GLM-5.2 subagent maps to 1048k and is CRITICAL at 250k" {
    printf 'claude-fable-5' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1000000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "z-ai/glm-5.2" 250000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "250k / 1048k"
    assert_output --partial "(23%)"
}

# =========================================================================
# ChatGPT-subscription lane: final gpt-5.4/5.5/5.6 accounting cap is 370k
# -------------------------------------------------------------------------
# The final min(resolved, 370000) constraint must cover the main cache path,
# same-model and different-model subagents, and unsafe explicit overrides. Exact
# lane signals are required. API/OpenRouter behavior and non-GPT models remain
# unchanged. Physical-window accounting stays separate from Sol's quality tier.
# =========================================================================

@test "chatgpt lane: exact Sol main session at 290k is CRITICAL against final 370k cap" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol[1m]" 290000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "290k / 370k"
    assert_output --partial "(78%)"
}

@test "API route: exact Sol main session at 290k remains NOMINAL on 1.05M" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol[1m]" 290000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "290k / 1050k"
    assert_output --partial "(27%)"
}

@test "statusline writer-to-reporter path caches 370k and reports Sol 290k CRITICAL" {
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol[1m]" 290000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_BAR_SH" < <(_payload_statusline "gpt-5.6-sol[1m]" "${TEST_DIR}/t.jsonl" 1050000)
    assert_success
    run cat "/tmp/claude-ctx-window-${FAKE_SESSION}"
    assert_success
    assert_output "370000"

    # Ensure no warm rate gate can suppress the reporter half of this path.
    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "290k / 370k"
}

@test "chatgpt lane: different-model gpt-5.6-sol subagent maps to 370k (81%)" {
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "300k / 370k"
    refute_output --partial "300k / 1050k"
    assert_output --partial "(81%)"
}

@test "chatgpt lane: same-model exact Sol subagent caps a stale 1.05M session cache" {
    printf 'gpt-5.6-sol[1m]' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'gpt-5.6-sol[1m]' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1050000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "gpt-5.6-sol[1m]" 290000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "290k / 370k"
    assert_output --partial "(78%)"
}

@test "chatgpt lane: explicit 1.05M cannot raise a different-model Sol subagent above 370k" {
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 290000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "290k / 370k"
}

@test "lane vars unset: gpt-5.6-sol subagent keeps the 1.05M API-lane window (28%)" {
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "300k / 1050k"
    refute_output --partial "300k / 370k"
    assert_output --partial "(28%)"
}

@test "SHIM_BACKEND_MODE=chatgpt alone (no DAAF_PROVIDER_SHIM) keeps 1.05M (28%)" {
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run env SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "300k / 1050k"
    refute_output --partial "300k / 370k"
}

@test "malformed lane signal values do not activate the reporter cap" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol[1m]" 290000

    run env DAAF_PROVIDER_SHIM=OpenAI SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "290k / 1050k"
}

@test "chatgpt lane preserves a lower positive explicit context window" {
    # A 250k override remains below the 370k final ceiling: 200k -> 80%.
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 200000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=250000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "200k / 250k"
    refute_output --partial "200k / 370k"
    assert_output --partial "(80%)"
}

@test "chatgpt lane does not perturb a non-GPT (Claude) subagent window (fable 1M, 25%)" {
    # The lane gate only rewrites the gpt-5.4/5.5/5.6 arm. A fable subagent still
    # maps to its 1M window regardless of the lane env: 250k -> 25% -> NOMINAL.
    printf 'claude-sonnet-4-6' > "/tmp/claude-model-${FAKE_SESSION}"
    printf 'claude-fable-5' > "/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "claude-fable-5" 250000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "250k / 1000k"
    assert_output --partial "(25%)"
}

# =========================================================================
# Transcript-aware main/subagent model-cache freshness
# =========================================================================

@test "main cache refreshes Claude -> Sol -> Terra -> Claude before cap and tier selection" {
    local transcript="${TEST_DIR}/main-switch.jsonl"
    local model_cache="/tmp/claude-model-${FAKE_SESSION}"
    local signature_cache="${model_cache}.transcript-signature"
    _seed_window 1000000
    _write_main_transcript "$transcript" "claude-fable-5" 100000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "100k / 1000k"
    run cat "$model_cache"
    assert_output "claude-fable-5"
    run test -s "$signature_cache"
    assert_success

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
    _append_model_usage "$transcript" "gpt-5.6-sol" 111000 false
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 370k"
    assert_output --partial "(30%)"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
    _append_model_usage "$transcript" "gpt-5.6-terra" 111000 false
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 370k"
    run cat "$model_cache"
    assert_output "gpt-5.6-terra"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
    _append_model_usage "$transcript" "claude-sonnet-4-6" 90000 false
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "90k / 1000k"
    refute_output --partial "/ 370k"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"
}

@test "subagent cache ignores synthetic entries, refreshes on later real models, and changes physical/tier decisions" {
    local parent="${TEST_DIR}/main.jsonl"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    local model_cache="/tmp/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    printf '{"type":"assistant","isSidechain":false,"message":{"model":"claude-sonnet-4-6"}}\n' > "$parent"
    _seed_window 200000
    _write_subagent_transcript "$transcript" "claude-sonnet-4-6" 90000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "90k / 200k"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "<synthetic>" 100000 true
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "100k / 200k"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "gpt-5.6-sol" 111000 true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 370k"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "gpt-5.6-terra" 111000 true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 370k"
    run cat "$model_cache"
    assert_output "gpt-5.6-terra"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "claude-fable-5" 100000 true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "100k / 1000k"
    refute_output --partial "/ 370k"
    run cat "$model_cache"
    assert_output "claude-fable-5"
}

@test "unchanged transcript signature reuses a nonempty compatible bare cache" {
    local transcript="${TEST_DIR}/unchanged.jsonl"
    local model_cache="/tmp/claude-model-${FAKE_SESSION}"
    _seed_window 1050000
    _write_main_transcript "$transcript" "claude-sonnet-4-6" 90000

    # First invocation establishes the sidecar from the script's own signature
    # implementation. Replacing only the compatibility cache then makes reuse
    # observable: an unchanged transcript must not be rescanned back to Sonnet.
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    run test -s "${model_cache}.transcript-signature"
    assert_success
    printf 'gpt-5.6-sol' > "$model_cache"
    cached_signature=$(cat "${model_cache}.transcript-signature")
    current_signature=$(stat -c '%s:%y' -- "$transcript")
    [[ "$cached_signature" == "$current_signature" ]]
    cached_model=$(cat "$model_cache")
    [[ "$cached_model" == "gpt-5.6-sol" ]]
    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "90k / 370k"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"
}

# =========================================================================
# Canonical positive-decimal override contract
# =========================================================================

@test "canonical reporter override 370000 and a lower value are accepted" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" 111000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "111k / 370k"

    rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=250000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "111k / 250k"
}

@test "invalid decimal overrides are ignored without arithmetic diagnostics and the reporter cap still applies" {
    local value
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" 111000
    for value in \
        0370000 \
        080000 \
        0 \
        +370000 \
        ' 370000' \
        '370000 ' \
        9223372036854775808 \
        99999999999999999999999999999999999999; do
        rm -f "/tmp/claude-ctx-ts-${FAKE_SESSION}"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_MAX_CONTEXT_TOKENS="$value" \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "111k / 370k"
        refute_output --partial "value too great"
        refute_output --partial "syntax error"
    done
}

# =========================================================================
# Anchored terminal-slug GPT physical-family classification
# =========================================================================

@test "reporter accepts supported terminal GPT flagship slugs for subagent physical mapping and final cap" {
    local model
    local parent="${TEST_DIR}/main.jsonl"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    printf '{"type":"assistant","message":{"model":"claude-sonnet-4-6"}}\n' > "$parent"
    _seed_window 200000
    for model in gpt-5.4 gpt-5.5 gpt-5.6 gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna 'gpt-5.6-sol[1m]' openrouter/openai/gpt-5.6-sol; do
        _clean_ctx_caches
        _seed_window 200000
        _write_subagent_transcript "$transcript" "$model" 111000
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
        assert_success
        assert_output --partial "111k / 370k"
    done
}

@test "reporter preserves anchored GPT 5.2, mini, and chat subagent mappings" {
    local parent="${TEST_DIR}/main.jsonl"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    printf '{"type":"assistant","message":{"model":"claude-fable-5"}}\n' > "$parent"

    _seed_window 1000000
    _write_subagent_transcript "$transcript" "gpt-5.2" 100000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "100k / 400k"

    _clean_ctx_caches
    _seed_window 1000000
    _write_subagent_transcript "$transcript" "openai/gpt-5.6-sol-mini" 100000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "100k / 400k"

    _clean_ctx_caches
    _seed_window 1000000
    _write_subagent_transcript "$transcript" "openai/gpt-5.6-sol-chat" 64000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "64k / 128k"
}

@test "reporter rejects malformed left boundaries and gpt-5.60 from flagship mapping and cap" {
    local model
    local parent="${TEST_DIR}/main.jsonl"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    printf '{"type":"assistant","message":{"model":"claude-sonnet-4-6"}}\n' > "$parent"
    for model in vendor/notgpt-5.6-sol xgpt-5.6-sol foo-gpt-5.6-sol gpt-5.60 gpt-5.60-sol; do
        _clean_ctx_caches
        _seed_window 200000
        _write_subagent_transcript "$transcript" "$model" 90000
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
        assert_success
        assert_output --partial "90k / 200k"
        refute_output --partial "/ 370k"
        refute_output --partial "/ 1050k"
    done
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
