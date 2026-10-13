#!/usr/bin/env bats
# ============================================================================
# Tests for archive-session.sh -- SessionEnd transcript archiver
# ============================================================================
# Contract (from the hook header): on SessionEnd, copy the raw JSONL
# transcript into `${CLAUDE_PROJECT_DIR}/.claude/logs/sessions/` and render a
# human-readable Markdown companion, named
#   {date}_{time}_{session-short}_orchestrator.{jsonl,md}
# Subagent transcripts are discovered from Claude Code's raw hierarchy
# ({transcript-dir}/{session-uuid}/subagents/agent-*.jsonl, with agent type
# read from the sibling .meta.json) and archived as
#   {date}_{time}_{session-short}_subagent_{agent-id-short}.{jsonl,md}
#
# Idempotency: a second run for the same session short-id skips when the
# source transcript is no larger than the existing archive; if the source has
# GROWN, the stale archive set is replaced.
#
# Recovered sessions (reason="recovered") derive the archive timestamp from
# the transcript's LAST entry instead of wall clock, so recovered archives
# sort by when the session actually ran.
#
# Failure posture: fail-OPEN by design (`trap '' ERR`) -- archival is
# observability, not a security gate. Exit code is always 0.
#
# Redirection: the archive destination derives entirely from
# CLAUDE_PROJECT_DIR, and the transcript path comes from the stdin payload, so
# every test here runs against a fake project tree inside the bats temp dir.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   ARCHIVE_SESSION_SH=/path/to/draft.sh bats archive_session.bats
# ============================================================================

load 'test_helper'

ARCHIVE_SESSION_SH="${ARCHIVE_SESSION_SH:-${REPO_ROOT}/.claude/hooks/archive-session.sh}"

setup() {
    common_setup
    export ARCHIVE_SESSION_SH
    FAKE_PROJECT="${TEST_DIR}/proj"
    TRANSCRIPT_DIR="${TEST_DIR}/transcripts"
    ARCHIVE_DIR="${FAKE_PROJECT}/.claude/logs/sessions"
    mkdir -p "$FAKE_PROJECT" "$TRANSCRIPT_DIR"
    TRANSCRIPT="${TRANSCRIPT_DIR}/session.jsonl"
    _write_transcript "$TRANSCRIPT"
    export FAKE_PROJECT TRANSCRIPT_DIR ARCHIVE_DIR TRANSCRIPT
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A minimal but structurally faithful Claude Code JSONL transcript:
# one user turn, one assistant turn with text + a tool_use + usage.
_write_transcript() {
    cat > "$1" <<'JSONL'
{"timestamp":"2026-09-23T10:00:00.000Z","message":{"role":"user","content":"profile the CCD file"}}
{"timestamp":"2026-09-23T10:00:05.000Z","message":{"role":"assistant","model":"claude-opus-5","content":[{"type":"text","text":"Reading the file."},{"type":"tool_use","name":"Bash","input":{"command":"ls /daaf"}}],"usage":{"input_tokens":120,"output_tokens":42}}}
{"timestamp":"2026-09-23T10:00:07.000Z","message":{"role":"user","content":[{"type":"tool_result","content":"scripts\nresearch"}]}}
JSONL
}

# SessionEnd payload: session_id $1, transcript $2, reason $3 (default "clear").
_session_payload() {
    jq -nc --arg sid "$1" --arg tp "$2" --arg r "${3:-clear}" '{
        "hook_event_name": "SessionEnd",
        "session_id": $sid,
        "transcript_path": $tp,
        "cwd": "/daaf",
        "reason": $r
    }'
}

# Run the archiver with the destination redirected into TEST_DIR.
_archive() {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$ARCHIVE_SESSION_SH" \
        < <(_session_payload "$@")
}

# =========================================================================
# Static checks
# =========================================================================

@test "archive-session.sh parses without errors" {
    run bash -n "$ARCHIVE_SESSION_SH"
    assert_success
}

@test "archive-session.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "$ARCHIVE_SESSION_SH"
    assert_success
}

# =========================================================================
# Happy path
# =========================================================================

@test "archives both the JSONL copy and the Markdown rendering" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    assert_output --partial "Session archived:"
    run bash -c 'ls -1 "$ARCHIVE_DIR" | wc -l'
    assert_output "2"
}

@test "archive names follow {date}_{time}_{session-short}_orchestrator.*" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    run bash -c 'ls -1 "$ARCHIVE_DIR"'
    assert_output --partial "_deadbeef_orchestrator.jsonl"
    assert_output --partial "_deadbeef_orchestrator.md"
    # Date-time prefix shape: YYYY-MM-DD_HH-MM-SS
    [[ "${lines[0]}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}_deadbeef_orchestrator ]]
}

@test "archive directory is created if it does not exist" {
    [ ! -d "$ARCHIVE_DIR" ]
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    [ -d "$ARCHIVE_DIR" ]
}

@test "the archived JSONL is a byte-identical copy of the transcript" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    run bash -c 'cmp -s "$TRANSCRIPT" "$ARCHIVE_DIR"/*_deadbeef_orchestrator.jsonl'
    assert_success
}

@test "Markdown header carries session id, cwd, model, and end reason" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT" "clear"
    assert_success
    run cat "${ARCHIVE_DIR}"/*_deadbeef_orchestrator.md
    assert_output --partial "**Session ID:** deadbeef-1111-2222"
    assert_output --partial "**Directory:** /daaf"
    assert_output --partial "**Model:** claude-opus-5"
    assert_output --partial "**End Reason:** clear"
}

@test "Markdown renders user turns, assistant turns, and tool uses" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    run cat "${ARCHIVE_DIR}"/*_deadbeef_orchestrator.md
    assert_output --partial "profile the CCD file"
    assert_output --partial "Reading the file."
    assert_output --partial "Tool: Bash"
    assert_output --partial "ls /daaf"
    assert_output --partial "Tokens: in=120, out=42"
}

@test "Token line counts cache reads and writes in the input total" {
    # input_tokens is only the uncached part; the archive's "in" must be the sum
    # of all three fields (as context-reporter.sh computes), with the cached share
    # shown. A non-numeric field counts as 0 instead of aborting the render.
    cat > "$TRANSCRIPT" <<'JSONL'
{"timestamp":"2026-09-23T10:00:00.000Z","message":{"role":"user","content":"profile the CCD file"}}
{"timestamp":"2026-09-23T10:00:05.000Z","message":{"role":"assistant","model":"gpt-6-sol","content":[{"type":"text","text":"Cached turn."}],"usage":{"input_tokens":120,"cache_read_input_tokens":900,"cache_creation_input_tokens":80,"output_tokens":42}}}
{"timestamp":"2026-09-23T10:00:06.000Z","message":{"role":"assistant","model":"gpt-6-sol","content":[{"type":"text","text":"Odd usage."}],"usage":{"input_tokens":50,"cache_read_input_tokens":"7","output_tokens":5}}}
JSONL
    _archive "cafe0000-1111-2222" "$TRANSCRIPT"
    assert_success
    run cat "${ARCHIVE_DIR}"/*_cafe0000_orchestrator.md
    assert_output --partial "Tokens: in=1100 (cached=900), out=42"
    assert_output --partial "Tokens: in=50, out=5"
    assert_output --partial "Odd usage."
}

@test "Markdown ends with a session summary block" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    run cat "${ARCHIVE_DIR}"/*_deadbeef_orchestrator.md
    assert_output --partial "Session Summary"
    assert_output --partial "**Total messages:** 3"
    assert_output --partial "Archive completed:"
}

# =========================================================================
# Idempotency
# =========================================================================

@test "second run with unchanged transcript: skips, no duplicate archive set" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    assert_output --partial "already archived"
    assert_output --partial "skipping"
    run bash -c 'ls -1 "$ARCHIVE_DIR" | wc -l'
    assert_output "2"
}

@test "grown transcript: stale archive set is replaced, not duplicated" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    printf '%s\n' '{"timestamp":"2026-09-23T10:01:00.000Z","message":{"role":"user","content":"one more turn"}}' >> "$TRANSCRIPT"
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    assert_output --partial "Session archived:"
    run bash -c 'ls -1 "$ARCHIVE_DIR"/*_deadbeef_orchestrator.jsonl | wc -l'
    assert_output "1"
    run grep -c "one more turn" "${ARCHIVE_DIR}"/*_deadbeef_orchestrator.jsonl
    assert_output "1"
}

# =========================================================================
# Missing / degenerate input -- fail-open, never a crash
# =========================================================================

@test "missing transcript: reports it and exits 0 without archiving" {
    _archive "cafe0000-3333-4444" "${TRANSCRIPT_DIR}/nope.jsonl"
    assert_success
    assert_output --partial "No transcript found at:"
    [ ! -d "$ARCHIVE_DIR" ] || [ -z "$(ls -A "$ARCHIVE_DIR")" ]
}

@test "empty transcript_path: exits 0 without archiving" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$ARCHIVE_SESSION_SH" \
        < <(jq -nc '{"session_id":"abcd1234-5555","transcript_path":"","cwd":"/daaf","reason":"clear"}')
    assert_success
    assert_output --partial "No transcript found"
}

@test "empty stdin: exits 0 without crashing" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$ARCHIVE_SESSION_SH" < /dev/null
    assert_success
}

@test "malformed stdin: exits 0 without crashing" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$ARCHIVE_SESSION_SH" <<<"not json {{{"
    assert_success
}

@test "transcript with a malformed JSONL line: archives anyway (fail-open)" {
    printf '%s\n' 'this line is not json at all' >> "$TRANSCRIPT"
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    assert_output --partial "Session archived:"
    [ -f "$(ls "${ARCHIVE_DIR}"/*_deadbeef_orchestrator.md)" ]
}

# =========================================================================
# Recovered-session timestamp derivation
# =========================================================================

@test "reason=recovered: timestamp comes from the transcript's last entry" {
    _archive "feed0000-6666-7777" "$TRANSCRIPT" "recovered"
    assert_success
    run bash -c 'ls -1 "$ARCHIVE_DIR" | grep feed0000 | head -1'
    # Last entry timestamp in the fixture is 2026-09-23T10:00:07.000Z
    assert_output "2026-09-23_10-00-07_feed0000_orchestrator.jsonl"
}

@test "reason=recovered handles a timestamp with no fractional seconds" {
    local tp="${TRANSCRIPT_DIR}/nofrac.jsonl"
    printf '%s\n' '{"timestamp":"2026-09-23T11:22:33Z","message":{"role":"user","content":"hi"}}' > "$tp"
    _archive "beefcafe-8888" "$tp" "recovered"
    assert_success
    run bash -c 'ls -1 "$ARCHIVE_DIR" | grep beefcafe | head -1'
    assert_output "2026-09-23_11-22-33_beefcafe_orchestrator.jsonl"
}

@test "reason=clear uses wall clock, not the transcript timestamp" {
    _archive "0bad0bad-9999" "$TRANSCRIPT" "clear"
    assert_success
    run bash -c 'ls -1 "$ARCHIVE_DIR" | grep 0bad0bad | head -1'
    # The fixture's last entry is 10:00:07; a wall-clock archive must not
    # reuse it (except in the vanishingly unlikely case of running at exactly
    # that second on that date -- acceptable, and the date itself differs).
    [[ "$output" != "2026-09-23_10-00-07_0bad0bad_orchestrator.jsonl" ]]
}

# =========================================================================
# Subagent discovery and archiving
# =========================================================================

@test "subagent transcripts are discovered, archived, and summarized" {
    local sid="aaaa1111-2222-3333"
    local sa_dir="${TRANSCRIPT_DIR}/${sid}/subagents"
    mkdir -p "$sa_dir"
    _write_transcript "${sa_dir}/agent-bbbb2222-4444.jsonl"
    printf '%s' '{"agentType":"search-agent"}' > "${sa_dir}/agent-bbbb2222-4444.meta.json"

    _archive "$sid" "$TRANSCRIPT"
    assert_success

    run bash -c 'ls -1 "$ARCHIVE_DIR"'
    assert_output --partial "_aaaa1111_subagent_bbbb2222.jsonl"
    assert_output --partial "_aaaa1111_subagent_bbbb2222.md"

    run cat "${ARCHIVE_DIR}"/*_aaaa1111_orchestrator.md
    assert_output --partial "Subagent Activity"
    assert_output --partial "**Subagents dispatched:** 1"
    assert_output --partial "search-agent"
}

@test "subagent with no .meta.json is archived with agent type 'unknown'" {
    local sid="aaaa1111-2222-3333"
    local sa_dir="${TRANSCRIPT_DIR}/${sid}/subagents"
    mkdir -p "$sa_dir"
    _write_transcript "${sa_dir}/agent-cccc3333-5555.jsonl"

    _archive "$sid" "$TRANSCRIPT"
    assert_success
    run cat "${ARCHIVE_DIR}"/*_aaaa1111_orchestrator.md
    assert_output --partial "unknown"
}

@test "no subagents directory: no Subagent Activity section is emitted" {
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    run cat "${ARCHIVE_DIR}"/*_deadbeef_orchestrator.md
    refute_output --partial "Subagent Activity"
}

# =========================================================================
# Pending log collection (project-local copy of the archive set)
# =========================================================================

@test "pending log collection copies archives into the referenced project" {
    local proj_target="${TEST_DIR}/research_proj"
    mkdir -p "${FAKE_PROJECT}/.claude/logs" "$proj_target"
    # The fixture transcript must reference the project basename for the
    # hook's grep-based relevance check to match.
    printf '%s\n' '{"timestamp":"2026-09-23T10:00:09.000Z","message":{"role":"user","content":"work in research_proj"}}' >> "$TRANSCRIPT"
    jq -nc --arg p "$proj_target" '{project_basename:"research_proj", project_path:$p}' \
        > "${FAKE_PROJECT}/.claude/logs/pending_log_collection.jsonl"

    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
    [ -d "${proj_target}/logs" ]
    run bash -c 'ls -1 "'"${proj_target}"'/logs" | wc -l'
    assert_output "2"
    # The queue file is consumed (atomically moved, then removed).
    [ ! -f "${FAKE_PROJECT}/.claude/logs/pending_log_collection.jsonl" ]
}

@test "pending entry for a nonexistent project path is skipped without error" {
    mkdir -p "${FAKE_PROJECT}/.claude/logs"
    jq -nc '{project_basename:"ghost", project_path:"/no/such/dir"}' \
        > "${FAKE_PROJECT}/.claude/logs/pending_log_collection.jsonl"
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    assert_success
}

# =========================================================================
# SessionEnd timeout budget
#
# settings.json gives this hook a 60s timeout (the largest in the file --
# every other hook is 5s). A small transcript must archive in a small
# fraction of that. The bound is deliberately loose (10s) so the assertion is
# a genuine budget regression detector, not a flaky performance microbenchmark.
# =========================================================================

@test "small transcript archives well inside the 60s SessionEnd budget" {
    local start end
    start=$(date +%s)
    _archive "deadbeef-1111-2222" "$TRANSCRIPT"
    end=$(date +%s)
    assert_success
    [ "$((end - start))" -lt 10 ]
}

@test "settings.json grants this hook the documented 60s SessionEnd timeout" {
    run jq -r '
        .hooks.SessionEnd[].hooks[]
        | select(.command | test("archive-session"))
        | .timeout
    ' "${REPO_ROOT}/.claude/settings.json"
    assert_success
    assert_output "60"
}

# =========================================================================
# Registration
# =========================================================================

@test "registered as a SessionEnd hook under the unmatched ('') matcher" {
    run jq -r '
        [.hooks.SessionEnd[]
         | select(.hooks[].command | test("archive-session"))
         | .matcher] | join(",")
    ' "${REPO_ROOT}/.claude/settings.json"
    assert_success
    assert_output ""
}
