"""The audit and the gates must not disagree about the same evidence.

They already share their assessors: `audit()` calls `assess_bundle_closure` and
`assess_provenance`, and so do the two gates. What diverged was field coverage.
`audit()` read `unaccounted` and ignored `unrecorded_delegations`, so a bundle
the shipped gate refused was reported as assessable with "This run delegated no
work" -- same evidence, two verdicts, and the audit's was the reassuring one.

Rewriting the audit to run the gates would lose what it is for: it reports
grounds for withholding, which needs the report rather than a pass or a fail.
So the guarantee is stated as a property instead, over cases built to break it:

    if a gate refuses this evidence, the audit must not call it assessable.

That forbids the whole class rather than the one instance that was found.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import unittest
from types import SimpleNamespace

from agent_economics import load_normalized_json_bundle
from agent_economics.audit import audit
from agent_economics.delegation import (
    UnaccountedDelegation,
    UnpricedDelegation,
)
from agent_economics.models import Outcome, TraceEvent
from agent_economics.provenance import (
    Attestation,
    UnattestedInstrument,
    evidence_provenance_gate,
)
from agent_economics.registry import default_registry
from agent_economics.unsupplied import checks_only_bundle

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code" / "bundle.json"
AS_OF = dt.date(2026, 8, 27)


def _event(index: int, name: str, kind: str = "tool", cost: float | None = 0.0):
    return TraceEvent(
        task_id="t0", event_id=f"e{index}",
        timestamp=f"2026-08-27T00:00:{index % 60:02d}Z",
        event_type=kind, name=name, model="m", direct_cost_usd=cost,
    )


#: Every case declares an instrument and supplies an attestation for it, so
#: provenance is not a ground and delegation is isolated as the only one. The
#: first version of this file omitted both: every bundle was unassessable for
#: "no evidence instrument recorded" whatever the delegation did, so the
#: property held vacuously and passed with the defect restored.
INSTRUMENT = "fixture.manual-review@1"
ATTESTATION = {
    INSTRUMENT: Attestation(
        instrument=INSTRUMENT, method="raw-agreement", agreement=0.95,
        sample_size=200, reference="two-annotator adjudication",
        measured_at="2026-08-01",
    )
}


def _bundle(events, edges=(), declared=()):
    return checks_only_bundle(
        events=tuple(events),
        outcomes={"t0": Outcome(task_id="t0", acceptable=True)},
        source_id="s.x", dependency_edges=tuple(edges),
        declared_delegations=tuple(declared), label_source=INSTRUMENT,
    )


def _audit(bundle):
    return audit(bundle, attestations=ATTESTATION, as_of=AS_OF)


def _delegation_gate_refuses(bundle) -> bool:
    view = SimpleNamespace(
        events=bundle.events, dependency_edges=bundle.dependency_edges,
        rates=bundle.rates,
    )
    try:
        default_registry().build(
            "gate.delegation-closure", bundle=bundle
        ).run(view)
    except (UnaccountedDelegation, UnpricedDelegation):
        return True
    return False


class TheAuditNeverCallsAssessableWhatAGateRefuses(unittest.TestCase):
    """Each case is one the shipped delegation gate refuses."""

    def _cases(self):
        return {
            "delegation tool spawned nothing recorded": _bundle(
                [_event(0, "chat", "model"), _event(1, "Agent")]
            ),
            "undeclared delegation over real spend": _bundle(
                [_event(0, "chat", "model"), _event(1, "Agent"),
                 _event(2, "chat", "model", 750.0)],
                edges=[("e1", "e2")],
            ),
            "delegated work nothing priced": _bundle(
                [_event(0, "chat", "model"), _event(1, "Agent"),
                 _event(2, "chat", "model", None)],
                edges=[("e1", "e2")],
            ),
            "nested links around an undeclared call": _bundle(
                [_event(0, "chat", "model"), _event(1, "Agent"), _event(2, "Agent"),
                 _event(3, "Agent"), _event(4, "chat", "model", 500.0)],
                edges=[("e1", "e2"), ("e2", "e3"), ("e3", "e4")],
                declared=["e1", "e2"],
            ),
        }

    def test_provenance_is_not_what_makes_these_unassessable(self) -> None:
        """Without this the property holds vacuously.

        A bundle with no attested instrument is unassessable whatever its
        delegation does, so the first version of these cases passed with the
        defect restored. This asserts the isolation the property depends on.
        """
        clean = _bundle([_event(0, "chat", "model")])
        report = _audit(clean)
        self.assertTrue(
            report.assessable,
            f"a case with no delegation problem must be assessable: {report.grounds}",
        )

    def test_the_gate_refuses_every_case_here(self) -> None:
        """If this fails the cases have gone stale and prove nothing."""
        for name, bundle in self._cases().items():
            with self.subTest(case=name):
                self.assertTrue(
                    _delegation_gate_refuses(bundle),
                    "this case no longer exercises a refusal",
                )

    def test_the_audit_withholds_wherever_the_gate_refuses(self) -> None:
        for name, bundle in self._cases().items():
            with self.subTest(case=name):
                report = _audit(bundle)
                self.assertFalse(
                    report.assessable,
                    f"gate refuses but audit calls it assessable: {report.grounds}",
                )

    def test_the_audit_never_reports_no_delegation_when_one_was_seen(self) -> None:
        """The exact sentence the divergence produced."""
        from agent_economics.audit import render_markdown

        for name, bundle in self._cases().items():
            with self.subTest(case=name):
                self.assertNotIn("delegated no work", render_markdown(_audit(bundle)))


class TheAuditAgreesWithTheProvenanceGate(unittest.TestCase):
    def test_an_unattested_instrument_withholds_in_both(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        instrument = bundle.label_source
        gate_refused = False
        try:
            evidence_provenance_gate(
                instruments=(instrument,), attestations={}, as_of=AS_OF
            ).run(None)
        except UnattestedInstrument:
            gate_refused = True
        self.assertTrue(gate_refused)
        self.assertFalse(audit(bundle, as_of=AS_OF).assessable)

    def test_a_corroborated_instrument_agrees_in_both(self) -> None:
        """The carve-out was reachable from one path and not the other."""
        bundle = load_normalized_json_bundle(EXAMPLE)
        instrument = bundle.label_source
        accepted = True
        try:
            evidence_provenance_gate(
                instruments=(instrument,), attestations={}, as_of=AS_OF,
                independently_verified=(instrument,),
            ).run(None)
        except UnattestedInstrument:
            accepted = False
        report = audit(bundle, independently_verified=(instrument,), as_of=AS_OF)
        self.assertEqual(report.assessable, accepted)


if __name__ == "__main__":
    unittest.main()
