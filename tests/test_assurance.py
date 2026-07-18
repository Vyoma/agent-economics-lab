from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from agent_economics import (
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Coverage,
    Decision,
    default_checks,
    evaluate,
    evaluate_bundle,
    load_baseline,
    load_csv_bundle,
    load_outcomes,
    load_policy,
    load_rates,
    load_traces,
)
from agent_economics.assurance import AssuranceEngine
from agent_economics.report import render_json, render_markdown


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


class AssuranceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.events = load_traces(EXAMPLES / "support_trace.csv")
        cls.outcomes = load_outcomes(EXAMPLES / "outcomes.csv")
        cls.rates = load_rates(EXAMPLES / "rates.json")
        cls.baseline = load_baseline(EXAMPLES / "baseline.json")
        cls.policy = load_policy(EXAMPLES / "policy.json")

    def evaluate(self, policy=None):
        return evaluate(
            self.events,
            self.outcomes,
            self.rates,
            self.baseline,
            policy or self.policy,
        )

    def test_demo_routes_to_assist(self) -> None:
        case = self.evaluate()
        self.assertEqual(case.decision, Decision.ASSIST)
        self.assertEqual(len(case.tasks), 8)
        self.assertEqual(case.acceptable_rate, 0.75)
        self.assertGreater(case.expected_net_value_per_attempt_usd, 0)
        controls = {(finding.task_id, finding.control) for finding in case.findings}
        self.assertIn(("t-005", "repeated_tool_shape"), controls)
        failed_gates = {
            (result.task_id, result.check_id)
            for result in case.check_results
            if result.status is CheckStatus.FAIL
        }
        self.assertIn(("t-005", "gate.runtime-caps"), failed_gates)

    def test_permissive_policy_routes_to_scale(self) -> None:
        policy = replace(
            self.policy,
            min_acceptable_rate=0.70,
            max_cost_per_acceptable_outcome_usd=10.0,
            max_p95_task_cost_usd=20.0,
            max_trace_cost_per_task_usd=1.0,
            max_calls_per_task=20,
        )
        self.assertEqual(self.evaluate(policy).decision, Decision.SCALE)

    def test_negative_threshold_routes_to_stop(self) -> None:
        policy = replace(self.policy, min_expected_net_value_per_attempt_usd=100.0)
        self.assertEqual(self.evaluate(policy).decision, Decision.STOP)

    def test_report_exposes_claim_boundary(self) -> None:
        report = render_markdown(self.evaluate())
        self.assertIn("**Decision: ASSIST**", report)
        self.assertIn("not semantic proof", report)
        self.assertIn("Counterfactual", report)
        self.assertIn("Enabled checks", report)

    def test_counterfactual_underperformance_cannot_scale(self) -> None:
        perfect_free_baseline = replace(
            self.baseline,
            cost_per_attempt_usd=0.0,
            acceptable_rate=1.0,
            value_per_acceptable_outcome_usd=8.0,
        )
        permissive = replace(
            self.policy,
            min_acceptable_rate=0.0,
            max_cost_per_acceptable_outcome_usd=100.0,
            max_p95_task_cost_usd=100.0,
            max_trace_cost_per_task_usd=100.0,
            max_calls_per_task=100,
        )
        case = evaluate(
            self.events,
            self.outcomes,
            self.rates,
            perfect_free_baseline,
            permissive,
        )
        self.assertLess(case.incremental_net_value_vs_baseline_usd, 0)
        self.assertEqual(case.decision, Decision.STOP)

    def test_removing_optional_diagnostic_changes_only_findings(self) -> None:
        evidence = load_csv_bundle(
            traces=EXAMPLES / "support_trace.csv",
            outcomes=EXAMPLES / "outcomes.csv",
            rates=EXAMPLES / "rates.json",
            baseline=EXAMPLES / "baseline.json",
            policy=EXAMPLES / "policy.json",
        )
        full = evaluate_bundle(evidence)
        checks = tuple(
            check
            for check in default_checks()
            if check.id != "diagnostic.repeated-tool-shape"
        )
        reduced = evaluate_bundle(evidence, checks)
        self.assertEqual(reduced.decision, full.decision)
        self.assertEqual(reduced.total_effective_cost_usd, full.total_effective_cost_usd)
        self.assertEqual(len(full.findings), 1)
        self.assertEqual(reduced.findings, ())

    def test_removing_required_gate_is_incomplete(self) -> None:
        evidence = load_csv_bundle(
            traces=EXAMPLES / "support_trace.csv",
            outcomes=EXAMPLES / "outcomes.csv",
            rates=EXAMPLES / "rates.json",
            baseline=EXAMPLES / "baseline.json",
            policy=EXAMPLES / "policy.json",
        )
        checks = tuple(
            check for check in default_checks() if check.id != "gate.acceptable-rate"
        )
        case = evaluate_bundle(evidence, checks)
        self.assertEqual(case.decision, Decision.INCOMPLETE)
        self.assertEqual(case.missing_coverage, ("outcome_quality",))

    def test_custom_gate_can_route_to_stop_without_core_edit(self) -> None:
        def custom(view):
            return CheckOutput(
                results=(
                    CheckResult(
                        check_id="gate.local",
                        status=CheckStatus.FAIL,
                        message="local policy failed",
                        on_failure=Decision.STOP,
                    ),
                )
            )

        check = CheckSpec(
            id="gate.local",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset(),
            run=custom,
        )
        case = self.evaluate()
        custom_case = evaluate(
            self.events,
            self.outcomes,
            self.rates,
            self.baseline,
            self.policy,
            checks=default_checks() + (check,),
        )
        self.assertEqual(case.decision, Decision.ASSIST)
        self.assertEqual(custom_case.decision, Decision.STOP)
        self.assertIn("gate.local@1", custom_case.enabled_checks)

    def test_diagnostic_cannot_change_decision(self) -> None:
        def invalid_diagnostic(view):
            return CheckOutput(
                results=(
                    CheckResult(
                        check_id="diagnostic.invalid",
                        status=CheckStatus.FAIL,
                        message="must not route",
                        on_failure=Decision.STOP,
                    ),
                )
            )

        check = CheckSpec(
            id="diagnostic.invalid",
            version="1",
            mode=CheckMode.DIAGNOSTIC,
            covers=frozenset(),
            run=invalid_diagnostic,
        )
        with self.assertRaisesRegex(ValueError, "cannot change"):
            evaluate(
                self.events,
                self.outcomes,
                self.rates,
                self.baseline,
                self.policy,
                checks=default_checks() + (check,),
            )

    def test_duplicate_check_ids_are_rejected(self) -> None:
        check = default_checks()[0]
        with self.assertRaisesRegex(ValueError, "Duplicate check IDs"):
            AssuranceEngine((check, check), frozenset({Coverage.OUTCOME_QUALITY}))

    def test_json_and_markdown_render_same_case(self) -> None:
        case = self.evaluate()
        self.assertIn('"decision": "ASSIST"', render_json(case))
        self.assertIn("**Decision: ASSIST**", render_markdown(case))


if __name__ == "__main__":
    unittest.main()
