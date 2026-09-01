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
from .evidence import recompute_digest
from .models import CheckSpec, EvidenceBundle, Unsupplied

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
    #: The source revision this claim was issued against, when known.
    #:
    #: Without it the record decays. A claim binds each check by the text that
    #: implemented it, so a comment added inside a gate body makes every prior
    #: claim UNVERIFIED -- demonstrated, not assumed. A track record that resets
    #: on each refactor is not a track record, and calendar time is the only
    #: thing here that cannot be copied.
    #:
    #: Recording it lets a reader ask two different questions: is this still
    #: true of the code today, and was it true when issued. The second is what
    #: makes the record durable.
    source_commit: str = ""
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
            "source_commit": self.source_commit,
        }

    def render(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


@dataclasses.dataclass(frozen=True)
class Verification:
    verdict: Verdict
    claim_assertion: str
    reasons: tuple[str, ...] = ()
    checked: tuple[str, ...] = ()
    #: True of the verification but not grounds to withhold it.
    caveats: tuple[str, ...] = ()
    #: The decision that was reproduced. This, not the prose, is what a
    #: SUPPORTED verdict is about.
    decision: str = ""

    @property
    def supported(self) -> bool:
        return self.verdict is Verdict.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "decision": self.decision,
            "assertion": self.claim_assertion,
            "assertion_is_verified": False,
            "reasons": list(self.reasons),
            "checked": list(self.checked),
            "caveats": list(self.caveats),
        }

    def render(self) -> str:
        # The verdict names the decision, never the prose. `assertion` is free
        # text bound to nothing: "zero breaches, safe for unsupervised rollout"
        # verifies against evidence routing to ASSIST, because only the decision
        # is recomputed. Printing "# SUPPORTED" above that sentence read as an
        # endorsement of it. The heading now says what was actually reproduced,
        # and the prose is marked as the issuer's words.
        heading = (
            f"# {self.verdict.value}: decision `{self.decision}`"
            if self.decision
            else f"# {self.verdict.value}"
        )
        lines = [
            heading,
            "",
            "Issuer's wording, which nothing here verifies:",
            f"> {self.claim_assertion}",
            "",
        ]
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
                f"The decision `{self.decision}` was recomputed from the "
                "evidence supplied and reproduced exactly. That is the whole "
                "of what is verified here. The issuer's wording above is not "
                "checked against it, and nothing establishes that the evidence "
                "describes reality: a bundle can be internally perfect and a "
                "fabrication."
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
        source_commit=str(raw.get("source_commit", "")),
    )


def issue(
    bundle: EvidenceBundle,
    assertion: str,
    *,
    checks: Sequence[CheckSpec] | None = None,
    required_coverage: frozenset[Any] | None = None,
    issued_at: dt.date | None = None,
    issuer: str = "",
    source_commit: str = "",
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
        source_commit=source_commit,
    )


#: Thresholds that cannot bind, whatever the evidence. A gate comparing against
#: one of these keeps its name, claims its coverage, and cannot fail -- which is
#: the failure mode this package was written about, arriving through the numbers
#: rather than through the gate list. The bounds are deliberately generous: this
#: detects a threshold that is *inert*, not one that is merely lenient, because
#: no normative standard for "strict enough" exists and inventing one here would
#: be the fabrication this package refuses.
#: The same test applied to the baseline. `gate.counterfactual` compares the
#: run against it, so the baseline is a pass mark the audited party supplies
#: exactly as the policy is. Checking only the policy left the forgery this
#: guard exists to stop escaping one field over: identical events, identical
#: labels, a baseline costing a million dollars an attempt, and STOP becomes
#: SCALE while the verifier printed "no threshold in this evidence is inert".
#: Only the one value that cannot be an honest declaration. A baseline costing
#: a million dollars an attempt is not a baseline. The first version of this
#: also flagged a non-positive `value_per_acceptable_outcome_usd` and a
#: non-positive `acceptable_rate`, which broke a true published claim: the
#: public SWE-bench case sets value-per-outcome to zero because resolving a
#: benchmark task carries no assigned dollar value, and that is a statement
#: about the domain rather than a rigged pass mark. Flagging an honest zero as
#: a rigged threshold is the same error as accepting a rigged one, pointed the
#: other way, and it is worse here because it refuses evidence that was fine.
_INERT_BASELINE: tuple[tuple[str, str, float], ...] = (
    ("cost_per_attempt_usd", ">=", 1e6),
)

_INERT_THRESHOLDS: tuple[tuple[str, str, float], ...] = (
    ("min_acceptable_rate", "<=", 0.0),
    ("max_cost_per_acceptable_outcome_usd", ">=", 1e6),
    ("max_p95_task_cost_usd", ">=", 1e6),
    ("max_trace_cost_per_task_usd", ">=", 1e6),
    ("max_calls_per_task", ">=", 1e6),
    ("min_expected_net_value_per_attempt_usd", "<=", -1e6),
    ("min_incremental_net_value_vs_baseline_usd", "<=", -1e6),
)


def _inert_against(subject: Any, spec: tuple[tuple[str, str, float], ...]) -> tuple[str, ...]:
    if isinstance(subject, Unsupplied) or subject is None:
        return ()
    found: list[str] = []
    for name, direction, bound in spec:
        try:
            value = float(getattr(subject, name))
        except (AttributeError, TypeError, ValueError):
            continue
        if (direction == "<=" and value <= bound) or (
            direction == ">=" and value >= bound
        ):
            found.append(f"{name}={value:g}")
    return tuple(found)


def inert_baseline(baseline: Any) -> tuple[str, ...]:
    """Baseline values a counterfactual gate could not fail against."""
    return _inert_against(baseline, _INERT_BASELINE)


def _coverage_key(item: Any) -> str:
    """A coverage dimension as it appears in a claim.

    `Coverage` subclasses `str`, so a member IS its value; `str()` on one gives
    "Coverage.BUSINESS_VALUE" and has already produced three separate defects
    in this package. A plain string dimension passes through unchanged.
    """
    return item if isinstance(item, str) else str(item)


def inert_thresholds(policy: Any) -> tuple[str, ...]:
    """Thresholds a gate could not fail against, whatever the evidence showed.

    A policy declared unsupplied has no thresholds to be inert. Reading one
    raises rather than answering, which is the point of `Unsupplied`, so it is
    skipped here: the missing economics are already a ground elsewhere and
    reporting them as a rigged threshold would be a different and false claim.
    """
    if isinstance(policy, Unsupplied) or policy is None:
        return ()
    found: list[str] = []
    for name, direction, bound in _INERT_THRESHOLDS:
        try:
            value = float(getattr(policy, name))
        except (AttributeError, TypeError, ValueError):
            continue
        if (direction == "<=" and value <= bound) or (
            direction == ">=" and value >= bound
        ):
            found.append(f"{name}={value:g}")
    return tuple(found)


def verify(
    claim: Claim,
    bundle: EvidenceBundle,
    *,
    checks: Sequence[CheckSpec] = (),
) -> Verification:
    """Recompute a claim from evidence. Total: never raises, never fails open.

    `checks` supplies implementations this build does not ship. Without it the
    verifier resolved only against `default_checks()`, so the claim layer and
    the custom-gate story were mutually exclusive: a team with a PII gate and a
    jailbreak gate -- the motivating example in `unsupplied` -- could issue a
    claim that nobody, including them, could ever verify.

    Supplying a check does not weaken anything. The claim binds each one by
    `implementation_digest`, so an implementation that differs from the one the
    claim was issued against is still UNVERIFIED, and a caller cannot smuggle a
    permissive substitute in through this argument.
    """
    checked: list[str] = []
    # Read before the try. The handler below reports `assertion`, so reading it
    # there meant a claim that was not a Claim -- a parsed dict, the single most
    # likely caller mistake -- raised AttributeError from inside the handler
    # written to prevent exactly that, in a function documented as total.
    assertion = getattr(claim, "assertion", "<unreadable claim>")
    caveats: list[str] = []

    try:
        # Recomputed, never read off the bundle. `digest` is a stored field, so
        # a bundle built by `dataclasses.replace` carries the original's digest
        # while holding different outcomes: flip every label to acceptable and
        # the digest still matches what was published.
        actual_digest = recompute_digest(bundle)
        if actual_digest != claim.evidence_digest:
            return Verification(
                Verdict.REFUTED, assertion,
                reasons=(
                    "the evidence supplied is not the evidence this claim was "
                    f"issued against (digest {actual_digest[:16]}... against "
                    f"claimed {claim.evidence_digest[:16]}...)",
                ),
            )
        checked.append("evidence digest recomputes from contents and matches")

        # Caller-supplied first, so a build can verify a claim about a gate it
        # does not ship, then the defaults.
        available = {spec.id: spec for spec in default_checks()}
        available.update({spec.id: spec for spec in checks})
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
            where = (
                f" This claim was issued against commit "
                f"{claim.source_commit}; check it out and verify there to ask "
                "whether it was true when made, rather than whether it is "
                "still true of this code."
                if claim.source_commit
                else " This claim records no source commit, so there is no "
                "revision to check it against."
            )
            # Not REFUTED. The claim may be perfectly true; this build simply
            # cannot reproduce it, and saying "false" would be a stronger
            # statement than the evidence licenses.
            return Verification(
                Verdict.UNVERIFIED, assertion,
                reasons=tuple(unavailable + substituted) + (where.strip(),),
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
        # A gate the claim ships whose dimension it does not require is the
        # weakening that matters, and it holds for any contract, custom or not.
        provided = frozenset(
            _coverage_key(item) for spec in specs for item in spec.covers
        )
        unrequired = provided - coverage
        if unrequired:
            return Verification(
                Verdict.UNVERIFIED, assertion,
                reasons=(
                    "this claim carries gates covering "
                    f"{', '.join(sorted(unrequired))} without requiring those "
                    "dimensions, so removing the gate would not change the "
                    "verdict. A requirement does not depart with the gate that "
                    "served it.",
                ),
                checked=tuple(checked),
            )
        checked.append("every dimension this claim's gates cover is required")

        # The shipped floor applies only to a claim built from the shipped
        # checks. Holding a safety-only contract to the economic dimensions
        # refused evidence that was never about them, which made the claim
        # layer and the custom-gate story mutually exclusive.
        shipped = {spec.id for spec in default_checks()}
        if all(binding.id in shipped for binding in claim.checks):
            dropped = frozenset(DEFAULT_REQUIRED_COVERAGE) - coverage
            if dropped:
                return Verification(
                    Verdict.UNVERIFIED, assertion,
                    reasons=(
                        "this claim uses the shipped checks and requires less "
                        f"than the shipped contract: {', '.join(sorted(dropped))} "
                        "is required here and not by the claim. A decision that "
                        "follows from a weakened contract is not a decision "
                        "that follows from this one.",
                    ),
                    checked=tuple(checked),
                )
            checked.append(
                "every dimension the shipped contract requires is required here"
            )
        else:
            absent = sorted(frozenset(DEFAULT_REQUIRED_COVERAGE) - coverage)
            if absent:
                caveats.append(
                    "this is a custom contract; the shipped contract also "
                    f"requires {', '.join(absent)}, which this claim does not"
                )

        # Coverage containment is structural and says nothing about what the
        # gates enforce. The thresholds live in the bundle, which means the
        # audited party supplies its own pass marks: identical events, identical
        # labels, every dimension covered, and ASSIST becomes SCALE. The earlier
        # wording here -- "contract is at least as strong as the shipped one" --
        # was false as printed, and vouched for numbers never inspected.
        inert = inert_thresholds(getattr(bundle, "policy", None)) + inert_baseline(
            getattr(bundle, "baseline", None)
        )
        if inert:
            return Verification(
                Verdict.UNVERIFIED, assertion,
                reasons=(
                    "this evidence carries thresholds no gate could fail "
                    f"against ({', '.join(inert)}). The gates ran and reported "
                    "PASS, which says nothing: a gate that keeps its name and "
                    "cannot fail is the failure this package exists to refuse, "
                    "arriving through the numbers rather than the gate list.",
                ),
                checked=tuple(checked),
            )
        checked.append(
            "no threshold or baseline in this evidence is inert, against the "
            "stated bounds"
        )
        recomputed_contract = decision_contract_digest(tuple(specs), coverage)
        if recomputed_contract != claim.decision_contract_digest:
            return Verification(
                Verdict.REFUTED, assertion,
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
                Verdict.REFUTED, assertion,
                reasons=(
                    f"re-evaluating this evidence yields {case.decision.value}, "
                    f"not the claimed {claim.decision}",
                ),
                checked=tuple(checked),
            )
        checked.append(f"re-evaluation reproduces {claim.decision}")
        return Verification(
            Verdict.SUPPORTED, assertion, checked=tuple(checked),
            decision=claim.decision, caveats=tuple(caveats),
        )
    except Exception as error:
        # Anything unforeseen is a failure to verify, never a pass and never a
        # traceback. A verifier that crashes on a hostile input is a verifier
        # an attacker chooses the input for.
        return Verification(
            Verdict.UNVERIFIED, assertion,
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
