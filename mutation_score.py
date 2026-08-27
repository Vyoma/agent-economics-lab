"""
Mutation score for agent-economics-lab's decision harness.

Mutation testing only means something when the mutant could plausibly survive.
An earlier version of this script injected one operator, gate REMOVAL, and
reported that the fixed-contract engine killed 100% of them. That number was
arithmetic, not evidence: the fixed contract pins all six required coverage
dimensions, the built-in coverage-to-gate map is one-to-one, and so removing any
gate leaves a required dimension unprovided. INCOMPLETE is the only reachable
answer. A score that cannot come out below 100% measures nothing.

This version injects two operators and scores both engines against both:

  REMOVAL       delete a required gate outright.
                Detected by the coverage contract by construction.

  SUBSTITUTION  replace a required gate with a permissive implementation that
                keeps the same ID, version, declared coverage, and failure
                route. Required coverage still appears satisfied; the gate
                simply stops failing. This is the realistic operator: a
                threshold loosened during an incident, an evaluator stubbed out
                in a migration, a gate downgraded to a warning.

Equivalent mutants are excluded from the denominator, as standard mutation
testing requires. If the unmutated verdict was already SCALE there is no verdict
for the mutation to corrupt, so those cases cannot be credited as kills.

Run:
    python3 mutation_score.py

Exit status is 0 when the report is produced. The script scores the harness; it
does not assert a target score.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from agent_economics import (
    AssuranceEngine,
    CheckMode,
    CheckOutput,
    CheckSpec,
    Coverage,
    Decision,
    default_checks,
    default_engine,
)
from false_green import GATE_DISABLEMENTS, build_evidence, scenario_matrix


def permissive_gate(view):
    """Enforce nothing while still claiming the coverage of the gate replaced."""
    return CheckOutput(results=())


COVERAGE_BY_CHECK_ID = {
    "gate.acceptable-rate": Coverage.OUTCOME_QUALITY,
    "gate.unit-economics": Coverage.UNIT_ECONOMICS,
    "gate.tail-cost": Coverage.TAIL_RISK,
    "gate.net-value": Coverage.BUSINESS_VALUE,
    "gate.counterfactual": Coverage.COUNTERFACTUAL,
    "gate.runtime-caps": Coverage.RUNTIME_CAPS,
}

REMOVAL = "removal"
SUBSTITUTION = "substitution"
OPERATORS = (REMOVAL, SUBSTITUTION)


@dataclass(frozen=True)
class MutantResult:
    operator: str
    coverage_dimension: str
    check_id: str
    equivalent: bool
    fixed_survived: bool
    dynamic_survived: bool
    digest_changed: bool


def _enabled_coverage(checks: Sequence[CheckSpec]) -> frozenset[Coverage]:
    return frozenset(
        coverage
        for check in checks
        if check.mode is CheckMode.GATE
        for coverage in check.covers
    )


def _mutate(
    checks: tuple[CheckSpec, ...], operator: str, check_id: str
) -> tuple[CheckSpec, ...]:
    if operator == REMOVAL:
        return tuple(check for check in checks if check.id != check_id)
    target = next(check for check in checks if check.id == check_id)
    substitute = CheckSpec(
        id=target.id,
        version=target.version,
        mode=target.mode,
        covers=target.covers,
        run=permissive_gate,
        failure_route=target.failure_route,
    )
    return tuple(
        substitute if check.id == check_id else check for check in checks
    )


def run_mutations() -> list[MutantResult]:
    checks = default_checks()
    results: list[MutantResult] = []
    for scenario in scenario_matrix():
        evidence = build_evidence(scenario)
        baseline_case = default_engine(checks).evaluate(evidence)
        baseline_decision = baseline_case.decision
        baseline_digest = baseline_case.decision_contract_digest
        for operator in OPERATORS:
            for coverage_dimension, check_id in GATE_DISABLEMENTS.items():
                mutated = _mutate(checks, operator, check_id)

                # Fixed contract: the original six requirements stand.
                fixed_case = default_engine(mutated).evaluate(evidence)

                # Dynamic coverage: completeness shrinks to whatever remains.
                dynamic_case = AssuranceEngine(
                    checks=mutated,
                    required_coverage=_enabled_coverage(mutated),
                ).evaluate(evidence)

                equivalent = baseline_decision is Decision.SCALE
                results.append(
                    MutantResult(
                        operator=operator,
                        coverage_dimension=coverage_dimension,
                        check_id=check_id,
                        equivalent=equivalent,
                        fixed_survived=(
                            not equivalent
                            and fixed_case.decision is Decision.SCALE
                        ),
                        dynamic_survived=(
                            not equivalent
                            and dynamic_case.decision is Decision.SCALE
                        ),
                        digest_changed=(
                            fixed_case.decision_contract_digest != baseline_digest
                        ),
                    )
                )
    return results


def _score(rows: Sequence[MutantResult], attribute: str) -> tuple[int, int, float]:
    scored = [row for row in rows if not row.equivalent]
    survived = sum(getattr(row, attribute) for row in scored)
    killed = len(scored) - survived
    return killed, len(scored), (killed / len(scored) if scored else 0.0)


def summarize(rows: Sequence[MutantResult]) -> dict[str, object]:
    summary: dict[str, object] = {
        "schema_version": 2,
        "experiment_id": "harness-mutation-score",
        "experiment_version": "2",
        "scenarios": len(scenario_matrix()),
        "mutants_injected": len(rows),
        "equivalent_mutants_excluded": sum(row.equivalent for row in rows),
        "operators": {},
        "claim_boundary": (
            "Synthetic conformance fixture. Removal detection is forced by the "
            "fixed coverage contract and is therefore not evidence of harness "
            "hardness. Substitution is the operator that discriminates."
        ),
    }
    operators: dict[str, object] = {}
    for operator in OPERATORS:
        rows_for_operator = [row for row in rows if row.operator == operator]
        fixed_killed, scored, fixed_rate = _score(rows_for_operator, "fixed_survived")
        dynamic_killed, _, dynamic_rate = _score(
            rows_for_operator, "dynamic_survived"
        )
        digest_changed = sum(row.digest_changed for row in rows_for_operator)
        operators[operator] = {
            "mutants": len(rows_for_operator),
            "scored_mutants": scored,
            "fixed_contract_killed": fixed_killed,
            "fixed_contract_score": fixed_rate,
            "fixed_contract_survived": scored - fixed_killed,
            "dynamic_coverage_killed": dynamic_killed,
            "dynamic_coverage_score": dynamic_rate,
            "dynamic_coverage_survived": scored - dynamic_killed,
            "contract_digest_changed": digest_changed,
            "detected_by_coverage_contract_by_construction": operator == REMOVAL,
            "by_dimension": {
                dimension: {
                    "fixed_survived": sum(
                        row.fixed_survived
                        for row in rows_for_operator
                        if row.coverage_dimension == dimension
                    ),
                    "dynamic_survived": sum(
                        row.dynamic_survived
                        for row in rows_for_operator
                        if row.coverage_dimension == dimension
                    ),
                }
                for dimension in GATE_DISABLEMENTS
            },
        }
    summary["operators"] = operators
    return summary


def _bar(value: int, total: int, width: int = 18) -> str:
    filled = round(width * value / total) if total else 0
    return "#" * filled + "." * (width - filled)


def render_summary(summary: dict[str, object]) -> str:
    operators = summary["operators"]
    assert isinstance(operators, dict)
    width = 66
    lines = [
        "=" * width,
        "  MUTATION SCORE  agent-economics-lab decision harness",
        "=" * width,
        (
            f"  {summary['mutants_injected']} mutants injected across "
            f"{summary['scenarios']} scenarios, "
            f"{len(GATE_DISABLEMENTS)} gates, {len(OPERATORS)} operators"
        ),
        (
            f"  {summary['equivalent_mutants_excluded']} equivalent mutants "
            "excluded (unmutated verdict was already SCALE)"
        ),
        "",
    ]
    for operator in OPERATORS:
        stats = operators[operator]
        assert isinstance(stats, dict)
        scored = stats["scored_mutants"]
        lines.append(f"  {operator.upper()}  ({scored} scored mutants)")
        verb = "killed" if stats[
            "detected_by_coverage_contract_by_construction"] else "not SCALE"
        lines.append(
            f"    fixed-contract engine    "
            f"{stats['fixed_contract_killed']:>3}/{scored} {verb}  "
            f"({stats['fixed_contract_score']:.1%})"
        )
        lines.append(
            f"    dynamic-coverage engine  "
            f"{stats['dynamic_coverage_killed']:>3}/{scored} {verb}  "
            f"({stats['dynamic_coverage_score']:.1%})"
        )
        if stats["detected_by_coverage_contract_by_construction"]:
            lines.append(
                "    note: the fixed-contract result here is forced. Required "
                "coverage loses a"
            )
            lines.append(
                "          sole provider, so INCOMPLETE is the only reachable "
                "answer. Not evidence."
            )
        else:
            lines.append(
                f"    contract digest changed  "
                f"{stats['contract_digest_changed']:>3}/{stats['mutants']} "
                "mutants (implementation fingerprint)"
            )
            lines.append(
                "    note: coverage still looks satisfied, so neither engine's "
                "routing DETECTS this."
            )
            lines.append(
                "          A non-SCALE result here means other gates were also "
                "failing and masked"
            )
            lines.append(
                "          the substitution. It is not detection. Only the "
                "changed digest surfaces it,"
            )
            lines.append(
                "          and only when the check body itself was substituted."
            )
        lines.append("")

    lines.extend(
        [
            "  Surviving mutants by dimension (fixed contract)",
            f"  {'dimension':<20} {'removal':>8} {'substitution':>14}",
            "  " + "-" * 46,
        ]
    )
    removal_stats = operators[REMOVAL]
    substitution_stats = operators[SUBSTITUTION]
    assert isinstance(removal_stats, dict)
    assert isinstance(substitution_stats, dict)
    removal_by = removal_stats["by_dimension"]
    substitution_by = substitution_stats["by_dimension"]
    assert isinstance(removal_by, dict)
    assert isinstance(substitution_by, dict)
    largest = max(
        (entry["fixed_survived"] for entry in substitution_by.values()),
        default=1,
    )
    for dimension in GATE_DISABLEMENTS:
        removed = removal_by[dimension]["fixed_survived"]
        substituted = substitution_by[dimension]["fixed_survived"]
        lines.append(
            f"  {dimension:<20} {removed:>8} {substituted:>14}  "
            f"{_bar(substituted, max(1, largest))}"
        )

    substitution_score = substitution_stats["fixed_contract_score"]
    assert isinstance(substitution_score, float)
    lines.extend(
        [
            "",
            f"  HARNESS MUTATION SCORE (substitution): {substitution_score:.1%}",
            "",
            "  Read it this way. The coverage contract makes gate deletion",
            "  undetectable-by-omission, which is a real property but a forced one.",
            "  Against a gate that keeps its declared identity and stops enforcing,",
            "  the fixed contract scores no better than the dynamic one. The",
            "  implementation fingerprint in the decision-contract digest is the",
            "  only thing that distinguishes them.",
            "",
            "  'All enabled checks passed' is not 'all required checks passed'.",
            "  'All required checks ran' is not 'all required checks enforced'.",
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
    rows = run_mutations()
    summary = summarize(rows)
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
