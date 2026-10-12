"""Native search: compatibility regressions from the v1.4.0/1.4.1 review rounds.

INTENT: drive five independent review hypotheses (H1 optional function ids, H2
absent/null/empty terminal inventories, H3 history-only truncation, H4 usage
provenance, H5 citation offsets) plus handler-level acceptance matrices through
the real translation code.
REASONING: native search must not change ordinary-generation semantics.
ASSUMES: synthetic fixtures certify implementation only, not live API/CLI support.

"v1.4.8" marks cells rewritten to the v1.4.8 tolerant contract (per-lane
blocked_domains mapping/drop; unrecognized hosted-action shapes skipped instead
of failing the turn). They fail against v1.4.7 by design.
"""
import copy
import json
import unittest
from unittest import mock

from . import _native_search_fixtures as fx
from ._loopback_harness import MockResponsesServer, RealShim, controlled_asgi_probe, parse_typed_sse

FUNCTION_ITEM = fx.FUNCTION_ITEM
response_body = fx.response_body


class CompatibilityTests(fx.NativeSearchCase):
    def test_acceptance_success_failure_action_handler_matrix(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for case in ("empty", "missing_sources", "failed", "no_search", "open_page", "find_in_page", "bad_output", "incomplete"):
                    items = copy.deepcopy(fx.RAW_ITEMS)
                    if case == "empty":
                        items[0]["action"]["sources"] = []; items[1]["content"][0]["annotations"] = []
                    elif case == "missing_sources": items[0]["action"].pop("sources")
                    elif case == "failed": items[0]["status"] = "failed"
                    elif case == "no_search": items = items[1:]
                    # Page action types carrying search-only fields (no url/pattern).
                    elif case in ("open_page", "find_in_page"): items[0]["action"]["type"] = case
                    scenario = fx.search_scenario(items)
                    if case == "bad_output":
                        scenario.nonstream_response["output"] = {}
                        scenario.stream_events[-1]["response"]["output"] = {}
                    elif case == "incomplete":
                        scenario.nonstream_response["status"] = "incomplete"
                        scenario.stream_events[-1]["response"]["status"] = "incomplete"
                        scenario.stream_events[-1]["type"] = "response.incomplete"
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(fx.search_request(stream)).encode())
                    raw = fx.probe_body(report)
                    with self.subTest(mode=mode, stream=stream, case=case):
                        self.assertIsNone(report.raised)
                        self.assertEqual(report.upstream_calls, 1)
                        self.assertEqual(report.stream_close_calls, 1)
                        self.assertEqual(report.pending_task_count, 0)
                        if case == "empty":
                            self.assertIn(b"web_search_tool_result", raw)
                            self.assertNotIn(b'"type": "error"', raw)
                        elif case in ("missing_sources", "open_page", "find_in_page"):
                            # v1.4.8 (formerly fatal): the unrenderable search or
                            # find is skipped; open_page keeps only documented keys.
                            self.assertNotIn(b'"type": "error"', raw)
                            self.assertIn(b"Synthetic answer about IANA.", raw)
                            self.assertNotIn(b"web_search_tool_result", raw)
                            self.assertEqual(b"server_tool_use" in raw, case == "open_page")
                        else:
                            self.assertIn(b'"type": "error"', raw)
                            self.assertNotIn(b"server_tool_use", raw)

    def test_acceptance_domain_location_controls_handler_matrix(self):
        location = {"type": "approximate", "country": "US", "city": "New York",
                    "region": "New York", "timezone": "America/New_York"}
        invalid = [{"allowed_domains": [value]} for value in
                   ("", "localhost", "bad..org", "-bad.org", "bad_.org", "*.iana.org",
                    "https://iana.org", "iana.org/path", "iana.org:443")]
        invalid += [{"allowed_domains": ["iana.org", "IANA.org"]}]
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                tool = {**fx.SEARCH, "allowed_domains": ["iana.org", "example.org"], "blocked_domains": [], "user_location": location}
                report = controlled_asgi_probe(scenario=fx.search_scenario(), stream=stream, backend_mode=mode,
                    raw_request_body=json.dumps(fx.search_request(stream, [tool])).encode())
                self.assertIsNone(report.raised)
                outbound = report.outbound_payloads[0]["tools"][0]
                self.assertEqual(outbound["filters"], {"allowed_domains": ["iana.org", "example.org"]})
                self.assertEqual(outbound["user_location"], location)
                for option in invalid:
                    request = fx.search_request(stream, [{**fx.SEARCH, **option}])
                    report = controlled_asgi_probe(stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(request).encode())
                    self.assertIsNone(report.raised)
                    self.assertEqual(report.messages[0]["status"], 400)
                    self.assertEqual((report.auth_calls, report.upstream_calls), (0, 0))

    def test_v148_blocked_domains_cell_mapped_or_dropped_per_lane(self):
        # v1.4.8: formerly in the 400 list above. openai lane merges the blocklist
        # into filters; chatgpt lane drops it. Allowlist and location always map.
        location = {"type": "approximate", "country": "US", "timezone": "America/New_York"}
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    tool = {**fx.SEARCH, "allowed_domains": ["iana.org"], "blocked_domains": ["example.com"],
                            "user_location": location}
                    report = controlled_asgi_probe(scenario=fx.search_scenario(), stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(fx.search_request(stream, [tool])).encode())
                    self.assertIsNone(report.raised)
                    self.assertEqual(report.messages[0]["status"], 200)
                    self.assertEqual(report.upstream_calls, 1)
                    filters = {"allowed_domains": ["iana.org"]}
                    if mode == "openai":
                        filters["blocked_domains"] = ["example.com"]
                    self.assertEqual(report.outbound_payloads[0]["tools"],
                                     [{"type": "web_search", "external_web_access": True,
                                       "filters": filters, "user_location": location}])

    def test_acceptance_multisearch_function_wire_replay_order(self):
        second = copy.deepcopy(fx.RAW_ITEMS[0]); second["id"] = "ws_second"
        function = {k: v for k, v in FUNCTION_ITEM.items() if k != "id"}
        items = [fx.RAW_ITEMS[0], function, second, fx.RAW_ITEMS[1]]
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with MockResponsesServer(fx.search_scenario(items)) as backend:
                    with RealShim(backend, mode) as shim:
                        request = fx.search_request(stream, [fx.SEARCH, fx.FUNCTION])
                        request["tool_choice"] = {"type": "auto"}
                        result = shim.post_raw_messages(json.dumps(request).encode())
                        blocks = fx.collected_blocks(result, stream)
                        self.assertEqual([b["type"] for b in blocks], ["server_tool_use", "web_search_tool_result",
                            "tool_use", "server_tool_use", "web_search_tool_result", "text", "text"])
                        self.assertEqual(blocks[0]["id"], blocks[1]["tool_use_id"])
                        self.assertEqual(blocks[3]["id"], blocks[4]["tool_use_id"])
                        self.assertNotEqual(blocks[0]["id"], blocks[3]["id"])
                        self.assertEqual(blocks[2]["id"], "call_fixture")
                        stop = (next(e.data["delta"]["stop_reason"] for e in parse_typed_sse(result.body)
                                     if e.event == "message_delta") if stream else result.json()["stop_reason"])
                        self.assertEqual(stop, "tool_use")
                        follow = fx.search_request(stream, [])
                        follow["tool_choice"] = {"type": "none"}
                        follow["messages"] += [{"role": "assistant", "content": blocks}, {"role": "user",
                            "content": [{"type": "tool_result", "tool_use_id": "call_fixture", "content": "fixture result"}]}]
                        backend.scenario = fx.search_scenario([fx.RAW_ITEMS[1]])
                        replay = shim.post_raw_messages(json.dumps(follow).encode())
                        self.assertEqual(replay.status, 200)
                        self.assertEqual(fx.collected_blocks(replay, stream)[0]["text"], fx.RAW_ITEMS[1]["content"][0]["text"])
                        actual = backend.responses_requests[-1].body["input"]
                        self.assertEqual(actual[1:5], items)
                        self.assertEqual(actual[-1]["type"], "function_call_output")
                        self.assertEqual(actual[-1]["call_id"], "call_fixture")
                        self.assertEqual(len(backend.responses_requests), 2)

    def test_acceptance_collector_exact_bounds(self):
        events = fx.search_scenario().stream_events
        exact_bytes = sum(len(self.shim._search_json(e["item"])) for e in events[:-1])
        limits = {"_SEARCH_MAX_BYTES": exact_bytes, "_SEARCH_MAX_ITEMS": 2, "_SEARCH_MAX_EVENTS": 3}
        with mock.patch.multiple(self.shim, **limits):
            c = self.shim._SearchCollector(self.shim._ToolRegistry([fx.SEARCH]))
            for e in events: terminal = c.event(copy.deepcopy(e))
            self.assertEqual(terminal["output"], fx.RAW_ITEMS)
        for key, value in limits.items():
            with self.subTest(bound=key), mock.patch.object(self.shim, key, value - 1):
                c = self.shim._SearchCollector(self.shim._ToolRegistry([fx.SEARCH]))
                with self.assertRaises(self.shim._ProtocolError):
                    for e in events: c.event(copy.deepcopy(e))

    def test_acceptance_cache_exact_bounds_ttl_and_split_rejection(self):
        registry = self.shim._ToolRegistry([fx.SEARCH])
        blocks = self.shim._search_projection({"status": "completed", "output": copy.deepcopy(fx.RAW_ITEMS)},
                                              "fixture", registry)["content"]
        token = blocks[0]["id"].split("_")[2]
        size = len(self.shim._search_json(fx.RAW_ITEMS)) + 32 * len(blocks)
        messages = [{"role": "assistant", "content": blocks}]
        with mock.patch.object(self.shim, "_SEARCH_MAX_BYTES", size), \
             mock.patch.object(self.shim, "_SEARCH_REPLAY_MAX_BYTES", size), \
             mock.patch.object(self.shim, "_SEARCH_REPLAY_MAX_GROUPS", 1):
            self.shim._SEARCH_REPLAY = self.shim._SearchReplayCache()
            with mock.patch.object(self.shim.time, "monotonic", return_value=100):
                self.shim._SEARCH_REPLAY.put(token, fx.RAW_ITEMS, blocks)
            self.assertEqual(self.shim._SEARCH_REPLAY.bytes, size)
            with mock.patch.object(self.shim.time, "monotonic", return_value=100 + self.shim._SEARCH_REPLAY_TTL):
                self.assertEqual(list(self.shim._SEARCH_REPLAY.plan(messages)[0].values()), [fx.RAW_ITEMS])
                with self.assertRaises(self.shim._InvalidRequestError):
                    self.shim._SEARCH_REPLAY.plan([{"role": "assistant", "content": blocks[:2]},
                                                   {"role": "assistant", "content": blocks[2:]}])
            with mock.patch.object(self.shim.time, "monotonic", return_value=100 + self.shim._SEARCH_REPLAY_TTL + .001):
                with self.assertRaises(self.shim._InvalidRequestError): self.shim._SEARCH_REPLAY.plan(messages)
            self.assertEqual(self.shim._SEARCH_REPLAY.bytes, 0)
        for limit in ("_SEARCH_MAX_BYTES", "_SEARCH_REPLAY_MAX_BYTES"):
            with mock.patch.object(self.shim, limit, size - 1):
                with self.assertRaises(self.shim._ProtocolError): self.shim._SEARCH_REPLAY.put(token, fx.RAW_ITEMS, blocks)
        self.shim._SEARCH_REPLAY = self.shim._SearchReplayCache()
        with self.assertRaises(self.shim._InvalidRequestError): self.shim._SEARCH_REPLAY.plan(messages)

    def test_h5_offsets_explicit_policy_preserves_original_annotation(self):
        cases = [("missing", None, None), ("boolean", True, 6), ("string", "0", 6),
                 ("negative", -1, 6), ("reversed", 6, 1), ("empty", 1, 1),
                 ("outside", 0, 500), ("unicode", 0, 2), ("unicode_utf16", 0, 4),
                 ("valid", 0, 6)]
        for label, start, end in cases:
            items = copy.deepcopy(fx.RAW_ITEMS)
            part = items[1]["content"][0]
            if label.startswith("unicode"): part["text"] = "é😀X"
            annotation = part["annotations"][0]
            if label == "missing":
                annotation.pop("start_index"); annotation.pop("end_index")
            else:
                annotation.update(start_index=start, end_index=end)
            before = copy.deepcopy(items)
            result = self.shim._search_projection({"status": "completed", "output": items},
                                                  "fixture", self.shim._ToolRegistry([fx.SEARCH]))
            with self.subTest(case=label):
                attribution = result["content"][-1]["text"]
                self.assertEqual("text spans unverified" in attribution, label != "valid")
                self.assertIn("[Example Domains](", attribution)
                self.assertNotIn("cited_text", json.dumps(result))
                self.assertNotIn("encrypted_index", json.dumps(result))
                self.assertEqual(items, before)
                self.assertEqual(self.shim._messages_to_input([{"role": "assistant", "content": result["content"]}])[0], before)

    def test_h5_malformed_offsets_handler_matrix(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                items = copy.deepcopy(fx.RAW_ITEMS)
                items[1]["content"][0]["annotations"][0]["start_index"] = False
                report = controlled_asgi_probe(scenario=fx.search_scenario(items), stream=stream, backend_mode=mode,
                    raw_request_body=json.dumps(fx.search_request(stream)).encode())
                self.assertIsNone(report.raised)
                raw = fx.probe_body(report)
                self.assertIn(b"Provider-linked sources (text spans unverified)", raw)
                self.assertNotIn(b"cited_text", raw)
                self.assertEqual((response_body(report, stream).get("delta") or response_body(report, stream))["stop_reason"], "end_turn")

    def test_h4_usage_matrix_preserves_zero_and_estimation_provenance(self):
        cases = [("absent", None, 7, "estimated"), ("container", [], 7, "estimated"),
                 ("bool", {"input_tokens": 31, "output_tokens": True}, 7, "estimated"),
                 ("string", {"input_tokens": 31, "output_tokens": "17"}, 7, "estimated"),
                 ("negative", {"input_tokens": 31, "output_tokens": -1}, 7, "estimated"),
                 ("zero", {"input_tokens": 0, "output_tokens": 0}, 0, "backend"),
                 ("missing_input", {"output_tokens": 17}, 17, "estimated"),
                 ("measured", {"input_tokens": 31, "output_tokens": 17}, 17, "backend")]
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for label, usage, expected, source in cases:
                    scenario = fx.search_scenario()
                    for terminal in (scenario.nonstream_response, scenario.stream_events[-1]["response"]):
                        if label == "absent": terminal.pop("usage")
                        else: terminal["usage"] = copy.deepcopy(usage)
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(fx.search_request(stream)).encode())
                    with self.subTest(mode=mode, stream=stream, case=label):
                        self.assertIsNone(report.raised)
                        result = response_body(report, stream)
                        self.assertEqual(result["usage"]["output_tokens"], expected)
                        self.assertIn("usage=" + source, report.logs)
                        self.assertEqual(set(result["usage"]), {"input_tokens", "output_tokens",
                            "cache_read_input_tokens", "cache_creation_input_tokens"})
                        self.assertNotIn(b"_usage_source", fx.probe_body(report))
                        self.assertEqual(report.stream_close_calls, 1)

    def test_h3_history_only_truncation_matrix_and_search_integrity(self):
        history = self.shim._search_projection({"status": "completed", "output": copy.deepcopy(fx.RAW_ITEMS)},
                                              "fixture", self.shim._ToolRegistry([fx.SEARCH]))["content"]
        token = history[0]["id"].split("_")[2]

        def seed(module):
            module._SEARCH_REPLAY.put(token, fx.RAW_ITEMS, history)
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for done in (False, True):
                    item = copy.deepcopy(fx.RAW_ITEMS[1]); item["status"] = "incomplete"
                    scenario = fx.search_scenario([item], terminal_empty=False)
                    scenario.nonstream_response["status"] = "incomplete"
                    scenario.stream_events[-1]["type"] = "response.incomplete"
                    scenario.stream_events[-1]["response"]["status"] = "incomplete"
                    if not done:
                        scenario.stream_events[0] = {"type": "response.output_item.added", "output_index": 0,
                            "item": {"type": "message", "id": item["id"], "status": "in_progress", "role": "assistant", "content": []}}
                    request = fx.search_request(stream, [])
                    request["tool_choice"] = {"type": "none"}
                    request["messages"].append({"role": "assistant", "content": history})
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(request).encode(), configure_module=seed)
                    with self.subTest(mode=mode, stream=stream, done=done):
                        self.assertIsNone(report.raised)
                        result = response_body(report, stream)
                        self.assertEqual((result.get("delta") or result).get("stop_reason"), "max_tokens")
                        raw = fx.probe_body(report)
                        self.assertIn(item["content"][0]["text"].encode(), raw)
                        self.assertNotIn(b"server_tool_use", raw)
                        self.assertEqual(report.stream_close_calls, 1)
                # An actual or requested hosted search cannot borrow the ordinary exception.
                for current in ("declared", "unexpected"):
                    scenario = fx.search_scenario()
                    scenario.nonstream_response["status"] = "incomplete"
                    scenario.stream_events[-1]["type"] = "response.incomplete"
                    scenario.stream_events[-1]["response"]["status"] = "incomplete"
                    request = fx.search_request(stream, [fx.SEARCH] if current == "declared" else [])
                    request["tool_choice"] = {"type": "auto"}
                    request["messages"].append({"role": "assistant", "content": history})
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(request).encode(), configure_module=seed)
                    raw = fx.probe_body(report)
                    self.assertNotIn(b'"stop_reason": "max_tokens"', raw)
                    self.assertIn(b"error", raw)

    def test_h2_absent_null_empty_inventory_and_conflict_controls(self):
        for shape in ("absent", "null", "empty", "nonempty"):
            for mutation in ("none", "gap", "missing_done", "duplicate_id", "nonempty_conflict"):
                events = copy.deepcopy(fx.search_scenario().stream_events)
                terminal = events[-1]["response"]
                if shape == "absent": terminal.pop("output")
                elif shape == "null": terminal["output"] = None
                elif shape == "nonempty": terminal["output"] = copy.deepcopy(fx.RAW_ITEMS)
                if mutation == "gap": events[1]["output_index"] = 2
                elif mutation == "missing_done": events[1]["type"] = "response.output_item.added"
                elif mutation == "duplicate_id": events[1]["item"]["id"] = events[0]["item"]["id"]
                elif mutation == "nonempty_conflict": terminal["output"] = [fx.RAW_ITEMS[0]]
                c = self.shim._SearchCollector(self.shim._ToolRegistry([fx.SEARCH]))
                with self.subTest(shape=shape, mutation=mutation):
                    if mutation == "none":
                        c.event(events[0]); c.event(events[0]); c.event(events[1])
                        self.assertEqual(c.event(events[-1])["output"], fx.RAW_ITEMS)
                    else:
                        with self.assertRaises(self.shim._ProtocolError):
                            for e in events: c.event(e)

    def test_h2_terminal_shapes_stream_transport_matrix(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for shape in ("absent", "null", "empty"):
                    scenario = fx.search_scenario()
                    terminal = scenario.stream_events[-1]["response"]
                    if shape == "absent": terminal.pop("output")
                    elif shape == "null": terminal["output"] = None
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(fx.search_request(stream)).encode())
                    self.assertIsNone(report.raised)
                    result = response_body(report, stream)
                    self.assertEqual((result.get("delta") or result).get("stop_reason"), "end_turn")

    def test_h1_optional_id_preserves_raw_inventory_and_replay(self):
        registry = self.shim._ToolRegistry([fx.SEARCH, fx.FUNCTION])
        done = {k: v for k, v in FUNCTION_ITEM.items() if k != "id"}
        for registration in ("added", "none", "call_id_only"):
            c = self.shim._SearchCollector(registry)
            c.event(fx.search_scenario().stream_events[0])
            if registration != "none":
                c.event({"type": "response.output_item.added", "output_index": 1, "item": FUNCTION_ITEM})
            event = {"type": "response.output_item.done", "output_index": 1, "item": done}
            if registration == "call_id_only":
                event.pop("output_index")
            c.event(event)
            c.event(event)  # exact duplicate remains idempotent
            terminal = c.event({"type": "response.completed", "response": {"status": "completed", "output": []}})
            self.assertEqual(terminal["output"], [fx.RAW_ITEMS[0], done])
            blocks = self.shim._search_projection(terminal, "fixture", registry)["content"]
            replay = self.shim._messages_to_input([{"role": "assistant", "content": blocks}])[0]
            self.assertEqual(replay, [fx.RAW_ITEMS[0], done])
            self.assertNotIn("id", replay[1])

    def test_h1_identity_conflicts_remain_errors(self):
        for mutation in ("call_id", "name", "index", "id", "duplicate_call_id"):
            c = self.shim._SearchCollector(self.shim._ToolRegistry([fx.SEARCH, fx.FUNCTION]))
            c.event({"type": "response.output_item.added", "output_index": 0, "item": FUNCTION_ITEM})
            done = {k: v for k, v in FUNCTION_ITEM.items() if k != "id"}
            event = {"type": "response.output_item.done", "output_index": 0, "item": done}
            if mutation in ("call_id", "name", "id"):
                done[mutation] = "conflicting"
            else:
                event["output_index"] = 1
                if mutation == "duplicate_call_id":
                    done["id"] = "other_id"
            with self.subTest(mutation=mutation), self.assertRaises(self.shim._ProtocolError):
                c.event(event)

    def test_h1_mixed_and_history_only_handler_matrix(self):
        done = {k: v for k, v in FUNCTION_ITEM.items() if k != "id"}
        history = self.shim._search_projection({"status": "completed", "output": copy.deepcopy(fx.RAW_ITEMS)},
                                              "fixture", self.shim._ToolRegistry([fx.SEARCH]))["content"]
        token = history[0]["id"].split("_")[2]

        def seed(module):
            module._SEARCH_REPLAY.put(token, fx.RAW_ITEMS, history)
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for historical in (False, True):
                    items = [done] if historical else [fx.RAW_ITEMS[0], done]
                    scenario = fx.search_scenario(items)
                    scenario.stream_events.insert(len(items) - 1, {"type": "response.output_item.added",
                        "output_index": len(items) - 1, "item": copy.deepcopy(FUNCTION_ITEM)})
                    request = fx.search_request(stream, [fx.FUNCTION] if historical else [fx.SEARCH, fx.FUNCTION])
                    request["tool_choice"] = {"type": "auto"}
                    if historical:
                        request["messages"].append({"role": "assistant", "content": history})
                    report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                        raw_request_body=json.dumps(request).encode(), configure_module=seed)
                    with self.subTest(mode=mode, stream=stream, historical=historical):
                        self.assertIsNone(report.raised)
                        result = response_body(report, stream)
                        self.assertEqual((result.get("delta") or result).get("stop_reason"), "tool_use")
                        self.assertEqual(report.stream_close_calls, 1)
                        self.assertEqual(report.pending_task_count, 0)


if __name__ == "__main__":
    unittest.main()
