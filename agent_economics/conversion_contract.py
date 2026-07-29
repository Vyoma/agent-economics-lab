from __future__ import annotations

import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import Baseline, EconomicPolicy, Outcome, TaskIdentity


def object_without_duplicate_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


def loads_strict_json(raw: str, *, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=object_without_duplicate_keys,
            parse_constant=reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"Invalid {label}: {error}") from error


def load_conversion_contract(path: str | Path) -> dict[str, Any]:
    value = loads_strict_json(
        Path(path).read_text(encoding="utf-8"),
        label=f"conversion contract {str(path)!r}",
    )
    if not isinstance(value, dict):
        raise ValueError("Conversion contract must be a JSON object")
    return value


def nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def nonnegative_number(value: Any, *, label: str) -> float:
    number = finite_number(value, label=label)
    if number < 0:
        raise ValueError(f"{label} must be non-negative")
    return number


def required_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def required_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def required_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def required_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def parse_baseline(raw: Any) -> Baseline:
    baseline = required_mapping(raw, label="baseline")
    return Baseline(
        name=required_string(baseline.get("name"), label="baseline.name"),
        cost_per_attempt_usd=nonnegative_number(
            baseline.get("cost_per_attempt_usd"),
            label="baseline.cost_per_attempt_usd",
        ),
        acceptable_rate=nonnegative_number(
            baseline.get("acceptable_rate"), label="baseline.acceptable_rate"
        ),
        value_per_acceptable_outcome_usd=nonnegative_number(
            baseline.get("value_per_acceptable_outcome_usd"),
            label="baseline.value_per_acceptable_outcome_usd",
        ),
    )


def parse_policy(raw: Any) -> EconomicPolicy:
    policy = required_mapping(raw, label="policy")
    return EconomicPolicy(
        human_hourly_cost_usd=nonnegative_number(
            policy.get("human_hourly_cost_usd"),
            label="policy.human_hourly_cost_usd",
        ),
        min_acceptable_rate=nonnegative_number(
            policy.get("min_acceptable_rate"),
            label="policy.min_acceptable_rate",
        ),
        max_cost_per_acceptable_outcome_usd=nonnegative_number(
            policy.get("max_cost_per_acceptable_outcome_usd"),
            label="policy.max_cost_per_acceptable_outcome_usd",
        ),
        max_p95_task_cost_usd=nonnegative_number(
            policy.get("max_p95_task_cost_usd"),
            label="policy.max_p95_task_cost_usd",
        ),
        max_trace_cost_per_task_usd=nonnegative_number(
            policy.get("max_trace_cost_per_task_usd"),
            label="policy.max_trace_cost_per_task_usd",
        ),
        max_calls_per_task=nonnegative_int(
            policy.get("max_calls_per_task"),
            label="policy.max_calls_per_task",
        ),
        min_expected_net_value_per_attempt_usd=finite_number(
            policy.get("min_expected_net_value_per_attempt_usd"),
            label="policy.min_expected_net_value_per_attempt_usd",
        ),
        min_incremental_net_value_vs_baseline_usd=finite_number(
            policy.get("min_incremental_net_value_vs_baseline_usd"),
            label="policy.min_incremental_net_value_vs_baseline_usd",
        ),
        repetition_warning_threshold=nonnegative_int(
            policy.get("repetition_warning_threshold"),
            label="policy.repetition_warning_threshold",
        ),
    )


def parse_outcomes_and_manifest(
    *,
    raw_tasks: Any,
    outcome_contract_raw: Any,
    expected_tasks: Mapping[str, Mapping[str, str | None]],
) -> tuple[dict[str, Outcome], dict[str, TaskIdentity], str, str]:
    outcome_contract = required_mapping(
        outcome_contract_raw, label="outcome_contract"
    )
    rubric_version = required_string(
        outcome_contract.get("rubric_version"),
        label="outcome_contract.rubric_version",
    )
    label_source = required_string(
        outcome_contract.get("label_source"),
        label="outcome_contract.label_source",
    )
    rows = required_list(raw_tasks, label="tasks")
    rows_by_id: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(rows):
        row = required_mapping(value, label=f"tasks[{index}]")
        task_id = required_string(
            row.get("task_id"), label=f"tasks[{index}].task_id"
        )
        if task_id in rows_by_id:
            raise ValueError(f"Duplicate outcome task ID: {task_id!r}")
        rows_by_id[task_id] = row
    if set(rows_by_id) != set(expected_tasks):
        raise ValueError(
            "Contract task IDs must exactly match the frozen source inventory"
        )

    outcomes: dict[str, Outcome] = {}
    identities: dict[str, TaskIdentity] = {}
    for task_id, expected in expected_tasks.items():
        row = rows_by_id[task_id]
        expected_digest = expected.get("input_digest")
        input_digest = row.get("input_digest")
        if expected_digest is not None and input_digest != expected_digest:
            raise ValueError(f"Task {task_id!r} input_digest does not match source")
        if (
            not isinstance(input_digest, str)
            or len(input_digest) != 64
            or any(character not in "0123456789abcdef" for character in input_digest)
        ):
            raise ValueError(
                f"Task {task_id!r} input_digest must be a lowercase SHA-256 digest"
            )
        if row.get("started_at") != expected.get("started_at"):
            raise ValueError(f"Task {task_id!r} started_at does not match source")
        outcomes[task_id] = Outcome(
            task_id=task_id,
            acceptable=required_bool(
                row.get("acceptable"), label=f"task {task_id} acceptable"
            ),
            business_value_usd=nonnegative_number(
                row.get("business_value_usd"),
                label=f"task {task_id} business_value_usd",
            ),
            human_minutes=nonnegative_number(
                row.get("human_minutes"),
                label=f"task {task_id} human_minutes",
            ),
            remediation_cost_usd=nonnegative_number(
                row.get("remediation_cost_usd"),
                label=f"task {task_id} remediation_cost_usd",
            ),
            incident_loss_usd=nonnegative_number(
                row.get("incident_loss_usd"),
                label=f"task {task_id} incident_loss_usd",
            ),
        )
        identities[task_id] = TaskIdentity(
            task_id=task_id,
            input_digest=input_digest,
            rubric_version=rubric_version,
        )
    return outcomes, identities, rubric_version, label_source
