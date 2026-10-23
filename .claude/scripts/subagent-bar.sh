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
#     tokenCount   — native progress count; may be output-only on late-usage streams
#     tokenSamples — rolling number[] window
#     cwd          — task cwd
#     model        — optional task model (present in CC 2.1.261); startup fallback
#   The DAAF agent type (e.g. "search-agent") is NOT in the payload; it lives
#   in the sidecar $(dirname transcript_path)/<session_id>/subagents/
#   agent-<id>.meta.json (key: agentType) and is looked up per row, fail-open.
#   The subagent's MODEL is preferentially read from the last
#   real assistant entry of agent-<id>.jsonl, cached in the compatibility path
#   /tmp/claude-subagent-model-<session>-<id> with a transcript-signature
#   sidecar (shared with context-reporter.sh), and drives the per-row window
#   denominator (see the loop; CLAUDE_CODE_MAX_CONTEXT_TOKENS, when set to a
#   positive integer,
#   ordinarily overrides the per-model mapping there, after which the matched
#   ChatGPT-subscription/Codex flagship route is finally capped at 919k).
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
# the bottom of the loop): Fable/Mythos patterns, plus Opus 5.5
# (claude-opus-5-5, bare or [1m]; admitted to this tier by user policy
# decision 2026-09-23, not validation), use ELEVATED >= 40% OR >= 400k,
# HIGH >= 50% OR >= 500k, and CRITICAL >= 60% OR >= 600k. These numbers date
# from a user policy decision of 2026-10-23, not validation, which raised the
# tier from 30/40/50% OR 300/400/500k (the levels Fable/Mythos were
# validated at). The exact terminal
# extended-horizon GPT slugs — GPT 5.6 Sol and GPT-6 Astra (validated), plus
# GPT-6 Sol, GPT-6.1 Sol, and the flagship -pro form of each (user policy
# decisions 2026-09-29 and 2026-10-12, not validation; see gpt_extended_re) — use 60%/75%/90%
# percentage gates while retaining their 300k/400k/500k absolute gates.
# Every other model — including every other Opus model (Opus 5 included),
# Sonnet, other GPT variants (GPT-6 Luna, Terra, mini, chat), GLM, and unknown
# ids — uses ELEVATED >= 40% OR >=
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
        model=$(jq -Rnr '
            [inputs | fromjson? | objects | select(.isApiErrorMessage != true)
             | .message? | objects | .model? | strings
             | select(. != "" and . != "<synthetic>")] | last // empty
        ' 2>/dev/null < "$transcript") || model=""
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

# Provider-dotted Claude model ids (added 2026-09-29). OpenRouter reports Claude
# models with a DOTTED version (anthropic/claude-opus-5.5, claude-opus-4.8,
# claude-opus-5.5[1m]), while every Claude pattern in this script expects
# Anthropic's hyphenated form (claude-opus-5-5). Reproduced 2026-09-29 against
# the live scripts: a dotted Opus 5.5 row missed the anchored extended-horizon
# profile arm (250k read CRITICAL, not NOMINAL), and a dotted Opus 4.8 row missed
# the *opus-4-8* window arm (150k read 75% of 200k, not 15% of 1M).
# normalize_model_id rewrites ONLY an id that ENDS in
# claude-<family>-<major>.<minor>, optionally followed by [1m], to the
# hyphenated form, keeping any provider prefix (anthropic/claude-opus-5.5 ->
# anthropic/claude-opus-5-5, which the anchored */claude-opus-5-5 arm already
# matches). Every other id passes through unchanged, so near misses such as
# anthropic/claude-opus-5.5-mini stay conservative (fail-conservative) and GPT
# ids are never touched. It is applied at CLASSIFICATION points only (the
# same/different-model comparison, the physical-window lookup, the ChatGPT-lane
# flagship predicate, and the quality tier); model caches and the visible row
# label keep the RAW name. The block between the section-sign markers is kept
# BYTE-IDENTICAL with .claude/hooks/context-reporter.sh (lockstep test in
# tests/bash/context_reporter.bats). Provenance:
# research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames (OpenRouter
# catalogue, which lists the dotted ids anthropic/claude-opus-5.5, -4.8, -4.7
# and claude-fable-5.1: web_fetches/2026-09-29T160403Z_openrouter-ai_untitled_051e0609.json).
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
# Same precedence as context-reporter.sh: THIS session's cache written by
# context-bar.sh when present (authoritative — Claude Code's provisioned
# window, with the static map/override/lane cap already applied), else the
# static map for the session model (filled in below, once the model and the
# classifier grammars are available), else 200000. Deliberately NO fallback to
# "the most recent cache from any session": that inherited an unrelated
# session's window into this one. This script NEVER writes the cache.
max_context=""
if [[ -n "$session_id" && -f "${cache_dir}/claude-ctx-window-${session_id}" ]]; then
    max_context=$(cat "${cache_dir}/claude-ctx-window-${session_id}" 2>/dev/null)
fi
# Guard: must be a canonical positive integer, else leave EMPTY for the
# model-keyed fallback below.
if ! is_canonical_positive_decimal "$max_context"; then
    max_context=""
fi

# Session model — used to decide whether a subagent shares the session's window
# or needs the per-model mapping below. Resolve it against the main transcript's
# current signature so a real model switch cannot leave the comparison stale.
session_model=""
if [[ -n "$session_id" ]]; then
    session_model=$(resolve_model_cache "$transcript_path" "${cache_dir}/claude-model-${session_id}")
fi

# --- Extract tasks (single jq pass, one \x1f-joined record per line) ---
# Fields: id, type, name, status, tokenCount, label, optional model. Tasks with an empty id
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
        ((.label // .description // "") | clean),
        # Reject malformed/control-bearing models rather than sanitize into a match.
        (if (.model | type) == "string" then
             # $ can match before a final newline; require absolute boundaries
             # and reject controls before joining newline-delimited task records.
             if (.model | test("[[:cntrl:]]") | not) and
                (.model | test("\\A[A-Za-z0-9][A-Za-z0-9._/\\[\\]-]{0,255}\\z"))
             then .model else "" end
         else "" end) ]
    | join("\u001f")
' 2>/dev/null) || exit 0

[[ -z "$tasks_rec" ]] && exit 0

# Closed-set GPT classifier grammar (Convention 3). Anchored EREs on the
# provider-stripped terminal slug replace the old open-ended case-globs
# (gpt-5.6[-\[]*), which mapped malformed ids (gpt-5.6-experimental,
# gpt-5.6-sol[1m]x, gpt-5.4-) into the 1.05M physical window. A new codename is a
# deliberate one-line registry edit here, consistent with validate-before-trust.
# The flagship grammar covers the gpt-5.4/5.5/5.6 family plus the GPT-6
# flagships gpt-6-astra, gpt-6-sol, and gpt-6-luna; mini/chat stay gpt-5-only,
# so gpt-6-astra-mini, gpt-6-sol-chat, etc. fall through to the conservative
# default (no evidence such GPT-6 variants exist — near misses stay
# conservative).
# USER POLICY DECISION 2026-09-29, not validation
# (research/2026-09-29_FrameworkDev_OpenRouterDottedModelNames): (1) any
# FLAGSHIP -pro model reads exactly as its non-pro base — same physical window,
# same 919k ChatGPT-lane cap eligibility, same quality tier. -pro sits
# immediately before the optional [1m] (gpt-6-sol-pro[1m] accepted,
# gpt-6-sol[1m]-pro rejected); mini/chat -pro spellings (gpt-5.6-mini-pro) are
# not flagships and stay conservative. (2) gpt-6-sol is treated identically to
# gpt-5.6-sol and gpt-6-luna identically to gpt-5.6-luna. There is NO
# gpt-6-terra (retired for the GPT-6 generation, per the user); it and every
# other GPT-6 name (bare gpt-6, GPT-6 mini/chat) stay unregistered. Windows
# per the OpenRouter catalogue fetched 2026-09-29 (context_length 1050000 for
# openai/gpt-6-sol, gpt-6-sol-pro, gpt-6-luna, gpt-6-luna-pro, gpt-6-astra-pro,
# gpt-5.6-{sol,terra,luna}-pro, gpt-5.5-pro, gpt-5.4-pro; no gpt-6-terra entry):
# web_fetches/2026-09-29T160403Z_openrouter-ai_untitled_051e0609.json in that
# workspace. Capping at 919k can only make a reading more conservative.
# USER POLICY DECISION 2026-10-12, not validation: gpt-6.1-sol (one exact
# alternative, optional -pro and [1m]) is treated identically to gpt-6-sol —
# 1,050,000 window, 919k ChatGPT-lane cap (ceiling measured 2026-10-13: accepted
# 919,744, rejected 921,973), extended quality tier. Window per OpenRouter openai/gpt-6.1-sol
# fetched 2026-10-12
# (research/2026-09-06_FrameworkDev_GPT_Shim_Native_Search/web_fetches/opus_audit_2026-10-12/).
# No gpt-6.1-* wildcard: gpt-6.1-luna, gpt-6.1-sol-mini, etc. stay unregistered.
#   flagship  -> 1,050,000 physical window + eligible for the 919k ChatGPT cap
#   mini      -> 400,000
#   chat      -> 128,000
#   prev (gpt-5 / gpt-5.2) -> 400,000, or 128,000 for its -chat variant
# gpt_extended_re is the QUALITY-TIER grammar (60/75/90% + 300/400/500k),
# deliberately narrower than the flagship window grammar: gpt-5.6-sol and
# gpt-6-astra (validated), plus gpt-6-sol, gpt-6.1-sol, and the -pro form of
# each (policy decisions above). Tested against the provider-stripped terminal slug,
# so a bare slug or a provider path whose FINAL segment matches is accepted and
# left-boundary near misses (xgpt-6-astra, foo-gpt-5.6-sol,
# vendor/notgpt-5.6-sol) stay conservative. Kept byte-identical with
# GPT_EXTENDED_RE / GPT_FLAGSHIP_RE in .claude/hooks/context-reporter.sh and
# gpt_flagship_re in .claude/scripts/context-bar.sh. The full three-way ERE
# lockstep test lives in tests/bash/context_reporter.bats;
# tests/bash/subagent_bar.bats locks only gpt_flagship_re against context-bar.sh
# (plus the literal gpt_extended_re value).
gpt_flagship_re='^(gpt-5\.(4|5|6)(-(sol|terra|luna))?|gpt-6-(astra|sol|luna)|gpt-6\.1-sol)(-pro)?(\[1m\])?$'
gpt_extended_re='^(gpt-5\.6-sol|gpt-6-(astra|sol)|gpt-6\.1-sol)(-pro)?(\[1m\])?$'
gpt_mini_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-mini(\[1m\])?$'
gpt_chat_re='^gpt-5\.(4|5|6)(-(sol|terra|luna))?-chat(\[1m\])?$'
gpt_prev_re='^gpt-5(\.2)?(-mini)?(\[1m\])?$'
gpt_prev_chat_re='^gpt-5(\.2)?-chat(\[1m\])?$'

# static_window_for_model: map a model id to the physical context window Claude
# Code provisions for it. Echoes a canonical positive integer; unknown or empty
# ids map to the conservative 200000. Window provisioning summary: GPT mini and
# broad gpt-5 ids map to 400k, chat variants to 128k, and 5.4/5.5/5.6 flagships
# (plus gpt-6-astra/-sol/-luna, and the flagship -pro forms) to 1.05M; callers
# pass the normalize_model_id form, so provider-dotted Claude ids reach the
# Claude arms hyphenated; exact z-ai/glm-5.2 and only terminal -YYYYMMDD
# snapshots map to 1,048,576; native 1M Claude models (Fable/Mythos 5, Opus
# 4.7/4.8, Opus 5) and generic [1m]-suffixed Claude ids map to 1,000,000; all
# other models map to 200,000. This broad physical-window map is separate from
# the quality-tier selector in the row loop. Re-verify after Claude Code /
# provider updates. OUTPUT-consistent (not byte-identical — the code shape
# differs) with context-reporter.sh's function of the same name: the GPT EREs
# and the flagship-family pre-filter glob are copied verbatim, so every
# flagship/mini/chat id and every malformed flagship-family id maps to the
# same window in both (and in context-bar.sh's static map; cross-script
# agreement tests in tests/bash/subagent_bar.bats and
# tests/bash/context_reporter.bats). One KNOWN, pre-existing difference is
# deliberately left as is: malformed gpt-5 / gpt-5.2-family spellings
# (e.g. gpt-5-pro) map to 200k here via the anchored prev EREs (1M if the id
# carries [1m], via the generic Claude arm), but to 400k (128k for *-chat*) in
# the reporter's and context-bar's broad gpt-5 globs.
# Opus 5 (claude-opus-5, bare AND [1m]) is a native 1M-window model: observed
# 2026-09-05 on Claude Code 2.1.261 via /model + /context — bare
# `claude-opus-5` reported "42.8k/1m tokens" and `claude-opus-5[1m]` reported
# "48.2k/1m", so the bare id must map to 1,000,000 too and not fall through to
# the 200k arm. Opus 5 nonetheless stays on the CONSERVATIVE quality profile
# (physical window and quality threshold are separate lookups). Provenance:
# research/2026-09-05_FrameworkDev_ClaudeCode_Upgrade_2.1.261 (to-do 03 Branch A).
# Opus 5.5 (claude-opus-5-5, bare AND [1m]) is likewise a native 1M-window model
# (Claude Code CHANGELOG 2.1.280: "Added Claude Opus 5.5 (`claude-opus-5-5`),
# now the default Opus model — 1M context"; platform docs "Context window / 1M
# tokens"). The pre-existing `*opus-5*` arm ALREADY substring-matched
# `claude-opus-5-5` — proven by an executed `case` repro on 2026-09-23 — so the
# explicit `*opus-5-5*` arm below changes no behavior. It is added for
# auditability: the implicit match is correct only by coincidence (it happens to
# be right because 5.5 is genuinely 1M), and the next Opus generation may not be.
# Provenance: research/2026-09-23_FrameworkDev_ClaudeCode_Upgrade_2.1.280.
static_window_for_model() {
    local model="${1:-}"
    local slug="${model##*/}"
    local window=200000
    case "$model" in
        # Exact GLM-5.2 plus terminal date snapshots only. Keep this narrow:
        # glm-5.2-air and future variants have no verified static window.
        # Window size only — GLM remains in the conservative threshold family.
        z-ai/glm-5.2|z-ai/glm-5.2-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9])
            window=1048576 ;;
        *)
            # Closed-set classification on the provider-stripped slug
            # (Convention 3). Only the enumerated flagship/mini/chat/prev slugs
            # earn a GPT physical window; malformed gpt-5.4/5.5/5.6/GPT-6
            # flagship-family ids then map to 200k via the family pre-filter
            # below, and everything else falls through to the Claude/[1m]/200k
            # map. Order: flagship, then mini, then chat before prev so a
            # prev-chat is not shadowed.
            if   [[ "$slug" =~ $gpt_flagship_re ]];  then window=1050000
            elif [[ "$slug" =~ $gpt_mini_re ]];      then window=400000
            elif [[ "$slug" =~ $gpt_chat_re ]];      then window=128000
            elif [[ "$slug" =~ $gpt_prev_chat_re ]]; then window=128000
            elif [[ "$slug" =~ $gpt_prev_re ]];      then window=400000
            else
                case "$slug" in
                    # GPT flagship-family pre-filter, copied verbatim from the
                    # family glob in context-reporter.sh's and context-bar.sh's
                    # static maps (2026-09-29 review fix). An id that reaches
                    # here matched none of the anchored EREs above, so a
                    # family-glob hit is a MALFORMED flagship-family id
                    # (gpt-6-sol[1m]-pro, gpt-6-sol-mini[1m], gpt-6-astra[1m]-x,
                    # gpt-5.6-sol[1m]x): map it to the conservative 200000
                    # BEFORE the generic Claude *\[1m\]* arm below can hand it
                    # 1,000,000, so all three scripts agree on the window.
                    gpt-5.4|gpt-5.4[-\[]*|gpt-5.5|gpt-5.5[-\[]*|gpt-5.6|gpt-5.6[-\[]*|gpt-6-astra|gpt-6-astra[-\[]*|gpt-6-sol|gpt-6-sol[-\[]*|gpt-6-luna|gpt-6-luna[-\[]*|gpt-6.1-sol|gpt-6.1-sol[-\[]*)
                        window=200000 ;;
                    *)
                        case "$model" in
                            *fable-5*|*mythos-5*|*opus-4-7*|*opus-4-8*|*opus-5-5*|*opus-5*|*\[1m\]*)
                                window=1000000 ;;
                            *) window=200000 ;;
                        esac
                        ;;
                esac
            fi
            ;;
    esac
    printf '%s' "$window"
}

# Session window fallback: no authoritative cache for this session (statusline
# not yet rendered, or a stale/corrupt cache) -> map by the SESSION model. This
# is what same-model rows inherit below; an empty/unknown session model still
# yields 200000 (fail-conservative). Formerly this fell to another session's
# cache or 200k regardless of model, so a GPT-6 Astra or Opus 5 session's
# same-model subagents rendered against 200k and hit red far too early.
# session_model_key is the CLASSIFICATION form of the session model
# (normalize_model_id, 2026-09-29): the claude-model-<session> cache is seeded
# by context-bar.sh from the REQUESTED .model.id and refreshed by
# resolve_model_cache from the transcript's RESPONSE model, so on OpenRouter it
# may hold either the dotted or the hyphenated spelling. Both sides of the
# same/different-model comparison below are normalized so a dotted-vs-hyphenated
# version spelling alone never forces the different-model path (a
# provider-prefix difference still does; that is harmless because the static
# map returns the correct window for either spelling). session_model itself (raw) is
# not displayed and the cache keeps the raw name.
session_model_key=$(normalize_model_id "$session_model")
if [[ -z "$max_context" ]]; then
    max_context=$(static_window_for_model "$session_model_key")
fi

# --- Render one output line per task ---
bar_width=5
while IFS=$'\x1f' read -r id type name status tokens label payload_model; do
    # Reject a path-unsafe agent id before constructing any child paths.
    is_safe_id "$id" || continue

    # Resolve the CHILD model before selecting its numerator. CC 2.1.261 first
    # schedules decoration at ~300ms, then refreshes at ~5s. Model signatures
    # avoid repeated model scans; measured input is refreshed on every render.
    task_model=""
    model_cache=""
    task_transcript=""
    [[ -n "$session_id" ]] && model_cache="${cache_dir}/claude-subagent-model-${session_id}-${id}"
    [[ -n "$subagents_dir" ]] && task_transcript="${subagents_dir}/agent-${id}.jsonl"
    if [[ -n "$model_cache" ]]; then
        task_model=$(resolve_model_cache "$task_transcript" "$model_cache")
    fi

    # This source-selection grammar is separate from physical capacity and
    # quality profiles: all registered 5.6 mini/chat variants participate, but
    # neither gain flagship capacity nor the Sol/Astra extended quality tier.
    # 2026-09-29 user policy decision (see gpt_flagship_re): gpt-6-sol and
    # gpt-6-luna participate like gpt-6-astra, and the flagship -pro form of
    # every participating flagship participates as its base does (-pro is
    # mutually exclusive with -mini/-chat, so gpt-5.6-mini-pro stays out).
    # 2026-10-12 user policy decision: gpt-6.1-sol (and its -pro form)
    # participates like gpt-6-sol.
    # Matched against the RAW task_model: normalize_model_id rewrites only
    # claude-* ids, and this grammar admits only gpt-* slugs, so normalization is
    # the identity on every id that can match here (and this block runs before
    # the control-strip that model_key is derived after).
    measured_input_re='^(gpt-5\.6(-(sol|terra|luna))?(-(mini|chat|pro))?|gpt-6-(astra|sol|luna)(-pro)?|gpt-6\.1-sol(-pro)?)(\[1m\])?$'
    shim_local=0
    if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
          ( "${SHIM_BACKEND_MODE:-}" == "chatgpt" || "${SHIM_BACKEND_MODE:-}" == "openai" ) && \
          "$type" == "local_agent" ]]; then
        shim_local=1
        # Only the affected shim lanes use the optional validated startup identity;
        # a resolved transcript/cache always wins, never the parent model.
        if [[ -z "$task_model" && "${payload_model##*/}" =~ $measured_input_re ]]; then
            task_model="$payload_model"
        fi
    fi

    # Normalize native progress as before. Use a string comparison for zero so
    # malformed/oversized values never enter arithmetic before the final guard.
    tokens=${tokens%.*}
    [[ "$tokens" =~ ^[0-9]+$ ]] || tokens=0
    context_pending=0
    if [[ "$shim_local" -eq 1 && "${task_model##*/}" =~ $measured_input_re ]]; then
        # CC 2.1.261 can snapshot zero initial usage, then retain only an output
        # estimate (e.g. 24/364) despite final positive input on disk. Read only
        # this child's latest positive input; never sum historical outputs or
        # max with older usage (compaction can legitimately lower the count).
        tokens=0
        if [[ -n "$task_transcript" && -f "$task_transcript" ]]; then
            tokens=$(jq -Rn '
                [inputs | fromjson? | objects
                 | select(.isApiErrorMessage != true)
                 | .message? | objects | .usage? | objects
                 | [.input_tokens, .cache_read_input_tokens, .cache_creation_input_tokens]
                 | map(if . == null then 0 else . end)
                 | select(all(.[]; type == "number"))
                 | select(all(.[]; . >= 0 and . <= 9007199254740991 and . == floor))
                 | add | select(. > 0 and . <= 9007199254740991)]
                | last // 0
            ' 2>/dev/null < "$task_transcript") || tokens=0
        fi
        # Safe-integer ceiling also keeps tokens*100 within signed int64.
        if ! is_canonical_positive_decimal "$tokens" || [[ "$tokens" -gt 9007199254740991 ]]; then
            tokens=0
            context_pending=1
        fi
    elif [[ "$tokens" == "0" && -n "$task_transcript" && -f "$task_transcript" ]]; then
        # Preserve the legacy generic zero-count fallback for unrelated rows.
        tokens=$(jq -s '
            [.[] | select(.message.usage and .isApiErrorMessage != true) | (
                (.message.usage.input_tokens // 0) +
                (.message.usage.cache_read_input_tokens // 0) +
                (.message.usage.cache_creation_input_tokens // 0)
            )] | map(select(. > 0)) | last // 0
        ' 2>/dev/null < "$task_transcript") || tokens=0
        tokens=${tokens%.*}
        [[ "$tokens" =~ ^[0-9]+$ ]] || tokens=0
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
    # CLASSIFICATION form of the (control-stripped) row model — see
    # normalize_model_id. task_model stays RAW for the row label (agent_disp);
    # model_key drives the different-model test, the physical window, the
    # ChatGPT-lane flagship predicate, and the quality tier.
    model_key=$(normalize_model_id "$task_model")
    # Default: the session window (covers same-model subagents and alternative
    # providers, where the mapping below does not apply).
    row_window="$max_context"
    if [[ -n "$model_key" && "$model_key" != "$session_model_key" ]]; then
        # Different-model row: the window Claude Code provisions for ITS model
        # (see static_window_for_model above), never the session's.
        row_window=$(static_window_for_model "$model_key")
    fi

    # CLAUDE_CODE_MAX_CONTEXT_TOKENS is the ordinary user override. Apply it to
    # same-model and different-model rows before the backend-specific final cap.
    if is_canonical_positive_decimal "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-}"; then
        row_window="$CLAUDE_CODE_MAX_CONTEXT_TOKENS"
    fi

    # ChatGPT-subscription/Codex final physical-window accounting constraint.
    # Canonical activation requires BOTH exact lane signals and a task model in
    # the anchored flagship arm — the gpt-5.4/5.5/5.6 family plus gpt-6-astra,
    # and (user policy decisions 2026-09-29 and 2026-10-12, not measurement)
    # gpt-6-sol, gpt-6-luna, gpt-6.1-sol, and the flagship -pro forms, which
    # inherit the cap from their
    # bases; mini/chat variants are excluded by ordering. Probes 2026-09-05 (Codex CLI
    # 0.153.2, shim v1.3.19, SHIM_BACKEND_MODE=chatgpt) measured BOTH lane
    # flagships: gpt-6-astra accepted 919,053 real input tokens and rejected
    # 922,552; gpt-5.6-sol accepted 910,827 and rejected 921,973. 919000 is
    # therefore the lane-wide accounting ceiling for this arm, MEASURED for Sol
    # and Astra alike and consistent with Astra's documented 922,000-token max
    # input (1,050,000 window - 128,000 output). Provenance: previously 370,000
    # (2026-07-16), now stale.
    # Apply min(resolved, 919000) after cache/model/override resolution so
    # stale same-model caches and unsafe explicit declarations are capped while
    # lower positive values survive. This is utilization/statusline accounting,
    # NOT compaction and NOT a transport-level request blocker; the backend
    # remains the ultimate hard ceiling.
    # Flagship predicate for the ChatGPT-lane cap uses the SAME closed-set ERE
    # (Convention 3); mini/chat slugs simply do not match it, so no explicit
    # exclusion arm is needed. The 919k min-ceiling ordering below is unchanged.
    gpt_flagship=0
    physical_slug="${model_key##*/}"
    if [[ "$physical_slug" =~ $gpt_flagship_re ]]; then
        gpt_flagship=1
    fi
    if [[ "${DAAF_PROVIDER_SHIM:-}" == "openai" && \
          "${SHIM_BACKEND_MODE:-}" == "chatgpt" && \
          "$gpt_flagship" -eq 1 ]] && \
       is_canonical_positive_decimal "$row_window" && \
       [[ "$row_window" -gt 919000 ]]; then
        row_window=919000
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
    # on the measured agent's model. Fable/Mythos and Opus 5.5 (admitted to
    # this tier by user policy decision 2026-09-23 — not validation; see the
    # block below) get the Claude extended-horizon gates: 40/50/60% plus
    # 400/500/600k absolute gates. Fable/Mythos were registered as validated
    # at 30/40/50% OR 300/400/500k; by USER POLICY DECISION of 2026-10-23
    # (not validation) the whole tier was raised to the current numbers, so
    # the raised gates rest on the user's policy decision, not on a DAAF
    # validation. Provenance (maintainer-only research workspace):
    # research/2026-10-23_FrameworkDev_ClaudeExtendedHorizonRaise/SESSION_NOTES.md.
    # The six threshold assignment lines in the case below are kept
    # byte-identical with calculate() in .claude/hooks/context-reporter.sh
    # (numeric lockstep test in tests/bash/context_reporter.bats). The exact
    # extended-horizon GPT ids — GPT 5.6 Sol and the second registered
    # extended-horizon model GPT-6 Astra (validated), plus GPT-6 Sol, GPT-6.1
    # Sol, and the flagship -pro form of each (user policy decisions
    # 2026-09-29 and 2026-10-12, not validation) — use 60/75/90% gates while
    # retaining 300/400/500k absolutes, so the Claude and GPT extended tiers
    # no longer share absolute gates. Everything else — INCLUDING opus-4-8[1m] and
    # opus-5 (bare or [1m]), whose 1M physical windows do NOT relax their
    # Opus-class quality horizon — gets 40/60/75% plus 150/200/250k. Opus 5's
    # 1M window was observed 2026-09-05 (Claude Code 2.1.261, /model + /context)
    # and registered in the physical-window arm above; its absence from this
    # quality-profile arm is deliberate, per CLAUDE.md § Context Quality Curve
    # (conservative-default membership, quoted verbatim: "all Opus models except
    # `claude-opus-5-5` (above), Sonnet, unknown model IDs, ..."). Opus 5.5 is
    # the single Opus exception, added 2026-09-23 by user policy decision — not
    # validation (see the block just above the case).
    # GPT extended-tier matching (gpt_extended_re, tested against the
    # provider-stripped terminal slug of model_key) accepts the bare slug or a
    # provider path only when its final segment is exactly gpt-5.6-sol,
    # gpt-6-astra, gpt-6-sol, or gpt-6.1-sol, each with an optional -pro and then
    # an optional [1m] (gpt-6-sol and every -pro form admitted 2026-09-29, and
    # gpt-6.1-sol 2026-10-12, by user policy decision, not validation — see
    # gpt_flagship_re); left- or right-boundary
    # near misses (xgpt-6-astra, gpt-6-astra-pro-x, gpt-6-astra-mini,
    # gpt-6-astra[1m]-x, gpt-6-sol[1m]-pro), gpt-6-luna (1.05M window but
    # conservative tier, like gpt-5.6-luna), and unknown/empty models fall
    # through to the conservative default (fail-conservative).
    # Deliberately different from the physical-window case block above — the
    # broad flagship physical map does not imply the exact quality-tier rule.
    # See CLAUDE.md § Context Quality Curve for the authoritative threshold table.
    #
    # Opus 5.5 (claude-opus-5-5, bare or [1m]) JOINS the
    # extended-horizon arm below. USER POLICY DECISION, 2026-09-23 (Checkpoint 1,
    # research/2026-09-23_FrameworkDev_ClaudeCode_Upgrade_2.1.280/SESSION_NOTES.md
    # § Key Decisions #3): this deliberately departs from the 2026-07-24
    # "validate before promoting" doctrine — no sustained-session DAAF
    # measurement of Opus 5.5 quality past 300k exists yet; the user accepted the
    # extended-horizon gates on the model's documented long-horizon design
    # ("built for long-running agentic coding and knowledge work"). The Opus 5.5
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
    # fallthrough arm, which tests/bash/subagent_bar.bats locks. The
    # physical-window case block above keeps its broad `*opus-5-5*`
    # deliberately: mapping a window is not a privilege grant, and `*opus-5*`
    # already matched those slugs before this change. The case is keyed on
    # model_key, so a provider-dotted anthropic/claude-opus-5.5 reaches this arm
    # as anthropic/claude-opus-5-5 (normalize_model_id, 2026-09-29).
    case "$model_key" in
        *fable-5*|*mythos-5*|claude-opus-5-5|*/claude-opus-5-5|claude-opus-5-5\[1m\]|*/claude-opus-5-5\[1m\])
            elev_pct=40; high_pct=50; crit_pct=60
            elev_k=400;  high_k=500;  crit_k=600 ;;
        *)
            if [[ "${model_key##*/}" =~ $gpt_extended_re ]]; then
                elev_pct=60; high_pct=75; crit_pct=90
                elev_k=300;  high_k=400;  crit_k=500
            else
                elev_pct=40; high_pct=60; crit_pct=75
                elev_k=150;  high_k=200;  crit_k=250
            fi
            ;;
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
    if [[ "$context_pending" -eq 1 ]]; then
        content+="${C_GRAY} · context pending${C_RESET}"
    else
        content+="${C_GRAY} ·${C_RESET} ${color}${tok_label}${C_RESET} ${bar} ${color}${pct}%${C_RESET}"
    fi
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
