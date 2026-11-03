#!/usr/bin/env bash
# block-webfetch.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   PreToolUse hook (matcher: WebFetch) that DENIES every WebFetch call and
#   redirects the agent to DAAF's provenance-preserving fetch utility.
#
#   Claude Code's built-in WebFetch is a summarizer, not a content retriever:
#   for most fetches it runs the calling agent's prompt against the fetched
#   page in a separate model call and returns that call's result rather than
#   the page, and it
#   reads at most 100,000 characters of a page per call (verified against the
#   Claude Code tools reference on 2026-11-02). Community reverse-engineering
#   also reports a Haiku model and a 125-character quote cap (not verified).
#   "Quotes" from WebFetch may therefore be paraphrase, which conflicts
#   directly with DAAF's evidence-graded quoting doctrine (CLAUDE.md
#   § Execution Philosophy). Its failures can also mislead (community reports
#   of Cloudflare-gated failures blamed on the user's network, and hard domain
#   blocks; not verified). DAAF replaces it with `scripts/web_fetch.sh`, which
#   writes the raw response plus a deterministic extract and a provenance
#   manifest to disk.
#
# WHY A HOOK AND NOT A permissions.deny RULE
#   Enforcement is this hook alone: settings.json has no WebFetch deny rule.
#   The hook's value is its redirect message, which teaches the agent the
#   fetch protocol, and a deny rule could answer the call with a bare
#   permission denial instead. Which one the agent would see with both in
#   place is not verified (the Claude Code hooks reference, read on
#   2026-11-02, says permission denials still fire PreToolUse, which suggests
#   the hook would run too). The single layer is a deliberate departure from
#   the usual defense-in-depth pattern.
#
# FAIL-CLOSED RATIONALE AND GUARANTEE
#   This is a doctrine/boundary guard: WebFetch must never reach the network,
#   because its output cannot satisfy DAAF's quoting standard. Unlike the
#   fail-OPEN dispatch guards (block-nested-dispatch.sh et al.), every path
#   through this hook DENIES. The guarantee is precise, and holds on all three
#   paths — none of which depends on stdin content, since the hook is
#   registered under the WebFetch matcher alone and the decision is therefore
#   unconditional:
#     1. NORMAL (jq present) — emit the JSON decision
#        `permissionDecision: deny` with the full instructional reason, and
#        exit 0. This is the preferred path: the richer message reaches the
#        agent as the tool result.
#     2. jq ABSENT — jq is the hook's only structural dependency, and it is
#        checked with `command -v` BEFORE any use. Without it the JSON
#        decision cannot be serialized, so the hook falls back to Claude
#        Code's documented plain-text block: the same redirect message on
#        stderr plus `exit 2`. Exit 2 blocks the tool call regardless of
#        whether stdout carries valid decision JSON (verified against the
#        Claude Code hooks reference on 2026-11-02), so a jq-less container
#        still cannot reach the network. It does NOT silently allow.
#     3. UNEXPECTED ERROR — the ERR trap takes the same jq-free stderr +
#        exit 2 path, so it too blocks whether or not jq is installed.
#   Blocking a fetch on error is cheap (the agent retries via web_fetch.sh);
#   allowing an unattributable paraphrase through is the costly outcome.
#
# INPUT   JSON on stdin (standard PreToolUse hook contract).
# OUTPUT  Deny, by either of two equivalent mechanisms:
#         - jq present: JSON permissionDecision=deny on stdout, exit 0 (the
#           convention for tool-call hooks, per enforce-explore-model.sh /
#           deny-claude-code-guide.sh).
#         - jq absent, or unexpected error: redirect message on stderr,
#           exit 2 (the plain-text block convention, per bash-safety.sh).
#
# REGISTRATION (user-only: .claude/hooks/ is deny-protected)
#   .claude/settings.json, PreToolUse, matcher "WebFetch", timeout 5.
#   Regression tests: tests/bash/block_webfetch.bats.
# ---------------------------------------------------------------------------

# -u catches unset-variable typos; -o pipefail surfaces pipeline failures.
# Deliberately omit -e: this hook emits its own decision and must not abort
# into an unintended state. The ERR trap below fails CLOSED (deny).
set -uo pipefail

# The instructional redirect message, defined BEFORE the ERR trap so that both
# the trap and the jq-free fallback can reference it (single source of truth).
read -r -d '' REASON <<'MSG' || true
WebFetch is disabled in DAAF: it usually returns an AI paraphrase of the page (not the source text) and fails opaquely, which conflicts with DAAF's evidence-graded quoting doctrine. Use the DAAF fetch protocol instead:

  bash /daaf/scripts/web_fetch.sh <URL> <dest-dir>

It saves the raw response, a deterministic extract, and a provenance manifest (URL, timestamp, HTTP status, SHA-256s) under the destination directory. Read the .md extract; grep the raw .html when the extract looks thin. See the `web-retrieval` skill for the full protocol, failure-handling table, and size rules.

WebSearch is available for finding URLs.
MSG

# Fail-closed ERR trap. Deliberately jq-FREE: an error path that serializes its
# deny with `jq -n` would itself fail (silently allowing) on a container missing
# jq — precisely the case the trap exists to cover. stderr + exit 2 blocks
# unconditionally and needs nothing but bash builtins.
trap 'printf "%s\n" "$REASON" >&2; exit 2' ERR

# Drain stdin so the harness pipe closes cleanly (contents are not needed —
# this hook denies unconditionally for the WebFetch matcher).
INPUT=$(cat)
: "${INPUT:=}"

# --- Dependency check (fail-closed, BEFORE any use of jq) ---
# Without jq the JSON decision cannot be serialized. Falling through to `jq -n`
# here would exit 0 with no decision on stdout, which the harness reads as
# ALLOW — a silent bypass of a boundary guard. Block in plain text instead.
if ! command -v jq >/dev/null 2>&1; then
    printf '%s\n' "$REASON" >&2
    exit 2
fi

jq -n --arg r "$REASON" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": $r
  }
}'

exit 0
