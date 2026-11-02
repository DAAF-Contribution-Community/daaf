#!/usr/bin/env bash
# adjudicator-read-scope.sh
# ---------------------------------------------------------------------------
# PURPOSE
#   Agent-scoped PreToolUse hook for the citation-adjudicator agent. The agent
#   judges one citation adjudication bundle and may read nothing else: a read
#   of any other file can show it the citing context its judgment must not
#   see, and ingest refuses the whole batch on any non-bundle tool call in the
#   audit log. The agent's tool list holds only Read, but Read opens any path,
#   so this hook is the boundary that keeps it to the bundle.
#
#   ALLOWS a Read whose file_path
#     - is an absolute path that is already canonical: `realpath -m -s` (no
#       symlink resolution) and `realpath -m` (symlinks resolved) both return
#       it unchanged, so it holds no `..`, `.`, `//`, trailing slash or
#       symlink anywhere;
#     - lies under <DAAF root>/research/ (DAAF root: $CLAUDE_PROJECT_DIR, else
#       /daaf), at <project>/data/adjudication_bundles/<batch_id>.json, where
#       <batch_id> follows lit_corpus's BATCH_ID_RE ^[a-z0-9][a-z0-9_-]{0,31}$
#       (so {batch_id}_prompt.txt and every other file in the folder is
#       refused);
#     - names an existing regular file.
#   DENIES everything else: any other path, any tool other than Read, and
#   every input or environment it cannot check.
#
# SCOPE
#   Registered in .claude/agents/citation-adjudicator.md frontmatter under
#   PreToolUse with matcher "" (every tool), so a tool other than Read is
#   denied too. A call whose agent_type names a DIFFERENT agent is allowed
#   untouched: the frontmatter hook is meant to fire only for this agent, and
#   if the harness ever ran it for a sibling agent working in the same wave,
#   denying that agent's reads would break unrelated work. A call with no
#   agent_type (the main thread) is checked like an adjudicator call, so an
#   absent field cannot open the gate. That costs the main thread nothing:
#   with DAAF's CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 a dispatch runs in the
#   foreground and returns inline in the dispatching turn (observed
#   2026-09-24, Claude Code 2.1.281), so the main thread makes no tool calls
#   while the adjudicator runs.
#
# FAIL-CLOSED DESIGN
#   Every deny goes out three ways at once: a JSON permissionDecision "deny"
#   on stdout, the same reason on stderr, and exit 2. Exit 2 blocks the tool
#   call whether or not the JSON is valid, and when the JSON carries a
#   blocking decision its reason is the one shown (verified against the
#   Claude Code hooks reference, "Exit code 2", on 2026-11-02). The JSON is
#   built with printf from fixed text plus a sanitized path, never with
#   `jq -n`, so neither the deny path nor the ERR trap depends on jq. jq is
#   checked before any use; without it the hook denies.
#
# INPUT   JSON on stdin (PreToolUse contract): tool_name, tool_input.file_path,
#         agent_type, agent_id among other fields.
# OUTPUT  Allow: exit 0, no output (the normal permission flow continues).
#         Deny:  JSON deny on stdout + reason on stderr + exit 2.
#
# INSTALL ORDER (user-only: .claude/hooks/ is deny-protected)
#   When changing or reinstalling this hook, the script comes first (mode
#   100755 in git), then the frontmatter registration (see
#   agent_reference/BOUNDARIES.md § Defense-in-Depth Architecture and the
#   agent-authoring skill § Per-Agent Hooks). A registered hook whose script
#   is missing counts as a non-blocking error and the Read goes ahead
#   (Claude Code 2.1.281, which predates `onFailure: "block"`; verified
#   against the Claude Code hooks reference on 2026-11-02).
#   Regression tests: tests/bash/adjudicator_read_scope.bats.
# ---------------------------------------------------------------------------

# Deliberately omit -e: the hook decides allow or deny itself, and every
# unexpected failure goes to the fail-closed ERR trap below.
set -uo pipefail

readonly HOOK_NAME="adjudicator-read-scope"

# Fail-closed ERR trap, jq-free: a fixed JSON deny, a stderr reason, exit 2.
static_deny() {
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"The reference checker may read only its citation bundle; this call was blocked because the read-scope check could not run."}}'
    printf 'BLOCKED by %s hook: unexpected error in the read-scope check (fail-closed).\n' "$HOOK_NAME" >&2
    exit 2
}
trap static_deny ERR

# deny REASON: emit the block decision and stop. The reason is made JSON-safe
# here (control characters, double quotes and backslashes replaced) so a
# caller cannot break the JSON string even by mistake.
deny() {
    local reason="$1"
    reason="${reason//[[:cntrl:]]/ }"
    reason="${reason//[\"\\]/?}"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    printf 'BLOCKED by %s hook: %s\n' "$HOOK_NAME" "$reason" >&2
    exit 2
}

readonly RULE="It may read one file only: the bundle its prompt names, an absolute path of the form /daaf/research/<project>/data/adjudication_bundles/<batch_id>.json with no symlinks, no '..' and no other file type. Reading anything else makes ingest refuse the whole batch (citation-adjudicator.md, Never Do)."

# --- Preflight: jq (checked before any use) ---
if ! command -v jq >/dev/null 2>&1; then
    deny "The reference checker's read was blocked because jq, which the read-scope check needs, is not installed."
fi
if ! command -v realpath >/dev/null 2>&1; then
    deny "The reference checker's read was blocked because realpath, which the read-scope check needs, is not installed."
fi

INPUT=$(cat)
: "${INPUT:=}"

# --- Input shape: exactly one JSON object ---
if [[ -z "$INPUT" ]]; then
    deny "The reference checker's read was blocked because the hook received no input."
fi
if ! printf '%s' "$INPUT" | jq -e -s 'length == 1 and (.[0] | type == "object")' >/dev/null 2>&1; then
    deny "The reference checker's read was blocked because the hook input is not a single JSON object."
fi

# --- Caller: only this agent's calls (and calls with no agent_type) are checked ---
AGENT_TYPE=$(printf '%s' "$INPUT" | jq -r '.agent_type // empty | strings')
if [[ -n "$AGENT_TYPE" && "$AGENT_TYPE" != "citation-adjudicator" ]]; then
    exit 0
fi

# --- Tool: Read only ---
# Compared inside jq: a value such as "Read" plus a newline must not pass as
# Read after command substitution trims it.
if ! printf '%s' "$INPUT" | jq -e '.tool_name == "Read"' >/dev/null 2>&1; then
    TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty | strings')
    SAFE_TOOL="${TOOL_NAME//[^A-Za-z0-9_.-]/?}"
    deny "The reference checker may use only the Read tool on its bundle; the ${SAFE_TOOL:-unnamed} tool call was blocked."
fi

# --- file_path: a string with no control characters ---
# Tested inside jq, because command substitution would drop a trailing newline
# and bash variables cannot hold a NUL.
if ! printf '%s' "$INPUT" | jq -e '.tool_input.file_path | type == "string" and length > 0 and (explode | all(. > 31 and . != 127))' >/dev/null 2>&1; then
    deny "The reference checker's read was blocked because the call names no usable file path. ${RULE}"
fi
REQ=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path')

# Shown in deny reasons: only path-safe characters, at most 200 of them.
SAFE_REQ="${REQ//[^A-Za-z0-9._\/-]/?}"
SAFE_REQ="${SAFE_REQ:0:200}"

if [[ "$REQ" != /* ]]; then
    deny "The reference checker's read of ${SAFE_REQ} was blocked: the path is not absolute. ${RULE}"
fi

# --- DAAF root: canonical, absolute, never / ---
ROOT=$(realpath -m -- "${CLAUDE_PROJECT_DIR:-/daaf}")
if [[ "$ROOT" != /?* ]]; then
    deny "The reference checker's read was blocked because the DAAF folder could not be determined."
fi

# --- Canonical form: no '..', '.', '//' or symlink anywhere in the path ---
LEXICAL=$(realpath -m -s -- "$REQ")
PHYSICAL=$(realpath -m -- "$REQ")
if [[ "$LEXICAL" != "$REQ" ]]; then
    deny "The reference checker's read of ${SAFE_REQ} was blocked: the path is not in plain form (it holds '..', '.', '//' or a trailing slash). ${RULE}"
fi
if [[ "$PHYSICAL" != "$REQ" ]]; then
    deny "The reference checker's read of ${SAFE_REQ} was blocked: the path goes through a symlink. ${RULE}"
fi

# --- Location: <ROOT>/research/<project...>/data/adjudication_bundles/<batch_id>.json ---
PREFIX="${ROOT}/research/"
if [[ "$REQ" != "$PREFIX"* ]]; then
    deny "The reference checker's read of ${SAFE_REQ} was blocked: the file is outside the DAAF research folder. ${RULE}"
fi
REST="${REQ#"$PREFIX"}"
BUNDLE_RE='^([^/]+/)+data/adjudication_bundles/[a-z0-9][a-z0-9_-]{0,31}\.json$'
if [[ ! "$REST" =~ $BUNDLE_RE ]]; then
    deny "The reference checker's read of ${SAFE_REQ} was blocked: it is not a bundle file in a project's data/adjudication_bundles folder. ${RULE}"
fi

# --- Existing regular file (no directory, FIFO or device) ---
if [[ ! -f "$REQ" ]]; then
    deny "The reference checker's read of ${SAFE_REQ} was blocked: no such bundle file exists. ${RULE}"
fi

exit 0
