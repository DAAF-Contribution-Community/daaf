#!/usr/bin/env bash
# enforce-explore-model.sh
# Prevents Explore-type subagents from being launched with the haiku model.
# Explore agents need frontier-tier reasoning for thorough codebase analysis.
#
# Hook type: PreToolUse (matchers: Task, Agent — both registered in
# .claude/settings.json)
# Decision: deny if subagent_type=Explore (Explore always runs on Haiku)
#
# DEPENDENCY POSTURE (jq)
#   The decision is CONDITIONAL on tool_input.subagent_type, so jq is normally
#   what reads it. jq is checked with `command -v` BEFORE any use, and its
#   absence takes a fallback path rather than silently allowing:
#     - jq PRESENT: parse subagent_type; on an exact "Explore" match emit the
#       JSON `permissionDecision: deny` (richer message) and exit 0; otherwise
#       exit 0 silently (allow).
#     - jq ABSENT: apply a conservative raw-text match on the stdin payload for
#       a "subagent_type" key whose value is "Explore" (whitespace-tolerant,
#       case-sensitive to match the jq path's exact-match semantics). On a
#       match, block with the same message on stderr plus `exit 2` — Claude
#       Code's documented plain-text block, which blocks the tool call
#       regardless of stdout JSON validity (guaranteed as of the 2.1.214 fix).
#       On no match, exit 0 (allow). Previously the jq-less path could not see
#       subagent_type at all and therefore allowed an Explore dispatch through.
#   Non-Explore dispatches still ALLOW on every path: this guard is a routing
#   preference, not a safety boundary, so it must never block the pipeline
#   wholesale. Only the ERR trap (a genuinely unexpected failure) blocks
#   unconditionally, matching the prior behavior — and it, too, is jq-free.
#
# MULTI-VALUE STDIN [2026-09-26, added to the 2026-09-24 hook-maintenance
# bundle as revision _a by the SafetyHookHardening session] — a concatenated
# payload such as a benign Agent object glued to a
# {"tool_input":{"subagent_type":"Explore"}} object (either order, with or
# without a newline) used to ALLOW: `jq -r` printed one line per object, so
# SUBAGENT_TYPE held two lines and never equalled "Explore". Probed on
# 2026-09-26 (all four concatenated orders, banned+garbage, garbage+banned,
# and a top-level array: rc 0, no decision). The jq path now DENIES when ANY
# top-level value (or any element of a top-level array) is an object whose
# tool_input.subagent_type is exactly "Explore". jq runs in streaming mode,
# so the values it parsed before a later syntax error still count; if jq
# reports any error, the jq-free raw-text match below is also applied, so an
# Explore pair after the garbage is still identified. Plain malformed or
# empty stdin that carries no Explore pair still ALLOWS (the routing-
# preference posture above is unchanged). Whether the harness can ever emit
# such a payload is inference (it sends one object); this is defence in
# depth. Same change as deny-claude-code-guide.sh.
set -uo pipefail

# Deny message — single source of truth for the JSON path and the jq-free
# fallback. Plain assignment (not a heredoc) so the string carries no trailing
# newline, preserving the exact reason text the JSON path has always emitted.
REASON="Explore subagents are blocked in this project. Explore runs on Haiku, which lacks sufficient reasoning depth. Use subagent_type search-agent instead — it is a DAAF-native read-only agent that defaults to the Sonnet tier (model can be overridden per dispatch), has web access (built-in WebSearch for discovery, plus the DAAF web-retrieval protocol — bash /daaf/scripts/web_fetch.sh URL DEST_DIR, see the web-retrieval skill — for document retrieval; the built-in WebFetch is blocked), and understands DAAF conventions."

# Fail-closed ERR trap, deliberately jq-FREE: an error path that serialized its
# deny with `jq -n` would itself fail (silently allowing) on a container missing
# jq. stderr + exit 2 blocks using bash builtins alone.
trap 'printf "%s\n" "enforce-explore-model hook encountered an unexpected error; blocking the dispatch (fail-closed)." >&2; exit 2' ERR

INPUT=$(cat)
: "${INPUT:=}"

# Raw-text identification of a "subagent_type" key bound to the exact value
# "Explore" (see the fallback-path comment below for the matching rules).
# Used by the jq-free fallback and, on the jq path, whenever jq could not
# parse the whole stream.
EXPLORE_RE='"subagent_type"[[:space:]]*:[[:space:]]*"Explore"'

# --- Preferred path: structured parse (jq present) ---
if command -v jq >/dev/null 2>&1; then
    # One JSON-encoded subagent_type string per line (-c keeps an embedded
    # newline escaped, so a line can only equal "Explore" when the whole value
    # does). Streaming, not slurped: output produced before a later syntax
    # error is kept; JQ_OK records whether the parse completed.
    JQ_OK=1
    SUBAGENT_TYPES=$(printf '%s' "$INPUT" | jq -c '(if type == "array" then .[] else . end) | objects | .tool_input | objects | .subagent_type | strings' 2>/dev/null) || JQ_OK=0

    BANNED=0
    if [[ $'\n'"${SUBAGENT_TYPES}"$'\n' == *$'\n''"Explore"'$'\n'* ]]; then
        BANNED=1
    elif [ "$JQ_OK" -eq 0 ] && [[ "$INPUT" =~ $EXPLORE_RE ]]; then
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
# Matches a "subagent_type" key bound to the exact value "Explore", tolerating
# arbitrary whitespace around the colon (JSON permits it). Case-sensitive, so a
# lowercase "explore" — not a real subagent type — still allows, exactly as the
# jq path does. Malformed or empty stdin simply fails to match and therefore
# ALLOWS: without a parser there is no way to distinguish "malformed" from
# "some other agent type", and blocking every dispatch on a bookkeeping failure
# would halt the pipeline over a routing preference. The conservative-but-not-
# paranoid choice is to block only what is positively identifiable as Explore.
# EXPLORE_RE (defined above) matches anywhere in the payload, so a
# concatenated stream is covered here without any parsing.
if [[ "$INPUT" =~ $EXPLORE_RE ]]; then
    printf '%s\n' "$REASON" >&2
    exit 2
fi

exit 0
