"""Native search: ordinary delta-only truncation after search history, raw JSON.

An ordinary (no new search) continuation whose replay history contains a hosted
search uses the buffered search collector. These tests pin how it treats partial
text deltas, authoritative done/terminal text and malformed raw JSON bytes. All
queries, text and identities are synthetic; this certifies the isolated bridge,
not live providers or the installed Claude Code client.
"""
import copy
import json
import unittest
from unittest import mock

from . import _loopback_harness as h
from . import _native_search_fixtures as fx

TEXT, DELTA, TERMINAL = fx.TEXT, fx.DELTA, fx.TERMINAL


class AcceptanceTests(fx.NativeSearchCase):
    def test_delta_only_two_turn_wire_matrix(self):
        for mode, stream in [("chatgpt", False), ("chatgpt", True), ("openai", True)]:
            for shape in ("absent", "null", "empty"):
                with self.subTest(mode=mode, stream=stream, shape=shape):
                    with h.MockResponsesServer(fx.search_scenario()) as backend:
                        with h.RealShim(backend, mode) as shim:
                            shim.assert_offline_contract()
                            first = shim.post_raw_messages(json.dumps(fx.search_request(stream)).encode())
                            history = fx.collected_blocks(first, stream)
                            self.assertTrue(any(b["type"] == "server_tool_use" for b in history))
                            scenario = fx.search_scenario([])
                            terminal = copy.deepcopy(TERMINAL)
                            if shape == "absent":
                                terminal["response"].pop("output")
                            elif shape == "null":
                                terminal["response"]["output"] = None
                            # Two chunks verify append rather than last-delta wins.
                            scenario.stream_events = [{**DELTA, "delta": TEXT[:8]},
                                                      {**DELTA, "delta": TEXT[8:]}, terminal]
                            backend.scenario = scenario
                            request = fx.search_request(stream, [])
                            request["tool_choice"] = {"type": "none"}
                            request["messages"] += [{"role": "assistant", "content": history},
                                                    {"role": "user", "content": "Continue."}]
                            result = shim.post_raw_messages(json.dumps(request).encode())
                            blocks = fx.collected_blocks(result, stream)
                            self.assertEqual(result.status, 200)
                            self.assertEqual(blocks, [{"type": "text", "text": TEXT}])
                            stop = (next(e.data["delta"]["stop_reason"] for e in h.parse_typed_sse(result.body)
                                         if e.event == "message_delta") if stream else result.json()["stop_reason"])
                            self.assertEqual(stop, "max_tokens")
                            self.assertEqual(len(backend.responses_requests), 2)
                            self.assertEqual(backend.responses_requests[-1].body["tools"], [])
                            self.assertEqual(backend.responses_requests[-1].body["input"][1:3], fx.RAW_ITEMS)

    def test_authoritative_done_or_terminal_text_is_not_duplicated(self):
        for authority in ("done", "terminal"):
            with self.subTest(authority=authority):
                c = self.shim._SearchCollector(self.shim._ToolRegistry([]))
                c.event(copy.deepcopy(DELTA))
                item = {"type": "message", "id": DELTA["item_id"], "role": "assistant",
                        "status": "incomplete", "content": [{"type": "output_text", "text": "Authoritative text."}]}
                terminal = copy.deepcopy(TERMINAL)
                if authority == "done":
                    c.event({"type": "response.output_item.done", "output_index": 0, "item": item})
                else:
                    terminal["response"]["output"] = [item]
                response = c.event(terminal)
                projected = self.shim._search_projection(response, "fixture", self.shim._ToolRegistry([]))
                self.assertEqual(projected["content"], [{"type": "text", "text": "Authoritative text."}])
                self.assertEqual(projected["stop_reason"], "max_tokens")
                self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 0)

    def test_delta_fallback_does_not_become_replay_evidence(self):
        c = self.shim._SearchCollector(self.shim._ToolRegistry([]))
        c.event(copy.deepcopy(DELTA))
        response = c.event(copy.deepcopy(TERMINAL))
        self.assertEqual(c.completed, {})
        projected = self.shim._search_projection(response, "fixture", self.shim._ToolRegistry([]))
        self.assertEqual(projected["content"], [{"type": "text", "text": TEXT}])
        self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 0)
        self.assertEqual(self.shim._SEARCH_REPLAY.bytes, 0)

    def test_current_search_and_missing_success_inventory_stay_strict(self):
        for case in ("declared", "observed", "terminal_search", "completed_without_done", "failed"):
            with self.subTest(case=case):
                registry = self.shim._ToolRegistry([fx.SEARCH] if case == "declared" else [])
                c = self.shim._SearchCollector(registry)
                c.event(copy.deepcopy(DELTA))
                terminal = copy.deepcopy(TERMINAL)
                if case == "observed":
                    c.event({"type": "response.output_item.done", "output_index": 1,
                             "item": copy.deepcopy(fx.RAW_ITEMS[0])})
                elif case == "terminal_search":
                    terminal["response"]["output"] = [copy.deepcopy(fx.RAW_ITEMS[0])]
                elif case == "completed_without_done":
                    terminal["type"] = "response.completed"
                    terminal["response"]["status"] = "completed"
                elif case == "failed":
                    terminal["type"] = "response.failed"
                    terminal["response"]["status"] = "failed"
                with self.assertRaises(self.shim._ProtocolError):
                    c.event(terminal)
                self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 0)

    def test_delta_retention_bounds_and_identity_validation(self):
        size = len(self.shim._search_json(TEXT))
        with mock.patch.object(self.shim, "_SEARCH_MAX_BYTES", size):
            c = self.shim._SearchCollector(self.shim._ToolRegistry([]))
            c.event(copy.deepcopy(DELTA))
            self.assertEqual(c.retained_bytes, size)
            with self.assertRaises(self.shim._ProtocolError):
                c.event({**DELTA, "delta": "x"})
            self.assertEqual(c.partial_text[(0, 0)], [TEXT])
        for key, value in [("content_index", True), ("content_index", -1),
                           ("content_index", None), ("item_id", None), ("delta", {}),
                           ("output_index", False)]:
            with self.subTest(key=key, value=value):
                c = self.shim._SearchCollector(self.shim._ToolRegistry([]))
                with self.assertRaises(self.shim._ProtocolError):
                    c.event({**DELTA, key: value})
        c = self.shim._SearchCollector(self.shim._ToolRegistry([]))
        c.event(copy.deepcopy(DELTA))
        with self.assertRaises(self.shim._ProtocolError):
            c.event({**DELTA, "item_id": "different"})
        c = self.shim._SearchCollector(self.shim._ToolRegistry([]))
        c.event({**DELTA, "output_index": 1})
        with self.assertRaises(self.shim._ProtocolError):
            c.event(copy.deepcopy(TERMINAL))

    def test_raw_malformed_openai_json_reaches_actual_handler(self):
        # INTENT: inject invalid JSON bytes, not a malformed Python output shape.
        # REASONING: the probe serializes nonstream_response; intercept ONLY that
        # exact synthetic object. The production JSON parser/error path is untouched.
        # ASSUMES: no unrelated dump call receives this object identity.
        for invalid in ('{"RAW_JSON_PRIVATE_SENTINEL":', '{"output": [}'):
            scenario = fx.search_scenario()
            request_bytes = json.dumps(fx.search_request(False)).encode()
            original_dumps = json.dumps
            injected = []
            modules = []

            def wire_dumps(value, *args, **kwargs):
                if value is scenario.nonstream_response:
                    injected.append(invalid.encode())
                    return invalid
                return original_dumps(value, *args, **kwargs)
            with mock.patch.object(h.json, "dumps", side_effect=wire_dumps):
                report = h.controlled_asgi_probe(scenario=scenario, stream=False, backend_mode="openai",
                                                 raw_request_body=request_bytes, configure_module=modules.append)
            raw = fx.probe_body(report)
            self.assertEqual(injected, [invalid.encode()])
            self.assertIsNone(report.raised)
            self.assertEqual(report.messages[0]["status"], 502)
            self.assertEqual(json.loads(raw)["type"], "error")
            self.assertNotIn(b"RAW_JSON_PRIVATE_SENTINEL", raw)
            self.assertNotIn("RAW_JSON_PRIVATE_SENTINEL", report.logs)
            self.assertEqual(report.upstream_calls, 1)
            self.assertEqual(report.stream_close_calls, 1)
            self.assertEqual(report.pending_task_count, 0)
            self.assertEqual(len(modules[0]._SEARCH_REPLAY.groups), 0)


if __name__ == "__main__":
    unittest.main()
