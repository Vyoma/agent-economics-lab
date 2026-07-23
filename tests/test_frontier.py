from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from agent_economics import (
    FrontierDecision,
    ModelRate,
    TaskIdentity,
    clopper_pearson_upper,
    evaluate_frontier,
    load_experiment,
    make_evidence_bundle,
    render_frontier_json,
    render_frontier_markdown,
    render_frontier_svg,
    run_frontier,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "examples" / "compute-frontier" / "manifest.json"


class FrontierTests(unittest.TestCase):
    def test_zero_breakages_still_has_nonzero_exact_upper_bound(self) -> None:
        alpha = 0.05
        bound = clopper_pearson_upper(0, 10, alpha)
        self.assertAlmostEqual(bound, 1 - alpha ** (1 / 10), places=10)
        self.assertGreater(bound, 0.25)

    def test_frozen_example_selects_balanced_arm(self) -> None:
        case = run_frontier(PLAN_PATH)
        self.assertEqual(case.decision, FrontierDecision.ADOPT)
        self.assertEqual(case.selected_arm, "balanced-4-step")
        comparisons = {
            comparison.candidate_arm: comparison
            for comparison in case.comparisons
        }
        self.assertTrue(comparisons["balanced-4-step"].eligible)
        self.assertFalse(comparisons["cheap-2-step"].eligible)
        self.assertGreater(
            comparisons["cheap-2-step"].breakage_rate_upper,
            case.plan.max_breakage_rate,
        )

    def test_missing_planned_arm_fails_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        bundles.pop("cheap-2-step")
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("missing planned arms" in item for item in case.problems))

    def test_mismatched_task_ids_fail_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        events = tuple(event for event in original.events if event.task_id != "case-000")
        outcomes = {
            task_id: outcome
            for task_id, outcome in original.outcomes.items()
            if task_id != "case-000"
        }
        bundles["balanced-4-step"] = make_evidence_bundle(
            events=events,
            outcomes=outcomes,
            rates=original.rates,
            baseline=original.baseline,
            policy=original.policy,
            source_id="source.test-mismatch",
            task_manifest={
                task_id: identity
                for task_id, identity in original.task_manifest.items()
                if task_id != "case-000"
            },
        )
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("do not exactly match" in item for item in case.problems))

    def test_predeclared_minimum_sample_size_fails_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        case = evaluate_frontier(
            replace(plan, min_paired_tasks=181), bundles, problems
        )
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("predeclared minimum" in item for item in case.problems))

    def test_unknown_tool_cost_fails_closed(self) -> None:
        bundle = {
            "events": [
                {
                    "task_id": "t-1",
                    "event_id": "e-1",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "event_type": "tool",
                    "name": "search",
                },
                {
                    "task_id": "t-2",
                    "event_id": "e-2",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "event_type": "tool",
                    "name": "search",
                },
            ],
            "outcomes": [
                {
                    "task_id": task_id,
                    "acceptable": True,
                    "business_value_usd": 5.0,
                    "human_minutes": 0.0,
                    "remediation_cost_usd": 0.0,
                    "incident_loss_usd": 0.0,
                }
                for task_id in ("t-1", "t-2")
            ],
            "task_manifest": [
                {
                    "task_id": task_id,
                    "input_digest": hashlib.sha256(task_id.encode("utf-8")).hexdigest(),
                    "rubric_version": "test-v1",
                }
                for task_id in ("t-1", "t-2")
            ],
            "rates": {},
            "baseline": {
                "name": "baseline",
                "cost_per_attempt_usd": 1.0,
                "acceptable_rate": 0.5,
                "value_per_acceptable_outcome_usd": 5.0,
            },
            "policy": {
                "human_hourly_cost_usd": 60.0,
                "min_acceptable_rate": 0.5,
                "max_cost_per_acceptable_outcome_usd": 10.0,
                "max_p95_task_cost_usd": 10.0,
                "max_trace_cost_per_task_usd": 10.0,
                "max_calls_per_task": 10,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("reference", "candidate"):
                (root / f"{name}.json").write_text(
                    json.dumps(bundle), encoding="utf-8"
                )
            plan = {
                "schema_version": 1,
                "experiment_id": "unknown-cost",
                "reference_arm": "reference",
                "arms": {
                    "reference": "reference.json",
                    "candidate": "candidate.json",
                },
                "max_breakage_rate": 0.1,
                "min_cost_reduction_rate": 0.0,
                "confidence_level": 0.95,
                "bootstrap_samples": 800,
                "seed": 1,
                "min_paired_tasks": 2,
                "task_manifest": "tasks.json",
                "task_manifest_digest": hashlib.sha256(
                    json.dumps(
                        {"tasks": bundle["task_manifest"]},
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            }
            (root / "tasks.json").write_text(
                json.dumps(
                    {"schema_version": 1, "tasks": bundle["task_manifest"]}
                ),
                encoding="utf-8",
            )
            plan_path = root / "manifest.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            case = run_frontier(plan_path)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("unknown cost" in item for item in case.problems))

    def test_public_api_rejects_missing_non_model_cost(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        events = list(original.events)
        events[0] = replace(
            events[0], event_type="tool", model="", direct_cost_usd=None
        )
        bundles["balanced-4-step"] = make_evidence_bundle(
            events=events,
            outcomes=original.outcomes,
            rates=original.rates,
            baseline=original.baseline,
            policy=original.policy,
            source_id="source.test-missing-cost",
            task_manifest=original.task_manifest,
        )
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("unknown cost" in item for item in case.problems))

    def test_non_finite_cost_cannot_be_adopted(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        events = list(original.events)
        events[0] = replace(events[0], direct_cost_usd=math.nan)
        bundles["balanced-4-step"] = replace(
            original,
            events=tuple(events),
        )
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("must be finite" in item for item in case.problems))

    def test_wrong_typed_outcome_fails_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        outcomes = dict(original.outcomes)
        outcomes["case-000"] = replace(
            outcomes["case-000"], acceptable="false"  # type: ignore[arg-type]
        )
        bundles["balanced-4-step"] = replace(original, outcomes=outcomes)
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("acceptable must be boolean" in item for item in case.problems))

    def test_zero_rate_card_usage_fails_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        events = list(original.events)
        events[0] = replace(
            events[0],
            model="priced-model",
            input_tokens=0,
            output_tokens=0,
            direct_cost_usd=None,
        )
        bundles["balanced-4-step"] = make_evidence_bundle(
            events=events,
            outcomes=original.outcomes,
            rates={
                **original.rates,
                "priced-model": ModelRate(1.0, 2.0),
            },
            baseline=original.baseline,
            policy=original.policy,
            source_id="source.test-zero-usage",
            task_manifest=original.task_manifest,
        )
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("zero rate-card usage" in item for item in case.problems))

    def test_baseline_drift_fails_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        bundles["balanced-4-step"] = make_evidence_bundle(
            events=original.events,
            outcomes=original.outcomes,
            rates=original.rates,
            baseline=replace(original.baseline, cost_per_attempt_usd=1.0),
            policy=original.policy,
            source_id="source.test-baseline-drift",
            task_manifest=original.task_manifest,
        )
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("baseline differs" in item for item in case.problems))

    def test_reused_task_id_with_different_input_fails_closed(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        original = bundles["balanced-4-step"]
        task_manifest = dict(original.task_manifest)
        task_manifest["case-000"] = TaskIdentity(
            task_id="case-000",
            input_digest="f" * 64,
            rubric_version=task_manifest["case-000"].rubric_version,
        )
        bundles["balanced-4-step"] = make_evidence_bundle(
            events=original.events,
            outcomes=original.outcomes,
            rates=original.rates,
            baseline=original.baseline,
            policy=original.policy,
            source_id="source.test-task-drift",
            task_manifest=task_manifest,
        )
        case = evaluate_frontier(plan, bundles, problems)
        self.assertEqual(case.decision, FrontierDecision.INCOMPLETE)
        self.assertTrue(any("input digests" in item for item in case.problems))

    def test_large_study_exact_bound_is_stable(self) -> None:
        bound = clopper_pearson_upper(250, 5000, 0.01)
        self.assertTrue(math.isfinite(bound))
        self.assertGreater(bound, 0.05)
        self.assertLess(bound, 0.06)

    def test_hold_does_not_recommend_an_unsafe_reference(self) -> None:
        plan, bundles, problems = load_experiment(PLAN_PATH)
        for arm_id, original in tuple(bundles.items()):
            bundles[arm_id] = make_evidence_bundle(
                events=original.events,
                outcomes=original.outcomes,
                rates=original.rates,
                baseline=original.baseline,
                policy=replace(
                    original.policy,
                    max_cost_per_acceptable_outcome_usd=0.01,
                ),
                source_id="source.test-unsafe-reference",
                task_manifest=original.task_manifest,
            )
        case = evaluate_frontier(plan, bundles, problems)
        report = render_frontier_markdown(case)
        self.assertEqual(case.decision, FrontierDecision.HOLD)
        self.assertIn("no deployment recommendation", report.lower())
        self.assertNotIn("keep the reference", report.lower())

    def test_outputs_are_deterministic_and_machine_safe(self) -> None:
        first = run_frontier(PLAN_PATH)
        second = run_frontier(PLAN_PATH)
        self.assertEqual(render_frontier_json(first), render_frontier_json(second))
        self.assertEqual(
            render_frontier_markdown(first), render_frontier_markdown(second)
        )
        self.assertEqual(render_frontier_svg(first), render_frontier_svg(second))
        payload = json.loads(render_frontier_json(first))
        self.assertEqual(payload["decision"], "ADOPT")
        self.assertEqual(payload["selected_arm"], "balanced-4-step")
        self.assertEqual(payload["numeric_precision_significant_digits"], 12)
        premium_reference = next(
            arm for arm in payload["arms"] if arm["arm_id"] == "premium-8-step"
        )
        self.assertEqual(premium_reference["mean_effective_cost_usd"], 1.665)
        self.assertIn("$1.67", render_frontier_markdown(first))
        self.assertIn("$5.94", render_frontier_markdown(first))


if __name__ == "__main__":
    unittest.main()
