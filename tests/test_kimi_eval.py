"""Tests for the judge eval: the scoring math and the eval set's integrity.

Runs with no network. The live judge is exercised by `make kimi-eval`; what is
tested here is everything that would make a live score meaningless: broken metric
arithmetic, an unbalanced or self-contradictory eval set, or expected labels that
do not follow from the rubric they claim to follow from.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import ClassVar

import kimi_eval

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = json.loads((ROOT / "examples/kimi-judge/rubric.json").read_text())


class EvalSetIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = kimi_eval.load_eval_set()
        cls.cases = cls.document["cases"]

    def test_case_count_is_enough_to_measure_anything(self) -> None:
        self.assertGreaterEqual(len(self.cases), 20)
        self.assertEqual(len(self.cases), self.document["case_count"])

    def test_ids_are_unique(self) -> None:
        ids = [case["task_id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_declared_class_counts_match_the_cases(self) -> None:
        acceptable = sum(1 for c in self.cases if c["expected_acceptable"])
        self.assertEqual(acceptable, self.document["acceptable_cases"])
        self.assertEqual(
            len(self.cases) - acceptable, self.document["unacceptable_cases"]
        )

    def test_both_classes_are_represented_substantially(self) -> None:
        """A single-class set would make agreement meaningless."""
        acceptable = sum(1 for c in self.cases if c["expected_acceptable"])
        self.assertGreaterEqual(acceptable, 5)
        self.assertGreaterEqual(len(self.cases) - acceptable, 5)

    def test_every_case_is_well_formed(self) -> None:
        for case in self.cases:
            with self.subTest(task_id=case.get("task_id")):
                for field in (
                    "task_id",
                    "category",
                    "expected_acceptable",
                    "context",
                    "output",
                ):
                    self.assertIn(field, case)
                self.assertIsInstance(case["expected_acceptable"], bool)
                self.assertGreater(len(case["output"].strip()), 20)
                self.assertGreater(len(case["context"].strip()), 10)

    def test_failure_modes_are_covered_by_category(self) -> None:
        categories = {case["category"] for case in self.cases}
        for required in (
            "correct",
            "factually-wrong",
            "hallucinated-feature",
            "contradicts-context",
            "non-answer",
            "policy-breach",
        ):
            with self.subTest(category=required):
                self.assertIn(required, categories)

    def test_every_category_holds_one_label_consistently(self) -> None:
        """A category mixing both labels would hide which behaviour failed."""
        by_category: dict[str, set[bool]] = {}
        for case in self.cases:
            by_category.setdefault(case["category"], set()).add(
                bool(case["expected_acceptable"])
            )
        for category, labels in by_category.items():
            with self.subTest(category=category):
                self.assertEqual(len(labels), 1, "category has mixed expected labels")

    def test_claim_boundary_is_stated(self) -> None:
        boundary = self.document["claim_boundary"].lower()
        self.assertIn("not a measure of judge accuracy", boundary)
        self.assertIn("agreement", boundary)
        self.assertIn("label_basis", self.document)

    def test_label_basis_follows_from_the_actual_rubric_weights(self) -> None:
        """The stated justification must be arithmetically true of this rubric.

        The eval set claims a correct-but-curt answer still clears while a
        factually wrong answer cannot. Both are consequences of the weights, so
        they are checkable rather than a matter of taste.
        """
        weights = {c["id"]: c["weight"] for c in RUBRIC["criteria"]}
        threshold = RUBRIC["acceptable_threshold"]
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

        # Perfect accuracy and policy, zero tone: a curt correct answer.
        curt = weights["accuracy"] + weights["policy"]
        self.assertGreaterEqual(
            curt, threshold, "tone alone should not sink a correct answer"
        )
        # Perfect policy and tone, zero accuracy: a wrong but polite answer.
        wrong = weights["policy"] + weights["tone"]
        self.assertLess(
            wrong, threshold, "a factually wrong answer must not be able to clear"
        )
        self.assertTrue(
            any(c["category"] == "correct-but-curt" for c in self.cases)
        )

    def test_rubric_reference_resolves(self) -> None:
        self.assertTrue((ROOT / self.document["rubric"]).exists())
        self.assertEqual(self.document["rubric_id"], RUBRIC["rubric_id"])


class ScoringTests(unittest.TestCase):
    CASES: ClassVar[list[dict]] = [
        {"task_id": "a", "category": "correct", "expected_acceptable": True},
        {"task_id": "b", "category": "correct", "expected_acceptable": True},
        {"task_id": "c", "category": "wrong", "expected_acceptable": False},
        {"task_id": "d", "category": "wrong", "expected_acceptable": False},
    ]

    def test_perfect_agreement(self) -> None:
        metrics = kimi_eval.score(
            self.CASES, {"a": True, "b": True, "c": False, "d": False}
        )
        self.assertEqual(metrics.agreement_rate, 1.0)
        self.assertEqual(metrics.precision, 1.0)
        self.assertEqual(metrics.recall, 1.0)
        self.assertEqual(metrics.f1, 1.0)
        self.assertEqual(metrics.negative_recall, 1.0)
        self.assertEqual(metrics.false_accept_rate, 0.0)

    def test_accept_everything_is_caught_as_a_false_accept_problem(self) -> None:
        """The dangerous judge: it inflates acceptable_rate and can flip a STOP."""
        metrics = kimi_eval.score(
            self.CASES, {"a": True, "b": True, "c": True, "d": True}
        )
        self.assertEqual(metrics.recall, 1.0)
        self.assertEqual(metrics.precision, 0.5)
        self.assertEqual(metrics.negative_recall, 0.0)
        self.assertEqual(metrics.false_accept_rate, 1.0)
        self.assertEqual(metrics.agreement_rate, 0.5)

    def test_reject_everything(self) -> None:
        metrics = kimi_eval.score(
            self.CASES, {"a": False, "b": False, "c": False, "d": False}
        )
        self.assertEqual(metrics.recall, 0.0)
        self.assertEqual(metrics.precision, 0.0)
        self.assertEqual(metrics.f1, 0.0)
        self.assertEqual(metrics.negative_recall, 1.0)
        self.assertEqual(metrics.false_accept_rate, 0.0)

    def test_confusion_matrix_accounts_for_every_scored_case(self) -> None:
        metrics = kimi_eval.score(
            self.CASES, {"a": True, "b": False, "c": True, "d": False}
        )
        self.assertEqual(metrics.true_positive, 1)
        self.assertEqual(metrics.false_negative, 1)
        self.assertEqual(metrics.false_positive, 1)
        self.assertEqual(metrics.true_negative, 1)
        self.assertEqual(
            metrics.true_positive
            + metrics.false_negative
            + metrics.false_positive
            + metrics.true_negative,
            metrics.scored,
        )

    def test_errors_are_excluded_rather_than_scored_as_rejections(self) -> None:
        """An outage must not be reported as strictness."""
        metrics = kimi_eval.score(
            self.CASES, {"a": True, "b": None, "c": False, "d": None}
        )
        self.assertEqual(metrics.errors, 2)
        self.assertEqual(metrics.scored, 2)
        self.assertEqual(metrics.agreement_rate, 1.0)
        self.assertEqual(metrics.total, 4)

    def test_missing_prediction_counts_as_an_error(self) -> None:
        metrics = kimi_eval.score(self.CASES, {"a": True})
        self.assertEqual(metrics.errors, 3)
        self.assertEqual(metrics.scored, 1)

    def test_empty_predictions_do_not_divide_by_zero(self) -> None:
        metrics = kimi_eval.score(self.CASES, {})
        for value in (
            metrics.agreement_rate,
            metrics.precision,
            metrics.recall,
            metrics.f1,
            metrics.negative_recall,
            metrics.false_accept_rate,
        ):
            self.assertEqual(value, 0.0)


class BreakdownTests(unittest.TestCase):
    def test_category_breakdown_totals_match(self) -> None:
        document = kimi_eval.load_eval_set()
        cases = document["cases"]
        predictions = {c["task_id"]: c["expected_acceptable"] for c in cases}
        buckets = kimi_eval.by_category(cases, predictions)
        self.assertEqual(sum(b["cases"] for b in buckets.values()), len(cases))
        self.assertEqual(sum(b["agreed"] for b in buckets.values()), len(cases))
        self.assertEqual(sum(b["errors"] for b in buckets.values()), 0)

    def test_disagreements_are_listed_with_direction(self) -> None:
        document = kimi_eval.load_eval_set()
        cases = document["cases"]
        predictions = {c["task_id"]: True for c in cases}
        rows = kimi_eval.disagreements(cases, predictions)
        self.assertEqual(len(rows), document["unacceptable_cases"])
        self.assertTrue(all(row["kind"] == "false accept" for row in rows))

    def test_no_disagreements_on_a_perfect_run(self) -> None:
        document = kimi_eval.load_eval_set()
        cases = document["cases"]
        predictions = {c["task_id"]: c["expected_acceptable"] for c in cases}
        self.assertEqual(kimi_eval.disagreements(cases, predictions), [])


class ReportTests(unittest.TestCase):
    def test_report_surfaces_the_dangerous_metric_and_the_boundary(self) -> None:
        document = kimi_eval.load_eval_set()
        predictions = {c["task_id"]: True for c in document["cases"]}
        report = kimi_eval.render_report(
            document, predictions, model="kimi-k3", reasoning_effort="max"
        )
        self.assertIn("false-accept rate", report)
        self.assertIn("100.0%", report)
        self.assertIn("CONFUSION MATRIX", report)
        self.assertIn("not a measure of judge accuracy", report)

    def test_scoring_a_saved_run_needs_no_network(self) -> None:
        import tempfile

        document = kimi_eval.load_eval_set()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.json"
            path.write_text(
                json.dumps(
                    {c["task_id"]: c["expected_acceptable"] for c in document["cases"]}
                )
            )
            code = kimi_eval.main(
                ["--predictions", str(path), "--min-agreement", "0.9"]
            )
        self.assertEqual(code, 0)

    def test_min_agreement_gate_fails_a_bad_run(self) -> None:
        import tempfile

        document = kimi_eval.load_eval_set()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predictions.json"
            path.write_text(
                json.dumps({c["task_id"]: True for c in document["cases"]})
            )
            code = kimi_eval.main(
                ["--predictions", str(path), "--min-agreement", "0.9"]
            )
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()


class EvalVersioningTests(unittest.TestCase):
    """A revised eval set must say what changed and why, and keep the old number.

    Silently editing a case after seeing a model's answers is how an eval stops
    measuring anything. The record has to be auditable.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = kimi_eval.load_eval_set()

    def test_revisions_state_a_reason_and_the_method_rule(self) -> None:
        """A revised case must record why, and the rule that governs revising."""
        for revision in self.document.get("revisions", []):
            with self.subTest(case=revision.get("case")):
                self.assertIn("reason", revision)
                self.assertIn("method_note", revision)
                self.assertGreater(len(revision["reason"]), 80)
                self.assertIn("overfit", " ".join(
                    r["method_note"] for r in self.document["revisions"]
                ).lower())

    def test_measured_runs_are_pinned_to_the_version_they_ran_on(self) -> None:
        """Every result must name the version it measured.

        The risk is a score from an older set being carried forward after cases
        change. A run against the current version is legitimate; a run against an
        older one must say so, and a full run must report the metric that matters.
        """
        current = self.document["eval_version"]
        for run in self.document.get("measured_runs", []):
            version = run.get("eval_version")
            with self.subTest(version=version):
                self.assertIn("eval_version", run)
                self.assertIn("judge", run)
                if "cases_run" not in run:
                    self.assertIn("false_accept_rate", run)
                if version != current:
                    self.assertIn(
                        "note",
                        run,
                        "a historical run must explain which set it measured",
                    )

    def test_a_perfect_current_score_carries_its_caveats(self) -> None:
        """A 100% agreement claim needs its limits attached, or it misleads.

        This set was partly restructured after observing the judge under test, and
        two verdicts sit hundredths from the threshold. Either fact alone makes an
        unqualified perfect score an overstatement.
        """
        current = self.document["eval_version"]
        for run in self.document.get("measured_runs", []):
            if run.get("eval_version") != current:
                continue
            if run.get("agreement_rate", 0.0) < 1.0:
                continue
            with self.subTest(version=current):
                caveats = run.get("caveats", [])
                self.assertGreaterEqual(
                    len(caveats), 3, "a perfect score needs its limits stated"
                )
                joined = " ".join(caveats).lower()
                self.assertIn("held-out", joined)
                self.assertIn("threshold", joined)

    def test_revised_case_no_longer_volunteers_an_out_of_scope_commitment(self) -> None:
        case = next(c for c in self.document["cases"] if c["task_id"] == "ok-06")
        for phrase in ("backup", "retention", "purged"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, case["output"].lower())
        self.assertTrue(case["expected_acceptable"])
