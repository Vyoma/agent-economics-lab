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
    TaskIdentity,
    TraceEvent,
)


def _canonical_digest(
    events: tuple[TraceEvent, ...],
    outcomes: dict[str, Outcome],
    rates: dict[str, ModelRate],
    baseline: Baseline,
    policy: EconomicPolicy,
    task_manifest: dict[str, TaskIdentity],
) -> str:
    payload = {
        "events": [asdict(event) for event in events],
        "outcomes": [asdict(outcomes[task_id]) for task_id in sorted(outcomes)],
        "rates": {name: asdict(rates[name]) for name in sorted(rates)},
        "baseline": asdict(baseline),
        "policy": asdict(policy),
    }
    if task_manifest:
        payload["task_manifest"] = [
            asdict(task_manifest[task_id]) for task_id in sorted(task_manifest)
        ]
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
    task_manifest: Mapping[str, TaskIdentity] | None = None,
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
    normalized_task_manifest = dict(sorted((task_manifest or {}).items()))
    for task_id, identity in normalized_task_manifest.items():
        if task_id != identity.task_id:
            raise ValueError(
                f"Task manifest key {task_id!r} does not match {identity.task_id!r}"
            )
    digest = _canonical_digest(
        normalized_events,
        normalized_outcomes,
        normalized_rates,
        baseline,
        policy,
        normalized_task_manifest,
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
        task_manifest=normalized_task_manifest,
    )
