"""Deterministic v1.3.9 contracts for canonical GPT tier translation.

Every request drives the production ASGI app or a real production-shim subprocess.
The loopback fixtures inject exact upstream values; they prove serializer/parser/state
behavior only and do not reproduce or claim provider acceptance. No test in this module
makes a live provider request.

Fixture provenance:
* The inbound ``speed`` plus beta-marker contract comes from current Anthropic
  documentation/source reviewed for the v1.3.7 design.
* Both exact GPT routes use canonical OpenAI Responses request value ``priority``;
  ChatGPT presents that wire value as friendly Fast under plan/credit semantics.
* The served-tier fixtures are deterministic exact-value probes. Canonical served
  ``priority`` is current vocabulary; exact served ``fast`` is compatibility-only parser
  coverage. There is no claimed live served-Fast capture. The historical subscription
  probe that requested ``priority`` and was served ``default`` remains negative evidence.
"""

from __future__ import annotations

import copy
import json
import unittest
import urllib.parse

from ._loopback_harness import (
    READ_TOOL,
    USAGE,
    MockResponsesServer,
    RealShim,
    controlled_asgi_probe,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
    terminal_contract_scenario,
)


_FAST_BETA = "fast-mode-2026-02-01"
_FAST_HEADER = [(b"anthropic-beta", _FAST_BETA.encode("ascii"))]
_ABSENT_USAGE = {
    "input_tokens": USAGE["input_tokens"],
    "output_tokens": USAGE["output_tokens"],
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}


def _request_body(*, stream: bool, speed_marker: object = None) -> bytes:
    body: dict[str, object] = {
        "model": "gpt-fixture",
        "max_tokens": 256,
        "stream": stream,
        "messages": [{"role": "user", "content": "Exercise Fast translation."}],
    }
    if speed_marker is not None:
        body["speed"] = speed_marker
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def _fast_body(*, stream: bool) -> bytes:
    return _request_body(stream=stream, speed_marker="fast")


def _asgi_status_and_json(report) -> tuple[int, dict]:
    starts = [
        message
        for message in report.messages
        if message.get("type") == "http.response.start"
    ]
    if len(starts) != 1:
        raise AssertionError(f"expected one ASGI response start, got {starts!r}")
    body = b"".join(
        message.get("body", b"")
        for message in report.messages
        if message.get("type") == "http.response.body"
    )
    return starts[0]["status"], json.loads(body)


def _asgi_sse_events(report) -> list[dict]:
    payload = b"".join(
        message.get("body", b"")
        for message in report.messages
        if message.get("type") == "http.response.body"
    )
    frames = parse_typed_sse(payload)
    lifecycle_report(frames)
    return [frame.data for frame in frames if isinstance(frame.data, dict)]


def _terminal_fields(lines) -> dict[str, str]:
    terminals = [line.fields for line in lines if line.event == "terminal"]
    if len(terminals) != 1:
        raise AssertionError(f"expected one terminal lifecycle line, got {terminals!r}")
    return terminals[0]


def _terminal_scenario(name: str, event_type: str, service_tier=...):
    kwargs = {
        "status": "completed" if event_type == "response.completed" else "incomplete",
        "output": [],
        "usage": dict(USAGE),
    }
    if service_tier is not ...:
        kwargs["service_tier"] = service_tier
    return terminal_contract_scenario(name, event_type, **kwargs)


class FastRequestTranslationTests(unittest.TestCase):
    maxDiff = 16000

    def test_fast_beta_maps_to_route_specific_outbound_tier(self) -> None:
        # These are current docs/source-derived request contracts. The response fixtures
        # are deterministic and do not claim a live served-Fast observation.
        cases = (
            ("openai", "priority", "priority"),
            ("chatgpt", "priority", "priority"),
        )
        for mode, requested_tier, served_fixture in cases:
            with self.subTest(mode=mode):
                scenario = _terminal_scenario(
                    f"fast-route-{mode}",
                    "response.completed",
                    served_fixture,
                )
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_raw_messages(
                            _fast_body(stream=False),
                            headers={"anthropic-beta": _FAST_BETA},
                        )
                        self.assertEqual(result.status, 200, result.text)
                        backend.assert_request_counts(responses=1)
                        outbound = backend.responses_requests[0].body
                        self.assertEqual(outbound["service_tier"], requested_tier)
                        self.assertEqual(result.json()["usage"]["speed"], "fast")
                        fields = _terminal_fields(lifecycle_for_response(shim, result))
                        self.assertEqual(fields["requested_service_tier"], requested_tier)
                        self.assertEqual(fields["served_service_tier"], served_fixture)
                        shim.assert_offline_contract()

    def test_fast_without_beta_is_local_400_before_upstream(self) -> None:
        report = controlled_asgi_probe(
            stream=False,
            raw_request_body=_fast_body(stream=False),
        )
        status, payload = _asgi_status_and_json(report)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["type"], "invalid_request_error")
        self.assertIn("requires anthropic beta", payload["error"]["message"])
        self.assertEqual(report.upstream_calls, 0)
        self.assertEqual(report.outbound_payloads, [])

    def test_invalid_and_non_string_speed_are_local_400_before_upstream(self) -> None:
        invalid_values = (
            None,
            0,
            True,
            {},
            [],
            "standard",
            "FAST",
            " fast",
            "fast ",
            "fast\x00",
        )
        for value in invalid_values:
            with self.subTest(speed=value):
                body = {
                    "model": "gpt-fixture",
                    "max_tokens": 256,
                    "stream": False,
                    "messages": [{"role": "user", "content": "invalid speed"}],
                    "speed": value,
                }
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=json.dumps(
                        body, separators=(",", ":")
                    ).encode("utf-8"),
                    raw_scope_headers=_FAST_HEADER,
                )
                status, payload = _asgi_status_and_json(report)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["type"], "invalid_request_error")
                self.assertEqual(payload["error"]["message"], "unsupported speed value")
                self.assertEqual(report.upstream_calls, 0)
                self.assertEqual(report.outbound_payloads, [])

    def test_duplicate_top_level_speed_rejected_narrowly_before_auth_or_upstream(self) -> None:
        duplicate_speed_bodies = (
            (
                "identical",
                b'{"model":"gpt-fixture","max_tokens":256,"stream":false,'
                b'"speed":"fast","speed":"fast","messages":'
                b'[{"role":"user","content":"duplicate speed"}]}',
            ),
            (
                "conflicting",
                b'{"model":"gpt-fixture","max_tokens":256,"stream":false,'
                b'"speed":"standard","speed":"fast","messages":'
                b'[{"role":"user","content":"duplicate speed"}]}',
            ),
        )
        for label, raw_body in duplicate_speed_bodies:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=raw_body,
                    raw_scope_headers=_FAST_HEADER,
                )
                status, payload = _asgi_status_and_json(report)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["type"], "invalid_request_error")
                self.assertEqual(
                    payload["error"]["message"], "duplicate top-level speed field"
                )
                self.assertEqual(report.auth_calls, 0)
                self.assertEqual(report.upstream_calls, 0)
                self.assertEqual(report.outbound_payloads, [])

        unrelated_duplicate = controlled_asgi_probe(
            stream=False,
            raw_request_body=(
                b'{"model":"gpt-first","model":"gpt-last","max_tokens":256,'
                b'"stream":false,"messages":'
                b'[{"role":"user","content":"ordinary duplicate"}]}'
            ),
        )
        status, _payload = _asgi_status_and_json(unrelated_duplicate)
        self.assertEqual(status, 200)
        self.assertEqual(unrelated_duplicate.auth_calls, 1)
        self.assertEqual(unrelated_duplicate.upstream_calls, 1)
        self.assertEqual(unrelated_duplicate.outbound_payloads[0]["model"], "gpt-last")
        self.assertNotIn("service_tier", unrelated_duplicate.outbound_payloads[0])

        nested_speed_duplicate = controlled_asgi_probe(
            stream=False,
            raw_request_body=(
                b'{"model":"gpt-fixture","max_tokens":256,"stream":false,'
                b'"messages":[{"role":"user","content":"nested duplicate",'
                b'"speed":"first","speed":"last"}]}'
            ),
        )
        status, _payload = _asgi_status_and_json(nested_speed_duplicate)
        self.assertEqual(status, 200)
        self.assertEqual(nested_speed_duplicate.auth_calls, 1)
        self.assertEqual(nested_speed_duplicate.upstream_calls, 1)
        self.assertNotIn("service_tier", nested_speed_duplicate.outbound_payloads[0])

    def test_beta_without_speed_and_ordinary_request_omit_service_tier(self) -> None:
        for label, headers in (
            ("beta-only", _FAST_HEADER),
            ("ordinary", []),
        ):
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=_request_body(stream=False),
                    raw_scope_headers=headers,
                )
                status, payload = _asgi_status_and_json(report)
                self.assertEqual(status, 200)
                self.assertEqual(payload["usage"], _ABSENT_USAGE)
                self.assertEqual(report.upstream_calls, 1)
                self.assertEqual(len(report.outbound_payloads), 1)
                self.assertNotIn("service_tier", report.outbound_payloads[0])
                terminal = _terminal_fields(report.lifecycle)
                self.assertEqual(terminal["requested_service_tier"], "-")
                self.assertEqual(terminal["served_service_tier"], "-")

    def test_raw_asgi_beta_parsing_preserves_duplicate_comma_and_exactness(self) -> None:
        accepted = (
            (
                "duplicate-case-insensitive-name",
                [
                    (b"anthropic-beta", b"unrelated-beta"),
                    (b"AnThRoPiC-BeTa", _FAST_BETA.encode("ascii")),
                ],
            ),
            (
                "comma-list",
                [
                    (
                        b"ANTHROPIC-BETA",
                        f"unrelated-beta, {_FAST_BETA}, another-beta".encode("ascii"),
                    )
                ],
            ),
        )
        for label, headers in accepted:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=_fast_body(stream=False),
                    raw_scope_headers=headers,
                )
                status, _payload = _asgi_status_and_json(report)
                self.assertEqual(status, 200)
                self.assertEqual(report.upstream_calls, 1)
                self.assertEqual(report.outbound_payloads[0]["service_tier"], "priority")

        rejected = (
            (
                "beta-token-case-sensitive",
                [(b"anthropic-beta", b"Fast-mode-2026-02-01")],
            ),
            (
                "malformed-value-bytes",
                [(b"anthropic-beta", b"\xfffast-mode-2026-02-01")],
            ),
            (
                "malformed-name-bytes",
                [(b"anthropic-beta\xff", _FAST_BETA.encode("ascii"))],
            ),
        )
        for label, headers in rejected:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=_fast_body(stream=False),
                    raw_scope_headers=headers,
                )
                status, _payload = _asgi_status_and_json(report)
                self.assertEqual(status, 400)
                self.assertEqual(report.upstream_calls, 0)
                self.assertEqual(report.outbound_payloads, [])

    def test_beta_token_trims_only_http_sp_htab_ows(self) -> None:
        token = _FAST_BETA.encode("ascii")
        accepted = (
            ("sp-and-htab-around-token", [(b"anthropic-beta", b" \t" + token + b"\t ")]),
            (
                "sp-and-htab-in-comma-list",
                [(b"anthropic-beta", b"unrelated,\t" + token + b" \t,another")],
            ),
        )
        for label, headers in accepted:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=_fast_body(stream=False),
                    raw_scope_headers=headers,
                )
                status, _payload = _asgi_status_and_json(report)
                self.assertEqual(status, 200)
                self.assertEqual(report.upstream_calls, 1)
                self.assertEqual(report.outbound_payloads[0]["service_tier"], "priority")

        rejected = (
            ("vertical-tab-leading", b"\x0b" + token),
            ("vertical-tab-trailing", token + b"\x0b"),
            ("form-feed-leading", b"\x0c" + token),
            ("form-feed-trailing", token + b"\x0c"),
            ("carriage-return-leading", b"\r" + token),
            ("line-feed-trailing", token + b"\n"),
            ("nul-leading", b"\x00" + token),
            ("delete-trailing", token + b"\x7f"),
        )
        for label, tainted_token in rejected:
            with self.subTest(case=label):
                report = controlled_asgi_probe(
                    stream=False,
                    raw_request_body=_fast_body(stream=False),
                    raw_scope_headers=[(b"anthropic-beta", tainted_token)],
                )
                status, payload = _asgi_status_and_json(report)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["type"], "invalid_request_error")
                self.assertIn("requires anthropic beta", payload["error"]["message"])
                self.assertEqual(report.upstream_calls, 0)
                self.assertEqual(report.outbound_payloads, [])

    def test_fast_adds_only_tier_to_existing_model_reasoning_and_tools_translation(self) -> None:
        scenario = _terminal_scenario(
            "translation-unchanged",
            "response.completed",
            "priority",
        )
        body = {
            "model": "gpt-fixture#low",
            "max_tokens": 256,
            "stream": False,
            "messages": [{"role": "user", "content": "translate unchanged"}],
            "tools": [READ_TOOL],
            "tool_choice": {"type": "tool", "name": "Read"},
        }
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                ordinary = shim.post_raw_messages(
                    json.dumps(body, separators=(",", ":")).encode("utf-8")
                )
                self.assertEqual(ordinary.status, 200, ordinary.text)
                fast_body = dict(body)
                fast_body["speed"] = "fast"
                fast = shim.post_raw_messages(
                    json.dumps(fast_body, separators=(",", ":")).encode("utf-8"),
                    headers={"Anthropic-Beta": _FAST_BETA},
                )
                self.assertEqual(fast.status, 200, fast.text)
                backend.assert_request_counts(responses=2)
                ordinary_out = copy.deepcopy(backend.responses_requests[0].body)
                fast_out = copy.deepcopy(backend.responses_requests[1].body)
                self.assertNotIn("service_tier", ordinary_out)
                self.assertEqual(fast_out.pop("service_tier"), "priority")
                self.assertEqual(fast_out, ordinary_out)
                self.assertEqual(fast_out["model"], "gpt-fixture")
                self.assertEqual(fast_out["reasoning"], {"summary": "auto", "effort": "low"})
                self.assertEqual(fast_out["tools"][0]["name"], "Read")
                self.assertEqual(
                    fast_out["tool_choice"], {"type": "function", "name": "Read"}
                )


class ActualTierProjectionTests(unittest.TestCase):
    maxDiff = 16000

    def test_nonstream_actual_tier_exactness_and_absent_usage_compatibility(self) -> None:
        # Explicit oracle table: exact terminal values are injected; expected Anthropic
        # speed is asserted directly. This is data, not a helper that reimplements mapping.
        cases = (
            ("priority", "fast"),
            ("fast", "fast"),
            ("default", "standard"),
            ("flex", "standard"),
            ("scale", "standard"),
            ("auto", "standard"),
            (..., None),
            ("unknown", None),
            (7, None),
            ("Priority", None),
            (" priority", None),
            ("priority ", None),
            ("priority\x00", None),
        )
        scenario = _terminal_scenario("nonstream-tier-sequence", "response.completed")
        responses = []
        for tier, _expected_speed in cases:
            response = copy.deepcopy(scenario.nonstream_response)
            if tier is not ...:
                response["service_tier"] = tier
            responses.append(response)
        scenario.nonstream_responses = responses

        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                for index, (tier, expected_speed) in enumerate(cases):
                    with self.subTest(index=index, tier=tier):
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        usage = result.json()["usage"]
                        expected_usage = dict(_ABSENT_USAGE)
                        if expected_speed is not None:
                            expected_usage["speed"] = expected_speed
                        self.assertEqual(usage, expected_usage)
                        fields = _terminal_fields(lifecycle_for_response(shim, result))
                        if tier is ... or not isinstance(tier, str):
                            self.assertEqual(fields["served_service_tier"], "-")
                        else:
                            expected_telemetry = {
                                " priority": "priority",
                                "priority ": "priority",
                                "priority\x00": "priority",
                            }.get(tier, tier)
                            self.assertEqual(
                                urllib.parse.unquote(fields["served_service_tier"]),
                                expected_telemetry,
                            )
                backend.assert_request_counts(responses=len(cases))
                shim.assert_offline_contract()

    def test_streaming_exact_tiers_only_appear_on_terminal_message_delta(self) -> None:
        cases = (
            ("priority", "fast"),
            ("fast", "fast"),
            ("default", "standard"),
            ("flex", "standard"),
            ("scale", "standard"),
            ("auto", "standard"),
            (..., None),
            ("unknown", None),
            (False, None),
            ("FAST", None),
            (" fast", None),
            ("fast ", None),
            ("fast\x00", None),
        )
        for index, (tier, expected_speed) in enumerate(cases):
            with self.subTest(index=index, tier=tier):
                scenario = _terminal_scenario(
                    f"stream-tier-{index}",
                    "response.completed",
                    tier,
                ) if tier is not ... else _terminal_scenario(
                    f"stream-tier-{index}",
                    "response.completed",
                )
                report = controlled_asgi_probe(scenario=scenario, stream=True)
                self.assertIsNone(report.raised)
                self.assertEqual(report.upstream_calls, 1)
                events = _asgi_sse_events(report)
                message_start = next(
                    event for event in events if event.get("type") == "message_start"
                )
                message_delta = next(
                    event for event in events if event.get("type") == "message_delta"
                )
                self.assertNotIn("speed", message_start["message"]["usage"])
                if expected_speed is None:
                    self.assertNotIn("speed", message_delta["usage"])
                else:
                    self.assertEqual(message_delta["usage"]["speed"], expected_speed)

    def test_streaming_incomplete_supports_fast_standard_and_absent_exactly(self) -> None:
        for index, (tier, expected_speed) in enumerate(
            (("fast", "fast"), ("default", "standard"), (..., None))
        ):
            with self.subTest(tier=tier):
                scenario = _terminal_scenario(
                    f"incomplete-tier-{index}",
                    "response.incomplete",
                    tier,
                ) if tier is not ... else _terminal_scenario(
                    f"incomplete-tier-{index}",
                    "response.incomplete",
                )
                report = controlled_asgi_probe(scenario=scenario, stream=True)
                events = _asgi_sse_events(report)
                delta = next(
                    event for event in events if event.get("type") == "message_delta"
                )
                self.assertEqual(delta["delta"]["stop_reason"], "max_tokens")
                if expected_speed is None:
                    self.assertNotIn("speed", delta["usage"])
                else:
                    self.assertEqual(delta["usage"]["speed"], expected_speed)


class RetryFallbackAndTelemetryTests(unittest.TestCase):
    maxDiff = 16000

    def test_transient_retry_reuses_identical_priority_payload(self) -> None:
        report = controlled_asgi_probe(
            scenario=_terminal_scenario("retry-priority", "response.completed", "priority"),
            stream=False,
            raw_request_body=_fast_body(stream=False),
            raw_scope_headers=_FAST_HEADER,
            attempt_outcomes=[503, 200],
        )
        status, payload = _asgi_status_and_json(report)
        self.assertEqual(status, 200)
        self.assertEqual(payload["usage"]["speed"], "fast")
        self.assertEqual(report.upstream_calls, 2)
        self.assertEqual(len(report.outbound_payloads), 2)
        self.assertEqual(report.outbound_payloads[0], report.outbound_payloads[1])
        self.assertEqual(report.outbound_payloads[0]["service_tier"], "priority")
        terminal = _terminal_fields(report.lifecycle)
        self.assertEqual(terminal["attempts"], "2")
        self.assertEqual(terminal["retries"], "1")

    def test_context_rejection_has_no_standard_fallback(self) -> None:
        scenario = _terminal_scenario("context-rejection", "response.completed")
        scenario.stream_error_body = (
            b'{"error":{"type":"invalid_request_error",'
            b'"code":"context_length_exceeded",'
            b'"message":"fixture context limit"}}'
        )
        report = controlled_asgi_probe(
            scenario=scenario,
            stream=False,
            raw_request_body=_fast_body(stream=False),
            raw_scope_headers=_FAST_HEADER,
            response_status=400,
        )
        status, payload = _asgi_status_and_json(report)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["type"], "invalid_request_error")
        self.assertEqual(report.upstream_calls, 1)
        self.assertEqual(len(report.outbound_payloads), 1)
        self.assertEqual(report.outbound_payloads[0]["service_tier"], "priority")
        self.assertNotEqual(report.outbound_payloads[0]["service_tier"], "default")
        terminal = _terminal_fields(report.lifecycle)
        self.assertEqual(terminal["retries"], "0")
        self.assertEqual(terminal["requested_service_tier"], "priority")
        self.assertEqual(terminal["served_service_tier"], "-")

    def test_historical_subscription_priority_default_is_negative_not_canonical(self) -> None:
        # Historical live evidence: one guarded subscription request explicitly asking for
        # PRIORITY was accepted but served DEFAULT. That is negative evidence only. The
        # current canonical request is PRIORITY, asserted below; this deterministic DEFAULT
        # response is serializer/parser/state evidence and makes no provider-acceptance claim.
        scenario = _terminal_scenario(
            "historical-negative-current-contract",
            "response.completed",
            "default",
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_raw_messages(
                    _fast_body(stream=False),
                    headers={"anthropic-beta": _FAST_BETA},
                )
                self.assertEqual(result.status, 200, result.text)
                self.assertEqual(
                    backend.responses_requests[0].body["service_tier"], "priority"
                )
                self.assertEqual(result.json()["usage"]["speed"], "standard")
                terminal = _terminal_fields(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["requested_service_tier"], "priority")
                self.assertEqual(terminal["served_service_tier"], "default")
                backend.assert_request_counts(responses=1)

    def test_requested_served_mismatch_and_control_scrub_are_encoded_safely(self) -> None:
        tainted = "priority\r\nFORGED=1\x00"
        report = controlled_asgi_probe(
            scenario=_terminal_scenario(
                "telemetry-control-scrub",
                "response.completed",
                tainted,
            ),
            stream=True,
            raw_request_body=_fast_body(stream=True),
            raw_scope_headers=_FAST_HEADER,
        )
        events = _asgi_sse_events(report)
        delta = next(event for event in events if event.get("type") == "message_delta")
        self.assertNotIn("speed", delta["usage"])
        terminal = _terminal_fields(report.lifecycle)
        self.assertEqual(terminal["requested_service_tier"], "priority")
        self.assertEqual(
            urllib.parse.unquote(terminal["served_service_tier"]),
            "priority FORGED=1",
        )
        self.assertIn("%20", terminal["served_service_tier"])
        self.assertIn("%3D", terminal["served_service_tier"])
        self.assertNotIn("\r", report.logs)
        self.assertNotIn("\nFORGED=1", report.logs)
        for line in report.logs.splitlines():
            self.assertNotRegex(line, r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


if __name__ == "__main__":
    unittest.main()
