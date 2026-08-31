"""Metamorphic relations for the audit.

Deriving a verdict where no ground truth exists is the oracle problem (Barr et
al., IEEE TSE 2015). The standard answer is metamorphic testing (Chen et al.,
1998): assert a relation between two runs rather than a value for one.

This repository already used the technique -- `test_stress_properties.py` has
permutation invariance and two monotonicity relations -- but only on the
decision kernel. `audit()` had none, and D07 lived exactly there: a bundle that
declared what produced its labels was unassessable while one that recorded
nothing was assessable. No single-case assertion expresses that, and a relation
over two bundles expresses it in one line.

The relations below are stated as properties of the audit, not as regression
tests for the defects that motivated them. Each should hold for reasons that
have nothing to do with how D07 or D08 happened to be written.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import unittest
from dataclasses import replace

from agent_economics import load_normalized_json_bundle
from agent_economics.audit import audit
from agent_economics.models import Outcome, TraceEvent
from agent_economics.provenance import Attestation
from agent_economics.unsupplied import checks_only_bundle

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code" / "bundle.json"
AS_OF = dt.date(2026, 8, 27)


def _attestation(instrument: str, agreement: float = 0.91) -> Attestation:
    return Attestation(
        instrument=instrument, method="raw-agreement", agreement=agreement,
        sample_size=120, reference="two-annotator human adjudication",
        measured_at="2026-07-01",
    )


def _event(index: int, name: str, kind: str = "model", cost: float | None = 0.0):
    return TraceEvent(
        task_id="t0", event_id=f"e{index}",
        timestamp=f"2026-08-27T00:00:{index:02d}Z", event_type=kind,
        name=name, model="m", direct_cost_usd=cost,
    )


class RemovingInformationNeverHelps(unittest.TestCase):
    """MR1: deleting evidence must never make a bundle more assessable.

    The general form of D07. An audit that can be improved by withholding
    something has an incentive gradient pointing away from disclosure, whatever
    the particular field happens to be.
    """

    def setUp(self) -> None:
        self.bundle = load_normalized_json_bundle(EXAMPLE)
        self.attestations = {self.bundle.label_source: _attestation(self.bundle.label_source)}

    def _assessable(self, bundle, *, attested: bool) -> bool:
        return audit(
            bundle,
            attestations=self.attestations if attested else None,
            as_of=AS_OF,
        ).assessable

    def test_deleting_the_label_source_never_helps(self) -> None:
        """Must hold whether or not an attestation was supplied.

        Stated only in the attested condition this relation is vacuous: with a
        valid attestation both bundles are assessable and the inequality holds
        for the wrong reason. D07 lived entirely in the unattested condition,
        where declaring the instrument withheld a verdict and deleting it did
        not. Verified against 4b60e19: the attested form passes there, the
        unattested form fails, which is the defect.
        """
        for attested in (True, False):
            with self.subTest(attested=attested):
                full = self._assessable(self.bundle, attested=attested)
                stripped = self._assessable(
                    replace(self.bundle, label_source=""), attested=attested
                )
                self.assertLessEqual(int(stripped), int(full))

    def test_deleting_the_declared_delegations_never_helps(self) -> None:
        for attested in (True, False):
            with self.subTest(attested=attested):
                full = self._assessable(self.bundle, attested=attested)
                stripped = self._assessable(
                    replace(self.bundle, declared_delegations=()), attested=attested
                )
                self.assertLessEqual(int(stripped), int(full))

    def test_deleting_the_task_manifest_never_helps(self) -> None:
        for attested in (True, False):
            with self.subTest(attested=attested):
                full = self._assessable(self.bundle, attested=attested)
                stripped = self._assessable(
                    replace(self.bundle, task_manifest={}), attested=attested
                )
                self.assertLessEqual(int(stripped), int(full))

    def test_withholding_the_attestation_never_helps(self) -> None:
        with_it = audit(
            self.bundle, attestations=self.attestations, as_of=AS_OF
        ).assessable
        without = audit(self.bundle, as_of=AS_OF).assessable
        self.assertLessEqual(int(without), int(with_it))


class AddingGroundsNeverHelps(unittest.TestCase):
    """MR2: every ground is a reason to withhold, so grounds only accumulate."""

    def test_a_weaker_attestation_never_yields_fewer_grounds(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        instrument = bundle.label_source
        strong = audit(
            bundle, attestations={instrument: _attestation(instrument, 0.95)},
            as_of=AS_OF,
        )
        weak = audit(
            bundle, attestations={instrument: _attestation(instrument, 0.10)},
            as_of=AS_OF,
        )
        self.assertLessEqual(len(strong.grounds), len(weak.grounds))

    def test_an_older_attestation_never_yields_fewer_grounds(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        instrument = bundle.label_source
        fresh = audit(
            bundle, attestations={instrument: _attestation(instrument)},
            as_of=AS_OF,
        )
        stale = audit(
            bundle, attestations={instrument: _attestation(instrument)},
            as_of=AS_OF + dt.timedelta(days=4000),
        )
        self.assertLessEqual(len(fresh.grounds), len(stale.grounds))


class OrderAndIdentityDoNotMatter(unittest.TestCase):
    """MR3: the audit reads evidence, not the order it arrived in."""

    def test_reversing_the_event_order_changes_nothing(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        reversed_events = replace(bundle, events=tuple(reversed(bundle.events)))
        self.assertEqual(
            audit(bundle, as_of=AS_OF).grounds,
            audit(reversed_events, as_of=AS_OF).grounds,
        )

    def test_auditing_twice_gives_the_same_answer(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        self.assertEqual(
            audit(bundle, as_of=AS_OF).to_dict(),
            audit(bundle, as_of=AS_OF).to_dict(),
        )


class RemovingPricesNeverStrengthensAClaim(unittest.TestCase):
    """MR4: the general form of D08 and D11.

    Taking the rate card away cannot license a statement about spend that was
    not licensed with it.
    """

    def _bundle(self, *, priced: bool):
        events = (
            _event(0, "chat"), _event(1, "Agent", "tool"),
            _event(2, "chat", cost=18.0 if priced else None),
        )
        return checks_only_bundle(
            events=events,
            outcomes={"t0": Outcome(task_id="t0", acceptable=True)},
            source_id="s.x", dependency_edges=(("e1", "e2"),),
        )

    def test_an_unpriced_trace_never_states_more_spend_than_a_priced_one(self) -> None:
        priced = audit(self._bundle(priced=True), as_of=AS_OF)
        unpriced = audit(self._bundle(priced=False), as_of=AS_OF)
        self.assertTrue(priced.spend_is_priced)
        self.assertFalse(unpriced.spend_is_priced)
        self.assertIsNone(
            unpriced.to_dict()["delegated_spend_unassessed"],
            "a trace nothing priced must not report a spend figure",
        )

    def test_removing_prices_never_increases_assessability(self) -> None:
        priced = audit(self._bundle(priced=True), as_of=AS_OF).assessable
        unpriced = audit(self._bundle(priced=False), as_of=AS_OF).assessable
        self.assertLessEqual(int(unpriced), int(priced))


if __name__ == "__main__":
    unittest.main()
