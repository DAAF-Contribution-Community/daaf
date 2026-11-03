"""Focused buffered-response regressions; synthetic ASGI and production source only.

Compact terminals need complete bounded evidence; populated terminals keep legacy
semantics. This is not the ordinary streaming reducer's refusal policy.
"""
import copy
import json
import unittest
from unittest.mock import AsyncMock, Mock

from ._loopback_harness import (
    USAGE_WITH_CACHE, controlled_asgi_probe, events_scenario,
    full_response_scenario, heartbeat_text_scenario, parse_typed_sse,
    lifecycle_report, text_delta_values,
)


TEXT = {"type": "message", "id": "msg_recovery", "role": "assistant",
        "status": "completed", "content": [{"type": "output_text", "text": "<allow>SYNTHETIC_ALLOW</allow>"}]}
REASONING = {"type": "reasoning", "id": "rs_recovery", "status": "completed",
             "summary": [{"type": "summary_text", "text": "Synthetic reasoning."}],
             "encrypted_content": "SYNTHETIC_ENCRYPTED"}
TOOL = {"type": "function_call", "id": "fc_recovery", "call_id": "call_recovery",
        "name": "Read", "status": "completed", "arguments": '{"file_path":"fixture.txt"}'}


def recovery_scenario(items=None, shape="empty", leading=None, incomplete=False):
    items = copy.deepcopy([TEXT] if items is None else items)
    terminal = {"id": "resp_recovery", "status": "incomplete" if incomplete else "completed",
                "usage": copy.deepcopy(USAGE_WITH_CACHE)}
    if shape != "absent":
        terminal["output"] = items if shape == "full" else None if shape == "null" else []
    if incomplete:
        terminal["incomplete_details"] = {"reason": "max_output_tokens"}
    events = copy.deepcopy(leading) if leading is not None else [
        {"type": "response.output_item.done", "output_index": i, "item": item}
        for i, item in enumerate(items)]
    events.append({"type": "response.incomplete" if incomplete else "response.completed", "response": terminal})
    return events_scenario("nonstream-recovery", events, nonstream_response=terminal)


class NonstreamRecoveryTests(unittest.TestCase):
    def probe(self, scenario, *, mode="chatgpt", stream=False, limits=None,
              recursion_fault=False, history=False):
        observed = {}
        request = {"model": "gpt-fixture", "max_tokens": 256, "stream": stream,
                   "messages": [{"role": "user", "content": "Synthetic input."}]}

        def configure(module):
            observed["module"] = module
            module._REASONING_CACHE.clear()
            module._REASONING_CACHE["sentinel"] = {"id": "rs_sentinel"}
            module._REASONING_CACHE_RESTORED_IDS = {"sentinel"}
            # INTENT: observe real cache mutations while suppressing persistence.
            # REASONING: an HTTP error alone cannot prove fail-before-cache ordering.
            # ASSUMES: wrappers delegate production logic; only disk writer is mocked.
            module._populate_reasoning_cache = Mock(wraps=module._populate_reasoning_cache)
            module._cache_reasoning = Mock(wraps=module._cache_reasoning)
            module._write_reasoning_cache_state = Mock()
            if recursion_fault:
                module._parse_recovery_number = Mock(side_effect=RecursionError("synthetic decoder fault"))
            if history:
                token = "1" * 32
                ref = "srvtoolu_shim_" + token + "_0"
                blocks = [{"type": "server_tool_use", "id": ref, "name": "web_search", "input": {"query": "synthetic"}},
                          {"type": "web_search_tool_result", "tool_use_id": ref, "content": []}]
                raw = [{"type": "web_search_call", "id": "ws_history", "status": "completed",
                        "action": {"type": "search", "query": "synthetic"}}]
                module._SEARCH_REPLAY.put(token, raw, blocks)
            observed["cache"] = copy.deepcopy(module._REASONING_CACHE)
            observed["replay"] = copy.deepcopy(module._SEARCH_REPLAY.groups)
            observed["ratio"] = copy.deepcopy(module._count_ratio_state)
            for key, value in (limits or {}).items():
                setattr(module, key, value(module) if callable(value) else value)

        # History must be encoded after the module callback seeds its replay entry.
        # Build matching blocks up front; configure only seeds the production cache.
        if history:
            ref = "srvtoolu_shim_" + "1" * 32 + "_0"
            request["messages"].extend([
                {"role": "assistant", "content": [
                    {"type": "server_tool_use", "id": ref, "name": "web_search", "input": {"query": "synthetic"}},
                    {"type": "web_search_tool_result", "tool_use_id": ref, "content": []}]},
                {"role": "user", "content": "Continue."}])
        report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                                      raw_request_body=json.dumps(request).encode(), configure_module=configure)
        self.assertIsNone(report.raised)
        self.assertFalse(report.cancelled)
        self.assertEqual(report.pending_task_count, 0)
        self.assertEqual(report.upstream_calls, 1)
        self.assertEqual(report.stream_close_calls, int(stream or mode == "chatgpt"))
        self.assertEqual(report.outbound_payloads[0]["stream"], stream or mode == "chatgpt")
        return report, observed

    def assert_success(self, report, text=TEXT["content"][0]["text"], stop="end_turn"):
        self.assertEqual(report.messages[0]["status"], 200)
        body = json.loads(b"".join(m.get("body", b"") for m in report.messages))
        self.assertEqual(body["content"], [{"type": "text", "text": text}])
        self.assertEqual(body["stop_reason"], stop)
        self.assertEqual(body["usage"], {"input_tokens": 19, "output_tokens": 17,
                                      "cache_read_input_tokens": 12, "cache_creation_input_tokens": 0})
        return body

    def assert_rejected(self, report, observed, *, stream=False):
        self.assertEqual(report.messages[0]["status"], 200 if stream else 502)
        raw = b"".join(m.get("body", b"") for m in report.messages)
        if stream:
            # HTTP was already started: refusal must be the sole error terminal,
            # with no content blocks, message_delta or successful message_stop.
            frames = parse_typed_sse(raw)
            errors = [frame.data for frame in frames if frame.event == "error"]
            self.assertEqual(len(errors), 1)
            self.assertFalse(any(frame.event in ("content_block_start", "content_block_delta",
                                                "message_delta", "message_stop") for frame in frames))
            body = errors[0]
        else:
            body = json.loads(raw)
        self.assertEqual(body["type"], "error")
        self.assertEqual(body["error"]["type"], "api_error")
        self.assertNotIn("content", body)
        self.assertNotIn("stop_reason", body)
        self.assertNotIn(b"SYNTHETIC", raw)
        self.assertNotIn(b"<allow>", raw)
        self.assertNotIn("outcome=success", report.logs)
        module = observed["module"]
        self.assertEqual(module._REASONING_CACHE, observed["cache"])
        self.assertEqual(module._REASONING_CACHE_RESTORED_IDS, {"sentinel"})
        self.assertEqual(module._SEARCH_REPLAY.groups, observed["replay"])
        self.assertEqual(module._count_ratio_state, observed["ratio"])
        for name in ("_populate_reasoning_cache", "_cache_reasoning", "_write_reasoning_cache_state"):
            getattr(module, name).assert_not_called()

    def test_completed_text_recovers_empty_null_and_absent_terminal(self):
        for shape in ("empty", "null", "absent"):
            with self.subTest(shape=shape):
                self.assert_success(self.probe(recovery_scenario(shape=shape))[0])

    def test_recovered_reasoning_text_and_tool_match_full_terminal(self):
        scenario = full_response_scenario()
        full, _ = self.probe(scenario)
        expected = json.loads(full.messages[1]["body"])
        for shape in ("empty", "null", "absent"):
            with self.subTest(shape=shape):
                compact = copy.deepcopy(scenario)
                if shape == "absent":
                    compact.stream_events[-1]["response"].pop("output")
                else:
                    compact.stream_events[-1]["response"]["output"] = [] if shape == "empty" else None
                report, observed = self.probe(compact)
                self.assertEqual(report.messages[0]["status"], 200)
                self.assertEqual(json.loads(report.messages[1]["body"]), expected)
                self.assertIn("call_full_fixture", observed["module"]._REASONING_CACHE)
                observed["module"]._write_reasoning_cache_state.assert_called_once()

    def test_populated_terminal_wins_over_sparse_invalid_inventory(self):
        for leading in ([{"type": "response.output_item.added", "item": {"type": "message"}}],
                        [{"type": "response.output_item.done", "output_index": 7, "item": TEXT}]):
            with self.subTest(leading=leading):
                self.assert_success(self.probe(recovery_scenario(shape="full", leading=leading))[0])

    def test_populated_terminal_wins_over_conflicting_done_text(self):
        prior = copy.deepcopy(TEXT)
        prior["content"][0]["text"] = "SYNTHETIC_INTERIM"
        leading = [{"type": "response.output_item.done", "output_index": 0, "item": prior}]
        self.assert_success(self.probe(recovery_scenario(shape="full", leading=leading))[0])

    def test_refusal_delta_and_done_reject_even_with_full_allow_terminal(self):
        for kind in ("response.refusal.delta", "response.refusal.done"):
            with self.subTest(kind=kind):
                scenario = recovery_scenario([REASONING, TOOL, TEXT], shape="full")
                scenario.stream_events.insert(-1, {"type": kind, "item_id": "msg_refusal", "output_index": 3,
                                                   "content_index": 0, "delta": "", "refusal": None})
                self.assert_rejected(*self.probe(scenario))

    def test_refusal_content_parts_reject_malformed_payloads(self):
        for kind in ("response.content_part.added", "response.content_part.done"):
            with self.subTest(kind=kind):
                scenario = recovery_scenario([REASONING, TOOL, TEXT], shape="full")
                scenario.stream_events.insert(-1, {"type": kind, "item_id": "msg_refusal", "output_index": 3,
                                                   "content_index": 0, "part": {"type": "refusal", "refusal": {}}})
                self.assert_rejected(*self.probe(scenario))

    def test_refusal_in_done_item_rejects_before_terminal_omission(self):
        refused = copy.deepcopy(TEXT)
        refused["content"].append({"type": "refusal", "refusal": "SYNTHETIC_REFUSAL"})
        scenario = recovery_scenario([REASONING, TOOL, TEXT], shape="full")
        scenario.stream_events.insert(-1, {"type": "response.output_item.done", "output_index": 3, "item": refused})
        self.assert_rejected(*self.probe(scenario))

    def test_refusal_in_terminal_rejects_before_cache_population(self):
        refused = copy.deepcopy(TEXT)
        refused["content"].append({"type": "refusal"})
        scenario = recovery_scenario([REASONING, TOOL, refused], shape="full", leading=[])
        for mode in ("chatgpt", "openai"):
            with self.subTest(mode=mode):
                self.assert_rejected(*self.probe(scenario, mode=mode))

    def test_history_incomplete_terminal_does_not_hide_refusal(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                scenario = recovery_scenario([REASONING, TOOL, TEXT], shape="full", incomplete=True)
                scenario.stream_events.insert(-1, {"type": "response.refusal.done", "refusal": ""})
                self.assert_rejected(*self.probe(scenario, history=True, stream=stream), stream=stream)

    def test_unfinished_delta_reference_requires_complete_inventory(self):
        for kind in ("response.output_text.delta", "response.function_call_arguments.delta",
                     "response.reasoning_summary_text.delta"):
            with self.subTest(kind=kind):
                scenario = recovery_scenario()
                scenario.stream_events.insert(-1, {"type": kind, "item_id": "unfinished", "output_index": 1,
                                                   "summary_index": 0, "delta": "SYNTHETIC_PARTIAL"})
                self.assert_rejected(*self.probe(scenario))

    def test_reference_type_conflict_is_deferred_until_recovery(self):
        for shape in ("empty", "full"):
            with self.subTest(shape=shape):
                scenario = recovery_scenario(shape=shape)
                scenario.stream_events.insert(-1, {"type": "response.function_call_arguments.delta",
                                                   "item_id": TEXT["id"], "output_index": 0, "delta": "{}"})
                result = self.probe(scenario)
                self.assert_rejected(*result) if shape == "empty" else self.assert_success(result[0])

    def test_incomplete_terminal_cannot_drop_unfinished_item(self):
        scenario = recovery_scenario(incomplete=True)
        scenario.stream_events.insert(-1, {"type": "response.output_item.added", "output_index": 1,
                                           "item": {"type": "message", "id": "unfinished", "status": "in_progress"}})
        self.assert_rejected(*self.probe(scenario))

    def test_incomplete_complete_inventory_preserves_max_tokens(self):
        self.assert_success(self.probe(recovery_scenario(incomplete=True))[0], stop="max_tokens")

    def test_gap_or_conflicting_duplicate_recovery_is_rejected(self):
        for mutation in ("gap", "conflict"):
            with self.subTest(mutation=mutation):
                scenario = recovery_scenario()
                if mutation == "gap":
                    scenario.stream_events[0]["output_index"] = 1
                else:
                    duplicate = copy.deepcopy(scenario.stream_events[0])
                    duplicate["item"]["content"][0]["text"] = "SYNTHETIC_CONFLICT"
                    scenario.stream_events.insert(1, duplicate)
                self.assert_rejected(*self.probe(scenario))

    def test_malformed_or_nonobject_recovered_arguments_are_rejected(self):
        for arguments in ('{"unfinished":', '[]', 'null', '"scalar"'):
            with self.subTest(arguments=arguments):
                tool = {**TOOL, "arguments": arguments}
                self.assert_rejected(*self.probe(recovery_scenario([REASONING, tool])))

    def test_nonfinite_overflow_and_overwritten_numbers_are_rejected(self):
        for arguments in ('{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}',
                          '{"x":1e999}', '{"x":NaN,"x":0}'):
            with self.subTest(arguments=arguments):
                self.assert_rejected(*self.probe(recovery_scenario([REASONING, {**TOOL, "arguments": arguments}])))

    def test_finite_recovered_float_and_exponent_preserve_tool_input(self):
        # No numeric parser injection: rejecting all floats must fail this control.
        scenario = recovery_scenario([REASONING, {**TOOL, "arguments": '{"x":1.5,"y":1e2}'}])
        report, _ = self.probe(scenario)
        self.assertEqual(report.messages[0]["status"], 200)
        body = json.loads(report.messages[1]["body"])
        tools = [block for block in body["content"] if block["type"] == "tool_use"]
        self.assertEqual(tools, [{"type": "tool_use", "name": "Read", "id": "call_recovery",
                                  "input": {"x": 1.5, "y": 100.0}}])
        self.assertEqual(body["stop_reason"], "tool_use")

    def test_recovered_argument_depth_boundary(self):
        for levels, expected in ((63, 200), (64, 502)):
            with self.subTest(levels=levels):
                raw = '{"x":' + '[' * levels + '0' + ']' * levels + '}'
                report, observed = self.probe(recovery_scenario([REASONING, {**TOOL, "arguments": raw}]))
                self.assertEqual(report.messages[0]["status"], expected)
                if expected == 502:
                    self.assert_rejected(report, observed)
                else:
                    nested = 0
                    for _ in range(levels):
                        nested = [nested]
                    body = json.loads(report.messages[1]["body"])
                    tools = [block for block in body["content"] if block["type"] == "tool_use"]
                    self.assertEqual(tools, [{"type": "tool_use", "name": "Read", "id": "call_recovery",
                                              "input": {"x": nested}}])
                    self.assertEqual(body["stop_reason"], "tool_use")

    def test_injected_decoder_recursion_is_structured_not_natural_depth_claim(self):
        for shape in ("empty", "full"):
            with self.subTest(shape=shape):
                report, observed = self.probe(recovery_scenario([REASONING, {**TOOL, "arguments": '{"x":1.5}'}], shape=shape), recursion_fault=True)
                if shape == "empty":
                    self.assert_rejected(report, observed)
                    observed["module"]._parse_recovery_number.assert_called_once()
                else:
                    self.assertEqual(report.messages[0]["status"], 200)
                    observed["module"]._parse_recovery_number.assert_not_called()

    def test_item_inventory_limit_boundary_and_full_terminal_control(self):
        for limit, shape, expected in ((0, "empty", 502), (1, "empty", 200), (0, "full", 200)):
            with self.subTest(limit=limit, shape=shape):
                result = self.probe(recovery_scenario(shape=shape), limits={"_SEARCH_MAX_ITEMS": limit})
                self.assert_rejected(*result) if expected == 502 else self.assert_success(result[0])

    def test_reference_bytes_count_at_exact_boundary(self):
        leading = [{"type": "response.output_text.delta", "item_id": TEXT["id"], "output_index": 0, "delta": "x"},
                   {"type": "response.output_item.done", "output_index": 0, "item": TEXT}]
        for offset in (-1, 0):
            with self.subTest(offset=offset):
                def budget(module):
                    return len(module._search_json(TEXT)) + len(module._search_json(TEXT["id"])) + offset
                result = self.probe(recovery_scenario(leading=leading), limits={"_SEARCH_MAX_BYTES": budget})
                self.assert_rejected(*result) if offset < 0 else self.assert_success(result[0])

    def test_openai_nonstream_uses_json_not_sse_recovery(self):
        scenario = recovery_scenario()
        report, _ = self.probe(scenario, mode="openai")
        self.assertEqual(report.messages[0]["status"], 200)
        self.assertEqual(json.loads(report.messages[1]["body"])["content"], [{"type": "text", "text": ""}])
        self.assertEqual(report.stream_close_calls, 0)

    def test_openai_nonstream_search_reads_json_through_stream_context(self):
        request = {"model": "gpt-fixture", "max_tokens": 256, "stream": False,
                   "messages": [{"role": "user", "content": "Synthetic search control."}],
                   "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]}
        report = controlled_asgi_probe(scenario=heartbeat_text_scenario(gap_s=0),
            backend_mode="openai", stream=False, raw_request_body=json.dumps(request).encode())
        self.assertIsNone(report.raised)
        self.assertEqual(report.messages[0]["status"], 200)
        self.assertEqual(report.upstream_calls, 1)
        self.assertIs(report.outbound_payloads[0]["stream"], False)
        self.assertEqual(report.stream_close_calls, 1)
        self.assertEqual(report.pending_task_count, 0)
        body = json.loads(report.messages[1]["body"])
        self.assertEqual(body["content"], [{"type": "text", "text": "Held-open answer."}])
        self.assertEqual(body["stop_reason"], "end_turn")
        self.assertEqual(body["usage"], {"input_tokens": 31, "output_tokens": 17,
                                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0})

    def test_configure_exception_propagates_and_closes_real_client_once(self):
        observed = {}
        failure = RuntimeError("synthetic configure failure")
        def configure(module):
            client = module._client
            observed["client"] = client
            observed["close"] = AsyncMock(wraps=client.aclose)
            client.aclose = observed["close"]
            raise failure
        with self.assertRaises(RuntimeError) as caught:
            controlled_asgi_probe(configure_module=configure)
        self.assertIs(caught.exception, failure)
        observed["close"].assert_awaited_once()
        self.assertTrue(observed["client"].is_closed)

    def test_full_terminal_and_ordinary_streaming_controls(self):
        self.assert_success(self.probe(recovery_scenario(shape="full"))[0])
        for mode in ("chatgpt", "openai"):
            with self.subTest(mode=mode):
                report, _ = self.probe(heartbeat_text_scenario(gap_s=0), mode=mode, stream=True)
                self.assertEqual(report.messages[0]["status"], 200)
                frames = parse_typed_sse(b"".join(m.get("body", b"") for m in report.messages))
                lifecycle_report(frames)
                self.assertEqual(text_delta_values(frames), ["Held-open answer."])
                self.assertEqual(sum(f.event == "message_stop" for f in frames), 1)
                self.assertFalse(any(f.event == "error" for f in frames))
