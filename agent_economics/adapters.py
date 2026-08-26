from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

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


def _object_without_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


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
    conversion = raw.get("conversion")
    if conversion is None:
        source_id = "source.normalized-json"
        source_version = "1"
    else:
        if not isinstance(conversion, Mapping):
            raise ValueError("conversion must be an object")
        source_id = conversion.get("source_id")
        source_version = conversion.get("source_version")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("conversion.source_id must be a non-empty string")
        if not isinstance(source_version, str) or not source_version:
            raise ValueError("conversion.source_version must be a non-empty string")
    bundle = make_evidence_bundle(
        events=events,
        outcomes=outcomes,
        rates=rates,
        baseline=Baseline(**raw["baseline"]),
        policy=EconomicPolicy(**raw["policy"]),
        source_id=source_id,
        source_version=source_version,
        task_manifest=task_manifest,
        declared_delegations=tuple(raw.get("declared_delegations", ())),
        dependency_edges=tuple(
            tuple(edge) for edge in raw.get("dependency_edges", ())
        ),
    )
    if conversion is not None:
        expected_digest = conversion.get("evidence_digest")
        if expected_digest != bundle.digest:
            raise ValueError(
                "conversion.evidence_digest does not match normalized evidence"
            )
    return bundle


def normalized_json_document(
    bundle: EvidenceBundle,
    *,
    conversion: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a bundle into the stable offline interchange document."""
    document: dict[str, Any] = {
        "events": [asdict(event) for event in bundle.events],
        "outcomes": [
            asdict(bundle.outcomes[task_id]) for task_id in sorted(bundle.outcomes)
        ],
        "rates": {
            name: asdict(bundle.rates[name]) for name in sorted(bundle.rates)
        },
        "baseline": asdict(bundle.baseline),
        "policy": asdict(bundle.policy),
    }
    if bundle.declared_delegations:
        document["declared_delegations"] = list(bundle.declared_delegations)
    if bundle.task_manifest:
        document["task_manifest"] = [
            asdict(bundle.task_manifest[task_id])
            for task_id in sorted(bundle.task_manifest)
        ]
    if bundle.dependency_edges:
        document["dependency_edges"] = [
            list(edge) for edge in bundle.dependency_edges
        ]
    if conversion is not None:
        document["conversion"] = dict(conversion)
    return document


def render_normalized_json(
    bundle: EvidenceBundle,
    *,
    conversion: Mapping[str, Any] | None = None,
) -> str:
    """Render a deterministic normalized JSON document."""
    return (
        json.dumps(
            normalized_json_document(bundle, conversion=conversion),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def load_normalized_json_bundle(path: str | Path) -> EvidenceBundle:
    """Load the canonical offline interchange format used by source adapters."""
    try:
        raw = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"Invalid normalized JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError("Normalized JSON must be an object")
    return normalized_json_bundle(raw)
