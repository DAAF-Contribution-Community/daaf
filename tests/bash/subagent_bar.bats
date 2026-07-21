#!/usr/bin/env bats
# ============================================================================
# Tests for subagent-bar.sh -- Claude Code subagentStatusLine renderer
# ============================================================================
# Focus: the model-conditional Context Quality Curve threshold tiers that drive
# each row's severity COLOR. Fable/Mythos use ELEVATED 30%/300k, HIGH
# 40%/400k, and CRITICAL 50%/500k. Exact GPT 5.6 Sol rows use ELEVATED
# 40%/300k, HIGH 60%/400k, and CRITICAL 75%/500k. Every other model --
# including opus-4-8[1m] and non-exact Sol variants -- uses ELEVATED 40%/150k,
# HIGH 60%/200k, and CRITICAL 75%/250k.
#
# ASSERTION TARGET: the severity is encoded as an ANSI 256-color code embedded
# in each row's JSON `content`. The codes are unique per severity:
#   NOMINAL  -> 38;5;71   (green)
#   ELEVATED -> 38;5;179  (amber)
#   HIGH     -> 1;38;5;173 (orange, bold)
#   CRITICAL -> 38;5;167  (red)
# In the emitted JSON the ESC byte is escaped as a backslash-u001b sequence,
# so we match on the numeric color substring (e.g. "38;5;71m"), which is unambiguous.
#
# SCRIPT UNDER TEST is parameterized via SUBAGENT_BAR_SH (defaults to the
# installed script) for symmetry with context_reporter.bats.
# ============================================================================

load 'test_helper'

SUBAGENT_BAR_SH="${SUBAGENT_BAR_SH:-${REPO_ROOT}/.claude/scripts/subagent-bar.sh}"

FAKE_SESSION="bats-subbar-session"

# Color substrings (severity discriminators). NOMINAL/HIGH/CRITICAL greens/reds
# are distinct integers; HIGH additionally carries the bold "1;" prefix.
COLOR_NOMINAL="38;5;71m"
COLOR_ELEVATED="38;5;179m"
COLOR_HIGH="1;38;5;173m"
COLOR_CRITICAL="38;5;167m"

# jq -Rsc encodes a real ESC byte as the 6-char text ESC. Trusted colors emit
# ESC[ (CSI); an injected OSC would emit ESC] . Build the encoded OSC
# introducer at runtime (avoids embedding a raw ESC or a \u escape in the source).
OSC_ENC=$(printf '\033]' | jq -Rsc . | tr -d '"')

# /tmp caches this script reads for FAKE_SESSION (cleaned each test). The
# per-subagent model cache uses a task-id suffix; tests that seed it build the
# exact path from their task id.
_clean_subbar_caches() {
    rm -f "/tmp/claude-ctx-window-${FAKE_SESSION}"
    rm -f /tmp/claude-model-"${FAKE_SESSION}"*
    rm -f /tmp/claude-subagent-model-"${FAKE_SESSION}"-*
}

setup() {
    common_setup
    _clean_subbar_caches
    unset CLAUDE_CODE_MAX_CONTEXT_TOKENS
    unset DAAF_PROVIDER_SHIM
    unset SHIM_BACKEND_MODE
    export FAKE_SESSION SUBAGENT_BAR_SH
}

teardown() {
    _clean_subbar_caches
    common_teardown
}

_seed_window() { printf '%s' "$1" > "/tmp/claude-ctx-window-${FAKE_SESSION}"; }
_seed_session_model() { printf '%s' "$1" > "/tmp/claude-model-${FAKE_SESSION}"; }
_seed_task_model() {
    # $1 = task id, $2 = model id
    printf '%s' "$2" > "/tmp/claude-subagent-model-${FAKE_SESSION}-${1}"
}

# Build a payload with a single task. Args: $1 task id, $2 tokenCount.
# session_id/transcript_path are set so window/model caches resolve. The
# transcript_path points into TEST_DIR (its /subagents dir need not exist when
# the per-task model is pre-seeded in the cache).
_payload_one_task() {
    printf '{"session_id":"%s","transcript_path":"%s/main.jsonl","tasks":[{"id":"%s","type":"local_agent","status":"running","tokenCount":%d}]}' \
        "$FAKE_SESSION" "$TEST_DIR" "$1" "$2"
}

_write_subbar_main_model() {
    printf '{"type":"assistant","isSidechain":false,"message":{"model":"%s"}}\n' "$1" > "${TEST_DIR}/main.jsonl"
}

_write_subbar_task_model() {
    local id="$1" model="$2"
    mkdir -p "${TEST_DIR}/${FAKE_SESSION}/subagents"
    printf '{"type":"assistant","isSidechain":true,"message":{"model":"%s"}}\n' \
        "$model" > "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${id}.jsonl"
}

_append_subbar_model() {
    local path="$1" model="$2" sidechain="$3"
    printf '{"type":"assistant","isSidechain":%s,"message":{"model":"%s"}}\n' \
        "$sidechain" "$model" >> "$path"
}

# =========================================================================
# Syntax
# =========================================================================

@test "subagent-bar.sh parses without errors" {
    run bash -n "$SUBAGENT_BAR_SH"
    assert_success
}

# =========================================================================
# Fable family (1M window) -- permissive thresholds
# =========================================================================

@test "fable row: 299k on 1M window renders NOMINAL green" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"   # session differs, forces per-row window mapping
    _seed_task_model "t1" "claude-fable-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 299000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
}

@test "fable row: 300k on 1M window renders ELEVATED amber" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-fable-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
}

@test "fable row: 400k on 1M window renders HIGH orange (bold)" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-fable-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 400000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
}

@test "fable row: 500k on 1M window renders CRITICAL red" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-fable-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 500000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
}

@test "fable row: same-model subagent (fable session + fable task) keeps session 1M window and fable family" {
    # Window-correction BYPASS path: when task_model == session_model,
    # subagent-bar.sh keeps the session window ($max_context) and skips the
    # per-model mapping. Here both are fable and the session window is 1M, so
    # 300k stays 300k/1M = 30% -> fable-family ELEVATED. This proves the bypass
    # branch still resolves the correct family (fable), not just the correct
    # window: a conservative family at 300k/1M would be CRITICAL (>=250k), so
    # ELEVATED confirms the fable family is applied on the bypass path too.
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "claude-fable-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "30%"
}

@test "fable[1m] row: 300k on 1M window renders ELEVATED amber (bracketed fable variant keeps extended-horizon tier)" {
    # The exact string claude-fable-5[1m] must resolve to the fable family. Under a
    # sonnet session the per-row window mapping maps it to 1M; 300k/1M = 30% ->
    # extended-horizon ELEVATED. A conservative family at 300k (>=250k) would be
    # CRITICAL red, so ELEVATED amber confirms the bracketed variant is fable.
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"   # session differs, forces per-row window mapping
    _seed_task_model "t1" "claude-fable-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
}

# =========================================================================
# GPT 5.6 Sol exact tier: 1.05M window, standard percentages + retained absolutes
# =========================================================================

@test "GPT 5.6 Sol row: different-model correction maps 299k to 1050k and NOMINAL" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 299000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "28%"
}

@test "GPT 5.6 Sol row: 300k on 1050k renders ELEVATED amber" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "28%"
}

@test "provider-prefixed GPT 5.6 Sol[1m] row: 400k renders HIGH orange" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "openrouter/openai/gpt-5.6-sol[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 400000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    assert_output --partial "38%"
}

@test "provider-prefixed GPT 5.6 Sol row: 500k renders CRITICAL red" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "openai/gpt-5.6-sol"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 500000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    assert_output --partial "47%"
}

@test "GPT 5.6 Sol row: same-model reuse keeps cached 1050k window and retained absolute gates" {
    _seed_window 1050000
    _seed_session_model "gpt-5.6-sol[1m]"
    _seed_task_model "t1" "gpt-5.6-sol[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "28%"
}

@test "exact Sol ChatGPT row boundaries use 40/60/75% on the final 370k denominator" {
    local boundary tokens expected_severity expected_pct expected_color
    _seed_window 1050000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    for boundary in \
        "147999 NOMINAL 39" \
        "148000 ELEVATED 40" \
        "221999 ELEVATED 59" \
        "222000 HIGH 60" \
        "277499 HIGH 74" \
        "277500 CRITICAL 75"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        case "$expected_severity" in
            NOMINAL) expected_color="$COLOR_NOMINAL" ;;
            ELEVATED) expected_color="$COLOR_ELEVATED" ;;
            HIGH) expected_color="$COLOR_HIGH" ;;
            CRITICAL) expected_color="$COLOR_CRITICAL" ;;
        esac
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" "$tokens")
        assert_success
        assert_output --partial "$expected_color"
        assert_output --partial "${expected_pct}%"
    done
}

@test "provider-prefixed exact Sol[1m] row retains 300k/400k/500k boundaries on 1050k" {
    local boundary tokens expected_severity expected_pct expected_color
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "openrouter/openai/gpt-5.6-sol[1m]"
    for boundary in \
        "299999 NOMINAL 28" \
        "300000 ELEVATED 28" \
        "399999 ELEVATED 38" \
        "400000 HIGH 38" \
        "499999 HIGH 47" \
        "500000 CRITICAL 47"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        case "$expected_severity" in
            NOMINAL) expected_color="$COLOR_NOMINAL" ;;
            ELEVATED) expected_color="$COLOR_ELEVATED" ;;
            HIGH) expected_color="$COLOR_HIGH" ;;
            CRITICAL) expected_color="$COLOR_CRITICAL" ;;
        esac
        run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" "$tokens")
        assert_success
        assert_output --partial "$expected_color"
        assert_output --partial "${expected_pct}%"
    done
}

@test "GPT 5.6 non-Sol and near-miss rows stay conservative" {
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
        _clean_subbar_caches
        _seed_window 200000
        _seed_session_model "claude-sonnet-4-6"
        _seed_task_model "t1" "$model"
        run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
        assert_success
        # Physical windows intentionally vary for mini/chat controls; only the
        # conservative threshold color is invariant across every near miss.
        assert_output --partial "$COLOR_CRITICAL"
    done
}

# =========================================================================
# Conservative tier (non-Fable/Mythos and non-exact-Sol)
# =========================================================================

@test "sonnet row: just under 40% on 200k window renders NOMINAL" {
    _seed_window 200000
    _seed_session_model "claude-fable-5"      # session differs -> per-row mapping to 200k
    _seed_task_model "t1" "claude-sonnet-4-6"
    # 79k / 200k = 39%
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 79000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
}

@test "sonnet row: at 40% on 200k window renders ELEVATED" {
    _seed_window 200000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "claude-sonnet-4-6"
    # 80k / 200k = 40%
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 80000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
}

@test "sonnet row: 45% on its provisioned 200k window renders ELEVATED" {
    # A sonnet task differing from the (fable) session is provisioned a 200k
    # window by the per-row mapping, NOT the 1M session cache. 90k/200k = 45%
    # -> conservative ELEVATED via the percentage leg.
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "claude-sonnet-4-6"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 90000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "45%"
}

# =========================================================================
# opus-4-8[1m]: 1M window but conservative thresholds
# =========================================================================

@test "opus-4-8[1m] row: 150k on 1M window renders ELEVATED (conservative family)" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"   # differs -> per-row mapping applies (opus -> 1M)
    _seed_task_model "t1" "claude-opus-4-8[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 150000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "15%"
}

@test "opus-4-8[1m] row: 220k on 1M window renders HIGH (conservative), not NOMINAL" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-4-8[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 220000)
    assert_success
    # opus-4-8[1m] maps to a 1M window but keeps the conservative family. 220k is
    # in [200k, 250k) -> HIGH. Under a fable family the same 220k would be
    # NOMINAL (< 300k) -- the exact distinction under test.
    assert_output --partial "$COLOR_HIGH"
    refute_output --partial "$COLOR_NOMINAL"
}

# =========================================================================
# GLM-5.2: 1,048,576 physical window, conservative quality thresholds
# =========================================================================

@test "GLM-5.2 row: 150k maps to 1048k window and renders ELEVATED" {
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "z-ai/glm-5.2"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 150000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "14%"
}

@test "date-suffixed GLM-5.2 row: 200k maps to 1048k window and renders HIGH" {
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "z-ai/glm-5.2-20260715"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 200000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    assert_output --partial "19%"
}

@test "GLM-5.2 Air row stays on the generic 200k window" {
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "z-ai/glm-5.2-air"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 90000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "45%"
}

@test "explicit override wins for an exact GLM-5.2 row" {
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "z-ai/glm-5.2"
    run env CLAUDE_CODE_MAX_CONTEXT_TOKENS=333333 bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 140000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "42%"
}

@test "GLM-5.2 row: 250k maps to 1048k window and renders CRITICAL" {
    _seed_window 1000000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "z-ai/glm-5.2"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    assert_output --partial "23%"
}

# =========================================================================
# Unknown model -> conservative family
# =========================================================================

@test "unknown model row: 45% on its provisioned 200k window renders ELEVATED (fail-conservative)" {
    # An unknown model differing from the session maps to the 200k default
    # window (else branch of the window case block) AND the conservative
    # threshold family (else branch of the family case block). 90k/200k = 45%
    # -> ELEVATED.
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "garbage-model-name-000"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 90000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
}

# =========================================================================
# ChatGPT-subscription lane: final gpt-5.4/5.5/5.6 row cap is 370k
# -------------------------------------------------------------------------
# The final min(resolved, 370000) constraint must cover same-model cache reuse,
# different-model mapping, and unsafe explicit overrides. Both exact lane values
# are required; API/OpenRouter routes and non-GPT rows retain ordinary behavior.
# =========================================================================

@test "chatgpt lane: exact Sol at 290k is CRITICAL red on the final 370k row window" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 290000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    assert_output --partial "78%"
    refute_output --partial "27%"
}

@test "API route: exact Sol at 290k remains NOMINAL green on the 1.05M row window" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 290000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "27%"
    refute_output --partial "78%"
}

@test "chatgpt lane: same-model Sol row caps a stale 1.05M session cache" {
    _seed_window 1050000
    _seed_session_model "gpt-5.6-sol[1m]"
    _seed_task_model "t1" "gpt-5.6-sol[1m]"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 290000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    assert_output --partial "78%"
}

@test "SHIM_BACKEND_MODE=chatgpt alone (no DAAF_PROVIDER_SHIM) keeps 1.05M (10%)" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run env SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
    assert_success
    assert_output --partial "10%"
    refute_output --partial "30%"
}

@test "chatgpt lane preserves a lower positive explicit row window" {
    # A 200k override remains lower than the 370k final cap: 100k -> 50%.
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=200000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    assert_output --partial "50%"
    refute_output --partial "27%"
}

@test "chatgpt lane caps an explicit 1.05M row override at 370k" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 290000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    assert_output --partial "78%"
    refute_output --partial "27%"
}

@test "chatgpt lane does not perturb a non-GPT (Claude) row window (fable 1M, 15%)" {
    # The lane gate only rewrites the gpt-5.4/5.5/5.6 arm. A fable task still
    # maps to its 1M window regardless of the lane env: 150k -> 15%.
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-fable-5"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 150000)
    assert_success
    assert_output --partial "15%"
}

# =========================================================================
# Transcript-aware main/subagent model-cache freshness
# =========================================================================

@test "subagent cache refreshes Claude -> Sol -> Terra -> Claude and ignores an intervening synthetic model" {
    local id="switch"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${id}.jsonl"
    local model_cache="/tmp/claude-subagent-model-${FAKE_SESSION}-${id}"
    local signature_cache="${model_cache}.transcript-signature"
    _seed_window 1000000
    _write_subbar_main_model "claude-fable-5"
    _write_subbar_task_model "$id" "claude-sonnet-4-6"

    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 90000)
    assert_success
    assert_output --partial "45%"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"
    run test -s "$signature_cache"
    assert_success

    _append_subbar_model "$transcript" "<synthetic>" true
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 90000)
    assert_success
    assert_output --partial "45%"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"

    _append_subbar_model "$transcript" "gpt-5.6-sol" true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 111000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "30%"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"

    _append_subbar_model "$transcript" "gpt-5.6-terra" true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 111000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "30%"
    run cat "$model_cache"
    assert_output "gpt-5.6-terra"

    _append_subbar_model "$transcript" "claude-sonnet-4-6" true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 90000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "45%"
    refute_output --partial "24%"
    run cat "$model_cache"
    assert_output "claude-sonnet-4-6"
}

@test "main-session cache refreshes against the main transcript signature" {
    local id="main-switch"
    local main_cache="/tmp/claude-model-${FAKE_SESSION}"
    _seed_window 1000000
    _write_subbar_main_model "claude-fable-5"
    _write_subbar_task_model "$id" "claude-fable-5"

    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 100000)
    assert_success
    run cat "$main_cache"
    assert_output "claude-fable-5"

    _append_subbar_model "${TEST_DIR}/main.jsonl" "claude-sonnet-4-6" false
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 100000)
    assert_success
    run cat "$main_cache"
    assert_output "claude-sonnet-4-6"
    run test -s "${main_cache}.transcript-signature"
    assert_success
}

@test "unchanged transcript signature reuses the compatible nonempty subagent bare cache" {
    local id="unchanged"
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${id}.jsonl"
    local model_cache="/tmp/claude-subagent-model-${FAKE_SESSION}-${id}"
    _seed_window 200000
    _write_subbar_main_model "claude-sonnet-4-6"
    _write_subbar_task_model "$id" "claude-sonnet-4-6"
    printf 'gpt-5.6-sol' > "$model_cache"
    stat -c '%s:%y' -- "$transcript" > "${model_cache}.transcript-signature"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 111000)
    assert_success
    assert_output --partial "30%"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"
}

# =========================================================================
# Canonical positive-decimal override contract
# =========================================================================

@test "canonical row overrides 370000 and a lower value are accepted" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
    assert_success
    assert_output --partial "30%"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=250000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    assert_output --partial "40%"
}

@test "invalid decimal row overrides are ignored without arithmetic diagnostics and the exact-lane cap still applies" {
    local value
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    for value in \
        0370000 \
        080000 \
        0 \
        +370000 \
        ' 370000' \
        '370000 ' \
        9223372036854775808 \
        99999999999999999999999999999999999999; do
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_MAX_CONTEXT_TOKENS="$value" \
            bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
        assert_success
        assert_output --partial "30%"
        refute_output --partial "value too great"
        refute_output --partial "syntax error"
    done
}

# =========================================================================
# Anchored terminal-slug GPT physical-family classification
# =========================================================================

@test "supported terminal GPT flagship slugs use the 1.05M different-model mapping" {
    local model
    for model in gpt-5.4 gpt-5.5 gpt-5.6 gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna 'gpt-5.6-sol[1m]' openrouter/openai/gpt-5.6-sol; do
        _clean_subbar_caches
        _seed_window 200000
        _seed_session_model "claude-sonnet-4-6"
        _seed_task_model "t1" "$model"
        run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
        assert_success
        assert_output --partial "10%"
    done
}

@test "anchored GPT 5.2, mini, and chat rows retain their smaller mappings" {
    _seed_window 1000000
    _seed_session_model "claude-fable-5"

    _seed_task_model "t1" "gpt-5.2"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    assert_output --partial "25%"

    _seed_task_model "t2" "openai/gpt-5.6-sol-mini"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t2" 100000)
    assert_success
    assert_output --partial "25%"

    _seed_task_model "t3" "openai/gpt-5.6-sol-chat"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t3" 64000)
    assert_success
    assert_output --partial "50%"
}

@test "malformed left boundaries and gpt-5.60 stay on the generic 200k row window" {
    local model
    for model in vendor/notgpt-5.6-sol xgpt-5.6-sol foo-gpt-5.6-sol gpt-5.60 gpt-5.60-sol; do
        _clean_subbar_caches
        _seed_window 1000000
        _seed_session_model "claude-fable-5"
        _seed_task_model "t1" "$model"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 90000)
        assert_success
        assert_output --partial "45%"
        refute_output --partial "24%"
        refute_output --partial "8%"
    done
}

# =========================================================================
# Fail-open behavior
# =========================================================================

@test "fail-open: empty stdin exits 0" {
    run bash "$SUBAGENT_BAR_SH" < /dev/null
    assert_success
}

@test "fail-open: garbage (non-JSON) stdin exits 0" {
    run bash "$SUBAGENT_BAR_SH" <<< 'this is not json {{{ [[[ %%%'
    assert_success
}

@test "fail-open: empty tasks array exits 0 with no rows" {
    _seed_window 1000000
    run bash "$SUBAGENT_BAR_SH" <<< '{"tasks": []}'
    assert_success
    refute_output --partial '"content"'
}

@test "fail-open: no window cache falls back and still renders a row" {
    # No window cache seeded -> script falls back (latest cache or 200k default).
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-sonnet-4-6"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 10000)
    assert_success
    assert_output --partial '"id":"t1"'
}

# =========================================================================
# HARDENING — Convention 1: terminal-escape-safe rendering (Finding 1)
# -------------------------------------------------------------------------
# Colors are now $'…' (real ESC in trusted constants) and the final render is
# printf '%s' (not '%b'). Untrusted fields are control-stripped: the main-payload
# clean() (all C0+DEL), the agentType sidecar read, and the resolved task_model.
# jq -Rsc encodes trusted color ESC as ESC[…; an INJECTED ESC/OSC would appear
# as ESC] (OSC) or as a raw ESC byte — both must be absent from output.
# =========================================================================

# Single-task payload with a jq-injected description expression.
# $1 = task id, $2 = jq expression producing the description string.
_payload_desc() {
    jq -nc --arg sid "$FAKE_SESSION" --arg tp "${TEST_DIR}/main.jsonl" \
        "{session_id:\$sid,transcript_path:\$tp,tasks:[{id:\"$1\",type:\"local_agent\",status:\"running\",description:($2),tokenCount:80000}]}"
}

@test "C1: injected ESC/BEL in a display field are stripped; printable backslash stays literal; trusted color survives" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-sonnet-4-6"
    local esc bel
    esc=$(printf '\033')
    bel=$(printf '\007')
    # description parses to: A <ESC> ]0;pwn <BEL> B\033C  ("\\033" is a printable
    # backslash sequence, NOT a control byte).
    run bash "$SUBAGENT_BAR_SH" < <(_payload_desc "t1" '"A"+([27]|implode)+"]0;pwn"+([7]|implode)+"B\\033C"')
    assert_success
    # trusted color CSI (ELEVATED amber, 40%) survives, encoded as ESC[38;5;179m
    assert_output --partial "$COLOR_ELEVATED"
    # injected ESC/BEL removed: no encoded OSC introducer, no raw control bytes
    refute_output --partial "$OSC_ENC"
    refute_output --partial "$esc"
    refute_output --partial "$bel"
    # JSON-encoding ALONE would not neutralize a materialized escape; the %b->%s
    # fix keeps the printable backslash literal (encoded as \\033), never an ESC.
    assert_output --partial '\\033'
}

@test "C1: raw control bytes from a hostile model cache are stripped before display" {
    # The bare model cache is read with cat (bypasses jq), so it is the one path
    # that can carry raw C0/DEL bytes into task_model. The bash strip removes them.
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    jq -rn '"g"+([27]|implode)+"]0;X"+([7]|implode)+"-5.6-sol"' \
        > "/tmp/claude-subagent-model-${FAKE_SESSION}-c1"
    local esc bel
    esc=$(printf '\033')
    bel=$(printf '\007')
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "c1" 50000)
    assert_success
    refute_output --partial "$esc"
    refute_output --partial "$bel"
    refute_output --partial "$OSC_ENC"
    # harmless text remainder survives, sans the control bytes
    assert_output --partial 'g]0;X-5.6-sol'
}

# =========================================================================
# HARDENING — Convention 2: identifier allowlist before path construction (Finding 2)
# =========================================================================

@test "C2: path-unsafe and mistyped ids are omitted (no row emitted)" {
    _seed_window 200000
    local idexpr
    # traversal, slash, leading dash, embedded newline, JSON number, JSON object
    for idexpr in '"../evil"' '"a/b"' '"-lead"' '("a"+([10]|implode)+"b")' '123' '{"k":1}'; do
        run bash "$SUBAGENT_BAR_SH" < <(jq -nc --arg sid "$FAKE_SESSION" \
            "{session_id:\$sid,transcript_path:\"x\",tasks:[{id:($idexpr),type:\"local_agent\",status:\"running\",tokenCount:50000}]}")
        assert_success
        refute_output --partial '"content"'
    done
}

@test "C2: id length boundary — 128 chars renders, 129 chars omitted" {
    _seed_window 200000
    local id128 id129
    id128=$(printf 'a%.0s' {1..128})
    id129=$(printf 'a%.0s' {1..129})
    run bash "$SUBAGENT_BAR_SH" < <(jq -nc --arg sid "$FAKE_SESSION" --arg id "$id128" \
        '{session_id:$sid,transcript_path:"x",tasks:[{id:$id,type:"local_agent",status:"running",tokenCount:50000}]}')
    assert_success
    assert_output --partial '"content"'
    run bash "$SUBAGENT_BAR_SH" < <(jq -nc --arg sid "$FAKE_SESSION" --arg id "$id129" \
        '{session_id:$sid,transcript_path:"x",tasks:[{id:$id,type:"local_agent",status:"running",tokenCount:50000}]}')
    assert_success
    refute_output --partial '"content"'
}

@test "C2: unsafe session_id is blanked but rows still render (fail-open, no session path built)" {
    _seed_window 200000
    run bash "$SUBAGENT_BAR_SH" < <(jq -nc \
        '{session_id:"a/b/../etc",transcript_path:"x",tasks:[{id:"t1",type:"local_agent",status:"running",tokenCount:50000}]}')
    assert_success
    assert_output --partial '"id":"t1"'
}

# =========================================================================
# HARDENING — Convention 3: closed-set flagship classifier grammar (Finding 4)
# -------------------------------------------------------------------------
# Existing tests 39-41 cover the accept side + left-boundary/gpt-5.60 rejects.
# This adds the RIGHT-boundary malformed rejects that the old open-ended globs
# (gpt-5.6[-\[]*) wrongly mapped into the 1.05M physical window.
# =========================================================================

@test "C3: malformed flagship-looking slugs do NOT get the 1.05M window" {
    local model
    for model in gpt-5.6-experimental 'gpt-5.6-sol[1m]x' gpt-5.4- gpt-5.4x 'gpt-5.5[1m' gpt-5.60; do
        _clean_subbar_caches
        _seed_window 1000000
        _seed_session_model "claude-fable-5"
        _seed_task_model "t1" "$model"
        run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 90000)
        assert_success
        # The Finding-4 invariant: NONE may map to the 1,050,000 flagship window
        # (90k/1.05M = 8%). They land on a conservative window instead — 200k -> 45%,
        # or the pre-existing generic [1m] arm -> 1M -> 9% for gpt-5.6-sol[1m]x — but
        # never the flagship 8%.
        assert_output --partial '"id":"t1"'
        refute_output --partial "8%"
    done
}

# =========================================================================
# HARDENING — Convention 4: full-transcript usage recovery (Finding 3)
# =========================================================================

@test "C4: usage recovery scans the full transcript — 60 trailing zero placeholders do not hide a positive record" {
    _seed_window 200000
    mkdir -p "${TEST_DIR}/${FAKE_SESSION}/subagents"
    jq -cn '[{isSidechain:true,message:{usage:{input_tokens:123000,cache_read_input_tokens:0,cache_creation_input_tokens:0}}}] + [range(60)|{isSidechain:true,message:{usage:{input_tokens:0,cache_read_input_tokens:0,cache_creation_input_tokens:0}}}] | .[]' \
        > "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-recov.jsonl"
    run bash "$SUBAGENT_BAR_SH" < <(jq -nc --arg sid "$FAKE_SESSION" --arg tp "${TEST_DIR}/main.jsonl" \
        '{session_id:$sid,transcript_path:$tp,tasks:[{id:"recov",type:"local_agent",status:"running",tokenCount:0}]}')
    assert_success
    # full scan recovers 123k -> 61%; tail -n 50 would have seen only zeros -> 0%
    assert_output --partial "61%"
    refute_output --partial " 0%"
}

# =========================================================================
# HARDENING — Convention 5: bounded numerator before x100 (Finding 10)
# =========================================================================

@test "C5: numerator bound — floor(INT64/100) accepted (100%), +1 rejected (0%), no wrap" {
    _seed_window 200000
    _seed_session_model "claude-fable-5"
    _seed_task_model "t1" "claude-sonnet-4-6"
    # 92233720368547758 = floor(INT64_MAX/100): tokens*100 stays int64-valid
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 92233720368547758)
    assert_success
    assert_output --partial "100%"
    assert_output --partial "$COLOR_CRITICAL"
    # +1 would overflow tokens*100 and wrap pct negative -> guarded to 0
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 92233720368547759)
    assert_success
    # guarded to 0 -> NOMINAL green at 0% (NOT a wrapped/overflowed 100% or negative)
    assert_output --partial "$COLOR_NOMINAL"
    refute_output --partial "100%"
    refute_output --partial "syntax error"
}

# =========================================================================
# HARDENING — Convention 6: suppress redirection-open diagnostics (Finding 11)
# =========================================================================

@test "C6: an ENOTDIR cache dir emits no stderr and still renders the row (exit 0)" {
    # A regular file as the cache dir makes every cache path under it ENOTDIR.
    # The grouped write must swallow the open() diagnostic (not leak it to the
    # display stream), while the row still renders from the transcript.
    local notadir="${TEST_DIR}/notadir"
    local payload="${TEST_DIR}/enotdir_payload.json"
    local errfile="${TEST_DIR}/enotdir_err.txt"
    printf 'x' > "$notadir"
    mkdir -p "${TEST_DIR}/${FAKE_SESSION}/subagents"
    printf '{"type":"assistant","isSidechain":true,"message":{"model":"claude-sonnet-4-6"}}\n' \
        > "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-t1.jsonl"
    printf '{"session_id":"%s","transcript_path":"%s/main.jsonl","tasks":[{"id":"t1","type":"local_agent","status":"running","tokenCount":0}]}' \
        "$FAKE_SESSION" "$TEST_DIR" > "$payload"
    run bash -c "DAAF_SUBAGENT_BAR_CACHE_DIR='$notadir' bash '$SUBAGENT_BAR_SH' < '$payload' 2>'$errfile'"
    assert_success
    # errfile must be empty: the ENOTDIR open() diagnostic was suppressed. A bare
    # test command (bats-assert's generic `assert` is not loaded in this harness).
    [ ! -s "$errfile" ]
    assert_output --partial '"id":"t1"'
}
