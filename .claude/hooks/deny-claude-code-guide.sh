#!/usr/bin/env bash
# deny-claude-code-guide.sh
# Blocks the claude-code-guide built-in agent from being spawned.
# This is a built-in agent with an opaque system prompt that doesn't
# align with DAAF's transparency requirements.
#
# Hook type: PreToolUse (matcher: Agent, Task)
# Decision: deny if subagent_type=claude-code-guide
trap 'jq -n "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"deny\",\"permissionDecisionReason\":\"deny-claude-code-guide hook encountered an unexpected error\"}}" 2>/dev/null; exit 0' ERR

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null) || SUBAGENT_TYPE=""

if [ "$SUBAGENT_TYPE" = "claude-code-guide" ]; then
  jq -n '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "claude-code-guide is NOT permitted in this project. It runs on the Haiku model, which lacks the reasoning depth and nuance required for accurate Claude Code guidance. Instead, spawn a search-agent (subagent_type: search-agent) and instruct it to use WebSearch to locate the relevant official Claude Code documentation pages (start at https://code.claude.com/docs/en/overview), then retrieve each page with the DAAF web-retrieval protocol — bash /daaf/scripts/web_fetch.sh URL DEST_DIR (see the web-retrieval skill) — and read the saved extract thoroughly for the question at hand. The search-agent defaults to the Sonnet tier (model can be overridden per dispatch); it uses built-in WebSearch for discovery and web_fetch.sh for document retrieval (the built-in WebFetch is blocked in this project)."
    }
  }'
fi

exit 0
