"""Data models for the DAAF Framework Adherence Benchmark harness.

Defines the core dataclasses used throughout the benchmark pipeline:
TestCase, RunConfig, RunResult, ScoredResult, and ModelConfig.
"""

from dataclasses import dataclass, field
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
class ModelConfig:
    """Configuration for a model to benchmark."""

    id: str
    name: str
    cost_tier: str = "medium"
    env_overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ModelConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RunConfig:
    """Configuration for a single benchmark run."""

    test_case: TestCase
    model: ModelConfig
    run_index: int
    permission_mode: str = "dontAsk"
    working_dir: str = "/daaf"
    sandbox_dir: str = "/daaf/benchmarks/_sandbox"


@dataclass
class RunResult:
    """Raw result from executing a single benchmark run."""

    test_case_id: str
    model_id: str
    model_name: str
    run_index: int
    session_id: str = ""
    total_turns: int = 0
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    response_text: str = ""
    raw_json: dict = field(default_factory=dict)
    audit_entries: list[dict] = field(default_factory=list)
    transcript_path: str = ""
    files_created: list[str] = field(default_factory=list)
    error: Optional[str] = None
    exit_code: int = 0

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
            "response_text": self.response_text[:500],
            "audit_entry_count": len(self.audit_entries),
            "transcript_path": self.transcript_path,
            "files_created": self.files_created,
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
