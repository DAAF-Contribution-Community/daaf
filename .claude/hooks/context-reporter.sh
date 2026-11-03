#!/usr/bin/env bash
# context-reporter.sh — Multi-event context utilization & timestamp hook
#
# Injects context window utilization and a current timestamp into Claude's
# conversation so the model can make informed decisions about delegation, state
# persistence, and session recovery (see CLAUDE.md § Context Quality Curve).
# The thresholds depend on the threshold profile of the measured model,
# whichever of the percentage or absolute gate fires first (see calculate()):
#   Claude extended-horizon (Fable/Mythos patterns, plus Opus 5.5:
#     claude-opus-5-5, bare or [1m]): ELEVATED >= 40% OR >= 400k,
#     HIGH >= 50% OR >= 500k, CRITICAL >= 60% OR >= 600k.
#   GPT extended-horizon (exact GPT 5.6 Sol and GPT-6 Astra, plus GPT-6 Sol,
#     GPT-6.1 Sol and the flagship -pro form of each; see GPT_EXTENDED_RE):
#     60%/75%/90% percentage gates with 300k/400k/500k absolute gates.
#   Every other model: ELEVATED >= 40% OR >= 150k, HIGH >= 60% OR >= 200k,
#     CRITICAL >= 75% OR >= 250k.
# POLICY ADMISSIONS (the canonical note for this hook): Opus 5.5 in the
# Claude profile; the Claude profile's 40/50/60% OR 400/500/600k numbers
# (Fable/Mythos were validated at 30/40/50% OR 300/400/500k); GPT-6 Sol,
# GPT-6.1 Sol and every flagship -pro form in the GPT profile; and the GPT-6
# window mappings and ChatGPT-lane cap for the forms not measured (see
# GPT_FLAGSHIP_RE) are admitted by user policy, not by DAAF validation; see
# CLAUDE.md § Context Quality Curve and
# agent_reference/CONTEXT_THRESHOLDS_REFERENCE.md. Other comments in this
# hook point here rather than restating it.
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
#   placeholders cannot hide the real values. Both scans parse line by line
#   (jq -Rn, inputs | fromjson?) and skip any line that is not a complete JSON
#   object, because Claude Code appends to the transcript while hooks read it:
#   a single partly written last line must not hide every record before it.
#
# Subagent support:
#   settings.json PreToolUse hooks also fire for tool calls made BY subagents.
#   In that case the hook's stdin JSON carries the PARENT's session_id and the
#   PARENT's main transcript_path, plus an `agent_id` field that is present
#   ONLY inside subagent calls (Claude Code hooks reference, verified
#   2026-11-02). When agent_id is present, this script measures
#   the SUBAGENT's own transcript, located at:
#     <dirname(transcript_path)>/<session_id>/subagents/agent-<agent_id>.jsonl
#   Entries in subagent transcripts all carry isSidechain:true (layout and
#   flag observed 2026-11-02, Claude Code 2.1.281), so the
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
#   never assumed to share the session model.
#
# Threshold profile (see calculate()):
#   The severity thresholds are keyed on the model identity of the agent being
#   measured — main-session measurements use the session model; subagent
#   measurements use that subagent's own model. Fable/Mythos patterns and
#   Opus 5.5 get the Claude extended-horizon profile. The exact terminal
#   extended-horizon GPT slugs (GPT_EXTENDED_RE: gpt-5.6-sol and gpt-6-astra,
#   plus gpt-6-sol, gpt-6.1-sol and the -pro form of each, each optionally
#   followed by [1m]) get the GPT profile, with its own 300/400/500k absolute
#   gates rather than the Claude profile's. Provider paths are accepted only
#   when one of those exact slugs is the final path segment. All other models
#   (every Opus model except Opus 5.5, Sonnet, other GPT variants including
#   GPT-6 Luna, GLM, unknown/empty) get the conservative profile. Profile
#   membership is deliberately separate from physical-window mapping: the
#   broad GPT 5.6 family and the GPT-6 flagships (Astra, Sol, Luna) each map
#   to a 1.05M physical window on API/OpenRouter routes, while the matched
#   ChatGPT-subscription/Codex lane is capped at 919k for accounting (see the
#   lane-cap block below). Likewise, claude-opus-4-8[1m], Opus 5
#   (claude-opus-5, bare and [1m]), Sonnet 5.x (claude-sonnet-5,
#   claude-sonnet-5-5) and Haiku 5.5 (claude-haiku-5-5) have 1M physical
#   windows but keep the conservative profile; on a 1M window its absolute
#   legs fire first (ELEVATED 150k, HIGH 200k, CRITICAL 250k).
#   Opus 5.5 (claude-opus-5-5, bare and [1m]) is the ONE Opus exception (see
#   POLICY ADMISSIONS). Every other Opus model, bare Opus 5 included, stays
#   conservative: the profile arm names claude-opus-5-5 exactly (bare or as a
#   provider path's final segment) rather than substring-matching, so near
#   misses such as claude-opus-5-5-mini and xclaude-opus-5-5 cannot inherit
#   the relaxed gates.
#   Provider-dotted Claude ids (OpenRouter's anthropic/claude-opus-5.5 form) are
#   rewritten to the hyphenated form by normalize_model_id before any of the
#   above classification, so they reach the same arms as claude-opus-5-5.
#   If model resolution fails, the conservative profile applies
#   (fail-conservative).
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

# Bounded identifier allowlist. Leading alnum, then
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
# nonempty, non-synthetic model via a FULL scan of the JSONL (a long tail of
# zero-token/synthetic placeholders cannot hide the real model).
# Both files are replaced through same-directory temporary siblings, with the
# signature moved last so interrupted writes force a safe refresh on the next
# invocation. When called with an empty transcript (e.g. the parent transcript
# is unavailable in the direct-subagent branch) it returns the cached value
# without scanning or writing.
# The scan is line-wise and skips lines that are not valid JSON objects and
# isApiErrorMessage records, so a partly written last line cannot blank the
# model (an empty subagent model would send the reading to the SESSION's
# window). stderr is redirected before stdin, so an unreadable transcript
# prints no "Permission denied". The block between the section-sign markers
# is kept BYTE-IDENTICAL with resolve_model_cache in
# .claude/scripts/subagent-bar.sh, which writes the same caches (lockstep test
# in tests/bash/context_reporter.bats). $3 = include_attachment (true/false,
# default false): true only for a subagent's OWN transcript. Then, if no
# record carries a .message.model yet, the model attachment Claude Code
# writes at the top of a subagent transcript ({"type":"attachment",
# "attachment":{"type":"model","identity":{"modelId":...}}}, observed
# 2026-11-02, Claude Code 2.1.281) supplies it. A .message.model always wins
# over the attachment.
resolve_model_cache() {
    local transcript="${1:-}"
    local cache="${2:-}"
    local include_attachment="${3:-false}"
    local signature_cache="${cache}.transcript-signature"
    local signature="" cached_signature="" cached_model="" model=""
    local model_tmp="${cache}.tmp.$$" signature_tmp="${signature_cache}.tmp.$$"

    [[ "$include_attachment" == "true" ]] || include_attachment=false

    [[ -n "$cache" ]] || return 0
    [[ -s "$cache" ]] && cached_model=$(cat "$cache" 2>/dev/null)
    signature=$(transcript_signature "$transcript") || signature=""
    [[ -s "$signature_cache" ]] && cached_signature=$(cat "$signature_cache" 2>/dev/null)

    if [[ -n "$cached_model" && -n "$signature" && "$cached_signature" == "$signature" ]]; then
        printf '%s' "$cached_model"
        return 0
    fi

    if [[ -n "$transcript" && -f "$transcript" ]]; then
# §§ MODEL_SCAN_JQ
        model=$(jq -Rnr --argjson attach "$include_attachment" '
            [inputs | fromjson? | objects | select(.isApiErrorMessage != true)
             | ((.message? | objects | .model? | strings | {src: "message", id: .}),
                (if $attach and .type? == "attachment" then
                     .attachment? | objects | select(.type? == "model")
                     | .identity? | objects | .modelId? | strings
                     | {src: "attachment", id: .}
                 else empty end))
             | select(.id != "" and .id != "<synthetic>")] as $hits
            | ([$hits[] | select(.src == "message") | .id] | last)
              // ([$hits[] | select(.src == "attachment") | .id] | last)
              // empty
        ' 2>/dev/null < "$transcript") || model=""
# §§ END MODEL_SCAN_JQ
    fi
    [[ -z "$model" ]] && model="$cached_model"

    if [[ -n "$model" && -n "$signature" ]]; then
        # Wrap the redirection so an open() failure on the temp
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

# Provider-dotted Claude model ids. OpenRouter reports Claude
# models with a DOTTED version (anthropic/claude-opus-5.5, claude-opus-4.8,
# claude-opus-5.5[1m]), while every Claude pattern in this hook expects
# Anthropic's hyphenated form (claude-opus-5-5). Unnormalized, a dotted id
# misses the anchored extended-horizon profile arm and the *opus-4-8* window
# arm, so a dotted Opus 5.5 or Opus 4.8 subagent would be measured against
# the conservative profile or a 200k window. normalize_model_id
# rewrites ONLY an id that ENDS in claude-<family>-<major>.<minor>, optionally
# followed by [1m], to the hyphenated form, keeping any provider prefix
# (anthropic/claude-opus-5.5 -> anthropic/claude-opus-5-5, which the anchored
# */claude-opus-5-5 arm already matches). Every other id passes through
# unchanged, so near misses such as anthropic/claude-opus-5.5-mini stay
# conservative (fail-conservative) and GPT ids are never touched. It is applied
# at CLASSIFICATION points only (SESSION_MODEL / AGENT_MODEL right after they
# are resolved, so the same/different-model comparison, the physical-window
# lookup, the ChatGPT-lane flagship predicate, and the threshold profile all see the
# normalized id); resolve_model_cache has already written the shared model
# caches with the RAW name, and this hook displays no model name. The block
# between the section-sign markers is kept BYTE-IDENTICAL with
# .claude/scripts/subagent-bar.sh (lockstep test in
# tests/bash/context_reporter.bats). Provenance: the OpenRouter model
# catalogue (https://openrouter.ai/api/v1/models, fetched 2026-09-29), which
# lists the dotted ids anthropic/claude-opus-5.5, -4.8, -4.7 and
# claude-fable-5.1.
# §§ NORMALIZE_MODEL_ID
normalize_model_id() {
    local model="${1:-}"
    local dotted_re='^((.*/)?claude-[a-z]+-[0-9]+)\.([0-9]+)(\[1m\])?$'
    if [[ "$model" =~ $dotted_re ]]; then
        model="${BASH_REMATCH[1]}-${BASH_REMATCH[3]}${BASH_REMATCH[4]}"
    fi
    printf '%s' "$model"
}
# §§ END NORMALIZE_MODEL_ID

INPUT=$(cat)
HOOK_EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null) || HOOK_EVENT=""
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "default"' 2>/dev/null) || SESSION_ID="default"
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null) || TRANSCRIPT_PATH=""
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // empty' 2>/dev/null) || AGENT_ID=""

# Allowlist ids BEFORE any path/cache interpolation. Fail open
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
        # IS the subagent transcript, so there is NO parent transcript to scan:
        # the parent/session model must come from the parent
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

# Closed-set GPT flagship grammar. Only these exact terminal
# slugs (after stripping any provider path prefix) are eligible for the
# 1,050,000-token physical window and the 919k ChatGPT-lane cap arm. New
# codenames are a deliberate one-line registry edit (validate-before-trust,
# consistent with DAAF policy). Stored in a variable to avoid [[ =~ ]] quoting
# pitfalls. Accepts gpt-5.4/5.5/5.6 with an optional -sol/-terra/-luna codename,
# plus the GPT-6 flagships gpt-6-astra, gpt-6-sol, and gpt-6-luna, each with an
# optional -pro and then an optional [1m] badge; rejects malformed suffixes
# (gpt-5.4-, gpt-5.6-experimental, gpt-5.6-sol[1m]x, gpt-6-astra-pro-x,
# gpt-6-sol[1m]-pro, gpt-6-astra[1m]-x), mini/chat (and their -pro spellings,
# e.g. gpt-5.6-mini-pro), unregistered GPT-6 names (gpt-6, gpt-6-terra,
# gpt-6-sol-mini), gpt-5.60, and left-boundary near misses (xgpt-6-astra,
# gpt-6-astrab).
# Flagship rules (see POLICY ADMISSIONS): (1) any FLAGSHIP -pro model reads
# exactly as its non-pro base — same physical window, same 919k ChatGPT-lane
# cap eligibility, same profile; -pro sits immediately before the optional
# [1m]. (2) gpt-6-sol is treated identically to gpt-5.6-sol and gpt-6-luna
# identically to gpt-5.6-luna; gpt-6.1-sol (one exact alternative, optional
# -pro and [1m]) is treated identically to gpt-6-sol. There is NO
# gpt-6-terra, and no gpt-6.1-* wildcard: gpt-6.1-luna, gpt-6.1-sol-mini,
# etc. stay unregistered. Windows per the OpenRouter catalogue fetched
# 2026-09-29 (context_length 1050000 for openai/gpt-6-sol, gpt-6-sol-pro,
# gpt-6-luna, gpt-6-luna-pro, gpt-6-astra-pro, gpt-5.6-{sol,terra,luna}-pro,
# gpt-5.5-pro, gpt-5.4-pro; no gpt-6-terra entry):
# https://openrouter.ai/api/v1/models; and OpenRouter openai/gpt-6.1-sol
# (https://openrouter.ai/openai/gpt-6.1-sol, fetched 2026-10-12). Capping at
# 919k can only make a reading more conservative.
# GPT_EXTENDED_RE is the PROFILE grammar used by calculate(), deliberately
# narrower than the window grammar: gpt-5.6-sol and gpt-6-astra (validated),
# plus gpt-6-sol, gpt-6.1-sol, and the -pro form of each (see POLICY
# ADMISSIONS); gpt-6-luna and every Terra/Luna form keep a 1.05M window but the
# conservative profile. Both strings are kept byte-identical with subagent-bar.sh
# (gpt_flagship_re, gpt_extended_re) and, for the flagship grammar, with
# context-bar.sh (lockstep tests in tests/bash/context_reporter.bats).
GPT_FLAGSHIP_RE='^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-(astra|sol|luna)|gpt-6\.1-sol)(-pro)?(\[1m\])?$'
GPT_EXTENDED_RE='^(gpt-5\.6-sol|gpt-6-(astra|sol)|gpt-6\.1-sol)(-pro)?(\[1m\])?$'
# Closed-set mini/chat grammars, byte-consistent with subagent-bar.sh and
# context-bar.sh's anchored EREs. They are anchored rather than open-ended
# globs (*-mini*/*-chat*), so suffixed near-misses (e.g.
# gpt-5.6-mini-preview) fail the anchor and fall through to the conservative
# 200k default rather than being mapped to 400k/128k. Anchored on the
# provider-stripped terminal slug.
GPT_MINI_RE='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-mini(\[1m\])?$'
GPT_CHAT_RE='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-chat(\[1m\])?$'

# Read THIS session's context window from the shared cache written by
# context-bar.sh (the statusline, which sees Claude Code's provisioned window
# and already applies the static map, override, and lane cap before writing).
# Subagent-fired hook calls carry the PARENT's session_id, so this is the
# SESSION's window; a subagent on a different model is mapped by its own model
# below. An absent or non-canonical cache leaves MAX_CONTEXT EMPTY here so the
# model-keyed static map below can fill it. Deliberately NO fallback to "the
# most recent cache from any session": that would bring in an unrelated
# session's window (a Claude 1M session's 1000000, or a 200k session's
# 200000), which is neither authoritative nor related to the measured model.
CTX_CACHE="${reporter_cache_dir}/claude-ctx-window-${SESSION_ID}"
MAX_CONTEXT=""
if [[ -f "$CTX_CACHE" ]]; then
    MAX_CONTEXT=$(cat "$CTX_CACHE" 2>/dev/null)
fi
if ! is_canonical_positive_decimal "$MAX_CONTEXT"; then
    MAX_CONTEXT=""
fi

# Refresh model identity before same/different-model window selection, final-cap
# selection, and threshold-profile selection. The main and subagent consumers share
# these bare cache paths and their synchronized .transcript-signature sidecars.
# The session model is derived ONLY from a genuine parent source
# (PARENT_TRANSCRIPT — empty when the supplied path is itself a subagent
# transcript), never by re-parsing a subagent transcript. An empty
# PARENT_TRANSCRIPT makes resolve_model_cache return the cached parent model (or
# empty), so a direct subagent measurement is never mistaken for the session.
# Both ids are then normalized (normalize_model_id) for CLASSIFICATION: the
# claude-model-<session> cache is seeded by context-bar.sh from the REQUESTED
# .model.id and refreshed here from the transcript's RESPONSE model, so on
# OpenRouter it may hold either the dotted or the hyphenated spelling;
# normalizing both sides keeps a dotted-vs-hyphenated version spelling alone
# from forcing the different-model path (a provider-prefix difference still
# does; harmless, because the static map returns the correct window for either
# spelling). resolve_model_cache has already written the caches
# with the RAW name, and nothing below displays or writes these variables.
SESSION_MODEL=$(resolve_model_cache "$PARENT_TRANSCRIPT" "${reporter_cache_dir}/claude-model-${SESSION_ID}")
SESSION_MODEL=$(normalize_model_id "$SESSION_MODEL")
AGENT_MODEL=""
if [[ -n "$AGENT_ID" ]]; then
    AGENT_MODEL_CACHE="${reporter_cache_dir}/claude-subagent-model-${SESSION_ID}-${AGENT_ID}"
    # include_attachment=true: the subagent's own transcript names its model in
    # a model attachment before its first assistant record is readable.
    AGENT_MODEL=$(resolve_model_cache "$MEASURE_TRANSCRIPT" "$AGENT_MODEL_CACHE" true)
    AGENT_MODEL=$(normalize_model_id "$AGENT_MODEL")
    MEASURE_MODEL="$AGENT_MODEL"
else
    MEASURE_MODEL="$SESSION_MODEL"
fi

# ---------------------------------------------------------------------------
# static_window_for_model: map a model id to the physical context window Claude
# Code provisions for it. Echoes a canonical positive integer; unknown or empty
# ids map to the conservative 200000. Physical GPT classification uses the
# terminal provider-stripped slug and the closed-set flagship predicate:
# the 1,050,000 flagship window is granted only to exact
# matches, while mini/chat retain their smaller windows and malformed codenames
# fall through to the conservative default. Physical size remains independent
# of the threshold profile. OUTPUT-consistent (not byte-identical — the code shape
# differs) with subagent-bar.sh's function of the same name and with the static
# map in context-bar.sh: the GPT EREs and the flagship-family glob below are
# copied verbatim into both, so every flagship/mini/chat id and every malformed
# flagship-family id (e.g. gpt-6-sol[1m]-pro -> 200k) maps identically
# (cross-script agreement tests in tests/bash/context_reporter.bats and
# tests/bash/subagent_bar.bats). Known difference: malformed
# gpt-5 / gpt-5.2-family spellings (e.g. gpt-5-pro) map to 400k here and in
# context-bar.sh but to 200k in subagent-bar.sh (anchored prev EREs; 1M there
# if the id carries [1m], via its generic Claude arm).
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
            # gpt-5.4/5.5/5.6 family plus the GPT-6 Astra/Sol/Luna flagships
            # and gpt-6.1-sol (broad globs select the arm; see POLICY
            # ADMISSIONS for the GPT-6 forms). Within it: the 1,050,000
            # flagship window is granted ONLY to an exact closed-set match
            # (GPT_FLAGSHIP_RE, which also accepts the flagship -pro forms);
            # mini/chat keep their smaller windows. A malformed codename that
            # entered the arm (gpt-5.6-experimental, gpt-5.4-,
            # gpt-5.6-sol[1m]x, gpt-6-astra-pro-x, gpt-6-sol[1m]-pro,
            # gpt-6-sol-mini, gpt-6-astra[1m]-x) is neither mini/chat nor an
            # exact flagship, so it maps conservatively to 200k instead of
            # inheriting the flagship window.
            case "$slug" in
                gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*|gpt-6-astra|gpt-6-astra[-\[]*|gpt-6-sol|gpt-6-sol[-\[]*|gpt-6-luna|gpt-6-luna[-\[]*|gpt-6.1-sol|gpt-6.1-sol[-\[]*)
                    # Closed-set classification: only the anchored
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
                    # the CONSERVATIVE profile below (physical window and
                    # threshold profile are separate lookups).
                    # Opus 5.5 (claude-opus-5-5, bare AND [1m]) is likewise a
                    # native 1M-window model (Claude Code CHANGELOG 2.1.280:
                    # "Added Claude Opus 5.5 (`claude-opus-5-5`), now the
                    # default Opus model — 1M context"). The explicit
                    # *opus-5-5* arm states Opus 5.5's 1M window; *opus-5*
                    # also matches it, but only because both happen to be
                    # 1M, and the next Opus generation may not be. A loose
                    # substring is acceptable HERE and not in the profile arm
                    # below: mapping a physical window is descriptive, not a
                    # privilege grant.
                    # Sonnet 5.x (*sonnet-5*: claude-sonnet-5,
                    # claude-sonnet-5-5) and Haiku 5.5 (*haiku-5-5*) also run
                    # with the 1M window by default, with no [1m] suffix
                    # (verified 2026-11-02 against the Claude Code docs,
                    # model-config "Extended context", and the Claude platform
                    # model docs). Neither glob matches a 200k model:
                    # claude-sonnet-4-5, claude-sonnet-4-6 and claude-haiku-4-5
                    # contain no "sonnet-5" or "haiku-5-5". A later major
                    # version (claude-sonnet-6) matches neither and needs its
                    # own arm. Window only: both stay on the CONSERVATIVE
                    # profile in calculate().
                    case "$model" in
                        *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*opus-5-5*|*opus-5*|*sonnet-5*|*haiku-5-5*|*\[1m\]*)
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
#   1. DIFFERENT-model subagent: always the static map for ITS model. A Sonnet
#      4.6 subagent inside a 1M fable session has 200k — its severity must be
#      computed against 200k, or HIGH/CRITICAL fire far too late. When
#      SESSION_MODEL is empty (no parent cache) and AGENT_MODEL is set, they
#      differ, so this arm still runs and never assumes same-model.
#   2. Otherwise (main session, or a same-model subagent): this session's
#      cache when present — it is authoritative, written by the statusline
#      from Claude Code's own provisioned window.
#   3. Otherwise: the static map for the MEASURED model. An uncached main
#      session or same-model child (statusline not yet rendered, or a
#      headless/dispatch context that never renders one) maps by its own
#      model, so a GPT-6 Astra or Opus 5 session is not measured against 200k
#      (at 300k it would read 100%/CRITICAL). An unknown or empty model
#      yields 200000 (fail-conservative).
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
# the anchored flagship arm (the closed set GPT_FLAGSHIP_RE accepts; mini/chat
# are excluded because they carry suffixes the ERE does not accept).
# Probes 2026-09-05 (Codex CLI 0.153.2, shim v1.3.19,
# SHIM_BACKEND_MODE=chatgpt) measured BOTH lane flagships: gpt-6-astra accepted
# 919,053 real input tokens and rejected 922,552; gpt-5.6-sol accepted 910,827
# and rejected 921,973. 919000 is therefore the lane-wide accounting ceiling for
# this arm, consistent with Astra's documented 922,000-token max input
# (1,050,000 window - 128,000 output). gpt-6.1-sol was measured against the
# same cap on 2026-10-13; gpt-6-sol, gpt-6-luna and the flagship -pro forms
# inherit it from their bases (see POLICY ADMISSIONS). Applying
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
# utilization message with timestamp. Scans the FULL JSONL and
# takes the last POSITIVE usage sum, so trailing zero-token shim placeholders
# cannot mask a real reading.
# Args: $1 = transcript path, $2 = allow_sidechain (true/false). When true,
# sidechain entries count; when false, only main-chain entries count.
# $3 = model id of the agent being measured (drives the threshold profile;
# may be empty → conservative profile).
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
    # Full-transcript scan via `< "$transcript"` (the -f guard
    # above keeps a missing/binary file fail-open). Line-wise, like the model
    # scan: a line that is not valid JSON (such as a partly written last line)
    # is skipped instead of failing the whole parse and suppressing the report.
    # stderr is redirected before stdin, so an unreadable transcript prints no
    # "Permission denied".
    tokens=$(jq -Rn --argjson allow_sidechain "$allow_sidechain" '
        [inputs | fromjson? | objects | select(
            .message.usage and
            ((.isSidechain != true) or $allow_sidechain) and
            .isApiErrorMessage != true
        ) | (
            (.message.usage.input_tokens // 0) +
            (.message.usage.cache_read_input_tokens // 0) +
            (.message.usage.cache_creation_input_tokens // 0)
        )] | map(select(. > 0)) | last // 0
    ' 2>/dev/null < "$transcript") || tokens=0

    # Bound the numerator before tokens*100 so a huge (but
    # jq-emitted, int64-valid) value cannot overflow signed-64 and wrap pct
    # negative. Require a canonical positive decimal <= floor(INT64_MAX/100);
    # anything else (including 0, non-numeric, or over-large) fails open by
    # omitting the injection — symmetric with the validated denominator.
    is_canonical_positive_decimal "$tokens" || return
    [[ "$tokens" -le 92233720368547758 ]] || return

    local pct=$((tokens * 100 / MAX_CONTEXT))
    [[ $pct -gt 100 ]] && pct=100
    local used_k=$((tokens / 1000))

    # Profile matching deliberately remains narrower than physical-family
    # matching. Fable/Mythos and Opus 5.5 use the Claude extended-horizon
    # gates, 40/50/60% OR 400/500/600k (see POLICY ADMISSIONS); the exact
    # terminal extended-horizon GPT slugs — GPT 5.6 Sol and GPT-6 Astra
    # (validated), plus GPT-6 Sol, GPT-6.1 Sol, and the flagship -pro form of
    # each (see GPT_EXTENDED_RE and POLICY ADMISSIONS) — use 60/75/90%
    # percentage gates with their own 300/400/500k absolute gates. Each is matched
    # only as the bare slug or the final segment of a provider path (the ERE is
    # tested against the provider-stripped terminal slug); left- or
    # right-boundary near misses (xgpt-6-astra, gpt-6-astra-pro-x,
    # gpt-6-astra-mini, gpt-6-astra[1m]-x, gpt-6-sol[1m]-pro) and gpt-6-luna
    # (1.05M window, conservative profile like gpt-5.6-luna) fall through to
    # the conservative profile.
    #
    # Opus 5.5 (claude-opus-5-5, bare or [1m]) JOINS the
    # extended-horizon arm below by user policy (see POLICY ADMISSIONS), on the
    # model's documented long-horizon design ("built for long-running agentic
    # coding and knowledge work"), not on a DAAF quality measurement past
    # 300k. The Opus 5.5
    # pattern is BOUNDARY-ANCHORED, not a substring glob: this arm GRANTS a
    # privilege (relaxed gates), and a privilege-granting arm must name exactly
    # what it privileges. A loose `*opus-5-5*` would silently hand the 40/50/60%
    # gates to any future slug merely containing that text — `claude-opus-5-5-mini`
    # on the right, `xclaude-opus-5-5` on the left — neither of which the user
    # policy decision covers. The accepted forms are therefore the bare slug or a
    # provider path whose FINAL segment is exactly claude-opus-5-5 or its [1m]
    # form, the same anchoring convention the GPT extended-tier test below
    # already uses (and for the same reason). Bare Opus 5 and every other Opus
    # model — plus every near miss — stay conservative-default via the `*`
    # fallthrough arm, which tests/bash/context_reporter.bats locks. The
    # physical-window case block above keeps its broad `*opus-5-5*`
    # deliberately: mapping a window is not a privilege grant. $model arrives
    # already normalized (normalize_model_id), so a provider-dotted
    # anthropic/claude-opus-5.5 reaches this arm as anthropic/claude-opus-5-5.
    # Kept lockstep-identical with .claude/scripts/subagent-bar.sh. The six
    # threshold assignment lines below must match that file byte for byte
    # (numeric lockstep test in tests/bash/context_reporter.bats).
    local elev_pct high_pct crit_pct elev_k high_k crit_k
    case "$model" in
        *fable-5*|*mythos-5*|claude-opus-5-5|*/claude-opus-5-5|claude-opus-5-5\[1m\]|*/claude-opus-5-5\[1m\])
            elev_pct=40; high_pct=50; crit_pct=60
            elev_k=400;  high_k=500;  crit_k=600 ;;
        *)
            if [[ "${model##*/}" =~ $GPT_EXTENDED_RE ]]; then
                elev_pct=60; high_pct=75; crit_pct=90
                elev_k=300;  high_k=400;  crit_k=500
            else
                elev_pct=40; high_pct=60; crit_pct=75
                elev_k=150;  high_k=200;  crit_k=250
            fi
            ;;
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

# A corrupt or future gate timestamp would make (NOW - LAST_INJECT)
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

# Update the per-agent timestamp gate. Wrap the redirection so an
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
