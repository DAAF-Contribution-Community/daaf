"""Shim v1.4.13: no count_tokens calibration from a hosted-search response.

Live shim.log, 2026-10-15: all 10 "count_tokens calibration rejected" lines were
hosted-search sub-requests (msgs=1 tools=1, hosted_projection outcome=valid) with
ratios 9.6-16 tokens/byte, against accepted ordinary ratios of 0.19-0.25. Hosted
search usage counts server-fetched content that the inbound body length cannot
represent. The band guard (_COUNT_RATIO_MIN/MAX) rejected those observations, but
logged a WARNING on every search, and a large search-bearing body (a main-loop
request replaying web_search_call items) could land inside the band and be
accepted at a skewed ratio. The two search call sites no longer calibrate.

1. a search-bearing response with a small body and input_tokens ~8500 leaves
   _count_ratio_state unchanged and logs no "calibration rejected" warning
   (non-stream and stream, both lanes);
2. a search-bearing response with a ~20 KB body at an in-band ratio (~0.43, which
   the guard would accept) leaves _count_ratio_state unchanged;
3. control: an ordinary (non-search) response at ~0.2 still updates the EMA.

Every case asserts the terminal line's usage=backend (the branch that used to
calibrate was reached); the search cases also see the DEBUG skip line exactly
once through a recording wrapper on the module logger's debug method.

Modeled on test_nonstream_recovery.py (deep-copied _count_ratio_state, compared
after the probe). Provider-free: the controlled in-process ASGI probe, fabricated
values only.
"""

from __future__ import annotations

import copy
import json
import unittest

from . import _native_search_fixtures as fx
from ._loopback_harness import controlled_asgi_probe, events_scenario

REJECTED = "count_tokens calibration rejected"
SKIPPED = "count_tokens calibration skipped reason=hosted_search"


def _usage(input_tokens):
    # No cached-token detail, so every call site's input total equals input_tokens.
    return {"input_tokens": input_tokens, "output_tokens": 17,
            "total_tokens": input_tokens + 17}


def _search_scenario(input_tokens):
    scenario = fx.search_scenario()
    scenario.nonstream_response["usage"] = _usage(input_tokens)
    scenario.stream_events[-1]["response"]["usage"] = _usage(input_tokens)
    return scenario


def _ordinary_scenario(input_tokens):
    item = {"type": "message", "id": "msg_v1413_calibration", "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Synthetic ordinary answer."}]}
    terminal = {"id": "resp_v1413_calibration", "status": "completed", "error": None,
                "output": [copy.deepcopy(item)], "usage": _usage(input_tokens)}
    events = [{"type": "response.output_item.done", "output_index": 0, "item": item},
              {"type": "response.completed", "response": terminal}]
    return events_scenario("v1413-ordinary-calibration", events, nonstream_response=terminal)


def _search_body(stream, filler_chars=0):
    request = fx.search_request(stream)
    if filler_chars:
        request["messages"][0]["content"] = "fixture public question " + "x" * filler_chars
    return json.dumps(request).encode("utf-8")


def _ordinary_body(stream, filler_chars):
    return json.dumps({
        "model": "gpt-fixture", "max_tokens": 256, "stream": stream,
        "messages": [{"role": "user", "content": "Synthetic input " + "y" * filler_chars}],
    }).encode("utf-8")


class SearchCalibrationTests(unittest.TestCase):
    maxDiff = 8000

    def _probe(self, scenario, body, stream, mode):
        observed = {}

        debug_messages = []

        def configure(module):
            observed["module"] = module
            observed["ratio"] = copy.deepcopy(module._count_ratio_state)
            # INTENT: see the DEBUG skip line, which the probe's INFO+ log capture
            #   does not record. The wrapper records the formatted message only.
            original_debug = module.log.debug

            def recording_debug(msg, *args, **kwargs):
                debug_messages.append(msg % args if args else msg)
                return original_debug(msg, *args, **kwargs)
            module.log.debug = recording_debug

        report = controlled_asgi_probe(scenario=scenario, stream=stream, backend_mode=mode,
                                       raw_request_body=body, configure_module=configure)
        observed["debug"] = debug_messages
        self.assertIsNone(report.raised)
        self.assertEqual(report.messages[0]["status"], 200)
        self.assertNotIn("outcome=error", report.logs)
        terminals = [line for line in report.lifecycle if line.event == "terminal"]
        self.assertEqual(len(terminals), 1, report.logs)
        # usage=backend proves the response reached the (former) calibration branch,
        # which runs only for backend-reported usage.
        self.assertEqual(terminals[0].fields["usage"], "backend", terminals[0].raw)
        return report, observed

    def _assert_skipped(self, report, observed):
        self.assertEqual(observed["module"]._count_ratio_state, observed["ratio"])
        self.assertEqual(observed["debug"].count(SKIPPED), 1, observed["debug"])
        self.assertNotIn(REJECTED, report.logs)
        self.assertNotIn("count_tokens calibrated", report.logs)

    def test_small_search_body_with_large_usage_is_not_calibrated(self):
        for mode in ("chatgpt", "openai"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    body = _search_body(stream)
                    # The pre-1.4.13 observation would be ~8500/len(body), far above the band.
                    self.assertGreater(8500 / len(body), 1.0)
                    report, observed = self._probe(_search_scenario(8500), body, stream, mode)
                    self._assert_skipped(report, observed)

    def test_large_search_body_at_an_in_band_ratio_is_not_calibrated(self):
        for mode in ("chatgpt", "openai"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    body = _search_body(stream, filler_chars=20000)
                    tokens = round(0.43 * len(body))
                    # The guard would ACCEPT this observation; only the skip keeps it out.
                    ratio = tokens / len(body)
                    self.assertGreater(len(body), 20000)
                    self.assertTrue(0.02 <= ratio <= 1.0, ratio)
                    report, observed = self._probe(_search_scenario(tokens), body, stream, mode)
                    self._assert_skipped(report, observed)

    def test_ordinary_response_still_updates_the_ratio(self):
        for mode, stream in (("chatgpt", False), ("openai", False), ("openai", True)):
            with self.subTest(mode=mode, stream=stream):
                body = _ordinary_body(stream, filler_chars=4000)
                tokens = round(0.2 * len(body))
                report, observed = self._probe(_ordinary_scenario(tokens), body, stream, mode)
                module = observed["module"]
                before = observed["ratio"]
                after = module._count_ratio_state
                self.assertEqual(after["obs"], before["obs"] + 1)
                if before["obs"] == 0:
                    # First observation replaces the prior outright.
                    self.assertAlmostEqual(after["ratio"], tokens / len(body), places=9)
                else:
                    self.assertNotEqual(after["ratio"], before["ratio"])
                self.assertIn("count_tokens calibrated ratio=", report.logs)
                self.assertNotIn(SKIPPED, observed["debug"])


if __name__ == "__main__":
    unittest.main()
