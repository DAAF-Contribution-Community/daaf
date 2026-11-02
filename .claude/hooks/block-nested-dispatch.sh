#!/usr/bin/env bash
# block-nested-dispatch.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   PreToolUse hook for Agent/Task dispatches: DENY any dispatch that
#   originates INSIDE a subagent. In DAAF, all dispatch authority belongs to
#   the orchestrator — a subagent that needs more work done returns that work
#   to the orchestrator for redelegation (the early-return protocol) rather
#   than spawning its own nested subagents.
#
#   Claude Code lets subagents spawn their own subagents at its default
#   spawn depth of 3 (Claude Code environment-variables docs, verified
#   2026-11-01). DAAF prevents that in three layers: (1) the harness
#   spawn-depth limit — settings.json env sets
#   CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1, and with it subagents receive no
#   Agent or Task tool (observed 2026-11-02, Claude Code 2.1.281); (2) DAAF's
#   named agents each carry an explicit `tools:` list that omits Agent/Task;
#   (3) this hook, the backstop. Without the depth limit, the generic built-in
#   types DAAF sanctions (`general-purpose` = "all tools", and `Plan`) carry
#   no DAAF-authored `tools:` list, and a `general-purpose` subagent can nest
#   (observed 2026-07-16); this hook covers that case should the depth limit
#   ever be lifted or regress. Scope caveat: this layered prevention covers
#   SPAWN-style dispatch (the Task/Agent tool matchers this hook binds).
#   Primitives that route work to already-running agents (e.g. a
#   SendMessage-style tool) do not match Task/Agent and are governed by the
#   agents' tools: lists alone.
#
# CALLER DETECTION
#   The hook's stdin JSON carries two caller-identifying fields (the same
#   general hook-JSON contract that context-reporter.sh and audit-log.sh
#   already consume):
#     agent_id   — present ONLY inside a subagent call; absent on the main
#                  (orchestrator) thread.
#     agent_type — the subagent's type inside a subagent call; absent on the
#                  main thread, except in a session started with --agent,
#                  where it names that agent (Claude Code hooks reference,
#                  verified 2026-11-02). DAAF does not start sessions with
#                  --agent; one that did would have every orchestrator
#                  dispatch denied here. audit-log.sh writes "orchestrator"
#                  into its log itself; the field is not sent that way.
#
# DECISION
#   AGENT_ID   = .agent_id   // empty
#   AGENT_TYPE = .agent_type // empty
#   DENY if AGENT_ID is non-empty OR (AGENT_TYPE is non-empty AND
#     != "orchestrator") — i.e. the call came from inside a subagent.
#   Otherwise (both empty, or agent_type literally "orchestrator") ALLOW via a
#   silent exit 0.
#
#   The `!= "orchestrator"` carve-out is deliberate future-proofing: if a
#   future harness version ever starts sending agent_type:"orchestrator"
#   literally on main-thread calls, the guard must not self-block the
#   orchestrator. Both signals are checked (belt-and-suspenders): agent_id is
#   the documented present-only-in-subagent marker, and agent_type is the
#   always-present positive-value marker — either one identifying a subagent
#   caller triggers the deny.
#
#   ASSUMPTION (single-literal carve-out): the allow-set is exactly the
#   lowercase literal "orchestrator" — deliberately narrow. The harness sends
#   no agent_type on main-thread calls outside --agent sessions (observed
#   2026-07-16; audit-log.sh synthesizes the "orchestrator" default itself),
#   so this branch does not fire. If a harness starts labeling main-thread
#   calls with any OTHER value or casing (e.g. "claude", "Orchestrator"), or
#   a session is started with --agent, this hook hard-DENIES every
#   orchestrator dispatch — a pipeline-halting failure, NOT a fail-open. If all
#   dispatches suddenly deny after a harness upgrade, re-verify the on-wire
#   contract here first. Do NOT casually broaden the allow-set as a fix:
#   "claude" is a dispatchable SUBAGENT type in this harness, so whitelisting
#   it would reopen the nesting hole this hook exists to close.
#
# FAIL-OPEN RATIONALE (deliberate divergence from the fail-closed convention)
#   This is an ORCHESTRATION-DISCIPLINE guard, not a safety boundary. The DAAF
#   safety hooks (bash-safety.sh, enforce-single-command.sh,
#   enforce-file-first.sh) fail CLOSED because allowing an unsafe command is
#   high-cost and irreversible. Here the "violation" is merely a subagent
#   spawning a bounded nested subagent (only possible if the harness depth
#   limit is lifted) instead of returning the work upward — an
#   architectural-cleanliness concern, not a security one. A
#   nested agent that does slip through still runs under bash-safety.sh,
#   enforce-single-command.sh, every settings.json deny rule, and the model
#   ceiling — all of which apply INSIDE subagents. Blocking legitimate
#   orchestrator dispatches whenever jq is missing or stdin is malformed would
#   be wildly disproportionate: it would halt the entire pipeline over a
#   bookkeeping failure. So every uncertain path ALLOWS (exit 0): missing jq,
#   empty or malformed stdin, and the ERR trap all fall through to allow. This
#   is intentional and documented; do not "harden" it to fail-closed without
#   revisiting this rationale. (Mirrors enforce-model-ceiling.sh and
#   block-remote-isolation.sh, the other two fail-open dispatch guards.)
#
# INPUT   JSON on stdin: agent_id, agent_type (among other fields).
# OUTPUT  Allow: exit 0 (no JSON). Deny: JSON permissionDecision=deny
#         (the convention for Task/Agent-tool hooks, per enforce-explore-model.sh
#         and enforce-model-ceiling.sh).
#
# REGISTRATION
#   Registered in .claude/settings.json under both the "Task" and "Agent"
#   PreToolUse matchers, alongside the four other dispatch hooks. Hooks are
#   changed only by the user (CLAUDE.md § Safety-System Integrity).
#   Regression tests: tests/bash/block_nested_dispatch.bats.
# ---------------------------------------------------------------------------

# -u: catch unset-variable typos. Deliberately omit -e: this hook inspects
# state and decides allow/deny itself; a non-zero from any probe must not
# abort into an unintended state. All paths exit explicitly.
set -uo pipefail

# Fail-open ERR trap: any unexpected failure allows the dispatch (orchestration
# guard, not a safety boundary — see FAIL-OPEN RATIONALE above).
trap 'echo "block-nested-dispatch: unexpected error; allowing dispatch (fail-open orchestration guard)" >&2; exit 0' ERR

# --- Dependency check: jq. Missing jq -> allow (fail-open). ---
if ! command -v jq >/dev/null 2>&1; then
  echo "block-nested-dispatch: jq not found; allowing dispatch (fail-open orchestration guard)" >&2
  exit 0
fi

# --- Read stdin ---
INPUT=$(cat)
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty' 2>/dev/null) || AGENT_ID=""
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null) || AGENT_TYPE=""

# ---------------------------------------------------------------------------
# deny: emit the Task/Agent-tool deny JSON and exit 0 (the hook itself
# succeeded; the JSON carries the block decision to Claude Code).
# Arg $1: human-readable reason shown to the dispatching subagent.
# ---------------------------------------------------------------------------
deny() {
  local reason="$1"
  jq -n --arg r "$reason" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": $r
    }
  }'
  exit 0
}

# --- Caller check: deny when the dispatch originates inside a subagent ---
# agent_id present -> definitively a subagent call.
# agent_type present and not literally "orchestrator" -> also a subagent call
# (the carve-out future-proofs against a harness that sends "orchestrator"
# literally on the main thread).
if [ -n "$AGENT_ID" ] || { [ -n "$AGENT_TYPE" ] && [ "$AGENT_TYPE" != "orchestrator" ]; }; then
  deny "DAAF policy: subagents may not launch nested subagents — all dispatch authority belongs to the orchestrator. Complete what you can with your own tools and return remaining work to the orchestrator for redelegation (early-return protocol, CLAUDE.md § Context & Session Health)."
fi

# --- Main-thread (orchestrator) dispatch -> allow ---
exit 0
