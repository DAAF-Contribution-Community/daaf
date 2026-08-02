"""Focused deterministic tests for ChatGPT-subscription model routing.

Synthetic health fixtures are schema/provenance contract evidence only; they make
no claim that a provider accepts or serves any requested tier.
"""

import argparse
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from benchmarks.harness import route_provenance
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
    RunResult,
    TestCase as BenchmarkCase,
)
from benchmarks.harness.route_provenance import (
    PROVENANCE_ALLOWLIST,
    RouteContractError,
    _validate_gpt_service_tier_block,
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

# OpenRouter keys added after the PREEXISTING snapshot (kimi-k3 added
# 2026-07-17 for the G1R Kimi K3 battery). Kept separate so the preexisting
# identity assertion documents exactly what predates the G1R additions.
G1R_OPENROUTER_ADDITIONS = {
    "kimi-k3",
}

# Concurrent OpenRouter keys added after the PREEXISTING snapshot. Kept separate
# from the G1R Kimi K3 addition so both post-snapshot registry changes remain
# explicit in the preexisting-key identity assertion. deepseek-v4-flash-0731
# added 2026-08-02, superseding the retired deepseek-v4-flash (removed from
# PREEXISTING_MODEL_KEYS the same day; see the REMOVED 2026-08-02 block in
# config/models.yaml).
POST_SNAPSHOT_OPENROUTER_ADDITIONS = {
    "gemini-35-flash",
    "gemini-36-flash",
    "gemini-35-flash-lite",
    "gemini-25-pro",
    "deepseek-v4-flash-0731",
}

# Anthropic keys added after the PREEXISTING snapshot (opus-5 added 2026-07-25
# for the Opus 5 evaluation). Kept separate, mirroring G1R_OPENROUTER_ADDITIONS,
# so the preexisting identity assertion keeps documenting exactly what predates
# each later addition.
ANTHROPIC_ADDITIONS = {
    "opus-5",
}


def coherent_env(**overrides):
    env = {
        "DAAF_PROVIDER_SHIM": "openai",
        "SHIM_BACKEND_MODE": "chatgpt",
        "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
        "SHIM_PORT": "4141",
        "ANTHROPIC_BASE_URL": "http://localhost:4141",
    }
    env.update(overrides)
    return env


def healthy_tier_block(backend_mode="chatgpt", **overrides):
    payload = {
        "backend_mode": backend_mode,
        "requested_tier_vocabulary": "priority",
        "policy": {
            "status": "ok",
            "backend_mode": backend_mode,
            "enabled": False,
            "effective": False,
        },
        "native_fast_disabled": True,
        "latest_terminal": None,
    }
    payload.update(overrides)
    return payload


def healthy_latest_terminal(**overrides):
    payload = {
        "model": "gpt-5.6-sol",
        "requested_service_tier": "priority",
        "requested_source": "shim_global",
        "served_service_tier": "default",
        "completed_at": "2026-07-25T18:00:00Z",
    }
    payload.update(overrides)
    return payload


def healthy_payload(**overrides):
    payload = {
        "service": "daaf-anthropic-openai-shim",
        "status": "ok",
        "backend": "https://chatgpt.com/backend-api/codex",
        "backend_mode": "chatgpt",
        "codex_home_present": True,
        "version": "1.3.9",
        "sanitize_tools": True,
        "reasoning_effort": "high",
        "text_verbosity": "high",
        "gpt_service_tier": healthy_tier_block(),
    }
    payload.update(overrides)
    return payload


class FakeResponse:
    def __init__(self, payload, status=200, raw_body=None):
        self.status = status
        self.payload = payload
        self.raw_body = raw_body

    def read(self, limit=None):
        self.read_limit = limit
        if self.raw_body is not None:
            raw = self.raw_body
        else:
            raw = json.dumps(self.payload).encode("utf-8")
        return raw[:limit] if limit is not None else raw

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
            PREEXISTING_MODEL_KEYS,
            set(models)
            - CHATGPT_SUBSCRIPTION_KEYS
            - G1R_OPENROUTER_ADDITIONS
            - POST_SNAPSHOT_OPENROUTER_ADDITIONS
            - ANTHROPIC_ADDITIONS,
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
        self.assertEqual(34, len(models))
        # 8 preexisting + opus-5 (added 2026-07-25 for the Opus 5 evaluation).
        self.assertEqual(9, len(filter_models(models, provider="anthropic")))
        # 17 preexisting + Kimi K3 + four later Gemini additions.
        self.assertEqual(22, len(filter_models(models, provider="openrouter")))
        # Luna + Terra + Sol on the ChatGPT-subscription lane (2026-07-17).
        self.assertEqual(3, len(filter_models(models, provider="chatgpt-subscription")))

    def test_kimi_k3_entry_is_openrouter_with_full_purity_pinning(self):
        models = self.load_all()
        selected = filter_models(models, ["kimi-k3"])
        self.assertEqual(1, len(selected))
        entry = selected[0]
        self.assertEqual("moonshotai/kimi-k3", entry.id)
        self.assertEqual("openrouter", entry.provider)
        self.assertEqual(3.00, entry.pricing.input)
        self.assertEqual(15.00, entry.pricing.output)
        # Cache-read rate from GET /api/v1/models/moonshotai/kimi-k3/endpoints
        # (2026-07-17); the model page displays no cache rate.
        self.assertEqual(0.30, entry.pricing.cached_input)
        # All three purity selectors pinned to the bare K3 slug so dispatched
        # children stay model-pure under the G1R validity gate.
        for selector in (
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "CLAUDE_CODE_SUBAGENT_MODEL",
        ):
            self.assertEqual("moonshotai/kimi-k3", entry.env_overrides[selector])

    def test_chatgpt_entries_preserve_tier_aliases_without_flatten_override(self):
        models = self.load_all()
        # Per-model published schedules. Terra/Sol originally (wrongly) copied
        # Luna's schedule; the registry was corrected 2026-07-29 to each model's
        # own published tier (developers.openai.com), so each entry is asserted
        # against its own rates. Luna keeps asserting the cost_estimator
        # constants to preserve the registry <-> estimator coherence check.
        TERRA_SHORT_CONTEXT_RATES = {
            "input": 2.50, "cached_input": 0.25, "cache_write": 3.125, "output": 15.00,
        }
        TERRA_LONG_CONTEXT_RATES = {
            "input": 5.00, "cached_input": 0.50, "cache_write": 6.25, "output": 22.50,
        }
        SOL_SHORT_CONTEXT_RATES = {
            "input": 5.00, "cached_input": 0.50, "cache_write": 6.25, "output": 30.00,
        }
        SOL_LONG_CONTEXT_RATES = {
            "input": 10.00, "cached_input": 1.00, "cache_write": 12.50, "output": 45.00,
        }
        expected = {
            "gpt-56-luna-chatgpt": (
                "gpt-5.6-luna", LUNA_SHORT_CONTEXT_RATES, LUNA_LONG_CONTEXT_RATES,
            ),
            "gpt-56-terra-chatgpt": (
                "gpt-5.6-terra", TERRA_SHORT_CONTEXT_RATES, TERRA_LONG_CONTEXT_RATES,
            ),
            "gpt-56-sol-chatgpt": (
                "gpt-5.6-sol", SOL_SHORT_CONTEXT_RATES, SOL_LONG_CONTEXT_RATES,
            ),
        }
        for key, (parent_id, short_rates, long_rates) in expected.items():
            with self.subTest(key=key):
                selected = filter_models(models, [key])
                self.assertEqual(1, len(selected))
                entry = selected[0]
                self.assertEqual(parent_id, entry.id)
                self.assertEqual("chatgpt-subscription", entry.provider)
                self.assertEqual(370_000, entry.context_window_tokens)
                self.assertEqual("high", entry.effort_level)
                self.assertEqual("not_separately_billed", entry.actual_billing_treatment)
                prices = entry.api_equivalent_pricing
                self.assertEqual(
                    LUNA_LONG_CONTEXT_THRESHOLD, prices["threshold_input_tokens"]
                )
                self.assertEqual(short_rates, prices["short_context"])
                self.assertEqual(long_rates, prices["long_context"])
                # Keep semantic tier selection operative while both aliases resolve
                # to the same parent model for the child-model purity condition.
                self.assertEqual(
                    parent_id,
                    entry.env_overrides["ANTHROPIC_DEFAULT_OPUS_MODEL"],
                )
                self.assertEqual(
                    parent_id,
                    entry.env_overrides["ANTHROPIC_DEFAULT_SONNET_MODEL"],
                )
                self.assertNotIn(
                    "CLAUDE_CODE_SUBAGENT_MODEL", entry.env_overrides
                )
                # Fail-closed local route overlay is applied identically to all three.
                self.assertEqual(
                    "http://127.0.0.1:4141",
                    entry.env_overrides["ANTHROPIC_BASE_URL"],
                )
                self.assertEqual(
                    "daaf-shim-local",
                    entry.env_overrides["ANTHROPIC_AUTH_TOKEN"],
                )
                self.assertEqual("", entry.env_overrides["ANTHROPIC_API_KEY"])

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
        with patch("benchmarks.harness.route_provenance.build_opener") as network:
            self.load_all()
        network.assert_not_called()

    def test_help_does_not_call_network(self):
        parser = argparse.ArgumentParser()
        with patch("benchmarks.harness.route_provenance.build_opener") as network:
            add_model_args(parser)
            with self.assertRaises(SystemExit) as stopped:
                parser.parse_args(["--help"])
        self.assertEqual(0, stopped.exception.code)
        network.assert_not_called()


class RouteContractTests(unittest.TestCase):
    def test_default_health_transport_is_loopback_no_proxy_no_redirect_and_bounded(self):
        response = FakeResponse(healthy_payload())

        class NetworkOpener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return response

        network = NetworkOpener()
        with patch.object(route_provenance, "build_opener", return_value=network) as build:
            provenance = fetch_route_provenance(environ=coherent_env(), timeout=2.5)
        self.assertEqual("chatgpt", provenance.backend_mode)
        self.assertEqual(
            "http://127.0.0.1:4141/health", network.request.full_url
        )
        self.assertEqual(2.5, network.timeout)
        self.assertEqual(
            route_provenance.HEALTH_BODY_LIMIT + 1, response.read_limit
        )
        handlers = build.call_args.args
        self.assertTrue(
            any(
                isinstance(item, route_provenance.ProxyHandler)
                and item.proxies == {}
                for item in handlers
            )
        )
        redirect = next(
            item
            for item in handlers
            if isinstance(item, route_provenance._RejectRedirects)
        )
        self.assertIsNone(
            redirect.redirect_request(
                None, None, 302, "Found", {}, "http://example.invalid"
            )
        )

    def test_oversized_health_body_is_rejected_before_json_decode(self):
        oversized = b"{" + b"x" * route_provenance.HEALTH_BODY_LIMIT
        with self.assertRaisesRegex(RouteContractError, "16 KiB"):
            fetch_route_provenance(
                environ=coherent_env(),
                opener=lambda *args, **kwargs: FakeResponse(
                    healthy_payload(), raw_body=oversized
                ),
            )

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

    def test_exact_gpt_ambient_boundary_fails_before_health_or_provider_execution(self):
        controls = {
            "DAAF_PROVIDER_SHIM": (None, "", "OpenAI", " openai", "openai ", "off"),
            "SHIM_BACKEND_MODE": (None, "", "ChatGPT", " chatgpt", "chatgpt ", "openai"),
            "CLAUDE_CODE_DISABLE_FAST_MODE": (None, "", "0", "TRUE", " 1", "1 ", "01"),
        }
        for name, malformed_values in controls.items():
            for value in malformed_values:
                with self.subTest(control=name, value=value):
                    env = coherent_env()
                    if value is None:
                        env.pop(name)
                    else:
                        env[name] = value
                    opener = Mock(return_value=FakeResponse(healthy_payload()))
                    with self.assertRaises(RouteContractError):
                        fetch_route_provenance(environ=env, opener=opener)
                    opener.assert_not_called()

    def test_native_anthropic_only_selection_does_not_inherit_gpt_boundary(self):
        model = ModelConfig(
            "claude-opus-4-8", "Opus 4.8", provider="anthropic", key="opus"
        )
        opener = Mock()
        snapshots = preflight_models(
            [model],
            environ={
                "DAAF_PROVIDER_SHIM": "OpenAI",
                "SHIM_BACKEND_MODE": " CHATGPT ",
                "CLAUDE_CODE_DISABLE_FAST_MODE": "0",
            },
            opener=opener,
        )
        self.assertEqual({}, snapshots)
        opener.assert_not_called()

    def test_health_contract_failures(self):
        bad_payloads = [
            healthy_payload(service="unrelated-service"),
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

    def test_gpt_service_tier_rejects_missing_extra_and_route_mismatch(self):
        extra_block = healthy_tier_block(extra="not-allowed")
        missing_block_field = healthy_tier_block()
        del missing_block_field["latest_terminal"]
        wrong_backend = healthy_tier_block(backend_mode="openai")
        wrong_vocabulary = healthy_tier_block(requested_tier_vocabulary="fast")
        missing_native_flag = healthy_tier_block()
        del missing_native_flag["native_fast_disabled"]
        bad_payloads = [
            healthy_payload(gpt_service_tier=None),
            healthy_payload(gpt_service_tier=extra_block),
            healthy_payload(gpt_service_tier=missing_block_field),
            healthy_payload(gpt_service_tier=wrong_backend),
            healthy_payload(gpt_service_tier=wrong_vocabulary),
            healthy_payload(gpt_service_tier=missing_native_flag),
            *(
                healthy_payload(
                    gpt_service_tier=healthy_tier_block(native_fast_disabled=value)
                )
                for value in (False, 0, 1, "true", None, [], {})
            ),
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(RouteContractError):
                    fetch_route_provenance(
                        environ=coherent_env(),
                        opener=lambda *args, payload=payload, **kwargs: FakeResponse(payload),
                    )

    def test_gpt_service_tier_rejects_duplicate_nested_json_key(self):
        payload = healthy_payload()
        rendered = json.dumps(payload).encode("utf-8")
        marker = b'"gpt_service_tier": {'
        duplicated = rendered.replace(
            marker,
            marker + b'"backend_mode": "chatgpt", ',
            1,
        )
        with self.assertRaises(RouteContractError):
            fetch_route_provenance(
                environ=coherent_env(),
                opener=lambda *args, **kwargs: FakeResponse(
                    payload, raw_body=duplicated
                ),
            )

    def test_gpt_service_tier_rejects_malformed_or_incoherent_policy(self):
        bad_policies = [
            {
                "status": "ok",
                "backend_mode": "chatgpt",
                "enabled": False,
            },
            {
                "status": "ok",
                "backend_mode": "chatgpt",
                "enabled": False,
                "effective": False,
                "extra": None,
            },
            {
                "status": "unknown",
                "backend_mode": None,
                "enabled": False,
                "effective": False,
            },
            {
                "status": "invalid",
                "backend_mode": "chatgpt",
                "enabled": False,
                "effective": False,
            },
            {
                "status": "missing",
                "backend_mode": None,
                "enabled": True,
                "effective": False,
            },
            {
                "status": "ok",
                "backend_mode": None,
                "enabled": False,
                "effective": False,
            },
            {
                "status": "ok",
                "backend_mode": "chatgpt",
                "enabled": True,
                "effective": False,
            },
            {
                "status": "ok",
                "backend_mode": "chatgpt",
                "enabled": False,
                "effective": True,
            },
            {
                "status": "ok",
                "backend_mode": "chatgpt",
                "enabled": 1,
                "effective": True,
            },
        ]
        for policy in bad_policies:
            payload = healthy_payload(
                gpt_service_tier=healthy_tier_block(policy=policy)
            )
            with self.subTest(policy=policy):
                with self.assertRaises(RouteContractError):
                    fetch_route_provenance(
                        environ=coherent_env(),
                        opener=lambda *args, payload=payload, **kwargs: FakeResponse(payload),
                    )

    def test_gpt_service_tier_rejects_malformed_latest_terminal(self):
        missing_latest_field = healthy_latest_terminal()
        del missing_latest_field["completed_at"]
        bad_latest_values = [
            "not-an-object",
            missing_latest_field,
            healthy_latest_terminal(extra="not-allowed"),
            healthy_latest_terminal(model="bad model"),
            healthy_latest_terminal(requested_service_tier="fast"),
            healthy_latest_terminal(requested_service_tier=" priority"),
            healthy_latest_terminal(requested_source="policy"),
            healthy_latest_terminal(requested_source=["shim_global"]),
            healthy_latest_terminal(requested_source="Shim_Global"),
            healthy_latest_terminal(requested_source=" shim_global"),
            healthy_latest_terminal(requested_service_tier=None, requested_source="shim_global"),
            healthy_latest_terminal(requested_source="none"),
            healthy_latest_terminal(served_service_tier="FAST"),
            healthy_latest_terminal(served_service_tier={"tier": "fast"}),
            healthy_latest_terminal(served_service_tier="fast "),
            healthy_latest_terminal(completed_at="2026-02-30T18:00:00Z"),
            healthy_latest_terminal(completed_at="2026-07-25T18:00:00.000Z"),
        ]
        for latest in bad_latest_values:
            payload = healthy_payload(
                gpt_service_tier=healthy_tier_block(latest_terminal=latest)
            )
            with self.subTest(latest=latest):
                with self.assertRaises(RouteContractError):
                    fetch_route_provenance(
                        environ=coherent_env(),
                        opener=lambda *args, payload=payload, **kwargs: FakeResponse(payload),
                    )

    def test_reusable_tier_validator_rejects_legacy_requested_fast_for_both_backends(self):
        for backend in ("chatgpt", "openai"):
            with self.subTest(backend=backend):
                block = healthy_tier_block(
                    backend_mode=backend,
                    requested_tier_vocabulary="fast",
                )
                with self.assertRaisesRegex(RouteContractError, "requested vocabulary"):
                    _validate_gpt_service_tier_block(block, backend)

    def test_reusable_tier_validator_accepts_openai_priority_vocabulary(self):
        block = healthy_tier_block(
            backend_mode="openai",
            policy={
                "status": "ok",
                "backend_mode": "openai",
                "enabled": True,
                "effective": True,
            },
            latest_terminal=healthy_latest_terminal(
                requested_service_tier="priority",
                served_service_tier="priority",
            ),
        )
        safe = _validate_gpt_service_tier_block(block, "openai")
        self.assertEqual("priority", safe["gpt_requested_tier_vocabulary"])
        self.assertTrue(safe["gpt_policy_enabled"])
        self.assertTrue(safe["gpt_policy_effective"])
        self.assertNotIn("latest_terminal", safe)

        null_terminal = healthy_latest_terminal(
            requested_service_tier=None,
            requested_source="none",
            served_service_tier=None,
        )
        safe = _validate_gpt_service_tier_block(
            healthy_tier_block(
                backend_mode="openai", latest_terminal=null_terminal
            ),
            "openai",
        )
        self.assertEqual("priority", safe["gpt_requested_tier_vocabulary"])

    def test_route_provenance_keeps_legacy_positional_constructor_order(self):
        legacy = RouteProvenance(
            "chatgpt_subscription_shim",
            "chatgpt-subscription",
            "http://127.0.0.1:4141",
            "chatgpt",
            "https://chatgpt.com/backend-api/codex",
            "1.3.7",
            True,
            "deployed_default",
            True,
            "high",
            "high",
            "2026-07-25T18:00:00+00:00",
        )
        self.assertEqual("2026-07-25T18:00:00+00:00", legacy.captured_at)
        self.assertIsNone(legacy.gpt_requested_tier_vocabulary)
        self.assertIsNone(legacy.gpt_policy_status)
        self.assertIsNone(legacy.native_fast_disabled)

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
        tier_block = healthy_tier_block(
            policy={
                "status": "ok",
                "backend_mode": "chatgpt",
                "enabled": True,
                "effective": True,
            },
            latest_terminal=healthy_latest_terminal(
                model="gpt-5.6-sol-terminal-only",
                # Exact served `fast` is compatibility-only terminal evidence;
                # requested vocabulary remains canonical `priority`.
                served_service_tier="fast",
            ),
        )
        payload = healthy_payload(
            access_token="must-not-survive",
            auth_json="must-not-survive-either",
            gpt_service_tier=tier_block,
        )
        provenance = fetch_route_provenance(
            environ=coherent_env(),
            opener=lambda *args, **kwargs: FakeResponse(payload),
        )
        safe = safe_provenance_dict(provenance)
        self.assertEqual(PROVENANCE_ALLOWLIST, set(safe))
        rendered = json.dumps(safe)
        self.assertNotIn("must-not-survive", rendered)
        self.assertNotIn("latest_terminal", safe)
        self.assertNotIn("served_service_tier", safe)
        self.assertNotIn("gpt-5.6-sol-terminal-only", rendered)
        self.assertEqual("http://127.0.0.1:4141", safe["endpoint_origin"])
        self.assertTrue(safe["sanitizer_enabled"])
        self.assertTrue(safe["auth_store_readable"])
        self.assertEqual("priority", safe["gpt_requested_tier_vocabulary"])
        self.assertEqual("ok", safe["gpt_policy_status"])
        self.assertEqual("chatgpt", safe["gpt_policy_backend_mode"])
        self.assertTrue(safe["gpt_policy_enabled"])
        self.assertTrue(safe["gpt_policy_effective"])
        self.assertTrue(safe["native_fast_disabled"])

        # A valid shim-global terminal is contract-checked above but cannot become
        # evidence about this run's served tier, billing, performance, or identity.
        run = RunResult("tier-provenance", "gpt-5.6-sol", "Sol", 0)
        run.route_provenance = provenance
        run_record = run.to_dict()
        self.assertNotIn("latest_terminal", run_record["route_provenance"])
        self.assertNotIn("served_service_tier", run_record["route_provenance"])
        self.assertIsNone(
            run_record["model_identity"]["backend_confirmed_model_id"]
        )
        self.assertEqual("unknown", run_record["actual_billing"]["charge_status"])
        self.assertIsNone(
            run_record["actual_billing"]["actual_marginal_charge_usd"]
        )

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
            models = load_models(MODELS_FILE)
        self.parent_ids = {
            "gpt-56-luna-chatgpt": "gpt-5.6-luna",
            "gpt-56-terra-chatgpt": "gpt-5.6-terra",
            "gpt-56-sol-chatgpt": "gpt-5.6-sol",
        }
        self.models = {key: models[key] for key in self.parent_ids}
        self.explicit_flatten_model = models["gpt-56-sol"]
        self.case = BenchmarkCase(
            id="route-test",
            category="test",
            prompt="No live request is launched in this unit test.",
            expected={},
        )

    def test_tier_aliases_and_context_are_applied_to_each_child_environment(self):
        route = RouteProvenance(provider="chatgpt-subscription")

        for key, parent_id in self.parent_ids.items():
            with self.subTest(key=key):
                result_payload = {
                    "type": "result",
                    "subtype": "success",
                    "session_id": "fake-session",
                    "result": "ok",
                    "total_cost_usd": 123.45,
                    "num_turns": 1,
                    "modelUsage": {
                        parent_id: {
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
                config = RunConfig(self.case, self.models[key], 0)

                # A conflicting ambient sentinel proves the executor scrubs the
                # flatten selector before applying this entry's two tier aliases.
                ambient = {
                    "SHIM_PORT": "4141",
                    "CLAUDE_CODE_SUBAGENT_MODEL": "ambient-must-not-survive",
                }
                with patch.dict(os.environ, ambient, clear=True):
                    with patch(
                        "benchmarks.harness.executor.revalidate_route",
                        return_value=route,
                    ):
                        with patch(
                            "benchmarks.harness.executor.subprocess.Popen",
                            return_value=process,
                        ) as popen:
                            result = execute_run(config)

                child_env = popen.call_args.kwargs["env"]
                self.assertEqual(
                    parent_id, child_env["ANTHROPIC_DEFAULT_OPUS_MODEL"]
                )
                self.assertEqual(
                    parent_id, child_env["ANTHROPIC_DEFAULT_SONNET_MODEL"]
                )
                self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL", child_env)
                self.assertEqual(
                    "370000", child_env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"]
                )
                self.assertEqual(parent_id, popen.call_args.args[0][4])
                self.assertIsNone(result.total_cost_usd)
                self.assertEqual(
                    [parent_id], result.model_identity.claude_cli_model_usage_ids
                )
                self.assertIsNone(result.model_identity.backend_confirmed_model_id)
                self.assertEqual("partial", result.usage_observed.completeness)
                self.assertIsNotNone(result.start_time_utc)
                self.assertIsNotNone(result.end_time_utc)
                self.assertIsNotNone(result.wall_clock_seconds)

    def test_explicit_model_flatten_override_is_reapplied_after_ambient_scrub(self):
        model = self.explicit_flatten_model
        result_payload = {
            "type": "result",
            "subtype": "success",
            "session_id": "fake-session",
            "result": "ok",
            "total_cost_usd": 0.01,
            "num_turns": 1,
            "modelUsage": {
                model.id: {
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
        config = RunConfig(self.case, model, 0)
        ambient = {"CLAUDE_CODE_SUBAGENT_MODEL": "ambient-must-not-survive"}

        with patch.dict(os.environ, ambient, clear=True):
            with patch("benchmarks.harness.executor.revalidate_route"):
                with patch(
                    "benchmarks.harness.executor.subprocess.Popen",
                    return_value=process,
                ) as popen:
                    execute_run(config)

        child_env = popen.call_args.kwargs["env"]
        self.assertEqual(
            "openai/gpt-5.6-sol",
            child_env["CLAUDE_CODE_SUBAGENT_MODEL"],
        )
        self.assertEqual(
            "openai/gpt-5.6-sol",
            child_env["ANTHROPIC_DEFAULT_OPUS_MODEL"],
        )
        self.assertEqual(
            "openai/gpt-5.6-sol",
            child_env["ANTHROPIC_DEFAULT_SONNET_MODEL"],
        )

    def test_preflight_failure_aborts_before_process_launch(self):
        config = RunConfig(self.case, self.models["gpt-56-luna-chatgpt"], 0)
        with patch(
            "benchmarks.harness.executor.revalidate_route",
            side_effect=RouteContractError("sanitizer mismatch"),
        ):
            with patch("benchmarks.harness.executor.subprocess.Popen") as popen:
                result = execute_run(config)
        popen.assert_not_called()
        self.assertIn("RouteContractError", result.error)
        self.assertIn("sanitizer mismatch", result.error)


if __name__ == "__main__":
    unittest.main()
