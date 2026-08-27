from __future__ import annotations

import random
import unittest
from pathlib import Path

from agent_economics import (
    DEFAULT_REQUIRED_COVERAGE,
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Decision,
    default_checks,
    default_engine,
    evaluate_bundle,
    load_csv_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


class AssuranceInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = load_csv_bundle(
            traces=EXAMPLES / "support_trace.csv",
            outcomes=EXAMPLES / "outcomes.csv",
            rates=EXAMPLES / "rates.json",
            baseline=EXAMPLES / "baseline.json",
            policy=EXAMPLES / "policy.json",
        )
        cls.checks = default_checks()

    def test_random_missing_coverage_compositions_never_scale(self) -> None:
        randomizer = random.Random(20260727)
        for _ in range(200):
            selected = tuple(
                check for check in self.checks if randomizer.choice((False, True))
            )
            enabled_coverage = frozenset(
                coverage
                for check in selected
                if check.mode is CheckMode.GATE
                for coverage in check.covers
            )
            case = default_engine(selected).evaluate(self.evidence)
            if not DEFAULT_REQUIRED_COVERAGE.issubset(enabled_coverage):
                self.assertEqual(case.decision, Decision.INCOMPLETE)

    def test_each_sole_provider_gate_is_required_for_scale(self) -> None:
        for removed in (
            check for check in self.checks if check.mode is CheckMode.GATE
        ):
            selected = tuple(
                check for check in self.checks if check.id != removed.id
            )
            case = default_engine(selected).evaluate(self.evidence)
            self.assertEqual(case.decision, Decision.INCOMPLETE, removed.id)

    def test_check_order_does_not_change_the_decision(self) -> None:
        expected = evaluate_bundle(self.evidence, self.checks)
        randomizer = random.Random(20260727)
        for _ in range(100):
            reordered = list(self.checks)
            randomizer.shuffle(reordered)
            observed = evaluate_bundle(self.evidence, tuple(reordered))
            self.assertEqual(observed.decision, expected.decision)
            self.assertEqual(
                observed.total_effective_cost_usd,
                expected.total_effective_cost_usd,
            )
            self.assertEqual(
                observed.incremental_net_value_vs_baseline_usd,
                expected.incremental_net_value_vs_baseline_usd,
            )
            self.assertEqual(observed.evidence_digest, expected.evidence_digest)

    def test_adding_a_restrictive_gate_cannot_improve_the_decision(self) -> None:
        def stop_gate(view):
            return CheckOutput(
                results=(
                    CheckResult(
                        check_id="gate.always-stop",
                        status=CheckStatus.FAIL,
                        message="controlled restrictive gate",
                        on_failure=Decision.STOP,
                    ),
                )
            )

        restrictive = CheckSpec(
            id="gate.always-stop",
            version="1-test",
            mode=CheckMode.GATE,
            covers=frozenset(),
            run=stop_gate,
            failure_route=Decision.STOP,
        )
        original = evaluate_bundle(self.evidence, self.checks)
        restricted = evaluate_bundle(self.evidence, self.checks + (restrictive,))
        order = {
            Decision.SCALE: 0,
            Decision.ASSIST: 1,
            Decision.STOP: 2,
            Decision.INCOMPLETE: 3,
        }
        self.assertGreaterEqual(order[restricted.decision], order[original.decision])
        self.assertEqual(restricted.evidence_digest, original.evidence_digest)

    def test_optional_diagnostic_is_decision_noninterfering(self) -> None:
        full = evaluate_bundle(self.evidence, self.checks)
        without_diagnostic = evaluate_bundle(
            self.evidence,
            tuple(
                check
                for check in self.checks
                if check.id != "diagnostic.repeated-tool-shape"
            ),
        )
        self.assertEqual(without_diagnostic.decision, full.decision)
        self.assertEqual(without_diagnostic.breaches, full.breaches)
        self.assertEqual(without_diagnostic.evidence_digest, full.evidence_digest)


if __name__ == "__main__":
    unittest.main()
