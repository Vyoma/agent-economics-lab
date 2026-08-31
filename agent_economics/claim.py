"""A published claim, and a verifier a stranger can run without trusting you.

Every artifact in this repository so far has been something *we* check. A
reader who does not run the code has to take the numbers on faith, which is the
posture this package exists to argue against, applied to itself.

A `Claim` is the portable form. It carries an assertion, the decision it rests
on, and the digests of the evidence and the decision contract that produced it.
`verify()` recomputes all of it from a bundle and answers in one of three ways:

    SUPPORTED   the evidence reproduces the claimed decision, exactly
    REFUTED     the evidence is present and does not support the claim
    UNVERIFIED  something needed to check is missing, absent, or unavailable

The third is the load-bearing one. A verifier that cannot distinguish "false"
from "I could not tell" is the same fail-open this package catalogues, moved
one level up, so no failure mode returns SUPPORTED and none raises. The
function is total by construction: every path is caught and mapped.

What this buys is the only thing here that does not copy. The format copies
freely and should. A record of claims that strangers checked, accumulated over
calendar time, does not.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

from .assurance import (
    DEFAULT_REQUIRED_COVERAGE,
    AssuranceEngine,
    decision_contract_digest,
    default_checks,
)
from .models import CheckSpec, EvidenceBundle

CLAIM_SCHEMA_VERSION = "assurance.claim@1"


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    UNVERIFIED = "UNVERIFIED"


@dataclasses.dataclass(frozen=True)
class CheckBinding:
    """One check, bound by identity and by the source text that implemented it."""

    id: str
    version: str
    implementation_digest: str

    def to_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Claim:
    """An assertion, and everything needed to check it."""

    assertion: str
    decision: str
    evidence_digest: str
    decision_contract_digest: str
    checks: tuple[CheckBinding, ...]
    required_coverage: tuple[str, ...]
    issued_at: str
    issuer: str = ""
    schema_version: str = CLAIM_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assertion": self.assertion,
            "decision": self.decision,
            "evidence_digest": self.evidence_digest,
            "decision_contract_digest": self.decision_contract_digest,
            "checks": [binding.to_dict() for binding in self.checks],
            "required_coverage": list(self.required_coverage),
            "issued_at": self.issued_at,
            "issuer": self.issuer,
        }

    def render(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


@dataclasses.dataclass(frozen=True)
class Verification:
    verdict: Verdict
    claim_assertion: str
    reasons: tuple[str, ...] = ()
    checked: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.verdict is Verdict.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "assertion": self.claim_assertion,
            "reasons": list(self.reasons),
            "checked": list(self.checked),
        }

    def render(self) -> str:
        lines = [f"# {self.verdict.value}", "", f"> {self.claim_assertion}", ""]
        if self.checked:
            lines.append("Checked, and reproduced:")
            lines += [f"- {item}" for item in self.checked]
            lines.append("")
        if self.reasons:
            heading = (
                "Why the evidence does not support this:"
                if self.verdict is Verdict.REFUTED
                else "Why this could not be checked:"
            )
            lines.append(heading)
            lines += [f"- {item}" for item in self.reasons]
            lines.append("")
        if self.verdict is Verdict.SUPPORTED:
            lines.append(
                "Recomputed from the evidence supplied. This says the decision "
                "follows from that evidence under that contract. It says "
                "nothing about whether the evidence describes reality."
            )
        return "\n".join(lines)


def parse_claim(raw: Mapping[str, Any]) -> Claim:
    """Read a claim document, refusing anything malformed rather than guessing."""
    if raw.get("schema_version") != CLAIM_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {CLAIM_SCHEMA_VERSION}")
    checks = raw.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("claim.checks must be a non-empty list")
    bindings = []
    for entry in checks:
        if not isinstance(entry, Mapping):
            raise ValueError("each claim.checks entry must be an object")
        missing = {"id", "version", "implementation_digest"} - set(entry)
        if missing:
            raise ValueError(f"claim.checks entry missing {sorted(missing)}")
        bindings.append(
            CheckBinding(
                id=str(entry["id"]),
                version=str(entry["version"]),
                implementation_digest=str(entry["implementation_digest"]),
            )
        )
    for field in ("assertion", "decision", "evidence_digest",
                  "decision_contract_digest", "issued_at"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ValueError(f"claim.{field} must be a non-empty string")
    coverage = raw.get("required_coverage")
    if not isinstance(coverage, list):
        raise ValueError("claim.required_coverage must be a list")
    return Claim(
        assertion=raw["assertion"],
        decision=raw["decision"],
        evidence_digest=raw["evidence_digest"],
        decision_contract_digest=raw["decision_contract_digest"],
        checks=tuple(bindings),
        required_coverage=tuple(str(item) for item in coverage),
        issued_at=raw["issued_at"],
        issuer=str(raw.get("issuer", "")),
    )


def issue(
    bundle: EvidenceBundle,
    assertion: str,
    *,
    checks: Sequence[CheckSpec] | None = None,
    required_coverage: frozenset[Any] | None = None,
    issued_at: dt.date | None = None,
    issuer: str = "",
) -> Claim:
    """Evaluate the bundle and bind the result into a portable claim."""
    specs = tuple(default_checks() if checks is None else checks)
    engine = (
        AssuranceEngine(specs)
        if required_coverage is None
        else AssuranceEngine(specs, required_coverage=required_coverage)
    )
    case = engine.evaluate(bundle)
    return Claim(
        assertion=assertion,
        decision=case.decision.value,
        evidence_digest=bundle.digest,
        decision_contract_digest=case.decision_contract_digest,
        # In evaluation order, deliberately not sorted. The decision contract
        # digest binds the order of the checks, so a claim that reorders them
        # describes a different contract and will never reproduce. Sorting here
        # made every issued claim verify as REFUTED.
        checks=tuple(
            CheckBinding(
                id=spec.id, version=spec.version,
                implementation_digest=spec.implementation_digest,
            )
            for spec in specs
        ),
        # The members, not str() of them. `Coverage` subclasses str, so a
        # member IS its value and serialises as it; `str(member)` gives
        # "Coverage.BUSINESS_VALUE" and silently produces a different contract
        # digest, so every claim issued would verify as REFUTED. This is the
        # coverage-stringification defect fixed once already in this package,
        # recurring in new code written the same day.
        required_coverage=tuple(sorted(engine.required_coverage)),
        issued_at=(issued_at or dt.date.today()).isoformat(),
        issuer=issuer,
    )


def verify(claim: Claim, bundle: EvidenceBundle) -> Verification:
    """Recompute a claim from evidence. Total: never raises, never fails open."""
    checked: list[str] = []

    try:
        if bundle.digest != claim.evidence_digest:
            return Verification(
                Verdict.REFUTED, claim.assertion,
                reasons=(
                    "the evidence supplied is not the evidence this claim was "
                    f"issued against (digest {bundle.digest[:16]}... against "
                    f"claimed {claim.evidence_digest[:16]}...)",
                ),
            )
        checked.append("evidence digest matches the claim")

        available = {spec.id: spec for spec in default_checks()}
        specs: list[CheckSpec] = []
        unavailable: list[str] = []
        substituted: list[str] = []
        for binding in claim.checks:
            spec = available.get(binding.id)
            if spec is None:
                unavailable.append(f"{binding.id} is not a check this build knows")
                continue
            if spec.version != binding.version:
                unavailable.append(
                    f"{binding.id} is version {spec.version} here, "
                    f"{binding.version} in the claim"
                )
                continue
            if spec.implementation_digest != binding.implementation_digest:
                substituted.append(
                    f"{binding.id} has different source here than when the "
                    "claim was issued"
                )
                continue
            specs.append(spec)

        if unavailable or substituted:
            # Not REFUTED. The claim may be perfectly true; this build simply
            # cannot reproduce it, and saying "false" would be a stronger
            # statement than the evidence licenses.
            return Verification(
                Verdict.UNVERIFIED, claim.assertion,
                reasons=tuple(unavailable + substituted),
                checked=tuple(checked),
            )
        checked.append(f"all {len(specs)} checks bound by identity and source")

        coverage = frozenset(claim.required_coverage)
        # The contract is stated by the claim, which means it is chosen by
        # whoever issues it. Confirming that a decision follows from a contract
        # the issuer wrote is not verification of anything: dropping the one
        # failing gate and requiring no coverage turned an honest ASSIST into a
        # SUPPORTED claim of "safe to scale, every gate passes".
        #
        # So SUPPORTED means supported under a contract at least as strong as
        # the shipped one. A weakened contract is not refuted -- it may be
        # internally true -- but it cannot be confirmed against the standard,
        # which is exactly this package's own rule that a requirement does not
        # depart with the gate that served it.
        dropped = frozenset(DEFAULT_REQUIRED_COVERAGE) - coverage
        if dropped:
            return Verification(
                Verdict.UNVERIFIED, claim.assertion,
                reasons=(
                    "this claim requires less than the shipped contract: "
                    # `Coverage` subclasses str, so the member IS its value.
                    # str() on it yields "Coverage.BUSINESS_VALUE"; the third
                    # time that trap fired in this package in one day.
                    f"{', '.join(sorted(dropped))} "
                    "is required here and not by the claim. A decision that "
                    "follows from a weakened contract is not a decision that "
                    "follows from this one.",
                ),
                checked=tuple(checked),
            )
        checked.append("contract is at least as strong as the shipped one")
        recomputed_contract = decision_contract_digest(tuple(specs), coverage)
        if recomputed_contract != claim.decision_contract_digest:
            return Verification(
                Verdict.REFUTED, claim.assertion,
                reasons=(
                    "the decision contract does not recompute to the claimed "
                    f"digest ({recomputed_contract[:16]}... against "
                    f"{claim.decision_contract_digest[:16]}...)",
                ),
                checked=tuple(checked),
            )
        checked.append("decision contract digest recomputes")

        case = AssuranceEngine(
            tuple(specs), required_coverage=coverage
        ).evaluate(bundle)
        if case.decision.value != claim.decision:
            return Verification(
                Verdict.REFUTED, claim.assertion,
                reasons=(
                    f"re-evaluating this evidence yields {case.decision.value}, "
                    f"not the claimed {claim.decision}",
                ),
                checked=tuple(checked),
            )
        checked.append(f"re-evaluation reproduces {claim.decision}")
        return Verification(
            Verdict.SUPPORTED, claim.assertion, checked=tuple(checked)
        )
    except Exception as error:
        # Anything unforeseen is a failure to verify, never a pass and never a
        # traceback. A verifier that crashes on a hostile input is a verifier
        # an attacker chooses the input for.
        return Verification(
            Verdict.UNVERIFIED, claim.assertion,
            reasons=(f"verification could not complete: {type(error).__name__}: {error}",),
            checked=tuple(checked),
        )


__all__ = [
    "CLAIM_SCHEMA_VERSION",
    "CheckBinding",
    "Claim",
    "Verdict",
    "Verification",
    "issue",
    "parse_claim",
    "verify",
]
