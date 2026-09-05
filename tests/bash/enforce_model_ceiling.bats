#!/usr/bin/env bats
# ============================================================================
# Tests for enforce-model-ceiling.sh -- PreToolUse subagent model-ceiling guard
# ============================================================================
# Contract (from the hook header): a subagent must never run on a HIGHER model
# tier than the current main session model. Ranks by substring match:
#   haiku=1, sonnet=2, opus=3, fable=4; a non-Claude slug = rank 0.
# Decision order (first match wins): (a) CLAUDE_CODE_SUBAGENT_MODEL set -> ALLOW;
# (b) ANTHROPIC_DEFAULT_OPUS/SONNET_MODEL set -> ALLOW; (c) requested model from
# tool_input.model else agent frontmatter, empty/inherit -> ALLOW; (d) session
# model from transcript then /tmp cache, undetectable -> ALLOW (fail-open);
# (f) non-Claude session + Claude request -> DENY (remap guidance); (g) requested
# rank > session rank -> DENY; (h) otherwise ALLOW.
#
# This hook is a COST guard and is deliberately FAIL-OPEN: missing jq, an
# undetectable session model, an unreadable/absent agent file, empty stdin, and
# malformed JSON all ALLOW (exit 0). Only a genuine over-tier (or non-Claude
# session + Claude request) dispatch is DENIED.
#
# Session-model control in these tests is deterministic via a synthetic
# transcript file placed in TEST_DIR whose last `.message.model` line the hook
# reads (same extraction as context-reporter.sh cache_model()). We avoid the
# /tmp/claude-model-<session_id> cache leg by using unique bogus session ids.
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft copy:
#   ENFORCE_MODEL_CEILING_SH=/path/to/draft.sh bats enforce_model_ceiling.bats
# ============================================================================

load 'test_helper'

ENFORCE_MODEL_CEILING_SH="${ENFORCE_MODEL_CEILING_SH:-${REPO_ROOT}/.claude/hooks/enforce-model-ceiling.sh}"

setup() {
    common_setup
    export ENFORCE_MODEL_CEILING_SH
    # Neutralize ambient env that would short-circuit the ceiling check (legs
    # a/b). A real container may export none of these, but a developer shell
    # might -- unset so the tests exercise the ranking logic deterministically.
    unset CLAUDE_CODE_SUBAGENT_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# Write a synthetic transcript JSONL whose last line carries $1 as the session
# model, and echo its path. tail -50 | ... | tail -1 in the hook reads it.
_make_transcript() {
    local model="$1"
    local path="${TEST_DIR}/transcript.jsonl"
    printf '%s\n' "{\"message\":{\"model\":\"${model}\"}}" > "$path"
    printf '%s' "$path"
}

# A dispatch payload: $1 session_id, $2 transcript_path, $3 requested model
# (tool_input.model), $4 subagent_type (optional).
_payload() {
    jq -nc \
        --arg sid "$1" \
        --arg tp "$2" \
        --arg model "$3" \
        --arg stype "${4:-research-executor}" '{
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "session_id": $sid,
        "transcript_path": $tp,
        "tool_input": ({ "subagent_type": $stype }
            + (if $model == "" then {} else { "model": $model } end))
    }'
}

# Write a fixture agent definition into TEST_DIR and echo the subagent_type
# string that drives the hook's FRONTMATTER leg (leg c) against it. The hook
# hardcodes `AGENTS_DIR=/daaf/.claude/agents` (readonly, no env override) and
# builds `AGENT_FILE="${AGENTS_DIR}/${subagent_type}.md"`. We therefore feed a
# subagent_type that path-traverses out of that hardcoded dir back to the
# fixture: the three leading `..` segments climb agents -> .claude -> daaf -> /,
# then TEST_DIR (absolute) descends to the fixture file. This exercises the
# REAL hook's frontmatter `model:` awk end-to-end against a controlled file,
# without modifying the hook or writing into the real agents dir. The fixture
# carries an inline comment on the `model:` line on purpose: the awk prints $2
# (the value), so a mutation to $NF would grab the trailing comment token and
# mis-rank the dispatch -- the over-tier DENY tests below fail under that
# mutation, closing the coverage gap. Fixtures live in TEST_DIR and are removed
# by common_teardown. Arg $1: fixture name; $2: the full `model:` line.
_make_agent_fixture() {
    local name="$1" modelline="$2"
    printf '%s\n' "---" "name: ${name}" "${modelline}" "tools: Read" "---" "# ${name}" "body" \
        > "${TEST_DIR}/${name}.md"
    # `..` x3 maps /daaf/.claude/agents -> / ; TEST_DIR is absolute (leading /),
    # so `../../..${TEST_DIR}` resolves to TEST_DIR. No trailing `.md` -- the
    # hook appends it.
    printf '../../..%s/%s' "${TEST_DIR}" "${name}"
}

# =========================================================================
# Syntax
# =========================================================================

@test "enforce-model-ceiling.sh parses without errors" {
    run bash -n "$ENFORCE_MODEL_CEILING_SH"
    assert_success
}

# =========================================================================
# DENY: requested tier exceeds session tier
# =========================================================================

@test "session sonnet + requested opus: DENY (over-tier)" {
    local tp; tp="$(_make_transcript "claude-sonnet-4-5")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-1" "$tp" "opus")
    assert_success
    [ -n "$output" ]  # non-empty guard: a no-emit hook would vacuously pass jq -e
    echo "$output" | jq -e '.' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | length > 0' >/dev/null
}

@test "session haiku + requested opus: DENY (over-tier, two ranks up)" {
    local tp; tp="$(_make_transcript "claude-haiku-4-5")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-2" "$tp" "claude-opus-4-8")
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    # The deny reason names the session model so the orchestrator can re-dispatch.
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("claude-haiku-4-5")' >/dev/null
}

# =========================================================================
# Leg (c): requested model resolved from AGENT FRONTMATTER (no tool_input.model)
# ---------------------------------------------------------------------------
# The live dispatch path: the orchestrator dispatches WITHOUT an explicit
# `model:` param, so the hook parses the tier from the dispatched agent's YAML
# frontmatter via awk (print $2 of the `model:` line, inside the leading `---`
# block). Every test above passes tool_input.model explicitly and short-circuits
# before this awk -- these tests exercise it. The fixtures carry an inline
# comment after the value (matching real DAAF agent files, e.g.
# `model: opus   # High-judgment tier ...`) so the $2-vs-$NF distinction is
# live: a mutation to $NF would read the trailing comment word (unrankable,
# rank 0) and silently ALLOW an over-tier dispatch.
# =========================================================================

@test "frontmatter over-tier + inline comment: session sonnet + agent 'model: opus  # ...' -> DENY (guards \$2 vs \$NF)" {
    local tp; tp="$(_make_transcript "claude-sonnet-4-5")"
    local stype; stype="$(_make_agent_fixture "fixture-opus" "model: opus   # High-judgment tier note words")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-fm-1" "$tp" "" "$stype")
    assert_success
    [ -n "$output" ]  # non-empty guard: a no-emit hook would vacuously pass jq -e
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    # Correct parse ($2) -> "opus" (rank 3) > sonnet (rank 2) -> DENY. A $NF
    # mutation would parse "words" (rank 0, unrankable) and ALLOW instead, so a
    # green DENY here proves the awk reads the value, not the inline comment.
}

@test "frontmatter within tier + inline comment: session opus + agent 'model: sonnet  # ...' -> ALLOW" {
    local tp; tp="$(_make_transcript "claude-opus-4-8")"
    local stype; stype="$(_make_agent_fixture "fixture-sonnet" "model: sonnet   # Well-specified tier note")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-fm-2" "$tp" "" "$stype")
    assert_success
    assert_output ""
}

@test "frontmatter over-tier + inline comment: session haiku + agent 'model: opus  # ...' -> DENY (reason names session)" {
    local tp; tp="$(_make_transcript "claude-haiku-4-5")"
    local stype; stype="$(_make_agent_fixture "fixture-opus2" "model: opus   # High-judgment tier note words")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-fm-3" "$tp" "" "$stype")
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    # Deny reason names the session model so the orchestrator can re-dispatch.
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("claude-haiku-4-5")' >/dev/null
}

# =========================================================================
# DENY: non-Claude session (rank 0) + Claude-family request -> remap guidance
# =========================================================================

@test "non-Claude session + Claude request: DENY with remap guidance" {
    local tp; tp="$(_make_transcript "glm-4.6")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-3" "$tp" "opus")
    assert_success
    [ -n "$output" ]
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null
    echo "$output" | jq -e '.hookSpecificOutput.permissionDecisionReason | contains("ANTHROPIC_DEFAULT_OPUS_MODEL")' >/dev/null
}

# =========================================================================
# ALLOW: requested tier within (<=) session tier
# =========================================================================

@test "session opus + requested sonnet: ALLOW (within ceiling), empty stdout" {
    local tp; tp="$(_make_transcript "claude-opus-4-8")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-4" "$tp" "sonnet")
    assert_success
    assert_output ""
}

@test "session opus + requested opus: ALLOW (equal tier)" {
    local tp; tp="$(_make_transcript "claude-opus-4-8")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-5" "$tp" "claude-opus-4-8")
    assert_success
    assert_output ""
}

# A non-Claude REQUESTED slug (rank 0) cannot be ranked -> ALLOW (fail-open),
# even against a Claude session. Complements the non-Claude-session deny leg.
@test "non-Claude requested model: ALLOW (unrankable, fail-open)" {
    local tp; tp="$(_make_transcript "claude-opus-4-8")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-6" "$tp" "glm-4.6")
    assert_success
    assert_output ""
}

# =========================================================================
# ALLOW: leg (c) -- requested model empty / inherit / unresolvable
# =========================================================================

@test "requested model 'inherit': ALLOW (tracks session)" {
    local tp; tp="$(_make_transcript "claude-sonnet-4-5")"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-7" "$tp" "inherit")
    assert_success
    assert_output ""
}

@test "no requested model + nonexistent agent file: ALLOW (nothing to constrain)" {
    local tp; tp="$(_make_transcript "claude-sonnet-4-5")"
    run bash "$ENFORCE_MODEL_CEILING_SH" \
        < <(_payload "bats-ceiling-8" "$tp" "" "no-such-agent-xyz")
    assert_success
    assert_output ""
}

# =========================================================================
# ALLOW: legs (a)/(b) -- env overrides short-circuit before ranking
# =========================================================================

@test "CLAUDE_CODE_SUBAGENT_MODEL set: ALLOW even for an over-tier request" {
    local tp; tp="$(_make_transcript "claude-sonnet-4-5")"
    export CLAUDE_CODE_SUBAGENT_MODEL="claude-opus-4-8"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-9" "$tp" "opus")
    assert_success
    assert_output ""
}

@test "ANTHROPIC_DEFAULT_OPUS_MODEL set: ALLOW even for an over-tier request" {
    local tp; tp="$(_make_transcript "claude-sonnet-4-5")"
    export ANTHROPIC_DEFAULT_OPUS_MODEL="my-custom-opus"
    run bash "$ENFORCE_MODEL_CEILING_SH" < <(_payload "bats-ceiling-10" "$tp" "opus")
    assert_success
    assert_output ""
}

# =========================================================================
# ALLOW: leg (d) -- session model undetectable -> fail-open with stderr note
# =========================================================================

@test "session model undetectable (no transcript, bogus cache id): ALLOW fail-open" {
    # transcript_path points at a nonexistent file; session_id is bogus so the
    # /tmp/claude-model-<id> cache leg also misses. The hook must fail open.
    run bash "$ENFORCE_MODEL_CEILING_SH" \
        < <(_payload "bats-ceiling-nonexistent-$$" "${TEST_DIR}/absent.jsonl" "opus")
    assert_success
    # stderr is folded into $output by `run`; the fail-open note must appear and
    # no deny JSON must be emitted.
    assert_output --partial "session model undetectable"
    refute_output --partial "\"deny\""
}

# =========================================================================
# Fail-open: missing jq -> ALLOW with a fail-open stderr message
# =========================================================================

@test "missing jq: exit 0 with fail-open stderr message (allow)" {
    local bindir="${TEST_DIR}/nojq_bin"
    mkdir -p "$bindir"
    ln -s "$(command -v bash)" "${bindir}/bash"
    ln -s "$(command -v cat)" "${bindir}/cat"
    # No jq symlink -> `command -v jq` fails inside the hook -> fail-open guard.
    run env -i PATH="$bindir" bash "$ENFORCE_MODEL_CEILING_SH" \
        <<<'{"session_id":"x","tool_input":{"subagent_type":"research-executor","model":"opus"}}'
    assert_success
    assert_output --partial "jq not found"
}

# =========================================================================
# Fail-open: empty stdin -> exit 0, no deny JSON
# =========================================================================

@test "empty stdin: exit 0, fail-open (allow), no deny JSON" {
    run bash "$ENFORCE_MODEL_CEILING_SH" < /dev/null
    assert_success
    refute_output --partial "\"deny\""
}

# =========================================================================
# Fail-open: malformed / non-JSON stdin -> exit 0, no deny JSON
# =========================================================================

@test "malformed stdin: exit 0, fail-open (allow), no deny JSON" {
    run bash "$ENFORCE_MODEL_CEILING_SH" <<<"this is not json {{{"
    assert_success
    refute_output --partial "\"deny\""
}
