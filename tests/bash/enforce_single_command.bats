#!/usr/bin/env bats
# ============================================================================
# Tests for enforce-single-command.sh -- the one-command-per-Bash-call hook
# ============================================================================
# Before 2026-09-18 this hook had NO bats coverage at all (its only automated
# coverage was scripts/test_enforce_single_command.sh, which pins the LIVE hook
# path, plus one DAAFBench integrity probe). This suite is the regression
# baseline for the hook's EXISTING rules and the specification for the
# 2026-09-18 hardening pass (findings items 8, 10, 13, 14 --
# research/2026-09-18_FrameworkDev_SafetyHookHardening/).
#
# CONTRACT: exit 0 = ALLOW the Bash call, exit 2 = BLOCK it. Chaining
# operators at top level (`&&`, `||`, `;`, a lone `&`) BLOCK. Operators inside
# quotes, inside `$( )` / `[[ ]]` / `(( ))`-style nesting, inside heredoc
# bodies, inside `#` comments, or backslash-escaped are DATA and must ALLOW.
#
# IMPORTANT -- .claude/hooks/ is deny-protected, so hook revisions are authored
# as drafts outside it. This suite defaults to the LIVE hook and accepts an
# override so a draft can be validated before the user installs it:
#   ENFORCE_SINGLE_COMMAND_SH=/daaf/research/2026-09-18_FrameworkDev_SafetyHookHardening/enforce-single-command.sh.proposed \
#     bats tests/bash/enforce_single_command.bats
#
# Tests tagged "(NEW 2026-09-18)" encode behavior the draft introduces and are
# EXPECTED TO FAIL against the pre-hardening live hook. Every other test must
# pass against BOTH, which is what makes this suite a faithful baseline.
#
# Tests tagged "(NEW 2026-09-26)" pin the fail-closed "exactly one JSON object
# on stdin" gate (hook header, "Fail-closed input posture"; staged as
# research/2026-09-18_FrameworkDev_SafetyHookHardening/enforce-single-command_a.sh.proposed).
# Its BLOCK cases are EXPECTED TO FAIL against a hook without the gate; its
# ALLOW / control cases pass against both.
#
# Case strings live INSIDE this file and are fed to the hook via a jq envelope
# (never on a command line), so the live PreToolUse hooks vetting the `bats`
# invocation never see the chained case strings themselves.
# ============================================================================

load 'test_helper'

# Path to the script under test (override to test a proposed/deliverable copy).
ENFORCE_SINGLE_COMMAND_SH="${ENFORCE_SINGLE_COMMAND_SH:-${REPO_ROOT}/.claude/hooks/enforce-single-command.sh}"

setup() {
    common_setup
    export ENFORCE_SINGLE_COMMAND_SH
}

teardown() {
    common_teardown
}

# --- Helper: feed a command to the hook via the PreToolUse JSON envelope ---
_run_hook() {
    run bash -c 'jq -n --arg c "$1" '\''{tool_name:"Bash",tool_input:{command:$c}}'\'' | bash "$2"' _ "$1" "$ENFORCE_SINGLE_COMMAND_SH"
}

# --- Helper: feed an arbitrary raw JSON envelope (for tool_name / empty cases) ---
_run_hook_raw() {
    run bash -c 'printf "%s" "$1" | bash "$2"' _ "$1" "$ENFORCE_SINGLE_COMMAND_SH"
}

_AND_MSG="Command chaining with '&&' detected"
_OR_MSG="Command chaining with '||' detected"
_SEMI_MSG="Command chaining with ';' detected"
_AMP_MSG="Command chaining with '&' (background) detected"

# =========================================================================
# Syntax
# =========================================================================

@test "enforce-single-command.sh parses without errors" {
    run bash -n "$ENFORCE_SINGLE_COMMAND_SH"
    assert_success
}

# =========================================================================
# Envelope handling
# =========================================================================

@test "non-Bash tool_name is ignored: ALLOW" {
    _run_hook_raw '{"tool_name":"Read","tool_input":{"file_path":"/x; /y"}}'
    assert_success
}

@test "Bash call with empty command string: ALLOW" {
    _run_hook_raw '{"tool_name":"Bash","tool_input":{"command":""}}'
    assert_success
}

@test "Bash call with no command field: ALLOW" {
    _run_hook_raw '{"tool_name":"Bash","tool_input":{}}'
    assert_success
}

@test "empty stdin fails closed: BLOCK" {
    _run_hook_raw ''
    assert_failure
    assert_output --partial "empty input"
}

# NOTE: the "jq is not installed" fail-closed branch is deliberately NOT
# tested. Exercising it requires removing jq from PATH for the hook only, and
# the hook is invoked through `bash -c` with the inherited environment; a PATH
# stub would also break the jq call that BUILDS the envelope. The branch is
# three lines of unconditional `command -v jq || exit 2` and is verified by
# reading, not by execution.

# =========================================================================
# (NEW 2026-09-26) Fail-closed on stdin that is not exactly one JSON object
# =========================================================================
# Without the gate, concatenated objects make `jq -r .tool_name` yield two
# lines ("Read\nBash", "Bash\nBash"), the `!= "Bash"` gate reads "not Bash",
# and the chain in the second object is never scanned (ALLOW). Malformed text,
# whitespace only, a bare JSON string and an array all resolve TOOL_NAME to ""
# and ALLOW the same way. Credit: the 2026-09-24 hook-maintenance session's
# enforce-file-first.sh finding. The chained strings below are fed as raw
# JSON from inside this file, never from a command line.

_MALFORMED_MSG="stdin is not a single JSON object"

@test "(NEW 2026-09-26) concatenated objects, Read then chained Bash: BLOCK" {
    _run_hook_raw '{"tool_name":"Read","tool_input":{"file_path":"/x"}}{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) concatenated objects, chained Bash then Read: BLOCK" {
    _run_hook_raw '{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}{"tool_name":"Read","tool_input":{"file_path":"/x"}}'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) concatenated objects, benign Bash then chained Bash: BLOCK" {
    _run_hook_raw '{"tool_name":"Bash","tool_input":{"command":"ls"}}{"tool_name":"Bash","tool_input":{"command":"echo a && echo b"}}'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) newline-separated objects (JSON Lines), Read then chained Bash: BLOCK" {
    _run_hook_raw $'{"tool_name":"Read","tool_input":{"file_path":"/x"}}\n{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}\n'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) malformed non-JSON text: BLOCK" {
    _run_hook_raw 'not json {{{'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) whitespace-only stdin: BLOCK" {
    _run_hook_raw $'   \n\t '
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) bare JSON string: BLOCK" {
    _run_hook_raw '"echo a; echo b"'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) array wrapping a chained Bash object: BLOCK" {
    _run_hook_raw '[{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}]'
    assert_failure
    assert_output --partial "$_MALFORMED_MSG"
}

@test "(NEW 2026-09-26) control: single benign Bash object passes the gate: ALLOW" {
    _run_hook_raw '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'
    assert_success
}

@test "(NEW 2026-09-26) control: single non-Bash (Read) object passes the gate: ALLOW" {
    _run_hook_raw '{"tool_name":"Read","tool_input":{"file_path":"/daaf/CLAUDE.md"}}'
    assert_success
}

@test "(NEW 2026-09-26) control: single chained Bash object still reaches the scanner: BLOCK" {
    _run_hook_raw '{"tool_name":"Bash","tool_input":{"command":"echo a; echo b"}}'
    assert_failure
    assert_output --partial "$_SEMI_MSG"
    refute_output --partial "$_MALFORMED_MSG"
}

# RESIDUAL R7 (hook header "Known residuals"; added 2026-09-27 after Phase 4
# review N4): the gate checks that stdin is ONE object but not the TYPE of
# tool_name, so a non-string tool_name reads as "not Bash" at the `!= "Bash"`
# gate and the chain is never scanned. Passes against the 2026-09-26 install
# and against `_a` (not tagged NEW). Mirrored in
# scripts/test_enforce_single_command.sh.
@test "RESIDUAL R7: non-string tool_name (array) with a chained command: ALLOW today" {
    _run_hook_raw '{"tool_name":["Bash"],"tool_input":{"command":"echo a; echo b"}}'
    assert_success
}

# =========================================================================
# EXISTING RULE: top-level chaining operators BLOCK
# =========================================================================

@test "&& chaining: BLOCK" {
    _run_hook 'echo a && echo b'
    assert_failure
    assert_output --partial "$_AND_MSG"
}

@test "|| chaining: BLOCK" {
    _run_hook 'echo a || echo b'
    assert_failure
    assert_output --partial "$_OR_MSG"
}

@test "; chaining: BLOCK" {
    _run_hook 'echo a; echo b'
    assert_failure
    assert_output --partial "$_SEMI_MSG"
}

@test "three-way ; chain: BLOCK" {
    _run_hook 'mkdir -p /x; cp f /x; ls /x'
    assert_failure
    assert_output --partial "$_SEMI_MSG"
}

@test "newline as a separator (two lines): BLOCK" {
    _run_hook $'echo a\necho b'
    assert_failure
}

@test "brace group with ; at top level: BLOCK" {
    _run_hook '{ echo a; echo b; }'
    assert_failure
}

@test "heredoc opener line carrying a trailing ; chain: BLOCK" {
    _run_hook 'cat > f <<EOF; rm x'
    assert_failure
}

# =========================================================================
# EXISTING RULE: compound-command keyword exemption ALLOWS ;
# =========================================================================

@test "for loop one-liner: ALLOW" {
    _run_hook 'for i in 1 2; do echo $i; done'
    assert_success
}

@test "for loop across lines: ALLOW" {
    _run_hook $'for i in 1 2; do\n  echo $i\ndone'
    assert_success
}

@test "while loop: ALLOW" {
    _run_hook 'while read l; do echo $l; done'
    assert_success
}

@test "until loop: ALLOW" {
    _run_hook 'until false; do break; done'
    assert_success
}

@test "if statement: ALLOW" {
    _run_hook 'if true; then echo a; fi'
    assert_success
}

@test "case statement: ALLOW" {
    _run_hook 'case $x in a) echo a;; esac'
    assert_success
}

# =========================================================================
# EXISTING RULE: quoted / escaped / nested operators are DATA
# =========================================================================

@test "; inside double quotes: ALLOW" {
    _run_hook 'grep -c "a;b" file.txt'
    assert_success
}

@test "|| inside single quotes: ALLOW" {
    _run_hook "echo 'a || b'"
    assert_success
}

@test "&& inside a here-string: ALLOW" {
    _run_hook 'cat <<< "a && b"'
    assert_success
}

@test "; inside a single-quoted awk program: ALLOW" {
    _run_hook "awk '{ if (\$1 > 2) print; }' f"
    assert_success
}

@test "; inside a single-quoted sed script: ALLOW" {
    _run_hook "sed -n '1,5p;10p' f"
    assert_success
}

@test "// inside a single-quoted jq filter: ALLOW" {
    _run_hook "jq '.a // .b' f.json"
    assert_success
}

@test "escaped \\; terminating find -exec: ALLOW" {
    _run_hook 'find . -name "*.py" -exec grep -l foo {} \;'
    assert_success
}

@test "&& inside [[ ]] test brackets: ALLOW" {
    _run_hook '[[ -f a && -f b ]]'
    assert_success
}

@test "; inside \$( ) command substitution (computed argument, residual R3): ALLOW" {
    _run_hook 'echo a $(echo b; echo c)'
    assert_success
}

@test "<< left shift inside \$(( )) is not a heredoc: ALLOW" {
    _run_hook 'echo $(( 1 << 3 ))'
    assert_success
}

@test "trailing semicolon only: ALLOW" {
    _run_hook 'ls -la;'
    assert_success
}

@test "bare script invocation (no operators): ALLOW" {
    _run_hook 'bash script.sh'
    assert_success
}

# =========================================================================
# EXISTING RULE: heredoc bodies are data, not commands
# =========================================================================

@test "heredoc body containing ; and &&: ALLOW" {
    _run_hook $'cat <<\'EOF\' > f\nline one; line two && three\nEOF'
    assert_success
}

@test "heredoc with <<- and a tab-indented terminator: ALLOW" {
    _run_hook $'cat <<-EOF\n\tbody; here\n\tEOF'
    assert_success
}

@test "heredoc terminator followed by a real chain: BLOCK" {
    _run_hook $'cat <<\'EOF\'\nbody\nEOF\nrm a; rm b'
    assert_failure
}

# =========================================================================
# ITEM 8 (NEW 2026-09-18): quote-aware heredoc detection + CRLF terminator
# =========================================================================
# The pre-hardening stripper matched `<<` anywhere on a line, including inside
# quotes, so a quoted `<<EOF` swallowed every following line as a "body" and
# the chain was never scanned. That is a scan EVASION, not a convention gap.

@test "(NEW 2026-09-18) SML2: quoted <<EOF must not swallow the next line: BLOCK" {
    _run_hook $'echo "x <<EOF"\nrm a; rm b'
    assert_failure
    assert_output --partial "$_SEMI_MSG"
}

@test "(NEW 2026-09-18) single-quoted <<EOF must not swallow the next line: BLOCK" {
    _run_hook $'echo \'x <<EOF\'\nrm a; rm b'
    assert_failure
}

@test "(NEW 2026-09-18) CRLF heredoc terminator still closes the body: BLOCK" {
    _run_hook $'cat <<EOF\nbody\r\nEOF\r\nrm a; rm b'
    assert_failure
    assert_output --partial "$_SEMI_MSG"
}

@test "(NEW 2026-09-18) <<EOF appearing only inside a comment: BLOCK" {
    _run_hook $'echo hi # <<EOF\nrm a; rm b'
    assert_failure
}

@test "(NEW 2026-09-18) <<EOF inside \$(( )) is a left shift, chain still seen: BLOCK" {
    _run_hook $'echo $(( 1 <<EOF ))\nrm a; rm b'
    assert_failure
}

@test "(NEW 2026-09-18) two heredocs on one line close in order: ALLOW" {
    _run_hook $'cat <<A <<B\nx; y\nA\np && q\nB'
    assert_success
}

@test "(NEW 2026-09-18) chain after two queued heredocs close: BLOCK" {
    _run_hook $'cat <<A <<B\nx\nA\ny\nB\nrm a; rm b'
    assert_failure
}

@test "here-string <<< is not a heredoc opener (chain after it still seen): BLOCK" {
    _run_hook $'cat <<< "data"\nrm a; rm b'
    assert_failure
}

# =========================================================================
# ITEM 10 (NEW 2026-09-18): a lone & is a chaining operator
# =========================================================================

@test "(NEW 2026-09-18) SBY1: background & followed by another command: BLOCK" {
    _run_hook 'sleep 1 & echo second'
    assert_failure
    assert_output --partial "$_AMP_MSG"
}

@test "(NEW 2026-09-18) & with no space before the next command: BLOCK" {
    _run_hook 'a &b'
    assert_failure
    assert_output --partial "$_AMP_MSG"
}

@test "(NEW 2026-09-18) a & b: BLOCK" {
    _run_hook 'a & b'
    assert_failure
}

@test "trailing background & with nothing after it: ALLOW" {
    _run_hook 'python3 x.py &'
    assert_success
}

@test "2>&1 fd duplication is not chaining: ALLOW" {
    _run_hook 'cmd 2>&1'
    assert_success
}

@test "&> redirect is not chaining: ALLOW" {
    _run_hook 'cmd &> out.txt'
    assert_success
}

@test "&>> append redirect is not chaining: ALLOW" {
    _run_hook 'cmd &>> out.txt'
    assert_success
}

@test ">&2 redirect is not chaining: ALLOW" {
    _run_hook 'echo oops >&2'
    assert_success
}

@test "<& input fd duplication is not chaining: ALLOW" {
    _run_hook 'cmd <&3'
    assert_success
}

@test "SBY8: |& is a pipe, and pipes are one command: ALLOW" {
    _run_hook 'echo a |& grep b'
    assert_success
}

@test "&& is still reported as AND, not as a lone &: BLOCK" {
    _run_hook 'true && false'
    assert_failure
    assert_output --partial "$_AND_MSG"
}

# =========================================================================
# ITEM 13 (NEW 2026-09-18): shell-carrier bodies are scanned for operators
# =========================================================================

@test "(NEW 2026-09-18) SBY10: bash -c with && in the body: BLOCK" {
    _run_hook 'bash -c "echo a && echo b"'
    assert_failure
    assert_output --partial "$_AND_MSG"
}

@test "(NEW 2026-09-18) SBY9: eval with ; in the body: BLOCK" {
    _run_hook 'eval "echo a; echo b"'
    assert_failure
    assert_output --partial "$_SEMI_MSG"
}

@test "(NEW 2026-09-18) sh -c with ; in the body: BLOCK" {
    _run_hook "sh -c 'echo a; echo b'"
    assert_failure
}

@test "(NEW 2026-09-18) absolute-path carrier /bin/bash -c: BLOCK" {
    _run_hook '/bin/bash -c "echo a; echo b"'
    assert_failure
}

@test "(NEW 2026-09-18) wrapper in front of the carrier (timeout N bash -c): BLOCK" {
    _run_hook 'timeout 5 bash -c "echo a && echo b"'
    assert_failure
}

@test "(NEW 2026-09-18) attached flag form bash -c\"...\": BLOCK" {
    _run_hook 'bash -c"echo a; echo b"'
    assert_failure
}

@test "(NEW 2026-09-18) nested carriers sh -c 'bash -c \"a; b\"': BLOCK" {
    _run_hook "sh -c 'bash -c \"echo a; echo b\"'"
    assert_failure
}

@test "(NEW 2026-09-18) xargs ... sh -c body with a chain: BLOCK" {
    _run_hook 'xargs -I{} sh -c "echo {} && rm {}"'
    assert_failure
}

@test "(NEW 2026-09-18) & inside a carrier body: BLOCK" {
    _run_hook 'bash -c "sleep 1 & echo second"'
    assert_failure
    assert_output --partial "$_AMP_MSG"
}

@test "carrier body with a compound command (exemption applies inside too): ALLOW" {
    _run_hook "bash -c 'for i in 1; do :; done'"
    assert_success
}

@test "carrier body with a single command: ALLOW" {
    _run_hook "sh -c 'echo hi'"
    assert_success
}

@test "python3 -c is NOT a shell carrier (SFP9): ALLOW" {
    _run_hook 'python3 -c "import os; print(os.getcwd())"'
    assert_success
}

@test "awk program is NOT a shell carrier (SFP3): ALLOW" {
    _run_hook "awk '{ if (x) print; }' f"
    assert_success
}

@test "git commit -m message with a semicolon is NOT a carrier body: ALLOW" {
    _run_hook 'git commit -m "fix: a; then b"'
    assert_success
}

@test "carrier body that is a command substitution (residual R3): ALLOW" {
    _run_hook 'bash -c "$(echo a; echo b)"'
    assert_success
}

@test "source with a plain filename argument: ALLOW" {
    _run_hook 'source "setup.sh"'
    assert_success
}

# =========================================================================
# ITEM 14 (NEW 2026-09-18): # comments
# =========================================================================

@test "(NEW 2026-09-18) SFP1: && inside a trailing comment: ALLOW" {
    _run_hook 'echo hi # this && that'
    assert_success
}

@test "(NEW 2026-09-18) whole-line comment then one command: ALLOW" {
    _run_hook $'# comment\necho a'
    assert_success
}

@test "(NEW 2026-09-18) ; inside a trailing comment: ALLOW" {
    _run_hook 'ls -la # then; also'
    assert_success
}

@test "# inside double quotes is not a comment (no chain present): ALLOW" {
    _run_hook 'echo "#not a comment && x"'
    assert_success
}

@test "# inside double quotes does not hide a real && after it: BLOCK" {
    _run_hook 'echo "#x" && rm y'
    assert_failure
    assert_output --partial "$_AND_MSG"
}

@test "# not at word start (a#b) does not start a comment: BLOCK" {
    _run_hook 'echo a#b && c'
    assert_failure
    assert_output --partial "$_AND_MSG"
}

@test "comment on line 1 does not hide the line-2 command: BLOCK" {
    _run_hook $'echo a # c\necho b'
    assert_failure
}

@test "comment cannot hide a chain on a later line: BLOCK" {
    _run_hook $'echo a # && b\nrm x; rm y'
    assert_failure
}

# =========================================================================
# DEFERRED items 11 and 12 -- KNOWN RESIDUALS, ALLOW today
# =========================================================================
# These are chains that the hook does NOT catch. They are recorded as ALLOW so
# that a future change which deliberately flips them shows up as a failing
# test to be updated, rather than passing silently. See the hook header's
# "Known residuals" block (R1, R2) and findings items 11/12 (deferred for
# medium false-positive risk).

@test "RESIDUAL R2 (item 12, probe SBY2): bare subshell with ;: ALLOW today" {
    _run_hook '(echo a; echo b)'
    assert_success
}

@test "RESIDUAL R2 (item 12, probe SBY3): bare subshell with &&: ALLOW today" {
    _run_hook '(echo a && rm x)'
    assert_success
}

@test "RESIDUAL R2 (item 12): (cd x && make) idiom: ALLOW today" {
    _run_hook '(cd build && make)'
    assert_success
}

@test "RESIDUAL R1 (item 11, probe SBY5): chain after a closed for loop: ALLOW today" {
    _run_hook 'for i in 1; do :; done; echo chained'
    assert_success
}

@test "RESIDUAL R1 (item 11, probe SBY6): chain after a closed if block: ALLOW today" {
    _run_hook 'if true; then :; fi; rm x'
    assert_success
}

@test "RESIDUAL R1 (item 11, probe SML5): newline chain after a closed for loop: ALLOW today" {
    _run_hook $'for i in 1; do :; done\nrm x'
    assert_success
}

# R6 is a DELIBERATE scope residual, not a deferred item: the hook's carrier
# set is the LOCAL shell set, so a remote command body (`ssh host '...'`) is
# not decomposed and its chain is not counted -- the one-command rule governs
# what THIS Bash call runs locally. See the hook header's R6 and
# agent_reference/BOUNDARIES.md (enforce-single-command row, known residuals).
# bash-safety.sh deliberately takes the opposite view (it promotes quoted
# spans after `ssh`), so this pin is single-command-only. (Added 2026-09-26.)
@test "RESIDUAL R6: ssh remote command body with && is not decomposed: ALLOW today" {
    _run_hook "ssh deploy@host 'cd /srv/app && git pull'"
    assert_success
}

# =========================================================================
# Performance -- a timed-out hook ALLOWS the call (Anthropic hooks docs), so
# slow is the same as broken. settings.json allows 5 s; assert well under.
# =========================================================================

@test "20 kB single-line command completes in under 2 s" {
    local big
    big="echo $(printf 'x%.0s' $(seq 1 20000))"
    run bash -c '
        start=$(date +%s%N)
        jq -n --arg c "$1" "{tool_name:\"Bash\",tool_input:{command:\$c}}" | bash "$2" >/dev/null 2>&1
        end=$(date +%s%N)
        echo $(( (end - start) / 1000000 ))
    ' _ "$big" "$ENFORCE_SINGLE_COMMAND_SH"
    assert_success
    [ "$output" -lt 2000 ]
}

@test "20 kB heavily quoted single-line command completes in under 2 s" {
    local big
    big="echo $(printf '"a;b" %.0s' $(seq 1 2500))"
    run bash -c '
        start=$(date +%s%N)
        jq -n --arg c "$1" "{tool_name:\"Bash\",tool_input:{command:\$c}}" | bash "$2" >/dev/null 2>&1
        end=$(date +%s%N)
        echo $(( (end - start) / 1000000 ))
    ' _ "$big" "$ENFORCE_SINGLE_COMMAND_SH"
    assert_success
    [ "$output" -lt 2000 ]
}

@test "500-line heredoc completes in under 2 s" {
    local body big
    body="$(seq 1 500 | sed 's/^/line ; and && more /')"
    big="$(printf 'cat <<EOF > f\n%s\nEOF' "$body")"
    run bash -c '
        start=$(date +%s%N)
        jq -n --arg c "$1" "{tool_name:\"Bash\",tool_input:{command:\$c}}" | bash "$2" >/dev/null 2>&1
        end=$(date +%s%N)
        echo $(( (end - start) / 1000000 ))
    ' _ "$big" "$ENFORCE_SINGLE_COMMAND_SH"
    assert_success
    [ "$output" -lt 2000 ]
}
