#!/usr/bin/env bash
# enforce-single-command.sh — PreToolUse hook that blocks command chaining
#
# Enforces the CLAUDE.md rule: "Every Bash tool call must contain exactly
# one command. No &&, ;, or || chaining."
#
# This prevents chained commands from bypassing safety hooks and permission
# checks that evaluate each Bash call individually.
#
# Detection strategy:
#   1. Remove heredoc bodies (avoid scanning their content)
#   2. Collapse line continuations (backslash-newline)
#   3. Scan with a quote-aware awk state machine that tracks:
#      - Single/double quote state (operators inside quotes are ignored)
#      - Parenthesis/bracket nesting depth (operators inside $()/[[]] are ignored)
#   4. Flag &&, ||, or ; found at the top level
#   5. Exception: ; is allowed when the command begins with a compound
#      keyword (for, while, until, if, case, select), since ; is
#      syntactic structure in those constructs — not command chaining
#
# Exit codes (Claude Code PreToolUse convention):
#   0 = allow the command to proceed
#   2 = BLOCK the command (stderr message shown to the model)
#
# Hook event: PreToolUse (matcher: "Bash")
# Registered in: .claude/settings.json

# Fail CLOSED: if anything unexpected goes wrong, block the command.
# This is a safety-adjacent hook — ambiguous failures must not silently allow.
trap 'echo "BLOCKED by enforce-single-command hook: unexpected error in chain detection" >&2; exit 2' ERR

# --- Dependency check (fail-closed) ---
if ! command -v jq &>/dev/null; then
    echo "BLOCKED by enforce-single-command hook: jq is not installed (required for hook)" >&2
    exit 2
fi

INPUT=$(cat)

# --- Empty input guard (fail-closed) ---
if [[ -z "$INPUT" ]]; then
    echo "BLOCKED by enforce-single-command hook: received empty input (expected JSON)" >&2
    exit 2
fi

# Only inspect Bash tool calls
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null) || TOOL_NAME=""
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Extract the command string
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || CMD=""
if [[ -z "$CMD" ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# block: Print a descriptive error to stderr and exit 2
# ---------------------------------------------------------------------------
block() {
    cat >&2 <<ENDBLOCK
BLOCKED by enforce-single-command hook: $1

DAAF requires exactly one command per Bash tool call.
Split chained commands into separate Bash calls:

  Wrong:  mkdir -p /path && cp file /path
  Right:  Two separate Bash calls, each with one command

This rule ensures each command is independently evaluated by safety hooks
and permission checks. See CLAUDE.md § "One Command Per Call".
ENDBLOCK
    exit 2
}

# ---------------------------------------------------------------------------
# PRE-PROCESSING
# ---------------------------------------------------------------------------

# 1. Strip heredoc bodies to avoid scanning their content.
#    Keeps the line containing <<DELIM but removes the body through the
#    closing delimiter line. Handles <<DELIM, <<'DELIM', <<"DELIM", <<-DELIM.
PROCESSED=$(printf '%s\n' "$CMD" | awk '
BEGIN { delim = "" }
{
    if (delim != "") {
        line = $0
        sub(/^[[:space:]]+/, "", line)
        if (line == delim) { delim = "" }
        next
    }

    # Detect heredoc start and extract delimiter
    if (match($0, /<<-?[[:space:]]*/)) {
        rest = substr($0, RSTART + RLENGTH)
        # Strip leading quotes (single or double)
        gsub(/^["'"'"']/, "", rest)
        # Extract word (the delimiter)
        match(rest, /^[A-Za-z_][A-Za-z0-9_]*/)
        if (RSTART > 0) {
            delim = substr(rest, RSTART, RLENGTH)
        }
    }
    print
}
')

# 2. Collapse line continuations (backslash immediately before newline)
PROCESSED=$(printf '%s' "$PROCESSED" | sed -z 's/\\\n/ /g')

# 3. Convert remaining newlines to ; so they are caught as command separators.
#    Trailing newlines become trailing ; which the scanner ignores (it checks
#    whether non-whitespace content follows a ;).
PROCESSED=$(printf '%s' "$PROCESSED" | tr '\n' ';')

# ---------------------------------------------------------------------------
# SCAN for top-level operators using awk state machine
#
# Tracks quote state and nesting depth. Only flags operators found at the
# top level (outside quotes, outside parentheses/brackets).
#
# The -v sq="'" trick passes a single-quote character as an awk variable,
# avoiding the bash quoting nightmare of embedding literal single quotes
# inside a single-quoted awk program.
#
# Returns one of: "AND", "OR", "SEMI", "OK"
# ---------------------------------------------------------------------------
SCAN_RESULT=$(printf '%s' "$PROCESSED" | awk -v sq="'" '
BEGIN {
    # States: 0=normal, 1=single-quote, 2=double-quote
    state = 0
    # Nesting depth for () and [] constructs
    depth = 0
    # Whether next character is escaped
    escaped = 0
    # Result to print
    result = "OK"
}
{
    n = length($0)
    for (i = 1; i <= n; i++) {
        c = substr($0, i, 1)

        # --- Handle escape flag ---
        if (escaped) {
            escaped = 0
            continue
        }

        # --- Single-quote state ---
        # In bash single quotes: no escaping, only a matching single-quote ends it
        if (state == 1) {
            if (c == sq) state = 0
            continue
        }

        # --- Double-quote state ---
        # Backslash escapes the next character; double-quote ends the state
        if (state == 2) {
            if (c == "\\") { escaped = 1; continue }
            if (c == "\"") state = 0
            continue
        }

        # --- Normal state ---
        if (c == "\\") { escaped = 1; continue }
        if (c == sq)   { state = 1; continue }
        if (c == "\"") { state = 2; continue }

        # Track nesting: ( ) [ ]
        # Covers $(), (( )), [[ ]], [ ], and subshells
        if (c == "(" || c == "[") { depth++; continue }
        if (c == ")" || c == "]") {
            if (depth > 0) depth--
            continue
        }

        # Only check operators at top level (depth 0, normal state)
        if (depth > 0) continue

        # --- Two-character operators ---
        if (i < n) {
            c2 = substr($0, i + 1, 1)
            if (c == "&" && c2 == "&") { result = "AND"; exit }
            if (c == "|" && c2 == "|") { result = "OR";  exit }
        }

        # --- Single-character operator: semicolon ---
        if (c == ";") {
            # Ignore trailing semicolons: if only whitespace and more
            # semicolons remain after this point, it is not chaining
            remaining = substr($0, i + 1)
            gsub(/[[:space:];]/, "", remaining)
            if (remaining != "") {
                result = "SEMI"
                exit
            }
        }
    }
}
END { print result }
')

# ---------------------------------------------------------------------------
# APPLY scan results
# ---------------------------------------------------------------------------
case "$SCAN_RESULT" in
    AND)
        block "Command chaining with '&&' detected."
        ;;
    OR)
        block "Command chaining with '||' detected."
        ;;
    SEMI)
        # Exception: compound commands use ; as syntactic structure.
        # Allow when the command STARTS with a compound keyword.
        # This avoids false positives on: for x in ...; do ...; done
        # While still blocking: cmd1 ; cmd2 (starts with cmd1, not a keyword)
        if echo "$CMD" | grep -qE '^\s*(for|while|until|if|elif|case|select)\b'; then
            exit 0
        fi
        block "Command chaining with ';' detected."
        ;;
    OK)
        exit 0
        ;;
    *)
        # Unexpected scanner output — fail open with caution.
        # This is a convention enforcement hook, not a security boundary;
        # a scanner bug should not block all Bash usage.
        exit 0
        ;;
esac
