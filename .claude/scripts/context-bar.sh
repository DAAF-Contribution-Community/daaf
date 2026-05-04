#!/bin/bash

# Color theme: gray, orange, blue, teal, green, lavender, rose, gold, slate, cyan
# Preview colors with: bash scripts/color-preview.sh
COLOR="blue"

# Color codes
C_RESET='\033[0m'
C_GRAY='\033[38;5;245m'  # explicit gray for default text
C_BAR_EMPTY='\033[38;5;238m'
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

# Extract model, directory, and cwd
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "?"')
cwd=$(echo "$input" | jq -r '.cwd // empty')
dir=$(basename "$cwd" 2>/dev/null || echo "?")

# Get git branch only (skip expensive status/sync checks)
branch=""
if [[ -n "$cwd" && -d "$cwd" ]]; then
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
fi

# Get transcript path for context calculation and last message feature
transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

# Get context window size from JSON, but override for OpenRouter models where
# Claude Code reports a hardcoded 200k default regardless of actual model.
# Calculate tokens from transcript (more accurate than total_input_tokens which
# excludes system prompt/tools/memory).
# See: github.com/anthropics/claude-code/issues/13652
max_context=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')

session_id=$(echo "$input" | jq -r '.session_id // "default"')

# OpenRouter context window override: Claude Code doesn't know the real context
# window size for third-party models accessed via OpenRouter, so it reports a
# hardcoded 200k default. Query the OpenRouter models API once per session to
# get the actual context_length for the current model.
if [[ "${ANTHROPIC_BASE_URL:-}" == *openrouter.ai* ]]; then
    model_id=$(echo "$input" | jq -r '.model.id // empty')
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

    ctx="${bar} ${C_GRAY}${pct_prefix}${pct}% of ${max_k}k tokens (lower session context use enhances performance)"
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

    ctx="${bar} ${C_GRAY}~${pct}% of ${max_k}k tokens (lower session context use enhances performance)"
fi

# Build output: Model | Dir | Branch (uncommitted) | Context
output="${C_ACCENT}${model}${C_GRAY} | 📁${dir}"
[[ -n "$branch" ]] && output+=" | 🔀${branch}"
output+=" | ${ctx}${C_RESET}"

printf '%b\n' "$output"

# Get user's last message (text only, not tool results, skip unhelpful messages)
if [[ -n "$transcript_path" && -f "$transcript_path" ]]; then
    # Calculate visible length (without ANSI codes) - 10 chars for bar + content
    plain_output="${model} | 📁${dir}"
    [[ -n "$branch" ]] && plain_output+=" | 🔀${branch}"
    plain_output+=" | xxxxxxxxxx ${pct}% of ${max_k}k tokens (lower session context use enhances performance)"
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