"""End-to-end reasoning-formatting contracts for both provider-shim lanes."""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from ._loopback_harness import (
    CENTRAL_DESIRED_TEXT,
    CENTRAL_LEGACY_TEXT,
    CENTRAL_SOURCE_DELTAS,
    FAKE_OPENAI_KEY,
    READ_TOOL,
    MockResponsesServer,
    RealShim,
    _ClosedLoopbackEndpoint,
    block_starts,
    central_multipart_scenario,
    event_dicts,
    extract_nonstream_thinking,
    identity_parts_scenario,
    is_loopback_url,
    lifecycle_report,
    malformed_identity_scenario,
    minimal_dual_mode_scenario,
    mixed_identity_scenario,
    normalized_non_reasoning_projection,
    parse_typed_sse,
    provider_scratch_residue,
    raw_reasoning_delta_scenario,
    reopened_thinking_scenario,
    text_delta_values,
    thinking_delta_values,
)


class ProviderShimReasoningFormattingTests(unittest.TestCase):
    maxDiff = 12000

    def _chatgpt_stream_text(self, scenario: object) -> str:
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)
                return "".join(thinking_delta_values(frames))

    def test_openai_streaming_legacy_bytes_unchanged(self) -> None:
        scenario = central_multipart_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

                self.assertEqual(thinking_delta_values(frames), CENTRAL_SOURCE_DELTAS)
                self.assertEqual("".join(thinking_delta_values(frames)), CENTRAL_LEGACY_TEXT)
                self.assertEqual(
                    [kind for _, kind in lifecycle.starts].count("thinking"),
                    1,
                )
                self.assertEqual(
                    backend.responses_requests[0].path,
                    "/v1/responses",
                )
                self.assertEqual(
                    shim.health.get("service"), "daaf-anthropic-openai-shim"
                )
                self.assertEqual(shim.health.get("status"), "ok")
                self.assertEqual(shim.health.get("backend_mode"), "openai")
                self.assertEqual(shim.health.get("version"), "1.3.5")

    def test_openai_nonstreaming_legacy_bytes_unchanged(self) -> None:
        scenario = central_multipart_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

                self.assertEqual(extract_nonstream_thinking(message), CENTRAL_LEGACY_TEXT)
                thinking_blocks = [
                    block for block in message["content"] if block.get("type") == "thinking"
                ]
                self.assertEqual(len(thinking_blocks), 1)
                self.assertEqual(message.get("stop_reason"), "end_turn")
                self.assertEqual(
                    backend.responses_requests[0].body.get("stream"),
                    False,
                )

    def test_chatgpt_boundary_streaming_multipart(self) -> None:
        scenario = central_multipart_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

                values = thinking_delta_values(frames)
                self.assertEqual(
                    [value for value in values if value != "\n\n"],
                    CENTRAL_SOURCE_DELTAS,
                )
                self.assertEqual(
                    [kind for _, kind in lifecycle.starts].count("thinking"),
                    1,
                )
                actual_text = "".join(values)
                mismatch = (
                    "CHATGPT_MULTIPART_CONCAT_MISMATCH "
                    f"actual={actual_text!r} expected={CENTRAL_DESIRED_TEXT!r}"
                )
                self.assertEqual(actual_text, CENTRAL_DESIRED_TEXT, mismatch)
                self.assertEqual(values.count("\n\n"), 2)
                self.assertEqual(
                    values,
                    [
                        "**Planning ",
                        "tests**",
                        "\n\n",
                        "**Validating boundaries**",
                        "\n\n",
                        "**Checking reset**",
                    ],
                )

    def test_chatgpt_boundary_nonstreaming_parity(self) -> None:
        scenario = central_multipart_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)

                self.assertEqual(extract_nonstream_thinking(message), CENTRAL_DESIRED_TEXT)
                self.assertEqual(message.get("stop_reason"), "end_turn")

    def test_chatgpt_empty_first_middle_parts_no_extra_separators(self) -> None:
        scenario = identity_parts_scenario(
            "empty-parts",
            [
                {"item_id": "rs_empty", "output_index": 0, "summary_index": 0, "deltas": []},
                {"item_id": "rs_empty", "output_index": 0, "summary_index": 1, "deltas": ["A"]},
                {"item_id": "rs_empty", "output_index": 0, "summary_index": 2, "deltas": []},
                {"item_id": "rs_empty", "output_index": 0, "summary_index": 3, "deltas": ["B"]},
                {"item_id": "rs_empty", "output_index": 0, "summary_index": 4, "deltas": []},
            ],
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                backend.assert_request_counts(responses=1)
                text = "".join(thinking_delta_values(frames))
                self.assertEqual(text, "A\n\nB")
                self.assertFalse(text.startswith("\n\n"))
                self.assertFalse(text.endswith("\n\n"))
                self.assertNotIn("\n\n\n\n", text)

    def test_chatgpt_missing_malformed_identity_falls_back_to_legacy_append(self) -> None:
        scenario = malformed_identity_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                backend.assert_request_counts(responses=1)
                self.assertEqual(thinking_delta_values(frames), ["M", "N", "O"])
                self.assertEqual("".join(thinking_delta_values(frames)), "MNO")

    def test_chatgpt_mixed_identity_disables_later_boundary_synthesis(self) -> None:
        scenario = mixed_identity_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                backend.assert_request_counts(responses=1)

                values = thinking_delta_values(frames)
                self.assertEqual(values, ["A", "B", "C"])
                self.assertEqual("".join(values), "ABC")
                self.assertNotIn("\n\n", values)

    def test_chatgpt_conflict_different_items_reuse_output_disables_later_synthesis(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "conflict-output-reused",
            [
                {"item_id": "rs_A", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "rs_B", "output_index": 0, "summary_index": 0, "delta": "B"},
                {"item_id": "rs_C", "output_index": 1, "summary_index": 0, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_conflict_one_item_moves_output_disables_later_synthesis(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "conflict-item-moved",
            [
                {"item_id": "rs_A", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "rs_A", "output_index": 1, "summary_index": 0, "delta": "B"},
                {"item_id": "rs_C", "output_index": 2, "summary_index": 0, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_output_fallback_missing_item_id_preserves_stable_boundaries(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "missing-item-output-fallback",
            [
                {"output_index": 0, "summary_index": 0, "delta": "A"},
                {"output_index": 0, "summary_index": 1, "delta": "B"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "A\n\nB")

    def test_chatgpt_empty_item_id_uses_stable_output_fallback(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "empty-item-output-fallback",
            [
                {"item_id": "", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "", "output_index": 0, "summary_index": 1, "delta": "B"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "A\n\nB")

    def test_chatgpt_boolean_summary_index_is_rejected_independently(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "boolean-summary",
            [
                {"item_id": "rs_bool_summary", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "rs_bool_summary", "output_index": 0, "summary_index": True, "delta": "B"},
                {"item_id": "rs_bool_summary", "output_index": 0, "summary_index": 1, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_boolean_output_without_item_is_rejected_independently(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "boolean-output",
            [
                {"output_index": 0, "summary_index": 0, "delta": "A"},
                {"output_index": True, "summary_index": 1, "delta": "B"},
                {"output_index": 0, "summary_index": 2, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_negative_summary_index_is_rejected_independently(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "negative-summary",
            [
                {"item_id": "rs_negative_summary", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "rs_negative_summary", "output_index": 0, "summary_index": -1, "delta": "B"},
                {"item_id": "rs_negative_summary", "output_index": 0, "summary_index": 1, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_negative_output_without_item_is_rejected_independently(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "negative-output",
            [
                {"output_index": 0, "summary_index": 0, "delta": "A"},
                {"output_index": -1, "summary_index": 1, "delta": "B"},
                {"output_index": 0, "summary_index": 2, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_partial_item_to_complete_identity_disables_synthesis(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "partial-item-to-complete",
            [
                {"item_id": "rs_partial", "summary_index": 0, "delta": "A"},
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 0, "delta": "B"},
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 1, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_complete_to_partial_item_identity_disables_synthesis(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "complete-to-partial-item",
            [
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "rs_partial", "summary_index": 0, "delta": "B"},
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 1, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_partial_output_to_complete_identity_disables_synthesis(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "partial-output-to-complete",
            [
                {"output_index": 0, "summary_index": 0, "delta": "A"},
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 0, "delta": "B"},
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 1, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_complete_to_partial_output_identity_disables_synthesis(self) -> None:
        scenario = raw_reasoning_delta_scenario(
            "complete-to-partial-output",
            [
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 0, "delta": "A"},
                {"output_index": 0, "summary_index": 0, "delta": "B"},
                {"item_id": "rs_partial", "output_index": 0, "summary_index": 1, "delta": "C"},
            ],
        )
        self.assertEqual(self._chatgpt_stream_text(scenario), "ABC")

    def test_chatgpt_nonstreaming_whitespace_only_summary_is_preserved_content(self) -> None:
        scenario = identity_parts_scenario(
            "whitespace-only-nonstream",
            [
                {"item_id": "rs_whitespace", "output_index": 0, "summary_index": 0, "deltas": [" \t"]},
                {"item_id": "rs_whitespace", "output_index": 0, "summary_index": 1, "deltas": ["B"]},
            ],
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                message = result.json()
                shim.assert_offline_contract()
                backend.assert_request_counts(responses=1)
                self.assertEqual(extract_nonstream_thinking(message), " \t\n\nB")

    def test_chatgpt_duplicate_same_part_chunks_have_no_separator(self) -> None:
        scenario = identity_parts_scenario(
            "same-part-chunks",
            [
                {
                    "item_id": "rs_chunked",
                    "output_index": 0,
                    "summary_index": 0,
                    "deltas": ["A", "B", "C"],
                },
            ],
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                backend.assert_request_counts(responses=1)
                self.assertEqual(thinking_delta_values(frames), ["A", "B", "C"])
                self.assertEqual("".join(thinking_delta_values(frames)), "ABC")

    def test_chatgpt_out_of_order_first_seen_identities_preserve_arrival_order(self) -> None:
        scenario = identity_parts_scenario(
            "out-of-order-identities",
            [
                {"item_id": "rs_order", "output_index": 0, "summary_index": 5, "deltas": ["Fifth"]},
                {"item_id": "rs_order", "output_index": 0, "summary_index": 2, "deltas": ["Second"]},
                {"item_id": "rs_order", "output_index": 0, "summary_index": 9, "deltas": ["Ninth"]},
            ],
        )
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                backend.assert_request_counts(responses=1)
                self.assertEqual(
                    "".join(thinking_delta_values(frames)),
                    "Fifth\n\nSecond\n\nNinth",
                )

    def test_chatgpt_multiple_reasoning_items_summary_reset_uses_composite_identity(self) -> None:
        scenario = central_multipart_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle_report(frames)
                backend.assert_request_counts(responses=1)
                self.assertEqual("".join(thinking_delta_values(frames)), CENTRAL_DESIRED_TEXT)
                self.assertTrue(CENTRAL_DESIRED_TEXT.endswith("\n\n**Checking reset**"))

    def test_chatgpt_thinking_to_text_lifecycle_signature_stop_and_end_turn(self) -> None:
        scenario = central_multipart_scenario(transition="text")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                events = event_dicts(frames)
                backend.assert_request_counts(responses=1)

                self.assertEqual([kind for _, kind in lifecycle.starts], ["thinking", "text"])
                thinking_index, text_index = [index for index, _ in lifecycle.starts]
                self.assertLess(thinking_index, text_index)
                signature_position = next(
                    position
                    for position, event in enumerate(events)
                    if event.get("type") == "content_block_delta"
                    and event.get("index") == thinking_index
                    and (event.get("delta") or {}).get("type") == "signature_delta"
                )
                thinking_stop_position = next(
                    position
                    for position, event in enumerate(events)
                    if event.get("type") == "content_block_stop"
                    and event.get("index") == thinking_index
                )
                text_start_position = next(
                    position
                    for position, event in enumerate(events)
                    if event.get("type") == "content_block_start"
                    and event.get("index") == text_index
                )
                self.assertLess(signature_position, thinking_stop_position)
                self.assertLess(thinking_stop_position, text_start_position)
                self.assertEqual(text_delta_values(frames), ["Final answer."])
                message_delta = next(
                    event for event in events if event.get("type") == "message_delta"
                )
                self.assertEqual(message_delta["delta"]["stop_reason"], "end_turn")

    def test_chatgpt_thinking_to_tool_lifecycle_arguments_and_stop_reason(self) -> None:
        scenario = central_multipart_scenario(transition="tool")
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                events = event_dicts(frames)
                backend.assert_request_counts(responses=1)

                self.assertEqual([kind for _, kind in lifecycle.starts], ["thinking", "tool_use"])
                thinking_index, tool_index = [index for index, _ in lifecycle.starts]
                thinking_stop_position = next(
                    position
                    for position, event in enumerate(events)
                    if event.get("type") == "content_block_stop"
                    and event.get("index") == thinking_index
                )
                tool_start_position = next(
                    position
                    for position, event in enumerate(events)
                    if event.get("type") == "content_block_start"
                    and event.get("index") == tool_index
                )
                self.assertLess(thinking_stop_position, tool_start_position)
                tool_start = next(
                    event
                    for event in events
                    if event.get("type") == "content_block_start"
                    and (event.get("content_block") or {}).get("type") == "tool_use"
                )
                self.assertEqual(tool_start["content_block"]["id"], "call_fixture_1")
                self.assertEqual(tool_start["content_block"]["name"], "Read")
                argument_deltas = [
                    event["delta"]["partial_json"]
                    for event in events
                    if event.get("type") == "content_block_delta"
                    and (event.get("delta") or {}).get("type") == "input_json_delta"
                ]
                self.assertEqual(
                    json.loads("".join(argument_deltas)),
                    {"file_path": "/daaf/README.md"},
                )
                message_delta = next(
                    event for event in events if event.get("type") == "message_delta"
                )
                self.assertEqual(message_delta["delta"]["stop_reason"], "tool_use")

    def test_chatgpt_reopened_thinking_block_resets_boundary_state(self) -> None:
        scenario = reopened_thinking_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                result = shim.post_messages(stream=True, tools=[READ_TOOL])
                self.assertEqual(result.status, 200, result.text)
                frames = parse_typed_sse(result.body)
                lifecycle = lifecycle_report(frames)
                backend.assert_request_counts(responses=1)

                self.assertEqual(
                    [kind for _, kind in lifecycle.starts],
                    ["thinking", "tool_use", "thinking"],
                )
                values = thinking_delta_values(frames)
                self.assertEqual(values, ["Before tool", "After tool"])
                self.assertFalse(values[1].startswith("\n\n"))

    def test_dual_mode_isolation_legacy_vs_boundary_modes(self) -> None:
        scenario = minimal_dual_mode_scenario()
        with MockResponsesServer(scenario) as openai_backend:
            with RealShim(openai_backend, "openai") as openai_shim:
                openai_result = openai_shim.post_messages(stream=True)
                self.assertEqual(openai_result.status, 200, openai_result.text)
                openai_frames = parse_typed_sse(openai_result.body)
                lifecycle_report(openai_frames)
                openai_backend.assert_request_counts(responses=1)
                openai_body = openai_backend.responses_requests[0].body
                openai_headers = openai_backend.responses_requests[0].headers

        with MockResponsesServer(scenario) as chatgpt_backend:
            with RealShim(chatgpt_backend, "chatgpt") as chatgpt_shim:
                chatgpt_result = chatgpt_shim.post_messages(stream=True)
                self.assertEqual(chatgpt_result.status, 200, chatgpt_result.text)
                chatgpt_frames = parse_typed_sse(chatgpt_result.body)
                lifecycle_report(chatgpt_frames)
                chatgpt_backend.assert_request_counts(responses=1)
                chatgpt_body = chatgpt_backend.responses_requests[0].body
                chatgpt_headers = chatgpt_backend.responses_requests[0].headers

        self.assertEqual("".join(thinking_delta_values(openai_frames)), "AB")
        self.assertEqual("".join(thinking_delta_values(chatgpt_frames)), "A\n\nB")
        self.assertEqual(
            normalized_non_reasoning_projection(openai_frames),
            normalized_non_reasoning_projection(chatgpt_frames),
        )
        self.assertIn("max_output_tokens", openai_body)
        self.assertNotIn("max_output_tokens", chatgpt_body)
        openai_without_known_delta = dict(openai_body)
        openai_without_known_delta.pop("max_output_tokens")
        self.assertEqual(openai_without_known_delta, chatgpt_body)
        self.assertEqual(openai_backend.responses_requests[0].path, "/v1/responses")
        self.assertEqual(chatgpt_backend.responses_requests[0].path, "/responses")
        self.assertNotEqual(openai_headers.get("authorization"), None)
        self.assertEqual(chatgpt_headers.get("accept"), "text/event-stream")

    def test_harness_security_child_environment_omits_parent_secrets(self) -> None:
        seeded_names = {
            "GITHUB_TOKEN": "FAKE_PARENT_GITHUB_TOKEN",
            "HF_TOKEN": "FAKE_PARENT_HF_TOKEN",
            "DATABASE_PASSWORD": "FAKE_PARENT_DATABASE_PASSWORD",
            "ARBITRARY_SERVICE_TOKEN": "FAKE_PARENT_ARBITRARY_TOKEN",
            "ARBITRARY_SERVICE_SECRET": "FAKE_PARENT_ARBITRARY_SECRET",
            "ARBITRARY_SERVICE_PASSWORD": "FAKE_PARENT_ARBITRARY_PASSWORD",
            "ARBITRARY_SERVICE_CREDENTIAL_FILE": "FAKE_PARENT_CREDENTIAL_PATH",
            "PYTHONPATH": "/fake/parent/pythonpath",
            "PYTHONHOME": "/fake/parent/pythonhome",
            "HOME": "/fake/parent/home",
        }
        scenario = central_multipart_scenario()
        with mock.patch.dict(os.environ, seeded_names, clear=False):
            with MockResponsesServer(scenario) as backend:
                with RealShim(backend, "chatgpt") as shim:
                    result = shim.post_messages(stream=False)
                    self.assertEqual(result.status, 200, result.text)
                    shim.assert_offline_contract()
                    backend.assert_request_counts(responses=1)
                    for name in seeded_names:
                        self.assertNotIn(name, shim.child_env, name)
                    allowed_names = (
                        set(RealShim._CONTROLLED_BASE_ENV)
                        | set(RealShim._CONTROLLED_CHILD_ENV_NAMES)
                    )
                    self.assertEqual(set(shim.child_env), allowed_names)

    def test_harness_cleanup_popen_failure_releases_scratch_and_proxy(self) -> None:
        before = provider_scratch_residue()
        proxy_exit_calls: list[str] = []
        original_proxy_exit = _ClosedLoopbackEndpoint.__exit__

        def recording_proxy_exit(instance, exc_type, exc, traceback):
            proxy_exit_calls.append(instance.url)
            return original_proxy_exit(instance, exc_type, exc, traceback)

        scenario = central_multipart_scenario()
        with MockResponsesServer(scenario) as backend:
            shim = RealShim(backend, "chatgpt")
            with mock.patch.object(
                _ClosedLoopbackEndpoint,
                "__exit__",
                new=recording_proxy_exit,
            ):
                with mock.patch(
                    "provider_shim._loopback_harness.subprocess.Popen",
                    side_effect=OSError("injected subprocess creation failure"),
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        "injected subprocess creation failure",
                    ):
                        shim.__enter__()
        self.assertEqual(provider_scratch_residue(), before)
        self.assertEqual(len(proxy_exit_calls), 1)
        self.assertIsNone(shim._proxy_guard)
        self.assertIsNotNone(shim.scratch_dir)
        self.assertFalse(shim.scratch_dir.exists())
        self.assertIsNone(shim.process)

    def test_harness_offline_contract_cleanup_and_mock_accounting(self) -> None:
        before = provider_scratch_residue()
        scenario = central_multipart_scenario()
        scratch_dir = None
        auth_path = None
        with MockResponsesServer(scenario) as backend:
            self.assertTrue(is_loopback_url(backend.base_url))
            self.assertTrue(is_loopback_url(backend.responses_url))
            with RealShim(backend, "chatgpt") as shim:
                scratch_dir = shim.scratch_dir
                auth_path = shim.auth_path
                self.assertIsNotNone(scratch_dir)
                self.assertIsNotNone(auth_path)
                self.assertTrue(scratch_dir.is_dir())
                self.assertTrue(auth_path.is_file())
                fabricated = json.loads(auth_path.read_text(encoding="utf-8"))
                self.assertEqual(fabricated.get("OPENAI_API_KEY"), FAKE_OPENAI_KEY)
                self.assertEqual(fabricated.get("auth_mode"), "chatgpt")
                self.assertIn(
                    "FABRICATED_PROVIDER_SHIM_UNITTEST_ONLY",
                    _decode_jwt_payload(fabricated["tokens"]["access_token"])["marker"],
                )
                shim.assert_offline_contract()
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                backend.assert_request_counts(responses=1)
                request = backend.responses_requests[0]
                self.assertEqual(request.headers.get("accept"), "text/event-stream")
                self.assertTrue(request.headers.get("authorization", "").startswith("Bearer "))
                self.assertNotIn("x-api-key", request.headers)
            self.assertFalse(scratch_dir.exists())
            self.assertFalse(auth_path.exists())
        self.assertEqual(provider_scratch_residue(), before)


def _decode_jwt_payload(token: str) -> dict[str, object]:
    import base64

    segment = token.split(".")[1]
    segment += "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment.encode("ascii")))


if __name__ == "__main__":
    unittest.main()
