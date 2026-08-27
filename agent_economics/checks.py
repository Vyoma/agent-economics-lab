from __future__ import annotations

from collections import defaultdict

from .controls import find_directed_cycles, repetition_findings
from .models import (
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    ControlFinding,
    Coverage,
    Decision,
    EvaluationView,
)

DEFAULT_REQUIRED_COVERAGE = frozenset(
    {
        Coverage.OUTCOME_QUALITY,
        Coverage.UNIT_ECONOMICS,
        Coverage.TAIL_RISK,
        Coverage.BUSINESS_VALUE,
        Coverage.COUNTERFACTUAL,
        Coverage.RUNTIME_CAPS,
    }
)


def _result(
    check_id: str,
    failed: bool,
    message: str,
    on_failure: Decision,
    *,
    task_id: str | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        status=CheckStatus.FAIL if failed else CheckStatus.PASS,
        message=message,
        on_failure=on_failure if failed else None,
        task_id=task_id,
    )


def _acceptable_rate(view: EvaluationView) -> CheckOutput:
    threshold = view.policy.min_acceptable_rate
    failed = view.acceptable_rate < threshold
    message = (
        f"acceptable_rate {view.acceptable_rate:.1%} "
        f"{'<' if failed else '>='} {threshold:.1%}"
    )
    return CheckOutput(
        results=(_result("gate.acceptable-rate", failed, message, Decision.ASSIST),)
    )


def _unit_economics(view: EvaluationView) -> CheckOutput:
    observed = view.cost_per_acceptable_outcome_usd
    threshold = view.policy.max_cost_per_acceptable_outcome_usd
    failed = observed > threshold
    message = (
        f"cost_per_acceptable_outcome ${observed:.2f} "
        f"{'>' if failed else '<='} ${threshold:.2f}"
    )
    return CheckOutput(
        results=(_result("gate.unit-economics", failed, message, Decision.ASSIST),)
    )


def _tail_cost(view: EvaluationView) -> CheckOutput:
    threshold = view.policy.max_p95_task_cost_usd
    failed = view.p95_task_cost_usd > threshold
    message = (
        f"p95_task_cost ${view.p95_task_cost_usd:.2f} "
        f"{'>' if failed else '<='} ${threshold:.2f}"
    )
    return CheckOutput(
        results=(_result("gate.tail-cost", failed, message, Decision.ASSIST),)
    )


def _net_value(view: EvaluationView) -> CheckOutput:
    threshold = view.policy.min_expected_net_value_per_attempt_usd
    failed = view.expected_net_value_per_attempt_usd < threshold
    message = (
        "expected_net_value_per_attempt "
        f"${view.expected_net_value_per_attempt_usd:.2f} "
        f"{'<' if failed else '>='} ${threshold:.2f}"
    )
    return CheckOutput(
        results=(_result("gate.net-value", failed, message, Decision.STOP),)
    )


def _counterfactual(view: EvaluationView) -> CheckOutput:
    threshold = view.policy.min_incremental_net_value_vs_baseline_usd
    failed = view.incremental_net_value_vs_baseline_usd < threshold
    message = (
        "incremental_net_value_vs_baseline "
        f"${view.incremental_net_value_vs_baseline_usd:.2f} "
        f"{'<' if failed else '>='} ${threshold:.2f}"
    )
    return CheckOutput(
        results=(_result("gate.counterfactual", failed, message, Decision.STOP),)
    )


def _runtime_caps(view: EvaluationView) -> CheckOutput:
    by_task = defaultdict(list)
    for event in view.events:
        by_task[event.task_id].append(event)

    failures: list[CheckResult] = []
    for task_id, events in sorted(by_task.items()):
        call_count = len(events)
        trace_cost = sum(event.cost(view.rates) for event in events)
        if call_count > view.policy.max_calls_per_task:
            failures.append(
                _result(
                    "gate.runtime-caps",
                    True,
                    f"{task_id}: {call_count} calls > cap of {view.policy.max_calls_per_task}",
                    Decision.ASSIST,
                    task_id=task_id,
                )
            )
        if trace_cost > view.policy.max_trace_cost_per_task_usd:
            failures.append(
                _result(
                    "gate.runtime-caps",
                    True,
                    (
                        f"{task_id}: ${trace_cost:.4f} trace cost > cap of "
                        f"${view.policy.max_trace_cost_per_task_usd:.4f}"
                    ),
                    Decision.ASSIST,
                    task_id=task_id,
                )
            )
    if not failures:
        failures.append(
            _result(
                "gate.runtime-caps",
                False,
                "all tasks remain within call and trace-cost caps",
                Decision.ASSIST,
            )
        )
    return CheckOutput(results=tuple(failures))


def _repeated_tool_shape(view: EvaluationView) -> CheckOutput:
    return CheckOutput(
        findings=tuple(
            repetition_findings(
                view.events, view.policy.repetition_warning_threshold
            )
        )
    )


def _directed_cycle(view: EvaluationView) -> CheckOutput:
    task_by_event = {event.event_id: event.task_id for event in view.events}
    findings = []
    for cycle in find_directed_cycles(view.dependency_edges):
        closed_cycle = cycle + (cycle[0],)
        findings.append(
            ControlFinding(
                task_id=task_by_event[cycle[0]],
                control="directed_dependency_cycle",
                severity="warning",
                evidence="dependency cycle: " + " -> ".join(closed_cycle),
                interpretation=(
                    "Observed dependency parentage contains a cycle. This is a "
                    "structural warning, not proof of a runtime deadlock."
                ),
            )
        )
    return CheckOutput(findings=tuple(findings))


def default_checks() -> tuple[CheckSpec, ...]:
    """Return explicit built-ins. Callers may add or remove specs as ordinary data."""
    return (
        CheckSpec(
            id="gate.acceptable-rate",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({Coverage.OUTCOME_QUALITY}),
            run=_acceptable_rate,
            failure_route=Decision.ASSIST,
        ),
        CheckSpec(
            id="gate.unit-economics",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({Coverage.UNIT_ECONOMICS}),
            run=_unit_economics,
            failure_route=Decision.ASSIST,
        ),
        CheckSpec(
            id="gate.tail-cost",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({Coverage.TAIL_RISK}),
            run=_tail_cost,
            failure_route=Decision.ASSIST,
        ),
        CheckSpec(
            id="gate.net-value",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({Coverage.BUSINESS_VALUE}),
            run=_net_value,
            failure_route=Decision.STOP,
        ),
        CheckSpec(
            id="gate.counterfactual",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({Coverage.COUNTERFACTUAL}),
            run=_counterfactual,
            failure_route=Decision.STOP,
        ),
        CheckSpec(
            id="gate.runtime-caps",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({Coverage.RUNTIME_CAPS}),
            run=_runtime_caps,
            failure_route=Decision.ASSIST,
        ),
        CheckSpec(
            id="diagnostic.repeated-tool-shape",
            version="1",
            mode=CheckMode.DIAGNOSTIC,
            covers=frozenset(),
            run=_repeated_tool_shape,
        ),
        CheckSpec(
            id="diagnostic.directed-cycle",
            version="1",
            mode=CheckMode.DIAGNOSTIC,
            covers=frozenset(),
            run=_directed_cycle,
        ),
    )
