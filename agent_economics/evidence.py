from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict
from numbers import Integral, Real
from typing import Any, Mapping, Sequence

from .models import (
    Baseline,
    EconomicPolicy,
    EvidenceBundle,
    ModelRate,
    Outcome,
    TaskIdentity,
    TraceEvent,
)


def _is_integer(value: Any) -> bool:
    return isinstance(value, Integral) and not isinstance(value, bool)


def _numeric_issue(
    label: str,
    value: Any,
    *,
    minimum: float | None = 0.0,
    maximum: float | None = None,
    integer: bool = False,
) -> str | None:
    if integer:
        if not _is_integer(value):
            return f"{label} must be an integer"
        number = float(value)
    else:
        if not isinstance(value, Real) or isinstance(value, bool):
            return f"{label} must be a finite number"
        number = float(value)
    if not math.isfinite(number):
        return f"{label} must be finite"
    if minimum is not None and number < minimum:
        return f"{label} must be at least {minimum}"
    if maximum is not None and number > maximum:
        return f"{label} must be no more than {maximum}"
    return None


def validate_evidence_bundle(
    bundle: EvidenceBundle,
    *,
    label: str = "evidence",
    require_explicit_costs: bool = False,
    require_task_manifest: bool = False,
) -> tuple[str, ...]:
    """Validate canonical evidence before an economic decision is issued."""
    problems: list[str] = []
    if not isinstance(bundle, EvidenceBundle):
        return (f"{label}: supplied value is not an EvidenceBundle",)

    event_ids: list[str] = []
    for event in bundle.events:
        if not isinstance(event, TraceEvent):
            problems.append(f"{label}: event is not a TraceEvent")
            continue
        event_label = f"{label}: event {event.event_id!r}"
        if not isinstance(event.task_id, str) or not event.task_id:
            problems.append(f"{event_label} has an invalid task_id")
        if not isinstance(event.event_id, str) or not event.event_id:
            problems.append(f"{label}: event has an invalid event_id")
        else:
            event_ids.append(event.event_id)
        for field, value in (
            ("input_tokens", event.input_tokens),
            ("output_tokens", event.output_tokens),
        ):
            issue = _numeric_issue(
                f"{event_label} {field}", value, minimum=0, integer=True
            )
            if issue:
                problems.append(issue)
        if event.direct_cost_usd is None:
            if event.event_type == "model":
                if event.model not in bundle.rates:
                    problems.append(
                        f"{event_label} has unknown model cost; provide "
                        "direct_cost_usd or a model rate"
                    )
                elif (
                    require_explicit_costs
                    and _is_integer(event.input_tokens)
                    and _is_integer(event.output_tokens)
                    and event.input_tokens + event.output_tokens <= 0
                ):
                    problems.append(
                        f"{event_label} has zero rate-card usage; provide positive "
                        "token usage or an explicit direct_cost_usd"
                    )
            elif require_explicit_costs:
                problems.append(
                    f"{event_label} has unknown cost; provide direct_cost_usd "
                    "(use 0.0 for explicitly included cost) or a model rate"
                )
        else:
            issue = _numeric_issue(
                f"{event_label} direct_cost_usd", event.direct_cost_usd
            )
            if issue:
                problems.append(issue)

    event_id_counts = Counter(event_ids)
    duplicate_event_ids = sorted(
        event_id for event_id, count in event_id_counts.items() if count > 1
    )
    if duplicate_event_ids:
        problems.append(f"{label}: duplicate event IDs: {duplicate_event_ids}")

    for model, rate in bundle.rates.items():
        if not isinstance(model, str) or not model:
            problems.append(f"{label}: model-rate IDs must be non-empty strings")
        if not isinstance(rate, ModelRate):
            problems.append(f"{label}: rate {model!r} is not a ModelRate")
            continue
        for field, value in (
            ("input_per_million_usd", rate.input_per_million_usd),
            ("output_per_million_usd", rate.output_per_million_usd),
        ):
            issue = _numeric_issue(f"{label}: rate {model!r} {field}", value)
            if issue:
                problems.append(issue)

    for task_id, outcome in bundle.outcomes.items():
        if not isinstance(outcome, Outcome):
            problems.append(f"{label}: outcome {task_id!r} is not an Outcome")
            continue
        outcome_label = f"{label}: outcome {task_id!r}"
        if not isinstance(task_id, str) or not task_id:
            problems.append(f"{outcome_label} has an invalid task ID")
        if task_id != outcome.task_id:
            problems.append(f"{outcome_label} key does not match its task_id")
        if not isinstance(outcome.acceptable, bool):
            problems.append(f"{outcome_label} acceptable must be boolean")
        for field, value in (
            ("business_value_usd", outcome.business_value_usd),
            ("human_minutes", outcome.human_minutes),
            ("remediation_cost_usd", outcome.remediation_cost_usd),
            ("incident_loss_usd", outcome.incident_loss_usd),
        ):
            issue = _numeric_issue(f"{outcome_label} {field}", value)
            if issue:
                problems.append(issue)

    event_task_ids = {
        event.task_id for event in bundle.events if isinstance(event, TraceEvent)
    }
    outcome_task_ids = set(bundle.outcomes)
    if event_task_ids != outcome_task_ids:
        problems.append(
            f"{label}: trace and outcome task IDs must exactly match"
        )

    manifest_task_ids = set(bundle.task_manifest)
    if require_task_manifest and not manifest_task_ids:
        problems.append(f"{label}: task manifest is required")
    if manifest_task_ids and (
        manifest_task_ids != outcome_task_ids or manifest_task_ids != event_task_ids
    ):
        problems.append(
            f"{label}: task manifest must exactly cover trace and outcome task IDs"
        )
    for task_id, identity in bundle.task_manifest.items():
        if not isinstance(identity, TaskIdentity):
            problems.append(
                f"{label}: task manifest {task_id!r} is not a TaskIdentity"
            )
            continue
        identity_label = f"{label}: task manifest {task_id!r}"
        if task_id != identity.task_id:
            problems.append(f"{identity_label} key does not match its task_id")
        if (
            not isinstance(identity.input_digest, str)
            or len(identity.input_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in identity.input_digest
            )
        ):
            problems.append(
                f"{identity_label} input_digest must be a lowercase SHA-256 digest"
            )
        if not isinstance(identity.rubric_version, str) or not identity.rubric_version:
            problems.append(
                f"{identity_label} rubric_version must be a non-empty string"
            )

    baseline = bundle.baseline
    if not isinstance(baseline, Baseline):
        problems.append(f"{label}: baseline is not a Baseline")
    else:
        if not isinstance(baseline.name, str) or not baseline.name:
            problems.append(f"{label}: baseline name must be a non-empty string")
        for field, value in (
            ("cost_per_attempt_usd", baseline.cost_per_attempt_usd),
            (
                "value_per_acceptable_outcome_usd",
                baseline.value_per_acceptable_outcome_usd,
            ),
        ):
            issue = _numeric_issue(f"{label}: baseline {field}", value)
            if issue:
                problems.append(issue)
        issue = _numeric_issue(
            f"{label}: baseline acceptable_rate",
            baseline.acceptable_rate,
            minimum=0.0,
            maximum=1.0,
        )
        if issue:
            problems.append(issue)
        elif baseline.acceptable_rate == 0:
            problems.append(
                f"{label}: baseline acceptable_rate must be greater than zero"
            )

    policy = bundle.policy
    if not isinstance(policy, EconomicPolicy):
        problems.append(f"{label}: policy is not an EconomicPolicy")
    else:
        for field in (
            "human_hourly_cost_usd",
            "max_cost_per_acceptable_outcome_usd",
            "max_p95_task_cost_usd",
            "max_trace_cost_per_task_usd",
        ):
            issue = _numeric_issue(
                f"{label}: policy {field}", getattr(policy, field)
            )
            if issue:
                problems.append(issue)
        for field in (
            "min_expected_net_value_per_attempt_usd",
            "min_incremental_net_value_vs_baseline_usd",
        ):
            issue = _numeric_issue(
                f"{label}: policy {field}", getattr(policy, field), minimum=None
            )
            if issue:
                problems.append(issue)
        issue = _numeric_issue(
            f"{label}: policy min_acceptable_rate",
            policy.min_acceptable_rate,
            minimum=0.0,
            maximum=1.0,
        )
        if issue:
            problems.append(issue)
        for field in ("max_calls_per_task", "repetition_warning_threshold"):
            issue = _numeric_issue(
                f"{label}: policy {field}",
                getattr(policy, field),
                minimum=1.0,
                integer=True,
            )
            if issue:
                problems.append(issue)

    return tuple(problems)


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
    bundle = EvidenceBundle(
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
    problems = validate_evidence_bundle(bundle)
    if problems:
        raise ValueError("Invalid evidence bundle: " + "; ".join(problems))
    return bundle
