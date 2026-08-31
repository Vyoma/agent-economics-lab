"""A verifier a stranger can run, and every way it was made to lie.

`verify()` answers SUPPORTED, REFUTED, or UNVERIFIED. The distinction between
the last two is the whole point: a verifier that cannot separate "false" from
"I could not tell" is the fail-open this package catalogues, moved one level up.

The forgery in `ForgingAClaim` is the reason the contract-strength check exists.
Before it, dropping the single failing gate and requiring no coverage turned an
honest ASSIST into a SUPPORTED claim reading "Safe to scale: every gate passes."
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import unittest
from dataclasses import replace

from agent_economics import load_normalized_json_bundle
from agent_economics.assurance import AssuranceEngine, default_checks
from agent_economics.claim import (
    CLAIM_SCHEMA_VERSION,
    Verdict,
    issue,
    parse_claim,
    verify,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code" / "bundle.json"
ISSUED = dt.date(2026, 8, 31)


def _bundle():
    return load_normalized_json_bundle(EXAMPLE)


def _claim(bundle=None, **kwargs):
    return issue(
        bundle if bundle is not None else _bundle(),
        kwargs.pop("assertion", "This evidence yields the stated decision."),
        issued_at=ISSUED, **kwargs,
    )


class AnHonestClaimVerifies(unittest.TestCase):
    def test_a_claim_verifies_against_its_own_evidence(self) -> None:
        bundle = _bundle()
        result = verify(_claim(bundle), bundle)
        self.assertIs(result.verdict, Verdict.SUPPORTED)
        self.assertTrue(result.supported)

    def test_it_survives_a_json_round_trip(self) -> None:
        bundle = _bundle()
        claim = _claim(bundle)
        restored = parse_claim(json.loads(claim.render()))
        self.assertEqual(restored, claim)
        self.assertIs(verify(restored, bundle).verdict, Verdict.SUPPORTED)

    def test_check_order_is_preserved(self) -> None:
        """The contract digest binds order, so a reordered claim is a different one."""
        claim = _claim()
        self.assertEqual(
            [binding.id for binding in claim.checks],
            [spec.id for spec in default_checks()],
        )


class ForgingAClaim(unittest.TestCase):
    """Every route tried to make the verifier bless something false."""

    def test_dropping_the_failing_gate_no_longer_verifies(self) -> None:
        bundle = _bundle()
        full = tuple(default_checks())
        case = AssuranceEngine(full).evaluate(bundle)
        failing = {r.check_id for r in case.check_results if r.status.value != "PASS"}
        self.assertTrue(failing, "fixture must have a non-passing check to drop")

        forged = issue(
            bundle, "Safe to scale: every gate passes.",
            checks=tuple(s for s in full if s.id not in failing),
            required_coverage=frozenset(), issued_at=ISSUED,
        )
        self.assertEqual(forged.decision, "SCALE")
        self.assertNotEqual(case.decision.value, "SCALE")

        result = verify(forged, bundle)
        self.assertIs(
            result.verdict, Verdict.UNVERIFIED,
            "a claim under a weakened contract must not be confirmed",
        )
        self.assertIn("requires less than the shipped contract", result.reasons[0])

    def test_requiring_no_coverage_never_verifies(self) -> None:
        bundle = _bundle()
        forged = issue(
            bundle, "Nothing was required, so everything is fine.",
            required_coverage=frozenset(), issued_at=ISSUED,
        )
        self.assertIs(verify(forged, bundle).verdict, Verdict.UNVERIFIED)

    def test_the_dropped_dimensions_are_named_by_value(self) -> None:
        """`Coverage` subclasses str; str() on a member leaks 'Coverage.NAME'."""
        bundle = _bundle()
        forged = issue(bundle, "x", required_coverage=frozenset(), issued_at=ISSUED)
        reason = verify(forged, bundle).reasons[0]
        self.assertNotIn("Coverage.", reason)
        self.assertIn("business_value", reason)

    def test_substituting_the_evidence_is_refuted(self) -> None:
        """A genuinely different bundle, not a `replace`d one.

        `EvidenceBundle.digest` is a stored field, so `dataclasses.replace`
        yields a bundle whose digest still describes the original. The first
        version of this test substituted that way and the digests matched,
        which is a hazard worth knowing about rather than a passing test.
        """
        bundle = _bundle()
        claim = _claim(bundle)
        other = load_normalized_json_bundle(
            ROOT / "examples" / "checks-only" / "bundle.json"
        )
        self.assertNotEqual(other.digest, bundle.digest)
        result = verify(claim, other)
        self.assertIs(result.verdict, Verdict.REFUTED)
        self.assertIn("not the evidence", result.reasons[0])

    def test_editing_the_claimed_decision_is_refuted(self) -> None:
        bundle = _bundle()
        claim = replace(_claim(bundle), decision="SCALE")
        result = verify(claim, bundle)
        self.assertIs(result.verdict, Verdict.REFUTED)
        self.assertIn("not the claimed SCALE", result.reasons[0])

    def test_editing_the_contract_digest_is_refuted(self) -> None:
        bundle = _bundle()
        claim = replace(_claim(bundle), decision_contract_digest="0" * 64)
        self.assertIs(verify(claim, bundle).verdict, Verdict.REFUTED)

    def test_naming_a_check_this_build_lacks_is_unverified_not_refuted(self) -> None:
        """Absence of the implementation is inability to check, not falsity."""
        bundle = _bundle()
        claim = _claim(bundle)
        alien = replace(claim.checks[0], id="gate.from-another-build")
        result = verify(replace(claim, checks=(alien,) + claim.checks[1:]), bundle)
        self.assertIs(result.verdict, Verdict.UNVERIFIED)

    def test_a_substituted_implementation_is_unverified_not_refuted(self) -> None:
        bundle = _bundle()
        claim = _claim(bundle)
        swapped = replace(claim.checks[0], implementation_digest="f" * 64)
        result = verify(replace(claim, checks=(swapped,) + claim.checks[1:]), bundle)
        self.assertIs(result.verdict, Verdict.UNVERIFIED)
        self.assertIn("different source here", result.reasons[0])


class TheVerifierIsTotal(unittest.TestCase):
    """It must always answer, and never answer SUPPORTED by accident."""

    def test_a_non_bundle_does_not_raise(self) -> None:
        for hostile in (None, 0, "", [], {}, object()):
            with self.subTest(value=type(hostile).__name__):
                result = verify(_claim(), hostile)
                self.assertIsNot(result.verdict, Verdict.SUPPORTED)

    def test_malformed_documents_are_refused_at_parse(self) -> None:
        good = json.loads(_claim().render())
        for mutate in (
            lambda d: d.pop("checks"),
            lambda d: d.update(checks=[]),
            lambda d: d.update(checks=[{"id": "x"}]),
            lambda d: d.update(schema_version="assurance.claim@99"),
            lambda d: d.update(assertion=""),
            lambda d: d.update(required_coverage="not-a-list"),
            lambda d: d.pop("evidence_digest"),
        ):
            document = json.loads(json.dumps(good))
            mutate(document)
            with (
                self.subTest(document=str(document)[:40]),
                self.assertRaises(ValueError),
            ):
                parse_claim(document)

    def test_the_schema_version_is_pinned(self) -> None:
        self.assertEqual(CLAIM_SCHEMA_VERSION, "assurance.claim@1")


if __name__ == "__main__":
    unittest.main()
