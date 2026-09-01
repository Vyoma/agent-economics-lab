"""Defects found by the pre-registered search, not by suspicion.

`research/probe_sites.py` was committed before these probes were written. It
enumerates divergences: one quantity computed two ways, which is the form all
five retrospective defects shared. Eighteen divergences, two real defects.

Both are regression-tested here. The sixteen that found nothing are recorded in
research/PROBE_RESULTS.md, because a search that reports only its hits has no
denominator and cannot be assessed.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace

from agent_economics import load_normalized_json_bundle
from agent_economics.audit import audit
from agent_economics.delegation import (
    UnaccountedDelegation,
    assess_bundle_closure,
    delegation_closure_gate,
)
from agent_economics.io import load_csv_bundle
from agent_economics.provenance import (
    UnattestedInstrument,
    evidence_provenance_gate,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "claude-code" / "bundle.json"

TRACE_HEADER = [
    "task_id", "event_id", "timestamp", "event_type", "name", "model",
    "input_tokens", "output_tokens", "direct_cost_usd", "parent_event_id",
]
# Two subagent calls carrying $500 of model work between them.
TRACE_ROWS = [
    ["t0", "e0", "2026-08-27T00:00:00Z", "model", "chat", "m", 100, 10, "1.00", ""],
    ["t0", "e1", "2026-08-27T00:00:01Z", "tool", "Agent", "", 0, 0, "0.0", ""],
    ["t0", "e2", "2026-08-27T00:00:02Z", "model", "chat", "m", 900000, 900000, "250.00", "e1"],
    ["t0", "e3", "2026-08-27T00:00:03Z", "tool", "Agent", "", 0, 0, "0.0", ""],
    ["t0", "e4", "2026-08-27T00:00:04Z", "model", "chat", "m", 900000, 900000, "250.00", "e3"],
]


def _csv_bundle(directory: pathlib.Path, *, with_edges: bool):
    header = TRACE_HEADER if with_edges else TRACE_HEADER[:-1]
    traces = directory / "traces.csv"
    with traces.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in TRACE_ROWS:
            writer.writerow(row if with_edges else row[:-1])
    (directory / "outcomes.csv").write_text(
        "task_id,acceptable,business_value_usd,human_minutes,remediation_cost_usd,incident_loss_usd\n" "t0,true,10,,,\n", encoding="utf-8"
    )
    reference = load_normalized_json_bundle(EXAMPLE)
    for name, payload in (
        ("rates.json", {"m": {"input_per_million_usd": 3.0,
                              "output_per_million_usd": 15.0}}),
        ("baseline.json", _as_dict(reference.baseline)),
        ("policy.json", _as_dict(reference.policy)),
    ):
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")
    return load_csv_bundle(
        traces=traces, outcomes=directory / "outcomes.csv",
        rates=directory / "rates.json", baseline=directory / "baseline.json",
        policy=directory / "policy.json",
    )


def _as_dict(value):
    import dataclasses
    return dataclasses.asdict(value)


class TheCsvPathCouldNotSeeDelegation(unittest.TestCase):
    """Finding 1. The largest of the eleven, and on a documented input path.

    `load_csv_bundle` never passed `dependency_edges`, and the CSV schema had no
    column able to carry them. A trace with two `Agent` calls and $500 of
    subagent spend reported zero delegations, 100% closure, and the gate passed
    saying "no delegation in this run".
    """

    def test_the_schema_can_now_carry_the_graph(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            bundle = _csv_bundle(pathlib.Path(raw), with_edges=True)
        self.assertEqual(len(bundle.dependency_edges), 2)
        report = assess_bundle_closure(bundle)
        self.assertEqual(len(report.delegations), 2)
        self.assertAlmostEqual(report.unaccounted_cost_usd, 500.0)

    def test_a_trace_that_cannot_express_its_graph_is_refused(self) -> None:
        """Silence is not absence.

        Without the column the delegation calls are still visible; what is
        missing is their extent. Reporting "no delegation" collapses "nothing
        was delegated" into "the graph was not captured".
        """
        with tempfile.TemporaryDirectory() as raw:
            bundle = _csv_bundle(pathlib.Path(raw), with_edges=False)
        view = SimpleNamespace(
            events=bundle.events, dependency_edges=bundle.dependency_edges,
            rates=bundle.rates,
        )
        with self.assertRaises(UnaccountedDelegation) as caught:
            delegation_closure_gate().run(view)
        self.assertIn("spawned no recorded work", str(caught.exception))

    def test_the_gate_still_passes_a_genuinely_undelegating_run(self) -> None:
        """The refusal must key on delegation tools, not on an empty graph."""
        bundle = load_normalized_json_bundle(EXAMPLE)
        view = SimpleNamespace(
            events=bundle.events, dependency_edges=bundle.dependency_edges,
            rates=bundle.rates,
        )
        output = delegation_closure_gate().run(view)
        self.assertTrue(output.results)


class TheAuditPromisedWhatTheGateRefused(unittest.TestCase):
    """Finding 2. The sole-provider carve-out was reachable from one path only.

    `evidence_provenance_gate` never accepted `independently_verified`, so an
    instrument corroborated by something else was exempt in the audit and
    rejected by the gate. It errs safe, but the audit reads as a prediction of
    the gate and was not one.
    """

    def test_the_audit_and_the_gate_agree_on_a_corroborated_instrument(self) -> None:
        bundle = load_normalized_json_bundle(EXAMPLE)
        instrument = bundle.label_source
        self.assertTrue(instrument, "fixture must name its label source")

        report = audit(bundle, independently_verified=(instrument,))
        spec = evidence_provenance_gate(
            instruments=(instrument,), attestations={},
            as_of=dt.date(2026, 8, 27),
            independently_verified=(instrument,),
        )
        gate_accepted = True
        try:
            spec.run(None)
        except UnattestedInstrument:
            gate_accepted = False
        self.assertEqual(report.assessable, gate_accepted)

    def test_an_uncorroborated_instrument_is_still_refused(self) -> None:
        spec = evidence_provenance_gate(
            instruments=("some.instrument",), attestations={},
            as_of=dt.date(2026, 8, 27),
        )
        with self.assertRaises(UnattestedInstrument):
            spec.run(None)


if __name__ == "__main__":
    unittest.main()
