"""Checks resolvable by name, and the two gates nothing could reach.

`default_checks()` was a literal baked into four consumers. The consequence was
two verdict systems: an engine running six economic gates, and an audit
reimplementing delegation and provenance assessment beside it, because the
engine could not be configured to hold them. `gate.delegation-closure` and
`gate.evidence-provenance` shipped, were documented, and reached no CLI
decision and no verifiable claim.
"""

from __future__ import annotations

import pathlib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from agent_economics import load_normalized_json_bundle
from agent_economics.assurance import AssuranceEngine, decision_contract_digest
from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from agent_economics.cli import main
from agent_economics.delegation import DELEGATION_CLOSURE
from agent_economics.registry import UnknownCheck, default_registry

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code" / "bundle.json"


def _run(argv: list[str]) -> tuple[int, str]:
    out, err = StringIO(), StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue() + err.getvalue()


class TheRegistryHoldsEverythingThisBuildRuns(unittest.TestCase):
    def test_it_holds_the_two_gates_that_were_unreachable(self) -> None:
        registry = default_registry()
        self.assertIn("gate.delegation-closure", registry)
        self.assertIn("gate.evidence-provenance", registry)

    def test_every_default_check_is_registered(self) -> None:
        registry = default_registry()
        for spec in default_checks():
            with self.subTest(check=spec.id):
                self.assertIn(spec.id, registry)

    def test_an_unknown_id_is_refused_not_omitted(self) -> None:
        """A contract naming an unbuildable check is unreadable, not weaker."""
        with self.assertRaises(UnknownCheck):
            default_registry().build("gate.nope")

    def test_registering_a_duplicate_id_is_refused(self) -> None:
        from agent_economics.registry import CheckBuilder, CheckRegistry

        builder = CheckBuilder(
            id="x", version="1", build=lambda ctx: None, summary="",
        )
        registry = CheckRegistry([builder])
        with self.assertRaises(ValueError):
            registry.register(builder)


class FactoryGatesAreBuiltFromTheEvidence(unittest.TestCase):
    def test_the_delegation_manifest_comes_from_the_bundle(self) -> None:
        """A contract that let the caller supply it could declare every
        delegation accounted for without the evidence saying so.
        """
        bundle = load_normalized_json_bundle(EXAMPLE)
        spec = default_registry().build("gate.delegation-closure", bundle=bundle)
        self.assertEqual(
            tuple(spec.config["declared"]), tuple(sorted(bundle.declared_delegations))
        )

    def test_the_instrument_comes_from_the_bundle(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        spec = default_registry().build("gate.evidence-provenance", bundle=bundle)
        self.assertEqual(tuple(spec.config["instruments"]), (bundle.label_source,))

    def test_compose_preserves_order(self) -> None:
        """The contract digest binds order, so sorting here would silently
        make a claim unreproducible."""
        registry = default_registry()
        names = ["gate.tail-cost", "gate.acceptable-rate"]
        specs = registry.compose(names)
        self.assertEqual([s.id for s in specs], names)
        self.assertNotEqual(
            decision_contract_digest(specs, DEFAULT_REQUIRED_COVERAGE),
            decision_contract_digest(tuple(reversed(specs)), DEFAULT_REQUIRED_COVERAGE),
        )


class TheGatesNowReachADecision(unittest.TestCase):
    def test_delegation_closure_can_be_composed_into_a_contract(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        specs = default_registry().compose(
            [s.id for s in default_checks()] + ["gate.delegation-closure"],
            bundle=bundle,
        )
        case = AssuranceEngine(
            specs,
            required_coverage=frozenset(DEFAULT_REQUIRED_COVERAGE)
            | {DELEGATION_CLOSURE},
        ).evaluate(bundle)
        self.assertIn(
            "gate.delegation-closure", {r.check_id for r in case.check_results}
        )

    def test_the_cli_can_run_it(self) -> None:
        """No CLI path could reach this gate before."""
        code, text = _run([
            "evaluate", "--bundle", str(EXAMPLE),
            "--check", "gate.acceptable-rate",
            "--check", "gate.delegation-closure",
            "--require-coverage", "outcome_quality",
            "--require-coverage", "delegation_closure",
        ])
        self.assertIn(code, (0, 2, 3, 4), text)
        self.assertIn("gate.delegation-closure", text)

    def test_the_cli_refuses_an_unknown_check(self) -> None:
        code, text = _run(["evaluate", "--bundle", str(EXAMPLE), "--check", "gate.nope"])
        self.assertEqual(code, 2)
        self.assertIn("no check registered", text)

    def test_capabilities_lists_the_opt_in_gates(self) -> None:
        """It printed only the six, so the gates it advertises were invisible."""
        _code, text = _run(["capabilities"])
        self.assertIn("gate.delegation-closure@1", text)
        self.assertIn("gate.evidence-provenance@1", text)


if __name__ == "__main__":
    unittest.main()
