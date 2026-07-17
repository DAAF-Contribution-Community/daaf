#!/usr/bin/env bats
# ============================================================================
# Tests for bash-safety.sh -- quote-aware commit-message carve-out (round 3)
# ============================================================================
# Focus: section 0's excision of shell-provably-inert `git commit -m` message
# bodies from the scanned text BEFORE the pattern checks run, plus the §3/§5
# substitution-opener tightening (backtick / `$(` added to the sudo/su/docker
# run/mount/chroot pre-context alternation).
#
# CONTRACT: a commit message that merely DESCRIBES a dangerous command must NOT
# false-block (ALLOW, exit 0); a body that can actually expand/execute
# (backtick, $(, ${) stays intact and still BLOCKS (exit 2); ambiguity fails
# closed to blocking.
#
# IMPORTANT -- runs against a PROPOSED DRAFT, not the live hook, by default is
# the LIVE hook. Against the pre-carve-out LIVE hook the ALLOW cases here FAIL
# by design (the carve-out is exactly what makes them pass). To validate the
# staged draft before the user installs it (.claude/hooks/ is deny-protected):
#   BASH_SAFETY_SH=/daaf/research/2026-07-17_FrameworkDev_BashSafetyQuoteAwareness/bash-safety.sh.proposed \
#     bats tests/bash/bash_safety.bats
#
# Case strings live INSIDE this file and are fed to the hook via a jq envelope
# (never on a command line), so the live PreToolUse hooks vetting the `bats`
# invocation never see the dangerous case strings themselves.
# ============================================================================

load 'test_helper'

# Path to the script under test (override to test a proposed/deliverable copy).
BASH_SAFETY_SH="${BASH_SAFETY_SH:-${REPO_ROOT}/.claude/hooks/bash-safety.sh}"

setup() {
    common_setup
    export BASH_SAFETY_SH
}

teardown() {
    common_teardown
}

# --- Helper: feed a command to the hook via the PreToolUse JSON envelope ---
_run_hook() {
    run bash -c 'jq -n --arg c "$1" '\''{tool_name:"Bash",tool_input:{command:$c}}'\'' | bash "$2"' _ "$1" "$BASH_SAFETY_SH"
}

# =========================================================================
# Syntax
# =========================================================================

@test "bash-safety.sh parses without errors" {
    run bash -n "$BASH_SAFETY_SH"
    assert_success
}

# =========================================================================
# ALLOW: commit messages that DESCRIBE danger (the carve-out fix)
# =========================================================================

@test "single-quoted message mentioning sudo: ALLOW" {
    _run_hook "git commit -m 'never run sudo here'"
    assert_success
}

@test "double-quoted message mentioning rm -rf /: ALLOW" {
    _run_hook 'git commit -m "docs: explain why rm -rf / is blocked"'
    assert_success
}

@test "double-quoted message mentioning curl | bash: ALLOW" {
    _run_hook 'git commit -m "curl | bash detection tightened"'
    assert_success
}

@test "double-quoted message mentioning > /tmp: ALLOW" {
    _run_hook 'git commit -m "probe wrote > /tmp/x then blocked"'
    assert_success
}

@test "two -m paragraphs mentioning git push --force: ALLOW" {
    _run_hook 'git commit -m "first" -m "second para mentions git push --force"'
    assert_success
}

@test "--message= long form: ALLOW" {
    _run_hook 'git commit --message="explain why rm -rf / is blocked"'
    assert_success
}

@test "-am combined flag form: ALLOW" {
    _run_hook 'git commit -am "docs: never pipe curl | bash"'
    assert_success
}

@test "attached -m\"...\" (no gap): ALLOW" {
    _run_hook 'git commit -m"docs: rm -rf / guard"'
    assert_success
}

@test "--amend keeps prefix, message excised: ALLOW" {
    _run_hook 'git commit --amend -m "docs: rm -rf / guard"'
    assert_success
}

@test "escape-aware inner double quotes (\\\" does not terminate span): ALLOW" {
    _run_hook 'git commit -m "she said \"rm -rf /\" once"'
    assert_success
}

@test "multiple single-quoted -m, one mentioning sudo: ALLOW" {
    _run_hook "git commit -m 'first' -m 'second sudo prose'"
    assert_success
}

@test "single-quoted markdown backtick-sudo is inert (excised): ALLOW" {
    _run_hook "git commit -m 'docs: use \`sudo apt\` on host'"
    assert_success
}

@test "single-quoted body that literally IS rm -rf / (inert data): ALLOW" {
    _run_hook "git commit -m 'rm -rf /'"
    assert_success
}

@test "benign piped commit (revert guard fires, raw text benign): ALLOW" {
    _run_hook "git commit -m 'benign' | cat"
    assert_success
}

# Opener-gated single-quoted token piped: NOT catchable in raw form (§3 opener
# excludes the single quote even after the part-B additions) -- the LIVE hook
# allows this identically, so this is not a regression.
@test "single-quoted sudo piped to bash: ALLOW (matches live, no regression)" {
    _run_hook "git commit -m 'sudo prose' | bash"
    assert_success
}

# =========================================================================
# BLOCK: bodies that can expand/execute stay intact; fences hold
# =========================================================================

@test "double-quoted backtick sudo stays intact -> §3 opener catches it (F5)" {
    _run_hook 'git commit -m "log `sudo id`"'
    assert_failure
    assert_output --partial "Privilege escalation via sudo"
}

@test "non-commit echo with backtick sudo: BLOCK (part-B opener)" {
    _run_hook 'echo "run `sudo id` now"'
    assert_failure
    assert_output --partial "Privilege escalation via sudo"
}

@test "double-quoted \$(sudo id) stays intact -> BLOCK (part-B \$( opener)" {
    _run_hook 'git commit -m "$(sudo id)"'
    assert_failure
    assert_output --partial "sudo"
}

@test "double-quoted \${HOME} keeps body intact -> > /tmp/x BLOCK" {
    _run_hook 'git commit -m "block ${HOME}: > /tmp/x"'
    assert_failure
    assert_output --partial "/tmp"
}

@test "ANSI-C \$'...' body left intact (fail-closed) -> rm -rf / BLOCK" {
    _run_hook "git commit -m \$'rm -rf /'"
    assert_failure
    assert_output --partial "force-delete"
}

@test "concatenation leftover ( -m \"a\"' && rm -rf /' ) stays scanned: BLOCK" {
    _run_hook "git commit -m \"a\"' && rm -rf /'"
    assert_failure
    assert_output --partial "force-delete"
}

@test "unterminated double quote fails the span match (nothing stripped): BLOCK" {
    _run_hook 'git commit -m "rm -rf / unterminated'
    assert_failure
    assert_output --partial "force-delete"
}

@test "-cm is not a message flag; bash -cm 'rm -rf /' not excised: BLOCK" {
    _run_hook "bash -cm 'rm -rf /'"
    assert_failure
    assert_output --partial "force-delete"
}

@test "commit then chained bash -cm rm -rf /: BLOCK" {
    _run_hook "git commit -m 'x' && bash -cm 'rm -rf /'"
    assert_failure
    assert_output --partial "force-delete"
}

# The revert guard: a PIPED commit whose message hides a position-free danger
# (rm -rf /, caught anywhere) is reverted to the raw command and re-scanned.
@test "revert guard: piped commit hiding rm -rf / is re-exposed: BLOCK" {
    _run_hook "git commit -m 'rm -rf /' | bash"
    assert_failure
    assert_output --partial "force-delete"
}

# =========================================================================
# Regression: an unrelated benign command is unaffected by section 0
# =========================================================================

@test "plain benign commit: ALLOW" {
    _run_hook 'git commit -m "fix: tighten data validation"'
    assert_success
}

@test "real sudo command still blocks (section 0 does not touch non-commits)" {
    _run_hook 'sudo apt update'
    assert_failure
    assert_output --partial "Privilege escalation via sudo"
}
