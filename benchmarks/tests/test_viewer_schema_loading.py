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

    def _write_timeout_set(self):
        """A dedicated Phase-1 set exercising the v3.3.0 timeout-exclusion
        chokepoint. Two Anthropic models share case ``mc-a``: the reference
        ``Opus 4.8`` (mean duration 2.0s over 2 completed runs) and
        ``Timeout Model`` (mean 5.0s over 2 completed runs). ``Timeout Model``
        also carries two ``timed_out: True`` runs that must vanish everywhere:
        a would-have-failed ``mc-a`` run (whose 99s latency and failing
        criteria would skew duration/rates if kept) and the ONLY run for
        ``mc-degenerate`` (an all-timed-out (case, model) cell that must not
        crash and must leave no per_case entry)."""
        root = self.results_dir / "20260720_000000"
        self._write_json(root / "manifest.json", {
            "daaf_git_sha": "c" * 40,
            "config": {"reps": 1, "parallel": False},
            "models": [
                {"id": "opus-4-8", "name": "Opus 4.8", "provider": "anthropic"},
                {"id": "timeout-model", "name": "Timeout Model",
                 "provider": "anthropic"},
            ],
        })
        self._write_json(root / "summary.json", {
            "total_runs": 6,
            "errored_runs": 0,
            "total_cost_usd": 0,
            "wall_time_s": 10,
            "by_model": {
                "Opus 4.8": {"criteria": {
                    "orchestrator_skill_loaded": {"passed": 2, "total": 2, "rate": 1.0},
                    "all_criteria": {"passed": 2, "total": 2, "rate": 1.0},
                }},
                "Timeout Model": {"criteria": {
                    "orchestrator_skill_loaded": {"passed": 2, "total": 4, "rate": 0.5},
                    "all_criteria": {"passed": 2, "total": 4, "rate": 0.5},
                }},
            },
        })

        def _run(run_dir, model, model_id, case_id, duration, timed_out,
                 passed, inp, outp):
            self._write_json(root / "runs" / run_dir / "result.json", {
                "case_id": case_id,
                "model": model,
                "model_id": model_id,
                "provider": "anthropic",
                "rep": 0,
                "turns": 1,
                "computed_cost_usd": 0,
                "input_tokens": inp,
                "output_tokens": outp,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "duration_s": duration,
                "timed_out": timed_out,
                "criteria": {"orchestrator_skill_loaded": {"passed": passed}},
            })

        # Reference model: 2 completed runs, mean duration 2.0s
        _run("opus_0", "Opus 4.8", "opus-4-8", "mc-a", 2.0, False, True, 100, 10)
        _run("opus_1", "Opus 4.8", "opus-4-8", "mc-a", 2.0, False, True, 100, 10)
        # Timeout Model: 2 completed runs, mean duration 5.0s
        _run("tm_ok_0", "Timeout Model", "timeout-model", "mc-a", 4.0, False, True, 200, 20)
        _run("tm_ok_1", "Timeout Model", "timeout-model", "mc-a", 6.0, False, True, 200, 20)
        # Timed-out, would-have-failed mc-a run (skews rates/duration if kept)
        _run("tm_timeout", "Timeout Model", "timeout-model", "mc-a", 99.0, True, False, 999, 999)
        # Timed-out ONLY run for mc-degenerate (all-timed-out cell)
        _run("tm_degenerate", "Timeout Model", "timeout-model", "mc-degenerate", 99.0, True, False, 999, 999)

    def _write_phase_timeout_set(self):
        """A per-PHASE analogue of the per-case degeneracy in
        ``_write_timeout_set``. Two Anthropic models span two phases. In the
        ``mode_classification`` set both models complete (``Phase Gap Model``
        is deliberately 1-of-2 perfect, so its sole surviving composite
        component has a non-1.0 rate). In the ``post_confirmation`` set only
        ``Coverage Model`` completes: ``Phase Gap Model``'s ONLY
        post_confirmation run is ``timed_out: True``. After the load-time
        timeout exclusion, ``Phase Gap Model`` has NO runs for the
        post_confirmation eval group, so that entire composite component drops
        for it — while the group itself survives because ``Coverage Model``
        keeps it alive. This is the headline degeneracy the design claims but
        the per-case ``_write_timeout_set`` never exercises: a model whose
        WHOLE phase timed out drops that component and still renders via the
        composite ``partial`` idiom (the group id absent from
        ``components_present``, listed in ``components_missing``,
        ``partial_data`` flagged)."""
        def _phase_run(root, run_dir, model, model_id, case_id, marker,
                       duration, timed_out, passed):
            self._write_json(root / "runs" / run_dir / "result.json", {
                "case_id": case_id,
                "model": model,
                "model_id": model_id,
                "provider": "anthropic",
                "rep": 0,
                "turns": 1,
                "computed_cost_usd": 0,
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "duration_s": duration,
                "timed_out": timed_out,
                "criteria": {marker: {"passed": passed}},
            })

        # --- Phase 1 (mode_classification) set: both models complete; Phase
        # Gap Model is 1-of-2 perfect so its retained component rate is 0.5 ---
        p1 = self.results_dir / "20260721_030303"
        self._write_json(p1 / "manifest.json", {
            "daaf_git_sha": "d" * 40,
            "config": {"reps": 1, "parallel": False},
            "models": [
                {"id": "coverage-model", "name": "Coverage Model",
                 "provider": "anthropic"},
                {"id": "phase-gap-model", "name": "Phase Gap Model",
                 "provider": "anthropic"},
            ],
        })
        self._write_json(p1 / "summary.json", {
            "total_runs": 3,
            "errored_runs": 0,
            "total_cost_usd": 0,
            "wall_time_s": 5,
            "by_model": {
                "Coverage Model": {"criteria": {
                    "orchestrator_skill_loaded": {"passed": 1, "total": 1, "rate": 1.0},
                    "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                }},
                "Phase Gap Model": {"criteria": {
                    "orchestrator_skill_loaded": {"passed": 1, "total": 2, "rate": 0.5},
                    "all_criteria": {"passed": 1, "total": 2, "rate": 0.5},
                }},
            },
        })
        _phase_run(p1, "cov_0", "Coverage Model", "coverage-model", "mc-a",
                   "orchestrator_skill_loaded", 2.0, False, True)
        _phase_run(p1, "gap_0", "Phase Gap Model", "phase-gap-model", "mc-a",
                   "orchestrator_skill_loaded", 2.0, False, True)
        _phase_run(p1, "gap_1", "Phase Gap Model", "phase-gap-model", "mc-a",
                   "orchestrator_skill_loaded", 2.0, False, False)

        # --- Phase 2 (post_confirmation) set: Coverage Model completes and
        # keeps the group alive; Phase Gap Model's ONLY run here is timed-out,
        # so the whole component drops for it after load-time exclusion ---
        p2 = self.results_dir / "20260721_040404"
        self._write_json(p2 / "manifest.json", {
            "daaf_git_sha": "e" * 40,
            "config": {"reps": 1, "parallel": False},
            "models": [
                {"id": "coverage-model", "name": "Coverage Model",
                 "provider": "anthropic"},
                {"id": "phase-gap-model", "name": "Phase Gap Model",
                 "provider": "anthropic"},
            ],
        })
        self._write_json(p2 / "summary.json", {
            "total_runs": 2,
            "errored_runs": 0,
            "total_cost_usd": 0,
            "wall_time_s": 5,
            "by_model": {
                "Coverage Model": {"criteria": {
                    "read_data_onboarding_mode": {"passed": 1, "total": 1, "rate": 1.0},
                    "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                }},
                "Phase Gap Model": {"criteria": {
                    "read_data_onboarding_mode": {"passed": 0, "total": 1, "rate": 0.0},
                    "all_criteria": {"passed": 0, "total": 1, "rate": 0.0},
                }},
            },
        })
        _phase_run(p2, "cov_p2_0", "Coverage Model", "coverage-model", "mc-b",
                   "read_data_onboarding_mode", 3.0, False, True)
        # Phase Gap Model's ONLY post_confirmation run is timed-out -> excluded
        # at load, leaving it with no completed runs in this whole phase.
        _phase_run(p2, "gap_p2_timeout", "Phase Gap Model", "phase-gap-model",
                   "mc-b", "read_data_onboarding_mode", 99.0, True, False)

    def _load(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result_sets = viewer.load_result_sets(str(self.results_dir))
            # load_runs returns a 3-tuple as of v3.3.0; the timeout-exclusion
            # count is asserted directly in the dedicated timeout test (which
            # captures all three returns), so it is discarded here.
            runs, anth_tokens, _ = viewer.load_runs(
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
        self.assertIn("Ignoring non-phase results reserved container: probes", warnings)

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
        self.assertEqual("3.7.3", bundle["generator_version"])

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

    def test_timed_out_runs_are_excluded_from_data_and_all_metrics(self):
        self._write_timeout_set()
        with redirect_stderr(io.StringIO()):
            result_sets = viewer.load_result_sets(
                str(self.results_dir), filter_timestamps=["20260720_000000"]
            )
            runs, anth_tokens, n_timed_out = viewer.load_runs(
                str(self.results_dir), result_sets, cases={}
            )

        # (6) The 3rd return equals the number of injected timed-out runs.
        self.assertEqual(2, n_timed_out)

        # (3) Timed-out runs never enter the returned runs list (the embedded
        # DATA payload), and the timed_out flag is not carried onto records.
        self.assertEqual(4, len(runs))
        self.assertTrue(all(not run.get("timed_out") for run in runs))
        self.assertNotIn("timed_out", runs[0])
        # The all-timed-out case_id is absent from the loaded runs entirely.
        self.assertEqual({"mc-a"}, {run["case_id"] for run in runs})
        # (3) Excluded from the Anthropic token aggregation: n counts completed
        # runs only (the 99999-token timed-out run would inflate it if kept).
        self.assertEqual(2, anth_tokens["Timeout Model"]["n"])
        self.assertEqual(2, anth_tokens["Opus 4.8"]["n"])

        precomputed = viewer.build_precomputed(
            result_sets,
            cases={},
            runs=runs,
            generation_params={"fixture": True},
            model_pricing={},
            anth_token_totals=anth_tokens,
            reconciliation=None,
        )

        # (3) per_model_phase counts and both rates reflect completed runs only.
        tm_cell = precomputed["per_model_phase"]["Timeout Model"]["mode_classification"]
        self.assertEqual(2, tm_cell["n_runs"])
        self.assertEqual(2, tm_cell["perfect_count"])
        self.assertEqual(1.0, tm_cell["perfect_rate"])
        self.assertEqual(1.0, tm_cell["hard_rate"])

        # (3) per_case excludes timed-out runs; (3) the degenerate all-timed-out
        # (case, model) cell produces no crash and simply leaves no per_case
        # entry — the composite/partial idioms handle the now-empty cell.
        self.assertEqual(4, precomputed["per_case"]["mc-a"]["n_runs"])
        self.assertEqual(1.0, precomputed["per_case"]["mc-a"]["perfect_rate"])
        self.assertNotIn("mc-degenerate", precomputed["per_case"])

        # (3b) v3.7.0 schema-additive consistency fields: cells_all_agree /
        # rate_agree computed over multi-rep (phase, case) cells. The fixture's
        # "Timeout Model" has one multi-rep cell (2 completed reps, both
        # graded perfect) -> identical grades -> full agreement.
        tm_cons = precomputed["consistency"]["Timeout Model"]
        self.assertEqual(1, tm_cons["cells_all_agree"])
        self.assertEqual(1.0, tm_cons["rate_agree"])

        # (4) PRECOMPUTED.duration mirrors cost.battery, over completed runs.
        duration = precomputed["duration"]
        dur_models = duration["models"]
        # est_duration_per_run == mean duration_s over completed runs
        self.assertEqual(2.0, dur_models["Opus 4.8"]["est_duration_per_run"])
        self.assertEqual(5.0, dur_models["Timeout Model"]["est_duration_per_run"])
        self.assertEqual(2, dur_models["Timeout Model"]["n_runs"])
        # battery_size == distinct completed case_ids (mc-degenerate excluded)
        self.assertEqual(1, duration["battery_size"])
        # est_battery_duration == est_duration_per_run x battery_size
        self.assertEqual(5.0, dur_models["Timeout Model"]["est_battery_duration"])
        # duration_multiplier_vs_ref is vs "Opus 4.8" (reference == 1.0)
        self.assertEqual("Opus 4.8", duration["reference_model"])
        self.assertEqual(1.0, dur_models["Opus 4.8"]["duration_multiplier_vs_ref"])
        self.assertEqual(2.5, dur_models["Timeout Model"]["duration_multiplier_vs_ref"])
        # (4) The SEPARATE duration.frontiers[basis][metric] block is present.
        self.assertIn("composite", duration["frontiers"])
        self.assertIn("perfect", duration["frontiers"]["composite"])
        self.assertIn("hard", duration["frontiers"]["composite"])

        # (5) Removed timeout surfaces are gone from PRECOMPUTED.
        self.assertNotIn("timeout_by_model", precomputed)
        self.assertNotIn("n_timed_out", precomputed["totals"])
        # totals.total_runs counts completed runs only.
        self.assertEqual(4, precomputed["totals"]["total_runs"])

    def test_completed_early_substitutes_score_complete_seconds_in_duration(self):
        """The duration-aggregate contribution rule for early-stopped runs
        (README § 8): a ``completed_early`` run carrying ``score_complete_seconds``
        contributes THAT value (a time-to-demonstrated-compliance measure), not
        its truncated ``duration_s`` and not an exclusion; a ``completed_early``
        run WITHOUT the field falls through to the documented excluded path. This
        exercises the real load_runs -> build_precomputed path (no mocks) and is
        the seam the field-carry BLOCKER broke: load_runs must surface
        ``score_complete_seconds`` onto the run record for the substitution to fire.
        """
        root = self.results_dir / "20260722_090909"
        self._write_json(root / "manifest.json", {
            "daaf_git_sha": "f" * 40,
            "config": {"reps": 1, "parallel": False},
            "models": [
                {"id": "opus-4-8", "name": "Opus 4.8", "provider": "anthropic"},
                {"id": "early-model", "name": "Early Model",
                 "provider": "anthropic"},
            ],
        })
        self._write_json(root / "summary.json", {
            "total_runs": 3,
            "errored_runs": 0,
            "total_cost_usd": 0,
            "wall_time_s": 10,
            "by_model": {
                "Opus 4.8": {"criteria": {
                    "orchestrator_skill_loaded": {"passed": 1, "total": 1, "rate": 1.0},
                    "all_criteria": {"passed": 1, "total": 1, "rate": 1.0},
                }},
                "Early Model": {"criteria": {
                    "orchestrator_skill_loaded": {"passed": 2, "total": 2, "rate": 1.0},
                    "all_criteria": {"passed": 2, "total": 2, "rate": 1.0},
                }},
            },
        })

        def _early_run(run_dir, model, model_id, duration, status,
                       score_complete):
            record = {
                "case_id": "mc-a",
                "model": model,
                "model_id": model_id,
                "provider": "anthropic",
                "rep": 0,
                "turns": 1,
                "computed_cost_usd": 0,
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "duration_s": duration,
                "timed_out": False,
                "status": status,
                "criteria": {"orchestrator_skill_loaded": {"passed": True}},
            }
            if score_complete is not None:
                record["score_complete_seconds"] = score_complete
            self._write_json(root / "runs" / run_dir / "result.json", record)

        # Reference model: one normal completed run, duration 2.0s.
        _early_run("opus_0", "Opus 4.8", "opus-4-8", 2.0, "completed", None)
        # Early Model, run WITH the field: truncated duration_s=50.0 must be
        # ignored in favor of score_complete_seconds=7.0.
        _early_run("early_with", "Early Model", "early-model", 50.0,
                   "completed_early", 7.0)
        # Early Model, run WITHOUT the field: must be EXCLUDED (not counted as
        # its truncated duration_s=60.0, which would otherwise pull the mean).
        _early_run("early_without", "Early Model", "early-model", 60.0,
                   "completed_early", None)

        with redirect_stderr(io.StringIO()):
            result_sets = viewer.load_result_sets(
                str(self.results_dir), filter_timestamps=["20260722_090909"]
            )
            runs, anth_tokens, _ = viewer.load_runs(
                str(self.results_dir), result_sets, cases={}
            )

        # load_runs must surface score_complete_seconds onto the run record (the
        # BLOCKER: absent this field the substitution is dead code and every
        # completed_early run is dropped from the duration aggregate).
        early_with = next(r for r in runs if r["model"] == "Early Model"
                          and r["score_complete_seconds"] is not None)
        self.assertEqual(7.0, early_with["score_complete_seconds"])
        early_without = next(r for r in runs if r["model"] == "Early Model"
                             and r["score_complete_seconds"] is None)
        self.assertIsNone(early_without["score_complete_seconds"])

        precomputed = viewer.build_precomputed(
            result_sets,
            cases={},
            runs=runs,
            generation_params={"fixture": True},
            model_pricing={},
            anth_token_totals=anth_tokens,
            reconciliation=None,
        )
        dur_models = precomputed["duration"]["models"]
        # Substitution fired: mean over the ONE contributing run == 7.0
        # (NOT 50.0 duration_s, NOT (50+60)/2 = 55.0, NOT excluded/absent).
        self.assertIn("Early Model", dur_models)
        self.assertEqual(1, dur_models["Early Model"]["n_runs"])
        self.assertEqual(7.0, dur_models["Early Model"]["est_duration_per_run"])
        self.assertEqual(2.0, dur_models["Opus 4.8"]["est_duration_per_run"])

    def test_all_timed_out_phase_drops_component_and_composite_renders_partial(self):
        # Companion to the per-CASE degeneracy above: exercises an all-timed-out
        # per-PHASE cell. The degenerate set flows through the shared _load()
        # path (alongside the setUp fixtures), then the REAL build_precomputed
        # path — no mocks — must not raise while dropping one model's whole
        # phase component and rendering it via the composite partial idiom.
        self._write_phase_timeout_set()
        result_sets, runs, anth_tokens, _ = self._load()

        precomputed = viewer.build_precomputed(
            result_sets,
            cases={},
            runs=runs,
            generation_params={"fixture": True},
            model_pricing={},
            anth_token_totals=anth_tokens,
            reconciliation=None,
        )

        pmp = precomputed["per_model_phase"]
        composite = precomputed["composite"]

        # The all-timed-out phase leaves NO per_model_phase cell for that group
        # (the model retains its mode_classification cell from the other phase)...
        self.assertIn("mode_classification", pmp["Phase Gap Model"])
        self.assertNotIn("post_confirmation", pmp["Phase Gap Model"])
        # ...while the group still EXISTS in the corpus, kept alive by the model
        # that completed a run in it — so this is a genuine dropped component,
        # not an absent group.
        self.assertIn("post_confirmation", pmp["Coverage Model"])

        # The dropped-component model still renders, via the composite partial
        # idiom: the group id is absent from components_present, listed in
        # components_missing, and the entry is flagged partial_data.
        self.assertIn("Phase Gap Model", composite)
        gap = composite["Phase Gap Model"]
        self.assertIn("mode_classification", gap["components_present"])
        self.assertNotIn("post_confirmation", gap["components_present"])
        self.assertIn("post_confirmation", gap["components_missing"])
        self.assertTrue(gap["partial_data"])

        # The composite score is the mean over PRESENT components only (missing
        # components are excluded, not zero-filled): 0.5 over the sole
        # mode_classification component (rate 0.5), NOT 0.25 as a zero-fill of
        # the missing post_confirmation component would yield.
        self.assertEqual(0.5, gap["score"])

        # The coverage model that kept the group alive has full coverage: the
        # component is present and it is not flagged partial.
        self.assertIn(
            "post_confirmation",
            composite["Coverage Model"]["components_present"],
        )
        self.assertFalse(composite["Coverage Model"]["partial_data"])

    def test_legacy_instant_exit_stub_excluded_but_errored_and_valid_kept(self):
        """v3.6.1 load-time guard: a LEGACY instant-exit stub (status absent,
        not timed out, error null, output_tokens null, 0/N criteria) is dropped
        at load — mirroring the corpus parity scan — so it can never re-enter
        rep counts or score averages. Two sibling legacy runs prove the screen
        is narrow: one with output_tokens present is KEPT, and an errored
        null-output run is KEPT with its handling UNCHANGED from pre-3.6.1 (the
        loader has never screened legacy runs on output_tokens; only the pure
        stub signature — null output AND null error — is newly excluded)."""
        root = self.results_dir / "20260729_120000"
        self._write_json(root / "manifest.json", {
            "daaf_git_sha": "a" * 40,
            "config": {"reps": 3, "parallel": False},
            "models": [
                {"id": "stub-model", "name": "Stub Legacy Model",
                 "provider": "anthropic"},
            ],
        })
        self._write_json(root / "summary.json", {
            "total_runs": 3,
            "errored_runs": 1,
            "total_cost_usd": 0,
            "wall_time_s": 6,
            "by_model": {
                "Stub Legacy Model": {"criteria": {
                    "orchestrator_skill_loaded":
                        {"passed": 1, "total": 3, "rate": 0.333},
                    "all_criteria": {"passed": 1, "total": 3, "rate": 0.333},
                }},
            },
        })

        def _legacy_run(run_dir, rep, output_tokens, error, passed):
            # NOTE: no "status" key is written — a legacy record (status
            # absent/null) is exactly the branch the v3.6.1 stub screen targets.
            self._write_json(root / "runs" / run_dir / "result.json", {
                "case_id": "mc-a",
                "model": "Stub Legacy Model",
                "model_id": "stub-model",
                "provider": "anthropic",
                "rep": rep,
                "turns": 1,
                "computed_cost_usd": 0,
                "input_tokens": 100,
                "output_tokens": output_tokens,
                "cache_read_tokens": 0,
                "cache_creation_tokens": 0,
                "duration_s": 2.0,
                "timed_out": False,
                "error": error,
                "criteria": {"orchestrator_skill_loaded": {"passed": passed}},
            })

        # (1) The instant-exit stub: null output, no error, criterion fails.
        _legacy_run("stub_rep0", 0, None, None, False)
        # (2) Sibling legacy run WITH output_tokens present -> still loaded.
        _legacy_run("valid_rep1", 1, 10, None, True)
        # (3) Errored legacy null-output run -> handling UNCHANGED (kept).
        _legacy_run("errored_rep2", 2, None, "TimeoutError: watchdog fired", False)

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result_sets = viewer.load_result_sets(
                str(self.results_dir), filter_timestamps=["20260729_120000"]
            )
            runs, anth_tokens, n_excluded = viewer.load_runs(
                str(self.results_dir), result_sets, cases={}
            )

        loaded_dirs = {run["run_dir"] for run in runs}
        # The stub is gone from the loaded runs (and thus every downstream
        # metric — rep counts, per_case, composite, cost/duration).
        self.assertNotIn("stub_rep0", loaded_dirs)
        # The output-bearing sibling and the errored null-output run are kept.
        self.assertIn("valid_rep1", loaded_dirs)
        self.assertIn("errored_rep2", loaded_dirs)
        self.assertEqual(2, len(runs))
        # The stub is folded into the No-signal excluded count and emits a NOTE.
        self.assertEqual(1, n_excluded)
        self.assertIn("legacy instant-exit stub", stderr.getvalue())
        self.assertIn("stub_rep0", stderr.getvalue())
        # The errored run's real failure signal is carried through untouched —
        # its handling is identical to pre-3.6.1 (loaded, error preserved).
        errored = next(r for r in runs if r["run_dir"] == "errored_rep2")
        self.assertEqual("TimeoutError: watchdog fired", errored["error"])
        self.assertIsNone(errored["status"])


if __name__ == "__main__":
    unittest.main()
