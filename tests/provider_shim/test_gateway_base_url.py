"""Offline tests for SHIM_BACKEND_BASE_URL normalization (shim v1.4.7).

Institutional OpenAI-compatible gateways (e.g. a university API toolkit) are used
by pasting their base URL into environment_settings.txt. The shim must accept the
forms people paste: surrounding whitespace, a trailing "/", or a URL that already
ends in "/responses". Each case is driven through a real shim subprocess against a
loopback mock backend; the forwarded request path proves the normalized URL, and
the captured shim log is checked for the (fabricated) API key.
"""

from __future__ import annotations

import unittest

from ._loopback_harness import (
    FAKE_OPENAI_KEY,
    MockResponsesServer,
    RealShim,
    full_response_scenario,
)

STRIP_WARNING = "SHIM_BACKEND_BASE_URL ended in /responses"


class GatewayBaseUrlTests(unittest.TestCase):
    maxDiff = 8000

    def _run(self, template: str):
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend, "openai", backend_base_url_template=template
            ) as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                health = dict(shim.health)
                expected_base = shim.backend_base_url
        return backend, shim, health, expected_base

    def _assert_clean(self, backend, shim, health, expected_base, *, warned: bool):
        # One forwarded request, to exactly {base}/responses.
        self.assertEqual(len(backend.responses_requests), 1)
        self.assertEqual(backend.responses_requests[0].path, "/v1/responses")
        # /health reports the normalized backend URL.
        self.assertEqual(health["backend"], expected_base)
        # The key reaches the backend as a Bearer header, never the log.
        headers = {k.lower(): v for k, v in backend.responses_requests[0].headers.items()}
        self.assertEqual(headers.get("authorization"), f"Bearer {FAKE_OPENAI_KEY}")
        self.assertNotIn(FAKE_OPENAI_KEY, shim.stderr)
        self.assertIn(f"backend={expected_base} ", shim.stderr)
        self.assertEqual(shim.stderr.count(STRIP_WARNING), 1 if warned else 0)

    def test_trailing_slash_is_dropped(self) -> None:
        self._assert_clean(*self._run("{base}/"), warned=False)

    def test_surrounding_whitespace_is_trimmed(self) -> None:
        self._assert_clean(*self._run("  {base}  "), warned=False)

    def test_pasted_responses_suffix_is_stripped_and_logged_once(self) -> None:
        self._assert_clean(*self._run("{base}/responses"), warned=True)

    def test_pasted_responses_suffix_with_trailing_slash(self) -> None:
        self._assert_clean(*self._run(" {base}/responses/ "), warned=True)


if __name__ == "__main__":
    unittest.main()
