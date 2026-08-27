"""Stress and property tests for the deterministic kernel.

The existing suite checks known inputs against known outputs. This checks
properties that must hold for *any* input: fail closed on hostile economics, stay
deterministic under permutation, keep derived metrics internally consistent, and
never emit a bare stdlib exception from arithmetic.

Randomized cases use a fixed seed so a failure is reproducible from the reported
scenario rather than only on a lucky run.
"""
from __future__ import annotations

import math
import random
import unittest

from agent_economics import (
    Baseline,
    Decision,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
    evaluate_bundle,
    make_evidence_bundle,
)
from agent_economics.assurance import percentile

SEED = 20260731

POLICY = EconomicPolicy(
    human_hourly_cost_usd=60.0,
    min_acceptable_rate=0.80,
    max_cost_per_acceptable_outcome_usd=2.00,
    max_p95_task_cost_usd=8.00,
    max_trace_cost_per_task_usd=1.00,
    max_calls_per_task=3,
)


def build_bundle(
    *,
    tasks=2,
    calls_per_task=1,
    cost=1.0,
    human_minutes=0.0,
    remediation=0.0,
    incident=0.0,
    value=5.0,
    acceptable=1,
    baseline_cost=4.0,
    baseline_rate=0.7,
    policy=POLICY,
):
    events = []
    outcomes = {}
    for index in range(tasks):
        task_id = f"task-{index:04d}"
        for call in range(calls_per_task):
            events.append(
                TraceEvent(
                    task_id=task_id,
                    event_id=f"event-{index:04d}-{call:03d}",
                    timestamp=f"2026-01-01T00:00:{index % 60:02d}Z",
                    event_type="model",
                    name="complete",
                    direct_cost_usd=cost,
                )
            )
        outcomes[task_id] = Outcome(
            task_id=task_id,
            acceptable=index < acceptable,
            business_value_usd=value,
            human_minutes=human_minutes,
            remediation_cost_usd=remediation,
            incident_loss_usd=incident,
        )
    return make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates={"unused": ModelRate(0.0, 0.0)},
        baseline=Baseline("controlled", baseline_cost, baseline_rate, value),
        policy=policy,
        source_id="source.stress",
        source_version="1",
    )


class FailClosedOnHostileEvidenceTests(unittest.TestCase):
    """Garbage in must produce a typed refusal, never a silent number."""

    def test_non_finite_and_negative_inputs_are_refused(self) -> None:
        hostile = {
            "negative cost": dict(cost=-5.0),
            "infinite cost": dict(cost=float("inf")),
            "nan cost": dict(cost=float("nan")),
            "negative value": dict(value=-100.0),
            "infinite value": dict(value=float("inf")),
            "nan value": dict(value=float("nan")),
            "negative human minutes": dict(human_minutes=-600.0),
            "negative remediation": dict(remediation=-1.0),
            "negative incident loss": dict(incident=-1000.0),
            "baseline rate zero": dict(baseline_rate=0.0),
            "baseline rate negative": dict(baseline_rate=-0.5),
            "baseline rate above one": dict(baseline_rate=1.5),
        }
        for label, kwargs in hostile.items():
            with self.subTest(case=label), self.assertRaises(ValueError):
                build_bundle(**kwargs)

    def test_summed_overflow_is_a_typed_refusal_not_an_overflowerror(self) -> None:
        """Individually valid costs whose total overflows must still explain itself.

        `math.fsum` raises `OverflowError`, which would escape before the
        non-finite guard and surface as a stdlib traceback from a system whose
        entire premise is fail-closed behavior.
        """
        bundle = build_bundle(tasks=2, cost=1e308, acceptable=2)
        with self.assertRaises(ValueError) as caught:
            evaluate_bundle(bundle)
        message = str(caught.exception)
        self.assertIn("overflow", message.lower())
        self.assertNotIsInstance(caught.exception, OverflowError)

    def test_extreme_but_representable_costs_still_decide(self) -> None:
        for cost in (1e-300, 1e-9, 1e6, 1e300):
            with self.subTest(cost=cost):
                case = evaluate_bundle(build_bundle(cost=cost, acceptable=2))
                self.assertIn(case.decision, tuple(Decision))
                self.assertTrue(math.isfinite(case.total_effective_cost_usd))


class DerivedMetricConsistencyTests(unittest.TestCase):
    """Randomized inputs, but the relationships between outputs are fixed."""

    def test_metrics_are_internally_consistent_across_random_scenarios(self) -> None:
        randomizer = random.Random(SEED)
        for trial in range(200):
            tasks = randomizer.randint(1, 12)
            acceptable = randomizer.randint(0, tasks)
            kwargs = dict(
                tasks=tasks,
                calls_per_task=randomizer.randint(1, 4),
                cost=round(randomizer.uniform(0.0, 5.0), 4),
                human_minutes=round(randomizer.uniform(0.0, 30.0), 2),
                remediation=round(randomizer.uniform(0.0, 5.0), 2),
                incident=round(randomizer.uniform(0.0, 50.0), 2),
                value=round(randomizer.uniform(0.0, 20.0), 2),
                acceptable=acceptable,
                baseline_cost=round(randomizer.uniform(0.1, 10.0), 2),
                baseline_rate=round(randomizer.uniform(0.05, 0.95), 3),
            )
            case = evaluate_bundle(build_bundle(**kwargs))
            with self.subTest(trial=trial, **kwargs):
                self.assertEqual(len(case.tasks), tasks)
                self.assertAlmostEqual(
                    case.acceptable_rate, acceptable / tasks, places=12
                )
                self.assertTrue(0.0 <= case.acceptable_rate <= 1.0)

                # Aggregate cost is the sum of its parts.
                self.assertAlmostEqual(
                    case.total_effective_cost_usd,
                    math.fsum(t.effective_cost_usd for t in case.tasks),
                    places=6,
                )
                # Tail statistics bracket correctly.
                self.assertLessEqual(case.p95_task_cost_usd, case.max_task_cost_usd)
                self.assertGreaterEqual(case.p95_task_cost_usd, 0.0)
                self.assertEqual(
                    case.max_task_cost_usd,
                    max(t.effective_cost_usd for t in case.tasks),
                )
                # Cost per acceptable outcome is defined only when one exists.
                if acceptable:
                    self.assertTrue(math.isfinite(case.cost_per_acceptable_outcome_usd))
                    self.assertAlmostEqual(
                        case.cost_per_acceptable_outcome_usd,
                        case.total_effective_cost_usd / acceptable,
                        places=6,
                    )
                else:
                    self.assertEqual(case.cost_per_acceptable_outcome_usd, math.inf)
                    self.assertIsNot(case.decision, Decision.SCALE)
                # Unacceptable tasks contribute no value.
                for task in case.tasks:
                    if not task.acceptable:
                        self.assertEqual(task.business_value_usd, 0.0)

    def test_zero_acceptable_outcomes_yields_infinite_unit_cost_by_design(self) -> None:
        """The one intentional non-finite metric, and it must never read as SCALE."""
        case = evaluate_bundle(build_bundle(tasks=4, acceptable=0))
        self.assertEqual(case.cost_per_acceptable_outcome_usd, math.inf)
        self.assertEqual(case.acceptable_rate, 0.0)
        self.assertIsNot(case.decision, Decision.SCALE)


class DeterminismTests(unittest.TestCase):
    """A verdict and its digests must not depend on incidental ordering."""

    def test_event_order_changes_nothing(self) -> None:
        randomizer = random.Random(SEED)
        bundle = build_bundle(tasks=6, calls_per_task=3, acceptable=4)
        expected = evaluate_bundle(bundle)
        for _ in range(25):
            shuffled = list(bundle.events)
            randomizer.shuffle(shuffled)
            reordered = make_evidence_bundle(
                events=shuffled,
                outcomes=dict(bundle.outcomes),
                rates=dict(bundle.rates),
                baseline=bundle.baseline,
                policy=bundle.policy,
                source_id="source.stress",
                source_version="1",
            )
            observed = evaluate_bundle(reordered)
            self.assertEqual(observed.evidence_digest, expected.evidence_digest)
            self.assertEqual(
                observed.decision_contract_digest, expected.decision_contract_digest
            )
            self.assertEqual(observed.decision, expected.decision)
            self.assertEqual(
                observed.total_effective_cost_usd, expected.total_effective_cost_usd
            )
            self.assertEqual(observed.breaches, expected.breaches)

    def test_repeated_evaluation_is_bit_identical(self) -> None:
        bundle = build_bundle(tasks=5, calls_per_task=2, acceptable=3)
        first = evaluate_bundle(bundle)
        for _ in range(10):
            again = evaluate_bundle(bundle)
            self.assertEqual(again.evidence_digest, first.evidence_digest)
            self.assertEqual(
                again.expected_net_value_per_attempt_usd,
                first.expected_net_value_per_attempt_usd,
            )
            self.assertEqual(again.breaches, first.breaches)


class MonotonicityTests(unittest.TestCase):
    """Economics must move in the direction a reader would expect."""

    def test_more_incident_loss_never_improves_the_decision(self) -> None:
        order = {
            Decision.SCALE: 0,
            Decision.ASSIST: 1,
            Decision.STOP: 2,
            Decision.INCOMPLETE: 3,
        }
        previous = None
        for incident in (0.0, 1.0, 5.0, 25.0, 100.0):
            case = evaluate_bundle(
                build_bundle(tasks=4, acceptable=4, incident=incident)
            )
            with self.subTest(incident=incident):
                self.assertTrue(math.isfinite(case.total_effective_cost_usd))
                if previous is not None:
                    self.assertGreaterEqual(
                        case.total_effective_cost_usd, previous[0]
                    )
                    self.assertGreaterEqual(order[case.decision], previous[1])
                previous = (case.total_effective_cost_usd, order[case.decision])

    def test_more_acceptable_outcomes_never_lowers_the_rate(self) -> None:
        previous = -1.0
        for acceptable in range(0, 9):
            case = evaluate_bundle(build_bundle(tasks=8, acceptable=acceptable))
            with self.subTest(acceptable=acceptable):
                self.assertGreaterEqual(case.acceptable_rate, previous)
                previous = case.acceptable_rate


class ScaleTests(unittest.TestCase):
    """Volume must not change semantics or blow up."""

    def test_one_thousand_tasks_evaluate_consistently(self) -> None:
        case = evaluate_bundle(
            build_bundle(tasks=1000, calls_per_task=2, acceptable=900, cost=0.01)
        )
        self.assertEqual(len(case.tasks), 1000)
        self.assertAlmostEqual(case.acceptable_rate, 0.9, places=12)
        self.assertTrue(math.isfinite(case.total_effective_cost_usd))
        self.assertEqual(len({t.task_id for t in case.tasks}), 1000)

    def test_single_task_single_call_is_valid(self) -> None:
        case = evaluate_bundle(build_bundle(tasks=1, calls_per_task=1, acceptable=1))
        self.assertEqual(len(case.tasks), 1)
        self.assertEqual(case.acceptable_rate, 1.0)
        self.assertEqual(case.p95_task_cost_usd, case.max_task_cost_usd)


class PercentileTests(unittest.TestCase):
    def test_boundaries_and_ordering(self) -> None:
        self.assertEqual(percentile([1.0], 0.95), 1.0)
        self.assertEqual(percentile([1.0, 2.0], 0.0), 1.0)
        self.assertEqual(percentile([1.0, 2.0], 1.0), 2.0)
        self.assertEqual(percentile([3.0, 1.0, 2.0], 0.5), 2.0)

    def test_input_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            percentile([], 0.95)
        for probability in (-0.1, 1.1):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                percentile([1.0, 2.0], probability)

    def test_result_is_always_a_member_of_the_input(self) -> None:
        randomizer = random.Random(SEED)
        for _ in range(100):
            values = [round(randomizer.uniform(0, 100), 3) for _ in range(randomizer.randint(1, 20))]
            self.assertIn(percentile(list(values), 0.95), values)


if __name__ == "__main__":
    unittest.main()
