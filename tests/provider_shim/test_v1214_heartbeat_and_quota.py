"""Deterministic contracts for the v1.2.14 A3b work: R6 downstream heartbeat +
idle-gap telemetry, and D1 quota-window header capture / allowlist prefix.

1. R6 heartbeat: during a held-open silent upstream phase (content already
   emitted, terminal delayed without a disconnect), Anthropic ``ping`` frames are
   emitted between the content and the terminal, never splitting a downstream
   frame; ``SHIM_PING_INTERVAL_S=0`` disables them in an otherwise identical run.
2. R6 idle-gap telemetry: the terminal record carries ``max_idle_gap_ms`` sized to
   the held-open gap.
3. D1 quota snapshot: a chatgpt-lane 2xx with synthetic ``x-codex-*`` headers emits
   exactly one ``event=quota_snapshot`` line of numeric/enum fields (absent headers
   render as ``-``); the openai lane and a chatgpt 4xx emit none.
4. D1 allowlist prefix: an ``x-codex-*`` header is captured in the diagnostic
   header line while an unrelated header stays excluded.
"""

from __future__ import annotations

import unittest

from ._loopback_harness import (
    MockResponsesServer,
    RealShim,
    backend_status_scenario,
    full_response_scenario,
    heartbeat_text_scenario,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
)


# Synthetic subscription-quota header surface modeled on the live chatgpt-lane
# capture (notes/07 §8). Secondary-window headers are intentionally omitted so the
# "absent header -> field renders as -" contract is exercised.
QUOTA_HEADERS = {
    "x-codex-plan-type": "pro",
    "x-codex-active-limit": "premium",
    "x-codex-primary-used-percent": "30",
    "x-codex-primary-window-minutes": "10080",
    "x-codex-primary-reset-after-seconds": "425943",
    "x-codex-credits-has-credits": "true",
    "x-codex-credits-balance": "0",
    "x-codex-credits-unlimited": "false",
}


class ProviderShimV1214HeartbeatTests(unittest.TestCase):
    maxDiff = 12000

    def _terminal_fields(self, lines: list[object]) -> dict[str, str]:
        matches = [line for line in lines if line.event == "terminal"]
        self.assertEqual(len(matches), 1, [line.raw for line in lines])
        return matches[0].fields

    def test_pings_bridge_silent_gap_between_content_and_terminal(self) -> None:
        # A single text turn whose terminal is delayed by a silent 0.8s gap; with a
        # 0.1s ping interval the shim must bridge it with several ping frames.
        scenario = heartbeat_text_scenario("hb-basic", gap_s=0.8)
        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend, "chatgpt", env_overrides={"SHIM_PING_INTERVAL_S": "0.1"}
            ) as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                # Frame-integrity oracle: the full success-stream shape still holds
                # (one message_start/delta/stop, non-overlapping monotonic blocks,
                # message_stop last) even with pings interleaved.
                report = lifecycle_report(frames)
                self.assertEqual([kind for _idx, kind in report.starts], ["text"])
                # A ping that split a content frame would surface as a raw (non-dict)
                # parsed frame; every frame must be a well-formed dict or [DONE].
                for frame in frames:
                    self.assertTrue(
                        isinstance(frame.data, dict) or frame.data == "[DONE]",
                        ("split/garbled frame", frame.raw_data),
                    )
                types = [
                    frame.data.get("type")
                    for frame in frames
                    if isinstance(frame.data, dict)
                ]
                # Multiple pings, all strictly between message_start and message_delta.
                self.assertGreaterEqual(types.count("ping"), 2, types)
                start_at = types.index("message_start")
                delta_at = types.index("message_delta")
                for position, kind in enumerate(types):
                    if kind == "ping":
                        self.assertGreater(position, start_at)
                        self.assertLess(
                            position, delta_at, "ping after terminal message_delta"
                        )
                # Every ping frame is exactly {"type": "ping"} — never a content frame.
                for frame in frames:
                    if isinstance(frame.data, dict) and frame.data.get("type") == "ping":
                        self.assertEqual(frame.data, {"type": "ping"})
                terminal = self._terminal_fields(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                # max_idle_gap_ms is present and plausibly sized for the ~0.8s gap.
                self.assertIn("max_idle_gap_ms", terminal)
                self.assertGreaterEqual(int(terminal["max_idle_gap_ms"]), 400)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_ping_interval_zero_disables_heartbeat(self) -> None:
        # The identical held-open scenario with SHIM_PING_INTERVAL_S=0 must produce
        # no ping frames while still completing cleanly.
        scenario = heartbeat_text_scenario("hb-disabled", gap_s=0.8)
        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend, "chatgpt", env_overrides={"SHIM_PING_INTERVAL_S": "0"}
            ) as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual([kind for _idx, kind in report.starts], ["text"])
                types = [
                    frame.data.get("type")
                    for frame in frames
                    if isinstance(frame.data, dict)
                ]
                self.assertNotIn("ping", types)
                terminal = self._terminal_fields(lifecycle_for_response(shim, result))
                self.assertEqual(terminal["outcome"], "success")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)


class ProviderShimV1214QuotaSnapshotTests(unittest.TestCase):
    maxDiff = 12000

    def _quota_lines(self, lines: list[object]) -> list[object]:
        return [line for line in lines if line.event == "quota_snapshot"]

    def test_chatgpt_2xx_emits_one_quota_snapshot_with_expected_fields(self) -> None:
        scenario = full_response_scenario()
        scenario.stream_headers = dict(QUOTA_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                parse_typed_sse(result.body)
                lines = lifecycle_for_response(shim, result)
                quota = self._quota_lines(lines)
                self.assertEqual(len(quota), 1, [line.raw for line in lines])
                fields = quota[0].fields
                self.assertEqual(fields["plan_type"], "pro")
                self.assertEqual(fields["active_limit"], "premium")
                self.assertEqual(fields["primary_used_pct"], "30")
                self.assertEqual(fields["primary_window_min"], "10080")
                self.assertEqual(fields["primary_reset_s"], "425943")
                self.assertEqual(fields["credits_has"], "true")
                self.assertEqual(fields["credits_balance"], "0")
                self.assertEqual(fields["credits_unlimited"], "false")
                # Absent secondary-window headers render as "-".
                self.assertEqual(fields["secondary_used_pct"], "-")
                self.assertEqual(fields["secondary_window_min"], "-")
                self.assertEqual(fields["secondary_reset_s"], "-")
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_openai_lane_emits_no_quota_snapshot(self) -> None:
        scenario = full_response_scenario()
        scenario.stream_headers = dict(QUOTA_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                parse_typed_sse(result.body)
                lines = lifecycle_for_response(shim, result)
                self.assertEqual(self._quota_lines(lines), [])
                shim.assert_offline_contract()

    def test_chatgpt_4xx_emits_no_quota_snapshot(self) -> None:
        scenario = backend_status_scenario("quota-4xx", 400)
        scenario.stream_headers = dict(QUOTA_HEADERS)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                # In-band error stream: HTTP 200, error surfaced as an SSE event.
                self.assertEqual(result.status, 200, result.text)
                lines = lifecycle_for_response(shim, result)
                self.assertEqual(self._quota_lines(lines), [])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_allowlist_prefix_captures_x_codex_excludes_unrelated(self) -> None:
        # A chatgpt 4xx routes its headers through _diag_headers. The x-codex-*
        # header must be captured by the new prefix rule; an unrelated header (not
        # exact- or prefix-allowlisted) must stay excluded from the diagnostic line.
        scenario = backend_status_scenario("prefix-4xx", 400)
        scenario.stream_headers = {
            "x-codex-anything": "capturedval",
            "x-unrelated-header": "excludedval",
        }
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_for_response(shim, result)
                logs = shim.captured_stderr()
                self.assertIn("x-codex-anything=capturedval", logs)
                self.assertNotIn("x-unrelated-header", logs)
                self.assertNotIn("excludedval", logs)
                shim.assert_offline_contract()


if __name__ == "__main__":
    unittest.main()
