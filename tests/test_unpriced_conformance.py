"""What the package must refuse to state when evidence was never supplied.

Two conformance sweeps and one regression. The regression is the eighth
instance of the pattern this repo catalogues, and it was found in this
package's own API: `checks_only_bundle` refuses to fabricate a rate card and
then the audit renderer printed "$0.0000 of delegated spend" from event costs
that nothing had priced. The verdict was correct throughout. The number
reaching the reader was invented at the rendering boundary.
"""

from __future__ import annotations

import json
import math
import pathlib
import unittest
from dataclasses import replace
from typing import ClassVar

from agent_economics import load_normalized_json_bundle
from agent_economics.adapters import (
    normalized_json_bundle,
    render_normalized_json,
)
from agent_economics.audit import audit, render_markdown
from agent_economics.delegation import assess_bundle_closure
from agent_economics.evidence import make_evidence_bundle
from agent_economics.models import (
    ModelRate,
    Outcome,
    TraceEvent,
    Unsupplied,
    UnsuppliedEvidence,
)
from agent_economics.unsupplied import (
    checks_only_bundle,
    unsupplied_baseline,
    unsupplied_policy,
    unsupplied_rates,
)


def _event(index: int, name: str, kind: str = "model", cost: float = 0.0) -> TraceEvent:
    return TraceEvent(
        task_id="t0", event_id=f"e{index}", timestamp=f"2026-08-27T00:00:{index:02d}Z",
        event_type=kind, name=name, model="m", direct_cost_usd=cost,
    )


def _bundle(**kwargs):
    return checks_only_bundle(
        events=(_event(0, "chat"), _event(1, "Agent", "tool"), _event(2, "chat")),
        outcomes={"t0": Outcome(task_id="t0", acceptable=True)},
        source_id="s.x", **kwargs,
    )


class UnsuppliedRefusesEveryRead(unittest.TestCase):
    """Every probed operation must raise, not coerce.

    `_UnsuppliedMetric` is deliberately not a float subclass. An earlier
    version was, and it leaked: `math.fsum` returned nan, `nan > 100` is
    False, and a gate passed on $3000 of real spend.
    """

    def _subjects(self):
        return {
            "rates": unsupplied_rates(),
            "baseline": unsupplied_baseline(),
            "policy": unsupplied_policy(),
        }

    def test_every_unsupplied_is_marked_as_such(self) -> None:
        for name, value in self._subjects().items():
            with self.subTest(subject=name):
                self.assertIsInstance(value, Unsupplied)

    def test_no_arithmetic_path_coerces_an_unsupplied_value(self) -> None:
        operations = {
            "float": lambda v: float(v),
            "int": lambda v: int(v),
            "abs": lambda v: abs(v),
            "round": lambda v: round(v),
            "add": lambda v: v + 1,
            "radd": lambda v: 1 + v,
            "sub": lambda v: v - 1,
            "mul": lambda v: v * 2,
            "truediv": lambda v: v / 2,
            "floordiv": lambda v: v // 2,
            "mod": lambda v: v % 2,
            "pow": lambda v: v**2,
            "neg": lambda v: -v,
            "gt": lambda v: v > 100,
            "lt": lambda v: v < 100,
            "fsum": lambda v: math.fsum([v]),
            "sum": lambda v: sum([v]),
            "format": lambda v: f"{v:.4f}",
            "iter": lambda v: list(iter(v)),
            "getitem": lambda v: v["anything"],
        }
        for name, value in self._subjects().items():
            for op_name, op in operations.items():
                with (
                    self.subTest(subject=name, operation=op_name),
                    self.assertRaises((UnsuppliedEvidence, TypeError, ValueError)),
                ):
                    op(value)


class DeclaredAbsenceSurvivesTheWire(unittest.TestCase):
    """The checks-only path is documented, so it must reach the file audit reads.

    Before this, a checks-only bundle could be built and audited in memory but
    `render_normalized_json` raised `UnsuppliedEvidence`, so `audit --bundle`
    could never load one. The barrier was the interchange format, not the CLI.
    """

    def test_a_checks_only_bundle_round_trips_without_acquiring_economics(self) -> None:
        original = _bundle()
        document = json.loads(render_normalized_json(original))
        for field in ("rates", "baseline", "policy"):
            with self.subTest(field=field):
                self.assertEqual(document[field], {"unsupplied": field})
        restored = normalized_json_bundle(document)
        self.assertEqual(restored.digest, original.digest)
        for field in ("rates", "baseline", "policy"):
            with self.subTest(field=field):
                self.assertIsInstance(getattr(restored, field), Unsupplied)


class UnpricedSpendIsNotStated(unittest.TestCase):
    def test_an_unpriced_trace_does_not_report_a_dollar_figure(self) -> None:
        text = render_markdown(audit(_bundle(dependency_edges=(("e1", "e2"),))))
        self.assertNotIn("$", text)
        self.assertIn("never priced", text)

    def test_the_json_reports_null_rather_than_a_fabricated_zero(self) -> None:
        report = audit(_bundle(dependency_edges=(("e1", "e2"),))).to_dict()
        self.assertIsNone(report["delegated_spend_unassessed"])
        self.assertFalse(report["spend_is_priced"])

    def test_an_unpriced_trace_still_fails_closed_on_closure(self) -> None:
        report = audit(_bundle(dependency_edges=(("e1", "e2"),)))
        self.assertEqual(report.closure, 0.0)
        self.assertFalse(report.assessable)


if __name__ == "__main__":
    unittest.main()


class RatePricedDelegationIsNotFree(unittest.TestCase):
    """Cost-weighted closure must price events the same way the rest of the package does.

    `assess_closure` read `direct_cost_usd or 0.0` instead of `TraceEvent.cost`,
    so any event priced by the rate card rather than an explicit figure weighed
    nothing. Every adapter-built bundle sets an explicit cost, which is why this
    survived. The documented CSV evidence path leaves the column blank and
    prices from the rate card, and there it reported 100% closure and $0.00
    unaccounted over $18.00 of undeclared subagent spend.
    """

    RATES: ClassVar[dict[str, ModelRate]] = {
        "m": ModelRate(input_per_million_usd=3.0, output_per_million_usd=15.0)
    }

    def _event(self, index, name, kind="model", direct=None, tin=0, tout=0):
        return TraceEvent(
            task_id="t0", event_id=f"e{index}",
            timestamp=f"2026-08-27T00:00:{index:02d}Z",
            event_type=kind, name=name, model="m", direct_cost_usd=direct,
            input_tokens=tin, output_tokens=tout,
        )

    def _mixed_bundle(self):
        """$100 of declared subagent spend, $18 of undeclared, priced two ways."""
        events = (
            self._event(0, "chat", direct=0.0),
            self._event(1, "Agent", "tool", direct=0.0),
            self._event(2, "chat", direct=100.0),
            self._event(3, "Agent", "tool", direct=0.0),
            self._event(4, "chat", tin=1_000_000, tout=1_000_000),
        )
        reference = load_normalized_json_bundle(
            pathlib.Path(__file__).resolve().parents[1]
            / "examples" / "claude-code" / "bundle.json"
        )
        return make_evidence_bundle(
            events=events, outcomes={"t0": Outcome(task_id="t0", acceptable=True)},
            rates=self.RATES, baseline=reference.baseline, policy=reference.policy,
            source_id="s.x", dependency_edges=(("e1", "e2"), ("e3", "e4")),
            declared_delegations=("e1",),
        )

    def test_undeclared_rate_priced_spend_is_not_counted_as_zero(self) -> None:
        report = assess_bundle_closure(self._mixed_bundle())
        undeclared = next(d for d in report.delegations if not d.declared)
        self.assertAlmostEqual(undeclared.spawned_cost_usd, 18.0)
        self.assertAlmostEqual(report.unaccounted_cost_usd, 18.0)
        self.assertLess(report.closure, 1.0)

    def test_the_two_ways_of_stating_the_same_cost_agree(self) -> None:
        explicit = self._event(9, "chat", direct=18.0)
        rate_priced = self._event(9, "chat", tin=1_000_000, tout=1_000_000)
        self.assertEqual(explicit.cost(self.RATES), rate_priced.cost(self.RATES))

    def test_delegated_work_nothing_priced_withholds_rather_than_raising(self) -> None:
        bundle = _bundle(dependency_edges=(("e1", "e2"),))
        unpriced = replace(
            bundle,
            events=(
                bundle.events[0], bundle.events[1],
                self._event(2, "chat", tin=1_000_000, tout=1_000_000),
            ),
        )
        report = audit(unpriced)
        self.assertEqual(report.decision, "INCOMPLETE")
        self.assertIn("delegated work nothing priced", report.grounds)


class ChecksOnlyExampleIsReachable(unittest.TestCase):
    """The documented checks-only path, exercised through the file audit reads.

    This example exists because the path was documented and unreachable: the
    bundle could be built in memory and never written to disk, so no user could
    follow the README. It carries real token counts and states no cost, because
    nothing priced those calls.
    """

    EXAMPLE: ClassVar[pathlib.Path] = (
        pathlib.Path(__file__).resolve().parents[1]
        / "examples" / "checks-only" / "bundle.json"
    )

    def test_the_committed_example_loads_and_stays_unpriced(self) -> None:
        bundle = load_normalized_json_bundle(self.EXAMPLE)
        for field in ("rates", "baseline", "policy"):
            with self.subTest(field=field):
                self.assertIsInstance(getattr(bundle, field), Unsupplied)

    def test_it_states_no_cost_rather_than_a_fabricated_zero(self) -> None:
        document = json.loads(self.EXAMPLE.read_text(encoding="utf-8"))
        for event in document["events"]:
            with self.subTest(event=event["event_id"]):
                self.assertIsNone(event["direct_cost_usd"])
                self.assertGreater(event["input_tokens"], 0)

    def test_auditing_it_withholds_a_verdict(self) -> None:
        report = audit(load_normalized_json_bundle(self.EXAMPLE))
        self.assertEqual(report.decision, "INCOMPLETE")
        self.assertFalse(report.assessable)


class VacuousClosureIsNotReportedAsFullMarks(unittest.TestCase):
    def test_a_run_with_no_delegation_says_so(self) -> None:
        text = render_markdown(audit(_bundle()))
        self.assertIn("delegated no work", text)
        self.assertNotIn("closure 100%", text)
