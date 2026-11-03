#!/usr/bin/env bats
# ============================================================================
# Tests for generate_log_viewer.py -- DAAF Session Log Manifest Builder
# ============================================================================
# Focus: per-session fault isolation. The archive can hold thousands of
# sessions and is often still growing while the builder runs, so truncated /
# in-flight .jsonl files are expected input. One malformed session must NOT
# abort the whole manifest -- it is skipped with a warning and processing
# continues. A manifest is still produced as long as at least one session
# parses; only an all-unreadable archive exits non-zero.
#
# These tests drive the Python builder directly (no Docker) against synthetic
# JSONL fixtures written into a temp logs/ dir. The last tests run the
# generate_log_viewer.sh wrapper only as far as its missing-logs checks, which
# exit before any manifest or server work.
# ============================================================================

load 'test_helper'

BUILDER="${REPO_ROOT}/scripts/generate_log_viewer.py"
WRAPPER="${REPO_ROOT}/scripts/generate_log_viewer.sh"

setup() {
    common_setup
    LOGS_DIR="${TEST_DIR}/logs"
    mkdir -p "${LOGS_DIR}"
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# Write a minimal VALID orchestrator session (one user + one assistant record).
# Args: <session_short> <timestamp-hh>
write_valid_session() {
    local short="$1"
    local hh="$2"
    local f="${LOGS_DIR}/2026-07-05_${hh}-00-00_${short}_orchestrator.jsonl"
    printf '%s\n' "{\"type\": \"user\", \"sessionId\": \"${short}0000\", \"version\": \"2.1.0\", \"gitBranch\": \"main\", \"timestamp\": \"2026-07-05T${hh}:00:00.000Z\", \"message\": {\"content\": [{\"type\": \"text\", \"text\": \"hi\"}]}, \"uuid\": \"u-${short}-1\"}" > "$f"
    printf '%s\n' "{\"type\": \"assistant\", \"timestamp\": \"2026-07-05T${hh}:00:01.000Z\", \"message\": {\"id\": \"m-${short}\", \"model\": \"claude-opus\", \"stop_reason\": \"end_turn\", \"content\": [{\"type\": \"text\", \"text\": \"reply\"}], \"usage\": {\"input_tokens\": 5, \"output_tokens\": 3}}, \"uuid\": \"u-${short}-2\"}" >> "$f"
}

# Write a POISON session: valid JSON, but a record whose "message" is a string
# rather than a dict. This survives json.loads but makes the downstream
# processing raise AttributeError, exercising the per-session try/except guard.
# Models a garbled/truncated in-flight record.
write_poison_session() {
    local short="$1"
    local hh="$2"
    local f="${LOGS_DIR}/2026-07-05_${hh}-00-00_${short}_orchestrator.jsonl"
    printf '%s\n' "{\"type\": \"assistant\", \"timestamp\": \"2026-07-05T${hh}:00:00.000Z\", \"message\": \"THIS-SHOULD-BE-A-DICT\", \"uuid\": \"p-${short}\"}" > "$f"
}

# Write a session whose orchestrator dispatches one subagent through tool $1
# ("Agent" today, "Task" in older transcripts), plus that subagent's transcript.
# The tool_result record carries toolUseResult.agentId, which is how the
# builder links the subagent back to its dispatch.
write_dispatch_session() {
    local tool="$1"
    local f="${LOGS_DIR}/2026-07-05_10-00-00_d15a7c00_orchestrator.jsonl"
    local sa="${LOGS_DIR}/2026-07-05_10-00-00_d15a7c00_subagent_ab12cd34.jsonl"
    {
        jq -nc '{type: "user", sessionId: "d15a7c00-0000", version: "2.1.281", timestamp: "2026-07-05T10:00:00.000Z",
                 message: {content: [{type: "text", text: "check the logs"}]}, uuid: "u-1"}'
        jq -nc --arg tool "$tool" '{type: "assistant", timestamp: "2026-07-05T10:00:01.000Z",
                 message: {id: "m-1", model: "claude-opus", stop_reason: "tool_use", content: [
                     {type: "tool_use", id: "toolu_1", name: $tool, input: {
                         subagent_type: "search-agent", description: "Scope the log viewer",
                         prompt: "scope it"}}]}, uuid: "u-2"}'
        jq -nc '{type: "user", timestamp: "2026-07-05T10:00:09.000Z",
                 message: {content: [{type: "tool_result", tool_use_id: "toolu_1", content: "done"}]},
                 toolUseResult: {agentId: "ab12cd34ef", agentType: "search-agent", totalDurationMs: 8000},
                 sourceToolAssistantUUID: "u-2", uuid: "u-3"}'
    } > "$f"
    {
        jq -nc '{type: "user", agentId: "ab12cd34ef", timestamp: "2026-07-05T10:00:02.000Z",
                 message: {content: "scope it"}, uuid: "s-1"}'
        jq -nc '{type: "assistant", agentId: "ab12cd34ef", timestamp: "2026-07-05T10:00:08.000Z",
                 message: {id: "sm-1", model: "claude-sonnet", stop_reason: "end_turn",
                           content: [{type: "text", text: "scoped"}]}, uuid: "s-2"}'
    } > "$sa"
}

# Print the dispatch fields of the built manifest, one per line: activity type,
# description, block summary, linked subagent id, subagent label, and the
# orchestrator line the subagent's invocation points at.
dispatch_fields() {
    jq -r '.sessions[0] as $s
        | ($s.blocks[] | select(.type == "assistant")) as $b
        | ($b.activities[0].type, $b.activities[0].description, $b.summary,
           $b.activities[0].subagentId, $s.subagents[0].label,
           ($s.subagents[0].invocation.orchestratorLine | tostring))' \
        "${LOGS_DIR}/session_manifest.json"
}

# --- Sanity ---

@test "generate_log_viewer.py compiles" {
    run python3 -m py_compile "${BUILDER}"
    assert_success
}

# --- Per-session fault isolation ---

@test "one malformed session among valid ones: manifest still built, exit 0" {
    write_valid_session aaaaaaaa 10
    write_valid_session bbbbbbbb 11
    write_poison_session cccccccc 12

    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_success
    assert_output --partial "Skipping session"
    assert_output --partial "cccccccc"
    assert_output --partial "2 processed"
    assert_output --partial "1 skipped"
    [ -f "${LOGS_DIR}/session_manifest.json" ]
}

@test "the skipped-session warning names the exception class" {
    write_valid_session aaaaaaaa 10
    write_poison_session cccccccc 12

    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_success
    assert_output --partial "AttributeError"
}

@test "all sessions malformed: no manifest, exit non-zero" {
    write_poison_session cccccccc 12
    write_poison_session dddddddd 13

    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_failure
    assert_output --partial "No sessions could be processed"
    [ ! -f "${LOGS_DIR}/session_manifest.json" ]
}

@test "all-valid sessions: no skip note in summary, exit 0" {
    write_valid_session aaaaaaaa 10
    write_valid_session bbbbbbbb 11

    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_success
    assert_output --partial "2 processed"
    refute_output --partial "skipped (unreadable)"
    [ -f "${LOGS_DIR}/session_manifest.json" ]
}

@test "empty logs dir (no jsonl): exit non-zero with clear message" {
    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_failure
    assert_output --partial "No JSONL session files found"
}

# --- Subagent dispatches: the "Agent" tool name and the older "Task" ---

@test "an Agent dispatch is shown as a dispatch and linked to its subagent" {
    write_dispatch_session "Agent"
    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_success
    run dispatch_fields
    assert_success
    assert_output "delegate
Dispatched search-agent specialist: Scope the log viewer
Dispatched 1 agent
ab12cd34
Scope the log viewer
2"
}

@test "a Task dispatch (older transcripts) is shown and linked the same way" {
    write_dispatch_session "Task"
    run python3 "${BUILDER}" --logs-dir "${LOGS_DIR}"
    assert_success
    run dispatch_fields
    assert_success
    assert_output "delegate
Dispatched search-agent specialist: Scope the log viewer
Dispatched 1 agent
ab12cd34
Scope the log viewer
2"
}

# --- Wrapper: missing-logs hints give a runnable command ---

@test "wrapper, project without logs/: exit 1 and the hint gives the full collect command" {
    local proj="${TEST_DIR}/2026-11-02_No_Logs"
    mkdir -p "$proj"
    run bash "${WRAPPER}" "$proj" --no-serve
    assert_failure 1
    assert_output --partial "ERROR: No logs/ directory found in: ${proj}"
    assert_output --partial "bash ${REPO_ROOT}/scripts/collect_session_logs.sh ${proj}"
    assert_output --partial "--archive"
}

@test "wrapper, project with an empty logs/ (a collect run that found nothing): same full hint" {
    local proj="${TEST_DIR}/2026-11-02_Empty_Logs"
    mkdir -p "${proj}/logs"
    run bash "${WRAPPER}" "$proj" --no-serve
    assert_failure 1
    assert_output --partial "ERROR: No orchestrator JSONL files found in: ${proj}/logs"
    assert_output --partial "bash ${REPO_ROOT}/scripts/collect_session_logs.sh ${proj}"
}
