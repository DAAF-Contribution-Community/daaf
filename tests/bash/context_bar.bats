#!/usr/bin/env bats
# ============================================================================
# Tests for context-bar.sh -- main statusline context-window resolution
# ============================================================================
# These tests are deterministic and network-independent. Static cases keep the
# OpenRouter branch disabled; dynamic cases prepend a fake curl executable that
# serves a controlled catalogue from project scratch. No live provider call is
# possible, and all catalogue, cache, health, and quota seams stay in project scratch.
# Synthetic health fixtures are local contract evidence only; they make no claim
# that either provider route accepts or serves a requested tier.
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
    DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE"
    HEALTH_FILE="${SCRATCH_DIR}/health.json"
    MOCK_CURL_LOG="${SCRATCH_DIR}/curl.log"
    mkdir -p "$MOCK_BIN" "$DAAF_CONTEXT_BAR_CACHE_DIR"
    cat > "${MOCK_BIN}/curl" <<'MOCK_CURL'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${MOCK_CURL_LOG:?MOCK_CURL_LOG must be set}"
url="${!#}"
case "$url" in
    https://openrouter.ai/api/v1/models)
        printf '{"data":[{"id":"z-ai/glm-5.2","context_length":%s}]}' \
            "${MOCK_OPENROUTER_CONTEXT:?MOCK_OPENROUTER_CONTEXT must be set}"
        ;;
    http://127.0.0.1:*/health)
        [[ "${MOCK_HEALTH_UNAVAILABLE:-0}" == "1" ]] && exit 22
        [[ -f "${MOCK_HEALTH_FILE:?MOCK_HEALTH_FILE must be set}" ]] || exit 22
        if [[ "${MOCK_HEALTH_REDIRECTED:-0}" == "1" ]]; then
            cat "$MOCK_HEALTH_FILE"
            exit 47
        fi
        if [[ "${MOCK_HEALTH_OVERSIZED:-0}" == "1" ]]; then
            printf '%17000s' x
            exit 63
        fi
        cat "$MOCK_HEALTH_FILE"
        ;;
    *)
        exit 97
        ;;
esac
MOCK_CURL
    chmod +x "${MOCK_BIN}/curl"
    PATH="${MOCK_BIN}:${PATH}"
    unset ANTHROPIC_BASE_URL
    unset CLAUDE_CODE_MAX_CONTEXT_TOKENS
    unset CLAUDE_CODE_DISABLE_FAST_MODE
    unset DAAF_PROVIDER_SHIM
    unset SHIM_BACKEND_MODE
    unset SHIM_PORT
    unset MOCK_HEALTH_UNAVAILABLE
    unset MOCK_HEALTH_REDIRECTED
    unset MOCK_HEALTH_OVERSIZED
    export CONTEXT_BAR_SH FAKE_SESSION SCRATCH_DIR MOCK_BIN PATH
    export DAAF_CONTEXT_BAR_CACHE_DIR CTX_CACHE MODEL_CACHE OR_CACHE QUOTA_STATE_FILE
    export DAAF_QUOTA_STATE_FILE
    export HEALTH_FILE MOCK_HEALTH_FILE="$HEALTH_FILE" MOCK_CURL_LOG
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

# Write the exact v1.3.9 gpt_service_tier /health contract. Args: route,
# policy status, policy backend (JSON scalar), enabled, effective,
# native_fast_disabled, latest_terminal (JSON value).
_write_gpt_health() {
    local vocabulary
    case "$1" in
        chatgpt|openai) vocabulary="priority" ;;
        *) fail "unsupported test route: $1" ;;
    esac
    printf '{"service":"daaf-anthropic-openai-shim","status":"ok","backend":"https://example.invalid","backend_mode":"%s","codex_home_present":true,"version":"1.3.9","sanitize_tools":true,"reasoning_effort":"high","text_verbosity":"medium","auth":{"state":"n/a"},"reasoning_cache":{"entries":0,"restored":0,"hits":0,"restored_hits":0},"prompt_cache":{"requests_with_usage":0,"requests_with_cached":0,"cached_tokens_total":0,"input_tokens_total":0},"gpt_service_tier":{"backend_mode":"%s","requested_tier_vocabulary":"%s","policy":{"status":"%s","backend_mode":%s,"enabled":%s,"effective":%s},"native_fast_disabled":%s,"latest_terminal":%s}}' \
        "$1" "$1" "$vocabulary" "$2" "$3" "$4" "$5" "$6" "$7" > "$HEALTH_FILE"
}

_refute_legacy_gpt_status_text() {
    refute_output --partial "GPT Fast req"
    refute_output --partial "GPT Priority req"
    refute_output --partial "req OFF"
    refute_output --partial "req unavailable"
    refute_output --partial "[global]"
    refute_output --partial "last global"
    refute_output --partial "served="
}

_assert_gpt_fast_on() {
    assert_output --partial $'\033[38;5;245mGPT Fast On\033[0m'
    _refute_legacy_gpt_status_text
}

_refute_gpt_fast_segment() {
    refute_output --partial "GPT Fast On"
    _refute_legacy_gpt_status_text
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

@test "setup pins every quota read to the per-test scratch seam" {
    [[ "$DAAF_QUOTA_STATE_FILE" == "$QUOTA_STATE_FILE" ]]
    [[ "$DAAF_QUOTA_STATE_FILE" == "${SCRATCH_DIR}/"* ]]
    run test ! -e "$DAAF_QUOTA_STATE_FILE"
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

@test "gpt-6-astra displays 1050k and caches the 1050000 physical window" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-6-astra")
    assert_success
    assert_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "gpt-6-astra[1m] displays 1050k and caches the 1050000 physical window" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-6-astra[1m]")
    assert_success
    assert_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "provider-prefixed gpt-6-astra maps to the 1,050,000 flagship window" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "openrouter/openai/gpt-6-astra" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

@test "gpt-6-astra near-misses do NOT get the 1.05M flagship window" {
    local model
    for model in gpt-6-astra-pro gpt-6-astra-mini 'gpt-6-astra[1m]-x' gpt-6-astrab gpt-6 gpt-6-luna; do
        run bash "$CONTEXT_BAR_SH" < <(_payload "$model")
        assert_success
        refute_output --partial "of 1050k tokens"
    done
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
# ChatGPT-subscription lane: final gpt-5.4/5.5/5.6 accounting cap is 919k
# -------------------------------------------------------------------------
# Canonical lane gate: DAAF_PROVIDER_SHIM=openai AND SHIM_BACKEND_MODE=chatgpt.
# The final min(resolved, 919000) constraint runs after payload, static-map,
# dynamic, and explicit-override resolution. Both exact lane values are required;
# malformed or partial signals keep the API/OpenRouter behavior fail-open.
# =========================================================================

@test "chatgpt lane: incoming 1,050,000 payload is finally capped and cached at 919,000" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 919k tokens"
    refute_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "919000"
}

@test "chatgpt lane: explicit 1,050,000 override cannot raise the final 919,000 cap" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 919k tokens"
    refute_output --partial "of 1050k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "919000"
}

@test "chatgpt lane: lower positive explicit override remains lower than the cap" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=333333 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 333k tokens"
    refute_output --partial "of 919k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "333333"
}

@test "API shim lane keeps the wider 1,050,000 flagship window" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "of 919k tokens"
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
    refute_output --partial "of 919k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

# =========================================================================
# GPT Fast ON-only indicator and bounded /health projection (v1.3.9)
# -------------------------------------------------------------------------
# The exact GPT routes query only the loopback health endpoint through the fake
# curl above. Tests prove the route-neutral ON label and silence for every other
# state; no running daemon, port 4141, proxy, or live provider is contacted.
# =========================================================================

@test "exact ChatGPT ON state renders only the route-neutral GPT Fast On segment" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "gpt-5.6-sol[1m]"
    _assert_gpt_fast_on
}

@test "exact OpenAI API ON state uses the same route-neutral GPT Fast On segment" {
    _write_gpt_health openai ok '"openai"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "gpt-5.6-sol[1m]"
    _assert_gpt_fast_on
}

@test "legacy requested fast vocabulary is silent on both exact GPT shim routes" {
    local route
    local canonical_health
    for route in chatgpt openai; do
        _write_gpt_health "$route" ok "\"${route}\"" true true true null
        canonical_health="$(<"$HEALTH_FILE")"
        printf '%s' "${canonical_health/\"requested_tier_vocabulary\":\"priority\"/\"requested_tier_vocabulary\":\"fast\"}" > "$HEALTH_FILE"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE="$route" \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done
}

@test "root health status must be the exact string ok" {
    local root_status
    local canonical_health
    local mutated_health
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    canonical_health="$(<"$HEALTH_FILE")"

    for root_status in '__missing__' '42' '"OK"' '" ok"' '"ok "' '"error"'; do
        if [[ "$root_status" == "__missing__" ]]; then
            mutated_health="${canonical_health/\"status\":\"ok\",/}"
        else
            mutated_health="${canonical_health/\"status\":\"ok\"/\"status\":${root_status}}"
        fi
        printf '%s' "$mutated_health" > "$HEALTH_FILE"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done
}

@test "root health version accepts plus and exact 1 and 64 character boundaries" {
    local canonical_health
    local mutated_health
    local version
    local version_64
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    canonical_health="$(<"$HEALTH_FILE")"
    version_64="$(printf 'a%.0s' {1..64})"

    # Positive control: the otherwise-canonical effective-ON document renders.
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on

    for version in 'a' '+' 'v1.3.9+fast' "$version_64"; do
        mutated_health="${canonical_health/\"version\":\"1.3.9\"/\"version\":\"${version}\"}"
        printf '%s' "$mutated_health" > "$HEALTH_FILE"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _assert_gpt_fast_on
    done
}

@test "root health version rejects slash empty and length 65 non-vacuously" {
    local canonical_health
    local mutated_health
    local version
    local version_65
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    canonical_health="$(<"$HEALTH_FILE")"
    version_65="$(printf 'a%.0s' {1..65})"

    # Positive control: each negative fixture below changes only root version.
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on

    for version in '/' '' "$version_65"; do
        mutated_health="${canonical_health/\"version\":\"1.3.9\"/\"version\":\"${version}\"}"
        printf '%s' "$mutated_health" > "$HEALTH_FILE"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done
}

@test "terminal model accepts exact 1 and 160 character boundaries and canonical punctuation" {
    local canonical_latest
    local latest
    local model
    local model_160
    canonical_latest='{"model":"gpt-5.6-sol","requested_service_tier":"priority","requested_source":"shim_global","served_service_tier":"default","completed_at":"2026-07-25T19:20:30Z"}'
    model_160="a$(printf -- '-%.0s' {1..159})"

    for model in 'a' 'a._:/-Z' "$model_160"; do
        latest="${canonical_latest/\"model\":\"gpt-5.6-sol\"/\"model\":\"${model}\"}"
        _write_gpt_health chatgpt ok '"chatgpt"' true true true "$latest"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _assert_gpt_fast_on
    done
}

@test "terminal model rejects empty length 161 leading hyphen and plus non-vacuously" {
    local canonical_latest
    local latest
    local model
    local model_161
    canonical_latest='{"model":"gpt-5.6-sol","requested_service_tier":"priority","requested_source":"shim_global","served_service_tier":"default","completed_at":"2026-07-25T19:20:30Z"}'
    model_161="a$(printf -- '-%.0s' {1..160})"
    _write_gpt_health chatgpt ok '"chatgpt"' true true true "$canonical_latest"

    # Positive control: each negative fixture below changes only latest_terminal.model.
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on

    for model in '' "$model_161" '-bad' 'a+bad'; do
        latest="${canonical_latest/\"model\":\"gpt-5.6-sol\"/\"model\":\"${model}\"}"
        _write_gpt_health chatgpt ok '"chatgpt"' true true true "$latest"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done
}

@test "duplicate health object members at any depth are rejected before jq semantics" {
    local canonical_health
    local fixture
    local -a fixtures
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    canonical_health="$(<"$HEALTH_FILE")"

    # Positive control: canonical ON survives the duplicate-rejecting prefilter.
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on

    fixtures=(
        "${canonical_health/\"status\":\"ok\"/\"status\":\"ok\",\"status\":\"ok\"}"
        "${canonical_health/\"status\":\"ok\"/\"status\":\"ok\",\"status\":\"error\"}"
        "${canonical_health/\"enabled\":true/\"enabled\":true,\"enabled\":true}"
        "${canonical_health/\"enabled\":true/\"enabled\":true,\"enabled\":false}"
        "${canonical_health/\"effective\":true/\"effective\":true,\"effective\":true}"
        "${canonical_health/\"effective\":true/\"effective\":true,\"effective\":false}"
        "${canonical_health/\"reasoning_cache\":{\"entries\":0/\"reasoning_cache\":{\"entries\":0,\"entries\":0}"
        "${canonical_health/\"reasoning_cache\":{\"entries\":0/\"reasoning_cache\":{\"entries\":0,\"entries\":1}"
        '{"service":"daaf-anthropic-openai-shim","status":"ok"'
    )
    for fixture in "${fixtures[@]}"; do
        printf '%s' "$fixture" > "$HEALTH_FILE"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
        refute_output --partial "duplicate object member"
        refute_output --partial "JSONDecodeError"
    done
}

@test "explicit OFF is silent on both exact GPT shim routes" {
    local route
    for route in chatgpt openai; do
        _write_gpt_health "$route" ok "\"${route}\"" false false true null
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE="$route" \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done
}

@test "missing reset invalid unreadable and unsafe policy states are silent" {
    local state
    for state in missing invalid unreadable unsafe; do
        _write_gpt_health chatgpt "$state" null false false true null
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done
}

@test "route mismatch and enabled-but-ineffective policy are silent" {
    _write_gpt_health chatgpt ok '"openai"' true false true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _refute_gpt_fast_segment

    _write_gpt_health chatgpt ok '"chatgpt"' true false true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _refute_gpt_fast_segment
}

@test "missing or incoherent native Fast disablement is silent" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _refute_gpt_fast_segment

    _write_gpt_health chatgpt ok '"chatgpt"' true true false null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _refute_gpt_fast_segment
}

@test "valid terminal history never appears even when the ON indicator renders" {
    local latest
    latest='{"model":"gpt-5.6-sol","requested_service_tier":"priority","requested_source":"shim_global","served_service_tier":"default","completed_at":"2026-07-25T19:20:30Z"}'
    _write_gpt_health openai ok '"openai"' true true true "$latest"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-terra[1m]" 1050000)
    assert_success
    assert_output --partial "gpt-5.6-terra[1m]"
    _assert_gpt_fast_on
    refute_output --partial "gpt-5.6-sol served"
    refute_output --partial "completed_at"
    refute_output --partial "requested=priority"
}

@test "compatibility terminal served fast permits ON without becoming requested vocabulary" {
    local latest
    latest='{"model":"gpt-5.6-sol","requested_service_tier":"priority","requested_source":"shim_global","served_service_tier":"fast","completed_at":"2026-07-25T19:20:30Z"}'
    _write_gpt_health chatgpt ok '"chatgpt"' true true true "$latest"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on
    refute_output --partial "requested=fast"
    refute_output --partial "served=fast"
}

@test "malformed semantic-invalid and extra-key nested health blocks are silent non-vacuously" {
    local fixture
    local prefix
    local canonical_nested
    prefix='{"service":"daaf-anthropic-openai-shim","status":"ok","version":"1.3.9","backend_mode":"chatgpt","gpt_service_tier":'
    canonical_nested='{"backend_mode":"chatgpt","requested_tier_vocabulary":"priority","policy":{"status":"ok","backend_mode":"chatgpt","enabled":true,"effective":true},"native_fast_disabled":true,"latest_terminal":null}'

    # Control: the same manually constructed root and a canonical nested block
    # reach the literal ON projection, so each loop case fails only at its nested defect.
    printf '%s%s}' "$prefix" "$canonical_nested" > "$HEALTH_FILE"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on

    for fixture in \
        '[' \
        '{"backend_mode":"chatgpt","requested_tier_vocabulary":"priority","policy":{"status":"ok","backend_mode":"chatgpt","enabled":true,"effective":true},"native_fast_disabled":true,"latest_terminal":null,"extra":"forbidden"}' \
        '{"backend_mode":"chatgpt","requested_tier_vocabulary":"priority","policy":{"status":"ok","backend_mode":"chatgpt","enabled":false,"effective":true},"native_fast_disabled":true,"latest_terminal":null}' \
        '{"backend_mode":"chatgpt","requested_tier_vocabulary":"priority","policy":{"status":"ok","backend_mode":"chatgpt","enabled":true,"effective":true},"native_fast_disabled":true,"latest_terminal":{"model":"gpt-5.6-sol","requested_service_tier":"priority","requested_source":"shim_global","served_service_tier":"fast","completed_at":"2026-07-25T19:20:30Z","extra":1}}'; do
        printf '%s%s}' "$prefix" "$fixture" > "$HEALTH_FILE"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        assert_output --partial "gpt-5.6-sol"
        _refute_gpt_fast_segment
        refute_output --partial "extra"
    done
}

@test "invalid terminal history keeps strict health validation and is silent" {
    local latest
    local requested
    local source
    local served
    local completed
    local case_spec
    for case_spec in \
        'fast|shim_global|default|2026-07-25T19:20:30Z' \
        ' priority|shim_global|default|2026-07-25T19:20:30Z' \
        'priority|Shim_Global|default|2026-07-25T19:20:30Z' \
        'priority| shim_global|default|2026-07-25T19:20:30Z' \
        'priority|shim_global|FAST|2026-07-25T19:20:30Z' \
        'priority|shim_global|fast |2026-07-25T19:20:30Z' \
        'priority|shim_global|default|2026-02-30T19:20:30Z'; do
        IFS='|' read -r requested source served completed <<< "$case_spec"
        latest=$(printf '{"model":"gpt-5.6-sol","requested_service_tier":"%s","requested_source":"%s","served_service_tier":"%s","completed_at":"%s"}' \
            "$requested" "$source" "$served" "$completed")
        _write_gpt_health chatgpt ok '"chatgpt"' true true true "$latest"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
        assert_success
        _refute_gpt_fast_segment
    done

    latest='{"model":"gpt-5.6-sol","requested_service_tier":null,"requested_source":"shim_global","served_service_tier":null,"completed_at":"2026-07-25T19:20:30Z"}'
    _write_gpt_health chatgpt ok '"chatgpt"' true true true "$latest"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _refute_gpt_fast_segment
}

@test "coherent null terminal history permits ON without rendering history" {
    local latest
    latest='{"model":"gpt-5.6-sol","requested_service_tier":null,"requested_source":"none","served_service_tier":null,"completed_at":"2026-07-25T19:20:30Z"}'
    _write_gpt_health chatgpt ok '"chatgpt"' true true true "$latest"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on
}

@test "unavailable oversized and redirected health are silent while the bar remains intact" {
    local failure_var
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    for failure_var in MOCK_HEALTH_UNAVAILABLE MOCK_HEALTH_OVERSIZED MOCK_HEALTH_REDIRECTED; do
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 "${failure_var}=1" \
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
        assert_success
        assert_output --partial "gpt-5.6-sol[1m]"
        assert_output --partial "of 919k tokens"
        _refute_gpt_fast_segment
    done
}

@test "missing curl jq or duplicate parser is silent and confined to scratch seams" {
    local bindir="${SCRATCH_DIR}/missing-tool-bin"
    local unsafe_session="-missing-tools-invalid-session"
    local unsafe_payload
    local isolated_quota="${SCRATCH_DIR}/guaranteed-missing-quota-state.json"
    unsafe_payload=$(printf '{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"cwd":"%s","transcript_path":"","session_id":"%s","context_window":{"context_window_size":200000}}' \
        "$TEST_DIR" "$unsafe_session")
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    ln -s "$(command -v basename)" "${bindir}/basename"
    ln -s "$(command -v jq)" "${bindir}/jq"
    ln -s "$(command -v python3)" "${bindir}/python3"
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run test ! -e "$isolated_quota"
    assert_success

    # Missing curl only.
    run env -i PATH="$bindir" \
        DAAF_CONTEXT_BAR_CACHE_DIR="$DAAF_CONTEXT_BAR_CACHE_DIR" \
        DAAF_QUOTA_STATE_FILE="$isolated_quota" \
        DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" <<< "$unsafe_payload"
    assert_success
    _refute_gpt_fast_segment
    refute_output --partial "Plan usage:"
    run test ! -e "$isolated_quota"
    assert_success
    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""

    # Missing jq only.
    rm -f "${bindir}/jq"
    ln -s "${MOCK_BIN}/curl" "${bindir}/curl"
    run env -i PATH="$bindir" \
        DAAF_CONTEXT_BAR_CACHE_DIR="$DAAF_CONTEXT_BAR_CACHE_DIR" \
        DAAF_QUOTA_STATE_FILE="$isolated_quota" \
        DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        MOCK_CURL_LOG="$MOCK_CURL_LOG" MOCK_HEALTH_FILE="$HEALTH_FILE" \
        bash "$CONTEXT_BAR_SH" <<< "$unsafe_payload"
    assert_success
    _refute_gpt_fast_segment
    refute_output --partial "Plan usage:"
    run test ! -e "$isolated_quota"
    assert_success
    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""

    # Missing duplicate-rejecting parser only.
    ln -s "$(command -v jq)" "${bindir}/jq"
    rm -f "${bindir}/python3"
    run env -i PATH="$bindir" \
        DAAF_CONTEXT_BAR_CACHE_DIR="$DAAF_CONTEXT_BAR_CACHE_DIR" \
        DAAF_QUOTA_STATE_FILE="$isolated_quota" \
        DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        MOCK_CURL_LOG="$MOCK_CURL_LOG" MOCK_HEALTH_FILE="$HEALTH_FILE" \
        bash "$CONTEXT_BAR_SH" <<< "$unsafe_payload"
    assert_success
    _refute_gpt_fast_segment
    refute_output --partial "Plan usage:"
    run test ! -e "$isolated_quota"
    assert_success
    run find "$DAAF_CONTEXT_BAR_CACHE_DIR" -mindepth 1 -maxdepth 1 -print
    assert_success
    assert_output ""
}

@test "health probe disables ambient curl config first and keeps all bounded transport controls" {
    _write_gpt_health openai ok '"openai"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 SHIM_PORT=' 4141 ' \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    _assert_gpt_fast_on

    run cat "$MOCK_CURL_LOG"
    assert_success
    [[ "$output" == "-q "* ]]
    assert_output --partial "-q --fail"
    assert_output --partial "--location"
    assert_output --partial "--max-redirs 0"
    assert_output --partial "--noproxy *"
    assert_output --partial "--proxy"
    assert_output --partial "--connect-timeout 0.2"
    assert_output --partial "--max-time 0.6"
    assert_output --partial "--max-filesize 16384"
    assert_output --partial "http://127.0.0.1:4141/health"
}

@test "anchored GPT indicator classification rejects near-miss model IDs without probing health" {
    local model
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    for model in vendor/notgpt-5.6-sol xgpt-5.6-sol foo-gpt-5.6-sol; do
        rm -f "$MOCK_CURL_LOG"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" < <(_payload "$model")
        assert_success
        assert_output --partial "$model"
        _refute_gpt_fast_segment
        run test ! -e "$MOCK_CURL_LOG"
        assert_success
    done
}

@test "provider-prefixed terminal GPT slug remains eligible for the ON indicator" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "openrouter/openai/gpt-5.6-sol" 1050000)
    assert_success
    assert_output --partial "openrouter/openai/gpt-5.6-sol"
    _assert_gpt_fast_on
}

@test "bounded display-name fallback remains eligible only when model id is absent" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" <<JSON
{"model":{"display_name":"gpt-5.6-sol[1m]#xhigh[1m]"},"cwd":"$TEST_DIR","transcript_path":"","session_id":"$FAKE_SESSION","context_window":{"context_window_size":200000}}
JSON
    assert_success
    assert_output --partial "gpt-5.6-sol[1m]"
    _assert_gpt_fast_on

    rm -f "$MOCK_CURL_LOG"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" <<JSON
{"model":{"id":"claude-fable-5","display_name":"gpt-5.6-sol"},"cwd":"$TEST_DIR","transcript_path":"","session_id":"$FAKE_SESSION","context_window":{"context_window_size":200000}}
JSON
    assert_success
    _refute_gpt_fast_segment
    run test ! -e "$MOCK_CURL_LOG"
    assert_success
}

@test "present invalid model ids cannot unlock GPT display-name fallback" {
    local oversized_id
    local payload
    local json_escape='\'
    local -a payloads
    oversized_id="gpt-$(printf 'a%.0s' {1..157})"
    payloads=(
        '{"model":{"id":42,"display_name":"gpt-5.6-sol"},"session_id":"bats-invalid-id-number","context_window":{"context_window_size":200000}}'
        '{"model":{"id":{"value":"gpt-5.6-sol"},"display_name":"gpt-5.6-sol"},"session_id":"bats-invalid-id-object","context_window":{"context_window_size":200000}}'
        '{"model":{"id":["gpt-5.6-sol"],"display_name":"gpt-5.6-sol"},"session_id":"bats-invalid-id-array","context_window":{"context_window_size":200000}}'
        "{\"model\":{\"id\":\"bad${json_escape}u001fgpt-5.6-sol\",\"display_name\":\"gpt-5.6-sol\"},\"session_id\":\"bats-invalid-id-control\",\"context_window\":{\"context_window_size\":200000}}"
        "{\"model\":{\"id\":\"${oversized_id}\",\"display_name\":\"gpt-5.6-sol\"},\"session_id\":\"bats-invalid-id-oversized\",\"context_window\":{\"context_window_size\":200000}}"
    )
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null

    for payload in "${payloads[@]}"; do
        rm -f "$MOCK_CURL_LOG"
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            CLAUDE_CODE_DISABLE_FAST_MODE=1 \
            bash "$CONTEXT_BAR_SH" <<< "$payload"
        assert_success
        assert_output --partial "gpt-5.6-sol"
        _refute_gpt_fast_segment
        run test ! -e "$MOCK_CURL_LOG"
        assert_success
    done
}

@test "exact shim route plus a non-GPT model is silent and skips the health probe" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "claude-fable-5" 1000000)
    assert_success
    assert_output --partial "claude-fable-5"
    _refute_gpt_fast_segment
    run test ! -e "$MOCK_CURL_LOG"
    assert_success
}

@test "Anthropic and OpenRouter non-GPT route fixtures remain byte-for-byte unchanged" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "claude-fable-5" 1000000)
    assert_success
    local anthropic_baseline="$output"
    run env DAAF_PROVIDER_SHIM=anthropic SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "claude-fable-5" 1000000)
    assert_success
    [[ "$output" == "$anthropic_baseline" ]]
    _refute_gpt_fast_segment

    rm -f "$OR_CACHE" "$MOCK_CURL_LOG"
    run env ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
        MOCK_OPENROUTER_CONTEXT=1048576 \
        bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
    assert_success
    local openrouter_baseline="$output"
    rm -f "$OR_CACHE" "$MOCK_CURL_LOG"
    run env ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
        DAAF_PROVIDER_SHIM=openrouter SHIM_BACKEND_MODE=openai \
        MOCK_OPENROUTER_CONTEXT=1048576 \
        bash "$CONTEXT_BAR_SH" < <(_payload "z-ai/glm-5.2")
    assert_success
    [[ "$output" == "$openrouter_baseline" ]]
    _refute_gpt_fast_segment

    run cat "$MOCK_CURL_LOG"
    assert_success
    assert_output --partial "https://openrouter.ai/api/v1/models"
    refute_output --partial "127.0.0.1"
}

@test "each missing shim-route signal leaves the GPT Fast segment silent" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env SHIM_BACKEND_MODE=chatgpt CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    _refute_gpt_fast_segment

    run env DAAF_PROVIDER_SHIM=openai CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    _refute_gpt_fast_segment
}

@test "non-shim malformed and noncanonical route values leave the GPT Fast segment silent" {
    _write_gpt_health chatgpt ok '"chatgpt"' true true true null
    run env DAAF_PROVIDER_SHIM=OpenAI SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    _refute_gpt_fast_segment

    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=' chatgpt ' \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    _refute_gpt_fast_segment

    run env DAAF_PROVIDER_SHIM=openrouter SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol[1m]" 1050000)
    assert_success
    assert_output --partial "of 1050k tokens"
    _refute_gpt_fast_segment
}

@test "chatgpt lane does not perturb a non-GPT (Claude) model window" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=1050000 \
        bash "$CONTEXT_BAR_SH" < <(_payload "claude-fable-5" 1000000)
    assert_success
    assert_output --partial "of 1050k tokens"
    refute_output --partial "of 919k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "1050000"
}

# =========================================================================
# Canonical positive-decimal override contract
# =========================================================================

@test "canonical override 919000 is accepted on the API lane" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_MAX_CONTEXT_TOKENS=919000 \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol" 1050000)
    assert_success
    assert_output --partial "of 919k tokens"
    run cat "$CTX_CACHE"
    assert_success
    assert_output "919000"
}

@test "invalid decimal overrides are ignored without arithmetic diagnostics and the exact-lane cap still applies" {
    local value
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
            bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol" 1050000)
        assert_success
        assert_output --partial "of 919k tokens"
        refute_output --partial "value too great"
        refute_output --partial "syntax error"
        run cat "$CTX_CACHE"
        assert_success
        assert_output "919000"
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

# -------------------------------------------------------------------------
# O1: anchored mini/chat grammar (byte-consistent with subagent-bar.sh).
# The old inner globs (*-mini*/*-chat*) matched any id containing -mini/-chat
# and mapped it to 400k/128k; the anchored gpt_mini_re/gpt_chat_re reject a
# trailing suffix so suffixed near-misses fall through to the 200k default.
# -------------------------------------------------------------------------
@test "anchored mini/chat grammar rejects suffixed near-misses the old inner globs accepted (O1)" {
    local model
    for model in \
        gpt-5.6-mini-preview \
        gpt-5.6-sol-mini-preview \
        'gpt-5.6-mini[1m]x' \
        gpt-5.6-chat-preview \
        gpt-5.6-sol-chat-beta \
        'gpt-5.6-chat[1m]x'; do
        run bash "$CONTEXT_BAR_SH" < <(_payload "$model")
        assert_success
        assert_output --partial "of 200k tokens"
        refute_output --partial "of 400k tokens"
        refute_output --partial "of 128k tokens"
    done
}

@test "well-formed mini/chat slugs still map to 400k/128k under the anchored grammar (O1)" {
    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-mini")
    assert_success
    assert_output --partial "of 400k tokens"

    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol-mini[1m]")
    assert_success
    assert_output --partial "of 400k tokens"

    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-chat")
    assert_success
    assert_output --partial "of 128k tokens"

    run bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol-chat[1m]")
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

# -------------------------------------------------------------------------
# O3: the transcript token-sum jq must suppress stderr (idiom parity with the
# ctx-window write at the sibling site). A corrupt transcript makes jq emit a
# parse error; without 2>/dev/null it leaks into the statusline display stream.
# The value path stays fail-open (// 0 + canonical-decimal guard), so the bar
# still renders against the resolved window.
# -------------------------------------------------------------------------
@test "corrupt transcript does not leak jq parse errors into the display stream (O3)" {
    local bad_transcript="${SCRATCH_DIR}/corrupt.jsonl"
    printf '%s\n' '{"message":{"usage":{"input_tokens":123}' '<<<not json>>>' > "$bad_transcript"
    run bash "$CONTEXT_BAR_SH" <<JSON
{"model":{"id":"gpt-5.6-sol","display_name":"gpt-5.6-sol"},"cwd":"$TEST_DIR","transcript_path":"$bad_transcript","session_id":"$FAKE_SESSION","context_window":{"context_window_size":1050000}}
JSON
    assert_success
    refute_output --partial "parse error"
    refute_output --partial "jq:"
    assert_output --partial "of 1050k tokens"
}

@test "chatgpt final-cap predicate accepts anchored provider slugs and rejects adversarial near misses" {
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        bash "$CONTEXT_BAR_SH" < <(_payload "openrouter/openai/gpt-5.6-terra[1m]" 1050000)
    assert_success
    assert_output --partial "of 919k tokens"

    local model
    for model in vendor/notgpt-5.6-sol xgpt-5.6-sol foo-gpt-5.6-sol gpt-5.60 gpt-5.60-sol; do
        run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
            bash "$CONTEXT_BAR_SH" < <(_payload "$model" 1050000)
        assert_success
        assert_output --partial "of 1050k tokens"
        refute_output --partial "of 919k tokens"
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
    # Rest of the bar is intact (chatgpt lane caps gpt-5.6-sol at 919k).
    assert_output --partial "of 919k tokens"
}

@test "codex Plan-usage is absent on malformed state JSON and the bar stays intact" {
    printf '{"captured_at":' > "$QUOTA_STATE_FILE"
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    assert_output --partial "of 919k tokens"
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
    # Rest of the bar is intact (chatgpt lane caps gpt-5.6-sol at 919k).
    assert_output --partial "of 919k tokens"
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
        refute_output --partial "of 919k tokens"
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
# drop of the whole segment. v1.3.2 (deferred obs. O2): the fractional-floor strip is
# gated on ^[0-9]+\.[0-9]+$, so an exponent-notation value carrying a dot ("1.0e999")
# is NOT stripped to "1" — it stays intact, fails the validator, and drops.
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

@test "codex Plan-usage drops the segment when primary percent is exponent notation" {
    local now
    now="$(date +%s)"
    # O2: "1.0e999" carries a dot but is NOT a plain fractional. The gated strip leaves
    # it intact, is_canonical_nonneg_decimal rejects it, and the whole segment drops —
    # it must never be floored to "1" and render "7d:1%".
    _write_quota_state "$now" 1.0e999 10080 402168 0 0 0
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    refute_output --partial "Plan usage:"
    refute_output --partial "7d:1%"
    assert_output --partial "of 919k tokens"
}

@test "codex Plan-usage drops only the secondary when its percent is exponent notation" {
    local now
    now="$(date +%s)"
    # Primary is a clean integer and renders; the secondary percent "2.0e9" is left
    # intact by the gated strip, fails the validator, and the secondary is omitted
    # (never floored to "2").
    _write_quota_state "$now" 73 10080 402168 2.0e9 300 600
    run env DAAF_PROVIDER_SHIM=openai SHIM_BACKEND_MODE=chatgpt \
        DAAF_QUOTA_STATE_FILE="$QUOTA_STATE_FILE" \
        bash "$CONTEXT_BAR_SH" < <(_payload "gpt-5.6-sol")
    assert_success
    assert_output --partial "7d:73%"
    refute_output --partial "5h:"
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
    assert_output --partial "of 919k tokens"
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
