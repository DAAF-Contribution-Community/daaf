#!/usr/bin/env bats
# ============================================================================
# Tests for collect_session_logs.sh -- copy a project's archived sessions
# ============================================================================
# Contract (from the script header): search the session archive
# (<repo>/.claude/logs/sessions/) for *_orchestrator.jsonl files that mention
# the project folder's basename, then copy every archive file of each matching
# session (orchestrator + subagents, .jsonl + .md) into <project>/logs/,
# skipping files already there. Every run also creates <project>/logs/ and
# appends a pending collection marker to
# <repo>/.claude/logs/pending_log_collection.jsonl BEFORE the search, so a
# project worked on only in the running session is copied by archive-session.sh
# when that session ends, even when the search finds nothing.
#
# The script finds the repo root as the parent of its own folder, so every test
# runs a COPY of it inside a fake repo under TEST_DIR: the real archive and
# the real marker file are never touched.
#
# The end-to-end test pipes a SessionEnd payload to archive-session.sh;
# point it at a draft with ARCHIVE_SESSION_SH=/path/to/draft.sh. Likewise
# COLLECT_SH=/path/to/other_version.sh tests another copy of the collector.
# ============================================================================

load 'test_helper'

COLLECT_SH="${COLLECT_SH:-${REPO_ROOT}/scripts/collect_session_logs.sh}"
ARCHIVE_SESSION_SH="${ARCHIVE_SESSION_SH:-${REPO_ROOT}/.claude/hooks/archive-session.sh}"

setup() {
    common_setup
    FAKE_REPO="${TEST_DIR}/repo"
    SESSIONS="${FAKE_REPO}/.claude/logs/sessions"
    MARKER="${FAKE_REPO}/.claude/logs/pending_log_collection.jsonl"
    PROJ_NAME="2026-11-02_Collect_Test"
    PROJ="${FAKE_REPO}/research/${PROJ_NAME}"
    mkdir -p "${FAKE_REPO}/scripts" "$SESSIONS" "$PROJ"
    cp "$COLLECT_SH" "${FAKE_REPO}/scripts/collect_session_logs.sh"
    COLLECT_COPY="${FAKE_REPO}/scripts/collect_session_logs.sh"
    export FAKE_REPO SESSIONS MARKER PROJ_NAME PROJ COLLECT_COPY ARCHIVE_SESSION_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# _archive_set <short8> <text>: one archived session (orchestrator + one
# subagent, .jsonl + .md) whose orchestrator transcript contains <text>. The
# subagent transcript never mentions it, as for a search-agent that only read
# framework files.
_archive_set() {
    local short="$1" text="$2" stem="${SESSIONS}/2026-11-02_10-00-00_$1"
    printf '%s\n' "{\"message\":{\"role\":\"user\",\"content\":\"${text}\"}}" > "${stem}_orchestrator.jsonl"
    printf '# Claude Code Session Log\n' > "${stem}_orchestrator.md"
    printf '%s\n' '{"message":{"role":"user","content":"read the skill"}}' > "${stem}_subagent_5ab5ab5a.jsonl"
    printf '# Subagent Session Log\n' > "${stem}_subagent_5ab5ab5a.md"
}

# =========================================================================
# Static checks
# =========================================================================

@test "collect_session_logs.sh parses without errors" {
    run bash -n "$COLLECT_SH"
    assert_success
}

@test "collect_session_logs.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -S warning "$COLLECT_SH"
    assert_success
}

# =========================================================================
# Usage errors
# =========================================================================

@test "no argument: usage and exit 1" {
    run bash "$COLLECT_COPY"
    assert_failure 1
    assert_output --partial "Usage: bash"
}

@test "missing project folder: exit 1, nothing written" {
    run bash "$COLLECT_COPY" "${FAKE_REPO}/research/no_such_project"
    assert_failure 1
    assert_output --partial "ERROR: Project directory does not exist"
    [ ! -f "$MARKER" ]
}

@test "no session archive folder: exit 0 with a warning, no marker" {
    rm -rf "${FAKE_REPO}/.claude"
    run bash "$COLLECT_COPY" "$PROJ"
    assert_success
    assert_output --partial "WARNING: No session archive directory found"
    [ ! -e "${FAKE_REPO}/.claude/logs/pending_log_collection.jsonl" ]
}

# =========================================================================
# No archived session mentions the project (the running-session case)
# =========================================================================

@test "no match: exit 0, logs/ created, marker written, plain next step" {
    _archive_set "0bad0bad" "unrelated work"
    run bash "$COLLECT_COPY" "$PROJ"
    assert_success
    assert_output --partial "No archived session mentions '${PROJ_NAME}' yet, so nothing was copied."
    assert_output --partial "should be copied into ${PROJ}/logs/"
    assert_output --partial "run this command"
    refute_output --partial "Phase 1"
    [ -d "${PROJ}/logs" ]
    [ -z "$(ls -A "${PROJ}/logs")" ]
    # One marker line naming this project.
    run jq -r '[.project_path, .project_basename, (.requested_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z$"))] | @tsv' "$MARKER"
    assert_success
    assert_output "$(printf '%s\t%s\t%s' "$PROJ" "$PROJ_NAME" "true")"
}

# =========================================================================
# Matching sessions are copied whole
# =========================================================================

@test "match: copies every file of the matching session, none of the others" {
    _archive_set "abcdef12" "work in research/${PROJ_NAME}/scripts"
    _archive_set "0bad0bad" "unrelated work"
    run bash "$COLLECT_COPY" "$PROJ"
    assert_success
    assert_output --partial "Found 1 session(s) referencing this project."
    assert_output --partial "Files copied:      4"
    assert_output --partial "should be copied here"
    run bash -c 'ls -1 "${PROJ}/logs"'
    assert_output "$(printf '%s\n' \
        "2026-11-02_10-00-00_abcdef12_orchestrator.jsonl" \
        "2026-11-02_10-00-00_abcdef12_orchestrator.md" \
        "2026-11-02_10-00-00_abcdef12_subagent_5ab5ab5a.jsonl" \
        "2026-11-02_10-00-00_abcdef12_subagent_5ab5ab5a.md")"
    run wc -l < "$MARKER"
    assert_output "1"
}

@test "second run: skips files already present and appends a second marker" {
    _archive_set "abcdef12" "work in ${PROJ_NAME}"
    run bash "$COLLECT_COPY" "$PROJ"
    assert_success
    run bash "$COLLECT_COPY" "$PROJ"
    assert_success
    assert_output --partial "Files copied:      0"
    assert_output --partial "Files skipped:     4 (already present)"
    run wc -l < "$MARKER"
    assert_output "2"
}

# =========================================================================
# End to end: the marker from a no-match run is honored at SessionEnd
# =========================================================================

@test "no-match marker: archive-session.sh copies the running session into logs/ when it ends" {
    run bash "$COLLECT_COPY" "$PROJ"
    assert_success
    [ -s "$MARKER" ]
    # The running session's transcript mentions the project (the command
    # that ran collect_session_logs.sh names its path).
    local transcript="${TEST_DIR}/transcripts/cafe0123-4567.jsonl"
    mkdir -p "${TEST_DIR}/transcripts"
    printf '%s\n' "{\"timestamp\":\"2026-11-02T10:00:00.000Z\",\"message\":{\"role\":\"user\",\"content\":\"bash collect_session_logs.sh ${PROJ}\"}}" > "$transcript"
    run env CLAUDE_PROJECT_DIR="$FAKE_REPO" bash "$ARCHIVE_SESSION_SH" \
        < <(jq -nc --arg tp "$transcript" '{session_id:"cafe0123-4567", transcript_path:$tp, cwd:"/daaf", reason:"prompt_input_exit"}')
    assert_success
    run bash -c 'ls -1 "${PROJ}/logs"'
    assert_output --partial "_cafe0123_orchestrator.jsonl"
    assert_output --partial "_cafe0123_orchestrator.md"
    # The hook consumed the marker.
    [ ! -f "$MARKER" ]
}
