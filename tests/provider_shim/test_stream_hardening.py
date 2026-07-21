"""Deterministic red/green contracts for provider-shim stream hardening."""

from __future__ import annotations

import json
import threading
import time
import unittest
import urllib.parse

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
    block_starts,
    assert_lifecycle_log_contract,
    controlled_asgi_probe,
    delayed_body_disconnect_scenario,
    delayed_header_disconnect_scenario,
    events_scenario,
    failure_lifecycle_report,
    full_response_scenario,
    group_lifecycle_logs,
    incomplete_response_scenario,
    lifecycle_for_response,
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
    sequenced_attempt_scenario,
    sequential_two_tools_scenario,
    structured_error_scenario,
    terminal_contract_scenario,
    terminal_failure_scenario,
    text_delta_values,
    thinking_delta_values,
)


class ProviderShimStreamHardeningTests(unittest.TestCase):
    maxDiff = 12000

    def _event_line(self, lines: list[object], event: str) -> object:
        matches = [line for line in lines if line.event == event]
        self.assertEqual(len(matches), 1, (event, [line.raw for line in lines]))
        return matches[0]

    def _terminal_fields(self, lines: list[object]) -> dict[str, str]:
        return self._event_line(lines, "terminal").fields

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
        expected_error_type: str = "api_error",
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
                lifecycle = failure_lifecycle_report(frames, expected_error_type)
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

    def test_reasoning_while_text_open_defers_to_trailing_thinking(self) -> None:
        # v1.2.14 (R3, adjudicated flip): out-of-order reasoning that arrives while a
        # text block is open is TOLERATED — buffered and emitted as a TRAILING thinking
        # block after the text block closes (ratified downstream shape), not failed as
        # the pre-R3 strict contract required.
        scenario = reasoning_while_text_open_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["text", "thinking"],
                    "text block, then a trailing thinking block",
                )
                self.assertEqual(report.open_at_end, set())
                self.assertEqual(text_delta_values(frames), ["Partial text."])
                self.assertEqual(
                    thinking_delta_values(frames), ["Out-of-order thinking."]
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_reasoning_while_tool_open_defers_to_trailing_thinking(self) -> None:
        # v1.2.14 (R3, adjudicated flip): out-of-order reasoning while a tool block is
        # open is tolerated — the tool block closes first, then the buffered reasoning
        # is emitted as a TRAILING thinking block (ratified shape).
        scenario = reasoning_while_tool_open_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["tool_use", "thinking"],
                    "tool_use block, then a trailing thinking block",
                )
                self.assertEqual(report.open_at_end, set())
                self.assertEqual(
                    thinking_delta_values(frames), ["Out-of-order thinking."]
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

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
        # v1.2.10: a pre-content backend 400 now surfaces the status-aware type
        # invalid_request_error in-band (was a hardcoded api_error), so Claude Code
        # stops retrying a deterministic rejection. HTTP status is still 200.
        frames = self._assert_stream_failure(
            scenario=backend_status_scenario("status-400", 400),
            marker="PRECONTENT_STATUS_400_TERMINAL_ERROR",
            expected_kinds=[],
            expected_error_type="invalid_request_error",
        )
        self.assertEqual(
            [frame.data.get("type") for frame in frames if isinstance(frame.data, dict)],
            ["message_start", "error"],
        )

    def test_stream_exhausted_retryable_status_uses_terminal_error(self) -> None:
        # 503 is not in the deterministic status->type map, so it keeps api_error
        # (reads as retryable — correct for a genuine 5xx) after the internal retry
        # loop exhausts its attempts.
        frames = self._assert_stream_failure(
            scenario=backend_status_scenario(
                "status-503-exhausted",
                503,
                retry_after="0",
            ),
            marker="PRECONTENT_STATUS_503_EXHAUSTED_TERMINAL_ERROR",
            expected_kinds=[],
            expected_requests=4,
            expected_error_type="api_error",
        )
        self.assertEqual(
            [frame.data.get("type") for frame in frames if isinstance(frame.data, dict)],
            ["message_start", "error"],
        )

    def test_stream_exhausted_429_surfaces_rate_limit_error_inband(self) -> None:
        # v1.2.10: an exhausted retryable 429 maps to rate_limit_error in-band.
        frames = self._assert_stream_failure(
            scenario=backend_status_scenario(
                "status-429-exhausted",
                429,
                retry_after="0",
            ),
            marker="PRECONTENT_STATUS_429_EXHAUSTED_TERMINAL_ERROR",
            expected_kinds=[],
            expected_requests=4,
            expected_error_type="rate_limit_error",
        )
        self.assertEqual(
            [frame.data.get("type") for frame in frames if isinstance(frame.data, dict)],
            ["message_start", "error"],
        )

    def test_stream_midstream_inband_failure_keeps_api_error(self) -> None:
        # v1.2.10 (e): a mid-stream in-band failure after content has begun has NO
        # backend HTTP status, so it must keep the generic api_error type — the
        # v1.2.8 finalizer semantics are unchanged for these paths.
        self._assert_terminal_error(
            scenario=terminal_failure_scenario("text", "error"),
            expected_kind="text",
            marker="MIDSTREAM_INBAND_ERROR_KEEPS_API_ERROR",
        )

    def _nonstream_backend_status(
        self,
        *,
        status: int,
        expected_type: str,
        expected_requests: int,
        marker: str,
    ) -> None:
        scenario = backend_status_scenario(
            f"nonstream-status-{status}", status, retry_after="0"
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(result.status, status, f"{marker}: {result.text}")
                body = result.json()
                self.assertEqual(body.get("type"), "error", marker)
                error = body.get("error") or {}
                self.assertEqual(error.get("type"), expected_type, marker)
                self.assertIsInstance(error.get("message"), str, marker)
                self.assertLessEqual(len(error.get("message", "")), 200, marker)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=expected_requests, oauth=0)

    def test_nonstream_backend_400_passes_through_as_invalid_request_error(self) -> None:
        # v1.2.10 (a): a deterministic 400 reaches the client as its real 400 with
        # an invalid_request_error type (was a flat 502 api_error) and is NOT
        # retried internally (400 is not in RETRY_STATUSES) -> exactly one request.
        self._nonstream_backend_status(
            status=400,
            expected_type="invalid_request_error",
            expected_requests=1,
            marker="NONSTREAM_400_INVALID_REQUEST",
        )

    def test_nonstream_backend_retryable_statuses_surface_correct_type(self) -> None:
        # v1.2.10 (b): retryable statuses exhaust the internal retry loop (4 total
        # attempts) then surface with the mapped type: 429->rate_limit_error,
        # 500->api_error (not in the deterministic map).
        for status, expected_type in ((429, "rate_limit_error"), (500, "api_error")):
            with self.subTest(status=status):
                self._nonstream_backend_status(
                    status=status,
                    expected_type=expected_type,
                    expected_requests=4,
                    marker=f"NONSTREAM_{status}_{expected_type.upper()}",
                )

    def test_chatgpt_claude_slug_fast_fails_nonstream_without_round_trip(self) -> None:
        # v1.2.10 (c): a claude-* slug on the chatgpt lane is rejected pre-flight
        # with a 400 invalid_request_error and NO backend round-trip.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False, model="claude-fable-5")
                self.assertEqual(result.status, 400, result.text)
                error = (result.json().get("error") or {})
                self.assertEqual(error.get("type"), "invalid_request_error")
                self.assertIn("ChatGPT (Codex)", error.get("message", ""))
                self.assertIn("environment_settings.txt", error.get("message", ""))
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=0, oauth=0)

    def test_chatgpt_claude_slug_fast_fails_stream_without_round_trip(self) -> None:
        # v1.2.10 (c): the same fast-fail applies to a streaming inbound request —
        # it fires before the HTTP-200 stream start, so the client sees a plain
        # JSON 400, not a 200 SSE error stream.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, model="claude-opus-4-8")
                self.assertEqual(result.status, 400, result.text)
                error = (result.json().get("error") or {})
                self.assertEqual(error.get("type"), "invalid_request_error")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=0, oauth=0)

    def test_chatgpt_provider_prefixed_claude_slug_fast_fails_without_round_trip(self) -> None:
        # v1.2.10 review-amendment: a PROVIDER-PREFIXED claude slug
        # ("anthropic/claude-opus-4-8") must also fast-fail on the chatgpt lane.
        # The harness leaves SHIM_STRIP_MODEL_PREFIX unset, so _map_model returns the
        # slug WITH its "anthropic/" prefix; the last-path-segment match catches it
        # (a whole-slug .startswith("claude") would have slipped it to the backend).
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False, model="anthropic/claude-opus-4-8")
                self.assertEqual(result.status, 400, result.text)
                error = (result.json().get("error") or {})
                self.assertEqual(error.get("type"), "invalid_request_error")
                self.assertIn("ChatGPT (Codex)", error.get("message", ""))
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=0, oauth=0)

    def test_openai_lane_does_not_fast_fail_claude_slug(self) -> None:
        # v1.2.10 (c): the openai/API-key lane forwards any slug unchanged — no
        # model-family opinion. A claude-* slug reaches the backend and succeeds.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False, model="claude-fable-5")
                self.assertEqual(result.status, 200, result.text)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

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

    def test_sse_complete_data_line_without_blank_boundary_flushes(self) -> None:
        # v1.2.14 (R5): a fully-formed terminal event whose trailing blank-line
        # boundary a proxy trimmed is now flushed at EOF and finalizes SUCCESS. Before
        # R5 this raised a framing failure (B7 — a completed response reported as an
        # error). The payload is complete and parses cleanly, so downstream strict
        # validation still applies; only the missing blank line is tolerated.
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
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(
                    result.status,
                    200,
                    f"SSE_COMPLETE_LINE_WITHOUT_BLANK_BOUNDARY {result.text}",
                )
                lifecycle_report(parse_typed_sse(result.body))
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

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

    def test_sse_event_size_limit_is_transport_segmentation_invariant(self) -> None:
        limit = 16 * 1024 * 1024
        template = {
            "type": "response.completed",
            "response": {
                "id": "resp_size_boundary",
                "status": "completed",
                "output": [],
                "usage": dict(USAGE),
                "padding": "",
            },
        }
        empty_payload = json.dumps(template, separators=(",", ":"))
        marker = '"padding":""'
        self.assertIn(marker, empty_payload)
        prefix, suffix = empty_payload.split(marker)
        payload_overhead = len((prefix + '"padding":""' + suffix).encode("utf-8"))

        for label, target_size, should_succeed in (
            ("below", limit - 1, True),
            ("at", limit, True),
            ("above", limit + 1, False),
        ):
            padding_size = target_size - payload_overhead
            self.assertGreaterEqual(padding_size, 0)
            payload = (
                prefix + '"padding":"' + ("X" * padding_size) + '"' + suffix
            ).encode("utf-8")
            self.assertEqual(len(payload), target_size)
            segmentations = (
                (
                    "joined-by-harness",
                    [b"data: ", payload, b"\n\n"],
                    False,
                ),
                (
                    "prefix-and-terminator-fragmented",
                    [b"d", b"a", b"t", b"a", b":", b" ", payload, b"\n", b"\n"],
                    True,
                ),
            )
            for segmentation, chunks, preserve_chunks in segmentations:
                with self.subTest(boundary=label, segmentation=segmentation):
                    scenario = raw_sse_scenario(
                        f"event-size-{label}-{segmentation}",
                        chunks,
                        preserve_chunks=preserve_chunks,
                    )
                    with MockResponsesServer(scenario) as backend:
                        with RealShim(backend, "chatgpt") as shim:
                            result = shim.post_messages(stream=True, timeout=60.0)
                            self.assertEqual(result.status, 200)
                            frames = parse_typed_sse(result.body)
                            if should_succeed:
                                lifecycle_report(frames)
                            else:
                                failure_lifecycle_report(frames)
                            backend.assert_request_counts(responses=1, oauth=0)

    def test_sse_event_size_counts_repeated_data_field_newline_join(self) -> None:
        limit = 16 * 1024 * 1024
        template = {
            "type": "response.completed",
            "response": {
                "id": "resp_multidata_size_boundary",
                "status": "completed",
                "output": [],
                "usage": dict(USAGE),
                "padding": "",
            },
        }
        empty_payload = json.dumps(template, separators=(",", ":"))
        marker = '"padding":""'
        prefix, suffix = empty_payload.split(marker)
        payload_overhead = len((prefix + '"padding":""' + suffix).encode("utf-8"))

        for label, logical_size, should_succeed in (
            ("at", limit, True),
            ("above", limit + 1, False),
        ):
            # Repeated SSE data fields insert one logical newline. Size the JSON bytes
            # one byte below the target, then split after a comma where JSON permits
            # that newline as insignificant whitespace.
            padding_size = logical_size - 1 - payload_overhead
            payload = (
                prefix + '"padding":"' + ("Y" * padding_size) + '"' + suffix
            ).encode("utf-8")
            split_at = payload.find(b',"response"') + 1
            self.assertGreater(split_at, 0)
            self.assertEqual(len(payload) + 1, logical_size)
            scenario = raw_sse_scenario(
                f"multidata-event-size-{label}",
                [
                    b"data: ",
                    payload[:split_at],
                    b"\n",
                    b"data: ",
                    payload[split_at:],
                    b"\n",
                    b"\n",
                ],
                preserve_chunks=True,
            )
            with self.subTest(boundary=label):
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_messages(stream=True, timeout=60.0)
                        self.assertEqual(result.status, 200)
                        frames = parse_typed_sse(result.body)
                        if should_succeed:
                            lifecycle_report(frames)
                        else:
                            failure_lifecycle_report(frames)
                        backend.assert_request_counts(responses=1, oauth=0)

    def test_sse_oversized_partial_line_eof_fails_without_dispatch(self) -> None:
        limit = 16 * 1024 * 1024
        scenario = raw_sse_scenario(
            "oversized-partial-line-eof",
            [b"data: " + (b"Z" * (limit + 1))],
        )
        self._assert_stream_failure(
            scenario=scenario,
            marker="SSE_OVERSIZED_PARTIAL_LINE_EOF",
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

    def test_text_while_tool_open_defers_to_trailing_text(self) -> None:
        # v1.2.14 (R3, adjudicated flip): text emitted while a tool block is open is
        # TOLERATED — buffered and emitted as a TRAILING text block after the tool
        # closes (ratified shape), not failed as the pre-R3 strict contract required.
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
        scenario = events_scenario("text-while-tool-open", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["thinking", "text", "tool_use", "text"],
                    "leading thinking+text, the tool, then a trailing text block",
                )
                self.assertEqual(report.open_at_end, set())
                # Leading streamed text, then the deferred out-of-order text trailing.
                self.assertEqual(
                    text_delta_values(frames),
                    ["Aggregated answer.", "overlapping text"],
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_second_tool_while_first_open_defers_to_sequential_blocks(self) -> None:
        # v1.2.14 (R3, adjudicated flip): a second tool added while the first is open
        # is TOLERATED — DEFERRED and drained after the first closes, yielding two
        # NON-OVERLAPPING tool_use blocks in added order (ratified shape), not failed.
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
        scenario = events_scenario("second-tool-while-first-open", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["thinking", "text", "tool_use", "tool_use"],
                    "leading thinking+text, then two non-overlapping tool blocks",
                )
                self.assertEqual(report.open_at_end, set())
                # Both tool_use blocks carry the correct call ids in added order; the
                # deferred second tool supplied no arguments, so its input stays empty.
                tool_starts = [
                    start
                    for start in block_starts(frames)
                    if (start.get("content_block") or {}).get("type") == "tool_use"
                ]
                self.assertEqual(
                    [start["content_block"]["id"] for start in tool_starts],
                    ["call_full_fixture", "call_overlap_second"],
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

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

    # v1.3.0 (A1): test_disconnect_during_rotating_oauth_refresh_persists_new_token
    # was DELETED here. It pinned the deleted Python OAuth-refresh path — the shim
    # POSTing to /oauth/token, atomically persisting the ROTATED refresh/access token
    # pair into auth.json, and reusing it on the next request. Under the delegation
    # design (A1-R2) the shim never writes auth.json and never performs an OAuth POST;
    # codex is the single writer. The disconnect-mid-refresh persistence hazard this
    # test guarded is structurally gone (no shim-side write to strand). Delegated
    # refresh is covered in test_v130_auth_delegation.py.

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
                disconnect_line, cancellation_seen_at = shim.wait_for_stderr_line(
                    "phase=disconnect event=disconnect",
                    timeout=1.25,
                )
                parsed_disconnects = [
                    line
                    for lines in group_lifecycle_logs(disconnect_line).values()
                    for line in lines
                ]
                self.assertEqual(len(parsed_disconnects), 1, disconnect_line)
                disconnect = parsed_disconnects[0]
                self.assertEqual(
                    disconnect.fields.get("observed_phase"),
                    "disconnect_watcher",
                )
                self.assertEqual(
                    urllib.parse.unquote(disconnect.fields.get("detail", "")),
                    "ASGI http.disconnect observed",
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

    def test_v1211_request_id_headers_and_lifecycle_correlation(self) -> None:
        scenario = full_response_scenario()
        inbound_id = "f" * 32
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                json_result = shim.post_messages(
                    stream=False,
                    headers={"x-daaf-request-id": inbound_id},
                )
                sse_result = shim.post_messages(
                    stream=True,
                    headers={"x-daaf-request-id": inbound_id},
                )
                self.assertEqual(json_result.status, 200, json_result.text)
                self.assertEqual(sse_result.status, 200, sse_result.text)
                json_lines = lifecycle_for_response(shim, json_result)
                sse_lines = lifecycle_for_response(shim, sse_result)
                ids = {
                    json_result.headers.get("x-daaf-request-id"),
                    sse_result.headers.get("x-daaf-request-id"),
                }
                self.assertEqual(len(ids), 2)
                self.assertNotIn(inbound_id, ids)
                for result, lines in (
                    (json_result, json_lines),
                    (sse_result, sse_lines),
                ):
                    req_id = result.headers["x-daaf-request-id"]
                    self.assertRegex(req_id, r"^[0-9a-f]{32}$")
                    self.assertEqual({line.req_id for line in lines}, {req_id})
                    terminal = self._terminal_fields(lines)
                    self.assertEqual(
                        terminal["outcome"],
                        "success",
                        (result.headers, [line.raw for line in lines]),
                    )
                    self.assertEqual(terminal["attempts"], "1")
                    self.assertEqual(terminal["retries"], "0")
                    self.assertEqual(terminal["terminal_frame_send"], "send_completed")
                    self.assertEqual(terminal["body_close_send"], "send_completed")
                    events = [line.event for line in lines]
                    self.assertIn("request_parsed", events)
                    self.assertIn("upstream_headers", events)
                    self.assertIn("downstream_first_content", events)
                    httpx_records = [
                        line
                        for line in shim.captured_stderr().splitlines()
                        if "HTTP Request: POST " in line
                        and f"req_id={req_id} phase=upstream_request" in line
                    ]
                    self.assertEqual(len(httpx_records), 1, httpx_records)
                startup_records = [
                    line
                    for line in shim.captured_stderr().splitlines()
                    if "req_id=- phase=process shim v1.3.5 starting" in line
                ]
                self.assertEqual(len(startup_records), 1, startup_records)
                self.assertIn(
                    "upstream_first_event",
                    [line.event for line in sse_lines],
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2, oauth=0)

    def test_v1211_concurrent_requests_keep_request_local_state(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            first_entered, release_first = backend.gate_response_request(1)
            second_entered, release_second = backend.gate_response_request(2)
            with RealShim(backend, "openai") as shim:
                results: dict[str, object] = {}
                failures: list[BaseException] = []

                def call(label: str) -> None:
                    try:
                        results[label] = shim.post_messages(
                            stream=False,
                            model=f"gpt-fixture-{label}",
                            headers={"x-daaf-request-id": label * 32},
                        )
                    except BaseException as error:
                        failures.append(error)

                first = threading.Thread(target=call, args=("a",), daemon=True)
                second = threading.Thread(target=call, args=("b",), daemon=True)
                first.start()
                self.assertTrue(first_entered.wait(3.0))
                second.start()
                self.assertTrue(second_entered.wait(3.0))
                release_second.set()
                second.join(timeout=5.0)
                self.assertFalse(second.is_alive())
                release_first.set()
                first.join(timeout=5.0)
                self.assertFalse(first.is_alive())
                self.assertEqual(failures, [])
                self.assertEqual(set(results), {"a", "b"})
                observed_ids = set()
                for label, result in results.items():
                    self.assertEqual(result.status, 200, result.text)
                    lines = lifecycle_for_response(shim, result)
                    observed_ids.add(result.headers["x-daaf-request-id"])
                    terminal = self._terminal_fields(lines)
                    self.assertEqual(terminal["model"], f"gpt-fixture-{label}")
                    self.assertEqual(terminal["attempts"], "1")
                    self.assertEqual(terminal["retries"], "0")
                self.assertEqual(len(observed_ids), 2)
                self.assertNotIn("a" * 32, observed_ids)
                self.assertNotIn("b" * 32, observed_ids)
                groups = group_lifecycle_logs(shim.captured_stderr())
                self.assertTrue(observed_ids.issubset(groups))
                for req_id in observed_ids:
                    self.assertEqual({line.req_id for line in groups[req_id]}, {req_id})
                    assert_lifecycle_log_contract(groups[req_id])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2, oauth=0)

    def test_v1211_attempt_and_retry_accounting_matrix(self) -> None:
        cases = (
            ("buffered-success", "openai", False, [200], 1, 0, "success"),
            ("stream-success", "openai", True, [200], 1, 0, "success"),
            ("buffered-status-retry", "openai", False, [503, 200], 2, 1, "success"),
            ("stream-status-retry", "chatgpt", True, [503, 200], 2, 1, "success"),
            ("stream-status-exhausted", "chatgpt", True, [503], 4, 3, "error"),
            ("stream-transport-retry", "chatgpt", True, ["transport", 200], 2, 1, "success"),
            ("stream-transport-exhausted", "chatgpt", True, ["transport"], 4, 3, "error"),
        )
        for name, mode, stream, statuses, attempts, retries, outcome in cases:
            with self.subTest(case=name):
                headers = [{"Retry-After": "0"} for _status in statuses]
                scenario = sequenced_attempt_scenario(
                    name,
                    statuses,
                    headers=headers,
                )
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_messages(stream=stream)
                        self.assertEqual(
                            result.status,
                            200,
                            f"{name}: {result.status} {result.text}",
                        )
                        if stream:
                            frames = parse_typed_sse(result.body)
                            if outcome == "success":
                                lifecycle_report(frames)
                            else:
                                failure_lifecycle_report(frames)
                        lines = lifecycle_for_response(shim, result, timeout=15.0)
                        terminal = self._terminal_fields(lines)
                        self.assertEqual(terminal["attempts"], str(attempts), name)
                        self.assertEqual(terminal["retries"], str(retries), name)
                        self.assertEqual(terminal["outcome"], outcome, name)
                        self.assertEqual(
                            [line.event for line in lines].count("upstream_attempt"),
                            attempts,
                            name,
                        )
                        self.assertEqual(
                            [line.event for line in lines].count("upstream_retry"),
                            retries,
                            name,
                        )
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=attempts, oauth=0)

        for name, statuses, expected_status, attempts, retries, outcome in (
            ("buffered-transport-retry", ["transport", 200], 200, 2, 1, "success"),
            ("buffered-transport-exhausted", ["transport"], 502, 4, 3, "error"),
        ):
            with self.subTest(case=name):
                scenario = sequenced_attempt_scenario(name, statuses)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "openai") as shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, expected_status, result.text)
                        lines = lifecycle_for_response(shim, result, timeout=15.0)
                        terminal = self._terminal_fields(lines)
                        self.assertEqual(terminal["attempts"], str(attempts))
                        self.assertEqual(terminal["retries"], str(retries))
                        self.assertEqual(terminal["outcome"], outcome)
                        backend.assert_request_counts(responses=attempts, oauth=0)

    def test_v1211_upstream_metadata_allowlist_precedence_and_length_cap(self) -> None:
        secret = "sk-FAKE_METADATA_SECRET_123456789"
        scenario = full_response_scenario()
        scenario.stream_headers = {
            "x-request-id": "chosen-" + secret,
            "request-id": "lower-precedence",
            "x-openai-request-id": "lower-precedence-openai",
            "openai-request-id": "lowest-precedence",
            "x-arbitrary-sentinel": "ARBITRARY_HEADER_MUST_NOT_LOG",
            "authorization": "Bearer CREDENTIAL_MUST_NOT_LOG",
        }
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lines = lifecycle_for_response(shim, result)
                upstream = self._event_line(lines, "upstream_headers")
                self.assertEqual(upstream.fields["upstream_req_id_header"], "x-request-id")
                self.assertEqual(
                    urllib.parse.unquote(upstream.fields["upstream_req_id"]),
                    "chosen-[REDACTED]",
                )
                logs = shim.captured_stderr()
                self.assertNotIn(secret, logs)
                self.assertNotIn("ARBITRARY_HEADER_MUST_NOT_LOG", logs)
                self.assertNotIn("CREDENTIAL_MUST_NOT_LOG", logs)

        scenario = full_response_scenario()
        scenario.stream_headers = {"x-request-id": "z" * 260}
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=True)
                lines = lifecycle_for_response(shim, result)
                upstream = self._event_line(lines, "upstream_headers")
                self.assertEqual(upstream.fields["upstream_req_id"], "z" * 200)
                self.assertNotIn("z" * 201, upstream.raw)

        report = controlled_asgi_probe(
            response_headers={
                "x-request-id": "  alpha\t beta\r\n gamma " + secret,
                "x-nonallowlisted": "NONALLOWLISTED_CONTROL_SENTINEL",
            }
        )
        upstream = self._event_line(report.lifecycle, "upstream_headers")
        self.assertEqual(upstream.fields["upstream_req_id_header"], "x-request-id")
        self.assertEqual(
            urllib.parse.unquote(upstream.fields["upstream_req_id"]),
            "alpha beta gamma [REDACTED]",
        )
        self.assertIn(
            "upstream_req_id=alpha%20beta%20gamma%20%5BREDACTED%5D",
            upstream.raw,
        )
        self.assertNotIn(secret, report.logs)
        self.assertNotIn("NONALLOWLISTED_CONTROL_SENTINEL", report.logs)
        for line in report.logs.splitlines():
            self.assertNotRegex(line, r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

    def test_v1211_machine_field_encoding_blocks_lifecycle_injection(self) -> None:
        # SECURITY REGRESSION: every value below reaches production lifecycle
        # serialization through a distinct untrusted surface. A whitespace parser
        # must never reinterpret an injected key=value fragment as a real field.
        model = (
            "gpt-fixture abc event=cleanup status=completed\t=%\"'\r\n雪"
        )
        upstream_request_id = (
            "abc outcome=success attempts=0\t=%\"'\r\n雪"
        )
        backend_type = (
            "abc req_id=00000000000000000000000000000000\t=%\"'\r\n雪"
        )
        backend_code = (
            "abc status=completed event=cleanup\t=%\"'\r\n雪"
        )
        cleanup_error = (
            "abc event=terminal status=completed\t=%\"'\r\n雪"
        )
        scenario = structured_error_scenario(
            "machine-field-injection",
            "error",
            {
                "type": backend_type,
                "code": backend_code,
                "message": "safe mapped backend failure",
            },
        )
        report = controlled_asgi_probe(
            scenario=scenario,
            stream=True,
            cleanup_failure=True,
            cleanup_failure_text=cleanup_error,
            response_headers={"x-request-id": upstream_request_id},
            raw_request_body=json.dumps(
                {
                    "model": model,
                    "max_tokens": 256,
                    "stream": True,
                    "messages": [{"role": "user", "content": "ASGI fixture"}],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        self.assertIsNone(report.raised)
        self.assertFalse(report.cancelled)
        assert_lifecycle_log_contract(report.lifecycle)
        events = [line.event for line in report.lifecycle]
        self.assertEqual(events.count("terminal"), 1)
        self.assertEqual(events.count("cleanup"), 1)
        self.assertEqual(events[-2:], ["terminal", "cleanup"])

        request_parsed = self._event_line(report.lifecycle, "request_parsed")
        upstream = self._event_line(report.lifecycle, "upstream_headers")
        backend_error = self._event_line(report.lifecycle, "backend_error")
        terminal = self._terminal_fields(report.lifecycle)
        cleanup = self._event_line(report.lifecycle, "cleanup").fields
        canonical_req_id = report.lifecycle[0].req_id
        self.assertRegex(canonical_req_id, r"^[0-9a-f]{32}$")
        self.assertNotEqual(canonical_req_id, "0" * 32)
        self.assertEqual({line.req_id for line in report.lifecycle}, {canonical_req_id})
        self.assertEqual(terminal["outcome"], "error")
        self.assertEqual(terminal["attempts"], "1")
        self.assertEqual(cleanup["status"], "failed")
        self.assertEqual(cleanup["failures"], "1")

        # urllib.parse.unquote is the independent standard-library oracle for the
        # documented percent-encoded machine-field grammar. Production helpers are
        # intentionally not imported or duplicated in this test.
        decoded = {
            "model": urllib.parse.unquote(request_parsed.fields["model"]),
            "upstream_req_id": urllib.parse.unquote(upstream.fields["upstream_req_id"]),
            "backend_type": urllib.parse.unquote(backend_error.fields["backend_type"]),
            "backend_code": urllib.parse.unquote(backend_error.fields["backend_code"]),
            "cleanup_error": urllib.parse.unquote(cleanup["error"]),
        }
        self.assertEqual(
            decoded["model"],
            "gpt-fixture abc event=cleanup status=completed=%\"'雪",
        )
        self.assertEqual(
            decoded["upstream_req_id"],
            "abc outcome=success attempts=0 =%\"' 雪",
        )
        self.assertEqual(
            decoded["backend_type"],
            "abc req_id=00000000000000000000000000000000 =%\"' 雪",
        )
        self.assertEqual(
            decoded["backend_code"],
            "abc status=completed event=cleanup =%\"' 雪",
        )
        self.assertEqual(
            decoded["cleanup_error"],
            "abc event=terminal status=completed =%\"' 雪",
        )
        for line in report.lifecycle:
            self.assertEqual(len(line.raw.splitlines()), 1, line.raw)

    def test_v1211_machine_field_encoding_is_total_for_unpaired_surrogates(self) -> None:
        # JSON accepts escaped lone surrogate code units even though strict UTF-8 does
        # not. Lifecycle serialization must preserve a printable forensic escape and
        # must never let observability abort request finalization.
        model_report = controlled_asgi_probe(
            raw_request_body=(
                b'{"model":"gpt-fixture-\\ud800","max_tokens":256,'
                b'"stream":true,"messages":[{"role":"user",'
                b'"content":"ASGI fixture"}]}'
            )
        )
        self.assertIsNone(model_report.raised)
        self.assertFalse(model_report.cancelled)
        model_parsed = self._event_line(
            model_report.lifecycle,
            "request_parsed",
        )
        self.assertEqual(
            urllib.parse.unquote(model_parsed.fields["model"]),
            "gpt-fixture-" + "\\ud800",
        )

        backend_report = controlled_asgi_probe(
            scenario=structured_error_scenario(
                "backend-lone-surrogate",
                "error",
                {
                    "type": "backend-type-\udfff",
                    "code": "backend-code-\udc00",
                    "message": "controlled backend failure",
                },
            )
        )
        self.assertIsNone(backend_report.raised)
        self.assertFalse(backend_report.cancelled)
        backend_error = self._event_line(
            backend_report.lifecycle,
            "backend_error",
        )
        self.assertEqual(
            urllib.parse.unquote(backend_error.fields["backend_type"]),
            "backend-type-" + "\\udfff",
        )
        self.assertEqual(
            urllib.parse.unquote(backend_error.fields["backend_code"]),
            "backend-code-" + "\\udc00",
        )

        # Cleanup error metadata comes from type(error).__name__; Python rejects lone
        # surrogates in a dynamic type name before production can observe one. Both
        # externally reachable surrogate cases must still finalize cleanup exactly once.
        for report in (model_report, backend_report):
            events = [line.event for line in report.lifecycle]
            self.assertEqual(events.count("terminal"), 1)
            self.assertEqual(events.count("cleanup"), 1)
            for line in report.lifecycle:
                self.assertEqual(len(line.raw.splitlines()), 1, line.raw)

    def test_v1211_sensitive_text_sanitizer_covers_credential_families(self) -> None:
        # Fabricated-only credential corpus. Each family is independently driven
        # through retained upstream request metadata, backend type/code, and the
        # diagnostic HTTP body slice. Free-form backend message prose is supplied
        # separately to prove that the client receives only the fixed classification.
        credentials = (
            ("openai-prefix", "sk-FAKE_SANITIZER_PREFIX_1234567890", "sk-FAKE_SANITIZER_PREFIX_1234567890"),
            ("bearer-header", "Authorization: Bearer FABRICATED_BEARER_HEADER_123456", "FABRICATED_BEARER_HEADER_123456"),
            ("bearer-standalone", "Bearer FABRICATED_BEARER_STANDALONE_123456", "FABRICATED_BEARER_STANDALONE_123456"),
            ("basic-header", "Authorization: Basic RkFLRV9CQVNJQ19DUkVERU5USUFM", "RkFLRV9CQVNJQ19DUkVERU5USUFM"),
            ("jwt", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJGQUtFIn0.ZmFrZS1zaWduYXR1cmU", "eyJhbGciOiJub25lIn0.eyJzdWIiOiJGQUtFIn0.ZmFrZS1zaWduYXR1cmU"),
            ("api-key", 'api_key="FABRICATED_API_KEY_123456"', "FABRICATED_API_KEY_123456"),
            ("access-token", "access_token: FABRICATED_ACCESS_TOKEN_123456", "FABRICATED_ACCESS_TOKEN_123456"),
            ("refresh-token", "refresh_token='FABRICATED_REFRESH_TOKEN_123456'", "FABRICATED_REFRESH_TOKEN_123456"),
            ("id-token", 'id_token: "FABRICATED_ID_TOKEN_123456"', "FABRICATED_ID_TOKEN_123456"),
            ("token", "token=FABRICATED_GENERIC_TOKEN_123456", "FABRICATED_GENERIC_TOKEN_123456"),
            ("secret", "secret: FABRICATED_SECRET_123456", "FABRICATED_SECRET_123456"),
            ("password", "password='FABRICATED_PASSWORD_123456'", "FABRICATED_PASSWORD_123456"),
        )
        for name, credential_form, secret_value in credentials:
            with self.subTest(family=name):
                carrier = f"SAFE_BEFORE {credential_form} SAFE_AFTER"
                scenario = structured_error_scenario(
                    f"credential-{name}",
                    "error",
                    {
                        "type": carrier,
                        "code": carrier,
                        "message": carrier,
                    },
                )
                scenario.stream_error_body = json.dumps(
                    {
                        "error": {
                            "type": carrier,
                            "code": carrier,
                            "message": carrier,
                        }
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                report = controlled_asgi_probe(
                    scenario=scenario,
                    stream=True,
                    response_status=400,
                    response_headers={"x-request-id": carrier},
                )
                self.assertIsNone(report.raised)
                self.assertFalse(report.cancelled)
                failure = failure_lifecycle_report(
                    parse_typed_sse(
                        b"".join(
                            message.get("body", b"")
                            for message in report.messages
                            if message.get("type") == "http.response.body"
                        )
                    ),
                    expected_error_type="invalid_request_error",
                )
                upstream = self._event_line(report.lifecycle, "upstream_headers")
                backend_error = self._event_line(report.lifecycle, "backend_error")
                decoded_fields = (
                    urllib.parse.unquote(upstream.fields["upstream_req_id"]),
                    urllib.parse.unquote(backend_error.fields["backend_type"]),
                    urllib.parse.unquote(backend_error.fields["backend_code"]),
                )
                for observed in decoded_fields:
                    self.assertIn("SAFE_BEFORE", observed, (name, observed))
                    self.assertIn("[REDACTED]", observed, (name, observed))
                    self.assertIn("SAFE_AFTER", observed, (name, observed))
                    self.assertNotIn(secret_value, observed, (name, observed))
                client_message = failure.error["message"]
                self.assertEqual(client_message, "backend rejected the request")
                self.assertNotIn("SAFE_BEFORE", client_message, name)
                self.assertNotIn("SAFE_AFTER", client_message, name)
                self.assertNotIn(secret_value, client_message, name)
                self.assertNotIn(secret_value, report.logs, name)
                diagnostic = next(
                    line
                    for line in report.logs.splitlines()
                    if "backend stream error status=400" in line
                )
                self.assertIn("SAFE_BEFORE", diagnostic, name)
                self.assertIn("[REDACTED]", diagnostic, name)
                self.assertIn("SAFE_AFTER", diagnostic, name)
                self.assertNotIn(secret_value, diagnostic, name)
                self.assertEqual(
                    [line.event for line in report.lifecycle].count("terminal"),
                    1,
                )
                self.assertEqual(
                    [line.event for line in report.lifecycle].count("cleanup"),
                    1,
                )

    def test_v1211_http_version_normalization(self) -> None:
        for wire_value, expected in (
            ("HTTP/1.0", "HTTP/1.0"),
            ("HTTP/1.1", "HTTP/1.1"),
            ("HTTP/2", "HTTP/2"),
            ("HTTP/3", "unknown"),
        ):
            with self.subTest(http_version=wire_value):
                report = controlled_asgi_probe(http_version=wire_value)
                self.assertIsNone(report.raised)
                upstream = self._event_line(report.lifecycle, "upstream_headers")
                self.assertEqual(upstream.fields["http_version"], expected)

    def test_v1211_structured_backend_error_normalization_and_safe_logs(self) -> None:
        fake_secret = "sk-FAKE_STRUCTURED_SECRET_123456789"
        prompt_sentinel = "PROMPT_BODY_SENTINEL_MUST_NOT_LOG"
        tool_schema_sentinel = "TOOL_SCHEMA_SENTINEL_MUST_NOT_LOG"
        tool_input_sentinel = "TOOL_INPUT_SENTINEL_MUST_NOT_LOG"
        raw_sse_sentinel = "RAW_SSE_SENTINEL_MUST_NOT_LOG"
        clean_message = "Context window exceeded\nplease shorten input " + fake_secret
        payload = {
            "type": "server_error",
            "code": "context_length_exceeded",
            "message": clean_message,
            "raw_detail": raw_sse_sentinel,
        }
        scenario = structured_error_scenario(
            "direct-context-code-precedence",
            "error",
            payload,
        )
        scenario.stream_events[-1]["arbitrary_payload"] = raw_sse_sentinel
        tools = [
            {
                "name": "Read",
                "description": tool_schema_sentinel,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "payload": {
                            "type": "string",
                            "description": tool_schema_sentinel,
                        }
                    },
                },
            }
        ]
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_log_sentinel",
                        "name": "Read",
                        "input": {"payload": tool_input_sentinel},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_log_sentinel",
                        "content": prompt_sentinel,
                    }
                ],
            },
        ]
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(
                    stream=True,
                    model="gpt-fixture\r\nFORGED_LOG_LINE",
                    tools=tools,
                    messages=messages,
                    headers={"x-arbitrary-request": "ARBITRARY_REQUEST_HEADER"},
                )
                self.assertEqual(result.status, 200, result.text)
                failure = failure_lifecycle_report(
                    parse_typed_sse(result.body),
                    expected_error_type="invalid_request_error",
                )
                self.assertEqual(
                    failure.error["message"],
                    "backend context length exceeded",
                )
                self.assertLessEqual(len(failure.error["message"]), 200)
                self.assertNotIn("raw_detail", failure.error["message"])
                lines = lifecycle_for_response(shim, result)
                backend_error = self._event_line(lines, "backend_error")
                self.assertEqual(backend_error.fields["backend_type"], "server_error")
                self.assertEqual(
                    backend_error.fields["backend_code"],
                    "context_length_exceeded",
                )
                self.assertEqual(
                    backend_error.fields["anthropic_type"],
                    "invalid_request_error",
                )
                terminal = self._terminal_fields(lines)
                self.assertEqual(terminal["outcome"], "error")
                logs = shim.captured_stderr()
                for forbidden in (
                    fake_secret,
                    prompt_sentinel,
                    tool_schema_sentinel,
                    tool_input_sentinel,
                    raw_sse_sentinel,
                    "ARBITRARY_REQUEST_HEADER",
                ):
                    self.assertNotIn(forbidden, logs)
                self.assertNotIn("\r", logs)
                self.assertNotIn("\nFORGED_LOG_LINE", logs)
                for log_line in logs.splitlines():
                    self.assertNotRegex(
                        log_line,
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
                    )

        code_precedence = structured_error_scenario(
            "response-failed-code-precedence",
            "response.failed",
            {
                "type": "context_length_exceeded",
                "code": "server_error",
                "message": {"message": "Nested bounded message"},
                "full_object_sentinel": "DO_NOT_SERIALIZE_FULL_BACKEND_OBJECT",
            },
            prefix="text",
        )
        with MockResponsesServer(code_precedence) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                failure = failure_lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(failure.error["type"], "api_error")
                self.assertEqual(failure.error["message"], "backend server error")
                self.assertNotIn("full_object_sentinel", failure.error["message"])
                lines = lifecycle_for_response(shim, result)
                backend_error = self._event_line(lines, "backend_error")
                self.assertEqual(
                    backend_error.fields["backend_type"],
                    "context_length_exceeded",
                )
                self.assertEqual(backend_error.fields["backend_code"], "server_error")
                self.assertEqual(backend_error.fields["anthropic_type"], "api_error")

        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 502, result.text)
                error = result.json()["error"]
                self.assertEqual(error["type"], "invalid_request_error")
                self.assertEqual(
                    error["message"],
                    "backend context length exceeded",
                )
                lines = lifecycle_for_response(shim, result)
                self.assertEqual(self._terminal_fields(lines)["outcome"], "error")

        fallback = structured_error_scenario(
            "stable-fallback",
            "error",
            {"type": "unknown_backend_shape", "opaque": {"large": [1, 2, 3]}},
        )
        with MockResponsesServer(fallback) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                failure = failure_lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(failure.error["message"], "backend request failed")
                self.assertNotIn("opaque", failure.error["message"])
                lifecycle_for_response(shim, result)

        bounded = structured_error_scenario(
            "bounded-message",
            "error",
            {"type": "server_error", "message": "M" * 260},
        )
        with MockResponsesServer(bounded) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                failure = failure_lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(failure.error["message"], "backend server error")
                self.assertLessEqual(len(failure.error["message"]), 200)
                lifecycle_for_response(shim, result)

    def test_v1211_reflected_backend_prose_never_reaches_logs_or_client_errors(self) -> None:
        # INTENT: prove arbitrary, non-credential-shaped backend prose cannot reflect
        # prompt, system, tool-schema, tool-input, or opaque request material across
        # the three distinct backend-error normalization paths.
        # REASONING: every sentinel is both sent to the loopback backend and copied into
        # its fabricated error message. Absence from the complete stderr capture and the
        # complete downstream body therefore tests non-reflection, not regex redaction.
        # ASSUMES: all values are fabricated and the RealShim fixture's closed-proxy
        # contract keeps every request loopback-only and offline.
        prompt_sentinel = "FABRICATED_PROMPT_PROSE_Q7V4M9"
        system_sentinel = "FABRICATED_SYSTEM_PROSE_N2K8W5"
        tool_schema_sentinel = "FABRICATED_TOOL_SCHEMA_PROSE_R6H3C1"
        tool_input_sentinel = "FABRICATED_TOOL_INPUT_PROSE_B9T5J2"
        opaque_sentinel = "FABRICATED_OPAQUE_BLOB_X4P7L8"
        sentinels = (
            prompt_sentinel,
            system_sentinel,
            tool_schema_sentinel,
            tool_input_sentinel,
            opaque_sentinel,
        )
        reflected_message = "backend reflected request prose: " + " | ".join(sentinels)
        error_payload = {
            "type": "server_error",
            "code": "context_length_exceeded",
            "message": reflected_message,
        }

        http_error = structured_error_scenario(
            "reflected-http-400",
            "error",
            error_payload,
        )
        http_error.stream_status = 400
        http_error.stream_error_body = json.dumps(
            {"error": error_payload},
            separators=(",", ":"),
        ).encode("utf-8")
        inband_error = structured_error_scenario(
            "reflected-response-failed",
            "response.failed",
            error_payload,
        )
        accumulated_error = structured_error_scenario(
            "reflected-chatgpt-nonstream",
            "error",
            error_payload,
        )
        cases = (
            ("http-400", http_error, True, 200, "400"),
            ("inband-response-failed", inband_error, True, 200, "200"),
            ("chatgpt-inbound-nonstream", accumulated_error, False, 502, "200"),
        )

        for name, scenario, inbound_stream, client_status, upstream_status in cases:
            with self.subTest(path=name):
                request_body = {
                    "model": "gpt-fixture",
                    "max_tokens": 256,
                    "stream": inbound_stream,
                    "system": system_sentinel,
                    "tools": [
                        {
                            "name": "ReflectFixture",
                            "description": tool_schema_sentinel,
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "payload": {
                                        "type": "string",
                                        "description": tool_schema_sentinel,
                                    }
                                },
                            },
                        }
                    ],
                    "messages": [
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call_reflected_prose",
                                    "name": "ReflectFixture",
                                    "input": {"payload": tool_input_sentinel},
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call_reflected_prose",
                                    "content": f"{prompt_sentinel} {opaque_sentinel}",
                                }
                            ],
                        },
                    ],
                }
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_raw_messages(
                            json.dumps(
                                request_body,
                                separators=(",", ":"),
                            ).encode("utf-8")
                        )
                        self.assertEqual(result.status, client_status, (name, result.text))
                        if inbound_stream:
                            client_error = failure_lifecycle_report(
                                parse_typed_sse(result.body),
                                expected_error_type="invalid_request_error",
                            ).error
                        else:
                            response = result.json()
                            self.assertEqual(response.get("type"), "error", name)
                            client_error = response.get("error") or {}
                        self.assertEqual(
                            client_error.get("type"),
                            "invalid_request_error",
                            name,
                        )
                        self.assertIsInstance(client_error.get("message"), str, name)

                        lines = lifecycle_for_response(shim, result)
                        assert_lifecycle_log_contract(lines)
                        events = [line.event for line in lines]
                        upstream = self._event_line(lines, "upstream_headers")
                        backend_error = self._event_line(lines, "backend_error")
                        terminal = self._terminal_fields(lines)
                        self.assertEqual(upstream.fields["status"], upstream_status, name)
                        self.assertEqual(
                            backend_error.fields["backend_type"],
                            "server_error",
                            name,
                        )
                        self.assertEqual(
                            backend_error.fields["backend_code"],
                            "context_length_exceeded",
                            name,
                        )
                        self.assertEqual(
                            backend_error.fields["anthropic_type"],
                            "invalid_request_error",
                            name,
                        )
                        self.assertEqual(terminal["outcome"], "error", name)
                        self.assertEqual(terminal["attempts"], "1", name)
                        self.assertEqual(terminal["retries"], "0", name)
                        self.assertEqual(events.count("terminal"), 1, name)
                        self.assertEqual(events.count("cleanup"), 1, name)
                        self.assertEqual(events[-2:], ["terminal", "cleanup"], name)

                        logs = shim.captured_stderr()
                        for sentinel in sentinels:
                            self.assertNotIn(sentinel, logs, (name, "stderr"))
                            self.assertNotIn(sentinel, result.text, (name, "client"))
                        backend_request = json.dumps(
                            backend.responses_requests[0].body,
                            separators=(",", ":"),
                        )
                        for sentinel in sentinels:
                            self.assertIn(sentinel, backend_request, (name, "request"))
                        self.assertIs(
                            backend.responses_requests[0].body.get("stream"),
                            True,
                            name,
                        )
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=1, oauth=0)

    def test_v1211_same_turn_terminal_send_disconnect_prefers_completed_send(self) -> None:
        report = controlled_asgi_probe(send_action="same_turn_terminal_disconnect")
        self.assertIsNone(report.raised)
        self.assertFalse(report.cancelled)
        # Harness instrumentation delegates to production asyncio.wait unchanged and
        # records its actual FIRST_COMPLETED return. Two done children and zero pending
        # children prove operation_task and disconnect_task were in the same observed
        # scheduler turn; the test does not reproduce the winner-selection condition.
        self.assertEqual(report.terminal_tie_wait_done_counts, [2])
        self.assertEqual(report.terminal_tie_wait_pending_counts, [0])
        self.assertEqual(report.terminal_tie_wait_used_first_completed, [True])
        self.assertTrue(report.terminal_tie_children_done)

        events = [line.event for line in report.lifecycle]
        terminal = self._terminal_fields(report.lifecycle)
        cleanup = self._event_line(report.lifecycle, "cleanup").fields
        self.assertEqual(events.count("disconnect"), 1)
        self.assertEqual(events.count("terminal"), 1)
        self.assertEqual(events.count("cleanup"), 1)
        self.assertEqual(terminal["outcome"], "success")
        self.assertEqual(terminal["terminal_frame_send"], "send_completed")
        self.assertEqual(terminal["body_close_send"], "skipped_disconnect")
        self.assertEqual(terminal["disconnect"], "True")
        self.assertEqual(terminal["disconnect_phase"], "disconnect_watcher")
        self.assertEqual(cleanup["status"], "completed")
        self.assertEqual(report.upstream_calls, 1)
        self.assertEqual(report.stream_close_calls, 1)
        self.assertEqual(report.pending_task_count, 0)
        terminal_messages = [
            message
            for message in report.messages
            if message.get("type") == "http.response.body"
            and b"event: message_stop" in message.get("body", b"")
        ]
        self.assertEqual(len(terminal_messages), 1)

    def test_v1211_response_start_owns_stream_and_watcher_before_send(self) -> None:
        cases = (
            ("write-failure", "fail_response_start", False, "error", 0),
            ("observed-disconnect", "disconnect_response_start", False, "disconnect", 1),
            ("outer-cancellation", "cancel_response_start", False, "error", 0),
            ("write-failure-close-failure", "fail_response_start", True, "error", 0),
            ("disconnect-close-failure", "disconnect_response_start", True, "disconnect", 1),
            ("cancellation-close-failure", "cancel_response_start", True, "error", 0),
        )
        for name, send_action, close_failure, outcome, disconnects in cases:
            with self.subTest(case=name):
                report = controlled_asgi_probe(
                    send_action=send_action,
                    cleanup_failure=close_failure,
                )
                events = [line.event for line in report.lifecycle]
                terminal = self._terminal_fields(report.lifecycle)
                cleanup = self._event_line(report.lifecycle, "cleanup").fields
                self.assertEqual(report.stream_close_calls, 1, name)
                self.assertEqual(report.stream_close_attempts, [1], name)
                self.assertEqual(report.close_after_cleanup, [False], name)
                self.assertEqual(report.watcher_settle_after_cleanup, [False], name)
                self.assertEqual(report.pending_task_count, 0, name)
                self.assertEqual(events.count("disconnect"), disconnects, name)
                self.assertEqual(events.count("terminal"), 1, name)
                self.assertEqual(events.count("cleanup"), 1, name)
                self.assertEqual(events[-2:], ["terminal", "cleanup"], name)
                self.assertEqual(terminal["outcome"], outcome, name)
                self.assertEqual(
                    cleanup["status"],
                    "failed" if close_failure else "completed",
                    name,
                )
                self.assertEqual(
                    cleanup["error"], "OSError" if close_failure else "-", name
                )
                self.assertEqual(
                    cleanup["failures"], "1" if close_failure else "0", name
                )
                self.assertEqual(report.cancelled, send_action == "cancel_response_start")

    def test_v1211_response_start_write_failure_has_owned_downstream_phase(self) -> None:
        # INTENT: exercise production app() ownership when the ASGI server rejects the
        # first downstream header write after successful upstream response headers.
        # REASONING: stream and JSON responses have distinct send sites, so the smallest
        # two-case matrix prevents either path from inheriting the stale upstream phase.
        # ASSUMES: injected OSError remains caller-visible while app() alone owns stream
        # closure, watcher settlement, and exactly-once lifecycle finalization.
        cases = (
            ("stream", True, 1),
            ("json", False, 0),
        )
        for name, stream, expected_stream_closes in cases:
            with self.subTest(path=name):
                report = controlled_asgi_probe(
                    stream=stream,
                    send_action="fail_response_start",
                )
                events = [line.event for line in report.lifecycle]
                terminal = self._terminal_fields(report.lifecycle)
                cleanup = self._event_line(report.lifecycle, "cleanup").fields
                self.assertEqual(report.raised, "OSError", name)
                self.assertFalse(report.cancelled, name)
                self.assertEqual(report.upstream_calls, 1, name)
                self.assertEqual(
                    report.stream_close_calls,
                    expected_stream_closes,
                    name,
                )
                self.assertEqual(
                    report.stream_close_attempts,
                    [1] if stream else [],
                    name,
                )
                self.assertEqual(report.pending_task_count, 0, name)
                self.assertEqual(report.watcher_settle_after_cleanup, [False], name)
                self.assertEqual(events.count("upstream_headers"), 1, name)
                self.assertLess(
                    events.index("upstream_headers"),
                    events.index("terminal"),
                    name,
                )
                self.assertEqual(events.count("disconnect"), 0, name)
                self.assertEqual(events.count("terminal"), 1, name)
                self.assertEqual(events.count("cleanup"), 1, name)
                self.assertEqual(events[-2:], ["terminal", "cleanup"], name)
                self.assertEqual(terminal["outcome"], "error", name)
                self.assertEqual(
                    terminal["failure_phase"],
                    "downstream_response_start",
                    name,
                )
                self.assertEqual(cleanup["status"], "completed", name)
                self.assertEqual(cleanup["error"], "-", name)
                self.assertEqual(cleanup["failures"], "0", name)

    def test_v1211_json_response_start_failure_preserves_prior_backend_cause(self) -> None:
        # INTENT: preserve the first causal backend-rejection phase when a later JSON
        # response-start write also fails.
        # REASONING: downstream_response_start owns header-write failures only when no
        # earlier causal error has already fixed failure_phase.
        scenario = structured_error_scenario(
            "json-backend-error-before-response-start-failure",
            "error",
            {
                "type": "server_error",
                "code": "context_length_exceeded",
                "message": "fabricated backend rejection",
            },
        )
        report = controlled_asgi_probe(
            scenario=scenario,
            stream=False,
            response_status=400,
            send_action="fail_response_start",
        )
        events = [line.event for line in report.lifecycle]
        terminal = self._terminal_fields(report.lifecycle)
        self.assertEqual(report.raised, "OSError")
        self.assertFalse(report.cancelled)
        self.assertEqual(report.upstream_calls, 1)
        self.assertEqual(report.stream_close_calls, 0)
        self.assertEqual(report.pending_task_count, 0)
        self.assertEqual(events.count("upstream_headers"), 1)
        self.assertEqual(events.count("backend_error"), 1)
        self.assertLess(events.index("upstream_headers"), events.index("backend_error"))
        self.assertLess(events.index("backend_error"), events.index("terminal"))
        self.assertEqual(events.count("disconnect"), 0)
        self.assertEqual(events.count("terminal"), 1)
        self.assertEqual(events.count("cleanup"), 1)
        self.assertEqual(events[-2:], ["terminal", "cleanup"])
        self.assertEqual(terminal["outcome"], "error")
        self.assertEqual(terminal["failure_phase"], "upstream_headers")

    def test_v1211_stream_response_start_failure_preserves_prior_backend_cause(self) -> None:
        # INTENT: drive production app() through a real non-2xx streamed backend
        # response whose downstream SSE response-start write then fails.
        # REASONING: upstream headers already prove a backend HTTP rejection before the
        # shim attempts downstream headers, so that first causal phase must survive the
        # later OSError. A successful-send companion pins the existing deferred body
        # parse, ensuring the repair does not sacrifice structured type/code enrichment.
        # ASSUMES: the controlled harness injects only the upstream response and ASGI
        # send failure; status recognition, lifecycle ordering, normalization, and
        # centralized finalization all execute through production code.
        scenario = backend_status_scenario(
            "stream-backend-error-before-response-start-failure",
            400,
        )
        scenario.stream_error_body = json.dumps(
            {
                "error": {
                    "type": "server_error",
                    "code": "context_length_exceeded",
                    "message": "fabricated backend rejection",
                }
            },
            separators=(",", ":"),
        ).encode("utf-8")

        failed_start = controlled_asgi_probe(
            scenario=scenario,
            stream=True,
            response_status=400,
            send_action="fail_response_start",
        )
        failed_events = [line.event for line in failed_start.lifecycle]
        failed_terminal = self._terminal_fields(failed_start.lifecycle)
        failed_cleanup = self._event_line(failed_start.lifecycle, "cleanup").fields
        self.assertEqual(failed_start.raised, "OSError")
        self.assertFalse(failed_start.cancelled)
        self.assertEqual(failed_start.upstream_calls, 1)
        self.assertEqual(failed_start.stream_close_calls, 1)
        self.assertEqual(failed_start.stream_close_attempts, [1])
        self.assertEqual(failed_start.pending_task_count, 0)
        self.assertEqual(failed_events.count("upstream_headers"), 1)
        self.assertEqual(failed_events.count("disconnect"), 0)
        self.assertEqual(failed_events.count("terminal"), 1)
        self.assertEqual(failed_events.count("cleanup"), 1)
        self.assertEqual(failed_events[-2:], ["terminal", "cleanup"])
        self.assertEqual(failed_terminal["outcome"], "error")
        self.assertEqual(failed_terminal["attempts"], "1")
        self.assertEqual(failed_terminal["retries"], "0")
        self.assertEqual(failed_terminal["failure_phase"], "upstream_headers")
        self.assertEqual(failed_cleanup["status"], "completed")
        self.assertEqual(failed_cleanup["failures"], "0")

        enriched = controlled_asgi_probe(
            scenario=scenario,
            stream=True,
            response_status=400,
        )
        enriched_events = [line.event for line in enriched.lifecycle]
        enriched_backend = self._event_line(
            enriched.lifecycle,
            "backend_error",
        ).fields
        enriched_terminal = self._terminal_fields(enriched.lifecycle)
        self.assertIsNone(enriched.raised)
        self.assertFalse(enriched.cancelled)
        self.assertEqual(enriched.upstream_calls, 1)
        self.assertEqual(enriched.stream_close_calls, 1)
        self.assertEqual(enriched.pending_task_count, 0)
        self.assertEqual(enriched_events.count("backend_error"), 1)
        self.assertLess(
            enriched_events.index("upstream_headers"),
            enriched_events.index("backend_error"),
        )
        self.assertEqual(enriched_backend["backend_type"], "server_error")
        self.assertEqual(
            enriched_backend["backend_code"],
            "context_length_exceeded",
        )
        self.assertEqual(
            enriched_backend["anthropic_type"],
            "invalid_request_error",
        )
        self.assertEqual(enriched_backend["failure_phase"], "upstream_headers")
        self.assertEqual(enriched_terminal["outcome"], "error")
        self.assertEqual(enriched_terminal["failure_phase"], "upstream_headers")
        self.assertEqual(enriched_events.count("terminal"), 1)
        self.assertEqual(enriched_events.count("cleanup"), 1)
        self.assertEqual(enriched_events[-2:], ["terminal", "cleanup"])

    def test_v1211_auth_error_send_failure_still_settles_watcher(self) -> None:
        report = controlled_asgi_probe(
            stream=False,
            auth_store_unavailable=True,
            send_action="fail_response_start",
        )
        events = [line.event for line in report.lifecycle]
        terminal = self._terminal_fields(report.lifecycle)
        cleanup = self._event_line(report.lifecycle, "cleanup").fields
        self.assertEqual(report.raised, "OSError")
        self.assertFalse(report.cancelled)
        self.assertEqual(report.upstream_calls, 0)
        self.assertEqual(report.stream_close_calls, 0)
        self.assertEqual(report.pending_task_count, 0)
        self.assertEqual(report.watcher_settle_after_cleanup, [False])
        self.assertEqual(events.count("terminal"), 1)
        self.assertEqual(events.count("cleanup"), 1)
        self.assertEqual(events[-2:], ["terminal", "cleanup"])
        self.assertEqual(terminal["outcome"], "error")
        self.assertEqual(terminal["failure_phase"], "backend_authentication")
        self.assertEqual(cleanup["status"], "completed")
        self.assertEqual(cleanup["error"], "-")
        self.assertEqual(cleanup["failures"], "0")

    def test_v1211_attempt_local_cleanup_failure_is_monotonic(self) -> None:
        cases = (
            (
                "eligible-status-retry",
                {"attempt_outcomes": [503, 200], "close_fail_attempts": {1}},
                2,
                [1, 2],
                "success",
                0,
            ),
            (
                "transport-retry",
                {"attempt_outcomes": ["transport", 200], "close_fail_attempts": {1}},
                2,
                [1, 2],
                "success",
                0,
            ),
            (
                "lazy-401-refresh",
                {
                    "attempt_outcomes": [401, 200],
                    "close_fail_attempts": {1},
                    "lazy_401_refresh": True,
                },
                2,
                [1, 2],
                "success",
                0,
            ),
            (
                "disconnect-during-enter",
                {
                    "disconnect_during_enter": True,
                    "close_fail_attempts": {1},
                },
                1,
                [1],
                "disconnect",
                1,
            ),
        )
        for name, kwargs, close_calls, close_attempts, outcome, disconnects in cases:
            with self.subTest(case=name):
                report = controlled_asgi_probe(**kwargs)
                events = [line.event for line in report.lifecycle]
                terminal = self._terminal_fields(report.lifecycle)
                cleanup = self._event_line(report.lifecycle, "cleanup").fields
                self.assertEqual(report.stream_close_calls, close_calls, name)
                self.assertEqual(report.stream_close_attempts, close_attempts, name)
                self.assertTrue(all(not value for value in report.close_after_cleanup), name)
                self.assertEqual(report.pending_task_count, 0, name)
                self.assertEqual(events.count("disconnect"), disconnects, name)
                self.assertEqual(events.count("terminal"), 1, name)
                self.assertEqual(events.count("cleanup"), 1, name)
                self.assertEqual(events[-2:], ["terminal", "cleanup"], name)
                self.assertEqual(terminal["outcome"], outcome, name)
                self.assertEqual(cleanup["status"], "failed", name)
                self.assertEqual(cleanup["error"], "OSError", name)
                self.assertEqual(cleanup["failures"], "1", name)
                self.assertEqual(report.watcher_settle_after_cleanup, [False], name)

    def test_v1211_malformed_json_shapes_return_correlated_400_without_upstream(self) -> None:
        cases = (
            ("root-array", b"[]"),
            ("root-null", b"null"),
            ("messages-null", b'{"messages":null}'),
            ("messages-item-null", b'{"messages":[null]}'),
        )
        for name, raw_body in cases:
            with self.subTest(case=name):
                report = controlled_asgi_probe(raw_request_body=raw_body)
                self.assertIsNone(report.raised, name)
                self.assertFalse(report.cancelled, name)
                self.assertEqual(report.upstream_calls, 0, name)
                starts = [
                    message
                    for message in report.messages
                    if message.get("type") == "http.response.start"
                ]
                self.assertEqual(len(starts), 1, name)
                self.assertEqual(starts[0].get("status"), 400, name)
                response_headers = dict(starts[0].get("headers", []))
                request_id = response_headers[b"x-daaf-request-id"].decode("ascii")
                self.assertEqual({line.req_id for line in report.lifecycle}, {request_id}, name)
                body = b"".join(
                    message.get("body", b"")
                    for message in report.messages
                    if message.get("type") == "http.response.body"
                )
                response = json.loads(body.decode("utf-8"))
                self.assertEqual(response.get("type"), "error", name)
                self.assertEqual(
                    (response.get("error") or {}).get("type"),
                    "invalid_request_error",
                    name,
                )
                events = [line.event for line in report.lifecycle]
                self.assertEqual(events.count("terminal"), 1, name)
                self.assertEqual(events.count("cleanup"), 1, name)
                self.assertNotIn("upstream_attempt", events, name)
                terminal = self._terminal_fields(report.lifecycle)
                self.assertEqual(terminal["attempts"], "0", name)
                self.assertEqual(terminal["retries"], "0", name)
                self.assertEqual(terminal["failure_phase"], "request_validation", name)
                self.assertEqual(terminal["terminal_frame_send"], "send_completed", name)
                self.assertEqual(terminal["body_close_send"], "send_completed", name)

    def test_v1211_max_tokens_rejects_nonpositive_noninteger_and_nonfinite_values(self) -> None:
        # INTENT: pin the Anthropic max_tokens boundary to finite positive JSON integers
        # before request translation or any backend attempt can occur.
        # REASONING: raw bytes preserve the overflowing 1e309 literal independently of
        # Python serializer policy; the remaining values cover explicit null, bool-as-int,
        # fractional, negative, and zero edges through the same production app() path.
        # ASSUMES: malformed request values receive one static, non-reflective JSON 400
        # correlated to the same request lifecycle and never enter retry accounting.
        invalid_cases = (
            ("explicit-null", b"null"),
            ("boolean", b"true"),
            ("fractional", b"16.5"),
            ("negative", b"-1"),
            ("zero", b"0"),
            ("overflowing-literal", b"1e309"),
        )
        for name, literal in invalid_cases:
            with self.subTest(case=name):
                raw_body = (
                    b'{"model":"gpt-fixture","max_tokens":'
                    + literal
                    + b',"stream":false,"messages":[]}'
                )
                report = controlled_asgi_probe(raw_request_body=raw_body)
                self.assertIsNone(report.raised, name)
                self.assertFalse(report.cancelled, name)
                self.assertEqual(report.upstream_calls, 0, name)
                self.assertEqual(report.stream_close_calls, 0, name)
                self.assertEqual(report.pending_task_count, 0, name)

                starts = [
                    message
                    for message in report.messages
                    if message.get("type") == "http.response.start"
                ]
                self.assertEqual(len(starts), 1, name)
                self.assertEqual(starts[0].get("status"), 400, name)
                response_headers = dict(starts[0].get("headers", []))
                request_id = response_headers[b"x-daaf-request-id"].decode("ascii")
                self.assertEqual(
                    {line.req_id for line in report.lifecycle},
                    {request_id},
                    name,
                )
                body = b"".join(
                    message.get("body", b"")
                    for message in report.messages
                    if message.get("type") == "http.response.body"
                )
                self.assertEqual(
                    json.loads(body.decode("utf-8")),
                    {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "message": "invalid request structure",
                        },
                    },
                    name,
                )

                events = [line.event for line in report.lifecycle]
                terminal = self._terminal_fields(report.lifecycle)
                cleanup = self._event_line(report.lifecycle, "cleanup").fields
                self.assertNotIn("upstream_attempt", events, name)
                self.assertEqual(events.count("terminal"), 1, name)
                self.assertEqual(events.count("cleanup"), 1, name)
                self.assertEqual(events[-2:], ["terminal", "cleanup"], name)
                self.assertEqual(terminal["outcome"], "error", name)
                self.assertEqual(terminal["attempts"], "0", name)
                self.assertEqual(terminal["retries"], "0", name)
                self.assertEqual(terminal["failure_phase"], "request_validation", name)
                self.assertEqual(terminal["terminal_frame_send"], "send_completed", name)
                self.assertEqual(terminal["body_close_send"], "send_completed", name)
                self.assertEqual(cleanup["status"], "completed", name)
                self.assertEqual(cleanup["failures"], "0", name)

        # Omission remains a distinct compatibility case: unlike explicit JSON null,
        # an absent max_tokens key is accepted and no outbound ceiling is synthesized.
        omitted = controlled_asgi_probe(
            stream=False,
            raw_request_body=(
                b'{"model":"gpt-fixture","stream":false,"messages":[]}'
            ),
        )
        omitted_events = [line.event for line in omitted.lifecycle]
        omitted_terminal = self._terminal_fields(omitted.lifecycle)
        omitted_starts = [
            message
            for message in omitted.messages
            if message.get("type") == "http.response.start"
        ]
        self.assertIsNone(omitted.raised)
        self.assertFalse(omitted.cancelled)
        self.assertEqual(omitted.upstream_calls, 1)
        self.assertEqual(omitted.stream_close_calls, 0)
        self.assertEqual(omitted.pending_task_count, 0)
        self.assertEqual(len(omitted_starts), 1)
        self.assertEqual(omitted_starts[0].get("status"), 200)
        omitted_headers = dict(omitted_starts[0].get("headers", []))
        omitted_request_id = omitted_headers[b"x-daaf-request-id"].decode("ascii")
        self.assertEqual(
            {line.req_id for line in omitted.lifecycle},
            {omitted_request_id},
        )
        self.assertEqual(omitted_events.count("upstream_attempt"), 1)
        self.assertEqual(omitted_events.count("terminal"), 1)
        self.assertEqual(omitted_events.count("cleanup"), 1)
        self.assertEqual(omitted_events[-2:], ["terminal", "cleanup"])
        self.assertEqual(omitted_terminal["outcome"], "success")
        self.assertEqual(omitted_terminal["attempts"], "1")
        self.assertEqual(omitted_terminal["retries"], "0")
        self.assertEqual(omitted_terminal["failure_phase"], "-")

        # A positive integer below the provider's outbound minimum remains compatible:
        # production accepts it and preserves the established clamp to 16.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_raw_messages(
                    b'{"model":"gpt-fixture","max_tokens":1,'
                    b'"stream":false,"messages":[]}'
                )
                self.assertEqual(result.status, 200, result.text)
                lines = lifecycle_for_response(shim, result)
                terminal = self._terminal_fields(lines)
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["attempts"], "1")
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(
                    backend.responses_requests[0].body.get("max_output_tokens"),
                    16,
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1, oauth=0)

    def test_v1211_failure_phase_identifies_parse_translation_and_auth_boundaries(self) -> None:
        invalid_json = controlled_asgi_probe(raw_request_body=b"{invalid-json")
        self.assertIsNone(invalid_json.raised)
        self.assertEqual(
            self._terminal_fields(invalid_json.lifecycle)["failure_phase"],
            "request_parse",
        )
        self.assertEqual(invalid_json.upstream_calls, 0)

        translation = controlled_asgi_probe(translation_failure=True)
        self.assertEqual(translation.raised, "TypeError")
        self.assertEqual(
            self._terminal_fields(translation.lifecycle)["failure_phase"],
            "request_translation",
        )
        self.assertEqual(translation.upstream_calls, 0)

        authentication = controlled_asgi_probe(
            stream=False,
            auth_store_unavailable=True,
        )
        self.assertIsNone(authentication.raised)
        self.assertEqual(
            self._terminal_fields(authentication.lifecycle)["failure_phase"],
            "backend_authentication",
        )
        self.assertEqual(authentication.upstream_calls, 0)

        lazy_authentication = controlled_asgi_probe(
            attempt_outcomes=[401],
            lazy_401_refresh_failure=True,
        )
        self.assertIsNone(lazy_authentication.raised)
        lazy_terminal = self._terminal_fields(lazy_authentication.lifecycle)
        self.assertEqual(lazy_terminal["failure_phase"], "backend_authentication")
        self.assertEqual(lazy_terminal["attempts"], "1")
        self.assertEqual(lazy_terminal["retries"], "1")
        self.assertEqual(lazy_authentication.upstream_calls, 1)

    def test_v1211_disconnect_records_only_observed_asgi_evidence(self) -> None:
        body_read = controlled_asgi_probe(body_read_disconnect=True)
        body_disconnect = self._event_line(body_read.lifecycle, "disconnect").fields
        self.assertEqual(body_disconnect["observed_phase"], "body_read")
        self.assertEqual(
            urllib.parse.unquote(body_disconnect["detail"]),
            "ASGI http.disconnect observed",
        )
        body_terminal = self._terminal_fields(body_read.lifecycle)
        self.assertEqual(body_terminal["attempts"], "0")
        self.assertEqual(body_terminal["retries"], "0")
        self.assertEqual(body_read.upstream_calls, 0)
        self.assertNotIn("upstream operation cancelled", body_read.logs)

        post_terminal = controlled_asgi_probe(send_action="disconnect_body_close")
        post_disconnect = self._event_line(post_terminal.lifecycle, "disconnect").fields
        self.assertEqual(
            urllib.parse.unquote(post_disconnect["detail"]),
            "ASGI http.disconnect observed",
        )
        post_terminal_fields = self._terminal_fields(post_terminal.lifecycle)
        self.assertEqual(post_terminal_fields["outcome"], "success")
        self.assertEqual(post_terminal_fields["terminal_frame_send"], "send_completed")
        self.assertEqual(post_terminal_fields["body_close_send"], "skipped_disconnect")
        self.assertNotIn("upstream operation cancelled", post_terminal.logs)

        outer_cancel = controlled_asgi_probe(send_action="cancel_response_start")
        outer_events = [line.event for line in outer_cancel.lifecycle]
        self.assertTrue(outer_cancel.cancelled)
        self.assertEqual(outer_events.count("disconnect"), 0)
        self.assertEqual(outer_events.count("terminal"), 1)
        self.assertEqual(outer_events.count("cleanup"), 1)
        self.assertEqual(self._terminal_fields(outer_cancel.lifecycle)["outcome"], "error")

    def test_v1211_terminal_send_outcome_matrix_and_first_causal_outcome(self) -> None:
        backend_failure = structured_error_scenario(
            "backend-error-disconnect",
            "error",
            {"type": "server_error", "message": "backend failed first"},
        )
        cases = (
            ("success", {}, "success", "send_completed", "send_completed", 0),
            (
                "terminal-write-failed",
                {"send_action": "fail_terminal"},
                "error",
                "write_failed",
                "not_attempted",
                0,
            ),
            (
                "body-close-write-failed",
                {"send_action": "fail_body_close"},
                "success",
                "send_completed",
                "write_failed",
                0,
            ),
            (
                "response-start-cancelled",
                {"send_action": "cancel_response_start"},
                "error",
                "not_attempted",
                "not_attempted",
                0,
            ),
            (
                "terminal-attempt-cancelled",
                {"send_action": "cancel_terminal"},
                "error",
                "attempted",
                "not_attempted",
                0,
            ),
            (
                "body-close-attempt-cancelled",
                {"send_action": "cancel_body_close"},
                "success",
                "send_completed",
                "attempted",
                0,
            ),
            (
                "pure-client-disconnect",
                {"pure_disconnect": True},
                "disconnect",
                "skipped_disconnect",
                "skipped_disconnect",
                1,
            ),
            (
                "body-read-disconnect",
                {"body_read_disconnect": True},
                "disconnect",
                "skipped_disconnect",
                "skipped_disconnect",
                1,
            ),
            (
                "post-message-stop-disconnect",
                {"send_action": "disconnect_body_close"},
                "success",
                "send_completed",
                "skipped_disconnect",
                1,
            ),
            (
                "backend-error-then-disconnect",
                {
                    "scenario": backend_failure,
                    "send_action": "disconnect_terminal",
                },
                "error",
                "skipped_disconnect",
                "skipped_disconnect",
                1,
            ),
            (
                "parse-error",
                {"raw_request_body": b"{invalid-json"},
                "error",
                "send_completed",
                "send_completed",
                0,
            ),
            (
                "invalid-request-shape",
                {"invalid_request_shape": True},
                "error",
                "send_completed",
                "send_completed",
                0,
            ),
            (
                "cleanup-failure-after-success",
                {"cleanup_failure": True},
                "success",
                "send_completed",
                "send_completed",
                0,
            ),
            (
                "cleanup-failure-after-error",
                {"scenario": backend_failure, "cleanup_failure": True},
                "error",
                "send_completed",
                "send_completed",
                0,
            ),
        )
        terminal_states = set()
        body_states = set()
        allowed_states = {
            "not_attempted",
            "attempted",
            "send_completed",
            "skipped_disconnect",
            "write_failed",
        }
        for name, kwargs, outcome, terminal_state, body_state, disconnects in cases:
            with self.subTest(case=name):
                report = controlled_asgi_probe(**kwargs)
                terminal = self._terminal_fields(report.lifecycle)
                cleanup = self._event_line(report.lifecycle, "cleanup").fields
                events = [line.event for line in report.lifecycle]
                self.assertEqual(events.count("terminal"), 1, name)
                self.assertEqual(events.count("cleanup"), 1, name)
                self.assertEqual(events.count("disconnect"), disconnects, name)
                if disconnects:
                    disconnect = self._event_line(report.lifecycle, "disconnect")
                    self.assertEqual(
                        urllib.parse.unquote(disconnect.fields["detail"]),
                        "ASGI http.disconnect observed",
                        name,
                    )
                    self.assertNotIn("upstream operation cancelled", report.logs, name)
                self.assertEqual(terminal["outcome"], outcome, name)
                self.assertEqual(
                    terminal["terminal_frame_send"],
                    terminal_state,
                    name,
                )
                self.assertEqual(terminal["body_close_send"], body_state, name)
                terminal_states.add(terminal["terminal_frame_send"])
                body_states.add(terminal["body_close_send"])
                if name in {
                    "cleanup-failure-after-success",
                    "cleanup-failure-after-error",
                }:
                    self.assertEqual(cleanup["status"], "failed")
                    self.assertEqual(cleanup["error"], "OSError")
                else:
                    self.assertIn(cleanup["status"], {"completed", "not_started"})
                if name == "backend-error-then-disconnect":
                    self.assertIn("backend_error", events)
                    self.assertLess(
                        events.index("backend_error"),
                        events.index("disconnect"),
                    )
                if name == "invalid-request-shape":
                    self.assertIsNone(report.raised)
                    self.assertEqual(terminal["failure_phase"], "request_validation")
        self.assertEqual(terminal_states, allowed_states)
        self.assertEqual(body_states, allowed_states)

    def test_v1211_prestart_and_poststart_failures_have_single_accounting(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, model="claude-fable-5")
                self.assertEqual(result.status, 400, result.text)
                lines = lifecycle_for_response(shim, result)
                terminal = self._terminal_fields(lines)
                self.assertEqual(terminal["outcome"], "error")
                self.assertEqual(terminal["attempts"], "0")
                self.assertEqual(terminal["terminal_frame_send"], "send_completed")
                self.assertEqual(terminal["body_close_send"], "send_completed")
                self.assertNotIn("upstream_attempt", [line.event for line in lines])
                backend.assert_request_counts(responses=0, oauth=0)

        scenario = abrupt_eof_scenario("text")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                failure_lifecycle_report(parse_typed_sse(result.body))
                lines = lifecycle_for_response(shim, result)
                terminal = self._terminal_fields(lines)
                self.assertEqual(terminal["outcome"], "error")
                self.assertEqual(terminal["attempts"], "1")
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(terminal["terminal_frame_send"], "send_completed")
                self.assertEqual(terminal["body_close_send"], "send_completed")
                self.assertIn("backend_error", [line.event for line in lines])
                backend.assert_request_counts(responses=1, oauth=0)

    def test_v1211_auth_error_has_one_terminal_and_cleanup(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                shim.remove_auth_store()
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 401, result.text)
                self.assertEqual(result.json()["error"]["type"], "authentication_error")
                lines = lifecycle_for_response(shim, result)
                terminal = self._terminal_fields(lines)
                self.assertEqual(terminal["outcome"], "error")
                self.assertEqual(terminal["attempts"], "0")
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(terminal["failure_phase"], "backend_authentication")
                self.assertEqual(
                    [line.event for line in lines].count("terminal"),
                    1,
                )
                self.assertEqual(
                    [line.event for line in lines].count("cleanup"),
                    1,
                )
                backend.assert_request_counts(responses=0, oauth=0)


if __name__ == "__main__":
    unittest.main()
