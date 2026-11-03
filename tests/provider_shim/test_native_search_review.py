"""Native search: independent-review regressions (partial answers, log privacy).

Every payload value is synthetic. The privacy test distinguishes legitimate
client-visible sources from forbidden log content across both lanes and three
outcomes (success, protocol failure, HTTP failure).
"""
import copy
import json
import unittest

from . import _native_search_fixtures as fx
from ._loopback_harness import controlled_asgi_probe, parse_typed_sse

TEXT, DELTA, TERMINAL = fx.TEXT, fx.DELTA, fx.TERMINAL


class ReviewTests(fx.NativeSearchCase):
    def test_partial_answer_after_completed_or_unfinished_prefix(self):
        history = self.shim._search_projection({"status": "completed", "output": copy.deepcopy(fx.RAW_ITEMS)},
            "fixture", self.shim._ToolRegistry([fx.SEARCH]))["content"]
        token = history[0]["id"].split("_")[2]

        def seed(module):
            module._SEARCH_REPLAY.put(token, fx.RAW_ITEMS, history)
        for mode, stream in [("chatgpt", False), ("chatgpt", True), ("openai", True)]:
            for prefix in ("reasoning_done", "reasoning_added", "message_done"):
                for shape in ("absent", "null", "empty"):
                    with self.subTest(mode=mode, stream=stream, prefix=prefix, shape=shape):
                        scenario = fx.search_scenario([])
                        item = {"type": "reasoning", "id": "rs_fixture", "summary": [],
                                "status": "in_progress" if prefix.endswith("added") else "completed"}
                        expected = TEXT
                        if prefix == "message_done":
                            item = {"type": "message", "id": "msg_prefix_fixture", "role": "assistant",
                                    "status": "completed", "content": [{"type": "output_text", "text": "Earlier."}]}
                            expected = "Earlier." + TEXT
                        terminal = copy.deepcopy(TERMINAL)
                        if shape == "absent":
                            terminal["response"].pop("output")
                        elif shape == "null":
                            terminal["response"]["output"] = None
                        scenario.stream_events = [{"type": "response.output_item." + prefix.split("_")[-1],
                            "output_index": 0, "item": item}, {**DELTA, "output_index": 1}, terminal]
                        request = fx.search_request(stream, [])
                        request["tool_choice"] = {"type": "none"}
                        request["messages"].append({"role": "assistant", "content": history})
                        report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                            raw_request_body=json.dumps(request).encode(), configure_module=seed)
                        self.assertIsNone(report.raised)
                        raw = fx.probe_body(report)
                        if stream:
                            frames = parse_typed_sse(raw)
                            text = "".join(e.data.get("delta", {}).get("text", "") for e in frames)
                            stop = next(e.data["delta"]["stop_reason"] for e in frames if e.event == "message_delta")
                        else:
                            body = json.loads(raw)
                            text = "".join(b.get("text", "") for b in body["content"])
                            stop = body["stop_reason"]
                        self.assertEqual(text, expected)
                        self.assertEqual(stop, "max_tokens")
                        self.assertNotIn(b"server_tool_use", raw)
                        self.assertEqual(report.stream_close_calls, 1)
                        self.assertEqual(report.pending_task_count, 0)

    def test_sensitive_search_fields_never_enter_logs(self):
        # INTENT: distinguish legitimate client-visible sources from forbidden log
        # content, for both lanes and success, protocol failure and HTTP failure.
        # ASSUMES: all sentinel strings here are synthetic, not real credentials.
        # The protocol failure is a non-completed hosted item (still fatal in v1.4.8;
        # the draft's missing-sources trigger is now a tolerated skip).
        sentinels = ["PRIVATE_QUERY_SENTINEL", "PRIVATE_ANSWER_SENTINEL",
                     "private-source-sentinel", "PRIVATE_SOURCE_TITLE_SENTINEL",
                     "PRIVATE_CITATION_TITLE_SENTINEL", "PRIVATE_CIPHERTEXT_SENTINEL",
                     "PRIVATE_HEADER_SENTINEL"]
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for outcome in ("success", "protocol_failure", "http_failure"):
                    with self.subTest(mode=mode, stream=stream, outcome=outcome):
                        items = copy.deepcopy(fx.RAW_ITEMS)
                        items[0]["action"].update(query=sentinels[0], queries=[sentinels[0]],
                            sources=[{"type": "url", "url": "https://example.org/" + sentinels[2],
                                      "title": sentinels[3]}])
                        items[1]["content"][0].update(text=sentinels[1], annotations=[{
                            "type": "url_citation", "url": "https://example.org/" + sentinels[2],
                            "title": sentinels[4], "start_index": 0, "end_index": 7}])
                        items.insert(0, {"type": "reasoning", "id": "rs_privacy_fixture",
                            "status": "completed", "summary": [], "encrypted_content": sentinels[5]})
                        if outcome == "protocol_failure":
                            items[1]["status"] = "failed"
                        scenario = fx.search_scenario(items)
                        scenario.stream_error_body = json.dumps({"error": {"type": "invalid_request_error",
                            "message": " ".join(sentinels)}}).encode()
                        request = fx.search_request(stream)
                        request["messages"][0]["content"] = sentinels[0]
                        report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                            response_status=400 if outcome == "http_failure" else 200,
                            response_headers={"content-type": "text/event-stream" if stream or mode == "chatgpt"
                                              else "application/json", "x-private-fixture": sentinels[6]},
                            raw_request_body=json.dumps(request).encode())
                        self.assertIsNone(report.raised)
                        raw = fx.probe_body(report)
                        for sentinel in sentinels:
                            self.assertNotIn(sentinel, report.logs)
                            if outcome != "success":
                                self.assertNotIn(sentinel.encode(), raw)
                        if outcome == "success":
                            self.assertIn(sentinels[1].encode(), raw)
                            self.assertIn(sentinels[2].encode(), raw)
                            self.assertNotIn(sentinels[5].encode(), raw)
                            self.assertNotIn(sentinels[6].encode(), raw)
                        else:
                            self.assertIn(b"error", raw)
                        self.assertEqual(report.upstream_calls, 1)
                        self.assertEqual(report.stream_close_calls, 1)
                        self.assertEqual(report.pending_task_count, 0)


if __name__ == "__main__":
    unittest.main()
