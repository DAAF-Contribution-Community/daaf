#!/usr/bin/env bash
# subagent-bar.sh — Claude Code subagentStatusLine renderer
#
# Customizes the body text of each row in Claude Code's agent panel, showing
# per-subagent context utilization colored by DAAF's Context Quality Curve
# (CLAUDE.md § Context Quality Curve; mirrors the severity logic in
# .claude/hooks/context-reporter.sh).
#
# Verified against: Claude Code 2.1.187 — schema confirmed BOTH from the
# installed binary's payload construction AND a live captured payload
# (2026-07-05 session). See research/2026-07-05_FrameworkDev_StatuslineUpgrade.
#
# INPUT CONTRACT (stdin, JSON — live-verified):
#   Top level: session_id, transcript_path (main session's), cwd, columns,
#   tasks[]. Each task:
#     id           — task/subagent id (row key; also matches the subagent
#                    transcript basename agent-<id>.jsonl)
#     type         — task discriminant ("local_agent" for Agent-tool dispatches,
#                    also "local_bash", "local_workflow", "remote_agent", ...)
#     name         — registered display name; ABSENT for anonymous Agent-tool
#                    dispatches (the common DAAF case)
#     status       — "running" / "pending" / "stopped" / "killed" / "failed"
#     description  — dispatch description (capped 1000 chars)
#     label        — computed label (progress summary for local_agent, else
#                    falls back to description)
#     startTime    — ms epoch
#     tokenCount   — subagent's context token count (0 until first progress)
#     tokenSamples — rolling number[] window
#     cwd          — task cwd
#   The DAAF agent type (e.g. "search-agent") is NOT in the payload; it lives
#   in the sidecar $(dirname transcript_path)/<session_id>/subagents/
#   agent-<id>.meta.json (key: agentType) and is looked up per row, fail-open.
#   The subagent's MODEL is also not in the payload; it is read from the last
#   assistant entry of agent-<id>.jsonl (same technique as context-reporter.sh
#   cache_model()), cached once per subagent in
#   /tmp/claude-subagent-model-<session>-<id> (shared with
#   context-reporter.sh), and drives the per-row window denominator (see the
#   loop; CLAUDE_CODE_MAX_CONTEXT_TOKENS, when set to an integer, overrides
#   the per-model mapping there).
#
# OUTPUT CONTRACT (stdout — binary-verified Zod schema {id, content}):
#   One compact JSON line per task: {"id": "<task id>", "content": "<row body>"}
#   The content REPLACES the entire native row body ("name · description ·
#   tokenCount"); the leading spinner glyph stays native. Emitting nothing for
#   an id keeps the native rendering — that is this script's failure mode.
#   ANSI colors are supported inside content.
#
# FIELD-JOINING NOTE (the bug this design prevents): fields are joined with
# the ASCII unit separator \x1f, NOT tabs. Tab is IFS *whitespace* in bash, so
# consecutive tabs collapse and empty fields (like the absent `name`) silently
# shift every later field left — that is exactly the failure observed live
# (tokenCount landing in `status`, bar stuck at 0%). A non-whitespace IFS
# preserves empty fields.
#
# FAIL-OPEN DESIGN:
#   set -u only (NO set -e): statusline-family scripts must never block Claude
#   Code. Every error path exits 0; errors are suppressed with 2>/dev/null.

set -u

# --- Color codes ---
C_RESET='\033[0m'
C_GRAY='\033[38;5;245m'
C_BAR_EMPTY='\033[38;5;238m'
# Severity palette aligned to the Context Quality Curve. The exact numeric
# thresholds are model-family conditional (see the per-row severity block near
# the bottom of the loop): Fable/Mythos rows use the permissive family
# (ELEVATED >= 30% OR >= 300k, HIGH >= 40% OR >= 400k, CRITICAL >= 50% OR >=
# 500k); every other model — Opus (incl. opus-4-8[1m]), Sonnet, unknown — uses
# the conservative family (ELEVATED >= 40% OR >= 150k, HIGH >= 60% OR >= 200k,
# CRITICAL >= 75% OR >= 250k). Each severity keeps one color regardless of
# family:
#   NOMINAL  green
#   ELEVATED amber
#   HIGH     orange  (bold to distinguish from amber)
#   CRITICAL red
C_NOMINAL='\033[38;5;71m'    # green
C_ELEVATED='\033[38;5;179m'  # amber
C_HIGH='\033[1;38;5;173m'    # orange, bold
C_CRITICAL='\033[38;5;167m'  # red

# --- Read input ---
input=$(cat 2>/dev/null) || exit 0
[[ -z "$input" ]] && exit 0

# --- Top-level fields (single jq pass, \x1f-joined; see FIELD-JOINING NOTE) ---
IFS=$'\x1f' read -r session_id transcript_path < <(printf '%s' "$input" | jq -r '
    [ (.session_id // ""), (.transcript_path // "") ]
    | map(tostring) | join("\u001f")
' 2>/dev/null) || { session_id=""; transcript_path=""; }
session_id="${session_id:-}"
transcript_path="${transcript_path:-}"

# Sidecar directory holding agent-<id>.meta.json (agentType lookup source).
subagents_dir=""
if [[ -n "$transcript_path" && -n "$session_id" ]]; then
    subagents_dir="$(dirname "$transcript_path" 2>/dev/null)/${session_id}/subagents"
fi

# --- Resolve context window size (read-only shared cache) ---
# Same fallback chain as context-reporter.sh (lines ~91-100): session-specific
# cache written by context-bar.sh, else the most recent cache from any session,
# else 200000. This script NEVER writes the cache.
max_context=""
if [[ -n "$session_id" && -f "/tmp/claude-ctx-window-${session_id}" ]]; then
    max_context=$(cat "/tmp/claude-ctx-window-${session_id}" 2>/dev/null)
fi
if [[ -z "$max_context" ]]; then
    latest_ctx=$(ls -t /tmp/claude-ctx-window-* 2>/dev/null | head -1)
    if [[ -n "${latest_ctx:-}" ]]; then
        max_context=$(cat "$latest_ctx" 2>/dev/null)
    fi
fi
# Guard: must be a positive integer, else fall back to 200k.
if ! [[ "$max_context" =~ ^[0-9]+$ ]] || [[ "$max_context" -le 0 ]]; then
    max_context=200000
fi

# Session model (cached by context-reporter.sh) — used to decide whether a
# subagent shares the session's window or needs the per-model mapping below.
session_model=""
if [[ -n "$session_id" ]]; then
    session_model=$(cat "/tmp/claude-model-${session_id}" 2>/dev/null)
fi

# --- Extract tasks (single jq pass, one \x1f-joined record per line) ---
# Fields: id, type, name, status, tokenCount, label. Tasks with an empty id
# are dropped (they cannot be keyed in the output). label/name are sanitized
# of newlines/tabs/\x1f so one task always stays one record line.
tasks_rec=$(printf '%s' "$input" | jq -r '
    def clean: tostring | gsub("[\n\r\t]"; " ");
    (.tasks // [])[]
    | select((.id // "") != "")
    | [ (.id // "" | clean),
        (.type // "" | clean),
        (.name // "" | clean),
        (.status // "" | clean),
        ((.tokenCount // 0) | tostring),
        ((.label // .description // "") | clean) ]
    | join("\u001f")
' 2>/dev/null) || exit 0

[[ -z "$tasks_rec" ]] && exit 0

# --- Render one output line per task ---
bar_width=5
while IFS=$'\x1f' read -r id type name status tokens label; do
    [[ -z "$id" ]] && continue

    # Normalize token count to a non-negative integer (strip any fraction).
    tokens=${tokens%.*}
    [[ "$tokens" =~ ^[0-9]+$ ]] || tokens=0

    # Per-row context window: a subagent on a different model than the session
    # gets a different window than the session's (e.g. a sonnet subagent
    # dispatched from a 1M fable session is provisioned 200k — its bar must
    # not be computed against 1M). Model read from the last assistant entry of
    # the subagent transcript (same source as context-reporter.sh cache_model())
    # and cached in /tmp/claude-subagent-model-<session>-<id> — a model never
    # changes mid-task, so the tail|jq runs once per subagent, not once per
    # ~300ms panel refresh. context-reporter.sh shares this cache (either
    # script may write it first; cache is written only on a successful read).
    task_model=""
    model_cache=""
    [[ -n "$session_id" ]] && model_cache="/tmp/claude-subagent-model-${session_id}-${id}"
    if [[ -n "$model_cache" && -f "$model_cache" ]]; then
        task_model=$(cat "$model_cache" 2>/dev/null)
    elif [[ -n "$subagents_dir" && -f "${subagents_dir}/agent-${id}.jsonl" ]]; then
        task_model=$(tail -n 50 "${subagents_dir}/agent-${id}.jsonl" 2>/dev/null | \
            jq -rs '[.[] | .message.model // empty] | last // empty' 2>/dev/null)
        [[ -n "$task_model" && -n "$model_cache" ]] && \
            echo "$task_model" > "$model_cache" 2>/dev/null
    fi
    # Default: the session window (covers same-model subagents and alternative
    # providers, where the mapping below does not apply).
    row_window="$max_context"
    if [[ -n "$task_model" && "$task_model" != "$session_model" ]]; then
        # Window provisioning: [1m]-suffixed and natively-1M models (fable-5,
        # mythos-5, opus-4-7, opus-4-8) get 1,000,000; ALL others 200,000.
        # Mapping verified against installed CC 2.1.187 binary, 2026-07-05;
        # re-verify after Claude Code upgrades.
        case "$task_model" in
            *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*\[1m\]*) row_window=1000000 ;;
            # GPT (OpenAI) windows, ordered most-specific first: mini/chat
            # variants are smaller than the gpt-5.4/5.5/5.6 flagships, so they must
            # precede the broad matches. Verified vs OpenRouter /api/v1/models
            # 2026-07-09. Keep aligned with context-bar.sh + context-reporter.sh.
            *gpt-5*-mini*) row_window=400000 ;;
            *gpt-5*-chat*) row_window=128000 ;;
            *gpt-5.4*|*gpt-5.5*|*gpt-5.6*) row_window=1050000 ;;
            *gpt-5*) row_window=400000 ;;
            *) row_window=200000 ;;
        esac
        # CLAUDE_CODE_MAX_CONTEXT_TOKENS overrides provisioning when set.
        if [[ "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}" =~ ^[0-9]+$ ]]; then
            row_window="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
        fi
    fi
    # Guard: must be a positive integer, else fall back to 200k.
    if ! [[ "$row_window" =~ ^[0-9]+$ ]] || [[ "$row_window" -le 0 ]]; then
        row_window=200000
    fi

    pct=$((tokens * 100 / row_window))
    [[ $pct -gt 100 ]] && pct=100
    used_k=$((tokens / 1000))

    # Threshold family (percentage AND absolute k-token gates per severity),
    # keyed on THIS row's model. Fable/Mythos get the permissive family;
    # everything else — INCLUDING opus-4-8[1m], whose 1M window does NOT relax
    # its Opus-class quality horizon — gets the conservative family. Match ONLY
    # *fable-5*/*mythos-5* (NOT [1m], NOT opus); unknown/empty falls through to
    # the conservative default (fail-conservative). Deliberately different from
    # the window-size case block above (which also matches opus and [1m]) —
    # family and window size are separate lookups.
    case "$task_model" in
        *fable-5*|*mythos-5*)
            elev_pct=30; high_pct=40; crit_pct=50
            elev_k=300;  high_k=400;  crit_k=500 ;;
        *)
            elev_pct=40; high_pct=60; crit_pct=75
            elev_k=150;  high_k=200;  crit_k=250 ;;
    esac

    # Severity via dual thresholds (percentage OR absolute k-tokens, whichever
    # fires first) — identical logic to context-reporter.sh calculate().
    if   [[ $pct -ge $crit_pct ]] || [[ $used_k -ge $crit_k ]]; then color="$C_CRITICAL"
    elif [[ $pct -ge $high_pct ]] || [[ $used_k -ge $high_k ]]; then color="$C_HIGH"
    elif [[ $pct -ge $elev_pct ]] || [[ $used_k -ge $elev_k ]]; then color="$C_ELEVATED"
    else                                                            color="$C_NOMINAL"
    fi

    # Mini context bar: fill segments proportional to pct across bar_width.
    filled=$((pct * bar_width / 100))
    [[ $filled -gt $bar_width ]] && filled=$bar_width
    bar=""
    for ((i=0; i<bar_width; i++)); do
        if [[ $i -lt $filled ]]; then
            bar+="${color}█${C_RESET}"
        else
            bar+="${C_BAR_EMPTY}░${C_RESET}"
        fi
    done

    # Compact token label: show as Nk once >= 1000 tokens, else the raw count.
    if [[ $tokens -ge 1000 ]]; then
        tok_label="${used_k}k"
    else
        tok_label="${tokens}"
    fi

    # Agent identity: the DAAF agent type from the meta.json sidecar is the
    # most informative ("search-agent" beats the generic "local_agent");
    # fall back to registered name, then task type, then "agent".
    agent_disp=""
    if [[ -n "$subagents_dir" && -f "${subagents_dir}/agent-${id}.meta.json" ]]; then
        agent_disp=$(jq -r '.agentType // empty' \
            "${subagents_dir}/agent-${id}.meta.json" 2>/dev/null)
    fi
    [[ -z "$agent_disp" ]] && agent_disp="$name"
    [[ -z "$agent_disp" ]] && agent_disp="$type"
    [[ -z "$agent_disp" ]] && agent_disp="agent"
    # Append the subagent's model (claude- prefix stripped for compactness),
    # e.g. "search-agent (sonnet-4-6)".
    [[ -n "$task_model" ]] && agent_disp+=" (${task_model#claude-})"

    # Dispatch description, truncated to keep the row compact.
    desc="$label"
    if [[ ${#desc} -gt 40 ]]; then
        desc="${desc:0:39}…"
    fi

    # Assemble the row body (this REPLACES the native row, so identity and
    # description belong to us). Status shown only when it isn't the default
    # "running" — the native spinner already conveys running.
    content="${color}${agent_disp}${C_RESET}"
    [[ -n "$desc" ]] && content+="${C_GRAY} · ${desc}${C_RESET}"
    content+="${C_GRAY} ·${C_RESET} ${color}${tok_label}${C_RESET} ${bar} ${color}${pct}%${C_RESET}"
    if [[ -n "$status" && "$status" != "running" ]]; then
        content+="${C_GRAY} [${status}]${C_RESET}"
    fi

    # Emit {"id","content"} as ONE compact JSON line. ANSI codes are
    # materialized via printf %b, then JSON-encoded through jq (-R raw,
    # -s slurp, -c compact) so quotes/escapes/ESC bytes are handled safely.
    rendered=$(printf '%b' "$content")
    printf '%s' "$rendered" | jq -Rsc --arg id "$id" '{id: $id, content: .}' 2>/dev/null
done <<< "$tasks_rec"

exit 0
