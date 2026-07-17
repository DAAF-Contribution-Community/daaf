#!/usr/bin/env bash

# Color theme — set COLOR to one of: gray, orange, blue, teal, green,
# lavender, rose, gold, slate, cyan (see the case block below for the codes).
COLOR="blue"

# Color codes
C_RESET='\033[0m'
C_GRAY='\033[38;5;245m'  # explicit gray for default text
C_BAR_EMPTY='\033[38;5;238m'
# Segment colors for the rate-limit addition (kept subtle so they do not
# compete with the single-accent context bar).
C_AMBER='\033[38;5;179m'   # rate limit warning (>=70%)
C_RED='\033[38;5;167m'     # rate limit danger (>=90%)
case "$COLOR" in
    orange)   C_ACCENT='\033[38;5;173m' ;;
    blue)     C_ACCENT='\033[38;5;74m' ;;
    teal)     C_ACCENT='\033[38;5;66m' ;;
    green)    C_ACCENT='\033[38;5;71m' ;;
    lavender) C_ACCENT='\033[38;5;139m' ;;
    rose)     C_ACCENT='\033[38;5;132m' ;;
    gold)     C_ACCENT='\033[38;5;136m' ;;
    slate)    C_ACCENT='\033[38;5;60m' ;;
    cyan)     C_ACCENT='\033[38;5;37m' ;;
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

input=$(cat)

# Single consolidated jq pass over the payload: extract every field used below
# as one tab-separated record, then read into shell variables. This replaces
# what were ~5 separate `jq` invocations on "$input" (one process fork each).
# Field order and defaults are preserved byte-for-byte from the prior per-field
# calls so downstream logic (OpenRouter override, transcript parsing, the
# /tmp/claude-ctx-window write) behaves identically:
#   model            = .model.display_name // .model.id // "?"
#   cwd              = .cwd // ""
#   transcript_path  = .transcript_path // ""
#   max_context      = .context_window.context_window_size // 200000
#   session_id       = .session_id // "default"
#   model_id         = .model.id // ""           (used by the OpenRouter block)
# New optional segments (all default to empty when absent, e.g. API-key sessions):
#   effort_level     = .effort.level
#   rl_5h            = .rate_limits.five_hour.used_percentage
#   rl_5h_reset      = .rate_limits.five_hour.resets_at
#   rl_7d            = .rate_limits.seven_day.used_percentage
#   rl_7d_reset      = .rate_limits.seven_day.resets_at
# Fields are joined with the ASCII unit separator \x1f, NOT @tsv: tab is IFS
# *whitespace* in bash, so consecutive tabs collapse and any EMPTY field (e.g.
# transcript_path at session start, or the absent effort/rate-limit fields)
# would silently shift every later field left. A non-whitespace IFS preserves
# empty fields. See subagent-bar.sh FIELD-JOINING NOTE for the discovery story.
IFS=$'\x1f' read -r model cwd transcript_path max_context session_id model_id \
    effort_level rl_5h rl_5h_reset rl_7d rl_7d_reset < <(echo "$input" | jq -r '
    [ (.model.display_name // .model.id // "?"),
      (.cwd // ""),
      (.transcript_path // ""),
      (.context_window.context_window_size // 200000 | tostring),
      (.session_id // "default"),
      (.model.id // ""),
      (.effort.level // ""),
      (.rate_limits.five_hour.used_percentage // ""),
      (.rate_limits.five_hour.resets_at // ""),
      (.rate_limits.seven_day.used_percentage // ""),
      (.rate_limits.seven_day.resets_at // "") ]
    | map(tostring) | join("\u001f")
')

# Guard against an unparseable payload leaving max_context empty (which would
# cause a divide-by-zero in the pct arithmetic below). Valid payloads always
# yield an integer here, so this only fires on malformed/empty stdin.
if ! is_canonical_positive_decimal "$max_context"; then
    max_context=200000
fi

# Directory basename from cwd
dir=$(basename "$cwd" 2>/dev/null || echo "?")

# Get git branch only (skip expensive status/sync checks)
branch=""
if [[ -n "$cwd" && -d "$cwd" ]]; then
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
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
# Production uses /tmp so hooks and statuslines share one session cache. The
# override is a deterministic-test seam only: Bats points it at project scratch
# so fake OpenRouter catalogues never write fixture data outside the repository.
context_cache_dir="${DAAF_CONTEXT_BAR_CACHE_DIR:-/tmp}"
if [[ "${ANTHROPIC_BASE_URL:-}" == *openrouter.ai* ]]; then
    # model_id already extracted in the consolidated jq pass above
    # (byte-identical to the old `.model.id // empty`).
    or_cache="${context_cache_dir}/claude-or-models-${session_id}"

    if [[ -n "$model_id" && ! -s "$or_cache" ]]; then
        # Fetch models list once per session (3s timeout to avoid blocking statusline).
        # Write to a temp file first and move atomically to prevent truncated JSON
        # from a mid-download timeout from poisoning the cache for the entire session.
        or_tmp="${or_cache}.tmp"
        if curl -sf --connect-timeout 3 --max-time 3 \
            "https://openrouter.ai/api/v1/models" > "$or_tmp" 2>/dev/null; then
            mv "$or_tmp" "$or_cache" 2>/dev/null
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
if [[ -n "$model_id" && "$or_context_resolved" -eq 0 && "$max_context" -eq 200000 ]]; then
    # Physical-family classification operates on the terminal provider-stripped
    # slug only. Supported flagship versions must begin the slug and be followed
    # by end-of-slug, '-' or '['; this rejects notgpt-5.6 and gpt-5.60 while
    # retaining provider prefixes and established hyphen/[1m] variants.
    physical_slug="${model_id##*/}"
    case "$model_id" in
        z-ai/glm-5.2|z-ai/glm-5.2-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
            max_context=1048576 ;;
        *)
            case "$physical_slug" in
                gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*)
                    case "$physical_slug" in
                        *-mini*) max_context=400000 ;;
                        *-chat*) max_context=128000 ;;
                        *) max_context=1050000 ;;
                    esac
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
# gpt-5.4/5.5/5.6 flagship arm used by the static map above (mini/chat variants
# are excluded by the arm's ordering). Probe 2026-07-16 (gpt-5.6-sol) accepted
# 369,941 real input tokens and rejected 372,905; 370000 is therefore the
# lane-wide accounting ceiling for this mapped flagship family. Apply min() only
# after every ordinary resolution source, including an incoming [1m] payload and
# CLAUDE_CODE_MAX_CONTEXT_TOKENS, so neither can raise the matched lane above the
# backend ceiling while an explicitly lower positive value remains lower.
#
# This controls DAAF's denominator, statusline, and downstream severity guidance.
# It is NOT compaction and is NOT a transport-level request blocker; the backend
# remains the ultimate hard ceiling. Exact equality keeps malformed/noncanonical
# lane values fail-open, while API/OpenRouter routes retain their wider windows.
gpt_flagship=0
physical_slug="${model_id##*/}"
case "$physical_slug" in
    gpt-5*-mini*|gpt-5*-chat*) ;;
    gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*)
        gpt_flagship=1 ;;
esac
if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
      "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
      "$gpt_flagship" -eq 1 && "$max_context" -gt 370000 ]]; then
    max_context=370000
fi

max_k=$((max_context / 1000))

# Share context window size with hooks (which don't receive it in their input payload)
echo "$max_context" > "${context_cache_dir}/claude-ctx-window-${session_id}" 2>/dev/null

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
    ' < "$transcript_path")

    # 20k baseline: conservative default estimate for system prompt, tools, memory,
    # skills, env block, XML framing, and other dynamic context
    baseline=20000
    bar_width=10

    if [[ "$context_length" -gt 0 ]]; then
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
# Detect a GPT/shim model from either the id or the display name (belt-and-braces:
# some payloads carry the slug only in display_name).
case "${model_id}${model_name}" in
    *gpt-*|*GPT-*) gpt_model=1 ;;
esac

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

# Build output: Model (effort) | Dir | Branch | Context [| Plan usage]
output="${C_ACCENT}${model_disp}${C_GRAY} | 📁${dir}"
[[ -n "$branch" ]] && output+=" | 🔀${branch}"
output+=" | ${ctx}${C_RESET}"
output+="${rl_seg}"

printf '%b\n' "$output"

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
            gsub("\n"; " ") | gsub("  +"; " ")) |
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