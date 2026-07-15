#!/usr/bin/env bash
# context-reporter.sh — Multi-event context utilization & timestamp hook
#
# Injects context window utilization and a current timestamp into Claude's
# conversation so the model can make informed decisions about delegation, state
# persistence, and session recovery (see CLAUDE.md utilization gates — the
# thresholds are model-family conditional: Fable/Mythos use 30%/40%/50% OR
# 300k/400k/500k, everything else uses 40%/60%/75% OR 150k/200k/250k, whichever
# fires first; see the calculate() threshold table below).
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
#   Uses `tail -50` to read only the end of the transcript, avoiding full-file
#   parsing. The last usage entry is always near the end of the JSONL.
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
# Threshold family (see calculate()):
#   The severity thresholds are keyed on the model FAMILY of the agent being
#   measured — main-session measurements use the session model; subagent
#   measurements use that subagent's own model. Fable/Mythos models get the
#   permissive family (30/40/50% OR 300/400/500k); everything else (Opus,
#   Sonnet, unknown/empty) gets the conservative family (40/60/75% OR
#   150/200/250k). This is DELIBERATELY separate from the window-size mapping:
#   claude-opus-4-8[1m] has a 1M *window* but an Opus-class *quality horizon*,
#   so it keeps the conservative thresholds even though it gets the 1M window.
#   The model used here is resolved into MEASURE_MODEL below; if it is
#   empty/unresolved the conservative family applies (fail-conservative).
#
# Exit codes:
#   0 = success (stdout/JSON processed by Claude Code)
#   All error paths exit 0 to never block tool execution.

# -u: catch unset variable typos. Deliberately omit -e: this hook must
# never block tool execution — all error paths exit 0.
set -u

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
    # Empty transcript_path = malformed payload; exit explicitly (mirroring the
    # subagent branch's guard above) instead of relying on the downstream -f
    # guard in calculate() and the empty-MSG exit to absorb it.
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
if [[ -f "$CTX_CACHE" ]]; then
    MAX_CONTEXT=$(cat "$CTX_CACHE" 2>/dev/null)
else
    LATEST_CTX=$(ls -t /tmp/claude-ctx-window-* 2>/dev/null | head -1)
    if [[ -n "${LATEST_CTX:-}" ]]; then
        MAX_CONTEXT=$(cat "$LATEST_CTX" 2>/dev/null)
    fi
fi
MAX_CONTEXT=${MAX_CONTEXT:-200000}

# Per-subagent window correction: a subagent on a DIFFERENT model than the
# session gets the window Claude Code provisions for ITS model, not the
# session's (e.g. a sonnet subagent inside a 1M fable session has 200k — its
# severity must be computed against 200k, or HIGH/CRITICAL fire far too late).
# The subagent's model is read once from its own transcript and cached in
# /tmp/claude-subagent-model-<session>-<agent> (a model never changes
# mid-task; subagent-bar.sh shares this cache). Window mapping: [1m]-suffixed
# and natively-1M models (fable-5, mythos-5, opus-4-7, opus-4-8) → 1,000,000;
# ALL others → 200,000. Mapping verified against installed CC 2.1.187 binary,
# 2026-07-05; re-verify after Claude Code upgrades. Same-model subagents (and
# alternative-provider sessions, where the model ids match the session cache)
# keep the session window from above. Fail-open: any read failure leaves
# MAX_CONTEXT untouched.
if [[ -n "$AGENT_ID" ]]; then
    SESSION_MODEL=$(cat "/tmp/claude-model-${SESSION_ID}" 2>/dev/null) || SESSION_MODEL=""
    AGENT_MODEL_CACHE="/tmp/claude-subagent-model-${SESSION_ID}-${AGENT_ID}"
    AGENT_MODEL=""
    if [[ -f "$AGENT_MODEL_CACHE" ]]; then
        AGENT_MODEL=$(cat "$AGENT_MODEL_CACHE" 2>/dev/null)
    else
        AGENT_MODEL=$(tail -50 "$MEASURE_TRANSCRIPT" 2>/dev/null | jq -rs '
            [.[] | select(.message.model != "<synthetic>") | .message.model // empty] | last // empty
        ' 2>/dev/null)
        [[ -n "${AGENT_MODEL:-}" ]] && echo "$AGENT_MODEL" > "$AGENT_MODEL_CACHE" 2>/dev/null
    fi
    if [[ -n "${AGENT_MODEL:-}" && "$AGENT_MODEL" != "${SESSION_MODEL:-}" ]]; then
        case "$AGENT_MODEL" in
            # GPT (OpenAI) windows FIRST, most-specific first (mini/chat before
            # the flagships). The gpt-5.4/5.5/5.6 flagships legitimately carry a
            # [1m]-suffixed context-length variant, so GPT ids must be matched
            # BEFORE the generic *\[1m\]* Claude branch below — otherwise
            # gpt-5.6-terra[1m] would resolve 1,000,000 instead of its real
            # 1,050,000. Verified vs OpenRouter /api/v1/models 2026-07-09; keep
            # aligned with context-bar.sh + subagent-bar.sh. Window size only —
            # GPT keeps the conservative threshold FAMILY in calculate() below.
            *gpt-5*-mini*) MAX_CONTEXT=400000 ;;
            *gpt-5*-chat*) MAX_CONTEXT=128000 ;;
            *gpt-5.4*|*gpt-5.5*|*gpt-5.6*) MAX_CONTEXT=1050000 ;;
            *gpt-5*) MAX_CONTEXT=400000 ;;
            *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*\[1m\]*) MAX_CONTEXT=1000000 ;;
            *) MAX_CONTEXT=200000 ;;
        esac
        # CLAUDE_CODE_MAX_CONTEXT_TOKENS overrides provisioning when set.
        if [[ "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}" =~ ^[0-9]+$ ]]; then
            MAX_CONTEXT="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
        fi
    fi
fi
# Guard: must be a positive integer, else fall back to 200k.
if ! [[ "$MAX_CONTEXT" =~ ^[0-9]+$ ]] || [[ "$MAX_CONTEXT" -le 0 ]]; then
    MAX_CONTEXT=200000
fi
MAX_K=$((MAX_CONTEXT / 1000))

# ---------------------------------------------------------------------------
# Threshold-family model resolution: which model's family governs the severity
# thresholds for THIS measurement. Subagent measurements use the subagent's own
# model (already resolved into AGENT_MODEL above); main-session measurements use
# the session model (cache populated by cache_model() on a prior turn — read it
# here, falling back to the transcript's last model entry when the cache is not
# yet warm). Empty/unresolved leaves MEASURE_MODEL empty, which the calculate()
# case block treats as the conservative family (fail-conservative). This is
# INTENTIONALLY independent of the window-size mapping above: family (quality
# horizon) and window size are separate lookups.
if [[ -n "$AGENT_ID" ]]; then
    MEASURE_MODEL="${AGENT_MODEL:-}"
else
    MEASURE_MODEL=$(cat "/tmp/claude-model-${SESSION_ID}" 2>/dev/null) || MEASURE_MODEL=""
    if [[ -z "${MEASURE_MODEL:-}" ]]; then
        MEASURE_MODEL=$(tail -50 "$MEASURE_TRANSCRIPT" 2>/dev/null | jq -rs '
            [.[] | select(.message.model != "<synthetic>") | .message.model // empty] | last // empty
        ' 2>/dev/null) || MEASURE_MODEL=""
    fi
fi

# ---------------------------------------------------------------------------
# calculate: Parse the transcript's most recent usage data and format a
# utilization message with timestamp. Uses tail -50 to avoid parsing the
# entire JSONL file.
# Args: $1 = transcript path, $2 = allow_sidechain (true/false). When true,
# sidechain entries count (required for subagent transcripts, where every
# entry is isSidechain:true); when false, only main-chain entries count.
# $3 = model id of the agent being measured (drives the threshold family; may
# be empty → conservative family).
# Outputs a single line to stdout, or nothing if data is unavailable.
# ---------------------------------------------------------------------------
calculate() {
    local transcript="$1"
    local allow_sidechain="$2"
    local model="$3"
    [[ -z "$transcript" || ! -f "$transcript" ]] && return

    local tokens
    # Map each qualifying usage entry to its token sum, then take the last
    # POSITIVE sum rather than the last entry outright. Shim-routed (GPT)
    # transcripts end with streaming-placeholder usage entries whose token
    # fields are all 0 (stop_reason:null, input_tokens:0); taking `last`
    # unconditionally computes 0, and the `[[ tokens -le 0 ]] && return` below
    # then silently suppresses the utilization <system-reminder> for GPT
    # agents. Native Claude transcripts are unaffected: their last usage entry
    # is already positive, so last-positive == last. `// 0` keeps the fail-open
    # contract (no usage / no positive entry → 0 → the guard below returns).
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

    # Threshold family (percentage AND absolute k-token gates per severity),
    # keyed on the measured agent's model. Fable/Mythos get the permissive
    # family; everything else — INCLUDING opus-4-8[1m], whose 1M window does NOT
    # relax its Opus-class quality horizon — gets the conservative family.
    # Match ONLY *fable-5*/*mythos-5* (NOT [1m], NOT opus); unknown/empty falls
    # through to the conservative default (fail-conservative). Deliberately
    # different from the window-size case block above (which also matches opus
    # and [1m]) — family and window size are separate lookups.
    # See CLAUDE.md § Context Quality Curve for the authoritative threshold table.
    local elev_pct high_pct crit_pct elev_k high_k crit_k
    case "$model" in
        *fable-5*|*mythos-5*)
            elev_pct=30; high_pct=40; crit_pct=50
            elev_k=300;  high_k=400;  crit_k=500 ;;
        *)
            elev_pct=40; high_pct=60; crit_pct=75
            elev_k=150;  high_k=200;  crit_k=250 ;;
    esac

    # Dual-trigger thresholds: percentage OR absolute token count, whichever
    # fires first. Absolute counts cap effective session length on large context
    # windows (1M) where percentage thresholds would allow excessive token usage.
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
# cache_model: Extract the model name from the transcript and cache it once
# per session. audit-log.sh reads this cache to include model in audit entries.
# Main session only — subagent-fired calls skip this to avoid cross-writing
# the parent's cache (the parent has already populated it).
# ---------------------------------------------------------------------------
cache_model() {
    local transcript="$1"
    local cache="/tmp/claude-model-${SESSION_ID}"
    [[ -f "$cache" ]] && return  # Already cached
    [[ -z "$transcript" || ! -f "$transcript" ]] && return

    local model
    model=$(tail -50 "$transcript" 2>/dev/null | jq -r '
        select(.message.model and .message.model != "<synthetic>") | .message.model
    ' 2>/dev/null | head -1)

    [[ -n "${model:-}" ]] && echo "$model" > "$cache" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Shared rate-limit check (used by both events)
# ---------------------------------------------------------------------------
if [[ -z "$AGENT_ID" ]]; then
    cache_model "$TRANSCRIPT_PATH"
fi

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
echo "$NOW" > "$LAST_INJECT_FILE" 2>/dev/null

# ---------------------------------------------------------------------------
# Event dispatch (format differs per event, but both share the gate above)
# ---------------------------------------------------------------------------
case "$HOOK_EVENT" in

    UserPromptSubmit)
        # stdout → injected into Claude's context as <user-prompt-submit-hook>
        echo "$MSG"
        ;;

    PreToolUse)
        # JSON additionalContext → injected as <system-reminder> before tool executes
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
