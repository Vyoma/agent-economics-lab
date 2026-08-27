"""
One question, asked four ways: what can this harness not tell you?

Everything else in this package answers a narrower question through its own
entry point, and the effect is that the stance the package takes is spread
across four commands nobody runs together. This composes them.

The four grounds on which a verdict is withheld, and what each catches:

1. **Unprovided coverage.** A required dimension no enabled check supplies.
   Statically computable. The contract cannot be met as written.
2. **Gates that are not load-bearing.** Removing a gate and re-evaluating shows
   which ones actually carry this run's verdict. Under a fixed contract the
   engine refuses every removal by construction, so that line is a regression
   test, not a score. What varies, and what is reported, is which gates are
   *pivotal* for this bundle.
3. **Unaccounted delegation.** Work spawned at runtime that no contract
   undertook to assess. Measured against the declared manifest, not against the
   trace, so a perfectly-recorded subagent nobody declared still counts.
4. **Unattested instruments.** Evidence produced by something whose accuracy
   nobody established, or established too long ago.

None of these is a score. Each is a reason the honest answer is `INCOMPLETE`.

This runs on a bundle carrying no economics at all
(`agent_economics.unsupplied.checks_only_bundle`), so a team with a PII gate and
a jailbreak gate can ask the question without first inventing a rate card.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .assurance import AssuranceEngine
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .delegation import assess_bundle_closure
from .models import CheckSpec, EvidenceBundle
from .mutation import mutate
from .provenance import Attestation, ProvenancePolicy, assess_provenance


@dataclass(frozen=True)
class AuditReport:
    decision: str
    unprovided_coverage: tuple[str, ...] = ()
    pivotal_gates: tuple[str, ...] = ()
    total_gates: int = 0
    unaccounted_delegations: tuple[str, ...] = ()
    delegated_spend_unassessed: float = 0.0
    closure: float = 1.0
    unattested_instruments: tuple[tuple[str, str], ...] = ()
    instruments_checked: tuple[str, ...] = ()
    conformance_held: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def grounds(self) -> tuple[str, ...]:
        """Every reason this harness cannot support a verdict."""
        reasons = []
        if self.unprovided_coverage:
            reasons.append("unprovided coverage")
        if self.unaccounted_delegations:
            reasons.append("unaccounted delegation")
        if self.unattested_instruments:
            reasons.append("unattested instruments")
        if not self.conformance_held:
            reasons.append("fail-closed invariant broken")
        return tuple(reasons)

    @property
    def assessable(self) -> bool:
        return not self.grounds

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "assessable": self.assessable,
            "grounds": list(self.grounds),
            "unprovided_coverage": list(self.unprovided_coverage),
            "pivotal_gates": list(self.pivotal_gates),
            "total_gates": self.total_gates,
            "unaccounted_delegations": list(self.unaccounted_delegations),
            "delegated_spend_unassessed": self.delegated_spend_unassessed,
            "closure": self.closure,
            "unattested_instruments": [
                {"instrument": i, "reason": r} for i, r in self.unattested_instruments
            ],
            "instruments_checked": list(self.instruments_checked),
            "fail_closed_conformance": self.conformance_held,
            "notes": list(self.notes),
        }


def audit(
    bundle: EvidenceBundle,
    checks: Sequence[CheckSpec] | None = None,
    required_coverage: frozenset[Any] | None = None,
    *,
    attestations: Mapping[str, Attestation] | None = None,
    policy: ProvenancePolicy | None = None,
    independently_verified: Sequence[str] = (),
    as_of: dt.date | None = None,
) -> AuditReport:
    """
    Ask all four questions and report every ground for withholding a verdict.

    `as_of` is required for the attestation age check to mean anything, and is
    only defaulted to today when instruments are actually being checked, so a
    run with no attestations stays reproducible.
    """
    checks = tuple(checks if checks is not None else default_checks())
    required = (
        required_coverage if required_coverage is not None else DEFAULT_REQUIRED_COVERAGE
    )

    verdict = AssuranceEngine(checks=checks, required_coverage=required).evaluate(bundle)
    mutation = mutate(bundle, checks, required)
    closure = assess_bundle_closure(bundle)

    instruments = [i for i in (bundle.label_source,) if i]
    unattested: list[tuple[str, str]] = []
    notes: list[str] = []
    if instruments:
        if attestations is None and not independently_verified:
            unattested = [
                (i, "no attestation supplied to this audit") for i in instruments
            ]
        else:
            provenance = assess_provenance(
                instruments,
                attestations or {},
                policy=policy,
                as_of=as_of or dt.date.today(),
                independently_verified=independently_verified,
            )
            unattested = [(s.instrument, s.reason) for s in provenance.rejected]
    else:
        notes.append(
            "no evidence instrument recorded; this bundle cannot say what "
            "produced its labels"
        )

    if closure.suspected_delegations:
        notes.append(
            f"{len(closure.suspected_delegations)} tool call(s) spawned model work "
            "but are not known delegation tools"
        )

    return AuditReport(
        decision=verdict.decision.value,
        unprovided_coverage=mutation.unprovided_coverage,
        pivotal_gates=tuple(sorted(m.coverage for m in mutation.flips)),
        total_gates=mutation.total,
        unaccounted_delegations=tuple(d.name for d in closure.unaccounted),
        delegated_spend_unassessed=closure.unaccounted_cost_usd,
        closure=closure.closure,
        unattested_instruments=tuple(unattested),
        instruments_checked=tuple(instruments),
        conformance_held=mutation.fail_closed_conformance,
        notes=tuple(notes),
    )


def render_markdown(report: AuditReport) -> str:
    lines = [
        "# What this harness cannot tell you",
        "",
        f"- Verdict on the evidence as supplied: **{report.decision}**",
        f"- Assessable: **{'yes' if report.assessable else 'no'}**",
    ]
    if report.grounds:
        lines.append(f"- Withheld on: **{', '.join(report.grounds)}**")
    lines.append("")

    lines += ["## 1. Coverage with no provider", ""]
    if report.unprovided_coverage:
        lines += [
            f"- `{c}` — no enabled check supplies this"
            for c in report.unprovided_coverage
        ]
        lines.append("")
        lines.append("The contract cannot be met as written.")
    else:
        lines.append("Every required dimension has an enabled provider.")
    lines.append("")

    lines += ["## 2. Which gates carry this verdict", ""]
    if report.total_gates == 0:
        lines.append("No required gate could be removed, so nothing was measured.")
    elif report.pivotal_gates:
        lines += [
            f"- `{g}` is pivotal: removing it flips this run green"
            for g in report.pivotal_gates
        ]
        others = report.total_gates - len(report.pivotal_gates)
        lines += ["", f"The other {others} "
                  f"{'gate is' if others == 1 else 'gates are'} not load-bearing for "
                  "this bundle, which is a property of the evidence rather than of "
                  "the harness."]
    else:
        lines.append(
            f"None of the {report.total_gates} required gates is pivotal for this "
            "bundle. That is what a passing run looks like, not a defect."
        )
    lines += ["", f"Fail-closed conformance: **{'held' if report.conformance_held else 'BROKEN'}** "
              "(an invariant, not a score).", ""]

    lines += ["## 3. Delegated work nobody undertook to assess", ""]
    if report.unaccounted_delegations:
        lines += [
            f"- `{d}` spawned work that no contract declared"
            for d in report.unaccounted_delegations
        ]
        lines += ["", f"${report.delegated_spend_unassessed:.4f} of delegated spend is "
                  f"unassessed; closure {report.closure:.0%}."]
    else:
        lines.append(f"All delegated work is accounted for (closure {report.closure:.0%}).")
    lines.append("")

    lines += ["## 4. Instruments nobody validated", ""]
    if report.unattested_instruments:
        lines += [f"- `{i}` — {r}" for i, r in report.unattested_instruments]
    elif report.instruments_checked:
        lines.append(
            "Every evidence-producing instrument carries a current attestation: "
            + ", ".join(f"`{i}`" for i in report.instruments_checked)
        )
    else:
        lines.append("No evidence instrument is recorded on this bundle.")
    lines.append("")

    if report.notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in report.notes] + [""]

    lines += [
        "---",
        "",
        "None of the above is a score. Each is a reason the honest answer is",
        "`INCOMPLETE` rather than a number, and every one of them is a question",
        "the evidence itself cannot settle.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["AuditReport", "audit", "render_markdown"]
