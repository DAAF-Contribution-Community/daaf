"""Provider-free regression tests for the DAAF deployment smoke harness.

Standard-library unittest + unittest.mock ONLY — no third-party test deps, no
network, no live provider calls. Synthetic health fixtures are contract evidence
only; they do not claim provider acceptance of any requested tier. Every fixture
lives under scripts/scratch/ (NEVER /tmp) and is removed in tearDown.

This module is wired into Tier D as TD.0 (run BEFORE the broader batteries) so an
official Tier D run first validates its own harness: environment sanitization,
Tier D failure-evidence capture, Pester/battery output routing, per-run Tier 2
sandbox cleanup, and the stricter T2.2 freshness/success semantics.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke.py'
"""

import json
import os
import subprocess
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock
from urllib.error import URLError

# --- Import path guard: mirror run_deploy_smoke.py so route_detection /
# smoke_probes / run_deploy_smoke and the benchmarks harness all import
# regardless of the caller's CWD. ---
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]                       # tests/python/ -> tests/ -> /daaf
_SMOKE_DIR = _REPO_ROOT / "scripts" / "deploy_smoke"
for _p in (str(_REPO_ROOT), str(_SMOKE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import route_detection  # noqa: E402
import smoke_probes  # noqa: E402
import run_deploy_smoke  # noqa: E402
from route_detection import Verdict  # noqa: E402

_SCRATCH = _REPO_ROOT / "scripts" / "scratch"


def _scratch_dir(prefix):
    """Create and return a fresh, uniquely named scratch directory (inside the
    project, per the /tmp prohibition)."""
    d = _SCRATCH / f"{prefix}_{uuid.uuid4().hex[:10]}"
    d.mkdir(parents=True, exist_ok=False)
    return d


class _HealthResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload
        self.read_limit = None

    def read(self, limit=None):
        self.read_limit = limit
        if isinstance(self.payload, bytes):
            return self.payload[:limit] if limit is not None else self.payload
        raw = json.dumps(self.payload).encode("utf-8")
        return raw[:limit] if limit is not None else raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _HealthOpener:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


class LocalHealthTransportTests(unittest.TestCase):
    def test_fixed_loopback_no_proxy_no_redirect_and_bounded_valid_read(self):
        response = _HealthResponse({"status": "ok"})
        opener = _HealthOpener(response)
        with mock.patch.object(smoke_probes, "build_opener", return_value=opener) as build:
            payload = smoke_probes._read_local_health(timeout=3.5)
        self.assertEqual(payload, {"status": "ok"})
        self.assertEqual(opener.request.full_url, smoke_probes.SHIM_HEALTH_URL)
        self.assertEqual(opener.timeout, 3.5)
        self.assertEqual(response.read_limit, smoke_probes.HEALTH_BODY_LIMIT + 1)
        handlers = build.call_args.args
        self.assertTrue(any(isinstance(item, smoke_probes.ProxyHandler) and item.proxies == {} for item in handlers))
        redirect_handler = next(item for item in handlers if isinstance(item, smoke_probes._RejectHealthRedirects))
        self.assertIsNone(redirect_handler.redirect_request(None, None, 302, "Found", {}, "http://example.invalid"))

    def test_oversized_health_is_rejected_before_json_decode(self):
        body = b"{" + b"x" * smoke_probes.HEALTH_BODY_LIMIT
        with self.assertRaisesRegex(ValueError, "16 KiB"):
            smoke_probes._read_local_health(opener=_HealthOpener(_HealthResponse(body)))


class RouteServiceTierCoherenceTests(unittest.TestCase):
    def _env(self, backend):
        env = {
            "DAAF_PROVIDER_SHIM": "openai",
            "SHIM_BACKEND_MODE": backend,
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:4141",
            "ANTHROPIC_AUTH_TOKEN": "shim-local-token",
            "CLAUDE_CODE_DISABLE_FAST_MODE": "1",
        }
        if backend == "chatgpt":
            env["CODEX_HOME"] = "/bounded/codex-home"
        else:
            env["OPENAI_API_KEY"] = "secret-not-reported"
        return env

    def test_safe_fingerprint_includes_exact_native_disable_control(self):
        exact = route_detection.env_fingerprint(
            {"CLAUDE_CODE_DISABLE_FAST_MODE": "1"}
        )
        malformed = route_detection.env_fingerprint(
            {"CLAUDE_CODE_DISABLE_FAST_MODE": " arbitrary\ntext "}
        )
        self.assertEqual(exact["CLAUDE_CODE_DISABLE_FAST_MODE"], "1")
        self.assertEqual(
            malformed["CLAUDE_CODE_DISABLE_FAST_MODE"],
            "<invalid:not-exact-1>",
        )
        self.assertNotIn("arbitrary", json.dumps(malformed))

    def test_both_exact_gpt_routes_require_exact_string_one(self):
        invalid_values = (None, "", "0", "true", "TRUE", " 1", "1 ", "01")
        for backend in ("openai", "chatgpt"):
            for value in invalid_values:
                with self.subTest(backend=backend, value=value):
                    env = self._env(backend)
                    if value is None:
                        env.pop("CLAUDE_CODE_DISABLE_FAST_MODE")
                    else:
                        env["CLAUDE_CODE_DISABLE_FAST_MODE"] = value
                    route = route_detection.build_route_info(env)
                    result = route_detection.probe_env_coherence(route, env)
                    self.assertEqual(result.verdict, Verdict.FAIL)
                    self.assertIn("exact string '1'", result.detail)
                    self.assertIn("gpt_fast.sh", result.detail)
                    self.assertIn("environment_settings.txt", result.detail)
                    self.assertIn("recreate the container", result.detail)
                    self.assertIn("new Claude session", result.detail)

    def test_both_exact_gpt_routes_accept_exact_string_one(self):
        expected_routes = {
            "openai": route_detection.ROUTE_OPENAI_API,
            "chatgpt": route_detection.ROUTE_CHATGPT,
        }
        for backend, expected_route in expected_routes.items():
            with self.subTest(backend=backend):
                env = self._env(backend)
                route = route_detection.build_route_info(env)
                result = route_detection.probe_env_coherence(route, env)
                self.assertEqual(route.detected_route, expected_route)
                self.assertEqual(result.verdict, Verdict.PASS, result.detail)

    def test_route_detection_accepts_clean_routes_and_rejects_incomplete_shim_attempts(self):
        cases = (
            (
                "empty native environment",
                {},
                route_detection.ROUTE_ANTHROPIC,
                Verdict.PASS,
                None,
            ),
            (
                "explicit native model",
                {"ANTHROPIC_MODEL": "claude-opus-4-8"},
                route_detection.ROUTE_ANTHROPIC,
                Verdict.PASS,
                None,
            ),
            (
                "coherent OpenRouter controls",
                {
                    "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
                    "ANTHROPIC_AUTH_TOKEN": "openrouter-test-token",
                    "ANTHROPIC_API_KEY": "",
                },
                route_detection.ROUTE_OPENROUTER,
                Verdict.PASS,
                None,
            ),
            (
                "shim control only",
                {"DAAF_PROVIDER_SHIM": "openai"},
                route_detection.ROUTE_ANTHROPIC,
                Verdict.FAIL,
                "SHIM_BACKEND_MODE",
            ),
            (
                "backend control only",
                {"SHIM_BACKEND_MODE": "openai"},
                route_detection.ROUTE_ANTHROPIC,
                Verdict.FAIL,
                "DAAF_PROVIDER_SHIM",
            ),
            (
                "exact ChatGPT pair",
                {
                    "DAAF_PROVIDER_SHIM": "openai",
                    "SHIM_BACKEND_MODE": "chatgpt",
                },
                route_detection.ROUTE_CHATGPT,
                Verdict.PASS,
                None,
            ),
            (
                "exact OpenAI pair",
                {
                    "DAAF_PROVIDER_SHIM": "openai",
                    "SHIM_BACKEND_MODE": "openai",
                },
                route_detection.ROUTE_OPENAI_API,
                Verdict.PASS,
                None,
            ),
        )
        for label, env, expected_route, expected_verdict, diagnostic in cases:
            with self.subTest(label=label):
                route = route_detection.build_route_info(env)
                result = route_detection.probe_route_detection(route)
                self.assertEqual(route.detected_route, expected_route)
                self.assertEqual(result.verdict, expected_verdict, result.detail)
                if diagnostic is not None:
                    self.assertIn(diagnostic, result.detail)

    def test_gpt_physical_window_maps_astra_flagship_and_rejects_near_misses(self):
        # Parallels the bats "GPT physical-family classifier" battery. gpt-6-astra
        # is a flagship-class 1,050,000-token model: only the exact bare slug, its
        # [1m] hint, or a provider-prefixed terminal segment qualify. '-pro', bare
        # 'gpt-6', and left-boundary text ('xgpt-6-astra') are near misses -> None.
        expected = {
            # gpt-5.x anchors (parallel with the existing families for regression)
            "gpt-5.6-sol": 1050000,
            "gpt-5.6-sol-mini": 400000,
            "gpt-5.6-sol-chat": 128000,
            # gpt-6-astra positives
            "gpt-6-astra": 1050000,
            "gpt-6-astra[1m]": 1050000,
            "openai/gpt-6-astra": 1050000,
            # gpt-6-astra near misses
            "gpt-6-astra-pro": None,
            "gpt-6": None,
            "xgpt-6-astra": None,
        }
        for model_id, want in expected.items():
            with self.subTest(model_id=model_id):
                self.assertEqual(
                    route_detection._gpt_physical_window(model_id), want
                )

    def test_route_control_diagnostics_are_bounded_and_do_not_reflect_values(self):
        marker = "credential-shaped-private-marker-" + "x" * 200
        env = {
            "DAAF_PROVIDER_SHIM": marker,
            "SHIM_BACKEND_MODE": marker,
        }
        route = route_detection.build_route_info(env)
        result = route_detection.probe_route_detection(route)
        reported = (
            result.detail
            + json.dumps(route.to_dict())
            + json.dumps(route_detection.env_fingerprint(env))
            + "".join(
                evidence.output + evidence.note for evidence in result.evidence
            )
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertNotIn(marker, reported)
        self.assertIn("<invalid:unsupported>", reported)
        self.assertLess(len(result.detail), 500)

    def test_api_route_requires_explicit_exact_openai_backend_control(self):
        for value in (None, "", "OpenAI", " OPENAI ", "openai ", "other"):
            with self.subTest(value=value):
                env = self._env("openai")
                if value is None:
                    env.pop("SHIM_BACKEND_MODE")
                else:
                    env["SHIM_BACKEND_MODE"] = value
                route = route_detection.build_route_info(env)
                result = route_detection.probe_route_detection(route)
                self.assertNotEqual(route.detected_route, route_detection.ROUTE_OPENAI_API)
                self.assertEqual(result.verdict, Verdict.FAIL)
                self.assertIn("SHIM_BACKEND_MODE", result.detail)

    def test_clean_native_tier0_has_no_route_detection_failure(self):
        env = {}
        route = route_detection.build_route_info(env)
        stub = route_detection.ProbeResult(
            probe_id="stub",
            name="provider-free stub",
            tier="0",
            verdict=Verdict.SKIP,
        )
        with mock.patch.object(smoke_probes, "probe_cli_available", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_hook_registration", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_statuslines", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_shim_health", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_auth_json", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_workspace_invariants", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_r_locale", return_value=stub):
            results = smoke_probes.run_tier0(route, env, base_dir="/not-used")
        route_results = [result for result in results if result.probe_id == "T0.1"]
        self.assertEqual(len(route_results), 1)
        self.assertEqual(route_results[0].verdict, Verdict.PASS, route_results[0].detail)

    def test_non_gpt_route_behavior_is_unchanged_by_native_disable_absence(self):
        cases = (
            (
                route_detection.ROUTE_ANTHROPIC,
                {"ANTHROPIC_MODEL": "claude-opus-4-8"},
            ),
            (
                route_detection.ROUTE_OPENROUTER,
                {
                    "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
                    "ANTHROPIC_AUTH_TOKEN": "openrouter-token",
                    "ANTHROPIC_API_KEY": "",
                },
            ),
        )
        for expected_route, env in cases:
            with self.subTest(expected_route=expected_route):
                route = route_detection.build_route_info(env)
                result = route_detection.probe_env_coherence(route, env)
                self.assertEqual(route.detected_route, expected_route)
                self.assertEqual(result.verdict, Verdict.PASS, result.detail)


class ShimHealthProbeTests(unittest.TestCase):
    def _payload(self, **overrides):
        backend = overrides.get("backend_mode", "openai")
        tier = "priority"
        payload = {
            "service": "daaf-anthropic-openai-shim",
            "status": "ok",
            "backend_mode": backend,
            "version": "1.3.9",
            "sanitize_tools": True,
            "codex_home_present": True,
            "gpt_service_tier": {
                "backend_mode": backend,
                "requested_tier_vocabulary": tier,
                "policy": {
                    "status": "ok",
                    "backend_mode": backend,
                    "enabled": False,
                    "effective": False,
                },
                "native_fast_disabled": True,
                "latest_terminal": None,
            },
        }
        payload.update(overrides)
        return payload

    def _probe(self, route_name, payload):
        route = route_detection.RouteInfo(route_name)
        with mock.patch.object(
            smoke_probes, "_read_local_health", return_value=payload
        ):
            return smoke_probes.probe_shim_health(route)

    def _reported_text(self, result):
        parts = [result.detail]
        for evidence in result.evidence:
            parts.extend((evidence.output or "", evidence.note or ""))
        return "\n".join(parts)

    def test_probe_uses_shared_safe_local_health_reader(self):
        route = route_detection.RouteInfo(route_detection.ROUTE_OPENAI_API)
        payload = self._payload()
        with mock.patch.object(
            smoke_probes, "_read_local_health", return_value=payload
        ) as reader:
            result = smoke_probes.probe_shim_health(route)
        self.assertEqual(result.verdict, Verdict.PASS, result.detail)
        reader.assert_called_once_with(timeout=10)

    def test_exact_service_status_route_mode_and_safe_version_pass(self):
        result = self._probe(
            route_detection.ROUTE_OPENAI_API,
            self._payload(version="1.2.12+build_7-x"),
        )
        self.assertEqual(result.verdict, Verdict.PASS, result.detail)
        self.assertIn("version=1.2.12+build_7-x", result.detail)

    def test_missing_version_fails_with_bounded_marker(self):
        payload = self._payload()
        payload.pop("version")
        result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("version must match", result.detail)
        self.assertIn("version=<invalid>", reported)

    def test_empty_version_fails_with_bounded_marker(self):
        result = self._probe(
            route_detection.ROUTE_OPENAI_API,
            self._payload(version=""),
        )
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("version must match", result.detail)
        self.assertIn("version=<invalid>", reported)

    def test_unsafe_version_fails_without_reflecting_endpoint_text(self):
        unsafe_version = "release/unsafe\nprivate-version-marker"
        result = self._probe(
            route_detection.ROUTE_OPENAI_API,
            self._payload(version=unsafe_version),
        )
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("version must match", result.detail)
        self.assertIn("version=<invalid>", reported)
        self.assertNotIn(unsafe_version, reported)
        self.assertNotIn("private-version-marker", reported)

    def test_overlong_version_fails_without_reflecting_endpoint_text(self):
        overlong_version = "A" * 65
        result = self._probe(
            route_detection.ROUTE_OPENAI_API,
            self._payload(version=overlong_version),
        )
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("version must match", result.detail)
        self.assertIn("version=<invalid>", reported)
        self.assertNotIn(overlong_version, reported)

    def test_nonstring_versions_fail_with_bounded_marker(self):
        for version in (None, 12, True, ["1.2.12"]):
            with self.subTest(version=version):
                result = self._probe(
                    route_detection.ROUTE_OPENAI_API,
                    self._payload(version=version),
                )
                reported = self._reported_text(result)
                self.assertEqual(result.verdict, Verdict.FAIL)
                self.assertIn("version must match", result.detail)
                self.assertIn("version=<invalid>", reported)

    def test_chatgpt_boolean_true_auth_presence_passes(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT,
            self._payload(backend_mode="chatgpt", codex_home_present=True),
        )
        self.assertEqual(result.verdict, Verdict.PASS, result.detail)

    def test_chatgpt_boolean_false_auth_presence_fails(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT,
            self._payload(backend_mode="chatgpt", codex_home_present=False),
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("codex_home_present must be boolean true", result.detail)

    def test_chatgpt_missing_auth_presence_fails(self):
        payload = self._payload(backend_mode="chatgpt")
        payload.pop("codex_home_present")
        result = self._probe(route_detection.ROUTE_CHATGPT, payload)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("codex_home_present must be boolean true", result.detail)

    def test_chatgpt_string_auth_presence_fails_with_bounded_marker(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT,
            self._payload(backend_mode="chatgpt", codex_home_present="true"),
        )
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("codex_home_present must be boolean true", result.detail)
        self.assertIn("codex_home_present=<invalid>", reported)

    def test_chatgpt_truthy_nonboolean_auth_presence_fails(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT,
            self._payload(backend_mode="chatgpt", codex_home_present=1),
        )
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("codex_home_present must be boolean true", result.detail)
        self.assertIn("codex_home_present=<invalid>", reported)

    def test_unrelated_service_degraded_status_and_wrong_mode_fail(self):
        cases = (
            self._payload(service="unrelated-service"),
            self._payload(status="degraded"),
            self._payload(backend_mode="chatgpt"),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
                self.assertEqual(result.verdict, Verdict.FAIL)

    def test_nonobject_and_malformed_health_json_fail_cleanly(self):
        for payload in (["not", "an", "object"], b"{not-json"):
            with self.subTest(payload=payload):
                result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
                self.assertEqual(result.verdict, Verdict.FAIL)
                self.assertIn("invalid", result.detail)

    def test_both_lane_vocabularies_and_valid_off_on_policies_pass(self):
        lanes = (
            (route_detection.ROUTE_OPENAI_API, "openai", "priority"),
            (route_detection.ROUTE_CHATGPT, "chatgpt", "priority"),
        )
        for route_name, backend, tier in lanes:
            for enabled in (False, True):
                with self.subTest(backend=backend, enabled=enabled):
                    payload = self._payload(backend_mode=backend)
                    payload["gpt_service_tier"]["policy"].update(
                        enabled=enabled, effective=enabled
                    )
                    result = self._probe(route_name, payload)
                    self.assertEqual(result.verdict, Verdict.PASS, result.detail)
                    self.assertIn(f"requested_policy={'ON' if enabled else 'OFF'}", result.detail)
                    self.assertEqual(
                        payload["gpt_service_tier"]["requested_tier_vocabulary"], tier
                    )
                    self.assertIn("not proof", result.detail)

    def test_legacy_requested_fast_fails_closed_on_both_backends(self):
        lanes = (
            (route_detection.ROUTE_OPENAI_API, "openai"),
            (route_detection.ROUTE_CHATGPT, "chatgpt"),
        )
        for route_name, backend in lanes:
            with self.subTest(backend=backend):
                payload = self._payload(backend_mode=backend)
                payload["gpt_service_tier"]["requested_tier_vocabulary"] = "fast"
                payload["gpt_service_tier"]["latest_terminal"] = {
                    "model": "gpt-5.6-sol",
                    "requested_service_tier": "fast",
                    "requested_source": "shim_global",
                    "served_service_tier": "default",
                    "completed_at": "2026-07-25T20:00:00Z",
                }
                result = self._probe(route_name, payload)
                self.assertEqual(result.verdict, Verdict.FAIL)
                self.assertIn("must equal 'priority'", result.detail)

    def test_non_ok_policy_statuses_are_valid_fail_safe_off_not_on_claims(self):
        for status in ("missing", "invalid", "unreadable", "unsafe"):
            with self.subTest(status=status):
                payload = self._payload()
                payload["gpt_service_tier"]["policy"] = {
                    "status": status,
                    "backend_mode": None,
                    "enabled": False,
                    "effective": False,
                }
                result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
                self.assertEqual(result.verdict, Verdict.PASS, result.detail)
                self.assertIn("requested_policy=OFF", result.detail)
                self.assertIn(f"status={status}", result.detail)
                self.assertNotIn("requested_policy=ON", self._reported_text(result))

    def test_service_tier_block_and_policy_reject_missing_extra_and_incoherence(self):
        cases = []
        missing_block_key = self._payload()
        missing_block_key["gpt_service_tier"].pop("native_fast_disabled")
        cases.append(missing_block_key)
        extra_block_key = self._payload()
        extra_block_key["gpt_service_tier"]["path"] = "/sensitive"
        cases.append(extra_block_key)
        wrong_vocabulary = self._payload()
        wrong_vocabulary["gpt_service_tier"]["requested_tier_vocabulary"] = "fast"
        cases.append(wrong_vocabulary)
        nonboolean_native = self._payload()
        nonboolean_native["gpt_service_tier"]["native_fast_disabled"] = 1
        cases.append(nonboolean_native)
        native_not_disabled = self._payload()
        native_not_disabled["gpt_service_tier"]["native_fast_disabled"] = False
        cases.append(native_not_disabled)
        extra_policy_key = self._payload()
        extra_policy_key["gpt_service_tier"]["policy"]["extra"] = False
        cases.append(extra_policy_key)
        incoherent_on = self._payload()
        incoherent_on["gpt_service_tier"]["policy"].update(
            enabled=True, effective=False
        )
        cases.append(incoherent_on)
        corrupt_claims_on = self._payload()
        corrupt_claims_on["gpt_service_tier"]["policy"] = {
            "status": "invalid",
            "backend_mode": "openai",
            "enabled": True,
            "effective": True,
        }
        cases.append(corrupt_claims_on)
        unhashable_policy_values = self._payload()
        unhashable_policy_values["gpt_service_tier"]["policy"].update(
            status=["ok"], backend_mode={"lane": "openai"}
        )
        cases.append(unhashable_policy_values)
        for payload in cases:
            with self.subTest(payload=payload["gpt_service_tier"]):
                result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
                self.assertEqual(result.verdict, Verdict.FAIL)

    def test_valid_latest_terminal_passes_for_both_lanes_and_separates_requested_from_served(self):
        lanes = (
            (route_detection.ROUTE_OPENAI_API, "openai", "priority"),
            (route_detection.ROUTE_CHATGPT, "chatgpt", "priority"),
        )
        for route_name, backend, tier in lanes:
            with self.subTest(backend=backend):
                payload = self._payload(backend_mode=backend)
                payload["gpt_service_tier"]["policy"].update(
                    enabled=True, effective=True
                )
                payload["gpt_service_tier"]["latest_terminal"] = {
                    "model": "openai/gpt-5.6-sol",
                    "requested_service_tier": tier,
                    "requested_source": "shim_global",
                    "served_service_tier": "default",
                    "completed_at": "2026-07-25T20:00:00Z",
                }
                result = self._probe(route_name, payload)
                self.assertEqual(result.verdict, Verdict.PASS, result.detail)
                self.assertIn("requested_policy=ON", result.detail)
                self.assertIn("latest terminal served tier=default", result.detail)
                self.assertIn("not proof", result.detail)

    def test_latest_terminal_rejects_extra_or_malformed_canonical_fields(self):
        valid = {
            "model": "gpt-5.6-sol",
            "requested_service_tier": "priority",
            "requested_source": "anthropic",
            "served_service_tier": "priority",
            "completed_at": "2026-07-25T20:00:00Z",
        }
        variants = []
        extra = dict(valid, path="/sensitive")
        variants.append(extra)
        for key, value in (
            ("model", "gpt bad\nmodel"),
            ("model", "https://private.example.invalid/model"),
            ("requested_service_tier", "fast"),
            ("requested_service_tier", ["priority"]),
            ("requested_source", "NONE"),
            ("requested_source", ["none"]),
            ("served_service_tier", "Priority"),
            ("served_service_tier", {"tier": "priority"}),
            ("completed_at", "2026-02-30T20:00:00Z"),
        ):
            malformed = dict(valid)
            malformed[key] = value
            variants.append(malformed)
        incoherent = dict(valid)
        incoherent["requested_service_tier"] = None
        variants.append(incoherent)
        for latest in variants:
            with self.subTest(latest=latest):
                payload = self._payload()
                payload["gpt_service_tier"]["latest_terminal"] = latest
                result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
                self.assertEqual(result.verdict, Verdict.FAIL)

    def test_health_evidence_is_bounded_projection_not_broad_health_document(self):
        payload = self._payload(
            backend="https://private.example.invalid/v1",
            auth={"token": "must-not-appear"},
            unrelated={"path": "/private/path", "content": "arbitrary"},
        )
        result = self._probe(route_detection.ROUTE_OPENAI_API, payload)
        reported = self._reported_text(result)
        self.assertEqual(result.verdict, Verdict.PASS, result.detail)
        for forbidden in (
            "private.example.invalid", "must-not-appear", "/private/path", "arbitrary"
        ):
            self.assertNotIn(forbidden, reported)

    def test_duplicate_health_keys_fail_before_schema_validation(self):
        payload = json.dumps(self._payload(), separators=(",", ":")).encode("utf-8")
        duplicate = payload.replace(
            b'{"service":', b'{"service":"duplicate","service":', 1
        )
        route = route_detection.RouteInfo(route_detection.ROUTE_OPENAI_API)
        with mock.patch.object(
            smoke_probes,
            "_read_local_health",
            side_effect=smoke_probes._DuplicateHealthKeyError("duplicate health JSON key"),
        ):
            result = smoke_probes.probe_shim_health(route)
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("duplicate health JSON key", result.detail)


class AuthJsonProbeTests(unittest.TestCase):
    """T0.9 (probe_auth_json): the shim /health `auth` block is authoritative for
    chatgpt-route auth validity (v1.3.0 / A1-R6b). FAIL on
    expired|absent|unreadable, WARN on expiring, PASS on valid, route-appropriate
    SKIP off shim routes."""

    def setUp(self):
        # Supplementary filesystem evidence target (presence/readability only,
        # never blocking on its own) — a real scratch dir keeps os.access() honest
        # without requiring an actual auth.json to exist.
        self.codex_home = _scratch_dir("codex_home")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.codex_home, ignore_errors=True)

    def _route(self, route_name):
        return route_detection.RouteInfo(route_name)

    def _env(self):
        return {"CODEX_HOME": str(self.codex_home)}

    def _health(self, **auth_overrides):
        auth = {"state": "valid", "days_left": 30}
        auth.update(auth_overrides)
        return {"auth": auth}

    def _probe(self, route_name, env, payload):
        route = self._route(route_name)
        with mock.patch.object(
            smoke_probes, "_read_local_health", return_value=payload
        ):
            return smoke_probes.probe_auth_json(route, env)

    def test_auth_probe_uses_shared_safe_local_health_reader(self):
        route = self._route(route_detection.ROUTE_CHATGPT)
        payload = self._health(state="valid", days_left=45)
        with mock.patch.object(
            smoke_probes, "_read_local_health", return_value=payload
        ) as reader:
            result = smoke_probes.probe_auth_json(route, self._env())
        self.assertEqual(result.verdict, Verdict.PASS, result.detail)
        reader.assert_called_once_with(timeout=10)

    def test_non_chatgpt_route_skips_without_hitting_health(self):
        # SKIP fires on route alone; env/health are never consulted.
        result = smoke_probes.probe_auth_json(
            self._route(route_detection.ROUTE_OPENAI_API), {}
        )
        self.assertEqual(result.verdict, Verdict.SKIP)
        self.assertIn("Not the chatgpt-subscription route", result.detail)

    def test_missing_codex_home_fails_before_any_health_call(self):
        result = smoke_probes.probe_auth_json(
            self._route(route_detection.ROUTE_CHATGPT), {}
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("CODEX_HOME", result.detail)

    def test_valid_state_passes(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state="valid", days_left=45),
        )
        self.assertEqual(result.verdict, Verdict.PASS, result.detail)
        self.assertIn("days_left=45", result.detail)

    def test_expiring_state_warns(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state="expiring", days_left=2),
        )
        self.assertEqual(result.verdict, Verdict.WARN)
        self.assertIn("expires soon", result.detail)
        self.assertIn("days_left=2", result.detail)

    def test_expired_state_fails(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state="expired", days_left=None),
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("auth is dead", result.detail)
        self.assertIn("state=expired", result.detail)

    def test_absent_state_fails(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state="absent", days_left=None),
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("auth is dead", result.detail)
        self.assertIn("state=absent", result.detail)

    def test_unreadable_state_fails(self):
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state="unreadable", days_left=None),
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("auth is dead", result.detail)
        self.assertIn("state=unreadable", result.detail)

    def test_missing_auth_block_fails_cleanly(self):
        # Pre-v1.3.0 shim / broken build: no "auth" key at all in /health.
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            {"service": "daaf-anthropic-openai-shim", "status": "ok"},
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("no auth block", result.detail)

    def test_auth_block_wrong_type_fails_cleanly(self):
        # Malformed shape: "auth" present but not an object.
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            {"auth": "not-an-object"},
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("no auth block", result.detail)

    def test_unrecognized_state_value_fails_without_crashing(self):
        # Garbage state string outside the known vocabulary must not crash the
        # probe and must be bounded (never reflected verbatim) in the detail.
        garbage_state = "totally-bogus-state"
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state=garbage_state, days_left=None),
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("unexpected auth state", result.detail)
        self.assertIn("state=<invalid>", result.detail)
        self.assertNotIn(garbage_state, result.detail)

    def test_health_reported_na_state_on_chatgpt_route_fails(self):
        # "n/a" is a KNOWN state string, but is unexpected specifically on the
        # chatgpt route (it's the non-shim-route marker) — must still FAIL, not
        # crash, and the known-but-wrong-here value is reflected verbatim.
        result = self._probe(
            route_detection.ROUTE_CHATGPT, self._env(),
            self._health(state="n/a", days_left=None),
        )
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("unexpected auth state", result.detail)
        self.assertIn("state=n/a", result.detail)

    def test_health_endpoint_unreachable_fails(self):
        route = self._route(route_detection.ROUTE_CHATGPT)
        with mock.patch.object(
            smoke_probes, "_read_local_health", side_effect=URLError("refused")
        ):
            result = smoke_probes.probe_auth_json(route, self._env())
        self.assertEqual(result.verdict, Verdict.FAIL)
        self.assertIn("cannot assess auth", result.detail)


class TierDEnvSanitizationTests(unittest.TestCase):
    def test_removes_exactly_the_two_contaminants_and_preserves_the_rest(self):
        with mock.patch.dict(os.environ, {
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000",
            "DAAF_BRANCH": "daaf_dev_r2",
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "SMOKE_UNRELATED": "keepme",
        }, clear=False):
            env, removed = smoke_probes.tier_d_sanitized_env()
        self.assertNotIn("CLAUDE_CODE_MAX_CONTEXT_TOKENS", env)
        self.assertNotIn("DAAF_BRANCH", env)
        self.assertEqual(sorted(removed), ["CLAUDE_CODE_MAX_CONTEXT_TOKENS", "DAAF_BRANCH"])
        self.assertEqual(env.get("SMOKE_UNRELATED"), "keepme")
        self.assertIn("PATH", env)  # toolchain reachability preserved

    def test_does_not_mutate_os_environ(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1050000"}, clear=False):
            smoke_probes.tier_d_sanitized_env()
            # The real process env is untouched; the helper copies first.
            self.assertEqual(os.environ.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS"), "1050000")

    def test_reports_no_contaminants_when_absent(self):
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("CLAUDE_CODE_MAX_CONTEXT_TOKENS", "DAAF_BRANCH")}
        with mock.patch.dict(os.environ, clean, clear=True):
            env, removed = smoke_probes.tier_d_sanitized_env()
        self.assertEqual(removed, [])


class BatteryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.ev = _scratch_dir("td_evidence")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.ev, ignore_errors=True)

    def test_pass_evidence_is_concise_final_eight_lines(self):
        # 30 numbered lines, exit 0 -> only the final 8 are retained, no artifact.
        script = "import sys\n" + "".join(f"print({i})\n" for i in range(30))
        r = smoke_probes._run_battery_cmd(
            "TDX.pass", "concise pass", ["python3", "-c", script], timeout=30,
            evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.PASS)
        out = r.evidence[0].output
        self.assertLessEqual(len(out.splitlines()), 8)
        self.assertIn("29", out)         # final line kept
        self.assertNotIn("0\n", out + "\n")  # early lines dropped from concise view
        # No failure artifact on PASS.
        self.assertFalse((self.ev / "TDX.pass.log").exists())

    def test_fail_evidence_keeps_head_and_tail_and_writes_full_artifact(self):
        # Distinctive early + late markers around a long middle, then exit 1.
        lines = ["print('EARLY_FAILURE_MARKER')"]
        lines += [f"print('mid-{i}')" for i in range(80)]
        lines += ["print('FINAL_SUMMARY_MARKER')", "import sys; sys.exit(1)"]
        script = "\n".join(lines) + "\n"
        r = smoke_probes._run_battery_cmd(
            "TDX.fail", "long fail", ["python3", "-c", script], timeout=30,
            evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.FAIL)
        excerpt = r.evidence[0].output
        self.assertIn("EARLY_FAILURE_MARKER", excerpt)     # early failure name visible
        self.assertIn("FINAL_SUMMARY_MARKER", excerpt)     # final summary visible
        self.assertIn("omitted", excerpt)                  # middle elided with count
        # Complete scrubbed output persisted and referenced.
        artifact = self.ev / "TDX.fail.log"
        self.assertTrue(artifact.exists())
        full = artifact.read_text()
        self.assertIn("EARLY_FAILURE_MARKER", full)
        self.assertIn("mid-40", full)                      # the elided middle is in the full log
        self.assertIn("FINAL_SUMMARY_MARKER", full)
        self.assertTrue(any(str(artifact) in (e.note or "") for e in r.evidence))

    def test_timeout_preserves_flushed_output_when_available(self):
        # Flush a marker, then block past the timeout -> partial output captured.
        script = ("import sys, time\n"
                  "sys.stdout.write('PRE_TIMEOUT_MARKER\\n'); sys.stdout.flush()\n"
                  "time.sleep(30)\n")
        r = smoke_probes._run_battery_cmd(
            "TDX.timeout", "timeout probe", ["python3", "-u", "-c", script], timeout=2,
            evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("timed out", r.detail)
        artifact = self.ev / "TDX.timeout.log"
        self.assertTrue(artifact.exists())
        self.assertIn("PRE_TIMEOUT_MARKER", artifact.read_text())

    def test_secret_values_are_scrubbed_from_evidence(self):
        # The threat channel is CAPTURED OUTPUT: a battery echoing an env secret.
        # (Tier D commands are fixed invocations with no secrets in argv.) The
        # child reads the secret from the env and prints it, so it appears in
        # stdout and must be scrubbed from both the excerpt and the full artifact.
        secret = "supersecretvalue123456"
        script = ("import os, sys\n"
                  "sys.stdout.write('leak=' + os.environ['SMOKE_TEST_API_KEY'] + '\\n')\n"
                  "sys.exit(1)\n")
        with mock.patch.dict(os.environ, {"SMOKE_TEST_API_KEY": secret}, clear=False):
            r = smoke_probes._run_battery_cmd(
                "TDX.scrub", "scrub", ["python3", "-c", script], timeout=30,
                evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertNotIn(secret, r.evidence[0].output)
        self.assertNotIn(secret, (self.ev / "TDX.scrub.log").read_text())

    def test_cwd_routes_output_into_the_evidence_directory(self):
        # Mirrors how TD.2 sets cwd=evidence_dir so Pester's testResults.xml lands
        # in the report instead of the repo root.
        target = self.ev / "wrote_in_cwd.txt"
        script = "open('wrote_in_cwd.txt', 'w').write('x')\nprint('ok')\n"
        r = smoke_probes._run_battery_cmd(
            "TDX.cwd", "cwd routing", ["python3", "-c", script], timeout=30,
            cwd=str(self.ev), evidence_dir=self.ev)
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertTrue(target.exists())

    def test_missing_cwd_is_fail_not_skip(self):
        # A nonexistent working directory is a BROKEN HARNESS (e.g. a misdetected
        # BASE_DIR), not a missing tool. It must FAIL loudly, never SKIP:
        # SKIP-on-missing-cwd is fail-open and would silently skip the entire Tier D
        # battery, with false negatives accruing false authority. Regression: on CI
        # runners /daaf does not exist, so the old cwd=BASE_DIR default of "/daaf"
        # raised FileNotFoundError inside subprocess.run and was misclassified as
        # SKIP ("tool unavailable") — the exact 4-test CI failure this test guards.
        missing = self.ev / f"nonexistent_{uuid.uuid4().hex[:8]}"
        self.assertFalse(missing.exists())
        r = smoke_probes._run_battery_cmd(
            "TDX.missingcwd", "missing cwd", ["python3", "-c", "print('ran')"],
            timeout=30, cwd=str(missing), evidence_dir=self.ev)
        # New semantics: FAIL, explicitly NOT SKIP.
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertNotEqual(r.verdict, Verdict.SKIP)
        # The detail/evidence must identify the WORKING DIRECTORY as the problem
        # (not a missing tool) and name the offending path.
        haystack = (r.detail + " " + " ".join(
            (e.note or "") + " " + (e.output or "") for e in r.evidence)).lower()
        self.assertIn("working directory", haystack)
        self.assertIn(str(missing).lower(), haystack)
        # The command itself would PASS with a valid cwd (see the test above), so
        # the FAIL is due to the cwd alone; no tool-unavailable SKIP text leaked in.
        self.assertNotIn("unavailable", r.detail.lower())


class T22FreshnessTests(unittest.TestCase):
    """The pure T2.2 evaluator: fresh banner + '# Exit code: 0' + this run's
    nonce after the banner is the ONLY PASS shape."""

    NONCE = "daaf-exec-abc123def456"

    def _log(self, exit_code, tail_body):
        return (
            f"import x\nprint('{self.NONCE}')\n"          # source line (nonce present by construction)
            "\n\n# =====\n# EXECUTION LOG\n# =====\n#\n"
            "# Executed: 2026-07-17\n"
            f"# Exit code: {exit_code}\n#\n"
            "# --- STDOUT ---\n"
            f"{tail_body}\n"
        )

    def test_fresh_success_with_nonce_after_banner_passes(self):
        body = self._log(0, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertTrue(all(facts.values()))

    def test_missing_script_fails(self):
        verdict, _ = smoke_probes._evaluate_t22(False, None, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)

    def test_no_banner_source_only_nonce_fails(self):
        # Script written (nonce in source) but never executed: no banner.
        body = f"import x\nprint('{self.NONCE}')\n"
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["banner"])

    def test_stale_banner_with_different_nonce_fails(self):
        # A leftover banner from a prior run carries a DIFFERENT run's nonce.
        body = self._log(0, "# daaf-exec-STALERUNyyyy")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["nonce_after_banner"])

    def test_banner_and_nonce_but_nonzero_exit_fails(self):
        body = self._log(1, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["exit_success"])

    def test_exit_code_100_does_not_match_success(self):
        # Anchored regex: '# Exit code: 100' must NOT satisfy the exit-0 check.
        body = self._log(100, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["exit_success"])


class Tier2SandboxCleanupTests(unittest.TestCase):
    """run_tier2 end-to-end with the live executor mocked out: no provider call,
    but the real per-run UUID sandbox creation + guaranteed cleanup path runs."""

    def setUp(self):
        self.sandbox = _scratch_dir("t2_sandbox")
        # A pre-existing sibling that must SURVIVE (proves cleanup is scoped to the
        # run-owned dir only, never a recursive wipe of _sandbox/).
        self.sibling = self.sandbox / "historical_sibling.txt"
        self.sibling.write_text("keep me\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_cleanup_removes_only_the_run_dir_and_spares_siblings(self):
        fake_meta = {"session_id": "test-sid-00000000"}
        fake_res = types.SimpleNamespace(response_text="", model_id="")

        with mock.patch.object(smoke_probes, "_sandbox_dir", return_value=self.sandbox), \
             mock.patch.object(smoke_probes, "execute_smoke_run",
                               return_value=(fake_res, fake_meta)), \
             mock.patch.object(smoke_probes, "find_transcript", return_value=None), \
             mock.patch.object(smoke_probes, "find_subagent_transcripts", return_value=[]):
            results = smoke_probes.run_tier2("", {}, timeout=5)

        # Six probes still produced (structure intact), no exception.
        self.assertEqual(len(results), 6)
        # The sibling survived; no stray run_ directory remains.
        self.assertTrue(self.sibling.exists())
        leftover = [p for p in self.sandbox.glob("run_*") if p.is_dir()]
        self.assertEqual(leftover, [], f"run dir not cleaned: {leftover}")


class ParseTiersTests(unittest.TestCase):
    def test_valid_spec_orders_and_dedupes(self):
        self.assertEqual(run_deploy_smoke.parse_tiers("0,1,2,D"), ["0", "1", "2", "D"])
        self.assertEqual(run_deploy_smoke.parse_tiers("d"), ["D"])
        self.assertEqual(run_deploy_smoke.parse_tiers("0,0,1"), ["0", "1"])

    def test_empty_spec_yields_empty_list(self):
        self.assertEqual(run_deploy_smoke.parse_tiers(""), [])
        self.assertEqual(run_deploy_smoke.parse_tiers(",, ,"), [])

    def test_invalid_token_is_a_hard_error_naming_token_and_valid_set(self):
        with self.assertRaises(ValueError) as ctx:
            run_deploy_smoke.parse_tiers("0,X")
        msg = str(ctx.exception)
        self.assertIn("X", msg)
        for tok in ("0", "1", "2", "D"):
            self.assertIn(tok, msg)

    def test_invalid_token_not_silently_dropped_when_valid_present(self):
        with self.assertRaises(ValueError):
            run_deploy_smoke.parse_tiers("D,3")


class LintScopingTests(unittest.TestCase):
    """The PowerShell preamble lint must ignore research/worktree/scratch residue
    while still failing a noncompliant scripts/host/*.ps1 (including untracked)."""

    LINT = _REPO_ROOT / "tests" / "lint" / "check-daaf-conventions.sh"

    def setUp(self):
        self.repo = _scratch_dir("lint_fakerepo")
        # Ignored residue: noncompliant PS everywhere the recursive scan used to
        # reach. None of these may produce a lint failure after the scoping fix.
        for rel in ("research/proj/scratch/a.ps1",
                    ".claude/worktrees/wt1/scripts/host/b.ps1",
                    "scripts/scratch/probe/c.ps1"):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("Write-Output 'no error action preference here'\n")
        # A CLAUDE.md so the freshness check (section 7) has a real path to grep;
        # without any freshness target present, GNU `grep -r` with an empty path
        # list falls back to scanning the process CWD — an artifact of running the
        # lint against a minimal synthetic root, not the scoping under test.
        (self.repo / "CLAUDE.md").write_text("# fake\nno bad freshness key here\n")
        # A compliant host script (DAAF_NESTED + progress + EAP) so the ONLY
        # possible failure isolates the preamble rule.
        host = self.repo / "scripts" / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "good.ps1").write_text(
            "# host script [1/1] DAAF_NESTED\n"
            "$ErrorActionPreference = 'Stop'\n"
            "Write-Output 'ok'\n")
        self.bad = host / "bad.ps1"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo, ignore_errors=True)

    def _run_lint(self):
        return subprocess.run(["bash", str(self.LINT), str(self.repo)],
                              capture_output=True, text=True, timeout=60)

    def test_ignored_residue_does_not_fail_lint(self):
        proc = self._run_lint()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for token in ("research/proj", ".claude/worktrees", "scripts/scratch/probe"):
            self.assertNotIn(token, proc.stdout)

    def test_noncompliant_host_ps1_still_fails(self):
        # Untracked host script missing $ErrorActionPreference (but DAAF_NESTED +
        # progress present so only the preamble rule fires).
        self.bad.write_text(
            "# host script [1/1] DAAF_NESTED\n"
            "Write-Output 'missing error action preference'\n")
        proc = self._run_lint()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("scripts/host/bad.ps1", proc.stdout)
        self.assertIn("ErrorActionPreference", proc.stdout)


class ProjectSlugTests(unittest.TestCase):
    """smoke_probes._project_slug encodes a working-directory path the way Claude
    Code names ~/.claude/projects/<slug>, derived from BASE_DIR rather than the
    old hardcoded '-daaf'."""

    def test_daaf_root_yields_observed_in_container_slug(self):
        # Ground truth: `ls ~/.claude/projects/` in-container shows exactly '-daaf'
        # for the working directory /daaf. This invariant preserves live behavior.
        self.assertEqual(smoke_probes._project_slug("/daaf"), "-daaf")

    def test_ci_checkout_path_encodes_each_separator(self):
        # A GitHub Actions checkout path under the same transformation.
        self.assertEqual(
            smoke_probes._project_slug("/home/runner/work/daaf/daaf"),
            "-home-runner-work-daaf-daaf",
        )

    def test_module_constant_matches_helper_applied_to_base_dir(self):
        # The cached module constant used by the transcript helpers is exactly the
        # helper applied to BASE_DIR (no drift between the two).
        self.assertEqual(
            smoke_probes._PROJECT_SLUG,
            smoke_probes._project_slug(smoke_probes.BASE_DIR),
        )
        # On a live in-container deployment (BASE_DIR == /daaf), also pin the
        # observed slug directly: the equality above is near-tautological (the
        # module computes the constant from the helper), so this locks the live
        # invariant against a future re-hardcoded or divergent constant.
        if smoke_probes.BASE_DIR == "/daaf":
            self.assertEqual(smoke_probes._PROJECT_SLUG, "-daaf")


if __name__ == "__main__":
    unittest.main()
