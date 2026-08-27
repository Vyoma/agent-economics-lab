"""Characterize current behavior when raw evidence is actually removed.

This benchmark is intentionally separate from ``false_green.py``. It never
removes a check or changes required decision coverage. Instead, it deletes one
raw field, record, object, manifest row, threshold, or timed-out event and then
records whether the current public evaluation path rejects the input or issues
a decision.

Run ``python3 evidence_ablation.py`` to print the frozen v1 result. The cases are
synthetic conformance fixtures, not estimates of production prevalence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_economics import (
    DEFAULT_REQUIRED_COVERAGE,
    AssuranceEngine,
    Decision,
    decision_contract_digest,
    default_checks,
    normalized_json_bundle,
)

SCHEMA_ERROR = "SCHEMA_ERROR"
EVIDENCE_ERROR = "EVIDENCE_ERROR"
EVALUATION_ERROR = "EVALUATION_ERROR"
DECISION = "DECISION"
INCOMPLETE = "INCOMPLETE"

PROTOCOL_VERSION = "1"
BENCHMARK_ID = "experiment.raw-evidence-ablation@1"
FIXED_CHECKS = default_checks()
FIXED_REQUIRED_COVERAGE = DEFAULT_REQUIRED_COVERAGE
FIXED_ENGINE = AssuranceEngine(
    checks=FIXED_CHECKS,
    required_coverage=FIXED_REQUIRED_COVERAGE,
)
CHECK_MANIFEST = tuple(check.manifest_id for check in FIXED_CHECKS)
REQUIRED_COVERAGE = tuple(
    sorted(coverage.value for coverage in FIXED_REQUIRED_COVERAGE)
)
DECISION_CONTRACT_DIGEST = decision_contract_digest(
    FIXED_CHECKS, FIXED_REQUIRED_COVERAGE
)


@dataclass(frozen=True)
class AblationSpec:
    case_id: str
    fixture_id: str
    evidence_layer: str
    operation: str
    target: tuple[str | int, ...]
    complete_decision: str
    library_outcome: str
    operational_outcome: str
    ablated_decision: str = ""
    error_type: str = ""
    error_code: str = ""

    @property
    def target_json_pointer(self) -> str:
        return "/" + "/".join(str(part) for part in self.target)


ABLATIONS = (
    AblationSpec(
        case_id="drop_outcome_record",
        fixture_id="clean",
        evidence_layer="outcomes",
        operation="delete_list_item",
        target=("outcomes", 0),
        complete_decision="SCALE",
        library_outcome=EVIDENCE_ERROR,
        operational_outcome=INCOMPLETE,
        error_type="ValueError",
        error_code="TRACE_OUTCOME_MISMATCH",
    ),
    AblationSpec(
        case_id="drop_baseline_object",
        fixture_id="clean",
        evidence_layer="baseline",
        operation="delete_mapping_key",
        target=("baseline",),
        complete_decision="SCALE",
        library_outcome=SCHEMA_ERROR,
        operational_outcome=INCOMPLETE,
        error_type="KeyError",
        error_code="MISSING_BASELINE",
    ),
    AblationSpec(
        case_id="drop_incident_loss",
        fixture_id="incident",
        evidence_layer="outcome_cost",
        operation="delete_mapping_key",
        target=("outcomes", 0, "incident_loss_usd"),
        complete_decision="ASSIST",
        library_outcome=DECISION,
        operational_outcome="SCALE",
        ablated_decision="SCALE",
    ),
    AblationSpec(
        case_id="drop_remediation_cost",
        fixture_id="remediation",
        evidence_layer="outcome_cost",
        operation="delete_mapping_key",
        target=("outcomes", 0, "remediation_cost_usd"),
        complete_decision="ASSIST",
        library_outcome=DECISION,
        operational_outcome="SCALE",
        ablated_decision="SCALE",
    ),
    AblationSpec(
        case_id="drop_human_review_time",
        fixture_id="human-review",
        evidence_layer="outcome_cost",
        operation="delete_mapping_key",
        target=("outcomes", 0, "human_minutes"),
        complete_decision="ASSIST",
        library_outcome=DECISION,
        operational_outcome="SCALE",
        ablated_decision="SCALE",
    ),
    AblationSpec(
        case_id="drop_trace_cost",
        fixture_id="trace-cost",
        evidence_layer="trace_cost",
        operation="delete_mapping_key",
        target=("events", 0, "direct_cost_usd"),
        complete_decision="ASSIST",
        library_outcome=DECISION,
        operational_outcome="SCALE",
        ablated_decision="SCALE",
    ),
    AblationSpec(
        case_id="drop_manifest_task",
        fixture_id="clean",
        evidence_layer="task_manifest",
        operation="delete_list_item",
        target=("task_manifest", 0),
        complete_decision="SCALE",
        library_outcome=EVIDENCE_ERROR,
        operational_outcome=INCOMPLETE,
        error_type="ValueError",
        error_code="MANIFEST_COVERAGE_MISMATCH",
    ),
    AblationSpec(
        case_id="drop_policy_threshold",
        fixture_id="clean",
        evidence_layer="policy",
        operation="delete_mapping_key",
        target=("policy", "max_cost_per_acceptable_outcome_usd"),
        complete_decision="SCALE",
        library_outcome=SCHEMA_ERROR,
        operational_outcome=INCOMPLETE,
        error_type="TypeError",
        error_code="MISSING_POLICY_THRESHOLD",
    ),
    AblationSpec(
        case_id="drop_timed_out_event",
        fixture_id="timed-out-event",
        evidence_layer="attempt_trace",
        operation="delete_list_item",
        target=("events", 1),
        complete_decision="ASSIST",
        library_outcome=DECISION,
        operational_outcome="SCALE",
        ablated_decision="SCALE",
    ),
)


@dataclass(frozen=True)
class EvaluationResult:
    library_outcome: str
    operational_outcome: str
    decision: str = ""
    assurance_case_emitted: bool = False
    error_type: str = ""
    error_code: str = ""
    attempts: int | None = None
    total_cost_usd: float | None = None
    p95_cost_usd: float | None = None
    max_calls: int | None = None
    enabled_checks: tuple[str, ...] = ()
    required_coverage: tuple[str, ...] = ()
    decision_contract_digest: str = ""


def _base_raw_fixture() -> dict[str, Any]:
    return {
        "events": [
            {
                "task_id": "task-a",
                "event_id": "event-a",
                "timestamp": "2026-07-01T00:00:00Z",
                "event_type": "tool",
                "name": "complete",
                "direct_cost_usd": 0.1,
                "status": "ok",
            },
            {
                "task_id": "task-b",
                "event_id": "event-b",
                "timestamp": "2026-07-01T00:00:01Z",
                "event_type": "tool",
                "name": "complete",
                "direct_cost_usd": 0.1,
                "status": "ok",
            },
        ],
        "outcomes": [
            {
                "task_id": "task-a",
                "acceptable": True,
                "business_value_usd": 20.0,
                "human_minutes": 0.0,
                "remediation_cost_usd": 0.0,
                "incident_loss_usd": 0.0,
            },
            {
                "task_id": "task-b",
                "acceptable": True,
                "business_value_usd": 20.0,
                "human_minutes": 0.0,
                "remediation_cost_usd": 0.0,
                "incident_loss_usd": 0.0,
            },
        ],
        "rates": {},
        "baseline": {
            "name": "human baseline",
            "cost_per_attempt_usd": 10.0,
            "acceptable_rate": 0.5,
            "value_per_acceptable_outcome_usd": 20.0,
        },
        "policy": {
            "human_hourly_cost_usd": 60.0,
            "min_acceptable_rate": 1.0,
            "max_cost_per_acceptable_outcome_usd": 5.0,
            "max_p95_task_cost_usd": 5.0,
            "max_trace_cost_per_task_usd": 5.0,
            "max_calls_per_task": 3,
            "min_expected_net_value_per_attempt_usd": 0.0,
            "min_incremental_net_value_vs_baseline_usd": 0.0,
            "repetition_warning_threshold": 3,
        },
        "task_manifest": [
            {
                "task_id": "task-a",
                "input_digest": "a" * 64,
                "rubric_version": "rubric-v1",
            },
            {
                "task_id": "task-b",
                "input_digest": "b" * 64,
                "rubric_version": "rubric-v1",
            },
        ],
    }


def build_fixture(fixture_id: str) -> dict[str, Any]:
    raw = _base_raw_fixture()
    first_outcome = raw["outcomes"][0]
    first_event = raw["events"][0]
    policy = raw["policy"]

    if fixture_id == "clean":
        return raw
    if fixture_id == "incident":
        first_outcome["incident_loss_usd"] = 3.0
        policy["max_p95_task_cost_usd"] = 1.0
        return raw
    if fixture_id == "remediation":
        first_outcome["remediation_cost_usd"] = 3.0
        policy["max_cost_per_acceptable_outcome_usd"] = 1.0
        return raw
    if fixture_id == "human-review":
        first_outcome["human_minutes"] = 3.0
        policy["max_cost_per_acceptable_outcome_usd"] = 1.0
        return raw
    if fixture_id == "trace-cost":
        first_event["direct_cost_usd"] = 2.0
        policy["max_cost_per_acceptable_outcome_usd"] = 1.0
        return raw
    if fixture_id == "timed-out-event":
        raw["events"].insert(
            1,
            {
                "task_id": "task-a",
                "event_id": "event-timeout",
                "timestamp": "2026-07-01T00:00:00.500000Z",
                "event_type": "model",
                "name": "retry",
                "direct_cost_usd": 0.1,
                "status": "timeout",
            },
        )
        policy["max_calls_per_task"] = 1
        return raw
    raise ValueError(f"Unknown fixture ID: {fixture_id}")


def apply_ablation(raw: dict[str, Any], spec: AblationSpec) -> None:
    container: Any = raw
    for part in spec.target[:-1]:
        container = container[part]
    removed = container.pop(spec.target[-1])
    if removed is None:
        raise ValueError(f"Ablation {spec.case_id} did not remove evidence")


def _error_code(case_id: str, error: Exception) -> str:
    message = str(error)
    if case_id == "drop_baseline_object" and isinstance(error, KeyError):
        return "MISSING_BASELINE"
    if (
        case_id == "drop_policy_threshold"
        and isinstance(error, TypeError)
        and "max_cost_per_acceptable_outcome_usd" in message
    ):
        return "MISSING_POLICY_THRESHOLD"
    if (
        case_id == "drop_outcome_record"
        and isinstance(error, ValueError)
        and "trace and outcome task IDs must exactly match" in message
    ):
        return "TRACE_OUTCOME_MISMATCH"
    if (
        case_id == "drop_manifest_task"
        and isinstance(error, ValueError)
        and "task manifest must exactly cover" in message
    ):
        return "MANIFEST_COVERAGE_MISMATCH"
    return "UNEXPECTED_ERROR"


def evaluate_raw(raw: dict[str, Any], *, case_id: str) -> EvaluationResult:
    try:
        evidence = normalized_json_bundle(raw)
    except (KeyError, TypeError) as error:
        return EvaluationResult(
            library_outcome=SCHEMA_ERROR,
            operational_outcome=INCOMPLETE,
            error_type=type(error).__name__,
            error_code=_error_code(case_id, error),
        )
    except ValueError as error:
        return EvaluationResult(
            library_outcome=EVIDENCE_ERROR,
            operational_outcome=INCOMPLETE,
            error_type=type(error).__name__,
            error_code=_error_code(case_id, error),
        )

    try:
        case = FIXED_ENGINE.evaluate(evidence)
    except Exception as error:  # An unexpected check or evaluation failure is recorded.
        return EvaluationResult(
            library_outcome=EVALUATION_ERROR,
            operational_outcome="ERROR",
            error_type=type(error).__name__,
            error_code="UNEXPECTED_EVALUATION_ERROR",
        )

    return EvaluationResult(
        library_outcome=DECISION,
        operational_outcome=case.decision.value,
        decision=case.decision.value,
        assurance_case_emitted=True,
        attempts=len(case.tasks),
        total_cost_usd=case.total_effective_cost_usd,
        p95_cost_usd=case.p95_task_cost_usd,
        max_calls=max(task.call_count for task in case.tasks),
        enabled_checks=case.enabled_checks,
        required_coverage=case.required_coverage,
        decision_contract_digest=case.decision_contract_digest,
    )


FIELDNAMES = (
    "protocol_version",
    "case_id",
    "fixture_id",
    "evidence_layer",
    "operation",
    "target_json_pointer",
    "decision_contract_digest",
    "complete_decision",
    "library_outcome",
    "operational_outcome",
    "ablated_decision",
    "assurance_case_emitted",
    "error_type",
    "error_code",
    "detection_boundary",
    "complete_attempts",
    "ablated_attempts",
    "complete_total_cost_usd",
    "ablated_total_cost_usd",
    "complete_p95_cost_usd",
    "ablated_p95_cost_usd",
    "complete_max_calls",
    "ablated_max_calls",
    "false_scale",
)


def _number(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.4f}"


def run_benchmark() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for spec in ABLATIONS:
        complete_raw = build_fixture(spec.fixture_id)
        complete = evaluate_raw(complete_raw, case_id=spec.case_id)
        ablated_raw = deepcopy(complete_raw)
        apply_ablation(ablated_raw, spec)
        ablated = evaluate_raw(ablated_raw, case_id=spec.case_id)

        false_scale = (
            complete.decision != Decision.SCALE.value
            and ablated.library_outcome == DECISION
            and ablated.decision == Decision.SCALE.value
        )
        detection_boundary = {
            SCHEMA_ERROR: "raw_schema",
            EVIDENCE_ERROR: "semantic_validation",
            EVALUATION_ERROR: "evaluation",
            DECISION: "none",
        }[ablated.library_outcome]
        rows.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "case_id": spec.case_id,
                "fixture_id": spec.fixture_id,
                "evidence_layer": spec.evidence_layer,
                "operation": spec.operation,
                "target_json_pointer": spec.target_json_pointer,
                "decision_contract_digest": complete.decision_contract_digest,
                "complete_decision": complete.decision,
                "library_outcome": ablated.library_outcome,
                "operational_outcome": ablated.operational_outcome,
                "ablated_decision": ablated.decision,
                "assurance_case_emitted": str(
                    ablated.assurance_case_emitted
                ).lower(),
                "error_type": ablated.error_type,
                "error_code": ablated.error_code,
                "detection_boundary": detection_boundary,
                "complete_attempts": _number(complete.attempts),
                "ablated_attempts": _number(ablated.attempts),
                "complete_total_cost_usd": _number(complete.total_cost_usd),
                "ablated_total_cost_usd": _number(ablated.total_cost_usd),
                "complete_p95_cost_usd": _number(complete.p95_cost_usd),
                "ablated_p95_cost_usd": _number(ablated.p95_cost_usd),
                "complete_max_calls": _number(complete.max_calls),
                "ablated_max_calls": _number(ablated.max_calls),
                "false_scale": str(false_scale).lower(),
            }
        )
    return rows


def validate_rows(rows: Sequence[dict[str, str]]) -> tuple[str, ...]:
    problems: list[str] = []
    if len(rows) != len(ABLATIONS):
        problems.append(f"expected {len(ABLATIONS)} rows, observed {len(rows)}")
        return tuple(problems)

    by_case = {row["case_id"]: row for row in rows}
    for spec in ABLATIONS:
        row = by_case.get(spec.case_id)
        if row is None:
            problems.append(f"missing case {spec.case_id}")
            continue
        expected = {
            "complete_decision": spec.complete_decision,
            "library_outcome": spec.library_outcome,
            "operational_outcome": spec.operational_outcome,
            "ablated_decision": spec.ablated_decision,
            "error_type": spec.error_type,
            "error_code": spec.error_code,
        }
        for field, value in expected.items():
            if row[field] != value:
                problems.append(
                    f"{spec.case_id}: expected {field}={value!r}, "
                    f"observed {row[field]!r}"
                )
        if row["decision_contract_digest"] != DECISION_CONTRACT_DIGEST:
            problems.append(f"{spec.case_id}: decision contract changed")

    operational_refusals = sum(
        row["operational_outcome"] == INCOMPLETE for row in rows
    )
    false_scales = sum(row["false_scale"] == "true" for row in rows)
    if operational_refusals != 4:
        problems.append(f"expected 4 operational refusals, observed {operational_refusals}")
    if false_scales != 5:
        problems.append(f"expected 5 false SCALE transitions, observed {false_scales}")
    return tuple(problems)


def render_csv(rows: Sequence[dict[str, str]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def summarize(
    rows: Sequence[dict[str, str]], *, results_csv_sha256: str
) -> dict[str, Any]:
    outcome_counts = {
        outcome: sum(row["library_outcome"] == outcome for row in rows)
        for outcome in (SCHEMA_ERROR, EVIDENCE_ERROR, EVALUATION_ERROR, DECISION)
    }
    return {
        "benchmark_id": BENCHMARK_ID,
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "ablation_count": len(rows),
        "operational_refusals": sum(
            row["operational_outcome"] == INCOMPLETE for row in rows
        ),
        "assist_to_scale_transitions": sum(
            row["complete_decision"] == Decision.ASSIST.value
            and row["ablated_decision"] == Decision.SCALE.value
            for row in rows
        ),
        "false_scale_transitions": sum(
            row["false_scale"] == "true" for row in rows
        ),
        "incomplete_assurance_cases": sum(
            row["assurance_case_emitted"] == "true"
            and row["ablated_decision"] == Decision.INCOMPLETE.value
            for row in rows
        ),
        "library_outcomes": outcome_counts,
        "fixed_decision_contract": {
            "digest": DECISION_CONTRACT_DIGEST,
            "enabled_checks": list(CHECK_MANIFEST),
            "required_coverage": list(REQUIRED_COVERAGE),
        },
        "results_csv_sha256": results_csv_sha256,
        "claim_boundary": [
            "These are synthetic boundary fixtures, not production prevalence.",
            "The benchmark removes raw evidence and never removes an assurance gate.",
            "Operational INCOMPLETE may be a CLI refusal without an assurance artifact.",
            "A deleted attempt cannot be detected without a source completeness contract.",
        ],
    }


def render_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def render_terminal_summary(summary: dict[str, Any]) -> str:
    outcomes = summary["library_outcomes"]
    return "\n".join(
        [
            "# Raw Evidence-Ablation Results",
            "",
            f"ablations                  {summary['ablation_count']}",
            f"adapter schema errors      {outcomes[SCHEMA_ERROR]}",
            f"semantic evidence errors   {outcomes[EVIDENCE_ERROR]}",
            f"operational refusals       {summary['operational_refusals']}",
            f"ASSIST -> SCALE             {summary['assist_to_scale_transitions']}",
            f"INCOMPLETE case artifacts  {summary['incomplete_assurance_cases']}",
            "",
            "The five transitions are boundary-case conformance results, not a rate.",
        ]
    )


def build_artifacts(rows: Sequence[dict[str, str]]) -> dict[str, str]:
    csv_text = render_csv(rows)
    summary = summarize(
        rows,
        results_csv_sha256=hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
    )
    return {
        "results.csv": csv_text,
        "summary.json": render_json(summary),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = run_benchmark()
    problems = validate_rows(rows)
    if problems:
        print("Evidence-ablation conformance failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    artifacts = build_artifacts(rows)
    if args.verify_dir:
        mismatches = [
            name
            for name, content in artifacts.items()
            if not (args.verify_dir / name).exists()
            or (args.verify_dir / name).read_text(encoding="utf-8") != content
        ]
        if mismatches:
            print("Generated evidence-ablation artifacts differ: " + ", ".join(mismatches))
            return 1

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in artifacts.items():
            (args.output_dir / name).write_text(content, encoding="utf-8")

    summary = json.loads(artifacts["summary.json"])
    print(render_terminal_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
