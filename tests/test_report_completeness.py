"""The rendered case must not lose what the decision was made from.

`renderer.markdown@1` and `renderer.json@1` were byte-compared against
checked-in fixtures, which proves the output has not changed and says
nothing about whether it is right. A renderer that silently dropped a
breach would keep matching its fixture forever, and the fixture would be
updated to match it.

The property here is completeness: everything that moved the decision has
to appear in what a reader is handed. A person acting on an assurance case
sees the prose, not the object.
"""

from __future__ import annotations

import json
import unittest

from agent_economics.assurance import AssuranceEngine
from agent_economics.checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from agent_economics.evidence import make_evidence_bundle
from agent_economics.models import (
    Baseline,
    CheckStatus,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
)
from agent_economics.report import render_json, render_markdown

POLICY = EconomicPolicy(
    human_hourly_cost_usd=90.0,
    min_acceptable_rate=0.95,          # deliberately unmeetable
    max_cost_per_acceptable_outcome_usd=0.001,
    max_p95_task_cost_usd=0.001,
    max_trace_cost_per_task_usd=0.001,
    max_calls_per_task=1,
    min_expected_net_value_per_attempt_usd=1000.0,
)


def _failing_case():
    """A case with several simultaneous breaches, across several tasks."""
    events = []
    outcomes = {}
    for task in range(4):
        task_id = f"t{task}"
        for index in range(3):
            events.append(TraceEvent(
                task_id=task_id, event_id=f"e{task}-{index}",
                timestamp=f"2026-01-01T00:00:{index:02d}Z",
                event_type="model", name="completion", model="m",
                input_tokens=900 + index, output_tokens=400 + index,
            ))
        outcomes[task_id] = Outcome(
            task_id=task_id, acceptable=task % 2 == 0,
            business_value_usd=1.0, human_minutes=3.0,
            remediation_cost_usd=2.0,
        )
    bundle = make_evidence_bundle(
        events=tuple(events), outcomes=outcomes,
        rates={"m": ModelRate(30.0, 150.0)},
        baseline=Baseline("human", 0.5, 0.99, 50.0),
        policy=POLICY, source_id="test.report",
    )
    return AssuranceEngine(
        checks=default_checks(), required_coverage=DEFAULT_REQUIRED_COVERAGE
    ).evaluate(bundle)


class TheMarkdownCarriesEverythingThatDecided(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = _failing_case()
        cls.rendered = render_markdown(cls.case)

    def test_the_case_actually_exercises_the_property(self) -> None:
        """A renderer test over a case with nothing to report proves nothing."""
        self.assertTrue(self.case.breaches)
        self.assertTrue(
            any(r.status is CheckStatus.FAIL for r in self.case.check_results)
        )

    def test_every_breach_appears(self) -> None:
        for breach in self.case.breaches:
            with self.subTest(breach=breach):
                self.assertIn(breach, self.rendered)

    def test_every_check_is_named_with_its_status(self) -> None:
        for result in self.case.check_results:
            with self.subTest(check=result.check_id):
                self.assertIn(result.check_id, self.rendered)
                self.assertIn(result.status.value, self.rendered)

    def test_the_decision_and_both_digests_appear(self) -> None:
        self.assertIn(self.case.decision.value, self.rendered)
        self.assertIn(self.case.evidence_digest, self.rendered)
        self.assertIn(self.case.decision_contract_digest, self.rendered)

    def test_the_breaches_are_carried_twice_over(self) -> None:
        """Stripping `breaches` alone loses nothing a reader can see.

        Written expecting the opposite, and the renderer was right: the same
        text reaches the page through the failing checks' own messages, so
        the breach list is a summary rather than the only carrier. Recorded
        because a later reader will otherwise try to prove the same wrong
        thing, and because a completeness test that passes only through
        redundancy should say so out loud.
        """
        import dataclasses

        without_breaches = render_markdown(
            dataclasses.replace(self.case, breaches=())
        )
        still_visible = [b for b in self.case.breaches if b in without_breaches]
        self.assertEqual(
            still_visible, list(self.case.breaches),
            "the failing checks no longer carry the breach text, so the "
            "breach list is now the only carrier and dropping it loses it",
        )

    def test_genuine_loss_is_detected(self) -> None:
        """Non-vacuity, against the redundancy: remove both carriers."""
        import dataclasses

        stripped = dataclasses.replace(self.case, breaches=(), check_results=())
        rendered = render_markdown(stripped)
        missing = [b for b in self.case.breaches if b not in rendered]
        self.assertEqual(
            missing, list(self.case.breaches),
            "removing every carrier still left the breaches on the page, so "
            "these tests cannot detect a renderer that drops them",
        )


class TheJsonCarriesEverythingThatDecided(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = _failing_case()
        cls.document = json.loads(render_json(cls.case))

    def test_the_check_set_is_complete(self) -> None:
        rendered = {entry["id"] for entry in self.document["checks"]}
        self.assertEqual(
            rendered, {r.check_id for r in self.case.check_results}
        )

    def test_every_failing_check_keeps_its_route(self) -> None:
        """The route is why a failure became this decision and not another."""
        by_id = {entry["id"]: entry for entry in self.document["checks"]}
        for result in self.case.check_results:
            if result.status is CheckStatus.FAIL:
                with self.subTest(check=result.check_id):
                    self.assertEqual(
                        by_id[result.check_id]["on_failure"],
                        result.on_failure.value,
                    )

    def test_the_digests_are_carried(self) -> None:
        manifest = self.document["manifest"]
        self.assertEqual(manifest["evidence_digest"], self.case.evidence_digest)
        self.assertEqual(
            manifest["decision_contract_digest"],
            self.case.decision_contract_digest,
        )

    def test_the_decision_is_carried(self) -> None:
        self.assertEqual(self.document["decision"], self.case.decision.value)


if __name__ == "__main__":
    unittest.main()
