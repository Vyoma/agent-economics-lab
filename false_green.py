"""One-file proof of decision-coverage drift under required-gate disablement.

Run `python3 false_green.py`. The frozen v1 matrix produces 23 false SCALE
transitions for a dynamic-coverage engine: the 23 cases where the disabled gate
was the only one failing. The fixed-contract engine returns INCOMPLETE for all
588 disablements, which is structural rather than empirical, because the
coverage-to-gate map is one-to-one and removing any gate necessarily leaves a
required dimension unprovided.

This test changes engine configuration, not evidence, and does not estimate
production prevalence. It also does not measure how hard the harness is to fool:
gate removal is the operator a fixed coverage contract detects by construction.
For the operator that discriminates, a permissive gate that keeps its declared
identity, see mutation_score.py.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Sequence

from agent_economics import (
    AssuranceEngine,
    Baseline,
    Coverage,
    Decision,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
    default_checks,
    default_engine,
    evaluate_bundle,
    make_evidence_bundle,
)


@dataclass(frozen=True)
class Scenario:
    acceptable_tasks: int
    trace_cost_usd: float
    failure_human_minutes: float
    tail_loss_usd: float
    baseline_cost_usd: float
    baseline_acceptable_rate: float
    all_task_human_minutes: float = 0.0
    business_value_usd: float = 5.0

    @property
    def id(self) -> str:
        return (
            f"a{self.acceptable_tasks}-t{self.trace_cost_usd:g}"
            f"-h{self.failure_human_minutes:g}-l{self.tail_loss_usd:g}"
            f"-bc{self.baseline_cost_usd:g}"
            f"-ba{self.baseline_acceptable_rate:g}"
            f"-ah{self.all_task_human_minutes:g}"
            f"-v{self.business_value_usd:g}"
        )


GATE_DISABLEMENTS = {
    "outcome_quality": "gate.acceptable-rate",
    "unit_economics": "gate.unit-economics",
    "tail_risk": "gate.tail-cost",
    "business_value": "gate.net-value",
    "counterfactual": "gate.counterfactual",
    "runtime_caps": "gate.runtime-caps",
}


def scenario_matrix() -> tuple[Scenario, ...]:
    factorial = tuple(
        Scenario(*values)
        for values in product(
            (5, 8, 10),
            (0.1, 1.5),
            (0.0, 5.0),
            (0.0, 10.0),
            (0.0, 4.0),
            (0.70, 0.95),
        )
    )
    boundary_cases = (
        # Isolate unit economics: distributed review cost breaches the unit-cost
        # gate without breaching quality, tail, trace-cap, or value gates.
        Scenario(10, 0.1, 0.0, 0.0, 4.0, 0.70, 3.0, 5.0),
        # Isolate business value: the agent beats a costly baseline but still has
        # negative net value in absolute terms.
        Scenario(10, 0.1, 0.0, 0.0, 4.0, 0.70, 0.0, 0.05),
    )
    return factorial + boundary_cases


def build_evidence(
    scenario: Scenario,
    *,
    incident_loss_usd: float | None = None,
    remediation_cost_usd: float | None = None,
    baseline_acceptable_rate: float | None = None,
    source_id: str = "source.synthetic-decision-coverage-drift",
    source_version: str = "1",
):
    """Build the fixture bundle for one scenario.

    The keyword overrides exist so a sensitivity analysis can perturb one
    economic assumption at a time against the identical construction. Leaving
    them unset reproduces the frozen v1 matrix exactly, which is what keeps the
    published coverage-drift artifacts byte-reproducible.
    """
    tail_loss = (
        scenario.tail_loss_usd if incident_loss_usd is None else incident_loss_usd
    )
    remediation = 0.0 if remediation_cost_usd is None else remediation_cost_usd
    baseline_rate = (
        scenario.baseline_acceptable_rate
        if baseline_acceptable_rate is None
        else baseline_acceptable_rate
    )
    events = []
    outcomes = {}
    for index in range(10):
        task_id = f"task-{index:02d}"
        acceptable = index < scenario.acceptable_tasks
        events.append(
            TraceEvent(
                task_id=task_id,
                event_id=f"event-{index:02d}",
                timestamp=f"2026-01-01T00:00:{index:02d}Z",
                event_type="model",
                name="complete_task",
                direct_cost_usd=scenario.trace_cost_usd,
            )
        )
        outcomes[task_id] = Outcome(
            task_id=task_id,
            acceptable=acceptable,
            business_value_usd=scenario.business_value_usd,
            human_minutes=(
                scenario.all_task_human_minutes
                + (scenario.failure_human_minutes if not acceptable else 0.0)
            ),
            remediation_cost_usd=(0.0 if acceptable else remediation),
            incident_loss_usd=(tail_loss if index == 0 else 0.0),
        )

    policy = EconomicPolicy(
        human_hourly_cost_usd=60.0,
        min_acceptable_rate=0.80,
        max_cost_per_acceptable_outcome_usd=2.0,
        max_p95_task_cost_usd=8.0,
        max_trace_cost_per_task_usd=1.0,
        max_calls_per_task=3,
        min_expected_net_value_per_attempt_usd=0.0,
        min_incremental_net_value_vs_baseline_usd=0.0,
    )
    return make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates={"unused": ModelRate(0.0, 0.0)},
        baseline=Baseline(
            name="controlled baseline",
            cost_per_attempt_usd=scenario.baseline_cost_usd,
            acceptable_rate=baseline_rate,
            value_per_acceptable_outcome_usd=scenario.business_value_usd,
        ),
        policy=policy,
        source_id=source_id,
        source_version=source_version,
    )


def _enabled_coverage(checks) -> frozenset[Coverage]:
    return frozenset(coverage for check in checks for coverage in check.covers)


def run_benchmark() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    checks = default_checks()
    for scenario in scenario_matrix():
        evidence = build_evidence(scenario)
        full_case = evaluate_bundle(evidence, checks)
        for coverage_dimension, disabled_check in GATE_DISABLEMENTS.items():
            reduced_checks = tuple(
                check for check in checks if check.id != disabled_check
            )

            # Fixed-contract architecture: the original six requirements remain.
            fixed_contract_case = default_engine(reduced_checks).evaluate(evidence)

            # Dynamic-coverage architecture: completeness silently shrinks to
            # whichever gates remain enabled.
            dynamic_coverage_case = AssuranceEngine(
                checks=reduced_checks,
                required_coverage=_enabled_coverage(reduced_checks),
            ).evaluate(evidence)

            false_scale_transition = (
                full_case.decision is not Decision.SCALE
                and dynamic_coverage_case.decision is Decision.SCALE
            )
            rows.append(
                {
                    "scenario_id": scenario.id,
                    "disabled_coverage_dimension": coverage_dimension,
                    "disabled_check_id": disabled_check,
                    "full_evidence_digest": full_case.evidence_digest,
                    "fixed_contract_evidence_digest": (
                        fixed_contract_case.evidence_digest
                    ),
                    "dynamic_coverage_evidence_digest": (
                        dynamic_coverage_case.evidence_digest
                    ),
                    "full_contract_digest": full_case.decision_contract_digest,
                    "fixed_contract_digest": (
                        fixed_contract_case.decision_contract_digest
                    ),
                    "dynamic_coverage_contract_digest": (
                        dynamic_coverage_case.decision_contract_digest
                    ),
                    "full_decision": full_case.decision.value,
                    "dynamic_coverage_decision": (
                        dynamic_coverage_case.decision.value
                    ),
                    "fixed_contract_decision": fixed_contract_case.decision.value,
                    "false_scale_transition": str(false_scale_transition).lower(),
                    "fixed_contract_refused": str(
                        false_scale_transition
                        and fixed_contract_case.decision is Decision.INCOMPLETE
                    ).lower(),
                    "acceptable_rate": f"{full_case.acceptable_rate:.3f}",
                    "cost_per_acceptable_usd": (
                        f"{full_case.cost_per_acceptable_outcome_usd:.4f}"
                    ),
                    "p95_task_cost_usd": f"{full_case.p95_task_cost_usd:.4f}",
                    "incremental_value_usd": (
                        f"{full_case.incremental_net_value_vs_baseline_usd:.4f}"
                    ),
                }
            )
    return rows


FIELDNAMES = (
    "scenario_id",
    "disabled_coverage_dimension",
    "disabled_check_id",
    "full_evidence_digest",
    "fixed_contract_evidence_digest",
    "dynamic_coverage_evidence_digest",
    "full_contract_digest",
    "fixed_contract_digest",
    "dynamic_coverage_contract_digest",
    "full_decision",
    "dynamic_coverage_decision",
    "fixed_contract_decision",
    "false_scale_transition",
    "fixed_contract_refused",
    "acceptable_rate",
    "cost_per_acceptable_usd",
    "p95_task_cost_usd",
    "incremental_value_usd",
)


def render_csv(rows: Sequence[dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def summarize(rows: Sequence[dict[str, str]]) -> dict[str, object]:
    non_scale = [row for row in rows if row["full_decision"] != Decision.SCALE.value]
    false_scale_transitions = [
        row for row in rows if row["false_scale_transition"] == "true"
    ]
    fixed_contract_false_scale_transitions = [
        row
        for row in rows
        if row["full_decision"] != Decision.SCALE.value
        and row["fixed_contract_decision"] == Decision.SCALE.value
    ]
    by_disabled_dimension = {
        coverage_dimension: sum(
            row["false_scale_transition"] == "true"
            for row in rows
            if row["disabled_coverage_dimension"] == coverage_dimension
        )
        for coverage_dimension in GATE_DISABLEMENTS
    }
    return {
        "schema_version": 1,
        "experiment_id": "decision-coverage-drift-conformance",
        "experiment_version": "1",
        "scenarios": len(scenario_matrix()),
        "comparisons": len(rows),
        "complete_non_scale_comparisons": len(non_scale),
        "dynamic_false_scale_transitions": len(false_scale_transitions),
        "dynamic_false_scale_rate_at_risk": (
            len(false_scale_transitions) / len(non_scale) if non_scale else 0.0
        ),
        "dynamic_false_scale_rate_all": (
            len(false_scale_transitions) / len(rows) if rows else 0.0
        ),
        "fixed_contract_false_scale_transitions": len(
            fixed_contract_false_scale_transitions
        ),
        "fixed_contract_incomplete": sum(
            row["fixed_contract_decision"] == Decision.INCOMPLETE.value
            for row in rows
        ),
        "by_disabled_dimension": by_disabled_dimension,
        "claim_boundary": (
            "Synthetic conformance fixture; not a production prevalence estimate."
        ),
    }


def render_summary(summary: dict[str, object]) -> str:
    by_disabled_dimension = summary["by_disabled_dimension"]
    assert isinstance(by_disabled_dimension, dict)
    lines = [
        "# Decision-Coverage Drift Conformance Results",
        "",
        f"- Synthetic scenarios: **{summary['scenarios']}**",
        f"- Single required-gate disablements: **{summary['comparisons']}**",
        (
            "- Disablements whose complete result was not SCALE: "
            f"**{summary['complete_non_scale_comparisons']}**"
        ),
        (
            "- False SCALE transitions under dynamic coverage: "
            f"**{summary['dynamic_false_scale_transitions']}**"
        ),
        (
            "- Dynamic-coverage transition rate among non-SCALE comparisons: "
            f"**{summary['dynamic_false_scale_rate_at_risk']:.1%}**"
        ),
        (
            "- Dynamic-coverage transition rate across all disablements: "
            f"**{summary['dynamic_false_scale_rate_all']:.1%}**"
        ),
        (
            "- Fixed-contract decisions returning INCOMPLETE: "
            f"**{summary['fixed_contract_incomplete']} / {summary['comparisons']}**"
        ),
        (
            "- False SCALE transitions under the fixed contract: "
            f"**{summary['fixed_contract_false_scale_transitions']}**"
        ),
        "",
        "| Disabled gate coverage | Dynamic-coverage false SCALE transitions |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{coverage_dimension}` | {by_disabled_dimension[coverage_dimension]} |"
        for coverage_dimension in GATE_DISABLEMENTS
    )
    largest = max(by_disabled_dimension.values(), default=1)
    lines.extend(["", "```text", "disabled gate          false SCALE"])
    for coverage_dimension in GATE_DISABLEMENTS:
        count = by_disabled_dimension[coverage_dimension]
        width = max(1, round(20 * count / largest)) if count else 0
        lines.append(f"{coverage_dimension:<20} {'#' * width:<20} {count}")
    lines.extend(
        [
            "```",
            "",
            "The evidence bundle is unchanged in every comparison. The intervention",
            "disables one required gate. The dynamic-coverage engine silently shrinks",
            "its completeness contract; the fixed-contract engine does not.",
            "",
            "This is a deterministic synthetic conformance test, not an estimate of",
            "how often production systems experience decision-coverage drift.",
            "",
            "All enabled checks passed is not the same claim as all required checks passed.",
            "",
        ]
    )
    return "\n".join(lines)


def render_summary_json(summary: dict[str, object]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--summary-verify", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--json-verify", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = run_benchmark()
    csv_text = render_csv(rows)
    summary = summarize(rows)
    summary_text = render_summary(summary)
    summary_json = render_summary_json(summary)
    if args.verify:
        if not args.verify.exists() or args.verify.read_text(encoding="utf-8") != csv_text:
            print(f"Generated results differ from {args.verify}")
            return 1
    if args.summary_verify:
        if (
            not args.summary_verify.exists()
            or args.summary_verify.read_text(encoding="utf-8") != summary_text
        ):
            print(f"Generated summary differs from {args.summary_verify}")
            return 1
    if args.json_verify:
        if (
            not args.json_verify.exists()
            or args.json_verify.read_text(encoding="utf-8") != summary_json
        ):
            print(f"Generated JSON summary differs from {args.json_verify}")
            return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(csv_text, encoding="utf-8")
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(summary_text, encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(summary_json, encoding="utf-8")
    print(summary_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
