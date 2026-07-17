#!/usr/bin/env bash
# context-reporter.sh — Multi-event context utilization & timestamp hook
#
# Injects context window utilization and a current timestamp into Claude's
# conversation so the model can make informed decisions about delegation, state
# persistence, and session recovery (see CLAUDE.md utilization gates — the
# thresholds are quality-tier conditional: Fable/Mythos use 30%/40%/50% OR
# 300k/400k/500k; exact GPT 5.6 Sol ids use 40%/60%/75% OR
# 300k/400k/500k; all other models use 40%/60%/75% OR 150k/200k/250k,
# whichever fires first; see calculate() below).
#
# Registered events:
#   UserPromptSubmit  — stdout text → injected as <user-prompt-submit-hook>
#   PreToolUse        — JSON additionalContext → injected before tool executes
#
# Rate limiting:
#   Both events share a single 60-second injection gate. The gate is
#   per-agent: the main session uses /tmp/claude-ctx-ts-<session_id>, while
#   subagent-fired calls use /tmp/claude-ctx-ts-<session_id>-<agent_id> so the
#   orchestrator and its subagents never suppress each other's injections.
#   Whichever event fires first resets the timer for that agent's gate. This
#   prevents redundant context injection across rapid tool calls and user
#   messages. The gate uses an epoch-timestamp cache file in /tmp.
#
# Performance:
#   Uses transcript byte-size + mtime signatures to reuse model caches without
#   rescanning unchanged files. Changed transcripts are resolved from `tail -50`,
#   which also bounds usage parsing to the end of the JSONL.
#
# Subagent support:
#   settings.json PreToolUse hooks also fire for tool calls made BY subagents.
#   In that case the hook's stdin JSON carries the PARENT's session_id and the
#   PARENT's main transcript_path, plus an `agent_id` field that is present
#   ONLY inside subagent calls. When agent_id is present, this script measures
#   the SUBAGENT's own transcript, located at:
#     <dirname(transcript_path)>/<session_id>/subagents/agent-<agent_id>.jsonl
#   Entries in subagent transcripts all carry isSidechain:true, so the
#   sidechain filter (used to isolate the main chain in the parent transcript)
#   is disabled when measuring a subagent's own transcript. Each subagent also
#   gets its own rate-limit gate file (see "Rate limiting" above), and its
#   utilization is computed against the window provisioned for ITS model, not
#   the session's (see the per-subagent window correction below).
#   Fail silent, never wrong: if the subagent's transcript cannot be located
#   or yields no usage data, the hook emits nothing. It NEVER falls back to
#   the parent transcript in the subagent branch — that would inject the
#   orchestrator's utilization into the subagent's context, causing subagents
#   to falsely throttle or refuse work at HIGH/CRITICAL.
#
# Threshold tier (see calculate()):
#   The severity thresholds are keyed on the model identity of the agent being
#   measured — main-session measurements use the session model; subagent
#   measurements use that subagent's own model. Fable/Mythos patterns get the
#   validated extended-horizon tier (30/40/50% OR 300/400/500k). The exact
#   terminal GPT slugs gpt-5.6-sol and gpt-5.6-sol[1m] use standard 40/60/75%
#   gates while retaining 300/400/500k absolute gates. Provider paths are
#   accepted only when one of those exact slugs is the final path segment. All
#   other models (Opus, Sonnet, other GPT variants, GLM, unknown/empty) get the
#   conservative tier (40/60/75% OR 150/200/250k). This is deliberately
#   separate from physical-window mapping: the broad GPT 5.6 family maps to a
#   1.05M physical window on API/OpenRouter routes, while the matched ChatGPT-
#   subscription/Codex lane is finally capped at 370k for accounting. Only exact
#   GPT 5.6 Sol slugs retain the larger absolute quality-horizon gates without
#   inheriting Fable/Mythos percentage gates. Likewise, claude-opus-4-8[1m] has
#   a 1M physical window but keeps the conservative tier.
#   If model resolution fails, the conservative tier applies (fail-conservative).
#
# Exit codes:
#   0 = success (stdout/JSON processed by Claude Code)
#   All error paths exit 0 to never block tool execution.

# -u: catch unset variable typos. Deliberately omit -e: this hook must
# never block tool execution — all error paths exit 0.
set -u

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

# Return a signature that changes when a transcript is appended or rewritten.
# GNU stat supplies byte size plus nanosecond-resolution mtime in one probe.
transcript_signature() {
    local transcript="${1:-}"
    [[ -n "$transcript" && -f "$transcript" ]] || return 1
    stat -c '%s:%y' -- "$transcript" 2>/dev/null
}

# Resolve the latest real model from a transcript while retaining the bare cache
# paths consumed by audit-log.sh and statusline components. The neighboring
# .transcript-signature sidecar is the commit marker: unchanged signatures reuse
# a nonempty bare cache without parsing; changed signatures refresh from the last
# nonempty, non-synthetic model. Both files are replaced through same-directory
# temporary siblings, with the signature moved last so interrupted writes force
# a safe refresh on the next invocation.
resolve_model_cache() {
    local transcript="${1:-}"
    local cache="${2:-}"
    local signature_cache="${cache}.transcript-signature"
    local signature="" cached_signature="" cached_model="" model=""
    local model_tmp="${cache}.tmp.$$" signature_tmp="${signature_cache}.tmp.$$"

    [[ -n "$cache" ]] || return 0
    [[ -s "$cache" ]] && cached_model=$(cat "$cache" 2>/dev/null)
    signature=$(transcript_signature "$transcript") || signature=""
    [[ -s "$signature_cache" ]] && cached_signature=$(cat "$signature_cache" 2>/dev/null)

    if [[ -n "$cached_model" && -n "$signature" && "$cached_signature" == "$signature" ]]; then
        printf '%s' "$cached_model"
        return 0
    fi

    if [[ -n "$transcript" && -f "$transcript" ]]; then
        model=$(tail -n 50 "$transcript" 2>/dev/null | jq -rs '
            [.[] | (.message.model // empty)
             | select(. != "" and . != "<synthetic>")] | last // empty
        ' 2>/dev/null) || model=""
    fi
    [[ -z "$model" ]] && model="$cached_model"

    if [[ -n "$model" && -n "$signature" ]]; then
        if printf '%s' "$model" > "$model_tmp" 2>/dev/null &&
           printf '%s' "$signature" > "$signature_tmp" 2>/dev/null &&
           mv "$model_tmp" "$cache" 2>/dev/null &&
           mv "$signature_tmp" "$signature_cache" 2>/dev/null; then
            :
        else
            rm -f "$model_tmp" "$signature_tmp" 2>/dev/null
        fi
    fi

    [[ -n "$model" ]] && printf '%s' "$model"
}

INPUT=$(cat)
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null) || HOOK_EVENT=""
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"' 2>/dev/null) || SESSION_ID="default"
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null) || TRANSCRIPT_PATH=""
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty' 2>/dev/null) || AGENT_ID=""

# ---------------------------------------------------------------------------
# Agent-aware measurement setup: decide WHICH transcript to measure, whether
# the sidechain filter applies, and which rate-limit gate file to use.
# ---------------------------------------------------------------------------
if [[ -n "$AGENT_ID" ]]; then
    # Subagent-fired call: measure the subagent's OWN transcript.
    [[ -z "$TRANSCRIPT_PATH" ]] && exit 0
    if [[ "$(basename "$TRANSCRIPT_PATH")" == "agent-${AGENT_ID}.jsonl" ]]; then
        # Robustness for future Claude Code versions that may pass the
        # subagent's transcript path directly.
        MEASURE_TRANSCRIPT="$TRANSCRIPT_PATH"
    else
        MEASURE_TRANSCRIPT="$(dirname "$TRANSCRIPT_PATH")/${SESSION_ID}/subagents/agent-${AGENT_ID}.jsonl"
    fi
    # Fail silent, never wrong: no fallback to the parent transcript here.
    [[ ! -f "$MEASURE_TRANSCRIPT" ]] && exit 0
    # Subagent transcripts are entirely isSidechain:true — disable the filter.
    ALLOW_SIDECHAIN=true
    # Per-agent gate so parent and subagents don't race on a shared timer.
    LAST_INJECT_FILE="/tmp/claude-ctx-ts-${SESSION_ID}-${AGENT_ID}"
else
    # Main session: measure the parent transcript's main chain only.
    [[ -z "$TRANSCRIPT_PATH" ]] && exit 0
    MEASURE_TRANSCRIPT="$TRANSCRIPT_PATH"
    ALLOW_SIDECHAIN=false
    LAST_INJECT_FILE="/tmp/claude-ctx-ts-${SESSION_ID}"
fi

INJECT_INTERVAL=60  # seconds between injections

# Read context window size from shared cache (written by context-bar.sh
# statusline). Subagent-fired hook calls carry the PARENT's session_id, so
# this resolves the SESSION's window; a subagent running on a different model
# than the session is corrected below. If the cache is absent, fall back to
# the most recent cache from any session, then to 200k as a last resort.
CTX_CACHE="/tmp/claude-ctx-window-${SESSION_ID}"
MAX_CONTEXT=""
if [[ -f "$CTX_CACHE" ]]; then
    MAX_CONTEXT=$(cat "$CTX_CACHE" 2>/dev/null)
else
    LATEST_CTX=$(ls -t /tmp/claude-ctx-window-* 2>/dev/null | head -1)
    if [[ -n "${LATEST_CTX:-}" ]]; then
        MAX_CONTEXT=$(cat "$LATEST_CTX" 2>/dev/null)
    fi
fi
MAX_CONTEXT=${MAX_CONTEXT:-200000}
if ! is_canonical_positive_decimal "$MAX_CONTEXT"; then
    MAX_CONTEXT=200000
fi

# Refresh model identity before same/different-model window selection, final-cap
# selection, and quality-tier selection. The main and subagent consumers share
# these bare cache paths and their synchronized .transcript-signature sidecars.
SESSION_MODEL=$(resolve_model_cache "$TRANSCRIPT_PATH" "/tmp/claude-model-${SESSION_ID}")
AGENT_MODEL=""
if [[ -n "$AGENT_ID" ]]; then
    AGENT_MODEL_CACHE="/tmp/claude-subagent-model-${SESSION_ID}-${AGENT_ID}"
    AGENT_MODEL=$(resolve_model_cache "$MEASURE_TRANSCRIPT" "$AGENT_MODEL_CACHE")
    MEASURE_MODEL="$AGENT_MODEL"
else
    MEASURE_MODEL="$SESSION_MODEL"
fi

# Per-subagent window correction: a subagent on a DIFFERENT model than the
# session gets the window Claude Code provisions for ITS model, not the
# session's (e.g. a sonnet subagent inside a 1M fable session has 200k — its
# severity must be computed against 200k, or HIGH/CRITICAL fire far too late).
# Physical GPT classification uses the terminal provider-stripped slug. Valid
# flagship versions begin that slug and are followed by end-of-slug, '-' or '[';
# mini/chat retain precedence. Physical size remains independent of quality tier.
if [[ -n "$AGENT_ID" && -n "$AGENT_MODEL" && "$AGENT_MODEL" != "$SESSION_MODEL" ]]; then
    PHYSICAL_SLUG="${AGENT_MODEL##*/}"
    case "$AGENT_MODEL" in
        # Exact GLM-5.2 plus terminal date snapshots only. Keep this narrow:
        # glm-5.2-air and future variants have no verified static window.
        z-ai/glm-5.2|z-ai/glm-5.2-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
            MAX_CONTEXT=1048576 ;;
        *)
            case "$PHYSICAL_SLUG" in
                gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*)
                    case "$PHYSICAL_SLUG" in
                        *-mini*) MAX_CONTEXT=400000 ;;
                        *-chat*) MAX_CONTEXT=128000 ;;
                        *) MAX_CONTEXT=1050000 ;;
                    esac
                    ;;
                gpt-5|gpt-5[-\[]*|gpt-5.2|gpt-5.2[-\[]*)
                    case "$PHYSICAL_SLUG" in
                        *-chat*) MAX_CONTEXT=128000 ;;
                        *) MAX_CONTEXT=400000 ;;
                    esac
                    ;;
                *)
                    case "$AGENT_MODEL" in
                        *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*\[1m\]*)
                            MAX_CONTEXT=1000000 ;;
                        *) MAX_CONTEXT=200000 ;;
                    esac
                    ;;
            esac
            ;;
    esac
fi

# CLAUDE_CODE_MAX_CONTEXT_TOKENS is the ordinary user override. Apply it to
# every measurement path before the backend-specific final constraint below.
if is_canonical_positive_decimal "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}"; then
    MAX_CONTEXT="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
fi

# ChatGPT-subscription/Codex final physical-window accounting constraint.
# Canonical activation requires BOTH exact lane signals and a measured model in
# the anchored gpt-5.4/5.5/5.6 flagship arm; mini/chat variants are excluded by
# ordering. Probe 2026-07-16 (gpt-5.6-sol) accepted 369,941 real input tokens and
# rejected 372,905, so 370000 is the lane-wide accounting ceiling for this arm.
# Applying min(resolved, 370000) after model/cache/override resolution prevents
# stale or unsafe ordinary values from surviving while preserving lower valid
# values. This is accounting, not compaction or a transport-level blocker.
GPT_FLAGSHIP=0
PHYSICAL_SLUG="${MEASURE_MODEL##*/}"
case "$PHYSICAL_SLUG" in
    gpt-5*-mini*|gpt-5*-chat*) ;;
    gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*)
        GPT_FLAGSHIP=1 ;;
esac
if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
      "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
      "$GPT_FLAGSHIP" -eq 1 ]] && \
   is_canonical_positive_decimal "$MAX_CONTEXT" && \
   [[ "$MAX_CONTEXT" -gt 370000 ]]; then
    MAX_CONTEXT=370000
fi

# Final denominator guard before arithmetic.
if ! is_canonical_positive_decimal "$MAX_CONTEXT"; then
    MAX_CONTEXT=200000
fi
MAX_K=$((MAX_CONTEXT / 1000))

# ---------------------------------------------------------------------------
# calculate: Parse the transcript's most recent usage data and format a
# utilization message with timestamp. Uses tail -50 to avoid parsing the
# entire JSONL file.
# Args: $1 = transcript path, $2 = allow_sidechain (true/false). When true,
# sidechain entries count; when false, only main-chain entries count.
# $3 = model id of the agent being measured (drives the threshold tier; may
# be empty → conservative tier).
# Outputs a single line to stdout, or nothing if data is unavailable.
# ---------------------------------------------------------------------------
calculate() {
    local transcript="$1"
    local allow_sidechain="$2"
    local model="$3"
    [[ -z "$transcript" || ! -f "$transcript" ]] && return

    local tokens
    # Map each qualifying usage entry to its token sum, then take the last
    # POSITIVE sum. Shim-routed transcripts can end with zero-token streaming
    # placeholders; native Claude transcripts are unchanged by last-positive.
    tokens=$(tail -50 "$transcript" 2>/dev/null | jq -s --argjson allow_sidechain "$allow_sidechain" '
        [.[] | select(
            .message.usage and
            ((.isSidechain != true) or $allow_sidechain) and
            .isApiErrorMessage != true
        ) | (
            (.message.usage.input_tokens // 0) +
            (.message.usage.cache_read_input_tokens // 0) +
            (.message.usage.cache_creation_input_tokens // 0)
        )] | map(select(. > 0)) | last // 0
    ' 2>/dev/null) || tokens=0

    [[ "$tokens" -le 0 ]] && return

    local pct=$((tokens * 100 / MAX_CONTEXT))
    [[ $pct -gt 100 ]] && pct=100
    local used_k=$((tokens / 1000))

    # Quality-tier matching deliberately remains narrower than physical-family
    # matching. Fable/Mythos keep the validated extended-horizon percentage and
    # absolute gates; exact terminal Sol slugs use standard percentage gates
    # while retaining the larger absolute gates.
    local elev_pct high_pct crit_pct elev_k high_k crit_k
    case "$model" in
        *fable-5*|*mythos-5*)
            elev_pct=30; high_pct=40; crit_pct=50
            elev_k=300;  high_k=400;  crit_k=500 ;;
        gpt-5.6-sol|*/gpt-5.6-sol|gpt-5.6-sol\[1m\]|*/gpt-5.6-sol\[1m\])
            elev_pct=40; high_pct=60; crit_pct=75
            elev_k=300;  high_k=400;  crit_k=500 ;;
        *)
            elev_pct=40; high_pct=60; crit_pct=75
            elev_k=150;  high_k=200;  crit_k=250 ;;
    esac

    local severity
    if   [[ $pct -ge $crit_pct ]] || [[ $used_k -ge $crit_k ]]; then severity="CRITICAL"
    elif [[ $pct -ge $high_pct ]] || [[ $used_k -ge $high_k ]]; then severity="HIGH"
    elif [[ $pct -ge $elev_pct ]] || [[ $used_k -ge $elev_k ]]; then severity="ELEVATED"
    else                                                             severity="NOMINAL"
    fi

    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S %Z')

    echo "Context utilization [${severity}]: ${used_k}k / ${MAX_K}k tokens (${pct}%) | ${ts}"
}

# ---------------------------------------------------------------------------
# Shared rate-limit check (used by both events)
# ---------------------------------------------------------------------------
NOW=$(date +%s)
LAST_INJECT=0
[[ -f "$LAST_INJECT_FILE" ]] && LAST_INJECT=$(cat "$LAST_INJECT_FILE" 2>/dev/null)

if [[ $((NOW - LAST_INJECT)) -lt $INJECT_INTERVAL ]]; then
    # Interval not elapsed — skip injection, don't block
    exit 0
fi

# Interval elapsed — calculate and emit
MSG=$(calculate "$MEASURE_TRANSCRIPT" "$ALLOW_SIDECHAIN" "$MEASURE_MODEL")
[[ -z "${MSG:-}" ]] && exit 0

# Update the per-agent timestamp gate
printf '%s' "$NOW" > "$LAST_INJECT_FILE" 2>/dev/null

# ---------------------------------------------------------------------------
# Event dispatch (format differs per event, but both share the gate above)
# ---------------------------------------------------------------------------
case "$HOOK_EVENT" in
    UserPromptSubmit)
        echo "$MSG"
        ;;
    PreToolUse)
        jq -n --arg ctx "$MSG" '{
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                additionalContext: $ctx
            }
        }'
        ;;
    *)
        # Unknown event — do nothing, don't block
        ;;
esac

exit 0
