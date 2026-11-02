#!/usr/bin/env bash
# audit-log.sh — PostToolUse hook that logs every tool invocation
#
# Appends one JSON line per tool call to .claude/logs/audit.jsonl (under
# $CLAUDE_PROJECT_DIR, else the .claude/ folder that holds this hook), for
# post-session review by instructors or supervisors, debugging, and
# accountability in shared environments.
#
# Outline: RECORD, REDACTION, ORDER AND CAPS, VALUE STEP, FAILURE PATHS,
# LIMITS, SHARED VOCABULARY.
#
# RECORD
#   Fields: timestamp (UTC ISO-8601 with a Z suffix), session_id, tool,
#   target, daaf_version (`git describe --always --dirty`), model (read from
#   the context-reporter cache /tmp/claude-model-<session_id>; "unknown" when
#   absent), agent_type ("orchestrator" for main-thread calls, else the
#   subagent's type, e.g. "research-executor"), and agent_id (subagent calls
#   only).
#   target by tool: Bash, the command (cut to 200 characters); Read, Write,
#   Edit, file_path; Glob, Grep, pattern; Task, Agent, description; WebFetch,
#   url; any other tool, "".
#   Consumers: benchmarks/harness/collector.py keys on session_id; the
#   scripts/lit_corpus.py ingest check reads agent_id, agent_type, tool and
#   target to confirm the citation adjudicator read only its bundle.
#   One jq invocation builds the record from stdin, so no logged field makes
#   a round trip through a bash variable: command substitution drops NUL
#   bytes, while jq -c escapes a NUL as \u0000, so a logged path matches the
#   requested one. The only other stdin read is the session id used for the
#   model cache path, accepted only as a plain [A-Za-z0-9_-]+ token (anything
#   else, including a NUL or a path separator, skips the lookup and records
#   model "unknown").
#
# REDACTION
#   Before it is written, target passes through redact(), which replaces
#   secret-shaped substrings with [REDACTED:<family>] placeholders, so a
#   credential typed into a command (or embedded in a URL or path) is not
#   persisted into .claude/logs/. Each rule's details are in its comment in
#   JQ_RECORD below.
#   - Rule 0, the value step: the VALUE of any credential-named environment
#     variable -> [REDACTED:env:<NAME>] (see VALUE STEP).
#   - Rules 1-6 and 8 mirror output-scanner.sh's credential families, so the
#     two hooks agree on what counts as a secret: PEM private-key blocks, AWS
#     secret-key assignments, AWS access key IDs, Stripe live keys, sk- keys,
#     GitHub tokens, and Bearer tokens (from 16 characters here; the
#     scanner's advisory floor is 50). When output-scanner.sh's patterns
#     change, update redact() to match; tests/bash/audit_log.bats carries a
#     cross-hook agreement test.
#   - Rule 7: any Authorization header or assignment value.
#   - Rule 9: a literal value (8+ characters) assigned to a credential-named
#     key (…API_KEY=, …TOKEN=, …SECRET=, …PASSWORD=, a hyphenated api-key
#     header name, a segment-bounded PASS / PASSPHRASE key name); a $VAR
#     reference is not a literal and is kept. A purely numeric value on a
#     token-named key is kept ("tokens: <digits>" is a counter, not a
#     credential); a numeric value on any other key is redacted. When the
#     value opens with a quote and its first 8+ characters match, it runs on
#     to the closing quote, so a quoted value with a space is not cut after
#     its first word.
#   - Rule 10: the value after a credential-named command-line flag
#     (--password VALUE, also short values and quoted values with a space)
#     -> [REDACTED:credential-flag].
#   - Rule 11: the password in URL userinfo (scheme://user:PASSWORD@host, up
#     to the last "@" before the host) -> [REDACTED:url-userinfo].
#   - Rule 12: the part after the first colon of curl's --user / -u
#     NAME:PASSWORD value, inside a curl command only ->
#     [REDACTED:credential-flag].
#   Rules 10-12 accept values from one character and do not match a value
#   that STARTS with a [REDACTED: marker. Rules 7 and 9-12 (and rule 8 below
#   50 characters) are log-side additions that output-scanner.sh does not
#   flag: they are input-side shapes, and on the output side (docs, fixtures,
#   example connection strings) they would add warning noise to an advisory
#   hook; the cross-hook test requires only scanner -> audit-log.
#
# ORDER AND CAPS (every target type, in this order)
#   1. Value step on the first 65,536 characters (see VALUE STEP).
#      split/join is a literal search (jq uses memmem), so this wider window
#      does not reach the regex failure the next cap bounds, and running it
#      first lets a value longer than about 3,800 characters that starts in
#      the first 200 be redacted whole.
#   2. Pattern rules on at most 4,000 characters. The cap does NOT bound
#      time: jq's regex engine (Oniguruma) gives up on heavy backtracking
#      with "Regex failure: retry-limit-in-match over" (jq exit 5) in tens of
#      milliseconds, far inside the 5 s hook timeout. It bounds FAILURE:
#      "token" repeated passes at 5,750 characters and errors from 6,000, as
#      does the "pass" segment ("pass_" or "_pass" repeated); the other
#      rule-9 keywords error from 6,500 to 7,500; dense flag, header, "://",
#      counter, quoted-value, "curl", "-u a:" and raw-"@" inputs did not
#      error up to 8,000 (observed 2026-09-27 to 2026-10-02, jq 1.7). Do not
#      raise the cap past about 5,000: an uncapped keyword-dense target (a
#      long Grep pattern, Task description or URL) fails the whole pass.
#      A try/catch guards the step: if the rules still error on some input
#      under the cap, the target becomes [REDACTED:pattern-step-failed] and
#      every other field is kept.
#   3. Tail margin: when the input exceeded the cap, the last 128 characters
#      of the pattern-redacted window are dropped. The cap can cut a secret
#      in two, and the cut-off prefix may be too short for its rule (an sk-
#      key needs 20 characters after the prefix); without the margin that
#      prefix would be logged, directly for non-Bash targets and, for Bash,
#      when earlier redactions shrink the text into the first 200
#      characters. 128 exceeds every rule's minimum secret length (at most
#      40) plus its key name. Two contrived exceptions: a key followed by a
#      very long run of whitespace, and a rule-11 userinfo password (the rule
#      needs the "@" AFTER the password, so a password cut by the cap never
#      matches; one that starts more than 128 characters before the cap and
#      runs past it is logged up to the margin).
#   4. Bash commands are cut to 200 characters; other targets are logged up
#      to the cap less the margin (3,872 characters). The 200-character cut
#      comes AFTER the pattern rules, so a secret straddling that boundary is
#      redacted rather than left as a partial, unrecognizable prefix.
#
# VALUE STEP (rule 0 of redact())
#   Pattern rules cannot recognize a secret with no characteristic shape (a
#   UUID-shaped data-source API key passed as a positional argument or
#   embedded in a URL), so every literal occurrence of the VALUE of a
#   credential-named environment variable is replaced with
#   [REDACTED:env:<NAME>]. The name test and value filters are identical to
#   output-scanner.sh's VALUE-BASED DETECTION: names from `compgen -e` whose
#   uppercased form has a SECRET_NAME_VOCAB segment, minus
#   SECRET_NAME_ALLOWLIST; values under 8 characters, absolute paths, URLs
#   without userinfo, and pure boolean/numeric words are skipped.
#   How values reach jq: bash writes NUL-separated NAME\0VALUE\0 pairs with
#   `builtin printf` into a process substitution, and jq reads that pipe
#   with --rawfile. No value appears on any command line (the process list
#   shows only "--rawfile envpairs /dev/fd/N"), and nothing is written to
#   disk (a pipe, not a here-string, which bash may spool to a temp file).
#   Spelling it `builtin printf` keeps the values from a shell function
#   named printf exported into the hook's environment. This is hardening,
#   not a boundary: an exported function named `builtin` still intercepts
#   it (observed 2026-11-02, bash 5.2.21), and whoever controls the hook's
#   environment can also run code through BASH_ENV.
#   Pair-count check: jq also receives the NUMBER of pairs (--argjson
#   npairs; a count, never a value) and raises an error unless the stream
#   holds exactly that many NUL-terminated pairs, so a truncated or empty
#   stream cannot silently redact only a prefix of a value, or nothing; the
#   error sends the hook to the fallback pass (see FAILURE PATHS).
#   jq replaces each value with split(value) | join(marker), a literal
#   split, never a regex built from the value, longest value first, so a
#   value that contains another is redacted under its own name.
#
# FAILURE PATHS (audit loss is accepted, a block never is)
#   - Pattern rules error under the cap: the try/catch in ORDER AND CAPS
#     step 2 keeps the record with a [REDACTED:pattern-step-failed] target.
#   - The full pass fails for any reason other than malformed input (the
#     value pipe cannot be opened, or the pair-count check fails): a second
#     pass writes the record without the value step. Its target is withheld
#     as [REDACTED:env-step-unavailable] whenever a credential-named value
#     was present to redact, so an unredacted target is never written; with
#     no such value the pattern-redacted target is written as usual. Every
#     other field (session_id, tool, agent_type, …) is kept, so consumers
#     that key on session_id do not lose the record.
#   - Malformed, empty, or non-object stdin: a record with the "unknown"
#     fallbacks (tool "unknown", session_id "unknown", target ""), so the
#     audit trail shows that a hook fired.
#   - jq cannot run at all: the same all-"unknown" record, written with
#     printf. Nothing from stdin, the model cache or the environment goes
#     into it.
#   - Silent audit loss, by design: a failed append (unwritable log
#     directory) and the 5 s hook timeout.
#
# LIMITS
#   The value step misses values under 8 characters, transformed or encoded
#   values (URL- or base64-encoded, quoted differently, split across
#   arguments), values that begin inside the logged part of the target but
#   end past the 65,536-character window, the tail of a shorter value that
#   overlaps a longer one in the text (the longer one is redacted first), and
#   secrets held in variables whose names are not credential-named (the
#   pattern rules may still catch them). The pattern rules miss short flags
#   (-p VALUE), user-name-only userinfo, header values under 8 characters,
#   and rule-10 and rule-12 values that start with "$" or "-" (rule 11 has no
#   such exclusion: a userinfo "$VAR" or "-x" password is redacted, accepted
#   over-redaction).
#
# SHARED VOCABULARY
#   The name list is carried in one variable after a `SECRET-NAME-VOCAB v1`
#   marker line that is kept byte-identical across output-scanner.sh,
#   audit-log.sh and scripts/run_with_capture.sh. bash-safety.sh does not
#   carry this vocabulary: its environment-disclosure guard (§9) uses its own
#   narrower rule (the last `_`-segment of an uppercase name).
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
SECRET_NAME_ALLOWLIST="SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS XDG_SESSION_DESKTOP CLAUDE_CODE_SESSION_ID"
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
# (see VALUE STEP in the header). Only NAMES are collected here;
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
# Pair-count check: the stream must hold exactly $npairs NUL-terminated pairs
# (2 x npairs fields plus the empty field after the final NUL), or be empty
# when npairs is 0. Anything else is an error, which sends the caller to the
# fallback pass (see VALUE STEP and FAILURE PATHS in the header).
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
# rule 8 are supersets of the scanner's patterns); rules 7 and 9-12 are
# log-side additions. Rules 10-12 run last and do not match a
# value that STARTS with a [REDACTED: marker, so they do not relabel what an
# earlier rule (or the value step) produced. A marker further inside a
# matched value is replaced together with it: the value stays redacted, under
# the later rule's family.
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
  #    The key may also hold "api-key" with a hyphen (an API-key request
  #    header, case F1a) and a segment-bounded "pass" or "passphrase"
  #    (DB_PASS=, case F1d): no letter or digit directly before or after it,
  #    so bypass, compass and passenger do not match. Case F4: when the key
  #    contains "token" and the value is purely numeric (digits with an
  #    optional decimal part, the value step's numeric skip), the match is
  #    kept unchanged, so a usage counter is not logged as a credential. A
  #    numeric value on any other key (a numeric password) is still redacted.
  #    When an opening quote precedes the value
  #    and a closing quote follows on the same line, the value runs from its
  #    8+-character start to that quote, so "KEY='<8+> <rest>'" is not cut
  #    after the first word. It only extends a match the unquoted branch
  #    would make; a quoted value whose first word is under 8 characters is
  #    still not matched here (rule 10 covers the --flag= form). The atomic
  #    group keeps the search linear when no closing quote follows.
  | gsub("(?<k>\\b[A-Za-z0-9_]*(?:api[_-]?key|secret|token|passw(?:or)?d|(?<![A-Za-z0-9])pass(?:phrase)?(?![A-Za-z0-9]))[A-Za-z0-9_]*[\"']?\\s*[=:]\\s*[\"']?)(?<v>(?<=[\"'])(?>[A-Za-z0-9_\\-./+=:@~]{8,}[^\"'\\n]*)(?=[\"'])|[A-Za-z0-9_\\-./+=:@~]{8,})";
         if (.k | test("token"; "i")) and (.v | test("^[+-]?[0-9]+(?:[.][0-9]+)?$"))
         then .k + .v
         else "\(.k)[REDACTED:credential-assignment]" end; "i")
  # 10. Value after a credential-named command-line flag (case F1b).
  #     At the start of a line or after whitespace: one or two dashes, up to
  #     three words joined by "-" or "_", then a word ending in password,
  #     passwd, passphrase, secret, token or api-key (also api_key, apikey),
  #     or the whole word "pass"; then whitespace or "=". The value (1+
  #     characters) runs to the next whitespace or quote; after an opening
  #     quote it runs to the next quote or newline, so a quoted value with a
  #     space is covered. Not matched: a value starting with "$" (a variable
  #     reference, as in rule 9) or "-" (the next option, or stdin), and a
  #     value that starts with a [REDACTED: marker. A plural or longer flag
  #     (max-tokens, token-file) is not followed by whitespace or "=" right
  #     after the keyword, so it never matches. Short flags (-p) are not
  #     covered: too ambiguous. An 8+-character "=" value (quoted: to the
  #     closing quote) is caught by rule 9 first and keeps the
  #     credential-assignment marker.
  | gsub("(?<k>(?:^|(?<=\\s))--?(?:[A-Za-z0-9]+[-_]){0,3}(?:[A-Za-z0-9]*(?:passw(?:or)?d|passphrase|secret|token|api[-_]?key)|pass)(?:\\s+|=)[\"']?)(?![$-]|\\[REDACTED:)(?:(?<=[\"'])[^\"'\\n]+|(?<![\"'])[^\\s\"']+)"; "\(.k)[REDACTED:credential-flag]"; "i")
  # 11. Password in URL userinfo, scheme://user:PASSWORD@host (case F1c).
  #     The scheme, the user name and "@host" are kept; the password
  #     (1+ characters) is replaced up to the LAST "@" before the host,
  #     so a raw "@" inside the password is covered. A raw
  #     "/", "?" or "#" ends the authority, so a password holding one is not
  #     matched, and nor is an e-mail-style user name (an "@" before the
  #     colon): documented residuals. The scheme must start after a
  #     non-scheme character, which keeps the search linear on long letter
  #     runs. The user part may itself be an earlier [REDACTED: marker; a
  #     password that starts with a marker is not relabelled. A password
  #     that starts with "$" or "-" IS redacted (no exclusion here, unlike
  #     rules 10 and 12). User-name-only userinfo (no colon) is not matched.
  | gsub("(?<k>(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*://(?:\\[REDACTED:[A-Za-z0-9:_.-]*\\]|[^\\s/?#@:\"'\\[\\]])*:)(?!\\[REDACTED:)[^\\s/?#\"']+(?=@)"; "\(.k)[REDACTED:url-userinfo]")
  # 12. curl's user option, --user NAME:PASSWORD
  #     or -u NAME:PASSWORD (also -uNAME:PASSWORD): the part after the first
  #     colon, up to the next whitespace or quote, is replaced; NAME is kept.
  #     Scoped to a curl command: "curl" as a word, then the option later in
  #     the same command (the scan stops at a newline that is not a "\"
  #     line continuation, ";", "|", "&&" or a lone "&" before whitespace),
  #     so a uid:gid or host:path value on another command's --user / -u is
  #     never touched. Not matched: a value
  #     with no colon (curl then prompts), a password that starts with "$",
  #     "-" or a [REDACTED: marker, --user-agent, --proxy-user / -U, and a
  #     -u inside a combined short-option group (-su). A quoted value with a
  #     space in the password is replaced only up to the space.
  | gsub("(?<k>\\bcurl\\b(?:[^\\n;|&]|&(?=[^&\\s])|\\\\\\n)*?\\s(?:--user\\s+|-u\\s*)[\"']?(?:\\[REDACTED:[A-Za-z0-9:_.-]*\\]|[^\\s:\"'\\[\\]])*:)(?![$-]|\\[REDACTED:)[^\\s\"']+"; "\(.k)[REDACTED:credential-flag]");

# Pattern cap and tail margin (see ORDER AND CAPS in the header). Do not
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
# capped pattern rules. Every target type goes through it.
def redact: .[0:65536] | redact_env | redact_patterns_capped;

# Stringify a field; a missing field becomes "".
def str: if . == null then "" else tostring end;

# Exactly one JSON object is required; anything else fails the whole pass so
# the caller writes the "unknown" fallback record instead of a partial one.
# Every target: value step on a 65,536-char window FIRST, then the 4,000-char
# pattern cap, the guarded pattern rules and the tail margin (see ORDER AND
# CAPS in the header); Bash commands are then cut to 200 chars.
# $fallback == "withhold" (second pass only, see FAILURE PATHS in the header): the
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
# VALUE STEP in the header). npairs is the pair COUNT for the
# pair-count check, never a value.
RECORD=$(printf '%s' "$INPUT" | jq -c -s \
    --arg ts "$TIMESTAMP" \
    --arg ver "$DAAF_VERSION" \
    --arg model "$MODEL" \
    --arg fallback "" \
    --argjson npairs "${#CRED_NAMES[@]}" \
    --rawfile envpairs <(for sv_name in "${CRED_NAMES[@]}"; do builtin printf '%s\0%s\0' "$sv_name" "${!sv_name-}"; done) \
    "$JQ_RECORD" 2>/dev/null) || RECORD=""
# Second pass without the value step (see FAILURE PATHS in the header): no value
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
# No jq at all: every jq call above failed, so
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
