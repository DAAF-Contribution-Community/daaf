#!/usr/bin/env bash
# remind-orchestrator.sh — Remind main-session LLM to load daaf-orchestrator
#
# Hook: UserPromptSubmit (main session only — explicit caller guard below)
#
# On each user message, checks whether the daaf-orchestrator skill has been
# loaded this session. If not, injects a reminder via stdout that appears as
# <user-prompt-submit-hook> text in the LLM's context.
#
# While that normal reminder branch is active, genuine terminal gpt-* session
# models also receive a compact collaborator-guidance reminder. Model identity
# comes only from the session-scoped /tmp/claude-model-<session_id> cache written
# by context-bar.sh. Missing, empty, or malformed identity is a silent no-op for
# GPT-specific guidance; the ordinary orchestrator reminder still fires.
#
# Additionally, on the user's FIRST EVER session (detected via activity.log
# line count), injects a first-run transparency statement that Claude must
# present before proceeding with normal workflow. The transparency content
# lives in first-run-transparency.txt alongside this script.
#
# Detection logic:
#   activity.log gets a line appended at every SessionStart. When this hook
#   fires on the first UserPromptSubmit of the first-ever session, activity.log
#   has exactly 1 line (from the SessionStart that just fired). On subsequent
#   sessions it has 2+. So: line_count <= 1 means first session.
#
# The orchestrator-loaded flag file is set by flag-orchestrator-loaded.sh
# (PostToolUse on Skill).
#
# Flag location — persistent home volume, NOT /tmp (changed 2026-07-15):
#   "The skill was loaded" is a property of the session TRANSCRIPT. Transcripts
#   live in ~/.claude (the claude-config Docker volume) and survive container
#   rebuilds, and resumed sessions reuse their original session_id (Claude Code
#   CLI reference: --fork-session exists precisely because plain --resume/
#   --continue reuses the ID). When the flag lived in /tmp it died with every
#   container rebuild, so the first prompt of every resumed session re-fired
#   the reminder and re-loaded ~10-15k tokens of skill content into a context
#   that already contained it. The flag now lives in ~/.claude/daaf-state/,
#   matching the transcript's lifetime.
#
#   General placement principle: match a cache's storage to the lifetime of
#   the fact it caches. Session-runtime facts (active model, context window,
#   reporter throttle timestamps) stay in /tmp — rebuild-wipe is free cache
#   invalidation for them. Transcript-lifetime facts belong in ~/.claude.
#
# Exit codes:
#   0 = always (never block user messages)

INPUT=$(cat)
INPUT_PARSED=0
SESSION_ID=""
CALLER_ELIGIBLE=0

# One jq pass validates caller eligibility and session identity before either
# value crosses into Bash. The path-safe session grammar is complete and
# anchored inside jq, so command substitution/read cannot normalize a newline,
# NUL, unit separator, or other control into a different cache identity. Caller
# eligibility is also reduced to a trusted 0/1 scalar inside jq: raw agent fields
# never enter Bash, and non-string or malformed nonempty identities stay silent.
# Missing jq, malformed/non-object JSON, or extraction failure preserves the
# ordinary reminder but can never authorize a model-cache read or GPT guidance.
if command -v jq >/dev/null 2>&1; then
    if IFS=$'\x1f' read -r SESSION_ID CALLER_ELIGIBLE < <(printf '%s' "$INPUT" | jq -er '
        def valid_session_id:
            if type == "string" then
                (test("[[:cntrl:]]") | not) and
                test("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
            else false
            end;

        if type != "object" then error("hook payload must be an object")
        else
            [ (if (.session_id? | valid_session_id)
               then .session_id
               else ""
               end),
              (if ((.agent_id? == null) or
                   ((.agent_id? | type) == "string" and .agent_id == "")) and
                  ((.agent_type? == null) or
                   ((.agent_type? | type) == "string" and
                    (.agent_type == "" or .agent_type == "orchestrator")))
               then "1"
               else "0"
               end) ]
            | join("")
        end
    ' 2>/dev/null); then
        INPUT_PARSED=1
    fi
fi

# Explicit main-thread guard. Successfully parsed subagent or malformed caller
# identity stays silent. Unresolved payload identity preserves the fail-open
# ordinary reminder while GPT-specific guidance remains disabled below.
if [[ "$INPUT_PARSED" -eq 1 && "$CALLER_ELIGIBLE" -ne 1 ]]; then
    exit 0
fi

# Session IDs become path components for both the transcript-lifetime flag and
# the session-runtime model cache. Only jq-validated IDs are exposed to Bash.
# Invalid or absent IDs retain historical "default" LOADED-FLAG semantics, but
# never select a shared default model cache.
SESSION_ID_VALID=0
FLAG_SESSION_ID="default"
if [[ "$INPUT_PARSED" -eq 1 && -n "$SESSION_ID" ]]; then
    SESSION_ID_VALID=1
    FLAG_SESSION_ID="$SESSION_ID"
fi

FLAG="${HOME}/.claude/daaf-state/orchestrator-loaded-${FLAG_SESSION_ID}"

if [[ ! -f "$FLAG" ]]; then
    # Always remind to load the orchestrator
    echo "You are interacting with a human user. You MUST IMMEDIATELY invoke the daaf-orchestrator skill (Skill tool with skill: \"daaf-orchestrator\") BEFORE doing any other work."

    # The statusline payload is the authoritative source for the active session
    # model. No transcript or environment fallback is used: stale or unresolved
    # identity must suppress GPT-specific guidance rather than guess.
    MODEL_ID=""
    if [[ "$INPUT_PARSED" -eq 1 && "$SESSION_ID_VALID" -eq 1 ]]; then
        MODEL_CACHE_DIR="${DAAF_REMIND_MODEL_CACHE_DIR:-/tmp}"
        MODEL_CACHE="${MODEL_CACHE_DIR}/claude-model-${SESSION_ID}"
        if [[ -s "$MODEL_CACHE" ]]; then
            # Command substitution removes trailing newlines. Append a sentinel
            # byte before substitution, then remove only that byte afterward so
            # cache whitespace — including a final newline — remains detectable.
            MODEL_ID_WITH_SENTINEL=$(cat "$MODEL_CACHE" 2>/dev/null; printf 'x')
            MODEL_ID="${MODEL_ID_WITH_SENTINEL%x}"
        fi
    fi

    MODEL_SLUG="${MODEL_ID##*/}"
    if [[ -n "$MODEL_ID" && "$MODEL_ID" != *[[:space:]]* && "$MODEL_SLUG" == gpt-?* ]]; then
        echo "For this GPT session, treat the user as an equal stakeholder and thoughtful collaborator. Default to concise, user-relevant responses in plain language at their demonstrated technical depth. Lead with the answer or decision; put an immediate action first only when action is what they need. Make required actions, options, recommendations, and consequences easy to spot. When several independent decisions are genuinely needed, present them separately rather than collapsing them into one question. Put secondary technical and implementation detail in clearly marked optional sections or artifacts. Be warm, direct, and easy to scan, never patronizing. Keep full evidence and reproducibility detail available, while surfacing the uncertainty, caveats, citations, safety warnings, and consent checkpoints that affect the current decision."
    fi

    # Check if this is the user's first-ever session
    ACTIVITY_LOG="${CLAUDE_PROJECT_DIR:-.}/.claude/logs/activity.log"
    LINE_COUNT=0
    if [[ -f "$ACTIVITY_LOG" ]]; then
        LINE_COUNT=$(wc -l < "$ACTIVITY_LOG" 2>/dev/null || echo "0")
        # Trim whitespace (macOS wc pads with spaces)
        LINE_COUNT=$(echo "$LINE_COUNT" | tr -d '[:space:]')
    fi

    if [[ "$LINE_COUNT" -le 1 ]]; then
        # First session ever — inject transparency statement
        HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
        TRANSPARENCY_FILE="${DAAF_REMIND_TRANSPARENCY_FILE:-${HOOK_DIR}/first-run-transparency.txt}"
        if [[ -f "$TRANSPARENCY_FILE" ]]; then
            echo ""
            cat "$TRANSPARENCY_FILE"
        fi
    fi
fi

exit 0
