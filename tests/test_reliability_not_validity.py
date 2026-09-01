"""Repeatability is not correctness, and an attestation must not conflate them.

Measuring whether an instrument repeats itself is far easier than measuring
whether it is right, which makes it tempting to report the easy number and let
the reader supply the interpretation. An instrument that scores identical
inputs identically every time can be systematically wrong about all of them.

This distinction was added because a real test-retest figure became available:
one arm pair in the upstream dataset publishes 500 byte-identical transcripts
under two model labels, and `info.resolved` disagrees on 44 of them. That is
91.2% agreement with itself, measured rather than invented, and it is still not
grounds to trust the label.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import unittest

from agent_economics.provenance import (
    METHOD_FLOORS,
    RELIABILITY_ONLY_METHODS,
    Attestation,
    assess_provenance,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
ATTESTATIONS = ROOT / "examples" / "public-swebench" / "attestations.json"
INSTRUMENT = "swe-bench-verified.hidden-tests@pinned-upstream"
AS_OF = dt.date(2026, 8, 31)


def _attestation(**overrides) -> Attestation:
    fields = {
        "instrument": INSTRUMENT,
        "method": "test-retest-agreement",
        "agreement": 0.912,
        "sample_size": 500,
        "reference": "duplicate scoring of identical transcripts",
        "measured_at": "2026-08-31",
    }
    fields.update(overrides)
    return Attestation(**fields)


class ReliabilityDoesNotSatisfyValidity(unittest.TestCase):
    def test_a_high_test_retest_figure_is_still_not_attested(self) -> None:
        report = assess_provenance(
            (INSTRUMENT,), {INSTRUMENT: _attestation()}, as_of=AS_OF
        )
        self.assertFalse(report.all_accepted)
        self.assertIn("repeatability, not correctness", report.statuses[0].reason)

    def test_even_a_perfect_test_retest_figure_is_not_attested(self) -> None:
        """The point is categorical, not a threshold."""
        report = assess_provenance(
            (INSTRUMENT,), {INSTRUMENT: _attestation(agreement=1.0)}, as_of=AS_OF
        )
        self.assertFalse(report.all_accepted)

    def test_a_validity_method_at_the_same_figure_is_attested(self) -> None:
        """Same number, different question, different answer."""
        report = assess_provenance(
            (INSTRUMENT,),
            {INSTRUMENT: _attestation(method="agreement-vs-human-adjudication")},
            as_of=AS_OF,
        )
        self.assertTrue(report.all_accepted, report.statuses[0].reason)

    def test_the_reliability_methods_are_a_subset_of_the_known_ones(self) -> None:
        """An unknown method is refused; these must be known and classified."""
        self.assertTrue(RELIABILITY_ONLY_METHODS)
        self.assertTrue(set(METHOD_FLOORS) >= RELIABILITY_ONLY_METHODS)

    def test_the_reason_names_a_method_that_would_serve(self) -> None:
        """A refusal that does not say what would satisfy it is a dead end."""
        reason = assess_provenance(
            (INSTRUMENT,), {INSTRUMENT: _attestation()}, as_of=AS_OF
        ).statuses[0].reason
        validity = set(METHOD_FLOORS) - RELIABILITY_ONLY_METHODS
        self.assertTrue(any(method in reason for method in validity))


class ThePublishedAttestationIsTheMeasuredOne(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(ATTESTATIONS.read_text(encoding="utf-8"))

    def test_it_records_the_figure_the_audit_computed(self) -> None:
        from research.outcome_audit import AUDIT, duplicate_arms

        pair = duplicate_arms(json.loads(AUDIT.read_text(encoding="utf-8")))[0]
        entry = self.document[INSTRUMENT]
        self.assertAlmostEqual(entry["agreement"], round(pair["agreement"], 4))
        self.assertEqual(entry["sample_size"], pair["n"])

    def test_it_declares_the_method_that_was_actually_used(self) -> None:
        """Filing this as a validity method would be the whole error."""
        self.assertEqual(
            self.document[INSTRUMENT]["method"], "test-retest-agreement"
        )

    def test_supplying_it_does_not_make_the_real_case_assessable(self) -> None:
        from agent_economics import load_normalized_json_bundle
        from agent_economics.audit import audit

        bundle = load_normalized_json_bundle(
            ROOT / "examples" / "public-swebench" / "arms" / "candidate-opus.json"
        )
        attestations = {
            name: Attestation(instrument=name, **fields)
            for name, fields in self.document.items()
        }
        report = audit(bundle, attestations=attestations, as_of=AS_OF)
        self.assertFalse(report.assessable)
        self.assertIn("unattested instruments", report.grounds)


if __name__ == "__main__":
    unittest.main()
