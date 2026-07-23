"""One-file proof that missing evidence can manufacture a green decision.

Run `python3 false_green.py`. The frozen v1 matrix produces 23 false SCALE
decisions for an unsafe available-evidence-only reducer and zero for the fail-safe
engine. This synthetic test validates routing semantics, not production prevalence.
"""

from __future__ import annotations

import argparse
import csv
import io
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


ABLATIONS = {
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


def build_evidence(scenario: Scenario):
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
            incident_loss_usd=(scenario.tail_loss_usd if index == 0 else 0.0),
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
            acceptable_rate=scenario.baseline_acceptable_rate,
            value_per_acceptable_outcome_usd=scenario.business_value_usd,
        ),
        policy=policy,
        source_id="source.synthetic-false-green",
        source_version="1",
    )


def _enabled_coverage(checks) -> frozenset[Coverage]:
    return frozenset(coverage for check in checks for coverage in check.covers)


def run_benchmark() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    checks = default_checks()
    for scenario in scenario_matrix():
        evidence = build_evidence(scenario)
        full_case = evaluate_bundle(evidence, checks)
        for ablation, removed_check in ABLATIONS.items():
            reduced_checks = tuple(
                check for check in checks if check.id != removed_check
            )

            # Production behavior: required removal is visible and fail-safe.
            safe_case = default_engine(reduced_checks).evaluate(evidence)

            # Unsafe comparator: emulate a system that silently redefines
            # "complete" as whatever checks happen to remain enabled.
            unsafe_case = AssuranceEngine(
                checks=reduced_checks,
                required_coverage=_enabled_coverage(reduced_checks),
            ).evaluate(evidence)

            false_green = (
                full_case.decision is not Decision.SCALE
                and unsafe_case.decision is Decision.SCALE
            )
            rows.append(
                {
                    "scenario_id": scenario.id,
                    "ablation": ablation,
                    "full_decision": full_case.decision.value,
                    "unsafe_decision": unsafe_case.decision.value,
                    "safe_decision": safe_case.decision.value,
                    "false_green": str(false_green).lower(),
                    "prevented_by_coverage": str(
                        false_green and safe_case.decision is Decision.INCOMPLETE
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
    "ablation",
    "full_decision",
    "unsafe_decision",
    "safe_decision",
    "false_green",
    "prevented_by_coverage",
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
    false_greens = [row for row in rows if row["false_green"] == "true"]
    safe_false_greens = [
        row
        for row in rows
        if row["full_decision"] != Decision.SCALE.value
        and row["safe_decision"] == Decision.SCALE.value
    ]
    by_ablation = {
        ablation: sum(
            row["false_green"] == "true"
            for row in rows
            if row["ablation"] == ablation
        )
        for ablation in ABLATIONS
    }
    return {
        "scenarios": len(scenario_matrix()),
        "comparisons": len(rows),
        "non_scale_comparisons": len(non_scale),
        "unsafe_false_greens": len(false_greens),
        "unsafe_false_green_rate": (
            len(false_greens) / len(non_scale) if non_scale else 0.0
        ),
        "safe_false_greens": len(safe_false_greens),
        "by_ablation": by_ablation,
    }


def render_summary(summary: dict[str, object]) -> str:
    by_ablation = summary["by_ablation"]
    assert isinstance(by_ablation, dict)
    lines = [
        "# False-Green Benchmark Results",
        "",
        f"- Synthetic scenarios: **{summary['scenarios']}**",
        f"- Single-module ablation comparisons: **{summary['comparisons']}**",
        f"- Comparisons whose complete result was not SCALE: **{summary['non_scale_comparisons']}**",
        f"- False SCALE results when missing coverage was silently ignored: **{summary['unsafe_false_greens']}**",
        (
            "- Unsafe false-green rate among non-SCALE comparisons: "
            f"**{summary['unsafe_false_green_rate']:.1%}**"
        ),
        f"- False SCALE results with fail-safe coverage enabled: **{summary['safe_false_greens']}**",
        "",
        "| Removed assurance dimension | Unsafe false-green decisions |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{ablation}` | {by_ablation[ablation]} |" for ablation in ABLATIONS
    )
    largest = max(by_ablation.values(), default=1)
    lines.extend(["", "```text", "removed evidence       false SCALE"])
    for ablation in ABLATIONS:
        count = by_ablation[ablation]
        width = max(1, round(20 * count / largest)) if count else 0
        lines.append(f"{ablation:<20} {'#' * width:<20} {count}")
    lines.extend(
        [
            "```",
            "",
            "This is a deterministic synthetic stress test of routing semantics, not an",
            "estimate of how often production systems make false-green decisions.",
            "",
            "A dashboard that averages only what it has can bless what it cannot see.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = run_benchmark()
    csv_text = render_csv(rows)
    if args.verify:
        if not args.verify.exists() or args.verify.read_text(encoding="utf-8") != csv_text:
            print(f"Generated results differ from {args.verify}")
            return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(csv_text, encoding="utf-8")
    print(render_summary(summarize(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
