#!/usr/bin/env bash
# output-scanner.sh — PostToolUse hook that scans tool output for leaked secrets
#
# Checks tool_response content for seven credential shape families:
#   - AWS Access Key IDs (AKIA...)
#   - AWS Secret Access Key assignments (aws_secret_access_key = <40 chars>)
#   - Generic API keys (sk-...)
#   - Stripe live keys (sk_live_..., rk_live_..., pk_live_...)
#   - GitHub tokens (ghp_..., gho_..., ghs_..., ghr_..., github_pat_...)
#   - Private key headers (-----BEGIN...PRIVATE KEY-----)
#   - Long Bearer tokens (Bearer <50+ chars>)
# and for the literal VALUE of any credential-named environment variable
# (see VALUE-BASED DETECTION below).
#
# Response shapes: tool_response may be a STRING, an ARRAY, or an OBJECT
# (Claude Code sends object-shaped responses for several tools, e.g.
# {"stdout": ..., "stderr": ...}). Every shape is stringified with jq
# `tostring` before the first 10,000 characters are scanned, so non-string
# responses are scanned as their JSON text. Slicing an object without
# `tostring` makes jq fail ("Cannot index object with object"), which would
# leave nothing to scan.
#
# Probe input: the shape probes feed grep with `printf '%s\n'`, not `echo`.
# With an inherited xpg_echo (BASHOPTS=xpg_echo in the environment), `echo`
# interprets backslash escapes and a literal \c ends its output, which would
# hide a secret after "\c" in the tool output.
#
# Pattern agreement: audit-log.sh redacts the same credential families from
# the tool INPUT side before logging. When a pattern here changes, update
# the matching gsub() in audit-log.sh's redact() filter (and vice versa);
# tests/bash/audit_log.bats carries a cross-hook agreement test.
#
# VALUE-BASED DETECTION
#   The seven shape families miss secrets with no recognizable prefix — e.g.
#   a UUID-shaped data-source API key. So the hook also compares the scanned
#   text against the ACTUAL values of the credential-named environment
#   variables it inherits:
#     - Names are enumerated with `compgen -e` inside this process; a name is
#       credential-named when, case-insensitively, one of its underscore-
#       delimited segments is in SECRET_NAME_VOCAB (below), and it is not in
#       SECRET_NAME_ALLOWLIST.
#     - Each value is read with ${!name}. Values shorter than 8 characters,
#       absolute paths, URLs without userinfo, and pure boolean or numeric
#       words are skipped (too common to be meaningful, or not secret).
#     - The comparison is a quoted bash pattern ([[ text == *"$value"* ]]),
#       which is a LITERAL substring test: the value is never interpolated
#       into a regex, never passed on a command line (no process-list
#       exposure), and never written anywhere.
#     - Both the raw value and its JSON-string-escaped form are checked:
#       after `tostring`, an object response escapes \ " newline CR and tab.
#     - COMPARISON LENGTH CAP: only the first 512 characters of a value are
#       compared (SV_CMP_MAX). bash's `*"$v"*` match costs roughly (text
#       length x value length) on repetitive input: about 1.5-2 s for 20
#       values of 3,000-5,000 characters against a 10 KB run of one
#       character. The cap bounds that cost, and it lets a value longer than
#       the 10,000-character window match by its prefix. A 512-character
#       prefix of a secret appearing in the output is itself a leak, so the
#       warning stays truthful.
#     - A match adds "value of <NAME> appears in this tool output". Only the
#       NAME of a MATCHING variable is ever printed — never a value, never
#       the name of a non-matching variable.
#   Limits: a value under 8 characters, a transformed or encoded value
#   (base64, URL-encoding, split across lines, other JSON escapes such as
#   \uXXXX), a value (or its first 512 characters) past the
#   10,000-character window, a partial occurrence shorter than the compared
#   length, and a secret held in a variable whose name is not
#   credential-named are all missed. Advisory only, like the shape families.
#   Shared vocabulary: the name list is carried in one variable after a
#   `SECRET-NAME-VOCAB v1` marker line that is kept byte-identical across
#   output-scanner.sh, audit-log.sh and scripts/run_with_capture.sh.
#   bash-safety.sh does not carry this vocabulary: its environment-disclosure
#   guard (§9) uses its own narrower rule (the last `_`-segment of an
#   uppercase name).
#
# TEST FIXTURES: for an Edit, Write or MultiEdit whose file_path is under a
#   tests/ folder, the key-shape families are skipped. Claude Code's result
#   for those tools carries the whole edited file, and DAAF's test suites
#   hold credential-shaped fixtures on purpose, so every edit of such a file
#   would otherwise warn. The value-based check still runs: a live credential
#   value written into a test file is a real leak.
#
# OUTPUT: when anything matches, the hook prints one JSON object,
#   {"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":…}},
#   whose additionalContext lists the matched families and variable NAMES and
#   tells the model to tell the user and stop (CLAUDE.md § Boundaries &
#   Safety > Credential & Secret Protection), or, when a key-shape match is
#   plainly a placeholder or a test fixture by its own text, to say so and
#   continue: shipped sample keys and the test suites match the shape
#   families, and a hard stop on them would halt ordinary work. A "value of
#   NAME" match is a live environment value, so the exception never applies
#   to it, and a doubtful match counts as real. Claude Code adds additionalContext
#   to the model's context next to the tool result, whereas it writes a
#   PostToolUse hook's plain stdout only to its debug log (verified against
#   the Claude Code hooks reference on 2026-11-02). Nothing is printed when
#   nothing matches. If jq cannot build the JSON, the same text goes to
#   stdout as plain text, which reaches only the debug log.
#
# Exit codes:
#   0 = always (an advisory hook never blocks, and exit 0 is the exit code
#       Claude Code expects with JSON output)
#
# Hook event: PostToolUse (matcher: "")
# Registered in: .claude/settings.json

# -u: catch unset-variable typos. Deliberately omit -e (an advisory observer
# must never abort into a non-zero exit) and pipefail (the `printf | grep -q`
# probes below would turn an early grep exit into a SIGPIPE status and read
# as "no match" — a silent missed detection).
set -u
# +x: an xtrace inherited from the caller (e.g. SHELLOPTS=xtrace in the
# environment) would echo every `sv_val=` assignment below — a credential
# value — to stderr. Switch it off before any value is read.
set +x

# SECRET-NAME-VOCAB v1 — keep identical in: output-scanner.sh, audit-log.sh, run_with_capture.sh
SECRET_NAME_VOCAB="KEY KEYS APIKEY TOKEN TOKENS SECRET SECRETS PASS PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDENTIALS CREDS AUTH COOKIE COOKIES SESSION DSN PAT"
SECRET_NAME_ALLOWLIST="SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS XDG_SESSION_DESKTOP CLAUDE_CODE_SESSION_ID"
# Whole-name ERE built from the vocabulary; matched against the UPPERCASED
# name, which makes the test case-insensitive without `nocasematch` (that
# option would also make the value comparison below case-insensitive).
SECRET_NAME_RE="^([A-Za-z0-9]+_)*(${SECRET_NAME_VOCAB// /|})(_[A-Za-z0-9]+)*\$"
# Comparison length cap for the value-based check (see COMPARISON LENGTH CAP).
SV_CMP_MAX=512

INPUT=$(cat)

# Extract tool response content as text (may be large, limit to first 10KB).
# `tostring` is the identity on strings and JSON-encodes objects/arrays/
# scalars, so the slice below always operates on a string.
RESPONSE=$(printf '%s' "$INPUT" | jq -r '.tool_response // "" | tostring | .[0:10000]' 2>/dev/null) || RESPONSE=""

if [[ -z "$RESPONSE" ]]; then
    exit 0
fi

WARNINGS=""

# Test-file edits skip the key-shape families (see TEST FIXTURES in the
# header): an Edit or Write result carries the whole file, and DAAF's test
# suites hold credential-shaped fixtures on purpose. The value-based check
# below still runs for them.
SHAPE_SCAN=1
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null) || TOOL_NAME=""
EDIT_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null) || EDIT_PATH=""
case "$TOOL_NAME" in
    Edit|Write|MultiEdit)
        case "$EDIT_PATH" in
            tests/*|*/tests/*) SHAPE_SCAN=0 ;;
        esac
        ;;
esac

if [[ "$SHAPE_SCAN" -eq 1 ]]; then

# AWS Access Key ID (always starts with AKIA, 20 chars)
if printf '%s\n' "$RESPONSE" | grep -qE 'AKIA[0-9A-Z]{16}'; then
    WARNINGS="${WARNINGS}  - AWS Access Key ID detected (AKIA...)\n"
fi

# AWS Secret Access Key pattern (40 char base64-ish after known prefixes)
if printf '%s\n' "$RESPONSE" | grep -qE '(aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*[A-Za-z0-9/+=]{40}'; then
    WARNINGS="${WARNINGS}  - AWS Secret Access Key detected\n"
fi

# OpenAI / Anthropic / generic sk- keys
if printf '%s\n' "$RESPONSE" | grep -qE 'sk-[A-Za-z0-9_-]{20,}'; then
    WARNINGS="${WARNINGS}  - API key detected (sk-...)\n"
fi

# Stripe live keys
if printf '%s\n' "$RESPONSE" | grep -qE '(sk_live_|rk_live_|pk_live_)[A-Za-z0-9]{20,}'; then
    WARNINGS="${WARNINGS}  - Stripe live key detected\n"
fi

# GitHub tokens (PAT, OAuth, App)
if printf '%s\n' "$RESPONSE" | grep -qE '(ghp_|gho_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{20,}'; then
    WARNINGS="${WARNINGS}  - GitHub token detected\n"
fi

# Private key headers (-- stops grep from interpreting leading dashes as options)
if printf '%s\n' "$RESPONSE" | grep -qE -- '-----BEGIN[[:space:]]+(RSA|DSA|EC|OPENSSH|PGP)?[[:space:]]*PRIVATE KEY-----'; then
    WARNINGS="${WARNINGS}  - Private key block detected\n"
fi

# Generic Bearer tokens (long ones are suspicious)
if printf '%s\n' "$RESPONSE" | grep -qE 'Bearer\s+[A-Za-z0-9_\-\.]{50,}'; then
    WARNINGS="${WARNINGS}  - Long Bearer token detected\n"
fi

fi  # SHAPE_SCAN

# Value-based detection (see VALUE-BASED DETECTION in the header). Nothing in
# this block writes to stdout except the WARNINGS entry for a matching NAME.
mapfile -t ENV_NAMES < <(compgen -e)
for sv_name in "${ENV_NAMES[@]}"; do
    [[ "${sv_name^^}" =~ $SECRET_NAME_RE ]] || continue
    [[ " ${SECRET_NAME_ALLOWLIST} " == *" ${sv_name} "* ]] && continue
    sv_val="${!sv_name-}"
    # Skip: short values, absolute paths, URLs whose authority has no
    # userinfo ('@'), and pure boolean/numeric words.
    [ "${#sv_val}" -ge 8 ] || continue
    [[ "$sv_val" == /* ]] && continue
    [[ "$sv_val" =~ ^[A-Za-z][A-Za-z0-9+.-]*://[^/?#@]*([/?#]|$) ]] && continue
    [[ "${sv_val,,}" =~ ^(true|false|yes|no|on|off|enabled|disabled)$ ]] && continue
    [[ "$sv_val" =~ ^[+-]?[0-9]+([.][0-9]+)?$ ]] && continue
    # Compare at most the first SV_CMP_MAX characters (bounds the match cost;
    # the filters above still see the whole value).
    sv_val="${sv_val:0:SV_CMP_MAX}"
    # JSON-string-escaped form (backslash first, so the escapes added after
    # it are not doubled).
    sv_esc="${sv_val//\\/\\\\}"
    sv_esc="${sv_esc//\"/\\\"}"
    sv_esc="${sv_esc//$'\n'/\\n}"
    sv_esc="${sv_esc//$'\r'/\\r}"
    sv_esc="${sv_esc//$'\t'/\\t}"
    # Quoted right-hand side = literal substring test, not a regex or glob.
    if [[ "$RESPONSE" == *"$sv_val"* ]] || [[ "$RESPONSE" == *"$sv_esc"* ]]; then
        WARNINGS="${WARNINGS}  - value of ${sv_name} appears in this tool output\n"
    fi
done
unset sv_val sv_esc

# Hand any warning to the model as PostToolUse additionalContext (see OUTPUT
# in the header). WARNINGS holds `\n` escapes and only family labels and
# variable NAMES, so expanding it with %b is safe; jq escapes the text into
# a single-line JSON string, the only thing printed on stdout.
if [[ -n "$WARNINGS" ]]; then
    WARN_TEXT="WARNING: Potential secrets detected in tool output:
$(printf '%b' "$WARNINGS")
Do NOT display, log, or commit these values. Tell the user that a credential appeared in this tool output, then stop and wait for their instructions (CLAUDE.md § Boundaries & Safety > Credential & Secret Protection). The one exception: for a key-shape match (never a \"value of …\" line, which is a live environment value), if the match is plainly a placeholder or a test fixture by its own text (such as sk-your_key_here), say that it is one and continue. If in doubt, treat it as real."
    jq -n -c --arg ctx "$WARN_TEXT" \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}' 2>/dev/null \
        || printf '%s\n' "$WARN_TEXT"
fi

exit 0
