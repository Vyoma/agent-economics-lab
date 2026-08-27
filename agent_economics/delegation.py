"""
Coverage closure over dynamic delegation.

The fixed-contract argument this package makes has a hole, and it is a hole the
argument itself creates.

A pinned contract assumes you can enumerate the required evidence before the run.
That holds for an agent that calls a model in a loop. It stops holding the moment
the agent spawns subagents at runtime, because the shape of what it did is not
known until it has done it. A subagent can call tools nobody wrote a gate for, on
data nobody declared, and its cost rolls up into the parent's totals as if it were
ordinary compute.

Taken at face value, the package's own logic says such a run is unassessable:
evidence exists that no gate covers, so `INCOMPLETE` is the only honest verdict.
Taken naively that makes every dynamic agent permanently incomplete, which is
useless and is why nobody enforces it.

The resolution is a closure property rather than an enumeration. A contract does
not have to anticipate every delegation. It has to require that every delegation
is *accounted for*: either the delegating call was declared in the conversion
contract, or the delegated work carries a contract of its own. Delegation that
satisfies neither is unaccounted, and unaccounted delegation is missing coverage
in the ordinary sense this package already means it.

What that buys, concretely, is a number that today nothing reports:

    closure = accounted delegated compute / total delegated compute

It is not an invariant. It varies with the run, it degrades as an agent becomes
more dynamic, and it is a property of the contract measured against what the agent
actually did, which is the direction of measurement this package otherwise lacks.

Prior art, stated rather than skipped: modular and compositional assurance cases
have long allowed one argument to discharge obligations onto another, and
contract-based design formalises exactly this in systems engineering. What appears
to be absent is any of it applied to structure discovered at runtime, in an agent
delegation tree, as a shipped check. See docs/landscape.md.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .models import (
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Decision,
    EvidenceBundle,
    TraceEvent,
)

# The coverage dimension this module supplies. A plain string rather than a
# Coverage member: it is not economic, and the engine accepts either.
DELEGATION_CLOSURE = "delegation_closure"


class UnaccountedDelegation(LookupError):
    """
    Raised when a run delegated work no contract undertook to assess.

    Deliberately an exception rather than a FAIL result. The engine requires a
    failing gate to route to ASSIST or STOP, and neither is right here: an
    undeclared subagent has not produced a bad outcome, it has produced an
    outcome nobody agreed to evaluate. That is missing coverage, and the engine
    already answers missing coverage with INCOMPLETE. A check that raises is a
    check declaring it cannot assess this run, which is exactly the claim.
    """


@dataclass(frozen=True)
class Delegation:
    """One call that spawned further agent work."""

    event_id: str
    task_id: str
    name: str
    depth: int
    spawned_event_ids: tuple[str, ...]
    spawned_cost_usd: float
    declared: bool

    @property
    def accounted(self) -> bool:
        return self.declared


@dataclass(frozen=True)
class ClosureReport:
    delegations: tuple[Delegation, ...] = ()
    total_events: int = 0
    declared_manifest: tuple[str, ...] = field(default_factory=tuple)
    suspected_delegations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return len(self.delegations)

    @property
    def unaccounted(self) -> tuple[Delegation, ...]:
        return tuple(d for d in self.delegations if not d.accounted)

    @property
    def delegated_cost_usd(self) -> float:
        return sum(d.spawned_cost_usd for d in self.delegations)

    @property
    def unaccounted_cost_usd(self) -> float:
        return sum(d.spawned_cost_usd for d in self.unaccounted)

    @property
    def closure(self) -> float:
        """
        Accounted share of delegated compute, by cost.

        Cost rather than count, because one undeclared subagent that burns most of
        the run matters more than five that return immediately. Undefined when
        nothing was delegated, which is reported as fully closed: an agent that
        never delegated has no delegation to account for.
        """
        total = self.delegated_cost_usd
        if total <= 0:
            return 1.0 if not self.unaccounted else 0.0
        return (total - self.unaccounted_cost_usd) / total

    @property
    def max_depth(self) -> int:
        return max((d.depth for d in self.delegations), default=0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "closure": self.closure,
            "delegations": self.total,
            "unaccounted": len(self.unaccounted),
            "max_depth": self.max_depth,
            "delegated_cost_usd": self.delegated_cost_usd,
            "unaccounted_cost_usd": self.unaccounted_cost_usd,
            "declared_manifest": list(self.declared_manifest),
            "suspected_delegations": list(self.suspected_delegations),
            "detail": [
                {
                    "event_id": d.event_id,
                    "task_id": d.task_id,
                    "name": d.name,
                    "depth": d.depth,
                    "spawned": list(d.spawned_event_ids),
                    "spawned_cost_usd": d.spawned_cost_usd,
                    "declared": d.declared,
                }
                for d in self.delegations
            ],
        }


def _children(edges: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for parent, child in edges:
        out[parent].append(child)
    return out


def _descendants(root: str, children: Mapping[str, list[str]]) -> tuple[str, ...]:
    """Every event reachable from `root`. Cycle-safe: a visited node is not re-entered."""
    seen: set[str] = set()
    stack = list(children.get(root, ()))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(children.get(node, ()))
    return tuple(sorted(seen))


def _depths(edges: Sequence[tuple[str, str]], roots: Sequence[str]) -> dict[str, int]:
    children = _children(edges)
    depth = {r: 0 for r in roots}
    stack = [(r, 0) for r in roots]
    while stack:
        node, d = stack.pop()
        for child in children.get(node, ()):
            if child not in depth or depth[child] > d + 1:
                depth[child] = d + 1
                stack.append((child, d + 1))
    return depth


def assess_closure(
    events: Sequence[TraceEvent],
    dependency_edges: Sequence[tuple[str, str]],
    *,
    delegation_tools: Sequence[str] = ("Task", "Agent"),
    declared: Sequence[str] = (),
) -> ClosureReport:
    """
    Walk the delegation graph and report how much of it the contract accounts for.

    `declared` is the manifest of delegating event IDs the conversion contract
    anticipated. A delegation absent from it spawned work nobody planned to
    assess, whatever that work then cost.
    """
    by_id: dict[str, TraceEvent] = {e.event_id: e for e in events}
    children = _children(dependency_edges)
    has_parent = {child for _, child in dependency_edges}
    roots = [e.event_id for e in events if e.event_id not in has_parent]
    depth = _depths(dependency_edges, roots)
    declared_set = set(declared)

    delegations: list[Delegation] = []
    for event in events:
        spawns = children.get(event.event_id, ())
        # Delegation is identified by the tool that performs it, matching the
        # adapter's own DELEGATION_TOOLS. An earlier version inferred it from
        # graph shape -- a tool call with model-call children -- which conflated
        # ordinary sequencing with delegation and reported `Read` as a subagent.
        # Over-counting here would inflate the very number this module exists to
        # report, so the structural signal is surfaced separately, as a suspicion,
        # never as closure.
        if event.name not in delegation_tools or not spawns:
            continue
        reachable = _descendants(event.event_id, children)
        cost = sum(
            by_id[e].direct_cost_usd or 0.0 for e in reachable if e in by_id
        )
        delegations.append(
            Delegation(
                event_id=event.event_id,
                task_id=event.task_id,
                name=event.name,
                depth=depth.get(event.event_id, 0),
                spawned_event_ids=reachable,
                spawned_cost_usd=cost,
                declared=event.event_id in declared_set,
            )
        )

    # Tool calls that were followed by model work but are not known delegation
    # tools. Not counted as delegation, because they are probably sequencing.
    # Reported so that an adapter for a framework whose delegation tool is named
    # something else does not silently read as fully closed.
    known = {d.event_id for d in delegations}
    suspected = tuple(
        sorted(
            event.event_id
            for event in events
            if event.event_id not in known
            and event.event_type == "tool"
            and any(
                by_id[c].event_type == "model"
                for c in children.get(event.event_id, ())
                if c in by_id
            )
        )
    )

    return ClosureReport(
        delegations=tuple(sorted(delegations, key=lambda d: d.event_id)),
        total_events=len(events),
        declared_manifest=tuple(sorted(declared_set)),
        suspected_delegations=suspected,
    )


def delegation_closure_gate(
    *,
    declared: Sequence[str] = (),
    delegation_tools: Sequence[str] = ("Task", "Agent"),
    minimum_closure: float = 1.0,
) -> CheckSpec:
    """
    A gate requiring that delegated work is accounted for.

    Yields INCOMPLETE, not STOP, when delegation is unaccounted. An undeclared
    subagent has not produced a bad result; it has produced a result nobody
    undertook to assess, and those are different verdicts.
    """

    def run(view) -> CheckOutput:
        report = assess_closure(
            view.events,
            view.dependency_edges,
            delegation_tools=delegation_tools,
            declared=declared,
        )
        if report.closure < minimum_closure:
            names = ", ".join(sorted({d.name for d in report.unaccounted}))
            raise UnaccountedDelegation(
                f"{len(report.unaccounted)} of {report.total} delegation(s) "
                f"undeclared ({names}); "
                f"${report.unaccounted_cost_usd:.4f} of "
                f"${report.delegated_cost_usd:.4f} delegated spend was never "
                f"undertaken for assessment; closure {report.closure:.1%} "
                f"below the required {minimum_closure:.1%}"
            )
        message = (
            "no delegation in this run"
            if report.total == 0
            else (
                f"{report.total} delegation(s) accounted for, "
                f"depth {report.max_depth}, "
                f"${report.delegated_cost_usd:.4f} delegated"
            )
        )
        if report.suspected_delegations:
            message += (
                f"; {len(report.suspected_delegations)} tool call(s) spawned model "
                "work but are not known delegation tools"
            )
        return CheckOutput(
            results=(
                CheckResult(
                    check_id="gate.delegation-closure",
                    status=CheckStatus.PASS,
                    message=message,
                ),
            )
        )

    return CheckSpec(
        id="gate.delegation-closure",
        version="1",
        mode=CheckMode.GATE,
        covers=frozenset({DELEGATION_CLOSURE}),
        run=run,
        failure_route=Decision.STOP,
    )


def assess_bundle_closure(
    bundle: EvidenceBundle,
    *,
    delegation_tools: Sequence[str] = ("Task", "Agent"),
    declared: Sequence[str] | None = None,
) -> ClosureReport:
    """
    Closure for a whole evidence bundle.

    Defaults to the bundle's own `declared_delegations`, which the adapters
    populate from the conversion contract, so closure reflects what the operator
    actually signed off rather than a parameter supplied at the call site. Pass
    `declared` explicitly to ask a what-if.
    """
    return assess_closure(
        bundle.events,
        bundle.dependency_edges,
        delegation_tools=delegation_tools,
        declared=bundle.declared_delegations if declared is None else declared,
    )


__all__ = [
    "DELEGATION_CLOSURE",
    "ClosureReport",
    "Delegation",
    "UnaccountedDelegation",
    "assess_bundle_closure",
    "assess_closure",
    "delegation_closure_gate",
]
