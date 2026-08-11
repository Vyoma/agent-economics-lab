"""Tests for the label-error propagation result.

Guards the four propositions and the documented scope. Deterministic, no network.
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_economics.label_error import (  # noqa: E402
    Workload,
    amplification,
    check_proposition_1,
    check_proposition_3,
    check_proposition_4,
    confusion,
    epsilon_star,
)


class PropositionTests(unittest.TestCase):
    def test_p1_ratio_identity_is_exact(self) -> None:
        self.assertLess(check_proposition_1(), 1e-12)

    def test_p3_difference_bound_holds(self) -> None:
        self.assertTrue(check_proposition_3())

    def test_p4_matches_integer_truth(self) -> None:
        # The residual is a float artefact of subtracting 1/n, not a real gap.
        self.assertLess(check_proposition_4(), 1e-12)

    def test_amplification_approaches_one_over_r(self) -> None:
        """As epsilon shrinks the exact factor converges to 1/r."""
        for r in (0.9, 0.5, 0.2):
            exact, predicted = amplification(r, 1e-6)
            self.assertAlmostEqual(exact / predicted, 1.0, places=4)
            self.assertAlmostEqual(predicted / 1e-6, 1 / r, places=6)

    def test_amplification_is_monotone_in_r(self) -> None:
        previous = 0.0
        for r in (0.9, 0.7, 0.5, 0.3, 0.1):
            exact, _ = amplification(r, 0.01)
            self.assertGreater(exact, previous)
            previous = exact

    def test_epsilon_star_bounds(self) -> None:
        self.assertEqual(epsilon_star(0.5, 0.0), 0.0)
        self.assertEqual(epsilon_star(0.5, -0.1), 0.0)
        for r in (0.1, 0.5, 1.0):
            for s in (0.01, 0.1, 1.0, 10.0):
                e = epsilon_star(r, s)
                self.assertGreater(e, 0.0)
                self.assertLess(e, r + 1e-12, "tolerance cannot exceed the rate")

    def test_confusion_counts(self) -> None:
        truth = (True, True, False, False)
        self.assertEqual(confusion(truth, (True, False, True, False)), (1, 1))
        self.assertEqual(confusion(truth, truth), (0, 0))

    def test_workload_unit_cost_is_infinite_with_no_successes(self) -> None:
        w = Workload((1.0, 1.0), (5.0, 5.0), (False, False))
        self.assertEqual(w.unit_cost(), math.inf)
        self.assertEqual(w.r, 0.0)

    def test_total_cost_is_label_independent(self) -> None:
        """The premise the whole analysis rests on."""
        costs = (1.0, 2.0, 3.0)
        base = Workload(costs, (9.0,) * 3, (True, True, False))
        flipped = Workload(costs, (9.0,) * 3, (False, False, True))
        self.assertEqual(base.C, flipped.C)


class DocumentedScopeTests(unittest.TestCase):
    """The published page must keep stating what the result does not claim.

    The result is conditional on a judge error rate it does not measure. A version
    of this page that dropped that caveat would be an overclaim, so the caveat is
    asserted rather than trusted.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.page = (ROOT / "docs/label-error.md").read_text(encoding="utf-8")

    def test_conditional_nature_is_disclosed(self) -> None:
        for caveat in ("does not measure any judge",
                       "not uniformly random",
                       "worst case",
                       "elementary"):
            with self.subTest(caveat=caveat):
                self.assertIn(caveat, self.page)

    def test_quoted_numbers_match_the_module(self) -> None:
        self.assertAlmostEqual(epsilon_star(0.70, 0.10), 0.0636, places=4)
        self.assertIn("93.6%", self.page)
        self.assertIn("6.36%", self.page)
        for r, shown in ((0.90, "5.9%"), (0.50, "11.1%"),
                         (0.20, "33.3%"), (0.10, "100.0%")):
            exact, _ = amplification(r, 0.05)
            with self.subTest(r=r):
                self.assertAlmostEqual(exact * 100, float(shown.rstrip("%")),
                                       places=1)
                self.assertIn(shown, self.page)

    def test_how_often_85_percent_suffices_depends_on_the_slack_grid(self) -> None:
        """The count is a property of the grid, so no single count may be quoted.

        An earlier version of this test asserted "exactly one of fifteen", which
        pinned a framing rather than testing a property: the one is an artifact
        of capping slack at 25%, while `check_proposition_4` sweeps slack to 1.0.
        Quoting it as a finding is the failure this project names elsewhere, a
        number that cannot come out differently because of how it was set up.
        """
        rates = (0.9, 0.7, 0.5, 0.3, 0.2)
        counts = {}
        for cap in (0.25, 0.50, 1.00):
            slacks = [s for s in (0.05, 0.10, 0.25, 0.50, 1.00) if s <= cap]
            cells = [(r, s) for r in rates for s in slacks]
            counts[cap] = (
                sum(1 for r, s in cells if epsilon_star(r, s) >= 0.15),
                len(cells),
            )
        self.assertEqual(counts[0.25], (1, 15))
        self.assertEqual(counts[0.50], (4, 20))
        self.assertEqual(counts[1.00], (8, 25))
        # Sufficiency is monotone in slack, which is why the cap drives the count.
        fractions = [c / n for c, n in counts.values()]
        self.assertEqual(fractions, sorted(fractions))

    def test_proposition_2_is_verified_not_merely_printed(self) -> None:
        """P2 was printed as a table with no PASS while P1, P3 and P4 were checked."""
        from agent_economics.label_error import check_proposition_2

        self.assertLess(check_proposition_2(), 1e-9)

    def test_net_bias_not_agreement_governs_the_distortion(self) -> None:
        """Balanced error cancels exactly, so agreement alone cannot decide safety."""
        n, a = 100, 70
        # 30% disagreement, perfectly balanced: the metric does not move at all.
        self.assertEqual(a / (a + (15 - 15)), 1.0)
        # 15% disagreement, one-directional: it moves a lot.
        self.assertGreater(abs(a / (a + 15) - 1), 0.17)
        self.assertGreater(abs(a / (a - 15) - 1), 0.27)
        # Agreement cuts both ways against the 85% rule of thumb. A judge at 93%
        # agreement whose error is one-directional carries 7% net bias, which
        # exceeds what a 70% / 10% gate tolerates, so it fails a gate that "85%
        # is sufficient" would have waved through.
        tolerance = epsilon_star(0.70, 0.10)
        one_directional = 7 / n
        self.assertGreater(1 - one_directional, 0.85, "that judge beats the norm")
        self.assertGreater(one_directional, tolerance, "yet it still fails the gate")

    def test_cli_answers_for_the_callers_own_numbers(self) -> None:
        """The docs tell readers to check their own r and s, so that must work."""
        import contextlib
        import io

        from agent_economics.label_error import main

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["-r", "0.62", "-s", "0.08"])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("4.59%", out)
        self.assertIn("95.41%", out)
        self.assertIn("net bias", out)
