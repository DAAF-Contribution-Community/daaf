"""Production-subprocess regressions for request translation and v1.2.12 diagnostics."""

from __future__ import annotations

import base64
import json
import threading
import unittest
import urllib.parse

from ._loopback_harness import (
    USAGE,
    MockResponsesServer,
    RealShim,
    controlled_asgi_probe,
    events_scenario,
    full_response_scenario,
    lifecycle_for_response,
    lifecycle_report,
    parse_typed_sse,
)


_IMAGE_BYTES = b"fabricated-provider-shim-image-bytes"
_IMAGE_B64 = base64.b64encode(_IMAGE_BYTES).decode("ascii")
_IMAGE_URL = "https://images.example.invalid/visual.png?private=URL_SENTINEL_92Q"
_FILE_ID = "file_PROVIDER_SCOPED_SENTINEL_71K"


def _image(media_type: str = "image/png", data: str = _IMAGE_B64) -> dict[str, object]:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _missing_name_scenario(count: int = 50):
    events: list[dict[str, object]] = []
    output: list[dict[str, object]] = []
    for index in range(count):
        item_id = f"fc_aggregate_{index}"
        call_id = f"call_aggregate_{index}"
        arguments = "{}"
        events.extend(
            [
                {
                    "type": "response.output_item.added",
                    "item": {
                        "type": "function_call",
                        "id": item_id,
                        "call_id": call_id,
                        "name": "Noop",
                    },
                },
                {
                    "type": "response.function_call_arguments.done",
                    "item_id": item_id,
                    "arguments": arguments,
                },
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "function_call",
                        "id": item_id,
                        "call_id": call_id,
                        "name": "Noop",
                        "arguments": arguments,
                    },
                },
            ]
        )
        output.append(
            {
                "type": "function_call",
                "id": item_id,
                "call_id": call_id,
                "name": "Noop",
                "arguments": arguments,
            }
        )
    events.append(
        {
            "type": "response.completed",
            "response": {
                "id": "resp_warning_aggregate",
                "status": "completed",
                "output": output,
                "usage": dict(USAGE),
            },
        }
    )
    return events_scenario("warning-aggregate", events)


class ProviderShimRequestTranslationTests(unittest.TestCase):
    maxDiff = 12000

    def test_supported_base64_images_map_in_both_lanes(self) -> None:
        for mode in ("openai", "chatgpt"):
            with self.subTest(mode=mode):
                scenario = full_response_scenario()
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        for media_type in (
                            "image/jpeg",
                            "image/png",
                            "image/gif",
                            "image/webp",
                        ):
                            result = shim.post_messages(
                                stream=False,
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [_image(media_type)],
                                    }
                                ],
                            )
                            self.assertEqual(result.status, 200, media_type)
                        self.assertEqual(len(backend.responses_requests), 4)
                        for request, media_type in zip(
                            backend.responses_requests,
                            ("image/jpeg", "image/png", "image/gif", "image/webp"),
                        ):
                            content = request.body["input"][0]["content"]
                            self.assertEqual(
                                content,
                                [
                                    {
                                        "type": "input_image",
                                        "image_url": f"data:{media_type};base64,{_IMAGE_B64}",
                                        "detail": "auto",
                                    }
                                ],
                            )
                        logs = shim.captured_stderr()
                        self.assertNotIn(_IMAGE_B64, logs)
                        self.assertNotIn(_IMAGE_BYTES.decode("ascii"), logs)

    def test_url_image_and_tool_result_preserve_content_order_both_lanes(self) -> None:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "before"},
                    {"type": "image", "source": {"type": "url", "url": _IMAGE_URL}},
                    {"type": "text", "text": "after"},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_image_result",
                        "content": [
                            {"type": "text", "text": "tool-before"},
                            _image(),
                            {"type": "text", "text": "tool-after"},
                        ],
                    }
                ],
            },
        ]
        expected_user = [
            {"type": "input_text", "text": "before"},
            {"type": "input_image", "image_url": _IMAGE_URL, "detail": "auto"},
            {"type": "input_text", "text": "after"},
        ]
        expected_tool = [
            {"type": "input_text", "text": "tool-before"},
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{_IMAGE_B64}",
                "detail": "auto",
            },
            {"type": "input_text", "text": "tool-after"},
        ]
        for mode in ("openai", "chatgpt"):
            with self.subTest(mode=mode):
                scenario = full_response_scenario()
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_messages(stream=False, messages=messages)
                        self.assertEqual(result.status, 200, result.text)
                        request_input = backend.responses_requests[0].body["input"]
                        self.assertEqual(request_input[0]["content"], expected_user)
                        self.assertEqual(
                            request_input[1],
                            {
                                "type": "function_call_output",
                                "call_id": "call_image_result",
                                "output": expected_tool,
                            },
                        )
                        logs = shim.captured_stderr()
                        self.assertNotIn(_IMAGE_URL, logs)
                        self.assertNotIn(_IMAGE_B64, logs)

    def test_invalid_visual_and_unknown_blocks_are_local_400_without_backend(self) -> None:
        cases = (
            ("invalid-base64", _image(data="abcd===")),
            ("unsupported-mime", _image(media_type="image/svg+xml")),
            (
                "unsupported-source",
                {"type": "image", "source": {"type": "future", "data": "hidden"}},
            ),
            (
                "file-source",
                {"type": "image", "source": {"type": "file", "file_id": _FILE_ID}},
            ),
            (
                "invalid-url-scheme",
                {"type": "image", "source": {"type": "url", "url": "file:///secret"}},
            ),
            (
                "invalid-url-credentials",
                {
                    "type": "image",
                    "source": {"type": "url", "url": "https://user:pass@example.invalid/x"},
                },
            ),
            ("unknown-block", {"type": "future_block", "payload": "PROMPT_SENTINEL_4X"}),
        )
        for mode in ("openai", "chatgpt"):
            with self.subTest(mode=mode):
                scenario = full_response_scenario()
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        for name, block in cases:
                            with self.subTest(case=name):
                                result = shim.post_messages(
                                    stream=False,
                                    messages=[{"role": "user", "content": [block]}],
                                )
                                self.assertEqual(result.status, 400, (name, result.text))
                                self.assertEqual(
                                    result.json()["error"]["type"],
                                    "invalid_request_error",
                                )
                        assistant = shim.post_messages(
                            stream=False,
                            messages=[{"role": "assistant", "content": [_image()]}],
                        )
                        self.assertEqual(assistant.status, 400, assistant.text)
                        self.assertEqual(len(backend.responses_requests), 0)
                        logs = shim.captured_stderr()
                        for forbidden in (
                            _IMAGE_B64,
                            _IMAGE_URL,
                            _FILE_ID,
                            "PROMPT_SENTINEL_4X",
                            "https://user:pass@example.invalid/x",
                        ):
                            self.assertNotIn(forbidden, logs)

    def test_malformed_history_is_local_400_in_both_lanes(self) -> None:
        sentinels = (
            "INVALID_ROLE_PROMPT_SENTINEL_7V",
            "MISPLACED_TOOL_INPUT_SENTINEL_8W",
            "MISPLACED_RESULT_SENTINEL_9X",
            "INVALID_RESULT_CONTENT_SENTINEL_0Y",
            "PRIVATE_TOOL_USE_ID_SENTINEL_1Z",
        )
        cases = (
            (
                "invalid-role",
                [
                    {
                        "role": sentinels[0],
                        "content": "private prompt text",
                    }
                ],
            ),
            (
                "missing-role",
                [{"content": "private prompt text"}],
            ),
            (
                "tool-use-in-user-message",
                [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": sentinels[4],
                                "name": "PrivateTool",
                                "input": {"secret": sentinels[1]},
                            }
                        ],
                    }
                ],
            ),
            (
                "tool-result-in-assistant-message",
                [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": sentinels[4],
                                "content": sentinels[2],
                            }
                        ],
                    }
                ],
            ),
            (
                "tool-result-object-content",
                [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": sentinels[4],
                                "content": {"private": sentinels[3]},
                            }
                        ],
                    }
                ],
            ),
            (
                "tool-result-null-content",
                [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": sentinels[4],
                                "content": None,
                            }
                        ],
                    }
                ],
            ),
        )
        for mode in ("openai", "chatgpt"):
            with self.subTest(mode=mode):
                scenario = full_response_scenario()
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        response_texts = []
                        for name, messages in cases:
                            with self.subTest(mode=mode, case=name):
                                result = shim.post_messages(
                                    stream=False,
                                    messages=messages,
                                )
                                response_texts.append(result.text)
                                self.assertEqual(result.status, 400, result.text)
                                self.assertEqual(
                                    result.json().get("error", {}).get("type"),
                                    "invalid_request_error",
                                )
                        backend.assert_request_counts(responses=0, oauth=0)
                        privacy_surfaces = "\n".join(response_texts) + shim.captured_stderr()
                        for sentinel in sentinels:
                            self.assertNotIn(sentinel, privacy_surfaces)

                control = full_response_scenario()
                with MockResponsesServer(control) as backend:
                    with RealShim(backend, mode) as shim:
                        result = shim.post_messages(
                            stream=False,
                            messages=[
                                {"role": "user", "content": "valid user text"},
                                {"role": "assistant", "content": "valid assistant text"},
                                {
                                    "role": "assistant",
                                    "content": [
                                        {
                                            "type": "tool_use",
                                            "id": "call_valid_history",
                                            "name": "ValidTool",
                                            "input": {"value": 1},
                                        }
                                    ],
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": "call_valid_history",
                                            "content": "valid string result",
                                        }
                                    ],
                                },
                            ],
                        )
                        self.assertEqual(result.status, 200, result.text)
                        request_input = backend.responses_requests[0].body["input"]
                        self.assertEqual(request_input[-2]["type"], "function_call")
                        self.assertEqual(
                            request_input[-1],
                            {
                                "type": "function_call_output",
                                "call_id": "call_valid_history",
                                "output": "valid string result",
                            },
                        )
                        backend.assert_request_counts(responses=1, oauth=0)

    def test_text_only_tool_result_retains_string_compatibility(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(
                    stream=False,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call_text_only",
                                    "content": [
                                        {"type": "text", "text": "one"},
                                        {"type": "text", "text": "two"},
                                    ],
                                }
                            ],
                        }
                    ],
                )
                self.assertEqual(result.status, 200, result.text)
                self.assertEqual(
                    backend.responses_requests[0].body["input"][0]["output"],
                    "one\ntwo",
                )

    def test_system_role_messages_fold_to_user_in_both_lanes(self) -> None:
        # v1.2.13 regression (live outage 2026-07-19): current Claude Code appends
        # a role:"system" message inside `messages` (alongside top-level
        # context_management/output_config). The v1.2.12 user/assistant-only role
        # checks rejected every real conversation turn with the static 400.
        # System-role messages must pass validation and fold to user-role input.
        for mode in ("openai", "chatgpt"):
            with self.subTest(mode=mode):
                scenario = full_response_scenario()
                with MockResponsesServer(scenario) as backend:
                    with RealShim(backend, mode) as shim:
                        body = {
                            "model": "gpt-fixture",
                            "max_tokens": 256,
                            "stream": False,
                            "metadata": {"user_id": "user_fixture_session_0001"},
                            "context_management": {"edits": []},
                            "output_config": {"verbosity": "high"},
                            "system": [{"type": "text", "text": "system prompt"}],
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [{"type": "text", "text": "hello"}],
                                },
                                {
                                    "role": "system",
                                    "content": "trailing system reminder",
                                },
                            ],
                        }
                        result = shim.post_raw_messages(
                            json.dumps(body, separators=(",", ":")).encode("utf-8"),
                        )
                        self.assertEqual(result.status, 200, result.text)
                        request = backend.responses_requests[-1]
                        input_items = request.body["input"]
                        folded = input_items[-1]
                        self.assertEqual(folded.get("role"), "user")
                        self.assertEqual(
                            folded.get("content"),
                            [{
                                "type": "input_text",
                                "text": "trailing system reminder",
                            }],
                        )
                        roles = {
                            item.get("role")
                            for item in input_items
                            if isinstance(item, dict)
                        }
                        self.assertNotIn("system", roles)

    def test_system_role_tool_blocks_stay_fail_closed(self) -> None:
        # v1.2.13 companion: the validation gauntlet checks RAW roles, so a
        # system-role message carrying tool_use/tool_result must still be
        # rejected with the static 400 BEFORE any backend round-trip — the
        # translator's fold-to-user must never launder tool blocks into a
        # role placement the gauntlet would have refused.
        for mode in ("openai", "chatgpt"):
            for block in (
                {"type": "tool_use", "id": "toolu_x", "name": "Noop", "input": {}},
                {"type": "tool_result", "tool_use_id": "toolu_x", "content": "ok"},
            ):
                with self.subTest(mode=mode, block=block["type"]):
                    scenario = full_response_scenario()
                    with MockResponsesServer(scenario) as backend:
                        with RealShim(backend, mode) as shim:
                            body = {
                                "model": "gpt-fixture",
                                "max_tokens": 256,
                                "stream": False,
                                "messages": [
                                    {"role": "system", "content": [block]},
                                ],
                            }
                            result = shim.post_raw_messages(
                                json.dumps(
                                    body, separators=(",", ":"),
                                ).encode("utf-8"),
                            )
                            self.assertEqual(result.status, 400, result.text)
                            self.assertEqual(
                                result.json()["error"]["message"],
                                "invalid request structure",
                            )
                            self.assertEqual(len(backend.responses_requests), 0)

    def test_request_ids_and_transport_timeout_families_are_bounded(self) -> None:
        scenario = full_response_scenario()
        scenario.stream_headers = {"x-request-id": "provider-request-17"}
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=True)
                self.assertEqual(result.status, 200, result.text)
                lifecycle_report(parse_typed_sse(result.body))
                lines = lifecycle_for_response(shim, result)
                local_id = result.headers["x-daaf-request-id"]
                self.assertEqual(
                    backend.responses_requests[0].headers.get("x-client-request-id"),
                    local_id,
                )
                upstream = next(line for line in lines if line.event == "upstream_headers")
                self.assertEqual(upstream.fields["upstream_req_id"], "provider-request-17")
                terminal = next(line for line in lines if line.event == "terminal")
                self.assertEqual(terminal.fields["client_req_id"], local_id)
                self.assertEqual(terminal.fields["upstream_req_id"], "provider-request-17")

        expected = {
            "connect_timeout": ("ConnectTimeout", "connect"),
            "read_timeout": ("ReadTimeout", "header_wait_or_body_read"),
            "write_timeout": ("WriteTimeout", "request_body_write"),
            "pool_timeout": ("PoolTimeout", "connection_pool_wait"),
        }
        for outcome, (exception_class, phase) in expected.items():
            with self.subTest(timeout=outcome):
                report = controlled_asgi_probe(attempt_outcomes=[outcome, 200])
                failures = [line for line in report.lifecycle if line.event == "transport_failure"]
                self.assertEqual(len(failures), 1)
                self.assertEqual(failures[0].fields["exception_class"], exception_class)
                self.assertEqual(failures[0].fields["failure_phase"], phase)
                self.assertEqual(failures[0].fields["retryable"], "y")
                retry = next(line for line in report.lifecycle if line.event == "upstream_retry")
                self.assertEqual(retry.fields["source"], "shim_policy")
                self.assertEqual(retry.fields["reason"], "transport")

        midbody = controlled_asgi_probe(attempt_outcomes=["midbody_read_timeout"])
        midbody_failures = [
            line for line in midbody.lifecycle if line.event == "transport_failure"
        ]
        self.assertEqual(len(midbody_failures), 1)
        self.assertEqual(
            midbody_failures[0].fields["exception_class"], "ReadTimeout"
        )
        self.assertEqual(
            midbody_failures[0].fields["failure_phase"],
            "post_stream_start_body_read",
        )
        self.assertEqual(midbody_failures[0].fields["retryable"], "n")
        midbody_terminal = next(
            line for line in midbody.lifecycle if line.event == "terminal"
        )
        self.assertEqual(
            midbody_terminal.fields["failure_phase"],
            "post_stream_start_body_read",
        )
        self.assertEqual(midbody.upstream_calls, 1)

    def test_missing_name_warning_is_concurrency_safe_and_bounded(self) -> None:
        scenario = _missing_name_scenario(150)
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "chatgpt") as shim:
                results: list[object] = []
                failures: list[BaseException] = []

                def call() -> None:
                    try:
                        results.append(shim.post_messages(stream=True))
                    except BaseException as error:
                        failures.append(error)

                threads = [threading.Thread(target=call, daemon=True) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=20.0)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
                self.assertEqual(failures, [])
                self.assertEqual(len(results), 2)
                for result in results:
                    self.assertEqual(result.status, 200, result.text)
                    lifecycle_report(parse_typed_sse(result.body))
                warning_lines = [
                    line
                    for line in shim.captured_stderr().splitlines()
                    if "arguments.done_missing_name" in line
                ]
                self.assertEqual(len(warning_lines), 4, warning_lines)
                expected = (
                    (1, None),
                    (100, 98),
                    (200, 99),
                    (300, 99),
                )
                for line, (observed, suppressed) in zip(warning_lines, expected):
                    self.assertIn(f"observed={observed}", line)
                    if suppressed is None:
                        self.assertNotIn("suppressed=", line)
                    else:
                        self.assertIn(f"suppressed={suppressed}", line)
                backend.assert_request_counts(responses=2, oauth=0)


if __name__ == "__main__":
    unittest.main()
