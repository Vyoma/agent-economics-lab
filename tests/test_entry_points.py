"""The gate and the engine must not be confusable.

`decide` evaluates and audits as one act; `evaluate_bundle` is the engine
alone. Both are legitimate and they answer differently, which is the whole
point: the gate refuses a green the auditor has grounds against.

That difference was a trap for a while. `decide` was not in `__all__`, so a
library consumer reaching for the obvious name got the engine, and on a
bundle shipped in this repository the engine returns SCALE where the gate
returns INCOMPLETE. The package's own argument is that the reassuring
answer must not be the default one, and its public surface had it exactly
that way round. These pin the contract so the trap cannot be reset.
"""

from __future__ import annotations

import glob
import pathlib
import unittest

import agent_economics as ae
from agent_economics.audit import decide

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLES = sorted(glob.glob(str(ROOT / "examples" / "**" / "bundle*.json"),
                          recursive=True))


class BothEntryPointsAreReachable(unittest.TestCase):
    def test_the_gate_is_exported(self) -> None:
        """The unexported one was the fail-closed one."""
        for name in ("decide", "audit", "AuditReport", "evaluate_bundle"):
            with self.subTest(name=name):
                self.assertIn(name, ae.__all__)

    def test_there_are_bundles_to_check(self) -> None:
        self.assertTrue(BUNDLES, "no shipped bundles found to compare")


class TheGateIsNeverMoreGenerousThanTheEngine(unittest.TestCase):
    """A gate that can turn a refusal into a green is not a gate."""

    ORDER = {"SCALE": 0, "ASSIST": 1, "STOP": 1, "INCOMPLETE": 2}

    def test_decide_only_ever_withholds(self) -> None:
        for path in BUNDLES:
            bundle = ae.load_normalized_json_bundle(path)
            engine = ae.evaluate_bundle(bundle).decision.value
            case, _ = decide(bundle)
            gate = case.decision.value
            with self.subTest(bundle=pathlib.Path(path).parent.name):
                self.assertGreaterEqual(
                    self.ORDER[gate], self.ORDER[engine],
                    f"{path}: gate {gate} is more generous than engine {engine}",
                )

    def test_a_green_the_auditor_refuses_is_withheld(self) -> None:
        """Non-vacuity: at least one shipped bundle actually diverges, so
        this file is testing a live difference and not an empty set."""
        divergent = []
        for path in BUNDLES:
            bundle = ae.load_normalized_json_bundle(path)
            engine = ae.evaluate_bundle(bundle).decision.value
            case, report = decide(bundle)
            if case.decision.value != engine:
                divergent.append((path, engine, case.decision.value, report))
        self.assertTrue(
            divergent,
            "no shipped bundle separates the engine from the gate; if the "
            "examples changed, add one that does rather than deleting this",
        )
        for path, engine, gate, report in divergent:
            with self.subTest(bundle=pathlib.Path(path).parent.name):
                self.assertEqual(engine, "SCALE")
                self.assertEqual(gate, "INCOMPLETE")
                self.assertTrue(
                    report.grounds,
                    "withheld with no grounds recorded",
                )


if __name__ == "__main__":
    unittest.main()


class EverySubcommandIsRoutable(unittest.TestCase):
    """`main` used to be a 439-line chain of `if args.command == ...`, where
    a subparser with no matching branch fell to the bottom and returned 2,
    indistinguishable from a real refusal. The chain is a table now, and a
    command in the parser with no entry in it is caught here rather than at
    the exit code."""

    def test_the_table_covers_the_parser(self) -> None:
        import argparse as _argparse

        from agent_economics.cli import DISPATCH, build_parser

        parser = build_parser()
        subparsers = [
            action for action in parser._actions
            if isinstance(action, _argparse._SubParsersAction)
        ]
        self.assertEqual(len(subparsers), 1, "expected one subparser group")
        declared = set(subparsers[0].choices)
        routed = set(DISPATCH)
        self.assertEqual(
            declared - routed, set(),
            "subcommands the parser accepts but the table cannot route",
        )
        self.assertEqual(
            routed - declared, set(),
            "table entries for subcommands the parser does not accept",
        )

    def test_every_handler_is_callable(self) -> None:
        from agent_economics.cli import DISPATCH

        for name, handler in DISPATCH.items():
            with self.subTest(command=name):
                self.assertTrue(callable(handler))
