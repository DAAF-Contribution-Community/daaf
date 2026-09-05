#!/usr/bin/env bash
# context-reporter.sh — Multi-event context utilization & timestamp hook
#
# Injects context window utilization and a current timestamp into Claude's
# conversation so the model can make informed decisions about delegation, state
# persistence, and session recovery (see CLAUDE.md utilization gates — the
# thresholds are quality-tier conditional: Fable/Mythos use 30%/40%/50% OR
# 300k/400k/500k; the exact extended-horizon GPT ids (GPT 5.6 Sol and GPT-6
# Astra) use 60%/75%/90% OR 300k/400k/500k; all other models use 40%/60%/75%
# OR 150k/200k/250k, whichever fires first; see calculate() below).
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
#   rescanning unchanged files. When a transcript has changed, the model and
#   usage are recovered from a full scan of the JSONL (last non-synthetic model,
#   last positive usage sum) so a long run of trailing zero-token shim
#   placeholders cannot hide the real values.
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
# Parent-model isolation:
#   The parent/session model is derived ONLY from a genuinely-parent source —
#   the parent model cache (/tmp/claude-model-<session_id>) refreshed from the
#   parent's MAIN transcript. It is NEVER inferred by re-parsing a path that is
#   itself a subagent transcript. When Claude Code passes the subagent's own
#   transcript directly (basename == agent-<id>.jsonl) there is no parent
#   transcript to scan, so the parent model comes from the cache alone (or is
#   left empty). A measured subagent is then mapped by ITS OWN model/window and
#   never assumed to share the session model (see Convention 10 in the
#   hardening spec).
#
# Threshold tier (see calculate()):
#   The severity thresholds are keyed on the model identity of the agent being
#   measured — main-session measurements use the session model; subagent
#   measurements use that subagent's own model. Fable/Mythos patterns get the
#   validated extended-horizon tier (30/40/50% OR 300/400/500k). The exact
#   terminal extended-horizon GPT slugs — gpt-5.6-sol and gpt-5.6-sol[1m], plus
#   the second registered extended-horizon model gpt-6-astra and gpt-6-astra[1m]
#   — use 60/75/90% gates while retaining 300/400/500k absolute gates. Provider
#   paths are accepted only when one of those exact slugs is the final path
#   segment. All other models (Opus, Sonnet, other GPT variants, GLM,
#   unknown/empty) get the conservative tier (40/60/75% OR 150/200/250k). This
#   is deliberately separate from physical-window mapping: the broad GPT 5.6
#   family and GPT-6 Astra each map to a 1.05M physical window on API/OpenRouter
#   routes, while the matched ChatGPT-subscription/Codex lane is finally capped
#   at 919k for accounting (measured 2026-09-05 for both Sol and Astra;
#   previously 370,000 (2026-07-16), now stale). Only the exact extended-horizon
#   GPT slugs retain the larger absolute quality-horizon gates without inheriting
#   Fable/Mythos percentage gates. Likewise, claude-opus-4-8[1m] AND Opus 5
#   (claude-opus-5, bare and [1m]) have 1M physical windows but keep the
#   conservative tier.
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

# Bounded identifier allowlist (Convention 2). Leading alnum, then
# alnum/dot/underscore/hyphen, max 128 chars. Rejects slashes, traversal (..),
# control chars, leading dash, empty, and >128. Every session_id / agent_id must
# pass this BEFORE it is interpolated into any transcript or /tmp cache path, so
# an attacker-shaped id can neither escape the /tmp namespace nor the subagent
# transcript subtree. A present-but-invalid id is rejected exactly like an
# absent one (key-presence contract).
is_safe_id() {
    [[ "${1:-}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]
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
# nonempty, non-synthetic model via a FULL scan of the JSONL (Convention 4 —
# a long tail of zero-token/synthetic placeholders cannot hide the real model).
# Both files are replaced through same-directory temporary siblings, with the
# signature moved last so interrupted writes force a safe refresh on the next
# invocation. When called with an empty transcript (e.g. the parent transcript
# is unavailable in the direct-subagent branch) it returns the cached value
# without scanning or writing.
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
        model=$(jq -rs '
            [.[] | (.message.model // empty)
             | select(. != "" and . != "<synthetic>")] | last // empty
        ' < "$transcript" 2>/dev/null) || model=""
    fi
    [[ -z "$model" ]] && model="$cached_model"

    if [[ -n "$model" && -n "$signature" ]]; then
        # Convention 6: wrap the redirection so an open() failure on the temp
        # target cannot leak "No such file"/"Permission denied" to the display
        # stream (redirections apply left-to-right, so a bare `> f 2>/dev/null`
        # would still print the open() diagnostic before 2> takes effect).
        if { printf '%s' "$model" > "$model_tmp"; } 2>/dev/null &&
           { printf '%s' "$signature" > "$signature_tmp"; } 2>/dev/null &&
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

# Convention 2: allowlist ids BEFORE any path/cache interpolation. Fail open
# (emit nothing, exit 0) on a rejected id — do not construct or read/write any
# path built from it. SESSION_ID is always used (every /tmp cache is keyed on
# it); AGENT_ID is only checked when present (its absence marks the main
# session). A present-but-invalid id is rejected like an absent one.
is_safe_id "$SESSION_ID" || exit 0
if [[ -n "$AGENT_ID" ]]; then
    is_safe_id "$AGENT_ID" || exit 0
fi

# Production caches live in /tmp. The override is a deterministic-test seam so
# Bats can exercise the gate/model/window cache reads and writes inside project
# scratch without touching live session state. The default is /tmp so
# production behavior is byte-identical; the name follows the per-script
# DAAF_<SCRIPT>_CACHE_DIR convention shared with context-bar.sh
# (DAAF_CONTEXT_BAR_CACHE_DIR) and subagent-bar.sh (DAAF_SUBAGENT_BAR_CACHE_DIR).
reporter_cache_dir="${DAAF_CONTEXT_REPORTER_CACHE_DIR:-/tmp}"

# ---------------------------------------------------------------------------
# Agent-aware measurement setup: decide WHICH transcript to measure, whether
# the sidechain filter applies, which rate-limit gate file to use, and which
# path (if any) is a genuine PARENT transcript for session-model inference.
# ---------------------------------------------------------------------------
if [[ -n "$AGENT_ID" ]]; then
    # Subagent-fired call: measure the subagent's OWN transcript.
    [[ -z "$TRANSCRIPT_PATH" ]] && exit 0
    if [[ "$(basename "$TRANSCRIPT_PATH")" == "agent-${AGENT_ID}.jsonl" ]]; then
        # Robustness for future Claude Code versions that may pass the
        # subagent's transcript path directly. In this case the supplied path
        # IS the subagent transcript, so there is NO parent transcript to scan
        # (Convention 10): the parent/session model must come from the parent
        # cache alone, never by re-parsing this subagent transcript.
        MEASURE_TRANSCRIPT="$TRANSCRIPT_PATH"
        PARENT_TRANSCRIPT=""
    else
        MEASURE_TRANSCRIPT="$(dirname "$TRANSCRIPT_PATH")/${SESSION_ID}/subagents/agent-${AGENT_ID}.jsonl"
        # The supplied path is the parent's MAIN transcript — a genuine parent
        # source for session-model inference.
        PARENT_TRANSCRIPT="$TRANSCRIPT_PATH"
    fi
    # Fail silent, never wrong: no fallback to the parent transcript here.
    [[ ! -f "$MEASURE_TRANSCRIPT" ]] && exit 0
    # Subagent transcripts are entirely isSidechain:true — disable the filter.
    ALLOW_SIDECHAIN=true
    # Per-agent gate so parent and subagents don't race on a shared timer.
    LAST_INJECT_FILE="${reporter_cache_dir}/claude-ctx-ts-${SESSION_ID}-${AGENT_ID}"
else
    # Main session: measure the parent transcript's main chain only.
    [[ -z "$TRANSCRIPT_PATH" ]] && exit 0
    MEASURE_TRANSCRIPT="$TRANSCRIPT_PATH"
    PARENT_TRANSCRIPT="$TRANSCRIPT_PATH"
    ALLOW_SIDECHAIN=false
    LAST_INJECT_FILE="${reporter_cache_dir}/claude-ctx-ts-${SESSION_ID}"
fi

INJECT_INTERVAL=60  # seconds between injections

# Convention 3: closed-set GPT flagship grammar. Only these exact terminal
# slugs (after stripping any provider path prefix) are eligible for the
# 1,050,000-token physical window and the 919k ChatGPT-lane cap arm. New
# codenames are a deliberate one-line registry edit (validate-before-trust,
# consistent with DAAF policy). Stored in a variable to avoid [[ =~ ]] quoting
# pitfalls. Accepts gpt-5.4/5.5/5.6 with an optional -sol/-terra/-luna codename,
# plus the standalone GPT-6 flagship gpt-6-astra, each with an optional [1m]
# badge; rejects malformed suffixes (gpt-5.4-, gpt-5.6-experimental,
# gpt-5.6-sol[1m]x, gpt-6-astra-pro, gpt-6-astra[1m]-x), mini/chat, gpt-5.60,
# and left-boundary near misses (xgpt-6-astra, gpt-6-astrab).
GPT_FLAGSHIP_RE='^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-astra)(\[1m\])?$'
# Closed-set mini/chat grammars (Convention 3), byte-consistent with
# subagent-bar.sh and context-bar.sh's anchored EREs. These replace the old
# open-ended inner globs (*-mini*/*-chat*) so suffixed near-misses (e.g.
# gpt-5.6-mini-preview) fail the anchor and fall through to the conservative
# 200k default rather than being mapped to 400k/128k. Anchored on the same
# provider-stripped PHYSICAL_SLUG the globs inspected.
GPT_MINI_RE='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-mini(\[1m\])?$'
GPT_CHAT_RE='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-chat(\[1m\])?$'

# Read THIS session's context window from the shared cache written by
# context-bar.sh (the statusline, which sees Claude Code's provisioned window
# and already applies the static map, override, and lane cap before writing).
# Subagent-fired hook calls carry the PARENT's session_id, so this is the
# SESSION's window; a subagent on a different model is mapped by its own model
# below. An absent or non-canonical cache leaves MAX_CONTEXT EMPTY here so the
# model-keyed static map below can fill it. Deliberately NO fallback to "the
# most recent cache from any session": that inherited an unrelated session's
# window (a Claude 1M session's 1000000, or a 200k session's 200000) into
# this one, which is neither authoritative nor related to the measured model.
CTX_CACHE="${reporter_cache_dir}/claude-ctx-window-${SESSION_ID}"
MAX_CONTEXT=""
if [[ -f "$CTX_CACHE" ]]; then
    MAX_CONTEXT=$(cat "$CTX_CACHE" 2>/dev/null)
fi
if ! is_canonical_positive_decimal "$MAX_CONTEXT"; then
    MAX_CONTEXT=""
fi

# Refresh model identity before same/different-model window selection, final-cap
# selection, and quality-tier selection. The main and subagent consumers share
# these bare cache paths and their synchronized .transcript-signature sidecars.
# Convention 10: the session model is derived ONLY from a genuine parent source
# (PARENT_TRANSCRIPT — empty when the supplied path is itself a subagent
# transcript), never by re-parsing a subagent transcript. An empty
# PARENT_TRANSCRIPT makes resolve_model_cache return the cached parent model (or
# empty), so a direct subagent measurement is never mistaken for the session.
SESSION_MODEL=$(resolve_model_cache "$PARENT_TRANSCRIPT" "${reporter_cache_dir}/claude-model-${SESSION_ID}")
AGENT_MODEL=""
if [[ -n "$AGENT_ID" ]]; then
    AGENT_MODEL_CACHE="${reporter_cache_dir}/claude-subagent-model-${SESSION_ID}-${AGENT_ID}"
    AGENT_MODEL=$(resolve_model_cache "$MEASURE_TRANSCRIPT" "$AGENT_MODEL_CACHE")
    MEASURE_MODEL="$AGENT_MODEL"
else
    MEASURE_MODEL="$SESSION_MODEL"
fi

# ---------------------------------------------------------------------------
# static_window_for_model: map a model id to the physical context window Claude
# Code provisions for it. Echoes a canonical positive integer; unknown or empty
# ids map to the conservative 200000. Physical GPT classification uses the
# terminal provider-stripped slug and the closed-set flagship predicate
# (Convention 3): the 1,050,000 flagship window is granted only to exact
# matches, while mini/chat retain their smaller windows and malformed codenames
# fall through to the conservative default. Physical size remains independent
# of the quality tier. Byte-consistent with subagent-bar.sh and the static map
# in context-bar.sh.
# ---------------------------------------------------------------------------
static_window_for_model() {
    local model="${1:-}"
    local slug="${model##*/}"
    local window=200000
    case "$model" in
        # Exact GLM-5.2 plus terminal date snapshots only. Keep this narrow:
        # glm-5.2-air and future variants have no verified static window.
        z-ai/glm-5.2|z-ai/glm-5.2-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
            window=1048576 ;;
        *)
            # gpt-5.4/5.5/5.6 family plus the standalone GPT-6 Astra flagship
            # (broad globs select the arm). Within it: mini/chat keep their
            # smaller windows and take precedence; the 1,050,000 flagship window
            # is granted ONLY to an exact closed-set match (GPT_FLAGSHIP_RE). A
            # malformed codename that entered the arm (gpt-5.6-experimental,
            # gpt-5.4-, gpt-5.6-sol[1m]x, gpt-6-astra-pro, gpt-6-astra[1m]-x) is
            # neither mini/chat nor an exact flagship, so it maps conservatively
            # to 200k instead of inheriting the flagship window.
            case "$slug" in
                gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*|gpt-6-astra|gpt-6-astra[-\[]*)
                    # Closed-set classification (Convention 3): only the anchored
                    # flagship/mini/chat grammars earn a GPT window. Order
                    # flagship, then mini, then chat. Malformed suffixes that
                    # reached this family glob match none and map conservatively.
                    if   [[ "$slug" =~ $GPT_FLAGSHIP_RE ]]; then window=1050000
                    elif [[ "$slug" =~ $GPT_MINI_RE ]];     then window=400000
                    elif [[ "$slug" =~ $GPT_CHAT_RE ]];     then window=128000
                    else window=200000
                    fi
                    ;;
                gpt-5|gpt-5[-\[]*|gpt-5.2|gpt-5.2[-\[]*)
                    case "$slug" in
                        *-chat*) window=128000 ;;
                        *) window=400000 ;;
                    esac
                    ;;
                *)
                    # Opus 5 (claude-opus-5, bare AND [1m]) is a native 1M-window
                    # model: observed 2026-09-05 on Claude Code 2.1.261 via
                    # /model + /context — bare `claude-opus-5` reported
                    # "42.8k/1m tokens" and `claude-opus-5[1m]` reported
                    # "48.2k/1m", so the bare id must map to 1,000,000 and not
                    # fall through to the 200k arm. Opus 5 nonetheless stays on
                    # the CONSERVATIVE quality profile below (physical window and
                    # quality threshold are separate lookups). Provenance:
                    # research/2026-09-05_FrameworkDev_ClaudeCode_Upgrade_2.1.261
                    # (to-do 03 Branch A).
                    case "$model" in
                        *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*opus-5*|*\[1m\]*)
                            window=1000000 ;;
                        *) window=200000 ;;
                    esac
                    ;;
            esac
            ;;
    esac
    printf '%s' "$window"
}

# Physical window resolution (denominator), in precedence order:
#   1. DIFFERENT-model subagent: always the static map for ITS model. A sonnet
#      subagent inside a 1M fable session has 200k — its severity must be
#      computed against 200k, or HIGH/CRITICAL fire far too late. When
#      SESSION_MODEL is empty (no parent cache) and AGENT_MODEL is set, they
#      differ, so this arm still runs and never assumes same-model
#      (Convention 10).
#   2. Otherwise (main session, or a same-model subagent): this session's
#      cache when present — it is authoritative, written by the statusline
#      from Claude Code's own provisioned window.
#   3. Otherwise: the static map for the MEASURED model. This closes the gap
#      where an uncached main session or same-model child (statusline not yet
#      rendered, or a headless/dispatch context that never renders one) fell
#      to 200k regardless of model — a GPT-6 Astra or Opus 5 session at 300k
#      then read 100%/CRITICAL and subagents falsely throttled. An unknown or
#      empty model still yields 200000 (fail-conservative).
# The user override and the ChatGPT-lane cap below apply after this, unchanged.
if [[ -n "$AGENT_ID" && -n "$AGENT_MODEL" && "$AGENT_MODEL" != "$SESSION_MODEL" ]]; then
    MAX_CONTEXT=$(static_window_for_model "$AGENT_MODEL")
elif ! is_canonical_positive_decimal "$MAX_CONTEXT"; then
    MAX_CONTEXT=$(static_window_for_model "$MEASURE_MODEL")
fi

# CLAUDE_CODE_MAX_CONTEXT_TOKENS is the ordinary user override. Apply it to
# every measurement path before the backend-specific final constraint below.
if is_canonical_positive_decimal "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}"; then
    MAX_CONTEXT="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
fi

# ChatGPT-subscription/Codex final physical-window accounting constraint.
# Canonical activation requires BOTH exact lane signals and a measured model in
# the anchored flagship arm (Convention 3 closed set — the gpt-5.4/5.5/5.6
# family plus gpt-6-astra; mini/chat are excluded because they carry suffixes
# the ERE does not accept). Probes 2026-09-05 (Codex CLI 0.153.2, shim v1.3.19,
# SHIM_BACKEND_MODE=chatgpt) measured BOTH lane flagships: gpt-6-astra accepted
# 919,053 real input tokens and rejected 922,552; gpt-5.6-sol accepted 910,827
# and rejected 921,973. 919000 is therefore the lane-wide accounting ceiling for
# this arm, MEASURED for Sol and Astra alike and consistent with Astra's
# documented 922,000-token max input (1,050,000 window - 128,000 output).
# Provenance: previously 370,000 (2026-07-16), now stale. Applying
# min(resolved, 919000) after model/cache/override resolution prevents stale or
# unsafe ordinary values from surviving while preserving lower valid values.
# This is accounting, not compaction or a transport-level blocker.
GPT_FLAGSHIP=0
PHYSICAL_SLUG="${MEASURE_MODEL##*/}"
if [[ "$PHYSICAL_SLUG" =~ $GPT_FLAGSHIP_RE ]]; then
    GPT_FLAGSHIP=1
fi
if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
      "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
      "$GPT_FLAGSHIP" -eq 1 ]] && \
   is_canonical_positive_decimal "$MAX_CONTEXT" && \
   [[ "$MAX_CONTEXT" -gt 919000 ]]; then
    MAX_CONTEXT=919000
fi

# Final denominator guard before arithmetic.
if ! is_canonical_positive_decimal "$MAX_CONTEXT"; then
    MAX_CONTEXT=200000
fi
MAX_K=$((MAX_CONTEXT / 1000))

# ---------------------------------------------------------------------------
# calculate: Parse the transcript's most recent usage data and format a
# utilization message with timestamp. Scans the FULL JSONL (Convention 4) and
# takes the last POSITIVE usage sum, so trailing zero-token shim placeholders
# cannot mask a real reading.
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
    # Convention 4: full-transcript scan via `< "$transcript"` (the -f guard
    # above keeps a missing/binary file fail-open).
    tokens=$(jq -s --argjson allow_sidechain "$allow_sidechain" '
        [.[] | select(
            .message.usage and
            ((.isSidechain != true) or $allow_sidechain) and
            .isApiErrorMessage != true
        ) | (
            (.message.usage.input_tokens // 0) +
            (.message.usage.cache_read_input_tokens // 0) +
            (.message.usage.cache_creation_input_tokens // 0)
        )] | map(select(. > 0)) | last // 0
    ' < "$transcript" 2>/dev/null) || tokens=0

    # Convention 5: bound the numerator before tokens*100 so a huge (but
    # jq-emitted, int64-valid) value cannot overflow signed-64 and wrap pct
    # negative. Require a canonical positive decimal <= floor(INT64_MAX/100);
    # anything else (including 0, non-numeric, or over-large) fails open by
    # omitting the injection — symmetric with the validated denominator.
    is_canonical_positive_decimal "$tokens" || return
    [[ "$tokens" -le 92233720368547758 ]] || return

    local pct=$((tokens * 100 / MAX_CONTEXT))
    [[ $pct -gt 100 ]] && pct=100
    local used_k=$((tokens / 1000))

    # Quality-tier matching deliberately remains narrower than physical-family
    # matching. Fable/Mythos keep the validated extended-horizon percentage and
    # absolute gates; the exact terminal extended-horizon GPT slugs — Sol and
    # the second registered extended-horizon model GPT-6 Astra — use 60/75/90%
    # percentage gates while retaining the larger absolute gates. Each is matched
    # only as the bare slug or the final segment of a provider path; left- or
    # right-boundary near misses (xgpt-6-astra, gpt-6-astra-pro, gpt-6-astra-mini,
    # gpt-6-astra[1m]-x) fall through to the conservative tier.
    local elev_pct high_pct crit_pct elev_k high_k crit_k
    case "$model" in
        *fable-5*|*mythos-5*)
            elev_pct=30; high_pct=40; crit_pct=50
            elev_k=300;  high_k=400;  crit_k=500 ;;
        gpt-5.6-sol|*/gpt-5.6-sol|gpt-5.6-sol\[1m\]|*/gpt-5.6-sol\[1m\]|gpt-6-astra|*/gpt-6-astra|gpt-6-astra\[1m\]|*/gpt-6-astra\[1m\])
            elev_pct=60; high_pct=75; crit_pct=90
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

# Convention 11: a corrupt or future gate timestamp would make (NOW - LAST_INJECT)
# negative — always under the interval — and suppress every future report
# indefinitely. Treat a non-canonical value OR one greater than NOW as corrupt
# and reset to 0 (allow the report). The short-circuit keeps the -gt arithmetic
# off any non-integer value. A legitimate recent-past value still suppresses.
if ! is_canonical_positive_decimal "$LAST_INJECT" || [[ "$LAST_INJECT" -gt "$NOW" ]]; then
    LAST_INJECT=0
fi

if [[ $((NOW - LAST_INJECT)) -lt $INJECT_INTERVAL ]]; then
    # Interval not elapsed — skip injection, don't block
    exit 0
fi

# Interval elapsed — calculate and emit
MSG=$(calculate "$MEASURE_TRANSCRIPT" "$ALLOW_SIDECHAIN" "$MEASURE_MODEL")
[[ -z "${MSG:-}" ]] && exit 0

# Update the per-agent timestamp gate. Convention 6: wrap the redirection so an
# open() failure (unwritable /tmp, ENOTDIR) cannot leak its diagnostic to the
# display stream before 2> takes effect. If the write fails, continue without
# gating — display output is preserved and the hook still exits 0.
{ printf '%s' "$NOW" > "$LAST_INJECT_FILE"; } 2>/dev/null

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
