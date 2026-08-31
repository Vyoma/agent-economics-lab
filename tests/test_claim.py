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


class ForgeriesFoundByAdversarialReview(unittest.TestCase):
    """Each of these verified SUPPORTED against evidence that did not support it."""

    def _permissive(self, bundle):
        """The same events and labels, with the audited party's own pass marks."""
        from agent_economics.evidence import make_evidence_bundle
        policy = replace(
            bundle.policy, min_acceptable_rate=0.0,
            max_cost_per_acceptable_outcome_usd=1e9, max_p95_task_cost_usd=1e9,
            max_trace_cost_per_task_usd=1e9, max_calls_per_task=10**9,
            min_expected_net_value_per_attempt_usd=-1e9,
            min_incremental_net_value_vs_baseline_usd=-1e9,
        )
        return make_evidence_bundle(
            events=bundle.events, outcomes=bundle.outcomes, rates=bundle.rates,
            baseline=bundle.baseline, policy=policy, source_id=bundle.source_id,
            task_manifest=bundle.task_manifest,
            dependency_edges=bundle.dependency_edges,
            declared_delegations=bundle.declared_delegations,
            label_source=bundle.label_source,
        )

    def test_shipping_your_own_pass_marks_does_not_verify(self) -> None:
        """The contract binds which gates run, never what they enforce.

        Identical events, identical labels, honest digest, every dimension
        covered: only the thresholds moved, and ASSIST became SCALE.
        """
        honest = _bundle()
        rigged = self._permissive(honest)
        self.assertEqual(rigged.events, honest.events)
        self.assertEqual(rigged.outcomes, honest.outcomes)

        claim = issue(
            rigged, "All gates PASS. Cleared to SCALE.", issued_at=ISSUED
        )
        self.assertEqual(claim.decision, "SCALE")
        result = verify(claim, rigged)
        self.assertIs(result.verdict, Verdict.UNVERIFIED)
        self.assertIn("no gate could fail against", result.reasons[0])

    def test_an_honest_policy_is_not_flagged_as_inert(self) -> None:
        """The floor must not fire on ordinary thresholds."""
        bundle = _bundle()
        self.assertIs(verify(_claim(bundle), bundle).verdict, Verdict.SUPPORTED)

    def test_a_carried_over_digest_does_not_authenticate_edited_evidence(self) -> None:
        """`digest` is a stored field; verify must recompute, not read."""
        honest = _bundle()
        claim = _claim(honest)
        doctored = replace(
            honest,
            outcomes={
                task: replace(outcome, acceptable=True)
                for task, outcome in honest.outcomes.items()
            },
        )
        self.assertEqual(
            doctored.digest, claim.evidence_digest,
            "the stored field must still look authentic for this to be a test",
        )
        self.assertIs(verify(claim, doctored).verdict, Verdict.REFUTED)

    def test_the_prose_is_never_presented_as_verified(self) -> None:
        bundle = _bundle()
        claim = issue(
            bundle,
            "Zero breaches, 100% acceptable, safe for unsupervised rollout.",
            issued_at=ISSUED,
        )
        result = verify(claim, bundle)
        self.assertIs(result.verdict, Verdict.SUPPORTED)
        text = result.render()
        self.assertIn("which nothing here verifies", text)
        self.assertIn("decision `ASSIST`", text)
        self.assertFalse(result.to_dict()["assertion_is_verified"])

    def test_verify_is_total_against_things_that_are_not_claims(self) -> None:
        """The handler read `claim.assertion` after the failure it was catching."""
        bundle = _bundle()
        for hostile in (json.loads(_claim().render()), None, 7, "claim", []):
            with self.subTest(value=type(hostile).__name__):
                result = verify(hostile, bundle)
                self.assertIs(result.verdict, Verdict.UNVERIFIED)


class TheRecordMustSurviveTheCodeMoving(unittest.TestCase):
    """A claim binds each check by its source text, so the record decays.

    Adding a comment inside a gate body changes that gate's implementation
    digest and makes every prior claim UNVERIFIED. Demonstrated against a real
    scratch checkout, not assumed. A track record that resets on each refactor
    is not a track record, and calendar time is the only asset here that cannot
    be copied, so this is the thing that would have quietly killed it.

    The claim therefore pins the revision it was issued against, which lets a
    reader ask two different questions: is this still true of the code today,
    and was it true when it was made.
    """

    def test_a_claim_records_the_revision_it_was_issued_against(self) -> None:
        claim = issue(
            _bundle(), "x", issued_at=ISSUED, source_commit="0" * 40
        )
        self.assertEqual(claim.source_commit, "0" * 40)
        self.assertEqual(
            json.loads(claim.render())["source_commit"], "0" * 40
        )

    def test_the_published_claims_pin_a_revision(self) -> None:
        claims = sorted((ROOT / "research" / "claims").glob("*.claim.json"))
        self.assertTrue(claims, "the ledger must hold at least one claim")
        for path in claims:
            with self.subTest(claim=path.name):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertRegex(document["source_commit"], r"^[0-9a-f]{40}$")

    def test_an_unreproducible_claim_names_where_to_check_it(self) -> None:
        bundle = _bundle()
        claim = issue(bundle, "x", issued_at=ISSUED, source_commit="a" * 40)
        moved = replace(
            claim,
            checks=(replace(claim.checks[0], implementation_digest="f" * 64),)
            + claim.checks[1:],
        )
        result = verify(moved, bundle)
        self.assertIs(result.verdict, Verdict.UNVERIFIED)
        self.assertTrue(
            any("a" * 40 in reason for reason in result.reasons),
            "the verdict must name the revision to check against",
        )

    def test_a_claim_without_a_revision_says_so(self) -> None:
        bundle = _bundle()
        claim = issue(bundle, "x", issued_at=ISSUED)
        moved = replace(
            claim,
            checks=(replace(claim.checks[0], implementation_digest="f" * 64),)
            + claim.checks[1:],
        )
        result = verify(moved, bundle)
        self.assertIs(result.verdict, Verdict.UNVERIFIED)
        self.assertTrue(
            any("records no source commit" in reason for reason in result.reasons)
        )
