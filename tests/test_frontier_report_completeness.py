"""The frontier renderers must not lose an arm, a refusal, or a caveat.

All three frontier renderers were byte-compared against checked-in fixtures
and nothing more. A fixture diff proves the output has not changed; it
cannot tell you that an arm the case ruled on is missing from the page, and
a renderer that dropped one would match its fixture forever.

These hold the property that matters for a comparison report: a reader is
shown every arm the case decided over, every reason an arm was refused, and
the fact that the selection is post-hoc. The last one is the load-bearing
caveat of the whole experiment - a frontier report that shows a winner
without it reads as a recommendation.
"""

from __future__ import annotations

import json
import pathlib
import unittest

from agent_economics import run_frontier
from agent_economics.frontier_report import (
    render_frontier_json,
    render_frontier_markdown,
    render_frontier_svg,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "examples" / "compute-frontier" / "manifest.json"


class TheFrontierMarkdownShowsEveryArm(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = run_frontier(PLAN_PATH)
        cls.rendered = render_frontier_markdown(cls.case)

    def test_the_case_exercises_the_property(self) -> None:
        """Several arms, and at least one refused, or this proves nothing."""
        self.assertGreater(len(self.case.arms), 2)
        self.assertTrue(any(not c.eligible for c in self.case.comparisons))

    def test_every_arm_is_named(self) -> None:
        for arm in self.case.arms:
            with self.subTest(arm=arm.arm_id):
                self.assertIn(arm.arm_id, self.rendered)

    def test_every_refusal_carries_its_reason(self) -> None:
        """An arm shown as ineligible without why is an unexplained verdict."""
        for comparison in self.case.comparisons:
            if comparison.eligible:
                continue
            with self.subTest(arm=comparison.candidate_arm):
                self.assertTrue(comparison.reasons)
                for reason in comparison.reasons:
                    self.assertIn(reason, self.rendered)

    def test_the_post_selection_caveat_survives(self) -> None:
        """The experiment's own boundary. Without it the page reads as advice."""
        lowered = self.rendered.lower()
        self.assertIn("post-selection", lowered)
        self.assertIn("held-out", lowered)

    def test_dropping_a_candidate_arm_would_be_caught(self) -> None:
        """Non-vacuity, and it must not be the reference arm.

        The first version dropped `arms[-1]`, which is the reference, and
        the reference is also printed from the frozen plan - so removing it
        from the arm list changed nothing and the check proved nothing. A
        candidate arm has exactly one carrier.
        """
        import dataclasses

        reference = self.case.plan.reference_arm
        candidates = [a for a in self.case.arms if a.arm_id != reference]
        self.assertTrue(candidates, "no non-reference arm to drop")
        dropped = candidates[-1]
        thinner = dataclasses.replace(
            self.case,
            arms=tuple(a for a in self.case.arms if a.arm_id != dropped.arm_id),
            comparisons=tuple(
                c for c in self.case.comparisons
                if c.candidate_arm != dropped.arm_id
            ),
        )
        rendered = render_frontier_markdown(thinner)
        self.assertNotIn(
            dropped.arm_id, rendered,
            "a candidate arm removed from the case still appears in the "
            "page, so these tests cannot detect a renderer that drops one",
        )


class TheFrontierJsonIsStructurallyComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = run_frontier(PLAN_PATH)
        cls.document = json.loads(render_frontier_json(cls.case))

    def test_the_arm_set_is_complete(self) -> None:
        rendered = {arm["arm_id"] for arm in self.document["arms"]}
        self.assertEqual(rendered, {arm.arm_id for arm in self.case.arms})

    def test_the_comparison_set_is_complete(self) -> None:
        rendered = {c["candidate_arm"] for c in self.document["comparisons"]}
        self.assertEqual(
            rendered, {c.candidate_arm for c in self.case.comparisons}
        )

    def test_every_arm_carries_both_digests(self) -> None:
        """A frontier arm without its digests cannot be re-checked."""
        for arm in self.document["arms"]:
            with self.subTest(arm=arm["arm_id"]):
                self.assertTrue(arm["evidence_digest"])
                self.assertTrue(arm["decision_contract_digest"])

    def test_the_decision_and_selection_are_carried(self) -> None:
        self.assertEqual(self.document["decision"], self.case.decision.value)
        self.assertEqual(self.document["selected_arm"], self.case.selected_arm)

    def test_refusals_keep_their_reasons(self) -> None:
        by_arm = {c["candidate_arm"]: c for c in self.document["comparisons"]}
        for comparison in self.case.comparisons:
            if not comparison.eligible:
                with self.subTest(arm=comparison.candidate_arm):
                    self.assertEqual(
                        list(by_arm[comparison.candidate_arm]["reasons"]),
                        list(comparison.reasons),
                    )


class TheFrontierSvgPlotsEveryArm(unittest.TestCase):
    """Structural only. Whether a chart misleads a human eye is not
    something a test decides, and the scorecard says so."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.case = run_frontier(PLAN_PATH)
        cls.svg = render_frontier_svg(cls.case)

    def test_it_is_a_single_well_formed_svg(self) -> None:
        import xml.etree.ElementTree as ElementTree

        root = ElementTree.fromstring(self.svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_every_arm_is_labelled(self) -> None:
        for arm in self.case.arms:
            with self.subTest(arm=arm.arm_id):
                self.assertIn(arm.arm_id, self.svg)

    def test_the_plotted_points_match_the_arm_count(self) -> None:
        import xml.etree.ElementTree as ElementTree

        root = ElementTree.fromstring(self.svg)
        circles = [e for e in root.iter() if e.tag.endswith("circle")]
        self.assertEqual(
            len(circles), len(self.case.arms),
            "the chart plots a different number of points than the case has "
            "arms, so a reader is counting something else",
        )


if __name__ == "__main__":
    unittest.main()
