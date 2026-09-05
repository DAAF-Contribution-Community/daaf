"""Historical provider-shim contracts driven through the real subprocess path."""

from __future__ import annotations

import copy
import json
import threading
import unittest

from ._loopback_harness import (
    READ_TOOL,
    USAGE,
    MockResponsesServer,
    RealShim,
    events_scenario,
    full_response_scenario,
    lifecycle_for_response,
)


_HEALTH_KEYS = {
    "service",
    "status",
    "backend",
    "backend_mode",
    "codex_home_present",
    "version",
    "sanitize_tools",
    "reasoning_effort",
    "text_verbosity",
    # v1.3.0 (A1-R4): read-only auth-validity snapshot block.
    "auth",
    # v1.3.3 (A2-R6): reasoning-cache continuity block (entries/restored counts only).
    "reasoning_cache",
    # v1.3.6 (V6-R4): prompt-cache observability block (cumulative counts only).
    "prompt_cache",
    # v1.3.8: bounded route-bound GPT requested/served observability.
    "gpt_service_tier",
}


def _response(response_id: str, output: list[dict[str, object]], usage: object = None):
    body: dict[str, object] = {
        "id": response_id,
        "model": "gpt-fixture",
        "status": "completed",
        "output": copy.deepcopy(output),
        "incomplete_details": None,
        "error": None,
    }
    if usage is not None:
        body["usage"] = copy.deepcopy(usage)
    return body


def _message_payload(
    *,
    model: str = "gpt-fixture",
    output_config: object = None,
    thinking: object = None,
    messages: list[dict[str, object]] | None = None,
) -> bytes:
    body: dict[str, object] = {
        "model": model,
        "max_tokens": 256,
        "stream": False,
        "messages": messages or [{"role": "user", "content": "Historical rig."}],
    }
    if output_config is not None:
        body["output_config"] = output_config
    if thinking is not None:
        body["thinking"] = thinking
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def _tool_item(
    item_id: str,
    call_id: str,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    return {
        "type": "function_call",
        "id": item_id,
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments, separators=(",", ":")),
        "status": "completed",
    }


class ProviderShimHistoricalRegressionTests(unittest.TestCase):
    maxDiff = 16000

    def test_count_tokens_rejects_poison_then_real_request_calibrates(self) -> None:
        scenario = full_response_scenario()
        template = copy.deepcopy(scenario.nonstream_response)
        invalid_responses: list[dict[str, object]] = []

        missing_usage = copy.deepcopy(template)
        missing_usage.pop("usage", None)
        invalid_responses.append(missing_usage)

        nonobject_usage = copy.deepcopy(template)
        nonobject_usage["usage"] = "malformed"
        invalid_responses.append(nonobject_usage)

        missing_input = copy.deepcopy(template)
        missing_input["usage"] = {"output_tokens": 17}
        invalid_responses.append(missing_input)

        malformed_input = copy.deepcopy(template)
        malformed_input["usage"] = {"input_tokens": "bad", "output_tokens": 17}
        invalid_responses.append(malformed_input)

        zero_input = copy.deepcopy(template)
        zero_input["usage"] = {"input_tokens": 0, "output_tokens": 17}
        invalid_responses.append(zero_input)

        negative_input = copy.deepcopy(template)
        negative_input["usage"] = {"input_tokens": -1, "output_tokens": 17}
        invalid_responses.append(negative_input)

        outlier_input = copy.deepcopy(template)
        outlier_input["usage"] = {
            "input_tokens": 999_999_999,
            "output_tokens": 17,
        }
        invalid_responses.append(outlier_input)

        valid_input = copy.deepcopy(template)
        valid_input["usage"] = {"input_tokens": 50, "output_tokens": 17}
        scenario.nonstream_responses = invalid_responses + [valid_input]

        count_body = {
            "model": "gpt-fixture#low",
            "messages": [{"role": "user", "content": "x" * 5000}],
            "tools": [{"name": "Read", "input_schema": {"type": "object"}}],
        }
        request_payload = _message_payload()

        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                baseline_result = shim.post_count_tokens(count_body)
                self.assertEqual(baseline_result.status, 200, baseline_result.text)
                baseline = baseline_result.json()["input_tokens"]
                self.assertGreater(baseline, 1)

                for expected_count in range(1, len(invalid_responses) + 1):
                    result = shim.post_raw_messages(request_payload)
                    self.assertEqual(result.status, 200, result.text)
                    unchanged = shim.post_count_tokens(count_body)
                    self.assertEqual(unchanged.status, 200, unchanged.text)
                    self.assertEqual(unchanged.json()["input_tokens"], baseline)
                    self.assertEqual(len(backend.responses_requests), expected_count)

                calibrated_request = shim.post_raw_messages(request_payload)
                self.assertEqual(calibrated_request.status, 200, calibrated_request.text)
                calibrated_result = shim.post_count_tokens(count_body)
                self.assertEqual(calibrated_result.status, 200, calibrated_result.text)
                calibrated = calibrated_result.json()["input_tokens"]
                self.assertGreater(calibrated, 1)
                self.assertNotEqual(calibrated, baseline)

                logs = shim.captured_stderr()
                self.assertEqual(logs.count("count_tokens calibration rejected"), 1)
                self.assertEqual(logs.count("count_tokens calibrated ratio="), 1)
                backend.assert_request_counts(responses=8)

    def test_effort_suffix_and_precedence_matrix(self) -> None:
        scenario = full_response_scenario()
        default_cases = [
            (
                "gpt-fixture#low",
                {"effort": "medium"},
                None,
                "gpt-fixture",
                "medium",
            ),
            (
                "gpt-fixture#low",
                {"effort": "high"},
                None,
                "gpt-fixture",
                "low",
            ),
            (
                "gpt-fixture#medium",
                {"effort": "invalid"},
                None,
                "gpt-fixture",
                "medium",
            ),
            (
                "gpt-fixture",
                {"effort": "   "},
                None,
                "gpt-fixture",
                "high",
            ),
            (
                "gpt-fixture#max",
                None,
                {"type": "disabled"},
                "gpt-fixture",
                "none",
            ),
            (
                "gpt-fixture#max",
                {"effort": "high"},
                {"type": "disabled"},
                "gpt-fixture",
                "none",
            ),
            (
                "gpt-fixture#max",
                {"effort": "low"},
                {"type": "disabled"},
                "gpt-fixture",
                "low",
            ),
            (
                "gpt-fixture#future",
                None,
                None,
                "gpt-fixture",
                "high",
            ),
        ]
        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                self.assertIsNone(shim.health["reasoning_effort"])
                for model, output_config, thinking, bare_model, effort in default_cases:
                    result = shim.post_raw_messages(
                        _message_payload(
                            model=model,
                            output_config=output_config,
                            thinking=thinking,
                        )
                    )
                    self.assertEqual(result.status, 200, result.text)
                    outgoing = backend.responses_requests[-1].body
                    self.assertEqual(outgoing["model"], bare_model)
                    self.assertEqual(outgoing["reasoning"]["effort"], effort)
                backend.assert_request_counts(responses=len(default_cases))

        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend,
                "openai",
                env_overrides={"SHIM_REASONING_EFFORT": " xhigh "},
            ) as shim:
                self.assertEqual(shim.health["reasoning_effort"], "xhigh")
                env_cases = [
                    ("gpt-fixture", None, "xhigh"),
                    ("gpt-fixture", {"effort": "high"}, "xhigh"),
                    ("gpt-fixture#", None, "xhigh"),
                    ("gpt-fixture#invalid", None, "xhigh"),
                    ("gpt-fixture#low", {"effort": "high"}, "low"),
                ]
                for model, output_config, effort in env_cases:
                    result = shim.post_raw_messages(
                        _message_payload(model=model, output_config=output_config)
                    )
                    self.assertEqual(result.status, 200, result.text)
                    outgoing = backend.responses_requests[-1].body
                    self.assertEqual(outgoing["model"], "gpt-fixture")
                    self.assertEqual(outgoing["reasoning"]["effort"], effort)

        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend,
                "openai",
                env_overrides={"SHIM_REASONING_EFFORT": "invalid"},
            ) as shim:
                result = shim.post_messages(stream=False)
                self.assertEqual(result.status, 200, result.text)
                self.assertEqual(shim.health["reasoning_effort"], "invalid")
                self.assertEqual(
                    backend.responses_requests[0].body["reasoning"]["effort"],
                    "high",
                )

    def test_verbosity_startup_health_warning_and_payload_matrix(self) -> None:
        cases = [
            ("unset", None, "medium", 0),
            ("low", "low", "low", 0),
            ("medium", " MeDiUm ", "medium", 0),
            ("high", "high", "high", 0),
            ("blank", "   ", "medium", 1),
            ("invalid", "verbose", "medium", 1),
        ]
        scenario = full_response_scenario()
        for name, raw, expected, warning_count in cases:
            with self.subTest(case=name):
                overrides = {} if raw is None else {"SHIM_TEXT_VERBOSITY": raw}
                with MockResponsesServer(scenario) as backend:
                    with RealShim(
                        backend,
                        "openai",
                        env_overrides=overrides,
                    ) as shim:
                        result = shim.post_messages(stream=False)
                        self.assertEqual(result.status, 200, result.text)
                        self.assertEqual(shim.health["text_verbosity"], expected)
                        self.assertEqual(
                            backend.responses_requests[0].body["text"],
                            {"verbosity": expected},
                        )
                        logs = shim.captured_stderr()
                        self.assertEqual(
                            logs.count("SHIM_TEXT_VERBOSITY"),
                            warning_count,
                            logs,
                        )
                        self.assertIn(f"text_verbosity={expected}", logs)

    def test_complete_stable_health_contract_both_lanes_and_overrides(self) -> None:
        scenario = full_response_scenario()
        cases = [
            (
                "openai",
                {
                    "SHIM_SANITIZE_TOOLS": "false",
                    "SHIM_REASONING_EFFORT": "low",
                    "SHIM_TEXT_VERBOSITY": "medium",
                    "SHIM_STRIP_MODEL_PREFIX": "provider/",
                },
                False,
                "low",
                "medium",
            ),
            (
                "chatgpt",
                {
                    "SHIM_SANITIZE_TOOLS": "1",
                    "SHIM_REASONING_EFFORT": "max",
                    "SHIM_TEXT_VERBOSITY": "low",
                },
                True,
                "max",
                "low",
            ),
        ]
        for mode, overrides, sanitize, effort, verbosity in cases:
            with self.subTest(mode=mode):
                with MockResponsesServer(scenario) as backend:
                    with RealShim(
                        backend,
                        mode,
                        env_overrides=overrides,
                    ) as shim:
                        health_result = shim.get_health()
                        self.assertEqual(health_result.status, 200, health_result.text)
                        health = health_result.json()
                        self.assertEqual(set(health), _HEALTH_KEYS)
                        self.assertEqual(health["service"], "daaf-anthropic-openai-shim")
                        self.assertEqual(health["status"], "ok")
                        self.assertEqual(health["version"], "1.3.19")
                        self.assertEqual(health["backend_mode"], mode)
                        self.assertEqual(health["sanitize_tools"], sanitize)
                        self.assertEqual(health["reasoning_effort"], effort)
                        self.assertEqual(health["text_verbosity"], verbosity)
                        self.assertIs(health["codex_home_present"], True)
                        tier = health["gpt_service_tier"]
                        self.assertEqual(
                            set(tier),
                            {
                                "backend_mode",
                                "requested_tier_vocabulary",
                                "policy",
                                "native_fast_disabled",
                                "latest_terminal",
                            },
                        )
                        self.assertEqual(tier["backend_mode"], mode)
                        self.assertEqual(
                            tier["requested_tier_vocabulary"],
                            "priority",
                        )
                        self.assertEqual(
                            set(tier["policy"]),
                            {"status", "backend_mode", "enabled", "effective"},
                        )
                        self.assertIs(tier["native_fast_disabled"], False)
                        self.assertIsNone(tier["latest_terminal"])
                        # v1.3.0 (A1-R4): the auth block. The openai lane does not use
                        # the codex OAuth store -> "n/a" (no token material). The chatgpt
                        # lane seeds a far-future fabricated token -> "valid", with an
                        # expiry/day-count and NO recovery command (recovery is present
                        # only for the four actionable states).
                        auth = health["auth"]
                        if mode == "openai":
                            self.assertEqual(auth, {"state": "n/a"})
                        else:
                            self.assertEqual(auth["state"], "valid")
                            self.assertNotIn("recovery", auth)
                            self.assertIsInstance(auth["expires_at"], str)
                            self.assertGreater(auth["days_left"], 1)
                        expected_backend = (
                            f"{backend.base_url}/v1"
                            if mode == "openai"
                            else backend.base_url
                        )
                        self.assertEqual(health["backend"], expected_backend)
                        for forbidden in (
                            "port",
                            "pid",
                            "api_key",
                            "credential_path",
                            "codex_home",
                        ):
                            self.assertNotIn(forbidden, health)

                        result = shim.post_messages(
                            stream=False,
                            model="provider/gpt-fixture",
                        )
                        self.assertEqual(result.status, 200, result.text)
                        outgoing = backend.responses_requests[0].body
                        expected_model = (
                            "gpt-fixture" if mode == "openai" else "provider/gpt-fixture"
                        )
                        self.assertEqual(outgoing["model"], expected_model)
                        self.assertEqual(outgoing["reasoning"]["effort"], effort)
                        self.assertEqual(outgoing["text"], {"verbosity": verbosity})

    def test_two_turn_reasoning_cache_replay_is_paired_and_conversation_local(self) -> None:
        scenario = full_response_scenario()
        first_response = copy.deepcopy(scenario.nonstream_response)
        quiet_response = _response(
            "resp_replay_followup",
            [],
            {"input_tokens": 31, "output_tokens": 1, "total_tokens": 32},
        )
        scenario.nonstream_responses = [first_response, quiet_response, quiet_response]
        cached_reasoning = copy.deepcopy(first_response["output"][0])

        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                first = shim.post_messages(stream=False, tools=[READ_TOOL])
                self.assertEqual(first.status, 200, first.text)
                first_content = first.json()["content"]
                paired_messages = [
                    {"role": "assistant", "content": first_content},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "call_full_fixture",
                                "content": "paired result",
                            }
                        ],
                    },
                ]
                unrelated_messages = [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "call_unrelated",
                                "name": "Read",
                                "input": {"file_path": "/daaf/CONTRIBUTING.md"},
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "call_unrelated",
                                "content": "unrelated result",
                            }
                        ],
                    },
                ]
                results: dict[str, object] = {}
                failures: list[BaseException] = []

                def call(label: str, messages: list[dict[str, object]]) -> None:
                    try:
                        results[label] = shim.post_messages(
                            stream=False,
                            tools=[READ_TOOL],
                            messages=messages,
                        )
                    except BaseException as error:
                        failures.append(error)

                threads = [
                    threading.Thread(
                        target=call,
                        args=("paired", paired_messages),
                        daemon=True,
                    ),
                    threading.Thread(
                        target=call,
                        args=("unrelated", unrelated_messages),
                        daemon=True,
                    ),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=20.0)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
                self.assertEqual(failures, [])
                self.assertEqual(set(results), {"paired", "unrelated"})

                requests_by_call: dict[str, dict[str, object]] = {}
                for request in backend.responses_requests[1:]:
                    call_ids = [
                        item.get("call_id")
                        for item in request.body["input"]
                        if item.get("type") == "function_call"
                    ]
                    if "call_full_fixture" in call_ids:
                        requests_by_call["paired"] = request.body
                    if "call_unrelated" in call_ids:
                        requests_by_call["unrelated"] = request.body
                self.assertEqual(set(requests_by_call), {"paired", "unrelated"})

                paired_input = requests_by_call["paired"]["input"]
                function_at = next(
                    index
                    for index, item in enumerate(paired_input)
                    if item.get("type") == "function_call"
                    and item.get("call_id") == "call_full_fixture"
                )
                self.assertGreater(function_at, 0)
                self.assertEqual(paired_input[function_at - 1], cached_reasoning)
                self.assertEqual(
                    paired_input[function_at - 1]["encrypted_content"],
                    "ENC_rs_full",
                )
                self.assertFalse(
                    any(
                        item.get("type") == "reasoning"
                        for item in requests_by_call["unrelated"]["input"]
                    )
                )

                paired_lifecycle = lifecycle_for_response(shim, results["paired"])
                unrelated_lifecycle = lifecycle_for_response(shim, results["unrelated"])
                paired_terminal = next(
                    line for line in paired_lifecycle if line.event == "terminal"
                )
                unrelated_terminal = next(
                    line for line in unrelated_lifecycle if line.event == "terminal"
                )
                self.assertEqual(paired_terminal.fields["reasoning_cache_miss"], "0")
                self.assertEqual(
                    unrelated_terminal.fields["reasoning_cache_miss"], "1"
                )
                backend.assert_request_counts(responses=3)

    def test_tool_argument_sanitization_matrix_and_disabled_passthrough(self) -> None:
        originals = [
            ("call_read_empty", "Read", {"file_path": "/daaf/README.md", "pages": "", "note": ""}),
            ("call_read_pages", "Read", {"file_path": "/daaf/a.pdf", "pages": "1-3"}),
            ("call_agent", "Agent", {"prompt": "", "isolation": "remote", "model": "opus"}),
            ("call_task", "Task", {"prompt": "task", "isolation": "", "model": "sonnet"}),
            ("call_bash_false", "Bash", {"command": "pwd", "dangerouslyDisableSandbox": False, "description": ""}),
            ("call_bash_true", "Bash", {"command": "pwd", "dangerouslyDisableSandbox": True}),
        ]
        output = [
            _tool_item(f"fc_{index}", call_id, name, arguments)
            for index, (call_id, name, arguments) in enumerate(originals)
        ]
        response = _response("resp_sanitize", output, dict(USAGE))
        scenario = events_scenario(
            "sanitize-matrix",
            [],
            nonstream_response=response,
        )
        tools = [
            {
                "name": name,
                "description": "fixture",
                "input_schema": {"type": "object", "properties": {}},
            }
            for name in ("Read", "Agent", "Task", "Bash")
        ]
        expected = {
            "call_read_empty": {"file_path": "/daaf/README.md", "note": ""},
            "call_read_pages": {"file_path": "/daaf/a.pdf", "pages": "1-3"},
            "call_agent": {"prompt": "", "model": "opus"},
            "call_task": {"prompt": "task", "model": "sonnet"},
            "call_bash_false": {"command": "pwd", "description": ""},
            "call_bash_true": {"command": "pwd", "dangerouslyDisableSandbox": True},
        }

        with MockResponsesServer(scenario) as backend:
            with RealShim(backend, "openai") as shim:
                result = shim.post_messages(stream=False, tools=tools)
                self.assertEqual(result.status, 200, result.text)
                actual = {
                    block["id"]: block["input"]
                    for block in result.json()["content"]
                    if block.get("type") == "tool_use"
                }
                self.assertEqual(actual, expected)
                self.assertEqual(shim.health["sanitize_tools"], True)
                self.assertEqual(
                    [tool["name"] for tool in backend.responses_requests[0].body["tools"]],
                    ["Read", "Agent", "Task", "Bash"],
                )
                replay = shim.post_messages(
                    stream=False,
                    tools=tools,
                    messages=[{"role": "assistant", "content": result.json()["content"]}],
                )
                self.assertEqual(replay.status, 200, replay.text)
                replayed_arguments = {
                    item["call_id"]: json.loads(item["arguments"])
                    for item in backend.responses_requests[1].body["input"]
                    if item.get("type") == "function_call"
                }
                self.assertEqual(replayed_arguments, expected)

        with MockResponsesServer(scenario) as backend:
            with RealShim(
                backend,
                "openai",
                env_overrides={"SHIM_SANITIZE_TOOLS": "false"},
            ) as shim:
                result = shim.post_messages(stream=False, tools=tools)
                self.assertEqual(result.status, 200, result.text)
                actual = {
                    block["id"]: block["input"]
                    for block in result.json()["content"]
                    if block.get("type") == "tool_use"
                }
                original_map = {
                    call_id: arguments for call_id, _name, arguments in originals
                }
                self.assertEqual(actual, original_map)
                self.assertEqual(shim.health["sanitize_tools"], False)
                replay = shim.post_messages(
                    stream=False,
                    tools=tools,
                    messages=[{"role": "assistant", "content": result.json()["content"]}],
                )
                self.assertEqual(replay.status, 200, replay.text)
                replayed_arguments = {
                    item["call_id"]: json.loads(item["arguments"])
                    for item in backend.responses_requests[1].body["input"]
                    if item.get("type") == "function_call"
                }
                self.assertEqual(replayed_arguments, original_map)

    def test_realshim_env_override_seam_rejects_security_sensitive_keys(self) -> None:
        scenario = full_response_scenario()
        with MockResponsesServer(scenario) as backend:
            for name in ("OPENAI_API_KEY", "SHIM_BACKEND_BASE_URL", "MY_SECRET"):
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, "not allowlisted"):
                        RealShim(backend, "openai", env_overrides={name: "forbidden"})


if __name__ == "__main__":
    unittest.main()
