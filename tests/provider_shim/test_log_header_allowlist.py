"""Shim v1.4.9: backend-error log lines carry only allowlisted response headers.

Live chatgpt-lane 4xx responses carry ``x-codex-turn-state`` (an opaque encrypted
backend session token) and account credit fields. Before v1.4.9 a ``x-codex-*``
prefix rule copied every such header into the ``| headers: ...`` part of the error
line in shim.log. These loopback tests send fake values for those headers (plus a
fake ``set-cookie``) on each error path that formats headers, and assert that none
of the fake values reach the captured shim log while allowlisted request IDs and
rate-limit numerics still do. Provider-free: a mock Responses backend, no network.
"""

from __future__ import annotations

import unittest

from ._loopback_harness import (
    MockResponsesServer,
    RealShim,
    backend_status_scenario,
)


# Fake values only. Each is distinctive so a substring check is unambiguous.
FAKE_TURN_STATE = "gAAAAABfakeTurnStateTokenNEVERLOGME0123456789"
FAKE_COOKIE_VALUE = "fakeSessionCookieNEVERLOGME42"
FAKE_CREDITS_BALANCE = "987654321"

LEAKY_HEADERS = {
    "x-codex-turn-state": FAKE_TURN_STATE,
    "set-cookie": f"__Secure-session={FAKE_COOKIE_VALUE}; Path=/; HttpOnly",
    "x-codex-credits-balance": FAKE_CREDITS_BALANCE,
    "x-codex-credits-has-credits": "true",
    "x-codex-plan-type": "pro",
    # Allowlisted diagnostics that must still appear.
    "x-oai-request-id": "req_fixture_allowlisted",
    "x-codex-primary-used-percent": "37",
}

FORBIDDEN_SUBSTRINGS = (
    FAKE_TURN_STATE,
    FAKE_COOKIE_VALUE,
    FAKE_CREDITS_BALANCE,
    "x-codex-turn-state",
    "set-cookie",
    "x-codex-credits",
    "x-codex-plan-type",
)


class LogHeaderAllowlistTests(unittest.TestCase):
    maxDiff = 8000

    def _assert_clean(self, logs: str, marker: str) -> None:
        # The error line for the path under test must exist, so the absence checks
        # below are meaningful (not vacuously true on a silent log).
        self.assertIn(marker, logs)
        self.assertIn("| headers: ", logs)
        for forbidden in FORBIDDEN_SUBSTRINGS:
            self.assertNotIn(forbidden, logs, f"{forbidden!r} leaked into shim log")
        self.assertIn("x-oai-request-id=req_fixture_allowlisted", logs)
        self.assertIn("x-codex-primary-used-percent=37", logs)

    def test_chatgpt_nonstream_adapter_error_drops_token_and_cookie(self) -> None:
        # The live leak path: chatgpt lane, client stream=false, backend 4xx.
        scenario = backend_status_scenario("hygiene-adapter-400", 400)
        scenario.stream_headers = dict(LEAKY_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertGreaterEqual(result.status, 400, result.text)
                logs = shim.captured_stderr()
                shim.assert_offline_contract()
        self._assert_clean(logs, "backend ChatGPT non-stream adapter error")

    def test_chatgpt_stream_error_drops_token_and_cookie(self) -> None:
        scenario = backend_status_scenario("hygiene-stream-400", 400)
        scenario.stream_headers = dict(LEAKY_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                logs = shim.captured_stderr()
                shim.assert_offline_contract()
        self._assert_clean(logs, "backend stream error")

    def test_chatgpt_stream_retry_line_drops_token_and_cookie(self) -> None:
        # A retryable status logs one "retrying" line per attempt through the same
        # header formatter before the final error line.
        scenario = backend_status_scenario("hygiene-stream-429", 429, retry_after="0")
        scenario.stream_headers.update(LEAKY_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                logs = shim.captured_stderr()
                shim.assert_offline_contract()
        self.assertIn("retrying in", logs)
        self.assertIn("retry-after=0", logs)
        self._assert_clean(logs, "backend stream error")

    def test_openai_nonstream_error_drops_token_and_cookie(self) -> None:
        # The openai lane's non-stream upstream POST has its own error line.
        scenario = backend_status_scenario("hygiene-openai-400", 400)
        scenario.stream_headers = dict(LEAKY_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False)
                self.assertGreaterEqual(result.status, 400, result.text)
                logs = shim.captured_stderr()
                shim.assert_offline_contract()
        self._assert_clean(logs, "backend error status=400")


if __name__ == "__main__":
    unittest.main()
