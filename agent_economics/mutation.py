"""
Mutation testing for the evaluation harness itself.

Standard mutation testing injects faults into your source and asks whether the
tests catch them. This injects *gate removals* into the decision harness and
asks whether the engine still refuses to return a verdict.

The question it answers is one no evaluation framework currently reports: how
load-bearing is each check in your eval? A score reported without it is
unfalsifiable about its own construction. "All enabled checks passed" and "all
required checks passed" are different claims, and only the second one is a
decision.

This works on any EvidenceBundle and any check set, including checks you wrote.
The required coverage is read from the contract and the providers of each
dimension are derived from `CheckSpec.covers`, so nothing here is specific to
the six gates this package ships.

    from agent_economics import load_normalized_json_bundle
    from agent_economics.mutation import mutate

    report = mutate(load_normalized_json_bundle("bundle.json"))
    print(report.fixed_contract_score)      # 1.0 means every gate is load-bearing
    for m in report.survivors:
        print(m.coverage, "can be removed without the harness noticing")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assurance import AssuranceEngine, evaluate_bundle
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .models import CheckSpec, Coverage, Decision, EvidenceBundle

# A coverage dimension is either one this package ships or a plain string you
# defined. The six economic dimensions are what the default gates happen to
# cover; the primitive itself has no opinion about them. A PII gate, a jailbreak
# gate or a regression eval is a dimension like any other.
CoverageLike = Coverage | str


def _name(coverage: CoverageLike) -> str:
    return coverage.value if isinstance(coverage, Coverage) else str(coverage)


@dataclass(frozen=True)
class Mutation:
    """One gate removal and what each engine did about it."""

    coverage: str
    removed_check_ids: tuple[str, ...]
    baseline_decision: str
    fixed_contract_decision: str
    dynamic_coverage_decision: str

    @property
    def killed_by_fixed_contract(self) -> bool:
        """A fixed contract must refuse: missing coverage means INCOMPLETE."""
        return self.fixed_contract_decision == Decision.INCOMPLETE.value

    @property
    def survived_dynamic_coverage(self) -> bool:
        """The removal produced a green verdict with a required gate missing."""
        return self.dynamic_coverage_decision == Decision.SCALE.value

    @property
    def flipped_to_scale(self) -> bool:
        """A verdict that was not SCALE became SCALE because a gate vanished."""
        return (
            self.baseline_decision != Decision.SCALE.value
            and self.dynamic_coverage_decision == Decision.SCALE.value
        )


@dataclass(frozen=True)
class MutationReport:
    baseline_decision: str
    mutations: tuple[Mutation, ...] = field(default_factory=tuple)
    unprovided_coverage: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.mutations)

    @property
    def fixed_contract_killed(self) -> int:
        return sum(1 for m in self.mutations if m.killed_by_fixed_contract)

    @property
    def fixed_contract_score(self) -> float:
        return self.fixed_contract_killed / self.total if self.total else 1.0

    @property
    def survivors(self) -> tuple[Mutation, ...]:
        return tuple(m for m in self.mutations if m.survived_dynamic_coverage)

    @property
    def flips(self) -> tuple[Mutation, ...]:
        return tuple(m for m in self.mutations if m.flipped_to_scale)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_decision": self.baseline_decision,
            "mutations_injected": self.total,
            "fixed_contract_killed": self.fixed_contract_killed,
            "fixed_contract_score": self.fixed_contract_score,
            "dynamic_coverage_survivors": len(self.survivors),
            "false_scale_transitions": len(self.flips),
            "unprovided_required_coverage": list(self.unprovided_coverage),
            "mutations": [
                {
                    "coverage": m.coverage,
                    "removed_check_ids": list(m.removed_check_ids),
                    "baseline_decision": m.baseline_decision,
                    "fixed_contract_decision": m.fixed_contract_decision,
                    "dynamic_coverage_decision": m.dynamic_coverage_decision,
                    "killed_by_fixed_contract": m.killed_by_fixed_contract,
                    "survived_dynamic_coverage": m.survived_dynamic_coverage,
                    "false_scale_transition": m.flipped_to_scale,
                }
                for m in self.mutations
            ],
        }


def providers(
    checks: tuple[CheckSpec, ...],
    required_coverage: frozenset[CoverageLike],
) -> dict[CoverageLike, tuple[str, ...]]:
    """Which checks supply each required coverage dimension."""
    return {
        coverage: tuple(
            sorted(check.id for check in checks if coverage in check.covers)
        )
        for coverage in required_coverage
    }


def _enabled_coverage(checks: tuple[CheckSpec, ...]) -> frozenset[CoverageLike]:
    return frozenset(coverage for check in checks for coverage in check.covers)


def mutate(
    bundle: EvidenceBundle,
    checks: tuple[CheckSpec, ...] | None = None,
    required_coverage: frozenset[CoverageLike] | None = None,
) -> MutationReport:
    """
    Remove each required gate in turn and record what the engine does.

    Two engines are compared for every removal:

    * the **fixed contract**, which pins the required coverage and must return
      INCOMPLETE whenever any of it is missing; and
    * **dynamic coverage**, which derives its requirements from whichever checks
      are currently enabled, so the requirement disappears with the gate.

    A mutation survives when dynamic coverage returns SCALE with a required gate
    removed. That is the failure this whole package exists to make visible: a
    green verdict issued on evidence nobody collected.
    """
    checks = tuple(checks if checks is not None else default_checks())
    required = (
        required_coverage if required_coverage is not None else DEFAULT_REQUIRED_COVERAGE
    )
    baseline = evaluate_bundle(bundle, checks).decision

    by_coverage = providers(checks, required)
    mutations: list[Mutation] = []
    unprovided: list[str] = []

    for coverage in sorted(required, key=_name):
        removed = by_coverage[coverage]
        if not removed:
            # Nothing supplies this requirement, so there is no gate to remove.
            # That is not a passing mutation; it is a contract already unmet.
            unprovided.append(_name(coverage))
            continue
        reduced = tuple(check for check in checks if check.id not in removed)
        fixed = AssuranceEngine(checks=reduced, required_coverage=required).evaluate(bundle)
        dynamic = AssuranceEngine(
            checks=reduced, required_coverage=_enabled_coverage(reduced)
        ).evaluate(bundle)
        mutations.append(
            Mutation(
                coverage=_name(coverage),
                removed_check_ids=removed,
                baseline_decision=baseline.value,
                fixed_contract_decision=fixed.decision.value,
                dynamic_coverage_decision=dynamic.decision.value,
            )
        )

    return MutationReport(
        baseline_decision=baseline.value,
        mutations=tuple(mutations),
        unprovided_coverage=tuple(unprovided),
    )


def render_markdown(report: MutationReport) -> str:
    lines = [
        "# Harness Mutation Score",
        "",
        f"- Baseline decision: **{report.baseline_decision}**",
        f"- Gate removals injected: **{report.total}**",
        f"- Killed by the fixed contract: **{report.fixed_contract_killed} / "
        f"{report.total}** ({report.fixed_contract_score:.1%})",
        f"- Survived under dynamic coverage: **{len(report.survivors)}**",
        f"- False SCALE transitions: **{len(report.flips)}**",
        "",
        "The kill rate is the score for *this* harness. The dynamic-coverage column\n"
        "shows what an engine that derives its requirements from whichever checks\n"
        "happen to be enabled would have returned instead.",
        "",
    ]
    if report.unprovided_coverage:
        lines += [
            "Required coverage with no provider (the contract is already unmet):",
            "",
            *[f"- `{c}`" for c in report.unprovided_coverage],
            "",
        ]
    lines += [
        "| Removed coverage | Checks removed | Fixed contract | Dynamic coverage |",
        "|---|---|---|---|",
    ]
    for m in report.mutations:
        removed = ", ".join(f"`{c}`" for c in m.removed_check_ids)
        marker = "  ← survives" if m.survived_dynamic_coverage else ""
        lines.append(
            f"| `{m.coverage}` | {removed} | {m.fixed_contract_decision} | "
            f"{m.dynamic_coverage_decision}{marker} |"
        )
    lines += [
        "",
        "A gate whose removal still yields SCALE is not load-bearing: the harness",
        "cannot tell whether that evidence was ever collected. A missing gate is not",
        "a passing gate.",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "CoverageLike",
    "Mutation",
    "MutationReport",
    "mutate",
    "providers",
    "render_markdown",
]
