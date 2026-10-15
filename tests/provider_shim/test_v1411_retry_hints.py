"""Shim v1.4.11: retry hints, the "Prompt is too long" message, failed JSON bodies
and OpenAI's billing codes.

A. A NON-STREAM error whose client-facing type is ``invalid_request_error`` carries
   ``x-should-retry: false``. Claude Code 2.1.281 reads that header before its
   status rules, so a backend 429 with a quota code (which keeps its real 429 since
   v1.2.14 R2) is no longer retried as a throttle. No header for api_error
   (incl. code server_error), rate_limit_error, overloaded_error or
   authentication_error, and none on a 408 or 409 whatever the type (Claude Code
   retries both; review fix). Streaming replies send HTTP 200 before the outcome is
   known, so the 200 never carries it; the error travels as an SSE event.
B. The fixed message for context_length_exceeded is "Prompt is too long (backend
   context length exceeded)", the phrase Claude Code recognizes as a context
   overflow, on streaming and non-stream paths.
C. OpenAI lane, HTTP 200 whose Responses object has status "failed": the ordinary
   non-stream path and the search JSON transport classify the body's ``error``
   instead of sending a flat 502 "conversion failed".
D. credit_balance_exhausted, organization_spend_limit_exceeded,
   project_spend_limit_exceeded and organization_usage_limit_exceeded classify as
   non-retryable invalid_request_error, so the shim sends such a 429 request once.

Provider-free: a mock Responses backend on loopback, fabricated values only.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import unittest
import uuid

from . import _native_search_fixtures as fx
from ._loopback_harness import (
    PRODUCTION_SHIM,
    USAGE,
    MockResponsesServer,
    RealShim,
    Scenario,
    _purge_in_process_reasoning_cache_seam,
    backend_status_scenario,
    failure_lifecycle_report,
    lifecycle_for_response,
    parse_typed_sse,
    sequenced_attempt_scenario,
    structured_error_scenario,
)

# Fabricated backend prose. The client message must come from the shim's fixed
# messages, never from this text.
PROSE_SENTINEL = "FABRICATED_BACKEND_PROSE_V1411_K3"

CONTEXT_MESSAGE = "Prompt is too long (backend context length exceeded)"
QUOTA_MESSAGE = "backend quota or plan limit reached"
NO_RETRY_HEADER = "x-should-retry"

# v1.4.11 (D): exact spellings from OpenAI's error-codes guide (fetched 2026-10-14).
BILLING_CODES = (
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
)


def _error_body(code, error_type, message=PROSE_SENTINEL):
    return json.dumps({"error": {"type": error_type, "code": code, "message": message}},
                      separators=(",", ":")).encode("utf-8")


def _ordinary_request(stream=False):
    return json.dumps({
        "model": "gpt-fixture", "max_tokens": 256, "stream": stream,
        "messages": [{"role": "user", "content": "Exercise the fixture."}],
    }, separators=(",", ":")).encode("utf-8")


class RetryHintUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _purge_in_process_reasoning_cache_seam()
        name = "provider_shim_v1411_hints_%s" % uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, PRODUCTION_SHIM)
        cls.shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.shim)

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.shim._client.aclose())

    def test_header_helper_emits_only_for_invalid_request_error(self):
        self.assertEqual(self.shim._no_retry_headers_for("invalid_request_error"),
                         [(b"x-should-retry", b"false")])
        for error_type in ("api_error", "rate_limit_error", "overloaded_error",
                           "authentication_error", "permission_error", "not_found_error",
                           "-", "", None, "INVALID_REQUEST_ERROR"):
            with self.subTest(error_type=error_type):
                self.assertIsNone(self.shim._no_retry_headers_for(error_type))

    def test_header_helper_never_emits_on_408_or_409(self):
        # Review fix: Claude Code 2.1.281 retries 408 and 409
        # (`if(e.status===408)return!0;if(e.status===409)return!0;`) and reads the
        # header first, so the header must not ride on either status, whatever the type.
        for status in (408, 409):
            with self.subTest(status=status):
                self.assertIsNone(
                    self.shim._no_retry_headers_for("invalid_request_error", status))
        for status in (None, 400, 403, 404, 422, 429, 500, 502):
            with self.subTest(status=status):
                self.assertEqual(
                    self.shim._no_retry_headers_for("invalid_request_error", status),
                    [(b"x-should-retry", b"false")])
                self.assertIsNone(self.shim._no_retry_headers_for("api_error", status))

    def test_helper_returns_a_fresh_list(self):
        # _send_json extends its own header list; a shared mutable default would leak.
        first = self.shim._no_retry_headers_for("invalid_request_error")
        first.append((b"x-fixture", b"1"))
        self.assertEqual(self.shim._no_retry_headers_for("invalid_request_error"),
                         [(b"x-should-retry", b"false")])

    def test_context_message_is_recognizable_and_digit_free(self):
        _type, message, retryable = \
            self.shim._BACKEND_SIGNAL_CLASSIFICATION["context_length_exceeded"]
        self.assertEqual(message, CONTEXT_MESSAGE)
        self.assertFalse(retryable)
        # Claude Code 2.1.281 yHn(): lowercase includes "prompt is too long".
        self.assertIn("prompt is too long", message.lower())
        # The client's gap parser reads digits after the phrase; there must be none.
        self.assertFalse(any(ch.isdigit() for ch in message))

    def test_billing_codes_classify_as_non_retryable_quota(self):
        for code in BILLING_CODES:
            with self.subTest(code=code):
                self.assertEqual(self.shim._BACKEND_SIGNAL_CLASSIFICATION[code],
                                 ("invalid_request_error", QUOTA_MESSAGE, False))
                # The type here is NOT insufficient_quota, so only the new code entry
                # can classify it (the type fallback would otherwise cover it).
                body = _error_body(code, "billing_fixture_type")
                self.assertEqual(self.shim._plan_retry(429, None, body, 0),
                                 (False, 0.0, "-"))


class RetryHintLoopbackTests(unittest.TestCase):
    maxDiff = 8000

    def _event_line(self, lines, event):
        matches = [line for line in lines if line.event == event]
        self.assertEqual(len(matches), 1, (event, [line.raw for line in lines]))
        return matches[0]

    def _assert_error(self, result, *, status, error_type, message, header, marker):
        self.assertEqual(result.status, status, (marker, result.text))
        body = result.json()
        self.assertEqual(body.get("type"), "error", marker)
        error = body.get("error") or {}
        self.assertEqual(error.get("type"), error_type, marker)
        self.assertEqual(error.get("message"), message, marker)
        self.assertNotIn(PROSE_SENTINEL, result.text, marker)
        if header:
            self.assertEqual(result.headers.get(NO_RETRY_HEADER), "false", marker)
        else:
            self.assertNotIn(NO_RETRY_HEADER, result.headers, marker)

    # --- A + D: pre-stream 429 with a quota or billing code ---

    def test_quota_and_billing_429_keep_status_add_header_and_send_once(self):
        cases = (
            ("insufficient_quota", "insufficient_quota"),
            ("usage_not_included", "usage_not_included"),
        ) + tuple((code, "billing_fixture_type") for code in BILLING_CODES)
        requests = (
            ("ordinary", _ordinary_request()),
            ("search", json.dumps(fx.search_request(False)).encode("utf-8")),
        )
        for lane in ("chatgpt", "openai"):
            for code, backend_type in cases:
                for request_name, request_bytes in requests:
                    marker = "QUOTA_429_%s_%s_%s" % (lane, code, request_name)
                    with self.subTest(lane=lane, code=code, request=request_name):
                        scenario = backend_status_scenario(
                            "v1411-" + code, 429, error_body=_error_body(code, backend_type))
                        with MockResponsesServer(scenario) as backend:
                            with RealShim(backend, lane) as shim:
                                result = shim.post_raw_messages(request_bytes)
                                self._assert_error(
                                    result, status=429, error_type="invalid_request_error",
                                    message=QUOTA_MESSAGE, header=True, marker=marker)
                                # D + v1.2.14 R4: the shim does not retry it either.
                                backend.assert_request_counts(responses=1)
                                terminal = self._event_line(
                                    lifecycle_for_response(shim, result), "terminal").fields
                                self.assertEqual(terminal["retries"], "0", marker)
                                self.assertNotIn(PROSE_SENTINEL, shim.captured_stderr(), marker)
                                shim.assert_offline_contract()

    def test_streaming_quota_429_is_an_sse_error_without_header(self):
        # A streamed request sends its HTTP 200 before the backend answers, so a
        # pre-stream quota 429 becomes an in-band `error` event and the 200 carries no
        # x-should-retry header (the client's non-streamed fallback re-send is the
        # request that gets it).
        for lane in ("chatgpt", "openai"):
            for code, backend_type in (("insufficient_quota", "insufficient_quota"),
                                       (BILLING_CODES[0], "billing_fixture_type")):
                marker = "STREAM_QUOTA_429_%s_%s" % (lane, code)
                with self.subTest(lane=lane, code=code):
                    scenario = backend_status_scenario(
                        "v1411-stream-" + code, 429, error_body=_error_body(code, backend_type))
                    with MockResponsesServer(scenario) as backend:
                        with RealShim(backend, lane) as shim:
                            result = shim.post_raw_messages(_ordinary_request(stream=True))
                            self.assertEqual(result.status, 200, (marker, result.text))
                            self.assertNotIn(NO_RETRY_HEADER, result.headers, marker)
                            failure = failure_lifecycle_report(
                                parse_typed_sse(result.body),
                                expected_error_type="invalid_request_error")
                            self.assertEqual(failure.error["message"], QUOTA_MESSAGE, marker)
                            self.assertNotIn(PROSE_SENTINEL, result.text, marker)
                            backend.assert_request_counts(responses=1)
                            shim.assert_offline_contract()

    # --- A: a bare 409 keeps the client's retry ---

    def test_bare_409_keeps_status_and_has_no_header(self):
        # Review fix: an unrecognized 409 falls to the status fallback and is typed
        # invalid_request_error, but Claude Code retries 409, so no header.
        body = json.dumps({"error": {"type": "fixture_conflict", "message": PROSE_SENTINEL}},
                          separators=(",", ":")).encode("utf-8")
        for lane in ("chatgpt", "openai"):
            with self.subTest(lane=lane):
                scenario = backend_status_scenario("v1411-409", 409, error_body=body)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_raw_messages(_ordinary_request())
                        self._assert_error(
                            result, status=409, error_type="invalid_request_error",
                            message="backend request failed", header=False,
                            marker="BARE_409_" + lane)
                        # 409 is outside the shim's own retry set: one request.
                        backend.assert_request_counts(responses=1)
                        shim.assert_offline_contract()

    def test_bare_409_on_search_nonstream_keeps_status_and_has_no_header(self):
        # v1.4.12 (1.4.11 review gap): the search non-stream status passthrough calls
        # _no_retry_headers_for(error_type, resp.status_code); a bare 409 there is also
        # typed invalid_request_error and must still reach the client without the
        # header. Both lanes (SSE transport on chatgpt, JSON transport on openai).
        body = json.dumps({"error": {"type": "fixture_conflict", "message": PROSE_SENTINEL}},
                          separators=(",", ":")).encode("utf-8")
        search_request = json.dumps(fx.search_request(False)).encode("utf-8")
        for lane in ("chatgpt", "openai"):
            with self.subTest(lane=lane):
                scenario = backend_status_scenario("v1412-search-409", 409, error_body=body)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_raw_messages(search_request)
                        self._assert_error(
                            result, status=409, error_type="invalid_request_error",
                            message="backend request failed", header=False,
                            marker="SEARCH_BARE_409_" + lane)
                        backend.assert_request_counts(responses=1)
                        shim.assert_offline_contract()

    # --- A: retryable types carry no header and keep the existing retry policy ---

    def test_rate_limit_429_has_no_header_and_is_still_retried(self):
        body = _error_body("rate_limit_exceeded", "rate_limit_exceeded",
                           "Rate limit reached. Please try again in 0.01s.")
        for lane in ("chatgpt", "openai"):
            with self.subTest(lane=lane, outcome="recovers"):
                # The shim's own retry of a rate-limit 429 still runs: one recorded
                # status_429 retry, then success. (A header check on the final 200
                # would pass whatever the 429 handling did, so it is not used here.)
                scenario = sequenced_attempt_scenario("v1411-rl-recovers", [429, 200])
                scenario.stream_error_body = body
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        backend.assert_request_counts(responses=2)
                        lines = lifecycle_for_response(shim, result)
                        retries = [line for line in lines if line.event == "upstream_retry"]
                        self.assertEqual([line.fields["reason"] for line in retries],
                                         ["status_429"], lane)
                        terminal = self._event_line(lines, "terminal").fields
                        self.assertEqual(terminal["retries"], "1", lane)
            with self.subTest(lane=lane, outcome="exhausted"):
                scenario = backend_status_scenario("v1411-rl-exhausted", 429, error_body=body)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_messages(stream=False)
                        self._assert_error(
                            result, status=429, error_type="rate_limit_error",
                            message="backend rate limit exceeded", header=False,
                            marker="RL_EXHAUSTED_" + lane)
                        # Existing policy: MAX_RETRIES (3) internal retries, 4 requests.
                        backend.assert_request_counts(responses=4)
                        terminal = self._event_line(
                            lifecycle_for_response(shim, result), "terminal").fields
                        self.assertEqual(terminal["retries"], "3")

    def test_server_error_paths_have_no_header(self):
        # Pre-stream 500 coded server_error: classifier retryable=False, so one
        # request, and it reaches the client as a retryable 500 api_error.
        for lane in ("chatgpt", "openai"):
            with self.subTest(lane=lane, path="pre-stream-500"):
                scenario = backend_status_scenario(
                    "v1411-500", 500, error_body=_error_body("server_error", "server_error"))
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, lane) as shim:
                        result = shim.post_messages(stream=False)
                        self._assert_error(
                            result, status=500, error_type="api_error",
                            message="backend server error", header=False,
                            marker="SERVER_ERROR_500_" + lane)
                        backend.assert_request_counts(responses=1)
        with self.subTest(lane="chatgpt", path="in-band"):
            scenario = structured_error_scenario(
                "v1411-inband-server-error", "response.failed",
                {"code": "server_error", "message": PROSE_SENTINEL})
            with MockResponsesServer(scenario) as backend:
                with RealShim(backend, "chatgpt") as shim:
                    result = shim.post_raw_messages(_ordinary_request())
                    self._assert_error(
                        result, status=502, error_type="api_error",
                        message="backend server error", header=False,
                        marker="SERVER_ERROR_INBAND")
                    backend.assert_request_counts(responses=1)

    def test_inband_token_invalidated_401_has_no_header(self):
        scenario = structured_error_scenario(
            "v1411-inband-401", "response.failed",
            {"code": "token_invalidated", "message": PROSE_SENTINEL})
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_raw_messages(_ordinary_request())
                self._assert_error(
                    result, status=401, error_type="authentication_error",
                    message="backend authentication failed", header=False,
                    marker="INBAND_401")
                backend.assert_request_counts(responses=1)

    def test_local_400s_carry_the_header(self):
        with MockResponsesServer(structured_error_scenario(
                "v1411-local", "error", {"code": "server_error"})) as backend:
            with RealShim(backend, "chatgpt") as shim:
                with self.subTest(case="invalid-json"):
                    result = shim.post_raw_messages(b"{not json")
                    self._assert_error(
                        result, status=400, error_type="invalid_request_error",
                        message="invalid JSON", header=True, marker="LOCAL_INVALID_JSON")
                with self.subTest(case="invalid-structure"):
                    result = shim.post_raw_messages(b'{"messages":"not a list"}')
                    self._assert_error(
                        result, status=400, error_type="invalid_request_error",
                        message="invalid request structure", header=True,
                        marker="LOCAL_INVALID_STRUCTURE")
                with self.subTest(case="claude-slug"):
                    result = shim.post_messages(stream=False, model="claude-fixture-model")
                    self.assertEqual(result.status, 400, result.text)
                    self.assertEqual(result.json()["error"]["type"], "invalid_request_error")
                    self.assertEqual(result.headers.get(NO_RETRY_HEADER), "false")
                backend.assert_request_counts(responses=0)

    # --- B: the context-overflow message, non-stream and streaming ---

    def test_context_overflow_message_and_header(self):
        payload = {"type": "invalid_request_error", "code": "context_length_exceeded",
                   "message": PROSE_SENTINEL}
        for event_type in ("response.failed", "error"):
            with self.subTest(event=event_type, stream=False):
                scenario = structured_error_scenario(
                    "v1411-context-" + event_type.replace(".", "-"), event_type, payload)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_raw_messages(_ordinary_request())
                        self._assert_error(
                            result, status=400, error_type="invalid_request_error",
                            message=CONTEXT_MESSAGE, header=True,
                            marker="CONTEXT_NONSTREAM_" + event_type)
                        backend.assert_request_counts(responses=1)
            with self.subTest(event=event_type, stream=True):
                scenario = structured_error_scenario(
                    "v1411-context-stream-" + event_type.replace(".", "-"), event_type, payload)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_raw_messages(_ordinary_request(stream=True))
                        # Streaming: HTTP 200 is sent first; the error is an SSE event.
                        self.assertEqual(result.status, 200, result.text)
                        failure = failure_lifecycle_report(
                            parse_typed_sse(result.body),
                            expected_error_type="invalid_request_error")
                        self.assertEqual(failure.error["message"], CONTEXT_MESSAGE)
                        self.assertNotIn(PROSE_SENTINEL, result.text)

    # --- C: OpenAI lane, HTTP 200 with status "failed" ---

    def test_openai_nonstream_failed_body_is_classified(self):
        cases = (
            ("invalid_prompt", 400, "invalid_request_error",
             "backend rejected the request", True),
            ("context_length_exceeded", 400, "invalid_request_error", CONTEXT_MESSAGE, True),
            ("server_error", 502, "api_error", "backend server error", False),
            ("rate_limit_exceeded", 429, "rate_limit_error",
             "backend rate limit exceeded", False),
        )
        for code, status, error_type, message, header in cases:
            with self.subTest(code=code):
                scenario = structured_error_scenario(
                    "v1411-openai-failed-" + code, "response.failed",
                    {"code": code, "message": PROSE_SENTINEL})
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "openai") as shim:
                        result = shim.post_raw_messages(_ordinary_request())
                        self._assert_error(
                            result, status=status, error_type=error_type, message=message,
                            header=header, marker="OPENAI_FAILED_" + code)
                        lines = lifecycle_for_response(shim, result)
                        backend_error = self._event_line(lines, "backend_error")
                        self.assertEqual(backend_error.fields["backend_code"], code)
                        self.assertEqual(backend_error.fields["anthropic_type"], error_type)
                        # HTTP 200: the shim's status-retry loop never re-sends it.
                        backend.assert_request_counts(responses=1)
                        self.assertNotIn(PROSE_SENTINEL, shim.captured_stderr())
                        shim.assert_offline_contract()

    def test_openai_nonstream_failed_body_without_error_stays_502(self):
        # A failed body whose `error` is absent, null or malformed (a bare string, a
        # non-string code) carries no usable code/type, so it classifies as api_error.
        for label, extra in (("error-null", {"error": None}), ("error-absent", {}),
                             ("error-string", {"error": "string"}),
                             ("error-int-code", {"error": {"code": 123}})):
            with self.subTest(case=label):
                nonstream = {"id": "resp_v1411_failed_bare", "status": "failed",
                             "output": [], "usage": dict(USAGE)}
                nonstream.update(extra)
                scenario = Scenario(name="v1411-failed-" + label, stream_events=[],
                                    nonstream_response=nonstream, append_done=False)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "openai") as shim:
                        result = shim.post_raw_messages(_ordinary_request())
                        self._assert_error(
                            result, status=502, error_type="api_error",
                            message="backend request failed", header=False,
                            marker="OPENAI_FAILED_BARE_" + label)
                        backend.assert_request_counts(responses=1)

    def test_openai_nonstream_malformed_non_failed_body_is_conversion_failure(self):
        # (C) only takes bodies whose status is exactly "failed". Any other 200 the
        # converter cannot use keeps the pre-1.4.11 502 "conversion failed" path.
        cases = (
            ("status-in-progress", {"id": "resp_v1411_ip", "status": "in_progress",
                                    "output": [], "usage": dict(USAGE)}),
            ("completed-output-null", {"id": "resp_v1411_null", "status": "completed",
                                       "output": None, "usage": dict(USAGE)}),
            ("status-absent", {"id": "resp_v1411_nostatus", "output": [],
                               "usage": dict(USAGE)}),
        )
        for label, nonstream in cases:
            with self.subTest(case=label):
                scenario = Scenario(name="v1411-malformed-" + label, stream_events=[],
                                    nonstream_response=nonstream, append_done=False)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "openai") as shim:
                        result = shim.post_raw_messages(_ordinary_request())
                        self._assert_error(
                            result, status=502, error_type="api_error",
                            message="backend response conversion failed", header=False,
                            marker="OPENAI_MALFORMED_" + label)
                        backend.assert_request_counts(responses=1)

    def test_openai_search_json_failed_body_is_classified(self):
        search_request = json.dumps(fx.search_request(False)).encode("utf-8")
        cases = (
            ("invalid_prompt", 400, "invalid_request_error",
             "backend rejected the request", True),
            ("server_error", 502, "api_error", "backend server error", False),
        )
        for code, status, error_type, message, header in cases:
            with self.subTest(code=code):
                scenario = structured_error_scenario(
                    "v1411-search-failed-" + code, "response.failed",
                    {"code": code, "message": PROSE_SENTINEL})
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "openai") as shim:
                        result = shim.post_raw_messages(search_request)
                        self._assert_error(
                            result, status=status, error_type=error_type, message=message,
                            header=header, marker="SEARCH_JSON_FAILED_" + code)
                        lines = lifecycle_for_response(shim, result)
                        backend_error = self._event_line(lines, "backend_error")
                        self.assertEqual(backend_error.fields["backend_code"], code)
                        backend.assert_request_counts(responses=1)
                        # JSON transport: the outbound request asked for no stream.
                        self.assertIs(backend.responses_requests[0].body.get("stream"), False)
                        shim.assert_offline_contract()


if __name__ == "__main__":
    unittest.main()
