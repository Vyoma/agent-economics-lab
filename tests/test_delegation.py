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

    def test_the_fixture_declares_its_delegation_in_the_contract(self) -> None:
        """Closure defaults to what the conversion contract actually signed off."""
        self.assertEqual(len(self.bundle.declared_delegations), 1)
        report = assess_bundle_closure(self.bundle)
        self.assertEqual(report.unaccounted, ())
        self.assertEqual(report.closure, 1.0)

    def test_withdrawing_the_declaration_leaves_it_unaccounted(self) -> None:
        report = assess_bundle_closure(self.bundle, declared=())
        self.assertEqual(len(report.unaccounted), 1)
        self.assertEqual(report.closure, 0.0)
        self.assertGreater(report.unaccounted_cost_usd, 0.0)

    def test_closure_varies_and_is_not_an_invariant(self) -> None:
        """Unlike the conformance line, this number moves with the evidence."""
        self.assertNotEqual(
            assess_bundle_closure(self.bundle, declared=()).closure,
            assess_bundle_closure(self.bundle).closure,
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
        cls.declared = tuple(cls.bundle.declared_delegations)

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


class ContractManifestTest(unittest.TestCase):
    """
    The declaration comes from the conversion contract, not a call-site argument.

    An adapter that silently converted a session containing undeclared subagents
    would put unassessed spend inside a bundle that then reads as complete, which
    is the failure this package exists to refuse. So the refusal happens at
    conversion, where the operator can still do something about it.
    """

    SESSION = ROOT / "examples" / "claude-code-tree" / "session.jsonl"
    CONTRACT = ROOT / "examples" / "claude-code-tree" / "conversion-contract.json"
    FLAT_SESSION = ROOT / "examples" / "claude-code" / "session.jsonl"
    FLAT_CONTRACT = ROOT / "examples" / "claude-code" / "conversion-contract.json"

    def _contract(self, path=None) -> dict:
        import json

        return json.loads((path or self.CONTRACT).read_text(encoding="utf-8"))

    def _convert(self, contract, session=None):
        from agent_economics.claude_code_tree import claude_code_tree_bundle

        return claude_code_tree_bundle(session or self.SESSION, contract)

    def test_the_shipped_contract_declares_its_delegation(self) -> None:
        bundle = self._convert(self._contract())
        self.assertEqual(len(bundle.declared_delegations), 1)
        self.assertEqual(assess_bundle_closure(bundle).closure, 1.0)

    def test_a_missing_delegation_block_is_refused(self) -> None:
        contract = self._contract()
        contract.pop("delegation")
        with self.assertRaises(ValueError) as ctx:
            self._convert(contract)
        self.assertIn("must carry a delegation block", str(ctx.exception))

    def test_an_undeclared_delegation_is_refused(self) -> None:
        contract = self._contract()
        contract["delegation"]["declared"] = []
        with self.assertRaises(ValueError) as ctx:
            self._convert(contract)
        self.assertIn("Undeclared delegation", str(ctx.exception))

    def test_declaring_a_call_the_run_never_made_is_refused(self) -> None:
        """A manifest is not a wish list."""
        contract = self._contract()
        contract["delegation"]["declared"].append("cc-tool-invented")
        with self.assertRaises(ValueError) as ctx:
            self._convert(contract)
        self.assertIn("did not make", str(ctx.exception))

    def test_approval_must_be_named(self) -> None:
        contract = self._contract()
        contract["delegation"]["approved_by"] = None
        with self.assertRaises(ValueError) as ctx:
            self._convert(contract)
        self.assertIn("approved_by", str(ctx.exception))

    def test_a_non_delegating_session_needs_no_block(self) -> None:
        """Every contract written before this existed stays valid."""
        from agent_economics.claude_code import claude_code_bundle

        contract = self._contract(self.FLAT_CONTRACT)
        self.assertNotIn("delegation", contract)
        bundle = claude_code_bundle(self.FLAT_SESSION, contract)
        self.assertEqual(bundle.declared_delegations, ())

    def test_a_non_delegating_session_may_not_claim_one(self) -> None:
        from agent_economics.claude_code import claude_code_bundle

        contract = self._contract(self.FLAT_CONTRACT)
        contract["delegation"] = {"approved_by": "x", "declared": ["cc-tool-invented"]}
        with self.assertRaises(ValueError) as ctx:
            claude_code_bundle(self.FLAT_SESSION, contract)
        self.assertIn("did not make", str(ctx.exception))

    def test_the_template_prefills_what_the_run_delegated(self) -> None:
        """The adapter supplies what it can read; the operator supplies approval."""
        from agent_economics.claude_code import conversion_contract_template
        from agent_economics.claude_code_tree import inspect_claude_code_session_tree

        template = conversion_contract_template(
            inspect_claude_code_session_tree(self.SESSION)
        )
        self.assertIsNone(template["delegation"]["approved_by"])
        self.assertEqual(len(template["delegation"]["declared"]), 1)

    def test_a_non_delegating_template_has_no_delegation_key(self) -> None:
        """Emitting a null key would change every non-delegating template."""
        from agent_economics.claude_code import (
            conversion_contract_template,
            inspect_claude_code_jsonl,
        )

        template = conversion_contract_template(
            inspect_claude_code_jsonl(self.FLAT_SESSION)
        )
        self.assertNotIn("delegation", template)
