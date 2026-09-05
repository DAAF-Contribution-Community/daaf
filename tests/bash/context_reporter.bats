#!/usr/bin/env bats
# ============================================================================
# Tests for context-reporter.sh -- context utilization injection hook
# ============================================================================
# Focus: the model-conditional Context Quality Curve threshold tiers in
# calculate(). Fable/Mythos use ELEVATED 30%/300k, HIGH 40%/400k, and
# CRITICAL 50%/500k. The exact extended-horizon GPT ids -- GPT 5.6 Sol and
# GPT-6 Astra -- use ELEVATED 60%/300k, HIGH 75%/400k, and CRITICAL 90%/500k.
# Every other model -- including opus-4-8[1m] and non-exact Sol/Astra variants
# -- uses ELEVATED 40%/150k, HIGH 60%/200k, and CRITICAL 75%/250k.
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

# Fixed fake session id so tests never touch a real session's caches.
FAKE_SESSION="bats-ctxrep-session"
FAKE_AGENT="bats-agent-0001"

# Cache files this hook reads/writes for FAKE_SESSION (cleaned each test). All
# live under the DAAF_CONTEXT_REPORTER_CACHE_DIR test seam (project scratch),
# never real /tmp -- mirroring context_bar.bats' DAAF_CONTEXT_BAR_CACHE_DIR.
_ctx_caches() {
    printf '%s\n' \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-window-${FAKE_SESSION}" \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}" \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}" \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}" \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}.transcript-signature" \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}" \
        "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}.transcript-signature"
}

_clean_ctx_caches() {
    local f
    while read -r f; do
        [ -n "$f" ] && rm -f "$f"
    done < <(_ctx_caches)
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}"/claude-model-"${FAKE_SESSION}".tmp.*
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}"/claude-model-"${FAKE_SESSION}".transcript-signature.tmp.*
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}"/claude-subagent-model-"${FAKE_SESSION}"-*.tmp.*
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}"/claude-subagent-model-"${FAKE_SESSION}"-*.transcript-signature.tmp.*
}

setup() {
    common_setup
    # Deterministic-test seam: point the reporter's cache dir at per-test project
    # scratch so its gate/model/window caches never collide with the live
    # container session's real /tmp/claude-* caches (the source of the prior
    # flakiness). Mirrors context_bar.bats exactly. DAAF_CONTEXT_BAR_CACHE_DIR is
    # aimed at the SAME dir so the statusline writer-to-reporter test rendezvouses
    # in scratch: context-bar writes the ctx-window cache the reporter then reads.
    SCRATCH_DIR="${REPO_ROOT}/scripts/scratch/context-reporter-bats-${BATS_TEST_NUMBER}-$$"
    DAAF_CONTEXT_REPORTER_CACHE_DIR="${SCRATCH_DIR}/cache"
    DAAF_CONTEXT_BAR_CACHE_DIR="${DAAF_CONTEXT_REPORTER_CACHE_DIR}"
    mkdir -p "$DAAF_CONTEXT_REPORTER_CACHE_DIR"
    _clean_ctx_caches
    unset CLAUDE_CODE_MAX_CONTEXT_TOKENS
    unset DAAF_PROVIDER_SHIM
    unset SHIM_BACKEND_MODE
    export FAKE_SESSION FAKE_AGENT CONTEXT_REPORTER_SH CONTEXT_BAR_SH
    export SCRATCH_DIR DAAF_CONTEXT_REPORTER_CACHE_DIR DAAF_CONTEXT_BAR_CACHE_DIR
}

teardown() {
    # rm -rf the whole per-test scratch dir removes every cache file AND the
    # (empty) directory the Convention 6 EISDIR test plants at a gate path, so no
    # cross-test residue survives and nothing is left under the repo for the
    # workspace-invariants check.
    rm -rf "$SCRATCH_DIR"
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

_seed_window() { printf '%s' "$1" > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-window-${FAKE_SESSION}"; }

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

@test "fable[1m]: 300k on 1M window is ELEVATED (bracketed fable variant keeps extended-horizon tier)" {
    # The exact string claude-fable-5[1m] must resolve to the fable family, not
    # conservative. At 300k/1M that is 30% -> extended-horizon ELEVATED; a
    # conservative family would treat 300k (>=250k absolute leg) as CRITICAL, so
    # ELEVATED confirms the bracketed variant is matched as fable.
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5[1m]" 300000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
}

# =========================================================================
# GPT 5.6 Sol exact tier: independent percentages + retained absolutes
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

@test "exact Sol ChatGPT boundaries are the 300k/400k/500k absolute gates on the final 919k denominator" {
    local boundary tokens expected_severity expected_pct
    # On the 919k lane denominator the Sol/Astra percentage legs land at 551.4k
    # (60%), 689.25k (75%) and 827.1k (90%) -- all ABOVE the retained absolute
    # legs, so the absolute gates are the ones that fire. Percentage-gate
    # coverage lives in the non-ChatGPT 400k-denominator test below.
    _seed_window 1050000
    for boundary in \
        "299999 NOMINAL 32" \
        "300000 ELEVATED 32" \
        "399999 ELEVATED 43" \
        "400000 HIGH 43" \
        "499999 HIGH 54" \
        "500000 CRITICAL 54"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
        _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" "$tokens"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "[${expected_severity}]"
        assert_output --partial "/ 919k tokens (${expected_pct}%)"
    done
}

@test "exact Sol profile-wide boundaries use 60/75/90% on a non-ChatGPT 400k denominator" {
    local boundary tokens expected_severity expected_pct
    # A 400k denominator isolates all three percentage gates below the retained
    # 300k/400k/500k absolute gates, so no absolute leg can mask a transition.
    _seed_window 400000
    for boundary in \
        "239999 NOMINAL 59" \
        "240000 ELEVATED 60" \
        "299999 ELEVATED 74" \
        "300000 HIGH 75" \
        "359999 HIGH 89" \
        "360000 CRITICAL 90"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
        _write_main_transcript "${TEST_DIR}/t.jsonl" "openai/gpt-5.6-sol[1m]" "$tokens"
        run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "[${expected_severity}]"
        assert_output --partial "/ 400k tokens (${expected_pct}%)"
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
        rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
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
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
# GPT-6 Astra exact tier: Sol-parity extended horizon (1,050,000 window)
# =========================================================================
# Astra registers with the same quality tier as Sol (60/75/90% + 300k/400k/500k)
# and the same 1,050,000 physical window. The 919k ChatGPT-lane cap applies to
# Astra via GPT_FLAGSHIP_RE and is MEASURED for both lane flagships (2026-09-05).

@test "GPT-6 Astra: 299k on 1050k window is NOMINAL" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-6-astra" 299000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "299k / 1050k"
}

@test "GPT-6 Astra: 300k on 1050k window is ELEVATED" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-6-astra" 300000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1050k"
}

@test "provider-prefixed GPT-6 Astra[1m]: 400k on 1050k window is HIGH" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "openrouter/openai/gpt-6-astra[1m]" 400000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "400k / 1050k"
}

@test "provider-prefixed GPT-6 Astra: 500k on 1050k window is CRITICAL" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "openai/gpt-6-astra" 500000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "500k / 1050k"
}

@test "GPT-6 Astra non-flagship and near-miss variants stay conservative" {
    local model
    for model in \
        gpt-6-astra-pro \
        gpt-6-astra-mini \
        gpt-6-astra-chat \
        xgpt-6-astra \
        foo-gpt-6-astra \
        notgpt-6-astra \
        'vendor/notgpt-6-astra[1m]' \
        'gpt-6-astra[1m]-x' \
        gpt-6-astrab \
        gpt-6 \
        gpt-6-luna \
        'gpt-6-astra[1m'; do
        _clean_ctx_caches
        _seed_window 1050000
        _write_main_transcript "${TEST_DIR}/t.jsonl" "$model" 300000
        run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "[CRITICAL]"
        assert_output --partial "300k / 1050k"
    done
}

@test "mixed: GPT-6 Astra subagent under sonnet session gets 1050k and extended tier" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-6-astra' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-6-astra" 300000

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
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
# Opus 5: 1M physical window (registered 2026-09-05) but CONSERVATIVE
# quality thresholds. Observed on Claude Code 2.1.261 via /model + /context:
# bare `claude-opus-5` reports "42.8k/1m tokens" and `claude-opus-5[1m]`
# reports "48.2k/1m" -- so the BARE id must map to 1,000,000, not fall to the
# 200k arm. The quality-profile glob (*fable-5*|*mythos-5*) is deliberately
# NOT extended: Opus 5 keeps 40/60/75% + 150/200/250k.
#
# NOTE: these four cases FAIL until the user applies
# research/2026-09-05_FrameworkDev_ClaudeCode_Upgrade_2.1.261/context-reporter_opus5.patch
# to .claude/hooks/context-reporter.sh (a user-only surface no agent may edit).
# The twin change in .claude/scripts/subagent-bar.sh is already applied and
# green in tests/bash/subagent_bar.bats.
# =========================================================================

@test "mixed: bare claude-opus-5 subagent maps to 1000k and is ELEVATED at 150k" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-opus-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000  # session window; subagent correction must override to 1M
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "claude-opus-5" 150000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    # 150k / 1000k = 15%; the conservative 150k absolute leg fires -> ELEVATED.
    # Without the *opus-5* arm this reads "150k / 200k" (75%) -> CRITICAL.
    assert_output --partial "150k / 1000k"
    assert_output --partial "[ELEVATED]"
}

@test "mixed: claude-opus-5[1m] subagent maps to 1000k and is ELEVATED at 150k" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-opus-5[1m]' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "claude-opus-5[1m]" 150000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "150k / 1000k"
    assert_output --partial "[ELEVATED]"
}

@test "mixed: claude-opus-5 subagent is HIGH at 220k -- conservative profile, NOT Fable/Mythos" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-opus-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "claude-opus-5" 220000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    # 220k / 1000k = 22%; conservative HIGH leg [200k, 250k). Under the
    # Fable/Mythos profile this same 220k would be NOMINAL (< 300k) -- Opus 5
    # must NOT select that profile despite sharing the 1M physical window.
    assert_output --partial "220k / 1000k"
    assert_output --partial "[HIGH]"
}

@test "mixed: claude-opus-5[1m] subagent is HIGH at 220k -- [1m] does not buy Fable gates" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-opus-5[1m]' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "claude-opus-5[1m]" 220000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "220k / 1000k"
    assert_output --partial "[HIGH]"
}

@test "mixed: claude-fable-5-1 subagent maps to 1000k and keeps the Fable profile" {
    # Locks the substring behaviour of the *fable-5* globs against the real
    # 2.1.261 model id `claude-fable-5-1` as TESTED FACT rather than inference.
    # This case passes with or without the Opus 5 patch.
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-fable-5-1' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "claude-fable-5-1" 250000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    # 250k / 1000k = 25% -> below the Fable 300k/30% ELEVATED leg -> NOMINAL.
    # Under the conservative profile the same 250k would be CRITICAL.
    assert_output --partial "250k / 1000k"
    assert_output --partial "[NOMINAL]"
}

# =========================================================================
# GLM-5.2: 1,048,576 physical window, conservative quality thresholds
# =========================================================================

@test "mixed: exact GLM-5.2 subagent maps to 1048k and is ELEVATED at 150k" {
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2-20260715' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2-air' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'z-ai/glm-5.2' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
# ChatGPT-subscription lane: final gpt-5.4/5.5/5.6 accounting cap is 919k
# -------------------------------------------------------------------------
# The final min(resolved, 919000) constraint must cover the main cache path,
# same-model and different-model subagents, and unsafe explicit overrides. Exact
# lane signals are required. API/OpenRouter behavior and non-GPT models remain
# unchanged. Physical-window accounting stays separate from Sol's quality tier.
# =========================================================================

@test "chatgpt lane: exact Sol main session at 400k is HIGH against final 919k cap" {
    # 400k trips the retained 400k absolute HIGH gate; on the 919k denominator
    # that is only 43%, well below the 75% percentage leg.
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol[1m]" 400000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "400k / 919k"
    assert_output --partial "(43%)"
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

@test "statusline writer-to-reporter path caches 919k and reports Sol 400k HIGH" {
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol[1m]" 400000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_BAR_SH" < <(_payload_statusline "gpt-5.6-sol[1m]" "${TEST_DIR}/t.jsonl" 1050000)
    assert_success
    run cat "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-window-${FAKE_SESSION}"
    assert_success
    assert_output "919000"

    # Ensure no warm rate gate can suppress the reporter half of this path.
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "400k / 919k"
}

@test "chatgpt lane: different-model gpt-5.6-sol subagent maps to 919k (32%)" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 919k"
    refute_output --partial "300k / 1050k"
    assert_output --partial "(32%)"
}

@test "chatgpt lane: same-model exact Sol subagent caps a stale 1.05M session cache" {
    printf 'gpt-5.6-sol[1m]' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'gpt-5.6-sol[1m]' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 1050000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "gpt-5.6-sol[1m]" 400000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "400k / 919k"
    assert_output --partial "(43%)"
}

@test "chatgpt lane: explicit 1.05M cannot raise a different-model Sol subagent above 919k" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 400000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[HIGH]"
    assert_output --partial "400k / 919k"
}

@test "lane vars unset: gpt-5.6-sol subagent keeps the 1.05M API-lane window (28%)" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "300k / 1050k"
    refute_output --partial "300k / 919k"
    assert_output --partial "(28%)"
}

@test "SHIM_BACKEND_MODE=chatgpt alone (no DAAF_PROVIDER_SHIM) keeps 1.05M (28%)" {
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 300000

    run env SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "300k / 1050k"
    refute_output --partial "300k / 919k"
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
    # A 250k override remains below the 919k final ceiling: 200k -> 80%.
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'openai/gpt-5.6-sol' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    _seed_window 200000
    parent="${TEST_DIR}/main.jsonl"
    printf '{"type":"user","isSidechain":false,"message":{"content":"x"}}\n' > "$parent"
    _write_subagent_transcript "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl" "openai/gpt-5.6-sol" 200000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=250000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "200k / 250k"
    refute_output --partial "200k / 919k"
    assert_output --partial "(80%)"
}

@test "chatgpt lane does not perturb a non-GPT (Claude) subagent window (fable 1M, 25%)" {
    # The lane gate only rewrites the gpt-5.4/5.5/5.6 arm. A fable subagent still
    # maps to its 1M window regardless of the lane env: 250k -> 25% -> NOMINAL.
    printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
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
    local model_cache="${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
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

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    _append_model_usage "$transcript" "gpt-5.6-sol" 111000 false
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 919k"
    assert_output --partial "(12%)"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    _append_model_usage "$transcript" "gpt-5.6-terra" 111000 false
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 919k"
    run cat "$model_cache"
    assert_output "gpt-5.6-terra"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    _append_model_usage "$transcript" "claude-sonnet-4-6" 90000 false
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "90k / 1000k"
    refute_output --partial "/ 919k"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"
}

@test "subagent cache ignores synthetic entries, refreshes on later real models, and changes physical/tier decisions" {
    local parent="${TEST_DIR}/main.jsonl"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    local model_cache="${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-subagent-model-${FAKE_SESSION}-${FAKE_AGENT}"
    printf '{"type":"assistant","isSidechain":false,"message":{"model":"claude-sonnet-4-6"}}\n' > "$parent"
    _seed_window 200000
    _write_subagent_transcript "$transcript" "claude-sonnet-4-6" 90000

    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "90k / 200k"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "<synthetic>" 100000 true
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "100k / 200k"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "gpt-5.6-sol" 111000 true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 919k"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "gpt-5.6-terra" 111000 true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "[NOMINAL]"
    assert_output --partial "111k / 919k"
    run cat "$model_cache"
    assert_output "gpt-5.6-terra"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}-${FAKE_AGENT}"
    _append_model_usage "$transcript" "claude-fable-5" 100000 true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "100k / 1000k"
    refute_output --partial "/ 919k"
    run cat "$model_cache"
    assert_output "claude-fable-5"
}

@test "unchanged transcript signature reuses a nonempty compatible bare cache" {
    local transcript="${TEST_DIR}/unchanged.jsonl"
    local model_cache="${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
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
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "90k / 919k"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"
}

# =========================================================================
# Canonical positive-decimal override contract
# =========================================================================

@test "canonical reporter override 919000 and a lower value are accepted" {
    _seed_window 1050000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "gpt-5.6-sol" 111000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=919000 \
        bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "111k / 919k"

    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
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
        0919000 \
        080000 \
        0 \
        +919000 \
        ' 919000' \
        '919000 ' \
        9223372036854775808 \
        99999999999999999999999999999999999999; do
        rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_MAX_CONTEXT_TOKENS="$value" \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
        assert_success
        assert_output --partial "111k / 919k"
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
        assert_output --partial "111k / 919k"
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
        refute_output --partial "/ 919k"
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
    date +%s > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    refute_output --partial "Context utilization"
}

# ############################################################################
# HARDENING CASES (2026-07-20 StatuslineHardening)
# ----------------------------------------------------------------------------
# The cases below exercise the CORRECTED logic in context-reporter.proposed.sh
# (findings 2,3,4,7,8,10,11). They are parameterized on CONTEXT_REPORTER_SH:
# run them against the proposed copy pre-apply, e.g.
#   CONTEXT_REPORTER_SH=/daaf/research/2026-07-20_FrameworkDev_StatuslineHardening/context-reporter.proposed.sh \
#     bats /daaf/tests/bash/context_reporter.bats
# Once the user copies the proposed file over the installed hook from the host,
# they pass with the default (installed) path too.
# ############################################################################

# --- Additional fixture helpers for the hardening cases ---

# Emit a main-session payload with an ARBITRARY (possibly adversarial)
# session_id, passed through %s verbatim so traversal/control bytes survive to
# the hook exactly as an attacker would supply them.
_payload_main_sid() {
    # $1 = raw session_id, $2 = transcript path
    printf '{"hook_event_name":"PreToolUse","session_id":"%s","transcript_path":"%s"}' \
        "$1" "$2"
}

# Emit a subagent payload with a valid session_id but an ARBITRARY agent_id.
_payload_subagent_aid() {
    # $1 = raw agent_id, $2 = transcript path (the parent's)
    printf '{"hook_event_name":"PreToolUse","session_id":"%s","transcript_path":"%s","agent_id":"%s"}' \
        "$FAKE_SESSION" "$2" "$1"
}

# Emit a DIRECT-subagent payload: transcript_path IS the subagent's own
# transcript (basename agent-<agent>.jsonl), the future-Claude-Code shape that
# Convention 10 guards. No parent transcript is available to scan.
_payload_direct_subagent() {
    # $1 = path to the subagent's own transcript (basename = agent-<agent>.jsonl)
    printf '{"hook_event_name":"PreToolUse","session_id":"%s","transcript_path":"%s","agent_id":"%s"}' \
        "$FAKE_SESSION" "$1" "$FAKE_AGENT"
}

# Append N all-zero-token usage entries (streaming/shim placeholders).
_append_zero_usage() {
    # $1 path, $2 model, $3 count, $4 isSidechain JSON boolean
    local path="$1" model="$2" n="$3" side="$4" i
    for ((i=0; i<n; i++)); do
        printf '{"type":"assistant","isSidechain":%s,"message":{"role":"assistant","model":"%s","usage":{"input_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0,"output_tokens":0}}}\n' \
            "$side" "$model" >> "$path"
    done
}

# Write a main transcript whose single usage entry carries an explicit
# input_tokens value (used to drive the numerator-bound boundary).
_write_main_transcript_raw_tokens() {
    # $1 dest, $2 model, $3 input_tokens (raw integer literal)
    local path="$1" model="$2" raw="$3"
    {
        printf '{"type":"user","isSidechain":false,"message":{"role":"user","content":"hi"}}\n'
        printf '{"type":"assistant","isSidechain":false,"message":{"role":"assistant","model":"%s","usage":{"input_tokens":%s,"cache_read_input_tokens":0,"cache_creation_input_tokens":0,"output_tokens":10}}}\n' \
            "$model" "$raw"
    } > "$path"
}

# =========================================================================
# Convention 2 — identifier allowlist before path construction (finding 2)
# =========================================================================

@test "adversarial session_id is rejected before any path build (exit 0, no injection)" {
    local sid
    # A valid fable transcript that WOULD inject (CRITICAL at 500k/1M) if the id
    # were accepted; empty output therefore proves the id gate suppressed it.
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 500000
    _seed_window 1000000
    # Sentinel path lives under the test seam, never real /tmp. The \$ keeps the
    # command substitution LITERAL in the session_id (the point of the test is
    # that the hook must NOT eval it); if that guarantee ever regressed the touch
    # would land in scratch, not pollute /tmp.
    local pwned="${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctxrep-pwned"
    for sid in \
        '../x' \
        'a/b' \
        'a\nb' \
        '-lead' \
        '..' \
        "\$(touch ${pwned})" \
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; do
        run bash "$CONTEXT_REPORTER_SH" < <(_payload_main_sid "$sid" "${TEST_DIR}/t.jsonl")
        assert_success
        refute_output --partial "Context utilization"
    done
    # No command-substitution id could have run, and no traversal path was built.
    run test -e "$pwned"
    assert_failure
}

@test "adversarial agent_id is rejected before the subagent transcript path is built" {
    local aid
    parent="${TEST_DIR}/main.jsonl"
    # A 'busy' parent that must NEVER be injected on the subagent branch.
    _write_main_transcript "$parent" "claude-fable-5" 500000
    _seed_window 1000000
    for aid in \
        '../../etc/x' \
        'a/b' \
        'a\nb' \
        '-lead' \
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'; do
        run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent_aid "$aid" "$parent")
        assert_success
        refute_output --partial "Context utilization"
    done
}

@test "the default session_id and the bats fixture ids still pass the allowlist" {
    # is_safe_id must not regress the legitimate default: no session_id key ->
    # jq default 'default' -> must inject normally.
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 300000
    printf '%s' 1000000 > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-window-default"
    run bash "$CONTEXT_REPORTER_SH" < <(printf '{"hook_event_name":"PreToolUse","transcript_path":"%s"}' "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-window-default" "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-default" \
          "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-default" "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-default.transcript-signature"
}

# =========================================================================
# Convention 4 — full-transcript usage recovery (finding 3)
# =========================================================================

@test "full-scan recovery: >50 trailing zero-token placeholders do not hide real usage" {
    local transcript="${TEST_DIR}/trailing-zeros.jsonl"
    _seed_window 1000000
    _write_main_transcript "$transcript" "claude-fable-5" 300000
    # 60 trailing zero-token placeholders push the positive record out of the
    # old tail-50 window; a full scan must still recover 300k.
    _append_zero_usage "$transcript" "claude-fable-5" 60 false
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "$transcript")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1000k"
}

@test "full-scan recovery works on the subagent branch too" {
    local parent="${TEST_DIR}/main.jsonl"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    _seed_window 1000000
    _write_subagent_transcript "$transcript" "claude-fable-5" 300000
    _append_zero_usage "$transcript" "claude-fable-5" 60 true
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
    assert_success
    assert_output --partial "300k / 1000k"
}

# =========================================================================
# Convention 3 — closed-set flagship classifier grammar (finding 4)
# =========================================================================
# The physical-window classifier must grant the 1,050,000 flagship window ONLY
# to exact closed-set matches. Malformed codenames that the OLD broad glob
# accepted must now fall through to the conservative 200k default (they are
# neither mini/chat nor an exact flagship), and must not trip the 919k cap.

@test "malformed flagship-ish ids map conservatively, not to the 1.05M flagship window" {
    local model
    parent="${TEST_DIR}/main.jsonl"
    transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    printf 'claude-sonnet-4-6' > "$parent"  # parent-model source (any non-gpt is fine)
    for model in \
        'gpt-5.4-' \
        'gpt-5.6-experimental' \
        'gpt-5.6-sol[1m]x' \
        'gpt-5.5[1m'; do
        _clean_ctx_caches
        printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
        _seed_window 200000
        _write_subagent_transcript "$transcript" "$model" 90000
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
        assert_success
        assert_output --partial "90k / 200k"
        refute_output --partial "/ 1050k"
        refute_output --partial "/ 919k"
    done
}

@test "exact closed-set flagships still receive the flagship window / 919k lane cap" {
    local model
    parent="${TEST_DIR}/main.jsonl"
    transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${FAKE_AGENT}.jsonl"
    printf 'claude-sonnet-4-6' > "$parent"
    for model in gpt-5.4 gpt-5.5 gpt-5.6 gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna \
                 'gpt-5.6-sol[1m]' 'gpt-5.6-luna[1m]' openrouter/openai/gpt-5.6-terra; do
        _clean_ctx_caches
        printf 'claude-sonnet-4-6' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
        _seed_window 200000
        _write_subagent_transcript "$transcript" "$model" 111000
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_REPORTER_SH" < <(_payload_subagent "$parent")
        assert_success
        assert_output --partial "111k / 919k"
    done
}

# =========================================================================
# Convention 5 — bounded numerator before x100 (finding 10)
# =========================================================================
# The exact boundary floor(INT64_MAX/100) = 92233720368547758. jq coerces usage
# sums through IEEE-754 doubles, so the input_tokens literals below are chosen as
# multiples of 16 (double-exact near 9.2e16) that jq emits in CANONICAL fixed
# notation bracketing the bound -- exercising the numerator guard itself, not the
# upstream is_canonical/sci-notation reject:
#   input 92233720368547744 -> jq emits 92233720368547740 (<= bound): injects,
#       and 92233720368547740*100 = 9223372036854774000 < INT64_MAX (no overflow),
#       so pct clamps to 100 -- never negative.
#   input 92233720368547760 -> jq emits 92233720368547760 (>  bound): fails open.
#       Pre-guard, 92233720368547760*100 = 9223372036854776000 > INT64_MAX wraps
#       signed-64 negative, which the bound check prevents.

@test "numerator bound: a canonical value <= floor(INT64_MAX/100) injects with a clamped, non-negative pct" {
    _seed_window 1000000
    _write_main_transcript_raw_tokens "${TEST_DIR}/t.jsonl" "claude-fable-5" 92233720368547744
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[CRITICAL]"
    assert_output --partial "(100%)"
    refute_output --partial "(-"
}

@test "numerator bound: a canonical value above floor(INT64_MAX/100) fails open (no injection, no negative pct)" {
    _seed_window 1000000
    _write_main_transcript_raw_tokens "${TEST_DIR}/t.jsonl" "claude-fable-5" 92233720368547760
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    refute_output --partial "Context utilization"
    refute_output --partial "(-"
}

# =========================================================================
# Convention 10 — parent-model isolation on a direct subagent transcript
# (finding 7)
# =========================================================================

@test "direct subagent transcript: session model comes from the parent cache, subagent mapped by its OWN window" {
    # Target scenario from Convention 10: parent ctx cache 1,000,000; legacy
    # parent model Fable; a DIRECT Sonnet subagent transcript; usage 100,000; no
    # subagent-model cache. Must report 100k / 200k (50%) ELEVATED (Sonnet's own
    # conservative window) -- NOT 100k / 1000k (10%), which is the pre-fix bug
    # where SESSION_MODEL was re-parsed from the subagent transcript, made equal
    # to AGENT_MODEL, and skipped the different-model window correction.
    printf 'claude-fable-5' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    _seed_window 1000000
    local transcript="${TEST_DIR}/agent-${FAKE_AGENT}.jsonl"
    _write_subagent_transcript "$transcript" "claude-sonnet-4-6" 100000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_direct_subagent "$transcript")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "100k / 200k"
    assert_output --partial "(50%)"
    refute_output --partial "100k / 1000k"
}

@test "direct subagent transcript with NO parent model cache still maps by the subagent's own window" {
    # No claude-model-<session> cache at all -> SESSION_MODEL empty. The
    # correction must still run (empty != sonnet) and map by the subagent's own
    # model, never assuming same-model as the (unknown) session.
    _seed_window 1000000
    local transcript="${TEST_DIR}/agent-${FAKE_AGENT}.jsonl"
    _write_subagent_transcript "$transcript" "claude-sonnet-4-6" 100000
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_direct_subagent "$transcript")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "100k / 200k"
    assert_output --partial "(50%)"
    refute_output --partial "100k / 1000k"
}

# =========================================================================
# Convention 11 — future/corrupt gate timestamp (finding 8)
# =========================================================================

@test "future gate timestamp is treated as corrupt (reset to 0) and does not suppress the report" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 300000
    # A far-future gate value would make (NOW - LAST_INJECT) negative -> always
    # under the 60s interval -> reports suppressed indefinitely, pre-fix.
    printf '%s' "$(( $(date +%s) + 100000 ))" > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1000k"
}

@test "corrupt (non-numeric) gate timestamp is treated as 0 and does not suppress the report" {
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 300000
    printf '%s' 'not-a-timestamp' > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1000k"
}

@test "a legitimate recent-past gate timestamp still suppresses within the interval" {
    # Regression guard: the Convention 11 reset must not defeat normal rate
    # limiting. A valid value a few seconds in the past stays under 60s.
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 300000
    printf '%s' "$(( $(date +%s) - 5 ))" > "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    refute_output --partial "Context utilization"
}

# =========================================================================
# Convention 6 — suppress redirection-open diagnostics (finding 11)
# =========================================================================

@test "gate write open() failure (gate path is a directory) leaks no diagnostic and still injects" {
    # Force an open() failure by making the gate path (under the test cache seam)
    # an (empty) DIRECTORY: EISDIR on the '>' redirect. Convention 6 wraps the
    # write so the "Is a directory" diagnostic cannot reach the display stream;
    # the injection still emits and the hook exits 0. teardown's rm -rf of the
    # scratch dir removes the planted directory.
    _seed_window 1000000
    _write_main_transcript "${TEST_DIR}/t.jsonl" "claude-fable-5" 300000
    rm -f "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    mkdir -p "${DAAF_CONTEXT_REPORTER_CACHE_DIR}/claude-ctx-ts-${FAKE_SESSION}"
    run bash "$CONTEXT_REPORTER_SH" < <(_payload_main "${TEST_DIR}/t.jsonl")
    assert_success
    assert_output --partial "[ELEVATED]"
    assert_output --partial "300k / 1000k"
    refute_output --partial "Is a directory"
    refute_output --partial "No such file"
    refute_output --partial "Permission denied"
}
