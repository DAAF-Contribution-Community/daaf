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
    export CONTEXT_BAR_SH FAKE_SESSION SCRATCH_DIR MOCK_BIN
    export DAAF_CONTEXT_BAR_CACHE_DIR CTX_CACHE OR_CACHE
}

teardown() {
    rm -rf "$SCRATCH_DIR"
    common_teardown
}

_payload() {
    printf '{"model":{"id":"%s","display_name":"%s"},"cwd":"%s","transcript_path":"","session_id":"%s","context_window":{"context_window_size":200000}}' \
        "$1" "$1" "$TEST_DIR" "$FAKE_SESSION"
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
