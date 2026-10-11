"""Provider-free regression tests for the DAAF deployment smoke harness.

Standard-library unittest + unittest.mock ONLY — no third-party test deps, no
network, no live provider calls. Synthetic health fixtures are contract evidence
only; they do not claim provider acceptance of any requested tier. Every fixture
lives under scripts/scratch/ (NEVER /tmp) and is removed in tearDown.

This module is wired into Tier D as TD.0 (run BEFORE the broader batteries) so an
official Tier D run first validates its own harness: environment sanitization,
Tier D failure-evidence capture, Pester/battery output routing, per-run Tier 2
sandbox cleanup, the stricter T2.2 freshness/success semantics, the Tier 1/2
live-run verdict evaluators (the live-run health gate with recovered-error and
--max-turns WARNs, T1.1/T1.4/T1.5/T1.6/T1.7, T2.3-T2.6 including T2.6 retry
counting and deferred tool names), malformed (non-dict) tool_use inputs, the
T0.7 statusline probe's report-local cache dir (no /tmp writes), and the T0.12
local-settings-shadowing and T0.13 synced-surface probes.

Run directly:
  python3 -m unittest discover -s /daaf/tests/python -p 'test_deploy_smoke.py'
"""

import json
import os
import re
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


class MainModelLaunchGateTests(unittest.TestCase):
    def test_per_profile_gating_with_or_without_tier_zero(self):
        from contextlib import ExitStack
        import io
        for tiers in ('1,2', '0,1,2'):
            with self.subTest(tiers=tiers), ExitStack() as stack:
                stack.enter_context(mock.patch.dict(os.environ, {'ANTHROPIC_MODEL': 'claude-opus-4-8'}, clear=True))
                stack.enter_context(mock.patch.object(sys, 'argv', ['smoke', '--tiers', tiers, '--yes']))
                stack.enter_context(mock.patch.object(sys, 'stdout', io.StringIO()))
                stack.enter_context(mock.patch.object(sys, 'stderr', io.StringIO()))
                stack.enter_context(mock.patch.object(run_deploy_smoke, 'load_profiles', return_value=[('bad', {}), ('good', {'ANTHROPIC_MODEL': 'gpt-6-astra'})]))
                stack.enter_context(mock.patch.object(smoke_probes, 'run_tier0', return_value=[]))
                def gate(env, base, **kwargs):
                    result = route_detection.ProbeResult('T0.14', 'coherence', kwargs['tier'], profile=kwargs['profile'])
                    result.verdict = Verdict.FAIL if env['ANTHROPIC_MODEL'].startswith('claude') else Verdict.PASS
                    return result
                check = stack.enter_context(mock.patch.object(smoke_probes, 'probe_main_model_coherence', side_effect=gate))
                t1 = stack.enter_context(mock.patch.object(smoke_probes, 'run_tier1', return_value=[]))
                t2 = stack.enter_context(mock.patch.object(smoke_probes, 'run_tier2', return_value=[]))
                stack.enter_context(mock.patch.object(run_deploy_smoke, 'write_reports', return_value=True))
                self.assertEqual(run_deploy_smoke.main(), 1)
                self.assertEqual(check.call_count, 2)
                self.assertEqual(t1.call_count, 1)
                self.assertEqual(t2.call_count, 1)
                self.assertEqual(t1.call_args.args[0], 'good')
                self.assertEqual(t2.call_args.args[0], 'good')
                self.assertEqual(os.environ['ANTHROPIC_MODEL'], 'claude-opus-4-8')

    def test_tier_d_discovers_both_modules(self):
        with mock.patch.object(smoke_probes, '_run_battery_cmd') as run:
            smoke_probes._run_tier_d_unit_tests(5, {}, _SCRATCH)
        self.assertIn('test_deploy_smoke*.py', run.call_args.args[2])


class MainModelProjectionTests(unittest.TestCase):
    def test_unknown_endpoint_is_not_detector_fallback_certification(self):
        for model in ('gpt-6-astra','claude-opus-4-8'):
            for url in ('https://custom.invalid/api','https://openrouter.ai.attacker.invalid/api',
                        'https://api.anthropic.com.attacker.invalid'):
                env = {'ANTHROPIC_MODEL':model,'ANTHROPIC_BASE_URL':url}
                result = route_detection.resolve_main_model(env)
                self.assertEqual(result.compatibility, 'unknown')
                self.assertEqual(result.endpoint_kind, 'unknown')
        self.assertEqual(route_detection.detect_route({'ANTHROPIC_BASE_URL':'https://custom.invalid'}),
                         route_detection.ROUTE_ANTHROPIC)  # old broad detector unchanged
        for url in (None, ''):
            result = route_detection.resolve_main_model({'DAAF_PROVIDER_SHIM':'openai',
                'SHIM_BACKEND_MODE':'chatgpt','ANTHROPIC_BASE_URL':url,'ANTHROPIC_MODEL':'gpt-6-astra'})
            self.assertEqual(result.compatibility, 'unknown')
        for env in ({'ANTHROPIC_MODEL':'claude-opus-4-8'},
                    {'ANTHROPIC_MODEL':'gpt-6-astra','ANTHROPIC_BASE_URL':'https://openrouter.ai/api'}):
            self.assertEqual(route_detection.resolve_main_model(env).compatibility, 'compatible')

    def test_ordinary_real_resolver_keeps_mismatch_with_benchmark_profile(self):
        import io
        import shutil
        from contextlib import ExitStack
        root = _scratch_dir('real_gate')
        self.addCleanup(shutil.rmtree, root)
        (root/'user').mkdir()
        for tiers in ('1,2','0,1,2'):
            for flag_source in ('ambient','profile'):
                env = {'DAAF_DEV':'1','CLAUDE_CONFIG_DIR':str(root/'user'),
                       'ANTHROPIC_MODEL':'claude-opus-4-8','DAAF_PROVIDER_SHIM':'openai',
                       'SHIM_BACKEND_MODE':'chatgpt','ANTHROPIC_BASE_URL':'http://127.0.0.1:4141'}
                overlay = {'DAAF_BENCHMARK_RUN':'1'} if flag_source == 'profile' else {}
                if flag_source == 'ambient':
                    env['DAAF_BENCHMARK_RUN'] = '1'
                with self.subTest(tiers=tiers, source=flag_source), ExitStack() as stack:
                    stack.enter_context(mock.patch.dict(os.environ, env, clear=True))
                    stack.enter_context(mock.patch.object(run_deploy_smoke,'BASE_DIR',str(root)))
                    stack.enter_context(mock.patch.object(sys,'argv',['smoke','--tiers',tiers,'--yes']))
                    stack.enter_context(mock.patch.object(sys,'stdout',io.StringIO()))
                    stack.enter_context(mock.patch.object(sys,'stderr',io.StringIO()))
                    stack.enter_context(mock.patch.object(run_deploy_smoke,'load_profiles',return_value=[('bad',overlay)]))
                    stack.enter_context(mock.patch.object(smoke_probes,'run_tier0',return_value=[]))
                    t1 = stack.enter_context(mock.patch.object(smoke_probes,'run_tier1'))
                    t2 = stack.enter_context(mock.patch.object(smoke_probes,'run_tier2'))
                    writer = stack.enter_context(mock.patch.object(run_deploy_smoke,'write_reports',return_value=True))
                    self.assertEqual(run_deploy_smoke.main(),1)
                    t1.assert_not_called()
                    t2.assert_not_called()
                    self.assertEqual(writer.call_args.args[3][0].verdict,Verdict.FAIL)
                resolution = route_detection.resolve_main_model(dict(env, **overlay))
                self.assertEqual(resolution.compatibility,'incompatible')
                self.assertFalse(resolution.normal_execution_context)

    def test_explicit_claude_is_not_rewritten_by_gpt_alias_or_subagent(self):
        env = {"DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "chatgpt",
               "ANTHROPIC_BASE_URL": "http://127.0.0.1:4141",
               "ANTHROPIC_MODEL": "claude-opus-4-8",
               "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-6-astra",
               "CLAUDE_CODE_SUBAGENT_MODEL": "gpt-6-astra"}
        self.assertEqual(route_detection.classify_model_family(env), ("gpt", True))
        result = route_detection.resolve_main_model(env)
        self.assertEqual((result.family, result.compatibility), ("claude", "incompatible"))
        self.assertNotIn("claude-opus", json.dumps(result.safe_metadata()))
        result = route_detection.resolve_main_model(env, explicit_model="gpt-6-astra")
        self.assertEqual((result.source, result.overridden, result.compatibility),
                         ("invocation", True, "compatible"))

    def test_alias_uses_own_mapping_and_precedence(self):
        env = {"ANTHROPIC_MODEL": "sonnet", "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-6-astra",
               "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6"}
        result = route_detection.resolve_main_model(env, saved_model="gpt-6-astra")
        self.assertEqual(result.resolved_model, "claude-sonnet-4-6")
        self.assertEqual(result.compatibility, "compatible")
        del env["ANTHROPIC_DEFAULT_SONNET_MODEL"]
        self.assertEqual(route_detection.resolve_main_model(env).compatibility, "unknown")
        self.assertEqual(route_detection.resolve_main_model({}, saved_model="claude-opus-4-8").source, "saved_model")
        self.assertEqual(route_detection.resolve_main_model({}).compatibility, "unknown")
        self.assertEqual(route_detection.resolve_main_model(env, uncertainty=("managed_policy_unresolved",)).compatibility, "unknown")

    def test_bounded_settings_projection_and_custom_config(self):
        import shutil
        root = _scratch_dir("main_projection")
        self.addCleanup(shutil.rmtree, root)
        config = root / "user"
        config.mkdir()
        (root / ".claude").mkdir()
        (config / "settings.json").write_text(json.dumps({"model": "claude-opus-4-8"}))
        (root / ".claude/settings.json").write_text(json.dumps({"env": {"ANTHROPIC_MODEL": "gpt-6-astra"}}))
        env = {"CLAUDE_CONFIG_DIR": str(config), "ANTHROPIC_MODEL": "claude-opus-4-8",
               "DAAF_PROVIDER_SHIM": "openai", "SHIM_BACKEND_MODE": "chatgpt",
               "ANTHROPIC_BASE_URL": "http://127.0.0.1:4141"}
        result, states = smoke_probes.collect_main_model(env, str(root))
        self.assertEqual(result.compatibility, "compatible")
        self.assertEqual(result.source, "project_settings_env")
        self.assertEqual(states["local"], "absent")
        local = root / ".claude/settings.local.json"
        local.write_text('{broken')
        result, states = smoke_probes.collect_main_model(env, str(root))
        self.assertEqual(states["local"], "malformed")
        self.assertEqual(result.compatibility, "unknown")
        local.write_text('{"env":{"ANTHROPIC_MODEL":"x","ANTHROPIC_MODEL":"y"}}')
        self.assertEqual(smoke_probes._read_main_settings(local)[1], "malformed")
        local.write_text('x' * (smoke_probes._SETTINGS_LIMIT + 1))
        self.assertEqual(smoke_probes._read_main_settings(local)[1], "oversized")
        with mock.patch.object(smoke_probes.os, "open", side_effect=PermissionError):
            self.assertEqual(smoke_probes._read_main_settings(local)[1], "unreadable")
        local.unlink()
        (config / "managed-settings.json").write_text('{}')
        result, _ = smoke_probes.collect_main_model(env, str(root))
        self.assertEqual(result.compatibility, "unknown")


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

    def test_gpt_physical_window_maps_gpt6_flagships_and_rejects_near_misses(self):
        # Parallels the bats "GPT physical-family classifier" battery. The GPT-6
        # flagships gpt-6-astra, gpt-6-sol and gpt-6-luna, each with an optional
        # '-pro' and then an optional '[1m]', map to 1,050,000. The Sol/Luna and
        # '-pro' members come from the USER POLICY DECISION of 2026-09-29, not
        # validation. Bare 'gpt-6', the retired 'gpt-6-terra', GPT-6 mini/chat, and
        # right- or left-boundary text are near misses and map to None.
        expected = {
            # gpt-5.x anchors (unchanged; regression guard)
            "gpt-5.6-sol": 1050000,
            "gpt-5.6-sol-mini": 400000,
            "gpt-5.6-sol-chat": 128000,
            "gpt-5.6-mini-pro": 400000,
            "gpt-5.6-sol-extra": 1050000,
            "gpt-5": 400000,
            "gpt-5.2": 400000,
            "gpt-5-chat": 128000,
            # gpt-5.x flagship -pro forms (already 1050000 via the gpt-5.x arm)
            "gpt-5.6-sol-pro": 1050000,
            "gpt-5.6-sol-pro[1m]": 1050000,
            "openai/gpt-5.6-terra-pro": 1050000,
            "gpt-5.5-pro": 1050000,
            "gpt-5.4-pro": 1050000,
            # gpt-6-astra positives
            "gpt-6-astra": 1050000,
            "gpt-6-astra[1m]": 1050000,
            "openai/gpt-6-astra": 1050000,
            # 2026-09-29 policy registrations: bare, [1m], provider-prefixed
            "gpt-6-sol": 1050000,
            "gpt-6-sol[1m]": 1050000,
            "openai/gpt-6-sol": 1050000,
            "gpt-6-luna": 1050000,
            "gpt-6-luna[1m]": 1050000,
            "openai/gpt-6-luna": 1050000,
            "gpt-6-astra-pro": 1050000,
            "gpt-6-astra-pro[1m]": 1050000,
            "openai/gpt-6-astra-pro": 1050000,
            "gpt-6-sol-pro": 1050000,
            "gpt-6-sol-pro[1m]": 1050000,
            "openai/gpt-6-sol-pro": 1050000,
            "gpt-6-luna-pro": 1050000,
            "gpt-6-luna-pro[1m]": 1050000,
            "openai/gpt-6-luna-pro": 1050000,
            # documented '#<effort>' env-selector suffix is tolerated
            "gpt-6-astra[1m]#xhigh": 1050000,
            "gpt-6-sol[1m]#medium": 1050000,
            "openai/gpt-6-luna-pro#high": 1050000,
            # near misses
            "gpt-6": None,
            "gpt-6-terra": None,
            "gpt-6-terra[1m]": None,
            "gpt-6-sol-mini": None,
            "gpt-6-sol-chat": None,
            "gpt-6-astra-pro-x": None,
            "gpt-6-sol-pro[1m]x": None,
            "gpt-6-astra[1m]x": None,
            "gpt-6-sol[1m]-pro": None,
            "gpt-6-astrab": None,
            "xgpt-6-astra": None,
            "xgpt-6-sol": None,
            "gpt-6-sol\n": None,
        }
        for model_id, want in expected.items():
            with self.subTest(model_id=model_id):
                self.assertEqual(
                    route_detection._gpt_physical_window(model_id), want
                )

    def test_gpt_flagship_grammar_is_byte_identical_to_runtime_consumers(self):
        # _gpt_physical_window promises to mirror the Bash consumers. Compare the
        # pattern text with each consumer's flagship ERE assignment line (read
        # only, never executed) so a registry edit there cannot drift from here.
        consumers = {
            ".claude/hooks/context-reporter.sh": "GPT_FLAGSHIP_RE",
            ".claude/scripts/subagent-bar.sh": "gpt_flagship_re",
            ".claude/scripts/context-bar.sh": "gpt_flagship_re",
        }
        for rel_path, var in consumers.items():
            with self.subTest(consumer=rel_path):
                text = (_REPO_ROOT / rel_path).read_text(encoding="utf-8")
                found = re.findall(
                    rf"^{var}='([^']*)'$", text, flags=re.MULTILINE
                )
                self.assertEqual(len(found), 1, (rel_path, found))
                self.assertEqual(
                    found[0], route_detection._GPT_FLAGSHIP_RE.pattern
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
             mock.patch.object(smoke_probes, "probe_r_locale", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_local_settings_shadowing", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_synced_surface", return_value=stub):
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
    """The pure T2.2 evaluator: exactly ONE framed banner + '# Exit code: 0' +
    '# Capture: COMPLETE' + the wrapper's frame records + this run's nonce inside
    the captured-STDOUT region is the ONLY PASS shape."""

    NONCE = "daaf-exec-abc123def456"
    # The literal rule line run_with_capture.sh writes above and below the
    # marker ($BANNER: "# " + 77 '='). The evaluator anchors on this full frame,
    # so the fixtures must reproduce it exactly rather than a bare marker line.
    RULE = "# " + "=" * 77
    # A rule an agent can plausibly type into the script SOURCE by hand. The
    # evaluator's 40-'=' floor is what separates it from the wrapper's real rule.
    TOKEN_RULE = "# ="

    def _frame(self, rule=None):
        rule = self.RULE if rule is None else rule
        return f"{rule}\n# EXECUTION LOG\n{rule}\n"

    def _log(self, exit_code, tail_body, capture="COMPLETE", source_prefix="",
             command=True, stdout_header=True):
        # capture=None omits the "# Capture:" record entirely (the pre-2026-09
        # wrapper log shape); any other value is written verbatim.
        # source_prefix injects attacker-controlled SOURCE text ahead of the real
        # appended log (forgery fixtures).
        # command / stdout_header drop one of the wrapper's structural records so
        # the frame_records fact can be exercised in isolation.
        capture_line = f"# Capture: {capture}\n" if capture is not None else ""
        command_line = "# Command: python3 /daaf/x/t22_probe.py\n" if command else ""
        stdout_line = "# --- STDOUT ---\n" if stdout_header else ""
        return (
            f"import x\nprint('{self.NONCE}')\n"          # source line (nonce present by construction)
            f"{source_prefix}"
            f"\n\n{self._frame()}#\n"
            "# Executed: 2026-07-17\n"
            f"{command_line}"
            "# Duration: 0s\n"
            f"# Exit code: {exit_code}\n"
            f"{capture_line}#\n"
            f"{stdout_line}"
            f"{tail_body}\n"
            "#\n"
            "# --- STDERR ---\n"
            "# (captured in STDOUT above via 2>&1)\n"
            "#\n"
            f"{self.RULE}\n"
        )

    def test_fresh_success_with_nonce_in_stdout_passes(self):
        # Happy path: the full wrapper log shape. Every fact true, including the
        # frame skeleton and the nonce landing in the captured-STDOUT region.
        body = self._log(0, f"# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertTrue(all(facts.values()))
        self.assertEqual(facts["banner_count"], 1)
        self.assertTrue(facts["frame_records"])
        self.assertTrue(facts["nonce_in_stdout"])

    def test_capture_complete_with_nul_note_passes(self):
        # The wrapper reports NUL bytes as a parenthesised note on the same
        # line; that is still a COMPLETE capture.
        body = self._log(0, f"# {self.NONCE}", capture="COMPLETE (1 NUL byte(s) dropped)")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertTrue(facts["capture_complete"])

    def test_capture_incomplete_fails(self):
        # Exit 0 + fresh nonce + banner, but the wrapper flagged the archived
        # stdout as possibly truncated: not verified evidence, so FAIL.
        body = self._log(0, f"# {self.NONCE}", capture="INCOMPLETE (tee exit 1)")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["capture_complete"])
        self.assertTrue(facts["exit_success"])
        self.assertTrue(facts["nonce_in_stdout"])

    def test_missing_capture_record_fails(self):
        # A log with no "# Capture:" line at all (older wrapper shape, or a
        # hand-forged banner) carries no evidence the archive is whole.
        body = self._log(0, f"# {self.NONCE}", capture=None)
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["capture_complete"])

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
        self.assertFalse(facts["nonce_in_stdout"])

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

    def test_fresh_success_reports_single_banner(self):
        body = self._log(0, f"# {self.NONCE}")
        _, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(facts["banner_count"], 1)

    def test_source_forged_bare_marker_without_frame_fails(self):
        # A coding agent writes the marker text plus fake records and the nonce
        # into the script SOURCE and never runs it. A bare "# EXECUTION LOG"
        # line carries no frame, so it is not a banner: banner_count == 0.
        body = (
            f"import x\nprint('{self.NONCE}')\n"
            "# EXECUTION LOG\n"
            "# Exit code: 0\n"
            "# Capture: COMPLETE\n"
            f"# {self.NONCE}\n"
        )
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertEqual(facts["banner_count"], 0)
        self.assertFalse(facts["banner"])

    def test_forged_frame_ahead_of_real_failing_log_fails(self):
        # Worst case: a full FORGED frame in the source (with fake exit 0 /
        # COMPLETE / nonce) sits ahead of the REAL appended log, which records
        # exit 1 and INCOMPLETE. Two frames => ambiguous evidence => FAIL.
        forged = (
            f"\n{self._frame()}"
            "# Exit code: 0\n"
            "# Capture: COMPLETE\n"
            f"# {self.NONCE}\n"
        )
        body = self._log(1, f"# {self.NONCE}", capture="INCOMPLETE (tee exit 1)",
                         source_prefix=forged)
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertEqual(facts["banner_count"], 2)

    def test_neutralized_marker_in_captured_stdout_still_passes(self):
        # The wrapper rewrites a captured output line reading exactly
        # "EXECUTION LOG" to "#  EXECUTION LOG" (two spaces). That neutralized
        # form must not count as a second banner.
        body = self._log(0, f"#  EXECUTION LOG\n# {self.NONCE}")
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertEqual(facts["banner_count"], 1)

    def test_source_forged_token_rule_frame_never_run_fails(self):
        # The regression this suite exists for. An agent types a MINIMAL "# ="
        # rule around the marker, plus the whole record skeleton and the nonce,
        # into the script SOURCE and never runs it. The wrapper then refuses to
        # run the script at all (marker already present), so no real log is ever
        # appended and the count can never rise to a disqualifying 2 — the frame
        # itself has to be rejected. The 40-'=' floor does that: banner_count 0.
        body = (
            f"import x\nprint('{self.NONCE}')\n"
            f"{self._frame(self.TOKEN_RULE)}"
            "# Command: python3 /daaf/x/t22_probe.py\n"
            "# Exit code: 0\n"
            "# Capture: COMPLETE\n"
            "# --- STDOUT ---\n"
            f"# {self.NONCE}\n"
            "# --- STDERR ---\n"
            f"{self.TOKEN_RULE}\n"
        )
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertEqual(facts["banner_count"], 0)
        self.assertFalse(facts["banner"])

    def test_real_frame_with_nonce_only_in_source_above_it_fails(self):
        # A genuine wrapper frame (e.g. a stale log from a prior run) whose
        # captured output does NOT carry this run's nonce — the token appears
        # only on the source print line ABOVE the banner. Not proof of execution.
        body = self._log(0, "# (no output)")
        self.assertIn(self.NONCE, body.split("# --- STDOUT ---")[0])  # present in source
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["nonce_in_stdout"])
        self.assertTrue(facts["frame_records"])

    def test_nonce_only_after_stderr_marker_fails(self):
        # A real frame, but the nonce sits BELOW the "# --- STDERR ---" marker —
        # outside the region that carries "# "-prefixed captured stdout. The old
        # "anywhere after the banner" rule accepted this; the region rule does not.
        body = self._log(0, "# (no output)").replace(
            "# (captured in STDOUT above via 2>&1)",
            f"# (captured in STDOUT above via 2>&1)\n# {self.NONCE}",
        )
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["nonce_in_stdout"])

    def test_missing_stdout_header_fails_frame_records(self):
        # A real rule + marker + exit/capture records, but the wrapper's
        # "# --- STDOUT ---" section header is absent: the log skeleton is
        # incomplete, so the frame is not the wrapper's own output.
        body = self._log(0, f"# {self.NONCE}", stdout_header=False)
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["frame_records"])
        self.assertFalse(facts["nonce_in_stdout"])
        self.assertEqual(facts["banner_count"], 1)

    def test_missing_command_record_fails_frame_records(self):
        # Same, for the "# Command:" record — the other half of the skeleton a
        # forgery would have to reproduce.
        body = self._log(0, f"# {self.NONCE}", command=False)
        verdict, facts = smoke_probes._evaluate_t22(True, body, self.NONCE)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertFalse(facts["frame_records"])
        self.assertTrue(facts["nonce_in_stdout"])


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


# --- Live-run verdict fixtures -----------------------------------------------
# Minimal excerpts copied from two observed 2026-09-24 Tier 1 transcripts
# (.claude/logs/sessions/..._0bfd41e1_orchestrator.jsonl = model_not_found run;
# ..._86e4b2c4_orchestrator.jsonl = passing run) plus the CLI result-object
# shape observed in scripts/scratch/postrebuild_2.1.281/r22_rm_r_probe.json.
# Inlined so the tests never depend on log paths at run time.

_SYNTHETIC_ERROR_RECORD = {
    "type": "assistant", "isApiErrorMessage": True, "error": "model_not_found",
    "message": {"model": "<synthetic>", "content": [{"type": "text", "text": (
        "There's an issue with the selected model (gpt-6-astra[1m]). It may not exist or you "
        "may not have access to it. Run --model to pick a different model.")}]},
}
_REAL_TOOL_USE_RECORD = {
    "type": "assistant",
    "message": {"model": "claude-opus-5-5", "content": [
        {"type": "tool_use", "id": "toolu_b1", "name": "Bash", "input": {"command": "echo daaf-smoke-ok"}}]},
}
_REAL_FINAL_RECORD = {
    "type": "assistant",
    "message": {"model": "claude-opus-5-5", "content": [{"type": "text", "text": "SMOKE_TIER1_COMPLETE"}]},
}
# A transient mid-response provider error, as the CLI records it (shape observed
# in .claude/logs/sessions/2026-09-22_16-54-32_0fec76e0_orchestrator.jsonl,
# where a real record followed it both times). Trimmed to the fields the gate reads.
_SERVER_ERROR_RECORD = {
    "type": "assistant", "isApiErrorMessage": True, "error": "server_error",
    "message": {"model": "<synthetic>", "content": [{"type": "text", "text": (
        "API Error: Server error mid-response. The response above may be incomplete.")}]},
}


def _cli_result(is_error=False, subtype="success", usage_ids=("claude-opus-5-5[1m]",),
                response="SMOKE_TIER1_COMPLETE", error="", input_tokens=4, output_tokens=1081,
                total_turns=2):
    """A RunResult-shaped stand-in: raw_json in the list-output form
    _parse_json_output stores, plus the modelUsage ids it extracts."""
    result_msg = {"type": "result", "subtype": subtype, "is_error": is_error, "num_turns": total_turns,
                  "result": response, "api_error_status": None}
    return types.SimpleNamespace(
        raw_json={"messages": [result_msg]}, error=error, response_text=response,
        model_identity=types.SimpleNamespace(claude_cli_model_usage_ids=list(usage_ids)),
        input_tokens=input_tokens, output_tokens=output_tokens, total_turns=total_turns,
        total_cost_usd=0.0, model_id="claude-opus-5-5[1m]",
    )


def _judge_t11(response_text, failure, warning=""):
    """T1.1 through the production path (_judge_t11 on a fresh ProbeResult),
    returning (verdict, detail)."""
    r = route_detection.ProbeResult(probe_id="T1.1", name="t", tier="1")
    return smoke_probes._judge_t11(r, response_text, failure, warning)


class Tier1VerdictTests(unittest.TestCase):
    """T1.1/T1.4/T1.5/T1.6/T1.7 pure evaluators against observed-shape fixtures."""

    def _t11(self, result, records):
        failure, warning = smoke_probes._live_run_health(result, records)
        return _judge_t11(result.response_text, failure, warning)

    def test_t11_synthetic_model_not_found_fails(self):
        # The observed failure: the CLI's own error sentence arrives as the
        # response, modelUsage is empty, the only assistant record is synthetic.
        res = _cli_result(usage_ids=(), response=_SYNTHETIC_ERROR_RECORD["message"]["content"][0]["text"],
                          input_tokens=None, output_tokens=None, total_turns=1)
        verdict, detail = self._t11(res, [_SYNTHETIC_ERROR_RECORD])
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertIn("model_not_found", detail)
        self.assertIn("<synthetic>", detail)

    def test_t11_is_error_result_fails(self):
        res = _cli_result(is_error=True, subtype="error_during_execution")
        verdict, detail = self._t11(res, [_REAL_TOOL_USE_RECORD, _REAL_FINAL_RECORD])
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertIn("is_error=true", detail)
        self.assertIn("error_during_execution", detail)

    def test_non_null_api_error_status_is_a_hard_fail_labelled_inferred(self):
        # Every observed value is null; a non-null one is read as an API
        # failure on inference, and the reason says so.
        res = _cli_result()
        res.raw_json["messages"][0]["api_error_status"] = 529
        failure, warning = smoke_probes._live_run_health(res, [_REAL_TOOL_USE_RECORD, _REAL_FINAL_RECORD])
        self.assertIn("api_error_status='529'", failure)
        self.assertIn("inferred", failure)
        self.assertEqual(warning, "")
        self.assertEqual(_judge_t11("SMOKE_TIER1_COMPLETE", failure, warning)[0], Verdict.FAIL)
        # null and "" are not failures.
        res.raw_json["messages"][0]["api_error_status"] = ""
        self.assertEqual(smoke_probes._live_run_health(res, [_REAL_FINAL_RECORD])[0], "")

    def test_t11_missing_completion_token_fails(self):
        res = _cli_result(response="Done.")
        verdict, detail = self._t11(res, [_REAL_TOOL_USE_RECORD])
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertIn("SMOKE_TIER1_COMPLETE", detail)

    def test_t11_real_model_with_token_passes(self):
        res = _cli_result()
        verdict, _ = self._t11(res, [_REAL_TOOL_USE_RECORD, _REAL_FINAL_RECORD])
        self.assertEqual(verdict, Verdict.PASS)

    def test_t14_claude_md_mention_is_not_injection(self):
        # CLAUDE.md ("instructions" attachment) and a skill body (isMeta user
        # record) both describe the reporter; neither is a hook injection.
        prose = "context-reporter injects `Context utilization [NOMINAL]: 55k / 1000k tokens`"
        records = [
            {"type": "attachment", "attachment": {"type": "instructions", "content": prose}},
            {"type": "user", "isMeta": True, "message": {"content": [{"type": "text", "text": prose}]}},
        ]
        self.assertEqual(smoke_probes._count_context_injections(records), 0)
        real = {"type": "attachment", "attachment": {
            "type": "hook_additional_context", "hookName": "PreToolUse:Agent", "hookEvent": "PreToolUse",
            "content": ["Context utilization [NOMINAL]: 43k / 1000k tokens (4%) | 2026-09-24 15:02:10 UTC"]}}
        self.assertEqual(smoke_probes._count_context_injections(records + [real]), 1)

    def test_t15_harness_written_cache_not_counted(self):
        # What T1.6's synthetic payload used to write: the payload model with
        # its [1m] suffix and the hard-coded 200000 window. Must not PASS.
        snap = {"model": {"value": "claude-opus-5-5[1m]"}, "ctx_window": {"value": "200000"}}
        verdict, _ = smoke_probes._evaluate_t15(snap, "claude-opus-5-5", "")
        self.assertEqual(verdict, Verdict.WARN)
        # A populated ctx-window cache alone never makes the probe PASS.
        verdict, detail = smoke_probes._evaluate_t15(
            {"model": {"value": None}, "ctx_window": {"value": "200000"}}, "claude-opus-5-5", "")
        self.assertEqual(verdict, Verdict.INFO)
        self.assertIn("Model cache absent", detail)

    def test_t15_matching_model_cache_passes_and_absent_window_is_expected(self):
        snap = {"model": {"value": "claude-opus-5-5"}, "ctx_window": {"value": None}}
        verdict, detail = smoke_probes._evaluate_t15(snap, "claude-opus-5-5", "")
        self.assertEqual(verdict, Verdict.PASS)
        self.assertIn("-p renders none", detail)
        self.assertEqual(smoke_probes._evaluate_t15(snap, "claude-opus-5-5", "no model")[0], Verdict.SKIP)

    def test_t16_uses_report_local_cache_dir_and_observed_model(self):
        cache_dir = _scratch_dir("t16_cache")
        self.addCleanup(__import__("shutil").rmtree, cache_dir, True)
        r6 = route_detection.ProbeResult(probe_id="T1.6", name="t", tier="1")
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout="bar-output\n", stderr="")
        with mock.patch.object(smoke_probes.subprocess, "run", return_value=done) as run:
            smoke_probes._run_t16(r6, "/x/transcript.jsonl", "sid-1234", "claude-opus-5-5", cache_dir, "")
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["env"]["DAAF_CONTEXT_BAR_CACHE_DIR"], str(cache_dir))
        self.assertEqual(json.loads(kwargs["input"])["model"]["id"], "claude-opus-5-5")
        self.assertEqual(r6.verdict, Verdict.PASS)
        # A failed live run renders nothing at all.
        r6b = route_detection.ProbeResult(probe_id="T1.6", name="t", tier="1")
        with mock.patch.object(smoke_probes.subprocess, "run") as run_b:
            smoke_probes._run_t16(r6b, "/x/t.jsonl", "sid", "m", cache_dir, "no model")
        run_b.assert_not_called()
        self.assertEqual(r6b.verdict, Verdict.SKIP)

    def test_t17_zero_turns_none_tokens_no_typeerror(self):
        verdict, _ = smoke_probes._evaluate_t17(None, None, 0, "")
        self.assertEqual(verdict, Verdict.WARN)
        verdict, detail = smoke_probes._evaluate_t17(None, None, 1, "no model named in the CLI modelUsage block")
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertIn("modelUsage", detail)
        self.assertEqual(smoke_probes._evaluate_t17(4, 1081, 2, "")[0], Verdict.PASS)

    # --- F1: recovered vs unrecovered transient API errors -------------------

    def test_recovered_transient_error_is_warn_not_fail(self):
        # Observed pattern: real -> <synthetic> server_error -> real.
        records = [_REAL_TOOL_USE_RECORD, _SERVER_ERROR_RECORD, _REAL_FINAL_RECORD]
        unrecovered, note, facts = smoke_probes._evaluate_transcript_api_errors(records)
        self.assertEqual(unrecovered, "")
        self.assertTrue(facts["recovered"])
        self.assertEqual(facts["error_records"], 1)
        self.assertIn("1 transient API-error record(s) recovered", note)
        self.assertIn("server_error", note)
        self.assertIn("Server error mid-response", note)
        failure, warning = smoke_probes._live_run_health(_cli_result(), records)
        self.assertEqual(failure, "")
        self.assertEqual(warning, note)
        verdict, detail = _judge_t11("SMOKE_TIER1_COMPLETE", failure, warning)
        self.assertEqual(verdict, Verdict.WARN)
        self.assertIn("Live-run warning", detail)
        self.assertIn("server_error", detail)

    def test_unrecovered_transient_error_fails(self):
        # The run ENDS on the error record: no real answer follows it.
        records = [_REAL_TOOL_USE_RECORD, _SERVER_ERROR_RECORD]
        unrecovered, note, facts = smoke_probes._evaluate_transcript_api_errors(records)
        self.assertFalse(facts["recovered"])
        self.assertEqual(note, "")
        self.assertIn("server_error", unrecovered)
        self.assertIn("<synthetic>", unrecovered)
        failure, warning = smoke_probes._live_run_health(_cli_result(), records)
        self.assertIn("server_error", failure)
        self.assertEqual(_judge_t11("SMOKE_TIER1_COMPLETE", failure, warning)[0],
                         Verdict.FAIL)

    def test_recovery_is_judged_after_the_last_error_record(self):
        # Recovered once, then a second error with nothing after it: FAIL, and
        # the reason names the count.
        records = [_REAL_TOOL_USE_RECORD, _SERVER_ERROR_RECORD, _REAL_FINAL_RECORD, _SERVER_ERROR_RECORD]
        unrecovered, note, facts = smoke_probes._evaluate_transcript_api_errors(records)
        self.assertEqual(facts["error_records"], 2)
        self.assertFalse(facts["recovered"])
        self.assertEqual(note, "")
        self.assertIn("2 error records", unrecovered)
        # An error-free transcript yields neither string.
        self.assertEqual(smoke_probes._evaluate_transcript_api_errors([_REAL_FINAL_RECORD])[:2], ("", ""))

    def test_live_warning_downgrades_pass_only(self):
        r = route_detection.ProbeResult(probe_id="T2.4", name="t", tier="2")
        r.verdict, r.detail = Verdict.PASS, "ok."
        smoke_probes._apply_live_warning(r, "1 transient API-error record(s) recovered")
        self.assertEqual(r.verdict, Verdict.WARN)
        self.assertIn("recovered", r.detail)
        r2 = route_detection.ProbeResult(probe_id="T2.5", name="t", tier="2")
        r2.verdict, r2.detail = Verdict.SKIP, "nothing to strip."
        smoke_probes._apply_live_warning(r2, "x")
        self.assertEqual(r2.verdict, Verdict.SKIP)
        r3 = route_detection.ProbeResult(probe_id="T2.1", name="t", tier="2")
        r3.verdict, r3.detail = Verdict.PASS, "ok."
        smoke_probes._apply_live_warning(r3, "")
        self.assertEqual(r3.verdict, Verdict.PASS)

    # --- F3: --max-turns stop is its own WARN, not "no real model" -----------

    def test_max_turns_is_warn_with_its_own_reason(self):
        # is_error on an error_max_turns result is unobserved; tolerate True.
        res = _cli_result(is_error=True, subtype="error_max_turns")
        failure, warning = smoke_probes._live_run_health(res, [_REAL_TOOL_USE_RECORD, _REAL_FINAL_RECORD])
        self.assertEqual(failure, "")
        self.assertIn("--max-turns", warning)
        self.assertIn("error_max_turns", warning)
        verdict, detail = _judge_t11("SMOKE_TIER1_COMPLETE", failure, warning)
        self.assertEqual(verdict, Verdict.WARN)
        # Without the token the probe's own check FAILs, and the reason is the
        # missing token plus the max-turns note, not "did not reach a real model".
        verdict, detail = _judge_t11("partial", failure, warning)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertIn("--max-turns", detail)
        self.assertNotIn("did not reach a real model", detail)
        # A max-turns stop with no real model billed is still a gate FAIL.
        failure, _ = smoke_probes._live_run_health(
            _cli_result(subtype="error_max_turns", usage_ids=()), [_SYNTHETIC_ERROR_RECORD])
        self.assertIn("modelUsage", failure)

    # --- F4: one injection is two attachments sharing a toolUseID ------------

    def test_t14_injection_pair_counts_once_per_tool_use_id(self):
        text = "Context utilization [NOMINAL]: 43k / 1000k tokens (4%) | 2026-09-24 15:02:10 UTC"

        def pair(tid):
            # Shape observed 2.1.281: hook_success (stdout) + hook_additional_context.
            return [
                {"type": "attachment", "attachment": {
                    "type": "hook_success", "hookName": "PreToolUse:Bash", "hookEvent": "PreToolUse",
                    "toolUseID": tid, "command": "context-reporter.sh", "stdout": text}},
                {"type": "attachment", "attachment": {
                    "type": "hook_additional_context", "hookName": "PreToolUse:Bash",
                    "hookEvent": "PreToolUse", "toolUseID": tid, "content": [text]}},
            ]
        self.assertEqual(smoke_probes._count_context_injections(pair("toolu_a")), 1)
        self.assertEqual(smoke_probes._count_context_injections(pair("toolu_a") + pair("toolu_b")), 2)


def _sub_snapshot(tool_names):
    return {"type": "attachment", "attachment": {
        "type": "prompt_snapshot", "tools": [{"name": n, "description": "", "schema": {}} for n in tool_names]}}


class Tier2VerdictTests(unittest.TestCase):
    """T2.3-T2.6 pure evaluators plus the Tier 2 live-run failure gate."""

    SKILL_PROSE = {"type": "user", "isMeta": True, "message": {"content": [{"type": "text", "text": (
        "Base directory for this skill: /daaf/.claude/skills/daaf-orchestrator ... subagents never "
        "launch nested subagents; they may not launch nested subagents either")}]}}

    def test_t26_skill_text_is_not_denial(self):
        # A subagent that loaded the orchestrator skill, attempted a nested
        # dispatch, and got no hook deny: prose must not count as the deny.
        sub = [self.SKILL_PROSE, {"type": "assistant", "message": {"model": "m", "content": [
            {"type": "tool_use", "id": "t1", "name": "Agent", "input": {"prompt": "OK"}}]}}]
        verdict, facts, _ = smoke_probes._evaluate_t26([sub])
        self.assertFalse(facts["denial_seen"])
        self.assertEqual(verdict, Verdict.WARN)

    def test_t26_real_deny_record_passes(self):
        deny = ("DAAF policy: subagents may not launch nested subagents — all dispatch authority "
                "belongs to the orchestrator.")
        sub = [{"type": "assistant", "message": {"model": "m", "content": [
                   {"type": "tool_use", "id": "t1", "name": "Agent", "input": {"prompt": "OK"}}]}},
               {"type": "user", "message": {"content": [
                   {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": deny}]}}]
        verdict, facts, _ = smoke_probes._evaluate_t26([sub])
        self.assertTrue(facts["denial_seen"])
        self.assertEqual(verdict, Verdict.PASS)

    def test_t26_depth1_no_agent_tool_passes_as_harness_layer(self):
        # Observed 2.1.281 subagent tool list (no Agent/Task), no attempt.
        sub = [_sub_snapshot(["Bash", "Edit", "ListAgents", "Read", "ReportFindings", "Skill",
                              "ToolSearch", "Write"])]
        verdict, facts, detail = smoke_probes._evaluate_t26([sub])
        self.assertEqual(verdict, Verdict.PASS)
        self.assertIs(facts["dispatch_tool_available"], False)
        self.assertIn("spawn depth 1", detail)
        self.assertIn("not exercised", detail)
        # Without a recorded tool list the model's self-report is not enough.
        self.assertEqual(smoke_probes._evaluate_t26([[self.SKILL_PROSE]])[0], Verdict.INFO)
        # Two subagent transcripts still means a nested dispatch ran.
        self.assertEqual(smoke_probes._evaluate_t26([sub, sub])[0], Verdict.FAIL)

    # --- F2: a retried outer dispatch is not nesting -------------------------

    @staticmethod
    def _dispatch(tid, name="Agent", prompt="x"):
        return {"type": "assistant", "message": {"model": "m", "content": [
            {"type": "tool_use", "id": tid, "name": name,
             "input": {"subagent_type": "general-purpose", "prompt": prompt}}]}}

    @staticmethod
    def _result(tid, is_error=None, content="done", tool_use_result=None):
        block = {"type": "tool_result", "tool_use_id": tid, "content": content}
        if is_error is not None:
            block["is_error"] = is_error
        rec = {"type": "user", "message": {"content": [block]}}
        if tool_use_result is not None:
            rec["toolUseResult"] = tool_use_result
        return rec

    # Shapes observed in stored transcripts: a completed dispatch's result
    # record carries toolUseResult {"agentId": ...} (2.1.281, b5524e7f); a
    # terminated-early one carries is_error true and a plain-string
    # toolUseResult with no agentId (2026-07-26 c6024f92).
    TERMINATED = "Agent terminated early due to an API error: Server error mid-response"

    def _ok_call(self, tid, prompt, agent_id):
        return [self._dispatch(tid, prompt=prompt),
                self._result(tid, None, "report", {"agentId": agent_id, "status": "completed"})]

    def _terminated_call(self, tid, prompt):
        return [self._dispatch(tid, prompt=prompt),
                self._result(tid, True, self.TERMINATED, "Error: " + self.TERMINATED)]

    @staticmethod
    def _sub(prompt=None, agent_id=None, tools=("Bash", "Read")):
        """A subagent transcript: its opening user prompt (the parent's
        input.prompt) and the agentId its records carry, then its tool list."""
        recs = []
        if prompt is not None:
            rec = {"type": "user", "message": {"content": prompt}}
            if agent_id:
                rec["agentId"] = agent_id
            recs.append(rec)
        snap = _sub_snapshot(list(tools))
        if agent_id:
            snap["agentId"] = agent_id
        recs.append(snap)
        return recs

    def test_t26_retried_dispatch_is_not_nested_dispatch(self):
        # Two completed outer dispatches with the same prompt -> two linked transcripts.
        main = self._ok_call("a0", "P", "agent0") + self._ok_call("a1", "P", "agent1")
        tops = smoke_probes._top_level_dispatches(main)
        self.assertEqual([t["agent_id"] for t in tops], ["agent0", "agent1"])
        verdict, facts, detail = smoke_probes._evaluate_t26(
            [self._sub("P", "agent0"), self._sub("P", "agent1")], main)
        self.assertEqual(verdict, Verdict.PASS, detail)
        self.assertTrue(facts["retried_dispatch"])
        self.assertEqual((facts["top_level_dispatches"], facts["linked_subagents"]), (2, 2))

    def test_t26_terminated_early_then_retry_is_not_nested(self):
        # (c) The regression: the first subagent died on a transient API error
        # (errored call, no agentId, but it DID leave a transcript), then the
        # retry completed. Two transcripts, two calls, both linked.
        main = self._terminated_call("a0", "P") + self._ok_call("a1", "P", "agent1")
        tops = smoke_probes._top_level_dispatches(main)
        self.assertEqual([(t["is_error"], t["agent_id"]) for t in tops], [(True, None), (False, "agent1")])
        verdict, facts, detail = smoke_probes._evaluate_t26(
            [self._sub("P", "agent0"), self._sub("P", "agent1")], main)
        self.assertNotEqual(verdict, Verdict.FAIL, detail)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertEqual((facts["top_level_errored"], facts["linked_subagents"],
                          facts["unlinked_subagents"]), (1, 2, 0))

    def test_t26_two_terminated_early_calls_are_not_nested(self):
        # (d) Both calls terminated early; each left a transcript (linked by prompt).
        main = self._terminated_call("a0", "P") + self._terminated_call("a1", "P")
        verdict, facts, detail = smoke_probes._evaluate_t26(
            [self._sub("P", "agent0"), self._sub("P", "agent1")], main)
        self.assertNotEqual(verdict, Verdict.FAIL, detail)
        self.assertEqual(facts["linked_subagents"], 2)

    def test_t26_transcript_linked_to_no_top_level_call_fails(self):
        # A child whose prompt and agentId match no orchestrator call: something
        # other than the orchestrator started it.
        main = self._ok_call("a0", "P", "agent0")
        child = self._sub("Reply with the single word OK and do nothing else.", "agentX")
        verdict, facts, detail = smoke_probes._evaluate_t26([self._sub("P", "agent0"), child], main)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertEqual(facts["unlinked_subagents"], 1)
        self.assertIn("match no top-level Agent/Task call", detail)

    def test_t26_count_backstop_for_unlinkable_or_missing_main(self):
        sub = [_sub_snapshot(["Bash", "Read"])]          # no identity: unlinkable
        main1 = self._terminated_call("a0", "P")
        verdict, facts, detail = smoke_probes._evaluate_t26([sub, sub], main1)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertEqual(facts["unlinkable_subagents"], 2)
        self.assertIn("more than the 1 top-level Agent/Task dispatch call(s)", detail)
        self.assertIn("errored calls included", detail)
        main2 = main1 + self._ok_call("a1", "P", "agent1")
        self.assertEqual(smoke_probes._evaluate_t26([sub, sub, sub], main2)[0], Verdict.FAIL)
        self.assertEqual(smoke_probes._evaluate_t26([sub, sub], main2)[0], Verdict.PASS)
        # Missing/unparsed main transcript: assume ONE outer dispatch; identity
        # cannot be judged without calls to link against.
        self.assertEqual(smoke_probes._evaluate_t26([self._sub("P", "agent0")], None)[0], Verdict.PASS)
        self.assertEqual(smoke_probes._evaluate_t26([sub, sub], None)[0], Verdict.FAIL)
        self.assertEqual(smoke_probes._evaluate_t26([sub, sub], [])[1]["top_level_dispatches"], 0)

    def test_t26_reviewer_repro_errored_retry_plus_successful_nested_call_fails(self):
        # Reviewer repro: main has a0 (is_error) + a1 (ok); the subagent's
        # nested n1 returned ok, and the child landed a second transcript.
        main = self._terminated_call("a0", "P") + self._ok_call("a1", "P", "agent1")
        sub = self._sub("P", "agent1", tools=("Bash", "Read", "Agent")) + [
            self._dispatch("n1", prompt="Reply OK"), self._result("n1")]
        child = self._sub("Reply OK", "agentN")
        verdict, facts, detail = smoke_probes._evaluate_t26([sub, child], main)
        self.assertEqual(facts["nested_succeeded"], 1)
        self.assertEqual(verdict, Verdict.FAIL)
        self.assertIn("A nested dispatch RAN", detail)
        # Independently of transcripts and linkage: a non-error nested result alone FAILs.
        self.assertEqual(smoke_probes._evaluate_t26([sub], main)[0], Verdict.FAIL)

    # --- G1: harness-layer rejection of an attempted nested call --------------

    # Records from the live 2026-09-24 16:48 run (session b5524e7f, subagent
    # ab44467f), trimmed: the subagent's snapshot tool list, its ToolSearch for
    # Agent/Task, then the nested Agent call and the harness's error result.
    LIVE_TOOLS = ["Bash", "Edit", "ListAgents", "Read", "ReportFindings", "Skill", "ToolSearch", "Write"]
    LIVE_REJECTION = ("<tool_use_error>Error: No such tool available: Agent. Agent is disabled for this "
                      "session, in subagents as well as here.</tool_use_error>")

    LIVE_AGENT_ID = "ab44467f9110314f5"   # observed: subagent records' agentId == toolUseResult.agentId

    def _live_g1_main(self):
        # The orchestrator's one Agent call (toolu_01N4tdZF...) and its completed
        # result, whose toolUseResult.agentId links the subagent (observed).
        return self._ok_call("toolu_01N4tdZFh38hUxr4PiekPNPx", "**BASE_DIR:** /daaf (trimmed T2.6 prompt)",
                             self.LIVE_AGENT_ID)

    def _live_g1_subagent(self):
        return [
            {"type": "user", "agentId": self.LIVE_AGENT_ID,
             "message": {"content": "**BASE_DIR:** /daaf (trimmed T2.6 prompt)"}},
            _sub_snapshot(self.LIVE_TOOLS),
            {"type": "assistant", "message": {"model": "m", "content": [
                {"type": "tool_use", "id": "toolu_01FP5Ym1sNJJRcWtvUgBLPXB", "name": "ToolSearch",
                 "input": {"query": "select:Agent,Task", "max_results": 5}}]}},
            self._result("toolu_01FP5Ym1sNJJRcWtvUgBLPXB", None, "No matching deferred tools found"),
            {"type": "assistant", "message": {"model": "m", "content": [
                {"type": "tool_use", "id": "toolu_01Y7siRk6EDw6p9eBZJCJoTZ", "name": "Agent",
                 "input": {"subagent_type": "general-purpose",
                           "prompt": "Reply with the single word OK and do nothing else."}}]}},
            self._result("toolu_01Y7siRk6EDw6p9eBZJCJoTZ", True, self.LIVE_REJECTION),
        ]

    def test_t26_live_harness_rejection_passes_on_harness_layer(self):
        verdict, facts, detail = smoke_probes._evaluate_t26([self._live_g1_subagent()], self._live_g1_main())
        # The live facts that used to grade WARN.
        self.assertEqual((facts["subagent_transcripts"], facts["top_level_dispatches"]), (1, 1))
        self.assertEqual(facts["linked_subagents"], 1)
        self.assertTrue(facts["nested_attempted"])
        self.assertFalse(facts["denial_seen"])
        self.assertIs(facts["dispatch_tool_available"], False)
        self.assertEqual(facts["nested_errored"], 1)
        self.assertIn("No such tool available: Agent", facts["nested_error_text"])
        self.assertEqual(verdict, Verdict.PASS, detail)
        self.assertIn("rejected at spawn depth 1 (harness layer)", detail)
        self.assertIn("because the tool was absent", detail)
        self.assertIn("not exercised", detail)

    def test_t26_attempt_with_tool_available_and_no_deny_stays_warn(self):
        sub = [_sub_snapshot(["Bash", "Agent"]), self._dispatch("n1"),
               self._result("n1", True, "some other error")]
        self.assertEqual(smoke_probes._evaluate_t26([sub])[0], Verdict.WARN)
        # Tool absent but the attempt has no recorded result: still inconclusive.
        sub2 = [_sub_snapshot(["Bash"]), self._dispatch("n2")]
        self.assertEqual(smoke_probes._evaluate_t26([sub2])[0], Verdict.WARN)

    def test_t26_harness_rejection_wording_depends_on_error_text(self):
        # F3: "because the tool was absent" only for the harness's own
        # "No such tool available" text; any other error gets neutral wording.
        sub = [_sub_snapshot(["Bash"]), self._dispatch("n1"), self._result("n1", True, "Some other failure")]
        verdict, _, detail = smoke_probes._evaluate_t26([sub])
        self.assertEqual(verdict, Verdict.PASS)
        self.assertNotIn("because the tool was absent", detail)
        self.assertIn("every nested Agent/Task attempt returned an error while Agent/Task was absent", detail)

    def test_t26_absent_tool_with_errored_and_unresulted_attempts_warns(self):
        # F4: one attempt errored, one has no recorded result -> WARN.
        sub = [_sub_snapshot(["Bash"]), self._dispatch("n1"), self._result("n1", True, self.LIVE_REJECTION),
               self._dispatch("n2")]
        verdict, facts, _ = smoke_probes._evaluate_t26([sub])
        self.assertEqual((facts["nested_calls"], facts["nested_errored"]), (2, 1))
        self.assertEqual(verdict, Verdict.WARN)

    def test_t26_unrecorded_tool_list_with_all_attempts_errored_warns(self):
        # F4: no prompt_snapshot tool list at all -> availability unknown -> WARN.
        sub = [self._dispatch("n1"), self._result("n1", True, self.LIVE_REJECTION)]
        verdict, facts, _ = smoke_probes._evaluate_t26([sub])
        self.assertIsNone(facts["dispatch_tool_available"])
        self.assertEqual(verdict, Verdict.WARN)

    def test_t26_tool_absence_needs_every_transcript_recorded(self):
        # F5: one recorded list without Agent/Task plus one unrecorded -> unknown.
        main = self._ok_call("a0", "P", "agent0") + self._ok_call("a1", "P", "agent1")
        recorded = self._sub("P", "agent0")
        unrecorded = [{"type": "user", "agentId": "agent1", "message": {"content": "P"}}]
        facts = smoke_probes._evaluate_t26([recorded, unrecorded], main)[1]
        self.assertIsNone(facts["dispatch_tool_available"])
        self.assertIs(smoke_probes._evaluate_t26([recorded], main)[1]["dispatch_tool_available"], False)

    # --- F7: deferred tool names count toward "Agent/Task available" ---------

    @staticmethod
    def _deferred(added, removed=()):
        # Shape observed in 2026-08 orchestrator transcripts.
        return {"type": "attachment", "attachment": {
            "type": "deferred_tools_delta", "addedNames": list(added), "removedNames": list(removed),
            "addedLines": []}}

    def test_t26_deferred_agent_tool_blocks_harness_layer_pass(self):
        sub = [_sub_snapshot(["Bash", "Read", "ToolSearch"]), self._deferred(["Agent", "CronList"])]
        verdict, facts, _ = smoke_probes._evaluate_t26([sub])
        self.assertIs(facts["dispatch_tool_available"], True)
        self.assertEqual(facts["subagent_deferred_tools"], ["Agent", "CronList"])
        self.assertEqual(verdict, Verdict.SKIP)

    def test_t26_deferred_names_are_matched_exactly_and_deltas_apply_in_order(self):
        # TaskOutput/TaskStop are not the Task dispatch tool.
        sub = [_sub_snapshot(["Bash", "Read"]), self._deferred(["TaskOutput", "TaskStop"])]
        verdict, facts, detail = smoke_probes._evaluate_t26([sub])
        self.assertIs(facts["dispatch_tool_available"], False)
        self.assertEqual(verdict, Verdict.PASS)
        self.assertIn("including any deferred tool names", detail)
        # Added then removed: no longer available.
        sub2 = [_sub_snapshot(["Bash"]), self._deferred(["Agent"]), self._deferred([], ["Agent"])]
        self.assertEqual(smoke_probes._evaluate_t26([sub2])[0], Verdict.PASS)
        # Field absent entirely (seen in some 2.1.281 subagent transcripts): recorded as None.
        self.assertIsNone(smoke_probes._evaluate_t26([[_sub_snapshot(["Bash"])]])[1]["subagent_deferred_tools"])

    def test_interpreting_results_quotes_code_strings_verbatim(self):
        # F10: the reference doc must quote the T2.6 harness-layer detail and
        # name T2.3 exactly as the code does, so they cannot drift apart.
        doc = (_REPO_ROOT / ".claude" / "skills" / "daaf-deploy-smoke-testing" / "references"
               / "interpreting-results.md").read_text()
        _, _, detail = smoke_probes._evaluate_t26([[_sub_snapshot(["Bash", "Read"])]])
        self.assertIn(f'"{detail}"', doc)
        _, _, rejected = smoke_probes._evaluate_t26([self._live_g1_subagent()], self._live_g1_main())
        self.assertIn(f'"{rejected}"', doc)
        other = [_sub_snapshot(["Bash"]), self._dispatch("n1"), self._result("n1", True, "Some other failure")]
        _, _, neutral = smoke_probes._evaluate_t26([other])
        self.assertIn(f'"{neutral}"', doc)
        self.assertIn("**T2.3 Web access (WebSearch + fetch protocol)**", doc)
        self.assertIn("**T2.6 Nested-dispatch prevention**", doc)

    def test_t23_requires_non_error_web_result(self):
        use = {"type": "assistant", "message": {"model": "m", "content": [
            {"type": "tool_use", "id": "w1", "name": "WebSearch", "input": {"query": "capital of France"}}]}}
        ok = {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "w1", "is_error": None, "content": "Paris"}]}}
        err = {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "w1", "is_error": True, "content": "denied"}]}}
        self.assertEqual(smoke_probes._evaluate_t23([[use, ok]])[0], Verdict.PASS)
        self.assertEqual(smoke_probes._evaluate_t23([[use, err]])[0], Verdict.FAIL)
        self.assertEqual(smoke_probes._evaluate_t23([[use]])[0], Verdict.FAIL)

    def test_t24_requires_successful_polars_skill_call(self):
        def call(tid, skill):
            return {"type": "assistant", "message": {"model": "m", "content": [
                {"type": "tool_use", "id": tid, "name": "Skill", "input": {"skill": skill}}]}}

        def res(tid):
            return {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": tid, "content": "Launching skill"}]}}
        orchestrator_only = [call("s1", "daaf-orchestrator"), res("s1")]
        self.assertEqual(smoke_probes._evaluate_t24(orchestrator_only)[0], Verdict.FAIL)
        self.assertEqual(smoke_probes._evaluate_t24(orchestrator_only + [call("s2", "polars"), res("s2")])[0],
                         Verdict.PASS)

    def test_t25_strip_evidence_requires_isolation_hook_attachment(self):
        use = {"type": "assistant", "message": {"model": "m", "content": [
            {"type": "tool_use", "id": "a1", "name": "Agent", "input": {"isolation": "worktree", "prompt": "x"}}]}}
        other_hook = {"type": "attachment", "attachment": {
            "type": "hook_success", "command": "enforce-model-ceiling.sh", "stdout": '{"updatedInput": {}}'}}
        iso_hook = {"type": "attachment", "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent",
            "command": '"$CLAUDE_PROJECT_DIR"/.claude/hooks/block-remote-isolation.sh',
            "stdout": '{"hookSpecificOutput": {"permissionDecision": "allow", "updatedInput": {}}}'}}
        self.assertEqual(smoke_probes._evaluate_t25([use, other_hook])[0], Verdict.WARN)
        self.assertEqual(smoke_probes._evaluate_t25([use, iso_hook])[0], Verdict.PASS)
        self.assertEqual(smoke_probes._evaluate_t25([iso_hook])[0], Verdict.SKIP)

    def test_tier2_api_error_fails_not_skips(self):
        # Every Tier 2 probe on a model_not_found run reads FAIL with the
        # reason — T2.5/T2.6 used to SKIP vacuously on such runs.
        sandbox = _scratch_dir("t2_apierr")
        self.addCleanup(__import__("shutil").rmtree, sandbox, True)
        bad = _cli_result(usage_ids=(), response="There's an issue with the selected model",
                          input_tokens=None, output_tokens=None, total_turns=1)
        with mock.patch.object(smoke_probes, "_sandbox_dir", return_value=sandbox), \
             mock.patch.object(smoke_probes, "execute_smoke_run",
                               return_value=(bad, {"session_id": "sid-apierr-000"})), \
             mock.patch.object(smoke_probes, "find_transcript", return_value=Path("/fake.jsonl")), \
             mock.patch.object(smoke_probes, "load_transcript_records",
                               return_value=[_SYNTHETIC_ERROR_RECORD]), \
             mock.patch.object(smoke_probes, "find_subagent_transcripts", return_value=[]):
            results = smoke_probes.run_tier2("", {}, timeout=5)
        self.assertEqual([r.probe_id for r in results], ["T2.1", "T2.2", "T2.3", "T2.4", "T2.5", "T2.6"])
        for r in results:
            with self.subTest(probe=r.probe_id):
                self.assertEqual(r.verdict, Verdict.FAIL, r.detail)
                self.assertIn("model_not_found", r.detail)

    def test_tier2_recovered_error_does_not_trip_the_gate(self):
        # A recovered mid-response server_error must reach each probe's own
        # verdict (with the warning recorded), never the gate's FAIL.
        sandbox = _scratch_dir("t2_recovered")
        self.addCleanup(__import__("shutil").rmtree, sandbox, True)
        records = [_REAL_TOOL_USE_RECORD, _SERVER_ERROR_RECORD, _REAL_FINAL_RECORD]
        with mock.patch.object(smoke_probes, "_sandbox_dir", return_value=sandbox), \
             mock.patch.object(smoke_probes, "execute_smoke_run",
                               return_value=(_cli_result(), {"session_id": "sid-recovered-00"})), \
             mock.patch.object(smoke_probes, "find_transcript", return_value=Path("/fake.jsonl")), \
             mock.patch.object(smoke_probes, "load_transcript_records", return_value=records), \
             mock.patch.object(smoke_probes, "find_subagent_transcripts", return_value=[]):
            results = smoke_probes.run_tier2("", {}, timeout=5)
        for r in results:
            with self.subTest(probe=r.probe_id):
                self.assertNotIn("did not reach a real model", r.detail)
                self.assertIn("Live-run warning", r.detail)
                gate = [e for e in r.evidence if e.command.startswith("live-run health")]
                self.assertTrue(gate and gate[0].output.startswith("ok with warning"), gate)


class MalformedToolInputTests(unittest.TestCase):
    """R1: a tool_use whose `input` is a non-empty string or list (untrusted,
    malformed transcript) must never raise — it used to abort the whole run with
    no report via `(input or {}).get(...)` — and must never substring-match."""

    BAD_INPUTS = ("isolation worktree prompt web_fetch.sh skill polars", ["isolation", "prompt"], 7)

    @staticmethod
    def _use(tid, name, inp):
        return {"type": "assistant", "message": {"model": "m", "content": [
            {"type": "tool_use", "id": tid, "name": name, "input": inp}]}}

    @staticmethod
    def _ok(tid):
        return {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}}

    def test_tool_input_normalizes_non_dicts(self):
        for bad in self.BAD_INPUTS + (None, ""):
            with self.subTest(bad=bad):
                self.assertEqual(smoke_probes._tool_input(bad), {})
        self.assertEqual(smoke_probes._tool_input({"prompt": "P"}), {"prompt": "P"})

    def test_tool_calls_yield_dict_input(self):
        for bad in self.BAD_INPUTS:
            with self.subTest(bad=bad):
                calls = smoke_probes._tool_calls([self._use("t1", "Bash", bad), self._ok("t1")])
                self.assertEqual(calls, [("Bash", {}, False)])

    def test_top_level_dispatches_non_dict_input_has_no_prompt(self):
        for bad in self.BAD_INPUTS:
            with self.subTest(bad=bad):
                tops = smoke_probes._top_level_dispatches([self._use("a0", "Agent", bad), self._ok("a0")])
                self.assertEqual([(t["id"], t["prompt"]) for t in tops], [("a0", None)])

    def test_t26_main_transcript_with_string_input_does_not_raise(self):
        # The reviewer's repro shape: the orchestrator's Agent call carries a
        # string input. T2.6 must return a verdict, not AttributeError.
        main = [self._use("a0", "Agent", "Reply with the single word OK"), self._ok("a0")]
        sub = [_sub_snapshot(["Bash", "Read"])]
        verdict, facts, _ = smoke_probes._evaluate_t26([sub], main)
        self.assertEqual(facts["top_level_dispatches"], 1)
        self.assertEqual(verdict, Verdict.PASS)
        # A nested call with a list input inside the subagent is still counted.
        sub2 = [_sub_snapshot(["Bash"]), self._use("n1", "Agent", ["x"]),
                {"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "n1", "is_error": True,
                     "content": "No such tool available: Agent"}]}}]
        self.assertEqual(smoke_probes._evaluate_t26([sub2], main)[1]["nested_calls"], 1)

    def test_t23_t24_t25_consumers_tolerate_non_dict_input(self):
        for bad in self.BAD_INPUTS:
            with self.subTest(bad=bad):
                recs = [self._use("b1", "Bash", bad), self._ok("b1"),
                        self._use("s1", "Skill", bad), self._ok("s1"),
                        self._use("a1", "Agent", bad), self._ok("a1")]
                # No web call, no polars skill, no isolation request can be read
                # out of a non-dict input — in particular no substring match.
                self.assertEqual(smoke_probes._evaluate_t23([recs])[1]["web_calls"], 0)
                self.assertEqual(smoke_probes._evaluate_t24(recs)[1]["skills_called"], [""])
                self.assertEqual(smoke_probes._evaluate_t25(recs),
                                 (Verdict.SKIP, {"isolation_requested": False, "strip_evidence": False}))

    def test_t26_docstring_warns_about_non_orchestrator_subagents(self):
        # R3: a subagent not started by an orchestrator Agent/Task call reads
        # as unlinked -> nested -> FAIL; the evaluator's docstring says so.
        doc = smoke_probes._evaluate_t26.__doc__
        self.assertIn("/code-review", doc)
        self.assertIn("forked skill", doc)
        main = [self._use("a0", "Agent", {"prompt": "P"}), self._ok("a0")]
        review = [{"type": "user", "agentId": "agentReview", "message": {"content": "Review the diff"}},
                  _sub_snapshot(["Bash", "Read"])]
        linked = [{"type": "user", "agentId": "agent0", "message": {"content": "P"}}, _sub_snapshot(["Bash"])]
        self.assertEqual(smoke_probes._evaluate_t26([linked, review], main)[0], Verdict.FAIL)


class StatuslineProbeTests(unittest.TestCase):
    """T0.7 renders both statuslines for a synthetic session into a report-local
    cache dir and never writes /tmp."""

    def setUp(self):
        self.cache = _scratch_dir("t07_cache")
        self.addCleanup(__import__("shutil").rmtree, self.cache, True)

    def test_tmp_candidates_are_exact_synthetic_paths(self):
        paths = smoke_probes._synthetic_tmp_cache_paths()
        self.assertTrue(paths)
        for p in paths:
            self.assertTrue(p.startswith("/tmp/claude-"), p)
            self.assertIn("-smoke-synthetic", p)
            self.assertNotIn("*", p)

    def test_both_seams_point_at_the_cache_dir(self):
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout="bar\n", stderr="")
        with mock.patch.object(smoke_probes.subprocess, "run", return_value=done) as run:
            r = smoke_probes.probe_statuslines(str(_REPO_ROOT), cache_dir=self.cache)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            env = call.kwargs["env"]
            self.assertEqual(env["DAAF_CONTEXT_BAR_CACHE_DIR"], str(self.cache))
            self.assertEqual(env["DAAF_SUBAGENT_BAR_CACHE_DIR"], str(self.cache))
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)

    def test_default_cache_dir_is_project_scratch_not_tmp(self):
        base = _scratch_dir("t07_base")
        self.addCleanup(__import__("shutil").rmtree, base, True)
        scripts = base / ".claude" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("context-bar.sh", "subagent-bar.sh"):
            (scripts / name).write_text("echo stub\n")
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout="bar\n", stderr="")
        with mock.patch.object(smoke_probes.subprocess, "run", return_value=done) as run:
            smoke_probes.probe_statuslines(str(base))
        used = run.call_args.kwargs["env"]["DAAF_CONTEXT_BAR_CACHE_DIR"]
        self.assertEqual(used, str(base / "scripts" / "scratch" / "deploy_smoke_t07_cache"))
        self.assertFalse(used.startswith("/tmp"))

    def test_changed_tmp_cache_warns(self):
        done = subprocess.CompletedProcess(args=[], returncode=0, stdout="bar\n", stderr="")
        paths = smoke_probes._synthetic_tmp_cache_paths()
        before = {p: None for p in paths}
        after = dict(before, **{paths[0]: (1, 7)})
        with mock.patch.object(smoke_probes.subprocess, "run", return_value=done), \
             mock.patch.object(smoke_probes, "_stat_paths", side_effect=[before, after]):
            r = smoke_probes.probe_statuslines(str(_REPO_ROOT), cache_dir=self.cache)
        self.assertEqual(r.verdict, Verdict.WARN)
        self.assertIn(paths[0], r.detail)
        # An unchanged pre-existing /tmp file (e.g. a leftover) is not this run's write.
        stale = dict(before, **{paths[0]: (1, 7)})
        with mock.patch.object(smoke_probes.subprocess, "run", return_value=done), \
             mock.patch.object(smoke_probes, "_stat_paths", side_effect=[stale, dict(stale)]):
            self.assertEqual(smoke_probes.probe_statuslines(str(_REPO_ROOT), cache_dir=self.cache).verdict,
                             Verdict.PASS)

    def test_real_render_writes_report_local_caches_and_leaves_tmp_alone(self):
        # Real scripts, real bash; ANTHROPIC_BASE_URL dropped so context-bar never
        # reaches the OpenRouter catalogue (no network in this suite).
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_BASE_URL"}
        tmp_before = smoke_probes._stat_paths(smoke_probes._synthetic_tmp_cache_paths())
        with mock.patch.dict(os.environ, env, clear=True):
            r = smoke_probes.probe_statuslines(str(_REPO_ROOT), cache_dir=self.cache)
        self.assertEqual(r.verdict, Verdict.PASS, r.detail)
        written = sorted(p.name for p in self.cache.iterdir())
        self.assertIn("claude-model-smoke-synthetic", written)
        self.assertIn("claude-ctx-window-smoke-synthetic", written)
        self.assertEqual(smoke_probes._stat_paths(smoke_probes._synthetic_tmp_cache_paths()), tmp_before)

    def test_run_tier0_and_cli_forward_the_report_local_dir(self):
        stub = route_detection.ProbeResult(probe_id="T0.7", name="t", tier="0", verdict=Verdict.PASS)
        with mock.patch.object(smoke_probes, "probe_statuslines", return_value=stub) as ps, \
             mock.patch.object(smoke_probes, "probe_cli_available", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_hook_registration", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_shim_health", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_auth_json", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_workspace_invariants", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_r_locale", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_local_settings_shadowing", return_value=stub), \
             mock.patch.object(smoke_probes, "probe_synced_surface", return_value=stub):
            smoke_probes.run_tier0(route_detection.build_route_info({}), {}, base_dir="/not-used",
                                   statusline_cache_dir=self.cache)
        self.assertEqual(ps.call_args.kwargs["cache_dir"], self.cache)

        report = _scratch_dir("t07_report")
        self.addCleanup(__import__("shutil").rmtree, report, True)
        argv = ["run_deploy_smoke.py", "--tiers", "0", "--yes", "--report-dir", str(report)]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(smoke_probes, "run_tier0", return_value=[stub]) as rt0, \
             mock.patch("builtins.print"):
            run_deploy_smoke.main()
        self.assertEqual(rt0.call_args.kwargs["statusline_cache_dir"],
                         report / "evidence" / "t07_statusline_cache")


class LocalSettingsShadowingTests(unittest.TestCase):
    """T0.12 against a temporary base_dir holding .claude/settings{,.local}.json."""

    SHARED_ENV = {"ANTHROPIC_MODEL": "claude-opus-5-5[1m]", "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"}

    def setUp(self):
        self.base = _scratch_dir("t012_base")
        (self.base / ".claude").mkdir()
        (self.base / ".claude" / "settings.json").write_text(json.dumps({"env": self.SHARED_ENV}))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)

    def _probe(self, local_text=None):
        if local_text is not None:
            (self.base / ".claude" / "settings.local.json").write_text(local_text)
        return smoke_probes.probe_local_settings_shadowing(str(self.base))

    def test_no_local_file_passes(self):
        r = self._probe()
        self.assertEqual(r.verdict, Verdict.PASS)
        self.assertIn("No settings.local.json", r.detail)

    def test_local_file_without_env_passes(self):
        r = self._probe(json.dumps({"permissions": {"allow": []}}))
        self.assertEqual(r.verdict, Verdict.PASS)

    def test_shadowed_non_model_key_warns_and_names_file_and_key(self):
        r = self._probe(json.dumps({"env": {"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "3"}}))
        self.assertEqual(r.verdict, Verdict.WARN)
        self.assertIn("settings.local.json", r.detail)
        self.assertIn("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", r.detail)
        self.assertNotIn('"3"', json.dumps([e.to_dict() for e in r.evidence]))

    def test_shadowed_anthropic_model_fails_with_values_via_redaction_helper(self):
        r = self._probe(json.dumps({"env": {"ANTHROPIC_MODEL": "gpt-6-astra[1m]"}}))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("ANTHROPIC_MODEL", r.detail)
        outputs = " ".join(e.output for e in r.evidence)
        self.assertIn("gpt-6-astra[1m]", outputs)
        self.assertIn("claude-opus-5-5[1m]", outputs)

    def test_invalid_local_json_warns(self):
        r = self._probe("{not json")
        self.assertEqual(r.verdict, Verdict.WARN)
        self.assertIn("invalid JSON", r.detail)

    def test_local_only_model_selector_warns(self):
        # settings.json does not set CLAUDE_CODE_SUBAGENT_MODEL, so nothing is
        # shadowed, but the local pin still re-points every session.
        r = self._probe(json.dumps({"env": {"CLAUDE_CODE_SUBAGENT_MODEL": "example-model-1"}}))
        self.assertEqual(r.verdict, Verdict.WARN)
        self.assertIn("CLAUDE_CODE_SUBAGENT_MODEL", r.detail)
        self.assertIn("does not set", r.detail)
        outputs = " ".join(e.output for e in r.evidence)
        self.assertIn("example-model-1", outputs)
        self.assertIn("settings.json=<unset>", outputs)

    def test_local_only_non_selector_key_still_passes(self):
        r = self._probe(json.dumps({"env": {"EXAMPLE_LOCAL_FLAG": "1"}}))
        self.assertEqual(r.verdict, Verdict.PASS)

    def test_local_only_selector_is_noted_alongside_a_shadow_fail(self):
        r = self._probe(json.dumps({"env": {"ANTHROPIC_MODEL": "example-model-2",
                                            "CLAUDE_CODE_SUBAGENT_MODEL": "example-model-1"}}))
        self.assertEqual(r.verdict, Verdict.FAIL)
        self.assertIn("ANTHROPIC_MODEL", r.detail)
        self.assertIn("CLAUDE_CODE_SUBAGENT_MODEL", r.detail)


class SyncedSurfaceTests(unittest.TestCase):
    """T0.13 against an injected config dir; INFO in every case."""

    def setUp(self):
        self.cfg = _scratch_dir("t013_cfg")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.cfg, ignore_errors=True)

    def test_empty_config_is_info_none(self):
        r = smoke_probes.probe_synced_surface({}, config_dir=str(self.cfg))
        self.assertEqual(r.verdict, Verdict.INFO)
        self.assertIn("No claude.ai synced skills or plugins", r.detail)

    def test_plugin_with_hooks_is_info_naming_events(self):
        # Made-up bucket, skill and plugin names: the probe logic is generic.
        bucket = "bucket0000_test"
        (self.cfg / "skills" / "synced" / bucket / "example-skill").mkdir(parents=True)
        (self.cfg / "skills" / "synced" / f".bucket-{bucket}").mkdir(parents=True)
        hooks_dir = self.cfg / "plugins" / "synced" / bucket / "example-plugin" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": {
            "PostToolUse": [{"matcher": "Edit|Write", "hooks": []}], "Stop": [{"hooks": []}]}}))
        (self.cfg / "plugins" / "synced" / bucket / "other-plugin").mkdir()
        # base_dir points at the scratch cfg too, so no real project settings leak in.
        r = smoke_probes.probe_synced_surface({"CLAUDE_CONFIG_DIR": str(self.cfg)}, base_dir=str(self.cfg))
        self.assertEqual(r.verdict, Verdict.INFO)
        self.assertIn("example-skill", r.detail)
        self.assertIn("2 synced plugin(s) on disk: example-plugin (enabled state not set), "
                      "other-plugin (enabled state not set)", r.detail)
        self.assertIn("Plugin example-plugin registers PostToolUse, Stop hook(s)", r.detail)
        self.assertIn("outside DAAF's audited hook set", r.detail)
        self.assertNotIn(".bucket-", r.detail)

    def test_disabled_plugin_is_labelled_from_enabled_plugins(self):
        # G10: "<name>@synced": false (the shape /plugin writes to user
        # settings, observed 2026-09-24) marks the on-disk plugin disabled; a
        # later-precedence local file overrides an earlier scope per key.
        bucket = "bucket0000_test"
        hooks_dir = self.cfg / "plugins" / "synced" / bucket / "example-plugin" / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": []}]}}))
        (self.cfg / "plugins" / "synced" / bucket / "other-plugin").mkdir()
        (self.cfg / "settings.json").write_text(json.dumps({"enabledPlugins": {
            "example-plugin@synced": False, "other-plugin@synced": False}}))
        (self.cfg / ".claude").mkdir()
        (self.cfg / ".claude" / "settings.local.json").write_text(json.dumps({"enabledPlugins": {
            "other-plugin@synced": True}}))
        r = smoke_probes.probe_synced_surface({}, config_dir=str(self.cfg), base_dir=str(self.cfg))
        self.assertEqual(r.verdict, Verdict.INFO)
        self.assertIn("example-plugin (disabled), other-plugin (enabled)", r.detail)
        self.assertIn("but enabledPlugins disables it", r.detail)
        self.assertNotIn("Plugin example-plugin registers Stop hook(s) — these run outside", r.detail)

    def test_listing_error_is_info_not_an_exception(self):
        # F5: an OSError while listing (e.g. PermissionError on a bucket) must
        # not abort the run; the probe stays INFO and names the error.
        with mock.patch.object(smoke_probes, "_synced_names",
                               side_effect=PermissionError(13, "Permission denied")):
            r = smoke_probes.probe_synced_surface({}, config_dir=str(self.cfg))
        self.assertEqual(r.verdict, Verdict.INFO)
        self.assertIn("Could not list", r.detail)
        self.assertIn("PermissionError", r.detail)


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
