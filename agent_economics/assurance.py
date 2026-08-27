from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .evidence import make_evidence_bundle, validate_evidence_bundle
from .models import (
    AssuranceCase,
    Baseline,
    CheckMode,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Coverage,
    Decision,
    EconomicPolicy,
    EvaluationView,
    EvidenceBundle,
    ModelRate,
    Outcome,
    TaskEconomics,
    TraceEvent,
)

DECISION_CONTRACT_SCHEMA = "assurance.decision-contract@2"
ASSURANCE_ENGINE_IMPLEMENTATION = "agent-economics.assurance-engine@1"
ROUTING_SEMANTICS = "missing-coverage>stop>assist>scale@1"


def _coverage_name(coverage: object) -> str:
    """Name a dimension, whether it is a Coverage member or a plain string."""
    return coverage.value if isinstance(coverage, Coverage) else str(coverage)


def decision_contract_manifest(
    checks: Sequence[CheckSpec],
    required_coverage: frozenset[Coverage],
) -> dict[str, object]:
    """Return the canonical configuration that gives a green decision meaning.

    Each entry records an `implementation_digest` alongside the declared
    identity. Without it, a gate that keeps its ID, version, and coverage while
    silently ceasing to enforce anything produces a byte-identical contract
    digest. With it, substituting a permissive implementation is visible even
    though required coverage still appears satisfied.
    """
    return {
        "schema": DECISION_CONTRACT_SCHEMA,
        "implementation": ASSURANCE_ENGINE_IMPLEMENTATION,
        "routing_semantics": ROUTING_SEMANTICS,
        "required_coverage": sorted(_coverage_name(i) for i in required_coverage),
        "checks": [
            {
                "manifest_id": check.manifest_id,
                "mode": check.mode.value,
                "covers": sorted(_coverage_name(i) for i in check.covers),
                "failure_route": (
                    check.failure_route.value
                    if check.failure_route is not None
                    else ("dynamic" if check.mode is CheckMode.GATE else None)
                ),
                "implementation_digest": check.implementation_digest,
            }
            for check in checks
        ],
    }


def decision_contract_digest(
    checks: Sequence[CheckSpec],
    required_coverage: frozenset[Coverage],
) -> str:
    payload = decision_contract_manifest(checks, required_coverage)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile of an empty list")
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability must be in [0, 1], got {probability}")
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def _checked_sum(values: Sequence[float], label: str) -> float:
    """Sum with a typed refusal instead of a bare OverflowError.

    Each input can be individually finite and in range while the total is not
    representable. `math.fsum` raises `OverflowError` in that case, which would
    escape before the engine's non-finite guard runs, so a fail-closed
    architecture would emit a stdlib traceback rather than an explained refusal.
    """
    try:
        total = math.fsum(values)
    except OverflowError as error:
        raise ValueError(
            f"{label} overflows a float even though every input is finite. "
            "Check the cost units and the rate card."
        ) from error
    if not math.isfinite(total):
        raise ValueError(
            f"{label} is not finite even though every input is finite. "
            "Check the cost units and the rate card."
        )
    return total


def reconstruct_tasks(
    events: Sequence[TraceEvent],
    outcomes: dict[str, Outcome],
    rates: dict[str, ModelRate],
    policy: EconomicPolicy,
) -> tuple[TaskEconomics, ...]:
    by_task: dict[str, list[TraceEvent]] = defaultdict(list)
    for event in events:
        by_task[event.task_id].append(event)

    missing_outcomes = set(by_task) - set(outcomes)
    orphan_outcomes = set(outcomes) - set(by_task)
    if missing_outcomes:
        raise ValueError(f"Missing outcomes for tasks: {sorted(missing_outcomes)}")
    if orphan_outcomes:
        raise ValueError(f"Outcomes have no trace events: {sorted(orphan_outcomes)}")

    tasks: list[TaskEconomics] = []
    for task_id in sorted(by_task):
        task_events = by_task[task_id]
        outcome = outcomes[task_id]
        trace_cost = _checked_sum(
            [event.cost(rates) for event in task_events],
            f"trace cost for task {task_id!r}",
        )
        human_cost = outcome.human_minutes * policy.human_hourly_cost_usd / 60
        effective_cost = _checked_sum(
            (
                trace_cost,
                human_cost,
                outcome.remediation_cost_usd,
                outcome.incident_loss_usd,
            ),
            f"effective cost for task {task_id!r}",
        )
        tasks.append(
            TaskEconomics(
                task_id=task_id,
                call_count=len(task_events),
                trace_cost_usd=trace_cost,
                human_cost_usd=human_cost,
                remediation_cost_usd=outcome.remediation_cost_usd,
                incident_loss_usd=outcome.incident_loss_usd,
                effective_cost_usd=effective_cost,
                acceptable=outcome.acceptable,
                business_value_usd=(
                    outcome.business_value_usd if outcome.acceptable else 0.0
                ),
            )
        )
    return tuple(tasks)


def _validate_check_output(spec: CheckSpec, results: tuple[CheckResult, ...]) -> None:
    for result in results:
        if result.check_id != spec.id:
            raise ValueError(
                f"Check {spec.id!r} emitted result for {result.check_id!r}"
            )
        if spec.mode is CheckMode.DIAGNOSTIC and (
            result.status is CheckStatus.FAIL or result.on_failure is not None
        ):
            raise ValueError(
                f"Diagnostic {spec.id!r} cannot change the assurance decision"
            )
        if spec.mode is CheckMode.GATE:
            if result.status is CheckStatus.FAIL and result.on_failure not in {
                Decision.ASSIST,
                Decision.STOP,
            }:
                raise ValueError(
                    f"Failed gate {spec.id!r} must route to ASSIST or STOP"
                )
            if result.status is not CheckStatus.FAIL and result.on_failure is not None:
                raise ValueError(
                    f"Passing gate {spec.id!r} cannot have a failure consequence"
                )
            if (
                result.status is CheckStatus.FAIL
                and spec.failure_route is not None
                and result.on_failure is not spec.failure_route
            ):
                raise ValueError(
                    f"Gate {spec.id!r} declared route "
                    f"{spec.failure_route.value} but emitted "
                    f"{result.on_failure.value if result.on_failure else None}"
                )


@dataclass(frozen=True)
class AssuranceEngine:
    checks: tuple[CheckSpec, ...]
    required_coverage: frozenset[Coverage] = DEFAULT_REQUIRED_COVERAGE

    def __post_init__(self) -> None:
        counts = Counter(check.id for check in self.checks)
        duplicates = sorted(check_id for check_id, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"Duplicate check IDs: {duplicates}")
        invalid_routes = [
            check.id
            for check in self.checks
            if (
                check.mode is CheckMode.DIAGNOSTIC
                and check.failure_route is not None
            )
            or (
                check.mode is CheckMode.GATE
                and check.failure_route not in {None, Decision.ASSIST, Decision.STOP}
            )
        ]
        if invalid_routes:
            raise ValueError(f"Invalid declared failure routes: {invalid_routes}")

    def evaluate(self, evidence: EvidenceBundle) -> AssuranceCase:
        evidence_problems = validate_evidence_bundle(evidence)
        if evidence_problems:
            raise ValueError(
                "Invalid evidence bundle: " + "; ".join(evidence_problems)
            )
        contract_digest = decision_contract_digest(
            self.checks, self.required_coverage
        )
        tasks = reconstruct_tasks(
            evidence.events, evidence.outcomes, evidence.rates, evidence.policy
        )
        if not tasks:
            raise ValueError("At least one task is required")

        accepted = sum(task.acceptable for task in tasks)
        acceptable_rate = accepted / len(tasks)
        total_cost = _checked_sum(
            [task.effective_cost_usd for task in tasks], "total effective cost"
        )
        cost_per_acceptable = total_cost / accepted if accepted else math.inf
        p95_cost = percentile([task.effective_cost_usd for task in tasks], 0.95)
        max_cost = max(task.effective_cost_usd for task in tasks)
        realized_value = _checked_sum(
            [task.business_value_usd for task in tasks], "total realized value"
        )
        expected_net = (realized_value - total_cost) / len(tasks)
        incremental_net = (
            expected_net - evidence.baseline.expected_net_value_per_attempt_usd
        )
        derived_metrics = (
            ("acceptable_rate", acceptable_rate),
            ("total_effective_cost_usd", total_cost),
            ("cost_per_acceptable_outcome_usd", cost_per_acceptable),
            ("p95_task_cost_usd", p95_cost),
            ("max_task_cost_usd", max_cost),
            ("expected_net_value_per_attempt_usd", expected_net),
            ("incremental_net_value_vs_baseline_usd", incremental_net),
        )
        non_finite = [
            label for label, value in derived_metrics if not math.isfinite(value)
        ]
        if non_finite and not (
            accepted == 0
            and non_finite == ["cost_per_acceptable_outcome_usd"]
        ):
            raise ValueError(
                "Computed economic metrics are not finite: " + ", ".join(non_finite)
            )
        view = EvaluationView(
            events=evidence.events,
            dependency_edges=evidence.dependency_edges,
            rates=evidence.rates,
            policy=evidence.policy,
            baseline=evidence.baseline,
            tasks=tasks,
            acceptable_rate=acceptable_rate,
            total_effective_cost_usd=total_cost,
            cost_per_acceptable_outcome_usd=cost_per_acceptable,
            p95_task_cost_usd=p95_cost,
            max_task_cost_usd=max_cost,
            expected_net_value_per_attempt_usd=expected_net,
            incremental_net_value_vs_baseline_usd=incremental_net,
        )

        enabled_coverage = frozenset(
            coverage
            for check in self.checks
            if check.mode is CheckMode.GATE
            for coverage in check.covers
        )
        missing_coverage = self.required_coverage - enabled_coverage

        results: list[CheckResult] = []
        findings = []
        unrunnable_checks: set[str] = set()
        if not missing_coverage:
            for check in self.checks:
                try:
                    output = check.run(view)
                except Exception as error:
                    unrunnable_checks.add(check.id)
                    if check.mode is CheckMode.GATE:
                        # A crash is never weaker than the same gate returning
                        # FAIL, so it routes the way that gate's failure routes.
                        results.append(
                            CheckResult(
                                check_id=check.id,
                                status=CheckStatus.FAIL,
                                message=(
                                    "check could not run: "
                                    f"{type(error).__name__}: {error}"
                                ),
                                on_failure=check.failure_route or Decision.STOP,
                            )
                        )
                    continue
                _validate_check_output(check, output.results)
                results.extend(output.results)
                findings.extend(output.findings)

        # Required coverage whose providing GATES all failed to run. A surviving
        # provider still covers the dimension; the GATE filter matters because a
        # diagnostic can never satisfy a requirement, and counting one here would
        # reintroduce coverage-derived-from-whatever-is-registered.
        unmet_coverage = {
            coverage
            for coverage in self.required_coverage
            if any(
                coverage in check.covers
                for check in self.checks
                if check.mode is CheckMode.GATE and check.id in unrunnable_checks
            )
            and not any(
                coverage in check.covers
                for check in self.checks
                if check.mode is CheckMode.GATE
                and check.id not in unrunnable_checks
            )
        }

        failed_gates = [
            result
            for result in results
            if result.status is CheckStatus.FAIL and result.on_failure is not None
        ]
        if missing_coverage or unmet_coverage:
            decision = Decision.INCOMPLETE
        elif any(result.on_failure is Decision.STOP for result in failed_gates):
            decision = Decision.STOP
        elif failed_gates:
            decision = Decision.ASSIST
        else:
            decision = Decision.SCALE

        return AssuranceCase(
            decision=decision,
            tasks=tasks,
            acceptable_rate=acceptable_rate,
            total_effective_cost_usd=total_cost,
            cost_per_acceptable_outcome_usd=cost_per_acceptable,
            p95_task_cost_usd=p95_cost,
            max_task_cost_usd=max_cost,
            expected_net_value_per_attempt_usd=expected_net,
            incremental_net_value_vs_baseline_usd=incremental_net,
            baseline=evidence.baseline,
            breaches=tuple(result.message for result in failed_gates),
            findings=tuple(findings),
            check_results=tuple(results),
            enabled_checks=tuple(check.manifest_id for check in self.checks),
            required_coverage=tuple(
                sorted(_coverage_name(c) for c in self.required_coverage)
            ),
            missing_coverage=tuple(
                sorted(_coverage_name(c) for c in missing_coverage)
            ),
            source_manifest_id=evidence.source_manifest_id,
            evidence_digest=evidence.digest,
            decision_contract_digest=contract_digest,
        )


def default_engine(
    checks: Sequence[CheckSpec] | None = None,
    required_coverage: frozenset[Coverage] = DEFAULT_REQUIRED_COVERAGE,
) -> AssuranceEngine:
    return AssuranceEngine(
        checks=tuple(checks) if checks is not None else default_checks(),
        required_coverage=required_coverage,
    )


def evaluate_bundle(
    evidence: EvidenceBundle,
    checks: Sequence[CheckSpec] | None = None,
) -> AssuranceCase:
    return default_engine(checks).evaluate(evidence)


def evaluate(
    events: list[TraceEvent],
    outcomes: dict[str, Outcome],
    rates: dict[str, ModelRate],
    baseline: Baseline,
    policy: EconomicPolicy,
    checks: Sequence[CheckSpec] | None = None,
) -> AssuranceCase:
    """Compatibility wrapper around the explicitly composed engine."""
    evidence = make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=baseline,
        policy=policy,
        source_id="source.legacy",
    )
    return evaluate_bundle(evidence, checks)
