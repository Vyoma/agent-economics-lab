"""
The single command: what can this harness not tell you?

Four grounds for withholding a verdict, composed into one report. The point of
the composition is that none of them is a score, and that the question can be
asked of a harness carrying no economics at all.
"""
from __future__ import annotations

import datetime as dt
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agent_economics import load_normalized_json_bundle
from agent_economics.audit import audit, render_markdown
from agent_economics.cli import main
from agent_economics.models import (
    CheckMode,
    CheckOutput,
    CheckResult,
    CheckSpec,
    CheckStatus,
    Decision,
    Outcome,
    TraceEvent,
)
from agent_economics.provenance import parse_attestations
from agent_economics.unsupplied import checks_only_bundle

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "examples" / "claude-code" / "bundle.json"
TODAY = dt.date(2026, 8, 27)


def _clean(_view):
    return CheckOutput(
        results=(CheckResult(check_id="gate.pii", status=CheckStatus.PASS, message="clean"),)
    )


def _fails(_view):
    return CheckOutput(
        results=(
            CheckResult(
                check_id="gate.jailbreak",
                status=CheckStatus.FAIL,
                message="1 of 3",
                on_failure=Decision.STOP,
            ),
        )
    )


def _safety_bundle():
    events = tuple(
        TraceEvent(
            task_id=f"t{i}", event_id=f"e{i}", timestamp=f"2026-08-27T00:00:0{i}Z",
            event_type="model", name="c", model="m", direct_cost_usd=0.0,
        )
        for i in range(3)
    )
    outcomes = {f"t{i}": Outcome(task_id=f"t{i}", acceptable=True) for i in range(3)}
    return checks_only_bundle(events=events, outcomes=outcomes, source_id="source.my-eval")


PII = CheckSpec(id="gate.pii", version="1", mode=CheckMode.GATE,
                covers=frozenset({"pii_safety"}), run=_clean, failure_route=Decision.STOP)
JAILBREAK = CheckSpec(id="gate.jailbreak", version="1", mode=CheckMode.GATE,
                      covers=frozenset({"jailbreak_safety"}), run=_fails,
                      failure_route=Decision.STOP)


class NoEconomicsRequiredTest(unittest.TestCase):
    """The sixty-second path: safety gates, no rate card, no baseline, no policy."""

    def test_a_safety_harness_can_be_audited(self) -> None:
        report = audit(
            _safety_bundle(), (PII, JAILBREAK),
            frozenset({"pii_safety", "jailbreak_safety"}),
        )
        self.assertEqual(report.total_gates, 2)
        self.assertEqual(report.decision, Decision.STOP.value)

    def test_a_dimension_nobody_supplies_is_the_first_ground(self) -> None:
        report = audit(
            _safety_bundle(), (PII, JAILBREAK),
            frozenset({"pii_safety", "jailbreak_safety", "refusal_rate"}),
        )
        self.assertEqual(report.unprovided_coverage, ("refusal_rate",))
        self.assertIn("unprovided coverage", report.grounds)
        self.assertFalse(report.assessable)

    def test_it_names_which_gate_carries_the_verdict(self) -> None:
        report = audit(
            _safety_bundle(), (PII, JAILBREAK),
            frozenset({"pii_safety", "jailbreak_safety"}),
        )
        self.assertEqual(report.pivotal_gates, ("jailbreak_safety",))


class GroundsAreNotScoresTest(unittest.TestCase):
    def test_conformance_is_reported_as_an_invariant_not_a_number(self) -> None:
        text = render_markdown(audit(load_normalized_json_bundle(BUNDLE)))
        self.assertIn("an invariant, not a score", text)
        self.assertIn("None of the above is a score", text)

    def test_every_ground_is_listed_when_present(self) -> None:
        report = audit(load_normalized_json_bundle(BUNDLE))
        self.assertIn("unattested instruments", report.grounds)

    def test_attesting_the_instrument_removes_that_ground(self) -> None:
        bundle = load_normalized_json_bundle(BUNDLE)
        attestations = parse_attestations([{
            "instrument": bundle.label_source,
            "method": "agreement-vs-human-adjudication",
            "agreement": 0.94, "sample_size": 500,
            "reference": "panel@2026-07", "measured_at": "2026-07-15",
        }])
        report = audit(bundle, attestations=attestations, as_of=TODAY)
        self.assertEqual(report.unattested_instruments, ())
        self.assertNotIn("unattested instruments", report.grounds)

    def test_a_bundle_with_no_recorded_instrument_says_so(self) -> None:
        report = audit(_safety_bundle(), (PII,), frozenset({"pii_safety"}))
        self.assertEqual(report.instruments_checked, ())
        self.assertTrue(any("cannot say what produced its labels" in n for n in report.notes))


class AuditCliTest(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        out = StringIO()
        with redirect_stdout(out), redirect_stderr(StringIO()):
            code = main(argv)
        return code, out.getvalue()

    def test_markdown_output(self) -> None:
        code, text = self._run(["audit", "--bundle", str(BUNDLE)])
        self.assertEqual(code, 0)
        self.assertIn("What this harness cannot tell you", text)

    def test_ci_fails_when_a_ground_is_present(self) -> None:
        code, _ = self._run(["audit", "--bundle", str(BUNDLE), "--ci"])
        self.assertEqual(code, 1)

    def test_json_output_is_machine_readable(self) -> None:
        code, text = self._run(["audit", "--bundle", str(BUNDLE), "--format", "json"])
        self.assertEqual(code, 0)
        payload = json.loads(text)
        self.assertIn("grounds", payload)
        self.assertFalse(payload["assessable"])

    def test_missing_bundle_fails_closed(self) -> None:
        code, _ = self._run(["audit", "--bundle", "/nonexistent.json"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
