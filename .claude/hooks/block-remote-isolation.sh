#!/usr/bin/env bash
# block-remote-isolation.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   PreToolUse hook for Agent/Task dispatches: STRIP the optional isolation
#   parameter (any value) and ALLOW the dispatch, so the subagent runs
#   in-place instead of in an isolated worktree/remote environment.
#
#   NOTE ON FILENAME: this file is still named block-remote-isolation.sh for
#   registration stability (settings.json PreToolUse matchers reference it by
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
#   Both values are undesirable in DAAF, so the isolation KEY is stripped
#   whenever present, regardless of its value.
#
# WHY STRIP INSTEAD OF DENY
#   First observed in the GPT DAAFBench smoke battery (2026-07-09/10): GPT
#   (OpenAI) models fill the optional `isolation` param on EVERY Agent
#   dispatch — and, critically, re-fill it on every retry after a deny. The
#   prior DENY-on-isolation behavior therefore produced deny->retry loops that
#   exhausted the turn budget without ever dispatching a subagent (observed:
#   DAAFBench dispatch_compliance scored agent_dispatched 0/12 for
#   GPT-5.6-Luna). Stripping the param lets the dispatch proceed in-place on
#   the first try, for all models, with no retry loop. Claude models rarely
#   fill this param, so the hook is usually inert for them; when they do fill
#   it, the strip applies uniformly.
#
# DECISION  (keyed on KEY PRESENCE, not truthiness — see the guard below)
#   tool_input has the "isolation" key (ANY value: "remote", "worktree", an
#     unknown string, "", null, false, an object, or an array) -> ALLOW +
#     strip (isolation key removed from the reconstructed tool_input)
#   isolation key absent (or tool_input missing / not an object) -> ALLOW
#     (exit 0, no JSON)
#
#   Note: this INCLUDES isolation:"" — an empty string now STRIPS (whereas a
#   truthiness guard would pass it through). strip-the-key-whenever-present is
#   a cleaner contract, matches the provider shim sanitizer exactly
#   (anthropic_openai_shim.py:996 — `if tool_name in ("Agent","Task") and
#   "isolation" in args: args.pop("isolation")`), and an empty string would
#   fail the Agent tool's enum schema anyway. This shared contract with the
#   shim is deliberate.
#
# MECHANISM
#   PreToolUse hooks may mutate tool input via
#   hookSpecificOutput.updatedInput, combinable with permissionDecision:
#   "allow" in the same response. Per the official docs
#   (https://code.claude.com/docs/en/hooks.md): "PreToolUse: updatedInput
#   directly under hookSpecificOutput REPLACES a tool's arguments before it
#   runs." updatedInput is a full REPLACEMENT of tool_input, NOT a merge —
#   there is no documented JSON merge-patch / null-deletion mechanism, so
#   `null` is NOT a deletion marker. Whatever object we emit under
#   updatedInput becomes the ENTIRE new tool_input. Therefore the hook must
#   emit the COMPLETE original tool_input reconstructed with only `isolation`
#   removed (jq `del(.isolation)`) — anything less drops the required fields
#   (description, prompt, subagent_type, ...) and the Agent/Task tool rejects
#   the dispatch as schema-invalid.
#
# DEFECT HISTORY
#   v3 (commit 3444e11) emitted a PARTIAL object `{"isolation": null}` under
#   the incorrect assumption that updatedInput is merge-patched into
#   tool_input (with null deleting the field). Because updatedInput actually
#   REPLACES tool_input wholesale, this replaced the entire Agent/Task payload
#   with just `{"isolation": null}`, dropping `description` and `prompt` and
#   breaking EVERY isolation-filled dispatch with a schema validation error
#   ("The required parameter 'description' is missing / The required parameter
#   'prompt' is missing"). Fixed in v4 by full-object reconstruction:
#   `.tool_input | del(.isolation)`.
#   Regression tests: tests/bash/block_remote_isolation.bats.
#
#   v4.1 (2026-07-13): advisory wording only — no behavioral change. During
#   cross-container validation, a GPT session issued FIVE redundant re-dispatches
#   after misreading the sanitized (isolation-free) rendered tool input as a
#   failed parameter submission: the old advisory said "do not re-add the
#   isolation parameter on retry" but never said the dispatch itself had
#   SUCCEEDED, so the model retried the whole dispatch. The additionalContext
#   now leads with dispatch success and explicitly instructs no re-dispatch.
#   The anti-re-dispatch phrases are pinned by the regression tests.
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
#         Strip: permissionDecision=allow + updatedInput=(full tool_input with
#         isolation removed) JSON.
#
# DEPLOYMENT
#   Authored as a session-workspace deliverable
#   (research/2026-07-12_FrameworkDev_AgentDispatchHookFix/deliverables/),
#   deployed to .claude/hooks/ (human-only, permission-gated path). The hook
#   is registered under TWO separate PreToolUse matchers — "Task"
#   (settings.json line ~162) and "Agent" (line ~187) — not a single
#   "Task|Agent" matcher. Filename unchanged on deploy so no settings.json
#   edit is required.
# ---------------------------------------------------------------------------

set -uo pipefail
trap 'echo "block-remote-isolation: unexpected error; allowing dispatch (fail-open availability guard)" >&2; exit 0' ERR

if ! command -v jq >/dev/null 2>&1; then
  echo "block-remote-isolation: jq not found; allowing dispatch (fail-open)" >&2
  exit 0
fi

INPUT=$(cat)
# Gate on KEY PRESENCE, not truthiness. jq's `//` alternative operator treats
# JSON `false` and `null` as empty, so a truthiness guard would leak
# isolation:false / isolation:null through UNSTRIPPED — contradicting the
# strip-any-value contract and likely still failing the Agent tool's enum
# schema downstream. `has("isolation")` (guarded by `(.tool_input? | type) ==
# "object"`) strips whenever the key is present regardless of value, matching
# the provider shim sanitizer exactly. Non-object or missing tool_input, or
# malformed stdin, yields "no" (via the `?` operator / 2>/dev/null path) ->
# silent exit 0.
HAS_ISOLATION=$(echo "$INPUT" | jq -r 'if (.tool_input? | type) == "object" and (.tool_input | has("isolation")) then "yes" else "no" end' 2>/dev/null) || HAS_ISOLATION="no"

if [ "$HAS_ISOLATION" = "yes" ]; then
  # updatedInput REPLACES tool_input, so emit the FULL original tool_input with
  # only `isolation` removed — reconstructed in a single jq pass over $INPUT.
  # No shell string interpolation into JSON: additionalContext derives the
  # stripped value from .tool_input.isolation within the same jq program.
  echo "$INPUT" | jq '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "updatedInput": (.tool_input | del(.isolation)),
      "additionalContext": ("DAAF stripped the isolation parameter (was \"" + (.tool_input.isolation | tostring) + "\") and this dispatch has proceeded successfully without it — the subagent runs in-place. If the rendered tool input no longer shows the isolation field, that is this sanitization working as intended, not a failed submission: do not re-dispatch this subagent, and do not re-add the isolation parameter on future dispatches (it will be stripped again). Background: isolated worktrees check out the repo default branch (stale framework snapshot, no visibility of untracked files or uncommitted work); \"remote\" cloud environments are unavailable in the container and hang forever.")
    }
  }'
  exit 0
fi

exit 0
