#!/usr/bin/env bash
# block-remote-isolation.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   PreToolUse hook for Agent/Task dispatches: STRIP the optional isolation
#   parameter (any value) and ALLOW the dispatch, so the subagent runs
#   in-place instead of in an isolated worktree/remote environment.
#
#   NOTE ON FILENAME: the name says block, but the hook strips the parameter
#   and allows the dispatch; the name stays because settings.json registers
#   the hook by file name.
#
#   isolation: "remote" — remote cloud environments are gated/unavailable in
#   the DAAF container, and such dispatches never return a tool_result — the
#   session waits silently until killed.
#
#   isolation: "worktree" — new worktrees branch from
#   origin/<default-branch> unless the worktree.baseRef setting is "head"
#   (Claude Code settings docs, verified 2026-11-02), and DAAF sets no
#   baseRef. So a subagent runs inside the remote default branch's framework
#   snapshot (its CLAUDE.md, hooks and agents), NOT the live session branch,
#   and cannot see untracked files (benchmark fixtures, uncommitted work).
#   Worktrees also accumulate under .claude/worktrees/ and require manual
#   cleanup.
#
#   Both values are undesirable in DAAF, so the isolation KEY is stripped
#   whenever present, regardless of its value.
#
# WHY STRIP INSTEAD OF DENY
#   GPT (OpenAI) models fill the optional `isolation` param on EVERY Agent
#   dispatch and fill it again on every retry after a deny, so a deny loops
#   until the turn budget runs out without a subagent ever being dispatched
#   (observed 2026-07-10 in DAAFBench: GPT-5.6-Luna scored agent_dispatched
#   0/12).
#   Stripping the param lets the dispatch proceed in-place on the first try,
#   for all models, with no retry loop. Claude models rarely fill this param,
#   so the hook is usually inert for them; when they do fill it, the strip
#   applies uniformly.
#
# DECISION  (keyed on KEY PRESENCE, not truthiness — see the guard below)
#   tool_input has the "isolation" key (ANY value: "remote", "worktree", an
#     unknown string, "", null, false, an object, or an array) -> ALLOW +
#     strip (isolation key removed from the reconstructed tool_input)
#   isolation key absent (or tool_input missing / not an object) -> ALLOW
#     (exit 0, no JSON)
#
#   Note: this INCLUDES isolation:"" — an empty string STRIPS (a truthiness
#   guard would pass it through). Strip-the-key-whenever-present is a cleaner
#   contract, matches the provider shim's tool-argument sanitizer exactly
#   (scripts/provider_shim/anthropic_openai_shim.py, which pops isolation from
#   Agent and Task calls whatever its value), and an empty string would fail
#   the Agent tool's enum schema anyway. This shared contract with the shim is
#   deliberate.
#
# MECHANISM
#   PreToolUse hooks may mutate tool input via
#   hookSpecificOutput.updatedInput, combinable with permissionDecision:
#   "allow" in the same response. The Claude Code hooks reference
#   (https://code.claude.com/docs/en/hooks, verified 2026-11-02) says:
#   "PreToolUse: updatedInput directly under hookSpecificOutput replaces a
#   tool's arguments before it runs." updatedInput is a full REPLACEMENT of
#   tool_input, NOT a merge —
#   there is no documented JSON merge-patch / null-deletion mechanism, so
#   `null` is NOT a deletion marker. Whatever object we emit under
#   updatedInput becomes the ENTIRE new tool_input. Therefore the hook must
#   emit the COMPLETE original tool_input reconstructed with only `isolation`
#   removed (jq `del(.isolation)`) — anything less drops the required fields
#   (description, prompt, subagent_type, ...) and the Agent/Task tool rejects
#   the dispatch as schema-invalid.
#
#   A partial object such as `{"isolation": null}` would therefore replace
#   the whole Agent/Task payload and drop `description` and `prompt`, failing
#   the dispatch's schema validation.
#
# ADVISORY
#   The additionalContext opens by saying the dispatch succeeded and tells the
#   model not to re-dispatch: a model that sees the isolation field missing
#   from the rendered tool input otherwise reads it as a failed submission and
#   retries the whole dispatch. tests/bash/block_remote_isolation.bats pins
#   both phrases.
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
# REGISTRATION
#   Registered under two PreToolUse matchers in .claude/settings.json,
#   "Task" and "Agent" (not one "Task|Agent" matcher). Hooks are changed only
#   by the user (CLAUDE.md § Safety-System Integrity). Regression tests:
#   tests/bash/block_remote_isolation.bats.
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
