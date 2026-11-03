"""Native WebSearch bridge: declaration registry and hosted-search projection.

Offline contracts for shim v1.4.0+ (web_search_20250305 -> Responses web_search,
bounded collection, process-local replay). All wire values are synthetic (see
_native_search_fixtures). Domain/location and OpenAI-lane cases certify request
translation only, not live provider support.

"v1.4.8" markers flag assertions written to the v1.4.8 TOLERANT WebSearch
contract: newer web_search_YYYYMMDD versions accepted; the valid bare domains of
a nonempty blocked_domains list mapped to filters.blocked_domains on the openai
lane, and filtered from the projected results (with a note and a WARNING) on the
chatgpt lane; disable_parallel_tool_use with search -> parallel_tool_calls;
unrecognized hosted-action shapes and sources skipped with a WARNING. Identity,
status and coverage checks still fail closed.
"""
import copy
import json
import unittest
from unittest import mock

from . import _native_search_fixtures as fx
from ._loopback_harness import (
    MockResponsesServer, RealShim, controlled_asgi_probe, full_response_scenario,
    lifecycle_report, parse_typed_sse,
)

SEARCH, FUNCTION, RAW_ITEMS = fx.SEARCH, fx.FUNCTION, fx.RAW_ITEMS
HOSTED = {"type": "web_search", "external_web_access": True}


class RegistryTests(fx.NativeSearchCase):
    def test_forced_payload_and_independent_lane_caps(self):
        for mode in ("openai", "chatgpt"):
            with self.subTest(mode=mode), mock.patch.object(self.shim, "SHIM_BACKEND_MODE", mode):
                request = {"tools": [SEARCH], "tool_choice": {"type": "tool", "name": "web_search"},
                           "max_tokens": 100, "messages": [{"role": "user", "content": "fixture"}]}
                payload = self.shim._anthropic_to_responses_request(request, "gpt-fixture", None)[0]
                self.assertEqual(payload["tools"], [HOSTED])
                self.assertEqual(payload["tool_choice"], "required")
                self.assertFalse(payload["store"])
                self.assertEqual(payload["include"], ["reasoning.encrypted_content", "web_search_call.action.sources"])
                self.assertEqual(payload.get("max_tool_calls"), 8 if mode == "openai" else None)
                self.assertNotIn("max_uses", payload)

    def test_ordinary_search_named_functions_remain_functions(self):
        for name in ("WebSearch", "web_search"):
            request = {"tools": [{**FUNCTION, "name": name}],
                       "tool_choice": {"type": "tool", "name": name}}
            payload = self.shim._anthropic_to_responses_request(request, "gpt-fixture", None)[0]
            self.assertEqual(payload["tools"][0]["type"], "function")
            self.assertEqual(payload["tool_choice"], {"type": "function", "name": name})
            self.assertEqual(payload["include"], ["reasoning.encrypted_content"])

    def test_controls_preserved_without_live_certification(self):
        location = {"type": "approximate", "country": "US", "city": "New York", "timezone": "America/New_York"}
        registry = self.shim._ToolRegistry([{**SEARCH, "allowed_domains": ["iana.org"], "user_location": location}])
        self.assertEqual(registry.tools[0]["filters"], {"allowed_domains": ["iana.org"]})
        self.assertEqual(registry.tools[0]["user_location"], location)
        self.assertEqual(registry.max_uses, 8)

    def test_invalid_declarations_and_controls(self):
        # Malformed declarations still fail closed under v1.4.8. The former entries
        # for a newer web_search_* version and a nonempty blocklist moved to the
        # v1.4.8 tolerance tests below; an undated web_search_* type stays invalid.
        variants = [
            {**SEARCH, "type": "web_search_latest"},
            {**SEARCH, "name": "WebSearch"},
            {**SEARCH, "input_schema": {}},
            {**SEARCH, "allowed_domains": ["iana.org/help"]},
            {**SEARCH, "allowed_domains": ["https://iana.org"]},
            {**SEARCH, "allowed_domains": ["*.iana.org"]},
            {**SEARCH, "allowed_domains": ["iana.org", "IANA.org"]},
            {**SEARCH, "user_location": {"type": "precise"}},
            {**SEARCH, "user_location": {"type": "approximate", "timezone": "../invalid"}},
            {**SEARCH, "type": "bash_20250124"},
        ]
        variants += [{**SEARCH, "max_uses": value} for value in (0, -1, True, 1.5, "8", None, 101)]
        for declaration in variants:
            with self.subTest(declaration=declaration):
                with self.assertRaises(self.shim._InvalidRequestError):
                    self.shim._ToolRegistry([declaration])
        for tools in ([SEARCH, SEARCH], [SEARCH, {**FUNCTION, "name": "web_search"}], [FUNCTION, FUNCTION]):
            with self.assertRaises(self.shim._InvalidRequestError):
                self.shim._ToolRegistry(tools)

    def test_v148_newer_web_search_versions_are_accepted(self):
        # v1.4.8: a dated web_search_YYYYMMDD version newer than 20250305 maps to
        # the same hosted tool instead of a 400 "unsupported tool ... version".
        for version in ("web_search_20260209", "web_search_20991231"):
            with self.subTest(version=version):
                registry = self.shim._ToolRegistry([{**SEARCH, "type": version}],
                                                   {"type": "tool", "name": "web_search"})
                self.assertEqual(registry.tools, [HOSTED])
                self.assertEqual(registry.search_name, "web_search")
                self.assertTrue(registry.forced_search)
                self.assertEqual(registry.max_uses, 8)

    def test_v148_nonempty_blocked_domains_mapped_or_filtered_per_lane(self):
        # v1.4.8 (was a 400): the openai lane forwards the valid bare domains of a
        # blocklist (deduplicated case-insensitively, merged with any allowlist) to
        # the documented filters.blocked_domains and warns only about the invalid
        # entries. The chatgpt lane cannot send the exclusion upstream, so it keeps
        # the valid domains for shim-side result filtering (see the projection
        # tests) and warns. Neither lane widens a blocklist into an allowlist, and
        # domains never reach the log.
        cases = [
            # (blocked, forwarded on openai, warns on openai)
            (["example.com"], ["example.com"], False),
            (["https://example.com/path"], [], True),
            (["example.com", "https://example.com/path", "EXAMPLE.com", "other.example"],
             ["example.com", "other.example"], True),
        ]
        for mode in ("openai", "chatgpt"):
            for allowed in ({}, {"allowed_domains": []}, {"allowed_domains": ["iana.org"]}):
                for blocked, forwarded, openai_warns in cases:
                    with self.subTest(mode=mode, allowed=allowed, blocked=blocked), \
                            mock.patch.object(self.shim, "SHIM_BACKEND_MODE", mode):
                        declaration = {**SEARCH, **allowed, "blocked_domains": blocked}
                        original = copy.deepcopy(declaration)
                        expected = dict(HOSTED)
                        filters = {}
                        if allowed.get("allowed_domains"):
                            filters["allowed_domains"] = ["iana.org"]
                        if mode == "openai" and forwarded:
                            filters["blocked_domains"] = forwarded
                        if filters:
                            expected["filters"] = filters
                        if mode == "openai" and not openai_warns:
                            registry = self.shim._ToolRegistry([declaration])
                        else:
                            with self.assertLogs(self.shim.log, level="WARNING") as captured:
                                registry = self.shim._ToolRegistry([declaration])
                            self.assertNotIn("example", "\n".join(captured.output))
                        if mode == "chatgpt":
                            self.assertNotIn("example", json.dumps(registry.tools))
                            self.assertEqual(registry.blocked_domains, forwarded)
                        else:
                            self.assertEqual(registry.blocked_domains, [])
                        self.assertEqual(registry.tools, [expected])
                        self.assertEqual(declaration, original)

    def test_explicit_empty_filters_preserve_semantics(self):
        variants = [
            {}, {"allowed_domains": []}, {"blocked_domains": []},
            {"allowed_domains": [], "blocked_domains": []},
            {"allowed_domains": ["iana.org"]},
            {"allowed_domains": ["iana.org"], "blocked_domains": []},
        ]
        for mode in ("openai", "chatgpt"):
            for filters in variants:
                with self.subTest(mode=mode, filters=filters), mock.patch.object(self.shim, "SHIM_BACKEND_MODE", mode):
                    declaration = {**SEARCH, **filters}
                    original = copy.deepcopy(declaration)
                    registry = self.shim._ToolRegistry([declaration], {"type": "auto"})
                    expected = dict(HOSTED)
                    if filters.get("allowed_domains"):
                        expected["filters"] = {"allowed_domains": ["iana.org"]}
                    self.assertEqual(registry.tools, [expected])
                    self.assertEqual(registry.choice, "auto")
                    self.assertEqual(registry.max_uses, 8)
                    self.assertEqual(declaration, original)

    def test_malformed_filter_lookalikes_and_unknown_options_fail_closed(self):
        # A non-list (or non-string / empty-string entries) is malformed, not a
        # droppable blocklist: both filter keys still fail closed in v1.4.8.
        for key in ("allowed_domains", "blocked_domains"):
            for value in (None, False, 0, "", {}, (), [None], [False], [0], [""], [{}], [[]]):
                with self.subTest(key=key, value=value), self.assertRaises(self.shim._InvalidRequestError):
                    self.shim._ToolRegistry([{**SEARCH, key: value}])
        with self.assertRaisesRegex(self.shim._InvalidRequestError, "unsupported server search option"):
            self.shim._ToolRegistry([{**SEARCH, "blocked_domains": [], "unknown_option": []}])

    def test_empty_filters_real_transport_both_lanes(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with MockResponsesServer(fx.search_scenario()) as backend:
                    with RealShim(backend, mode) as shim:
                        shim.assert_offline_contract()
                        for filters in ({"allowed_domains": ["iana.org"], "blocked_domains": []},
                                        {"allowed_domains": [], "blocked_domains": []}):
                            result = shim.post_raw_messages(json.dumps(fx.search_request(stream, [{**SEARCH, **filters}])).encode())
                            self.assertEqual(result.status, 200, result.text)
                            self.assertIn("Synthetic answer about IANA.", result.text)
                            expected = dict(HOSTED)
                            if filters["allowed_domains"]:
                                expected["filters"] = {"allowed_domains": ["iana.org"]}
                            self.assertEqual(backend.responses_requests[-1].body["tools"], [expected])
                        self.assertEqual(len(backend.responses_requests), 2)

    def test_choices_fail_closed(self):
        invalid_choices = ["required", {"type": "future"}, {"type": "tool", "name": "undeclared"},
                           {"type": "none", "name": "web_search"},
                           {"type": "auto", "disable_parallel_tool_use": "yes"}]
        for choice in invalid_choices:
            with self.subTest(choice=choice), self.assertRaises(self.shim._InvalidRequestError):
                self.shim._ToolRegistry([SEARCH], choice)
        with self.assertRaises(self.shim._InvalidRequestError):
            self.shim._ToolRegistry([SEARCH, FUNCTION], {"type": "tool", "name": "web_search"})
        self.assertEqual(self.shim._ToolRegistry([SEARCH], {"type": "none"}).choice, "none")
        self.assertTrue(self.shim._ToolRegistry([SEARCH], {"type": "any"}).forced_search)

    def test_v148_disable_parallel_with_search_maps_to_parallel_false(self):
        # v1.4.8: previously a 400 ("parallel search control is not
        # established"); now forwarded as the Responses parallel_tool_calls:false.
        for tools in ([SEARCH], [SEARCH, FUNCTION]):
            with self.subTest(tools=[t["name"] for t in tools]):
                request = {"tools": copy.deepcopy(tools), "max_tokens": 100,
                           "tool_choice": {"type": "auto", "disable_parallel_tool_use": True},
                           "messages": [{"role": "user", "content": "fixture"}]}
                payload = self.shim._anthropic_to_responses_request(request, "gpt-fixture", None)[0]
                self.assertIs(payload["parallel_tool_calls"], False)
                self.assertEqual(payload["tool_choice"], "auto")
                self.assertIn("web_search_call.action.sources", payload["include"])

    def test_local_rejection_precedes_auth_and_upstream_in_both_lanes(self):
        # A still-invalid control (scheme-bearing allowlist entry) proves local
        # rejection; the blocklist variant this test once used is tolerated in v1.4.8.
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                request = {"model": "gpt-fixture", "max_tokens": 100, "stream": stream,
                           "messages": [{"role": "user", "content": "PRIVATE_QUERY_SENTINEL"}],
                           "tools": [{**SEARCH, "allowed_domains": ["https://PRIVATE-DOMAIN-SENTINEL.org"]}]}
                report = controlled_asgi_probe(raw_request_body=json.dumps(request).encode(),
                                              backend_mode=mode, stream=stream)
                self.assertIsNone(report.raised)
                self.assertEqual(report.auth_calls, 0)
                self.assertEqual(report.upstream_calls, 0)
                self.assertEqual(report.messages[0]["status"], 400)
                self.assertNotIn("PRIVATE_QUERY_SENTINEL", report.logs)
                self.assertNotIn("PRIVATE-DOMAIN-SENTINEL", report.logs)

    def test_v148_blocked_domains_request_reaches_upstream_without_leaking(self):
        # v1.4.8: the request shape that used to be rejected locally now completes.
        # openai lane: forwarded as filters.blocked_domains. chatgpt lane: dropped
        # with a WARNING and absent upstream. Neither lane logs the domain.
        domain = "private-domain-sentinel.org"
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    request = fx.search_request(stream, [{**SEARCH, "blocked_domains": [domain]}])
                    report = controlled_asgi_probe(scenario=fx.search_scenario(), raw_request_body=json.dumps(request).encode(),
                                                  backend_mode=mode, stream=stream)
                    self.assertIsNone(report.raised)
                    self.assertEqual(report.messages[0]["status"], 200)
                    self.assertEqual(report.upstream_calls, 1)
                    self.assertIn(b"server_tool_use", fx.probe_body(report))
                    self.assertNotIn(domain, report.logs)
                    if mode == "openai":
                        self.assertEqual(report.outbound_payloads[0]["tools"],
                                         [{**HOSTED, "filters": {"blocked_domains": [domain]}}])
                    else:
                        self.assertEqual(report.outbound_payloads[0]["tools"], [HOSTED])
                        self.assertNotIn(domain, json.dumps(report.outbound_payloads))
                        self.assertIn("WARNING", report.logs)

    def test_real_process_ordinary_function_regression_both_lanes(self):
        for mode in ("openai", "chatgpt"):
            with MockResponsesServer(full_response_scenario()) as backend:
                with RealShim(backend, mode) as shim:
                    shim.assert_offline_contract()
                    for stream in (False, True):
                        result = shim.post_messages(stream=stream, tools=[FUNCTION])
                        self.assertEqual(result.status, 200)
                    self.assertEqual(len(backend.responses_requests), 2)
                    for request in backend.responses_requests:
                        self.assertEqual(request.body["tools"][0]["type"], "function")


class SearchBridgeTests(fx.NativeSearchCase):
    def test_wire_pairs_attribution_usage_and_exact_replay_both_lanes(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    with MockResponsesServer(fx.search_scenario()) as backend:
                        with RealShim(backend, mode) as shim:
                            shim.assert_offline_contract()
                            result = shim.post_raw_messages(json.dumps(fx.search_request(stream)).encode())
                            self.assertEqual(result.status, 200, result.text)
                            if stream:
                                lifecycle_report(parse_typed_sse(result.body))
                            blocks = fx.collected_blocks(result, stream)
                            self.assertEqual([b["type"] for b in blocks], ["server_tool_use", "web_search_tool_result", "text", "text"])
                            self.assertEqual(len(blocks[1]["content"]), 31)
                            self.assertEqual(blocks[0]["id"], blocks[1]["tool_use_id"])
                            self.assertEqual(blocks[2]["text"], RAW_ITEMS[1]["content"][0]["text"])
                            self.assertIn("[Example Domains](" + fx.CITED + ")", blocks[3]["text"])
                            self.assertEqual(blocks[1]["content"][0]["title"], "URL: " + fx.HELP)
                            self.assertNotIn("encrypted_index", result.text)
                            self.assertNotIn("cited_text", result.text)
                            usage = (next(f.data["usage"] for f in parse_typed_sse(result.body) if f.event == "message_delta") if stream else result.json()["usage"])
                            self.assertEqual(usage["input_tokens"] + usage["cache_read_input_tokens"], 31)
                            self.assertEqual(usage["output_tokens"], 17)
                            follow = fx.search_request(False)
                            follow["tools"] = []
                            follow["tool_choice"] = {"type": "none"}
                            follow["messages"] += [{"role": "assistant", "content": blocks}, {"role": "user", "content": "continue"},
                                                   {"role": "assistant", "content": blocks}, {"role": "user", "content": "continue again"}]
                            backend.scenario = fx.search_scenario(items=[RAW_ITEMS[1]])
                            replay = shim.post_raw_messages(json.dumps(follow).encode())
                            self.assertEqual(replay.json()["content"][0]["text"], RAW_ITEMS[1]["content"][0]["text"])
                            self.assertEqual(backend.responses_requests[-1].body["tools"], [])
                            self.assertEqual(replay.status, 200)
                            actual = backend.responses_requests[-1].body["input"]
                            self.assertEqual(actual[1:3], RAW_ITEMS)
                            self.assertEqual(actual[4:6], RAW_ITEMS)
                            self.assertEqual(backend.responses_requests[-1].body["tool_choice"], "none")
                            self.assertNotIn(fx.CITED, shim.captured_stderr())
                            self.assertNotIn("synthetic public IANA question", shim.captured_stderr())

    def test_collector_duplicates_conflicts_and_missing_inventory(self):
        registry = self.shim._ToolRegistry([SEARCH], {"type": "any"})
        events = fx.search_scenario().stream_events
        collector = self.shim._SearchCollector(registry)
        collector.event(events[0]); collector.event(events[0]); collector.event(events[1])
        self.assertEqual(collector.event(events[-1])["output"], RAW_ITEMS)
        for mutation in ("conflict", "gap", "same_id", "missing", "terminal_conflict", "failed", "incomplete"):
            with self.subTest(mutation=mutation):
                events = copy.deepcopy(fx.search_scenario().stream_events)
                if mutation == "conflict":
                    changed = copy.deepcopy(events[0]); changed["item"]["action"]["query"] = "different"
                    events.insert(1, changed)
                elif mutation == "gap": events[1]["output_index"] = 2
                elif mutation == "same_id": events[1]["item"]["id"] = events[0]["item"]["id"]
                elif mutation == "missing": events[1]["type"] = "response.output_item.added"
                elif mutation == "terminal_conflict": events[-1]["response"]["output"] = [RAW_ITEMS[0]]
                elif mutation == "failed": events[-1]["response"]["error"] = {"message": "PRIVATE"}
                elif mutation == "incomplete": events[-1]["type"] = "response.incomplete"; events[-1]["response"]["status"] = "incomplete"
                collector = self.shim._SearchCollector(registry)
                with self.assertRaises(self.shim._ProtocolError):
                    for event in events: collector.event(event)

    def test_limits_source_contract_and_forced_no_search(self):
        registry = self.shim._ToolRegistry([{**SEARCH, "max_uses": 1}], {"type": "any"})
        collector = self.shim._SearchCollector(registry)
        collector.event(fx.search_scenario().stream_events[0])
        second = copy.deepcopy(fx.search_scenario().stream_events[0])
        second["output_index"] = 1; second["item"]["id"] = "ws_second"
        with self.assertRaisesRegex(self.shim._ProtocolError, "ceiling exceeded"):
            collector.event(second)
        with mock.patch.object(self.shim, "_SEARCH_MAX_BYTES", 20):
            with self.assertRaisesRegex(self.shim._ProtocolError, "byte limit"):
                self.shim._SearchCollector(registry).event(fx.search_scenario().stream_events[0])
        # Status and forced-search evidence remain fatal.
        for mutation in ("failed", "no_search", "text_only"):
            items = copy.deepcopy(RAW_ITEMS)
            if mutation == "failed": items[0]["status"] = "failed"
            else: items = items[1:]
            with self.subTest(mutation=mutation), self.assertRaises(self.shim._ProtocolError):
                self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", registry)
        # v1.4.8 (formerly fatal): unrecognized shapes degrade instead of failing.
        answer = RAW_ITEMS[1]["content"][0]["text"]
        missing = copy.deepcopy(RAW_ITEMS)
        del missing[0]["action"]["sources"]
        blocks = self.shim._search_projection({"status": "completed", "output": missing}, "gpt-fixture", registry)["content"]
        self.assertEqual([b["type"] for b in blocks], ["text", "text"])  # search item skipped
        self.assertEqual(blocks[0]["text"], answer)
        page = copy.deepcopy(RAW_ITEMS)
        page[0]["action"]["type"] = "open_page"  # search-only fields are ignored
        blocks = self.shim._search_projection({"status": "completed", "output": page}, "gpt-fixture", registry)["content"]
        self.assertEqual(blocks[0], {**blocks[0], "type": "server_tool_use", "input": {"type": "open_page"}})
        self.assertIn("URL not supplied by provider", blocks[1]["text"])
        bad_url = copy.deepcopy(RAW_ITEMS)
        bad_url[0]["action"]["sources"][0]["url"] = "javascript:alert(1)"
        blocks = self.shim._search_projection({"status": "completed", "output": bad_url}, "gpt-fixture", registry)["content"]
        self.assertEqual(len(blocks[1]["content"]), 30)  # one source skipped, rest kept
        self.assertNotIn("javascript:", json.dumps(blocks))
        empty = copy.deepcopy(RAW_ITEMS)
        empty[0]["action"]["sources"] = []
        empty[1]["content"][0]["annotations"] = []
        result = self.shim._search_projection({"status": "completed", "output": empty}, "gpt-fixture", registry)
        self.assertEqual(result["content"][1]["content"], [])

    def test_replay_tamper_expiry_eviction_unknown_fields_and_mixed_tools(self):
        registry = self.shim._ToolRegistry([SEARCH, FUNCTION])
        items = copy.deepcopy(RAW_ITEMS)
        items.insert(0, {"type": "reasoning", "id": "rs_synthetic", "summary": [{"type": "summary_text", "text": "Synthetic reasoning"}], "encrypted_content": "SYNTHETIC_OPAQUE"})
        items.append({"type": "function_call", "id": "fc_synthetic", "call_id": "call_synthetic", "name": "WebSearch", "arguments": "{}"})
        items[1]["unknown_field"] = {"preserved": [1, 2]}
        blocks = self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", registry)["content"]
        messages = [{"role": "assistant", "content": blocks}, {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_synthetic", "content": "ordinary result"}]}]
        actual = self.shim._messages_to_input(messages)[0]
        self.assertEqual(actual[:-1], items)
        self.assertEqual(actual[-1]["type"], "function_call_output")
        for mutation in ("text", "missing", "ref"):
            bad = copy.deepcopy(messages)
            if mutation == "text": bad[0]["content"][-1]["text"] += "changed"
            elif mutation == "missing": bad[0]["content"].pop(0)
            else: bad[0]["content"][1]["id"] += "invalid"
            with self.subTest(mutation=mutation), self.assertRaises(self.shim._InvalidRequestError):
                self.shim._messages_to_input(bad)
        with mock.patch.object(self.shim, "_SEARCH_REPLAY_TTL", -1):
            with self.assertRaisesRegex(self.shim._InvalidRequestError, "missing or expired"):
                self.shim._messages_to_input(messages)
        with mock.patch.object(self.shim, "_SEARCH_REPLAY_MAX_GROUPS", 1):
            old = self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", registry)["content"]
            self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", registry)
            with self.assertRaises(self.shim._InvalidRequestError):
                self.shim._messages_to_input([{"role": "assistant", "content": old}])

    def test_missing_and_multiple_queries_never_invent_single_query(self):
        registry = self.shim._ToolRegistry([SEARCH])
        for queries in (None, ["first", "second"]):
            items = copy.deepcopy(RAW_ITEMS)
            items[0]["action"].pop("query")
            items[0]["action"].pop("queries")
            if queries is not None:
                items[0]["action"]["queries"] = queries
                items[0]["action"]["query"] = "first"
            result = self.shim._search_projection({"status": "completed", "output": items}, "gpt-fixture", registry)
            actual = result["content"][0]["input"]
            self.assertNotIn("query", actual)
            self.assertEqual(actual, {} if queries is None else {"queries": queries})

    def test_cache_concurrency_and_byte_bounds(self):
        from concurrent.futures import ThreadPoolExecutor
        registry = self.shim._ToolRegistry([SEARCH])

        def exchange(_):
            result = self.shim._search_projection({"status": "completed", "output": copy.deepcopy(RAW_ITEMS)}, "gpt-fixture", registry)
            replay = self.shim._messages_to_input([{"role": "assistant", "content": result["content"]}])[0]
            self.assertEqual(replay, RAW_ITEMS)
            return result["content"][0]["id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            references = list(pool.map(exchange, range(16)))
        self.assertEqual(len(set(references)), 16)
        self.assertLessEqual(self.shim._SEARCH_REPLAY.bytes, self.shim._SEARCH_REPLAY_MAX_BYTES)
        with mock.patch.object(self.shim, "_SEARCH_REPLAY_MAX_BYTES", 10):
            with self.assertRaisesRegex(self.shim._ProtocolError, "capacity exceeded"):
                exchange(0)

    def test_search_heartbeat_and_cancellation_cleanup(self):
        for mode in ("openai", "chatgpt"):
            scenario = fx.search_scenario()
            scenario.heartbeat_gap_s = 0.2
            with MockResponsesServer(scenario) as backend:
                with RealShim(backend, mode, env_overrides={"SHIM_PING_INTERVAL_S": "0.04"}) as shim:
                    result = shim.post_raw_messages(json.dumps(fx.search_request(True)).encode())
                    frames = parse_typed_sse(result.body)
                    lifecycle_report(frames)
                    self.assertTrue(any(f.event == "ping" for f in frames))
            for action in ("disconnect_response_start", "cancel_terminal", "disconnect_body_close"):
                report = controlled_asgi_probe(scenario=fx.search_scenario(), stream=True,
                                              raw_request_body=json.dumps(fx.search_request(True)).encode(),
                                              backend_mode=mode, send_action=action)
                self.assertEqual(report.pending_task_count, 0)
                self.assertEqual(report.stream_close_calls, 1)
                self.assertEqual(sum(line.event == "cleanup" for line in report.lifecycle), 1)

    def test_observed_limit_failure_closes_upstream_without_retry(self):
        second = copy.deepcopy(RAW_ITEMS[0]); second["id"] = "ws_second"
        scenario = fx.search_scenario(items=[RAW_ITEMS[0], second, RAW_ITEMS[1]])
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                request = fx.search_request(stream)
                request["tools"][0]["max_uses"] = 1
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_raw_messages(json.dumps(request).encode())
                        self.assertIn("shim-observed search-call ceiling exceeded", result.text)
                        self.assertNotIn("message_stop", result.text)
                        self.assertEqual(len(backend.responses_requests), 1)
                        self.assertNotIn("server_tool_use", result.text)
                        if mode == "chatgpt":
                            self.assertNotIn("max_tool_calls", backend.responses_requests[0].body)

    def test_error_classification_and_no_reflected_prose(self):
        scenario = fx.search_scenario()
        scenario.stream_status = 400
        scenario.stream_error_body = json.dumps({"error": {"code": "insufficient_quota", "message": "PRIVATE_ERROR_SENTINEL"}}).encode()
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_raw_messages(json.dumps(fx.search_request(stream)).encode())
                        self.assertIn("invalid_request_error", result.text)
                        self.assertNotIn("PRIVATE_ERROR_SENTINEL", result.text + shim.captured_stderr())
                        self.assertEqual(len(backend.responses_requests), 1)

    def test_transport_rejects_html_and_incomplete_stream(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                if mode == "openai" and not stream:
                    continue  # This cell is JSON, not the SSE/MIME fallback path.
                for variant in ("html", "missing_terminal", "malformed"):
                    scenario = fx.search_scenario()
                    if variant == "html": scenario.raw_stream_frames = [b"<html>challenge</html>"]
                    elif variant == "missing_terminal": scenario.stream_events.pop()
                    else: scenario.raw_stream_frames = [b'event: response.created\ndata: {invalid}\n\n']
                    with self.subTest(mode=mode, stream=stream, variant=variant):
                        with MockResponsesServer(scenario) as backend:
                            with RealShim(backend, mode) as shim:
                                result = shim.post_raw_messages(json.dumps(fx.search_request(stream)).encode())
                                if stream:
                                    frames = parse_typed_sse(result.body)
                                    self.assertEqual(sum(f.event == "error" for f in frames), 1)
                                    self.assertFalse(any(f.event == "message_stop" for f in frames))
                                else:
                                    self.assertEqual(result.status, 502)
                                self.assertEqual(len(backend.responses_requests), 1)


if __name__ == "__main__":
    unittest.main()
