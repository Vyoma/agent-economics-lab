from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from false_green import (
    main,
    render_csv,
    render_summary,
    render_summary_json,
    run_benchmark,
    scenario_matrix,
    summarize,
)


class DecisionCoverageDriftBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = run_benchmark()
        cls.summary = summarize(cls.rows)

    def test_matrix_and_comparison_count_are_fixed(self) -> None:
        self.assertEqual(len(scenario_matrix()), 98)
        self.assertEqual(len(self.rows), 588)

    def test_dynamic_coverage_creates_false_scale_transitions(self) -> None:
        self.assertEqual(self.summary["dynamic_false_scale_transitions"], 23)

    def test_fixed_contract_refuses_every_gate_disablement(self) -> None:
        self.assertEqual(self.summary["fixed_contract_incomplete"], 588)
        self.assertEqual(self.summary["fixed_contract_false_scale_transitions"], 0)

    def test_counterfactual_disablement_has_a_measurable_effect(self) -> None:
        by_dimension = self.summary["by_disabled_dimension"]
        self.assertGreater(by_dimension["counterfactual"], 0)

    def test_every_required_dimension_has_a_false_scale_transition(self) -> None:
        by_dimension = self.summary["by_disabled_dimension"]
        self.assertTrue(all(count > 0 for count in by_dimension.values()))

    def test_evidence_is_unchanged_across_architectures(self) -> None:
        for row in self.rows:
            self.assertEqual(
                {
                    row["full_evidence_digest"],
                    row["fixed_contract_evidence_digest"],
                    row["dynamic_coverage_evidence_digest"],
                },
                {row["full_evidence_digest"]},
            )

    def test_contract_digests_make_the_configuration_change_visible(self) -> None:
        for row in self.rows:
            digests = {
                row["full_contract_digest"],
                row["fixed_contract_digest"],
                row["dynamic_coverage_contract_digest"],
            }
            self.assertNotIn("", digests)
            self.assertEqual(len(digests), 3)

    def test_checked_in_artifacts_are_reproducible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        results = root / "research/results"
        structured = results / "decision-coverage-drift"
        self.assertEqual(
            render_summary(self.summary),
            (results / "SUMMARY.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            render_csv(self.rows),
            (structured / "results.csv").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            render_summary_json(self.summary),
            (structured / "summary.json").read_text(encoding="utf-8"),
        )

    def test_verification_happens_before_output_is_written(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "results.csv"
            artifact.write_text("stale\n", encoding="utf-8")
            with redirect_stdout(output):
                exit_code = main(
                    ["--output", str(artifact), "--verify", str(artifact)]
                )
            self.assertEqual(artifact.read_text(encoding="utf-8"), "stale\n")
        self.assertEqual(exit_code, 1)
        self.assertIn("Generated results differ", output.getvalue())


if __name__ == "__main__":
    unittest.main()
