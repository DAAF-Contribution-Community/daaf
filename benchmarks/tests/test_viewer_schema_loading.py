"""Focused deterministic tests for schema-v1/v2 viewer data loading.

Fixtures are created only beneath ``benchmarks/.test_scratch`` and removed after
use. The HTML template is not opened: this module exercises discovery, loading,
payload assembly, and precomputed cost-compatibility metadata only.
"""

import io
import json
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from benchmarks.scripts import generate_results_viewer_v2 as viewer


TEST_SCRATCH = Path("/daaf/benchmarks/.test_scratch")


class ViewerSchemaLoadingTests(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)
        self.results_dir = TEST_SCRATCH / "results"
        self.results_dir.mkdir(parents=True)
        self._write_legacy_set()
        self._write_subscription_set()
        self._write_non_result_containers()

    def tearDown(self):
        shutil.rmtree(TEST_SCRATCH, ignore_errors=True)

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_legacy_set(self):
        root = self.results_dir / "20260101_010101"
        self._write_json(root / "manifest.json", {
            "daaf_git_sha": "a" * 40,
            "config": {"reps": 1, "parallel": False},
            "models": [{
                "id": "claude-sonnet-4-6",
                "name": "Legacy Model",
                "provider": "anthropic",
            }],
        })
        self._write_json(root / "summary.json", {
            "total_runs": 1,
            "errored_runs": 0,
            "total_cost_usd": 0,
            "wall_time_s": 2,
            "by_model": {
                "Legacy Model": {
                    "avg_cost_usd": 0,
                    "criteria": {
                        "orchestrator_skill_loaded": {
                            "passed": 1, "total": 1, "rate": 1.0,
                        },
                        "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                    },
                },
            },
        })
        self._write_json(root / "runs" / "legacy_0" / "result.json", {
            "case_id": "mc-legacy",
            "model": "Legacy Model",
            "model_id": "claude-sonnet-4-6",
            "provider": "anthropic",
            "rep": 0,
            "turns": 1,
            "computed_cost_usd": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "duration_s": 1.0,
            "timed_out": False,
            "criteria": {
                "orchestrator_skill_loaded": {"passed": True},
            },
        })

    def _write_subscription_set(self):
        root = self.results_dir / "20260715_120000"
        self._write_json(root / "manifest.json", {
            "schema_version": 2,
            "daaf_git_sha": "b" * 40,
            "raw_environment": {"AUTH_TOKEN": "manifest-secret"},
            "models": [{
                "key": "gpt-56-luna-chatgpt",
                "id": "gpt-5.6-luna",
                "name": "Luna Subscription",
                "display_name": "Luna Subscription",
                "provider": "chatgpt-subscription",
                "effort_level": "high",
                "context_window_tokens": 370_000,
                "billing": {
                    "actual_billing_treatment": "not_separately_billed",
                    "api_equivalent_pricing": {"raw_secret": "pricing-secret"},
                },
                "env_overrides": {"AUTH_TOKEN": "model-secret"},
            }],
        })
        self._write_json(root / "summary.json", {
            "schema_version": 2,
            "total_runs": 1,
            "errored_runs": 0,
            "total_cost_usd": None,
            "wall_time_s": 3,
            "accounting_coverage": {
                "exact": 0,
                "scenario_only": 1,
                "unavailable": 0,
                "legacy_numeric": 0,
                "secret_count": 999,
            },
            "purity_coverage": {
                "verified": 1,
                "failed": 0,
                "unverifiable": 0,
                "raw_child_payload": "summary-secret",
            },
            "by_model": {
                "Luna Subscription": {
                    "criteria": {
                        "orchestrator_skill_loaded": {
                            "passed": 1, "total": 1, "rate": 1.0,
                        },
                        "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                    },
                },
            },
        })
        self._write_json(root / "runs" / "subscription_0" / "result.json", {
            "schema_version": 2,
            "case_id": "mc-subscription",
            "model": "Luna Subscription",
            "model_id": "gpt-5.6-luna",
            "provider": "chatgpt-subscription",
            "rep": 0,
            "turns": 1,
            "computed_cost_usd": None,
            "duration_s": 1.5,
            "timed_out": False,
            "criteria": {
                "orchestrator_skill_loaded": {"passed": True},
            },
            "provenance": {
                "route_type": "chatgpt_subscription_shim",
                "provider": "chatgpt-subscription",
                "endpoint_origin": "http://127.0.0.1:4141",
                "backend_mode": "chatgpt",
                "backend": "https://chatgpt.com/backend-api/codex",
                "shim_version": "1.2.5",
                "sanitizer_enabled": True,
                "sanitizer_condition": "deployed_default",
                "auth_store_readable": True,
                "reasoning_effort": "high",
                "text_verbosity": "high",
                "captured_at": "2026-07-15T12:00:00+00:00",
                "raw_health_payload": {"access_token": "health-secret"},
            },
            "model_identity": {
                "benchmark_key": "gpt-56-luna-chatgpt",
                "requested_model_id": "gpt-5.6-luna",
                "claude_cli_model_usage_ids": ["gpt-5.6-luna"],
                "backend_confirmed_model_id": None,
                "executor_raw_json": {"secret": "identity-secret"},
            },
            "usage_observed": {
                "input_tokens": 123,
                "input_semantics": "shim_reported_total_input_cache_breakdown_unavailable",
                "input_includes_cache_tokens": True,
                "output_tokens": 0,
                "output_includes_reasoning": True,
                "cache_read_tokens": None,
                "cache_write_tokens": None,
                "reasoning_tokens": None,
                "max_request_input_tokens": None,
                "pricing_context_tier": None,
                "source": "claude_cli.modelUsage",
                "completeness": "partial",
                "incompleteness_reasons": ["cache_read_tokens_unavailable"],
                "cli_model_usage": {"gpt-5.6-luna": {"raw": "usage-secret"}},
            },
            "actual_billing": {
                "access_type": "chatgpt_subscription",
                "charge_status": "not_separately_billed",
                "actual_marginal_charge_usd": None,
                "credential": "billing-secret",
            },
            "api_equivalent": {
                "cost_usd": None,
                "calculation_status": "scenario_only",
                "short_context_uncached_scenario_usd": 0,
                "long_context_uncached_scenario_usd": 0.0009,
                "scenario_assumptions": ["uncached counterfactual"],
                "incompleteness_reasons": ["request_tier_unavailable"],
                "price_source_url": "https://developers.openai.com/api/docs/models/gpt-5.6-luna",
                "price_schedule_accessed_at": "2026-07-15",
                "currency": "USD",
                "context_threshold_input_tokens": 272_000,
                "context_tier": None,
                "not_invoiced": True,
                "raw_pricing_response": "api-secret",
            },
            "subscription_capacity": {
                "before": None,
                "after": None,
                "delta_observed": 0,
                "credits_calculated": None,
                "credit_usd_value": None,
                "raw_account": "capacity-secret",
            },
            "child_model_purity": {
                "requested_child_model_id": "gpt-5.6-luna",
                "observed_child_model_ids_raw": ["gpt-5.6-luna"],
                "comparison_child_model_ids": ["gpt-5.6-luna"],
                "normalization_applied": False,
                "comparison_rule": "exact_string_equality_no_alias_normalization",
                "purity_status": "verified",
                "evidence_source": "child_transcript_assistant_message.model",
                "evidence_boundary": "CLI-observed; not backend-confirmed",
                "child_transcript_count": 1,
                "readable_child_transcript_count": 1,
                "incompleteness_reason": None,
                "raw_transcript": "purity-secret",
            },
            "raw_json": {"AUTH_TOKEN": "root-secret"},
            "full_environment": {"SECRET": "environment-secret"},
        })
        malformed = root / "runs" / "zz_malformed" / "result.json"
        malformed.parent.mkdir(parents=True)
        malformed.write_text("{not-json", encoding="utf-8")

    def _write_non_result_containers(self):
        self._write_json(
            self.results_dir / "probes" / "probe-a" / "probe.json",
            {"artifact_type": "daafbench_model_route_probe", "schema_version": 2},
        )
        (self.results_dir / "not_a_result_set").mkdir()
        malformed = self.results_dir / "malformed_set" / "summary.json"
        malformed.parent.mkdir()
        malformed.write_text("{broken", encoding="utf-8")

    def _load(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result_sets = viewer.load_result_sets(str(self.results_dir))
            runs, anth_tokens = viewer.load_runs(
                str(self.results_dir), result_sets, cases={}
            )
        return result_sets, runs, anth_tokens, stderr.getvalue()

    def test_schema_v1_and_absent_version_remain_compatible(self):
        result_sets, runs, anth_tokens, warnings = self._load()
        legacy_set = next(rs for rs in result_sets if rs["timestamp"] == "20260101_010101")
        legacy_run = next(run for run in runs if run["result_set"] == "20260101_010101")

        self.assertEqual(1, legacy_set["schema_version"])
        self.assertEqual("default_absent_version", legacy_set["schema_version_source"])
        self.assertEqual("legacy_schema_v1", legacy_set["schema_classification"])
        self.assertTrue(legacy_set["legacy_schema"])
        self.assertEqual(0, legacy_set["total_cost_usd"])
        self.assertEqual(
            0, legacy_set["model_accounting"]["Legacy Model"]["avg_cost_usd"]
        )
        self.assertEqual(0, legacy_run["computed_cost_usd"])
        self.assertTrue(legacy_run["billing_grade_cost_eligible"])
        self.assertEqual("perfect", legacy_run["grade"])
        self.assertEqual(1, anth_tokens["Legacy Model"]["n"])
        self.assertIn("Ignoring reserved non-phase results container: probes", warnings)

    def test_missing_legacy_cost_remains_null_instead_of_zero(self):
        root = self.results_dir / "20260102_010101"
        self._write_json(root / "summary.json", {
            "total_runs": 0,
            "errored_runs": 0,
            "by_model": {},
        })
        with redirect_stderr(io.StringIO()):
            loaded = viewer.load_result_sets(
                str(self.results_dir), filter_timestamps=[root.name]
            )
        self.assertEqual(1, len(loaded))
        self.assertEqual(1, loaded[0]["schema_version"])
        self.assertIsNone(loaded[0]["total_cost_usd"])
        self.assertIsNone(loaded[0]["wall_time_s"])

    def test_schema_precedence_and_run_fallback_are_explicit(self):
        self.assertEqual(1, viewer.detect_schema_version({}, {}, {}))
        self.assertEqual(
            1,
            viewer.detect_schema_version(
                {"schema_version": 1},
                {"schema_version": 2},
                {"schema_version": 3},
            ),
        )
        self.assertEqual(
            2,
            viewer.detect_schema_version({}, {"schema_version": 2}, {"schema_version": 3}),
        )
        self.assertEqual(3, viewer.detect_schema_version({}, {}, {"schema_version": 3}))

    def test_schema_v2_nested_fields_preserve_nulls_and_explicit_zero(self):
        result_sets, runs, _, _ = self._load()
        subscription_set = next(
            rs for rs in result_sets if rs["timestamp"] == "20260715_120000"
        )
        subscription_run = next(
            run for run in runs if run["result_set"] == "20260715_120000"
        )

        self.assertEqual(2, subscription_set["schema_version"])
        self.assertEqual("manifest", subscription_set["schema_version_source"])
        self.assertIsNone(subscription_set["total_cost_usd"])
        self.assertIsNone(
            subscription_set["model_accounting"]["Luna Subscription"]["avg_cost_usd"]
        )
        self.assertEqual(
            {"verified": 1, "failed": 0, "unverifiable": 0},
            subscription_set["purity_coverage"],
        )
        self.assertFalse(subscription_set["billing_grade_cost_eligible"])

        self.assertEqual("chatgpt-subscription", subscription_run["provider"])
        self.assertEqual("chatgpt_subscription_shim", subscription_run["route_type"])
        self.assertIsNone(subscription_run["computed_cost_usd"])
        usage = subscription_run["usage_observed"]
        self.assertEqual(0, usage["output_tokens"])
        self.assertIsNone(usage["cache_read_tokens"])
        self.assertIsNone(usage["reasoning_tokens"])
        self.assertEqual("partial", usage["completeness"])
        self.assertEqual("claude_cli.modelUsage", usage["source"])

        actual = subscription_run["actual_billing"]
        equivalent = subscription_run["api_equivalent"]
        capacity = subscription_run["subscription_capacity"]
        self.assertEqual("not_separately_billed", actual["charge_status"])
        self.assertIsNone(actual["actual_marginal_charge_usd"])
        self.assertIsNone(equivalent["cost_usd"])
        self.assertEqual(0, equivalent["short_context_uncached_scenario_usd"])
        self.assertTrue(equivalent["not_invoiced"])
        self.assertEqual(0, capacity["delta_observed"])
        self.assertEqual("verified", subscription_run["child_model_purity"]["purity_status"])
        self.assertIn(
            "not backend-confirmed",
            subscription_run["child_model_purity"]["evidence_boundary"],
        )
        self.assertIsNone(
            subscription_run["model_identity"]["backend_confirmed_model_id"]
        )

    def test_secret_and_raw_extras_do_not_enter_embedded_payload(self):
        result_sets, runs, _, _ = self._load()
        bundle = viewer.build_data_bundle(
            result_sets,
            cases={},
            runs=runs,
            transcripts={},
            subagent_transcripts={},
            inline_transcripts=False,
        )
        rendered = json.dumps(bundle)
        for forbidden in (
            "manifest-secret", "pricing-secret", "model-secret", "summary-secret",
            "health-secret", "identity-secret", "usage-secret", "billing-secret",
            "api-secret", "capacity-secret", "purity-secret", "root-secret",
            "environment-secret", "raw_health_payload", "raw_json",
            "full_environment", "executor_raw_json",
        ):
            self.assertNotIn(forbidden, rendered)
        subscription_run = next(
            run for run in bundle["runs"]
            if run["provider"] == "chatgpt-subscription"
        )
        self.assertNotIn("cli_model_usage", subscription_run["usage_observed"])
        self.assertEqual(2, bundle["embedded_schema_contract_version"])
        self.assertEqual("3.2.0", bundle["generator_version"])

    def test_subscription_cost_incompatibility_retains_behavioral_scores(self):
        result_sets, runs, anth_tokens, _ = self._load()
        precomputed = viewer.build_precomputed(
            result_sets,
            cases={},
            runs=runs,
            generation_params={"fixture": True},
            model_pricing={
                "Legacy Model": {
                    "input_per_million": 3.0,
                    "output_per_million": 15.0,
                    "cached_input_per_million": 0.3,
                },
                # An accidental published-price entry must not make the
                # subscription condition compatible with billing-grade views.
                "Luna Subscription": {
                    "input_per_million": 1.0,
                    "output_per_million": 6.0,
                    "cached_input_per_million": 0.1,
                },
            },
            anth_token_totals=anth_tokens,
            reconciliation=None,
        )

        self.assertIn("Luna Subscription", precomputed["composite"])
        cost_models = {entry["key"] for entry in precomputed["cost"]["models"]}
        self.assertNotIn("Luna Subscription", cost_models)
        omitted = next(
            entry for entry in precomputed["cost"]["omitted_models"]
            if entry["model"] == "Luna Subscription"
        )
        self.assertTrue(omitted["behavioral_scores_retained"])
        self.assertEqual(
            "subscription_access_api_equivalent_is_counterfactual_not_invoiced",
            omitted["reason"],
        )

    def test_probe_and_malformed_directories_are_skipped_deterministically(self):
        result_sets, runs, _, warnings = self._load()
        self.assertEqual(
            ["20260101_010101", "20260715_120000"],
            [rs["timestamp"] for rs in result_sets],
        )
        self.assertEqual(2, len(runs))
        self.assertIn("No summary.json", warnings)
        self.assertIn("Could not read summary.json", warnings)
        self.assertIn("Could not read result.json", warnings)
        self.assertNotIn("probes", [rs["timestamp"] for rs in result_sets])

    def test_generator_help_is_side_effect_free(self):
        with patch.object(sys, "argv", [str(Path(viewer.__file__)), "--help"]), \
                patch.object(viewer, "resolve_paths") as resolve, \
                patch.object(viewer, "load_result_sets") as load, \
                patch.object(viewer.os, "makedirs") as makedirs, \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                viewer.main()
        self.assertEqual(0, stopped.exception.code)
        resolve.assert_not_called()
        load.assert_not_called()
        makedirs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
