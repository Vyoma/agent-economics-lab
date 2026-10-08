from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agent-decision-record/v1"
DECISIONS = frozenset({"INCOMPLETE", "SCALE", "ASSIST", "STOP"})
CLAIM_STATUSES = frozenset({"PASS", "FAIL", "INCOMPLETE"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{7,40}$")


_BLANK_RECORD: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "record_id": "",
    "workload": {
        "name": "",
        "unit_of_work": "",
        "owner": "",
        "population": "",
        "observation_window": {"start": "", "end": ""},
    },
    "decision": {
        "requested": "",
        "issued": "",
        "rationale": "",
        "expires_on": "",
        "rollback_trigger": "",
    },
    "claims": [],
    "evidence": {
        "source_manifest_id": "",
        "evidence_digest": "",
        "decision_contract_digest": "",
        "artifacts": [],
    },
    "counterfactual": {
        "name": "",
        "evidence_ref": "",
        "why_comparable": "",
    },
    "cost_boundary": {
        "currency": "USD",
        "included": [],
        "excluded": [],
        "allocation_notes": "",
    },
    "uncertainty": {
        "method": "",
        "known_missing_evidence": [],
        "non_claims": [],
    },
    "controls": {
        "required_before_next_mode": [],
        "human_escalation": "",
        "runtime_caps": [],
    },
    "reproduction": {
        "command": "",
        "environment": "",
        "revision": "",
    },
    "review": {
        "review_date": "",
        "reviewers": [],
        "signed_off": False,
    },
}


def blank_decision_record() -> dict[str, Any]:
    """Return a fresh, intentionally incomplete decision-record template."""

    return deepcopy(_BLANK_RECORD)


def render_blank_decision_record() -> str:
    return json.dumps(blank_decision_record(), indent=2, ensure_ascii=False) + "\n"


def load_decision_record(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("record must be a JSON object")
    return payload


def validate_decision_record(document: Any) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ("record must be a JSON object",)

    _reject_unknown(document, frozenset(_BLANK_RECORD), errors)
    _expect_exact(document, "schema_version", SCHEMA_VERSION, errors)
    _expect_string(document, "record_id", errors)

    workload = _expect_object(document, "workload", errors)
    _reject_unknown(
        workload,
        frozenset(
            {"name", "unit_of_work", "owner", "population", "observation_window"}
        ),
        errors,
        "workload",
    )
    for field in ("name", "unit_of_work", "owner", "population"):
        _expect_string(workload, field, errors, "workload")
    window = _expect_object(workload, "observation_window", errors, "workload")
    _reject_unknown(
        window,
        frozenset({"start", "end"}),
        errors,
        "workload.observation_window",
    )
    _expect_string(window, "start", errors, "workload.observation_window")
    _expect_string(window, "end", errors, "workload.observation_window")

    decision = _expect_object(document, "decision", errors)
    _reject_unknown(
        decision,
        frozenset(
            {"requested", "issued", "rationale", "expires_on", "rollback_trigger"}
        ),
        errors,
        "decision",
    )
    requested = _expect_enum(
        decision,
        "requested",
        DECISIONS - {"INCOMPLETE"},
        errors,
        "decision",
    )
    issued = _expect_enum(decision, "issued", DECISIONS, errors, "decision")
    for field in ("rationale", "expires_on", "rollback_trigger"):
        _expect_string(decision, field, errors, "decision")

    claims = _expect_list(document, "claims", errors, non_empty=True)
    claim_ids: set[str] = set()
    claim_evidence_refs: list[tuple[str, str]] = []
    required_statuses: list[str] = []
    for index, claim in enumerate(claims):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        _reject_unknown(
            claim,
            frozenset(
                {
                    "id",
                    "statement",
                    "status",
                    "threshold",
                    "observed",
                    "missing_reason",
                    "check_id",
                    "required",
                    "if_absent",
                    "evidence_refs",
                }
            ),
            errors,
            prefix,
        )
        claim_id = _expect_string(claim, "id", errors, prefix)
        if claim_id:
            if claim_id in claim_ids:
                errors.append(f"{prefix}.id must be unique: {claim_id!r}")
            claim_ids.add(claim_id)
        _expect_string(claim, "statement", errors, prefix)
        status = _expect_enum(claim, "status", CLAIM_STATUSES, errors, prefix)
        _expect_string(claim, "threshold", errors, prefix)
        _expect_string(claim, "check_id", errors, prefix)
        required = _expect_bool(claim, "required", errors, prefix)
        if_absent = _expect_enum(
            claim,
            "if_absent",
            DECISIONS,
            errors,
            prefix,
        )
        evidence_refs = _expect_string_list(
            claim,
            "evidence_refs",
            errors,
            prefix,
        )
        claim_evidence_refs.extend((prefix, ref) for ref in evidence_refs)
        observed = claim.get("observed")
        missing_reason = claim.get("missing_reason")
        if status in {"PASS", "FAIL"}:
            if not isinstance(observed, str) or not observed.strip():
                errors.append(f"{prefix}.observed must be a non-empty string")
            if not evidence_refs:
                errors.append(
                    f"{prefix}.evidence_refs must contain evidence for {status}"
                )
        elif status == "INCOMPLETE":
            if not isinstance(missing_reason, str) or not missing_reason.strip():
                errors.append(
                    f"{prefix}.missing_reason is required when status is INCOMPLETE"
                )
        if required is True:
            required_statuses.append(status)
            if if_absent != "INCOMPLETE":
                errors.append(
                    f"{prefix}.if_absent must be INCOMPLETE for a required claim"
                )

    evidence = _expect_object(document, "evidence", errors)
    _reject_unknown(
        evidence,
        frozenset(
            {
                "source_manifest_id",
                "evidence_digest",
                "decision_contract_digest",
                "artifacts",
            }
        ),
        errors,
        "evidence",
    )
    _expect_string(evidence, "source_manifest_id", errors, "evidence")
    _expect_digest(evidence, "evidence_digest", errors, "evidence")
    _expect_digest(evidence, "decision_contract_digest", errors, "evidence")
    artifacts = _expect_list(evidence, "artifacts", errors, "evidence", non_empty=True)
    artifact_uris: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"evidence.artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        _reject_unknown(
            artifact,
            frozenset({"uri", "role", "sha256"}),
            errors,
            prefix,
        )
        uri = _expect_string(artifact, "uri", errors, prefix)
        if uri:
            if uri in artifact_uris:
                errors.append(f"{prefix}.uri must be unique: {uri!r}")
            artifact_uris.add(uri)
        _expect_string(artifact, "role", errors, prefix)
        _expect_digest(artifact, "sha256", errors, prefix)
    for prefix, evidence_ref in claim_evidence_refs:
        if evidence_ref not in artifact_uris:
            errors.append(
                f"{prefix}.evidence_refs contains undeclared artifact {evidence_ref!r}"
            )

    counterfactual = _expect_object(document, "counterfactual", errors)
    _reject_unknown(
        counterfactual,
        frozenset({"name", "evidence_ref", "why_comparable"}),
        errors,
        "counterfactual",
    )
    _expect_string(counterfactual, "name", errors, "counterfactual")
    counterfactual_ref = _expect_string(
        counterfactual,
        "evidence_ref",
        errors,
        "counterfactual",
    )
    _expect_string(counterfactual, "why_comparable", errors, "counterfactual")
    if counterfactual_ref and counterfactual_ref not in artifact_uris:
        errors.append(
            "counterfactual.evidence_ref must name a declared evidence artifact"
        )

    cost_boundary = _expect_object(document, "cost_boundary", errors)
    _reject_unknown(
        cost_boundary,
        frozenset({"currency", "included", "excluded", "allocation_notes"}),
        errors,
        "cost_boundary",
    )
    _expect_string(cost_boundary, "currency", errors, "cost_boundary")
    _expect_string_list(
        cost_boundary,
        "included",
        errors,
        "cost_boundary",
        non_empty=True,
    )
    _expect_string_list(cost_boundary, "excluded", errors, "cost_boundary")
    _expect_string(cost_boundary, "allocation_notes", errors, "cost_boundary")

    uncertainty = _expect_object(document, "uncertainty", errors)
    _reject_unknown(
        uncertainty,
        frozenset({"method", "known_missing_evidence", "non_claims"}),
        errors,
        "uncertainty",
    )
    _expect_string(uncertainty, "method", errors, "uncertainty")
    missing_evidence = _expect_string_list(
        uncertainty,
        "known_missing_evidence",
        errors,
        "uncertainty",
    )
    _expect_string_list(
        uncertainty,
        "non_claims",
        errors,
        "uncertainty",
        non_empty=True,
    )

    controls = _expect_object(document, "controls", errors)
    _reject_unknown(
        controls,
        frozenset({"required_before_next_mode", "human_escalation", "runtime_caps"}),
        errors,
        "controls",
    )
    _expect_string_list(
        controls,
        "required_before_next_mode",
        errors,
        "controls",
    )
    _expect_string(controls, "human_escalation", errors, "controls")
    _expect_string_list(controls, "runtime_caps", errors, "controls")

    reproduction = _expect_object(document, "reproduction", errors)
    _reject_unknown(
        reproduction,
        frozenset({"command", "environment", "revision"}),
        errors,
        "reproduction",
    )
    _expect_string(reproduction, "command", errors, "reproduction")
    _expect_string(reproduction, "environment", errors, "reproduction")
    revision = _expect_string(reproduction, "revision", errors, "reproduction")
    if revision and not _REVISION.fullmatch(revision):
        errors.append("reproduction.revision must be a 7-40 character Git SHA")

    review = _expect_object(document, "review", errors)
    _reject_unknown(
        review,
        frozenset({"review_date", "reviewers", "signed_off"}),
        errors,
        "review",
    )
    _expect_string(review, "review_date", errors, "review")
    _expect_string_list(review, "reviewers", errors, "review", non_empty=True)
    _expect_bool(review, "signed_off", errors, "review")

    if not required_statuses:
        errors.append("claims must contain at least one required claim")
    if requested and issued == "SCALE" and any(
        status != "PASS" for status in required_statuses
    ):
        errors.append(
            "decision.issued cannot be SCALE unless every required claim passes"
        )
    if issued == "SCALE" and missing_evidence:
        errors.append(
            "decision.issued cannot be SCALE while known_missing_evidence is non-empty"
        )
    if review.get("signed_off") is not True:
        errors.append("review.signed_off must be true for a valid decision record")

    return tuple(errors)


def _path(prefix: str, field: str) -> str:
    return f"{prefix}.{field}" if prefix else field


def _reject_unknown(
    parent: dict[str, Any],
    allowed: frozenset[str],
    errors: list[str],
    prefix: str = "",
) -> None:
    for field in sorted(set(parent) - allowed):
        errors.append(f"{_path(prefix, field)} is not part of {SCHEMA_VERSION}")


def _expect_object(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> dict[str, Any]:
    value = parent.get(field)
    if not isinstance(value, dict):
        errors.append(f"{_path(prefix, field)} must be an object")
        return {}
    return value


def _expect_list(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
    *,
    non_empty: bool = False,
) -> list[Any]:
    value = parent.get(field)
    if not isinstance(value, list):
        errors.append(f"{_path(prefix, field)} must be a list")
        return []
    if non_empty and not value:
        errors.append(f"{_path(prefix, field)} must not be empty")
    return value


def _expect_string(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> str:
    value = parent.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{_path(prefix, field)} must be a non-empty string")
        return ""
    return value.strip()


def _expect_string_list(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
    *,
    non_empty: bool = False,
) -> list[str]:
    values = _expect_list(parent, field, errors, prefix, non_empty=non_empty)
    strings: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"{_path(prefix, field)}[{index}] must be a non-empty string"
            )
        else:
            strings.append(value.strip())
    return strings


def _expect_bool(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> bool | None:
    value = parent.get(field)
    if not isinstance(value, bool):
        errors.append(f"{_path(prefix, field)} must be a boolean")
        return None
    return value


def _expect_enum(
    parent: dict[str, Any],
    field: str,
    allowed: frozenset[str],
    errors: list[str],
    prefix: str = "",
) -> str:
    value = parent.get(field)
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        errors.append(f"{_path(prefix, field)} must be one of: {choices}")
        return ""
    return value


def _expect_exact(
    parent: dict[str, Any],
    field: str,
    expected: str,
    errors: list[str],
) -> None:
    if parent.get(field) != expected:
        errors.append(f"{field} must be {expected!r}")


def _expect_digest(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> None:
    value = parent.get(field)
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        errors.append(f"{_path(prefix, field)} must be a lowercase SHA-256 digest")
