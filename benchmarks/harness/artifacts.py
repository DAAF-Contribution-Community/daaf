"""Shared schema-v2 artifact, preflight, and null-accounting helpers.

The phase runners keep their phase-specific scoring and archive layouts. This
module owns only the fields and control flow that must mean the same thing in
every runner: provider/model metadata, route and usage evidence, billing
ledgers, nullable monetary summaries, and the zero-execution preflight gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
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

# Display-only relabel for accounting coverage console output. The internal
# accounting KEYS (ACCOUNTING_CATEGORIES) are a persisted summary.json contract
# read by generate_results_viewer_v2.py and asserted in tests, so they must not
# change. This map only rewrites how a category is LABELED in format_coverage()
# console text; keys not present pass through unchanged.
ACCOUNTING_CATEGORY_LABELS = {
    "legacy_numeric": "numeric_computed_cost",
}

# --- B2: child-model purity as an infrastructure validity gate ---
# Non-scoring. A purity-failed run is marked invalid and excluded from score
# rollups (never deleted); an unverifiable run stays valid but is disclosed via
# purity_coverage. Valid runs score exactly as before.
VALIDITY_STATUSES = ("valid", "invalid")
VALIDITY_INVALID_REASON = "child_model_purity_failed"

# --- B3: manifest provenance stamping (shared across all four runners) ---
# G1R condition identifiers. golden_generation_id records which golden
# generation a result set replayed; condition_id names the pinned G1R condition.
GOLDEN_GENERATION_ID = "G1"
CONDITION_ID = "G1R-python-2026-07"
# SHA-256 of the empty byte string. `git diff HEAD` on a clean worktree emits no
# bytes, so worktree_diff_sha256 equals this constant when the tree is clean.
EMPTY_DIFF_SHA256 = hashlib.sha256(b"").hexdigest()
PURITY_EVIDENCE_SOURCE = "child_transcript_assistant_message.model"
PURITY_EVIDENCE_BOUNDARY = (
    "Claude CLI child-transcript-observed model identity; not backend-confirmed"
)


def attach_schema_version(payload: Mapping) -> dict:
    """Return an additive schema-v2 copy without mutating the caller's mapping."""
    artifact = dict(payload)
    artifact["schema_version"] = SCHEMA_VERSION
    return artifact


def sandbox_slug(model_name: str) -> str:
    """Return a shell-safe sandbox-suffix slug for a model display name.

    The `_sandbox/run_<suffix>` directory name is interpolated into shell
    command lines by the harness; display names carry characters that are
    hostile to the shell — notably parentheses (e.g. "GPT-5.6 Luna (ChatGPT
    Subscription)"), which produce `syntax error near unexpected token '('`.
    Collapse every character outside the safe set [A-Za-z0-9._-] to a single
    underscore, coalescing runs, and trim leading/trailing underscores.

    Slugging affects ONLY the sandbox directory name (new runs). The display
    name is preserved verbatim everywhere else (manifests, result.json `model`
    field, results-dir naming), so this is not an identity change.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", model_name)
    return slug.strip("_")


def assert_unique_sandbox_slugs(models) -> None:
    """Fail fast if any two selected models slug to the same sandbox suffix.

    ``sandbox_slug`` collapses shell-hostile characters to underscores, so two
    distinct display names can collide onto one slug (e.g. "GPT-5.6 (A)" and
    "GPT-5.6 [A]" both → "GPT-5.6_A_"). Colliding slugs share a ``_sandbox/run_*``
    directory, cross-contaminating fixtures and transcripts between runs. Called
    once at batch start (after model selection) so the collision surfaces as a
    clear, named error instead of silent data corruption downstream.
    """
    seen = {}
    for m in models:
        slug = sandbox_slug(m.name)
        if slug in seen:
            raise SystemExit(
                f"ERROR: sandbox_slug collision — models {seen[slug]!r} and "
                f"{m.name!r} both slug to {slug!r}. Rename one display name so "
                f"their _sandbox/run_* directories do not collide."
            )
        seen[slug] = m.name


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
        # The declared wire identity (purity comparison target). Recorded
        # alongside the routing id so a result set is self-documenting about
        # which string the child-model purity gate compared against. None for
        # entries whose wire form equals their routing id.
        "wire_id": model.wire_id,
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


def _run_status(result: RunResult) -> str:
    """Derive the single run-lifecycle status string for a result.json record.

    Precedence (most specific first): an early stop and a stall are terminal
    watchdog outcomes and win over the generic error/timeout classification. The
    exact strings "completed_early" and "stalled" are contract with the viewer
    (which substitutes score_complete_seconds for completed_early runs in duration
    aggregates when present, else excludes them) and the README.
    """
    if getattr(result, "early_stopped", False):
        return "completed_early"
    if getattr(result, "stalled", False):
        return "stalled"
    if result.error and "Timed out" in result.error:
        return "timed_out"
    if result.error:
        return "error"
    return "completed"


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
        # Run-lifecycle flags + a single derived status string (Dispatch B). The
        # viewer keys duration/latency handling on status == "completed_early",
        # substituting score_complete_seconds when present (else excluding the run);
        # None-safe getattr keeps this working for any RunResult built before the
        # watchdog fields existed (e.g. legacy callers, error artifacts).
        "early_stopped": bool(getattr(result, "early_stopped", False)),
        "stalled": bool(getattr(result, "stalled", False)),
        "stall_diagnostics": dict(getattr(result, "stall_diagnostics", {}) or {}),
        # Comparable duration for early-stopped runs (time-to-demonstrated-
        # compliance; None otherwise). The viewer substitutes this for duration_s
        # on completed_early runs in duration/latency aggregates (README § 8).
        # getattr keeps this None-safe for RunResults built before the field existed.
        "score_complete_seconds": getattr(result, "score_complete_seconds", None),
        "status": _run_status(result),
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
    """Format stable accounting coverage counts for console output.

    Display-only: the persisted accounting keys are unchanged; only the
    human-facing label is rewritten via ACCOUNTING_CATEGORY_LABELS.
    """
    return ", ".join(
        f"{ACCOUNTING_CATEGORY_LABELS.get(category, category)}"
        f"={coverage.get(category, 0)}"
        for category in ACCOUNTING_CATEGORIES
    )


def _is_non_model_marker(value: str) -> bool:
    """True for CLI placeholder markers that are not model identities.

    # INTENT: keep non-model strings out of the model-identity tally.
    # REASONING: the Claude CLI writes ``"<synthetic>"`` into
    #   ``message.model`` on locally fabricated assistant records — most
    #   commonly usage-limit / spend-cap error stubs ("You've hit your org's
    #   monthly spend limit."). That is a stub marker, not a routing outcome,
    #   so counting it as an observed model id turns a genuinely on-model run
    #   into a purity failure and silently discards the run from all rollups.
    # ASSUMES: the CLI's angle-bracket convention (``<...>``) marks placeholders
    #   and no real model slug is ever angle-bracketed. The rule is deliberately
    #   kept to that one narrow shape rather than a broader heuristic: a real
    #   slug that somehow arrived bracketed would be surfaced verbatim in
    #   ``observed_non_model_markers``, never dropped from the artifact.
    """
    return len(value) > 2 and value.startswith("<") and value.endswith(">")


def child_model_purity(
    transcript_paths: Iterable,
    requested_model_id: str,
    wire_model_id: Optional[str] = None,
) -> dict:
    """Evaluate child-model purity from safely observable transcript identity.

    The Claude CLI writes the model ID on child transcript assistant records at
    ``record.message.model``. This helper reads JSONL incrementally, observes
    only that identity field, and compares exact strings. No aliases are
    collapsed and no observed string is rewritten, which keeps the evidence
    auditable and avoids inventing a canonicalization rule that the backend has
    not confirmed.

    Comparison target
    -----------------
    ``requested_model_id`` is the ROUTING SELECTOR handed to ``claude --model``.
    ``wire_model_id`` is the identity that model is *declared* (in models.yaml)
    to report on the wire; when omitted it defaults to ``requested_model_id``.
    The comparison runs against the wire id, because several registry entries
    pin a provider/quantization in the routing selector (e.g.
    ``deepseek/deepseek-v4-flash:atlas-cloud/fp8``) while the CLI writes only
    the bare slug into transcripts. Comparing the routing selector against the
    wire form failed on the string mismatch alone, even for perfectly on-model
    children. Declaring the expected wire form per model — rather than deriving
    it by stripping the suffix — keeps the "no invented canonicalization" rule
    intact, and ``normalization_applied`` stays truthfully ``False``.

    EVIDENCE BOUNDARY — what this can and cannot establish
    ------------------------------------------------------
    The wire form carries **no provider/quant suffix at all**. Transcript-
    observed purity can therefore verify the **model** only; it can NEVER verify
    the **provider pin** or the **quantization** a pinned entry routes to. A run
    whose ``purity_status`` is ``verified`` asserts "the child reported the
    expected model slug", not "the child was served by the pinned
    provider/quant". No quant-level or provider-level purity is being checked
    here, and none should be inferred from this artifact. Confirming a provider
    pin would require backend-side evidence this observer does not have.

    Non-model markers
    -----------------
    Strings matching the CLI's angle-bracket placeholder shape (see
    ``_is_non_model_marker``; ``<synthetic>`` is the known instance) are not
    model identities and are excluded from the comparison tally. They are never
    discarded: they remain in ``observed_child_model_ids_raw`` and are listed
    separately in ``observed_non_model_markers``. If real model ids remain after
    filtering and all of them match, the run is ``verified`` — positive
    on-model evidence is not thrown away because a billing stub shared the
    transcript. If nothing but markers was observed, the result is
    ``unverifiable`` (no evidence either way), never ``failed``.
    """
    # INTENT: compare against the declared wire identity, not the routing id.
    # ASSUMES: callers that pass only two arguments have a model whose wire
    #   identity equals its routing id (every bare-slug registry entry).
    comparison_target_id = wire_model_id or requested_model_id

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

    # INTENT: partition raw observations into model identities vs. placeholders.
    # REASONING: both partitions are reported. The raw list stays complete so a
    #   reader can always reconstruct what the transcript actually contained;
    #   only the comparison tally is narrowed.
    non_model_markers = [
        model_id for model_id in observed_ids if _is_non_model_marker(model_id)
    ]
    comparison_ids = [
        model_id for model_id in observed_ids if not _is_non_model_marker(model_id)
    ]

    if not existing_paths:
        purity_status = "unverifiable"
        incompleteness_reason = "no_child_transcript_exists"
    elif not observed_ids:
        purity_status = "unverifiable"
        incompleteness_reason = "child_transcripts_expose_no_model_id"
    elif not comparison_ids:
        # Only placeholders were observed: no model-identity evidence exists in
        # either direction, so this is an absence of evidence (unverifiable),
        # not evidence of an off-model child (failed). The validity gate treats
        # unverifiable as valid, which is the correct outcome here.
        purity_status = "unverifiable"
        incompleteness_reason = (
            "child_transcripts_expose_only_non_model_markers:"
            + ",".join(non_model_markers)
        )
    elif all(model_id == comparison_target_id for model_id in comparison_ids):
        # At least one real model id remains and every one of them matches.
        # Markers, if any, are recorded but do not gate the run invalid.
        purity_status = "verified"
        incompleteness_reason = None
    else:
        # A genuine mismatch among real model ids. The gate is unchanged.
        purity_status = "failed"
        incompleteness_reason = None

    return {
        # The routing selector actually handed to `claude --model`.
        "requested_child_model_id": requested_model_id,
        # The declared wire identity the observations were compared against.
        # Equal to requested_child_model_id unless models.yaml declares wire_id.
        "comparison_target_child_model_id": comparison_target_id,
        "wire_id_declared": comparison_target_id != requested_model_id,
        # Every distinct string observed, markers included — never pruned.
        "observed_child_model_ids_raw": observed_ids,
        # The subset actually compared (raw minus non-model markers).
        "comparison_child_model_ids": comparison_ids,
        "observed_non_model_markers": non_model_markers,
        "non_model_marker_rule": "angle_bracketed_cli_placeholder_excluded_from_tally",
        # Still truthfully False: no observed string is rewritten or collapsed.
        # The expected wire form is declared per model, not derived.
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


def run_validity(record: Mapping) -> dict:
    """Derive an infrastructure validity verdict from child-model purity (B2).

    This is a validity gate, not a scored criterion. It reads the run's already
    computed ``child_model_purity`` evidence and returns an explicit verdict:

    - ``failed`` purity  -> ``invalid``: the run is excluded from score rollups
      (but never deleted — the record and its criteria are retained for audit).
    - ``unverifiable`` / ``verified`` / absent -> ``valid``: scored exactly as
      before. Unverifiable counts are disclosed separately via purity_coverage.

    No ``CriterionResult`` is added or changed; behavioral scores of valid runs
    are identical to the pre-gate behavior.
    """
    purity = record.get("child_model_purity") or {}
    if purity.get("purity_status") == "failed":
        return {"status": "invalid", "reason": VALIDITY_INVALID_REASON}
    return {"status": "valid", "reason": None}


def validity_coverage(records: Iterable[Mapping]) -> dict[str, int]:
    """Count valid vs. invalid runs for summary disclosure (B2).

    A missing ``validity`` field is treated as ``valid`` — only an explicit
    invalid marking (purity-failed) excludes a run from score rollups.
    """
    counts = {status: 0 for status in VALIDITY_STATUSES}
    for record in records:
        status = (record.get("validity") or {}).get("status", "valid")
        if status not in counts:
            status = "valid"
        counts[status] += 1
    return counts


def is_scorable(record: Mapping) -> bool:
    """Return True unless the run was gated invalid by the B2 purity gate."""
    return (record.get("validity") or {}).get("status", "valid") != "invalid"


def _git_output_bytes(args: Iterable[str], base_dir: str) -> Optional[bytes]:
    """Run a read-only git command, returning stdout bytes or None on failure."""
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            timeout=30,
            cwd=base_dir,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_worktree_state(base_dir: str = "/daaf") -> tuple[Optional[bool], Optional[str]]:
    """Return ``(git_dirty, worktree_diff_sha256)`` for the DAAF worktree (B3).

    ``git_dirty`` is True when ``git status --porcelain`` is non-empty.
    ``worktree_diff_sha256`` is the SHA-256 of the raw ``git diff HEAD`` bytes;
    a clean worktree emits no bytes, so the hash equals ``EMPTY_DIFF_SHA256``.
    On any git failure both fall back to ``None`` so provenance never fabricates
    a false "clean" signal.
    """
    status = _git_output_bytes(["status", "--porcelain"], base_dir)
    diff = _git_output_bytes(["diff", "HEAD"], base_dir)
    if status is None or diff is None:
        return None, None
    dirty = bool(status.strip())
    diff_sha = hashlib.sha256(diff).hexdigest()
    return dirty, diff_sha


def golden_checksums(
    golden_checkpoints: Iterable[Optional[str]],
    base_dir: str = "/daaf",
) -> dict[str, Optional[str]]:
    """Map each repo-relative golden path to the SHA-256 of its bytes (B3).

    Falsy paths (e.g. checkpoint-free mode classification) are skipped, yielding
    an empty map. An unreadable golden maps to None rather than being omitted.
    """
    checksums: dict[str, Optional[str]] = {}
    for rel in sorted({c for c in golden_checkpoints if c}):
        path = Path(base_dir) / rel
        try:
            checksums[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            checksums[rel] = None
    return checksums


def claude_code_version() -> Optional[str]:
    """Return the ``claude --version`` string, or None on any failure (B3)."""
    try:
        proc = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def manifest_provenance(
    golden_checkpoints: Iterable[Optional[str]] = (),
    run_records: Iterable[Mapping] = (),
    base_dir: str = "/daaf",
) -> dict:
    """Build the shared additive manifest provenance block for all runners (B3).

    Returns dirty-tree state, worktree diff hash, golden generation id and
    per-golden checksums, the pinned G1R condition id, the Claude Code version,
    and manifest-level route provenance reused from the first run record that
    already captured one (never a divergent second /health call — the per-run
    ``provenance`` was produced by ``route_provenance`` at execution time).
    """
    dirty, diff_sha = git_worktree_state(base_dir)
    route_provenance = None
    for record in run_records:
        candidate = record.get("provenance")
        if candidate:
            route_provenance = candidate
            break
    return {
        "git_dirty": dirty,
        "worktree_diff_sha256": diff_sha,
        "golden_generation_id": GOLDEN_GENERATION_ID,
        "golden_checksums": golden_checksums(golden_checkpoints, base_dir),
        "condition_id": CONDITION_ID,
        "claude_code_version": claude_code_version(),
        "route_provenance": route_provenance,
    }


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
