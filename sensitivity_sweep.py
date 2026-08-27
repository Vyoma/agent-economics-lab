"""
Decision robustness analysis and baseline fragility index.

Every SCALE/ASSIST/STOP verdict is a function of economic assumptions. If those
assumptions are wrong, the verdict is wrong. Two questions are measured here:

  1. DECISION ROBUSTNESS. How many verdicts flip across a grid of incident-loss
     and remediation-cost assumptions. A verdict that changes under plausible
     assumptions is a measurement artifact, not a fact.

  2. BASELINE FRAGILITY INDEX. How many counterfactual gates flip when the
     baseline acceptable rate is perturbed by 10%, 25%, and 50% in each
     direction. A baseline is always an estimate, so this is its error bar.

Both parts reuse the 98-scenario matrix and the single fixture builder in
false_green.py, so the identity cell of the grid reproduces the unperturbed
verdict exactly rather than comparing two different constructions.

This is a synthetic conformance fixture. The flip counts characterize the
sensitivity of this matrix under this policy, not a production prevalence.

Run:
    python3 sensitivity_sweep.py
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from itertools import product
from pathlib import Path

from agent_economics import CheckStatus, Decision, evaluate_bundle
from false_green import Scenario, build_evidence, scenario_matrix

SOURCE_ID = "source.synthetic-sensitivity-sweep"

INCIDENT_LOSS_GRID = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
REMEDIATION_COST_GRID = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0)
BASELINE_PERTURBATIONS = (
    (0.50, "-50%"),
    (0.75, "-25%"),
    (0.90, "-10%"),
    (1.10, "+10%"),
    (1.25, "+25%"),
    (1.50, "+50%"),
)

FRAGILE_FLIP_THRESHOLD = 1
BRITTLE_FLIP_THRESHOLD = 3
CRITICAL_FRAGILITY_RATE = 0.25


def _bar(value: int, total: int, width: int = 24) -> str:
    filled = round(width * value / total) if total else 0
    return "#" * filled + "." * (width - filled)


def _decision(
    scenario: Scenario,
    *,
    incident_loss_usd: float | None = None,
    remediation_cost_usd: float | None = None,
    baseline_acceptable_rate: float | None = None,
) -> Decision:
    evidence = build_evidence(
        scenario,
        incident_loss_usd=incident_loss_usd,
        remediation_cost_usd=remediation_cost_usd,
        baseline_acceptable_rate=baseline_acceptable_rate,
        source_id=SOURCE_ID,
    )
    return evaluate_bundle(evidence).decision


def _counterfactual_fails(
    scenario: Scenario, baseline_acceptable_rate: float | None
) -> bool:
    evidence = build_evidence(
        scenario,
        baseline_acceptable_rate=baseline_acceptable_rate,
        source_id=SOURCE_ID,
    )
    case = evaluate_bundle(evidence)
    return any(
        result.check_id == "gate.counterfactual"
        and result.status is CheckStatus.FAIL
        for result in case.check_results
    )


def _clamped_rate(scenario: Scenario, multiplier: float) -> float:
    return min(0.9999, max(0.0001, scenario.baseline_acceptable_rate * multiplier))


def flip_counts() -> tuple[int, ...]:
    """Return, per scenario, how many grid cells change the verdict."""
    counts: list[int] = []
    for scenario in scenario_matrix():
        unperturbed = _decision(scenario)
        counts.append(
            sum(
                _decision(
                    scenario,
                    incident_loss_usd=incident_loss,
                    remediation_cost_usd=remediation,
                )
                is not unperturbed
                for incident_loss, remediation in product(
                    INCIDENT_LOSS_GRID, REMEDIATION_COST_GRID
                )
            )
        )
    return tuple(counts)


def baseline_fragility() -> dict[str, int]:
    """Return, per perturbation label, how many counterfactual gates flip."""
    scenarios = scenario_matrix()
    unperturbed = {
        scenario.id: _counterfactual_fails(scenario, None) for scenario in scenarios
    }
    fragility: dict[str, int] = {}
    for multiplier, label in BASELINE_PERTURBATIONS:
        fragility[label] = sum(
            _counterfactual_fails(scenario, _clamped_rate(scenario, multiplier))
            is not unperturbed[scenario.id]
            for scenario in scenarios
        )
    return fragility


def summarize() -> dict[str, object]:
    counts = flip_counts()
    scenarios = len(counts)
    grid_cells = len(INCIDENT_LOSS_GRID) * len(REMEDIATION_COST_GRID)
    robust = sum(count == 0 for count in counts)
    fragile = sum(
        FRAGILE_FLIP_THRESHOLD <= count < BRITTLE_FLIP_THRESHOLD for count in counts
    )
    brittle = sum(count >= BRITTLE_FLIP_THRESHOLD for count in counts)
    fragility = baseline_fragility()
    return {
        "schema_version": 1,
        "experiment_id": "decision-sensitivity-sweep",
        "experiment_version": "1",
        "scenarios": scenarios,
        "grid_cells": grid_cells,
        "incident_loss_grid": list(INCIDENT_LOSS_GRID),
        "remediation_cost_grid": list(REMEDIATION_COST_GRID),
        "robust_scenarios": robust,
        "fragile_scenarios": fragile,
        "brittle_scenarios": brittle,
        "brittle_rate": brittle / scenarios if scenarios else 0.0,
        "max_flips_for_one_scenario": max(counts, default=0),
        "baseline_fragility": fragility,
        "claim_boundary": (
            "Synthetic conformance fixture. Flip counts characterize this "
            "matrix under this policy; they are not a production prevalence "
            "estimate."
        ),
    }


def render_summary(summary: dict[str, object]) -> str:
    scenarios = summary["scenarios"]
    grid_cells = summary["grid_cells"]
    fragility = summary["baseline_fragility"]
    assert isinstance(scenarios, int)
    assert isinstance(grid_cells, int)
    assert isinstance(fragility, dict)
    width = 66
    lines = [
        "=" * width,
        "  SENSITIVITY SWEEP  decision robustness analysis",
        "=" * width,
        (
            f"  {scenarios} scenarios x {grid_cells}-cell economic grid "
            f"({len(INCIDENT_LOSS_GRID)} incident x "
            f"{len(REMEDIATION_COST_GRID)} remediation)"
        ),
        (
            f"  incident_loss ${INCIDENT_LOSS_GRID[0]:g} to "
            f"${INCIDENT_LOSS_GRID[-1]:g}, "
            f"remediation ${REMEDIATION_COST_GRID[0]:g} to "
            f"${REMEDIATION_COST_GRID[-1]:g}"
        ),
        "",
        "  DECISION ROBUSTNESS across the economic assumption grid",
        "  " + "-" * 58,
    ]
    for label, key in (
        ("ROBUST  (0 flips)", "robust_scenarios"),
        (f"FRAGILE (1-{BRITTLE_FLIP_THRESHOLD - 1} flips)", "fragile_scenarios"),
        (f"BRITTLE ({BRITTLE_FLIP_THRESHOLD}+ flips)", "brittle_scenarios"),
    ):
        count = summary[key]
        assert isinstance(count, int)
        lines.append(
            f"  {label:<22} {count:>4}/{scenarios}  "
            f"{_bar(count, scenarios)}  {count / scenarios:.1%}"
        )
    lines.extend(
        [
            "",
            (
                "  Max flips for a single scenario: "
                f"{summary['max_flips_for_one_scenario']}/{grid_cells}"
            ),
        ]
    )
    brittle = summary["brittle_scenarios"]
    assert isinstance(brittle, int)
    if brittle:
        lines.extend(
            [
                (
                    f"  {brittle} scenarios produce a verdict that is an economic "
                    "assumption"
                ),
                "  artifact rather than a stable result. Do not publish a SCALE",
                (
                    f"  verdict from a scenario with {BRITTLE_FLIP_THRESHOLD}+ "
                    "flips without this report beside it."
                ),
            ]
        )
    lines.extend(
        [
            "",
            "  BASELINE FRAGILITY INDEX  (perturb baseline acceptable rate)",
            "  " + "-" * 58,
        ]
    )
    for _, label in BASELINE_PERTURBATIONS:
        flips = fragility[label]
        rate = flips / scenarios if scenarios else 0.0
        marker = "  <- critical" if rate > CRITICAL_FRAGILITY_RATE else ""
        lines.append(
            f"  {label:>5} baseline error  {flips:>3}/{scenarios} "
            f"counterfactual flips  {_bar(flips, scenarios, 18)}  "
            f"{rate:.1%}{marker}"
        )
    lines.extend(
        [
            "",
            "  A baseline is always an estimate. These are its error bars.",
            "  Report the fragility index alongside every SCALE verdict.",
            "=" * width,
            "",
        ]
    )
    return "\n".join(lines)


def render_summary_json(summary: dict[str, object]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--summary-verify", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--json-verify", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = summarize()
    summary_text = render_summary(summary)
    summary_json = render_summary_json(summary)
    if args.summary_verify and (
        not args.summary_verify.exists()
        or args.summary_verify.read_text(encoding="utf-8") != summary_text
    ):
        print(f"Generated summary differs from {args.summary_verify}")
        return 1
    if args.json_verify and (
        not args.json_verify.exists()
        or args.json_verify.read_text(encoding="utf-8") != summary_json
    ):
        print(f"Generated JSON summary differs from {args.json_verify}")
        return 1
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(summary_text, encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(summary_json, encoding="utf-8")
    print(summary_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
