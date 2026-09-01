"""Checks resolvable by name, so a contract is composed rather than compiled in.

`default_checks()` was a literal, and four consumers baked it in. That one
decision forked the package into two verdict systems: an `AssuranceEngine`
running six economic gates, and an `AuditReport` reimplementing delegation and
provenance assessment beside it, because the engine could not be configured to
hold them. The shipped delegation and provenance gates reached no CLI decision
at all, and `claim.verify` could only verify the six built-ins.

A registry resolves an id to a *builder* rather than to a finished spec, because
the two most consequential gates are factories: what they enforce lives in
arguments drawn from the bundle and from the caller. A builder takes both and
returns the spec, so `gate.delegation-closure` can be named on a command line
and still be built from the declarations the evidence actually carries.

Registering does not enable. A contract is the checks a caller asks for, and
asking is explicit everywhere: `--check` on the command line, a `checks`
argument in the library. Nothing here changes what `default_checks()` returns,
so the shipped contract digest does not move.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .checks import default_checks
from .delegation import delegation_closure_gate
from .models import CheckSpec, EvidenceBundle
from .provenance import Attestation, ProvenancePolicy, evidence_provenance_gate


class UnknownCheck(LookupError):
    """Raised for a check id the registry does not hold.

    A contract naming a check nobody can build is not a weaker contract, it is
    an unreadable one, so this refuses rather than silently omitting the check
    and evaluating what remains.
    """


@dataclasses.dataclass(frozen=True)
class BuildContext:
    """What a builder may read: the evidence, and what the caller asked for."""

    bundle: EvidenceBundle | None = None
    config: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)


@dataclasses.dataclass(frozen=True)
class CheckBuilder:
    id: str
    version: str
    build: Callable[[BuildContext], CheckSpec]
    summary: str


def _static(spec: CheckSpec, summary: str) -> CheckBuilder:
    return CheckBuilder(
        id=spec.id, version=spec.version, build=lambda _ctx: spec, summary=summary
    )


def _build_delegation_closure(context: BuildContext) -> CheckSpec:
    """Declared delegations come from the evidence, thresholds from the caller.

    Reading the manifest off the bundle is the point: a contract that let the
    caller supply it could declare every delegation accounted for without the
    evidence saying so.
    """
    declared = context.get("declared")
    if declared is None:
        declared = (
            context.bundle.declared_delegations if context.bundle is not None else ()
        )
    return delegation_closure_gate(
        declared=tuple(declared),
        delegation_tools=tuple(context.get("delegation_tools", ("Task", "Agent"))),
        minimum_closure=float(context.get("minimum_closure", 1.0)),
    )


def _build_evidence_provenance(context: BuildContext) -> CheckSpec:
    """The instrument is whatever the evidence says produced its labels."""
    instruments = context.get("instruments")
    if instruments is None:
        label_source = (
            context.bundle.label_source if context.bundle is not None else ""
        )
        instruments = (label_source,) if label_source else ()
    raw = context.get("attestations", {}) or {}
    attestations = {
        name: value if isinstance(value, Attestation)
        else Attestation(instrument=name, **value)
        for name, value in raw.items()
    }
    as_of = context.get("as_of") or dt.date.today()
    if isinstance(as_of, str):
        as_of = dt.date.fromisoformat(as_of)
    policy = context.get("policy")
    if isinstance(policy, Mapping):
        policy = ProvenancePolicy(**policy)
    return evidence_provenance_gate(
        instruments=tuple(instruments),
        attestations=attestations,
        as_of=as_of,
        policy=policy,
        independently_verified=tuple(context.get("independently_verified", ())),
    )


class CheckRegistry:
    """Builders by id. Resolution is by id; version is reported, never guessed."""

    def __init__(self, builders: Sequence[CheckBuilder] = ()) -> None:
        self._builders: dict[str, CheckBuilder] = {}
        for builder in builders:
            self.register(builder)

    def register(self, builder: CheckBuilder) -> None:
        if builder.id in self._builders:
            raise ValueError(f"check {builder.id!r} is already registered")
        self._builders[builder.id] = builder

    def __contains__(self, check_id: object) -> bool:
        return check_id in self._builders

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._builders))

    def describe(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(
            (b.id, b.version, b.summary)
            for b in sorted(self._builders.values(), key=lambda b: b.id)
        )

    def build(
        self,
        check_id: str,
        *,
        bundle: EvidenceBundle | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> CheckSpec:
        builder = self._builders.get(check_id)
        if builder is None:
            raise UnknownCheck(
                f"no check registered as {check_id!r}. Known: "
                f"{', '.join(self.ids())}"
            )
        return builder.build(BuildContext(bundle=bundle, config=config or {}))

    def compose(
        self,
        check_ids: Sequence[str],
        *,
        bundle: EvidenceBundle | None = None,
        config: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> tuple[CheckSpec, ...]:
        """Build a contract, in the order asked for.

        Order is preserved because the decision-contract digest binds it: two
        contracts holding the same checks in different orders are different
        contracts, and silently sorting here would make a claim unreproducible.
        """
        per_check = config or {}
        return tuple(
            self.build(check_id, bundle=bundle, config=per_check.get(check_id, {}))
            for check_id in check_ids
        )


def default_registry() -> CheckRegistry:
    """Every check this build ships, including the two nothing could reach."""
    registry = CheckRegistry()
    summaries = {
        "gate.acceptable-rate": "outcome quality against the policy floor",
        "gate.unit-economics": "cost per acceptable outcome against its ceiling",
        "gate.tail-cost": "p95 task cost against its ceiling",
        "gate.net-value": "expected net value per attempt",
        "gate.counterfactual": "incremental net value against the named baseline",
        "gate.runtime-caps": "per-task call and trace-cost caps",
        "diagnostic.repeated-tool-shape": "repeated identical tool calls, reported not gated",
        "diagnostic.directed-cycle": "cycles in the dependency graph, reported not gated",
    }
    for spec in default_checks():
        registry.register(_static(spec, summaries.get(spec.id, spec.id)))
    registry.register(CheckBuilder(
        id="gate.delegation-closure", version="1",
        build=_build_delegation_closure,
        summary="delegated work the conversion contract undertook to assess",
    ))
    registry.register(CheckBuilder(
        id="gate.evidence-provenance", version="1",
        build=_build_evidence_provenance,
        summary="calibration of the instrument that produced the outcome labels",
    ))
    return registry


__all__ = [
    "BuildContext",
    "CheckBuilder",
    "CheckRegistry",
    "UnknownCheck",
    "default_registry",
]
