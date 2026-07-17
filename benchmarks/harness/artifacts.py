"""Shared schema-v2 artifact, preflight, and null-accounting helpers.

The phase runners keep their phase-specific scoring and archive layouts. This
module owns only the fields and control flow that must mean the same thing in
every runner: provider/model metadata, route and usage evidence, billing
ledgers, nullable monetary summaries, and the zero-execution preflight gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from numbers import Real
from pathlib import Path
from typing import Iterable, Mapping, Optional

from benchmarks.harness.cost_estimator import compute_accounting, compute_cost
from benchmarks.harness.models import ModelConfig, RunResult
from benchmarks.harness.route_provenance import (
    CHATGPT_PROVIDER,
    RouteContractError,
    preflight_models,
    safe_provenance_dict,
)


SCHEMA_VERSION = 2
ACCOUNTING_CATEGORIES = (
    "exact",
    "scenario_only",
    "unavailable",
    "legacy_numeric",
)
PURITY_STATUSES = ("verified", "failed", "unverifiable")
PURITY_EVIDENCE_SOURCE = "child_transcript_assistant_message.model"
PURITY_EVIDENCE_BOUNDARY = (
    "Claude CLI child-transcript-observed model identity; not backend-confirmed"
)


def attach_schema_version(payload: Mapping) -> dict:
    """Return an additive schema-v2 copy without mutating the caller's mapping."""
    artifact = dict(payload)
    artifact["schema_version"] = SCHEMA_VERSION
    return artifact


def _model_key(model: ModelConfig) -> str:
    """Resolve the selectable key using the registry's compatibility rule."""
    return model.key or model.name.lower().replace(" ", "-").replace(".", "")


def model_manifest_entry(model: ModelConfig) -> dict:
    """Serialize explicit model identity, route, context, and price metadata.

    Historical manifest keys (``name``, ``id``, ``provider``, and
    ``effort_level``) remain present. New keys are additive and make provider
    and billing interpretation explicit.
    """
    pricing = asdict(model.pricing) if model.pricing is not None else None
    return {
        "key": _model_key(model),
        "id": model.id,
        "name": model.name,
        "display_name": model.name,
        "provider": model.provider,
        "effort_level": model.effort_level or "default",
        "context_window_tokens": model.context_window_tokens,
        "pricing": pricing,
        "billing": {
            "actual_billing_treatment": model.actual_billing_treatment,
            "api_equivalent_pricing": dict(model.api_equivalent_pricing),
        },
    }


def _identity_dict(model: ModelConfig, result: RunResult) -> dict:
    identity = result.model_identity
    return {
        "benchmark_key": identity.benchmark_key or _model_key(model),
        "requested_model_id": identity.requested_model_id or model.id,
        "claude_cli_model_usage_ids": list(identity.claude_cli_model_usage_ids),
        "backend_confirmed_model_id": identity.backend_confirmed_model_id,
    }


def _schema_v2_run_fields(model: ModelConfig, result: RunResult) -> dict:
    provenance = (
        safe_provenance_dict(result.route_provenance)
        if result.route_provenance is not None
        else None
    )
    accounting = compute_accounting(model, result)
    if model.provider == CHATGPT_PROVIDER:
        actual_billing = accounting["actual_billing"]
        api_equivalent = accounting["api_equivalent"]
        subscription_capacity = result.subscription_capacity
    else:
        actual_billing = result.actual_billing
        api_equivalent = accounting["api_equivalent"]
        subscription_capacity = result.subscription_capacity

    return {
        "provenance": provenance,
        "model_identity": _identity_dict(model, result),
        "usage_observed": asdict(result.usage_observed),
        "actual_billing": asdict(actual_billing),
        "api_equivalent": asdict(api_equivalent),
        "subscription_capacity": asdict(subscription_capacity),
    }


def computed_cost_for_run(model: ModelConfig, result: RunResult) -> Optional[float]:
    """Return the legacy computed amount or null for included subscription use."""
    if model.provider == CHATGPT_PROVIDER:
        return None
    return compute_cost(model, result)


def build_run_artifact(
    model: ModelConfig,
    result: RunResult,
    phase_fields: Optional[Mapping] = None,
    duration_s: Optional[float] = None,
) -> dict:
    """Build one additive run record while preserving historical flat fields."""
    flat = {
        "model": model.name,
        "model_id": model.id,
        "provider": model.provider,
        "effort_level": model.effort_level or "default",
        "session_id": result.session_id,
        "turns": result.total_turns,
        "computed_cost_usd": computed_cost_for_run(model, result),
        "reasoning_cost_multiplier": model.reasoning_cost_multiplier,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cache_read_tokens": result.cache_read_tokens,
        "cache_creation_tokens": result.cache_creation_tokens,
        "duration_s": (
            round(duration_s, 1)
            if duration_s is not None
            else round(result.duration_seconds, 1)
        ),
        "error": result.error,
        "timed_out": bool(result.error and "Timed out" in result.error),
        "tool_failures": list(result.tool_failures),
    }
    if phase_fields:
        flat.update(phase_fields)
    flat.update(_schema_v2_run_fields(model, result))
    return attach_schema_version(flat)


def error_measurement_defaults(model: ModelConfig) -> dict:
    """Return provider-aware flat defaults for a pre-result execution error.

    Legacy archives historically used numeric zeroes on this path, so those
    values remain for Anthropic/OpenRouter. A subscription route has no observed
    token telemetry or separately billed marginal charge, so null is required.
    """
    if model.provider == CHATGPT_PROVIDER:
        return {
            "computed_cost_usd": None,
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_creation_tokens": None,
        }
    return {
        "computed_cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
    }


def build_error_artifact(
    model: ModelConfig,
    test_case_id: str,
    rep: int,
    error_message: str,
    phase_fields: Optional[Mapping] = None,
) -> dict:
    """Build a schema-v2 error record without inventing subscription telemetry."""
    result = RunResult(
        test_case_id=test_case_id,
        model_id=model.id,
        model_name=model.name,
        run_index=rep,
        error=error_message,
        exit_code=1,
    )
    result.model_identity.benchmark_key = _model_key(model)
    result.model_identity.requested_model_id = model.id
    if model.provider == CHATGPT_PROVIDER:
        result.total_cost_usd = None
        accounting = compute_accounting(model, result)
        result.actual_billing = accounting["actual_billing"]
        result.api_equivalent = accounting["api_equivalent"]
        result.subscription_capacity = accounting["subscription_capacity"]

    record = build_run_artifact(
        model,
        result,
        phase_fields={"case_id": test_case_id, "rep": rep, **dict(phase_fields or {})},
        duration_s=0.0,
    )
    record.update(error_measurement_defaults(model))
    return record


def _numeric_values(values: Iterable[Optional[Real]]) -> list[Real]:
    """Select real, non-boolean, non-null values for monetary arithmetic."""
    return [
        value for value in values
        if isinstance(value, Real) and not isinstance(value, bool)
    ]


def nullable_total(values: Iterable[Optional[Real]]) -> Optional[Real]:
    """Sum observed numeric values, returning null when none are available."""
    observed = _numeric_values(values)
    return sum(observed) if observed else None


def nullable_mean(values: Iterable[Optional[Real]]) -> Optional[float]:
    """Average observed numeric values, returning null when none are available."""
    observed = _numeric_values(values)
    return sum(observed) / len(observed) if observed else None


def accounting_coverage(records: Iterable[Mapping]) -> dict[str, int]:
    """Count exact, scenario-only, unavailable, and legacy numeric records."""
    counts = {category: 0 for category in ACCOUNTING_CATEGORIES}
    for record in records:
        provider = record.get("provider", "anthropic")
        if provider != CHATGPT_PROVIDER:
            if isinstance(record.get("computed_cost_usd"), Real) and not isinstance(
                record.get("computed_cost_usd"), bool
            ):
                counts["legacy_numeric"] += 1
            else:
                counts["unavailable"] += 1
            continue

        equivalent = record.get("api_equivalent") or {}
        exact = equivalent.get("cost_usd")
        if isinstance(exact, Real) and not isinstance(exact, bool):
            counts["exact"] += 1
        elif any(
            isinstance(equivalent.get(key), Real)
            and not isinstance(equivalent.get(key), bool)
            for key in (
                "short_context_uncached_scenario_usd",
                "long_context_uncached_scenario_usd",
            )
        ):
            counts["scenario_only"] += 1
        else:
            counts["unavailable"] += 1
    return counts


def cost_summary(records: Iterable[Mapping]) -> dict:
    """Return nullable legacy totals/means plus explicit accounting coverage."""
    rows = list(records)
    costs = [row.get("computed_cost_usd") for row in rows]
    return {
        "total_cost_usd": nullable_total(costs),
        "avg_cost_usd": nullable_mean(costs),
        "accounting_coverage": accounting_coverage(rows),
    }


def console_billing_label(record: Mapping, precision: int = 3) -> str:
    """Render a truthful per-run billing label for legacy and subscription use."""
    if record.get("provider") != CHATGPT_PROVIDER:
        amount = record.get("computed_cost_usd")
        if isinstance(amount, Real) and not isinstance(amount, bool):
            return f"${amount:.{precision}f}"
        return "unavailable"

    equivalent = record.get("api_equivalent") or {}
    exact = equivalent.get("cost_usd")
    if isinstance(exact, Real) and not isinstance(exact, bool):
        if exact == 0:
            return (
                "included subscription capacity; API-equivalent calculation "
                "reflects zero observed usage (not invoiced)"
            )
        return (
            "included subscription capacity; "
            f"API-equivalent ${exact:.{precision}f} (not invoiced)"
        )
    short = equivalent.get("short_context_uncached_scenario_usd")
    long = equivalent.get("long_context_uncached_scenario_usd")
    scenarios = _numeric_values([short, long])
    if scenarios:
        low = min(scenarios)
        high = max(scenarios)
        if high == 0:
            return (
                "included subscription capacity; API-equivalent scenario "
                "reflects zero observed usage (not invoiced)"
            )
        return (
            "included subscription capacity; API-equivalent scenario "
            f"${low:.{precision}f}-${high:.{precision}f} (not invoiced)"
        )
    return "included subscription capacity; marginal charge unavailable"


def format_coverage(coverage: Mapping[str, int]) -> str:
    """Format stable accounting coverage counts for console output."""
    return ", ".join(
        f"{category}={coverage.get(category, 0)}"
        for category in ACCOUNTING_CATEGORIES
    )


def child_model_purity(
    transcript_paths: Iterable,
    requested_model_id: str,
) -> dict:
    """Evaluate child-model purity from safely observable transcript identity.

    The Claude CLI writes the model ID on child transcript assistant records at
    ``record.message.model``. This helper reads JSONL incrementally, observes only
    that identity field, and compares exact strings. No aliases are collapsed:
    the raw IDs are also the comparison IDs, which keeps the evidence auditable
    and avoids inventing a canonicalization rule that the backend has not
    confirmed.
    """
    paths = [Path(path) for path in transcript_paths]
    existing_paths = [path for path in paths if path.is_file()]
    observed_ids = []
    readable_transcript_count = 0

    for path in existing_paths:
        try:
            with open(path) as transcript:
                readable_transcript_count += 1
                for line in transcript:
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if not isinstance(record, dict) or record.get("type") != "assistant":
                        continue
                    message = record.get("message")
                    if not isinstance(message, dict):
                        continue
                    model_id = message.get("model")
                    if (
                        isinstance(model_id, str)
                        and model_id
                        and model_id not in observed_ids
                    ):
                        observed_ids.append(model_id)
        except OSError:
            continue

    if not existing_paths:
        purity_status = "unverifiable"
        incompleteness_reason = "no_child_transcript_exists"
    elif not observed_ids:
        purity_status = "unverifiable"
        incompleteness_reason = "child_transcripts_expose_no_model_id"
    elif all(model_id == requested_model_id for model_id in observed_ids):
        purity_status = "verified"
        incompleteness_reason = None
    else:
        purity_status = "failed"
        incompleteness_reason = None

    return {
        "requested_child_model_id": requested_model_id,
        "observed_child_model_ids_raw": observed_ids,
        "comparison_child_model_ids": list(observed_ids),
        "normalization_applied": False,
        "comparison_rule": "exact_string_equality_no_alias_normalization",
        "purity_status": purity_status,
        "evidence_source": PURITY_EVIDENCE_SOURCE,
        "evidence_boundary": PURITY_EVIDENCE_BOUNDARY,
        "child_transcript_count": len(existing_paths),
        "readable_child_transcript_count": readable_transcript_count,
        "incompleteness_reason": incompleteness_reason,
    }


def purity_coverage(records: Iterable[Mapping]) -> dict[str, int]:
    """Count Phase-3 child-model purity states without hiding missing evidence."""
    counts = {status: 0 for status in PURITY_STATUSES}
    for record in records:
        evidence = record.get("child_model_purity") or {}
        status = evidence.get("purity_status", "unverifiable")
        if status not in counts:
            status = "unverifiable"
        counts[status] += 1
    return counts


def add_preflight_arg(parser: argparse.ArgumentParser) -> None:
    """Register the common zero-execution route-preflight CLI flag."""
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "Validate selected provider routes, then exit without estimates, "
            "checkpoints, sandboxes, model execution, or result artifacts"
        ),
    )


def run_preflight(models: Iterable[ModelConfig], preflight_only: bool = False) -> bool:
    """Run batch route preflight and report whether the caller must stop.

    Route contract failures exit nonzero with a concise message. A successful
    ``--preflight-only`` call returns ``True`` so the runner can return before
    any estimate, checkpoint, sandbox, executor, or archive path is reached.
    """
    selected = list(models)
    try:
        snapshots = preflight_models(selected)
    except RouteContractError as exc:
        print(f"ERROR: Provider route preflight failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if snapshots:
        providers = sorted({model.provider for model in selected})
        print(
            "Provider route preflight passed: "
            f"{len(snapshots)} model(s); providers={','.join(providers)}"
        )
    else:
        print("Provider route preflight passed: no live route check required")

    if preflight_only:
        print("Preflight-only complete; no benchmark execution or artifacts created.")
        return True
    return False
