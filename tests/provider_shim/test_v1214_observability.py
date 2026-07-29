"""Deterministic contracts for the v1.2.14 A1 observability/classification work.

Covers the four turnkey test families handed off from Dispatch A1 (shim frozen):

1. R1 unknown-wire counting: an unknown SSE event type and an unmodeled
   ``output_item`` type are counted on the terminal record while the turn still
   completes cleanly downstream; a clean stream reports zero.
2. R1 ``obfuscation`` tolerance: a known-but-unmodeled ``obfuscation`` field on
   ``arguments.delta`` is silently accepted (no unknown_events, no failure).
3. R2 unified code-driven classification: each recognized backend code maps to its
   Anthropic error type across the four captured error-envelope shapes; the two
   status-only rows and the adjudicated bare-503 -> api_error behavior are pinned.
4. D5 request-shape diagnosis line: an invalid_request_error emits exactly one
   ``event=request_shape`` line of key NAMES only, never request values.

Retry expectations honor the A1 build: retries are still RETRY_STATUSES-gated
(A2 lands the classification-driven gating later), so a retryable 5xx is attempted
MAX_RETRIES+1 = 4 times and a 4xx is attempted once.
"""

from __future__ import annotations

import json
import unittest
import urllib.parse

from ._loopback_harness import (
    READ_TOOL,
    MockResponsesServer,
    RealShim,
    backend_status_scenario,
    failure_lifecycle_report,
    full_response_scenario,
    lifecycle_for_response,
    lifecycle_report,
    obfuscation_tool_scenario,
    parse_typed_sse,
    structured_error_scenario,
    unknown_wire_scenario,
)


class ProviderShimV1214ObservabilityTests(unittest.TestCase):
    maxDiff = 12000

    # --- shared lifecycle-line helpers (mirror the stream-hardening suite) ---

    def _event_line(self, lines: list[object], event: str) -> object:
        matches = [line for line in lines if line.event == event]
        self.assertEqual(len(matches), 1, (event, [line.raw for line in lines]))
        return matches[0]

    def _terminal_fields(self, lines: list[object]) -> dict[str, str]:
        return self._event_line(lines, "terminal").fields

    def _inband_error(
        self,
        name: str,
        error_payload: dict[str, object],
        expected_type: str,
    ) -> tuple[object, dict[str, str]]:
        """Drive one in-band SSE ``error`` event through real classification.

        An in-band error carries no HTTP status, so classification is code/type
        driven; it also arrives after ``message_start`` and is therefore never
        retried (responses == 1).
        """

        scenario = structured_error_scenario(name, "error", error_payload)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                failure = failure_lifecycle_report(
                    parse_typed_sse(result.body), expected_type
                )
                lines = lifecycle_for_response(shim, result)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)
                return failure, self._terminal_fields(lines)

    def _http_failure(
        self,
        scenario: object,
        expected_type: str,
        expected_requests: int,
    ) -> tuple[object, dict[str, str]]:
        """Drive one pre-content backend HTTP failure through status classification."""

        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                failure = failure_lifecycle_report(
                    parse_typed_sse(result.body), expected_type
                )
                lines = lifecycle_for_response(shim, result)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=expected_requests)
                return failure, self._terminal_fields(lines)

    # --- Group 1: R1 unknown-wire counting ---

    def test_unknown_event_and_item_counted_while_turn_completes(self) -> None:
        # One unknown SSE event type (response.audio.delta) and one unmodeled
        # output_item.added type (web_search_call). The downstream Anthropic stream
        # must still be a well-formed success (single text block), and the terminal
        # record must surface exactly one unknown event and one unknown item.
        scenario = unknown_wire_scenario("unknown-both")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["text"],
                    "unknown wire must not disturb the clean text block",
                )
                self.assertEqual(report.open_at_end, set())
                terminal = self._terminal_fields(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["unknown_events"], "1")
                self.assertEqual(terminal["unknown_items"], "1")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_clean_stream_reports_zero_unknown_counts(self) -> None:
        # A fully modeled reasoning+text+tool turn must report unknown_events=0 and
        # unknown_items=0 — the "0 when clean" invariant the allowlists protect.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                terminal = self._terminal_fields(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["unknown_events"], "0")
                self.assertEqual(terminal["unknown_items"], "0")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_unknown_event_only_and_item_only_isolated(self) -> None:
        # Isolate each dimension so a future regression cannot cross-contaminate the
        # event vs item counters.
        for label, kwargs, expect in (
            ("event-only", {"unknown_item_type": None}, ("1", "0")),
            ("item-only", {"unknown_event_type": None}, ("0", "1")),
        ):
            with self.subTest(dimension=label):
                scenario = unknown_wire_scenario(f"unknown-{label}", **kwargs)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_messages(stream=True, tools=[READ_TOOL])
                        self.assertEqual(result.status, 200, result.text)
                        lifecycle_report(parse_typed_sse(result.body))
                        terminal = self._terminal_fields(
                            lifecycle_for_response(shim, result)
                        )
                        self.assertEqual(terminal["unknown_events"], expect[0], label)
                        self.assertEqual(terminal["unknown_items"], expect[1], label)
                        shim.assert_offline_contract()

    # --- Group 2: R1 obfuscation tolerance ---

    def test_obfuscation_field_on_arguments_delta_is_tolerated(self) -> None:
        # A live `obfuscation` field on arguments.delta is a known-but-unmodeled
        # field: tolerated silently (unknown_events stays 0) while the tool call
        # still translates to a clean tool_use block.
        scenario = obfuscation_tool_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                report = lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["tool_use"],
                )
                self.assertEqual(report.open_at_end, set())
                terminal = self._terminal_fields(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                self.assertEqual(terminal["unknown_events"], "0")
                self.assertEqual(terminal["unknown_items"], "0")
                self.assertEqual(terminal["tools_called"], "1")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- Group 3: R2 code/status classification + envelope shapes ---

    def test_inband_recognized_code_rows_across_envelope_shapes(self) -> None:
        # Each recognized backend code maps to its Anthropic error type, and each is
        # carried by a DIFFERENT captured envelope shape so both dimensions (code
        # classification + envelope tolerance) are proven together. A recognized
        # envelope never increments the unknown-envelope counter (unknown_events=0).
        cases = (
            # (label, error_payload, expected anthropic type)
            # Shape 3: flat root {code, message}
            (
                "insufficient_quota/flat-root",
                {"code": "insufficient_quota", "message": "plan exhausted"},
                "invalid_request_error",
            ),
            # Shape 2: {status, error:{...}} (chatgpt lane); top-level status is
            # metadata only — classification is code-driven.
            (
                "rate_limit_exceeded/status-wrapped",
                {"status": 429, "error": {"code": "rate_limit_exceeded"}},
                "rate_limit_error",
            ),
            # Shape 1: bare {error:{...}} (openai lane).
            (
                "server_is_overloaded/bare-error",
                {"error": {"code": "server_is_overloaded"}},
                "overloaded_error",
            ),
            # Shape 3 again, distinct code -> authentication_error.
            (
                "token_invalidated/flat-root",
                {"code": "token_invalidated", "message": "session expired"},
                "authentication_error",
            ),
        )
        for label, payload, expected_type in cases:
            with self.subTest(row=label):
                failure, terminal = self._inband_error(
                    f"classify-{label.split('/')[0]}", payload, expected_type
                )
                self.assertEqual(failure.error.get("type"), expected_type, label)
                self.assertIsInstance(failure.error.get("message"), str, label)
                self.assertLessEqual(len(failure.error.get("message", "")), 200, label)
                self.assertEqual(terminal["outcome"], "error", label)
                # Recognized envelope: no unknown-envelope increment.
                self.assertEqual(terminal["unknown_events"], "0", label)

    def test_http_status_only_rows(self) -> None:
        # Unknown backend type + no code -> pure HTTP-status classification. 422 is a
        # 4xx (non-retryable, one request); 500 is a retryable 5xx (RETRY_STATUSES,
        # exhausted after MAX_RETRIES -> four requests).
        with self.subTest(row="unknown-code-4xx"):
            failure, terminal = self._http_failure(
                backend_status_scenario("status-422", 422),
                "invalid_request_error",
                expected_requests=1,
            )
            self.assertEqual(failure.error.get("type"), "invalid_request_error")
            self.assertEqual(terminal["outcome"], "error")

        with self.subTest(row="unknown-code-5xx"):
            failure, terminal = self._http_failure(
                backend_status_scenario("status-500", 500, retry_after="0"),
                "api_error",
                expected_requests=4,
            )
            self.assertEqual(failure.error.get("type"), "api_error")
            self.assertEqual(terminal["retries"], "3")

    def test_bare_503_classifies_as_api_error(self) -> None:
        # Adjudicated (2026-07-20): a bare/unknown-code 503 -> api_error, NOT
        # overloaded_error. overloaded_error is reserved for the recognized overload
        # codes (server_is_overloaded/slow_down) and status 529. Both classes stay
        # retryable, so client behavior is equivalent; this pins the type explicitly.
        failure, terminal = self._http_failure(
            backend_status_scenario("status-503-bare", 503, retry_after="0"),
            "api_error",
            expected_requests=4,
        )
        self.assertEqual(failure.error.get("type"), "api_error")
        self.assertEqual(terminal["outcome"], "error")
        self.assertEqual(terminal["retries"], "3")

    def test_detail_envelope_is_recognized_and_status_classified(self) -> None:
        # Codex model-rejection shape {detail: "..."} is a RECOGNIZED envelope (no
        # unknown-envelope increment) even though it is code-less; it classifies by
        # HTTP status (400 -> invalid_request_error).
        scenario = backend_status_scenario("detail-400", 400)
        scenario.stream_error_body = json.dumps(
            {"detail": "The requested model is not available."},
            separators=(",", ":"),
        ).encode("utf-8")
        failure, terminal = self._http_failure(
            scenario, "invalid_request_error", expected_requests=1
        )
        self.assertEqual(failure.error.get("type"), "invalid_request_error")
        self.assertEqual(terminal["outcome"], "error")
        # {detail} is recognized shape -> NOT counted as an unknown envelope.
        self.assertEqual(terminal["unknown_events"], "0")

    def test_unstructured_envelope_is_counted(self) -> None:
        # Contrast to {detail}: a dict with no error-ish fields is UNRECOGNIZED, so
        # R1 counts it (unknown_events=1) before classifying it by HTTP status.
        scenario = backend_status_scenario("unstructured-400", 400)
        scenario.stream_error_body = json.dumps(
            {"foo": "bar"}, separators=(",", ":")
        ).encode("utf-8")
        failure, terminal = self._http_failure(
            scenario, "invalid_request_error", expected_requests=1
        )
        self.assertEqual(failure.error.get("type"), "invalid_request_error")
        self.assertEqual(terminal["unknown_events"], "1")

    # --- Group 4: D5 request-shape diagnosis line ---

    def test_request_shape_line_on_invalid_request_leaks_no_values(self) -> None:
        # On a backend invalid_request_error, exactly one `event=request_shape` line
        # is emitted carrying only sorted key NAMES (keys=, and text_keys=/
        # reasoning_keys= where applicable). No request VALUE may appear on that line
        # or anywhere in the captured logs (sentinel-absence, mirroring
        # test_v1211_reflected_backend_prose...).
        system_sentinel = "FABRICATED_SYSTEM_VALUE_D5_A1B"
        tool_desc_sentinel = "FABRICATED_TOOL_DESC_VALUE_D5_A1B"
        tool_input_sentinel = "FABRICATED_TOOL_INPUT_VALUE_D5_A1B"
        prompt_sentinel = "FABRICATED_PROMPT_VALUE_D5_A1B"
        sentinels = (
            system_sentinel,
            tool_desc_sentinel,
            tool_input_sentinel,
            prompt_sentinel,
        )
        request_body = {
            "model": "gpt-fixture",
            "max_tokens": 256,
            "stream": True,
            "system": system_sentinel,
            "tools": [
                {
                    "name": "ShapeFixture",
                    "description": tool_desc_sentinel,
                    "input_schema": {
                        "type": "object",
                        "properties": {"payload": {"type": "string"}},
                    },
                }
            ],
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call_shape_fixture",
                            "name": "ShapeFixture",
                            "input": {"payload": tool_input_sentinel},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call_shape_fixture",
                            "content": prompt_sentinel,
                        }
                    ],
                },
            ],
        }
        # insufficient_quota -> invalid_request_error triggers the request_shape line.
        scenario = structured_error_scenario(
            "d5-request-shape",
            "error",
            {"code": "insufficient_quota", "message": "plan exhausted"},
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_raw_messages(
                    json.dumps(request_body, separators=(",", ":")).encode("utf-8")
                )
                self.assertEqual(result.status, 200, result.text)
                failure_lifecycle_report(
                    parse_typed_sse(result.body),
                    expected_error_type="invalid_request_error",
                )
                lines = lifecycle_for_response(shim, result)

                shape_lines = [line for line in lines if line.event == "request_shape"]
                self.assertEqual(
                    len(shape_lines),
                    1,
                    ("exactly one request_shape line", [ln.raw for ln in lines]),
                )
                shape = shape_lines[0]
                # keys= present, non-empty, and includes the always-present outbound
                # Responses `input` key. The comma-joined name list is percent-encoded
                # by the v1.2.11 injection-safe machine-field encoder (commas -> %2C),
                # so decode with the stdlib oracle before splitting — production
                # helpers are intentionally not imported.
                keys_field = shape.fields.get("keys")
                self.assertIsInstance(keys_field, str)
                self.assertTrue(keys_field, "request_shape keys= is empty")
                decoded_keys = urllib.parse.unquote(keys_field).split(",")
                self.assertIn("input", decoded_keys)
                # Names only — never a request value.
                self.assertEqual(decoded_keys, sorted(decoded_keys))
                # text_keys/reasoning_keys, if present, are also name-lists only.
                for optional_field in ("text_keys", "reasoning_keys"):
                    if optional_field in shape.fields:
                        self.assertTrue(shape.fields[optional_field])
                        sub_keys = urllib.parse.unquote(
                            shape.fields[optional_field]
                        ).split(",")
                        self.assertEqual(sub_keys, sorted(sub_keys))

                # No request VALUE may appear on the request_shape line, in any
                # lifecycle line, or anywhere in the captured stderr.
                logs = shim.captured_stderr()
                for sentinel in sentinels:
                    self.assertNotIn(sentinel, shape.raw, sentinel)
                    for line in lines:
                        self.assertNotIn(sentinel, line.raw, (sentinel, line.event))
                    self.assertNotIn(sentinel, logs, sentinel)
                    self.assertNotIn(sentinel, result.text, sentinel)
                # The sentinels DID reach the backend request (proving non-reflection,
                # not mere absence from an unsent payload).
                backend_request = json.dumps(
                    backend.responses_requests[0].body, separators=(",", ":")
                )
                for sentinel in (tool_desc_sentinel, tool_input_sentinel, prompt_sentinel):
                    self.assertIn(sentinel, backend_request, sentinel)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)


if __name__ == "__main__":
    unittest.main()
