"""
Coverage closure over dynamic delegation.

The fixed-contract argument assumes the required evidence can be enumerated
before the run. That stops holding when the agent spawns subagents at runtime.
This module's claim is that a contract need not anticipate every delegation, but
must require that each one is accounted for, and that unaccounted delegation is
missing coverage in the ordinary sense.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from agent_economics import load_normalized_json_bundle
from agent_economics.assurance import AssuranceEngine
from agent_economics.delegation import (
    DELEGATION_CLOSURE,
    assess_bundle_closure,
    assess_closure,
    delegation_closure_gate,
)
from agent_economics.models import Decision, TraceEvent

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / "examples" / "claude-code-tree" / "bundle.json"
FLAT = ROOT / "examples" / "claude-code" / "bundle.json"


def _event(event_id: str, name: str, kind: str, cost: float = 0.0) -> TraceEvent:
    return TraceEvent(
        task_id="t",
        event_id=event_id,
        timestamp="2026-08-26T00:00:00Z",
        event_type=kind,
        name=name,
        model="m" if kind == "model" else "",
        direct_cost_usd=cost,
    )


class ShippedTreeFixtureTest(unittest.TestCase):
    """The real session-tree fixture contains exactly one delegation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_normalized_json_bundle(TREE)

    def test_one_delegation_is_found(self) -> None:
        report = assess_bundle_closure(self.bundle)
        self.assertEqual(report.total, 1)
        self.assertEqual(report.delegations[0].name, "Agent")

    def test_undeclared_delegation_is_unaccounted(self) -> None:
        report = assess_bundle_closure(self.bundle)
        self.assertEqual(len(report.unaccounted), 1)
        self.assertEqual(report.closure, 0.0)
        self.assertGreater(report.unaccounted_cost_usd, 0.0)

    def test_declaring_it_closes_the_contract(self) -> None:
        ids = tuple(d.event_id for d in assess_bundle_closure(self.bundle).delegations)
        report = assess_bundle_closure(self.bundle, declared=ids)
        self.assertEqual(report.unaccounted, ())
        self.assertEqual(report.closure, 1.0)

    def test_closure_varies_and_is_not_an_invariant(self) -> None:
        """Unlike the conformance line, this number moves with the evidence."""
        ids = tuple(d.event_id for d in assess_bundle_closure(self.bundle).delegations)
        self.assertNotEqual(
            assess_bundle_closure(self.bundle).closure,
            assess_bundle_closure(self.bundle, declared=ids).closure,
        )


class DetectionIsNameAuthoritativeTest(unittest.TestCase):
    """
    An earlier version inferred delegation from graph shape: a tool call with
    model-call children. That conflated sequencing with delegation and reported
    `Read` as a subagent, inflating the very number this module exists to report.
    """

    def test_a_tool_followed_by_model_work_is_not_a_delegation(self) -> None:
        events = [
            _event("read", "Read", "tool"),
            _event("m1", "call", "model", 1.0),
        ]
        report = assess_closure(events, [("read", "m1")])
        self.assertEqual(report.total, 0)

    def test_but_it_is_reported_as_suspected(self) -> None:
        """An adapter whose delegation tool is named otherwise must not read as closed."""
        events = [
            _event("read", "Read", "tool"),
            _event("m1", "call", "model", 1.0),
        ]
        report = assess_closure(events, [("read", "m1")])
        self.assertEqual(report.suspected_delegations, ("read",))

    def test_a_known_delegation_tool_is_counted(self) -> None:
        events = [
            _event("task", "Task", "tool"),
            _event("m1", "call", "model", 1.0),
        ]
        report = assess_closure(events, [("task", "m1")])
        self.assertEqual(report.total, 1)


class ClosureArithmeticTest(unittest.TestCase):
    def test_closure_is_weighted_by_cost_not_count(self) -> None:
        """One undeclared subagent burning the run matters more than five cheap ones."""
        events = [
            _event("big", "Task", "tool"),
            _event("big-child", "call", "model", 100.0),
            _event("small", "Task", "tool"),
            _event("small-child", "call", "model", 1.0),
        ]
        edges = [("big", "big-child"), ("small", "small-child")]
        declared_cheap = assess_closure(events, edges, declared=("small",))
        declared_costly = assess_closure(events, edges, declared=("big",))
        self.assertLess(declared_cheap.closure, 0.05)
        self.assertGreater(declared_costly.closure, 0.95)

    def test_a_run_with_no_delegation_is_fully_closed(self) -> None:
        report = assess_bundle_closure(load_normalized_json_bundle(FLAT))
        self.assertEqual(report.total, 0)
        self.assertEqual(report.closure, 1.0)

    def test_nested_delegation_reports_depth(self) -> None:
        events = [
            _event("outer", "Task", "tool"),
            _event("mid", "call", "model", 1.0),
            _event("inner", "Task", "tool"),
            _event("leaf", "call", "model", 1.0),
        ]
        edges = [("outer", "mid"), ("mid", "inner"), ("inner", "leaf")]
        report = assess_closure(events, edges)
        self.assertEqual(report.total, 2)
        self.assertEqual(report.max_depth, 2)

    def test_a_cycle_does_not_hang_the_walk(self) -> None:
        events = [
            _event("task", "Task", "tool"),
            _event("a", "call", "model", 1.0),
            _event("b", "call", "model", 1.0),
        ]
        report = assess_closure(events, [("task", "a"), ("a", "b"), ("b", "a")])
        self.assertEqual(report.total, 1)
        self.assertEqual(len(report.delegations[0].spawned_event_ids), 2)


class DelegationGateTest(unittest.TestCase):
    """Unaccounted delegation must be INCOMPLETE, not STOP and not a pass."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_normalized_json_bundle(TREE)
        cls.declared = tuple(
            d.event_id for d in assess_bundle_closure(cls.bundle).delegations
        )

    def _decide(self, declared) -> Decision:
        return AssuranceEngine(
            checks=(delegation_closure_gate(declared=declared),),
            required_coverage=frozenset({DELEGATION_CLOSURE}),
        ).evaluate(self.bundle).decision

    def test_undeclared_delegation_yields_incomplete(self) -> None:
        self.assertIs(self._decide(()), Decision.INCOMPLETE)

    def test_declared_delegation_permits_a_verdict(self) -> None:
        self.assertIsNot(self._decide(self.declared), Decision.INCOMPLETE)

    def test_it_is_not_reported_as_a_bad_outcome(self) -> None:
        """An unassessed subagent is not a failing one. STOP would be a lie."""
        self.assertIsNot(self._decide(()), Decision.STOP)


if __name__ == "__main__":
    unittest.main()
