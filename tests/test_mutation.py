"""
Harness mutation testing.

The primitive must work on any bundle and any check set, not only on the six
gates this package ships, or it is a demo rather than a tool.
"""
from __future__ import annotations

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agent_economics import default_checks, load_normalized_json_bundle
from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE
from agent_economics.cli import main
from agent_economics.models import Decision
from agent_economics.mutation import mutate, providers, render_markdown

ROOT = Path(__file__).resolve().parents[1]
ASSIST_BUNDLE = ROOT / "examples" / "claude-code" / "bundle.json"
SCALE_BUNDLE = ROOT / "examples" / "compute-frontier" / "arms" / "balanced-4-step.json"


def _bundle(path: Path):
    return load_normalized_json_bundle(path)


class ProvidersTest(unittest.TestCase):
    def test_every_required_dimension_has_a_provider(self) -> None:
        by_coverage = providers(tuple(default_checks()), DEFAULT_REQUIRED_COVERAGE)
        for coverage, ids in by_coverage.items():
            with self.subTest(coverage=coverage.value):
                self.assertTrue(ids, f"{coverage.value} has no provider")

    def test_every_default_gate_is_a_sole_provider(self) -> None:
        """If two checks covered one dimension, removing one would prove nothing."""
        by_coverage = providers(tuple(default_checks()), DEFAULT_REQUIRED_COVERAGE)
        for coverage, ids in by_coverage.items():
            with self.subTest(coverage=coverage.value):
                self.assertEqual(len(ids), 1, ids)


class MutationOnRealTraceTest(unittest.TestCase):
    """A real Claude Code session: ASSIST, with one gate carrying the verdict."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = mutate(_bundle(ASSIST_BUNDLE))

    def test_one_mutation_per_required_dimension(self) -> None:
        self.assertEqual(self.report.total, len(DEFAULT_REQUIRED_COVERAGE))
        self.assertEqual(self.report.unprovided_coverage, ())

    def test_fixed_contract_kills_every_mutation(self) -> None:
        self.assertEqual(self.report.fixed_contract_score, 1.0)
        for m in self.report.mutations:
            with self.subTest(coverage=m.coverage):
                self.assertEqual(m.fixed_contract_decision, Decision.INCOMPLETE.value)

    def test_removing_outcome_quality_produces_a_false_scale(self) -> None:
        """The whole argument, on real data: ASSIST becomes SCALE."""
        self.assertEqual(self.report.baseline_decision, Decision.ASSIST.value)
        flips = {m.coverage for m in self.report.flips}
        self.assertIn("outcome_quality", flips)

    def test_render_markdown_names_the_survivor(self) -> None:
        rendered = render_markdown(self.report)
        self.assertIn("outcome_quality", rendered)
        self.assertIn("survives", rendered)


class MutationOnPassingBundleTest(unittest.TestCase):
    """A SCALE baseline cannot produce a false transition, and must not claim one."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = mutate(_bundle(SCALE_BUNDLE))

    def test_baseline_is_scale(self) -> None:
        self.assertEqual(self.report.baseline_decision, Decision.SCALE.value)

    def test_no_false_transitions_are_reported(self) -> None:
        self.assertEqual(self.report.flips, ())

    def test_fixed_contract_still_refuses_every_removal(self) -> None:
        self.assertEqual(self.report.fixed_contract_score, 1.0)


class CustomCheckSetTest(unittest.TestCase):
    """The primitive must not be welded to the shipped gates."""

    def test_a_dimension_with_no_provider_is_reported_not_scored(self) -> None:
        reduced = tuple(c for c in default_checks() if c.id != "gate.tail-cost")
        report = mutate(_bundle(ASSIST_BUNDLE), reduced)
        self.assertIn("tail_risk", report.unprovided_coverage)
        self.assertEqual(report.total, len(DEFAULT_REQUIRED_COVERAGE) - 1)

    def test_narrowing_required_coverage_narrows_the_mutation_set(self) -> None:
        from agent_economics.models import Coverage

        required = frozenset({Coverage.OUTCOME_QUALITY, Coverage.UNIT_ECONOMICS})
        report = mutate(_bundle(ASSIST_BUNDLE), tuple(default_checks()), required)
        self.assertEqual(report.total, 2)
        self.assertEqual(
            {m.coverage for m in report.mutations},
            {"outcome_quality", "unit_economics"},
        )


class MutateCliTest(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        out = StringIO()
        with redirect_stdout(out), redirect_stderr(StringIO()):
            code = main(argv)
        return code, out.getvalue()

    def test_markdown_output(self) -> None:
        code, text = self._run(["mutate", "--bundle", str(ASSIST_BUNDLE)])
        self.assertEqual(code, 0)
        self.assertIn("Harness Mutation Score", text)

    def test_json_output_is_machine_readable(self) -> None:
        code, text = self._run(
            ["mutate", "--bundle", str(ASSIST_BUNDLE), "--format", "json"]
        )
        self.assertEqual(code, 0)
        payload = json.loads(text)
        self.assertEqual(payload["fixed_contract_score"], 1.0)
        self.assertEqual(payload["mutations_injected"], len(DEFAULT_REQUIRED_COVERAGE))

    def test_ci_passes_when_every_gate_is_load_bearing(self) -> None:
        """--ci gates on the fixed contract, not on the dynamic-coverage column."""
        for bundle in (ASSIST_BUNDLE, SCALE_BUNDLE):
            with self.subTest(bundle=bundle.name):
                code, _ = self._run(["mutate", "--bundle", str(bundle), "--ci"])
                self.assertEqual(code, 0)

    def test_missing_bundle_fails_closed(self) -> None:
        code, _ = self._run(["mutate", "--bundle", "/nonexistent.json"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()


class CustomCoverageDimensionTest(unittest.TestCase):
    """
    The README claims mutate() works on checks you wrote. It did not: Coverage
    is a closed enum of six economic dimensions and a plain string crashed with
    AttributeError deep in the contract digest. An adversarial audit caught the
    claim being false. These tests are what make it true.

    This is the adoption path. A team with a PII gate, a jailbreak gate, or a
    regression eval must be able to ask which of their checks are load-bearing
    without adopting an economic contract first.
    """

    @staticmethod
    def _gate(check_id: str, coverage: str):
        from agent_economics.models import (
            CheckMode,
            CheckOutput,
            CheckResult,
            CheckSpec,
            CheckStatus,
        )

        def run(_view):
            return CheckOutput(
                results=(
                    CheckResult(
                        check_id=check_id, status=CheckStatus.PASS, message="ok"
                    ),
                )
            )

        return CheckSpec(
            id=check_id,
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({coverage}),
            run=run,
            failure_route=Decision.STOP,
        )

    def test_a_string_dimension_is_mutation_tested(self) -> None:
        custom = self._gate("gate.pii", "pii_safety")
        report = mutate(
            _bundle(ASSIST_BUNDLE),
            tuple(default_checks()) + (custom,),
            frozenset({"pii_safety"}),
        )
        self.assertEqual(report.total, 1)
        self.assertEqual(report.mutations[0].coverage, "pii_safety")
        self.assertEqual(report.mutations[0].removed_check_ids, ("gate.pii",))
        self.assertEqual(report.fixed_contract_score, 1.0)

    def test_custom_and_builtin_dimensions_mix(self) -> None:
        from agent_economics.models import Coverage

        custom = self._gate("gate.jailbreak", "jailbreak_safety")
        report = mutate(
            _bundle(ASSIST_BUNDLE),
            tuple(default_checks()) + (custom,),
            frozenset({"jailbreak_safety", Coverage.OUTCOME_QUALITY}),
        )
        self.assertEqual(
            {m.coverage for m in report.mutations},
            {"jailbreak_safety", "outcome_quality"},
        )
        self.assertEqual(report.fixed_contract_score, 1.0)

    def test_a_custom_dimension_with_no_provider_is_reported(self) -> None:
        report = mutate(
            _bundle(ASSIST_BUNDLE), tuple(default_checks()), frozenset({"pii_safety"})
        )
        self.assertEqual(report.unprovided_coverage, ("pii_safety",))
        self.assertEqual(report.total, 0)

    def test_two_checks_covering_one_dimension_are_removed_together(self) -> None:
        """Neither is a sole provider, so removing one proves nothing."""
        a = self._gate("gate.pii-a", "pii_safety")
        b = self._gate("gate.pii-b", "pii_safety")
        report = mutate(
            _bundle(ASSIST_BUNDLE),
            tuple(default_checks()) + (a, b),
            frozenset({"pii_safety"}),
        )
        self.assertEqual(
            report.mutations[0].removed_check_ids, ("gate.pii-a", "gate.pii-b")
        )


class ContractDigestStabilityTest(unittest.TestCase):
    """Opening Coverage to strings must not move any committed digest."""

    def test_default_contract_digest_is_unchanged(self) -> None:
        from agent_economics import decision_contract_digest
        from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE

        digest = decision_contract_digest(
            tuple(default_checks()), DEFAULT_REQUIRED_COVERAGE
        )
        self.assertEqual(
            digest,
            "f30996d535c1722fddb2e767bc830c9d2cb34054b864481e1220d459121e3e1a",
        )
