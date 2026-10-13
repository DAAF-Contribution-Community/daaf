#!/usr/bin/env python3
# =============================================================================
# anthropic_openai_shim.py
#
# Hardened Anthropic Messages API -> OpenAI Responses API (/v1/responses)
# translation shim for Claude Code. Productionized from the validated PoC
# (research/2026-07-09_FrameworkDev_OpenAI_Provider/poc/shim_anthropic_openai.py),
# then migrated from the OpenAI Chat Completions wire format to the Responses
# API in v1.2.0 (see Changelog).
#
# Claude Code speaks the Anthropic Messages API. When ANTHROPIC_BASE_URL points
# at this shim, Claude Code POSTs Anthropic-format requests to /v1/messages
# (usually with stream=true). This shim translates each request into an OpenAI
# Responses request (POST {SHIM_BACKEND_BASE_URL}/responses), forwards it to the
# OpenAI Responses backend (api.openai.com/v1, or an OpenAI-compatible proxy of
# the Responses API), and translates the response back into the Anthropic SSE
# dialect Claude Code expects.
#
# WHY /v1/responses (not /v1/chat/completions): as of 2026-07-11 the gpt-5.6
# family REJECTS function tools on /v1/chat/completions whenever reasoning is
# active, with a 400: "Function tools with reasoning_effort are not supported
# for gpt-5.6-sol in /v1/chat/completions. To use function tools, use
# /v1/responses or set reasoning_effort to 'none'." Claude Code sends tools on
# essentially every turn, so every real GPT session on the chat lane fails.
# /v1/responses supports function tools + reasoning together. The Chat
# Completions translator was therefore REMOVED (user decision 2026-07-11);
# generic OpenAI-compatible chat backends (vLLM/LM Studio) are explicitly out of
# scope. Git history is the archive for the removed chat lane.
#
# Design constraints:
#   * stdlib + httpx + uvicorn ONLY. No fastapi/flask/litellm. Raw ASGI callable.
#   * Single file, sequential and readable. Comments concentrated at the
#     translation decision points, which is where the fidelity risk lives.
#   * Zero credential logging: the backend API key is referenced by env only and
#     never written to logs or response bodies. The reasoning cache stores only
#     backend-generated opaque encrypted blobs (never key material) — safe.
#
# ATTRIBUTION: specific Responses-translation decisions below — omitting
#   temperature/top_p for reasoning models, the incomplete->max_tokens /
#   tool_use / end_turn stop_reason mapping, the thinking-block-BEFORE-text-block
#   ordering, and routing streamed argument deltas by internal item_id (fc_...)
#   rather than public call_id — are ported (logic, NOT code) from two
#   MIT-licensed reference implementations: raine/claude-code-proxy (Rust) and
#   AmazingAng/auth2api (TypeScript). See
#   research/2026-07-11_FrameworkDev_ShimDiagnostics_AuthOptions/output/
#   preliminary_notes/05_prior_art_responses_translators.md. The reasoning-cache
#   re-injection design (below) is NOVEL: neither reference implements reasoning
#   re-injection on the request/replay path — this shim closes that gap.
#
# Hardening (preserved from the chat-lane shim; see § HARDENING tags inline):
#   * Retry with exponential backoff + jitter on backend 429/500/502/503/529,
#     max 3 retries, honoring Retry-After. Never retries once streaming has
#     begun emitting to the client (fails the stream cleanly instead), except the
#     single v1.4.8 whitespace-guard retry, allowed only before any tool_use is sent.
#   * Client-disconnect handling: aborts the backend request on ASGI disconnect.
#   * Usage robustness: reads usage from response.completed; if the backend omits
#     it, estimates and flags the estimate in a log line.
#   * Empty-response guard: emits one empty text block if the backend yields no
#     content at all, so Claude Code always receives a well-formed message.
#   * Structured single-line-per-request logging to stderr (never credentials or
#     bodies). The manager script (start_shim.sh) redirects stderr to the log.
#   * Backend-error diagnostics on every non-2xx: status, exact structured
#     type/code, mapped Anthropic type, and allowlisted headers — never body prose.
#   * Log contract (metadata only) covers response headers too: on backend-error and
#     retry lines a header reaches the log only if its exact lowercased name is in
#     DIAG_HEADER_ALLOWLIST (request IDs, retry-after, rate-limit numerics). There is
#     no prefix rule (removed in v1.4.9), so opaque session tokens
#     (x-codex-turn-state), cookies/set-cookie, auth-like headers and account credit
#     fields are never written there. The separate 2xx quota_snapshot event still
#     records plan and credit numerics (no tokens).
#   * GET /health endpoint for the manager's idempotency/status checks.
#
# Changelog:
#   v1.4.9 (2026-10-13): Follow-ups from live verification of 1.4.8.
#     (1) Effort floor extended: GPT-6.1 Sol also rejects effort:"none" (live: a
#     "gpt-6.1-sol#none" request got backend 400 invalid_request_error /
#     unsupported_value). The Astra-only set is renamed _NO_NONE_EFFORT_SLUGS and now
#     also holds gpt-6.1-sol, gpt-6.1-sol-pro and their "[1m]" forms; a resolved
#     "none" for any member is sent as "low". The -pro members are an inference from
#     the shared model family, not a live observation. gpt-6-sol and every other
#     model are unchanged. (2) Log hygiene: backend-error and retry log lines
#     ("| headers: ...") no longer include every x-codex-* response header. That
#     prefix rule let an opaque backend session token (x-codex-turn-state) and
#     account credit fields into shim.log. Headers now pass an exact-name allowlist
#     only (DIAG_HEADER_ALLOWLIST: request IDs, retry-after, x-ratelimit-* numerics,
#     and the x-codex primary/secondary used-percent and reset-after-seconds
#     numerics); everything else, including cookies, auth-like headers, credit
#     balances and turn-state tokens, is never written. The 2xx quota_snapshot event
#     is unchanged. Request translation and the /health schema are unchanged.
#   v1.4.8 (2026-10-12): PDF document blocks, WebSearch edge cases and the whitespace
#     guard no longer fail hard. (1) PDF/document blocks, in user content and inside tool_result content,
#     are translated. Correction (v1.4.9, from live testing): Claude Code 2.1.281's
#     Read tool on a PDF already worked before 1.4.8, because it renders pages and
#     returns text plus images. Raw document blocks come from other paths, such as a
#     PDF attached or @-mentioned directly in a message, or a client that sends
#     document blocks; the shim used to reject those with a 400, and the block stayed
#     in the history. Mapping: base64 PDF -> input_file (file_data data URL), URL PDF
#     -> input_file (file_url, accepted only when it passes the same strict URL check
#     as consulted search sources), text documents -> input_text. Any other document
#     variant becomes a short text note instead of a 400 (logged once per variant at INFO,
#     never the content). Base64 is checked with one flat character-class scan, so
#     multi-megabyte PDFs validate quickly. SHIM_PDF_MODE=omit turns PDFs into a note
#     that says they were omitted by configuration; an unrecognized SHIM_PDF_MODE
#     value logs one startup WARNING and uses "file". (2) WebSearch tolerance: any
#     web_search_YYYYMMDD tool version is accepted (unknown options still fail
#     closed); disable_parallel_tool_use with search maps to parallel_tool_calls.
#     blocked_domains: the openai lane forwards the valid bare domains (deduplicated,
#     max 100) to filters.blocked_domains and WARNs about invalid entries only; the
#     chatgpt lane cannot send the exclusion upstream, so it WARNs and removes
#     sources and citations whose host is a blocked domain (or a subdomain of one)
#     from the projected result, adding a one-line note saying so. Unrecognized
#     hosted-action shapes, sources and citations are skipped with a WARNING instead
#     of failing the turn; a search whose listed sources are ALL unusable is skipped
#     (outcome=malformed) rather than shown as zero results. An overlong citation or
#     source title falls back to a "URL: ..." label. Identity, status and coverage
#     checks still fail closed. (3) Runaway whitespace in a streamed tool call (the
#     v1.4.4 guard; seen on GPT-6 Astra) no longer hands Claude Code an empty tool
#     call: with SHIM_SANITIZE_TOOLS on (default), the tool_use header is held until
#     its arguments are complete, and on a guard trip before any tool_use was sent the
#     shim re-sends the request once inside the same reply (terminal line: attempts=2
#     or more, since ordinary transport/status retries of that re-send still apply;
#     retry_reason=tool_argument_whitespace). Text already shown before the trip stays
#     on screen, so a short preamble can appear twice. A second trip, or a trip after
#     a tool was already sent, ends the reply with the usual error, without an empty
#     tool call; if the re-send itself fails (rate limit, server error, expired login,
#     transport), the client sees that failure's own error type and message. At the
#     end of a completed response a still-held tool takes its arguments from the
#     final output item or the buffered deltas (never an empty {}); on an incomplete
#     response a tool whose arguments never completed is dropped with a WARNING.
#   v1.4.7 (2026-10-12): Institutional-gateway robustness. SHIM_BACKEND_BASE_URL is
#     trimmed, an empty value falls back to the lane default, trailing "/" is dropped,
#     and a pasted ".../responses" suffix is stripped with one startup WARNING (the
#     shim appends /responses itself). /health "backend" reports the normalized URL;
#     the API key is still never logged. The permissive GET .../models listing
#     (_handle_models) also advertises openai/gpt-6-sol, openai/gpt-6-luna and
#     openai/gpt-6.1-sol. No other behavior change.
#   v1.4.6 (2026-09-21): Worker-aware conversation routing (stable per session and
#     worker routing hints for concurrent Claude Code workers).
#   v1.4.5 (2026-09-20): Non-streaming recovery: completed output items are no longer
#     lost, and explicit refusal evidence is preserved through validation.
#   v1.4.4 (2026-09-17): Fail-fast guard on runaway whitespace outside JSON strings in
#     streamed tool arguments (256-character limit).
#   v1.4.3 (2026-09-17): Live stream-interruption diagnostics revision.
#     Details for 1.4.3-1.4.6 are in the project research notes under
#     research/2026-09-06_FrameworkDev_GPT_Shim_Native_Search/ (STATE_2026-09-17_*,
#     STATE_2026-09-20_*, STATE_2026-09-21_*).
#   v1.4.2 (isolated draft, 2026-09-15): Support documented hosted search,
#     open_page and find_in_page sequences without inventing ranked page results.
#     Page actions retain typed inputs and explicit provenance text; optional absent
#     open URLs are disclosed, required find evidence fails closed. Raw replay stays
#     intact. Lifecycle action diagnostics contain fixed buckets/counts only.
#     Schema-derived page fixtures are offline compatibility evidence, not proof of
#     the action subtype responsible for the reported live 502s.
#   v1.4.1 (2026-09-13): Accept the installed client's explicitly empty native
#     allowed_domains/blocked_domains lists as omitted filters. Nonempty blocklists
#     remain explicitly unsupported; malformed controls and unknown keys still fail
#     closed. Nonempty allowlists retain their upstream mapping. This repairs the
#     local unsupported-option rejection observed in the 1.4.0 live WebSearch check.
#   v1.4.0 (isolated draft, 2026-09-11): Typed native web_search_20250305
#     translation, bounded hosted-response collection and process-local replay.
#     Real consulted-source URLs/titles and answer attribution are projected without
#     invented source quotations or proprietary encrypted citation fields. Ordinary
#     incomplete answers preserve observed partial text after search history, even
#     when another output item has completed. Subscription max_uses is an observed
#     call ceiling, NOT an upstream execution/billing/quota guarantee. Replay expires
#     or is lost on eviction/restart; open_page/find_in_page remain unsupported.
#     Installed extracted SDK/parser contracts are tested, not full CLI/live API
#     certification. Shared promotion/deployment requires separate approval.
#   v1.3.19 (2026-09-05): GPT-6 Astra onboarding — model-aware effort floor + model
#     listing. _handle_models now advertises openai/gpt-6-astra alongside the
#     existing gpt-5.6-sol/gpt-5.5 entries (additive). A single model-conditional
#     clamp in _anthropic_to_responses_request rewrites a resolved reasoning.effort
#     of "none" to "low" for the Astra family (_ASTRA_FAMILY_SLUGS = {gpt-6-astra,
#     gpt-6-astra[1m]}, matched on the provider-prefix- and effort-suffix-stripped
#     terminal slug), because Astra's supported effort enum is
#     {low,medium,high,xhigh,max} and REJECTS "none"
#     (developers.openai.com/api/docs/models/gpt-6-astra, primary source
#     2026-09-05). Every other model keeps prior behavior exactly; the general
#     four-tier effort resolver and the /health schema are unchanged.
#     SHIM_VERSION -> 1.3.19.
#   v1.3.18 (2026-08-09): Bind stream-member cleanup to captured identities.
#     Cleanup atomically quarantines `.owner` and `output.fifo`, revalidates each
#     quarantined inode, and unlinks only a match. A one-time same-UID substitution
#     is restored when safe and reported as contamination/non-success; partial
#     cleanup and restoration failures are explicit. This does not claim protection
#     against a continuously racing same-UID attacker. Request translation and
#     /health schema are unchanged. SHIM_VERSION -> 1.3.18.
#   v1.3.17 (2026-08-08): Tighten seven lifecycle-manager invariants.
#     Supervisor capabilities and helper records are exact-schema; locked actions
#     adjudicate stable typed PID roles before health or mutation and remain fail-closed
#     after later uncertainty; TERM-to-KILL escalation binds the serving process start
#     time; append failure consistently exits 43; and inode cleanup finds arbitrary
#     same-parent workspace renames without deleting replacements. Request translation
#     and /health schema are unchanged. SHIM_VERSION -> 1.3.17.
#   v1.3.16 (2026-08-07): Complete capability-bound lifecycle hardening.
#     Standard-library typed PID reads now use no-follow, nonblocking descriptor and
#     path identity checks; stream workspaces carry inode/nonce capabilities through
#     readiness and supervisor cleanup; bounded diagnostic children are identity-
#     verified and reaped; restart-result state is monotonic with successful append
#     as the irreversible commit boundary; and INT/TERM/HUP handlers remain queue-only
#     through natural manager exit. Request translation and /health schema are
#     unchanged. SHIM_VERSION -> 1.3.16.
#   v1.3.15 (2026-08-06): Close reviewed lifecycle-manager commit/read cleanup gaps.
#     Authoritative restart records are independent of fallible stderr presentation;
#     PID-decoder failures fail closed; committed signal semantics survive lock release;
#     and foreground stream ownership persists through strict readiness. Pre-append
#     interruption diagnostics now distinguish persisted=no from genuinely unknown.
#     Request translation and /health schema are unchanged. SHIM_VERSION -> 1.3.15.
#   v1.3.14 (2026-08-06): Complete reviewed lifecycle-manager race hardening.
#     Signal-handler restoration is lossless, durable READY is the restart commit
#     boundary, process identity is positional and role-specific, partial stream
#     allocations are reclaimable immediately, PID parsing is byte-exact, and the
#     no-setsid control is test-mode-only. Request translation and /health schema
#     are unchanged. SHIM_VERSION -> 1.3.14.
#   v1.3.13 (2026-08-05): Close reviewed lifecycle-manager launch/read hazards.
#     INT/TERM/HUP are queued across background launch-to-PID handoff and replayed
#     only after the exact supervisor PID is known; the foreground manager now
#     preallocates and retains a private stream-workspace capability so it can
#     reclaim setup state if that supervisor dies before PID publication; and PID
#     reads reject symlinks/special files, validate the opened descriptor identity,
#     and bound the first line. Request translation and /health schema are unchanged.
#     SHIM_VERSION -> 1.3.13.
#   v1.3.12 (2026-08-04): Harden lifecycle-manager state transitions.
#     Stable private lock directories now use kernel flock descriptors with no stale-
#     owner deletion; start/auto interruption cleans direct and published launches while
#     locked; supervisor teardown uses bounded identity-checked TERM-to-KILL escalation;
#     and pre-validation setup failures remain stderr-only. Deterministic regressions cover
#     process-death lock release, hostile owner metadata, launch interruption, resistant
#     children, and rejected log-directory symlinks. Request translation is unchanged.
#     SHIM_VERSION -> 1.3.12.
#   v1.3.11 (2026-08-03): Harden lifecycle-manager stream setup and diagnostics.
#     The manager now allocates a private, atomically unique FIFO directory per
#     supervisor, cleans owned setup/state artifacts from the earliest failure
#     point, and persists bounded setup and auto-start failure classifications.
#     Shim request translation/runtime behavior is unchanged. SHIM_VERSION -> 1.3.11.
#   v1.3.10 (2026-07-29): Default GPT response verbosity to "medium".
#     SHIM_TEXT_VERBOSITY still accepts explicit low|medium|high overrides, but an
#     unset, empty, whitespace-only, or invalid value now resolves to "medium".
#     This balances decision-focused responses with DAAF's evidence requirements;
#     reasoning effort and every other request field are unchanged. User-approved.
#     SHIM_VERSION -> 1.3.10.
#   v1.3.9 (2026-07-26): Canonical GPT service-tier request vocabulary.
#     Both exact GPT shim backends now converge on the one OpenAI Responses wire value
#     `service_tier:"priority"` for valid inbound Anthropic Fast and shim-global ON.
#     ChatGPT subscription continues to present this as Fast with plan/credit semantics;
#     OpenAI API continues to present it as Priority with API Priority billing semantics.
#     OFF still omits service_tier, policy persistence remains schema-v1 backend+boolean,
#     and request snapshots, retry invariance, route reset, and no-fallback behavior are
#     unchanged. Canonical served `priority` maps to Anthropic usage.speed=`fast`; exact
#     served `fast` remains a compatibility-only terminal parser value and is never emitted
#     as requested vocabulary. SHIM_VERSION -> 1.3.9.
#   v1.3.8 (2026-07-25): Route-bound shim-native GPT service-tier control.
#     Adds a strict persistent default-OFF policy shared across both GPT lanes, startup
#     compare-and-set reset on route changes, one request-boundary policy snapshot reused
#     by all retries, additive precedence with validated inbound Anthropic Fast, bounded
#     requested-source telemetry, process-local latest-terminal evidence, and the stable
#     gpt_service_tier /health block. SHIM_VERSION -> 1.3.8.
#   v1.3.7 (2026-07-24): Claude Code Fast mode with route-specific service tiers.
#     Valid `speed:"fast"` plus beta `fast-mode-2026-02-01` emits Responses
#     `service_tier:"priority"` on the OpenAI API lane and `service_tier:"fast"` on the
#     ChatGPT/Codex lane. Invalid speed requests fail locally before auth/upstream; beta-only
#     and ordinary traffic omit service_tier. Fast never changes model, reasoning, tools,
#     retry payloads, or context gating and never falls back to Standard. Terminal actual
#     tiers priority/fast map to Anthropic usage.speed=fast; default/flex/scale/auto map to
#     standard; absent/unknown remain omitted. Terminal telemetry distinguishes scrubbed
#     requested_service_tier from served_service_tier. No env or /health field was added.
#     SHIM_VERSION -> 1.3.7.
#   v1.3.6 (2026-07-22): Prompt-cache observability + reasoning-cache persistence cap resize
#     (minor bump — the observability is additive and the client-visible usage mapping is
#     sum-invariant, so downstream context accounting is byte-equivalent). Step 1 of the
#     prompt-cache backlog item; Step 2 (prompt_cache_key emission) remains out of scope
#     (blocked on there being no stable cross-turn identifier in the shim today).
#     * CAPTURE (V6-R1): the shim now reads usage.input_tokens_details.cached_tokens at all
#       three usage-parse sites (streaming response.completed/incomplete reducer, and both
#       non-stream lanes via _responses_to_anthropic, which carries the value through a
#       private _cached_tokens key each lane pops before send). Defensive typing via
#       _resolve_cached_tokens: only a non-bool int >= 0 that does not exceed the reported
#       input total is accepted; absent/null/string/negative/bool/clamped all resolve to
#       ABSENT (None), indistinguishable from "no cache info" (old backends/fixtures emit no
#       detail). _RequestLifecycleState gains self.cached_tokens. Never raises.
#     * TERMINAL RECORD (V6-R2): the terminal log record gains cached_tokens (the captured
#       int, or the "-" absent-convention when None) at the single lane-agnostic emission
#       site. This is the field the ~1-week telemetry review greps.
#     * ANTHROPIC USAGE MAPPING (V6-R3, Decision 1 + Decision 2 = always-emit): client-
#       visible usage blocks now use the subtraction mapping — input_tokens = openai_total
#       - cached, cache_read_input_tokens = cached, cache_creation_input_tokens = 0 (OpenAI
#       reports no cache-write count). Anthropic's input_tokens is the uncached remainder,
#       so this preserves the sum invariant EXACTLY (the three fields sum to the OpenAI
#       total) and Claude Code shows real cache behavior natively. The two cache fields are
#       ALWAYS present (0 when absent) for a deterministic shape matching Anthropic's own
#       responses; message_start zero-usage seeds and error frames carry them as zeros too.
#       Clamp guard folds into _resolve_cached_tokens (cached > input_total -> absent,
#       fail-open, never a negative input_tokens).
#     * /HEALTH (V6-R4, Decision 3): a NEW top-level prompt_cache block — requests_with_usage,
#       requests_with_cached, cached_tokens_total, input_tokens_total (module-global int
#       counters, counts only, ticked once per terminal). hit-rate = cached_tokens_total /
#       input_tokens_total. This changes the pinned /health key set, so _HEALTH_KEYS + the
#       version pin move in the same commit (the sanctioned money-test extension).
#     * REASONING-CACHE PERSISTENCE CAP RESIZE (V6-R5, Decision 4b): _REASONING_PERSIST_MAX_
#       ENTRIES 256 -> 1024, _REASONING_PERSIST_MAX_BYTES 2 MiB -> 8 MiB (4x headroom for
#       ~4 session-tails). In-memory _REASONING_CACHE_CAP (2048) UNCHANGED — the persist cap
#       stays under it (no RAM change, no restore-clamp interaction). Worst-case persist
#       write measured at low tens of ms at the 8 MiB bound (see the persistence-bounds
#       comment). Bounds stay hard constants (no env seam).
#     SHIM_VERSION -> 1.3.6.
#   v1.3.5 (2026-07-21): Janitorial — removed the dead non-streaming lazy-401 refresh
#     branch (no behavior change). The branch lived inside the OpenAI/API-key
#     `if not stream:` block and was guarded by `SHIM_BACKEND_MODE == "chatgpt"`, but
#     that condition is unreachable there: the earlier v1.2.7 chatgpt non-stream adapter
#     (`if not stream and SHIM_BACKEND_MODE == "chatgpt":`) returns on every exit path, so
#     control reaches the OpenAI/API-key `if not stream:` block only when
#     SHIM_BACKEND_MODE != "chatgpt", making the deleted guard a permanent contradiction.
#     Unreachable since the v1.3.0 auth delegation reshaped the non-stream chatgpt path;
#     the live chatgpt non-stream case is fully handled by the v1.2.7 adapter, and the
#     live lazy-401 refresh path is the shared opener's did_401_refresh guard
#     (_open_backend_stream). No test asserted the deleted branch's log strings; the
#     lazy-401 regression tests exercise the live opener path. SHIM_VERSION -> 1.3.5.
#   v1.3.4 (2026-07-21): Stale-blob insurance for restored reasoning + known-events
#     allowlist absorption + reasoning-cache effectiveness telemetry (minor bump — the
#     insurance is additive around the existing 400 fail-fast contract, and the other two
#     are observability/stability riders; no change to the clean-path translation
#     semantics). Landed as two implementation commits under one release.
#     * STALE-BLOB INSURANCE (V4-R1..R4): v1.3.3 persistence introduced the one scenario
#       where the reasoning cache's graceful-miss guarantee did not hold — a restored
#       (disk-loaded) `encrypted_content` blob has an undocumented backend-side validity
#       lifetime, and a 400 rejecting a re-injected restored blob previously failed the
#       request outright (400s are never in RETRY_STATUSES). Now: a module-level
#       _REASONING_CACHE_RESTORED_IDS set records which call_ids came from disk (rebuilt
#       after each restore; discarded on any live re-population or LRU eviction), and each
#       request tracks the restored reasoning-item ids/call_ids it actually injects. In
#       BOTH retry loops (JSON _post_with_retry, SSE _open_backend_stream), after _plan_retry
#       declines, a 400 whose error body NAMES reasoning material (broad case-insensitive
#       match of `reasoning`/`encrypted_content` over the normalized type/code/param/message/
#       detail fields) AND that injected >=1 restored item triggers a one-shot strip: remove
#       exactly those restored reasoning items from the reused payload["input"] by id (never
#       index), evict+discard the proven-stale call_ids and rewrite the persisted snapshot,
#       then retry once (retry_reason=stale_reasoning_400, retry_source=body). The detector's
#       breadth is safe because the restored-items-present + 400 + one-shot gate carries the
#       precision: a request that injected no restored items can never trigger, and a true
#       false positive costs at most one extra attempt in today's graceful-miss shape. Every
#       non-triggering 400 stays fail-fast, byte-identical to v1.3.3. Logs a distinct
#       counts-only event=reasoning_cache_stale_strip stripped=N line — never blob content or
#       backend error prose.
#     * ALLOWLIST ABSORPTION (V4-R5): `keepalive` (a top-level type, namespaced like `error`)
#       and `response.metadata` join the ignored status/lifecycle group of
#       _KNOWN_EVENT_TYPES. Both were observed live during v1.2.14 validation and have been
#       throttle-logged as "unknown wire" ever since despite carrying nothing the translation
#       needs; absorbing them restores unknown_events=0 on a clean stream from backends that
#       emit them. Not added to _MALFORMED_TOLERANT_EVENT_TYPES (a malformed instance should
#       still fail strictly). The two catch-alls compare raw event-type strings, so both
#       absorb by plain set membership with no namespace logic.
#     * EFFECTIVENESS TELEMETRY (V4-R6/R7): the terminal record gains two additive,
#       always-present ints — reasoning_cache_hit (per-request cache-hit count, parallel to
#       reasoning_cache_miss) and reasoning_cache_stripped (restored items stripped by the
#       insurance this request, 0 otherwise). /health's existing NESTED reasoning_cache block
#       gains hits (process-cumulative cache hits) and restored_hits (the subset whose call_id
#       was still disk-restored at hit time — the direct measure for the ~1-week cap/ceiling
#       review); no new top-level /health key, so the health key set is unchanged. The hit
#       path stays strictly read-only — it reads via .get(), NEVER move_to_end, so hit-
#       counting introduces no LRU mutation and no persist / write amplification. Counts only.
#     SHIM_VERSION -> 1.3.4.
#   v1.3.3 (2026-07-21): Reasoning-cache persistence across shim restarts (Tier 3 A2;
#     minor bump — additive continuity feature, no change to the live response path's
#     translation semantics). Before this, a restart mid-session discarded the entire
#     in-memory _REASONING_CACHE, so every subsequent turn replayed tool history WITHOUT
#     its reasoning items (graceful misses — the miss path has always omitted-and-sent,
#     never 400d — but degraded model context for the rest of long tool loops). The cache
#     now survives restarts.
#     * PERSIST: after each cache mutation the shim writes a bounded, newest-first snapshot
#       (LRU tail) to a state file — capped at 256 entries OR 2 MiB, whichever hits first —
#       and restores it at module import. The write is atomic (mkstemp + os.replace), 0600,
#       and absolutely fail-open (the whole writer is try/except: pass — a persistence write
#       must NEVER affect, delay, or raise on the response path), exactly mirroring the
#       _write_quota_state precedent. Restore is likewise fail-open: a missing/malformed/
#       stale/oversize file silently skips (next persist overwrites it) and the shim starts
#       cold. Staleness is a 30-day sanity ceiling only (_REASONING_PERSIST_TTL_S) — the
#       primary bound is the entry/byte cap, mirroring the in-memory cache's age-less LRU;
#       a short TTL would erase exactly the entries a multi-day session-resume replays.
#     * PLACEMENT: default path is $HOME/.claude/provider_shim/reasoning_cache.json (the
#       shim owns directory creation, mode 0700). This is deliberately OFF the repo tree,
#       UNLIKE shim.log/quota_state.json which stay in scripts/provider_shim/logs/: the
#       reasoning blobs are backend-encrypted content and must never be committable to any
#       VCS (gitignore notwithstanding), so they live on the per-container claude-config
#       volume ($HOME/.claude, the same volume codex CLI state uses). Per-container by
#       intent: because the file is not install-shared, the cross-install last-writer-wins
#       race that quota_state.json accepts as status-quo degradation cannot occur here. The
#       file is expendable continuity state (loss = graceful misses = prior behavior), never
#       a research artifact, and sits outside the /daaf backup/audit boundary by design.
#     * SEAM: DAAF_REASONING_CACHE_FILE redirects the path, resolved at MODULE IMPORT time
#       (_REASONING_CACHE_PATH is computed once when the module loads), so a post-import env
#       change does not redirect a live shim — the seam must be set before the module loads.
#       Same contract as DAAF_QUOTA_STATE_FILE; it is a redirect / hermetic-test seam, not
#       an off-switch (persistence stays unconditional and fail-open).
#     * SECURITY: persisted values are exactly the in-memory values — opaque backend
#       `encrypted_content` blobs plus item metadata, decryptable only by the backend. No
#       plaintext reasoning, no prompts, no tool arguments, no key material. Anthropic
#       thinking blocks are consumed, never stored. Logging stays counts-only (a single
#       event=reasoning_cache_restore entries=N age_s=M line on a successful restore),
#       never entry contents.
#     * OBSERVABILITY: /health gains "reasoning_cache": {"entries": N, "restored": M}
#       (counts only; restored = entries loaded at startup, 0 if none). No reader outside
#       the shim — this file is shim-internal continuity state, unlike quota_state.json.
#     * LIFECYCLE: start_shim.sh's state_targets_are_safe() now also covers quota_state.json
#       in its symlink/non-regular hijack checklist (closing a pre-existing gap — the file
#       has lived in that dir since v1.3.1). The reasoning-cache file is intentionally out
#       of that checklist: it lives under $HOME/.claude/, outside start_shim's domain, and
#       os.replace does not dereference a destination symlink.
#     * TOPOLOGY: the supported deployment is one running shim per container at a time.
#     * HARDENING (A2 review fold-in, no version bump): restore now (a) skips a file whose
#       on-disk size exceeds the 2 MiB persist cap BEFORE reading it (defense-in-depth — a
#       shim-written file can never exceed the cap, so only a hand-tampered file trips it),
#       and (b) reports the count of entries actually RESIDENT after restore on /health, so
#       a tampered over-cap file can no longer overstate reasoning_cache.restored.
#     SHIM_VERSION -> 1.3.3.
#   v1.3.2 (2026-07-21): Hermetic quota-state writes + a statusline reader tightening
#     (two-part maintenance release; no shim behavior change on the live response path).
#     * SHIM: _write_quota_state now honors DAAF_QUOTA_STATE_FILE — the SAME env var the
#       reader (context-bar.sh) already consumes — so one variable coherently redirects
#       both ends. Set + non-empty: the write (and its mkstemp temp sibling) land at that
#       exact path; unset/empty: the __file__-derived default is byte-identical to v1.3.1.
#       This is a redirect / hermetic-test seam, NOT an off-switch — the write stays
#       unconditional and absolutely fail-open (a bad seam value is swallowed like any
#       other failure). It resolves at MODULE IMPORT time (_QUOTA_STATE_PATH is computed
#       once when the module loads), so a post-import env change does not redirect a live
#       shim — the seam must be set before the module loads. Motivation: the loopback
#       harness exercises the PRODUCTION shim two ways — spawned in chatgpt mode AND loaded
#       in-process (controlled_asgi_probe drives the real request path inside the test-
#       runner process) — and before the seam every mocked chatgpt 2xx overwrote the live
#       INSTALL-SHARED quota_state.json with all-"-" snapshots (observed live 2026-07-21: a
#       full-suite run rewrote the production file every ~15s, blanking the OTHER install's
#       "Plan usage:" segment). The decisive polluter was the in-process load, whose write
#       ran deterministically in the runner with the env var unset. The harness now covers
#       BOTH contexts — a per-instance child-env seam for spawned shims plus a runner-level
#       os.environ.setdefault for in-process loads — which together keep test runs off the
#       install-shared file.
#     * READER (context-bar.sh, statusline-hardening deferred observation O2): the
#       fractional-floor strip of primary/secondary used-percent is now gated on
#       ^[0-9]+\.[0-9]+$ so an exponent-notation value carrying a dot (e.g. "1.0e999")
#       DROPS the segment instead of surviving the strip as "1" and rendering "1%". Plain
#       fractionals (69.9 -> 69) still render; this change lives in the reader, not here.
#     SHIM_VERSION -> 1.3.2.
#   v1.3.1 (2026-07-20): Statusline Plan-usage telemetry (additive, no behavior change).
#     On every chatgpt-lane 2xx (same guard as the D1 quota_snapshot line), the shim now
#     also caches the latest quota snapshot to <log dir>/quota_state.json — an atomic,
#     0600, absolutely-fail-open write next to shim.log. The file is a single JSON object
#     {captured_at:<int epoch>, <the 11 x-codex-* snapshot fields, raw header strings or
#     "-">}; the READER (context-bar.sh) computes the absolute reset instant as
#     captured_at + primary_reset_s. context-bar.sh renders it as the "Plan usage:"
#     segment on shim-lane sessions (window labels derived from window-minutes; stale-
#     window drop rule; zero secondary omitted). INSTALL-SHARED: under the shared-/daaf
#     multi-install assumption this state file lives on the shared mount and is read by
#     any install's statusline (auth under $HOME stays per-install). Pure additive
#     telemetry: no new env vars, no off-switch; a write failure is swallowed and never
#     touches the response path. SHIM_VERSION -> 1.3.1.
#   v1.3.0 (2026-07-20): ChatGPT-lane auth refresh DELEGATED to the codex CLI
#     (Tier 3 A1; minor bump — behavior + config-surface change). The shim is now a
#     pure READER of $CODEX_HOME/auth.json; codex is the SINGLE WRITER. This deletes
#     the shim's Python OAuth reimplementation and structurally eliminates the
#     refresh-rotation race that caused the 2026-07-20 auth lockout.
#     A1-i (delegation core, committed separately):
#       * DELETED the Python refresh path: the OAuth token POST to
#         auth.openai.com/oauth/token, rotated-refresh-token atomic persistence, the
#         manager.rs-mirror reload-before-refresh guard, and the SHIM_OAUTH_TOKEN_URL/
#         SHIM_OAUTH_CLIENT_ID env seams (their only consumer was the deleted path).
#         No legacy fallback flag — a retained Python path would preserve the race.
#       * ADDED delegated_refresh(): a single-flight (asyncio.Lock) primitive that
#         spawns `{SHIM_CODEX_BIN} login status` (CODEX_HOME passthrough, bounded by
#         SHIM_CODEX_TIMEOUT_S) then RE-READS auth.json and judges success SOLELY by
#         the re-read result — the subprocess exit code/output are diagnostic-only.
#         Proactive trigger: token within a 5-min exp margin (was 30 min) mirroring
#         codex's CHATGPT_ACCESS_TOKEN_REFRESH_WINDOW_MINUTES so codex actually
#         refreshes when asked. Reactive trigger: backend 401 -> one delegated_refresh
#         + single retry (existing retry-guard shape preserved).
#       * NEW config: SHIM_CODEX_BIN (default "codex") and SHIM_CODEX_TIMEOUT_S
#         (float, default 30, unparseable->30). CODEX_HOME passthrough unchanged.
#       * Every auth-failure surface (failed delegation, post-retry 401, absent/
#         unreadable store, codex "Not logged in"/missing/timeout) raises the actionable
#         _RELOGIN_MSG that literally contains `codex login --device-auth` (A1-R5).
#     A1-ii (auth surfaces, this dispatch):
#       * A1-R4: /health gains a read-only `auth` block {state, expires_at, days_left,
#         recovery?} on the chatgpt lane ("n/a" on the openai lane). state is
#         valid|expiring|expired|absent|unreadable, derived from auth.json presence +
#         JWT exp decode only — NEVER token material. `recovery` (the literal re-login
#         command) is present only for the four actionable states. "expiring" = exp
#         within _AUTH_EXPIRING_WINDOW_S (48h) — a USER heads-up horizon, deliberately
#         wider than the internal 5-min refresh margin.
#       * A1-R6a: start_shim.sh readiness + --status query /health and print an auth
#         line; expiring -> prominent "expires in N days" warning naming
#         `codex login --device-auth`; expired/absent/unreadable -> the "is dead" phrasing.
#       * A1-R6b: deploy-smoke T0.9 extends from "auth.json readable" to asserting the
#         /health auth block on shim routes: FAIL on expired|absent|unreadable, WARN on
#         expiring, PASS on valid (SKIP on non-shim routes).
#       * A1-R7: SHIM_CODEX_BIN/SHIM_CODEX_TIMEOUT_S documented in the Config block and
#         start_shim.sh help/env passthrough.
#     Review fix-it (post-A1 three-angle review; version unchanged): guard
#       _auth_health_block() against a pathological JWT exp overflowing platform time_t
#       (classify "unreadable" rather than raising, upholding the never-raises
#       contract); bound the post-kill codex reap with a 5s wait_for so an unkillable
#       child cannot stall the request path; and swept the deleted SHIM_OAUTH_* seams
#       out of the host settings template and the user docs (install guide + technical
#       FAQ), which still framed the now-delegated refresh as a shim-side rotation race.
#     The two historical v1.2.5 comments describing the now-deleted Python OAuth path
#     carry inline "[superseded in v1.3.0 ...]" markers so version history stays
#     accurate without asserting present-tense behavior that no longer exists.
#     SHIM_VERSION -> 1.3.0.
#   v1.2.14 (2026-07-20): Robustness (R1-R6) + diagnostics (D1-D5) hardening pass,
#     driven by the v1.2.8/v1.2.13 self-inflicted-outage retrospective. Doctrine:
#     "strict emit, tolerant accept" — every change moves an unexpected upstream
#     input from {silent drop | hard fail} to {tolerate + count + log}, while the
#     downstream Anthropic SSE emission stays exactly as strict as before.
#     ROBUSTNESS:
#       R1 (observability): a bounded process map + per-request counters make unknown
#         SSE event types, unmodeled output_item types, and unrecognized error
#         envelopes VISIBLE (terminal record: unknown_events/unknown_items, 0 when
#         clean) instead of vanishing. Logged via the v1.2.12 wire-divergence channel
#         (first + every 100th), never per-event, never bodies. A live obfuscation
#         field on arguments.delta is explicitly tolerated (no count, no failure).
#       R2 (classification): ONE code-driven classifier on all failure paths (pre-
#         stream HTTP, in-band error, response.failed, non-stream adapter). Envelope
#         tolerance parses {error:{...}}, {status,error:{...}}, flat root code/message,
#         and the Codex {detail:"..."} shape; first match wins, unrecognized is R1-
#         counted then status-classified. insufficient_quota/usage_not_included ->
#         invalid_request_error (mirrors Anthropic's own credit-balance 400); unknown-
#         code 4xx -> invalid_request_error (CHANGED from retryable api_error).
#         ADJUDICATED: a bare/unknown-code 503 -> api_error (retryable); overloaded_
#         error is reserved for recognized overload codes and status 529 (both classes
#         retryable, so client behavior is equivalent).
#       R4 (retry policy): retry gating is now classification-driven (RETRY_STATUSES
#         stays as the envelope-less fallback). insufficient_quota-coded 429 fails
#         fast (was retried as a transient 429 — a confirmed defect class). Per-attempt
#         delay precedence parsed -> Retry-After -> backoff; the rate-limit-delay hint
#         ("try again in <n>") is parsed for the NUMBER only (gated on
#         rate_limit_exceeded, never logged). Rate-limit-class cap raised 30s -> 60s;
#         a delay beyond the cap fails fast with rate_limit_error so the client owns
#         the long wait. Terminal record gains retry_delay_source (parsed|header|
#         backoff). Retry counts and the no-retry-after-first-byte invariant unchanged.
#         The ≥400 error body read for classification is bounded at 1 MiB
#         (MAX_ERROR_BODY_BYTES): a pathologically large body is truncated before the
#         retry-classification parse and falls back to HTTP-status gating; the full body
#         stays cached on resp for the caller's error re-read (behavior unchanged).
#       R5 (SSE tail): BEHAVIOR CHANGE — at EOF a non-blank-terminated tail whose
#         pending event parses cleanly is now FLUSHED as the final event (recovers a
#         complete terminal whose trailing blank line a proxy trimmed, B7); a malformed
#         tail after the terminal frame is R1-counted and ignored; before the terminal
#         it stays a fatal framing failure. One pinned test intentionally flipped
#         (..._fails -> ..._flushes).
#       R3 (tolerant reducer): open-block bookkeeping is a deferred-open scheduler
#         (pending tools opened FIFO in added order; at most one Anthropic tool_use
#         block open at a time; downstream blocks stay strictly non-overlapping).
#         null/[] response.completed.output after tool events is guarded (streamed
#         state wins); a text block still opens on output_text.delta independent of
#         content_part.added; a no-reasoning turn is tolerated. Malformed-JSON on NON-
#         load-bearing status events is skipped + R1-counted; load-bearing events
#         (deltas, argument events, output_item.*, terminal, error) keep strict
#         failure. Out-of-order text/reasoning arriving while a block is open is
#         buffered and emitted as a TRAILING text/thinking block (ratified shapes).
#         DEVIATION: _finalize_stream_failure's block-close sort is filtered to OPENED
#         tools only (a still-deferred tool has no downstream block and a None index) —
#         semantically inert. DEFERRED: oversized-payload tolerance (the 16 MiB cap
#         fires inside the bounded reader before the event type is knowable; a type-
#         aware reader would disturb the R5 EOF-tail region). Four pinned strict-
#         ordering tests intentionally flipped to the tolerant contract.
#       R6 (heartbeat): while the upstream is silent after message_start, the streaming
#         path emits Anthropic `ping` SSE events every SHIM_PING_INTERVAL_S (env, float-
#         tolerant, default 15, <=0 disables) through the SAME single-writer lock as
#         emit(), so a ping can never split a partial frame. The watchdog stops before
#         the terminal frames and on failure/disconnect (reaped by the request resource
#         finalizer as a safety net); a failed ping write is treated as a disconnect
#         (fast dead-client detection). Streaming only; /health unchanged. Terminal
#         record gains max_idle_gap_ms (max upstream inter-event silence, ms).
#     DIAGNOSTICS:
#       D1 (quota capture): DIAG_HEADER_ALLOWLIST gains prefix matching (x-codex-*)
#         plus exact x-oai-request-id; a chatgpt-lane 2xx now emits ONE grep-stable
#         event=quota_snapshot line of numeric/enum fields (plan/limit, primary+
#         secondary used-percent/window-minutes/reset-after, credits flags/balance;
#         absent -> "-", values machine-field-encoded, never free text). openai lane
#         and every non-2xx unchanged (no line).
#       D2 (terminal enrichment): additive-only terminal fields — unknown_events/
#         unknown_items, populated backend_type/backend_code on in-band failures,
#         retry_delay_source, max_idle_gap_ms. All existing fields unchanged.
#       D5 (400 diagnosis): a backend-classified invalid_request_error emits one
#         request-correlated event=request_shape line of sorted top-level request key
#         NAMES (+ text/reasoning sub-key names) — names only, never values.
#       D3/D4 (lifecycle honesty + --auto footgun): implemented in start_shim.sh by a
#         parallel dispatch (supervisor.state running|gave_up_storm|stopped surfaced by
#         --status; an unrecognized non-empty DAAF_PROVIDER_SHIM warns once and still
#         exits 0). See start_shim.sh; not in this file.
#     R1 ALLOWLIST-SYNC OBLIGATION: the R1 unknown-event/item counters fire only for
#       types outside _KNOWN_EVENT_TYPES/_KNOWN_ITEM_TYPES; those allowlists MUST stay
#       in sync with the R3 reducer's handled/skippable event sets or "0 when clean"
#       regresses (A1b tripwire tests guard this). v1.3.4 (V4-R5) grew the ignored
#       (skippable) group by `keepalive` and `response.metadata` — see that changelog
#       entry; the two catch-alls compare raw event-type strings, so both absorb by
#       plain set membership with no namespace logic.
#     ENVIRONMENTAL NOTE: shim STATE under /daaf (the repo/volume) is install-shared
#       across containers on the same mount, while OAuth auth under $HOME/.claude
#       (CODEX_HOME) is per-install — a token refresh in one install does not
#       propagate, so concurrent installs must not be assumed to share auth.
#     SCOPE: no auth-layer changes (the OAuth/token-delegation direction is the
#       BindMounts session's Tier 3). Additive-only logging; scrubber discipline
#       preserved. INTENTIONAL TEST UPDATES: 6 total (2 R5-region + 4 R3-region flips).
#       SHIM_VERSION -> 1.2.14.
#   v1.2.13 (2026-07-19): System-role message admission (live-outage fix). Current
#     Claude Code appends a role:"system" message inside `messages`; the v1.2.12
#     request-validation role check (user/assistant only) and the translator's
#     matching raise rejected every real conversation turn with the static 400
#     "invalid request structure" while small side requests (no system-role
#     message) still passed. Validation now admits "system" and the translator
#     folds system-role messages to user-role input — the exact pre-v1.2.12
#     mapping proven against the live Codex backend. Captured-payload repro and
#     bisection: scripts/scratch/replay_captured_request.py. All other v1.2.12
#     hardening, translation, and lifecycle behavior unchanged.
#     SHIM_VERSION -> 1.2.13.
#   v1.2.12 (2026-07-18): Content-blind image fidelity and bounded translator
#     diagnostics. User and tool-result image blocks now map to Responses
#     input_image parts for the shared OpenAI/ChatGPT payload shape, with strict
#     local validation and explicit 400s for unsupported sources, assistant images,
#     and unknown history blocks. Transport lifecycle records now attribute bounded
#     exception classes/phases, sent and returned request IDs, and retry sources.
#     The live Codex arguments.done missing-name divergence is process-aggregated
#     (first occurrence plus periodic summaries) instead of warning per event.
#     /health now carries an exact service identity so the lifecycle manager can
#     reject an unrelated HTTP 200 before declaring readiness. Retry counts,
#     backoff policy, response translation, reasoning continuity, and cancellation/
#     cleanup ownership are unchanged. SHIM_VERSION -> 1.2.12.
#   v1.2.11 (2026-07-17): Correlated request-lifecycle observability and
#     structured backend-error normalization. Every /v1/messages request now owns
#     an internally generated 32-hex correlation ID in a ContextVar before body
#     reading; the same ID is returned as x-daaf-request-id and annotates shim/httpx
#     stderr records with a stable phase. Grep-stable lifecycle events cover parse,
#     upstream attempts/retries/headers/first event, first downstream content,
#     backend failure, disconnect, one terminal record, and one cleanup record with
#     monotonic integer timings. Attempt accounting is updated before every actual
#     Responses call, including raising/exhausted paths. Allowlisted upstream request
#     IDs and normalized HTTP versions are recorded without replacing the local ID.
#     Terminal semantic-frame and final-body-close sends are tracked independently as
#     not_attempted/attempted/send_completed/skipped_disconnect/write_failed; an
#     awaited send returning means only send_completed, never client receipt. A shared
#     structured normalizer now maps context_length_exceeded to invalid_request_error,
#     server_error to api_error, preserves real non-2xx status mapping, and emits only
#     a scrubbed bounded message rather than serialized backend objects. First causal
#     outcome wins, body-read disconnects are recognized, and cleanup failures remain
#     visible without overwriting success/error. Retry policy, timeout/backoff values,
#     pooling, heartbeat behavior, translation, cache, and tool sanitization are
#     unchanged. SHIM_VERSION -> 1.2.11.
#   v1.2.10 (2026-07-16): ChatGPT-lane error-contract fidelity + claude-slug
#     fast-fail, from the first full live v1.2.8/v1.2.9 session (shim.log 14:15+).
#     LIVE EVIDENCE: (1) the Codex subscription lane ACCEPTED a real 337,034-token
#       input (13:35, gpt-5.6-sol) but REJECTED ~400k real tokens with a
#       deterministic 400 context_length_exceeded (14:17, 14:54) — a far lower
#       ceiling than the API lane's ~1.05M. The non-stream chatgpt adapter
#       collapsed that 400 to a flat 502 api_error, which reads as transient; the
#       client then retried the unsatisfiable input ~10x (client-side reaction —
#       the shim's own RETRY_STATUSES excludes 400 and never retried it). (2) A
#       background/scheduled runner using the saved default model produced a
#       claude-fable-5 rejection burst (14:52-14:53, ~50 req/min) — the Codex
#       backend 400s every claude-* slug ("not supported when using Codex with a
#       ChatGPT account"), yet each was a full wasted round-trip.
#     FIXES (chatgpt lane only unless noted; openai/API-key lane untouched):
#       (a) NON-STREAM status passthrough: a backend HTTP rejection now reaches the
#           client with its REAL status and a mapped Anthropic error type (400->
#           invalid_request_error, 401->authentication_error, 403->permission_error,
#           404->not_found_error, 429->rate_limit_error, 529->overloaded_error,
#           other 5xx->api_error) instead of a flat 502 api_error. The scrubbed
#           backend message is preserved; the 401-refresh-exhausted _RELOGIN_MSG
#           special case is unchanged. Retryable statuses still exhaust the internal
#           retry loop first — passthrough governs only what is finally sent.
#       (b) STREAMING in-band error-type mapping (BOTH lanes): the pre-content
#           status/connect failure finalizer now emits the same status-aware error
#           type in its in-band SSE event:error (shared helper). HTTP status stays
#           200 (the stream has already started — Claude Code reads errors from
#           events). Mid-stream protocol/framing/transport failures (no backend
#           status) keep api_error; the v1.2.8 finalizer block-closing and terminal
#           ordering are unchanged.
#       (c) CLAUDE-SLUG FAST-FAIL: a mapped model slug beginning with "claude"
#           (case-insensitive) is rejected on the chatgpt lane with a 400
#           invalid_request_error BEFORE any backend round-trip, for both stream and
#           non-stream inbound requests, carrying an actionable remap instruction
#           (ANTHROPIC_DEFAULT_OPUS_MODEL / ANTHROPIC_DEFAULT_SONNET_MODEL /
#           CLAUDE_CODE_SUBAGENT_MODEL). One scrubbed WARNING per rejection.
#           [2026-10-12 text-only amendment, no logic change: the instruction now
#           names all four tier aliases (OPUS/SONNET/HAIKU/FABLE) and no longer
#           offers CLAUDE_CODE_SUBAGENT_MODEL, which Claude Code >= 2.1.251 treats
#           only as a fallback for subagents without their own model.]
#     WHY: deterministic backend rejections must not look retryable. The intended
#       effect is that Claude Code stops the retry storm on context_length_exceeded
#       once it sees invalid_request_error; that suppression is EXPECTED but pending
#       live verification (the retry multiplier originates client-side, not in this
#       shim). A companion user-run probe (scripts/provider_shim/
#       probe_context_ceiling.py) measures the exact Codex-lane ceiling; the window
#       constant itself lands in the hooks/docs workstream, not here.
#     REVIEW AMENDMENTS (pre-commit, same version): (c) the fast-fail now matches
#       the LAST path segment of the mapped slug (rsplit "/"), so a provider-prefixed
#       "anthropic/claude-*" is caught when SHIM_STRIP_MODEL_PREFIX is unset (a
#       whole-slug startswith would have slipped it to the backend); companion probe
#       hardened (URLError -> clean "shim not reachable" exit, --self-test now drives
#       the real bisect via post_fn injection, bracket clamp on accept overshoot).
#     SHIM_VERSION -> 1.2.10.
#   v1.2.9 (2026-07-16): Live-evidence fixture rebase + request-accounting
#     repair, from the first live v1.2.8 session (shim.log 14:15+).
#     LIVE EVIDENCE: the Codex backend omits ONLY `name` on
#       response.function_call_arguments.done (dozens of "wire-divergence:
#       arguments.done missing name" warnings; zero missing-arguments,
#       missing-id, or usage-drop warnings). Item ids and the complete
#       arguments string ARE present on the live wire, so the v1.2.8 name
#       fallback is the live-exercised path. The loopback fixtures now encode
#       this name-less live shape; a dedicated regression keeps the public-API
#       name-bearing shape covered (matching name passes, conflicting fails).
#     ACCOUNTING FIX: under v1.2.7/v1.2.8 the streamed-success "req ..." log
#       line was skipped on essentially every live request — Claude Code closes
#       the connection immediately after message_stop, and the disconnect-gated
#       final empty-body send raised _ClientDisconnected before the log line
#       (0 req lines since v1.2.7 activation vs 6,701 before), misreporting
#       completed requests as "client disconnected" and losing per-request
#       usage/duration/stop accounting. The req line is now logged once the
#       awaited ASGI send for message_stop returns, and a disconnect on the
#       trailing empty-body frame is treated as normal completion. That send
#       completion is shim-level evidence, not proof of client receipt.
#       Disconnects BEFORE message_stop
#       keep the existing abort semantics. SHIM_VERSION -> 1.2.9.
#   v1.2.8 (2026-07-16): Live-wire tolerance for the v1.2.7 strict validators.
#     After v1.2.7 activated, EVERY real Codex tool-call turn died with a raised
#     _ProtocolError after a 200 response (shim.log 13:37-13:38, 7/7 turns): the
#     v1.2.7 validators hard-require fields that the loopback mock fabricates but
#     that no live Codex tool-call stream has ever confirmed (the repo's live
#     captures truncate before any arguments.done / output_item.done tool event).
#     Because sanitize mode buffers argument deltas until .done, the failure
#     finalizer closed the already-open tool_use block with input {} — Claude Code
#     then executed EMPTY tool calls ("required parameter ... is missing") before
#     the terminal event:error ("Server error mid-response").
#     FIXES (wire-boundary leniency, conflict/ordering/status checks unchanged):
#       (a) response.function_call_arguments.done requires only item_id; a missing
#           name falls back to the name captured at output_item.added and missing
#           arguments fall back to the buffered delta stream (argument deltas now
#           buffer in BOTH sanitize modes so the fallback is always available);
#       (b) function_call output-item id is optional (the Codex CLI's own struct
#           models it as Option<String>); output_item.done matches the open tool
#           by call_id when id is absent;
#       (c) invalid terminal usage token counts degrade to a dropped field with a
#           WARNING, never a stream failure — a bad counter must not discard a
#           completed generation;
#       (d) every tolerance fallback logs a grep-stable "wire-divergence:" WARNING
#           so one live session documents the real Codex schema, providing the
#           evidence base for rebasing the mock harness fixtures;
#       (e) the post-start stream-failure log line now includes the scrubbed
#           failure message (v1.2.7 logged only the exception TYPE, which is what
#           made this incident statically undiagnosable to the exact field);
#       (f) fixed an UnboundLocalError in the ChatGPT inbound-nonstream path when
#           terminal accumulation raises before terminal_response is assigned.
#     SHIM_VERSION -> 1.2.8.
#   v1.2.7 (2026-07-16): Provider-stream lifecycle hardening. ChatGPT mode now
#     always requests upstream Responses SSE, including when the inbound Anthropic
#     request is non-streaming. For an inbound stream:false request, the shim
#     consumes events in arrival order without retaining the raw transcript,
#     accepts a complete response only from response.completed/incomplete, and
#     sends the terminal event's response object through the existing
#     _responses_to_anthropic() converter. This shares reasoning-cache behavior,
#     thinking/text/tool ordering, sanitization, public call IDs, usage, and stop
#     reasons with the established non-stream translator while adapting Codex's
#     stream:true-only contract.
#     FAILURE POSTURE: a common post-start finalizer closes open text, thinking
#       (with an empty signature), and tool blocks exactly once, emits a bounded
#       Anthropic event:error/api_error, ends the HTTP body, and emits no success
#       terminal events. It covers response.failed, in-band error, post-start
#       transport errors, malformed/oversized SSE, missing terminal events, and
#       malformed block order. [DONE] and clean EOF are not success without a
#       parsed response.completed/incomplete terminal object. Reasoning arriving
#       while text or an unfinished tool block is open is rejected explicitly;
#       reasoning after a fully closed tool remains supported.
#     BOUNDS/INVARIANCE: each upstream SSE event is capped at a conservative 16
#       MiB (ample for realistic 64K output and tool payloads), and failures return
#       bounded scrubbed/generic messages. The OpenAI/API-key lane retains its real
#       upstream stream:false JSON path and legacy conversion behavior. Deterministic
#       real-shim regressions cover all new success, failure, ordering, and startup-
#       retry contracts. SHIM_VERSION -> 1.2.7.
#     PROTOCOL REVIEW FIXES (same v1.2.7): pre-content status/connect failures now
#       use the common event:error finalizer; one shared validator enforces terminal
#       event/status/container/token coherence before conversion or cache access;
#       malformed event fields and narrow translation/state exceptions fail cleanly;
#       duplicate tool lifecycle replays are idempotent only when identical and fail
#       when conflicting; text/tool overlap and duplicate item IDs are rejected; EOF
#       never synthesizes an SSE blank-line boundary; and the first valid terminal
#       event stops semantic consumption promptly. The downstream success/failure
#       lifecycle oracles enforce exact message-start/terminal grammar.
#     DISCONNECT CANCELLATION REVIEW FIX (same v1.2.7): each response now owns an
#       asyncio.Event set immediately by the ASGI disconnect watcher. One shared
#       cancellation-race helper safely races stream header acquisition, upstream
#       body reads, non-stream POSTs, and retry sleeps against that event, cancels
#       and awaits losing tasks, preserves outer task cancellation, and retrieves
#       completed-task exceptions. A narrow _ClientDisconnected control signal
#       returns without downstream error/success bytes while caller finally blocks
#       close the active upstream context. Deterministic real-loopback regressions
#       cover blocked headers, blocked bodies, and Retry-After sleep cancellation.
#     CANCELLATION-OWNERSHIP FOLLOW-UP (same v1.2.7): once a rotating OAuth refresh
#       POST is launched, one explicitly owned refresh task now completes response
#       validation, rotated-token extraction, atomic persistence, and in-memory state
#       update before request disconnect or outer cancellation propagates. The token
#       lock remains held until that task settles, so waiters observe either the new
#       persisted token or the bounded refresh failure. Stream opening also closes a
#       locally owned context when outer cancellation races a successful __aenter__;
#       the shared race helper settles and retrieves both child outcomes on every
#       cancellation path. Focused regressions cover refresh commit survival, the
#       stream-enter ownership race, and a log-gated retry-sleep disconnect.
#   v1.2.6 (2026-07-15): ChatGPT-subscription reasoning-summary boundary
#     repair. An authorized live Codex probe observed 15 consecutive reasoning
#     output items containing 44 nonempty summary parts. Every part carried a
#     stable item_id/output_index/summary_index identity (summary_index restarted
#     at 0 for each new reasoning item), completed the full part.added ->
#     text.delta -> text.done -> part.done lifecycle, and arrived adjacent to the
#     next reasoning part/item with no intervening text or tool transition. The
#     shim consequently emitted all 44 source deltas in one Anthropic thinking
#     block; because later source parts began with "*" rather than whitespace,
#     legacy byte concatenation collapsed their Markdown boundaries.
#     STREAMING FIX (chatgpt mode only): within each open Anthropic thinking
#       block, identify a semantic summary part by the validated composite
#       (item_id, output_index, summary_index), using nonempty item_id as the
#       preferred item scope and a valid output_index as fallback. Before the
#       first nonempty delta of each newly seen stable part after the first, emit
#       one separate thinking_delta containing exactly "\n\n"; forward every
#       source delta unchanged and never replay text from .done events. Identity
#       is consumed in arrival order only — no sorting or buffering. Missing,
#       malformed, mixed, or contradictory identity disables boundary synthesis
#       for the remainder of that thinking block, preserving exact legacy append
#       rather than guessing a split. Contradiction includes either one item_id
#       moving between output indexes or one output_index being reused by different
#       item IDs. Opening a new thinking block resets all reliability/maps. Focused
#       real-shim regressions cover every malformed/partial identity branch,
#       bidirectional item/output contradictions, and cleanup/env isolation.
#     NON-STREAMING PARITY (chatgpt mode only): preserve source strings exactly,
#       ignore only exactly-empty summary strings for separator decisions, and
#       join nonempty parts and reasoning items with "\n\n". Whitespace-only
#       strings remain real content. Equivalent streaming/non-streaming semantic
#       content therefore reconstructs to the same text.
#     OPENAI INVARIANCE: the API-key lane retains the exact legacy streaming
#       forwarding and non-streaming empty-string concatenation behavior; it does
#       not inspect summary identities or add response bytes. Auth, requests,
#       tools, signatures, usage, cache, retry, count-token, and lifecycle logic
#       are unchanged. SHIM_VERSION -> 1.2.6.
#   v1.2.5 (2026-07-15): ChatGPT-subscription (Codex) backend lane. A new
#     SHIM_BACKEND_MODE env knob (default "openai") adds a mode-switched second
#     backend lane, "chatgpt", that routes Claude Code through the ChatGPT
#     subscription's Codex Responses backend
#     (POST https://chatgpt.com/backend-api/codex/responses) using the OAuth
#     access_token from $CODEX_HOME/auth.json as the Bearer — NO api.openai.com
#     API key. The api.openai.com API-key lane ("openai") keeps working unchanged;
#     the two lanes diverge in auth + base URL and ONE small body delta (below).
#     The proven v1.2.0+ Responses translator (tools, SSE, reasoning cache,
#     sanitizer, retry, diagnostics, count_tokens calibration) is REUSED UNCHANGED —
#     the chatgpt lane forks nothing in the translator's structure.
#     BODY DELTA (live-observed, smoke 30, 2026-07-15): the Codex backend REJECTS
#       max_output_tokens with a verbatim 400 "Unsupported parameter:
#       max_output_tokens" (it is not in the notes/08 body floor), whereas the
#       api.openai.com lane requires/accepts it. So max_output_tokens is emitted
#       (clamped to >=16) in openai mode and OMITTED entirely in chatgpt mode; the
#       Codex backend applies its own output ceiling. The inbound max_tokens contract
#       is untouched (still read from the client).
#     WHY the backend needs almost nothing (notes/08, 7 live ablation requests):
#       chatgpt.com/backend-api/codex/responses gates on a valid OAuth Bearer and
#       nothing else. ALL codex telemetry/fingerprint (x-codex-*, chatgpt-account-id,
#       originator, user-agent, client_metadata, prompt_cache_key) is IGNORED; the
#       backend accepts a STANDARD top-level Responses `tools` array (auto-upgrades
#       strict:false->true) and returns STANDARD Responses SSE. So chatgpt mode emits
#       ONLY the 3-header floor: authorization (Bearer <access_token>),
#       content-type: application/json, accept: text/event-stream.
#     TOKEN LAYER [SUPERSEDED in v1.3.0 — the Python OAuth refresh described in
#       present tense below (the auth.openai.com token POST, rotated-refresh-token
#       persistence, and the manager.rs-mirror reload guard) was DELETED in v1.3.0;
#       auth refresh is now delegated to the codex CLI (see the v1.3.0 entry). The
#       paragraph is preserved verbatim as v1.2.5 history — read it in the past tense]
#       (the only genuinely new component; notes/09 + notes/10, live-
#       verified): the access_token TTL is ~10 days, so within any DAAF session the
#       shim refreshes ~never — it is read-mostly. It decodes the access_token JWT
#       PAYLOAD ONLY (never the signature) for the `exp` claim and refreshes only
#       when exp is within a 30-min safety margin OR on a backend 401 (lazy).
#       Refresh = POST https://auth.openai.com/oauth/token with
#       client_id=app_EMoamEEZ73f0CkXaXp7hrann, grant_type=refresh_token. The
#       refresh_token ROTATES on every refresh (consuming a stale one -> permanent
#       refresh_token_reused lockout), so the new tokens MUST be persisted. Persist
#       is ATOMIC (temp file in the same dir -> chmod 0600 -> os.replace()),
#       preserving OPENAI_API_KEY/auth_mode/tokens.account_id and writing
#       last_refresh in codex's exact format (RFC3339 UTC, 9-digit nanosecond
#       fractional seconds, trailing Z — Python gives 6 digits, zero-padded to 9).
#       Before refreshing, the shim does a GUARDED reload-before-refresh (mirror
#       codex manager.rs:2388): re-read auth.json; if the on-disk access_token's exp
#       is newer than the one held, adopt it and SKIP the refresh (another writer
#       beat us to it). Own refreshes are serialized with an in-process asyncio.Lock.
#       A permanent refresh failure fast-fails with an actionable re-login message
#       ("run 'codex login --device-auth' inside the container to re-authenticate")
#       rather than spinning. The refresh response is deserialized LENIENTLY —
#       undocumented fields (earliest_refresh_at, oai_is) are tolerated/ignored;
#       earliest_refresh_at is NOT honored for scheduling (the shim keys on the live
#       exp claim).
#     CREDENTIAL SAFETY: no token value (access_token, refresh_token, id_token, the
#       JWT, the Bearer, or OPENAI_API_KEY) is ever logged/printed/echoed. Writing
#       token values INTO auth.json (0600) is the intended credential-store
#       operation, not a leak. The _diag_headers Authorization exclusion invariant is
#       preserved. Presence is checked with `if not tok:` guards, never by printing.
#     HEALTH/LOG (cycle 1, uncommitted — no version bump): four adjudicated
#       cleanups. (a) The OAuth refresh POST gets a DEDICATED short timeout (10s
#       connect / 30s read) instead of the shared _client's 600s read window, so a
#       hung auth.openai.com cannot hold _token_refresh_lock (and block concurrent
#       chatgpt-lane requests) for up to 600s; httpx timeout -> the existing clean
#       RuntimeError(_RELOGIN_MSG). (b) The two OAuth test/staging override env vars
#       (SHIM_OAUTH_TOKEN_URL, SHIM_OAUTH_CLIENT_ID) were documented in the Config
#       block and in start_shim.sh (production leaves them unset -> hardcoded
#       codex defaults). [SUPERSEDED in v1.3.0 — both env seams were REMOVED with the
#       Python refresh path; they no longer exist in the Config block or start_shim.sh.]
#       (c) codex_home_present is now HONEST — it reflects actual
#       auth.json readability (os.access R_OK), not merely CODEX_HOME being set,
#       matching the "resolvable auth.json" docstring; applied to BOTH /health and
#       the startup log field so they agree. Still a presence-only boolean (no
#       path/secret leak).
#     HEALTH/LOG: /health and the startup log gain backend_mode and a
#       codex_home_present boolean (no secret/path leak). SHIM_VERSION -> 1.2.5.
#     All v1.2.4 invariants preserved untouched (verbosity resolver, four-tier
#     effort resolver, suffix strip, tool-arg scrubber, reasoning cache, store:false,
#     retry/backoff, backend-error diagnostics, count_tokens calibration, the
#     max_output_tokens floor).
#   v1.2.4 (2026-07-12): Response verbosity control via a new SHIM_TEXT_VERBOSITY
#     env knob (default "high"), user-approved. The outbound /v1/responses payload
#     now ALWAYS carries text:{"verbosity": V}. V resolves once at startup from
#     SHIM_TEXT_VERBOSITY (case-insensitive, whitespace-trimmed): values low|medium|
#     high map through identity; an unrecognized/empty/whitespace value logs ONE
#     startup WARNING and falls back to the default "high". The default "high" is a
#     user-locked posture choice — parity with DAAF's warm/educational Claude
#     sessions, same rationale as the SHIM_REASONING_EFFORT default "high".
#     WHY the field is always sent: text.verbosity is LIVE-CONFIRMED accepted by
#       gpt-5.6-sol on /v1/responses (HTTP 200 for both "high" and "low", probe
#       research/2026-07-11_FrameworkDev_ShimDiagnostics_AuthOptions/scripts/
#       live_tests/18_diag-verbosity-compare.py, 2026-07-12) — reclassifying the
#       notes-04 §5/confidence-table "verbosity: LOW/not confirmed" claim to
#       CONFIRMED. "medium" is the documented middle value; NOT independently
#       live-probed here (the 18-probe exercised default/high/low only) — asserted
#       in mock and marked # ASSUMES: at the resolver.
#     EFFECT (observed in the 18-probe, informational): "high" adds warmth/volume
#       — at a 1600-token cap "high" truncated (status incomplete) while "low"
#       completed at 1109 tokens. This is NOT a production concern: real Claude
#       Code sessions send max_tokens=32000, far above where verbosity=high would
#       clip a normal turn; the effect surfaces only against an artificially small
#       cap.
#     Read at startup like SHIM_REASONING_EFFORT; the shim's "starting" startup
#     log line gains a text_verbosity=<v> field (per-request "req" lines are
#     unchanged — verbosity is a startup constant, not per-request). SHIM_VERSION -> 1.2.4 (/health reports it,
#     single-source). All v1.2.3 invariants preserved untouched: the four-tier
#     effort resolver, "#<effort>" suffix strip, tool-arg scrubber, reasoning
#     cache, store:false, retry/backoff, backend-error diagnostics, count_tokens
#     calibration, and the max_output_tokens floor.
#   v1.2.3 (2026-07-12): Two fixes from a live real-GPT session (shim.log
#     1377-1416), user-approved.
#     FIX 1 — Demote inbound "high". Claude Code v2.1.187 PINS
#       output_config.effort="high" on EVERY request for unknown/custom slugs
#       (the effort capability is model-ID-pattern-gated; docs-verified — a slug
#       the client doesn't recognize as effort-capable gets the hardcoded default
#       "high"). With tier 1 honoring that constant, every request logged
#       effort=high:inbound, the /model effort UI was INERT for GPT slugs, and the
#       slug/env tiers were dead in practice. Fix: in the effort resolver, when the
#       inbound output_config.effort normalizes to exactly "high", treat it as the
#       pinned constant — SKIP tier 1 and fall through (slug > env > default), with
#       NO warning log (it fires on essentially every request; silent by design).
#       All OTHER inbound values keep tier-1 status: low/medium/xhigh/max honored,
#       thinking:{"type":"disabled"}->none unchanged, malformed->existing
#       warn+fall-through unchanged. Consequences (intentional): a deliberate UI
#       "high" is now indistinguishable from the pin and equals the fall-through
#       default anyway; users steer via the "#<effort>" slug suffix or
#       SHIM_REASONING_EFFORT. The effort=<value>:<source> log field now reports
#       whichever tier actually supplied the value (an inbound-high request with no
#       slug/env logs effort=high:default, NOT high:inbound).
#     FIX 2 — max_output_tokens floor. On a /model switch the client sent a probe
#       request with max_tokens:1; OpenAI rejected it with a verbatim
#       400 invalid_request_error on param max_output_tokens:
#       "Expected a value >= 16, but got 1" (shim.log 02:06:41 + 02:07:26),
#       blocking /model switching TO GPT slugs in the UI. Fix: clamp the outbound
#       max_output_tokens to max(16, value) (OpenAI's documented minimum). No other
#       max-tokens behavior change; the client's max_tokens=1 model-switch probe
#       origin is undocumented (observed, noted as such).
#     All v1.2.2 invariants preserved (control-char scrub, suffix-strip discipline,
#     output_config drop, reasoning cache, store:false, scrubber, retry,
#     diagnostics, count_tokens calibration). SHIM_VERSION -> 1.2.3 (/health).
#   v1.2.2 (2026-07-11): Reasoning-effort flexibility via a four-tier precedence
#     chain, replacing the single startup-only SHIM_REASONING_EFFORT knob. The
#     outbound payload now ALWAYS carries reasoning.effort (previously it was
#     omitted unless the env var was set, letting the backend default of "medium"
#     apply). Precedence, first present wins:
#       1. Inbound per-request signal — output_config.effort (Claude Code v2.1.187
#          sends this top-level field for custom slugs; wire-captured 2026-07-11).
#          thinking:{"type":"disabled"} inbound also counts as tier 1 -> the
#          minimum-reasoning value ("none"). thinking:{"type":"adaptive"} is NOT a
#          level and does not satisfy tier 1.
#       2. Slug suffix — "#<effort>" parsed and stripped from the inbound model
#          (e.g. "gpt-5.6-sol#high"). The [1m] window hint is consumed client-side
#          and never reaches the shim, so only "#<effort>" is ever parsed here.
#       3. Env — SHIM_REASONING_EFFORT (unchanged name; still read once at startup).
#       4. Default — "high" (posture parity with DAAF Claude sessions).
#     Value handling: values in the gpt-5.6 accepted set (none|low|medium|high|
#     xhigh|max, per notes file 04 §5) map through identity; any other value at any
#     tier is treated as unknown for that tier — one WARNING is logged and the tier
#     is IGNORED (fall through to the next), EXCEPT a known-but-unsupported clamp
#     path is retained for defensiveness (currently only "minimal" -> "low", which
#     notes file 04 flags as LOW-confidence for gpt-5.6). The "#<effort>" suffix is
#     ALWAYS stripped from the model everywhere it is consumed (backend payload,
#     count_tokens path, and every log line) even when its value is unknown/ignored
#     — a "#"-bearing model is never forwarded to OpenAI. Observability: the per-
#     request "req ..." log line gains effort=<value>:<source> (source in
#     {inbound,slug,env,default}). output_config is NEVER forwarded to OpenAI (the
#     Anthropic-inbound-only contract is otherwise unchanged; thinking is still
#     dropped from the outbound payload). SHIM_VERSION -> 1.2.2 (/health reports it).
#     Hardening (CP2): the bare model is control-char-scrubbed (\x00-\x1f,\x7f)
#     before it is logged (closes a log-injection vector via a CR/LF-bearing model
#     slug); a malformed non-string/empty effort value now logs a WARNING too.
#   v1.2.1 (2026-07-11): Self-calibrating count_tokens estimator. Claude Code
#     enforces its LOCAL context-window budget by POSTing the whole request
#     envelope to the base URL's /v1/messages/count_tokens and treating the
#     returned input_tokens as the turn size. The pre-v1.2.1 estimator returned
#     len(raw_json_body)//4, counting the ENTIRE serialized Anthropic envelope
#     (23 tool schemas, JSON keys, brace/quote/backslash escaping) rather than
#     the natural-language text a real tokenizer sees — live-measured to inflate
#     realistic Claude Code envelopes ~1.6-1.9x (diag scripts 03/04, 2026-07-11).
#     Combined with Claude Code assuming a ~200K window for unknown model slugs,
#     GPT sessions died client-side ("Prompt is too long") at ~9% of the real
#     1,050,000 window. Fix: a module-level EMA (alpha 0.3, seed prior 1/4.6
#     tokens-per-byte) of real_input_tokens/inbound_body_bytes, updated after
#     every successful backend response on BOTH the streaming and non-streaming
#     paths from the backend's own reported usage.input_tokens. count_tokens now
#     returns int(body_bytes * ema_ratio * 0.9). The 0.9 is a deliberate LOW
#     bias: an under-estimate at worst lets an oversized request reach the
#     backend, which fails LOUDLY with the v1.1.1 diagnostics; an over-estimate
#     ends the session SILENTLY and prematurely (today's incident). The endpoint
#     is KEPT (not 404'd) — a calibrated estimate beats Claude Code's local
#     fallback and keeps the statusline utilization meaningful. Calibration is
#     process-local (resets on restart; the prior covers cold start). One INFO
#     line is logged when the EMA first moves off the prior; quiet thereafter.
#   v1.2.0 (2026-07-11): Responses API migration. The translation layer was
#     rewritten from OpenAI Chat Completions to the OpenAI Responses API
#     (POST /v1/responses). The Chat Completions translator was REMOVED
#     (generic OpenAI-compatible chat backends out of scope by user decision).
#     Changes:
#       - Request: system -> top-level `instructions`; messages[] -> Responses
#         `input[]` items (input_text/output_text/function_call/
#         function_call_output); tools -> flat internally-tagged
#         {type,name,description,parameters} (NO nested "function": {} wrapper);
#         max_tokens -> max_output_tokens; store:false; include:
#         ["reasoning.encrypted_content"]; reasoning:{summary:"auto"} always
#         (+ effort when SHIM_REASONING_EFFORT is set). temperature and top_p
#         are DROPPED unconditionally (gpt-5.x rejects non-default values while
#         reasoning is active).
#       - Reasoning cache: a module-level bounded LRU (call_id -> reasoning item
#         WITH encrypted_content) populated from responses, re-injected into
#         input[] immediately before the paired function_call on replay. Closes
#         the "function_call was provided without its required reasoning item"
#         gap that neither prior-art reference solves on the replay path.
#       - Streaming: Responses SSE (response.output_text.delta,
#         response.function_call_arguments.delta/.done,
#         response.reasoning_summary_text.delta, response.output_item.added/done,
#         response.completed/incomplete/failed, error) -> Anthropic SSE.
#         Reasoning summaries emitted as an Anthropic THINKING block BEFORE the
#         text block (convergent Claude Code requirement from both references).
#       - New env var SHIM_REASONING_EFFORT (documented in Config below).
#     All hardening (retry/backoff, client-disconnect, usage/empty-response
#     guards, diagnostics logging, scrubber, _sanitize_tool_args rules) is
#     preserved unchanged.
#     Review hardening (cycle 1, uncommitted — no version bump): fixed B1
#     (overlapping content blocks) — on response.output_item.added ->
#     function_call the shim now closes ANY open text block AND any open
#     thinking block (emitting their content_block_stop, resetting state)
#     before opening the tool_use block, so no two blocks overlap on the wire;
#     text arriving after the tool block opens a NEW text block at a fresh index
#     (thinking -> text -> tool -> text yields four distinct, strictly
#     sequential indexes). Fixed W1 (false success on failure) — response.failed
#     and in-band `error` SSE events no longer terminate as a clean end_turn;
#     the shim sets stream_failed, logs ERROR with scrubbed diagnostics, closes
#     any open blocks, emits an Anthropic `event: error` frame ({"type":"error",
#     "error":{"type":"api_error","message":<bounded, scrubbed>}}) and stops
#     WITHOUT message_delta/message_stop.
#   v1.1.3 (2026-07-11): [chat lane, now removed] emit max_completion_tokens.
#   v1.1.2 (2026-07-11): Diagnostics scrubber broadened to {sk,rk,org,proj,sess}.
#   v1.1.1 (2026-07-11): Backend-error diagnostics (allowlisted headers + body).
#
# Config (all via env):
#   SHIM_PORT               default 4141
#   CLAUDE_CODE_DISABLE_FAST_MODE
#                           REQUIRED as exact `CLAUDE_CODE_DISABLE_FAST_MODE=1` on
#                           GPT provider-shim installations/routes. This is Claude
#                           Code's supported native `/fast` disable/hide control.
#                           Control the shim-native route tier with:
#                             bash /daaf/scripts/provider_shim/gpt_fast.sh {on|off|status}
#                           Both exact GPT backends request canonical Responses wire
#                           `service_tier:"priority"` when ON. ChatGPT presents this as
#                           Fast with plan/credit semantics; OpenAI API presents it as
#                           Priority with API Priority billing semantics. Setting changes
#                           require container recreation and a new Claude session,
#                           not a daemon restart or image rebuild. In-container DAAF
#                           code does not mutate the private host configuration.
#   SHIM_BACKEND_MODE       backend lane selector (v1.2.5). Legacy core process
#                           behavior intentionally trims/normalizes the value,
#                           defaults to "openai" when omitted, and warns then falls
#                           back to "openai" for an unknown value. The strict product
#                           boundary is separate: supported provider-route detection,
#                           gpt_fast.sh, and v1.3.8 GPT policy activation require exact
#                           SHIM_BACKEND_MODE="openai" or "chatgpt" paired with exact
#                           DAAF_PROVIDER_SHIM="openai"; omitted, case-varied, or
#                           whitespace-padded values are not accepted there.
#                             * openai  — api.openai.com/v1 API-key lane (the
#                               original, unchanged). Auth = Bearer of
#                               SHIM_BACKEND_API_KEY (from env); default base URL
#                               https://api.openai.com/v1.
#                             * chatgpt — ChatGPT-subscription Codex backend lane.
#                               Routes to https://chatgpt.com/backend-api/codex
#                               (default; still overridable via SHIM_BACKEND_BASE_URL).
#                               Auth = Bearer of the OAuth access_token read from
#                               $CODEX_HOME/auth.json (NOT an API key); the outbound
#                               request emits the validated auth/content/accept floor
#                               plus the privacy-safe X-Client-Request-Id used for
#                               transport correlation. REQUIRES CODEX_HOME set and a
#                               readable auth.json; if either is missing the shim
#                               fails fast with the re-login message rather than
#                               inventing a default path. Request translation, tools,
#                               and the Responses/Anthropic block lifecycle remain
#                               shared with the openai lane. As of v1.2.7, chatgpt
#                               mode always requests upstream SSE (Codex rejects
#                               stream:false); inbound non-stream callers receive an
#                               internally accumulated Anthropic JSON message. The
#                               v1.2.6 response-formatting rule remains route-specific:
#                               chatgpt mode synthesizes "\n\n" between reliably
#                               identified adjacent reasoning-summary parts so
#                               multipart Markdown boundaries survive; openai mode
#                               retains exact legacy concatenation and its real
#                               upstream JSON/non-stream request path.
#   SHIM_BACKEND_BASE_URL   default depends on SHIM_BACKEND_MODE: openai ->
#                           https://api.openai.com/v1; chatgpt ->
#                           https://chatgpt.com/backend-api/codex. An explicit env
#                           value overrides the mode default in either lane. The
#                           Responses endpoint is always {base}/responses.
#                           v1.4.7: trimmed; empty = default; a trailing "/" or
#                           pasted "/responses" suffix is stripped.
#   SHIM_BACKEND_API_KEY    default: value of OPENAI_API_KEY. Used only in openai
#                           mode; ignored in chatgpt mode (the OAuth access_token
#                           is the Bearer there).
#   CODEX_HOME              (chatgpt mode only) directory holding auth.json (the
#                           codex OAuth token store, mode 0600). Compose sets it to
#                           /home/appuser/.claude/codex-daaf. In chatgpt mode the
#                           shim READS $CODEX_HOME/auth.json for the access_token;
#                           when the token is near expiry or a backend 401 rejects
#                           it, the shim DELEGATES the refresh to the codex CLI
#                           (`codex login status`, CODEX_HOME passed through) and
#                           re-reads the result — codex is the single writer, the
#                           shim never writes auth.json. Never logged as a
#                           path-of-secrets; /health reports only a
#                           codex_home_present boolean (True iff auth.json is
#                           readable).
#   SHIM_CODEX_BIN          (chatgpt mode only) codex binary invoked for delegated
#                           token refresh. Default "codex" (on PATH in the DAAF
#                           image). Overridable for portability and for test
#                           injection of a fake-codex stub.
#   SHIM_CODEX_TIMEOUT_S    (chatgpt mode only) wall-clock bound (float seconds) on
#                           the `codex login status` subprocess. Default 30; an
#                           unparseable value falls back to 30. On timeout the child
#                           is killed and the auth.json re-read decides success.
#   SHIM_STRIP_MODEL_PREFIX default "" (e.g. "openai/" to strip for api.openai.com)
#   SHIM_SANITIZE_TOOLS     default ON ("0"/"false"/"no" to disable). Strips
#                           known GPT "fill-every-optional" tool-call quirks
#                           before they reach Claude Code (see
#                           _sanitize_tool_args for the evidence-based rules).
#                           MUST be set to 0 for DAAFBench runs of shim-routed
#                           models — the benchmark measures raw model
#                           behavior. Read once at startup: that means
#                           RESTARTING the shim with the opt-out set.
#                           (v1.4.8) While ON, a streamed tool_use header is sent
#                           only once its arguments are complete, which is what
#                           lets the whitespace-guard retry stay invisible. With
#                           it OFF, headers stream immediately and a guard trip
#                           is never retried (pre-1.4.8 behavior).
#   SHIM_REASONING_EFFORT  TIER 3 of the reasoning-effort precedence chain
#                           (v1.2.2). Read once at startup like the other flags.
#                           Precedence, first present wins:
#                             1. inbound output_config.effort (per-request),
#                                EXCEPT exactly "high" is demoted (v1.2.3): the
#                                client PINS "high" on every request for custom
#                                slugs, so it is treated as unset and falls through.
#                             2. "#<effort>" slug suffix on the model
#                             3. SHIM_REASONING_EFFORT (this env var)
#                             4. default "high"
#                           So the outbound payload ALWAYS carries reasoning.effort
#                           now — this env var only sets the value used when no
#                           usable per-request signal and no slug suffix are present.
#                           Because inbound "high" is demoted (v1.2.3), for GPT
#                           slugs the real steering surfaces are the "#<effort>"
#                           slug suffix (tier 2) and this env var (tier 3).
#                           Valid values: none | low | medium | high | xhigh |
#                           max. ("max"/"xhigh" are supported by both the gpt-5.6
#                           family and gpt-6-astra. NOTE: gpt-6-astra and gpt-6.1-sol
#                           do NOT accept "none" — such a request resolving to
#                           "none" is clamped to "low" at request build; see
#                           _NO_NONE_EFFORT_SLUGS.) "none" disables reasoning on the
#                           gpt-5.6 family (and, per the API, re-enables temperature
#                           — but this shim never sends temperature regardless). An
#                           unrecognized value here is ignored with a WARNING and
#                           the default applies.
#   SHIM_PDF_MODE           (v1.4.8) file | omit, default file. "file" sends
#                           Anthropic PDF document blocks as Responses input_file
#                           parts; "omit" replaces each with a short text note.
#                           Escape hatch if a backend rejects input_file. Read once
#                           at startup; an unrecognized value logs one WARNING and
#                           "file" applies.
#   SHIM_TEXT_VERBOSITY     Response verbosity (v1.2.4). Read once at startup like
#                           the other flags. The outbound payload ALWAYS carries
#                           text:{"verbosity": <value>}. Valid values: low | medium
#                           | high (case-insensitive; surrounding whitespace
#                           trimmed). Default "medium" — a balanced response length
#                           for decision-focused collaboration while preserving
#                           DAAF's evidence requirements. "high" adds warmth/volume;
#                           "low" is terse. An unrecognized, empty, or whitespace-only
#                           value logs ONE startup WARNING and falls back to "medium".
#                           Live-confirmed accepted by gpt-5.6-sol on /v1/responses
#                           (high/low HTTP 200, probe live_tests/18); "medium" is the
#                           documented middle value (asserted in mock, not
#                           independently live-probed here).
# =============================================================================

import os
import sys
import json
import re
import uuid
import time
import random
import asyncio
import logging
import tempfile
import threading
import urllib.parse
from collections import OrderedDict
from contextvars import ContextVar

# The shim is also loaded directly from its file path by deterministic tests. Add only
# this script's own directory so the sibling strict policy library resolves identically
# under direct execution and importlib-based loading.
_SHIM_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SHIM_SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SHIM_SCRIPT_DIR)

from gpt_fast import PolicyStore, native_fast_is_disabled

import httpx
import uvicorn

# --- Config ---
# v1.4.0 ISOLATED DRAFT (2026-09-08): typed hosted-search bridge, bounded
# completed-item collection, truthful URL projection and process-local group replay.
# Subscription max_uses is an observed-call ceiling ONLY; upstream work may precede
# cancellation. Replay expires after 30 minutes or cache eviction/process restart.
# Domain/location mapping and the OpenAI lane are fixture-tested, not live-certified.
# No new health fields, env controls, backend lanes or persistent search caches.
SHIM_VERSION = "1.4.9"
SHIM_SERVICE_ID = "daaf-anthropic-openai-shim"

SHIM_PORT = int(os.environ.get("SHIM_PORT", "4141"))

# v1.2.5: backend lane selector. "openai" (default) drives the api.openai.com
# API-key lane unchanged; "chatgpt" drives the ChatGPT-subscription Codex backend
# with an OAuth Bearer read from $CODEX_HOME/auth.json.
# INTENT: pick the lane ONCE at startup so the hot request path just reads a
#   constant and branches auth/base-URL, never re-parses env.
# REASONING: an unknown value must not silently route to a surprising backend;
#   we degrade to the safe, original "openai" default with ONE startup WARNING
#   (parity with the verbosity resolver's invalid-value posture). The WARNING is
#   emitted after `log` exists (see the deferred warning below), because config is
#   read before logging is configured.
# ASSUMES: the two lanes are the only valid values (notes/08 — chatgpt is a lean
#   impersonation = existing translator + base-URL swap + Bearer-from-auth.json).
_BACKEND_MODE_SUPPORTED = frozenset({"openai", "chatgpt"})
_BACKEND_MODE_DEFAULT = "openai"
_raw_provider_shim = os.environ.get("DAAF_PROVIDER_SHIM")
_raw_backend_mode = os.environ.get("SHIM_BACKEND_MODE")
_legacy_backend_mode_input = (
    _BACKEND_MODE_DEFAULT if _raw_backend_mode is None else _raw_backend_mode
)
_backend_mode_norm = (_legacy_backend_mode_input or "").strip().lower()
# Keep two independent boundaries. Core v1.2.5/v1.3.7 routing intentionally defaults an
# omitted backend to OpenAI, normalizes case/whitespace, and warns+falls back on unknown
# values. The v1.3.8 shim-global policy is stricter: only the complete raw exact provider
# and backend pair may reconcile as valid, project effective, or activate on a request.
_GPT_FAST_ROUTE_VALID = bool(
    _raw_provider_shim == "openai"
    and _raw_backend_mode in _BACKEND_MODE_SUPPORTED
)
if _backend_mode_norm in _BACKEND_MODE_SUPPORTED:
    SHIM_BACKEND_MODE = _backend_mode_norm
    _backend_mode_warn = None
else:
    SHIM_BACKEND_MODE = _BACKEND_MODE_DEFAULT
    # Deferred: `log` is configured further down. Stash the message and emit it
    # once logging exists so the operator sees the misconfiguration.
    _backend_mode_warn = (
        "SHIM_BACKEND_MODE %r invalid (valid: openai|chatgpt); "
        "falling back to default %r" % (_raw_backend_mode, _BACKEND_MODE_DEFAULT)
    )

# v1.3.8: process-wide route-bound GPT tier policy. The startup reconciliation is one
# lock-serialized compare-and-set operation: a valid policy bound to the other lane, or
# a current-lane ON policy without either the complete raw exact provider/backend pair
# or exact native-Fast disable boundary, is replaced by explicit OFF. A concurrent
# current-lane `on` that wins the writer lock is observed and preserved only when both
# boundaries are exact. Every failure remains effective OFF; unsafe filesystem objects
# are never overwritten and can never crash shim startup.
_GPT_FAST_STORE = PolicyStore()
_GPT_FAST_NATIVE_DISABLED = native_fast_is_disabled()
try:
    _GPT_FAST_STARTUP_NORMALIZATION = _GPT_FAST_STORE.normalize_backend(
        SHIM_BACKEND_MODE,
        route_boundary_valid=_GPT_FAST_ROUTE_VALID,
        native_fast_disabled=_GPT_FAST_NATIVE_DISABLED,
    )
except Exception:
    _GPT_FAST_STARTUP_NORMALIZATION = None

# HARDENING: the backend base URL default is MODE-CONDITIONAL. openai ->
# api.openai.com/v1 (the original production target); chatgpt -> the Codex backend
# (notes/08). An explicit SHIM_BACKEND_BASE_URL env value overrides the mode
# default in EITHER lane. The Responses endpoint is always {base}/responses
# (assembled in _handle_messages) — the /responses suffix assembly is unchanged.
_BACKEND_BASE_URL_DEFAULTS = {
    "openai": "https://api.openai.com/v1",
    "chatgpt": "https://chatgpt.com/backend-api/codex",
}
# v1.4.7: normalize a user-pasted gateway URL. INTENT: accept the forms people copy
#   from a provider's docs. REASONING: env_file values keep stray whitespace, a
#   trailing "/" would yield "//responses", and a pasted ".../v1/responses" would
#   yield ".../responses/responses"; an empty value now means "use the default".
# ASSUMES: no OpenAI-compatible base URL legitimately ends in "/responses".
SHIM_BACKEND_BASE_URL = (
    os.environ.get("SHIM_BACKEND_BASE_URL", "").strip()
    or _BACKEND_BASE_URL_DEFAULTS[SHIM_BACKEND_MODE]
).rstrip("/")
_backend_base_url_warn = None
if SHIM_BACKEND_BASE_URL.lower().endswith("/responses"):
    SHIM_BACKEND_BASE_URL = SHIM_BACKEND_BASE_URL[: -len("/responses")].rstrip("/")
    # Deferred like _backend_mode_warn: `log` is configured further down.
    _backend_base_url_warn = (
        "SHIM_BACKEND_BASE_URL ended in /responses; stripped that suffix because "
        "the shim appends /responses itself (using backend=%s)" % SHIM_BACKEND_BASE_URL
    )
# API key is read from env and never logged. Default to OPENAI_API_KEY. Used only
# in openai mode; in chatgpt mode the OAuth access_token (from auth.json) is the
# Bearer and this value is ignored.
SHIM_BACKEND_API_KEY = os.environ.get("SHIM_BACKEND_API_KEY") or os.environ.get(
    "OPENAI_API_KEY", ""
)

# v1.2.5: chatgpt-lane token store. CODEX_HOME points at the directory holding
# auth.json (the codex OAuth token store, mode 0600). Resolved to a path here;
# validated at first use (or fail-fast) in chatgpt mode. In openai mode this is
# unused. We do NOT invent a default path in chatgpt mode — a missing CODEX_HOME
# is a hard, actionable error, not a silent fallback (notes/09 F).
CODEX_HOME = os.environ.get("CODEX_HOME", "").strip() or None
_CODEX_AUTH_PATH = os.path.join(CODEX_HOME, "auth.json") if CODEX_HOME else None
SHIM_STRIP_MODEL_PREFIX = os.environ.get("SHIM_STRIP_MODEL_PREFIX", "")
# Tool-argument sanitization (2026-07-10). Default ON. Set SHIM_SANITIZE_TOOLS=0
# to disable — REQUIRED when benchmarking shim-routed models. Read once at
# startup (verify via /health "sanitize_tools").
SHIM_SANITIZE_TOOLS = os.environ.get(
    "SHIM_SANITIZE_TOOLS", "1"
).strip().lower() not in ("0", "false", "no")
# v1.2.0/v1.2.2: reasoning effort. This env var is TIER 3 of the v1.2.2 precedence
# chain (inbound output_config.effort > "#<effort>" slug suffix > this env var >
# default "high"). Read once at startup; empty/whitespace treated as unset (falls
# through to the default). Its value is validated at RESOLVE time (below) so an
# unrecognized env value degrades to the default with a WARNING rather than being
# blindly forwarded.
SHIM_REASONING_EFFORT = os.environ.get("SHIM_REASONING_EFFORT", "").strip() or None
# v1.4.8: PDF document escape hatch. "file" (default) forwards PDFs as Responses
# input_file parts; "omit" replaces them with a short text note. Exists because
# input_file acceptance on the ChatGPT/Codex backend is not yet live-confirmed.
# Empty/unset means "file"; any other unrecognized value also means "file" and logs
# one startup WARNING (deferred like _backend_mode_warn: `log` is configured below),
# mirroring how an unrecognized SHIM_REASONING_EFFORT degrades. Read once at startup.
_PDF_MODE_RAW = os.environ.get("SHIM_PDF_MODE", "").strip().lower()
SHIM_PDF_MODE = "omit" if _PDF_MODE_RAW == "omit" else "file"
_pdf_mode_warn = None
if _PDF_MODE_RAW not in ("", "file", "omit"):
    _pdf_mode_warn = (
        "SHIM_PDF_MODE=%r is not recognized (expected file or omit); using file"
        % _PDF_MODE_RAW[:40]
    )

# v1.2.4: response verbosity. The outbound Responses payload ALWAYS carries
# text:{"verbosity": <value>}. Resolved ONCE here at startup (parallel to
# SHIM_REASONING_EFFORT's startup read), not per-request — verbosity is a
# whole-session posture, not a per-turn signal, and Claude Code sends no inbound
# verbosity field.
# INTENT: pick a backend-acceptable verbosity string now, so the hot request path
#   just reads the resolved constant.
# REASONING: the accepted set is low|medium|high. A value in the set (case-
#   insensitive, whitespace-trimmed) maps through identity; anything else — a
#   typo, an empty string, whitespace only — logs ONE startup WARNING and degrades
#   to the default rather than being blindly forwarded (a rejected verbosity would
#   400 every request). Resolving at startup means the WARNING fires exactly once,
#   not on every request.
# ASSUMES: high and low are LIVE-CONFIRMED accepted by gpt-5.6-sol on /v1/responses
#   (both HTTP 200, probe live_tests/18, 2026-07-12). "medium" is the DOCUMENTED
#   middle value and is treated as accepted here on that basis — it was NOT
#   independently live-probed (the 18-probe exercised only default/high/low). If a
#   backend later rejects "medium", drop it from _VERBOSITY_SUPPORTED. The default
#   "medium" balances decision-focused responses with DAAF's evidence requirements.
_VERBOSITY_SUPPORTED = frozenset({"low", "medium", "high"})
_VERBOSITY_DEFAULT = "medium"


def _resolve_startup_verbosity():
    # INTENT: resolve the process-wide verbosity from SHIM_TEXT_VERBOSITY once.
    # REASONING: mirror the effort-normalizer's shape (identity for a supported
    #   value; WARNING + default for anything else) but as a startup-only, no-tier
    #   resolution since verbosity has a single source.
    # WARNING semantics: distinguish "var not set at all" (the common, deliberate
    #   unset -> silent default "medium") from "var IS set but to an invalid value,
    #   including an empty/whitespace-only string" (a misconfiguration the operator
    #   should see -> ONE WARNING, then default). A present-but-blank value is a
    #   config mistake, not an intentional unset, so it warns.
    raw = os.environ.get("SHIM_TEXT_VERBOSITY")
    if raw is None:
        return _VERBOSITY_DEFAULT  # unset entirely — silent default.
    norm = raw.strip().lower() if isinstance(raw, str) else ""
    if norm in _VERBOSITY_SUPPORTED:
        return norm
    log.warning("SHIM_TEXT_VERBOSITY %r invalid (valid: low|medium|high); "
                "falling back to default %r", raw, _VERBOSITY_DEFAULT)
    return _VERBOSITY_DEFAULT


# v1.2.2: reasoning-effort resolution machinery.
# INTENT: the outbound Responses payload now ALWAYS carries reasoning.effort. The
#   resolver picks the value + its source by the four-tier precedence chain and
#   returns both (the source is logged in the per-request line for observability).
# REASONING: the accepted set is the gpt-5.6 family's documented effort enum
#   (notes file 04 §5: none|low|medium|high|xhigh|max). A value in this set maps
#   through IDENTITY. gpt-6-astra shares low|medium|high|xhigh|max but REJECTS
#   "none" (primary source 2026-09-05); that one model-specific difference is not
#   encoded in this generic value-set — it is handled by the Astra floor applied at
#   request build (see _NO_NONE_EFFORT_SLUGS; v1.4.9 adds gpt-6.1-sol). A value NOT
#   in the set is "unknown"
#   for the tier that carried
#   it: we log ONE warning and IGNORE that tier (fall through) — never forward a
#   value OpenAI would reject. The one deliberate exception is a known-but-LOW-
#   confidence-for-gpt-5.6 alias ("minimal"), which we CLAMP to the nearest
#   supported value ("low") rather than dropping, because it is a real effort
#   level on the gpt-5/gpt-5-mini family and a caller sending it clearly wants
#   minimal reasoning. Everything genuinely unknown (typos, future levels we have
#   not validated) falls through.
# ASSUMES: the accepted set matches the live backend for gpt-5.6 (notes file 04
#   §1/§5, HIGH confidence for none/low/medium/high; MEDIUM for xhigh/max — both
#   community-confirmed). If OpenAI later rejects xhigh/max, the fix is to remove
#   them from _EFFORT_SUPPORTED and add a clamp entry; the resolver logic is
#   unchanged. The default "high" (not "medium") is a user-locked posture choice
#   for parity with DAAF Claude sessions.
_EFFORT_SUPPORTED = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
_EFFORT_DEFAULT = "high"
# Minimum-reasoning value for an explicit thinking:{"type":"disabled"} inbound.
# "none" is a valid /v1/responses effort for gpt-5.6 (notes file 04 §1/§5, MEDIUM
# confidence — community-confirmed, not quoted from the official effort enum; it
# also empirically re-enables temperature, which the shim never sends regardless).
# ASSUMES: a real client actually sends thinking:{"type":"disabled"} AND the
#   backend accepts effort:"none" for gpt-5.6. NOT live-verified in the v1.2.2
#   validation battery (the 10_diag-effort-live.py run exercised default/slug/
#   inbound-low lanes only; no observed client sends disabled thinking today). If
#   OpenAI rejects "none", swap this to the lowest live-accepted value ("low").
_EFFORT_DISABLED = "none"
# Known-but-clamp map: a value we recognize as a real effort level on a sibling
# model family but which is not in the gpt-5.6 accepted set -> nearest supported.
# ASSUMES: "minimal" is LOW-confidence for gpt-5.6 specifically (notes file 04
#   §5) — clamp to "low" rather than forward-and-risk-a-400.
_EFFORT_CLAMP = {"minimal": "low"}
# GPT-6 Astra onboarding (2026-09-05): the Astra family's reasoning.effort enum is
# {low, medium, high, xhigh, max} — it does NOT accept "none" (OpenAI Astra model
# page, developers.openai.com/api/docs/models/gpt-6-astra, primary-source). The
# general resolver above still treats "none" as valid because it IS valid for the
# gpt-5.6 family; the Astra-specific floor is applied model-conditionally at the
# single interception point in _anthropic_to_responses_request (below), so every
# non-Astra model keeps current behavior exactly. Membership is matched on the
# terminal slug (provider prefix + "#<effort>" suffix already stripped by the
# caller); the "[1m]" window-hint form is included defensively even though it is
# consumed client-side and normally never reaches the shim.
# v1.4.9: renamed from _ASTRA_FAMILY_SLUGS because it is no longer Astra-only.
# GPT-6.1 Sol also rejects "none" (live 2026-10-13: "gpt-6.1-sol#none[1m]" ->
# backend 400 invalid_request_error / unsupported_value). The gpt-6.1-sol-pro forms
# are included by family inference (not live-observed). gpt-6-sol is deliberately
# NOT a member: there is no evidence either way, so it keeps prior behavior.
_NO_NONE_EFFORT_SLUGS = frozenset({
    "gpt-6-astra", "gpt-6-astra[1m]",
    "gpt-6.1-sol", "gpt-6.1-sol[1m]",
    "gpt-6.1-sol-pro", "gpt-6.1-sol-pro[1m]",
})

# HARDENING: retry policy. Retry only on transient backend failures, and only
# before any bytes have been emitted to the client (a partially-streamed
# response cannot be safely restarted).
RETRY_STATUSES = {429, 500, 502, 503, 529}
MAX_RETRIES = 3
BACKOFF_BASE = 0.5   # seconds; doubles each attempt
BACKOFF_CAP = 8.0    # seconds; ceiling before jitter
RETRY_AFTER_CAP = 30.0  # seconds; never honor an absurd Retry-After
# v1.2.14 (R4): rate-limit-class retries may honor a longer advertised/parsed delay
# than other classes (a genuine per-minute rate window can exceed 30s), but a delay
# beyond THIS cap is failed fast to the client rather than slept internally, so the
# client owns any multi-minute wait instead of a silent shim stall. Non-rate-limit
# classes keep RETRY_AFTER_CAP.
RATE_LIMIT_RETRY_AFTER_CAP = 60.0  # seconds
# v1.2.14 (R4): Codex-style rate-limit delay hint embedded in the backend message
# text. Parsed for the NUMBER only (gated on code rate_limit_exceeded); the prose is
# never logged or reflected. "s"/"seconds" -> seconds, "ms" -> milliseconds.
_RATE_LIMIT_DELAY_RE = re.compile(
    r"try again in (\d+(?:\.\d+)?)\s*(s|ms|seconds?)", re.IGNORECASE)

# Backend-error diagnostics distinguish status plus exact structured type/code
# (for example insufficient_quota versus rate_limit_exceeded) and retain only
# allowlisted retry/rate-limit headers. Free-form response prose is never logged.
ERR_BODY_MAXLEN = 500  # chars; bound locally generated diagnostic text
# v1.2.7: cap one decoded Responses SSE data event before JSON parsing. A complete
# terminal Responses object can legitimately contain a 64K-token answer plus tool
# payloads, so 16 MiB is deliberately generous while still preventing an unbounded
# upstream line from exhausting shim memory. The raw SSE transcript is never stored.
MAX_RESPONSES_SSE_EVENT_BYTES = 16 * 1024 * 1024
# v1.2.14 (F3): cap the ≥400 error body handed to the retry classifier at 1 MiB. A
# legitimate backend error envelope is tiny; a pathological/oversized body must not
# drive an unbounded json.loads/scan in _plan_retry. Beyond-cap bodies are truncated
# and parse-fail on the truncated bytes, falling back to HTTP-status classification.
MAX_ERROR_BODY_BYTES = 1024 * 1024

# v1.2.14 (R6): downstream heartbeat interval in seconds. After message_start is on
# the wire, the streaming path emits Anthropic `ping` SSE events every
# SHIM_PING_INTERVAL_S while the upstream is silent, so an intermediary/client keeps
# the connection warm and a dead client is detected within one interval instead of
# only at the next upstream event. Float-tolerant: an unparseable value falls back to
# the 15s default; a value <= 0 disables the heartbeat entirely (no watchdog task is
# started). Streaming responses only — non-streaming paths never start a watchdog.
try:
    SHIM_PING_INTERVAL_S = float(os.environ.get("SHIM_PING_INTERVAL_S", "15"))
except (ValueError, TypeError):
    SHIM_PING_INTERVAL_S = 15.0

# v1.2.11 request-local lifecycle accounting. The mutable record is intentionally
# stored as one ContextVar value: child tasks inherit the same record, while
# concurrent requests receive distinct records established at the ASGI boundary.
_SEND_STATES = frozenset({
    "not_attempted", "attempted", "send_completed", "skipped_disconnect",
    "write_failed",
})
_UPSTREAM_REQUEST_ID_HEADERS = (
    "x-request-id", "request-id", "x-openai-request-id", "openai-request-id",
)
_UPSTREAM_REQUEST_ID_MAXLEN = 200
_CLIENT_ERROR_MESSAGE_MAXLEN = 200
_MACHINE_FIELD_VALUE_MAXLEN = 1000
_WIRE_DIVERGENCE_SUMMARY_INTERVAL = 100
_WIRE_DIVERGENCE_COUNTS = {}
_WIRE_DIVERGENCE_LAST_EMITTED = {}
_WIRE_DIVERGENCE_LOCK = threading.Lock()

# v1.2.14 (R1): forward-compatible observability for wire shapes the shim does not
# model. Bounded process-level aggregation keyed by (kind, name) with kind in
# {event_type, item_type, envelope}. The cap bounds distinct keys; once reached,
# further novel keys collapse into (kind, "__overflow__") so a hostile or highly
# variable backend cannot grow the map without limit. Lock-guarded independently
# of the wire-divergence lock it forwards into.
_UNKNOWN_WIRE_COUNTS = {}
_UNKNOWN_WIRE_CAP = 256
_UNKNOWN_WIRE_LOCK = threading.Lock()

# Event types the shim either explicitly handles or benignly ignores. A clean
# stream contains ONLY these, so the reducer/accumulator catch-alls can count any
# event type outside this set as genuinely unknown wire (R1) while keeping
# unknown_events at 0 for well-behaved backends. Kept in sync with the streaming
# reducer in _handle_messages and _accumulate_terminal_response: the first group
# is actively translated; the second is known status/lifecycle scaffolding the
# reducer skips (they still reach the catch-all today and must not be miscounted).
# v1.3.4 (V4-R5) added `keepalive` and `response.metadata` to the second group.
_KNOWN_EVENT_TYPES = frozenset({
    # Actively handled by the reducer.
    "response.reasoning_summary_text.delta",
    "response.output_text.delta",
    "response.output_item.added",
    "response.output_item.done",
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
    "response.completed",
    "response.incomplete",
    "response.failed",
    "error",
    # Known status/lifecycle events the reducer legitimately ignores.
    "response.created",
    "response.in_progress",
    "response.queued",
    "response.content_part.added",
    "response.content_part.done",
    "response.output_text.done",
    "response.reasoning_summary_text.done",
    "response.reasoning_summary_part.added",
    "response.reasoning_summary_part.done",
    "response.reasoning_text.delta",
    "response.reasoning_text.done",
    # v1.3.4 (V4-R5): two benign scaffolding types observed live during v1.2.14
    # validation and throttle-logged as "unknown wire" ever since — a top-level
    # keepalive (namespaced like `error`, matched by raw set membership at the two
    # catch-alls) and a response.metadata lifecycle frame. Both carry nothing the
    # translation needs, so absorbing them into the ignored group makes them silently
    # skipped rather than counted, restoring "unknown_events=0 when clean" on the
    # backends that emit them. Deliberately NOT added to _MALFORMED_TOLERANT_EVENT_TYPES:
    # tolerance is for malformed FRAMES of load-free events, and there is no evidence
    # either type appears malformed — a malformed instance should still fail strictly.
    "keepalive",
    "response.metadata",
})
# output_item.added/done item types the reducer models. Any other item type is
# counted as unknown_items (R1) — observability only; it is still not translated.
_KNOWN_ITEM_TYPES = frozenset({"function_call", "message", "reasoning"})

# v1.2.14 (R3.5): non-load-bearing event types whose FRAME may be tolerated when it
# fails strict JSON parse. These are pure status/lifecycle scaffolding the reducer
# already ignores when well-formed, so a malformed instance carries nothing the
# translation needs — it is counted (R1) and skipped rather than failing the stream.
# A load-bearing event type (deltas, tool-argument events, terminal frames, error)
# is deliberately absent, so a malformed instance of one still fails strictly. This
# is a subset of the ignored group in _KNOWN_EVENT_TYPES and must stay consistent
# with it. Tolerance is malformed-JSON only; an oversized payload is capped inside
# the bounded SSE reader before the type is knowable and is deferred (see changelog).
_MALFORMED_TOLERANT_EVENT_TYPES = frozenset({
    "response.created",
    "response.in_progress",
    "response.queued",
    "response.content_part.added",
    "response.content_part.done",
    "response.reasoning_summary_part.added",
    "response.reasoning_summary_part.done",
})
# Extract a clean, bounded, unescaped `"type":"..."` token from the RAW bytes of an
# SSE frame that failed strict JSON parse. Only an ASCII type of 1-64 chars with no
# quote/backslash qualifies; anything else yields None (strict failure preserved).
_MALFORMED_TYPE_PROBE = re.compile(rb'"type"\s*:\s*"([^"\\]{1,64})"')

# v1.3.9 Fast-mode constants. Header names are case-insensitive, while Anthropic beta
# tokens are case-sensitive. Both exact GPT routes emit the one canonical Responses request
# value `priority`. Served tier is read only from a terminal Responses object; exact served
# `fast` is retained temporarily as a compatibility-only parser value and is never emitted.
_FAST_BETA_TOKEN = "fast-mode-2026-02-01"
_FAST_REQUEST_SERVICE_TIERS = {"openai": "priority", "chatgpt": "priority"}
_FAST_ACTUAL_SERVICE_TIERS = frozenset({"priority", "fast"})
_STANDARD_ACTUAL_SERVICE_TIERS = frozenset({"default", "flex", "scale", "auto"})
_FAST_REQUEST_SOURCES = frozenset({"none", "anthropic", "shim_global", "both"})
_LATEST_TERMINAL_LOCK = threading.Lock()
_LATEST_TERMINAL = None
_LATEST_TERMINAL_SEQUENCE = 0
_LATEST_TERMINAL_ORDER = 0
_HEALTH_MODEL_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


class _JSONObjectPairs(list):
    """Temporary marker preserving object-pair order through JSON decoding."""


class _DuplicateTopLevelSpeedError(ValueError):
    """The privileged exact top-level `speed` key appeared more than once."""


def _preserve_json_object_pairs(pairs):
    return _JSONObjectPairs(pairs)


def _collapse_inbound_json(value, *, root=False):
    # Narrow duplicate-key protection for the privileged top-level Fast marker.
    # Every unrelated duplicate and every nested duplicate retains json.loads()'s
    # established last-key-wins behavior after recursive collapse.
    if isinstance(value, _JSONObjectPairs):
        collapsed = {}
        speed_seen = False
        for key, child in value:
            if root and key == "speed":
                if speed_seen:
                    raise _DuplicateTopLevelSpeedError()
                speed_seen = True
            collapsed[key] = _collapse_inbound_json(child)
        return collapsed
    if isinstance(value, list):
        return [_collapse_inbound_json(child) for child in value]
    return value


def _conversation_session_id(preserved, scope_headers=()):
    # Claude Code 2.1.261 m9() JSON-encodes device_id/account_uuid/session_id in
    # metadata.user_id. Generic API user IDs are not session IDs; only the
    # verified worker header below refines the session routing namespace.
    # INTENT: forward only the session UUID; never retain account/device metadata.
    # REASONING: inspect preserved pairs so ambiguous duplicate keys omit the hint
    # without changing existing request decoding or rejecting otherwise valid calls.
    # ASSUMES: this untrusted routing hint grants no authority or cache isolation.
    if not isinstance(preserved, _JSONObjectPairs):
        return None
    metadata = [value for key, value in preserved if key == "metadata"]
    if len(metadata) != 1 or not isinstance(metadata[0], _JSONObjectPairs):
        return None
    user_ids = [value for key, value in metadata[0] if key == "user_id"]
    if len(user_ids) != 1 or not isinstance(user_ids[0], str):
        return None
    # Defensive parser bound, not a claimed Anthropic schema limit.
    if len(user_ids[0]) > 4096:
        return None
    try:
        pairs = json.loads(user_ids[0], object_pairs_hook=_preserve_json_object_pairs)
    except (ValueError, RecursionError):
        return None
    if not isinstance(pairs, _JSONObjectPairs):
        return None
    fields = dict(pairs)
    if len(fields) != len(pairs):
        return None
    if not all(isinstance(fields.get(key), str)
               for key in ("device_id", "account_uuid", "session_id")):
        return None
    session_id = fields["session_id"]
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", session_id) is None:
        return None
    session_id = session_id.lower()
    worker_ids = []
    parent_header_present = False
    for name, value in scope_headers or ():
        if name.lower() == b"x-claude-code-parent-agent-id":
            parent_header_present = True
        if name.lower() == b"x-claude-code-agent-id":
            worker_ids.append(value)
    if not worker_ids:
        # Main contexts omit both worker headers. A parent-only header indicates
        # incomplete worker identity: do not collapse it into the parent's route.
        return None if parent_header_present else session_id
    if len(worker_ids) != 1 or len(worker_ids[0]) > 81:
        return None
    try:
        worker_id = worker_ids[0].decode("ascii")
    except (AttributeError, UnicodeDecodeError):
        return None
    # Exact installed Claude Code DS()/bh() generated-worker grammar; other forms
    # (including unverified teammate/custom IDs) omit the hint, never use parent.
    if re.fullmatch(r"a(?:[A-Za-z0-9_-]{1,63}-)?[0-9a-f]{16}", worker_id) is None:
        return None
    # Stable, domain-separated worker UUID; no device/account data or raw worker
    # ID goes upstream. This is our routing derivation, not a native client schema.
    return str(uuid.uuid5(uuid.UUID(session_id), "daaf-claude-worker-v1:" + worker_id))


def _decode_anthropic_request_json(body, scope_headers=()):
    preserved = json.loads(
        body.decode("utf-8"), object_pairs_hook=_preserve_json_object_pairs
    )
    request = _collapse_inbound_json(preserved, root=True)
    state = _request_state()
    if state is not None and SHIM_BACKEND_MODE == "chatgpt":
        state.conversation_session_id = _conversation_session_id(preserved, scope_headers)
    return request


def _anthropic_beta_tokens(scope_headers):
    # Preserve duplicate-field semantics by scanning every ASGI header pair, then split
    # every value on commas. Malformed non-ASCII values cannot equal the ASCII beta token.
    tokens = set()
    for raw_name, raw_value in scope_headers or ():
        try:
            name = raw_name.decode("ascii").lower()
            value = raw_value.decode("ascii")
        except (AttributeError, UnicodeDecodeError):
            continue
        if name == "anthropic-beta":
            # HTTP list optional whitespace is SP / HTAB only. A broader str.strip()
            # would erase controls such as VT / FF and could turn a tainted member into
            # the privileged exact beta token.
            tokens.update(
                part.strip(" \t") for part in value.split(",") if part.strip(" \t")
            )
    return tokens


def _requested_service_tier(body, beta_tokens, policy_snapshot):
    # v1.3.8 additive precedence. Inbound Anthropic Fast is validated exactly as in
    # v1.3.7 even when global mode is ON; global policy never makes malformed input valid.
    inbound_fast = False
    if "speed" in body:
        speed = body.get("speed")
        if not isinstance(speed, str) or speed != "fast":
            raise _InvalidRequestError("unsupported speed value")
        if _FAST_BETA_TOKEN not in beta_tokens:
            raise _InvalidRequestError(
                "speed 'fast' requires anthropic beta fast-mode-2026-02-01")
        inbound_fast = True
    # The persisted opt-in is necessary but never sufficient: every accepted request
    # also requires the complete raw exact provider/backend pair and exact native-Fast
    # disable boundary captured for this process at startup. This keeps configuration
    # immutable for the daemon lifetime while failing closed on every malformed control.
    global_fast = bool(
        _GPT_FAST_ROUTE_VALID
        and _GPT_FAST_NATIVE_DISABLED
        and policy_snapshot is not None
        and policy_snapshot.status == "ok"
        and policy_snapshot.backend_mode == SHIM_BACKEND_MODE
        and policy_snapshot.effective
    )
    if inbound_fast and global_fast:
        source = "both"
    elif inbound_fast:
        source = "anthropic"
    elif global_fast:
        source = "shim_global"
    else:
        source = "none"
    # OFF means omission, never service_tier:"default" and never suppression of a valid
    # inbound request. Both active sources converge on the lane's one canonical value.
    requested_tier = (
        _FAST_REQUEST_SERVICE_TIERS[SHIM_BACKEND_MODE]
        if inbound_fast or global_fast else None
    )
    return requested_tier, source


def _probe_malformed_event_type(data_bytes):
    # v1.2.14 (R3.5): best-effort event-type recovery from a malformed SSE frame.
    # INTENT: decide whether a frame that failed json.loads is a tolerable
    #   non-load-bearing status event. Probes only the first 4 KiB so a large junk
    #   frame cannot drive an unbounded scan. Returns the type string or None.
    # REASONING: a regex over the raw bytes never executes the malformed JSON and
    #   cannot be tricked into recovering a load-bearing type via escapes (the token
    #   class excludes quote and backslash). The caller checks membership in
    #   _MALFORMED_TOLERANT_EVENT_TYPES; a non-match falls through to strict failure.
    match = _MALFORMED_TYPE_PROBE.search(data_bytes[:4096])
    if not match:
        return None
    try:
        return match.group(1).decode("ascii")
    except (UnicodeDecodeError, AttributeError):
        return None


class _RequestLifecycleState:
    def __init__(self):
        self.req_id = uuid.uuid4().hex
        self.started_at = time.monotonic()
        self.phase = "request_read"
        self.model = "-"
        self.stream = None
        self.message_count = 0
        self.tool_count = 0
        self.stop_reason = "-"
        self.input_tokens = None
        self.output_tokens = None
        # v1.3.6 (V6-R1): cached-prefix count (OpenAI usage.input_tokens_details.
        # cached_tokens), None until a backend terminal usage is parsed. Emitted on the
        # terminal record (as "-" when None) and feeds the /health prompt_cache counters.
        # Lane-agnostic, like the token fields above.
        self.cached_tokens = None
        self.usage_source = "-"
        # v1.3.7: requested intent and actual served tier remain distinct. "-" means
        # absent/unknown and must never be interpreted as Standard.
        self.requested_service_tier = "-"
        self.requested_service_tier_source = "none"
        # Captured exactly once by app() immediately after this lifecycle object is
        # created and before body reading/authentication. Retries never consult global state.
        self.gpt_policy_snapshot = None
        self.served_service_tier = "-"
        self.tools_called = 0
        self.effort_value = "-"
        self.effort_source = "-"
        self.reasoning_cache_misses = 0
        # v1.3.4 (V4-R6): per-request cache-hit count (parallel to the miss count above),
        # emitted on the terminal record. reasoning_cache_stripped is the count of restored
        # reasoning items stripped by the stale-blob 400 insurance this request (0 unless a
        # strip-retry fired — see _maybe_strip_restored_reasoning). Both always-present ints
        # so the terminal record parses stably regardless of whether a strip occurred.
        self.reasoning_cache_hits = 0
        self.reasoning_cache_stripped = 0
        # v1.3.4 (V4-R1): per-request working state for the stale-blob 400 insurance.
        # injected_restored_reasoning_ids holds the reasoning-item ids (rs_...) of restored
        # blobs actually injected into this request's outbound payload (what R3 strips, by
        # id, from the reused payload["input"]); injected_restored_call_ids holds the
        # matching call_ids (what R4 evicts as proven-stale). stale_strip_used is the
        # one-shot gate — a request may strip-and-retry exactly once. None of these are
        # emitted on the terminal record (internal working state only).
        self.injected_restored_reasoning_ids = set()
        self.injected_restored_call_ids = set()
        self.stale_strip_used = False
        # v1.2.14 (R1/D2): per-request counts of unknown SSE event types and
        # unmodeled output_item types, surfaced on the terminal record (0 when clean).
        self.unknown_events = 0
        self.unknown_items = 0
        # v1.2.14 (R6/D2): maximum upstream inter-event idle gap in whole
        # milliseconds (monotonic clock), surfaced on the terminal record for stall
        # triage. last_upstream_event_at holds the monotonic timestamp of the previous
        # upstream event yield; the first event has no predecessor and therefore
        # contributes no gap (it only seeds the timer).
        self.max_idle_gap_ms = 0
        self.last_upstream_event_at = None
        # v1.2.14 (R6): the downstream heartbeat watchdog task for a streaming
        # response (None until message_start is emitted; torn down before the terminal
        # frames and reaped by the request-level resource finalizer as a safety net).
        self.heartbeat_task = None
        # v1.2.14 (D5): sorted top-level request key names (+ text/reasoning sub-key
        # names) captured once after translation, emitted once if the backend
        # classifies the request as invalid_request_error. Names only, never values.
        self.request_shape = None
        self.invalid_request_shape_logged = False
        self.attempts = 0
        self.retries = 0
        self.last_retry_reason = "-"
        self.last_retry_source = "-"
        # v1.2.14 (R4/D2): source of the delay used for the most recent retry sleep
        # (parsed = backend message "try again in" text; header = Retry-After; backoff
        # = local exponential backoff). Stays "-" when no retry slept; on a fail-fast
        # beyond the rate-limit cap it records the advertised source that triggered it.
        self.retry_delay_source = "-"
        self.client_request_id = self.req_id
        # Private routing state only: never included in lifecycle logs or health.
        self.conversation_session_id = None
        self.transport_exception = "-"
        self.upstream_request_id = "-"
        self.upstream_request_id_header = "-"
        self.upstream_http_version = "unknown"
        self.upstream_first_event_at = None
        self.downstream_first_content_at = None
        self.failure_phase = "-"
        self.backend_type = "-"
        self.backend_code = "-"
        self.anthropic_error_type = "-"
        self.backend_error_logged = False
        self.outcome = None
        self.disconnect_observed = False
        self.disconnect_phase = "-"
        self.disconnect_logged = False
        self.terminal_frame_send = "not_attempted"
        self.body_close_send = "not_attempted"
        self.terminal_logged = False
        self.cleanup_status = "not_started"
        self.cleanup_error = "-"
        self.cleanup_failures = 0
        self.owned_stream_contexts = []
        self.disconnect_watcher = None
        self.cleanup_logged = False


_REQUEST_STATE = ContextVar("shim_request_state", default=None)
_DIAGNOSTICS = None
_DIAGNOSTICS_STARTUP_ERROR = (
    "SHIM_DEV_DIAGNOSTICS_MODULE could not initialize private developer diagnostics; "
    "set it to an absolute readable module file with a working Recorder, "
    "or unset it to disable diagnostics."
)


def _trace_event(event, content=None, **fields):
    # Observational only: recorder failure cannot alter a model response.
    if _DIAGNOSTICS is None:
        return
    try:
        state = _request_state()
        if state is not None:
            _DIAGNOSTICS.record(state.req_id, event, content, **fields)
    except Exception:
        pass


def _start_diagnostics():
    global _DIAGNOSTICS
    # Optional absolute path to a private developer tool; normal installs leave unset.
    module_path = os.environ.get("SHIM_DEV_DIAGNOSTICS_MODULE", "")
    if not module_path:
        return
    try:
        import hashlib
        import importlib.util
        if not os.path.isabs(module_path) or not os.path.isfile(module_path):
            raise ValueError()
        spec = importlib.util.spec_from_file_location("_shim_dev_diagnostics", module_path)
        if spec is None or spec.loader is None:
            raise ValueError()
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = os.path.abspath(__file__)
        with open(source, "rb") as handle:
            source_hash = hashlib.sha256(handle.read()).hexdigest()
        _DIAGNOSTICS = module.Recorder(
            os.path.join(os.path.dirname(source), "logs", "diagnostics"),
            source_hash, SHIM_VERSION)
    except (Exception, SystemExit):
        raise RuntimeError(_DIAGNOSTICS_STARTUP_ERROR) from None



def _request_state():
    return _REQUEST_STATE.get()


def _elapsed_ms(state=None):
    state = state or _request_state()
    if state is None:
        return 0
    return max(0, int((time.monotonic() - state.started_at) * 1000))


def _set_phase(phase):
    state = _request_state()
    if state is not None:
        state.phase = phase


def _machine_field_value(value):
    # INTENT: serialize one lifecycle value as exactly one whitespace-delimited
    #   key=value token, regardless of whether the source is backend-controlled.
    # REASONING: UTF-8 URL percent encoding is deterministic and reversible with
    #   urllib.parse.unquote for valid Unicode. The explicit backslashreplace policy
    #   keeps serialization total for lone surrogate code units accepted from JSON,
    #   preserving them as printable forensic \\uXXXX escapes. The deliberately narrow
    #   safe alphabet preserves plain identifiers, integers, booleans, HTTP versions,
    #   and effort source pairs while encoding every grammar delimiter: whitespace,
    #   "=", "%", quotes, controls, backslash, and non-ASCII bytes. Sensitive text is
    #   sanitized first so encoding can never obscure credential material rather than
    #   removing it.
    # ASSUMES: lifecycle keys and event names are source constants. Only values pass
    #   here; callers must not construct untrusted field names.
    sanitized = _sanitize_sensitive_text(
        str(value), max_len=_MACHINE_FIELD_VALUE_MAXLEN
    )
    return urllib.parse.quote(
        sanitized,
        safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~/:",
        errors="backslashreplace",
    )


def _lifecycle_event(name, _fields_before_elapsed=False, **fields):
    state = _request_state()
    if state is None:
        return
    _trace_event(name, **fields)
    parts = ["event=%s" % name]
    if not _fields_before_elapsed:
        parts.append("elapsed_ms=%d" % _elapsed_ms(state))
    for key, value in fields.items():
        parts.append("%s=%s" % (key, _machine_field_value(value)))
    if _fields_before_elapsed:
        # Compatibility for a pre-lifecycle diagnostic whose exact event/field prefix is
        # consumed by focused regressions. It still uses this one bounded serializer and
        # retains elapsed timing; only the token order is preserved.
        parts.append("elapsed_ms=%d" % _elapsed_ms(state))
    log.info(" ".join(parts))


def _scrub_metadata(value, max_len=_UPSTREAM_REQUEST_ID_MAXLEN):
    if not isinstance(value, str):
        return "-"
    safe = _sanitize_sensitive_text(value, max_len=max_len)
    return safe or "-"


def _normalize_http_version(value):
    normalized = str(value or "").upper()
    return normalized if normalized in {"HTTP/1.0", "HTTP/1.1", "HTTP/2"} else "unknown"


# v1.3.1: quota-state cache for the statusline Plan-usage segment. The file lives in
# the shim's own logs/ directory — the SAME directory start_shim.sh writes shim.log to
# (SCRIPT_DIR/logs); it is derived here from __file__ because the shim itself logs only
# to stderr and holds no log-directory constant of its own. Under the shared-/daaf
# multi-install assumption this file is INSTALL-SHARED across containers on the mount:
# any install's context-bar.sh reads it to render "Plan usage:" (auth under $HOME stays
# per-install). The shim records only captured_at (write-time epoch); the reader does the
# clock math (absolute reset = captured_at + primary_reset_s).
# v1.3.2: DAAF_QUOTA_STATE_FILE, when set and non-empty, redirects the write to that exact
# path (the state dir becomes its dirname, so the mkstemp temp sibling lands there too).
# This is the SAME env var the reader (context-bar.sh) already honors, so one variable
# coherently redirects BOTH ends — a hermetic-test / redirect seam mirroring the reader's,
# NOT an off-switch: the write itself stays unconditional and fail-open (a bad seam value
# that makes the write fail is swallowed like any other failure). When unset/empty the
# __file__-derived default below is byte-identical to prior behavior.
_QUOTA_STATE_FILE_ENV = os.environ.get("DAAF_QUOTA_STATE_FILE", "")
if _QUOTA_STATE_FILE_ENV:
    _QUOTA_STATE_PATH = _QUOTA_STATE_FILE_ENV
    _QUOTA_STATE_DIR = os.path.dirname(_QUOTA_STATE_PATH)
else:
    _QUOTA_STATE_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs"
    )
    _QUOTA_STATE_PATH = os.path.join(_QUOTA_STATE_DIR, "quota_state.json")


def _write_quota_state(snapshot):
    # Absolutely fail-open telemetry: a quota-state write must NEVER affect, delay, or
    # raise on the response path. Every failure mode (unwritable dir, replace error,
    # serialization surprise) is swallowed, leaving at most one debug line and no stale
    # temp sibling. The DAAF_QUOTA_STATE_FILE seam (above) only redirects WHERE the write
    # lands (mirroring the reader's seam); it is NOT an off-switch — the write stays
    # unconditional, and a bad seam value is swallowed here like any other failure.
    tmp_path = None
    try:
        payload = {"captured_at": int(time.time())}
        # snapshot carries the 11 raw header-string values (or "-" when the header was
        # absent), exactly as emitted on the quota_snapshot line.
        payload.update(snapshot)
        data = json.dumps(payload).encode("utf-8")
        # Atomic publish via a uniquely-named sibling temp file + os.replace(): a reader
        # sees either the old file or the fully-written new one, never a partial write.
        # mkstemp creates the temp with mode 0600 already (matching the shim.log
        # permission discipline) and a unique name, so concurrent installs sharing this
        # directory cannot clobber each other's in-flight temp file.
        fd, tmp_path = tempfile.mkstemp(
            prefix="quota_state.", suffix=".tmp", dir=_QUOTA_STATE_DIR
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_path, _QUOTA_STATE_PATH)
        tmp_path = None
    except Exception:
        try:
            log.debug("quota_state write skipped (fail-open)")
        except Exception:
            pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _record_upstream_headers(response):
    state = _request_state()
    if state is None or response is None:
        return
    state.phase = "upstream_headers"
    state.upstream_http_version = _normalize_http_version(response.http_version)
    for name in _UPSTREAM_REQUEST_ID_HEADERS:
        value = response.headers.get(name)
        if value is not None:
            state.upstream_request_id_header = name
            state.upstream_request_id = _scrub_metadata(value)
            break
    _trace_event("upstream_headers_detail", status=response.status_code,
                 http_version=state.upstream_http_version,
                 upstream_request_id=state.upstream_request_id)
    if response.is_closed:
        try:
            _trace_event("upstream_json", response.content)
        except Exception:
            pass
    _lifecycle_event(
        "upstream_headers", status=response.status_code,
        http_version=state.upstream_http_version,
        upstream_req_id_header=state.upstream_request_id_header,
        upstream_req_id=state.upstream_request_id,
    )
    # v1.2.14 (D1): on the chatgpt lane a 2xx carries the full x-codex-* subscription
    # quota surface. Emit ONE compact, grep-stable quota_snapshot line of numeric/enum
    # fields for subscription-window triage. The openai lane (no x-codex-*) and every
    # non-2xx response are unchanged — no line is emitted.
    if SHIM_BACKEND_MODE == "chatgpt" and 200 <= response.status_code < 300:
        snapshot = {}
        for field, header_name in _QUOTA_SNAPSHOT_HEADER_FIELDS:
            value = response.headers.get(header_name)
            snapshot[field] = value if value is not None else "-"
        _lifecycle_event("quota_snapshot", **snapshot)
        # v1.3.1: also cache the snapshot to an install-shared JSON state file so the
        # statusline (context-bar.sh) can render a "Plan usage:" segment on shim-lane
        # sessions. Fail-open; never affects the response path.
        _write_quota_state(snapshot)


def _record_upstream_first_event():
    state = _request_state()
    if state is None or state.upstream_first_event_at is not None:
        return
    state.phase = "upstream_stream"
    state.upstream_first_event_at = time.monotonic()
    _lifecycle_event("upstream_first_event")


def _record_upstream_event_gap():
    # v1.2.14 (R6): timestamp each dispatched upstream SSE event and track the maximum
    # inter-event idle gap (monotonic clock) for stall triage on the terminal record.
    # INTENT: give the terminal record a single max_idle_gap_ms number that summarizes
    #   the longest silent stretch between upstream events, without storing a
    #   transcript or per-event timing.
    # REASONING: the first event has no predecessor, so it only seeds the timer; every
    #   later event updates the running maximum with the elapsed span since the prior
    #   event when it is larger. Purely additive telemetry — it never alters the
    #   control flow of the bounded SSE reader that calls it at each yield point.
    # ASSUMES: called once per yielded upstream event, on the same request context.
    state = _request_state()
    if state is None:
        return
    now = time.monotonic()
    if state.last_upstream_event_at is not None:
        gap_ms = int((now - state.last_upstream_event_at) * 1000)
        if gap_ms > state.max_idle_gap_ms:
            state.max_idle_gap_ms = gap_ms
    state.last_upstream_event_at = now


def _record_downstream_first_content():
    state = _request_state()
    if state is None or state.downstream_first_content_at is not None:
        return
    state.phase = "downstream_stream"
    state.downstream_first_content_at = time.monotonic()
    _lifecycle_event("downstream_first_content")


def _record_attempt(transport):
    state = _request_state()
    if state is None:
        return
    state.phase = "upstream_request"
    state.attempts += 1
    _lifecycle_event("upstream_attempt", attempt=state.attempts, transport=transport)


def _record_retry(reason, source="shim_policy"):
    state = _request_state()
    if state is None:
        return
    state.phase = "upstream_retry"
    state.retries += 1
    state.last_retry_reason = _scrub_metadata(reason, 100)
    state.last_retry_source = _scrub_metadata(source, 100)
    _lifecycle_event(
        "upstream_retry", retry=state.retries, reason=state.last_retry_reason,
        source=state.last_retry_source,
    )


def _record_transport_failure(error, phase, retryable):
    state = _request_state()
    if state is None:
        return
    exception_class = _scrub_metadata(type(error).__name__, 100)
    state.transport_exception = exception_class
    if not retryable and state.failure_phase == "-":
        state.failure_phase = phase
    _lifecycle_event(
        "transport_failure", exception_class=exception_class,
        failure_phase=phase, attempt=state.attempts,
        retryable="y" if retryable else "n",
    )


def _record_disconnect(phase):
    state = _request_state()
    if state is None:
        return
    state.disconnect_observed = True
    if state.disconnect_phase == "-":
        state.disconnect_phase = phase
    if state.outcome is None:
        state.outcome = "disconnect"
    if not state.disconnect_logged:
        state.disconnect_logged = True
        state.phase = "disconnect"
        _lifecycle_event(
            "disconnect", observed_phase=state.disconnect_phase,
            detail="ASGI http.disconnect observed",
        )


def _record_backend_error(error_type="api_error", backend_type="-", backend_code="-",
                          phase=None):
    state = _request_state()
    if state is None:
        return
    if state.outcome is None or state.outcome == "disconnect":
        state.outcome = "error"
    if state.failure_phase == "-":
        state.failure_phase = phase or state.phase
    if not state.backend_error_logged:
        state.backend_type = _scrub_metadata(backend_type)
        state.backend_code = _scrub_metadata(backend_code)
        state.anthropic_error_type = error_type
        state.phase = "backend_error"
        state.backend_error_logged = True
        _lifecycle_event(
            "backend_error", backend_type=state.backend_type,
            backend_code=state.backend_code, anthropic_type=error_type,
            failure_phase=state.failure_phase,
        )
    # v1.2.14 (D5): a backend-classified invalid_request_error gets one
    # request-correlated shape line to aid 400 diagnosis. Guarded by its own flag
    # (independent of backend_error_logged) so it emits exactly once even when the
    # backend_error line was already recorded by an earlier failure hop. Names only.
    if (error_type == "invalid_request_error"
            and not state.invalid_request_shape_logged
            and state.request_shape is not None):
        state.invalid_request_shape_logged = True
        _lifecycle_event("request_shape", **state.request_shape)


def _mark_success():
    state = _request_state()
    if state is not None and (
        state.outcome is None
        or (
            state.outcome == "disconnect"
            and state.terminal_frame_send == "send_completed"
        )
    ):
        # A disconnect observed in the same event-loop turn as a completed terminal
        # send is post-terminal evidence. The semantic response already completed;
        # only a cancellation that prevents terminal completion remains disconnect.
        state.outcome = "success"


def _mark_error(phase=None, error_type=None):
    state = _request_state()
    if state is None:
        return
    if state.outcome is None or state.outcome == "disconnect":
        state.outcome = "error"
    if state.failure_phase == "-":
        state.failure_phase = phase or state.phase
    if error_type is not None:
        state.anthropic_error_type = error_type


def _log_terminal_once():
    state = _request_state()
    if state is None or state.terminal_logged:
        return
    state.terminal_logged = True
    if state.outcome is None:
        state.outcome = "disconnect" if state.disconnect_observed else "error"
    if state.disconnect_observed:
        if state.terminal_frame_send == "not_attempted":
            state.terminal_frame_send = "skipped_disconnect"
        if state.body_close_send == "not_attempted":
            state.body_close_send = "skipped_disconnect"
    state.phase = "terminal"
    # v1.3.6 (V6-R4): tick the process-cumulative /health prompt_cache counters exactly
    # once per request (this function is idempotent via terminal_logged, checked above).
    _bump_prompt_cache_counters(state)
    _lifecycle_event(
        "terminal", outcome=state.outcome, model=state.model,
        stream=("y" if state.stream else "n") if state.stream is not None else "-",
        msgs=state.message_count, tools=state.tool_count,
        stop=state.stop_reason, input_tokens=state.input_tokens,
        output_tokens=state.output_tokens, usage=state.usage_source,
        # v1.3.6 (V6-R2): cached-prefix count for the ~1-week telemetry review. The
        # captured int, or the "-" absent-convention when no valid detail was parsed
        # (absent/malformed/clamped -> None). Mapped explicitly because _machine_field_value
        # would render None as "None"; the "-" convention matches usage/stop above. Single
        # lane-agnostic emission site.
        cached_tokens=(state.cached_tokens if state.cached_tokens is not None else "-"),
        requested_service_tier=state.requested_service_tier,
        requested_service_tier_source=state.requested_service_tier_source,
        served_service_tier=state.served_service_tier,
        tools_called=state.tools_called, effort="%s:%s" % (
            state.effort_value, state.effort_source),
        reasoning_cache_miss=state.reasoning_cache_misses,
        # v1.3.4 (V4-R6): additive, always-present ints. reasoning_cache_hit is this
        # request's cache-hit count; reasoning_cache_stripped is 0 unless the stale-blob
        # 400 insurance stripped restored items this request (counts only, never content).
        reasoning_cache_hit=state.reasoning_cache_hits,
        reasoning_cache_stripped=state.reasoning_cache_stripped,
        attempts=state.attempts, retries=state.retries,
        retry_reason=state.last_retry_reason,
        retry_source=state.last_retry_source,
        # v1.2.14 (R4/D2): additive. "-" when no retry slept.
        retry_delay_source=state.retry_delay_source,
        transport_exception=state.transport_exception,
        client_req_id=state.client_request_id,
        upstream_req_id=state.upstream_request_id,
        failure_phase=state.failure_phase,
        terminal_frame_send=state.terminal_frame_send,
        body_close_send=state.body_close_send,
        disconnect=state.disconnect_observed,
        disconnect_phase=state.disconnect_phase,
        # v1.2.14 (D2): additive observability. unknown_events/unknown_items are 0
        # on a clean stream; backend_type/backend_code default to "-" and carry the
        # extracted structural metadata on an in-band or HTTP backend failure.
        unknown_events=state.unknown_events,
        unknown_items=state.unknown_items,
        backend_type=state.backend_type,
        backend_code=state.backend_code,
        # v1.2.14 (R6/D2): additive. Longest observed upstream inter-event silence in
        # whole milliseconds (0 on a single-event or non-streaming response).
        max_idle_gap_ms=state.max_idle_gap_ms,
        dur_ms=_elapsed_ms(state),
    )


def _record_cleanup_result(success, error_type=None):
    """Merge one owned-resource settlement into monotonic request cleanup state."""

    state = _request_state()
    if state is None:
        return
    if success:
        if state.cleanup_status == "not_started":
            state.cleanup_status = "completed"
        return
    state.cleanup_failures += 1
    if state.cleanup_status != "failed":
        state.cleanup_status = "failed"
        state.cleanup_error = _scrub_metadata(error_type, 100)


def _register_owned_stream_context(stream_cm):
    state = _request_state()
    if state is not None:
        state.owned_stream_contexts.append(stream_cm)


def _release_owned_stream_context(stream_cm):
    state = _request_state()
    if state is None:
        return
    try:
        state.owned_stream_contexts.remove(stream_cm)
    except ValueError:
        pass


def _log_cleanup_once():
    state = _request_state()
    if state is None or state.cleanup_logged:
        return
    state.cleanup_logged = True
    state.phase = "cleanup"
    _lifecycle_event(
        "cleanup", status=state.cleanup_status, error=state.cleanup_error,
        failures=state.cleanup_failures, dur_ms=_elapsed_ms(state),
    )


class _RequestLogFilter(logging.Filter):
    def filter(self, record):
        state = _request_state()
        record.req_id = state.req_id if state is not None else "-"
        record.phase = state.phase if state is not None else "process"
        return True


class _ProtocolError(Exception):
    """Controlled upstream Responses protocol/schema violation."""


class _InvalidRequestError(Exception):
    """Sanitized local Anthropic request rejection before any backend call."""


class _ClientDisconnected(Exception):
    """Response-local control signal for a downstream client disconnect."""

    def __init__(self, operation_result=None):
        super().__init__("client disconnected")
        # A successful operation can finish in the same event-loop turn as the
        # disconnect waiter. Preserve that losing result so the caller can close
        # a newly acquired response/context instead of leaking it.
        self.operation_result = operation_result


async def _settle_owned_task(task, cancel=False):
    # INTENT: settle one explicitly owned child despite cancellation already pending
    # on the current task, and retrieve its exact result/exception.
    # REASONING: a second outer cancel can interrupt ordinary cleanup awaits. Shielding
    # the child while repeatedly consuming only the *owner's* cancellation deliveries
    # keeps ownership local; the child is cancelled only when the caller requests it.
    # Returning a tagged outcome retrieves exceptions without turning cleanup into an
    # unobserved-task warning. The third return value tells callers whether cancellation
    # arrived during cleanup so they can preserve cancellation rather than convert it.
    owner_cancellation = None
    if cancel and not task.done():
        task.cancel()
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as cancellation:
            # shield() also raises CancelledError when the CHILD itself is cancelled.
            # Distinguish that from cancellation pending on this owner; only the latter
            # must be propagated after settlement. If the child is now done, leave the
            # loop so its cancelled outcome is retrieved below.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                owner_cancellation = cancellation
            if task.done():
                break
            continue
        except Exception:
            # The child has failed; the tagged task.result() call below retrieves it.
            break
    if task.cancelled():
        return "cancelled", None, owner_cancellation
    try:
        return "result", task.result(), owner_cancellation
    except Exception as error:
        return "exception", error, owner_cancellation


async def _await_or_disconnect(operation, disconnect_event, discard_result=None,
                               prefer_completed=False):
    # INTENT: race one awaitable operation against this response's disconnect
    # event while leaving no child task, exception, or cancellation warning behind.
    # REASONING: passive flag checks cannot interrupt a blocked connect/read/sleep.
    # Upstream operations give disconnect priority when both children finish in the
    # same loop turn, preventing post-disconnect work; downstream ASGI sends may opt
    # to prefer a completed ASGI send so post-terminal disconnect evidence cannot
    # relabel its send state as skipped. A discarded successful upstream result
    # is retained on _ClientDisconnected so resource-owning callers can close it.
    # On outer cancellation, only a caller-supplied discard_result callback may close
    # a successful result: stream responses belong to their local context manager, so
    # a generic duck-typed aclose here would violate exactly-once context ownership.
    operation_task = asyncio.ensure_future(operation)
    disconnect_task = asyncio.create_task(disconnect_event.wait())
    try:
        done, _pending = await asyncio.wait(
            (operation_task, disconnect_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        # Outer cancellation is not a backend/protocol failure. Explicitly cancel and
        # settle both children, retrieving completed same-turn outcomes before the
        # original cancellation propagates. A generic async-close result (notably a
        # buffered httpx.Response) is closed here because no caller can receive it.
        operation_kind, operation_outcome, _owner_cancelled = \
            await _settle_owned_task(operation_task, cancel=True)
        await _settle_owned_task(disconnect_task, cancel=True)
        if operation_kind == "result" and discard_result is not None:
            try:
                close_task = asyncio.ensure_future(discard_result(operation_outcome))
            except Exception:
                close_task = None
            if close_task is not None:
                await _settle_owned_task(close_task)
        raise

    if disconnect_task in done and disconnect_event.is_set():
        # A downstream ASGI send that returned in the same loop turn is a completed
        # ASGI send, not a pure cancellation. The send caller opts into this tie-break
        # so a simultaneous http.disconnect cannot relabel that completed ASGI send as
        # skipped. Upstream connect/read/sleep callers
        # retain disconnect priority and therefore preserve prompt cancellation.
        if prefer_completed and operation_task in done:
            disconnect_task.result()
            return operation_task.result()
        # Retrieve the disconnect wait result and cancel/await the operation. If
        # the operation completed in the same turn, retrieve its result/exception;
        # retain a successful result so the caller can close acquired resources.
        disconnect_task.result()
        operation_kind, operation_outcome, owner_cancellation = \
            await _settle_owned_task(operation_task, cancel=not operation_task.done())
        if owner_cancellation is not None:
            # Simultaneous downstream disconnect and outer task cancellation remains
            # outer cancellation. Retrieve and, where the caller explicitly supplied
            # ownership policy, close a successful discarded result before propagating.
            # Stream contexts provide no callback and are closed by their opener.
            if operation_kind == "result" and discard_result is not None:
                try:
                    close_task = asyncio.ensure_future(
                        discard_result(operation_outcome))
                except Exception:
                    close_task = None
                if close_task is not None:
                    await _settle_owned_task(close_task)
            raise owner_cancellation
        operation_result = (
            operation_outcome if operation_kind == "result" else None
        )
        raise _ClientDisconnected(operation_result)

    # The operation won. Stop and retrieve the response-local waiter before
    # propagating the operation's result or exception. If outer cancellation lands
    # during this cleanup turn, settle/retrieve the operation too and propagate
    # cancellation instead of accidentally returning a resource to cancelled code.
    _waiter_kind, _waiter_outcome, owner_cancellation = await _settle_owned_task(
        disconnect_task, cancel=True)
    if owner_cancellation is not None:
        operation_kind, operation_outcome, _second_cancel = await _settle_owned_task(
            operation_task)
        if operation_kind == "result" and discard_result is not None:
            try:
                close_task = asyncio.ensure_future(discard_result(operation_outcome))
            except Exception:
                close_task = None
            if close_task is not None:
                await _settle_owned_task(close_task)
        raise owner_cancellation
    return operation_task.result()


# Allowlist ONLY — never dump all headers. This structurally guarantees the
# Authorization header (and any other credential-bearing header) is never
# logged: a header is logged only if its lowercased name is in this set.
DIAG_HEADER_ALLOWLIST = (
    "retry-after",
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-reset-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-tokens",
    # v1.2.14 (D1): the chatgpt lane's request-id header.
    "x-oai-request-id",
    # v1.4.9: the request-ID headers used for upstream correlation
    # (_UPSTREAM_REQUEST_ID_HEADERS), so error lines carry them too.
    "x-request-id",
    "request-id",
    "x-openai-request-id",
    "openai-request-id",
    # v1.4.9: chatgpt-lane rate-limit numerics only (percent used and seconds until
    # reset). Plan, limit names, credit fields and window sizes stay in the 2xx
    # quota_snapshot event and are not repeated here.
    "x-codex-primary-used-percent",
    "x-codex-primary-reset-after-seconds",
    "x-codex-secondary-used-percent",
    "x-codex-secondary-reset-after-seconds",
)
# v1.4.9: the v1.2.14 prefix rule (DIAG_HEADER_PREFIX_ALLOWLIST = ("x-codex-",)) is
# REMOVED. It matched every x-codex-* header, which on the live chatgpt lane includes
# x-codex-turn-state (an opaque encrypted backend session token) and the credit
# fields (has-credits, balance, unlimited), so those reached shim.log on error lines.
# Exact names only now: a new upstream header is excluded until someone adds it here.
# v1.2.14 (D1): the compact chatgpt-lane subscription quota snapshot. ONLY numeric and
# enum x-codex-* fields are surfaced — never a free-text header such as a promo message
# or limit name. Each pair maps one header to one stable grep-line key; an absent header
# renders as "-". Values still pass the shared machine-field encoding, so a hostile
# value cannot break the single-token grammar. Header names are lowercased because
# httpx.Headers.get() is case-insensitive. (Live capture: notes/07 §8.)
_QUOTA_SNAPSHOT_HEADER_FIELDS = (
    ("plan_type", "x-codex-plan-type"),
    ("active_limit", "x-codex-active-limit"),
    ("primary_used_pct", "x-codex-primary-used-percent"),
    ("primary_window_min", "x-codex-primary-window-minutes"),
    ("primary_reset_s", "x-codex-primary-reset-after-seconds"),
    ("secondary_used_pct", "x-codex-secondary-used-percent"),
    ("secondary_window_min", "x-codex-secondary-window-minutes"),
    ("secondary_reset_s", "x-codex-secondary-reset-after-seconds"),
    ("credits_has", "x-codex-credits-has-credits"),
    ("credits_balance", "x-codex-credits-balance"),
    ("credits_unlimited", "x-codex-credits-unlimited"),
)
# Defense in depth: even though credentials and Authorization are architecturally
# excluded from logs, upstream-controlled metadata and error text receive one shared
# sensitive-text pass before any truncation or lifecycle-field encoding.
# (re is imported at module top for the v1.2.14 rate-limit-delay pattern.)
_SK_KEY_RE = re.compile(r"(?i)\b(?:sk|rk|org|proj|sess)[-_][A-Za-z0-9_-]{8,}")
_AUTH_SCHEME_RE = re.compile(
    r"(?i)\b((?:authorization\s*:\s*)?(?:bearer|basic))"
    r"\s+([A-Za-z0-9._~+/=-]+)"
)
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}"
    r"(?![A-Za-z0-9_-])"
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])"
    r"(?P<key_quote>[\"']?)"
    r"(?P<key>api_key|access_token|refresh_token|id_token|token|secret|password)"
    r"(?P=key_quote)(?P<separator>\s*[:=]\s*)(?!\[REDACTED\])"
    r"(?:\\\"[^\"\\\r\n]*\\\"|\"[^\"\r\n]*\"|'[^'\r\n]*'|"
    r"[^\s,;\}\]\)&\\\"']+)"
)

# Controls are collapsed, not deleted, so hostile CR/LF cannot concatenate words
# into a new credential-shaped value or forge a physical log line.
_SCRUB_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_sensitive_text(value, max_len=None):
    # INTENT: provide one defense-in-depth sanitizer for every bounded log/client
    #   text surface that may contain backend- or upstream-controlled bytes.
    # REASONING: normalize controls/whitespace first, then redact specific credential
    #   shapes from most structured to least structured: authorization schemes,
    #   OpenAI-style prefixes, JWTs, and named assignments. Assignment values support
    #   matching or absent key quotes plus quoted/unquoted values without consuming
    #   surrounding comma/semicolon/bracket/ampersand text. Every regex is a single
    #   bounded-character-class scan with no nested repetition or ambiguous alternation,
    #   avoiding catastrophic backtracking on adversarial input. Truncation, when
    #   requested, happens only after all redaction passes.
    # ASSUMES: this is defense in depth rather than perfect secret detection; opaque
    #   credentials without a recognized scheme, prefix, JWT shape, or assignment key
    #   remain governed by the architectural rule that payloads/credentials are never
    #   intentionally logged.
    if not isinstance(value, str):
        value = str(value)
    safe = " ".join(_SCRUB_CTRL_RE.sub(" ", value).split())
    safe = _AUTH_SCHEME_RE.sub(lambda match: "%s [REDACTED]" % match.group(1), safe)
    safe = _SK_KEY_RE.sub("[REDACTED]", safe)
    safe = _JWT_RE.sub("[REDACTED]", safe)

    def _redact_assignment(match):
        return "%s%s%s%s[REDACTED]" % (
            match.group("key_quote"),
            match.group("key"),
            match.group("key_quote"),
            match.group("separator"),
        )

    safe = _SENSITIVE_ASSIGNMENT_RE.sub(_redact_assignment, safe)
    if max_len is not None:
        safe = safe[:max_len]
    return safe


def _scrub_log_token(value):
    # v1.2.11: upstream-controlled identifiers in human diagnostic records receive
    # the same control normalization and credential redaction as lifecycle metadata.
    # Non-strings pass through for existing %s rendering semantics.
    return _sanitize_sensitive_text(value) if isinstance(value, str) else value


def _record_wire_divergence(kind):
    # Process-level aggregation is protected even when validators run from multiple
    # server tasks or test threads. Emit one discovery warning, then one bounded
    # summary per fixed interval; no event IDs or payload values enter the record.
    # The summary reports records suppressed strictly BETWEEN emitted records: the
    # first summary at observation 100 therefore covers observations 2..99 (98),
    # while later summaries cover 101..199, 201..299, and so on (99 each). Keep the
    # warning writes inside the same lock so concurrent observations cannot reorder
    # an emitted summary ahead of the discovery record it follows.
    with _WIRE_DIVERGENCE_LOCK:
        count = _WIRE_DIVERGENCE_COUNTS.get(kind, 0) + 1
        _WIRE_DIVERGENCE_COUNTS[kind] = count
        if count == 1:
            log.warning("wire-divergence: %s observed=1", kind)
            _WIRE_DIVERGENCE_LAST_EMITTED[kind] = count
        elif count % _WIRE_DIVERGENCE_SUMMARY_INTERVAL == 0:
            previous_emitted = _WIRE_DIVERGENCE_LAST_EMITTED.get(kind, 0)
            suppressed = count - previous_emitted - 1
            log.warning(
                "wire-divergence-summary kind=%s observed=%d suppressed=%d",
                kind, count, suppressed,
            )
            _WIRE_DIVERGENCE_LAST_EMITTED[kind] = count
    return count


def _record_unknown_wire(kind, name):
    # v1.2.14 (R1): record one observation of an unmodeled wire shape.
    # INTENT: make unknown SSE event types, unmodeled output_item types, and
    #   unrecognized error envelopes VISIBLE instead of vanishing, without ever
    #   logging event bodies or values. Three effects, in order: (a) bump the bounded
    #   process aggregate, (b) route first/every-100th logging through the existing
    #   wire-divergence channel, (c) bump the per-request terminal-record counter.
    # REASONING: the process map is bounded and overflow-collapsed so a novel-name
    #   flood cannot grow it; the name is scrubbed and length-bounded before it can
    #   reach a log line. The behavior is observability-only — unknown shapes are
    #   still not translated (there is nothing to translate them to).
    # ASSUMES: kind is a source constant ("event_type"/"item_type"/"envelope");
    #   only `name` is backend-influenced and therefore scrubbed.
    safe_name = _sanitize_sensitive_text(name, max_len=64) if isinstance(
        name, str) and name else "-"
    with _UNKNOWN_WIRE_LOCK:
        key = (kind, safe_name)
        if key not in _UNKNOWN_WIRE_COUNTS and (
                len(_UNKNOWN_WIRE_COUNTS) >= _UNKNOWN_WIRE_CAP):
            key = (kind, "__overflow__")
        _UNKNOWN_WIRE_COUNTS[key] = _UNKNOWN_WIRE_COUNTS.get(key, 0) + 1
    _record_wire_divergence("unknown_%s:%s" % (kind, key[1]))
    state = _request_state()
    if state is not None:
        if kind == "item_type":
            state.unknown_items += 1
        else:
            state.unknown_events += 1


def _request_shape_fields(payload):
    # v1.2.14 (D5): capture only the SORTED top-level request key NAMES (plus
    # text/reasoning sub-key names) for a possible invalid_request_error diagnosis
    # line. Names only, never values; the outbound Responses payload keys are
    # shim-constructed identifiers, and _lifecycle_event scrubs each value anyway.
    if not isinstance(payload, dict):
        return None
    fields = {"keys": ",".join(sorted(str(k) for k in payload.keys()))}
    for sub in ("text", "reasoning"):
        val = payload.get(sub)
        if isinstance(val, dict):
            fields["%s_keys" % sub] = ",".join(sorted(str(k) for k in val.keys()))
    return fields


# v1.2.0: reasoning-item cache (module-level, bounded LRU).
# INTENT: the Responses API pairs a `reasoning` output item with the
#   function_call(s) that follow it. On store:false stateless replay the caller
#   MUST re-inject that reasoning item (with its encrypted_content blob) into
#   input[] immediately before the paired function_call, or gpt-5.x can reject
#   the request: "function_call was provided without its required 'reasoning'
#   item." Claude Code, however, only round-trips tool_use/tool_result blocks —
#   the reasoning item is not part of the Anthropic wire format and is NOT
#   resent by the client. So the shim caches each reasoning item keyed by the
#   call_id(s) of the function_call(s) it precedes, and re-injects on the next
#   turn's replay.
# REASONING: keyed by call_id because that is the ONLY identifier that survives
#   the Anthropic round-trip (tool_use.id -> function_call.call_id ->
#   function_call_output.call_id). The reasoning item's own id (rs_...) never
#   reaches Claude Code, so it cannot be the key.
# ASSUMES: a bounded LRU (evict-oldest) is sufficient — a session's live tool
#   calls are recent, and a cache miss degrades gracefully (omit the reasoning
#   item, log the miss, proceed) rather than failing. Cap ~2048 entries covers
#   long multi-hop sessions without unbounded growth. Not persisted across shim
#   restarts (a restart mid-session simply produces cache misses).
_REASONING_CACHE = OrderedDict()   # call_id -> reasoning item dict (WITH encrypted_content)
_REASONING_CACHE_CAP = 2048

# v1.3.4 (V4-R1): call_ids whose reasoning blob was loaded from the persisted snapshot at
# import (as opposed to populated by a live backend response this process). Defined BEFORE
# _cache_reasoning so the write path below can reference it — Python resolves module globals
# at call time, and the first call (the import-time restore) runs after this binding exists.
# A restored blob is the one case v1.3.3 persistence can turn a graceful cache miss into a
# hard failure (a stale encrypted_content of unknown backend-side validity is re-injected
# and rejected with a 400); this set lets the stale-blob 400 insurance (V4-R2..R4) tell a
# restored blob from a live-populated one at re-injection time. Contents are call_ids only.
_REASONING_CACHE_RESTORED_IDS = set()

# v1.3.4 (V4-R7): process-cumulative reasoning-cache hit counters for the /health restore-
# effectiveness surface. _REASONING_CACHE_HITS_TOTAL counts every cache hit since process
# start; _REASONING_CACHE_RESTORED_HITS_TOTAL counts the subset whose call_id was still in
# _REASONING_CACHE_RESTORED_IDS at hit time (the direct measure of how often disk-restored
# continuity is actually exercised, for the ~1-week cap/ceiling review). Counts only, never
# content or call_ids. Ticked read-only alongside the .get() hit (never a move_to_end), so
# hit-counting adds ZERO cache-file write amplification (the persist writer stays gated on
# genuine cache mutations only).
_REASONING_CACHE_HITS_TOTAL = 0
_REASONING_CACHE_RESTORED_HITS_TOTAL = 0


def _bump_reasoning_hit_counters(restored):
    # v1.3.4 (V4-R7): tick the process-cumulative /health hit counters for one cache hit.
    # `restored` is True iff this hit's call_id was in _REASONING_CACHE_RESTORED_IDS at hit
    # time. This never touches the cache itself (the caller reads via .get(), never
    # move_to_end), so it introduces no LRU mutation and no persist / write amplification.
    global _REASONING_CACHE_HITS_TOTAL, _REASONING_CACHE_RESTORED_HITS_TOTAL
    _REASONING_CACHE_HITS_TOTAL += 1
    if restored:
        _REASONING_CACHE_RESTORED_HITS_TOTAL += 1


# v1.3.6 (V6-R4): process-cumulative prompt-cache observability counters for the /health
# prompt_cache block. COUNTS ONLY — never prompt content or token material. Ticked once per
# terminal (from _log_terminal_once, idempotent via terminal_logged) by
# _bump_prompt_cache_counters. requests_with_usage counts terminals with a backend-parsed
# usage; requests_with_cached is the subset reporting cached_tokens > 0; cached_tokens_total
# and input_tokens_total are the cumulative sums (input_tokens_total is the OpenAI input
# TOTAL) so the ~1-week review reads a cache hit-rate in ONE probe as
# cached_tokens_total / input_tokens_total.
_PROMPT_CACHE_REQUESTS_WITH_USAGE = 0
_PROMPT_CACHE_REQUESTS_WITH_CACHED = 0
_PROMPT_CACHE_CACHED_TOKENS_TOTAL = 0
_PROMPT_CACHE_INPUT_TOKENS_TOTAL = 0


def _bump_prompt_cache_counters(state):
    # v1.3.6 (V6-R4): tick the /health prompt_cache counters for one terminal. Gated on a
    # BACKEND-sourced usage (usage_source == "backend") so the estimated-fallback path
    # (input_tokens defaulted to 0, no real cache detail) never pollutes the hit-rate
    # denominator. The cached counters advance only on a valid, non-clamped cached detail
    # (state.cached_tokens a real int > 0). Counts only; never raises.
    global _PROMPT_CACHE_REQUESTS_WITH_USAGE, _PROMPT_CACHE_REQUESTS_WITH_CACHED
    global _PROMPT_CACHE_CACHED_TOKENS_TOTAL, _PROMPT_CACHE_INPUT_TOKENS_TOTAL
    if state is None or state.usage_source != "backend":
        return
    if isinstance(state.input_tokens, bool) or not isinstance(state.input_tokens, int):
        return
    _PROMPT_CACHE_REQUESTS_WITH_USAGE += 1
    _PROMPT_CACHE_INPUT_TOKENS_TOTAL += state.input_tokens
    cached = state.cached_tokens
    if not isinstance(cached, bool) and isinstance(cached, int) and cached > 0:
        _PROMPT_CACHE_REQUESTS_WITH_CACHED += 1
        _PROMPT_CACHE_CACHED_TOKENS_TOTAL += cached


def _cache_reasoning(call_id, reasoning_item):
    # INTENT: store one reasoning item under a function_call's call_id, LRU-style.
    # REASONING: move-to-end on write so the most recently paired call_ids evict
    #   last; a session's active tool loop stays warm.
    # RETURNS: True iff the write actually landed (valid call_id + dict item), False
    #   on a no-op reject. v1.3.3 (A2): the caller uses this to persist only on a real
    #   mutation, and the restore path reuses it to rebuild the cache in file order.
    if not call_id or not isinstance(reasoning_item, dict):
        return False
    _REASONING_CACHE[call_id] = reasoning_item
    _REASONING_CACHE.move_to_end(call_id)
    # v1.3.4 (V4-R1): a write here is a LIVE (re-)population of this call_id — the blob is
    # fresh from a backend response, so it is no longer a disk-restored entry. Drop it from
    # the restored set. The import-time restore also routes through this function, so it
    # re-adds the genuinely-restored ids AFTER its loop (see _restore_reasoning_cache); this
    # discard therefore never races the restore's own bookkeeping.
    _REASONING_CACHE_RESTORED_IDS.discard(call_id)
    while len(_REASONING_CACHE) > _REASONING_CACHE_CAP:
        evicted_id, _evicted_item = _REASONING_CACHE.popitem(last=False)  # evict oldest
        # An evicted entry can no longer be injected, so it cannot be a stale-blob source.
        _REASONING_CACHE_RESTORED_IDS.discard(evicted_id)
    return True


def _populate_reasoning_cache(output_items):
    # INTENT: from a Responses `output[]` array, associate each `reasoning` item
    #   with the call_id(s) of the function_call item(s) that FOLLOW it in output
    #   order, up to the next reasoning item. Store the full reasoning item
    #   (including encrypted_content) under each such call_id.
    # REASONING: the API emits reasoning immediately before the function_call(s)
    #   it justifies; parallel calls share one reasoning item. Walking output[]
    #   and re-pointing `current_reasoning` at each reasoning item, then binding
    #   every subsequent function_call to it until the next reasoning item,
    #   reproduces that pairing without needing an explicit link field.
    # ASSUMES: reasoning precedes its function_calls in output order (verified in
    #   the wire-format spec skeleton, notes file 04 §4). A function_call with no
    #   preceding reasoning item (current_reasoning is None) is simply not cached
    #   — nothing to inject, and the cache miss path handles the absence.
    # RETURNS: the number of cache entries actually written/refreshed. v1.3.3 (A2):
    #   the call sites persist the cache only when this is nonzero, so a populate that
    #   binds nothing (no reasoning, or unpaired function_calls) triggers no disk write.
    current_reasoning = None
    mutated = 0
    for item in output_items or []:
        if not isinstance(item, dict):
            continue
        itype = item.get("type")
        if itype == "reasoning":
            current_reasoning = item
        elif itype == "function_call":
            if current_reasoning is not None:
                if _cache_reasoning(item.get("call_id"), current_reasoning):
                    mutated += 1
    return mutated


# --- v1.3.3 (A2): reasoning-cache persistence across shim restarts ---
# INTENT: the in-memory _REASONING_CACHE above is module-global and unpersisted, so
#   every restart discards it. A restart mid-session then replays the tool history
#   WITHOUT its reasoning items — the miss path is graceful (omit the item, count the
#   miss, proceed), but the model loses the reasoning context for the rest of a long
#   tool loop. Persisting a bounded newest-first snapshot on each cache mutation and
#   restoring it at import keeps reasoning continuity across a restart.
# SECURITY: persisted values are EXACTLY the in-memory values — opaque backend-encrypted
#   `encrypted_content` blobs plus item metadata. No plaintext reasoning, no key
#   material (same posture as the live cache; Anthropic thinking blocks are consumed,
#   never stored). Logging discipline is unchanged: names/counts only, never contents.
# PLACEMENT (A2-R4, amended by the design checkpoint): the default lives on the
#   per-container claude-config volume ($HOME/.claude/provider_shim/), DELIBERATELY
#   outside the /daaf repo tree. Reasoning blobs are relatively private and must not sit
#   in a directory that is shareable across containers or ever syncable to VCS. This is
#   why the path is HOME-derived, NOT __file__-derived like quota_state.json (which is
#   scrubbed operational telemetry, deliberately kept install-shared in logs/). Only the
#   content-bearing artifact moves off the repo mount. Because the file is per-container,
#   the install-shared last-writer-wins race that quota_state.json carries does not apply
#   here; the supported topology is one running shim per container at a time.
# SEAM (A2-R4): DAAF_REASONING_CACHE_FILE, resolved at MODULE IMPORT time exactly like
#   DAAF_QUOTA_STATE_FILE (a post-import env change does NOT redirect a live shim). When
#   set and non-empty it overrides both the path and its parent dir; when unset the
#   HOME-derived default below applies. Hermetic tests provision this seam in every
#   module-load context (spawned child env, in-process runner setdefault, per-test patch).
_REASONING_CACHE_FILE_ENV = os.environ.get("DAAF_REASONING_CACHE_FILE", "")
if _REASONING_CACHE_FILE_ENV:
    _REASONING_CACHE_PATH = _REASONING_CACHE_FILE_ENV
    _REASONING_CACHE_DIR = os.path.dirname(_REASONING_CACHE_PATH)
else:
    _REASONING_CACHE_DIR = os.path.join(
        os.path.expanduser("~"), ".claude", "provider_shim"
    )
    _REASONING_CACHE_PATH = os.path.join(_REASONING_CACHE_DIR, "reasoning_cache.json")

# Persistence bounds (A2-R2; Decision 3 as amended; v1.3.6 V6-R5 resize to 1024 / 8 MiB).
# The entry/byte caps are the PRIMARY bound and intentionally mirror the in-memory LRU tail
# — restart recovery only needs the recent tail (active tool loops), not all 2048 in-memory
# entries, and the byte cap bounds the response-path write to low tens of ms at the 8 MiB
# bound (measured 2026-07-22: ~19 ms median, ~25 ms worst over 20 full-snapshot serialize+
# atomic-write iterations incl. fsync — a conservative upper bound; was "single-digit ms" at
# the old 2 MiB cap). The TTL is only a 30-day SANITY CEILING against
# replaying ancient blobs of unknown backend-side validity; it is deliberately NOT an
# aggressive expiry, because the live cache has no age limit (LRU only) and multi-day
# session gaps are normal (a short TTL would erase exactly the entries a resumed session
# replays). Keep the NEWEST entries when either bound binds.
_REASONING_PERSIST_MAX_ENTRIES = 1024      # v1.3.6 (V6-R5): 256 -> 1024 (4x headroom)
_REASONING_PERSIST_MAX_BYTES = 8_388_608   # v1.3.6 (V6-R5): 2 MiB -> 8 MiB
_REASONING_PERSIST_TTL_S = 2_592_000       # 30 days (sanity ceiling only)

# Count of entries loaded from the persisted snapshot at startup (0 if none). Set by the
# restore call below and surfaced read-only on /health. Never includes contents/call_ids.
_REASONING_CACHE_RESTORED = 0


def _write_reasoning_cache_state():
    # Absolutely fail-open persistence, mirroring _write_quota_state (:1321): a persist
    # must NEVER affect, delay, or raise on the response path. Every failure mode
    # (unwritable dir, replace error, serialization surprise, bad seam value) is
    # swallowed, leaving at most one debug line and no stale temp sibling.
    tmp_path = None
    try:
        # Snapshot the NEWEST entries (the LRU tail). _REASONING_CACHE iterates
        # oldest->newest, so the last N items are the most-recently-used; keeping the tail
        # matches the in-memory eviction order and gives restore an oldest->newest list.
        items = list(_REASONING_CACHE.items())
        if not items:
            return
        entries = [[cid, item] for cid, item in items[-_REASONING_PERSIST_MAX_ENTRIES:]]
        payload = {"captured_at": int(time.time()), "entries": entries}
        data = json.dumps(payload).encode("utf-8")
        # Byte cap: if oversize, drop OLDEST entries (front) until under the cap, keeping
        # the newest. If even a single entry exceeds the cap, persist nothing this round.
        while len(data) > _REASONING_PERSIST_MAX_BYTES and len(payload["entries"]) > 1:
            payload["entries"] = payload["entries"][1:]
            data = json.dumps(payload).encode("utf-8")
        if len(data) > _REASONING_PERSIST_MAX_BYTES:
            return
        # The shim owns directory creation (the HOME-derived default dir may not exist yet
        # in a fresh container). 0700 matches the logs/ dir discipline start_shim.sh uses.
        os.makedirs(_REASONING_CACHE_DIR, mode=0o700, exist_ok=True)
        # Atomic publish via a uniquely-named sibling temp + os.replace(): a reader sees
        # either the old file or the fully-written new one, never a partial write. mkstemp
        # creates the temp with mode 0600 already (matching the shim.log/quota_state
        # permission discipline). os.replace onto a symlink replaces the symlink entry
        # itself (rename(2) does not dereference the destination), so the atomic-publish
        # path is not symlink-redirectable; the 0700 parent dir is the primary guard.
        fd, tmp_path = tempfile.mkstemp(
            prefix="reasoning_cache.", suffix=".tmp", dir=_REASONING_CACHE_DIR
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_path, _REASONING_CACHE_PATH)
        tmp_path = None
    except Exception:
        try:
            log.debug("reasoning_cache write skipped (fail-open)")
        except Exception:
            pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _restore_reasoning_cache():
    # Fail-open restore at import. Returns (restored_count, age_s) on a successful load,
    # (0, None) on ANY failure or skip (missing file, unparseable JSON, bad shape, stale,
    # oversize). Never raises. The next persist overwrites a file that failed to restore.
    try:
        if not os.path.exists(_REASONING_CACHE_PATH):
            return (0, None)
        # Defense-in-depth (A2 review INFO-2): bound the READ the same way the writer bounds
        # its output. Check the on-disk size BEFORE reading the whole file into memory and
        # skip an oversized file. A shim-written file can never exceed the byte cap (the
        # writer refuses to publish above it at the `len(data) > _REASONING_PERSIST_MAX_BYTES`
        # guard above), so this only trips on a hand-tampered/oversized file — fail-open like
        # every other branch here (an OSError from getsize is caught by the outer except).
        if os.path.getsize(_REASONING_CACHE_PATH) > _REASONING_PERSIST_MAX_BYTES:
            return (0, None)
        with open(_REASONING_CACHE_PATH, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
        if not isinstance(payload, dict):
            return (0, None)
        captured_at = payload.get("captured_at")
        entries = payload.get("entries")
        # bool is an int subclass; reject it explicitly so a stray True/False captured_at
        # cannot pass the numeric gate.
        if isinstance(captured_at, bool) or not isinstance(captured_at, int):
            return (0, None)
        if not isinstance(entries, list):
            return (0, None)
        age_s = int(time.time()) - captured_at
        # Reject a future timestamp (clock skew / tampering) and anything past the 30-day
        # sanity ceiling.
        if age_s < 0 or age_s > _REASONING_PERSIST_TTL_S:
            return (0, None)
        # Rebuild in file order (oldest->newest) so the LRU tail ends up most-recently-used;
        # _cache_reasoning enforces the 2048 cap and skips malformed pairs. A single bad
        # entry is skipped, not fatal — the rest of a well-formed file still restores.
        restored = 0
        restored_ids = set()
        for pair in entries:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            if _cache_reasoning(pair[0], pair[1]):
                restored += 1
                restored_ids.add(pair[0])
        # v1.3.4 (V4-R1): record which call_ids came from disk so the stale-blob 400
        # insurance can distinguish a restored blob from a live-populated one at
        # re-injection. Built AFTER the loop because _cache_reasoning discards each id as it
        # writes (treating every write as live population); we re-add the genuinely-restored
        # ids here, intersected with what actually resides in the cache (a hand-tampered
        # over-cap file could have evicted some during the loop). Mutated in place (clear +
        # update) so no `global` rebinding is needed.
        _REASONING_CACHE_RESTORED_IDS.clear()
        _REASONING_CACHE_RESTORED_IDS.update(restored_ids & set(_REASONING_CACHE.keys()))
        # A2 review INFO-1: report the number of entries actually RESIDENT after restore,
        # not the raw insert count. A hand-tampered file with more entries than
        # _REASONING_CACHE_CAP (or with duplicate call_ids) would make `restored` exceed
        # what the cache actually holds (e.g. 5000 inserts -> cache caps at 2048),
        # overstating /health.reasoning_cache.restored. Clamp against the live cache size
        # (restore runs at import against an empty cache, so len == the resident restored
        # count) so the surfaced number can never overstate what is truly loaded.
        return (min(restored, len(_REASONING_CACHE)), age_s)
    except Exception:
        return (0, None)


# Restore at import, adjacent to the cache definition. `log` is not configured yet here,
# so the one-line restore log is DEFERRED to just after logging is set up below (mirroring
# the _backend_mode_warn deferral). counts only — never entry contents or call_ids.
_reasoning_restore_result = _restore_reasoning_cache()
_REASONING_CACHE_RESTORED = _reasoning_restore_result[0]


# HARDENING: structured logging to stderr ONLY. The manager script redirects
# stderr to the log file. No FileHandler here and, critically, no credential or
# body logging anywhere.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s req_id=%(req_id)s phase=%(phase)s %(message)s",
    stream=sys.stderr,
)
# Attach to the existing stderr handler rather than adding a file or second stream.
# Root-owned httpx records and shim records therefore share request correlation.
for _stderr_handler in logging.getLogger().handlers:
    _stderr_handler.addFilter(_RequestLogFilter())
log = logging.getLogger("shim")

# v1.2.5: emit the deferred SHIM_BACKEND_MODE warning now that `log` exists (the
# value was resolved above, before logging was configured). Fires ONCE for an
# invalid value; silent for a valid one.
if _backend_mode_warn is not None:
    log.warning(_backend_mode_warn)
# v1.4.7: one-time notice for a base URL pasted with a trailing /responses.
if _backend_base_url_warn is not None:
    log.warning(_backend_base_url_warn)
# v1.4.8: one-time notice for an unrecognized SHIM_PDF_MODE value.
if _pdf_mode_warn is not None:
    log.warning(_pdf_mode_warn)

# v1.3.3 (A2-R3): emit the deferred reasoning-cache restore line now that `log` exists.
# The restore itself ran at import above (before logging was configured). Silent when
# nothing was restored (missing/stale/corrupt file all resolve to 0). counts only —
# never entry contents or call_ids.
if _REASONING_CACHE_RESTORED > 0:
    log.info(
        "event=reasoning_cache_restore entries=%d age_s=%s",
        _REASONING_CACHE_RESTORED, _reasoning_restore_result[1],
    )

# v1.2.4: resolve the process-wide response verbosity now that `log` exists (the
# resolver emits its one WARNING via `log` for an invalid value). Read once at
# startup; the hot path just reads this constant into text:{"verbosity": ...}.
SHIM_TEXT_VERBOSITY = _resolve_startup_verbosity()

# Shared async client (connection pooling; long read timeout for slow models).
_client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0))


# --- v1.3.0: ChatGPT-subscription auth layer — delegated to the codex CLI ---
# INTENT: in chatgpt mode the Bearer is the OAuth access_token from
#   $CODEX_HOME/auth.json, not an api.openai.com API key. The access_token TTL is
#   ~10 days (notes/09 A), so within any DAAF session refreshes are rare: this layer
#   is READ-MOSTLY. It reads the access_token, sends it as Bearer, and — when the
#   token is near expiry (proactive) or a backend 401 rejects it (reactive) —
#   DELEGATES the refresh to the codex CLI. The codex CLI is the SINGLE WRITER of
#   auth.json; the shim NEVER writes it. The shim invokes `codex login status`, then
#   re-reads auth.json and judges validity from the JWT `exp` claim. Delegating the
#   write structurally eliminates the refresh-token-rotation race a Python-side
#   refresh had with any other codex-based tool sharing the same CODEX_HOME (the
#   live-confirmed 2026-07-20 auth-lockout cause).
# CREDENTIAL SAFETY: no token value is ever logged. The shim only READS auth.json;
#   codex owns every write. Presence is checked with `if not tok:` guards, never by
#   printing. The codex subprocess's stdout/stderr are captured (to keep them off the
#   shim's own streams) but NEVER logged — codex may echo account detail. Only its
#   exit code and a coarse event label are logged.

# The codex binary used for delegated refresh. Default `codex` (on PATH in the DAAF
# image); overridable for test injection (a fake-codex stub) and portability.
SHIM_CODEX_BIN = os.environ.get("SHIM_CODEX_BIN", "").strip() or "codex"
# Wall-clock bound on the `codex login status` subprocess. Float-tolerant: an
# unparseable value falls back to the 30s default (mirrors the SHIM_PING_INTERVAL_S
# convention). A hung codex must not stall a chatgpt-lane request indefinitely; on
# timeout the child is killed and the re-read decides success/failure.
try:
    SHIM_CODEX_TIMEOUT_S = float(os.environ.get("SHIM_CODEX_TIMEOUT_S", "30"))
except (ValueError, TypeError):
    SHIM_CODEX_TIMEOUT_S = 30.0
# Refresh when the access_token is within this many seconds of its `exp`. Mirrors
# codex's own CHATGPT_ACCESS_TOKEN_REFRESH_WINDOW_MINUTES (5 min, notes/05) so that
# when the shim decides to refresh, codex — keying refresh on the same window —
# actually performs it rather than treating `login status` as a no-op.
_TOKEN_REFRESH_MARGIN_S = 5 * 60
# Actionable message surfaced on ANY auth failure (a failed delegated refresh, a
# post-retry 401, a missing/unreadable auth store, or codex reporting "Not logged
# in"). No secret content — just the recovery instruction. It MUST literally contain
# `codex login --device-auth` (A1-R5); every auth-failure surface reuses this string.
_RELOGIN_MSG = ("ChatGPT OAuth token is invalid or expired and the codex CLI could "
                "not refresh it; run 'codex login --device-auth' inside the container "
                "to re-authenticate")

# In-process single-flight serialization of delegated refreshes (the shim is async;
# concurrent requests that all observe a stale/rejected token must not each spawn a
# codex subprocess — the first refresh wins and the rest adopt its result).
# Cross-process coordination is now codex's own domain as the single writer.
_token_refresh_lock = asyncio.Lock()
# The access_token currently held in memory. Seeded lazily from disk on first use.
# Value is a secret string; never logged.
_token_state = {"access_token": None, "exp": None}


def _b64url_decode(seg):
    # INTENT: decode one base64url JWT segment to bytes, tolerating missing padding.
    # REASONING: JWT segments are base64url WITHOUT padding; urlsafe_b64decode
    #   requires padding, so pad to a multiple of 4. Never raises to the caller for
    #   a malformed segment — callers treat a decode failure as "no exp".
    import base64
    seg = seg + "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg.encode("ascii"))


def _jwt_exp(access_token):
    # INTENT: extract the `exp` (unix seconds) claim from a JWT access_token by
    #   decoding its PAYLOAD ONLY — the middle segment. The signature is NEVER
    #   decoded or verified (we are not the token issuer; we only need the expiry
    #   to decide when to refresh).
    # REASONING: a JWT is header.payload.signature (base64url). We split on ".",
    #   decode segment[1], json-parse it, and read "exp". Any structural problem
    #   (not 3 segments, bad base64, bad JSON, missing/non-numeric exp) yields None,
    #   which the caller treats as "unknown expiry" (forces a conservative refresh).
    # CREDENTIAL SAFETY: the token string is handled in-memory only; neither the
    #   token nor any decoded claim is logged.
    # ASSUMES: the access_token is a JWT (notes/09: it carries exp + account claims).
    #   If it is ever opaque (non-JWT), _jwt_exp returns None and the layer refreshes
    #   conservatively rather than trusting a stale token.
    if not access_token or not isinstance(access_token, str):
        return None
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(_b64url_decode(parts[1]))
    except Exception:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp == exp:  # exp==exp rejects NaN
        return int(exp)
    return None


def _read_auth_json():
    # INTENT: read and parse $CODEX_HOME/auth.json, returning the parsed dict.
    # REASONING: chatgpt mode REQUIRES a resolvable auth store. A missing
    #   CODEX_HOME, a missing file, or unparseable JSON is a hard, actionable error
    #   (raise RuntimeError with the re-login message) — we NEVER invent a default
    #   path or a synthetic token (notes/09 F).
    # CREDENTIAL SAFETY: the returned dict CONTAINS token values; callers must not
    #   log it. The error message carries no secret content.
    if not _CODEX_AUTH_PATH:
        raise RuntimeError(
            "CODEX_HOME is not set; chatgpt backend mode requires an auth store. "
            + _RELOGIN_MSG)
    try:
        with open(_CODEX_AUTH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        # OSError = missing/unreadable; ValueError = malformed JSON. Do NOT echo the
        # file body — only the exception TYPE and the recovery instruction.
        raise RuntimeError(
            "cannot read auth.json (%s); %s" % (type(e).__name__, _RELOGIN_MSG))
    if not isinstance(data, dict) or not isinstance(data.get("tokens"), dict):
        raise RuntimeError("auth.json missing 'tokens'; " + _RELOGIN_MSG)
    return data


async def _run_codex_login_status():
    # INTENT: invoke `{SHIM_CODEX_BIN} login status` so the codex CLI — the SINGLE
    #   writer of auth.json — performs any needed token refresh in its own store.
    # REASONING: async create_subprocess_exec keeps the event loop unblocked; the
    #   subprocess inherits the shim's environ (CODEX_HOME already exported) so codex
    #   targets the same per-install store the shim reads. Bounded by
    #   SHIM_CODEX_TIMEOUT_S. This call's exit code and output are DIAGNOSTIC ONLY —
    #   the authoritative refresh outcome is the auth.json re-read the caller performs
    #   afterward, NEVER parsed from this subprocess's stdout/stderr (A1-R3). A spawn
    #   failure (missing binary) or a timeout is non-fatal here; the re-read decides.
    # CREDENTIAL SAFETY: stdout/stderr are captured (to keep them off the shim's own
    #   streams) but NEVER logged — codex may echo account detail. Only the exit code
    #   and a coarse event label are logged.
    try:
        proc = await asyncio.create_subprocess_exec(
            SHIM_CODEX_BIN, "login", "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
    except (OSError, ValueError) as e:
        # Missing binary (FileNotFoundError), permission error, bad argv, etc. Log the
        # exception TYPE only; the caller's re-read surfaces the actionable error.
        log.warning("event=codex_spawn_failed err=%s", type(e).__name__)
        return
    try:
        await asyncio.wait_for(proc.communicate(), timeout=SHIM_CODEX_TIMEOUT_S)
    except asyncio.TimeoutError:
        log.warning("event=codex_login_status_timeout timeout_s=%s",
                    SHIM_CODEX_TIMEOUT_S)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        # Reap the killed child so it does not linger as a zombie or leak its pipes.
        # Bound the reap: an unkillable child (e.g. stuck in uninterruptible sleep)
        # must not stall the request path — log a coarse event and keep going.
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5)
        except asyncio.TimeoutError:
            log.warning("event=codex_login_status_reap_timeout timeout_s=5")
        except Exception:
            pass
        return
    log.info("event=codex_login_status rc=%s", proc.returncode)


async def delegated_refresh(rejected_token=None):
    # INTENT: the single delegated-refresh primitive. Serialize (single-flight),
    #   invoke the codex CLI to refresh, then re-read auth.json and judge validity by
    #   the JWT `exp` — returning a currently-valid access_token or raising
    #   RuntimeError(_RELOGIN_MSG). Success/failure is determined ONLY by the re-read
    #   result, never by the subprocess's exit code or output (A1-R3).
    # REASONING: the asyncio.Lock makes concurrent callers single-flight — the first
    #   waiter refreshes; the rest, after acquiring the lock, adopt the now-fresh
    #   in-memory token WITHOUT re-invoking codex (the short-circuit below).
    # rejected_token: on the reactive (401) path this is the token the backend just
    #   rejected. A token that merely LOOKS exp-valid but EQUALS rejected_token must
    #   NOT short-circuit the codex invocation — the server has already rejected it,
    #   so its exp margin cannot vouch for it. On the proactive path it is None.
    # CREDENTIAL SAFETY: token values live in memory / auth.json only; never logged.
    async with _token_refresh_lock:
        now = time.time()
        # Single-flight short-circuit: a concurrent waiter may have already refreshed
        # to a comfortably-valid token. Adopt it without re-invoking codex — unless it
        # is the very token we were told the backend rejected.
        cached = _token_state["access_token"]
        cached_exp = _token_state["exp"]
        if (cached and cached_exp is not None
                and cached_exp - now > _TOKEN_REFRESH_MARGIN_S
                and (rejected_token is None or cached != rejected_token)):
            return cached

        # Delegate the refresh to codex (the single writer). Diagnostic only.
        await _run_codex_login_status()

        # Authoritative outcome: re-read auth.json and judge validity from the JWT
        # exp. A missing/unreadable/malformed store raises RuntimeError(_RELOGIN_MSG).
        current = _read_auth_json()
        disk_access = (current.get("tokens") or {}).get("access_token")
        disk_exp = _jwt_exp(disk_access)
        if disk_access and disk_exp is not None and disk_exp - now > _TOKEN_REFRESH_MARGIN_S:
            _token_state["access_token"] = disk_access
            _token_state["exp"] = disk_exp
            log.info("chatgpt token refreshed via codex (new exp=%s)", disk_exp)
            return disk_access
        # Still invalid/absent after delegation -> actionable failure (A1-R5).
        raise RuntimeError(_RELOGIN_MSG)


async def _get_access_token(force_refresh=False, rejected_token=None):
    # INTENT: return a currently-valid access_token for the chatgpt-lane Bearer.
    #   The common path is a pure READ (no subprocess): the ~10-day TTL means the
    #   token is almost always comfortably valid. A refresh — DELEGATED to the codex
    #   CLI — happens only proactively (token within _TOKEN_REFRESH_MARGIN_S of exp)
    #   or reactively (force_refresh, the lazy-401 path).
    # REASONING: the proactive path checks the cached token, then the authoritative
    #   on-disk token; only if that is missing or near-expiry does it delegate. The
    #   reactive path always delegates (passing the rejected token) because a 401'd
    #   token can still be far from its nominal exp — exp margin cannot decide.
    # CREDENTIAL SAFETY: token values live in memory / auth.json only; never logged.
    now = time.time()

    # Fast path (no lock, no subprocess): a cached in-memory token that is comfortably
    # valid and no forced refresh -> return it directly.
    if not force_refresh:
        cached = _token_state["access_token"]
        cached_exp = _token_state["exp"]
        if cached and cached_exp is not None and cached_exp - now > _TOKEN_REFRESH_MARGIN_S:
            return cached

    if force_refresh:
        # Reactive (lazy-401): delegate unconditionally, passing the rejected token so
        # the single-flight short-circuit cannot hand back the just-rejected token.
        return await delegated_refresh(rejected_token=rejected_token)

    # Proactive: re-read the authoritative on-disk token (cheap). If it is present and
    # comfortably valid, adopt and return it with no subprocess. Otherwise delegate.
    # A missing/unreadable store raises RuntimeError(_RELOGIN_MSG) (A1-R5).
    current = _read_auth_json()
    disk_access = (current.get("tokens") or {}).get("access_token")
    disk_exp = _jwt_exp(disk_access)
    if disk_access:
        _token_state["access_token"] = disk_access
        _token_state["exp"] = disk_exp
    if disk_access and disk_exp is not None and disk_exp - now > _TOKEN_REFRESH_MARGIN_S:
        return disk_access
    return await delegated_refresh()


# --- Helpers: request translation (Anthropic -> OpenAI Responses) ---

def _split_effort_suffix(model):
    # v1.2.2: parse and STRIP a "#<effort>" suffix from a model slug.
    # INTENT: Claude Code v2.1.187 passes a custom slug's "#<effort>" suffix to the
    #   wire verbatim inside `model` (e.g. "gpt-5.6-sol#high"). The shim must strip
    #   it before the model reaches OpenAI (a "#"-bearing model is not a valid
    #   backend slug) and surface the parsed effort as precedence TIER 2.
    # REASONING: the "[1m]" window hint is consumed CLIENT-side and never reaches
    #   the shim (wire-captured 2026-07-11, both orderings), so the only suffix the
    #   shim ever sees is "#<effort>". We split on the FIRST "#" and treat
    #   everything after it as the raw effort token (lowercased, whitespace-
    #   stripped). Returns (bare_model, raw_suffix_or_None). The suffix is ALWAYS
    #   stripped even when its value is later judged unknown — the caller decides
    #   whether the value satisfies tier 2, but the bare model is what gets used
    #   everywhere regardless.
    # ASSUMES: a single "#" separator; an empty token after "#" (e.g. "model#")
    #   yields raw_suffix None (nothing to parse) while still stripping the "#".
    # SECURITY (log injection): the bare model string is logged verbatim as
    #   `model=%s` on every req line (grep-stable, NOT %r — awk/grep forensics key
    #   on `model=gpt-5.6-sol`). An inbound model carrying control characters —
    #   e.g. `"gpt-5.6-sol\r\nFAKE LOG#low"` (reviewer probe) — would otherwise
    #   inject a forged newline-delimited log line. We scrub C0/DEL control chars
    #   (\x00-\x1f, \x7f) and strip surrounding whitespace from the BARE model
    #   before returning, so no model string can break the one-line-per-request
    #   contract. Normal slugs contain none of these bytes and pass through
    #   byte-identical.
    bare_raw, _, raw = model.partition("#") if "#" in model else (model, "", "")
    bare = _SCRUB_CTRL_RE.sub("", bare_raw).strip()
    if "#" not in model:
        return bare, None
    raw = raw.strip().lower()
    return bare, (raw or None)


def _normalize_effort_value(raw, source):
    # v1.2.2: validate one raw effort token for a given precedence source.
    # INTENT: return a backend-acceptable effort string, or None if this tier's
    #   value is unusable (caller falls through to the next tier).
    # REASONING: identity for anything in the gpt-5.6 accepted set; clamp for a
    #   recognized-but-unsupported-for-gpt-5.6 alias (log the clamp once); None
    #   (with one WARNING) for anything genuinely unknown so the tier is ignored.
    # ASSUMES: `raw` is already lowercased/stripped by the caller (both the slug
    #   parser and output_config path normalize before calling). A non-string raw
    #   is treated as unknown.
    if not isinstance(raw, str) or not raw:
        # FIX 2: a non-string (e.g. output_config.effort=123) or empty/whitespace-
        # only value is malformed. Log one WARNING (parity with the unknown-string
        # branch below) so it leaves an audit trail, then fall through.
        log.warning("reasoning effort %r (%s) is not a usable string; ignoring this tier",
                    raw, source)
        return None
    if raw in _EFFORT_SUPPORTED:
        return raw
    if raw in _EFFORT_CLAMP:
        clamped = _EFFORT_CLAMP[raw]
        log.warning("reasoning effort %r (%s) not supported for gpt-5.6; clamped to %r",
                    raw, source, clamped)
        return clamped
    log.warning("reasoning effort %r (%s) unrecognized; ignoring this tier", raw, source)
    return None


def _resolve_effort(body, slug_effort_raw):
    # v1.2.2: resolve reasoning.effort by the four-tier precedence chain.
    # INTENT: return (effort_value, source) where source is one of
    #   "inbound" | "slug" | "env" | "default". The value is ALWAYS a supported
    #   string (the payload now always carries reasoning.effort).
    # REASONING (tier order, first present-and-valid wins):
    #   1. inbound per-request signal:
    #        a. output_config.effort (string) — Claude Code's per-request level;
    #        b. thinking:{"type":"disabled"} — an explicit request to disable
    #           reasoning -> the minimum value (_EFFORT_DISABLED = "none").
    #      thinking:{"type":"adaptive"} is NOT a level (tier 1 absent -> fall
    #      through). If output_config.effort is present its value takes precedence
    #      over a disabled-thinking signal (an explicit level beats a toggle).
    #   2. slug "#<effort>" suffix (already parsed by the caller).
    #   3. SHIM_REASONING_EFFORT env var.
    #   4. default "high".
    # ASSUMES: a malformed value at ANY tier is ignored (not fatal) and we fall
    #   through — _normalize_effort_value logs the one warning. The default is
    #   always supported so the chain always terminates with a valid value.
    #
    # FIX 1 (v1.2.3): DEMOTE an inbound output_config.effort of exactly "high".
    # INTENT: skip tier 1 (fall through to slug/env/default) whenever the inbound
    #   per-request effort normalizes to "high", treating that value as the client's
    #   PINNED CONSTANT rather than a user choice.
    # REASONING: live-observed (shim.log 1377-1416, real GPT session 2026-07-12)
    #   that Claude Code v2.1.187 pins output_config.effort="high" on EVERY request
    #   for unknown/custom slugs — the effort capability is model-ID-pattern-gated
    #   (docs-verified), so a slug the client doesn't recognize as effort-capable
    #   gets the hardcoded default "high" on every turn. With tier 1 honoring that,
    #   the /model effort UI was INERT for GPT slugs (every line logged
    #   effort=high:inbound) and the slug/env tiers were dead in practice. Demoting
    #   exactly "high" reactivates the #<effort> slug suffix and SHIM_REASONING_EFFORT
    #   as the real steering surfaces for GPT sessions.
    # CONSEQUENCE (intentional, documented): a user who DELIBERATELY selects "high"
    #   in the /model UI is now indistinguishable from the pinned constant — both
    #   fall through. This is acceptable because (a) the pinned "high" is
    #   indistinguishable on the wire from a deliberate one, and (b) the fall-through
    #   default is itself "high" (posture parity with DAAF Claude sessions), so a
    #   user wanting "high" still gets it unless a slug/env tier overrides — which is
    #   exactly the steering we are restoring. To pin a non-default level, users
    #   steer via the #<effort> slug suffix or SHIM_REASONING_EFFORT.
    # NO WARNING: this fires on essentially every request, so logging here would
    #   flood the log. It is silent by design; the effort=<value>:<source> field on
    #   the req line already reports which tier actually supplied the value (an
    #   inbound-high request with no slug/env now logs effort=high:default).
    # SCOPE: ONLY exactly "high" is demoted. All OTHER inbound values keep tier-1
    #   status — low/medium/xhigh/max are honored, thinking:{"type":"disabled"}->none
    #   is unchanged, and a malformed/unknown inbound value still warns+falls through
    #   via _normalize_effort_value below.
    # ASSUMES: the pin value is literally "high" (verified in shim.log 1377-1416).
    #   If a future client pins a different constant, this guard needs to track it.
    oc = body.get("output_config")
    if isinstance(oc, dict) and oc.get("effort") is not None:
        raw = oc.get("effort")
        raw = raw.strip().lower() if isinstance(raw, str) else raw
        if raw == "high":
            # Pinned client constant — skip tier 1, fall through (no warning).
            pass
        else:
            val = _normalize_effort_value(raw, "inbound")
            if val is not None:
                return val, "inbound"
    # Explicit disabled-thinking -> minimum reasoning (only if no usable
    # output_config.effort above). adaptive/other thinking types are not levels.
    # v1.2.3 co-occurrence note: when inbound output_config.effort=="high" (the
    #   demoted pin) AND thinking:{"type":"disabled"} are BOTH present, the demoted
    #   high falls through to here and this branch wins -> ("none","inbound"); an
    #   honored (non-"high") inbound level would have returned above and never
    #   reached this toggle (explicit level beats the disable toggle).
    thinking = body.get("thinking")
    if isinstance(thinking, dict) and thinking.get("type") == "disabled":
        return _EFFORT_DISABLED, "inbound"

    # Tier 2: slug suffix.
    if slug_effort_raw is not None:
        val = _normalize_effort_value(slug_effort_raw, "slug")
        if val is not None:
            return val, "slug"

    # Tier 3: env var.
    if SHIM_REASONING_EFFORT is not None:
        val = _normalize_effort_value(SHIM_REASONING_EFFORT.strip().lower(), "env")
        if val is not None:
            return val, "env"

    # Tier 4: default.
    return _EFFORT_DEFAULT, "default"


def _map_model(model):
    # INTENT: pass the model slug through unchanged by default so a proxy
    # receives e.g. "openai/gpt-5.6-sol". Optionally strip a prefix for direct
    # api.openai.com use where the slug is bare "gpt-5.6-sol".
    # NOTE (v1.2.2): callers strip any "#<effort>" suffix via _split_effort_suffix
    #   BEFORE this function, so `model` here is already suffix-free. Prefix
    #   stripping is independent of effort-suffix stripping.
    if SHIM_STRIP_MODEL_PREFIX and model.startswith(SHIM_STRIP_MODEL_PREFIX):
        return model[len(SHIM_STRIP_MODEL_PREFIX):]
    return model


def _system_to_text(system):
    # Anthropic `system` may be a plain string OR an array of content blocks,
    # each of which may carry a `cache_control` field. The Responses API has no
    # cache_control concept, so we flatten to text and drop cache_control. The
    # flattened text becomes the top-level `instructions` string (NOT a system
    # message inside input[]).
    if system is None:
        return None
    if isinstance(system, str):
        return system
    parts = []
    for block in system:
        if isinstance(block, dict):
            if block.get("type", "text") == "text":
                parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(p for p in parts if p)


_IMAGE_MEDIA_TYPES = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp",
})
# v1.4.8: one flat character class plus at most two trailing "=" (callers also
# require len % 4 == 0, which together equal strict RFC 4648 padding). The earlier
# repeated 4-character group was slow on multi-megabyte PDF payloads.
_BASE64_IMAGE_RE = re.compile(r"[A-Za-z0-9+/]*={0,2}")
_CONTENT_LABEL_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _content_label(value):
    # Content errors may identify only structural coordinates and type labels. Keep
    # arbitrary request text, URLs, file IDs, and image bytes structurally unreachable.
    if not isinstance(value, str) or not value:
        return "unknown"
    return _CONTENT_LABEL_RE.sub("_", value)[:40] or "unknown"


def _content_error(message_index, block_index, role, block_type, reason):
    return _InvalidRequestError(
        "message %d block %s role %s type %s: %s" % (
            message_index, block_index, _content_label(role),
            _content_label(block_type), reason,
        )
    )


def _image_to_responses_part(block, message_index, block_index, role):
    # INTENT: translate visual bytes without inspecting, decoding, or logging them.
    # REASONING: MIME prefixes come only from an exact allowlist; strict RFC-4648
    #   syntax is checked with a bounded-character regex so validation never creates
    #   a second decoded image copy. GIF is accepted syntactically; this stdlib-only
    #   shim does not claim animated-GIF detection, so the later live lane smoke is
    #   the release gate for each provider endpoint.
    if role != "user":
        raise _content_error(
            message_index, block_index, role, "image",
            "assistant/history images are unsupported",
        )
    source = block.get("source")
    if not isinstance(source, dict):
        raise _content_error(
            message_index, block_index, role, "image", "invalid image source",
        )
    source_type = source.get("type")
    if source_type == "base64":
        media_type = source.get("media_type")
        data = source.get("data")
        if media_type not in _IMAGE_MEDIA_TYPES:
            raise _content_error(
                message_index, block_index, role, "image",
                "unsupported image media type",
            )
        if (
            not isinstance(data, str)
            or not data
            or len(data) % 4 != 0
            or _BASE64_IMAGE_RE.fullmatch(data) is None
        ):
            raise _content_error(
                message_index, block_index, role, "image", "invalid base64 image data",
            )
        return {
            "type": "input_image",
            "image_url": "data:%s;base64,%s" % (media_type, data),
            "detail": "auto",
        }
    if source_type == "url":
        url = source.get("url")
        valid = isinstance(url, str) and bool(url) and not any(
            char.isspace() or ord(char) < 0x20 or ord(char) == 0x7f
            for char in url
        ) and "\\" not in url
        if valid:
            try:
                parsed = urllib.parse.urlsplit(url)
                valid = (
                    parsed.scheme.lower() in {"http", "https"}
                    and bool(parsed.netloc)
                    and bool(parsed.hostname)
                    and parsed.username is None
                    and parsed.password is None
                )
                if valid:
                    parsed.port  # force invalid-port validation
            except (TypeError, ValueError):
                valid = False
        if not valid:
            raise _content_error(
                message_index, block_index, role, "image", "invalid image URL",
            )
        return {"type": "input_image", "image_url": url, "detail": "auto"}
    if source_type == "file":
        raise _content_error(
            message_index, block_index, role, "image",
            "provider-scoped file image sources are unsupported",
        )
    raise _content_error(
        message_index, block_index, role, "image", "unsupported image source type",
    )


# v1.4.8: variants already reported, so each omitted-document kind logs once.
_DOCUMENT_OMIT_LOGGED = set()
_WARNED_ONCE = set()


def _warn_once(key, message, *args):
    # v1.4.8: one WARNING per process per degradation kind (search tolerance), so a
    # long session that repeats the same request shape does not flood shim.log.
    if key not in _WARNED_ONCE:
        _WARNED_ONCE.add(key)
        log.warning(message, *args)


def _document_to_responses_parts(block, role):
    # INTENT: translate an Anthropic `document` block into Responses content parts.
    #   These arrive when a PDF is attached directly to a message or a client sends
    #   document blocks (Claude Code's Read tool renders PDF pages as text + images
    #   instead). The block stays in history, so a hard 400 here would break every
    #   later turn of the session.
    # REASONING: Responses accepts PDFs as input_file with either a base64 data URL
    #   in file_data (plus a filename) or a file_url, per
    #   https://developers.openai.com/api/docs/guides/file-inputs (fetched
    #   2026-10-12). Text documents become plain text. Anything else degrades to a
    #   short note rather than an error. Title/context are optional Anthropic
    #   fields; citations has no Responses equivalent and is dropped.
    # ASSUMES: content is never logged; only a bounded source-type label is.
    text_type = "output_text" if role == "assistant" else "input_text"
    source = block.get("source")
    source_type = source.get("type") if isinstance(source, dict) else None
    header = []
    for key, label in (("title", "Document title"), ("context", "Document context")):
        if isinstance(block.get(key), str) and block[key]:
            header.append("%s: %s" % (label, block[key]))
    header = "\n".join(header)

    if source_type == "text" and isinstance(source.get("data"), str):
        text = (header + "\n\n" if header else "") + source["data"]
        return [{"type": text_type, "text": text}]
    if (source_type == "content" and isinstance(source.get("content"), list)
            and all(isinstance(c, dict) and c.get("type") == "text"
                    and isinstance(c.get("text"), str) for c in source["content"])):
        text = "\n".join(c["text"] for c in source["content"])
        return [{"type": text_type, "text": (header + "\n\n" if header else "") + text}]

    file_part = None
    if role != "assistant" and SHIM_PDF_MODE == "file":
        if source_type == "base64" and source.get("media_type") == "application/pdf":
            data = source.get("data")
            if (isinstance(data, str) and data and len(data) % 4 == 0
                    and _BASE64_IMAGE_RE.fullmatch(data) is not None):
                file_part = {"type": "input_file", "filename": "document.pdf",
                             "file_data": "data:application/pdf;base64," + data}
        elif source_type == "url":
            # Same strict check as consulted search URLs: http(s) with a host, no
            # userinfo, a valid port, no whitespace/control characters. Anything else
            # degrades to the note below instead of a backend 400.
            try:
                file_part = {"type": "input_file", "file_url": _search_url(source.get("url"))}
            except _ProtocolError:
                file_part = None
    if file_part is not None:
        return ([{"type": text_type, "text": header}] if header else []) + [file_part]

    variant = "%s/%s" % (
        _content_label(source_type),
        _content_label(source.get("media_type")) if isinstance(source, dict) else "none",
    )
    if variant not in _DOCUMENT_OMIT_LOGGED:
        _DOCUMENT_OMIT_LOGGED.add(variant)
        log.info("document block omitted (variant=%s, pdf_mode=%s); content not forwarded",
                 variant, SHIM_PDF_MODE)
    if (SHIM_PDF_MODE == "omit" and role != "assistant" and source_type in ("base64", "url")
            and (source_type == "url" or source.get("media_type") == "application/pdf")):
        note = ("[A PDF attachment was omitted by shim configuration "
                "(SHIM_PDF_MODE=omit) and was not sent to this model.]")
    else:
        note = ("[A document attachment (type %s) could not be passed to this model "
                "and was omitted.]" % variant)
    return [{"type": text_type, "text": (header + "\n" if header else "") + note}]


def _tool_result_output(tr_content, message_index, block_index, role):
    # Preserve the historical string output for text-only results. The Responses
    # function-call output item-list form is used only when an image or (v1.4.8) a
    # PDF input_file is present.
    # Other container/scalar types are malformed Anthropic history, not values to
    # serialize opportunistically into a backend function-call output.
    if isinstance(tr_content, str):
        return tr_content
    if not isinstance(tr_content, list):
        raise _content_error(
            message_index, block_index, role, "tool_result",
            "content must be a string or list (got %s)" % _content_label(
                type(tr_content).__name__
            ),
        )
    parts = []
    flat_text = []
    saw_image = False
    for sub_index, sub in enumerate(tr_content):
        nested_index = "%d.%d" % (block_index, sub_index)
        if isinstance(sub, str):
            text = sub
            parts.append({"type": "input_text", "text": text})
            flat_text.append(text)
            continue
        if not isinstance(sub, dict):
            raise _content_error(
                message_index, nested_index, role, "non_object",
                "unsupported tool-result content block",
            )
        sub_type = sub.get("type")
        if sub_type == "text":
            text = sub.get("text", "")
            if not isinstance(text, str):
                raise _content_error(
                    message_index, nested_index, role, "text", "invalid text block",
                )
            parts.append({"type": "input_text", "text": text})
            flat_text.append(text)
        elif sub_type == "image":
            saw_image = True
            parts.append(_image_to_responses_part(
                sub, message_index, nested_index, role,
            ))
        elif sub_type == "document":
            # v1.4.8: a PDF input_file needs the item-list output form, exactly
            # like an image: function_call_output.output may be "an array of content
            # outputs (text, image, file)", per
            # https://developers.openai.com/api/reference/python/resources/responses
            # (fetched 2026-10-12).
            # Text-only translations stay in the historical flat string.
            for part in _document_to_responses_parts(sub, role):
                parts.append(part)
                if part["type"] == "input_text":
                    flat_text.append(part["text"])
                else:
                    saw_image = True
        else:
            raise _content_error(
                message_index, nested_index, role, sub_type,
                "unsupported tool-result content block",
            )
    return parts if saw_image else "\n".join(flat_text)


def _messages_to_input(messages):
    # Translate in source order. User text/images remain adjacent content parts;
    # assistant tool replay keeps reasoning-cache injection immediately before calls.
    # Prevalidate complete groups before emitting any input, once per occurrence.
    replay_plan, replay_covered = _SEARCH_REPLAY.plan(messages)
    input_items = []
    injected_reasoning_ids = set()
    missing_reasoning = 0
    # v1.3.4 (V4-R6): per-request reasoning-cache hits (parallel to missing_reasoning),
    # surfaced on the terminal record and used to feed the process-cumulative /health
    # counters via _bump_reasoning_hit_counters at each hit.
    reasoning_cache_hits = 0
    # v1.3.4 (V4-R1): track restored (disk-loaded) reasoning material injected this
    # request. reasoning-item ids for the strip (R3), call_ids for the eviction (R4).
    injected_restored_reasoning_ids = set()
    injected_restored_call_ids = set()

    for message_index, message in enumerate(messages):
        role = message.get("role")
        # v1.2.13: fold role:"system" messages to user-role input. Live Claude
        # Code appends a system-role message to `messages`; pre-v1.2.12 code
        # mapped every non-assistant role to user and that behavior is proven
        # against the live Codex backend, so system reuses it verbatim rather
        # than inventing untested native system/developer-role translation.
        # ORDERING DEPENDENCY: the request-validation gauntlet checks RAW roles
        # and pre-rejects system-role messages carrying tool_use/tool_result;
        # this fold runs after it, so the post-fold tool checks below never see
        # them. Callers must not invoke this translator without that gauntlet.
        if role == "system":
            role = "user"
        if role not in ("user", "assistant"):
            raise _InvalidRequestError(
                "message %d role invalid: expected user or assistant" % message_index
            )
        content = message.get("content", "")
        if isinstance(content, str):
            input_items.append({
                **({"type": "message"} if role == "assistant" else {}),
                "role": "assistant" if role == "assistant" else "user",
                "content": [{
                    "type": "output_text" if role == "assistant" else "input_text",
                    "text": content,
                }],
            })
            continue

        pending_parts = []

        def flush_message_parts():
            if not pending_parts:
                return
            input_items.append({
                **({"type": "message"} if role == "assistant" else {}),
                "role": "assistant" if role == "assistant" else "user",
                "content": list(pending_parts),
            })
            pending_parts.clear()

        for block_index, block in enumerate(content):
            key = (message_index, block_index)
            if key in replay_plan:
                flush_message_parts()
                input_items.extend(replay_plan[key])
            if key in replay_covered:
                continue
            if not isinstance(block, dict):
                raise _content_error(
                    message_index, block_index, role, "non_object",
                    "unsupported content block",
                )
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "")
                if not isinstance(text, str):
                    raise _content_error(
                        message_index, block_index, role, "text", "invalid text block",
                    )
                pending_parts.append({
                    "type": "output_text" if role == "assistant" else "input_text",
                    "text": text,
                })
            elif block_type == "image":
                pending_parts.append(_image_to_responses_part(
                    block, message_index, block_index, role,
                ))
            elif block_type == "document":
                # v1.4.8: PDFs/text documents (e.g. a directly attached PDF). Never 400s.
                pending_parts.extend(_document_to_responses_parts(block, role))
            elif block_type in {"thinking", "redacted_thinking"}:
                # Known Claude continuity blocks are intentionally consumed rather
                # than forwarded. Encrypted Responses reasoning cache entries, not
                # replayed Anthropic thinking prose/signatures, preserve continuity.
                continue
            elif block_type == "tool_use":
                if role != "assistant":
                    raise _content_error(
                        message_index, block_index, role, "tool_use",
                        "tool_use is permitted only in assistant messages",
                    )
                flush_message_parts()
                call_id = block.get("id", "")
                cached = _REASONING_CACHE.get(call_id)
                if cached is not None:
                    # v1.3.4 (V4-R6/R7): count this hit for the terminal record (per-request)
                    # and the /health restore-effectiveness counters (process-cumulative). The
                    # hit above used .get() — never move_to_end — so counting stays read-only
                    # and adds no LRU mutation / persist / write amplification. The restored
                    # flag reads the SAME membership V4-R1's tracking below keys off; the set
                    # is not mutated within this translation, so the two reads agree.
                    reasoning_cache_hits += 1
                    _bump_reasoning_hit_counters(call_id in _REASONING_CACHE_RESTORED_IDS)
                    reasoning_id = cached.get("id")
                    if reasoning_id not in injected_reasoning_ids:
                        input_items.append(cached)
                        injected_reasoning_ids.add(reasoning_id)
                    # v1.3.4 (V4-R1): if this call_id's blob came from disk, record its
                    # reasoning-item id (for the strip) and call_id (for the eviction). The
                    # reasoning item is guaranteed present in input_items here — appended by
                    # this hit or an earlier one sharing the same id — so recording its id
                    # for a possible strip is always valid. reasoning_id must be truthy so a
                    # malformed id-less item cannot broaden the strip to every id-less item.
                    if reasoning_id and call_id in _REASONING_CACHE_RESTORED_IDS:
                        injected_restored_reasoning_ids.add(reasoning_id)
                        injected_restored_call_ids.add(call_id)
                else:
                    missing_reasoning += 1
                input_items.append({
                    "type": "function_call",
                    "call_id": call_id,
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                })
            elif block_type == "tool_result":
                if role != "user":
                    raise _content_error(
                        message_index, block_index, role, "tool_result",
                        "tool_result is permitted only in user messages",
                    )
                flush_message_parts()
                input_items.append({
                    "type": "function_call_output",
                    "call_id": block.get("tool_use_id", ""),
                    "output": _tool_result_output(
                        block.get("content", ""), message_index, block_index, role,
                    ),
                })
            else:
                raise _content_error(
                    message_index, block_index, role, block_type,
                    "unsupported content block",
                )
        flush_message_parts()

    return (
        input_items, missing_reasoning, reasoning_cache_hits,
        injected_restored_reasoning_ids, injected_restored_call_ids,
    )


class _ToolRegistry:
    """Request-local declaration types; names alone never imply hosted execution.

    Source-backed controls: allowed_domains and approximate location (pinned
    Codex ToolSpec / OpenAI SDK, 2026-09-06). Fixtures do not live-certify these
    controls. Subscription max_uses is ONLY a shim-observed call ceiling, not an
    upstream execution, billing, internal-query or quota guarantee. OpenAI's
    max_tool_calls separately bounds total built-in calls, not exact searches.
    """

    def __init__(self, tools, choice=None):
        self.tools = []
        self.declared = tools is not None
        self.kinds = {}
        self.search_name = None
        self.max_uses = None
        self.forced_search = False
        # v1.4.8: lowercase bare domains to remove from projected search results on a
        # lane that cannot exclude them upstream (ChatGPT/Codex). Empty = no filter.
        self.blocked_domains = []
        self.choice = None
        self.parallel = None
        if tools is None:
            tools = []
        if not isinstance(tools, list):
            raise _InvalidRequestError("tools must be a list")
        for tool in tools:
            if not isinstance(tool, dict):
                raise _InvalidRequestError("tool declaration must be an object")
            name = tool.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
                raise _InvalidRequestError("tool declaration has an invalid name")
            if name in self.kinds:
                raise _InvalidRequestError("duplicate or ambiguous tool names")
            kind = tool.get("type", "custom")
            # v1.4.8: accept every dated server-search version (web_search_YYYYMMDD),
            # so a Claude Code update that bumps the tool version keeps working.
            if isinstance(kind, str) and re.fullmatch(r"web_search_[0-9]{8}", kind):
                if name != "web_search" or self.search_name is not None:
                    raise _InvalidRequestError("server search requires the unique name web_search")
                allowed = {"type", "name", "max_uses", "allowed_domains", "blocked_domains", "user_location"}
                # Unknown options still fail closed: an unrecognized key could be a
                # restriction we would otherwise silently widen.
                if set(tool) - allowed:
                    raise _InvalidRequestError("unsupported server search option")
                limit = tool.get("max_uses")
                if "max_uses" in tool and (type(limit) is not int or not 1 <= limit <= 100):
                    raise _InvalidRequestError("server search max_uses must be an integer from 1 to 100")
                self.max_uses = limit
                self.search_name = name
                hosted = {"type": "web_search", "external_web_access": True}
                domain_re = (r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
                             r"[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
                if "allowed_domains" in tool:
                    domains = tool["allowed_domains"]
                    # Reject paths/schemes/wildcards rather than silently widening a restriction.
                    if (not isinstance(domains, list) or len(domains) > 100
                            or any(not isinstance(d, str) or len(d) > 253
                                   or not re.fullmatch(domain_re, d) for d in domains)):
                        raise _InvalidRequestError("allowed_domains requires bare DNS domains; paths are unsupported")
                    if len({d.lower() for d in domains}) != len(domains):
                        raise _InvalidRequestError("duplicate allowed_domains")
                    # An empty allowlist is the client's no-filter representation;
                    # omit the upstream filter rather than sending an ambiguous [].
                    if domains:
                        hosted["filters"] = {"allowed_domains": list(domains)}
                if "blocked_domains" in tool:
                    blocked = tool["blocked_domains"]
                    if not isinstance(blocked, list) or any(not isinstance(d, str) or not d for d in blocked):
                        raise _InvalidRequestError("blocked_domains must be a list of domains")
                    # v1.4.8: the OpenAI web-search guide documents filters.blocked_domains
                    # (up to 100 bare domains; https://developers.openai.com/api/docs/guides/
                    # tools-web-search, fetched 2026-10-12), so the openai lane maps it.
                    # The ChatGPT/Codex backend's support is unestablished (its pinned
                    # ToolSpec has allowed_domains only), and an unknown filter key could
                    # 400 upstream, so that lane, or any list that is not bare domains,
                    # drops the exclusion with a WARNING instead of failing the turn.
                    # An empty list stays a silent no-op (v1.4.1).
                    if blocked:
                        # Valid bare domains, deduplicated case-insensitively (first
                        # spelling kept, in order); everything else counts as invalid.
                        well_formed = [d for d in blocked
                                       if len(d) <= 253 and re.fullmatch(domain_re, d)]
                        invalid = len(blocked) - len(well_formed)
                        valid, seen_domains = [], set()
                        for d in well_formed:
                            if d.lower() not in seen_domains:
                                seen_domains.add(d.lower())
                                valid.append(d)
                        if SHIM_BACKEND_MODE == "openai":
                            # Partial lists still forward their valid part (max 100).
                            forwarded = valid[:100]
                            if forwarded:
                                hosted.setdefault("filters", {})["blocked_domains"] = forwarded
                            dropped = invalid + len(valid) - len(forwarded)
                            if dropped:
                                # Logged per request (not once): each drop widens that
                                # search. Count only; domains are never logged.
                                log.warning("server search: dropped %d blocked_domains "
                                            "entries (not bare domains, or over the 100 "
                                            "limit); the remaining %d are applied",
                                            dropped, len(forwarded))
                        else:
                            # The ChatGPT/Codex backend cannot take the exclusion, so
                            # honour it after the search: sources and citations on a
                            # blocked host are removed from the projected result.
                            self.blocked_domains = [d.lower() for d in valid]
                            log.warning("server search: backend=%s cannot exclude domains "
                                        "during search; %d blocked_domains entries are "
                                        "filtered from results afterwards%s",
                                        SHIM_BACKEND_MODE, len(valid),
                                        " (%d invalid entries ignored)" % invalid
                                        if invalid else "")
                if "user_location" in tool:
                    location = tool["user_location"]
                    if (not isinstance(location, dict)
                            or location.get("type") != "approximate"
                            or set(location) - {"type", "city", "region", "country", "timezone"}):
                        raise _InvalidRequestError("unsupported server search user_location")
                    for key, value in location.items():
                        if (not isinstance(value, str) or not 1 <= len(value) <= 200
                                or any(ord(char) < 32 or ord(char) == 127 for char in value)):
                            raise _InvalidRequestError("invalid server search location field")
                    if "country" in location and not re.fullmatch(r"[A-Z]{2}", location["country"]):
                        raise _InvalidRequestError("location country requires a two-letter uppercase code")
                    if "timezone" in location:
                        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
                        try:
                            ZoneInfo(location["timezone"])
                        except (ValueError, ZoneInfoNotFoundError):
                            raise _InvalidRequestError("location timezone requires an IANA zone") from None
                    hosted["user_location"] = dict(location)
                self.kinds[name] = "server_search"
                self.tools.append(hosted)
            elif kind == "custom":
                schema = tool.get("input_schema", {"type": "object", "properties": {}})
                if not isinstance(schema, dict) or not isinstance(tool.get("description", ""), str):
                    raise _InvalidRequestError("invalid function tool schema or description")
                self.kinds[name] = "function"
                self.tools.append({"type": "function", "name": name,
                                   "description": tool.get("description", ""),
                                   "parameters": schema})
            else:
                raise _InvalidRequestError("unsupported tool declaration type or version")
        if choice is None:
            return
        if (not isinstance(choice, dict)
                or set(choice) - {"type", "name", "disable_parallel_tool_use"}):
            raise _InvalidRequestError("unsupported tool_choice")
        if "disable_parallel_tool_use" in choice:
            if type(choice["disable_parallel_tool_use"]) is not bool:
                raise _InvalidRequestError("disable_parallel_tool_use must be boolean")
            # v1.4.8: map the same way with or without hosted search. The flag
            # governs parallel tool calls in general; how it interacts with hosted
            # search calls is the provider's documented parallel_tool_calls behavior.
            self.parallel = not choice["disable_parallel_tool_use"]
        choice_type = choice.get("type")
        if choice_type not in ("auto", "any", "none", "tool"):
            raise _InvalidRequestError("unsupported tool_choice type")
        if choice_type != "tool" and "name" in choice:
            raise _InvalidRequestError("tool_choice name requires type tool")
        if choice_type == "tool":
            name = choice.get("name")
            if not isinstance(name, str) or name not in self.kinds:
                raise _InvalidRequestError("tool_choice names an undeclared tool")
            if self.kinds[name] == "server_search":
                if len(self.tools) != 1:
                    raise _InvalidRequestError("forced server search with mixed tools is not established")
                self.choice = "required"
                self.forced_search = True
            else:
                self.choice = {"type": "function", "name": name}
        else:
            if choice_type == "any" and not self.tools:
                raise _InvalidRequestError("required tool_choice needs a declaration")
            self.choice = "required" if choice_type == "any" else choice_type
            self.forced_search = bool(self.search_name and len(self.tools) == 1 and choice_type == "any")

    def apply(self, payload):
        if self.tools or self.declared:
            payload["tools"] = self.tools
        if self.choice is not None:
            payload["tool_choice"] = self.choice
        if self.parallel is not None:
            payload["parallel_tool_calls"] = self.parallel
        if self.search_name:
            payload["include"].append("web_search_call.action.sources")
            if self.max_uses is not None and SHIM_BACKEND_MODE == "openai":
                payload["max_tool_calls"] = self.max_uses


def _tools_to_responses(tools):
    return _ToolRegistry(tools).tools or None


def _anthropic_to_responses_request(
        body, bare_model, slug_effort_raw, requested_service_tier=None, registry=None):
    # Build the OpenAI Responses payload from an Anthropic Messages body.
    # Returns (payload, missing_reasoning_count, reasoning_cache_hits, effort_value,
    #   effort_source, injected_restored_reasoning_ids, injected_restored_call_ids).
    #   v1.3.4 (V4-R1): the two restored-id sets are plumbed to the request state so the
    #   retry loops' stale-blob 400 insurance can strip/evict exactly the disk-restored
    #   blobs. v1.3.4 (V4-R6): reasoning_cache_hits is the per-request cache-hit count for
    #   the terminal record (parallel to missing_reasoning).
    # v1.2.2: `bare_model` is the inbound model with any "#<effort>" suffix already
    # stripped (by _split_effort_suffix in the caller); `slug_effort_raw` is that
    # stripped suffix's raw token (tier 2). The suffix-free model is what reaches
    # the backend — a "#"-bearing model is never forwarded.
    if registry is None:
        registry = _ToolRegistry(body.get("tools"), body.get("tool_choice"))
    input_items, missing_reasoning, reasoning_cache_hits, \
        injected_restored_reasoning_ids, injected_restored_call_ids = \
        _messages_to_input(body.get("messages", []))

    payload = {
        "model": _map_model(bare_model),
        "input": input_items,
        # PRIVACY POSTURE: never persist server-side. Combined with `include`
        # below this is the stateless / Zero-Data-Retention mode.
        "store": False,
        # REASONING CONTINUITY: request the encrypted reasoning blob so the
        # reasoning cache receives it under store:false. Without this, reasoning
        # items returned under store:false carry no encrypted_content and cannot
        # be re-injected (the API 404s on a bare reasoning id when store:false).
        "include": ["reasoning.encrypted_content"],
    }
    # Only the locally validated Fast/Priority path supplies the canonical wire value.
    # Ordinary requests and every noncanonical value omit the field; retries reuse this
    # same payload and never downgrade it. In particular DAAF never emits raw `fast`.
    if requested_service_tier == "priority":
        payload["service_tier"] = "priority"

    # system -> top-level `instructions` (NOT a system message in input[]).
    system_text = _system_to_text(body.get("system"))
    if system_text:
        payload["instructions"] = system_text

    # max_tokens (Anthropic, REQUIRED on every request) -> max_output_tokens.
    # INTENT: forward the client's generation ceiling, CLAMPED to OpenAI's
    #   documented minimum of 16.
    # REASONING: the Responses key is `max_output_tokens`; truncation surfaces as
    #   status:"incomplete" (spec file 04 §1, §3). The inbound Anthropic contract
    #   is untouched — we still READ `max_tokens` from the client.
    # FIX 2 (v1.2.3): clamp to max(16, value). Live-observed (real GPT session
    #   2026-07-12) that on a /model switch Claude Code sent a probe request with
    #   max_tokens:1, which OpenAI rejected with a verbatim
    #   400 invalid_request_error on param max_output_tokens:
    #   "Expected a value >= 16, but got 1" (shim.log 02:06:41 + 02:07:26). That
    #   rejection blocked /model switching TO GPT slugs in the UI. The origin of
    #   the client's max_tokens=1 model-switch probe is UNDOCUMENTED (noted as
    #   such — observed behavior, not a spec'd contract). Clamping the outbound
    #   floor to 16 (OpenAI's documented minimum, quoted above) lets the probe
    #   succeed without altering any legitimate larger ceiling.
    # v1.2.5: the Codex (chatgpt-lane) backend REJECTS max_output_tokens with a
    # verbatim 400 "Unsupported parameter: max_output_tokens" (live-observed
    # 2026-07-15, smoke 30) — it is NOT in the notes/08 ablation body floor. The
    # api.openai.com (openai-lane) backend REQUIRES/accepts it (v1.2.3 FIX 2 clamp).
    # So the field is lane-conditional: emit it (clamped) in openai mode; OMIT it
    # entirely in chatgpt mode. The client's max_tokens contract is untouched — we
    # still read it; in chatgpt mode the backend applies its own output ceiling.
    # ASSUMES: dropping the ceiling in chatgpt mode is acceptable — real Claude Code
    #   sessions send max_tokens=32000 (a soft cap, not a truncation goal), and the
    #   Codex backend enforces its own limits. If a hard client-side ceiling is ever
    #   needed on this lane, it must be expressed via a parameter the backend accepts.
    if body.get("max_tokens") is not None and SHIM_BACKEND_MODE != "chatgpt":
        payload["max_output_tokens"] = max(16, body["max_tokens"])

    # temperature and top_p: DROPPED UNCONDITIONALLY — never forwarded.
    # REASONING: gpt-5.x reasoning models REJECT any non-default temperature/top_p
    #   with a 400 while reasoning is active ("Only the default (1) value is
    #   supported"), spec file 04 §5. raine/claude-code-proxy omits them entirely;
    #   auth2api forwards temperature, which is a latent bug for reasoning models
    #   (notes file 05 §3b). We follow raine. We do NOT even read body["temperature"]
    #   / body["top_p"] into the payload — the safest approach is to never send them.

    # reasoning object: always request an auto summary so we can surface a
    # thinking block, and (v1.2.2) ALWAYS set effort via the precedence resolver.
    # REASONING: prior to v1.2.2 effort was set only when SHIM_REASONING_EFFORT was
    #   present, letting the backend default ("medium" for gpt-5.6) apply. v1.2.2
    #   resolves an effort value on every request (inbound > slug > env > default
    #   "high") so the outbound payload always carries reasoning.effort — posture
    #   parity with DAAF Claude sessions and full per-request control. The summary
    #   is still requested unconditionally so the thinking block is available at
    #   any effort level (raine requests summary:"auto" only when effort is set,
    #   notes file 05 §3e; we are stricter for reliable thinking surfacing).
    effort_value, effort_source = _resolve_effort(body, slug_effort_raw)
    # Effort floor: GPT-6 Astra and (v1.4.9) GPT-6.1 Sol reject effort:"none" (see
    # the _NO_NONE_EFFORT_SLUGS note). Comments below say "Astra"; the same rule
    # applies to every member of that set.
    # INTENT: for an Astra-family request whose resolved effort is "none" (e.g. an
    #   inbound thinking:{"type":"disabled"} or a "#none" slug suffix), rewrite to
    #   "low" — the lowest Astra-supported level — so the backend does not 400.
    # REASONING: this is the ONLY model-conditional branch in the effort path; it
    #   runs after the general four-tier resolver and touches Astra alone. Every
    #   other model forwards its resolved effort unchanged. `bare_model` already has
    #   the "#<effort>" suffix stripped (by _split_effort_suffix in the caller); we
    #   additionally drop any provider prefix (e.g. "openai/") to compare the
    #   terminal slug. The effort_source is left as-is so the per-request log still
    #   reports which tier supplied the (pre-clamp) value.
    # ASSUMES: Astra's supported enum is {low, medium, high, xhigh, max} (primary
    #   source, 2026-09-05). If Astra later accepts "none", delete this branch.
    _terminal_slug = bare_model.rsplit("/", 1)[-1].strip().lower()
    if _terminal_slug in _NO_NONE_EFFORT_SLUGS and effort_value == "none":
        log.warning("reasoning effort 'none' not supported for %s; clamped to 'low'",
                    _terminal_slug)
        effort_value = "low"
    reasoning_obj = {"summary": "auto", "effort": effort_value}
    payload["reasoning"] = reasoning_obj

    # v1.2.4: ALWAYS carry response verbosity. text:{"verbosity": V} where V is the
    # startup-resolved SHIM_TEXT_VERBOSITY (default "medium").
    # REASONING: verbosity is a whole-session posture (no inbound per-request signal
    #   exists on the Anthropic wire), so it is resolved once at startup and applied
    #   uniformly. text.verbosity is live-confirmed accepted by gpt-5.6-sol on
    #   /v1/responses (high/low HTTP 200, probe live_tests/18). Sent unconditionally
    #   for the same reason effort is: posture parity with DAAF Claude sessions.
    payload["text"] = {"verbosity": SHIM_TEXT_VERBOSITY}

    registry.apply(payload)

    # `thinking`, `output_config`, `metadata`, `stream` (handled by transport),
    # and any unknown fields are intentionally dropped — output_config is an
    # Anthropic-inbound-only signal (its effort was consumed into reasoning.effort
    # above) and MUST NOT be forwarded to OpenAI.
    return (
        payload, missing_reasoning, reasoning_cache_hits, effort_value, effort_source,
        injected_restored_reasoning_ids, injected_restored_call_ids,
    )


# --- Native search: bounded completed-item inventory and process-local replay ---
# Fixed bounds, not new environment/configuration contracts. The cache is intentionally
# process-local: eviction, age expiry and restart cause explicit continuity errors.
_SEARCH_MAX_BYTES = 2 * 1024 * 1024
_SEARCH_MAX_ITEMS = 128
_SEARCH_MAX_EVENTS = 4096
_SEARCH_MAX_ERROR_BYTES = 64 * 1024
# Separate raw-input and projected-content budgets: citation titles may be reused
# across many consulted sources. Never silently truncate evidence to fit these caps.
_SEARCH_MAX_PROJECTED_BYTES = 2 * 1024 * 1024
_SEARCH_MAX_SOURCES = 1024
_SEARCH_MAX_TITLE_CHARS = 4096
_SEARCH_REPLAY_MAX_BYTES = 8 * 1024 * 1024
_SEARCH_REPLAY_MAX_GROUPS = 128
_SEARCH_REPLAY_TTL = 1800
# A bounded resident cache alone does not bound expansion of repeated historical
# occurrences. These per-request ceilings are checked before decoding any group.
_SEARCH_REPLAY_REQUEST_MAX_BYTES = 8 * 1024 * 1024
_SEARCH_REPLAY_REQUEST_MAX_ITEMS = 1024
_SEARCH_REPLAY_REQUEST_MAX_GROUPS = 128


def _search_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _search_json_size(value, limit):
    """Count canonical ASCII JSON bytes without serializing amplified objects.

    The iterator stack visits shared values once per occurrence (the wire will
    repeat them too), but never builds a flattened traversal or encoded string.
    This matches _search_json's separators/ensure_ascii policy, not provider units.
    """
    size = 0
    stack = [iter((value,))]
    while stack:
        try:
            part = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if isinstance(part, str):
            size += 2
            for char in part:
                point = ord(char)
                size += (2 if char in '\"\\\\\b\f\n\r\t' else
                         6 if point < 32 or 126 < point <= 65535 else
                         12 if point > 65535 else 1)
                if size > limit:
                    raise _ProtocolError("search projected content exceeded byte limit")
        elif isinstance(part, dict):
            size += 2 + max(0, len(part) - 1) + len(part)
            if any(not isinstance(key, str) for key in part):
                raise _ProtocolError("search projection contains invalid object keys")
            stack.append(iter(component for pair in part.items() for component in pair))
        elif isinstance(part, (list, tuple)):
            size += 2 + max(0, len(part) - 1)
            stack.append(iter(part))
        elif part is None:
            size += 4
        elif isinstance(part, bool):
            size += 4 if part else 5
        elif isinstance(part, (int, float)):
            size += len(json.dumps(part))
        else:
            raise _ProtocolError("search projection contains invalid JSON values")
        if size > limit:
            raise _ProtocolError("search projected content exceeded byte limit")
    return size


class _SearchProjectionList(list):
    """Budget a growing projected array before any full JSON serialization."""
    def __init__(self):
        super().__init__()
        self.json_bytes = 2

    def append(self, value):
        remaining = _SEARCH_MAX_PROJECTED_BYTES - self.json_bytes - bool(self)
        size = _search_json_size(value, remaining)
        self.json_bytes += size + bool(self)
        super().append(value)


class _SearchReplayCache:
    def __init__(self):
        self.groups = OrderedDict()
        self.bytes = 0
        self.lock = threading.RLock()

    def _prune(self):
        now = time.monotonic()
        for key in list(self.groups):
            entry = self.groups[key]
            if now - entry[0] > _SEARCH_REPLAY_TTL:
                self.bytes -= entry[3]
                del self.groups[key]

    def put(self, token, raw_items, blocks):
        import hashlib
        _search_json_size(blocks, _SEARCH_MAX_PROJECTED_BYTES)
        raw = _search_json(raw_items)
        fingerprints = tuple(hashlib.sha256(_search_json(b)).digest() for b in blocks)
        size = len(raw) + len(fingerprints) * 32
        if size > _SEARCH_MAX_BYTES:
            raise _ProtocolError("search replay group exceeded byte limit")
        # The first hosted reference anchors the whole emitted sequence, including
        # any preceding thinking blocks. Later results/citations never re-inject it.
        first = next(i for i, b in enumerate(blocks) if b["type"] == "server_tool_use")
        refs = frozenset(b["id"] for b in blocks if b["type"] == "server_tool_use")
        with self.lock:
            self._prune()
            while self.groups and (len(self.groups) >= _SEARCH_REPLAY_MAX_GROUPS
                                   or self.bytes + size > _SEARCH_REPLAY_MAX_BYTES):
                _, old = self.groups.popitem(last=False)
                self.bytes -= old[3]
            if size > _SEARCH_REPLAY_MAX_BYTES or _SEARCH_REPLAY_MAX_GROUPS < 1:
                raise _ProtocolError("search replay cache capacity exceeded")
            self.groups[token] = (time.monotonic(), raw, fingerprints, size, first, refs, len(raw_items))
            self.bytes += size

    def plan(self, messages):
        import hashlib
        planned, covered = {}, set()
        # Snapshot immutable entry references at request start, under a short lock.
        # Expiry/eviction after this snapshot applies to the next request. Hashing
        # and JSON decoding must not monopolize the shared cache's critical section.
        with self.lock:
            self._prune()
            available = dict(self.groups)
        expanded_bytes = expanded_items = 0
        for mi, message in enumerate(messages):
            blocks = message.get("content")
            if not isinstance(blocks, list):
                continue
            for bi, block in enumerate(blocks):
                if (mi, bi) in covered or not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind not in ("server_tool_use", "web_search_tool_result"):
                    continue
                if message.get("role") != "assistant":
                    raise _InvalidRequestError("search replay blocks require assistant role")
                ref = block.get("id") if kind == "server_tool_use" else block.get("tool_use_id")
                match = re.fullmatch(r"srvtoolu_shim_([0-9a-f]{32})_[0-9]+", ref or "") if isinstance(ref, str) else None
                entry = available.get(match[1]) if match else None
                if entry is None:
                    raise _InvalidRequestError("search replay missing or expired; restart/eviction requires a fresh search")
                if ref not in entry[5] or kind != "server_tool_use":
                    raise _InvalidRequestError("search replay sequence is incomplete or modified")
                start = bi - entry[4]
                end = start + len(entry[2])
                if (start < 0 or end > len(blocks)
                        or any((mi, i) in covered for i in range(start, end))):
                    raise _InvalidRequestError("search replay sequence is incomplete or modified")
                expanded_bytes += len(entry[1])
                expanded_items += entry[6]
                if (expanded_bytes > _SEARCH_REPLAY_REQUEST_MAX_BYTES
                        or expanded_items > _SEARCH_REPLAY_REQUEST_MAX_ITEMS
                        or len(planned) >= _SEARCH_REPLAY_REQUEST_MAX_GROUPS):
                    raise _InvalidRequestError("search replay request expansion exceeded limit")
                planned[(mi, start)] = entry
                covered.update((mi, i) for i in range(start, end))
        # All occurrence budgets pass before any decoding. Then validate every
        # complete emitted sequence before constructing independent raw occurrences.
        for (mi, start), entry in planned.items():
            blocks = messages[mi]["content"]
            end = start + len(entry[2])
            observed = tuple(hashlib.sha256(_search_json(blocks[i])).digest() for i in range(start, end))
            if observed != entry[2]:
                raise _InvalidRequestError("search replay sequence is incomplete or modified")
        plan = {key: json.loads(entry[1]) for key, entry in planned.items()}
        return plan, covered


_SEARCH_REPLAY = _SearchReplayCache()


class _SearchCollector:
    """Strict search-only inventory. Completed items, not deltas, are replay evidence."""
    def __init__(self, registry):
        self.registry = registry
        self.ids = {}
        self.indexes = {}
        self.types = {}
        self.function_calls = {}  # index -> (call_id, name); never alters raw items
        self.call_indexes = {}
        self.added = {}
        self.completed = {}
        # Display-only fallback for ordinary truncation after search history.
        # These deltas never enter completed inventory or hosted-search replay.
        self.partial_text = {}
        self.search_ids = set()
        self.events = 0
        self.retained_bytes = 0
        self.terminal = None

    def _identity(self, index, item_id, item_type=None, call_id=None):
        if type(index) is not int or not 0 <= index < _SEARCH_MAX_ITEMS:
            raise _ProtocolError("search output index missing or out of bounds")
        if item_id is None and item_type == "function_call":
            # Internal tagged identity cannot collide with a provider string id.
            # A done-only/JSON function may expose only call_id. The caller first
            # validates uniqueness and consistency; raw replay objects stay intact.
            _require_protocol_string(call_id, "function call id")
            item_id = self.indexes.get(index, ("function_call", call_id))
        else:
            _require_protocol_string(item_id, "search inventory item id")
        if ((index in self.indexes and self.indexes[index] != item_id)
                or (item_id in self.ids and self.ids[item_id] != index)):
            raise _ProtocolError("search inventory identity conflict")
        if item_type is not None:
            if item_id in self.types and self.types[item_id] != item_type:
                raise _ProtocolError("search inventory item type changed")
            self.types[item_id] = item_type
        self.ids[item_id] = index
        self.indexes[index] = item_id
        if item_type == "web_search_call":
            self.search_ids.add(item_id)
            if self.registry.choice == "none":
                raise _ProtocolError("backend searched despite tool_choice none")
            if self.registry.max_uses is not None and len(self.search_ids) > self.registry.max_uses:
                raise _ProtocolError("shim-observed search-call ceiling exceeded; upstream work may already have occurred")

    def event(self, event):
        self.events += 1
        if self.events > _SEARCH_MAX_EVENTS:
            raise _ProtocolError("search event count exceeded limit")
        kind = _validate_stream_event_fields(event)
        if kind in ("response.output_item.added", "response.output_item.done"):
            item = event["item"]
            index = event.get("output_index")
            if item.get("type") == "function_call":
                # INTENT: preserve optional-id wire compatibility without ambiguous
                # matching. REASONING: index, call_id and name are one association.
                # ASSUMES: shared validation already checked function string fields.
                call_id = item["call_id"]
                identity = (call_id, item["name"])
                registered = self.call_indexes.get(call_id)
                if index is None and registered is not None:
                    index = registered
                if (type(index) is not int or not 0 <= index < _SEARCH_MAX_ITEMS
                        or (registered is not None and registered != index)
                        or (index in self.function_calls and self.function_calls[index] != identity)):
                    raise _ProtocolError("search function identity conflict")
                self.function_calls[index] = identity
                self.call_indexes[call_id] = index
            if kind.endswith("done") and item.get("type") == "web_search_call":
                # Validate/log each unique completed inventory item before generic
                # status rejection. Repeated identical done events do not double-count.
                if type(index) is not int or index not in self.completed:
                    _validate_hosted_action(item, observe=True)
            self._identity(index, item.get("id"), item.get("type"), item.get("call_id"))
            if kind.endswith("done"):
                # Defer ordinary partial-item status to the terminal boundary.
                # Historical search replay is not evidence of a search this turn.
                allowed_statuses = ("completed", "incomplete") if not self.registry.search_name else ("completed",)
                if "status" in item and item["status"] not in allowed_statuses:
                    raise _ProtocolError("search inventory item was not completed")
                if item.get("type") == "message" and (item.get("role") != "assistant" or item.get("status") not in allowed_statuses):
                    raise _ProtocolError("search message role/status is invalid")
                if index in self.added and json.loads(self.added[index])["type"] != item["type"]:
                    raise _ProtocolError("search inventory item type changed")
            destination = self.added if kind.endswith("added") else self.completed
            raw = _search_json(item)
            if index in destination:
                if destination[index] != raw:
                    raise _ProtocolError("search completed/added item conflict")
            else:
                self.retained_bytes += len(raw)
                if self.retained_bytes > _SEARCH_MAX_BYTES:
                    raise _ProtocolError("search retained inventory exceeded byte limit")
                destination[index] = raw
        elif "item_id" in event:
            self._identity(event.get("output_index"), event["item_id"],
                           "web_search_call" if kind.startswith("response.web_search_call.") else None)
        if kind == "response.output_text.delta" and not self.registry.search_name:
            # INTENT: retain ordinary text for an incomplete terminal lacking items.
            # REASONING: replay history selects this collector even without a new
            # search. Completed/terminal output remains authoritative when present.
            # ASSUMES: explicit item/part identities associate the observed deltas;
            # ambiguous identities fail closed rather than manufacture attribution.
            index = event.get("output_index")
            part = event.get("content_index")
            self._identity(index, event.get("item_id"), "message")
            if type(part) is not int or not 0 <= part < _SEARCH_MAX_ITEMS:
                raise _ProtocolError("ordinary partial text index missing or out of bounds")
            self.retained_bytes += len(_search_json(event["delta"]))
            if self.retained_bytes > _SEARCH_MAX_BYTES:
                raise _ProtocolError("search retained inventory exceeded byte limit")
            self.partial_text.setdefault((index, part), []).append(event["delta"])
        if kind in ("response.failed", "error"):
            details = event.get("response") or event.get("error") or event
            _, message, _, _ = _normalize_backend_error(details, phase="upstream_stream")
            raise _ProtocolError(message)
        if kind in ("response.completed", "response.incomplete"):
            terminal = _validate_terminal_response(kind, event.get("response"))
            if (kind == "response.incomplete" and not self.registry.search_name
                    and not self.search_ids and terminal.get("error") is None):
                # Ordinary continuation after replay: terminal partial output is
                # authoritative; no hosted success or replay group is manufactured.
                # Existing ordinary conversion maps incomplete to max_tokens.
                if terminal.get("output"):
                    indexed_partial = dict(enumerate(terminal["output"]))
                else:
                    indexed_partial = {i: json.loads(raw) for i, raw in self.completed.items()}
                    if self.partial_text:
                        # INTENT: reconcile ordinary display output per item, not
                        # per response. A completed reasoning prefix cannot replace
                        # the text of a different unfinished message.
                        # ASSUMES: all observed output identities cover a contiguous
                        # prefix; unfinished non-text items supply no invented text.
                        if set(self.indexes) != set(range(len(self.indexes))):
                            raise _ProtocolError("ordinary partial text has incomplete index coverage")
                        for index in sorted({i for i, _ in self.partial_text}):
                            if index in indexed_partial:
                                continue  # This item's done content is authoritative.
                            # Local incomplete display only, never completed replay.
                            indexed_partial[index] = {
                                "type": "message", "id": self.indexes[index],
                                "role": "assistant", "status": "incomplete",
                                "content": [{"type": "output_text", "text": "".join(chunks)}
                                            for (output_index, _), chunks in sorted(self.partial_text.items())
                                            if output_index == index]}
                for index, item in sorted(indexed_partial.items()):
                    _validate_output_item(item)
                    if item.get("type") == "web_search_call":
                        raise _ProtocolError("unexpected hosted search in ordinary continuation")
                    self._identity(index, item.get("id"), item.get("type"), item.get("call_id"))
                    if index in self.completed and json.loads(self.completed[index]) != item:
                        raise _ProtocolError("ordinary terminal inventory conflicts with done items")
                partial = [item for _, item in sorted(indexed_partial.items())]
                if (len(partial) > _SEARCH_MAX_ITEMS or len(_search_json(partial)) > _SEARCH_MAX_BYTES):
                    raise _ProtocolError("search output exceeded aggregate limit")
                self.terminal = {**terminal, "output": partial}
                return self.terminal
            if kind != "response.completed" or terminal.get("error") is not None:
                raise _ProtocolError("search response did not complete successfully")
            if any(json.loads(raw).get("status", "completed") != "completed" for raw in self.completed.values()):
                raise _ProtocolError("search inventory item was not completed")
            if set(self.completed) != set(self.indexes) or set(self.indexes) != set(range(len(self.indexes))):
                raise _ProtocolError("search inventory missing completed items or index coverage")
            items = [json.loads(self.completed[i]) for i in range(len(self.completed))]
            # Shared validation intentionally treats absent/null output like [].
            # Coverage and byte-identical nonempty reconciliation stay mandatory.
            terminal_items = terminal.get("output") or []
            if terminal_items and terminal_items != items:
                raise _ProtocolError("search terminal inventory conflicts with completed items")
            self.terminal = {**terminal, "output": items}
            return self.terminal
        return None


class _BoundedSearchStream:
    """Narrow MIME fallback plus whole-body bound before the existing SSE iterator."""
    def __init__(self, response):
        self.response = response

    async def aiter_bytes(self):
        total = 0
        prefix = bytearray()
        mime = self.response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        recognized = mime == "text/event-stream"
        if mime in ("text/html", "application/json"):
            raise _ProtocolError("search expected SSE, received non-stream content")
        async for chunk in self.response.aiter_bytes():
            total += len(chunk)
            if total > _SEARCH_MAX_BYTES:
                raise _ProtocolError("search stream exceeded aggregate byte limit")
            if not recognized:
                prefix.extend(chunk)
                # Non-SSE MIME fallback needs a real bounded response SSE
                # preamble. Never scan past HTML, JSON, whitespace or challenge text.
                if len(prefix) < 32 and b"\n" not in prefix:
                    continue
                if not (prefix.startswith(b"event: response.") or prefix.startswith(b'data: {"type":"response.')
                        or prefix.startswith(b'data: {"type": "response.')):
                    raise _ProtocolError("search stream has no recognized SSE response prefix")
                recognized = True
                yield bytes(prefix)
                prefix.clear()
            else:
                yield chunk
        if not recognized:
            raise _ProtocolError("search stream has no recognized SSE response prefix")


async def _collect_search_response(resp, disconnect_event, registry, json_mode=False,
                                   reject_refusals=False):
    collector = _SearchCollector(registry)
    if json_mode:
        raw = bytearray()
        iterator = resp.aiter_bytes().__aiter__()
        while True:
            try:
                chunk = await _await_or_disconnect(iterator.__anext__(), disconnect_event)
            except StopAsyncIteration:
                break
            if len(raw) + len(chunk) > _SEARCH_MAX_BYTES:
                raise _ProtocolError("search JSON exceeded aggregate byte limit")
            raw.extend(chunk)
        try:
            response = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise _ProtocolError("search response contained malformed JSON") from None
        response = _validate_response_for_conversion(response)
        items = response.get("output")
        if not isinstance(items, list):
            raise _ProtocolError("search terminal output must be a list")
        # JSON transport supplies the actual completed inventory in one object.
        # Reuse the inventory validator; these internal events are not wire evidence.
        for index, item in enumerate(items):
            collector.event({"type": "response.output_item.done", "output_index": index, "item": item})
        return collector.event({"type": "response." + response["status"], "response": response})
    async for raw in _iter_bounded_sse_data(_BoundedSearchStream(resp), disconnect_event):
        if raw.strip() == b"[DONE]":
            break
        try:
            event = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise _ProtocolError("search stream contained malformed SSE JSON") from None
        # Optional guard runs before history truncation can drop done evidence.
        # Ordinary streaming never uses this buffered collection path.
        if reject_refusals:
            _reject_buffered_refusal_event(event)
        terminal = collector.event(event)
        if terminal is not None:
            return terminal
    raise _ProtocolError("search stream ended without a successful terminal response")


def _search_url(value):
    if not isinstance(value, str) or len(value) > 8192 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise _ProtocolError("search source URL is invalid")
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
        parsed.port
    except ValueError:
        raise _ProtocolError("search source URL is invalid") from None
    return value


def _search_source_ok(source):
    # v1.4.8: one consulted source is projectable only as a typed URL with an
    # optional string title. Anything else is skipped (never raised) by callers.
    if not isinstance(source, dict) or source.get("type") != "url":
        return False
    try:
        _search_url(source.get("url"))
    except _ProtocolError:
        return False
    return not ("title" in source and source["title"] is not None
                and not isinstance(source["title"], str))


def _validate_hosted_action(item, observe=False):
    """Validate documented action evidence; diagnostics never contain provider text.

    Returns the action dict, or None when the action's SHAPE is unrecognized and the
    item should be skipped (v1.4.8). WHY the split: a non-completed or invalid status
    is a protocol state the collector also enforces, so it still raises; an unknown
    action type, missing evidence or an odd field is just content we cannot render.
    Skipping such an item is safe because the raw item stays in the replay
    inventory unchanged and it carries no client tool ID (function-call pairing and
    inventory identity/coverage checks live elsewhere and are untouched).
    """
    action = item.get("action")
    kind = action.get("type") if isinstance(action, dict) else None
    action_type = kind if isinstance(kind, str) and kind in ("search", "open_page", "find_in_page") else "unknown"
    status = item.get("status")
    action_status = status if isinstance(status, str) and status in ("in_progress", "searching", "completed", "failed", "incomplete") else "unknown"
    outcome, evidence, source_count = "malformed", "absent", 0
    try:
        if action_status == "unknown":
            raise _ProtocolError("hosted action status is invalid")
        if status != "completed":
            outcome = "not_completed"
            raise _ProtocolError("hosted action did not complete successfully")
        if not isinstance(action, dict) or not isinstance(kind, str) or not kind:
            return None
        if action_type == "unknown":
            outcome = "unsupported"
            return None
        if kind == "search":
            for key in ("query", "queries"):
                if key not in action:
                    continue
                value = action[key]
                if key == "query" and not isinstance(value, str):
                    return None
                if key == "queries" and (not isinstance(value, list) or any(not isinstance(q, str) for q in value)):
                    return None
            sources = action.get("sources")
            if not isinstance(sources, list):
                # Absent or malformed sources: skipping is more truthful than
                # projecting an empty (zero-result) search the provider never reported.
                outcome = "missing_evidence" if "sources" not in action or sources is None else "malformed"
                return None
            source_count = sum(1 for source in sources if _search_source_ok(source))
            evidence = "sources"
            if sources and not source_count:
                # v1.4.8: the provider listed sources but none is usable. Projecting
                # an empty result list would claim the search found nothing; skip it.
                outcome = "malformed"
                return None
            outcome = "valid" if source_count else "zero_results"
        else:
            # INTENT: retain page actions as actions, never synthetic searches.
            # REASONING: pinned OpenAPI + SDK specify optional nullable open URL,
            # but require both URL and pattern for find. No source list is defined.
            # ASSUMES (v1.4.8): extra fields are ignored (projection copies only the
            # known keys); a find without a valid pattern/URL is skipped.
            if kind == "find_in_page" and ("pattern" not in action or "url" not in action):
                outcome = "missing_evidence"
                return None
            if kind == "find_in_page" and not isinstance(action["pattern"], str):
                return None
            url = action.get("url")
            if kind == "find_in_page" or url is not None:
                try:
                    _search_url(url)
                except _ProtocolError:
                    return None
                evidence = "url"
            outcome = "valid" if evidence == "url" else "url_not_supplied"
        return action
    finally:
        if observe:
            # Only fixed enums and an integer derived from a bounded inventory.
            # No query, URL, pattern, title, item id, extension or ciphertext enters logs.
            _lifecycle_event("hosted_action", action_type=action_type,
                             action_status=action_status, outcome=outcome,
                             evidence=evidence, source_count=source_count)


def _search_projection(response, model, registry):
    """Keep malformed conversion failures structured and provider prose private."""
    try:
        message = _project_search_response(response, model, registry)
        hosted = [item for item in response.get("output", []) if item.get("type") == "web_search_call"]
        # v1.4.8: skipped items may lack a dict action; count them as no known type.
        kinds = [item["action"].get("type") if isinstance(item.get("action"), dict) else None
                 for item in hosted]
        _lifecycle_event("hosted_projection", outcome="valid" if hosted else "no_hosted_actions",
                         action_count=len(hosted),
                         search_count=kinds.count("search"),
                         open_page_count=kinds.count("open_page"),
                         find_in_page_count=kinds.count("find_in_page"))
        return message
    except _ProtocolError:
        _lifecycle_event("hosted_projection", outcome="protocol_error")
        raise
    except (TypeError, AttributeError, KeyError, ValueError, RecursionError):
        _lifecycle_event("hosted_projection", outcome="malformed")
        raise _ProtocolError("search response conversion failed") from None


def _project_search_response(response, model, registry):
    """Real consulted URLs and answer attribution; no proprietary-origin fields."""
    response = _validate_response_for_conversion(response)
    items = response["output"]
    if len(items) > _SEARCH_MAX_ITEMS or len(_search_json(items)) > _SEARCH_MAX_BYTES:
        raise _ProtocolError("search output exceeded aggregate limit")
    searches = [i for i in items if i.get("type") == "web_search_call"]
    if registry.forced_search and not searches:
        raise _ProtocolError("forced search returned no hosted search evidence")
    if registry.max_uses is not None and len(searches) > registry.max_uses:
        raise _ProtocolError("shim-observed search-call ceiling exceeded; upstream work may already have occurred")
    # INTENT: preserve the ordinary stream's missing-usage policy on buffered
    # transports too. REASONING: measured zero is not absent/invalid usage.
    # ASSUMES: shared validation has dropped invalid counters. Only model answer
    # text feeds the existing heuristic; consulted URLs, attribution and hosted
    # calls are NOT tokens or provider search charges manufactured by the shim.
    usage = dict(response.get("usage") or {})
    usage_estimated = "input_tokens" not in usage or "output_tokens" not in usage
    if "output_tokens" not in usage:
        answer_text = "".join(part.get("text", "") for item in items
                              if item.get("type") == "message"
                              for part in item.get("content", []) if part.get("type") == "output_text")
        usage["output_tokens"] = _estimate_tokens(answer_text)
    usage.setdefault("input_tokens", 0)
    response = {**response, "usage": usage}
    usage_source = "estimated" if usage_estimated else "backend"
    if not searches:
        message = _responses_to_anthropic(response, model)
        message["_usage_source"] = usage_source
        return message
    titles, citations = {}, []
    unverified_spans = False
    # v1.4.8: blocked_domains on a lane that cannot exclude them upstream (see
    # _ToolRegistry). A host matches when it equals a blocked domain or is one of
    # its subdomains; matching sources and citations are removed from the display.
    blocked = tuple(getattr(registry, "blocked_domains", None) or ())

    def _blocked_host(url):
        host = (urllib.parse.urlsplit(url).hostname or "").rstrip(".").lower()
        return any(host == d or host.endswith("." + d) for d in blocked)

    removed_blocked = 0

    for item in items:
        _validate_output_item(item)
        if item.get("type") == "message":
            for part in item.get("content", []):
                annotations = part.get("annotations", [])
                if not isinstance(annotations, list):
                    # v1.4.8: attribution is additive display text; an odd shape
                    # loses the citation list, not the answer.
                    _warn_once("search_annotations", "search projection: skipped "
                               "non-list annotations (citations omitted)")
                    continue
                for annotation in annotations:
                    if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                        continue
                    try:
                        _search_url(annotation.get("url"))
                    except _ProtocolError:
                        _warn_once("search_citation_url", "search projection: skipped a "
                                   "citation with an invalid URL")
                        continue
                    if blocked and _blocked_host(annotation["url"]):
                        removed_blocked += 1
                        continue
                    # INTENT: validate offsets explicitly without inventing source
                    # quotations or assuming provider Unicode indexing semantics.
                    # REASONING: our conservative local convention is a nonempty
                    # half-open range in the original output_text. Only ASCII is
                    # encoding-unambiguous across code points/UTF-8/UTF-16. For
                    # non-ASCII or malformed/missing offsets, retain the URL as a
                    # provider-linked source but label spans UNVERIFIED. Never
                    # slice, repair offsets, or modify the replay annotation.
                    # ASSUMES: titles/URLs are provider attribution, not quotations.
                    text = part.get("text") if part.get("type") == "output_text" else None
                    start, end = annotation.get("start_index"), annotation.get("end_index")
                    valid_range = (isinstance(text, str) and type(start) is int and type(end) is int
                                   and 0 <= start < end <= len(text))
                    if not valid_range or not text.isascii():
                        unverified_spans = True
                    url = annotation["url"]
                    title = annotation.get("title")
                    # v1.4.8: an unusable title falls back to the URL label.
                    if not isinstance(title, str) or len(title) > _SEARCH_MAX_TITLE_CHARS:
                        title = None
                    title = title or "URL: " + url
                    titles[url] = title
                    citations.append((title, url))
    blocks = _SearchProjectionList()
    source_count = 0
    token = uuid.uuid4().hex
    for item in items:
        kind = item.get("type")
        if kind == "reasoning":
            text = _reasoning_summary_text(item)
            if text:
                blocks.append({"type": "thinking", "thinking": text, "signature": ""})
        elif kind == "web_search_call":
            action = _validate_hosted_action(item)
            if action is None:
                # v1.4.8: unrecognized action shape. Skip this display item; the raw
                # item still replays to the provider unchanged (see the docstring).
                _warn_once("search_action_shape", "search projection: skipped a hosted "
                           "web action with an unrecognized shape (see hosted_action events)")
                continue
            if action["type"] != "search":
                # The installed WebSearch parser retains text blocks, but renders
                # web_search_tool_result arrays as ranked links. Use the existing
                # hosted tool identity as a replay anchor and text as action evidence;
                # never reinterpret a page open/find as a new search or source quote.
                ref = "srvtoolu_shim_%s_%d" % (token, len(blocks))
                # v1.4.8: copy only documented keys; extra provider fields are ignored.
                actual_input = {key: action[key] for key in ("type", "url", "pattern") if key in action}
                blocks.append({"type": "server_tool_use", "id": ref, "name": "web_search", "input": actual_input})
                url = action.get("url")
                detail = "\n\nHosted web action: " + action["type"] + " (not ranked search results)."
                if url is None:
                    detail += " URL not supplied by provider; page provenance unavailable."
                else:
                    source_count += 1
                    if source_count > _SEARCH_MAX_SOURCES:
                        raise _ProtocolError("search consulted-source count exceeded limit")
                    target = url.replace("<", "%3C").replace(">", "%3E").replace("(", "%28").replace(")", "%29")
                    detail += " Provider action URL: [page](" + target + ")."
                if action["type"] == "find_in_page":
                    detail += " Pattern: " + json.dumps(action["pattern"], ensure_ascii=True) + "."
                detail += " Action completion does not verify page content or a pattern match.\n\n"
                blocks.append({"type": "text", "text": detail})
                continue
            # _validate_hosted_action returned this action, so sources is a list and
            # query/queries (when present) are well-typed.
            sources = action["sources"]
            actual_input = {key: action[key] for key in ("query", "queries") if key in action}
            # Never invent a single query for missing/multiple upstream queries.
            if "queries" in actual_input and len(actual_input["queries"]) > 1:
                actual_input.pop("query", None)
            ref = "srvtoolu_shim_%s_%d" % (token, len(blocks))
            source_count += len(sources)
            if source_count > _SEARCH_MAX_SOURCES:
                raise _ProtocolError("search consulted-source count exceeded limit")
            results = _SearchProjectionList()
            for source in sources:
                if not _search_source_ok(source):
                    # v1.4.8: drop one unusable source, keep the rest of the search.
                    _warn_once("search_source_shape", "search projection: skipped a "
                               "consulted source with an unrecognized shape")
                    continue
                url = source["url"]
                if blocked and _blocked_host(url):
                    removed_blocked += 1
                    continue
                title = source.get("title") or titles.get(url) or "URL: " + url
                if len(title) > _SEARCH_MAX_TITLE_CHARS:
                    title = "URL: " + url
                results.append({"type": "web_search_result", "url": url, "title": title})
            blocks.append({"type": "server_tool_use", "id": ref, "name": "web_search", "input": actual_input})
            blocks.append({"type": "web_search_tool_result", "tool_use_id": ref, "content": results})
        elif kind == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text" and part.get("text"):
                    blocks.append({"type": "text", "text": part["text"]})
        elif kind == "function_call":
            try:
                arguments = json.loads(item["arguments"])
            except ValueError:
                raise _ProtocolError("search-associated function arguments are invalid") from None
            arguments, _ = _sanitize_tool_args(item["name"], arguments)
            blocks.append({"type": "tool_use", "id": item["call_id"], "name": item["name"], "input": arguments})
    if citations:
        # Explicit added attribution, never source quotations or invented ciphertext.
        # Percent-encode Markdown delimiters only in display links; replay keeps
        # original query-bearing URLs and every original annotation field unchanged.
        links = _SearchProjectionList()
        for title, url in dict.fromkeys(citations):
            label = title.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("\n", " ").replace("\r", " ")
            target = url.replace("<", "%3C").replace(">", "%3E").replace("(", "%28").replace(")", "%29")
            links.append("[%s](%s)" % (label, target))
        label = ("Provider-linked sources (text spans unverified): " if unverified_spans
                 else "Source attribution: ")
        blocks.append({"type": "text", "text": "\n\n" + label + "; ".join(links)})
    if not any(b["type"] != "thinking" for b in blocks):
        # v1.4.8: every hosted item was skipped and the model wrote no answer text.
        # Never hand Claude Code an empty message; say plainly what happened.
        blocks.append({"type": "text", "text": "[The web search ran, but its results came "
                       "back in a format this shim could not display.]"})
    if blocked and any(b["type"] == "web_search_tool_result" for b in blocks):
        # v1.4.8: tell the reader the exclusion was applied after the search.
        blocks.append({"type": "text", "text": "\n\nNote: this backend can't exclude "
                       "domains during search; results from blocked domains were "
                       "removed afterwards."})
        if removed_blocked:
            log.info("search projection: removed %d results/citations on blocked domains",
                     removed_blocked)
    usage = response.get("usage") or {}
    input_total, output_total = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    cached = _resolve_cached_tokens(usage, input_total)
    message = {"id": response.get("id") or "msg_" + uuid.uuid4().hex, "type": "message",
            "role": "assistant", "model": model, "content": blocks,
            "stop_reason": "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn",
            "stop_sequence": None, "_cached_tokens": cached, "_usage_source": usage_source,
            "usage": _anthropic_usage_block(input_total, output_total, cached, _actual_speed_from_response(response))}
    # Validate the full response before committing any replay state. A failed
    # projection must neither insert a group nor evict a prior valid occurrence.
    _search_json_size(message, _SEARCH_MAX_PROJECTED_BYTES)
    # v1.4.8: replay groups are anchored on a projected server_tool_use. If every
    # hosted item was skipped, there is nothing to anchor: the turn is delivered as
    # plain text/tool_use and later turns replay it as ordinary history.
    if any(b["type"] == "server_tool_use" for b in blocks):
        _SEARCH_REPLAY.put(token, items, blocks)
    return message


# --- Helpers: response translation (OpenAI Responses -> Anthropic) ---

class _ToolWhitespaceError(_ProtocolError):
    """Provider failed to make structural progress while forming tool arguments."""


def _check_tool_argument_whitespace(st, fragment):
    # This is an operational output bound, not a JSON grammar restriction.
    # Preserve lexical state across SSE fragments; strings may contain arbitrary
    # whitespace, escaped quotes and backslashes without counting as padding.
    inside, escaped, run = st.get("json_whitespace_state", (False, False, 0))
    for char in fragment:
        if inside:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                inside = False
            run = 0
        else:
            if char == '"':
                inside = True
            run = run + 1 if char in " \t\r\n" else 0
            if run > 256:
                raise _ToolWhitespaceError(
                    "backend tool arguments exceeded 256 consecutive whitespace "
                    "characters outside JSON strings; generation cancelled "
                    "before tool arguments completed")
    st["json_whitespace_state"] = (inside, escaped, run)


def _sanitize_tool_args(tool_name, args):
    # Evidence-based cleanup of the GPT "fill-every-optional" tool-call habit,
    # quantified in the 2026-07-09/10 GPT DAAFBench smoke battery
    # (research/2026-07-09_FrameworkDev_GPTBenchSmoke/SESSION_NOTES.md):
    #   * Read.pages == ""            — 724 occurrences; each one costs a
    #     rejected tool call + an error round-trip before the model retries.
    #   * Agent/Task isolation=<any>  — filled on essentially every dispatch;
    #     "remote" hangs the session forever (Issue #2), "worktree" runs the
    #     subagent in a stale origin/main checkout (Iteration 5). Stripped for
    #     ANY value, mirroring the block-remote-isolation.sh hook v2 policy;
    #     the hook remains the second line of defense for non-shim routes.
    #   * Bash dangerouslyDisableSandbox == false — filled on every Bash call;
    #     dropping the explicit default is a semantic no-op. A `true` fill is
    #     deliberately passed through UNTOUCHED so the harness permission
    #     layer (not this shim) decides what to do with it.
    # Deliberately NOT touched: `model` on Agent/Task — DAAF's model-selection
    # doctrine depends on legitimate tier choices, and the shim cannot tell a
    # compulsive fill from an intentional one.
    #
    # Targeted rules only — no generic empty-value stripping, because "" is a
    # legitimate value for some params (e.g. Edit.new_string deletes text).
    # Returns (args, dropped) where dropped is a list of human-readable
    # "key=value" strings for the caller to log. UNCHANGED from the chat lane.
    if not SHIM_SANITIZE_TOOLS or not isinstance(args, dict):
        return args, []
    dropped = []
    if tool_name == "Read" and args.get("pages") == "":
        del args["pages"]
        dropped.append('pages=""')
    if tool_name in ("Agent", "Task") and "isolation" in args:
        dropped.append(f"isolation={args.pop('isolation')!r}")
    if tool_name == "Bash" and args.get("dangerouslyDisableSandbox") is False:
        del args["dangerouslyDisableSandbox"]
        dropped.append("dangerouslyDisableSandbox=false")
    return args, dropped


def _validate_terminal_response(event_type, response):
    # INTENT: enforce one terminal-event/status/schema contract before any cache or
    # converter access. Both streamed translation and ChatGPT's inbound-nonstream
    # SSE accumulator call this exact validator.
    # REASONING: a terminal event name is not sufficient proof of success. The
    # embedded response status must agree exactly, and converter-facing containers
    # and token counters must have safe types. bool is rejected explicitly because
    # it is an int subclass in Python but not a valid token count.
    if event_type not in ("response.completed", "response.incomplete"):
        raise _ProtocolError("backend emitted a non-success terminal event")
    if not isinstance(response, dict):
        raise _ProtocolError("backend terminal event omitted its response object")
    expected_status = (
        "completed" if event_type == "response.completed" else "incomplete"
    )
    status = response.get("status")
    if not isinstance(status, str) or status != expected_status:
        raise _ProtocolError("backend terminal event/status mismatch")
    if (
        "output" in response
        and response["output"] is not None
        and not isinstance(response["output"], list)
    ):
        # v1.2.14 (R3.3): `output: null` is a captured Codex quirk on a completed
        # response after a tool turn. Tolerate it here (streamed/collected state is
        # the fallback source); only a non-null, non-list output is a real violation.
        raise _ProtocolError("backend terminal response output is not a list")
    if "usage" in response:
        usage = response["usage"]
        if not isinstance(usage, dict):
            # v1.2.8 wire tolerance: malformed usage must not fail a completed
            # generation. Drop it and let downstream estimation apply.
            log.warning("wire-divergence: terminal usage is not an object; dropping")
            del response["usage"]
        else:
            for field in ("input_tokens", "output_tokens"):
                if field not in usage:
                    continue
                value = usage[field]
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 0
                ):
                    log.warning(
                        "wire-divergence: terminal usage %s invalid; dropping field",
                        field,
                    )
                    del usage[field]
    return response


def _validate_response_for_conversion(response):
    # Defense in depth for the JSON/non-stream converter boundary. SSE callers
    # already validated event/status coherence; the real OpenAI non-stream lane has
    # only the response object, so infer the sole coherent terminal event from its
    # exact status and then apply the same schema validator.
    if not isinstance(response, dict):
        raise _ProtocolError("backend response is not an object")
    status = response.get("status")
    if status == "completed":
        event_type = "response.completed"
    elif status == "incomplete":
        event_type = "response.incomplete"
    else:
        raise _ProtocolError("backend response has no successful terminal status")
    return _validate_terminal_response(event_type, response)


def _require_protocol_string(value, field, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value):
        raise _ProtocolError("backend event contains an invalid %s" % field)
    return value


def _validate_output_item(item):
    # Validate converter/cache-relevant output item fields before either subsystem
    # sees the object. Unknown string item types remain forward-compatible and are
    # ignored by conversion; known types receive the strict fields they rely on.
    if not isinstance(item, dict):
        raise _ProtocolError("backend output item is not an object")
    item_type = _require_protocol_string(item.get("type"), "item type")
    if "id" in item:
        _require_protocol_string(item.get("id"), "item id")
    if item_type == "reasoning":
        summary = item.get("summary", [])
        if not isinstance(summary, list):
            raise _ProtocolError("backend reasoning summary is not a list")
        for part in summary:
            if not isinstance(part, dict):
                raise _ProtocolError("backend reasoning summary part is not an object")
            if part.get("type") == "summary_text":
                _require_protocol_string(
                    part.get("text"), "reasoning summary text", allow_empty=True
                )
    elif item_type == "message":
        content = item.get("content", [])
        if not isinstance(content, list):
            raise _ProtocolError("backend message content is not a list")
        for part in content:
            if not isinstance(part, dict):
                raise _ProtocolError("backend message content part is not an object")
            if part.get("type") == "output_text":
                _require_protocol_string(
                    part.get("text"), "output text", allow_empty=True
                )
    elif item_type == "function_call":
        # v1.2.8 wire tolerance: the item id is optional (the Codex CLI's own
        # struct models function_call id as Option<String>); a present id is
        # still validated by the generic check above.
        if "id" not in item:
            log.warning("wire-divergence: function_call item missing id (call_id=%s)",
                        _scrub_log_token(item.get("call_id")))
        _require_protocol_string(item.get("call_id"), "function call id")
        _require_protocol_string(item.get("name"), "function name")
        _require_protocol_string(
            item.get("arguments"), "function arguments", allow_empty=True
        )
    return item


def _validate_stream_event_fields(event):
    # Validate event-specific fields before the streaming state machine mutates
    # state or emits downstream bytes. This same routine also protects ChatGPT's
    # inbound-nonstream accumulator, which otherwise might ignore malformed deltas
    # that precede an apparently valid terminal object.
    if not isinstance(event, dict):
        raise _ProtocolError("backend stream contained a malformed event")
    event_type = event.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise _ProtocolError("backend stream event has no valid type")
    if event_type == "response.reasoning_summary_text.delta":
        _require_protocol_string(
            event.get("delta"), "reasoning delta", allow_empty=True
        )
        if "item_id" in event and not isinstance(event.get("item_id"), str):
            raise _ProtocolError("backend reasoning delta has an invalid item id")
    elif event_type == "response.output_text.delta":
        _require_protocol_string(event.get("delta"), "text delta", allow_empty=True)
        if "item_id" in event and not isinstance(event.get("item_id"), str):
            raise _ProtocolError("backend text delta has an invalid item id")
    elif event_type == "response.function_call_arguments.delta":
        _require_protocol_string(event.get("item_id"), "function item id")
        _require_protocol_string(
            event.get("delta"), "function argument delta", allow_empty=True
        )
        # v1.2.14 (R1): only item_id/delta are load-bearing here. Known-but-unmodeled
        # extra fields (e.g. the live `obfuscation` string the Codex backend attaches
        # to arguments.delta) are tolerated by design — validated-when-present is not
        # required, and they are deliberately NOT counted as unknown wire (too noisy
        # to flag a benign per-delta field).
    elif event_type == "response.function_call_arguments.done":
        _require_protocol_string(event.get("item_id"), "function item id")
        # v1.2.8 wire tolerance: the public API documents name/arguments on this
        # event, but the Codex backend's own client never consumes it, so no live
        # pressure guarantees their presence. Validate when present; the handler
        # falls back to state captured at output_item.added (name) and to the
        # buffered delta stream (arguments) when absent.
        if "name" in event:
            _require_protocol_string(event.get("name"), "function name")
        else:
            _record_wire_divergence("arguments.done_missing_name")
        if "arguments" in event:
            _require_protocol_string(
                event.get("arguments"), "function arguments", allow_empty=True
            )
        else:
            log.warning("wire-divergence: arguments.done missing arguments (item %s)",
                        _scrub_log_token(event.get("item_id")))
    elif event_type == "response.output_item.added":
        item = event.get("item")
        if not isinstance(item, dict):
            raise _ProtocolError("backend output_item.added item is not an object")
        item_type = _require_protocol_string(item.get("type"), "item type")
        if "id" in item:
            _require_protocol_string(item.get("id"), "item id")
        if item_type == "function_call":
            _require_protocol_string(item.get("id"), "function item id")
            _require_protocol_string(item.get("call_id"), "function call id")
            _require_protocol_string(item.get("name"), "function name")
    elif event_type == "response.output_item.done":
        _validate_output_item(event.get("item"))
    return event_type


def _stop_reason_from_status(status, saw_tool_use):
    # Responses status -> Anthropic stop_reason.
    # INTENT/REASONING: incomplete (any incomplete status, regardless of
    #   incomplete_details.reason) -> "max_tokens"; else a function_call was
    #   emitted -> "tool_use"; else "end_turn". Ported from raine
    #   (reducer.rs:678-683) and auth2api (responses-translator.ts:519), which
    #   both map ANY incomplete to truncation and do not switch on the specific
    #   incomplete_details.reason string (which is inconsistently documented as
    #   "max_output_tokens" vs "max_tokens"). Notes file 05 §3d.
    if status == "incomplete":
        return "max_tokens"
    if saw_tool_use:
        return "tool_use"
    return "end_turn"


def _reasoning_summary_text(reasoning_item):
    # Concatenate the summary_text parts of a reasoning item into one string.
    # INTENT: the reasoning item's `summary` is an array of {type:"summary_text",
    #   text:...} parts; join them for the non-streaming thinking block.
    # v1.2.6: only the chatgpt lane synthesizes paragraph boundaries. Preserve each
    # source string byte-for-byte, ignore only exactly-empty strings when deciding
    # where separators belong, and retain whitespace-only strings as real content.
    # The openai lane deliberately keeps the legacy empty-string join unchanged.
    parts = []
    for s in (reasoning_item.get("summary") or []):
        if isinstance(s, dict) and s.get("type") == "summary_text":
            text = s.get("text", "")
            if SHIM_BACKEND_MODE != "chatgpt" or text != "":
                parts.append(text)
    separator = "\n\n" if SHIM_BACKEND_MODE == "chatgpt" else ""
    return separator.join(parts)


def _estimate_tokens(text):
    # Rough char/4 heuristic used only when the backend omits usage.
    return max(1, len(text) // 4)


# --- v1.2.1: self-calibrating count_tokens estimator ---
# INTENT: Claude Code enforces its LOCAL context-window budget by POSTing the
#   whole request envelope to {base_url}/v1/messages/count_tokens and treating the
#   returned input_tokens as the turn's size. The pre-v1.2.1 estimator returned
#   len(raw_json_body)//4 — it counted the ENTIRE serialized Anthropic envelope
#   (23 tool schemas, JSON key names, brace/quote/backslash escaping), not the
#   natural-language text a real tokenizer sees. Live-measured 2026-07-11 that
#   over-counts realistic Claude Code envelopes by ~1.6-1.9x (diag scripts 03/04).
#   Combined with Claude Code assuming a ~200K window for unknown model slugs,
#   GPT sessions died client-side ("Prompt is too long") at ~9% of the real
#   1,050,000 window. This estimator instead learns the true bytes->tokens ratio
#   from the backend's own reported usage and applies a deliberate LOW bias.
# REASONING: we cannot run the real GPT tokenizer here (stdlib+httpx+uvicorn
#   only), but every non-count_tokens request already round-trips through the
#   backend, which reports usage.input_tokens for a request whose inbound
#   Anthropic body size we know exactly. The ratio real_input_tokens/body_bytes
#   is the empirical calibration; an EMA tracks it with recency weighting so it
#   adapts to the session's actual envelope shape (tool count, system size).
# ASSUMES: the count_tokens envelope is structurally similar (per byte) to the
#   /v1/messages envelopes that feed the EMA — true in practice, both are the
#   same Claude Code request shape. Calibration is process-local (resets on
#   restart); the seed prior covers cold start. A single global ratio is
#   sufficient — Claude Code only needs a whole-session budget signal, not a
#   per-request-exact count.
#
# Seed prior = 1/4.6 tokens-per-byte. Live-measured realistic envelopes ran
#   ~1/4.4 to 1/7.7 bytes-per-token (i.e. 0.13-0.23 tokens-per-byte); the prior
#   deliberately sits on the LOW (conservative-under-estimate) side of that band.
_COUNT_RATIO_PRIOR = 1.0 / 4.6      # tokens per inbound-body byte (seed)
_COUNT_EMA_ALPHA = 0.3              # recency weight for new observations
_COUNT_LOW_BIAS = 0.9              # deliberate under-estimate factor (see below)
# INTENT: sane acceptance band (tokens-per-byte) for a calibration observation.
# REASONING: live-measured realistic envelopes run ~0.13-0.23 tokens/byte; the
#   band is set deliberately WIDE (0.02 .. 1.0) so it never rejects a legitimate
#   envelope shape, only the pathological ones. The lower edge (0.02 = 1 token
#   per 50 bytes) is far below any real natural-language-in-JSON density; the
#   upper edge (1.0 = 1 token per byte) is the theoretical ceiling for byte-
#   dense text and above anything a real tokenizer produces on our envelopes.
#   An observation outside the band is a corrupt pairing (e.g. a backend usage
#   number that doesn't correspond to this inbound body — the reproduced poison
#   was input_tokens=999999999 against a ~10-byte body => ratio ~3e7) and must be
#   dropped, not folded into the EMA, so it can never permanently poison the ratio.
_COUNT_RATIO_MIN = 0.02            # reject observations below this (tokens/byte)
_COUNT_RATIO_MAX = 1.0             # reject observations above this (tokens/byte)
_count_ratio_state = {"ratio": _COUNT_RATIO_PRIOR, "obs": 0}


def _calibrate_count_ratio(real_input_tokens, body_bytes):
    # INTENT: fold one (real_input_tokens, inbound_body_bytes) observation into
    #   the EMA of tokens-per-byte. Called after every successful backend response
    #   (streaming and non-streaming) where the backend reported input_tokens.
    # REASONING: EMA (alpha=0.3) is recent-weighted so the ratio tracks the live
    #   session's envelope shape without a single outlier dominating. The guard set
    #   is layered: (1) type guard drops non-numeric inputs; (2) domain guard drops
    #   missing/zero bytes and non-positive or NaN tokens; (3) an acceptance-band
    #   guard drops any obs_ratio outside _COUNT_RATIO_MIN.._COUNT_RATIO_MAX. Only
    #   an observation clearing all three updates the EMA and the obs count, so a
    #   pathologically large usage number (the reproduced ratio-poisoning case)
    #   can never corrupt the ratio, and no single observation can push count_tokens
    #   permanently out of a sane range.
    # ASSUMES: real_input_tokens is the backend's own count for a request whose
    #   inbound Anthropic body was body_bytes long. A cache-populated turn still
    #   pairs one usage number with one inbound body, which is exactly the ratio
    #   count_tokens needs to reproduce.
    try:
        rt = float(real_input_tokens)
        bb = float(body_bytes)
    except (TypeError, ValueError):
        return
    if not (rt > 0) or not (bb > 0) or rt != rt or bb != bb:  # rt!=rt catches NaN
        return
    obs_ratio = rt / bb
    if obs_ratio < _COUNT_RATIO_MIN or obs_ratio > _COUNT_RATIO_MAX:
        # Pathological observation (e.g. a backend usage number that doesn't match
        # this inbound body). Skip it entirely — do NOT update the EMA or the obs
        # count — so a single corrupt pairing can never permanently poison the ratio.
        log.warning("count_tokens calibration rejected ratio=%.4g", obs_ratio)
        return
    st = _count_ratio_state
    prev_obs = st["obs"]
    if prev_obs == 0:
        # First real observation replaces the seed prior outright, then EMA takes
        # over. Blending the very first obs with the seed would bias the ratio
        # toward the (arbitrary) prior for several turns.
        st["ratio"] = obs_ratio
    else:
        st["ratio"] = (_COUNT_EMA_ALPHA * obs_ratio
                       + (1.0 - _COUNT_EMA_ALPHA) * st["ratio"])
    st["obs"] = prev_obs + 1
    if prev_obs == 0:
        # Log ONCE when the EMA first moves off the prior; thereafter stay quiet.
        log.info("count_tokens calibrated ratio=%.4f obs=%d", st["ratio"], st["obs"])


def _count_tokens_estimate(body_bytes):
    # INTENT: estimate a request's real input_tokens for Claude Code's local
    #   budget from the calibrated tokens-per-byte ratio, with a deliberate LOW
    #   bias. Floor at 1 so a well-formed response always carries a positive count.
    # REASONING: the 0.9 LOW-bias factor is intentional and asymmetric. An
    #   UNDER-estimate at worst lets an oversized request reach the backend, which
    #   then fails LOUDLY with the v1.1.1 backend-error diagnostics (visible,
    #   recoverable). An OVER-estimate causes Claude Code to end the session
    #   client-side prematurely and SILENTLY — exactly today's incident. Given the
    #   asymmetry, we bias low on purpose. The calibrated ratio already tracks the
    #   truth; the 0.9 is headroom against the count_tokens envelope running a
    #   touch heavier per byte than the average /v1/messages envelope.
    # ASSUMES: body_bytes is the raw inbound count_tokens body length. A degenerate
    #   ratio (shouldn't happen — guarded on write) still yields >=1 via the floor.
    try:
        est = int(float(body_bytes) * _count_ratio_state["ratio"] * _COUNT_LOW_BIAS)
    except (TypeError, ValueError):
        est = 0
    return max(1, est)


def _sse(event, data):
    # Format one Anthropic-style SSE event.
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


# --- v1.1.1: backend-error diagnostics helpers (UNCHANGED) ---

def _scrub_and_trim_body(text):
    # Produce a single-line, bounded rendering of locally generated protocol and
    # transport diagnostic text. Raw backend bodies/messages must never reach here.
    # INTENT: keep internal failure descriptions bounded and resistant to control
    #   characters or credential-shaped values before logging/client presentation.
    # REASONING: the architectural backend-prose boundary is structural extraction,
    #   not regex redaction; this helper is defense in depth for local constants and
    #   exception descriptions after that boundary.
    # ASSUMES: callers do not pass free-form backend response prose.
    if not text:
        return ""
    scrubbed = _sanitize_sensitive_text(text)
    if len(scrubbed) > ERR_BODY_MAXLEN:
        scrubbed = scrubbed[:ERR_BODY_MAXLEN] + "...[truncated]"
    return scrubbed


def _diag_headers(headers):
    # Extract the allowlisted diagnostic headers into a compact "k=v k=v" string.
    # INTENT: surface safe rate-limit / retry-after metadata without body prose.
    # REASONING: allowlist-only lookup means credential headers (Authorization),
    #   cookies and opaque session tokens are structurally unreachable here — we
    #   never iterate all headers (v1.4.9 removed the x-codex-* prefix loop that did).
    # ASSUMES: `headers` is an httpx.Headers (case-insensitive .get()).
    parts = []
    for name in DIAG_HEADER_ALLOWLIST:
        val = headers.get(name)
        if val is not None:
            parts.append(f"{name}={_sanitize_sensitive_text(val)}")
    return " ".join(parts) if parts else "(none)"


# --- HARDENING: retry helper ---


def _transport_failure_phase(error, post_stream_start=False):
    if post_stream_start:
        return "post_stream_start_body_read"
    if isinstance(error, (httpx.ConnectTimeout, httpx.ConnectError)):
        return "connect"
    if isinstance(error, httpx.PoolTimeout):
        return "connection_pool_wait"
    if isinstance(error, (httpx.WriteTimeout, httpx.WriteError)):
        return "request_body_write"
    if isinstance(error, (httpx.ReadTimeout, httpx.ReadError)):
        return "header_wait_or_body_read"
    return "connect_or_header_wait"


async def _discard_httpx_response(response):
    """Close a successful buffered POST result discarded by outer cancellation."""

    if isinstance(response, httpx.Response):
        await response.aclose()


def _retry_delay(attempt, retry_after):
    # Compute the sleep before the next attempt. Honor a backend Retry-After
    # header when present and sane; otherwise exponential backoff with jitter.
    if retry_after is not None:
        try:
            ra = float(retry_after)
            if ra >= 0:
                return min(ra, RETRY_AFTER_CAP)
        except (ValueError, TypeError):
            pass  # non-numeric (HTTP-date) Retry-After -> fall through to backoff
    base = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_CAP)
    # Full jitter: spreads retries so concurrent clients don't thundering-herd.
    return random.uniform(0, base)


def _parse_rate_limit_delay_seconds(message_text):
    # v1.2.14 (R4): extract the numeric "try again in <n>" hint from a backend
    # rate-limit message. Returns float seconds or None. The prose is inspected
    # locally ONLY and is never logged, reflected, or persisted.
    if not isinstance(message_text, str) or not message_text:
        return None
    match = _RATE_LIMIT_DELAY_RE.search(message_text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except (ValueError, TypeError):
        return None
    if value < 0:
        return None
    return value / 1000.0 if match.group(2).lower() == "ms" else value


def _numeric_retry_after_seconds(retry_after):
    # Parse a Retry-After header value as non-negative seconds, else None (an
    # HTTP-date form is intentionally treated as absent -> fall through to backoff).
    if retry_after is None:
        return None
    try:
        value = float(retry_after)
    except (ValueError, TypeError):
        return None
    return value if value >= 0 else None


def _retry_signals_from_body(raw_body):
    # v1.2.14 (R4): classify a backend error body for retry gating. Returns
    # (backend_code, backend_type, code_norm, message_text, signal_recognized).
    # message_text is retained ONLY for the internal rate-limit delay regex.
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except (ValueError, TypeError, UnicodeDecodeError):
        payload = {}
    backend_type, backend_code, _recognized, _param = _backend_error_fields(payload)
    code_norm = backend_code.strip().lower() if backend_code != "-" else ""
    type_norm = backend_type.strip().lower() if backend_type != "-" else ""
    root = payload if isinstance(payload, dict) else {}
    nested = root.get("error") if isinstance(root.get("error"), dict) else root
    message = nested.get("message") if isinstance(nested, dict) else None
    message_text = message if isinstance(message, str) else ""
    signal_recognized = bool(
        (code_norm and code_norm in _BACKEND_SIGNAL_CLASSIFICATION)
        or (type_norm and type_norm in _BACKEND_SIGNAL_CLASSIFICATION)
    )
    return backend_code, backend_type, code_norm, message_text, signal_recognized


def _plan_retry(status, retry_after_header, raw_body, attempt):
    # v1.2.14 (R4): classification-driven retry decision + delay selection for one
    # non-2xx attempt. Returns (should_retry, delay_seconds, delay_source).
    # INTENT: retry iff the classifier marks the failure retryable when a recognized
    #   backend code/type is present; otherwise reproduce today's bare-status behavior
    #   (RETRY_STATUSES, plus 408 as standard-retryable). A recognized deterministic
    #   code OVERRIDES the status (e.g. insufficient_quota-coded 429 fails fast).
    # REASONING: delay precedence per attempt is (1) parsed rate-limit message hint
    #   (gated on code rate_limit_exceeded), (2) Retry-After header, (3) local backoff.
    #   Rate-limit-class delays cap at 60s; a parsed/advertised delay beyond the cap
    #   fails fast (should_retry False) so the client owns the long wait rather than a
    #   silent shim stall. Non-rate-limit classes keep the 30s clamp.
    # ASSUMES: caller has already handled the chatgpt lazy-401 path; message prose is
    #   never logged (only its parsed number is used).
    backend_code, backend_type, code_norm, message_text, signal_recognized = \
        _retry_signals_from_body(raw_body)
    anthropic_type, _client_message, retryable = _classify_backend_error(
        status, backend_code, backend_type)
    if signal_recognized:
        should_retry = retryable
    else:
        # 408 is standard-retryable (retries up to MAX_RETRIES) — the once-only
        # special case in the design was judged not worth its bookkeeping.
        should_retry = (status in RETRY_STATUSES) or (status == 408)
    if not should_retry or attempt >= MAX_RETRIES:
        return False, 0.0, "-"
    is_rate_limit_class = (anthropic_type == "rate_limit_error")
    delay = None
    source = "backoff"
    if code_norm == "rate_limit_exceeded":
        parsed = _parse_rate_limit_delay_seconds(message_text)
        if parsed is not None:
            delay, source = parsed, "parsed"
    if delay is None:
        header_delay = _numeric_retry_after_seconds(retry_after_header)
        if header_delay is not None:
            delay, source = header_delay, "header"
    if delay is None:
        base = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_CAP)
        return True, random.uniform(0, base), "backoff"
    cap = RATE_LIMIT_RETRY_AFTER_CAP if is_rate_limit_class else RETRY_AFTER_CAP
    if delay > cap:
        if is_rate_limit_class:
            # Fail fast: do not sleep a multi-minute wait internally. Record the
            # advertised source so the terminal record explains the fast-fail.
            return False, 0.0, source
        delay = cap
    return True, delay, source


def _record_retry_delay_source(source):
    # v1.2.14 (R4): persist the selected delay source on the request record (both a
    # taken retry and a fail-fast-beyond-cap set it; a plain non-retryable keeps "-").
    if source == "-":
        return
    state = _request_state()
    if state is not None:
        state.retry_delay_source = source


# v1.3.4 (V4-R2): markers a stale/rejected reasoning blob's error body may name.
_STALE_REASONING_MARKERS = ("reasoning", "encrypted_content")


def _error_body_names_reasoning(raw_body):
    # V4-R2 condition 3: does this backend error body name reasoning material? The exact
    # backend rejection shape for a stale/expired encrypted reasoning blob is unobserved and
    # undocumented, so the probe is deliberately BROAD — a case-insensitive search for
    # "reasoning" or "encrypted_content" across the normalized error fields (type/code/param/
    # message, plus a Codex-style top-level `detail`). _backend_error_fields already collapses
    # both lane envelopes ({error:{}} openai, {status,error:{}} chatgpt) plus flat-root and
    # {detail:} into the same fields, so this works identically on every observed shape.
    # Breadth is safe: the caller gates on status==400 AND >=1 restored reasoning item
    # actually injected this request AND a one-shot budget, so a false positive costs at most
    # one extra attempt in today's graceful-miss shape. Body prose is scanned in memory ONLY
    # and never logged (counts-only discipline). Returns False on any parse failure so an
    # unreadable body preserves today's fail-fast contract.
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except (ValueError, TypeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    backend_type, backend_code, _recognized, param = _backend_error_fields(payload)
    nested = payload.get("error") if isinstance(payload.get("error"), dict) else payload
    message = nested.get("message") if isinstance(nested, dict) else None
    detail = payload.get("detail")
    haystack = " ".join(
        part for part in (backend_type, backend_code, param, message, detail)
        if isinstance(part, str) and part != "-"
    ).lower()
    return any(marker in haystack for marker in _STALE_REASONING_MARKERS)


def _maybe_strip_restored_reasoning(payload, status, raw_body):
    # V4-R2/R3/R4 shared entrypoint for both retry loops, called in the non-2xx block AFTER
    # _plan_retry has declined to retry. Returns True iff it stripped the injected restored
    # reasoning items and prepared a one-shot retry (the caller then performs its loop-local
    # cleanup + `continue`); False leaves 400 handling byte-identical to v1.3.3 (fail-fast).
    #
    # Gate (ALL must hold): (1) status == 400; (2) >=1 restored reasoning item was injected
    # this request; (3) the strip-retry has not already fired this request (one-shot, same
    # discipline as the lazy-401 refresh); (4) the error body names reasoning material. The
    # body-parsing condition (4) is checked LAST — the cheap request-scoped gates short-
    # circuit it for the overwhelming majority of 400s (which injected no restored items), so
    # a generic 400 (e.g. the pinned observability fixtures) never even parses the body.
    if status != 400:
        return False
    state = _request_state()
    if state is None or state.stale_strip_used:
        return False
    target_reasoning_ids = state.injected_restored_reasoning_ids
    if not target_reasoning_ids:
        return False
    if not _error_body_names_reasoning(raw_body):
        return False
    original = payload.get("input")
    if not isinstance(original, list):
        return False
    # R3: remove exactly the injected restored reasoning items from the reused payload IN
    # PLACE (both loops reuse one payload object across attempts, with no per-attempt
    # rebuild), matching by recorded reasoning-item id — never by positional index.
    kept = [
        item for item in original
        if not (
            isinstance(item, dict)
            and item.get("type") == "reasoning"
            and item.get("id") in target_reasoning_ids
        )
    ]
    stripped = len(original) - len(kept)
    if stripped == 0:
        # Nothing matched (already gone) — do not burn the one-shot or spend a retry on an
        # unchanged payload; fall through to today's fail-fast.
        return False
    original[:] = kept  # slice-assign so the object identity each loop closes over is kept
    # v1.3.4 (V4-R6): record the stripped count for the terminal record (counts only). +=
    # rather than = so the (one-shot-gated) figure would still accumulate correctly if the
    # strip contract ever allowed more than one strip per request.
    state.reasoning_cache_stripped += stripped
    # R4: the stripped call_ids are proven stale — evict them from the live cache, drop them
    # from the restored set, and rewrite the persisted snapshot via the existing fail-open
    # writer so neither this process nor a future restart re-injects and re-trips. Eviction
    # is not the populate path, so the persist call is explicit here.
    for call_id in state.injected_restored_call_ids:
        _REASONING_CACHE.pop(call_id, None)
        _REASONING_CACHE_RESTORED_IDS.discard(call_id)
    _write_reasoning_cache_state()
    # One-shot: this request may strip-and-retry exactly once.
    state.stale_strip_used = True
    # Terminal-record plumbing via the existing retry recorder (sets retry_reason=
    # stale_reasoning_400 / retry_source=body, increments the retry count, emits the
    # upstream_retry lifecycle event) — same convention as every other retry.
    _record_retry("stale_reasoning_400", source="body")
    # Distinct counts-only event. NEVER the stripped content or the backend error prose.
    _lifecycle_event(
        "reasoning_cache_stale_strip", _fields_before_elapsed=True, stripped=stripped)
    return True


async def _post_with_retry(url, headers, payload, disconnect_event):
    # HARDENING: non-streaming POST with bounded retry on transient errors.
    # Each potentially blocking POST/sleep races this response's disconnect event;
    # _ClientDisconnected is control flow, not a backend transport failure.
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        if disconnect_event.is_set():
            raise _ClientDisconnected()
        try:
            _trace_event("provider_request", payload, transport="json")
            _record_attempt("json")
            r = await _await_or_disconnect(
                _client.post(url, headers=headers, json=payload),
                disconnect_event,
                discard_result=_discard_httpx_response,
            )
        except _ClientDisconnected as error:
            # A same-turn successful POST can lose to disconnect. Close its response
            # before propagating the control signal so the pooled connection is freed.
            if isinstance(error.operation_result, httpx.Response):
                try:
                    await error.operation_result.aclose()
                except Exception:
                    pass
            raise
        except httpx.HTTPError as e:
            last_exc = e
            _record_transport_failure(
                e, _transport_failure_phase(e), attempt < MAX_RETRIES,
            )
            if attempt < MAX_RETRIES:
                delay = _retry_delay(attempt, None)
                _record_retry("transport")
                log.warning("backend transport error (attempt %d/%d), retrying in %.2fs: %s",
                            attempt + 1, MAX_RETRIES + 1, delay, type(e).__name__)
                await _await_or_disconnect(asyncio.sleep(delay), disconnect_event)
                continue
            _record_backend_error("api_error", backend_type=type(e).__name__,
                                  phase="upstream_request")
            raise
        _record_upstream_headers(r)
        if r.status_code >= 400 and attempt < MAX_RETRIES:
            # v1.2.14 (R4): classify the error body ONCE (for gating + delay source),
            # then decide. r.content is already buffered (non-streaming POST); the
            # prose is parsed in memory for structural signals and never logged.
            should_retry, delay, delay_source = _plan_retry(
                r.status_code, r.headers.get("retry-after"), r.content, attempt)
            if should_retry:
                _record_retry_delay_source(delay_source)
                _record_retry("status_%d" % r.status_code)
                # Retry diagnostics retain status, attempt, delay, delay-source, and
                # allowlisted headers only. Backend body prose is neither needed for
                # retry policy nor safe to persist (it can reflect request content).
                log.warning(
                    "backend %d (attempt %d/%d), retrying in %.2fs (source=%s) | headers: %s",
                    r.status_code, attempt + 1, MAX_RETRIES + 1, delay,
                    delay_source, _diag_headers(r.headers),
                )
                await r.aclose()
                await _await_or_disconnect(asyncio.sleep(delay), disconnect_event)
                continue
            # Not retrying: a non-retryable code (e.g. insufficient_quota-coded 429),
            # a bare status outside RETRY_STATUSES, or a rate-limit delay beyond cap
            # (fail fast). Record the advertised source when the cap forced the choice.
            _record_retry_delay_source(delay_source)
            # v1.3.4 (V4-R2/R3/R4): stale-blob insurance. A 400 that names reasoning material
            # AND carried >=1 restored (disk-loaded) reasoning item is the one case v1.3.3
            # persistence can turn a graceful miss into a hard failure — strip exactly those
            # items from the reused payload, evict+persist them as proven stale, and retry
            # once. Every non-triggering 400 stays fail-fast (byte-identical to v1.3.3).
            if _maybe_strip_restored_reasoning(payload, r.status_code, r.content):
                await r.aclose()
                continue
        return r, attempt
    # Unreachable in practice (loop returns or raises), but keeps intent explicit.
    if last_exc:
        raise last_exc
    raise httpx.HTTPError("retry loop exhausted")


async def _close_stream_context(stream_cm):
    """Close one stream context and expose a safe completion/failure result."""

    try:
        await stream_cm.__aexit__(None, None, None)
        return True, None
    except Exception as error:
        return False, type(error).__name__


async def _settle_stream_context(stream_cm):
    """Settle one owned stream exactly once and retain its cleanup evidence."""

    close_task = asyncio.create_task(_close_stream_context(stream_cm))
    kind, outcome, owner_cancellation = await _settle_owned_task(close_task)
    if kind == "result":
        cleanup_ok, cleanup_error = outcome
    elif kind == "exception":
        cleanup_ok, cleanup_error = False, type(outcome).__name__
    else:
        cleanup_ok, cleanup_error = False, "CancelledError"
    _record_cleanup_result(cleanup_ok, cleanup_error)
    _release_owned_stream_context(stream_cm)
    if owner_cancellation is not None:
        raise owner_cancellation
    return cleanup_ok, cleanup_error


async def _settle_request_resources(state):
    """Settle every resource registered to one request before lifecycle logging."""

    owner_cancellation = None
    for stream_cm in list(state.owned_stream_contexts):
        try:
            await _settle_stream_context(stream_cm)
        except asyncio.CancelledError as cancellation:
            owner_cancellation = cancellation

    # v1.2.14 (R6): the downstream heartbeat watchdog is normally stopped before the
    # terminal frames; this is the request-teardown safety net for the paths that
    # return without a terminal (mid-stream disconnect, early exit). Settled exactly
    # like the disconnect watcher.
    heartbeat = state.heartbeat_task
    state.heartbeat_task = None
    if heartbeat is not None:
        kind, outcome, heartbeat_cancellation = await _settle_owned_task(
            heartbeat, cancel=True)
        if kind == "exception":
            _record_cleanup_result(False, type(outcome).__name__)
        else:
            _record_cleanup_result(True)
        if heartbeat_cancellation is not None:
            owner_cancellation = heartbeat_cancellation

    watcher = state.disconnect_watcher
    state.disconnect_watcher = None
    if watcher is not None:
        kind, outcome, watcher_cancellation = await _settle_owned_task(
            watcher, cancel=True)
        if kind == "exception":
            _record_cleanup_result(False, type(outcome).__name__)
        else:
            # A watcher cancelled by its owner and a watcher that observed disconnect
            # are both fully settled; neither is a cleanup failure.
            _record_cleanup_result(True)
        if watcher_cancellation is not None:
            owner_cancellation = watcher_cancellation

    if state.cleanup_status == "not_started":
        _record_cleanup_result(True)
    if owner_cancellation is not None:
        raise owner_cancellation


async def _read_search_error_body(resp, disconnect_event):
    """Read a search error once with a transport bound, never an unbounded aread.

    Bounds apply to decoded chunks delivered by HTTPX; the current transport chunk
    can cross the ceiling, but it is not retained and no further chunk is pulled.
    The owner must settle the stream on overflow, disconnect, or read failure.
    """
    cache_key = "daaf_search_error_body"
    if cache_key in resp.extensions:
        return resp.extensions[cache_key]
    raw = bytearray()
    iterator = resp.aiter_bytes().__aiter__()
    try:
        while True:
            try:
                chunk = await _await_or_disconnect(iterator.__anext__(), disconnect_event)
            except StopAsyncIteration:
                break
            if len(raw) + len(chunk) > _SEARCH_MAX_ERROR_BYTES:
                raise _ProtocolError("search error body exceeded byte limit")
            raw.extend(chunk)
    finally:
        # Close the owned iterator explicitly: do not leave its async-generator
        # finalization to garbage collection after request cleanup was reported.
        await iterator.aclose()
    result = bytes(raw)
    resp.extensions[cache_key] = result
    return result


async def _open_backend_stream(url, headers, payload, disconnect_event, *, search_bearing=False):
    # v1.2.7 shared streamed-connect helper.
    # INTENT: give downstream streaming and ChatGPT inbound-nonstream accumulation
    # the same pre-content retries/lazy-401 behavior while making every blocked
    # connect, error-body read, refresh, and retry delay disconnect-cancellable.
    # REASONING: replay remains safe only before semantic SSE content is consumed.
    # Every discarded/losing context is closed exactly once here; the returned
    # context is closed exactly once by its caller's finally block.
    retry_count = 0
    did_401_refresh = False
    attempt = 0
    while attempt <= MAX_RETRIES:
        if disconnect_event.is_set():
            raise _ClientDisconnected()
        stream_cm = _client.stream("POST", url, headers=headers, json=payload)
        try:
            _trace_event("provider_request", payload, transport="sse")
            _record_attempt("sse")
            resp = await _await_or_disconnect(
                stream_cm.__aenter__(),
                disconnect_event,
            )
        except _ClientDisconnected:
            # Cancellation can race a just-completed __aenter__. Exiting the context
            # handles both partial and complete acquisition without a second owner.
            await _settle_stream_context(stream_cm)
            raise
        except asyncio.CancelledError as cancellation:
            # Outer ASGI/process cancellation can arrive after __aenter__ completed but
            # before _await_or_disconnect returned its response. The opener still owns
            # stream_cm in that window, so it must close the discarded context exactly
            # once before preserving cancellation. A caller owns only a returned tuple.
            try:
                await _settle_stream_context(stream_cm)
            except asyncio.CancelledError:
                pass
            raise cancellation
        except httpx.HTTPError as e:
            await _settle_stream_context(stream_cm)
            _record_transport_failure(
                e, _transport_failure_phase(e), attempt < MAX_RETRIES,
            )
            if attempt >= MAX_RETRIES:
                _record_backend_error(
                    "api_error", backend_type=type(e).__name__,
                    phase="upstream_request",
                )
                raise
            delay = _retry_delay(attempt, None)
            _record_retry("transport")
            log.warning("backend stream transport error (attempt %d/%d), retrying in %.2fs: %s",
                        attempt + 1, MAX_RETRIES + 1, delay, type(e).__name__)
            attempt += 1
            retry_count = attempt
            await _await_or_disconnect(asyncio.sleep(delay), disconnect_event)
            continue

        _record_upstream_headers(resp)
        if (SHIM_BACKEND_MODE == "chatgpt" and resp.status_code == 401
                and not did_401_refresh):
            _record_retry("auth_401")
            log.warning("chatgpt backend stream 401; attempting one token refresh + reconnect")
            await _settle_stream_context(stream_cm)
            rejected = _bearer_of(headers)
            _set_phase("backend_authentication")
            try:
                headers = await _await_or_disconnect(
                    _build_backend_headers(
                        force_token_refresh=True,
                        rejected_token=rejected,
                    ),
                    disconnect_event,
                )
            except RuntimeError:
                _mark_error(phase="backend_authentication")
                raise
            did_401_refresh = True
            # Token refresh is authentication recovery, not a transient replay;
            # preserve the retry budget and reconnect before semantic content.
            continue

        if search_bearing and resp.status_code >= 400:
            # Bound the ACTUAL read before retry classification, even on the final
            # attempt. The ordinary route deliberately retains its existing policy.
            try:
                search_error = await _read_search_error_body(resp, disconnect_event)
            except BaseException:
                await _settle_stream_context(stream_cm)
                raise

        if resp.status_code >= 400 and attempt < MAX_RETRIES:
            # v1.2.14 (R4): read the error body ONCE for classification-driven gating
            # and delay-source selection. The body is parsed in memory for structural
            # signals only (never decoded into a log line). On disconnect the read is
            # cancelled and the owned context is settled before propagating.
            try:
                raw_err = (search_error if search_bearing else await _await_or_disconnect(
                    resp.aread(),
                    disconnect_event,
                ))
            except _ClientDisconnected:
                await _settle_stream_context(stream_cm)
                raise
            except Exception:
                raw_err = b""
            # v1.2.14 (F3): bound the body handed to the classifier at MAX_ERROR_BODY_BYTES
            # (1 MiB). resp.aread() caches the full body on resp for the caller's error
            # re-read (comment below), so this truncation caps only the structural
            # retry-classification parse — a pathologically large error body cannot drive
            # an unbounded json.loads/scan. Beyond-cap bodies parse-fail on the truncated
            # bytes and fall back to HTTP-status classification (RETRY_STATUSES).
            if len(raw_err) > MAX_ERROR_BODY_BYTES:
                raw_err = raw_err[:MAX_ERROR_BODY_BYTES]
            should_retry, delay, delay_source = _plan_retry(
                resp.status_code, resp.headers.get("retry-after"), raw_err, attempt)
            if should_retry:
                _record_retry_delay_source(delay_source)
                _record_retry("status_%d" % resp.status_code)
                await _settle_stream_context(stream_cm)
                attempt += 1
                retry_count = attempt
                # Keep the structural diagnostic adjacent to the raced delay. The
                # real-subprocess regression uses the line plus a bounded scheduler
                # turn as evidence that the phase is retry sleep, not header acquisition.
                log.warning(
                    "backend stream %d (attempt %d/%d), retrying in %.2fs (source=%s) | headers: %s",
                    resp.status_code, attempt, MAX_RETRIES + 1, delay,
                    delay_source, _diag_headers(resp.headers),
                )
                await _await_or_disconnect(asyncio.sleep(delay), disconnect_event)
                continue
            # Not retrying: fall through to return this final non-2xx response. Its
            # body is already cached on resp, so the caller's error path re-reads it
            # without a second network round-trip. Record the advertised delay source
            # when a rate-limit cap forced the fail-fast.
            _record_retry_delay_source(delay_source)
            # v1.3.4 (V4-R2/R3/R4): stale-blob insurance, mirroring the JSON loop. A 400 that
            # names reasoning material AND carried >=1 restored reasoning item strips those
            # items from the reused payload, evicts+persists them as stale, and retries once.
            # raw_err is the bounded, already-read error body. Every non-triggering 400 stays
            # fail-fast (byte-identical to v1.3.3), settling and returning this response.
            if _maybe_strip_restored_reasoning(payload, resp.status_code, raw_err):
                await _settle_stream_context(stream_cm)
                attempt += 1
                retry_count = attempt
                continue

        # Transfer ownership to the request lifecycle before this tuple is visible to
        # caller code. The outer ASGI finalizer can therefore settle the context even if
        # cancellation or a downstream response-start failure lands before a branch-local
        # try/finally begins.
        _register_owned_stream_context(stream_cm)
        return resp, stream_cm, headers, retry_count, did_401_refresh

    raise httpx.HTTPError("stream retry loop exhausted")


# --- Prompt-cache observability helpers (v1.3.6, V6-R1/R3) ---

def _resolve_cached_tokens(usage_obj, input_total):
    # V6-R1/R3: extract usage.input_tokens_details.cached_tokens from a Responses usage
    # object with defensive typing AND the R3 clamp guard. Returns the effective cached
    # count (a non-negative int) or None. None means ABSENT — deliberately
    # indistinguishable from "no cache info", which is exactly how old backends and
    # fixtures emit it (they carry no input_tokens_details at all). Accept ONLY a non-bool
    # int >= 0; absent/null/string/negative/bool all resolve to None. The OpenAI Responses
    # `input_tokens` INCLUDES the cached prefix, so cached is a subset of that total; a
    # value exceeding the reported input total is malformed upstream and is treated as
    # absent (fail-open — never a negative client-visible input_tokens). Never raises:
    # usage parsing must not turn an otherwise-good response into a failure.
    if not isinstance(usage_obj, dict):
        return None
    details = usage_obj.get("input_tokens_details")
    if not isinstance(details, dict):
        return None
    cached = details.get("cached_tokens")
    if isinstance(cached, bool) or not isinstance(cached, int) or cached < 0:
        return None
    if isinstance(input_total, bool) or not isinstance(input_total, int):
        return None
    if cached > input_total:
        return None
    return cached


def _actual_speed_from_response(response):
    # Only a validated terminal upstream object calls this helper. Requested policy,
    # HTTP success, and latency never establish served service. Capture ordering before
    # parsing so a slower earlier terminal cannot overwrite a later terminal after it.
    global _LATEST_TERMINAL, _LATEST_TERMINAL_SEQUENCE, _LATEST_TERMINAL_ORDER
    with _LATEST_TERMINAL_LOCK:
        _LATEST_TERMINAL_SEQUENCE += 1
        terminal_order = _LATEST_TERMINAL_SEQUENCE
    raw_tier = response.get("service_tier") if isinstance(response, dict) else None
    canonical_served = (
        raw_tier
        if isinstance(raw_tier, str)
        and raw_tier in (_FAST_ACTUAL_SERVICE_TIERS | _STANDARD_ACTUAL_SERVICE_TIERS)
        else None
    )
    state = _request_state()
    if state is not None and isinstance(raw_tier, str):
        state.served_service_tier = _scrub_metadata(raw_tier, 100)
    raw_model = response.get("model") if isinstance(response, dict) else None
    if not isinstance(raw_model, str) or not _HEALTH_MODEL_TOKEN_RE.fullmatch(raw_model):
        raw_model = None
    requested_tier = None
    requested_source = "none"
    if state is not None:
        if state.requested_service_tier in _FAST_REQUEST_SERVICE_TIERS.values():
            requested_tier = state.requested_service_tier
        if state.requested_service_tier_source in _FAST_REQUEST_SOURCES:
            requested_source = state.requested_service_tier_source
    latest = {
        "model": raw_model,
        "requested_service_tier": requested_tier,
        "requested_source": requested_source,
        "served_service_tier": canonical_served,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with _LATEST_TERMINAL_LOCK:
        if terminal_order > _LATEST_TERMINAL_ORDER:
            _LATEST_TERMINAL = latest
            _LATEST_TERMINAL_ORDER = terminal_order
    if canonical_served in _FAST_ACTUAL_SERVICE_TIERS:
        return "fast"
    if canonical_served in _STANDARD_ACTUAL_SERVICE_TIERS:
        return "standard"
    return None


def _anthropic_usage_block(input_total, output_total, cached, speed=None):
    # V6-R3 (Decision 1 + Decision 2 = always-emit): build the client-visible Anthropic
    # usage block. Anthropic's `input_tokens` is the UNCACHED remainder only (unlike
    # OpenAI's, which includes the cached prefix), and clients (incl. Claude Code context
    # accounting) may sum input_tokens + cache_read_input_tokens + cache_creation_input_tokens
    # for the prompt total. So the mapping SUBTRACTS the cached prefix from input_tokens and
    # reports it as cache_read_input_tokens, preserving the sum invariant EXACTLY (the three
    # token fields still sum to the OpenAI input total, so downstream context arithmetic is
    # byte-equivalent whether or not caching fired). cache_read/cache_creation are ALWAYS
    # present (0 when `cached` is None) for a deterministic usage shape that matches
    # Anthropic's own responses. OpenAI reports no cache-WRITE count, so
    # cache_creation_input_tokens is always 0. `cached` must already be the effective
    # (typed, clamp-checked) value from _resolve_cached_tokens.
    block = {
        "input_tokens": input_total - cached if cached is not None else input_total,
        "output_tokens": output_total,
        "cache_read_input_tokens": cached if cached is not None else 0,
        "cache_creation_input_tokens": 0,
    }
    if speed is not None:
        block["speed"] = speed
    return block


# --- Non-streaming path: full Responses object -> full Anthropic message ---

def _validate_nonstream_output_items(output_items):
    # INTENT: reject the entire refusal-bearing response before cache/content effects.
    # REASONING: clients may parse allow-looking text despite a refusal stop reason;
    # neither refusal nor prefix may escape through ordinary or hosted conversion.
    # ASSUMES: callers supply a validated list, after any collector recovery. The
    # refusal discriminator suffices even for empty, missing or malformed payloads.
    # The buffered search-stream fallback also uses this check via the converter;
    # ordinary streaming refusal handling is deliberately outside this change.
    for item in output_items:
        _validate_output_item(item)
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "refusal":
                    raise _ProtocolError("backend response contains refusal")


def _reject_buffered_refusal_event(event):
    """Reject explicit refusal evidence before buffered inventory reconciliation."""
    kind = event.get("type") if isinstance(event, dict) else None
    if kind in ("response.refusal.delta", "response.refusal.done"):
        raise _ProtocolError("backend response contains refusal")
    if kind in ("response.content_part.added", "response.content_part.done"):
        part = event.get("part")
        if isinstance(part, dict) and part.get("type") == "refusal":
            raise _ProtocolError("backend response contains refusal")
    if kind == "response.output_item.done":
        _validate_nonstream_output_items([event.get("item")])


def _parse_recovery_number(value):
    # Used for every float/constant token, even one overwritten by a duplicate key.
    number = float(value)
    if not -float("inf") < number < float("inf"):
        raise ValueError("non-finite recovery number")
    return number


def _validate_recovered_function_arguments(raw):
    # INTENT: reject invalid/unserializable recovered inputs before any cache effect.
    # REASONING: Python JSON accepts NaN/Infinity and can overflow finite literals;
    # deep input can exhaust decoder/encoder recursion. Full-terminal legacy stays
    # unchanged. ASSUMES: raw inventory already passed the existing byte bound.
    try:
        arguments = json.loads(raw, parse_float=_parse_recovery_number,
                               parse_constant=_parse_recovery_number)
        if not isinstance(arguments, dict):
            raise _ProtocolError("backend recovered function arguments are not an object")
        # Iterator stack bounds structural depth without recursively walking values
        # or allocating a flattened copy. Count the root object as depth one.
        stack = [iter(arguments.values())]
        while stack:
            try:
                value = next(stack[-1])
            except StopIteration:
                stack.pop()
                continue
            if isinstance(value, (dict, list)):
                if len(stack) >= 64:
                    raise _ProtocolError("backend recovered function arguments exceed nesting limit")
                stack.append(iter(value.values() if isinstance(value, dict) else value))
        encoded = json.dumps(arguments, allow_nan=False, ensure_ascii=True,
                             separators=(",", ":"))
        if len(encoded) > _SEARCH_MAX_BYTES:
            raise _ProtocolError("backend recovered function arguments exceed byte limit")
    except (ValueError, RecursionError):
        raise _ProtocolError("backend recovered function arguments are not bounded finite JSON") from None


def _responses_to_anthropic(resp_obj, model):
    # Translate a complete Responses response object into an Anthropic message.
    # INTENT: walk `output[]` and build the Anthropic content array in the order
    #   Claude Code expects: THINKING block (reasoning summary) FIRST, then TEXT
    #   (message output_text), then TOOL_USE (function_call, sanitized).
    # REASONING: thinking-before-text is a convergent empirical Claude Code
    #   requirement (both prior-art references, notes file 05 §3c). Validate every
    #   converter/cache-facing field before cache mutation, then populate the
    #   reasoning cache so a non-streaming turn seeds continuity.
    resp_obj = _validate_response_for_conversion(resp_obj)
    output_items = resp_obj.get("output", [])
    # Recovery callers supply a list before reaching this boundary. Explicit null
    # here has no usable inventory; reject rather than invent an empty success.
    # The shared terminal validator still permits streaming's existing recovery.
    if output_items is None:
        raise _ProtocolError("backend nonstream response output is null")
    _validate_nonstream_output_items(output_items)
    # v1.3.3 (A2-R1): persist only when the populate actually mutated the cache, so a
    # reasoning-free or unpaired turn triggers no disk write. Fail-open; never on the hot
    # path's critical section (the write is atomic-replace and swallows all errors).
    if _populate_reasoning_cache(output_items):
        _write_reasoning_cache_state()

    content = []
    saw_tool_use = False

    # 1) THINKING block first (concatenate all reasoning summaries in order).
    # v1.2.6: chatgpt mode joins each nonempty reasoning-item summary with the
    # same paragraph boundary used between parts. Empty items do not arm or add a
    # separator. openai mode retains exact legacy empty-string concatenation.
    thinking_parts = []
    for item in output_items:
        if isinstance(item, dict) and item.get("type") == "reasoning":
            summary_text = _reasoning_summary_text(item)
            if SHIM_BACKEND_MODE != "chatgpt" or summary_text != "":
                thinking_parts.append(summary_text)
    thinking_separator = "\n\n" if SHIM_BACKEND_MODE == "chatgpt" else ""
    thinking_text = thinking_separator.join(thinking_parts)
    if thinking_text:
        # ASSUMES: an empty-signature signature is tolerated by Claude Code on a
        #   thinking block emitted by a proxy — the reasoning summary is a plain
        #   text summary, not a cryptographically signed Anthropic thinking block.
        #   Non-streaming Anthropic messages carry `signature` on thinking blocks;
        #   we emit an empty string. MEDIUM confidence — live test confirms.
        content.append({"type": "thinking", "thinking": thinking_text, "signature": ""})

    # 2) TEXT blocks (message items' output_text parts).
    for item in output_items:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in (item.get("content") or []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                txt = part.get("text", "")
                if txt:
                    content.append({"type": "text", "text": txt})

    # 3) TOOL_USE blocks (function_call items, sanitized).
    for item in output_items:
        if not isinstance(item, dict) or item.get("type") != "function_call":
            continue
        saw_tool_use = True
        try:
            args = json.loads(item.get("arguments") or "{}")
        except (ValueError, TypeError):
            args = {}
        name = item.get("name", "")
        args, dropped = _sanitize_tool_args(name, args)
        if dropped:
            log.info("sanitize tool=%s dropped=%s", name, ",".join(dropped))
        content.append({
            "type": "tool_use",
            # Use the public call_id as the Anthropic block id so the next turn's
            # tool_result threads back to the reasoning cache correctly.
            "id": item.get("call_id") or f"toolu_{uuid.uuid4().hex[:24]}",
            "name": name,
            "input": args,
        })

    if not content:
        # HARDENING (empty-response guard): Anthropic clients dislike an empty
        # content array; emit an empty text block so Claude Code stays happy.
        content.append({"type": "text", "text": ""})

    usage = resp_obj.get("usage") or {}
    status = resp_obj.get("status", "completed")
    input_total = usage.get("input_tokens", 0)
    output_total = usage.get("output_tokens", 0)
    cached = _resolve_cached_tokens(usage, input_total)
    actual_speed = _actual_speed_from_response(resp_obj)
    return {
        "id": resp_obj.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": _stop_reason_from_status(status, saw_tool_use),
        "stop_sequence": None,
        "usage": _anthropic_usage_block(
            input_total, output_total, cached, actual_speed),
        # V6-R1: private carry of the effective cached count (or None) for the two
        # non-stream lane consumers. Each pops it before the message is sent so it never
        # reaches the wire. Carried SEPARATELY from cache_read_input_tokens because a
        # mapped cache_read of 0 cannot distinguish ABSENT (terminal cached_tokens=-) from
        # a genuine cached_tokens:0 (terminal cached_tokens=0) — a distinction the terminal
        # record and the /health requests_with_cached counter both need.
        "_cached_tokens": cached,
    }


# --- ASGI application ---

async def _read_body(receive):
    chunks = b""
    more = True
    while more:
        event = await receive()
        if event.get("type") == "http.disconnect":
            _record_disconnect("body_read")
            break
        chunks += event.get("body", b"")
        more = event.get("more_body", False)
    return chunks


async def _send_json(send, status, obj, extra_headers=None):
    payload = json.dumps(obj).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    state = _request_state()
    if state is not None:
        headers.append((b"x-daaf-request-id", state.req_id.encode("ascii")))
        if status >= 400:
            error_obj = obj.get("error") if isinstance(obj, dict) else None
            error_type = error_obj.get("type") if isinstance(error_obj, dict) else None
            # Fix the logical error cause before entering the downstream send phase.
            # A response-start OSError can then use downstream_response_start only
            # when no request/backend/auth cause was already first-causal.
            _mark_error(error_type=error_type)
    if extra_headers:
        headers.extend(extra_headers)
    _set_phase("downstream_response_start")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    if state is not None:
        state.terminal_frame_send = "attempted"
        state.body_close_send = "attempted"
    _record_downstream_first_content()
    try:
        await send({"type": "http.response.body", "body": payload})
    except _ClientDisconnected:
        if state is not None:
            state.terminal_frame_send = "skipped_disconnect"
            state.body_close_send = "skipped_disconnect"
        _record_disconnect("json_body_send")
        raise
    except Exception:
        if state is not None:
            state.terminal_frame_send = "write_failed"
            state.body_close_send = "write_failed"
        raise
    if state is not None:
        state.terminal_frame_send = "send_completed"
        state.body_close_send = "send_completed"
        if status < 400:
            _mark_success()


# v1.2.10: canonical backend-HTTP-status -> Anthropic top-level error `type` map.
# INTENT: a deterministic backend rejection (esp. a 400 context_length_exceeded on
#   the ChatGPT/Codex subscription lane) must reach Claude Code as a NON-retryable
#   error shape so the client stops re-sending it; a flat api_error reads as a
#   transient failure and provoked the observed ~10x client-side retry storms on a
#   fixed, unsatisfiable input (live 14:17/14:54 context_length_exceeded).
# REASONING: exactly one source of truth shared by BOTH the non-stream
#   status-passthrough site and the streaming in-band-error finalizer, so the two
#   error surfaces cannot drift. Only known-deterministic 4xx map to
#   client-terminal Anthropic types; retry-eligible 429/5xx keep types that read as
#   retryable (rate_limit_error / overloaded_error / api_error) — the shim's own
#   RETRY_STATUSES loop has already exhausted its attempts before any status here
#   is passed through to the client.
# ASSUMES: the caller holds a real backend HTTP status. Sites with NO backend
#   status (mid-stream protocol/framing/transport failures after a 200 stream
#   start) do NOT call this — they keep api_error, per the v1.2.8 finalizer
#   contract.
_ANTHROPIC_ERROR_TYPE_BY_STATUS = {
    400: "invalid_request_error",
    401: "authentication_error",
    403: "permission_error",
    404: "not_found_error",
    429: "rate_limit_error",
    529: "overloaded_error",
}


def _anthropic_error_type_for_status(status):
    # v1.2.10: exact-status lookup; unknown statuses and other 5xx fall back to the
    # generic api_error (which reads as retryable — correct for genuine 5xx).
    return _ANTHROPIC_ERROR_TYPE_BY_STATUS.get(status, "api_error")


_BACKEND_ERROR_MESSAGE_BY_STATUS = {
    400: "backend rejected the request",
    401: "backend authentication failed",
    403: "backend permission denied",
    404: "backend resource not found",
    429: "backend rate limit exceeded",
    529: "backend overloaded",
}


def _backend_error_fields(payload):
    # INTENT: retain only the structured error type/code needed for classification
    #   and lifecycle metadata; free-form backend message/body prose is never returned.
    # REASONING: backend error messages can reflect prompts, system text, tool schemas,
    #   tool inputs, or opaque request material. Regex scrubbing cannot establish that
    #   arbitrary prose is safe, so the durable boundary is structural extraction only.
    # ASSUMES: exact type/code strings remain approved bounded metadata and are scrubbed
    #   by lifecycle/log serializers before persistence.
    # v1.2.14 (R2): recognize the four observed envelope shapes and report whether
    # the payload was a structured error envelope at all. The four shapes:
    #   1. {"error": {type, code, message, param}}        (openai lane, captured)
    #   2. {"status": N, "error": {…}}                    (chatgpt lane, captured)
    #   3. flat root {code, message, param}               (documented in-stream error)
    #   4. {"detail": "…"}                                (Codex model-rejection, survey)
    # Shape 2's top-level `status` is metadata only — the HTTP status is passed
    # separately to the classifier; here we just descend into root["error"].
    root = payload if isinstance(payload, dict) else {}
    nested = root.get("error") if isinstance(root.get("error"), dict) else root
    if nested is root and isinstance(root.get("incomplete_details"), dict):
        nested = root["incomplete_details"]
    backend_type = nested.get("type") if isinstance(nested.get("type"), str) else "-"
    backend_code = nested.get("code") if isinstance(nested.get("code"), str) else "-"
    param = nested.get("param") if isinstance(nested.get("param"), str) else "-"
    message = nested.get("message")
    if isinstance(message, dict):
        if backend_type == "-" and isinstance(message.get("type"), str):
            backend_type = message["type"]
        if backend_code == "-" and isinstance(message.get("code"), str):
            backend_code = message["code"]
    # "recognized" is about SHAPE, not whether the type/code VALUE is modeled: an
    # unknown-valued type is still a recognized error envelope. A payload is
    # recognized when it carries any structured error field (type/code/param), a
    # string message, a Codex-style string `detail` (shape 4, code-less), or
    # incomplete_details. Truly shapeless payloads ({} from an unparseable body, or
    # a dict with no error-ish fields) are unrecognized and counted via R1.
    recognized = (
        backend_type != "-"
        or backend_code != "-"
        or param != "-"
        or isinstance(nested.get("message"), str)
        or isinstance(root.get("detail"), str)
        or isinstance(root.get("incomplete_details"), dict)
    )
    return backend_type, backend_code, recognized, param


def _status_fallback_classification(status):
    # v1.2.14 (R2) pure HTTP-status fallback, used only when no recognized backend
    # code/type is present. Type mapping per the R2 design table. Two deliberate
    # points: (1) other-4xx -> invalid_request_error (non-retryable) is the
    # intentional change from the prior retryable api_error, so a deterministic
    # rejection is not client-retried; (2) overloaded_error is reserved for the
    # recognized codes server_is_overloaded/slow_down and status 529 — a bare 503
    # with an UNKNOWN code falls to the "unknown code + 5xx -> api_error" row (design
    # table row 9), which also preserves the v1.2.10 pinned-status behavior. The
    # client MESSAGE keeps the v1.2.11 fixed-message rule unchanged.
    if status in _BACKEND_ERROR_MESSAGE_BY_STATUS:
        client_message = _BACKEND_ERROR_MESSAGE_BY_STATUS[status]
    elif status >= 500:
        client_message = "backend server error"
    else:
        client_message = "backend request failed"
    if status == 401:
        return "authentication_error", client_message, False
    if status == 429:
        return "rate_limit_error", client_message, True
    if status == 529:
        return "overloaded_error", client_message, True
    if status == 408:
        return "api_error", client_message, True
    if 400 <= status < 500:
        return "invalid_request_error", client_message, False
    return "api_error", client_message, True


# v1.2.14 (R2): recognized backend code/type -> (anthropic_type, message, retryable).
# Ordered checks inside the classifier; a code match beats a type match, and both
# beat the HTTP status. Fixed messages only (v1.2.11 no-prose rule).
_BACKEND_SIGNAL_CLASSIFICATION = {
    "context_length_exceeded": (
        "invalid_request_error", "backend context length exceeded", False),
    "insufficient_quota": (
        "invalid_request_error", "backend quota or plan limit reached", False),
    "usage_not_included": (
        "invalid_request_error", "backend quota or plan limit reached", False),
    "invalid_prompt": ("invalid_request_error", "backend rejected the request", False),
    "bio_policy": ("invalid_request_error", "backend rejected the request", False),
    "cyber_policy": ("invalid_request_error", "backend rejected the request", False),
    "token_invalidated": ("authentication_error", "backend authentication failed", False),
    "rate_limit_exceeded": ("rate_limit_error", "backend rate limit exceeded", True),
    "server_is_overloaded": ("overloaded_error", "backend overloaded", True),
    "slow_down": ("overloaded_error", "backend overloaded", True),
    "server_error": ("api_error", "backend server error", False),
}


def _classify_backend_error(status, backend_code, backend_type):
    # v1.2.14 (R2): map a backend failure to (anthropic_type, client_message,
    # retryable) with CODE/TYPE precedence over HTTP status.
    # INTENT: one classifier for every failure path (pre-stream HTTP, in-band error,
    #   response.failed, chatgpt inbound-nonstream). Returns a retryable hint.
    # REASONING: known code/type first (most specific), else HTTP status, else the
    #   historical bodyless api_error/retryable fallback. Code beats type (mirrors the
    #   captured backend precedence, e.g. code=server_error over type=context_length).
    # RETRYABLE: COMPUTED here but NOT yet consumed — A1 leaves the retry loops
    #   (RETRY_STATUSES-gated in _post_with_retry/_open_backend_stream) byte-identical;
    #   A2 rewires gating to consume this flag. Fixed messages preserve the v1.2.11
    #   no-prose rule.
    code_norm = backend_code.strip().lower() if backend_code != "-" else ""
    type_norm = backend_type.strip().lower() if backend_type != "-" else ""
    for signal in (code_norm, type_norm):
        if signal and signal in _BACKEND_SIGNAL_CLASSIFICATION:
            return _BACKEND_SIGNAL_CLASSIFICATION[signal]
    if status is not None and status >= 400:
        return _status_fallback_classification(status)
    return "api_error", "backend request failed", True


def _normalize_backend_error(payload, status=None, phase=None):
    # Extract and persist only approved structural metadata. The client message is
    # selected from local constants and never from payload.message or raw body text.
    backend_type, backend_code, recognized, _param = _backend_error_fields(payload)
    if not recognized:
        # v1.2.14 (R1): an unrecognized error envelope is counted for observability
        # and then classified by HTTP status. The tag is a bounded shape descriptor,
        # never payload content: "empty" for a non-dict/empty body (typically an
        # unparseable one collapsed to {}), "unstructured" for a dict with no
        # error-ish fields.
        tag = "empty" if not isinstance(payload, dict) or not payload else "unstructured"
        _record_unknown_wire("envelope", tag)
    # v1.2.14 (R2): retryable is returned by the classifier but intentionally dropped
    # here — A1 does not consume it; A2 threads it through to the retry loops.
    anthropic_type, client_message, _retryable = _classify_backend_error(
        status, backend_code, backend_type)
    _record_backend_error(
        anthropic_type, backend_type=backend_type, backend_code=backend_code,
        phase=phase,
    )
    return anthropic_type, client_message, backend_type, backend_code


def _bearer_of(headers):
    # INTENT: extract the raw token from an already-built header dict's
    #   authorization/Authorization Bearer, for the lazy-401 guarded-reload identity
    #   check. Returns the token string or None. Never logged.
    if not isinstance(headers, dict):
        return None
    val = headers.get("authorization") or headers.get("Authorization") or ""
    if isinstance(val, str) and val.startswith("Bearer "):
        return val[len("Bearer "):]
    return None


async def _build_backend_headers(force_token_refresh=False, rejected_token=None):
    # v1.2.5: assemble the backend request headers for the active lane.
    # INTENT: both lanes add the local X-Client-Request-Id for safe correlation.
    #   OpenAI mode otherwise sends Authorization + Content-Type; ChatGPT mode sends
    #   its validated authorization/content-type/accept floor and no API-key header.
    # REASONING: keeping this in one helper means the lazy-401 retry path can rebuild
    #   the headers (with force_token_refresh=True + the rejected token for the
    #   guarded-reload identity check) identically to the first attempt.
    # CREDENTIAL SAFETY: returns a dict CONTAINING the Bearer; callers must never log
    #   it. In chatgpt mode a token-layer failure raises RuntimeError(_RELOGIN_MSG)
    #   (no secret content) for the caller to surface as a clean client error.
    state = _request_state()
    client_request_id = state.client_request_id if state is not None else uuid.uuid4().hex
    if SHIM_BACKEND_MODE == "chatgpt":
        access_token = await _get_access_token(
            force_refresh=force_token_refresh, rejected_token=rejected_token)
        return {
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "accept": "text/event-stream",
            **({"session-id": state.conversation_session_id}
               if state is not None and state.conversation_session_id is not None else {}),
            "X-Client-Request-Id": client_request_id,
        }
    return {
        "Authorization": f"Bearer {SHIM_BACKEND_API_KEY}",
        "Content-Type": "application/json",
        "X-Client-Request-Id": client_request_id,
    }


def _pending_sse_data_bytes(line_buffer):
    # Return the logical payload bytes currently buffered for a data field, or None
    # when the partial line is not a data field. SSE framing ("data:", one optional
    # space, and a possible trailing CR awaiting LF) is deliberately excluded.
    # This makes the event cap independent of where upstream transport chunks split,
    # including splits inside the field prefix and immediately before CRLF.
    logical_end = len(line_buffer)
    if logical_end and line_buffer[-1] == 0x0D:
        logical_end -= 1
    if logical_end == 4 and line_buffer[:logical_end] == b"data":
        return 0
    if logical_end < 5 or line_buffer[:5] != b"data:":
        return None
    value_start = 5
    if logical_end > value_start and line_buffer[value_start] == 0x20:
        value_start += 1
    return logical_end - value_start


def _consume_sse_line(raw_line, data_lines, event_size, event_open):
    # v1.2.7 bounded SSE framing primitive. SSE joins repeated data fields with a
    # newline and dispatches only on a REAL blank line. Comments do not open an
    # event. Return (payload-or-None, new_event_size, event-open-flag).
    if raw_line.endswith(b"\r"):
        raw_line = raw_line[:-1]
    if raw_line == b"":
        payload = b"\n".join(data_lines) if data_lines else None
        data_lines.clear()
        return payload, 0, False
    if raw_line.startswith(b":"):
        return None, event_size, event_open
    field, separator, value = raw_line.partition(b":")
    if separator and value.startswith(b" "):
        value = value[1:]
    event_open = True
    if field == b"data":
        event_size += len(value) + (1 if data_lines else 0)
        if event_size > MAX_RESPONSES_SSE_EVENT_BYTES:
            raise ValueError("upstream SSE event exceeded size limit")
        data_lines.append(bytes(value))
    return None, event_size, event_open


async def _iter_bounded_sse_data(resp, disconnect_event, terminal_seen=None):
    # v1.2.7 incremental SSE reader. Do not use aiter_lines(): it may allocate an
    # unbounded line before the caller can reject it. This parser retains only the
    # current line and current data event, each capped at 16 MiB, and never stores
    # the transcript. Every __anext__ body read races the response-local disconnect
    # event; cancelling a pending read cannot dispatch the partial buffered event.
    # EOF is NOT a synthetic blank line: any partial line or event that lacks a real
    # blank-line terminator is a framing failure.
    line_buffer = bytearray()
    data_lines = []
    event_size = 0
    event_open = False
    chunk_iterator = resp.aiter_bytes().__aiter__()
    while True:
        _trace_event("upstream_read_start")
        try:
            chunk = await _await_or_disconnect(
                chunk_iterator.__anext__(),
                disconnect_event,
            )
        except StopAsyncIteration:
            break
        _trace_event("upstream_chunk", bytes=len(chunk), content_omitted="raw_chunk_credentials_boundary")
        line_buffer.extend(chunk)
        while True:
            newline_at = line_buffer.find(b"\n")
            if newline_at < 0:
                pending_data_bytes = _pending_sse_data_bytes(line_buffer)
                if pending_data_bytes is None:
                    # Non-data fields still receive a raw-line bound. Data fields use
                    # the logical event bound below so their fixed SSE framing does not
                    # make an exactly-at-limit payload fail under one chunking pattern.
                    if len(line_buffer) > MAX_RESPONSES_SSE_EVENT_BYTES:
                        raise ValueError("upstream SSE line exceeded size limit")
                else:
                    joined_size = (
                        event_size
                        + (1 if data_lines else 0)
                        + pending_data_bytes
                    )
                    if joined_size > MAX_RESPONSES_SSE_EVENT_BYTES:
                        raise ValueError("upstream SSE event exceeded size limit")
                break
            raw_line = bytes(line_buffer[:newline_at])
            del line_buffer[:newline_at + 1]
            payload, event_size, event_open = _consume_sse_line(
                raw_line, data_lines, event_size, event_open)
            if payload is not None:
                _record_upstream_first_event()
                _record_upstream_event_gap()  # v1.2.14 (R6) idle-gap timestamp
                _trace_event("upstream_event", payload)
                yield payload
    _trace_event("upstream_eof", partial_line_bytes=len(line_buffer), partial_event_bytes=event_size)
    if not (line_buffer or event_open or data_lines):
        return
    # v1.2.14 (R5): a non-blank-terminated tail at EOF. If a complete, dispatchable
    # event is pending (data lines were seen and any residual partial line is NOT a
    # data-field continuation that would join into it), flush it as the final event.
    # This recovers a fully generated terminal response whose trailing blank line a
    # proxy trimmed (B7); downstream keeps its strict JSON/terminal validation, so a
    # semantically bad flushed payload still fails there. Any residual non-data bytes
    # after the complete event are a malformed tail: counted for observability, then
    # dropped.
    partial_data = _pending_sse_data_bytes(line_buffer)
    if data_lines and partial_data is None:
        if line_buffer:
            _record_unknown_wire("event_type", "malformed_sse_tail")
        payload = b"\n".join(data_lines)
        data_lines.clear()
        _record_upstream_first_event()
        _record_upstream_event_gap()  # v1.2.14 (R6) idle-gap timestamp
        _trace_event("upstream_event", payload, eof_flushed=True)
        yield payload
        return
    # Otherwise the residual is a genuinely incomplete event (a partial data line, or
    # a dangling field with no dispatchable data). Tolerate it ONLY once a terminal
    # semantic frame has already been accepted (the response is complete, so trailing
    # junk is harmless); before the terminal frame it stays a fatal framing failure.
    if terminal_seen is not None and terminal_seen[0]:
        _record_unknown_wire("event_type", "malformed_sse_tail")
        return
    raise ValueError("upstream SSE ended before a blank-line event boundary")


async def _accumulate_terminal_response(resp, disconnect_event):
    # v1.2.7 ChatGPT inbound-nonstream adapter.
    # INTENT: consume upstream SSE without emitting downstream bytes, accepting a
    # complete Responses object only from response.completed/incomplete.
    # REASONING: the terminal response is the single canonical aggregate; routing
    # it through _responses_to_anthropic() prevents a second reducer from drifting
    # on cache, ordering, sanitization, call IDs, usage, or stop reason. Event fields
    # are validated in arrival order so malformed content cannot hide behind a later
    # superficially valid terminal object. The first valid terminal ends consumption.
    # Returns (terminal_response, failure_message). Exactly one is non-None.
    # v1.2.14 (R5): a mutable one-slot flag lets the bounded SSE reader tolerate a
    # malformed tail at EOF only after a terminal semantic frame was accepted.
    terminal_seen = [False]
    # INTENT: preserve completed items omitted from a compact terminal envelope.
    # REASONING: retain bounded inventory, but defer search-only validation errors
    # until recovery is needed. A populated terminal keeps ordinary acceptance.
    # ASSUMES: only done items are evidence; deltas/partial tool JSON are not repaired.
    completed_inventory = _SearchCollector(_ToolRegistry(None, None))
    recovery_error = None
    try:
        async for data_bytes in _iter_bounded_sse_data(
                resp, disconnect_event, terminal_seen):
            if data_bytes.strip() == b"[DONE]":
                return None, "backend stream ended without a terminal response"
            try:
                ev = json.loads(data_bytes)
            except (ValueError, UnicodeDecodeError):
                return None, "backend stream contained malformed SSE JSON"
            etype = _validate_stream_event_fields(ev)
            _reject_buffered_refusal_event(ev)
            if (etype in ("response.output_item.added", "response.output_item.done")
                    and recovery_error is None):
                try:
                    completed_inventory.event(ev)
                except _ProtocolError:
                    # Fixed message only; release retained content and stop collecting.
                    # Continue shared event validation and wait for terminal authority.
                    recovery_error = "backend completed-item recovery inventory is invalid or exceeds limits"
                    completed_inventory = None
            if (recovery_error is None and etype in (
                    "response.output_text.delta", "response.output_text.done",
                    "response.function_call_arguments.delta", "response.function_call_arguments.done",
                    "response.content_part.added", "response.content_part.done",
                    "response.reasoning_summary_text.delta", "response.reasoning_summary_text.done",
                    "response.reasoning_summary_part.added", "response.reasoning_summary_part.done")):
                try:
                    index, item_id = ev.get("output_index"), ev.get("item_id")
                    if index is None and isinstance(item_id, str):
                        index = completed_inventory.ids.get(item_id)
                    if item_id is None and type(index) is int:
                        item_id = completed_inventory.indexes.get(index)
                    # No content retention or synthesis: only strengthen coverage.
                    _require_protocol_string(item_id, "recovery item reference")
                    if item_id not in completed_inventory.ids:
                        completed_inventory.retained_bytes += len(_search_json(item_id))
                        if completed_inventory.retained_bytes > _SEARCH_MAX_BYTES:
                            raise _ProtocolError("backend recovery references exceed byte limit")
                    item_type = ("function_call" if etype.startswith("response.function_call_arguments.")
                                 else "reasoning" if etype.startswith("response.reasoning_summary_")
                                 else "message")
                    completed_inventory._identity(index, item_id, item_type)
                except _ProtocolError:
                    recovery_error = "backend completed-item recovery has ambiguous item references"
                    completed_inventory = None
            if etype in ("response.completed", "response.incomplete"):
                terminal_seen[0] = True
                terminal = _validate_terminal_response(etype, ev.get("response"))
                if not terminal.get("output"):
                    if recovery_error is not None:
                        raise _ProtocolError(recovery_error)
                    if completed_inventory.indexes:
                        if (set(completed_inventory.completed) != set(completed_inventory.indexes)
                                or set(completed_inventory.indexes) != set(range(len(completed_inventory.indexes)))):
                            raise _ProtocolError("backend completed-item recovery lacks complete index coverage")
                        terminal = completed_inventory.event(ev)
                        for item in terminal["output"]:
                            if item.get("type") == "function_call":
                                _validate_recovered_function_arguments(item["arguments"])
                return terminal, None
            if etype == "response.failed":
                response_obj = ev.get("response")
                if not isinstance(response_obj, dict):
                    return None, "backend response.failed event was malformed"
                details = (response_obj.get("error")
                           or response_obj.get("incomplete_details")
                           or response_obj)
                _error_type, message, _backend_type, _backend_code = \
                    _normalize_backend_error(
                        details,
                        phase="upstream_stream",
                    )
                return None, message
            if etype == "error":
                details = ev.get("error") or ev
                _error_type, message, _backend_type, _backend_code = \
                    _normalize_backend_error(
                        details,
                        phase="upstream_stream",
                    )
                return None, message
            # v1.2.14 (R1): terminal/error events above return; a non-terminal event
            # reaching here is ignored (this adapter only extracts the terminal
            # object). Count only genuinely unknown event types, not the known
            # status/content events a normal stream interleaves before its terminal.
            if etype not in _KNOWN_EVENT_TYPES:
                _record_unknown_wire("event_type", etype)
    except httpx.HTTPError as error:
        _record_transport_failure(
            error, _transport_failure_phase(error, post_stream_start=True), False,
        )
        raise
    except _ProtocolError as error:
        return None, _scrub_and_trim_body(str(error))[:200] or "backend protocol error"
    except ValueError as error:
        return None, _scrub_and_trim_body(str(error))[:200] or "backend SSE framing error"
    return None, "backend stream ended without a terminal response"


async def _handle_messages(body, receive, send, scope_headers=()):
    t0 = time.time()

    # HARDENING (client-disconnect): a response-local Event is both the lightweight
    # state check and the active wait signal raced against every blocking upstream
    # operation. No disconnect state is shared across requests or processes.
    disconnect_event = asyncio.Event()

    async def _watch_disconnect():
        while True:
            event = await receive()
            if event.get("type") == "http.disconnect":
                disconnect_event.set()
                _record_disconnect("disconnect_watcher")
                return

    # Decode Anthropic request. Malformed JSON -> 400. Preserve raw object pairs just
    # long enough to reject duplicate exact top-level `speed` before ordinary dict
    # collapse; unrelated and nested duplicates retain last-key-wins compatibility.
    _set_phase("request_parse")
    try:
        req = _decode_anthropic_request_json(body, scope_headers)
        if _DIAGNOSTICS is not None and isinstance(req, dict):
            try:
                _DIAGNOSTICS.bind(_request_state().req_id, req, body)
                _trace_event("client_correlation", headers={
                    key.decode("ascii"): value.decode("ascii", errors="replace")
                    for key, value in scope_headers
                    if key.lower() in (b"x-client-request-id", b"x-request-id")})
            except Exception:
                pass
    except _DuplicateTopLevelSpeedError:
        _mark_error(phase="request_validation", error_type="invalid_request_error")
        await _send_json(send, 400, {"type": "error", "error": {
            "type": "invalid_request_error",
            "message": "duplicate top-level speed field",
        }})
        return
    except (ValueError, UnicodeDecodeError) as e:
        log.error("bad request json: %s", type(e).__name__)
        await _send_json(send, 400, {"type": "error", "error": {"type": "invalid_request_error", "message": "invalid JSON"}})
        return

    # Validate only the structural boundary the existing translator depends on.
    # The response is deliberately static: malformed request content must not be
    # reflected into either client-visible errors or diagnostic logs.
    _set_phase("request_validation")
    invalid_structure = not isinstance(req, dict)
    if not invalid_structure:
        messages = req.get("messages", [])
        invalid_structure = not isinstance(messages, list)
        if not invalid_structure:
            invalid_structure = any(not isinstance(message, dict) for message in messages)
        if not invalid_structure:
            # v1.2.13: "system" is admitted alongside user/assistant. Live Claude
            # Code sends a trailing role:"system" message inside `messages`; the
            # v1.2.12 two-role check rejected every real conversation turn with
            # the static 400 (captured-payload repro: scripts/scratch/
            # replay_captured_request.py). Translation folds system to user-role
            # input, the pre-v1.2.12 behavior proven against the live backend.
            invalid_structure = any(
                message.get("role") not in ("user", "assistant", "system")
                for message in messages
            )
        if not invalid_structure:
            invalid_structure = any(
                "content" in message
                and not isinstance(message.get("content"), (str, list))
                for message in messages
            )
        if not invalid_structure:
            invalid_structure = any(
                isinstance(message.get("content"), list)
                and any(
                    isinstance(block, dict)
                    and (
                        (block.get("type") == "tool_use"
                         and message.get("role") != "assistant")
                        or (block.get("type") == "tool_result"
                            and message.get("role") != "user")
                        or (
                            block.get("type") == "tool_result"
                            and not isinstance(block.get("content", ""), (str, list))
                        )
                    )
                    for block in message["content"]
                )
                for message in messages
            )
        if not invalid_structure:
            invalid_structure = any(
                isinstance(message.get("content"), list)
                and any(
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and not isinstance(block.get("text", ""), str)
                    for block in message["content"]
                )
                for message in messages
            )
        if not invalid_structure and "tools" in req:
            tools = req.get("tools")
            invalid_structure = (
                not isinstance(tools, list)
                or any(not isinstance(tool, dict) for tool in tools)
            )
        if not invalid_structure and "model" in req:
            invalid_structure = not isinstance(req.get("model"), str)
        if not invalid_structure and req.get("system") is not None:
            system = req.get("system")
            invalid_structure = not isinstance(system, (str, list))
            if not invalid_structure and isinstance(system, list):
                invalid_structure = any(
                    isinstance(block, dict)
                    and block.get("type", "text") == "text"
                    and not isinstance(block.get("text", ""), str)
                    for block in system
                )
        if not invalid_structure and "max_tokens" in req:
            max_tokens = req.get("max_tokens")
            invalid_structure = type(max_tokens) is not int or max_tokens <= 0
    if invalid_structure:
        log.error("bad request structure")
        await _send_json(send, 400, {"type": "error", "error": {
            "type": "invalid_request_error",
            "message": "invalid request structure",
        }})
        return

    # Validate the body/header Fast contract before authentication or any upstream call.
    # A persistent Fast beta with no speed remains ordinary traffic.
    try:
        state = _request_state()
        requested_service_tier, requested_service_tier_source = _requested_service_tier(
            req, _anthropic_beta_tokens(scope_headers),
            state.gpt_policy_snapshot if state is not None else None,
        )
    except _InvalidRequestError as error:
        _mark_error(phase="request_validation", error_type="invalid_request_error")
        await _send_json(send, 400, {"type": "error", "error": {
            "type": "invalid_request_error", "message": str(error),
        }})
        return

    _set_phase("request_translation")
    stream = bool(req.get("stream", False))
    # v1.2.2: strip any "#<effort>" suffix from the inbound model up front, so the
    # BARE model is used everywhere it is consumed — the outbound backend payload,
    # every log line below, and the response echoed to Claude Code. `model` from
    # here on is suffix-free; `slug_effort_raw` is the parsed tier-2 token (or None).
    model, slug_effort_raw = _split_effort_suffix(req.get("model", ""))
    try:
        search_registry = _ToolRegistry(req.get("tools"), req.get("tool_choice"))
        responses_payload, missing_reasoning, reasoning_cache_hits, effort_value, \
            effort_source, injected_restored_reasoning_ids, injected_restored_call_ids = \
            _anthropic_to_responses_request(
                req, model, slug_effort_raw, requested_service_tier, search_registry)
    except _InvalidRequestError as error:
        # The exception text is constructed exclusively from structural indexes,
        # bounded type labels, and local constants. Never log or reflect block data.
        _mark_error(phase="request_translation", error_type="invalid_request_error")
        await _send_json(send, 400, {"type": "error", "error": {
            "type": "invalid_request_error", "message": str(error),
        }})
        return
    search_bearing = bool(search_registry.search_name or any(
        item.get("type") == "web_search_call" for item in responses_payload["input"]))
    n_msgs = len(responses_payload["input"])
    n_tools = len(responses_payload.get("tools", []))
    state = _request_state()
    if state is not None:
        state.phase = "request_parsed"
        state.model = model
        state.stream = stream
        state.message_count = n_msgs
        state.tool_count = n_tools
        state.effort_value = effort_value
        state.effort_source = effort_source
        state.requested_service_tier = (
            _scrub_metadata(requested_service_tier, 100)
            if requested_service_tier is not None else "-"
        )
        state.requested_service_tier_source = requested_service_tier_source
        state.reasoning_cache_misses = missing_reasoning
        # v1.3.4 (V4-R6): per-request cache-hit count for the terminal record.
        state.reasoning_cache_hits = reasoning_cache_hits
        # v1.3.4 (V4-R1): hand the restored-blob tracking to the request state so the retry
        # loops' stale-blob 400 insurance (V4-R2..R4) can strip/evict exactly these items.
        state.injected_restored_reasoning_ids = injected_restored_reasoning_ids
        state.injected_restored_call_ids = injected_restored_call_ids
        # v1.2.14 (D5): capture the request key-name shape once, for a possible
        # backend invalid_request_error diagnosis line (emitted in _record_backend_error).
        state.request_shape = _request_shape_fields(responses_payload)
    _lifecycle_event(
        "request_parsed", model=model, stream="y" if stream else "n",
        msgs=n_msgs, tools=n_tools,
    )

    # v1.2.10: fast-fail a Claude-family model slug on the ChatGPT (Codex) lane
    # BEFORE any backend round-trip.
    # INTENT: the Codex backend rejects claude-* slugs with a 400 ("model ... is
    #   not supported when using Codex with a ChatGPT account"). Live 14:52-14:53
    #   a background/scheduled runner using the saved default model (Fable 5)
    #   produced a ~50-request/min rejection burst against the subscription lane.
    #   Fail deterministically here so the client sees a clear invalid_request_error
    #   with the actionable remap instruction instead of consuming quota on a
    #   guaranteed rejection.
    # REASONING: gated on the chatgpt lane only (the openai/API-key lane forwards
    #   whatever slug it is given and must not gain model-family opinions). The
    #   check runs on the MAPPED slug (post prefix-strip) so a configured
    #   SHIM_STRIP_MODEL_PREFIX cannot hide a claude alias. Match the LAST path
    #   segment (rsplit on "/") rather than the whole slug so a provider-prefixed
    #   form like "anthropic/claude-opus-4-8" is still caught when
    #   SHIM_STRIP_MODEL_PREFIX is unset (the mapped slug retains its prefix). Applies
    #   to BOTH stream and non-stream inbound requests: this runs before the streaming
    #   branch's HTTP-200 stream start, so a plain JSON error is the correct pre-flight
    #   shape for either (mirrors the pre-stream auth-failure return below).
    # ASSUMES: no legitimate Codex model slug's final path segment begins with
    #   "claude" (case-insensitive).
    if SHIM_BACKEND_MODE == "chatgpt":
        _mapped_slug = _map_model(model)
        if isinstance(_mapped_slug, str) and _mapped_slug.rsplit("/", 1)[-1].lower().startswith("claude"):
            # Scrub the upstream-controlled slug before it enters a log line
            # (log-injection class, same posture as _scrub_log_token elsewhere).
            _safe_slug = _scrub_log_token(_mapped_slug)
            log.warning(
                "chatgpt-lane claude-slug fast-fail: model %r rejected without "
                "backend round-trip", _safe_slug)
            await _send_json(send, 400, {"type": "error", "error": {
                "type": "invalid_request_error",
                # User-facing guidance (2026-10-12): name all four tier aliases.
                # CLAUDE_CODE_SUBAGENT_MODEL alone is only a fallback for
                # subagents without their own model (Claude Code >= 2.1.251), so
                # it cannot stop DAAF's opus/sonnet agents sending claude-* slugs;
                # and Claude Code's housekeeping calls (naming and summarizing
                # the session) use the haiku tier. Text only — no logic change.
                "message": (
                    "model %r is not available via the ChatGPT (Codex) lane; "
                    "map all four Claude tier aliases to GPT slugs in "
                    "environment_settings.txt: ANTHROPIC_DEFAULT_FABLE_MODEL, "
                    "ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL "
                    "and ANTHROPIC_DEFAULT_HAIKU_MODEL (Claude Code's housekeeping "
                    "calls, such as naming and summarizing your session, use the "
                    "haiku tier); or, if this is your session model, pick a GPT "
                    "model with /model"
                ) % _safe_slug,
            }})
            return

    # v1.2.5: build the backend auth headers by lane.
    # INTENT: in openai mode, Bearer the env API key. In chatgpt mode, Bearer the
    #   OAuth access_token from auth.json and emit its validated header floor. Both
    #   lanes add the local X-Client-Request-Id for content-blind correlation. Tools and SSE
    #   block lifecycle stay shared. v1.2.7 makes chatgpt transport always-streaming
    #   (inbound non-stream callers are internally accumulated), while v1.2.6's one
    #   route-specific response-formatting rule preserves reliable reasoning-summary
    #   boundaries. openai mode keeps exact legacy reasoning bytes and JSON transport.
    # CREDENTIAL SAFETY: the token/key are placed into the header dict (which is
    #   never logged — _diag_headers is allowlist-only and excludes Authorization)
    #   but never printed. A token-layer failure surfaces as a clean client error
    #   with the re-login message, no secret content.
    # Start the watcher before any potentially blocking auth/header work. This
    # makes an initial token refresh cancellable too, rather than waiting to begin
    # disconnect observation only after credentials are ready.
    watcher = asyncio.create_task(_watch_disconnect())
    state = _request_state()
    if state is not None:
        state.disconnect_watcher = watcher
    downstream_send = send

    async def _send_connected(message):
        # Every write after watcher startup is gated by the same active signal.
        # This prevents terminal/error bytes from racing past a known disconnect.
        state = _request_state()
        is_body_close = (
            message.get("type") == "http.response.body"
            and not message.get("more_body", False)
        )
        if is_body_close and state is not None:
            state.body_close_send = "attempted"
        if disconnect_event.is_set():
            if is_body_close and state is not None:
                state.body_close_send = "skipped_disconnect"
            _record_disconnect("downstream_send")
            raise _ClientDisconnected()
        try:
            await _await_or_disconnect(
                downstream_send(message), disconnect_event,
                prefer_completed=True,
            )
        except _ClientDisconnected:
            if is_body_close and state is not None:
                state.body_close_send = "skipped_disconnect"
            _record_disconnect("downstream_send")
            raise
        except Exception:
            if is_body_close and state is not None:
                state.body_close_send = "write_failed"
            raise
        if is_body_close and state is not None:
            state.body_close_send = "send_completed"

    send = _send_connected
    try:
        _set_phase("backend_authentication")
        headers = await _await_or_disconnect(
            _build_backend_headers(),
            disconnect_event,
        )
    except _ClientDisconnected:
        _record_disconnect("backend_authentication")
        return
    except RuntimeError as e:
        # chatgpt-mode auth store missing/unreadable, or a permanent refresh
        # failure at header-build time. Fail fast with the actionable message; no
        # token value in the error (RuntimeError text is the re-login instruction).
        log.error("chatgpt auth unavailable: %s", str(e))
        try:
            await _send_json(send, 401, {"type": "error", "error": {
                "type": "authentication_error", "message": str(e)}})
        except _ClientDisconnected:
            _record_disconnect("backend_authentication_failure")
        return
    url = f"{SHIM_BACKEND_BASE_URL}/responses"

    try:
        if not stream and search_bearing:
            # Both search transports remain bounded. OpenAI retains JSON while
            # subscription requests SSE; neither emits partial downstream content.
            json_mode = SHIM_BACKEND_MODE == "openai"
            responses_payload["stream"] = not json_mode
            search_cm = None
            try:
                resp, search_cm, headers, retries, refreshed = await _open_backend_stream(
                    url, headers, responses_payload, disconnect_event, search_bearing=True)
                if resp.status_code >= 400:
                    # The opener already bounded this body; reuse its private bytes.
                    raw_error = await _read_search_error_body(resp, disconnect_event)
                    try:
                        details = json.loads(raw_error)
                    except ValueError:
                        details = {}
                    error_type, message, _, _ = _normalize_backend_error(details, status=resp.status_code, phase="upstream_headers")
                    owned, search_cm = search_cm, None
                    await _settle_stream_context(owned)
                    await _send_json(send, resp.status_code, {"type": "error", "error": {"type": error_type, "message": message}})
                    return
                terminal = await _collect_search_response(resp, disconnect_event, search_registry, json_mode, reject_refusals=True)
                owned, search_cm = search_cm, None
                await _settle_stream_context(owned)
                # Validate recovered inventory before hosted projection/replay effects.
                _validate_nonstream_output_items(terminal["output"])
                anth = _search_projection(terminal, model, search_registry)
                cached = anth.pop("_cached_tokens", None)
                usage_source = anth.pop("_usage_source")
                state = _request_state()
                if state is not None:
                    state.input_tokens = anth["usage"]["input_tokens"] + (cached or 0)
                    state.output_tokens = anth["usage"]["output_tokens"]
                    state.cached_tokens = cached
                    state.usage_source = usage_source
                    state.stop_reason = anth["stop_reason"]
                if usage_source == "backend":
                    _calibrate_count_ratio(anth["usage"]["input_tokens"] + (cached or 0), len(body))
                await _send_json(send, 200, anth)
            except RuntimeError:
                if search_cm is not None:
                    owned, search_cm = search_cm, None
                    await _settle_stream_context(owned)
                await _send_json(send, 401, {"type": "error", "error": {"type": "authentication_error", "message": _RELOGIN_MSG}})
            except (_ProtocolError, ValueError, httpx.HTTPError) as error:
                # Release upstream BEFORE a downstream send can backpressure.
                if search_cm is not None:
                    owned, search_cm = search_cm, None
                    await _settle_stream_context(owned)
                message = str(error) if isinstance(error, _ProtocolError) else "backend search transport or framing error"
                state = _request_state()
                error_type = state.anthropic_error_type if state and state.anthropic_error_type != "-" else "api_error"
                await _send_json(send, 502, {"type": "error", "error": {"type": error_type, "message": message}})
            finally:
                if search_cm is not None:
                    await _settle_stream_context(search_cm)
            return

        if not stream and SHIM_BACKEND_MODE == "chatgpt":
            # v1.2.7: Codex requires stream:true even when the Anthropic caller
            # requested JSON. Consume one real upstream SSE response internally,
            # then translate only its complete terminal Responses object. No
            # downstream bytes are sent until success/failure is known.
            responses_payload["stream"] = True
            resp = None
            stream_cm = None
            retries = 0
            refreshed_401 = False
            anth = None
            # v1.2.8: pre-bind so an accumulator exception cannot leave this name
            # unbound at the `if terminal_response is not None` check below.
            terminal_response = None
            failure_message = None
            # v1.2.10: capture the real backend HTTP status for a rejection so the
            # final send can pass it through (mapped to an Anthropic error type)
            # instead of collapsing every 4xx/5xx to a flat, retryable-looking 502.
            # Stays None for post-200 accumulation/conversion failures, which have
            # no backend rejection status and correctly keep the 502 api_error path.
            backend_status = None
            try:
                try:
                    resp, stream_cm, headers, retries, refreshed_401 = \
                        await _open_backend_stream(
                            url, headers, responses_payload, disconnect_event)
                except RuntimeError as e:
                    log.error("chatgpt non-stream lazy-401 refresh failed: %s", str(e))
                    if not disconnect_event.is_set():
                        await _send_json(send, 401, {"type": "error", "error": {
                            "type": "authentication_error", "message": str(e)}})
                    return
                except httpx.HTTPError as e:
                    log.error("chatgpt non-stream transport error: %s", type(e).__name__)
                    if not disconnect_event.is_set():
                        await _send_json(send, 502, {"type": "error", "error": {
                            "type": "api_error", "message": "backend transport error"}})
                    return

                if resp.status_code >= 400:
                    status = resp.status_code
                    # v1.2.10: remember the backend rejection status for passthrough.
                    backend_status = status
                    try:
                        raw_err = (
                            await _read_search_error_body(resp, disconnect_event)
                            if search_bearing else await _await_or_disconnect(
                                resp.aread(),
                                disconnect_event,
                            )
                        ).decode("utf-8", "replace")
                        try:
                            structured_error = json.loads(raw_err)
                        except ValueError:
                            structured_error = {}
                        _error_type, failure_message, backend_type, backend_code = \
                            _normalize_backend_error(
                                structured_error, status=status,
                                phase="upstream_headers",
                            )
                    except _ClientDisconnected:
                        raise
                    except Exception:
                        failure_message = _classify_backend_error(
                            status, "-", "-")[1]
                        backend_type = "-"
                        backend_code = "-"
                    log.error(
                        "backend ChatGPT non-stream adapter error status=%d "
                        "retries=%d backend_type=%s backend_code=%s "
                        "anthropic_type=%s | headers: %s",
                        status, retries, _scrub_metadata(backend_type),
                        _scrub_metadata(backend_code),
                        _anthropic_error_type_for_status(status),
                        _diag_headers(resp.headers),
                    )
                    if refreshed_401 and status == 401:
                        if not disconnect_event.is_set():
                            await _send_json(send, 401, {"type": "error", "error": {
                                "type": "authentication_error", "message": _RELOGIN_MSG}})
                        return
                else:
                    try:
                        terminal_response, failure_message = \
                            await _accumulate_terminal_response(resp, disconnect_event)
                    except httpx.HTTPError as e:
                        log.error("chatgpt non-stream post-content transport error: %s",
                                  type(e).__name__)
                        if disconnect_event.is_set():
                            return
                        failure_message = "backend transport error"
                    except (TypeError, AttributeError, KeyError, ValueError) as error:
                        log.error("chatgpt non-stream protocol error: %s",
                                  type(error).__name__)
                        failure_message = "backend protocol error"
                    if terminal_response is not None:
                        try:
                            anth = _responses_to_anthropic(terminal_response, model)
                        except (_ProtocolError, TypeError, AttributeError,
                                KeyError, ValueError) as error:
                            log.error("chatgpt non-stream conversion error: %s",
                                      type(error).__name__)
                            failure_message = "backend response conversion failed"
            finally:
                # The caller owns the one context returned by the shared opener.
                # Closing here promptly cancels reads after terminal/failure and also
                # covers downstream disconnects and converter exceptions.
                if stream_cm is not None:
                    await _settle_stream_context(stream_cm)
                    stream_cm = None

            if disconnect_event.is_set():
                return
            if anth is None:
                safe_message = (
                    _scrub_and_trim_body(failure_message or "")[
                        :_CLIENT_ERROR_MESSAGE_MAXLEN
                    ] or "backend stream failed"
                )
                state = _request_state()
                if state is not None and not state.backend_error_logged:
                    _record_backend_error(
                        _anthropic_error_type_for_status(backend_status)
                        if backend_status is not None else "api_error",
                        phase="upstream_stream",
                    )
                # v1.2.10: if the failure was a backend HTTP rejection, pass the real
                # status through (mapped to the matching Anthropic error type) so a
                # deterministic 400 (e.g. context_length_exceeded) is not retried by
                # the client. Accumulation/conversion failures after a 200 (no
                # backend_status) retain the original 502 api_error shape.
                if backend_status is not None:
                    # v1.2.14 (R2): surface the CLASSIFIER type (code/type precedence
                    # over status), set by _normalize_backend_error on the successful
                    # parse. Fall back to the status-only mapping only when the body
                    # was unparseable and no classifier type was recorded. Preserves
                    # the real backend HTTP status passthrough.
                    state = _request_state()
                    passthrough_type = (
                        state.anthropic_error_type
                        if state is not None and state.anthropic_error_type != "-"
                        else _anthropic_error_type_for_status(backend_status)
                    )
                    await _send_json(send, backend_status, {"type": "error", "error": {
                        "type": passthrough_type,
                        "message": safe_message}})
                else:
                    state = _request_state()
                    normalized_type = (
                        state.anthropic_error_type
                        if state is not None and state.anthropic_error_type != "-"
                        else "api_error"
                    )
                    await _send_json(send, 502, {"type": "error", "error": {
                        "type": normalized_type, "message": safe_message}})
                return
            usage = anth["usage"]
            cached = anth.pop("_cached_tokens", None)
            # V6-R1: reconstruct the OpenAI input TOTAL from the always-emit block
            # (uncached remainder + cached prefix, 0 when absent). state.input_tokens and
            # the count-token calibrator both stay on the OpenAI total (unchanged terminal
            # semantics), NOT the subtracted client-visible remainder.
            input_total = usage["input_tokens"] + (cached or 0)
            _calibrate_count_ratio(input_total, len(body))
            state = _request_state()
            if state is not None:
                state.stop_reason = anth["stop_reason"]
                state.input_tokens = input_total
                state.output_tokens = usage["output_tokens"]
                state.cached_tokens = cached
                state.usage_source = "backend"
            await _send_json(send, 200, anth)
            return

        if not stream:
            # --- OpenAI/API-key non-streaming: retain the real upstream JSON POST. ---
            responses_payload["stream"] = False
            try:
                r, retries = await _post_with_retry(url, headers, responses_payload, disconnect_event)
            except httpx.HTTPError as e:
                log.error("messages non-stream transport error: %s", type(e).__name__)
                await _send_json(send, 502, {"type": "error", "error": {"type": "api_error", "message": "backend transport error"}})
                return
            if r.status_code >= 400:
                # Retain only structural classification metadata plus allowlisted
                # headers. Free-form backend body/message prose is parsed in memory for
                # exact type/code fields, then discarded without logging or reflection.
                try:
                    structured_error = json.loads(r.text)
                except (Exception, ValueError):
                    structured_error = {}
                error_type, client_msg, backend_type, backend_code = \
                    _normalize_backend_error(
                        structured_error, status=r.status_code,
                        phase="upstream_headers",
                    )
                log.error(
                    "backend error status=%d retries=%d backend_type=%s "
                    "backend_code=%s anthropic_type=%s | headers: %s",
                    r.status_code, retries, _scrub_metadata(backend_type),
                    _scrub_metadata(backend_code), error_type,
                    _diag_headers(r.headers),
                )
                await _send_json(send, r.status_code, {"type": "error", "error": {
                    "type": error_type, "message": client_msg}})
                return
            try:
                anth = _responses_to_anthropic(r.json(), model)
            except (_ProtocolError, TypeError, AttributeError,
                    KeyError, ValueError) as error:
                log.error("messages non-stream conversion error: %s",
                          type(error).__name__)
                _record_backend_error(
                    "api_error", backend_type=type(error).__name__,
                    phase="response_conversion",
                )
                await _send_json(send, 502, {"type": "error", "error": {
                    "type": "api_error",
                    "message": "backend response conversion failed"}})
                return
            usage = anth["usage"]
            cached = anth.pop("_cached_tokens", None)
            # v1.2.1: feed the count_tokens calibrator from successful usage — the OpenAI
            # input TOTAL (uncached remainder + cached prefix), not the subtracted client-
            # visible remainder. V6-R1: state.input_tokens likewise stays on the total.
            input_total = usage["input_tokens"] + (cached or 0)
            _calibrate_count_ratio(input_total, len(body))
            state = _request_state()
            if state is not None:
                state.stop_reason = anth["stop_reason"]
                state.input_tokens = input_total
                state.output_tokens = usage["output_tokens"]
                state.cached_tokens = cached
                state.usage_source = "backend"
            await _send_json(send, 200, anth)
            return

        # --- Streaming: translate Responses SSE events into Anthropic SSE events. ---
        responses_payload["stream"] = True

        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        # Streaming state machine. Claude Code expects, per message:
        #   message_start
        #   (content_block_start / content_block_delta* / content_block_stop)+
        #   message_delta (with stop_reason + usage)
        #   message_stop
        # Block ordering: THINKING block(s) precede the TEXT block, which precede
        # TOOL_USE blocks (convergent Claude Code requirement, notes file 05 §3c).
        started = False              # message_start emitted (bytes on the wire)
        next_index = 0               # next Anthropic content-block index to assign
        thinking_block_open = False
        thinking_index = None
        # v1.2.6 response-local ChatGPT boundary state for the CURRENT Anthropic
        # thinking block. It is reset only when a NEW thinking block opens, never
        # on a source summary-part .done lifecycle event.
        thinking_part_keys = set()
        thinking_item_to_output = {}
        thinking_output_to_item = {}
        thinking_emitted_nonempty = False
        thinking_boundaries_reliable = True
        text_block_open = False
        text_index = None
        # Responses stream addresses function_call argument deltas by INTERNAL
        # item_id (fc_...), NOT public call_id (both prior-art references verify
        # this — notes file 05 §3c). So key tool routing state on item_id.
        # item_id -> lifecycle/canonical replay state for one function call.
        tool_state = {}
        # v1.2.14 (R3): FIFO order of function_call item_ids as they were ADDED. The
        # tolerant scheduler opens at most one tool_use block at a time and drains the
        # rest in this order, so concurrently/interleaved-added tools still translate
        # to non-overlapping Anthropic blocks in added order.
        tool_added_order = []
        # Every output_item.added id is single-use, regardless of item kind. Completed
        # item values retain canonical JSON so identical replays are idempotent while
        # conflicting replays fail before duplicate stop/cache effects.
        added_item_ids = set()
        completed_item_values = {}
        # Collect each distinct full output item once, for cache population.
        completed_items = []
        terminal_output_items = None
        saw_tool_use = False
        final_status = "completed"
        # WARNING W1 FIX: track a terminal in-band failure separately from status.
        # On response.failed or an in-band `error` SSE event we must NOT close the
        # stream as a clean end_turn (that silently presents partial content as a
        # complete message). Instead we surface the failure to the client following
        # Anthropic streaming error semantics — an `error` SSE event — and stop.
        stream_failed = False
        failure_message = "backend stream failed"   # fixed local/classification text only
        failure_error_type = "api_error"
        saw_terminal_response = False
        # v1.2.14 (R5): one-slot mutable flag shared with the bounded SSE reader so it
        # can tolerate a malformed tail at EOF only after a terminal frame was seen.
        terminal_seen = [False]
        failure_finalized = False
        input_tokens = None
        output_tokens = None
        cached_tokens = None         # V6-R1: cached-prefix count from terminal usage (None until parsed)
        actual_speed = None          # v1.3.7: only terminal service_tier evidence sets this
        accumulated_text = ""        # for usage estimation fallback
        usage_estimated = False
        retries = 0
        # v1.2.14 (R3): out-of-order text/reasoning that arrives while a tool (or, for
        # text, another text) block is open is buffered here and flushed as a TRAILING
        # text/thinking block once all preceding blocks close (ratified downstream
        # shapes). This keeps Anthropic content blocks strictly non-overlapping while
        # tolerating the interleaved-emission wire instead of failing the stream.
        deferred_text = ""
        deferred_thinking = ""

        # v1.2.14 (R6): single-writer lock shared by every emit() call AND the ping
        # watchdog below. Each downstream frame is written under this lock, so a
        # heartbeat ping can never be interleaved into the middle of a partial content
        # frame — the writer discipline stays exactly single-writer.
        emit_lock = asyncio.Lock()

        async def emit(ev, data):
            state = _request_state()
            is_terminal = ev in ("message_stop", "error")
            _trace_event("emit_intent", event_type=ev,
                         deferred_text_chars=len(deferred_text), deferred_thinking_chars=len(deferred_thinking))
            async with emit_lock:
                _trace_event("emit_lock_acquired", event_type=ev)
                if is_terminal and state is not None:
                    state.terminal_frame_send = "attempted"
                _record_downstream_first_content()
                try:
                    await send({"type": "http.response.body", "body": _sse(ev, data), "more_body": True})
                except _ClientDisconnected:
                    if is_terminal and state is not None:
                        state.terminal_frame_send = "skipped_disconnect"
                    _record_disconnect("terminal_frame_send" if is_terminal else "content_send")
                    raise
                except Exception:
                    if is_terminal and state is not None:
                        state.terminal_frame_send = "write_failed"
                    raise
                if is_terminal and state is not None:
                    state.terminal_frame_send = "send_completed"

        async def _heartbeat_loop():
            # v1.2.14 (R6): keep the downstream SSE connection warm during upstream
            # silence and detect a dead client within one interval.
            # INTENT: emit an Anthropic `ping` event every SHIM_PING_INTERVAL_S once
            #   message_start is on the wire, through emit() (hence emit_lock) so a ping
            #   shares the single-writer discipline and never splits a partial frame.
            # REASONING: a failed ping write is positive evidence the client is gone.
            #   emit() has already recorded the disconnect; we set disconnect_event so
            #   the main reader loop tears down promptly (the fast dead-client-detection
            #   benefit) and then stop pinging. CancelledError (normal teardown at the
            #   terminal/failure boundary) is a BaseException and is intentionally NOT
            #   caught by `except Exception`, so it propagates and cancels cleanly.
            # ASSUMES: started only for a streaming response with SHIM_PING_INTERVAL_S
            #   > 0; runs in the request's inherited context so _request_state() and the
            #   downstream `send` resolve to this request.
            while True:
                await asyncio.sleep(SHIM_PING_INTERVAL_S)
                try:
                    await emit("ping", {"type": "ping"})
                except _ClientDisconnected:
                    disconnect_event.set()
                    return
                except Exception:
                    # A non-disconnect write failure is still evidence the client is
                    # gone; surface it as a disconnect and stop the heartbeat.
                    disconnect_event.set()
                    return

        async def _stop_heartbeat():
            # v1.2.14 (R6): tear the watchdog down exactly once, before the terminal
            # frames (so no ping can follow message_delta/message_stop) and as the
            # request-teardown safety net. Idempotent: a no-op once already stopped.
            st = _request_state()
            if st is None or st.heartbeat_task is None:
                return
            task = st.heartbeat_task
            st.heartbeat_task = None
            _kind, _outcome, owner_cancellation = await _settle_owned_task(
                task, cancel=True)
            if owner_cancellation is not None:
                raise owner_cancellation

        def _reasoning_part_key(ev):
            # v1.2.6 chatgpt-only semantic identity extraction.
            # INTENT: distinguish summary_index resets across reasoning items without
            # guessing from delta count, punctuation, timing, sequence_number, or
            # Markdown. The caller invokes this only in chatgpt mode; openai mode
            # never inspects identity for formatting.
            # REASONING: summary_index is valid only as a nonnegative integer (bool
            # is excluded despite being an int subclass). A nonempty item_id is the
            # preferred item scope; a valid output_index is retained when present to
            # strengthen the composite and is the fallback scope when item_id is
            # absent. With neither item_id nor output_index, identity is unreliable.
            summary_index = ev.get("summary_index")
            if (not isinstance(summary_index, int) or isinstance(summary_index, bool)
                    or summary_index < 0):
                return None
            item_id = ev.get("item_id")
            item_id = item_id if isinstance(item_id, str) and item_id else None
            output_index = ev.get("output_index")
            if (not isinstance(output_index, int) or isinstance(output_index, bool)
                    or output_index < 0):
                output_index = None
            if item_id is None and output_index is None:
                return None
            return (item_id, output_index, summary_index)

        def _item_output_mapping_conflicts(part_key):
            # Detect contradictions between the two independently supplied item scopes.
            # A complete identity is reliable only while the item_id <-> output_index
            # relationship remains one-to-one inside the current thinking block. If
            # either coordinate is rebound, even the current event cannot prove a new
            # semantic part; disable synthesis before deciding whether to emit a split.
            item_id, output_index, _summary_index = part_key
            if item_id is None or output_index is None:
                return False
            known_output = thinking_item_to_output.get(item_id)
            known_item = thinking_output_to_item.get(output_index)
            conflict = ((known_output is not None and known_output != output_index)
                        or (known_item is not None and known_item != item_id))
            if not conflict:
                thinking_item_to_output[item_id] = output_index
                thinking_output_to_item[output_index] = item_id
            return conflict

        def _part_key_conflicts_with_seen(part_key):
            # Detect a mixed/unstable identity for a semantic part already observed.
            # If two keys agree on summary_index and every shared scope component but
            # disagree only because one event omitted/changed item_id or output_index,
            # they might be the SAME part under a degraded identity. Treat that as
            # unreliable rather than inserting a false split mid-part. Conservative
            # posture: once this fires, boundary synthesis stays disabled until a new
            # Anthropic thinking block opens; all source deltas still pass unchanged.
            item_id, output_index, summary_index = part_key
            for seen_item_id, seen_output_index, seen_summary_index in thinking_part_keys:
                if summary_index != seen_summary_index:
                    continue
                if item_id is not None and seen_item_id is not None:
                    if item_id != seen_item_id:
                        # A different preferred item scope is a reliably new item,
                        # even when summary_index restarted to the same value.
                        continue
                    # Same preferred item + same summary index can only be the same
                    # part; a changed/omitted output index is degraded identity.
                    return True
                if output_index is not None and seen_output_index is not None:
                    if output_index != seen_output_index:
                        # With item_id unavailable, output_index is the fallback
                        # item scope; a different value is a reliably new item.
                        continue
                    return True
                # One side lacks the only scope component available on the other.
                # The relationship is unknowable, so suppress rather than split.
                return True
            return False

        async def _ensure_thinking_open():
            # Lazily open the thinking block (must be BEFORE any text/tool block).
            nonlocal thinking_block_open, thinking_index, next_index
            nonlocal thinking_part_keys, thinking_item_to_output
            nonlocal thinking_output_to_item, thinking_emitted_nonempty
            nonlocal thinking_boundaries_reliable
            if not thinking_block_open:
                thinking_index = next_index
                next_index += 1
                thinking_block_open = True
                # Reset all boundary state for this newly opened block. In particular,
                # reasoning after a text/tool transition must never inherit a stale
                # seen-key set or emit a leading separator.
                thinking_part_keys = set()
                thinking_item_to_output = {}
                thinking_output_to_item = {}
                thinking_emitted_nonempty = False
                thinking_boundaries_reliable = True
                await emit("content_block_start", {"type": "content_block_start",
                    "index": thinking_index,
                    "content_block": {"type": "thinking", "thinking": ""}})

        async def _ensure_text_open():
            # Lazily open the text block. If a thinking block is still open, close
            # it first so ordering (thinking before text) and non-overlap hold.
            nonlocal text_block_open, text_index, next_index, thinking_block_open
            if thinking_block_open:
                # ASSUMES: Claude Code tolerates a thinking block closed with an
                #   empty-signature signature_delta from a proxy. Anthropic's own
                #   thinking blocks carry a signature; we emit an empty one before
                #   content_block_stop. MEDIUM confidence — live test confirms; if
                #   Claude Code rejects the empty signature, the fallback is to omit
                #   the signature_delta entirely (some clients accept a bare stop).
                await emit("content_block_delta", {"type": "content_block_delta",
                    "index": thinking_index,
                    "delta": {"type": "signature_delta", "signature": ""}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": thinking_index})
                thinking_block_open = False
            if not text_block_open:
                text_index = next_index
                next_index += 1
                text_block_open = True
                await emit("content_block_start", {"type": "content_block_start",
                    "index": text_index,
                    "content_block": {"type": "text", "text": ""}})

        async def _flush_tool_args_sanitized(st, complete_args):
            # v1.2.14 (R3): sanitize-mode single input_json_delta emission for one tool
            # block. The caller guarantees the block is OPEN and its args have not been
            # emitted yet; the sanitize/parse/fallback logic is identical to the
            # pre-R3 inline sites — only the emission point (open, not pending) moved.
            try:
                parsed = json.loads(complete_args or "{}")
                parsed, dropped = _sanitize_tool_args(st["name"], parsed)
                if dropped:
                    log.info("sanitize tool=%s dropped=%s", st["name"], ",".join(dropped))
                out_json = json.dumps(parsed)
            except (ValueError, TypeError):
                # Fail-open: unparseable args pass through verbatim — sanitization must
                # never break a working tool call.
                log.warning("sanitize: unparseable args for tool=%s; passing through", st["name"])
                out_json = complete_args or "{}"
            await emit("content_block_delta", {"type": "content_block_delta",
                "index": st["anth_index"],
                "delta": {"type": "input_json_delta", "partial_json": out_json}})
            st["args_emitted"] = True

        async def _open_tool(st):
            # v1.2.14 (R3): give one deferred/serialized tool the single active-tool slot.
            # v1.4.8: in sanitize mode the downstream tool_use HEADER waits until the
            # arguments are complete (_start_tool), because the arguments are sent as one
            # delta at .done anyway. Until then nothing about this tool is on the wire, so
            # a whitespace-guard trip can retry upstream instead of leaving Claude Code
            # an empty tool call. Sanitize-off keeps the immediate header (unchanged).
            st["opened"] = True
            if not SHIM_SANITIZE_TOOLS or st["arguments_done"] is not None:
                await _start_tool(st)

        async def _start_tool(st):
            # Emit the tool_use content_block_start once. anth_index is assigned HERE so
            # Anthropic block indices stay monotonic in EMISSION order.
            nonlocal next_index
            if st["started"]:
                return
            st["anth_index"] = next_index
            next_index += 1
            st["started"] = True
            await emit("content_block_start", {"type": "content_block_start",
                "index": st["anth_index"],
                "content_block": {"type": "tool_use", "id": st["call_id"],
                                  "name": st["name"], "input": {}}})
            if not SHIM_SANITIZE_TOOLS:
                # Flush any argument bytes buffered while this tool waited its turn as
                # ONE input_json_delta. A serialized tool has nothing buffered at open
                # (its deltas arrive after), so this is a no-op on the byte-identical
                # path; a deferred tool flushes its whole buffer here.
                pending = st["args_buf"][st["emitted_len"]:]
                if pending:
                    await emit("content_block_delta", {"type": "content_block_delta",
                        "index": st["anth_index"],
                        "delta": {"type": "input_json_delta", "partial_json": pending}})
                    st["emitted_len"] = len(st["args_buf"])
            elif st["arguments_done"] is not None and not st["args_emitted"]:
                # Sanitize mode: the complete args already arrived while this tool was
                # deferred — emit the single sanitized delta now that the block is open.
                await _flush_tool_args_sanitized(st, st["arguments_done"][1])

        async def _close_tool(st):
            # v1.2.14 (R3): emit the terminal content_block_stop for one open tool.
            # v1.4.8: a still-deferred header (and its sanitized args, when known) is
            # emitted first, so every closed tool is a complete start->delta->stop block.
            await _start_tool(st)
            await emit("content_block_stop", {
                "type": "content_block_stop", "index": st["anth_index"]})
            st["closed"] = True

        async def _try_open_next_tool():
            # v1.2.14 (R3): FIFO-drain deferred tools when the active tool closes. Open
            # the next not-yet-opened tool in added order; if it is ALREADY fully
            # finalized (its output_item.done arrived while it waited), close it
            # contiguously and continue, so a run of finalized deferrals emits
            # back-to-back start->delta->stop blocks. Stop at the first tool still
            # awaiting its own events — that one becomes the active open block and its
            # remaining deltas/done flow through the normal handlers.
            while True:
                nxt = None
                for iid in tool_added_order:
                    cand = tool_state[iid]
                    if not cand["opened"] and not cand["closed"]:
                        nxt = cand
                        break
                if nxt is None:
                    return
                await _open_tool(nxt)
                if nxt["finalized"]:
                    await _close_tool(nxt)
                    continue
                return

        def _settle_unfinished_args(item_id, st):
            # v1.4.8: at the terminal, decide whether a sanitize-mode tool whose header
            # is still held may be sent, and with which arguments. Returns False when
            # the tool must be dropped instead of becoming an empty `{}` call.
            # INTENT: a completed response proves generation finished, so its final
            #   output item (preferred) or the buffered deltas are the arguments, and
            #   they flow through the same sanitizer as the .done path. An incomplete
            #   response whose arguments never completed (no .done, no output_item.done)
            #   was cut off mid-call; sending it would run a truncated tool call.
            # ASSUMES: terminal_output_items was validated with the terminal event.
            if not SHIM_SANITIZE_TOOLS or st["started"] or st["arguments_done"] is not None:
                return True
            if final_status != "completed":
                return False
            for item in terminal_output_items or []:
                if (isinstance(item, dict) and item.get("type") == "function_call"
                        and (item.get("id") == item_id
                             or item.get("call_id") == st["call_id"])
                        and item.get("name") == st["name"]
                        and isinstance(item.get("arguments"), str)):
                    st["arguments_done"] = (st["name"], item["arguments"])
                    return True
            st["arguments_done"] = (st["name"], st["args_buf"])
            return True

        async def _drain_pending_tools():
            # v1.2.14 (R3): terminal-success flush — open and close every still-deferred
            # tool in added order so each becomes a complete non-overlapping tool_use
            # block. Called after the single active tool (if any) has been closed.
            # v1.4.8: a sanitize-mode tool with unfinished arguments on an incomplete
            # response is dropped (marked closed, never sent); see _settle_unfinished_args.
            for iid in tool_added_order:
                st = tool_state[iid]
                if not st["opened"] and not st["closed"]:
                    if not _settle_unfinished_args(iid, st):
                        st["closed"] = True
                        log.warning("dropped a tool call whose arguments never completed "
                                    "(response status=%s)", _scrub_metadata(final_status))
                        continue
                    await _open_tool(st)
                    await _close_tool(st)

        async def _finalize_stream_failure(message, error_type="api_error"):
            # v1.2.7 common post-start failure finalizer.
            # INTENT: leave every emitted block structurally closed, then make the
            # final semantic frame an Anthropic event:error rather than a success.
            # REASONING: every failure source must share one lifecycle implementation;
            # otherwise a new branch can accidentally double-stop a tool, omit a
            # thinking signature, or emit message_stop after partial content.
            # v1.2.10: `error_type` lets a caller that KNOWS the backend HTTP status
            # (only the pre-content status/connect failure site does) surface a
            # status-aware Anthropic error type via _anthropic_error_type_for_status,
            # so a deterministic 400 becomes invalid_request_error and the client
            # stops retrying. HTTP status stays 200 (the stream already started);
            # only the in-band error `type` string is status-aware. Every other caller
            # (mid-stream protocol/framing/transport failures with no backend status)
            # keeps the default api_error, preserving the v1.2.8 finalizer semantics.
            nonlocal text_block_open, thinking_block_open, failure_finalized, stream_cm
            # Buffered search no longer needs its upstream after any failure.
            # Relinquish ownership before heartbeat settlement or downstream writes.
            if search_bearing and stream_cm is not None:
                owned, stream_cm = stream_cm, None
                await _settle_stream_context(owned)
            # v1.2.14 (R6): stop the heartbeat before emitting any terminal-failure
            # frames so a ping can never interleave with the error/body-close sequence.
            await _stop_heartbeat()
            _record_backend_error(error_type, phase="upstream_stream")
            if failure_finalized or disconnect_event.is_set():
                return False
            failure_finalized = True
            safe_message = (_scrub_and_trim_body(str(message or ""))[:200]
                            or "backend stream failed")
            if text_block_open:
                text_block_open = False
                await emit("content_block_stop", {
                    "type": "content_block_stop", "index": text_index})
            if thinking_block_open:
                thinking_block_open = False
                await emit("content_block_delta", {
                    "type": "content_block_delta", "index": thinking_index,
                    "delta": {"type": "signature_delta", "signature": ""}})
                await emit("content_block_stop", {
                    "type": "content_block_stop", "index": thinking_index})
            # v1.2.14 (R3): only STARTED tools have a downstream block (and a real
            # anth_index) to close; a still-deferred tool never emitted a
            # content_block_start, so it is skipped here. Filtering to started tools
            # also keeps the sort key from comparing a pending tool's None index.
            # v1.4.8: in sanitize mode this also skips the active tool whose arguments
            # never completed, so a failure no longer leaves an empty tool call.
            for item_id in sorted(
                (key for key in tool_state if tool_state[key]["started"]),
                key=lambda key: tool_state[key]["anth_index"],
            ):
                st = tool_state[item_id]
                if not st.get("closed"):
                    st["closed"] = True
                    await emit("content_block_stop", {
                        "type": "content_block_stop", "index": st["anth_index"]})
            await emit("error", {"type": "error", "error": {
                "type": error_type, "message": safe_message}})
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return True

        async def _close_text_and_thinking():
            # Close an open thinking block (empty-signature convention, see
            # _ensure_text_open) and an open text block before a tool or a retry.
            nonlocal thinking_block_open, text_block_open
            if thinking_block_open:
                await emit("content_block_delta", {"type": "content_block_delta",
                    "index": thinking_index,
                    "delta": {"type": "signature_delta", "signature": ""}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": thinking_index})
                thinking_block_open = False
            if text_block_open:
                await emit("content_block_stop", {"type": "content_block_stop", "index": text_index})
                text_block_open = False

        whitespace_retry_used = False
        # v1.4.8: (client message, Anthropic error type) when the one whitespace retry
        # was attempted but its reopen failed. The shared error handler then reports
        # THAT cause (e.g. a 429 or an expired login) instead of the whitespace trip.
        whitespace_retry_failure = None

        async def _retry_after_whitespace_trip():
            # v1.4.8: one transparent upstream retry after the tool-argument whitespace
            # guard trips. Claude Code does not retry an error that arrives after a tool
            # call has started, so the shim re-sends the same payload itself, but only
            # while no tool_use header has reached the client (sanitize mode defers it,
            # see _open_tool) and only once per response. The new attempt continues the
            # SAME downstream message (same message_start and heartbeat, next block
            # index). Returns False to use the normal error path instead; when the
            # reopen itself failed, whitespace_retry_failure carries the real cause.
            nonlocal whitespace_retry_used, resp, stream_cm, frames
            nonlocal saw_tool_use, deferred_text, deferred_thinking
            nonlocal whitespace_retry_failure
            if (whitespace_retry_used or not SHIM_SANITIZE_TOOLS
                    or disconnect_event.is_set()
                    or any(st["started"] for st in tool_state.values())):
                return False
            whitespace_retry_used = True
            req_state = _request_state()
            # Name attempt 1's upstream request id now: the reopen overwrites it.
            log.warning("tool-argument whitespace guard tripped before any tool_use "
                        "was sent; retrying upstream once (attempt-1 upstream_req_id=%s)",
                        req_state.upstream_request_id if req_state is not None else "-")
            # Release the abandoned attempt before any downstream write can block.
            await frames.aclose()
            owned, stream_cm = stream_cm, None
            await _settle_stream_context(owned)
            await _close_text_and_thinking()
            # Forget everything the abandoned attempt registered; none of it was sent
            # (deferred text/thinking included) and none of it may reach the cache.
            for container in (tool_state, tool_added_order, added_item_ids,
                              completed_item_values, completed_items):
                container.clear()
            saw_tool_use = False
            deferred_text = deferred_thinking = ""
            if req_state is not None:
                # The idle-gap clock restarts with the new attempt; the reconnect wait
                # is not upstream silence inside a stream.
                req_state.last_upstream_event_at = None
            _record_retry("tool_argument_whitespace")
            try:
                new_resp, new_cm, _headers, _retries, refreshed = await _open_backend_stream(
                    url, headers, responses_payload, disconnect_event)
            except RuntimeError as error:
                # Token refresh failed (the message carries the re-login command).
                log.error("whitespace retry could not reopen the backend stream: %s",
                          type(error).__name__)
                _record_backend_error("authentication_error", backend_type="token_refresh",
                                      phase="backend_authentication")
                whitespace_retry_failure = (str(error) or _RELOGIN_MSG, "authentication_error")
                return False
            except (_ProtocolError, httpx.HTTPError) as error:
                # _open_backend_stream already recorded an exhausted transport failure.
                log.error("whitespace retry could not reopen the backend stream: %s",
                          type(error).__name__)
                _record_backend_error("api_error", backend_type=type(error).__name__,
                                      phase="upstream_request")
                whitespace_retry_failure = ("backend transport error"
                                            if isinstance(error, httpx.HTTPError)
                                            else str(error), "api_error")
                return False
            if new_resp.status_code >= 400:
                status = new_resp.status_code
                log.error("whitespace retry backend status=%d", status)
                _mark_error(phase="upstream_headers",
                            error_type=_anthropic_error_type_for_status(status))
                raw_err = b""
                try:
                    raw_err = await _await_or_disconnect(new_resp.aread(), disconnect_event)
                except _ClientDisconnected:
                    await _settle_stream_context(new_cm)
                    raise
                except Exception:
                    pass
                await _settle_stream_context(new_cm)
                try:
                    structured_error = json.loads(raw_err.decode("utf-8", "replace"))
                except ValueError:
                    structured_error = {}
                error_type, client_failure, _backend_type, _backend_code = \
                    _normalize_backend_error(structured_error, status=status,
                                             phase="upstream_headers")
                if refreshed and status == 401:
                    client_failure = _RELOGIN_MSG
                whitespace_retry_failure = (client_failure, error_type)
                return False
            resp, stream_cm = new_resp, new_cm
            frames = _iter_bounded_sse_data(resp, disconnect_event, terminal_seen)
            return True

        # v1.2.7: open through the shared pre-content retry/lazy-401 helper.
        # Once event consumption begins this response is never replayed, except the
        # one v1.4.8 whitespace-guard retry (_retry_after_whitespace_trip).
        resp = None
        stream_cm = None
        frames = None                # upstream SSE reader; a whitespace retry swaps it
        did_401_refresh = False
        precontent_failure_message = None
        try:
            resp, stream_cm, headers, retries, did_401_refresh = \
                await _open_backend_stream(
                    url, headers, responses_payload, disconnect_event, search_bearing=search_bearing)
        except _ProtocolError as error:
            precontent_failure_message = str(error)
        except RuntimeError as e:
            # A permanent token-refresh failure is converted to a clean terminal
            # error stream below; no credential material is included.
            log.error("chatgpt stream lazy-401 refresh failed: %s", str(e))
            precontent_failure_message = str(e)
        except httpx.HTTPError as e:
            if disconnect_event.is_set():
                _record_disconnect("before_stream_start")
                return
            log.error("backend stream connect error: %s", type(e).__name__)
            precontent_failure_message = "backend transport error"

        # INTENT: fix a known backend HTTP rejection as the first causal error before
        #   attempting the downstream SSE response start.
        # REASONING: _mark_error records only outcome/phase/type and emits no lifecycle
        #   event, so a later successful header send can still parse the body and let
        #   _normalize_backend_error record enriched backend type/code metadata once.
        # ASSUMES: _open_backend_stream has exhausted any eligible status retries before
        #   returning this final non-2xx response to the streaming branch.
        if resp is not None and resp.status_code >= 400:
            _mark_error(
                phase="upstream_headers",
                error_type=_anthropic_error_type_for_status(resp.status_code),
            )

        # HARDENING: send the SSE response-start exactly once, before any emit().
        # Both the error-stream branch and the success branch emit a well-formed
        # Anthropic SSE stream with HTTP 200 (Claude Code reads stop_reason/error
        # from the events, not the HTTP status), so the headers are identical.
        # The live phase owns a header-write failure while _mark_error preserves an
        # earlier backend/auth failure_phase when one is already first-causal.
        _set_phase("downstream_response_start")
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/event-stream"),
                (b"cache-control", b"no-cache"),
                (b"connection", b"keep-alive"),
                (b"x-daaf-request-id", _request_state().req_id.encode("ascii")),
            ],
        })

        try:
            if resp is None or resp.status_code >= 400:
                status = resp.status_code if resp is not None else 502
                if resp is not None:
                    raw_err = ""
                    try:
                        raw_err = (
                            await _read_search_error_body(resp, disconnect_event)
                            if search_bearing else await _await_or_disconnect(
                                resp.aread(),
                                disconnect_event,
                            )
                        ).decode("utf-8", "replace")
                    except _ClientDisconnected:
                        raise
                    except Exception:
                        pass
                    diag_headers = _diag_headers(resp.headers)
                    try:
                        structured_error = json.loads(raw_err)
                    except ValueError:
                        structured_error = {}
                    error_type, client_failure, backend_type, backend_code = \
                        _normalize_backend_error(
                            structured_error, status=status,
                            phase="upstream_headers",
                        )
                    if did_401_refresh and status == 401:
                        client_failure = _RELOGIN_MSG
                else:
                    diag_headers = "(none)"
                    client_failure = precontent_failure_message or "backend transport error"
                    error_type = "api_error"
                    backend_type = "-"
                    backend_code = "-"
                    _record_backend_error(error_type, phase="upstream_request")
                log.error(
                    "backend stream error status=%d retries=%d backend_type=%s "
                    "backend_code=%s anthropic_type=%s | headers: %s",
                    status, retries, _scrub_metadata(backend_type),
                    _scrub_metadata(backend_code), error_type, diag_headers,
                )
                # Once the downstream SSE response has started, every backend status
                # or connect failure uses the same failure grammar as post-content
                # failures: one message_start followed by one terminal event:error.
                await emit("message_start", {"type": "message_start", "message": {
                    "id": msg_id, "type": "message", "role": "assistant", "model": model,
                    "content": [], "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0,
                              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}})
                started = True
                # v1.2.10: this is the ONLY finalizer caller that knows a real
                # backend HTTP status (`status`). Map it to the Anthropic error type
                # so a pre-content 400 (e.g. context_length_exceeded) surfaces as
                # invalid_request_error in-band and the client stops retrying. A
                # pre-content connect failure (resp is None) has status=502 -> the
                # map's api_error default, unchanged. The did_401_refresh 401 case
                # keeps its _RELOGIN_MSG message and now also carries the
                # authentication_error type.
                await _finalize_stream_failure(client_failure, error_type)
                return

            # message_start (usage filled with 0s; refined at message_delta). V6-R3: the
            # two cache fields are always present (0) for a deterministic usage shape.
            await emit("message_start", {"type": "message_start", "message": {
                "id": msg_id, "type": "message", "role": "assistant", "model": model,
                "content": [], "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0,
                          "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}})
            started = True

            # v1.2.14 (R6): message_start is on the wire — start the downstream
            # heartbeat. A `ping` every SHIM_PING_INTERVAL_S keeps the connection warm
            # during upstream silence; SHIM_PING_INTERVAL_S <= 0 disables it. This is
            # the ONLY start site, so the watchdog never runs for a non-streaming
            # response or for the pre-content error branch above (which returns first).
            if SHIM_PING_INTERVAL_S > 0:
                _hb_state = _request_state()
                if _hb_state is not None:
                    _hb_state.heartbeat_task = asyncio.create_task(_heartbeat_loop())

            if search_bearing:
                # Search-bearing requests share one canonical buffered collector.
                # The existing heartbeat, disconnect watcher, error finalizer and
                # stream-context owner remain in force; ordinary streaming is untouched.
                try:
                    terminal = await _collect_search_response(resp, disconnect_event, search_registry, reject_refusals=not search_registry.search_name)
                    owned, stream_cm = stream_cm, None
                    await _settle_stream_context(owned)
                    anth = _search_projection(terminal, model, search_registry)
                except _ProtocolError as error:
                    state = _request_state()
                    error_type = state.anthropic_error_type if state and state.anthropic_error_type != "-" else "api_error"
                    await _finalize_stream_failure(str(error), error_type)
                    return
                for index, block in enumerate(anth["content"]):
                    kind = block["type"]
                    start = dict(block)
                    field = {"text": "text", "thinking": "thinking", "tool_use": "input", "server_tool_use": "input"}.get(kind)
                    if field:
                        start[field] = {} if field == "input" else ""
                        if kind == "thinking":
                            start.pop("signature", None)
                    await emit("content_block_start", {"type": "content_block_start", "index": index, "content_block": start})
                    if field:
                        delta = ({"type": "input_json_delta", "partial_json": json.dumps(block[field])}
                                 if field == "input" else {"type": field + "_delta", field: block[field]})
                        await emit("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta})
                        if kind == "thinking":
                            await emit("content_block_delta", {"type": "content_block_delta", "index": index,
                                       "delta": {"type": "signature_delta", "signature": ""}})
                    await emit("content_block_stop", {"type": "content_block_stop", "index": index})
                cached = anth.pop("_cached_tokens", None)
                usage_source = anth.pop("_usage_source")
                state = _request_state()
                if state is not None:
                    state.input_tokens = anth["usage"]["input_tokens"] + (cached or 0)
                    state.output_tokens = anth["usage"]["output_tokens"]
                    state.cached_tokens = cached
                    state.usage_source = usage_source
                    state.stop_reason = anth["stop_reason"]
                    state.tools_called = sum(b["type"] == "tool_use" for b in anth["content"])
                if usage_source == "backend":
                    _calibrate_count_ratio(anth["usage"]["input_tokens"] + (cached or 0), len(body))
                await _stop_heartbeat()
                await emit("message_delta", {"type": "message_delta", "delta": {
                    "stop_reason": anth["stop_reason"], "stop_sequence": None}, "usage": anth["usage"]})
                await emit("message_stop", {"type": "message_stop"})
                _mark_success()
                await send({"type": "http.response.body", "body": b"", "more_body": False})
                return

            # v1.4.8: pull frames explicitly (same semantics as `async for`) so a
            # whitespace-guard retry can swap `frames` to the new upstream mid-loop.
            frames = _iter_bounded_sse_data(resp, disconnect_event, terminal_seen)
            while True:
                try:
                    data_bytes = await frames.__anext__()
                except StopAsyncIteration:
                    break
                # HARDENING (client-disconnect mid-stream): stop pulling from the
                # backend the moment the client goes away.
                if disconnect_event.is_set():
                    _record_disconnect("mid_stream")
                    return
                if data_bytes.strip() == b"[DONE]":
                    if not saw_terminal_response:
                        stream_failed = True
                        failure_message = "backend stream ended without a terminal response"
                    break
                try:
                    ev = json.loads(data_bytes)
                except (ValueError, UnicodeDecodeError):
                    # v1.2.14 (R3.5): a malformed frame whose recoverable type is a
                    # non-load-bearing status event is counted (R1) and skipped rather
                    # than failing the whole stream — the frame carried nothing the
                    # translation needs. Any other (or unrecoverable) type stays a
                    # strict failure, so a malformed load-bearing frame still aborts.
                    probed_type = _probe_malformed_event_type(data_bytes)
                    if probed_type in _MALFORMED_TOLERANT_EVENT_TYPES:
                        _record_unknown_wire("event_type", probed_type)
                        continue
                    stream_failed = True
                    failure_message = "backend stream contained malformed SSE JSON"
                    break
                etype = _validate_stream_event_fields(ev)

                # --- reasoning summary delta -> thinking block (BEFORE text) ---
                if etype == "response.reasoning_summary_text.delta":
                    delta = ev.get("delta", "")
                    if delta:
                        # v1.2.7 protocol-order invariant: reasoning may reopen only
                        # after prior text/tool blocks are fully closed. Closing and
                        # continuing would reorder malformed upstream semantics and
                        # could overlap Anthropic content blocks, so fail explicitly.
                        unfinished_tool = any(
                            st["opened"] and not st.get("closed")
                            for st in tool_state.values()
                        )
                        if text_block_open or unfinished_tool:
                            # v1.2.14 (R3): tolerate out-of-order reasoning. A text or
                            # tool block is open, so buffer this reasoning and emit it
                            # as a TRAILING thinking block once those blocks close
                            # (ratified shape) — keeps Anthropic blocks non-overlapping
                            # instead of failing the stream as pre-R3 did.
                            deferred_thinking += delta
                            continue
                        await _ensure_thinking_open()
                        if SHIM_BACKEND_MODE == "chatgpt":
                            # v1.2.6: synthesize a boundary only before the first
                            # nonempty delta of a NEW, reliable semantic part. Same-key
                            # chunks pass consecutively with no separator. Empty source
                            # deltas never reach this branch and therefore cannot arm a
                            # boundary. Arrival order is authoritative; identities are
                            # never sorted or buffered, and .done events remain ignored.
                            part_key = _reasoning_part_key(ev)
                            if part_key is None:
                                # Missing/malformed identity: exact legacy append now,
                                # and disable later synthesis for this thinking block so
                                # a subsequently identified delta cannot create a false
                                # mid-part split relative to this unidentified text.
                                thinking_boundaries_reliable = False
                            elif _item_output_mapping_conflicts(part_key):
                                # Contradictory complete scopes are not a reliable new
                                # part: one item moved outputs or one output was rebound
                                # to another item. Preserve this and all later source
                                # deltas by exact append for the rest of the block.
                                thinking_boundaries_reliable = False
                                thinking_part_keys.add(part_key)
                            elif part_key not in thinking_part_keys:
                                if _part_key_conflicts_with_seen(part_key):
                                    # Identity changed or became more/less complete for
                                    # what may be the same semantic part. Do not guess.
                                    thinking_boundaries_reliable = False
                                elif (thinking_boundaries_reliable
                                      and thinking_emitted_nonempty):
                                    await emit("content_block_delta", {
                                        "type": "content_block_delta",
                                        "index": thinking_index,
                                        "delta": {
                                            "type": "thinking_delta",
                                            "thinking": "\n\n",
                                        },
                                    })
                                thinking_part_keys.add(part_key)
                            thinking_emitted_nonempty = True
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": thinking_index,
                            "delta": {"type": "thinking_delta", "thinking": delta}})
                    continue

                # --- text delta ---
                if etype == "response.output_text.delta":
                    delta = ev.get("delta", "")
                    if delta:
                        unfinished_tool = any(
                            st["opened"] and not st.get("closed")
                            for st in tool_state.values()
                        )
                        if unfinished_tool:
                            # v1.2.14 (R3): tolerate text emitted while a tool block is
                            # open. Buffer it and emit as a TRAILING text block once the
                            # tool closes (ratified shape) — keeps Anthropic blocks
                            # non-overlapping instead of failing the stream as pre-R3 did.
                            deferred_text += delta
                            accumulated_text += delta
                            continue
                        await _ensure_text_open()
                        accumulated_text += delta
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": text_index,
                            "delta": {"type": "text_delta", "text": delta}})
                    continue

                # --- new output item added (function_call opens a tool_use block) ---
                if etype == "response.output_item.added":
                    item = ev["item"]
                    item_id = item.get("id")
                    if item_id is not None:
                        if item_id in added_item_ids:
                            raise _ProtocolError(
                                "backend replayed response.output_item.added"
                            )
                        added_item_ids.add(item_id)
                    if item.get("type") == "function_call":
                        if item_id in tool_state:
                            raise _ProtocolError("backend reused a function item id")
                        # v1.2.14 (R3): tolerant scheduler. A function_call added while
                        # another tool block is still OPEN is DEFERRED (registered
                        # pending, args buffered), not rejected as a protocol failure —
                        # it opens later via _try_open_next_tool when the active tool
                        # closes, producing non-overlapping Anthropic tool_use blocks in
                        # added order (strict-emit downstream). On a SERIALIZED wire no
                        # tool is ever open here, so `other_tool_open` is always False
                        # and this reduces to the pre-R3 immediate-open path.
                        other_tool_open = any(
                            st["opened"] and not st.get("closed")
                            for st in tool_state.values()
                        )
                        st = {
                            "anth_index": None,        # assigned at header (emission order)
                            "opened": False,           # holds the active-tool slot
                            "started": False,          # v1.4.8: header is on the wire
                            "closed": False,
                            "call_id": item["call_id"],
                            "name": item["name"],
                            "args_buf": "",
                            "emitted_len": 0,          # sanitize-off incremental cursor
                            "arguments_done": None,
                            "args_emitted": False,     # sanitize-on single-delta guard
                            "finalized": False,        # output_item.done seen
                            "completed_item": None,
                        }
                        tool_state[item_id] = st
                        tool_added_order.append(item_id)
                        saw_tool_use = True
                        if not other_tool_open:
                            # Serialized path: close ALL open non-tool blocks before
                            # opening tool_use (normal text/thinking -> tool transition),
                            # then open immediately. While another tool IS open, text and
                            # thinking are already closed, so the deferred branch has
                            # nothing to close and emits nothing until it drains.
                            # (v1.4.8: in sanitize mode "open" takes the slot; the header
                            # itself follows when the arguments complete.)
                            await _close_text_and_thinking()
                            await _open_tool(st)
                    elif item.get("type") not in _KNOWN_ITEM_TYPES:
                        # v1.2.14 (R1): message/reasoning items are known and handled
                        # elsewhere; any other output_item type is unmodeled and
                        # counted for observability (still not translated).
                        _record_unknown_wire("item_type", item.get("type"))
                    continue

                # --- function_call argument deltas (route by item_id) ---
                if etype == "response.function_call_arguments.delta":
                    item_id = ev["item_id"]
                    st = tool_state.get(item_id)
                    if st is None:
                        raise _ProtocolError(
                            "backend emitted arguments for an unknown tool item"
                        )
                    if st.get("closed") or st.get("arguments_done") is not None:
                        raise _ProtocolError(
                            "backend emitted argument delta after tool arguments completed"
                        )
                    frag = ev["delta"]
                    if not frag:
                        continue
                    # v1.2.8: ALWAYS buffer — the buffered delta stream is the
                    # canonical fallback when arguments.done omits the full string,
                    # in both sanitize modes. Sanitize mode still defers emission
                    # to .done; sanitize-off still forwards incrementally.
                    try:
                        _check_tool_argument_whitespace(st, frag)
                    except _ToolWhitespaceError:
                        # v1.4.8: retry once if no tool_use has reached the client;
                        # otherwise fall through to the shared error path below.
                        if await _retry_after_whitespace_trip():
                            continue
                        raise
                    st["args_buf"] += frag
                    # v1.2.14 (R3): forward incrementally only once the block is OPEN.
                    # A still-deferred tool just buffers (emitted_len stays behind, and
                    # _open_tool flushes args_buf[emitted_len:] as one delta on open).
                    if not SHIM_SANITIZE_TOOLS and st["opened"]:
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": st["anth_index"],
                            "delta": {"type": "input_json_delta", "partial_json": frag}})
                        st["emitted_len"] = len(st["args_buf"])
                    continue

                # --- function_call arguments finalized ---
                if etype == "response.function_call_arguments.done":
                    item_id = ev["item_id"]
                    st = tool_state.get(item_id)
                    if st is None:
                        raise _ProtocolError(
                            "backend completed arguments for an unknown tool item"
                        )
                    # v1.2.8 wire tolerance: fall back to the identity captured at
                    # output_item.added and to the buffered delta stream when the
                    # event omits name/arguments (validated-optional above).
                    # ASSUMES: a replayed .done is consistent about whether it
                    #   carries `arguments` — a replay that includes it once and
                    #   omits it once compares against args_buf and is treated as
                    #   conflicting (fail-closed) rather than idempotent.
                    canonical_done = (
                        ev.get("name") or st["name"],
                        ev["arguments"] if "arguments" in ev else st["args_buf"],
                    )
                    prior_done = st.get("arguments_done")
                    if prior_done is not None:
                        if canonical_done == prior_done:
                            continue
                        raise _ProtocolError(
                            "backend replayed conflicting completed tool arguments"
                        )
                    if canonical_done[0] != st["name"]:
                        raise _ProtocolError(
                            "backend completed arguments with a conflicting tool name"
                        )
                    if st.get("closed"):
                        completed_item = st.get("completed_item")
                        completed_done = None
                        if isinstance(completed_item, dict):
                            completed_done = (
                                completed_item.get("name"),
                                completed_item.get("arguments"),
                            )
                        if canonical_done == completed_done:
                            st["arguments_done"] = canonical_done
                            continue
                        raise _ProtocolError(
                            "backend completed conflicting arguments after tool closure"
                        )
                    complete_args = canonical_done[1]
                    st["arguments_done"] = canonical_done
                    # v1.2.14 (R3): SANITIZE MODE emits the sanitized args as ONE
                    # input_json_delta, but only once the block is OPEN. A still-deferred
                    # tool records arguments_done now; _open_tool emits the sanitized
                    # delta when it drains. Identical replay is ignored above, so
                    # downstream sees this exact delta at most once. Sanitize-off already
                    # forwarded (open) or buffered (deferred) the deltas — nothing to emit.
                    # v1.4.8: _start_tool emits the deferred header, then this one delta.
                    if SHIM_SANITIZE_TOOLS and st["opened"]:
                        await _start_tool(st)
                    continue

                # --- an output item completed ---
                if etype == "response.output_item.done":
                    item = ev["item"]
                    item_id = item.get("id")
                    if item_id is None and item.get("type") == "function_call":
                        # v1.2.8 wire tolerance: function_call item id is optional
                        # on the wire; match the open tool by its call_id instead.
                        matched = [
                            key for key, state in tool_state.items()
                            if state["call_id"] == item.get("call_id")
                        ]
                        if len(matched) == 1:
                            item_id = matched[0]
                            log.warning(
                                "wire-divergence: output_item.done function_call missing id; matched call_id=%s",
                                _scrub_log_token(item.get("call_id")))
                        else:
                            # Distinct message: the generic "invalid item id" would
                            # mask the true cause (id absent AND call_id unmatched
                            # or ambiguous) — the diagnosability gap fix (e) closed.
                            raise _ProtocolError(
                                "backend output_item.done omitted the item id and "
                                "its call_id matched %d open tools" % len(matched))
                    item_id = _require_protocol_string(item_id, "item id")
                    prior_item = completed_item_values.get(item_id)
                    if prior_item is not None:
                        if item == prior_item:
                            continue
                        raise _ProtocolError(
                            "backend replayed a conflicting completed output item"
                        )

                    # v1.2.14 (R1): count unmodeled completed item types for
                    # observability. function_call/message/reasoning are known; any
                    # other type is still cached below but not otherwise translated.
                    if item.get("type") not in _KNOWN_ITEM_TYPES:
                        _record_unknown_wire("item_type", item.get("type"))

                    # Validate all state relationships before adding the item to the
                    # completed/cache set or emitting a fallback delta/stop.
                    if item.get("type") == "function_call":
                        st = tool_state.get(item_id)
                        if st is None:
                            raise _ProtocolError(
                                "backend completed an unknown tool output item"
                            )
                        if (
                            item["call_id"] != st["call_id"]
                            or item["name"] != st["name"]
                        ):
                            raise _ProtocolError(
                                "backend completed a tool with conflicting identity"
                            )
                        item_done = (item["name"], item["arguments"])
                        prior_done = st.get("arguments_done")
                        if prior_done is not None and item_done != prior_done:
                            raise _ProtocolError(
                                "backend completed a tool with conflicting arguments"
                            )
                        if st.get("closed"):
                            raise _ProtocolError(
                                "backend completed a tool after an inconsistent closure"
                            )

                        if prior_done is None:
                            st["arguments_done"] = item_done
                        # v1.2.14 (R3): the tool is now fully finalized on the wire.
                        # finalized lets a still-deferred tool drain as a contiguous
                        # start->delta->stop block when its turn comes.
                        st["finalized"] = True
                        st["completed_item"] = item
                        if st["opened"]:
                            # Sanitize-mode fallback: if arguments.done never fired,
                            # _close_tool -> _start_tool emits the header and the single
                            # sanitized delta from the completed item's arguments now.
                            await _close_tool(st)
                            # An active tool just closed — drain the next deferred tool.
                            await _try_open_next_tool()
                        # else: still deferred — it opens and closes on drain later.

                    completed_item_values[item_id] = item
                    completed_items.append(item)
                    continue

                # --- terminal SUCCESS/TRUNCATION events ---
                if etype in ("response.completed", "response.incomplete"):
                    r_obj = _validate_terminal_response(etype, ev.get("response"))
                    # v1.2.14 (R3.3): tolerate `output: null`/absent — fall back to the
                    # streamed/collected state (cache_items below uses completed_items
                    # when terminal_output_items is empty). `or []` covers both the
                    # null (validated-tolerated) and the missing-key cases.
                    terminal_output = r_obj.get("output") or []
                    for item in terminal_output:
                        _validate_output_item(item)
                    saw_terminal_response = True
                    terminal_seen[0] = True
                    final_status = r_obj["status"]
                    usage = r_obj.get("usage", {})
                    input_tokens = usage.get("input_tokens", input_tokens)
                    output_tokens = usage.get("output_tokens", output_tokens)
                    # V6-R1: capture the cached-prefix count alongside the token totals.
                    # input_tokens is now resolved to the OpenAI total, so the clamp guard
                    # inside _resolve_cached_tokens compares against the correct basis.
                    cached_tokens = _resolve_cached_tokens(usage, input_tokens)
                    # Actual service is terminal evidence. Never expose requested intent
                    # in message_start or infer Standard from an absent/unknown tier.
                    actual_speed = _actual_speed_from_response(r_obj)
                    # Retain only validated terminal output for one post-loop cache
                    # population. The first valid terminal is final: stop semantic
                    # consumption immediately and close the upstream context in the
                    # surrounding finally block.
                    terminal_output_items = terminal_output
                    break

                # --- terminal FAILURE event (W1) ---
                if etype == "response.failed":
                    # INTENT: a terminal response.failed means the model did NOT
                    #   finish normally — the previously-mapped "failed"->"end_turn"
                    #   stop_reason silently corrupted the session by presenting
                    #   partial content as complete. Surface the failure instead.
                    # REASONING: log only normalized type/code metadata, then break so
                    #   the post-loop handler emits a classification-derived Anthropic
                    #   `error` SSE event and terminates —
                    #   no message_delta/message_stop pretending success.
                    r_obj = ev.get("response")
                    if not isinstance(r_obj, dict):
                        raise _ProtocolError(
                            "backend response.failed event was malformed"
                        )
                    err_payload = r_obj.get("error") or r_obj.get("incomplete_details") or r_obj
                    failure_error_type, failure_message, backend_type, backend_code = \
                        _normalize_backend_error(
                            err_payload,
                            phase="upstream_stream",
                        )
                    log.error(
                        "backend stream response.failed backend_type=%s backend_code=%s anthropic_type=%s",
                        _scrub_metadata(backend_type), _scrub_metadata(backend_code),
                        failure_error_type,
                    )
                    stream_failed = True
                    break

                if etype == "error":
                    # An in-band error SSE event mid-stream (W1). Same posture as
                    # response.failed: log and surface as an Anthropic `error` event,
                    # never a clean message_stop.
                    err = ev.get("error") or ev
                    failure_error_type, failure_message, backend_type, backend_code = \
                        _normalize_backend_error(
                            err,
                            phase="upstream_stream",
                        )
                    log.error(
                        "backend stream in-band error backend_type=%s backend_code=%s anthropic_type=%s",
                        _scrub_metadata(backend_type), _scrub_metadata(backend_code),
                        failure_error_type,
                    )
                    stream_failed = True
                    break
                # v1.2.14 (R1): every handled event type above continues or breaks,
                # so anything reaching here is unhandled. Known status/lifecycle
                # events (created, in_progress, content_part.*, *_text.done, reasoning
                # summary part boundaries) are ignored silently; a genuinely unknown
                # event type is counted for observability without translation.
                if etype not in _KNOWN_EVENT_TYPES:
                    _record_unknown_wire("event_type", etype)

            # v1.2.7 terminal invariant: [DONE] and clean EOF are framing signals,
            # never proof that generation completed. Only a parsed complete terminal
            # Responses event authorizes Anthropic success terminal events.
            if not stream_failed and not saw_terminal_response:
                stream_failed = True
                failure_message = "backend stream ended without a terminal response"

            if stream_failed:
                finalized = await _finalize_stream_failure(
                    failure_message, failure_error_type)
                if finalized:
                    state = _request_state()
                    if state is not None:
                        state.stop_reason = "FAILED"
                        state.tools_called = len(tool_state)
                return

            # Populate the cache exactly once. Prefer the validated terminal output
            # when it is nonempty; otherwise use each distinct completed item collected
            # from output_item.done events.
            cache_items = terminal_output_items or completed_items
            if cache_items:
                # v1.3.3 (A2-R1): persist only on a real mutation (see the non-stream
                # call site). Same fail-open, atomic-replace write.
                if _populate_reasoning_cache(cache_items):
                    _write_reasoning_cache_state()

            # Close any still-open text/thinking blocks (tools closed at .done).
            if text_block_open:
                await emit("content_block_stop", {"type": "content_block_stop", "index": text_index})
                text_block_open = False
            if thinking_block_open:
                # Close a thinking block that never yielded to text (reasoning-only
                # turn). Emit the empty signature_delta first (see _ensure_text_open).
                await emit("content_block_delta", {"type": "content_block_delta",
                    "index": thinking_index,
                    "delta": {"type": "signature_delta", "signature": ""}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": thinking_index})
                thinking_block_open = False
            # Close the active tool that never received an output_item.done (at most one
            # is open under the R3 scheduler), then drain any still-deferred tools so
            # each becomes a complete non-overlapping tool_use block in added order.
            # v1.4.8: a held (sanitize-mode) header gets its arguments from the terminal
            # output or the buffered deltas first, or is dropped on an incomplete
            # response, so the drain never sends an empty `{}` tool call.
            for item_id in tool_added_order:
                st = tool_state[item_id]
                if st["opened"] and not st.get("closed"):
                    if not _settle_unfinished_args(item_id, st):
                        st["closed"] = True
                        log.warning("dropped a tool call whose arguments never completed "
                                    "(response status=%s)", _scrub_metadata(final_status))
                        continue
                    await _close_tool(st)
            await _drain_pending_tools()

            # v1.2.14 (R3): flush reasoning/text that arrived out of order (while a tool
            # or text block was open) as TRAILING thinking/text blocks (ratified shapes).
            # By construction all preceding blocks are now closed, so these open with
            # fresh monotonic indices and stay non-overlapping.
            if deferred_thinking:
                deferred_thinking_index = next_index
                next_index += 1
                await emit("content_block_start", {"type": "content_block_start",
                    "index": deferred_thinking_index,
                    "content_block": {"type": "thinking", "thinking": ""}})
                await emit("content_block_delta", {"type": "content_block_delta",
                    "index": deferred_thinking_index,
                    "delta": {"type": "thinking_delta", "thinking": deferred_thinking}})
                await emit("content_block_delta", {"type": "content_block_delta",
                    "index": deferred_thinking_index,
                    "delta": {"type": "signature_delta", "signature": ""}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": deferred_thinking_index})
                deferred_thinking = ""
            if deferred_text:
                deferred_text_index = next_index
                next_index += 1
                await emit("content_block_start", {"type": "content_block_start",
                    "index": deferred_text_index,
                    "content_block": {"type": "text", "text": ""}})
                await emit("content_block_delta", {"type": "content_block_delta",
                    "index": deferred_text_index,
                    "delta": {"type": "text_delta", "text": deferred_text}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": deferred_text_index})
                deferred_text = ""

            # HARDENING (empty-response guard): if neither text, thinking, nor a
            # tool call was produced, emit an empty text block so Claude Code sees
            # a valid (non-empty) content array.
            if next_index == 0:
                await emit("content_block_start", {"type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": 0})

            # HARDENING (usage robustness): prefer backend numbers; else estimate.
            if output_tokens is None:
                output_tokens = _estimate_tokens(accumulated_text)
                usage_estimated = True
            if input_tokens is None:
                input_tokens = 0
                usage_estimated = True

            # v1.2.1: feed the count_tokens calibrator ONLY when input_tokens is a
            # real backend number (not the usage_estimated fallback of 0). Pair it
            # with the inbound Anthropic body size (len(body)) for this request.
            if not usage_estimated:
                _calibrate_count_ratio(input_tokens, len(body))

            stop_reason = _stop_reason_from_status(final_status, saw_tool_use)
            state = _request_state()
            if state is not None:
                state.stop_reason = stop_reason
                state.input_tokens = input_tokens
                state.output_tokens = output_tokens
                # V6-R1: None on the estimated path (no terminal usage parsed) -> the
                # terminal record renders "-"; the /health prompt_cache counters only tick
                # on a backend-sourced usage (usage_source == "backend").
                state.cached_tokens = cached_tokens
                state.usage_source = "estimated" if usage_estimated else "backend"
                # v1.4.8: count only tool calls actually sent (a dropped one is not).
                state.tools_called = sum(1 for st in tool_state.values() if st["started"])

            # v1.2.14 (R6): stop the heartbeat before the terminal frames so no ping
            # can be written after message_delta/message_stop.
            await _stop_heartbeat()
            await emit("message_delta", {"type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                # V6-R3: always-emit Anthropic usage shape with the subtraction mapping.
                # cached_tokens is already the effective (typed, clamp-checked) value.
                "usage": _anthropic_usage_block(
                    input_tokens, output_tokens, cached_tokens, actual_speed)})
            await emit("message_stop", {"type": "message_stop"})
            # A returned ASGI send marks only send_completed. It does not prove
            # client acknowledgment or receipt. Success is fixed at this semantic
            # terminal; a later body-close disconnect cannot overwrite it.
            _mark_success()
            try:
                await send({"type": "http.response.body", "body": b"", "more_body": False})
            except _ClientDisconnected:
                pass

        except (_ProtocolError, httpx.HTTPError, TypeError,
                AttributeError, KeyError, ValueError) as e:
            # Transport, framing, controlled protocol, and narrow translation/state
            # failures after response start share one terminal-error lifecycle. Do
            # not catch asyncio.CancelledError: task cancellation remains cancellation.
            failure_type = "api_error"
            if isinstance(e, _ToolWhitespaceError):
                if whitespace_retry_failure is None:
                    _record_backend_error("api_error", backend_type="tool_argument_guard",
                                          backend_code="excessive_json_whitespace",
                                          phase="upstream_tool_arguments")
                # Stop upstream before an error send can block on the downstream.
                if stream_cm is not None:
                    owned, stream_cm = stream_cm, None
                    await _settle_stream_context(owned)
            if isinstance(e, _ToolWhitespaceError) and whitespace_retry_failure is not None:
                # v1.4.8: the retry's reopen failed; report that cause and type.
                failure_kind, failure_type = whitespace_retry_failure
            elif isinstance(e, _ProtocolError):
                failure_kind = _scrub_and_trim_body(str(e))[:200] or "backend protocol error"
            elif isinstance(e, ValueError):
                failure_kind = "backend SSE framing error"
            elif isinstance(e, httpx.HTTPError):
                _record_transport_failure(
                    e, _transport_failure_phase(e, post_stream_start=True), False,
                )
                failure_kind = "backend transport error"
            else:
                failure_kind = "backend stream translation error"
            # v1.2.8: include the scrubbed message — the exception TYPE alone made
            # the v1.2.7 field-validation incident undiagnosable from the log.
            log.error("stream failure after response start: %s: %s",
                      type(e).__name__, _scrub_and_trim_body(str(e))[:200])
            if disconnect_event.is_set():
                return
            if not started:
                await emit("message_start", {"type": "message_start", "message": {
                    "id": msg_id, "type": "message", "role": "assistant", "model": model,
                    "content": [], "stop_reason": None, "stop_sequence": None,
                    # V6-R3: always-emit cache fields (0) for a deterministic usage shape.
                    "usage": {"input_tokens": 0, "output_tokens": 0,
                              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}})
                started = True
            try:
                await _finalize_stream_failure(failure_kind, failure_type)
            except Exception:
                # A downstream write failure means the client is already gone; the
                # finally block still closes the upstream stream promptly.
                pass
        finally:
            # HARDENING: always tear down the backend stream. On client disconnect
            # this aborts the upstream request rather than leaking it.
            if stream_cm is not None:
                await _settle_stream_context(stream_cm)
                stream_cm = None
    except _ClientDisconnected:
        # Expected response-local control flow: no downstream error/success bytes.
        # The request-level finalizer owns any active stream context and watcher.
        _record_disconnect("upstream_operation")
        return


def _count_tokens_bare_model(body):
    # v1.2.2: suffix-strip discipline for the count_tokens path. Claude Code POSTs
    # the whole request envelope (including model="gpt-5.6-sol#high") here. The
    # estimate itself is byte-length based and does NOT depend on the model, so
    # this is purely to keep the "#<effort>" suffix from ever leaking out of the
    # count_tokens handler (e.g. into a future log line or a model echo) — a
    # "#"-bearing model must be stripped everywhere the model is consumed.
    # INTENT: best-effort parse; return the suffix-stripped model or None. Never
    #   raises — a malformed body just yields None (nothing to strip/log).
    try:
        req = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, AttributeError):
        return None
    if not isinstance(req, dict):
        return None
    m = req.get("model")
    if not isinstance(m, str):
        return None
    bare, _suffix = _split_effort_suffix(m)
    return bare


async def _handle_count_tokens(body, send):
    # v1.2.1: return a self-calibrated estimate instead of the naive
    # len(raw_json)//4 (which inflated realistic Claude Code envelopes ~1.6-1.9x
    # and drove premature client-side session death — see _count_tokens_estimate
    # and the v1.2.1 changelog). Never errors on a malformed body: the estimate is
    # a pure function of the inbound BYTE length, so junk/undecodable content
    # still yields a floored (>=1) number rather than a 4xx (Claude Code tolerates
    # failure here, but a calibrated estimate keeps its local budget meaningful).
    #
    # v1.2.2: strip any "#<effort>" suffix from the model on this path too, so the
    # suffix never leaks out of count_tokens handling. The estimate is UNCHANGED
    # (byte-length based, v1.2.1 calibration invariant); _count_tokens_bare_model
    # is a pure, non-raising helper whose only job is to guarantee the strip
    # discipline holds uniformly across every endpoint that reads the model.
    _bare_model = _count_tokens_bare_model(body)  # noqa: F841 — strip discipline; see above
    est = _count_tokens_estimate(len(body))
    await _send_json(send, 200, {"input_tokens": est})


async def _handle_models(send):
    # Permissive model listing in Anthropic shape (only used if Claude Code asks).
    await _send_json(send, 200, {"data": [
        {"type": "model", "id": "openai/gpt-5.6-sol", "display_name": "gpt-5.6-sol"},
        {"type": "model", "id": "openai/gpt-5.5", "display_name": "gpt-5.5"},
        {"type": "model", "id": "openai/gpt-6-astra", "display_name": "gpt-6-astra"},
        {"type": "model", "id": "openai/gpt-6-sol", "display_name": "gpt-6-sol"},
        {"type": "model", "id": "openai/gpt-6-luna", "display_name": "gpt-6-luna"},
        {"type": "model", "id": "openai/gpt-6.1-sol", "display_name": "gpt-6.1-sol"},
    ]})


# A1-R4 (v1.3.0): read-only auth-validity snapshot for /health. Derived ENTIRELY from
# auth.json presence + the access_token's JWT `exp` claim (payload decoded, never
# verified, never the signature). It NEVER returns token material — only a coarse
# state, the decoded expiry, a day count, and (for actionable states) the literal
# recovery command. This is a REPORTING mirror of the auth store: it never writes,
# never refreshes, and never touches the delegation path (delegated_refresh's domain).
# The "expiring" horizon is deliberately WIDER than the internal 5-min refresh margin
# (_TOKEN_REFRESH_MARGIN_S): that margin governs when the shim asks codex to refresh;
# this window is a USER heads-up ("subscription auth expires in N days") surfaced by
# start_shim.sh readiness and deploy-smoke, so it warns 48h ahead — enough lead time to
# run `codex login --device-auth` before work is blocked.
_AUTH_EXPIRING_WINDOW_S = 48 * 3600
_AUTH_RECOVERY_CMD = "codex login --device-auth"


def _auth_health_block():
    # INTENT: return the /health "auth" block: {state, expires_at, days_left, recovery?}.
    #   state is valid|expiring|expired|absent|unreadable on the chatgpt lane, and "n/a"
    #   on the openai (API-key) lane, which does not use the codex OAuth store.
    # REASONING: absent = no readable auth.json (CODEX_HOME unset, or the file missing/
    #   unreadable); unreadable = the file reads but yields no decodable access_token exp
    #   (malformed JSON, missing tokens/access_token, or a non-JWT/undecodable token);
    #   otherwise the exp decides expired (exp <= now) / expiring (within
    #   _AUTH_EXPIRING_WINDOW_S) / valid. `recovery` (the literal re-login command) is
    #   present ONLY for the four actionable states, never for valid or n/a.
    # CREDENTIAL SAFETY: never returns token material — only the coarse state, the
    #   decoded expiry timestamp, a day count, and a static command string. Never raises
    #   (a /health probe must not 500); every failure path degrades to absent/unreadable.
    if SHIM_BACKEND_MODE != "chatgpt":
        return {"state": "n/a"}
    if not _CODEX_AUTH_PATH or not os.access(_CODEX_AUTH_PATH, os.R_OK):
        return {"state": "absent", "expires_at": None, "days_left": None,
                "recovery": _AUTH_RECOVERY_CMD}
    try:
        with open(_CODEX_AUTH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        access = (data.get("tokens") or {}).get("access_token") if isinstance(data, dict) else None
    except (OSError, ValueError):
        access = None
    exp = _jwt_exp(access) if access else None
    if exp is None:
        return {"state": "unreadable", "expires_at": None, "days_left": None,
                "recovery": _AUTH_RECOVERY_CMD}
    now = time.time()
    try:
        remaining = exp - now
        if remaining <= 0:
            state = "expired"
        elif remaining <= _AUTH_EXPIRING_WINDOW_S:
            state = "expiring"
        else:
            state = "valid"
        block = {
            "state": state,
            "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp)),
            "days_left": round(remaining / 86400, 1),
        }
    except (OverflowError, OSError, ValueError):
        # A pathological numeric exp (corrupt/partial-write auth.json, or a non-codex
        # writer yielding a garbage-but-numeric exp) can overflow the platform time_t
        # inside time.gmtime/strftime. The file reached us and parsed, but the auth
        # data is unusable -> classify "unreadable" (an actionable state, recovery
        # command included), preserving this function's "never raises" contract.
        return {"state": "unreadable", "expires_at": None, "days_left": None,
                "recovery": _AUTH_RECOVERY_CMD}
    if state != "valid":
        block["recovery"] = _AUTH_RECOVERY_CMD
    return block


def _gpt_service_tier_health_block():
    # Stable bounded v1.3.8 health contract. Current policy is a fresh strict read and is
    # explicitly global requested state, while latest_terminal is process-local historical
    # evidence from one genuine terminal upstream object. Neither is per-session proof.
    native_fast_disabled = _GPT_FAST_NATIVE_DISABLED
    try:
        snapshot = _GPT_FAST_STORE.read(
            SHIM_BACKEND_MODE if _GPT_FAST_ROUTE_VALID else None
        )
        policy = snapshot.health_dict()
        # Preserve the persisted `enabled` fact while projecting request-effective state
        # honestly. Failed reconciliation of an unsafe/invalid state, or any missing exact
        # process boundary, cannot leave health claiming stored ON is currently active.
        if (not _GPT_FAST_ROUTE_VALID or not native_fast_disabled) and policy["effective"]:
            policy["effective"] = False
    except Exception:
        policy = {
            "status": "unreadable",
            "backend_mode": None,
            "enabled": False,
            "effective": False,
        }
    with _LATEST_TERMINAL_LOCK:
        latest = dict(_LATEST_TERMINAL) if _LATEST_TERMINAL is not None else None
    return {
        "backend_mode": SHIM_BACKEND_MODE,
        "requested_tier_vocabulary": _FAST_REQUEST_SERVICE_TIERS[SHIM_BACKEND_MODE],
        "policy": policy,
        "native_fast_disabled": native_fast_disabled,
        "latest_terminal": latest,
    }


async def _handle_health(send):
    # HARDENING: health endpoint for the manager's idempotency + --status checks.
    await _send_json(send, 200, {
        "service": SHIM_SERVICE_ID,
        "status": "ok",
        "backend": SHIM_BACKEND_BASE_URL,
        "backend_mode": SHIM_BACKEND_MODE,
        # v1.2.5: presence-only boolean — never the path/contents of the secret
        # store. True iff chatgpt mode has a READABLE auth.json (openai mode is
        # trivially True since it does not use CODEX_HOME).
        # HONEST-BOOLEAN: check actual readability, not merely CODEX_HOME being set.
        #   bool(_CODEX_AUTH_PATH) is True the moment CODEX_HOME is set even if
        #   auth.json is absent/unreadable — which contradicts the "resolvable
        #   auth.json" claim. os.access(path, R_OK) confirms the file exists AND is
        #   readable without opening it (no secret/content leak, non-crashing:
        #   returns False for a missing path).
        "codex_home_present": (
            _CODEX_AUTH_PATH is not None and os.access(_CODEX_AUTH_PATH, os.R_OK)
            if SHIM_BACKEND_MODE == "chatgpt" else True
        ),
        "version": SHIM_VERSION,
        "sanitize_tools": SHIM_SANITIZE_TOOLS,
        "reasoning_effort": SHIM_REASONING_EFFORT,
        "text_verbosity": SHIM_TEXT_VERBOSITY,
        # A1-R4 (v1.3.0): read-only auth-validity snapshot (chatgpt lane; "n/a" on the
        # openai lane). Derived from auth.json presence + JWT exp only — never token
        # material. start_shim.sh readiness/--status and deploy-smoke T0.9 consume it.
        "auth": _auth_health_block(),
        # v1.3.3 (A2-R6): reasoning-cache continuity surface — COUNTS ONLY (never entry
        # contents or call_ids). entries = current in-memory cache size; restored =
        # entries loaded from the persisted snapshot at startup (0 if none). This file is
        # shim-internal continuity state, so no reader outside the shim consumes it — the
        # surface exists for operator triage (start_shim --status, deploy-smoke).
        # v1.3.4 (V4-R7): restore-effectiveness — hits = process-cumulative reasoning-cache
        # hits since start; restored_hits = the subset whose call_id was still disk-restored
        # at hit time (direct evidence for the ~1-week cap/ceiling review). Both counts only,
        # nested here (NOT new top-level keys) so the /health top-level key set is unchanged.
        "reasoning_cache": {
            "entries": len(_REASONING_CACHE),
            "restored": _REASONING_CACHE_RESTORED,
            "hits": _REASONING_CACHE_HITS_TOTAL,
            "restored_hits": _REASONING_CACHE_RESTORED_HITS_TOTAL,
        },
        # v1.3.6 (V6-R4): prompt-cache observability — a NEW top-level block. Unlike the
        # v1.3.4 reasoning_cache fold-in, prompt_cache has no natural parent (reasoning_cache
        # is a DIFFERENT cache — reasoning-continuity blobs), so it is added as its own key.
        # This DOES change the pinned top-level key set, so _HEALTH_KEYS + the version pin
        # move in the same commit (the sanctioned, review-visible money-test extension).
        # Counts only, never content. hit-rate = cached_tokens_total / input_tokens_total.
        "prompt_cache": {
            "requests_with_usage": _PROMPT_CACHE_REQUESTS_WITH_USAGE,
            "requests_with_cached": _PROMPT_CACHE_REQUESTS_WITH_CACHED,
            "cached_tokens_total": _PROMPT_CACHE_CACHED_TOKENS_TOTAL,
            "input_tokens_total": _PROMPT_CACHE_INPUT_TOKENS_TOTAL,
        },
        "gpt_service_tier": _gpt_service_tier_health_block(),
    })


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        # Handle uvicorn lifespan protocol so startup/shutdown are clean.
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    _start_diagnostics()
                except RuntimeError:
                    # Explicit failure prevents ASGI auto-detection from continuing.
                    await send({"type": "lifespan.startup.failed",
                                "message": _DIAGNOSTICS_STARTUP_ERROR})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                if _DIAGNOSTICS is not None:
                    await asyncio.to_thread(_DIAGNOSTICS.stop)
                await send({"type": "lifespan.shutdown.complete"})
                return
        return

    if scope["type"] != "http":
        return

    path = scope.get("path", "")
    method = scope.get("method", "GET")

    if path == "/health" and method == "GET":
        await _handle_health(send)
    elif path == "/v1/messages" and method == "POST":
        # Establish correlation before the first body read so body-read disconnects
        # and every nested task/log record belong to this request lifecycle.
        state = _RequestLifecycleState()
        # v1.3.8 request-boundary snapshot: exactly one lock-free read, immediately after
        # lifecycle creation and before request_start/body read/auth. The resulting object
        # is the sole global-policy input used to build the one retry-stable payload.
        try:
            state.gpt_policy_snapshot = _GPT_FAST_STORE.read(
                SHIM_BACKEND_MODE if _GPT_FAST_ROUTE_VALID else None
            )
        except Exception:
            state.gpt_policy_snapshot = None
        token = _REQUEST_STATE.set(state)
        original_send = send

        async def observed_send(message):
            # Capture actual ASGI body handoff; headers remain outside recorder.
            _trace_event("downstream_send_start", message.get("body"),
                         asgi_type=message.get("type"), status=message.get("status"),
                         more_body=message.get("more_body"))
            try:
                await original_send(message)
            except BaseException as error:
                _trace_event("downstream_send_failure", exception=type(error).__name__)
                raise
            _trace_event("downstream_send_completed", asgi_type=message.get("type"))

        send = observed_send
        _lifecycle_event("request_start", method="POST", path="/v1/messages")
        try:
            body = await _read_body(receive)
            if not state.disconnect_observed:
                # Pass `receive` through so the handler can watch for disconnect.
                await _handle_messages(
                    body, receive, send, scope.get("headers", ()))
        except _ClientDisconnected:
            _record_disconnect(state.phase)
        except asyncio.CancelledError:
            # Task cancellation alone is not evidence that ASGI delivered an
            # http.disconnect event. Preserve cancellation without inventing a
            # disconnect lifecycle record; the centralized finalizer still emits
            # exactly one terminal and cleanup record.
            raise
        except Exception:
            _mark_error(phase=state.phase)
            raise
        finally:
            cleanup_cancellation = None
            try:
                await _settle_request_resources(state)
            except asyncio.CancelledError as cancellation:
                cleanup_cancellation = cancellation
            except Exception as error:
                _record_cleanup_result(False, type(error).__name__)
            _log_terminal_once()
            _log_cleanup_once()
            _REQUEST_STATE.reset(token)
            if cleanup_cancellation is not None:
                raise cleanup_cancellation
    elif path == "/v1/messages/count_tokens" and method == "POST":
        body = await _read_body(receive)
        await _handle_count_tokens(body, send)
    elif path.endswith("/models") and method == "GET":
        await _handle_models(send)
    else:
        await _read_body(receive)
        await _send_json(send, 404, {"type": "error", "error": {"type": "not_found_error", "message": path}})


# --- Entry point ---
if __name__ == "__main__":
    # NOTE: never log the key itself — only whether one is present. v1.2.5:
    # backend_mode + codex_home_present (presence booleans only; no secret/path).
    # Readability check mirrors /health so the two fields agree (see _handle_health).
    _codex_present = (
        _CODEX_AUTH_PATH is not None and os.access(_CODEX_AUTH_PATH, os.R_OK)
        if SHIM_BACKEND_MODE == "chatgpt" else True
    )
    log.info("shim v%s starting port=%d backend_mode=%s backend=%s strip_prefix=%r key_present=%s codex_home_present=%s sanitize_tools=%s reasoning_effort=%s text_verbosity=%s",
             SHIM_VERSION, SHIM_PORT, SHIM_BACKEND_MODE, SHIM_BACKEND_BASE_URL,
             SHIM_STRIP_MODEL_PREFIX, bool(SHIM_BACKEND_API_KEY), _codex_present,
             SHIM_SANITIZE_TOOLS, SHIM_REASONING_EFFORT, SHIM_TEXT_VERBOSITY)
    # log_config=None: keep uvicorn from clobbering our stderr handler.
    uvicorn.run(app, host="127.0.0.1", port=SHIM_PORT, log_level="warning", log_config=None)
