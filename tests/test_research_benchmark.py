from __future__ import annotations

import unittest
from pathlib import Path

from research.false_green_benchmark import (
    render_summary,
    run_benchmark,
    scenario_matrix,
    summarize,
)


class FalseGreenBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = run_benchmark()
        cls.summary = summarize(cls.rows)

    def test_matrix_and_comparison_count_are_fixed(self) -> None:
        self.assertEqual(len(scenario_matrix()), 98)
        self.assertEqual(len(self.rows), 588)

    def test_incomplete_coverage_can_create_an_unsafe_false_green(self) -> None:
        self.assertGreater(self.summary["unsafe_false_greens"], 0)

    def test_fail_safe_coverage_prevents_every_false_green(self) -> None:
        self.assertEqual(self.summary["safe_false_greens"], 0)

    def test_counterfactual_ablation_has_a_measurable_effect(self) -> None:
        by_ablation = self.summary["by_ablation"]
        self.assertGreater(by_ablation["counterfactual"], 0)

    def test_every_required_dimension_has_an_isolated_false_green(self) -> None:
        by_ablation = self.summary["by_ablation"]
        self.assertTrue(all(count > 0 for count in by_ablation.values()))

    def test_checked_in_summary_is_reproducible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        expected = (root / "research/results/SUMMARY.md").read_text(encoding="utf-8")
        self.assertEqual(render_summary(self.summary), expected)


if __name__ == "__main__":
    unittest.main()
