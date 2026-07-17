#!/usr/bin/env python3
"""One-turn DAAFBench probe for the deployed ChatGPT-subscription model route.

The probe reuses the benchmark registry, fail-closed route preflight, executor,
and schema-v2 accounting helpers. It requests no tool work, caps the fresh
session at one turn, and archives both successful and failed executions beneath
the gitignored benchmark results tree. A route preflight failure or declined
capacity confirmation creates no probe artifact.
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/daaf")

from benchmarks.harness.artifacts import (
    SCHEMA_VERSION,
    build_run_artifact,
    console_billing_label,
    model_manifest_entry,
    run_preflight,
)
from benchmarks.harness.executor import execute_run
from benchmarks.harness.model_loader import filter_models, load_models
from benchmarks.harness.models import ModelConfig, RunConfig, RunResult, TestCase
from benchmarks.harness.route_provenance import CHATGPT_PROVIDER


BASE_DIR = Path("/daaf")
MODELS_FILE = BASE_DIR / "benchmarks" / "config" / "models.yaml"
RESULTS_DIR = BASE_DIR / "benchmarks" / "results" / "probes"
DEFAULT_MODEL_KEY = "gpt-56-luna-chatgpt"
DEFAULT_EXPECTED_TEXT = "LUNA_PROBE_OK"
PROBE_TIMEOUT_SECONDS = 120

# The existing executor supports an explicit --disallowed-tools list. These are
# the standard built-in tools relevant to a one-turn DAAF session. The prompt
# also requests no tool work. This is intentionally not described as proof that
# every possible extension/MCP tool is technically unavailable.
DISALLOWED_BUILTIN_TOOLS = [
    "Agent",
    "AskUserQuestion",
    "Bash",
    "Edit",
    "Glob",
    "Grep",
    "NotebookEdit",
    "Read",
    "Skill",
    "WebFetch",
    "WebSearch",
    "Write",
]

COMPARISON_RULE = "response_text.strip() == expected_text"
EVIDENCE_BOUNDARY = (
    "A passing probe shows that the deployed DAAF path accepted the requested "
    "model slug and returned the expected response. It does not prove that the "
    "private ChatGPT backend performed no internal alias resolution. Requested, "
    "Claude-CLI-observed, and backend-confirmed model identities are separate "
    "evidence fields; a null backend-confirmed identity is not proof of identity."
)


# --- CLI and selection ---

def build_parser() -> argparse.ArgumentParser:
    """Build the parser without loading models, checking health, or executing."""
    parser = argparse.ArgumentParser(
        description=(
            "Run one fresh-session, one-turn route probe through the deployed "
            "DAAF ChatGPT-subscription shim path"
        )
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_KEY,
        help=(
            "One chatgpt-subscription registry key "
            f"(default: {DEFAULT_MODEL_KEY}); comma-separated values are rejected"
        ),
    )
    parser.add_argument(
        "--expect-text",
        default=DEFAULT_EXPECTED_TEXT,
        help=f"Exact response text expected after stripping (default: {DEFAULT_EXPECTED_TEXT})",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the ChatGPT-subscription capacity confirmation prompt",
    )
    return parser


def validate_model_argument(parser: argparse.ArgumentParser, value: str) -> str:
    """Require one nonempty registry key, never a comma-separated model list."""
    model_key = value.strip()
    if not model_key:
        parser.error("--model must name exactly one registry key")
    if "," in model_key:
        parser.error("--model accepts exactly one value; comma-separated models are not allowed")
    if any(character.isspace() for character in model_key):
        parser.error("--model accepts one registry key without whitespace")
    return model_key


def select_probe_model(
    parser: argparse.ArgumentParser,
    registry: dict[str, ModelConfig],
    model_key: str,
) -> ModelConfig:
    """Select exactly one ChatGPT-subscription model through shared filtering."""
    selected = filter_models(registry, model_keys=[model_key])
    if len(selected) != 1:
        parser.error(f"unknown or unavailable model registry key: {model_key}")
    model = selected[0]
    if model.provider != CHATGPT_PROVIDER:
        parser.error(
            f"model '{model_key}' uses provider '{model.provider}'; "
            f"the route probe requires provider '{CHATGPT_PROVIDER}'"
        )
    return model


# --- Probe contract ---

def build_probe_prompt(expected_text: str) -> str:
    """Build a deterministic, no-tool-work request for the exact expected text."""
    encoded = json.dumps(expected_text, ensure_ascii=False)
    return (
        "This is a one-turn route-selection probe. Do not use tools or perform "
        "any other work. Reply with exactly the JSON string value below, without "
        "quotation marks, code fences, explanation, or surrounding text.\n"
        f"Expected value: {encoded}"
    )


def compare_response(response_text: object, expected_text: str) -> dict:
    """Apply the probe's exact stripped-response comparison semantics."""
    if not isinstance(response_text, str):
        return {
            "response_text": None,
            "stripped_response_text": None,
            "response_present": False,
            "comparison_rule": COMPARISON_RULE,
            "exact_match": False,
            "scorable": False,
        }
    stripped = response_text.strip()
    return {
        "response_text": response_text,
        "stripped_response_text": stripped,
        "response_present": bool(stripped),
        "comparison_rule": COMPARISON_RULE,
        "exact_match": stripped == expected_text,
        "scorable": bool(stripped),
    }


def build_run_config(model: ModelConfig, prompt: str) -> RunConfig:
    """Create one cold-start, one-turn executor configuration."""
    test_case = TestCase(
        id="model-route-probe",
        category="route_probe",
        subcategory="chatgpt_subscription_model_selection",
        prompt=prompt,
        expected={"text": DEFAULT_EXPECTED_TEXT},
        turn_limit=1,
        cost_tier="low",
    )
    return RunConfig(
        test_case=test_case,
        model=model,
        run_index=0,
        disallowed_tools=list(DISALLOWED_BUILTIN_TOOLS),
        working_dir=str(BASE_DIR),
        sandbox_dir=str(BASE_DIR / "benchmarks" / "_sandbox" / "route_probe"),
        timeout_override=PROBE_TIMEOUT_SECONDS,
    )


def _redact_error(error: object) -> str | None:
    """Redact common credential forms from executor diagnostics before archival."""
    if error is None:
        return None
    text = str(error)
    text = re.sub(
        r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+",
        r"\1 [REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)\b(api[_-]?key|auth(?:orization)?|token|secret)\b\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
    return text


def _identity_assessment(model: ModelConfig, result: RunResult) -> dict:
    """Describe identity evidence without collapsing observer boundaries."""
    observed = list(result.model_identity.claude_cli_model_usage_ids)
    mismatches = [model_id for model_id in observed if model_id != model.id]
    if mismatches:
        status = "mismatch"
    elif observed:
        status = "cli_observed_match"
    else:
        status = "cli_observation_unavailable"
    return {
        "assessment": status,
        "comparison_rule": "each available Claude-CLI-observed ID exactly equals requested wire ID",
        "evidence_boundary": (
            "Claude CLI modelUsage keys are CLI-observed, not backend-confirmed identity."
        ),
    }


def build_probe_artifact(
    model: ModelConfig,
    result: RunResult,
    prompt: str,
    expected_text: str,
) -> tuple[dict, bool]:
    """Build the schema-v2 probe artifact and return its pass/fail decision."""
    comparison = compare_response(result.response_text, expected_text)
    timed_out = bool(result.error and "Timed out" in result.error)
    identity = _identity_assessment(model, result)
    execution_error = _redact_error(result.error)
    execution_failed = bool(execution_error) or result.exit_code != 0
    turn_limit_respected = result.total_turns <= 1
    identity_consistent = identity["assessment"] == "cli_observed_match"
    passed = (
        not execution_failed
        and not timed_out
        and comparison["scorable"]
        and comparison["exact_match"]
        and turn_limit_respected
        and identity_consistent
    )

    common = build_run_artifact(model, result)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "daafbench_model_route_probe",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": passed,
        "model": model_manifest_entry(model),
        "requested": {
            "registry_key": model.key,
            "wire_model_id": model.id,
            "provider": model.provider,
        },
        "probe": {
            "prompt": prompt,
            "expected_text": expected_text,
            "turn_limit": 1,
            "fresh_session_requested": True,
            "tool_work_requested": False,
            "known_builtin_tools_disallowed": list(DISALLOWED_BUILTIN_TOOLS),
            "tool_availability_claim": (
                "No tool work was requested and standard built-in tools were disallowed; "
                "this artifact does not claim every possible extension tool was unavailable."
            ),
            "comparison": comparison,
        },
        "execution": {
            "error": execution_error,
            "timed_out": timed_out,
            "exit_code": result.exit_code,
            "turns_observed": result.total_turns,
            "turn_limit_respected": turn_limit_respected,
            "duration_seconds": result.duration_seconds,
            "wall_clock_seconds": result.wall_clock_seconds,
            "start_time_utc": result.start_time_utc,
            "end_time_utc": result.end_time_utc,
            "tool_failures": list(result.tool_failures),
        },
        "session": {
            "session_id": result.session_id or None,
            "transcript_reference": result.transcript_path or None,
            "transcript_reference_source": (
                "executor_exposed"
                if result.transcript_path
                else "unavailable_executor_did_not_expose_safe_path"
            ),
        },
        "provenance": common["provenance"],
        "model_identity": {
            **common["model_identity"],
            **identity,
        },
        "usage_observed": common["usage_observed"],
        "actual_billing": common["actual_billing"],
        "api_equivalent": common["api_equivalent"],
        "subscription_capacity": common["subscription_capacity"],
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }
    return artifact, passed


# --- Archival and output ---

def archive_probe(artifact: dict) -> Path:
    """Write a collision-resistant probe artifact beneath the ignored results tree."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output_dir = RESULTS_DIR / f"{timestamp}_{uuid.uuid4().hex[:12]}"
    output_dir.mkdir(parents=True, exist_ok=False)
    artifact_path = output_dir / "probe.json"
    with open(artifact_path, "w", encoding="utf-8") as output:
        json.dump(artifact, output, indent=2, ensure_ascii=False)
        output.write("\n")
    return artifact_path


def print_probe_summary(artifact_path: Path, artifact: dict) -> None:
    """Print the artifact path and a concise billing/provenance summary."""
    identity = artifact["model_identity"]
    provenance = artifact.get("provenance") or {}
    billing_record = {
        "provider": artifact["requested"]["provider"],
        "computed_cost_usd": None,
        "api_equivalent": artifact["api_equivalent"],
    }
    print(f"Probe artifact: {artifact_path}")
    print(
        "Route: "
        f"{provenance.get('route_type', 'unavailable')} | "
        f"backend_mode={provenance.get('backend_mode')} | "
        f"sanitizer_enabled={provenance.get('sanitizer_enabled')}"
    )
    print(
        "Model identity: "
        f"requested={identity['requested_model_id']} | "
        f"CLI-observed={identity['claude_cli_model_usage_ids']} | "
        f"backend-confirmed={identity['backend_confirmed_model_id']}"
    )
    print(f"Billing: {console_billing_label(billing_record)}")
    print(f"Evidence boundary: {EVIDENCE_BOUNDARY}")


# --- Main ---

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    model_key = validate_model_argument(parser, args.model)
    if not args.expect_text or not args.expect_text.strip():
        parser.error("--expect-text must contain non-whitespace text")

    registry = load_models(MODELS_FILE)
    model = select_probe_model(parser, registry, model_key)

    # Shared route preflight is zero model cost. Any mismatch exits before the
    # confirmation, executor, or artifact path.
    run_preflight([model], preflight_only=False)

    if not args.yes:
        answer = input(
            "This one-turn probe consumes ChatGPT-subscription capacity. "
            "Proceed? [y/N] "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            print("Probe declined; no model execution or probe artifact created.")
            return 1

    prompt = build_probe_prompt(args.expect_text)
    config = build_run_config(model, prompt)
    # Preserve the exact runtime expectation in the in-memory test case metadata.
    config.test_case.expected = {"text": args.expect_text}
    try:
        result = execute_run(config)
    except Exception as exc:
        # Execution has been authorized and begun, so preserve an auditable
        # failure artifact even if an unexpected executor exception escapes its
        # normal RunResult error path.
        result = RunResult(
            test_case_id=config.test_case.id,
            model_id=model.id,
            model_name=model.name,
            run_index=0,
            total_cost_usd=None,
            error=f"Execution error: {type(exc).__name__}: {exc}",
            exit_code=1,
        )
        result.model_identity.benchmark_key = model.key
        result.model_identity.requested_model_id = model.id
    artifact, passed = build_probe_artifact(model, result, prompt, args.expect_text)
    artifact_path = archive_probe(artifact)
    print_probe_summary(artifact_path, artifact)

    if passed:
        print("Probe result: PASS (exact stripped response match).")
        return 0

    comparison = artifact["probe"]["comparison"]
    if artifact["execution"]["timed_out"]:
        reason = "timeout"
    elif artifact["execution"]["error"] or artifact["execution"]["exit_code"] != 0:
        reason = "execution error"
    elif not comparison["scorable"]:
        reason = "missing or unscorable response"
    elif not comparison["exact_match"]:
        reason = "response mismatch"
    elif artifact["model_identity"]["assessment"] == "mismatch":
        reason = "CLI-observed model identity mismatch"
    elif artifact["model_identity"]["assessment"] == "cli_observation_unavailable":
        reason = "CLI-observed model identity unavailable"
    else:
        reason = "one-turn contract violation"
    print(f"Probe result: FAIL ({reason}).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
