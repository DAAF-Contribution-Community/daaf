#!/usr/bin/env bash
# enforce-explore-model.sh
# Blocks every dispatch of Claude Code's built-in Explore subagent and points
# the caller to search-agent. Explore starts without CLAUDE.md, so it does not
# follow DAAF's conventions, and it cannot write files, so it cannot save a
# record of what it found (Claude Code subagents docs, verified 2026-11-02).
# search-agent loads CLAUDE.md, carries the web-retrieval protocol, and writes
# its record to the path a dispatch names. The model is not the reason:
# Explore runs on the main conversation's model, capped at Opus (Claude Code
# v2.1.198 release note, quoted in anthropics/claude-code#72940; verified
# 2026-11-02).
#
# Hook type: PreToolUse (matchers: Task, Agent — both registered in
# .claude/settings.json)
# Decision: deny if subagent_type=Explore, whatever model the dispatch names
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
#       Code's plain-text block, which blocks the tool call whatever stdout
#       holds (Claude Code hooks reference, verified 2026-11-02). On no
#       match, exit 0 (allow).
#   Non-Explore dispatches ALLOW on every path: this guard is a routing
#   preference, not a safety boundary, so it must never block the pipeline
#   wholesale. Only the ERR trap (a genuinely unexpected failure) blocks
#   unconditionally, and it is jq-free.
#
# MULTI-VALUE STDIN. The jq path denies when any top-level value, or any
# element of a top-level array, is an object whose tool_input.subagent_type
# is exactly "Explore", so an Explore object glued to a benign one (either
# order, with or without a newline) is still caught. jq runs in streaming
# mode, so the values it parsed before a later syntax error count; after any
# jq error the jq-free raw-text match below also runs, so an Explore pair
# after the garbage is identified too. Malformed or empty stdin that carries
# no Explore pair ALLOWS (the routing-preference posture above). Claude Code
# sends one object; this is defence in depth, the same as in
# deny-claude-code-guide.sh.
set -uo pipefail

# Deny message — single source of truth for the JSON path and the jq-free
# fallback. Plain assignment (not a heredoc) so the string carries no trailing
# newline, preserving the exact reason text the JSON path has always emitted.
REASON="Explore subagents are blocked in this project. Use subagent_type search-agent instead: it follows DAAF's conventions (CLAUDE.md) and can write its findings to the file a dispatch names, while Explore starts without CLAUDE.md and cannot write files (Claude Code subagents docs, verified 2026-11-02). search-agent defaults to the Sonnet tier (the model can be overridden per dispatch) and has web access: built-in WebSearch to find pages, and bash /daaf/scripts/web_fetch.sh URL DEST_DIR (see the web-retrieval skill) to retrieve them; the built-in WebFetch is blocked."

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
