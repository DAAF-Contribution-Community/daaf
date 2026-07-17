"""Data models for the DAAF Framework Adherence Benchmark harness.

Defines the core dataclasses used throughout the benchmark pipeline:
TestCase, RunConfig, RunResult, ScoredResult, and ModelConfig.
"""

from dataclasses import asdict, dataclass, field
from typing import Optional
import json
from pathlib import Path


@dataclass
class TestCase:
    """A single benchmark test case loaded from a JSONL dataset file."""

    id: str
    category: str
    prompt: str
    expected: dict
    subcategory: str = ""
    golden_checkpoint: Optional[str] = None
    golden_project_path: Optional[str] = None
    auto_replies: list[dict] = field(default_factory=list)
    turn_limit: int = 5
    cost_tier: str = "low"
    hard_requirements: list[str] = field(default_factory=list)
    soft_requirements: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def load_from_jsonl(cls, path: Path) -> list["TestCase"]:
        cases = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    cases.append(cls.from_dict(json.loads(line)))
        return cases


@dataclass
class PricingConfig:
    """Per-million-token pricing for cost estimation."""

    input: float = 0.0
    output: float = 0.0
    cached_input: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "PricingConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def estimate_cost(self, input_tokens: int, output_tokens: int,
                      cached_input_tokens: int = 0,
                      cache_creation_tokens: int = 0) -> float:
        """Estimate cost from token counts.

        IMPORTANT: input_tokens from the CLI is already the UNCACHED count.
        cached_input_tokens is a separate, additive count. Total input
        tokens billed = input_tokens + cached_input_tokens +
        cache_creation_tokens.

        Cache-write billing added 2026-06-11: cache_creation_tokens are billed
        at 1.25x the input rate (Anthropic's cache-write convention). The
        OpenRouter billing reconciliation of 2026-06-11 showed that omitting
        cache writes understated Anthropic-side costs ~3x against Anthropic's
        own billing convention (cache-write spend dominates subagent-heavy
        runs). No separate config rate is introduced — 1.25 x input is derived
        in-formula. Affects newly computed costs only; archived result.json
        values are immutable and not recomputed.
        """
        cost = (input_tokens * self.input + output_tokens * self.output) / 1_000_000
        if self.cached_input is not None and cached_input_tokens > 0:
            cost += (cached_input_tokens * self.cached_input) / 1_000_000
        else:
            cost += (cached_input_tokens * self.input) / 1_000_000
        cost += (cache_creation_tokens * self.input * 1.25) / 1_000_000
        return cost


@dataclass
class ModelConfig:
    """Configuration for a model to benchmark.

    ``key`` is optional so historical entries retain their name-derived
    selectable keys. ``context_window_tokens`` is route metadata and is applied
    to the child process by the executor; it is deliberately not encoded in the
    wire model identifier.
    """

    id: str
    name: str
    cost_tier: str = "medium"
    effort_level: Optional[str] = None
    provider: str = "anthropic"
    pricing: Optional[PricingConfig] = None
    reasoning_cost_multiplier: float = 1.0
    env_overrides: dict[str, str] = field(default_factory=dict)
    # New fields are appended after the historical positional constructor
    # surface so existing ModelConfig(id, name, cost_tier, ...) calls keep their
    # meaning.
    key: Optional[str] = None
    context_window_tokens: Optional[int] = None
    actual_billing_treatment: Optional[str] = None
    api_equivalent_pricing: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ModelConfig":
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "pricing" in filtered and isinstance(filtered["pricing"], dict):
            filtered["pricing"] = PricingConfig.from_dict(filtered["pricing"])
        return cls(**filtered)


@dataclass
class RunConfig:
    """Configuration for a single benchmark run."""

    test_case: TestCase
    model: ModelConfig
    run_index: int
    permission_mode: str = "bypassPermissions"
    # Git-write prevention is handled by the env-gated PreToolUse hook
    # (harness/hooks/block-git-writes.sh, activated via DAAF_BENCHMARK_RUN=1
    # in executor.py). The --disallowed-tools git patterns formerly listed
    # here were ineffective: Claude Code splits compound commands on shell
    # operators and leading-* globs are prefix-anchored (README § 11).
    disallowed_tools: list[str] = field(default_factory=list)
    working_dir: str = "/daaf"
    sandbox_dir: str = "/daaf/benchmarks/_sandbox"
    # When False, prepare_sandbox() skips its rmtree+recreate of sandbox_dir.
    # Used by runners that stage fixtures into the sandbox before execute_run()
    # (run_dispatch_compliance.py wipes the sandbox itself, then stages).
    # Default True preserves the original behavior for all other runners.
    wipe_sandbox: bool = True
    timeout_override: Optional[int] = None


@dataclass
class RouteProvenance:
    """Allowlisted, secret-safe snapshot of a benchmark provider route."""

    route_type: Optional[str] = None
    provider: Optional[str] = None
    endpoint_origin: Optional[str] = None
    backend_mode: Optional[str] = None
    backend: Optional[str] = None
    shim_version: Optional[str] = None
    sanitizer_enabled: Optional[bool] = None
    sanitizer_condition: Optional[str] = None
    auth_store_readable: Optional[bool] = None
    reasoning_effort: Optional[str] = None
    text_verbosity: Optional[str] = None
    captured_at: Optional[str] = None


@dataclass
class ModelIdentityEvidence:
    """Model identity evidence, separated by what each observer can establish."""

    benchmark_key: Optional[str] = None
    requested_model_id: Optional[str] = None
    claude_cli_model_usage_ids: list[str] = field(default_factory=list)
    backend_confirmed_model_id: Optional[str] = None


@dataclass
class UsageObserved:
    """Nullable token observations plus their source and field semantics."""

    input_tokens: Optional[int] = None
    input_semantics: Optional[str] = None
    input_includes_cache_tokens: Optional[bool] = None
    output_tokens: Optional[int] = None
    output_includes_reasoning: Optional[bool] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    max_request_input_tokens: Optional[int] = None
    pricing_context_tier: Optional[str] = None
    cli_model_usage: dict[str, dict[str, Optional[int]]] = field(default_factory=dict)
    source: Optional[str] = None
    completeness: str = "unavailable"
    incompleteness_reasons: list[str] = field(default_factory=list)


@dataclass
class ActualBilling:
    """Observed billing treatment; a null amount is distinct from a zero charge."""

    access_type: Optional[str] = None
    charge_status: str = "unknown"
    actual_marginal_charge_usd: Optional[float] = None


@dataclass
class ApiEquivalentAccounting:
    """Counterfactual API-list-price accounting, never an invoice."""

    cost_usd: Optional[float] = None
    calculation_status: str = "unavailable"
    short_context_uncached_scenario_usd: Optional[float] = None
    long_context_uncached_scenario_usd: Optional[float] = None
    scenario_assumptions: list[str] = field(default_factory=list)
    incompleteness_reasons: list[str] = field(default_factory=list)
    price_source_url: Optional[str] = None
    price_schedule_accessed_at: Optional[str] = None
    currency: str = "USD"
    context_threshold_input_tokens: Optional[int] = None
    context_tier: Optional[str] = None
    not_invoiced: Optional[bool] = None


@dataclass
class SubscriptionCapacity:
    """Optional provider allowance observations and calculated credit proxy."""

    before: Optional[float] = None
    after: Optional[float] = None
    delta_observed: Optional[float] = None
    credits_calculated: Optional[float] = None
    credit_usd_value: Optional[float] = None


@dataclass
class RunResult:
    """Raw result from executing a single benchmark run."""

    test_case_id: str
    model_id: str
    model_name: str
    run_index: int
    session_id: str = ""
    total_turns: int = 0
    total_cost_usd: Optional[float] = 0.0
    duration_seconds: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    response_text: str = ""
    raw_json: dict = field(default_factory=dict)
    audit_entries: list[dict] = field(default_factory=list)
    transcript_path: str = ""
    files_created: list[str] = field(default_factory=list)
    tool_failures: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    exit_code: int = 0
    # New telemetry is appended after the historical positional constructor
    # surface, preserving existing callers that instantiate RunResult positionally.
    wall_clock_seconds: Optional[float] = None
    start_time_utc: Optional[str] = None
    end_time_utc: Optional[str] = None
    route_provenance: Optional[RouteProvenance] = None
    model_identity: ModelIdentityEvidence = field(default_factory=ModelIdentityEvidence)
    usage_observed: UsageObserved = field(default_factory=UsageObserved)
    actual_billing: ActualBilling = field(default_factory=ActualBilling)
    api_equivalent: ApiEquivalentAccounting = field(default_factory=ApiEquivalentAccounting)
    subscription_capacity: SubscriptionCapacity = field(default_factory=SubscriptionCapacity)

    def to_dict(self) -> dict:
        return {
            "test_case_id": self.test_case_id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "run_index": self.run_index,
            "session_id": self.session_id,
            "total_turns": self.total_turns,
            "total_cost_usd": self.total_cost_usd,
            "duration_seconds": self.duration_seconds,
            "wall_clock_seconds": self.wall_clock_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "start_time_utc": self.start_time_utc,
            "end_time_utc": self.end_time_utc,
            "route_provenance": (
                asdict(self.route_provenance) if self.route_provenance else None
            ),
            "model_identity": asdict(self.model_identity),
            "usage_observed": asdict(self.usage_observed),
            "actual_billing": asdict(self.actual_billing),
            "api_equivalent": asdict(self.api_equivalent),
            "subscription_capacity": asdict(self.subscription_capacity),
            "response_text": self.response_text[:500],
            "audit_entry_count": len(self.audit_entries),
            "transcript_path": self.transcript_path,
            "files_created": self.files_created,
            "tool_failures": self.tool_failures,
            "error": self.error,
            "exit_code": self.exit_code,
        }


@dataclass
class CriterionResult:
    """Result for a single scoring criterion."""

    name: str
    passed: bool
    tier: str  # "tier1", "tier2", "tier3"
    detail: str = ""
    judge_reasoning: str = ""


@dataclass
class ScoredResult:
    """A RunResult with scoring applied."""

    run: RunResult
    criteria: list[CriterionResult] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.criteria if c.passed)

    @property
    def total_count(self) -> int:
        return len(self.criteria)

    @property
    def pass_rate(self) -> float:
        if not self.criteria:
            return 0.0
        return self.pass_count / self.total_count

    def hard_requirement_failures(self, hard_reqs: list[str]) -> list[str]:
        return [
            c.name for c in self.criteria
            if c.name in hard_reqs and not c.passed
        ]

    def to_dict(self) -> dict:
        return {
            "run": self.run.to_dict(),
            "criteria": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "tier": c.tier,
                    "detail": c.detail,
                }
                for c in self.criteria
            ],
            "pass_count": self.pass_count,
            "total_count": self.total_count,
            "pass_rate": self.pass_rate,
        }
