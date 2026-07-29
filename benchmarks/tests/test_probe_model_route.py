"""Deterministic tests for the bounded DAAFBench model-route probe.

All filesystem artifacts stay beneath benchmarks/.test_scratch and are removed.
Every executor, route, and model-registry dependency is mocked; these tests make
no live model call and do not contact the provider shim.
"""

import io
import json
import shutil
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from benchmarks.harness.models import ModelConfig, RouteProvenance, RunResult
from benchmarks.scripts import probe_model_route


TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch")


def luna_model():
    return ModelConfig(
        id="gpt-5.6-luna",
        name="GPT-5.6 Luna (ChatGPT Subscription)",
        key="gpt-56-luna-chatgpt",
        provider="chatgpt-subscription",
        cost_tier="medium",
        effort_level="high",
        context_window_tokens=370_000,
        actual_billing_treatment="not_separately_billed",
        api_equivalent_pricing={
            "source_url": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
            "accessed_at": "2026-07-15",
            "threshold_input_tokens": 272_000,
        },
    )


def fake_result(
    response="LUNA_PROBE_OK",
    error=None,
    observed_ids=None,
    backend_confirmed=None,
    exit_code=0,
):
    result = RunResult(
        test_case_id="model-route-probe",
        model_id="gpt-5.6-luna",
        model_name="GPT-5.6 Luna (ChatGPT Subscription)",
        run_index=0,
        session_id="probe-session-123",
        total_turns=1,
        total_cost_usd=None,
        duration_seconds=1.25,
        response_text=response,
        raw_json={
            "credential_extra": "super-secret-extra",
            "full_environment": {"AUTH_TOKEN": "super-secret-env-value"},
        },
        transcript_path="",
        error=error,
        exit_code=exit_code,
        wall_clock_seconds=1.5,
        start_time_utc="2026-07-15T20:00:00+00:00",
        end_time_utc="2026-07-15T20:00:01.500000+00:00",
        route_provenance=RouteProvenance(
            route_type="chatgpt_subscription_shim",
            provider="chatgpt-subscription",
            endpoint_origin="http://127.0.0.1:4141",
            backend_mode="chatgpt",
            backend="https://chatgpt.com/backend-api/codex",
            shim_version="1.2.5",
            sanitizer_enabled=True,
            sanitizer_condition="deployed_default",
            auth_store_readable=True,
            reasoning_effort="high",
            text_verbosity="high",
            captured_at="2026-07-15T20:00:00+00:00",
        ),
    )
    result.model_identity.benchmark_key = "gpt-56-luna-chatgpt"
    result.model_identity.requested_model_id = "gpt-5.6-luna"
    result.model_identity.claude_cli_model_usage_ids = (
        ["gpt-5.6-luna"] if observed_ids is None else list(observed_ids)
    )
    result.model_identity.backend_confirmed_model_id = backend_confirmed
    result.usage_observed.input_tokens = 100
    result.usage_observed.input_semantics = (
        "shim_reported_total_input_cache_breakdown_unavailable"
    )
    result.usage_observed.input_includes_cache_tokens = True
    result.usage_observed.output_tokens = 5
    result.usage_observed.output_includes_reasoning = True
    result.usage_observed.cache_read_tokens = None
    result.usage_observed.cache_write_tokens = None
    result.usage_observed.reasoning_tokens = None
    result.usage_observed.source = "claude_cli.modelUsage"
    result.usage_observed.completeness = "partial"
    result.usage_observed.incompleteness_reasons = [
        "cache_read_tokens_not_reliably_exposed_by_deployed_shim",
        "cache_write_tokens_not_reliably_exposed_by_deployed_shim",
        "reasoning_tokens_not_exposed_by_deployed_shim",
        "per_request_context_tier_not_exposed_by_claude_cli",
    ]
    return result


class ProbeCliValidationTests(unittest.TestCase):
    def test_default_model_and_singular_argument_validation(self):
        parser = probe_model_route.build_parser()
        self.assertEqual(
            "gpt-56-luna-chatgpt",
            parser.parse_args([]).model,
        )
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as comma_stopped:
                probe_model_route.validate_model_argument(
                    parser,
                    "gpt-56-luna-chatgpt,gpt-56-luna",
                )
        self.assertNotEqual(0, comma_stopped.exception.code)

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as multi_stopped:
                parser.parse_args([
                    "--model",
                    "gpt-56-luna-chatgpt",
                    "gpt-56-luna",
                ])
        self.assertNotEqual(0, multi_stopped.exception.code)

    def test_openrouter_and_other_non_subscription_entries_are_rejected(self):
        non_subscription_models = (
            ModelConfig(
                id="openai/gpt-5.6-luna",
                name="GPT-5.6 Luna",
                key="gpt-56-luna",
                provider="openrouter",
            ),
            ModelConfig(
                id="claude-sonnet-4-6",
                name="Sonnet 4.6",
                key="sonnet-46",
                provider="anthropic",
            ),
        )
        for model in non_subscription_models:
            with self.subTest(provider=model.provider):
                with patch.object(
                    probe_model_route,
                    "load_models",
                    return_value={model.key: model},
                ), patch.object(probe_model_route, "run_preflight") as preflight, \
                        patch.object(probe_model_route, "execute_run") as execute, \
                        redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as stopped:
                        probe_model_route.main(["--model", model.key, "--yes"])
                self.assertNotEqual(0, stopped.exception.code)
                preflight.assert_not_called()
                execute.assert_not_called()

    def test_help_calls_no_registry_network_preflight_or_executor_path(self):
        with patch.object(probe_model_route, "load_models") as load, \
                patch.object(probe_model_route, "run_preflight") as preflight, \
                patch.object(probe_model_route, "execute_run") as execute, \
                patch("benchmarks.harness.route_provenance.build_opener") as network, \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                probe_model_route.main(["--help"])
        self.assertEqual(0, stopped.exception.code)
        load.assert_not_called()
        preflight.assert_not_called()
        execute.assert_not_called()
        network.assert_not_called()


class ProbeComparisonTests(unittest.TestCase):
    def test_exact_comparison_strips_only_surrounding_whitespace(self):
        matching = probe_model_route.compare_response(
            "  \nLUNA_PROBE_OK\t ",
            "LUNA_PROBE_OK",
        )
        self.assertTrue(matching["scorable"])
        self.assertTrue(matching["exact_match"])
        self.assertEqual(
            "response_text.strip() == expected_text",
            matching["comparison_rule"],
        )

        case_mismatch = probe_model_route.compare_response(
            "luna_probe_ok",
            "LUNA_PROBE_OK",
        )
        extra_text = probe_model_route.compare_response(
            "LUNA_PROBE_OK.",
            "LUNA_PROBE_OK",
        )
        missing = probe_model_route.compare_response(" \n\t ", "LUNA_PROBE_OK")
        self.assertFalse(case_mismatch["exact_match"])
        self.assertFalse(extra_text["exact_match"])
        self.assertFalse(missing["scorable"])
        self.assertFalse(missing["exact_match"])


class ProbeControlFlowAndArtifactTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        self.results_dir = TEST_SCRATCH / "results" / "probes"
        self.model = luna_model()

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def invoke(self, result, extra_args=None):
        args = ["--model", self.model.key, "--yes"]
        if extra_args:
            args.extend(extra_args)
        with patch.object(
            probe_model_route,
            "RESULTS_DIR",
            self.results_dir,
        ), patch.object(
            probe_model_route,
            "load_models",
            return_value={self.model.key: self.model},
        ), patch.object(
            probe_model_route,
            "run_preflight",
            return_value=False,
        ) as preflight, patch.object(
            probe_model_route,
            "execute_run",
            return_value=result,
        ) as execute, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = probe_model_route.main(args)
        artifacts = list(self.results_dir.glob("*/probe.json"))
        return status, artifacts, preflight, execute

    def test_preflight_failure_creates_no_artifact_and_invokes_no_executor(self):
        with patch.object(
            probe_model_route,
            "RESULTS_DIR",
            self.results_dir,
        ), patch.object(
            probe_model_route,
            "load_models",
            return_value={self.model.key: self.model},
        ), patch.object(
            probe_model_route,
            "run_preflight",
            side_effect=SystemExit(2),
        ) as preflight, patch.object(
            probe_model_route,
            "execute_run",
        ) as execute, patch.object(
            probe_model_route,
            "archive_probe",
        ) as archive, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                probe_model_route.main(["--model", self.model.key, "--yes"])
        self.assertNotEqual(0, stopped.exception.code)
        preflight.assert_called_once_with([self.model], preflight_only=False)
        execute.assert_not_called()
        archive.assert_not_called()
        self.assertFalse(self.results_dir.exists())

    def test_declined_confirmation_creates_no_artifact_or_executor_call(self):
        with patch.object(
            probe_model_route,
            "RESULTS_DIR",
            self.results_dir,
        ), patch.object(
            probe_model_route,
            "load_models",
            return_value={self.model.key: self.model},
        ), patch.object(
            probe_model_route,
            "run_preflight",
            return_value=False,
        ), patch.object(
            probe_model_route,
            "execute_run",
        ) as execute, patch.object(
            probe_model_route,
            "archive_probe",
        ) as archive, patch(
            "builtins.input",
            return_value="n",
        ), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = probe_model_route.main(["--model", self.model.key])
        self.assertNotEqual(0, status)
        execute.assert_not_called()
        archive.assert_not_called()
        self.assertFalse(self.results_dir.exists())

    def test_mocked_exact_success_creates_complete_schema_v2_artifact(self):
        status, paths, preflight, execute = self.invoke(fake_result())
        self.assertEqual(0, status)
        self.assertEqual(1, len(paths))
        preflight.assert_called_once_with([self.model], preflight_only=False)
        execute.assert_called_once()
        config = execute.call_args.args[0]
        self.assertEqual(1, config.test_case.turn_limit)
        self.assertEqual("LUNA_PROBE_OK", config.test_case.expected["text"])
        self.assertIn("Do not use tools", config.test_case.prompt)
        self.assertTrue(config.disallowed_tools)
        self.assertNotIn("openai/gpt-5.6-luna", config.test_case.prompt)

        artifact = json.loads(paths[0].read_text())
        self.assertEqual(2, artifact["schema_version"])
        self.assertEqual("daafbench_model_route_probe", artifact["artifact_type"])
        self.assertTrue(artifact["success"])
        self.assertEqual("LUNA_PROBE_OK", artifact["probe"]["expected_text"])
        self.assertTrue(artifact["probe"]["comparison"]["exact_match"])
        self.assertEqual(1, artifact["probe"]["turn_limit"])
        self.assertFalse(artifact["probe"]["tool_work_requested"])
        self.assertEqual("probe-session-123", artifact["session"]["session_id"])
        self.assertIsNone(artifact["session"]["transcript_reference"])
        self.assertEqual(
            "unavailable_executor_did_not_expose_safe_path",
            artifact["session"]["transcript_reference_source"],
        )

        identity = artifact["model_identity"]
        self.assertEqual("gpt-56-luna-chatgpt", identity["benchmark_key"])
        self.assertEqual("gpt-5.6-luna", identity["requested_model_id"])
        self.assertEqual(
            ["gpt-5.6-luna"],
            identity["claude_cli_model_usage_ids"],
        )
        self.assertIsNone(identity["backend_confirmed_model_id"])
        self.assertEqual("cli_observed_match", identity["assessment"])

        provenance = artifact["provenance"]
        self.assertEqual("chatgpt_subscription_shim", provenance["route_type"])
        self.assertEqual("chatgpt", provenance["backend_mode"])
        self.assertTrue(provenance["sanitizer_enabled"])
        self.assertEqual("deployed_default", provenance["sanitizer_condition"])
        rendered = json.dumps(artifact)
        self.assertNotIn("super-secret-extra", rendered)
        self.assertNotIn("super-secret-env-value", rendered)
        self.assertNotIn("credential_extra", rendered)
        self.assertNotIn("full_environment", rendered)

        self.assertEqual("partial", artifact["usage_observed"]["completeness"])
        self.assertEqual(
            "not_separately_billed",
            artifact["actual_billing"]["charge_status"],
        )
        self.assertIsNone(
            artifact["actual_billing"]["actual_marginal_charge_usd"]
        )
        equivalent = artifact["api_equivalent"]
        self.assertIsNone(equivalent["cost_usd"])
        self.assertIsNotNone(equivalent["short_context_uncached_scenario_usd"])
        self.assertIsNotNone(equivalent["long_context_uncached_scenario_usd"])
        self.assertEqual(272_000, equivalent["context_threshold_input_tokens"])
        self.assertTrue(equivalent["not_invoiced"])
        self.assertIn("reasoning is not added", " ".join(equivalent["scenario_assumptions"]))
        self.assertIn("internal alias resolution", artifact["evidence_boundary"])
        self.assertIn("does not prove", artifact["evidence_boundary"])

    def test_response_mismatch_execution_error_and_timeout_preserve_failure_artifacts(self):
        cases = (
            (fake_result(response="NOT_LUNA_PROBE_OK"), "mismatch"),
            (fake_result(error="Execution error: RuntimeError: boom", exit_code=1), "error"),
            (fake_result(response="", error="Timed out after 120s"), "timeout"),
        )
        for result, label in cases:
            with self.subTest(label=label):
                shutil.rmtree(self.results_dir, ignore_errors=True)
                status, paths, _, execute = self.invoke(result)
                self.assertNotEqual(0, status)
                self.assertEqual(1, len(paths))
                execute.assert_called_once()
                artifact = json.loads(paths[0].read_text())
                self.assertEqual(2, artifact["schema_version"])
                self.assertFalse(artifact["success"])
                self.assertEqual(label == "timeout", artifact["execution"]["timed_out"])
                if label == "mismatch":
                    self.assertFalse(artifact["probe"]["comparison"]["exact_match"])
                if label == "error":
                    self.assertIn("RuntimeError", artifact["execution"]["error"])
                if label == "timeout":
                    self.assertIn("Timed out", artifact["execution"]["error"])

    def test_cli_observed_identity_mismatch_is_not_recast_as_backend_confirmation(self):
        result = fake_result(
            observed_ids=["gpt-5.6-sol"],
            backend_confirmed=None,
        )
        status, paths, _, _ = self.invoke(result)
        self.assertNotEqual(0, status)
        artifact = json.loads(paths[0].read_text())
        identity = artifact["model_identity"]
        self.assertEqual("gpt-5.6-luna", identity["requested_model_id"])
        self.assertEqual(["gpt-5.6-sol"], identity["claude_cli_model_usage_ids"])
        self.assertIsNone(identity["backend_confirmed_model_id"])
        self.assertEqual("mismatch", identity["assessment"])
        self.assertIn("not backend-confirmed", identity["evidence_boundary"])

        shutil.rmtree(self.results_dir, ignore_errors=True)
        unavailable_status, unavailable_paths, _, _ = self.invoke(
            fake_result(observed_ids=[])
        )
        self.assertNotEqual(0, unavailable_status)
        unavailable = json.loads(unavailable_paths[0].read_text())
        self.assertEqual(
            "cli_observation_unavailable",
            unavailable["model_identity"]["assessment"],
        )
        self.assertIsNone(
            unavailable["model_identity"]["backend_confirmed_model_id"]
        )


if __name__ == "__main__":
    unittest.main()
