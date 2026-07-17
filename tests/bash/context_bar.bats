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
    OR_CACHE="${DAAF_CONTEXT_BAR_CACHE_DIR}/claude-or-models-${FAKE_SESSION}"
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
    export DAAF_CONTEXT_BAR_CACHE_DIR CTX_CACHE OR_CACHE
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
