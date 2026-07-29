"""Deterministic red/green contracts for provider-shim v1.3.6 prompt-cache observability.

Covers the V6-R1/R2/R3/R4 client-visible + telemetry surface introduced in shim v1.3.6:

* R1/R3 client mapping — OpenAI `usage.input_tokens` INCLUDES the cached prefix, so the
  Anthropic-native usage block SUBTRACTS it (`input_tokens = total - cached`) and reports the
  cached count as `cache_read_input_tokens`, preserving the sum invariant. `cache_creation_input_tokens`
  is always 0 (OpenAI reports no cache-write count) and both cache fields are ALWAYS emitted.
* R2 terminal record — the lane-agnostic terminal log line carries `cached_tokens` (the OpenAI
  total's cached subset, or the `-` absent-convention). `state.input_tokens` stays the OpenAI TOTAL.
* R4 /health — a new top-level `prompt_cache` block whose cumulative counters advance per terminal.

Design test-plan items 2-8 (2026-07-22_v136_PromptCacheObservability_Design.md § Test plan).
"""

from __future__ import annotations

import unittest

from ._loopback_harness import (
    USAGE,
    USAGE_WITH_CACHE,
    MockResponsesServer,
    RealShim,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
    terminal_contract_scenario,
)


# The prompt-cache detail resolves to input=19 (uncached remainder) + cache_read=12 on the wire,
# while the terminal record and /health denominators keep the OpenAI total of 31.
_TOTAL = USAGE_WITH_CACHE["input_tokens"]          # 31 (OpenAI total, includes cached prefix)
_CACHED = USAGE_WITH_CACHE["input_tokens_details"]["cached_tokens"]  # 12
_REMAINDER = _TOTAL - _CACHED                      # 19 (client-visible Anthropic input_tokens)
_OUTPUT = USAGE_WITH_CACHE["output_tokens"]        # 17


def _cache_hit_scenario(name: str):
    """A clean, completed terminal whose usage carries a valid prompt-cache detail."""
    return terminal_contract_scenario(
        name,
        "response.completed",
        status="completed",
        output=[],
        usage=USAGE_WITH_CACHE,
    )


def _usage_scenario(name: str, usage):
    """A clean, completed terminal carrying an arbitrary (possibly malformed) usage object."""
    return terminal_contract_scenario(
        name,
        "response.completed",
        status="completed",
        output=[],
        usage=usage,
    )


class ProviderShimPromptCacheObservabilityTests(unittest.TestCase):
    maxDiff = 12000

    # --- helpers -------------------------------------------------------------------------

    def _terminal_fields(self, shim: RealShim, result) -> dict:
        """Resolve the single terminal lifecycle record for one response."""
        lines = lifecycle_for_response(shim, result)
        terminal = next(line for line in lines if line.event == "terminal")
        return terminal.fields

    def _stream_client_usage(self, result) -> dict:
        """Extract the client-visible message_delta usage block from a streaming response."""
        frames = parse_typed_sse(result.body)
        lifecycle_report(frames)
        events = [frame.data for frame in frames if isinstance(frame.data, dict)]
        delta = next(event for event in events if event.get("type") == "message_delta")
        return delta["usage"]

    def _health_prompt_cache(self, shim: RealShim) -> dict:
        health = shim.get_health()
        self.assertEqual(health.status, 200, health.text)
        return health.json()

    # --- item 2: streaming lane, cache-hit -----------------------------------------------

    def test_streaming_cache_hit_maps_usage_and_records_terminal(self) -> None:
        scenario = _cache_hit_scenario("prompt-cache-stream")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                usage = self._stream_client_usage(result)
                # Subtraction mapping: total(31) - cached(12) = 19; cache_read carries the 12.
                self.assertEqual(
                    usage,
                    {
                        "input_tokens": _REMAINDER,
                        "output_tokens": _OUTPUT,
                        "cache_read_input_tokens": _CACHED,
                        "cache_creation_input_tokens": 0,
                    },
                )
                # Terminal record keeps the OpenAI TOTAL input_tokens and the cached subset.
                fields = self._terminal_fields(shim, result)
                self.assertEqual(fields["cached_tokens"], str(_CACHED))
                self.assertEqual(fields["input_tokens"], str(_TOTAL))
                self.assertEqual(fields["usage"], "backend")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- item 3: both non-streaming lanes, cache-hit -------------------------------------

    def test_nonstream_both_lanes_map_usage_and_record_terminal(self) -> None:
        for mode in ("chatgpt", "openai"):
            with self.subTest(mode=mode):
                scenario = _cache_hit_scenario(f"prompt-cache-ns-{mode}")
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        message = result.json()
                        self.assertEqual(
                            message.get("usage"),
                            {
                                "input_tokens": _REMAINDER,
                                "output_tokens": _OUTPUT,
                                "cache_read_input_tokens": _CACHED,
                                "cache_creation_input_tokens": 0,
                            },
                        )
                        # The private carry key never reaches the wire.
                        self.assertNotIn("_cached_tokens", message.get("usage", {}))
                        self.assertNotIn("_cached_tokens", message)
                        fields = self._terminal_fields(shim, result)
                        self.assertEqual(fields["cached_tokens"], str(_CACHED))
                        self.assertEqual(fields["input_tokens"], str(_TOTAL))
                        self.assertEqual(fields["usage"], "backend")
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=1)

    # --- item 4: absent detail (backward compatibility) ----------------------------------

    def test_absent_detail_emits_zero_cache_fields_and_dash_terminal(self) -> None:
        # The plain USAGE fixture carries no input_tokens_details — the pre-v1.3.6 world. The
        # client sees the full OpenAI input as input_tokens (no subtraction) with both cache
        # fields present as 0; the terminal renders the `-` absent-convention.
        scenario = _usage_scenario("prompt-cache-absent", dict(USAGE))
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                stream_result = shim.post_messages(stream=True)
                self.assertEqual(stream_result.status, 200, stream_result.text)
                usage = self._stream_client_usage(stream_result)
                self.assertEqual(
                    usage,
                    {
                        "input_tokens": USAGE["input_tokens"],
                        "output_tokens": USAGE["output_tokens"],
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                )
                fields = self._terminal_fields(shim, stream_result)
                self.assertEqual(fields["cached_tokens"], "-")
                self.assertEqual(fields["input_tokens"], str(USAGE["input_tokens"]))
                shim.assert_offline_contract()

    # --- item 5: malformed detail battery ------------------------------------------------

    def test_malformed_detail_is_treated_as_absent_without_error(self) -> None:
        # string / negative / boolean / non-dict details all resolve to ABSENT: the response
        # still succeeds, the client sees no cached tokens, and the terminal renders `-`.
        malformed_details = (
            ("string", "12"),
            ("negative", -5),
            ("boolean", True),
            ("non-dict-details", None),  # input_tokens_details set to a non-dict below
        )
        for label, cached_value in malformed_details:
            with self.subTest(case=label):
                if label == "non-dict-details":
                    usage = {
                        "input_tokens": _TOTAL,
                        "output_tokens": _OUTPUT,
                        "input_tokens_details": "not-a-dict",
                    }
                else:
                    usage = {
                        "input_tokens": _TOTAL,
                        "output_tokens": _OUTPUT,
                        "input_tokens_details": {"cached_tokens": cached_value},
                    }
                scenario = _usage_scenario(f"prompt-cache-malformed-{label}", usage)
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        message = result.json()
                        self.assertEqual(message.get("stop_reason"), "end_turn")
                        self.assertEqual(
                            message.get("usage"),
                            {
                                "input_tokens": _TOTAL,
                                "output_tokens": _OUTPUT,
                                "cache_read_input_tokens": 0,
                                "cache_creation_input_tokens": 0,
                            },
                        )
                        fields = self._terminal_fields(shim, result)
                        self.assertEqual(fields["cached_tokens"], "-")
                        self.assertEqual(fields["outcome"], "success")
                        shim.assert_offline_contract()

    # --- item 6: clamp guard (cached > input) --------------------------------------------

    def test_cached_exceeding_input_total_is_treated_as_absent(self) -> None:
        # A malformed upstream where cached_tokens > input_tokens must fail open to ABSENT,
        # never a negative client-visible input_tokens.
        usage = {
            "input_tokens": _TOTAL,
            "output_tokens": _OUTPUT,
            "input_tokens_details": {"cached_tokens": _TOTAL + 5},
        }
        scenario = _usage_scenario("prompt-cache-clamp", usage)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                self.assertEqual(
                    message.get("usage"),
                    {
                        "input_tokens": _TOTAL,
                        "output_tokens": _OUTPUT,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                )
                fields = self._terminal_fields(shim, result)
                self.assertEqual(fields["cached_tokens"], "-")
                self.assertEqual(fields["input_tokens"], str(_TOTAL))
                shim.assert_offline_contract()

    # --- item 7: /health prompt_cache block + counter advancement ------------------------

    def test_health_prompt_cache_block_present_and_top_level(self) -> None:
        scenario = _cache_hit_scenario("prompt-cache-health-shape")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                health = self._health_prompt_cache(shim)
                # ADDS a top-level key (distinct from the nested reasoning_cache block).
                self.assertIn("prompt_cache", health)
                block = health["prompt_cache"]
                self.assertEqual(
                    set(block),
                    {
                        "requests_with_usage",
                        "requests_with_cached",
                        "cached_tokens_total",
                        "input_tokens_total",
                    },
                )
                # The prompt-cache counters are NOT promoted to top-level /health keys.
                for key in block:
                    self.assertNotIn(key, {k for k in health if k != "prompt_cache"})

    def test_health_counters_advance_on_a_cached_terminal(self) -> None:
        scenario = _cache_hit_scenario("prompt-cache-health-cached")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                before = self._health_prompt_cache(shim)["prompt_cache"]
                # Fresh subprocess: no terminal has fired yet, so every counter starts at 0.
                self.assertEqual(
                    before,
                    {
                        "requests_with_usage": 0,
                        "requests_with_cached": 0,
                        "cached_tokens_total": 0,
                        "input_tokens_total": 0,
                    },
                )
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_for_response(shim, result)  # ensure the terminal bump has landed
                after = self._health_prompt_cache(shim)["prompt_cache"]
                # One cached terminal: requests +1, cached-subset +1, totals advance by the
                # cached count (12) and the OpenAI input TOTAL (31), respectively.
                self.assertEqual(
                    after,
                    {
                        "requests_with_usage": 1,
                        "requests_with_cached": 1,
                        "cached_tokens_total": _CACHED,
                        "input_tokens_total": _TOTAL,
                    },
                )
                shim.assert_offline_contract()

    def test_health_present_but_absent_cached_counts_usage_only(self) -> None:
        # A terminal with parsed backend usage but NO cached detail advances requests_with_usage
        # and input_tokens_total, but leaves the cached-subset counters at 0 (adjudication 3:
        # cached counters advance only when cached_tokens > 0).
        scenario = _usage_scenario("prompt-cache-health-absent", dict(USAGE))
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_for_response(shim, result)
                after = self._health_prompt_cache(shim)["prompt_cache"]
                self.assertEqual(
                    after,
                    {
                        "requests_with_usage": 1,
                        "requests_with_cached": 0,
                        "cached_tokens_total": 0,
                        "input_tokens_total": USAGE["input_tokens"],
                    },
                )
                shim.assert_offline_contract()


if __name__ == "__main__":
    unittest.main()
