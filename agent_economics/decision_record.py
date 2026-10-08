from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

from .audit import AuditReport, decide
from .checks import DEFAULT_REQUIRED_COVERAGE, default_checks
from .models import AssuranceCase, CheckMode, CheckStatus, EvidenceBundle
from .provenance import Attestation

SCHEMA_VERSION = "agent-decision-record/v1"
GATE_ENTRY_POINT = "agent_economics.audit.decide"
DECISIONS = frozenset({"INCOMPLETE", "SCALE", "ASSIST", "STOP"})
CLAIM_STATUSES = frozenset({"PASS", "FAIL", "INCOMPLETE"})
DELEGATION_STATUSES = frozenset({"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"})
DELEGATION_BASES = frozenset({"COST", "COUNT", "NOT_APPLICABLE"})
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
        "bundle_ref": "",
        "enabled_checks": [],
        "required_coverage": [],
        "artifacts": [],
    },
    "assurance": {
        "gate_entry_point": GATE_ENTRY_POINT,
        "audit_as_of": "",
        "audit_assessable": False,
        "audit_grounds": [],
        "label_source": "",
        "attestation_refs": [],
        "delegation": {
            "status": "",
            "basis": "",
            "closure": None,
            "unaccounted": [],
        },
        "fail_closed_conformance": False,
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
    """Render the intentionally incomplete template as stable JSON."""

    return json.dumps(blank_decision_record(), indent=2, ensure_ascii=False) + "\n"


def load_decision_record(path: str | Path) -> dict[str, Any]:
    """Load a JSON object without filling, coercing, or defaulting fields."""

    payload = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_object_without_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(payload, dict):
        raise ValueError("record must be a JSON object")
    return payload


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


def validate_decision_record(document: Any) -> tuple[str, ...]:
    """Validate the record's closed schema and its fail-closed invariants.

    This is structural validation. Use :func:`verify_decision_record` to
    recompute the decision, audit, claim statuses, and artifact hashes.
    """

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
    start = _expect_date(window, "start", errors, "workload.observation_window")
    end = _expect_date(window, "end", errors, "workload.observation_window")
    if start and end and start > end:
        errors.append("workload.observation_window.start must not be after end")

    decision = _expect_object(document, "decision", errors)
    _reject_unknown(
        decision,
        frozenset(
            {"requested", "issued", "rationale", "expires_on", "rollback_trigger"}
        ),
        errors,
        "decision",
    )
    _expect_enum(
        decision,
        "requested",
        DECISIONS - {"INCOMPLETE"},
        errors,
        "decision",
    )
    issued = _expect_enum(decision, "issued", DECISIONS, errors, "decision")
    _expect_string(decision, "rationale", errors, "decision")
    _expect_date(decision, "expires_on", errors, "decision")
    _expect_string(decision, "rollback_trigger", errors, "decision")

    claims = _expect_list(document, "claims", errors, non_empty=True)
    claim_ids: set[str] = set()
    required_check_ids: set[str] = set()
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
        check_id = _expect_string(claim, "check_id", errors, prefix)
        required = _expect_bool(claim, "required", errors, prefix)
        if_absent = _expect_enum(claim, "if_absent", DECISIONS, errors, prefix)
        evidence_refs = _expect_string_list(claim, "evidence_refs", errors, prefix)
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
            if check_id:
                if check_id in required_check_ids:
                    errors.append(
                        f"{prefix}.check_id duplicates required check {check_id!r}"
                    )
                required_check_ids.add(check_id)

    evidence = _expect_object(document, "evidence", errors)
    _reject_unknown(
        evidence,
        frozenset(
            {
                "source_manifest_id",
                "evidence_digest",
                "decision_contract_digest",
                "bundle_ref",
                "enabled_checks",
                "required_coverage",
                "artifacts",
            }
        ),
        errors,
        "evidence",
    )
    _expect_string(evidence, "source_manifest_id", errors, "evidence")
    _expect_digest(evidence, "evidence_digest", errors, "evidence")
    _expect_digest(evidence, "decision_contract_digest", errors, "evidence")
    bundle_ref = _expect_string(evidence, "bundle_ref", errors, "evidence")
    enabled_checks = _expect_string_list(
        evidence, "enabled_checks", errors, "evidence", non_empty=True
    )
    required_coverage = _expect_string_list(
        evidence, "required_coverage", errors, "evidence", non_empty=True
    )
    if len(enabled_checks) != len(set(enabled_checks)):
        errors.append("evidence.enabled_checks must not contain duplicates")
    if len(required_coverage) != len(set(required_coverage)):
        errors.append("evidence.required_coverage must not contain duplicates")
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
            if not _safe_relative_uri(uri):
                errors.append(
                    f"{prefix}.uri must be a normalized relative path without '..'"
                )
        _expect_string(artifact, "role", errors, prefix)
        _expect_digest(artifact, "sha256", errors, prefix)
    if bundle_ref and bundle_ref not in artifact_uris:
        errors.append("evidence.bundle_ref must name a declared evidence artifact")
    for prefix, evidence_ref in claim_evidence_refs:
        if evidence_ref not in artifact_uris:
            errors.append(
                f"{prefix}.evidence_refs contains undeclared artifact {evidence_ref!r}"
            )

    assurance = _expect_object(document, "assurance", errors)
    _reject_unknown(
        assurance,
        frozenset(
            {
                "gate_entry_point",
                "audit_as_of",
                "audit_assessable",
                "audit_grounds",
                "label_source",
                "attestation_refs",
                "delegation",
                "fail_closed_conformance",
            }
        ),
        errors,
        "assurance",
    )
    _expect_exact(
        assurance,
        "gate_entry_point",
        GATE_ENTRY_POINT,
        errors,
        prefix="assurance",
    )
    _expect_date(assurance, "audit_as_of", errors, "assurance")
    assessable = _expect_bool(assurance, "audit_assessable", errors, "assurance")
    grounds = _expect_string_list(assurance, "audit_grounds", errors, "assurance")
    _expect_string(assurance, "label_source", errors, "assurance")
    attestation_refs = _expect_string_list(
        assurance, "attestation_refs", errors, "assurance"
    )
    conformance = _expect_bool(
        assurance, "fail_closed_conformance", errors, "assurance"
    )
    for ref in attestation_refs:
        if ref not in artifact_uris:
            errors.append(
                "assurance.attestation_refs contains undeclared artifact "
                f"{ref!r}"
            )
    if assessable is True and grounds:
        errors.append("assurance.audit_grounds must be empty when audit_assessable is true")
    if assessable is False and not grounds:
        errors.append(
            "assurance.audit_grounds must name why audit_assessable is false"
        )
    if conformance is not True:
        errors.append("assurance.fail_closed_conformance must be true")

    delegation = _expect_object(assurance, "delegation", errors, "assurance")
    _reject_unknown(
        delegation,
        frozenset({"status", "basis", "closure", "unaccounted"}),
        errors,
        "assurance.delegation",
    )
    delegation_status = _expect_enum(
        delegation,
        "status",
        DELEGATION_STATUSES,
        errors,
        "assurance.delegation",
    )
    delegation_basis = _expect_enum(
        delegation,
        "basis",
        DELEGATION_BASES,
        errors,
        "assurance.delegation",
    )
    closure = _expect_optional_fraction(
        delegation, "closure", errors, "assurance.delegation"
    )
    unaccounted = _expect_string_list(
        delegation, "unaccounted", errors, "assurance.delegation"
    )
    if delegation_status == "NOT_APPLICABLE":
        if delegation_basis != "NOT_APPLICABLE":
            errors.append(
                "assurance.delegation.basis must be NOT_APPLICABLE when status is"
                " NOT_APPLICABLE"
            )
        if closure is not None:
            errors.append(
                "assurance.delegation.closure must be null when status is"
                " NOT_APPLICABLE"
            )
        if unaccounted:
            errors.append(
                "assurance.delegation.unaccounted must be empty when status is"
                " NOT_APPLICABLE"
            )
    elif delegation_basis == "NOT_APPLICABLE":
        errors.append(
            "assurance.delegation.basis cannot be NOT_APPLICABLE when delegation"
            " was measured"
        )
    elif closure is None:
        errors.append(
            "assurance.delegation.closure must be a number when delegation was measured"
        )
    if delegation_status == "COMPLETE" and unaccounted:
        errors.append(
            "assurance.delegation.unaccounted must be empty when status is COMPLETE"
        )
    if delegation_status == "INCOMPLETE" and not unaccounted:
        errors.append(
            "assurance.delegation.unaccounted must explain an INCOMPLETE status"
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
        cost_boundary, "included", errors, "cost_boundary", non_empty=True
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
        uncertainty, "known_missing_evidence", errors, "uncertainty"
    )
    _expect_string_list(
        uncertainty, "non_claims", errors, "uncertainty", non_empty=True
    )

    controls = _expect_object(document, "controls", errors)
    _reject_unknown(
        controls,
        frozenset({"required_before_next_mode", "human_escalation", "runtime_caps"}),
        errors,
        "controls",
    )
    _expect_string_list(
        controls, "required_before_next_mode", errors, "controls"
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
    _expect_date(review, "review_date", errors, "review")
    _expect_string_list(review, "reviewers", errors, "review", non_empty=True)
    _expect_bool(review, "signed_off", errors, "review")

    if not required_statuses:
        errors.append("claims must contain at least one required claim")
    if issued == "SCALE" and any(status != "PASS" for status in required_statuses):
        errors.append(
            "decision.issued cannot be SCALE unless every required claim passes"
        )
    if issued == "SCALE" and missing_evidence:
        errors.append(
            "decision.issued cannot be SCALE while known_missing_evidence is non-empty"
        )
    if issued == "SCALE" and assessable is not True:
        errors.append("decision.issued cannot be SCALE when the audit is unassessable")
    if issued == "SCALE" and delegation_status == "INCOMPLETE":
        errors.append(
            "decision.issued cannot be SCALE with incomplete delegation closure"
        )
    if review.get("signed_off") is not True:
        errors.append("review.signed_off must be true for a valid decision record")

    return tuple(errors)


def verify_decision_record(
    document: Any,
    *,
    bundle: EvidenceBundle,
    artifact_root: str | Path,
    bundle_ref: str,
    attestations: Mapping[str, Attestation] | None = None,
    attestation_ref: str | None = None,
) -> tuple[str, ...]:
    """Recompute every machine-checkable binding in a decision record.

    The record's prose remains an issuer claim. This verifies the artifacts,
    evidence and contract digests, gate decision, per-check statuses, and audit
    facts using the public fail-closed entry point.
    """

    errors = list(validate_decision_record(document))
    if errors:
        return tuple(errors)

    root = Path(artifact_root).resolve()
    declared_bundle_ref = document["evidence"]["bundle_ref"]
    if bundle_ref != declared_bundle_ref:
        errors.append(
            f"supplied bundle ref {bundle_ref!r} does not match "
            f"evidence.bundle_ref {declared_bundle_ref!r}"
        )
    declared_attestations = document["assurance"]["attestation_refs"]
    if attestation_ref is not None and attestation_ref not in declared_attestations:
        errors.append(
            f"supplied attestation ref {attestation_ref!r} is not declared in "
            "assurance.attestation_refs"
        )
    if declared_attestations and attestation_ref is None:
        errors.append("record declares attestations but no attestation artifact was supplied")

    for artifact in document["evidence"]["artifacts"]:
        path = (root / artifact["uri"]).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"artifact escapes artifact root: {artifact['uri']!r}")
            continue
        try:
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            errors.append(f"artifact cannot be read: {artifact['uri']!r}: {error}")
            continue
        if observed != artifact["sha256"]:
            errors.append(
                f"artifact digest mismatch for {artifact['uri']!r}: "
                f"recorded {artifact['sha256']}, observed {observed}"
            )

    audit_as_of = dt.date.fromisoformat(document["assurance"]["audit_as_of"])
    checks = tuple(default_checks())
    case, report = decide(
        bundle,
        checks,
        DEFAULT_REQUIRED_COVERAGE,
        attestations=attestations,
        as_of=audit_as_of,
    )
    _compare_case(document, case, checks, errors)
    _compare_audit(document, report, bundle, errors)
    return tuple(errors)


def _compare_case(
    document: dict[str, Any],
    case: AssuranceCase,
    checks: tuple[Any, ...],
    errors: list[str],
) -> None:
    expected = {
        "decision.issued": (document["decision"]["issued"], case.decision.value),
        "evidence.source_manifest_id": (
            document["evidence"]["source_manifest_id"],
            case.source_manifest_id,
        ),
        "evidence.evidence_digest": (
            document["evidence"]["evidence_digest"],
            case.evidence_digest,
        ),
        "evidence.decision_contract_digest": (
            document["evidence"]["decision_contract_digest"],
            case.decision_contract_digest,
        ),
        "evidence.enabled_checks": (
            document["evidence"]["enabled_checks"],
            list(case.enabled_checks),
        ),
        "evidence.required_coverage": (
            document["evidence"]["required_coverage"],
            list(case.required_coverage),
        ),
    }
    for label, (recorded, observed) in expected.items():
        if recorded != observed:
            errors.append(
                f"{label} does not reproduce: recorded {recorded!r}, "
                f"observed {observed!r}"
            )

    manifest_by_id = {check.id: check.manifest_id for check in checks}
    statuses: dict[str, list[CheckStatus]] = defaultdict(list)
    for result in case.check_results:
        statuses[manifest_by_id[result.check_id]].append(result.status)

    required_gate_ids = {
        check.manifest_id
        for check in checks
        if check.mode is CheckMode.GATE
        and check.covers & DEFAULT_REQUIRED_COVERAGE
    }
    recorded_required_ids = {
        claim["check_id"] for claim in document["claims"] if claim["required"]
    }
    if recorded_required_ids != required_gate_ids:
        errors.append(
            "required claims do not cover the recomputed gate contract: "
            f"recorded {sorted(recorded_required_ids)!r}, "
            f"expected {sorted(required_gate_ids)!r}"
        )

    for index, claim in enumerate(document["claims"]):
        observed_statuses = statuses.get(claim["check_id"], [])
        if not observed_statuses:
            observed_status = "INCOMPLETE"
        elif CheckStatus.FAIL in observed_statuses:
            observed_status = "FAIL"
        else:
            observed_status = "PASS"
        if claim["status"] != observed_status:
            errors.append(
                f"claims[{index}].status does not reproduce for "
                f"{claim['check_id']}: recorded {claim['status']}, "
                f"observed {observed_status}"
            )


def _compare_audit(
    document: dict[str, Any],
    report: AuditReport,
    bundle: EvidenceBundle,
    errors: list[str],
) -> None:
    assurance = document["assurance"]
    observed_status, observed_basis, observed_closure, observed_unaccounted = (
        _delegation_summary(report)
    )
    expected = {
        "assurance.audit_assessable": (
            assurance["audit_assessable"],
            report.assessable,
        ),
        "assurance.audit_grounds": (
            assurance["audit_grounds"],
            list(report.grounds),
        ),
        "assurance.label_source": (
            assurance["label_source"],
            bundle.label_source,
        ),
        "assurance.delegation.status": (
            assurance["delegation"]["status"],
            observed_status,
        ),
        "assurance.delegation.basis": (
            assurance["delegation"]["basis"],
            observed_basis,
        ),
        "assurance.delegation.closure": (
            assurance["delegation"]["closure"],
            observed_closure,
        ),
        "assurance.delegation.unaccounted": (
            assurance["delegation"]["unaccounted"],
            observed_unaccounted,
        ),
        "assurance.fail_closed_conformance": (
            assurance["fail_closed_conformance"],
            report.conformance_held,
        ),
    }
    for label, (recorded, observed) in expected.items():
        if recorded != observed:
            errors.append(
                f"{label} does not reproduce: recorded {recorded!r}, "
                f"observed {observed!r}"
            )


def _delegation_summary(
    report: AuditReport,
) -> tuple[str, str, float | None, list[str]]:
    if report.delegation_count == 0 and not report.unrecorded_delegations:
        return "NOT_APPLICABLE", "NOT_APPLICABLE", None, []
    unaccounted = list(report.unaccounted_delegations)
    unaccounted.extend(report.unrecorded_delegations)
    if report.unpriced_delegation:
        unaccounted.append(report.unpriced_delegation)
    status = "INCOMPLETE" if unaccounted else "COMPLETE"
    basis = "COST" if report.spend_is_priced else "COUNT"
    return status, basis, report.closure, unaccounted


def _safe_relative_uri(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and value == path.as_posix()
        and value not in {"", "."}
    )


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
            errors.append(f"{_path(prefix, field)}[{index}] must be a non-empty string")
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
    *,
    prefix: str = "",
) -> None:
    if parent.get(field) != expected:
        errors.append(f"{_path(prefix, field)} must be {expected!r}")


def _expect_digest(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> None:
    value = parent.get(field)
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        errors.append(f"{_path(prefix, field)} must be a lowercase SHA-256 digest")


def _expect_date(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> dt.date | None:
    value = _expect_string(parent, field, errors, prefix)
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        errors.append(f"{_path(prefix, field)} must be an ISO date (YYYY-MM-DD)")
        return None


def _expect_optional_fraction(
    parent: dict[str, Any],
    field: str,
    errors: list[str],
    prefix: str = "",
) -> float | None:
    value = parent.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{_path(prefix, field)} must be null or a number in [0, 1]")
        return None
    numeric = float(value)
    if not 0.0 <= numeric <= 1.0:
        errors.append(f"{_path(prefix, field)} must be in [0, 1]")
        return None
    return numeric


__all__ = [
    "GATE_ENTRY_POINT",
    "SCHEMA_VERSION",
    "blank_decision_record",
    "load_decision_record",
    "render_blank_decision_record",
    "validate_decision_record",
    "verify_decision_record",
]
