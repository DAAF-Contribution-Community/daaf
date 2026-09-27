#!/usr/bin/env bash
# test_enforce_single_command.sh — Comprehensive test battery for enforce-single-command.sh
#
# Tests the hook with a wide range of inputs covering:
#   - Commands that SHOULD be blocked (chaining violations)
#   - Commands that SHOULD be allowed (legitimate single commands)
#   - Edge cases (quote handling, nesting, heredocs, compound commands)
#   - Fail-closed input posture (NEW 2026-09-26): stdin that is not exactly
#     one JSON object (concatenated objects, malformed text, whitespace only,
#     a bare JSON string, an array) must BLOCK — mirrored in
#     tests/bash/enforce_single_command.bats
#
# Usage: bash /daaf/scripts/test_enforce_single_command.sh
#        HOOK=/path/to/draft.sh bash /daaf/scripts/test_enforce_single_command.sh
#
# Each test case sends simulated Claude Code JSON to the hook via stdin
# and checks whether the exit code matches the expected result. The HOOK
# environment override lets the battery run against a STAGED draft before the
# user installs it (.claude/hooks/ is deny-protected) — behavior-neutral for CI.

HOOK="${HOOK:-/daaf/.claude/hooks/enforce-single-command.sh}"
PASS=0
FAIL=0
TOTAL=0
FAILURES=""

# ---------------------------------------------------------------------------
# test_case: Run one test and record result
#   $1 = "allow" or "block"
#   $2 = description
#   $3 = command string to test
# ---------------------------------------------------------------------------
test_case() {
    local expected="$1"
    local description="$2"
    local command="$3"
    ((TOTAL++))

    # Build JSON matching Claude Code's PreToolUse format
    local json
    json=$(jq -n --arg cmd "$command" '{"tool_name": "Bash", "tool_input": {"command": $cmd}}')

    # Run the hook, capture exit code, suppress output
    local exit_code
    echo "$json" | bash "$HOOK" >/dev/null 2>/dev/null
    exit_code=$?

    local result
    if [[ $exit_code -eq 0 ]]; then
        result="allow"
    elif [[ $exit_code -eq 2 ]]; then
        result="block"
    else
        result="error($exit_code)"
    fi

    if [[ "$result" == "$expected" ]]; then
        printf "  PASS  [%-5s] %s\n" "$expected" "$description"
        ((PASS++))
    else
        printf "  FAIL  [expected %-5s, got %-5s] %s\n" "$expected" "$result" "$description"
        FAILURES="${FAILURES}\n  FAIL  [expected ${expected}, got ${result}] ${description}"
        ((FAIL++))
    fi
}

# ---------------------------------------------------------------------------
# test_non_bash: Verify non-Bash tools pass through
# ---------------------------------------------------------------------------
test_non_bash() {
    local description="$1"
    local tool_name="$2"
    ((TOTAL++))

    local json
    json=$(jq -n --arg tool "$tool_name" '{"tool_name": $tool, "tool_input": {"content": "test"}}')

    local exit_code
    echo "$json" | bash "$HOOK" >/dev/null 2>/dev/null
    exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        printf "  PASS  [allow] %s\n" "$description"
        ((PASS++))
    else
        printf "  FAIL  [expected allow, got block] %s\n" "$description"
        FAILURES="${FAILURES}\n  FAIL  [expected allow, got block] ${description}"
        ((FAIL++))
    fi
}

# ---------------------------------------------------------------------------
# test_raw_stdin: Feed a RAW stdin payload (not built by jq) and record result
#   $1 = "allow" or "block"
#   $2 = description
#   $3 = exact bytes to send on the hook's stdin
# Used for the fail-closed input cases (NEW 2026-09-26), where the payload is
# deliberately NOT one well-formed JSON object, so it cannot come from jq -n.
# ---------------------------------------------------------------------------
test_raw_stdin() {
    local expected="$1"
    local description="$2"
    local payload="$3"
    ((TOTAL++))

    local exit_code
    printf '%s' "$payload" | bash "$HOOK" >/dev/null 2>/dev/null
    exit_code=$?

    local result
    if [[ $exit_code -eq 0 ]]; then
        result="allow"
    elif [[ $exit_code -eq 2 ]]; then
        result="block"
    else
        result="error($exit_code)"
    fi

    if [[ "$result" == "$expected" ]]; then
        printf "  PASS  [%-5s] %s\n" "$expected" "$description"
        ((PASS++))
    else
        printf "  FAIL  [expected %-5s, got %-5s] %s\n" "$expected" "$result" "$description"
        FAILURES="${FAILURES}\n  FAIL  [expected ${expected}, got ${result}] ${description}"
        ((FAIL++))
    fi
}

echo "========================================================================"
echo "  Test Battery: enforce-single-command.sh"
echo "========================================================================"
echo ""

# ===================================================================
# SECTION 1: SHOULD BLOCK — && chaining
# ===================================================================
echo "--- SHOULD BLOCK: && chaining ---"

test_case block \
    "Simple && chain" \
    "mkdir -p /path && cp file /path"

test_case block \
    "Triple && chain" \
    "mkdir -p /path && cp file /path && ls /path"

test_case block \
    "cd && command (common violation)" \
    "cd /tmp && ls -la"

test_case block \
    "git add && git commit" \
    'git add file.txt && git commit -m "msg"'

test_case block \
    "&& with redirections" \
    "cmd1 > /tmp/out && cmd2"

test_case block \
    "&& after pipe" \
    "cat file | grep pattern && echo done"

test_case block \
    "&& with variable assignment" \
    "export FOO=bar && echo \$FOO"

test_case block \
    "&& with path containing spaces" \
    'mkdir -p "/my path" && cd "/my path"'

echo ""

# ===================================================================
# SECTION 2: SHOULD BLOCK — || chaining
# ===================================================================
echo "--- SHOULD BLOCK: || chaining ---"

test_case block \
    "Simple || chain" \
    "cmd1 || cmd2"

test_case block \
    "|| with echo fallback" \
    "grep pattern file || echo not found"

test_case block \
    "|| true (error suppression)" \
    "grep pattern file || true"

test_case block \
    "|| exit (bail pattern)" \
    "test -f file || exit 1"

echo ""

# ===================================================================
# SECTION 3: SHOULD BLOCK — ; chaining
# ===================================================================
echo "--- SHOULD BLOCK: ; chaining ---"

test_case block \
    "Simple ; chain" \
    "cmd1 ; cmd2"

test_case block \
    "Triple ; chain" \
    "echo a ; echo b ; echo c"

test_case block \
    "Export then command" \
    "export VAR=val ; echo \$VAR"

test_case block \
    "; at start of second command" \
    "echo hello; echo world"

echo ""

# ===================================================================
# SECTION 4: SHOULD BLOCK — newline-separated commands
# ===================================================================
echo "--- SHOULD BLOCK: newline-separated commands ---"

test_case block \
    "Two commands on separate lines" \
    $'mkdir -p /tmp/test\nls /tmp/test'

test_case block \
    "Three commands on separate lines" \
    $'echo line1\necho line2\necho line3'

test_case block \
    "Newline with mixed operators" \
    $'echo hello\necho world'

test_case block \
    "Blank line between commands" \
    $'echo first\n\necho second'

echo ""

# ===================================================================
# SECTION 5: SHOULD BLOCK — mixed operators
# ===================================================================
echo "--- SHOULD BLOCK: mixed operators ---"

test_case block \
    "&& and || mixed" \
    "cmd1 && cmd2 || cmd3"

test_case block \
    "&& and ; mixed" \
    "cmd1 && cmd2 ; cmd3"

test_case block \
    "Brace group with ; (not a compound keyword)" \
    "{ echo a; echo b; }"

echo ""

# ===================================================================
# SECTION 6: SHOULD ALLOW — simple single commands
# ===================================================================
echo "--- SHOULD ALLOW: simple single commands ---"

test_case allow \
    "Simple ls" \
    "ls -la"

test_case allow \
    "Simple git status" \
    "git status"

test_case allow \
    "Command with arguments" \
    "grep -rn pattern /path/to/search"

test_case allow \
    "Command with absolute path" \
    "bash /daaf/scripts/run_with_capture.sh /daaf/research/scripts/01_test.py"

test_case allow \
    "Empty command" \
    ""

test_case allow \
    "Single word" \
    "date"

test_case allow \
    "pwd command" \
    "pwd"

test_case allow \
    "Echo with special chars" \
    "echo hello world 123 !@#"

echo ""

# ===================================================================
# SECTION 7: SHOULD ALLOW — pipes (not chaining)
# ===================================================================
echo "--- SHOULD ALLOW: pipes ---"

test_case allow \
    "Simple pipe" \
    "cat file | grep pattern"

test_case allow \
    "Triple pipe" \
    "cat file | grep pattern | wc -l"

test_case allow \
    "Pipe with sort" \
    "ls -la | sort -k5 -n"

test_case allow \
    "Complex pipeline" \
    "find /path -name '*.py' | xargs grep -l pattern | head -20"

echo ""

# ===================================================================
# SECTION 8: SHOULD ALLOW — redirections
# ===================================================================
echo "--- SHOULD ALLOW: redirections ---"

test_case allow \
    "Output redirect" \
    "echo hello > /tmp/file.txt"

test_case allow \
    "Append redirect" \
    "echo hello >> /tmp/file.txt"

test_case allow \
    "Stderr redirect" \
    "cmd 2>/dev/null"

test_case allow \
    "Combined stderr/stdout redirect" \
    "cmd > /tmp/out.txt 2>&1"

test_case allow \
    "Input redirect" \
    "wc -l < /tmp/file.txt"

echo ""

# ===================================================================
# SECTION 9: SHOULD ALLOW — quoted strings containing operators
# ===================================================================
echo "--- SHOULD ALLOW: operators inside quotes ---"

test_case allow \
    "&& inside double quotes" \
    'echo "mkdir -p /path && cp file /path"'

test_case allow \
    "|| inside double quotes" \
    'echo "cmd1 || cmd2"'

test_case allow \
    "; inside double quotes" \
    'echo "cmd1 ; cmd2"'

test_case allow \
    "&& inside single quotes" \
    "echo 'mkdir -p /path && cp file /path'"

test_case allow \
    "|| inside single quotes" \
    "echo 'cmd1 || cmd2'"

test_case allow \
    "; inside single quotes" \
    "echo 'cmd1 ; cmd2'"

test_case allow \
    "grep pattern with &&" \
    "grep -E 'pattern1 && pattern2' file.txt"

test_case allow \
    "git commit message with semicolons" \
    'git commit -m "fix: handle edge case; update tests"'

test_case allow \
    "echo with multiple quoted operators" \
    'echo "a && b || c ; d"'

test_case allow \
    "printf with operator chars" \
    "printf '%s && %s\n' hello world"

echo ""

# ===================================================================
# SECTION 10: SHOULD ALLOW — compound commands (for/while/if/case)
# ===================================================================
echo "--- SHOULD ALLOW: compound commands ---"

test_case allow \
    "for loop" \
    "for f in *.py; do echo \"\$f\"; done"

test_case allow \
    "for loop with wc" \
    "for f in *.py; do wc -l \"\$f\"; done"

test_case allow \
    "while read loop" \
    "while read line; do echo \"\$line\"; done < file.txt"

test_case allow \
    "if-then-fi" \
    "if [ -f file ]; then cat file; fi"

test_case allow \
    "if-then-else-fi" \
    "if [ -f file ]; then cat file; else echo missing; fi"

test_case allow \
    "if with elif" \
    "if [ -f a ]; then echo a; elif [ -f b ]; then echo b; else echo none; fi"

test_case allow \
    "case statement" \
    'case "$1" in a) echo a;; b) echo b;; *) echo other;; esac'

test_case allow \
    "select statement" \
    'select opt in a b c; do echo "$opt"; break; done'

test_case allow \
    "until loop" \
    "until [ -f /tmp/ready ]; do sleep 1; done"

test_case allow \
    "for loop on multiple lines" \
    $'for f in *.py; do\n  echo "$f"\ndone'

test_case allow \
    "if on multiple lines" \
    $'if [ -f file ]; then\n  cat file\nfi'

echo ""

# ===================================================================
# SECTION 11: SHOULD ALLOW — nesting constructs
# ===================================================================
echo "--- SHOULD ALLOW: nesting constructs ---"

test_case allow \
    "[[ ]] with &&" \
    "[[ -f a && -f b ]]"

test_case allow \
    "[[ ]] with ||" \
    "[[ -f a || -f b ]]"

test_case allow \
    "(( )) arithmetic" \
    "(( x > 0 ))"

test_case allow \
    "$() command substitution" \
    'echo $(date)'

test_case allow \
    "Nested $() with operators" \
    'echo "$(echo foo && echo bar)"'

test_case allow \
    "Backtick substitution" \
    'echo `date`'

test_case allow \
    "Subshell" \
    '(echo hello)'

test_case allow \
    "Array assignment" \
    'arr=(one two three)'

test_case allow \
    "[ ] test with ||" \
    "[ -f a -o -f b ]"

test_case allow \
    "test command inside [[ ]] with && and pattern" \
    '[[ "$x" == "yes" && "$y" == "no" ]]'

echo ""

# ===================================================================
# SECTION 12: SHOULD ALLOW — heredocs
# ===================================================================
echo "--- SHOULD ALLOW: heredocs ---"

test_case allow \
    "Heredoc with && in body" \
    $'cat <<EOF\nhello && world\nEOF'

test_case allow \
    "Quoted heredoc with operators" \
    $'cat <<\'EOF\'\nhello && world || foo ; bar\nEOF'

test_case allow \
    "Heredoc with multiple operator lines" \
    $'cat <<EOF\nline1 && line2\nline3 || line4\nline5 ; line6\nEOF'

test_case allow \
    "Indented heredoc (<<-)" \
    $'cat <<-EOF\n\thello && world\n\tEOF'

test_case allow \
    "Git commit with heredoc body" \
    $'git commit -m "$(cat <<\'EOF\'\nFix: handle edge case\n\nThis fixes the && parsing bug\nEOF\n)"'

echo ""

# ===================================================================
# SECTION 13: SHOULD ALLOW — line continuations
# ===================================================================
echo "--- SHOULD ALLOW: line continuations ---"

test_case allow \
    "Backslash continuation" \
    $'echo hello \\\n  world'

test_case allow \
    "Long command with continuations" \
    $'curl -X POST \\\n  -H "Content-Type: application/json" \\\n  -d \'{"key":"val"}\' \\\n  http://example.com/api'

test_case allow \
    "grep with continuation" \
    $'grep -rn \\\n  "pattern" \\\n  /path/to/search'

echo ""

# ===================================================================
# SECTION 14: SHOULD ALLOW — single & (background) and single | (pipe)
# ===================================================================
echo "--- SHOULD ALLOW: & (background) and | (pipe) ---"

test_case allow \
    "Background job with &" \
    "sleep 10 &"

test_case allow \
    "Single pipe (not ||)" \
    "echo hello | cat"

echo ""

# ===================================================================
# SECTION 15: SHOULD ALLOW — miscellaneous safe patterns
# ===================================================================
echo "--- SHOULD ALLOW: miscellaneous safe patterns ---"

test_case allow \
    "Environment variable prefix" \
    "PYTHONPATH=/foo python script.py"

test_case allow \
    "Multiple env var prefixes" \
    "FOO=bar BAZ=qux command arg"

test_case allow \
    "Escaped && in argument" \
    "echo hello \\&\\& world"

test_case allow \
    "wc -l with pipe" \
    "wc -l /daaf/.claude/hooks/enforce-single-command.sh"

test_case allow \
    "find with -exec (contains ;)" \
    "find /path -name '*.py' -exec wc -l {} \;"

test_case allow \
    "jq with complex filter" \
    "jq '.tool_name // empty' file.json"

test_case allow \
    "sed with semicolons in pattern" \
    "sed 's/old/new/g; s/foo/bar/g' file.txt"

echo ""

# ===================================================================
# SECTION 16: NON-BASH TOOL PASSTHROUGH
# ===================================================================
echo "--- NON-BASH: tool passthrough ---"

test_non_bash "Read tool passes through" "Read"
test_non_bash "Write tool passes through" "Write"
test_non_bash "Edit tool passes through" "Edit"
test_non_bash "Grep tool passes through" "Grep"
test_non_bash "Glob tool passes through" "Glob"

echo ""

# ===================================================================
# SECTION 17: EDGE CASES
# ===================================================================
echo "--- EDGE CASES ---"

test_case allow \
    "Trailing semicolon (no chaining)" \
    "echo hello;"

test_case allow \
    "Multiple trailing semicolons" \
    "echo hello;;;"

test_case allow \
    "Whitespace-only command" \
    "   "

test_case block \
    "Semicolons with whitespace between commands" \
    "echo a ;   echo b"

test_case block \
    "&& with lots of whitespace" \
    "echo a   &&   echo b"

test_case block \
    "|| with no spaces" \
    "true||false"

test_case block \
    "&& with no spaces" \
    "true&&false"

test_case block \
    "Newline after pipe then new command" \
    $'echo hello | cat\necho world'

test_case allow \
    "Single & at end (background, not &&)" \
    "long_running_cmd &"

test_case allow \
    "Double-quoted string with escaped quote inside" \
    'echo "she said \"hello && goodbye\""'

test_case allow \
    "Nested quotes: double inside single" \
    "echo 'he said \"a && b\"'"

test_case allow \
    "Single-quoted string with double quotes" \
    "echo '\"a && b\"'"

echo ""

# ===================================================================
# SECTION 18: KNOWN LIMITATIONS (document expected behavior)
# ===================================================================
echo "--- KNOWN LIMITATIONS ---"
echo "  These test expected behavior of KNOWN EDGE CASES."
echo "  Some may be false positives/negatives by design."
echo ""

# find -exec uses ; as terminator. The ; here is trailing (nothing
# follows it), so the scanner correctly treats it as non-chaining.
# This was initially expected to be a false positive but the trailing-;
# logic handles it correctly.
test_case allow \
    "find -exec with trailing ; (correctly allowed — trailing ;)" \
    "find /path -name '*.py' -exec wc -l {} ;"

# sed with multiple expressions: the ; is inside single quotes,
# so the quote-aware scanner correctly ignores it.
# This was initially expected to be a false positive but quote
# tracking handles it correctly.
test_case allow \
    "sed with ; inside quotes (correctly allowed — inside quotes)" \
    "sed 's/a/b/;s/c/d/' file"

# cmd1 ; for ... would be blocked because it starts with cmd1, not for
test_case block \
    "cmd before compound (correctly blocked)" \
    "echo start ; for f in *.py; do echo \$f; done"

# && inside $() at top-level echo — allowed because $() is nested
test_case allow \
    "&& inside command substitution (correctly allowed)" \
    'echo $(cmd1 && cmd2)'

# RESIDUAL R6 (hook header "Known residuals"; pinned ALLOW today, 2026-09-26):
# the carrier set is the LOCAL shell set, so a remote command body after
# `ssh` is not decomposed and its && is not counted. Deliberate scope choice
# (the one-command rule governs what this Bash call runs locally); mirrored in
# tests/bash/enforce_single_command.bats. A change that flips it must update
# both pins and the BOUNDARIES.md row.
test_case allow \
    "RESIDUAL R6: ssh remote body with && not decomposed (ALLOW today)" \
    "ssh deploy@host 'cd /srv/app && git pull'"

echo ""

# ===================================================================
# SECTION 19 (NEW 2026-09-26): FAIL-CLOSED INPUT — not exactly one JSON object
# ===================================================================
# A hook without the single-object gate ALLOWS every BLOCK row below:
# concatenated objects make `jq -r .tool_name` yield two lines, and the other
# shapes resolve TOOL_NAME to "", so the `!= "Bash"` gate reads "not Bash".
# Credit: the 2026-09-24 hook-maintenance session's enforce-file-first.sh
# finding. Mirrored 1:1 in tests/bash/enforce_single_command.bats.
echo "--- FAIL-CLOSED INPUT: not exactly one JSON object (NEW 2026-09-26) ---"

test_raw_stdin block \
    "(NEW 2026-09-26) concatenated objects, Read then chained Bash" \
    '{"tool_name":"Read","tool_input":{"file_path":"/x"}}{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}'

test_raw_stdin block \
    "(NEW 2026-09-26) concatenated objects, chained Bash then Read" \
    '{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}{"tool_name":"Read","tool_input":{"file_path":"/x"}}'

test_raw_stdin block \
    "(NEW 2026-09-26) concatenated objects, benign Bash then chained Bash" \
    '{"tool_name":"Bash","tool_input":{"command":"ls"}}{"tool_name":"Bash","tool_input":{"command":"echo a && echo b"}}'

test_raw_stdin block \
    "(NEW 2026-09-26) newline-separated objects (JSON Lines), Read then chained Bash" \
    $'{"tool_name":"Read","tool_input":{"file_path":"/x"}}\n{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}\n'

test_raw_stdin block \
    "(NEW 2026-09-26) malformed non-JSON text" \
    'not json {{{'

test_raw_stdin block \
    "(NEW 2026-09-26) whitespace-only stdin" \
    $'   \n\t '

test_raw_stdin block \
    "(NEW 2026-09-26) bare JSON string" \
    '"echo a; echo b"'

test_raw_stdin block \
    "(NEW 2026-09-26) array wrapping a chained Bash object" \
    '[{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}]'

test_raw_stdin allow \
    "(NEW 2026-09-26) control: single benign Bash object passes the gate" \
    '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'

test_raw_stdin allow \
    "(NEW 2026-09-26) control: single non-Bash (Read) object passes the gate" \
    '{"tool_name":"Read","tool_input":{"file_path":"/daaf/CLAUDE.md"}}'

test_raw_stdin block \
    "(NEW 2026-09-26) control: single chained Bash object still reaches the scanner" \
    '{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}'

# RESIDUAL R7 (hook header "Known residuals"; pinned ALLOW today, added
# 2026-09-27 after Phase 4 review N4): the gate checks that stdin is ONE object
# but not the TYPE of tool_name, so a non-string tool_name reads as "not Bash"
# and the chain is never scanned. Passes on the 2026-09-26 install and on `_a`.
# Mirrored in tests/bash/enforce_single_command.bats. A change that flips it
# must update both pins and the BOUNDARIES.md row.
test_raw_stdin allow \
    "RESIDUAL R7: non-string tool_name (array) with a chained command (ALLOW today)" \
    '{"tool_name":["Bash"],"tool_input":{"command":"echo a; echo b"}}'

echo ""

# ===================================================================
# SUMMARY
# ===================================================================
echo "========================================================================"
printf "  RESULTS: %d passed, %d failed out of %d total\n" "$PASS" "$FAIL" "$TOTAL"
echo "========================================================================"

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "  FAILURES:"
    printf "$FAILURES\n"
    echo ""
    exit 1
else
    echo ""
    echo "  All tests passed!"
    echo ""
    exit 0
fi
