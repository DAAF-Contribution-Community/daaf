"""Deterministic contracts for the v1.3.4 stale-blob reasoning-cache insurance (V4-R1..R4).

v1.3.3 made the reasoning cache persist across shim restarts. A RESTORED encrypted_content
blob has an undocumented backend-side validity lifetime: if the backend ever rejects a
re-injected restored blob with a 400, v1.3.3 fails the request outright (400s are never
retried). v1.3.4 closes that hole. When a 400 (a) names reasoning material in its error
body AND (b) the request injected >=1 restored reasoning item AND (c) the one-shot budget is
unused, the shim strips exactly the injected restored reasoning items from the reused
payload, evicts+persists them as proven stale, and retries once. Every non-triggering 400
stays fail-fast, byte-identical to v1.3.3.

These tests seed a restored cache by writing a persisted-snapshot seam file and loading a
fresh in-process shim pinned to it (the module's import-time restore then populates both the
in-memory cache and the V4-R1 restored-id set). A compact in-test driver seams the module's
httpx client to script per-attempt outcomes ([400-reasoning, 200], etc.) and captures a
deep copy of each outbound payload so the "second request carries no reasoning items"
contract is directly observable. Hermeticity: every seam lives under scripts/scratch (never
/tmp, never the production HOME default reasoning_cache.json or logs/quota_state.json), and
each test pins a UNIQUE per-test seam via DAAF_REASONING_CACHE_FILE so import-time restore is
isolated.

Test plan (design § Test Plan items 1-7, 10):
 1. Strip-retry happy path (JSON loop): 2 upstream calls, second body has no reasoning item,
    outcome=success, retry_reason=stale_reasoning_400, distinct strip log event.
 2. Both lane envelopes trigger: chatgpt {status,error:{...}} and openai bare {error:{...}}.
 3. One-shot gate: 400-reasoning then 400-reasoning -> exactly 2 attempts, then failure.
 4. Negative: generic 400 body + restored items injected -> no retry (fail-fast preserved).
 5. Negative: reasoning-naming 400 but only live-populated items -> no retry, no strip.
 6. Eviction: stripped call_ids absent from in-memory cache AND persisted seam; unrelated
    restored entry untouched.
 7. Existing 400 pins unbroken (asserted by running the v1214 400-family modules).
10. Hit-path non-mutation: a hit-only request does not advance the cache file.
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


# --- Local fixtures (self-contained copies of the v133 helper patterns) ---

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
    path looks each reasoning item up in the restored cache), followed by matching user
    tool_results. A single call_id may be passed as a string."""
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
# never repopulates the reasoning cache (keeps hit-non-mutation / eviction assertions clean).
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

# Reasoning-naming 400 error bodies in each observed lane envelope.
_CHATGPT_REASONING_400 = (
    b'{"status":400,"error":{"type":"invalid_request_error",'
    b'"message":"Invalid reasoning item: encrypted_content is no longer valid"}}'
)
_OPENAI_REASONING_400 = (
    b'{"error":{"type":"invalid_request_error","param":"input",'
    b'"message":"reasoning blob rejected"}}'
)
# A generic 400 with NO reasoning marker (mirrors the pinned observability fixture body).
_GENERIC_400 = b'{"error":{"type":"fixture_status","message":"fixture rejection"}}'


def _sse_bytes(scenario) -> bytes:
    """Serialize a scenario's semantic events into the SSE wire bytes the shim consumes,
    mirroring the loopback harness's own success-stream construction."""
    payload = b"".join(
        (
            f"event: {event.get('type', 'message')}\n"
            f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
        ).encode("utf-8")
        for event in scenario.stream_events
    )
    if scenario.append_done:
        payload += b"data: [DONE]\n\n"
    return payload


def _seam_path() -> Path:
    """A unique per-test reasoning-cache seam path under scripts/scratch (never /tmp)."""
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    return SCRATCH_ROOT / f"v134_stale_blob_{uuid.uuid4().hex}.json"


def _load_probe_module(seam_path: Path, backend_mode: str = "openai"):
    """Import a fresh production shim in-process pinned to ``seam_path`` (so its import-time
    restore reads exactly that seeded seam and populates the V4-R1 restored-id set). No
    purge: this loader deliberately preserves the seeded file, unlike the ASGI probe."""
    module_name = f"provider_shim_stale_blob_{uuid.uuid4().hex}"
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
            raise RuntimeError("could not load production shim for stale-blob probe")
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
    error_body,
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


def _reasoning_item_ids(payload) -> list[str]:
    """The ids of every reasoning item present in an outbound payload's input[]."""
    return [
        item.get("id")
        for item in (payload or {}).get("input", [])
        if isinstance(item, dict) and item.get("type") == "reasoning"
    ]


class StaleBlobStripRetryTests(unittest.TestCase):
    maxDiff = 8000

    def _seed(self, pairs, captured_at=None, backend_mode="openai"):
        seam = _seam_path()
        seam.write_text(json.dumps(_seam_payload(pairs, captured_at)), encoding="utf-8")
        self.addCleanup(lambda: seam.unlink(missing_ok=True))
        module = _load_probe_module(seam, backend_mode=backend_mode)
        return module, seam

    # --- Test 1: strip-retry happy path (JSON loop) ---
    def test_strip_retry_happy_path(self) -> None:
        call_id, rs_id = "call_stale_1", "rs_stale_1"
        module, _seam = self._seed([(call_id, _reasoning(rs_id))])
        # Precondition: the seeded blob restored and is marked restored.
        self.assertIn(call_id, module._REASONING_CACHE)
        self.assertIn(call_id, module._REASONING_CACHE_RESTORED_IDS)

        report = _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[400, 200],
            error_body=_OPENAI_REASONING_400,
        )

        self.assertEqual(report.upstream_calls, 2, report.logs)
        # First outbound request carried the restored reasoning item; the second did not.
        self.assertIn(rs_id, _reasoning_item_ids(report.payloads[0]))
        self.assertEqual(_reasoning_item_ids(report.payloads[1]), [])
        self.assertEqual(report.terminal.get("outcome"), "success")
        self.assertEqual(report.terminal.get("retry_reason"), "stale_reasoning_400")
        self.assertEqual(report.terminal.get("retry_source"), "body")
        self.assertIn("event=reasoning_cache_stale_strip stripped=1", report.logs)
        # Counts-only discipline: the stripped blob's opaque content never reaches a log line.
        self.assertNotIn("ENC_", report.logs)

    # --- Test 2: both lane envelopes trigger ---
    def test_both_lane_envelopes_trigger(self) -> None:
        for label, body in (
            ("chatgpt", _CHATGPT_REASONING_400),
            ("openai", _OPENAI_REASONING_400),
        ):
            with self.subTest(envelope=label):
                call_id, rs_id = f"call_{label}", f"rs_{label}"
                module, _seam = self._seed([(call_id, _reasoning(rs_id))])
                report = _drive(
                    module,
                    messages=_tool_use_replay_messages(call_id),
                    attempt_outcomes=[400, 200],
                    error_body=body,
                )
                self.assertEqual(report.upstream_calls, 2, report.logs)
                self.assertEqual(report.terminal.get("outcome"), "success")
                self.assertEqual(
                    report.terminal.get("retry_reason"), "stale_reasoning_400"
                )

    # --- Test 1b: strip-retry also fires on the SSE loop (_open_backend_stream) ---
    def test_strip_retry_streaming_loop(self) -> None:
        # R2 spans BOTH retry loops; the JSON-loop tests above exercise _post_with_retry, so
        # this drives the streaming path (stream=True -> _open_backend_stream) end to end.
        call_id, rs_id = "call_stream", "rs_stream"
        module, _seam = self._seed([(call_id, _reasoning(rs_id))])
        report = _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[400, 200],
            error_body=_CHATGPT_REASONING_400,
            stream=True,
            success_stream_bytes=_sse_bytes(full_response_scenario()),
        )
        self.assertEqual(report.upstream_calls, 2, report.logs)
        self.assertIn(rs_id, _reasoning_item_ids(report.payloads[0]))
        self.assertEqual(_reasoning_item_ids(report.payloads[1]), [])
        self.assertEqual(report.terminal.get("outcome"), "success")
        self.assertEqual(report.terminal.get("retry_reason"), "stale_reasoning_400")
        self.assertIn("event=reasoning_cache_stale_strip stripped=1", report.logs)

    # --- Test 3: one-shot gate ---
    def test_one_shot_gate(self) -> None:
        call_id, rs_id = "call_oneshot", "rs_oneshot"
        module, _seam = self._seed([(call_id, _reasoning(rs_id))])
        report = _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[400, 400],
            error_body=_OPENAI_REASONING_400,
        )
        # Exactly two attempts: the original + the single strip-retry, then fail-fast.
        self.assertEqual(report.upstream_calls, 2, report.logs)
        self.assertEqual(report.terminal.get("outcome"), "error")
        # The strip fired exactly once.
        self.assertEqual(report.logs.count("event=reasoning_cache_stale_strip"), 1)

    # --- Test 4: negative — generic 400 body, restored items injected, no retry ---
    def test_generic_400_with_restored_items_does_not_retry(self) -> None:
        call_id, rs_id = "call_generic", "rs_generic"
        module, _seam = self._seed([(call_id, _reasoning(rs_id))])
        report = _drive(
            module,
            messages=_tool_use_replay_messages(call_id),
            attempt_outcomes=[400, 200],
            error_body=_GENERIC_400,
        )
        # Fail-fast preserved: a single attempt, no strip, no retry.
        self.assertEqual(report.upstream_calls, 1, report.logs)
        self.assertNotIn("event=reasoning_cache_stale_strip", report.logs)
        self.assertEqual(report.terminal.get("outcome"), "error")

    # --- Test 5: negative — reasoning-naming 400 but only live-populated items ---
    def test_reasoning_400_with_only_live_items_does_not_strip(self) -> None:
        # Seed an empty cache (nothing restored). A live tool_use then MISSES the cache, so
        # no reasoning item is injected and no restored-id is recorded — the detector's
        # restored-items-present gate stays closed even though the body names reasoning.
        module, _seam = self._seed([])
        self.assertEqual(len(module._REASONING_CACHE_RESTORED_IDS), 0)
        report = _drive(
            module,
            messages=_tool_use_replay_messages("call_live_only"),
            attempt_outcomes=[400, 200],
            error_body=_OPENAI_REASONING_400,
        )
        self.assertEqual(report.upstream_calls, 1, report.logs)
        self.assertNotIn("event=reasoning_cache_stale_strip", report.logs)
        self.assertEqual(report.terminal.get("outcome"), "error")

    # --- Test 6: eviction + persist of stripped entries; unrelated restored untouched ---
    def test_eviction_and_persist_of_stripped_entries(self) -> None:
        stale_id, stale_rs = "call_stale_evict", "rs_stale_evict"
        keep_id, keep_rs = "call_keep", "rs_keep"
        # Two restored entries; only the first is referenced by the request (so only it is
        # injected, stripped, and evicted). The second must survive untouched.
        module, seam = self._seed(
            [(keep_id, _reasoning(keep_rs)), (stale_id, _reasoning(stale_rs))]
        )
        report = _drive(
            module,
            messages=_tool_use_replay_messages(stale_id),
            attempt_outcomes=[400, 200],
            error_body=_OPENAI_REASONING_400,
        )
        self.assertEqual(report.upstream_calls, 2, report.logs)
        # In-memory: the stale call_id is gone from both the cache and the restored set;
        # the unrelated restored entry is untouched.
        self.assertNotIn(stale_id, module._REASONING_CACHE)
        self.assertNotIn(stale_id, module._REASONING_CACHE_RESTORED_IDS)
        self.assertIn(keep_id, module._REASONING_CACHE)
        self.assertIn(keep_id, module._REASONING_CACHE_RESTORED_IDS)
        # Persisted: the rewritten seam no longer carries the stale call_id but keeps the
        # unrelated one (the text-only 200 adds no new live entry).
        persisted = json.loads(seam.read_text(encoding="utf-8"))
        persisted_call_ids = {cid for cid, _ in persisted["entries"]}
        self.assertNotIn(stale_id, persisted_call_ids)
        self.assertIn(keep_id, persisted_call_ids)

    # --- Test 10: hit-path non-mutation (stat-snapshot retry-once bracket) ---
    def test_hit_only_request_does_not_advance_cache_file(self) -> None:
        # A restored hit with a 200-first success must not mutate the cache file: the hit
        # path is read-only (.get(), never move_to_end) and the text-only success populates
        # nothing, so no persist fires. Retry-once bracket per test_v133 precedent.
        call_id, rs_id = "call_hit", "rs_hit"

        def snapshot(path: Path):
            try:
                st = path.stat()
                return (st.st_mtime_ns, path.read_bytes())
            except FileNotFoundError:
                return None

        dirty = True
        last_report = None
        for _attempt in range(2):
            module, seam = self._seed([(call_id, _reasoning(rs_id))])
            before = snapshot(seam)
            last_report = _drive(
                module,
                messages=_tool_use_replay_messages(call_id),
                attempt_outcomes=[200],
                error_body=_OPENAI_REASONING_400,
            )
            after = snapshot(seam)
            if before == after:
                dirty = False
                break
        self.assertEqual(last_report.upstream_calls, 1, last_report.logs)
        # The restored item WAS injected (genuine hit), proving non-vacuity.
        self.assertIn(rs_id, _reasoning_item_ids(last_report.payloads[0]))
        self.assertEqual(last_report.terminal.get("outcome"), "success")
        self.assertFalse(dirty, "hit-only request advanced the reasoning-cache seam file")


if __name__ == "__main__":
    unittest.main()
