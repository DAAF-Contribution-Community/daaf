#!/usr/bin/env bats
# ============================================================================
# Tests for context-bar.sh -- main statusline context-window resolution
# ============================================================================
# These tests are deterministic and network-independent. Static cases keep the
# OpenRouter branch disabled; dynamic cases prepend a fake curl executable that
# serves a controlled catalogue from project scratch. No live provider call is
# possible, and fake catalogue/cache data never writes to /tmp.
# ============================================================================

load 'test_helper'

CONTEXT_BAR_SH="${CONTEXT_BAR_SH:-${REPO_ROOT}/.claude/scripts/context-bar.sh}"
FAKE_SESSION="bats-context-bar-session"

setup() {
    common_setup
    SCRATCH_DIR="${REPO_ROOT}/scripts/scratch/context-bar-bats-${BATS_TEST_NUMBER}-$$"
    MOCK_BIN="${SCRATCH_DIR}/bin"
    DAAF_CONTEXT_BAR_CACHE_DIR="${SCRATCH_DIR}/cache"
    CTX_CACHE="${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-ctx-window-${FAKE_SESSION}"
    MODEL_CACHE="${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    OR_CACHE="${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-or-models-${FAKE_SESSION}"
    QUOTA_STATE_FILE="${SCRATCH_DIR}/quota_state.json"
    mkdir -p "$MOCK_BIN" "$DAAF_CONTEXT_BAR_CACHE_DIR"
    cat > "${MOCK_BIN}/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
printf '{"data":[{"id":"z-ai/glm-5.2","context_length":%s}]}' \
    "${MOCK_OPENROUTER_CONTEXT:?MOCK_OPENROUTER_CONTEXT must be set}"
MOCK_CURL
    chmod +x "${MOCK_BIN}/curl"
    unset ANTHROPIC_BASE_URL
    unset CLAUDE_CODE_MAX_CONTEXT_TOKENS
    unset DAAF_PROVIDER_SHIM
    unset SHIM_BACKEND_MODE
    export CONTEXT_BAR_SH FAKE_SESSION SCRATCH_DIR MOCK_BIN
    export DAAF_CONTEXT_BAR_CACHE_DIR CTX_CACHE MODEL_CACHE OR_CACHE QUOTA_STATE_FILE
}

# Write a quota_state.json fixture. Args: captured_at, primary_used_pct,
# primary_window_min, primary_reset_s, secondary_used_pct, secondary_window_min,
# secondary_reset_s. The five snapshot fields the reader never consults are fixed
# constants here (plan_type, active_limit, credits_has, credits_balance,
# credits_unlimited -- credits_balance is numeric-looking but still reader-ignored).
# Mirrors the shim's _write_quota_state output shape.
_write_quota_state() {
    printf '{"captured_at":%s,"plan_type":"pro","active_limit":"premium","primary_used_pct":"%s","primary_window_min":"%s","primary_reset_s":"%s","secondary_used_pct":"%s","secondary_window_min":"%s","secondary_reset_s":"%s","credits_has":"False","credits_balance":"0","credits_unlimited":"False"}' \
        "$1" "$2" "$3" "$4" "$5" "$6" "$7" > "$QUOTA_STATE_FILE"
}

teardown() {
    rm -rf "$SCRATCH_DIR"
    common_teardown
}

_payload() {
    local incoming_window="${2:-200000}"
    printf '{"model":{"id":"%s","display_name":"%s"},"cwd":"%s","transcript_path":"","session_id":"%s","context_window":{"context_window_size":%s}}' \
        "$1" "$1" "$TEST_DIR" "$FAKE_SESSION" "$incoming_window"
}

@test "context-bar.sh parses without errors" {
    run bash -n "$CONTEXT_BAR_SH"
    assert_success
}

@test "authoritative statusline model id is cached atomically for the session" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "openrouter/openai/gpt-5.6-terra[1m]")
    assert_success

    run cat "$MODEL_CACHE"
    assert_success
    assert_output "openrouter/openai/gpt-5.6-terra[1m]"

    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -maxdepth 1 -name 'claude-model-*.tmp.*' -print
    assert_success
    assert_output ""
}

@test "empty authoritative model id replaces a stale model cache with unresolved identity" {
    printf '%s' 'gpt-5.6-sol' > "$MODEL_CACHE"
    run bash "$CONTEXT_BAR_SH" <<JSON
{"model":{"display_name":"Unknown"},"cwd":"$TEST_DIR","transcript_path":"","session_id":"$FAKE_SESSION","context_window":{"context_window_size":200000}}
JSON
    assert_success

    run test -f "$MODEL_CACHE"
    assert_success
    run test ! -s "$MODEL_CACHE"
    assert_success
}

@test "unsafe session ids skip all session-scoped cache writes while statusline stays fail-open" {
    local unsafe_session
    for unsafe_session in \
        '../escape' \
        'nested/session' \
        'session with spaces' \
        '-leading-dash' \
        "$(printf 'a%.0s' {1..129})"; do
        run bash "$CONTEXT_BAR_SH" <<JSON
{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"cwd":"$TEST_DIR","transcript_path":"","session_id":"$unsafe_session","context_window":{"context_window_size":200000}}
JSON
        assert_success
        assert_output --partial "gpt-5.6-sol"
    done

    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""
}

@test "newline NUL and unit-separator session identities cannot alias or poison caches" {
    printf '%s' 'seed-safe-model' > "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-model-safe"
    printf '%s' '111111' > "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-ctx-window-safe"
    printf '%s' 'seed-victim-model' > "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-model-victim"
    printf '%s' '222222' > "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-ctx-window-victim"

    local payload
    for payload in \
        '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"session_id":"safe\nid","context_window":{"context_window_size":1000000}}' \
        '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"session_id":"safe\n","context_window":{"context_window_size":1000000}}'; do
        run bash "$CONTEXT_BAR_SH" <<< "$payload"
        assert_success
        assert_output --partial "Fable 5"
        refute_output --partial "of 1050k tokens"
    done

    printf -v payload '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"session_id":"victim\\u%04x","context_window":{"context_window_size":1000000}}' 0
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "Fable 5"
    refute_output --partial "of 1050k tokens"

    printf -v payload '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"session_id":"victim\\u%04xgpt-5.6-sol","context_window":{"context_window_size":1000000}}' 31
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "Fable 5"
    refute_output --partial "of 1050k tokens"

    run cat "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-model-safe"
    assert_success
    assert_output "seed-safe-model"
    run cat "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-ctx-window-safe"
    assert_success
    assert_output "111111"
    run cat "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-model-victim"
    assert_success
    assert_output "seed-victim-model"
    run cat "${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-ctx-window-victim"
    assert_success
    assert_output "222222"
}

@test "controls in earlier display and path fields cannot shift later identity or rate fields" {
    local payload
    printf -v payload '{"model":{"id":"gpt-5.6-sol","display_name":"GPT\\u%04xDisplay\\u%04xName"},"cwd":"bad\\u%04xpath","transcript_path":"bad\\u%04xtranscript","session_id":"%s","context_window":{"context_window_size":1050000},"effort":{"level":"high\\u%04xshift"},"rate_limits":{"five_hour":{"used_percentage":"42\\u%04xgpt","resets_at":"bad\\u%04xreset"},"seven_day":{"used_percentage":13,"resets_at":0}}}' 10 31 10 31 "$FAKE_SESSION" 10 31 10
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "GPTDisplayName"
    assert_output --partial "of 1050k tokens"
    assert_output --partial "Plan usage:"
    assert_output --partial "7d:13%"
    refute_output --partial "5h:"

    run cat "$MODEL_CACHE"
    assert_success
    assert_output "gpt-5.6-sol"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "control-bearing model identity is unresolved and cannot poison a stale cache" {
    local payload
    printf '%s' 'gpt-5.6-sol' > "$MODEL_CACHE"
    printf -v payload '{"model":{"id":"claude-fable-5\\u%04xgpt-5.6-sol","display_name":"Fable 5"},"cwd":"%s","transcript_path":"","session_id":"%s","context_window":{"context_window_size":200000}}' 31 "$TEST_DIR" "$FAKE_SESSION"
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "Fable 5"
    assert_output --partial "of 200k tokens"
    refute_output --partial "of 1050k tokens"

    run test ! -s "$MODEL_CACHE"
    assert_success
}

@test "missing null empty and non-string session ids never use a shared default cache" {
    local payload
    for payload in \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"context_window":{"context_window_size":200000}}' \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"session_id":null,"context_window":{"context_window_size":200000}}' \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"session_id":"","context_window":{"context_window_size":200000}}' \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"session_id":42,"context_window":{"context_window_size":200000}}' \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"session_id":true,"context_window":{"context_window_size":200000}}' \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"session_id":{"value":"object-id"},"context_window":{"context_window_size":200000}}' \
        '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"session_id":["array-id"],"context_window":{"context_window_size":200000}}'; do
        run bash "$CONTEXT_BAR_SH" <<< "$payload"
        assert_success
        assert_output --partial "gpt-5.6-sol"
    done

    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""
}

@test "malformed statusline input exits successfully without writing session caches" {
    run bash "$CONTEXT_BAR_SH" <<< 'not-json {{{'
    assert_success

    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""
}

@test "missing jq leaves statusline fail-open and creates no session or default cache" {
    local bindir="${SCRATCH_DIR}/nojq-bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    ln -s "$(command -v basename)" "${bindir}/basename"

    run env -i \
        PATH="$bindir" \
        DAAF_CONTEXT_BAR_CACHE_DIR="$DAAF_CONTEXT_BAR_CACHE_DIR" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "of 200k tokens"

    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""
}

@test "gpt-5.6-sol[1m] displays 1050k and caches the 1050000 physical window" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]")
    assert_success
    assert_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "dynamic OpenRouter context 1048576 wins over the static resolution path" {
    run env \
        ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
        MOCK_OPENROUTER_CONTEXT=1048576 \
        PATH="${MOCK_BIN}:${PATH}" \
        bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
    assert_success
    assert_output --partial "of 1048k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1048576"
}

@test "authoritative dynamic OpenRouter context 200000 is not rewritten by the GLM static fallback" {
    run env \
        ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
        MOCK_OPENROUTER_CONTEXT=200000 \
        PATH="${MOCK_BIN}:${PATH}" \
        bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
    assert_success
    assert_output --partial "of 200k tokens"
    refute_output --partial "of 1048k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "200000"
}

@test "exact z-ai/glm-5.2 uses the narrow 1,048,576 static fallback" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
    assert_success
    assert_output --partial "of 1048k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1048576"
}

@test "terminal GLM-5.2 date snapshot uses the 1,048,576 static fallback" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2-20260715")
    assert_success
    assert_output --partial "of 1048k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1048576"
}

@test "z-ai/glm-5.2-air is not assigned the exact model's static window" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2-air")
    assert_success
    assert_output --partial "of 200k tokens"
    refute_output --partial "of 1048k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "200000"
}

@test "explicit CLAUDE_CODE_MAX_CONTEXT_TOKENS overrides the GLM static fallback" {
    run env CLAUDE_CODE_MAX_CONTEXT_TOKENS=333333 bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
    assert_success
    assert_output --partial "of 333k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "333333"
}

# =========================================================================
# ChatGPT-subscription lane: final gpt-5.4/5.5/5.6 accounting cap is 370k
# -------------------------------------------------------------------------
# Canonical lane gate: DAAF_PROVIDER_SHIM=openai AND SHIM_BACKEND_MODE=chatgpt.
# The final min(resolved, 370000) constraint runs after payload, static-map,
# dynamic, and explicit-override resolution. Both exact lane values are required;
# malformed or partial signals keep the API/OpenRouter behavior fail-open.
# =========================================================================

@test "chatgpt lane: incoming 1,050,000 payload is finally capped and cached at 370,000" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 370k tokens"
    refute_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "370000"
}

@test "chatgpt lane: explicit 1,050,000 override cannot raise the final 370,000 cap" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 370k tokens"
    refute_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "370000"
}

@test "chatgpt lane: lower positive explicit override remains lower than the cap" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=333333 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 333k tokens"
    refute_output --partial "of 370k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "333333"
}

@test "API shim lane keeps the wider 1,050,000 flagship window" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "of 370k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "OpenRouter route keeps the wider 1,050,000 flagship window" {
    run env ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
        MOCK_OPENROUTER_CONTEXT=1048576 PATH="${MOCK_BIN}:${PATH}" \
        bash "$CONTEXT_BAR_SH" < <(_payload "openai/gpt-5.6-sol" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "of 370k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "each missing lane signal leaves the 1,050,000 flagship window unchanged" {
    run env SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"

    run env DAAF_PROVIDER_SHIM=openai \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
}

@test "malformed and noncanonical lane values do not activate the subscription cap" {
    run env DAAF_PROVIDER_SHIM=OpenAI SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=' chatgpt ' \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
}

@test "chatgpt lane does not perturb a non-GPT (Claude) model window" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_BAR_SH" < <(_payload "claude-fable-5" 1000000)
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "of 370k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

# =========================================================================
# Canonical positive-decimal override contract
# =========================================================================

@test "canonical override 370000 is accepted on the API lane" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=370000 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol" 1050000)
    assert_success
    assert_output --partial "of 370k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "370000"
}

@test "invalid decimal overrides are ignored without arithmetic diagnostics and the exact-lane cap still applies" {
    local value
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
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol" 1050000)
        assert_success
        assert_output --partial "of 370k tokens"
        refute_output --partial "value too great"
        refute_output --partial "syntax error"
        run cat "$CTX_CACHE"
        assert_success
        assert_output "370000"
    done
}

# =========================================================================
# Anchored terminal-slug GPT physical-family classification
# =========================================================================

@test "supported bare and provider-prefixed GPT flagship slugs map to 1.05M" {
    local model
    for model in \
        gpt-5.4 \
        gpt-5.5 \
        gpt-5.6 \
        gpt-5.6-sol \
        gpt-5.6-terra \
        gpt-5.6-luna \
        'gpt-5.6-sol[1m]' \
        openrouter/openai/gpt-5.6-sol; do
        run bash "$CONTEXT_BAR_SH" < <(_payload "$model")
        assert_success
        assert_output --partial "of 1050k tokens"
    done
}

@test "anchored GPT 5.2, mini, and chat variants retain their smaller physical mappings" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.2")
    assert_success
    assert_output --partial "of 400k tokens"

    run bash "$CONTEXT_BAR_SH" < <(_payload "openai/gpt-5.6-sol-mini")
    assert_success
    assert_output --partial "of 400k tokens"

    run bash "$CONTEXT_BAR_SH" < <(_payload "openai/gpt-5.6-sol-chat")
    assert_success
    assert_output --partial "of 128k tokens"
}

@test "malformed left boundaries and unsupported GPT version prefixes stay on the ordinary 200k default" {
    local model
    for model in \
        vendor/notgpt-5.6-sol \
        xgpt-5.6-sol \
        foo-gpt-5.6-sol \
        gpt-5.60 \
        gpt-5.60-sol; do
        run bash "$CONTEXT_BAR_SH" < <(_payload "$model")
        assert_success
        assert_output --partial "of 200k tokens"
        refute_output --partial "of 1050k tokens"
    done
}

@test "chatgpt final-cap predicate accepts anchored provider slugs and rejects adversarial near misses" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "openrouter/openai/gpt-5.6-terra[1m]" 1050000)
    assert_success
    assert_output --partial "of 370k tokens"

    local model
    for model in vendor/notgpt-5.6-sol xgpt-5.6-sol foo-gpt-5.6-sol gpt-5.60 gpt-5.60-sol; do
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_BAR_SH" < <(_payload "$model" 1050000)
        assert_success
        assert_output --partial "of 1050k tokens"
        refute_output --partial "of 370k tokens"
    done
}

# =========================================================================
# Codex (ChatGPT-subscription) Plan-usage segment (v1.3.1)
# -------------------------------------------------------------------------
# On shim-lane sessions (DAAF_PROVIDER_SHIM=openai AND SHIM_BACKEND_MODE=chatgpt)
# with no native rate limits in the payload, context-bar.sh reads the shim's
# quota_state.json (DAAF_QUOTA_STATE_FILE test seam) and renders "Plan usage:".
# The reader computes the absolute reset instant as captured_at + primary_reset_s.
# =========================================================================

@test "codex Plan-usage renders 7d label pct and countdown from a fresh state file" {
    local now
    now="$(date +%s)"
    # primary_reset_s ~4.65 days -> a future reset -> a "(4d..h)" countdown.
    _write_quota_state "$now" 73 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "Plan usage:"
    assert_output --partial "7d:73%"
    assert_output --partial "(4d"
}

@test "codex Plan-usage omits an all-zero secondary window" {
    local now
    now="$(date +%s)"
    _write_quota_state "$now" 73 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "7d:73%"
    refute_output --partial "5h:"
}

@test "codex Plan-usage renders a positive secondary window when present" {
    local now
    now="$(date +%s)"
    # secondary: 300 min -> "5h", 5%, reset 600s in the future.
    _write_quota_state "$now" 73 10080 402168 5 300 600
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "7d:73%"
    assert_output --partial "5h:5%"
}

@test "codex Plan-usage drops the whole segment when the primary window is stale" {
    local past
    past="$(( $(date +%s) - 100000 ))"
    # captured_at + 50s is well in the past -> stale -> segment dropped entirely.
    _write_quota_state "$past" 73 10080 50 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    # Rest of the bar is intact (chatgpt lane caps gpt-5.6-sol at 370k).
    assert_output --partial "of 370k tokens"
}

@test "codex Plan-usage is absent on malformed state JSON and the bar stays intact" {
    printf '{"captured_at":' > "$QUOTA_STATE_FILE"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    assert_output --partial "of 370k tokens"
}

@test "codex Plan-usage is gated off on a native session even with a state file present" {
    local now
    now="$(date +%s)"
    _write_quota_state "$now" 73 10080 402168 0 0 0
    # No shim lane env (setup unsets DAAF_PROVIDER_SHIM/SHIM_BACKEND_MODE).
    run env DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    assert_output --partial "of 1050k tokens"
}

@test "codex Plan-usage renders a zero primary percent" {
    local now
    now="$(date +%s)"
    _write_quota_state "$now" 0 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "7d:0%"
}

@test "codex Plan-usage segment is dropped when primary_used_pct carries a hostile control-char escape" {
    local now
    now="$(date +%s)"
    # Valid JSON (a properly-escaped unicode sequence, not a raw control byte)
    # whose parsed value embeds an ESC/ANSI sequence in primary_used_pct.
    # Bypasses _write_quota_state (which only accepts plain values) to write
    # the JSON literal directly; the double backslash below makes printf emit
    # a literal backslash-u-0-0-1-b sequence in the file, mirroring how the
    # earlier newline/NUL bats fixtures embed JSON unicode escapes rather
    # than raw bytes.
    printf '{"captured_at":%s,"plan_type":"pro","active_limit":"premium","primary_used_pct":"73\\u001b[31m","primary_window_min":"10080","primary_reset_s":"402168","secondary_used_pct":"0","secondary_window_min":"0","secondary_reset_s":"0","credits_has":"False","credits_balance":"0","credits_unlimited":"False"}' \
        "$now" > "$QUOTA_STATE_FILE"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    # Rest of the bar is intact (chatgpt lane caps gpt-5.6-sol at 370k).
    assert_output --partial "of 370k tokens"
}

# =========================================================================
# Hardening: terminal-escape-safe rendering (Finding 1 / Convention 1)
# -------------------------------------------------------------------------
# Colors are ANSI-C ($'...') constants and the final render is printf '%s'.
# A printable backslash-escape payload arriving in an untrusted field must stay
# an inert literal (never re-materialized into a real ESC/OSC), while real
# control bytes in a field are still stripped by the jq [[:cntrl:]] stage.
# =========================================================================

@test "printable escape payload in the display name stays a literal and is not re-materialized" {
    local payload
    # JSON \\033 -> literal backslash-0-3-3 after jq parse (printable, no control
    # byte). Under the old printf '%b' render this would have become a real ESC and
    # emitted a live OSC 52 clipboard-write sequence; under '%s' it stays literal.
    payload='{"model":{"id":"claude-fable-5","display_name":"PRE\\033]52;c;OSCPAYLOAD"},"cwd":"'"$TEST_DIR"'","transcript_path":"","session_id":"'"$FAKE_SESSION"'","context_window":{"context_window_size":200000}}'
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial '\033]52;c;OSCPAYLOAD'
    assert_output --partial "of 200k tokens"
}

@test "a real ESC byte in the display name is still stripped by the jq control filter" {
    local payload
    # JSON  -> a REAL ESC byte after parse; the display filter removes it so
    # the surrounding text joins cleanly and no raw ESC reaches the display stream.
    printf -v payload '{"model":{"id":"claude-fable-5","display_name":"AAA\\u%04xBBB"},"cwd":"%s","transcript_path":"","session_id":"%s","context_window":{"context_window_size":200000}}' 27 "$TEST_DIR" "$FAKE_SESSION"
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "AAABBB"
}

# =========================================================================
# Hardening: closed-set flagship grammar rejects malformed suffixes (Finding 4)
# -------------------------------------------------------------------------
# The anchored ERE ^gpt-5\.(4|5|6)(-(sol|terra|luna))?(\[1m\])?$ tightens the
# old case-globs (gpt-5.6[-\[]*) that accepted arbitrary trailing junk. These
# five slugs used to map to the 1,050,000 flagship window; they now fall through.
# =========================================================================

@test "anchored flagship grammar rejects malformed suffixes the old globs accepted" {
    local model
    for model in \
        'gpt-5.4-' \
        'gpt-5.4x' \
        'gpt-5.6-experimental' \
        'gpt-5.5[1m' \
        'gpt-5.6-sol[1m]x'; do
        run bash "$CONTEXT_BAR_SH" < <(_payload "$model")
        assert_success
        assert_output --partial "of 200k tokens"
        refute_output --partial "of 1050k tokens"
    done
}

@test "chatgpt lane final cap ignores malformed flagship-suffix near-misses" {
    local model
    for model in 'gpt-5.4-' 'gpt-5.6-experimental' 'gpt-5.5[1m' 'gpt-5.6-sol[1m]x'; do
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_BAR_SH" < <(_payload "$model" 1050000)
        assert_success
        assert_output --partial "of 1050k tokens"
        refute_output --partial "of 370k tokens"
    done
}

# =========================================================================
# Hardening: bounded numerator before x100 (Finding 10 / Convention 5)
# -------------------------------------------------------------------------
# context_length is guarded (is_canonical_positive_decimal AND <= INT64_MAX/100 =
# 92233720368547758) before `context_length * 100`, so a huge token count cannot
# overflow signed-64 and wrap pct negative. NOTE: jq (IEEE-754 doubles) rounds
# both 92233720368547758 and ...759 to 92233720368547760 before the guard sees
# them, so the exact +/-1 boundary is not separately observable through the
# transcript->jq path; these tests exercise the guard's observable contract (a
# safe value renders a real clamped pct; an overflow-inducing value falls to the
# baseline with a non-negative reading and no arithmetic diagnostic).
# =========================================================================

@test "a large but safe transcript token count renders a real clamped percentage" {
    local tf payload
    tf="${SCRATCH_DIR}/transcript_safe.jsonl"
    # 9e11 tokens: jq-exact (< 2^53) and 9e11*100 stays well within int64.
    printf '%s\n' '{"message":{"usage":{"input_tokens":900000000000}}}' > "$tf"
    printf -v payload '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"cwd":"%s","transcript_path":"%s","session_id":"%s","context_window":{"context_window_size":200000}}' "$TEST_DIR" "$tf" "$FAKE_SESSION"
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "100% of 200k tokens"
    refute_output --partial "~100%"
}

@test "an overflow-inducing transcript token count falls to baseline with no negative percent" {
    local tf payload
    tf="${SCRATCH_DIR}/transcript_huge.jsonl"
    # jq rounds this to 92233720368547760 (> INT64_MAX/100); *100 would overflow
    # signed-64 and wrap pct negative if unguarded. The guard rejects it -> baseline.
    printf '%s\n' '{"message":{"usage":{"input_tokens":92233720368547758}}}' > "$tf"
    printf -v payload '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"cwd":"%s","transcript_path":"%s","session_id":"%s","context_window":{"context_window_size":200000}}' "$TEST_DIR" "$tf" "$FAKE_SESSION"
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    assert_output --partial "~10% of 200k tokens"
    refute_output --partial "value too great"
    refute_output --partial "syntax error"
}

# =========================================================================
# Hardening: redirection-open diagnostics are suppressed (Finding 11 / Conv. 6)
# -------------------------------------------------------------------------
# Cache writes are brace-wrapped so 2>/dev/null covers an open() failure on '>'.
# An unusable cache dir (a regular file -> ENOTDIR, or a child of a nonexistent
# dir -> ENOENT) must not leak a diagnostic onto the display stream; the
# statusline still renders and exits 0.
# =========================================================================

@test "cache dir that is a regular file (ENOTDIR) does not leak an open diagnostic" {
    local regfile="${SCRATCH_DIR}/reg-not-dir"
    printf 'x' > "$regfile"
    run env DAAF_CONTEXT_BAR_CACHE_DIR="$regfile" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "Not a directory"
    refute_output --partial "No such file"
}

@test "cache dir under a nonexistent parent (ENOENT) does not leak an open diagnostic" {
    run env DAAF_CONTEXT_BAR_CACHE_DIR="${SCRATCH_DIR}/does-not-exist/sub" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "No such file"
    refute_output --partial "Not a directory"
}

# =========================================================================
# Hardening: atomic ctx-window publish (Finding 5 / Convention 7)
# -------------------------------------------------------------------------
# The claude-ctx-window-* cache is written to a writer-private temp then renamed,
# so a concurrent reader never sees a momentarily-empty file. Observable here:
# the final value is present and no .tmp.* artifact is left behind.
# =========================================================================

@test "context window cache is published atomically with no leftover temp file" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]")
    assert_success
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -maxdepth 1 -name 'claude-ctx-window-*.tmp.*' -print
    assert_success
    assert_output ""
}

# =========================================================================
# Hardening: OpenRouter catalog private temp + JSON validation (Finding 6 / Conv 8)
# -------------------------------------------------------------------------
# A 200-response body that is not a JSON object with a .data array must NOT be
# promoted to the session cache; resolution falls back to the static map.
# =========================================================================

@test "corrupt OpenRouter catalog body is not promoted and falls back to the static map" {
    local badbin="${SCRATCH_DIR}/badcurl-bin"
    mkdir -p "$badbin"
    cat > "${badbin}/curl" <<'MOCK_BAD_CURL'
#!/usr/bin/env bash
printf '%s' "${MOCK_OPENROUTER_BODY?MOCK_OPENROUTER_BODY must be set}"
MOCK_BAD_CURL
    chmod +x "${badbin}/curl"

    local body
    for body in \
        '{"data":"not-an-array"}' \
        '{"data":' \
        '{"error":"rate limited"}' \
        'null'; do
        rm -f "$OR_CACHE"
        run env ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
            PATH="${badbin}:${PATH}" \
            MOCK_OPENROUTER_BODY="$body" \
            bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
        assert_success
        assert_output --partial "of 1048k tokens"
        run test -e "$OR_CACHE"
        assert_failure
    done
}

# =========================================================================
# Hardening: codex plan-usage percentage bounds (Finding 9 / Convention 9)
# -------------------------------------------------------------------------
# The codex path now floors a fractional percent (69.9 -> 69) and clamps to <=100,
# mirroring the native rate-limit path. Non-numeric/negative stays a fail-closed
# drop of the whole segment.
# =========================================================================

@test "codex Plan-usage clamps a primary percent above 100 to 100" {
    local now
    now="$(date +%s)"
    _write_quota_state "$now" 101 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "7d:100%"
    refute_output --partial "7d:101%"
}

@test "codex Plan-usage floors a fractional primary percent and keeps the segment" {
    local now
    now="$(date +%s)"
    # 69.9 used to be dropped by the integer-only validator; it is now floored to 69.
    _write_quota_state "$now" 69.9 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "Plan usage:"
    assert_output --partial "7d:69%"
}

@test "codex Plan-usage drops the segment for a negative primary percent" {
    local now
    now="$(date +%s)"
    _write_quota_state "$now" -1 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    assert_output --partial "of 370k tokens"
}

@test "codex Plan-usage clamps a secondary percent above 100 to 100" {
    local now
    now="$(date +%s)"
    # secondary: 300 min -> "5h", percent 150 -> clamped to 100, reset 600s ahead.
    _write_quota_state "$now" 50 10080 402168 150 300 600
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "5h:100%"
    refute_output --partial "5h:150%"
}

# =========================================================================
# Hardening follow-up: C1 controls in the git branch name (Convention 1)
# -------------------------------------------------------------------------
# git refnames only forbid bytes < 0x20 and DEL, so a hostile repo can name a
# branch with a UTF-8-encoded C1 control (U+009B = 8-bit CSI on xterm-class
# terminals). Byte-wise tr [:cntrl:] passed it through to the display stream;
# the Unicode-aware jq strip removes it while keeping the printable remainder.
# =========================================================================

@test "UTF-8-encoded C1 in a git branch name is stripped from the display stream" {
    local repo="${SCRATCH_DIR}/c1-branch-repo"
    mkdir -p "$repo"
    git -C "$repo" -c init.defaultBranch=main init -q
    git -C "$repo" -c user.email=b@b -c user.name=b commit -q --allow-empty -m x
    git -C "$repo" checkout -q -b "$(printf 'br\302\233inj')"
    local payload
    printf -v payload '{"model":{"id":"claude-fable-5","display_name":"Fable 5"},"cwd":"%s","transcript_path":"","session_id":"%s","context_window":{"context_window_size":200000}}' \
        "$repo" "$FAKE_SESSION"
    run bash "$CONTEXT_BAR_SH" <<< "$payload"
    assert_success
    # C1 removed: the two halves of the branch name join; no raw c2 9b bytes.
    assert_output --partial "🔀brinj"
    refute_output --partial "$(printf '\302\233')"
}
