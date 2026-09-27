#!/usr/bin/env bash
# deny-claude-code-guide.sh
# Blocks the claude-code-guide built-in agent from being spawned.
# This is a built-in agent with an opaque system prompt that doesn't
# align with DAAF's transparency requirements.
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
#       message on stderr plus `exit 2` — Claude Code's documented plain-text
#       block, which blocks the tool call regardless of stdout JSON validity
#       (guaranteed as of the 2.1.214 fix). On no match, exit 0 (allow).
#       [2026-09-24 hook-maintenance pass] Previously the jq-less path could
#       not see subagent_type at all and exited 0 with no decision, which the
#       harness read as ALLOW — a silent fail-OPEN on the banned agent.
#     - UNEXPECTED ERROR: the ERR trap blocks with stderr + exit 2. It is
#       deliberately jq-FREE: the previous trap serialized its deny with
#       `jq -n`, which itself fails (and so allows) on exactly the jq-less
#       container the trap is meant to cover.
#   Other subagent types still ALLOW on every non-error path, including empty
#   or malformed stdin: without a parse there is no positive identification
#   of claude-code-guide, and blocking every dispatch on a bookkeeping failure
#   would halt the pipeline (the same reasoning enforce-explore-model.sh
#   records for its fallback).
#
# MULTI-VALUE STDIN [2026-09-26 bundle revision _a, SafetyHookHardening
# session] — a concatenated payload such as a benign Agent object glued to a
# {"tool_input":{"subagent_type":"claude-code-guide"}} object (either order,
# with or without a newline) used to ALLOW: `jq -r` printed one line per
# object, so SUBAGENT_TYPE held two lines and never equalled
# "claude-code-guide". Probed on 2026-09-26 (all four concatenated orders,
# banned+garbage, garbage+banned, and a top-level array: rc 0, no decision).
# The jq path now DENIES when ANY top-level value (or any element of a
# top-level array) is an object whose tool_input.subagent_type is exactly
# "claude-code-guide". jq runs in streaming mode, so the values it parsed
# before a later syntax error still count; if jq reports any error, the
# jq-free raw-text match below is also applied, so a banned pair after the
# garbage is still identified. Plain malformed or empty stdin that carries no
# banned pair still ALLOWS (the documented fail-open posture is unchanged).
# Whether the harness can ever emit such a payload is inference (it sends one
# object); this is defence in depth, mirroring enforce-file-first.sh's
# one-object gate for a hook that must stay fail-open on malformed input.
set -uo pipefail

# Deny message — single source of truth for the JSON path and the jq-free
# fallback. Plain assignment (not a heredoc) so the string carries no trailing
# newline, preserving the exact reason text the JSON path has always emitted.
REASON="claude-code-guide is NOT permitted in this project. It runs on the Haiku model, which lacks the reasoning depth and nuance required for accurate Claude Code guidance. Instead, spawn a search-agent (subagent_type: search-agent) and instruct it to use WebSearch to locate the relevant official Claude Code documentation pages (start at https://code.claude.com/docs/en/overview), then retrieve each page with the DAAF web-retrieval protocol — bash /daaf/scripts/web_fetch.sh URL DEST_DIR (see the web-retrieval skill) — and read the saved extract thoroughly for the question at hand. The search-agent defaults to the Sonnet tier (model can be overridden per dispatch); it uses built-in WebSearch for discovery and web_fetch.sh for document retrieval (the built-in WebFetch is blocked in this project)."

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
