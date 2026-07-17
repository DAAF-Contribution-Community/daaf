"""Focused deterministic tests for ChatGPT-subscription model routing."""

import argparse
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.harness.cost_estimator import (
    LUNA_LONG_CONTEXT_RATES,
    LUNA_LONG_CONTEXT_THRESHOLD,
    LUNA_SHORT_CONTEXT_RATES,
)
from benchmarks.harness.executor import execute_run
from benchmarks.harness.model_loader import add_model_args, filter_models, load_models
from benchmarks.harness.models import (
    ModelConfig,
    RouteProvenance,
    RunConfig,
    TestCase as BenchmarkCase,
)
from benchmarks.harness.route_provenance import (
    PROVENANCE_ALLOWLIST,
    RouteContractError,
    fetch_route_provenance,
    preflight_models,
    safe_provenance_dict,
)


MODELS_FILE = Path("/daaf/benchmarks/config/models.yaml")
PREEXISTING_MODEL_KEYS = {
    "haiku-45",
    "sonnet-46",
    "opus-45",
    "opus-46",
    "opus-47",
    "opus-48",
    "fable-5",
    "sonnet-5",
    "glm-51",
    "glm-52",
    "kimi-k26",
    "kimi-k27-code",
    "qwen-36-27b",
    "gemma-4-31b",
    "gemma-4-26b",
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    "gemini-31-pro",
    "nemotron-3-ultra",
    "gemini-31-flash-lite",
    "gpt-56-sol",
    "gpt-56-terra",
    "gpt-56-luna",
    "gpt-55",
    "gpt-54-mini",
}

# ChatGPT-subscription registry keys (Luna since 2026-07-15; Terra + Sol added
# 2026-07-17 for the G1R battery). Kept separate from PREEXISTING_MODEL_KEYS so
# the openrouter/anthropic identity assertion stays independent of this lane.
CHATGPT_SUBSCRIPTION_KEYS = {
    "gpt-56-luna-chatgpt",
    "gpt-56-terra-chatgpt",
    "gpt-56-sol-chatgpt",
}


def coherent_env(**overrides):
    env = {
        "DAAF_PROVIDER_SHIM": "openai",
        "SHIM_BACKEND_MODE": "chatgpt",
        "SHIM_PORT": "4141",
        "ANTHROPIC_BASE_URL": "http://localhost:4141",
    }
    env.update(overrides)
    return env


def healthy_payload(**overrides):
    payload = {
        "status": "ok",
        "backend": "https://chatgpt.com/backend-api/codex",
        "backend_mode": "chatgpt",
        "codex_home_present": True,
        "version": "1.2.5",
        "sanitize_tools": True,
        "reasoning_effort": "high",
        "text_verbosity": "high",
    }
    payload.update(overrides)
    return payload


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class ModelRegistryTests(unittest.TestCase):
    def load_all(self):
        env = {
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api",
            "OPENROUTER_AUTH_TOKEN": "test-only-placeholder",
            "ANTHROPIC_BASE_URL": "https://unrelated.example.test",
            "SHIM_PORT": "4141",
        }
        with patch.dict(os.environ, env, clear=False):
            return load_models(MODELS_FILE)

    def test_preexisting_model_keys_are_identical(self):
        models = self.load_all()
        self.assertEqual(
            PREEXISTING_MODEL_KEYS, set(models) - CHATGPT_SUBSCRIPTION_KEYS
        )

    def test_explicit_key_selects_chatgpt_luna(self):
        models = self.load_all()
        selected = filter_models(models, ["gpt-56-luna-chatgpt"])
        self.assertEqual(1, len(selected))
        self.assertEqual("gpt-5.6-luna", selected[0].id)
        self.assertEqual("chatgpt-subscription", selected[0].provider)
        self.assertEqual(370_000, selected[0].context_window_tokens)
        configured_prices = selected[0].api_equivalent_pricing
        self.assertEqual(LUNA_LONG_CONTEXT_THRESHOLD, configured_prices["threshold_input_tokens"])
        self.assertEqual(LUNA_SHORT_CONTEXT_RATES, configured_prices["short_context"])
        self.assertEqual(LUNA_LONG_CONTEXT_RATES, configured_prices["long_context"])
        self.assertEqual(
            "http://127.0.0.1:4141",
            selected[0].env_overrides["ANTHROPIC_BASE_URL"],
        )
        self.assertEqual(
            "daaf-shim-local",
            selected[0].env_overrides["ANTHROPIC_AUTH_TOKEN"],
        )
        self.assertEqual("", selected[0].env_overrides["ANTHROPIC_API_KEY"])

    def test_provider_filter_adds_chatgpt_without_changing_existing_counts(self):
        models = self.load_all()
        self.assertEqual(8, len(filter_models(models, provider="anthropic")))
        self.assertEqual(17, len(filter_models(models, provider="openrouter")))
        # Luna + Terra + Sol on the ChatGPT-subscription lane (2026-07-17).
        self.assertEqual(3, len(filter_models(models, provider="chatgpt-subscription")))

    def test_terra_and_sol_chatgpt_entries_mirror_luna(self):
        models = self.load_all()
        expected = {
            "gpt-56-terra-chatgpt": "gpt-5.6-terra",
            "gpt-56-sol-chatgpt": "gpt-5.6-sol",
        }
        for key, wire_id in expected.items():
            selected = filter_models(models, [key])
            self.assertEqual(1, len(selected), key)
            entry = selected[0]
            self.assertEqual(wire_id, entry.id)
            self.assertEqual("chatgpt-subscription", entry.provider)
            self.assertEqual(370_000, entry.context_window_tokens)
            self.assertEqual("high", entry.effort_level)
            self.assertEqual("not_separately_billed", entry.actual_billing_treatment)
            prices = entry.api_equivalent_pricing
            self.assertEqual(LUNA_LONG_CONTEXT_THRESHOLD, prices["threshold_input_tokens"])
            self.assertEqual(LUNA_SHORT_CONTEXT_RATES, prices["short_context"])
            self.assertEqual(LUNA_LONG_CONTEXT_RATES, prices["long_context"])
            # Purity selectors all pinned to the bare wire ID.
            for selector in (
                "ANTHROPIC_DEFAULT_OPUS_MODEL",
                "ANTHROPIC_DEFAULT_SONNET_MODEL",
                "CLAUDE_CODE_SUBAGENT_MODEL",
            ):
                self.assertEqual(wire_id, entry.env_overrides[selector])
            # Fail-closed local route overlay is applied identically to Luna.
            self.assertEqual(
                "http://127.0.0.1:4141", entry.env_overrides["ANTHROPIC_BASE_URL"]
            )
            self.assertEqual(
                "daaf-shim-local", entry.env_overrides["ANTHROPIC_AUTH_TOKEN"]
            )

    def test_terra_and_sol_pass_batch_route_preflight(self):
        models = self.load_all()
        selected = filter_models(
            models, ["gpt-56-terra-chatgpt", "gpt-56-sol-chatgpt"]
        )
        opener = Mock(return_value=FakeResponse(healthy_payload()))
        snapshots = preflight_models(selected, environ=coherent_env(), opener=opener)
        self.assertEqual(
            {"gpt-56-terra-chatgpt", "gpt-56-sol-chatgpt"}, set(snapshots)
        )
        # One shared /health round-trip covers all selected subscription models.
        self.assertEqual(1, opener.call_count)

    def test_loading_registry_does_not_call_network(self):
        with patch("benchmarks.harness.route_provenance.urlopen") as network:
            self.load_all()
        network.assert_not_called()

    def test_help_does_not_call_network(self):
        parser = argparse.ArgumentParser()
        with patch("benchmarks.harness.route_provenance.urlopen") as network:
            add_model_args(parser)
            with self.assertRaises(SystemExit) as stopped:
                parser.parse_args(["--help"])
        self.assertEqual(0, stopped.exception.code)
        network.assert_not_called()


class RouteContractTests(unittest.TestCase):
    def test_route_coherence_failures(self):
        cases = [
            coherent_env(DAAF_PROVIDER_SHIM="off"),
            coherent_env(SHIM_BACKEND_MODE="openai"),
            coherent_env(ANTHROPIC_BASE_URL="https://api.anthropic.com"),
            coherent_env(ANTHROPIC_BASE_URL="http://127.0.0.1:4142"),
        ]
        for env in cases:
            with self.subTest(env=env):
                with self.assertRaises(RouteContractError):
                    fetch_route_provenance(
                        environ=env,
                        opener=lambda *args, **kwargs: FakeResponse(healthy_payload()),
                    )

    def test_health_contract_failures(self):
        bad_payloads = [
            healthy_payload(status="degraded"),
            healthy_payload(backend_mode="openai"),
            healthy_payload(sanitize_tools=False),
            healthy_payload(codex_home_present=False),
            healthy_payload(backend="https://api.openai.com/v1"),
            healthy_payload(version=""),
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(RouteContractError):
                    fetch_route_provenance(
                        environ=coherent_env(),
                        opener=lambda *args, payload=payload, **kwargs: FakeResponse(payload),
                    )

    def test_configured_shim_port_is_canonicalized(self):
        env = coherent_env(
            SHIM_PORT="4242",
            ANTHROPIC_BASE_URL="http://localhost:4242",
        )
        opener = Mock(return_value=FakeResponse(healthy_payload()))
        provenance = fetch_route_provenance(environ=env, opener=opener)
        self.assertEqual("http://127.0.0.1:4242", provenance.endpoint_origin)
        self.assertEqual("http://127.0.0.1:4242/health", opener.call_args.args[0])

    def test_success_returns_secret_safe_allowlist(self):
        payload = healthy_payload(
            access_token="must-not-survive",
            auth_json="must-not-survive-either",
        )
        provenance = fetch_route_provenance(
            environ=coherent_env(),
            opener=lambda *args, **kwargs: FakeResponse(payload),
        )
        safe = safe_provenance_dict(provenance)
        self.assertEqual(PROVENANCE_ALLOWLIST, set(safe))
        rendered = json.dumps(safe)
        self.assertNotIn("must-not-survive", rendered)
        self.assertEqual("http://127.0.0.1:4141", safe["endpoint_origin"])
        self.assertTrue(safe["sanitizer_enabled"])
        self.assertTrue(safe["auth_store_readable"])

    def test_batch_preflight_fetches_health_once_for_chatgpt_models(self):
        models = [
            ModelConfig("gpt-5.6-luna", "Luna A", provider="chatgpt-subscription", key="a"),
            ModelConfig("gpt-5.6-luna", "Luna B", provider="chatgpt-subscription", key="b"),
            ModelConfig("claude-sonnet-4-6", "Sonnet", provider="anthropic"),
        ]
        opener = Mock(return_value=FakeResponse(healthy_payload()))
        snapshots = preflight_models(models, environ=coherent_env(), opener=opener)
        self.assertEqual({"a", "b"}, set(snapshots))
        self.assertEqual(1, opener.call_count)


class ExecutorRouteTests(unittest.TestCase):
    def setUp(self):
        env = {
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api",
            "OPENROUTER_AUTH_TOKEN": "test-only-placeholder",
        }
        with patch.dict(os.environ, env, clear=False):
            self.model = load_models(MODELS_FILE)["gpt-56-luna-chatgpt"]
        self.case = BenchmarkCase(
            id="route-test",
            category="test",
            prompt="No live request is launched in this unit test.",
            expected={},
        )
        self.config = RunConfig(self.case, self.model, 0)

    def test_model_purity_and_context_are_applied_to_child_only(self):
        result_payload = {
            "type": "result",
            "subtype": "success",
            "session_id": "fake-session",
            "result": "ok",
            "total_cost_usd": 123.45,
            "num_turns": 1,
            "modelUsage": {
                "gpt-5.6-luna": {
                    "inputTokens": 10,
                    "outputTokens": 2,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                }
            },
        }
        process = Mock()
        process.communicate.return_value = (json.dumps(result_payload), "")
        process.returncode = 0
        route = RouteProvenance(provider="chatgpt-subscription")

        with patch("benchmarks.harness.executor.revalidate_route", return_value=route):
            with patch("benchmarks.harness.executor.subprocess.Popen", return_value=process) as popen:
                result = execute_run(self.config)

        child_env = popen.call_args.kwargs["env"]
        for selector in (
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "CLAUDE_CODE_SUBAGENT_MODEL",
        ):
            self.assertEqual("gpt-5.6-luna", child_env[selector])
        self.assertEqual("370000", child_env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"])
        self.assertEqual("gpt-5.6-luna", popen.call_args.args[0][4])
        self.assertIsNone(result.total_cost_usd)
        self.assertEqual(["gpt-5.6-luna"], result.model_identity.claude_cli_model_usage_ids)
        self.assertIsNone(result.model_identity.backend_confirmed_model_id)
        self.assertEqual("partial", result.usage_observed.completeness)
        self.assertIsNotNone(result.start_time_utc)
        self.assertIsNotNone(result.end_time_utc)
        self.assertIsNotNone(result.wall_clock_seconds)

    def test_preflight_failure_aborts_before_process_launch(self):
        with patch(
            "benchmarks.harness.executor.revalidate_route",
            side_effect=RouteContractError("sanitizer mismatch"),
        ):
            with patch("benchmarks.harness.executor.subprocess.Popen") as popen:
                result = execute_run(self.config)
        popen.assert_not_called()
        self.assertIn("RouteContractError", result.error)
        self.assertIn("sanitizer mismatch", result.error)


if __name__ == "__main__":
    unittest.main()
