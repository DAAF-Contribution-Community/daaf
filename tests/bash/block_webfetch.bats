#!/usr/bin/env bats
# ============================================================================
# Tests for block-webfetch.sh -- PreToolUse WebFetch deny-and-redirect guard
# ============================================================================
# Contract (from the hook header): the built-in WebFetch tool is DENIED
# UNCONDITIONALLY (it returns an AI paraphrase, not source text, conflicting
# with DAAF's evidence-graded quoting doctrine). Every invocation -- regardless
# of payload -- emits a deny decision whose reason redirects the agent to the
# DAAF fetch protocol `bash /daaf/scripts/web_fetch.sh <URL> <dest-dir>`.
#
# Failure posture: FAIL-CLOSED on EVERY path. Unlike the fail-open dispatch
# guards, an unexpected error must still DENY. jq is the hook's only structural
# dependency and it is checked before use, so there are two equivalent deny
# mechanisms:
#   - jq present: JSON permissionDecision=deny on stdout, exit 0 (the richer
#     message; the preferred path).
#   - jq absent, or ERR trap: the same redirect message on stderr plus exit 2
#     (Claude Code's plain-text block, which blocks regardless of stdout JSON
#     validity). jq is always present in the DAAF image, but the fallback is a
#     hard guarantee rather than a documented degradation: a hook that exits 0
#     with no decision would be read as ALLOW, silently bypassing the guard.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft copy:
#   BLOCK_WEBFETCH_SH=/path/to/draft.sh bats block_webfetch.bats
# ============================================================================

load 'test_helper'

BLOCK_WEBFETCH_SH="${BLOCK_WEBFETCH_SH:-${REPO_ROOT}/.claude/hooks/block-webfetch.sh}"

setup() {
    common_setup
    export BLOCK_WEBFETCH_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# A representative WebFetch PreToolUse payload.
_payload_webfetch() {
    jq -nc '{
        "hook_event_name": "PreToolUse",
        "tool_name": "WebFetch",
        "tool_input": {
            "url": "https://example.com/some-doc",
            "prompt": "summarize this page"
        }
    }'
}

# =========================================================================
# Syntax
# =========================================================================

@test "block-webfetch.sh parses without errors" {
    run bash -n "$BLOCK_WEBFETCH_SH"
    assert_success
}

# =========================================================================
# DENY: a normal WebFetch payload is blocked with a well-formed decision
# =========================================================================

@test "WebFetch payload: DENY with well-formed decision JSON" {
    run bash "$BLOCK_WEBFETCH_SH" < <(_payload_webfetch)
    assert_success
    [ -n "$output" ]  # non-empty guard: a no-emit hook would vacuously pass jq -e
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | length > 0' >/dev/null
}

@test "deny reason redirects to web_fetch.sh and cites the web-retrieval skill" {
    run bash "$BLOCK_WEBFETCH_SH" < <(_payload_webfetch)
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("web_fetch.sh")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("web-retrieval")' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("WebSearch")' >/dev/null
}

# =========================================================================
# DENY is unconditional: even empty and malformed stdin must still block
# (fail-closed doctrine guard -- the payload contents are irrelevant).
# =========================================================================

@test "empty stdin: still DENY (unconditional block, fail-closed)" {
    run bash "$BLOCK_WEBFETCH_SH" < /dev/null
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

@test "malformed stdin: still DENY (unconditional block, fail-closed)" {
    run bash "$BLOCK_WEBFETCH_SH" <<<"this is not json {{{"
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# =========================================================================
# The hook exits 0 (the hook process itself succeeds; the deny decision is
# carried in the JSON body, per the Task/Agent-tool hook convention). A nonzero
# exit would be misread by the harness.
# =========================================================================

@test "hook process exits 0 while emitting the deny decision in JSON" {
    run bash "$BLOCK_WEBFETCH_SH" < <(_payload_webfetch)
    [ "$status" -eq 0 ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
}

# =========================================================================
# Missing jq: the JSON decision cannot be serialized, so the hook MUST fall
# back to the plain-text block (stderr + exit 2) rather than exiting 0 with no
# decision -- an empty exit-0 is read by the harness as ALLOW, which would let
# WebFetch reach the network on any container missing jq. The jq-absence is
# simulated by running the hook under `env -i` with a PATH containing only
# symlinks to bash and cat, so `command -v jq` genuinely fails inside the hook.
# (The fallback deliberately uses bash builtins only -- printf, command -- so it
# needs nothing beyond those two symlinks.)
# =========================================================================

@test "missing jq: exit 2 (plain-text block), not a silent allow" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$BLOCK_WEBFETCH_SH" < <(printf '%s' '{"tool_name":"WebFetch"}')
    [ "$status" -eq 2 ]
}

@test "missing jq: block message still redirects to web_fetch.sh" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$BLOCK_WEBFETCH_SH" < <(printf '%s' '{"tool_name":"WebFetch"}')
    [ "$status" -eq 2 ]
    assert_output --partial "web_fetch.sh"
    assert_output --partial "web-retrieval"
}

# Guard that the jq-absence simulation is real: with the same stripped PATH, a
# `command -v jq` probe must fail. If jq ever leaked into the sandbox PATH the
# two tests above would silently exercise the ordinary JSON path instead.
@test "jq-absence simulation actually removes jq from the hook's PATH" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash -c 'command -v jq'
    assert_failure
}

# =========================================================================
# jq present: the primary path is unchanged -- the richer JSON deny decision is
# still emitted on stdout with exit 0 (the fallback must not have displaced it).
# =========================================================================

@test "jq present: primary path still emits JSON deny (exit 0, no exit 2)" {
    command -v jq >/dev/null  # precondition: this suite's normal environment has jq
    run bash "$BLOCK_WEBFETCH_SH" < <(_payload_webfetch)
    [ "$status" -eq 0 ]
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("web_fetch.sh")' >/dev/null
}
