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
if ! [[ "$max_context" =~ ^[0-9]+$ ]] || [[ "$max_context" -le 0 ]]; then
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
# get the actual context_length for the current model.
if [[ "${ANTHROPIC_BASE_URL:-}" == *openrouter.ai* ]]; then
    # model_id already extracted in the consolidated jq pass above
    # (byte-identical to the old `.model.id // empty`).
    or_cache="/tmp/claude-or-models-${session_id}"

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
        if [[ -n "$or_context" && "$or_context" -gt 0 ]]; then
            max_context="$or_context"
        fi
    fi
fi

max_k=$((max_context / 1000))

# Share context window size with hooks (which don't receive it in their input payload)
echo "$max_context" > "/tmp/claude-ctx-window-${session_id}" 2>/dev/null

# Calculate context bar from transcript
if [[ -n "$transcript_path" && -f "$transcript_path" ]]; then
    context_length=$(jq -s '
        map(select(.message.usage and .isSidechain != true and .isApiErrorMessage != true)) |
        last |
        if . then
            (.message.usage.input_tokens // 0) +
            (.message.usage.cache_read_input_tokens // 0) +
            (.message.usage.cache_creation_input_tokens // 0)
        else 0 end
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
model_disp="$model"
[[ -n "$effort_level" ]] && model_disp="${model} (${effort_level})"

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