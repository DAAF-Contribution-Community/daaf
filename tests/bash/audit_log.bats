#!/usr/bin/env bats
# ============================================================================
# Tests for audit-log.sh -- PostToolUse (unmatched) append-only audit trail
# ============================================================================
# Contract (from the hook header): every tool invocation appends one JSONL
# record to `${CLAUDE_PROJECT_DIR}/.claude/logs/audit.jsonl` carrying
# timestamp, session_id, tool, a tool-specific target summary, daaf_version,
# model, and agent_type ("orchestrator" on the main thread, the subagent type
# otherwise). agent_id is present ONLY for subagent calls.
#
# Log destination is redirectable: LOG_DIR derives from CLAUDE_PROJECT_DIR, so
# every test here points it at a fake project tree inside the bats temp dir.
# The model field reads a /tmp coordination cache (/tmp/claude-model-{sid})
# written by context-reporter.sh -- this suite only READS that path via the
# hook and never writes to /tmp; absent cache yields "unknown" (asserted).
#
# Exit code: always 0 -- a PostToolUse hook must never block execution.
#
# 2026-09-24 hook-maintenance pass: the record is now built in a single jq
# pass (NUL bytes survive as \u0000 instead of being dropped by bash command
# substitution -- B8), and `target` is redacted of secret-shaped substrings
# before it is written (defect #4). The SECRET-REDACTION and NUL sections
# below were flipped from the previous CURRENT-BEHAVIOR pins.
#
# 2026-09-26 (hook bundle revision _a): `target` is also redacted of the
# literal VALUES of credential-named environment variables, as
# [REDACTED:env:<NAME>]. The VALUE-BASED REDACTION section sets its OWN fake
# DAAFTEST_* variables and asserts on those only. Those tests FAIL on hooks
# without the feature (the 2026-09-24 bundle copy) by design.
# Revision _b (2026-09-27, installed 2026-09-27): the value step runs on a
# 65,536-char window BEFORE the 4,000-char regex cap, a failed value step
# falls back to a second pass that keeps every field but withholds the
# target, and an xtrace guard is added. The "(_b)" tests and the marker pin
# (three carriers) fail on hooks_a by design.
# Revision _c (2026-09-27): the 4,000-char cap applies to EVERY target, the
# pattern step is wrapped in try/catch, a 128-char tail margin is dropped
# when the cap cut the input, the value stream carries a pair-count check,
# the value-feeding printf is `builtin printf`, and a missing jq still
# writes the all-"unknown" record. The "(_c)" tests fail on the _b hook by
# design until _c is installed; run them against
#   research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/hook_patches/hooks_c/audit-log.sh
# Revision _d (2026-10-01): inline-literal gaps F1 closed (rule 9 accepts a
# hyphenated api-key header name and a segment-bounded pass / passphrase key;
# new rule 10 credential-flag; new rule 11 url-userinfo) and the F4 counter
# false positive fixed (a purely numeric value on a token-named key is kept).
# Review fixes (2026-10-02): quoted rule-9 values run to the closing quote,
# rule 11 runs to the last "@", and new rule 12 redacts the password part of
# curl --user / -u (curl commands only, incl. a backslash line continuation).
# _d was installed 2026-10-02; all "(_d)" cases pass on the live hook.
# The "(_d)" tests build every credential-shaped fixture at run time with
# tests/bash/helpers/fake_shapes.bash (read its NO-LITERAL RULE before adding
# a case) and check outcomes with its masked checks only -- never
# assert_output / refute_output on a generated value. The gap cases and the
# F4 counter case fail on the _c hook by design until _d is installed; run
# them against
#   research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/hook_patches/hooks_d/audit-log.sh
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   AUDIT_LOG_SH=/path/to/draft.sh bats audit_log.bats
# The cross-hook agreement test also runs output-scanner.sh; override it with
#   OUTPUT_SCANNER_SH=/path/to/draft.sh
# ============================================================================

load 'test_helper'
load 'helpers/fake_shapes'

AUDIT_LOG_SH="${AUDIT_LOG_SH:-${REPO_ROOT}/.claude/hooks/audit-log.sh}"
OUTPUT_SCANNER_SH="${OUTPUT_SCANNER_SH:-${REPO_ROOT}/.claude/hooks/output-scanner.sh}"

setup() {
    common_setup
    export AUDIT_LOG_SH OUTPUT_SCANNER_SH
    FAKE_PROJECT="${TEST_DIR}/proj"
    LOG_FILE="${FAKE_PROJECT}/.claude/logs/audit.jsonl"
    mkdir -p "$FAKE_PROJECT"
    export FAKE_PROJECT LOG_FILE
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---

# Feed a payload (on stdin) to the hook with the redirected destination.
_emit() {
    printf '%s' "$1" | env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH"
}

# Log a Bash call whose command is $1, then print the logged target.
# Secret-shaped fixtures are assembled from fragments at the call sites so the
# literals never appear whole in this file (shape-matches only, not secrets).
_bash_target() {
    _emit "$(jq -nc --arg c "$1" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    jq -r '.target' < <(tail -1 "$LOG_FILE")
}

# =========================================================================
# Static checks
# =========================================================================

@test "audit-log.sh parses without errors" {
    run bash -n "$AUDIT_LOG_SH"
    assert_success
}

@test "audit-log.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "$AUDIT_LOG_SH"
    assert_success
}

# =========================================================================
# Destination is redirectable and created on demand
# =========================================================================

@test "CLAUDE_PROJECT_DIR redirects the log into the fake project tree" {
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"echo hi"}}'
    [ -f "$LOG_FILE" ]
}

@test "log directory is created if it does not exist" {
    [ ! -d "${FAKE_PROJECT}/.claude/logs" ]
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"ls"}}'
    [ -d "${FAKE_PROJECT}/.claude/logs" ]
}

@test "records are APPENDED, not overwritten" {
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"one"}}'
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"two"}}'
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"three"}}'
    run wc -l < "$LOG_FILE"
    assert_output "3"
}

@test "each record is a single self-contained JSON line (valid JSONL)" {
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"one"}}'
    _emit '{"session_id":"s2","tool_name":"Read","tool_input":{"file_path":"/x"}}'
    run jq -e -s 'length == 2' "$LOG_FILE"
    assert_success
}

# =========================================================================
# Record schema
# =========================================================================

@test "record carries the full documented field set" {
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"echo hi"}}'
    run jq -e 'has("timestamp") and has("session_id") and has("tool")
               and has("target") and has("daaf_version") and has("model")
               and has("agent_type")' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "timestamp is UTC ISO-8601 with a Z suffix" {
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"x"}}'
    run jq -r '.timestamp' < <(tail -1 "$LOG_FILE")
    assert_success
    [[ "$output" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

@test "agent_type defaults to 'orchestrator' and agent_id is omitted" {
    _emit '{"session_id":"s1","tool_name":"Bash","tool_input":{"command":"x"}}'
    run jq -e '.agent_type == "orchestrator" and (has("agent_id") | not)' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "subagent call: agent_type is the subagent type and agent_id is present" {
    _emit '{"session_id":"s2","agent_type":"code-reviewer","agent_id":"ag-9","tool_name":"Read","tool_input":{"file_path":"/x/y"}}'
    run jq -e '.agent_type == "code-reviewer" and .agent_id == "ag-9"' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "model is 'unknown' when the context-reporter /tmp cache is absent" {
    # The hook READS /tmp/claude-model-{session_id} (the sanctioned coordination
    # cache). This test uses a session id that cannot have a cache entry, so the
    # documented "unknown" fallback is exercised without writing to /tmp.
    _emit '{"session_id":"bats-no-such-session-9f3a","tool_name":"Bash","tool_input":{"command":"x"}}'
    run jq -r '.model' < <(tail -1 "$LOG_FILE")
    assert_output "unknown"
}

# =========================================================================
# Per-tool target extraction
# =========================================================================

@test "Bash target is the command string" {
    _emit '{"session_id":"s","tool_name":"Bash","tool_input":{"command":"echo hello"}}'
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "echo hello"
}

@test "Bash target is truncated to 200 characters" {
    local long
    long="$(printf 'x%.0s' $(seq 1 300))"
    _emit "$(jq -nc --arg c "$long" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run jq -r '.target | length' < <(tail -1 "$LOG_FILE")
    assert_output "200"
}

@test "Read/Write/Edit target is the file path" {
    _emit '{"session_id":"s","tool_name":"Write","tool_input":{"file_path":"/daaf/a.md"}}'
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "/daaf/a.md"
}

@test "Glob/Grep target is the pattern" {
    _emit '{"session_id":"s","tool_name":"Grep","tool_input":{"pattern":"AKIA"}}'
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "AKIA"
}

@test "Task/Agent target is the dispatch description" {
    _emit '{"session_id":"s","tool_name":"Agent","tool_input":{"description":"scope the repo","subagent_type":"search-agent"}}'
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "scope the repo"
}

@test "WebFetch target is the url" {
    _emit '{"session_id":"s","tool_name":"WebFetch","tool_input":{"url":"https://example.com/x"}}'
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "https://example.com/x"
}

@test "unrecognized tool: target is empty but the record is still written" {
    _emit '{"session_id":"s","tool_name":"SomeNewTool","tool_input":{"weird":"payload"}}'
    run jq -e '.tool == "SomeNewTool" and .target == ""' < <(tail -1 "$LOG_FILE")
    assert_success
}

# =========================================================================
# Never-block posture on degenerate input
# =========================================================================

@test "missing fields: exits 0 and records the documented 'unknown' fallbacks" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH" <<<'{}'
    assert_success
    run jq -e '.session_id == "unknown" and .tool == "unknown"' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "empty stdin: exits 0 without crashing" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH" < /dev/null
    assert_success
}

@test "malformed stdin: exits 0 without crashing" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH" <<<"not json {{{"
    assert_success
}

@test "unreadable log directory: exits 0 (audit loss, never a block)" {
    mkdir -p "${FAKE_PROJECT}/.claude/logs"
    chmod 500 "${FAKE_PROJECT}/.claude/logs"
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH" \
        <<<'{"session_id":"s","tool_name":"Bash","tool_input":{"command":"x"}}'
    chmod 700 "${FAKE_PROJECT}/.claude/logs"
    assert_success
}

# =========================================================================
# Secret redaction (2026-09-24 hook-maintenance pass, defect #4)
#
# DEFECT FIXED: the hook performed NO redaction -- a Bash command containing
# a credential was recorded verbatim (up to the 200-char truncation), and the
# sibling output-scanner.sh inspects only tool_response (the OUTPUT side), so
# a secret typed into a command was scanned by neither. The previous
# CURRENT-BEHAVIOR pins (verbatim logging; `grep -ci redact` == 0) are
# flipped below, as their comment instructed.
#
# DESIRED BEHAVIOR (now pinned): `target` is passed through redact() before
# the line is written; secret-shaped substrings become [REDACTED:<family>].
# The families reuse output-scanner.sh's patterns (agreement is tested at the
# end of this section) plus Authorization values, 16+-char Bearer tokens, and
# literal values assigned to credential-named keys. Every test in this section
# except the no-false-positive ones FAILS on the pre-fix hook.
# =========================================================================

@test "AWS key ID in a command is redacted, placeholder present (regression: was verbatim)" {
    run _bash_target "export TOK=AKIA""IOSFODNN7EXAMPLE"
    refute_output --partial "IOSFODNN7EXAMPLE"
    assert_output "export TOK=[REDACTED:aws-access-key-id]"
}

@test "the hook source contains redaction logic (probe flipped: count is non-zero)" {
    run grep -ci "redact\|sanitize\|mask" "$AUDIT_LOG_SH"
    [ "$output" -gt 0 ]
}

@test "sk- API key is redacted" {
    run _bash_target "curl -H x-api-key:sk-""abcdefghijklmnopqrstuvwxyz0123 https://api.example.com"
    refute_output --partial "abcdefghijklmnopqrstuvwxyz0123"
    assert_output --partial "[REDACTED:api-key]"
}

@test "Stripe live key is redacted" {
    run _bash_target "stripe login --api-key sk_live_""abcdefghijklmnopqrstuvwx"
    refute_output --partial "abcdefghijklmnopqrstuvwx"
    assert_output --partial "[REDACTED:stripe-live-key]"
}

@test "GitHub token is redacted" {
    run _bash_target "git clone https://ghp_""abcdefghijklmnopqrstuvwxyz01@github.com/o/r"
    refute_output --partial "abcdefghijklmnopqrstuvwxyz01"
    assert_output --partial "[REDACTED:github-token]"
}

@test "AWS secret access key assignment: value redacted, key name kept" {
    run _bash_target "export AWS_SECRET_ACCESS_KEY=""abcdefghij0123456789abcdefghij0123456789"
    refute_output --partial "abcdefghij0123456789abcdefghij0123456789"
    assert_output --partial "AWS_SECRET_ACCESS_KEY=[REDACTED:"
}

@test "PEM private-key block is redacted from BEGIN through END (body included)" {
    run _bash_target "printf '%s' '-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAbodybodybody
-----END RSA PRIVATE KEY-----' > k.pem"
    refute_output --partial "MIIEowIBAAKCAQEAbodybodybody"
    refute_output --partial "BEGIN RSA PRIVATE KEY"
    assert_output --partial "[REDACTED:private-key]"
}

@test "Authorization header: short Bearer value redacted, scheme kept" {
    run _bash_target 'curl -H "Authorization: Bearer abc123" https://api.example.com'
    refute_output --partial "abc123"
    assert_output --partial "Authorization: Bearer [REDACTED:authorization]"
}

@test "Authorization header: Basic credential redacted" {
    run _bash_target 'curl -H "authorization: basic dXNlcjpwYXNz" https://x'
    refute_output --partial "dXNlcjpwYXNz"
    assert_output --partial "[REDACTED:authorization]"
}

@test "standalone Bearer token (16+ chars) is redacted" {
    run _bash_target "http GET https://x 'Bearer abcdefghijklmnop1234'"
    refute_output --partial "abcdefghijklmnop1234"
    assert_output --partial "Bearer [REDACTED:bearer-token]"
}

@test "literal value assigned to a credential-named key is redacted" {
    run _bash_target "export HARVARD_DATAVERSE_API_KEY=1234abcd-""5678-90ef-aaaa"
    refute_output --partial "1234abcd-5678-90ef-aaaa"
    assert_output "export HARVARD_DATAVERSE_API_KEY=[REDACTED:credential-assignment]"
}

@test "a dollar-VAR reference assigned to a credential-named key is kept (not a literal)" {
    run _bash_target 'export X_API_KEY="$HARVARD_DATAVERSE_API_KEY"'
    assert_output 'export X_API_KEY="$HARVARD_DATAVERSE_API_KEY"'
}

@test "redaction also applies to non-Bash targets (WebFetch URL query token)" {
    _emit '{"session_id":"s","tool_name":"WebFetch","tool_input":{"url":"https://h.example/x?access_token=abcdefgh1234&q=1"}}'
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    refute_output --partial "abcdefgh1234"
    assert_output "https://h.example/x?access_token=[REDACTED:credential-assignment]&q=1"
}

# Redaction runs BEFORE the 200-char cut. Cutting first would leave a partial
# key ("sk-abcdef") too short to match any pattern -- a leak that looks benign.
@test "a secret straddling the 200-char cut is redacted, not left as a partial prefix" {
    local pad
    pad="$(printf 'x%.0s' $(seq 1 190))"
    run _bash_target "${pad} sk-""abcdefghijklmnopqrstuvwxyz0123"
    refute_output --partial "sk-abc"
    [ "${#output}" -eq 200 ]
}

@test "no false positives: git SHA, max_tokens=4096, and prose 'secret' pass unchanged" {
    run _bash_target 'git show 9cb0801f2a3b4c5d6e7f8091a2b3c4d5e6f70819 && echo max_tokens=4096 "secret sauce"'
    assert_output 'git show 9cb0801f2a3b4c5d6e7f8091a2b3c4d5e6f70819 && echo max_tokens=4096 "secret sauce"'
}

# Cross-hook agreement: every credential shape output-scanner.sh FLAGS on the
# output side must be REDACTED by audit-log.sh on the input side. Each entry is
# "fixture|core" where core is the substring that must not reach the log.
@test "cross-hook agreement: every family output-scanner flags, audit-log redacts" {
    local -a cases=(
        "AKIA""IOSFODNN7EXAMPLE|IOSFODNN7EXAMPLE"
        "AWS_SECRET_ACCESS_KEY=""abcdefghij0123456789abcdefghij0123456789|abcdefghij0123456789abcdefghij0123456789"
        "sk-""abcdefghijklmnopqrstuvwxyz0123|abcdefghijklmnopqrstuvwxyz0123"
        "sk_live_""abcdefghijklmnopqrstuvwx|abcdefghijklmnopqrstuvwx"
        "ghp_""abcdefghijklmnopqrstuvwxyz01|abcdefghijklmnopqrstuvwxyz01"
        "-----BEGIN RSA PRIVATE KEY-----|BEGIN RSA PRIVATE KEY"
        "-----BEGIN PRIVATE KEY-----|BEGIN PRIVATE KEY"
        "Authorization: Bearer ""aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa|aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    local entry fixture core scan target
    for entry in "${cases[@]}"; do
        fixture="${entry%%|*}"
        core="${entry#*|}"
        scan="$(jq -nc --arg r "$fixture" '{tool_name:"Bash",tool_response:$r}' | bash "$OUTPUT_SCANNER_SH")"
        if [[ "$scan" != *"Potential secrets detected"* ]]; then
            echo "output-scanner did not flag fixture: ${fixture:0:24}..."
            return 1
        fi
        target="$(_bash_target "echo ${fixture}")"
        if [[ "$target" == *"$core"* ]]; then
            echo "audit-log did not redact fixture: ${fixture:0:24}... -> ${target:0:60}"
            return 1
        fi
    done
}

# =========================================================================
# NUL bytes (2026-09-24 hook-maintenance pass, B8)
#
# DEFECT FIXED: every field went through `$(… | jq -r …)`; bash command
# substitution drops NUL bytes, so "/daaf/a\0b" was logged as "/daaf/ab" and
# bash printed "ignored null byte in input" on the hook's stderr. The record
# is now built in one jq pass, whose -c output escapes the NUL as \u0000. All
# three tests FAIL on the pre-fix hook.
# =========================================================================

@test "Read target preserves an embedded NUL as a JSON u0000 escape (regression: was stripped)" {
    _emit '{"session_id":"s","tool_name":"Read","tool_input":{"file_path":"/daaf/a\u0000b"}}'
    run jq -e '.target == "/daaf/a\u0000b"' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "Bash command with NUL is logged escaped, not stripped" {
    _emit '{"session_id":"s","tool_name":"Bash","tool_input":{"command":"echo a\u0000b"}}'
    run jq -e '.target == "echo a\u0000b"' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "hook emits no 'ignored null byte' warning on stderr" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH" \
        <<<'{"session_id":"s","tool_name":"Read","tool_input":{"file_path":"/daaf/a\u0000b"}}'
    assert_success
    refute_output --partial "null byte"
}

# =========================================================================
# Hardening pins for the single-pass rewrite (pass on both old and new hook)
# =========================================================================

@test "malformed stdin still writes one record with the 'unknown' fallbacks" {
    run env CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH" <<<"not json {{{"
    assert_success
    run jq -e '.session_id == "unknown" and .tool == "unknown" and .target == ""' < <(tail -1 "$LOG_FILE")
    assert_success
    run wc -l < "$LOG_FILE"
    assert_output "1"
}

@test "path-shaped session_id: model cache lookup skipped (model unknown), session_id logged verbatim" {
    _emit '{"session_id":"../../etc/x","tool_name":"Bash","tool_input":{"command":"ls"}}'
    run jq -e '.model == "unknown" and .session_id == "../../etc/x"' < <(tail -1 "$LOG_FILE")
    assert_success
}

# =========================================================================
# Value-based redaction (2026-09-26, hook bundle revision _a)
#
# Pattern rules cannot recognize a secret with no characteristic shape. The
# hook therefore replaces literal occurrences of credential-named env var
# VALUES with [REDACTED:env:<NAME>] before the pattern rules and the 200-char
# cut. Each test sets its OWN fake variable; `fakevalue_0123456789abcdef`
# matches none of the pattern rules, so a redaction below comes from the
# value-based step alone. Assertions check the WHOLE log line, not just the
# target, so a value leaking into any field would fail the test.
# =========================================================================

ENV_FAKE_VAL="fakevalue_0123456789abcdef"

# Log a payload ($2) with extra env assignments ($1, space-separated
# NAME=VALUE words) using the redirected destination.
_emit_env() {
    local -a assigns
    read -r -a assigns <<<"$1"
    printf '%s' "$2" | env "${assigns[@]}" CLAUDE_PROJECT_DIR="$FAKE_PROJECT" bash "$AUDIT_LOG_SH"
}

@test "value-based: the hook carries the SECRET-NAME-VOCAB v1 marker and exact vocabulary" {
    run grep -A1 -xF '# SECRET-NAME-VOCAB v1 — keep identical in: output-scanner.sh, audit-log.sh, run_with_capture.sh' "$AUDIT_LOG_SH"
    assert_success
    assert_output --partial 'SECRET_NAME_VOCAB="KEY KEYS APIKEY TOKEN TOKENS SECRET SECRETS PASS PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDENTIALS CREDS AUTH COOKIE COOKIES SESSION DSN PAT"'
}

@test "value-based: fake env value in a Bash command is redacted by NAME and absent from the log line" {
    _emit_env "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}" \
        "$(jq -nc --arg c "curl -s https://api.example.org/data/${ENV_FAKE_VAL}/rows" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run tail -1 "$LOG_FILE"
    refute_output --partial "$ENV_FAKE_VAL"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "curl -s https://api.example.org/data/[REDACTED:env:DAAFTEST_FAKE_API_KEY]/rows"
}

@test "value-based: fake env value in a WebFetch URL is redacted and absent from the log line" {
    _emit_env "DAAFTEST_FAKE_TOKEN=${ENV_FAKE_VAL}" \
        "$(jq -nc --arg u "https://h.example/x?k=${ENV_FAKE_VAL}&q=1" '{session_id:"s",tool_name:"WebFetch",tool_input:{url:$u}}')"
    run tail -1 "$LOG_FILE"
    refute_output --partial "$ENV_FAKE_VAL"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "https://h.example/x?k=[REDACTED:env:DAAFTEST_FAKE_TOKEN]&q=1"
}

@test "value-based: a value straddling the 200-char cut is redacted before the cut, never left partial" {
    local pad
    pad="$(printf 'x%.0s' $(seq 1 190))"
    _emit_env "DAAFTEST_FAKE_SECRET=${ENV_FAKE_VAL}" \
        "$(jq -nc --arg c "${pad} ${ENV_FAKE_VAL}" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    refute_output --partial "fakevalue"
    [ "${#output}" -eq 200 ]
}

@test "value-based: longest value wins when one value contains another" {
    _emit_env "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL} DAAFTEST_FAKE_SESSION_TOKEN=${ENV_FAKE_VAL}_longer" \
        "$(jq -nc --arg c "echo ${ENV_FAKE_VAL}_longer ${ENV_FAKE_VAL}" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "echo [REDACTED:env:DAAFTEST_FAKE_SESSION_TOKEN] [REDACTED:env:DAAFTEST_FAKE_API_KEY]"
}

@test "value-based: a regex-special value is replaced literally, not as a pattern" {
    _emit_env "DAAFTEST_FAKE_TOKEN=fake.*value+[0-9]" \
        "$(jq -nc '{session_id:"s",tool_name:"Bash",tool_input:{command:"echo fakeXXvalue5 fake.*value+[0-9]"}}')"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "echo fakeXXvalue5 [REDACTED:env:DAAFTEST_FAKE_TOKEN]"
}

@test "value-based: short, path, numeric, allowlisted and non-credential values are NOT redacted" {
    _emit_env "DAAFTEST_FAKE_KEY=abc1234 DAAFTEST_FAKE_AUTH=/daaf/fake/auth/file DAAFTEST_FAKE_PAT=1234567890 DBUS_SESSION_BUS_ADDRESS=unix:abstract=fakebus_0123456789 DAAFTEST_KEYBOARD=${ENV_FAKE_VAL}" \
        "$(jq -nc --arg c "echo abc1234 /daaf/fake/auth/file 1234567890 unix:abstract=fakebus_0123456789 ${ENV_FAKE_VAL}" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "echo abc1234 /daaf/fake/auth/file 1234567890 unix:abstract=fakebus_0123456789 ${ENV_FAKE_VAL}"
}

@test "value-based: record stays valid single-line JSON with NUL preserved alongside a redaction" {
    _emit_env "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}" \
        "$(jq -nc --arg p "/daaf/${ENV_FAKE_VAL}/a" '{session_id:"s",tool_name:"Read",tool_input:{file_path:($p + "\u0000b")}}')"
    run jq -e '.target == "/daaf/[REDACTED:env:DAAFTEST_FAKE_API_KEY]/a\u0000b"' < <(tail -1 "$LOG_FILE")
    assert_success
    run wc -l < "$LOG_FILE"
    assert_output "1"
}

# --- Revision _b (2026-09-27) ---
# These run the hook under `env -i` (fake DAAFTEST_* variables only), so a
# hook without the xtrace guard can only ever trace fake values.

# Log a payload ($2) with ONLY the given env assignments ($1) plus PATH and
# the redirected destination; hook stderr goes to ${TEST_DIR}/al.err.
_emit_isolated() {
    local hook="$1" payload="$2"; shift 2
    printf '%s' "$payload" | env -i PATH="$PATH" CLAUDE_PROJECT_DIR="$FAKE_PROJECT" "$@" \
        bash "$hook" 2>"${TEST_DIR}/al.err"
}

@test "value-based (_b): a value longer than the 4,000-char cap is redacted whole, no prefix logged" {
    local v
    v="${ENV_FAKE_VAL}$(printf '%*s' 5000 '' | tr ' ' z)"
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc --arg c "curl -H X:${v} https://h.example" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')" \
        "DAAFTEST_FAKE_API_KEY=${v}"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "curl -H X:[REDACTED:env:DAAFTEST_FAKE_API_KEY] https://h.example"
}

# The fallback is exercised on a copy of the hook whose first pass cannot
# open its value file (sed adds a nonexistent --rawfile); the copy lives in
# the bats temp dir and the sed must change exactly that one line.
_make_fault_copy() {
    sed 's|--arg fallback "" \\|--arg fallback "" --rawfile envpairs /nonexistent/daaftest-fault \\|' \
        "$AUDIT_LOG_SH" > "${TEST_DIR}/al_fault.sh"
    [ "$(diff "$AUDIT_LOG_SH" "${TEST_DIR}/al_fault.sh" | grep -c '^>')" -eq 1 ]
}

@test "fallback (_b): value-step failure keeps session_id/tool/agent_type and withholds the target" {
    _make_fault_copy
    _emit_isolated "${TEST_DIR}/al_fault.sh" \
        "$(jq -nc --arg c "echo ${ENV_FAKE_VAL}" '{session_id:"s9",tool_name:"Bash",tool_input:{command:$c},agent_type:"research-executor",agent_id:"a1"}')" \
        "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}"
    run jq -e '.session_id == "s9" and .tool == "Bash" and .agent_type == "research-executor" and .agent_id == "a1" and .target == "[REDACTED:env-step-unavailable]"' < <(tail -1 "$LOG_FILE")
    assert_success
    run tail -1 "$LOG_FILE"
    refute_output --partial "$ENV_FAKE_VAL"
    [ ! -s "${TEST_DIR}/al.err" ]
}

@test "fallback (_b): with no credential-named value the pattern-redacted target is kept" {
    _make_fault_copy
    _emit_isolated "${TEST_DIR}/al_fault.sh" \
        '{"session_id":"s9","tool_name":"Read","tool_input":{"file_path":"/daaf/x.py"}}'
    run jq -e '.session_id == "s9" and .target == "/daaf/x.py"' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "fallback (_b): malformed stdin still yields the all-'unknown' record" {
    _make_fault_copy
    _emit_isolated "${TEST_DIR}/al_fault.sh" "not json {{{" "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}"
    run jq -e '.session_id == "unknown" and .tool == "unknown" and .target == ""' < <(tail -1 "$LOG_FILE")
    assert_success
}

@test "value-based (_b): an inherited xtrace (SHELLOPTS) never writes a value to stderr" {
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc --arg c "echo ${ENV_FAKE_VAL}" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')" \
        SHELLOPTS=xtrace "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}"
    run grep -c "$ENV_FAKE_VAL" "${TEST_DIR}/al.err"
    assert_output "0"
}

# --- Pattern cap on every target (review of _b, 2026-09-27: W1, W2, NIT 1)
# jq's regex engine errors out (retry limit) on long keyword-dense text:
# "token" repeated fails from about 6,000 chars. Fixtures are repeated plain
# words; nothing here is credential-shaped. All run under `env -i`.

# W2 pin. Passes on _b too; on _c it also fails if the cap is deleted,
# because the try guard would then turn the target into the failure marker.
@test "pattern cap: an 8,000-char keyword-dense Bash command keeps the record and logs its first 200 chars" {
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc '{session_id:"s",tool_name:"Bash",tool_input:{command:("token" * 1600)}}')"
    run jq -e '.session_id == "s" and .tool == "Bash" and .target == ("token" * 40)' < <(tail -1 "$LOG_FILE")
    assert_success
}

# W1 / W2 non-Bash twin: under _b each of these was logged as unknown/unknown.
@test "pattern cap (_c): an 8,000-char keyword-dense non-Bash target keeps the record, capped at 3,872 chars" {
    local entry tool field
    for entry in Grep:pattern Glob:pattern Task:description Agent:description WebFetch:url Read:file_path; do
        tool="${entry%%:*}"
        field="${entry#*:}"
        _emit_isolated "$AUDIT_LOG_SH" \
            "$(jq -nc --arg t "$tool" --arg f "$field" '{session_id:"s",tool_name:$t,tool_input:{($f):("token" * 1600)}}')"
        if ! jq -e --arg t "$tool" '.session_id == "s" and .tool == $t and .target == ("token" * 1600)[0:3872]' < <(tail -1 "$LOG_FILE") >/dev/null; then
            echo "record lost or target wrong for ${tool}: $(tail -1 "$LOG_FILE" | jq -c '{session_id,tool,len:(.target|length)}')"
            return 1
        fi
    done
}

# The try guard, exercised on a copy whose cap is raised far past the regex
# failure threshold (the sed must change exactly the one def line).
@test "pattern guard (_c): a regex failure keeps session_id/tool and marks the target" {
    sed 's/^def pattern_cap: 4000;$/def pattern_cap: 100000;/' "$AUDIT_LOG_SH" > "${TEST_DIR}/al_nocap.sh"
    [ "$(diff "$AUDIT_LOG_SH" "${TEST_DIR}/al_nocap.sh" | grep -c '^>')" -eq 1 ]
    _emit_isolated "${TEST_DIR}/al_nocap.sh" \
        "$(jq -nc '{session_id:"s7",tool_name:"Grep",tool_input:{pattern:("token" * 3000)}}')"
    run jq -e '.session_id == "s7" and .tool == "Grep" and .target == "[REDACTED:pattern-step-failed]"' < <(tail -1 "$LOG_FILE")
    assert_success
    [ ! -s "${TEST_DIR}/al.err" ]
}

# NIT 1, non-Bash: the cap cuts "note_token=plainwordsvalue" after "=pl", a
# value too short for rule 9. The tail margin keeps that prefix out.
@test "tail margin (_c): a credential-style assignment cut by the cap leaves no partial value in a non-Bash target" {
    local pad
    pad="$(printf 'x%.0s' $(seq 1 3986))"
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc --arg p "${pad} note_token=plainwordsvalue" '{session_id:"s",tool_name:"Grep",tool_input:{pattern:$p}}')"
    run jq -e '.target == ("x" * 3872)' < <(tail -1 "$LOG_FILE")
    assert_success
}

# NIT 1, Bash: a 3,981-char value redacted early shrinks the window, which
# would pull the cut "b_token=pl" into the logged 200 chars without the margin.
@test "tail margin (_c): an earlier redaction cannot pull a cut-off value into the Bash 200 chars" {
    local pad
    pad="$(printf 'w%.0s' $(seq 1 3981))"
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc --arg c "a_token=${pad} b_token=plainwordsvalue" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run jq -e '.session_id == "s" and .tool == "Bash" and (.target | contains("=pl") | not)' < <(tail -1 "$LOG_FILE")
    assert_success
}

# NIT 2: a copy whose value stream is EMPTY although one credential-named
# value exists. Without the pair-count check the value is simply not redacted.
@test "pair-count check (_c): an incomplete value stream withholds the target instead of logging the value" {
    sed 's|for sv_name in "${CRED_NAMES\[@\]}"; do|for sv_name in ; do|' "$AUDIT_LOG_SH" > "${TEST_DIR}/al_short.sh"
    [ "$(diff "$AUDIT_LOG_SH" "${TEST_DIR}/al_short.sh" | grep -c '^>')" -eq 1 ]
    _emit_isolated "${TEST_DIR}/al_short.sh" \
        "$(jq -nc --arg c "echo ${ENV_FAKE_VAL}" '{session_id:"s8",tool_name:"Bash",tool_input:{command:$c}}')" \
        "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}"
    run jq -e '.session_id == "s8" and .tool == "Bash" and .target == "[REDACTED:env-step-unavailable]"' < <(tail -1 "$LOG_FILE")
    assert_success
    run tail -1 "$LOG_FILE"
    refute_output --partial "$ENV_FAKE_VAL"
}

# NIT 6: an exported shell function named printf records its arguments in a
# file. The payload itself carries no value, so a value in that file could
# only have come from the value-feeding printf.
@test "value-based (_c): an exported printf function never receives a value" {
    local rec="${TEST_DIR}/printf_args.txt"
    _emit_isolated "$AUDIT_LOG_SH" \
        '{"session_id":"s","tool_name":"Bash","tool_input":{"command":"echo hello"}}' \
        "BASH_FUNC_printf%%=() { builtin printf \"\$@\"; builtin printf '%s\\n' \"\$*\" >> '${rec}'; }" \
        "DAAFTEST_FAKE_API_KEY=${ENV_FAKE_VAL}"
    [ -s "$rec" ]
    run grep -c "$ENV_FAKE_VAL" "$rec"
    assert_output "0"
}

# NIT 5: PATH holds shims for the few external commands the hook needs, but
# no jq (and no git). The firing must still be recorded, as valid JSON.
@test "no jq (_c): the all-'unknown' record is still written, and stderr stays silent" {
    local bin="${TEST_DIR}/nojq_bin" c
    mkdir -p "$bin"
    for c in cat date mkdir; do
        printf '#!/bin/sh\nexec %s "$@"\n' "$(command -v "$c")" > "${bin}/${c}"
        chmod +x "${bin}/${c}"
    done
    printf '%s' '{"session_id":"s","tool_name":"Bash","tool_input":{"command":"echo hi"}}' \
        | env -i PATH="$bin" CLAUDE_PROJECT_DIR="$FAKE_PROJECT" "$(command -v bash)" "$AUDIT_LOG_SH" 2>"${TEST_DIR}/al.err"
    run jq -e '.session_id == "unknown" and .tool == "unknown" and .target == "" and .model == "unknown"
               and (.timestamp | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"))' < <(tail -1 "$LOG_FILE")
    assert_success
    [ ! -s "${TEST_DIR}/al.err" ]
}

# Cross-hook agreement for the shared vocabulary: the SECRET_NAME_VOCAB and
# SECRET_NAME_ALLOWLIST lines must be byte-identical in audit-log.sh and
# output-scanner.sh. The three carriers are output-scanner.sh, audit-log.sh
# and scripts/run_with_capture.sh (bash-safety.sh does not carry the block:
# its env guard was deferred on 2026-09-26).
@test "cross-hook agreement: SECRET_NAME_VOCAB and SECRET_NAME_ALLOWLIST identical in audit-log and output-scanner" {
    local a s
    a="$(grep -E '^SECRET_NAME_(VOCAB|ALLOWLIST)=' "$AUDIT_LOG_SH")"
    s="$(grep -E '^SECRET_NAME_(VOCAB|ALLOWLIST)=' "$OUTPUT_SCANNER_SH")"
    [ -n "$a" ]
    [ "$a" = "$s" ]
}

# scripts/run_with_capture.sh carries the same block (its owner pins it in
# run_with_capture.bats). When it is present there, the whole block -- the
# marker line and the two lines after it -- must match audit-log.sh's and
# output-scanner.sh's byte for byte; skipped if that file has no marker yet.
@test "cross-hook agreement: marker block identical in audit-log, output-scanner and run_with_capture.sh (when marked)" {
    local rwc="${REPO_ROOT}/scripts/run_with_capture.sh" a s r
    if ! grep -q '^# SECRET-NAME-VOCAB v1 ' "$rwc"; then
        skip "run_with_capture.sh carries no SECRET-NAME-VOCAB v1 marker (probe: grep)"
    fi
    a="$(grep -A2 '^# SECRET-NAME-VOCAB v1 ' "$AUDIT_LOG_SH")"
    s="$(grep -A2 '^# SECRET-NAME-VOCAB v1 ' "$OUTPUT_SCANNER_SH")"
    r="$(grep -A2 '^# SECRET-NAME-VOCAB v1 ' "$rwc")"
    [ "$(printf '%s\n' "$a" | wc -l)" -eq 3 ]
    [ "$a" = "$s" ]
    [ "$a" = "$r" ]
}

# Behavioral agreement: a fake credential-named value that output-scanner
# flags on the output side is redacted by audit-log on the input side.
@test "cross-hook agreement: an env value output-scanner flags, audit-log redacts" {
    local scan
    scan="$(jq -nc --arg r "x ${ENV_FAKE_VAL} y" '{tool_name:"Bash",tool_response:$r}' \
        | env "DAAFTEST_FAKE_CREDENTIAL=${ENV_FAKE_VAL}" bash "$OUTPUT_SCANNER_SH")"
    [[ "$scan" == *"value of DAAFTEST_FAKE_CREDENTIAL appears"* ]]
    _emit_env "DAAFTEST_FAKE_CREDENTIAL=${ENV_FAKE_VAL}" \
        "$(jq -nc --arg c "echo ${ENV_FAKE_VAL}" '{session_id:"s",tool_name:"Bash",tool_input:{command:$c}}')"
    run tail -1 "$LOG_FILE"
    refute_output --partial "$ENV_FAKE_VAL"
    assert_output --partial "[REDACTED:env:DAAFTEST_FAKE_CREDENTIAL]"
}

# =========================================================================
# Inline-literal gaps F1 and the F4 counter (2026-10-01, revision _d)
#
# Every credential-shaped fixture below is BUILT AT RUN TIME by
# helpers/fake_shapes.bash (split name fragments + sha256-derived filler)
# and checked with fake_expect_redacted / fake_expect_kept, which print
# nothing on success and only a MASKED line on failure. Benign fixtures
# (non-matches) may use assert_output. Nothing here echoes a generated value.
# =========================================================================

# Log $1 as a Bash command; LINE = the whole logged record. Prints nothing.
_d_log_bash() {
    _bash_target "$1" >/dev/null
    LINE="$(tail -1 "$LOG_FILE")"
}

# Log $3 as field $2 of tool $1; LINE = the whole logged record.
_d_log_tool() {
    _emit "$(jq -nc --arg t "$1" --arg f "$2" --arg v "$3" '{session_id:"s",tool_name:$t,tool_input:{($f):$v}}')"
    LINE="$(tail -1 "$LOG_FILE")"
}

@test "fake_shapes helper (_d): passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "${REPO_ROOT}/tests/bash/helpers/fake_shapes.bash"
    assert_success
}

# Sourced by a plain `set -uo pipefail` shell it prints nothing, its builders
# work, and a failing check prints a masked report that never holds the value.
@test "fake_shapes helper (_d): silent when sourced under set -u; a failing check prints only a masked line" {
    run bash -c 'set -uo pipefail
        . "$1"
        fake_api_key_header
        [ "${#FS_VALUE}" -eq 32 ] || exit 3
        fake_expect_redacted selftest "$FS_TEXT" && exit 4
        exit 0' _ "${REPO_ROOT}/tests/bash/helpers/fake_shapes.bash"
    [ "$status" -eq 0 ]
    fake_api_key_header
    [[ "$output" == *'case "selftest"'* ]]
    [[ "$output" == *"<fake>"* ]]
    [[ "$output" != *"$FS_VALUE"* ]]
    [[ "$output" != *"${FS_VALUE:0:8}"* ]]
    run bash -c 'set -uo pipefail; . "$1"' _ "${REPO_ROOT}/tests/bash/helpers/fake_shapes.bash"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "F1a (_d): API-key request header value is redacted, header name kept" {
    fake_api_key_header
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1a header" "$LINE"
    [[ "$LINE" == *"${FS_NAME}: [REDACTED:credential-assignment]"* ]]
}

@test "F1b (_d): password flag values are redacted (space, 1-3 chars, quoted with a space, multi-word, short =)" {
    fake_password_flag
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b space" "$LINE"
    [[ "$LINE" == *"${FS_NAME} [REDACTED:credential-flag] --host"* ]]
    fake_password_flag 3
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b short" "$LINE"
    fake_password_flag 1 space "--db-""pass"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b one char, multi-word flag" "$LINE"
    fake_password_flag 20 quoted
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b quoted" "$LINE"
    fake_password_flag 16 space "--client-""secret"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b client secret flag" "$LINE"
    fake_password_flag 16 space "--api-""key"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b api-key flag" "$LINE"
    fake_password_flag 3 equals
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b short equals" "$LINE"
}

# An 8+-character "=" value is caught by rule 9 first; rule 10 must not
# relabel it.
@test "F1b (_d): a long --flag=value keeps the credential-assignment marker" {
    fake_password_flag 24 equals
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1b long equals" "$LINE"
    [[ "$LINE" != *"[REDACTED:credential-flag]"* ]]
}

@test "F1b (_d): non-matches kept: plural and longer flags, a VAR reference, stdin, bypass" {
    local pw="--pass""word"
    run _bash_target "llm --max-tokens 4096 --token-file ./t.txt --bypass cache"
    assert_output "llm --max-tokens 4096 --token-file ./t.txt --bypass cache"
    run _bash_target "mysql ${pw} \"\$DB_PW\" -h db"
    assert_output "mysql ${pw} \"\$DB_PW\" -h db"
    run _bash_target "mysql ${pw} - -h db"
    assert_output "mysql ${pw} - -h db"
}

@test "F1c (_d): URL userinfo password is redacted; scheme, user and host kept (Bash and WebFetch)" {
    fake_url_userinfo
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1c bash" "$LINE"
    [[ "$LINE" == *"://${FS_NAME}:[REDACTED:url-userinfo]@db.example.invalid:5432/analytics"* ]]
    fake_url_userinfo 1
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1c one char" "$LINE"
    fake_url_userinfo 24
    _d_log_tool WebFetch url "${FS_TEXT#psql }"
    fake_expect_redacted "F1c webfetch" "$LINE"
}

@test "F1c (_d): non-matches kept: a port after the host, user-only git userinfo" {
    run _bash_target "curl https://example.invalid:8080/x && git clone ssh://git@example.invalid/o/r"
    assert_output "curl https://example.invalid:8080/x && git clone ssh://git@example.invalid/o/r"
}

@test "F1d (_d): PASS / PASSPHRASE / bare pass assignments are redacted" {
    fake_pass_assignment
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1d DB_PASS" "$LINE"
    [[ "$LINE" == *"${FS_NAME}=[REDACTED:credential-assignment]"* ]]
    fake_pass_assignment 16 "GPG_""PASS""PHRASE"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1d PASSPHRASE" "$LINE"
    fake_pass_assignment 12 "pa""ss"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F1d bare pass" "$LINE"
}

@test "F1d (_d): non-matches kept: bypass, compass, passenger keys" {
    run _bash_target "echo bypass=abcdefghij compass=abcdefghij passenger=abcdefghij"
    assert_output "echo bypass=abcdefghij compass=abcdefghij passenger=abcdefghij"
}

@test "F4 (_d): a numeric token counter is kept unredacted (plain and JSON-style)" {
    fake_token_counter
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "F4 counter" "$LINE"
    [[ "$LINE" != *"[REDACTED:"* ]]
    fake_token_counter 12
    FS_TEXT="echo '{\"input_tokens\": ${FS_VALUE}}'"
    FS_NEEDLE="input_tokens\\\": ${FS_VALUE}"
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "F4 json counter" "$LINE"
}

# The exemption is for token-named keys and numeric values only.
@test "F4 (_d): a non-numeric token assignment and a numeric password are still redacted" {
    fake_token_assignment
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F4 sibling" "$LINE"
    fake_digits 12 daaf-fake-numeric-pw
    FS_VALUE="$FS_FILL"
    FS_TEXT="export DB_""PASS""WORD=${FS_VALUE}"
    FS_NEEDLE="=${FS_VALUE}"
    FS_MARKER="credential-assignment"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "F4 numeric password" "$LINE"
}

# Rules 10 and 11 run after the earlier rules and the value step; a value
# that already is a [REDACTED: marker must keep its family.
@test "no relabel (_d): earlier markers survive the new rules (sk- key after --api-key, env values in flag, header and userinfo)" {
    fake_filler 24 daaf-fake-sk
    FS_VALUE="$FS_FILL"
    FS_TEXT="tool --api-""key sk-""${FS_VALUE} --verbose"
    FS_NEEDLE="${FS_VALUE}"
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "relabel sk" "$LINE" api-key
    [[ "$LINE" != *"[REDACTED:credential-flag]"* ]]
    # An Agent description, not a Bash command: the markers lengthen the text
    # past the Bash 200-char cut.
    local hdr="X-""Api""-Key" pw="--pass""word" sch="post""gres"
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc --arg c "tool ${pw} ${ENV_FAKE_VAL} -H \"${hdr}: ${ENV_FAKE_VAL}\" ${sch}://u:${ENV_FAKE_VAL}@h.invalid/d" '{session_id:"s",tool_name:"Agent",tool_input:{description:$c}}')" \
        "DAAFTEST_FAKE_PASSWORD=${ENV_FAKE_VAL}"
    run jq -r '.target' < <(tail -1 "$LOG_FILE")
    assert_output "tool ${pw} [REDACTED:env:DAAFTEST_FAKE_PASSWORD] -H \"${hdr}: [REDACTED:env:DAAFTEST_FAKE_PASSWORD]\" ${sch}://u:[REDACTED:env:DAAFTEST_FAKE_PASSWORD]@h.invalid/d"
}

# Rule 11 accepts an earlier marker as the user part, so a password after a
# user name redacted by the value step is still caught.
@test "F1c (_d): a password after a user name already redacted by the value step is redacted too" {
    local sch="post""gres"
    fake_filler 16 daaf-fake-userinfo-after-env
    FS_VALUE="$FS_FILL"
    FS_TEXT="${sch}://${ENV_FAKE_VAL}:${FS_VALUE}@h.invalid/d"
    FS_NEEDLE=":${FS_VALUE}@"
    FS_MARKER="url-userinfo"
    _emit_isolated "$AUDIT_LOG_SH" \
        "$(jq -nc --arg c "$FS_TEXT" '{session_id:"s",tool_name:"Agent",tool_input:{description:$c}}')" \
        "DAAFTEST_FAKE_USER_TOKEN=${ENV_FAKE_VAL}"
    LINE="$(tail -1 "$LOG_FILE")"
    fake_expect_redacted "F1c env user" "$LINE"
    [[ "$LINE" == *"://[REDACTED:env:DAAFTEST_FAKE_USER_TOKEN]:[REDACTED:url-userinfo]@h.invalid/d"* ]]
}

# Documented residuals (README_d § 9): pinned so a change is noticed.
@test "residuals (_d): short -p flag, user-name-only userinfo and a header value under 8 chars are NOT redacted" {
    fake_filler 12 daaf-fake-short-flag
    FS_VALUE="$FS_FILL"
    FS_TEXT="mysql -u app -p ${FS_VALUE} -h db"
    FS_NEEDLE="-p ${FS_VALUE} -h"
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "residual -p" "$LINE"
    fake_filler 24 daaf-fake-user-only
    FS_VALUE="$FS_FILL"
    FS_TEXT="git clone https://${FS_VALUE}@git.example.invalid/o/r"
    FS_NEEDLE="//${FS_VALUE}@"
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "residual user-only" "$LINE"
    fake_api_key_header 6
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "residual short header" "$LINE"
}

# --- Revision _d review fixes (2026-10-02, Phase 4 reviews) ---

# Review N2: with no builder run there is no needle, so both checks must fail
# (not pass vacuously), and the report must not abort under set -u.
@test "fake_shapes helper (_d): checks fail closed with no builder run, and the report survives set -u" {
    run bash -c 'set -uo pipefail
        . "$1"
        fake_expect_kept nobuilder "plain text" && exit 4
        fake_expect_redacted nobuilder "plain text" credential-flag && exit 5
        exit 0' _ "${REPO_ROOT}/tests/bash/helpers/fake_shapes.bash"
    [ "$status" -eq 0 ]
    [[ "$output" == *'case "nobuilder": expected kept: no needle set'* ]]
    [[ "$output" == *'case "nobuilder": expected redacted: no needle set'* ]]
    [[ "$output" != *"unbound variable"* ]]
}

# Review W1: a quoted "=" value with a space. Rule 9 takes an 8+-character
# first word; it must now run on to the closing quote instead of leaving the
# rest of the quoted value in the log.
@test "F1b/F1d (_d): a quoted = value with a space is redacted whole (flag and assignment)" {
    fake_password_flag 20 quoted_equals
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W1 flag quoted equals" "$LINE"
    [[ "$LINE" == *"${FS_NAME}='[REDACTED:credential-assignment]' --host"* ]]
    fake_password_flag 10 quoted_equals
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W1 flag quoted equals, short first word" "$LINE"
    fake_pass_assignment 24 "" daaf-fake-pass-quoted quoted
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W1 PASS quoted" "$LINE"
    [[ "$LINE" == *"${FS_NAME}='[REDACTED:credential-assignment]'"* ]]
}

# Review W2: curl's --user / -u "name:password". Only the part after the
# first colon is replaced; the user name is kept.
@test "F1b (_d): curl --user / -u password is redacted, user name kept (long, short, attached, line continuation)" {
    fake_curl_user
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W2 curl --user" "$LINE"
    [[ "$LINE" == *"${FS_NAME}:[REDACTED:credential-flag] https"* ]]
    fake_curl_user 12 short
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W2 curl -u" "$LINE"
    fake_curl_user 3 attached
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W2 curl -u attached, short value" "$LINE"
    fake_curl_user 16 continued
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W2 curl --user after a line continuation" "$LINE"
}

# The curl rule is scoped to a curl command: a uid:gid or host:path value on
# another command's --user / -u is untouched, the scan stops at && ; | and at
# a newline that is not a line continuation, and a variable reference or
# --user-agent is not matched.
@test "F1b (_d): non-matches kept: non-curl --user uid:gid, -u host:path after && or a newline, curl --user-agent, a VAR password" {
    run _bash_target "podman exec --user 1000:1000 ctr id && rsync -u host:/src ./dst"
    assert_output "podman exec --user 1000:1000 ctr id && rsync -u host:/src ./dst"
    run _bash_target "curl -s https://example.invalid/a && rsync -u host:/src ./dst; ls -u a:b"
    assert_output "curl -s https://example.invalid/a && rsync -u host:/src ./dst; ls -u a:b"
    run _bash_target "curl -s https://example.invalid/a"$'\n'"rsync -u host:/src ./dst"
    assert_output "curl -s https://example.invalid/a"$'\n'"rsync -u host:/src ./dst"
    run _bash_target "curl -A x --user-agent ua:5 https://example.invalid/a"
    assert_output "curl -A x --user-agent ua:5 https://example.invalid/a"
    run _bash_target "curl -u \"app:\$API_PW\" https://example.invalid/a"
    assert_output "curl -u \"app:\$API_PW\" https://example.invalid/a"
}

# Review W3: a raw "@" inside a userinfo password; the password runs to the
# LAST "@" before the host.
@test "F1c (_d): a userinfo password holding a raw @ is redacted whole" {
    fake_url_userinfo 20 at
    _d_log_bash "$FS_TEXT"
    fake_expect_redacted "W3 raw at" "$LINE"
    [[ "$LINE" == *"://${FS_NAME}:[REDACTED:url-userinfo]@db.example.invalid:5432/analytics"* ]]
}

@test "F1c (_d): non-matches kept: an @ in the path or query of an ordinary URL" {
    run _bash_target "curl https://example.invalid:8080/a/b@c?x=y@z && curl http://example.invalid/u@v#w@x"
    assert_output "curl https://example.invalid:8080/a/b@c?x=y@z && curl http://example.invalid/u@v#w@x"
}

# Consistency review W1: rule 11 has no "$" / "-" exclusion. A userinfo
# password that is a variable reference or starts with "-" is redacted
# (accepted over-redaction, README_d R17); pinned so a change is noticed.
@test "F1c (_d): a userinfo VAR reference or dash-led password IS redacted (accepted over-redaction)" {
    local sch="post""gres"
    run _bash_target "psql ${sch}://u:\$PGPW@h.invalid/d && psql ${sch}://u:-x@h.invalid/d"
    assert_output "psql ${sch}://u:[REDACTED:url-userinfo]@h.invalid/d && psql ${sch}://u:[REDACTED:url-userinfo]@h.invalid/d"
}

# Review W3, documented residuals (README_d R16): a raw "/" in the password
# ends the authority match, and an e-mail-style user name (an "@" before the
# colon) is not matched. Pinned so a change is noticed.
@test "residuals (_d): a userinfo password with a raw / and an e-mail-style user name are NOT redacted" {
    local sch="post""gres"
    fake_filler 16 daaf-fake-slash-pw
    FS_VALUE="${FS_FILL:0:8}/${FS_FILL:8}"
    FS_TEXT="psql ${sch}://app:${FS_VALUE}@db.example.invalid/d"
    FS_NEEDLE=":${FS_VALUE}@"
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "residual raw slash" "$LINE"
    fake_filler 16 daaf-fake-email-user
    FS_VALUE="$FS_FILL"
    FS_TEXT="psql ${sch}://app@example.invalid:${FS_VALUE}@db.example.invalid/d"
    FS_NEEDLE=":${FS_VALUE}@"
    _d_log_bash "$FS_TEXT"
    fake_expect_kept "residual e-mail user" "$LINE"
}

# =========================================================================
# Registration
# =========================================================================

@test "registered as a PostToolUse hook under the unmatched ('') matcher" {
    run jq -r '
        [.hooks.PostToolUse[]
         | select(.hooks[].command | test("audit-log"))
         | .matcher] | join(",")
    ' "${REPO_ROOT}/.claude/settings.json"
    assert_success
    assert_output ""
}
