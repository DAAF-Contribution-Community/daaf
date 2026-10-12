"""v1.4.8 contracts for the tool-argument whitespace guard retry.

GPT-6 Astra sometimes streams hundreds of whitespace characters into a tool call's
arguments; the v1.4.4 guard stops that stream. Before v1.4.8 the tool_use header was
already on the wire, so Claude Code ran an empty tool call. Now, with
SHIM_SANITIZE_TOOLS on (default), the header waits for complete arguments and a trip
before any tool_use was sent is retried once inside the same downstream message.

1. trip then success: one clean tool_use with real arguments, no error, attempts=2.
2. trip then trip: terminal error, no tool_use block at all.
3. trip after a completed tool was already sent: no retry, error path as before.
4. preamble text before the trip: closed once, the retry continues with fresh
   indices, and text deferred inside the abandoned attempt never reaches the client.
5. SHIM_SANITIZE_TOOLS=0: header at output_item.added and no retry (unchanged).
6. client disconnect while the retry is connecting: no response bytes, disconnect.
7. heartbeat: pings keep flowing while a tool header is held back, and the held
   tool gets its buffered arguments at the terminal (never an empty {}).
8. a held tool on an incomplete response is dropped, not sent empty or partial.
9. reasoning completed in the abandoned attempt never reaches the reasoning cache.
10. a deferred parallel tool that trips while the active one is still held retries.
11. a failed retry reopen (429, 5xx, 401, transport) reports its own error type.
"""

from __future__ import annotations

import json
import unittest

from ._loopback_harness import (
    READ_TOOL,
    MockResponsesServer,
    RealShim,
    _EventBuilder,
    _append_reasoning_item,
    _append_text_item,
    _append_tool_item,
    events_scenario,
    failure_lifecycle_report,
    full_response_scenario,
    group_lifecycle_logs,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
    raw_disconnect_messages,
    text_delta_values,
)

WHITESPACE_RUN = " " * 300   # > 256 consecutive whitespace characters outside strings


def _trip_events(*, preamble_text=None, completed_tool_first=False, deferred_text=False):
    """One attempt that trips the guard inside the arguments of tool fc_trip."""

    builder = _EventBuilder()
    builder.add("response.created", response={"id": "resp_trip", "status": "in_progress"})
    index = 0
    if preamble_text is not None:
        _append_text_item(builder, index, text=preamble_text)
        index += 1
    if completed_tool_first:
        _append_tool_item(builder, index, call_id="call_first", item_id="fc_first")
        index += 1
    builder.add(
        "response.output_item.added",
        output_index=index,
        item={"type": "function_call", "id": "fc_trip", "call_id": "call_trip",
              "name": "Read", "status": "in_progress"},
    )
    builder.add("response.function_call_arguments.delta", item_id="fc_trip",
                output_index=index, delta='{"file_path":')
    if deferred_text:
        # Text while the tool holds the slot is deferred; the retry must drop it.
        builder.add("response.output_text.delta", item_id="msg_abandoned",
                    output_index=index + 1, delta="abandoned text")
    builder.add("response.function_call_arguments.delta", item_id="fc_trip",
                output_index=index, delta=WHITESPACE_RUN)
    return builder.events


def _scenario(name, *attempts):
    scenario = events_scenario(name, attempts[0])
    scenario.attempt_stream_events = [list(events) for events in attempts]
    return scenario


def _input_deltas(frames):
    return [
        frame.data["delta"]["partial_json"]
        for frame in frames
        if isinstance(frame.data, dict)
        and frame.data.get("type") == "content_block_delta"
        and frame.data["delta"].get("type") == "input_json_delta"
    ]


def _tool_starts(frames):
    return [
        frame.data["content_block"]
        for frame in frames
        if isinstance(frame.data, dict)
        and frame.data.get("type") == "content_block_start"
        and frame.data["content_block"].get("type") == "tool_use"
    ]


class ProviderShimWhitespaceRetryTests(unittest.TestCase):
    maxDiff = 12000

    def _terminal(self, lines):
        matches = [line for line in lines if line.event == "terminal"]
        self.assertEqual(len(matches), 1, [line.raw for line in lines])
        return matches[0].fields

    def test_trip_then_success_is_one_clean_tool_call(self) -> None:
        success = full_response_scenario().stream_events
        with MockResponsesServer(_scenario("ws-retry-ok", _trip_events(), success)) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)   # success grammar, no error event
                self.assertEqual([kind for _i, kind in report.starts],
                                 ["thinking", "text", "tool_use"])
                tools = _tool_starts(frames)
                self.assertEqual([tool["id"] for tool in tools], ["call_full_fixture"])
                self.assertNotIn("call_trip", result.text)
                deltas = _input_deltas(frames)
                self.assertEqual(len(deltas), 1)
                self.assertEqual(json.loads(deltas[0]), {"file_path": "/daaf/README.md"})
                lines = lifecycle_for_response(shim, result)
                terminal = self._terminal(lines)
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["attempts"], "2")
                self.assertEqual(terminal["retries"], "1")
                self.assertEqual(terminal["retry_reason"], "tool_argument_whitespace")
                self.assertEqual(terminal["tools_called"], "1")
                self.assertEqual(terminal["backend_code"], "-")
                retries = [line for line in lines if line.event == "upstream_retry"]
                self.assertEqual([line.fields["reason"] for line in retries],
                                 ["tool_argument_whitespace"])
                shim.wait_for_stderr_line("whitespace guard tripped before any tool_use")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2)
                # The retry re-sends the identical translated payload.
                self.assertEqual(backend.responses_requests[0].body,
                                 backend.responses_requests[1].body)

    def test_second_trip_ends_with_error_and_no_tool_block(self) -> None:
        with MockResponsesServer(_scenario("ws-retry-twice", _trip_events())) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = failure_lifecycle_report(frames)
                self.assertEqual(report.starts, [], "no empty tool_use may reach the client")
                self.assertIn("whitespace", report.error["message"])
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "error")
                self.assertEqual(terminal["attempts"], "2")
                self.assertEqual(terminal["retry_reason"], "tool_argument_whitespace")
                self.assertEqual(terminal["backend_code"], "excessive_json_whitespace")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2)

    def test_trip_after_completed_tool_was_sent_does_not_retry(self) -> None:
        trip = _trip_events(completed_tool_first=True)
        success = full_response_scenario().stream_events
        with MockResponsesServer(_scenario("ws-after-tool", trip, success)) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                frames = parse_typed_sse(result.body)
                report = failure_lifecycle_report(frames)
                self.assertEqual([kind for _i, kind in report.starts], ["tool_use"])
                self.assertEqual([tool["id"] for tool in _tool_starts(frames)], ["call_first"])
                self.assertEqual(len(_input_deltas(frames)), 1)
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "error")
                self.assertEqual(terminal["attempts"], "1")
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(terminal["backend_code"], "excessive_json_whitespace")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_preamble_text_is_closed_and_retry_uses_fresh_indices(self) -> None:
        trip = _trip_events(preamble_text="Checking the file.", deferred_text=True)
        success = full_response_scenario().stream_events
        with MockResponsesServer(_scenario("ws-preamble", trip, success)) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                frames = parse_typed_sse(result.body)
                # lifecycle_report rejects overlap, reuse and non-monotonic indices.
                report = lifecycle_report(frames)
                self.assertEqual(report.starts, [(0, "text"), (1, "thinking"),
                                                 (2, "text"), (3, "tool_use")])
                # The abandoned attempt's preamble stays (it was already sent); its
                # deferred, never-sent text is dropped.
                self.assertEqual(text_delta_values(frames),
                                 ["Checking the file.", "Aggregated answer."])
                self.assertNotIn("abandoned text", result.text)
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["attempts"], "2")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2)

    def test_sanitize_off_keeps_header_at_added_and_never_retries(self) -> None:
        success = full_response_scenario().stream_events
        with MockResponsesServer(_scenario("ws-sanitize-off", _trip_events(), success)) as backend:
            with RealShim(backend, "chatgpt",
                          env_overrides={"SHIM_SANITIZE_TOOLS": "0"}) as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                frames = parse_typed_sse(result.body)
                report = failure_lifecycle_report(frames)
                # Pre-1.4.8 shape: header and the first fragment streamed, then error.
                self.assertEqual([kind for _i, kind in report.starts], ["tool_use"])
                self.assertEqual([tool["id"] for tool in _tool_starts(frames)], ["call_trip"])
                self.assertEqual(_input_deltas(frames), ['{"file_path":'])
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["attempts"], "1")
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(terminal["backend_code"], "excessive_json_whitespace")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_client_disconnect_during_retry_connect(self) -> None:
        success = full_response_scenario().stream_events
        with MockResponsesServer(_scenario("ws-disconnect", _trip_events(), success)) as backend:
            entered, release = backend.gate_response_request(2)
            with RealShim(backend, "chatgpt") as shim:
                raw_disconnect_messages(shim, close_after_event=entered, timeout=6.0)
                shim.wait_for_stderr_line("event=cleanup", timeout=5.0)
                release.set()
                groups = list(group_lifecycle_logs(shim.captured_stderr()).values())
                self.assertEqual(len(groups), 1)
                terminal = self._terminal(groups[0])
                self.assertEqual(terminal["outcome"], "disconnect")
                self.assertEqual(terminal["attempts"], "2")
                self.assertEqual(terminal["retry_reason"], "tool_argument_whitespace")
                self.assertEqual(terminal["backend_code"], "-")
                health = shim.get_health()
                self.assertEqual(health.status, 200, health.text)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2)

    def test_pings_continue_while_tool_header_is_held(self) -> None:
        # No .done events: the header is held until the terminal arrives after a
        # silent 0.6 s gap. Pings must bridge the gap before the tool header.
        builder = _EventBuilder()
        builder.add("response.created", response={"id": "resp_held", "status": "in_progress"})
        builder.add("response.output_item.added", output_index=0,
                    item={"type": "function_call", "id": "fc_held", "call_id": "call_held",
                          "name": "Read", "status": "in_progress"})
        builder.add("response.function_call_arguments.delta", item_id="fc_held",
                    output_index=0, delta='{"file_path":"/daaf/README.md"}')
        builder.add("response.completed", response={
            "id": "resp_held", "status": "completed", "output": [],
            "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}})
        scenario = events_scenario("ws-held-header", builder.events)
        scenario.heartbeat_gap_s = 0.6
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt",
                          env_overrides={"SHIM_PING_INTERVAL_S": "0.1"}) as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual([kind for _i, kind in report.starts], ["tool_use"])
                types = [frame.data.get("type") for frame in frames
                         if isinstance(frame.data, dict)]
                header_at = types.index("content_block_start")
                self.assertGreaterEqual(types[:header_at].count("ping"), 2, types)
                # No .done events and an empty terminal output: the completed
                # response's buffered deltas are the arguments (never an empty {}).
                deltas = _input_deltas(frames)
                self.assertEqual(len(deltas), 1)
                self.assertEqual(json.loads(deltas[0]), {"file_path": "/daaf/README.md"})
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_held_tool_on_incomplete_response_is_dropped_not_sent_empty(self) -> None:
        # The response is cut off mid-arguments (incomplete, no .done events): the
        # held tool must not reach the client at all, as {} or as a partial call.
        builder = _EventBuilder()
        builder.add("response.created", response={"id": "resp_cut", "status": "in_progress"})
        builder.add("response.output_item.added", output_index=0,
                    item={"type": "function_call", "id": "fc_cut", "call_id": "call_cut",
                          "name": "Read", "status": "in_progress"})
        builder.add("response.function_call_arguments.delta", item_id="fc_cut",
                    output_index=0, delta='{"file_path":"/daaf/REA')
        builder.add("response.incomplete", response={
            "id": "resp_cut", "status": "incomplete", "output": [],
            "incomplete_details": {"reason": "max_output_tokens"},
            "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}})
        with MockResponsesServer(events_scenario("ws-incomplete-held", builder.events)) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(report.starts, [(0, "text")])   # empty-response guard
                self.assertEqual(_tool_starts(frames), [])
                self.assertEqual(_input_deltas(frames), [])
                self.assertNotIn("call_cut", result.text)
                stop = [frame.data["delta"]["stop_reason"] for frame in frames
                        if isinstance(frame.data, dict)
                        and frame.data.get("type") == "message_delta"]
                self.assertEqual(stop, ["max_tokens"])
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["tools_called"], "0")
                shim.wait_for_stderr_line("dropped a tool call whose arguments never completed")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_abandoned_attempt_reasoning_is_not_cached(self) -> None:
        # Attempt 1 completes a reasoning item, then trips. Attempt 2 has a tool call
        # but NO reasoning and an empty terminal output, so the cache would bind the
        # tool to attempt 1's reasoning if the abandoned item leaked into it.
        def reasoning_trip():
            builder = _EventBuilder()
            builder.add("response.created", response={"id": "resp_rs", "status": "in_progress"})
            _append_reasoning_item(builder, "rs_abandoned", 0,
                                   [{"summary_index": 0, "deltas": ["Planning the read."]}])
            builder.add("response.output_item.added", output_index=1,
                        item={"type": "function_call", "id": "fc_trip", "call_id": "call_trip",
                              "name": "Read", "status": "in_progress"})
            builder.add("response.function_call_arguments.delta", item_id="fc_trip",
                        output_index=1, delta='{"file_path":' + WHITESPACE_RUN)
            return builder.events

        def tool_only(with_reasoning=False):
            builder = _EventBuilder()
            builder.add("response.created", response={"id": "resp_tool", "status": "in_progress"})
            index = 0
            if with_reasoning:
                _append_reasoning_item(builder, "rs_control", 0,
                                       [{"summary_index": 0, "deltas": ["Control."]}])
                index = 1
            _append_tool_item(builder, index)
            builder.add("response.completed", response={
                "id": "resp_tool", "status": "completed", "output": [],
                "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}})
            return builder.events

        with MockResponsesServer(_scenario("ws-reasoning", reasoning_trip(), tool_only())) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                report = lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual([kind for _i, kind in report.starts], ["thinking", "tool_use"])
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["attempts"], "2")
                health = shim.get_health()
                self.assertEqual(health.json()["reasoning_cache"]["entries"], 0, health.text)
                backend.assert_request_counts(responses=2)
        # Control: the same measurement sees a binding made inside one attempt.
        with MockResponsesServer(events_scenario("ws-reasoning-control",
                                                 tool_only(with_reasoning=True))) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                lifecycle_report(parse_typed_sse(result.body))
                health = shim.get_health()
                self.assertEqual(health.json()["reasoning_cache"]["entries"], 1, health.text)

    def test_deferred_parallel_tool_trip_still_retries(self) -> None:
        # Tool A holds the active slot with unfinished arguments (header held) while
        # deferred tool B trips the guard: no tool_use is on the wire, so retry.
        builder = _EventBuilder()
        builder.add("response.created", response={"id": "resp_par", "status": "in_progress"})
        builder.add("response.output_item.added", output_index=0,
                    item={"type": "function_call", "id": "fc_a", "call_id": "call_a",
                          "name": "Read", "status": "in_progress"})
        builder.add("response.function_call_arguments.delta", item_id="fc_a",
                    output_index=0, delta='{"file_path":')
        builder.add("response.output_item.added", output_index=1,
                    item={"type": "function_call", "id": "fc_b", "call_id": "call_b",
                          "name": "Read", "status": "in_progress"})
        builder.add("response.function_call_arguments.delta", item_id="fc_b",
                    output_index=1, delta=WHITESPACE_RUN)
        success = full_response_scenario().stream_events
        with MockResponsesServer(_scenario("ws-parallel", builder.events, success)) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                self.assertEqual([tool["id"] for tool in _tool_starts(frames)],
                                 ["call_full_fixture"])
                for abandoned in ("call_a", "call_b"):
                    self.assertNotIn(abandoned, result.text)
                terminal = self._terminal(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["attempts"], "2")
                self.assertEqual(terminal["retry_reason"], "tool_argument_whitespace")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2)

    def test_failed_retry_reopen_reports_its_own_cause(self) -> None:
        # The retry's reopen fails: the client sees that failure's error type (not
        # the whitespace api_error) and still never sees a tool_use block.
        cases = [
            # (name, mode, attempt statuses, attempt headers, error type,
            #  message fragment, backend requests)
            ("rate-limit", "chatgpt", [200, 429], [{}, {"Retry-After": "120"}],
             "rate_limit_error", None, 2),
            ("server-error", "chatgpt", [200, 503], [{}, {"Retry-After": "0"}],
             "api_error", None, 5),
            ("auth-refresh", "chatgpt", [200, 401], [{}, {}],
             "authentication_error", "codex login --device-auth", 3),
            ("openai-auth", "openai", [200, 401], [{}, {}],
             "authentication_error", None, 2),
            ("transport", "chatgpt", [200, "transport"], [{}, {}],
             "api_error", "backend transport error", 5),
        ]
        for name, mode, statuses, headers, error_type, fragment, requests in cases:
            with self.subTest(case=name):
                scenario = _scenario("ws-reopen-" + name, _trip_events())
                scenario.attempt_statuses = list(statuses)
                scenario.attempt_headers = [dict(h) for h in headers]
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_messages(stream=True, tools=[READ_TOOL])
                        self.assertEqual(result.status, 200, result.text)
                        frames = parse_typed_sse(result.body)
                        report = failure_lifecycle_report(frames, error_type)
                        self.assertEqual(report.starts, [])
                        self.assertNotIn("whitespace", report.error["message"])
                        if fragment is not None:
                            self.assertIn(fragment, report.error["message"])
                        # The auth case logs a codex_login_status diagnostic that the
                        # strict lifecycle-name contract does not list, so read the one
                        # request's grouped lines directly (as the disconnect test does).
                        shim.wait_for_stderr_line("event=cleanup", timeout=5.0)
                        groups = list(group_lifecycle_logs(shim.captured_stderr()).values())
                        self.assertEqual(len(groups), 1)
                        lines = groups[0]
                        terminal = self._terminal(lines)
                        self.assertEqual(terminal["outcome"], "error")
                        self.assertGreaterEqual(int(terminal["retries"]), 1)
                        backend_errors = [line.fields["anthropic_type"] for line in lines
                                          if line.event == "backend_error"]
                        self.assertEqual(backend_errors, [error_type])
                        self.assertNotEqual(terminal["backend_code"], "excessive_json_whitespace")
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=requests)


if __name__ == "__main__":
    unittest.main()
