"""Shim v1.4.8: WebSearch responses degrade gracefully instead of failing hard.

Response side only: an unrecognized hosted action, source or citation is skipped
with a WARNING, while status and identity checks still fail closed; on a lane
that cannot exclude domains upstream (ChatGPT/Codex), blocked_domains are honoured
by removing matching sources and citations from the projected result, with a
note. The request-side tolerance contracts (dated versions, blocked_domains
mapping, disable_parallel_tool_use) live in test_native_search.py. Wire values are
synthetic (see _native_search_fixtures); nothing here certifies live behavior.
"""

from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from . import _native_search_fixtures as fx
from ._loopback_harness import (
    MockResponsesServer,
    RealShim,
    _purge_in_process_reasoning_cache_seam,
)


GOOD_URL = fx.HELP
UNKNOWN_SENTINEL = "UNKNOWN_ACTION_PAYLOAD_SENTINEL_6T"
BLOCKED_NOTE = ("this backend can't exclude domains during search; results from "
                "blocked domains were removed afterwards")

SEARCH_ITEM = {
    "type": "web_search_call", "id": "ws_tolerant_a", "status": "completed",
    "action": {"type": "search", "query": "synthetic tolerant query", "sources": [
        {"type": "url", "url": GOOD_URL},
        {"type": "url", "url": "javascript:alert(1)"},
        {"type": "future_source", "ref": UNKNOWN_SENTINEL},
    ]},
}
UNKNOWN_ITEM = {
    "type": "web_search_call", "id": "ws_tolerant_b", "status": "completed",
    "action": {"type": "future_action", "payload": UNKNOWN_SENTINEL},
}
MESSAGE_ITEM = {
    "type": "message", "id": "msg_tolerant", "status": "completed", "role": "assistant",
    "content": [{"type": "output_text", "text": "Synthetic tolerant answer.", "annotations": [
        {"type": "url_citation", "url": "javascript:void(0)", "title": "bad", "start_index": 0, "end_index": 3},
        {"type": "url_citation", "url": GOOD_URL, "title": "Example Domains", "start_index": 0, "end_index": 9},
    ]}],
}
# Blocked-domain fixtures: iana.org and its subdomains are blocked; a look-alike
# host that merely ends in the same letters (notiana.org) is not.
KEPT_URL = "https://example.org/kept-page"
LOOKALIKE_URL = "https://notiana.org/lookalike"
MIXED_SEARCH_ITEM = {
    "type": "web_search_call", "id": "ws_blocked_mix", "status": "completed",
    "action": {"type": "search", "query": "synthetic blocked query", "sources": [
        {"type": "url", "url": GOOD_URL},
        {"type": "url", "url": "https://iana.org/root"},
        {"type": "url", "url": KEPT_URL, "title": "Kept"},
        {"type": "url", "url": LOOKALIKE_URL, "title": "Look-alike"},
    ]},
}
MIXED_MESSAGE_ITEM = {
    "type": "message", "id": "msg_blocked_mix", "status": "completed", "role": "assistant",
    "content": [{"type": "output_text", "text": "Synthetic blocked answer.", "annotations": [
        {"type": "url_citation", "url": GOOD_URL, "title": "Blocked cite", "start_index": 0, "end_index": 9},
        {"type": "url_citation", "url": KEPT_URL, "title": "Kept cite", "start_index": 0, "end_index": 9},
    ]}],
}


class ResponseToleranceTests(fx.NativeSearchCase):
    @classmethod
    def setUpClass(cls):
        # Start the in-process module load from an empty reasoning-cache seam.
        _purge_in_process_reasoning_cache_seam()
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.shim._WARNED_ONCE.clear()
        self.registry = self.shim._ToolRegistry([fx.SEARCH], {"type": "tool", "name": "web_search"})

    def _project(self, items, registry=None):
        response = {"status": "completed", "output": copy.deepcopy(items)}
        return self.shim._search_projection(response, "gpt-fixture", registry or self.registry)

    def test_unexpected_action_source_and_citation_are_skipped_not_fatal(self):
        with self.assertLogs(self.shim.log, level="WARNING") as captured:
            message = self._project([SEARCH_ITEM, UNKNOWN_ITEM, MESSAGE_ITEM])
        blocks = message["content"]
        self.assertEqual([b["type"] for b in blocks],
                         ["server_tool_use", "web_search_tool_result", "text", "text"])
        self.assertEqual(blocks[1]["content"],
                         [{"type": "web_search_result", "url": GOOD_URL, "title": "Example Domains"}])
        self.assertEqual(blocks[0]["id"], blocks[1]["tool_use_id"])
        self.assertIn("[Example Domains](" + GOOD_URL + ")", blocks[3]["text"])
        self.assertNotIn("javascript:", json.dumps(blocks))
        logs = "\n".join(captured.output)
        for label in ("unrecognized shape", "consulted source", "invalid URL"):
            self.assertIn(label, logs)
        self.assertNotIn(UNKNOWN_SENTINEL, logs)
        self.assertNotIn(UNKNOWN_SENTINEL, json.dumps(message))
        # The raw inventory (including the skipped item) still forms one replay group.
        self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 1)

    def test_all_hosted_items_skipped_delivers_text_without_replay_group(self):
        message = self._project([UNKNOWN_ITEM, MESSAGE_ITEM])
        self.assertEqual([b["type"] for b in message["content"]], ["text", "text"])
        self.assertEqual(message["stop_reason"], "end_turn")
        self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 0)
        # Nothing displayable at all: a plain note instead of an empty message.
        message = self._project([UNKNOWN_ITEM])
        self.assertEqual(len(message["content"]), 1)
        self.assertEqual(message["content"][0]["type"], "text")
        self.assertIn("could not display", message["content"][0]["text"])
        missing_sources = copy.deepcopy(SEARCH_ITEM)
        del missing_sources["action"]["sources"]
        page_with_extras = {"type": "web_search_call", "id": "ws_page", "status": "completed",
                            "action": {"type": "open_page", "url": GOOD_URL, "extra": UNKNOWN_SENTINEL}}
        message = self._project([missing_sources, page_with_extras, MESSAGE_ITEM])
        self.assertEqual(message["content"][0]["input"], {"type": "open_page", "url": GOOD_URL})
        self.assertNotIn(UNKNOWN_SENTINEL, json.dumps(message))

    def test_collector_accepts_unrecognized_action_but_status_still_fails_closed(self):
        events = fx.search_scenario([SEARCH_ITEM, UNKNOWN_ITEM, MESSAGE_ITEM]).stream_events
        collector = self.shim._SearchCollector(self.registry)
        terminal = None
        for event in events:
            terminal = collector.event(copy.deepcopy(event)) or terminal
        self.assertEqual(len(terminal["output"]), 3)
        for status in ("failed", "in_progress"):
            with self.subTest(status=status):
                broken = copy.deepcopy(UNKNOWN_ITEM)
                broken["status"] = status
                with self.assertRaises(self.shim._ProtocolError):
                    self._project([SEARCH_ITEM, broken, MESSAGE_ITEM])
        with self.assertRaises(self.shim._ProtocolError):
            self._project([{**SEARCH_ITEM, "id": 7}, MESSAGE_ITEM])

    def test_blocked_domains_filtered_from_results_on_chatgpt_lane(self):
        # The chatgpt lane cannot send the exclusion upstream, so the projection
        # removes sources and citations on a blocked host (or any subdomain of it)
        # and says so in one note; look-alike hosts and other domains are kept.
        declaration = {**fx.SEARCH, "blocked_domains": ["IANA.org"]}
        with mock.patch.object(self.shim, "SHIM_BACKEND_MODE", "chatgpt"):
            registry = self.shim._ToolRegistry([declaration], {"type": "tool", "name": "web_search"})
        self.assertEqual(registry.blocked_domains, ["iana.org"])
        message = self._project([MIXED_SEARCH_ITEM, MIXED_MESSAGE_ITEM], registry)
        blocks = message["content"]
        results = next(b for b in blocks if b["type"] == "web_search_tool_result")["content"]
        self.assertEqual([r["url"] for r in results], [KEPT_URL, LOOKALIKE_URL])
        text = "".join(b.get("text", "") for b in blocks)
        self.assertIn("[Kept cite](" + KEPT_URL + ")", text)
        self.assertNotIn("Blocked cite", text)
        for blocked_host in ("//www.iana.org", "//iana.org"):
            self.assertNotIn(blocked_host, json.dumps(blocks))
        self.assertEqual(text.count(BLOCKED_NOTE), 1)
        # The filtered projection still anchors one replay group for later turns.
        self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 1)

    def test_no_filter_or_note_on_openai_lane_or_without_search_results(self):
        declaration = {**fx.SEARCH, "blocked_domains": ["iana.org"]}
        with mock.patch.object(self.shim, "SHIM_BACKEND_MODE", "openai"):
            registry = self.shim._ToolRegistry([declaration], {"type": "tool", "name": "web_search"})
        # openai: the backend enforces filters.blocked_domains; the shim adds nothing.
        message = self._project([MIXED_SEARCH_ITEM, MIXED_MESSAGE_ITEM], registry)
        results = next(b for b in message["content"] if b["type"] == "web_search_tool_result")["content"]
        self.assertEqual(len(results), 4)
        self.assertNotIn(BLOCKED_NOTE, json.dumps(message))
        # chatgpt, but no search results to filter: no note either.
        with mock.patch.object(self.shim, "SHIM_BACKEND_MODE", "chatgpt"):
            registry = self.shim._ToolRegistry([declaration], {"type": "auto"})
        message = self._project([MIXED_MESSAGE_ITEM], registry)
        self.assertNotIn(BLOCKED_NOTE, json.dumps(message))


class ToleranceTransportTests(unittest.TestCase):
    def test_unexpected_item_is_skipped_end_to_end_and_replays(self):
        items = [SEARCH_ITEM, UNKNOWN_ITEM, MESSAGE_ITEM]
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    with MockResponsesServer(fx.search_scenario(items)) as backend:
                        with RealShim(backend, mode) as shim:
                            result = shim.post_raw_messages(json.dumps(fx.search_request(stream)).encode())
                            self.assertEqual(result.status, 200, result.text)
                            self.assertIn("server_tool_use", result.text)
                            self.assertIn("Synthetic tolerant answer.", result.text)
                            self.assertNotIn(UNKNOWN_SENTINEL, result.text)
                            logs = shim.captured_stderr()
                            self.assertIn("skipped a hosted web action", logs)
                            self.assertNotIn(UNKNOWN_SENTINEL, logs)
                            if stream:
                                continue
                            follow = fx.search_request(False, [])
                            follow["tool_choice"] = {"type": "none"}
                            follow["messages"] += [{"role": "assistant", "content": result.json()["content"]},
                                                   {"role": "user", "content": "continue"}]
                            backend.scenario = fx.search_scenario([MESSAGE_ITEM])
                            replay = shim.post_raw_messages(json.dumps(follow).encode())
                            self.assertEqual(replay.status, 200, replay.text)
                            self.assertEqual(backend.responses_requests[-1].body["input"][1:4], items)

    def test_blocked_domains_filtered_end_to_end_on_chatgpt_lane(self):
        items = [MIXED_SEARCH_ITEM, MIXED_MESSAGE_ITEM]
        tools = [{**fx.SEARCH, "blocked_domains": ["iana.org"]}]
        for stream in (False, True):
            with self.subTest(stream=stream):
                with MockResponsesServer(fx.search_scenario(items)) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_raw_messages(
                            json.dumps(fx.search_request(stream, tools)).encode())
                        self.assertEqual(result.status, 200, result.text)
                        blocks = fx.collected_blocks(result, stream)
                        results = next(b for b in blocks if b["type"] == "web_search_tool_result")
                        self.assertEqual([r["url"] for r in results["content"]],
                                         [KEPT_URL, LOOKALIKE_URL])
                        self.assertIn(BLOCKED_NOTE, json.dumps(blocks))
                        for blocked_host in ("//www.iana.org", "//iana.org"):
                            self.assertNotIn(blocked_host, json.dumps(blocks))
                        # Upstream never sees an unsupported filter key.
                        self.assertNotIn("filters", backend.responses_requests[-1].body["tools"][0])
                        logs = shim.captured_stderr()
                        self.assertIn("cannot exclude domains during search", logs)
                        self.assertNotIn("iana.org", logs)


if __name__ == "__main__":
    unittest.main()
