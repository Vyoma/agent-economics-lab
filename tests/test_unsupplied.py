"""
Evidence bundles that carry no economics.

Two adversarial audits reached the same conclusion: the one portable idea in
this package was locked behind an economic contract almost nobody has. To run
the conformance primitive on a PII gate you first had to invent a price per
million tokens and a named baseline, which is the fabrication this package
exists to prevent.

An unsupplied input is not zero and not a default. It raises when read. Combined
with the engine failing closed on a check that cannot run, an economic gate
added to a non-economic harness yields INCOMPLETE rather than pricing the
traffic at nothing.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from agent_economics import default_checks, evaluate_bundle, make_evidence_bundle
from agent_economics.assurance import AssuranceEngine
from agent_economics.models import (
    Baseline,
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Decision,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
)
from agent_economics.mutation import mutate
from agent_economics.unsupplied import (
    UnsuppliedEvidence,
    checks_only_bundle,
    unsupplied_policy,
)

ROOT = Path(__file__).resolve().parents[1]


def _events(n: int = 3) -> tuple[TraceEvent, ...]:
    return tuple(
        TraceEvent(
            task_id=f"t{i}",
            event_id=f"e{i}",
            timestamp=f"2026-08-26T00:00:0{i}Z",
            event_type="model",
            name="call",
            model="m",
            direct_cost_usd=0.0,
        )
        for i in range(n)
    )


def _outcomes(n: int = 3, acceptable=lambda i: True) -> dict[str, Outcome]:
    return {f"t{i}": Outcome(task_id=f"t{i}", acceptable=acceptable(i)) for i in range(n)}


def _gate(check_id: str, coverage: str, status: CheckStatus, route=Decision.STOP):
    def run(_view):
        return CheckOutput(
            results=(
                CheckResult(
                    check_id=check_id,
                    status=status,
                    message="synthetic",
                    on_failure=route if status is CheckStatus.FAIL else None,
                ),
            )
        )

    return CheckSpec(
        id=check_id,
        version="1",
        mode=CheckMode.GATE,
        covers=frozenset({coverage}),
        run=run,
        failure_route=route,
    )


class UnsuppliedRefusesToBeReadTest(unittest.TestCase):
    def test_reading_an_unsupplied_input_raises_rather_than_defaulting(self) -> None:
        policy = unsupplied_policy()
        with self.assertRaises(UnsuppliedEvidence):
            _ = policy.min_acceptable_rate

    def test_it_is_not_falsy_or_empty_or_zero(self) -> None:
        """A sentinel that quietly compares equal to something is the bug."""
        policy = unsupplied_policy()
        for attempt in (lambda: bool(policy), lambda: len(policy), lambda: list(policy)):
            with self.subTest(), self.assertRaises(UnsuppliedEvidence):
                attempt()


class ChecksOnlyBundleTest(unittest.TestCase):
    def test_a_bundle_can_be_built_with_no_economics(self) -> None:
        bundle = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )
        self.assertEqual(len(bundle.events), 3)
        self.assertTrue(bundle.digest)

    def test_its_digest_differs_from_an_economically_complete_bundle(self) -> None:
        """Declared absence must be visible in the tamper-evident digest."""
        absent = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )
        supplied = make_evidence_bundle(
            events=_events(),
            outcomes=_outcomes(),
            rates={"m": ModelRate(input_per_million_usd=1.0, output_per_million_usd=2.0)},
            baseline=Baseline(
                name="human",
                acceptable_rate=0.5,
                cost_per_attempt_usd=1.0,
                value_per_acceptable_outcome_usd=10.0,
            ),
            policy=EconomicPolicy(
                min_acceptable_rate=0.8,
                max_cost_per_acceptable_outcome_usd=1.0,
                max_p95_task_cost_usd=1.0,
                max_trace_cost_per_task_usd=1.0,
                max_calls_per_task=10,
                human_hourly_cost_usd=50.0,
                min_expected_net_value_per_attempt_usd=1.0,
                min_incremental_net_value_vs_baseline_usd=0.5,
                repetition_warning_threshold=3,
            ),
            source_id="source.my-eval",
        )
        self.assertNotEqual(absent.digest, supplied.digest)


class NonEconomicHarnessTest(unittest.TestCase):
    """The adoption path: safety gates, no rate card, no baseline, no policy."""

    def setUp(self) -> None:
        self.bundle = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )
        self.pii = _gate("gate.pii", "pii_safety", CheckStatus.PASS)
        self.jailbreak = _gate("gate.jailbreak", "jailbreak_safety", CheckStatus.FAIL)

    def test_a_passing_safety_harness_reaches_a_real_verdict(self) -> None:
        report = mutate(self.bundle, (self.pii,), frozenset({"pii_safety"}))
        self.assertEqual(report.baseline_decision, Decision.SCALE.value)

    def test_a_failing_safety_gate_routes_to_stop(self) -> None:
        report = mutate(
            self.bundle,
            (self.pii, self.jailbreak),
            frozenset({"pii_safety", "jailbreak_safety"}),
        )
        self.assertEqual(report.baseline_decision, Decision.STOP.value)

    def test_removing_the_failing_gate_is_a_false_green_under_dynamic_coverage(self) -> None:
        """The thesis, on a safety harness with no economics at all."""
        report = mutate(
            self.bundle,
            (self.pii, self.jailbreak),
            frozenset({"pii_safety", "jailbreak_safety"}),
        )
        flips = {m.coverage for m in report.flips}
        self.assertEqual(flips, {"jailbreak_safety"})
        for m in report.mutations:
            with self.subTest(coverage=m.coverage):
                self.assertEqual(m.fixed_contract_decision, Decision.INCOMPLETE.value)


class EconomicGateWithoutEconomicsTest(unittest.TestCase):
    """The property that makes declared absence safe rather than convenient."""

    def test_it_does_not_pass_by_comparing_favourably(self) -> None:
        """
        A zero cost would satisfy every ceiling, so this must not compare at all.

        Scoped to each gate's own coverage. Evaluating one gate against the full
        default contract returns INCOMPLETE from missing coverage without ever
        entering the check loop, which is what an earlier version of this test
        did: it asserted the right answer for the wrong reason.
        """
        bundle = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )
        for check in default_checks():
            if check.mode is not CheckMode.GATE:
                continue
            with self.subTest(check=check.id):
                case = AssuranceEngine(
                    checks=(check,), required_coverage=frozenset(check.covers)
                ).evaluate(bundle)
                self.assertEqual(case.missing_coverage, ())
                self.assertIs(case.decision, Decision.INCOMPLETE)

    def test_a_custom_cost_gate_cannot_total_unsupplied_costs(self) -> None:
        """
        math.fsum over unsupplied costs used to yield nan, and `nan > limit` is
        False, so a gate passed on $3000 of real spend. It is the idiom this
        engine itself uses, so a custom gate is likely to copy it.
        """
        import math

        bundle = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )

        def total_cost(view):
            total = math.fsum(t.effective_cost_usd for t in view.tasks)
            return CheckOutput(
                results=(
                    CheckResult(
                        check_id="gate.my-cost",
                        status=CheckStatus.FAIL if total > 100.0 else CheckStatus.PASS,
                        message=f"total ${total} vs $100.00",
                        on_failure=Decision.STOP if total > 100.0 else None,
                    ),
                )
            )

        gate = CheckSpec(
            id="gate.my-cost",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({"my_unit_economics"}),
            run=total_cost,
            failure_route=Decision.STOP,
        )
        case = AssuranceEngine(
            checks=(gate,), required_coverage=frozenset({"my_unit_economics"})
        ).evaluate(bundle)
        self.assertIs(case.decision, Decision.INCOMPLETE)


class UnrunnableCheckFailsClosedTest(unittest.TestCase):
    """Previously a raising check crashed the engine instead of yielding a verdict."""

    def test_a_raising_check_yields_incomplete_not_an_exception(self) -> None:
        bundle = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )

        def boom(_view):
            raise KeyError("evidence never collected")

        broken = CheckSpec(
            id="gate.broken",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({"pii_safety"}),
            run=boom,
            failure_route=Decision.STOP,
        )
        case = evaluate_bundle(bundle, (broken,))
        self.assertIs(case.decision, Decision.INCOMPLETE)

    def test_a_second_provider_keeps_the_dimension_covered(self) -> None:
        """Only when ALL providers fail is the dimension unmet."""
        bundle = checks_only_bundle(
            events=_events(), outcomes=_outcomes(), source_id="source.my-eval"
        )

        def boom(_view):
            raise KeyError("evidence never collected")

        broken = CheckSpec(
            id="gate.broken",
            version="1",
            mode=CheckMode.GATE,
            covers=frozenset({"pii_safety"}),
            run=boom,
            failure_route=Decision.STOP,
        )
        working = _gate("gate.pii", "pii_safety", CheckStatus.PASS)
        from agent_economics.assurance import AssuranceEngine

        case = AssuranceEngine(
            checks=(broken, working), required_coverage=frozenset({"pii_safety"})
        ).evaluate(bundle)
        self.assertIsNot(case.decision, Decision.INCOMPLETE)


if __name__ == "__main__":
    unittest.main()


class CrashingCheckRoutingTest(unittest.TestCase):
    """
    An audit found two ways a crashed check produced a green verdict.

    A diagnostic that listed a required dimension in `covers` counted as a
    surviving provider, so a crashed sole gate read as covered. And a crashing
    gate outside the required set was swallowed entirely, so a harder failure
    bought a softer verdict than the same gate returning FAIL.
    """

    def setUp(self) -> None:
        from agent_economics import load_normalized_json_bundle

        self.bundle = load_normalized_json_bundle(
            ROOT / "examples" / "otel-genai" / "langfuse-bundle.json"
        )

    @staticmethod
    def _boom(_view):
        raise RuntimeError("rubric scorer returned 503")

    def test_a_diagnostic_is_not_a_surviving_provider(self) -> None:
        from agent_economics.assurance import AssuranceEngine
        from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE
        from agent_economics.models import Coverage

        others = tuple(c for c in default_checks() if c.id != "gate.acceptable-rate")
        crashed = CheckSpec(
            id="gate.acceptable-rate", version="1", mode=CheckMode.GATE,
            covers=frozenset({Coverage.OUTCOME_QUALITY}), run=self._boom,
            failure_route=Decision.ASSIST,
        )
        diagnostic = CheckSpec(
            id="diagnostic.claims-coverage", version="1", mode=CheckMode.DIAGNOSTIC,
            covers=frozenset({Coverage.OUTCOME_QUALITY}), run=lambda _v: CheckOutput(),
        )
        case = AssuranceEngine(
            checks=others + (crashed, diagnostic),
            required_coverage=DEFAULT_REQUIRED_COVERAGE,
        ).evaluate(self.bundle)
        self.assertIs(case.decision, Decision.INCOMPLETE)

    def test_a_crashing_gate_outside_required_coverage_still_routes(self) -> None:
        """A crash must never be weaker than the same gate returning FAIL."""
        from agent_economics.assurance import AssuranceEngine
        from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE

        outside = CheckSpec(
            id="gate.pii", version="1", mode=CheckMode.GATE, covers=frozenset(),
            run=self._boom, failure_route=Decision.STOP,
        )
        case = AssuranceEngine(
            checks=tuple(default_checks()) + (outside,),
            required_coverage=DEFAULT_REQUIRED_COVERAGE,
        ).evaluate(self.bundle)
        self.assertIs(case.decision, Decision.STOP)

    def test_a_crashing_diagnostic_yields_a_finding_not_a_fail_result(self) -> None:
        """The engine's own validator rejects a FAIL from a diagnostic."""
        from agent_economics.assurance import AssuranceEngine
        from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE

        crashy = CheckSpec(
            id="diagnostic.crashy", version="1", mode=CheckMode.DIAGNOSTIC,
            covers=frozenset(), run=self._boom,
        )
        case = AssuranceEngine(
            checks=tuple(default_checks()) + (crashy,),
            required_coverage=DEFAULT_REQUIRED_COVERAGE,
        ).evaluate(self.bundle)
        self.assertNotIn(
            "diagnostic.crashy", {r.check_id for r in case.check_results}
        )
        self.assertIn("diagnostic.crashy", {f.control for f in case.findings})
