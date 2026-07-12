#!/usr/bin/env bash
# block-remote-isolation.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   PreToolUse hook for Agent/Task dispatches: STRIP the optional isolation
#   parameter (any value) and ALLOW the dispatch, so the subagent runs
#   in-place instead of in an isolated worktree/remote environment.
#
#   NOTE ON FILENAME: this file is still named block-remote-isolation.sh for
#   registration stability (settings.json PreToolUse matcher references it by
#   name). "block" is now a slight misnomer — the hook no longer DENIES; it
#   SANITIZES (strips the param) and allows. The name is retained deliberately
#   to avoid a settings.json edit and re-registration.
#
#   isolation: "remote" — remote cloud environments are gated/unavailable in
#   the DAAF container, and such dispatches never return a tool_result — the
#   session waits silently until killed.
#
#   isolation: "worktree" — worktrees are checked out from the repo default
#   branch (origin/main), NOT the live session branch: subagents run inside a
#   stale framework snapshot (old CLAUDE.md/hooks/agents) and cannot see
#   untracked files (benchmark fixtures, uncommitted work). Worktrees also
#   accumulate under .claude/worktrees/ and require manual cleanup.
#
#   Both values are undesirable in DAAF, so ANY non-empty isolation value is
#   stripped rather than honored.
#
# WHY STRIP INSTEAD OF DENY
#   First observed in the GPT DAAFBench smoke battery (2026-07-09/10): GPT
#   (OpenAI) models fill the optional `isolation` param on EVERY Agent
#   dispatch — and, critically, re-fill it on every retry after a deny. The
#   prior DENY-on-isolation behavior therefore produced deny->retry loops that
#   exhausted the turn budget without ever dispatching a subagent (observed:
#   DAAFBench dispatch_compliance scored agent_dispatched 0/12 for
#   GPT-5.6-Luna). Stripping the param (merge-patch it to null via
#   updatedInput) lets the dispatch proceed in-place on the first try, for all
#   models, with no retry loop. Claude models rarely fill this param, so the
#   hook is usually inert for them; when they do fill it, the strip applies
#   uniformly.
#
# DECISION
#   tool_input.isolation present AND non-empty (any value: "remote",
#     "worktree", or anything else) -> ALLOW + strip (updatedInput.isolation=null)
#   isolation absent/empty          -> ALLOW (exit 0, no JSON) — unchanged
#
# MECHANISM
#   PreToolUse hooks may mutate tool input via
#   hookSpecificOutput.updatedInput, which is MERGED into the original
#   tool_input (JSON merge-patch semantics), combinable with
#   permissionDecision:"allow" in the same response. Setting a field to null
#   removes it (merge-patch). Verified against Claude Code 2.1.187 hooks docs
#   (https://code.claude.com/docs/en/hooks.md).
#
# FAIL-OPEN RATIONALE
#   This is an availability/sanitization guard (prevents a hang and a stale
#   checkout), not a safety boundary. Missing jq, malformed stdin, or any
#   unexpected error ALLOWS the dispatch unmodified — mirroring
#   enforce-model-ceiling.sh's documented fail-open convention. Never block a
#   dispatch on hook failure.
#
# INPUT   JSON on stdin: tool_input.isolation (among other fields)
# OUTPUT  Silent allow: exit 0 (no JSON).
#         Strip: permissionDecision=allow + updatedInput.isolation=null JSON.
#
# DEPLOYMENT
#   Authored as a session-workspace deliverable
#   (research/2026-07-09_FrameworkDev_GPTBenchSmoke/deliverables/), deployed
#   to .claude/hooks/ (human-only, permission-gated path) and registered in
#   settings.json under PreToolUse matcher "Task|Agent". Filename unchanged on
#   deploy so no settings.json edit is required.
# ---------------------------------------------------------------------------

set -uo pipefail
trap 'echo "block-remote-isolation: unexpected error; allowing dispatch (fail-open availability guard)" >&2; exit 0' ERR

if ! command -v jq >/dev/null 2>&1; then
  echo "block-remote-isolation: jq not found; allowing dispatch (fail-open)" >&2
  exit 0
fi

INPUT=$(cat)
ISOLATION=$(echo "$INPUT" | jq -r '.tool_input.isolation // empty' 2>/dev/null) || ISOLATION=""

if [ -n "$ISOLATION" ]; then
  jq -n --arg iso "$ISOLATION" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "updatedInput": { "isolation": null },
      "additionalContext": ("DAAF stripped the isolation parameter (was \"" + $iso + "\"); subagents run in-place, not in an isolated worktree/remote env. Isolated worktrees check out the repo default branch (stale framework snapshot, no visibility of untracked fixtures/uncommitted work); \"remote\" cloud envs are unavailable in the container and hang forever. Do not re-add the isolation parameter on retry — it will be stripped again.")
    }
  }'
  exit 0
fi

exit 0
