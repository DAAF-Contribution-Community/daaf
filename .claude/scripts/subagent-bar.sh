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
# Re-verified against CC 2.1.202 behaviorally (live subagent model caches +
# per-model window computations, 2026-07-15 session). See
# research/2026-07-15_FrameworkDev_ClaudeCode_Upgrade_2.1.202.
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
#   real assistant entry of agent-<id>.jsonl, cached in the compatibility path
#   /tmp/claude-subagent-model-<session>-<id> with a transcript-signature
#   sidecar (shared with context-reporter.sh), and drives the per-row window
#   denominator (see the loop; CLAUDE_CODE_MAX_CONTEXT_TOKENS, when set to a
#   positive integer,
#   ordinarily overrides the per-model mapping there, after which the matched
#   ChatGPT-subscription/Codex flagship route is finally capped at 370k).
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
# ANSI-C quoting ($'…') so the ESC byte lives in these TRUSTED constants, not in
# a printf '%b' pass over the assembled string (Convention 1). The final render
# uses printf '%s' (see the emit step), so a printable backslash escape arriving
# in an untrusted field (model name, agentType, description) stays inert rather
# than being re-materialized into a real ESC/OSC/BEL sequence.
C_RESET=$'\033[0m'
C_GRAY=$'\033[38;5;245m'
C_BAR_EMPTY=$'\033[38;5;238m'
# Severity palette aligned to the Context Quality Curve. The exact numeric
# thresholds are quality-tier conditional (see the per-row severity block near
# the bottom of the loop): Fable/Mythos patterns use ELEVATED >= 30% OR >= 300k,
# HIGH >= 40% OR >= 400k, and CRITICAL >= 50% OR >= 500k. Exact terminal GPT
# 5.6 Sol slugs use 60%/75%/90% percentage gates while retaining the
# larger 300k/400k/500k absolute gates. Every other model — including Opus,
# Sonnet, other GPT variants, GLM, and unknown ids — uses ELEVATED >= 40% OR >=
# 150k, HIGH >= 60% OR >= 200k, and CRITICAL >= 75% OR >= 250k. Each severity
# keeps one color regardless of tier:
#   NOMINAL  green
#   ELEVATED amber
#   HIGH     orange  (bold to distinguish from amber)
#   CRITICAL red
C_NOMINAL=$'\033[38;5;71m'    # green
C_ELEVATED=$'\033[38;5;179m'  # amber
C_HIGH=$'\033[1;38;5;173m'    # orange, bold
C_CRITICAL=$'\033[38;5;167m'  # red

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

# Bounded identifier allowlist for values interpolated into cache/transcript
# paths (session_id, per-agent id). Leading alnum, then alnum/dot/underscore/
# hyphen, max 128 chars (Convention 2). Rejects slashes, traversal (..), control
# chars, leading dash, empty, and >128. A present-but-invalid id is rejected
# exactly like an absent one (key-presence contract shared with context-bar.sh
# and the provider shim). Same name + regex across the hardened renderers.
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
# path consumed by older DAAF components. The neighboring
# .transcript-signature sidecar is the commit marker: unchanged signatures reuse
# the nonempty cache without parsing; changed signatures refresh from the last
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
        # Full-transcript scan (Convention 4): no `tail -n 50` bound, so more than
        # 50 trailing synthetic/placeholder model entries cannot hide the last
        # real model. The `< "$transcript"` redirect keeps a missing/binary file
        # fail-open, mirroring context-bar.sh's recovery idiom.
        model=$(jq -rs '
            [.[] | (.message.model // empty)
             | select(. != "" and . != "<synthetic>")] | last // empty
        ' < "$transcript" 2>/dev/null) || model=""
    fi
    [[ -z "$model" ]] && model="$cached_model"

    if [[ -n "$model" && -n "$signature" ]]; then
        # Group the writes+moves under ONE stderr redirect (Convention 6): a
        # `> "$tmp"` open() failure emits its diagnostic BEFORE a trailing
        # `2>/dev/null` on the same simple command takes effect, so the whole
        # sequence is wrapped to suppress the open() error too. If the cache dir
        # is unusable, drop the temps and continue without caching (fail-open).
        if {
            printf '%s' "$model" > "$model_tmp" &&
            printf '%s' "$signature" > "$signature_tmp" &&
            mv -- "$model_tmp" "$cache" &&
            mv -- "$signature_tmp" "$signature_cache"
        } 2>/dev/null; then
            :
        else
            rm -f "$model_tmp" "$signature_tmp" 2>/dev/null
        fi
    fi

    [[ -n "$model" ]] && printf '%s' "$model"
}

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

# Reject a present-but-unsafe session id before it reaches any cache/transcript
# path (Convention 2). Blanking it makes every session-scoped cache read/write
# below no-op via the existing [[ -n "$session_id" ]] guards, and the window
# falls back to the newest cache / 200k default — fail-open, no row lost.
is_safe_id "$session_id" || session_id=""

# Cache base dir. Production caches live in /tmp; the override is a
# deterministic-test seam (mirrors context-bar.sh's DAAF_CONTEXT_BAR_CACHE_DIR)
# so bats can point writes at project scratch and exercise ENOTDIR paths without
# touching live session state. Default preserves production behavior exactly.
cache_dir="${DAAF_SUBAGENT_BAR_CACHE_DIR:-/tmp}"

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
if [[ -n "$session_id" && -f "${cache_dir}/claude-ctx-window-${session_id}" ]]; then
    max_context=$(cat "${cache_dir}/claude-ctx-window-${session_id}" 2>/dev/null)
fi
if [[ -z "$max_context" ]]; then
    latest_ctx=$(ls -t "${cache_dir}"/claude-ctx-window-* 2>/dev/null | head -1)
    if [[ -n "${latest_ctx:-}" ]]; then
        max_context=$(cat "$latest_ctx" 2>/dev/null)
    fi
fi
# Guard: must be a positive integer, else fall back to 200k.
if ! is_canonical_positive_decimal "$max_context"; then
    max_context=200000
fi

# Session model — used to decide whether a subagent shares the session's window
# or needs the per-model mapping below. Resolve it against the main transcript's
# current signature so a real model switch cannot leave the comparison stale.
session_model=""
if [[ -n "$session_id" ]]; then
    session_model=$(resolve_model_cache "$transcript_path" "${cache_dir}/claude-model-${session_id}")
fi

# --- Extract tasks (single jq pass, one \x1f-joined record per line) ---
# Fields: id, type, name, status, tokenCount, label. Tasks with an empty id
# are dropped (they cannot be keyed in the output). label/name are sanitized
# of newlines/tabs/\x1f so one task always stays one record line.
tasks_rec=$(printf '%s' "$input" | jq -r '
    # clean strips ALL C0 controls + DEL (Convention 1), not just \n\r\t\x1f: a
    # JSON-escaped control (e.g. an escaped ESC) parses to a real ESC byte here,
    # so stripping it stops the byte reaching the rendered row. Replacement is a
    # space (not "") to preserve the \x1f record structure. C1 bytes are handled
    # upstream: jq rejects raw C1 in JSON input, so they never reach this stage.
    def clean: tostring | gsub("[[:cntrl:]]"; " ");
    (.tasks // [])[]
    # id must be a string (Convention 2): a JSON number/object id is malformed
    # input and is dropped here; a path-unsafe string id is rejected later by
    # is_safe_id in the render loop before any path is built from it.
    | select((.id | type) == "string")
    | select((.id | clean) != "")
    | [ (.id | clean),
        (.type // "" | clean),
        (.name // "" | clean),
        (.status // "" | clean),
        ((.tokenCount // 0) | tostring),
        ((.label // .description // "") | clean) ]
    | join("\u001f")
' 2>/dev/null) || exit 0

[[ -z "$tasks_rec" ]] && exit 0

# Closed-set GPT classifier grammar (Convention 3). Anchored EREs on the
# provider-stripped terminal slug replace the old open-ended case-globs
# (gpt-5.6[-\[]*), which mapped malformed ids (gpt-5.6-experimental,
# gpt-5.6-sol[1m]x, gpt-5.4-) into the 1.05M physical window. A new codename is a
# deliberate one-line registry edit here, consistent with validate-before-trust.
#   flagship  -> 1,050,000 physical window + eligible for the 370k ChatGPT cap
#   mini      -> 400,000
#   chat      -> 128,000
#   prev (gpt-5 / gpt-5.2) -> 400,000, or 128,000 for its -chat variant
gpt_flagship_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?(\[1m\])?$'
gpt_mini_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-mini(\[1m\])?$'
gpt_chat_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-chat(\[1m\])?$'
gpt_prev_re='^gpt-5(\.2)?(-mini)?(\[1m\])?$'
gpt_prev_chat_re='^gpt-5(\.2)?-chat(\[1m\])?$'

# --- Render one output line per task ---
bar_width=5
while IFS=$'\x1f' read -r id type name status tokens label; do
    # Reject a path-unsafe agent id before it is interpolated into any transcript
    # or cache path (Convention 2); omit the row, keep the native rendering.
    # is_safe_id also subsumes the empty-id guard (the regex requires >=1 char).
    is_safe_id "$id" || continue

    # Normalize token count to a non-negative integer (strip any fraction).
    tokens=${tokens%.*}
    [[ "$tokens" =~ ^[0-9]+$ ]] || tokens=0

    # Transcript fallback for shim-routed (GPT) subagents: the harness stdin
    # .tokenCount field is 0/absent for shim-routed subagents, so the panel
    # would render "0 ░░░░░ 0%" for the whole task. When tokenCount is <= 0,
    # recover the count from the subagent's own transcript (path already used
    # for the model lookup just below) with the SAME last-POSITIVE-usage logic
    # as context-reporter.sh calculate(). Subagent transcripts are entirely
    # isSidechain:true, so no sidechain filter is needed. Shim transcripts end
    # with streaming-placeholder usage entries whose token fields are all 0, so
    # `last` outright would recover 0 too — map to token sums, drop zeros, take
    # the last positive. Fail-open: only attempt when the transcript file
    # exists; any jq failure yields empty, and the numeric re-guard leaves
    # tokens at 0 (which keeps native rendering, this script's failure mode).
    if [[ "$tokens" -le 0 && -n "$subagents_dir" && -f "${subagents_dir}/agent-${id}.jsonl" ]]; then
        # Full-transcript scan (Convention 4): drop the `tail -n 50` bound so more
        # than 50 trailing zero-token shim placeholders cannot hide the real
        # usage. The `< file` redirect keeps a missing/binary transcript
        # fail-open, mirroring context-bar.sh's recovery idiom.
        tokens=$(jq -s '
            [.[] | select(.message.usage and .isApiErrorMessage != true) | (
                (.message.usage.input_tokens // 0) +
                (.message.usage.cache_read_input_tokens // 0) +
                (.message.usage.cache_creation_input_tokens // 0)
            )] | map(select(. > 0)) | last // 0
        ' < "${subagents_dir}/agent-${id}.jsonl" 2>/dev/null) || tokens=0
        tokens=${tokens%.*}
        [[ "$tokens" =~ ^[0-9]+$ ]] || tokens=0
    fi

    # Per-row context window: a subagent on a different model than the session
    # gets a different window than the session's (e.g. a sonnet subagent
    # dispatched from a 1M fable session is provisioned 200k — its bar must
    # not be computed against 1M). The transcript-signature sidecar makes the
    # shared bare cache append/rewrite-aware while avoiding rescans during the
    # ~300ms panel refresh cycle when the transcript has not changed.
    task_model=""
    model_cache=""
    task_transcript=""
    [[ -n "$session_id" ]] && model_cache="${cache_dir}/claude-subagent-model-${session_id}-${id}"
    [[ -n "$subagents_dir" ]] && task_transcript="${subagents_dir}/agent-${id}.jsonl"
    if [[ -n "$model_cache" ]]; then
        task_model=$(resolve_model_cache "$task_transcript" "$model_cache")
    fi
    # Control-strip the resolved model id before it is used for display
    # (agent_disp) or slug classification (Convention 1). The bare cache file is
    # read with `cat`, so a corrupt/hostile cache is the one path that can carry
    # raw control bytes past the payload clean; a legitimate model id never
    # contains them. jq -Rs makes the strip Unicode-aware: gsub([[:cntrl:]])
    # removes C0, DEL, AND C1 (U+0080-U+009F — Oniguruma's [[:cntrl:]] is the
    # Unicode Cc category, unlike byte-wise bash/tr ranges, which pass
    # UTF-8-encoded C1 through), and jq's UTF-8 decoding replaces raw stray
    # bytes (a lone 8-bit C1) with inert U+FFFD. Slurp (-s) keeps an embedded
    # newline inside the one string so it is stripped rather than re-emitted as
    # a second line. Fail-open: on any jq failure the model reads as unresolved
    # (empty) and the row still renders.
    task_model=$(printf '%s' "$task_model" | jq -Rsr 'gsub("[[:cntrl:]]"; "")' 2>/dev/null) || task_model=""
    # Default: the session window (covers same-model subagents and alternative
    # providers, where the mapping below does not apply).
    row_window="$max_context"
    if [[ -n "$task_model" && "$task_model" != "$session_model" ]]; then
        # Window provisioning summary: GPT mini and broad gpt-5 ids map to 400k,
        # chat variants to 128k, and 5.4/5.5/5.6 flagships to 1.05M; exact
        # z-ai/glm-5.2 and only terminal -YYYYMMDD snapshots map to 1,048,576;
        # native 1M Claude models
        # and generic [1m]-suffixed Claude ids map to 1,000,000; all other models
        # map to 200,000. This broad physical-window map is separate from the
        # quality-tier selector below, where exact terminal GPT 5.6 Sol slugs
        # retain larger absolute gates. Re-verify this map after Claude
        # Code/provider updates.
        # Physical GPT classification uses only the terminal provider-stripped
        # slug. Supported flagship versions must start that slug and be followed
        # by end-of-slug, '-' or '['; mini/chat retain precedence.
        physical_slug="${task_model##*/}"
        case "$task_model" in
            # Exact GLM-5.2 plus terminal date snapshots only. Keep this narrow:
            # glm-5.2-air and future variants have no verified static window.
            # Window size only — GLM remains in the conservative threshold family.
            z-ai/glm-5.2|z-ai/glm-5.2-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
                row_window=1048576 ;;
            *)
                # Closed-set classification on the provider-stripped slug
                # (Convention 3). Only the enumerated flagship/mini/chat/prev
                # slugs earn a GPT physical window; anything else (malformed
                # flagship-looking ids included) falls through to the
                # conservative Claude/[1m]/200k map. Order: flagship, then mini,
                # then chat before prev so a prev-chat is not shadowed.
                if   [[ "$physical_slug" =~ $gpt_flagship_re ]];  then row_window=1050000
                elif [[ "$physical_slug" =~ $gpt_mini_re ]];      then row_window=400000
                elif [[ "$physical_slug" =~ $gpt_chat_re ]];      then row_window=128000
                elif [[ "$physical_slug" =~ $gpt_prev_chat_re ]]; then row_window=128000
                elif [[ "$physical_slug" =~ $gpt_prev_re ]];      then row_window=400000
                else
                    case "$task_model" in
                        *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*\[1m\]*)
                            row_window=1000000 ;;
                        *) row_window=200000 ;;
                    esac
                fi
                ;;
        esac
    fi

    # CLAUDE_CODE_MAX_CONTEXT_TOKENS is the ordinary user override. Apply it to
    # same-model and different-model rows before the backend-specific final cap.
    if is_canonical_positive_decimal "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}"; then
        row_window="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
    fi

    # ChatGPT-subscription/Codex final physical-window accounting constraint.
    # Canonical activation requires BOTH exact lane signals and a task model in
    # the existing gpt-5.4/5.5/5.6 flagship arm; mini/chat variants are excluded
    # by ordering. Probe 2026-07-16 (gpt-5.6-sol) accepted 369,941 real input
    # tokens and rejected 372,905, so 370000 is the lane-wide accounting ceiling
    # for this arm. Apply min(resolved, 370000) after cache/model/override
    # resolution so stale same-model caches and unsafe explicit declarations are
    # capped while lower positive values survive. This is utilization/statusline
    # accounting, NOT compaction and NOT a transport-level request blocker; the
    # backend remains the ultimate hard ceiling.
    # Flagship predicate for the ChatGPT-lane cap uses the SAME closed-set ERE
    # (Convention 3); mini/chat slugs simply do not match it, so no explicit
    # exclusion arm is needed. The 370k min-ceiling ordering below is unchanged.
    gpt_flagship=0
    physical_slug="${task_model##*/}"
    if [[ "$physical_slug" =~ $gpt_flagship_re ]]; then
        gpt_flagship=1
    fi
    if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
          "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
          "$gpt_flagship" -eq 1 ]] && \
       is_canonical_positive_decimal "$row_window" && \
       [[ "$row_window" -gt 370000 ]]; then
        row_window=370000
    fi

    # Guard: must be a canonical positive decimal, else fall back to 200k.
    if ! is_canonical_positive_decimal "$row_window"; then
        row_window=200000
    fi

    # Numerator bound (Convention 5): tokens is already ^[0-9]+$, but an int64-
    # valid value above floor(INT64_MAX/100)=92233720368547758 would overflow
    # tokens*100 below and wrap pct negative. row_window is already validated
    # above; bound the numerator symmetrically. tokens==0 is legitimate (0%), so
    # only non-zero values are checked; is_canonical_positive_decimal guarantees
    # tokens<=INT64_MAX first, making the -gt comparison itself overflow-safe.
    if [[ "$tokens" != "0" ]] && \
       { ! is_canonical_positive_decimal "$tokens" || [[ "$tokens" -gt 92233720368547758 ]]; }; then
        tokens=0
    fi

    pct=$((tokens * 100 / row_window))
    [[ $pct -gt 100 ]] && pct=100
    used_k=$((tokens / 1000))

    # Threshold tier (percentage AND absolute k-token gates per severity), keyed
    # on the measured agent's model. Fable/Mythos keep the validated 30/40/50%
    # extended-horizon gates plus 300/400/500k absolute gates. Exact GPT 5.6 Sol
    # ids use 60/75/90% gates while retaining 300/400/500k absolutes.
    # Everything else — INCLUDING opus-4-8[1m], whose 1M window does NOT relax
    # its Opus-class quality horizon — gets 40/60/75% plus 150/200/250k. GPT Sol
    # matching accepts the bare slug or a provider path only when its final
    # segment is exactly gpt-5.6-sol or gpt-5.6-sol[1m]; left- or right-boundary
    # near misses and unknown/empty models fall through to the conservative
    # default (fail-conservative). Deliberately different from the physical-
    # window case block above — the broad GPT 5.6 physical map does not imply the
    # exact Sol quality-tier rule. See CLAUDE.md § Context Quality Curve for the
    # authoritative threshold table.
    case "$task_model" in
        *fable-5*|*mythos-5*)
            elev_pct=30; high_pct=40; crit_pct=50
            elev_k=300;  high_k=400;  crit_k=500 ;;
        gpt-5.6-sol|*/gpt-5.6-sol|gpt-5.6-sol\[1m\]|*/gpt-5.6-sol\[1m\])
            elev_pct=60; high_pct=75; crit_pct=90
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
        # Control-strip agentType (Convention 1): this sidecar read bypasses the
        # main-payload clean, so a JSON-escaped control in agentType would
        # otherwise reach the row. jq rejects raw C1 in the file, and gsub
        # removes any C0/DEL that arrived as a JSON escape.
        agent_disp=$(jq -r '(.agentType // empty) | tostring
            | gsub("[[:cntrl:]]"; " ")' \
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

    # Emit {"id","content"} as ONE compact JSON line. Color CSI bytes already
    # live as real ESC in the trusted $'…' constants, so the render uses
    # printf '%s' — NOT '%b' (Convention 1): a printable backslash escape in an
    # untrusted field (model name, agentType, description) stays inert instead of
    # being re-materialized into a real ESC/OSC/BEL. jq (-R raw, -s slurp,
    # -c compact) then JSON-encodes the line. Note that JSON-encoding ALONE does
    # NOT neutralize escapes — the consumer decodes  back to ESC — which is
    # why untrusted fields are control-stripped at extraction (clean, the
    # agentType read, and task_model) rather than relying on the encode step.
    printf '%s' "$content" | jq -Rsc --arg id "$id" '{id: $id, content: .}' 2>/dev/null
done <<< "$tasks_rec"

exit 0
