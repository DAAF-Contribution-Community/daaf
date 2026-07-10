#!/usr/bin/env bash
# block-remote-isolation.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   PreToolUse hook for Agent/Task dispatches: DENY any dispatch that sets
#   isolation: "remote". Remote cloud environments are gated/unavailable in
#   the DAAF container, and such dispatches never return a tool_result — the
#   session waits silently until killed.
#
#   First observed in the GPT DAAFBench smoke battery (2026-07-09/10): GPT
#   models fill the optional `isolation` param on every Agent dispatch;
#   the value "remote" hung case pc-03 reproducibly at both 300s and 600s
#   timeouts (evidence: research/2026-07-09_FrameworkDev_GPTBenchSmoke/
#   SESSION_NOTES.md Issue #2). Claude models do not normally fill this
#   param, so the hook is inert for them.
#
# DECISION
#   tool_input.isolation == "remote"  -> DENY with corrective guidance
#   anything else (absent, worktree)  -> ALLOW (exit 0, no JSON)
#
# FAIL-OPEN RATIONALE
#   This is an availability guard (prevents a hang), not a safety boundary.
#   Missing jq, malformed stdin, or any unexpected error ALLOWS the dispatch
#   — mirroring enforce-model-ceiling.sh's documented fail-open convention.
#
# INPUT   JSON on stdin: tool_input.isolation (among other fields)
# OUTPUT  Allow: exit 0 (no JSON). Deny: permissionDecision=deny JSON
#         (the convention for Task/Agent-tool hooks).
#
# DEPLOYMENT
#   Authored as a session-workspace deliverable
#   (research/2026-07-09_FrameworkDev_GPTBenchSmoke/deliverables/), deployed
#   to .claude/hooks/ and registered in settings.json under PreToolUse
#   matcher "Task|Agent" with explicit user permission (2026-07-10).
# ---------------------------------------------------------------------------

set -uo pipefail
trap 'echo "block-remote-isolation: unexpected error; allowing dispatch (fail-open availability guard)" >&2; exit 0' ERR

if ! command -v jq >/dev/null 2>&1; then
  echo "block-remote-isolation: jq not found; allowing dispatch (fail-open)" >&2
  exit 0
fi

INPUT=$(cat)
ISOLATION=$(echo "$INPUT" | jq -r '.tool_input.isolation // empty' 2>/dev/null) || ISOLATION=""

if [ "$ISOLATION" = "remote" ]; then
  jq -n '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": "isolation: \"remote\" requests a remote cloud environment that is unavailable inside the DAAF container — the dispatch would hang forever. Re-dispatch this subagent WITHOUT the isolation parameter (omit it entirely; do not substitute \"worktree\", which hides untracked project files from the subagent)."
    }
  }'
  exit 0
fi

exit 0
