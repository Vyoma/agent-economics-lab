from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from typing import Any

from agent_economics.cli import main as cli_main
from evidence_ablation import (
    ABLATIONS,
    CHECK_MANIFEST,
    DECISION,
    DECISION_CONTRACT_DIGEST,
    EVALUATION_ERROR,
    EVIDENCE_ERROR,
    INCOMPLETE,
    REQUIRED_COVERAGE,
    SCHEMA_ERROR,
    apply_ablation,
    build_artifacts,
    build_fixture,
    evaluate_raw,
    main,
    run_benchmark,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "research" / "results" / "evidence-ablation"


def _resolve(raw: dict[str, Any], path: tuple[str | int, ...]) -> Any:
    value: Any = raw
    for part in path:
        value = value[part]
    return value


class EvidenceAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = run_benchmark()
        cls.by_case = {row["case_id"]: row for row in cls.rows}
        cls.artifacts = build_artifacts(cls.rows)
        cls.summary = json.loads(cls.artifacts["summary.json"])

    def test_case_registry_is_frozen(self) -> None:
        self.assertEqual(
            [spec.case_id for spec in ABLATIONS],
            [
                "drop_outcome_record",
                "drop_baseline_object",
                "drop_incident_loss",
                "drop_remediation_cost",
                "drop_human_review_time",
                "drop_trace_cost",
                "drop_manifest_task",
                "drop_policy_threshold",
                "drop_timed_out_event",
            ],
        )
        self.assertEqual(len(self.rows), 9)

    def test_current_behavior_matrix_is_exact(self) -> None:
        expected = {
            "drop_outcome_record": ("SCALE", EVIDENCE_ERROR, INCOMPLETE, ""),
            "drop_baseline_object": ("SCALE", SCHEMA_ERROR, INCOMPLETE, ""),
            "drop_incident_loss": ("ASSIST", DECISION, "SCALE", "SCALE"),
            "drop_remediation_cost": ("ASSIST", DECISION, "SCALE", "SCALE"),
            "drop_human_review_time": ("ASSIST", DECISION, "SCALE", "SCALE"),
            "drop_trace_cost": ("ASSIST", DECISION, "SCALE", "SCALE"),
            "drop_manifest_task": ("SCALE", EVIDENCE_ERROR, INCOMPLETE, ""),
            "drop_policy_threshold": ("SCALE", SCHEMA_ERROR, INCOMPLETE, ""),
            "drop_timed_out_event": ("ASSIST", DECISION, "SCALE", "SCALE"),
        }
        observed = {
            case_id: (
                row["complete_decision"],
                row["library_outcome"],
                row["operational_outcome"],
                row["ablated_decision"],
            )
            for case_id, row in self.by_case.items()
        }
        self.assertEqual(observed, expected)

    def test_aggregate_counts_are_exact(self) -> None:
        self.assertEqual(self.summary["ablation_count"], 9)
        self.assertEqual(
            self.summary["library_outcomes"],
            {
                DECISION: 5,
                EVALUATION_ERROR: 0,
                EVIDENCE_ERROR: 2,
                SCHEMA_ERROR: 2,
            },
        )
        self.assertEqual(self.summary["operational_refusals"], 4)
        self.assertEqual(self.summary["assist_to_scale_transitions"], 5)
        self.assertEqual(self.summary["false_scale_transitions"], 5)
        self.assertEqual(self.summary["incomplete_assurance_cases"], 0)

    def test_each_spec_deletes_exactly_one_target(self) -> None:
        for spec in ABLATIONS:
            with self.subTest(case_id=spec.case_id):
                before = build_fixture(spec.fixture_id)
                after = deepcopy(before)
                removed = deepcopy(_resolve(before, spec.target))
                apply_ablation(after, spec)

                parent_before = _resolve(before, spec.target[:-1])
                parent_after = _resolve(after, spec.target[:-1])
                final = spec.target[-1]
                restored = deepcopy(after)
                restored_parent = _resolve(restored, spec.target[:-1])
                if isinstance(final, int):
                    self.assertEqual(len(parent_after), len(parent_before) - 1)
                    restored_parent.insert(final, removed)
                else:
                    self.assertNotIn(final, parent_after)
                    self.assertIn(final, parent_before)
                    restored_parent[final] = removed
                self.assertEqual(restored, before)

    def test_gates_and_required_coverage_never_change(self) -> None:
        for spec in ABLATIONS:
            with self.subTest(case_id=spec.case_id):
                complete_raw = build_fixture(spec.fixture_id)
                complete = evaluate_raw(complete_raw, case_id=spec.case_id)
                self.assertEqual(complete.enabled_checks, CHECK_MANIFEST)
                self.assertEqual(complete.required_coverage, REQUIRED_COVERAGE)
                self.assertEqual(
                    complete.decision_contract_digest,
                    DECISION_CONTRACT_DIGEST,
                )

                ablated_raw = deepcopy(complete_raw)
                apply_ablation(ablated_raw, spec)
                ablated = evaluate_raw(ablated_raw, case_id=spec.case_id)
                if ablated.library_outcome == DECISION:
                    self.assertEqual(ablated.enabled_checks, CHECK_MANIFEST)
                    self.assertEqual(ablated.required_coverage, REQUIRED_COVERAGE)
                    self.assertEqual(
                        ablated.decision_contract_digest,
                        DECISION_CONTRACT_DIGEST,
                    )

    def test_defaulted_cost_omissions_match_explicit_zero(self) -> None:
        for case_id in (
            "drop_incident_loss",
            "drop_remediation_cost",
            "drop_human_review_time",
            "drop_trace_cost",
        ):
            spec = next(spec for spec in ABLATIONS if spec.case_id == case_id)
            with self.subTest(case_id=case_id):
                raw = build_fixture(spec.fixture_id)
                explicit_zero = deepcopy(raw)
                parent = _resolve(explicit_zero, spec.target[:-1])
                parent[spec.target[-1]] = 0.0
                zero_result = evaluate_raw(explicit_zero, case_id=case_id)

                missing = deepcopy(raw)
                apply_ablation(missing, spec)
                missing_result = evaluate_raw(missing, case_id=case_id)

                self.assertEqual(zero_result.library_outcome, DECISION)
                self.assertEqual(zero_result.decision, "SCALE")
                self.assertEqual(missing_result.decision, zero_result.decision)
                self.assertEqual(
                    missing_result.total_cost_usd, zero_result.total_cost_usd
                )

    def test_error_codes_are_stable(self) -> None:
        self.assertEqual(
            {
                case_id: (row["error_type"], row["error_code"])
                for case_id, row in self.by_case.items()
                if row["error_code"]
            },
            {
                "drop_outcome_record": (
                    "ValueError",
                    "TRACE_OUTCOME_MISMATCH",
                ),
                "drop_baseline_object": ("KeyError", "MISSING_BASELINE"),
                "drop_manifest_task": (
                    "ValueError",
                    "MANIFEST_COVERAGE_MISMATCH",
                ),
                "drop_policy_threshold": (
                    "TypeError",
                    "MISSING_POLICY_THRESHOLD",
                ),
            },
        )

    def test_cli_projects_rejections_to_incomplete(self) -> None:
        rejecting = (
            "drop_outcome_record",
            "drop_baseline_object",
            "drop_manifest_task",
            "drop_policy_threshold",
        )
        for case_id in rejecting:
            spec = next(spec for spec in ABLATIONS if spec.case_id == case_id)
            with self.subTest(case_id=case_id), tempfile.TemporaryDirectory() as directory:
                raw = build_fixture(spec.fixture_id)
                apply_ablation(raw, spec)
                bundle = Path(directory) / "bundle.json"
                bundle.write_text(json.dumps(raw), encoding="utf-8")
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = cli_main(
                        [
                            "evaluate",
                            "--bundle",
                            str(bundle),
                            "--format",
                            "json",
                            "--ci",
                        ]
                    )
                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("INCOMPLETE: invalid evidence:", stderr.getvalue())

    def test_checked_in_artifacts_are_reproducible(self) -> None:
        for name, content in self.artifacts.items():
            with self.subTest(name=name):
                self.assertEqual(
                    (RESULTS / name).read_text(encoding="utf-8"),
                    content,
                )

    def test_verification_precedes_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            stale = {
                "results.csv": "stale results\n",
                "summary.json": "stale summary\n",
            }
            for name, content in stale.items():
                (target / name).write_text(content, encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--output-dir",
                        str(target),
                        "--verify-dir",
                        str(target),
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertIn(
                "Generated evidence-ablation artifacts differ",
                stdout.getvalue(),
            )
            for name, content in stale.items():
                self.assertEqual(
                    (target / name).read_text(encoding="utf-8"),
                    content,
                )


if __name__ == "__main__":
    unittest.main()
