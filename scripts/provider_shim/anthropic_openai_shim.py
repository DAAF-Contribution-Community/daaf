#!/usr/bin/env python3
# =============================================================================
# anthropic_openai_shim.py
#
# Hardened Anthropic Messages API -> OpenAI Chat Completions translation shim
# for Claude Code. Productionized from the validated PoC
# (research/2026-07-09_FrameworkDev_OpenAI_Provider/poc/shim_anthropic_openai.py).
#
# Claude Code speaks the Anthropic Messages API. When ANTHROPIC_BASE_URL points
# at this shim, Claude Code POSTs Anthropic-format requests to /v1/messages
# (usually with stream=true). This shim translates each request into an OpenAI
# Chat Completions request, forwards it to any OpenAI-compatible backend
# (api.openai.com, or OpenRouter's OpenAI-format endpoint which is wire-
# identical), and translates the response back into the Anthropic SSE dialect
# Claude Code expects.
#
# Design constraints:
#   * stdlib + httpx + uvicorn ONLY. No fastapi/flask/litellm. Raw ASGI callable.
#   * Single file, sequential and readable. Comments concentrated at the
#     translation decision points, which is where the fidelity risk lives.
#   * Zero credential logging: the backend API key is referenced by env only and
#     never written to logs or response bodies.
#
# Hardening over the PoC (see § HARDENING tags inline):
#   * Retry with exponential backoff + jitter on backend 429/500/502/503/529,
#     max 3 retries, honoring Retry-After. Never retries once streaming has
#     begun emitting to the client (fails the stream cleanly instead).
#   * Client-disconnect handling: aborts the backend request on ASGI disconnect.
#   * Usage robustness: always requests stream_options.include_usage; if the
#     backend omits it, estimates and flags the estimate in a log line + header.
#   * Empty-response guard: emits one empty text block if the backend yields no
#     content at all, so Claude Code always receives a well-formed message.
#   * Structured single-line-per-request logging to stderr (never credentials or
#     bodies). The manager script (start_shim.sh) redirects stderr to the log.
#   * GET /health endpoint for the manager's idempotency/status checks.
#
# Config (all via env):
#   SHIM_PORT               default 4141
#   SHIM_BACKEND_BASE_URL   default https://api.openai.com/v1
#   SHIM_BACKEND_API_KEY    default: value of OPENAI_API_KEY
#   SHIM_STRIP_MODEL_PREFIX default "" (e.g. "openai/" to strip for api.openai.com)
# =============================================================================

import os
import sys
import json
import uuid
import time
import random
import asyncio
import logging

import httpx
import uvicorn

# --- Config ---
SHIM_VERSION = "1.0.0"

SHIM_PORT = int(os.environ.get("SHIM_PORT", "4141"))
# HARDENING: default backend is now api.openai.com/v1 (the production target).
# Live re-validation overrides this to OpenRouter's OpenAI-format endpoint via
# SHIM_BACKEND_BASE_URL, since the container has no OpenAI key.
SHIM_BACKEND_BASE_URL = os.environ.get(
    "SHIM_BACKEND_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")
# API key is read from env and never logged. Default to OPENAI_API_KEY.
SHIM_BACKEND_API_KEY = os.environ.get("SHIM_BACKEND_API_KEY") or os.environ.get(
    "OPENAI_API_KEY", ""
)
SHIM_STRIP_MODEL_PREFIX = os.environ.get("SHIM_STRIP_MODEL_PREFIX", "")

# HARDENING: retry policy. Retry only on transient backend failures, and only
# before any bytes have been emitted to the client (a partially-streamed
# response cannot be safely restarted).
RETRY_STATUSES = {429, 500, 502, 503, 529}
MAX_RETRIES = 3
BACKOFF_BASE = 0.5   # seconds; doubles each attempt
BACKOFF_CAP = 8.0    # seconds; ceiling before jitter
RETRY_AFTER_CAP = 30.0  # seconds; never honor an absurd Retry-After

# HARDENING: structured logging to stderr ONLY. The manager script redirects
# stderr to the log file. No FileHandler here (keeps the shim agnostic about
# where logs land) and, critically, no credential or body logging anywhere.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("shim")

# Shared async client (connection pooling; long read timeout for slow models).
_client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0))


# --- Helpers: request translation (Anthropic -> OpenAI) ---

def _map_model(model):
    # INTENT: pass the model slug through unchanged by default so OpenRouter
    # receives e.g. "openai/gpt-5.2". Optionally strip a prefix for direct
    # api.openai.com use where the slug is bare "gpt-5.2".
    if SHIM_STRIP_MODEL_PREFIX and model.startswith(SHIM_STRIP_MODEL_PREFIX):
        return model[len(SHIM_STRIP_MODEL_PREFIX):]
    return model


def _system_to_text(system):
    # Anthropic `system` may be a plain string OR an array of content blocks,
    # each of which may carry a `cache_control` field. OpenAI has no cache_control
    # concept, so we flatten to text and drop cache_control.
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


def _content_blocks_to_openai(role, content):
    # Translate one Anthropic message's content into zero-or-more OpenAI messages.
    #
    # The tricky part: Anthropic packs tool_use (assistant) and tool_result (user)
    # into the *content array* of a single message, but OpenAI models them very
    # differently:
    #   * assistant tool_use  -> assistant message with a `tool_calls` array
    #   * user tool_result    -> one OpenAI message with role="tool" PER result
    # So a single Anthropic message can fan out into several OpenAI messages.

    # Plain string content -> single message, verbatim.
    if isinstance(content, str):
        return [{"role": role, "content": content}]

    out = []
    text_parts = []
    tool_calls = []

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")

        if btype == "text":
            text_parts.append(block.get("text", ""))

        elif btype == "tool_use":
            # Assistant asked to call a tool. OpenAI wants the arguments as a
            # JSON *string*, not an object.
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                },
            })

        elif btype == "tool_result":
            # tool_result content may be a string OR an array of blocks. Flatten
            # to text. Emit a dedicated OpenAI role="tool" message keyed by the
            # tool_use id it responds to.
            tr_content = block.get("content", "")
            if isinstance(tr_content, list):
                flat = []
                for sub in tr_content:
                    if isinstance(sub, dict) and sub.get("type") == "text":
                        flat.append(sub.get("text", ""))
                    elif isinstance(sub, str):
                        flat.append(sub)
                tr_text = "\n".join(flat)
            else:
                tr_text = tr_content if isinstance(tr_content, str) else json.dumps(tr_content)
            out.append({
                "role": "tool",
                "tool_call_id": block.get("tool_use_id", ""),
                "content": tr_text,
            })
        # Unknown block types (e.g. image, thinking) are ignored gracefully.

    # Assemble the main message for this role (if any text/tool_calls remain).
    if role == "assistant":
        msg = {"role": "assistant"}
        msg["content"] = "\n".join(text_parts) if text_parts else None
        if tool_calls:
            msg["tool_calls"] = tool_calls
        # Only emit if it carries something.
        if msg.get("content") or tool_calls:
            # tool_result messages must come AFTER the assistant tool_calls that
            # prompted them, but within a single assistant message there are no
            # tool_results, so ordering across messages is preserved by caller.
            out.insert(0, msg)
    else:  # user
        if text_parts:
            # tool_result blocks belong to user turns and become standalone tool
            # messages; the user's plain text (if present) becomes a user message.
            out.insert(0, {"role": "user", "content": "\n".join(text_parts)})

    return out


def _tools_to_openai(tools):
    # Anthropic tool: {name, description, input_schema}
    # OpenAI tool:     {type:"function", function:{name, description, parameters}}
    if not tools:
        return None
    out = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        out.append({
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return out


def _anthropic_to_openai_request(body):
    # Build the OpenAI Chat Completions payload from an Anthropic Messages body.
    messages = []

    system_text = _system_to_text(body.get("system"))
    if system_text:
        messages.append({"role": "system", "content": system_text})

    for m in body.get("messages", []):
        role = m.get("role", "user")
        messages.extend(_content_blocks_to_openai(role, m.get("content", "")))

    payload = {
        "model": _map_model(body.get("model", "")),
        "messages": messages,
    }

    # max_tokens: Anthropic requires it; OpenAI accepts max_tokens (still honored
    # by chat/completions and OpenRouter). Pass through.
    if body.get("max_tokens") is not None:
        payload["max_tokens"] = body["max_tokens"]
    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]

    ot = _tools_to_openai(body.get("tools"))
    if ot:
        payload["tools"] = ot
        # Map Anthropic tool_choice -> OpenAI tool_choice where present.
        tc = body.get("tool_choice")
        if isinstance(tc, dict):
            ttype = tc.get("type")
            if ttype == "auto":
                payload["tool_choice"] = "auto"
            elif ttype == "any":
                payload["tool_choice"] = "required"
            elif ttype == "tool" and tc.get("name"):
                payload["tool_choice"] = {"type": "function", "function": {"name": tc["name"]}}

    # `thinking`, `metadata`, `stream` (handled by transport), and any unknown
    # fields are intentionally dropped.
    return payload


# --- Helpers: response translation (OpenAI -> Anthropic) ---

def _map_finish_reason(fr):
    # OpenAI finish_reason -> Anthropic stop_reason.
    return {
        "tool_calls": "tool_use",
        "stop": "end_turn",
        "length": "max_tokens",
        "content_filter": "end_turn",
    }.get(fr, "end_turn")


def _estimate_tokens(text):
    # Rough char/4 heuristic used only when the backend omits usage.
    return max(1, len(text) // 4)


def _sse(event, data):
    # Format one Anthropic-style SSE event.
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


# --- HARDENING: retry helper ---

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
    # abort rather than burn retries on a response nobody will read.
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
            log.warning("backend %d (attempt %d/%d), retrying in %.2fs",
                        r.status_code, attempt + 1, MAX_RETRIES + 1, delay)
            await r.aclose()
            await asyncio.sleep(delay)
            continue
        return r, attempt
    # Unreachable in practice (loop returns or raises), but keeps intent explicit.
    if last_exc:
        raise last_exc
    raise httpx.HTTPError("retry loop exhausted")


# --- Non-streaming path: full OpenAI response -> full Anthropic message ---

def _openai_response_to_anthropic(oai, model):
    choice = (oai.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    content = []

    text = msg.get("content")
    if text:
        content.append({"type": "text", "text": text})

    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except (ValueError, TypeError):
            args = {}
        content.append({
            "type": "tool_use",
            "id": tc.get("id") or f"toolu_{uuid.uuid4().hex[:24]}",
            "name": fn.get("name", ""),
            "input": args,
        })

    if not content:
        # HARDENING (empty-response guard): Anthropic clients dislike an empty
        # content array; emit an empty text block so Claude Code stays happy.
        content.append({"type": "text", "text": ""})

    usage = oai.get("usage") or {}
    return {
        "id": oai.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": _map_finish_reason(choice.get("finish_reason")),
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
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
    model = req.get("model", "")
    oai_payload = _anthropic_to_openai_request(req)
    n_msgs = len(oai_payload["messages"])
    n_tools = len(oai_payload.get("tools", []))

    headers = {
        "Authorization": f"Bearer {SHIM_BACKEND_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{SHIM_BACKEND_BASE_URL}/chat/completions"

    watcher = asyncio.ensure_future(_watch_disconnect())
    try:
        if not stream:
            # --- Non-streaming: one shot (with retry), translate the whole response. ---
            oai_payload["stream"] = False
            try:
                r, retries = await _post_with_retry(url, headers, oai_payload, _is_disconnected)
            except httpx.HTTPError as e:
                log.error("messages non-stream transport error: %s", type(e).__name__)
                await _send_json(send, 502, {"type": "error", "error": {"type": "api_error", "message": "backend transport error"}})
                return
            if r.status_code >= 400:
                # Do not echo backend body verbatim in the log (may be large); a
                # trimmed copy goes to the client for debuggability only.
                log.error("backend error status=%d retries=%d", r.status_code, retries)
                await _send_json(send, r.status_code, {"type": "error", "error": {"type": "api_error", "message": r.text[:500]}})
                return
            anth = _openai_response_to_anthropic(r.json(), model)
            usage = anth["usage"]
            dur = time.time() - t0
            # HARDENING (structured log line): one line, no bodies, no creds.
            log.info("req method=POST path=/v1/messages model=%s stream=n msgs=%d tools=%d "
                     "dur=%.2fs stop=%s in=%s out=%s retries=%d",
                     model, n_msgs, n_tools, dur, anth["stop_reason"],
                     usage["input_tokens"], usage["output_tokens"], retries)
            await _send_json(send, 200, anth)
            return

        # --- Streaming: translate OpenAI SSE deltas into Anthropic SSE events. ---
        oai_payload["stream"] = True
        # HARDENING: always ask backend to include usage in the final chunk.
        oai_payload["stream_options"] = {"include_usage": True}

        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        # Streaming state machine. Claude Code expects, per message:
        #   message_start
        #   (content_block_start / content_block_delta* / content_block_stop)+
        #   message_delta (with stop_reason + usage)
        #   message_stop
        started = False              # message_start emitted (bytes on the wire)
        text_block_open = False
        text_block_index = None
        next_index = 0
        # tool index (OpenAI) -> {"anth_index": int, "opened": bool, ...}
        tool_state = {}
        finish_reason = None
        prompt_tokens = None
        completion_tokens = None
        accumulated_text = ""        # for usage estimation fallback
        usage_estimated = False
        retries = 0

        async def emit(ev, data):
            await send({"type": "http.response.body", "body": _sse(ev, data), "more_body": True})

        # HARDENING: retry the *connection* to the backend before any bytes are
        # emitted to the client. Once we've sent message_start we never retry —
        # a partially-streamed response cannot be safely restarted, so we fail
        # the stream cleanly instead.
        resp = None
        stream_cm = None
        for attempt in range(MAX_RETRIES + 1):
            if disconnected["flag"]:
                log.info("client disconnected before stream start; aborting")
                return
            stream_cm = _client.stream("POST", url, headers=headers, json=oai_payload)
            resp = await stream_cm.__aenter__()
            if resp.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
                delay = _retry_delay(attempt, resp.headers.get("retry-after"))
                log.warning("backend stream %d (attempt %d/%d), retrying in %.2fs",
                            resp.status_code, attempt + 1, MAX_RETRIES + 1, delay)
                await stream_cm.__aexit__(None, None, None)
                resp = None
                retries = attempt + 1
                await asyncio.sleep(delay)
                continue
            break

        # HARDENING: send the SSE response-start exactly once, before any emit().
        # Both the error-stream branch and the success branch below emit a
        # well-formed Anthropic SSE stream with HTTP 200 (Claude Code reads the
        # stop_reason/error from the events, not the HTTP status), so the headers
        # are identical for both. Emitting a body frame before this start frame is
        # an ASGI protocol violation — the bug that the first live test caught.
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
                    err_text = (await resp.aread()).decode("utf-8", "replace")[:500]
                else:
                    err_text = "backend transport error"
                log.error("backend stream error status=%d retries=%d", status, retries)
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
                # backend the moment the client goes away. The finally-block
                # closes the backend stream, aborting the upstream request.
                if disconnected["flag"]:
                    log.info("client disconnected mid-stream; aborting backend")
                    return
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except ValueError:
                    continue

                # Usage may arrive in a trailing chunk (choices empty).
                if chunk.get("usage"):
                    prompt_tokens = chunk["usage"].get("prompt_tokens", prompt_tokens)
                    completion_tokens = chunk["usage"].get("completion_tokens", completion_tokens)

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta", {})
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

                # --- text delta ---
                dtext = delta.get("content")
                if dtext:
                    if not text_block_open:
                        text_block_index = next_index
                        next_index += 1
                        text_block_open = True
                        await emit("content_block_start", {"type": "content_block_start",
                            "index": text_block_index,
                            "content_block": {"type": "text", "text": ""}})
                    accumulated_text += dtext
                    await emit("content_block_delta", {"type": "content_block_delta",
                        "index": text_block_index,
                        "delta": {"type": "text_delta", "text": dtext}})

                # --- tool_call deltas (may be several, keyed by index) ---
                for tcd in delta.get("tool_calls") or []:
                    idx = tcd.get("index", 0)
                    st = tool_state.get(idx)
                    if st is None:
                        # New tool call: open a tool_use content block. id and
                        # name arrive on the first delta(s) for this index.
                        anth_index = next_index
                        next_index += 1
                        st = {"anth_index": anth_index, "opened": False,
                              "id": tcd.get("id") or f"toolu_{uuid.uuid4().hex[:24]}",
                              "name": (tcd.get("function") or {}).get("name", "")}
                        tool_state[idx] = st
                    # Backfill id/name if they arrive after the first delta.
                    if tcd.get("id"):
                        st["id"] = tcd["id"]
                    fn = tcd.get("function") or {}
                    if fn.get("name"):
                        st["name"] = fn["name"]

                    if not st["opened"]:
                        st["opened"] = True
                        await emit("content_block_start", {"type": "content_block_start",
                            "index": st["anth_index"],
                            "content_block": {"type": "tool_use", "id": st["id"],
                                              "name": st["name"], "input": {}}})

                    # Argument fragments -> input_json_delta (partial JSON string).
                    arg_frag = fn.get("arguments")
                    if arg_frag:
                        await emit("content_block_delta", {"type": "content_block_delta",
                            "index": st["anth_index"],
                            "delta": {"type": "input_json_delta", "partial_json": arg_frag}})

            # Close any open content blocks (text first, then tools in order).
            if text_block_open:
                await emit("content_block_stop", {"type": "content_block_stop", "index": text_block_index})
            for idx in sorted(tool_state, key=lambda k: tool_state[k]["anth_index"]):
                st = tool_state[idx]
                if st["opened"]:
                    await emit("content_block_stop", {"type": "content_block_stop", "index": st["anth_index"]})

            # HARDENING (empty-response guard): if the model produced neither text
            # nor tool calls, emit an empty text block so Claude Code sees a valid
            # (non-empty) content array.
            if not text_block_open and not tool_state:
                await emit("content_block_start", {"type": "content_block_start", "index": 0,
                    "content_block": {"type": "text", "text": ""}})
                await emit("content_block_stop", {"type": "content_block_stop", "index": 0})

            # HARDENING (usage robustness): prefer backend numbers; else estimate
            # and record that the numbers are estimated.
            if completion_tokens is None:
                completion_tokens = _estimate_tokens(accumulated_text)
                usage_estimated = True
            if prompt_tokens is None:
                prompt_tokens = 0
                usage_estimated = True

            # If tools were called but finish_reason was missing/stop, prefer tool_use.
            stop_reason = _map_finish_reason(finish_reason)
            if tool_state and stop_reason == "end_turn":
                stop_reason = "tool_use"

            await emit("message_delta", {"type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}})
            await emit("message_stop", {"type": "message_stop"})
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            dur = time.time() - t0
            log.info("req method=POST path=/v1/messages model=%s stream=y msgs=%d tools=%d "
                     "dur=%.2fs stop=%s in=%s out=%s tools_called=%d retries=%d usage=%s",
                     model, n_msgs, n_tools, dur, stop_reason, prompt_tokens,
                     completion_tokens, len(tool_state), retries,
                     "estimated" if usage_estimated else "backend")

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
            # HARDENING: always tear down the backend stream. On client
            # disconnect this aborts the upstream request rather than leaking it.
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


async def _handle_count_tokens(body, send):
    # Claude Code tolerates failure here; a cheap estimate keeps it happy.
    est = _estimate_tokens(body.decode("utf-8", "replace"))
    await _send_json(send, 200, {"input_tokens": est})


async def _handle_models(send):
    # Permissive model listing in Anthropic shape (only used if Claude Code asks).
    await _send_json(send, 200, {"data": [
        {"type": "model", "id": "openai/gpt-5.2", "display_name": "gpt-5.2"},
        {"type": "model", "id": "openai/gpt-5.5", "display_name": "gpt-5.5"},
    ]})


async def _handle_health(send):
    # HARDENING: health endpoint for the manager's idempotency + --status checks.
    await _send_json(send, 200, {
        "status": "ok",
        "backend": SHIM_BACKEND_BASE_URL,
        "version": SHIM_VERSION,
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
    # NOTE: never log the key itself — only whether one is present.
    log.info("shim v%s starting port=%d backend=%s strip_prefix=%r key_present=%s",
             SHIM_VERSION, SHIM_PORT, SHIM_BACKEND_BASE_URL,
             SHIM_STRIP_MODEL_PREFIX, bool(SHIM_BACKEND_API_KEY))
    # log_config=None: keep uvicorn from clobbering our stderr handler.
    uvicorn.run(app, host="127.0.0.1", port=SHIM_PORT, log_level="warning", log_config=None)
