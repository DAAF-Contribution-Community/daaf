#!/usr/bin/env bash
# enforce-explore-model.sh
# Prevents Explore-type subagents from being launched with the haiku model.
# Explore agents need frontier-tier reasoning for thorough codebase analysis.
#
# Hook type: PreToolUse (matcher: Task)
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

# --- Preferred path: structured parse (jq present) ---
if command -v jq >/dev/null 2>&1; then
    SUBAGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null) || SUBAGENT_TYPE=""

    if [ "$SUBAGENT_TYPE" = "Explore" ]; then
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
EXPLORE_RE='"subagent_type"[[:space:]]*:[[:space:]]*"Explore"'
if [[ "$INPUT" =~ $EXPLORE_RE ]]; then
    printf '%s\n' "$REASON" >&2
    exit 2
fi

exit 0
