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

    def test_eighty_five_percent_suffices_in_exactly_one_cell(self) -> None:
        """The page's central comparison, asserted rather than asserted-in-prose."""
        cells = [(r, s) for r in (0.9, 0.7, 0.5, 0.3, 0.2)
                 for s in (0.05, 0.10, 0.25)]
        sufficient = [(r, s) for r, s in cells if epsilon_star(r, s) >= 0.15]
        self.assertEqual(len(cells), 15)
        self.assertEqual(len(sufficient), 1)
        self.assertEqual(sufficient[0], (0.9, 0.25))
        self.assertIn("suffices in", self.page)
