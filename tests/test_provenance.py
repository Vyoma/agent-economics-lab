"""
Attestation for the instruments that produced the evidence.

Every gate rests on evidence; the evidence came from an instrument; nothing
checked the instrument. A judge at 0.62 agreement on forty samples measured eight
months ago and one at 0.94 on five hundred last week both read as `label_source`.
This applies the package's own rule one level down: an unattested instrument
supplying a sole-provider gate forces INCOMPLETE.
"""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from agent_economics import load_normalized_json_bundle
from agent_economics.assurance import AssuranceEngine
from agent_economics.models import Decision
from agent_economics.provenance import (
    EVIDENCE_PROVENANCE,
    Attestation,
    ProvenancePolicy,
    assess_provenance,
    evidence_provenance_gate,
    parse_attestations,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "examples" / "claude-code" / "bundle.json"
TODAY = dt.date(2026, 8, 26)


def _record(**overrides) -> dict:
    row = {
        "instrument": "judge@v1",
        "method": "agreement-vs-human-adjudication",
        "agreement": 0.94,
        "sample_size": 500,
        "reference": "human-panel@2026-07",
        "measured_at": "2026-07-15",
    }
    row.update(overrides)
    return row


class ParseTest(unittest.TestCase):
    def test_a_complete_record_parses(self) -> None:
        parsed = parse_attestations([_record()])
        self.assertEqual(parsed["judge@v1"].agreement, 0.94)

    def test_every_field_is_required(self) -> None:
        """An attestation missing any of them establishes nothing."""
        for field in (
            "instrument", "method", "agreement",
            "sample_size", "reference", "measured_at",
        ):
            with self.subTest(missing=field):
                with self.assertRaises(ValueError) as ctx:
                    parse_attestations([_record(**{field: None})])
                self.assertIn(field, str(ctx.exception))

    def test_duplicate_instruments_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            parse_attestations([_record(), _record()])

    def test_a_measured_at_that_is_not_a_date_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            parse_attestations([_record(measured_at="recently")])

    def test_no_attestations_is_not_an_error(self) -> None:
        self.assertEqual(parse_attestations(None), {})


class AssessmentTest(unittest.TestCase):
    def _assess(self, raw, instruments=("judge@v1",), policy=None):
        return assess_provenance(
            instruments, parse_attestations(raw), policy=policy, as_of=TODAY
        )

    def test_an_instrument_with_no_record_is_rejected(self) -> None:
        report = self._assess([])
        self.assertFalse(report.all_accepted)
        self.assertIn("no attestation", report.rejected[0].reason)

    def test_agreement_below_the_floor_is_rejected(self) -> None:
        report = self._assess([_record(agreement=0.62)])
        self.assertIn("0.62 below", report.rejected[0].reason)
        self.assertIn("agreement-vs-human-adjudication", report.rejected[0].reason)

    def test_too_small_a_sample_is_rejected(self) -> None:
        report = self._assess([_record(sample_size=40)])
        self.assertIn("sample of 40", report.rejected[0].reason)

    def test_a_lapsed_calibration_is_rejected(self) -> None:
        """Good agreement, measured too long ago. This is the metrology rule."""
        report = self._assess([_record(measured_at="2025-07-01")])
        self.assertIn("days ago", report.rejected[0].reason)

    def test_all_three_failures_are_reported_together(self) -> None:
        """A reader fixing one should see the other two, not discover them next run."""
        report = self._assess(
            [_record(agreement=0.5, sample_size=10, measured_at="2024-01-01")]
        )
        reason = report.rejected[0].reason
        self.assertIn("agreement", reason)
        self.assertIn("sample", reason)
        self.assertIn("days ago", reason)

    def test_an_instrument_in_calibration_is_accepted(self) -> None:
        self.assertTrue(self._assess([_record()]).all_accepted)

    def test_the_policy_is_configurable(self) -> None:
        strict = ProvenancePolicy(min_agreement=0.99, min_sample_size=1, max_age_days=9999)
        self.assertFalse(self._assess([_record()], policy=strict).all_accepted)

    def test_an_unused_attestation_does_not_make_a_run_pass(self) -> None:
        """Attesting some other instrument says nothing about the one in use."""
        report = self._assess([_record(instrument="some-other-judge@v1")])
        self.assertFalse(report.all_accepted)

    def test_as_of_is_required_so_verdicts_are_reproducible(self) -> None:
        """A verdict that changes with the wall clock is not an artifact."""
        with self.assertRaises(TypeError):
            assess_provenance(("judge@v1",), {})


class GateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_normalized_json_bundle(BUNDLE)

    def _decide(self, raw) -> Decision:
        gate = evidence_provenance_gate(
            instruments=[self.bundle.label_source],
            attestations=parse_attestations(raw),
            as_of=TODAY,
        )
        return AssuranceEngine(
            checks=(gate,), required_coverage=frozenset({EVIDENCE_PROVENANCE})
        ).evaluate(self.bundle).decision

    def test_the_bundle_records_its_labelling_instrument(self) -> None:
        """Previously parsed from the contract and discarded."""
        self.assertEqual(self.bundle.label_source, "fixture.manual-review")

    def test_an_unattested_instrument_yields_incomplete(self) -> None:
        self.assertIs(self._decide([]), Decision.INCOMPLETE)

    def test_a_weak_instrument_yields_incomplete_not_stop(self) -> None:
        """An uncalibrated judge has not produced a bad result, just an unknown one."""
        verdict = self._decide(
            [_record(instrument=self.bundle.label_source, agreement=0.62)]
        )
        self.assertIs(verdict, Decision.INCOMPLETE)
        self.assertIsNot(verdict, Decision.STOP)

    def test_a_lapsed_instrument_yields_incomplete(self) -> None:
        self.assertIs(
            self._decide(
                [_record(instrument=self.bundle.label_source, measured_at="2025-07-01")]
            ),
            Decision.INCOMPLETE,
        )

    def test_an_instrument_in_calibration_permits_a_verdict(self) -> None:
        self.assertIsNot(
            self._decide([_record(instrument=self.bundle.label_source)]),
            Decision.INCOMPLETE,
        )


class AgeArithmeticTest(unittest.TestCase):
    def test_age_is_measured_in_whole_days(self) -> None:
        record = Attestation(
            instrument="j", method="m", agreement=1.0, sample_size=1,
            reference="r", measured_at="2026-07-15",
        )
        self.assertEqual(record.age_days(dt.date(2026, 8, 26)), 42)

    def test_a_timestamp_with_a_time_component_still_parses(self) -> None:
        record = Attestation(
            instrument="j", method="m", agreement=1.0, sample_size=1,
            reference="r", measured_at="2026-07-15T09:30:00Z",
        )
        self.assertEqual(record.age_days(dt.date(2026, 7, 16)), 1)


if __name__ == "__main__":
    unittest.main()


class SoleProviderCarveOutTest(unittest.TestCase):
    """
    An instrument whose output is checked by something else is not the sole
    provider of its evidence and need not be attested.

    The module's docstring described this and its code did not implement it: the
    gate refused on any failing instrument. A prior-art sweep found the gap, and
    also found that the carve-out is DO-178C's independent-verification
    exemption, which docs/landscape.md now cites rather than claims.
    """

    def test_a_corroborated_instrument_needs_no_attestation(self) -> None:
        report = assess_provenance(
            ["judge@v1"], {}, as_of=TODAY, independently_verified=["judge@v1"]
        )
        self.assertTrue(report.all_accepted)

    def test_the_same_instrument_uncorroborated_is_rejected(self) -> None:
        self.assertFalse(assess_provenance(["judge@v1"], {}, as_of=TODAY).all_accepted)

    def test_corroborating_a_different_instrument_does_not_help(self) -> None:
        report = assess_provenance(
            ["judge@v1"], {}, as_of=TODAY, independently_verified=["some-other@v1"]
        )
        self.assertFalse(report.all_accepted)


class PerMethodFloorTest(unittest.TestCase):
    """
    Raw agreement, Cohen's kappa and held-out accuracy do not share a threshold.

    Kappa discounts chance agreement and raw agreement does not, so 0.8 means
    materially different things. Comparing all three against one `min_agreement`
    was a category error; ILAC-G8 requires a conformity statement to declare its
    decision rule.
    """

    def _accepts(self, method: str, agreement: float) -> bool:
        raw = parse_attestations([_record(method=method, agreement=agreement)])
        return assess_provenance(["judge@v1"], raw, as_of=TODAY).all_accepted

    def test_the_same_number_passes_as_kappa_and_fails_as_raw_agreement(self) -> None:
        self.assertTrue(self._accepts("cohens-kappa", 0.70))
        self.assertFalse(self._accepts("raw-agreement", 0.70))

    def test_an_unknown_method_is_refused_not_graded_on_another_scale(self) -> None:
        raw = parse_attestations([_record(method="vibes-based")])
        with self.assertRaises(ValueError) as ctx:
            assess_provenance(["judge@v1"], raw, as_of=TODAY)
        self.assertIn("unknown attestation method", str(ctx.exception))

    def test_an_explicit_policy_floor_overrides_the_per_method_default(self) -> None:
        raw = parse_attestations([_record(method="vibes-based", agreement=0.99)])
        report = assess_provenance(
            ["judge@v1"], raw, as_of=TODAY, policy=ProvenancePolicy(min_agreement=0.9)
        )
        self.assertTrue(report.all_accepted)
