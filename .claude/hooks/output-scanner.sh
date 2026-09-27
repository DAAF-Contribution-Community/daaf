#!/usr/bin/env bash
# output-scanner.sh — PostToolUse hook that scans tool output for leaked secrets
#
# Checks tool_response content for patterns matching common credential formats:
#   - AWS Access Key IDs (AKIA...)
#   - Generic API keys (sk-..., sk_live_..., rk_live_...)
#   - GitHub Personal Access Tokens (ghp_..., gho_..., ghs_...)
#   - Private key headers (-----BEGIN...PRIVATE KEY-----)
#   - Generic high-entropy tokens (Bearer <long-token>)
# and, since the 2026-09-26 bundle revision _a, for the literal VALUE of any
# credential-named environment variable (see VALUE-BASED DETECTION below).
#
# Response shapes: tool_response may be a STRING, an ARRAY, or an OBJECT
# (Claude Code sends object-shaped responses for several tools, e.g.
# {"stdout": ..., "stderr": ...}). Every shape is stringified with jq
# `tostring` before the first 10,000 characters are scanned, so non-string
# responses are scanned as their JSON text. [2026-09-24 hook-maintenance
# pass] Previously the extractor sliced `.tool_response` directly; an object
# made jq fail ("Cannot index object with object"), the response resolved
# to empty, and nothing was scanned.
#
# Probe input [revision _c 2026-09-27, review NIT 6]: the shape probes feed
# grep with `printf '%s\n'`, not `echo`. With an inherited xpg_echo
# (BASHOPTS=xpg_echo in the environment), `echo` interprets backslash
# escapes and a literal \c ends its output, so a secret after "\c" in the
# tool output was never scanned.
#
# Pattern agreement: audit-log.sh redacts the same credential families from
# the tool INPUT side before logging. When a pattern here changes, update
# the matching gsub() in audit-log.sh's redact() filter (and vice versa);
# tests/bash/audit_log.bats carries a cross-hook agreement test.
#
# VALUE-BASED DETECTION [2026-09-26 bundle revision _a, SafetyHookHardening
# session; revision _b 2026-09-27: comparison length cap, xtrace guard]
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
#     - COMPARISON LENGTH CAP [revision _b]: only the first 512 characters
#       of a value are compared (SV_CMP_MAX). bash's `*"$v"*` match costs
#       roughly (text length x value length) on repetitive input: the _a
#       review measured 1.5-2 s for 20 values of 3,000-5,000 characters
#       against a 10 KB run of one character. The cap bounds that cost, and
#       a value longer than the 10,000-character window can now match at all
#       (by its prefix). A 512-character prefix of a secret appearing in
#       the output is itself a leak, so the warning stays truthful.
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
#   bash-safety.sh does NOT carry it: its env-disclosure guard was deferred
#   as an accepted gap by user decision on 2026-09-26.
#
# If a pattern is detected, injects a warning via stdout so the model
# is aware and can avoid propagating the secret.
#
# Exit codes:
#   0 = always (PostToolUse hooks must never block execution)
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
SECRET_NAME_ALLOWLIST="SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS XDG_SESSION_DESKTOP"
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

# If any warnings were generated, output them for the model to see
if [[ -n "$WARNINGS" ]]; then
    echo "WARNING: Potential secrets detected in tool output:"
    echo -e "$WARNINGS"
    echo "Do NOT display, log, or commit these values. Treat them as sensitive."
fi

exit 0
