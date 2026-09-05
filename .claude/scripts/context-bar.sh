#!/usr/bin/env bash

# Color theme — set COLOR to one of: gray, orange, blue, teal, green,
# lavender, rose, gold, slate, cyan (see the case block below for the codes).
COLOR="blue"

# Color codes.
# ANSI-C quoting ($'...') so the real ESC byte lives in these TRUSTED variables.
# The final render uses printf '%s' (not '%b'), so backslash sequences arriving
# in UNTRUSTED fields (model name, effort label, cwd basename, git branch, last
# user message) stay inert literals and can never be re-materialized into escape
# sequences. See the render at the end of the file.
C_RESET=$'\033[0m'
C_GRAY=$'\033[38;5;245m'  # explicit gray for default text
C_BAR_EMPTY=$'\033[38;5;238m'
# Segment colors for the rate-limit addition (kept subtle so they do not
# compete with the single-accent context bar).
C_AMBER=$'\033[38;5;179m'   # rate limit warning (>=70%)
C_RED=$'\033[38;5;167m'     # rate limit danger (>=90%)
case "$COLOR" in
    orange)   C_ACCENT=$'\033[38;5;173m' ;;
    blue)     C_ACCENT=$'\033[38;5;74m' ;;
    teal)     C_ACCENT=$'\033[38;5;66m' ;;
    green)    C_ACCENT=$'\033[38;5;71m' ;;
    lavender) C_ACCENT=$'\033[38;5;139m' ;;
    rose)     C_ACCENT=$'\033[38;5;132m' ;;
    gold)     C_ACCENT=$'\033[38;5;136m' ;;
    slate)    C_ACCENT=$'\033[38;5;60m' ;;
    cyan)     C_ACCENT=$'\033[38;5;37m' ;;
    *)        C_ACCENT="$C_GRAY" ;;  # gray: all same color
esac

# Accept only canonical positive decimal integers that Bash can represent
# safely. Lexical and length/string bounds run before any arithmetic, so values
# such as 080000 or 9223372036854775808 can never reach an arithmetic context.
is_canonical_positive_decimal() {
    local value="${1:-}"
    local max_value="9223372036854775807"
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ ${#value} -lt ${#max_value} ]] && return 0
    [[ ${#value} -gt ${#max_value} ]] && return 1
    # Equal-length canonical decimals are intentionally compared lexicographically before arithmetic.
    # shellcheck disable=SC2071
    [[ "$value" == "$max_value" || "$value" < "$max_value" ]]
}

# As above, but ALSO accepts a canonical zero. The codex quota fields
# used_percent and *-reset-after-seconds are legitimately 0 (e.g. an unused
# window or an all-zero secondary), which is_canonical_positive_decimal rejects.
# Same length/lexical bounds run before any arithmetic so oversized or
# non-canonical values can never reach an arithmetic context.
is_canonical_nonneg_decimal() {
    local value="${1:-}"
    local max_value="9223372036854775807"
    [[ "$value" =~ ^(0|[1-9][0-9]*)$ ]] || return 1
    [[ ${#value} -lt ${#max_value} ]] && return 0
    [[ ${#value} -gt ${#max_value} ]] && return 1
    # Equal-length canonical decimals are intentionally compared lexicographically before arithmetic.
    # shellcheck disable=SC2071
    [[ "$value" == "$max_value" || "$value" < "$max_value" ]]
}

input=$(cat)

# One jq pass validates and normalizes every field before joining it with an
# ASCII unit separator. Identity/path strings containing C0/DEL controls become
# empty; display-only strings have those controls removed; numeric fields accept
# only their expected JSON scalar type. The session ID is validated against the
# complete path-safe grammar inside jq, before Bash can normalize a newline or
# drop a NUL. Therefore every emitted field is delimiter/control-free and the
# fixed-order read cannot be shifted by untrusted JSON content.
model="?"
cwd=""
transcript_path=""
max_context="200000"
session_id=""
model_id=""
model_id_state="invalid"
effort_level=""
rl_5h=""
rl_5h_reset=""
rl_7d=""
rl_7d_reset=""
payload_parsed=0
if command -v jq >/dev/null 2>&1; then
    if IFS=$'\x1f' read -r model cwd transcript_path max_context session_id model_id \
    model_id_state effort_level rl_5h rl_5h_reset rl_7d rl_7d_reset < <(printf '%s' "$input" | jq -er '
        def has_control:
            test("[[:cntrl:]]");
        def display_string($fallback):
            if type == "string" then gsub("[[:cntrl:]]"; "")
            else $fallback
            end;
        def control_free_string:
            if type == "string" then
                if has_control then "" else . end
            else ""
            end;
        def reset_scalar:
            if type == "number" then tostring
            elif type == "string" then
                if has_control then "" else . end
            else ""
            end;
        def valid_session_id:
            if type == "string" then
                (has_control | not) and
                test("^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
            else false
            end;

        if type != "object" then error("statusline payload must be an object")
        else
            [ ((.model.display_name? // .model.id? // "?") | display_string("?")),
              ((.cwd? // "") | control_free_string),
              ((.transcript_path? // "") | control_free_string),
              (if (.context_window.context_window_size? | type) == "number" then
                   if .context_window.context_window_size > 0 and
                          (.context_window.context_window_size | floor) == .context_window.context_window_size
                   then (.context_window.context_window_size | tostring)
                   else "200000"
                   end
               else "200000"
               end),
              (if (.session_id? | valid_session_id)
               then .session_id
               else ""
               end),
              ((.model.id? // "") | control_free_string),
              (if (.model | type) == "object" and (.model | has("id")) and
                       .model.id != null
               then
                   if (.model.id | type) == "string" and
                          ((.model.id | has_control) | not) and
                          (.model.id | length) > 0 and
                          (.model.id | length) <= 160
                   then "valid"
                   else "invalid"
                   end
               else "absent"
               end),
              ((.effort.level? // "") | display_string("")),
              (if (.rate_limits.five_hour.used_percentage? | type) == "number"
               then (.rate_limits.five_hour.used_percentage | tostring)
               else ""
               end),
              ((.rate_limits.five_hour.resets_at? // "") | reset_scalar),
              (if (.rate_limits.seven_day.used_percentage? | type) == "number"
               then (.rate_limits.seven_day.used_percentage | tostring)
               else ""
               end),
              ((.rate_limits.seven_day.resets_at? // "") | reset_scalar) ]
            | join("\u001f")
        end
    ' 2>/dev/null); then
        payload_parsed=1
    fi
fi

# Production caches live in /tmp. The override is a deterministic-test seam so
# Bats can exercise writes inside project scratch without touching live session
# state. Cache eligibility requires a successfully parsed payload plus a
# nonempty session ID in the established UUID-safe character set and bounded
# length. All other cases keep statusline rendering fail-open while skipping
# every session-scoped cache read and write below.
context_cache_dir="${DAAF_CONTEXT_BAR_CACHE_DIR:-/tmp}"
session_id_safe=0
if [[ "$payload_parsed" -eq 1 && \
      "$session_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && \
      ${#session_id} -le 128 ]]; then
    session_id_safe=1
fi

# Seed the authoritative main-session model cache from the statusline's
# .model.id. Replace through a same-directory sibling so reminder/reporting
# hooks never observe a partial write. An empty authoritative ID intentionally
# replaces any stale value with an empty file, causing GPT-specific consumers to
# treat identity as unresolved rather than guess.
if [[ "$session_id_safe" -eq 1 ]]; then
    model_cache="${context_cache_dir}/claude-model-${session_id}"
    model_tmp="${model_cache}.tmp.$$"
    # Brace-wrap the redirect so 2>/dev/null also covers an open() failure on '>'
    # (redirections apply left-to-right; a bare `> f 2>/dev/null` still prints the
    # open() diagnostic before 2> takes effect). Convention 6.
    if { printf '%s' "$model_id" > "$model_tmp"; } 2>/dev/null; then
        mv "$model_tmp" "$model_cache" 2>/dev/null || rm -f "$model_tmp" 2>/dev/null
    else
        rm -f "$model_tmp" 2>/dev/null
    fi
fi

# Guard against an unparseable payload leaving max_context empty (which would
# cause a divide-by-zero in the pct arithmetic below). Valid payloads always
# yield an integer here, so this only fires on malformed/empty stdin.
if ! is_canonical_positive_decimal "$max_context"; then
    max_context=200000
fi

# Directory basename from cwd
dir=$(basename "$cwd" 2>/dev/null || echo "?")

# Get git branch only (skip expensive status/sync checks). The branch name does
# not pass through the jq control-strip stage, so strip controls here before it
# reaches the printf '%s' render. jq -Rs (not tr) makes the strip Unicode-aware:
# gsub([[:cntrl:]]) removes C0, DEL, AND C1 (U+0080-U+009F) — git refnames only
# forbid bytes < 0x20 and DEL, so a hostile repo can name a branch with a
# UTF-8-encoded C1 control (e.g. U+009B, 8-bit CSI on xterm-class terminals),
# which byte-wise `tr -d '[:cntrl:]'` passed through. jq's UTF-8 decoding also
# replaces raw stray bytes with inert U+FFFD. If jq is unavailable the branch
# segment is simply omitted (fail-open; the bar is already degraded without jq).
branch=""
if [[ -n "$cwd" && -d "$cwd" ]]; then
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null | jq -Rsr 'gsub("[[:cntrl:]]"; "")' 2>/dev/null) || branch=""
fi

# Context window size: from JSON above, but override for OpenRouter models where
# Claude Code reports a hardcoded 200k default regardless of actual model.
# Calculate tokens from transcript (more accurate than total_input_tokens which
# excludes system prompt/tools/memory).
# See: github.com/anthropics/claude-code/issues/13652

# OpenRouter context window override: Claude Code doesn't know the real context
# window size for third-party models accessed via OpenRouter, so it reports a
# hardcoded 200k default. Query the OpenRouter models API once per session to
# get the actual context_length for the current model. Track successful dynamic
# resolution separately from the numeric value: 200000 can itself be an
# authoritative catalogue result and must not be mistaken for the generic
# fallback by the static map below.
or_context_resolved=0
# context_cache_dir and the session-ID path guard are initialized immediately
# after payload extraction. Malformed session IDs skip this cache-backed branch.
if [[ "$session_id_safe" -eq 1 && "${ANTHROPIC_BASE_URL:-}" == *openrouter.ai* ]]; then
    # model_id already extracted in the consolidated jq pass above
    # (byte-identical to the old `.model.id // empty`).
    or_cache="${context_cache_dir}/claude-or-models-${session_id}"

    if [[ -n "$model_id" && ! -s "$or_cache" ]]; then
        # Fetch models list once per session (3s timeout to avoid blocking statusline).
        # Writer-private temp ($$ suffix) prevents a fixed-name race under
        # overlapping session refreshes. Validate that the body is a JSON object
        # carrying a .data array BEFORE the atomic promote, so a truncated or
        # garbage 200-body (curl -sf already rejects non-2xx/timeout) cannot poison
        # the cache for the rest of the session. Convention 6/8.
        or_tmp="${or_cache}.tmp.$$"
        if { curl -sf --connect-timeout 3 --max-time 3 \
            "https://openrouter.ai/api/v1/models" > "$or_tmp"; } 2>/dev/null; then
            if jq -e '.data | type == "array"' "$or_tmp" >/dev/null 2>&1; then
                mv "$or_tmp" "$or_cache" 2>/dev/null || rm -f "$or_tmp" 2>/dev/null
            else
                rm -f "$or_tmp" 2>/dev/null
            fi
        else
            rm -f "$or_tmp" 2>/dev/null
        fi
    fi

    if [[ -n "$model_id" && -s "$or_cache" ]]; then
        # Try exact match first; if not found, strip date suffix (-YYYYMMDD)
        # because Claude Code appends snapshot dates (e.g., glm-5.1-20260406)
        # but OpenRouter uses versionless IDs (e.g., z-ai/glm-5.1).
        or_context=$(jq -r --arg id "$model_id" \
            'first(.data[] | select(.id == $id) | .context_length) // empty' \
            "$or_cache" 2>/dev/null)
        if [[ -z "$or_context" ]]; then
            stripped_id=$(echo "$model_id" | sed 's/-[0-9]\{8\}$//' 2>/dev/null)
            if [[ "$stripped_id" != "$model_id" ]]; then
                or_context=$(jq -r --arg id "$stripped_id" \
                    'first(.data[] | select(.id == $id) | .context_length) // empty' \
                    "$or_cache" 2>/dev/null)
            fi
        fi
        if is_canonical_positive_decimal "$or_context"; then
            max_context="$or_context"
            or_context_resolved=1
        fi
    fi
fi

# Static third-party window map. Claude Code reports a hardcoded 200k for
# unknown models, and the OpenRouter API lookup above is unavailable on direct
# provider-shim sessions or may fail transiently. Apply this map only when
# dynamic OpenRouter resolution did NOT succeed and max_context remains the
# untrusted 200k default. An authoritative dynamic value of exactly 200000 stays
# authoritative; the explicit user override below still has ordinary precedence.
#
# GLM matching is deliberately narrow: exact z-ai/glm-5.2 plus Claude Code's
# terminal -YYYYMMDD snapshot form. Do not broaden it to *glm-5.2*, which would
# incorrectly assign this window to glm-5.2-air or future variants. Verified
# against the exact OpenRouter catalogue entry on 2026-07-15: 1,048,576 tokens.
#
# GPT patterns are ordered most-specific first: *-mini* and *-chat* variants
# have smaller windows than the base gpt-5.4/5.5/5.6 flagships (the whole
# gpt-5.6 Sol/Terra/Luna family is 1,050,000), so they must precede the broad
# flagship and *gpt-5* fallbacks. Verified against OpenRouter on 2026-07-09.
# Closed-set GPT flagship grammar (Convention 3). Only the exact flagship set —
# bare gpt-5.4/5.5/5.6 plus the sol/terra/luna codenames, and the standalone
# GPT-6 flagship gpt-6-astra, each with an optional [1m] badge — is eligible for
# the 1,050,000 physical window (and the 919k ChatGPT-lane cap arm below).
# Anchored so malformed suffixes (gpt-5.4-, gpt-5.6-experimental, gpt-5.5[1m,
# gpt-5.6-sol[1m]x, gpt-6-astra-pro, gpt-6-astra[1m]-x) and left-boundary near
# misses (xgpt-6-astra, gpt-6-astrab) fall through to the ordinary default
# rather than being mapped to the flagship window. New codenames are a
# deliberate one-line edit here, consistent with DAAF's validate-before-trust
# policy. Stored in a variable to avoid [[ =~ ]] quoting pitfalls; defined
# unconditionally so it is in scope for the ChatGPT-lane predicate below even
# when this static-map block is skipped.
gpt_flagship_re='^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-astra)(\[1m\])?$'
# Closed-set mini/chat grammars (Convention 3), byte-consistent with
# subagent-bar.sh's anchored EREs. These replace the old open-ended inner globs
# (*-mini*/*-chat*) so suffixed near-misses (e.g. gpt-5.6-mini-preview) fail the
# anchor and fall through to the conservative 200k default rather than being
# mapped to 400k/128k. Anchored on the same provider-stripped physical_slug the
# globs inspected. Defined here alongside the flagship grammar for locality.
gpt_mini_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-mini(\[1m\])?$'
gpt_chat_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-chat(\[1m\])?$'
if [[ -n "$model_id" && "$or_context_resolved" -eq 0 && "$max_context" -eq 200000 ]]; then
    # Physical-family classification operates on the terminal provider-stripped
    # slug only. mini/chat variants have smaller windows and are matched by their
    # own arms before the anchored flagship test; the flagship 1,050,000 window is
    # granted only when the anchored grammar matches, so notgpt-5.6, gpt-5.60, and
    # trailing-junk near-misses stay on the ordinary default.
    physical_slug="${model_id##*/}"
    case "$model_id" in
        z-ai/glm-5.2|z-ai/glm-5.2-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
            max_context=1048576 ;;
        *)
            case "$physical_slug" in
                gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*|gpt-6-astra|gpt-6-astra[-\[]*)
                    # Closed-set classification (Convention 3), byte-consistent
                    # with subagent-bar.sh: only the anchored flagship/mini/chat
                    # grammars earn a GPT window. Order flagship, then mini, then
                    # chat. Malformed suffixes that reached this family glob (e.g.
                    # gpt-5.4-, gpt-5.6-experimental, gpt-5.6-mini-preview,
                    # gpt-5.6-sol[1m]x, gpt-6-astra-pro, gpt-6-astra[1m]-x) match
                    # none and fall through to the 200k default (max_context is
                    # already 200000 in this block).
                    if   [[ "$physical_slug" =~ $gpt_flagship_re ]]; then max_context=1050000
                    elif [[ "$physical_slug" =~ $gpt_mini_re ]];     then max_context=400000
                    elif [[ "$physical_slug" =~ $gpt_chat_re ]];     then max_context=128000
                    fi
                    ;;
                gpt-5|gpt-5[-\[]*|gpt-5.2|gpt-5.2[-\[]*)
                    case "$physical_slug" in
                        *-chat*) max_context=128000 ;;
                        *) max_context=400000 ;;
                    esac
                    ;;
            esac
            ;;
    esac
fi

# CLAUDE_CODE_MAX_CONTEXT_TOKENS is the user's explicit ordinary override over
# JSON defaults, OpenRouter lookup, and the static map. A backend-specific final
# physical-accounting constraint is applied after this step.
if is_canonical_positive_decimal "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}"; then
    max_context="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
fi

# ChatGPT-subscription/Codex final physical-window accounting constraint.
# Canonical activation requires BOTH exact lane signals and a model in the same
# anchored flagship arm used by the static map above — the gpt-5.4/5.5/5.6
# family plus gpt-6-astra (mini/chat variants are excluded by the arm's
# ordering). Probes 2026-09-05 (Codex CLI 0.153.2, shim v1.3.19,
# SHIM_BACKEND_MODE=chatgpt) measured BOTH lane flagships: gpt-6-astra accepted
# 919,053 real input tokens and rejected 922,552; gpt-5.6-sol accepted 910,827
# and rejected 921,973. 919000 is therefore the lane-wide accounting ceiling for
# this mapped flagship family, MEASURED for Sol and Astra alike and consistent
# with Astra's documented 922,000-token max input (1,050,000 window - 128,000
# output). Provenance: previously 370,000 (2026-07-16), now stale. Apply min()
# only after every ordinary resolution source, including an incoming [1m] payload and
# CLAUDE_CODE_MAX_CONTEXT_TOKENS, so neither can raise the matched lane above the
# backend ceiling while an explicitly lower positive value remains lower.
#
# This controls DAAF's denominator, statusline, and downstream severity guidance.
# It is NOT compaction and is NOT a transport-level request blocker; the backend
# remains the ultimate hard ceiling. Exact equality keeps malformed/noncanonical
# lane values fail-open, while API/OpenRouter routes retain their wider windows.
gpt_flagship=0
physical_slug="${model_id##*/}"
# Same anchored closed-set predicate as the static map (Convention 3): the 919k
# lane cap applies only to the exact flagship set, so mini/chat variants and
# malformed near-misses keep their resolved (wider or default) window fail-open.
if [[ "$physical_slug" =~ $gpt_flagship_re ]]; then
    gpt_flagship=1
fi
if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
      "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
      "$gpt_flagship" -eq 1 && "$max_context" -gt 919000 ]]; then
    max_context=919000
fi

max_k=$((max_context / 1000))

# Share context window size with hooks (which don't receive it in their input
# payload). Unsafe session IDs skip the path construction and retain fail-open
# statusline output without creating an attacker-controlled cache path.
if [[ "$session_id_safe" -eq 1 ]]; then
    # Atomic publish (Convention 7): a concurrent reader (context-reporter.sh) must
    # never observe a momentarily-empty file from a direct truncate-write and fall
    # back to 200k. Write a writer-private temp then rename, mirroring the model
    # cache above. Brace-wrap so 2>/dev/null covers an open() failure on '>' too
    # (Convention 6); if the cache dir is unusable, skip caching and keep rendering.
    ctx_window_cache="${context_cache_dir}/claude-ctx-window-${session_id}"
    ctx_window_tmp="${ctx_window_cache}.tmp.$$"
    if { printf '%s\n' "$max_context" > "$ctx_window_tmp"; } 2>/dev/null; then
        mv "$ctx_window_tmp" "$ctx_window_cache" 2>/dev/null || rm -f "$ctx_window_tmp" 2>/dev/null
    else
        rm -f "$ctx_window_tmp" 2>/dev/null
    fi
fi

# Calculate context bar from transcript
if [[ -n "$transcript_path" && -f "$transcript_path" ]]; then
    # Map each main-chain usage entry to its token sum and take the last
    # POSITIVE sum rather than the last entry outright. Defensive: shim-routed
    # (GPT) transcripts end with streaming-placeholder usage entries whose token
    # fields are all 0; taking `last` unconditionally would compute 0 and stall
    # the bar at the ~baseline reading. Not currently triggered on main
    # transcripts (the main session is native Claude today) but mirrors the
    # context-reporter.sh / subagent-bar.sh fix so all three stay consistent.
    # Native Claude transcripts are unaffected (last entry is already positive,
    # so last-positive == last). `// 0` preserves the fail-open contract.
    context_length=$(jq -s '
        [.[] | select(.message.usage and .isSidechain != true and .isApiErrorMessage != true) | (
            (.message.usage.input_tokens // 0) +
            (.message.usage.cache_read_input_tokens // 0) +
            (.message.usage.cache_creation_input_tokens // 0)
        )] | map(select(. > 0)) | last // 0
    ' < "$transcript_path" 2>/dev/null)

    # 20k baseline: conservative default estimate for system prompt, tools, memory,
    # skills, env block, XML framing, and other dynamic context
    baseline=20000
    bar_width=10

    # Bounded numerator (Convention 5): only multiply context_length by 100 when it
    # is a canonical positive decimal AND <= floor(INT64_MAX/100) = 92233720368547758,
    # so a huge but int64-valid token count cannot overflow signed-64 arithmetic and
    # wrap pct negative (a negative pct evades the `-gt 100` clamp and would render).
    # is_canonical_positive_decimal guarantees the value fits in int64, so the -le
    # comparison is itself overflow-safe. Anything else falls to the baseline estimate.
    if is_canonical_positive_decimal "$context_length" && \
       [[ "$context_length" -le 92233720368547758 ]]; then
        pct=$((context_length * 100 / max_context))
        pct_prefix=""
    else
        # At conversation start, ~40k baseline is already loaded
        pct=$((baseline * 100 / max_context))
        pct_prefix="~"
    fi

    [[ $pct -gt 100 ]] && pct=100

    bar=""
    for ((i=0; i<bar_width; i++)); do
        bar_start=$((i * 10))
        progress=$((pct - bar_start))
        if [[ $progress -ge 8 ]]; then
            bar+="${C_ACCENT}█${C_RESET}"
        elif [[ $progress -ge 3 ]]; then
            bar+="${C_ACCENT}▄${C_RESET}"
        else
            bar+="${C_BAR_EMPTY}░${C_RESET}"
        fi
    done

    ctx="${bar} ${C_GRAY}${pct_prefix}${pct}% of ${max_k}k tokens"
else
    # Transcript not available yet - show baseline estimate
    baseline=20000
    bar_width=10
    pct=$((baseline * 100 / max_context))
    [[ $pct -gt 100 ]] && pct=100

    bar=""
    for ((i=0; i<bar_width; i++)); do
        bar_start=$((i * 10))
        progress=$((pct - bar_start))
        if [[ $progress -ge 8 ]]; then
            bar+="${C_ACCENT}█${C_RESET}"
        elif [[ $progress -ge 3 ]]; then
            bar+="${C_ACCENT}▄${C_RESET}"
        else
            bar+="${C_BAR_EMPTY}░${C_RESET}"
        fi
    done

    ctx="${bar} ${C_GRAY}~${pct}% of ${max_k}k tokens"
fi

# --- Model display ---
# Append the effort level directly to the model name when the payload reports
# one (low/medium/high/xhigh/max), e.g. "Fable 5 (high)". Kept inside the model
# segment so effort reads as a property of the model rather than a standalone
# indicator.
#
# D2 display sanitization (shim/GPT models routed through the provider shim).
# The client reports the *configured* model slug as the display name, which for
# shim sessions can carry an effort suffix (#high/#xhigh/#medium/...) AND a
# duplicated [1m] context badge (the client re-appends its own [1m] to a slug
# that already ends in [1m]) -> e.g. "gpt-5.6-sol[1m]#xhigh[1m]". It also pins
# effort=high for unknown (GPT) models, so the "(high)" label is meaningless
# here. All three are display-only cosmetics; native Claude models are untouched.
# Fail-open: pure string ops, no external calls; on any surprise the worst case
# is the unmodified name.
model_name="$model"
gpt_model=0
# Classify only a bounded, anchored terminal GPT slug. The consolidated payload
# parser preserves whether model.id is valid, genuinely absent/null, or present
# but invalid; display_name is a fallback only for the absent/null state. Provider
# prefixes are stripped before matching, while malformed left boundaries such as
# notgpt-*, xgpt-*, and foo-gpt-* cannot match.
# The display fallback first removes the established effort suffix and duplicate
# [1m] cosmetic so legitimate shim display slugs retain their prior behavior.
gpt_status_slug_re='^(gpt|GPT)-[A-Za-z0-9][A-Za-z0-9._-]*(\[1m\])?$'
gpt_status_candidate=""
if [[ "$model_id_state" == "valid" ]]; then
    gpt_status_candidate="${model_id##*/}"
elif [[ "$model_id_state" == "absent" ]]; then
    gpt_status_candidate="${model_name##*/}"
    gpt_status_candidate="${gpt_status_candidate%%#*}"
    while [[ "$gpt_status_candidate" == *'[1m][1m]' ]]; do
        gpt_status_candidate="${gpt_status_candidate%'[1m]'}"
    done
fi
if [[ ${#gpt_status_candidate} -le 160 && \
      "$gpt_status_candidate" =~ $gpt_status_slug_re ]]; then
    gpt_model=1
fi

if [[ "$gpt_model" -eq 1 ]]; then
    # 1) strip a trailing "#<effort>" token (and anything the client appended
    #    after it, e.g. a duplicate [1m]): keep everything before the first '#'.
    model_name="${model_name%%#*}"
    # 2) collapse a duplicated trailing "[1m]" to a single one (covers the case
    #    where the slug itself ended in [1m] and the client added another).
    while [[ "$model_name" == *'[1m][1m]' ]]; do
        model_name="${model_name%'[1m]'}"
    done
fi

model_disp="$model_name"
# Effort label: keep it for native Claude models (a real, user-controlled
# setting); suppress it for GPT/shim models where the client pins it to "high"
# regardless of the actual routing.
if [[ -n "$effort_level" && "$gpt_model" -ne 1 ]]; then
    model_disp="${model_name} (${effort_level})"
fi

# --- GPT provider-shim Fast indicator ---
# Render one route-neutral ON-only label. The indicator requires the existing
# statusline GPT classification, an exact supported shim route, exact local
# native-Fast disablement, and a strictly validated /health ON state. Every
# missing, invalid, OFF, ineffective, mismatched, or unavailable state is silent.
gpt_tier_seg=""
if [[ "$gpt_model" -eq 1 && \
      "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
      ( "${SHIM_BACKEND_MODE:-}" == "chatgpt" || \
        "${SHIM_BACKEND_MODE:-}" == "openai" ) && \
      "${CLAUDE_CODE_DISABLE_FAST_MODE:-}" == "1" ]]; then
    gpt_route="${SHIM_BACKEND_MODE}"
    health_port="${SHIM_PORT:-4141}"
    if ! is_canonical_positive_decimal "$health_port" || \
       [[ "$health_port" -gt 65535 ]]; then
        health_port=4141
    fi

    health_on=""
    if command -v curl >/dev/null 2>&1 && \
       command -v python3 >/dev/null 2>&1 && \
       command -v jq >/dev/null 2>&1; then
        # Disable ambient curl config with first-option -q, then enforce hardcoded
        # loopback, proxy bypass, zero allowed redirects, short deadlines, and a
        # 16 KiB transfer ceiling. Before jq, Python's stdlib parser rejects duplicate
        # member names at every object depth and emits canonical JSON; pipefail makes
        # any transport/parser/semantic failure silent. Only literal "on" enters Bash.
        health_on=$(
            set -o pipefail
            curl -q --fail --silent --show-error \
                --location --max-redirs 0 \
                --noproxy '*' --proxy '' \
                --connect-timeout 0.2 --max-time 0.6 \
                --max-filesize 16384 \
                "http://127.0.0.1:${health_port}/health" 2>/dev/null |
            python3 -c '
import json, sys
reject = lambda pairs: dict(pairs) if len(pairs) == len(dict(pairs)) else (_ for _ in ()).throw(ValueError("duplicate object member"))
reject_constant = lambda value: (_ for _ in ()).throw(ValueError("invalid JSON constant"))
json.dump(json.load(sys.stdin, object_pairs_hook=reject, parse_constant=reject_constant), sys.stdout, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
' 2>/dev/null |
            jq -er --arg expected_backend "$gpt_route" '
                def exact_keys($expected):
                    type == "object" and
                    ((keys | sort) == ($expected | sort));
                def canonical_version:
                    type == "string" and
                    test("^[A-Za-z0-9._+-]{1,64}$");
                def bounded_terminal_model:
                    type == "string" and
                    test("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$");

                if type != "object" then error("health must be an object") else . end
                | select(.service == "daaf-anthropic-openai-shim")
                | select(.status == "ok")
                | select(.version | canonical_version)
                | select(.backend_mode == $expected_backend)
                | .gpt_service_tier as $g
                | select($g | exact_keys([
                    "backend_mode", "requested_tier_vocabulary", "policy",
                    "native_fast_disabled", "latest_terminal"
                  ]))
                | select($g.backend_mode == $expected_backend)
                | select(
                    ($expected_backend == "chatgpt" or
                     $expected_backend == "openai") and
                    $g.requested_tier_vocabulary == "priority"
                  )
                | select($g.native_fast_disabled | type == "boolean")
                | $g.policy as $p
                | select($p | exact_keys([
                    "status", "backend_mode", "enabled", "effective"
                  ]))
                | select(["ok", "missing", "invalid", "unreadable", "unsafe"] |
                         index($p.status))
                | select($p.backend_mode == null or
                         $p.backend_mode == "chatgpt" or
                         $p.backend_mode == "openai")
                | select(($p.enabled | type) == "boolean" and
                         ($p.effective | type) == "boolean")
                | select(
                    ($p.status == "ok" and $p.backend_mode != null) or
                    ($p.status != "ok" and $p.backend_mode == null and
                     ($p.enabled | not) and ($p.effective | not))
                  )
                | select(($p.effective | not) or
                         ($p.enabled and $p.backend_mode == $expected_backend))
                | $g.latest_terminal as $l
                | select($l == null or (
                    ($l | exact_keys([
                      "model", "requested_service_tier", "requested_source",
                      "served_service_tier", "completed_at"
                    ])) and
                    ($l.model == null or ($l.model | bounded_terminal_model)) and
                    ($l.requested_service_tier == null or
                     (($expected_backend == "chatgpt" or
                       $expected_backend == "openai") and
                      $l.requested_service_tier == "priority")) and
                    (["none", "anthropic", "shim_global", "both"] |
                     index($l.requested_source)) and
                    (($l.requested_source == "none") ==
                     ($l.requested_service_tier == null)) and
                    ([null, "fast", "priority", "default", "flex", "scale", "auto"] |
                     index($l.served_service_tier)) and
                    (($l.completed_at | type) == "string") and
                    ($l.completed_at |
                     test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")) and
                    (($l.completed_at |
                      try (fromdateiso8601 | strftime("%Y-%m-%dT%H:%M:%SZ")) catch "") ==
                     $l.completed_at)
                  ))
                | select($g.native_fast_disabled == true)
                | select($p.status == "ok" and
                         $p.backend_mode == $expected_backend and
                         $p.enabled == true and
                         $p.effective == true)
                | "on"
            ' 2>/dev/null
        ) || health_on=""
    fi

    if [[ "$health_on" == "on" ]]; then
        gpt_tier_seg=" ${C_GRAY}|${C_RESET} ${C_GRAY}GPT Fast On${C_RESET}"
    fi
fi

# --- Rate-limit segment ---
# Present only for Claude.ai subscriber sessions (absent on API-key sessions).
# Renders as: Plan usage: 5h:42%(2h10m) 7d:13%(3d4h)
# Color each percentage: gray <70, amber >=70, red >=90. Each window appends a
# reset countdown derived from resets_at whenever it can be parsed (epoch
# seconds and ISO-8601 both handled; omitted rather than printing garbage).
rl_seg=""
rl_color_for() {
    # $1 = integer percent; echoes an ANSI color code.
    if   [[ "$1" -ge 90 ]]; then printf '%s' "$C_RED"
    elif [[ "$1" -ge 70 ]]; then printf '%s' "$C_AMBER"
    else                         printf '%s' "$C_GRAY"
    fi
}
fmt_reset() {
    # $1 = resets_at (epoch seconds or ISO-8601). Echoes "(NdNh)" / "(NhNm)"
    # time remaining, or nothing when unparseable or already past (fail-open:
    # omit rather than print garbage or corrupt the bar).
    local raw="$1" reset_epoch="" now_epoch="" remain
    if [[ "$raw" =~ ^[0-9]+$ ]]; then
        reset_epoch="$raw"                       # already epoch seconds
    else
        reset_epoch=$(date -d "$raw" +%s 2>/dev/null) || reset_epoch=""
    fi
    [[ "$reset_epoch" =~ ^[0-9]+$ ]] || return 0
    # 13+ digits means epoch MILLISECONDS (seconds stay 10 digits until 2286);
    # normalize so a ms timestamp doesn't render as a multi-decade countdown.
    [[ ${#reset_epoch} -ge 13 ]] && reset_epoch=$((reset_epoch / 1000))
    now_epoch=$(date +%s 2>/dev/null) || now_epoch=""
    # Guard: arithmetic on an empty now_epoch would emit a bash syntax error
    # to stderr/stdout and corrupt the statusline.
    [[ "$now_epoch" =~ ^[0-9]+$ ]] || return 0
    remain=$((reset_epoch - now_epoch))
    [[ "$remain" -gt 0 ]] || return 0
    if [[ "$remain" -ge 86400 ]]; then
        printf '(%dd%dh)' $((remain / 86400)) $(((remain % 86400) / 3600))
    else
        printf '(%dh%dm)' $((remain / 3600)) $(((remain % 3600) / 60))
    fi
}
window_label_for() {
    # $1 = window length in whole minutes (a validated positive integer). Echoes a
    # compact window label: divisible by 1440 -> "<N>d" (10080 -> 7d), else divisible
    # by 60 -> "<N>h" (300 -> 5h), else "<N>m". Pure arithmetic on a pre-validated int.
    local min="$1"
    if   [[ $((min % 1440)) -eq 0 ]]; then printf '%dd' $((min / 1440))
    elif [[ $((min % 60)) -eq 0 ]];   then printf '%dh' $((min / 60))
    else                                   printf '%dm' "$min"
    fi
}
if [[ -n "$rl_5h" || -n "$rl_7d" ]]; then
    rl_body=""
    if [[ -n "$rl_5h" ]]; then
        rl_5h_int=${rl_5h%.*}                    # strip any fractional part
        [[ "$rl_5h_int" =~ ^[0-9]+$ ]] || rl_5h_int=0
        c5=$(rl_color_for "$rl_5h_int")
        cd5=$(fmt_reset "$rl_5h_reset")
        rl_body+="${c5}5h:${rl_5h_int}%${C_RESET}"
        [[ -n "$cd5" ]] && rl_body+="${C_GRAY}${cd5}${C_RESET}"
    fi
    if [[ -n "$rl_7d" ]]; then
        rl_7d_int=${rl_7d%.*}
        [[ "$rl_7d_int" =~ ^[0-9]+$ ]] || rl_7d_int=0
        c7=$(rl_color_for "$rl_7d_int")
        cd7=$(fmt_reset "$rl_7d_reset")
        [[ -n "$rl_body" ]] && rl_body+=" "
        rl_body+="${c7}7d:${rl_7d_int}%${C_RESET}"
        [[ -n "$cd7" ]] && rl_body+="${C_GRAY}${cd7}${C_RESET}"
    fi
    [[ -n "$rl_body" ]] && rl_seg=" ${C_GRAY}|${C_RESET} ${C_GRAY}Plan usage:${C_RESET} ${rl_body}"
fi

# --- Codex (ChatGPT-subscription) Plan-usage fallback ---
# On shim-lane sessions the native Anthropic rate-limit payload fields are absent;
# instead the provider shim caches its latest ChatGPT-subscription quota snapshot to
# scripts/provider_shim/logs/quota_state.json (see anthropic_openai_shim.py
# _write_quota_state — install-shared under the shared-/daaf assumption). Render that
# file as the SAME unchanged "Plan usage:" segment, reusing rl_color_for/fmt_reset.
# Gate (belt-and-braces): the exact shim lane AND no native rate limits in the payload
# (if the payload somehow carries native limits, they win and this read is skipped).
# Everything here is pure string/arithmetic + one local file read; any parse or
# validation failure yields no segment and leaves the rest of the statusline untouched.
if [[ -z "$rl_seg" && \
      "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
      "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
      -z "$rl_5h" && -z "$rl_7d" ]]; then
    # State-file path: default derived from this script's own location
    # (.claude/scripts -> repo root -> scripts/provider_shim/logs/quota_state.json).
    # DAAF_QUOTA_STATE_FILE is a deterministic-test seam mirroring
    # DAAF_CONTEXT_BAR_CACHE_DIR: Bats points it at project scratch so tests never
    # depend on a live shim's log directory.
    quota_state_file="${DAAF_QUOTA_STATE_FILE:-}"
    if [[ -z "$quota_state_file" ]]; then
        cb_scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P 2>/dev/null)" || cb_scripts_dir=""
        if [[ -n "$cb_scripts_dir" ]]; then
            quota_state_file="${cb_scripts_dir%/.claude/scripts}/scripts/provider_shim/logs/quota_state.json"
        fi
    fi

    if [[ -n "$quota_state_file" && -f "$quota_state_file" ]] && command -v jq >/dev/null 2>&1; then
        # One jq pass: require a top-level object, emit captured_at plus the six
        # numeric primary/secondary fields as an ASCII-unit-separated record. String
        # fields carrying any control character (including the \x1f delimiter) become
        # empty so untrusted content cannot shift the fixed-order read; every emitted
        # field is validated numerically in Bash below before any use.
        q_captured=""
        q_p_pct=""
        q_p_win=""
        q_p_reset=""
        q_s_pct=""
        q_s_win=""
        q_s_reset=""
        codex_parsed=0
        if IFS=$'\x1f' read -r q_captured q_p_pct q_p_win q_p_reset q_s_pct q_s_win q_s_reset \
            < <(jq -er '
                def num_string:
                    if type == "string" then (if test("[[:cntrl:]]") then "" else . end)
                    elif type == "number" then tostring
                    else "" end;
                if type != "object" then error("quota_state must be an object")
                else
                    [ (if (.captured_at? | type) == "number" and
                            (.captured_at | floor) == .captured_at
                       then (.captured_at | tostring) else "" end),
                      (.primary_used_pct? | num_string),
                      (.primary_window_min? | num_string),
                      (.primary_reset_s? | num_string),
                      (.secondary_used_pct? | num_string),
                      (.secondary_window_min? | num_string),
                      (.secondary_reset_s? | num_string) ]
                    | join("\u001f")
                end
            ' "$quota_state_file" 2>/dev/null); then
            codex_parsed=1
        fi

        # Plan-usage percent parity with the native rate-limit path (Convention 9):
        # floor a fractional percent (69.9 -> 69) so a legitimate fractional value
        # is KEPT rather than dropped by the integer-only validator below, and so
        # the <=100 clamp has an integer to compare. The strip is gated on a strict
        # plain-decimal shape (^[0-9]+\.[0-9]+$) so ONLY a genuine fractional is
        # floored: an exponent-notation value carrying a dot (e.g. "1.0e999") must not
        # survive the strip as "1" and render "1%" — leaving it intact makes the
        # is_canonical_nonneg_decimal gate below drop it (fail-closed). A non-numeric or
        # negative value likewise stays intact and remains a fail-closed drop.
        [[ "$q_p_pct" =~ ^[0-9]+\.[0-9]+$ ]] && q_p_pct="${q_p_pct%.*}"
        [[ "$q_s_pct" =~ ^[0-9]+\.[0-9]+$ ]] && q_s_pct="${q_s_pct%.*}"

        # Primary window is mandatory: captured_at + used-percent (0 allowed) + a
        # positive window length + reset-after (0 allowed) must all validate.
        if [[ "$codex_parsed" -eq 1 ]] && \
           is_canonical_nonneg_decimal "$q_captured" && \
           is_canonical_nonneg_decimal "$q_p_pct" && \
           is_canonical_positive_decimal "$q_p_win" && \
           is_canonical_nonneg_decimal "$q_p_reset"; then
            # Clamp to <=100 (parity with the native path's intent): a stale/overshoot
            # cached percent must not render as e.g. 101%. Validated int64 above, so
            # the arithmetic comparison is safe.
            (( q_p_pct > 100 )) && q_p_pct=100
            now_epoch=$(date +%s 2>/dev/null) || now_epoch=""
            # Both operands are already bounded to int64-representable canonical decimals
            # (is_canonical_nonneg_decimal above), but if their sum were ever to overflow
            # bash's 64-bit arithmetic, it wraps negative -- which safely fails the
            # `-gt now_epoch` staleness check below rather than corrupting the display.
            primary_reset_epoch=$((q_captured + q_p_reset))
            # Staleness: an expired primary window means the cached percent is stale, so
            # drop the ENTIRE segment (no display beats a wrong display).
            if [[ "$now_epoch" =~ ^[0-9]+$ && "$primary_reset_epoch" -gt "$now_epoch" ]]; then
                cbody=""
                pwl=$(window_label_for "$q_p_win")
                pcolor=$(rl_color_for "$q_p_pct")
                pcd=$(fmt_reset "$primary_reset_epoch")
                cbody+="${pcolor}${pwl}:${q_p_pct}%${C_RESET}"
                [[ -n "$pcd" ]] && cbody+="${C_GRAY}${pcd}${C_RESET}"
                # Secondary renders only when its window is > 0 and its percent
                # validates; live data shows an all-zero secondary, which is omitted.
                if is_canonical_positive_decimal "$q_s_win" && \
                   is_canonical_nonneg_decimal "$q_s_pct"; then
                    (( q_s_pct > 100 )) && q_s_pct=100
                    swl=$(window_label_for "$q_s_win")
                    scolor=$(rl_color_for "$q_s_pct")
                    cbody+=" ${scolor}${swl}:${q_s_pct}%${C_RESET}"
                    if is_canonical_nonneg_decimal "$q_s_reset"; then
                        secondary_reset_epoch=$((q_captured + q_s_reset))
                        scd=$(fmt_reset "$secondary_reset_epoch")
                        [[ -n "$scd" ]] && cbody+="${C_GRAY}${scd}${C_RESET}"
                    fi
                fi
                rl_seg=" ${C_GRAY}|${C_RESET} ${C_GRAY}Plan usage:${C_RESET} ${cbody}"
            fi
        fi
    fi
fi

# Build output: Model (effort) | Dir | Branch | Context
#               [| GPT Fast On] [| Plan usage]
output="${C_ACCENT}${model_disp}${C_GRAY} | 📁${dir}"
[[ -n "$branch" ]] && output+=" | 🔀${branch}"
output+=" | ${ctx}${C_RESET}"
output+="${gpt_tier_seg}"
output+="${rl_seg}"

# Render with %s (not %b): the color bytes already live in the $'...' constants,
# so untrusted field content (model name, effort, cwd, branch, message) is emitted
# verbatim and its backslash sequences stay inert — a printable \033]52;c;... OSC
# payload in a field can never be re-materialized into a real escape. Convention 1.
printf '%s\n' "$output"

# Get user's last message (text only, not tool results, skip unhelpful messages)
if [[ -n "$transcript_path" && -f "$transcript_path" ]]; then
    # Calculate visible length (without ANSI codes) - 10 chars for bar + content
    plain_output="${model_disp} | 📁${dir}"
    [[ -n "$branch" ]] && plain_output+=" | 🔀${branch}"
    plain_output+=" | xxxxxxxxxx ${pct}% of ${max_k}k tokens"
    max_len=${#plain_output}
    last_user_msg=$(jq -rs '
        # Messages to skip (not useful as context)
        def is_unhelpful:
            startswith("[Request interrupted") or
            startswith("[Request cancelled") or
            . == "";

        [.[] | select(.type == "user") |
         select(.message.content | type == "string" or
                (type == "array" and any(.[]; .type == "text")))] |
        reverse |
        map(.message.content |
            if type == "string" then .
            else [.[] | select(.type == "text") | .text] | join(" ") end |
            gsub("[[:cntrl:]]"; " ") | gsub("  +"; " ")) |
        map(select(is_unhelpful | not)) |
        first // ""
    ' < "$transcript_path" 2>/dev/null)

    if [[ -n "$last_user_msg" ]]; then
        if [[ ${#last_user_msg} -gt $max_len ]]; then
            echo "💬 ${last_user_msg:0:$((max_len - 3))}..."
        else
            echo "💬 ${last_user_msg}"
        fi
    fi
fi