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
#     begun emitting to the client (fails the stream cleanly instead).
#   * Client-disconnect handling: aborts the backend request on ASGI disconnect.
#   * Usage robustness: reads usage from response.completed; if the backend omits
#     it, estimates and flags the estimate in a log line.
#   * Empty-response guard: emits one empty text block if the backend yields no
#     content at all, so Claude Code always receives a well-formed message.
#   * Structured single-line-per-request logging to stderr (never credentials or
#     bodies). The manager script (start_shim.sh) redirects stderr to the log.
#   * Backend-error diagnostics on every non-2xx: allowlisted headers + a
#     scrubbed/trimmed body slice (v1.1.1/v1.1.2, unchanged).
#   * GET /health endpoint for the manager's idempotency/status checks.
#
# Changelog:
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
#     TOKEN LAYER (the only genuinely new component; notes/09 + notes/10, live-
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
#       (SHIM_OAUTH_TOKEN_URL, SHIM_OAUTH_CLIENT_ID) are now documented in the Config
#       block here and in start_shim.sh (production leaves them unset -> hardcoded
#       codex defaults). (c) codex_home_present is now HONEST — it reflects actual
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
#   SHIM_BACKEND_MODE       backend lane selector (v1.2.5). "openai" (default) |
#                           "chatgpt". Read once at startup (case-insensitive,
#                           whitespace-trimmed). An unknown value logs ONE startup
#                           WARNING and falls back to "openai".
#                             * openai  — api.openai.com/v1 API-key lane (the
#                               original, unchanged). Auth = Bearer of
#                               SHIM_BACKEND_API_KEY (from env); default base URL
#                               https://api.openai.com/v1.
#                             * chatgpt — ChatGPT-subscription Codex backend lane.
#                               Routes to https://chatgpt.com/backend-api/codex
#                               (default; still overridable via SHIM_BACKEND_BASE_URL).
#                               Auth = Bearer of the OAuth access_token read from
#                               $CODEX_HOME/auth.json (NOT an API key); the outbound
#                               request emits ONLY the 3-header floor (authorization,
#                               content-type: application/json, accept:
#                               text/event-stream) — the backend gates on nothing
#                               else (notes/08). REQUIRES CODEX_HOME set and a
#                               readable auth.json; if either is missing the shim
#                               fails fast with the re-login message rather than
#                               inventing a default path. The request BODY, tools,
#                               and SSE handling are IDENTICAL to the openai lane —
#                               the proven v1.2.0+ Responses translator is reused
#                               unchanged; only auth + base URL differ.
#   SHIM_BACKEND_BASE_URL   default depends on SHIM_BACKEND_MODE: openai ->
#                           https://api.openai.com/v1; chatgpt ->
#                           https://chatgpt.com/backend-api/codex. An explicit env
#                           value overrides the mode default in either lane. The
#                           Responses endpoint is always {base}/responses.
#   SHIM_BACKEND_API_KEY    default: value of OPENAI_API_KEY. Used only in openai
#                           mode; ignored in chatgpt mode (the OAuth access_token
#                           is the Bearer there).
#   CODEX_HOME              (chatgpt mode only) directory holding auth.json (the
#                           codex OAuth token store, mode 0600). Compose sets it to
#                           /home/appuser/.claude/codex-daaf. In chatgpt mode the
#                           shim reads $CODEX_HOME/auth.json for the access_token
#                           and refreshes it in place when near expiry or on a 401.
#                           Never logged as a path-of-secrets; /health reports only
#                           a codex_home_present boolean (True iff auth.json is
#                           readable).
#   SHIM_OAUTH_TOKEN_URL    (chatgpt mode only) TEST/STAGING OVERRIDE for the OAuth
#                           token endpoint. Default (production) is the hardcoded
#                           https://auth.openai.com/oauth/token. Set only to point
#                           the refresh POST at a mock/staging token endpoint (the
#                           mock rig uses this); leave unset in production.
#   SHIM_OAUTH_CLIENT_ID    (chatgpt mode only) TEST/STAGING OVERRIDE for the OAuth
#                           client_id sent on refresh. Default (production) is the
#                           hardcoded codex first-party client_id. Set only for a
#                           mock/staging token endpoint that expects a different
#                           client_id; leave unset in production.
#   SHIM_STRIP_MODEL_PREFIX default "" (e.g. "openai/" to strip for api.openai.com)
#   SHIM_SANITIZE_TOOLS     default ON ("0"/"false"/"no" to disable). Strips
#                           known GPT "fill-every-optional" tool-call quirks
#                           before they reach Claude Code (see
#                           _sanitize_tool_args for the evidence-based rules).
#                           MUST be set to 0 for DAAFBench runs of shim-routed
#                           models — the benchmark measures raw model
#                           behavior. Read once at startup: that means
#                           RESTARTING the shim with the opt-out set.
#   SHIM_REASONING_EFFORT   TIER 3 of the reasoning-effort precedence chain
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
#                           max ("max" is gpt-5.6-specific). "none" disables
#                           reasoning (and, per the API, re-enables temperature —
#                           but this shim never sends temperature regardless). An
#                           unrecognized value here is ignored with a WARNING and
#                           the default applies.
#   SHIM_TEXT_VERBOSITY     Response verbosity (v1.2.4). Read once at startup like
#                           the other flags. The outbound payload ALWAYS carries
#                           text:{"verbosity": <value>}. Valid values: low | medium
#                           | high (case-insensitive; surrounding whitespace
#                           trimmed). Default "high" — parity with DAAF's
#                           warm/educational posture (same rationale as the
#                           SHIM_REASONING_EFFORT "high" default). "high" adds
#                           warmth/volume; "low" is terse. An unrecognized, empty,
#                           or whitespace-only value logs ONE startup WARNING and
#                           falls back to "high". Live-confirmed accepted by
#                           gpt-5.6-sol on /v1/responses (high/low HTTP 200, probe
#                           live_tests/18); "medium" is the documented middle value
#                           (asserted in mock, not independently live-probed here).
# =============================================================================

import os
import sys
import json
import uuid
import time
import random
import asyncio
import logging
from collections import OrderedDict

import httpx
import uvicorn

# --- Config ---
SHIM_VERSION = "1.2.5"

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
_raw_backend_mode = os.environ.get("SHIM_BACKEND_MODE", _BACKEND_MODE_DEFAULT)
_backend_mode_norm = (_raw_backend_mode or "").strip().lower()
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

# HARDENING: the backend base URL default is MODE-CONDITIONAL. openai ->
# api.openai.com/v1 (the original production target); chatgpt -> the Codex backend
# (notes/08). An explicit SHIM_BACKEND_BASE_URL env value overrides the mode
# default in EITHER lane. The Responses endpoint is always {base}/responses
# (assembled in _handle_messages) — the /responses suffix assembly is unchanged.
_BACKEND_BASE_URL_DEFAULTS = {
    "openai": "https://api.openai.com/v1",
    "chatgpt": "https://chatgpt.com/backend-api/codex",
}
SHIM_BACKEND_BASE_URL = os.environ.get(
    "SHIM_BACKEND_BASE_URL", _BACKEND_BASE_URL_DEFAULTS[SHIM_BACKEND_MODE]
).rstrip("/")
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
#   "high" is a user-locked posture choice for parity with DAAF Claude sessions.
_VERBOSITY_SUPPORTED = frozenset({"low", "medium", "high"})
_VERBOSITY_DEFAULT = "high"


def _resolve_startup_verbosity():
    # INTENT: resolve the process-wide verbosity from SHIM_TEXT_VERBOSITY once.
    # REASONING: mirror the effort-normalizer's shape (identity for a supported
    #   value; WARNING + default for anything else) but as a startup-only, no-tier
    #   resolution since verbosity has a single source.
    # WARNING semantics: distinguish "var not set at all" (the common, deliberate
    #   unset -> silent default "high") from "var IS set but to an invalid value,
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
#   through IDENTITY. A value NOT in the set is "unknown" for the tier that carried
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

# HARDENING: retry policy. Retry only on transient backend failures, and only
# before any bytes have been emitted to the client (a partially-streamed
# response cannot be safely restarted).
RETRY_STATUSES = {429, 500, 502, 503, 529}
MAX_RETRIES = 3
BACKOFF_BASE = 0.5   # seconds; doubles each attempt
BACKOFF_CAP = 8.0    # seconds; ceiling before jitter
RETRY_AFTER_CAP = 30.0  # seconds; never honor an absurd Retry-After

# v1.1.1: backend-error diagnostics. The status code alone cannot tell an
# operator whether a 429 is insufficient_quota (unfunded project) or
# rate_limit_exceeded (tier TPM/RPM), nor surface retry-after guidance — that
# information lives in the JSON error body and the x-ratelimit-* headers. On
# every backend non-2xx we log a bounded slice of both.
ERR_BODY_MAXLEN = 500  # chars; truncate the logged error body to keep lines bounded
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
)
# Defense in depth: even though the allowlist excludes Authorization, a backend
# could conceivably echo a secret inside its JSON error body. Compiled once at
# import.
#
# v1.1.2: broaden beyond OpenAI `sk-` keys. Match the common secret prefixes
# {sk, rk, org, proj, sess} followed by either separator, case-insensitively.
# ASSUMES: the >=8 trailing-char floor plus the leading \b and mandatory
#   separator keep this from over-matching normal prose. The floor captures
#   every real credential (OpenAI keys are 40+ chars) while excluding short
#   hyphenated tokens common in prose.
import re
_SK_KEY_RE = re.compile(r"(?i)\b(sk|rk|org|proj|sess)[-_][A-Za-z0-9_-]{8,}")

# v1.2.2 hardening: control-character scrubber for the bare model string. The
# model is logged verbatim as `model=%s` (grep-stable), so C0/DEL control bytes in
# an inbound model could forge log lines (log injection). Strip \x00-\x1f and \x7f.
# Compiled once at import. See _split_effort_suffix for the injection vector.
_SCRUB_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")

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


def _cache_reasoning(call_id, reasoning_item):
    # INTENT: store one reasoning item under a function_call's call_id, LRU-style.
    # REASONING: move-to-end on write so the most recently paired call_ids evict
    #   last; a session's active tool loop stays warm.
    if not call_id or not isinstance(reasoning_item, dict):
        return
    _REASONING_CACHE[call_id] = reasoning_item
    _REASONING_CACHE.move_to_end(call_id)
    while len(_REASONING_CACHE) > _REASONING_CACHE_CAP:
        _REASONING_CACHE.popitem(last=False)  # evict oldest


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
    current_reasoning = None
    for item in output_items or []:
        if not isinstance(item, dict):
            continue
        itype = item.get("type")
        if itype == "reasoning":
            current_reasoning = item
        elif itype == "function_call":
            if current_reasoning is not None:
                _cache_reasoning(item.get("call_id"), current_reasoning)


# HARDENING: structured logging to stderr ONLY. The manager script redirects
# stderr to the log file. No FileHandler here and, critically, no credential or
# body logging anywhere.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("shim")

# v1.2.5: emit the deferred SHIM_BACKEND_MODE warning now that `log` exists (the
# value was resolved above, before logging was configured). Fires ONCE for an
# invalid value; silent for a valid one.
if _backend_mode_warn is not None:
    log.warning(_backend_mode_warn)

# v1.2.4: resolve the process-wide response verbosity now that `log` exists (the
# resolver emits its one WARNING via `log` for an invalid value). Read once at
# startup; the hot path just reads this constant into text:{"verbosity": ...}.
SHIM_TEXT_VERBOSITY = _resolve_startup_verbosity()

# Shared async client (connection pooling; long read timeout for slow models).
_client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0))


# --- v1.2.5: ChatGPT-subscription OAuth token layer (chatgpt mode ONLY) ---
# INTENT: in chatgpt mode the Bearer is the OAuth access_token from
#   $CODEX_HOME/auth.json, not an api.openai.com API key. The access_token TTL is
#   ~10 days (notes/09 A), so within any DAAF session the shim refreshes ~never:
#   this layer is READ-MOSTLY. It reads the access_token, sends it as Bearer, and
#   refreshes ONLY when the JWT `exp` is within a 30-min safety margin OR on a
#   backend 401 (lazy). Refresh rotates the refresh_token (notes/10) and MUST
#   persist atomically; a guarded reload-before-refresh (notes/09 B2, codex
#   manager.rs:2388) skips the refresh when another writer already produced a
#   newer on-disk token. All own-refreshes are serialized by an asyncio.Lock.
# CREDENTIAL SAFETY: no token value is ever logged. Writing token values INTO
#   auth.json (0600) is the intended credential-store operation, not a leak.
#   Presence is checked with `if not tok:` guards, never by printing.

# OAuth refresh endpoint + client_id (first-party, notes/09 B). Both are the codex
# constants; env-overridable purely for testing (the mock rig points them at a
# local mock token endpoint). Real production leaves them unset -> these defaults.
_OAUTH_TOKEN_URL = os.environ.get(
    "SHIM_OAUTH_TOKEN_URL", "https://auth.openai.com/oauth/token"
)
_OAUTH_CLIENT_ID = os.environ.get(
    "SHIM_OAUTH_CLIENT_ID", "app_EMoamEEZ73f0CkXaXp7hrann"
)
# Refresh when the access_token is within this many seconds of its `exp` (notes/09
# F: 30-min safety margin — deliberately wider than codex's 5-min window because a
# DAAF session is long and a mid-turn expiry is worse than a slightly-early refresh).
_TOKEN_REFRESH_MARGIN_S = 30 * 60
# Actionable message surfaced on a permanent refresh failure or a missing/unreadable
# auth store. No secret content — just the recovery instruction (notes/09 B/F).
_RELOGIN_MSG = ("ChatGPT OAuth token refresh failed permanently; run "
                "'codex login --device-auth' inside the container to re-authenticate")

# In-process serialization of our OWN refreshes (the shim is async; concurrent
# requests must not each fire a refresh). Per-process only — cross-process
# coordination is the guarded reload-before-refresh below (notes/09 B2).
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


def _codex_last_refresh_now():
    # INTENT: produce a `last_refresh` timestamp string matching codex's EXACT
    #   format so an external codex reload treats our write as well-formed.
    # REASONING: codex writes RFC3339 UTC with 9-digit (nanosecond) fractional
    #   seconds + trailing "Z" (chrono's DateTime<Utc>::to_rfc3339() default,
    #   notes/10). Python's datetime sources only microseconds (6 digits), so we
    #   format to microseconds and zero-pad the fractional field to 9 digits.
    # ASSUMES: nanosecond-precision beyond microseconds is not required for
    #   correctness — codex only parses the field; the padding matches its STRING
    #   shape (notes/10 wrote 2026-07-15T00:46:57.074803000Z this exact way).
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # e.g. 2026-07-15T00:46:57.074803 -> pad microseconds (6) to nanoseconds (9).
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + ("%06d000" % now.microsecond) + "Z"


def _atomic_write_auth_json(new_data):
    # INTENT: persist the updated auth.json ATOMICALLY, mode 0600, in the SAME
    #   directory as the real file (same-fs rename requirement for os.replace).
    # REASONING: temp file in the same dir -> chmod 0600 on the temp -> os.replace()
    #   (atomic same-fs rename). This fixes the torn-write hazard codex itself has
    #   (notes/09 B2) — a reader never sees a partial file. Live-validated write
    #   path (notes/10). The temp is uniquely named to avoid colliding with a
    #   concurrent writer's temp.
    # CREDENTIAL SAFETY: writing token values into the 0600 store is the INTENDED
    #   operation, not a leak. Nothing is logged here.
    import tempfile
    d = os.path.dirname(_CODEX_AUTH_PATH)
    fd, tmp = tempfile.mkstemp(prefix=".auth.json.tmp.", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(new_data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, _CODEX_AUTH_PATH)  # atomic same-fs rename
    except Exception:
        # Best-effort cleanup of the temp on any failure so we never leave a
        # partial credential file behind.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


async def _refresh_tokens(current):
    # INTENT: exchange the current refresh_token for a fresh token set, persist the
    #   rotated tokens atomically, and update in-memory state. Returns the new
    #   access_token.
    # REASONING: POST _OAUTH_TOKEN_URL with client_id + grant_type=refresh_token +
    #   the current refresh_token. On HTTP 200 the response carries a ROTATED
    #   refresh_token (notes/10) plus new access_token/id_token; we MUST persist the
    #   rotation or a later reuse of the consumed refresh_token triggers a permanent
    #   refresh_token_reused lockout (notes/09 B). Deserialize LENIENTLY — the live
    #   response also carries undocumented fields (earliest_refresh_at, oai_is) that
    #   we tolerate/ignore (notes/10). We do NOT honor earliest_refresh_at for
    #   scheduling; the shim keys refresh decisions on the live JWT `exp` claim.
    # FAST-FAIL: a non-200, or a 200 missing access_token, is a permanent failure
    #   for this session — raise RuntimeError(_RELOGIN_MSG). We do NOT spin.
    # CREDENTIAL SAFETY: the refresh_token/access_token/id_token are handled
    #   in-memory and written into auth.json only; never logged. The request body
    #   contains the refresh_token — httpx does not log bodies, and we never print it.
    tokens = current.get("tokens") or {}
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("auth.json has no refresh_token; " + _RELOGIN_MSG)
    payload = {
        "client_id": _OAUTH_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        # TIMEOUT: this single OAuth POST gets a DEDICATED short timeout, NOT the
        #   shared _client's 600s read window.
        # REASONING: _refresh_tokens runs inside _token_refresh_lock; a hung
        #   auth.openai.com would otherwise hold that lock for up to 600s and stall
        #   every concurrent chatgpt-lane request behind it. The OAuth token
        #   endpoint is a fast, small JSON exchange — 10s connect / 30s read is
        #   generous for it while capping the worst-case lock hold. On timeout httpx
        #   raises httpx.HTTPError (TimeoutException is a subclass), which the
        #   existing except-clause converts to a clean RuntimeError(_RELOGIN_MSG),
        #   releasing the lock via the `async with` in _get_access_token.
        r = await _client.post(_OAUTH_TOKEN_URL, json=payload,
                               headers={"Content-Type": "application/json"},
                               timeout=httpx.Timeout(30.0, connect=10.0))
    except httpx.HTTPError as e:
        # A transport error is not necessarily permanent, but we do not retry-spin
        # a refresh (rare path); surface it as a clean failure for this attempt.
        raise RuntimeError("token refresh transport error (%s); %s"
                           % (type(e).__name__, _RELOGIN_MSG))
    if r.status_code != 200:
        # Permanent: refresh_token_reused, invalid_grant, etc. Do NOT log the body
        # (may echo token fragments); log only the status.
        log.error("token refresh failed status=%d (permanent); %s",
                  r.status_code, _RELOGIN_MSG)
        raise RuntimeError(_RELOGIN_MSG)
    try:
        resp = r.json()
    except ValueError:
        raise RuntimeError("token refresh returned non-JSON; " + _RELOGIN_MSG)
    new_access = resp.get("access_token")
    new_refresh = resp.get("refresh_token")   # ROTATED — differs from the input
    new_id = resp.get("id_token")
    if not new_access:
        raise RuntimeError("token refresh response missing access_token; " + _RELOGIN_MSG)

    # Build the new auth.json preserving the fields codex owns, updating only the
    # rotated tokens + last_refresh. Lenient: unknown response fields are ignored.
    new_data = dict(current)  # shallow copy preserves OPENAI_API_KEY/auth_mode/etc.
    new_tokens = dict(tokens)  # preserves tokens.account_id (not returned by refresh)
    new_tokens["access_token"] = new_access
    if new_refresh:
        new_tokens["refresh_token"] = new_refresh
    if new_id:
        new_tokens["id_token"] = new_id
    new_data["tokens"] = new_tokens
    new_data["last_refresh"] = _codex_last_refresh_now()
    _atomic_write_auth_json(new_data)

    _token_state["access_token"] = new_access
    _token_state["exp"] = _jwt_exp(new_access)
    # SAFETY: log ONLY the fact of a refresh and the new expiry (a unix ts / ISO is
    # NOT a secret); never the token itself.
    log.info("chatgpt token refreshed (new exp=%s)", _token_state["exp"])
    return new_access


async def _get_access_token(force_refresh=False, rejected_token=None):
    # INTENT: return a currently-valid access_token for the chatgpt-lane Bearer.
    #   Refresh (guarded reload -> POST -> rotate -> atomic persist) only when the
    #   token is within _TOKEN_REFRESH_MARGIN_S of exp, OR when force_refresh is set
    #   (the lazy-401 path forces one refresh regardless of exp).
    # REASONING (read-mostly): the common path reads auth.json (or the cached
    #   in-memory token), checks exp, and returns the Bearer with NO network call —
    #   the ~10-day TTL means this is the path ~always taken. Only near-expiry or a
    #   401 triggers the refresh branch, which is serialized by _token_refresh_lock.
    # GUARDED RELOAD-BEFORE-REFRESH (notes/09 B2, codex manager.rs:2388): inside the
    #   lock we re-read auth.json; if another writer (codex CLI/plugin) already
    #   rotated the on-disk token, adopt it and SKIP our own refresh — this avoids
    #   consuming (and rotating away) a refresh_token another process just replaced.
    #   The comparison differs by path (see below): the proactive path keys on exp
    #   margin; the lazy-401 path keys on TOKEN IDENTITY vs. the rejected token,
    #   because a 401'd token can still be far from its nominal exp (it was rejected
    #   server-side, so exp margin cannot decide whether a refresh is needed).
    # CREDENTIAL SAFETY: token values live in memory / auth.json only; never logged.
    now = time.time()

    # Fast path (no lock): a cached in-memory token that is comfortably valid and no
    # forced refresh -> return it directly.
    if not force_refresh:
        cached = _token_state["access_token"]
        cached_exp = _token_state["exp"]
        if cached and cached_exp is not None and cached_exp - now > _TOKEN_REFRESH_MARGIN_S:
            return cached

    async with _token_refresh_lock:
        # Re-read from disk under the lock (this IS the guarded reload). This picks
        # up any external writer's refresh and is the authoritative current state.
        current = _read_auth_json()
        disk_access = (current.get("tokens") or {}).get("access_token")
        disk_exp = _jwt_exp(disk_access)

        # Adopt the on-disk token into memory (it is at least as fresh as ours).
        if disk_access:
            _token_state["access_token"] = disk_access
            _token_state["exp"] = disk_exp

        if force_refresh:
            # Lazy-401 path. Guarded reload by TOKEN IDENTITY (not exp margin): if the
            # on-disk token DIFFERS from the token the backend just rejected, another
            # writer already rotated it — adopt it and skip our refresh, retrying with
            # the fresh on-disk token first. If the on-disk token is the SAME one that
            # got 401'd (the common single-writer case), we MUST refresh — its exp
            # margin is irrelevant because the server has already rejected it.
            if (disk_access and rejected_token is not None
                    and disk_access != rejected_token):
                log.info("chatgpt 401 refresh skipped: on-disk token rotated by another writer (guarded reload)")
                return disk_access
            return await _refresh_tokens(current)

        # Proactive path: refresh only if the (authoritative on-disk) token is
        # missing or within the safety margin of exp.
        if disk_access and disk_exp is not None and disk_exp - now > _TOKEN_REFRESH_MARGIN_S:
            # Guarded reload already adopted a fresh on-disk token — no refresh.
            return disk_access
        return await _refresh_tokens(current)


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


def _flatten_tool_result_content(tr_content):
    # tool_result content may be a string OR an array of blocks. Flatten to text.
    # INTENT: the Responses `function_call_output.output` field is a plain string,
    #   so we reduce the Anthropic tool_result content to text (same flattening
    #   the chat lane used, preserved verbatim for behavioral continuity).
    if isinstance(tr_content, list):
        flat = []
        for sub in tr_content:
            if isinstance(sub, dict) and sub.get("type") == "text":
                flat.append(sub.get("text", ""))
            elif isinstance(sub, str):
                flat.append(sub)
        return "\n".join(flat)
    if isinstance(tr_content, str):
        return tr_content
    return json.dumps(tr_content)


def _messages_to_input(messages):
    # Translate Anthropic messages[] into a Responses `input[]` array, threading
    # cached reasoning items in before the function_calls they justify.
    #
    # INTENT: produce the ordered list of Responses input items:
    #   * user text          -> {"role":"user","content":[{"type":"input_text",...}]}
    #   * assistant text      -> {"type":"message","role":"assistant",
    #                             "content":[{"type":"output_text",...}]}
    #   * assistant tool_use  -> [cached reasoning item?] then
    #                             {"type":"function_call","call_id","name","arguments"}
    #   * user tool_result    -> {"type":"function_call_output","call_id","output"}
    # REASONING: assistant history content parts MUST be `output_text`, NOT
    #   `input_text` — the Responses API rejects input_text on resent assistant
    #   messages (spec file 04 §1 "Important deprecation"). Reasoning items are
    #   injected from the cache (see _REASONING_CACHE) immediately before their
    #   paired function_call so gpt-5.x's required-reasoning-item invariant holds
    #   on stateless replay.
    # ASSUMES: image/thinking/other unknown blocks are ignored gracefully (chat-
    #   lane behavior preserved). Thinking blocks that Claude Code resends from
    #   OUR own thinking emission are DROPPED here — the reasoning cache, not
    #   resent thinking text, is the continuity mechanism.
    input_items = []
    injected_reasoning_ids = set()  # dedupe: a reasoning item shared by parallel
                                    # calls is injected ONCE per request build.
    missing_reasoning = 0           # count cache misses for the request log line.

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")

        # Plain string content -> a single message item for this role.
        if isinstance(content, str):
            if role == "assistant":
                input_items.append({
                    "type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": content}],
                })
            else:
                input_items.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": content}],
                })
            continue

        text_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")

            if btype == "text":
                text_parts.append(block.get("text", ""))

        # Emit the message item (text) for this turn FIRST, so text precedes the
        # function_call items within an assistant turn (mirrors output order).
        if text_parts:
            joined = "\n".join(text_parts)
            if role == "assistant":
                input_items.append({
                    "type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": joined}],
                })
            else:
                input_items.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": joined}],
                })

        # Second pass over blocks for tool_use / tool_result (order-preserving).
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")

            if btype == "tool_use":
                call_id = block.get("id", "")
                # REASONING-CACHE INJECTION: if we have a cached reasoning item
                # for this call_id, insert it immediately BEFORE the function_call
                # (unless an equivalent reasoning item — same id — was already
                # injected for this request build; parallel calls share one).
                cached = _REASONING_CACHE.get(call_id)
                if cached is not None:
                    rs_id = cached.get("id")
                    if rs_id not in injected_reasoning_ids:
                        input_items.append(cached)
                        injected_reasoning_ids.add(rs_id)
                else:
                    # Cache miss (e.g. shim restarted mid-session, or unknown
                    # call_id). Omit the reasoning item and proceed — do NOT fail
                    # the request. Live testing will establish whether the API
                    # hard-rejects; the documented risk is the community-reported
                    # "function_call was provided without its required 'reasoning'
                    # item" error.
                    missing_reasoning += 1
                input_items.append({
                    "type": "function_call",
                    "call_id": call_id,
                    "name": block.get("name", ""),
                    # arguments is a JSON *string*, not an object.
                    "arguments": json.dumps(block.get("input", {})),
                })

            elif btype == "tool_result":
                input_items.append({
                    "type": "function_call_output",
                    "call_id": block.get("tool_use_id", ""),
                    "output": _flatten_tool_result_content(block.get("content", "")),
                })
            # Unknown block types (image, thinking) are ignored gracefully.

    return input_items, missing_reasoning


def _tools_to_responses(tools):
    # Anthropic tool: {name, description, input_schema}
    # Responses tool (FLAT / internally-tagged):
    #   {type:"function", name, description, parameters}
    # INTENT: emit the flat internally-tagged function-tool shape.
    # REASONING: the Responses API uses INTERNAL tagging — name/description/
    #   parameters are SIBLINGS of "type", NOT nested under a "function" key.
    #   The nested {"type":"function","function":{...}} shape is Chat Completions
    #   (external tagging) and is the #1 silent-failure trap in this migration
    #   (spec file 04 §1). Verified HIGH confidence, quoted from migration docs.
    if not tools:
        return None
    out = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        out.append({
            "type": "function",
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
        })
    return out


def _anthropic_to_responses_request(body, bare_model, slug_effort_raw):
    # Build the OpenAI Responses payload from an Anthropic Messages body.
    # Returns (payload, missing_reasoning_count, effort_value, effort_source).
    # v1.2.2: `bare_model` is the inbound model with any "#<effort>" suffix already
    # stripped (by _split_effort_suffix in the caller); `slug_effort_raw` is that
    # stripped suffix's raw token (tier 2). The suffix-free model is what reaches
    # the backend — a "#"-bearing model is never forwarded.
    input_items, missing_reasoning = _messages_to_input(body.get("messages", []))

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
    reasoning_obj = {"summary": "auto", "effort": effort_value}
    payload["reasoning"] = reasoning_obj

    # v1.2.4: ALWAYS carry response verbosity. text:{"verbosity": V} where V is the
    # startup-resolved SHIM_TEXT_VERBOSITY (default "high").
    # REASONING: verbosity is a whole-session posture (no inbound per-request signal
    #   exists on the Anthropic wire), so it is resolved once at startup and applied
    #   uniformly. text.verbosity is live-confirmed accepted by gpt-5.6-sol on
    #   /v1/responses (high/low HTTP 200, probe live_tests/18). Sent unconditionally
    #   for the same reason effort is: posture parity with DAAF Claude sessions.
    payload["text"] = {"verbosity": SHIM_TEXT_VERBOSITY}

    ot = _tools_to_responses(body.get("tools"))
    if ot:
        payload["tools"] = ot
        # Map Anthropic tool_choice -> Responses tool_choice where present.
        tc = body.get("tool_choice")
        if isinstance(tc, dict):
            ttype = tc.get("type")
            if ttype == "auto":
                payload["tool_choice"] = "auto"
            elif ttype == "any":
                payload["tool_choice"] = "required"
            elif ttype == "tool" and tc.get("name"):
                # FLAT name (sibling of type), not nested — spec file 04 §1.
                payload["tool_choice"] = {"type": "function", "name": tc["name"]}

    # `thinking`, `output_config`, `metadata`, `stream` (handled by transport),
    # and any unknown fields are intentionally dropped — output_config is an
    # Anthropic-inbound-only signal (its effort was consumed into reasoning.effort
    # above) and MUST NOT be forwarded to OpenAI.
    return payload, missing_reasoning, effort_value, effort_source


# --- Helpers: response translation (OpenAI Responses -> Anthropic) ---

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
    parts = []
    for s in (reasoning_item.get("summary") or []):
        if isinstance(s, dict) and s.get("type") == "summary_text":
            parts.append(s.get("text", ""))
    return "".join(parts)


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
    # Produce a single-line, bounded, credential-safe rendering of a backend
    # error body for logging.
    # INTENT: give the operator the *diagnostic content* of the error (e.g.
    #   OpenAI's {"error":{"code":"insufficient_quota",...}}) without ever
    #   leaking key material or blowing up the log with a huge/multiline body.
    # REASONING: scrub BEFORE truncation so a key that straddles the truncation
    #   boundary can't survive as a half-token; collapse whitespace so each log
    #   entry stays exactly one line (the shim's logging contract).
    # ASSUMES: `text` is already a decoded str (callers decode bytes first).
    if not text:
        return ""
    scrubbed = _SK_KEY_RE.sub("<REDACTED>", text)
    collapsed = " ".join(scrubbed.split())
    if len(collapsed) > ERR_BODY_MAXLEN:
        collapsed = collapsed[:ERR_BODY_MAXLEN] + "...[truncated]"
    return collapsed


def _diag_headers(headers):
    # Extract the allowlisted diagnostic headers into a compact "k=v k=v" string.
    # INTENT: surface rate-limit / retry-after guidance next to the error body.
    # REASONING: allowlist-only lookup means credential headers (Authorization)
    #   are structurally unreachable here — we never iterate all headers.
    # ASSUMES: `headers` is an httpx.Headers (case-insensitive .get()).
    parts = []
    for name in DIAG_HEADER_ALLOWLIST:
        val = headers.get(name)
        if val is not None:
            parts.append(f"{name}={val}")
    return " ".join(parts) if parts else "(none)"


# --- HARDENING: retry helper (UNCHANGED) ---

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


async def _post_with_retry(url, headers, payload, is_disconnected):
    # HARDENING: non-streaming POST with bounded retry on transient errors.
    # Returns (response, retry_count) on a response with status < 400 OR a
    # non-retryable status. Raises httpx.HTTPError if transport keeps failing.
    # `is_disconnected` is an async callable; if the client has gone away we
    # abort rather than burn retries on a response nobody will read. UNCHANGED.
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        if await is_disconnected():
            raise httpx.HTTPError("client disconnected before backend response")
        try:
            r = await _client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                delay = _retry_delay(attempt, None)
                log.warning("backend transport error (attempt %d/%d), retrying in %.2fs: %s",
                            attempt + 1, MAX_RETRIES + 1, delay, type(e).__name__)
                await asyncio.sleep(delay)
                continue
            raise
        if r.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            delay = _retry_delay(attempt, r.headers.get("retry-after"))
            # v1.1.1: read the body BEFORE aclose() so we can log the backend's
            # diagnostic payload on every retry attempt, not just the final one.
            # v1.1.2: wrap the buffered .text read in the same defensive
            # try/except the streaming aread() sites use.
            try:
                err_body = _scrub_and_trim_body(r.text)
            except Exception:
                err_body = "(body unavailable)"
            log.warning("backend %d (attempt %d/%d), retrying in %.2fs | headers: %s | body: %s",
                        r.status_code, attempt + 1, MAX_RETRIES + 1, delay,
                        _diag_headers(r.headers), err_body)
            await r.aclose()
            await asyncio.sleep(delay)
            continue
        return r, attempt
    # Unreachable in practice (loop returns or raises), but keeps intent explicit.
    if last_exc:
        raise last_exc
    raise httpx.HTTPError("retry loop exhausted")


# --- Non-streaming path: full Responses object -> full Anthropic message ---

def _responses_to_anthropic(resp_obj, model):
    # Translate a complete Responses response object into an Anthropic message.
    # INTENT: walk `output[]` and build the Anthropic content array in the order
    #   Claude Code expects: THINKING block (reasoning summary) FIRST, then TEXT
    #   (message output_text), then TOOL_USE (function_call, sanitized).
    # REASONING: thinking-before-text is a convergent empirical Claude Code
    #   requirement (both prior-art references, notes file 05 §3c). Populate the
    #   reasoning cache here too so a non-streaming turn seeds continuity.
    output_items = resp_obj.get("output") or []
    _populate_reasoning_cache(output_items)

    content = []
    saw_tool_use = False

    # 1) THINKING block first (concatenate all reasoning summaries in order).
    thinking_text = ""
    for item in output_items:
        if isinstance(item, dict) and item.get("type") == "reasoning":
            thinking_text += _reasoning_summary_text(item)
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
    return {
        "id": resp_obj.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": _stop_reason_from_status(status, saw_tool_use),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


# --- ASGI application ---

async def _read_body(receive):
    chunks = b""
    more = True
    while more:
        event = await receive()
        if event.get("type") == "http.disconnect":
            break
        chunks += event.get("body", b"")
        more = event.get("more_body", False)
    return chunks


async def _send_json(send, status, obj, extra_headers=None):
    payload = json.dumps(obj).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if extra_headers:
        headers.extend(extra_headers)
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({"type": "http.response.body", "body": payload})


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
    # INTENT: openai mode -> {Authorization: Bearer <env key>, Content-Type}. chatgpt
    #   mode -> the 3-header floor {authorization: Bearer <access_token>,
    #   content-type: application/json, accept: text/event-stream} the Codex backend
    #   gates on (notes/08); NO api-key/openai-specific headers.
    # REASONING: keeping this in one helper means the lazy-401 retry path can rebuild
    #   the headers (with force_token_refresh=True + the rejected token for the
    #   guarded-reload identity check) identically to the first attempt.
    # CREDENTIAL SAFETY: returns a dict CONTAINING the Bearer; callers must never log
    #   it. In chatgpt mode a token-layer failure raises RuntimeError(_RELOGIN_MSG)
    #   (no secret content) for the caller to surface as a clean client error.
    if SHIM_BACKEND_MODE == "chatgpt":
        access_token = await _get_access_token(
            force_refresh=force_token_refresh, rejected_token=rejected_token)
        return {
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }
    # openai mode (unchanged behavior).
    return {
        "Authorization": f"Bearer {SHIM_BACKEND_API_KEY}",
        "Content-Type": "application/json",
    }


async def _handle_messages(body, receive, send):
    t0 = time.time()

    # HARDENING (client-disconnect): a background reader drains the receive
    # channel and flips a flag when the client goes away, so both the retry
    # loop (non-streaming) and the streaming loop can abort the backend request.
    disconnected = {"flag": False}

    async def _watch_disconnect():
        try:
            while True:
                event = await receive()
                if event.get("type") == "http.disconnect":
                    disconnected["flag"] = True
                    return
        except asyncio.CancelledError:
            return

    async def _is_disconnected():
        return disconnected["flag"]

    # Decode Anthropic request. Malformed JSON -> 400.
    try:
        req = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        log.error("bad request json: %s", type(e).__name__)
        await _send_json(send, 400, {"type": "error", "error": {"type": "invalid_request_error", "message": "invalid JSON"}})
        return

    stream = bool(req.get("stream", False))
    # v1.2.2: strip any "#<effort>" suffix from the inbound model up front, so the
    # BARE model is used everywhere it is consumed — the outbound backend payload,
    # every log line below, and the response echoed to Claude Code. `model` from
    # here on is suffix-free; `slug_effort_raw` is the parsed tier-2 token (or None).
    model, slug_effort_raw = _split_effort_suffix(req.get("model", ""))
    responses_payload, missing_reasoning, effort_value, effort_source = \
        _anthropic_to_responses_request(req, model, slug_effort_raw)
    n_msgs = len(responses_payload["input"])
    n_tools = len(responses_payload.get("tools", []))

    # v1.2.5: build the backend auth headers by lane.
    # INTENT: in openai mode, Bearer the env API key (unchanged). In chatgpt mode,
    #   Bearer the OAuth access_token from auth.json and emit ONLY the 3-header floor
    #   the Codex backend gates on (notes/08). The request BODY/tools/SSE handling is
    #   IDENTICAL across lanes — only these headers diverge.
    # CREDENTIAL SAFETY: the token/key are placed into the header dict (which is
    #   never logged — _diag_headers is allowlist-only and excludes Authorization)
    #   but never printed. A token-layer failure surfaces as a clean client error
    #   with the re-login message, no secret content.
    # NOTE: build headers BEFORE the disconnect watcher is spawned below, so a
    # fail-fast auth error returns without needing to tear down a watcher.
    try:
        headers = await _build_backend_headers()
    except RuntimeError as e:
        # chatgpt-mode auth store missing/unreadable, or a permanent refresh
        # failure at header-build time. Fail fast with the actionable message; no
        # token value in the error (RuntimeError text is the re-login instruction).
        log.error("chatgpt auth unavailable: %s", str(e))
        await _send_json(send, 401, {"type": "error", "error": {
            "type": "authentication_error", "message": str(e)}})
        return
    url = f"{SHIM_BACKEND_BASE_URL}/responses"

    watcher = asyncio.ensure_future(_watch_disconnect())
    try:
        if not stream:
            # --- Non-streaming: one shot (with retry), translate the whole response. ---
            responses_payload["stream"] = False
            try:
                r, retries = await _post_with_retry(url, headers, responses_payload, _is_disconnected)
            except httpx.HTTPError as e:
                log.error("messages non-stream transport error: %s", type(e).__name__)
                await _send_json(send, 502, {"type": "error", "error": {"type": "api_error", "message": "backend transport error"}})
                return
            # v1.2.5: lazy-401 refresh (chatgpt lane only). A 401 from the Codex
            # backend means the access_token expired between our exp check and the
            # request; refresh ONCE, rebuild the Authorization header, and retry the
            # request a single time. A second 401 -> surface the fast-fail re-login
            # message. openai mode is untouched (SHIM_BACKEND_MODE guard).
            if SHIM_BACKEND_MODE == "chatgpt" and r.status_code == 401:
                await r.aclose()
                log.warning("chatgpt backend 401; attempting one token refresh + retry")
                _rejected = _bearer_of(headers)
                try:
                    headers = await _build_backend_headers(
                        force_token_refresh=True, rejected_token=_rejected)
                except RuntimeError as e:
                    log.error("chatgpt lazy-401 refresh failed: %s", str(e))
                    await _send_json(send, 401, {"type": "error", "error": {
                        "type": "authentication_error", "message": str(e)}})
                    return
                try:
                    r, retries = await _post_with_retry(url, headers, responses_payload, _is_disconnected)
                except httpx.HTTPError as e:
                    log.error("messages non-stream transport error (post-refresh): %s", type(e).__name__)
                    await _send_json(send, 502, {"type": "error", "error": {"type": "api_error", "message": "backend transport error"}})
                    return
                if r.status_code == 401:
                    log.error("chatgpt backend still 401 after refresh; %s", _RELOGIN_MSG)
                    await r.aclose()
                    await _send_json(send, 401, {"type": "error", "error": {
                        "type": "authentication_error", "message": _RELOGIN_MSG}})
                    return
            if r.status_code >= 400:
                # v1.1.1/1.1.2: log a scrubbed, truncated backend body + allowlisted
                # diagnostic headers so the operator can distinguish failure classes.
                try:
                    err_body = _scrub_and_trim_body(r.text)
                except Exception:
                    err_body = "(body unavailable)"
                log.error("backend error status=%d retries=%d | headers: %s | body: %s",
                          r.status_code, retries, _diag_headers(r.headers), err_body)
                try:
                    client_msg = r.text[:500]
                except Exception:
                    client_msg = "backend error (body unavailable)"
                await _send_json(send, r.status_code, {"type": "error", "error": {"type": "api_error", "message": client_msg}})
                return
            anth = _responses_to_anthropic(r.json(), model)
            usage = anth["usage"]
            # v1.2.1: feed the count_tokens calibrator. Pair the backend's
            # reported input_tokens with the inbound Anthropic body size (len(body)
            # — the raw bytes Claude Code POSTed for THIS request) so the EMA
            # learns this session's true tokens-per-byte ratio.
            _calibrate_count_ratio(usage["input_tokens"], len(body))
            dur = time.time() - t0
            # HARDENING (structured log line): one line, no bodies, no creds.
            # v1.2.2: effort=<value>:<source> surfaces the resolved reasoning effort
            # and which precedence tier won (inbound|slug|env|default). `model` is
            # the suffix-stripped slug.
            miss_suffix = f" reasoning_cache_miss={missing_reasoning}" if missing_reasoning > 0 else ""
            log.info("req method=POST path=/v1/messages model=%s stream=n msgs=%d tools=%d "
                     "dur=%.2fs stop=%s in=%s out=%s retries=%d effort=%s:%s%s",
                     model, n_msgs, n_tools, dur, anth["stop_reason"],
                     usage["input_tokens"], usage["output_tokens"], retries,
                     effort_value, effort_source, miss_suffix)
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
        text_block_open = False
        text_index = None
        # Responses stream addresses function_call argument deltas by INTERNAL
        # item_id (fc_...), NOT public call_id (both prior-art references verify
        # this — notes file 05 §3c). So key tool routing state on item_id.
        # item_id -> {"anth_index", "opened", "call_id", "name", "args_buf"}
        tool_state = {}
        # Collect the full output_items as they complete, for cache population.
        completed_items = []
        saw_tool_use = False
        final_status = "completed"
        # WARNING W1 FIX: track a terminal in-band failure separately from status.
        # On response.failed or an in-band `error` SSE event we must NOT close the
        # stream as a clean end_turn (that silently presents partial content as a
        # complete message). Instead we surface the failure to the client following
        # Anthropic streaming error semantics — an `error` SSE event — and stop.
        stream_failed = False
        failure_message = "backend stream failed"   # bounded, scrubbed at set time
        input_tokens = None
        output_tokens = None
        accumulated_text = ""        # for usage estimation fallback
        usage_estimated = False
        retries = 0

        async def emit(ev, data):
            await send({"type": "http.response.body", "body": _sse(ev, data), "more_body": True})

        async def _ensure_thinking_open():
            # Lazily open the thinking block (must be BEFORE any text/tool block).
            nonlocal thinking_block_open, thinking_index, next_index
            if not thinking_block_open:
                thinking_index = next_index
                next_index += 1
                thinking_block_open = True
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

        # HARDENING: retry the *connection* to the backend before any bytes are
        # emitted to the client. Once we've sent message_start we never retry —
        # a partially-streamed response cannot be safely restarted.
        resp = None
        stream_cm = None
        # v1.2.5: guard so the chatgpt lazy-401 refresh fires at most once per
        # stream connect. A 401 before any client bytes are on the wire is safe to
        # refresh + reconnect (message_start has NOT been emitted yet).
        did_401_refresh = False
        for attempt in range(MAX_RETRIES + 1):
            if disconnected["flag"]:
                log.info("client disconnected before stream start; aborting")
                return
            stream_cm = _client.stream("POST", url, headers=headers, json=responses_payload)
            resp = await stream_cm.__aenter__()
            # v1.2.5: lazy-401 (chatgpt lane). A 401 here means the access_token
            # expired between our exp check and this connect. Refresh ONCE, rebuild
            # the Authorization header, tear down this attempt, and reconnect — all
            # BEFORE http.response.start, so the client has seen no bytes. A second
            # 401 falls through to the error-stream branch with the re-login message.
            if (SHIM_BACKEND_MODE == "chatgpt" and resp.status_code == 401
                    and not did_401_refresh):
                log.warning("chatgpt backend stream 401; attempting one token refresh + reconnect")
                await stream_cm.__aexit__(None, None, None)
                resp = None
                did_401_refresh = True
                _rejected = _bearer_of(headers)
                try:
                    headers = await _build_backend_headers(
                        force_token_refresh=True, rejected_token=_rejected)
                except RuntimeError as e:
                    # Permanent refresh failure. Emit a clean SSE error stream below
                    # by leaving resp=None -> the error branch surfaces it. Log the
                    # actionable message (no secret content).
                    log.error("chatgpt stream lazy-401 refresh failed: %s", str(e))
                    break
                continue
            if resp.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
                delay = _retry_delay(attempt, resp.headers.get("retry-after"))
                # v1.1.1: aread() the deferred body before teardown to log the
                # backend's diagnostic payload on every retry attempt.
                try:
                    err_body = _scrub_and_trim_body(
                        (await resp.aread()).decode("utf-8", "replace"))
                except Exception:
                    err_body = "(body unavailable)"
                log.warning("backend stream %d (attempt %d/%d), retrying in %.2fs | headers: %s | body: %s",
                            resp.status_code, attempt + 1, MAX_RETRIES + 1, delay,
                            _diag_headers(resp.headers), err_body)
                await stream_cm.__aexit__(None, None, None)
                resp = None
                retries = attempt + 1
                await asyncio.sleep(delay)
                continue
            break

        # HARDENING: send the SSE response-start exactly once, before any emit().
        # Both the error-stream branch and the success branch emit a well-formed
        # Anthropic SSE stream with HTTP 200 (Claude Code reads stop_reason/error
        # from the events, not the HTTP status), so the headers are identical.
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/event-stream"),
                (b"cache-control", b"no-cache"),
                (b"connection", b"keep-alive"),
            ],
        })

        try:
            if resp is None or resp.status_code >= 400:
                status = resp.status_code if resp is not None else 502
                if resp is not None:
                    raw_err = (await resp.aread()).decode("utf-8", "replace")
                    diag_body = _scrub_and_trim_body(raw_err)
                    diag_headers = _diag_headers(resp.headers)
                else:
                    diag_body = "(no response)"
                    diag_headers = "(none)"
                log.error("backend stream error status=%d retries=%d | headers: %s | body: %s",
                          status, retries, diag_headers, diag_body)
                # Emit a minimal well-formed error stream so Claude Code fails cleanly.
                await emit("message_start", {"type": "message_start", "message": {
                    "id": msg_id, "type": "message", "role": "assistant", "model": model,
                    "content": [], "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0}}})
                await emit("content_block_start", {"type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""}})
                await emit("content_block_delta", {"type": "content_block_delta", "index": 0,
                    "delta": {"type": "text_delta", "text": f"[shim backend error {status}]"}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": 0})
                await emit("message_delta", {"type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 0}})
                await emit("message_stop", {"type": "message_stop"})
                await send({"type": "http.response.body", "body": b"", "more_body": False})
                return

            # message_start (usage filled with 0s; refined at message_delta).
            await emit("message_start", {"type": "message_start", "message": {
                "id": msg_id, "type": "message", "role": "assistant", "model": model,
                "content": [], "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0}}})
            started = True

            async for line in resp.aiter_lines():
                # HARDENING (client-disconnect mid-stream): stop pulling from the
                # backend the moment the client goes away.
                if disconnected["flag"]:
                    log.info("client disconnected mid-stream; aborting backend")
                    return
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    ev = json.loads(data_str)
                except ValueError:
                    continue

                etype = ev.get("type")

                # --- reasoning summary delta -> thinking block (BEFORE text) ---
                if etype == "response.reasoning_summary_text.delta":
                    delta = ev.get("delta", "")
                    if delta:
                        await _ensure_thinking_open()
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": thinking_index,
                            "delta": {"type": "thinking_delta", "thinking": delta}})
                    continue

                # --- text delta ---
                if etype == "response.output_text.delta":
                    delta = ev.get("delta", "")
                    if delta:
                        await _ensure_text_open()
                        accumulated_text += delta
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": text_index,
                            "delta": {"type": "text_delta", "text": delta}})
                    continue

                # --- new output item added (function_call opens a tool_use block) ---
                if etype == "response.output_item.added":
                    item = ev.get("item") or {}
                    if item.get("type") == "function_call":
                        # BLOCKER B1 FIX: close ALL open non-tool blocks before
                        # opening a tool_use block. The Anthropic streaming contract
                        # forbids overlapping content blocks — every block must run
                        # start -> deltas -> stop before the next start (verified
                        # against Anthropic's official text-then-tool streaming
                        # example). On a text-then-tool stream (common gpt-5.x
                        # pattern) BOTH a text block (index N) and this tool_use
                        # block (index N+1) would otherwise be open simultaneously.
                        # INTENT: emit content_block_stop for any open thinking/text
                        #   block and reset its open-flag, so the tool_use block that
                        #   follows is the only open block on the wire.
                        # REASONING: mirror the existing thinking-close logic (the
                        #   empty signature_delta then stop) and add the symmetric
                        #   text-close. Order preserved: thinking closes before text
                        #   (thinking precedes text within a turn). After this the
                        #   state machine can still resume text: a later
                        #   response.output_text.delta finds text_block_open False
                        #   and _ensure_text_open() opens a NEW text block with a
                        #   fresh index (it never reuses the closed index), so the
                        #   sequence thinking -> text -> tool -> text yields four
                        #   distinct, strictly-sequential block indexes.
                        if thinking_block_open:
                            # Close the thinking block directly (do NOT route through
                            # _ensure_text_open, which would open a spurious empty
                            # text block just to close thinking).
                            await emit("content_block_delta", {"type": "content_block_delta",
                                "index": thinking_index,
                                "delta": {"type": "signature_delta", "signature": ""}})
                            await emit("content_block_stop", {"type": "content_block_stop", "index": thinking_index})
                            thinking_block_open = False
                        if text_block_open:
                            await emit("content_block_stop", {"type": "content_block_stop", "index": text_index})
                            text_block_open = False
                        item_id = item.get("id") or f"fc_{uuid.uuid4().hex[:12]}"
                        anth_index = next_index
                        next_index += 1
                        st = {
                            "anth_index": anth_index,
                            "opened": False,
                            "call_id": item.get("call_id") or f"toolu_{uuid.uuid4().hex[:24]}",
                            "name": item.get("name", ""),
                            "args_buf": "",
                        }
                        tool_state[item_id] = st
                        saw_tool_use = True
                        st["opened"] = True
                        await emit("content_block_start", {"type": "content_block_start",
                            "index": anth_index,
                            "content_block": {"type": "tool_use", "id": st["call_id"],
                                              "name": st["name"], "input": {}}})
                    continue

                # --- function_call argument deltas (route by item_id) ---
                if etype == "response.function_call_arguments.delta":
                    item_id = ev.get("item_id")
                    st = tool_state.get(item_id)
                    if st is None:
                        continue  # delta for an item we never opened; ignore
                    frag = ev.get("delta", "")
                    if not frag:
                        continue
                    if SHIM_SANITIZE_TOOLS:
                        # SANITIZE MODE (default): buffer deltas; the complete
                        # string arrives in .done. Do NOT forward incrementally.
                        st["args_buf"] += frag
                    else:
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": st["anth_index"],
                            "delta": {"type": "input_json_delta", "partial_json": frag}})
                    continue

                # --- function_call arguments finalized ---
                if etype == "response.function_call_arguments.done":
                    item_id = ev.get("item_id")
                    st = tool_state.get(item_id)
                    if st is None:
                        continue
                    complete_args = ev.get("arguments", st.get("args_buf", ""))
                    if SHIM_SANITIZE_TOOLS:
                        # SANITIZE MODE: parse the complete string, sanitize, and
                        # emit as ONE input_json_delta. Simpler than the chat-lane
                        # buffer-at-close approach because .done carries the whole
                        # string directly.
                        try:
                            parsed = json.loads(complete_args or "{}")
                            parsed, dropped = _sanitize_tool_args(st["name"], parsed)
                            if dropped:
                                log.info("sanitize tool=%s dropped=%s", st["name"], ",".join(dropped))
                            out_json = json.dumps(parsed)
                        except (ValueError, TypeError):
                            # Fail-open: unparseable args pass through verbatim —
                            # sanitization must never break a working tool call.
                            log.warning("sanitize: unparseable args for tool=%s; passing through", st["name"])
                            out_json = complete_args or "{}"
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": st["anth_index"],
                            "delta": {"type": "input_json_delta", "partial_json": out_json}})
                    # Sanitize-off already forwarded the deltas; nothing to emit.
                    st["done"] = True
                    continue

                # --- an output item completed ---
                if etype == "response.output_item.done":
                    item = ev.get("item") or {}
                    if isinstance(item, dict):
                        completed_items.append(item)
                        # Close the tool_use block for a completed function_call.
                        if item.get("type") == "function_call":
                            item_id = item.get("id")
                            st = tool_state.get(item_id)
                            if st is not None and st["opened"]:
                                # Fallback: if no .done arguments event fired (some
                                # backends only put the full args on the item),
                                # emit them here under sanitize mode.
                                if SHIM_SANITIZE_TOOLS and not st.get("done"):
                                    raw = item.get("arguments", st.get("args_buf", ""))
                                    try:
                                        parsed = json.loads(raw or "{}")
                                        parsed, dropped = _sanitize_tool_args(st["name"], parsed)
                                        if dropped:
                                            log.info("sanitize tool=%s dropped=%s", st["name"], ",".join(dropped))
                                        out_json = json.dumps(parsed)
                                    except (ValueError, TypeError):
                                        log.warning("sanitize: unparseable args for tool=%s; passing through", st["name"])
                                        out_json = raw or "{}"
                                    await emit("content_block_delta", {"type": "content_block_delta",
                                        "index": st["anth_index"],
                                        "delta": {"type": "input_json_delta", "partial_json": out_json}})
                                await emit("content_block_stop", {"type": "content_block_stop", "index": st["anth_index"]})
                                st["closed"] = True
                    continue

                # --- terminal SUCCESS/TRUNCATION events ---
                if etype in ("response.completed", "response.incomplete"):
                    r_obj = ev.get("response") or {}
                    final_status = r_obj.get("status") or (
                        "incomplete" if etype == "response.incomplete" else "completed")
                    usage = r_obj.get("usage") or {}
                    if usage:
                        input_tokens = usage.get("input_tokens", input_tokens)
                        output_tokens = usage.get("output_tokens", output_tokens)
                    # Populate the reasoning cache from the full output if present
                    # in the terminal event; else from the items we collected.
                    if r_obj.get("output"):
                        _populate_reasoning_cache(r_obj["output"])
                    continue

                # --- terminal FAILURE event (W1) ---
                if etype == "response.failed":
                    # INTENT: a terminal response.failed means the model did NOT
                    #   finish normally — the previously-mapped "failed"->"end_turn"
                    #   stop_reason silently corrupted the session by presenting
                    #   partial content as complete. Surface the failure instead.
                    # REASONING: log ERROR with the existing diagnostics helper (the
                    #   scrubbed/trimmed error payload), then break so the post-loop
                    #   handler emits an Anthropic `error` SSE event and terminates —
                    #   no message_delta/message_stop pretending success.
                    r_obj = ev.get("response") or {}
                    err_payload = r_obj.get("error") or r_obj.get("incomplete_details") or r_obj
                    log.error("backend stream response.failed: %s",
                              _scrub_and_trim_body(json.dumps(err_payload)))
                    stream_failed = True
                    failure_message = _scrub_and_trim_body(json.dumps(err_payload))[:200] or "response.failed"
                    break

                if etype == "error":
                    # An in-band error SSE event mid-stream (W1). Same posture as
                    # response.failed: log and surface as an Anthropic `error` event,
                    # never a clean message_stop.
                    err = ev.get("error") or ev
                    log.error("backend stream in-band error: %s",
                              _scrub_and_trim_body(json.dumps(err))[:200])
                    stream_failed = True
                    failure_message = _scrub_and_trim_body(json.dumps(err))[:200] or "in-band stream error"
                    break
                # Any other event type is ignored gracefully.

            # W1: terminal in-band failure -> emit an Anthropic `error` SSE event
            # and terminate. Anthropic streams surface failures as `event: error`
            # with {"type":"error","error":{"type":"api_error","message":...}}.
            # We close any blocks left open before the failure so the client isn't
            # left with a dangling open block, then emit the error and stop — no
            # message_delta/message_stop, which would falsely signal success.
            # ASSUMES: Claude Code handles a mid-stream `error` event by failing the
            #   request (MEDIUM confidence, live-verifiable). The message text is
            #   bounded and scrubbed via _scrub_and_trim_body at set time.
            if stream_failed:
                if text_block_open:
                    await emit("content_block_stop", {"type": "content_block_stop", "index": text_index})
                    text_block_open = False
                if thinking_block_open:
                    await emit("content_block_delta", {"type": "content_block_delta",
                        "index": thinking_index,
                        "delta": {"type": "signature_delta", "signature": ""}})
                    await emit("content_block_stop", {"type": "content_block_stop", "index": thinking_index})
                    thinking_block_open = False
                for item_id in sorted(tool_state, key=lambda k: tool_state[k]["anth_index"]):
                    st = tool_state[item_id]
                    if st["opened"] and not st.get("closed"):
                        await emit("content_block_stop", {"type": "content_block_stop", "index": st["anth_index"]})
                        st["closed"] = True
                await emit("error", {"type": "error",
                    "error": {"type": "api_error", "message": failure_message}})
                await send({"type": "http.response.body", "body": b"", "more_body": False})
                dur = time.time() - t0
                log.info("req method=POST path=/v1/messages model=%s stream=y msgs=%d tools=%d "
                         "dur=%.2fs stop=FAILED tools_called=%d retries=%d effort=%s:%s",
                         model, n_msgs, n_tools, dur, len(tool_state), retries,
                         effort_value, effort_source)
                return

            # Fallback cache population from collected items if the terminal event
            # did not carry a full output[] array.
            if completed_items:
                _populate_reasoning_cache(completed_items)

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
            # Close any tool blocks that never received an output_item.done.
            for item_id in sorted(tool_state, key=lambda k: tool_state[k]["anth_index"]):
                st = tool_state[item_id]
                if st["opened"] and not st.get("closed"):
                    await emit("content_block_stop", {"type": "content_block_stop", "index": st["anth_index"]})
                    st["closed"] = True

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

            await emit("message_delta", {"type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}})
            await emit("message_stop", {"type": "message_stop"})
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            dur = time.time() - t0
            miss_suffix = f" reasoning_cache_miss={missing_reasoning}" if missing_reasoning > 0 else ""
            log.info("req method=POST path=/v1/messages model=%s stream=y msgs=%d tools=%d "
                     "dur=%.2fs stop=%s in=%s out=%s tools_called=%d retries=%d usage=%s effort=%s:%s%s",
                     model, n_msgs, n_tools, dur, stop_reason, input_tokens,
                     output_tokens, len(tool_state), retries,
                     "estimated" if usage_estimated else "backend",
                     effort_value, effort_source, miss_suffix)

        except httpx.HTTPError as e:
            log.error("stream transport error: %s", type(e).__name__)
            if not started:
                await _send_json(send, 502, {"type": "error", "error": {"type": "api_error", "message": "backend transport error"}})
            else:
                # Best-effort close of an already-open stream so the client isn't
                # left hanging on a half-open SSE connection.
                try:
                    await emit("message_stop", {"type": "message_stop"})
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                except Exception:
                    pass
        finally:
            # HARDENING: always tear down the backend stream. On client disconnect
            # this aborts the upstream request rather than leaking it.
            if stream_cm is not None:
                try:
                    await stream_cm.__aexit__(None, None, None)
                except Exception:
                    pass
    finally:
        watcher.cancel()
        try:
            await watcher
        except (asyncio.CancelledError, Exception):
            pass


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
    ]})


async def _handle_health(send):
    # HARDENING: health endpoint for the manager's idempotency + --status checks.
    await _send_json(send, 200, {
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
    })


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        # Handle uvicorn lifespan protocol so startup/shutdown are clean.
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
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
        body = await _read_body(receive)
        # Pass `receive` through so the handler can watch for client disconnect.
        await _handle_messages(body, receive, send)
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
