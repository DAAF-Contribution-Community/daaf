"""Deterministic contracts for the v1.2.14 R3 tolerant stream reducer (Dispatch A3a).

The R3 doctrine is STRICT EMIT, TOLERANT ACCEPT: the reducer accepts interleaved /
out-of-order / null / malformed-non-load-bearing upstream shapes that pre-R3 failed
on, while the DOWNSTREAM Anthropic SSE stream stays strictly non-overlapping and
serialized. These tests pin:

1. Serialized wire is BYTE-IDENTICAL to the pre-R3 single-slot reducer (the
   non-negotiable regression gate — the tolerant scheduler must not perturb the
   common serialized path).
2. Interleaved two-tool wire (second tool added while first open, alternating arg
   deltas) → two non-overlapping tool_use blocks in added order, inputs correct.
3. `response.completed` with `output: null` / `output: []` after a tool turn is
   tolerated (streamed state is the fallback source).
4. A text turn with NO `content_part.added` opens the text block on the first
   `output_text.delta` (R3.4, pinned by test only — no shim change).
5. Malformed-JSON tolerance is TYPE-GATED: a malformed non-load-bearing status frame
   (`response.in_progress`) is counted and skipped (success); a malformed
   load-bearing frame (`output_text.delta`) still fails the stream strictly.
6. Reasoning-summary deltas BETWEEN two completed tools reduce to a clean thinking
   block between two tool_use blocks.
"""

from __future__ import annotations

import json
import unittest

from ._loopback_harness import (
    USAGE,
    READ_TOOL,
    MockResponsesServer,
    RealShim,
    Scenario,
    _EventBuilder,
    _append_reasoning_item,
    _append_tool_item,
    _finish_response,
    _nonstream_response,
    block_starts,
    events_scenario,
    failure_lifecycle_report,
    interleaved_two_tools_scenario,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
    sequential_two_tools_scenario,
    text_delta_values,
    thinking_delta_values,
)


# Golden captured from the serialized-two-tools path (msg id normalized). This is the
# byte-identical baseline the R3 scheduler must not perturb: two non-overlapping
# tool_use blocks at monotonic indices 0 and 1, each with one sanitized input delta.
_SERIALIZED_TWO_TOOL_NAMES = [
    "message_start",
    "content_block_start",
    "content_block_delta",
    "content_block_stop",
    "content_block_start",
    "content_block_delta",
    "content_block_stop",
    "message_delta",
    "message_stop",
]
_SERIALIZED_TWO_TOOL_PROJECTION = [
    {
        "type": "message_start",
        "message": {
            "id": "<dynamic-message-id>",
            "type": "message",
            "role": "assistant",
            "model": "gpt-fixture",
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            # v1.3.6 (V6-R3, always-emit): the message_start zero-usage seed gains the two
            # cache fields as 0 for a deterministic usage shape.
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        },
    },
    {
        "type": "content_block_start",
        "index": 0,
        "content_block": {
            "type": "tool_use",
            "id": "call_sequential_1",
            "name": "Read",
            "input": {},
        },
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {
            "type": "input_json_delta",
            "partial_json": '{"file_path": "/daaf/README.md"}',
        },
    },
    {"type": "content_block_stop", "index": 0},
    {
        "type": "content_block_start",
        "index": 1,
        "content_block": {
            "type": "tool_use",
            "id": "call_sequential_2",
            "name": "Read",
            "input": {},
        },
    },
    {
        "type": "content_block_delta",
        "index": 1,
        "delta": {
            "type": "input_json_delta",
            "partial_json": '{"file_path": "/daaf/README.md"}',
        },
    },
    {"type": "content_block_stop", "index": 1},
    {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use", "stop_sequence": None},
        # v1.3.6 (V6-R3, always-emit): absent cache detail -> both fields 0.
        "usage": {
            "input_tokens": USAGE["input_tokens"],
            "output_tokens": USAGE["output_tokens"],
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    },
    {"type": "message_stop"},
]


def _normalize_message_id(frames):
    """Project frames to (event, data) with the dynamic message id normalized."""

    projected = []
    for frame in frames:
        data = json.loads(json.dumps(frame.data)) if isinstance(frame.data, dict) else frame.data
        if isinstance(data, dict) and data.get("type") == "message_start":
            message = data.get("message") or {}
            if "id" in message:
                message["id"] = "<dynamic-message-id>"
        projected.append(data)
    return projected


def _tool_input_by_index(frames):
    """Reconstruct each tool block's input JSON from its input_json_delta stream."""

    partials: dict[int, str] = {}
    for event in (f.data for f in frames if isinstance(f.data, dict)):
        if event.get("type") != "content_block_delta":
            continue
        delta = event.get("delta") or {}
        if delta.get("type") == "input_json_delta":
            index = event.get("index")
            partials[index] = partials.get(index, "") + delta.get("partial_json", "")
    return {index: json.loads(raw or "{}") for index, raw in partials.items()}


class ProviderShimV1214TolerantReducerTests(unittest.TestCase):
    maxDiff = 20000

    def _event_line(self, lines, event):
        matches = [line for line in lines if line.event == event]
        self.assertEqual(len(matches), 1, (event, [line.raw for line in lines]))
        return matches[0]

    def _terminal_fields(self, lines):
        return self._event_line(lines, "terminal").fields

    # --- 1. serialized byte-identical pin (non-negotiable regression gate) ---

    def test_serialized_two_tools_is_byte_identical(self) -> None:
        scenario = sequential_two_tools_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                # Success lifecycle still holds (non-overlap, monotonic, clean stop).
                lifecycle_report(frames)
                self.assertEqual(
                    [frame.event for frame in frames],
                    _SERIALIZED_TWO_TOOL_NAMES,
                )
                self.assertEqual(
                    _normalize_message_id(frames),
                    _SERIALIZED_TWO_TOOL_PROJECTION,
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- 2. interleaved two-tool success ---

    def test_interleaved_two_tools_yields_ordered_blocks(self) -> None:
        scenario = interleaved_two_tools_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["tool_use", "tool_use"],
                )
                self.assertEqual(report.open_at_end, set())
                # Non-overlapping blocks in ADDED order, each with the correct input.
                tool_starts = [
                    start
                    for start in block_starts(frames)
                    if (start.get("content_block") or {}).get("type") == "tool_use"
                ]
                self.assertEqual(
                    [start["content_block"]["id"] for start in tool_starts],
                    ["call_interleaved_1", "call_interleaved_2"],
                )
                self.assertEqual(
                    _tool_input_by_index(frames),
                    {0: {"file_path": "/daaf/A.md"}, 1: {"file_path": "/daaf/B.md"}},
                )
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- 3. completed output null / [] after a tool turn ---

    def _tool_turn_with_terminal_output(self, name, terminal_output):
        args = '{"file_path":"/daaf/README.md"}'
        events = [
            {"type": "response.created",
             "response": {"id": f"resp_{name}", "status": "in_progress"}},
            {"type": "response.output_item.added", "output_index": 0,
             "item": {"type": "function_call", "id": "fc_null_1",
                      "call_id": "call_null_1", "name": "Read", "status": "in_progress"}},
            {"type": "response.function_call_arguments.delta",
             "item_id": "fc_null_1", "output_index": 0, "delta": args},
            {"type": "response.function_call_arguments.done",
             "item_id": "fc_null_1", "output_index": 0, "arguments": args},
            {"type": "response.output_item.done", "output_index": 0,
             "item": {"type": "function_call", "id": "fc_null_1", "call_id": "call_null_1",
                      "name": "Read", "arguments": args, "status": "completed"}},
            {"type": "response.completed",
             "response": {"id": f"resp_{name}", "status": "completed",
                          "output": terminal_output, "usage": dict(USAGE)}},
        ]
        return events_scenario(name, events)

    def test_completed_null_or_empty_output_after_tool_is_tolerated(self) -> None:
        for label, terminal_output in (("null", None), ("empty", [])):
            with self.subTest(output=label):
                scenario = self._tool_turn_with_terminal_output(
                    f"tool-{label}-output", terminal_output
                )
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, "chatgpt") as shim:
                        result = shim.post_messages(stream=True, tools=[READ_TOOL])
                        self.assertEqual(result.status, 200, result.text)
                        frames = parse_typed_sse(result.body)
                        report = lifecycle_report(frames)
                        self.assertEqual(
                            [kind for _index, kind in report.starts],
                            ["tool_use"],
                            label,
                        )
                        self.assertEqual(report.open_at_end, set())
                        self.assertEqual(
                            _tool_input_by_index(frames),
                            {0: {"file_path": "/daaf/README.md"}},
                            label,
                        )
                        shim.assert_offline_contract()
                        backend.assert_request_counts(responses=1)

    # --- 4. content_part-omitted text turn (R3.4 pin) ---

    def test_text_turn_without_content_part_opens_on_first_delta(self) -> None:
        text = "No content_part first."
        events = [
            {"type": "response.created",
             "response": {"id": "resp_cp", "status": "in_progress"}},
            {"type": "response.output_item.added", "output_index": 0,
             "item": {"type": "message", "id": "msg_cp", "role": "assistant",
                      "status": "in_progress", "content": []}},
            # NOTE: no response.content_part.added is emitted before the delta.
            {"type": "response.output_text.delta", "item_id": "msg_cp",
             "output_index": 0, "content_index": 0, "delta": text},
            {"type": "response.output_item.done", "output_index": 0,
             "item": {"type": "message", "id": "msg_cp", "role": "assistant",
                      "status": "completed",
                      "content": [{"type": "output_text", "text": text}]}},
            {"type": "response.completed",
             "response": {"id": "resp_cp", "status": "completed",
                          "output": [{"type": "message", "id": "msg_cp",
                                      "role": "assistant", "status": "completed",
                                      "content": [{"type": "output_text", "text": text}]}],
                          "usage": dict(USAGE)}},
        ]
        scenario = events_scenario("content-part-omitted", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts], ["text"]
                )
                self.assertEqual(text_delta_values(frames), [text])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- 4b. fully-realistic no-reasoning text turn (F1 completeness pin) ---

    def test_no_reasoning_turn_is_tolerated(self) -> None:
        # A live-capture-realistic streamed text turn that carries NO reasoning items
        # or summary deltas at all: created -> in_progress -> output_item.added(message)
        # -> content_part.added -> output_text.delta -> output_text.done ->
        # content_part.done -> output_item.done -> completed. The reducer must produce a
        # clean single text block (no synthesized thinking block), the text must survive,
        # and every event is a known type so unknown_events stays 0.
        text = "A plain answer with no reasoning at all."
        events = [
            {"type": "response.created",
             "response": {"id": "resp_noreason", "status": "in_progress"}},
            {"type": "response.in_progress",
             "response": {"id": "resp_noreason", "status": "in_progress"}},
            {"type": "response.output_item.added", "output_index": 0,
             "item": {"type": "message", "id": "msg_noreason", "role": "assistant",
                      "status": "in_progress", "content": []}},
            {"type": "response.content_part.added", "item_id": "msg_noreason",
             "output_index": 0, "content_index": 0,
             "part": {"type": "output_text", "text": ""}},
            {"type": "response.output_text.delta", "item_id": "msg_noreason",
             "output_index": 0, "content_index": 0, "delta": text},
            {"type": "response.output_text.done", "item_id": "msg_noreason",
             "output_index": 0, "content_index": 0, "text": text},
            {"type": "response.content_part.done", "item_id": "msg_noreason",
             "output_index": 0, "content_index": 0,
             "part": {"type": "output_text", "text": text}},
            {"type": "response.output_item.done", "output_index": 0,
             "item": {"type": "message", "id": "msg_noreason", "role": "assistant",
                      "status": "completed",
                      "content": [{"type": "output_text", "text": text}]}},
            {"type": "response.completed",
             "response": {"id": "resp_noreason", "status": "completed",
                          "output": [{"type": "message", "id": "msg_noreason",
                                      "role": "assistant", "status": "completed",
                                      "content": [{"type": "output_text", "text": text}]}],
                          "usage": dict(USAGE)}},
        ]
        scenario = events_scenario("no-reasoning-turn", events)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                # Exactly one text block, no thinking block anywhere.
                self.assertEqual([kind for _index, kind in report.starts], ["text"])
                self.assertEqual(report.open_at_end, set())
                self.assertEqual(text_delta_values(frames), [text])
                # No reasoning arrived, so the observability counter stays clean.
                terminal_fields = self._terminal_fields(
                    lifecycle_for_response(shim, result)
                )
                self.assertEqual(terminal_fields["outcome"], "success")
                self.assertEqual(int(terminal_fields["unknown_events"]), 0)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- 5. malformed-JSON tolerance is type-gated ---

    def _raw_frame(self, event_type, obj):
        return (
            f"event: {event_type}\n"
            f"data: {json.dumps(obj, separators=(',', ':'))}\n\n"
        ).encode("utf-8")

    def _malformed_prefix_frames(self):
        return [
            self._raw_frame(
                "response.created",
                {"type": "response.created",
                 "response": {"id": "resp_mal", "status": "in_progress"}},
            ),
            self._raw_frame(
                "response.output_item.added",
                {"type": "response.output_item.added", "output_index": 0,
                 "item": {"type": "message", "id": "msg_mal", "role": "assistant",
                          "status": "in_progress", "content": []}},
            ),
            self._raw_frame(
                "response.output_text.delta",
                {"type": "response.output_text.delta", "item_id": "msg_mal",
                 "output_index": 0, "content_index": 0, "delta": "Prefix."},
            ),
        ]

    def test_malformed_non_load_bearing_frame_is_tolerated(self) -> None:
        # A malformed `response.in_progress` frame: json.loads fails, but the probe
        # recovers a non-load-bearing type, so it is counted (R1) and skipped and the
        # stream still completes via the following valid terminal frame.
        frames = self._malformed_prefix_frames()
        frames.append(
            b'event: response.in_progress\n'
            b'data: {"type":"response.in_progress","x":}\n\n'
        )
        terminal = {
            "type": "response.completed",
            "response": {"id": "resp_mal", "status": "completed",
                         "output": [{"type": "message", "id": "msg_mal",
                                     "role": "assistant", "status": "completed",
                                     "content": [{"type": "output_text", "text": "Prefix."}]}],
                         "usage": dict(USAGE)},
        }
        frames.append(self._raw_frame("response.completed", terminal))
        frames.append(b"data: [DONE]\n\n")
        scenario = Scenario(
            name="malformed-in-progress-tolerated",
            stream_events=[],
            nonstream_response=_nonstream_response("resp_mal_ns", []),
            append_done=False,
            raw_stream_frames=frames,
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                sse = parse_typed_sse(result.body)
                report = lifecycle_report(sse)
                self.assertEqual([kind for _index, kind in report.starts], ["text"])
                self.assertEqual(text_delta_values(sse), ["Prefix."])
                terminal_fields = self._terminal_fields(
                    lifecycle_for_response(shim, result)
                )
                self.assertEqual(terminal_fields["outcome"], "success")
                self.assertGreaterEqual(int(terminal_fields["unknown_events"]), 1)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    def test_malformed_load_bearing_frame_still_fails(self) -> None:
        # Contrast: a malformed `output_text.delta` frame carries a load-bearing type,
        # so even though the probe recovers the type it is NOT in the tolerant set —
        # the stream fails strictly (terminal error), never presenting partial success.
        frames = self._malformed_prefix_frames()
        frames.append(
            b'event: response.output_text.delta\n'
            b'data: {"type":"response.output_text.delta","delta":}\n\n'
        )
        frames.append(b"data: [DONE]\n\n")
        scenario = Scenario(
            name="malformed-output-text-fails",
            stream_events=[],
            nonstream_response=_nonstream_response("resp_mal_fail_ns", []),
            append_done=False,
            raw_stream_frames=frames,
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                failure = failure_lifecycle_report(parse_typed_sse(result.body))
                self.assertEqual(failure.error.get("type"), "api_error")
                self.assertEqual(failure.open_at_end, set())
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

    # --- 6. reasoning-summary deltas between two completed tools ---

    def test_reasoning_between_completed_tools_is_a_thinking_block(self) -> None:
        builder = _EventBuilder()
        builder.add(
            "response.created",
            response={"id": "resp_between", "status": "in_progress"},
        )
        output = [
            _append_tool_item(
                builder, 0, call_id="call_between_1", item_id="fc_between_1"
            ),
            _append_reasoning_item(
                builder, "rs_between", 1,
                [{"summary_index": 0, "deltas": ["Between the tools."]}],
            ),
            _append_tool_item(
                builder, 2, call_id="call_between_2", item_id="fc_between_2"
            ),
        ]
        _finish_response(builder, "resp_between", output)
        scenario = Scenario(
            name="reasoning-between-tools",
            stream_events=builder.events,
            nonstream_response=_nonstream_response("resp_between_ns", output),
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                report = lifecycle_report(frames)
                self.assertEqual(
                    [kind for _index, kind in report.starts],
                    ["tool_use", "thinking", "tool_use"],
                )
                self.assertEqual(report.open_at_end, set())
                self.assertEqual(thinking_delta_values(frames), ["Between the tools."])
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)


if __name__ == "__main__":
    unittest.main()
