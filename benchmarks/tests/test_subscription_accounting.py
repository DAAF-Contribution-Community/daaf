"""Focused deterministic tests for legacy and subscription accounting."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.harness.artifacts import build_run_artifact
from benchmarks.harness.cost_estimator import compute_accounting, compute_cost
from benchmarks.harness.model_loader import load_models
from benchmarks.harness.models import ModelConfig, PricingConfig, RunResult


MODELS_FILE = Path("/daaf/benchmarks/config/models.yaml")

# Mirrors the gpt-56-luna-chatgpt api_equivalent_pricing block in
# config/models.yaml. Since 2026-09-29 compute_accounting() prices each model
# from its OWN block (no LUNA_* constant fallback), so a synthetic Luna fixture
# must carry the schedule explicitly.
LUNA_API_EQUIVALENT_PRICING = {
    "source_url": "https://developers.openai.com/api/docs/pricing",
    "accessed_at": "2026-08-11",
    "threshold_input_tokens": 272_000,
    "short_context": {
        "input": 0.20, "cached_input": 0.02, "cache_write": 0.25, "output": 1.20,
    },
    "long_context": {
        "input": 0.40, "cached_input": 0.04, "cache_write": 0.50, "output": 1.80,
    },
}


class LegacyCostTests(unittest.TestCase):
    def test_legacy_cost_output_is_unchanged(self):
        model = ModelConfig(
            id="legacy",
            name="Legacy",
            provider="openrouter",
            pricing=PricingConfig(input=2.0, output=10.0, cached_input=0.2),
        )
        result = RunResult(
            test_case_id="x",
            model_id="legacy",
            model_name="Legacy",
            run_index=0,
            input_tokens=100_000,
            output_tokens=10_000,
            cache_read_tokens=20_000,
            cache_creation_tokens=4_000,
        )
        # Historical formula: ordinary input + output + cache read +
        # cache creation at 1.25x ordinary input.
        self.assertAlmostEqual(0.314, compute_cost(model, result), places=12)

    def test_legacy_cli_fallback_is_unchanged_without_pricing(self):
        model = ModelConfig(id="legacy", name="Legacy")
        result = RunResult("x", "legacy", "Legacy", 0, total_cost_usd=1.2345)
        self.assertEqual(1.2345, compute_cost(model, result))


class SubscriptionAccountingTests(unittest.TestCase):
    def setUp(self):
        self.model = ModelConfig(
            id="gpt-5.6-luna",
            name="GPT-5.6 Luna (ChatGPT Subscription)",
            key="gpt-56-luna-chatgpt",
            provider="chatgpt-subscription",
            actual_billing_treatment="not_separately_billed",
            api_equivalent_pricing=LUNA_API_EQUIVALENT_PRICING,
        )

    def result(self):
        return RunResult("x", self.model.id, self.model.name, 0)

    def test_null_not_zero_and_scenarios_for_incomplete_cache_telemetry(self):
        result = self.result()
        result.usage_observed.input_tokens = 120_000
        result.usage_observed.output_tokens = 18_000
        result.usage_observed.output_includes_reasoning = True
        accounting = compute_accounting(self.model, result)

        actual = accounting["actual_billing"]
        equivalent = accounting["api_equivalent"]
        capacity = accounting["subscription_capacity"]
        self.assertEqual("not_separately_billed", actual.charge_status)
        self.assertIsNone(actual.actual_marginal_charge_usd)
        self.assertIsNone(equivalent.cost_usd)
        # 2026-08-11 Luna 5x price cut (short 0.20/1.20, long 0.40/1.80):
        # 120k uncached input + 18k output. Was 0.228 / 0.402 prior.
        self.assertAlmostEqual(0.0456, equivalent.short_context_uncached_scenario_usd)
        self.assertAlmostEqual(0.0804, equivalent.long_context_uncached_scenario_usd)
        self.assertIn("cache_read_tokens_unavailable", equivalent.incompleteness_reasons)
        self.assertIn("cache_write_tokens_unavailable", equivalent.incompleteness_reasons)
        self.assertTrue(equivalent.not_invoiced)
        self.assertIsNone(capacity.before)
        self.assertIsNone(capacity.after)
        self.assertIsNone(capacity.delta_observed)
        self.assertIsNone(capacity.credits_calculated)
        self.assertIsNone(capacity.credit_usd_value)

    def test_exact_short_context_separates_cache_and_does_not_double_count_reasoning(self):
        result = self.result()
        usage = result.usage_observed
        usage.input_tokens = 120_000
        usage.input_includes_cache_tokens = True
        usage.cache_read_tokens = 20_000
        usage.cache_write_tokens = 10_000
        usage.output_tokens = 18_000
        usage.output_includes_reasoning = True
        usage.reasoning_tokens = 12_000
        usage.max_request_input_tokens = 120_000

        equivalent = compute_accounting(self.model, result)["api_equivalent"]
        # 90k ordinary input + 20k cache read + 10k cache write + 18k
        # output. The 12k reasoning subset is already inside 18k output.
        self.assertEqual("short", equivalent.context_tier)
        self.assertEqual("exact_from_observed_token_categories", equivalent.calculation_status)
        # 2026-08-11 Luna cut: 90k input*0.20 + 20k read*0.02 + 10k write*0.25 +
        # 18k output*1.20, all /1M = 0.0425. Was 0.2125 prior.
        self.assertAlmostEqual(0.0425, equivalent.cost_usd, places=12)

        usage.reasoning_tokens = 0
        without_reasoning_detail = compute_accounting(self.model, result)["api_equivalent"]
        self.assertEqual(equivalent.cost_usd, without_reasoning_detail.cost_usd)

    def test_exact_long_context_uses_threshold_rates(self):
        result = self.result()
        usage = result.usage_observed
        usage.input_tokens = 320_000
        usage.input_includes_cache_tokens = True
        usage.cache_read_tokens = 20_000
        usage.cache_write_tokens = 10_000
        usage.output_tokens = 18_000
        usage.output_includes_reasoning = True
        usage.reasoning_tokens = 12_000
        usage.max_request_input_tokens = 300_000
        usage.pricing_context_tier = "long"

        equivalent = compute_accounting(self.model, result)["api_equivalent"]
        self.assertEqual("long", equivalent.context_tier)
        # 2026-08-11 Luna cut (long 0.40/0.04/0.50/1.80): 290k input*0.40 +
        # 20k read*0.04 + 10k write*0.50 + 18k output*1.80, /1M = 0.1542.
        # Was 0.771 prior.
        self.assertAlmostEqual(0.1542, equivalent.cost_usd, places=12)

    def test_cache_categories_are_subsets_not_additions(self):
        result = self.result()
        usage = result.usage_observed
        usage.input_tokens = 100
        usage.input_includes_cache_tokens = True
        usage.cache_read_tokens = 20
        usage.cache_write_tokens = 10
        usage.output_tokens = 0
        usage.output_includes_reasoning = True
        usage.max_request_input_tokens = 100

        equivalent = compute_accounting(self.model, result)["api_equivalent"]
        # 2026-08-11 Luna short rates: input 0.20, cached 0.02, cache_write 0.25.
        expected = (70 * 0.20 + 20 * 0.02 + 10 * 0.25) / 1_000_000
        self.assertAlmostEqual(expected, equivalent.cost_usd, places=15)

    def test_inconsistent_cache_breakdown_never_produces_exact_cost(self):
        result = self.result()
        usage = result.usage_observed
        usage.input_tokens = 100
        usage.input_includes_cache_tokens = True
        usage.cache_read_tokens = 80
        usage.cache_write_tokens = 30
        usage.output_tokens = 10
        usage.output_includes_reasoning = True
        usage.max_request_input_tokens = 100

        equivalent = compute_accounting(self.model, result)["api_equivalent"]
        self.assertIsNone(equivalent.cost_usd)
        self.assertIn("cache_categories_exceed_total_input", equivalent.incompleteness_reasons)


class PerModelApiEquivalentPricingTests(unittest.TestCase):
    """Regression (2026-09-29): each ChatGPT-lane model is priced at its OWN rates.

    Before the fix compute_accounting() priced every chatgpt-subscription model
    at the LUNA_* constants, so Terra/Sol/Astra archived API-equivalent costs
    were understated 10x/20x/50x. Expected values below are hand-computed from
    the api_equivalent_pricing blocks in config/models.yaml (loaded live, so a
    registry repricing surfaces here). If a registry schedule changes (e.g. Sol's
    promotional pricing is reverted), update these hand computations with it.
    """

    @classmethod
    def setUpClass(cls):
        env = {
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api",
            "OPENROUTER_AUTH_TOKEN": "test-only-placeholder",
            "ANTHROPIC_BASE_URL": "https://unrelated.example.test",
            "SHIM_PORT": "4141",
        }
        with patch.dict(os.environ, env, clear=False):
            cls.registry = load_models(MODELS_FILE)

    def complete_usage_result(self, model, long_context=False):
        """A run with every token category observed (exact cost is computable).

        Short: 120k total input (20k cache read + 10k cache write, so 90k
        ordinary), 18k output, 120k max request -> short tier by threshold.
        Long: 320k total input (20k read + 10k write, so 290k ordinary), 18k
        output, 300k max request, explicit long tier.
        """
        result = RunResult("x", model.id, model.name, 0)
        usage = result.usage_observed
        usage.input_tokens = 320_000 if long_context else 120_000
        usage.input_includes_cache_tokens = True
        usage.cache_read_tokens = 20_000
        usage.cache_write_tokens = 10_000
        usage.output_tokens = 18_000
        usage.output_includes_reasoning = True
        usage.reasoning_tokens = 12_000
        usage.max_request_input_tokens = 300_000 if long_context else 120_000
        if long_context:
            usage.pricing_context_tier = "long"
        return result

    def test_sol_exact_cost_and_scenarios_use_sol_rates(self):
        sol = self.registry["gpt-56-sol-chatgpt"]
        equivalent = compute_accounting(sol, self.complete_usage_result(sol))["api_equivalent"]
        self.assertEqual("exact_from_observed_token_categories", equivalent.calculation_status)
        self.assertEqual([], equivalent.incompleteness_reasons)
        # Sol short 4.00/0.40/5.00/20.00: 90k*4 + 20k*0.4 + 10k*5 + 18k*20
        # = 360,000 + 8,000 + 50,000 + 360,000 = 778,000 /1M = 0.778.
        # (Old Luna-priced value for the same run: 0.0425.)
        self.assertAlmostEqual(0.778, equivalent.cost_usd, places=12)
        # Scenarios (all input ordinary): short 120k*4 + 18k*20 = 0.84;
        # long 120k*8 + 18k*30 = 1.5. (Old Luna values: 0.0456 / 0.0804.)
        self.assertAlmostEqual(0.84, equivalent.short_context_uncached_scenario_usd, places=12)
        self.assertAlmostEqual(1.5, equivalent.long_context_uncached_scenario_usd, places=12)

    def test_sol_long_context_exact_cost_uses_sol_long_rates(self):
        sol = self.registry["gpt-56-sol-chatgpt"]
        result = self.complete_usage_result(sol, long_context=True)
        equivalent = compute_accounting(sol, result)["api_equivalent"]
        self.assertEqual("long", equivalent.context_tier)
        # Sol long 8.00/0.80/10.00/30.00: 290k*8 + 20k*0.8 + 10k*10 + 18k*30
        # = 2,320,000 + 16,000 + 100,000 + 540,000 = 2,976,000 /1M = 2.976.
        self.assertAlmostEqual(2.976, equivalent.cost_usd, places=12)

    def test_astra_exact_cost_and_scenarios_use_astra_rates(self):
        astra = self.registry["gpt-6-astra-chatgpt"]
        equivalent = compute_accounting(astra, self.complete_usage_result(astra))["api_equivalent"]
        # Astra short 10.00/1.00/12.50/50.00: 90k*10 + 20k*1 + 10k*12.5 + 18k*50
        # = 900,000 + 20,000 + 125,000 + 900,000 = 1,945,000 /1M = 1.945.
        self.assertAlmostEqual(1.945, equivalent.cost_usd, places=12)
        # Scenarios: short 120k*10 + 18k*50 = 2.1; long 120k*20 + 18k*75 = 3.75.
        self.assertAlmostEqual(2.1, equivalent.short_context_uncached_scenario_usd, places=12)
        self.assertAlmostEqual(3.75, equivalent.long_context_uncached_scenario_usd, places=12)

    def test_terra_exact_cost_uses_terra_rates_in_both_tiers(self):
        terra = self.registry["gpt-56-terra-chatgpt"]
        short = compute_accounting(terra, self.complete_usage_result(terra))["api_equivalent"]
        # Terra short 2.00/0.20/2.50/12.00: 90k*2 + 20k*0.2 + 10k*2.5 + 18k*12
        # = 180,000 + 4,000 + 25,000 + 216,000 = 425,000 /1M = 0.425.
        self.assertAlmostEqual(0.425, short.cost_usd, places=12)
        long = compute_accounting(
            terra, self.complete_usage_result(terra, long_context=True)
        )["api_equivalent"]
        # Terra long 4.00/0.40/5.00/18.00: 290k*4 + 20k*0.4 + 10k*5 + 18k*18
        # = 1,160,000 + 8,000 + 50,000 + 324,000 = 1,542,000 /1M = 1.542.
        self.assertAlmostEqual(1.542, long.cost_usd, places=12)

    def test_luna_registry_pricing_is_unchanged(self):
        luna = self.registry["gpt-56-luna-chatgpt"]
        short = compute_accounting(luna, self.complete_usage_result(luna))["api_equivalent"]
        # Same values the pre-fix constants produced (see SubscriptionAccountingTests).
        self.assertAlmostEqual(0.0425, short.cost_usd, places=12)
        self.assertAlmostEqual(0.0456, short.short_context_uncached_scenario_usd, places=12)
        self.assertAlmostEqual(0.0804, short.long_context_uncached_scenario_usd, places=12)
        long = compute_accounting(
            luna, self.complete_usage_result(luna, long_context=True)
        )["api_equivalent"]
        self.assertAlmostEqual(0.1542, long.cost_usd, places=12)
        self.assertEqual("https://developers.openai.com/api/docs/pricing", short.price_source_url)
        self.assertEqual("2026-08-11", short.price_schedule_accessed_at)
        self.assertEqual(272_000, short.context_threshold_input_tokens)

    def test_price_basis_is_stamped_from_the_models_own_schedule(self):
        # Registry: Sol's schedule was accessed 2026-09-29, not Luna's 2026-08-11.
        sol = self.registry["gpt-56-sol-chatgpt"]
        equivalent = compute_accounting(sol, self.complete_usage_result(sol))["api_equivalent"]
        self.assertEqual("2026-09-29", equivalent.price_schedule_accessed_at)
        self.assertEqual(
            sol.api_equivalent_pricing["source_url"], equivalent.price_source_url
        )
        self.assertEqual(
            sol.api_equivalent_pricing["threshold_input_tokens"],
            equivalent.context_threshold_input_tokens,
        )

    def test_threshold_url_and_date_come_from_model_not_luna_constants(self):
        # Synthetic schedule whose every provenance field differs from Luna's.
        # A 120k max request is short under Luna's 272k threshold but exceeds
        # this model's 100k threshold, so with no explicit tier the run spans
        # an unknown mix of tiers and no exact cost may be produced.
        pricing = dict(LUNA_API_EQUIVALENT_PRICING)
        pricing.update(
            source_url="https://example.test/pricing/custom-model",
            accessed_at="2099-01-01",
            threshold_input_tokens=100_000,
        )
        model = ModelConfig(
            id="custom-model",
            name="Custom (ChatGPT Subscription)",
            provider="chatgpt-subscription",
            api_equivalent_pricing=pricing,
        )
        equivalent = compute_accounting(model, self.complete_usage_result(model))["api_equivalent"]
        self.assertEqual("https://example.test/pricing/custom-model", equivalent.price_source_url)
        self.assertEqual("2099-01-01", equivalent.price_schedule_accessed_at)
        self.assertEqual(100_000, equivalent.context_threshold_input_tokens)
        self.assertIn(
            "mixed_request_context_tiers_unavailable", equivalent.incompleteness_reasons
        )
        self.assertIsNone(equivalent.cost_usd)

    def test_missing_pricing_is_unavailable_not_luna_priced(self):
        model = ModelConfig(
            id="gpt-unpriced",
            name="Unpriced (ChatGPT Subscription)",
            provider="chatgpt-subscription",
        )
        equivalent = compute_accounting(model, self.complete_usage_result(model))["api_equivalent"]
        # Telemetry is complete, so the ONLY reason is the missing schedule.
        self.assertEqual(["api_equivalent_pricing_unavailable"], equivalent.incompleteness_reasons)
        self.assertEqual("unavailable_api_equivalent_pricing", equivalent.calculation_status)
        self.assertIsNone(equivalent.cost_usd)
        self.assertIsNone(equivalent.short_context_uncached_scenario_usd)
        self.assertIsNone(equivalent.long_context_uncached_scenario_usd)
        self.assertIsNone(equivalent.price_source_url)
        self.assertIsNone(equivalent.price_schedule_accessed_at)
        self.assertIsNone(equivalent.context_threshold_input_tokens)
        self.assertTrue(equivalent.not_invoiced)

    def test_partial_or_invalid_pricing_is_unavailable_with_named_reasons(self):
        cases = {
            "missing_long_rates": (
                {k: v for k, v in LUNA_API_EQUIVALENT_PRICING.items() if k != "long_context"},
                "api_equivalent_long_context_rates_unavailable",
            ),
            "negative_short_rate": (
                {**LUNA_API_EQUIVALENT_PRICING,
                 "short_context": {**LUNA_API_EQUIVALENT_PRICING["short_context"], "output": -1.0}},
                "api_equivalent_short_context_rates_invalid",
            ),
            "missing_rate_key": (
                {**LUNA_API_EQUIVALENT_PRICING,
                 "short_context": {"input": 0.20, "output": 1.20}},
                "api_equivalent_short_context_rates_invalid",
            ),
            "missing_threshold": (
                {k: v for k, v in LUNA_API_EQUIVALENT_PRICING.items()
                 if k != "threshold_input_tokens"},
                "api_equivalent_threshold_input_tokens_unavailable",
            ),
            "missing_source_url": (
                {k: v for k, v in LUNA_API_EQUIVALENT_PRICING.items() if k != "source_url"},
                "api_equivalent_price_source_url_unavailable",
            ),
            "blank_accessed_at": (
                {**LUNA_API_EQUIVALENT_PRICING, "accessed_at": "  "},
                "api_equivalent_price_accessed_at_invalid",
            ),
            # Type-edge rates and thresholds (Phase 4 review, 2026-09-29): each
            # row kills a mutant of _is_usable_rate / the threshold guard that
            # the rows above let survive. bool is an int subclass (True == 1),
            # so a dropped bool check silently prices at $1/M; inf passes
            # `>= 0`, so only math.isfinite rejects it. NaN already fails
            # `>= 0`; its row locks the rejection regardless of which guard
            # does the work.
            "bool_short_rate": (
                {**LUNA_API_EQUIVALENT_PRICING,
                 "short_context": {**LUNA_API_EQUIVALENT_PRICING["short_context"], "output": True}},
                "api_equivalent_short_context_rates_invalid",
            ),
            "nan_short_rate": (
                {**LUNA_API_EQUIVALENT_PRICING,
                 "short_context": {**LUNA_API_EQUIVALENT_PRICING["short_context"],
                                   "input": float("nan")}},
                "api_equivalent_short_context_rates_invalid",
            ),
            "inf_long_rate": (
                {**LUNA_API_EQUIVALENT_PRICING,
                 "long_context": {**LUNA_API_EQUIVALENT_PRICING["long_context"],
                                  "output": float("inf")}},
                "api_equivalent_long_context_rates_invalid",
            ),
            "bool_threshold": (
                {**LUNA_API_EQUIVALENT_PRICING, "threshold_input_tokens": True},
                "api_equivalent_threshold_input_tokens_invalid",
            ),
            "float_threshold": (
                {**LUNA_API_EQUIVALENT_PRICING, "threshold_input_tokens": 272000.0},
                "api_equivalent_threshold_input_tokens_invalid",
            ),
        }
        for label, (pricing, reason) in cases.items():
            with self.subTest(case=label):
                model = ModelConfig(
                    id="gpt-partial",
                    name="Partial (ChatGPT Subscription)",
                    provider="chatgpt-subscription",
                    api_equivalent_pricing=pricing,
                )
                equivalent = compute_accounting(
                    model, self.complete_usage_result(model)
                )["api_equivalent"]
                self.assertIn(reason, equivalent.incompleteness_reasons)
                self.assertEqual(
                    "unavailable_api_equivalent_pricing", equivalent.calculation_status
                )
                self.assertIsNone(equivalent.cost_usd)
                self.assertIsNone(equivalent.short_context_uncached_scenario_usd)
                self.assertIsNone(equivalent.long_context_uncached_scenario_usd)

    def test_request_exactly_at_threshold_is_short_and_one_over_is_mixed(self):
        # Boundary of the no-explicit-tier classification (Phase 4 review,
        # 2026-09-29): a largest request EQUAL to the threshold is short-tier
        # (`<=`), so the run is exactly priced at short rates; one token over
        # means some request may have crossed into long-context pricing, so no
        # exact cost. The max request is held at 120k (== total input, so no
        # exceed-total reason) and the threshold is moved instead.
        at_threshold = dict(LUNA_API_EQUIVALENT_PRICING, threshold_input_tokens=120_000)
        one_over = dict(LUNA_API_EQUIVALENT_PRICING, threshold_input_tokens=119_999)
        for label, pricing in (("equal", at_threshold), ("one_over", one_over)):
            with self.subTest(case=label):
                model = ModelConfig(
                    id="gpt-boundary",
                    name="Boundary (ChatGPT Subscription)",
                    provider="chatgpt-subscription",
                    api_equivalent_pricing=pricing,
                )
                result = self.complete_usage_result(model)
                self.assertEqual(120_000, result.usage_observed.max_request_input_tokens)
                self.assertIsNone(result.usage_observed.pricing_context_tier)
                equivalent = compute_accounting(model, result)["api_equivalent"]
                if label == "equal":
                    self.assertEqual("short", equivalent.context_tier)
                    self.assertEqual([], equivalent.incompleteness_reasons)
                    self.assertEqual(
                        "exact_from_observed_token_categories", equivalent.calculation_status
                    )
                    # Luna short rates, same run as SubscriptionAccountingTests:
                    # 90k*0.20 + 20k*0.02 + 10k*0.25 + 18k*1.20, /1M = 0.0425.
                    self.assertAlmostEqual(0.0425, equivalent.cost_usd, places=12)
                else:
                    self.assertEqual("unknown", equivalent.context_tier)
                    self.assertEqual(
                        ["mixed_request_context_tiers_unavailable"],
                        equivalent.incompleteness_reasons,
                    )
                    self.assertEqual(
                        "unavailable_incomplete_telemetry", equivalent.calculation_status
                    )
                    self.assertIsNone(equivalent.cost_usd)

    def test_run_artifact_records_sol_priced_api_equivalent(self):
        # Caller wiring: build_run_artifact (artifacts.py) is how the executor's
        # result becomes result.json; its api_equivalent must carry Sol pricing.
        sol = self.registry["gpt-56-sol-chatgpt"]
        record = build_run_artifact(
            sol, self.complete_usage_result(sol), {"case_id": "x", "rep": 0}
        )
        self.assertAlmostEqual(0.778, record["api_equivalent"]["cost_usd"], places=12)
        self.assertEqual("2026-09-29", record["api_equivalent"]["price_schedule_accessed_at"])
        self.assertIsNone(record["computed_cost_usd"])


if __name__ == "__main__":
    unittest.main()
