from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence import make_evidence_bundle
from .models import (
    Baseline,
    EconomicPolicy,
    EvidenceBundle,
    ModelRate,
    Outcome,
    TraceEvent,
)


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_rates(path: str | Path) -> dict[str, ModelRate]:
    raw = _load_json(path)
    return {
        name: ModelRate(
            input_per_million_usd=float(values["input_per_million_usd"]),
            output_per_million_usd=float(values["output_per_million_usd"]),
        )
        for name, values in raw.items()
    }


def load_traces(path: str | Path) -> list[TraceEvent]:
    """Read trace events. `parent_event_id`, where present, builds the graph."""
    events: list[TraceEvent] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            direct = row.get("direct_cost_usd", "").strip()
            raw_arguments = row.get("arguments", "").strip()
            try:
                arguments = json.loads(raw_arguments) if raw_arguments else {}
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid arguments JSON on event {row.get('event_id')!r}"
                ) from error
            events.append(
                TraceEvent(
                    task_id=row["task_id"],
                    event_id=row["event_id"],
                    timestamp=row.get("timestamp", ""),
                    event_type=row["event_type"],
                    name=row["name"],
                    model=row.get("model", ""),
                    input_tokens=int(row.get("input_tokens") or 0),
                    output_tokens=int(row.get("output_tokens") or 0),
                    direct_cost_usd=float(direct) if direct else None,
                    status=row.get("status", "ok"),
                    arguments=arguments,
                )
            )
    event_id_counts = Counter(event.event_id for event in events)
    duplicates = sorted(
        event_id for event_id, count in event_id_counts.items() if count > 1
    )
    if duplicates:
        raise ValueError(f"Duplicate event IDs: {duplicates}")
    return events


#: Outcome columns that price the decision. Absence of any of them is refused
#: rather than defaulted, because a file that is silent about incident loss has
#: not said there was none.
_OUTCOME_ECONOMICS = (
    "business_value_usd",
    "human_minutes",
    "remediation_cost_usd",
    "incident_loss_usd",
)


def load_outcomes(path: str | Path) -> dict[str, Outcome]:
    outcomes: dict[str, Outcome] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            task_id = row["task_id"]
            if task_id in outcomes:
                raise ValueError(f"Duplicate outcome task ID: {task_id!r}")
            acceptable_text = row["acceptable"].strip().lower()
            if acceptable_text not in {"0", "1", "false", "true", "no", "yes"}:
                raise ValueError(
                    f"Invalid acceptable value for task {task_id!r}: "
                    f"{row['acceptable']!r}"
                )
            # A column absent from the header is not a stated zero. Every one
            # of these carries economic weight -- incident loss is the entire
            # tail-risk term -- and `row.get(...) or 0` made an outcomes file
            # that never mentions them indistinguishable from one that declares
            # them all zero. That is the same fabrication refused for token
            # counts in evidence.py, on the outcome side.
            #
            # An empty cell is still allowed and still means zero: that is a
            # value the file stated. Only silence about the column is refused.
            missing = [name for name in _OUTCOME_ECONOMICS if name not in row]
            if missing:
                raise ValueError(
                    f"outcomes file is missing column(s) {', '.join(missing)}. "
                    "A file that does not mention them has not stated they are "
                    "zero, and they price the decision. Add the column(s), "
                    "leaving cells empty where the value really is zero."
                )
            outcomes[task_id] = Outcome(
                task_id=task_id,
                acceptable=acceptable_text in {"1", "true", "yes"},
                business_value_usd=float(row.get("business_value_usd") or 0),
                human_minutes=float(row.get("human_minutes") or 0),
                remediation_cost_usd=float(row.get("remediation_cost_usd") or 0),
                incident_loss_usd=float(row.get("incident_loss_usd") or 0),
            )
    return outcomes


def load_baseline(path: str | Path) -> Baseline:
    raw = _load_json(path)
    return Baseline(
        name=raw["name"],
        cost_per_attempt_usd=float(raw["cost_per_attempt_usd"]),
        acceptable_rate=float(raw["acceptable_rate"]),
        value_per_acceptable_outcome_usd=float(
            raw["value_per_acceptable_outcome_usd"]
        ),
    )


def load_policy(path: str | Path) -> EconomicPolicy:
    raw = _load_json(path)
    return EconomicPolicy(**raw)


def load_dependency_edges(path: str | Path) -> tuple[tuple[str, str], ...]:
    """Parent/child edges from the optional `parent_event_id` column.

    Without this the CSV path could not express delegation at all, so a trace
    containing subagent calls reported no delegation and the closure gate passed
    on it. A format that cannot say a thing is not evidence that the thing did
    not happen.
    """
    edges: list[tuple[str, str]] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            parent = (row.get("parent_event_id") or "").strip()
            if parent:
                edges.append((parent, row["event_id"]))
    return tuple(edges)


def load_csv_bundle(
    *,
    traces: str | Path,
    outcomes: str | Path,
    rates: str | Path,
    baseline: str | Path,
    policy: str | Path,
    label_source: str = "",
) -> EvidenceBundle:
    return make_evidence_bundle(
        events=load_traces(traces),
        outcomes=load_outcomes(outcomes),
        rates=load_rates(rates),
        baseline=load_baseline(baseline),
        policy=load_policy(policy),
        dependency_edges=load_dependency_edges(traces),
        source_id="source.csv",
        source_version="1",
        label_source=label_source,
    )
