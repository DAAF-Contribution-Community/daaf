"""Pre-run cost estimation and post-run cost computation.

Uses calibration token profiles (average input/output/cached tokens per case)
collected from real benchmark runs, combined with per-model pricing from
models.yaml, to estimate costs before launching and compute actual costs after.

Calibration data collected 2026-06-08 from Haiku 4.5, DeepSeek V4 Flash, and
Gemini 3.1 Flash Lite (3 reps each, averaged across models).

Token semantics: Token counts come from the CLI's modelUsage block (which
aggregates across main session + subagent sessions). input_tokens is the
UNCACHED count, cache_read_tokens is additive. Total billed input =
input + cached.

IMPORTANT: Calibration data below was collected BEFORE the modelUsage fix
(2026-06-08) and reflects main-session-only tokens. These profiles will
underestimate costs for cases that dispatch subagents. Recalibrate after
the next batch run with the corrected token extraction.
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

CALIBRATION = {
    "mode_classification": PHASE1_TOKENS,
    "post_confirmation": PHASE2_TOKENS,
    "dispatch_compliance": PHASE3_TOKENS,
}


def compute_cost(model: ModelConfig, result: RunResult) -> float:
    """Compute actual cost from a completed run's token counts and model pricing.

    Use this instead of result.total_cost_usd — the CLI reports cost using
    Anthropic-internal pricing which is wrong for OpenRouter models.
    """
    if model.pricing is None:
        return result.total_cost_usd
    return model.pricing.estimate_cost(
        result.input_tokens, result.output_tokens, result.cache_read_tokens
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
    cal = CALIBRATION.get(phase, {})
    if not cal:
        return 0.0

    cases = case_ids if case_ids else list(cal.keys())
    return sum(_estimate_case_cost(model, cal[cid]) for cid in cases if cid in cal)


def estimate_batch_cost(models: list[ModelConfig], phase: str,
                        case_ids: list[str] | None = None,
                        reps: int = 1) -> dict:
    """Estimate total batch cost with per-model breakdown."""
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
