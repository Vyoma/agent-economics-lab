"""
Mutation testing for the evaluation harness itself.

What this is, stated precisely, because a vaguer claim did not survive review.

It removes every provider of one required coverage dimension, re-evaluates, and
records what two engines do about it. It is two different things at once, and
conflating them was the error:

1. **A conformance test for the fail-closed invariant.** Under a fixed contract
   the answer is INCOMPLETE by construction: removing a dimension's only
   providers puts it in `required - enabled`, and the engine refuses. That
   verdict is analytically constant, not a measurement. It is worth running in
   CI as a regression test on the invariant, and it is worth nothing as a score.
   A sweep of all 252 non-empty subsets of the shipped checks returns 1.0 every
   time. Reporting it as "100% of gates are load-bearing" would be reporting a
   tautology as a finding.

2. **A per-bundle sensitivity analysis.** Under an engine that derives its
   requirements from whichever checks are currently enabled, removing a gate can
   turn a non-green verdict green. That number does vary, and it is genuinely
   informative, but it describes *this bundle under this policy*, not the check
   set. Loosen the thresholds until everything passes and every dimension
   "survives", because no gate is pivotal when nothing is failing. Code coverage
   does not behave this way, so the analogy to it does not hold.

The statically useful output is `unprovided_coverage`: required dimensions that
no enabled check supplies at all. That is a real defect, computable without
evaluating anything, and it is what `--ci` should fail on.

Prior art, because this is a narrower contribution than it first looked: mutating
the checker rather than the design goes back to Di Guglielmo et al. (DATE 2010);
"is this check load-bearing" is Schuler and Zeller's checked coverage; coverage
metrics over a specification by mutation are Chockler, Kupferman and Vardi; and
leave-one-out gate ablation for LLM release decisions was published in
arXiv:2603.15676 months before this package existed. See docs/landscape.md.

This works on any EvidenceBundle and any check set, including checks you wrote.
The required coverage is read from the contract and the providers of each
dimension are derived from `CheckSpec.covers`, so nothing here is specific to
the six gates this package ships.

    from agent_economics import load_normalized_json_bundle
    from agent_economics.mutation import mutate

    report = mutate(load_normalized_json_bundle("bundle.json"))
    report.unprovided_coverage      # required dimensions nothing supplies: a defect
    report.fail_closed_conformance  # invariant held; constant, not a score
    report.flips                    # gates pivotal for THIS bundle under THIS policy
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assurance import AssuranceEngine
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
    def fail_closed_conformance(self) -> bool:
        """
        Did the fixed contract refuse every removal?

        This is an invariant, not a score. It is True for every input the engine
        can be given, so it earns its place as a regression test that would catch
        the invariant being broken, and nothing more. Do not publish it as a
        measurement of a harness.
        """
        return self.fixed_contract_killed == self.total

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
            "fail_closed_conformance": self.fail_closed_conformance,
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
    # Must use the caller's contract, not the shipped one. Evaluating a custom
    # required-coverage set against DEFAULT_REQUIRED_COVERAGE reported INCOMPLETE
    # for every custom harness, which made the whole custom path useless.
    baseline = (
        AssuranceEngine(checks=checks, required_coverage=required)
        .evaluate(bundle)
        .decision
    )

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
        "# Gate Removal Conformance",
        "",
        f"- Baseline decision: **{report.baseline_decision}**",
        f"- Gate removals injected: **{report.total}**",
        f"- Fail-closed conformance: **{'held' if report.fail_closed_conformance else 'BROKEN'}** "
        f"({report.fixed_contract_killed} / {report.total} removals refused)",
        f"- Pivotal for this bundle under dynamic coverage: **{len(report.flips)}**",
        "",
        "Conformance is an invariant, not a score: a fixed contract refuses every",
        "removal by construction, so this line is a regression test and reads `held`",
        "for any harness. The pivotal count is a sensitivity analysis of *this bundle",
        "under this policy*, not a property of the check set: loosen the thresholds",
        "until nothing fails and every dimension becomes non-pivotal.",
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
        "The actionable line is unprovided coverage, if any: a required dimension no",
        "enabled check supplies is a contract that cannot be met, and it is the one",
        "result here that is a property of the harness rather than of this bundle.",
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
