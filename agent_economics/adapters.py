from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .evidence import make_evidence_bundle
from .models import Baseline, EconomicPolicy, EvidenceBundle, ModelRate, Outcome, TraceEvent


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
    return make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=Baseline(**raw["baseline"]),
        policy=EconomicPolicy(**raw["policy"]),
        source_id="source.normalized-json",
        source_version="1",
    )


def load_normalized_json_bundle(path: str | Path) -> EvidenceBundle:
    """Load the canonical offline interchange format used by source adapters."""
    with Path(path).open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return normalized_json_bundle(raw)
