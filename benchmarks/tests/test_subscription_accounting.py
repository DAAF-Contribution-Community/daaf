"""Focused deterministic tests for legacy and subscription accounting."""

import unittest

from benchmarks.harness.cost_estimator import compute_accounting, compute_cost
from benchmarks.harness.models import ModelConfig, PricingConfig, RunResult


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


if __name__ == "__main__":
    unittest.main()
