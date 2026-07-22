from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .evidence import make_evidence_bundle
from .models import (
    Baseline,
    EconomicPolicy,
    EvidenceBundle,
    ModelRate,
    Outcome,
    TaskIdentity,
    TraceEvent,
)


def normalized_json_bundle(raw: Mapping[str, Any]) -> EvidenceBundle:
    """Normalize an already-decoded canonical interchange document."""
    events = [TraceEvent(**event) for event in raw["events"]]
    outcome_rows = [Outcome(**outcome) for outcome in raw["outcomes"]]
    outcomes: dict[str, Outcome] = {}
    for outcome in outcome_rows:
        if outcome.task_id in outcomes:
            raise ValueError(f"Duplicate outcome task ID: {outcome.task_id!r}")
        outcomes[outcome.task_id] = outcome
    rates = {
        name: ModelRate(**values) for name, values in raw["rates"].items()
    }
    task_manifest: dict[str, TaskIdentity] = {}
    for row in raw.get("task_manifest", ()):
        identity = TaskIdentity(**row)
        if identity.task_id in task_manifest:
            raise ValueError(f"Duplicate task manifest ID: {identity.task_id!r}")
        task_manifest[identity.task_id] = identity
    return make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=Baseline(**raw["baseline"]),
        policy=EconomicPolicy(**raw["policy"]),
        source_id="source.normalized-json",
        source_version="1",
        task_manifest=task_manifest,
    )


def load_normalized_json_bundle(path: str | Path) -> EvidenceBundle:
    """Load the canonical offline interchange format used by source adapters."""
    with Path(path).open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return normalized_json_bundle(raw)
