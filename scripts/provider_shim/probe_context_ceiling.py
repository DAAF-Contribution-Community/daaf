#!/usr/bin/env python3
"""Measure the effective backend context-window ceiling of the local provider shim.

This is a standalone, user-run diagnostic CLI (the sanctioned argparse exception to
DAAF's no-functions rule — it is not a research pipeline script and is never
executed by an agent). It POSTs Anthropic-protocol requests to the LOCAL shim and
finds the largest input the currently-configured backend lane will accept before it
returns a `context_length_exceeded` rejection.

INVOCATION (user, from the host or container shell):

    python3 /daaf/scripts/provider_shim/probe_context_ceiling.py

Common overrides:

    python3 /daaf/scripts/provider_shim/probe_context_ceiling.py \
        --base-url http://127.0.0.1:4141 --model gpt-5.6-sol

Self-test (no network I/O — exercises the message parser AND drives the real
run_live_probe bisect/parse bookkeeping against an in-process fake backend):

    python3 /daaf/scripts/provider_shim/probe_context_ceiling.py --self-test

COST NOTE: on the ChatGPT (Codex) subscription lane every accepted request spends
real quota, so the probe is deliberately cost-minimizing. It FIRST sends one
oversized request and tries to parse an explicit maximum out of the backend's
rejection message ("maximum context length is N tokens"); only if no number can be
parsed does it fall back to a binary search, and the search is biased so that
rejections (the cheap outcome) do the work and accepted (expensive) requests are
minimized. `max_tokens` is pinned to 1 so an accepted request generates almost no
output.

OBSERVED BAND (2026-09-05, Codex CLI 0.153.2, shim v1.3.19, SHIM_BACKEND_MODE=chatgpt,
ChatGPT Pro plan): the subscription lane accepted 919,053 real input tokens for
gpt-6-astra (rejecting 922,552) and 910,827 for gpt-5.6-sol (rejecting 921,973), so the
lane-wide cap DAAF accounts against is 919,000 — consistent with Astra's documented
922,000-token max input (1,050,000 window - 128,000 output). Provenance: previously
370,000 (2026-07-16), now stale. The bracket/oversize defaults below sit just
below/above that measured band.

ROBUSTNESS: the 2026-09-05 gpt-5.6-sol run also exposed a backend that answered a
~912k-token request with a bogus usage.input_tokens=42165. The probe adopted it as
truth, chars/token exploded, and the remaining bisect probed meaningless sizes. A
single reading that would change the running chars/token estimate by more than
MAX_CALIBRATION_RATIO_CHANGE-fold is now ignored with a printed warning.

COMPATIBILITY: this probe parses the rejection MESSAGE TEXT, not the HTTP status or
error `type`, so it works against both the live v1.2.8 shim (which collapses the
backend 400 to a flat `502 api_error` carrying the `context_length_exceeded` text in
the message) and v1.2.10+ (which passes the real 400 / `invalid_request_error`
through). It depends on no v1.2.10-specific behavior.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request


# --- Constants ---
# Default local shim endpoint (Anthropic-compatible /v1/messages).
DEFAULT_BASE_URL = "http://127.0.0.1:4141"
DEFAULT_MODEL = "gpt-5.6-sol"
# Live-observed bracket (session 2026-09-05): the ChatGPT lane ACCEPTED real 919,053
# tokens (gpt-6-astra) / 910,827 (gpt-5.6-sol) and REJECTED 922,552 / 921,973. The
# bisect defaults sit just below/above that band. (Session 2026-07-16 measured a much
# lower 337,034-accept / ~400k-reject band; that observation is stale.)
DEFAULT_BRACKET_LOW = 900000
DEFAULT_BRACKET_HIGH = 1000000
# The deliberately-oversized first probe: comfortably past the observed rejection
# point so the backend states its maximum in the error body.
DEFAULT_OVERSIZE_TARGET = 1150000
# Stop the bisect once the accept/reject boundary is bracketed this tightly.
DEFAULT_TOLERANCE = 3000
# Initial chars-per-token guess before the first accepted response recalibrates it.
# ~4 chars/token is a standard rough prior for English text; the probe replaces this
# with the real usage.input_tokens ratio as soon as one request is accepted.
INITIAL_CHARS_PER_TOKEN = 4.0
# When confirming a parsed ceiling, aim this many tokens BELOW it for the single
# just-under-ceiling acceptance check.
CONFIRM_MARGIN_TOKENS = 4000
# Largest fold-change in the running chars-per-token estimate that a single accepted
# response is allowed to cause. A backend that reports a wildly wrong
# usage.input_tokens (observed 2026-09-05: input_tokens=42165 for a ~912k-token
# request) would otherwise be adopted as truth and derail every subsequent target.
MAX_CALIBRATION_RATIO_CHANGE = 3.0

# Deterministic filler vocabulary — a fixed word list repeated so every run of the
# probe produces byte-identical input for a given target (reproducible probing).
_FILLER_WORDS = (
    "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima "
    "mike november oscar papa quebec romeo sierra tango uniform victor whiskey "
    "xray yankee zulu"
).split()

# Patterns that name an explicit maximum inside a backend rejection message.
_CEILING_PATTERNS = (
    re.compile(r"maximum context length is\s+([0-9][0-9,]*)\s+tokens", re.IGNORECASE),
    re.compile(r"context window of\s+([0-9][0-9,]*)\s+tokens", re.IGNORECASE),
    re.compile(r"maximum of\s+([0-9][0-9,]*)\s+tokens", re.IGNORECASE),
    re.compile(r"limit of\s+([0-9][0-9,]*)\s+tokens", re.IGNORECASE),
)

# Signals that a rejection is specifically a context-length overflow (vs. any other
# 4xx/5xx). Matched case-insensitively against the full rejection text.
_CONTEXT_EXCEEDED_MARKERS = (
    "context_length_exceeded",
    "maximum context length",
    "context length",
    "context window",
    "too many tokens",
    "reduce the length",
)


def build_filler(num_tokens, chars_per_token):
    # INTENT: build a deterministic text block whose estimated token count is
    #   approximately `num_tokens`, using the current chars-per-token estimate.
    # REASONING: repeat a fixed word list so the block is byte-identical across runs
    #   for a given (num_tokens, chars_per_token) pair; approximate the needed
    #   character length, then trim to it on a word boundary.
    target_chars = max(1, int(round(num_tokens * chars_per_token)))
    parts = []
    total = 0
    idx = 0
    while total < target_chars:
        word = _FILLER_WORDS[idx % len(_FILLER_WORDS)]
        parts.append(word)
        total += len(word) + 1  # +1 for the joining space
        idx += 1
    text = " ".join(parts)
    return text[:target_chars]


def make_request_body(model, filler, max_tokens):
    # INTENT: a minimal, non-streaming Anthropic messages request whose single user
    #   message carries the filler payload; max_tokens pinned small to avoid output
    #   cost on an accepted request.
    return {
        "model": model,
        "max_tokens": max_tokens,
        "stream": False,
        "messages": [
            {"role": "user", "content": filler},
        ],
    }


def parse_ceiling_from_message(text):
    # INTENT: pull an explicit maximum token count out of a backend rejection
    #   message, returning an int or None.
    # ASSUMES: the caller passes the full text it observed (the shim may have nested
    #   the real backend body inside its own error.message and/or truncated it to
    #   ~200 chars; the numeric maximum appears early in OpenAI-family messages, so
    #   truncation usually preserves it).
    if not text:
        return None
    for pattern in _CEILING_PATTERNS:
        match = pattern.search(text)
        if match:
            digits = match.group(1).replace(",", "")
            try:
                return int(digits)
            except ValueError:
                continue
    return None


def looks_like_context_exceeded(text):
    # INTENT: decide whether a rejection is a context-length overflow specifically.
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _CONTEXT_EXCEEDED_MARKERS)


def extract_message_text(payload):
    # INTENT: given a decoded response body (dict) OR a raw string, return the most
    #   informative human-readable text to scan for ceiling/overflow signals.
    # REASONING: the shim wraps errors as {"type":"error","error":{"message": ...}};
    #   an accepted response has no such field. Fall back to the whole JSON so a
    #   differently-shaped backend body is still searchable.
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        # Some backends put the message at the top level.
        if isinstance(payload.get("message"), str):
            return payload["message"]
        return json.dumps(payload)
    if isinstance(payload, str):
        return payload
    return ""


def classify_response(status, payload):
    # INTENT: normalize one probe response into a decision record.
    # Returns a dict:
    #   accepted            -> bool (HTTP 200 with a usable message body)
    #   real_input_tokens   -> int | None (only on an accepted response)
    #   context_exceeded    -> bool (rejection is a context-length overflow)
    #   parsed_ceiling      -> int | None (explicit maximum parsed from the message)
    #   message             -> str (the text scanned)
    message = extract_message_text(payload)
    accepted = False
    real_input_tokens = None
    if status == 200 and isinstance(payload, dict):
        # An accepted Anthropic message carries usage.input_tokens (the REAL backend
        # count — trustworthy, unlike the shim's 0.9-biased count_tokens estimate).
        usage = payload.get("usage")
        if isinstance(usage, dict) and isinstance(usage.get("input_tokens"), int):
            accepted = True
            real_input_tokens = usage["input_tokens"]
        elif payload.get("type") == "message":
            accepted = True
    context_exceeded = (not accepted) and looks_like_context_exceeded(message)
    parsed_ceiling = parse_ceiling_from_message(message) if context_exceeded else None
    return {
        "accepted": accepted,
        "real_input_tokens": real_input_tokens,
        "context_exceeded": context_exceeded,
        "parsed_ceiling": parsed_ceiling,
        "message": message,
    }


def post_probe(base_url, body, timeout):
    # INTENT: POST one Anthropic request to the local shim; return (status, payload)
    #   where payload is the decoded JSON dict when possible, else the raw text.
    # REASONING: 4xx/5xx must NOT raise — the rejection body is exactly what we need
    #   to parse — so HTTPError is caught and unwrapped like a normal response.
    url = base_url.rstrip("/") + "/v1/messages"
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as error:
        # A 4xx/5xx carries the rejection body we need to parse — unwrap it like a
        # normal response rather than raising.
        raw = error.read().decode("utf-8", "replace")
        status = error.code
    except urllib.error.URLError as error:
        # INTENT: a transport-level failure (connection refused, DNS, timeout) means
        #   the shim is DOWN — this is NOT a context-length rejection and must never
        #   update the bisect bracket. Exit cleanly with an actionable message and a
        #   nonzero code instead of surfacing an uncaught traceback.
        # REASONING: HTTPError subclasses URLError, so this except MUST be ordered
        #   after the HTTPError arm above — a real HTTP response is unwrapped there;
        #   only genuine transport failures (no response at all) reach here.
        print(
            f"[probe] ERROR: shim not reachable at {url} — is it running? "
            f"check /health ({type(error).__name__}: {error.reason})",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        payload = raw
    return status, payload


def probe_target(base_url, model, target_tokens, chars_per_token, max_tokens, timeout,
                 post_fn=post_probe):
    # INTENT: run one probe at an estimated real-token target and classify it.
    # REASONING: `post_fn` defaults to the real network POST but is injectable so the
    #   offline --self-test can drive this exact code path with an in-process fake
    #   backend (no network, no monkeypatching).
    filler = build_filler(target_tokens, chars_per_token)
    body = make_request_body(model, filler, max_tokens)
    status, payload = post_fn(base_url, body, timeout)
    record = classify_response(status, payload)
    record["target_tokens"] = target_tokens
    record["status"] = status
    record["filler_chars"] = len(filler)
    return record


def summarize_record(record):
    # INTENT: one human-readable line per request for the run log.
    if record["accepted"]:
        real = record["real_input_tokens"]
        real_str = str(real) if real is not None else "unknown"
        return (
            f"  target~{record['target_tokens']} tokens "
            f"({record['filler_chars']} chars) -> ACCEPTED "
            f"status={record['status']} real_input_tokens={real_str}"
        )
    kind = "context_length_exceeded" if record["context_exceeded"] else "other_rejection"
    ceiling = record["parsed_ceiling"]
    ceiling_str = f" parsed_max={ceiling}" if ceiling is not None else ""
    snippet = (record["message"] or "").replace("\n", " ")[:120]
    return (
        f"  target~{record['target_tokens']} tokens "
        f"({record['filler_chars']} chars) -> REJECTED "
        f"status={record['status']} kind={kind}{ceiling_str} msg=\"{snippet}\""
    )


def run_live_probe(args, post_fn=post_probe):
    # INTENT: the cost-minimizing measurement flow (parse-first, bisect-fallback).
    # REASONING: `post_fn` is injectable (defaults to the real network POST) so the
    #   offline --self-test can drive this REAL measurement + bookkeeping loop against
    #   an in-process fake backend, instead of a reimplementation that could drift.
    chars_per_token = INITIAL_CHARS_PER_TOKEN
    log_lines = []
    largest_accept = None       # largest real input_tokens observed accepted
    smallest_reject = None      # smallest estimated target observed rejected

    def record_and_log(record):
        # Returns True when the record's reported token count was trusted, False when
        # an implausible usage.input_tokens caused it to be ignored (see guard below).
        nonlocal chars_per_token, largest_accept, smallest_reject
        log_lines.append(summarize_record(record))
        if record["accepted"] and record["real_input_tokens"]:
            # Recalibrate chars-per-token from the REAL backend count so subsequent
            # targets are sized accurately (the shim's own estimate is biased low).
            observed = record["real_input_tokens"]
            candidate = max(1.0, record["filler_chars"] / observed)
            # INTENT: reject a single absurd usage.input_tokens rather than adopting it.
            # REASONING: observed live 2026-09-05 (gpt-5.6-sol) — the backend answered a
            #   ~912k-token request with input_tokens=42165, which recalibrated
            #   chars/token from ~4.4 to ~96 and sent the remaining bisect probing
            #   multi-million-character payloads that could only be rejected.
            # ASSUMES: a genuine backend tokenizer never shifts the running estimate by
            #   more than MAX_CALIBRATION_RATIO_CHANGE-fold between requests that use
            #   the same deterministic filler vocabulary.
            ratio = max(candidate / chars_per_token, chars_per_token / candidate)
            if ratio > MAX_CALIBRATION_RATIO_CHANGE:
                warning = (
                    f"  [warn] implausible usage.input_tokens={observed} for "
                    f"{record['filler_chars']} chars (chars/token "
                    f"{chars_per_token:.2f} -> {candidate:.2f}, {ratio:.1f}x change); "
                    "ignoring this reading for calibration and accept bookkeeping"
                )
                log_lines.append(warning)
                print(warning, flush=True)
                return False
            chars_per_token = candidate
            if largest_accept is None or observed > largest_accept:
                largest_accept = observed
        elif record["context_exceeded"]:
            if smallest_reject is None or record["target_tokens"] < smallest_reject:
                smallest_reject = record["target_tokens"]
        return True

    # --- Phase 1: one deliberately-oversized request; try to parse the maximum. ---
    print(f"[probe] oversized request at ~{args.oversize_target} tokens ...", flush=True)
    over = probe_target(
        args.base_url, args.model, args.oversize_target,
        chars_per_token, args.max_tokens, args.timeout, post_fn,
    )
    record_and_log(over)

    if over["accepted"]:
        # The lane accepted our "oversized" target — the ceiling is at/above it.
        # Nothing cheap left to parse; report the accepted real count as a floor.
        print("\n".join(log_lines))
        method = "parsed"  # no bisect needed; boundary is above the probed range
        est = over["real_input_tokens"] or args.oversize_target
        return est, method, largest_accept, smallest_reject, log_lines

    if over["context_exceeded"] and over["parsed_ceiling"] is not None:
        ceiling = over["parsed_ceiling"]
        # Confirm with at most ONE just-under-ceiling acceptance check.
        confirm_target = max(1, ceiling - CONFIRM_MARGIN_TOKENS)
        print(f"[probe] parsed maximum={ceiling}; confirming at ~{confirm_target} ...",
              flush=True)
        confirm = probe_target(
            args.base_url, args.model, confirm_target,
            chars_per_token, args.max_tokens, args.timeout, post_fn,
        )
        record_and_log(confirm)
        print("\n".join(log_lines))
        return ceiling, "parsed", largest_accept, smallest_reject, log_lines

    # --- Phase 2: no explicit maximum available -> biased binary search. ---
    print("[probe] no explicit maximum in rejection; falling back to bisect ...",
          flush=True)
    low = args.bracket_low     # believed-accepted floor
    high = args.bracket_high   # believed-rejected ceiling
    # The oversized rejection already gives us an upper bound if it is tighter.
    if over["context_exceeded"] and args.oversize_target < high:
        high = args.oversize_target
    ceiling_estimate = high
    while high - low > args.tolerance:
        mid = (low + high) // 2
        record = probe_target(
            args.base_url, args.model, mid,
            chars_per_token, args.max_tokens, args.timeout, post_fn,
        )
        trusted = record_and_log(record)
        if record["accepted"]:
            # Clamp to `high`: an accept whose REAL token count overshoots the current
            # ceiling (filler over-produced) must not push `low` above `high` and
            # invert the bracket — cap it so the search interval stays well-formed.
            # An untrusted (guard-rejected) token count falls back to the estimated
            # target so one bogus reading cannot collapse the bracket floor either.
            observed = record["real_input_tokens"] if trusted else None
            low = min(observed or mid, high)
        else:
            # A rejection (cheap) tightens the ceiling.
            high = mid
            ceiling_estimate = mid
    # The best ceiling estimate is the tightest confirmed-reject lower-bounded by
    # the largest confirmed-accept.
    if largest_accept is not None:
        ceiling_estimate = max(largest_accept, low)
    print("\n".join(log_lines))
    return ceiling_estimate, "bisect", largest_accept, smallest_reject, log_lines


def run_self_test():
    # INTENT: verify the probe's core deterministically with NO network I/O — the
    #   message parser/classifier directly, AND the REAL run_live_probe measurement
    #   loop (parse-first, bisect-fallback, bracket bookkeeping, chars-per-token
    #   recalibration) driven against an in-process fake backend via post_fn
    #   injection. Earlier versions reimplemented the bisect here, which gave false
    #   coverage; this drives the actual code path the live run uses.
    failures = []

    def check(name, condition):
        status = "PASS" if condition else "FAIL"
        print(f"[self-test] {status}: {name}")
        if not condition:
            failures.append(name)

    # 1. parse_ceiling_from_message on canonical OpenAI-family phrasings.
    check(
        "parse plain maximum",
        parse_ceiling_from_message(
            "This model's maximum context length is 400000 tokens. However, your "
            "messages resulted in 450123 tokens."
        ) == 400000,
    )
    check(
        "parse comma-grouped maximum",
        parse_ceiling_from_message("maximum context length is 272,000 tokens") == 272000,
    )
    check(
        "parse from v1.2.8 flat-502 nested wrapper",
        classify_response(
            502,
            {"type": "error", "error": {
                "type": "api_error",
                "message": ("This model's maximum context length is 400000 tokens, "
                            "however you requested more. code: context_length_exceeded"),
            }},
        )["parsed_ceiling"] == 400000,
    )
    check(
        "non-ceiling rejection parses to None",
        parse_ceiling_from_message("backend rejected the request") is None,
    )

    # 2. classify_response decisions.
    accepted = classify_response(
        200, {"type": "message", "usage": {"input_tokens": 337034, "output_tokens": 1}}
    )
    check("accepted response detected", accepted["accepted"] is True)
    check("accepted real tokens read", accepted["real_input_tokens"] == 337034)
    check("accepted is not context_exceeded", accepted["context_exceeded"] is False)

    rejected_502 = classify_response(
        502, {"type": "error", "error": {
            "type": "api_error", "message": "context_length_exceeded: too many tokens"}}
    )
    check("v1.2.8 flat-502 overflow detected", rejected_502["context_exceeded"] is True)

    rejected_400 = classify_response(
        400, {"type": "error", "error": {
            "type": "invalid_request_error",
            "message": "maximum context length is 400000 tokens (context_length_exceeded)"}}
    )
    check("v1.2.10 real-400 overflow detected", rejected_400["context_exceeded"] is True)
    check("v1.2.10 real-400 ceiling parsed", rejected_400["parsed_ceiling"] == 400000)

    other_400 = classify_response(
        400, {"type": "error", "error": {
            "type": "invalid_request_error", "message": "unknown field 'foo'"}}
    )
    check("unrelated 400 is not context_exceeded", other_400["context_exceeded"] is False)

    # 3. Drive the REAL run_live_probe against an in-process fake backend (no
    #    network). The fake sizes REAL backend tokens from the request's filler
    #    length using a ratio (4.5) DIFFERENT from the probe's initial 4.0 prior, so
    #    the first accepted response necessarily reports a real_input_tokens that
    #    differs from the naive target — forcing the chars-per-token recalibration
    #    (calibration path) through the actual code.
    real_cpt = 4.5

    def make_fake_backend(true_ceiling_real, reject_message):
        # A stand-in for post_probe(base_url, body, timeout): accept iff the REAL
        # token count is at/under the true ceiling, else reject with reject_message.
        # Records every call so the self-test can assert calibration actually fired.
        calls = []

        def fake_post(base_url, body, timeout):
            chars = len(body["messages"][0]["content"])
            real = int(round(chars / real_cpt))
            if real <= true_ceiling_real:
                calls.append({"accepted": True, "chars": chars, "real": real})
                return 200, {"type": "message",
                             "usage": {"input_tokens": real, "output_tokens": 1}}
            calls.append({"accepted": False, "chars": chars, "real": real})
            return 400, {"type": "error", "error": {
                "type": "invalid_request_error", "message": reject_message}}

        return fake_post, calls

    # 3a. Bisect path: the rejection carries NO explicit maximum, so Phase 1 falls
    #     through to the real Phase-2 binary search + bracket bookkeeping.
    tol = 3000
    bisect_ceiling_real = 372000
    bisect_args = argparse.Namespace(
        base_url="http://fake.invalid", model="gpt-5.6-sol",
        bracket_low=337000, bracket_high=450000, oversize_target=450000,
        tolerance=tol, max_tokens=1, timeout=1.0,
    )
    fake_bisect, bisect_calls = make_fake_backend(
        bisect_ceiling_real, "context_length_exceeded: too many tokens")
    est, method, largest_accept, smallest_reject, _ = run_live_probe(
        bisect_args, post_fn=fake_bisect)
    check("bisect self-test drives the real bisect path", method == "bisect")
    check("bisect estimate within tolerance of true ceiling",
          abs(est - bisect_ceiling_real) <= tol)
    check("bisect never accepted above the true ceiling",
          largest_accept is not None and largest_accept <= bisect_ceiling_real)
    check("bisect recorded a reject bound above the largest accept",
          smallest_reject is not None and smallest_reject > largest_accept)
    _accepts = [c for c in bisect_calls if c["accepted"]]
    _first_accept = _accepts[0] if _accepts else None
    check(
        "calibration path fired (first accept real != naive 4.0 target)",
        _first_accept is not None
        and _first_accept["real"]
        != int(round(_first_accept["chars"] / INITIAL_CHARS_PER_TOKEN)),
    )

    # 3b. Parsed path: the rejection states an explicit maximum, so Phase 1 parses it
    #     and confirms with a single just-under-ceiling accept (also calibrating).
    parsed_ceiling_real = 390000
    parsed_args = argparse.Namespace(
        base_url="http://fake.invalid", model="gpt-5.6-sol",
        bracket_low=337000, bracket_high=450000, oversize_target=450000,
        tolerance=tol, max_tokens=1, timeout=1.0,
    )
    fake_parsed, _parsed_calls = make_fake_backend(
        parsed_ceiling_real,
        "This model's maximum context length is 390000 tokens (context_length_exceeded)")
    p_est, p_method, p_largest, _p_reject, _ = run_live_probe(
        parsed_args, post_fn=fake_parsed)
    check("parsed self-test drives the real parse+confirm path", p_method == "parsed")
    check("parsed estimate equals the stated maximum", p_est == parsed_ceiling_real)
    check("parsed path ran a confirming accept", p_largest is not None)

    # 3c. Calibration-guard path (regression for the 2026-09-05 gpt-5.6-sol defect):
    #     one accepted response reports an absurd usage.input_tokens (1/20th of the
    #     real count). The guard must ignore that reading — never adopting it as the
    #     chars-per-token truth and never letting it stand as an accept bound — so the
    #     bisect still converges on the true ceiling.
    bogus_state = {"fired": False}

    def fake_bogus_post(base_url, body, timeout):
        chars = len(body["messages"][0]["content"])
        real = int(round(chars / real_cpt))
        if real > bisect_ceiling_real:
            return 400, {"type": "error", "error": {
                "type": "invalid_request_error",
                "message": "context_length_exceeded: too many tokens"}}
        reported = real
        if not bogus_state["fired"]:
            # First accepted response only: emit a wildly-too-small token count.
            bogus_state["fired"] = True
            reported = max(1, real // 20)
        return 200, {"type": "message",
                     "usage": {"input_tokens": reported, "output_tokens": 1}}

    guard_args = argparse.Namespace(
        base_url="http://fake.invalid", model="gpt-5.6-sol",
        bracket_low=337000, bracket_high=450000, oversize_target=450000,
        tolerance=tol, max_tokens=1, timeout=1.0,
    )
    g_est, g_method, g_largest, _g_reject, g_log = run_live_probe(
        guard_args, post_fn=fake_bogus_post)
    check("guard self-test drives the real bisect path", g_method == "bisect")
    check("guard warned about the implausible token count",
          any("implausible usage.input_tokens" in line for line in g_log))
    check("guard kept the bisect converging despite the bogus reading",
          abs(g_est - bisect_ceiling_real) <= tol)
    check("guard never adopted the bogus count as an accept bound",
          g_largest is not None and g_largest > bisect_ceiling_real // 2)

    print()
    if failures:
        print(f"SELF_TEST=FAIL failures={len(failures)}")
        return 1
    print("SELF_TEST=PASS")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Measure the local provider shim's backend context-window ceiling."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"local shim base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"model slug to probe (default: {DEFAULT_MODEL})")
    parser.add_argument("--bracket-low", type=int, default=DEFAULT_BRACKET_LOW,
                        help=f"bisect accepted floor (default: {DEFAULT_BRACKET_LOW})")
    parser.add_argument("--bracket-high", type=int, default=DEFAULT_BRACKET_HIGH,
                        help=f"bisect rejected ceiling (default: {DEFAULT_BRACKET_HIGH})")
    parser.add_argument("--oversize-target", type=int, default=DEFAULT_OVERSIZE_TARGET,
                        help=("first deliberately-oversized target used to parse the "
                              f"backend maximum (default: {DEFAULT_OVERSIZE_TARGET})"))
    parser.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE,
                        help=f"bisect stop bracket width (default: {DEFAULT_TOLERANCE})")
    parser.add_argument("--max-tokens", type=int, default=1,
                        help="max_tokens for each probe request (default: 1)")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="per-request timeout in seconds (default: 120)")
    parser.add_argument("--self-test", action="store_true",
                        help="run offline parser/bisect self-test and exit (no network)")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    print(f"[probe] shim={args.base_url} model={args.model} "
          f"bracket=({args.bracket_low},{args.bracket_high}) "
          f"oversize={args.oversize_target} tolerance={args.tolerance}", flush=True)
    started = time.time()
    ceiling, method, confirmed_accept, confirmed_reject, _log = run_live_probe(args)
    elapsed = time.time() - started

    accept_str = str(confirmed_accept) if confirmed_accept is not None else "none"
    reject_str = str(confirmed_reject) if confirmed_reject is not None else "none"
    print()
    print(f"[probe] done in {elapsed:.1f}s")
    # Machine-greppable final line.
    print(
        f"CEILING_ESTIMATE={ceiling} METHOD={method} "
        f"CONFIRMED_ACCEPT={accept_str} CONFIRMED_REJECT={reject_str}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
