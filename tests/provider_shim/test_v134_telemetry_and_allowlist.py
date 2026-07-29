"""Deterministic contracts for the v1.3.4 telemetry + allowlist riders (V4-R5..R7).

This module covers the V4-ii features that ride alongside the stale-blob insurance
(V4-R1..R4, exercised by test_v134_stale_blob_insurance.py):

  * V4-R5 — known-events allowlist absorption. `keepalive` and `response.metadata`
    joined the ignored status/lifecycle group of _KNOWN_EVENT_TYPES, so a clean stream
    that interleaves them completes with unknown_events=0 rather than throttle-logging
    them as unknown wire. The three v1.2.14 R1 allowlist-guard tests still key off
    response.audio.delta / web_search_call and pass unmodified (run by the suite).
  * V4-R6 — reasoning-cache HIT counter on the terminal record. reasoning_cache_hit is
    the per-request hit count (parallel to reasoning_cache_miss); reasoning_cache_stripped
    is 0 on a clean request (nonzero exercised by the V4-i strip tests).
  * V4-R7 — /health restore-effectiveness. The existing NESTED reasoning_cache block
    gains hits (process-cumulative) and restored_hits (the subset whose call_id was still
    disk-restored at hit time). No new top-level /health key (the _HEALTH_KEYS money test
    in test_historical_regressions.py stays intact with only its version-pin edit).

Hermeticity mirrors test_v134_stale_blob_insurance.py: every reasoning-cache seam lives
under scripts/scratch (never /tmp, never the production HOME default), each test pins a
UNIQUE per-test DAAF_REASONING_CACHE_FILE, and the in-process shim is imported fresh per
test so its import-time restore and its process-cumulative counters start clean. The
seeded-seam importer pattern (not the ASGI probe, which purges the reasoning seam before
load) is required for the restored-blob scenarios.

Test plan (design § Test Plan items 8, 9, 11, 12):
 8. Allowlist: a stream carrying keepalive + response.metadata -> unknown_events=0.
 9. HIT counter: seeded restored cache + replay -> reasoning_cache_hit=1/miss=0; a mixed
    hit/miss request reports both; reasoning_cache_stripped=0 on a clean request.
11. /health: nested block carries hits/restored_hits; restored_hits increments ONLY for
    restored-id hits (a live-populated hit bumps hits but not restored_hits).
12. Version pins swept + full suite green (asserted by the suite gate, not a test here).
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import io
import json
import logging
import os
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

from ._loopback_harness import (
    FAKE_OPENAI_KEY,
    PRODUCTION_SHIM,
    SCRATCH_ROOT,
    full_response_scenario,
    parse_lifecycle_logs,
)


# --- Local fixtures (self-contained copies of the v133/v134 helper patterns) ---

def _reasoning(item_id: str) -> dict[str, object]:
    """A minimal, well-shaped reasoning item carrying an opaque encrypted_content blob."""
    return {
        "type": "reasoning",
        "id": item_id,
        "status": "completed",
        "summary": [],
        "encrypted_content": f"ENC_{item_id}",
    }


def _seam_payload(pairs, captured_at=None) -> dict[str, object]:
    """Build a persisted-file payload from (call_id, item) pairs in oldest->newest order."""
    return {
        "captured_at": int(time.time()) if captured_at is None else int(captured_at),
        "entries": [[cid, item] for cid, item in pairs],
    }


def _tool_use_replay_messages(call_ids):
    """One assistant message replaying tool_use for each call_id (so the shim's re-injection
    path looks each reasoning item up in the cache), followed by matching user tool_results.
    A single call_id may be passed as a string."""
    if isinstance(call_ids, str):
        call_ids = [call_ids]
    tool_uses = [
        {
            "type": "tool_use",
            "id": cid,
            "name": "Read",
            "input": {"file_path": f"/daaf/README_{cid}.md"},
        }
        for cid in call_ids
    ]
    tool_results = [
        {"type": "tool_result", "tool_use_id": cid, "content": "replay result"}
        for cid in call_ids
    ]
    return [
        {"role": "assistant", "content": tool_uses},
        {"role": "user", "content": tool_results},
    ]


# A text-only Responses object: NO reasoning/function_call, so a 200 success carrying it
# repopulates nothing (keeps hit-count / restored-set assertions clean).
_TEXT_SUCCESS = {
    "id": "resp_text_success",
    "model": "gpt-fixture",
    "status": "completed",
    "output": [
        {
            "type": "message",
            "id": "msg_text_success",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "ok"}],
        }
    ],
    "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
    "incomplete_details": None,
    "error": None,
}


def _sse_bytes_from_events(events, append_done: bool = True) -> bytes:
    """Serialize a list of semantic event dicts into the SSE wire bytes the shim consumes,
    mirroring the loopback harness's own success-stream construction."""
    payload = b"".join(
        (
            f"event: {event.get('type', 'message')}\n"
            f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
        ).encode("utf-8")
        for event in events
    )
    if append_done:
        payload += b"data: [DONE]\n\n"
    return payload


def _seam_path() -> Path:
    """A unique per-test reasoning-cache seam path under scripts/scratch (never /tmp)."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    return SCRATCH_ROOT / f"v134_telemetry_{uuid.uuid4().hex}.json"


def _load_probe_module(seam_path: Path, backend_mode: str = "openai"):
    """Import a fresh production shim in-process pinned to ``seam_path`` (so its import-time
    restore reads exactly that seeded seam and populates the V4-R1 restored-id set, and its
    process-cumulative /health hit counters start at 0). No purge: this loader deliberately
    preserves the seeded file, unlike the ASGI probe."""
    module_name = f"provider_shim_telemetry_{uuid.uuid4().hex}"
    env = {
        "DAAF_REASONING_CACHE_FILE": str(seam_path),
        "SHIM_BACKEND_MODE": backend_mode,
        "SHIM_BACKEND_BASE_URL": "http://127.0.0.1:1/v1",
        "SHIM_BACKEND_API_KEY": FAKE_OPENAI_KEY,
        "OPENAI_API_KEY": FAKE_OPENAI_KEY,
    }
    with mock.patch.dict(os.environ, env, clear=False):
        spec = importlib.util.spec_from_file_location(module_name, PRODUCTION_SHIM)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load production shim for telemetry probe")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class _ProbeReport:
    def __init__(self):
        self.upstream_calls = 0
        self.payloads: list[dict] = []
        self.logs = ""
        self.terminal: dict[str, str] = {}
        self.raised = None


def _drive(
    module,
    *,
    messages,
    attempt_outcomes,
    error_body=b"{}",
    stream=False,
    success_nonstream=None,
    success_stream_bytes=b"",
) -> _ProbeReport:
    """Drive one production request through ``module.app`` with a seamed httpx client that
    scripts per-attempt HTTP outcomes and captures a deep copy of each outbound payload."""

    report = _ProbeReport()

    def response_for_attempt(n: int, payload):
        report.payloads.append(copy.deepcopy(payload))
        outcome = attempt_outcomes[min(n - 1, len(attempt_outcomes) - 1)]
        status = int(outcome)
        if status >= 400:
            content = bytes(error_body)
        elif stream:
            content = success_stream_bytes
        else:
            content = json.dumps(success_nonstream or _TEXT_SUCCESS).encode("utf-8")
        return module.httpx.Response(
            status,
            content=content,
            request=module.httpx.Request("POST", "http://127.0.0.1:1/v1/responses"),
        )

    class ProbeStreamContext:
        def __init__(self, n, payload):
            self.n = n
            self.payload = payload

        async def __aenter__(self):
            return response_for_attempt(self.n, self.payload)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class ProbeClient:
        def stream(self, *args, **kwargs):
            report.upstream_calls += 1
            return ProbeStreamContext(report.upstream_calls, kwargs.get("json"))

        async def post(self, *args, **kwargs):
            report.upstream_calls += 1
            return response_for_attempt(report.upstream_calls, kwargs.get("json"))

    original_client = module._client
    module._client = ProbeClient()

    log_buffer = io.StringIO()
    handler = logging.StreamHandler(log_buffer)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s req_id=%(req_id)s phase=%(phase)s %(message)s"
        )
    )
    handler.addFilter(module._RequestLogFilter())
    original_handlers = list(module.log.handlers)
    original_propagate = module.log.propagate
    module.log.handlers = [handler]
    module.log.propagate = False
    module.log.setLevel(logging.INFO)

    request_body = json.dumps(
        {
            "model": "gpt-fixture",
            "max_tokens": 256,
            "stream": stream,
            "messages": messages,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    async def exercise():
        receive_queue: asyncio.Queue = asyncio.Queue()
        receive_queue.put_nowait(
            {"type": "http.request", "body": request_body, "more_body": False}
        )

        async def receive():
            return await receive_queue.get()

        sent: list[dict] = []

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "method": "POST", "path": "/v1/messages"}
        try:
            await asyncio.wait_for(module.app(scope, receive, send), timeout=5.0)
        except Exception as error:  # noqa: BLE001 - recorded for assertions
            report.raised = type(error).__name__

    try:
        asyncio.run(exercise())
    finally:
        module._client = ProbeClient() if original_client is None else original_client
        module.log.handlers = original_handlers
        module.log.propagate = original_propagate

    report.logs = log_buffer.getvalue()
    for line in parse_lifecycle_logs(report.logs):
        if line.event == "terminal":
            report.terminal = line.fields
    return report


def _get_health(module) -> dict:
    """Drive a GET /health request through ``module.app`` and return the parsed JSON body."""

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "GET", "path": "/health"}
    asyncio.run(asyncio.wait_for(module.app(scope, receive, send), timeout=5.0))
    body = b"".join(
        m.get("body", b"") for m in sent if m.get("type") == "http.response.body"
    )
    return json.loads(body)


def _seed(test: unittest.TestCase, pairs, backend_mode="openai"):
    """Seed a persisted reasoning-cache seam and load a fresh in-process shim pinned to it."""
    seam = _seam_path()
    seam.write_text(json.dumps(_seam_payload(pairs)), encoding="utf-8")
    test.addCleanup(lambda: seam.unlink(missing_ok=True))
    module = _load_probe_module(seam, backend_mode=backend_mode)
    return module, seam


# --- Item 8: known-events allowlist absorption ---

class AllowlistAbsorptionTests(unittest.TestCase):
    maxDiff = 8000

    def test_keepalive_and_metadata_absorbed_unknown_events_zero(self) -> None:
        # A clean streaming turn that ALSO interleaves a top-level `keepalive` frame and a
        # `response.metadata` lifecycle frame. Both are now in the ignored group of
        # _KNOWN_EVENT_TYPES, so the reducer catch-all skips them silently and the terminal
        # record must report unknown_events=0 (the "0 when clean" invariant, extended).
        module, _seam = _seed(self, [])
        scenario = full_response_scenario()
        events = list(scenario.stream_events)
        # Insert the two absorbed types among the clean events (positions are arbitrary; the
        # reducer keys off the event type, not order). keepalive is top-level like `error`.
        events.insert(1, {"type": "keepalive"})
        events.insert(
            2, {"type": "response.metadata", "response": {"id": "resp_full"}}
        )
        report = _drive(
            module,
            messages=[{"role": "user", "content": "hello"}],
            attempt_outcomes=[200],
            stream=True,
            success_stream_bytes=_sse_bytes_from_events(events, scenario.append_done),
        )
        self.assertEqual(report.upstream_calls, 1, report.logs)
        self.assertEqual(report.terminal.get("outcome"), "success", report.logs)
        self.assertEqual(report.terminal.get("unknown_events"), "0", report.logs)


# --- Item 9: reasoning-cache HIT counter on the terminal record ---

class HitCounterTerminalTests(unittest.TestCase):
    maxDiff = 8000

    def test_hit_only_request_reports_hit_one_miss_zero(self) -> None:
        call_id, rs_id = "call_hit_only", "rs_hit_only"
        module, _seam = _seed(self, [(call_id, _reasoning(rs_id))])
        self.assertIn(call_id, module._REASONING_CACHE)
        report = _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[200],
        )
        self.assertEqual(report.upstream_calls, 1, report.logs)
        self.assertEqual(report.terminal.get("outcome"), "success", report.logs)
        self.assertEqual(report.terminal.get("reasoning_cache_hit"), "1", report.logs)
        self.assertEqual(report.terminal.get("reasoning_cache_miss"), "0", report.logs)
        # A clean request never strips — the field is present and 0.
        self.assertEqual(
            report.terminal.get("reasoning_cache_stripped"), "0", report.logs
        )

    def test_mixed_hit_and_miss_reports_both(self) -> None:
        # One cached call_id (hit) and one absent call_id (miss) in the same replay message.
        hit_id, rs_id = "call_mixed_hit", "rs_mixed_hit"
        miss_id = "call_mixed_miss"
        module, _seam = _seed(self, [(hit_id, _reasoning(rs_id))])
        report = _drive(
            module,
            messages=_tool_use_replay_messages([hit_id, miss_id]),
            attempt_outcomes=[200],
        )
        self.assertEqual(report.terminal.get("outcome"), "success", report.logs)
        self.assertEqual(report.terminal.get("reasoning_cache_hit"), "1", report.logs)
        self.assertEqual(report.terminal.get("reasoning_cache_miss"), "1", report.logs)


# --- Item 11: /health restore-effectiveness (hits / restored_hits) ---

class HealthRestoreEffectivenessTests(unittest.TestCase):
    maxDiff = 8000

    def test_health_nested_block_carries_hits_and_restored_hits(self) -> None:
        call_id, rs_id = "call_health", "rs_health"
        module, _seam = _seed(self, [(call_id, _reasoning(rs_id))])
        # Baseline: fresh process, no hits yet.
        baseline = _get_health(module)["reasoning_cache"]
        self.assertEqual(baseline["hits"], 0)
        self.assertEqual(baseline["restored_hits"], 0)
        # A restored hit bumps BOTH cumulative counters.
        _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[200],
        )
        after = _get_health(module)["reasoning_cache"]
        self.assertEqual(after["hits"], 1)
        self.assertEqual(after["restored_hits"], 1)
        # Nesting invariant: the four count keys live INSIDE reasoning_cache, and hits/
        # restored_hits are NOT promoted to top-level /health keys.
        self.assertEqual(
            set(after), {"entries", "restored", "hits", "restored_hits"}
        )
        health = _get_health(module)
        self.assertNotIn("hits", health)
        self.assertNotIn("restored_hits", health)

    def test_live_populated_hit_bumps_hits_but_not_restored_hits(self) -> None:
        # Seed one restored entry, exercise a restored hit (hits=1, restored_hits=1). Then
        # convert that entry to LIVE via _cache_reasoning — the exact production write the
        # live-population path uses, which discards the call_id from the restored set. A
        # second hit on the now-live entry must bump hits (2) but NOT restored_hits (1).
        call_id, rs_id = "call_live_vs_restored", "rs_live_vs_restored"
        module, _seam = _seed(self, [(call_id, _reasoning(rs_id))])
        _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[200],
        )
        first = _get_health(module)["reasoning_cache"]
        self.assertEqual((first["hits"], first["restored_hits"]), (1, 1))
        # Live re-population of the same call_id: real production function; drops it from the
        # restored set (a live blob is no longer "restored").
        self.assertIn(call_id, module._REASONING_CACHE_RESTORED_IDS)
        module._cache_reasoning(call_id, module._REASONING_CACHE[call_id])
        self.assertNotIn(call_id, module._REASONING_CACHE_RESTORED_IDS)
        _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[200],
        )
        second = _get_health(module)["reasoning_cache"]
        self.assertEqual(second["hits"], 2, "the live hit must still count as a hit")
        self.assertEqual(
            second["restored_hits"], 1, "a live-populated hit must not bump restored_hits"
        )


if __name__ == "__main__":
    unittest.main()
