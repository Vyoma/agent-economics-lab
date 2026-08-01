"""Property tests for the frontier's statistical machinery.

`clopper_pearson_upper` and `_paired_cost_bootstrap` decide whether a candidate
configuration is eligible. If either is wrong, the frontier adopts arms it should
have refused, and no amount of downstream digesting would catch it.

The exact bound has a closed form at zero observations, which lets these tests
check the implementation against analysis rather than against itself.
"""
from __future__ import annotations

import math
import random
import unittest

from agent_economics.frontier import (
    _binomial_cdf,
    _paired_cost_bootstrap,
    clopper_pearson_upper,
)

SEED = 20260731


class ClopperPearsonTests(unittest.TestCase):
    def test_zero_observations_matches_the_closed_form(self) -> None:
        """With no harmful events the exact upper bound is 1 - alpha^(1/n)."""
        for trials in (1, 2, 5, 20, 100, 500):
            for alpha in (0.05, 0.025, 0.01, 0.001):
                with self.subTest(trials=trials, alpha=alpha):
                    self.assertAlmostEqual(
                        clopper_pearson_upper(0, trials, alpha),
                        1.0 - alpha ** (1.0 / trials),
                        places=9,
                    )

    def test_all_observations_harmful_gives_certainty(self) -> None:
        for trials in (1, 5, 20):
            with self.subTest(trials=trials):
                self.assertEqual(clopper_pearson_upper(trials, trials, 0.025), 1.0)

    def test_bound_is_always_a_probability(self) -> None:
        randomizer = random.Random(SEED)
        for _ in range(300):
            trials = randomizer.randint(1, 200)
            observed = randomizer.randint(0, trials)
            alpha = randomizer.choice((0.05, 0.025, 0.01, 0.005, 0.001))
            bound = clopper_pearson_upper(observed, trials, alpha)
            with self.subTest(observed=observed, trials=trials, alpha=alpha):
                self.assertTrue(0.0 <= bound <= 1.0)
                self.assertGreaterEqual(
                    bound + 1e-9,
                    observed / trials,
                    "an upper bound must not fall below the point estimate",
                )

    def test_bound_is_monotonic_in_observations(self) -> None:
        previous = -1.0
        for observed in range(0, 51):
            bound = clopper_pearson_upper(observed, 50, 0.025)
            with self.subTest(observed=observed):
                self.assertGreaterEqual(bound, previous - 1e-12)
            previous = bound

    def test_bound_tightens_as_evidence_grows(self) -> None:
        """More clean trials must narrow the bound, never widen it."""
        previous = 1.1
        for trials in (1, 5, 10, 50, 100, 1000):
            bound = clopper_pearson_upper(0, trials, 0.025)
            with self.subTest(trials=trials):
                self.assertLess(bound, previous)
            previous = bound

    def test_smaller_alpha_gives_a_more_conservative_bound(self) -> None:
        previous = 0.0
        for alpha in (0.1, 0.05, 0.025, 0.01, 0.001):
            bound = clopper_pearson_upper(1, 30, alpha)
            with self.subTest(alpha=alpha):
                self.assertGreaterEqual(bound, previous)
            previous = bound

    def test_inputs_are_validated(self) -> None:
        for args in ((0, 0, 0.025), (-1, 10, 0.025), (11, 10, 0.025),
                     (0, 10, 0.0), (0, 10, 1.0), (0, 10, -0.1), (0, 10, 1.1)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    clopper_pearson_upper(*args)

    def test_binomial_cdf_is_a_distribution(self) -> None:
        for trials in (1, 5, 20):
            for probability in (0.01, 0.25, 0.5, 0.9):
                with self.subTest(trials=trials, probability=probability):
                    self.assertAlmostEqual(
                        _binomial_cdf(trials, trials, probability), 1.0, places=9
                    )
                    previous = -1.0
                    for observed in range(trials + 1):
                        value = _binomial_cdf(observed, trials, probability)
                        self.assertTrue(0.0 <= value <= 1.0)
                        self.assertGreaterEqual(value, previous - 1e-12)
                        previous = value

    def test_binomial_cdf_edge_probabilities(self) -> None:
        self.assertEqual(_binomial_cdf(0, 10, 0.0), 1.0)
        self.assertEqual(_binomial_cdf(10, 10, 1.0), 1.0)
        self.assertEqual(_binomial_cdf(9, 10, 1.0), 0.0)


class PairedBootstrapTests(unittest.TestCase):
    def test_point_estimate_matches_the_definition(self) -> None:
        reference = [2.0, 4.0, 6.0, 8.0]
        candidate = [1.0, 2.0, 3.0, 4.0]
        point, _ = _paired_cost_bootstrap(
            reference, candidate, samples=200, alpha=0.025, seed=1
        )
        self.assertAlmostEqual(point, 0.5, places=12)

    def test_lower_bound_never_exceeds_the_point_estimate(self) -> None:
        randomizer = random.Random(SEED)
        for trial in range(40):
            count = randomizer.randint(5, 60)
            reference = [round(randomizer.uniform(0.5, 5.0), 4) for _ in range(count)]
            candidate = [round(randomizer.uniform(0.5, 5.0), 4) for _ in range(count)]
            point, lower = _paired_cost_bootstrap(
                reference, candidate, samples=300, alpha=0.025, seed=trial
            )
            with self.subTest(trial=trial):
                self.assertLessEqual(lower, point + 1e-9)

    def test_same_seed_reproduces_the_interval(self) -> None:
        reference = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidate = [0.9, 1.8, 2.7, 3.6, 4.5]
        first = _paired_cost_bootstrap(
            reference, candidate, samples=500, alpha=0.025, seed=7
        )
        second = _paired_cost_bootstrap(
            reference, candidate, samples=500, alpha=0.025, seed=7
        )
        self.assertEqual(first, second)

    def test_proportional_arms_have_no_resample_variance(self) -> None:
        """A constant per-task ratio gives the same estimate in every resample.

        Worth pinning because it looks like a stuck bootstrap but is the correct
        answer: if every candidate cost is exactly k times its reference, the
        ratio of sums is k regardless of which tasks are drawn.
        """
        reference = [1.0, 2.0, 3.0, 4.0, 5.0]
        candidate = [0.9 * value for value in reference]
        for seed in (1, 2, 3):
            point, lower = _paired_cost_bootstrap(
                reference, candidate, samples=500, alpha=0.025, seed=seed
            )
            with self.subTest(seed=seed):
                self.assertAlmostEqual(point, 0.1, places=12)
                self.assertAlmostEqual(lower, 0.1, places=12)

    def test_different_seed_changes_the_interval_when_variance_exists(self) -> None:
        reference = [1.0, 2.0, 3.0, 40.0, 5.0]
        candidate = [0.9, 1.9, 0.2, 39.0, 4.0]
        point_a, lower_a = _paired_cost_bootstrap(
            reference, candidate, samples=500, alpha=0.025, seed=1
        )
        point_b, lower_b = _paired_cost_bootstrap(
            reference, candidate, samples=500, alpha=0.025, seed=2
        )
        self.assertAlmostEqual(point_a, point_b, places=12)
        self.assertNotEqual(lower_a, lower_b)

    def test_free_candidate_is_a_total_reduction(self) -> None:
        point, lower = _paired_cost_bootstrap(
            [1.0] * 5, [0.0] * 5, samples=200, alpha=0.025, seed=3
        )
        self.assertEqual(point, 1.0)
        self.assertEqual(lower, 1.0)

    def test_zero_reference_cost_fails_closed_to_negative_infinity(self) -> None:
        """A free reference makes a reduction ratio undefined, so refuse it.

        `evaluate_frontier` rejects a non-finite estimate, so returning -inf here
        routes to ineligible rather than silently adopting the candidate.
        """
        point, lower = _paired_cost_bootstrap(
            [0.0] * 5, [1.0] * 5, samples=100, alpha=0.025, seed=4
        )
        self.assertEqual(point, -math.inf)
        self.assertFalse(math.isfinite(lower))

    def test_identical_arms_show_no_reduction(self) -> None:
        costs = [1.5, 2.5, 3.5, 4.5]
        point, lower = _paired_cost_bootstrap(
            costs, list(costs), samples=300, alpha=0.025, seed=5
        )
        self.assertAlmostEqual(point, 0.0, places=12)
        self.assertAlmostEqual(lower, 0.0, places=12)

    def test_pairing_is_preserved_across_resamples(self) -> None:
        """Both arms must be resampled on the same indices.

        If they were resampled independently, a paired comparison would become an
        unpaired one and the interval would be wrong in a way no digest reveals.
        Identical arms are the detector: paired resampling gives exactly zero
        spread, independent resampling would not.
        """
        costs = [0.5, 1.0, 4.0, 9.0, 20.0, 50.0]
        for seed in range(6):
            point, lower = _paired_cost_bootstrap(
                costs, list(costs), samples=200, alpha=0.025, seed=seed
            )
            with self.subTest(seed=seed):
                self.assertAlmostEqual(point, 0.0, places=12)
                self.assertAlmostEqual(lower, 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
