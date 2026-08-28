"""
Inputs the operator has not supplied.

The adapters refuse to invent economics, and that refusal previously had a cost:
`EvidenceBundle` required a rate card, a baseline and a policy whether or not any
enabled check read them. A team with a PII gate and a jailbreak gate had to
fabricate a price per million tokens and a named baseline before the engine would
look at anything, which is precisely the fabrication this package exists to
prevent.

An unsupplied input is not zero and not a default. It is a value that raises when
anything reads it. Combined with the engine's fail-closed handling of a check that
cannot run, the result is the behaviour the contract already promised: a gate whose
evidence was never supplied yields `INCOMPLETE`, and gates that do not touch the
missing input run normally.

    from agent_economics.unsupplied import checks_only_bundle

    bundle = checks_only_bundle(
        events=my_events, outcomes=my_outcomes, source_id="source.my-eval"
    )
    mutate(bundle, my_checks, frozenset({"pii_safety"}))

Nothing is fabricated. Ask the bundle for a price and it tells you that you never
gave it one.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .evidence import make_evidence_bundle
from .models import (
    EvidenceBundle,
    Outcome,
    TaskIdentity,
    TraceEvent,
    Unsupplied,
    UnsuppliedEvidence,
)


def unsupplied_rates() -> Any:
    return Unsupplied("rates")


def unsupplied_baseline() -> Any:
    return Unsupplied("baseline")


def unsupplied_policy() -> Any:
    return Unsupplied("policy")


def checks_only_bundle(
    *,
    events: Sequence[TraceEvent],
    outcomes: Mapping[str, Outcome],
    source_id: str,
    source_version: str = "1",
    task_manifest: Mapping[str, TaskIdentity] | None = None,
    dependency_edges: Sequence[tuple[str, str]] = (),
    declared_delegations: Sequence[str] = (),
    label_source: str = "",
) -> EvidenceBundle:
    """
    A bundle carrying evidence but no economics.

    Use it when your required coverage is supplied entirely by checks you wrote:
    a PII gate, a jailbreak gate, a regression eval. The rate card, baseline and
    policy are marked unsupplied rather than filled with defaults, so any
    economic gate you add later fails closed instead of quietly pricing your
    traffic at zero.
    """
    return make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=unsupplied_rates(),
        baseline=unsupplied_baseline(),
        policy=unsupplied_policy(),
        source_id=source_id,
        source_version=source_version,
        task_manifest=task_manifest,
        dependency_edges=dependency_edges,
        declared_delegations=declared_delegations,
        label_source=label_source,
    )


__all__ = [
    "Unsupplied",
    "UnsuppliedEvidence",
    "checks_only_bundle",
    "unsupplied_baseline",
    "unsupplied_policy",
    "unsupplied_rates",
]
