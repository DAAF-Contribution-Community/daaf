#!/usr/bin/env bats
# ============================================================================
# Tests for remind-orchestrator.sh -- first-prompt orchestrator reminder
# ============================================================================
# The protected deployed hook is not edited by automation. SCRIPT UNDER TEST is
# parameterized so this suite can validate the workspace draft before a user
# copies it into .claude/hooks/:
#   REMIND_ORCHESTRATOR_SH=/path/to/draft/remind-orchestrator.sh \
#     bats tests/bash/remind_orchestrator.bats
# ============================================================================

load 'test_helper'

REMIND_ORCHESTRATOR_SH="${REMIND_ORCHESTRATOR_SH:-${REPO_ROOT}/.claude/hooks/remind-orchestrator.sh}"
CONTEXT_BAR_SH="${CONTEXT_BAR_SH:-${REPO_ROOT}/.claude/scripts/context-bar.sh}"
FAKE_SESSION="bats-remind-orchestrator-session"
ORDINARY_REMINDER='You are interacting with a human user. You MUST IMMEDIATELY invoke the daaf-orchestrator skill'
# GPT-gated collaborator guidance was removed from the hook in 7defcc8
# (superseded by the model-agnostic Turn-End Briefing standard). The marker is
# retained only as a regression guard: no session model may re-enable it.
GUIDANCE_MARKER='For this GPT session, treat the user as an equal stakeholder and thoughtful collaborator'

setup() {
    common_setup
    TEST_HOME="${TEST_DIR}/home"
    PROJECT_DIR="${TEST_DIR}/project"
    MODEL_CACHE_DIR="${TEST_DIR}/model-cache"
    STATE_DIR="${TEST_HOME}/.claude/daaf-state"
    ACTIVITY_LOG="${PROJECT_DIR}/.claude/logs/activity.log"
    TRANSPARENCY_FILE="${REPO_ROOT}/.claude/hooks/first-run-transparency.txt"
    mkdir -p "$STATE_DIR" "$(dirname "$ACTIVITY_LOG")" "$MODEL_CACHE_DIR"
    printf 'session-one\nsession-two\n' > "$ACTIVITY_LOG"
    export REMIND_ORCHESTRATOR_SH CONTEXT_BAR_SH FAKE_SESSION TEST_HOME PROJECT_DIR
    export MODEL_CACHE_DIR STATE_DIR ACTIVITY_LOG TRANSPARENCY_FILE
    export ORDINARY_REMINDER GUIDANCE_MARKER
}

teardown() {
    common_teardown
}

_payload_main() {
    printf '{"hook_event_name":"UserPromptSubmit","session_id":"%s"}' "$FAKE_SESSION"
}

_payload_agent_id() {
    printf '{"hook_event_name":"UserPromptSubmit","session_id":"%s","agent_id":"agent-123","agent_type":"general-purpose"}' "$FAKE_SESSION"
}

_payload_agent_type() {
    printf '{"hook_event_name":"UserPromptSubmit","session_id":"%s","agent_type":"%s"}' "$FAKE_SESSION" "$1"
}

_seed_model() {
    printf '%s' "$1" > "${MODEL_CACHE_DIR}/claude-model-${FAKE_SESSION}"
}

_run_hook() {
    run env \
        HOME="$TEST_HOME" \
        CLAUDE_PROJECT_DIR="$PROJECT_DIR" \
        DAAF_REMIND_MODEL_CACHE_DIR="$MODEL_CACHE_DIR" \
        DAAF_REMIND_TRANSPARENCY_FILE="$TRANSPARENCY_FILE" \
        bash "$REMIND_ORCHESTRATOR_SH"
}

@test "remind-orchestrator.sh draft parses without errors" {
    run bash -n "$REMIND_ORCHESTRATOR_SH"
    assert_success
}

@test "terminal GPT session models receive the ordinary reminder and no removed guidance" {
    local model
    for model in gpt-5.6-sol 'gpt-5.6-sol[1m]' gpt-5.6-terra gpt-5.5 \
        openai/gpt-5.6-sol 'openrouter/openai/gpt-5.6-terra[1m]'; do
        _seed_model "$model"
        _run_hook < <(_payload_main)
        assert_success
        assert_output --partial "$ORDINARY_REMINDER"
        refute_output --partial "$GUIDANCE_MARKER"
    done
}

@test "statusline model-cache writer feeds the first-prompt path end to end without guidance" {
    run env DAAF_CONTEXT_BAR_CACHE_DIR="$MODEL_CACHE_DIR" \
        bash "$CONTEXT_BAR_SH" <<JSON
{"model":{"id":"openrouter/openai/gpt-5.6-terra[1m]","display_name":"gpt-5.6-terra[1m]"},"cwd":"$PROJECT_DIR","transcript_path":"","session_id":"$FAKE_SESSION","context_window":{"context_window_size":1050000}}
JSON
    assert_success

    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "malformed left-boundary lookalikes keep ordinary reminder but receive no guidance" {
    local model
    for model in xgpt-5.6-sol notgpt-5.6-sol foo-gpt-5.6-sol vendor/notgpt-5.6-sol vendor/foo-gpt-5.6-sol; do
        _seed_model "$model"
        _run_hook < <(_payload_main)
        assert_success
        assert_output --partial "$ORDINARY_REMINDER"
        refute_output --partial "$GUIDANCE_MARKER"
    done
}

@test "Claude Fable keeps ordinary reminder but receives no GPT guidance" {
    _seed_model 'claude-fable-5[1m]'
    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "missing model cache preserves ordinary reminder with no GPT guidance" {
    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "empty model cache preserves ordinary reminder with no GPT guidance" {
    : > "${MODEL_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "malformed cache content does not enable GPT-specific guidance" {
    printf 'gpt-5.6-sol\ntrailing-data' > "${MODEL_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "trailing newline in the model cache makes identity ineligible" {
    printf 'gpt-5.6-sol\n' > "${MODEL_CACHE_DIR}/claude-model-${FAKE_SESSION}"
    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "malformed input cannot read a seeded shared default model cache" {
    printf '%s' 'gpt-5.6-sol' > "${MODEL_CACHE_DIR}/claude-model-default"
    _run_hook <<< 'not-json {{{'
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "missing null and empty session ids cannot read a seeded shared default model cache" {
    local payload
    printf '%s' 'gpt-5.6-sol' > "${MODEL_CACHE_DIR}/claude-model-default"
    for payload in \
        '{"hook_event_name":"UserPromptSubmit"}' \
        '{"hook_event_name":"UserPromptSubmit","session_id":null}' \
        '{"hook_event_name":"UserPromptSubmit","session_id":""}'; do
        _run_hook <<< "$payload"
        assert_success
        assert_output --partial "$ORDINARY_REMINDER"
        refute_output --partial "$GUIDANCE_MARKER"
    done
}

@test "newline NUL and unit-separator session identities cannot read seeded alias caches" {
    local payload
    printf '%s' 'gpt-5.6-sol' > "${MODEL_CACHE_DIR}/claude-model-safe"
    printf '%s' 'gpt-5.6-sol' > "${MODEL_CACHE_DIR}/claude-model-victim"
    touch "${STATE_DIR}/orchestrator-loaded-safe" "${STATE_DIR}/orchestrator-loaded-victim"

    for payload in \
        '{"hook_event_name":"UserPromptSubmit","session_id":"safe\nid"}' \
        '{"hook_event_name":"UserPromptSubmit","session_id":"safe\n"}'; do
        _run_hook <<< "$payload"
        assert_success
        assert_output --partial "$ORDINARY_REMINDER"
        refute_output --partial "$GUIDANCE_MARKER"
    done

    printf -v payload '{"hook_event_name":"UserPromptSubmit","session_id":"victim\\u%04x"}' 0
    _run_hook <<< "$payload"
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"

    printf -v payload '{"hook_event_name":"UserPromptSubmit","session_id":"victim\\u%04xgpt-5.6-sol"}' 31
    _run_hook <<< "$payload"
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "malformed nonempty caller identity is silent and cannot enable GPT guidance" {
    local payload
    _seed_model 'gpt-5.6-sol'

    for payload in \
        '{"hook_event_name":"UserPromptSubmit","session_id":"bats-remind-orchestrator-session","agent_id":"agent\nnormalized"}' \
        '{"hook_event_name":"UserPromptSubmit","session_id":"bats-remind-orchestrator-session","agent_id":{"id":"agent-123"}}' \
        '{"hook_event_name":"UserPromptSubmit","session_id":"bats-remind-orchestrator-session","agent_type":"orchestrator\nsubagent"}' \
        '{"hook_event_name":"UserPromptSubmit","session_id":"bats-remind-orchestrator-session","agent_type":42}'; do
        _run_hook <<< "$payload"
        assert_success
        assert_output ""
    done
}

@test "explicit empty caller identity remains eligible for the ordinary reminder" {
    _seed_model 'gpt-5.6-sol'
    _run_hook <<JSON
{"hook_event_name":"UserPromptSubmit","session_id":"$FAKE_SESSION","agent_id":"","agent_type":""}
JSON
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "payload with agent_id is explicitly ignored" {
    _seed_model 'gpt-5.6-sol'
    _run_hook < <(_payload_agent_id)
    assert_success
    assert_output ""
}

@test "explicit non-orchestrator agent_type is ignored even without agent_id" {
    _seed_model 'gpt-5.6-sol'
    _run_hook < <(_payload_agent_type 'research-executor')
    assert_success
    assert_output ""
}

@test "positive orchestrator agent_type remains eligible for the ordinary reminder" {
    _seed_model 'openai/gpt-5.6-terra'
    _run_hook < <(_payload_agent_type 'orchestrator')
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "existing persistent loaded flag suppresses every reminder" {
    _seed_model 'gpt-5.6-sol'
    touch "${STATE_DIR}/orchestrator-loaded-${FAKE_SESSION}"
    _run_hook < <(_payload_main)
    assert_success
    assert_output ""
}

@test "first-run transparency still appears alongside the ordinary reminder" {
    printf 'first-session\n' > "$ACTIVITY_LOG"
    _seed_model 'gpt-5.6-sol'
    _run_hook < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
    assert_output --partial 'FIRST-TIME USER DETECTED: ONBOARDING PROCESS TRIGGERED.'
    assert_output --partial 'KEY POINTS TO COVER:'
}

@test "missing jq cannot read a seeded shared default cache and remains fail-open" {
    local bindir="${TEST_DIR}/nojq-bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    ln -s "$(command -v wc)" "${bindir}/wc"
    ln -s "$(command -v tr)" "${bindir}/tr"
    printf '%s' 'gpt-5.6-sol' > "${MODEL_CACHE_DIR}/claude-model-default"

    run env -i \
        PATH="$bindir" \
        HOME="$TEST_HOME" \
        CLAUDE_PROJECT_DIR="$PROJECT_DIR" \
        DAAF_REMIND_MODEL_CACHE_DIR="$MODEL_CACHE_DIR" \
        bash "$REMIND_ORCHESTRATOR_SH" < <(_payload_main)
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}

@test "unsafe session id cannot select a model cache but ordinary reminder survives" {
    printf '%s' 'gpt-5.6-sol' > "${MODEL_CACHE_DIR}/claude-model-default"
    run env \
        HOME="$TEST_HOME" \
        CLAUDE_PROJECT_DIR="$PROJECT_DIR" \
        DAAF_REMIND_MODEL_CACHE_DIR="$MODEL_CACHE_DIR" \
        bash "$REMIND_ORCHESTRATOR_SH" \
        <<<'{"hook_event_name":"UserPromptSubmit","session_id":"../unsafe"}'
    assert_success
    assert_output --partial "$ORDINARY_REMINDER"
    refute_output --partial "$GUIDANCE_MARKER"
}
