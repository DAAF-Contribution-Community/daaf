"""Shim v1.4.10: a non-streaming in-band failure gets the HTTP status of its type.

On the ChatGPT lane the backend can answer HTTP 200 and then report the failure
inside the SSE stream (``response.failed`` or an ``error`` event). The shim
classified it correctly (``context_length_exceeded`` -> ``invalid_request_error``)
but sent it with HTTP 502, and Claude Code retries 5xx up to 10 times before any
content has streamed. Live 2026-10-13: probe_context_ceiling.py got a 502 with
"backend context length exceeded"; the shim log recorded
``backend_type=invalid_request_error backend_code=context_length_exceeded``. The
fixtures below use that live type/code pair.

1. unit: the type -> status map is the exact inverse of the status -> type map and
   defaults to 502.
2. chatgpt non-stream, in-band ``response.failed`` and ``error`` with
   context_length_exceeded -> 400 invalid_request_error, one backend request.
3. the rest of the map on the same path: rate_limit_exceeded -> 429,
   token_invalidated -> 401, server_is_overloaded -> 529, insufficient_quota -> 400;
   server_error and an unknown code stay 502 api_error. No internal retry (the
   failure arrives after the 200), even for a retryable code.
4. code beats type on the same path: type ``context_length_exceeded`` with code
   ``server_error`` stays 502 api_error (the non-stream mirror of the stream-only
   case in test_stream_hardening).
5. the non-stream search path (search-bearing request) gets the same status.

Guards that unclassified failures keep 502 api_error (refusal, malformed events,
recovery validation, framing, transport) already live in test_stream_hardening
(``_assert_nonstream_api_error``), test_nonstream_recovery (``assert_rejected``),
test_native_search (transport/HTML/malformed) and test_native_search_acceptance.
A refusal on the search non-stream path staying 502 is pinned by
test_nonstream_recovery.py:198-203 (``history=True, stream=False``: the replayed
web_search_call makes the request search-bearing; ``assert_rejected`` checks 502 at
:105 and api_error at :119).
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
    MockResponsesServer,
    RealShim,
    _purge_in_process_reasoning_cache_seam,
    lifecycle_for_response,
    structured_error_scenario,
)

# Fabricated backend prose. The client message must come from the shim's fixed
# messages, never from this text.
PROSE_SENTINEL = "FABRICATED_BACKEND_PROSE_V1410_7Q"

# The live 2026-10-13 shape: type and code as recorded in shim.log.
CONTEXT_PAYLOAD = {
    "type": "invalid_request_error",
    "code": "context_length_exceeded",
    "message": PROSE_SENTINEL,
}

# The fixed client message for context_length_exceeded (v1.4.11 B; it was
# "backend context length exceeded" in 1.4.10).
CONTEXT_MESSAGE = "Prompt is too long (backend context length exceeded)"

# Decision 1 (user-confirmed 2026-10-13): the full inverse of the v1.2.10 map.
EXPECTED_STATUS_BY_TYPE = {
    "invalid_request_error": 400,
    "authentication_error": 401,
    "permission_error": 403,
    "not_found_error": 404,
    "rate_limit_error": 429,
    "overloaded_error": 529,
}


class InverseMapUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _purge_in_process_reasoning_cache_seam()
        name = "provider_shim_v1410_inband_%s" % uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, PRODUCTION_SHIM)
        cls.shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.shim)

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.shim._client.aclose())

    def test_inverse_map_is_exact_inverse_of_status_map(self):
        forward = self.shim._ANTHROPIC_ERROR_TYPE_BY_STATUS
        inverse = self.shim._CLIENT_STATUS_BY_ANTHROPIC_ERROR_TYPE
        # One-to-one forward map, so nothing is lost by inverting it.
        self.assertEqual(len(set(forward.values())), len(forward))
        self.assertEqual(inverse, {error_type: status for status, error_type in forward.items()})
        self.assertEqual(inverse, EXPECTED_STATUS_BY_TYPE)
        for status, error_type in forward.items():
            with self.subTest(error_type=error_type):
                self.assertEqual(self.shim._client_status_for_anthropic_error_type(error_type), status)
                self.assertEqual(self.shim._anthropic_error_type_for_status(status), error_type)

    def test_unmapped_types_default_to_502(self):
        for error_type in ("api_error", "-", "", "unknown_type", None, "INVALID_REQUEST_ERROR"):
            with self.subTest(error_type=error_type):
                self.assertEqual(self.shim._client_status_for_anthropic_error_type(error_type), 502)


class InbandStatusLoopbackTests(unittest.TestCase):
    maxDiff = 8000

    def _event_line(self, lines, event):
        matches = [line for line in lines if line.event == event]
        self.assertEqual(len(matches), 1, (event, [line.raw for line in lines]))
        return matches[0]

    def _assert_inband(self, scenario, *, request_bytes, status, error_type, message,
                       backend_code, marker, backend_type=None):
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_raw_messages(request_bytes)
                self.assertEqual(result.status, status, (marker, result.text))
                body = result.json()
                self.assertEqual(body.get("type"), "error", marker)
                error = body.get("error") or {}
                self.assertEqual(error.get("type"), error_type, marker)
                self.assertEqual(error.get("message"), message, marker)
                self.assertNotIn(PROSE_SENTINEL, result.text, marker)
                lines = lifecycle_for_response(shim, result)
                self.assertEqual(self._event_line(lines, "upstream_headers").fields["status"], "200", marker)
                backend_error = self._event_line(lines, "backend_error")
                self.assertEqual(backend_error.fields["anthropic_type"], error_type, marker)
                self.assertEqual(backend_error.fields["backend_code"], backend_code, marker)
                if backend_type is not None:
                    self.assertEqual(backend_error.fields["backend_type"], backend_type, marker)
                terminal = self._event_line(lines, "terminal").fields
                self.assertEqual(terminal["outcome"], "error", marker)
                self.assertEqual(terminal["stream"], "n", marker)
                # The failure arrives after the 200, so the shim never re-sends it,
                # even for a code the classifier marks retryable.
                self.assertEqual(terminal["attempts"], "1", marker)
                self.assertEqual(terminal["retries"], "0", marker)
                self.assertNotIn(PROSE_SENTINEL, shim.captured_stderr(), marker)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def _ordinary_request(self):
        return json.dumps({
            "model": "gpt-fixture", "max_tokens": 256, "stream": False,
            "messages": [{"role": "user", "content": "Exercise the fixture."}],
        }, separators=(",", ":")).encode("utf-8")

    def test_chatgpt_nonstream_context_length_is_400_for_both_inband_events(self):
        for event_type in ("response.failed", "error"):
            with self.subTest(event=event_type):
                scenario = structured_error_scenario(
                    "v1410-context-" + event_type.replace(".", "-"), event_type, CONTEXT_PAYLOAD)
                self._assert_inband(
                    scenario, request_bytes=self._ordinary_request(), status=400,
                    error_type="invalid_request_error",
                    message=CONTEXT_MESSAGE,
                    backend_code="context_length_exceeded",
                    marker="CHATGPT_NONSTREAM_INBAND_CONTEXT_" + event_type)

    def test_chatgpt_nonstream_inband_status_follows_the_full_map(self):
        cases = (
            ("rate_limit_exceeded", 429, "rate_limit_error", "backend rate limit exceeded"),
            ("token_invalidated", 401, "authentication_error", "backend authentication failed"),
            ("server_is_overloaded", 529, "overloaded_error", "backend overloaded"),
            ("insufficient_quota", 400, "invalid_request_error", "backend quota or plan limit reached"),
            ("server_error", 502, "api_error", "backend server error"),
            ("unmodeled_fixture_code", 502, "api_error", "backend request failed"),
        )
        for code, status, error_type, message in cases:
            with self.subTest(code=code):
                scenario = structured_error_scenario(
                    "v1410-map-" + code, "response.failed",
                    {"code": code, "message": PROSE_SENTINEL})
                self._assert_inband(
                    scenario, request_bytes=self._ordinary_request(), status=status,
                    error_type=error_type, message=message, backend_code=code,
                    marker="CHATGPT_NONSTREAM_INBAND_" + code.upper())

    def test_chatgpt_nonstream_inband_code_beats_type(self):
        # Non-stream mirror of test_stream_hardening's stream-only code-precedence
        # case: the classifier checks code before type, so code=server_error wins
        # over type=context_length_exceeded and the failure stays 502 api_error.
        scenario = structured_error_scenario(
            "v1410-code-precedence", "response.failed",
            {"type": "context_length_exceeded", "code": "server_error",
             "message": PROSE_SENTINEL})
        self._assert_inband(
            scenario, request_bytes=self._ordinary_request(), status=502,
            error_type="api_error", message="backend server error",
            backend_code="server_error", backend_type="context_length_exceeded",
            marker="CHATGPT_NONSTREAM_INBAND_CODE_BEATS_TYPE")

    def test_nonstream_search_inband_status_matches_type(self):
        cases = (
            ("response.failed", CONTEXT_PAYLOAD, 400, "invalid_request_error",
             CONTEXT_MESSAGE, "context_length_exceeded"),
            ("error", CONTEXT_PAYLOAD, 400, "invalid_request_error",
             CONTEXT_MESSAGE, "context_length_exceeded"),
            ("response.failed", {"code": "rate_limit_exceeded", "message": PROSE_SENTINEL}, 429,
             "rate_limit_error", "backend rate limit exceeded", "rate_limit_exceeded"),
            ("response.failed", {"code": "server_error", "message": PROSE_SENTINEL}, 502,
             "api_error", "backend server error", "server_error"),
        )
        search_request = json.dumps(fx.search_request(False)).encode("utf-8")
        for event_type, payload, status, error_type, message, code in cases:
            with self.subTest(event=event_type, code=code):
                scenario = structured_error_scenario(
                    "v1410-search-" + code, event_type, payload)
                self._assert_inband(
                    scenario, request_bytes=search_request, status=status,
                    error_type=error_type, message=message, backend_code=code,
                    marker="SEARCH_NONSTREAM_INBAND_%s_%s" % (event_type, code))


if __name__ == "__main__":
    unittest.main()
