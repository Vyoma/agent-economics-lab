"""What a gate enforces must be in the contract digest, not only in its source.

`implementation_digest` hashes `inspect.getsource(run)`, which is right for a
plain function and blind for a closure. The two most consequential gates shipped
here are factories whose entire enforcement lives in captured arguments, so a
gate built to be unfailable produced a contract digest byte-identical to the
strict one -- the failure this package calls harder than a missing gate,
arriving through closure arguments rather than through the gate list.

Also here: closure totals are unions over delegated events. Summing
per-delegation subtrees counted nested spend once per enclosing link, so twenty
declared links around one undeclared delegation diluted it to 95% closure and
passed a 0.95 gate while none of the real spend was assessed.
"""

from __future__ import annotations

import datetime as dt
import unittest
from types import SimpleNamespace

from agent_economics.assurance import decision_contract_digest, default_checks
from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE
from agent_economics.delegation import (
    UnaccountedDelegation,
    assess_bundle_closure,
    delegation_closure_gate,
)
from agent_economics.models import Outcome, TraceEvent
from agent_economics.provenance import ProvenancePolicy, evidence_provenance_gate
from agent_economics.unsupplied import checks_only_bundle

COVERAGE = frozenset(DEFAULT_REQUIRED_COVERAGE)


def _event(index: int, name: str, kind: str = "tool", cost: float = 0.0):
    return TraceEvent(
        task_id="t0", event_id=f"e{index}",
        timestamp=f"2026-08-27T00:00:{index % 60:02d}Z",
        event_type=kind, name=name, model="m", direct_cost_usd=cost,
    )


class ConfigurationIsBoundIntoTheContract(unittest.TestCase):
    def test_an_unfailable_closure_gate_has_a_different_contract(self) -> None:
        strict = delegation_closure_gate(declared=(), minimum_closure=1.0)
        unfailable = delegation_closure_gate(
            declared=("e1", "e2"), minimum_closure=0.0, delegation_tools=()
        )
        self.assertEqual(
            strict.implementation_digest, unfailable.implementation_digest,
            "same source: this is exactly why source alone is not enough",
        )
        self.assertNotEqual(
            decision_contract_digest((strict,), COVERAGE),
            decision_contract_digest((unfailable,), COVERAGE),
        )

    def test_an_unfailable_provenance_gate_has_a_different_contract(self) -> None:
        as_of = dt.date(2026, 8, 27)
        strict = evidence_provenance_gate(
            instruments=("i",), attestations={}, as_of=as_of
        )
        unfailable = evidence_provenance_gate(
            instruments=("i",), attestations={}, as_of=as_of,
            policy=ProvenancePolicy(
                min_agreement=0.0, min_sample_size=0, max_age_days=10**6
            ),
        )
        self.assertNotEqual(
            decision_contract_digest((strict,), COVERAGE),
            decision_contract_digest((unfailable,), COVERAGE),
        )

    def test_the_shipped_contract_digest_is_unchanged(self) -> None:
        """Config is omitted when empty, so the six default checks do not move.

        The digest is published in several artifacts; binding configuration
        must not silently invalidate them.
        """
        digest = decision_contract_digest(
            tuple(default_checks()), DEFAULT_REQUIRED_COVERAGE
        )
        self.assertTrue(digest.startswith("e7faae0cb2b0fb62"), digest)

    def test_a_check_without_configuration_omits_the_key(self) -> None:
        from agent_economics.assurance import decision_contract_manifest

        manifest = decision_contract_manifest(
            tuple(default_checks()), DEFAULT_REQUIRED_COVERAGE
        )
        for entry in manifest["checks"]:
            with self.subTest(check=entry["manifest_id"]):
                self.assertNotIn("config", entry)


class ClosureTotalsAreUnionsNotSums(unittest.TestCase):
    def _nested(self, depth: int, declared: bool):
        events = [_event(0, "chat", "model", 0.0)]
        edges, ids = [], []
        for i in range(1, depth + 1):
            events.append(_event(i, "Agent"))
            ids.append(f"e{i}")
            if i > 1:
                edges.append((f"e{i - 1}", f"e{i}"))
        events.append(_event(50, "Agent"))
        edges.append((f"e{depth}", "e50"))
        events.append(_event(51, "chat", "model", 500.0))
        edges.append(("e50", "e51"))
        return checks_only_bundle(
            events=tuple(events),
            outcomes={"t0": Outcome(task_id="t0", acceptable=True)},
            source_id="s.x", dependency_edges=tuple(edges),
            declared_delegations=tuple(ids) if declared else (),
        )

    def test_nesting_does_not_multiply_the_delegated_total(self) -> None:
        report = assess_bundle_closure(self._nested(3, declared=False))
        self.assertAlmostEqual(report.delegated_cost_usd, 500.0)

    def test_declared_links_cannot_dilute_an_undeclared_delegation(self) -> None:
        """Twenty declared links around one undeclared call used to read 95%."""
        bundle = self._nested(20, declared=True)
        report = assess_bundle_closure(bundle)
        self.assertAlmostEqual(report.unaccounted_cost_usd, 500.0)
        self.assertEqual(report.closure, 0.0)

        view = SimpleNamespace(
            events=bundle.events, dependency_edges=bundle.dependency_edges,
            rates=bundle.rates,
        )
        with self.assertRaises(UnaccountedDelegation):
            delegation_closure_gate(
                declared=bundle.declared_delegations, minimum_closure=0.95
            ).run(view)


if __name__ == "__main__":
    unittest.main()
