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
# Failure posture: FAIL-CLOSED. Unlike the fail-open dispatch guards, an
# unexpected error must still DENY (the ERR trap emits a deny). The single
# structural dependency is jq (used to emit the JSON) -- with jq present the
# hook always denies; the missing-jq degradation is exercised and documented
# below as a container-integrity note (jq is always present in the DAAF image).
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
# Container-integrity note (missing jq): the hook emits its decision via `jq -n`,
# so without jq it cannot serialize the deny and exits 0 with no JSON. jq is
# always present in the DAAF image; this test documents the degradation edge
# rather than endorsing a jq-less operating mode.
# =========================================================================

@test "missing jq: exit 0, no crash (deny cannot be serialized without jq)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    run env -i PATH="$bindir" bash "$BLOCK_WEBFETCH_SH" < <(printf '%s' '{"tool_name":"WebFetch"}')
    assert_success
}
