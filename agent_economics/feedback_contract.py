from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "production-feedback-contract/v1"
MODALITIES = frozenset({"predictive", "generative", "agent"})
INTERVENTION_LAYERS = frozenset(
    {"data", "model", "retrieval", "tool", "routing", "policy"}
)
MISSING_ROUTES = frozenset({"INCOMPLETE", "ABSTAIN", "HUMAN_REVIEW"})

_MODALITY_FIELDS: dict[str, frozenset[str]] = {
    "predictive": frozenset({"calibration", "threshold_policy", "drift_slices"}),
    "generative": frozenset(
        {"prompt_version", "retrieval_version", "task_outcome"}
    ),
    "agent": frozenset(
        {"tool_registry_version", "side_effect_ledger", "human_handoff"}
    ),
}

_BLANK_CONTRACT: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "contract_id": "",
    "system": {
        "name": "",
        "unit_of_decision": "",
        "owner": "",
        "modalities": [],
        "model_versions": [],
        "policy_version": "",
        "observation_window": {"start": "", "end": ""},
    },
    "outcome": {
        "name": "",
        "definition_version": "",
        "source": "",
        "acceptable_when": "",
        "available_after": "",
        "missing_route": "",
    },
    "proxies": [],
    "joins": {
        "decision_id": "",
        "outcome_id": "",
        "deduplication": "",
        "late_data": "",
        "unmatched_route": "",
    },
    "modality_evidence": {},
    "interventions": [],
    "rollout": {
        "counterfactual": "",
        "canary": "",
        "advance_when": "",
        "rollback_when": "",
        "reviewer": "",
    },
    "non_claims": [],
    "reproduction": {"revision": "", "command": "", "environment": ""},
}


def blank_feedback_contract() -> dict[str, Any]:
    """Return a fresh, intentionally incomplete feedback-loop contract."""

    return deepcopy(_BLANK_CONTRACT)


def render_blank_feedback_contract() -> str:
    """Render the intentionally incomplete template as stable JSON."""

    return json.dumps(blank_feedback_contract(), indent=2, ensure_ascii=False) + "\n"


def load_feedback_contract(path: str | Path) -> dict[str, Any]:
    """Load JSON without silently accepting duplicates or non-finite numbers."""

    payload = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_object_without_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(payload, dict):
        raise ValueError("feedback contract must be a JSON object")
    return payload


def feedback_contract_digest(document: Any) -> str:
    """Hash one valid contract after canonical JSON serialization."""

    errors = validate_feedback_contract(document)
    if errors:
        raise ValueError("invalid feedback contract: " + "; ".join(errors))
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_feedback_contract(document: Any) -> tuple[str, ...]:
    """Validate a closed cross-modality production-feedback contract.

    The validator establishes structural completeness and binds every declared
    modality to its own evidence surface. It does not validate the truth of the
    outcome, proxy, or rollout assertions supplied by the issuer.
    """

    errors: list[str] = []
    if not isinstance(document, dict):
        return ("feedback contract must be a JSON object",)

    _reject_unknown(document, frozenset(_BLANK_CONTRACT), errors)
    _expect_exact(document, "schema_version", SCHEMA_VERSION, errors)
    _expect_string(document, "contract_id", errors)

    system = _expect_object(document, "system", errors)
    _reject_unknown(system, frozenset(_BLANK_CONTRACT["system"]), errors, "system")
    for field in ("name", "unit_of_decision", "owner", "policy_version"):
        _expect_string(system, field, errors, "system")
    _expect_string_list(system, "model_versions", errors, "system", non_empty=True)
    modalities = _expect_string_list(
        system, "modalities", errors, "system", non_empty=True
    )
    modality_set = set(modalities)
    unknown_modalities = modality_set - MODALITIES
    if unknown_modalities:
        errors.append(
            "system.modalities contains unsupported values: "
            + ", ".join(sorted(unknown_modalities))
        )
    if len(modalities) != len(modality_set):
        errors.append("system.modalities must not contain duplicates")
    window = _expect_object(system, "observation_window", errors, "system")
    _reject_unknown(
        window,
        frozenset({"start", "end"}),
        errors,
        "system.observation_window",
    )
    start = _expect_date(window, "start", errors, "system.observation_window")
    end = _expect_date(window, "end", errors, "system.observation_window")
    if start and end and start > end:
        errors.append("system.observation_window.start must not be after end")

    outcome = _expect_object(document, "outcome", errors)
    _reject_unknown(outcome, frozenset(_BLANK_CONTRACT["outcome"]), errors, "outcome")
    for field in (
        "name",
        "definition_version",
        "source",
        "acceptable_when",
        "available_after",
    ):
        _expect_string(outcome, field, errors, "outcome")
    outcome_name = outcome.get("name") if isinstance(outcome.get("name"), str) else ""
    _expect_enum(outcome, "missing_route", MISSING_ROUTES, errors, "outcome")

    proxies = _expect_list(document, "proxies", errors)
    proxy_names: set[str] = set()
    for index, proxy in enumerate(proxies):
        prefix = f"proxies[{index}]"
        if not isinstance(proxy, dict):
            errors.append(f"{prefix} must be an object")
            continue
        _reject_unknown(
            proxy,
            frozenset(
                {
                    "name",
                    "source",
                    "validated_against",
                    "agreement_measure",
                    "failure_modes",
                    "allowed_uses",
                    "forbidden_uses",
                }
            ),
            errors,
            prefix,
        )
        name = _expect_string(proxy, "name", errors, prefix)
        if name:
            if name in proxy_names:
                errors.append(f"{prefix}.name must be unique: {name!r}")
            proxy_names.add(name)
        _expect_string(proxy, "source", errors, prefix)
        validated_against = _expect_string(
            proxy, "validated_against", errors, prefix
        )
        if validated_against and outcome_name and validated_against != outcome_name:
            errors.append(
                f"{prefix}.validated_against must name outcome.name "
                f"{outcome_name!r}"
            )
        _expect_string(proxy, "agreement_measure", errors, prefix)
        for field in ("failure_modes", "allowed_uses", "forbidden_uses"):
            _expect_string_list(proxy, field, errors, prefix, non_empty=True)

    joins = _expect_object(document, "joins", errors)
    _reject_unknown(joins, frozenset(_BLANK_CONTRACT["joins"]), errors, "joins")
    for field in ("decision_id", "outcome_id", "deduplication", "late_data"):
        _expect_string(joins, field, errors, "joins")
    _expect_enum(joins, "unmatched_route", MISSING_ROUTES, errors, "joins")

    evidence = _expect_object(document, "modality_evidence", errors)
    evidence_keys = set(evidence)
    if evidence_keys != modality_set:
        missing = modality_set - evidence_keys
        extra = evidence_keys - modality_set
        if missing:
            errors.append(
                "modality_evidence is missing declared modalities: "
                + ", ".join(sorted(missing))
            )
        if extra:
            errors.append(
                "modality_evidence contains undeclared modalities: "
                + ", ".join(sorted(extra))
            )
    for modality in sorted(evidence_keys & MODALITIES):
        payload = evidence[modality]
        prefix = f"modality_evidence.{modality}"
        if not isinstance(payload, dict):
            errors.append(f"{prefix} must be an object")
            continue
        fields = _MODALITY_FIELDS[modality]
        _reject_unknown(payload, fields, errors, prefix)
        for field in sorted(fields):
            if field == "drift_slices":
                _expect_string_list(payload, field, errors, prefix, non_empty=True)
            else:
                _expect_string(payload, field, errors, prefix)
        if modality == "generative":
            task_outcome = payload.get("task_outcome")
            if (
                isinstance(task_outcome, str)
                and task_outcome.strip()
                and outcome_name
                and task_outcome != outcome_name
            ):
                errors.append(
                    f"{prefix}.task_outcome must name outcome.name "
                    f"{outcome_name!r}"
                )

    interventions = _expect_list(
        document, "interventions", errors, non_empty=True
    )
    for index, intervention in enumerate(interventions):
        prefix = f"interventions[{index}]"
        if not isinstance(intervention, dict):
            errors.append(f"{prefix} must be an object")
            continue
        _reject_unknown(
            intervention,
            frozenset({"layer", "hypothesis", "test", "owner", "rollback_trigger"}),
            errors,
            prefix,
        )
        _expect_enum(intervention, "layer", INTERVENTION_LAYERS, errors, prefix)
        for field in ("hypothesis", "test", "owner", "rollback_trigger"):
            _expect_string(intervention, field, errors, prefix)

    rollout = _expect_object(document, "rollout", errors)
    _reject_unknown(rollout, frozenset(_BLANK_CONTRACT["rollout"]), errors, "rollout")
    for field in ("counterfactual", "canary", "advance_when", "rollback_when", "reviewer"):
        _expect_string(rollout, field, errors, "rollout")

    _expect_string_list(document, "non_claims", errors, non_empty=True)
    reproduction = _expect_object(document, "reproduction", errors)
    _reject_unknown(
        reproduction,
        frozenset(_BLANK_CONTRACT["reproduction"]),
        errors,
        "reproduction",
    )
    for field in ("revision", "command", "environment"):
        _expect_string(reproduction, field, errors, "reproduction")

    return tuple(errors)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


def _reject_unknown(
    value: Mapping[str, Any],
    allowed: frozenset[str],
    errors: list[str],
    prefix: str = "",
) -> None:
    for key in sorted(set(value) - allowed):
        field = f"{prefix}.{key}" if prefix else key
        errors.append(f"unknown field: {field}")


def _expect_object(
    value: Mapping[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> dict[str, Any]:
    path = f"{prefix}.{field}" if prefix else field
    observed = value.get(field)
    if not isinstance(observed, dict):
        errors.append(f"{path} must be an object")
        return {}
    return observed


def _expect_list(
    value: Mapping[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
    *,
    non_empty: bool = False,
) -> list[Any]:
    path = f"{prefix}.{field}" if prefix else field
    observed = value.get(field)
    if not isinstance(observed, list):
        errors.append(f"{path} must be an array")
        return []
    if non_empty and not observed:
        errors.append(f"{path} must not be empty")
    return observed


def _expect_string(
    value: Mapping[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> str:
    path = f"{prefix}.{field}" if prefix else field
    observed = value.get(field)
    if not isinstance(observed, str) or not observed.strip():
        errors.append(f"{path} must be a non-empty string")
        return ""
    return observed


def _expect_string_list(
    value: Mapping[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
    *,
    non_empty: bool = False,
) -> list[str]:
    path = f"{prefix}.{field}" if prefix else field
    observed = _expect_list(value, field, errors, prefix, non_empty=non_empty)
    strings: list[str] = []
    for index, item in enumerate(observed):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}[{index}] must be a non-empty string")
        else:
            strings.append(item)
    if len(strings) != len(set(strings)):
        errors.append(f"{path} must not contain duplicates")
    return strings


def _expect_enum(
    value: Mapping[str, Any],
    field: str,
    allowed: frozenset[str],
    errors: list[str],
    prefix: str = "",
) -> str:
    path = f"{prefix}.{field}" if prefix else field
    observed = value.get(field)
    if not isinstance(observed, str) or observed not in allowed:
        errors.append(f"{path} must be one of {sorted(allowed)!r}")
        return ""
    return observed


def _expect_exact(
    value: Mapping[str, Any],
    field: str,
    expected: str,
    errors: list[str],
) -> None:
    if value.get(field) != expected:
        errors.append(f"{field} must equal {expected!r}")


def _expect_date(
    value: Mapping[str, Any],
    field: str,
    errors: list[str],
    prefix: str,
) -> dt.date | None:
    observed = _expect_string(value, field, errors, prefix)
    if not observed:
        return None
    try:
        return dt.date.fromisoformat(observed)
    except ValueError:
        errors.append(f"{prefix}.{field} must be an ISO date")
        return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a production feedback-loop contract."
    )
    parser.add_argument("contract", type=Path)
    args = parser.parse_args(argv)
    try:
        document = load_feedback_contract(args.contract)
    except (OSError, ValueError) as error:
        print(f"INVALID {error}")
        return 2
    errors = validate_feedback_contract(document)
    if errors:
        for error in errors:
            print(f"INVALID {error}")
        return 2
    print(f"VALID digest={feedback_contract_digest(document)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
