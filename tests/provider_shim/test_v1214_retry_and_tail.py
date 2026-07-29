"""v1.2.14 R4 (classification-driven retry policy) + R5 (SSE tail tolerance).

These deterministic red/green contracts exercise the two behaviors added in
Dispatch A2 against the real shim subprocess via the loopback harness:

- R4: retry gating is driven by the unified error classifier. A recognized
  deterministic code overrides the bare-status fallback (insufficient_quota-coded
  429 fails fast; rate_limit_exceeded is retried with a parsed/advertised delay),
  while a bare status still reproduces today's RETRY_STATUSES behavior. A
  rate-limit-class delay beyond the 60s cap fails fast instead of stalling.
- R5: a fully-formed terminal event at EOF whose trailing blank line was trimmed
  is flushed (see test_stream_hardening for the clean-tail pin); a malformed tail
  AFTER a terminal frame is counted and ignored (this file).
"""

from __future__ import annotations

import json
import time
import unittest

from ._loopback_harness import (
    USAGE,
    MockResponsesServer,
    RealShim,
    backend_status_scenario,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
    raw_sse_scenario,
    sequenced_attempt_scenario,
)


class ProviderShimRetryAndTailTests(unittest.TestCase):
    maxDiff = 12000

    def _terminal(self, shim: object, result: object) -> dict[str, str]:
        lines = lifecycle_for_response(shim, result)
        terminals = [line for line in lines if line.event == "terminal"]
        self.assertEqual(len(terminals), 1, [line.raw for line in lines])
        return terminals[0].fields

    # --- R4: classification-driven retry gating ---

    def test_insufficient_quota_429_fails_fast_no_retry(self) -> None:
        # A recognized deterministic code OVERRIDES the retryable 429 status: an
        # insufficient_quota-coded 429 is non-retryable and surfaces as
        # invalid_request_error, with exactly one upstream request (no retry).
        scenario = backend_status_scenario("quota-429", 429)
        scenario.stream_error_body = (
            b'{"error":{"type":"insufficient_quota","code":"insufficient_quota",'
            b'"message":"You exceeded your current quota."}}'
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 429, result.text)
                self.assertEqual(
                    result.json()["error"]["type"], "invalid_request_error")
                backend.assert_request_counts(responses=1)
                terminal = self._terminal(shim, result)
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(terminal["retry_delay_source"], "-")

    def test_rate_limit_exceeded_429_parsed_delay_retries(self) -> None:
        # A rate_limit_exceeded code with an embedded "try again in <n>s" hint is
        # retried; the delay is parsed from the message NUMBER only and the source
        # is recorded as `parsed`. A tiny 0.05s delay keeps the suite fast.
        scenario = sequenced_attempt_scenario("rl-parsed", [429, 200])
        scenario.stream_error_body = (
            b'{"error":{"type":"rate_limit_exceeded","code":"rate_limit_exceeded",'
            b'"message":"Rate limit reached. Please try again in 0.05s. Contact us."}}'
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                backend.assert_request_counts(responses=2)
                terminal = self._terminal(shim, result)
                self.assertEqual(terminal["retries"], "1")
                self.assertEqual(terminal["retry_delay_source"], "parsed")

    def test_bare_429_retries_with_header_delay_source(self) -> None:
        # A bare 429 (no recognized code) still retries via the RETRY_STATUSES
        # fallback. With a Retry-After header present the delay source is `header`
        # (value 0 keeps the retry instant).
        scenario = sequenced_attempt_scenario(
            "bare-429", [429, 200], headers=[{"Retry-After": "0"}, {}])
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                backend.assert_request_counts(responses=2)
                terminal = self._terminal(shim, result)
                self.assertEqual(terminal["retries"], "1")
                self.assertEqual(terminal["retry_delay_source"], "header")

    def test_rate_limit_delay_beyond_cap_fails_fast(self) -> None:
        # A rate-limit-class advertised delay beyond the 60s cap fails fast with
        # rate_limit_error rather than sleeping — the client owns the long wait. One
        # upstream request, no multi-minute internal stall.
        scenario = backend_status_scenario("rl-over-cap", 429, retry_after="120")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                start = time.monotonic()
                result = shim.post_messages(stream=False)
                elapsed = time.monotonic() - start
                self.assertEqual(result.status, 429, result.text)
                self.assertEqual(
                    result.json()["error"]["type"], "rate_limit_error")
                backend.assert_request_counts(responses=1)
                self.assertLess(elapsed, 30.0, "must not sleep the 120s advertised delay")
                terminal = self._terminal(shim, result)
                self.assertEqual(terminal["retries"], "0")
                self.assertEqual(terminal["retry_delay_source"], "header")

    def test_oversized_error_body_is_bounded_and_classified_by_status(self) -> None:
        # F3: a >=400 error body far larger than any real envelope (2 MiB of junk on a
        # 503) must not drive an unbounded parse in _open_backend_stream's retry path.
        # The body is truncated to MAX_ERROR_BODY_BYTES (1 MiB) before _plan_retry; the
        # truncated junk fails envelope parse and falls back to HTTP-status gating (503
        # is in RETRY_STATUSES), so the attempt is retried and the next (200) succeeds.
        # Retry-After: 0 keeps the retry instant and pins the delay source deterministically.
        scenario = sequenced_attempt_scenario(
            "f3-oversized-error-body", [503, 200], headers=[{"Retry-After": "0"}, {}])
        scenario.stream_error_body = b"x" * (2 * 1024 * 1024)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=2)
                terminal = self._terminal(shim, result)
                self.assertEqual(terminal["retries"], "1")
                self.assertEqual(terminal["retry_delay_source"], "header")

    # --- R5: SSE tail tolerance ---

    def test_eof_malformed_tail_after_terminal_flushes_and_counts(self) -> None:
        # A complete terminal event missing its blank-line boundary, followed by a
        # truncated non-data field at EOF: the terminal event is flushed (success)
        # and the trailing malformed bytes are counted for observability, not raised.
        terminal = {
            "type": "response.completed",
            "response": {
                "id": "resp_tail",
                "status": "completed",
                "output": [],
                "usage": dict(USAGE),
            },
        }
        frame = (
            b"data: "
            + json.dumps(terminal, separators=(",", ":")).encode()
            + b"\nevent: response.trailing-truncated"
        )
        scenario = raw_sse_scenario("eof-malformed-tail-after-terminal", [frame])
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                shim.assert_offline_contract()
                terminal_fields = self._terminal(shim, result)
                self.assertGreaterEqual(int(terminal_fields["unknown_events"]), 1)
                backend.assert_request_counts(responses=1)


if __name__ == "__main__":
    unittest.main()
