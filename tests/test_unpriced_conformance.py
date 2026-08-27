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
import unittest

from agent_economics.adapters import (
    normalized_json_bundle,
    render_normalized_json,
)
from agent_economics.audit import audit, render_markdown
from agent_economics.models import Outcome, TraceEvent, Unsupplied, UnsuppliedEvidence
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
