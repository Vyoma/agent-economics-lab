from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .evidence import make_evidence_bundle
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


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile of an empty list")
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


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
        trace_cost = sum(event.cost(rates) for event in task_events)
        human_cost = outcome.human_minutes * policy.human_hourly_cost_usd / 60
        effective_cost = (
            trace_cost
            + human_cost
            + outcome.remediation_cost_usd
            + outcome.incident_loss_usd
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


@dataclass(frozen=True)
class AssuranceEngine:
    checks: tuple[CheckSpec, ...]
    required_coverage: frozenset[Coverage] = DEFAULT_REQUIRED_COVERAGE

    def __post_init__(self) -> None:
        counts = Counter(check.id for check in self.checks)
        duplicates = sorted(check_id for check_id, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"Duplicate check IDs: {duplicates}")

    def evaluate(self, evidence: EvidenceBundle) -> AssuranceCase:
        tasks = reconstruct_tasks(
            evidence.events, evidence.outcomes, evidence.rates, evidence.policy
        )
        if not tasks:
            raise ValueError("At least one task is required")

        accepted = sum(task.acceptable for task in tasks)
        acceptable_rate = accepted / len(tasks)
        total_cost = sum(task.effective_cost_usd for task in tasks)
        cost_per_acceptable = total_cost / accepted if accepted else math.inf
        p95_cost = percentile([task.effective_cost_usd for task in tasks], 0.95)
        max_cost = max(task.effective_cost_usd for task in tasks)
        realized_value = sum(task.business_value_usd for task in tasks)
        expected_net = (realized_value - total_cost) / len(tasks)
        incremental_net = (
            expected_net - evidence.baseline.expected_net_value_per_attempt_usd
        )
        view = EvaluationView(
            events=evidence.events,
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
        for check in self.checks:
            try:
                output = check.run(view)
            except Exception as error:
                raise RuntimeError(f"Check {check.manifest_id!r} failed") from error
            _validate_check_output(check, output.results)
            results.extend(output.results)
            findings.extend(output.findings)

        failed_gates = [
            result
            for result in results
            if result.status is CheckStatus.FAIL and result.on_failure is not None
        ]
        if missing_coverage:
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
                sorted(coverage.value for coverage in self.required_coverage)
            ),
            missing_coverage=tuple(
                sorted(coverage.value for coverage in missing_coverage)
            ),
            source_manifest_id=evidence.source_manifest_id,
            evidence_digest=evidence.digest,
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
