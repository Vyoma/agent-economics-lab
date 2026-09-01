from __future__ import annotations

import functools
import hashlib
import inspect
import json
import textwrap
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


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


class UnsuppliedEvidence(LookupError):
    """Raised when a check reads an input the operator never supplied."""


class Unsupplied:
    """An input the operator explicitly declared absent. Every read raises."""

    __slots__ = ("_what",)

    def __init__(self, what: str) -> None:
        object.__setattr__(self, "_what", what)

    def _refuse(self, detail: str) -> Any:
        raise UnsuppliedEvidence(
            f"{self._what} was not supplied, so any check requiring it cannot run "
            f"(reading {detail}). Supply it, or drop the coverage that needs it "
            f"from your required contract."
        )

    def __getattr__(self, name: str) -> Any:
        return self._refuse(f"{self._what}.{name}")

    def __getitem__(self, key: Any) -> Any:
        return self._refuse(f"{self._what}[{key!r}]")

    def __iter__(self) -> Any:
        return self._refuse(f"iter({self._what})")

    def __len__(self) -> int:
        return self._refuse(f"len({self._what})")

    def __bool__(self) -> bool:
        return self._refuse(f"bool({self._what})")

    def __repr__(self) -> str:
        return f"<unsupplied {self._what}>"


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


@functools.cache
def implementation_fingerprint(run: CheckFn) -> str:
    """Return a SHA-256 fingerprint of a check implementation's source text.

    Declared metadata alone cannot distinguish an enforcing gate from a
    same-named, same-coverage gate whose own body stopped enforcing anything.

    Scope, and it is narrow: this hashes the source of `run` itself and nothing
    that `run` calls. It is NOT transitive. Editing a shared helper the gates
    delegate to, such as `checks._result` or `assurance.percentile`, changes
    behaviour while leaving every fingerprint and the contract digest
    byte-identical. The digest therefore detects substitution of a check
    function, not tampering with the engine as a whole. Treat it as a
    reproducibility record for the checks, not as an integrity guarantee for the
    package.

    Normalization strips the common indent and per-line trailing whitespace so
    the value depends on source text rather than on nesting depth. It is
    deliberately not a signature: it proves that an implementation changed, not
    that any particular implementation is correct.

    Raises ValueError when source text is unavailable, so a check whose
    implementation cannot be fingerprinted cannot silently enter a contract.
    """
    try:
        source = inspect.getsource(run)
    except (OSError, TypeError) as error:
        raise ValueError(
            "Check implementations must have retrievable source text so the "
            "decision contract can bind them. Built-ins, C functions, "
            "functools.partial objects, and interactively defined callables "
            "cannot be fingerprinted; wrap the logic in a module-level "
            "function instead."
        ) from error
    normalized = "\n".join(
        line.rstrip() for line in textwrap.dedent(source).splitlines()
    ).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CheckSpec:
    id: str
    version: str
    mode: CheckMode
    covers: frozenset[Coverage]
    run: CheckFn
    failure_route: Decision | None = None
    #: The configuration this gate enforces, when its behaviour lives in
    #: captured arguments rather than in its source.
    #:
    #: `implementation_digest` hashes the source of `run`, which is the right
    #: thing for a plain function and blind for a closure. The two most
    #: consequential gates shipped here are factories: `delegation_closure_gate`
    #: and `evidence_provenance_gate` close over the thresholds and manifests
    #: that are their entire enforcement. A gate built with
    #: `minimum_closure=0.0` and no delegation tools cannot fail, and produced a
    #: contract digest byte-identical to the strict one -- the failure this
    #: package names as harder than a missing gate, arriving through closure
    #: arguments instead of through the gate list.
    #:
    #: Empty by default, and omitted from the manifest when empty, so a check
    #: whose behaviour is fully in its source is unaffected and the shipped
    #: contract digest does not move.
    config: Mapping[str, Any] = field(default_factory=dict)

    @property
    def manifest_id(self) -> str:
        return f"{self.id}@{self.version}"

    @property
    def implementation_digest(self) -> str:
        """Fingerprint of `run`, recorded in the decision-contract manifest.

        Two checks generated by the same factory share source text and
        therefore share this value. Closure arguments are not captured.
        """
        return implementation_fingerprint(self.run)


@dataclass(frozen=True)
class EvaluationView:
    events: tuple[TraceEvent, ...]
    dependency_edges: tuple[tuple[str, str], ...]
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


def _bundle_is_unsupplied(value: object) -> bool:
    """An input the operator explicitly declared absent, not a default."""
    return isinstance(value, Unsupplied)


def bundle_digest_of(
    events: tuple[TraceEvent, ...],
    outcomes: dict[str, Outcome],
    rates: dict[str, ModelRate],
    baseline: Baseline,
    policy: EconomicPolicy,
    task_manifest: dict[str, TaskIdentity],
    dependency_edges: tuple[tuple[str, str], ...],
    declared_delegations: tuple[str, ...] = (),
    label_source: str = "",
) -> str:
    payload = {
        "events": [asdict(event) for event in events],
        "outcomes": [asdict(outcomes[task_id]) for task_id in sorted(outcomes)],
        "rates": (
            {"unsupplied": "rates"}
            if _bundle_is_unsupplied(rates)
            else {name: asdict(rates[name]) for name in sorted(rates)}
        ),
        "baseline": (
            {"unsupplied": "baseline"} if _bundle_is_unsupplied(baseline) else asdict(baseline)
        ),
        "policy": (
            {"unsupplied": "policy"} if _bundle_is_unsupplied(policy) else asdict(policy)
        ),
    }
    if declared_delegations:
        payload["declared_delegations"] = list(declared_delegations)
    if label_source:
        payload["label_source"] = label_source
    if task_manifest:
        payload["task_manifest"] = [
            asdict(task_manifest[task_id]) for task_id in sorted(task_manifest)
        ]
    if dependency_edges:
        payload["dependency_edges"] = [list(edge) for edge in dependency_edges]
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EvidenceBundle:
    events: tuple[TraceEvent, ...]
    outcomes: dict[str, Outcome]
    rates: dict[str, ModelRate]
    baseline: Baseline
    policy: EconomicPolicy
    source_id: str
    source_version: str
    task_manifest: dict[str, TaskIdentity] = field(default_factory=dict)
    dependency_edges: tuple[tuple[str, str], ...] = ()
    # Delegating calls the operator declared in the conversion contract.
    declared_delegations: tuple[str, ...] = ()
    # The instrument that produced the outcome labels. Named, never invoked:
    # the verdict path stays inference-free.
    label_source: str = ""

    @property
    def digest(self) -> str:
        """Recomputed from contents on every read, never stored.

        It was a stored field, which made "tamper-evident" false. `outcomes`,
        `rates` and `task_manifest` are plain dicts, so mutating one in place
        needed no `dataclasses.replace` and left the digest untouched: flipping
        a single outcome to acceptable turned an ASSIST into a SCALE while the
        bundle still advertised the honest evidence's digest, and the engine
        republished that stale value into the assurance case it issued.
        """
        return bundle_digest_of(
            self.events,
            self.outcomes,
            self.rates,
            self.baseline,
            self.policy,
            self.task_manifest,
            self.dependency_edges,
            self.declared_delegations,
            self.label_source,
        )

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
    decision_contract_digest: str = ""
