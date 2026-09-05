#!/usr/bin/env bash
# enforce-model-ceiling.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   Enforce DAAF's session-model *ceiling* on subagent dispatches: a subagent
#   must never run on a HIGHER model tier than the current main session model.
#   Users who deliberately chose a cheaper session model (cost control) should
#   not have that choice silently overridden by a subagent dispatched — via
#   frontmatter default or per-dispatch parameter — on a pricier tier. The
#   orchestrator cannot reliably know its own session model from context, so
#   this hook resolves the ceiling deterministically from the transcript and
#   denies over-tier dispatches with an instruction to re-dispatch at the
#   stated tier.
#
#   Ranks (by substring match on the resolved model id/alias):
#     haiku = 1, sonnet = 2, opus = 3, fable = 4
#   A requested rank strictly greater than the session rank is denied.
#
# DECISION ORDER (first match wins)
#   a. CLAUDE_CODE_SUBAGENT_MODEL set  -> ALLOW. This env var outranks the
#      per-dispatch parameter and frontmatter (official 4-level resolution
#      order), so it globally pins every subagent's model; enforcing a ceiling
#      would be moot and misleading.
#   b. ANTHROPIC_DEFAULT_OPUS_MODEL or ANTHROPIC_DEFAULT_SONNET_MODEL set
#      -> ALLOW. The user has deliberately remapped the tier aliases to their
#      own (possibly non-Claude) models; we cannot rank arbitrary custom slugs.
#   c. Resolve the REQUESTED model: tool_input.model if present, else the
#      `model:` field parsed from the dispatched agent's frontmatter
#      (/daaf/.claude/agents/{subagent_type}.md). Missing file, absent field,
#      or `inherit` -> ALLOW (nothing to constrain; inherit tracks the session).
#   d. Resolve the SESSION model from the transcript (same extraction approach
#      as cache_model() in context-reporter.sh), then fall back to the model
#      cache file /tmp/claude-model-${SESSION_ID}. Neither available -> ALLOW
#      (fail-open) with a stderr note.
#   e. Classify both models into ranks by substring match.
#   f. Session model detected but matches NO Claude family (non-Claude provider,
#      e.g. GLM via OpenRouter) AND requested model IS Claude-family -> DENY
#      (the requested Claude alias almost certainly does not exist on the user's
#      endpoint; point them at the remap/flatten env vars).
#   g. Requested rank > session rank -> DENY (re-dispatch at the session tier).
#   h. Otherwise -> ALLOW.
#
# FAIL-OPEN RATIONALE (deliberate divergence from the fail-closed convention)
#   This hook is a COST-CONTROL guard, not a safety boundary. The DAAF safety
#   hooks (bash-safety.sh, enforce-single-command.sh, enforce-file-first.sh)
#   fail CLOSED because the cost of allowing an unsafe command is high and
#   irreversible. Here the "violation" is merely spending more money than the
#   user's session-model choice implied — a bounded, recoverable cost. Blocking
#   ALL subagent work whenever the session model cannot be parsed, jq is
#   missing, or the agent file is unreadable would be wildly disproportionate:
#   it would halt the entire pipeline over a bookkeeping failure. So every
#   uncertain path ALLOWS (exit 0) and, where useful, notes why on stderr. The
#   ERR trap likewise allows. This is intentional and documented; do not
#   "harden" it to fail-closed without revisiting this rationale.
#
# INPUT   JSON on stdin: session_id, transcript_path,
#         tool_input.subagent_type, tool_input.model
# OUTPUT  Allow: exit 0 (no JSON). Deny: JSON permissionDecision=deny
#         (the convention for Task/Agent-tool hooks, per enforce-explore-model.sh).
#
# DEPLOYMENT
#   This script is a workspace deliverable. Human deployment into
#   .claude/hooks/ (deny-protected) plus settings.json registration is
#   documented in DEPLOYMENT.md alongside this file.
# ---------------------------------------------------------------------------

# -u: catch unset-variable typos. Deliberately omit -e: this hook inspects
# state and decides allow/deny itself; a non-zero from any probe must not
# abort into an unintended state. All paths exit explicitly.
set -uo pipefail

# Fail-open ERR trap: any unexpected failure allows the dispatch (cost guard,
# not a safety boundary — see FAIL-OPEN RATIONALE above).
trap 'echo "enforce-model-ceiling: unexpected error; allowing dispatch (fail-open cost guard)" >&2; exit 0' ERR

readonly AGENTS_DIR="${DAAF_ENFORCE_MODEL_CEILING_AGENTS_DIR:-/daaf/.claude/agents}"

# --- Dependency check: jq. Missing jq -> allow (fail-open). ---
if ! command -v jq >/dev/null 2>&1; then
  echo "enforce-model-ceiling: jq not found; allowing dispatch (fail-open cost guard)" >&2
  exit 0
fi

# --- Read stdin ---
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"' 2>/dev/null) || SESSION_ID="default"
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null) || TRANSCRIPT_PATH=""
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null) || SUBAGENT_TYPE=""
REQUESTED_MODEL=$(echo "$INPUT" | jq -r '.tool_input.model // empty' 2>/dev/null) || REQUESTED_MODEL=""

# ---------------------------------------------------------------------------
# deny: emit the Task/Agent-tool deny JSON and exit 0 (the hook itself
# succeeded; the JSON carries the block decision to Claude Code).
# Arg $1: human-readable reason shown to the orchestrator.
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

# ---------------------------------------------------------------------------
# rank_of: classify a model id/alias into a tier rank by substring match.
# Echoes 1..4 for a known Claude family, or 0 when no family matches
# (empty input or a non-Claude provider slug).
# ---------------------------------------------------------------------------
rank_of() {
  local m
  m=$(echo "$1" | tr '[:upper:]' '[:lower:]')
  case "$m" in
    *haiku*)  echo 1 ;;
    *sonnet*) echo 2 ;;
    *opus*)   echo 3 ;;
    *fable*)  echo 4 ;;
    *)        echo 0 ;;
  esac
}

# --- (a) Global subagent-model override pins everything: nothing to enforce ---
if [ -n "${CLAUDE_CODE_SUBAGENT_MODEL:-}" ]; then
  exit 0
fi

# --- (b) User-configured alias remapping: cannot rank custom models ---
if [ -n "${ANTHROPIC_DEFAULT_OPUS_MODEL:-}" ] || [ -n "${ANTHROPIC_DEFAULT_SONNET_MODEL:-}" ]; then
  exit 0
fi

# --- (c) Resolve the requested model ---
# Precedence mirrors Claude Code's own resolution: per-dispatch parameter
# (tool_input.model) outranks the agent's frontmatter default.
if [ -z "$REQUESTED_MODEL" ] && [ -n "$SUBAGENT_TYPE" ]; then
  AGENT_FILE="${AGENTS_DIR}/${SUBAGENT_TYPE}.md"
  if [ -f "$AGENT_FILE" ]; then
    # Parse the first `model:` line inside the leading YAML frontmatter block.
    # Frontmatter is delimited by the first two `---` lines; awk restricts the
    # scan to that block so a `model:` mention in prose can't be misread.
    # Assumes an unquoted single-token value: `model: opus   # comment` -> `opus`
    # ($2 is the value; trailing inline comments fall into $3+ and are dropped).
    # Quoted or multi-word values are NOT supported by this parser.
    REQUESTED_MODEL=$(awk '
      NR==1 && $0=="---" { infm=1; next }
      infm && $0=="---"  { exit }
      infm && $1=="model:" { print $2; exit }
    ' "$AGENT_FILE" 2>/dev/null) || REQUESTED_MODEL=""
  fi
  # Missing agent file -> REQUESTED_MODEL stays empty -> allow below.
fi

# Absent or `inherit` -> nothing to constrain (inherit tracks the session model).
if [ -z "$REQUESTED_MODEL" ] || [ "$REQUESTED_MODEL" = "inherit" ]; then
  exit 0
fi

# --- (d) Resolve the session model: transcript first, then cache file ---
SESSION_MODEL=""
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
  # Same extraction approach as context-reporter.sh cache_model(): the most
  # recent assistant message carrying a `.message.model` field. tail -50 keeps
  # this cheap — the latest usage/model entry is always near the file end.
  SESSION_MODEL=$(tail -50 "$TRANSCRIPT_PATH" 2>/dev/null | jq -r '
    select(.message.model and .message.model != "<synthetic>") | .message.model
  ' 2>/dev/null | tail -1) || SESSION_MODEL=""
fi

if [ -z "$SESSION_MODEL" ]; then
  MODEL_CACHE="/tmp/claude-model-${SESSION_ID}"
  if [ -f "$MODEL_CACHE" ]; then
    SESSION_MODEL=$(cat "$MODEL_CACHE" 2>/dev/null) || SESSION_MODEL=""
  fi
fi

# Session model undetectable -> fail-open (cost guard, not a safety boundary).
if [ -z "$SESSION_MODEL" ]; then
  echo "enforce-model-ceiling: session model undetectable; allowing dispatch (fail-open cost guard)" >&2
  exit 0
fi

# --- (e) Classify both models ---
REQ_RANK=$(rank_of "$REQUESTED_MODEL")
SESS_RANK=$(rank_of "$SESSION_MODEL")

# --- (f) Non-Claude session + Claude-family request -> deny with remap guidance ---
if [ "$SESS_RANK" -eq 0 ] && [ "$REQ_RANK" -gt 0 ]; then
  deny "Session runs a non-Claude model (${SESSION_MODEL}) — the requested Claude tier '${REQUESTED_MODEL}' does not exist on this endpoint and would fail or silently downgrade. Either re-dispatch with model: ${SESSION_MODEL} explicitly, or configure ANTHROPIC_DEFAULT_OPUS_MODEL / ANTHROPIC_DEFAULT_SONNET_MODEL (or CLAUDE_CODE_SUBAGENT_MODEL) in environment_settings.txt so DAAF's two-tier routing maps to your models — see the model routing section there."
fi

# If the requested model isn't a recognized Claude family (custom/non-Claude
# slug), we can't rank it against the session tier — allow (fail-open).
if [ "$REQ_RANK" -eq 0 ]; then
  exit 0
fi

# --- (g) Ceiling check: requested tier must not exceed the session tier ---
if [ "$REQ_RANK" -gt "$SESS_RANK" ]; then
  deny "Session model is ${SESSION_MODEL} — subagents must not exceed the session tier. Re-dispatch this ${SUBAGENT_TYPE:-subagent} with model: ${SESSION_MODEL} (or an equal-or-lower Claude tier)."
fi

# --- (h) Within ceiling -> allow ---
exit 0
