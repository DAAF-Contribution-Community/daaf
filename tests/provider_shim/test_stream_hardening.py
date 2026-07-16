"""Deterministic red/green contracts for provider-shim stream hardening."""

from __future__ import annotations

import json
import threading
import time
import unittest

from ._loopback_harness import (
    FAKE_REFRESH_TOKEN,
    NONSTREAM_REJECTION_BODY,
    READ_TOOL,
    TERMINAL_FIELD_OMITTED,
    USAGE,
    MockResponsesServer,
    OccupiedLoopbackPort,
    PortRaceSelector,
    RealShim,
    TypedSSEFrame,
    abrupt_eof_scenario,
    backend_status_scenario,
    delayed_body_disconnect_scenario,
    delayed_header_disconnect_scenario,
    events_scenario,
    failure_lifecycle_report,
    full_response_scenario,
    incomplete_response_scenario,
    lifecycle_report,
    malformed_sse_scenario,
    missing_terminal_response_scenario,
    outer_cancel_after_stream_enter_report,
    parse_typed_sse,
    provider_scratch_residue,
    raw_disconnect_messages,
    raw_sse_scenario,
    reasoning_while_text_open_scenario,
    reasoning_while_tool_open_scenario,
    retry_sleep_disconnect_scenario,
    sequential_two_tools_scenario,
    terminal_contract_scenario,
    terminal_failure_scenario,
)


class ProviderShimStreamHardeningTests(unittest.TestCase):
    maxDiff = 12000

    def _assert_terminal_error(
        self,
        *,
        scenario: object,
        expected_kind: str,
        marker: str,
    ) -> None:
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(
                    stream=True,
                    tools=[READ_TOOL] if expected_kind == "tool_use" else None,
                )
                self.assertEqual(result.status, 200, f"{marker} status/body={result.status} {result.text}")
                frames = parse_typed_sse(result.body)
                try:
                    lifecycle = failure_lifecycle_report(frames)
                except AssertionError as error:
                    self.fail(f"{marker}: {error}")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
                self.assertEqual(
                    [kind for _index, kind in lifecycle.starts],
                    [expected_kind],
                    marker,
                )
                self.assertEqual(lifecycle.open_at_end, set(), marker)
                self.assertEqual(lifecycle.error.get("type"), "api_error", marker)

    def _assert_stream_failure(
        self,
        *,
        scenario: object,
        marker: str,
        expected_kinds: list[str],
        expected_requests: int = 1,
    ) -> list[object]:
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(
                    result.status,
                    200,
                    f"{marker} status/body={result.status} {result.text}",
                )
                frames = parse_typed_sse(result.body)
                lifecycle = failure_lifecycle_report(frames)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=expected_requests, oauth=0)
                self.assertEqual(
                    [kind for _index, kind in lifecycle.starts],
                    expected_kinds,
                    marker,
                )
                self.assertEqual(lifecycle.open_at_end, set(), marker)
                self.assertLessEqual(len(lifecycle.error.get("message", "")), 200)
                return frames

    def _assert_nonstream_api_error(
        self,
        *,
        scenario: object,
        marker: str,
    ) -> None:
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(result.status, 502, f"{marker}: {result.text}")
                body = result.json()
                self.assertEqual(body.get("type"), "error", marker)
                error = body.get("error") or {}
                self.assertEqual(error.get("type"), "api_error", marker)
                self.assertIsInstance(error.get("message"), str, marker)
                self.assertLessEqual(len(error.get("message", "")), 200, marker)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_chatgpt_nonstream_forces_upstream_sse_and_aggregates(self) -> None:
        scenario = full_response_scenario(reject_nonstream=True)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(
                    result.status,
                    200,
                    "CHATGPT_NONSTREAM_SSE_REQUIRED "
                    f"status={result.status} body={result.text!r} "
                    f"observed_backend_rejection={NONSTREAM_REJECTION_BODY!r}",
                )
                message = result.json()
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
                self.assertIs(backend.responses_requests[0].body.get("stream"), True)
                self.assertEqual(
                    [block.get("type") for block in message.get("content", [])],
                    ["thinking", "text", "tool_use"],
                )
                thinking, text, tool = message["content"]
                self.assertEqual(thinking.get("thinking"), "Inspecting stream semantics.")
                self.assertEqual(thinking.get("signature"), "")
                self.assertEqual(text.get("text"), "Aggregated answer.")
                self.assertEqual(tool.get("id"), "call_full_fixture")
                self.assertEqual(tool.get("name"), "Read")
                self.assertEqual(tool.get("input"), {"file_path": "/daaf/README.md"})
                self.assertEqual(message.get("stop_reason"), "tool_use")
                self.assertEqual(
                    message.get("usage"),
                    {
                        "input_tokens": USAGE["input_tokens"],
                        "output_tokens": USAGE["output_tokens"],
                    },
                )

    def test_openai_nonstream_preserves_real_upstream_json_mode(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
                self.assertIs(backend.responses_requests[0].body.get("stream"), False)
                self.assertEqual(result.headers.get("content-type"), "application/json")
                self.assertEqual(
                    [block.get("type") for block in message.get("content", [])],
                    ["thinking", "text", "tool_use"],
                )
                self.assertEqual(message.get("stop_reason"), "tool_use")
                self.assertEqual(message["usage"]["input_tokens"], USAGE["input_tokens"])
                self.assertEqual(message["usage"]["output_tokens"], USAGE["output_tokens"])

    def test_transport_failure_after_thinking_is_terminal_error(self) -> None:
        self._assert_terminal_error(
            scenario=abrupt_eof_scenario("thinking"),
            expected_kind="thinking",
            marker="TRANSPORT_AFTER_THINKING_TERMINAL_ERROR",
        )

    def test_transport_failure_after_text_is_terminal_error(self) -> None:
        self._assert_terminal_error(
            scenario=abrupt_eof_scenario("text"),
            expected_kind="text",
            marker="TRANSPORT_AFTER_TEXT_TERMINAL_ERROR",
        )

    def test_transport_failure_after_tool_is_terminal_error(self) -> None:
        self._assert_terminal_error(
            scenario=abrupt_eof_scenario("tool"),
            expected_kind="tool_use",
            marker="TRANSPORT_AFTER_TOOL_TERMINAL_ERROR",
        )

    def test_inband_response_failed_uses_terminal_error_contract(self) -> None:
        for prefix, expected_kind in (
            ("thinking", "thinking"),
            ("text", "text"),
            ("tool", "tool_use"),
        ):
            with self.subTest(prefix=prefix):
                self._assert_terminal_error(
                    scenario=terminal_failure_scenario(prefix, "response.failed"),
                    expected_kind=expected_kind,
                    marker=f"INBAND_RESPONSE_FAILED_{prefix.upper()}",
                )

    def test_inband_error_uses_terminal_error_contract(self) -> None:
        for prefix, expected_kind in (
            ("thinking", "thinking"),
            ("text", "text"),
            ("tool", "tool_use"),
        ):
            with self.subTest(prefix=prefix):
                self._assert_terminal_error(
                    scenario=terminal_failure_scenario(prefix, "error"),
                    expected_kind=expected_kind,
                    marker=f"INBAND_ERROR_{prefix.upper()}",
                )

    def test_reasoning_while_text_open_fails_cleanly(self) -> None:
        self._assert_terminal_error(
            scenario=reasoning_while_text_open_scenario(),
            expected_kind="text",
            marker="REASONING_WHILE_TEXT_OPEN_TERMINAL_ERROR",
        )

    def test_reasoning_while_tool_open_fails_cleanly(self) -> None:
        self._assert_terminal_error(
            scenario=reasoning_while_tool_open_scenario(),
            expected_kind="tool_use",
            marker="REASONING_WHILE_TOOL_OPEN_TERMINAL_ERROR",
        )

    def test_missing_terminal_response_fails_cleanly(self) -> None:
        self._assert_terminal_error(
            scenario=missing_terminal_response_scenario(),
            expected_kind="text",
            marker="MISSING_TERMINAL_RESPONSE_ERROR",
        )

    def test_malformed_sse_fails_cleanly(self) -> None:
        self._assert_terminal_error(
            scenario=malformed_sse_scenario(),
            expected_kind="text",
            marker="MALFORMED_SSE_TERMINAL_ERROR",
        )

    def test_stream_nonretryable_backend_status_uses_terminal_error(self) -> None:
        frames = self._assert_stream_failure(
            scenario=backend_status_scenario("status-400", 400),
            marker="PRECONTENT_STATUS_400_TERMINAL_ERROR",
            expected_kinds=[],
        )
        self.assertEqual(
            [frame.data.get("type") for frame in frames if isinstance(frame.data, dict)],
            ["message_start", "error"],
        )

    def test_stream_exhausted_retryable_status_uses_terminal_error(self) -> None:
        frames = self._assert_stream_failure(
            scenario=backend_status_scenario(
                "status-503-exhausted",
                503,
                retry_after="0",
            ),
            marker="PRECONTENT_STATUS_503_EXHAUSTED_TERMINAL_ERROR",
            expected_kinds=[],
            expected_requests=4,
        )
        self.assertEqual(
            [frame.data.get("type") for frame in frames if isinstance(frame.data, dict)],
            ["message_start", "error"],
        )

    def test_terminal_incomplete_stream_and_nonstream_maps_max_tokens(self) -> None:
        scenario = incomplete_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                events = [frame.data for frame in frames if isinstance(frame.data, dict)]
                terminal = next(event for event in events if event.get("type") == "message_delta")
                self.assertEqual(terminal["delta"]["stop_reason"], "max_tokens")
                self.assertEqual(terminal["usage"]["input_tokens"], USAGE["input_tokens"])
                self.assertEqual(terminal["usage"]["output_tokens"], USAGE["output_tokens"])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                self.assertEqual(message.get("stop_reason"), "max_tokens")
                self.assertEqual(
                    message.get("usage"),
                    {
                        "input_tokens": USAGE["input_tokens"],
                        "output_tokens": USAGE["output_tokens"],
                    },
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_completed_event_rejects_failed_missing_and_incomplete_status_both_modes(self) -> None:
        cases = (
            ("failed", "failed"),
            ("missing", TERMINAL_FIELD_OMITTED),
            ("incomplete", "incomplete"),
        )
        for label, status in cases:
            with self.subTest(status=label, mode="stream"):
                scenario = terminal_contract_scenario(
                    f"completed-status-{label}",
                    "response.completed",
                    status=status,
                    output=[],
                    usage=dict(USAGE),
                )
                self._assert_stream_failure(
                    scenario=scenario,
                    marker=f"COMPLETED_STATUS_{label.upper()}_STREAM",
                    expected_kinds=[],
                )
            with self.subTest(status=label, mode="nonstream"):
                self._assert_nonstream_api_error(
                    scenario=scenario,
                    marker=f"COMPLETED_STATUS_{label.upper()}_NONSTREAM",
                )

    def test_incomplete_event_rejects_missing_and_completed_status_both_modes(self) -> None:
        cases = (
            ("missing", TERMINAL_FIELD_OMITTED),
            ("completed", "completed"),
        )
        for label, status in cases:
            with self.subTest(status=label, mode="stream"):
                scenario = terminal_contract_scenario(
                    f"incomplete-status-{label}",
                    "response.incomplete",
                    status=status,
                    output=[],
                    usage=dict(USAGE),
                )
                self._assert_stream_failure(
                    scenario=scenario,
                    marker=f"INCOMPLETE_STATUS_{label.upper()}_STREAM",
                    expected_kinds=[],
                )
            with self.subTest(status=label, mode="nonstream"):
                self._assert_nonstream_api_error(
                    scenario=scenario,
                    marker=f"INCOMPLETE_STATUS_{label.upper()}_NONSTREAM",
                )

    def test_terminal_malformed_output_type_fails_both_modes(self) -> None:
        scenario = terminal_contract_scenario(
            "malformed-terminal-output-object",
            "response.completed",
            status="completed",
            output={},
            usage=dict(USAGE),
        )
        with self.subTest(mode="stream"):
            self._assert_stream_failure(
                scenario=scenario,
                marker="MALFORMED_TERMINAL_OUTPUT-OBJECT_STREAM",
                expected_kinds=[],
            )
        with self.subTest(mode="nonstream"):
            self._assert_nonstream_api_error(
                scenario=scenario,
                marker="MALFORMED_TERMINAL_OUTPUT-OBJECT_NONSTREAM",
            )

    def test_terminal_malformed_usage_degrades_to_dropped_fields_both_modes(self) -> None:
        # v1.2.8 wire tolerance: an invalid usage counter must never discard a
        # completed generation. The invalid field (or a non-object usage) is
        # dropped with a wire-divergence WARNING; downstream defaults/estimation
        # apply and the response succeeds in both modes. Expected values follow
        # the established defaults: nonstream missing fields render as 0; the
        # streaming path estimates a missing output count from accumulated text
        # (empty here -> floor of 1) and defaults a missing input count to 0.
        cases = (
            (
                "usage-list",
                [],
                {"input_tokens": 0, "output_tokens": 0},
                {"input_tokens": 0, "output_tokens": 1},
            ),
            (
                "usage-bool",
                {"input_tokens": True, "output_tokens": USAGE["output_tokens"]},
                {"input_tokens": 0, "output_tokens": USAGE["output_tokens"]},
                {"input_tokens": 0, "output_tokens": USAGE["output_tokens"]},
            ),
            (
                "usage-negative",
                {"input_tokens": USAGE["input_tokens"], "output_tokens": -1},
                {"input_tokens": USAGE["input_tokens"], "output_tokens": 0},
                {"input_tokens": USAGE["input_tokens"], "output_tokens": 1},
            ),
        )
        for label, usage, expected_nonstream, expected_stream in cases:
            scenario = terminal_contract_scenario(
                f"malformed-terminal-{label}",
                "response.completed",
                status="completed",
                output=[],
                usage=usage,
            )
            with self.subTest(case=label, mode="stream"):
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_messages(stream=True)
                        self.assertEqual(result.status, 200, result.text)
                        frames = parse_typed_sse(result.body)
                        lifecycle_report(frames)
                        events = [
                            frame.data for frame in frames
                            if isinstance(frame.data, dict)
                        ]
                        terminal = next(
                            event for event in events
                            if event.get("type") == "message_delta"
                        )
                        self.assertEqual(
                            terminal["delta"]["stop_reason"], "end_turn"
                        )
                        self.assertEqual(terminal["usage"], expected_stream)
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=1, oauth=0)
            with self.subTest(case=label, mode="nonstream"):
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        message = result.json()
                        self.assertEqual(message.get("stop_reason"), "end_turn")
                        self.assertEqual(message.get("usage"), expected_nonstream)
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=1, oauth=0)

    def test_response_failed_never_converts_as_nonstream_success(self) -> None:
        self._assert_nonstream_api_error(
            scenario=terminal_failure_scenario("text", "response.failed"),
            marker="RESPONSE_FAILED_NONSTREAM_API_ERROR",
        )

    def test_malformed_text_delta_object_fails_both_modes(self) -> None:
        scenario = terminal_contract_scenario(
            "malformed-text-delta",
            "response.completed",
            status="completed",
            output=[],
            usage=dict(USAGE),
            leading_events=[
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_malformed_text",
                    "delta": {"not": "a string"},
                }
            ],
        )
        self._assert_stream_failure(
            scenario=scenario,
            marker="MALFORMED_TEXT_DELTA_STREAM",
            expected_kinds=[],
        )
        self._assert_nonstream_api_error(
            scenario=scenario,
            marker="MALFORMED_TEXT_DELTA_NONSTREAM",
        )

    def test_malformed_tool_added_fields_fail_both_modes(self) -> None:
        scenario = terminal_contract_scenario(
            "malformed-tool-added",
            "response.completed",
            status="completed",
            output=[],
            usage=dict(USAGE),
            leading_events=[
                {
                    "type": "response.output_item.added",
                    "item": {
                        "type": "function_call",
                        "id": "fc_malformed_added",
                        "call_id": {"not": "a string"},
                        "name": "Read",
                    },
                }
            ],
        )
        self._assert_stream_failure(
            scenario=scenario,
            marker="MALFORMED_TOOL_ADDED_STREAM",
            expected_kinds=[],
        )
        self._assert_nonstream_api_error(
            scenario=scenario,
            marker="MALFORMED_TOOL_ADDED_NONSTREAM",
        )

    def test_malformed_tool_argument_delta_fails_both_modes(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        target = next(
            event
            for event in events
            if event.get("type") == "response.function_call_arguments.delta"
        )
        target["delta"] = {"not": "a string"}
        scenario = events_scenario("malformed-tool-argument-delta", events)
        self._assert_stream_failure(
            scenario=scenario,
            marker="MALFORMED_TOOL_ARGUMENT_DELTA_STREAM",
            expected_kinds=["thinking", "text", "tool_use"],
        )
        self._assert_nonstream_api_error(
            scenario=scenario,
            marker="MALFORMED_TOOL_ARGUMENT_DELTA_NONSTREAM",
        )

    def test_malformed_tool_output_item_done_fails_both_modes(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        target = next(
            event
            for event in events
            if event.get("type") == "response.output_item.done"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        target["item"]["arguments"] = {"not": "a string"}
        scenario = events_scenario("malformed-tool-output-done", events)
        self._assert_stream_failure(
            scenario=scenario,
            marker="MALFORMED_TOOL_OUTPUT_DONE_STREAM",
            expected_kinds=["thinking", "text", "tool_use"],
        )
        self._assert_nonstream_api_error(
            scenario=scenario,
            marker="MALFORMED_TOOL_OUTPUT_DONE_NONSTREAM",
        )

    def test_sse_complete_data_line_without_blank_boundary_fails(self) -> None:
        terminal = {
            "type": "response.completed",
            "response": {
                "id": "resp_unterminated_complete_line",
                "status": "completed",
                "output": [],
                "usage": dict(USAGE),
            },
        }
        scenario = raw_sse_scenario(
            "unterminated-complete-data-line",
            [f"data: {json.dumps(terminal, separators=(',', ':'))}\n".encode()],
        )
        self._assert_stream_failure(
            scenario=scenario,
            marker="SSE_COMPLETE_LINE_WITHOUT_BLANK_BOUNDARY",
            expected_kinds=[],
        )

    def test_sse_partial_line_at_eof_fails(self) -> None:
        scenario = raw_sse_scenario(
            "partial-line-at-eof",
            [b'data: {"type":"response.completed"'],
        )
        self._assert_stream_failure(
            scenario=scenario,
            marker="SSE_PARTIAL_LINE_AT_EOF",
            expected_kinds=[],
        )

    def test_sse_crlf_blank_line_framing_succeeds(self) -> None:
        terminal = {
            "type": "response.completed",
            "response": {
                "id": "resp_crlf",
                "status": "completed",
                "output": [],
                "usage": dict(USAGE),
            },
        }
        payload = json.dumps(terminal, separators=(",", ":"))
        scenario = raw_sse_scenario(
            "crlf-framing",
            [f"event: response.completed\r\ndata: {payload}\r\n\r\n".encode()],
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_sse_multiple_data_lines_join_with_newline_and_succeed(self) -> None:
        first = '{"type":"response.completed",'
        second = (
            '"response":{"id":"resp_multidata","status":"completed",'
            f'"output":[],"usage":{json.dumps(USAGE, separators=(",", ":"))}}}}}'
        )
        scenario = raw_sse_scenario(
            "multi-data-lines",
            [
                (
                    "event: response.completed\n"
                    f"data: {first}\n"
                    f"data: {second}\n\n"
                ).encode()
            ],
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_first_valid_terminal_stops_later_semantic_processing_both_modes(self) -> None:
        first_output = [
            {
                "type": "message",
                "id": "msg_before_terminal",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "Before terminal."}],
            }
        ]
        trailing = [
            {
                "type": "response.output_text.delta",
                "item_id": "msg_after_terminal",
                "delta": {"would": "fail if consumed"},
            },
            {
                "type": "response.incomplete",
                "response": {
                    "id": "resp_second_terminal",
                    "status": "incomplete",
                    "output": [],
                    "usage": {"input_tokens": 999, "output_tokens": 999},
                },
            },
        ]
        scenario = terminal_contract_scenario(
            "first-terminal-wins",
            "response.completed",
            status="completed",
            output=first_output,
            usage=dict(USAGE),
            leading_events=[
                {
                    "type": "response.output_text.delta",
                    "item_id": "msg_before_terminal",
                    "delta": "Before terminal.",
                }
            ],
            trailing_events=trailing,
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                text = "".join(
                    event["delta"]["text"]
                    for event in [frame.data for frame in frames if isinstance(frame.data, dict)]
                    if event.get("type") == "content_block_delta"
                    and (event.get("delta") or {}).get("type") == "text_delta"
                )
                self.assertEqual(text, "Before terminal.")
                terminal = next(
                    frame.data
                    for frame in frames
                    if isinstance(frame.data, dict)
                    and frame.data.get("type") == "message_delta"
                )
                self.assertEqual(terminal["delta"]["stop_reason"], "end_turn")
                self.assertEqual(terminal["usage"]["input_tokens"], USAGE["input_tokens"])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                self.assertEqual(message["content"][0]["text"], "Before terminal.")
                self.assertEqual(message["stop_reason"], "end_turn")
                self.assertEqual(message["usage"]["input_tokens"], USAGE["input_tokens"])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_duplicate_identical_arguments_done_emits_one_delta(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.function_call_arguments.done"
        )
        events.insert(index + 1, json.loads(json.dumps(events[index])))
        scenario = events_scenario("duplicate-identical-arguments-done", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                events_out = [frame.data for frame in frames if isinstance(frame.data, dict)]
                argument_deltas = [
                    event
                    for event in events_out
                    if event.get("type") == "content_block_delta"
                    and (event.get("delta") or {}).get("type") == "input_json_delta"
                ]
                self.assertEqual(len(argument_deltas), 1)
                tool_indexes = [index for index, kind in lifecycle.starts if kind == "tool_use"]
                self.assertEqual(len(tool_indexes), 1)
                self.assertEqual(lifecycle.stops.count(tool_indexes[0]), 1)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_duplicate_conflicting_arguments_done_is_protocol_failure(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.function_call_arguments.done"
        )
        conflicting = json.loads(json.dumps(events[index]))
        conflicting["arguments"] = '{"file_path":"/daaf/CLAUDE.md"}'
        events.insert(index + 1, conflicting)
        self._assert_stream_failure(
            scenario=events_scenario("duplicate-conflicting-arguments-done", events),
            marker="DUPLICATE_CONFLICTING_ARGUMENTS_DONE",
            expected_kinds=["thinking", "text", "tool_use"],
        )

    def test_arguments_done_public_api_name_shapes(self) -> None:
        # The default fixtures encode the live Codex shape (no `name` on
        # arguments.done — 2026-07-16 live capture). The public OpenAI API
        # documents a `name` field on this event, so both shapes must stay
        # supported: a present matching name passes through; a present
        # conflicting name is a protocol failure.
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.function_call_arguments.done"
        )
        matching = json.loads(json.dumps(events))
        matching[index]["name"] = "Read"
        scenario = events_scenario("arguments-done-with-matching-name", matching)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                tool_indexes = [
                    idx for idx, kind in lifecycle.starts if kind == "tool_use"
                ]
                self.assertEqual(len(tool_indexes), 1)
                self.assertEqual(lifecycle.stops.count(tool_indexes[0]), 1)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

        conflicting = json.loads(json.dumps(events))
        conflicting[index]["name"] = "Edit"
        self._assert_stream_failure(
            scenario=events_scenario(
                "arguments-done-with-conflicting-name", conflicting
            ),
            marker="ARGUMENTS_DONE_CONFLICTING_NAME",
            expected_kinds=["thinking", "text", "tool_use"],
        )

    def test_arguments_done_after_closed_tool_identical_is_ignored(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        done_index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.function_call_arguments.done"
        )
        done_event = events.pop(done_index)
        output_done_index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.done"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        events.insert(output_done_index + 1, done_event)
        scenario = events_scenario("arguments-done-after-close-identical", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                tool_indexes = [index for index, kind in lifecycle.starts if kind == "tool_use"]
                self.assertEqual(len(tool_indexes), 1)
                self.assertEqual(lifecycle.stops.count(tool_indexes[0]), 1)
                argument_deltas = [
                    frame.data
                    for frame in frames
                    if isinstance(frame.data, dict)
                    and frame.data.get("type") == "content_block_delta"
                    and (frame.data.get("delta") or {}).get("type") == "input_json_delta"
                ]
                self.assertEqual(len(argument_deltas), 1)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_arguments_done_after_closed_tool_conflict_fails(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        done_index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.function_call_arguments.done"
        )
        done_event = events.pop(done_index)
        done_event["arguments"] = '{"file_path":"/daaf/CLAUDE.md"}'
        output_done_index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.done"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        events.insert(output_done_index + 1, done_event)
        self._assert_stream_failure(
            scenario=events_scenario("arguments-done-after-close-conflict", events),
            marker="ARGUMENTS_DONE_AFTER_CLOSE_CONFLICT",
            expected_kinds=["thinking", "text", "tool_use"],
        )

    def test_duplicate_identical_output_item_done_emits_one_stop(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.done"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        events.insert(index + 1, json.loads(json.dumps(events[index])))
        scenario = events_scenario("duplicate-identical-output-item-done", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                lifecycle = lifecycle_report(parse_typed_sse(result.body))
                tool_indexes = [index for index, kind in lifecycle.starts if kind == "tool_use"]
                self.assertEqual(len(tool_indexes), 1)
                self.assertEqual(lifecycle.stops.count(tool_indexes[0]), 1)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_duplicate_conflicting_output_item_done_is_protocol_failure(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.done"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        conflicting = json.loads(json.dumps(events[index]))
        conflicting["item"]["arguments"] = '{"file_path":"/daaf/CLAUDE.md"}'
        events.insert(index + 1, conflicting)
        self._assert_stream_failure(
            scenario=events_scenario("duplicate-conflicting-output-item-done", events),
            marker="DUPLICATE_CONFLICTING_OUTPUT_ITEM_DONE",
            expected_kinds=["thinking", "text", "tool_use"],
        )

    def test_duplicate_output_item_added_is_protocol_failure_without_second_start(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.added"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        events.insert(index + 1, json.loads(json.dumps(events[index])))
        frames = self._assert_stream_failure(
            scenario=events_scenario("duplicate-output-item-added", events),
            marker="DUPLICATE_OUTPUT_ITEM_ADDED",
            expected_kinds=["thinking", "text", "tool_use"],
        )
        tool_starts = [
            frame.data
            for frame in frames
            if isinstance(frame.data, dict)
            and frame.data.get("type") == "content_block_start"
            and (frame.data.get("content_block") or {}).get("type") == "tool_use"
        ]
        self.assertEqual(len(tool_starts), 1)

    def test_text_while_tool_open_is_protocol_failure(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.added"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        events.insert(
            index + 1,
            {
                "type": "response.output_text.delta",
                "item_id": "msg_overlap",
                "delta": "overlapping text",
            },
        )
        self._assert_stream_failure(
            scenario=events_scenario("text-while-tool-open", events),
            marker="TEXT_WHILE_TOOL_OPEN",
            expected_kinds=["thinking", "text", "tool_use"],
        )

    def test_second_tool_while_first_open_is_protocol_failure(self) -> None:
        base = full_response_scenario()
        events = json.loads(json.dumps(base.stream_events))
        index = next(
            position
            for position, event in enumerate(events)
            if event.get("type") == "response.output_item.added"
            and (event.get("item") or {}).get("type") == "function_call"
        )
        events.insert(
            index + 1,
            {
                "type": "response.output_item.added",
                "item": {
                    "type": "function_call",
                    "id": "fc_overlap_second",
                    "call_id": "call_overlap_second",
                    "name": "Read",
                    "status": "in_progress",
                },
            },
        )
        self._assert_stream_failure(
            scenario=events_scenario("second-tool-while-first-open", events),
            marker="SECOND_TOOL_WHILE_FIRST_OPEN",
            expected_kinds=["thinking", "text", "tool_use"],
        )

    def test_normal_sequential_two_tools_remains_supported(self) -> None:
        scenario = sequential_two_tools_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                lifecycle = lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(
                    [kind for _index, kind in lifecycle.starts],
                    ["tool_use", "tool_use"],
                )
                self.assertEqual(len(lifecycle.stops), 2)
                self.assertEqual(len(set(lifecycle.stops)), 2)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_lifecycle_oracles_reject_duplicate_terminal_grammar(self) -> None:
        failure_frames = [
            TypedSSEFrame("message_start", {"type": "message_start"}, ""),
            TypedSSEFrame("message_start", {"type": "message_start"}, ""),
            TypedSSEFrame(
                "error",
                {
                    "type": "error",
                    "error": {"type": "api_error", "message": "fixture"},
                },
                "",
            ),
        ]
        with self.assertRaisesRegex(AssertionError, "exactly one message_start"):
            failure_lifecycle_report(failure_frames)

        success_frames = [
            TypedSSEFrame("message_start", {"type": "message_start"}, ""),
            TypedSSEFrame("message_delta", {"type": "message_delta"}, ""),
            TypedSSEFrame("message_delta", {"type": "message_delta"}, ""),
            TypedSSEFrame("message_stop", {"type": "message_stop"}, ""),
        ]
        with self.assertRaisesRegex(AssertionError, "exactly one message_delta"):
            lifecycle_report(success_frames)

    def test_realshim_retries_address_in_use(self) -> None:
        before = provider_scratch_residue()
        scenario = full_response_scenario()
        with OccupiedLoopbackPort() as occupied:
            selector = PortRaceSelector(occupied.port)
            with MockResponsesServer(scenario) as backend:
                shim = RealShim(backend, "openai", port_selector=selector)
                try:
                    with shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=1, oauth=0)
                except (OSError, RuntimeError, TimeoutError) as error:
                    self.fail(
                        "REALSHIM_ADDRESS_IN_USE_RETRY_REQUIRED "
                        f"selected={selector.selected!r} error={error!r}"
                    )
        self.assertGreaterEqual(len(selector.selected), 2)
        self.assertEqual(selector.selected[0], occupied.port)
        self.assertNotEqual(selector.selected[0], selector.selected[-1])
        self.assertEqual(provider_scratch_residue(), before)

    def test_client_disconnect_cancels_stream_header_wait(self) -> None:
        before = provider_scratch_residue()
        scenario = delayed_header_disconnect_scenario(delay=2.0)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                metadata = raw_disconnect_messages(
                    shim,
                    close_after_event=backend.first_response_request,
                    timeout=4.0,
                )
                self.assertGreater(metadata.request_bytes_sent, 0)
                self.assertFalse(metadata.response_headers_seen)
                self.assertTrue(
                    backend.peer_closed_before_delayed_send.wait(1.25),
                    "CLIENT_DISCONNECT_HEADER_WAIT_NOT_CANCELLED "
                    f"requests={len(backend.responses_requests)}",
                )
                self.assertTrue(
                    backend.delayed_send_completed.wait(1.5),
                    "CLIENT_DISCONNECT_HEADER_DELAYED_SEND_NOT_ATTEMPTED",
                )
                self.assertNotEqual(
                    backend.delayed_send_failed.is_set(),
                    backend.delayed_send_succeeded.is_set(),
                    "CLIENT_DISCONNECT_HEADER_SEND_OUTCOME_NOT_EXACT",
                )
                health = shim.get_health()
                self.assertEqual(health.status, 200, health.text)
                self.assertEqual(health.json().get("status"), "ok")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
        self.assertEqual(provider_scratch_residue(), before)

    def test_client_disconnect_cancels_stream_body_read(self) -> None:
        before = provider_scratch_residue()
        scenario = delayed_body_disconnect_scenario(delay=2.0)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                metadata = raw_disconnect_messages(
                    shim,
                    marker='"type": "text_delta"',
                    timeout=4.0,
                )
                self.assertTrue(metadata.response_headers_seen)
                self.assertTrue(metadata.marker_seen)
                self.assertTrue(backend.body_prefix_flushed.is_set())
                self.assertTrue(
                    backend.peer_closed_before_delayed_send.wait(1.25),
                    "CLIENT_DISCONNECT_BODY_READ_NOT_CANCELLED "
                    f"requests={len(backend.responses_requests)}",
                )
                self.assertTrue(
                    backend.delayed_send_completed.wait(1.5),
                    "CLIENT_DISCONNECT_BODY_DELAYED_SEND_NOT_ATTEMPTED",
                )
                self.assertNotEqual(
                    backend.delayed_send_failed.is_set(),
                    backend.delayed_send_succeeded.is_set(),
                    "CLIENT_DISCONNECT_BODY_SEND_OUTCOME_NOT_EXACT",
                )
                health = shim.get_health()
                self.assertEqual(health.status, 200, health.text)
                self.assertEqual(health.json().get("status"), "ok")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)
        self.assertEqual(provider_scratch_residue(), before)

    def test_disconnect_during_rotating_oauth_refresh_persists_new_token(self) -> None:
        before = provider_scratch_residue()
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            backend.delay_oauth_response = True
            with RealShim(backend, "chatgpt") as shim:
                shim.expire_auth_access_token()
                client_errors: list[BaseException] = []

                def disconnecting_client() -> None:
                    try:
                        raw_disconnect_messages(
                            shim,
                            close_after_event=backend.oauth_request_received,
                            timeout=4.0,
                        )
                    except BaseException as error:
                        client_errors.append(error)

                client = threading.Thread(
                    target=disconnecting_client,
                    name="provider-shim-oauth-disconnect-client",
                    daemon=True,
                )
                client.start()
                self.assertTrue(
                    backend.oauth_request_received.wait(4.0),
                    "ROTATING_OAUTH_REQUEST_NOT_RECEIVED",
                )
                client.join(timeout=2.0)
                self.assertFalse(client.is_alive(), "ROTATING_OAUTH_CLIENT_DID_NOT_DISCONNECT")
                self.assertEqual(client_errors, [])
                backend.oauth_response_release.set()
                self.assertTrue(
                    backend.oauth_response_sent.wait(2.0),
                    "ROTATING_OAUTH_RESPONSE_NOT_SENT_AFTER_DISCONNECT",
                )

                persisted = False
                persisted_deadline = time.monotonic() + 3.0
                while time.monotonic() < persisted_deadline:
                    auth = json.loads(shim.auth_path.read_text(encoding="utf-8"))
                    tokens = auth.get("tokens") or {}
                    if (
                        tokens.get("access_token") == backend.rotated_access_token
                        and tokens.get("refresh_token") == FAKE_REFRESH_TOKEN + "_ROTATED"
                    ):
                        persisted = True
                        break
                    time.sleep(0.02)
                self.assertTrue(persisted, "ROTATING_OAUTH_TOKEN_PAIR_NOT_PERSISTED")
                self.assertEqual(len(backend.oauth_requests), 1)
                self.assertTrue(
                    backend.oauth_requests[0].body.get("refresh_token")
                    == FAKE_REFRESH_TOKEN,
                    "ROTATING_OAUTH_SERVER_DID_NOT_CONSUME_ORIGINAL_REFRESH_TOKEN",
                )

                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(len(backend.responses_requests), 1)
                self.assertTrue(
                    backend.responses_requests[0].headers.get("authorization")
                    == "Bearer " + backend.rotated_access_token,
                    "NEXT_REQUEST_DID_NOT_USE_ROTATED_ACCESS_TOKEN",
                )
                backend.assert_request_counts(responses=1, oauth=1)
                health = shim.get_health()
                self.assertEqual(health.status, 200, health.text)
                shim.assert_offline_contract()
        self.assertEqual(provider_scratch_residue(), before)

    def test_outer_task_cancel_after_stream_enter_closes_context(self) -> None:
        report = outer_cancel_after_stream_enter_report()
        self.assertTrue(report.get("request_cancelled"))
        self.assertEqual(
            report.get("cancellation_message"),
            "cancel-after-successful-stream-enter",
        )
        self.assertEqual(report.get("context_exit_count"), 1)
        self.assertTrue(report.get("peer_closed"))
        self.assertEqual(report.get("downstream_terminal_events"), [])
        self.assertEqual(report.get("pending_task_count"), 0)

    def test_client_disconnect_cancels_retry_sleep(self) -> None:
        before = provider_scratch_residue()
        retry_after = 4.0
        scenario = retry_sleep_disconnect_scenario(delay=retry_after)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                client_errors: list[BaseException] = []
                client_metadata: list[object] = []
                release_disconnect = threading.Event()

                def delayed_disconnect_client() -> None:
                    try:
                        client_metadata.append(
                            raw_disconnect_messages(
                                shim,
                                close_after_event=release_disconnect,
                                timeout=6.0,
                            )
                        )
                    except BaseException as error:
                        client_errors.append(error)

                client = threading.Thread(
                    target=delayed_disconnect_client,
                    name="provider-shim-retry-sleep-client",
                    daemon=True,
                )
                client.start()
                marker = "backend stream 503 (attempt 1/4), retrying in 4.00s"
                _line, marker_seen_at = shim.wait_for_stderr_line(marker, timeout=4.0)
                # The production log is emitted only after the complete 503 body has
                # been read and its stream context closed, immediately before the
                # raced asyncio.sleep(). This bounded scheduling turn therefore moves
                # the shim into the target delay; a plain sleep would hold shutdown for
                # nearly the full remaining Retry-After and violate the 1.25s bound.
                time.sleep(0.05)
                release_disconnect.set()
                disconnect_started = time.monotonic()
                client.join(timeout=2.0)
                self.assertFalse(client.is_alive(), "RETRY_SLEEP_CLIENT_DID_NOT_DISCONNECT")
                self.assertEqual(client_errors, [])
                self.assertEqual(len(client_metadata), 1)
                metadata = client_metadata[0]
                self.assertGreater(metadata.request_bytes_sent, 0)
                self.assertFalse(metadata.response_headers_seen)
                self.assertLess(
                    disconnect_started - marker_seen_at,
                    1.25,
                    "RETRY_SLEEP_DISCONNECT_GATE_EXCEEDED_PROMPT_BOUND",
                )
                _cancel_line, cancellation_seen_at = shim.wait_for_stderr_line(
                    "client disconnected; upstream operation cancelled",
                    timeout=1.25,
                )
                self.assertLess(
                    cancellation_seen_at - disconnect_started,
                    1.25,
                    "CLIENT_DISCONNECT_RETRY_SLEEP_NOT_CANCELLED "
                    f"elapsed={cancellation_seen_at - disconnect_started:.3f}s "
                    f"requests={len(backend.responses_requests)}",
                )
                health = shim.get_health()
                self.assertEqual(health.status, 200, health.text)
                self.assertEqual(health.json().get("status"), "ok")
                shim.assert_offline_contract()
                # Keep the real shim alive past the original Retry-After. A plain,
                # uncancellable sleep would now wake and issue request two; the raced
                # sleep has already ended the request and must remain at one attempt.
                self.assertFalse(
                    backend.second_response_request.wait(retry_after + 0.3),
                    "CLIENT_DISCONNECT_RETRY_ISSUED_SECOND_REQUEST "
                    f"requests={len(backend.responses_requests)}",
                )
                backend.assert_request_counts(responses=1, oauth=0)
        self.assertEqual(provider_scratch_residue(), before)


if __name__ == "__main__":
    unittest.main()
