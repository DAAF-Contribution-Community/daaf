"""Focused schema-v2 artifact and runner-preflight regression tests.

All fakes are in-memory. These tests make no backend/model call and create no
benchmark result, checkpoint, sandbox, or temporary directory.
"""

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from benchmarks.harness.artifacts import (
    SCHEMA_VERSION,
    accounting_coverage,
    build_error_artifact,
    build_run_artifact,
    child_model_purity,
    console_billing_label,
    cost_summary,
    error_measurement_defaults,
    model_manifest_entry,
    nullable_mean,
    nullable_total,
    purity_coverage,
)
from benchmarks.harness.models import (
    ModelConfig,
    PricingConfig,
    RouteProvenance,
    RunResult,
    TestCase as BenchmarkCase,
)
from benchmarks.harness.route_provenance import RouteContractError
from benchmarks.scripts import (
    run_dispatch_compliance,
    run_mode_classification,
    run_post_confirmation,
    run_skill_routing,
)


TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch")


def legacy_model():
    return ModelConfig(
        id="claude-sonnet-4-6",
        name="Sonnet 4.6",
        provider="anthropic",
        pricing=PricingConfig(input=3.0, output=15.0, cached_input=0.3),
    )


def luna_model():
    return ModelConfig(
        id="gpt-5.6-luna",
        name="GPT-5.6 Luna (ChatGPT Subscription)",
        key="gpt-56-luna-chatgpt",
        provider="chatgpt-subscription",
        effort_level="high",
        context_window_tokens=370_000,
        actual_billing_treatment="not_separately_billed",
        api_equivalent_pricing={
            "source_url": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
            "accessed_at": "2026-07-15",
        },
    )


def selected_case(case_id):
    return BenchmarkCase(
        id=case_id,
        category="test",
        subcategory="test-mode",
        prompt="No execution in this test.",
        expected={"mode": "data_lookup"},
        golden_checkpoint="benchmarks/golden_checkpoints/not-read-in-preflight.jsonl",
    )


class ArtifactSerializationTests(unittest.TestCase):
    def test_model_and_run_serialization_for_legacy_and_luna(self):
        legacy = legacy_model()
        legacy_manifest = model_manifest_entry(legacy)
        self.assertEqual("sonnet-46", legacy_manifest["key"])
        self.assertEqual("anthropic", legacy_manifest["provider"])
        self.assertEqual(3.0, legacy_manifest["pricing"]["input"])
        self.assertIsNone(legacy_manifest["billing"]["actual_billing_treatment"])

        legacy_result = RunResult(
            "mc-01",
            legacy.id,
            legacy.name,
            0,
            input_tokens=100_000,
            output_tokens=10_000,
            cache_read_tokens=20_000,
            cache_creation_tokens=4_000,
        )
        legacy_record = build_run_artifact(
            legacy,
            legacy_result,
            {"case_id": "mc-01", "rep": 0, "criteria": {}},
        )
        self.assertEqual(SCHEMA_VERSION, legacy_record["schema_version"])
        self.assertAlmostEqual(0.471, legacy_record["computed_cost_usd"], places=12)
        self.assertEqual(100_000, legacy_record["input_tokens"])
        self.assertEqual("not_applicable_legacy_provider", legacy_record["api_equivalent"]["calculation_status"])
        self.assertIn("model_identity", legacy_record)
        self.assertIn("usage_observed", legacy_record)

        luna = luna_model()
        luna_manifest = model_manifest_entry(luna)
        self.assertEqual("gpt-56-luna-chatgpt", luna_manifest["key"])
        self.assertEqual("gpt-5.6-luna", luna_manifest["id"])
        self.assertEqual("GPT-5.6 Luna (ChatGPT Subscription)", luna_manifest["display_name"])
        self.assertEqual("chatgpt-subscription", luna_manifest["provider"])
        self.assertEqual(370_000, luna_manifest["context_window_tokens"])
        self.assertEqual("not_separately_billed", luna_manifest["billing"]["actual_billing_treatment"])

        luna_result = RunResult("mc-01", luna.id, luna.name, 0)
        luna_result.total_cost_usd = None
        luna_result.model_identity.benchmark_key = luna.key
        luna_result.model_identity.requested_model_id = luna.id
        luna_result.model_identity.claude_cli_model_usage_ids = [luna.id]
        luna_result.route_provenance = RouteProvenance(
            route_type="chatgpt_subscription_shim",
            provider="chatgpt-subscription",
            endpoint_origin="http://127.0.0.1:4141",
            backend_mode="chatgpt",
            backend="https://chatgpt.com/backend-api/codex",
            shim_version="1.2.5",
            sanitizer_enabled=True,
        )
        luna_result.input_tokens = 120_000
        luna_result.output_tokens = 18_000
        luna_result.usage_observed.input_tokens = 120_000
        luna_result.usage_observed.output_tokens = 18_000
        luna_result.usage_observed.input_includes_cache_tokens = True
        luna_result.usage_observed.output_includes_reasoning = True
        luna_result.usage_observed.completeness = "partial"

        luna_record = build_run_artifact(
            luna,
            luna_result,
            {"case_id": "mc-01", "rep": 0, "criteria": {}},
        )
        self.assertIsNone(luna_record["computed_cost_usd"])
        self.assertIsNone(luna_record["actual_billing"]["actual_marginal_charge_usd"])
        self.assertEqual("not_separately_billed", luna_record["actual_billing"]["charge_status"])
        self.assertIsNone(luna_record["api_equivalent"]["cost_usd"])
        self.assertAlmostEqual(0.228, luna_record["api_equivalent"]["short_context_uncached_scenario_usd"])
        self.assertEqual([luna.id], luna_record["model_identity"]["claude_cli_model_usage_ids"])
        self.assertIsNone(luna_record["model_identity"]["backend_confirmed_model_id"])
        self.assertTrue(luna_record["provenance"]["sanitizer_enabled"])

    def test_null_aware_totals_means_and_accounting_coverage(self):
        self.assertIsNone(nullable_total([None, None]))
        self.assertIsNone(nullable_mean([None]))
        self.assertEqual(3.5, nullable_total([1.0, None, 2.5]))
        self.assertEqual(1.75, nullable_mean([1.0, None, 2.5]))

        records = [
            {"provider": "anthropic", "computed_cost_usd": 1.25},
            {
                "provider": "chatgpt-subscription",
                "computed_cost_usd": None,
                "api_equivalent": {"cost_usd": 0.20},
            },
            {
                "provider": "chatgpt-subscription",
                "computed_cost_usd": None,
                "api_equivalent": {
                    "cost_usd": None,
                    "short_context_uncached_scenario_usd": 0.15,
                },
            },
            {
                "provider": "chatgpt-subscription",
                "computed_cost_usd": None,
                "api_equivalent": {},
            },
        ]
        expected = {
            "exact": 1,
            "scenario_only": 1,
            "unavailable": 1,
            "legacy_numeric": 1,
        }
        self.assertEqual(expected, accounting_coverage(records))
        summary = cost_summary(records)
        self.assertEqual(1.25, summary["total_cost_usd"])
        self.assertEqual(1.25, summary["avg_cost_usd"])
        self.assertEqual(expected, summary["accounting_coverage"])

    def test_provider_aware_error_defaults_and_legacy_compatibility(self):
        legacy = legacy_model()
        subscription = luna_model()
        self.assertEqual(
            {
                "computed_cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
            },
            error_measurement_defaults(legacy),
        )
        self.assertTrue(all(value is None for value in error_measurement_defaults(subscription).values()))

        legacy_error = build_error_artifact(legacy, "mc-01", 0, "boom")
        self.assertEqual(0.0, legacy_error["computed_cost_usd"])
        self.assertEqual(0, legacy_error["input_tokens"])
        self.assertEqual(SCHEMA_VERSION, legacy_error["schema_version"])

        subscription_error = build_error_artifact(subscription, "mc-01", 0, "boom")
        self.assertIsNone(subscription_error["computed_cost_usd"])
        self.assertIsNone(subscription_error["input_tokens"])
        self.assertIsNone(subscription_error["output_tokens"])
        self.assertIsNone(subscription_error["actual_billing"]["actual_marginal_charge_usd"])
        self.assertEqual("unavailable", subscription_error["usage_observed"]["completeness"])

    def test_console_billing_labels_never_call_included_use_free_or_zero_cost(self):
        legacy = {"provider": "anthropic", "computed_cost_usd": 0.125}
        self.assertEqual("$0.125", console_billing_label(legacy))

        unavailable_subscription = {
            "provider": "chatgpt-subscription",
            "computed_cost_usd": None,
            "api_equivalent": {},
        }
        unavailable_label = console_billing_label(unavailable_subscription)
        self.assertEqual(
            "included subscription capacity; marginal charge unavailable",
            unavailable_label,
        )
        self.assertNotIn("free", unavailable_label.lower())
        self.assertNotEqual("$0.000", unavailable_label)

        scenario_subscription = {
            "provider": "chatgpt-subscription",
            "computed_cost_usd": None,
            "api_equivalent": {
                "short_context_uncached_scenario_usd": 0.228,
                "long_context_uncached_scenario_usd": 0.402,
            },
        }
        scenario_label = console_billing_label(scenario_subscription)
        self.assertIn("included subscription capacity", scenario_label)
        self.assertIn("API-equivalent scenario $0.228-$0.402", scenario_label)
        self.assertIn("not invoiced", scenario_label)
        self.assertNotIn("free", scenario_label.lower())

        zero_scenario_label = console_billing_label({
            "provider": "chatgpt-subscription",
            "computed_cost_usd": None,
            "api_equivalent": {
                "short_context_uncached_scenario_usd": 0.0,
                "long_context_uncached_scenario_usd": 0.0,
            },
        })
        self.assertNotIn("$0", zero_scenario_label)
        self.assertIn("zero observed usage", zero_scenario_label)


class ChildModelPurityTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        self.purity_dir = TEST_SCRATCH / "purity"
        self.purity_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def _transcript(self, name, records):
        path = self.purity_dir / name
        path.write_text("".join(json.dumps(record) + "\n" for record in records))
        return path

    def _assistant(self, model_id):
        return {
            "type": "assistant",
            "message": {"model": model_id, "content": []},
        }

    def test_verified_when_every_observed_child_id_exactly_matches_requested(self):
        first = self._transcript(
            "agent-one.jsonl",
            [self._assistant("gpt-5.6-luna"), self._assistant("gpt-5.6-luna")],
        )
        second = self._transcript(
            "agent-two.jsonl",
            [{"type": "user", "message": {"content": "prompt"}}, self._assistant("gpt-5.6-luna")],
        )
        evidence = child_model_purity([first, second], "gpt-5.6-luna")

        self.assertEqual("verified", evidence["purity_status"])
        self.assertEqual(["gpt-5.6-luna"], evidence["observed_child_model_ids_raw"])
        self.assertEqual(
            evidence["observed_child_model_ids_raw"],
            evidence["comparison_child_model_ids"],
        )
        self.assertFalse(evidence["normalization_applied"])
        self.assertEqual("exact_string_equality_no_alias_normalization", evidence["comparison_rule"])
        self.assertEqual("child_transcript_assistant_message.model", evidence["evidence_source"])
        self.assertIn("not backend-confirmed", evidence["evidence_boundary"])
        self.assertIsNone(evidence["incompleteness_reason"])

    def test_failed_when_any_observed_child_id_differs(self):
        transcript = self._transcript(
            "agent-mixed.jsonl",
            [self._assistant("gpt-5.6-luna"), self._assistant("gpt-5.6-sol")],
        )
        evidence = child_model_purity([transcript], "gpt-5.6-luna")

        self.assertEqual("failed", evidence["purity_status"])
        self.assertEqual(
            ["gpt-5.6-luna", "gpt-5.6-sol"],
            evidence["observed_child_model_ids_raw"],
        )
        self.assertIsNone(evidence["incompleteness_reason"])

    def test_unverifiable_when_child_transcript_is_missing(self):
        evidence = child_model_purity([], "gpt-5.6-luna")

        self.assertEqual("unverifiable", evidence["purity_status"])
        self.assertEqual("no_child_transcript_exists", evidence["incompleteness_reason"])
        self.assertEqual([], evidence["observed_child_model_ids_raw"])
        self.assertEqual(0, evidence["child_transcript_count"])

    def test_unverifiable_when_transcript_exposes_no_model_field(self):
        transcript = self._transcript(
            "agent-no-model.jsonl",
            [
                {"type": "user", "message": {"content": "prompt"}},
                {"type": "assistant", "message": {"content": []}},
            ],
        )
        evidence = child_model_purity([transcript], "gpt-5.6-luna")

        self.assertEqual("unverifiable", evidence["purity_status"])
        self.assertEqual(
            "child_transcripts_expose_no_model_id",
            evidence["incompleteness_reason"],
        )
        self.assertEqual(1, evidence["child_transcript_count"])

    def test_purity_coverage_preserves_failed_and_unverifiable_states(self):
        records = [
            {"child_model_purity": {"purity_status": "verified"}},
            {"child_model_purity": {"purity_status": "failed"}},
            {"child_model_purity": {"purity_status": "unverifiable"}},
            {},
        ]
        self.assertEqual(
            {"verified": 1, "failed": 1, "unverifiable": 2},
            purity_coverage(records),
        )


class RunnerPreflightTests(unittest.TestCase):
    def _invoke_preflight_only(self, module, case_id):
        model = luna_model()
        case = selected_case(case_id)
        events = []

        def load_selected_models(*args, **kwargs):
            events.append("models_loaded")
            return {model.key: model}

        def select_models(*args, **kwargs):
            events.append("models_selected")
            return [model]

        def load_selected_cases(*args, **kwargs):
            events.append("cases_loaded")
            return [case]

        def preflight_selected_models(*args, **kwargs):
            events.append("preflight")
            return {model.key: object()}

        argv = [
            str(module.__file__),
            "--provider", "chatgpt-subscription",
            "--models", "gpt-56-luna-chatgpt",
            "--test-id", case_id,
            "--reps", "1",
            "--sequential",
            "--preflight-only",
        ]
        patchers = {
            "load_models": patch.object(
                module, "load_models", side_effect=load_selected_models
            ),
            "select_models": patch.object(
                module, "filter_models", side_effect=select_models
            ),
            "load_cases": patch.object(
                module, "load_test_cases", side_effect=load_selected_cases
            ),
            "preflight": patch(
                "benchmarks.harness.artifacts.preflight_models",
                side_effect=preflight_selected_models,
            ),
            "execute": patch.object(module, "execute_run"),
            "run_one": patch.object(module, "run_one"),
            "archive": patch.object(module, "archive_results"),
            "estimate": patch.object(module, "estimate_batch_cost"),
            "mkdir": patch.object(module.Path, "mkdir"),
            "popen": patch.object(module.subprocess, "Popen"),
            "process_run": patch.object(module.subprocess, "run"),
            "run_range": patch.object(module, "range", create=True),
            "argv": patch.object(sys, "argv", argv),
        }
        if module is not run_mode_classification:
            patchers["checkpoint"] = patch.object(module, "get_checkpoint_line_count")
            patchers["cleanup"] = patch.object(module, "cleanup_sandbox")
        if module is run_dispatch_compliance:
            patchers["fixture_restore"] = patch.object(module, "restore_fixtures")
            patchers["fixture_prepare"] = patch.object(module, "prepare_fixtures")
            patchers["fixture_check"] = patch.object(module, "check_fixture_contamination")

        mocks = {}
        try:
            for name, patcher in patchers.items():
                mocks[name] = patcher.start()
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                module.main()
        finally:
            for patcher in reversed(list(patchers.values())):
                patcher.stop()

        mocks["preflight"].assert_called_once()
        selected = mocks["preflight"].call_args.args[0]
        self.assertEqual([model], list(selected))
        self.assertEqual(
            ["models_loaded", "models_selected", "cases_loaded", "preflight"],
            events,
        )
        for name in (
            "execute", "run_one", "archive", "estimate", "mkdir", "popen",
            "process_run", "run_range", "checkpoint", "cleanup",
            "fixture_restore", "fixture_prepare", "fixture_check",
        ):
            if name in mocks:
                mocks[name].assert_not_called()

    def test_mode_classification_preflight_only_has_no_execution_or_artifacts(self):
        self._invoke_preflight_only(run_mode_classification, "mc-01")

    def test_post_confirmation_preflight_only_has_no_execution_or_artifacts(self):
        self._invoke_preflight_only(run_post_confirmation, "pc-01")

    def test_dispatch_compliance_preflight_only_has_no_downstream_actions(self):
        self._invoke_preflight_only(run_dispatch_compliance, "dc-01")

    def test_skill_routing_preflight_only_has_no_downstream_actions(self):
        self._invoke_preflight_only(run_skill_routing, "sr-01")

    def test_preflight_failure_exits_nonzero_and_creates_no_artifacts(self):
        for module, case_id in (
            (run_mode_classification, "mc-01"),
            (run_post_confirmation, "pc-01"),
            (run_dispatch_compliance, "dc-01"),
            (run_skill_routing, "sr-01"),
        ):
            with self.subTest(module=module.__name__):
                model = luna_model()
                argv = [
                    str(module.__file__),
                    "--provider", "chatgpt-subscription",
                    "--models", model.key,
                    "--test-id", case_id,
                    "--reps", "1",
                    "--preflight-only",
                ]
                patchers = {
                    "load": patch.object(module, "load_models", return_value={model.key: model}),
                    "cases": patch.object(
                        module, "load_test_cases", return_value=[selected_case(case_id)]
                    ),
                    "preflight": patch(
                        "benchmarks.harness.artifacts.preflight_models",
                        side_effect=RouteContractError("route mismatch"),
                    ),
                    "execute": patch.object(module, "execute_run"),
                    "archive": patch.object(module, "archive_results"),
                    "estimate": patch.object(module, "estimate_batch_cost"),
                    "mkdir": patch.object(module.Path, "mkdir"),
                    "popen": patch.object(module.subprocess, "Popen"),
                    "argv": patch.object(sys, "argv", argv),
                }
                if module is run_dispatch_compliance:
                    patchers["fixture_restore"] = patch.object(module, "restore_fixtures")
                mocks = {}
                try:
                    for name, patcher in patchers.items():
                        mocks[name] = patcher.start()
                    with self.assertRaises(SystemExit) as stopped:
                        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                            module.main()
                finally:
                    for patcher in reversed(list(patchers.values())):
                        patcher.stop()

                self.assertNotEqual(0, stopped.exception.code)
                mocks["preflight"].assert_called_once()
                for name in ("execute", "archive", "estimate", "mkdir", "popen", "fixture_restore"):
                    if name in mocks:
                        mocks[name].assert_not_called()

    def test_all_runner_help_paths_are_network_free(self):
        for module in (
            run_mode_classification,
            run_post_confirmation,
            run_dispatch_compliance,
            run_skill_routing,
        ):
            with self.subTest(module=module.__name__):
                with patch("benchmarks.harness.route_provenance.urlopen") as network, \
                        patch.object(module, "load_models") as load, \
                        patch.object(module, "execute_run") as execute, \
                        patch.object(sys, "argv", [str(module.__file__), "--help"]):
                    with self.assertRaises(SystemExit) as stopped:
                        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                            module.main()
                self.assertEqual(0, stopped.exception.code)
                network.assert_not_called()
                load.assert_not_called()
                execute.assert_not_called()

    def test_runner_error_records_keep_legacy_numeric_and_flat_field_behavior(self):
        records = [
            run_mode_classification._error_result(
                selected_case("mc-01"), legacy_model(), 0, "boom"
            ),
            run_post_confirmation._error_result(
                selected_case("pc-01"), legacy_model(), 0, "boom"
            ),
            run_dispatch_compliance._error_result(
                selected_case("dc-01"), legacy_model(), 0, "boom"
            ),
            run_skill_routing._error_result(
                selected_case("sr-01"), legacy_model(), 0, "boom"
            ),
        ]
        historical_flat_fields = {
            "case_id", "model", "model_id", "provider", "effort_level", "rep",
            "session_id", "turns", "computed_cost_usd", "input_tokens",
            "output_tokens", "cache_read_tokens", "cache_creation_tokens",
            "duration_s", "error", "timed_out", "criteria", "tool_failures",
        }
        for record in records:
            self.assertEqual(0.0, record["computed_cost_usd"])
            self.assertEqual(0, record["input_tokens"])
            self.assertEqual(0, record["output_tokens"])
            self.assertEqual("anthropic", record["provider"])
            self.assertEqual(SCHEMA_VERSION, record["schema_version"])
            self.assertTrue(historical_flat_fields.issubset(record))

    def test_new_runner_subscription_errors_never_fabricate_zero_usage_or_cost(self):
        for module, case_id in (
            (run_dispatch_compliance, "dc-01"),
            (run_skill_routing, "sr-01"),
        ):
            with self.subTest(module=module.__name__):
                record = module._error_result(
                    selected_case(case_id), luna_model(), 0, "boom"
                )
                for field in (
                    "computed_cost_usd", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_creation_tokens",
                ):
                    self.assertIsNone(record[field])
                self.assertIsNone(
                    record["actual_billing"]["actual_marginal_charge_usd"]
                )
                self.assertEqual(SCHEMA_VERSION, record["schema_version"])


class RunnerArchiveTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        TEST_SCRATCH.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def test_dispatch_summary_and_runs_preserve_all_purity_states(self):
        model = luna_model()
        case = selected_case("dc-01")
        records = []
        for rep, status in enumerate(("verified", "failed", "unverifiable")):
            record = run_dispatch_compliance._error_result(case, model, rep, "boom")
            record["child_model_purity"] = {
                **record["child_model_purity"],
                "purity_status": status,
                "incompleteness_reason": (
                    "no_child_transcript_exists" if status == "unverifiable" else None
                ),
            }
            records.append(record)

        args = SimpleNamespace(
            reps=3,
            sequential=True,
            delay=0,
            timeout=300,
            test_id="dc-01",
            models=model.key,
        )
        with patch.object(run_dispatch_compliance, "BASE_DIR", TEST_SCRATCH), \
                patch.object(run_dispatch_compliance, "get_git_sha", return_value="test-sha"):
            output_dir = run_dispatch_compliance.archive_results(
                records, [model], [case], args, 1.0
            )

        summary = json.loads((output_dir / "summary.json").read_text())
        self.assertEqual(SCHEMA_VERSION, summary["schema_version"])
        self.assertEqual(
            {"verified": 1, "failed": 1, "unverifiable": 1},
            summary["purity_coverage"],
        )
        self.assertEqual(
            summary["purity_coverage"],
            summary["by_model"][model.name]["purity_coverage"],
        )
        run_payloads = [
            json.loads(path.read_text())
            for path in sorted((output_dir / "runs").glob("*/result.json"))
        ]
        self.assertEqual(
            {"verified", "failed", "unverifiable"},
            {
                payload["child_model_purity"]["purity_status"]
                for payload in run_payloads
            },
        )
        self.assertTrue(all(payload["schema_version"] == SCHEMA_VERSION for payload in run_payloads))
        self.assertTrue(
            all(payload["criteria"] == run_payloads[0]["criteria"] for payload in run_payloads)
        )


if __name__ == "__main__":
    unittest.main()
