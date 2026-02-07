#!/bin/bash
# context-reporter.sh — Multi-event context utilization hook
#
# Injects context window utilization into Claude's conversation so the model
# can make informed decisions about delegation, state persistence, and session
# recovery (see CLAUDE.md utilization gates at 40%/60%/75%).
#
# Registered events:
#   UserPromptSubmit  — stdout text → injected as <user-prompt-submit-hook>
#   PreToolUse        — JSON additionalContext → injected before tool executes
#
# Deduplication:
#   A cache file stores the last-reported message. PreToolUse only injects
#   when the utilization message has changed (avoiding identical noise across
#   consecutive tool calls within the same exchange). UserPromptSubmit always
#   reports (it fires once per user message, so dedup isn't needed).
#
# Performance:
#   Uses `tail -50` to read only the end of the transcript, avoiding full-file
#   parsing. The last usage entry is always near the end of the JSONL.
#
# Exit codes:
#   0 = success (stdout/JSON processed by Claude Code)
#   All error paths exit 0 to never block tool execution.

INPUT=$(cat)
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null) || HOOK_EVENT=""
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"' 2>/dev/null) || SESSION_ID="default"
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null) || TRANSCRIPT_PATH=""

# Cache for deduplication (one per session, stores last reported message)
CACHE_FILE="/tmp/claude-ctx-${SESSION_ID}"

MAX_CONTEXT=200000
MAX_K=$((MAX_CONTEXT / 1000))

# ---------------------------------------------------------------------------
# calculate: Parse the transcript's most recent usage data and format a
# utilization message. Uses tail -50 to avoid parsing the entire JSONL file.
# Outputs a single line to stdout, or nothing if data is unavailable.
# ---------------------------------------------------------------------------
calculate() {
    local transcript="$1"
    [[ -z "$transcript" || ! -f "$transcript" ]] && return

    local tokens
    tokens=$(tail -50 "$transcript" 2>/dev/null | jq -s '
        [.[] | select(
            .message.usage and
            .isSidechain != true and
            .isApiErrorMessage != true
        )] | last |
        if . then
            (.message.usage.input_tokens // 0) +
            (.message.usage.cache_read_input_tokens // 0) +
            (.message.usage.cache_creation_input_tokens // 0)
        else 0 end
    ' 2>/dev/null) || tokens=0

    [[ "$tokens" -le 0 ]] && return

    local pct=$((tokens * 100 / MAX_CONTEXT))
    [[ $pct -gt 100 ]] && pct=100
    local used_k=$((tokens / 1000))

    local severity
    if   [[ $pct -ge 75 ]]; then severity="CRITICAL"
    elif [[ $pct -ge 60 ]]; then severity="HIGH"
    elif [[ $pct -ge 40 ]]; then severity="MODERATE"
    else                         severity="OK"
    fi

    echo "Context utilization [${severity}]: ${used_k}k / ${MAX_K}k tokens (${pct}%)"
}

# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------
case "$HOOK_EVENT" in

    UserPromptSubmit)
        # Always calculate and report (fires once per user message).
        # stdout → injected into Claude's context.
        MSG=$(calculate "$TRANSCRIPT_PATH")
        if [[ -n "$MSG" ]]; then
            echo "$MSG" > "$CACHE_FILE" 2>/dev/null
            echo "$MSG"
        fi
        ;;

    PreToolUse)
        # Calculate and inject ONLY if utilization has changed since last report.
        # This prevents identical messages on consecutive Read/Glob/Grep calls.
        MSG=$(calculate "$TRANSCRIPT_PATH")
        if [[ -n "$MSG" ]]; then
            CACHED=""
            [[ -f "$CACHE_FILE" ]] && CACHED=$(cat "$CACHE_FILE" 2>/dev/null)

            if [[ "$MSG" != "$CACHED" ]]; then
                echo "$MSG" > "$CACHE_FILE" 2>/dev/null
                # PreToolUse requires JSON with additionalContext to inject
                # into Claude's context. No permissionDecision = normal flow.
                jq -n --arg ctx "$MSG" '{
                    hookSpecificOutput: {
                        hookEventName: "PreToolUse",
                        additionalContext: $ctx
                    }
                }'
            fi
            # If unchanged → exit 0 with no output → tool proceeds, no injection
        fi
        ;;

    *)
        # Unknown event — do nothing, don't block
        ;;
esac

exit 0
