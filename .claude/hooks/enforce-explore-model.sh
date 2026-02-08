#!/bin/bash
# enforce-explore-model.sh
# Prevents Explore-type subagents from being launched with the haiku model.
# Explore agents need frontier-tier reasoning for thorough codebase analysis.
#
# Hook type: PreToolUse (matcher: Task)
# Decision: deny if subagent_type=Explore AND model=haiku
set -e

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty')
MODEL=$(echo "$INPUT" | jq -r '.tool_input.model // empty')

if [ "$SUBAGENT_TYPE" = "Explore" ] && [ "$MODEL" = "haiku" ]; then
  jq -n '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "Explore subagents must not use haiku. Use sonnet or opus for sufficient reasoning depth."
    }
  }'
fi

exit 0
