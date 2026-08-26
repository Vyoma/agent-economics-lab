"""
Regression locks for the research scripts whose numbers the README publishes.

`mutation_score.py`, `real_trace_verdict.py`, and `sensitivity_sweep.py` produce
the headline claims in the README. Without these tests the claims live only in
terminal output and can drift silently when the engine changes.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_economics.models import Decision  # noqa: E402
from mutation_score import mutation_stats  # noqa: E402
from real_trace_verdict import verdict_stats  # noqa: E402
from sensitivity_sweep import sweep_stats  # noqa: E402


class MutationScoreTest(unittest.TestCase):
    """The README claims 588 mutations, 100% killed, 23 dynamic survivors."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.stats = mutation_stats()

    def test_mutation_matrix_shape(self) -> None:
        self.assertEqual(self.stats["n_scenarios"], 98)
        self.assertEqual(self.stats["n_gates"], 6)
        self.assertEqual(self.stats["n_total"], 588)
        self.assertEqual(
            self.stats["n_total"],
            self.stats["n_scenarios"] * self.stats["n_gates"],
        )

    def test_fixed_contract_kills_every_mutation(self) -> None:
        self.assertEqual(self.stats["fixed_killed"], 588)
        self.assertEqual(self.stats["fixed_score"], 1.0)

    def test_dynamic_engine_lets_twenty_three_survive(self) -> None:
        self.assertEqual(self.stats["dynamic_survived"], 23)
        self.assertEqual(self.stats["dynamic_killed"], 565)

    def test_per_gate_survivor_breakdown(self) -> None:
        """The README's per-gate bar chart. Every gate is sole-provider."""
        expected = {
            "outcome_quality": 2,
            "unit_economics": 1,
            "tail_risk": 8,
            "business_value": 1,
            "counterfactual": 3,
            "runtime_caps": 8,
        }
        actual = {
            dim: st["dyn_survived"] for dim, st in self.stats["gate_stats"].items()
        }
        self.assertEqual(actual, expected)
        self.assertEqual(sum(expected.values()), self.stats["dynamic_survived"])

    def test_every_gate_is_load_bearing_under_the_fixed_contract(self) -> None:
        for dim, st in self.stats["gate_stats"].items():
            with self.subTest(gate=dim):
                self.assertEqual(st["total"], 98)
                self.assertEqual(st["fixed_killed"], 98)


class RealTraceVerdictTest(unittest.TestCase):
    """A naive transcript read and the gated verdict must disagree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.stats = verdict_stats()

    def test_naive_reading_looks_acceptable(self) -> None:
        self.assertEqual(self.stats["n"], 2)
        self.assertEqual(self.stats["n_acceptable"], 1)
        self.assertEqual(self.stats["naive_rate"], 0.5)

    def test_gated_verdict_is_assist(self) -> None:
        self.assertIs(self.stats["case"].decision, Decision.ASSIST)

    def test_at_least_one_gate_blocks(self) -> None:
        self.assertGreaterEqual(len(self.stats["failed_gates"]), 1)

    def test_the_two_readings_disagree(self) -> None:
        """This is the whole point of the script: 50% 'passing' is not SCALE."""
        self.assertGreater(self.stats["naive_rate"], 0.0)
        self.assertIsNot(self.stats["case"].decision, Decision.SCALE)


class SensitivitySweepTest(unittest.TestCase):
    """Verdict robustness under perturbed economic assumptions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.stats = sweep_stats()

    def test_sweep_shape(self) -> None:
        self.assertEqual(self.stats["n"], 98)
        self.assertEqual(self.stats["grid_size"], 48)
        self.assertEqual(len(self.stats["flip_counts"]), 98)

    def test_robustness_buckets_partition_the_scenarios(self) -> None:
        total = self.stats["robust"] + self.stats["fragile"] + self.stats["brittle"]
        self.assertEqual(total, self.stats["n"])

    def test_brittle_scenarios_are_reported(self) -> None:
        """Verdicts that flip under plausible assumptions must not be hidden."""
        self.assertEqual(self.stats["brittle"], 55)
        self.assertLessEqual(self.stats["max_flips"], self.stats["grid_size"])

    def test_baseline_fragility_is_monotone_in_perturbation_size(self) -> None:
        """A larger baseline error should not flip strictly fewer gates."""
        fragility = self.stats["fragility"]
        self.assertGreaterEqual(fragility[0.50], fragility[0.75])
        self.assertGreaterEqual(fragility[0.75], fragility[0.90])
        self.assertGreaterEqual(fragility[1.50], fragility[1.25])
        self.assertGreaterEqual(fragility[1.25], fragility[1.10])

    def test_fifty_percent_baseline_error_is_critical(self) -> None:
        self.assertEqual(self.stats["fragility"][0.50], 25)
        self.assertGreater(self.stats["fragility"][0.50] / self.stats["n"], 0.25)


if __name__ == "__main__":
    unittest.main()
