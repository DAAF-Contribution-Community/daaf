#!/usr/bin/env bats

setup() {
    export GPT_FAST_SH="/daaf/scripts/provider_shim/gpt_fast.sh"
    export TEST_ROOT="/daaf/scripts/scratch/gpt-fast-bats-${BATS_TEST_NUMBER}-$$"
    mkdir -p "$TEST_ROOT"
    chmod 700 "$TEST_ROOT"
}

teardown() {
    if [ -e "$TEST_ROOT" ]; then
        find "$TEST_ROOT" -depth -delete
    fi
}

@test "wrapper rejects missing arguments" {
    run bash "$GPT_FAST_SH"
    [ "$status" -eq 20 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "wrapper resolves its checked-in controller through a symlink" {
    ln -s "$GPT_FAST_SH" "$TEST_ROOT/gpt-fast-link.sh"
    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=chatgpt \
        SHIM_PORT=1 \
        bash "$TEST_ROOT/gpt-fast-link.sh" status
    [ "$status" -eq 0 ]
    [[ "$output" == *"Route: ChatGPT subscription"* ]]
}

@test "wrapper rejects unknown and extra arguments" {
    run bash "$GPT_FAST_SH" enable
    [ "$status" -eq 20 ]
    [[ "$output" == *"use exactly one of"* ]]

    run bash "$GPT_FAST_SH" on extra
    [ "$status" -eq 20 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "on requires exact native Fast disable and leaves explicit OFF unchanged" {
    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=chatgpt \
        bash "$GPT_FAST_SH" off
    [ "$status" -eq 0 ]
    before="$(sha256sum "$TEST_ROOT/.claude/provider_shim/gpt_fast_policy.json")"

    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=true \
        bash "$GPT_FAST_SH" on
    [ "$status" -eq 20 ]
    [[ "$output" == *"CLAUDE_CODE_DISABLE_FAST_MODE=1"* ]]
    after="$(sha256sum "$TEST_ROOT/.claude/provider_shim/gpt_fast_policy.json")"
    [ "$after" = "$before" ]
}

@test "ChatGPT on and off persist exact route-bound booleans" {
    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=chatgpt \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$GPT_FAST_SH" on
    [ "$status" -eq 0 ]
    [[ "$output" == *"Requested Fast service is ON"* ]]
    [[ "$output" == *"service_tier='priority'"* ]]
    [[ "$output" != *"Priority Processing can change API cost"* ]]
    run grep -Fx '{"version":1,"backend_mode":"chatgpt","enabled":true}' \
        "$TEST_ROOT/.claude/provider_shim/gpt_fast_policy.json"
    [ "$status" -eq 0 ]

    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=chatgpt \
        bash "$GPT_FAST_SH" off
    [ "$status" -eq 0 ]
    run grep -Fx '{"version":1,"backend_mode":"chatgpt","enabled":false}' \
        "$TEST_ROOT/.claude/provider_shim/gpt_fast_policy.json"
    [ "$status" -eq 0 ]
}

@test "OpenAI API on prints non-interactive Priority cost warning" {
    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=openai \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$GPT_FAST_SH" on
    [ "$status" -eq 0 ]
    [[ "$output" == *"Priority Processing can change API cost"* ]]
    [[ "$output" == *"Requested Priority service is ON"* ]]
    [[ "$output" == *"service_tier='priority'"* ]]
}

@test "status remains available and never claims requested means served" {
    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=openai \
        SHIM_PORT=1 \
        bash "$GPT_FAST_SH" status
    [ "$status" -eq 0 ]
    [[ "$output" == *"Persisted requested policy:"* ]]
    [[ "$output" == *"Shim: unavailable"* ]]
    [[ "$output" == *"Latest terminal: unknown"* ]]
    [[ "$output" == *"requested Priority service is not proof"* ]]
}

@test "malformed route variables reject mutation" {
    run env \
        HOME="$TEST_ROOT" \
        DAAF_PROVIDER_SHIM=openai \
        SHIM_BACKEND_MODE=OPENAI \
        CLAUDE_CODE_DISABLE_FAST_MODE=1 \
        bash "$GPT_FAST_SH" on
    [ "$status" -eq 20 ]
    [[ "$output" == *"SHIM_BACKEND_MODE must be exactly"* ]]
    [ ! -e "$TEST_ROOT/.claude/provider_shim/gpt_fast_policy.json" ]
}
