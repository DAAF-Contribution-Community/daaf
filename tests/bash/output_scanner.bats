#!/usr/bin/env bats
# ============================================================================
# Tests for output-scanner.sh -- PostToolUse (unmatched) secret-leak scanner
# ============================================================================
# Contract (from the hook header): scan `tool_response` (first 10KB) for
# common credential shapes -- AWS access key IDs, AWS secret access keys,
# generic `sk-` keys, Stripe live keys, GitHub tokens, PEM private-key
# headers, and long Bearer tokens -- and, when any match, print a WARNING
# block on stdout so the model sees it. This is ADVISORY only: the hook never
# blocks, always exits 0, and prints nothing on clean output.
#
# Response shapes (STRUCTURED-RESPONSE, 2026-09-24 hook-maintenance pass):
# the fixed extractor is `(.tool_response // "" | tostring)[0:10000]`, so a
# STRING, ARRAY, OBJECT, or scalar tool_response is scanned as text. The
# previous extractor sliced without `tostring`; an OBJECT made jq error out,
# the response resolved to empty, and nothing was scanned. The object tests
# below were flipped from that CURRENT-BEHAVIOR pin to the desired behavior.
# The fix was installed on 2026-09-26 (it was staged as
# research/2026-09-18_FrameworkDev_SafetyHookHardening/output-scanner.sh.proposed).
#
# VALUE-BASED DETECTION (2026-09-26, hook bundle revision _a): the scanner
# also warns when the literal value of a credential-named environment
# variable appears in the response. Those tests (section near the end) set
# their OWN fake DAAFTEST_* variables and assert on those only; the hook also
# sees the real environment at test time, which is fine because it never
# prints a value. They FAIL on hooks without the feature (the 2026-09-24
# bundle copy) by design.
# Revision _b (2026-09-27, installed 2026-09-27) adds a 512-char comparison
# cap, an xtrace guard and a glob-literal case; the "(_b)" tests also fail
# on hooks_a by design, and the marker pin now reads the _b marker text
# (three carriers). The 512-cap pins (positive and negative) pass on _b.
# Revision _c (2026-09-27) feeds the shape probes with printf instead of
# echo; its "(_c)" test fails on the _b hook by design until _c is
# installed; run it against
#   research/2026-09-24_FrameworkDev_ClaudeCode_Upgrade_2.1.281/hook_patches/hooks_c/output-scanner.sh
#
# SCRIPT UNDER TEST is parameterized for pre-deployment testing of a draft:
#   OUTPUT_SCANNER_SH=/path/to/draft.sh bats output_scanner.bats
# ============================================================================

load 'test_helper'

OUTPUT_SCANNER_SH="${OUTPUT_SCANNER_SH:-${REPO_ROOT}/.claude/hooks/output-scanner.sh}"

setup() {
    common_setup
    export OUTPUT_SCANNER_SH
}

teardown() {
    common_teardown
}

# --- Fixture helpers ---
# Synthetic, non-functional credential shapes are assembled from fragments so
# the literals never appear whole in this file (they are shape-matches only,
# not real secrets, but keeping them split avoids tripping other scanners).

# Run the hook against a string tool_response.
_scan() {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg r "$1" '{
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "cat somefile"},
        "tool_response": $r
    }')
}

# =========================================================================
# Static checks
# =========================================================================

@test "output-scanner.sh parses without errors" {
    run bash -n "$OUTPUT_SCANNER_SH"
    assert_success
}

@test "output-scanner.sh passes shellcheck at -S warning" {
    if ! command -v shellcheck >/dev/null 2>&1; then
        skip "shellcheck not installed (probe: command -v shellcheck)"
    fi
    run shellcheck -x -S warning "$OUTPUT_SCANNER_SH"
    assert_success
}

# =========================================================================
# DETECT: each documented credential family
# =========================================================================

@test "detects an AWS Access Key ID (AKIA + 16 uppercase/digits)" {
    _scan "aws_key = AKIA""IOSFODNN7EXAMPLE and more text"
    assert_success
    assert_output --partial "WARNING: Potential secrets detected"
    assert_output --partial "AWS Access Key ID detected"
}

@test "detects an AWS Secret Access Key assignment" {
    _scan "AWS_SECRET_ACCESS_KEY=abcdefghij0123456789abcdefghij0123456789"
    assert_success
    assert_output --partial "AWS Secret Access Key detected"
}

@test "detects a generic sk- API key" {
    _scan "key: sk-""abcdefghijklmnopqrstuvwxyz0123"
    assert_success
    assert_output --partial "API key detected"
}

@test "detects a Stripe live key" {
    _scan "sk_live_""abcdefghijklmnopqrstuvwx"
    assert_success
    assert_output --partial "Stripe live key detected"
}

@test "detects a GitHub token" {
    _scan "token=ghp_""abcdefghijklmnopqrstuvwxyz01"
    assert_success
    assert_output --partial "GitHub token detected"
}

# The PEM headers are split like the other shapes: a whole header literal in
# this file makes the pre-commit `detect-private-key` hook reject the commit
# (probed 2026-09-26: "Private key found: tests/bash/output_scanner.bats").
@test "detects a PEM private key header" {
    _scan "-----BEGIN RSA ""PRIVATE KEY-----"
    assert_success
    assert_output --partial "Private key block detected"
}

@test "detects an unprefixed PEM private key header" {
    _scan "-----BEGIN ""PRIVATE KEY-----"
    assert_success
    assert_output --partial "Private key block detected"
}

@test "detects a long Bearer token" {
    _scan "Authorization: Bearer aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert_success
    assert_output --partial "Long Bearer token detected"
}

@test "multiple families in one response: each is listed separately" {
    _scan "AKIA""IOSFODNN7EXAMPLE and ghp_""abcdefghijklmnopqrstuvwxyz01"
    assert_success
    assert_output --partial "AWS Access Key ID detected"
    assert_output --partial "GitHub token detected"
}

@test "warning text instructs the model not to propagate the value" {
    _scan "AKIA""IOSFODNN7EXAMPLE"
    assert_output --partial "Do NOT display, log, or commit these values"
}

# =========================================================================
# CLEAN: no false positives on ordinary developer output
# =========================================================================

@test "ordinary command output: silent (no warning, exit 0)" {
    _scan "total 24
drwxr-xr-x 3 appuser appuser 4096 Sep 23 10:00 scripts
-rw-r--r-- 1 appuser appuser  512 Sep 23 10:00 README.md"
    assert_success
    [ -z "$output" ]
}

# The hook's header claims no specific hash carve-out, but every credential
# pattern is prefix-anchored (AKIA, sk-, ghp_, ...), so bare hex digests do
# not match. These pin that property: a future broadened "high-entropy" rule
# that starts flagging hashes would surface here as a failing test.
@test "no false positive on a 40-char git SHA" {
    _scan "commit 9cb0801f2a3b4c5d6e7f8091a2b3c4d5e6f70819"
    assert_success
    [ -z "$output" ]
}

@test "no false positive on a sha256 digest" {
    _scan "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  data.parquet"
    assert_success
    [ -z "$output" ]
}

@test "no false positive on a short Bearer token (<50 chars)" {
    _scan "Authorization: Bearer abc123"
    assert_success
    [ -z "$output" ]
}

@test "no false positive on the word 'secret' in prose" {
    _scan "The secret sauce of this analysis is the fixed-effects specification."
    assert_success
    [ -z "$output" ]
}

@test "no false positive on a base64 blob without a credential prefix" {
    _scan "payload: QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVowMTIzNDU2Nzg5"
    assert_success
    [ -z "$output" ]
}

# =========================================================================
# Response-shape handling
# =========================================================================

@test "array tool_response is scanned (stringified before slicing)" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc '{
        "tool_name": "Read",
        "tool_response": [{"type":"text","text":"AKIA0123456789ABCDEF"}]
    }')
    assert_success
    assert_output --partial "AWS Access Key ID detected"
}

# DEFECT FIXED in the staged draft (2026-09-24 pass; see header). The old extractor
# `jq -r '.tool_response // "" | .[0:10000]'` failed on an OBJECT
# tool_response ("Cannot index object with object"), RESPONSE became empty,
# and the hook exited 0 at the empty-response guard WITHOUT scanning. Claude
# Code sends object-shaped tool_response payloads for several tools, so the
# scanner was a no-op for those. The fix stringifies first (`tostring`), so
# objects are scanned as their JSON text. The first test below is the
# regression case: it FAILS on the pre-fix hook (empty output).
@test "object tool_response IS scanned (regression: was silently skipped)" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc '{
        "tool_name": "Bash",
        "tool_response": {"stdout": "AKIA0123456789ABCDEF", "stderr": ""}
    }')
    assert_success
    assert_output --partial "AWS Access Key ID detected"
}

@test "nested object tool_response: a secret two levels deep is scanned" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg t "ghp_""abcdefghijklmnopqrstuvwxyz01" '{
        "tool_name": "Agent",
        "tool_response": {"content": [{"type": "text", "text": ("token=" + $t)}]}
    }')
    assert_success
    assert_output --partial "GitHub token detected"
}

# 2026-09-26 (Unit C1): regression cases for the object shapes the non-Bash
# tools send. The field layouts are ILLUSTRATIVE of those tools (a Read-style
# file object, Grep/Glob-style objects wrapping arrays), not pinned schemas --
# what matters is that the top level is an OBJECT, the shape that made the
# unfixed extractor fail. Each FAILS on the pre-fix hook (empty output).
@test "Read-style nested object (file.content) is scanned" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg k "AKIA""IOSFODNN7EXAMPLE" '{
        "tool_name": "Read",
        "tool_response": {"type": "text",
                          "file": {"filePath": "/daaf/config.txt",
                                   "content": ("aws_key = " + $k),
                                   "numLines": 1}}
    }')
    assert_success
    assert_output --partial "AWS Access Key ID detected"
}

@test "Grep-style object with a matches array is scanned" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg t "sk-""abcdefghijklmnopqrstuvwxyz0123" '{
        "tool_name": "Grep",
        "tool_response": {"mode": "content",
                          "matches": ["src/a.py:3:x = 1", ("src/b.py:7:key = " + $t)],
                          "numLines": 2}
    }')
    assert_success
    assert_output --partial "API key detected"
}

@test "Glob-style object with a filenames array is scanned" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg t "ghp_""abcdefghijklmnopqrstuvwxyz01" '{
        "tool_name": "Glob",
        "tool_response": {"filenames": ["/daaf/a.md", ("/daaf/leak_" + $t + ".txt")],
                          "numFiles": 2, "truncated": false}
    }')
    assert_success
    assert_output --partial "GitHub token detected"
}

# STRING shape must behave exactly as before the fix: `tostring` returns a
# string unchanged, so the 10KB window is still measured on the raw text. A
# secret that STARTS inside the window is caught; one that starts past it is
# not. These pass on BOTH the live and the fixed hook. The first is tight: the
# 20-char key ENDS exactly at char 10000, so slicing JSON-encoded text instead
# (`tojson` adds a leading quote) would push its last char out and fail it.
@test "string tool_response: secret inside the 10KB window is detected (unchanged)" {
    _scan "$(printf 'x%.0s' {1..9980})AKIA""IOSFODNN7EXAMPLE"
    assert_success
    assert_output --partial "AWS Access Key ID detected"
}

@test "string tool_response: secret past the 10KB window is not scanned (unchanged)" {
    _scan "$(printf 'x%.0s' {1..10000})AKIA""IOSFODNN7EXAMPLE"
    assert_success
    [ -z "$output" ]
}

@test "object tool_response with no secret: silent, exit 0" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc '{
        "tool_name": "Bash",
        "tool_response": {"stdout": "total 24", "stderr": "", "interrupted": false}
    }')
    assert_success
    [ -z "$output" ]
}

@test "scalar (numeric) tool_response: silent, exit 0" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc '{"tool_name":"Bash","tool_response":42}')
    assert_success
    [ -z "$output" ]
}

@test "empty tool_response: silent, exit 0" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc '{"tool_name":"Bash","tool_response":""}')
    assert_success
    [ -z "$output" ]
}

@test "absent tool_response field: silent, exit 0" {
    run bash "$OUTPUT_SCANNER_SH" < <(jq -nc '{"tool_name":"Bash","tool_input":{"command":"ls"}}')
    assert_success
    [ -z "$output" ]
}

# =========================================================================
# Never-block posture
# =========================================================================

@test "empty stdin: exits 0 without crashing" {
    run bash "$OUTPUT_SCANNER_SH" < /dev/null
    assert_success
    [ -z "$output" ]
}

@test "malformed stdin: exits 0 without crashing" {
    run bash "$OUTPUT_SCANNER_SH" <<<"not json {{{"
    assert_success
    [ -z "$output" ]
}

@test "a detected secret still exits 0 (advisory, never a block)" {
    _scan "AKIA""IOSFODNN7EXAMPLE"
    [ "$status" -eq 0 ]
}

# =========================================================================
# Value-based detection (2026-09-26, hook bundle revision _a)
#
# A secret with no recognizable shape (e.g. a UUID-shaped data-source API
# key) matches none of the seven families above. The scanner therefore also
# compares the response against the values of credential-named environment
# variables. Every test sets its OWN fake variable via `env`; the fake value
# `fakevalue_0123456789abcdef` matches none of the shape families, so any
# warning below comes from the value-based check alone.
# =========================================================================

FAKE_VAL="fakevalue_0123456789abcdef"

# Run the hook with extra env assignments ($1, space-separated NAME=VALUE
# words without spaces in values) against string response $2.
_scan_env() {
    local -a assigns
    read -r -a assigns <<<"$1"
    run env "${assigns[@]}" bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg r "$2" '{
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_response": $r
    }')
}

@test "value-based: the hook carries the SECRET-NAME-VOCAB v1 marker and exact vocabulary" {
    run grep -A1 -xF '# SECRET-NAME-VOCAB v1 — keep identical in: output-scanner.sh, audit-log.sh, run_with_capture.sh' "$OUTPUT_SCANNER_SH"
    assert_success
    assert_output --partial 'SECRET_NAME_VOCAB="KEY KEYS APIKEY TOKEN TOKENS SECRET SECRETS PASS PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDENTIALS CREDS AUTH COOKIE COOKIES SESSION DSN PAT"'
}

@test "value-based: raw value in a string response is flagged by variable NAME" {
    _scan_env "DAAFTEST_FAKE_API_KEY=${FAKE_VAL}" "fetched with key ${FAKE_VAL} ok"
    assert_success
    assert_output --partial "WARNING: Potential secrets detected"
    assert_output --partial "value of DAAFTEST_FAKE_API_KEY appears in this tool output"
}

@test "value-based: the warning names the variable but never contains the value" {
    _scan_env "DAAFTEST_FAKE_API_KEY=${FAKE_VAL}" "x ${FAKE_VAL} y"
    assert_success
    assert_output --partial "DAAFTEST_FAKE_API_KEY"
    refute_output --partial "$FAKE_VAL"
}

@test "value-based: value inside an OBJECT response is flagged" {
    run env "DAAFTEST_FAKE_TOKEN=${FAKE_VAL}" bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg v "$FAKE_VAL" '{
        "tool_name": "Bash",
        "tool_response": {"stdout": ("key=" + $v), "stderr": "", "interrupted": false}
    }')
    assert_success
    assert_output --partial "value of DAAFTEST_FAKE_TOKEN appears in this tool output"
    refute_output --partial "$FAKE_VAL"
}

# After `tostring`, an object's text escapes quote and backslash, so the raw
# value no longer appears verbatim; the JSON-escaped form must be checked too.
@test "value-based: JSON-escaped value (quote + backslash) inside an object is flagged" {
    local v='fake"quoted\value_0123456789'
    run env "DAAFTEST_FAKE_SECRET=${v}" bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg v "$v" '{
        "tool_name": "Bash",
        "tool_response": {"stdout": ("a " + $v + " b")}
    }')
    assert_success
    assert_output --partial "value of DAAFTEST_FAKE_SECRET appears in this tool output"
    refute_output --partial "quoted"
}

@test "value-based: newline-bearing value inside an object is flagged (escaped as \\n)" {
    local v=$'fakeline1_0123\nfakeline2_4567'
    run env "DAAFTEST_FAKE_PASSPHRASE=${v}" bash "$OUTPUT_SCANNER_SH" < <(jq -nc --arg v "$v" '{
        "tool_name": "Bash",
        "tool_response": {"stdout": $v}
    }')
    assert_success
    assert_output --partial "value of DAAFTEST_FAKE_PASSPHRASE appears in this tool output"
}

@test "value-based: a value shorter than 8 characters is ignored" {
    _scan_env "DAAFTEST_FAKE_API_KEY=abc1234" "the word abc1234 appears here"
    assert_success
    [ -z "$output" ]
}

@test "value-based: an absolute-path value is ignored" {
    _scan_env "DAAFTEST_FAKE_KEY=/daaf/fake/secret/path/file" "reading /daaf/fake/secret/path/file now"
    assert_success
    [ -z "$output" ]
}

@test "value-based: a URL value without userinfo is ignored" {
    _scan_env "DAAFTEST_FAKE_AUTH=https://auth.example.org/fake" "GET https://auth.example.org/fake 200"
    assert_success
    [ -z "$output" ]
}

@test "value-based: a URL value WITH userinfo is flagged" {
    _scan_env "DAAFTEST_FAKE_DSN=postgres://fakeuser:fakepw123@db.example.org/x" "connecting to postgres://fakeuser:fakepw123@db.example.org/x"
    assert_success
    assert_output --partial "value of DAAFTEST_FAKE_DSN appears in this tool output"
}

@test "value-based: pure numeric and boolean-word values are ignored" {
    _scan_env "DAAFTEST_FAKE_TOKEN=1234567890 DAAFTEST_FAKE_AUTH=disabled" "count 1234567890 and auth disabled"
    assert_success
    [ -z "$output" ]
}

@test "value-based: an allowlisted name is ignored (DBUS_SESSION_BUS_ADDRESS)" {
    _scan_env "DBUS_SESSION_BUS_ADDRESS=unix:abstract=fakebus_0123456789" "bus unix:abstract=fakebus_0123456789 up"
    assert_success
    [ -z "$output" ]
}

@test "value-based: a non-credential-named variable is ignored" {
    _scan_env "DAAFTEST_KEYBOARD_LAYOUT=${FAKE_VAL} DAAFTEST_NOTSECRET=${FAKE_VAL}" "x ${FAKE_VAL} y"
    assert_success
    [ -z "$output" ]
}

@test "value-based: name matching is case-insensitive on segments" {
    _scan_env "daaftest_fake_api_key=${FAKE_VAL}" "x ${FAKE_VAL} y"
    assert_success
    assert_output --partial "value of daaftest_fake_api_key appears in this tool output"
}

@test "value-based: a regex-special value is matched literally, not as a pattern" {
    # If the value were used as a regex, '.*' would match the unrelated text.
    _scan_env "DAAFTEST_FAKE_TOKEN=fake.*value+[0-9]" "unrelated text fakeXXvalue5"
    assert_success
    [ -z "$output" ]
    _scan_env "DAAFTEST_FAKE_TOKEN=fake.*value+[0-9]" "literal fake.*value+[0-9] here"
    assert_output --partial "value of DAAFTEST_FAKE_TOKEN appears in this tool output"
}

# The regex case above cannot tell a glob match from a literal one ('.*' is
# not a glob wildcard). A bare '*' can: as a glob it would match 'XX'.
@test "value-based: a glob-special value ('*') is matched literally, not as a glob" {
    _scan_env "DAAFTEST_FAKE_TOKEN=fake*value_12345" "unrelated text fakeXXvalue_12345"
    assert_success
    [ -z "$output" ]
    _scan_env "DAAFTEST_FAKE_TOKEN=fake*value_12345" "literal fake*value_12345 here"
    assert_output --partial "value of DAAFTEST_FAKE_TOKEN appears in this tool output"
}

@test "value-based: a match is still advisory (exit 0)" {
    _scan_env "DAAFTEST_FAKE_API_KEY=${FAKE_VAL}" "${FAKE_VAL}"
    [ "$status" -eq 0 ]
}

# Revision _b (2026-09-27): comparison length cap, xtrace guard, stderr
# silence. These run the hook under `env -i`, so ONLY the fake DAAFTEST_*
# variable is in its environment: on a hook without the xtrace guard the
# trace would otherwise carry real values into bats' failure output.
# They FAIL on hooks_a (no cap, no guard) by design.

@test "value-based (_b): a value longer than the 512-char cap is flagged when its prefix appears" {
    local v p
    v="${FAKE_VAL}$(printf '%*s' 600 '' | tr ' ' q)_tail"
    p="${v:0:520}"
    run env -i PATH="$PATH" "DAAFTEST_FAKE_API_KEY=${v}" bash "$OUTPUT_SCANNER_SH" \
        < <(jq -nc --arg r "x ${p} y" '{tool_name:"Bash",tool_response:$r}')
    assert_success
    assert_output --partial "value of DAAFTEST_FAKE_API_KEY appears in this tool output"
    refute_output --partial "$FAKE_VAL"
}

# Negative twin (review of _b, NIT 3): only the first 500 characters of the
# 631-character value appear. With the 512 cap the compared prefix is absent,
# so there is no warning; a smaller cap (<= 500) would warn and fail this.
@test "value-based (_b): a 500-char prefix of a longer value is NOT flagged (the cap is not smaller than 512)" {
    local v p
    v="${FAKE_VAL}$(printf '%*s' 600 '' | tr ' ' q)_tail"
    p="${v:0:500}"
    [ "${#v}" -eq 631 ]
    run env -i PATH="$PATH" "DAAFTEST_FAKE_API_KEY=${v}" bash "$OUTPUT_SCANNER_SH" \
        < <(jq -nc --arg r "x ${p} y" '{tool_name:"Bash",tool_response:$r}')
    assert_success
    [ -z "$output" ]
}

@test "value-based (_b): the hook carries the 512-char comparison cap" {
    run grep -cx 'SV_CMP_MAX=512' "$OUTPUT_SCANNER_SH"
    assert_output "1"
}

@test "value-based (_b): an inherited xtrace (SHELLOPTS) never writes a value to stderr" {
    local err="${TEST_DIR}/scan_xtrace.err"
    env -i PATH="$PATH" SHELLOPTS=xtrace "DAAFTEST_FAKE_API_KEY=${FAKE_VAL}" bash "$OUTPUT_SCANNER_SH" \
        < <(jq -nc --arg r "x ${FAKE_VAL} y" '{tool_name:"Bash",tool_response:$r}') >/dev/null 2>"$err"
    run grep -c "$FAKE_VAL" "$err"
    assert_output "0"
}

@test "value-based (_b): stderr is empty on a value match" {
    local err="${TEST_DIR}/scan_match.err" out
    out="$(env -i PATH="$PATH" "DAAFTEST_FAKE_API_KEY=${FAKE_VAL}" bash "$OUTPUT_SCANNER_SH" \
        < <(jq -nc --arg r "x ${FAKE_VAL} y" '{tool_name:"Bash",tool_response:$r}') 2>"$err")"
    [[ "$out" == *"value of DAAFTEST_FAKE_API_KEY appears"* ]]
    [ ! -s "$err" ]
}

# Revision _c (review of _b, NIT 6): with an inherited xpg_echo, `echo`
# stops at a literal \c, so a shape after it was never scanned. The probes
# now use printf. The fixture is the split AWS documentation example used
# above; it runs under `env -i`.
@test "shape probes (_c): an inherited xpg_echo cannot hide a secret behind a literal backslash-c" {
    run env -i PATH="$PATH" BASHOPTS=xpg_echo bash "$OUTPUT_SCANNER_SH" \
        < <(jq -nc --arg r "note \\c then AKIA""IOSFODNN7EXAMPLE" '{tool_name:"Bash",tool_response:$r}')
    assert_success
    assert_output --partial "AWS Access Key ID detected"
}

# =========================================================================
# Registration
# =========================================================================

@test "registered as a PostToolUse hook under the unmatched ('') matcher" {
    run jq -r '
        [.hooks.PostToolUse[]
         | select(.hooks[].command | test("output-scanner"))
         | .matcher] | join(",")
    ' "${REPO_ROOT}/.claude/settings.json"
    assert_success
    assert_output ""
}
