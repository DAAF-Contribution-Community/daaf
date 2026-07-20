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
# secondary_reset_s. The four non-numeric snapshot fields are fixed constants the
# reader ignores. Mirrors the shim's _write_quota_state output shape.
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
