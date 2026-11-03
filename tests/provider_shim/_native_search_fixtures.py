"""Shared synthetic fixtures for the native WebSearch bridge tests (shim v1.4.0+).

Every identifier, query, URL, title, answer string and ciphertext below is
FABRICATED for offline tests. The response *shape* (completed web_search_call +
message items, an empty terminal ``output`` array, a query-bearing citation URL and
a non-SSE MIME carrying real SSE framing) mirrors a live subscription response the
shim maintainers observed on 2026-09-08; no value is copied from that response.
The repeated public IANA URLs are placeholders, not a source inventory. These
fixtures certify the shim's translation code, not live provider or client support.

Not a test module (leading underscore): ``unittest discover -p 'test_*.py'`` never
collects it; the ``test_native_search*.py`` modules import it.
"""
import asyncio
import copy
import importlib.util
import json
import unittest

from ._loopback_harness import PRODUCTION_SHIM, USAGE_WITH_CACHE, Scenario, parse_typed_sse

# --- Request-side declarations ---
SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}
FUNCTION = {"name": "WebSearch", "input_schema": {"type": "object", "properties": {}}}
FUNCTION_ITEM = {"type": "function_call", "id": "fc_fixture", "call_id": "call_fixture",
                 "name": "WebSearch", "arguments": "{}"}

# --- Hosted search response items (synthetic) ---
HELP = "https://www.iana.org/help/example-domains"
CITED = HELP + "?utm_source=openai"
RAW_ITEMS = [
    {"type": "web_search_call", "id": "ws_synthetic", "status": "completed",
     "action": {"type": "search", "query": "synthetic public IANA question",
                "queries": ["synthetic public IANA question"],
                "sources": [{"type": "url",
                             "url": HELP if i % 2 == 0 else "https://www.iana.org/domains/reserved"}
                            for i in range(31)]}},
    {"type": "message", "id": "msg_synthetic", "status": "completed", "role": "assistant",
     "phase": "final_answer",
     "content": [{"type": "output_text", "text": "Synthetic answer about IANA.",
                  "annotations": [{"type": "url_citation", "url": CITED, "title": "Example Domains",
                                   "start_index": 0, "end_index": 6}]}]},
]

# --- Hosted page actions (schema-derived from the public OpenAI Responses API
# WebSearchActionOpenPage / WebSearchActionFind shapes; synthetic values) ---
OPEN = {"type": "open_page", "url": "https://example.org/OPEN_URL_SENTINEL?q=x(y)"}
FIND = {"type": "find_in_page", "url": "https://example.org/FIND_URL_SENTINEL",
        "pattern": 'PATTERN_SENTINEL\nquoted "text"'}

# --- Ordinary delta-only truncation fixtures ---
TEXT = "Partial synthetic answer."
DELTA = {"type": "response.output_text.delta", "output_index": 0,
         "content_index": 0, "item_id": "msg_delta_fixture", "delta": TEXT}
TERMINAL = {"type": "response.incomplete", "response": {
    "id": "resp_partial_fixture", "status": "incomplete", "error": None,
    "output": [], "incomplete_details": {"reason": "max_output_tokens"},
    "usage": {"input_tokens": 100, "output_tokens": 6}}}


def action_items(actions):
    """One completed web_search_call per action, each carrying an unknown extension."""
    return [{"type": "web_search_call", "id": "ws_action_" + str(i),
             "status": "completed", "action": copy.deepcopy(action),
             "extension": "ITEM_EXTENSION_SENTINEL"} for i, action in enumerate(actions)]


def search_scenario(items=None, terminal_empty=True):
    """Done events for each item, then a terminal whose output is empty by default."""
    items = copy.deepcopy(RAW_ITEMS if items is None else items)
    complete = {"id": "resp_synthetic", "status": "completed", "error": None,
                "output": items, "usage": copy.deepcopy(USAGE_WITH_CACHE)}
    events = [{"type": "response.output_item.done", "output_index": i, "item": item}
              for i, item in enumerate(items)]
    events.append({"type": "response.completed",
                   "response": {**complete, "output": [] if terminal_empty else items}})
    return Scenario("grounded-synthetic-native-search", events, complete,
                    stream_headers={"Content-Type": "application/octet-stream"})


def search_request(stream, tools=None):
    return {"model": "gpt-fixture", "max_tokens": 256, "stream": stream,
            "messages": [{"role": "user", "content": "fixture public question"}],
            "tools": copy.deepcopy([SEARCH] if tools is None else tools),
            "tool_choice": {"type": "tool", "name": "web_search"}}


def collected_blocks(result, stream):
    """Anthropic content blocks from a JSON body or a reassembled SSE stream."""
    if not stream:
        return result.json()["content"]
    blocks = []
    pending = {}
    for frame in parse_typed_sse(result.body):
        event = frame.data
        if not isinstance(event, dict):
            continue
        if event.get("type") == "content_block_start":
            blocks.append(copy.deepcopy(event["content_block"]))
        elif event.get("type") == "content_block_delta":
            delta = event["delta"]
            index = event["index"]
            if delta["type"] == "input_json_delta":
                pending[index] = pending.get(index, "") + delta["partial_json"]
            elif delta["type"] == "text_delta":
                blocks[index]["text"] += delta["text"]
            elif delta["type"] == "thinking_delta":
                blocks[index]["thinking"] += delta["thinking"]
            elif delta["type"] == "signature_delta":
                blocks[index]["signature"] = delta["signature"]
        elif event.get("type") == "content_block_stop" and event["index"] in pending:
            blocks[event["index"]]["input"] = json.loads(pending.pop(event["index"]))
    return blocks


def probe_body(report):
    return b"".join(message.get("body", b"") for message in report.messages)


def response_body(report, stream):
    """Non-stream JSON body, or the message_delta frame of a streamed probe."""
    raw = probe_body(report)
    if not stream:
        return json.loads(raw)
    frames = parse_typed_sse(raw)
    return next((frame.data for frame in frames if frame.event == "message_delta"), {})


class NativeSearchCase(unittest.TestCase):
    """Loads one private copy of the production shim per test class.

    Each test starts with an empty process-local replay cache. Has no test methods
    of its own, so discovery collects nothing from this base.
    """

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "provider_shim_native_search_%s" % cls.__name__, PRODUCTION_SHIM)
        cls.shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.shim)

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.shim._client.aclose())

    def setUp(self):
        self.shim._SEARCH_REPLAY = self.shim._SearchReplayCache()
