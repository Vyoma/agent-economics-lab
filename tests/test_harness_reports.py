"""Conformance tests for the three harness-analysis executables.

These were unreferenced scripts until they were wired into `make reproduce`.
They are held to the same standard as every other published artifact: the
checked-in output must be byte-reproducible, and the claims each script makes
about the harness must be asserted rather than printed.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

import completion_vs_verdict
import mutation_score
import sensitivity_sweep
from agent_economics import (
    Decision,
    default_checks,
    default_engine,
    evaluate_bundle,
    load_csv_bundle,
)
from agent_economics.report import render_markdown
from false_green import build_evidence, scenario_matrix

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research/results"


class MutationScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = mutation_score.run_mutations()
        cls.summary = mutation_score.summarize(cls.rows)

    def test_checked_in_artifacts_are_byte_reproducible(self) -> None:
        directory = RESULTS / "mutation-score"
        with self.subTest(name="summary.md"):
            self.assertEqual(
                mutation_score.render_summary(self.summary),
                (directory / "summary.md").read_text(encoding="utf-8"),
            )
        with self.subTest(name="summary.json"):
            self.assertEqual(
                mutation_score.render_summary_json(self.summary),
                (directory / "summary.json").read_text(encoding="utf-8"),
            )

    def test_equivalent_mutants_are_excluded_from_the_denominator(self) -> None:
        """A mutation of an already-SCALE verdict cannot be credited as a kill."""
        self.assertGreater(self.summary["equivalent_mutants_excluded"], 0)
        operators = self.summary["operators"]
        assert isinstance(operators, dict)
        for operator, stats in operators.items():
            with self.subTest(operator=operator):
                self.assertLess(
                    stats["scored_mutants"],
                    stats["mutants"],
                    "scored mutants must exclude the equivalent ones",
                )
                for row in self.rows:
                    if row.equivalent:
                        self.assertFalse(row.fixed_survived)
                        self.assertFalse(row.dynamic_survived)

    def test_removal_detection_is_forced_and_labelled_as_such(self) -> None:
        """Removal is detected by construction, so it must not be sold as a result."""
        operators = self.summary["operators"]
        assert isinstance(operators, dict)
        removal = operators[mutation_score.REMOVAL]
        self.assertEqual(removal["fixed_contract_score"], 1.0)
        self.assertTrue(removal["detected_by_coverage_contract_by_construction"])
        rendered = mutation_score.render_summary(self.summary)
        self.assertIn("forced", rendered)
        self.assertNotIn("PERFECT", rendered)

    def test_substitution_survives_both_engines_equally(self) -> None:
        """The headline claim: a fixed contract is no better against substitution."""
        operators = self.summary["operators"]
        assert isinstance(operators, dict)
        substitution = operators[mutation_score.SUBSTITUTION]
        self.assertFalse(
            substitution["detected_by_coverage_contract_by_construction"]
        )
        self.assertEqual(
            substitution["fixed_contract_survived"],
            substitution["dynamic_coverage_survived"],
        )
        self.assertGreater(substitution["fixed_contract_survived"], 0)
        self.assertLess(substitution["fixed_contract_score"], 1.0)

    def test_every_substitution_changes_the_contract_digest(self) -> None:
        """The fingerprint is the only thing that surfaces a permissive swap."""
        substitutions = [
            row for row in self.rows if row.operator == mutation_score.SUBSTITUTION
        ]
        self.assertTrue(substitutions)
        self.assertTrue(all(row.digest_changed for row in substitutions))

    def test_permissive_gate_leaves_required_coverage_satisfied(self) -> None:
        checks = default_checks()
        evidence = build_evidence(scenario_matrix()[0])
        for check_id in mutation_score.COVERAGE_BY_CHECK_ID:
            mutated = mutation_score._mutate(
                checks, mutation_score.SUBSTITUTION, check_id
            )
            case = default_engine(mutated).evaluate(evidence)
            with self.subTest(check_id=check_id):
                self.assertEqual(case.missing_coverage, ())
                self.assertIsNot(case.decision, Decision.INCOMPLETE)


class SensitivitySweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = sensitivity_sweep.summarize()

    def test_checked_in_artifacts_are_byte_reproducible(self) -> None:
        directory = RESULTS / "sensitivity"
        with self.subTest(name="summary.md"):
            self.assertEqual(
                sensitivity_sweep.render_summary(self.summary),
                (directory / "summary.md").read_text(encoding="utf-8"),
            )
        with self.subTest(name="summary.json"):
            self.assertEqual(
                sensitivity_sweep.render_summary_json(self.summary),
                (directory / "summary.json").read_text(encoding="utf-8"),
            )

    def test_identity_grid_cell_reproduces_the_unperturbed_verdict(self) -> None:
        """The grid must perturb one assumption, not swap the construction.

        The earlier implementation rebuilt evidence without
        `all_task_human_minutes`, so the cell that should have matched the
        unperturbed verdict did not, inflating flip counts.
        """
        for scenario in scenario_matrix():
            unperturbed = sensitivity_sweep._decision(scenario)
            identity = sensitivity_sweep._decision(
                scenario,
                incident_loss_usd=scenario.tail_loss_usd,
                remediation_cost_usd=0.0,
            )
            with self.subTest(scenario=scenario.id):
                self.assertIs(identity, unperturbed)

    def test_scenario_counts_partition_the_matrix(self) -> None:
        total = (
            self.summary["robust_scenarios"]
            + self.summary["fragile_scenarios"]
            + self.summary["brittle_scenarios"]
        )
        self.assertEqual(total, self.summary["scenarios"])
        self.assertEqual(self.summary["scenarios"], len(scenario_matrix()))

    def test_brittleness_is_reported_rather_than_suppressed(self) -> None:
        """The point of the sweep is that a real fraction is assumption-driven."""
        self.assertGreater(self.summary["brittle_scenarios"], 0)
        self.assertGreater(self.summary["brittle_rate"], 0.0)
        rendered = sensitivity_sweep.render_summary(self.summary)
        self.assertIn("BRITTLE", rendered)

    def test_baseline_fragility_covers_every_declared_perturbation(self) -> None:
        fragility = self.summary["baseline_fragility"]
        assert isinstance(fragility, dict)
        self.assertEqual(
            sorted(fragility),
            sorted(label for _, label in sensitivity_sweep.BASELINE_PERTURBATIONS),
        )
        self.assertTrue(any(count > 0 for count in fragility.values()))


class CompletionVsVerdictTests(unittest.TestCase):
    def test_checked_in_report_is_byte_reproducible(self) -> None:
        expected = (
            RESULTS / "completion-vs-verdict/report.txt"
        ).read_text(encoding="utf-8")
        self.assertEqual(completion_vs_verdict.render_report(), expected)

    def test_report_does_not_claim_the_fixture_is_a_real_session(self) -> None:
        """The Claude Code fixture is synthetic; the report must say so."""
        report = completion_vs_verdict.render_report()
        self.assertIn("Synthetic conformance fixture", report)
        self.assertNotIn("real trace", report.lower())

    def test_report_shows_the_gap_it_claims_to_show(self) -> None:
        report = completion_vs_verdict.render_report()
        self.assertIn("completion rate: 50%", report)
        self.assertIn("decision: ASSIST", report)


class HarnessSummaryJsonTests(unittest.TestCase):
    def test_pinned_json_summaries_parse_and_carry_claim_boundaries(self) -> None:
        for relative in (
            "mutation-score/summary.json",
            "sensitivity/summary.json",
        ):
            with self.subTest(path=relative):
                payload = json.loads(
                    (RESULTS / relative).read_text(encoding="utf-8")
                )
                self.assertIn("claim_boundary", payload)
                self.assertIn("synthetic", payload["claim_boundary"].lower())


if __name__ == "__main__":
    unittest.main()


class ReadmeAccuracyTests(unittest.TestCase):
    """The README must not drift from what the commands actually print.

    A recorded GIF previously showed a superseded claim-boundary sentence because
    an image cannot be re-verified when the code changes. These assertions apply
    the repository's own standard to its own front page.
    """

    @classmethod
    def setUpClass(cls) -> None:
        examples = ROOT / "examples"
        cls.demo_report = render_markdown(
            evaluate_bundle(
                load_csv_bundle(
                    traces=examples / "support_trace.csv",
                    outcomes=examples / "outcomes.csv",
                    rates=examples / "rates.json",
                    baseline=examples / "baseline.json",
                    policy=examples / "policy.json",
                )
            )
        )
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_quoted_demo_lines_appear_verbatim_in_real_output(self) -> None:
        for line in (
            "**Decision: ASSIST**",
            "| Attempts | 8 |",
            "| Acceptable outcomes | 6 (75.0%) |",
            "| Total effective cost | $21.02 |",
            "| Cost per acceptable outcome | $3.50 |",
            "| p95 effective task cost | $14.25 |",
            "| Maximum effective task cost | $14.25 |",
            "| Expected net value per attempt | $3.37 |",
            "- **FAIL · gate.acceptable-rate:** acceptable_rate 75.0% < 80.0%",
            "- **FAIL · gate.unit-economics:** cost_per_acceptable_outcome $3.50 > $2.00",
            "- **FAIL · gate.tail-cost:** p95_task_cost $14.25 > $8.00",
            "- **PASS · gate.net-value:** expected_net_value_per_attempt $3.37 >= $0.00",
            (
                "- **PASS · gate.counterfactual:** "
                "incremental_net_value_vs_baseline $2.77 >= $0.00"
            ),
            "- **FAIL · gate.runtime-caps:** t-005: 12 calls > cap of 8",
            (
                "- **FAIL · gate.runtime-caps:** t-005: $0.2454 trace cost > "
                "cap of $0.1500"
            ),
        ):
            with self.subTest(line=line):
                self.assertIn(line, self.readme, "line is not quoted in the README")
                self.assertIn(line, self.demo_report, "line is not what demo prints")

    def test_no_unverifiable_recorded_terminal_asset(self) -> None:
        """An image cannot be checked against the code, so it must not be cited."""
        self.assertFalse((ROOT / "assets/demo.gif").exists())
        for pattern in ("demo.gif", "assets/demo", ".mp4", ".webm", ".mov"):
            with self.subTest(pattern=pattern):
                self.assertNotIn(pattern, self.readme)

    def test_readme_eval_counts_match_the_eval_set(self) -> None:
        """The README must not quote a case count the eval set has outgrown.

        This drifted once: splitting a case took the set from 24 cases and seven
        categories to 25 and eight, and the README kept the old figures. The
        earlier README test only covered the demo output, so it passed while the
        page was wrong. Any number quoted from a generated artifact needs a
        binding assertion, not a nearby one.
        """
        document = json.loads(
            (ROOT / "research/eval/judge-eval-set.json").read_text(encoding="utf-8")
        )
        cases = document["case_count"]
        categories = len({case["category"] for case in document["cases"]})
        self.assertEqual(cases, len(document["cases"]))
        spelled = {7: "seven", 8: "eight", 9: "nine"}[categories]

        self.assertIn(f"{cases} labelled cases", self.readme)
        self.assertIn(f"{cases}\nconstructed cases across {spelled} categories",
                      self.readme)
        # And the superseded figures must be gone.
        for stale in (f"{cases - 1} labelled cases", f"{cases + 1} labelled cases"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.readme)

    def test_forced_stop_is_disclosed_as_forced(self) -> None:
        """A verdict no evidence could have avoided must not read as a finding.

        Every public SWE-bench outcome is credited zero business value while the
        net-value gate requires a non-negative result, so the routing is STOP for
        any labels at all. Presenting that as a comparison result would invite a
        reader to conclude the engine is rigged.
        """
        for name in ("README.md", "examples/public-swebench/README.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(doc=name):
                self.assertIn("forced", text.lower())
                self.assertIn("HOLD", text)

    def test_zero_value_really_does_force_the_stop(self) -> None:
        """Assert the arithmetic the disclosure describes, not just the prose."""
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, "examples/public-swebench/build_case.py",
                 "--source", "examples/public-swebench/runs.json",
                 "--output-dir", tmp],
                cwd=ROOT, check=True, capture_output=True,
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )
            bundle = json.loads(
                (Path(tmp) / "arms/candidate-opus.json").read_text(encoding="utf-8")
            )
        outcomes = bundle["outcomes"]
        rows = outcomes if isinstance(outcomes, list) else list(outcomes.values())
        self.assertEqual({row.get("business_value_usd", 0.0) for row in rows}, {0.0})
        self.assertGreaterEqual(
            bundle["policy"]["min_expected_net_value_per_attempt_usd"], 0.0,
            "with zero value credited, a non-negative threshold forces the STOP",
        )

    def test_headline_decision_matches_the_engine(self) -> None:
        self.assertIn("**Decision: ASSIST**", self.demo_report)
        self.assertIn("ASSIST", self.readme)


class TheKimiEvalSetCountsAreCurrent(unittest.TestCase):
    """These were 24/16/seven against an eval set holding 25/17/eight.

    They were unguarded, so the doc drifted when a category was added and the
    README's own guarded copy (25, eight) sat two files away contradicting it.
    """

    def test_the_integration_doc_matches_the_eval_set(self) -> None:
        import collections
        import json as _json

        root = Path(__file__).resolve().parents[1]
        cases = _json.loads(
            (root / "research" / "eval" / "judge-eval-set.json").read_text(
                encoding="utf-8"
            )
        )["cases"]
        acceptable = sum(1 for c in cases if c.get("expected_acceptable"))
        categories = sorted(collections.Counter(c["category"] for c in cases))
        doc = (root / "docs" / "kimi-integration.md").read_text(encoding="utf-8")

        self.assertIn(f"holds {len(cases)}\n", doc)
        self.assertIn(f"{acceptable} expected-acceptable", doc)
        self.assertIn(f"{len(cases) - acceptable} expected-unacceptable", doc)
        for category in categories:
            with self.subTest(category=category):
                self.assertIn(category, doc)
