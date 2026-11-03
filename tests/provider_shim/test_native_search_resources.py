"""Native search: bounded resource regressions (projection, replay, error reader).

All payloads are synthetic; this tests application code, not live provider
support. Each adversarial boundary is reduced to bytes/items small enough for
routine CI. Error-reader cases use the harness's opt-in chunked error stream.

"v1.4.8" marks assertions aligned to the tolerant projection contract (an
over-long title falls back to the URL label instead of failing the turn).
"""
import copy
import json
import threading
import unittest
from functools import partial
from unittest import mock

from . import _native_search_fixtures as fx
from ._loopback_harness import controlled_asgi_probe

RAW_ITEMS, SEARCH = fx.RAW_ITEMS, fx.SEARCH


def configure_error_budget(module, retries=1):
    """Small in-memory transport budget; no production configuration changes."""
    module._SEARCH_MAX_ERROR_BYTES = 64
    module.MAX_ERROR_BODY_BYTES = 64
    module.MAX_RETRIES = retries


class SearchResourceTests(fx.NativeSearchCase):
    def setUp(self):
        super().setUp()
        self.registry = self.shim._ToolRegistry([SEARCH])

    def test_projection_byte_bound_before_serialization_and_cache(self):
        items = copy.deepcopy(RAW_ITEMS)
        url = items[1]["content"][0]["annotations"][0]["url"]
        items[0]["action"]["sources"] = [{"type": "url", "url": url}] * 64
        items[1]["content"][0]["annotations"][0]["title"] = "T" * 512
        self.assertLess(len(self.shim._search_json(items)), 16384)
        with mock.patch.object(self.shim, "_SEARCH_MAX_PROJECTED_BYTES", 16384), \
                mock.patch.object(self.shim._SEARCH_REPLAY, "put", wraps=self.shim._SEARCH_REPLAY.put) as put, \
                mock.patch.object(self.shim, "_search_json", wraps=self.shim._search_json) as encode:
            with self.assertRaisesRegex(self.shim._ProtocolError, "projected content exceeded"):
                self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", self.registry)
            put.assert_not_called()
            # Only raw-inventory validation serializes: amplified content never does.
            self.assertEqual(encode.call_count, 1)
        self.assertEqual(self.shim._SEARCH_REPLAY.bytes, 0)

    def test_projection_title_and_source_exact_boundaries(self):
        items = copy.deepcopy(RAW_ITEMS)
        items[0]["action"]["sources"] = [{"type": "url", "url": "https://example.org", "title": "T" * 8}] * 2
        items[1]["content"][0]["annotations"] = []
        with mock.patch.object(self.shim, "_SEARCH_MAX_TITLE_CHARS", 8), \
                mock.patch.object(self.shim, "_SEARCH_MAX_SOURCES", 2):
            result = self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", self.registry)
            self.assertEqual([r["title"] for r in result["content"][1]["content"]], ["T" * 8] * 2)
            # The source-count ceiling still fails closed, without touching the cache.
            bad = copy.deepcopy(items)
            bad[0]["action"]["sources"].append(bad[0]["action"]["sources"][0])
            before = self.shim._SEARCH_REPLAY.bytes
            with self.assertRaises(self.shim._ProtocolError):
                self.shim._search_projection({"status": "completed", "output": bad}, "gpt-fixture", self.registry)
            self.assertEqual(self.shim._SEARCH_REPLAY.bytes, before)
            # v1.4.8 (formerly fatal): an over-long source or citation title falls
            # back to the "URL: <url>" label; the turn and its evidence survive.
            long_source = copy.deepcopy(items)
            long_source[0]["action"]["sources"][0] = {**long_source[0]["action"]["sources"][0], "title": "T" * 9}
            result = self.shim._search_projection({"status": "completed", "output": long_source}, "gpt-fixture", self.registry)
            self.assertEqual([r["title"] for r in result["content"][1]["content"]], ["URL: https://example.org", "T" * 8])
            long_citation = copy.deepcopy(items)
            long_citation[1]["content"][0]["annotations"] = copy.deepcopy(RAW_ITEMS[1]["content"][0]["annotations"])
            long_citation[1]["content"][0]["annotations"][0]["title"] = "T" * 9
            result = self.shim._search_projection({"status": "completed", "output": long_citation}, "gpt-fixture", self.registry)
            self.assertIn("[URL: " + fx.CITED + "](", result["content"][-1]["text"])
            self.assertNotIn("T" * 9, json.dumps(result["content"]))

    def test_projection_exact_json_size_unicode_and_delimiters(self):
        # The bound is ASCII JSON byte length, NOT a claim about citation offsets.
        values = [None, True, False, 0, -1, 1.5, [], {}, "é😀\x7f\x00\b\f\n\r\t\"\\",
                  {"k": ["é😀", {"url": "https://example.org/a(b)?x=1", "quote": '"'}]}]
        for value in values:
            exact = len(self.shim._search_json(value))
            with self.subTest(value=value):
                self.assertEqual(self.shim._search_json_size(value, exact), exact)
                with self.assertRaises(self.shim._ProtocolError):
                    self.shim._search_json_size(value, exact - 1)

    def test_projection_list_exact_byte_boundary(self):
        value = {"title": "é😀", "url": "https://example.org"}
        exact = len(self.shim._search_json([value]))
        with mock.patch.object(self.shim, "_SEARCH_MAX_PROJECTED_BYTES", exact):
            target = self.shim._SearchProjectionList()
            target.append(value)
            self.assertEqual(target.json_bytes, exact)
            with self.assertRaises(self.shim._ProtocolError):
                target.append(value)
            self.assertEqual(target, [value])

    def test_replay_request_exact_bounds_precede_any_decoding(self):
        blocks = self.shim._search_projection({"status": "completed", "output": RAW_ITEMS}, "gpt-fixture", self.registry)["content"]
        messages = [{"role": "assistant", "content": blocks}] * 2
        limits = {"_SEARCH_REPLAY_REQUEST_MAX_BYTES": len(self.shim._search_json(RAW_ITEMS)) * 2,
                  "_SEARCH_REPLAY_REQUEST_MAX_ITEMS": len(RAW_ITEMS) * 2,
                  "_SEARCH_REPLAY_REQUEST_MAX_GROUPS": 2}
        with mock.patch.multiple(self.shim, **limits):
            plan, covered = self.shim._SEARCH_REPLAY.plan(messages)
            self.assertEqual(list(plan.values()), [RAW_ITEMS, RAW_ITEMS])
            self.assertIsNot(*plan.values())
        for name, limit in limits.items():
            with self.subTest(limit=name), mock.patch.object(self.shim, name, limit - 1), \
                    mock.patch.object(self.shim.json, "loads", wraps=json.loads) as decode:
                with self.assertRaisesRegex(self.shim._InvalidRequestError, "request expansion exceeded"):
                    self.shim._SEARCH_REPLAY.plan(messages)
                decode.assert_not_called()

    def test_replay_hash_and_decode_run_outside_cache_lock(self):
        blocks = self.shim._search_projection({"status": "completed", "output": RAW_ITEMS}, "gpt-fixture", self.registry)["content"]
        cache = self.shim._SEARCH_REPLAY
        cache.lock = threading.Lock()
        original_decode = json.loads
        original_encode = self.shim._search_json

        def unlocked_decode(value):
            self.assertTrue(cache.lock.acquire(blocking=False), "decode held shared lock")
            cache.lock.release()
            return original_decode(value)

        def unlocked_encode(value):
            self.assertTrue(cache.lock.acquire(blocking=False), "fingerprint held shared lock")
            cache.lock.release()
            return original_encode(value)
        with mock.patch.object(self.shim.json, "loads", side_effect=unlocked_decode), \
                mock.patch.object(self.shim, "_search_json", side_effect=unlocked_encode):
            plan, _ = cache.plan([{"role": "assistant", "content": blocks}])
        self.assertEqual(list(plan.values()), [RAW_ITEMS])

    def test_replay_overflow_is_local_before_auth_all_handler_cells(self):
        blocks = self.shim._search_projection({"status": "completed", "output": RAW_ITEMS}, "gpt-fixture", self.registry)["content"]
        token = blocks[0]["id"].split("_")[2]

        def setup(module):
            module._SEARCH_REPLAY.put(token, RAW_ITEMS, blocks)
            module._SEARCH_REPLAY_REQUEST_MAX_GROUPS = 1
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                request = {"model": "gpt-fixture", "max_tokens": 256, "stream": stream,
                           "messages": [{"role": "assistant", "content": blocks}] * 2,
                           "tools": [], "tool_choice": {"type": "none"}}
                report = controlled_asgi_probe(raw_request_body=json.dumps(request).encode(),
                                              stream=stream, backend_mode=mode, configure_module=setup)
                self.assertIsNone(report.raised)
                self.assertEqual(report.messages[0]["status"], 400)
                self.assertEqual((report.auth_calls, report.upstream_calls), (0, 0))

    def test_service_tier_container_is_unknown_not_typeerror(self):
        for tier in ([], {}, ["priority"], {"tier": "priority"}, None, True, 3, "future"):
            with self.subTest(tier=tier):
                result = self.shim._search_projection({"status": "completed", "output": RAW_ITEMS,
                                                       "service_tier": tier}, "gpt-fixture", self.registry)
                self.assertNotIn("speed", result["usage"])
        for tier, speed in (("priority", "fast"), ("default", "standard")):
            result = self.shim._search_projection({"status": "completed", "output": RAW_ITEMS,
                                                   "service_tier": tier}, "gpt-fixture", self.registry)
            self.assertEqual(result["usage"]["speed"], speed)

    def test_conversion_failure_is_structured_without_cache_mutation(self):
        self.shim._search_projection({"status": "completed", "output": RAW_ITEMS}, "gpt-fixture", self.registry)
        before = dict(self.shim._SEARCH_REPLAY.groups)
        # A simulated future usage-conversion failure must happen before insertion,
        # including before an eviction that could destroy an unrelated valid group.
        with mock.patch.object(self.shim, "_SEARCH_REPLAY_MAX_GROUPS", 1), \
                mock.patch.object(self.shim, "_anthropic_usage_block", side_effect=TypeError("PRIVATE_CONVERSION_SENTINEL")):
            with self.assertRaisesRegex(self.shim._ProtocolError, "^search response conversion failed$"):
                self.shim._search_projection({"status": "completed", "output": RAW_ITEMS}, "gpt-fixture", self.registry)
        self.assertEqual(dict(self.shim._SEARCH_REPLAY.groups), before)
        # Non-list output is fatal; malformed usage is intentionally dropped by the
        # baseline validator and must NOT be repurposed as a fatal-error fixture.
        with self.assertRaises(self.shim._ProtocolError):
            self.shim._search_projection({"status": "completed", "output": {}}, "gpt-fixture", self.registry)
        self.assertEqual(dict(self.shim._SEARCH_REPLAY.groups), before)

    def test_service_tier_container_all_handler_cells(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for tier in ([], {}):
                    scenario = fx.search_scenario()
                    scenario.nonstream_response["service_tier"] = tier
                    scenario.stream_events[-1]["response"]["service_tier"] = tier
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                                                  raw_request_body=json.dumps(fx.search_request(stream)).encode())
                    self.assertIsNone(report.raised)
                    self.assertEqual(report.messages[0]["status"], 200)
                    body = fx.probe_body(report)
                    self.assertNotIn(b"event: error", body)
                    self.assertNotIn(b'"speed"', body)
                    self.assertIn(b"server_tool_use", body)
                    self.assertEqual(report.stream_close_calls, 1)

    def test_search_error_reader_bounds_actual_opener_and_final_attempt(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for retries in (0, 1):
                    for status in (400, 503):
                        observations = {}
                        report = controlled_asgi_probe(
                            scenario=fx.search_scenario(), stream=stream, backend_mode=mode,
                            raw_request_body=json.dumps(fx.search_request(stream)).encode(),
                            response_status=status, configure_module=partial(configure_error_budget, retries=retries),
                            error_body_chunks=[b"X" * 32] * 3 + [b"PRIVATE_ERROR_SENTINEL"],
                            resource_observations=observations)
                        self.assertIsNone(report.raised)
                        # One crossing chunk may be supplied by HTTPX; no subsequent
                        # chunk is consumed or retained and retry must not run.
                        self.assertEqual(observations["error_chunks_read"], 3)
                        self.assertEqual(observations["error_bytes_read"], 96)
                        self.assertEqual(report.upstream_calls, 1)
                        self.assertEqual(report.stream_close_calls, 1)
                        self.assertEqual(report.pending_task_count, 0, observations)
                        body = fx.probe_body(report)
                        self.assertIn(b"search error body exceeded byte limit", body)
                        self.assertNotIn("PRIVATE_ERROR_SENTINEL", report.logs + body.decode())

    def test_search_error_exact_bound_retains_structural_classification(self):
        error_body = b'{"error":{"code":"insufficient_quota"}}'.ljust(64, b" ")
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                observations = {}
                report = controlled_asgi_probe(
                    scenario=fx.search_scenario(), stream=stream, backend_mode=mode,
                    raw_request_body=json.dumps(fx.search_request(stream)).encode(),
                    response_status=400, configure_module=configure_error_budget,
                    error_body_chunks=[error_body[:32], error_body[32:]], resource_observations=observations)
                self.assertIsNone(report.raised)
                self.assertEqual(observations["error_bytes_read"], 64)
                self.assertEqual(report.stream_close_calls, 1)
                body = fx.probe_body(report)
                self.assertIn(b"invalid_request_error", body)
                self.assertNotIn(b"exceeded byte limit", body)

    def test_search_error_reader_disconnect_cancels_and_closes_once(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                observations = {}
                report = controlled_asgi_probe(
                    scenario=fx.search_scenario(), stream=stream, backend_mode=mode,
                    raw_request_body=json.dumps(fx.search_request(stream)).encode(),
                    response_status=400, configure_module=configure_error_budget,
                    error_body_chunks=[b"X" * 32] * 5, disconnect_error_read=True,
                    resource_observations=observations)
                self.assertIsNone(report.raised, observations)
                self.assertEqual(observations["error_chunks_read"], 1)
                self.assertTrue(observations["error_reader_cancelled"])
                self.assertEqual(report.stream_close_calls, 1)
                self.assertEqual(report.pending_task_count, 0, observations)

    def test_ordinary_error_reader_policy_is_unchanged(self):
        observations = {}
        report = controlled_asgi_probe(response_status=400, stream=True,
                                      configure_module=configure_error_budget,
                                      error_body_chunks=[b"X" * 32] * 5,
                                      resource_observations=observations)
        self.assertIsNone(report.raised)
        self.assertEqual(observations["error_bytes_read"], 160)
        self.assertEqual(report.stream_close_calls, 1)

    def test_search_failure_closes_before_held_downstream_send(self):
        # Three still-fatal failures at three stages: collector ceiling, collector
        # item status, and projection (forced search with no hosted evidence).
        # (v1.4.8: missing sources is no longer fatal, so it is not a case here.)
        second = copy.deepcopy(RAW_ITEMS[0])
        second["id"] = "ws_second"
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for failure in ("observed_limit", "invalid_item_status", "forced_no_search"):
                    items = copy.deepcopy(RAW_ITEMS)
                    request = fx.search_request(stream)
                    if failure == "observed_limit":
                        items.insert(1, second)
                        request["tools"][0]["max_uses"] = 1
                    elif failure == "invalid_item_status":
                        items[0]["status"] = "failed"
                    else:
                        items = items[1:]
                    observations = {}
                    report = controlled_asgi_probe(scenario=fx.search_scenario(items),
                                                  stream=stream, backend_mode=mode, send_action="hold_error",
                                                  raw_request_body=json.dumps(request).encode(),
                                                  resource_observations=observations)
                    with self.subTest(mode=mode, stream=stream, failure=failure):
                        self.assertIsNone(report.raised, observations)
                        self.assertEqual(observations["closed_at_held_send"], 1)
                        self.assertTrue(report.cancelled)
                        self.assertEqual(report.stream_close_calls, 1)
                        self.assertEqual(report.pending_task_count, 0, observations)
                        self.assertEqual(sum(line.event == "cleanup" for line in report.lifecycle), 1)


if __name__ == "__main__":
    unittest.main()
