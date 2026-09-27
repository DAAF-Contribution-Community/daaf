#!/usr/bin/env bash
# audit-log.sh — PostToolUse hook that logs every tool invocation
#
# Creates an append-only JSONL audit trail at .claude/logs/audit.jsonl.
# Each entry records: timestamp, session ID, tool name, and a summary of
# what was targeted (command for Bash, file path for Read/Write/Edit, etc.).
#
# Every entry includes agent_type: "orchestrator" for main-thread calls,
# or the subagent's type (e.g., "research-executor") when running inside
# a subagent. agent_id is included only for subagent calls.
#
# This is invaluable for:
#   - Post-session review by instructors or supervisors
#   - Debugging what went wrong if something breaks
#   - Accountability in shared environments
#
# RECORD CONSTRUCTION (single jq pass) [2026-09-24 hook-maintenance pass]
#   The record is built by ONE jq invocation reading the hook JSON from stdin;
#   no logged field makes a round trip through a bash variable. Previously
#   every field went through `$(… | jq -r …)`, and bash command substitution
#   silently drops NUL bytes, so a requested path "/daaf/a\0b" was logged as
#   "/daaf/ab" (plus an "ignored null byte" warning on stderr). jq's own `-c`
#   output escapes the NUL as \u0000, so the logged value now matches the
#   requested one. The only other stdin read is the session id used to locate
#   the model cache; it is accepted only if it is a plain [A-Za-z0-9_-]+ token
#   (anything else, including a NUL or a path separator, skips the lookup and
#   records model "unknown").
#
# REDACTION [2026-09-24 hook-maintenance pass]
#   Before it is written, the `target` field is passed through a redact()
#   filter that replaces secret-shaped substrings with [REDACTED:<family>]
#   placeholders, so a credential typed into a command (or embedded in a URL
#   or path) is not persisted into .claude/logs/. The credential families
#   reuse output-scanner.sh's patterns so the two hooks agree on what counts
#   as a secret (AWS access key IDs, AWS secret-key assignments, sk- keys,
#   Stripe live keys, GitHub tokens, PEM private-key blocks, Bearer tokens),
#   and add three log-side rules: any Authorization header/assignment value,
#   Bearer tokens of 16+ chars (the scanner's advisory floor is 50), and a
#   literal value assigned to a credential-named key (…API_KEY=, …TOKEN=,
#   …SECRET=, …PASSWORD=; a $VAR reference is not a literal and is kept).
#   When output-scanner.sh's patterns change, update redact() to match;
#   tests/bash/audit_log.bats carries a cross-hook agreement test.
#
# CAP, GUARD AND CUT [revision _c 2026-09-27: every target, try guard, tail
# margin]
#   Every target (before _c: Bash commands only) is capped at 4,000
#   characters before the pattern rules. The cap does NOT bound time: jq's
#   regex engine (Oniguruma) gives up on heavy backtracking with "Regex
#   failure: retry-limit-in-match over" (jq exit 5) in tens of milliseconds,
#   far inside the 5 s hook timeout. It bounds FAILURE. Measured 2026-09-27
#   (jq 1.7, the rules below): "token" repeated passes at 5,750 characters
#   and errors from 6,000; the other rule-9 keywords error from 6,500 to
#   7,500. Do not raise the cap past about 5,000. Before _c a long
#   keyword-dense Grep pattern, Task description or URL was uncapped, the
#   whole pass failed, and the record fell back to all-"unknown" (review W1).
#   Two guards sit on the pattern step:
#     - try/catch: if the pattern rules still error on some input under the
#       cap, the target becomes [REDACTED:pattern-step-failed] and every
#       other field is kept.
#     - tail margin: when the input exceeded the cap, the last 128
#       characters of the pattern-redacted window are dropped. The cap can
#       cut a secret in two, and the cut-off prefix may be too short for its
#       rule (an sk- key needs 20 characters after the prefix); without the
#       margin that prefix would be logged, directly for non-Bash targets
#       and, for Bash, when earlier redactions shrink the text into the
#       first 200 characters (review NIT 1). 128 exceeds every rule's
#       minimum secret length (at most 40) plus its key name; a key followed
#       by a very long run of whitespace is the contrived exception.
#   Bash commands are then cut to 200 characters; other targets are logged
#   up to the cap less the margin (3,872 characters). The 200-char cut comes
#   AFTER the pattern rules, so a secret straddling that boundary is
#   redacted rather than left as a partial, unrecognizable prefix. (The
#   value-based step runs earlier, on a 65,536-char window; see below.)
#
# VALUE-BASED REDACTION [2026-09-26 bundle revision _a, SafetyHookHardening
# session; revision _b 2026-09-27: command order, fallback, xtrace guard;
# revision _c 2026-09-27: order for every target, pair-count check,
# `builtin printf`]
#   Pattern rules cannot recognize a secret with no characteristic shape (a
#   UUID-shaped data-source API key passed as a positional argument or
#   embedded in a URL). So, as step 0 of redact(), every literal occurrence
#   of the VALUE of a credential-named environment variable is replaced with
#   [REDACTED:env:<NAME>]. The name test and value filters are identical to
#   output-scanner.sh's VALUE-BASED DETECTION: names from `compgen -e` whose
#   uppercased form has a SECRET_NAME_VOCAB segment, minus
#   SECRET_NAME_ALLOWLIST; values under 8 characters, absolute paths, URLs
#   without userinfo, and pure boolean/numeric words are skipped.
#   How values reach jq: bash writes NUL-separated NAME\0VALUE\0 pairs with
#   the `printf` builtin into a process substitution, and jq reads that pipe
#   with --rawfile. No value appears on any command line (the process list
#   shows only "--rawfile envpairs /dev/fd/N"), and nothing is written to
#   disk (a pipe, not a here-string, which bash may spool to a temp file).
#   [revision _c] The call is spelled `builtin printf`, so a shell function
#   named printf exported into the hook's environment does not receive the
#   values (review NIT 6). This is hardening, not a boundary: an exported
#   function named `builtin` still intercepts it (observed 2026-09-27), and
#   whoever controls the hook's environment can also run code through
#   BASH_ENV.
#   PAIR-COUNT CHECK [revision _c]: jq also receives the NUMBER of pairs
#   (--argjson npairs; a count, never a value) and raises an error unless
#   the stream holds exactly that many NUL-terminated pairs. A truncated or
#   empty stream therefore cannot silently redact only a prefix of a value,
#   or nothing; the error sends the hook to the FALLBACK pass, which
#   withholds the target (review NIT 2).
#   jq replaces each value with split(value) | join(marker) — a literal
#   split, never a regex built from the value — longest value first, so a
#   value that contains another is redacted under its own name. Runs before
#   the pattern rules and before the 200-char cut.
#   ORDER [revision _b 2026-09-27 for Bash commands; revision _c for every
#   target]: the value step runs on the first 65,536 characters of the
#   target, BEFORE the 4,000-character pattern cap. Under _a it ran after
#   that cap, so a value longer than about 3,800 characters that started
#   inside the first 200 could never match whole and its opening characters
#   were logged. split/join is a literal search (jq uses memmem), so this
#   wider window does not re-open the regex failure the 4,000 cap bounds.
#   FALLBACK [revision _b]: if the full pass fails for any reason other than
#   malformed input (e.g. the value pipe cannot be opened, or the pair-count
#   check fails), a second pass writes the record without the value step.
#   Its target is withheld as [REDACTED:env-step-unavailable] whenever a
#   credential-named value was present to redact, so an unredacted target is
#   never written; with no such value the pattern-redacted target is written
#   as usual. Every other field (session_id, tool, agent_type, …) is kept,
#   so consumers that key on session_id (DAAFBench's collector) do not lose
#   the record. Only malformed input still falls through to the
#   all-"unknown" record. [revision _c] Under _b that last sentence was
#   false: a pattern-rule regex error failed both passes (review W1). The
#   try guard under CAP, GUARD AND CUT now keeps the record.
#   NO jq [revision _c]: if jq cannot run at all, a constant all-"unknown"
#   record is written with printf, so the firing is still recorded. Nothing
#   from stdin, the model cache or the environment goes into it (review
#   NIT 5). Audit loss that remains, silent by design: a failed append
#   (unwritable log directory) and the 5 s hook timeout.
#   Limits: values under 8 characters, transformed or encoded values (URL-
#   or base64-encoded, quoted differently, split across arguments), values
#   that begin inside the logged part of the target but end past the 65,536-
#   character window, the tail of a shorter value that overlaps a longer one
#   in the text (the longer one is redacted first), and secrets held in
#   variables whose names are not credential-named are not redacted by this
#   step (the pattern rules may still catch them).
#   Shared vocabulary: the name list is carried in one variable after a
#   `SECRET-NAME-VOCAB v1` marker line that is kept byte-identical across
#   output-scanner.sh, audit-log.sh and scripts/run_with_capture.sh.
#   bash-safety.sh does NOT carry it: its env-disclosure guard was deferred
#   as an accepted gap by user decision on 2026-09-26.
#
# Malformed, empty, or non-object stdin still produces a record with the
# documented "unknown" fallbacks (tool "unknown", session_id "unknown",
# target ""), so the audit trail shows that a hook fired.
#
# Exit codes:
#   0 = always (PostToolUse hooks must never block execution)
#
# Hook event: PostToolUse (matcher: "")
# Registered in: .claude/settings.json

# -u: catch unset variable typos. Deliberately omit -e: this hook must
# never block execution — all error paths exit 0.
set -u
# +x: an xtrace inherited from the caller (e.g. SHELLOPTS=xtrace in the
# environment) would echo every `sv_val=` assignment and the value-feeding
# printf below — credential values — to stderr. Switch it off before any
# value is read.
set +x

# SECRET-NAME-VOCAB v1 — keep identical in: output-scanner.sh, audit-log.sh, run_with_capture.sh
SECRET_NAME_VOCAB="KEY KEYS APIKEY TOKEN TOKENS SECRET SECRETS PASS PASSWORD PASSWD PASSPHRASE CREDENTIAL CREDENTIALS CREDS AUTH COOKIE COOKIES SESSION DSN PAT"
SECRET_NAME_ALLOWLIST="SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS XDG_SESSION_DESKTOP"
# Whole-name ERE built from the vocabulary; matched against the UPPERCASED
# name (case-insensitive without `nocasematch`).
SECRET_NAME_RE="^([A-Za-z0-9]+_)*(${SECRET_NAME_VOCAB// /|})(_[A-Za-z0-9]+)*\$"

INPUT=$(cat)

TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# DAAF version (git commit hash)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DAAF_VERSION=$(git -C "$PROJECT_DIR" describe --always --dirty 2>/dev/null || echo "unknown")

# Model (from context-reporter cache, populated after first assistant response).
# The session id is used ONLY to build the cache path, never logged from here:
# jq emits it only when it is a plain token, so no NUL byte or path separator
# can reach bash or the path.
CACHE_SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty | tostring | select(test("^[A-Za-z0-9_-]+$"))' 2>/dev/null) || CACHE_SID=""
MODEL="unknown"
if [[ -n "$CACHE_SID" ]]; then
    MODEL_CACHE="/tmp/claude-model-${CACHE_SID}"
    MODEL=$(cat "$MODEL_CACHE" 2>/dev/null || echo "unknown")
fi

# Credential-named environment variables whose values are worth redacting
# (see VALUE-BASED REDACTION in the header). Only NAMES are collected here;
# the values are read again inside the process substitution that feeds jq.
CRED_NAMES=()
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
    CRED_NAMES+=("$sv_name")
done
unset sv_val

# The record-building jq program. A quoted heredoc keeps the regexes free of
# shell quoting; inside jq string literals every regex backslash is doubled.
read -r -d '' JQ_RECORD <<'JQ' || true
# env_list: the NAME\0VALUE\0 pairs from --rawfile envpairs as
# [{name, value}], longest value first.
# Pair-count check [revision _c]: the stream must hold exactly $npairs
# NUL-terminated pairs (2 x npairs fields plus the empty field after the
# final NUL), or be empty when npairs is 0. Anything else is an error, which
# sends the caller to the FALLBACK pass (see PAIR-COUNT CHECK in the header).
def env_list:
  ($envpairs | split("\u0000")) as $p
  | if ($npairs == 0 and $envpairs == "")
       or (($p | length) == 2 * $npairs + 1 and $p[-1] == "")
    then . else error("envpairs incomplete") end
  | [range(0; ($p | length) - 1; 2) | {name: $p[.], value: $p[. + 1]}]
  | map(select((.value | length) >= 8))
  | sort_by(-(.value | length));

# redact_env: replace each literal occurrence of a value with
# [REDACTED:env:<NAME>]. split/1 on a string separator is a LITERAL split,
# so no regex is ever built from a value.
def redact_env:
  reduce env_list[] as $e (.; split($e.value) | join("[REDACTED:env:" + $e.name + "]"));

# redact_patterns: replace secret-shaped substrings with [REDACTED:<family>].
# Rules 1-6 and 8 mirror output-scanner.sh's credential families (rule 1 and
# rule 8 are supersets of the scanner's patterns); rules 7 and 9 are
# log-side additions.
def redact_patterns:
  # 1. PEM private-key block: BEGIN through END, or to end of string.
  gsub("-----BEGIN[A-Z\\s]*PRIVATE KEY-----[\\s\\S]*?(?:-----END[A-Z\\s]*PRIVATE KEY-----|\\z)"; "[REDACTED:private-key]")
  # 2. AWS secret access key assignment (the key name is kept).
  | gsub("(?<k>(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\\s*[=:]\\s*)[A-Za-z0-9/+=]{40}"; "\(.k)[REDACTED:aws-secret-access-key]")
  # 3. AWS access key ID.
  | gsub("AKIA[0-9A-Z]{16}"; "[REDACTED:aws-access-key-id]")
  # 4. Stripe live keys.
  | gsub("(?:sk_live_|rk_live_|pk_live_)[A-Za-z0-9]{20,}"; "[REDACTED:stripe-live-key]")
  # 5. Generic sk- API keys (OpenAI / Anthropic / others).
  | gsub("sk-[A-Za-z0-9_-]{20,}"; "[REDACTED:api-key]")
  # 6. GitHub tokens (PAT, OAuth, App, fine-grained).
  | gsub("(?:ghp_|gho_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{20,}"; "[REDACTED:github-token]")
  # 7. Authorization header or assignment value, any length (scheme kept).
  | gsub("(?<k>authorization[\"']?\\s*[:=]\\s*[\"']?)(?<s>(?:bearer|basic|token|digest)\\s+)?[^\\s\"',;]+"; "\(.k)\(.s // "")[REDACTED:authorization]"; "i")
  # 8. Bearer tokens of 16+ chars outside an Authorization header.
  | gsub("(?<k>bearer\\s+)[A-Za-z0-9_\\-.~+/=]{16,}"; "\(.k)[REDACTED:bearer-token]"; "i")
  # 9. Literal value (8+ chars) assigned to a credential-named key. A $VAR
  #    reference does not match: "$" is outside the value character class.
  | gsub("(?<k>\\b[A-Za-z0-9_]*(?:api_?key|secret|token|passw(?:or)?d)[A-Za-z0-9_]*[\"']?\\s*[=:]\\s*[\"']?)[A-Za-z0-9_\\-./+=:@~]{8,}"; "\(.k)[REDACTED:credential-assignment]"; "i");

# Pattern cap and tail margin (see CAP, GUARD AND CUT in the header). Do not
# raise pattern_cap past about 5,000: keyword-dense text makes the rules
# above hit the regex engine's retry limit from 6,000 characters.
def pattern_cap: 4000;
def cap_margin: 128;

# redact_patterns_capped: the pattern rules on at most pattern_cap
# characters; if the input was longer, the last cap_margin characters of the
# result are dropped, so a secret cut in two by the cap never leaves its
# prefix in the log. try/catch keeps the record if the rules still error.
def redact_patterns_capped:
  try (if length > pattern_cap
       then .[0:pattern_cap] | redact_patterns | .[0:([length - cap_margin, 0] | max)]
       else redact_patterns end)
  catch "[REDACTED:pattern-step-failed]";

# redact: the value-based step (rule 0) on a 65,536-char window, then the
# capped pattern rules. Every target type goes through it [revision _c].
def redact: .[0:65536] | redact_env | redact_patterns_capped;

# Stringify a field; a missing field becomes "".
def str: if . == null then "" else tostring end;

# Exactly one JSON object is required; anything else fails the whole pass so
# the caller writes the "unknown" fallback record instead of a partial one.
# Every target: value step on a 65,536-char window FIRST, then the 4,000-char
# pattern cap, the guarded pattern rules and the tail margin (see ORDER and
# CAP, GUARD AND CUT in the header); Bash commands are then cut to 200 chars.
# $fallback == "withhold" (second pass only, see FALLBACK in the header): the
# value step was unavailable while a credential-named value existed, so the
# target is replaced by a marker instead of being written unredacted.
if length == 1 and (.[0] | type == "object") then .[0] else error("malformed hook input") end
| (.tool_name // "unknown" | tostring) as $tool
| (.tool_input | if type == "object" then . else {} end) as $in
| (if $tool == "Bash" then ($in.command | str | redact | .[0:200])
   elif $tool == "Read" or $tool == "Write" or $tool == "Edit" then ($in.file_path | str | redact)
   elif $tool == "Glob" or $tool == "Grep" then ($in.pattern | str | redact)
   elif $tool == "Task" or $tool == "Agent" then ($in.description | str | redact)
   elif $tool == "WebFetch" then ($in.url | str | redact)
   else "" end
   | if $fallback == "withhold" and . != "" then "[REDACTED:env-step-unavailable]" else . end) as $target
| (.agent_type | str | if . == "" then "orchestrator" else . end) as $atype
| (.agent_id | str) as $aid
| {timestamp: $ts, session_id: (.session_id // "unknown" | tostring), tool: $tool,
   target: $target, daaf_version: $ver, model: $model, agent_type: $atype}
  + (if $aid != "" then {agent_id: $aid} else {} end)
JQ

# Build the record in a single pass over stdin (-s slurps so the one-object
# check above can count values). The env values travel NUL-separated through
# a process-substitution pipe read with --rawfile (`builtin printf`, so no
# value is on any argv and an exported printf function is bypassed; see
# VALUE-BASED REDACTION in the header). npairs is the pair COUNT for the
# pair-count check, never a value.
RECORD=$(printf '%s' "$INPUT" | jq -c -s \
    --arg ts "$TIMESTAMP" \
    --arg ver "$DAAF_VERSION" \
    --arg model "$MODEL" \
    --arg fallback "" \
    --argjson npairs "${#CRED_NAMES[@]}" \
    --rawfile envpairs <(for sv_name in "${CRED_NAMES[@]}"; do builtin printf '%s\0%s\0' "$sv_name" "${!sv_name-}"; done) \
    "$JQ_RECORD" 2>/dev/null) || RECORD=""
# Second pass without the value step (see FALLBACK in the header): no value
# is passed at all (envpairs is empty), and the target is withheld whenever a
# credential-named value existed. Malformed input fails this pass too.
if [[ -z "$RECORD" ]]; then
    if (( ${#CRED_NAMES[@]} > 0 )); then FB_MODE="withhold"; else FB_MODE="patterns"; fi
    RECORD=$(printf '%s' "$INPUT" | jq -c -s \
        --arg ts "$TIMESTAMP" \
        --arg ver "$DAAF_VERSION" \
        --arg model "$MODEL" \
        --arg fallback "$FB_MODE" \
        --argjson npairs 0 \
        --arg envpairs "" \
        "$JQ_RECORD" 2>/dev/null) || RECORD=""
fi
# Last resort (malformed, empty, or non-object stdin): the documented
# all-"unknown" record.
if [[ -z "$RECORD" ]]; then
    RECORD=$(jq -n -c \
        --arg ts "$TIMESTAMP" \
        --arg ver "$DAAF_VERSION" \
        --arg model "$MODEL" \
        '{timestamp: $ts, session_id: "unknown", tool: "unknown", target: "", daaf_version: $ver, model: $model, agent_type: "orchestrator"}' 2>/dev/null) || RECORD=""
fi
# No jq at all [revision _c, review NIT 5]: every jq call above failed, so
# write the same all-"unknown" record with printf. It carries nothing from
# stdin, the model cache or the environment; the timestamp and git version
# are reduced to JSON-safe characters so the line stays valid JSON.
if [[ -z "$RECORD" ]]; then
    RECORD=$(builtin printf '{"timestamp":"%s","session_id":"unknown","tool":"unknown","target":"","daaf_version":"%s","model":"unknown","agent_type":"orchestrator"}' \
        "${TIMESTAMP//[^0-9TZ:-]/}" "${DAAF_VERSION//[^A-Za-z0-9._+-]/_}")
fi

# Determine log directory relative to project root
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    LOG_DIR="$CLAUDE_PROJECT_DIR/.claude/logs"
else
    # Fallback: use script's own location to find project root
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LOG_DIR="$(dirname "$SCRIPT_DIR")/logs"
fi

mkdir -p "$LOG_DIR" 2>/dev/null

# Append the JSON line to the audit log. stderr is redirected BEFORE the
# append so a failed open (unwritable log dir) is silent too — audit loss is
# accepted, a block never is.
LOG_FILE="$LOG_DIR/audit.jsonl"
if [[ -n "$RECORD" ]]; then
    printf '%s\n' "$RECORD" 2>/dev/null >> "$LOG_FILE"
fi

exit 0
