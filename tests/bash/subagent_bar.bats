#!/usr/bin/env bats
# ============================================================================
# Tests for subagent-bar.sh -- Claude Code subagentStatusLine renderer
# ============================================================================
# Focus: the model-conditional Context Quality Curve threshold tiers that drive
# each row's severity COLOR. Fable/Mythos use ELEVATED 30%/300k, HIGH
# 40%/400k, and CRITICAL 50%/500k. The exact extended-horizon GPT rows -- GPT
# 5.6 Sol and GPT-6 Astra, plus (2026-09-29 user policy decision) GPT-6 Sol and
# the flagship -pro form of all three -- use ELEVATED 60%/300k, HIGH 75%/400k,
# and CRITICAL 90%/500k. Every other model -- including opus-4-8[1m] and
# non-exact Sol/Astra variants -- uses ELEVATED 40%/150k, HIGH 60%/200k, and
# CRITICAL 75%/250k. Provider-dotted Claude ids (anthropic/claude-opus-5.5) are
# classified through normalize_model_id (2026-09-29 block at the end).
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
# GPT 5.6 Sol exact tier: independent percentages + retained absolutes
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

@test "exact Sol ChatGPT row boundaries are the 300k/400k/500k absolute gates on the final 919k denominator" {
    local boundary tokens expected_severity expected_pct expected_color
    # On the 919k lane denominator the Sol/Astra percentage legs land at 551.4k
    # (60%), 689.25k (75%) and 827.1k (90%) -- all ABOVE the retained absolute
    # legs, so the absolute gates are the ones that fire. Percentage-gate
    # coverage lives in the non-ChatGPT 400k-denominator test below.
    _seed_window 1050000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    for boundary in \
        "299999 NOMINAL 32" \
        "300000 ELEVATED 32" \
        "399999 ELEVATED 43" \
        "400000 HIGH 43" \
        "499999 HIGH 54" \
        "500000 CRITICAL 54"; do
        read -r tokens expected_severity expected_pct <<< "$boundary"
        case "$expected_severity" in
            NOMINAL) expected_color="$COLOR_NOMINAL" ;;
            ELEVATED) expected_color="$COLOR_ELEVATED" ;;
            HIGH) expected_color="$COLOR_HIGH" ;;
            CRITICAL) expected_color="$COLOR_CRITICAL" ;;
        esac
        _append_subbar_usage t1 "$tokens"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" "$tokens")
        assert_success
        assert_output --partial "$expected_color"
        assert_output --partial "${expected_pct}%"
    done
}

@test "exact Sol profile-wide row boundaries use 60/75/90% on a non-ChatGPT 400k denominator" {
    local boundary tokens expected_severity expected_pct expected_color
    # A 400k denominator isolates all three percentage gates below the retained
    # 300k/400k/500k absolute gates, so no absolute leg can mask a transition.
    _seed_window 400000
    _seed_session_model "gpt-5.6-sol[1m]"
    _seed_task_model "t1" "gpt-5.6-sol[1m]"
    for boundary in \
        "239999 NOMINAL 59" \
        "240000 ELEVATED 60" \
        "299999 ELEVATED 74" \
        "300000 HIGH 75" \
        "359999 HIGH 89" \
        "360000 CRITICAL 90"; do
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
    # 2026-09-29 policy flip: gpt-5.6-sol-pro used to be a near miss here; the
    # user policy decision of 2026-09-29 (flagship -pro reads as its base) now
    # admits it ON PURPOSE, so the genuine right-boundary near miss is
    # gpt-5.6-sol-pro-x. The -pro positive cases live in the 2026-09-29 block.
    for model in \
        gpt-5.6-terra \
        gpt-5.6-luna \
        xgpt-5.6-sol \
        foo-gpt-5.6-sol \
        notgpt-5.6-sol \
        'vendor/notgpt-5.6-sol[1m]' \
        gpt-5.6-sol-pro-x \
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
# GPT-6 Astra exact tier: Sol-parity extended horizon (1,050,000 window)
# =========================================================================

@test "GPT-6 Astra row: different-model correction maps 299k to 1050k and NOMINAL" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-6-astra"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 299000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "28%"
}

@test "GPT-6 Astra row: 300k on 1050k renders ELEVATED amber" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-6-astra"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "28%"
}

@test "provider-prefixed GPT-6 Astra[1m] row: 400k renders HIGH orange" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "openrouter/openai/gpt-6-astra[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 400000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    assert_output --partial "38%"
}

@test "provider-prefixed GPT-6 Astra row: 500k renders CRITICAL red" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "openai/gpt-6-astra"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 500000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    assert_output --partial "47%"
}

@test "GPT-6 Astra row: same-model reuse keeps cached 1050k window and extended tier" {
    _seed_window 1050000
    _seed_session_model "gpt-6-astra[1m]"
    _seed_task_model "t1" "gpt-6-astra[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 300000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "28%"
}

@test "GPT-6 Astra non-flagship and near-miss rows stay conservative" {
    local model
    # 2026-09-29 policy flip: gpt-6-astra-pro is now admitted ON PURPOSE (user
    # policy decision: flagship -pro reads as its base), so the right-boundary
    # near miss is gpt-6-astra-pro-x. gpt-6-luna stays here: since 2026-09-29 it
    # maps to the 1.05M window, but its quality tier is conservative (like
    # gpt-5.6-luna), so 300k still renders CRITICAL.
    for model in \
        gpt-6-astra-pro-x \
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
# Opus 5: 1M physical window (registered 2026-09-05) but conservative
# quality thresholds. Observed on Claude Code 2.1.261 via /model + /context:
# bare `claude-opus-5` reports "42.8k/1m tokens" and `claude-opus-5[1m]`
# reports "48.2k/1m" -- so the BARE id must map to 1,000,000 as well, which
# the *opus-5* arm of the physical-window glob provides. The quality-profile
# glob is deliberately NOT extended to *opus-5* (its only Opus entry is the
# anchored claude-opus-5-5 slug, added 2026-09-23), so Opus 5 keeps the
# 40/60/75% + 150/200/250k conservative gates.
# =========================================================================

@test "opus-5 (bare) row: 150k maps to a 1M window (15%) and renders ELEVATED" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"   # differs -> per-row mapping applies
    _seed_task_model "t1" "claude-opus-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 150000)
    assert_success
    # 15% proves the 1M denominator: on a 200k window 150k would read 75%.
    assert_output --partial "15%"
    refute_output --partial "75%"
    assert_output --partial "$COLOR_ELEVATED"
}

@test "opus-5[1m] row: 150k maps to a 1M window (15%) and renders ELEVATED" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 150000)
    assert_success
    assert_output --partial "15%"
    assert_output --partial "$COLOR_ELEVATED"
}

@test "opus-5 row: 220k on 1M window renders HIGH (conservative profile), not NOMINAL" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 220000)
    assert_success
    # Opus 5 must NOT select the Fable/Mythos profile: 220k is in [200k, 250k)
    # -> conservative HIGH. Under the Fable/Mythos gates the same 220k would be
    # NOMINAL (< 300k) -- the exact distinction under test.
    assert_output --partial "$COLOR_HIGH"
    refute_output --partial "$COLOR_NOMINAL"
}

@test "opus-5[1m] row: 220k renders HIGH -- the [1m] suffix does not buy Fable gates" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 220000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    refute_output --partial "$COLOR_NOMINAL"
}

@test "fable-5-1 row: 150k maps to a 1M window (15%) and renders NOMINAL" {
    # Locks the substring behaviour of the *fable-5* globs against the real
    # 2.1.261 model id `claude-fable-5-1` as TESTED FACT rather than inference:
    # 1M physical window AND the Fable/Mythos quality profile (150k < 300k and
    # 15% < 30% -> NOMINAL, where the conservative profile would be ELEVATED).
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"   # differs -> per-row mapping applies
    _seed_task_model "t1" "claude-fable-5-1"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 150000)
    assert_success
    assert_output --partial "15%"
    assert_output --partial "$COLOR_NOMINAL"
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
# ChatGPT-subscription lane: final gpt-5.4/5.5/5.6 row cap is 919k
# -------------------------------------------------------------------------
# The final min(resolved, 919000) constraint must cover same-model cache reuse,
# different-model mapping, and unsafe explicit overrides. Both exact lane values
# are required; API/OpenRouter routes and non-GPT rows retain ordinary behavior.
# =========================================================================

@test "chatgpt lane: exact Sol at 400k is HIGH orange on the final 919k row window" {
    # 400k trips the retained 400k absolute HIGH gate; 400k/919k = 43%, while
    # the uncapped 1.05M window would render 38%.
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    _append_subbar_usage t1 400000
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 400000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    assert_output --partial "43%"
    refute_output --partial "38%"
}

@test "API route: exact Sol at 290k remains NOMINAL green on the 1.05M row window" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    _append_subbar_usage t1 290000
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 290000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "27%"
    refute_output --partial "31%"
}

@test "chatgpt lane: same-model Sol row caps a stale 1.05M session cache" {
    _seed_window 1050000
    _seed_session_model "gpt-5.6-sol[1m]"
    _seed_task_model "t1" "gpt-5.6-sol[1m]"
    _append_subbar_usage t1 400000
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 400000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    assert_output --partial "43%"
}

@test "SHIM_BACKEND_MODE=chatgpt alone (no DAAF_PROVIDER_SHIM) keeps 1.05M (10%)" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    run env SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
    assert_success
    assert_output --partial "10%"
    refute_output --partial "12%"
}

@test "chatgpt lane preserves a lower positive explicit row window" {
    # A 200k override remains lower than the 919k final cap: 100k -> 50%.
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    _append_subbar_usage t1 100000
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=200000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    assert_output --partial "50%"
    refute_output --partial "10%"
}

@test "chatgpt lane caps an explicit 1.05M row override at 919k" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    _append_subbar_usage t1 400000
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 400000)
    assert_success
    assert_output --partial "$COLOR_HIGH"
    assert_output --partial "43%"
    refute_output --partial "38%"
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

    _append_subbar_usage "$id" 111000
    _append_subbar_model "$transcript" "gpt-5.6-sol" true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 111000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "12%"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"

    _append_subbar_model "$transcript" "gpt-5.6-terra" true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 111000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "12%"
    run cat "$model_cache"
    assert_output "gpt-5.6-terra"

    _append_subbar_model "$transcript" "claude-sonnet-4-6" true
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 90000)
    assert_success
    assert_output --partial "$COLOR_ELEVATED"
    assert_output --partial "45%"
    refute_output --partial "9%"
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
    _append_subbar_usage "$id" 111000
    stat -c '%s:%y' -- "$transcript" > "${model_cache}.transcript-signature"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" 111000)
    assert_success
    assert_output --partial "12%"
    run cat "$model_cache"
    assert_output "gpt-5.6-sol"
}

# =========================================================================
# Canonical positive-decimal override contract
# =========================================================================

@test "canonical row overrides 919000 and a lower value are accepted" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "gpt-5.6-sol"
    _append_subbar_usage t1 111000

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=919000 \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
    assert_success
    assert_output --partial "12%"

    _append_subbar_usage t1 100000
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
    _append_subbar_usage t1 111000
    for value in \
        0919000 \
        080000 \
        0 \
        +919000 \
        ' 919000' \
        '919000 ' \
        9223372036854775808 \
        99999999999999999999999999999999999999; do
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_MAX_CONTEXT_TOKENS="$value" \
            bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 111000)
        assert_success
        assert_output --partial "12%"
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
        refute_output --partial "9%"
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
    # No window cache seeded -> script maps the window by the session model
    # (sonnet -> 200k), never another session's cache. 10000/200000 = 5%.
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-sonnet-4-6"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 10000)
    assert_success
    assert_output --partial '"id":"t1"'
    assert_output --partial "m5%"
}

# =========================================================================
# Denominator resolution without a session window cache (2026-09-05)
# -------------------------------------------------------------------------
# Formerly the bar inherited the most recent window cache from ANY session,
# else 200k, so same-model rows in an uncached GPT-6 Astra / Opus 5 session
# rendered against 200k and went red far too early. Now: this session's cache
# when present, else the static map for the session model.
#
# These tests use the DAAF_SUBAGENT_BAR_CACHE_DIR seam (an empty per-test dir)
# rather than the shared /tmp used above, so the live container's own
# /tmp/claude-ctx-window-* caches cannot leak into the "no cache" condition
# and mask a regression to the any-session fallback.
# =========================================================================

_iso_cache() { # isolated cache dir for this test; echoes its path
    local d="${TEST_DIR}/isocache"
    mkdir -p "$d"
    printf '%s' "$d"
}
_iso_seed_session_model() { printf '%s' "$1" > "$(_iso_cache)/claude-model-${FAKE_SESSION}"; }
_iso_seed_task_model() { printf '%s' "$2" > "$(_iso_cache)/claude-subagent-model-${FAKE_SESSION}-${1}"; }
_iso_seed_window() { printf '%s' "$1" > "$(_iso_cache)/claude-ctx-window-${FAKE_SESSION}"; }

@test "no window cache: same-model gpt-6-astra row maps by model to 1.05M, not 200k" {
    _iso_seed_session_model "gpt-6-astra"
    _iso_seed_task_model "t1" "gpt-6-astra"
    run env DAAF_SUBAGENT_BAR_CACHE_DIR="$(_iso_cache)" bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 210000)
    assert_success
    # 210000 / 1050000 = 20% (against 200k: 100%; against an inherited 1M: 21%).
    assert_output --partial "210k"
    assert_output --partial "m20%"
    assert_output --partial "$COLOR_NOMINAL"
}

@test "no window cache: same-model gpt-6-astra row on the ChatGPT lane is capped at 919k" {
    export DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
    _iso_seed_session_model "gpt-6-astra"
    _iso_seed_task_model "t1" "gpt-6-astra"
    _append_subbar_usage t1 459500
    run env DAAF_SUBAGENT_BAR_CACHE_DIR="$(_iso_cache)" bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 459500)
    assert_success
    # 459500 / 919000 = 50% (against 200k: 100%).
    assert_output --partial "m50%"
}

@test "no window cache: same-model claude-opus-5 row maps to 1M, not 200k" {
    _iso_seed_session_model "claude-opus-5"
    _iso_seed_task_model "t1" "claude-opus-5"
    run env DAAF_SUBAGENT_BAR_CACHE_DIR="$(_iso_cache)" bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    # 100000 / 1000000 = 10% (against 200k it would read 50%).
    assert_output --partial "m10%"
}

@test "no window cache: an UNRELATED session's window cache is never inherited" {
    # Plant a 200000 cache for a different session id in the isolated cache dir;
    # a gpt-6-astra same-model row must still map by model (1.05M -> 20%).
    printf '200000' > "$(_iso_cache)/claude-ctx-window-some-other-session"
    _iso_seed_session_model "gpt-6-astra"
    _iso_seed_task_model "t1" "gpt-6-astra"
    run env DAAF_SUBAGENT_BAR_CACHE_DIR="$(_iso_cache)" bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 210000)
    assert_success
    assert_output --partial "m20%"
}

@test "session window cache, when present, stays authoritative for same-model rows" {
    _iso_seed_window 200000
    _iso_seed_session_model "claude-opus-5"
    _iso_seed_task_model "t1" "claude-opus-5"
    run env DAAF_SUBAGENT_BAR_CACHE_DIR="$(_iso_cache)" bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    # Cache (200000) wins over the static map (1M): 100000/200000 = 50%.
    assert_output --partial "m50%"
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
        # (90k/1.05M = 8%). Since the 2026-09-29 review fix they all land on the
        # conservative 200k window (45%) — including gpt-5.6-sol[1m]x, which the
        # flagship-family pre-filter now keeps off the generic Claude [1m] arm
        # (formerly 1M -> 9%), matching context-reporter.sh and context-bar.sh.
        assert_output --partial '"id":"t1"'
        refute_output --partial "8%"
        assert_output --partial "m45%"
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

# =========================================================================
# HARDENING follow-up — Convention 1: UTF-8-encoded C1 via the model cache
# -------------------------------------------------------------------------
# The bare model cache is read with cat, so it can carry a VALID-UTF-8 C1
# control (U+009B = 8-bit CSI on xterm-class terminals) that the old byte-wise
# bash range strip (C0+DEL only) passed through into the row and the emitted
# JSON. The Unicode-aware jq [[:cntrl:]] strip (Unicode Cc) removes it.
# =========================================================================

@test "C1: UTF-8-encoded C1 from a hostile model cache is stripped before display" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    # [155]|implode -> U+009B, emitted by jq -rn as raw UTF-8 bytes c2 9b.
    jq -rn '"evil"+([155]|implode)+"0;pwn-model"' \
        > "/tmp/claude-subagent-model-${FAKE_SESSION}-c1u"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "c1u" 50000)
    assert_success
    # Neither the raw UTF-8 C1 bytes nor a JSON-escaped  may survive.
    refute_output --partial "$(printf '\302\233')"
    refute_output --partial 'u009b'
    # Harmless text remainder joins, sans the control.
    assert_output --partial 'evil0;pwn-model'
}

# =========================================================================
# Late-usage shim streams (chatgpt/openai): measured child input, never progress output
# =========================================================================

_measured_child() {
    local model="$1" usage="${2:-70000}"
    mkdir -p "${TEST_DIR}/${FAKE_SESSION}/subagents"
    jq -nc --arg model "$model" --argjson usage "$usage" \
        '{type:"assistant",message:{model:$model,usage:{input_tokens:$usage}}}' \
        > "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-measured.jsonl"
}

# Add measured usage explicitly for legacy window/threshold fixtures without
# changing their model identity. Call before recording a signature-cache marker.
_append_subbar_usage() {
    local id="$1" tokens="$2"
    mkdir -p "${TEST_DIR}/${FAKE_SESSION}/subagents"
    jq -nc --argjson tokens "$tokens" \
        '{type:"assistant",isSidechain:true,message:{usage:{input_tokens:$tokens}}}' \
        >> "${TEST_DIR}/${FAKE_SESSION}/subagents/agent-${id}.jsonl"
}

_measured_payload() {
    local tokens="${1:-24}" model="${2:-gpt-6-astra}" type="${3-local_agent}"
    jq -nc --arg sid "$FAKE_SESSION" --arg tp "${TEST_DIR}/main.jsonl" \
        --arg model "$model" --arg type "$type" --argjson tokens "$tokens" \
        '{session_id:$sid,transcript_path:$tp,tasks:[{id:"measured",type:$type,
          status:"running",model:$model,tokenCount:$tokens}]}'
}

@test "measured input: both modes replace small positive progress 24 and 364 with child 70k not parent 150k" {
    export DAAF_PROVIDER_SHIM=openai
    printf '%s\n' '{"message":{"model":"gpt-6-astra","usage":{"input_tokens":150000}}}' > "${TEST_DIR}/main.jsonl"
    _measured_child gpt-6-astra
    local mode tokens pct
    for mode in chatgpt openai; do
        case "$mode" in chatgpt) pct=7 ;; openai) pct=6 ;; esac
        for tokens in 0 24 364 99000; do
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload "$tokens")
            assert_success
            assert_output --partial '70k'
            assert_output --partial "m${pct}%"
            refute_output --partial '150k'
        done
    done
}

@test "measured input: both modes and all approved terminal spellings keep their own denominators" {
    export DAAF_PROVIDER_SHIM=openai
    local mode base variant prefix suffix model pct flagship_pct
    for mode in chatgpt openai; do
        case "$mode" in chatgpt) flagship_pct=7 ;; openai) flagship_pct=6 ;; esac
        for base in gpt-5.6 gpt-5.6-sol gpt-5.6-terra gpt-5.6-luna gpt-6-astra; do
            for variant in '' -mini -chat; do
                [[ "$base" == gpt-6-astra && -n "$variant" ]] && continue
                case "$variant" in -mini) pct=17 ;; -chat) pct=54 ;; *) pct="$flagship_pct" ;; esac
                for prefix in '' openrouter/openai/; do
                    for suffix in '' '[1m]'; do
                        model="${prefix}${base}${variant}${suffix}"
                        _measured_child "$model"
                        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
                        assert_success
                        assert_output --partial '70k'
                        assert_output --partial "m${pct}%"
                    done
                done
            done
        done
    done
}

@test "measured input: both modes respect explicit overrides and only chatgpt caps flagship windows" {
    export DAAF_PROVIDER_SHIM=openai
    local mode override pct
    _measured_child gpt-6-astra
    for mode in chatgpt openai; do
        for override in 200000 919000 1050000; do
            case "$override" in
                200000) pct=35 ;;
                919000) pct=7 ;;
                1050000)
                    case "$mode" in chatgpt) pct=7 ;; openai) pct=6 ;; esac ;;
            esac
            run env SHIM_BACKEND_MODE="$mode" CLAUDE_CODE_MAX_CONTEXT_TOKENS="$override" \
                bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial '70k'
            assert_output --partial "m${pct}%"
            assert_output --partial "$COLOR_NOMINAL"
        done
    done
}

@test "measured input: both modes sum cache partitions and latest lower measurement wins" {
    export DAAF_PROVIDER_SHIM=openai
    local mode pct transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-measured.jsonl"
    for mode in chatgpt openai; do
        _measured_child gpt-5.6-sol 150000
        printf '%s\n' '{"message":{"model":"gpt-5.6-sol","usage":{"input_tokens":11000,"cache_read_input_tokens":58000,"cache_creation_input_tokens":1000,"output_tokens":999999}}}' >> "$transcript"
        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 99000)
        assert_success
        assert_output --partial '70k'
        printf '%s\n' '{"message":{"model":"gpt-5.6-sol","usage":{"input_tokens":40000}}}' >> "$transcript"
        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 99000)
        assert_success
        assert_output --partial '40k'
        case "$mode" in chatgpt) pct=4 ;; openai) pct=3 ;; esac
        assert_output --partial "m${pct}%"
    done
}

@test "measured input: malformed trailing lines fields errors and zero placeholders are ignored" {
    export DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
    _measured_child gpt-6-astra
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-measured.jsonl" value
    for value in '"90000"' true -5 0.5 9007199254740992 '{}' '[]'; do
        printf '{"message":{"usage":{"input_tokens":%s}}}\n' "$value" >> "$transcript"
    done
    printf '%s\n' '{"isApiErrorMessage":true,"message":{"model":"claude-sonnet-4-6","usage":{"input_tokens":90000}}}' \
        '{"message":{"usage":{"input_tokens":0}}}' 'not-json' '[]' >> "$transcript"
    printf '{"message":' >> "$transcript"
    run bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
    assert_success
    assert_output --partial '70k'
    assert_output --partial 'm7%'
}

@test "measured input: both modes startup pending from payload or cache has no percent or estimate" {
    export DAAF_PROVIDER_SHIM=openai
    local mode
    for mode in chatgpt openai; do
        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 364)
        assert_success
        assert_output --partial 'context pending'
        refute_output --partial '%'
        refute_output --partial '364'
    done
    _seed_task_model measured gpt-5.6-luna
    _measured_child '<synthetic>' 0
    for mode in chatgpt openai; do
        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 24 claude-sonnet-4-6)
        assert_success
        assert_output --partial 'context pending'
        refute_output --partial '%'
        refute_output --partial 'm24'
    done
}

@test "measured input: both modes prefer child transcript and cache over conflicting payload models" {
    export DAAF_PROVIDER_SHIM=openai
    local mode
    for mode in chatgpt openai; do
        _seed_task_model measured claude-sonnet-4-6
        _measured_child gpt-6-astra
        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 24 claude-sonnet-4-6)
        assert_success
        assert_output --partial '70k'
        _measured_child claude-sonnet-4-6
        run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 24 gpt-6-astra)
        assert_success
        refute_output --partial '70k'
        assert_output --partial 'm24'
    done
}

@test "measured input: unrelated models routes and task types retain positive native progress in both modes" {
    local mode model route type
    export DAAF_PROVIDER_SHIM=openai
    for mode in chatgpt openai; do
        for model in claude-sonnet-4-6 gpt-5.5 gpt-5.6-experimental gpt-6-astra-mini xgpt-5.6-sol 'gpt-5.6-sol[1m]-x'; do
            _measured_child "$model"
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial 'm24'
            refute_output --partial '70k'
        done
        _measured_child gpt-6-astra
        for route in openrouter OpenAI ''; do
            run env SHIM_BACKEND_MODE="$mode" DAAF_PROVIDER_SHIM="$route" \
                bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial 'm24'
        done
        for type in local_bash remote_agent local_workflow ''; do
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload 24 gpt-6-astra "$type")
            assert_success
            assert_output --partial 'm24'
        done
    done
    for route in unknown ChatGPT OpenAI 'openai ' ''; do
        run env SHIM_BACKEND_MODE="$route" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
        assert_success
        assert_output --partial 'm24'
        refute_output --partial '70k'
    done
}

@test "measured input: malformed payload models cannot create startup identity or terminal escapes" {
    export DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
    local model point
    local -a invalid_models=(null true 123 '{}' '[]' '""' '"gpt-6-astra "' '"gpt-6-astra[1m]-x"')
    # Generate control-bearing JSON without embedding raw controls in this file.
    for point in 0 10 13 27 31 127 133 155; do
        invalid_models+=("$(jq -nc --argjson point "$point" '"gpt-5.6-sol" + ([$point] | implode)')")
    done
    for model in "${invalid_models[@]}"; do
        run bash "$SUBAGENT_BAR_SH" < <(_measured_payload | jq --argjson model "$model" '.tasks[0].model=$model')
        assert_success
        assert_output --partial 'm24'
        refute_output --partial 'context pending'
        refute_output --partial "$OSC_ENC"
    done
}

@test "measured input: invalid partitions and unsafe sums are pending until valid input arrives" {
    export DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-measured.jsonl" field value
    for field in input_tokens cache_read_input_tokens cache_creation_input_tokens; do
        for value in '"90000"' true -1 0.5 '{}' '[]' 9007199254740992; do
            _measured_child gpt-6-astra 0
            jq -nc --arg field "$field" --argjson value "$value" \
                '{message:{usage:({input_tokens:1000}+{($field):$value})}}' >> "$transcript"
            run bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial 'context pending'
            refute_output --partial '%'
        done
    done
    _measured_child gpt-6-astra 0
    printf '%s\n' '{"message":{"usage":{"input_tokens":9007199254740991,"cache_read_input_tokens":1}}}' >> "$transcript"
    run bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
    assert_success
    assert_output --partial 'context pending'
    _append_subbar_usage measured 9007199254740991
    run bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
    assert_success
    assert_output --partial 'm100%'
    refute_output --partial 'context pending'
}

@test "measured input: unreadable child is pending from cache and emits no read diagnostic" {
    export DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
    _seed_task_model measured gpt-6-astra
    _measured_child gpt-6-astra
    local transcript="${TEST_DIR}/${FAKE_SESSION}/subagents/agent-measured.jsonl"
    chmod 000 "$transcript"
    [ ! -r "$transcript" ]
    run bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
    chmod 600 "$transcript"
    assert_success
    assert_output --partial 'context pending'
    refute_output --partial 'Permission denied'
    refute_output --partial '%'
}

@test "measured input: legacy generic zero fallback still reads unrelated child input" {
    export DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
    _measured_child claude-sonnet-4-6
    run bash "$SUBAGENT_BAR_SH" < <(_measured_payload 0 gpt-6-astra)
    assert_success
    assert_output --partial '70k'
    assert_output --partial 'm35%'
    run env SHIM_BACKEND_MODE=unknown bash "$SUBAGENT_BAR_SH" < <(_measured_payload 24)
    assert_success
    assert_output --partial 'm24'
}

# =========================================================================
# Opus 5.5 (claude-opus-5-5, added Claude Code 2.1.280): 1M physical window
# AND -- uniquely among Opus models -- the EXTENDED-HORIZON quality profile
# (30/40/50% + 300/400/500k), by USER POLICY DECISION of 2026-09-23 (not by
# validation)
# (research/2026-09-23_FrameworkDev_ClaudeCode_Upgrade_2.1.280/SESSION_NOTES.md
# § Key Decisions #3). The profile arm matches claude-opus-5-5 EXACTLY (bare or
# as a provider path's final segment), NEVER *opus-5* and never a loose
# *opus-5-5* substring: bare
# Opus 5 must keep the conservative gates, which the last two cases lock, and
# near misses are locked by the boundary-anchoring block appended below.
# Lockstep twin of the Opus 5.5 block in tests/bash/context_reporter.bats
# (whose profile cases needed the user-applied
# research/2026-09-23_FrameworkDev_ClaudeCode_Upgrade_2.1.280/context-reporter_opus55.patch,
# now deployed; this suite's script under test is agent-editable and carried
# both glob changes from the start, so every case here was green throughout).
# =========================================================================

@test "opus-5-5 (bare) row: 100k maps to a 1M window (10%), not 200k" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"   # differs -> per-row mapping applies
    _seed_task_model "t1" "claude-opus-5-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    # 10% proves the 1M denominator: on a 200k window 100k would read 50%.
    assert_output --partial "10%"
    refute_output --partial "50%"
}

@test "opus-5-5[1m] row: 100k maps to a 1M window (10%), not 200k" {
    _seed_window 200000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 100000)
    assert_success
    assert_output --partial "10%"
    refute_output --partial "50%"
}

@test "opus-5-5 row: 250k on 1M window renders NOMINAL -- extended-horizon profile" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    # 250k / 1M = 25%: below the extended-horizon 300k/30% ELEVATED leg.
    # Under the conservative profile the same 250k would be CRITICAL (>= 250k).
    assert_output --partial "$COLOR_NOMINAL"
    refute_output --partial "$COLOR_CRITICAL"
}

@test "opus-5-5[1m] row: 250k renders NOMINAL -- extended-horizon profile" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    refute_output --partial "$COLOR_CRITICAL"
}

@test "opus-5 (bare) row: 250k STILL renders CRITICAL -- *opus-5-5* must not widen to *opus-5*" {
    # LOCK. If the profile glob were ever written *opus-5* instead of
    # *opus-5-5*, bare Opus 5 would silently inherit the extended-horizon gates
    # and this 250k reading would flip from CRITICAL to NOMINAL.
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    refute_output --partial "$COLOR_NOMINAL"
}

@test "opus-5[1m] row: 250k STILL renders CRITICAL -- lock against glob widening" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    refute_output --partial "$COLOR_NOMINAL"
}

# =========================================================================
# Opus 5.5 profile arm: BOUNDARY-ANCHORING locks (added 2026-09-23, fix cycle 1).
# The profile arm grants a privilege (relaxed 30/40/50% + 300/400/500k gates),
# so it names claude-opus-5-5 exactly -- bare, or as the FINAL segment of a
# provider path -- rather than substring-matching *opus-5-5*. These four cases
# are the regression lock for that choice: two right-/left-boundary near misses
# that must stay CONSERVATIVE, and two provider-path forms that must be
# recognized. If the arm is ever reverted to a loose *opus-5-5* glob, the first
# two flip from CRITICAL to NOMINAL and fail. Lockstep twin of the same block in
# tests/bash/context_reporter.bats.
# =========================================================================

@test "opus-5-5-mini row: 250k renders CRITICAL -- right-boundary near miss stays conservative" {
    # 250k >= the conservative 250k CRITICAL absolute leg. Under a loose
    # *opus-5-5* glob this hypothetical mini variant would read NOMINAL.
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "claude-opus-5-5-mini"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    refute_output --partial "$COLOR_NOMINAL"
}

@test "xclaude-opus-5-5 row: 250k renders CRITICAL -- left-boundary near miss stays conservative" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "xclaude-opus-5-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    refute_output --partial "$COLOR_NOMINAL"
}

@test "anthropic/claude-opus-5-5 row: 250k renders NOMINAL -- provider path is recognized" {
    # The */claude-opus-5-5 alternative: anchoring must not break the provider-
    # prefixed form agents actually see on non-first-party routes.
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "anthropic/claude-opus-5-5"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    refute_output --partial "$COLOR_CRITICAL"
}

@test "anthropic/claude-opus-5-5[1m] row: 250k renders NOMINAL -- provider path plus [1m]" {
    _seed_window 1000000
    _seed_session_model "claude-sonnet-4-6"
    _seed_task_model "t1" "anthropic/claude-opus-5-5[1m]"
    run bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "t1" 250000)
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    refute_output --partial "$COLOR_CRITICAL"
}

# =========================================================================
# 2026-09-29: provider-dotted Claude ids (normalize_model_id) and the GPT
# registry extension (gpt-6-sol, gpt-6-luna, flagship -pro).
# -------------------------------------------------------------------------
# (A) BUG FIX. OpenRouter reports Claude models with a DOTTED version
# (anthropic/claude-opus-5.5, claude-opus-4.8, claude-opus-5.5[1m]); every
# Claude pattern expects the hyphenated form. normalize_model_id rewrites ONLY
# an id ending in claude-<family>-<major>.<minor>[optional [1m]] and is applied
# at classification points only -- the row label and the model caches keep the
# RAW name. Reproduced before the fix: dotted Opus 5.5 at 250k read CRITICAL
# (not NOMINAL); dotted Opus 4.8 at 150k read 75% of 200k (not 15% of 1M).
# (B) USER POLICY DECISION 2026-09-29, not validation: flagship -pro reads as
# its non-pro base; gpt-6-sol reads as gpt-5.6-sol (1.05M window + extended
# tier); gpt-6-luna reads as gpt-5.6-luna (1.05M window, conservative tier);
# gpt-6-terra, bare gpt-6, and GPT-6 mini/chat stay unregistered.
# Provenance: research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames.
#
# These cases use the DAAF_SUBAGENT_BAR_CACHE_DIR seam (_iso_* helpers above)
# so no fixture touches the shared /tmp caches.
# =========================================================================

# Run one row against the isolated cache. Args: $1 task id, $2 tokenCount,
# then optional VAR=value environment assignments.
_iso_row() {
    local id="$1" tokens="$2"
    shift 2
    env DAAF_SUBAGENT_BAR_CACHE_DIR="$(_iso_cache)" "$@" \
        bash "$SUBAGENT_BAR_SH" < <(_payload_one_task "$id" "$tokens")
}

# Fresh sonnet-session fixture whose row model differs from the session.
# Args: $1 task model, $2 session window (default 200000).
_iso_sonnet_row_fixture() {
    rm -rf "${TEST_DIR}/isocache" "${TEST_DIR}/${FAKE_SESSION}"
    _iso_seed_session_model "claude-sonnet-4-6"
    _iso_seed_window "${2:-200000}"
    _iso_seed_task_model "t1" "$1"
}

_color_for() {
    case "$1" in
        NOMINAL) printf '%s' "$COLOR_NOMINAL" ;;
        ELEVATED) printf '%s' "$COLOR_ELEVATED" ;;
        HIGH) printf '%s' "$COLOR_HIGH" ;;
        CRITICAL) printf '%s' "$COLOR_CRITICAL" ;;
    esac
}

@test "normalize_model_id: start/end markers each appear exactly once" {
    run grep -c '^# §§ NORMALIZE_MODEL_ID$' "$SUBAGENT_BAR_SH"
    assert_success
    assert_output "1"
    run grep -c '^# §§ END NORMALIZE_MODEL_ID$' "$SUBAGENT_BAR_SH"
    assert_success
    assert_output "1"
    # Exactly one definition line, so a second normalize_model_id outside the
    # markers cannot shadow the lockstep-checked copy (review fix 2026-09-29).
    run grep -c '^normalize_model_id() {$' "$SUBAGENT_BAR_SH"
    assert_success
    assert_output "1"
}

@test "normalize_model_id: rewrites only terminal dotted claude-<family>-<major>.<minor>" {
    local fn case_row input expected
    fn=$(sed -n '/^# §§ NORMALIZE_MODEL_ID$/,/^# §§ END NORMALIZE_MODEL_ID$/p' "$SUBAGENT_BAR_SH")
    [ -n "$fn" ]
    eval "$fn"
    # input|expected ('' encodes the empty string)
    for case_row in \
        'anthropic/claude-opus-5.5|anthropic/claude-opus-5-5' \
        'claude-opus-5.5[1m]|claude-opus-5-5[1m]' \
        'anthropic/claude-opus-5.5[1m]|anthropic/claude-opus-5-5[1m]' \
        'anthropic/claude-opus-4.8|anthropic/claude-opus-4-8' \
        'anthropic/claude-opus-4.7|anthropic/claude-opus-4-7' \
        'anthropic/claude-fable-5.1|anthropic/claude-fable-5-1' \
        'claude-sonnet-4.6|claude-sonnet-4-6' \
        'anthropic/claude-opus-5.5-mini|anthropic/claude-opus-5.5-mini' \
        'xclaude-opus-5.5|xclaude-opus-5.5' \
        'anthropic/claude-opus-5.5[1m]x|anthropic/claude-opus-5.5[1m]x' \
        'claude-opus-5-5|claude-opus-5-5' \
        'anthropic/claude-opus-5-5|anthropic/claude-opus-5-5' \
        'gpt-5.6-sol|gpt-5.6-sol' \
        'openai/gpt-6-sol-pro[1m]|openai/gpt-6-sol-pro[1m]' \
        'z-ai/glm-5.2|z-ai/glm-5.2' \
        '|'; do
        input="${case_row%%|*}"
        expected="${case_row#*|}"
        run normalize_model_id "$input"
        assert_success
        assert_output "$expected"
    done
}

@test "lockstep: gpt_flagship_re is byte-identical in subagent-bar.sh and context-bar.sh" {
    local bar_re ctx_re context_bar_sh="${REPO_ROOT}/.claude/scripts/context-bar.sh"
    bar_re=$(sed -n "s/^gpt_flagship_re='\(.*\)'\$/\1/p" "$SUBAGENT_BAR_SH")
    ctx_re=$(sed -n "s/^gpt_flagship_re='\(.*\)'\$/\1/p" "$context_bar_sh")
    [ -n "$bar_re" ]
    [ "$bar_re" = "$ctx_re" ]
    # And it is the approved 2026-09-29 grammar plus the 2026-10-12 gpt-6.1-sol
    # alternative (user policy decision; one exact alternative, no wildcard).
    [ "$bar_re" = '^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-(astra|sol|luna)|gpt-6\.1-sol)(-pro)?(\[1m\])?$' ]
    run sed -n "s/^gpt_extended_re='\(.*\)'\$/\1/p" "$SUBAGENT_BAR_SH"
    assert_output '^(gpt-5\.6-sol|gpt-6-(astra|sol)|gpt-6\.1-sol)(-pro)?(\[1m\])?$'
}

@test "dotted anthropic/claude-opus-5.5 row: 250k NOMINAL, 300k ELEVATED -- extended-horizon profile" {
    local row tokens expected pct
    for row in "250000 NOMINAL 25" "300000 ELEVATED 30"; do
        read -r tokens expected pct <<< "$row"
        _iso_sonnet_row_fixture "anthropic/claude-opus-5.5"
        run _iso_row t1 "$tokens"
        assert_success
        assert_output --partial "$(_color_for "$expected")"
        assert_output --partial "m${pct}%"
    done
}

@test "dotted claude-opus-5.5[1m] row: 250k renders NOMINAL on the 1M window" {
    _iso_sonnet_row_fixture "claude-opus-5.5[1m]"
    run _iso_row t1 250000
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "m25%"
    refute_output --partial "$COLOR_CRITICAL"
}

@test "dotted near miss anthropic/claude-opus-5.5-mini row: 250k stays CRITICAL (not normalized)" {
    _iso_sonnet_row_fixture "anthropic/claude-opus-5.5-mini"
    run _iso_row t1 250000
    assert_success
    assert_output --partial "$COLOR_CRITICAL"
    refute_output --partial "$COLOR_NOMINAL"
}

@test "dotted anthropic/claude-opus-4.8 row: 150k maps to the 1M window (15%), ELEVATED -- not 75% of 200k" {
    _iso_sonnet_row_fixture "anthropic/claude-opus-4.8"
    run _iso_row t1 150000
    assert_success
    assert_output --partial "m15%"
    assert_output --partial "$COLOR_ELEVATED"
    refute_output --partial "m75%"
}

@test "dotted anthropic/claude-fable-5.1 row: 250k keeps the Fable profile (NOMINAL)" {
    _iso_sonnet_row_fixture "anthropic/claude-fable-5.1"
    run _iso_row t1 250000
    assert_success
    assert_output --partial "$COLOR_NOMINAL"
    assert_output --partial "m25%"
}

@test "dotted rows keep the RAW model name in the row label" {
    _iso_sonnet_row_fixture "anthropic/claude-opus-5.5"
    run _iso_row t1 250000
    assert_success
    assert_output --partial "(anthropic/claude-opus-5.5)"
    refute_output --partial "claude-opus-5-5"
    _iso_sonnet_row_fixture "claude-opus-5.5[1m]"
    run _iso_row t1 250000
    assert_success
    # The label strips only a leading claude- prefix, never the dotted version.
    assert_output --partial "(opus-5.5[1m])"
}

@test "dotted transcript models are cached RAW; dotted session + dotted row share the session window" {
    # Both models come from transcripts (no pre-seeded model caches), so this
    # exercises resolve_model_cache: the caches must hold the raw dotted name.
    # Session window 800000 is deliberately distinct from the 1M static map:
    # same-model rows use it (200k -> 25%); a spurious different-model path
    # would read 1M (20%).
    rm -rf "${TEST_DIR}/isocache" "${TEST_DIR}/${FAKE_SESSION}"
    _iso_seed_window 800000
    _write_subbar_main_model "anthropic/claude-opus-5.5"
    _write_subbar_task_model t1 "anthropic/claude-opus-5.5"
    run _iso_row t1 200000
    assert_success
    assert_output --partial "m25%"
    refute_output --partial "m20%"
    run cat "$(_iso_cache)/claude-subagent-model-${FAKE_SESSION}-t1"
    assert_output "anthropic/claude-opus-5.5"
    run cat "$(_iso_cache)/claude-model-${FAKE_SESSION}"
    assert_output "anthropic/claude-opus-5.5"
}

@test "same model, different spelling: dotted session cache + hyphenated row stays on the session window" {
    # context-bar.sh seeds claude-model-<session> from the REQUESTED .model.id
    # (dotted on OpenRouter) while the row's transcript may carry the
    # hyphenated RESPONSE spelling. Both sides are normalized, so this is a
    # same-model row: 200k / 800k session window = 25% (different-model: 20%).
    local session_spelling row_spelling pair
    for pair in \
        "anthropic/claude-opus-5.5 anthropic/claude-opus-5-5" \
        "anthropic/claude-opus-5-5 anthropic/claude-opus-5.5"; do
        read -r session_spelling row_spelling <<< "$pair"
        rm -rf "${TEST_DIR}/isocache" "${TEST_DIR}/${FAKE_SESSION}"
        _iso_seed_window 800000
        _iso_seed_session_model "$session_spelling"
        _iso_seed_task_model t1 "$row_spelling"
        run _iso_row t1 200000
        assert_success
        assert_output --partial "m25%"
        refute_output --partial "m20%"
    done
}

@test "gpt-6-sol rows (bare, provider-prefixed, [1m]) map to 1.05M and use the extended tier" {
    local model row tokens expected pct
    for model in gpt-6-sol openai/gpt-6-sol 'gpt-6-sol[1m]' 'openrouter/openai/gpt-6-sol[1m]'; do
        for row in \
            "299000 NOMINAL 28" \
            "300000 ELEVATED 28" \
            "400000 HIGH 38" \
            "500000 CRITICAL 47"; do
            read -r tokens expected pct <<< "$row"
            _iso_sonnet_row_fixture "$model"
            run _iso_row t1 "$tokens"
            assert_success
            assert_output --partial "$(_color_for "$expected")"
            assert_output --partial "m${pct}%"
        done
    done
}

@test "gpt-6-sol profile-wide boundaries use 60/75/90% on a non-ChatGPT 400k denominator" {
    local row tokens expected pct
    for row in \
        "239999 NOMINAL 59" \
        "240000 ELEVATED 60" \
        "299999 ELEVATED 74" \
        "300000 HIGH 75" \
        "359999 HIGH 89" \
        "360000 CRITICAL 90"; do
        read -r tokens expected pct <<< "$row"
        rm -rf "${TEST_DIR}/isocache" "${TEST_DIR}/${FAKE_SESSION}"
        _iso_seed_window 400000
        _iso_seed_session_model "gpt-6-sol[1m]"
        _iso_seed_task_model t1 "gpt-6-sol[1m]"
        run _iso_row t1 "$tokens"
        assert_success
        assert_output --partial "$(_color_for "$expected")"
        assert_output --partial "m${pct}%"
    done
}

@test "flagship -pro forms of 5.6-sol, 6-astra, and 6-sol use 1.05M and the extended tier" {
    local model
    for model in gpt-5.6-sol-pro gpt-6-astra-pro gpt-6-sol-pro 'gpt-6-sol-pro[1m]' \
                 openai/gpt-6-astra-pro 'openrouter/openai/gpt-5.6-sol-pro[1m]'; do
        _iso_sonnet_row_fixture "$model"
        run _iso_row t1 300000
        assert_success
        # 300k / 1.05M = 28%: extended ELEVATED (conservative would be CRITICAL).
        assert_output --partial "$COLOR_ELEVATED"
        assert_output --partial "m28%"
    done
}

@test "gpt-6-luna, gpt-6-luna-pro, gpt-5.6-terra-pro: 1.05M window but conservative tier" {
    local model
    for model in gpt-6-luna openai/gpt-6-luna 'gpt-6-luna[1m]' gpt-6-luna-pro gpt-5.6-terra-pro; do
        _iso_sonnet_row_fixture "$model"
        run _iso_row t1 150000
        assert_success
        # 150k / 1.05M = 14%; the conservative 150k absolute leg -> ELEVATED
        # (extended tier would be NOMINAL; a 200k window would be 75%).
        assert_output --partial "$COLOR_ELEVATED"
        assert_output --partial "m14%"
    done
}

@test "chatgpt lane caps gpt-6-sol, gpt-6-luna, and flagship -pro rows at 919k" {
    local model
    for model in gpt-6-sol gpt-6-luna gpt-6-sol-pro 'gpt-6-sol-pro[1m]' gpt-6-astra-pro gpt-5.6-sol-pro gpt-5.4-pro; do
        _iso_sonnet_row_fixture "$model"
        # Measured-input shim lanes read the child transcript's latest positive
        # input for participating slugs; seed it so every model has 111k.
        _append_subbar_usage t1 111000
        run _iso_row t1 111000 DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
        assert_success
        # 111000 / 919000 = 12% (1.05M uncapped would be 10%).
        assert_output --partial "m12%"
        refute_output --partial "context pending"
    done
}

@test "measured input: gpt-6-sol, gpt-6-luna, and flagship -pro participate; mini/chat -pro does not" {
    export DAAF_PROVIDER_SHIM=openai
    local mode model
    for mode in chatgpt openai; do
        for model in gpt-6-sol 'openrouter/openai/gpt-6-luna[1m]' gpt-6-astra-pro 'gpt-5.6-sol-pro[1m]' gpt-6-sol-pro; do
            _measured_child "$model"
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial '70k'
            refute_output --partial 'm24'
        done
        for model in gpt-5.6-mini-pro gpt-6-terra gpt-6-sol-mini 'gpt-6-sol[1m]-pro' gpt-6-sol-pro-x; do
            _measured_child "$model"
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial 'm24'
            refute_output --partial '70k'
        done
    done
}

@test "GPT-6 and -pro near misses stay conservative on the generic 200k row window (no 919k cap)" {
    local model
    for model in gpt-6-terra gpt-6 gpt-6-sol-mini gpt-6-sol-pro-x gpt-5.6-mini-pro xgpt-6-sol \
                 vendor/notgpt-6-sol gpt-6-sol-chat; do
        _iso_sonnet_row_fixture "$model" 1000000
        run _iso_row t1 90000 DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
        assert_success
        # 90k / 200k = 45% -> conservative ELEVATED (extended would be NOMINAL;
        # 919k or 1.05M would be 9% / 8%).
        assert_output --partial "m45%"
        assert_output --partial "$COLOR_ELEVATED"
    done
}

@test "malformed GPT-family [1m] ids (gpt-6-sol[1m]-pro etc.) map to 200k and the conservative tier" {
    # Review fix 2026-09-29: these used to fall through to the generic Claude
    # *\[1m\]* window arm (1,000,000) in this script while the reporter and
    # context-bar.sh mapped them to 200,000. The flagship-family pre-filter now
    # routes them to 200k first, so all three scripts agree.
    # 90k / 200k = 45% -> conservative ELEVATED (a 1M window would be 9% NOMINAL).
    local model
    for model in 'gpt-6-sol[1m]-pro' 'gpt-6-sol-mini[1m]' 'gpt-6-astra[1m]-pro' \
                 'gpt-5.6-sol[1m]-pro' 'gpt-6-astra[1m]-x' 'openai/gpt-6-luna[1m]-pro'; do
        _iso_sonnet_row_fixture "$model"
        run _iso_row t1 90000
        assert_success
        assert_output --partial "m45%"
        assert_output --partial "$COLOR_ELEVATED"
        refute_output --partial "m9%"
    done
}

# 2026-10-12 GPT-6.1 Sol registration (USER POLICY DECISION, not validation):
# gpt-6.1-sol, with an optional -pro and then an optional [1m], reads exactly as
# gpt-6-sol — 1.05M window (OpenRouter openai/gpt-6.1-sol fetched 2026-10-12),
# inferred 919k ChatGPT-lane cap (lane ceiling pending measurement), extended
# tier, measured-input participation. No gpt-6.1-* wildcard.

@test "gpt-6.1-sol rows (bare, provider-prefixed, [1m], -pro) map to 1.05M and use the extended tier" {
    local model row tokens expected pct
    for model in gpt-6.1-sol openai/gpt-6.1-sol 'gpt-6.1-sol[1m]' 'openrouter/openai/gpt-6.1-sol[1m]' \
                 gpt-6.1-sol-pro 'gpt-6.1-sol-pro[1m]'; do
        for row in \
            "299000 NOMINAL 28" \
            "300000 ELEVATED 28" \
            "400000 HIGH 38" \
            "500000 CRITICAL 47"; do
            read -r tokens expected pct <<< "$row"
            _iso_sonnet_row_fixture "$model"
            run _iso_row t1 "$tokens"
            assert_success
            assert_output --partial "$(_color_for "$expected")"
            assert_output --partial "m${pct}%"
        done
    done
}

@test "gpt-6.1-sol profile-wide boundaries use 60/75/90% on a non-ChatGPT 400k denominator" {
    local row tokens expected pct
    for row in \
        "239999 NOMINAL 59" \
        "240000 ELEVATED 60" \
        "299999 ELEVATED 74" \
        "300000 HIGH 75" \
        "359999 HIGH 89" \
        "360000 CRITICAL 90"; do
        read -r tokens expected pct <<< "$row"
        rm -rf "${TEST_DIR}/isocache" "${TEST_DIR}/${FAKE_SESSION}"
        _iso_seed_window 400000
        _iso_seed_session_model "gpt-6.1-sol[1m]"
        _iso_seed_task_model t1 "gpt-6.1-sol[1m]"
        run _iso_row t1 "$tokens"
        assert_success
        assert_output --partial "$(_color_for "$expected")"
        assert_output --partial "m${pct}%"
    done
}

@test "chatgpt lane caps gpt-6.1-sol rows at 919k" {
    local model
    for model in gpt-6.1-sol 'gpt-6.1-sol[1m]' gpt-6.1-sol-pro; do
        _iso_sonnet_row_fixture "$model"
        _append_subbar_usage t1 111000
        run _iso_row t1 111000 DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
        assert_success
        # 111000 / 919000 = 12% (1.05M uncapped would be 10%).
        assert_output --partial "m12%"
        refute_output --partial "context pending"
    done
}

@test "measured input: gpt-6.1-sol participates; GPT-6.1 near misses do not" {
    export DAAF_PROVIDER_SHIM=openai
    local mode model
    for mode in chatgpt openai; do
        for model in gpt-6.1-sol 'openrouter/openai/gpt-6.1-sol[1m]' gpt-6.1-sol-pro; do
            _measured_child "$model"
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial '70k'
            refute_output --partial 'm24'
        done
        for model in gpt-6.1-luna gpt-6.1-sol-mini 'gpt-6.1-sol[1m]-pro' gpt-6x1-sol; do
            _measured_child "$model"
            run env SHIM_BACKEND_MODE="$mode" bash "$SUBAGENT_BAR_SH" < <(_measured_payload)
            assert_success
            assert_output --partial 'm24'
            refute_output --partial '70k'
        done
    done
}

@test "GPT-6.1 near misses stay conservative on the generic 200k row window (no 919k cap)" {
    local model
    for model in gpt-6.1-luna gpt-6.1-astra gpt-6.1 gpt-6.1-sol-mini gpt-6.1-sol-chat \
                 gpt-6.1-sol-pro-x gpt-6.10-sol gpt-6x1-sol xgpt-6.1-sol; do
        _iso_sonnet_row_fixture "$model" 1000000
        run _iso_row t1 90000 DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt
        assert_success
        # 90k / 200k = 45% -> conservative ELEVATED (extended would be NOMINAL;
        # 919k or 1.05M would be 9% / 8%).
        assert_output --partial "m45%"
        assert_output --partial "$COLOR_ELEVATED"
    done
}

@test "malformed GPT-6.1 Sol [1m] ids map to 200k, not the generic 1M [1m] arm" {
    # Family pre-filter now includes gpt-6.1-sol, so these agree with the
    # reporter and context-bar (200k). 90k / 200k = 45% ELEVATED.
    local model
    for model in 'gpt-6.1-sol[1m]-pro' 'gpt-6.1-sol-mini[1m]' 'openai/gpt-6.1-sol[1m]-x'; do
        _iso_sonnet_row_fixture "$model"
        run _iso_row t1 90000
        assert_success
        assert_output --partial "m45%"
        assert_output --partial "$COLOR_ELEVATED"
        refute_output --partial "m9%"
    done
}

# Cross-script window agreement (review fix 2026-09-29). subagent-bar.sh's
# static_window_for_model (extracted and evaluated with its own EREs) must return
# exactly the window context-bar.sh's static map caches for the same id (no
# OpenRouter lookup: ANTHROPIC_BASE_URL is unset, payload window 200000). The
# reporter side of the same table lives in tests/bash/context_reporter.bats.
_subbar_static_window() {
    bash -c '
        eval "$(grep -E "^gpt_[a-z_]+_re=" "$1")"
        eval "$(sed -n "/^static_window_for_model() {\$/,/^}\$/p" "$1")"
        static_window_for_model "$2"
    ' _ "$SUBAGENT_BAR_SH" "$1"
}

_ctxbar_static_window() {
    local cache="${TEST_DIR}/ctxbarcache" context_bar_sh="${REPO_ROOT}/.claude/scripts/context-bar.sh"
    rm -rf "$cache"
    mkdir -p "$cache"
    jq -nc --arg m "$1" --arg cwd "$TEST_DIR" --arg sid "$FAKE_SESSION" \
        '{model:{id:$m,display_name:$m},cwd:$cwd,transcript_path:($cwd+"/none.jsonl"),session_id:$sid,context_window:{context_window_size:200000}}' \
        | env -u ANTHROPIC_BASE_URL DAAF_CONTEXT_BAR_CACHE_DIR="$cache" bash "$context_bar_sh" >/dev/null 2>&1
    tr -d '\n' < "${cache}/claude-ctx-window-${FAKE_SESSION}"
}

@test "cross-script: subagent-bar and context-bar agree on windows for malformed and exact GPT-family ids" {
    local row model expected bar ctx
    for row in \
        'gpt-6-sol[1m]-pro 200000' \
        'gpt-6-sol-mini[1m] 200000' \
        'gpt-6-astra[1m]-pro 200000' \
        'gpt-5.6-sol[1m]-pro 200000' \
        'gpt-5.6-sol[1m]x 200000' \
        'gpt-6-astra[1m]-x 200000' \
        'openai/gpt-6-luna[1m]-pro 200000' \
        'gpt-6-sol-pro[1m] 1050000' \
        'openai/gpt-6-luna 1050000' \
        'gpt-6.1-sol 1050000' \
        'gpt-6.1-sol-pro[1m] 1050000' \
        'gpt-6.1-sol[1m]-pro 200000' \
        'gpt-6.1-luna 200000' \
        'gpt-5.6-mini[1m] 400000' \
        'gpt-5.6-chat 128000'; do
        read -r model expected <<< "$row"
        bar=$(_subbar_static_window "$model")
        ctx=$(_ctxbar_static_window "$model")
        [ "$bar" = "$expected" ] || { echo "subagent-bar $model -> $bar (want $expected)"; return 1; }
        [ "$ctx" = "$expected" ] || { echo "context-bar $model -> $ctx (want $expected)"; return 1; }
    done
}

@test "lockstep: GPT flagship-family pre-filter glob is byte-identical in subagent-bar.sh and context-bar.sh" {
    local bar_glob ctx_glob context_bar_sh="${REPO_ROOT}/.claude/scripts/context-bar.sh"
    bar_glob=$(sed -n 's/^[[:space:]]*\(gpt-5\.4|gpt-5\.4.*\))$/\1/p' "$SUBAGENT_BAR_SH")
    ctx_glob=$(sed -n 's/^[[:space:]]*\(gpt-5\.4|gpt-5\.4.*\))$/\1/p' "$context_bar_sh")
    [ -n "$bar_glob" ]
    [ "$(printf '%s\n' "$bar_glob" | wc -l)" -eq 1 ]
    [ "$bar_glob" = "$ctx_glob" ]
}
