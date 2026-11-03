#!/usr/bin/env bash
# deny-claude-code-guide.sh
# Blocks the claude-code-guide built-in agent from being spawned.
# This is a built-in agent with an opaque system prompt that doesn't
# align with DAAF's transparency requirements. It also runs on Haiku (Claude
# Code subagents docs, verified 2026-11-02), a tier DAAF does not use for
# subagents; the deny message gives that second, since it is a vendor fact
# that can change.
#
# Hook type: PreToolUse (matcher: Agent, Task)
# Decision: deny if subagent_type=claude-code-guide
#
# DEPENDENCY POSTURE (jq) — mirrors enforce-explore-model.sh, the sibling
# Task/Agent hook with the same "deny one named subagent_type" shape.
#   The decision is CONDITIONAL on tool_input.subagent_type, so jq is normally
#   what reads it. jq is checked with `command -v` BEFORE any use, and its
#   absence takes a jq-free fallback rather than silently allowing:
#     - jq PRESENT: parse subagent_type; on an exact "claude-code-guide" match
#       emit the JSON `permissionDecision: deny` (the Task/Agent-tool
#       convention) and exit 0; otherwise exit 0 silently (allow).
#     - jq ABSENT: apply a raw-text match on the stdin payload for a
#       "subagent_type" key bound to the exact value "claude-code-guide"
#       (whitespace-tolerant around the colon, case-sensitive to match the jq
#       path's exact-match semantics). On a match, block with the same
#       message on stderr plus `exit 2` — Claude Code's plain-text block,
#       which blocks the tool call whatever stdout holds (Claude Code hooks
#       reference, verified 2026-11-02). On no match, exit 0 (allow).
#     - UNEXPECTED ERROR: the ERR trap blocks with stderr + exit 2. It uses
#       no jq: a deny written with `jq -n` would itself fail, and so allow, on
#       the jq-less container the trap is meant to cover.
#   Other subagent types still ALLOW on every non-error path, including empty
#   or malformed stdin: without a parse there is no positive identification
#   of claude-code-guide, and blocking every dispatch on a bookkeeping failure
#   would halt the pipeline (the same reasoning enforce-explore-model.sh
#   records for its fallback).
#
# MULTI-VALUE STDIN. The jq path denies when any top-level value, or any
# element of a top-level array, is an object whose tool_input.subagent_type
# is exactly "claude-code-guide", so a banned object glued to a benign one
# (either order, with or without a newline) is still caught. jq runs in
# streaming mode, so the values it parsed before a later syntax error count;
# after any jq error the jq-free raw-text match below also runs, so a banned
# pair after the garbage is identified too. Malformed or empty stdin that
# carries no banned pair ALLOWS (the fail-open posture above). Claude Code
# sends one object; this is defence in depth, mirroring enforce-file-first.sh's
# one-object gate for a hook that must stay fail-open on malformed input.
set -uo pipefail

# Deny message — single source of truth for the JSON path and the jq-free
# fallback. Plain assignment (not a heredoc) so the string carries no trailing
# newline, preserving the exact reason text the JSON path has always emitted.
REASON="claude-code-guide is NOT permitted in this project. Spawn a search-agent instead (subagent_type: search-agent): claude-code-guide is a built-in agent with an opaque system prompt, which conflicts with DAAF's transparency requirement, and it runs on the Haiku model, a tier DAAF does not use for subagents (Claude Code subagents docs, verified 2026-11-02). Instruct the search-agent to use WebSearch to find the official Claude Code documentation pages (start at https://code.claude.com/docs/en/overview), retrieve each page with the DAAF web-retrieval protocol, bash /daaf/scripts/web_fetch.sh URL DEST_DIR (see the web-retrieval skill), and read the saved extract for the question at hand. The search-agent defaults to the Sonnet tier (the model can be overridden per dispatch); the built-in WebFetch is blocked in this project."

# Fail-closed ERR trap, deliberately jq-FREE (see DEPENDENCY POSTURE above).
trap 'printf "%s\n" "deny-claude-code-guide hook encountered an unexpected error; blocking the dispatch (fail-closed)." >&2; exit 2' ERR

INPUT=$(cat)
: "${INPUT:=}"

# Raw-text identification of a "subagent_type" key bound to the exact value
# "claude-code-guide". The closing quote is part of the pattern, so a
# near-miss name such as "claude-code-guide-v2" does NOT match (same
# exact-equality semantics as the jq path). Used by the jq-free fallback and,
# on the jq path, whenever jq could not parse the whole stream.
GUIDE_RE='"subagent_type"[[:space:]]*:[[:space:]]*"claude-code-guide"'

# --- Preferred path: structured parse (jq present) ---
if command -v jq >/dev/null 2>&1; then
    # One JSON-encoded subagent_type string per line (-c keeps an embedded
    # newline escaped, so a line can only equal "claude-code-guide" when the
    # whole value does). Streaming, not slurped: output produced before a
    # later syntax error is kept; JQ_OK records whether the parse completed.
    JQ_OK=1
    SUBAGENT_TYPES=$(printf '%s' "$INPUT" | jq -c '(if type == "array" then .[] else . end) | objects | .tool_input | objects | .subagent_type | strings' 2>/dev/null) || JQ_OK=0

    BANNED=0
    if [[ $'\n'"${SUBAGENT_TYPES}"$'\n' == *$'\n''"claude-code-guide"'$'\n'* ]]; then
        BANNED=1
    elif [ "$JQ_OK" -eq 0 ] && [[ "$INPUT" =~ $GUIDE_RE ]]; then
        BANNED=1
    fi

    if [ "$BANNED" -eq 1 ]; then
        jq -n --arg r "$REASON" '{
          "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": $r
          }
        }'
    fi

    exit 0
fi

# --- Fallback path: raw-text match (jq absent) ---
# GUIDE_RE (defined above) matches anywhere in the payload, so a concatenated
# stream is covered here without any parsing.
if [[ "$INPUT" =~ $GUIDE_RE ]]; then
    printf '%s\n' "$REASON" >&2
    exit 2
fi

exit 0
