"""Native search: hosted search / open_page / find_in_page action sequences (v1.4.2+).

Page-action fixtures are schema-derived from the public OpenAI Responses API
(WebSearchActionSearch / OpenPage / Find and the SDK param union) and are
synthetic offline compatibility evidence, NOT live observations. The search
envelope reuses the shared synthetic fixtures.

"v1.4.8" marks tests written to the v1.4.8 tolerant contract: unrecognized
hosted-action shapes and unusable consulted sources are skipped with a WARNING
(extra page-action fields ignored) instead of failing the turn. Non-completed
statuses and limits still fail closed. These fail against v1.4.7 by design.
"""
import copy
import json
import unittest
from unittest import mock

from . import _loopback_harness as h
from . import _native_search_fixtures as fx

OPEN, FIND, action_items = fx.OPEN, fx.FIND, fx.action_items


def client_websearch_contract(blocks, query="fixture"):
    """Fabricated model of how the Claude Code WebSearch tool consumes a turn.

    Written for this test from the client's observable contract as pinned against
    Claude Code 2.1.261 — NOT vendor code: text runs between hosted calls are kept
    as strings; each web_search_tool_result array becomes one "Links:" entry (or
    "No links found." when empty); searchCount is max(server_tool_use count,
    result count). Later client versions may differ; this guards the shim's side
    of that contract (page actions must survive as text, not as ranked links).
    """
    results, text, calls, result_blocks = [], "", 0, 0
    for block in blocks:
        if block["type"] == "server_tool_use":
            calls += 1
            if text.strip():
                results.append(text.strip())
            text = ""
            continue
        if block["type"] == "web_search_tool_result":
            result_blocks += 1
            if not isinstance(block["content"], list):
                results.append("Web search error: %s" % block["content"].get("error_code"))
                continue
            results.append({"tool_use_id": block["tool_use_id"],
                            "content": [{"title": r["title"], "url": r["url"]} for r in block["content"]]})
        if block["type"] == "text":
            text += block["text"]
    if text.strip():
        results.append(text.strip())
    serialized = 'Web search results for query: "%s"\n\n' % query
    for entry in results:
        if isinstance(entry, str):
            serialized += entry + "\n\n"
        elif entry["content"]:
            serialized += "Links: " + json.dumps(entry["content"], separators=(",", ":")) + "\n\n"
        else:
            serialized += "No links found.\n\n"
    return {"searchCount": max(calls, result_blocks), "serialized": serialized}


class HostedActionTests(fx.NativeSearchCase):
    def test_mixed_repeated_actions_wire_replay_and_ordinary_continuation(self):
        actions = [fx.RAW_ITEMS[0]["action"], OPEN, FIND, OPEN, FIND]
        items = action_items(actions) + copy.deepcopy(fx.RAW_ITEMS[1:])
        items.insert(0, {"type": "reasoning", "id": "rs_action", "summary": [],
                         "encrypted_content": "CIPHERTEXT_SENTINEL"})
        items.append({"type": "function_call", "id": "fc_action", "call_id": "call_action",
                      "name": "WebSearch", "arguments": "{}"})
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    with h.MockResponsesServer(fx.search_scenario(items)) as backend:
                        with h.RealShim(backend, mode) as shim:
                            shim.assert_offline_contract()
                            request = fx.search_request(stream, [fx.SEARCH, fx.FUNCTION])
                            request["tool_choice"] = {"type": "auto"}
                            result = shim.post_raw_messages(json.dumps(request).encode())
                            self.assertEqual(result.status, 200)
                            blocks = fx.collected_blocks(result, stream)
                            hosted = [b for b in blocks if b["type"] == "server_tool_use"]
                            self.assertEqual(len(hosted), 5)
                            self.assertEqual([b["input"] for b in hosted[1:]], actions[1:])
                            self.assertEqual(len({b["id"] for b in hosted}), 5)
                            self.assertEqual(sum(b["type"] == "web_search_tool_result" for b in blocks), 1)
                            text = "".join(b.get("text", "") for b in blocks)
                            self.assertEqual(text.count("Hosted web action: open_page"), 2)
                            self.assertEqual(text.count("Hosted web action: find_in_page"), 2)
                            self.assertIn("x%28y%29", text)
                            self.assertIn("does not verify page content or a pattern match", text)
                            self.assertEqual(blocks[-2]["type"], "tool_use")
                            follow = fx.search_request(stream, [])
                            follow["tool_choice"] = {"type": "none"}
                            follow["messages"] += [{"role": "assistant", "content": blocks},
                                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_action", "content": "ordinary fixture result"}]}]
                            backend.scenario = fx.search_scenario([fx.RAW_ITEMS[1]])
                            continuation = shim.post_raw_messages(json.dumps(follow).encode())
                            self.assertEqual(continuation.status, 200)
                            self.assertEqual(backend.responses_requests[-1].body["input"][1:1 + len(items)], items)
                            self.assertEqual(fx.collected_blocks(continuation, stream)[0]["text"], fx.RAW_ITEMS[1]["content"][0]["text"])
                            logs = shim.captured_stderr()
                            for sentinel in ("OPEN_URL_SENTINEL", "FIND_URL_SENTINEL", "PATTERN_SENTINEL", "ITEM_EXTENSION_SENTINEL", "CIPHERTEXT_SENTINEL"):
                                self.assertNotIn(sentinel, logs)
                            self.assertIn("open_page_count=2", logs)
                            self.assertIn("find_in_page_count=2", logs)
                            self.assertIn("action_count=5", logs)
                            self.assertIn("outcome=no_hosted_actions", logs)

    def test_page_only_sequences_have_replay_anchor_without_ranked_results(self):
        for actions in ([OPEN], [FIND], [OPEN, FIND], [{"type": "open_page"}],
                        [{"type": "open_page", "url": None}], [{**FIND, "pattern": ""}]):
            with self.subTest(actions=actions):
                items = action_items(actions)
                response = self.shim._search_projection({"status": "completed", "output": items}, "fixture", self.shim._ToolRegistry([fx.SEARCH]))
                blocks = response["content"]
                self.assertFalse(any(b["type"] == "web_search_tool_result" for b in blocks))
                self.assertEqual([b["input"] for b in blocks if b["type"] == "server_tool_use"], actions)
                self.assertEqual(self.shim._messages_to_input([{"role": "assistant", "content": blocks}])[0], items)
                if actions[0].get("url") is None:
                    self.assertIn("URL not supplied by provider", blocks[1]["text"])
                bad = copy.deepcopy(blocks)
                bad[-1]["text"] += "tamper"
                with self.assertRaises(self.shim._InvalidRequestError):
                    self.shim._messages_to_input([{"role": "assistant", "content": bad}])

    def test_valid_and_missing_optional_evidence_wire_matrix(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with h.MockResponsesServer(fx.search_scenario()) as backend:
                    with h.RealShim(backend, mode) as shim:
                        shim.assert_offline_contract()
                        for action in (OPEN, FIND, {"type": "open_page"}, {"type": "open_page", "url": None}):
                            backend.scenario = fx.search_scenario(action_items([action]))
                            result = shim.post_raw_messages(json.dumps(fx.search_request(stream)).encode())
                            self.assertEqual(result.status, 200)
                            blocks = fx.collected_blocks(result, stream)
                            self.assertEqual(blocks[0]["input"], action)
                            self.assertEqual([b["type"] for b in blocks], ["server_tool_use", "text"])
                        self.assertIn("outcome=url_not_supplied", shim.captured_stderr())

    def test_v148_unrecognized_action_shapes_degrade_with_precise_buckets(self):
        # v1.4.8 (each case was a fatal "hosted ... invalid/unsupported" error):
        # "skipped" = the hosted item is dropped from display (raw replay intact) and
        # the answer still arrives; "page" = extra open_page fields are ignored. A
        # search whose listed sources are ALL unusable is skipped as "malformed"
        # rather than projected as an empty (zero-result) search it never was.
        # The fixed-bucket diagnostic outcome is unchanged, and no provider value
        # (query, URL, pattern, title, extension) reaches the body or the logs.
        clean = "https://example.org/page"
        cases = [
            (None, "malformed", "skipped"),
            ({}, "malformed", "skipped"),
            ({"type": ["TYPE_SENTINEL"]}, "malformed", "skipped"),
            ({"type": "TYPE_SENTINEL"}, "unsupported", "skipped"),
            ({**OPEN, "url": 7}, "malformed", "skipped"),
            ({**OPEN, "url": "javascript:URL_SENTINEL"}, "malformed", "skipped"),
            ({"type": "open_page", "url": clean, "sources": ["SOURCE_SENTINEL"]}, "valid", "page"),
            ({"type": "find_in_page", "pattern": "PATTERN_SENTINEL"}, "missing_evidence", "skipped"),
            ({"type": "find_in_page", "url": FIND["url"]}, "missing_evidence", "skipped"),
            ({**FIND, "url": None}, "malformed", "skipped"),
            ({**FIND, "pattern": {"private": "PATTERN_SENTINEL"}}, "malformed", "skipped"),
            ({"type": "search"}, "missing_evidence", "skipped"),
            ({"type": "search", "sources": None}, "missing_evidence", "skipped"),
            ({"type": "search", "sources": "SOURCES_SENTINEL"}, "malformed", "skipped"),
            ({"type": "search", "query": {"private": "QUERY_SENTINEL"}, "sources": []}, "malformed", "skipped"),
            ({"type": "search", "queries": "QUERIES_SENTINEL", "sources": []}, "malformed", "skipped"),
            ({"type": "search", "queries": ["QUERY_SENTINEL", None], "sources": []}, "malformed", "skipped"),
            ({"type": "search", "sources": [{"type": "url", "url": {"private": "URL_SENTINEL"}}]}, "malformed", "skipped"),
            ({"type": "search", "sources": [{"type": "url", "url": "javascript:URL_SENTINEL"}]}, "malformed", "skipped"),
            ({"type": "search", "sources": [{"type": "url", "url": OPEN["url"], "title": ["TITLE_SENTINEL"]}]}, "malformed", "skipped"),
        ]
        answer = fx.RAW_ITEMS[1]["content"][0]["text"].encode()
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                for action, outcome, projected in cases:
                    with self.subTest(mode=mode, stream=stream, action=action):
                        items = action_items([action]) + [copy.deepcopy(fx.RAW_ITEMS[1])]
                        report = h.controlled_asgi_probe(scenario=fx.search_scenario(items),
                            raw_request_body=json.dumps(fx.search_request(stream)).encode(), backend_mode=mode, stream=stream)
                        self.assertIsNone(report.raised)
                        body = fx.probe_body(report)
                        self.assertEqual(report.messages[0]["status"], 200)
                        self.assertNotIn(b'"type": "error"', body)
                        self.assertIn(answer, body)
                        self.assertIn("outcome=" + outcome, report.logs)
                        self.assertNotIn("SENTINEL", body.decode() + report.logs)
                        if projected == "skipped":
                            self.assertNotIn(b"server_tool_use", body)
                        else:
                            self.assertIn(b"server_tool_use", body)
                        self.assertEqual(b"web_search_tool_result" in body, projected == "zero_results")
                        if projected != "page":
                            self.assertIn("WARNING", report.logs)
                        if stream:
                            self.assertIn(b"event: message_stop", body)
                        self.assertEqual(report.upstream_calls, 1)
                        self.assertEqual(report.pending_task_count, 0)
                        self.assertEqual(report.stream_close_calls, 1)

    def test_v148_unexpected_source_entries_are_skipped_with_warning(self):
        # v1.4.8: consulted-source entries that are not url objects used to fail
        # the whole turn ("hosted search source is invalid"). They are now skipped
        # with a WARNING; well-formed sources are still projected and no skipped
        # content reaches the client body or the logs.
        action = {"type": "search", "query": "fixture", "sources": [
            {"type": "url", "url": fx.HELP},
            "SOURCE_SENTINEL",
            {"type": "SOURCE_TYPE_SENTINEL", "url": "https://example.org/SKIPPED_SENTINEL"},
        ]}
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    report = h.controlled_asgi_probe(scenario=fx.search_scenario(action_items([action]) + [fx.RAW_ITEMS[1]]),
                        raw_request_body=json.dumps(fx.search_request(stream)).encode(), backend_mode=mode, stream=stream)
                    self.assertIsNone(report.raised)
                    self.assertEqual(report.messages[0]["status"], 200)
                    raw = fx.probe_body(report)
                    self.assertNotIn(b"event: error", raw)
                    self.assertIn(b"web_search_tool_result", raw)
                    self.assertIn(fx.HELP.encode(), raw)
                    self.assertNotIn(b"SENTINEL", raw)
                    self.assertNotIn("SENTINEL", report.logs)
                    self.assertIn("WARNING", report.logs)
                    self.assertEqual(report.stream_close_calls, 1)
                    self.assertEqual(report.pending_task_count, 0)

    def test_status_buckets_are_private_and_precise(self):
        for status in ("failed", "incomplete", "in_progress", "searching", "STATUS_SENTINEL", {}, None):
            item = action_items([OPEN])[0]
            item["status"] = status
            with mock.patch.object(self.shim, "_lifecycle_event") as event:
                with self.assertRaises(self.shim._ProtocolError):
                    self.shim._validate_hosted_action(item, observe=True)
            fields = event.call_args.kwargs
            self.assertEqual(fields["action_status"], status if isinstance(status, str) and status in ("failed", "incomplete", "in_progress", "searching") else "unknown")
            self.assertNotIn("SENTINEL", json.dumps(fields))

    def test_zero_results_and_no_hosted_actions_are_distinct(self):
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with h.MockResponsesServer(fx.search_scenario()) as backend:
                    with h.RealShim(backend, mode) as shim:
                        shim.assert_offline_contract()
                        request = fx.search_request(stream)
                        request["tool_choice"] = {"type": "auto"}
                        backend.scenario = fx.search_scenario(action_items([{"type": "search", "sources": []}]))
                        zero = shim.post_raw_messages(json.dumps(request).encode())
                        self.assertEqual(fx.collected_blocks(zero, stream)[1]["content"], [])
                        backend.scenario = fx.search_scenario([fx.RAW_ITEMS[1]])
                        absent = shim.post_raw_messages(json.dumps(request).encode())
                        self.assertFalse(any(b["type"] == "server_tool_use" for b in fx.collected_blocks(absent, stream)))
                        logs = shim.captured_stderr()
                        self.assertIn("outcome=zero_results", logs)
                        self.assertIn("outcome=no_hosted_actions", logs)

    def test_diagnostics_are_fixed_buckets_and_deduplicate_done_events(self):
        action = copy.deepcopy(fx.RAW_ITEMS[0]["action"])
        action.update(query="QUERY_SENTINEL", queries=["QUERIES_SENTINEL"])
        action["sources"] = [{"type": "url", "url": "https://example.org/URL_SENTINEL", "title": "TITLE_SENTINEL"}]
        items = action_items([action, OPEN, FIND])
        c = self.shim._SearchCollector(self.shim._ToolRegistry([fx.SEARCH]))
        with mock.patch.object(self.shim, "_lifecycle_event") as events:
            for event in fx.search_scenario(items).stream_events[:-1]:
                c.event(event)
                c.event(event)
        self.assertEqual(events.call_count, 3)
        for call in events.call_args_list:
            self.assertEqual(set(call.kwargs), {"action_type", "action_status", "outcome", "evidence", "source_count"})
            self.assertNotIn("SENTINEL", json.dumps(call.kwargs))

    def test_page_actions_obey_existing_call_source_and_projection_limits(self):
        items = action_items([OPEN, FIND])
        for field, limit in (("_SEARCH_MAX_SOURCES", 1), ("_SEARCH_MAX_PROJECTED_BYTES", 100)):
            with mock.patch.object(self.shim, field, limit), self.assertRaises(self.shim._ProtocolError):
                self.shim._search_projection({"status": "completed", "output": items}, "fixture", self.shim._ToolRegistry([fx.SEARCH]))
        with self.assertRaisesRegex(self.shim._ProtocolError, "ceiling exceeded"):
            self.shim._search_projection({"status": "completed", "output": items}, "fixture", self.shim._ToolRegistry([{**fx.SEARCH, "max_uses": 1}]))
        self.assertEqual(len(self.shim._SEARCH_REPLAY.groups), 0)

    def test_client_contract_retains_page_evidence_and_zero_distinction(self):
        # Replaces the draft's byte-pinned extracted client snippets (vendor code,
        # not redistributable) with the fabricated contract model above.
        cases = []
        for actions in ([OPEN, FIND], [{"type": "open_page"}], [{"type": "search", "sources": []}]):
            cases.append(self.shim._search_projection({"status": "completed", "output": action_items(actions)}, "fixture", self.shim._ToolRegistry([fx.SEARCH]))["content"])
        cases.append([{"type": "text", "text": "No hosted action fixture."}])
        observed = [client_websearch_contract(blocks) for blocks in cases]
        self.assertEqual([o["searchCount"] for o in observed], [2, 1, 1, 0])
        self.assertIn("Hosted web action: open_page", observed[0]["serialized"])
        self.assertIn("Hosted web action: find_in_page", observed[0]["serialized"])
        self.assertIn("PATTERN_SENTINEL", observed[0]["serialized"])
        self.assertNotIn("Links:", observed[0]["serialized"])
        self.assertNotIn("No links found.", observed[0]["serialized"])
        self.assertIn("URL not supplied by provider", observed[1]["serialized"])
        self.assertIn("No links found.", observed[2]["serialized"])
        self.assertNotIn("No links found.", observed[3]["serialized"])


if __name__ == "__main__":
    unittest.main()
