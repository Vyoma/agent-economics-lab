"""SPEC.md, clause by clause, as executable assertions.

Each test names the clause it enforces. This file is the conformance
surface ROADMAP.md's first stage gate calls for: a second implementation
passing these tests against the same fixtures produces the same digests and
the same decisions. Overlap with the wider suite is deliberate — here the
organizing principle is the spec's numbering, so a clause with no test is
visible by grepping for its number.
"""

from __future__ import annotations

import unittest

from agent_economics.assurance import (
    ROUTING_SEMANTICS,
    AssuranceEngine,
    decision_contract_digest,
)
from agent_economics.audit import decide
from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from agent_economics.claim import Verdict, parse_claim, verify
from agent_economics.evidence import make_evidence_bundle
from agent_economics.models import (
    Baseline,
    CheckMode,
    Coverage,
    Decision,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
)
from agent_economics.provenance import (
    METHOD_FLOORS,
    RELIABILITY_ONLY_METHODS,
    Attestation,
    ProvenancePolicy,
    assess_provenance,
)

POLICY = EconomicPolicy(
    human_hourly_cost_usd=90.0,
    min_acceptable_rate=0.5,
    max_cost_per_acceptable_outcome_usd=10.0,
    max_p95_task_cost_usd=5.0,
    max_trace_cost_per_task_usd=5.0,
    max_calls_per_task=50,
)


def _bundle(**overrides):
    events = overrides.pop("events", (
        TraceEvent(task_id="t1", event_id="e1",
                   timestamp="2026-01-01T00:00:00Z", event_type="model",
                   name="completion", model="m", input_tokens=10,
                   output_tokens=5),
    ))
    keywords = dict(
        events=events,
        outcomes={"t1": Outcome(task_id="t1", acceptable=True,
                                business_value_usd=5.0, human_minutes=1.0)},
        rates={"m": ModelRate(3.0, 15.0)},
        baseline=Baseline("human", 5.0, 0.9, 8.0),
        policy=POLICY,
        source_id="test.conformance",
    )
    keywords.update(overrides)
    return make_evidence_bundle(**keywords)


class Clause1Decisions(unittest.TestCase):
    def test_1_1_the_four_decisions_name_equals_value(self) -> None:
        self.assertEqual(
            {d.name: d.value for d in Decision},
            {"INCOMPLETE": "INCOMPLETE", "SCALE": "SCALE",
             "ASSIST": "ASSIST", "STOP": "STOP"},
        )

    def test_1_2_exit_zero_is_reachable_only_by_scale(self) -> None:
        from agent_economics.cli import CI_EXIT_CODES

        self.assertEqual(
            CI_EXIT_CODES,
            {Decision.SCALE: 0, Decision.INCOMPLETE: 2,
             Decision.ASSIST: 3, Decision.STOP: 4},
        )

    def test_1_3_the_action_maps_unknown_codes_to_incomplete(self) -> None:
        from agent_economics.github_action import CI_DECISIONS

        self.assertEqual(CI_DECISIONS,
                         {0: "SCALE", 2: "INCOMPLETE", 3: "ASSIST", 4: "STOP"})
        self.assertNotIn(1, CI_DECISIONS)


class Clause2Coverage(unittest.TestCase):
    def test_2_1_six_core_dimensions_all_required_by_default(self) -> None:
        self.assertEqual(
            {c.value for c in Coverage},
            {"outcome_quality", "unit_economics", "tail_risk",
             "business_value", "counterfactual", "runtime_caps"},
        )
        self.assertEqual(DEFAULT_REQUIRED_COVERAGE, frozenset(Coverage))

    def test_2_3_a_diagnostic_with_a_failure_route_is_rejected(self) -> None:
        import dataclasses

        checks = default_checks()
        diagnostic = next(c for c in checks if c.mode is CheckMode.DIAGNOSTIC)
        bad = dataclasses.replace(diagnostic, failure_route=Decision.STOP)
        with self.assertRaises(ValueError):
            AssuranceEngine(checks=(bad,))


class Clause3Routing(unittest.TestCase):
    def test_3_1_the_routing_constant(self) -> None:
        self.assertEqual(ROUTING_SEMANTICS, "missing-coverage>stop>assist>scale@1")

    def test_3_2_no_check_runs_under_missing_coverage(self) -> None:
        gates = tuple(c for c in default_checks() if c.id != "gate.net-value")
        case = AssuranceEngine(
            checks=gates, required_coverage=DEFAULT_REQUIRED_COVERAGE
        ).evaluate(_bundle())
        self.assertIs(case.decision, Decision.INCOMPLETE)
        self.assertEqual(case.check_results, ())


class Clause4TheOneAct(unittest.TestCase):
    def test_4_1_a_refused_scale_is_incomplete_with_audit_grounds(self) -> None:
        bundle = _bundle()  # no label_source, no attestations
        case, report = decide(bundle)
        self.assertIs(case.decision, Decision.INCOMPLETE)
        self.assertFalse(report.assessable)
        self.assertTrue(
            any(entry.startswith("audit: ") for entry in case.missing_coverage)
        )

    def test_4_2_a_stop_passes_through_untouched(self) -> None:
        bundle = _bundle(
            outcomes={"t1": Outcome(task_id="t1", acceptable=True,
                                    business_value_usd=0.0, human_minutes=1.0)},
        )
        case, _ = decide(bundle)
        self.assertIs(case.decision, Decision.STOP)


class Clause5ContractDigest(unittest.TestCase):
    def test_5_2_reordering_checks_changes_the_digest(self) -> None:
        checks = default_checks()
        forward = decision_contract_digest(checks, DEFAULT_REQUIRED_COVERAGE)
        reversed_ = decision_contract_digest(
            tuple(reversed(checks)), DEFAULT_REQUIRED_COVERAGE
        )
        self.assertNotEqual(forward, reversed_)

    def test_5_2_empty_config_and_absent_config_share_a_digest(self) -> None:
        import dataclasses

        checks = default_checks()
        with_empty = (dataclasses.replace(checks[0], config={}),) + checks[1:]
        self.assertEqual(
            decision_contract_digest(checks, DEFAULT_REQUIRED_COVERAGE),
            decision_contract_digest(with_empty, DEFAULT_REQUIRED_COVERAGE),
        )

    def test_5_3_a_check_without_retrievable_source_is_refused(self) -> None:
        import dataclasses

        checks = default_checks()
        unbound = dataclasses.replace(checks[0], run=len)
        with self.assertRaises(ValueError):
            decision_contract_digest(
                (unbound,) + checks[1:], DEFAULT_REQUIRED_COVERAGE
            )


class Clause6EvidenceDigest(unittest.TestCase):
    def test_6_2_the_digest_tracks_mutation(self) -> None:
        bundle = _bundle()
        before = bundle.digest
        bundle.outcomes["t1"] = Outcome(task_id="t1", acceptable=False,
                                        business_value_usd=5.0,
                                        human_minutes=1.0)
        self.assertNotEqual(bundle.digest, before)

    def test_6_1_truthiness_gates_the_optional_keys(self) -> None:
        self.assertNotEqual(
            _bundle().digest, _bundle(label_source="instrument.x").digest
        )


class Clause7Attestation(unittest.TestCase):
    def _assess(self, method: str, agreement: float):
        import datetime as dt

        record = Attestation(
            instrument="i", method=method, agreement=agreement,
            sample_size=500, reference="ref", measured_at="2026-08-01",
        )
        return assess_provenance(
            ["i"], {"i": record}, policy=ProvenancePolicy(),
            as_of=dt.date(2026, 9, 1),
        )

    def test_7_2_the_method_floors(self) -> None:
        self.assertEqual(METHOD_FLOORS["cohens-kappa"], 0.60)
        self.assertEqual(METHOD_FLOORS["krippendorff-alpha"], 0.667)
        self.assertTrue(self._assess("cohens-kappa", 0.61).all_accepted)
        self.assertFalse(self._assess("cohens-kappa", 0.59).all_accepted)

    def test_7_3_test_retest_never_attests(self) -> None:
        self.assertIn("test-retest-agreement", RELIABILITY_ONLY_METHODS)
        self.assertFalse(self._assess("test-retest-agreement", 0.99).all_accepted)

    def test_7_4_as_of_is_required(self) -> None:
        with self.assertRaises(TypeError):
            assess_provenance(["i"], {}, policy=ProvenancePolicy())


class Clause8Claims(unittest.TestCase):
    def test_8_2_verify_is_total_on_garbage(self) -> None:
        class Hostile:
            def __getattr__(self, name):
                raise RuntimeError("hostile claim")

        verdict = verify(Hostile(), _bundle())
        self.assertIs(verdict.verdict, Verdict.UNVERIFIED)

    def test_8_1_parse_rejects_a_foreign_schema(self) -> None:
        with self.assertRaises(ValueError):
            parse_claim({"schema_version": "assurance.claim@0"})


class Clause9NonInference(unittest.TestCase):
    def test_9_1_zero_usage_under_a_rate_card_is_invalid_evidence(self) -> None:
        with self.assertRaises(ValueError):
            _bundle(events=(
                TraceEvent(task_id="t1", event_id="e1",
                           timestamp="2026-01-01T00:00:00Z",
                           event_type="model", name="completion", model="m"),
            ))


if __name__ == "__main__":
    unittest.main()
