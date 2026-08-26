"""
Regression locks for the frontier table published in README.md.

The absolute upper bounds, the cost lower bounds, `premium-12-step`'s
zero-count, and the 180 paired-task figure were previously guarded only by the
byte-comparison inside `make frontier`. That runs in CI, but it meant
`python -m unittest discover -s tests` passed with those published numbers
arbitrarily wrong.

Scope, stated honestly: these tests read the committed artifact, so they lock
the published file against edits. Drift originating upstream of the artifact is
still caught only by `make frontier`. See research/SELF_AUDIT.md.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTIER = ROOT / "research" / "results" / "frontier" / "frontier.json"


def _by_arm() -> dict[str, dict]:
    payload = json.loads(FRONTIER.read_text(encoding="utf-8"))
    return {c["candidate_arm"]: c for c in payload["comparisons"]}, payload


class PublishedFrontierTableTest(unittest.TestCase):
    """README.md renders these as 3.7% / 1-of-171 / 32.0% / eligible, etc."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.comparisons, cls.payload = _by_arm()

    def test_paired_task_count(self) -> None:
        """README calls this '180 synthetic task input digests'."""
        for arm in self.payload["arms"]:
            with self.subTest(arm=arm["arm_id"]):
                self.assertEqual(arm["paired_tasks"], 180)

    def test_balanced_four_step_is_the_only_eligible_arm(self) -> None:
        c = self.comparisons["balanced-4-step"]
        self.assertAlmostEqual(c["breakage_rate_upper"], 0.037431, places=6)
        self.assertEqual(c["harmful_regressions"], 1)
        self.assertEqual(c["reference_acceptable_tasks"], 171)
        self.assertAlmostEqual(c["cost_reduction_rate_lower"], 0.320092, places=6)
        self.assertTrue(c["eligible"])
        self.assertEqual(c["reasons"], [])

    def test_cheap_two_step_fails_on_quality(self) -> None:
        c = self.comparisons["cheap-2-step"]
        self.assertAlmostEqual(c["breakage_rate_upper"], 0.124773, places=6)
        self.assertEqual(c["harmful_regressions"], 12)
        self.assertAlmostEqual(c["cost_reduction_rate_lower"], 0.299269, places=6)
        self.assertFalse(c["eligible"])
        self.assertTrue(any("breakage upper bound" in r for r in c["reasons"]))

    def test_premium_twelve_step_fails_on_cost(self) -> None:
        """Cheapest breakage, but a negative cost-reduction bound. Not eligible."""
        c = self.comparisons["premium-12-step"]
        self.assertAlmostEqual(c["breakage_rate_upper"], 0.026247, places=6)
        self.assertEqual(c["harmful_regressions"], 0)
        self.assertAlmostEqual(c["cost_reduction_rate_lower"], -0.389442, places=6)
        self.assertFalse(c["eligible"])
        self.assertTrue(any("cost-reduction lower bound" in r for r in c["reasons"]))

    def test_zero_harmful_regressions_does_not_buy_eligibility(self) -> None:
        """The invariant the table exists to show: passing one gate is not passing."""
        c = self.comparisons["premium-12-step"]
        self.assertEqual(c["harmful_regressions"], 0)
        self.assertFalse(c["eligible"])

    def test_adopt_selects_balanced_four_step(self) -> None:
        self.assertEqual(self.payload["decision"], "ADOPT")
        self.assertEqual(self.payload["selected_arm"], "balanced-4-step")


if __name__ == "__main__":
    unittest.main()
