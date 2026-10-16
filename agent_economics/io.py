from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO

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
        return json.load(handle, object_pairs_hook=_unique_json_object)


def _csv_rows(handle: TextIO) -> Iterator[dict[str, str]]:
    """Reject ambiguous headers and incomplete records before interpreting values.

    DictReader otherwise overwrites duplicate columns and fills truncated rows
    with None. Neither is evidence that an economic quantity was stated as zero.
    Explicit empty cells retain the existing loader semantics.
    """
    reader = csv.DictReader(handle, strict=True)
    try:
        fields = reader.fieldnames
        if not fields or any(not name.strip() for name in fields):
            raise ValueError("CSV requires non-empty column names")
        duplicates = sorted(name for name, count in Counter(fields).items() if count > 1)
        if duplicates:
            raise ValueError(f"CSV contains duplicate columns: {duplicates}")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(
                    f"CSV row ending at line {reader.line_num} has a different "
                    "number of fields than the header"
                )
            yield row
    except csv.Error as error:
        raise ValueError(f"Invalid CSV near line {reader.line_num}: {error}") from error


def load_rates(path: str | Path) -> dict[str, ModelRate]:
    """Load the per-model rate card from JSON, so token counts become money."""
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
        for row in _csv_rows(handle):
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
    """Load per-task outcomes from CSV, keyed by task id."""
    outcomes: dict[str, Outcome] = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in _csv_rows(handle):
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
    """Load the alternative being compared against, usually the human-only
    workflow, from JSON."""
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
    """Load the thresholds a decision will be held to, from JSON."""
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
        for row in _csv_rows(handle):
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
    """Build a bundle from the five CSV and JSON inputs. `label_source` names
    the instrument that produced the outcome labels; the gate wants that
    instrument attested before it counts the labels."""
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


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse duplicate prices or policy fields rather than taking the last one."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result
