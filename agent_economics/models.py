from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Decision(str, Enum):
    INCOMPLETE = "INCOMPLETE"
    SCALE = "SCALE"
    ASSIST = "ASSIST"
    STOP = "STOP"


class CheckMode(str, Enum):
    GATE = "gate"
    DIAGNOSTIC = "diagnostic"


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class Coverage(str, Enum):
    OUTCOME_QUALITY = "outcome_quality"
    UNIT_ECONOMICS = "unit_economics"
    TAIL_RISK = "tail_risk"
    BUSINESS_VALUE = "business_value"
    COUNTERFACTUAL = "counterfactual"
    RUNTIME_CAPS = "runtime_caps"


@dataclass(frozen=True)
class ModelRate:
    input_per_million_usd: float
    output_per_million_usd: float


@dataclass(frozen=True)
class TraceEvent:
    task_id: str
    event_id: str
    timestamp: str
    event_type: str
    name: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    direct_cost_usd: float | None = None
    status: str = "ok"
    arguments: Any = field(default_factory=dict)

    def cost(self, rates: dict[str, ModelRate]) -> float:
        if self.direct_cost_usd is not None:
            return self.direct_cost_usd
        if self.event_type != "model":
            return 0.0
        if self.model not in rates:
            raise ValueError(
                f"No rate for model {self.model!r} on event {self.event_id!r}; "
                "provide direct_cost_usd or add a rate"
            )
        rate = rates[self.model]
        return (
            self.input_tokens * rate.input_per_million_usd
            + self.output_tokens * rate.output_per_million_usd
        ) / 1_000_000


@dataclass(frozen=True)
class Outcome:
    task_id: str
    acceptable: bool
    business_value_usd: float = 0.0
    human_minutes: float = 0.0
    remediation_cost_usd: float = 0.0
    incident_loss_usd: float = 0.0


@dataclass(frozen=True)
class TaskIdentity:
    task_id: str
    input_digest: str
    rubric_version: str


@dataclass(frozen=True)
class Baseline:
    name: str
    cost_per_attempt_usd: float
    acceptable_rate: float
    value_per_acceptable_outcome_usd: float

    @property
    def cost_per_acceptable_outcome_usd(self) -> float:
        return self.cost_per_attempt_usd / self.acceptable_rate

    @property
    def expected_net_value_per_attempt_usd(self) -> float:
        return (
            self.acceptable_rate * self.value_per_acceptable_outcome_usd
            - self.cost_per_attempt_usd
        )


@dataclass(frozen=True)
class EconomicPolicy:
    human_hourly_cost_usd: float
    min_acceptable_rate: float
    max_cost_per_acceptable_outcome_usd: float
    max_p95_task_cost_usd: float
    max_trace_cost_per_task_usd: float
    max_calls_per_task: int
    min_expected_net_value_per_attempt_usd: float = 0.0
    min_incremental_net_value_vs_baseline_usd: float = 0.0
    repetition_warning_threshold: int = 3


@dataclass(frozen=True)
class TaskEconomics:
    task_id: str
    call_count: int
    trace_cost_usd: float
    human_cost_usd: float
    remediation_cost_usd: float
    incident_loss_usd: float
    effective_cost_usd: float
    acceptable: bool
    business_value_usd: float


@dataclass(frozen=True)
class ControlFinding:
    task_id: str
    control: str
    severity: str
    evidence: str
    interpretation: str


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: CheckStatus
    message: str
    on_failure: Decision | None = None
    task_id: str | None = None


@dataclass(frozen=True)
class CheckOutput:
    results: tuple[CheckResult, ...] = ()
    findings: tuple[ControlFinding, ...] = ()


CheckFn = Callable[["EvaluationView"], CheckOutput]


@dataclass(frozen=True)
class CheckSpec:
    id: str
    version: str
    mode: CheckMode
    covers: frozenset[Coverage]
    run: CheckFn

    @property
    def manifest_id(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass(frozen=True)
class EvaluationView:
    events: tuple[TraceEvent, ...]
    rates: dict[str, ModelRate]
    policy: EconomicPolicy
    baseline: Baseline
    tasks: tuple[TaskEconomics, ...]
    acceptable_rate: float
    total_effective_cost_usd: float
    cost_per_acceptable_outcome_usd: float
    p95_task_cost_usd: float
    max_task_cost_usd: float
    expected_net_value_per_attempt_usd: float
    incremental_net_value_vs_baseline_usd: float


@dataclass(frozen=True)
class EvidenceBundle:
    events: tuple[TraceEvent, ...]
    outcomes: dict[str, Outcome]
    rates: dict[str, ModelRate]
    baseline: Baseline
    policy: EconomicPolicy
    source_id: str
    source_version: str
    digest: str
    task_manifest: dict[str, TaskIdentity] = field(default_factory=dict)

    @property
    def source_manifest_id(self) -> str:
        return f"{self.source_id}@{self.source_version}"


@dataclass(frozen=True)
class AssuranceCase:
    decision: Decision
    tasks: tuple[TaskEconomics, ...]
    acceptable_rate: float
    total_effective_cost_usd: float
    cost_per_acceptable_outcome_usd: float
    p95_task_cost_usd: float
    max_task_cost_usd: float
    expected_net_value_per_attempt_usd: float
    incremental_net_value_vs_baseline_usd: float
    baseline: Baseline
    breaches: tuple[str, ...]
    findings: tuple[ControlFinding, ...]
    check_results: tuple[CheckResult, ...] = ()
    enabled_checks: tuple[str, ...] = ()
    required_coverage: tuple[str, ...] = ()
    missing_coverage: tuple[str, ...] = ()
    source_manifest_id: str = "source.legacy@1"
    evidence_digest: str = ""
