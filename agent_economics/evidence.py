from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from typing import Mapping, Sequence

from .models import (
    Baseline,
    EconomicPolicy,
    EvidenceBundle,
    ModelRate,
    Outcome,
    TraceEvent,
)


def _canonical_digest(
    events: tuple[TraceEvent, ...],
    outcomes: dict[str, Outcome],
    rates: dict[str, ModelRate],
    baseline: Baseline,
    policy: EconomicPolicy,
) -> str:
    payload = {
        "events": [asdict(event) for event in events],
        "outcomes": [asdict(outcomes[task_id]) for task_id in sorted(outcomes)],
        "rates": {name: asdict(rates[name]) for name in sorted(rates)},
        "baseline": asdict(baseline),
        "policy": asdict(policy),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_evidence_bundle(
    *,
    events: Sequence[TraceEvent],
    outcomes: Mapping[str, Outcome],
    rates: Mapping[str, ModelRate],
    baseline: Baseline,
    policy: EconomicPolicy,
    source_id: str,
    source_version: str = "1",
) -> EvidenceBundle:
    """Normalize and fingerprint evidence without depending on its source vendor."""
    event_id_counts = Counter(event.event_id for event in events)
    duplicate_events = sorted(
        event_id for event_id, count in event_id_counts.items() if count > 1
    )
    if duplicate_events:
        raise ValueError(f"Duplicate event IDs: {duplicate_events}")

    normalized_events = tuple(
        sorted(events, key=lambda event: (event.task_id, event.timestamp, event.event_id))
    )
    normalized_outcomes = dict(sorted(outcomes.items()))
    normalized_rates = dict(sorted(rates.items()))
    digest = _canonical_digest(
        normalized_events,
        normalized_outcomes,
        normalized_rates,
        baseline,
        policy,
    )
    return EvidenceBundle(
        events=normalized_events,
        outcomes=normalized_outcomes,
        rates=normalized_rates,
        baseline=baseline,
        policy=policy,
        source_id=source_id,
        source_version=source_version,
        digest=digest,
    )
