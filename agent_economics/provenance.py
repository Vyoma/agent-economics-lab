"""
Attestation for the instruments that produced the evidence.

Every gate in this package rests on evidence, and every piece of evidence was
produced by something: a rubric applied by a human, an LLM judge, a subagent
whose output rolled up into its parent's totals, a metric pipeline. The contract
already records *which* instrument (`outcome_contract.label_source`). Nothing
records whether that instrument works.

That is the same hole the rest of this package refuses one level up. An
acceptable-rate gate is only as good as the labels beneath it, and a judge with
0.62 agreement against forty samples measured eight months ago is a materially
different instrument from one at 0.94 against five hundred last week. Today both
read as `label_source` and neither is checked, so the decision inherits a
confidence nobody established.

Manufacturing settled this a long time ago. A measuring instrument carries a
calibration certificate: what it was checked against, how closely it agreed, how
large the sample was, and when. Measurements taken with a lapsed certificate are
not accepted. That is all this module is, applied to eval instruments:

    an unattested instrument supplying a sole-provider gate forces INCOMPLETE

Which is exactly what this package already says about a missing gate. The point
is that the rule was never applied to its own labels.

Prior art, because there is a lot: metrology calibration certificates and their
expiry, measurement systems analysis and Gauge R&R in manufacturing, inter-rater
reliability in the social sciences, W3C PROV for lineage, and the substantial
current literature on calibrating LLM judges against human labels. What appears
absent is gating a deployment decision on the calibration state of the instrument
that produced its evidence. See docs/landscape.md.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .models import CheckMode, CheckOutput, CheckResult, CheckSpec, CheckStatus, Decision

# The coverage dimension this module supplies.
EVIDENCE_PROVENANCE = "evidence_provenance"


class UnattestedInstrument(LookupError):
    """
    Raised when evidence came from an instrument nobody validated.

    An exception rather than a FAIL result, for the same reason unaccounted
    delegation raises: the engine requires a failing gate to route to ASSIST or
    STOP, and neither is true. An uncalibrated judge has not produced a bad
    result. It has produced a result of unknown quality, and the honest verdict
    for unknown quality is INCOMPLETE.
    """


@dataclass(frozen=True)
class Attestation:
    """
    A calibration record for one evidence-producing instrument.

    `agreement` is deliberately unnamed as to method: agreement against human
    adjudication, Cohen's kappa, and a held-out accuracy are different things and
    this does not pretend otherwise. `method` says which, and a consumer that
    cares must read it. What is enforced here is that a number exists, that it was
    measured against something named, on a stated sample, on a stated date.
    """

    instrument: str
    method: str
    agreement: float
    sample_size: int
    reference: str
    measured_at: str

    def age_days(self, as_of: dt.date) -> int:
        measured = dt.date.fromisoformat(self.measured_at[:10])
        return (as_of - measured).days


# Agreement is not one quantity. Raw agreement, Cohen's kappa and held-out
# accuracy answer different questions and do not share a threshold: kappa
# discounts chance agreement, raw agreement does not, so 0.8 means something
# materially different in each. A single `min_agreement` compared across all
# three was a category error, and a metrology reviewer would say so first.
# ILAC-G8 requires a conformity statement to declare its decision rule; these
# are ours, and an attestation whose method is not named here is refused rather
# than silently graded on someone else's scale.
METHOD_FLOORS: dict[str, float] = {
    "agreement-vs-human-adjudication": 0.80,
    "raw-agreement": 0.80,
    "cohens-kappa": 0.60,
    "fleiss-kappa": 0.60,
    "krippendorff-alpha": 0.667,
    "held-out-accuracy": 0.80,
    # Reliability, not validity. See RELIABILITY_ONLY_METHODS.
    "test-retest-agreement": 0.80,
}

#: Methods that measure whether an instrument repeats itself, not whether it is
#: right. An instrument can score identical inputs identically every time and be
#: systematically wrong about all of them, so a high figure here is necessary
#: and nowhere near sufficient.
#:
#: This distinction exists because measuring one of these is much easier than
#: measuring the other, which makes it tempting to report the easy number and
#: let a reader supply the interpretation. Accepting a test-retest figure where
#: a validity figure is required is the same error as grading one method on
#: another's scale, which `floor_for` already refuses.
RELIABILITY_ONLY_METHODS: frozenset[str] = frozenset({"test-retest-agreement"})


@dataclass(frozen=True)
class ProvenancePolicy:
    """
    What an attestation must show before its instrument's evidence is accepted.

    `min_agreement` overrides the per-method floor when set; leaving it None uses
    METHOD_FLOORS, which is the defensible default. The floors are conventional
    landmarks, not derived from this package's data, and are stated as such.
    """

    min_agreement: float | None = None
    min_sample_size: int = 100
    max_age_days: int = 180

    def floor_for(self, method: str) -> float:
        if self.min_agreement is not None:
            return self.min_agreement
        try:
            return METHOD_FLOORS[method]
        except KeyError:
            raise ValueError(
                f"unknown attestation method {method!r}; add it to METHOD_FLOORS "
                "with a stated floor, or set ProvenancePolicy.min_agreement "
                "explicitly. Grading an unknown method against another method's "
                "threshold is not a decision rule."
            ) from None


@dataclass(frozen=True)
class InstrumentStatus:
    instrument: str
    attested: bool
    reason: str = ""
    agreement: float | None = None
    sample_size: int | None = None
    age_days: int | None = None

    @property
    def accepted(self) -> bool:
        return self.attested and not self.reason


@dataclass(frozen=True)
class ProvenanceReport:
    statuses: tuple[InstrumentStatus, ...] = ()
    policy: ProvenancePolicy = ProvenancePolicy()

    @property
    def instruments(self) -> tuple[str, ...]:
        return tuple(s.instrument for s in self.statuses)

    @property
    def rejected(self) -> tuple[InstrumentStatus, ...]:
        return tuple(s for s in self.statuses if not s.accepted)

    @property
    def all_accepted(self) -> bool:
        return not self.rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_accepted": self.all_accepted,
            "instruments": len(self.statuses),
            "rejected": len(self.rejected),
            "policy": {
                "min_agreement": self.policy.min_agreement,
                "min_sample_size": self.policy.min_sample_size,
                "max_age_days": self.policy.max_age_days,
            },
            "detail": [
                {
                    "instrument": s.instrument,
                    "attested": s.attested,
                    "accepted": s.accepted,
                    "reason": s.reason,
                    "agreement": s.agreement,
                    "sample_size": s.sample_size,
                    "age_days": s.age_days,
                }
                for s in self.statuses
            ],
        }


def parse_attestations(raw: Any) -> dict[str, Attestation]:
    """Read the attestation records from a conversion contract."""
    if raw is None:
        return {}
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("evidence_provenance.attestations must be a list")
    out: dict[str, Attestation] = {}
    for index, row in enumerate(raw):
        if not isinstance(row, Mapping):
            raise ValueError(f"attestations[{index}] must be an object")
        missing = [
            key
            for key in (
                "instrument", "method", "agreement",
                "sample_size", "reference", "measured_at",
            )
            if row.get(key) in (None, "")
        ]
        if missing:
            raise ValueError(
                f"attestations[{index}] is missing {', '.join(missing)}; an "
                "attestation without them establishes nothing"
            )
        attestation = Attestation(
            instrument=str(row["instrument"]),
            method=str(row["method"]),
            agreement=float(row["agreement"]),
            sample_size=int(row["sample_size"]),
            reference=str(row["reference"]),
            measured_at=str(row["measured_at"]),
        )
        if attestation.instrument in out:
            raise ValueError(f"Duplicate attestation for {attestation.instrument!r}")
        try:
            dt.date.fromisoformat(attestation.measured_at[:10])
        except ValueError as error:
            raise ValueError(
                f"attestations[{index}].measured_at is not a date: {error}"
            ) from error
        out[attestation.instrument] = attestation
    return out


def assess_provenance(
    instruments: Sequence[str],
    attestations: Mapping[str, Attestation],
    *,
    policy: ProvenancePolicy | None = None,
    as_of: dt.date,
    independently_verified: Sequence[str] = (),
) -> ProvenanceReport:
    """
    Check every instrument this run's evidence depends on.

    `as_of` is required rather than defaulted to today, because a verdict that
    silently changes with the wall clock is not reproducible, and every artifact
    in this package is meant to be.
    """
    policy = policy or ProvenancePolicy()
    corroborated = set(independently_verified)
    statuses: list[InstrumentStatus] = []
    for instrument in sorted(set(instruments)):
        if instrument in corroborated:
            # Its output is checked by something else, so this instrument is not
            # the sole provider of its evidence and need not be attested. This is
            # DO-178C's independent-verification exemption, borrowed knowingly.
            statuses.append(
                InstrumentStatus(
                    instrument=instrument,
                    attested=True,
                    reason="",
                )
            )
            continue
        record = attestations.get(instrument)
        if record is None:
            statuses.append(
                InstrumentStatus(
                    instrument=instrument,
                    attested=False,
                    reason="no attestation: nothing establishes that this "
                           "instrument measures what the decision assumes",
                )
            )
            continue
        age = record.age_days(as_of)
        reasons = []
        if record.method in RELIABILITY_ONLY_METHODS:
            # Recorded, and deliberately not sufficient. This measures whether
            # the instrument repeats itself, which an instrument that is
            # consistently wrong also does. Reporting it where a validity
            # figure is required would let the easy measurement stand in for
            # the hard one.
            reasons.append(
                f"{record.method} measures repeatability, not correctness; "
                "an instrument can score identical inputs identically and be "
                "wrong about all of them. Supply a validity measurement "
                f"({', '.join(sorted(set(METHOD_FLOORS) - RELIABILITY_ONLY_METHODS))})"
            )
        floor = policy.floor_for(record.method)
        if record.agreement < floor:
            reasons.append(
                f"{record.method} {record.agreement:.2f} below {floor:.2f}"
            )
        if record.sample_size < policy.min_sample_size:
            reasons.append(
                f"sample of {record.sample_size} below {policy.min_sample_size}"
            )
        if age < 0:
            # `age_days` goes negative and the only test was `age > max_age`,
            # so a certificate issued after the audit date read as freshly
            # calibrated. A measurement that has not been taken yet is not a
            # measurement.
            reasons.append(
                f"calibrated {-age} days in the future, which is not a "
                "calibration that has happened"
            )
        elif age > policy.max_age_days:
            reasons.append(f"calibrated {age} days ago, limit {policy.max_age_days}")
        statuses.append(
            InstrumentStatus(
                instrument=instrument,
                attested=True,
                reason="; ".join(reasons),
                agreement=record.agreement,
                sample_size=record.sample_size,
                age_days=age,
            )
        )
    return ProvenanceReport(statuses=tuple(statuses), policy=policy)


def evidence_provenance_gate(
    *,
    instruments: Sequence[str],
    attestations: Mapping[str, Attestation],
    as_of: dt.date,
    policy: ProvenancePolicy | None = None,
    independently_verified: Sequence[str] = (),
) -> CheckSpec:
    """A gate requiring that every evidence-producing instrument is in calibration.

    `independently_verified` names instruments whose output is checked by
    something else, so they are not the sole provider of their evidence. The
    carve-out existed in `assess_provenance` and in the audit but could not be
    reached through this gate, so the audit reported no grounds on a
    corroborated instrument and the gate then refused it. Erring safe, but the
    audit reads as a prediction of the gate and was not one.
    """

    def run(_view) -> CheckOutput:
        report = assess_provenance(
            instruments, attestations, policy=policy, as_of=as_of,
            independently_verified=independently_verified,
        )
        if not report.all_accepted:
            detail = "; ".join(
                f"{s.instrument}: {s.reason}" for s in report.rejected
            )
            raise UnattestedInstrument(
                f"{len(report.rejected)} of {len(report.statuses)} evidence "
                f"instrument(s) cannot be relied on ({detail})"
            )
        # An instrument exempted as not-sole-provider has no agreement figure,
        # because nothing attested it. Formatting None here raised TypeError, so
        # the success path crashed on exactly the case the carve-out exists for.
        summary = ", ".join(
            (
                f"{s.instrument} corroborated elsewhere, not attested"
                if s.agreement is None
                else f"{s.instrument} at {s.agreement:.2f} on "
                f"{s.sample_size}, {s.age_days}d old"
            )
            for s in report.statuses
        )
        return CheckOutput(
            results=(
                CheckResult(
                    check_id="gate.evidence-provenance",
                    status=CheckStatus.PASS,
                    message=summary or "no instruments declared",
                ),
            )
        )

    return CheckSpec(
        id="gate.evidence-provenance",
        version="1",
        mode=CheckMode.GATE,
        covers=frozenset({EVIDENCE_PROVENANCE}),
        run=run,
        failure_route=Decision.STOP,
        # As with the closure gate, everything this enforces is captured here.
        # A policy of min_agreement=0.0, min_sample_size=0 and an effectively
        # unbounded max_age is a gate that cannot fail; the digest must say so.
        config={
            "instruments": sorted(instruments),
            # The records themselves, not just their names: a decision gated
            # on a 0.95/n=500 certificate and one gated on kappa 0.10/n=3
            # produced byte-identical contract digests, which contradicted the
            # sentence below. What the gate enforces is the record's content.
            "attestations": {
                name: {
                    "method": record.method,
                    "agreement": record.agreement,
                    "sample_size": record.sample_size,
                    "reference": record.reference,
                    "measured_at": record.measured_at,
                }
                for name, record in sorted(attestations.items())
            },
            "independently_verified": sorted(independently_verified),
            "as_of": as_of.isoformat(),
            "policy": (
                {
                    "min_agreement": (policy or ProvenancePolicy()).min_agreement,
                    "min_sample_size": (policy or ProvenancePolicy()).min_sample_size,
                    "max_age_days": (policy or ProvenancePolicy()).max_age_days,
                }
            ),
        },
    )


__all__ = [
    "EVIDENCE_PROVENANCE",
    "Attestation",
    "InstrumentStatus",
    "ProvenancePolicy",
    "ProvenanceReport",
    "UnattestedInstrument",
    "assess_provenance",
    "evidence_provenance_gate",
    "parse_attestations",
]
