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
# JSONL fixtures written into a temp logs/ dir.
# ============================================================================

load 'test_helper'

BUILDER="${REPO_ROOT}/scripts/generate_log_viewer.py"

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
