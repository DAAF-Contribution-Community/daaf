"""Pre-run cost estimation and post-run cost computation.

Uses calibration token profiles (average input/output/cached tokens per case)
collected from real benchmark runs, combined with per-model pricing from
models.yaml, to estimate costs before launching and compute actual costs after.

Phase 1-3 calibration data collected 2026-06-08 from Haiku 4.5, DeepSeek V4
Flash, and Gemini 3.1 Flash Lite (3 reps each, averaged across models).
Phase 4 calibration is newer — see the PHASE4_TOKENS_* block comment.

Token semantics: Token counts come from the CLI's modelUsage block (which
aggregates across main session + subagent sessions). input_tokens is the
UNCACHED count, cache_read_tokens is additive. Total billed input =
input + cached + cache_creation (cache writes billed at 1.25x input since
2026-06-11; calibration profiles below predate that and carry no
cache-creation column, so pre-run estimates remain cache-write-free).

IMPORTANT (Phases 1-3 only): the PHASE1/2/3_TOKENS data below was collected
BEFORE the modelUsage fix (2026-06-08) and reflects main-session-only tokens.
Those profiles will underestimate costs for cases that dispatch subagents.
Recalibrate after the next batch run with the corrected token extraction.
Phase 4 is post-fix and recalibrated per provider from the fresh-golden
baseline matrix (2026-06-10) — see the PHASE4_TOKENS_* block comment.
"""

from benchmarks.harness.models import ModelConfig, RunResult

# --- Calibration: average (input_tokens, output_tokens, cache_read_tokens) per case ---
# input_tokens = uncached input, cache_read_tokens = cached input (additive)

PHASE1_TOKENS = {
    "mc-01": (45006, 614, 22245),
    "mc-02": (76259, 421, 22245),
    "mc-03": (57407, 833, 27166),
    "mc-04": (66048, 536, 22782),
    "mc-05": (41038, 617, 25124),
    "mc-06": (98245, 882, 28609),
    "mc-07": (62794, 837, 30419),
    "mc-08": (38623, 782, 23102),
    "mc-09": (83868, 644, 39961),
    "mc-10": (43507, 788, 21538),
    "mc-11": (57471, 714, 26883),
    "mc-12": (61114, 734, 30752),
    "mc-13": (69866, 643, 23899),
    "mc-14": (82482, 585, 33666),
    "mc-15": (43472, 482, 25719),
}

PHASE2_TOKENS = {
    "pc-01": (64311, 695, 36455),
    "pc-02": (63021, 708, 44954),
    "pc-03": (110616, 1276, 5569),
    "pc-04": (111352, 1302, 35959),
    "pc-05": (102710, 871, 63408),
    "pc-06": (169395, 964, 53526),
    "pc-07": (143681, 1798, 109356),
    "pc-08": (92049, 1594, 24218),
    "pc-09": (174593, 1200, 79512),
}

PHASE3_TOKENS = {
    "dc-01": (121061, 1176, 36107),
    "dc-02": (145261, 1716, 80165),
    "dc-03": (94858, 2127, 54512),
    "dc-04": (150015, 1924, 45819),
    "dc-05": (67199, 1146, 39041),
    "dc-06": (77571, 1226, 28788),
    "dc-07": (200835, 1771, 142550),
    "dc-08": (82188, 1471, 58226),
    "dc-09": (115063, 1223, 107638),
    "dc-10": (152690, 1682, 120281),
    "dc-11": (89360, 1019, 28817),
    "dc-12": (113907, 1101, 37013),
}

# Recalibrated 2026-06-10 from the eight fresh-golden baseline sets
# (results/20260610_{184022,194256,201039,203038,203935,205051,210215,214502}:
# 10 OpenRouter models x 3 reps + 7 Anthropic models x 1 rep). Per-case means
# over 520 usable runs; 35 excluded (error/timed_out/zero-output — 34 Gemma 4
# 31B silent stalls, 1 DeepSeek V4 Pro). Computation:
# _sandbox/calibrate_phase4_c.py (execution log appended there).
#
# Phase 4 is calibrated PER PROVIDER because the two billing regimes do not
# mix: Anthropic runs carry ~0 uncached input and 90-190k cache_read tokens
# (billed ~10% of input price), while OpenRouter runs re-send uncached context
# every turn (CLI prompt caching does not apply). A single blended profile
# over-estimated Anthropic models 3.3-8.4x (validated against actuals in
# _sandbox/validate_phase4_estimator.py). Estimation selects the profile via
# model.provider; an unknown provider falls back to the OpenRouter profile
# (conservative: estimates high).
PHASE4_TOKENS_OPENROUTER = {
    "sr-01": (187569, 1828, 12603),
    "sr-02": (147919, 1645, 10989),
    "sr-03": (164965, 1942, 12968),
    "sr-04": (201967, 1826, 5489),
    "sr-05": (121071, 1361, 8240),
    "sr-06": (149310, 1554, 12410),
    "sr-07": (112737, 2086, 10647),
    "sr-08": (135098, 1782, 4832),
    "sr-09": (133282, 1940, 6280),
    "sr-10": (161858, 1827, 9632),
    "sr-11": (128361, 1659, 9374),
    "sr-12": (149213, 1677, 5066),
    "sr-13": (158344, 1691, 9972),
    "sr-14": (200071, 1429, 9555),
    "sr-15": (248931, 2433, 7462),
}

PHASE4_TOKENS_ANTHROPIC = {
    "sr-01": (12, 3035, 164352),
    "sr-02": (12, 3253, 139511),
    "sr-03": (11, 3728, 135421),
    "sr-04": (5254, 2734, 120691),
    "sr-05": (13, 2592, 153501),
    "sr-06": (10, 2407, 114003),
    "sr-07": (865, 3853, 132097),
    "sr-08": (635, 2498, 101479),
    "sr-09": (3058, 2862, 122605),
    "sr-10": (11, 1883, 89653),
    "sr-11": (1989, 3042, 122223),
    "sr-12": (2242, 2663, 112201),
    "sr-13": (12, 2711, 124155),
    "sr-14": (3667, 2007, 157398),
    "sr-15": (8808, 3840, 187044),
}

CALIBRATION = {
    "mode_classification": PHASE1_TOKENS,
    "post_confirmation": PHASE2_TOKENS,
    "dispatch_compliance": PHASE3_TOKENS,
    "skill_routing": PHASE4_TOKENS_OPENROUTER,
}

# Provider-specific overrides applied on top of CALIBRATION (see Phase 4
# block comment). Phases 1-3 have no split yet — their profiles predate the
# modelUsage fix and are pending recalibration regardless.
ANTHROPIC_CALIBRATION = {
    "skill_routing": PHASE4_TOKENS_ANTHROPIC,
}


def _calibration_for(model: ModelConfig, phase: str) -> dict:
    """Select the calibration table for a model+phase, honoring provider overrides."""
    if model.provider == "anthropic" and phase in ANTHROPIC_CALIBRATION:
        return ANTHROPIC_CALIBRATION[phase]
    return CALIBRATION.get(phase, {})


def compute_cost(model: ModelConfig, result: RunResult) -> float:
    """Compute cost from a completed run's token counts and model pricing.

    Use this instead of result.total_cost_usd — the CLI reports cost using
    Anthropic-internal pricing which is wrong for OpenRouter models.

    Note: For OpenRouter models, CLI token counts use Anthropic's tokenizer
    (not the model's native tokenizer), so computed costs are approximate.

    2026-06-11: cache_creation_tokens now included (billed at 1.25x input —
    Anthropic's cache-write convention; see PricingConfig.estimate_cost).
    Previously omitted, which understated Anthropic-side costs ~3x. Applies
    to future runs only; archived result.json values are not recomputed.
    """
    if model.pricing is None:
        return result.total_cost_usd
    return model.pricing.estimate_cost(
        result.input_tokens, result.output_tokens, result.cache_read_tokens,
        result.cache_creation_tokens,
    )


def _estimate_case_cost(model: ModelConfig, tokens: tuple[int, int, int]) -> float:
    """Estimate cost for a single case given calibration token counts."""
    if model.pricing is None:
        return 0.0
    input_tok, output_tok, cached_tok = tokens
    return model.pricing.estimate_cost(input_tok, output_tok, cached_tok)


def estimate_run_cost(model: ModelConfig, phase: str,
                      case_ids: list[str] | None = None) -> float:
    """Estimate cost for one rep of the given cases on the given model."""
    cal = _calibration_for(model, phase)
    if not cal:
        return 0.0

    cases = case_ids if case_ids else list(cal.keys())
    return sum(_estimate_case_cost(model, cal[cid]) for cid in cases if cid in cal)


def estimate_batch_cost(models: list[ModelConfig], phase: str,
                        case_ids: list[str] | None = None,
                        reps: int = 1) -> dict:
    """Estimate total batch cost with per-model breakdown."""
    # Case enumeration uses the default (OpenRouter) table; provider override
    # tables must keep identical case-id keysets (asserted by the calibration
    # scripts) or provider-specific cases would be silently dropped here.
    cal = CALIBRATION.get(phase, {})
    cases = [c for c in (case_ids or list(cal.keys())) if c in cal]
    num_cases = len(cases)

    by_model = []
    total = 0.0
    for m in models:
        per_rep = estimate_run_cost(m, phase, cases)
        model_total = per_rep * reps
        total += model_total
        num_runs = num_cases * reps
        by_model.append({
            "name": m.name,
            "runs": num_runs,
            "per_run": model_total / num_runs if num_runs > 0 else 0,
            "estimated_cost": model_total,
        })

    return {
        "total": total,
        "runs": num_cases * reps * len(models),
        "by_model": by_model,
    }


def format_estimate(est: dict) -> str:
    """Format a batch estimate as a human-readable string."""
    lines = [f"Estimated cost: ${est['total']:.2f} ({est['runs']} runs)"]
    for m in est["by_model"]:
        lines.append(
            f"  {m['name']:25s} {m['runs']:3d} runs × ~${m['per_run']:.3f} = ${m['estimated_cost']:.2f}"
        )
    return "\n".join(lines)
