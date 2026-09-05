"""Offline tests for the GPT-6 Astra effort floor and model listing (2026-09-05).

Astra's reasoning.effort enum is {low, medium, high, xhigh, max} — it rejects
"none" (OpenAI Astra model page, primary source). The shim applies a single
model-conditional floor at request build: an Astra-family request whose resolved
effort is "none" is rewritten to "low"; every other model forwards its resolved
effort unchanged. These are provider-free tests — a mock Responses backend
captures the forwarded payload, no live network.
"""

from __future__ import annotations

import json
import unittest
import urllib.request

from ._loopback_harness import (
    MockResponsesServer,
    RealShim,
    _direct_request,
    full_response_scenario,
)


class AstraEffortFloorTests(unittest.TestCase):
    maxDiff = 8000

    def _forwarded_effort(self, backend) -> object:
        # The mock backend records each forwarded Responses payload; the effort the
        # shim actually sent lives at reasoning.effort of the single request.
        self.assertEqual(len(backend.responses_requests), 1)
        reasoning = backend.responses_requests[0].body.get("reasoning")
        self.assertIsInstance(reasoning, dict)
        return reasoning.get("effort")

    def test_models_list_includes_astra(self) -> None:
        # (a) /v1/models advertises the Astra slug alongside the existing entries.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                request = urllib.request.Request(
                    f"{shim.base_url}/v1/models", method="GET"
                )
                result = _direct_request(request, timeout=5.0)
        self.assertEqual(result.status, 200)
        ids = {entry["id"] for entry in result.json()["data"]}
        self.assertIn("openai/gpt-6-astra", ids)
        # Existing entries must be preserved (additive change only).
        self.assertIn("openai/gpt-5.6-sol", ids)
        self.assertIn("openai/gpt-5.5", ids)

    def test_astra_none_effort_clamped_to_low(self) -> None:
        # (b1) Astra + resolved "none" -> "low".
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False, model="gpt-6-astra#none")
                self.assertEqual(result.status, 200)
        self.assertEqual(self._forwarded_effort(backend), "low")

    def test_non_astra_none_effort_passes_through(self) -> None:
        # (b2) A non-Astra model with the same "none" signal is forwarded unchanged
        # — the floor is Astra-only.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False, model="gpt-fixture#none")
                self.assertEqual(result.status, 200)
        self.assertEqual(self._forwarded_effort(backend), "none")

    def test_astra_max_and_xhigh_pass_through(self) -> None:
        # (c) Astra's supported high-reasoning levels are forwarded unmodified.
        for effort in ("max", "xhigh"):
            with self.subTest(effort=effort):
                scenario = full_response_scenario()
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "openai") as shim:
                        result = shim.post_messages(
                            stream=False, model=f"gpt-6-astra#{effort}"
                        )
                        self.assertEqual(result.status, 200)
                self.assertEqual(self._forwarded_effort(backend), effort)

    def test_provider_prefixed_astra_none_clamped(self) -> None:
        # (d) Provider-prefixed slug: the terminal slug (after dropping "openai/")
        # is what the floor matches, so "#none" still clamps to "low".
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(
                    stream=False, model="openai/gpt-6-astra#none"
                )
                self.assertEqual(result.status, 200)
        self.assertEqual(self._forwarded_effort(backend), "low")

    def test_astra_thinking_disabled_clamped_to_low(self) -> None:
        # (e) The inbound thinking:{"type":"disabled"} toggle is tier-1 of the
        # effort resolver and maps to "none" (_EFFORT_DISABLED). For Astra that
        # resolved "none" is then rewritten to "low" by the same model-conditional
        # floor — the disable-toggle path reaches the clamp exactly like "#none".
        # post_messages carries no thinking field, so build the raw body directly.
        scenario = full_response_scenario()
        body = {
            "model": "gpt-6-astra",
            "max_tokens": 256,
            "stream": False,
            "thinking": {"type": "disabled"},
            "messages": [{"role": "user", "content": "Exercise the fixture."}],
        }
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_raw_messages(
                    json.dumps(body, separators=(",", ":")).encode("utf-8")
                )
                self.assertEqual(result.status, 200)
        self.assertEqual(self._forwarded_effort(backend), "low")

    def test_astra_default_effort_high_not_clamped(self) -> None:
        # (f) A bare Astra request with NO effort signal (no output_config.effort,
        # no disabled-thinking, no "#<effort>" suffix, no SHIM_REASONING_EFFORT in
        # the harness base env) falls through all four resolver tiers to the default
        # "high". high != "none", so the Astra floor does NOT fire — the request is
        # forwarded unclamped, confirming the clamp is narrowly none-only.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False, model="gpt-6-astra")
                self.assertEqual(result.status, 200)
        self.assertEqual(self._forwarded_effort(backend), "high")

    def test_astra_1m_family_slug_none_clamped(self) -> None:
        # (g) The "[1m]" hint variant is a recognized Astra family slug
        # (_ASTRA_FAMILY_SLUGS = {gpt-6-astra, gpt-6-astra[1m]}), matched on the
        # provider-prefix- and effort-suffix-stripped terminal slug, so "#none"
        # still clamps to "low" for the 1m family member.
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(
                    stream=False, model="gpt-6-astra[1m]#none"
                )
                self.assertEqual(result.status, 200)
        self.assertEqual(self._forwarded_effort(backend), "low")


if __name__ == "__main__":
    unittest.main()
