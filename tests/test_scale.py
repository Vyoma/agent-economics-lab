"""The scale layer's guards: identity under optimization, honesty under depth.

Every optimization in the scale pass claimed to change nothing observable.
These tests hold each claim to that: the hand-rolled digest serialization is
byte-identical to the generic form it replaced, the audit's digest reuse
yields the same digest the bundle derives from content, and cycle detection
survives dependency chains far past Python's recursion limit — the depth at
which the old detector died and had its corpse reported as "diagnostic could
not run".
"""

from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import asdict

from agent_economics.audit import decide
from agent_economics.controls import find_directed_cycles
from agent_economics.delegation import assess_closure
from agent_economics.evidence import make_evidence_bundle
from agent_economics.models import (
    Baseline,
    EconomicPolicy,
    ModelRate,
    Outcome,
    TraceEvent,
    bundle_digest_of,
)


def _bundle(events, **overrides):
    keywords = dict(
        events=events,
        outcomes={
            e.task_id: Outcome(task_id=e.task_id, acceptable=True,
                               business_value_usd=5.0, human_minutes=1.0)
            for e in events
        },
        rates={"m": ModelRate(3.0, 15.0)},
        baseline=Baseline("human", 5.0, 0.9, 8.0),
        policy=EconomicPolicy(
            human_hourly_cost_usd=90.0,
            min_acceptable_rate=0.5,
            max_cost_per_acceptable_outcome_usd=10.0,
            max_p95_task_cost_usd=5.0,
            max_trace_cost_per_task_usd=5.0,
            max_calls_per_task=50,
        ),
        source_id="test.scale",
    )
    keywords.update(overrides)
    return make_evidence_bundle(**keywords)


class DigestSerializationIsByteIdentical(unittest.TestCase):
    """The fast event serialization must reproduce the asdict payload exactly.

    Every published claim's evidence digest depends on this identity; a
    silent divergence would refute the entire ledger at once.
    """

    def test_field_access_equals_asdict_for_awkward_values(self) -> None:
        events = (
            TraceEvent(
                task_id="t1", event_id="e1", timestamp="2026-01-01T00:00:00Z",
                event_type="model", name="completion", model="m",
                input_tokens=10, output_tokens=3, direct_cost_usd=None,
                status="ok",
                arguments={"nested": {"z": [1, 2, {"k": "v"}], "a": None}},
            ),
            TraceEvent(
                task_id="t2", event_id="e2", timestamp="2026-01-01T00:00:01Z",
                event_type="tool_call", name="Task", direct_cost_usd=0.25,
                status="error", arguments={},
            ),
        )
        reference = json.dumps(
            [asdict(e) for e in events],
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        bundle = _bundle(events, label_source="test.instrument")
        recomputed = bundle_digest_of(
            bundle.events, bundle.outcomes, bundle.rates, bundle.baseline,
            bundle.policy, bundle.task_manifest, bundle.dependency_edges,
            bundle.declared_delegations, bundle.label_source,
        )
        # Rebuild the digest with the asdict reference payload for events and
        # require equality with the shipped implementation.
        payload = {
            "events": [asdict(e) for e in bundle.events],
            "outcomes": [asdict(bundle.outcomes[t]) for t in sorted(bundle.outcomes)],
            "rates": {n: asdict(bundle.rates[n]) for n in sorted(bundle.rates)},
            "baseline": asdict(bundle.baseline),
            "policy": asdict(bundle.policy),
        }
        payload["label_source"] = bundle.label_source
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        self.assertEqual(recomputed, hashlib.sha256(encoded).hexdigest())
        self.assertIn('"nested"', reference)  # the awkward value actually ran

    def test_every_traceevent_field_is_serialized(self) -> None:
        """A field added to TraceEvent must land in the digest or be refused.

        The fast path lists fields by hand; this catches the drift where a
        new field silently never reaches the hash.
        """
        from dataclasses import fields

        listed = {
            "task_id", "event_id", "timestamp", "event_type", "name", "model",
            "input_tokens", "output_tokens", "direct_cost_usd", "status",
            "arguments",
        }
        actual = {f.name for f in fields(TraceEvent)}
        self.assertEqual(
            actual, listed,
            "TraceEvent's fields changed; update the serialization in "
            "bundle_digest_of and then this list",
        )


class TheAuditHashesTheEvidenceOnce(unittest.TestCase):
    def test_decide_publishes_the_content_derived_digest(self) -> None:
        events = (
            TraceEvent(task_id="t1", event_id="e1",
                       timestamp="2026-01-01T00:00:00Z", event_type="model",
                       name="completion", model="m", input_tokens=10,
                       output_tokens=5),
        )
        bundle = _bundle(events)
        case, _ = decide(bundle)
        self.assertEqual(case.evidence_digest, bundle.digest)


class DepthDoesNotKillTheDiagnostics(unittest.TestCase):
    def test_cycle_detection_on_a_chain_past_the_recursion_limit(self) -> None:
        """The recursive detector died at ~1,000 and the engine reported the
        corpse as 'diagnostic could not run'. 50,000 is comfortably past any
        configured recursion limit."""
        chain = [(f"n{i}", f"n{i + 1}") for i in range(50_000)]
        self.assertEqual(find_directed_cycles(chain), [])
        with_back_edge = [*chain, ("n49999", "n40000")]
        cycles = find_directed_cycles(with_back_edge)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(len(cycles[0]), 10_000)

    def test_closure_on_a_deep_delegation_chain_still_answers(self) -> None:
        n = 4_000
        events = [
            TraceEvent(task_id="t", event_id=f"e{i}",
                       timestamp="2026-01-01T00:00:00Z",
                       event_type="tool_call", name="Task",
                       direct_cost_usd=0.01)
            for i in range(n)
        ]
        edges = [(f"e{i}", f"e{i + 1}") for i in range(n - 1)]
        report = assess_closure(
            events, edges, delegation_tools=("Task",), declared=()
        )
        self.assertEqual(report.basis, "cost")
        self.assertEqual(report.closure, 0.0)


if __name__ == "__main__":
    unittest.main()
