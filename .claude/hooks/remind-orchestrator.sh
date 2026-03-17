#!/bin/bash
# remind-orchestrator.sh — Remind main-session LLM to load daaf-orchestrator
#
# Hook: UserPromptSubmit (main session only — subagents never trigger this)
#
# On each user message, checks whether the daaf-orchestrator skill has been
# loaded this session. If not, injects a reminder via stdout that appears as
# <user-prompt-submit-hook> text in the LLM's context.
#
# The flag file is set by flag-orchestrator-loaded.sh (PostToolUse on Skill).
#
# Exit codes:
#   0 = always (never block user messages)

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"' 2>/dev/null) || SESSION_ID="default"
FLAG="/tmp/claude-daaf-orchestrator-${SESSION_ID}"

if [[ ! -f "$FLAG" ]]; then
    echo "You are interacting with a human user. You MUST IMMEDIATELY invoke the daaf-orchestrator skill (Skill tool with skill: \"daaf-orchestrator\") BEFORE doing any other work."
fi

exit 0
